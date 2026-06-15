"""Preview official denominator registry changes for v2 approved candidates.

This artifact is intentionally a diff preview only. It reads the current
official denominator registry, proposes track-specific denominator entries,
and proves that the registry file was not mutated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"

DEFAULT_APPLIED_DECISIONS = REVIEW_DIR / "rag_human_audit_v2_applied_decisions.json"
DEFAULT_REGISTRY = EVAL_QUERY_DIR / "official_denominator_registry.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "official_denominator_candidate_diff_preview_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "official_denominator_candidate_diff_preview_v1.md"

SCHEMA_VERSION = "official_denominator_candidate_diff_preview_v1"
TRACK_OUTPUT_PATHS = {
    "text_namu_v2_1": "ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv",
    "xlsx_business_structured": "ai/eval/eval_queries/gold_queries_xlsx_question_gold_v2.csv",
    "pdf_business_ocr_mm": "ai/eval/eval_queries/gold_queries_pdf_question_gold_v2.csv",
}
TRACK_NAMES = {
    "text_namu_v2_1": "Track B TEXT/Namu V2.1 question gold v2",
    "xlsx_business_structured": "Track A XLSX question gold v2",
    "pdf_business_ocr_mm": "Track C PDF question gold v2",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_preview(
        applied_decisions_path=Path(args.applied_decisions),
        official_denominator_registry=Path(args.official_denominator_registry),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "registry_diff_status": report["registry_diff_status"],
                "proposed_rows_by_track": report["summary"]["proposed_rows_by_track"],
                "official_metric_input_rows": report["official_metric_input_rows"],
                "official_denominator_registry_changed": report["guardrails"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--applied-decisions", default=str(DEFAULT_APPLIED_DECISIONS))
    parser.add_argument("--official-denominator-registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_preview(
    *,
    applied_decisions_path: Path,
    official_denominator_registry: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    registry_sha_before = sha256_file(official_denominator_registry)
    applied = read_json(applied_decisions_path)
    registry = read_json(official_denominator_registry)
    registry_sha_after = sha256_file(official_denominator_registry)
    report = build_preview(
        applied_decisions=applied,
        applied_decisions_path=applied_decisions_path,
        registry=registry,
        official_denominator_registry=official_denominator_registry,
        registry_sha_before=registry_sha_before,
        registry_sha_after=registry_sha_after,
    )
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_preview(
    *,
    applied_decisions: Mapping[str, Any],
    applied_decisions_path: Path,
    registry: Mapping[str, Any],
    official_denominator_registry: Path,
    registry_sha_before: str,
    registry_sha_after: str,
) -> dict[str, Any]:
    rows = [
        row
        for row in applied_decisions.get("approved_candidate_rows") or []
        if isinstance(row, Mapping)
    ]
    proposed_by_track: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        track = clean(row.get("track"))
        proposed_by_track.setdefault(track, []).append(row)

    proposed_entries: dict[str, dict[str, Any]] = {}
    for track, track_rows in sorted(proposed_by_track.items()):
        denominator_key = clean(track_rows[0].get("track_denominator_key_preview"))
        if not denominator_key:
            denominator_key = f"{track}_question_gold_v2_human_audit_approved"
        proposed_entries[denominator_key] = {
            "track": track,
            "display_name": TRACK_NAMES.get(track, track),
            "path": TRACK_OUTPUT_PATHS.get(track, ""),
            "row_count": len(track_rows),
            "official_positive_denominator": len(track_rows),
            "sha256": "TO_BE_COMPUTED_AFTER_APPROVED_CSV_WRITE",
            "gold_status_policy": "human_label=INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE from v2 audit packet",
            "denominator_rule": "source-bound question, expected answer, evidence, and citation locator verified before human approval",
            "promotion_evidence": False,
            "evidence_role": "official_question_gold_candidate_pending_registry_application",
            "current_default": False,
            "registry_application_required": True,
            "source_applied_decisions": repo_relative(applied_decisions_path),
        }

    registry_changed = registry_sha_before != registry_sha_after
    errors: list[str] = []
    if clean(applied_decisions.get("status")) != "HUMAN_AUDIT_V2_APPLIED_DECISIONS_READY":
        errors.append("applied decisions must be HUMAN_AUDIT_V2_APPLIED_DECISIONS_READY")
    if int_value(applied_decisions.get("official_metric_input_rows")) != 0:
        errors.append("applied decisions official_metric_input_rows must remain 0")
    if applied_decisions.get("promotion_evidence") is True:
        errors.append("applied decisions promotion_evidence must remain false")
    if registry_changed:
        errors.append("official denominator registry changed during diff preview")
    current_denominators = registry.get("official_diagnostic_denominators")
    if not isinstance(current_denominators, Mapping):
        errors.append("official denominator registry missing official_diagnostic_denominators")
    if not proposed_entries:
        errors.append("no approved candidate rows available for denominator preview")
    collisions = sorted(set(proposed_entries) & set(current_denominators or {}))
    if collisions:
        errors.append(f"proposed denominator keys already exist: {', '.join(collisions)}")

    proposed_rows_by_track = {track: len(track_rows) for track, track_rows in sorted(proposed_by_track.items())}
    total_rows = sum(proposed_rows_by_track.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "OFFICIAL_DENOMINATOR_CANDIDATE_DIFF_PREVIEW_READY" if not errors else "OFFICIAL_DENOMINATOR_CANDIDATE_DIFF_PREVIEW_FAIL_CLOSED",
        "report_role": "official_denominator_candidate_diff_preview",
        "registry_diff_status": "PREVIEW_ONLY_NO_MUTATION",
        "diagnostic_only": False,
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "proposed_official_metric_candidate_rows": total_rows,
        "summary": {
            "proposed_denominator_entries": len(proposed_entries),
            "proposed_rows_total": total_rows,
            "proposed_rows_by_track": proposed_rows_by_track,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
        },
        "proposed_registry_patch": {
            "operation": "add_track_specific_official_diagnostic_denominators_after_explicit_user_approval",
            "target_section": "official_diagnostic_denominators",
            "entries": proposed_entries,
            "current_defaults_changes": {},
            "cross_track_average_denominator": False,
        },
        "required_apply_sequence": [
            "materialize_approved_track_csvs_or_jsonl_with_sha256",
            "apply_registry_patch_after_explicit_user_approval",
            "regenerate_metric_input_config_as_official_metric_input",
            "run_official_metrics_only_after_registry_application",
        ],
        "guardrails": {
            "official_denominator_registry_path": repo_relative(official_denominator_registry),
            "official_denominator_registry_sha256_before": registry_sha_before,
            "official_denominator_registry_sha256_after": registry_sha_after,
            "official_denominator_registry_changed": registry_changed,
            "official_denominator_registry_mutation": False,
            "official_denominator_opened": False,
            "official_metric_executed": False,
            "gold_registry_mutation": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_written": False,
            "tuning_run_started": False,
        },
        "source_artifacts": {
            "applied_decisions": repo_relative(applied_decisions_path),
            "official_denominator_registry": repo_relative(official_denominator_registry),
        },
        "artifact_paths": {"report_json": "", "report_md": ""},
        "validation": {"ok": not errors, "errors": sorted(dict.fromkeys(errors))},
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = nested_mapping(report, "summary")
    lines = [
        "# Official Denominator Candidate Diff Preview v1",
        "",
        f"- Status: `{report['status']}`",
        f"- Registry diff status: `{report['registry_diff_status']}`",
        f"- Proposed rows total: `{summary.get('proposed_rows_total')}`",
        f"- Proposed rows by track: `{json.dumps(summary.get('proposed_rows_by_track'), ensure_ascii=False, sort_keys=True)}`",
        f"- Official metric input rows: `{report['official_metric_input_rows']}`",
        f"- Registry changed: `{str(nested_mapping(report, 'guardrails').get('official_denominator_registry_changed')).lower()}`",
        "",
        "This is a registry patch preview only. The official denominator registry is not modified by this artifact.",
    ]
    if report["validation"]["errors"]:
        lines.extend(["", "## Validation Errors", ""])
        lines.extend(f"- `{error}`" for error in report["validation"]["errors"])
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
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
