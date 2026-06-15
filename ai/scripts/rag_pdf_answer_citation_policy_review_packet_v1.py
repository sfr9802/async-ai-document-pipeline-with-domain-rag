"""Build the PDF answer/citation diagnostic policy review packet.

This packet wraps deterministic PDF answer/citation diagnostic review rows into
a report-only policy surface. It keeps official metrics, official denominators,
production indexes, candidate artifacts, immutable baselines, and gold
registries closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"

DEFAULT_DIAGNOSTIC_REPORT = REPORT_DIR / "pdf_answer_citation_diagnostic_report.json"
DEFAULT_REVIEW_INPUT = REPORT_DIR / "pdf_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "rag_pdf_answer_citation_policy_review_packet_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "rag_pdf_answer_citation_policy_review_packet_v1.md"

SCHEMA_VERSION = "rag_pdf_answer_citation_policy_review_packet_v1"
TRACK = "pdf_business_ocr_mm"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = run_packet(
        diagnostic_report=Path(args.diagnostic_report),
        review_input_jsonl=Path(args.review_input_jsonl),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": packet["status"],
                "report": packet["artifact_paths"]["report_json"],
                "input_rows": packet["input_rows"],
                "clean_pass_rows": packet["clean_pass_rows"],
                "official_metric_input_rows": packet["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if packet["status"] != "FAILED_GUARDRAIL" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostic-report", default=str(DEFAULT_DIAGNOSTIC_REPORT))
    parser.add_argument("--review-input-jsonl", default=str(DEFAULT_REVIEW_INPUT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_packet(
    *,
    diagnostic_report: Path,
    review_input_jsonl: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    packet = build_packet(diagnostic_report=diagnostic_report, review_input_jsonl=review_input_jsonl)
    packet["artifact_paths"]["report_json"] = repo_relative(output_report)
    packet["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, packet)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(packet), encoding="utf-8")
    return packet


def build_packet(*, diagnostic_report: Path, review_input_jsonl: Path) -> dict[str, Any]:
    diagnostic = read_json(diagnostic_report)
    review_input_exists = review_input_jsonl.exists()
    rows = read_jsonl(review_input_jsonl) if review_input_exists else []
    row_counts = row_guard_counts(rows)
    official_rows = int_value(diagnostic.get("official_metric_input_rows")) + sum(
        1 for row in rows if row.get("official_metric_input") is not False
    )
    expected_review_rows = expected_review_input_rows(diagnostic)
    generated_answer_rows = len(rows)
    answer_support_pass = sum(1 for row in rows if row.get("answer_claims_supported") is True)
    citation_valid = sum(1 for row in rows if row.get("citation_locator_valid") is True)
    clean_pass_rows = sum(1 for row in rows if clean(row.get("bucket")) == "clean_pass")
    cleanup_rows = sum(
        1
        for row in rows
        if clean(row.get("bucket"))
        in {"cleanup_required", "answer_rewrite_required", "citation_locator_incomplete", "unsupported_answer"}
    )
    unresolved_rows = sum(1 for row in rows if clean(row.get("bucket")) == "unresolved_diagnostic")
    lane_policy_blocked_rows = sum(1 for row in rows if clean(row.get("bucket")) == "lane_policy_blocked")
    validation_errors = validation_errors_for(
        diagnostic=diagnostic,
        rows=rows,
        official_rows=official_rows,
        review_input_exists=review_input_exists,
        expected_review_rows=expected_review_rows,
    )
    lane_or_evidence_blocked = (
        lane_policy_blocked_rows > 0
        or row_counts["file_identity_rows_used_as_content_evidence"] > 0
        or row_counts["filename_only_identity_accepted"] > 0
        or row_counts["policy_excluded_rows_used"] > 0
        or row_counts["diagnostic_fallback_rows_used"] > 0
    )
    if validation_errors:
        status = "FAILED_GUARDRAIL"
    elif lane_or_evidence_blocked:
        status = "DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LANE_OR_EVIDENCE_GUARD"
    elif clean_pass_rows == generated_answer_rows and generated_answer_rows > 0:
        status = "DIAGNOSTIC_POLICY_PACKET_READY"
    else:
        status = "DIAGNOSTIC_POLICY_PACKET_READY_WITH_CLEANUP"
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "pdf_answer_citation_policy_review_packet",
        "track": TRACK,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "input_rows": generated_answer_rows,
        "strict_ready_rows": int_value(diagnostic.get("strict_ready_rows")) or generated_answer_rows,
        "expected_review_input_rows": expected_review_rows,
        "generated_answer_rows": generated_answer_rows,
        "answer_support_pass_count": answer_support_pass,
        "citation_locator_valid_count": citation_valid,
        "clean_pass_rows": clean_pass_rows,
        "cleanup_rows": cleanup_rows,
        "unresolved_rows": unresolved_rows,
        "lane_policy_blocked_rows": lane_policy_blocked_rows,
        "answer_rewrite_required_rows": sum(1 for row in rows if clean(row.get("bucket")) == "answer_rewrite_required"),
        "citation_locator_incomplete_rows": sum(1 for row in rows if clean(row.get("bucket")) == "citation_locator_incomplete"),
        "unsupported_answer_rows": sum(1 for row in rows if clean(row.get("bucket")) == "unsupported_answer"),
        "official_metric_input_rows": official_rows,
        "denominator_policy": "closed",
        "answer_generation_scope": "diagnostic_only",
        "pdf_answer_generation_denominator_opened": False,
        "content_file_identity_lane_merge": False,
        "filename_only_identity_accepted": row_counts["filename_only_identity_accepted"] > 0,
        "file_identity_rows_used_as_content_evidence": row_counts["file_identity_rows_used_as_content_evidence"],
        "policy_excluded_rows_used": row_counts["policy_excluded_rows_used"],
        "diagnostic_fallback_rows_used": row_counts["diagnostic_fallback_rows_used"],
        "bucket_counts": {
            "clean_pass": clean_pass_rows,
            "cleanup_rows": cleanup_rows,
            "unresolved_diagnostic": unresolved_rows,
            "lane_policy_blocked": lane_policy_blocked_rows,
        },
        "guardrails": {
            "official_metric_input_rows_remain_zero": official_rows == 0,
            "official_denominator_registry_opened": False,
            "official_denominator_registry_mutation": False,
            "gold_registry_mutation": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_index_mutation": False,
            "production_vector_written": False,
            "promotion_evidence_created": False,
            "model_assisted_outputs_promoted_to_gold": False,
            "content_file_identity_lane_merge": False,
            "filename_only_identity_accepted": row_counts["filename_only_identity_accepted"] > 0,
            "diagnostic_fallback_rows_used": row_counts["diagnostic_fallback_rows_used"] > 0,
        },
        "source_artifacts": {
            "diagnostic_report": file_identity(diagnostic_report),
            "review_input_jsonl": file_identity(review_input_jsonl),
        },
        "artifact_paths": {
            "report_json": "",
            "report_md": "",
        },
        "validation": {
            "ok": not validation_errors,
            "errors": validation_errors,
        },
        "next_safe_actions": [
            "Keep PDF answer/citation rows diagnostic-only until human audit opens a separate denominator policy.",
            "Keep official metrics and official denominators closed.",
            "Keep filename-only identity blocked and CONTENT/FILE lanes separate.",
        ],
    }
    return packet


def row_guard_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "file_identity_rows_used_as_content_evidence": sum(
            1 for row in rows if row.get("no_file_identity_lane_used_as_content_evidence") is not True
        ),
        "filename_only_identity_accepted": sum(
            1 for row in rows if row.get("no_filename_only_identity_acceptance") is not True
        ),
        "policy_excluded_rows_used": sum(1 for row in rows if row.get("no_policy_excluded_row_used") is not True),
        "diagnostic_fallback_rows_used": sum(1 for row in rows if row.get("no_diagnostic_fallback_row_used") is not True),
    }


def validation_errors_for(
    *,
    diagnostic: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    official_rows: int,
    review_input_exists: bool,
    expected_review_rows: int,
) -> list[str]:
    errors: list[str] = []
    if not review_input_exists:
        errors.append("pdf answer/citation review input JSONL is missing")
    if not rows:
        errors.append("pdf answer/citation review input JSONL must contain row-level audit data")
    if expected_review_rows > 0 and len(rows) != expected_review_rows:
        errors.append(
            f"pdf answer/citation review input row count must match diagnostic expected rows: {len(rows)} != {expected_review_rows}"
        )
    if diagnostic.get("official_metric") is True:
        errors.append("pdf diagnostic report must keep official_metric=false")
    if diagnostic.get("promotion_evidence") is True:
        errors.append("pdf diagnostic report must keep promotion_evidence=false")
    if clean(diagnostic.get("status")) != "PASS":
        errors.append("pdf diagnostic report status must be PASS")
    validation = diagnostic.get("validation") if isinstance(diagnostic.get("validation"), Mapping) else {}
    if validation.get("ok") is not True:
        errors.append("pdf diagnostic report validation.ok must be true")
    if diagnostic.get("pdf_answer_generation_denominator_opened") is True:
        errors.append("pdf_answer_generation_denominator_opened must remain false")
    if official_rows != 0:
        errors.append("official_metric_input_rows must remain 0")
    if any(row.get("promotion_evidence") is True for row in rows):
        errors.append("review rows must keep promotion_evidence=false")
    guardrails = diagnostic.get("guardrails") if isinstance(diagnostic.get("guardrails"), Mapping) else {}
    for key in (
        "official_denominator_registry_opened",
        "official_denominator_registry_mutation",
        "gold_registry_mutation",
        "candidate_artifact_mutation",
        "immutable_baseline_mutation",
        "production_namespace_vector_index_mutation",
        "production_vector_index_mutation",
        "production_vector_written",
        "promotion_evidence_created",
        "model_assisted_outputs_promoted_to_gold",
    ):
        if diagnostic.get(key) is True or guardrails.get(key) is True:
            errors.append(f"pdf diagnostic guardrail violation: {key}=true")
    return errors


def expected_review_input_rows(diagnostic: Mapping[str, Any]) -> int:
    generated = int_value(diagnostic.get("generated_answer_rows"))
    strict_ready = int_value(diagnostic.get("strict_ready_rows"))
    if generated:
        return generated
    return strict_ready


def render_markdown(packet: Mapping[str, Any]) -> str:
    lines = [
        "# PDF Answer/Citation Policy Review Packet v1",
        "",
        f"- Status: `{packet['status']}`",
        "- Scope: diagnostic-only; official metrics and denominators remain closed.",
        f"- Input rows: `{packet['input_rows']}`",
        f"- Strict-ready rows: `{packet['strict_ready_rows']}`",
        f"- Generated answer rows: `{packet['generated_answer_rows']}`",
        f"- Answer support pass: `{packet['answer_support_pass_count']}`",
        f"- Citation locator valid: `{packet['citation_locator_valid_count']}`",
        f"- Clean pass rows: `{packet['clean_pass_rows']}`",
        f"- Cleanup rows: `{packet['cleanup_rows']}`",
        f"- Unresolved rows: `{packet['unresolved_rows']}`",
        f"- Lane policy blocked rows: `{packet['lane_policy_blocked_rows']}`",
        f"- Official metric input rows: `{packet['official_metric_input_rows']}`",
        "",
        "## Guardrails",
        "",
    ]
    for key, value in packet["guardrails"].items():
        lines.append(f"- `{key}`: `{json.dumps(value, ensure_ascii=False)}`")
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() else None,
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
