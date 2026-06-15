"""Build a report-only gold policy resolution packet.

This packet consumes the reviewed-gold normalization report plus the local raw
review CSVs. It prepares row-level user-decision packets for a narrow scope:
XLSX denominator-confirmation rows and PDF expected-evidence revision rows.

It does not run retrieval, mutate namespaces, or update the official
denominator registry.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

NORMALIZATION_REPORT_CANDIDATES = [
    REPORT_DIR / "rag_reviewed_gold_policy_normalization_report.json",
    AI_WORKER_ROOT / "eval" / "reviewed_gold_policy_normalization_report.json",
]
XLSX_STRICT_NORMALIZATION_REPORT = REPORT_DIR / "rag_xlsx_human_review_gold_normalization_report.json"
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
XLSX_REVIEW_CSV = REVIEW_DIR / "xlsx" / "제목 없는 스프레드시트 - xlsx_gold_human_review_pack (1).csv"
PDF_REVIEW_CSV = (
    REVIEW_DIR
    / "pdf_supplemental_gold_review"
    / "pdf_gold_review_pack_manual_v1_file_lookup_companion - "
    "pdf_gold_review_pack_manual_v1_file_lookup_companion.csv"
)

DEFAULT_JSON_OUTPUT = REVIEW_DIR / "rag_gold_policy_resolution_packet_v1.json"
DEFAULT_MD_OUTPUT = REVIEW_DIR / "rag_gold_policy_resolution_packet_v1.md"

SCHEMA_VERSION = "rag_gold_policy_resolution_packet_v1"

XLSX_TARGET_IDS = [
    "gq_xlsx_lookup_001",
    "gq_xlsx_lookup_004",
    "gq_xlsx_lookup_005",
    "gq_xlsx_lookup_006",
    "gq_xlsx_lookup_007",
    "gq_xlsx_lookup_008",
    "gq_xlsx_date_number_format_001",
    "gq_xlsx_date_number_format_003",
    "gq_xlsx_aggregation_001",
    "gq_xlsx_aggregation_002",
    "gq_auto_012",
    "gq_auto_017",
    "gq_auto_018",
    "gq_auto_022",
    "gq_auto_023",
    "gq_auto_028",
    "gq_auto_031",
    "gq_auto_034",
    "gq_auto_035",
    "gq_auto_036",
    "gq_auto_037",
    "gq_auto_038",
    "gq_auto_040",
    "gq_auto_043",
    "gq_auto_044",
]

PDF_TARGET_IDS = [
    "pdf_file_lookup_content_anchor_004",
    "pdf_file_lookup_content_anchor_012",
    "pdf_file_lookup_content_anchor_013",
    "pdf_file_lookup_content_anchor_014",
    "pdf_file_lookup_content_anchor_015",
    "pdf_file_lookup_content_anchor_017",
    "pdf_file_lookup_content_anchor_018",
    "pdf_file_lookup_content_anchor_020",
    "pdf_file_lookup_metadata_002",
]

XLSX_CONFIRM = "CONFIRM_INCLUDE_OFFICIAL_CANDIDATE"
XLSX_PENDING_ANSWER = "KEEP_PENDING_EXPECTED_ANSWER"
XLSX_PENDING_EVIDENCE = "KEEP_PENDING_EVIDENCE"
XLSX_DIAGNOSTIC = "DEMOTE_TO_DIAGNOSTIC_ONLY"

PDF_KEEP_CONTENT = "KEEP_AS_CONTENT_EVIDENCE"
PDF_CONVERT_FILE = "CONVERT_TO_FILE_LOOKUP_IDENTITY"
PDF_EXCLUDE = "EXCLUDE_POLICY_OR_NOT_ANSWERABLE"
PDF_PENDING = "KEEP_PENDING_USER_REVIEW"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    normalization_report_path = resolve_normalization_report(Path(args.normalization_report) if args.normalization_report else None)
    packet = build_packet(
        normalization_report_path=normalization_report_path,
        xlsx_review_csv=Path(args.xlsx_review_csv),
        pdf_review_csv=Path(args.pdf_review_csv),
        xlsx_strict_report=Path(args.xlsx_strict_report),
        official_denominator_registry=Path(args.official_denominator_registry),
    )
    write_json(Path(args.output_json), packet)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(render_markdown(packet), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": packet["status"],
                "output_json": repo_relative(Path(args.output_json)),
                "output_md": repo_relative(Path(args.output_md)),
                "xlsx_processed_count": packet["rows_processed_by_track"]["xlsx_human_review"],
                "pdf_processed_count": packet["rows_processed_by_track"]["pdf_file_lookup_companion"],
                "official_denominator_registry_changed": packet["guardrail_status"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if packet["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalization-report", default="")
    parser.add_argument("--xlsx-review-csv", default=str(XLSX_REVIEW_CSV))
    parser.add_argument("--pdf-review-csv", default=str(PDF_REVIEW_CSV))
    parser.add_argument("--xlsx-strict-report", default=str(XLSX_STRICT_NORMALIZATION_REPORT))
    parser.add_argument("--official-denominator-registry", default=str(OFFICIAL_DENOMINATOR_REGISTRY))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUTPUT))
    return parser.parse_args(argv)


def build_packet(
    *,
    normalization_report_path: Path,
    xlsx_review_csv: Path,
    pdf_review_csv: Path,
    xlsx_strict_report: Path,
    official_denominator_registry: Path,
) -> dict[str, Any]:
    registry_sha_before = sha256_file(official_denominator_registry)
    normalization_report = read_json(normalization_report_path)
    xlsx_rows = keyed_rows(read_csv_rows(xlsx_review_csv))
    pdf_rows = keyed_rows(read_csv_rows(pdf_review_csv))
    xlsx_norm_rows = keyed_json_rows(normalization_report["tracks"]["xlsx_human_review"]["rows"])
    pdf_norm_rows = keyed_json_rows(normalization_report["tracks"]["pdf_file_lookup_companion"]["rows"])
    strict_pending_evidence = xlsx_strict_pending_evidence_ids(xlsx_strict_report)

    validation_errors = validate_inputs(
        normalization_report=normalization_report,
        xlsx_rows=xlsx_rows,
        pdf_rows=pdf_rows,
        xlsx_norm_rows=xlsx_norm_rows,
        pdf_norm_rows=pdf_norm_rows,
    )

    xlsx_packets = [
        build_xlsx_packet(
            query_id=query_id,
            raw_row=xlsx_rows[query_id],
            normalized_row=xlsx_norm_rows[query_id],
            strict_pending_evidence_ids=strict_pending_evidence,
        )
        for query_id in XLSX_TARGET_IDS
        if query_id in xlsx_rows and query_id in xlsx_norm_rows
    ]
    pdf_packets = [
        build_pdf_packet(query_id=query_id, raw_row=pdf_rows[query_id], normalized_row=pdf_norm_rows[query_id])
        for query_id in PDF_TARGET_IDS
        if query_id in pdf_rows and query_id in pdf_norm_rows
    ]

    registry_sha_after = sha256_file(official_denominator_registry)
    xlsx_counts = Counter(packet["codex_recommendation"] for packet in xlsx_packets)
    pdf_counts = Counter(packet["proposed_expected_evidence_policy"] for packet in pdf_packets)
    text_track = normalization_report["tracks"]["text_namu_v2"]
    status = "PASS" if not validation_errors and registry_sha_before == registry_sha_after else "FAIL"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": utc_timestamp(),
        "source_normalization_report": {
            "path": repo_relative(normalization_report_path),
            "sha256": sha256_file(normalization_report_path),
            "status": normalization_report.get("status"),
            "cross_track_validation_errors": normalization_report.get("cross_track_validation_errors", []),
        },
        "guardrail_status": {
            "report_only": True,
            "retrieval_variants_run": False,
            "production_namespace_mutated": False,
            "official_denominator_opened": False,
            "official_denominator_registry_path": repo_relative(official_denominator_registry),
            "official_denominator_registry_sha256_before": registry_sha_before,
            "official_denominator_registry_sha256_after": registry_sha_after,
            "official_denominator_registry_changed": registry_sha_before != registry_sha_after,
            "diagnostic_only_row_promoted": False,
            "pdf_content_and_file_identity_aggregated": False,
            "not_answerable_or_irrelevant_emitted_as_content_positive": False,
        },
        "scope": {
            "active_tracks": ["xlsx_human_review", "pdf_file_lookup_companion"],
            "text_namu_v2_resolved": False,
            "xlsx_target_source": "xlsx_human_review.denominator_confirmation_required_query_ids",
            "pdf_target_source": "pdf_file_lookup_companion.expected_answer_or_evidence_revision_query_ids",
            "no_retrieval_or_ranking_experiments": True,
        },
        "rows_processed_by_track": {
            "xlsx_human_review": len(xlsx_packets),
            "pdf_file_lookup_companion": len(pdf_packets),
            "text_namu_v2": 0,
        },
        "xlsx_decision_packets": xlsx_packets,
        "pdf_decision_packets": pdf_packets,
        "unchanged_text_unresolved_summary": {
            "track": "text_namuwiki_animation",
            "unresolved_user_review_count": text_track["unresolved_user_review_count"],
            "unresolved_user_review_rows": text_track["unresolved_user_review_rows"],
            "resolution_attempted": False,
            "rationale": "TEXT/Namu unresolved rows are explicitly out of scope for this packet.",
        },
        "counts_by_proposed_decision": {
            "xlsx_human_review": dict(sorted(xlsx_counts.items())),
            "pdf_file_lookup_companion": dict(sorted(pdf_counts.items())),
        },
        "exact_remaining_user_decisions": {
            "xlsx_human_review": build_xlsx_user_decisions(xlsx_packets),
            "pdf_file_lookup_companion": build_pdf_user_decisions(pdf_packets),
            "text_namu_v2": [
                "Carry forward the 23 TEXT/Namu unresolved rows for a separate TEXT-only gold-policy review."
            ],
        },
        "validation": {
            "errors": validation_errors,
            "only_requested_xlsx_rows_processed": [packet["query_id"] for packet in xlsx_packets] == XLSX_TARGET_IDS,
            "only_requested_pdf_rows_processed": [packet["query_id"] for packet in pdf_packets] == PDF_TARGET_IDS,
            "text_unresolved_carried_forward_only": True,
            "pdf_lane_counts": {
                "content_evidence_packet_count": sum(
                    1 for packet in pdf_packets if packet["appears_to_be"] == "content_evidence_candidate"
                ),
                "file_identity_packet_count": sum(
                    1 for packet in pdf_packets if packet["appears_to_be"] == "file_document_identity_lookup_candidate"
                ),
                "policy_excluded_or_not_answerable_packet_count": sum(
                    1 for packet in pdf_packets if packet["appears_to_be"] == "policy_excluded_not_answerable"
                ),
                "aggregate_official_denominator_count": None,
            },
        },
        "official_denominator_registry_not_changed": registry_sha_before == registry_sha_after,
    }


def build_xlsx_packet(
    *,
    query_id: str,
    raw_row: Mapping[str, str],
    normalized_row: Mapping[str, Any],
    strict_pending_evidence_ids: set[str],
) -> dict[str, Any]:
    target = xlsx_source_target(raw_row)
    answer = xlsx_expected_answer(raw_row)
    evidence = xlsx_evidence_summary(raw_row)
    has_target = bool(target.get("sheet") and target.get("range") and target.get("citation_locator_parse_status") == "PASS")
    has_evidence = bool(evidence.get("summary")) and not evidence.get("workbook_only_context")

    if query_id in strict_pending_evidence_ids or not has_target or not has_evidence:
        recommendation = XLSX_PENDING_EVIDENCE
        user_decision = (
            "Provide or confirm the exact evidence locator/evidence sufficiency before this row can become "
            "an official retrieval/evidence candidate."
        )
        rationale = (
            "Existing artifacts do not satisfy the stricter evidence contract, so the row remains proposed-only."
        )
    elif not answer.get("text"):
        recommendation = XLSX_PENDING_ANSWER
        user_decision = "Provide the expected answer text or confirm that the existing answer shape is sufficient."
        rationale = "No deterministic expected answer is available from existing artifacts."
    elif normalized_row.get("normalized_policy_bucket") != "PROPOSED_OFFICIAL_CANDIDATE":
        recommendation = XLSX_DIAGNOSTIC
        user_decision = "Confirm whether this row should stay diagnostic-only."
        rationale = "The row is not currently in the normalized proposed-candidate bucket."
    else:
        recommendation = XLSX_CONFIRM
        user_decision = (
            "Confirm inclusion in the official retrieval/evidence candidate denominator. "
            "This does not open XLSX answer-generation denominator membership."
        )
        rationale = (
            "The row has confirmed answerability/relevance plus existing expected-answer, evidence, and citation target artifacts."
        )

    return {
        "query_id": query_id,
        "question_input": clean(raw_row.get("query")),
        "current_normalized_bucket": normalized_row.get("normalized_policy_bucket", ""),
        "user_answerability_label": clean(raw_row.get("user_answerability_label")),
        "user_relevance_label": clean(raw_row.get("user_relevance_label")),
        "user_gold_answer_shape": clean(raw_row.get("user_gold_answer_shape")),
        "user_required_citation_policy": clean(raw_row.get("user_required_citation_policy")),
        "candidate_expected_answer": answer,
        "candidate_expected_evidence": evidence,
        "source_citation_target": target,
        "codex_recommendation": recommendation,
        "rationale": rationale,
        "exact_user_decision_needed": user_decision,
        "official_denominator_frozen": False,
    }


def build_pdf_packet(*, query_id: str, raw_row: Mapping[str, str], normalized_row: Mapping[str, Any]) -> dict[str, Any]:
    issue_tags = list(normalized_row.get("issue_tags", []))
    conflict_tags = pdf_conflict_tags(raw_row, issue_tags)
    generic_risk = "GENERIC_FILENAME" in conflict_tags
    stable_identity = stable_pdf_identity(raw_row, generic_risk=generic_risk)
    appears_to_be = pdf_appearance(raw_row, conflict_tags)

    if "NOT_ANSWERABLE" in conflict_tags or "IRRELEVANT" in conflict_tags:
        proposed_policy = PDF_EXCLUDE
        user_decision = (
            "Confirm exclusion or revise the answerability/relevance/evidence labels with sufficient expected evidence."
        )
        rationale = "NOT_ANSWERABLE or IRRELEVANT rows cannot silently become content-positive denominator rows."
    elif appears_to_be == "file_document_identity_lookup_candidate" and generic_risk and not stable_identity["available"]:
        proposed_policy = PDF_PENDING
        user_decision = (
            "Confirm whether the generic filename is acceptable, or provide a stable document identity before file-lookup inclusion."
        )
        rationale = "The row looks file-identity oriented, but generic filename risk blocks a safe conversion."
    elif appears_to_be == "file_document_identity_lookup_candidate":
        proposed_policy = PDF_CONVERT_FILE
        user_decision = "Confirm conversion to the separate file/document identity lookup lane."
        rationale = "The row is answerable as file lookup with identity-oriented evidence."
    elif appears_to_be == "content_evidence_candidate":
        proposed_policy = PDF_KEEP_CONTENT
        user_decision = "Confirm content evidence sufficiency and page/layout evidence policy."
        rationale = "The row has answerable/relevant content evidence labels."
    else:
        proposed_policy = PDF_PENDING
        user_decision = "Resolve the expected evidence policy and lane selection."
        rationale = "Existing labels do not safely determine content versus file identity policy."

    return {
        "query_id": query_id,
        "current_issue_tags": issue_tags,
        "current_normalized_bucket": normalized_row.get("normalized_policy_bucket", ""),
        "appears_to_be": appears_to_be,
        "current_conflict_tags": conflict_tags,
        "generic_filename_identity_risk": generic_risk,
        "stable_document_identity": stable_identity,
        "proposed_expected_evidence_policy": proposed_policy,
        "proposed_expected_evidence_text_or_summary": pdf_expected_evidence(raw_row),
        "rationale": rationale,
        "exact_user_decision_needed": user_decision,
        "source_file_name": clean(raw_row.get("source_file_name")),
        "expected_file_name": clean(raw_row.get("expected_file_name")),
        "expected_document_version_id": clean(raw_row.get("expected_document_version_id")),
        "official_denominator_frozen": False,
    }


def xlsx_expected_answer(row: Mapping[str, str]) -> dict[str, str]:
    for field in ["user_expected_answer_text", "expected_answer_text_existing", "deterministic_compiled_answer"]:
        value = clean(row.get(field))
        if value and not placeholder_answer(value):
            return {"text": value, "source_field": field}
    return {"text": "", "source_field": "USER_REQUIRED"}


def xlsx_evidence_summary(row: Mapping[str, str]) -> dict[str, Any]:
    summary = clean(row.get("user_expected_evidence_text_or_summary")) or clean(row.get("evidence_summary"))
    headers = parse_json_list(row.get("evidence_headers"))
    workbook_only = summary.startswith("Visible row context: citation_text:") or clean(row.get("citation_locator")) == "{}"
    return {
        "summary": "" if workbook_only else summary,
        "source_field": "evidence_summary" if summary and not workbook_only else "USER_REQUIRED",
        "headers": headers,
        "deterministic_compiled_status": clean(row.get("deterministic_compiled_status")),
        "workbook_only_context": workbook_only,
    }


def xlsx_source_target(row: Mapping[str, str]) -> dict[str, Any]:
    locator = parse_json_object(row.get("citation_locator"))
    citation_policy = clean(row.get("user_required_citation_policy"))
    sheet = clean(row.get("sheet")) or clean(locator.get("sheet"))
    cell_range = clean(row.get("range")) or clean(locator.get("range"))
    return {
        "citation_policy": citation_policy,
        "target_kind": citation_target_kind(citation_policy),
        "sheet": sheet,
        "range": cell_range,
        "file": clean(locator.get("file")),
        "document_version_id": clean(locator.get("document_version_id")),
        "search_unit_id": clean(locator.get("search_unit_id")),
        "citation_locator_parse_status": "PASS" if locator else "FAIL",
    }


def citation_target_kind(policy: str) -> str:
    return {
        "EXACT_CELL": "exact_cell",
        "EXACT_ROW": "exact_row",
        "SHEET_RANGE_WITH_EXAMPLES": "sheet_range",
        "ROW_GROUP_RANGE": "row_group_range",
        "TABLE_RANGE": "table_range",
        "EXACT_CELL, EXACT_ROW": "exact_cell_or_row",
    }.get(policy, "unknown")


def xlsx_strict_pending_evidence_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = read_json(path)
    rows = payload.get("rows_excluded_despite_human_relevant_labels", [])
    return {clean(row.get("query_id")) for row in rows if clean(row.get("derived_denominator_policy")) != "OFFICIAL_POSITIVE"}


def pdf_appearance(row: Mapping[str, str], conflict_tags: Iterable[str]) -> str:
    tags = set(conflict_tags)
    if "NOT_ANSWERABLE" in tags or "IRRELEVANT" in tags:
        return "policy_excluded_not_answerable"
    if clean(row.get("user_answerability_label")) == "ANSWERABLE_AS_FILE_LOOKUP" or clean(
        row.get("user_expected_evidence_policy")
    ) == "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY":
        return "file_document_identity_lookup_candidate"
    if clean(row.get("user_answerability_label")) == "ANSWERABLE" and clean(row.get("user_relevance_label")) == "RELEVANT":
        return "content_evidence_candidate"
    return "still_ambiguous"


def pdf_conflict_tags(row: Mapping[str, str], issue_tags: Iterable[str]) -> list[str]:
    tags = list(issue_tags)
    for field in [
        "user_gold_decision",
        "user_answerability_label",
        "user_relevance_label",
        "user_expected_evidence_policy",
        "user_denominator_policy",
    ]:
        tags.extend(split_values(row.get(field)))
    tags.extend(split_values(row.get("risk_tags")))
    return dedupe(
        tag
        for tag in tags
        if tag
        in {
            "NOT_ANSWERABLE",
            "IRRELEVANT",
            "PARTIAL",
            "ANSWERABLE_AS_FILE_LOOKUP",
            "GENERIC_FILENAME",
            "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW",
            "INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE",
            "REVISE_EXPECTED_EVIDENCE",
            "KEEP_POSITIVE",
        }
    )


def stable_pdf_identity(row: Mapping[str, str], *, generic_risk: bool) -> dict[str, Any]:
    document_version_id = clean(row.get("expected_document_version_id"))
    expected_file_name = clean(row.get("expected_file_name"))
    if document_version_id:
        return {"available": True, "basis": "expected_document_version_id", "value": document_version_id}
    if expected_file_name and not generic_risk:
        return {"available": True, "basis": "non_generic_expected_file_name", "value": expected_file_name}
    return {"available": False, "basis": "none", "value": ""}


def pdf_expected_evidence(row: Mapping[str, str]) -> dict[str, str]:
    for field in ["expected_evidence_excerpt", "evidence_object_summary", "deterministic_draft"]:
        value = clean(row.get(field))
        if value:
            return {"text": value, "source_field": field}
    return {"text": "", "source_field": "USER_REQUIRED"}


def build_xlsx_user_decisions(packets: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "query_id": packet["query_id"],
            "decision_needed": packet["exact_user_decision_needed"],
            "recommendation": packet["codex_recommendation"],
        }
        for packet in packets
    ]


def build_pdf_user_decisions(packets: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "query_id": packet["query_id"],
            "decision_needed": packet["exact_user_decision_needed"],
            "proposed_expected_evidence_policy": packet["proposed_expected_evidence_policy"],
        }
        for packet in packets
    ]


def validate_inputs(
    *,
    normalization_report: Mapping[str, Any],
    xlsx_rows: Mapping[str, Mapping[str, str]],
    pdf_rows: Mapping[str, Mapping[str, str]],
    xlsx_norm_rows: Mapping[str, Mapping[str, Any]],
    pdf_norm_rows: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if normalization_report.get("status") != "PASS":
        errors.append("normalization report status is not PASS")
    if normalization_report.get("cross_track_validation_errors"):
        errors.append("normalization report has cross_track_validation_errors")
    report_xlsx_ids = normalization_report["tracks"]["xlsx_human_review"].get(
        "denominator_confirmation_required_query_ids", []
    )
    report_pdf_ids = normalization_report["tracks"]["pdf_file_lookup_companion"].get(
        "expected_answer_or_evidence_revision_query_ids", []
    )
    if report_xlsx_ids != XLSX_TARGET_IDS:
        errors.append("normalization report XLSX target list differs from v1 packet scope")
    if report_pdf_ids != PDF_TARGET_IDS:
        errors.append("normalization report PDF target list differs from v1 packet scope")
    for query_id in XLSX_TARGET_IDS:
        if query_id not in xlsx_rows:
            errors.append(f"missing XLSX raw row: {query_id}")
        if query_id not in xlsx_norm_rows:
            errors.append(f"missing XLSX normalized row: {query_id}")
    for query_id in PDF_TARGET_IDS:
        if query_id not in pdf_rows:
            errors.append(f"missing PDF raw row: {query_id}")
        if query_id not in pdf_norm_rows:
            errors.append(f"missing PDF normalized row: {query_id}")
    return errors


def render_markdown(packet: Mapping[str, Any]) -> str:
    xlsx_counts = packet["counts_by_proposed_decision"]["xlsx_human_review"]
    pdf_counts = packet["counts_by_proposed_decision"]["pdf_file_lookup_companion"]
    lines = [
        "# Gold Policy Resolution Packet v1",
        "",
        f"- Status: `{packet['status']}`",
        f"- Generated at: `{packet['generated_at']}`",
        f"- Source normalization report: `{packet['source_normalization_report']['path']}`",
        "- Scope: XLSX denominator confirmations and PDF expected-evidence revisions only.",
        "- TEXT/Namu unresolved rows are carried forward unchanged.",
        "- No retrieval variants, production namespace mutation, or denominator registry edits were performed.",
        "",
        "## Counts",
        "",
        f"- XLSX processed: `{packet['rows_processed_by_track']['xlsx_human_review']}`; decisions: `{json.dumps(xlsx_counts, ensure_ascii=False, sort_keys=True)}`",
        f"- PDF processed: `{packet['rows_processed_by_track']['pdf_file_lookup_companion']}`; decisions: `{json.dumps(pdf_counts, ensure_ascii=False, sort_keys=True)}`",
        f"- TEXT carried forward unresolved: `{packet['unchanged_text_unresolved_summary']['unresolved_user_review_count']}`",
        "",
        "## XLSX Decisions",
        "",
        "| query_id | recommendation | answer source | citation target |",
        "|---|---|---|---|",
    ]
    for row in packet["xlsx_decision_packets"]:
        target = row["source_citation_target"]
        lines.append(
            "| {query_id} | `{recommendation}` | `{answer_source}` | `{sheet} {cell_range}` |".format(
                query_id=row["query_id"],
                recommendation=row["codex_recommendation"],
                answer_source=row["candidate_expected_answer"]["source_field"],
                sheet=target.get("sheet") or "USER_REQUIRED",
                cell_range=target.get("range") or "USER_REQUIRED",
            )
        )
    lines.extend(["", "## PDF Decisions", "", "| query_id | proposed policy | appears to be | stable identity |", "|---|---|---|---|"])
    for row in packet["pdf_decision_packets"]:
        stable = row["stable_document_identity"]
        lines.append(
            "| {query_id} | `{policy}` | `{appears}` | `{stable}` |".format(
                query_id=row["query_id"],
                policy=row["proposed_expected_evidence_policy"],
                appears=row["appears_to_be"],
                stable=stable["available"],
            )
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            f"- Official denominator registry changed: `{packet['guardrail_status']['official_denominator_registry_changed']}`",
            f"- Retrieval variants run: `{packet['guardrail_status']['retrieval_variants_run']}`",
            f"- Production namespace mutated: `{packet['guardrail_status']['production_namespace_mutated']}`",
            f"- PDF content/file identity aggregated: `{packet['guardrail_status']['pdf_content_and_file_identity_aggregated']}`",
            f"- Diagnostic-only row promoted: `{packet['guardrail_status']['diagnostic_only_row_promoted']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def resolve_normalization_report(explicit: Path | None) -> Path:
    if explicit:
        if explicit.exists():
            return explicit
        raise FileNotFoundError(f"normalization report not found: {explicit}")
    for path in NORMALIZATION_REPORT_CANDIDATES:
        if path.exists():
            return path
    candidates = ", ".join(str(path) for path in NORMALIZATION_REPORT_CANDIDATES)
    raise FileNotFoundError(f"normalization report not found in: {candidates}")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def keyed_rows(rows: Iterable[Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    return {clean(row.get("query_id")): row for row in rows}


def keyed_json_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {clean(row.get("query_id")): row for row in rows}


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


def parse_json_object(value: Any) -> dict[str, Any]:
    text = clean(value)
    if not text or text == "{}":
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_json_list(value: Any) -> list[Any]:
    text = clean(value)
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def split_values(value: Any) -> list[str]:
    text = clean(value)
    if not text:
        return []
    parts = [part.strip() for chunk in text.split(";") for part in chunk.split(",")]
    return [part for part in parts if part]


def placeholder_answer(value: str) -> bool:
    return " needs " in f" {value.lower()} "


def dedupe(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def clean(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
