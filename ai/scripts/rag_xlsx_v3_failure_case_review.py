"""Review the four XLSX v3 degraded location cases for Track A."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_POSITIVE_GOLD = Path("eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv")
DEFAULT_DIAGNOSTIC_REPORT = Path("reports/rag_eval/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json")
DEFAULT_FAILURE_BREAKDOWN = Path("reports/rag_eval/rag-ingestion/rag_xlsx_v3_after_cleanup_failure_breakdown.json")
DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/rag_xlsx_v3_failure_case_review.json")

DEFAULT_TARGET_QUERY_IDS = [
    "gq_xlsx_lookup_002",
    "gq_auto_042",
    "gq_auto_041",
    "gq_xlsx_date_number_format_001",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gold_rows = read_csv_rows(Path(args.positive_gold))
    diagnostic_report = read_json(Path(args.diagnostic_report))
    failure_breakdown = read_json(Path(args.failure_breakdown))
    payload = build_review(
        args=args,
        gold_rows=gold_rows,
        diagnostic_report=diagnostic_report,
        failure_breakdown=failure_breakdown,
    )
    write_json(Path(args.output), payload)
    print_json(
        {
            "status": payload["status"],
            "output": args.output,
            "reviewed_degraded_query_count": payload["reviewed_degraded_query_count"],
            "unknown_category_count": payload["unknown_category_count"],
            "unclassified_next_action_count": payload["unclassified_next_action_count"],
            "true_retrieval_ranking_failure_count": payload["true_retrieval_ranking_failure_count"],
        }
    )
    return 0 if payload["status"] == "COMPLETED" else 1


def build_review(
    *,
    args: argparse.Namespace,
    gold_rows: list[dict[str, str]],
    diagnostic_report: Mapping[str, Any],
    failure_breakdown: Mapping[str, Any],
) -> dict[str, Any]:
    target_ids = parse_target_ids(args.target_query_ids)
    gold_duplicates = duplicate_ids(gold_rows)
    diagnostic_rows = [
        row
        for row in (diagnostic_report.get("query_results") or diagnostic_report.get("per_query") or [])
        if isinstance(row, Mapping)
    ]
    diagnostic_duplicates = duplicate_ids(diagnostic_rows)
    degraded_rows = [
        row
        for row in failure_breakdown.get("failed_or_degraded_rows") or []
        if isinstance(row, Mapping)
    ]
    breakdown_duplicates = duplicate_ids(degraded_rows)
    degraded_ids = [str(row.get("query_id") or "") for row in degraded_rows if row.get("query_id")]
    unreviewed_degraded_ids = sorted(set(degraded_ids) - set(target_ids))
    target_not_degraded_ids = sorted(set(target_ids) - set(degraded_ids))
    gold_by_id = {row.get("query_id", ""): row for row in gold_rows}
    query_results_by_id = {
        row.get("query_id", ""): row
        for row in diagnostic_rows
    }
    breakdown_by_id = {
        row.get("query_id", ""): row
        for row in degraded_rows
    }
    rows = [
        build_review_row(
            query_id=query_id,
            gold=gold_by_id.get(query_id, {}),
            diagnostic=query_results_by_id.get(query_id, {}),
            breakdown=breakdown_by_id.get(query_id, {}),
        )
        for query_id in target_ids
    ]
    category_counts = Counter(str(row.get("category") or "UNKNOWN") for row in rows)
    unknown_count = sum(1 for row in rows if row.get("category") in {"", None, "UNKNOWN"})
    unclassified_count = sum(1 for row in rows if row.get("recommended_next_action") in {"", None, "UNCLASSIFIED"})
    true_failure_count = sum(1 for row in rows if row.get("category") == "TRUE_RETRIEVAL_RANKING_FAILURE")
    blockers = []
    if gold_duplicates:
        blockers.append("duplicate_gold_query_ids")
    if diagnostic_duplicates:
        blockers.append("duplicate_diagnostic_query_ids")
    if breakdown_duplicates:
        blockers.append("duplicate_failure_breakdown_query_ids")
    if unreviewed_degraded_ids:
        blockers.append("unreviewed_degraded_query_ids")
    if target_not_degraded_ids:
        blockers.append("target_query_ids_not_in_failure_breakdown")
    if unknown_count:
        blockers.append("unknown_category_count")
    if unclassified_count:
        blockers.append("unclassified_next_action_count")
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED" if not blockers else "NEEDS_REVIEW",
        "report_role": "xlsx_v3_failure_case_review",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "source_positive_gold": args.positive_gold,
        "source_diagnostic_report": args.diagnostic_report,
        "source_failure_breakdown": args.failure_breakdown,
        "target_query_ids": target_ids,
        "failure_breakdown_query_ids": degraded_ids,
        "unreviewed_degraded_query_ids": unreviewed_degraded_ids,
        "target_query_ids_not_in_failure_breakdown": target_not_degraded_ids,
        "duplicate_query_ids": {
            "positive_gold": gold_duplicates,
            "diagnostic_report": diagnostic_duplicates,
            "failure_breakdown": breakdown_duplicates,
        },
        "reviewed_degraded_query_count": len(rows),
        "unknown_category_count": unknown_count,
        "unclassified_next_action_count": unclassified_count,
        "true_retrieval_ranking_failure_count": true_failure_count,
        "category_counts": dict(sorted(category_counts.items())),
        "rows": rows,
        "guardrails": {
            "promotion_evidence_true_set": False,
            "candidate_v1_mutated": False,
            "immutable_baseline_changed": False,
            "rag_data_canary_changed": False,
            "broad_reindex_executed": False,
            "hidden_negative_in_positive_metrics": False,
            "retrieval_algorithm_changed": False,
            "gold_manifest_changed": False,
        },
        "completion_criteria": {
            "reviewed_degraded_query_count": len(rows),
            "reviewed_degraded_query_count_is_4": len(rows) == 4,
            "all_degraded_query_ids_reviewed": not unreviewed_degraded_ids,
            "target_query_ids_are_degraded": not target_not_degraded_ids,
            "no_duplicate_query_ids": not (gold_duplicates or diagnostic_duplicates or breakdown_duplicates),
            "unknown_category_count": unknown_count,
            "unknown_category_count_is_0": unknown_count == 0,
            "unclassified_next_action_count": unclassified_count,
            "unclassified_next_action_count_is_0": unclassified_count == 0,
            "true_retrieval_ranking_failure_count": true_failure_count,
        },
        "blockers": blockers,
        "notes": [
            "A1 is evidence classification only; it does not modify query text, policy, parser, index, or baseline artifacts.",
            "True retrieval ranking failures should be handled by a separate retrieval experiment proposal, not by this Track A review.",
        ],
    }


def build_review_row(
    *,
    query_id: str,
    gold: Mapping[str, str],
    diagnostic: Mapping[str, Any],
    breakdown: Mapping[str, Any],
) -> dict[str, Any]:
    category = str(breakdown.get("category") or "UNKNOWN")
    return {
        "query_id": query_id,
        "query": diagnostic.get("query") or gold.get("query"),
        "original_query": gold.get("original_query") or breakdown.get("v2_query"),
        "query_seed": gold.get("query_seed") or breakdown.get("v2_query"),
        "expected_file_name": gold.get("expected_file_name") or diagnostic.get("expected_file_name"),
        "expected_document_version_id": gold.get("expected_document_version_id"),
        "expected_sheet_name": gold.get("expected_sheet_name") or diagnostic.get("expected_sheet_name"),
        "expected_cell_range": gold.get("expected_cell_range") or diagnostic.get("expected_cell_range"),
        "expected_table_id": gold.get("expected_table_id") or diagnostic.get("expected_table_id"),
        "range_match_policy": gold.get("range_match_policy"),
        "harness_range_match_policy": gold.get("harness_range_match_policy"),
        "v2_label_status": gold.get("v2_label_status"),
        "v2_eval_purpose": gold.get("eval_purpose"),
        "label_status": gold.get("label_status") or diagnostic.get("label_status"),
        "contract_value_surface": gold.get("contract_value_surface"),
        "embedding_text_surface_status": gold.get("embedding_text_surface_status"),
        "naturalization_anchor_terms": gold.get("naturalization_anchor_terms"),
        "top_k_hits": [normalize_hit(hit) for hit in diagnostic.get("top_k_results") or []],
        "hit_rank": diagnostic.get("hit_rank"),
        "location_rank": diagnostic.get("location_rank"),
        "location_match": diagnostic.get("location_match"),
        "failure_reason": diagnostic.get("failure_reason") or breakdown.get("v3_failure_reason"),
        "category": category,
        "category_rationale": breakdown.get("rationale"),
        "range_relation_in_top_k": breakdown.get("range_relation_in_top_k"),
        "recommended_next_phase": recommended_next_phase(category),
        "recommended_next_action": recommended_next_action(category),
    }


def normalize_hit(hit: Mapping[str, Any]) -> dict[str, Any]:
    location = hit.get("location_json") if isinstance(hit.get("location_json"), Mapping) else {}
    return {
        "rank": hit.get("rank"),
        "score": hit.get("score"),
        "search_unit_id": hit.get("search_unit_id"),
        "source_file_name": hit.get("source_file_name"),
        "sheet_name": location.get("sheet_name") or location.get("sheetName"),
        "cell_range": location.get("cell_range") or location.get("cellRange"),
        "table_id": location.get("table_id") or location.get("tableId"),
        "chunk_type": hit.get("chunk_type"),
        "citation_text": hit.get("citation_text"),
        "location_json": hit.get("location_json"),
        "parser_name": hit.get("parser_name"),
        "parser_version": hit.get("parser_version"),
        "embedding_status": hit.get("embedding_status"),
        "index_version": hit.get("index_version"),
        "match_breakdown": hit.get("match_breakdown") or {},
    }


def recommended_next_phase(category: str) -> str:
    return {
        "QUERY_NATURALIZATION_DRIFT": "A2",
        "RANGE_POLICY_MISMATCH": "A3",
        "FORMULA_DATE_CONTRACT_MISMATCH": "A4",
        "TRUE_RETRIEVAL_RANKING_FAILURE": "SEPARATE_EXPERIMENT_PROPOSAL",
        "CHUNK_GRANULARITY_ISSUE": "A5_DECISION_GATE",
    }.get(category, "A1_REVIEW_REQUIRED")


def recommended_next_action(category: str) -> str:
    return {
        "QUERY_NATURALIZATION_DRIFT": "A2_QUERY_SURFACE_REVIEW",
        "RANGE_POLICY_MISMATCH": "A3_RANGE_POLICY_REVIEW",
        "FORMULA_DATE_CONTRACT_MISMATCH": "A4_FORMULA_DATE_CONTRACT_REVIEW",
        "TRUE_RETRIEVAL_RANKING_FAILURE": "WRITE_SEPARATE_RETRIEVAL_EXPERIMENT_PROPOSAL",
        "CHUNK_GRANULARITY_ISSUE": "A5_EVALUATE_CANDIDATE_V2_NEED",
    }.get(category, "UNCLASSIFIED")


def parse_target_ids(raw: str) -> list[str]:
    ids = [part.strip() for part in raw.split(",") if part.strip()]
    return ids or list(DEFAULT_TARGET_QUERY_IDS)


def duplicate_ids(rows: list[Mapping[str, Any]]) -> list[str]:
    counts = Counter(str(row.get("query_id") or "") for row in rows if row.get("query_id"))
    return sorted(query_id for query_id, count in counts.items() if count > 1)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be an object: {path}")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positive-gold", default=str(DEFAULT_POSITIVE_GOLD))
    parser.add_argument("--diagnostic-report", default=str(DEFAULT_DIAGNOSTIC_REPORT))
    parser.add_argument("--failure-breakdown", default=str(DEFAULT_FAILURE_BREAKDOWN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--target-query-ids", default=",".join(DEFAULT_TARGET_QUERY_IDS))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
