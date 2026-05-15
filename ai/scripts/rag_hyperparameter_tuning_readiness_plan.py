"""Create a report-only hyperparameter tuning readiness plan.

This is scaffolding only. It defines track-specific policy and guardrails for a
future tuning run while keeping official metrics, official denominators,
production indexes, candidate artifacts, and gold registries closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"

DEFAULT_OUTPUT_JSON = REPORT_DIR / "hyperparameter_tuning_readiness_plan.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "hyperparameter_tuning_readiness_plan.md"
DEFAULT_METRIC_BOARD = REPORT_DIR / "three_track_metric_preflight_board.json"

SCHEMA_VERSION = "hyperparameter_tuning_readiness_plan_v1"
PROTECTED_FALSE_GUARDRAILS = (
    "official_denominator_registry_mutation",
    "official_denominator_registry_opened",
    "production_namespace_vector_index_mutation",
    "production_vector_index_mutation",
    "production_vector_written",
    "candidate_artifact_mutation",
    "immutable_baseline_mutation",
    "gold_registry_mutation",
    "model_assisted_outputs_promoted_to_gold",
    "tuning_run_started",
    "cross_track_average_optimization_allowed",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = run_plan(
        metric_board=Path(args.metric_board),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": plan["status"],
                "report": plan["artifact_paths"]["report_json"],
                "tuning_run_started": plan["tuning_run_started"],
                "official_metrics_closed": plan["official_metrics_closed"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if plan["status"] != "FAILED_GUARDRAIL" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metric-board", default=str(DEFAULT_METRIC_BOARD))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_plan(*, output_report: Path, output_md: Path, metric_board: Path | None = DEFAULT_METRIC_BOARD) -> dict[str, Any]:
    metric_board_payload = read_json(metric_board) if metric_board is not None else {}
    plan = build_plan(metric_board_payload=metric_board_payload)
    if metric_board is not None:
        plan["artifact_paths"]["metric_board"] = repo_relative(metric_board)
    plan["artifact_paths"]["report_json"] = repo_relative(output_report)
    plan["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, plan)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(plan), encoding="utf-8")
    return plan


def build_plan(
    *,
    guardrail_overrides: Mapping[str, Any] | None = None,
    metric_board_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    guardrails = base_guardrails()
    if guardrail_overrides:
        guardrails.update(dict(guardrail_overrides))
    board = metric_board_payload if isinstance(metric_board_payload, Mapping) else {}
    board_guardrails = board_derived_guardrails(board)
    guardrails.update(board_guardrails)
    errors = [
        *validate_guardrails(guardrails),
        *metric_board_validation_errors(board),
    ]
    readiness = track_readiness(board)
    technical_blockers = readiness_blockers(readiness)
    blockers = [*technical_blockers, "human_audit_required_before_official_metric_open"]
    status = "REPORT_ONLY_READY"
    if technical_blockers:
        status = "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    if errors:
        status = "FAILED_GUARDRAIL"
    plan = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "hyperparameter_tuning_readiness_plan_report_only",
        "diagnostic_only": True,
        "report_only": True,
        "tuning_run_started": bool(guardrails.get("tuning_run_started")),
        "official_metrics_closed": True,
        "official_metric_input_rows": int(guardrails.get("official_metric_input_rows") or 0),
        "promotion_evidence": False,
        "cross_track_average_optimization_allowed": bool(
            guardrails.get("cross_track_average_optimization_allowed")
        ),
        "current_text_66_rows_policy": "diagnostic_dev_not_final_holdout",
        "optimization_policy": {
            "cross_track_averages": "forbidden",
            "objective_scope": "track_specific_only",
            "official_metric_inputs": "closed_until_human_audit",
            "model_assisted_outputs": "not_gold_not_promotion_evidence",
        },
        "track_policies": track_policies(readiness),
        "readiness_blockers": blockers,
        "technical_readiness_blockers": technical_blockers,
        "official_transition_blockers": ["human_audit_required_before_official_metric_open"],
        "guardrails": guardrails,
        "artifact_paths": {
            "metric_board": "",
            "report_json": "",
            "report_md": "",
        },
        "validation": {
            "ok": not errors,
            "errors": errors,
        },
    }
    return plan


def base_guardrails() -> dict[str, Any]:
    guardrails = {key: False for key in PROTECTED_FALSE_GUARDRAILS}
    guardrails.update(
        {
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "official_metrics_closed": True,
            "no_production_mutation": True,
            "no_gold_registry_mutation": True,
            "no_candidate_artifact_mutation": True,
            "text_66_rows_are_diagnostic_dev": True,
        }
    )
    return guardrails


def track_policies(readiness: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    readiness = readiness or {}
    return {
        "text_namu_v2_1": {
            "readiness_status": readiness.get("text_namu_v2_1", "FROZEN_DIAGNOSTIC_V2_1"),
            "dev_policy": "diagnostic_dev_only",
            "holdout_policy": "not_final_holdout",
            "current_rows_policy": "66_rows_are_diagnostic_dev_not_final_holdout",
            "allowed_parameters": [
                "rewrite_formatter_mode",
                "citation_support_threshold_report_only",
                "cleanup_bucket_policy_report_only",
            ],
            "blocked_parameters": [
                "official_metric_threshold",
                "gold_label_rewrite",
                "production_route_weight",
            ],
        },
        "xlsx_business_structured": {
            "readiness_status": readiness.get("xlsx_business_structured", "REPORT_ONLY_NOT_BLOCKED_DIAGNOSTIC"),
            "dev_policy": "strict_silver_diagnostic_only",
            "holdout_policy": "strict_silver_not_official_holdout",
            "allowed_parameters": [
                "structured_evidence_field_subset",
                "citation_locator_required_fields",
                "leakage_probe_token_policy_report_only",
            ],
            "blocked_parameters": [
                "hidden_or_excluded_row_inclusion",
                "answer_denominator_open",
                "production_index_weight",
            ],
        },
        "pdf_business_ocr_mm": {
            "readiness_status": readiness.get("pdf_business_ocr_mm", "REPORT_ONLY_NOT_BLOCKED_DIAGNOSTIC"),
            "dev_policy": "readiness_artifact_only",
            "holdout_policy": "no_answer_holdout_until_evidence_ready",
            "allowed_parameters": [
                "layout_metadata_completeness_threshold",
                "citation_locator_required_fields",
                "stable_identity_policy_variant_report_only",
            ],
            "blocked_parameters": [
                "answer_generation_prompt",
                "filename_only_identity_acceptance",
                "content_file_identity_lane_merge",
            ],
        },
    }


def board_derived_guardrails(board: Mapping[str, Any]) -> dict[str, Any]:
    rows_by_track = nested_mapping(board, "official_metric_input_rows_by_track")
    official_rows = sum(int_value(value) for value in rows_by_track.values())
    if official_rows == 0:
        tracks = nested_mapping(board, "tracks")
        official_rows = sum(
            int_value(payload.get("official_metric_input_rows"))
            for payload in tracks.values()
            if isinstance(payload, Mapping)
        )
    result: dict[str, Any] = {"official_metric_input_rows": official_rows}
    board_guardrails = nested_mapping(board, "guardrails")
    for key in PROTECTED_FALSE_GUARDRAILS:
        if key in {"tuning_run_started", "cross_track_average_optimization_allowed"}:
            continue
        if board_guardrails.get(key) is True:
            result[key] = True
    return result


def track_readiness(board: Mapping[str, Any]) -> dict[str, str]:
    tracks = nested_mapping(board, "tracks")
    xlsx = tracks.get("xlsx_business_structured") if isinstance(tracks.get("xlsx_business_structured"), Mapping) else {}
    pdf = tracks.get("pdf_business_ocr_mm") if isinstance(tracks.get("pdf_business_ocr_mm"), Mapping) else {}
    blocker_status = nested_mapping(board, "blocker_status")
    xlsx_leakage = clean(xlsx.get("leakage_status"))
    xlsx_leakage_count = int_value(xlsx.get("leakage_count"))
    pdf_strict_ready = int_value(pdf.get("strict_gate_readiness_count"))
    pdf_input_rows = int_value(pdf.get("input_rows"))
    pdf_board_blocked = blocker_status.get("pdf_evidence_readiness_blocked") is True
    pdf_answer_blocked = (
        blocker_status.get("pdf_answer_citation_blocked") is True
        or clean(pdf.get("answer_citation_status")) == "DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LANE_OR_EVIDENCE_GUARD"
    )
    pdf_track_ready = pdf_input_rows > 0 and pdf_strict_ready == pdf_input_rows
    if "strict_gate_rerun_eligible" in pdf:
        pdf_track_ready = pdf_track_ready and pdf.get("strict_gate_rerun_eligible") is True
    pdf_data_blocked = bool(tracks) and not pdf_track_ready
    return {
        "text_namu_v2_1": "FROZEN_DIAGNOSTIC_V2_1",
        "xlsx_business_structured": (
            "REPORT_ONLY_BLOCKED_BY_LEAKAGE"
            if blocker_status.get("xlsx_leakage_blocked") is True
            or (xlsx_leakage and xlsx_leakage != "PASS")
            or xlsx_leakage_count != 0
            else "REPORT_ONLY_NOT_BLOCKED_DIAGNOSTIC"
        ),
        "pdf_business_ocr_mm": (
            "REPORT_ONLY_BLOCKED_BY_ANSWER_CITATION"
            if pdf_answer_blocked
            else
            "REPORT_ONLY_BLOCKED_BY_EVIDENCE_READINESS"
            if pdf_board_blocked or pdf_data_blocked
            else "REPORT_ONLY_NOT_BLOCKED_DIAGNOSTIC"
        ),
    }


def readiness_blockers(readiness: Mapping[str, str]) -> list[str]:
    blockers: list[str] = []
    if readiness.get("xlsx_business_structured") == "REPORT_ONLY_BLOCKED_BY_LEAKAGE":
        blockers.append("xlsx_business_structured leakage_raw_status=FAIL")
    if readiness.get("pdf_business_ocr_mm") == "REPORT_ONLY_BLOCKED_BY_EVIDENCE_READINESS":
        blockers.append("pdf_business_ocr_mm evidence_readiness_blocked")
    if readiness.get("pdf_business_ocr_mm") == "REPORT_ONLY_BLOCKED_BY_ANSWER_CITATION":
        blockers.append("pdf_business_ocr_mm answer_citation_blocked")
    return blockers


def metric_board_validation_errors(board: Mapping[str, Any]) -> list[str]:
    if not board:
        return ["metric board is missing"]
    errors: list[str] = []
    status = clean(board.get("status"))
    if status == "FAILED_GUARDRAIL":
        errors.append("metric board status is FAILED_GUARDRAIL")
    validation = nested_mapping(board, "validation")
    if validation and validation.get("ok") is not True:
        for error in validation.get("errors") or ["unknown"]:
            errors.append(f"metric board validation failed: {error}")
    if board.get("official_metric") is True:
        errors.append("metric board official_metric must remain false")
    if board.get("promotion_evidence") is True:
        errors.append("metric board promotion_evidence must remain false")
    if board.get("cross_track_averages_computed") is True:
        errors.append("metric board cross_track_averages_computed must remain false")
    guardrails = nested_mapping(board, "guardrails")
    for key in (
        "official_metric_input_rows_remain_zero",
        "route_fallback_labels_diagnostic_only",
    ):
        if key in guardrails and guardrails.get(key) is not True:
            errors.append(f"metric board guardrail {key} must remain true")
    for key in (
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
    ):
        if guardrails.get(key) is True:
            errors.append(f"metric board guardrail {key} must remain false")
    return errors


def validate_guardrails(guardrails: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in PROTECTED_FALSE_GUARDRAILS:
        if guardrails.get(key) is True:
            errors.append(f"{key} must remain false")
    if int(guardrails.get("official_metric_input_rows") or 0) != 0:
        errors.append("official_metric_input_rows must remain 0")
    if guardrails.get("promotion_evidence") is not False:
        errors.append("promotion_evidence must remain false")
    if guardrails.get("official_metrics_closed") is not True:
        errors.append("official_metrics_closed must remain true")
    return errors


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def render_markdown(plan: Mapping[str, Any]) -> str:
    lines = [
        "# Hyperparameter Tuning Readiness Plan",
        "",
        f"- Status: `{plan['status']}`",
        f"- Report only: `{str(plan['report_only']).lower()}`",
        f"- Tuning run started: `{str(plan['tuning_run_started']).lower()}`",
        f"- Official metrics closed: `{str(plan['official_metrics_closed']).lower()}`",
        f"- Cross-track average optimization allowed: `{str(plan['cross_track_average_optimization_allowed']).lower()}`",
        f"- TEXT 66-row policy: `{plan['current_text_66_rows_policy']}`",
        "",
        "## Track Policies",
        "",
    ]
    for track, policy in plan["track_policies"].items():
        lines.extend(
            [
                f"### {track}",
                "",
                f"- readiness_status: `{policy['readiness_status']}`",
                f"- dev_policy: `{policy['dev_policy']}`",
                f"- holdout_policy: `{policy['holdout_policy']}`",
                "- allowed_parameters: " + ", ".join(f"`{item}`" for item in policy["allowed_parameters"]),
                "- blocked_parameters: " + ", ".join(f"`{item}`" for item in policy["blocked_parameters"]),
                "",
            ]
        )
    lines.extend(["## Guardrails", ""])
    for key, value in plan["guardrails"].items():
        lines.append(f"- `{key}`: `{json.dumps(value, ensure_ascii=False)}`")
    lines.extend(["", "## Readiness Blockers", ""])
    if plan["readiness_blockers"]:
        for blocker in plan["readiness_blockers"]:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- `none`")
    return "\n".join(lines) + "\n"


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def int_value(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


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
