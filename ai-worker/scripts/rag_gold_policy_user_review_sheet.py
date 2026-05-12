"""Create a compact user-facing gold-policy review sheet.

The sheet is generated from rag_gold_policy_decision_draft_v1 and includes
only the user-facing policy decisions needed for the next review pass. It does
not run retrieval, mutate namespaces, or edit the denominator registry.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_DRAFT_JSON = REVIEW_DIR / "rag_gold_policy_decision_draft_v1.json"
DEFAULT_OUTPUT_MD = REVIEW_DIR / "rag_gold_policy_user_review_sheet_v1.md"
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
PDF_REVIEW_CSV = (
    REVIEW_DIR
    / "pdf_supplemental_gold_review"
    / "pdf_gold_review_pack_manual_v1_file_lookup_companion - "
    "pdf_gold_review_pack_manual_v1_file_lookup_companion.csv"
)

XLSX_INCLUDE_DECISION = "INCLUDE_AS_GOLD_V0_1_CANDIDATE"
XLSX_PENDING_EVIDENCE_DECISION = "KEEP_PENDING_EVIDENCE"
PDF_EXCLUDE_DECISION = "EXCLUDE_FROM_GOLD_V0_1"
PDF_PENDING_FILE_IDENTITY_DECISION = "KEEP_PENDING_FILE_IDENTITY_REVIEW"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_sha_before = sha256_file(Path(args.official_denominator_registry))
    draft = read_json(Path(args.draft_json))
    pdf_rows = keyed_rows(read_csv_rows(Path(args.pdf_review_csv)))
    sheet = render_review_sheet(draft, pdf_rows=pdf_rows)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(sheet, encoding="utf-8")
    registry_sha_after = sha256_file(Path(args.official_denominator_registry))
    status = "PASS" if validate_sheet_inputs(draft) and registry_sha_before == registry_sha_after else "FAIL"
    print(
        json.dumps(
            {
                "status": status,
                "output_md": repo_relative(Path(args.output_md)),
                "xlsx_pending_rows": 2,
                "pdf_pending_rows": 3,
                "xlsx_batch_include_rows": 23,
                "pdf_batch_exclude_rows": 6,
                "text_unresolved_carried_forward": 23,
                "official_denominator_registry_changed": registry_sha_before != registry_sha_after,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-json", default=str(DEFAULT_DRAFT_JSON))
    parser.add_argument("--pdf-review-csv", default=str(PDF_REVIEW_CSV))
    parser.add_argument("--official-denominator-registry", default=str(OFFICIAL_DENOMINATOR_REGISTRY))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def render_review_sheet(draft: Mapping[str, Any], *, pdf_rows: Mapping[str, Mapping[str, str]]) -> str:
    xlsx_pending = [
        row for row in draft["xlsx_draft_decisions"] if row["proposed_user_decision"] == XLSX_PENDING_EVIDENCE_DECISION
    ]
    xlsx_include = [
        row for row in draft["xlsx_draft_decisions"] if row["proposed_user_decision"] == XLSX_INCLUDE_DECISION
    ]
    pdf_pending = [
        row for row in draft["pdf_draft_decisions"] if row["proposed_user_decision"] == PDF_PENDING_FILE_IDENTITY_DECISION
    ]
    pdf_exclude = [
        row for row in draft["pdf_draft_decisions"] if row["proposed_user_decision"] == PDF_EXCLUDE_DECISION
    ]
    text_summary = draft["text_unresolved_carry_forward_summary"]

    lines = [
        "# Gold Policy User Review Sheet v1",
        "",
        f"- Generated at: `{utc_timestamp()}`",
        f"- Source decision draft: `{draft['source_resolution_packet']['json_path'].replace('resolution_packet', 'decision_draft')}`",
        "- Scope: 2 XLSX pending-evidence rows, 3 PDF pending file-identity rows, "
        "23 XLSX include-candidate confirmations, 6 PDF exclude-candidate confirmations, "
        "and 23 TEXT/Namu unresolved rows carried forward unchanged.",
        "- This sheet records user policy decisions only. It does not freeze an official denominator.",
        "- Guardrails: no retrieval variants, no production namespace mutation, no denominator registry edit, "
        "no diagnostic-only promotion.",
        "",
        "## Decision Summary",
        "",
        "- [ ] Approve the XLSX include-candidate batch as draft `gold_v0.1` candidates.",
        "- [ ] Approve the PDF exclude batch as draft exclusions from `gold_v0.1`.",
        "- [ ] Resolve or keep pending the 2 XLSX evidence rows below.",
        "- [ ] Resolve or keep pending the 3 PDF file-identity rows below.",
        "- [ ] Carry TEXT/Namu unresolved rows forward without resolving them in this task.",
        "",
        "## XLSX Pending Evidence Rows",
        "",
    ]
    for row in xlsx_pending:
        lines.extend(render_xlsx_actionable_row(row))

    lines.extend(["## PDF Pending File-Identity Rows", ""])
    for row in pdf_pending:
        lines.extend(render_pdf_actionable_row(row, pdf_rows.get(row["query_id"], {})))

    lines.extend(render_xlsx_batch_section(xlsx_include))
    lines.extend(render_pdf_batch_section(pdf_exclude))
    lines.extend(render_text_carry_forward_section(text_summary))
    lines.extend(render_guardrails(draft))
    return "\n".join(lines) + "\n"


def render_xlsx_actionable_row(row: Mapping[str, Any]) -> list[str]:
    return [
        f"### {row['query_id']}",
        "",
        f"- Question/input: {text_or_missing(row.get('question_input'))}",
        f"- Current expected answer: {answer_text(row.get('candidate_expected_answer', {}))}",
        f"- Current evidence/citation target: {xlsx_evidence_target(row)}",
        "- Current issue: expected evidence and citation sufficiency are not safely confirmed for candidate-manifest entry.",
        f"- Recommended decision: `{row['proposed_user_decision']}`",
        "- Exact user decision needed:",
        *[f"  - [ ] {decision}" for decision in row.get("exact_user_decision_needed", [])],
        "- User mark:",
        "  - [ ] Approve recommendation",
        "  - [ ] Reject recommendation",
        "  - [ ] Provide revised evidence/citation policy",
        "",
    ]


def render_pdf_actionable_row(row: Mapping[str, Any], raw_row: Mapping[str, str]) -> list[str]:
    stable = row.get("stable_document_identity", {})
    return [
        f"### {row['query_id']}",
        "",
        f"- Question/input: {text_or_missing(raw_row.get('query'))}",
        "- Current expected answer: not available in the decision draft; this row is pending file/document identity policy.",
        f"- Current evidence/citation target: {pdf_evidence_target(row, raw_row)}",
        "- Current issue: generic filename identity risk; stable document identity is not available; row must not be converted to content evidence positive.",
        f"- Recommended decision: `{row['proposed_user_decision']}`",
        f"- Stable document identity: `{stable.get('available')}` ({stable.get('basis') or 'none'})",
        "- Exact user decision needed:",
        *[f"  - [ ] {decision}" for decision in row.get("exact_user_decision_needed", [])],
        "- User mark:",
        "  - [ ] Approve recommendation",
        "  - [ ] Reject recommendation",
        "  - [ ] Provide stable document identity or lane decision",
        "",
    ]


def render_xlsx_batch_section(rows: list[Mapping[str, Any]]) -> list[str]:
    return [
        "## Batch Confirmation: XLSX Include Candidates",
        "",
        f"- Row count: `{len(rows)}`",
        f"- All row IDs: {inline_ids(row['query_id'] for row in rows)}",
        f"- Proposed batch decision: `{XLSX_INCLUDE_DECISION}` as draft `gold_v0.1` candidates.",
        "- Why batch approval is safe: each row already has confirmed answerability/relevance, "
        "an expected-answer source, and a citation target in the decision draft.",
        "- What remains not frozen: official denominator registry, final denominator membership, "
        "candidate manifest mutation, and any future scoring policy application.",
        "- User mark:",
        "  - [ ] Approve this batch",
        "  - [ ] Reject or split this batch",
        "",
    ]


def render_pdf_batch_section(rows: list[Mapping[str, Any]]) -> list[str]:
    return [
        "## Batch Confirmation: PDF Exclude Candidates",
        "",
        f"- Row count: `{len(rows)}`",
        f"- All row IDs: {inline_ids(row['query_id'] for row in rows)}",
        f"- Proposed batch decision: `{PDF_EXCLUDE_DECISION}` as draft exclusions from `gold_v0.1`.",
        "- Why batch approval is safe: each row is policy-excluded, not-answerable, irrelevant, "
        "or has an unstable evidence/lane conflict; exclusion does not count the row as a retrieval failure.",
        "- What remains not frozen: official denominator registry, final exclusion policy, and downstream metrics.",
        "- User mark:",
        "  - [ ] Approve this batch",
        "  - [ ] Reject or split this batch",
        "",
    ]


def render_text_carry_forward_section(text_summary: Mapping[str, Any]) -> list[str]:
    buckets = text_summary.get("summary_buckets", {})
    return [
        "## TEXT/Namu Carry-Forward",
        "",
        f"- Row count: `{text_summary['unresolved_user_review_count']}`",
        f"- Row IDs: {inline_ids(text_summary['unresolved_user_review_rows'])}",
        "- Resolution status: unchanged; no TEXT/Namu row is resolved in this task.",
        f"- Expected answer/evidence revisions: {inline_ids(buckets.get('expected_answer_or_evidence_revisions', []))}",
        f"- Second review: {inline_ids(buckets.get('second_review', []))}",
        f"- Invalid/ambiguous query: {inline_ids(buckets.get('invalid_or_ambiguous_query', []))}",
        f"- Evidence too broad: {inline_ids(buckets.get('evidence_too_broad', []))}",
        f"- Source-binding review required: {inline_ids(buckets.get('source_binding_review_required', []))}",
        "",
    ]


def render_guardrails(draft: Mapping[str, Any]) -> list[str]:
    guardrails = draft["guardrail_status"]
    return [
        "## Guardrail Confirmation",
        "",
        f"- official_denominator_registry.json changed: `{guardrails['official_denominator_registry_changed']}`",
        f"- retrieval variants ran: `{guardrails['retrieval_variants_run']}`",
        f"- production namespace mutated: `{guardrails['production_namespace_mutated']}`",
        f"- diagnostic-only row promoted: `{guardrails['diagnostic_only_row_promoted']}`",
        f"- PDF content/file identity lanes aggregated: `{guardrails['pdf_content_and_file_identity_aggregated']}`",
        "",
    ]


def xlsx_evidence_target(row: Mapping[str, Any]) -> str:
    evidence = row.get("candidate_expected_evidence", {})
    target = row.get("source_citation_target", {})
    evidence_text = evidence.get("summary") or "USER_REQUIRED"
    locator = " / ".join(
        part
        for part in [
            target.get("file"),
            target.get("sheet"),
            target.get("range"),
            target.get("citation_policy"),
        ]
        if part
    )
    return f"{evidence_text}; citation target: {locator or 'USER_REQUIRED'}"


def pdf_evidence_target(row: Mapping[str, Any], raw_row: Mapping[str, str]) -> str:
    evidence = row.get("proposed_expected_evidence_text_or_summary", {}).get("text") or "USER_REQUIRED"
    target_parts = [
        raw_row.get("expected_file_name"),
        raw_row.get("expected_document_version_id"),
        raw_row.get("expected_page_label") or raw_row.get("expected_page_no"),
        raw_row.get("expected_bbox"),
    ]
    locator = " / ".join(part for part in target_parts if part)
    return f"{evidence}; citation target: {locator or 'USER_REQUIRED'}"


def answer_text(answer: Mapping[str, Any]) -> str:
    text = clean(answer.get("text"))
    if not text:
        return "USER_REQUIRED"
    return text


def text_or_missing(value: Any) -> str:
    text = clean(value)
    return text if text else "USER_REQUIRED"


def inline_ids(ids: Iterable[str]) -> str:
    values = list(ids)
    return ", ".join(f"`{value}`" for value in values) if values else "`none`"


def validate_sheet_inputs(draft: Mapping[str, Any]) -> bool:
    return (
        draft.get("status") == "PASS"
        and len([row for row in draft["xlsx_draft_decisions"] if row["proposed_user_decision"] == XLSX_PENDING_EVIDENCE_DECISION]) == 2
        and len([row for row in draft["pdf_draft_decisions"] if row["proposed_user_decision"] == PDF_PENDING_FILE_IDENTITY_DECISION]) == 3
        and len([row for row in draft["xlsx_draft_decisions"] if row["proposed_user_decision"] == XLSX_INCLUDE_DECISION]) == 23
        and len([row for row in draft["pdf_draft_decisions"] if row["proposed_user_decision"] == PDF_EXCLUDE_DECISION]) == 6
        and draft["text_unresolved_carry_forward_summary"]["unresolved_user_review_count"] == 23
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def keyed_rows(rows: Iterable[Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    return {clean(row.get("query_id")): row for row in rows}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
