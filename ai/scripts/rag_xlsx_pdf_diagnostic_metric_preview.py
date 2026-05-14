"""Generate a diagnostic metric preview for XLSX/PDF tracks.

This report deliberately avoids official denominators, official metrics, and
cross-track averages. It only previews per-track diagnostic readiness counts
from the XLSX answer/citation and PDF evidence-readiness reports.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"

DEFAULT_XLSX_REPORT = REPORT_DIR / "xlsx_answer_citation_diagnostic_report.json"
DEFAULT_PDF_REPORT = REPORT_DIR / "pdf_evidence_readiness_report.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "xlsx_pdf_diagnostic_metric_preview_report.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "xlsx_pdf_diagnostic_metric_preview_report.md"

SCHEMA_VERSION = "xlsx_pdf_diagnostic_metric_preview_v1"
ALLOWED_SOURCE_STATUSES = {
    "xlsx_business_structured": {"PASS"},
    "pdf_business_ocr_mm": {"DIAGNOSTIC_ONLY_BLOCKED", "READY_FOR_STRICT_GATE_RERUN"},
}
PROTECTED_GUARDRAILS = (
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
    report = run_preview(
        xlsx_answer_report=Path(args.xlsx_answer_report),
        pdf_readiness_report=Path(args.pdf_readiness_report),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "official_metric_input_rows": report["official_metric_input_rows"],
                "cross_track_averages_computed": report["cross_track_averages_computed"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx-answer-report", default=str(DEFAULT_XLSX_REPORT))
    parser.add_argument("--pdf-readiness-report", default=str(DEFAULT_PDF_REPORT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_preview(
    *,
    xlsx_answer_report: Path,
    pdf_readiness_report: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    report = build_preview(
        xlsx_answer_report=xlsx_answer_report,
        pdf_readiness_report=pdf_readiness_report,
    )
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_preview(*, xlsx_answer_report: Path, pdf_readiness_report: Path) -> dict[str, Any]:
    xlsx = read_json(xlsx_answer_report)
    pdf = read_json(pdf_readiness_report)
    official_metric_input_rows = int(xlsx.get("official_metric_input_rows") or 0)
    track_previews = {
        "xlsx_business_structured": {
            "source_report": repo_relative(xlsx_answer_report),
            "status": xlsx.get("status"),
            "diagnostic_only": bool(xlsx.get("diagnostic_only", True)),
            "promotion_evidence": bool(xlsx.get("promotion_evidence", False)),
            "review_input_rows": nested_int(xlsx, "counts", "generated_review_input_rows"),
            "answer_claim_supported_rows": nested_int(xlsx, "counts", "answer_claim_supported_rows"),
            "citation_locator_resolved_rows": nested_int(xlsx, "counts", "citation_locator_resolved_rows"),
            "official_metric_input_rows": int(xlsx.get("official_metric_input_rows") or 0),
        },
        "pdf_business_ocr_mm": {
            "source_report": repo_relative(pdf_readiness_report),
            "status": pdf.get("status"),
            "diagnostic_only": bool(pdf.get("diagnostic_only", True)),
            "promotion_evidence": bool(pdf.get("promotion_evidence", False)),
            "input_rows": nested_int(pdf, "counts", "input_rows"),
            "strict_gate_readiness_count": nested_int(pdf, "counts", "strict_gate_readiness_count"),
            "rows_blocked_by_missing_layout": nested_int(pdf, "counts", "rows_blocked_by_missing_layout"),
            "rows_blocked_by_file_identity_ambiguity": nested_int(
                pdf, "counts", "rows_blocked_by_file_identity_ambiguity"
            ),
            "answer_denominator_rows": nested_int(pdf, "counts", "pdf_answer_generation_denominator"),
            "answer_generation_run": pdf.get("answer_generation_run") is True,
            "official_metric_input_rows": int(
                pdf.get("official_metric_input_rows") or nested_int(pdf, "counts", "official_metric_input_rows")
            ),
        },
    }
    official_metric_input_rows += track_previews["pdf_business_ocr_mm"]["official_metric_input_rows"]
    validation_errors = []
    validation_errors.extend(validate_source_report("xlsx_business_structured", xlsx))
    validation_errors.extend(validate_source_report("pdf_business_ocr_mm", pdf))
    if official_metric_input_rows != 0:
        validation_errors.append("official_metric_input_rows must remain 0")
    if any(item.get("promotion_evidence") for item in track_previews.values()):
        validation_errors.append("promotion_evidence must remain false for all diagnostic previews")
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "PASS" if not validation_errors else "FAIL",
        "report_role": "xlsx_pdf_track_level_diagnostic_metric_preview",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": official_metric_input_rows,
        "official_metric_input_rows_by_track": {
            track: item["official_metric_input_rows"] for track, item in track_previews.items()
        },
        "cross_track_averages_computed": False,
        "track_previews": track_previews,
        "route_fallback_label_policy": {
            "route_labels": "diagnostic_only",
            "fallback_labels": "diagnostic_only",
            "official_routing_accuracy_computed": False,
            "official_fallback_success_computed": False,
        },
        "guardrails": {
            "official_metric_input_rows_remain_zero": official_metric_input_rows == 0,
            "official_denominator_opened": False,
            "cross_track_average_computed": False,
            "route_fallback_labels_diagnostic_only": True,
            "model_assisted_outputs_promoted_to_gold": False,
            "promotion_evidence_created": False,
        },
        "artifact_paths": {
            "report_json": "",
            "report_md": "",
        },
        "validation": {
            "ok": not validation_errors,
            "errors": validation_errors,
        },
    }
    return report


def validate_source_report(track: str, payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    status = str(payload.get("status", ""))
    if status not in ALLOWED_SOURCE_STATUSES[track]:
        errors.append(f"{track} source report status is {status}")
    validation = payload.get("validation") if isinstance(payload.get("validation"), Mapping) else {}
    if validation.get("ok") is False:
        errors.append(f"{track} source report validation is not ok")
    if payload.get("diagnostic_only") is not True:
        errors.append(f"{track} source report must be diagnostic_only=true")
    if payload.get("official_metric") is not False:
        errors.append(f"{track} source report must keep official_metric=false")
    if payload.get("promotion_evidence") is not False:
        errors.append(f"{track} source report must keep promotion_evidence=false")
    guardrails = payload.get("guardrails") if isinstance(payload.get("guardrails"), Mapping) else {}
    for key in PROTECTED_GUARDRAILS:
        if guardrails.get(key) is True:
            errors.append(f"{track} source guardrail violation: {key}=true")
    if track == "pdf_business_ocr_mm":
        counts = payload.get("counts") if isinstance(payload.get("counts"), Mapping) else {}
        lane_separation = (
            payload.get("lane_separation") if isinstance(payload.get("lane_separation"), Mapping) else {}
        )
        if payload.get("answer_generation_run") is True:
            errors.append("pdf_business_ocr_mm answer generation must remain closed")
        if nested_int(counts, "pdf_answer_generation_denominator") != 0:
            errors.append("pdf_business_ocr_mm answer denominator must remain 0")
        if int(payload.get("official_metric_input_rows") or nested_int(counts, "official_metric_input_rows")) != 0:
            errors.append("pdf_business_ocr_mm official_metric_input_rows must remain 0")
        if lane_separation.get("content_and_file_identity_aggregated") is True:
            errors.append("pdf_business_ocr_mm content/file identity lanes must remain separate")
    return errors


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# XLSX/PDF Diagnostic Metric Preview",
        "",
        f"- Status: `{report['status']}`",
        f"- Official metric input rows: `{report['official_metric_input_rows']}`",
        f"- Cross-track averages computed: `{str(report['cross_track_averages_computed']).lower()}`",
        "- Route/fallback labels remain diagnostic-only.",
        "",
        "## Track Preview",
        "",
        "| Track | Status | Rows | Ready/Supported | Blockers |",
        "|---|---|---:|---:|---:|",
    ]
    xlsx = report["track_previews"]["xlsx_business_structured"]
    pdf = report["track_previews"]["pdf_business_ocr_mm"]
    lines.append(
        "| xlsx_business_structured | "
        f"`{xlsx['status']}` | `{xlsx['review_input_rows']}` | `{xlsx['citation_locator_resolved_rows']}` | `0` |"
    )
    lines.append(
        "| pdf_business_ocr_mm | "
        f"`{pdf['status']}` | `{pdf['input_rows']}` | `{pdf['strict_gate_readiness_count']}` | "
        f"`{pdf['rows_blocked_by_missing_layout']}` |"
    )
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def nested_int(payload: Mapping[str, Any], *keys: str) -> int:
    value: Any = payload
    for key in keys:
        if not isinstance(value, Mapping):
            return 0
        value = value.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
