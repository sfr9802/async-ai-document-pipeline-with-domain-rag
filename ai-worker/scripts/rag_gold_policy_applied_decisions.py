"""Apply user gold-policy decisions as report-only artifacts.

This script consumes rag_gold_policy_user_approved_resolutions_v1, writes an
applied-decision report, and updates the user review sheet status. It does not
edit the official denominator registry, run retrieval variants, or mutate
production namespaces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_APPROVED_RESOLUTIONS_JSON = REVIEW_DIR / "rag_gold_policy_user_approved_resolutions_v1.json"
DEFAULT_REVIEW_SHEET_MD = REVIEW_DIR / "rag_gold_policy_user_review_sheet_v1.md"
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"

DEFAULT_JSON_OUTPUT = REVIEW_DIR / "rag_gold_policy_applied_decisions_v1.json"
DEFAULT_MD_OUTPUT = REVIEW_DIR / "rag_gold_policy_applied_decisions_v1.md"

SCHEMA_VERSION = "rag_gold_policy_applied_decisions_v1"

XLSX_APPROVED_DECISION = "APPROVE_DRAFT_GOLD_V0_1_CANDIDATE"
XLSX_PENDING_EVIDENCE_DECISION = "KEEP_PENDING_EVIDENCE"
PDF_EXCLUDE_DECISION = "EXCLUDE_FROM_GOLD_V0_1"
PDF_EXCLUDE_REQUIRE_STABLE_IDENTITY_DECISION = "EXCLUDE_FROM_GOLD_V0_1_REQUIRE_STABLE_IDENTITY"
TEXT_CARRY_FORWARD_DECISION = "CARRY_FORWARD_UNRESOLVED"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_path = Path(args.official_denominator_registry)
    registry_sha_before = sha256_file(registry_path)
    approved = read_json(Path(args.approved_resolutions_json))
    registry_sha_after = sha256_file(registry_path)
    applied = build_applied_decisions(
        approved_resolutions=approved,
        approved_resolutions_path=Path(args.approved_resolutions_json),
        review_sheet_path=Path(args.review_sheet_md),
        official_denominator_registry=registry_path,
        registry_sha_before=registry_sha_before,
        registry_sha_after=registry_sha_after,
    )

    review_sheet_text = render_applied_review_sheet(applied)
    Path(args.review_sheet_md).write_text(review_sheet_text, encoding="utf-8")
    applied["source_user_review_sheet"]["sha256_after_status_update"] = sha256_file(Path(args.review_sheet_md))

    write_json(Path(args.output_json), applied)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(render_markdown(applied), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": applied["status"],
                "output_json": repo_relative(Path(args.output_json)),
                "output_md": repo_relative(Path(args.output_md)),
                "review_sheet_updated": repo_relative(Path(args.review_sheet_md)),
                "xlsx_draft_candidate_count": applied["counts"]["xlsx_draft_candidates_applied"],
                "xlsx_pending_evidence_count": applied["counts"]["xlsx_pending_evidence_applied"],
                "pdf_excluded_count": applied["counts"]["pdf_excluded_applied"],
                "pdf_stable_identity_required_excluded_count": applied["counts"][
                    "pdf_stable_identity_required_excluded_applied"
                ],
                "text_unresolved_carried_forward_count": applied["counts"]["text_unresolved_carried_forward"],
                "official_denominator_registry_changed": applied["guardrails"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if applied["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-resolutions-json", default=str(DEFAULT_APPROVED_RESOLUTIONS_JSON))
    parser.add_argument("--review-sheet-md", default=str(DEFAULT_REVIEW_SHEET_MD))
    parser.add_argument("--official-denominator-registry", default=str(OFFICIAL_DENOMINATOR_REGISTRY))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUTPUT))
    return parser.parse_args(argv)


def build_applied_decisions(
    *,
    approved_resolutions: Mapping[str, Any],
    approved_resolutions_path: Path,
    review_sheet_path: Path,
    official_denominator_registry: Path,
    registry_sha_before: str,
    registry_sha_after: str,
) -> dict[str, Any]:
    xlsx = approved_resolutions["xlsx_human_review"]
    pdf = approved_resolutions["pdf_file_lookup_companion"]
    text = approved_resolutions["text_namu_v2"]
    manifest = approved_resolutions["draft_gold_v0_1_candidate_manifest"]
    registry_changed = registry_sha_before != registry_sha_after

    applied = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "source_user_approved_resolutions": {
            "path": repo_relative(approved_resolutions_path),
            "sha256": sha256_file(approved_resolutions_path),
            "status": approved_resolutions.get("status"),
        },
        "source_user_review_sheet": {
            "path": repo_relative(review_sheet_path),
            "sha256_before_status_update": sha256_file(review_sheet_path) if review_sheet_path.exists() else "",
            "sha256_after_status_update": "",
        },
        "application_scope": {
            "report_only": True,
            "official_denominator_registry_mutation": False,
            "official_denominator_open_or_freeze": False,
            "retrieval_variants_run": False,
            "production_namespace_mutation": False,
            "pdf_content_file_identity_aggregation": False,
        },
        "guardrails": {
            "report_only": True,
            "official_denominator_registry_path": repo_relative(official_denominator_registry),
            "official_denominator_registry_sha256_before": registry_sha_before,
            "official_denominator_registry_sha256_after": registry_sha_after,
            "official_denominator_registry_changed": registry_changed,
            "official_denominator_opened": False,
            "official_denominator_frozen": False,
            "retrieval_variants_run": False,
            "production_namespace_mutated": False,
            "diagnostic_only_row_promoted": False,
            "pdf_content_and_file_identity_aggregated": False,
            "policy_excluded_rows_counted_as_retrieval_failures": False,
            "unresolved_text_rows_included_in_gold_v0_1": False,
        },
        "applied_decisions": {
            "xlsx_draft_gold_v0_1_candidates": {
                "status": "APPLIED_DRAFT_ONLY_NOT_FROZEN",
                "query_ids": xlsx["approved_draft_candidate_query_ids"],
                "registry_mutation": False,
                "official_denominator_frozen": False,
            },
            "xlsx_pending_evidence": {
                "status": "APPLIED_KEEP_PENDING_EVIDENCE",
                "query_ids": xlsx["pending_evidence_query_ids"],
                "gold_v0_1_candidate_manifest_inclusion": False,
                "row_notes": {
                    "gq_xlsx_date_number_format_003": "Pending exact evidence/citation sufficiency verification.",
                    "gq_xlsx_aggregation_001": "Expected answer and supporting evidence remain USER_REQUIRED.",
                },
            },
            "pdf_excluded_from_gold_v0_1": {
                "status": "APPLIED_EXCLUDE_FROM_GOLD_V0_1",
                "query_ids": pdf["approved_exclude_query_ids"],
                "count_as_retrieval_failure": False,
            },
            "pdf_stable_identity_required_excluded": {
                "status": "APPLIED_EXCLUDE_REQUIRE_STABLE_DOCUMENT_IDENTITY",
                "query_ids": pdf["stable_identity_required_exclude_query_ids"],
                "generic_filename_identity_accepted": False,
                "stable_document_identity_required": True,
                "diagnostic_only_file_identity_review_allowed": True,
                "count_as_retrieval_failure": False,
            },
            "text_namu_v2_unresolved_carry_forward": {
                "status": "APPLIED_CARRY_FORWARD_UNCHANGED",
                "query_ids": text["unresolved_query_ids"],
                "resolution_attempted": False,
                "include_in_gold_v0_1": False,
            },
        },
        "draft_gold_v0_1_candidate_manifest": {
            "status": "DRAFT_ONLY_NOT_FROZEN",
            "included_query_ids_by_track": manifest["included_query_ids_by_track"],
            "excluded_pending_query_ids_by_track": manifest["excluded_pending_query_ids_by_track"],
            "registry_mutation": False,
            "official_denominator_frozen": False,
        },
        "counts": {
            "xlsx_draft_candidates_applied": len(xlsx["approved_draft_candidate_query_ids"]),
            "xlsx_pending_evidence_applied": len(xlsx["pending_evidence_query_ids"]),
            "pdf_excluded_applied": len(pdf["approved_exclude_query_ids"]),
            "pdf_stable_identity_required_excluded_applied": len(
                pdf["stable_identity_required_exclude_query_ids"]
            ),
            "text_unresolved_carried_forward": text["unresolved_count"],
        },
    }
    validation_errors = validate_applied(applied, approved_resolutions)
    applied["validation"] = {
        "errors": validation_errors,
        "approved_resolutions_status_pass": approved_resolutions.get("status") == "PASS",
        "xlsx_draft_candidate_count_is_23": applied["counts"]["xlsx_draft_candidates_applied"] == 23,
        "xlsx_pending_evidence_count_is_2": applied["counts"]["xlsx_pending_evidence_applied"] == 2,
        "pdf_excluded_count_is_6": applied["counts"]["pdf_excluded_applied"] == 6,
        "pdf_stable_identity_required_excluded_count_is_3": applied["counts"][
            "pdf_stable_identity_required_excluded_applied"
        ]
        == 3,
        "text_unresolved_count_is_23": applied["counts"]["text_unresolved_carried_forward"] == 23,
        "official_denominator_registry_not_modified": not registry_changed,
        "pending_xlsx_rows_not_in_manifest": not set(
            applied["applied_decisions"]["xlsx_pending_evidence"]["query_ids"]
        )
        & set(manifest["included_query_ids_by_track"]["xlsx_human_review"]),
    }
    applied["status"] = "PASS" if not validation_errors else "FAIL"
    return applied


def validate_applied(applied: Mapping[str, Any], approved_resolutions: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if approved_resolutions.get("status") != "PASS":
        errors.append("approved resolutions status is not PASS")
    counts = applied["counts"]
    expected_counts = {
        "xlsx_draft_candidates_applied": 23,
        "xlsx_pending_evidence_applied": 2,
        "pdf_excluded_applied": 6,
        "pdf_stable_identity_required_excluded_applied": 3,
        "text_unresolved_carried_forward": 23,
    }
    for key, expected in expected_counts.items():
        if counts.get(key) != expected:
            errors.append(f"{key} expected {expected}, got {counts.get(key)}")
    guardrails = applied["guardrails"]
    for key in [
        "official_denominator_registry_changed",
        "official_denominator_opened",
        "official_denominator_frozen",
        "retrieval_variants_run",
        "production_namespace_mutated",
        "diagnostic_only_row_promoted",
        "pdf_content_and_file_identity_aggregated",
        "policy_excluded_rows_counted_as_retrieval_failures",
        "unresolved_text_rows_included_in_gold_v0_1",
    ]:
        if guardrails.get(key):
            errors.append(f"guardrail breach: {key}")
    manifest_ids = set(
        applied["draft_gold_v0_1_candidate_manifest"]["included_query_ids_by_track"]["xlsx_human_review"]
    )
    pending_ids = set(applied["applied_decisions"]["xlsx_pending_evidence"]["query_ids"])
    if manifest_ids & pending_ids:
        errors.append("pending XLSX evidence row included in draft candidate manifest")
    if applied["applied_decisions"]["pdf_stable_identity_required_excluded"]["generic_filename_identity_accepted"]:
        errors.append("generic filename identity accepted for excluded PDF rows")
    if applied["applied_decisions"]["text_namu_v2_unresolved_carry_forward"]["resolution_attempted"]:
        errors.append("TEXT/Namu resolution attempted")
    return errors


def render_applied_review_sheet(applied: Mapping[str, Any]) -> str:
    decisions = applied["applied_decisions"]
    return "\n".join(
        [
            "# Gold Policy User Review Sheet v1",
            "",
            f"- Status: `APPLIED`",
            f"- Applied at: `{applied['generated_at']}`",
            f"- Applied-decision artifact: `ai-worker/eval/review/rag_gold_policy_applied_decisions_v1.json`",
            "- This sheet records user policy decisions only. It does not freeze an official denominator.",
            "- Guardrails: no retrieval variants, no production namespace mutation, no denominator registry edit, "
            "no diagnostic-only promotion, and no PDF content/file-identity aggregation.",
            "",
            "## Applied Decision Summary",
            "",
            f"- [x] XLSX include-candidate batch approved as draft `gold_v0.1` candidates only: `{applied['counts']['xlsx_draft_candidates_applied']}` rows.",
            f"- [x] XLSX pending evidence kept out of candidate manifest: {inline_ids(decisions['xlsx_pending_evidence']['query_ids'])}.",
            f"- [x] PDF exclude batch approved as `EXCLUDE_FROM_GOLD_V0_1`: `{applied['counts']['pdf_excluded_applied']}` rows.",
            f"- [x] PDF generic filename identity rejected; stable document identity required; excluded from `gold_v0.1`: {inline_ids(decisions['pdf_stable_identity_required_excluded']['query_ids'])}.",
            f"- [x] TEXT/Namu unresolved rows carried forward unchanged and excluded from `gold_v0.1`: `{applied['counts']['text_unresolved_carried_forward']}` rows.",
            "",
            "## XLSX Pending Evidence Rows",
            "",
            "- `gq_xlsx_date_number_format_003`: `KEEP_PENDING_EVIDENCE`; do not include in `gold_v0.1` candidate manifest until exact evidence/citation sufficiency is verified.",
            "- `gq_xlsx_aggregation_001`: `KEEP_PENDING_EVIDENCE`; do not include in `gold_v0.1`; expected answer and supporting evidence remain `USER_REQUIRED`.",
            "",
            "## PDF Applied Exclusions",
            "",
            f"- Exclude batch: {inline_ids(decisions['pdf_excluded_from_gold_v0_1']['query_ids'])}",
            f"- Stable-identity-required excludes: {inline_ids(decisions['pdf_stable_identity_required_excluded']['query_ids'])}",
            "- These rows are not retrieval failures and are not content-evidence positives.",
            "",
            "## XLSX Draft Candidate Batch",
            "",
            f"- Draft candidate IDs: {inline_ids(decisions['xlsx_draft_gold_v0_1_candidates']['query_ids'])}",
            "- What remains not frozen: official denominator registry, official denominator membership, and future scoring policy.",
            "",
            "## TEXT/Namu Carry-Forward",
            "",
            f"- Row IDs: {inline_ids(decisions['text_namu_v2_unresolved_carry_forward']['query_ids'])}",
            "- Resolution attempted: `false`",
            "- Include in `gold_v0.1`: `false`",
            "",
            "## Guardrail Confirmation",
            "",
            f"- official_denominator_registry.json changed: `{applied['guardrails']['official_denominator_registry_changed']}`",
            f"- official denominator opened/frozen: `{applied['guardrails']['official_denominator_opened'] or applied['guardrails']['official_denominator_frozen']}`",
            f"- retrieval variants ran: `{applied['guardrails']['retrieval_variants_run']}`",
            f"- production namespace mutated: `{applied['guardrails']['production_namespace_mutated']}`",
            f"- diagnostic-only row promoted: `{applied['guardrails']['diagnostic_only_row_promoted']}`",
            f"- PDF content/file identity lanes aggregated: `{applied['guardrails']['pdf_content_and_file_identity_aggregated']}`",
            "",
        ]
    )


def render_markdown(applied: Mapping[str, Any]) -> str:
    decisions = applied["applied_decisions"]
    return "\n".join(
        [
            "# Gold Policy Applied Decisions v1",
            "",
            f"- Status: `{applied['status']}`",
            f"- Generated at: `{applied['generated_at']}`",
            f"- Source approved resolutions: `{applied['source_user_approved_resolutions']['path']}`",
            "- This is report-only. It does not open, freeze, or mutate the official denominator.",
            "",
            "## Applied Counts",
            "",
            f"- XLSX draft candidates: `{applied['counts']['xlsx_draft_candidates_applied']}`",
            f"- XLSX pending evidence: `{applied['counts']['xlsx_pending_evidence_applied']}`",
            f"- PDF excluded: `{applied['counts']['pdf_excluded_applied']}`",
            f"- PDF stable-identity-required excluded: `{applied['counts']['pdf_stable_identity_required_excluded_applied']}`",
            f"- TEXT/Namu unresolved carry-forward: `{applied['counts']['text_unresolved_carried_forward']}`",
            "",
            "## Applied Decisions",
            "",
            f"- XLSX draft candidates: {inline_ids(decisions['xlsx_draft_gold_v0_1_candidates']['query_ids'])}",
            f"- XLSX pending evidence: {inline_ids(decisions['xlsx_pending_evidence']['query_ids'])}",
            f"- PDF exclude batch: {inline_ids(decisions['pdf_excluded_from_gold_v0_1']['query_ids'])}",
            f"- PDF stable-identity-required excludes: {inline_ids(decisions['pdf_stable_identity_required_excluded']['query_ids'])}",
            f"- TEXT/Namu carry-forward: {inline_ids(decisions['text_namu_v2_unresolved_carry_forward']['query_ids'])}",
            "",
            "## Guardrails",
            "",
            f"- official_denominator_registry.json changed: `{applied['guardrails']['official_denominator_registry_changed']}`",
            f"- official denominator opened: `{applied['guardrails']['official_denominator_opened']}`",
            f"- official denominator frozen: `{applied['guardrails']['official_denominator_frozen']}`",
            f"- retrieval variants ran: `{applied['guardrails']['retrieval_variants_run']}`",
            f"- production namespace mutated: `{applied['guardrails']['production_namespace_mutated']}`",
            f"- diagnostic-only row promoted: `{applied['guardrails']['diagnostic_only_row_promoted']}`",
            f"- PDF lanes aggregated: `{applied['guardrails']['pdf_content_and_file_identity_aggregated']}`",
            f"- policy-excluded rows counted as retrieval failures: `{applied['guardrails']['policy_excluded_rows_counted_as_retrieval_failures']}`",
            "",
        ]
    )


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
