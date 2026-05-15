"""Generate a report-only tuning dry-run plan and transition checklist.

This script creates planning artifacts only. It does not run tuning, compute
official metrics, open official denominators, write vectors, mutate candidate
artifacts, mutate immutable baselines, or select production winners.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_BOARD = REPORT_DIR / "three_track_metric_preflight_board.json"
DEFAULT_READINESS_PLAN = REPORT_DIR / "hyperparameter_tuning_readiness_plan.json"
DEFAULT_TEXT_PACKET = REVIEW_DIR / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json"
DEFAULT_XLSX_PACKET = REPORT_DIR / "rag_xlsx_answer_citation_policy_review_packet_v1.json"
DEFAULT_PDF_METADATA = REPORT_DIR / "pdf_evidence_metadata_enrichment_report.json"
DEFAULT_PDF_LAYOUT = REPORT_DIR / "pdf_layout_gap_closure_report.json"
DEFAULT_PDF_REPAIR = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_PDF_ANSWER_PACKET = REPORT_DIR / "rag_pdf_answer_citation_policy_review_packet_v1.json"
DEFAULT_PROGRESS_DOC = REPO_ROOT / "docs" / "rag-ingestion-progress.md"
DEFAULT_HUMAN_AUDIT_PACKET = REVIEW_DIR / "rag_human_audit_packet_v1.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "report_only_tuning_dry_run_plan_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "report_only_tuning_dry_run_plan_v1.md"
DEFAULT_CHECKLIST_JSON = REPORT_DIR / "official_metric_transition_readiness_checklist_v1.json"
DEFAULT_CHECKLIST_MD = REPORT_DIR / "official_metric_transition_readiness_checklist_v1.md"

SCHEMA_VERSION = "report_only_tuning_dry_run_plan_v1"
CHECKLIST_SCHEMA_VERSION = "official_metric_transition_readiness_checklist_v1"

TRACKS = ("text_namu_v2_1", "xlsx_business_structured", "pdf_business_ocr_mm")

ALLOWED_REPORT_ONLY_PARAMETERS = {
    "text_namu_v2_1": [
        "rewrite_formatter_mode",
        "citation_support_threshold_report_only",
        "cleanup_bucket_policy_report_only",
        "verifier_strictness_report_only",
    ],
    "xlsx_business_structured": [
        "structured_evidence_field_subset",
        "citation_locator_required_fields",
        "leakage_probe_surface_policy_report_only",
        "table_context_window_report_only",
    ],
    "pdf_business_ocr_mm": [
        "citation_locator_required_fields",
        "nearby_paragraph_window_report_only",
        "native_text_vs_ocr_trust_policy_report_only",
        "bbox_region_strictness_report_only",
        "stable_identity_policy_variant_report_only",
    ],
    "route_orchestration_diagnostic_only": [
        "route_confidence_threshold_report_only",
        "fallback_policy_report_only",
        "multi_route_diagnostic_policy_report_only",
    ],
}

BLOCKED_PARAMETERS = [
    "official_metric_threshold",
    "gold_label_rewrite",
    "expected_answer_rewrite",
    "official_denominator_inclusion",
    "production_route_weight",
    "production_index_weight",
    "hidden_or_excluded_row_inclusion",
    "filename_only_identity_acceptance",
    "content_file_identity_lane_merge",
    "answer_denominator_open",
    "vector_namespace_selection_for_production",
    "broad_candidate_indexing",
    "candidate_artifact_promotion",
    "immutable_baseline_update",
]

BOARD_PROTECTED_GUARDRAILS = (
    "official_denominator_registry_mutation",
    "official_denominator_registry_opened",
    "gold_registry_mutation",
    "candidate_artifact_mutation",
    "immutable_baseline_mutation",
    "production_namespace_vector_index_mutation",
    "production_vector_index_mutation",
    "production_vector_written",
    "model_assisted_outputs_promoted_to_gold",
    "cross_track_averages_computed",
)

OUTPUT_METRIC_POLICY = {
    "metric_role": "diagnostic_preview_only",
    "official_metric": False,
    "promotion_evidence": False,
    "winner_selection": "forbidden",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_plan(
        board_path=Path(args.board),
        readiness_plan_path=Path(args.readiness_plan),
        text_packet_path=Path(args.text_packet),
        xlsx_packet_path=Path(args.xlsx_packet),
        pdf_metadata_report_path=Path(args.pdf_metadata_report),
        pdf_layout_report_path=Path(args.pdf_layout_report),
        pdf_repair_report_path=Path(args.pdf_repair_report),
        pdf_answer_packet_path=Path(args.pdf_answer_packet),
        progress_doc_path=Path(args.progress_doc),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        checklist_report=Path(args.checklist_report),
        checklist_md=Path(args.checklist_md),
        human_audit_packet_path=Path(args.human_audit_packet),
    )
    plan = result["plan"]
    print(
        json.dumps(
            {
                "status": plan["status"],
                "report": plan["artifact_paths"]["report_json"],
                "checklist": result["checklist"]["artifact_paths"]["report_json"],
                "tuning_run_started": plan["tuning_run_started"],
                "official_metric_input_rows_by_track": plan["official_metric_input_rows_by_track"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if plan["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", default=str(DEFAULT_BOARD))
    parser.add_argument("--readiness-plan", default=str(DEFAULT_READINESS_PLAN))
    parser.add_argument("--text-packet", default=str(DEFAULT_TEXT_PACKET))
    parser.add_argument("--xlsx-packet", default=str(DEFAULT_XLSX_PACKET))
    parser.add_argument("--pdf-metadata-report", default=str(DEFAULT_PDF_METADATA))
    parser.add_argument("--pdf-layout-report", default=str(DEFAULT_PDF_LAYOUT))
    parser.add_argument("--pdf-repair-report", default=str(DEFAULT_PDF_REPAIR))
    parser.add_argument("--pdf-answer-packet", default=str(DEFAULT_PDF_ANSWER_PACKET))
    parser.add_argument("--progress-doc", default=str(DEFAULT_PROGRESS_DOC))
    parser.add_argument("--human-audit-packet", default=str(DEFAULT_HUMAN_AUDIT_PACKET))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--checklist-report", default=str(DEFAULT_CHECKLIST_JSON))
    parser.add_argument("--checklist-md", default=str(DEFAULT_CHECKLIST_MD))
    return parser.parse_args(argv)


def run_plan(
    *,
    board_path: Path,
    readiness_plan_path: Path,
    text_packet_path: Path,
    xlsx_packet_path: Path,
    pdf_metadata_report_path: Path,
    pdf_layout_report_path: Path,
    pdf_repair_report_path: Path,
    pdf_answer_packet_path: Path,
    progress_doc_path: Path,
    output_report: Path,
    output_md: Path,
    checklist_report: Path,
    checklist_md: Path,
    human_audit_packet_path: Path,
) -> dict[str, dict[str, Any]]:
    payloads = {
        "three_track_metric_preflight_board": read_json(board_path),
        "hyperparameter_tuning_readiness_plan": read_json(readiness_plan_path),
        "text_policy_packet": read_json(text_packet_path),
        "xlsx_answer_citation_policy_packet": read_json(xlsx_packet_path),
        "pdf_evidence_metadata_enrichment": read_json(pdf_metadata_report_path),
        "pdf_layout_gap_closure": read_json(pdf_layout_report_path),
        "pdf_evidence_readiness_repair": read_json(pdf_repair_report_path),
        "pdf_answer_citation_policy_packet": read_json(pdf_answer_packet_path),
    }
    paths = {
        "three_track_metric_preflight_board": board_path,
        "hyperparameter_tuning_readiness_plan": readiness_plan_path,
        "text_policy_packet": text_packet_path,
        "xlsx_answer_citation_policy_packet": xlsx_packet_path,
        "pdf_evidence_metadata_enrichment": pdf_metadata_report_path,
        "pdf_layout_gap_closure": pdf_layout_report_path,
        "pdf_evidence_readiness_repair": pdf_repair_report_path,
        "pdf_answer_citation_policy_packet": pdf_answer_packet_path,
        "progress_doc": progress_doc_path,
    }
    freshness = canonical_freshness(paths, payloads)
    plan = build_plan(payloads=payloads, paths=paths, freshness=freshness, human_audit_packet_path=human_audit_packet_path)
    plan["artifact_paths"]["report_json"] = repo_relative(output_report)
    plan["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, plan)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(plan), encoding="utf-8")

    checklist = build_transition_checklist(plan=plan, human_audit_packet_path=human_audit_packet_path)
    checklist["artifact_paths"]["report_json"] = repo_relative(checklist_report)
    checklist["artifact_paths"]["report_md"] = repo_relative(checklist_md)
    write_json(checklist_report, checklist)
    checklist_md.parent.mkdir(parents=True, exist_ok=True)
    checklist_md.write_text(render_checklist_markdown(checklist), encoding="utf-8")
    return {"plan": plan, "checklist": checklist}


def build_plan(
    *,
    payloads: Mapping[str, Mapping[str, Any]],
    paths: Mapping[str, Path],
    freshness: Mapping[str, Any],
    human_audit_packet_path: Path,
) -> dict[str, Any]:
    board = payloads["three_track_metric_preflight_board"]
    readiness = payloads["hyperparameter_tuning_readiness_plan"]
    text = payloads["text_policy_packet"]
    xlsx = payloads["xlsx_answer_citation_policy_packet"]
    pdf_metadata = payloads["pdf_evidence_metadata_enrichment"]
    pdf_layout = payloads["pdf_layout_gap_closure"]
    pdf_repair = payloads["pdf_evidence_readiness_repair"]
    pdf_answer = payloads["pdf_answer_citation_policy_packet"]

    official_rows_by_track = official_rows_by_track_from(board, text, xlsx, pdf_repair, pdf_answer)
    pdf_answer_exists = paths["pdf_answer_citation_policy_packet"].exists()
    pdf_answer_ready = pdf_answer_packet_ready(pdf_answer) if pdf_answer_exists else False
    pdf_board_answer_ready = (
        clean(nested_mapping(board, "tracks", "pdf_business_ocr_mm").get("answer_citation_status"))
        == "DIAGNOSTIC_POLICY_PACKET_READY"
    )
    xlsx_leakage_status = clean(
        xlsx.get("leakage_raw_status")
        or nested_mapping(xlsx, "diagnostic_metric_preview").get("leakage_status")
    )
    xlsx_leakage_count = int_value(
        xlsx.get("leakage_raw_total")
        or nested_mapping(xlsx, "diagnostic_metric_preview").get("leakage_count")
    )
    pdf_strict_rows = int_value(pdf_repair.get("strict_ready_rows") or nested_mapping(pdf_repair, "counts").get("strict_gate_readiness_count"))
    lane_merge = content_file_lane_merge_detected(pdf_repair, pdf_answer)
    hidden_excluded_candidate_count = 0
    hidden_excluded_leakage_detected = xlsx_leakage_status != "PASS" or xlsx_leakage_count != 0

    errors: list[str] = []
    if freshness["missing_required_artifacts"]:
        errors.extend(f"MISSING_CANONICAL_ARTIFACT:{item}" for item in freshness["missing_required_artifacts"])
    if clean(board.get("status")) != "DIAGNOSTIC_PREFLIGHT_READY":
        errors.append("BOARD_STATUS_NOT_DIAGNOSTIC_PREFLIGHT_READY")
    if nested_mapping(board, "validation").get("ok") is not True:
        errors.append("BOARD_VALIDATION_NOT_OK")
    if nested_mapping(board, "guardrails").get("official_metric_input_rows_remain_zero") is not True:
        errors.append("BOARD_OFFICIAL_METRIC_INPUT_ROWS_NOT_CONFIRMED_ZERO")
    for key in BOARD_PROTECTED_GUARDRAILS:
        if nested_mapping(board, "guardrails").get(key) is True:
            errors.append(f"BOARD_PROTECTED_GUARDRAIL_TRUE:{key}")
    if board.get("cross_track_averages_computed") is True:
        errors.append("BOARD_CROSS_TRACK_AVERAGES_COMPUTED")
    if not pdf_answer_exists and pdf_board_answer_ready:
        errors.append("PDF_ANSWER_CITATION_PACKET_MISSING_FAIL_CLOSED")
    if pdf_answer_exists and not pdf_answer_ready:
        errors.append("PDF_ANSWER_CITATION_PACKET_NOT_READY_FAIL_CLOSED")
    if any(value != 0 for value in official_rows_by_track.values()):
        errors.append("OFFICIAL_METRIC_INPUT_ROWS_GT_0")
    if int_value(readiness.get("official_metric_input_rows")) != 0:
        errors.append("READINESS_PLAN_OFFICIAL_METRIC_INPUT_ROWS_GT_0")
    if readiness.get("tuning_run_started") is True:
        errors.append("TUNING_RUN_ALREADY_STARTED")
    if readiness.get("official_metrics_closed") is not True:
        errors.append("OFFICIAL_METRICS_NOT_CLOSED")
    if readiness.get("cross_track_average_optimization_allowed") is True:
        errors.append("CROSS_TRACK_AVERAGE_OPTIMIZATION_ALLOWED")
    if xlsx_leakage_status != "PASS":
        errors.append("XLSX_LEAKAGE_STATUS_NOT_PASS")
    if xlsx_leakage_count != 0:
        errors.append("HIDDEN_EXCLUDED_XLSX_LEAKAGE_DETECTED")
    if pdf_strict_rows < 7:
        errors.append("PDF_EVIDENCE_STRICT_READY_ROWS_LT_7")
    if lane_merge:
        errors.append("PDF_CONTENT_FILE_IDENTITY_LANE_MERGE_DETECTED")
    if hidden_excluded_candidate_count:
        errors.append("HIDDEN_EXCLUDED_XLSX_ROWS_IN_CANDIDATES")
    if freshness["stale_current_markers"]:
        errors.extend(f"STALE_CURRENT_MARKER:{item}" for item in freshness["stale_current_markers"])

    if any(error.startswith("MISSING_CANONICAL_ARTIFACT") or error == "PDF_ANSWER_CITATION_PACKET_MISSING_FAIL_CLOSED" for error in errors):
        status = "FAIL_CLOSED_CANONICAL_FRESHNESS"
    elif errors:
        status = "FAIL_CLOSED_GUARDRAIL"
    else:
        status = "REPORT_ONLY_DRY_RUN_PLAN_READY"

    plan = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "report_only_tuning_dry_run_plan",
        "diagnostic_only": True,
        "report_only": True,
        "promotion_evidence": False,
        "tuning_run_started": False,
        "official_metrics_closed": True,
        "official_metric_input_rows_by_track": official_rows_by_track,
        "official_metric_input_rows": sum(official_rows_by_track.values()),
        "cross_track_average_optimization_allowed": False,
        "cross_track_averages_computed": False,
        "human_audit_required_before_official_metric_open": True,
        "canonical_freshness": freshness,
        "track_dev_set_policy": track_dev_set_policy(
            text=text,
            xlsx=xlsx,
            pdf_repair=pdf_repair,
            pdf_answer=pdf_answer,
            pdf_answer_exists=pdf_answer_exists,
        ),
        "parameter_matrix": {
            "allowed_report_only": ALLOWED_REPORT_ONLY_PARAMETERS,
            "blocked_parameters": BLOCKED_PARAMETERS,
        },
        "dry_run_evaluation_matrix": dry_run_evaluation_matrix(
            text=text,
            xlsx=xlsx,
            pdf_metadata=pdf_metadata,
            pdf_layout=pdf_layout,
            pdf_repair=pdf_repair,
            pdf_answer=pdf_answer,
            official_rows_by_track=official_rows_by_track,
        ),
        "split_policy": {
            "final_holdout_opened": False,
            "sealed_holdout_consumed": False,
            "cross_track_average_computed": False,
            "track_level_diagnostic_previews_allowed": True,
            "parameter_winner_selected": False,
            "diagnostic_ranking_label_required_if_ranked": True,
        },
        "stop_conditions": {
            "official_metric_rows_gt_0": any(value != 0 for value in official_rows_by_track.values()),
            "official_denominator_registry_diff_exists": "verified_by_external_git_diff_checks",
            "pdf_answer_packet_missing_but_pdf_answer_ready": (not pdf_answer_exists and pdf_board_answer_ready),
            "pdf_answer_packet_not_ready": pdf_answer_exists and not pdf_answer_ready,
            "xlsx_leakage_status_not_pass": xlsx_leakage_status != "PASS",
            "pdf_evidence_strict_ready_rows_lt_7": pdf_strict_rows < 7,
            "content_file_identity_lane_merge_detected": lane_merge,
            "hidden_excluded_xlsx_leakage_detected": hidden_excluded_leakage_detected,
            "stale_artifact_selected_over_latest_canonical": bool(freshness["stale_current_markers"]),
        },
        "artifact_paths": {
            "board": repo_relative(paths["three_track_metric_preflight_board"]),
            "readiness_plan": repo_relative(paths["hyperparameter_tuning_readiness_plan"]),
            "text_policy_packet": repo_relative(paths["text_policy_packet"]),
            "xlsx_policy_packet": repo_relative(paths["xlsx_answer_citation_policy_packet"]),
            "pdf_metadata_report": repo_relative(paths["pdf_evidence_metadata_enrichment"]),
            "pdf_layout_report": repo_relative(paths["pdf_layout_gap_closure"]),
            "pdf_repair_report": repo_relative(paths["pdf_evidence_readiness_repair"]),
            "pdf_answer_packet": repo_relative(paths["pdf_answer_citation_policy_packet"]),
            "human_audit_packet": repo_relative(human_audit_packet_path),
            "report_json": "",
            "report_md": "",
        },
        "validation": {"ok": not errors, "errors": errors},
    }
    return plan


def canonical_freshness(paths: Mapping[str, Path], payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    artifacts = []
    missing: list[str] = []
    for role, path in paths.items():
        if role == "progress_doc":
            exists = path.exists()
            if not exists:
                missing.append(role)
            artifacts.append(
                {
                    "role": role,
                    "path": repo_relative(path),
                    "exists": exists,
                    "generated_at": None,
                    "sha256": sha256_file(path) if exists else None,
                    "status": "doc_present" if exists else "missing",
                }
            )
            continue
        payload = payloads.get(role, {})
        exists = path.exists()
        if not exists:
            missing.append(role)
        artifacts.append(
            {
                "role": role,
                "path": repo_relative(path),
                "exists": exists,
                "generated_at": payload.get("generated_at") if isinstance(payload, Mapping) else None,
                "sha256": sha256_file(path) if exists else None,
                "status": clean(payload.get("status")) if isinstance(payload, Mapping) else "missing",
            }
        )
    return {
        "artifacts": artifacts,
        "missing_required_artifacts": missing,
        "stale_current_markers": progress_doc_stale_markers(paths["progress_doc"]),
        "selection_policy": "exact canonical repo-local paths; do not select stale historical blocker artifacts",
    }


def track_dev_set_policy(
    *,
    text: Mapping[str, Any],
    xlsx: Mapping[str, Any],
    pdf_repair: Mapping[str, Any],
    pdf_answer: Mapping[str, Any],
    pdf_answer_exists: bool,
) -> dict[str, Any]:
    text_preview = nested_mapping(text, "diagnostic_metric_preview")
    text_total = int_value(text.get("row_count")) or int_value(
        nested_mapping(text_preview, "strict_clean_answer_preview").get("denominator")
    )
    xlsx_preview = nested_mapping(xlsx, "diagnostic_metric_preview")
    pdf_answer_ready = pdf_answer_exists and pdf_answer_packet_ready(pdf_answer)
    return {
        "text_namu_v2_1": {
            "source": "frozen_packet_current_diagnostic_state",
            "input_rows": text_total,
            "eligible_diagnostic_dev_rows": text_total,
            "dev_set_role": "diagnostic_dev_not_final_holdout",
            "official_denominator": "closed",
            "cleanup_rows": nested_int(text, "row_groups", "cleanup_rows", "row_count"),
            "unresolved_rows": nested_int(text, "row_groups", "unresolved_rows", "row_count") or int_value(text_preview.get("unresolved_count")),
        },
        "xlsx_business_structured": {
            "source": "strict_silver_answer_citation_clean_rows",
            "input_rows": int_value(xlsx.get("strict_silver_rows")) or int_value(xlsx_preview.get("generated_answer_rows")),
            "eligible_diagnostic_dev_rows": int_value(xlsx_preview.get("clean_pass_rows")),
            "dev_set_role": "strict_silver_diagnostic_dev_not_official_holdout",
            "official_denominator": "closed",
            "hidden_excluded_pending_rows_excluded": True,
        },
        "pdf_business_ocr_mm": {
            "source": "strict_ready_answer_citation_packet_if_present",
            "input_rows": int_value(pdf_repair.get("input_rows")),
            "eligible_diagnostic_dev_rows": int_value(pdf_answer.get("clean_pass_rows")) if pdf_answer_ready else 0,
            "answer_citation_dry_run_eligibility": "eligible" if pdf_answer_ready else "blocked",
            "official_denominator": "closed",
            "file_identity_rows_excluded_from_content_answer_evidence": True,
            "filename_only_identity_rows_excluded": True,
        },
    }


def dry_run_evaluation_matrix(
    *,
    text: Mapping[str, Any],
    xlsx: Mapping[str, Any],
    pdf_metadata: Mapping[str, Any],
    pdf_layout: Mapping[str, Any],
    pdf_repair: Mapping[str, Any],
    pdf_answer: Mapping[str, Any],
    official_rows_by_track: Mapping[str, int],
) -> dict[str, Any]:
    text_preview = nested_mapping(text, "diagnostic_metric_preview")
    xlsx_preview = nested_mapping(xlsx, "diagnostic_metric_preview")
    return {
        "text_namu_v2_1": {
            "input_rows": int_value(text.get("row_count")) or int_value(nested_mapping(text_preview, "strict_clean_answer_preview").get("denominator")),
            "eligible_diagnostic_dev_rows": int_value(text.get("row_count")) or int_value(nested_mapping(text_preview, "strict_clean_answer_preview").get("denominator")),
            "excluded_rows_by_reason": {"official_denominator_closed": int_value(text.get("row_count")) or 0},
            "cleanup_unresolved_rows": {
                "cleanup": nested_int(text, "row_groups", "cleanup_rows", "row_count"),
                "unresolved": nested_int(text, "row_groups", "unresolved_rows", "row_count") or int_value(text_preview.get("unresolved_count")),
            },
            "support_checks": {"citation_supported_rows": nested_int(text_preview, "citation_supported_preview", "numerator")},
            "citation_locator_checks": {"citation_supported_preview_only": True},
            "leakage_lane_checks": {},
            "allowed_knobs": ALLOWED_REPORT_ONLY_PARAMETERS["text_namu_v2_1"],
            "blocked_knobs": BLOCKED_PARAMETERS,
            "output_metrics": OUTPUT_METRIC_POLICY,
            "official_metric_input_rows": official_rows_by_track["text_namu_v2_1"],
        },
        "xlsx_business_structured": {
            "input_rows": int_value(xlsx.get("strict_silver_rows")) or int_value(xlsx_preview.get("generated_answer_rows")),
            "eligible_diagnostic_dev_rows": int_value(xlsx_preview.get("clean_pass_rows")),
            "excluded_rows_by_reason": {
                "hidden_negative_rows": int_value(xlsx.get("hidden_negative_rows")),
                "normalized_excluded_rows": int_value(xlsx.get("normalized_excluded_rows")),
                "pending_excluded_rows": int_value(xlsx.get("pending_excluded_rows")),
            },
            "cleanup_unresolved_rows": {
                "cleanup": int_value(xlsx_preview.get("cleanup_rows")),
                "unresolved": int_value(xlsx_preview.get("rewrite_unresolved_rows")),
            },
            "support_checks": {"citation_fully_supported_rows": int_value(xlsx_preview.get("citation_fully_supported_rows"))},
            "citation_locator_checks": {"citation_locator_valid_rows": int_value(xlsx_preview.get("citation_locator_valid_rows"))},
            "leakage_lane_checks": {
                "leakage_status": clean(xlsx.get("leakage_raw_status") or xlsx_preview.get("leakage_status")),
                "leakage_count": int_value(xlsx.get("leakage_raw_total") or xlsx_preview.get("leakage_count")),
                "hidden_excluded_rows_in_candidates": False,
            },
            "allowed_knobs": ALLOWED_REPORT_ONLY_PARAMETERS["xlsx_business_structured"],
            "blocked_knobs": BLOCKED_PARAMETERS,
            "output_metrics": OUTPUT_METRIC_POLICY,
            "official_metric_input_rows": official_rows_by_track["xlsx_business_structured"],
        },
        "pdf_business_ocr_mm": {
            "input_rows": int_value(pdf_repair.get("input_rows")),
            "eligible_diagnostic_dev_rows": int_value(pdf_answer.get("clean_pass_rows")),
            "excluded_rows_by_reason": {
                "diagnostic_only_fallback_rows": int_value(pdf_repair.get("diagnostic_only_fallback_rows")),
                "file_identity_rows_excluded_from_content": int_value(pdf_repair.get("file_identity_ambiguous_count")),
                "filename_only_identity_rows_excluded": int_value(pdf_answer.get("filename_only_identity_accepted")),
            },
            "cleanup_unresolved_rows": {
                "cleanup": int_value(pdf_answer.get("cleanup_rows")),
                "unresolved": int_value(pdf_answer.get("unresolved_rows")),
            },
            "support_checks": {
                "metadata_after_strict_ready_rows": nested_int(pdf_metadata, "after_counts", "strict_ready_rows"),
                "layout_strict_ready_rows_after": int_value(pdf_layout.get("strict_ready_rows_after")),
                "answer_support_pass_count": int_value(pdf_answer.get("answer_support_pass_count")),
            },
            "citation_locator_checks": {
                "repair_citation_locator_complete_count": int_value(pdf_repair.get("citation_locator_complete_count")),
                "answer_citation_locator_valid_count": int_value(pdf_answer.get("citation_locator_valid_count")),
            },
            "lane_checks": {
                "content_file_identity_lane_merge_detected": content_file_lane_merge_detected(pdf_repair, pdf_answer),
                "filename_only_identity_accepted": bool_value(pdf_answer.get("filename_only_identity_accepted")),
                "content_lane": "pdf_content_evidence",
                "file_identity_lane": "pdf_file_identity_blocked_by_stable_identity_required",
            },
            "allowed_knobs": ALLOWED_REPORT_ONLY_PARAMETERS["pdf_business_ocr_mm"],
            "blocked_knobs": BLOCKED_PARAMETERS,
            "output_metrics": OUTPUT_METRIC_POLICY,
            "official_metric_input_rows": official_rows_by_track["pdf_business_ocr_mm"],
        },
    }


def build_transition_checklist(*, plan: Mapping[str, Any], human_audit_packet_path: Path) -> dict[str, Any]:
    official_rows = int_value(plan.get("official_metric_input_rows"))
    checklist = {
        "schema_version": CHECKLIST_SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "OFFICIAL_TRANSITION_BLOCKED_PENDING_HUMAN_AUDIT",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_denominator_registry_opened": False,
        "official_metric_input_rows": official_rows,
        "human_audit_packet_generated": human_audit_packet_path.exists(),
        "human_audit_completed": False,
        "official_transition_blocked_until_user_decisions_applied": True,
        "production_mutation": False,
        "cross_track_average": False,
        "diagnostic_artifacts_not_promotion_evidence": True,
        "next_allowed_steps_after_user_audit": [
            "apply_human_audit_decisions_report_only",
            "generate_official_denominator_candidate_diff_preview",
            "require_explicit_user_approval_before_registry_mutation",
        ],
        "artifact_paths": {
            "plan": plan.get("artifact_paths", {}).get("report_json", ""),
            "human_audit_packet": repo_relative(human_audit_packet_path),
            "report_json": "",
            "report_md": "",
        },
        "validation": {
            "ok": official_rows == 0 and plan.get("tuning_run_started") is False,
            "errors": [] if official_rows == 0 else ["official_metric_input_rows must remain 0"],
        },
    }
    return checklist


def official_rows_by_track_from(
    board: Mapping[str, Any],
    text: Mapping[str, Any],
    xlsx: Mapping[str, Any],
    pdf_repair: Mapping[str, Any],
    pdf_answer: Mapping[str, Any],
) -> dict[str, int]:
    rows = {
        "text_namu_v2_1": 0,
        "xlsx_business_structured": 0,
        "pdf_business_ocr_mm": 0,
    }
    board_rows = nested_mapping(board, "official_metric_input_rows_by_track")
    for track in TRACKS:
        rows[track] = int_value(board_rows.get(track))
    rows["text_namu_v2_1"] = max(
        rows["text_namu_v2_1"],
        int_value(nested_mapping(text, "diagnostic_metric_preview").get("official_metric_input_rows")),
        int_value(text.get("official_metric_input_rows")),
    )
    rows["xlsx_business_structured"] = max(
        rows["xlsx_business_structured"],
        int_value(xlsx.get("official_metric_input_rows")),
        int_value(nested_mapping(xlsx, "diagnostic_metric_preview").get("official_metric_input_rows")),
    )
    rows["pdf_business_ocr_mm"] = max(
        rows["pdf_business_ocr_mm"],
        int_value(pdf_repair.get("official_metric_input_rows")),
        int_value(pdf_answer.get("official_metric_input_rows")),
    )
    return rows


def content_file_lane_merge_detected(pdf_repair: Mapping[str, Any], pdf_answer: Mapping[str, Any]) -> bool:
    repair_lane = nested_mapping(pdf_repair, "lane_separation")
    answer_guardrails = nested_mapping(pdf_answer, "guardrails")
    return any(
        value is True
        for value in (
            repair_lane.get("content_and_file_identity_aggregated"),
            pdf_answer.get("content_file_identity_lane_merge"),
            answer_guardrails.get("content_file_identity_lane_merge"),
        )
    )


def pdf_answer_packet_ready(payload: Mapping[str, Any]) -> bool:
    return (
        clean(payload.get("status")) == "DIAGNOSTIC_POLICY_PACKET_READY"
        and int_value(payload.get("input_rows")) == 7
        and int_value(payload.get("strict_ready_rows")) == 7
        and int_value(payload.get("generated_answer_rows")) == 7
        and int_value(payload.get("clean_pass_rows")) == 7
        and int_value(payload.get("answer_support_pass_count")) == 7
        and int_value(payload.get("citation_locator_valid_count")) == 7
        and int_value(payload.get("cleanup_rows")) == 0
        and int_value(payload.get("unresolved_rows")) == 0
        and int_value(payload.get("lane_policy_blocked_rows")) == 0
    )


def progress_doc_stale_markers(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    current = text.split("## 2026-05-13", 1)[0]
    markers: list[str] = []
    lowered = current.lower()
    if "xlsx" in lowered and "leakage" in lowered and "`fail`" in lowered:
        markers.append("progress_doc_current_xlsx_leakage_fail")
    if "pdf" in lowered and "strict ready rows `0`" in lowered:
        markers.append("progress_doc_current_pdf_strict_ready_rows_0")
    return markers


def render_markdown(plan: Mapping[str, Any]) -> str:
    lines = [
        "# Report-Only Tuning Dry-Run Plan v1",
        "",
        f"- Status: `{plan['status']}`",
        "- Scope: planning only; no tuning run, official metric, denominator opening, or production mutation.",
        f"- Tuning run started: `{str(plan['tuning_run_started']).lower()}`",
        f"- Official metric input rows: `{plan['official_metric_input_rows']}`",
        f"- Cross-track average optimization allowed: `{str(plan['cross_track_average_optimization_allowed']).lower()}`",
        "",
        "## Track Dev Sets",
        "",
    ]
    for track, policy in plan["track_dev_set_policy"].items():
        lines.extend(
            [
                f"### {track}",
                "",
                f"- input_rows: `{policy['input_rows']}`",
                f"- eligible_diagnostic_dev_rows: `{policy['eligible_diagnostic_dev_rows']}`",
                f"- dev_set_role: `{policy.get('dev_set_role', policy.get('source', ''))}`",
                f"- official_denominator: `{policy['official_denominator']}`",
                "",
            ]
        )
    lines.extend(["## Stop Conditions", ""])
    for key, value in plan["stop_conditions"].items():
        lines.append(f"- `{key}`: `{json.dumps(value, ensure_ascii=False)}`")
    lines.extend(["", "## Validation", ""])
    if plan["validation"]["errors"]:
        lines.extend(f"- `{error}`" for error in plan["validation"]["errors"])
    else:
        lines.append("- `ok`")
    return "\n".join(lines) + "\n"


def render_checklist_markdown(checklist: Mapping[str, Any]) -> str:
    lines = [
        "# Official Metric Transition Readiness Checklist v1",
        "",
        f"- Status: `{checklist['status']}`",
        f"- official_denominator_registry_opened: `{str(checklist['official_denominator_registry_opened']).lower()}`",
        f"- official_metric_input_rows: `{checklist['official_metric_input_rows']}`",
        f"- human_audit_packet_generated: `{str(checklist['human_audit_packet_generated']).lower()}`",
        f"- human_audit_completed: `{str(checklist['human_audit_completed']).lower()}`",
        f"- production_mutation: `{str(checklist['production_mutation']).lower()}`",
        f"- cross_track_average: `{str(checklist['cross_track_average']).lower()}`",
        "- Diagnostic artifacts are not promotion evidence.",
        "",
        "## Next Allowed Steps After User Audit",
        "",
    ]
    lines.extend(f"- `{step}`" for step in checklist["next_allowed_steps_after_user_audit"])
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def nested_int(payload: Mapping[str, Any], *keys: str) -> int:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return 0
        current = current.get(key)
    return int_value(current)


def int_value(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def clean(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
