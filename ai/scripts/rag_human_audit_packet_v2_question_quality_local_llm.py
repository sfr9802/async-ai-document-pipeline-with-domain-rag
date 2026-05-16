"""Build human audit packet v2 from verified local-LLM diagnostic drafts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_local_llm_expected_answer_generation_v1 import clean, read_json, repo_relative, utc_timestamp, write_json  # noqa: E402
from rag_question_quality_gate_v1 import evaluate_row  # noqa: E402


REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"
DEFAULT_HUMAN_AUDIT_V1 = REVIEW_DIR / "rag_human_audit_packet_v1.json"
DEFAULT_VERIFIER_REPORT = REVIEW_DIR / "rag_local_llm_expected_answer_verifier_v1.json"
DEFAULT_OUTPUT_JSON = REVIEW_DIR / "rag_human_audit_packet_v2_question_quality_local_llm.json"
DEFAULT_OUTPUT_MD = REVIEW_DIR / "rag_human_audit_packet_v2_question_quality_local_llm.md"
ALLOWED_DECISION_VALUES = [
    "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
    "EXCLUDE_FROM_OFFICIAL_GOLD",
    "DO_NOT_INCLUDE_IN_OFFICIAL_DENOMINATOR",
    "NEEDS_USER_REWRITE_OF_EXPECTED_ANSWER",
    "NEEDS_USER_REWRITE_OF_EXPECTED_EVIDENCE",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = run_packet(
        human_audit_v1_path=Path(args.human_audit_v1),
        verifier_report_path=Path(args.verifier_report),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        apply_all_human_label=args.apply_all_human_label,
        human_notes=args.human_notes,
    )
    print(
        json.dumps(
            {
                "status": packet["status"],
                "report": packet["artifact_paths"]["report_json"],
                "final_user_action_rows_by_track": packet["summary"]["final_user_action_rows_by_track"],
                "official_metric_input_rows": packet["summary"]["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if packet["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human-audit-v1", default=str(DEFAULT_HUMAN_AUDIT_V1))
    parser.add_argument("--verifier-report", default=str(DEFAULT_VERIFIER_REPORT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument(
        "--apply-all-human-label",
        choices=ALLOWED_DECISION_VALUES,
        default=None,
        help="Apply a user-provided human audit decision to every actionable row.",
    )
    parser.add_argument("--human-notes", default=None, help="Optional note copied to each labeled row.")
    return parser.parse_args(argv)


def run_packet(
    *,
    human_audit_v1_path: Path,
    verifier_report_path: Path,
    output_report: Path,
    output_md: Path,
    apply_all_human_label: str | None = None,
    human_notes: str | None = None,
) -> dict[str, Any]:
    v1 = read_json(human_audit_v1_path)
    verifier = read_json(verifier_report_path) if verifier_report_path.exists() else empty_verifier_report()
    original_rows = [row for row in v1.get("actionable_rows") or [] if isinstance(row, Mapping)]

    text_rows = [text_action_row(row) for row in original_rows if clean(row.get("track")) == "text_namu_v2_1"]
    bad_original_rows = [
        row
        for row in original_rows
        if clean(row.get("track")) in {"pdf_business_ocr_mm", "xlsx_business_structured"}
        and evaluate_row(row)["official_candidate_eligible"] is False
    ]
    bad_original_ids = {clean(row.get("query_id") or row.get("row_id")) for row in bad_original_rows}
    verified = [row for row in verifier.get("verified_candidates") or [] if isinstance(row, Mapping)]
    clean_generated = [
        generated_action_row(row, bad_original_ids=bad_original_ids)
        for row in verified
        if clean(row.get("bucket")) == "clean_candidate_for_human_audit"
    ]
    rejected_generated = [row for row in verified if clean(row.get("bucket")) != "clean_candidate_for_human_audit"]
    actionable_rows = sorted(text_rows + clean_generated, key=lambda row: (row["track"], row["row_id"]))
    if apply_all_human_label:
        for row in actionable_rows:
            row["human_label"] = apply_all_human_label
            row["human_notes"] = clean(human_notes) or (
                "User completed manual review and approved this row as an official gold candidate only; "
                "no denominator, metric, gold registry, or production promotion is opened by this label."
            )
            row["human_review_status"] = "USER_REVIEWED_APPROVED"
    by_track = Counter(row["track"] for row in actionable_rows)
    final_by_track = {track: count for track, count in sorted(by_track.items()) if count}
    official_rows = sum(1 for row in actionable_rows if row.get("official_metric_input") is not False)
    labeled_rows = [row for row in actionable_rows if clean(row.get("human_label"))]
    invalid_labeled_rows = [
        clean(row.get("query_id") or row.get("row_id"))
        for row in labeled_rows
        if clean(row.get("human_label")) not in row.get("allowed_decision_values", [])
    ]
    human_audit_completed = (
        bool(actionable_rows)
        and len(labeled_rows) == len(actionable_rows)
        and not invalid_labeled_rows
    )
    validation_errors: list[str] = []
    if official_rows != 0:
        validation_errors.append("official_metric_input_rows must remain 0")
    if any(row.get("promotion_evidence") is not False for row in actionable_rows):
        validation_errors.append("promotion_evidence must remain false")
    if any(row.get("human_review_required") is not True for row in actionable_rows):
        validation_errors.append("all action rows must require human review")
    if invalid_labeled_rows:
        validation_errors.append(f"invalid human_label rows: {', '.join(invalid_labeled_rows)}")
    packet = {
        "schema_version": "rag_human_audit_packet_v2_question_quality_local_llm",
        "generated_at": utc_timestamp(),
        "status": "HUMAN_AUDIT_PACKET_V2_READY" if not validation_errors else "FAILED_GUARDRAIL",
        "report_role": "human_audit_packet_v2_question_quality_local_llm",
        "diagnostic_only": True,
        "model_assisted_diagnostic_only": True,
        "human_audit_completed": human_audit_completed,
        "human_audit_decision_source": "user_conversation_all_rows_reviewed_ok" if human_audit_completed else None,
        "human_audit_label_counts": dict(sorted(Counter(row.get("human_label") for row in labeled_rows).items())),
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "actionable_rows": actionable_rows,
        "non_action_diagnostic_summary": {
            "rejected_bad_question_row_ids": [clean(row.get("query_id") or row.get("row_id")) for row in bad_original_rows],
            "verifier_rejected_candidate_ids": [clean(row.get("query_id")) for row in rejected_generated],
            "verifier_rejection_reasons": dict(
                sorted(Counter(reason for row in rejected_generated for reason in row.get("rejection_reasons", [])).items())
            ),
        },
        "summary": {
            "original_action_rows": int(
                nested_mapping(v1, "summary").get("total_user_action_rows") or len(original_rows)
            ),
            "rejected_bad_question_rows": len(bad_original_rows),
            "pdf_generated_candidates": sum(1 for row in verified if clean(row.get("track")) == "pdf_business_ocr_mm"),
            "pdf_manual_candidates": sum(
                1
                for row in verified
                if clean(row.get("track")) == "pdf_business_ocr_mm"
                and clean(row.get("source_packet_role")) == "manual_source_bound_pdf_context_v2"
            ),
            "pdf_local_llm_candidates": sum(
                1
                for row in verified
                if clean(row.get("track")) == "pdf_business_ocr_mm"
                and clean(row.get("source_packet_role")) != "manual_source_bound_pdf_context_v2"
            ),
            "xlsx_generated_candidates": sum(1 for row in verified if clean(row.get("track")) == "xlsx_business_structured"),
            "verifier_clean_candidates": sum(
                1 for row in verified if clean(row.get("bucket")) == "clean_candidate_for_human_audit"
            ),
            "verifier_rejected_candidates": len(rejected_generated),
            "final_user_action_rows_by_track": final_by_track,
            "human_labeled_rows": len(labeled_rows),
            "human_unlabeled_rows": len(actionable_rows) - len(labeled_rows),
            "human_audit_completed": human_audit_completed,
            "human_label_invalid_rows": invalid_labeled_rows,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
        },
        "guardrails": {
            "local_llm_outputs_promoted_to_gold": False,
            "official_denominator_registry_opened": False,
            "official_denominator_registry_mutation": False,
            "gold_registry_mutation": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_index_mutation": False,
            "production_vector_written": False,
            "tuning_run_started": False,
        },
        "source_artifacts": {
            "human_audit_v1": repo_relative(human_audit_v1_path),
            "verifier_report": repo_relative(verifier_report_path),
        },
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
        "validation": {"ok": not validation_errors, "errors": validation_errors},
    }
    write_json(output_report, packet)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(packet), encoding="utf-8")
    return packet


def text_action_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return normalize_action_row(
        {
            "row_id": clean(row.get("row_id") or row.get("query_id")),
            "query_id": clean(row.get("query_id") or row.get("row_id")),
            "track": "text_namu_v2_1",
            "question": clean(row.get("question")),
            "proposed_answer": clean(row.get("proposed_answer")),
            "proposed_evidence": clean(row.get("proposed_evidence")),
            "citation_locator": row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {},
            "issue_type": clean(row.get("issue_type") or "TEXT_EXISTING_ACTION_ROW_UNCHANGED"),
            "source_packet_role": "v1_text_action_row_preserved",
        }
    )


def generated_action_row(row: Mapping[str, Any], *, bad_original_ids: set[str] | None = None) -> dict[str, Any]:
    source_role = clean(row.get("source_packet_role")) or "verified_local_llm_diagnostic_candidate"
    issue_type = (
        "MANUAL_SOURCE_BOUND_PDF_QUESTION_EXPECTED_ANSWER_DRAFT"
        if source_role == "manual_source_bound_pdf_context_v2"
        else "LOCAL_LLM_MODEL_ASSISTED_QUESTION_EXPECTED_ANSWER_DRAFT"
    )
    query_id = clean(row.get("query_id"))
    supersedes = query_id if bad_original_ids and query_id in bad_original_ids else ""
    return normalize_action_row(
        {
            "row_id": query_id,
            "query_id": query_id,
            "track": clean(row.get("track")),
            "question": clean(row.get("rewritten_question_ko")),
            "proposed_answer": clean(row.get("expected_answer_ko")),
            "proposed_evidence": clean(row.get("supporting_evidence_quote") or " / ".join(row.get("supporting_evidence_cells", []))),
            "citation_locator": row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {},
            "issue_type": issue_type,
            "source_packet_role": source_role,
            "original_question": clean(row.get("original_question")),
            "supersedes_rejected_row_id": supersedes or None,
            "query_id_bridge_policy": "supersedes_bad_original_question_row" if supersedes else "unique_action_row",
        }
    )


def normalize_action_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized.update(
        {
            "human_review_required": True,
            "model_assisted_diagnostic_only": True,
            "official_metric_input": False,
            "promotion_evidence": False,
            "official_denominator_current": False,
            "gold_promoted": False,
            "human_label": None,
            "human_notes": None,
            "allowed_decision_values": [
                *ALLOWED_DECISION_VALUES,
            ],
        }
    )
    return normalized


def empty_verifier_report() -> dict[str, Any]:
    return {
        "verified_candidates": [],
        "bucket_counts": {},
        "summary": {"official_metric_input_rows": 0, "promotion_evidence": False},
    }


def render_markdown(packet: Mapping[str, Any]) -> str:
    summary = packet.get("summary") if isinstance(packet.get("summary"), Mapping) else {}
    return "\n".join(
        [
            "# Human Audit Packet v2: Question Quality + Local LLM",
            "",
            f"- Status: `{packet.get('status')}`",
            f"- Original action rows: `{summary.get('original_action_rows')}`",
            f"- Rejected bad question rows: `{summary.get('rejected_bad_question_rows')}`",
            f"- Verifier clean candidates: `{summary.get('verifier_clean_candidates')}`",
            f"- Verifier rejected candidates: `{summary.get('verifier_rejected_candidates')}`",
            f"- PDF manual candidates: `{summary.get('pdf_manual_candidates', 0)}`",
            f"- Final user action rows by track: `{json.dumps(summary.get('final_user_action_rows_by_track'), ensure_ascii=False, sort_keys=True)}`",
            f"- Human labeled rows: `{summary.get('human_labeled_rows')}`",
            f"- Human audit completed: `{str(summary.get('human_audit_completed')).lower()}`",
            f"- Official metric input rows: `{summary.get('official_metric_input_rows')}`",
            f"- Promotion evidence: `{str(summary.get('promotion_evidence')).lower()}`",
            "",
            "PDF rows are manually authored from source-bound context v2; XLSX rows are local-LLM diagnostic drafts. Human labels approve candidate quality only; official denominators, metrics, promotion evidence, and gold registry mutation remain closed.",
        ]
    ) + "\n"


def nested_mapping(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
