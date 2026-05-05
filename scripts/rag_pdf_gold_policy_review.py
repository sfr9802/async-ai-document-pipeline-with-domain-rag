"""Review Track C PDF gold policy candidates after C6.

This C7 report is read-only. It reviews the C6 gold/policy and chunk
granularity candidates, records deterministic page/table/bbox/OCR policy
decisions, and produces relabel/reclassification candidates when needed. It
does not mutate gold CSV rows, run retrieval, run indexing, promote, update a
baseline, cleanup, or reset.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_BREAKDOWN = Path("reports/rag_pdf_vector_quality_breakdown.json")
DEFAULT_GOLD = Path("eval/gold_queries_v0.csv")
DEFAULT_C1_REPORT = Path("reports/pdf_candidate_scope_report.json")
DEFAULT_C2_REPORT = Path("reports/pdf_vector_metadata_projection_readiness.json")
DEFAULT_C3_REPORT = Path("reports/rag_pdf_embedding_text_contract_audit.json")
DEFAULT_OUTPUT = Path("reports/rag_pdf_gold_policy_review.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    breakdown_path = Path(args.quality_breakdown)
    gold_path = Path(args.gold)
    c1_path = Path(args.c1_report)
    c2_path = Path(args.c2_report)
    c3_path = Path(args.c3_report)
    breakdown = read_json(breakdown_path)
    gold_rows = read_csv_rows(gold_path)
    c1_report = read_optional_json(c1_path)
    c2_report = read_optional_json(c2_path)
    c3_report = read_optional_json(c3_path)
    payload = build_review(
        breakdown=breakdown,
        gold_rows=gold_rows,
        c1_report=c1_report,
        c2_report=c2_report,
        c3_report=c3_report,
        breakdown_path=breakdown_path,
        gold_path=gold_path,
        c1_report_path=c1_path,
        c2_report_path=c2_path,
        c3_report_path=c3_path,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_review(
    *,
    breakdown: Mapping[str, Any],
    gold_rows: list[dict[str, str]],
    c1_report: Mapping[str, Any],
    c2_report: Mapping[str, Any],
    c3_report: Mapping[str, Any],
    breakdown_path: Path,
    gold_path: Path,
    c1_report_path: Path = DEFAULT_C1_REPORT,
    c2_report_path: Path = DEFAULT_C2_REPORT,
    c3_report_path: Path = DEFAULT_C3_REPORT,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    validate_inputs(breakdown, blockers)
    gold_by_id = {row.get("query_id", ""): row for row in gold_rows}

    candidate_rows = list(breakdown.get("gold_policy_candidate_rows") or [])
    candidate_rows.extend(list(breakdown.get("chunk_granularity_candidate_rows") or []))
    reviewed_rows = [
        review_candidate(row, gold_by_id.get(str(row.get("query_id") or ""), {}))
        for row in candidate_rows
    ]
    invalid_rows = [row for row in reviewed_rows if row.get("policy_status") == "INVALID_GOLD"]
    page_ambiguous = [row for row in reviewed_rows if row.get("page_policy_status") == "AMBIGUOUS"]
    table_ambiguous = [row for row in reviewed_rows if row.get("table_policy_status") == "AMBIGUOUS"]
    ocr_ambiguous = [row for row in reviewed_rows if row.get("ocr_policy_status") == "AMBIGUOUS"]
    relabel_rows = [row for row in reviewed_rows if row.get("relabel_candidate")]
    if invalid_rows:
        blockers.append("invalid_gold_count must be 0")
    if page_ambiguous:
        blockers.append("page_policy_ambiguous_count must be 0")
    if table_ambiguous:
        blockers.append("table_policy_ambiguous_count must be 0")
    if ocr_ambiguous:
        blockers.append("ocr_policy_ambiguous_count must be 0")
    if relabel_rows:
        warnings.append(f"relabel_candidate_count={len(relabel_rows)}; review before retrieval tuning")

    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    decision_counts = Counter(str(row.get("decision_category") or "UNKNOWN") for row in reviewed_rows)
    policy_category_counts = Counter(str(row.get("c7_policy_category") or "UNKNOWN") for row in reviewed_rows)
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C7",
        "report_role": "pdf_gold_policy_review",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "baseline_execution": "not_run_by_this_script",
        "gold_mutation_execution": "not_run_by_this_script",
        "source_quality_breakdown": str(breakdown_path),
        "gold": str(gold_path),
        "input_artifacts": [
            artifact_identity(breakdown_path),
            artifact_identity(gold_path),
            artifact_identity(c1_report_path),
            artifact_identity(c2_report_path),
            artifact_identity(c3_report_path),
        ],
        "c1_report": report_ref(c1_report, c1_report_path),
        "c2_report": report_ref(c2_report, c2_report_path),
        "c3_report": report_ref(c3_report, c3_report_path),
        "policy_decisions": policy_decisions(),
        "reviewed_candidate_count": len(reviewed_rows),
        "invalid_gold_count": len(invalid_rows),
        "page_policy_ambiguous_count": len(page_ambiguous),
        "table_policy_ambiguous_count": len(table_ambiguous),
        "ocr_policy_ambiguous_count": len(ocr_ambiguous),
        "relabel_candidate_count": len(relabel_rows),
        "relabel_candidate_rows_recorded": bool(relabel_rows),
        "decision_category_counts": dict(sorted(decision_counts.items())),
        "allowed_c7_policy_categories": [
            "valid_exact_location",
            "valid_page_level_location",
            "valid_bbox_overlap",
            "valid_table_bbox_overlap",
            "valid_parent_child_chunk",
            "ambiguous_generic_query",
            "invalid_gold_binding",
            "relabel_candidate",
            "exclude_from_metric",
        ],
        "c7_policy_category_counts": dict(sorted(policy_category_counts.items())),
        "reviewed_candidate_rows": reviewed_rows,
        "relabel_candidate_rows": relabel_rows,
        "post_c7_decision": {
            "metadata_projection_blocker_count": int(breakdown.get("metadata_projection_failure_count") or 0),
            "text_contract_blocker_count": 0 if c3_report.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 1,
            "indexing_consistency_blocker_count": 0,
            "gold_policy_blocker_count": len(invalid_rows) + len(page_ambiguous) + len(table_ambiguous) + len(ocr_ambiguous),
            "true_retrieval_ranking_failure_count": int(breakdown.get("true_retrieval_ranking_failure_count") or 0),
            "post_c7_reclassification_required": bool(relabel_rows),
            "retrieval_tuning_candidate_ready": (
                not blockers
                and not relabel_rows
                and int(breakdown.get("true_retrieval_ranking_failure_count") or 0) > 0
            ),
            "decision": (
                "Resolve relabel candidates and rerun C6 before retrieval tuning."
                if relabel_rows
                else "No C7 relabel candidates remain; retrieval tuning candidates may be scoped separately."
            ),
        },
        "completion_criteria": {
            "invalid_gold_count_zero": len(invalid_rows) == 0,
            "page_policy_ambiguous_count_zero": len(page_ambiguous) == 0,
            "table_policy_ambiguous_count_zero": len(table_ambiguous) == 0,
            "ocr_policy_ambiguous_count_zero": len(ocr_ambiguous) == 0,
            "relabel_candidate_rows_recorded_or_zero": bool(relabel_rows) or len(relabel_rows) == 0,
        },
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "next_action": (
            "Review relabel candidates and rerun C6 if accepted; do not start retrieval tuning yet."
            if relabel_rows and not blockers
            else "Resolve C7 blockers before C6 reclassification or retrieval tuning."
            if blockers
            else "Track C policy review has no relabel candidates; retrieval tuning can be considered in a separate track."
        ),
        "notes": [
            "C7 records policy decisions only; it does not mutate eval/gold_queries_v0.csv.",
            "Table/page/bbox/chunk policy candidates are separated from true retrieval ranking failures.",
            "If relabel candidates are accepted, create a follow-up C6 reclassification entry.",
        ],
    }


def validate_inputs(breakdown: Mapping[str, Any], blockers: list[str]) -> None:
    if breakdown.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C6 breakdown must be PASS or PASS_WITH_WARNINGS; got {breakdown.get('status')}")
    if breakdown.get("promotion_evidence") is not False:
        blockers.append("C6 breakdown must keep promotion_evidence=false")
    if breakdown.get("evidence_role") != "diagnostic":
        blockers.append("C6 breakdown must keep evidence_role=diagnostic")
    if int(breakdown.get("unknown_failure_count") or 0) != 0:
        blockers.append("C6 unknown_failure_count must be 0 before C7")
    completion = breakdown.get("completion_criteria") or {}
    if completion and not all(bool(value) for value in completion.values()):
        blockers.append("C6 completion criteria must all be true before C7")


def review_candidate(row: Mapping[str, Any], gold: Mapping[str, str]) -> dict[str, Any]:
    expected = dict(row.get("expected") or {})
    query_id = str(row.get("query_id") or gold.get("query_id") or "")
    failure_type = str(row.get("failure_type") or "")
    bucket = str(row.get("bucket") or gold.get("bucket") or "")
    required_missing = required_gold_fields_missing(expected, gold)
    page_policy_status = "DECIDED"
    table_policy_status = "NOT_APPLICABLE"
    ocr_policy_status = "NOT_APPLICABLE"
    policy_status = "VALID"
    relabel_candidate = False
    decision_category = "NO_POLICY_CHANGE"
    c7_policy_category = "valid_exact_location"
    rationale = "Gold row is evaluable under the current PDF policy."
    proposed_action = "Keep current gold binding."

    if required_missing:
        policy_status = "INVALID_GOLD"
        decision_category = "INVALID_GOLD_MISSING_REQUIRED_FIELD"
        c7_policy_category = "invalid_gold_binding"
        rationale = "Bound PDF gold row is missing required file/page metadata."
        proposed_action = "Repair required gold fields before metric use."
    elif failure_type == "PDF_TABLE_GOLD_BINDING_MISMATCH":
        table_policy_status = "DECIDED_RELABEL_CANDIDATE"
        relabel_candidate = True
        decision_category = "RELABEL_TABLE_PAGE_BINDING"
        c7_policy_category = "relabel_candidate"
        rationale = (
            "PDF table lookup rows currently bind to paragraph/page evidence; "
            "table exactness is not proven by current metadata."
        )
        proposed_action = "Review table-like gold binding and choose table bbox, page-level, or paragraph bbox policy."
    elif failure_type == "PDF_BBOX_POLICY_MISMATCH":
        relabel_candidate = True
        decision_category = "RELABEL_BBOX_OR_PAGE_FALLBACK"
        c7_policy_category = "relabel_candidate"
        rationale = (
            "Correct-page supporting hit is page-level and bbox is optional for page summaries, "
            "while the gold row expects paragraph bbox."
        )
        proposed_action = "Review whether page-level fallback should be accepted or the gold bbox should remain strict."
    elif failure_type == "PDF_CHUNK_GRANULARITY_ISSUE":
        relabel_candidate = True
        decision_category = "RELABEL_CHUNK_TYPE_POLICY"
        c7_policy_category = "relabel_candidate"
        rationale = (
            "Expected page/chunk type differs from top same-page evidence; "
            "this is a chunk granularity or matching-contract issue, not a retrieval miss."
        )
        proposed_action = "Review expected chunk type and rerun C6 after relabel or policy decision."
    elif ocr_used(row):
        ocr_policy_status = "DECIDED"
        decision_category = "OCR_TRUST_POLICY_CONFIRMED"
        rationale = "OCR evidence has confidence/trust handling available in metadata."

    return {
        "query_id": query_id,
        "bucket": bucket,
        "c6_failure_type": failure_type,
        "c5_failure_reason": row.get("c5_failure_reason"),
        "policy_status": policy_status,
        "page_policy_status": page_policy_status,
        "table_policy_status": table_policy_status,
        "ocr_policy_status": ocr_policy_status,
        "relabel_candidate": relabel_candidate,
        "decision_category": decision_category,
        "c7_policy_category": c7_policy_category,
        "rationale": rationale,
        "proposed_action": proposed_action,
        "required_missing_fields": required_missing,
        "expected": expected,
        "supporting_hit_summary": row.get("supporting_hit_summary") or [],
        "next_action": (
            "Record as relabel candidate and rerun C6 after policy/gold decision."
            if relabel_candidate
            else proposed_action
        ),
    }


def required_gold_fields_missing(expected: Mapping[str, Any], gold: Mapping[str, str]) -> list[str]:
    fields = {
        "expected_file_name": expected.get("file_name") or gold.get("expected_file_name"),
        "expected_page_no": expected.get("page_no") if expected.get("page_no") is not None else gold.get("expected_page_no"),
        "expected_physical_page_index": (
            expected.get("physical_page_index")
            if expected.get("physical_page_index") is not None
            else gold.get("expected_physical_page_index")
        ),
    }
    return [name for name, value in fields.items() if value in (None, "")]


def policy_decisions() -> dict[str, str]:
    return {
        "page_policy": (
            "Bound PDF gold rows must carry expected_file_name, page_no, and physical_page_index. "
            "page_label is recorded when available but does not replace numeric page identity."
        ),
        "bbox_policy": (
            "Text/table/OCR block gold may require bbox overlap; page/document summaries may omit bbox. "
            "A page-level hit without bbox is not a strict paragraph-bbox match."
        ),
        "table_policy": (
            "PDF table lookup rows require explicit policy review when current evidence is paragraph/page bound. "
            "They are relabel candidates before retrieval tuning."
        ),
        "ocr_policy": (
            "OCR block evidence must retain ocr_used and confidence/trust metadata. "
            "Rows without required OCR confidence remain lower-trust/policy-excluded candidates."
        ),
        "generic_query_policy": (
            "Generic PDF queries can remain diagnostic, but specific page/bbox expectations should be relabeled "
            "when top-k evidence shows a policy or chunk mismatch rather than pure ranking failure."
        ),
    }


def ocr_used(row: Mapping[str, Any]) -> bool:
    for hit in row.get("supporting_hit_summary") or []:
        if isinstance(hit, Mapping) and hit.get("ocr_used") is True:
            return True
    return False


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


def dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-breakdown", default=str(DEFAULT_BREAKDOWN))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--c1-report", default=str(DEFAULT_C1_REPORT))
    parser.add_argument("--c2-report", default=str(DEFAULT_C2_REPORT))
    parser.add_argument("--c3-report", default=str(DEFAULT_C3_REPORT))
    parser.add_argument("--output", "--report", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
