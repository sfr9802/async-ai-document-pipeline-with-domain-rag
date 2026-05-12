"""Materialize user-approved gold-policy resolutions as report-only artifacts.

This consumes rag_gold_policy_decision_draft_v1 plus the user-facing review
sheet and records the user's policy decisions. It does not mutate the official
denominator registry, run retrieval/ranking variants, or touch namespaces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_DRAFT_JSON = REVIEW_DIR / "rag_gold_policy_decision_draft_v1.json"
DEFAULT_REVIEW_SHEET_MD = REVIEW_DIR / "rag_gold_policy_user_review_sheet_v1.md"
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"

DEFAULT_JSON_OUTPUT = REVIEW_DIR / "rag_gold_policy_user_approved_resolutions_v1.json"
DEFAULT_MD_OUTPUT = REVIEW_DIR / "rag_gold_policy_user_approved_resolutions_v1.md"

SCHEMA_VERSION = "rag_gold_policy_user_approved_resolutions_v1"

XLSX_APPROVED_DECISION = "APPROVE_DRAFT_GOLD_V0_1_CANDIDATE"
XLSX_PENDING_EVIDENCE_DECISION = "KEEP_PENDING_EVIDENCE"
PDF_EXCLUDE_DECISION = "EXCLUDE_FROM_GOLD_V0_1"
PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION = "EXCLUDE_FROM_GOLD_V0_1_REQUIRE_STABLE_IDENTITY"
TEXT_CARRY_FORWARD_DECISION = "CARRY_FORWARD_UNRESOLVED"

XLSX_INCLUDE_DRAFT = "INCLUDE_AS_GOLD_V0_1_CANDIDATE"
XLSX_PENDING_EVIDENCE_DRAFT = "KEEP_PENDING_EVIDENCE"
PDF_EXCLUDE_DRAFT = "EXCLUDE_FROM_GOLD_V0_1"
PDF_PENDING_FILE_IDENTITY_DRAFT = "KEEP_PENDING_FILE_IDENTITY_REVIEW"

XLSX_PENDING_EVIDENCE_IDS = [
    "gq_xlsx_date_number_format_003",
    "gq_xlsx_aggregation_001",
]

PDF_PENDING_FILE_IDENTITY_IDS = [
    "pdf_file_lookup_content_anchor_017",
    "pdf_file_lookup_content_anchor_018",
    "pdf_file_lookup_content_anchor_020",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    resolutions = build_resolutions(
        draft_json=Path(args.draft_json),
        review_sheet_md=Path(args.review_sheet_md),
        official_denominator_registry=Path(args.official_denominator_registry),
    )
    write_json(Path(args.output_json), resolutions)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(render_markdown(resolutions), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": resolutions["status"],
                "output_json": repo_relative(Path(args.output_json)),
                "output_md": repo_relative(Path(args.output_md)),
                "xlsx_draft_candidate_approved_count": resolutions["counts"]["xlsx"][
                    XLSX_APPROVED_DECISION
                ],
                "xlsx_pending_evidence_count": resolutions["counts"]["xlsx"][XLSX_PENDING_EVIDENCE_DECISION],
                "pdf_excluded_count": resolutions["counts"]["pdf"][PDF_EXCLUDE_DECISION],
                "pdf_stable_identity_required_excluded_count": resolutions["counts"]["pdf"][
                    PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION
                ],
                "text_unresolved_carried_forward_count": resolutions["text_namu_v2"]["unresolved_count"],
                "official_denominator_registry_changed": resolutions["guardrails"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if resolutions["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-json", default=str(DEFAULT_DRAFT_JSON))
    parser.add_argument("--review-sheet-md", default=str(DEFAULT_REVIEW_SHEET_MD))
    parser.add_argument("--official-denominator-registry", default=str(OFFICIAL_DENOMINATOR_REGISTRY))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUTPUT))
    return parser.parse_args(argv)


def build_resolutions(
    *,
    draft_json: Path,
    review_sheet_md: Path,
    official_denominator_registry: Path,
) -> dict[str, Any]:
    registry_sha_before = sha256_file(official_denominator_registry)
    draft = read_json(draft_json)
    xlsx_resolutions = build_xlsx_resolutions(draft)
    pdf_resolutions = build_pdf_resolutions(draft)
    text_summary = build_text_resolution(draft)
    registry_sha_after = sha256_file(official_denominator_registry)
    registry_changed = registry_sha_before != registry_sha_after
    counts = {
        "xlsx": dict(sorted(Counter(row["user_gold_policy_decision"] for row in xlsx_resolutions).items())),
        "pdf": dict(sorted(Counter(row["user_gold_policy_decision"] for row in pdf_resolutions).items())),
        "text_namu_v2": {TEXT_CARRY_FORWARD_DECISION: text_summary["unresolved_count"]},
    }
    draft_manifest_ids = [
        row["query_id"]
        for row in xlsx_resolutions
        if row["user_gold_policy_decision"] == XLSX_APPROVED_DECISION
    ]
    validation_errors = validate_resolutions(
        draft=draft,
        xlsx_resolutions=xlsx_resolutions,
        pdf_resolutions=pdf_resolutions,
        text_summary=text_summary,
        registry_changed=registry_changed,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not validation_errors else "FAIL",
        "generated_at": utc_timestamp(),
        "source_decision_draft": {
            "path": repo_relative(draft_json),
            "sha256": sha256_file(draft_json),
            "status": draft.get("status"),
        },
        "source_user_review_sheet": {
            "path": repo_relative(review_sheet_md),
            "sha256": sha256_file(review_sheet_md) if review_sheet_md.exists() else "",
        },
        "user_decision_source": {
            "received_at": "2026-05-12",
            "summary": "User approved XLSX 23-row include batch as draft-only candidates, kept two XLSX rows pending evidence, approved PDF 6-row exclude batch, excluded three generic-filename PDF file-identity rows from gold_v0.1 while allowing diagnostic-only use, and carried TEXT/Namu unresolved rows forward unchanged.",
        },
        "guardrails": {
            "report_only": True,
            "retrieval_variants_run": False,
            "production_namespace_mutated": False,
            "official_denominator_opened": False,
            "official_denominator_registry_path": repo_relative(official_denominator_registry),
            "official_denominator_registry_sha256_before": registry_sha_before,
            "official_denominator_registry_sha256_after": registry_sha_after,
            "official_denominator_registry_changed": registry_changed,
            "official_denominator_registry_not_changed": not registry_changed,
            "official_denominator_frozen": False,
            "diagnostic_only_row_promoted": False,
            "pdf_content_and_file_identity_aggregated": False,
            "policy_excluded_rows_counted_as_retrieval_failures": False,
            "unresolved_text_rows_included_in_gold_v0_1": False,
        },
        "draft_gold_v0_1_candidate_manifest": {
            "status": "DRAFT_ONLY_NOT_FROZEN",
            "registry_mutation": False,
            "included_track_count": {"xlsx_human_review": len(draft_manifest_ids)},
            "included_query_ids_by_track": {"xlsx_human_review": draft_manifest_ids},
            "excluded_pending_query_ids_by_track": {
                "xlsx_human_review": XLSX_PENDING_EVIDENCE_IDS,
                "pdf_file_lookup_companion": [row["query_id"] for row in pdf_resolutions],
                "text_namu_v2": text_summary["unresolved_query_ids"],
            },
        },
        "xlsx_human_review": {
            "resolutions": xlsx_resolutions,
            "approved_draft_candidate_query_ids": draft_manifest_ids,
            "pending_evidence_query_ids": XLSX_PENDING_EVIDENCE_IDS,
        },
        "pdf_file_lookup_companion": {
            "resolutions": pdf_resolutions,
            "approved_exclude_query_ids": [
                row["query_id"]
                for row in pdf_resolutions
                if row["user_gold_policy_decision"] == PDF_EXCLUDE_DECISION
            ],
            "stable_identity_required_exclude_query_ids": [
                row["query_id"]
                for row in pdf_resolutions
                if row["user_gold_policy_decision"] == PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION
            ],
        },
        "text_namu_v2": text_summary,
        "counts": counts,
        "validation": {
            "errors": validation_errors,
            "xlsx_approved_draft_candidate_count": len(draft_manifest_ids),
            "xlsx_pending_evidence_count": counts["xlsx"].get(XLSX_PENDING_EVIDENCE_DECISION, 0),
            "pdf_exclude_approved_count": counts["pdf"].get(PDF_EXCLUDE_DECISION, 0),
            "pdf_stable_identity_required_exclude_count": counts["pdf"].get(
                PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION, 0
            ),
            "text_unresolved_carried_forward_count": text_summary["unresolved_count"],
            "official_denominator_registry_not_modified": not registry_changed,
            "pending_evidence_not_in_draft_candidate_manifest": not set(XLSX_PENDING_EVIDENCE_IDS)
            & set(draft_manifest_ids),
            "generic_filename_pdf_rows_excluded_from_gold_v0_1": True,
            "pdf_excluded_rows_not_retrieval_failures": True,
            "text_resolution_attempted": False,
        },
    }


def build_xlsx_resolutions(draft: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in draft["xlsx_draft_decisions"]:
        query_id = row["query_id"]
        if row["proposed_user_decision"] == XLSX_INCLUDE_DRAFT:
            rows.append(
                {
                    "query_id": query_id,
                    "question_input": row.get("question_input", ""),
                    "user_gold_policy_decision": XLSX_APPROVED_DECISION,
                    "gold_v0_1_candidate_status": "APPROVED_DRAFT_CANDIDATE_NOT_FROZEN",
                    "final_denominator_status": "NOT_FROZEN",
                    "registry_mutation": False,
                    "official_denominator_frozen": False,
                    "rationale": "User approved the 23-row XLSX include batch as draft gold_v0.1 candidates only.",
                    "current_expected_answer": row.get("candidate_expected_answer", {}),
                    "current_evidence": row.get("candidate_expected_evidence", {}),
                    "current_citation_target": row.get("source_citation_target", {}),
                }
            )
        elif row["proposed_user_decision"] == XLSX_PENDING_EVIDENCE_DRAFT:
            expected_answer_status = "USER_REQUIRED" if query_id == "gq_xlsx_aggregation_001" else "NOT_FINAL"
            evidence_status = "USER_REQUIRED" if query_id == "gq_xlsx_aggregation_001" else "PENDING_VERIFICATION"
            rows.append(
                {
                    "query_id": query_id,
                    "question_input": row.get("question_input", ""),
                    "user_gold_policy_decision": XLSX_PENDING_EVIDENCE_DECISION,
                    "gold_v0_1_candidate_status": "EXCLUDED_PENDING_EVIDENCE",
                    "final_denominator_status": "UNRESOLVED",
                    "registry_mutation": False,
                    "official_denominator_frozen": False,
                    "include_in_draft_candidate_manifest": False,
                    "expected_answer_status": expected_answer_status,
                    "supporting_evidence_status": evidence_status,
                    "rationale": (
                        "User kept this row pending evidence and barred gold_v0.1 candidate inclusion until exact "
                        "evidence/citation sufficiency is verified."
                    ),
                    "current_expected_answer": row.get("candidate_expected_answer", {}),
                    "current_evidence": row.get("candidate_expected_evidence", {}),
                    "current_citation_target": row.get("source_citation_target", {}),
                }
            )
    return rows


def build_pdf_resolutions(draft: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in draft["pdf_draft_decisions"]:
        query_id = row["query_id"]
        if row["proposed_user_decision"] == PDF_EXCLUDE_DRAFT:
            rows.append(
                {
                    "query_id": query_id,
                    "user_gold_policy_decision": PDF_EXCLUDE_DECISION,
                    "gold_v0_1_status": "EXCLUDED_APPROVED",
                    "final_denominator_status": "EXCLUDED",
                    "registry_mutation": False,
                    "official_denominator_frozen": False,
                    "count_as_retrieval_failure": False,
                    "content_evidence_positive": False,
                    "rationale": "User approved the 6-row PDF exclude batch from gold_v0.1.",
                    "current_issue_tags": row.get("current_issue_tags", []),
                    "current_conflict_tags": row.get("current_conflict_tags", []),
                }
            )
        elif row["proposed_user_decision"] == PDF_PENDING_FILE_IDENTITY_DRAFT:
            rows.append(
                {
                    "query_id": query_id,
                    "user_gold_policy_decision": PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION,
                    "gold_v0_1_status": "EXCLUDED_APPROVED",
                    "final_denominator_status": "EXCLUDED",
                    "registry_mutation": False,
                    "official_denominator_frozen": False,
                    "generic_filename_identity_accepted": False,
                    "stable_document_identity_required": True,
                    "stable_document_identity_available": bool(
                        row.get("stable_document_identity", {}).get("available")
                    ),
                    "diagnostic_only_file_identity_candidate": True,
                    "count_as_retrieval_failure": False,
                    "content_evidence_positive": False,
                    "rationale": (
                        "User rejected generic filename identity for gold_v0.1, required stable document identity, "
                        "excluded the row from gold_v0.1, and allowed diagnostic-only file identity use if useful."
                    ),
                    "current_issue_tags": row.get("current_issue_tags", []),
                    "current_conflict_tags": row.get("current_conflict_tags", []),
                }
            )
    return rows


def build_text_resolution(draft: Mapping[str, Any]) -> dict[str, Any]:
    text_summary = draft["text_unresolved_carry_forward_summary"]
    return {
        "user_gold_policy_decision": TEXT_CARRY_FORWARD_DECISION,
        "resolution_attempted": False,
        "include_in_gold_v0_1": False,
        "unresolved_count": text_summary["unresolved_user_review_count"],
        "unresolved_query_ids": text_summary["unresolved_user_review_rows"],
        "summary_buckets": text_summary.get("summary_buckets", {}),
        "rationale": "User carried TEXT/Namu unresolved rows forward unchanged and barred inclusion in gold_v0.1.",
    }


def validate_resolutions(
    *,
    draft: Mapping[str, Any],
    xlsx_resolutions: list[Mapping[str, Any]],
    pdf_resolutions: list[Mapping[str, Any]],
    text_summary: Mapping[str, Any],
    registry_changed: bool,
) -> list[str]:
    errors: list[str] = []
    if draft.get("status") != "PASS":
        errors.append("source decision draft status is not PASS")
    if registry_changed:
        errors.append("official denominator registry changed")
    xlsx_counts = Counter(row["user_gold_policy_decision"] for row in xlsx_resolutions)
    pdf_counts = Counter(row["user_gold_policy_decision"] for row in pdf_resolutions)
    if xlsx_counts.get(XLSX_APPROVED_DECISION, 0) != 23:
        errors.append("expected 23 approved XLSX draft candidates")
    if xlsx_counts.get(XLSX_PENDING_EVIDENCE_DECISION, 0) != 2:
        errors.append("expected 2 XLSX pending evidence rows")
    if sorted(
        row["query_id"]
        for row in xlsx_resolutions
        if row["user_gold_policy_decision"] == XLSX_PENDING_EVIDENCE_DECISION
    ) != sorted(XLSX_PENDING_EVIDENCE_IDS):
        errors.append("XLSX pending evidence ids mismatch")
    if pdf_counts.get(PDF_EXCLUDE_DECISION, 0) != 6:
        errors.append("expected 6 approved PDF excludes")
    if pdf_counts.get(PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION, 0) != 3:
        errors.append("expected 3 PDF stable-identity-required excludes")
    if sorted(
        row["query_id"]
        for row in pdf_resolutions
        if row["user_gold_policy_decision"] == PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION
    ) != sorted(PDF_PENDING_FILE_IDENTITY_IDS):
        errors.append("PDF stable-identity-required exclude ids mismatch")
    if text_summary["unresolved_count"] != 23 or text_summary["include_in_gold_v0_1"]:
        errors.append("TEXT/Namu unresolved carry-forward policy mismatch")
    if any(row.get("registry_mutation") for row in xlsx_resolutions + pdf_resolutions):
        errors.append("a resolution requested registry mutation")
    if any(row.get("official_denominator_frozen") for row in xlsx_resolutions + pdf_resolutions):
        errors.append("a resolution froze official denominator membership")
    if any(row.get("count_as_retrieval_failure") for row in pdf_resolutions):
        errors.append("a PDF excluded row was counted as retrieval failure")
    if any(row.get("content_evidence_positive") for row in pdf_resolutions):
        errors.append("a PDF excluded row was converted to content evidence positive")
    return errors


def render_markdown(resolutions: Mapping[str, Any]) -> str:
    xlsx = resolutions["xlsx_human_review"]
    pdf = resolutions["pdf_file_lookup_companion"]
    text = resolutions["text_namu_v2"]
    lines = [
        "# Gold Policy User-Approved Resolutions v1",
        "",
        f"- Status: `{resolutions['status']}`",
        f"- Generated at: `{resolutions['generated_at']}`",
        f"- Source decision draft: `{resolutions['source_decision_draft']['path']}`",
        f"- Source review sheet: `{resolutions['source_user_review_sheet']['path']}`",
        "- This artifact records user gold-policy decisions only. It is not a frozen official denominator.",
        "",
        "## Counts",
        "",
        f"- XLSX approved draft candidates: `{resolutions['counts']['xlsx'][XLSX_APPROVED_DECISION]}`",
        f"- XLSX pending evidence: `{resolutions['counts']['xlsx'][XLSX_PENDING_EVIDENCE_DECISION]}`",
        f"- PDF approved excludes: `{resolutions['counts']['pdf'][PDF_EXCLUDE_DECISION]}`",
        f"- PDF excluded because stable identity is required: `{resolutions['counts']['pdf'][PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION]}`",
        f"- TEXT/Namu carried forward unresolved: `{text['unresolved_count']}`",
        "",
        "## Draft Candidate Manifest",
        "",
        "- Status: `DRAFT_ONLY_NOT_FROZEN`",
        f"- XLSX draft candidate IDs: {inline_ids(xlsx['approved_draft_candidate_query_ids'])}",
        f"- XLSX pending evidence excluded from manifest: {inline_ids(xlsx['pending_evidence_query_ids'])}",
        "- Official denominator registry mutation: `false`",
        "",
        "## XLSX Pending Evidence",
        "",
    ]
    for row in xlsx["resolutions"]:
        if row["user_gold_policy_decision"] == XLSX_PENDING_EVIDENCE_DECISION:
            lines.append(
                f"- `{row['query_id']}`: keep pending; candidate manifest inclusion is `false`; "
                f"expected answer status `{row['expected_answer_status']}`, evidence status `{row['supporting_evidence_status']}`."
            )
    lines.extend(["", "## PDF Exclusions", ""])
    lines.append(f"- Approved 6-row exclude batch: {inline_ids(pdf['approved_exclude_query_ids'])}")
    lines.append(
        "- Stable-identity-required excludes: "
        f"{inline_ids(pdf['stable_identity_required_exclude_query_ids'])}"
    )
    lines.append("- These rows are not retrieval failures and are not content-evidence positives.")
    lines.extend(
        [
            "",
            "## TEXT/Namu Carry-Forward",
            "",
            f"- Unresolved rows: `{text['unresolved_count']}`",
            f"- Row IDs: {inline_ids(text['unresolved_query_ids'])}",
            "- Resolution attempted: `false`",
            "- Include in gold_v0.1: `false`",
            "",
            "## Guardrails",
            "",
            f"- official_denominator_registry.json changed: `{resolutions['guardrails']['official_denominator_registry_changed']}`",
            f"- retrieval variants ran: `{resolutions['guardrails']['retrieval_variants_run']}`",
            f"- production namespace mutated: `{resolutions['guardrails']['production_namespace_mutated']}`",
            f"- diagnostic-only row promoted: `{resolutions['guardrails']['diagnostic_only_row_promoted']}`",
            f"- policy-excluded rows counted as retrieval failures: `{resolutions['guardrails']['policy_excluded_rows_counted_as_retrieval_failures']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def inline_ids(ids: Iterable[str]) -> str:
    values = list(ids)
    return ", ".join(f"`{value}`" for value in values) if values else "`none`"


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


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
