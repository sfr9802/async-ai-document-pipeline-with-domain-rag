"""Break down full72 vector diagnostic retrieval quality by query and location."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_RETRIEVAL_REPORT = Path("reports/rag_retrieval_eval_full72_vector_diagnostic_report.json")
DEFAULT_GOLD = Path("eval/gold_queries_v0.csv")
DEFAULT_CANDIDATE_SCOPE_READINESS = Path("reports/rag_candidate_scope_path_readiness.json")
DEFAULT_GLOBAL_PATH_HYGIENE = Path("reports/rag_path_separation_readiness.json")
DEFAULT_OUTPUT = Path("reports/rag_retrieval_full72_vector_quality_breakdown.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    retrieval = read_json(Path(args.retrieval_report))
    gold_rows = read_gold_rows(Path(args.gold))
    candidate_scope = read_optional_json(Path(args.candidate_scope_readiness))
    global_hygiene = read_optional_json(Path(args.global_path_hygiene))
    payload = build_breakdown(
        retrieval=retrieval,
        gold_rows=gold_rows,
        candidate_scope=candidate_scope,
        global_hygiene=global_hygiene,
        retrieval_report_path=Path(args.retrieval_report),
        gold_path=Path(args.gold),
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0


def build_breakdown(
    *,
    retrieval: Mapping[str, Any],
    gold_rows: list[dict[str, str]],
    candidate_scope: Mapping[str, Any],
    global_hygiene: Mapping[str, Any],
    retrieval_report_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    gold_by_id = {row.get("query_id", ""): row for row in gold_rows}
    query_results = list(retrieval.get("query_results") or [])
    classified_rows: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    suspect_group_counts: Counter[str] = Counter()
    by_bucket: dict[str, Counter[str]] = defaultdict(Counter)
    by_bucket_group: dict[str, Counter[str]] = defaultdict(Counter)
    pdf_policy_counts: Counter[str] = Counter()
    xlsx_policy_counts: Counter[str] = Counter()

    for row in query_results:
        gold = gold_by_id.get(str(row.get("query_id") or ""), {})
        classified = classify_query(row, gold)
        classified_rows.append(classified)
        category_counts[classified["failure_category"]] += 1
        suspect_group_counts[classified["suspect_group"]] += 1
        bucket = str(row.get("bucket") or "unknown")
        by_bucket[bucket][classified["failure_category"]] += 1
        by_bucket_group[bucket][classified["suspect_group"]] += 1
        if bucket.startswith("pdf"):
            for flag in classified.get("diagnostic_flags", []):
                pdf_policy_counts[flag] += 1
        if bucket.startswith("xlsx") or bucket == "mixed_text_table":
            for flag in classified.get("diagnostic_flags", []):
                xlsx_policy_counts[flag] += 1

    bucket_metrics = dict(retrieval.get("bucket_metrics") or {})
    bucket_breakdown = {}
    for bucket, counts in sorted(by_bucket.items()):
        bucket_breakdown[bucket] = {
            "query_count": sum(counts.values()),
            "metrics": bucket_metrics.get(bucket, {}),
            "failure_category_counts": dict(counts),
            "suspect_group_counts": dict(by_bucket_group[bucket]),
        }

    return {
        "run_id": utc_run_id(),
        "status": "COMPLETED",
        "report_role": "retrieval_quality_diagnostic_only",
        "promotion_evidence": False,
        "source_retrieval_report": str(retrieval_report_path),
        "gold": str(gold_path),
        "retrieval_backend": retrieval.get("retrieval_backend"),
        "backend_identity": retrieval.get("backend_identity") or {},
        "evidence_role": retrieval.get("evidence_role"),
        "top_k": retrieval.get("top_k"),
        "query_count": len(query_results),
        "metrics": retrieval.get("metrics") or {},
        "bucket_metrics": bucket_metrics,
        "failure_category_counts": dict(category_counts),
        "suspect_group_counts": dict(suspect_group_counts),
        "bucket_breakdown": bucket_breakdown,
        "pdf_page_bbox_failure_breakdown": {
            "query_count": sum(1 for row in classified_rows if str(row.get("bucket") or "").startswith("pdf")),
            "category_counts": {
                key: value for key, value in category_counts.items() if key.startswith("pdf_")
            },
            "diagnostic_flag_counts": dict(pdf_policy_counts),
            "interpretation": (
                "PDF failures split into ranking/file misses versus matching-policy issues. "
                "Rows with correct page_no hits but missing physical_page_index or bbox are not pure retrieval misses."
            ),
        },
        "xlsx_sheet_range_failure_breakdown": {
            "query_count": sum(
                1
                for row in classified_rows
                if str(row.get("bucket") or "").startswith("xlsx") or row.get("bucket") == "mixed_text_table"
            ),
            "category_counts": {
                key: value
                for key, value in category_counts.items()
                if key.startswith("xlsx_") or key.startswith("mixed_")
            },
            "diagnostic_flag_counts": dict(xlsx_policy_counts),
        },
        "gold_label_suspect_rows": compact_rows(classified_rows, "gold_binding_or_label_suspect"),
        "retrieval_text_ranking_suspect_rows": compact_rows(classified_rows, "retrieval_text_or_ranking_suspect"),
        "chunk_granularity_suspect_rows": compact_rows(classified_rows, "chunk_granularity_suspect"),
        "policy_matching_rule_suspect_rows": compact_rows(classified_rows, "policy_or_matching_rule_suspect"),
        "classified_query_rows": classified_rows,
        "readiness_separation": {
            "candidate_scope_readiness_report": str(DEFAULT_CANDIDATE_SCOPE_READINESS),
            "candidate_scope_status": candidate_scope.get("status"),
            "global_path_hygiene_report": str(DEFAULT_GLOBAL_PATH_HYGIENE),
            "global_path_hygiene_status": global_hygiene.get("status"),
            "decision": (
                "Candidate promotion-scope readiness and global path hygiene are reported separately. "
                "Global legacy drift is not counted as a full72 candidate-scope blocker here."
            ),
        },
        "notes": [
            "This report analyzes vector-only full72 diagnostic retrieval quality.",
            "It does not introduce hybrid search, reranking, parser changes, or promotion evidence.",
        ],
    }


def classify_query(row: Mapping[str, Any], gold: Mapping[str, str]) -> dict[str, Any]:
    bucket = str(row.get("bucket") or "")
    top_hits = list(row.get("top_k_results") or [])
    expected_type = gold.get("expected_location_type") or ("pdf" if bucket.startswith("pdf") else "xlsx")
    expected_page_no = to_int(gold.get("expected_page_no") or row.get("expected_page_no"))
    expected_physical = to_int(gold.get("expected_physical_page_index") or row.get("expected_physical_page_index"))
    expected_bbox = bool(gold.get("expected_bbox") or row.get("expected_bbox"))
    expected_table = bool(gold.get("expected_table_id") or row.get("expected_table_id"))
    expected_sheet = gold.get("expected_sheet_name") or row.get("expected_sheet_name")
    expected_range = gold.get("expected_cell_range") or row.get("expected_cell_range")

    file_hits = [hit for hit in top_hits if breakdown(hit).get("file_match")]
    docv_hits = [hit for hit in file_hits if breakdown(hit).get("document_version_match")]
    sheet_hits = [hit for hit in docv_hits if breakdown(hit).get("xlsx_sheet_match")]
    range_hits = [hit for hit in sheet_hits if breakdown(hit).get("xlsx_range_policy_match")]
    page_no_hits = [hit for hit in docv_hits if expected_page_no is not None and location(hit).get("page_no") == expected_page_no]
    page_policy_hits = [hit for hit in page_no_hits if not breakdown(hit).get("pdf_page_match")]
    bbox_missing_hits = [hit for hit in page_no_hits if expected_bbox and not location(hit).get("bbox")]

    flags: list[str] = []
    if row.get("location_match") is True:
        category = "ok"
        group = "matched"
    elif expected_type in {"pdf", "ocr"}:
        if not file_hits:
            category = "pdf_expected_file_absent_in_top10"
            group = "retrieval_text_or_ranking_suspect"
        elif not docv_hits:
            category = "pdf_gold_docv_or_duplicate_file_binding_mismatch"
            group = "gold_binding_or_label_suspect"
        elif page_policy_hits:
            category = "pdf_page_policy_missing_physical_or_label"
            group = "policy_or_matching_rule_suspect"
            if expected_physical is not None and any(location(hit).get("physical_page_index") is None for hit in page_policy_hits):
                flags.append("correct_page_no_hit_but_missing_physical_page_index")
            if expected_bbox and bbox_missing_hits:
                flags.append("correct_page_no_hit_but_missing_bbox")
        elif expected_page_no is not None and not page_no_hits:
            category = "pdf_expected_page_absent_in_top10"
            group = "retrieval_text_or_ranking_suspect"
        elif expected_bbox and not any(breakdown(hit).get("pdf_bbox_overlap") for hit in page_no_hits):
            category = "pdf_bbox_policy_or_chunk_granularity_mismatch"
            group = "policy_or_matching_rule_suspect"
            flags.append("page_hit_without_bbox_overlap")
        else:
            category = "pdf_other_location_mismatch"
            group = "gold_binding_or_label_suspect"
    else:
        if not file_hits:
            category = "xlsx_expected_file_absent_in_top10"
            group = "retrieval_text_or_ranking_suspect"
        elif not docv_hits:
            category = "xlsx_gold_docv_or_duplicate_file_binding_mismatch"
            group = "gold_binding_or_label_suspect"
        elif expected_table and range_hits and not any(breakdown(hit).get("xlsx_table_match") for hit in range_hits):
            category = "xlsx_table_metadata_or_gold_binding_mismatch"
            group = "gold_binding_or_label_suspect"
            flags.append("expected_table_id_not_present_on_range_hit")
        elif expected_sheet and sheet_hits and expected_range and not range_hits:
            category = "xlsx_range_ranking_or_chunk_granularity_mismatch"
            group = "chunk_granularity_suspect"
            flags.append("expected_sheet_hit_but_expected_range_absent")
        elif expected_sheet and not sheet_hits:
            category = "xlsx_sheet_ranking_mismatch"
            group = "retrieval_text_or_ranking_suspect"
        else:
            category = "xlsx_other_location_mismatch"
            group = "gold_binding_or_label_suspect"

    return {
        "query_id": row.get("query_id"),
        "bucket": bucket,
        "query": row.get("query"),
        "label_status": row.get("label_status") or gold.get("label_status"),
        "hit_rank": row.get("hit_rank"),
        "location_rank": row.get("location_rank"),
        "failure_reason": row.get("failure_reason"),
        "failure_category": category,
        "suspect_group": group,
        "diagnostic_flags": flags,
        "expected": {
            "file_name": row.get("expected_file_name") or gold.get("expected_file_name"),
            "document_version_id": gold.get("expected_document_version_id"),
            "chunk_type": gold.get("expected_chunk_type"),
            "location_type": expected_type,
            "sheet_name": expected_sheet,
            "cell_range": expected_range,
            "table_id": gold.get("expected_table_id") or row.get("expected_table_id"),
            "physical_page_index": gold.get("expected_physical_page_index") or row.get("expected_physical_page_index"),
            "page_no": gold.get("expected_page_no") or row.get("expected_page_no"),
            "page_label": gold.get("expected_page_label") or row.get("expected_page_label"),
            "bbox": gold.get("expected_bbox") or row.get("expected_bbox"),
        },
        "top_hits": summarize_hits(top_hits[:5]),
    }


def summarize_hits(hits: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for hit in hits:
        loc = location(hit)
        br = breakdown(hit)
        result.append(
            {
                "rank": hit.get("rank"),
                "source_file_name": hit.get("source_file_name"),
                "chunk_type": hit.get("chunk_type"),
                "citation_text": hit.get("citation_text"),
                "page_no": loc.get("page_no"),
                "physical_page_index": loc.get("physical_page_index"),
                "bbox_present": bool(loc.get("bbox")),
                "sheet_name": loc.get("sheet_name"),
                "cell_range": loc.get("cell_range"),
                "file_match": br.get("file_match"),
                "document_version_match": br.get("document_version_match"),
                "location_match": br.get("location_match"),
                "pdf_page_match": br.get("pdf_page_match"),
                "pdf_bbox_overlap": br.get("pdf_bbox_overlap"),
                "xlsx_sheet_match": br.get("xlsx_sheet_match"),
                "xlsx_range_policy_match": br.get("xlsx_range_policy_match"),
                "xlsx_table_match": br.get("xlsx_table_match"),
            }
        )
    return result


def compact_rows(classified_rows: list[dict[str, Any]], group: str) -> list[dict[str, Any]]:
    rows = [row for row in classified_rows if row.get("suspect_group") == group]
    return [
        {
            "query_id": row.get("query_id"),
            "bucket": row.get("bucket"),
            "failure_reason": row.get("failure_reason"),
            "failure_category": row.get("failure_category"),
            "diagnostic_flags": row.get("diagnostic_flags"),
            "hit_rank": row.get("hit_rank"),
            "location_rank": row.get("location_rank"),
            "expected": row.get("expected"),
            "top_hits": row.get("top_hits"),
        }
        for row in rows
    ]


def breakdown(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("match_breakdown")
    return value if isinstance(value, Mapping) else {}


def location(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("location_json")
    return value if isinstance(value, Mapping) else {}


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be an object: {path}")
    return payload


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_gold_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


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
    parser.add_argument("--retrieval-report", default=str(DEFAULT_RETRIEVAL_REPORT))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--candidate-scope-readiness", default=str(DEFAULT_CANDIDATE_SCOPE_READINESS))
    parser.add_argument("--global-path-hygiene", default=str(DEFAULT_GLOBAL_PATH_HYGIENE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
