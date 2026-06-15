"""Prepare Track A A2 XLSX query surface review artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_POSITIVE_GOLD = Path("eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv")
DEFAULT_REVIEWED_GOLD = Path("eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv")
DEFAULT_A1_REVIEW = Path("reports/rag_eval/rag-ingestion/rag_xlsx_v3_failure_case_review.json")
DEFAULT_BEFORE_REPORT = Path("reports/rag_eval/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json")
DEFAULT_REVIEWED_REPORT = Path("reports/rag_eval/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json")
DEFAULT_PATCH_PLAN = Path("reports/rag_eval/rag-ingestion/rag_xlsx_query_surface_patch_plan.json")
DEFAULT_COMPARE_OUTPUT = Path("reports/rag_eval/rag-ingestion/rag_xlsx_v3_query_surface_before_after_compare.json")

QUERY_PATCHES = {
    "gq_xlsx_lookup_002": {
        "primary": "신분당선 승차총승객수 찾아줘.",
        "candidates": [
            "신분당선 승차총승객수 찾아줘.",
            "신분당선 월별 승차 자료 찾아줘.",
            "신분당선 승차 현황 알려줘.",
        ],
        "reason": "The current wording keeps only the line name and asks where it is; adding the metric anchor keeps a realistic query while pointing at the expected row group.",
    },
    "gq_auto_042": {
        "primary": "축복전문요양원 장기요양기관 정보 찾아줘.",
        "candidates": [
            "축복전문요양원 장기요양기관 정보 찾아줘.",
            "축복전문요양원 시설 정보 찾아줘.",
            "축복전문요양원 기관 정보 찾아줘.",
        ],
        "reason": "The current wording asks for a generic row; adding a weak domain anchor keeps the query natural without exposing file, sheet, or cell range.",
    },
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gold_rows = read_csv_rows(Path(args.positive_gold))
    a1_review = read_json(Path(args.a1_review))
    patch_plan = build_patch_plan(args=args, gold_rows=gold_rows, a1_review=a1_review)
    reviewed_path = Path(args.reviewed_gold)
    reviewed_base_rows = read_csv_rows(reviewed_path) if reviewed_path.exists() else gold_rows
    reviewed_rows = apply_query_patches(reviewed_base_rows)
    write_csv(Path(args.reviewed_gold), reviewed_rows)
    write_json(Path(args.patch_plan), patch_plan)

    compare = None
    reviewed_report = Path(args.reviewed_report)
    if reviewed_report.exists():
        compare = build_compare(
            args=args,
            before_report=read_json(Path(args.before_report)),
            after_report=read_json(reviewed_report),
            original_rows=gold_rows,
            reviewed_rows=reviewed_rows,
        )
        write_json(Path(args.compare_output), compare)

    print_json(
        {
            "status": "COMPLETED",
            "patch_plan": args.patch_plan,
            "reviewed_gold": args.reviewed_gold,
            "reviewed_query_count": len(QUERY_PATCHES),
            "query_quality_audit_pass": patch_plan["query_quality_audit"]["pass"],
            "compare_output": args.compare_output if compare else None,
            "compare_status": compare.get("status") if compare else "REVIEWED_REPORT_NOT_FOUND",
        }
    )
    return 0


def build_patch_plan(
    *,
    args: argparse.Namespace,
    gold_rows: list[dict[str, str]],
    a1_review: Mapping[str, Any],
) -> dict[str, Any]:
    rows_by_id = {row.get("query_id", ""): row for row in gold_rows}
    a1_by_id = {row.get("query_id", ""): row for row in a1_review.get("rows") or []}
    patch_rows = []
    audit_results = []
    for query_id, patch in QUERY_PATCHES.items():
        gold = rows_by_id.get(query_id, {})
        a1 = a1_by_id.get(query_id, {})
        audits = [audit_candidate(candidate, gold) for candidate in patch["candidates"]]
        audit_results.extend(audits)
        patch_rows.append(
            {
                "query_id": query_id,
                "category": a1.get("category"),
                "current_query": gold.get("query"),
                "original_query": gold.get("original_query"),
                "query_seed": gold.get("query_seed"),
                "expected_cell_range": gold.get("expected_cell_range"),
                "candidate_queries": [
                    {"query": candidate, "audit": audit}
                    for candidate, audit in zip(patch["candidates"], audits, strict=True)
                ],
                "selected_query": patch["primary"],
                "selection_reason": patch["reason"],
                "expected_effect": "Improve range anchor without changing candidate namespace or gold binding.",
            }
        )
    failed_audits = [audit for audit in audit_results if not audit["pass"]]
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED" if not failed_audits else "NEEDS_REVIEW",
        "report_role": "xlsx_query_surface_patch_plan",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_positive_gold": args.positive_gold,
        "source_a1_review": args.a1_review,
        "output_reviewed_gold": args.reviewed_gold,
        "reviewed_query_count": len(QUERY_PATCHES),
        "rows": patch_rows,
        "query_quality_audit": {
            "pass": not failed_audits,
            "failed_count": len(failed_audits),
            "failed": failed_audits,
            "checks": [
                "no cell range literal",
                "no exact sheet name",
                "no exact file name or file stem",
                "no hidden-policy terms from must_not_contain_terms",
            ],
        },
        "guardrails": guardrails_payload(),
    }


def apply_query_patches(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    reviewed = []
    for row in rows:
        copy = dict(row)
        patch = QUERY_PATCHES.get(copy.get("query_id", ""))
        if patch:
            copy["query"] = patch["primary"]
            copy["naturalization_notes"] = append_note(
                copy.get("naturalization_notes", ""),
                "track_a_a2_reviewed_query_candidate",
            )
        reviewed.append(copy)
    return reviewed


def audit_candidate(candidate: str, gold: Mapping[str, str]) -> dict[str, Any]:
    expected_file_name = gold.get("expected_file_name", "")
    file_stem = Path(expected_file_name).stem if expected_file_name else ""
    expected_sheet = gold.get("expected_sheet_name", "")
    expected_range = gold.get("expected_cell_range", "")
    must_not_terms = [term.strip() for term in (gold.get("must_not_contain_terms") or "").split(";") if term.strip()]
    failures = []
    if expected_range and expected_range in candidate:
        failures.append("cell_range_literal")
    if expected_sheet and expected_sheet in candidate:
        failures.append("sheet_name_literal")
    if expected_file_name and expected_file_name in candidate:
        failures.append("file_name_literal")
    if file_stem and file_stem in candidate:
        failures.append("file_stem_literal")
    leaked_hidden_terms = [term for term in must_not_terms if term and term in candidate]
    if leaked_hidden_terms:
        failures.append("must_not_term_literal")
    return {
        "query": candidate,
        "pass": not failures,
        "failures": failures,
        "hidden_term_hits": leaked_hidden_terms,
    }


def build_compare(
    *,
    args: argparse.Namespace,
    before_report: Mapping[str, Any],
    after_report: Mapping[str, Any],
    original_rows: list[dict[str, str]],
    reviewed_rows: list[dict[str, str]],
) -> dict[str, Any]:
    before_by_id = rows_by_query_id(before_report)
    after_by_id = rows_by_query_id(after_report)
    original_by_id = {row.get("query_id", ""): row for row in original_rows}
    reviewed_by_id = {row.get("query_id", ""): row for row in reviewed_rows}
    rows = []
    recovered_count = 0
    regressed_count = 0
    for query_id in QUERY_PATCHES:
        before = before_by_id.get(query_id, {})
        after = after_by_id.get(query_id, {})
        before_match = bool(before.get("location_match"))
        after_match = bool(after.get("location_match"))
        if not before_match and after_match:
            recovered_count += 1
        if before_match and not after_match:
            regressed_count += 1
        rows.append(
            {
                "query_id": query_id,
                "before_query": original_by_id.get(query_id, {}).get("query"),
                "after_query": reviewed_by_id.get(query_id, {}).get("query"),
                "before_hit_rank": before.get("hit_rank"),
                "after_hit_rank": after.get("hit_rank"),
                "before_location_rank": before.get("location_rank"),
                "after_location_rank": after.get("location_rank"),
                "before_location_match": before_match,
                "after_location_match": after_match,
                "before_failure_reason": before.get("failure_reason"),
                "after_failure_reason": after.get("failure_reason"),
                "before_top1": summarize_top_hit(before),
                "after_top1": summarize_top_hit(after),
            }
        )
    before_metrics = before_report.get("metrics") or {}
    after_metrics = after_report.get("metrics") or {}
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_v3_query_surface_before_after_compare",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_before_report": args.before_report,
        "source_after_report": args.reviewed_report,
        "source_original_gold": args.positive_gold,
        "source_reviewed_gold": args.reviewed_gold,
        "reviewed_query_count": len(QUERY_PATCHES),
        "recovered_location_match_count": recovered_count,
        "regressed_location_match_count": regressed_count,
        "metrics": {
            "before": metric_subset(before_metrics),
            "after": metric_subset(after_metrics),
            "delta": metric_delta(before_metrics, after_metrics),
        },
        "rows": rows,
        "guardrails": guardrails_payload(),
    }


def rows_by_query_id(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("query_id") or ""): row
        for row in report.get("query_results") or report.get("per_query") or []
        if isinstance(row, Mapping)
    }


def summarize_top_hit(row: Mapping[str, Any]) -> dict[str, Any] | None:
    hits = row.get("top_k_results") or []
    if not hits:
        return None
    hit = hits[0]
    location = hit.get("location_json") if isinstance(hit.get("location_json"), Mapping) else {}
    return {
        "rank": hit.get("rank"),
        "score": hit.get("score"),
        "source_file_name": hit.get("source_file_name"),
        "sheet_name": location.get("sheet_name"),
        "cell_range": location.get("cell_range"),
        "chunk_type": hit.get("chunk_type"),
        "range_policy_match": (hit.get("match_breakdown") or {}).get("xlsx_range_policy_match"),
    }


def metric_subset(metrics: Mapping[str, Any]) -> dict[str, Any]:
    keys = ["Hit@10", "MRR@10", "xlsx_range_overlap@10", "xlsx_range_contains@10", "xlsx_exact_range@10", "xlsx_citation_location_accuracy", "hidden_content_leakage_count"]
    return {key: metrics.get(key) for key in keys}


def metric_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    delta = {}
    for key, before_value in metric_subset(before).items():
        after_value = metric_subset(after).get(key)
        delta[key] = round(float(after_value) - float(before_value), 4) if is_number(before_value) and is_number(after_value) else None
    return delta


def is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def append_note(existing: str, note: str) -> str:
    parts = [part.strip() for part in existing.split(";") if part.strip()]
    if note not in parts:
        parts.append(note)
    seen = set()
    unique_parts = []
    for part in parts:
        if part in seen:
            continue
        seen.add(part)
        unique_parts.append(part)
    return "; ".join(unique_parts)


def guardrails_payload() -> dict[str, Any]:
    return {
        "promotion_evidence_true_set": False,
        "candidate_v1_mutated": False,
        "candidate_namespace_created": False,
        "immutable_baseline_changed": False,
        "rag_data_canary_changed": False,
        "hidden_negative_in_positive_metrics": False,
    }


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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
    parser.add_argument("--reviewed-gold", default=str(DEFAULT_REVIEWED_GOLD))
    parser.add_argument("--a1-review", default=str(DEFAULT_A1_REVIEW))
    parser.add_argument("--before-report", default=str(DEFAULT_BEFORE_REPORT))
    parser.add_argument("--reviewed-report", default=str(DEFAULT_REVIEWED_REPORT))
    parser.add_argument("--patch-plan", default=str(DEFAULT_PATCH_PLAN))
    parser.add_argument("--compare-output", default=str(DEFAULT_COMPARE_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
