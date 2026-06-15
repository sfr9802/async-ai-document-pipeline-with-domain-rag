"""Audit PDF question/evidence lineage before regenerating gold candidates.

This script is report-only. It traces the current PDF strict-ready diagnostic
rows through vector diagnostic, repair rows, answer/citation input, and human
audit v1. It also records local prior review/gold-like source candidates so the
next canary can distinguish "good prior source" from "current bad surface".
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_local_llm_expected_answer_generation_v1 import (  # noqa: E402
    clean,
    read_json,
    read_jsonl,
    repo_relative,
    utc_timestamp,
    write_json,
)
from rag_question_quality_gate_v1 import NATURAL_LANGUAGE_QUESTION, classify_question  # noqa: E402


REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_VECTOR_REPORT = REPO_ROOT / "reports" / "rag_retrieval_eval_pdf_vector_diagnostic_report.json"
DEFAULT_REPAIR_REPORT = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_PDF_REVIEW_INPUT = REPORT_DIR / "pdf_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_HUMAN_AUDIT_PACKET = REVIEW_DIR / "rag_human_audit_packet_v1.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "pdf_gold_evidence_lineage_audit_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "pdf_gold_evidence_lineage_audit_v1.md"
DEFAULT_SOURCE_CANDIDATE_FILES = [
    AI_WORKER_ROOT / "eval" / "corpora" / "gold_queries_pdf_v1_reviewed.csv",
    AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_pdf_v0.csv",
    AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_pdf_supplemental_elec_lh_synthetic_diagnostic.csv",
    REPO_ROOT / "reports" / "rag_pdf_gold_policy_review.json",
    REPO_ROOT / "reports" / "rag_pdf_gold_policy_decision_overlay.json",
    REPO_ROOT / "reports" / "rag_pdf_v1_reviewed_manifest_report.json",
    REPO_ROOT / "reports" / "rag_pdf_c8_case_level_review_report.json",
    REVIEW_DIR
    / "_archive"
    / "2026-05-11-review-cleanup"
    / "pdf_supplemental_gold_review"
    / "pdf_gold_review_pack_manual_v1_file_lookup_companion.jsonl",
]
KNOWN_ABSENT_MANUAL_CSV = REPO_ROOT / "ai-worker" / "eval" / "review" / "pdf_supplemental_gold_review" / "pdf_gold_review_pack_manual_v1.csv"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_files = [Path(path) for path in args.source_candidate_file] if args.source_candidate_file else None
    report = run_audit(
        vector_report=Path(args.vector_report),
        repair_report=Path(args.repair_report),
        pdf_review_input=Path(args.pdf_review_input),
        human_audit_packet=Path(args.human_audit_packet),
        source_candidate_files=source_files,
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "lineage_rows": report["summary"]["current_pdf_rows"],
                "vector_query_surface_already_bad_rows": report["summary"]["vector_query_surface_already_bad_rows"],
                "prior_good_candidate_rows": report["summary"]["prior_good_candidate_rows"],
                "report": report["artifact_paths"]["report_json"],
                "official_metric_input_rows": report["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vector-report", default=str(DEFAULT_VECTOR_REPORT))
    parser.add_argument("--repair-report", default=str(DEFAULT_REPAIR_REPORT))
    parser.add_argument("--pdf-review-input", default=str(DEFAULT_PDF_REVIEW_INPUT))
    parser.add_argument("--human-audit-packet", default=str(DEFAULT_HUMAN_AUDIT_PACKET))
    parser.add_argument("--source-candidate-file", action="append", default=[])
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_audit(
    *,
    vector_report: Path = DEFAULT_VECTOR_REPORT,
    repair_report: Path = DEFAULT_REPAIR_REPORT,
    pdf_review_input: Path = DEFAULT_PDF_REVIEW_INPUT,
    human_audit_packet: Path = DEFAULT_HUMAN_AUDIT_PACKET,
    source_candidate_files: Sequence[Path] | None = None,
    output_report: Path = DEFAULT_OUTPUT_JSON,
    output_md: Path = DEFAULT_OUTPUT_MD,
) -> dict[str, Any]:
    vector_payload = read_json(vector_report)
    repair_payload = read_json(repair_report)
    input_rows = read_jsonl(pdf_review_input)
    human_payload = read_json(human_audit_packet)

    vector_lookup = load_vector_lookup(vector_payload)
    repair_lookup = keyed_rows(repair_payload.get("repair_rows"))
    input_lookup = keyed_rows(input_rows)
    human_lookup = load_human_pdf_lookup(human_payload)
    query_ids = sorted(set(input_lookup) | set(repair_lookup))

    lineage_rows = [
        build_lineage_row(
            query_id=query_id,
            vector_row=vector_lookup.get(query_id, {}),
            repair_row=repair_lookup.get(query_id, {}),
            input_row=input_lookup.get(query_id, {}),
            human_row=human_lookup.get(query_id, {}),
        )
        for query_id in query_ids
    ]
    source_files = list(source_candidate_files or DEFAULT_SOURCE_CANDIDATE_FILES)
    protected_source_errors = protected_source_candidate_errors(source_files)
    safe_source_files = [path for path in source_files if not is_protected_source_candidate_path(path)]
    source_summaries, prior_good_rows = inspect_source_candidate_files(safe_source_files)
    matching_prior_rows = matching_source_rows(safe_source_files, set(query_ids))
    counters = Counter(stage for row in lineage_rows for stage in row["degradation_stages"])
    class_counts = Counter(label for row in lineage_rows for label in row["surface_classifications"])
    validation_errors = validation_errors_for(vector_payload, repair_payload, input_rows, human_payload)
    validation_errors.extend(protected_source_errors)
    report = {
        "schema_version": "rag_pdf_gold_evidence_lineage_audit_v1",
        "generated_at": utc_timestamp(),
        "status": "PDF_GOLD_EVIDENCE_LINEAGE_AUDIT_COMPLETE" if not validation_errors else "FAILED_GUARDRAIL",
        "diagnostic_only": True,
        "report_only": True,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "official_denominator_registry_opened": False,
        "tuning_run_started": False,
        "gold_registry_mutated": False,
        "candidate_artifact_mutated": False,
        "production_vector_index_mutated": False,
        "source_artifacts": {
            "vector_report": repo_relative(vector_report),
            "repair_report": repo_relative(repair_report),
            "pdf_review_input": repo_relative(pdf_review_input),
            "human_audit_packet": repo_relative(human_audit_packet),
        },
        "summary": {
            "current_pdf_rows": len(lineage_rows),
            "vector_query_surface_already_bad_rows": counters["VECTOR_QUERY_SURFACE_ALREADY_BAD"],
            "repair_nearby_context_locator_only_rows": counters["REPAIR_NEARBY_CONTEXT_LOCATOR_ONLY"],
            "answer_input_echoes_matched_text_rows": counters["ANSWER_INPUT_ECHOES_MATCHED_TEXT"],
            "human_audit_inherited_bad_query_rows": counters["HUMAN_AUDIT_INHERITED_BAD_QUERY"],
            "prior_source_candidate_files": len(source_summaries),
            "prior_good_candidate_rows": len(prior_good_rows),
            "matching_prior_review_rows": len(matching_prior_rows),
            "matching_prior_review_positive_rows": sum(1 for row in matching_prior_rows if row.get("positive_review_row")),
            "surface_classification_counts": dict(sorted(class_counts.items())),
            "degradation_stage_counts": dict(sorted(counters.items())),
        },
        "lineage_rows": lineage_rows,
        "source_candidate_files": source_summaries,
        "prior_good_candidate_rows": prior_good_rows,
        "matching_prior_review_rows": matching_prior_rows,
        "known_manual_review_csv": {
            "path": repo_relative(KNOWN_ABSENT_MANUAL_CSV),
            "exists": KNOWN_ABSENT_MANUAL_CSV.exists(),
        },
        "root_cause_summary": root_cause_summary(lineage_rows),
        "next_safe_actions": [
            "Keep PDF evidence readiness separate from official question-gold readiness.",
            "Build canary with current bad 7 rows plus prior review-source rows that have evidence text.",
            "Reprocess native/OCR context so locator-only nearby rows cannot enter answer candidates.",
            "Route PDF table labels to deterministic table extraction before any LLM phrasing.",
        ],
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
        "validation": {"ok": not validation_errors, "errors": validation_errors},
    }
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_lineage_row(
    *,
    query_id: str,
    vector_row: Mapping[str, Any],
    repair_row: Mapping[str, Any],
    input_row: Mapping[str, Any],
    human_row: Mapping[str, Any],
) -> dict[str, Any]:
    vector_query = clean(vector_row.get("query") or vector_row.get("question"))
    matched_text = clean(repair_row.get("matched_text") or input_row.get("matched_text"))
    generated_answer = clean(input_row.get("diagnostic_answer") or input_row.get("generated_answer"))
    human_question = clean(human_row.get("question"))
    quality = classify_question(
        vector_query or human_question or matched_text,
        query_id=query_id,
        track="pdf_business_ocr_mm",
        region_type=clean(repair_row.get("region_type") or input_row.get("region_type")),
        evidence_text=matched_text,
        answer_text=clean(human_row.get("proposed_answer") or generated_answer),
    )
    classifications = quality["classifications"]
    vector_surface_bad = classifications != [NATURAL_LANGUAGE_QUESTION]
    locator_only = has_locator_only_nearby(repair_row) or has_locator_only_nearby(input_row)
    answer_echo = (
        bool(generated_answer)
        and normalize(generated_answer) == normalize(matched_text)
        and (vector_surface_bad or normalize(vector_query) == normalize(matched_text))
    )
    human_inherited = bool(human_question and vector_query and normalize(human_question) == normalize(vector_query) and vector_surface_bad)

    stages: list[str] = []
    if vector_surface_bad:
        stages.append("VECTOR_QUERY_SURFACE_ALREADY_BAD")
    if locator_only:
        stages.append("REPAIR_NEARBY_CONTEXT_LOCATOR_ONLY")
    if answer_echo:
        stages.append("ANSWER_INPUT_ECHOES_MATCHED_TEXT")
    if human_inherited:
        stages.append("HUMAN_AUDIT_INHERITED_BAD_QUERY")
    return {
        "query_id": query_id,
        "vector_diagnostic": {
            "query": vector_query,
            "bucket": clean(vector_row.get("bucket")),
            "hit_rank": vector_row.get("hit_rank"),
            "failure_reason": clean(vector_row.get("failure_reason")),
        },
        "repair_row": {
            "matched_text": matched_text,
            "nearby_paragraphs": list_value(repair_row.get("nearby_paragraphs")),
            "content_evidence_lane": clean(repair_row.get("content_evidence_lane")),
            "native_text_available": repair_row.get("native_text_available") is True,
            "OCR_fallback_used": repair_row.get("OCR_fallback_used") is True,
            "region_type": clean(repair_row.get("region_type")),
            "citation_locator": citation_locator_summary(repair_row),
        },
        "pdf_answer_citation_input": {
            "generated_answer": generated_answer,
            "diagnostic_answer": clean(input_row.get("diagnostic_answer")),
            "matched_text": clean(input_row.get("matched_text")),
            "nearby_paragraphs": list_value(input_row.get("nearby_paragraphs")),
        },
        "human_audit_v1": {
            "question": human_question,
            "proposed_answer": clean(human_row.get("proposed_answer")),
            "issue_type": clean(human_row.get("issue_type")),
            "lane_decision_scope": clean(human_row.get("lane_decision_scope")),
        },
        "surface_classifications": classifications,
        "degradation_stages": stages,
        "root_cause": classify_root_cause(stages),
    }


def classify_root_cause(stages: Sequence[str]) -> str:
    stage_set = set(stages)
    if {"VECTOR_QUERY_SURFACE_ALREADY_BAD", "REPAIR_NEARBY_CONTEXT_LOCATOR_ONLY"} <= stage_set:
        return "VECTOR_BAD_QUERY_SURFACE_AND_REPAIR_LOCATOR_ONLY"
    if "VECTOR_QUERY_SURFACE_ALREADY_BAD" in stage_set:
        return "VECTOR_QUERY_SURFACE_ALREADY_BAD"
    if "REPAIR_NEARBY_CONTEXT_LOCATOR_ONLY" in stage_set:
        return "REPAIR_CONTEXT_TEXT_MISSING"
    if not stages:
        return "NO_DEGRADATION_DETECTED_IN_CURRENT_TRACE"
    return "PDF_LINEAGE_REVIEW_REQUIRED"


def inspect_source_candidate_files(files: Sequence[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries: list[dict[str, Any]] = []
    prior_good_rows: list[dict[str, Any]] = []
    for path in files:
        summary = inspect_source_candidate_file(path)
        summaries.append(summary)
        prior_good_rows.extend(summary.pop("_prior_good_rows", []))
    return summaries, prior_good_rows


def matching_source_rows(files: Sequence[Path], query_ids: set[str]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for path in files:
        if not path.exists() or not path.is_file():
            continue
        try:
            if path.suffix.lower() == ".csv":
                rows = read_csv_rows(path)
            elif path.suffix.lower() == ".jsonl":
                rows = read_jsonl(path)
            elif path.suffix.lower() == ".json":
                rows = rows_from_json_source(read_json(path))
            else:
                rows = []
        except Exception:
            rows = []
        for row in rows:
            query_id = clean(row.get("query_id") or row.get("row_id"))
            if query_id not in query_ids:
                continue
            matches.append(
                {
                    "source_path": repo_relative(path),
                    "source_role": candidate_role_for_path(path),
                    "query_id": query_id,
                    "query": clean(row.get("query") or row.get("question")),
                    "expected_answer_text": clean(
                        row.get("expected_answer_text") or row.get("expected_evidence_excerpt")
                    ),
                    "expected_chunk_type": clean(row.get("expected_chunk_type") or row.get("anchor_type")),
                    "label_status": clean(row.get("label_status")),
                    "review_decision": clean(row.get("review_decision") or row.get("final_decision")),
                    "pdf_review_label": clean(row.get("pdf_review_label")),
                    "positive_metric_eligible": bool_value(row.get("positive_metric_eligible")),
                    "positive_review_row": positive_review_row(row),
                }
            )
    return matches


def inspect_source_candidate_file(path: Path) -> dict[str, Any]:
    exists = path.exists()
    summary: dict[str, Any] = {
        "path": repo_relative(path),
        "exists": exists,
        "candidate_role": candidate_role_for_path(path),
        "row_count": 0,
        "sample_fields": [],
        "sample_rows": [],
        "_prior_good_rows": [],
    }
    if not exists or not path.is_file():
        return summary
    try:
        if path.suffix.lower() == ".csv":
            rows = read_csv_rows(path)
        elif path.suffix.lower() == ".jsonl":
            rows = read_jsonl(path)
        elif path.suffix.lower() == ".json":
            rows = rows_from_json_source(read_json(path))
        else:
            rows = []
    except Exception as exc:  # pragma: no cover - defensive report-only path
        summary["read_error"] = f"{type(exc).__name__}: {exc}"
        return summary
    summary["row_count"] = len(rows)
    summary["sample_fields"] = sorted({key for row in rows[:5] for key in row.keys()})[:30]
    summary["sample_rows"] = [source_sample_row(row) for row in rows[:3]]
    summary["_prior_good_rows"] = [
        prior_good_row(row, path, summary["candidate_role"])
        for row in rows
        if is_prior_good_source_row(row)
    ][:30]
    return summary


def is_prior_good_source_row(row: Mapping[str, Any]) -> bool:
    query = clean(row.get("query") or row.get("question"))
    evidence = clean(row.get("expected_answer_text") or row.get("expected_evidence_excerpt") or row.get("answerable_evidence_text"))
    if not query or not evidence:
        return False
    quality = classify_question(query, track="pdf_business_ocr_mm", evidence_text=evidence)
    if quality["primary_classification"] != NATURAL_LANGUAGE_QUESTION:
        return False
    label_status = clean(row.get("label_status")).lower()
    review_decision = clean(row.get("review_decision") or row.get("user_gold_decision"))
    if label_status in {"excluded", "pending"}:
        return False
    if review_decision and "DEFER" in review_decision:
        return False
    return True


def positive_review_row(row: Mapping[str, Any]) -> bool:
    decision = clean(row.get("review_decision") or row.get("final_decision"))
    label = clean(row.get("pdf_review_label"))
    eligible = bool_value(row.get("positive_metric_eligible"))
    return (
        eligible
        or "KEEP_REVIEWED_POSITIVE" in decision
        or "ACCEPT" in decision
        or label == "positive_reviewed"
    )


def prior_good_row(row: Mapping[str, Any], path: Path, role: str) -> dict[str, Any]:
    bbox = parse_bbox(row.get("expected_bbox") or row.get("parser_derived_bbox"))
    page = int_or_none(row.get("expected_page_no") or row.get("parser_derived_page_no"))
    return {
        "source_path": repo_relative(path),
        "source_role": role,
        "query_id": clean(row.get("query_id") or row.get("row_id")),
        "query": clean(row.get("query") or row.get("question")),
        "expected_answer_text": clean(row.get("expected_answer_text") or row.get("expected_evidence_excerpt")),
        "expected_file_name": clean(row.get("expected_file_name") or row.get("file_name") or row.get("source_file_name")),
        "expected_page_no": page,
        "expected_bbox": bbox,
        "expected_chunk_type": clean(row.get("expected_chunk_type") or row.get("anchor_type")),
        "label_status": clean(row.get("label_status")),
        "review_decision": clean(row.get("review_decision") or row.get("user_gold_decision")),
    }


def source_sample_row(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "query_id",
        "bucket",
        "query",
        "question",
        "expected_answer_text",
        "expected_evidence_excerpt",
        "expected_file_name",
        "file_name",
        "expected_page_no",
        "expected_bbox",
        "label_status",
        "review_decision",
        "pdf_review_label",
        "positive_metric_eligible",
    ]
    return {key: clean(row.get(key)) for key in keys if key in row}


def candidate_role_for_path(path: Path) -> str:
    text = str(path).replace("\\", "/").lower()
    if "gold_queries_pdf_v1_reviewed" in text:
        return "reviewed_gold_corpus"
    if "gold_queries_pdf_v0" in text:
        return "legacy_gold_input"
    if "supplemental" in text and "diagnostic" in text:
        return "diagnostic_supplemental_source"
    if "manual_v1" in text or "review" in text:
        return "diagnostic_prior_review_source"
    if "policy" in text or "manifest" in text or "case_level" in text:
        return "diagnostic_policy_or_case_report"
    return "diagnostic_prior_review_source"


def rows_from_json_source(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("rows", "reviewed_candidate_rows", "relabel_candidate_rows", "actionable_rows", "c7_review_rows"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(dict(row) for row in value if isinstance(row, Mapping))
    return rows


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def load_vector_lookup(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for key in ("per_query", "query_results", "rows"):
        rows = payload.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, Mapping) and clean(row.get("query_id")):
                lookup[clean(row.get("query_id"))] = dict(row)
    return lookup


def keyed_rows(rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    return {clean(row.get("query_id")): dict(row) for row in rows if isinstance(row, Mapping) and clean(row.get("query_id"))}


def load_human_pdf_lookup(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("actionable_rows")
    if not isinstance(rows, list):
        return {}
    return {
        clean(row.get("query_id")): dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and clean(row.get("query_id"))
        and clean(row.get("track")) == "pdf_business_ocr_mm"
    }


def validation_errors_for(
    vector_payload: Mapping[str, Any],
    repair_payload: Mapping[str, Any],
    input_rows: Sequence[Mapping[str, Any]],
    human_payload: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if int_or_none(vector_payload.get("official_metric_input_rows")) not in (None, 0):
        errors.append("vector_report official_metric_input_rows must remain 0")
    if vector_payload.get("promotion_evidence") is True:
        errors.append("vector_report promotion_evidence must remain false")
    if int_or_none(repair_payload.get("official_metric_input_rows")) not in (None, 0):
        errors.append("repair_report official_metric_input_rows must remain 0")
    if int_or_none(human_payload.get("official_metric_input_rows")) not in (None, 0):
        errors.append("human_audit_packet official_metric_input_rows must remain 0")
    if any(row.get("official_metric_input") is True for row in input_rows):
        errors.append("pdf_review_input rows must not set official_metric_input=true")
    if repair_payload.get("promotion_evidence") is True or human_payload.get("promotion_evidence") is True:
        errors.append("promotion_evidence must remain false")
    guardrails = repair_payload.get("guardrails") if isinstance(repair_payload.get("guardrails"), Mapping) else {}
    if guardrails.get("official_denominator_registry_opened") is True:
        errors.append("official_denominator_registry_opened must remain false")
    return errors


def protected_source_candidate_errors(paths: Sequence[Path]) -> list[str]:
    return [f"PROTECTED_SOURCE_CANDIDATE_PATH:{repo_relative(path)}" for path in paths if is_protected_source_candidate_path(path)]


def is_protected_source_candidate_path(path: Path) -> bool:
    normalized = str(path).replace("\\", "/").lower()
    return normalized.endswith("official_denominator_registry.json") or "/eval_queries/official_denominator_registry.json" in normalized


def root_cause_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_root = Counter(clean(row.get("root_cause")) for row in rows)
    return {
        "counts": dict(sorted(by_root.items())),
        "interpretation": (
            "Current PDF evidence readiness preserved locator/layout metadata, but it did not prove "
            "that the query surface was a natural answerable question or that nearby context contained text."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    lines = [
        "# PDF Gold/Evidence Lineage Audit v1",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Current PDF rows: `{summary.get('current_pdf_rows')}`",
        f"- Bad vector query surface rows: `{summary.get('vector_query_surface_already_bad_rows')}`",
        f"- Locator-only nearby context rows: `{summary.get('repair_nearby_context_locator_only_rows')}`",
        f"- Prior good candidate rows: `{summary.get('prior_good_candidate_rows')}`",
        f"- Matching prior review rows: `{summary.get('matching_prior_review_rows')}`",
        f"- Matching prior review positive rows: `{summary.get('matching_prior_review_positive_rows')}`",
        f"- Official metric input rows: `{report.get('official_metric_input_rows')}`",
        f"- Promotion evidence: `{str(report.get('promotion_evidence')).lower()}`",
        "",
        "## Current Row Trace",
        "",
    ]
    for row in report.get("lineage_rows", []):
        lines.append(
            f"- `{row.get('query_id')}` root=`{row.get('root_cause')}` "
            f"classes=`{', '.join(row.get('surface_classifications', []))}`"
        )
    lines.extend(["", "## Source Candidates", ""])
    for item in report.get("source_candidate_files", []):
        lines.append(
            f"- `{item.get('path')}` role=`{item.get('candidate_role')}` "
            f"exists=`{str(item.get('exists')).lower()}` rows=`{item.get('row_count')}`"
        )
    return "\n".join(lines) + "\n"


def citation_locator_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    return {
        "file": clean(locator.get("file") or row.get("file") or row.get("source_file_id")),
        "page": row.get("page") if row.get("page") is not None else locator.get("page"),
        "bbox": row.get("bbox") if row.get("bbox") else locator.get("bbox"),
        "region_type": clean(row.get("region_type") or locator.get("region_type")),
        "search_unit_id": clean(row.get("search_unit_id") or locator.get("search_unit_id")),
    }


def has_locator_only_nearby(row: Mapping[str, Any]) -> bool:
    values = [clean(item) for item in list_value(row.get("nearby_paragraphs")) if clean(item)]
    return bool(values) and all(is_locator_text(value) for value in values)


def is_locator_text(value: str) -> bool:
    return bool(re.search(r"\S+\.pdf\s*>\s*p\.\d+\s*>\s*bbox\s*\[", value))


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_or_none(value: Any) -> int | None:
    try:
        if value in ("", None):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_bbox(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not clean(value):
        return []
    try:
        parsed = ast.literal_eval(clean(value))
    except (SyntaxError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def normalize(value: str) -> str:
    return "".join(clean(value).lower().split())


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y"}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
