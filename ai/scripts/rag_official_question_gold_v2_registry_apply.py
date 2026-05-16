"""Apply v2 human-approved question gold candidates to the denominator registry.

This is the explicit registry-application step after the preview artifact. It
materializes per-track official question-gold CSVs, updates
official_denominator_registry.json with lane-specific entries, and writes a
registry application report. It does not run official metrics, start tuning, or
write production vectors.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"

DEFAULT_APPLIED_DECISIONS = REVIEW_DIR / "rag_human_audit_v2_applied_decisions.json"
DEFAULT_DENOMINATOR_DIFF_PREVIEW = REPORT_DIR / "official_denominator_candidate_diff_preview_v1.json"
DEFAULT_REGISTRY = EVAL_QUERY_DIR / "official_denominator_registry.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "official_question_gold_v2_registry_application_report.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "official_question_gold_v2_registry_application_report.md"

TRACK_OUTPUTS = {
    "text_namu_v2_1": EVAL_QUERY_DIR / "gold_queries_text_namu_v2_1_question_gold_v2.csv",
    "xlsx_business_structured": EVAL_QUERY_DIR / "gold_queries_xlsx_question_gold_v2.csv",
    "pdf_business_ocr_mm": EVAL_QUERY_DIR / "gold_queries_pdf_question_gold_v2.csv",
}
TRACK_DEFAULT_KEYS = {
    "text_namu_v2_1": "track_b_text_namu_v2_1_question_gold_v2",
    "xlsx_business_structured": "track_a_xlsx_question_gold_v2",
    "pdf_business_ocr_mm": "track_c_pdf_question_gold_v2",
}
SCHEMA_VERSION = "official_question_gold_v2_registry_application_v1"
DENOMINATOR_KIND = "question_answer_citation_gold_v2"
CSV_COLUMNS = [
    "query_id",
    "question",
    "expected_answer",
    "supporting_evidence",
    "track",
    "citation_locator",
    "human_label",
    "human_review_status",
    "human_approved_gold",
    "model_assisted_source",
    "model_assisted_diagnostic_only_before_human_approval",
    "official_denominator_current",
    "official_metric_input",
    "promotion_evidence",
    "gold_promoted",
    "source_packet_role",
    "issue_type",
    "supersedes_rejected_row_id",
    "query_id_bridge_policy",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_application(
        applied_decisions_path=Path(args.applied_decisions),
        denominator_diff_preview_path=Path(args.denominator_diff_preview),
        registry_path=Path(args.official_denominator_registry),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "registry_updated": report["registry_updated"],
                "official_metric_input_rows": report["official_metric_input_rows"],
                "official_metric_input_rows_by_track": report["official_metric_input_rows_by_track"],
                "official_metric_execution_started": report["official_metric_execution_started"],
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
    parser.add_argument("--denominator-diff-preview", default=str(DEFAULT_DENOMINATOR_DIFF_PREVIEW))
    parser.add_argument("--official-denominator-registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_application(
    *,
    applied_decisions_path: Path,
    denominator_diff_preview_path: Path,
    registry_path: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    applied = read_json(applied_decisions_path)
    preview = read_json(denominator_diff_preview_path)
    registry = read_json(registry_path)
    registry_sha_before = sha256_file(registry_path)
    report = build_application_report(
        applied_decisions=applied,
        denominator_diff_preview=preview,
        registry=registry,
        applied_decisions_path=applied_decisions_path,
        denominator_diff_preview_path=denominator_diff_preview_path,
        registry_path=registry_path,
        registry_sha_before=registry_sha_before,
    )
    if report["validation"]["ok"]:
        track_rows = rows_by_track(applied)
        write_track_outputs(track_rows)
        output_records = track_output_records(track_rows)
        apply_registry_patch(
            registry=registry,
            output_records=output_records,
            applied_decisions_path=applied_decisions_path,
            denominator_diff_preview_path=denominator_diff_preview_path,
            output_report=output_report,
        )
        write_json(registry_path, registry)
        report["registry_updated"] = True
        report["registry_sha256_after"] = sha256_file(registry_path)
        report["official_metric_input_artifacts"] = output_records
        report["official_metric_input_rows"] = sum(row["row_count"] for row in output_records.values())
        report["official_metric_input_rows_by_track"] = {
            track: row["row_count"] for track, row in sorted(output_records.items())
        }
    else:
        report["registry_sha256_after"] = registry_sha_before
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_application_report(
    *,
    applied_decisions: Mapping[str, Any],
    denominator_diff_preview: Mapping[str, Any],
    registry: Mapping[str, Any],
    applied_decisions_path: Path,
    denominator_diff_preview_path: Path,
    registry_path: Path,
    registry_sha_before: str,
) -> dict[str, Any]:
    rows = [row for row in applied_decisions.get("approved_candidate_rows") or [] if isinstance(row, Mapping)]
    counts = Counter(clean(row.get("track")) for row in rows)
    preview_counts = nested_mapping(denominator_diff_preview, "summary", "proposed_rows_by_track")
    preview_entries = nested_mapping(denominator_diff_preview, "proposed_registry_patch", "entries")
    errors: list[str] = []
    if clean(applied_decisions.get("status")) != "HUMAN_AUDIT_V2_APPLIED_DECISIONS_READY":
        errors.append("applied decisions must be ready")
    if clean(denominator_diff_preview.get("status")) != "OFFICIAL_DENOMINATOR_CANDIDATE_DIFF_PREVIEW_READY":
        errors.append("denominator diff preview must be ready")
    if clean(denominator_diff_preview.get("registry_diff_status")) != "PREVIEW_ONLY_NO_MUTATION":
        errors.append("denominator diff preview must be preview-only")
    if not rows:
        errors.append("no approved candidate rows to apply")
    for track, count in sorted(counts.items()):
        if int_value(preview_counts.get(track)) != count:
            errors.append(f"preview row count mismatch for {track}")
    registry_denominators = registry.get("official_diagnostic_denominators")
    if not isinstance(registry_denominators, Mapping):
        errors.append("registry missing official_diagnostic_denominators")
    for key, entry in preview_entries.items():
        if not isinstance(entry, Mapping):
            errors.append(f"preview entry {key} is not an object")
            continue
        track = clean(entry.get("track"))
        output = TRACK_OUTPUTS.get(track)
        if output is None:
            errors.append(f"unknown preview track {track}")
            continue
        expected_key = denominator_key_for_track(track)
        if key != expected_key:
            errors.append(f"preview denominator key mismatch for {track}: expected {expected_key}, got {key}")
        if clean(entry.get("path")) != repo_relative(output):
            errors.append(f"preview output path mismatch for {track}")
        existing = registry_denominators.get(key) if isinstance(registry_denominators, Mapping) else None
        if isinstance(existing, Mapping):
            same_path = clean(existing.get("path")) == repo_relative(output)
            same_kind = clean(existing.get("denominator_kind")) == DENOMINATOR_KIND
            if not (same_path and same_kind):
                errors.append(f"registry key collision for {key}")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLIED" if not errors else "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLY_FAIL_CLOSED",
        "report_role": "official_question_gold_v2_registry_application",
        "registry_updated": False,
        "registry_path": repo_relative(registry_path),
        "registry_sha256_before": registry_sha_before,
        "registry_sha256_after": registry_sha_before,
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_by_track": {},
        "official_metric_execution_started": False,
        "tuning_run_started": False,
        "official_metric_input_artifacts": {},
        "guardrails": {
            "gold_registry_mutation": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_written": False,
            "official_metric_execution_started": False,
            "tuning_run_started": False,
            "promotion_evidence_created": False,
            "retrieval_defaults_overwritten": False,
            "cross_track_average_denominator": False,
        },
        "source_artifacts": {
            "applied_decisions": repo_relative(applied_decisions_path),
            "denominator_diff_preview": repo_relative(denominator_diff_preview_path),
        },
        "artifact_paths": {"report_json": "", "report_md": ""},
        "validation": {"ok": not errors, "errors": sorted(dict.fromkeys(errors))},
    }


def rows_by_track(applied: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in applied.get("approved_candidate_rows") or []:
        if isinstance(row, Mapping):
            grouped.setdefault(clean(row.get("track")), []).append(row)
    return {track: sorted(rows, key=lambda row: clean(row.get("query_id"))) for track, rows in grouped.items()}


def write_track_outputs(track_rows: Mapping[str, list[Mapping[str, Any]]]) -> None:
    for track, rows in track_rows.items():
        output = TRACK_OUTPUTS[track]
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow(csv_row(row))


def csv_row(row: Mapping[str, Any]) -> dict[str, str]:
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    expected_answer = clean(row.get("expected_answer"))
    expected_answer = strip_text_answer_report(expected_answer)
    return {
        "query_id": clean(row.get("query_id")),
        "question": clean(row.get("question")),
        "expected_answer": expected_answer,
        "supporting_evidence": clean(row.get("supporting_evidence")),
        "track": clean(row.get("track")),
        "citation_locator": json.dumps(locator, ensure_ascii=False, sort_keys=True),
        "human_label": clean(row.get("human_label")),
        "human_review_status": clean(row.get("human_review_status")),
        "human_approved_gold": "TRUE",
        "model_assisted_source": "TRUE" if row.get("model_assisted_source") else "FALSE",
        "model_assisted_diagnostic_only_before_human_approval": (
            "TRUE" if row.get("model_assisted_diagnostic_only_before_human_approval") else "FALSE"
        ),
        "official_denominator_current": "TRUE",
        "official_metric_input": "TRUE",
        "promotion_evidence": "FALSE",
        "gold_promoted": "TRUE",
        "source_packet_role": clean(row.get("source_packet_role")),
        "issue_type": clean(row.get("issue_type")),
        "supersedes_rejected_row_id": clean(row.get("supersedes_rejected_row_id")),
        "query_id_bridge_policy": clean(row.get("query_id_bridge_policy")),
    }


def strip_text_answer_report(value: str) -> str:
    marker = "**Short answer:**"
    if marker not in value:
        return value
    tail = value.split(marker, 1)[1]
    return tail.split("**Supporting passages:**", 1)[0].strip()


def track_output_records(track_rows: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for track, rows in sorted(track_rows.items()):
        path = TRACK_OUTPUTS[track]
        records[track] = {
            "path": repo_relative(path),
            "row_count": len(rows),
            "sha256": sha256_file(path),
            "query_ids": [clean(row.get("query_id")) for row in rows],
        }
    return records


def apply_registry_patch(
    *,
    registry: dict[str, Any],
    output_records: Mapping[str, Mapping[str, Any]],
    applied_decisions_path: Path,
    denominator_diff_preview_path: Path,
    output_report: Path,
) -> None:
    denominators = registry.setdefault("official_diagnostic_denominators", {})
    current_defaults = registry.setdefault("current_defaults", {})
    registry["updated_at"] = datetime.now(timezone.utc).date().isoformat()
    for track, record in sorted(output_records.items()):
        denominator_key = denominator_key_for_track(track)
        denominators[denominator_key] = {
            "path": record["path"],
            "row_count": record["row_count"],
            "official_positive_denominator": record["row_count"],
            "official_metric_input_rows": record["row_count"],
            "sha256": record["sha256"],
            "gold_status_policy": "human_label=INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE from v2 audit packet",
            "denominator_rule": "human-approved source-bound question, expected answer, evidence, and citation locator",
            "promotion_evidence": False,
            "evidence_role": "official_question_gold_denominator",
            "denominator_kind": DENOMINATOR_KIND,
            "metric_lane": "answer_citation",
            "question_gold_current_default": True,
            "current_default": False,
            "not_retrieval_denominator": True,
            "source_applied_decisions": repo_relative(applied_decisions_path),
            "source_denominator_diff_preview": repo_relative(denominator_diff_preview_path),
            "registry_application_report": repo_relative(output_report),
        }
        current_defaults[TRACK_DEFAULT_KEYS[track]] = {
            "denominator_key": denominator_key,
            "official_metric_input_path": record["path"],
            "official_metric_input_rows": record["row_count"],
            "official_positive_denominator": record["row_count"],
            "metric_lane": "answer_citation",
            "denominator_kind": DENOMINATOR_KIND,
            "retrieval_default_unchanged": True,
        }


def denominator_key_for_track(track: str) -> str:
    if track == "text_namu_v2_1":
        return "track_b_text_namu_v2_1_question_gold_v2_human_audit_approved"
    if track == "xlsx_business_structured":
        return "track_a_xlsx_question_gold_v2_human_audit_approved"
    if track == "pdf_business_ocr_mm":
        return "track_c_pdf_question_gold_v2_human_audit_approved"
    raise ValueError(f"unknown track: {track}")


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Official Question Gold v2 Registry Application",
        "",
        f"- Status: `{report['status']}`",
        f"- Registry updated: `{str(report['registry_updated']).lower()}`",
        f"- Official metric input rows: `{report['official_metric_input_rows']}`",
        f"- Rows by track: `{json.dumps(report['official_metric_input_rows_by_track'], ensure_ascii=False, sort_keys=True)}`",
        f"- Official metric execution started: `{str(report['official_metric_execution_started']).lower()}`",
        f"- Tuning run started: `{str(report['tuning_run_started']).lower()}`",
        f"- Promotion evidence: `{str(report['promotion_evidence']).lower()}`",
        "",
        "The registry is updated for question-gold answer/citation lanes only. Existing retrieval defaults remain separate.",
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
