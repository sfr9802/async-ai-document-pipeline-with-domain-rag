"""Apply the TEXT/Namu model-assisted answer/citation review draft.

This creates a diagnostic-only applied artifact from the GPT draft review and
the generated-answer review input. It is not official gold, not promotion
evidence, and not an official metric input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_DRAFT_JSONL = REVIEW_DIR / "rag_text_namu_answer_citation_review_draft_gpt.jsonl"
DEFAULT_DRAFT_SUMMARY = REVIEW_DIR / "rag_text_namu_answer_citation_review_draft_gpt_summary.json"
DEFAULT_GENERATED_ANSWER_JSONL = REPORT_DIR / "rag_text_namu_generated_answer_review_input.jsonl"
DEFAULT_OUTPUT_JSON = REVIEW_DIR / "rag_text_namu_answer_citation_review_applied_diagnostic_v1.json"
DEFAULT_OUTPUT_MD = REVIEW_DIR / "rag_text_namu_answer_citation_review_applied_diagnostic_v1.md"

SCHEMA_VERSION = "rag_text_namu_answer_citation_review_applied_diagnostic_v1"
OFFICIAL_METRIC_STATUS = "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"
KEEP_DIAGNOSTIC_CANDIDATE = "KEEP_DIAGNOSTIC_CANDIDATE"
KEEP_WITH_CLEANUP = "KEEP_WITH_CLEANUP"
ANSWER_REWRITE_REQUIRED = "ANSWER_REWRITE_REQUIRED"
FULLY_SUPPORTED = "fully_supported"
INCOMPLETE_GENERATED_ANSWER = "citation_contains_correct_answer_but_generated_answer_incomplete"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_applied_report(
        draft_jsonl=Path(args.draft_jsonl),
        draft_summary=Path(args.draft_summary),
        generated_answer_jsonl=Path(args.generated_answer_jsonl),
    )
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    write_json(output_json, report)
    write_text(output_md, render_markdown(report))
    print_json(
        {
            "status": report["status"],
            "output_json": repo_relative(output_json),
            "output_md": repo_relative(output_md),
            "row_count": report["row_count"],
            "official_metric_input_rows": report["diagnostic_metric_preview"]["official_metric_input_rows"],
            "official_metric_status": report["diagnostic_metric_preview"]["official_metric_status"],
        }
    )
    return 0 if report["status"] == "APPLIED_DIAGNOSTIC_ONLY" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-jsonl", default=str(DEFAULT_DRAFT_JSONL))
    parser.add_argument("--draft-summary", default=str(DEFAULT_DRAFT_SUMMARY))
    parser.add_argument("--generated-answer-jsonl", default=str(DEFAULT_GENERATED_ANSWER_JSONL))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def build_applied_report(
    *,
    draft_jsonl: Path,
    draft_summary: Path,
    generated_answer_jsonl: Path,
) -> dict[str, Any]:
    generated_at = utc_timestamp()
    draft_rows, draft_parse_errors = read_jsonl_with_errors(draft_jsonl)
    generated_rows, generated_parse_errors = read_jsonl_with_errors(generated_answer_jsonl)
    summary = read_json_if_exists(draft_summary)

    generated_by_id = {clean(row.get("query_id")): row for row in generated_rows if clean(row.get("query_id"))}
    draft_by_id = {clean(row.get("query_id")): row for row in draft_rows if clean(row.get("query_id"))}
    generated_ids = set(generated_by_id)
    draft_ids = set(draft_by_id)
    missing_ids = sorted(generated_ids.difference(draft_ids))
    extra_ids = sorted(draft_ids.difference(generated_ids))
    duplicate_draft_ids = duplicate_query_ids(draft_rows)
    duplicate_generated_ids = duplicate_query_ids(generated_rows)
    blank_draft_row_numbers = blank_query_id_row_numbers(draft_rows)
    blank_generated_row_numbers = blank_query_id_row_numbers(generated_rows)

    applied_rows = [
        build_applied_row(draft_by_id[query_id], generated_by_id[query_id])
        for query_id in sorted(generated_ids.intersection(draft_ids))
    ]
    validation_errors = validation_errors_for(
        draft_rows=draft_rows,
        generated_rows=generated_rows,
        draft_parse_errors=draft_parse_errors,
        generated_parse_errors=generated_parse_errors,
        missing_ids=missing_ids,
        extra_ids=extra_ids,
        duplicate_draft_ids=duplicate_draft_ids,
        duplicate_generated_ids=duplicate_generated_ids,
        blank_draft_row_numbers=blank_draft_row_numbers,
        blank_generated_row_numbers=blank_generated_row_numbers,
        applied_row_count=len(applied_rows),
        summary=summary,
        generated_answer_jsonl=generated_answer_jsonl,
    )
    metrics = diagnostic_metric_preview(applied_rows)
    status = "APPLIED_DIAGNOSTIC_ONLY" if not validation_errors else "FAIL_CLOSED"
    answer_counts = dict(sorted(Counter(row["assistant_answer_judgment"] for row in applied_rows).items()))
    citation_counts = dict(sorted(Counter(row["assistant_citation_support_judgment"] for row in applied_rows).items()))
    action_counts = dict(sorted(Counter(row["assistant_review_action"] for row in applied_rows).items()))
    promotion_rows = sum(1 for row in draft_rows if row.get("promotion_evidence") is True)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "scope": "model_assisted_text_namu_answer_citation_review_applied_diagnostic_only",
        "diagnostic_only": True,
        "not_official_gold": True,
        "promotion_evidence": False,
        "official_metric_input": False,
        "source_artifacts": {
            "draft_jsonl": artifact_info(draft_jsonl),
            "draft_summary": artifact_info(draft_summary),
            "generated_answer_jsonl": artifact_info(generated_answer_jsonl),
        },
        "input_summary": {
            "draft_summary_schema_version": summary.get("schema_version"),
            "draft_summary_scope": summary.get("scope"),
            "draft_summary_input_sha256": summary.get("input_sha256"),
            "generated_answer_jsonl_sha256": sha256_if_exists(generated_answer_jsonl),
        },
        "row_count": len(applied_rows),
        "generated_answer_row_count": len(generated_rows),
        "draft_row_count": len(draft_rows),
        "assistant_answer_judgment_counts": answer_counts,
        "assistant_citation_support_judgment_counts": citation_counts,
        "review_action_counts": action_counts,
        "diagnostic_metric_preview": metrics,
        "applied_rows": applied_rows,
        "row_groups": {
            "metric_eligible_diagnostic_candidates": row_ids_with_action(applied_rows, KEEP_DIAGNOSTIC_CANDIDATE),
            "cleanup_only_rows": row_ids_with_action(applied_rows, KEEP_WITH_CLEANUP),
            "rewrite_required_rows": row_ids_with_action(applied_rows, ANSWER_REWRITE_REQUIRED),
            "citation_contains_correct_answer_but_generated_answer_incomplete": [
                row["query_id"]
                for row in applied_rows
                if row["assistant_citation_support_judgment"] == INCOMPLETE_GENERATED_ANSWER
            ],
        },
        "guardrails": {
            "diagnostic_only_all_rows": all(row.get("diagnostic_only") is True for row in applied_rows),
            "official_metric_input_rows": metrics["official_metric_input_rows"],
            "official_metrics_opened": False,
            "official_metric_status": OFFICIAL_METRIC_STATUS,
            "promotion_evidence_rows": promotion_rows,
            "official_denominator_registry_changed": False,
            "text_namu_gold_registry_changed": False,
            "candidate_artifact_mutated": False,
            "immutable_baseline_mutated": False,
            "production_namespace_mutation": False,
            "production_vector_index_mutation": False,
            "production_vector_written": False,
            "human_approval_required_for_official_metric": True,
        },
        "validation": {
            "ok": not validation_errors,
            "errors": validation_errors,
            "missing_query_ids": missing_ids,
            "extra_query_ids": extra_ids,
            "duplicate_draft_query_ids": duplicate_draft_ids,
            "duplicate_generated_query_ids": duplicate_generated_ids,
            "blank_draft_query_id_rows": blank_draft_row_numbers,
            "blank_generated_query_id_rows": blank_generated_row_numbers,
            "draft_parse_errors": draft_parse_errors,
            "generated_parse_errors": generated_parse_errors,
        },
        "remaining_blockers": [
            "Official TEXT answer/citation-support denominators remain closed.",
            "Model-assisted labels require human approval before official metric input can open.",
            "Rewrite-required rows need regenerated answers or manual cleanup before any official review lane.",
        ],
    }


def build_applied_row(draft: Mapping[str, Any], generated: Mapping[str, Any]) -> dict[str, Any]:
    action = clean(draft.get("assistant_review_action"))
    answer_judgment = clean(draft.get("assistant_answer_judgment"))
    citation_judgment = clean(draft.get("assistant_citation_support_judgment"))
    answer_pass_preview = action == KEEP_DIAGNOSTIC_CANDIDATE and answer_judgment == "correct"
    cleanup_pass_preview = action == KEEP_WITH_CLEANUP and answer_judgment == "correct_with_excess_context"
    rewrite_required = action == ANSWER_REWRITE_REQUIRED
    citation_fully_supported = citation_judgment == FULLY_SUPPORTED
    citation_incomplete = citation_judgment == INCOMPLETE_GENERATED_ANSWER
    return {
        "query_id": clean(draft.get("query_id")),
        "query": clean(draft.get("query") or generated.get("safe_query_text") or generated.get("query")),
        "assistant_answer_judgment": answer_judgment,
        "assistant_citation_support_judgment": citation_judgment,
        "assistant_review_action": action,
        "answer_pass_preview": answer_pass_preview,
        "cleanup_pass_preview": cleanup_pass_preview,
        "rewrite_required": rewrite_required,
        "diagnostic_citation_success_preview": citation_fully_supported and not rewrite_required,
        "official_answer_success": False,
        "official_citation_success": False,
        "suggested_extractive_answer_not_gold": clean(draft.get("suggested_extractive_answer_not_gold")),
        "assistant_review_notes": clean(draft.get("assistant_review_notes")),
        "generated_short_answer": clean(draft.get("generated_short_answer")),
        "generated_answer": clean(generated.get("generated_answer")),
        "cited_chunk_ids": clean_id_list(draft.get("cited_chunk_ids")) or clean_id_list(generated.get("cited_chunk_ids")),
        "retrieved_chunk_ids": clean_id_list(draft.get("retrieved_chunk_ids")) or clean_id_list(
            generated.get("retrieved_chunk_ids")
        ),
        "citation_text_excerpt": clean(draft.get("citation_text_excerpt")),
        "citation_contains_correct_answer_but_generated_answer_incomplete": citation_incomplete,
        "model_reviewer": clean(draft.get("model_reviewer")),
        "human_approval_required_for_official_metric": True,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def diagnostic_metric_preview(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    answer_pass = sum(1 for row in rows if row.get("answer_pass_preview") is True)
    cleanup_pass = sum(1 for row in rows if row.get("cleanup_pass_preview") is True)
    rewrite_required = sum(1 for row in rows if row.get("rewrite_required") is True)
    fully_supported = sum(
        1 for row in rows if row.get("assistant_citation_support_judgment") == FULLY_SUPPORTED
    )
    incomplete = sum(
        1 for row in rows if row.get("assistant_citation_support_judgment") == INCOMPLETE_GENERATED_ANSWER
    )
    return {
        "answer_pass_preview_count": answer_pass,
        "cleanup_pass_preview_count": cleanup_pass,
        "rewrite_required_count": rewrite_required,
        "citation_fully_supported_generated_answer_count": fully_supported,
        "citation_contains_correct_answer_but_generated_answer_incomplete_count": incomplete,
        "official_metric_input_rows": 0,
        "official_metric_status": OFFICIAL_METRIC_STATUS,
        "official_answer_success_count": 0,
        "official_citation_success_count": 0,
        "diagnostic_preview_not_official_metric": True,
    }


def validation_errors_for(
    *,
    draft_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
    draft_parse_errors: list[str],
    generated_parse_errors: list[str],
    missing_ids: list[str],
    extra_ids: list[str],
    duplicate_draft_ids: list[str],
    duplicate_generated_ids: list[str],
    blank_draft_row_numbers: list[int],
    blank_generated_row_numbers: list[int],
    applied_row_count: int,
    summary: Mapping[str, Any],
    generated_answer_jsonl: Path,
) -> list[str]:
    errors: list[str] = []
    if draft_parse_errors:
        errors.extend(f"draft JSONL parse error: {error}" for error in draft_parse_errors)
    if generated_parse_errors:
        errors.extend(f"generated-answer JSONL parse error: {error}" for error in generated_parse_errors)
    if missing_ids:
        errors.append(f"draft missing generated query ids: {', '.join(missing_ids)}")
    if extra_ids:
        errors.append(f"draft has extra query ids: {', '.join(extra_ids)}")
    if duplicate_draft_ids:
        errors.append(f"draft has duplicate query ids: {', '.join(duplicate_draft_ids)}")
    if duplicate_generated_ids:
        errors.append(f"generated-answer input has duplicate query ids: {', '.join(duplicate_generated_ids)}")
    if blank_draft_row_numbers:
        errors.append(f"draft has blank query_id rows: {', '.join(str(number) for number in blank_draft_row_numbers)}")
    if blank_generated_row_numbers:
        errors.append(
            "generated-answer input has blank query_id rows: "
            + ", ".join(str(number) for number in blank_generated_row_numbers)
        )
    if applied_row_count != len(draft_rows) or applied_row_count != len(generated_rows):
        errors.append("validated row count must match draft and generated-answer row counts")
    if any(row.get("diagnostic_only") is not True for row in draft_rows):
        errors.append("draft rows must keep diagnostic_only=true")
    if any(row.get("official_metric_input") is not False for row in draft_rows):
        errors.append("draft rows must keep official_metric_input=false")
    if any(row.get("promotion_evidence") is not False for row in draft_rows):
        errors.append("draft rows must keep promotion_evidence=false")
    if any(row.get("diagnostic_only") is not True for row in generated_rows):
        errors.append("generated-answer rows must keep diagnostic_only=true")
    if any(row.get("official_metric_input") is not False for row in generated_rows):
        errors.append("generated-answer rows must keep official_metric_input=false")
    if any(row.get("promotion_evidence") is not False for row in generated_rows):
        errors.append("generated-answer rows must keep promotion_evidence=false")
    action_values = {clean(row.get("assistant_review_action")) for row in draft_rows}
    allowed_actions = {KEEP_DIAGNOSTIC_CANDIDATE, KEEP_WITH_CLEANUP, ANSWER_REWRITE_REQUIRED}
    unknown_actions = sorted(action_values.difference(allowed_actions))
    if unknown_actions:
        errors.append(f"unknown assistant_review_action values: {', '.join(unknown_actions)}")
    if summary:
        if summary.get("official_metric_input_rows") not in {0, None}:
            errors.append("draft summary official_metric_input_rows must be 0")
        if summary.get("not_official_gold") is not True:
            errors.append("draft summary must state not_official_gold=true")
        if summary.get("not_promotion_evidence") is not True:
            errors.append("draft summary must state not_promotion_evidence=true")
        expected_sha = clean(summary.get("input_sha256")).lower()
        actual_sha = (sha256_if_exists(generated_answer_jsonl) or "").lower()
        if expected_sha and actual_sha and expected_sha != actual_sha:
            errors.append("draft summary input_sha256 does not match generated-answer JSONL")
    else:
        errors.append("draft summary is missing or invalid JSON")
    return errors


def render_markdown(report: Mapping[str, Any]) -> str:
    metrics = report["diagnostic_metric_preview"]
    actions = report["review_action_counts"]
    lines = [
        "# TEXT/Namu Answer/Citation Diagnostic Review Applied",
        "",
        f"- status: `{report['status']}`",
        f"- row_count: `{report['row_count']}`",
        f"- diagnostic_only: `{report['diagnostic_only']}`",
        f"- not_official_gold: `{report['not_official_gold']}`",
        f"- promotion_evidence: `{report['promotion_evidence']}`",
        "",
        "## Review Actions",
        "",
        f"- keep diagnostic candidate: `{actions.get(KEEP_DIAGNOSTIC_CANDIDATE, 0)}`",
        f"- keep with cleanup: `{actions.get(KEEP_WITH_CLEANUP, 0)}`",
        f"- answer rewrite required: `{actions.get(ANSWER_REWRITE_REQUIRED, 0)}`",
        "",
        "## Diagnostic Metric Preview",
        "",
        f"- answer_pass_preview_count: `{metrics['answer_pass_preview_count']}`",
        f"- cleanup_pass_preview_count: `{metrics['cleanup_pass_preview_count']}`",
        f"- rewrite_required_count: `{metrics['rewrite_required_count']}`",
        f"- citation_fully_supported_generated_answer_count: `{metrics['citation_fully_supported_generated_answer_count']}`",
        "- citation_contains_correct_answer_but_generated_answer_incomplete_count: "
        f"`{metrics['citation_contains_correct_answer_but_generated_answer_incomplete_count']}`",
        f"- official_metric_input_rows: `{metrics['official_metric_input_rows']}`",
        f"- official_metric_status: `{metrics['official_metric_status']}`",
        "",
        "## Guardrails",
        "",
        f"- official metrics opened: `{report['guardrails']['official_metrics_opened']}`",
        f"- promotion evidence rows: `{report['guardrails']['promotion_evidence_rows']}`",
        f"- production vector index mutation: `{report['guardrails']['production_vector_index_mutation']}`",
        f"- validation ok: `{report['validation']['ok']}`",
    ]
    return "\n".join(lines) + "\n"


def row_ids_with_action(rows: list[Mapping[str, Any]], action: str) -> list[str]:
    return [clean(row.get("query_id")) for row in rows if row.get("assistant_review_action") == action]


def duplicate_query_ids(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    counts = Counter(clean(row.get("query_id")) for row in rows if clean(row.get("query_id")))
    return sorted(query_id for query_id, count in counts.items() if count > 1)


def blank_query_id_row_numbers(rows: Iterable[Mapping[str, Any]]) -> list[int]:
    return [line_number for line_number, row in enumerate(rows, start=1) if not clean(row.get("query_id"))]


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.exists():
        return rows, [f"{repo_relative(path)}: missing"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{repo_relative(path)}:{line_number}: {exc.msg}")
                continue
            if not isinstance(payload, dict):
                errors.append(f"{repo_relative(path)}:{line_number}: row must be a JSON object")
                continue
            rows.append(payload)
    return rows, errors


def clean_id_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.replace("|", ";").replace(",", ";").split(";") if part.strip()]
    if isinstance(value, Iterable):
        return [clean(item) for item in value if clean(item)]
    return []


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def artifact_info(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_if_exists(path),
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_if_exists(path: Path) -> str | None:
    return sha256_file(path) if path.exists() else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
