"""Create XLSX query-evidence review decisions and a cleaned eval CSV.

This script does not modify the source gold CSV. It records review decisions
for the XLSX diagnostic cleanup rows and writes a derived XLSX eval set that
can be used for a later diagnostic rerun.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_CLEANUP_PLAN = Path("reports/rag_xlsx_query_evidence_cleanup_plan.json")
DEFAULT_RETRIEVAL_REPORT = Path("reports/rag_retrieval_eval_xlsx_vector_diagnostic_report.json")
DEFAULT_GOLD = Path("eval/gold_queries_v0.csv")
DEFAULT_OUTPUT = Path("reports/rag_xlsx_query_evidence_review_decisions.json")
DEFAULT_CLEANED_GOLD = Path("eval/gold_queries_xlsx_v1.csv")
DEFAULT_CANDIDATE_INDEX_VERSION = "rag-ingestion-v2-xlsx-candidate-v1"
DEFAULT_CLEANED_DATASET_ID = "gold_queries_xlsx_v1"
DEFAULT_CLEANED_DATASET_VERSION = "xlsx_v1_reviewed_positive_35"

DECISION_KEEP = "KEEP_AS_POSITIVE"
DECISION_NEGATIVE = "RELABEL_AS_NEGATIVE_HIDDEN_POLICY"
DECISION_EXCLUDE = "EXCLUDE_FROM_PROMOTION_EVAL"
DECISION_REBIND_FILE = "REBIND_EXPECTED_FILE_OR_DOCV"
DECISION_REBIND_RANGE = "REBIND_EXPECTED_SHEET_OR_RANGE"
DECISION_RANGE_OVERLAP = "RELAX_MATCH_POLICY_TO_RANGE_OVERLAP"
DECISION_CHUNK_FIX = "REQUIRE_CHUNK_GRANULARITY_FIX"
DECISION_TUNING_LATER = "REQUIRE_RETRIEVAL_TUNING_LATER"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cleanup = read_json(Path(args.cleanup_plan))
    retrieval = read_json(Path(args.retrieval_report))
    gold_rows = read_gold_rows(Path(args.gold))
    payload, cleaned_rows = build_review(
        cleanup=cleanup,
        retrieval=retrieval,
        gold_rows=gold_rows,
        cleanup_path=Path(args.cleanup_plan),
        retrieval_path=Path(args.retrieval_report),
        gold_path=Path(args.gold),
        cleaned_gold_path=Path(args.cleaned_gold),
        candidate_index_version=args.candidate_index_version,
        cleaned_dataset_id=args.cleaned_dataset_id,
        cleaned_dataset_version=args.cleaned_dataset_version,
    )
    write_cleaned_csv(Path(args.cleaned_gold), cleaned_rows, gold_rows)
    payload["cleaned_eval_set"]["sha256"] = sha256_file(Path(args.cleaned_gold))
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0


def build_review(
    *,
    cleanup: Mapping[str, Any],
    retrieval: Mapping[str, Any],
    gold_rows: list[dict[str, str]],
    cleanup_path: Path,
    retrieval_path: Path,
    gold_path: Path,
    cleaned_gold_path: Path,
    candidate_index_version: str,
    cleaned_dataset_id: str,
    cleaned_dataset_version: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    gold_by_id = {row.get("query_id", ""): row for row in gold_rows}
    cleanup_rows = list(cleanup.get("cleanup_rows") or [])
    xlsx_rows = [
        row for row in cleanup_rows
        if str(row.get("bucket") or "").startswith("xlsx") or row.get("bucket") == "mixed_text_table"
    ]
    decisions = [review_row(row, gold_by_id.get(str(row.get("query_id") or ""), {})) for row in xlsx_rows]
    decision_by_id = {row["query_id"]: row for row in decisions}
    cleaned_rows: list[dict[str, str]] = []
    for row in gold_rows:
        query_id = row.get("query_id", "")
        decision = decision_by_id.get(query_id)
        if not decision or not decision["promotion_eval_eligible"]:
            continue
        cleaned = dict(row)
        cleaned["review_decision"] = decision["decision"]
        cleaned["review_category"] = decision["category"]
        cleaned["review_reason_code"] = decision["reason_code"]
        cleaned["policy_label"] = decision["policy_label"]
        cleaned["promotion_eval_eligible"] = "true"
        cleaned["cleanup_source_query_id"] = query_id
        cleaned_rows.append(cleaned)

    unresolved_source_ids = [
        str(row.get("query_id") or "")
        for row in xlsx_rows
        if row.get("cleanup_status") != "ready"
    ]
    unreviewed = sorted(set(unresolved_source_ids) - {row["query_id"] for row in decisions})
    decision_counts = Counter(row["decision"] for row in decisions)
    category_counts = Counter(row["category"] for row in decisions)
    eligible_decisions = [row for row in decisions if row["promotion_eval_eligible"]]
    deferred_decisions = [row for row in decisions if not row["promotion_eval_eligible"]]

    return (
        {
            "run_id": utc_run_id(),
            "generated_at": utc_timestamp(),
            "status": "READY_FOR_CLEANED_DIAGNOSTIC_RERUN" if not unreviewed else "NEEDS_REVIEW",
            "report_role": "xlsx_query_evidence_review_decisions",
            "promotion_evidence": False,
            "evidence_role": "diagnostic_review_overlay",
            "source_cleanup_plan": str(cleanup_path),
            "source_retrieval_report": str(retrieval_path),
            "source_gold": str(gold_path),
            "candidate_index_version": candidate_index_version,
            "retrieval_backend": retrieval.get("retrieval_backend"),
            "retrieval_promotion_evidence": retrieval.get("promotion_evidence"),
            "retrieval_evidence_role": retrieval.get("evidence_role"),
            "query_count": len(xlsx_rows),
            "source_ready_query_count": cleanup.get("ready_query_count"),
            "source_unresolved_query_count": cleanup.get("unresolved_query_count"),
            "reviewed_unresolved_query_count": len(unresolved_source_ids) - len(unreviewed),
            "unreviewed_unresolved_query_count": len(unreviewed),
            "promotion_eval_eligible_count": len(eligible_decisions),
            "excluded_or_deferred_count": len(deferred_decisions),
            "decision_counts": dict(sorted(decision_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
            "decision_query_ids": ids_by_field(decisions, "decision"),
            "category_query_ids": ids_by_field(decisions, "category"),
            "cleaned_eval_set": {
                "path": str(cleaned_gold_path),
                "eval_dataset_id": cleaned_dataset_id,
                "eval_dataset_version": cleaned_dataset_version,
                "row_count": len(cleaned_rows),
                "source": str(gold_path),
                "selection_rule": "promotion_eval_eligible=true from this review overlay",
                "expected_location_type": "xlsx",
                "promotion_evidence": False,
                "sha256": None,
            },
            "rerun_preparation": {
                "diagnostic_only_command": [
                    "python",
                    "scripts/rag_retrieval_eval.py",
                    "--gold",
                    str(cleaned_gold_path),
                    "--retrieval-backend",
                    "vector",
                    "--vector-index-dir",
                    "rag-data-xlsx-candidate-v1",
                    "--candidate-index-version",
                    candidate_index_version,
                    "--required-index-version",
                    candidate_index_version,
                    "--required-embedding-status",
                    "EMBEDDED",
                    "--top-k",
                    "10",
                    "--report",
                    "reports/rag_retrieval_eval_xlsx_v1_vector_diagnostic_report.json",
                ],
                "promotion_evidence": False,
                "note": "Do not add --promotion-evidence until this diagnostic-only rerun is explicitly accepted.",
            },
            "decisions": decisions,
            "blockers": [] if not unreviewed else ["some unresolved XLSX rows were not reviewed"],
            "warnings": [
                "Rows excluded or relabeled here are not silently removed from provenance; they remain in decisions.",
                "RELAX_MATCH_POLICY_TO_RANGE_OVERLAP is a review decision only; no matching policy was changed.",
            ],
            "notes": [
                "eval/gold_queries_v0.csv is not modified.",
                "eval/gold_queries_xlsx_v1.csv contains only promotion_eval_eligible=true rows.",
                "This report does not run promotion, hybrid search, reranking, parser expansion, or threshold changes.",
            ],
        },
        cleaned_rows,
    )


def review_row(row: Mapping[str, Any], gold: Mapping[str, str]) -> dict[str, Any]:
    query_id = str(row.get("query_id") or "")
    bucket = str(row.get("bucket") or "")
    cleanup_action = str(row.get("cleanup_action") or "")
    category = str(row.get("failure_category") or "")
    flags = list(row.get("diagnostic_flags") or [])
    top_hits = list(row.get("top_hits") or [])
    supporting_hits = list(row.get("supporting_hits") or [])

    if row.get("cleanup_status") == "ready":
        decision = DECISION_KEEP
        review_category = "matched"
        reason_code = "diagnostic_location_matched"
        eligible = True
        policy_label = "positive"
    elif cleanup_action == "gold_policy_negative_relabel_or_exclude":
        decision = DECISION_NEGATIVE
        review_category = "hidden_policy_contract"
        reason_code = "negative_hidden_policy_row_requires_explicit_policy_eval"
        eligible = False
        policy_label = "negative_hidden_policy"
    elif bucket in {"xlsx_formula_value", "xlsx_date_number_format"}:
        if has_range_overlap(row):
            decision = DECISION_RANGE_OVERLAP
            reason_code = "formula_or_date_row_has_overlap_but_not_contains_policy_match"
        else:
            decision = DECISION_EXCLUDE
            reason_code = "formula_or_date_value_not_proven_in_current_indexed_text_contract"
        review_category = "formula_date_contract"
        eligible = False
        policy_label = "defer_formula_date_contract"
    elif cleanup_action == "xlsx_table_chunk_ranking_or_query_contract_review":
        decision = DECISION_EXCLUDE
        review_category = "table_range_strictness"
        reason_code = "expected_table_id_not_present_on_matching_sheet_range_hit"
        eligible = False
        policy_label = "defer_table_contract"
    elif cleanup_action == "gold_binding_review_required":
        if category == "xlsx_table_metadata_or_gold_binding_mismatch":
            decision = DECISION_REBIND_RANGE
            review_category = "table_range_strictness"
            reason_code = "matching_range_exists_but_gold_table_binding_is_too_strict"
        elif category == "xlsx_other_location_mismatch":
            decision = DECISION_REBIND_RANGE
            review_category = "gold_binding"
            reason_code = "same_file_sheet_hits_disagree_with_expected_range_binding"
        else:
            decision = DECISION_REBIND_FILE
            review_category = "gold_binding"
            reason_code = "gold_file_or_document_version_binding_needs_review"
        eligible = False
        policy_label = "defer_gold_rebind"
    elif cleanup_action == "chunk_granularity_or_range_policy_review":
        decision = DECISION_CHUNK_FIX
        review_category = "chunk_granularity"
        reason_code = "same_sheet_hit_but_expected_range_absent"
        eligible = False
        policy_label = "defer_chunk_granularity"
    else:
        decision = DECISION_TUNING_LATER
        review_category = "true_retrieval_ranking_failure"
        reason_code = "expected_file_or_location_absent_after_candidate_filters"
        eligible = False
        policy_label = "defer_retrieval_tuning"

    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": row.get("query") or gold.get("query"),
        "decision": decision,
        "category": review_category,
        "reason_code": reason_code,
        "policy_label": policy_label,
        "promotion_eval_eligible": eligible,
        "cleaned_eval_action": "include" if eligible else "exclude_or_defer",
        "source_cleanup_action": cleanup_action,
        "source_cleanup_status": row.get("cleanup_status"),
        "source_failure_category": category,
        "source_suspect_group": row.get("suspect_group"),
        "failure_reason": row.get("failure_reason"),
        "hit_rank": row.get("hit_rank"),
        "location_rank": row.get("location_rank"),
        "diagnostic_flags": flags,
        "gold_fields": row.get("gold_fields") or {},
        "evidence_summary": {
            "top_hit_count": len(top_hits),
            "supporting_hit_count": len(supporting_hits),
            "supporting_hit_ranks": row.get("supporting_hit_ranks") or [],
            "range_overlap_observed": has_range_overlap(row),
            "expected_table_id_not_present": "expected_table_id_not_present_on_range_hit" in flags,
        },
        "top_hits": top_hits[:5],
        "supporting_hits": supporting_hits[:5],
    }


def has_range_overlap(row: Mapping[str, Any]) -> bool:
    hits = list(row.get("supporting_hits") or []) + list(row.get("top_hits") or [])
    expected = row.get("gold_fields") or {}
    expected_range = str(expected.get("expected_cell_range") or "")
    if not expected_range:
        return False
    expected_cells = parse_a1_range(expected_range)
    if expected_cells is None:
        return False
    for hit in hits:
        if not hit.get("xlsx_sheet_match"):
            continue
        hit_range = str(hit.get("cell_range") or "")
        hit_cells = parse_a1_range(hit_range)
        if hit_cells and ranges_overlap(expected_cells, hit_cells):
            return True
    return False


def parse_a1_range(value: str) -> tuple[int, int, int, int] | None:
    if ":" not in value:
        return None
    start, end = value.split(":", 1)
    start_cell = parse_cell(start)
    end_cell = parse_cell(end)
    if not start_cell or not end_cell:
        return None
    start_col, start_row = start_cell
    end_col, end_row = end_cell
    return min(start_col, end_col), min(start_row, end_row), max(start_col, end_col), max(start_row, end_row)


def parse_cell(value: str) -> tuple[int, int] | None:
    letters = ""
    digits = ""
    for char in value.strip().upper():
        if "A" <= char <= "Z" and not digits:
            letters += char
        elif char.isdigit():
            digits += char
        else:
            return None
    if not letters or not digits:
        return None
    col = 0
    for char in letters:
        col = col * 26 + (ord(char) - ord("A") + 1)
    return col, int(digits)


def ranges_overlap(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> bool:
    l_col1, l_row1, l_col2, l_row2 = left
    r_col1, r_row1, r_col2, r_row2 = right
    return not (l_col2 < r_col1 or r_col2 < l_col1 or l_row2 < r_row1 or r_row2 < l_row1)


def ids_by_field(rows: list[Mapping[str, Any]], field: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "")].append(str(row.get("query_id") or ""))
    return {key: value for key, value in sorted(grouped.items())}


def write_cleaned_csv(path: Path, rows: list[dict[str, str]], original_rows: list[dict[str, str]]) -> None:
    original_fields = list(original_rows[0].keys()) if original_rows else []
    extra_fields = [
        "review_decision",
        "review_category",
        "review_reason_code",
        "policy_label",
        "promotion_eval_eligible",
        "cleanup_source_query_id",
    ]
    fieldnames = [*original_fields, *[field for field in extra_fields if field not in original_fields]]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_report(payload: Mapping[str, Any]) -> None:
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
    parser.add_argument("--cleanup-plan", default=str(DEFAULT_CLEANUP_PLAN))
    parser.add_argument("--retrieval-report", default=str(DEFAULT_RETRIEVAL_REPORT))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--cleaned-gold", default=str(DEFAULT_CLEANED_GOLD))
    parser.add_argument("--candidate-index-version", default=DEFAULT_CANDIDATE_INDEX_VERSION)
    parser.add_argument("--cleaned-dataset-id", default=DEFAULT_CLEANED_DATASET_ID)
    parser.add_argument("--cleaned-dataset-version", default=DEFAULT_CLEANED_DATASET_VERSION)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
