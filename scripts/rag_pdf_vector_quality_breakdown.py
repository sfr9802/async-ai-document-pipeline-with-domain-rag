"""Classify Track C PDF-only vector diagnostic failures.

This C6 report is read-only. It consumes the C5 PDF-only vector diagnostic
report and gold labels, then separates metadata projection gaps, retrieval
ranking misses, gold/policy candidates, and chunk granularity issues. It does
not run retrieval, indexing, promotion, baseline updates, cleanup, or reset.
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


DEFAULT_EVAL_REPORT = Path("reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_GOLD = Path("eval/gold_queries_v0.csv")
DEFAULT_C2_REPORT = Path("reports/pdf_vector_metadata_projection_readiness.json")
DEFAULT_OUTPUT = Path("reports/rag_pdf_vector_quality_breakdown.json")

MATCHED = "MATCHED"
UNKNOWN = "UNKNOWN"
FAILURE_TYPES = {
    MATCHED,
    "PDF_METADATA_PROJECTION_MISSING_PHYSICAL_PAGE",
    "PDF_METADATA_PROJECTION_MISSING_BBOX",
    "PDF_EXPECTED_FILE_ABSENT_IN_TOP10",
    "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10",
    "PDF_BBOX_POLICY_MISMATCH",
    "PDF_TABLE_GOLD_BINDING_MISMATCH",
    "PDF_CHUNK_GRANULARITY_ISSUE",
    "PDF_OCR_TRUST_CONTRACT_MISMATCH",
    "PDF_TRUE_RETRIEVAL_RANKING_FAILURE",
    UNKNOWN,
}

METADATA_FAILURE_TYPES = {
    "PDF_METADATA_PROJECTION_MISSING_PHYSICAL_PAGE",
    "PDF_METADATA_PROJECTION_MISSING_BBOX",
    "PDF_OCR_TRUST_CONTRACT_MISMATCH",
}
GOLD_POLICY_TYPES = {
    "PDF_BBOX_POLICY_MISMATCH",
    "PDF_TABLE_GOLD_BINDING_MISMATCH",
}
CHUNK_GRANULARITY_TYPES = {"PDF_CHUNK_GRANULARITY_ISSUE"}
TRUE_RANKING_TYPES = {
    "PDF_EXPECTED_FILE_ABSENT_IN_TOP10",
    "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10",
    "PDF_TRUE_RETRIEVAL_RANKING_FAILURE",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    eval_path = Path(args.eval_report)
    gold_path = Path(args.gold)
    c2_path = Path(args.c2_report)
    report = read_json(eval_path)
    gold_rows = read_csv_rows(gold_path)
    c2_report = read_optional_json(c2_path)
    payload = build_breakdown(
        eval_report=report,
        gold_rows=gold_rows,
        c2_report=c2_report,
        eval_report_path=eval_path,
        gold_path=gold_path,
        c2_report_path=c2_path,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload.get("status") == "PASS" else 2


def build_breakdown(
    *,
    eval_report: Mapping[str, Any],
    gold_rows: list[dict[str, str]],
    c2_report: Mapping[str, Any],
    eval_report_path: Path,
    gold_path: Path,
    c2_report_path: Path = DEFAULT_C2_REPORT,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    validate_eval_report(eval_report, blockers)

    gold_by_id = {row.get("query_id", ""): row for row in gold_rows}
    query_rows = list(eval_report.get("query_results") or eval_report.get("per_query") or [])
    classified_rows = [
        classify_query(row, gold_by_id.get(str(row.get("query_id") or ""), {}))
        for row in query_rows
    ]
    for row in classified_rows:
        if not row.get("next_action"):
            blockers.append(f"query {row.get('query_id')} missing next_action")

    type_counts = Counter(str(row.get("failure_type") or UNKNOWN) for row in classified_rows)
    bucket_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in classified_rows:
        bucket_counts[str(row.get("bucket") or "unknown")][str(row.get("failure_type") or UNKNOWN)] += 1

    unknown_count = type_counts.get(UNKNOWN, 0)
    if unknown_count:
        blockers.append("UNKNOWN failure count must be 0")

    failure_rows = [row for row in classified_rows if row.get("failure_type") != MATCHED]
    metadata_rows = rows_with_types(classified_rows, METADATA_FAILURE_TYPES)
    gold_policy_rows = rows_with_types(classified_rows, GOLD_POLICY_TYPES)
    chunk_rows = rows_with_types(classified_rows, CHUNK_GRANULARITY_TYPES)
    true_ranking_rows = rows_with_types(classified_rows, TRUE_RANKING_TYPES)

    status = "PASS" if not blockers else "FAIL"
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C6",
        "report_role": "pdf_vector_quality_breakdown",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "baseline_execution": "not_run_by_this_script",
        "source_eval_report": str(eval_report_path),
        "gold": str(gold_path),
        "c2_report": report_ref(c2_report, c2_report_path),
        "input_artifacts": [
            artifact_identity(eval_report_path),
            artifact_identity(gold_path),
            artifact_identity(c2_report_path),
        ],
        "retrieval_backend": eval_report.get("retrieval_backend"),
        "index_version": eval_report.get("index_version"),
        "artifact_dir": eval_report.get("artifact_dir"),
        "query_count": len(classified_rows),
        "failed_query_count": len(failure_rows),
        "matched_query_count": type_counts.get(MATCHED, 0),
        "unknown_failure_count": unknown_count,
        "metadata_projection_failure_count": len(metadata_rows),
        "gold_policy_candidate_count": len(gold_policy_rows),
        "chunk_granularity_candidate_count": len(chunk_rows),
        "true_retrieval_ranking_failure_count": len(true_ranking_rows),
        "failure_type_counts": dict(sorted(type_counts.items())),
        "failure_reason_counts": dict(sorted(Counter(
            str(row.get("c5_failure_reason") or "matched") for row in classified_rows
        ).items())),
        "bucket_breakdown": {
            bucket: {
                "query_count": sum(counts.values()),
                "failure_type_counts": dict(sorted(counts.items())),
            }
            for bucket, counts in sorted(bucket_counts.items())
        },
        "metadata_projection_rows": compact_rows(metadata_rows),
        "gold_policy_candidate_rows": compact_rows(gold_policy_rows),
        "chunk_granularity_candidate_rows": compact_rows(chunk_rows),
        "true_retrieval_ranking_failure_rows": compact_rows(true_ranking_rows),
        "classified_query_rows": classified_rows,
        "completion_criteria": {
            "unknown_failure_count_zero": unknown_count == 0,
            "metadata_vs_ranking_separated": True,
            "gold_policy_candidate_count_recorded": True,
            "chunk_granularity_candidate_count_recorded": True,
            "all_queries_have_next_action": all(bool(row.get("next_action")) for row in classified_rows),
        },
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "next_action": (
            "Proceed to C7 gold policy review for gold/policy and chunk candidates before retrieval tuning."
            if status == "PASS"
            else "Resolve C6 classification blockers before C7."
        ),
        "notes": [
            "C6 reclassifies C5 diagnostic failures; it does not rerun retrieval.",
            "Only PDF bound positive rows from the C5 report are classified here.",
            "Rows classified as true retrieval ranking failures should not trigger tuning until C7 resolves gold/policy candidates.",
        ],
    }


def validate_eval_report(eval_report: Mapping[str, Any], blockers: list[str]) -> None:
    if eval_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C5 eval report must be PASS or PASS_WITH_WARNINGS; got {eval_report.get('status')}")
    if eval_report.get("promotion_evidence") is not False:
        blockers.append("C5 eval report must keep promotion_evidence=false")
    if eval_report.get("evidence_role") != "diagnostic":
        blockers.append("C5 eval report must keep evidence_role=diagnostic")
    if eval_report.get("retrieval_backend") != "vector":
        blockers.append("C5 eval report must use retrieval_backend=vector")
    gate_counters = eval_report.get("gate_counters") or {}
    for key, value in gate_counters.items():
        if int(value or 0) != 0:
            blockers.append(f"C5 gate counter {key} must be 0")


def classify_query(row: Mapping[str, Any], gold: Mapping[str, str]) -> dict[str, Any]:
    query_id = str(row.get("query_id") or gold.get("query_id") or "")
    bucket = str(row.get("bucket") or gold.get("bucket") or "unknown")
    failure_reason = clean(row.get("failure_reason"))
    top_hits = list(row.get("top_k_results") or [])
    expected = expected_fields(row, gold)
    file_hits = [hit for hit in top_hits if match(hit, "file_match")]
    doc_hits = [hit for hit in top_hits if match(hit, "document_version_match")]
    page_hits = [hit for hit in top_hits if match(hit, "pdf_page_match")]
    location_hits = [hit for hit in top_hits if match(hit, "location_match")]
    bbox_hits = [hit for hit in top_hits if match(hit, "pdf_bbox_overlap")]
    expected_page_hits = [
        hit for hit in file_hits
        if expected["page_no"] is not None and location(hit).get("page_no") == expected["page_no"]
    ]
    expected_doc_page_hits = [
        hit for hit in doc_hits
        if expected["page_no"] is not None and location(hit).get("page_no") == expected["page_no"]
    ]
    expected_doc_location_hits = [
        hit for hit in doc_hits
        if match(hit, "location_match")
    ]

    failure_type = UNKNOWN
    evidence: dict[str, Any] = {}
    next_action = ""
    c7_candidate = False

    if not failure_reason and row.get("location_match") is True:
        failure_type = MATCHED
        next_action = "No C6 action required; keep as matched diagnostic evidence."
        evidence = {"matched_rank": row.get("location_rank") or row.get("hit_rank")}
    elif has_ocr_trust_gap(expected_doc_page_hits):
        failure_type = "PDF_OCR_TRUST_CONTRACT_MISMATCH"
        next_action = "Review OCR trust/confidence contract before retrieval tuning."
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)
    elif expected_doc_page_hits and any(location(hit).get("physical_page_index") is None for hit in expected_doc_page_hits):
        failure_type = "PDF_METADATA_PROJECTION_MISSING_PHYSICAL_PAGE"
        next_action = "Repair metadata projection for physical_page_index, then rerun diagnostic."
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)
    elif (
        expected_doc_page_hits
        and expected["bbox"]
        and any(
            not location(hit).get("bbox")
            and clean(hit.get("chunk_type")).lower() == expected["chunk_type"].lower()
            for hit in expected_doc_page_hits
        )
    ):
        failure_type = "PDF_METADATA_PROJECTION_MISSING_BBOX"
        next_action = "Repair bbox projection for page hits, then rerun diagnostic."
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)
    elif failure_reason == "expected_file_not_found" or not file_hits:
        failure_type = "PDF_EXPECTED_FILE_ABSENT_IN_TOP10"
        next_action = "Treat as retrieval ranking/file recall failure unless C7 finds a gold binding error."
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)
    elif bucket == "pdf_table_lookup" and failure_reason:
        failure_type = "PDF_TABLE_GOLD_BINDING_MISMATCH"
        next_action = "Send to C7 table/page gold policy review before retrieval tuning."
        c7_candidate = True
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)
    elif failure_reason == "bbox_mismatch":
        failure_type = "PDF_BBOX_POLICY_MISMATCH"
        next_action = "Send to C7 bbox overlap/exact policy review before retrieval tuning."
        c7_candidate = True
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)
    elif expected_doc_location_hits and not exact_chunk_type_match(expected_doc_location_hits, expected["chunk_type"]):
        failure_type = "PDF_CHUNK_GRANULARITY_ISSUE"
        next_action = "Review expected chunk type versus available page/paragraph hit in C7 or a chunk policy step."
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)
    elif failure_reason == "expected_page_not_found":
        failure_type = "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10"
        next_action = "Treat as true page-ranking failure after C7 clears gold/page policy."
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)
    elif failure_reason:
        failure_type = "PDF_TRUE_RETRIEVAL_RANKING_FAILURE"
        next_action = "Treat as true ranking failure after C7 clears gold/policy candidates."
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)
    else:
        next_action = "Inspect manually; classifier could not assign a known C6 failure type."
        evidence = evidence_counts(top_hits, file_hits, doc_hits, page_hits, location_hits, bbox_hits)

    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": row.get("query") or gold.get("query"),
        "label_status": row.get("label_status") or gold.get("label_status"),
        "c5_failure_reason": failure_reason or None,
        "failure_type": failure_type,
        "hit_rank": row.get("hit_rank"),
        "location_rank": row.get("location_rank"),
        "hit_at_10": bool(row.get("hit_at_10")),
        "location_match": bool(row.get("location_match")),
        "c7_candidate": c7_candidate,
        "expected": expected,
        "evidence": evidence,
        "top_hit_summary": summarize_hits(top_hits[:5]),
        "supporting_hit_summary": summarize_hits(supporting_hits_for_type(failure_type, top_hits, file_hits, doc_hits, expected_doc_page_hits, expected_doc_location_hits)),
        "next_action": next_action,
    }


def expected_fields(row: Mapping[str, Any], gold: Mapping[str, str]) -> dict[str, Any]:
    return {
        "file_name": clean(row.get("expected_file_name")) or clean(gold.get("expected_file_name")),
        "document_version_id": clean(row.get("expected_document_version_id")) or clean(gold.get("expected_document_version_id")),
        "chunk_type": clean(row.get("expected_chunk_type")) or clean(gold.get("expected_chunk_type")),
        "location_type": clean(row.get("expected_location_type")) or clean(gold.get("expected_location_type")) or "pdf",
        "page_no": to_int(row.get("expected_page_no") or gold.get("expected_page_no")),
        "physical_page_index": to_int(row.get("expected_physical_page_index") or gold.get("expected_physical_page_index")),
        "page_label": clean(row.get("expected_page_label")) or clean(gold.get("expected_page_label")),
        "bbox": clean(row.get("expected_bbox")) or clean(gold.get("expected_bbox")),
        "must_contain_terms": clean(gold.get("must_contain_terms")),
        "notes": clean(gold.get("notes")),
    }


def evidence_counts(
    top_hits: list[Mapping[str, Any]],
    file_hits: list[Mapping[str, Any]],
    doc_hits: list[Mapping[str, Any]],
    page_hits: list[Mapping[str, Any]],
    location_hits: list[Mapping[str, Any]],
    bbox_hits: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "top_k_count": len(top_hits),
        "expected_file_hit_count": len(file_hits),
        "expected_document_version_hit_count": len(doc_hits),
        "expected_page_hit_count": len(page_hits),
        "location_match_hit_count": len(location_hits),
        "bbox_overlap_hit_count": len(bbox_hits),
        "best_file_hit_rank": min((int(hit.get("rank") or 999999) for hit in file_hits), default=None),
        "best_docv_hit_rank": min((int(hit.get("rank") or 999999) for hit in doc_hits), default=None),
        "best_page_hit_rank": min((int(hit.get("rank") or 999999) for hit in page_hits), default=None),
        "best_location_hit_rank": min((int(hit.get("rank") or 999999) for hit in location_hits), default=None),
    }


def supporting_hits_for_type(
    failure_type: str,
    top_hits: list[Mapping[str, Any]],
    file_hits: list[Mapping[str, Any]],
    doc_hits: list[Mapping[str, Any]],
    expected_doc_page_hits: list[Mapping[str, Any]],
    expected_doc_location_hits: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if failure_type == "PDF_EXPECTED_FILE_ABSENT_IN_TOP10":
        return top_hits[:5]
    if failure_type in {"PDF_EXPECTED_PAGE_ABSENT_IN_TOP10", "PDF_TABLE_GOLD_BINDING_MISMATCH"}:
        return (doc_hits or file_hits or top_hits)[:5]
    if failure_type in {
        "PDF_BBOX_POLICY_MISMATCH",
        "PDF_METADATA_PROJECTION_MISSING_PHYSICAL_PAGE",
        "PDF_METADATA_PROJECTION_MISSING_BBOX",
    }:
        return (expected_doc_page_hits or doc_hits or file_hits)[:5]
    if failure_type == "PDF_CHUNK_GRANULARITY_ISSUE":
        return (expected_doc_location_hits or doc_hits or file_hits)[:5]
    return (doc_hits or file_hits or top_hits)[:5]


def exact_chunk_type_match(hits: list[Mapping[str, Any]], expected_chunk_type: str) -> bool:
    if not expected_chunk_type:
        return True
    return any(clean(hit.get("chunk_type")).lower() == expected_chunk_type.lower() for hit in hits)


def has_ocr_trust_gap(hits: list[Mapping[str, Any]]) -> bool:
    for hit in hits:
        loc = location(hit)
        if loc.get("ocr_used") is True and loc.get("ocr_confidence") in (None, ""):
            return True
    return False


def rows_with_types(rows: list[dict[str, Any]], types: set[str]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("failure_type") in types]


def compact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "query_id": row.get("query_id"),
            "bucket": row.get("bucket"),
            "c5_failure_reason": row.get("c5_failure_reason"),
            "failure_type": row.get("failure_type"),
            "hit_rank": row.get("hit_rank"),
            "location_rank": row.get("location_rank"),
            "evidence": row.get("evidence"),
            "expected": row.get("expected"),
            "supporting_hit_summary": row.get("supporting_hit_summary"),
            "next_action": row.get("next_action"),
        }
        for row in rows
    ]


def summarize_hits(hits: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for hit in hits:
        loc = location(hit)
        br = breakdown(hit)
        result.append({
            "rank": hit.get("rank"),
            "source_file_name": hit.get("source_file_name"),
            "search_unit_id": hit.get("search_unit_id"),
            "chunk_type": hit.get("chunk_type"),
            "page_no": loc.get("page_no"),
            "physical_page_index": loc.get("physical_page_index"),
            "page_label": loc.get("page_label"),
            "bbox_present": bool(loc.get("bbox")),
            "ocr_used": loc.get("ocr_used"),
            "ocr_confidence": loc.get("ocr_confidence"),
            "file_match": br.get("file_match"),
            "document_version_match": br.get("document_version_match"),
            "chunk_type_match": br.get("chunk_type_match"),
            "pdf_page_match": br.get("pdf_page_match"),
            "pdf_bbox_overlap": br.get("pdf_bbox_overlap"),
            "location_match": br.get("location_match"),
        })
    return result


def match(hit: Mapping[str, Any], key: str) -> bool:
    return bool(breakdown(hit).get(key))


def breakdown(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("match_breakdown")
    return value if isinstance(value, Mapping) else {}


def location(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("location_json")
    return value if isinstance(value, Mapping) else {}


def report_ref(report: Mapping[str, Any], path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() else None,
        "status": report.get("status"),
        "promotion_evidence": report.get("promotion_evidence"),
        "evidence_role": report.get("evidence_role"),
    }


def artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() else None,
    }


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-report", default=str(DEFAULT_EVAL_REPORT))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--c2-report", default=str(DEFAULT_C2_REPORT))
    parser.add_argument("--output", "--report", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
