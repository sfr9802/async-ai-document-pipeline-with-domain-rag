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
    plan = run_plan(output_report=Path(args.output_report), output_md=Path(args.output_md))
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
    return 0 if plan["status"] == "REPORT_ONLY_READY" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_plan(*, output_report: Path, output_md: Path) -> dict[str, Any]:
    plan = build_plan()
    plan["artifact_paths"]["report_json"] = repo_relative(output_report)
    plan["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, plan)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(plan), encoding="utf-8")
    return plan


def build_plan(*, guardrail_overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    guardrails = base_guardrails()
    if guardrail_overrides:
        guardrails.update(dict(guardrail_overrides))
    errors = validate_guardrails(guardrails)
    plan = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "REPORT_ONLY_READY" if not errors else "FAILED_GUARDRAIL",
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
        "track_policies": track_policies(),
        "guardrails": guardrails,
        "artifact_paths": {
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


def track_policies() -> dict[str, dict[str, Any]]:
    return {
        "text_namu_v2_1": {
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
    return "\n".join(lines) + "\n"


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
