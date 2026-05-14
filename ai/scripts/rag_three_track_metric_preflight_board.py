"""Build a three-track diagnostic metric-preflight board.

The board reports TEXT/Namu V2.1, XLSX answer/citation diagnostics, and PDF
evidence readiness separately. It does not compute official metrics, open
official denominators, run tuning, or average across tracks.
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
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_TEXT_POLICY_PACKET = REVIEW_DIR / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json"
DEFAULT_XLSX_ANSWER_REPORT = REPORT_DIR / "xlsx_answer_citation_diagnostic_report.json"
DEFAULT_PDF_READINESS_REPORT = REPORT_DIR / "pdf_evidence_readiness_report.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "three_track_metric_preflight_board.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "three_track_metric_preflight_board.md"

SCHEMA_VERSION = "three_track_metric_preflight_board_v1"
TRACKS = ("text_namu_v2_1", "xlsx_business_structured", "pdf_business_ocr_mm")
PROTECTED_SOURCE_GUARDRAILS = (
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
    return 0 if board["status"] in {"DIAGNOSTIC_PREFLIGHT_READY", "DIAGNOSTIC_PREFLIGHT_BLOCKED"} else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-policy-packet", default=str(DEFAULT_TEXT_POLICY_PACKET))
    parser.add_argument("--xlsx-answer-report", default=str(DEFAULT_XLSX_ANSWER_REPORT))
    parser.add_argument("--pdf-readiness-report", default=str(DEFAULT_PDF_READINESS_REPORT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--cross-track-averages-requested", action="store_true")
    return parser.parse_args(argv)


def run_board(
    *,
    text_policy_packet: Path,
    xlsx_answer_report: Path,
    pdf_readiness_report: Path,
    output_report: Path,
    output_md: Path,
    cross_track_averages_requested: bool = False,
) -> dict[str, Any]:
    board = build_board(
        text_policy_packet=text_policy_packet,
        xlsx_answer_report=xlsx_answer_report,
        pdf_readiness_report=pdf_readiness_report,
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
    cross_track_averages_requested: bool = False,
) -> dict[str, Any]:
    text = read_json(text_policy_packet)
    xlsx = read_json(xlsx_answer_report)
    pdf = read_json(pdf_readiness_report)
    tracks = {
        "text_namu_v2_1": text_track(text, text_policy_packet),
        "xlsx_business_structured": xlsx_track(xlsx, xlsx_answer_report),
        "pdf_business_ocr_mm": pdf_track(pdf, pdf_readiness_report),
    }
    errors = validation_errors(tracks, text=text, xlsx=xlsx, pdf=pdf)
    if cross_track_averages_requested:
        errors.append("cross-track averages are not allowed for this diagnostic board")
    official_rows_by_track = {
        track: int(payload.get("official_metric_input_rows") or 0)
        for track, payload in tracks.items()
    }
    blocked = any(payload.get("status") in {"FAIL", "DIAGNOSTIC_ONLY_BLOCKED"} for payload in tracks.values())
    status = "DIAGNOSTIC_PREFLIGHT_READY"
    if blocked:
        status = "DIAGNOSTIC_PREFLIGHT_BLOCKED"
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
        "cross_track_averages_computed": False,
        "route_fallback_label_status": {
            "route_labels": "diagnostic_only",
            "fallback_labels": "diagnostic_only",
            "official_route_metric_opened": False,
            "official_fallback_metric_opened": False,
        },
        "guardrails": {
            "official_metric_input_rows_remain_zero": all(value == 0 for value in official_rows_by_track.values()),
            "official_denominator_registry_mutation": False,
            "official_denominator_registry_opened": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_index_mutation": False,
            "production_vector_written": False,
            "model_assisted_outputs_promoted_to_gold": False,
            "cross_track_averages_computed": False,
            "route_fallback_labels_diagnostic_only": True,
        },
        "artifact_paths": {
            "text_policy_packet": repo_relative(text_policy_packet),
            "xlsx_answer_report": repo_relative(xlsx_answer_report),
            "pdf_readiness_report": repo_relative(pdf_readiness_report),
            "report_json": "",
            "report_md": "",
        },
        "validation": {
            "ok": not errors,
            "errors": errors,
        },
        "remaining_blockers": remaining_blockers(tracks),
    }
    return board


def text_track(payload: Mapping[str, Any], path: Path) -> dict[str, Any]:
    metrics = nested_mapping(payload, "diagnostic_metric_preview")
    return {
        "source_report": repo_relative(path),
        "status": clean(payload.get("status")),
        "diagnostic_status": clean(payload.get("status")),
        "answer_citation_status": "diagnostic_metric_pass_candidate"
        if metrics.get("metric_pass_candidate") is True
        else "diagnostic_policy_review_required",
        "official_metric_input_rows": int(metrics.get("official_metric_input_rows") or 0),
        "promotion_evidence": False,
        "clean_pass_rows": nested_int(metrics, "strict_clean_answer_preview", "numerator"),
        "cleanup_rows": nested_int(payload, "row_groups", "cleanup_rows", "row_count"),
        "rewrite_unresolved_rows": nested_int(payload, "row_groups", "unresolved_rows", "row_count"),
        "citation_fully_supported_rows": nested_int(metrics, "citation_supported_preview", "numerator"),
        "policy_packet_status": clean(payload.get("status")),
    }


def xlsx_track(payload: Mapping[str, Any], path: Path) -> dict[str, Any]:
    preview = nested_mapping(payload, "diagnostic_metric_preview")
    counts = nested_mapping(payload, "counts")
    leakage = nested_mapping(payload, "leakage_reprobe")
    return {
        "source_report": repo_relative(path),
        "status": clean(payload.get("status")),
        "diagnostic_status": "blocked_by_leakage_reprobe" if clean(payload.get("status")) != "PASS" else "ready",
        "generated_answer_rows": int(preview.get("generated_answer_rows") or counts.get("generated_review_input_rows") or 0),
        "clean_pass_rows": int(preview.get("clean_pass_rows") or 0),
        "cleanup_rows": int(preview.get("cleanup_rows") or 0),
        "rewrite_unresolved_rows": int(preview.get("rewrite_unresolved_rows") or 0),
        "citation_fully_supported_rows": int(
            preview.get("citation_fully_supported_rows") or counts.get("answer_claim_supported_rows") or 0
        ),
        "citation_locator_valid_rows": int(
            preview.get("citation_locator_valid_rows") or counts.get("citation_locator_resolved_rows") or 0
        ),
        "leakage_count": int(preview.get("leakage_count") or leakage.get("surface_leakage_count") or 0),
        "leakage_status": clean(preview.get("leakage_status") or leakage.get("status")),
        "official_metric_input_rows": int(payload.get("official_metric_input_rows") or 0),
        "promotion_evidence": bool(payload.get("promotion_evidence", False)),
    }


def pdf_track(payload: Mapping[str, Any], path: Path) -> dict[str, Any]:
    counts = nested_mapping(payload, "counts")
    rerun = nested_mapping(payload, "strict_gate_rerun")
    source_official_rows = int(payload.get("official_metric_input_rows") or counts.get("official_metric_input_rows") or 0)
    answer_denominator_rows = int(counts.get("pdf_answer_generation_denominator") or 0)
    return {
        "source_report": repo_relative(path),
        "status": clean(payload.get("status")),
        "diagnostic_status": clean(payload.get("status")),
        "input_rows": int(counts.get("input_rows") or 0),
        "rows_with_complete_page_bbox_region": int(counts.get("rows_with_complete_page_bbox_region") or 0),
        "rows_with_matched_text": int(counts.get("rows_with_matched_text") or 0),
        "rows_with_nearby_paragraphs": int(counts.get("rows_with_nearby_paragraphs") or 0),
        "rows_with_ocr_confidence_or_native_text_na": int(
            counts.get("rows_with_ocr_confidence_or_native_text_na") or 0
        ),
        "rows_with_citation_locator": int(counts.get("rows_with_citation_locator") or 0),
        "rows_blocked_by_missing_layout": int(counts.get("rows_blocked_by_missing_layout") or 0),
        "rows_blocked_by_file_identity_ambiguity": int(counts.get("rows_blocked_by_file_identity_ambiguity") or 0),
        "strict_gate_readiness_count": int(counts.get("strict_gate_readiness_count") or 0),
        "generated_strict_rows_if_rerun": int(counts.get("generated_strict_rows_if_rerun") or 0),
        "strict_gate_rerun_performed": rerun.get("rerun_performed") is True,
        "answer_denominator_rows": answer_denominator_rows,
        "answer_generation_run": payload.get("answer_generation_run") is True,
        "official_metric_input_rows": source_official_rows,
        "promotion_evidence": bool(payload.get("promotion_evidence", False)),
    }


def validation_errors(
    tracks: Mapping[str, Mapping[str, Any]],
    *,
    text: Mapping[str, Any],
    xlsx: Mapping[str, Any],
    pdf: Mapping[str, Any],
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
    lane_separation = nested_mapping(pdf, "lane_separation")
    if lane_separation.get("content_and_file_identity_aggregated") is True:
        errors.append("pdf content and file identity lanes must not be aggregated")
    return errors


def source_guardrail_errors(track: str, payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("official_metric") is True:
        errors.append(f"{track} source report must keep official_metric=false")
    guardrails = payload.get("guardrails") if isinstance(payload.get("guardrails"), Mapping) else {}
    for key in PROTECTED_SOURCE_GUARDRAILS:
        if guardrails.get(key) is True:
            errors.append(f"{track} source guardrail violation: {key}=true")
    return errors


def remaining_blockers(tracks: Mapping[str, Mapping[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if tracks["xlsx_business_structured"].get("leakage_status") != "PASS":
        blockers.append("XLSX hidden/excluded leakage reprobe must pass before clean preflight.")
    if int(tracks["pdf_business_ocr_mm"].get("strict_gate_readiness_count") or 0) == 0:
        blockers.append("PDF layout/SearchUnit/OCR/citation metadata must be enriched before strict gate rerun.")
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
        "- Scope: diagnostic-only; official metrics and official denominators remain closed.",
        f"- Cross-track averages computed: `{str(board['cross_track_averages_computed']).lower()}`",
        "",
        "## Tracks",
        "",
        "| Track | Status | Rows | Supported/Ready | Blockers | Official rows |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
        "| TEXT/Namu V2.1 | "
        f"`{text['diagnostic_status']}` | `{text['clean_pass_rows'] + text['cleanup_rows'] + text['rewrite_unresolved_rows']}` | "
        f"`{text['citation_fully_supported_rows']}` | `{text['rewrite_unresolved_rows']}` | `{text['official_metric_input_rows']}` |",
        "| XLSX | "
        f"`{xlsx['diagnostic_status']}` | `{xlsx['generated_answer_rows']}` | "
        f"`{xlsx['citation_locator_valid_rows']}` | `{xlsx['leakage_count']}` | `{xlsx['official_metric_input_rows']}` |",
        "| PDF | "
        f"`{pdf['diagnostic_status']}` | `{pdf['input_rows']}` | `{pdf['strict_gate_readiness_count']}` | "
        f"`{pdf['rows_blocked_by_missing_layout']}` | `{pdf['official_metric_input_rows']}` |",
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
