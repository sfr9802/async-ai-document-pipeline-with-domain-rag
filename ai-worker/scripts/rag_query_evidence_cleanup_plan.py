"""Plan query-level evidence cleanup for the full72 vector diagnostic.

This script is intentionally report-only. It does not rewrite the gold CSV,
change parser behavior, tune retrieval, or mark any diagnostic result as
promotion evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_BREAKDOWN = Path("eval/reports/rag-ingestion/rag_retrieval_full72_vector_quality_breakdown.json")
DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_v0.csv")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_full72_query_evidence_cleanup_plan.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    breakdown = read_json(Path(args.quality_breakdown))
    gold_rows = read_gold_rows(Path(args.gold))
    payload = build_cleanup_plan(
        breakdown=breakdown,
        gold_rows=gold_rows,
        quality_breakdown_path=Path(args.quality_breakdown),
        gold_path=Path(args.gold),
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0


def build_cleanup_plan(
    *,
    breakdown: Mapping[str, Any],
    gold_rows: list[dict[str, str]],
    quality_breakdown_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    gold_by_id = {row.get("query_id", ""): row for row in gold_rows}
    classified_rows = list(breakdown.get("classified_query_rows") or [])
    cleanup_rows: list[dict[str, Any]] = []
    action_counts: Counter[str] = Counter()
    owner_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    bucket_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in classified_rows:
        query_id = str(row.get("query_id") or "")
        gold = gold_by_id.get(query_id, {})
        cleanup = classify_cleanup(row, gold)
        cleanup_rows.append(cleanup)
        action_counts[cleanup["cleanup_action"]] += 1
        owner_counts[cleanup["owner"]] += 1
        status_counts[cleanup["cleanup_status"]] += 1
        bucket_counts[str(row.get("bucket") or "unknown")][cleanup["cleanup_action"]] += 1

    unresolved_rows = [
        row for row in cleanup_rows
        if row["cleanup_status"] in {"cleanup_required", "blocked_until_evidence_update"}
    ]
    promotion_ready_rows = [row for row in cleanup_rows if row["cleanup_status"] == "ready"]

    return {
        "run_id": utc_run_id(),
        "status": "NEEDS_CLEANUP" if unresolved_rows else "READY",
        "report_role": "query_level_evidence_cleanup_plan",
        "promotion_evidence": False,
        "quality_breakdown_report": str(quality_breakdown_path),
        "gold": str(gold_path),
        "query_count": len(cleanup_rows),
        "ready_query_count": len(promotion_ready_rows),
        "unresolved_query_count": len(unresolved_rows),
        "cleanup_action_counts": dict(action_counts),
        "owner_counts": dict(owner_counts),
        "cleanup_status_counts": dict(status_counts),
        "bucket_action_counts": {
            bucket: dict(counts)
            for bucket, counts in sorted(bucket_counts.items())
        },
        "promotion_grade_vector_eval_input": {
            "ready_now": not unresolved_rows,
            "ready_query_ids": [row["query_id"] for row in promotion_ready_rows],
            "unresolved_query_ids": [row["query_id"] for row in unresolved_rows],
            "decision": (
                "Do not run a promotion-evidence vector eval from this diagnostic set until unresolved "
                "query evidence rows are either corrected, explicitly excluded, or reclassified."
            ),
        },
        "pdf_page_bbox_resolution": pdf_page_bbox_resolution(cleanup_rows),
        "xlsx_resolution": xlsx_resolution(cleanup_rows),
        "cleanup_rows": cleanup_rows,
        "notes": [
            "This is diagnostic cleanup evidence only.",
            "It keeps gold cleanup, retrieval/ranking, bbox policy, and chunk granularity separate.",
            "It does not modify eval/gold_queries_v0.csv.",
        ],
    }


def classify_cleanup(row: Mapping[str, Any], gold: Mapping[str, str]) -> dict[str, Any]:
    bucket = str(row.get("bucket") or "")
    category = str(row.get("failure_category") or "")
    suspect_group = str(row.get("suspect_group") or "")
    flags = list(row.get("diagnostic_flags") or [])
    hidden_policy = str(gold.get("hidden_policy") or "")
    must_contain_terms = str(gold.get("must_contain_terms") or "").strip()
    must_not_contain_terms = str(gold.get("must_not_contain_terms") or "").strip()
    notes = str(gold.get("notes") or "").lower()

    if category == "ok":
        action = "keep_for_promotion_eval"
        owner = "none"
        status = "ready"
        rationale = "Diagnostic hit and location matched the current gold binding."
    elif bucket == "xlsx_hidden_policy":
        if hidden_policy == "negative":
            action = "keep_hidden_negative_policy_check"
            owner = "none"
            status = "ready" if row.get("failure_reason") not in {"hidden_content_returned"} else "cleanup_required"
            rationale = "Gold already marks this row as a negative hidden-leakage check."
        elif must_not_contain_terms and (not must_contain_terms or "negative" in notes):
            action = "gold_policy_negative_relabel_or_exclude"
            owner = "gold_cleanup"
            status = "cleanup_required"
            rationale = (
                "This row has negative hidden-leakage shape, but hidden_policy is not negative. "
                "Relabel it as hidden_policy=negative or explicitly exclude it before promotion eval."
            )
        else:
            action = "hidden_policy_visible_control_rebind_review"
            owner = "gold_cleanup"
            status = "cleanup_required"
            rationale = (
                "This hidden-policy row appears to be a visible-control query, so it should be rebound "
                "to visible indexed evidence instead of grouped with negative hidden-leakage rows."
            )
    elif category == "pdf_page_policy_missing_physical_or_label" or any(
        flag.startswith("correct_page_no_hit_but_missing_") for flag in flags
    ):
        action = "pdf_location_metadata_projection_or_matching_rule"
        owner = "metadata_projection_or_matching_policy"
        status = "blocked_until_evidence_update"
        rationale = (
            "A correct page_no appears in top hits, but physical_page_index and/or bbox evidence is "
            "missing from returned vector-hit metadata. Treat this separately from ranking."
        )
    elif category in {"pdf_expected_page_absent_in_top10", "pdf_expected_file_absent_in_top10"}:
        action = "retrieval_text_or_ranking_investigation"
        owner = "retrieval_quality"
        status = "cleanup_required"
        rationale = "Expected PDF file/page evidence is absent from top 10 after candidate filters."
    elif category in {"xlsx_table_metadata_or_gold_binding_mismatch", "xlsx_other_location_mismatch"}:
        if (
            category == "xlsx_table_metadata_or_gold_binding_mismatch"
            and gold.get("expected_chunk_type") == "table"
            and gold.get("expected_table_id")
            and any((hit.get("xlsx_range_policy_match") and not hit.get("xlsx_table_match")) for hit in row.get("top_hits") or [])
        ):
            action = "xlsx_table_chunk_ranking_or_query_contract_review"
            owner = "query_contract_or_ranking"
            status = "cleanup_required"
            rationale = (
                "The expected file/sheet/range appears in top hits, but the ranked hit is not the expected table chunk. "
                "Review table-chunk ranking versus gold query contract before treating this as a label-only issue."
            )
        else:
            action = "gold_binding_review_required"
            owner = "gold_cleanup"
            status = "cleanup_required"
            rationale = "Top hits suggest the file/range may exist, but table/location binding does not match gold."
    elif category == "xlsx_range_ranking_or_chunk_granularity_mismatch":
        action = "chunk_granularity_or_range_policy_review"
        owner = "chunk_granularity"
        status = "cleanup_required"
        rationale = "The expected sheet is found, but the expected range is not matched by current chunk/range policy."
    elif bucket in {"xlsx_formula_value", "xlsx_date_number_format"}:
        action = "gold_query_contract_review_required"
        owner = "gold_cleanup"
        status = "cleanup_required"
        rationale = "Formula/formatted-value rows need evidence that the indexed text contract carries the expected value."
    elif suspect_group == "gold_binding_or_label_suspect":
        action = "gold_binding_review_required"
        owner = "gold_cleanup"
        status = "cleanup_required"
        rationale = "The diagnostic classified this row as a likely gold binding or label issue."
    elif suspect_group == "chunk_granularity_suspect":
        action = "chunk_granularity_or_range_policy_review"
        owner = "chunk_granularity"
        status = "cleanup_required"
        rationale = "The diagnostic classified this row as a likely chunk granularity issue."
    else:
        action = "retrieval_text_or_ranking_investigation"
        owner = "retrieval_quality"
        status = "cleanup_required"
        rationale = "No matching evidence was found in the current top-k diagnostic result."

    return {
        "query_id": row.get("query_id"),
        "bucket": bucket,
        "query": row.get("query") or gold.get("query"),
        "failure_category": category,
        "suspect_group": suspect_group,
        "cleanup_action": action,
        "owner": owner,
        "cleanup_status": status,
        "rationale": rationale,
        "diagnostic_flags": flags,
        "hit_rank": row.get("hit_rank"),
        "location_rank": row.get("location_rank"),
        "failure_reason": row.get("failure_reason"),
        "gold_fields": {
            "expected_file_name": gold.get("expected_file_name"),
            "expected_document_version_id": gold.get("expected_document_version_id"),
            "expected_location_type": gold.get("expected_location_type"),
            "expected_sheet_name": gold.get("expected_sheet_name"),
            "expected_cell_range": gold.get("expected_cell_range"),
            "expected_table_id": gold.get("expected_table_id"),
            "expected_page_no": gold.get("expected_page_no"),
            "expected_physical_page_index": gold.get("expected_physical_page_index"),
            "expected_bbox": gold.get("expected_bbox"),
            "range_match_policy": gold.get("range_match_policy"),
            "hidden_policy": gold.get("hidden_policy"),
            "requires_formula_value": gold.get("requires_formula_value"),
            "requires_formatted_value": gold.get("requires_formatted_value"),
            "label_status": gold.get("label_status"),
        },
        "top_hits": row.get("top_hits") or [],
        "supporting_hit_ranks": row.get("supporting_hit_ranks") or [],
        "supporting_hits": row.get("supporting_hits") or [],
    }


def pdf_page_bbox_resolution(cleanup_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    pdf_rows = [row for row in cleanup_rows if str(row.get("bucket") or "").startswith("pdf")]
    metadata_rows = [
        row for row in pdf_rows
        if row.get("cleanup_action") == "pdf_location_metadata_projection_or_matching_rule"
    ]
    ranking_rows = [
        row for row in pdf_rows
        if row.get("cleanup_action") == "retrieval_text_or_ranking_investigation"
    ]
    flag_counts: Counter[str] = Counter()
    for row in pdf_rows:
        flag_counts.update(row.get("diagnostic_flags") or [])
    return {
        "pdf_query_count": len(pdf_rows),
        "metadata_projection_or_matching_policy_count": len(metadata_rows),
        "retrieval_or_ranking_count": len(ranking_rows),
        "diagnostic_flag_counts": dict(flag_counts),
        "metadata_projection_or_matching_policy_query_ids": [row["query_id"] for row in metadata_rows],
        "retrieval_or_ranking_query_ids": [row["query_id"] for row in ranking_rows],
    }


def xlsx_resolution(cleanup_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    xlsx_rows = [
        row for row in cleanup_rows
        if str(row.get("bucket") or "").startswith("xlsx") or row.get("bucket") == "mixed_text_table"
    ]
    by_action: dict[str, list[str]] = defaultdict(list)
    for row in xlsx_rows:
        by_action[str(row.get("cleanup_action"))].append(str(row.get("query_id")))
    return {
        "xlsx_query_count": len(xlsx_rows),
        "action_counts": {action: len(ids) for action, ids in sorted(by_action.items())},
        "action_query_ids": {action: ids for action, ids in sorted(by_action.items())},
    }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be an object: {path}")
    return payload


def read_gold_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-breakdown", default=str(DEFAULT_BREAKDOWN))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
