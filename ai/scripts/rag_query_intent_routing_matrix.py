"""Build Track B R1 query intent routing matrix.

The matrix keeps resource lanes and file/content lookup lanes separate before
later retrieval metrics choose a denominator.
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


DEFAULT_INPUTS = [
    Path("eval/eval_queries/gold_queries_text_namu_v4_v0.csv"),
    Path("eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv"),
    Path("eval/eval_queries/gold_queries_pdf_v0.csv"),
]
DEFAULT_FUTURE_INPUTS: list[Path] = []
DEFAULT_OUTPUT_CSV = Path("eval/eval_queries/query_intent_routing_matrix_v0.csv")
DEFAULT_REPORT = Path("reports/rag_eval/rag-ingestion/rag_query_intent_routing_matrix_report.json")

TRACK_TEXT_NAMUWIKI_ANIMATION = "text_namuwiki_animation"
TRACK_XLSX_BUSINESS_STRUCTURED = "xlsx_business_structured"
TRACK_PDF_BUSINESS_OCR_MM = "pdf_business_ocr_mm"
CURRENT_XLSX_OFFICIAL_SOURCE = "gold_queries_xlsx_human_review_official_positive_v0_retrieval"
LEGACY_XLSX_REVIEWED_SOURCE = "gold_queries_xlsx_v3_positive_reviewed"
CURRENT_TEXT_NAMU_SOURCE = "gold_queries_text_namu_v4_v0"

CSV_FIELDNAMES = [
    "query_id",
    "source_manifest",
    "query",
    "resource_type",
    "target_type",
    "answer_mode",
    "retrieval_lane",
    "readiness",
    "classification_rule",
    "confidence",
    "requires_clarification",
    "notes",
]

RESOURCE_TYPES = ["TEXT", "XLSX", "PDF", "UNKNOWN"]
TARGET_TYPES = ["FILE", "CONTENT", "MIXED", "UNKNOWN"]
LANES = [
    "B_NAMU_TEXT_CONTENT",
    "TEXT_FILE_LOOKUP",
    "XLSX_CONTENT",
    "XLSX_FILE",
    "PDF_CONTENT",
    "PDF_FILE",
    "APP_TEXT_SMOKE",
    "UNKNOWN",
]
READINESS_VALUES = ["READY", "DIAGNOSTIC_READY", "SMOKE_ONLY", "PLANNED", "BLOCKED", "NOT_READY"]

STRONG_FILE_SIGNALS = [
    "파일",
    "문서",
    "보고서",
    "원본",
    "다운로드",
    "목록",
    "열어줘",
    "어디 있어",
]
WEAK_FILE_SIGNALS = ["자료", "찾아줘", "어디야", "어디쯤"]
CONTENT_SIGNALS = [
    "얼마",
    "몇",
    "언제",
    "조건",
    "내용",
    "요약",
    "항목",
    "수치",
    "비율",
    "행",
    "셀",
    "표",
    "페이지",
    "문단",
    "조항",
    "승차",
    "승객수",
    "해지",
    "만료",
    "반납",
]

XLSX_LOCATION_FIELDS = [
    "expected_sheet_name",
    "expected_cell_range",
    "expected_table_id",
]
PDF_LOCATION_FIELDS = [
    "expected_physical_page_index",
    "expected_page_no",
    "expected_page_label",
    "expected_bbox",
]
CONTENT_EVIDENCE_FIELDS = [
    "expected_answer_summary",
    "expected_answer_text",
    "expected_chunk_ids",
    "expected_citation_texts",
    "must_contain_terms",
    "expected_cell_range",
    "expected_page_no",
    "expected_bbox",
]


@dataclass(frozen=True)
class CsvInput:
    path: Path
    role: str = "current_candidate"


@dataclass(frozen=True)
class LoadedInput:
    path: Path
    source_manifest: str
    role: str
    exists: bool
    rows: list[dict[str, str]]
    columns: list[str]
    error: str | None = None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inputs = [CsvInput(Path(item), "current_candidate") for item in args.inputs]
    future_inputs = [CsvInput(Path(item), "future_namu_candidate") for item in args.future_inputs]
    loaded = [load_input(item) for item in inputs]
    future_loaded = [load_input(item) for item in future_inputs]
    matrix_rows = build_matrix_rows(loaded)
    report = build_report(
        loaded=loaded,
        future_loaded=future_loaded,
        matrix_rows=matrix_rows,
        output_csv=Path(args.output_csv),
    )
    write_csv(Path(args.output_csv), matrix_rows)
    write_json(Path(args.report), report)
    print_json({
        "status": report["status"],
        "row_count": report["row_count"],
        "output_csv": str(Path(args.output_csv)),
        "report": str(Path(args.report)),
        "unknown_count": report["unknown_count"],
        "mixed_file_content_count": report["mixed_file_content_count"],
    })
    return 1 if report["blockers"] else 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="*", default=[str(path) for path in DEFAULT_INPUTS])
    parser.add_argument("--future-inputs", nargs="*", default=[str(path) for path in DEFAULT_FUTURE_INPUTS])
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    return parser.parse_args(argv)


def load_input(item: CsvInput) -> LoadedInput:
    path = item.path
    source_manifest = path.stem
    if not path.exists():
        return LoadedInput(
            path=path,
            source_manifest=source_manifest,
            role=item.role,
            exists=False,
            rows=[],
            columns=[],
            error="missing input; skipped by R1 policy",
        )
    try:
        rows, columns = read_csv_rows(path)
    except Exception as exc:
        return LoadedInput(
            path=path,
            source_manifest=source_manifest,
            role=item.role,
            exists=True,
            rows=[],
            columns=[],
            error=f"{type(exc).__name__}: {exc}",
        )
    return LoadedInput(
        path=path,
        source_manifest=source_manifest,
        role=item.role,
        exists=True,
        rows=rows,
        columns=columns,
    )


def build_matrix_rows(inputs: Iterable[LoadedInput]) -> list[dict[str, str]]:
    matrix_rows: list[dict[str, str]] = []
    for loaded in inputs:
        if not loaded.exists or loaded.error:
            continue
        for row in loaded.rows:
            matrix_rows.append(classify_row(row, loaded.source_manifest, columns=loaded.columns))
    return matrix_rows


def classify_row(
    row: Mapping[str, str],
    source_manifest: str,
    *,
    columns: Iterable[str] = (),
) -> dict[str, str]:
    query = clean(row.get("query"))
    resource_type, resource_rule = classify_resource(row, source_manifest, columns=columns)
    target_type, target_rule, confidence, requires_clarification = classify_target(row, query)
    answer_mode = answer_mode_for(row, target_type)
    retrieval_lane = lane_for(resource_type, target_type, source_manifest)
    readiness = readiness_for(retrieval_lane)
    notes = notes_for(
        row=row,
        source_manifest=source_manifest,
        resource_type=resource_type,
        target_type=target_type,
        retrieval_lane=retrieval_lane,
    )
    denominator_eligible, denominator_exclusion_reason = denominator_eligibility(
        row=row,
        source_manifest=source_manifest,
        retrieval_lane=retrieval_lane,
        target_type=target_type,
        readiness=readiness,
    )
    return {
        "query_id": clean(row.get("query_id")) or "<missing query_id>",
        "source_manifest": source_manifest,
        "query": query,
        "resource_type": resource_type,
        "target_type": target_type,
        "answer_mode": answer_mode,
        "retrieval_lane": retrieval_lane,
        "readiness": readiness,
        "classification_rule": f"{resource_rule}; {target_rule}",
        "confidence": confidence,
        "requires_clarification": bool_str(requires_clarification),
        "notes": notes,
        "_denominator_eligible": bool_str(denominator_eligible),
        "_denominator_exclusion_reason": denominator_exclusion_reason,
    }


def classify_resource(
    row: Mapping[str, str],
    source_manifest: str,
    *,
    columns: Iterable[str] = (),
) -> tuple[str, str]:
    location_type = clean(row.get("expected_location_type")).lower()
    column_set = set(columns)
    if location_type == "xlsx":
        return "XLSX", "expected_location_type=xlsx"
    if location_type == "pdf":
        return "PDF", "expected_location_type=pdf"
    if any(clean(row.get(field)) for field in XLSX_LOCATION_FIELDS):
        return "XLSX", "xlsx location fields present"
    if any(clean(row.get(field)) for field in PDF_LOCATION_FIELDS):
        return "PDF", "pdf page/bbox fields present"
    expected_file_name = clean(row.get("expected_file_name")).lower()
    if expected_file_name.endswith((".xlsx", ".xls")):
        return "XLSX", "expected_file_name has XLSX extension"
    if expected_file_name.endswith(".pdf"):
        return "PDF", "expected_file_name has PDF extension"
    if "namu" in source_manifest:
        return "TEXT", "source_manifest=namu-v4"
    if source_manifest == "gold_queries_text_e2e_v0":
        return "TEXT", "source_manifest=legacy Track B app TEXT smoke"
    if {"expected_source_ids", "expected_chunk_ids"}.intersection(column_set):
        return "TEXT", "TEXT source/chunk columns present"
    return "UNKNOWN", "no resource hint or corpus-bound evidence"


def classify_target(row: Mapping[str, str], query: str) -> tuple[str, str, str, bool]:
    strong_file_hits = signal_hits(query, STRONG_FILE_SIGNALS)
    weak_file_hits = signal_hits(query, WEAK_FILE_SIGNALS)
    content_hits = signal_hits(query.replace("엑셀", ""), CONTENT_SIGNALS)
    content_evidence = [field for field in CONTENT_EVIDENCE_FIELDS if clean(row.get(field))]
    file_only_evidence = bool(clean(row.get("expected_file_name"))) and not content_evidence

    if strong_file_hits and (content_hits or content_evidence):
        return "MIXED", signal_rule(strong_file_hits, content_hits, content_evidence), "medium", True
    if file_only_evidence or (strong_file_hits and not content_hits and not content_evidence):
        return "FILE", signal_rule(strong_file_hits, content_hits, content_evidence), "high", False
    if content_hits or content_evidence:
        confidence = "medium" if weak_file_hits else "high"
        return "CONTENT", signal_rule([*strong_file_hits, *weak_file_hits], content_hits, content_evidence), confidence, False
    if weak_file_hits:
        return "FILE", signal_rule(weak_file_hits, content_hits, content_evidence), "medium", False
    return "UNKNOWN", "no file/content signal", "low", True


def signal_rule(
    file_hits: list[str],
    content_hits: list[str],
    content_evidence: list[str],
) -> str:
    parts = []
    if file_hits:
        parts.append("file_signal=" + "|".join(file_hits))
    if content_hits:
        parts.append("content_signal=" + "|".join(content_hits))
    if content_evidence:
        parts.append("content_evidence=" + "|".join(content_evidence))
    return "; ".join(parts) if parts else "no file/content signal"


def signal_hits(query: str, signals: Iterable[str]) -> list[str]:
    return [signal for signal in signals if signal and signal in query]


def answer_mode_for(row: Mapping[str, str], target_type: str) -> str:
    if target_type == "FILE":
        return "FILE_LIST"
    if target_type in {"MIXED", "UNKNOWN"}:
        return "ABSTAIN_OR_CLARIFY"
    if clean(row.get("allowed_abstain")).lower() == "true":
        return "ABSTAIN_OR_CLARIFY"
    if clean(row.get("expected_citation_texts")) or clean(row.get("expected_cell_range")) or clean(row.get("expected_bbox")):
        return "CITATION_LOOKUP"
    return "CONTENT_ANSWER"


def lane_for(resource_type: str, target_type: str, source_manifest: str) -> str:
    if target_type in {"MIXED", "UNKNOWN"} or resource_type == "UNKNOWN":
        return "UNKNOWN"
    if resource_type == "TEXT":
        if target_type == "FILE":
            return "TEXT_FILE_LOOKUP"
        if "namu" in source_manifest:
            return "B_NAMU_TEXT_CONTENT"
        return "APP_TEXT_SMOKE"
    if resource_type == "XLSX":
        return "XLSX_FILE" if target_type == "FILE" else "XLSX_CONTENT"
    if resource_type == "PDF":
        return "PDF_FILE" if target_type == "FILE" else "PDF_CONTENT"
    return "UNKNOWN"


def readiness_for(retrieval_lane: str) -> str:
    return {
        "B_NAMU_TEXT_CONTENT": "DIAGNOSTIC_READY",
        "TEXT_FILE_LOOKUP": "PLANNED",
        "XLSX_CONTENT": "DIAGNOSTIC_READY",
        "XLSX_FILE": "NOT_READY",
        "PDF_CONTENT": "BLOCKED",
        "PDF_FILE": "NOT_READY",
        "APP_TEXT_SMOKE": "SMOKE_ONLY",
        "UNKNOWN": "NOT_READY",
    }.get(retrieval_lane, "NOT_READY")


def notes_for(
    *,
    row: Mapping[str, str],
    source_manifest: str,
    resource_type: str,
    target_type: str,
    retrieval_lane: str,
) -> str:
    notes = []
    original_notes = clean(row.get("notes"))
    if original_notes:
        notes.append(original_notes)
    if source_manifest == "gold_queries_text_e2e_v0":
        notes.append("legacy B-app text smoke; not B-namu representative evidence")
    if retrieval_lane == "PDF_CONTENT":
        notes.append("blocked until Track C PDF readiness is complete")
    if retrieval_lane in {"XLSX_FILE", "PDF_FILE", "TEXT_FILE_LOOKUP"}:
        notes.append("file lookup lane; exclude from content retrieval denominator")
    if target_type in {"MIXED", "UNKNOWN"}:
        notes.append("requires clarification; exclude from positive retrieval denominator")
    if resource_type == "UNKNOWN":
        notes.append("no resource hint or corpus-bound evidence")
    return "; ".join(unique(notes))


def denominator_eligibility(
    *,
    row: Mapping[str, str],
    source_manifest: str,
    retrieval_lane: str,
    target_type: str,
    readiness: str,
) -> tuple[bool, str]:
    if target_type in {"MIXED", "UNKNOWN"}:
        return False, "target_type_requires_clarification"
    if readiness in {"BLOCKED", "NOT_READY", "PLANNED", "SMOKE_ONLY"}:
        return False, f"readiness_{readiness.lower()}_excluded"
    if retrieval_lane == "B_NAMU_TEXT_CONTENT":
        if source_manifest != CURRENT_TEXT_NAMU_SOURCE:
            return False, "source manifest is not the current namu-v4 text set"
        label_status = clean(row.get("label_status")).lower()
        if label_status != "bound":
            return False, f"label_status={label_status or '<missing>'}"
        return True, ""
    if retrieval_lane != "XLSX_CONTENT":
        return False, "only current TEXT_NAMU and XLSX_CONTENT rows are denominator eligible"
    if source_manifest == CURRENT_XLSX_OFFICIAL_SOURCE:
        label_status = clean(row.get("label_status")).lower()
        if label_status != "bound":
            return False, f"label_status={label_status or '<missing>'}"
        return True, ""
    if source_manifest != LEGACY_XLSX_REVIEWED_SOURCE:
        return False, "source manifest is not the current XLSX official or legacy reviewed positive set"
    policy_label = clean(row.get("policy_label")).lower()
    review_decision = clean(row.get("review_decision")).upper()
    promotion_eval_eligible = clean(row.get("promotion_eval_eligible")).lower()
    review_status = clean(row.get("review_status")).lower()
    if policy_label != "positive":
        return False, f"policy_label={policy_label or '<missing>'}"
    if review_decision != "KEEP_AS_POSITIVE":
        return False, f"review_decision={review_decision or '<missing>'}"
    if promotion_eval_eligible != "true":
        return False, f"promotion_eval_eligible={promotion_eval_eligible or '<missing>'}"
    if review_status != "ready_positive":
        return False, f"review_status={review_status or '<missing>'}"
    return True, ""


def build_report(
    *,
    loaded: list[LoadedInput],
    future_loaded: list[LoadedInput],
    matrix_rows: list[dict[str, str]],
    output_csv: Path,
) -> dict[str, Any]:
    lane_counts = seeded_counter((row["retrieval_lane"] for row in matrix_rows), LANES)
    readiness_counts = seeded_counter((row["readiness"] for row in matrix_rows), READINESS_VALUES)
    resource_counts = seeded_counter((row["resource_type"] for row in matrix_rows), RESOURCE_TYPES)
    target_counts = seeded_counter((row["target_type"] for row in matrix_rows), TARGET_TYPES)
    ambiguous_count = sum(1 for row in matrix_rows if row["requires_clarification"] == "true")
    unknown_count = sum(1 for row in matrix_rows if row["resource_type"] == "UNKNOWN" or row["retrieval_lane"] == "UNKNOWN")
    mixed_count = sum(1 for row in matrix_rows if row["target_type"] == "MIXED")
    required_acceptance_lanes = ["B_NAMU_TEXT_CONTENT", "XLSX_CONTENT", "PDF_CONTENT", "XLSX_FILE", "PDF_FILE", "UNKNOWN"]
    observed_required_lane_coverage = {
        lane: lane_counts.get(lane, 0) > 0 for lane in required_acceptance_lanes
    }
    missing_current = [record["path"] for record in input_records(loaded) if not record["exists"] or record.get("error")]
    missing_future = [record["path"] for record in input_records(future_loaded) if not record["exists"] or record.get("error")]
    blockers = []
    if not matrix_rows:
        blockers.append("no usable input rows were available")
    eligible_groups = eligible_denominator_groups(matrix_rows)
    denominator_exclusion_counts = dict(sorted(Counter(
        row.get("_denominator_exclusion_reason", "")
        for row in matrix_rows
        if row.get("_denominator_eligible") != "true"
    ).items()))
    completion_criteria = {
        "csv_schema_matches_phase_doc": True,
        "at_least_one_usable_input": bool(matrix_rows),
        "lane_schema_declares_required_lanes": all(lane in lane_counts for lane in required_acceptance_lanes),
        "observed_required_lane_coverage_complete": all(observed_required_lane_coverage.values()),
        "unknown_rows_excluded_from_positive_denominator": True,
        "mixed_rows_require_clarification": all(
            row["requires_clarification"] == "true" for row in matrix_rows if row["target_type"] == "MIXED"
        ),
        "xlsx_pdf_file_lanes_separate_from_content_lanes": True,
        "positive_denominator_must_group_by_retrieval_lane": True,
        "blocked_planned_smoke_and_file_lanes_excluded_from_generic_positive_denominator": True,
        "promotion_evidence_false": True,
    }
    status = "COMPLETED" if not blockers and all(completion_criteria.values()) else "NEEDS_REVIEW"
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_query_intent_routing_matrix_v1",
        "status": status,
        "report_role": "rag_query_intent_routing_matrix",
        "scope": "track_b_text_retrieval_e2e",
        "phase": "R1",
        "track_architecture": {
            "tracks": [
                TRACK_TEXT_NAMUWIKI_ANIMATION,
                TRACK_XLSX_BUSINESS_STRUCTURED,
                TRACK_PDF_BUSINESS_OCR_MM,
            ],
            "text_track_domain": "Namuwiki animation-domain RAG, not general business text RAG",
            "xlsx_track_goal": "business spreadsheet structured RAG with structure-aware retrieval",
            "pdf_track_goal": "business OCR/MM document RAG with layout-aware retrieval",
            "single_integrated_vector_index": False,
        },
        "output_csv": str(output_csv).replace("\\", "/"),
        "row_count": len(matrix_rows),
        "lane_counts": lane_counts,
        "readiness_counts": readiness_counts,
        "resource_type_counts": resource_counts,
        "target_type_counts": target_counts,
        "ambiguous_count": ambiguous_count,
        "unknown_count": unknown_count,
        "mixed_file_content_count": mixed_count,
        "blocked_lane_counts": {
            lane: lane_counts.get(lane, 0)
            for lane in ["PDF_CONTENT", "PDF_FILE", "XLSX_FILE", "TEXT_FILE_LOOKUP", "UNKNOWN"]
        },
        "observed_required_lane_coverage": observed_required_lane_coverage,
        "positive_denominator_policy": {
            "must_group_by": ["retrieval_lane"],
            "exclude_target_types": ["MIXED", "UNKNOWN"],
            "exclude_readiness": ["BLOCKED", "NOT_READY", "PLANNED", "SMOKE_ONLY"],
            "exclude_retrieval_lanes": [
                "UNKNOWN",
                "APP_TEXT_SMOKE",
                "TEXT_FILE_LOOKUP",
                "XLSX_FILE",
                "PDF_FILE",
                "PDF_CONTENT",
            ],
            "eligible_denominator_groups_by_lane": eligible_groups,
            "track_namespace_policy": {
                "B_NAMU_TEXT_CONTENT": "text_namuwiki_animation namespace/index/eval denominator",
                "XLSX_CONTENT": "xlsx_business_structured namespace/index/eval denominator",
                "PDF_CONTENT": "pdf_business_ocr_mm namespace/index/eval denominator; conservative C7 rows only",
            },
            "notes": [
                "B-app smoke rows are preserved for diagnostics but not used as B-namu denominators.",
                "FILE lookup lanes are not content retrieval metrics.",
                "Positive denominators must be computed per retrieval_lane, never by aggregating all CONTENT rows.",
                "BLOCKED, NOT_READY, PLANNED, and SMOKE_ONLY rows are excluded from generic positive denominators.",
                "UNKNOWN and MIXED rows require clarification before positive Hit/MRR denominators.",
            ],
        },
        "route_decision_metrics": {
            "routing_accuracy": None,
            "wrong_route_rate": None,
            "fallback_success_rate": None,
            "multi_route_success_rate": None,
            "low_confidence_route_count": sum(1 for row in matrix_rows if row.get("confidence") == "low"),
            "diagnostic_only_reason": "route gold labels and fallback outcomes are not human-verified in this matrix",
        },
        "denominator_exclusion_counts": denominator_exclusion_counts,
        "lane_readiness_policy": {
            "B_NAMU_TEXT_CONTENT": "DIAGNOSTIC_READY for namu-v4 bound rows; keep separate from APP_TEXT_SMOKE",
            "XLSX_CONTENT": "DIAGNOSTIC_READY from current XLSX positive diagnostics",
            "PDF_CONTENT": "BLOCKED until Track C PDF readiness",
            "XLSX_FILE": "NOT_READY; file lookup index is separate from content retrieval",
            "PDF_FILE": "NOT_READY; file lookup index is separate from content retrieval",
            "UNKNOWN": "NOT_READY; requires clarification",
        },
        "inputs": input_records(loaded),
        "future_inputs": input_records(future_loaded),
        "missing_inputs": missing_current,
        "missing_future_inputs": missing_future,
        "missing_input_policy": {
            "current_candidates": "Missing current candidate inputs are recorded and skipped; at least one usable input is required.",
            "future_namu_candidate": "Optional future inputs are recorded and skipped; namu-v4 is now a current text track input when present.",
        },
        "completion_criteria": completion_criteria,
        "blockers": blockers,
        "warnings": warnings_for(lane_counts, missing_future, unknown_count, mixed_count),
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "next_phase_recommendation": "Keep route decisions and denominators track-scoped; do not aggregate TEXT/XLSX/PDF into one quality score.",
    }


def warnings_for(
    lane_counts: Mapping[str, int],
    missing_future: list[str],
    unknown_count: int,
    mixed_count: int,
) -> list[str]:
    warnings = []
    if missing_future:
        warnings.append("B-namu gold input is not expected until R2/R3 and is currently missing.")
    if lane_counts.get("APP_TEXT_SMOKE", 0):
        warnings.append("APP_TEXT_SMOKE rows are legacy B-app diagnostics and not B-namu evidence.")
    if lane_counts.get("PDF_CONTENT", 0):
        warnings.append("PDF_CONTENT rows remain blocked until Track C readiness is complete.")
    if unknown_count:
        warnings.append("UNKNOWN rows must not enter positive retrieval denominators.")
    if mixed_count:
        warnings.append("MIXED rows require clarification before metric use.")
    return warnings


def eligible_denominator_groups(matrix_rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in matrix_rows:
        if row.get("_denominator_eligible") != "true":
            continue
        lane = row["retrieval_lane"]
        entry = groups.setdefault(
            lane,
            {
                "row_count": 0,
                "readiness": row["readiness"],
                "query_ids": [],
                "denominator_role": "lane_scoped_positive_candidate",
            },
        )
        entry["row_count"] += 1
        entry["query_ids"].append(row["query_id"])
    return groups


def input_records(inputs: list[LoadedInput]) -> list[dict[str, Any]]:
    return [
        {
            "path": str(item.path).replace("\\", "/"),
            "source_manifest": item.source_manifest,
            "role": item.role,
            "exists": item.exists,
            "row_count": len(item.rows),
            "columns": item.columns,
            "sha256": sha256_file(item.path) if item.path.exists() and not item.error else None,
            "bytes": item.path.stat().st_size if item.path.exists() else None,
            "error": item.error,
        }
        for item in inputs
    ]


def seeded_counter(values: Iterable[str], seed_keys: Iterable[str]) -> dict[str, int]:
    counter = Counter(values)
    return {key: int(counter.get(key, 0)) for key in seed_keys}


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDNAMES})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean(value: str | None) -> str:
    return (value or "").strip()


def bool_str(value: bool) -> str:
    return "true" if value else "false"


def unique(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
