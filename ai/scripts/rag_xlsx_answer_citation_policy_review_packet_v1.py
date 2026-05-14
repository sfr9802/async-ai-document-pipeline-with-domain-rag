"""Build the XLSX answer/citation diagnostic policy review packet.

This script wraps the current strict-silver answer/citation diagnostic rows and
the latest hidden/excluded leakage reprobe into a report-only policy packet.
It does not open official metrics, official denominators, production indexes,
candidate artifacts, immutable baselines, or gold registries.
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
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"

DEFAULT_ANSWER_REPORT = REPORT_DIR / "xlsx_answer_citation_diagnostic_report.json"
DEFAULT_LEAKAGE_REPROBE = REPORT_DIR / "xlsx_answer_citation_hidden_excluded_leakage_reprobe.json"
DEFAULT_REVIEW_INPUT = REPORT_DIR / "xlsx_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "rag_xlsx_answer_citation_policy_review_packet_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "rag_xlsx_answer_citation_policy_review_packet_v1.md"

SCHEMA_VERSION = "rag_xlsx_answer_citation_policy_review_packet_v1"
TRACK = "xlsx_business_structured"
PUBLIC_SURFACES = {"debug_public", "public", "query", "official_denominator"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = run_packet(
        answer_report=Path(args.answer_report),
        leakage_reprobe=Path(args.leakage_reprobe),
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
                "leakage_raw_status": packet["leakage_raw_status"],
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
    parser.add_argument("--answer-report", default=str(DEFAULT_ANSWER_REPORT))
    parser.add_argument("--leakage-reprobe", default=str(DEFAULT_LEAKAGE_REPROBE))
    parser.add_argument("--review-input-jsonl", default=str(DEFAULT_REVIEW_INPUT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_packet(
    *,
    answer_report: Path,
    leakage_reprobe: Path,
    review_input_jsonl: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    packet = build_packet(
        answer_report=answer_report,
        leakage_reprobe=leakage_reprobe,
        review_input_jsonl=review_input_jsonl,
    )
    packet["artifact_paths"]["report_json"] = repo_relative(output_report)
    packet["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, packet)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(packet), encoding="utf-8")
    return packet


def build_packet(*, answer_report: Path, leakage_reprobe: Path, review_input_jsonl: Path) -> dict[str, Any]:
    answer = read_json(answer_report)
    leakage = read_json(leakage_reprobe)
    review_rows = read_jsonl(review_input_jsonl) if review_input_jsonl.exists() else []
    answer_counts = nested_mapping(answer, "counts")
    preview = nested_mapping(answer, "diagnostic_metric_preview")
    verifier = nested_mapping(answer, "verifier_counts")
    leakage_counts = nested_mapping(leakage, "counts")
    leakage_raw_status = clean(leakage.get("status") or preview.get("leakage_status") or nested_mapping(answer, "leakage_reprobe").get("status"))
    leakage_surface_counts = surface_counts(leakage)
    leakage_total = int_value(leakage_counts.get("surface_leakage_count"))
    if leakage_total == 0:
        leakage_total = sum(leakage_surface_counts.values())
    annotation_only_allowlist_used = allowlist_used(leakage)
    input_rows = int_value(answer_counts.get("generated_review_input_rows")) or len(review_rows)
    answer_support_pass = (
        int_value(answer_counts.get("answer_claim_supported_rows"))
        or int_value(verifier.get("answer_claim_support_pass"))
        or int_value(preview.get("citation_fully_supported_rows"))
    )
    citation_locator_valid = (
        int_value(answer_counts.get("citation_locator_resolved_rows"))
        or int_value(verifier.get("citation_locator_pass"))
        or int_value(preview.get("citation_locator_valid_rows"))
    )
    official_rows = int_value(answer.get("official_metric_input_rows")) + sum(
        1 for row in review_rows if row.get("official_metric_input") is not False
    )
    leakage_failed = leakage_raw_status != "PASS" or leakage_total > 0
    answer_citation_clean = min(answer_support_pass, citation_locator_valid)
    clean_pass_rows = 0 if leakage_failed else answer_citation_clean
    cleanup_rows = max(input_rows - clean_pass_rows, 0)
    validation_errors = validation_errors_for(answer=answer, official_metric_input_rows=official_rows)
    status = "DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LEAKAGE" if leakage_failed else "DIAGNOSTIC_POLICY_PACKET_READY"
    if validation_errors:
        status = "FAILED_GUARDRAIL"
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "xlsx_answer_citation_policy_review_packet",
        "track": TRACK,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "answer_generation_run": False,
        "input_rows": input_rows,
        "strict_silver_rows": int_value(answer_counts.get("input_strict_silver_rows")) or input_rows,
        "pending_excluded_rows": excluded_count(answer, "pending_evidence"),
        "normalized_excluded_rows": int_value(leakage_counts.get("normalized_excluded_row_count"))
        or excluded_count(answer, "normalized_excluded"),
        "hidden_negative_rows": int_value(leakage_counts.get("normalized_hidden_negative_row_count"))
        or int_value(leakage_counts.get("hidden_negative_row_count"))
        or excluded_count(answer, "normalized_hidden_negative"),
        "answer_support_pass_count": answer_support_pass,
        "citation_locator_valid_count": citation_locator_valid,
        "leakage_raw_status": leakage_raw_status or "UNKNOWN",
        "leakage_surface_counts": leakage_surface_counts,
        "leakage_raw_total": leakage_total,
        "annotation_only_allowlist_used": annotation_only_allowlist_used,
        "official_metric_input_rows": official_rows,
        "metric_preview_status": "FAIL_CLOSED_BY_LEAKAGE" if leakage_failed else "DIAGNOSTIC_POLICY_PACKET_READY",
        "denominator_policy": "closed",
        "diagnostic_metric_preview": {
            "generated_answer_rows": input_rows,
            "pre_leakage_support_pass_rows": answer_citation_clean,
            "answer_citation_clean_pass_rows": answer_citation_clean,
            "clean_pass_rows": clean_pass_rows,
            "cleanup_rows": cleanup_rows,
            "blocked_by_leakage_rows": input_rows if leakage_failed else 0,
            "rewrite_unresolved_rows": int_value(preview.get("rewrite_unresolved_rows")),
            "citation_fully_supported_rows": answer_support_pass,
            "citation_locator_valid_rows": citation_locator_valid,
            "leakage_count": leakage_total,
            "leakage_status": leakage_raw_status,
            "official_metric_input_rows": official_rows,
            "official_metric": False,
            "promotion_evidence": False,
            "status": "FAIL_CLOSED_BY_LEAKAGE" if leakage_failed else "PASS",
        },
        "leakage_by_row": leakage_rows(leakage=leakage, annotation_only_allowlist_used=annotation_only_allowlist_used),
        "bucket_counts": {
            "clean_pass_rows": clean_pass_rows,
            "cleanup_rows": cleanup_rows,
            "blocked_by_leakage_rows": input_rows if leakage_failed else 0,
            "official_metric_candidate_rows": 0,
        },
        "terminology": {
            "pre_leakage_support_pass_rows": (
                "rows where answer support and citation locator checks passed before leakage fail-closed gating"
            ),
            "answer_citation_clean_pass_rows": (
                "backward-compatible alias for pre_leakage_support_pass_rows"
            ),
            "clean_pass_rows": (
                "final diagnostic clean rows after raw leakage gating; forced to 0 while leakage_raw_status is FAIL"
            ),
        },
        "guardrails": {
            "official_metric_input_rows_remain_zero": official_rows == 0,
            "official_denominator_registry_opened": False,
            "official_denominator_registry_mutation": False,
            "production_namespace_mutated": False,
            "production_vector_index_mutated": False,
            "production_vector_written": False,
            "candidate_artifact_mutated": False,
            "immutable_baseline_mutated": False,
            "gold_registry_mutation": False,
            "promotion_evidence_created": False,
            "model_assisted_outputs_promoted_to_gold": False,
            "annotation_only_allowlist_promoted_to_pass": False,
        },
        "source_artifacts": {
            "answer_report": file_identity(answer_report),
            "leakage_reprobe": file_identity(leakage_reprobe),
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
        "next_safe_actions": next_safe_actions(leakage_raw_status=leakage_raw_status or "UNKNOWN"),
    }
    return packet


def next_safe_actions(*, leakage_raw_status: str) -> list[str]:
    if clean(leakage_raw_status) == "PASS":
        return [
            "Keep raw leakage PASS only while public answer/citation/debug/public/official surfaces remain free of hidden or excluded tokens.",
            "Treat any future private formatter_input scan separately from public surface leakage.",
            "Do not open answer denominators or official metric rows from this packet.",
        ]
    return [
        "Keep raw leakage status as FAIL until answer/citation/debug/public/official surfaces no longer expose hidden or excluded tokens.",
        "Treat strict-evidence token allowlist as annotation-only; do not use it to pass raw leakage.",
        "Do not open answer denominators or official metric rows from this packet.",
    ]


def surface_counts(leakage: Mapping[str, Any]) -> dict[str, int]:
    coverage = nested_mapping(leakage, "surface_coverage")
    counts: dict[str, int] = {}
    for surface, payload in sorted(coverage.items()):
        if isinstance(payload, Mapping):
            count = int_value(payload.get("leakage_count"))
            if count or clean(payload.get("status")) in {"FAIL", "PASS"}:
                counts[clean(surface)] = count
    return counts


def allowlist_used(leakage: Mapping[str, Any]) -> bool:
    policy = nested_mapping(leakage, "allowlist_policy")
    return bool(
        policy.get("strict_evidence_shared_token_allowlist") is True
        and clean(policy.get("status_effect")) == "annotation_only"
        and int_value(policy.get("allowlisted_surface_violation_count")) > 0
    )


def leakage_rows(*, leakage: Mapping[str, Any], annotation_only_allowlist_used: bool) -> list[dict[str, Any]]:
    rows = leakage.get("query_results") if isinstance(leakage.get("query_results"), list) else []
    results: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        violations = row.get("surface_violations") if isinstance(row.get("surface_violations"), list) else []
        surfaces = sorted(
            {
                clean(violation.get("surface"))
                for violation in violations
                if isinstance(violation, Mapping) and clean(violation.get("surface"))
            }
        )
        raw_count = int_value(row.get("surface_violation_count")) or len(surfaces)
        if raw_count == 0:
            continue
        results.append(
            {
                "query_id": clean(row.get("query_id")),
                "row_source": clean(row.get("row_source")),
                "hidden_negative": bool(row.get("hidden_negative")),
                "surfaces": surfaces,
                "raw_surface_violation_count": raw_count,
                "annotation_only_allowlisted": annotation_only_allowlist_used,
                "classifications": classify_leakage_row(
                    row=row,
                    surfaces=surfaces,
                    annotation_only_allowlist_used=annotation_only_allowlist_used,
                ),
            }
        )
    return results


def classify_leakage_row(
    *,
    row: Mapping[str, Any],
    surfaces: Sequence[str],
    annotation_only_allowlist_used: bool,
) -> list[str]:
    classifications: set[str] = set()
    if bool(row.get("hidden_negative")):
        classifications.add("hidden_negative_token")
    if clean(row.get("row_source")) == "normalized_excluded":
        classifications.add("normalized_excluded_row_token")
    if any(surface in PUBLIC_SURFACES for surface in surfaces):
        classifications.add("policy_excluded_public_surface")
    if "answer" in surfaces:
        classifications.add("answer_text_leaks_excluded_context")
    if "citation" in surfaces:
        classifications.add("citation_locator_leaks_excluded_context")
    if "official_denominator" in surfaces:
        classifications.add("official_denominator_surface_leakage")
    if annotation_only_allowlist_used:
        classifications.add("ambiguous_strict_evidence_token_annotation_only")
    return sorted(classifications)


def validation_errors_for(*, answer: Mapping[str, Any], official_metric_input_rows: int) -> list[str]:
    errors: list[str] = []
    if answer.get("diagnostic_only") is not True:
        errors.append("xlsx source answer/citation report must remain diagnostic_only=true")
    if answer.get("official_metric") is True:
        errors.append("xlsx source answer/citation report must keep official_metric=false")
    if answer.get("promotion_evidence") is True:
        errors.append("xlsx source answer/citation report must keep promotion_evidence=false")
    if official_metric_input_rows != 0:
        errors.append("official_metric_input_rows must remain 0")
    guardrails = nested_mapping(answer, "guardrails")
    for key in (
        "official_denominator_registry_opened",
        "official_denominator_registry_mutation",
        "official_denominator_registry_changed",
        "gold_registry_mutation",
        "production_namespace_mutated",
        "production_vector_index_mutated",
        "production_vector_written",
        "candidate_artifact_mutated",
        "immutable_baseline_mutated",
        "promotion_evidence_created",
        "model_assisted_outputs_promoted_to_gold",
    ):
        if guardrails.get(key) is True:
            errors.append(f"xlsx source guardrail violation: {key}=true")
    return errors


def excluded_count(answer: Mapping[str, Any], key: str) -> int:
    excluded = nested_mapping(answer, "excluded_query_ids")
    value = excluded.get(key)
    return len(value) if isinstance(value, list) else 0


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(packet: Mapping[str, Any]) -> str:
    lines = [
        "# XLSX Answer/Citation Policy Review Packet v1",
        "",
        f"- Status: `{packet['status']}`",
        "- Scope: diagnostic-only; official metrics and denominators remain closed.",
        f"- Input rows: `{packet['input_rows']}`",
        f"- Strict silver rows: `{packet['strict_silver_rows']}`",
        f"- Pending excluded rows: `{packet['pending_excluded_rows']}`",
        f"- Normalized excluded rows: `{packet['normalized_excluded_rows']}`",
        f"- Hidden-negative rows: `{packet['hidden_negative_rows']}`",
        f"- Answer support pass count: `{packet['answer_support_pass_count']}`",
        f"- Citation locator valid count: `{packet['citation_locator_valid_count']}`",
        f"- Pre-leakage support pass rows: `{packet['diagnostic_metric_preview']['pre_leakage_support_pass_rows']}`",
        f"- Final clean pass rows: `{packet['diagnostic_metric_preview']['clean_pass_rows']}`",
        f"- Leakage raw status: `{packet['leakage_raw_status']}`",
        f"- Leakage surface counts: `{json.dumps(packet['leakage_surface_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Annotation-only allowlist used: `{str(packet['annotation_only_allowlist_used']).lower()}`",
        f"- Official metric input rows: `{packet['official_metric_input_rows']}`",
        f"- Promotion evidence: `{str(packet['promotion_evidence']).lower()}`",
        f"- Metric preview status: `{packet['metric_preview_status']}`",
        f"- Denominator policy: `{packet['denominator_policy']}`",
        "",
        "## Buckets",
        "",
    ]
    for key, value in packet["bucket_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Terminology",
            "",
            "- `pre_leakage_support_pass_rows` is the answer/citation support count before raw leakage gating.",
            "- `answer_citation_clean_pass_rows` is kept as a backward-compatible alias.",
            "- `clean_pass_rows` is the final fail-closed diagnostic clean count and remains `0` while raw leakage is `FAIL`.",
        ]
    )
    lines.extend(["", "## Next Safe Actions", ""])
    for action in packet["next_safe_actions"]:
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


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
