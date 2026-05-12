"""Build a report-only gold policy decision draft from the resolution packet.

The draft translates the reviewed-gold resolution packet into conservative
proposed user decisions. It does not open or mutate the official denominator,
run retrieval/ranking experiments, or change production namespaces.
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
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"

DEFAULT_PACKET_JSON = REVIEW_DIR / "rag_gold_policy_resolution_packet_v1.json"
DEFAULT_PACKET_MD = REVIEW_DIR / "rag_gold_policy_resolution_packet_v1.md"
DEFAULT_NORMALIZATION_REPORT = REPORT_DIR / "rag_reviewed_gold_policy_normalization_report.json"
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"

DEFAULT_JSON_OUTPUT = REVIEW_DIR / "rag_gold_policy_decision_draft_v1.json"
DEFAULT_MD_OUTPUT = REVIEW_DIR / "rag_gold_policy_decision_draft_v1.md"

SCHEMA_VERSION = "rag_gold_policy_decision_draft_v1"

XLSX_INCLUDE_DECISION = "INCLUDE_AS_GOLD_V0_1_CANDIDATE"
XLSX_PENDING_EVIDENCE_DECISION = "KEEP_PENDING_EVIDENCE"
PDF_EXCLUDE_DECISION = "EXCLUDE_FROM_GOLD_V0_1"
PDF_PENDING_FILE_IDENTITY_DECISION = "KEEP_PENDING_FILE_IDENTITY_REVIEW"

XLSX_CONFIRM_RECOMMENDATION = "CONFIRM_INCLUDE_OFFICIAL_CANDIDATE"
XLSX_PENDING_EVIDENCE_RECOMMENDATION = "KEEP_PENDING_EVIDENCE"
PDF_EXCLUDE_RECOMMENDATION = "EXCLUDE_POLICY_OR_NOT_ANSWERABLE"
PDF_PENDING_RECOMMENDATION = "KEEP_PENDING_USER_REVIEW"

EXPECTED_XLSX_PENDING_EVIDENCE_IDS = [
    "gq_xlsx_date_number_format_003",
    "gq_xlsx_aggregation_001",
]

EXPECTED_PDF_EXCLUDE_IDS = [
    "pdf_file_lookup_content_anchor_004",
    "pdf_file_lookup_content_anchor_012",
    "pdf_file_lookup_content_anchor_013",
    "pdf_file_lookup_content_anchor_014",
    "pdf_file_lookup_content_anchor_015",
    "pdf_file_lookup_metadata_002",
]

EXPECTED_PDF_PENDING_IDS = [
    "pdf_file_lookup_content_anchor_017",
    "pdf_file_lookup_content_anchor_018",
    "pdf_file_lookup_content_anchor_020",
]

XLSX_PENDING_DECISIONS = [
    "confirm expected evidence",
    "confirm citation target",
    "confirm whether the row can enter gold_v0.1 candidate manifest",
]

PDF_PENDING_FILE_IDENTITY_DECISIONS = [
    "decide whether generic filename identity is acceptable",
    "decide whether stable document identity is required",
    "decide whether the row belongs to file/document identity lookup lane",
    "decide whether to exclude from gold_v0.1",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    draft = build_draft(
        packet_json=Path(args.packet_json),
        packet_md=Path(args.packet_md),
        normalization_report=Path(args.normalization_report),
        official_denominator_registry=Path(args.official_denominator_registry),
    )
    write_json(Path(args.output_json), draft)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(render_markdown(draft), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": draft["status"],
                "output_json": repo_relative(Path(args.output_json)),
                "output_md": repo_relative(Path(args.output_md)),
                "xlsx_processed_count": draft["rows_processed_by_track"]["xlsx_human_review"],
                "pdf_processed_count": draft["rows_processed_by_track"]["pdf_file_lookup_companion"],
                "text_unresolved_carried_forward_count": draft["text_unresolved_carry_forward_summary"][
                    "unresolved_user_review_count"
                ],
                "official_denominator_registry_changed": draft["guardrail_status"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if draft["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-json", default=str(DEFAULT_PACKET_JSON))
    parser.add_argument("--packet-md", default=str(DEFAULT_PACKET_MD))
    parser.add_argument("--normalization-report", default=str(DEFAULT_NORMALIZATION_REPORT))
    parser.add_argument("--official-denominator-registry", default=str(OFFICIAL_DENOMINATOR_REGISTRY))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUTPUT))
    return parser.parse_args(argv)


def build_draft(
    *,
    packet_json: Path,
    packet_md: Path,
    normalization_report: Path,
    official_denominator_registry: Path,
) -> dict[str, Any]:
    registry_sha_before = sha256_file(official_denominator_registry)
    packet = read_json(packet_json)
    normalization = read_json(normalization_report)

    xlsx_decisions = [build_xlsx_decision(row) for row in packet["xlsx_decision_packets"]]
    pdf_decisions = [build_pdf_decision(row) for row in packet["pdf_decision_packets"]]
    text_summary = build_text_summary(packet, normalization)

    registry_sha_after = sha256_file(official_denominator_registry)
    registry_changed = registry_sha_before != registry_sha_after
    validation_errors = validate_draft(
        packet=packet,
        xlsx_decisions=xlsx_decisions,
        pdf_decisions=pdf_decisions,
        text_summary=text_summary,
        registry_sha_before=registry_sha_before,
        registry_sha_after=registry_sha_after,
    )
    guardrails = {
        "report_only": True,
        "retrieval_variants_run": False,
        "production_namespace_mutated": False,
        "official_denominator_opened": False,
        "official_denominator_registry_path": repo_relative(official_denominator_registry),
        "official_denominator_registry_sha256_before": registry_sha_before,
        "official_denominator_registry_sha256_after": registry_sha_after,
        "official_denominator_registry_changed": registry_changed,
        "official_denominator_registry_not_changed": not registry_changed,
        "diagnostic_only_row_promoted": False,
        "pdf_content_and_file_identity_aggregated": False,
        "not_answerable_or_irrelevant_emitted_as_content_positive": False,
        "stable_identity_false_in_frozen_denominator": False,
    }
    counts = {
        "xlsx_human_review": dict(sorted(Counter(row["proposed_user_decision"] for row in xlsx_decisions).items())),
        "pdf_file_lookup_companion": dict(
            sorted(Counter(row["proposed_user_decision"] for row in pdf_decisions).items())
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not validation_errors else "FAIL",
        "generated_at": utc_timestamp(),
        "source_resolution_packet": {
            "json_path": repo_relative(packet_json),
            "json_sha256": sha256_file(packet_json),
            "md_path": repo_relative(packet_md),
            "md_sha256": sha256_file(packet_md) if packet_md.exists() else "",
            "status": packet.get("status"),
        },
        "source_normalization_report": {
            "path": repo_relative(normalization_report),
            "sha256": sha256_file(normalization_report),
            "status": normalization.get("status"),
        },
        "guardrail_status": guardrails,
        "scope": {
            "decision_draft_only": True,
            "official_denominator_registry_changed": registry_changed,
            "official_denominator_membership_frozen": False,
            "text_namu_v2_resolution_attempted": False,
            "pdf_content_evidence_and_file_identity_lanes_separate": True,
        },
        "rows_processed_by_track": {
            "xlsx_human_review": len(xlsx_decisions),
            "pdf_file_lookup_companion": len(pdf_decisions),
            "text_namu_v2": 0,
        },
        "xlsx_draft_decisions": xlsx_decisions,
        "pdf_draft_decisions": pdf_decisions,
        "text_unresolved_carry_forward_summary": text_summary,
        "counts_by_proposed_user_decision": counts,
        "exact_remaining_user_decisions": build_remaining_user_decisions(xlsx_decisions, pdf_decisions, text_summary),
        "explicit_confirmations": {
            "official_denominator_registry_json_was_not_changed": not registry_changed,
            "no_retrieval_variants_ran": True,
            "no_production_namespace_was_mutated": True,
            "no_diagnostic_only_row_was_promoted": True,
            "official_denominator_was_not_opened": True,
            "pdf_lanes_were_not_aggregated": True,
            "decision_draft_is_not_a_frozen_denominator": True,
        },
        "validation": {
            "errors": validation_errors,
            "required_schema_fields_present": True,
            "exactly_25_xlsx_rows_processed": len(xlsx_decisions) == 25,
            "exactly_9_pdf_rows_processed": len(pdf_decisions) == 9,
            "exactly_23_text_unresolved_rows_carried_forward": text_summary["unresolved_user_review_count"] == 23,
            "xlsx_include_candidate_draft_count": counts["xlsx_human_review"].get(XLSX_INCLUDE_DECISION, 0),
            "xlsx_pending_evidence_count": counts["xlsx_human_review"].get(XLSX_PENDING_EVIDENCE_DECISION, 0),
            "pdf_exclude_draft_count": counts["pdf_file_lookup_companion"].get(PDF_EXCLUDE_DECISION, 0),
            "pdf_pending_file_identity_count": counts["pdf_file_lookup_companion"].get(
                PDF_PENDING_FILE_IDENTITY_DECISION, 0
            ),
            "official_denominator_registry_not_modified": registry_sha_before == registry_sha_after,
            "pdf_content_file_identity_aggregation_count": None,
            "not_answerable_or_irrelevant_content_positive_rows": [],
            "diagnostic_only_promoted_rows": [],
            "stable_identity_false_frozen_rows": [],
        },
    }


def build_xlsx_decision(row: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = clean(row.get("codex_recommendation"))
    query_id = clean(row.get("query_id"))
    if recommendation == XLSX_CONFIRM_RECOMMENDATION:
        proposed_decision = XLSX_INCLUDE_DECISION
        final_status = "NOT_FROZEN"
        exact_user_decision_needed = [
            "confirm gold_v0.1 candidate inclusion before any candidate manifest or registry mutation"
        ]
        rationale = (
            "Answerability and relevance were already confirmed, expected answer source exists, "
            "and citation target exists. This remains a draft candidate only."
        )
    elif recommendation == XLSX_PENDING_EVIDENCE_RECOMMENDATION:
        proposed_decision = XLSX_PENDING_EVIDENCE_DECISION
        final_status = "UNRESOLVED"
        exact_user_decision_needed = XLSX_PENDING_DECISIONS
        rationale = (
            "Existing artifacts do not safely freeze the expected evidence or citation target; "
            "no missing evidence was inferred."
        )
    else:
        proposed_decision = XLSX_PENDING_EVIDENCE_DECISION
        final_status = "UNRESOLVED"
        exact_user_decision_needed = XLSX_PENDING_DECISIONS
        rationale = "Unexpected packet recommendation was kept unresolved by fail-closed policy."

    return {
        "query_id": query_id,
        "track": "xlsx_human_review",
        "question_input": row.get("question_input", ""),
        "source_packet_recommendation": recommendation,
        "current_normalized_bucket": row.get("current_normalized_bucket", ""),
        "user_answerability_label": row.get("user_answerability_label", ""),
        "user_relevance_label": row.get("user_relevance_label", ""),
        "user_gold_answer_shape": row.get("user_gold_answer_shape", ""),
        "user_required_citation_policy": row.get("user_required_citation_policy", ""),
        "candidate_expected_answer": row.get("candidate_expected_answer", {}),
        "candidate_expected_evidence": row.get("candidate_expected_evidence", {}),
        "source_citation_target": row.get("source_citation_target", {}),
        "proposed_user_decision": proposed_decision,
        "registry_mutation": False,
        "final_denominator_status": final_status,
        "official_denominator_frozen": False,
        "rationale": rationale,
        "exact_user_decision_needed": exact_user_decision_needed,
    }


def build_pdf_decision(row: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = clean(row.get("proposed_expected_evidence_policy"))
    conflict_tags = list(row.get("current_conflict_tags", []))
    if recommendation == PDF_EXCLUDE_RECOMMENDATION:
        proposed_decision = PDF_EXCLUDE_DECISION
        final_status = "EXCLUDED_DRAFT"
        exact_user_decision_needed = [
            "confirm exclusion from gold_v0.1 or revise answerability, relevance, lane, and expected evidence labels"
        ]
        rationale = "Policy-excluded, not-answerable, irrelevant, or unstable evidence/lane conflict."
    elif recommendation == PDF_PENDING_RECOMMENDATION:
        proposed_decision = PDF_PENDING_FILE_IDENTITY_DECISION
        final_status = "UNRESOLVED"
        exact_user_decision_needed = PDF_PENDING_FILE_IDENTITY_DECISIONS
        rationale = (
            "Generic filename identity risk and missing stable document identity block file-identity denominator inclusion."
        )
    else:
        proposed_decision = PDF_PENDING_FILE_IDENTITY_DECISION
        final_status = "UNRESOLVED"
        exact_user_decision_needed = PDF_PENDING_FILE_IDENTITY_DECISIONS
        rationale = "Unexpected packet recommendation was kept unresolved by fail-closed policy."

    return {
        "query_id": row.get("query_id", ""),
        "track": "pdf_file_lookup_companion",
        "source_packet_recommendation": recommendation,
        "current_issue_tags": row.get("current_issue_tags", []),
        "current_conflict_tags": conflict_tags,
        "current_normalized_bucket": row.get("current_normalized_bucket", ""),
        "appears_to_be": row.get("appears_to_be", ""),
        "generic_filename_identity_risk": bool(row.get("generic_filename_identity_risk")),
        "stable_document_identity": row.get("stable_document_identity", {}),
        "proposed_user_decision": proposed_decision,
        "registry_mutation": False,
        "final_denominator_status": final_status,
        "official_denominator_frozen": False,
        "converted_to_content_evidence_positive": False,
        "content_evidence_lane_counted": False,
        "file_document_identity_lane_counted": False,
        "proposed_expected_evidence_text_or_summary": row.get("proposed_expected_evidence_text_or_summary", {}),
        "rationale": rationale,
        "exact_user_decision_needed": exact_user_decision_needed,
    }


def build_text_summary(packet: Mapping[str, Any], normalization: Mapping[str, Any]) -> dict[str, Any]:
    packet_text = packet["unchanged_text_unresolved_summary"]
    text_track = normalization["tracks"]["text_namu_v2"]
    buckets = text_track.get("review_marker_buckets", {})
    expected_revision_rows = dedupe(
        list(buckets.get("expected_answer_revision", []))
        + list(buckets.get("expected_answer_and_evidence_revision", []))
    )
    invalid_or_ambiguous_rows = dedupe(list(buckets.get("ambiguous_query", [])) + list(buckets.get("invalid_query", [])))
    return {
        "track": packet_text.get("track", "text_namuwiki_animation"),
        "resolution_attempted": False,
        "unresolved_user_review_count": packet_text["unresolved_user_review_count"],
        "unresolved_user_review_rows": packet_text["unresolved_user_review_rows"],
        "summary_buckets": {
            "expected_answer_or_evidence_revisions": expected_revision_rows,
            "second_review": list(buckets.get("needs_second_review", [])),
            "invalid_or_ambiguous_query": invalid_or_ambiguous_rows,
            "evidence_too_broad": list(buckets.get("evidence_too_broad", [])),
            "source_binding_review_required": list(buckets.get("source_binding_review_required", [])),
        },
        "rationale": "TEXT/Namu unresolved rows are carried forward unchanged and are not resolved in this draft.",
    }


def validate_draft(
    *,
    packet: Mapping[str, Any],
    xlsx_decisions: list[Mapping[str, Any]],
    pdf_decisions: list[Mapping[str, Any]],
    text_summary: Mapping[str, Any],
    registry_sha_before: str,
    registry_sha_after: str,
) -> list[str]:
    errors: list[str] = []
    if packet.get("status") != "PASS":
        errors.append("source resolution packet status is not PASS")
    packet_guardrails = packet.get("guardrail_status", {})
    for field in [
        "retrieval_variants_run",
        "production_namespace_mutated",
        "official_denominator_opened",
        "official_denominator_registry_changed",
        "diagnostic_only_row_promoted",
        "pdf_content_and_file_identity_aggregated",
        "not_answerable_or_irrelevant_emitted_as_content_positive",
    ]:
        if packet_guardrails.get(field):
            errors.append(f"source packet guardrail breach: {field}")

    if len(xlsx_decisions) != 25:
        errors.append("expected exactly 25 XLSX decisions")
    if len(pdf_decisions) != 9:
        errors.append("expected exactly 9 PDF decisions")
    if text_summary.get("unresolved_user_review_count") != 23 or text_summary.get("resolution_attempted") is not False:
        errors.append("TEXT unresolved rows were not carried forward unchanged")

    xlsx_counts = Counter(row["proposed_user_decision"] for row in xlsx_decisions)
    pdf_counts = Counter(row["proposed_user_decision"] for row in pdf_decisions)
    if xlsx_counts.get(XLSX_INCLUDE_DECISION, 0) != 23:
        errors.append("expected 23 XLSX INCLUDE_AS_GOLD_V0_1_CANDIDATE draft rows")
    if xlsx_counts.get(XLSX_PENDING_EVIDENCE_DECISION, 0) != 2:
        errors.append("expected 2 XLSX KEEP_PENDING_EVIDENCE rows")
    if pdf_counts.get(PDF_EXCLUDE_DECISION, 0) != 6:
        errors.append("expected 6 PDF EXCLUDE_FROM_GOLD_V0_1 rows")
    if pdf_counts.get(PDF_PENDING_FILE_IDENTITY_DECISION, 0) != 3:
        errors.append("expected 3 PDF KEEP_PENDING_FILE_IDENTITY_REVIEW rows")

    actual_pending_xlsx = sorted(row["query_id"] for row in xlsx_decisions if row["proposed_user_decision"] == XLSX_PENDING_EVIDENCE_DECISION)
    if actual_pending_xlsx != sorted(EXPECTED_XLSX_PENDING_EVIDENCE_IDS):
        errors.append("XLSX pending-evidence row ids differ from expected scope")
    actual_pdf_excluded = sorted(row["query_id"] for row in pdf_decisions if row["proposed_user_decision"] == PDF_EXCLUDE_DECISION)
    if actual_pdf_excluded != sorted(EXPECTED_PDF_EXCLUDE_IDS):
        errors.append("PDF exclusion row ids differ from expected scope")
    actual_pdf_pending = sorted(
        row["query_id"] for row in pdf_decisions if row["proposed_user_decision"] == PDF_PENDING_FILE_IDENTITY_DECISION
    )
    if actual_pdf_pending != sorted(EXPECTED_PDF_PENDING_IDS):
        errors.append("PDF file-identity pending row ids differ from expected scope")

    for row in pdf_decisions:
        conflict_tags = set(row.get("current_conflict_tags", []))
        if {"NOT_ANSWERABLE", "IRRELEVANT"} & conflict_tags and row["proposed_user_decision"] != PDF_EXCLUDE_DECISION:
            errors.append(f"NOT_ANSWERABLE/IRRELEVANT PDF row not excluded: {row['query_id']}")
        if row.get("converted_to_content_evidence_positive"):
            errors.append(f"PDF row converted to content evidence positive: {row['query_id']}")
        stable = row.get("stable_document_identity", {})
        if stable.get("available") is False and row.get("official_denominator_frozen"):
            errors.append(f"stable_identity=false row frozen: {row['query_id']}")
    if any(row.get("registry_mutation") for row in xlsx_decisions + pdf_decisions):
        errors.append("draft row requested registry mutation")
    if registry_sha_before != registry_sha_after:
        errors.append("official denominator registry changed")
    return errors


def build_remaining_user_decisions(
    xlsx_decisions: list[Mapping[str, Any]],
    pdf_decisions: list[Mapping[str, Any]],
    text_summary: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "xlsx_include_confirmation_draft_rows": [
            row["query_id"] for row in xlsx_decisions if row["proposed_user_decision"] == XLSX_INCLUDE_DECISION
        ],
        "xlsx_pending_evidence_rows": [
            {
                "query_id": row["query_id"],
                "decision_needed": row["exact_user_decision_needed"],
            }
            for row in xlsx_decisions
            if row["proposed_user_decision"] == XLSX_PENDING_EVIDENCE_DECISION
        ],
        "pdf_exclusion_confirmation_draft_rows": [
            row["query_id"] for row in pdf_decisions if row["proposed_user_decision"] == PDF_EXCLUDE_DECISION
        ],
        "pdf_pending_file_identity_review_rows": [
            {
                "query_id": row["query_id"],
                "decision_needed": row["exact_user_decision_needed"],
            }
            for row in pdf_decisions
            if row["proposed_user_decision"] == PDF_PENDING_FILE_IDENTITY_DECISION
        ],
        "text_namu_v2_unresolved_rows": text_summary["unresolved_user_review_rows"],
    }


def render_markdown(draft: Mapping[str, Any]) -> str:
    xlsx_counts = json.dumps(
        draft["counts_by_proposed_user_decision"]["xlsx_human_review"], ensure_ascii=False, sort_keys=True
    )
    pdf_counts = json.dumps(
        draft["counts_by_proposed_user_decision"]["pdf_file_lookup_companion"], ensure_ascii=False, sort_keys=True
    )
    text_summary = draft["text_unresolved_carry_forward_summary"]
    lines = [
        "# Gold Policy Decision Draft v1",
        "",
        f"- Status: `{draft['status']}`",
        f"- Generated at: `{draft['generated_at']}`",
        f"- Source resolution packet: `{draft['source_resolution_packet']['json_path']}`",
        "- Scope: decision draft only; no official denominator membership is frozen.",
        "- Guardrails: no retrieval variants, no production namespace mutation, no denominator registry change.",
        "",
        "## Counts",
        "",
        f"- XLSX processed: `{draft['rows_processed_by_track']['xlsx_human_review']}`; draft decisions: `{xlsx_counts}`",
        f"- PDF processed: `{draft['rows_processed_by_track']['pdf_file_lookup_companion']}`; draft decisions: `{pdf_counts}`",
        f"- TEXT/Namu carried forward unresolved: `{text_summary['unresolved_user_review_count']}`",
        "",
        "## XLSX Draft Decisions",
        "",
        "| query_id | proposed_user_decision | final_denominator_status | citation target |",
        "|---|---|---|---|",
    ]
    for row in draft["xlsx_draft_decisions"]:
        target = row.get("source_citation_target", {})
        citation = f"{target.get('sheet') or 'USER_REQUIRED'} {target.get('range') or 'USER_REQUIRED'}"
        lines.append(
            f"| {row['query_id']} | `{row['proposed_user_decision']}` | `{row['final_denominator_status']}` | `{citation}` |"
        )

    lines.extend(
        [
            "",
            "## PDF Draft Decisions",
            "",
            "| query_id | proposed_user_decision | final_denominator_status | appears_to_be | stable_identity |",
            "|---|---|---|---|---|",
        ]
    )
    for row in draft["pdf_draft_decisions"]:
        stable = row.get("stable_document_identity", {}).get("available")
        lines.append(
            f"| {row['query_id']} | `{row['proposed_user_decision']}` | `{row['final_denominator_status']}` | `{row['appears_to_be']}` | `{stable}` |"
        )

    lines.extend(
        [
            "",
            "## TEXT/Namu Carry-Forward",
            "",
            f"- Unresolved rows: `{text_summary['unresolved_user_review_count']}`",
            "- Resolution attempted: `false`",
        ]
    )
    for bucket, rows in text_summary["summary_buckets"].items():
        lines.append(f"- {bucket}: `{len(rows)}`")

    lines.extend(
        [
            "",
            "## Remaining User Decisions",
            "",
            f"- XLSX include-confirmation draft rows: `{len(draft['exact_remaining_user_decisions']['xlsx_include_confirmation_draft_rows'])}`",
            f"- XLSX pending evidence rows: `{', '.join(row['query_id'] for row in draft['exact_remaining_user_decisions']['xlsx_pending_evidence_rows'])}`",
            f"- PDF exclusion-confirmation draft rows: `{len(draft['exact_remaining_user_decisions']['pdf_exclusion_confirmation_draft_rows'])}`",
            f"- PDF pending file-identity rows: `{', '.join(row['query_id'] for row in draft['exact_remaining_user_decisions']['pdf_pending_file_identity_review_rows'])}`",
            f"- TEXT/Namu unresolved rows: `{text_summary['unresolved_user_review_count']}`",
            "",
            "## Guardrails",
            "",
            f"- official_denominator_registry.json changed: `{draft['guardrail_status']['official_denominator_registry_changed']}`",
            f"- retrieval variants ran: `{draft['guardrail_status']['retrieval_variants_run']}`",
            f"- production namespace mutated: `{draft['guardrail_status']['production_namespace_mutated']}`",
            f"- diagnostic-only row promoted: `{draft['guardrail_status']['diagnostic_only_row_promoted']}`",
            f"- PDF content/file identity lanes aggregated: `{draft['guardrail_status']['pdf_content_and_file_identity_aggregated']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean(value: Any) -> str:
    return str(value or "").strip()


def dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
