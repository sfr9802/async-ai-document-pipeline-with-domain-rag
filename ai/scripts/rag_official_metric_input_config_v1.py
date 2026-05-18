"""Build official metric input configuration for v2 candidates without running metrics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_APPLIED_DECISIONS = REVIEW_DIR / "rag_human_audit_v2_applied_decisions.json"
DEFAULT_DENOMINATOR_DIFF_PREVIEW = REPORT_DIR / "official_denominator_candidate_diff_preview_v1.json"
DEFAULT_REGISTRY_APPLICATION_REPORT = REPORT_DIR / "official_question_gold_v2_registry_application_report.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "metric_input_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "metric_input_v1.md"

SCHEMA_VERSION = "official_metric_input_config_v1"
TRACKS = ("text_namu_v2_1", "xlsx_business_structured", "pdf_business_ocr_mm")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = run_config(
        applied_decisions_path=Path(args.applied_decisions),
        denominator_diff_preview_path=Path(args.denominator_diff_preview),
        registry_application_report_path=Path(args.registry_application_report),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": config["status"],
                "report": config["artifact_paths"]["report_json"],
                "proposed_metric_input_rows_by_track": config["proposed_metric_input_rows_by_track"],
                "official_metric_input_rows": config["official_metric_input_rows"],
                "official_metric_execution_started": config["official_metric_execution_started"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if config["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--applied-decisions", default=str(DEFAULT_APPLIED_DECISIONS))
    parser.add_argument("--denominator-diff-preview", default=str(DEFAULT_DENOMINATOR_DIFF_PREVIEW))
    parser.add_argument("--registry-application-report", default=str(DEFAULT_REGISTRY_APPLICATION_REPORT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_config(
    *,
    applied_decisions_path: Path,
    denominator_diff_preview_path: Path,
    registry_application_report_path: Path | None = None,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    applied = read_json(applied_decisions_path)
    diff = read_json(denominator_diff_preview_path)
    registry_application = (
        read_json(registry_application_report_path)
        if registry_application_report_path is not None and registry_application_report_path.exists()
        else {}
    )
    config = build_config(
        applied_decisions=applied,
        applied_decisions_path=applied_decisions_path,
        denominator_diff_preview=diff,
        denominator_diff_preview_path=denominator_diff_preview_path,
        registry_application_report=registry_application,
        registry_application_report_path=registry_application_report_path,
    )
    config["artifact_paths"]["report_json"] = repo_relative(output_report)
    config["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, config)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(config), encoding="utf-8")
    return config


def build_config(
    *,
    applied_decisions: Mapping[str, Any],
    applied_decisions_path: Path,
    denominator_diff_preview: Mapping[str, Any],
    denominator_diff_preview_path: Path,
    registry_application_report: Mapping[str, Any] | None = None,
    registry_application_report_path: Path | None = None,
) -> dict[str, Any]:
    rows = [
        row
        for row in applied_decisions.get("approved_candidate_rows") or []
        if isinstance(row, Mapping)
    ]
    counts: Counter[str] = Counter(clean(row.get("track")) for row in rows)
    proposed_by_track = {track: int(counts.get(track, 0)) for track in TRACKS if counts.get(track, 0)}
    diff_entries = nested_mapping(denominator_diff_preview, "proposed_registry_patch", "entries")
    registry_application = registry_application_report if isinstance(registry_application_report, Mapping) else {}
    registry_applied = registry_application_ready(registry_application)
    registry_artifacts = nested_mapping(registry_application, "official_metric_input_artifacts")
    official_by_track = (
        {
            track: int_value(value)
            for track, value in registry_application.get("official_metric_input_rows_by_track", {}).items()
            if int_value(value)
        }
        if registry_applied and isinstance(registry_application.get("official_metric_input_rows_by_track"), Mapping)
        else {}
    )
    metric_lanes = {}
    for key, entry in sorted(diff_entries.items()):
        if not isinstance(entry, Mapping):
            continue
        track = clean(entry.get("track"))
        artifact = registry_artifacts.get(track) if isinstance(registry_artifacts.get(track), Mapping) else {}
        candidate_path = clean(entry.get("path") or artifact.get("path") or artifact.get("csv_path"))
        metric_lanes[track] = {
            "denominator_key": key,
            "candidate_path": candidate_path,
            "csv_path": candidate_path,
            "proposed_rows": int_value(entry.get("row_count")),
            "row_count": official_by_track.get(track, int_value(entry.get("row_count"))) if registry_applied else 0,
            "sha256": clean(artifact.get("sha256")),
            "metric_lane": clean(entry.get("metric_lane") or artifact.get("metric_lane") or "answer_citation"),
            "metric_role": "official_answer_citation_candidate_after_registry_application",
            "registry_application_required": not registry_applied,
            "official_metric_input_rows_current": official_by_track.get(track, 0) if registry_applied else 0,
        }

    errors: list[str] = []
    if clean(applied_decisions.get("status")) != "HUMAN_AUDIT_V2_APPLIED_DECISIONS_READY":
        errors.append("applied decisions must be ready")
    if clean(denominator_diff_preview.get("status")) != "OFFICIAL_DENOMINATOR_CANDIDATE_DIFF_PREVIEW_READY":
        errors.append("denominator diff preview must be ready")
    if int_value(applied_decisions.get("official_metric_input_rows")) != 0:
        errors.append("applied decisions official_metric_input_rows must remain 0")
    if int_value(denominator_diff_preview.get("official_metric_input_rows")) != 0:
        errors.append("denominator diff preview official_metric_input_rows must remain 0")
    if applied_decisions.get("promotion_evidence") is True or denominator_diff_preview.get("promotion_evidence") is True:
        errors.append("candidate config sources must not be promotion evidence")
    if nested_mapping(denominator_diff_preview, "guardrails").get("official_denominator_registry_changed") is True:
        errors.append("denominator diff preview cannot report registry changes")
    if sum(proposed_by_track.values()) != int_value(denominator_diff_preview.get("proposed_official_metric_candidate_rows")):
        errors.append("proposed row count mismatch between applied decisions and denominator preview")
    if registry_application:
        if not registry_applied:
            errors.append("registry application report is present but not ready")
        elif int_value(registry_application.get("official_metric_input_rows")) != sum(proposed_by_track.values()):
            errors.append("registry application official metric input rows mismatch")
        elif registry_applied and not registry_artifacts:
            errors.append("registry application report must expose official metric input artifacts")
    for track, lane in metric_lanes.items():
        if registry_applied and not lane["sha256"]:
            errors.append(f"{track} metric lane missing csv sha256")
        if registry_applied and lane["metric_lane"] != "answer_citation":
            errors.append(f"{track} metric lane must be answer_citation")
    if not rows:
        errors.append("no approved rows available for metric config")

    candidate_manifest = [
        {
            "query_id": clean(row.get("query_id")),
            "track": clean(row.get("track")),
            "question": clean(row.get("question")),
            "expected_answer": clean(row.get("expected_answer")),
            "supporting_evidence": clean(row.get("supporting_evidence")),
            "citation_locator": row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {},
            "official_metric_input": registry_applied,
            "promotion_evidence": False,
            "registry_application_required": not registry_applied,
        }
        for row in sorted(rows, key=lambda item: (clean(item.get("track")), clean(item.get("query_id"))))
    ]
    total = sum(proposed_by_track.values())
    official_rows = sum(official_by_track.values()) if registry_applied else 0
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": (
            "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED"
            if registry_applied and not errors
            else (
                "OFFICIAL_METRIC_INPUT_CONFIG_READY_PENDING_REGISTRY_APPLICATION"
                if not errors
                else "OFFICIAL_METRIC_INPUT_CONFIG_FAIL_CLOSED"
            )
        ),
        "report_role": "official_metric_input_config",
        "config_role": "metric_input_configuration_not_executed",
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_execution_started": False,
        "official_metric_input_rows": official_rows,
        "official_metric_input_rows_by_track": official_by_track if registry_applied else {},
        "official_metric_input_rows_scope": (
            "registry_backed_question_gold_input_rows_not_metric_execution"
            if registry_applied
            else "pending_registry_application_rows_not_metric_execution"
        ),
        "official_metric_input_artifacts": metric_input_artifacts(metric_lanes, registry_artifacts, registry_applied),
        "proposed_metric_input_rows": total,
        "proposed_metric_input_rows_by_track": proposed_by_track,
        "metric_execution_allowed": registry_applied,
        "metric_execution_requires_explicit_command": True,
        "registry_application_required": not registry_applied,
        "registry_application_status": "APPLIED" if registry_applied else "PENDING",
        "explicit_user_approval_required_before_registry_mutation": True,
        "cross_track_averages_computed": False,
        "cross_track_average_optimization_allowed": False,
        "tuning_run_started": False,
        "metric_lanes": metric_lanes,
        "candidate_manifest": candidate_manifest,
        "guardrails": {
            "official_metric_input_rows_remain_zero": official_rows == 0,
            "official_metric_input_rows_registry_backed": registry_applied,
            "official_metric_execution_started": False,
            "metric_execution_requires_explicit_command": True,
            "official_denominator_registry_mutation": registry_applied,
            "official_denominator_registry_opened": registry_applied,
            "gold_registry_mutation": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_written": False,
            "promotion_evidence_created": False,
            "tuning_run_started": False,
        },
        "source_artifacts": {
            "applied_decisions": repo_relative(applied_decisions_path),
            "denominator_diff_preview": repo_relative(denominator_diff_preview_path),
            "registry_application_report": repo_relative(registry_application_report_path)
            if registry_application_report_path is not None
            else "",
        },
        "artifact_paths": {"report_json": "", "report_md": ""},
        "validation": {"ok": not errors, "errors": sorted(dict.fromkeys(errors))},
    }


def render_markdown(config: Mapping[str, Any]) -> str:
    lines = [
        "# Official Metric Input Config v1",
        "",
        f"- Status: `{config['status']}`",
        f"- Config role: `{config['config_role']}`",
        f"- Proposed metric input rows: `{config['proposed_metric_input_rows']}`",
        f"- Proposed rows by track: `{json.dumps(config['proposed_metric_input_rows_by_track'], ensure_ascii=False, sort_keys=True)}`",
        f"- Official metric input rows: `{config['official_metric_input_rows']}`",
        f"- Official metric input rows scope: `{config.get('official_metric_input_rows_scope')}`",
        f"- Registry application status: `{config.get('registry_application_status')}`",
        f"- Official metric execution started: `{str(config['official_metric_execution_started']).lower()}`",
        f"- Metric execution allowed: `{str(config['metric_execution_allowed']).lower()}`",
        f"- Metric execution requires explicit command: `{str(config.get('metric_execution_requires_explicit_command')).lower()}`",
        f"- Registry application required: `{str(config['registry_application_required']).lower()}`",
        f"- Tuning run started: `{str(config['tuning_run_started']).lower()}`",
        "",
    ]
    if config.get("registry_application_status") == "APPLIED":
        lines.append(
            "This config is registry-backed input for the official answer/citation metric, but the metric has not been executed and still requires an explicit execution command."
        )
    else:
        lines.append(
            "This config enters metric setup as a pending input manifest. It cannot run official metrics until the denominator registry patch is explicitly approved and applied."
        )
    if config["validation"]["errors"]:
        lines.extend(["", "## Validation Errors", ""])
        lines.extend(f"- `{error}`" for error in config["validation"]["errors"])
    return "\n".join(lines) + "\n"


def registry_application_ready(payload: Mapping[str, Any]) -> bool:
    return (
        clean(payload.get("status")) == "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLIED"
        and payload.get("registry_updated") is True
        and nested_mapping(payload, "validation").get("ok") is True
        and int_value(payload.get("official_metric_input_rows")) > 0
        and payload.get("official_metric_execution_started") is False
        and payload.get("promotion_evidence") is not True
    )


def metric_input_artifacts(
    metric_lanes: Mapping[str, Mapping[str, Any]],
    registry_artifacts: Mapping[str, Any],
    registry_applied: bool,
) -> dict[str, Any]:
    if not registry_applied:
        return {}
    artifacts: dict[str, Any] = {}
    for track, lane in sorted(metric_lanes.items()):
        artifact = registry_artifacts.get(track) if isinstance(registry_artifacts.get(track), Mapping) else {}
        path = clean(lane.get("candidate_path") or artifact.get("path"))
        artifacts[track] = {
            "path": path,
            "csv_path": path,
            "row_count": int_value(lane.get("official_metric_input_rows_current") or lane.get("row_count")),
            "sha256": clean(lane.get("sha256") or artifact.get("sha256")),
            "denominator_key": clean(lane.get("denominator_key")),
            "metric_lane": clean(lane.get("metric_lane") or "answer_citation"),
            "query_ids": artifact.get("query_ids") if isinstance(artifact.get("query_ids"), list) else [],
        }
    return artifacts


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any) -> str:
    return str(value or "").strip()


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return dict(current) if isinstance(current, Mapping) else {}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
