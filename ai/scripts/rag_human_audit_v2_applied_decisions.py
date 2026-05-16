"""Apply human audit packet v2 labels to official-gold candidate decisions.

This creates an applied-decision artifact for the v2 human audit packet. It
does not mutate the official denominator registry, write official gold files,
run official metrics, or promote model-assisted drafts by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"

DEFAULT_HUMAN_AUDIT_PACKET = REVIEW_DIR / "rag_human_audit_packet_v2_question_quality_local_llm.json"
DEFAULT_REGISTRY = EVAL_QUERY_DIR / "official_denominator_registry.json"
DEFAULT_OUTPUT_JSON = REVIEW_DIR / "rag_human_audit_v2_applied_decisions.json"
DEFAULT_OUTPUT_MD = REVIEW_DIR / "rag_human_audit_v2_applied_decisions.md"

SCHEMA_VERSION = "rag_human_audit_v2_applied_decisions_v1"
APPROVE_LABEL = "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE"
TRACKS = ("text_namu_v2_1", "xlsx_business_structured", "pdf_business_ocr_mm")
TRACK_DENOMINATOR_KEYS = {
    "text_namu_v2_1": "track_b_text_namu_v2_1_question_gold_v2_human_audit_approved",
    "xlsx_business_structured": "track_a_xlsx_question_gold_v2_human_audit_approved",
    "pdf_business_ocr_mm": "track_c_pdf_question_gold_v2_human_audit_approved",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_application(
        human_audit_packet_path=Path(args.human_audit_packet),
        official_denominator_registry=Path(args.official_denominator_registry),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "approved_rows_by_track": report["summary"]["approved_rows_by_track"],
                "proposed_official_metric_candidate_rows": report["summary"][
                    "proposed_official_metric_candidate_rows"
                ],
                "official_metric_input_rows": report["summary"]["official_metric_input_rows"],
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
    parser.add_argument("--human-audit-packet", default=str(DEFAULT_HUMAN_AUDIT_PACKET))
    parser.add_argument("--official-denominator-registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_application(
    *,
    human_audit_packet_path: Path,
    official_denominator_registry: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    registry_sha_before = sha256_file(official_denominator_registry)
    packet = read_json(human_audit_packet_path)
    registry_sha_after = sha256_file(official_denominator_registry)
    report = build_applied_decisions(
        human_audit_packet=packet,
        human_audit_packet_path=human_audit_packet_path,
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


def build_applied_decisions(
    *,
    human_audit_packet: Mapping[str, Any],
    human_audit_packet_path: Path,
    official_denominator_registry: Path,
    registry_sha_before: str,
    registry_sha_after: str,
) -> dict[str, Any]:
    rows = [row for row in human_audit_packet.get("actionable_rows") or [] if isinstance(row, Mapping)]
    rejected_bad_question_ids = {
        clean(value)
        for value in nested_mapping(human_audit_packet, "non_action_diagnostic_summary").get(
            "rejected_bad_question_row_ids",
            [],
        )
        if clean(value)
    }
    label_validation = validate_labels(rows, human_audit_packet)
    row_errors: list[str] = []
    approved_rows: list[dict[str, Any]] = []
    non_approved_rows: list[dict[str, Any]] = []
    for row in rows:
        label = clean(row.get("human_label"))
        qid = clean(row.get("query_id") or row.get("row_id"))
        if label == APPROVE_LABEL:
            errors = validate_approved_row(row, rejected_bad_question_ids=rejected_bad_question_ids)
            if errors:
                row_errors.extend(f"{qid}: {error}" for error in errors)
                continue
            approved_rows.append(project_candidate_row(row))
        elif label:
            non_approved_rows.append(
                {
                    "query_id": qid,
                    "track": clean(row.get("track")),
                    "human_label": label,
                    "candidate_included": False,
                }
            )

    registry_changed = registry_sha_before != registry_sha_after
    errors = []
    if clean(human_audit_packet.get("status")) != "HUMAN_AUDIT_PACKET_V2_READY":
        errors.append("human audit packet v2 must be ready")
    if human_audit_packet.get("human_audit_completed") is not True:
        errors.append("human audit packet v2 human_audit_completed must be true")
    if nested_mapping(human_audit_packet, "summary").get("human_audit_completed") is not True:
        errors.append("human audit packet v2 summary human_audit_completed must be true")
    if int_value(human_audit_packet.get("official_metric_input_rows")) != 0:
        errors.append("human audit packet official_metric_input_rows must remain 0")
    if human_audit_packet.get("promotion_evidence") is True:
        errors.append("human audit packet promotion_evidence must remain false")
    if registry_changed:
        errors.append("official denominator registry changed during applied decision generation")
    errors.extend(label_validation["errors"])
    errors.extend(row_errors)

    approved_counts = {track: 0 for track in TRACKS}
    for row in approved_rows:
        approved_counts[row["track"]] = approved_counts.get(row["track"], 0) + 1
    approved_counts = {track: count for track, count in approved_counts.items() if count}
    total_approved = sum(approved_counts.values())
    status = (
        "HUMAN_AUDIT_V2_APPLIED_DECISIONS_READY"
        if not errors
        else "HUMAN_AUDIT_V2_APPLIED_DECISIONS_FAIL_CLOSED"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "human_audit_v2_applied_decisions",
        "report_only": True,
        "candidate_gold_status": "human_approved_candidate_not_current_official_denominator",
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "proposed_official_metric_candidate_rows": total_approved,
        "approved_candidate_rows": sorted(approved_rows, key=lambda row: (row["track"], row["query_id"])),
        "non_approved_action_rows": sorted(non_approved_rows, key=lambda row: (row["track"], row["query_id"])),
        "track_denominator_key_preview": {
            track: TRACK_DENOMINATOR_KEYS[track] for track in approved_counts
        },
        "summary": {
            "source_action_rows": len(rows),
            "human_labeled_rows": label_validation["labeled_rows"],
            "approved_gold_candidate_rows": total_approved,
            "approved_rows_by_track": approved_counts,
            "non_approved_rows_by_label": label_validation["non_approved_rows_by_label"],
            "proposed_official_metric_candidate_rows": total_approved,
            "proposed_official_metric_candidate_rows_by_track": approved_counts,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "superseded_rejected_bad_question_rows": sum(
                1
                for row in approved_rows
                if clean(row.get("supersedes_rejected_row_id")) in rejected_bad_question_ids
            ),
        },
        "application_scope": {
            "human_decisions_applied": True,
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
        "guardrails": {
            "official_denominator_registry_path": repo_relative(official_denominator_registry),
            "official_denominator_registry_sha256_before": registry_sha_before,
            "official_denominator_registry_sha256_after": registry_sha_after,
            "official_denominator_registry_changed": registry_changed,
            "official_denominator_registry_mutation": False,
            "official_denominator_opened": False,
            "official_metric_executed": False,
            "official_metric_input_rows_remain_zero": True,
            "promotion_evidence_created": False,
            "model_assisted_outputs_promoted_without_human_approval": False,
            "gold_registry_mutation": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_written": False,
            "tuning_run_started": False,
        },
        "source_artifacts": {
            "human_audit_packet_v2": repo_relative(human_audit_packet_path),
            "official_denominator_registry": repo_relative(official_denominator_registry),
        },
        "artifact_paths": {"report_json": "", "report_md": ""},
        "validation": {"ok": not errors, "errors": sorted(dict.fromkeys(errors))},
    }


def validate_labels(rows: list[Mapping[str, Any]], packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    counts: Counter[str] = Counter()
    missing: list[str] = []
    invalid: list[str] = []
    for row in rows:
        qid = clean(row.get("query_id") or row.get("row_id"))
        label = clean(row.get("human_label"))
        allowed = row.get("allowed_decision_values") if isinstance(row.get("allowed_decision_values"), list) else []
        allowed_values = {clean(value) for value in allowed}
        if not label:
            missing.append(qid)
            continue
        counts[label] += 1
        if label not in allowed_values:
            invalid.append(qid)
    if not rows:
        errors.append("human audit packet has no actionable rows")
    if missing:
        errors.append(f"human audit rows missing human_label: {', '.join(missing)}")
    if invalid:
        errors.append(f"human audit rows have invalid human_label: {', '.join(invalid)}")
    summary = nested_mapping(packet, "summary")
    if "human_labeled_rows" in summary and int_value(summary.get("human_labeled_rows")) != sum(counts.values()):
        errors.append("human audit human_labeled_rows summary mismatch")
    if "human_unlabeled_rows" in summary and int_value(summary.get("human_unlabeled_rows")) != len(missing):
        errors.append("human audit human_unlabeled_rows summary mismatch")
    expected_counts = packet.get("human_audit_label_counts")
    if isinstance(expected_counts, Mapping):
        normalized_expected = {clean(key): int_value(value) for key, value in expected_counts.items()}
        if normalized_expected != dict(sorted(counts.items())):
            errors.append("human audit label counts mismatch")
    non_approved = {label: count for label, count in sorted(counts.items()) if label != APPROVE_LABEL}
    return {
        "errors": errors,
        "labeled_rows": sum(counts.values()),
        "label_counts": dict(sorted(counts.items())),
        "non_approved_rows_by_label": non_approved,
    }


def validate_approved_row(row: Mapping[str, Any], *, rejected_bad_question_ids: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    qid = clean(row.get("query_id") or row.get("row_id"))
    question = clean(row.get("question"))
    answer = clean(row.get("proposed_answer"))
    evidence = clean(row.get("proposed_evidence"))
    track = clean(row.get("track"))
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    if track not in TRACKS:
        errors.append(f"unknown track {track!r}")
    if qid.startswith("expanded_pdf_file_lookup") or qid.startswith("expanded_xlsx_constraint"):
        errors.append("placeholder expanded query id cannot enter candidate decisions")
    if not question:
        errors.append("question is empty")
    if not answer:
        errors.append("proposed answer is empty")
    if not evidence:
        errors.append("proposed evidence is empty")
    if question and qid and question == qid:
        errors.append("question equals query_id")
    if question and answer and question == answer:
        errors.append("question equals proposed answer")
    if rejected_bad_question_ids and qid in rejected_bad_question_ids:
        if clean(row.get("supersedes_rejected_row_id")) != qid:
            errors.append("query_id overlaps rejected bad question row without explicit supersedes bridge")
        if clean(row.get("query_id_bridge_policy")) != "supersedes_bad_original_question_row":
            errors.append("query_id overlap bridge policy must be supersedes_bad_original_question_row")
    if row.get("human_review_required") is not True:
        errors.append("human_review_required must be true")
    if row.get("official_metric_input") is not False:
        errors.append("official_metric_input must remain false")
    if row.get("promotion_evidence") is not False:
        errors.append("promotion_evidence must remain false")
    if row.get("gold_promoted") is not False:
        errors.append("gold_promoted must remain false")
    if track == "pdf_business_ocr_mm":
        for field in ("page", "bbox", "search_unit_id"):
            if not locator.get(field):
                errors.append(f"PDF citation locator missing {field}")
        if clean(row.get("content_evidence_lane")) == "pdf_file_identity":
            errors.append("PDF FILE identity lane cannot become CONTENT candidate")
        if clean(row.get("source_packet_role")) == "pdf_file_identity":
            errors.append("PDF file identity source role cannot become CONTENT candidate")
    if track == "xlsx_business_structured":
        if not (locator.get("workbook") or locator.get("file")):
            errors.append("XLSX citation locator missing workbook/file")
        if not locator.get("sheet"):
            errors.append("XLSX citation locator missing sheet")
        if not (locator.get("range") or locator.get("cells") or locator.get("matched_cells")):
            errors.append("XLSX citation locator missing range/cells")
        for flag in ("hidden", "excluded", "pending", "hidden_or_excluded_or_pending"):
            if row.get(flag) is True:
                errors.append(f"XLSX {flag} row cannot enter candidates")
    return errors


def project_candidate_row(row: Mapping[str, Any]) -> dict[str, Any]:
    track = clean(row.get("track"))
    expected_answer, normalization = normalized_expected_answer(row)
    return {
        "query_id": clean(row.get("query_id") or row.get("row_id")),
        "row_id": clean(row.get("row_id") or row.get("query_id")),
        "track": track,
        "question": clean(row.get("question")),
        "expected_answer": expected_answer,
        "supporting_evidence": clean(row.get("proposed_evidence")),
        "citation_locator": row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {},
        "human_label": APPROVE_LABEL,
        "human_review_status": clean(row.get("human_review_status")),
        "human_review_required": True,
        "model_assisted_source": bool(row.get("model_assisted_diagnostic_only")),
        "model_assisted_diagnostic_only_before_human_approval": bool(row.get("model_assisted_diagnostic_only")),
        "candidate_gold_status": "human_approved_candidate_not_current_official_denominator",
        "official_denominator_candidate": True,
        "official_denominator_current": False,
        "official_metric_input": False,
        "promotion_evidence": False,
        "gold_promoted": False,
        "track_denominator_key_preview": TRACK_DENOMINATOR_KEYS.get(track, ""),
        "issue_type": clean(row.get("issue_type")),
        "source_packet_role": clean(row.get("source_packet_role")),
        "supersedes_rejected_row_id": clean(row.get("supersedes_rejected_row_id")),
        "query_id_bridge_policy": clean(row.get("query_id_bridge_policy")),
        "expected_answer_normalization": normalization,
    }


def normalized_expected_answer(row: Mapping[str, Any]) -> tuple[str, str]:
    answer = clean(row.get("proposed_answer"))
    if clean(row.get("track")) != "text_namu_v2_1":
        return answer, "unchanged"
    marker = "**Short answer:**"
    if marker not in answer:
        return answer, "unchanged"
    tail = answer.split(marker, 1)[1]
    short = tail.split("**Supporting passages:**", 1)[0].strip()
    return short, "extracted_short_answer_from_text_report"


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = nested_mapping(report, "summary")
    lines = [
        "# Human Audit v2 Applied Decisions",
        "",
        f"- Status: `{report['status']}`",
        f"- Candidate gold status: `{report['candidate_gold_status']}`",
        f"- Source action rows: `{summary.get('source_action_rows')}`",
        f"- Approved candidate rows: `{summary.get('approved_gold_candidate_rows')}`",
        f"- Approved rows by track: `{json.dumps(summary.get('approved_rows_by_track'), ensure_ascii=False, sort_keys=True)}`",
        f"- Proposed official metric candidate rows: `{summary.get('proposed_official_metric_candidate_rows')}`",
        f"- Official metric input rows: `{summary.get('official_metric_input_rows')}`",
        f"- Promotion evidence: `{str(summary.get('promotion_evidence')).lower()}`",
        f"- Registry changed: `{str(nested_mapping(report, 'guardrails').get('official_denominator_registry_changed')).lower()}`",
        "",
        "Human labels are applied to candidate decisions only. Registry mutation, official metric input rows, production writes, and tuning remain closed.",
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
