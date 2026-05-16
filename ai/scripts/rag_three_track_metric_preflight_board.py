"""Build a three-track diagnostic metric-preflight board.

The board reports TEXT/Namu V2.1, XLSX answer/citation diagnostics, and PDF
evidence readiness separately. It does not compute official metrics, open
official denominators, run tuning, or average across tracks.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_TEXT_POLICY_PACKET = REVIEW_DIR / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json"
DEFAULT_XLSX_ANSWER_REPORT = REPORT_DIR / "rag_xlsx_answer_citation_policy_review_packet_v1.json"
DEFAULT_PDF_READINESS_REPORT = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_PDF_ANSWER_REPORT = REPORT_DIR / "rag_pdf_answer_citation_policy_review_packet_v1.json"
DEFAULT_HUMAN_AUDIT_PACKET_V2 = REVIEW_DIR / "rag_human_audit_packet_v2_question_quality_local_llm.json"
DEFAULT_APPLIED_DECISIONS = REVIEW_DIR / "rag_human_audit_v2_applied_decisions.json"
DEFAULT_DENOMINATOR_DIFF_PREVIEW = REPORT_DIR / "official_denominator_candidate_diff_preview_v1.json"
DEFAULT_METRIC_INPUT_CONFIG = REPORT_DIR / "official_metric_input_config_v1.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "three_track_metric_preflight_board.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "three_track_metric_preflight_board.md"

SCHEMA_VERSION = "three_track_metric_preflight_board_v1"
TRACKS = ("text_namu_v2_1", "xlsx_business_structured", "pdf_business_ocr_mm")
PROTECTED_SOURCE_GUARDRAILS = (
    "official_denominator_registry_mutation",
    "official_denominator_registry_changed",
    "official_denominator_registry_opened",
    "gold_registry_mutation",
    "official_denominator_opened",
    "official_denominator_opened_or_frozen",
    "promotion_evidence_created",
    "production_namespace_mutated",
    "production_vector_index_mutated",
    "production_vector_written",
    "candidate_artifact_mutated",
    "immutable_baseline_mutated",
    "model_assisted_outputs_promoted_to_gold",
    "answer_generation_run",
    "pdf_answer_generation_denominator_opened",
    "pdf_answer_generation_opened",
    "pdf_content_file_lanes_aggregated",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    board = run_board(
        text_policy_packet=Path(args.text_policy_packet),
        xlsx_answer_report=Path(args.xlsx_answer_report),
        pdf_readiness_report=Path(args.pdf_readiness_report),
        pdf_answer_report=Path(args.pdf_answer_report),
        human_audit_packet=Path(args.human_audit_packet),
        applied_decisions=Path(args.applied_decisions),
        denominator_diff_preview=Path(args.denominator_diff_preview),
        metric_input_config=Path(args.metric_input_config),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        cross_track_averages_requested=args.cross_track_averages_requested,
    )
    print(
        json.dumps(
            {
                "status": board["status"],
                "report": board["artifact_paths"]["report_json"],
                "official_metric_input_rows_by_track": board["official_metric_input_rows_by_track"],
                "cross_track_averages_computed": board["cross_track_averages_computed"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if board["status"].startswith("DIAGNOSTIC_PREFLIGHT_") else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-policy-packet", default=str(DEFAULT_TEXT_POLICY_PACKET))
    parser.add_argument("--xlsx-answer-report", default=str(DEFAULT_XLSX_ANSWER_REPORT))
    parser.add_argument("--pdf-readiness-report", default=str(DEFAULT_PDF_READINESS_REPORT))
    parser.add_argument("--pdf-answer-report", default=str(DEFAULT_PDF_ANSWER_REPORT))
    parser.add_argument("--human-audit-packet", default=str(DEFAULT_HUMAN_AUDIT_PACKET_V2))
    parser.add_argument("--applied-decisions", default=str(DEFAULT_APPLIED_DECISIONS))
    parser.add_argument("--denominator-diff-preview", default=str(DEFAULT_DENOMINATOR_DIFF_PREVIEW))
    parser.add_argument("--metric-input-config", default=str(DEFAULT_METRIC_INPUT_CONFIG))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--cross-track-averages-requested", action="store_true")
    return parser.parse_args(argv)


def run_board(
    *,
    text_policy_packet: Path,
    xlsx_answer_report: Path,
    pdf_readiness_report: Path,
    pdf_answer_report: Path | None = None,
    human_audit_packet: Path | None = None,
    applied_decisions: Path | None = None,
    denominator_diff_preview: Path | None = None,
    metric_input_config: Path | None = None,
    output_report: Path,
    output_md: Path,
    cross_track_averages_requested: bool = False,
) -> dict[str, Any]:
    board = build_board(
        text_policy_packet=text_policy_packet,
        xlsx_answer_report=xlsx_answer_report,
        pdf_readiness_report=pdf_readiness_report,
        pdf_answer_report=pdf_answer_report,
        human_audit_packet=human_audit_packet,
        applied_decisions=applied_decisions,
        denominator_diff_preview=denominator_diff_preview,
        metric_input_config=metric_input_config,
        cross_track_averages_requested=cross_track_averages_requested,
    )
    board["artifact_paths"]["report_json"] = repo_relative(output_report)
    board["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, board)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(board), encoding="utf-8")
    return board


def build_board(
    *,
    text_policy_packet: Path,
    xlsx_answer_report: Path,
    pdf_readiness_report: Path,
    pdf_answer_report: Path | None = None,
    human_audit_packet: Path | None = None,
    applied_decisions: Path | None = None,
    denominator_diff_preview: Path | None = None,
    metric_input_config: Path | None = None,
    cross_track_averages_requested: bool = False,
) -> dict[str, Any]:
    text = read_json(text_policy_packet)
    xlsx = read_json(xlsx_answer_report)
    pdf = read_json(pdf_readiness_report)
    pdf_answer = read_json(pdf_answer_report) if pdf_answer_report is not None and pdf_answer_report.exists() else {}
    human_audit = read_json(human_audit_packet) if human_audit_packet is not None and human_audit_packet.exists() else {}
    applied = read_json(applied_decisions) if applied_decisions is not None and applied_decisions.exists() else {}
    denominator_preview = (
        read_json(denominator_diff_preview)
        if denominator_diff_preview is not None and denominator_diff_preview.exists()
        else {}
    )
    metric_config = read_json(metric_input_config) if metric_input_config is not None and metric_input_config.exists() else {}
    tracks = {
        "text_namu_v2_1": text_track(text, text_policy_packet),
        "xlsx_business_structured": xlsx_track(xlsx, xlsx_answer_report),
        "pdf_business_ocr_mm": pdf_track(
            pdf,
            pdf_readiness_report,
            pdf_answer=pdf_answer,
            pdf_answer_path=pdf_answer_report,
        ),
    }
    source_guardrails = source_guardrail_summary(text=text, xlsx=xlsx, pdf=pdf, pdf_answer=pdf_answer)
    errors = validation_errors(tracks, text=text, xlsx=xlsx, pdf=pdf, pdf_answer=pdf_answer)
    if cross_track_averages_requested:
        errors.append("cross-track averages are not allowed for this diagnostic board")
    errors.extend(human_audit_guardrail_errors(human_audit))
    errors.extend(candidate_transition_guardrail_errors(applied, denominator_preview, metric_config))
    source_official_rows_by_track = {
        track: int(payload.get("official_metric_input_rows") or 0)
        for track, payload in tracks.items()
    }
    official_rows_by_track = dict(source_official_rows_by_track)
    registry_backed_official_rows_by_track: dict[str, int] = {}
    if metric_input_config_registry_backed(metric_config):
        registry_backed_official_rows_by_track = {
            track: int_value(value)
            for track, value in nested_mapping(metric_config, "official_metric_input_rows_by_track").items()
        }
        official_rows_by_track = dict(registry_backed_official_rows_by_track)
    blocker_status = {
        "xlsx_leakage_blocked": xlsx_leakage_blocked(tracks["xlsx_business_structured"]),
        "pdf_evidence_readiness_blocked": pdf_evidence_readiness_blocked(tracks["pdf_business_ocr_mm"]),
        "pdf_answer_citation_blocked": pdf_answer_citation_blocked(tracks["pdf_business_ocr_mm"]),
        "official_question_gold_incomplete": official_question_gold_incomplete(human_audit),
        "human_audit_completed": human_audit_completed(human_audit),
        "applied_decisions_ready": applied_decisions_ready(applied),
        "denominator_diff_preview_ready": denominator_diff_preview_ready(denominator_preview),
        "metric_input_config_ready": metric_input_config_ready(metric_config),
        "metric_input_config_registry_backed": metric_input_config_registry_backed(metric_config),
    }
    status = board_status(blocker_status)
    if errors:
        status = "FAILED_GUARDRAIL"
    board = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "three_track_metric_preflight_board",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "tracks": tracks,
        "official_metric_input_rows_by_track": official_rows_by_track,
        "official_metric_input_rows_total": sum(official_rows_by_track.values()),
        "official_metric_input_rows_scope": (
            "registry_backed_question_gold_input_rows_not_metric_execution"
            if registry_backed_official_rows_by_track
            else "source_diagnostic_report_rows"
        ),
        "source_report_official_metric_input_rows_by_track": source_official_rows_by_track,
        "source_report_official_metric_input_rows_total": sum(source_official_rows_by_track.values()),
        "registry_backed_official_metric_input_rows_by_track": registry_backed_official_rows_by_track,
        "registry_backed_official_metric_input_rows_total": sum(registry_backed_official_rows_by_track.values()),
        "cross_track_averages_computed": False,
        "blocker_status": blocker_status,
        "official_question_gold_status": official_question_gold_status(
            human_audit,
            applied,
            denominator_preview,
            metric_config,
        ),
        "official_metric_setup_status": official_metric_setup_status(applied, denominator_preview, metric_config),
        "route_fallback_label_status": {
            "route_labels": "diagnostic_only",
            "fallback_labels": "diagnostic_only",
            "official_route_metric_opened": False,
            "official_fallback_metric_opened": False,
        },
        "guardrails": {
            "official_metric_input_rows_remain_zero": all(value == 0 for value in source_official_rows_by_track.values()),
            "official_metric_input_rows_remain_zero_scope": "source_diagnostic_reports_only",
            "source_report_official_metric_input_rows_remain_zero": all(
                value == 0 for value in source_official_rows_by_track.values()
            ),
            "official_metric_input_rows_registry_backed": metric_input_config_registry_backed(metric_config),
            "registry_backed_official_metric_input_rows_present": bool(registry_backed_official_rows_by_track),
            "official_denominator_registry_mutation": source_guardrails["official_denominator_registry_mutation"],
            "official_denominator_registry_opened": source_guardrails["official_denominator_registry_opened"],
            "gold_registry_mutation": source_guardrails["gold_registry_mutation"],
            "candidate_artifact_mutation": source_guardrails["candidate_artifact_mutation"],
            "immutable_baseline_mutation": source_guardrails["immutable_baseline_mutation"],
            "production_namespace_vector_index_mutation": source_guardrails[
                "production_namespace_vector_index_mutation"
            ],
            "production_vector_index_mutation": source_guardrails["production_vector_index_mutation"],
            "production_vector_written": source_guardrails["production_vector_written"],
            "model_assisted_outputs_promoted_to_gold": source_guardrails[
                "model_assisted_outputs_promoted_to_gold"
            ],
            "cross_track_averages_computed": False,
            "route_fallback_labels_diagnostic_only": True,
        },
        "artifact_paths": {
            "text_policy_packet": repo_relative(text_policy_packet),
            "xlsx_answer_report": repo_relative(xlsx_answer_report),
            "pdf_readiness_report": repo_relative(pdf_readiness_report),
            "pdf_answer_report": repo_relative(pdf_answer_report) if pdf_answer_report is not None else "",
            "human_audit_packet": repo_relative(human_audit_packet) if human_audit_packet is not None else "",
            "applied_decisions": repo_relative(applied_decisions) if applied_decisions is not None else "",
            "denominator_diff_preview": repo_relative(denominator_diff_preview)
            if denominator_diff_preview is not None
            else "",
            "metric_input_config": repo_relative(metric_input_config) if metric_input_config is not None else "",
            "report_json": "",
            "report_md": "",
        },
        "validation": {
            "ok": not errors,
            "errors": errors,
        },
        "remaining_blockers": remaining_blockers(tracks, blocker_status),
    }
    return board


def text_track(payload: Mapping[str, Any], path: Path) -> dict[str, Any]:
    metrics = nested_mapping(payload, "diagnostic_metric_preview")
    return {
        "source_report": repo_relative(path),
        "status": "FROZEN_DIAGNOSTIC_V2_1",
        "diagnostic_status": "FROZEN_DIAGNOSTIC_V2_1",
        "source_policy_packet_role": "frozen_source_packet_provenance",
        "answer_citation_status": "frozen_diagnostic_v2_1",
        "official_metric_input_rows": int(metrics.get("official_metric_input_rows") or 0),
        "promotion_evidence": False,
        "clean_pass_rows": nested_int(metrics, "strict_clean_answer_preview", "numerator"),
        "cleanup_rows": nested_int(payload, "row_groups", "cleanup_rows", "row_count"),
        "rewrite_unresolved_rows": nested_int(payload, "row_groups", "unresolved_rows", "row_count"),
        "citation_fully_supported_rows": nested_int(metrics, "citation_supported_preview", "numerator"),
        "policy_packet_status": "frozen_source_packet_not_current_preflight_readiness",
    }


def xlsx_track(payload: Mapping[str, Any], path: Path) -> dict[str, Any]:
    preview = nested_mapping(payload, "diagnostic_metric_preview")
    counts = nested_mapping(payload, "counts")
    leakage = nested_mapping(payload, "leakage_reprobe")
    leakage_status = clean(payload.get("leakage_raw_status") or preview.get("leakage_status") or leakage.get("status"))
    return {
        "source_report": repo_relative(path),
        "status": clean(payload.get("status")),
        "diagnostic_status": "blocked_by_leakage_reprobe" if leakage_status != "PASS" else "ready",
        "strict_silver_rows": int(payload.get("strict_silver_rows") or counts.get("input_strict_silver_rows") or 0),
        "generated_answer_rows": int(
            preview.get("generated_answer_rows") or payload.get("input_rows") or counts.get("generated_review_input_rows") or 0
        ),
        "pre_leakage_support_pass_rows": int(
            preview.get("pre_leakage_support_pass_rows")
            or preview.get("answer_citation_clean_pass_rows")
            or min(
                int(preview.get("citation_fully_supported_rows") or counts.get("answer_claim_supported_rows") or 0),
                int(preview.get("citation_locator_valid_rows") or counts.get("citation_locator_resolved_rows") or 0),
            )
            or 0
        ),
        "ready_rows": int(preview.get("clean_pass_rows") or 0),
        "clean_pass_rows": int(preview.get("clean_pass_rows") or 0),
        "cleanup_rows": int(preview.get("cleanup_rows") or 0),
        "rewrite_unresolved_rows": int(preview.get("rewrite_unresolved_rows") or 0),
        "citation_fully_supported_rows": int(
            preview.get("citation_fully_supported_rows") or counts.get("answer_claim_supported_rows") or 0
        ),
        "citation_locator_valid_rows": int(
            preview.get("citation_locator_valid_rows") or counts.get("citation_locator_resolved_rows") or 0
        ),
        "leakage_count": int(
            payload.get("leakage_raw_total")
            or preview.get("leakage_count")
            or leakage.get("surface_leakage_count")
            or 0
        ),
        "leakage_status": leakage_status,
        "metric_preview_status": clean(payload.get("metric_preview_status") or preview.get("status")),
        "official_metric_input_rows": int(
            payload.get("official_metric_input_rows") or preview.get("official_metric_input_rows") or 0
        ),
        "promotion_evidence": bool(payload.get("promotion_evidence", False)),
    }


def pdf_track(
    payload: Mapping[str, Any],
    path: Path,
    *,
    pdf_answer: Mapping[str, Any] | None = None,
    pdf_answer_path: Path | None = None,
) -> dict[str, Any]:
    counts = nested_mapping(payload, "counts")
    rerun = nested_mapping(payload, "strict_gate_rerun")
    answer = pdf_answer if isinstance(pdf_answer, Mapping) else {}
    source_official_rows = int(payload.get("official_metric_input_rows") or counts.get("official_metric_input_rows") or 0)
    answer_official_rows = int(answer.get("official_metric_input_rows") or 0)
    answer_denominator_rows = int(counts.get("pdf_answer_generation_denominator") or 0)
    return {
        "source_report": repo_relative(path),
        "answer_citation_report": repo_relative(pdf_answer_path) if pdf_answer_path is not None else "",
        "status": clean(payload.get("status")),
        "diagnostic_status": clean(payload.get("status")),
        "answer_citation_status": clean(answer.get("status") or "NOT_GENERATED"),
        "input_rows": int(payload.get("input_rows") or counts.get("input_rows") or 0),
        "rows_with_complete_page_bbox_region": int(
            payload.get("complete_page_bbox_region_count") or counts.get("rows_with_complete_page_bbox_region") or 0
        ),
        "rows_with_matched_text": int(payload.get("matched_text_count") or counts.get("rows_with_matched_text") or 0),
        "rows_with_nearby_paragraphs": int(
            payload.get("nearby_paragraph_count") or counts.get("rows_with_nearby_paragraphs") or 0
        ),
        "rows_with_ocr_confidence_or_native_text_na": int(
            payload.get("OCR_confidence_available_count")
            or payload.get("native_text_available_count")
            or counts.get("rows_with_ocr_confidence_or_native_text_na")
            or 0
        ),
        "rows_with_citation_locator": int(
            payload.get("citation_locator_complete_count") or counts.get("rows_with_citation_locator") or 0
        ),
        "search_unit_id_available_count": int(payload.get("search_unit_id_available_count") or 0),
        "parser_source_metadata_available_count": int(payload.get("parser_source_metadata_available_count") or 0),
        "rows_blocked_by_missing_layout": int(
            payload.get("blocked_by_missing_layout_count") or counts.get("rows_blocked_by_missing_layout") or 0
        ),
        "rows_blocked_by_missing_page_bbox_region": int(payload.get("blocked_by_missing_page_bbox_region_count") or 0),
        "rows_blocked_by_missing_context_metadata": int(payload.get("blocked_by_missing_context_metadata_count") or 0),
        "rows_blocked_by_missing_layout_or_context_metadata": int(
            payload.get("blocked_by_missing_layout_or_context_metadata_count")
            or payload.get("blocked_by_missing_layout_count")
            or counts.get("rows_blocked_by_missing_layout")
            or 0
        ),
        "rows_blocked_by_missing_source_unit": int(payload.get("blocked_by_missing_source_unit_count") or 0),
        "rows_blocked_by_file_identity_ambiguity": int(
            payload.get("file_identity_ambiguous_count") or counts.get("rows_blocked_by_file_identity_ambiguity") or 0
        ),
        "strict_gate_readiness_count": int(
            payload.get("strict_ready_rows") or counts.get("strict_gate_readiness_count") or 0
        ),
        "generated_strict_rows_if_rerun": int(
            payload.get("generated_strict_silver_rows") or counts.get("generated_strict_rows_if_rerun") or 0
        ),
        "strict_gate_rerun_performed": rerun.get("rerun_performed") is True,
        "strict_gate_rerun_eligible": rerun.get("eligible") is True,
        "answer_denominator_rows": answer_denominator_rows,
        "answer_generation_run": payload.get("answer_generation_run") is True,
        "answer_generated_rows": int(answer.get("generated_answer_rows") or 0),
        "answer_clean_pass_rows": int(answer.get("clean_pass_rows") or 0),
        "answer_cleanup_rows": int(answer.get("cleanup_rows") or 0),
        "answer_unresolved_rows": int(answer.get("unresolved_rows") or 0),
        "answer_lane_policy_blocked_rows": int(answer.get("lane_policy_blocked_rows") or 0),
        "answer_support_pass_count": int(answer.get("answer_support_pass_count") or 0),
        "answer_citation_locator_valid_count": int(answer.get("citation_locator_valid_count") or 0),
        "official_metric_input_rows": source_official_rows + answer_official_rows,
        "promotion_evidence": bool(payload.get("promotion_evidence", False) or answer.get("promotion_evidence", False)),
    }


def validation_errors(
    tracks: Mapping[str, Mapping[str, Any]],
    *,
    text: Mapping[str, Any],
    xlsx: Mapping[str, Any],
    pdf: Mapping[str, Any],
    pdf_answer: Mapping[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    for track, payload in tracks.items():
        if int(payload.get("official_metric_input_rows") or 0) != 0:
            errors.append(f"{track} official_metric_input_rows must remain 0")
        if payload.get("promotion_evidence") is True:
            errors.append(f"{track} promotion_evidence must remain false")
    errors.extend(source_guardrail_errors("text_namu_v2_1", text))
    errors.extend(source_guardrail_errors("xlsx_business_structured", xlsx))
    errors.extend(source_guardrail_errors("pdf_business_ocr_mm", pdf))
    pdf_answer = pdf_answer if isinstance(pdf_answer, Mapping) else {}
    if pdf_answer:
        errors.extend(source_guardrail_errors("pdf_business_ocr_mm", pdf_answer))
    if text.get("diagnostic_only") is not True:
        errors.append("text_namu_v2_1 policy packet must be diagnostic_only=true")
    if xlsx.get("diagnostic_only") is not True:
        errors.append("xlsx_business_structured report must be diagnostic_only=true")
    if pdf.get("diagnostic_only") is not True:
        errors.append("pdf_business_ocr_mm report must be diagnostic_only=true")
    if pdf.get("answer_generation_run") is True:
        errors.append("pdf_business_ocr_mm answer generation must remain closed")
    if nested_int(pdf, "counts", "pdf_answer_generation_denominator") != 0:
        errors.append("pdf_business_ocr_mm answer denominator must remain 0")
    if pdf_answer and pdf_answer.get("diagnostic_only") is not True:
        errors.append("pdf_business_ocr_mm answer/citation packet must be diagnostic_only=true")
    if pdf_answer and pdf_answer.get("pdf_answer_generation_denominator_opened") is True:
        errors.append("pdf_business_ocr_mm answer denominator must remain 0")
    lane_separation = nested_mapping(pdf, "lane_separation")
    if lane_separation.get("content_and_file_identity_aggregated") is True:
        errors.append("pdf content and file identity lanes must not be aggregated")
    return errors


def pdf_evidence_readiness_blocked(payload: Mapping[str, Any]) -> bool:
    strict_ready = int(payload.get("strict_gate_readiness_count") or 0)
    input_rows = int(payload.get("input_rows") or 0)
    ready_status = clean(payload.get("status")) in {
        "READY_FOR_STRICT_GATE_RERUN",
        "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN",
    }
    if not ready_status:
        return True
    return not (
        input_rows > 0
        and strict_ready == input_rows
        and payload.get("strict_gate_rerun_eligible") is True
    )


def xlsx_leakage_blocked(payload: Mapping[str, Any]) -> bool:
    return clean(payload.get("leakage_status")) != "PASS" or int(payload.get("leakage_count") or 0) != 0


def pdf_answer_citation_blocked(payload: Mapping[str, Any]) -> bool:
    if pdf_evidence_readiness_blocked(payload):
        return False
    return not pdf_answer_citation_ready(payload)


def pdf_answer_citation_ready(payload: Mapping[str, Any]) -> bool:
    return (
        clean(payload.get("answer_citation_status")) == "DIAGNOSTIC_POLICY_PACKET_READY"
        and int(payload.get("answer_generated_rows") or 0) == 7
        and int(payload.get("answer_clean_pass_rows") or 0) == 7
        and int(payload.get("answer_cleanup_rows") or 0) == 0
        and int(payload.get("answer_unresolved_rows") or 0) == 0
        and int(payload.get("answer_lane_policy_blocked_rows") or 0) == 0
        and int(payload.get("answer_support_pass_count") or 0) == 7
        and int(payload.get("answer_citation_locator_valid_count") or 0) == 7
    )


def board_status(blocker_status: Mapping[str, bool]) -> str:
    xlsx_blocked = blocker_status.get("xlsx_leakage_blocked") is True
    pdf_blocked = blocker_status.get("pdf_evidence_readiness_blocked") is True
    pdf_answer_blocked = blocker_status.get("pdf_answer_citation_blocked") is True
    question_gold_incomplete = blocker_status.get("official_question_gold_incomplete") is True
    if xlsx_blocked or pdf_blocked:
        return "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    if pdf_answer_blocked:
        return "DIAGNOSTIC_PREFLIGHT_BLOCKED_BY_PDF_ANSWER_CITATION"
    if question_gold_incomplete:
        return "DIAGNOSTIC_PREFLIGHT_BLOCKED_BY_OFFICIAL_QUESTION_GOLD"
    return "DIAGNOSTIC_PREFLIGHT_READY"


def official_question_gold_status(
    human_audit: Mapping[str, Any],
    applied_decisions: Mapping[str, Any] | None = None,
    denominator_diff_preview: Mapping[str, Any] | None = None,
    metric_input_config: Mapping[str, Any] | None = None,
) -> str:
    if not human_audit:
        return "NOT_CHECKED"
    summary = nested_mapping(human_audit, "summary")
    pdf_candidates = int(summary.get("pdf_generated_candidates") or 0)
    xlsx_candidates = int(summary.get("xlsx_generated_candidates") or 0)
    if clean(human_audit.get("status")) != "HUMAN_AUDIT_PACKET_V2_READY":
        return "OFFICIAL_QUESTION_GOLD_INCOMPLETE"
    if pdf_candidates == 0 or xlsx_candidates == 0:
        return "OFFICIAL_QUESTION_GOLD_INCOMPLETE"
    if human_audit_completed(human_audit):
        applied = applied_decisions if isinstance(applied_decisions, Mapping) else {}
        preview = denominator_diff_preview if isinstance(denominator_diff_preview, Mapping) else {}
        config = metric_input_config if isinstance(metric_input_config, Mapping) else {}
        if metric_input_config_ready(config):
            if metric_input_config_registry_backed(config):
                return "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED"
            return "OFFICIAL_METRIC_INPUT_CONFIG_READY_PENDING_REGISTRY_APPLICATION"
        if denominator_diff_preview_ready(preview):
            return "OFFICIAL_DENOMINATOR_DIFF_PREVIEW_READY_PENDING_METRIC_CONFIG"
        if applied_decisions_ready(applied):
            return "HUMAN_AUDIT_APPLIED_PENDING_DENOMINATOR_DIFF_PREVIEW"
        return "HUMAN_AUDIT_COMPLETED_PENDING_REPORT_ONLY_DECISION_APPLICATION"
    return "PENDING_HUMAN_AUDIT_OF_V2_PACKET"


def official_question_gold_incomplete(human_audit: Mapping[str, Any]) -> bool:
    return official_question_gold_status(human_audit) == "OFFICIAL_QUESTION_GOLD_INCOMPLETE"


def human_audit_completed(human_audit: Mapping[str, Any]) -> bool:
    return human_label_validation(human_audit)["completed"]


def applied_decisions_ready(applied: Mapping[str, Any]) -> bool:
    return (
        clean(applied.get("status")) == "HUMAN_AUDIT_V2_APPLIED_DECISIONS_READY"
        and nested_mapping(applied, "validation").get("ok") is True
        and int_value(applied.get("official_metric_input_rows")) == 0
        and applied.get("promotion_evidence") is not True
    )


def denominator_diff_preview_ready(preview: Mapping[str, Any]) -> bool:
    return (
        clean(preview.get("status")) == "OFFICIAL_DENOMINATOR_CANDIDATE_DIFF_PREVIEW_READY"
        and clean(preview.get("registry_diff_status")) == "PREVIEW_ONLY_NO_MUTATION"
        and nested_mapping(preview, "validation").get("ok") is True
        and int_value(preview.get("official_metric_input_rows")) == 0
        and nested_mapping(preview, "guardrails").get("official_denominator_registry_changed") is not True
        and preview.get("promotion_evidence") is not True
    )


def metric_input_config_ready(config: Mapping[str, Any]) -> bool:
    status = clean(config.get("status"))
    if status == "OFFICIAL_METRIC_INPUT_CONFIG_READY_PENDING_REGISTRY_APPLICATION":
        return (
            nested_mapping(config, "validation").get("ok") is True
            and int_value(config.get("official_metric_input_rows")) == 0
            and config.get("official_metric_execution_started") is False
            and config.get("metric_execution_allowed") is False
            and config.get("promotion_evidence") is not True
        )
    if status == "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED":
        return metric_input_config_registry_backed(config)
    return False


def metric_input_config_registry_backed(config: Mapping[str, Any]) -> bool:
    return (
        clean(config.get("status")) == "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED"
        and nested_mapping(config, "validation").get("ok") is True
        and int_value(config.get("official_metric_input_rows")) > 0
        and config.get("official_metric_execution_started") is False
        and config.get("metric_execution_allowed") is True
        and config.get("registry_application_status") == "APPLIED"
        and config.get("promotion_evidence") is not True
    )


def official_metric_setup_status(
    applied: Mapping[str, Any],
    preview: Mapping[str, Any],
    config: Mapping[str, Any],
) -> str:
    if metric_input_config_ready(config):
        if metric_input_config_registry_backed(config):
            return "REGISTRY_BACKED_CONFIG_READY_NOT_EXECUTED"
        return "CONFIG_READY_PENDING_REGISTRY_APPLICATION"
    if denominator_diff_preview_ready(preview):
        return "DENOMINATOR_DIFF_PREVIEW_READY_PENDING_CONFIG"
    if applied_decisions_ready(applied):
        return "APPLIED_DECISIONS_READY_PENDING_DENOMINATOR_DIFF_PREVIEW"
    return "NOT_READY"


def human_audit_guardrail_errors(human_audit: Mapping[str, Any]) -> list[str]:
    if not human_audit:
        return []
    errors: list[str] = []
    summary = nested_mapping(human_audit, "summary")
    label_validation = human_label_validation(human_audit)
    errors.extend(label_validation["errors"])
    if (human_audit.get("human_audit_completed") is True or summary.get("human_audit_completed") is True) and not label_validation["completed"]:
        errors.append("human_audit_packet completion flag must match row-level valid labels")
    if human_audit.get("official_metric") is True:
        errors.append("human_audit_packet official_metric must remain false")
    if int(human_audit.get("official_metric_input_rows") or 0) != 0 or nested_int(summary, "official_metric_input_rows") != 0:
        errors.append("human_audit_packet official_metric_input_rows must remain 0")
    if human_audit.get("promotion_evidence") is True or summary.get("promotion_evidence") is True:
        errors.append("human_audit_packet promotion_evidence must remain false")
    guardrails = nested_mapping(human_audit, "guardrails")
    for key in (
        "local_llm_outputs_promoted_to_gold",
        "official_denominator_registry_opened",
        "official_denominator_registry_mutation",
        "gold_registry_mutation",
        "candidate_artifact_mutation",
        "immutable_baseline_mutation",
        "production_namespace_vector_index_mutation",
        "production_vector_index_mutation",
        "production_vector_written",
        "tuning_run_started",
    ):
        if guardrails.get(key) is True:
            errors.append(f"human_audit_packet guardrail violation: {key}=true")
    return errors


def candidate_transition_guardrail_errors(
    applied: Mapping[str, Any],
    preview: Mapping[str, Any],
    config: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if applied and not applied_decisions_ready(applied):
        errors.append("applied decisions artifact is present but not ready")
    if preview and not denominator_diff_preview_ready(preview):
        errors.append("denominator diff preview artifact is present but not ready")
    if config and not metric_input_config_ready(config):
        errors.append("metric input config artifact is present but not ready")
    for name, payload in (
        ("applied_decisions", applied),
        ("denominator_diff_preview", preview),
        ("metric_input_config", config),
    ):
        if not payload:
            continue
        if int_value(payload.get("official_metric_input_rows")) != 0 and not (
            name == "metric_input_config" and metric_input_config_registry_backed(payload)
        ):
            errors.append(f"{name} official_metric_input_rows must remain 0")
        if payload.get("promotion_evidence") is True:
            errors.append(f"{name} promotion_evidence must remain false")
        if payload.get("tuning_run_started") is True:
            errors.append(f"{name} tuning_run_started must remain false")
        guardrails = nested_mapping(payload, "guardrails")
        for key in (
            "official_denominator_registry_mutation",
            "official_denominator_registry_opened",
            "official_denominator_opened",
            "official_metric_executed",
            "gold_registry_mutation",
            "candidate_artifact_mutation",
            "immutable_baseline_mutation",
            "production_namespace_vector_index_mutation",
            "production_vector_written",
            "tuning_run_started",
        ):
            if payload.get(key) is True or guardrails.get(key) is True:
                if name == "metric_input_config" and metric_input_config_registry_backed(payload) and key in {
                    "official_denominator_registry_mutation",
                    "official_denominator_registry_opened",
                }:
                    continue
                errors.append(f"{name} guardrail violation: {key}=true")
    return errors


def human_label_validation(human_audit: Mapping[str, Any]) -> dict[str, Any]:
    rows = [row for row in human_audit.get("actionable_rows") or [] if isinstance(row, Mapping)]
    if not rows:
        return {"completed": False, "errors": [], "counts": {}}
    errors: list[str] = []
    counts: Counter[str] = Counter()
    missing: list[str] = []
    invalid: list[str] = []
    for row in rows:
        qid = clean(row.get("query_id") or row.get("row_id"))
        label = clean(row.get("human_label"))
        allowed = row.get("allowed_decision_values") if isinstance(row.get("allowed_decision_values"), list) else []
        allowed_values = {clean(value) for value in allowed}
        if not label:
            missing.append(qid)
            continue
        counts[label] += 1
        if label not in allowed_values:
            invalid.append(qid)
    if missing:
        errors.append(f"human_audit_packet rows missing human_label: {', '.join(missing)}")
    if invalid:
        errors.append(f"human_audit_packet rows have invalid human_label: {', '.join(invalid)}")
    summary = nested_mapping(human_audit, "summary")
    expected_labeled = int_value(summary.get("human_labeled_rows"))
    expected_unlabeled = int_value(summary.get("human_unlabeled_rows"))
    if "human_labeled_rows" in summary and expected_labeled != sum(counts.values()):
        errors.append("human_audit_packet human_labeled_rows summary mismatch")
    if "human_unlabeled_rows" in summary and expected_unlabeled != len(missing):
        errors.append("human_audit_packet human_unlabeled_rows summary mismatch")
    expected_counts = human_audit.get("human_audit_label_counts")
    if isinstance(expected_counts, Mapping):
        normalized_expected = {clean(key): int_value(value) for key, value in expected_counts.items()}
        if normalized_expected != dict(sorted(counts.items())):
            errors.append("human_audit_packet human_audit_label_counts mismatch")
    return {"completed": bool(rows) and not missing and not invalid, "errors": errors, "counts": dict(sorted(counts.items()))}


def source_guardrail_errors(track: str, payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("official_metric") is True:
        errors.append(f"{track} source report must keep official_metric=false")
    validation = payload.get("validation") if isinstance(payload.get("validation"), Mapping) else {}
    if validation.get("ok") is False:
        source_errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
        source_errors = [
            source_error
            for source_error in source_errors
            if "leakage" not in clean(source_error).lower()
        ]
        if source_errors:
            for source_error in source_errors:
                errors.append(f"{track} source validation failed: {source_error}")
        elif clean(payload.get("status")) == "FAILED_GUARDRAIL":
            errors.append(f"{track} source validation failed")
    guardrails = payload.get("guardrails") if isinstance(payload.get("guardrails"), Mapping) else {}
    source_guardrails = payload.get("source_guardrails") if isinstance(payload.get("source_guardrails"), Mapping) else {}
    for key in PROTECTED_SOURCE_GUARDRAILS:
        if payload.get(key) is True or guardrails.get(key) is True or source_guardrails.get(key) is True:
            errors.append(f"{track} source guardrail violation: {key}=true")
    return errors


def source_guardrail_summary(
    *,
    text: Mapping[str, Any],
    xlsx: Mapping[str, Any],
    pdf: Mapping[str, Any],
    pdf_answer: Mapping[str, Any] | None = None,
) -> dict[str, bool]:
    source_payloads = (text, xlsx, pdf, pdf_answer if isinstance(pdf_answer, Mapping) else {})

    def any_guardrail(*keys: str) -> bool:
        for payload in source_payloads:
            guardrails = payload.get("guardrails") if isinstance(payload.get("guardrails"), Mapping) else {}
            source_guardrails = (
                payload.get("source_guardrails") if isinstance(payload.get("source_guardrails"), Mapping) else {}
            )
            for key in keys:
                if payload.get(key) is True or guardrails.get(key) is True or source_guardrails.get(key) is True:
                    return True
        return False

    return {
        "official_denominator_registry_mutation": any_guardrail(
            "official_denominator_registry_mutation",
            "official_denominator_registry_changed",
        ),
        "official_denominator_registry_opened": any_guardrail(
            "official_denominator_registry_opened",
            "official_denominator_opened",
            "official_denominator_opened_or_frozen",
        ),
        "gold_registry_mutation": any_guardrail("gold_registry_mutation"),
        "candidate_artifact_mutation": any_guardrail("candidate_artifact_mutation", "candidate_artifact_mutated"),
        "immutable_baseline_mutation": any_guardrail("immutable_baseline_mutation", "immutable_baseline_mutated"),
        "production_namespace_vector_index_mutation": any_guardrail(
            "production_namespace_vector_index_mutation",
            "production_namespace_mutated",
            "production_vector_index_mutated",
        ),
        "production_vector_index_mutation": any_guardrail("production_vector_index_mutation", "production_vector_index_mutated"),
        "production_vector_written": any_guardrail("production_vector_written"),
        "model_assisted_outputs_promoted_to_gold": any_guardrail("model_assisted_outputs_promoted_to_gold"),
    }


def remaining_blockers(tracks: Mapping[str, Mapping[str, Any]], blocker_status: Mapping[str, bool]) -> list[str]:
    blockers: list[str] = []
    if tracks["xlsx_business_structured"].get("leakage_status") != "PASS":
        blockers.append("XLSX hidden/excluded leakage reprobe must pass before clean preflight.")
    if int(tracks["pdf_business_ocr_mm"].get("strict_gate_readiness_count") or 0) == 0:
        blockers.append("PDF layout/SearchUnit/OCR/citation metadata must be enriched before strict gate rerun.")
    if pdf_answer_citation_blocked(tracks["pdf_business_ocr_mm"]):
        blockers.append("PDF answer/citation diagnostic packet is missing or not ready.")
    if blocker_status.get("official_question_gold_incomplete") is True:
        blockers.append("Official question-gold candidates are incomplete pending v2 human audit; evidence readiness remains complete.")
    if blocker_status.get("metric_input_config_registry_backed") is True:
        blockers.append("Official metric input config is registry-backed; official metric execution is the next gated step.")
    elif blocker_status.get("metric_input_config_ready") is True:
        blockers.append("Official metric input config is ready, but registry application and metric execution still require explicit approval.")
    elif blocker_status.get("denominator_diff_preview_ready") is True:
        blockers.append("Denominator diff preview is ready; metric input config must be regenerated before registry application.")
    elif blocker_status.get("applied_decisions_ready") is True:
        blockers.append("Human audit decisions are applied; denominator diff preview must be generated before registry application.")
    elif blocker_status.get("human_audit_completed") is True:
        blockers.append("Human audit decisions must be applied report-only before any official metric candidate can open.")
    else:
        blockers.append("Human audit is still required before any official metric candidate can open.")
    return blockers


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(board: Mapping[str, Any]) -> str:
    text = board["tracks"]["text_namu_v2_1"]
    xlsx = board["tracks"]["xlsx_business_structured"]
    pdf = board["tracks"]["pdf_business_ocr_mm"]
    lines = [
        "# Three-Track Metric Preflight Board",
        "",
        f"- Status: `{board['status']}`",
        "- Scope: source diagnostic report rows remain closed; registry-backed question-gold input rows are ready, and the official metric is not executed.",
        f"- Cross-track averages computed: `{str(board['cross_track_averages_computed']).lower()}`",
        f"- XLSX leakage blocker: `{str(board['blocker_status']['xlsx_leakage_blocked']).lower()}`",
        f"- PDF evidence readiness blocker: `{str(board['blocker_status']['pdf_evidence_readiness_blocked']).lower()}`",
        f"- PDF answer/citation blocker: `{str(board['blocker_status']['pdf_answer_citation_blocked']).lower()}`",
        f"- Official question-gold status: `{board['official_question_gold_status']}`",
        f"- Official metric setup status: `{board.get('official_metric_setup_status')}`",
        f"- Official metric input rows scope: `{board.get('official_metric_input_rows_scope')}`",
        f"- Official metric input rows total: `{board.get('official_metric_input_rows_total')}`",
        f"- Source-report official input rows total: `{board.get('source_report_official_metric_input_rows_total')}`",
        f"- Registry-backed official input rows total: `{board.get('registry_backed_official_metric_input_rows_total')}`",
        f"- Official question-gold incomplete: `{str(board['blocker_status']['official_question_gold_incomplete']).lower()}`",
        f"- Human audit completed: `{str(board['blocker_status']['human_audit_completed']).lower()}`",
        f"- Applied decisions ready: `{str(board['blocker_status'].get('applied_decisions_ready')).lower()}`",
        f"- Denominator diff preview ready: `{str(board['blocker_status'].get('denominator_diff_preview_ready')).lower()}`",
        f"- Metric input config ready: `{str(board['blocker_status'].get('metric_input_config_ready')).lower()}`",
        f"- Metric input config registry-backed: `{str(board['blocker_status'].get('metric_input_config_registry_backed')).lower()}`",
        "",
        "## Tracks",
        "",
        "| Track | Status | Rows | Final clean/strict ready | Pre-leakage/support | Blockers | Official rows |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        "| TEXT/Namu V2.1 | "
        f"`{text['diagnostic_status']}` | `{text['clean_pass_rows'] + text['cleanup_rows'] + text['rewrite_unresolved_rows']}` | "
        f"`{text['clean_pass_rows']}` | `{text['citation_fully_supported_rows']}` | `{text['rewrite_unresolved_rows']}` | "
        f"`{text['official_metric_input_rows']}` |",
        "| XLSX | "
        f"`{xlsx['diagnostic_status']}` | `{xlsx['generated_answer_rows']}` | "
        f"`{xlsx['ready_rows']}` | `{xlsx['pre_leakage_support_pass_rows']}` | `{xlsx['leakage_count']}` | "
        f"`{xlsx['official_metric_input_rows']}` |",
        "| PDF | "
        f"`{pdf['diagnostic_status']}` / `{pdf['answer_citation_status']}` | `{pdf['input_rows']}` | `{pdf['strict_gate_readiness_count']}` | `{pdf['answer_clean_pass_rows']}` | "
        f"`{pdf['rows_blocked_by_missing_layout_or_context_metadata']}` | `{pdf['official_metric_input_rows']}` |",
        "",
        "## Guardrails",
        "",
    ]
    for key, value in board["guardrails"].items():
        lines.append(f"- `{key}`: `{json.dumps(value, ensure_ascii=False)}`")
    lines.extend(["", "## Remaining Blockers", ""])
    lines.extend(f"- {blocker}" for blocker in board["remaining_blockers"])
    return "\n".join(lines) + "\n"


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    value: Any = payload
    for key in keys:
        if not isinstance(value, Mapping):
            return {}
        value = value.get(key)
    return value if isinstance(value, Mapping) else {}


def nested_int(payload: Mapping[str, Any], *keys: str) -> int:
    value: Any = payload
    for key in keys:
        if not isinstance(value, Mapping):
            return 0
        value = value.get(key)
    return int_value(value)


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
