"""Generate a diagnostic-only XLSX human gold-review pack.

The pack is for human review only. It does not update gold files, does not
promote diagnostic answers, and keeps official XLSX answer denominators at 0.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
EVAL_RUNS_DIR = AI_WORKER_ROOT / "eval" / "artifacts" / "eval_runs"
DEFAULT_SOURCE_ARTIFACT_DIR = (
    EVAL_RUNS_DIR / "pdf_xlsx_answer_shape_xlsx_llm_answer_probe_20260506T070258Z"
)
DEFAULT_GOLD_FILES = [
    AI_WORKER_ROOT / "eval" / "review" / "gold_set_review" / "xlsx_gold_review_pack.csv",
]

SCHEMA_VERSION = "rag_pdf_xlsx_gold_human_review_pack_v1"
RUN_PREFIX = "pdf_xlsx_gold_human_review_pack"

USER_DECISION_COLUMNS = [
    "user_answerability_label",
    "user_relevance_label",
    "user_gold_answer_shape",
    "user_expected_answer_text",
    "user_required_entity_anchors",
    "user_required_header_anchors",
    "user_required_target_values",
    "user_required_evidence_locator",
    "user_required_citation_policy",
    "user_expected_evidence_text_or_summary",
    "user_gold_policy_decision",
    "user_include_in_official_denominator",
    "user_review_notes",
]

REVIEW_PACK_COLUMNS = [
    "query_id",
    "query",
    "track",
    "expected_answer_shape_existing",
    "answer_allowed_diagnostic",
    "fail_closed_reason",
    "selected_searchunit_id",
    "selected_searchunit_rank",
    "sheet",
    "range",
    "citation_locator",
    "evidence_summary",
    "evidence_headers",
    "evidence_row_values",
    "evidence_cell_values",
    "evidence_content_source_fields",
    "deterministic_compiled_answer",
    "deterministic_compiled_status",
    "llm_answer",
    "llm_answer_type",
    "llm_abstain_reason",
    "llm_citations",
    "llm_keyword_echo_only",
    "llm_unsupported_claims",
    "llm_gold_leakage_suspected",
    "expected_answer_text_existing",
    "expected_answer_text_role_llm_suggested",
    "must_contain_terms_existing",
    "must_contain_terms_roles_llm_suggested",
    "human_review_required_llm_suggested",
    "review_reason_llm_suggested",
    *USER_DECISION_COLUMNS,
    "suggested_review_priority",
    "suggested_review_category",
    "suggested_possible_answer_shape",
    "suggested_reason",
]

TRIAGE_COLUMNS = [
    "query_id",
    "query",
    "llm_answer",
    "deterministic_compiled_answer",
    "evidence_summary",
    "expected_answer_text_existing",
    "expected_answer_text_role_llm_suggested",
    "must_contain_terms_existing",
    "must_contain_terms_roles_llm_suggested",
    "triage_label_suggested",
    "triage_rationale",
    "recommended_next_action",
]

SUGGESTED_REVIEW_CATEGORIES = {
    "CELL_VALUE_CANDIDATE",
    "ROW_SUMMARY_CANDIDATE",
    "RANGE_LOCATION_SUMMARY_CANDIDATE",
    "POLICY_PENDING_REVIEW",
    "HIDDEN_ROW_OR_COLUMN_POLICY_REVIEW",
    "FORMULA_VALUE_POLICY_REVIEW",
    "DATE_NUMBER_FORMAT_POLICY_REVIEW",
    "AGGREGATION_POLICY_REVIEW",
    "HEADER_AMBIGUITY_REVIEW",
    "KEYWORD_ECHO_TRIAGE",
    "EVIDENCE_INSUFFICIENT",
    "QUERY_ANCHOR_MISMATCH",
    "GOLD_FIELD_AMBIGUITY_REVIEW",
}

TRIAGE_LABELS = {
    "TRUE_KEYWORD_ECHO",
    "TARGET_HEADER_NOT_BOUND",
    "RANGE_SUMMARY_EXPECTED",
    "ROW_SUMMARY_EXPECTED",
    "CELL_VALUE_EXPECTED_BUT_ENTITY_RETURNED",
    "EXPECTED_TEXT_IS_ANCHOR_NOT_ANSWER",
    "MUST_CONTAIN_ROLE_MISCLASSIFIED",
    "CHECKER_FALSE_POSITIVE",
    "HUMAN_GOLD_POLICY_REQUIRED",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_pack(
        source_artifact_dir=Path(args.source_artifact_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        run_prefix=args.run_prefix,
        gold_files=[Path(path) for path in args.gold_file],
    )
    print_json(
        {
            "status": report["status"],
            "artifact_dir": report["artifact_dir"],
            "review_pack_row_count": report["review_pack_row_count"],
            "keyword_echo_triage_row_count": report["keyword_echo_triage_row_count"],
            "human_review_required_count": report["human_review_required_count"],
            "official_xlsx_answer_eval_denominator": report["official_xlsx_answer_eval_denominator"],
            "promotion_evidence": report["promotion_evidence"],
            "gold_files_modified": report["gold_files_modified"],
        }
    )
    return 0 if report["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-artifact-dir", default=str(DEFAULT_SOURCE_ARTIFACT_DIR))
    parser.add_argument("--output-root", default=str(EVAL_RUNS_DIR))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-prefix", default=RUN_PREFIX)
    parser.add_argument(
        "--gold-file",
        action="append",
        default=[str(path) for path in DEFAULT_GOLD_FILES],
        help="Gold/review file to hash before and after generation. Files are never written.",
    )
    return parser.parse_args(argv)


def run_pack(
    *,
    source_artifact_dir: Path,
    output_root: Path,
    run_id: str = "",
    run_prefix: str = RUN_PREFIX,
    gold_files: list[Path] | None = None,
) -> dict[str, Any]:
    run_id = run_id or utc_run_id()
    generated_at = utc_timestamp()
    artifact_dir = output_root / f"{run_prefix}_{run_id}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    gold_files = gold_files if gold_files is not None else list(DEFAULT_GOLD_FILES)
    gold_before = file_snapshots(gold_files)

    source_manifest = read_json_object(source_artifact_dir / "manifest.json")
    source_report = read_json_object(source_artifact_dir / "llm_answer_probe_report.json")
    llm_inputs = read_jsonl(source_artifact_dir / "llm_answer_probe_inputs.jsonl")
    llm_outputs = read_jsonl(source_artifact_dir / "llm_answer_probe_outputs.jsonl")
    role_rows = read_jsonl(source_artifact_dir / "gold_intent_role_probe.jsonl")
    role_csv_rows = read_csv_rows(source_artifact_dir / "gold_intent_role_probe.csv")

    source_paths = source_paths_from_manifest(source_manifest)
    answer_inputs = read_jsonl(source_paths["answer_generation_inputs"])
    evidence_rows = read_jsonl(source_paths["evidence_objects"])
    compiled_rows = read_jsonl(source_paths["compiled_answers"])

    output_by_id = keyed_by_query_id(llm_outputs)
    role_by_id = keyed_by_query_id(role_rows)
    source_by_id = keyed_by_query_id(answer_inputs)
    evidence_by_id = keyed_by_query_id(evidence_rows)
    compiled_by_id = keyed_by_query_id(compiled_rows)

    review_rows = [
        build_review_row(
            probe_input=row,
            llm_output=output_by_id.get(clean(row.get("query_id")), {}),
            role_row=role_by_id.get(clean(row.get("query_id")), {}),
            source_row=source_by_id.get(clean(row.get("query_id")), {}),
            evidence_row=evidence_by_id.get(clean(row.get("query_id")), {}),
            compiled_row=compiled_by_id.get(clean(row.get("query_id")), {}),
        )
        for row in llm_inputs
        if clean(row.get("track")).upper() == "XLSX"
    ]
    triage_rows = [build_triage_row(row) for row in review_rows if parse_bool(row.get("llm_keyword_echo_only"))]

    review_csv_path = artifact_dir / "xlsx_gold_human_review_pack.csv"
    review_jsonl_path = artifact_dir / "xlsx_gold_human_review_pack.jsonl"
    manifest_path = artifact_dir / "xlsx_gold_human_review_pack_manifest.json"
    readme_path = artifact_dir / "xlsx_gold_human_review_pack_readme.md"
    triage_csv_path = artifact_dir / "xlsx_keyword_echo_triage.csv"
    triage_jsonl_path = artifact_dir / "xlsx_keyword_echo_triage.jsonl"
    policy_path = artifact_dir / "xlsx_gold_policy_draft.md"

    write_csv(review_csv_path, REVIEW_PACK_COLUMNS, review_rows)
    write_jsonl(review_jsonl_path, review_rows)
    write_csv(triage_csv_path, TRIAGE_COLUMNS, triage_rows)
    write_jsonl(triage_jsonl_path, triage_rows)
    write_text(readme_path, build_readme(generated_at=generated_at, review_rows=review_rows, triage_rows=triage_rows))
    write_text(policy_path, build_policy_draft())

    gold_after = file_snapshots(gold_files)
    gold_files_modified = gold_before != gold_after
    manifest = build_manifest(
        generated_at=generated_at,
        source_artifact_dir=source_artifact_dir,
        artifact_dir=artifact_dir,
        review_csv_path=review_csv_path,
        review_jsonl_path=review_jsonl_path,
        readme_path=readme_path,
        triage_csv_path=triage_csv_path,
        triage_jsonl_path=triage_jsonl_path,
        policy_path=policy_path,
        review_rows=review_rows,
        triage_rows=triage_rows,
        source_report=source_report,
        source_artifact_files=source_artifact_files(source_artifact_dir),
        role_csv_rows=role_csv_rows,
        source_paths=source_paths,
        gold_before=gold_before,
        gold_after=gold_after,
        gold_files_modified=gold_files_modified,
    )
    write_json(manifest_path, manifest)
    return manifest


def build_review_row(
    *,
    probe_input: Mapping[str, Any],
    llm_output: Mapping[str, Any],
    role_row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    evidence_row: Mapping[str, Any],
    compiled_row: Mapping[str, Any],
) -> dict[str, Any]:
    query_id = clean(probe_input.get("query_id"))
    evidence = evidence_row.get("evidence_object") if isinstance(evidence_row.get("evidence_object"), Mapping) else {}
    prompt_payload = (
        probe_input.get("answer_prompt_payload")
        if isinstance(probe_input.get("answer_prompt_payload"), Mapping)
        else {}
    )
    prompt_evidence = prompt_payload.get("evidence") if isinstance(prompt_payload.get("evidence"), Mapping) else {}
    compiled_answer = (
        compiled_row.get("compiled_answer") if isinstance(compiled_row.get("compiled_answer"), Mapping) else {}
    )
    locator = first_mapping(
        evidence.get("citation_locator"),
        evidence.get("content_source_locator"),
        evidence.get("selected_searchunit_locator"),
        prompt_payload.get("citation_locator") if isinstance(prompt_payload, Mapping) else {},
        prompt_evidence.get("locator") if isinstance(prompt_evidence, Mapping) else {},
    )
    suggestion = suggested_review(row_id=query_id, probe_input=probe_input, llm_output=llm_output, role_row=role_row)
    row = {
        "query_id": query_id,
        "query": clean(probe_input.get("query") or source_row.get("query")),
        "track": "XLSX",
        "expected_answer_shape_existing": clean(
            source_row.get("expected_answer_shape") or probe_input.get("expected_answer_shape")
        ),
        "answer_allowed_diagnostic": parse_bool(
            probe_input.get("answer_allowed") or llm_output.get("answer_allowed")
        ),
        "fail_closed_reason": clean(probe_input.get("fail_closed_reason") or llm_output.get("fail_closed_reason")),
        "selected_searchunit_id": clean(
            evidence_row.get("selected_search_unit_id")
            or evidence.get("selected_search_unit_id")
            or locator.get("search_unit_id")
        ),
        "selected_searchunit_rank": clean(locator.get("rank")),
        "sheet": clean(evidence.get("sheet") or locator.get("sheet") or prompt_evidence.get("sheet")),
        "range": clean(evidence.get("range") or locator.get("range") or prompt_evidence.get("range")),
        "citation_locator": compact_json(locator),
        "evidence_summary": clean(evidence_row.get("content_summary") or evidence.get("content_summary")),
        "evidence_headers": compact_json(first_list(evidence.get("header_context"), prompt_evidence.get("header_context"))),
        "evidence_row_values": compact_json(first_list(evidence.get("row_values"), prompt_evidence.get("row_values"))[:12]),
        "evidence_cell_values": compact_json(first_list(evidence.get("cell_values"), prompt_evidence.get("cell_values"))[:12]),
        "evidence_content_source_fields": compact_json(
            first_list(evidence_row.get("content_source_fields"), evidence.get("content_source_fields"))
        ),
        "deterministic_compiled_answer": clean(
            nested(compiled_row, "compiled_answer", "answer")
            or nested(probe_input, "answer_prompt_payload", "compiled_deterministic_draft", "answer")
        ),
        "deterministic_compiled_status": clean(compiled_row.get("compiler_status")),
        "llm_answer": clean(llm_output.get("answer")),
        "llm_answer_type": clean(llm_output.get("answer_type")),
        "llm_abstain_reason": clean(llm_output.get("abstain_reason")),
        "llm_citations": compact_json(llm_output.get("citations") if isinstance(llm_output.get("citations"), list) else []),
        "llm_keyword_echo_only": parse_bool(llm_output.get("llm_keyword_echo_only")),
        "llm_unsupported_claims": compact_json(
            llm_output.get("unsupported_claims") if isinstance(llm_output.get("unsupported_claims"), list) else []
        ),
        "llm_gold_leakage_suspected": parse_bool(llm_output.get("llm_gold_leakage_suspected")),
        "expected_answer_text_existing": clean(
            source_row.get("expected_answer_text") or evidence_row.get("expected_answer_text")
        ),
        "expected_answer_text_role_llm_suggested": clean(role_row.get("expected_answer_text_role")),
        "must_contain_terms_existing": compact_json(
            first_list(source_row.get("must_contain_terms"), evidence_row.get("must_contain_terms"))
        ),
        "must_contain_terms_roles_llm_suggested": compact_json(
            role_row.get("must_contain_terms_roles")
            if isinstance(role_row.get("must_contain_terms_roles"), list)
            else []
        ),
        "human_review_required_llm_suggested": parse_bool(role_row.get("human_review_required")),
        "review_reason_llm_suggested": clean(role_row.get("rationale")),
        **{column: "" for column in USER_DECISION_COLUMNS},
        "suggested_review_priority": suggestion["priority"],
        "suggested_review_category": suggestion["category"],
        "suggested_possible_answer_shape": suggestion["shape"],
        "suggested_reason": suggestion["reason"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_xlsx_answer_eval_denominator": 0,
        "gold_promoted": False,
        "compiled_answer_shape": clean(compiled_answer.get("answer_shape")),
    }
    return row


def suggested_review(
    *,
    row_id: str,
    probe_input: Mapping[str, Any],
    llm_output: Mapping[str, Any],
    role_row: Mapping[str, Any],
) -> dict[str, str]:
    qid = row_id.lower()
    fail_reason = clean(probe_input.get("fail_closed_reason") or llm_output.get("fail_closed_reason")).upper()
    expected_shape = clean(probe_input.get("expected_answer_shape"))
    answer_type = clean(llm_output.get("answer_type"))
    expected_role = clean(role_row.get("expected_answer_text_role"))

    if parse_bool(llm_output.get("llm_keyword_echo_only")):
        return suggestion("P0", "KEYWORD_ECHO_TRIAGE", answer_type or expected_shape, "LLM answer was flagged keyword-only")
    if "hidden" in qid or "HIDDEN" in fail_reason:
        return suggestion("P0", "HIDDEN_ROW_OR_COLUMN_POLICY_REVIEW", expected_shape, "Hidden-content policy needs human confirmation")
    if "formula" in qid or "FORMULA" in fail_reason:
        return suggestion("P0", "FORMULA_VALUE_POLICY_REVIEW", expected_shape, "Formula/result-value scoring policy needs confirmation")
    if "date_number" in qid or "DATE" in fail_reason or "NUMBER" in fail_reason:
        return suggestion("P1", "DATE_NUMBER_FORMAT_POLICY_REVIEW", expected_shape, "Date/number formatting tolerance needs confirmation")
    if "aggregation" in qid or "AGGREGATION" in fail_reason:
        return suggestion("P1", "AGGREGATION_POLICY_REVIEW", expected_shape, "Aggregation question needs explicit gold policy")
    if "header_ambiguous" in qid or "HEADER" in fail_reason:
        return suggestion("P1", "HEADER_AMBIGUITY_REVIEW", expected_shape, "Header binding is ambiguous")
    if "POLICY_PENDING" in fail_reason or expected_role == "POLICY_OR_REVIEW_PLACEHOLDER":
        return suggestion("P0", "POLICY_PENDING_REVIEW", expected_shape, "Policy-pending row requires human review")
    if not parse_bool(probe_input.get("answer_allowed")):
        return suggestion("P1", "EVIDENCE_INSUFFICIENT", expected_shape, "Diagnostic evidence did not allow answer generation")
    if parse_bool(role_row.get("human_review_required")) or expected_role == "AMBIGUOUS_NEEDS_HUMAN_REVIEW":
        return suggestion("P1", "GOLD_FIELD_AMBIGUITY_REVIEW", expected_shape, "Mixed-use gold fields need human interpretation")
    if answer_type == "CELL_VALUE" or expected_shape == "TABLE_ROW_VALUE":
        return suggestion("P2", "CELL_VALUE_CANDIDATE", "CELL_VALUE", "Evidence contains a concrete cell/value candidate")
    if answer_type == "ROW_SUMMARY":
        return suggestion("P2", "ROW_SUMMARY_CANDIDATE", "ROW_SUMMARY", "Evidence supports a row-level summary candidate")
    if answer_type in {"RANGE_SUMMARY", "LOCATION_PLUS_CONTENT"} or expected_shape == "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT":
        return suggestion("P2", "RANGE_LOCATION_SUMMARY_CANDIDATE", "RANGE_SUMMARY", "Evidence supports a range/location summary candidate")
    return suggestion("P2", "QUERY_ANCHOR_MISMATCH", expected_shape or answer_type, "Review query/evidence anchor alignment")


def suggestion(priority: str, category: str, shape: str, reason: str) -> dict[str, str]:
    if category not in SUGGESTED_REVIEW_CATEGORIES:
        category = "GOLD_FIELD_AMBIGUITY_REVIEW"
    return {
        "priority": priority,
        "category": category,
        "shape": clean(shape) or "HUMAN_REVIEW_REQUIRED",
        "reason": reason,
    }


def build_triage_row(review_row: Mapping[str, Any]) -> dict[str, Any]:
    label, rationale, action = keyword_triage(review_row)
    return {
        "query_id": clean(review_row.get("query_id")),
        "query": clean(review_row.get("query")),
        "llm_answer": clean(review_row.get("llm_answer")),
        "deterministic_compiled_answer": clean(review_row.get("deterministic_compiled_answer")),
        "evidence_summary": clean(review_row.get("evidence_summary")),
        "expected_answer_text_existing": clean(review_row.get("expected_answer_text_existing")),
        "expected_answer_text_role_llm_suggested": clean(review_row.get("expected_answer_text_role_llm_suggested")),
        "must_contain_terms_existing": clean(review_row.get("must_contain_terms_existing")),
        "must_contain_terms_roles_llm_suggested": clean(review_row.get("must_contain_terms_roles_llm_suggested")),
        "triage_label_suggested": label,
        "triage_rationale": rationale,
        "recommended_next_action": action,
        "diagnostic_only": True,
        "promotion_evidence": False,
    }


def keyword_triage(row: Mapping[str, Any]) -> tuple[str, str, str]:
    expected_role = clean(row.get("expected_answer_text_role_llm_suggested"))
    shape = clean(row.get("expected_answer_shape_existing"))
    llm_answer = clean(row.get("llm_answer"))
    deterministic = clean(row.get("deterministic_compiled_answer"))
    evidence_summary = clean(row.get("evidence_summary"))
    must_roles_text = clean(row.get("must_contain_terms_roles_llm_suggested"))

    if expected_role in {"ENTITY_ANCHOR", "HEADER_OR_COLUMN_ANCHOR", "EVIDENCE_REQUIREMENT_SUMMARY"}:
        return (
            "EXPECTED_TEXT_IS_ANCHOR_NOT_ANSWER",
            "Expected/must fields look anchor-like while the LLM output is short.",
            "Human should decide target value versus anchor-only requirement.",
        )
    if "REQUIRED_HEADER_ANCHOR" in must_roles_text and llm_answer in must_roles_text:
        return (
            "TARGET_HEADER_NOT_BOUND",
            "LLM returned a header-like term without enough value context.",
            "Check whether target header should be paired with an entity/value.",
        )
    if shape == "TABLE_ROW_VALUE" and deterministic and llm_answer and llm_answer in deterministic:
        return (
            "CELL_VALUE_EXPECTED_BUT_ENTITY_RETURNED",
            "The row-value shape likely needs a concrete value, but the LLM returned a short entity/value fragment.",
            "Confirm the exact cell value and required anchors.",
        )
    if shape == "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT":
        return (
            "RANGE_SUMMARY_EXPECTED",
            "The diagnostic shape expects range context while the answer was keyword-like.",
            "Review whether a range summary or a single cell value should be gold.",
        )
    if shape == "TABLE_ROW_VALUE":
        return (
            "ROW_SUMMARY_EXPECTED",
            "The diagnostic shape expects row value context while the answer was keyword-like.",
            "Review row label, header, and target value together.",
        )
    if llm_answer and llm_answer in evidence_summary:
        return (
            "CHECKER_FALSE_POSITIVE",
            "The short answer appears in evidence, so the keyword checker may be conservative.",
            "Human should confirm whether this short value is acceptable.",
        )
    return (
        "HUMAN_GOLD_POLICY_REQUIRED",
        "Keyword-only signal needs human scoring policy before promotion.",
        "Do not promote until review columns are filled by a human.",
    )


def build_manifest(
    *,
    generated_at: str,
    source_artifact_dir: Path,
    artifact_dir: Path,
    review_csv_path: Path,
    review_jsonl_path: Path,
    readme_path: Path,
    triage_csv_path: Path,
    triage_jsonl_path: Path,
    policy_path: Path,
    review_rows: list[dict[str, Any]],
    triage_rows: list[dict[str, Any]],
    source_report: Mapping[str, Any],
    source_artifact_files: Mapping[str, Path],
    role_csv_rows: list[dict[str, str]],
    source_paths: Mapping[str, Path],
    gold_before: list[dict[str, Any]],
    gold_after: list[dict[str, Any]],
    gold_files_modified: bool,
) -> dict[str, Any]:
    expected_counts = Counter(clean(row.get("expected_answer_text_role_llm_suggested")) for row in review_rows)
    must_counts: Counter[str] = Counter()
    for row in review_rows:
        for item in parse_json_list(row.get("must_contain_terms_roles_llm_suggested")):
            if isinstance(item, Mapping):
                must_counts[clean(item.get("role"))] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not gold_files_modified and user_decision_columns_blank(review_rows) else "FAIL",
        "source_artifact_dir": repo_relative(source_artifact_dir),
        "artifact_dir": repo_relative(artifact_dir),
        "generated_at": generated_at,
        "total_xlsx_rows": 50,
        "review_pack_row_count": len(review_rows),
        "keyword_echo_triage_row_count": len(triage_rows),
        "human_review_required_count": sum(
            1 for row in review_rows if parse_bool(row.get("human_review_required_llm_suggested"))
        ),
        "expected_answer_text_role_counts": dict(expected_counts),
        "must_contain_terms_role_counts": dict(must_counts),
        "gold_intent_role_probe_csv_row_count": len(role_csv_rows),
        "answer_allowed_xlsx_rows": int_or_zero(source_report.get("answer_allowed_xlsx_rows")),
        "llm_answer_count": int_or_zero(source_report.get("llm_answer_count")),
        "llm_abstain_count": int_or_zero(source_report.get("llm_abstain_count")),
        "official_xlsx_answer_eval_denominator": 0,
        "promotion_evidence": False,
        "gold_files_modified": gold_files_modified,
        "gold_files_checked_before": gold_before,
        "gold_files_checked_after": gold_after,
        "existing_gold_csv_overwritten": False,
        "user_decision_columns_blank": user_decision_columns_blank(review_rows),
        "diagnostic_only": True,
        "diagnostic_llm_answers_are_gold": False,
        "gold_intent_suggestions_used_for_scoring": False,
        "expected_answer_text_promoted_to_scoring_target": False,
        "must_contain_terms_promoted_to_scoring_target": False,
        "outputs": {
            "xlsx_gold_human_review_pack_csv": artifact_entry(review_csv_path),
            "xlsx_gold_human_review_pack_jsonl": artifact_entry(review_jsonl_path),
            "xlsx_keyword_echo_triage_csv": artifact_entry(triage_csv_path),
            "xlsx_keyword_echo_triage_jsonl": artifact_entry(triage_jsonl_path),
            "xlsx_gold_policy_draft": artifact_entry(policy_path),
            "readme": artifact_entry(readme_path),
        },
        "source_artifact_files": {key: artifact_entry(path) for key, path in source_artifact_files.items()},
        "source_inputs": {key: artifact_entry(path) for key, path in source_paths.items()},
        "source_probe_report": {
            "llm_model": source_report.get("llm_model"),
            "external_live_llm_run": source_report.get("external_live_llm_run"),
            "promotion_evidence": source_report.get("promotion_evidence"),
            "official_xlsx_answer_eval_denominator": source_report.get("official_xlsx_answer_eval_denominator"),
        },
    }


def build_readme(*, generated_at: str, review_rows: list[dict[str, Any]], triage_rows: list[dict[str, Any]]) -> str:
    return f"""# XLSX Human Gold Review Pack

Generated at: {generated_at}

This artifact is diagnostic-only. It is intended to help a human create or
confirm the XLSX answer gold set. It does not modify gold files and does not
promote diagnostic answers.

Files:
- `xlsx_gold_human_review_pack.csv`: main 50-row review sheet.
- `xlsx_gold_human_review_pack.jsonl`: JSONL copy of the same review rows.
- `xlsx_keyword_echo_triage.csv`: {len(triage_rows)} diagnostic keyword-echo rows.
- `xlsx_keyword_echo_triage.jsonl`: JSONL copy of keyword triage rows.
- `xlsx_gold_policy_draft.md`: policy proposal for human confirmation.
- `xlsx_gold_human_review_pack_manifest.json`: provenance and guardrails.

Counts:
- Review pack rows: {len(review_rows)}
- Keyword echo triage rows: {len(triage_rows)}
- Human-review-required suggestions: {sum(1 for row in review_rows if parse_bool(row.get("human_review_required_llm_suggested")))}

Important guardrails:
- User decision columns are intentionally blank.
- Diagnostic LLM answers are not gold.
- Existing `expected_answer_text` and `must_contain_terms` are shown only as
  review context because they are mixed-use fields.
- Official XLSX answer denominator remains 0 until a human confirms decisions.
- `promotion_evidence=false`.
"""


def build_policy_draft() -> str:
    return """# XLSX Gold Policy Draft

This is a proposal for human review, not an official scoring policy.

Mandatory guardrails:
- official_xlsx_answer_eval_denominator remains 0 until user confirms review decisions.
- diagnostic LLM answers are not gold.
- expected_answer_text and must_contain_terms are mixed-use fields and cannot be used as automatic scoring targets.
- user confirmation is required before any official gold promotion.

Suggested handling by existing expected_answer_text role:
- EXACT_ANSWER_VALUE: consider scoring against the exact visible value only after the human confirms the value and citation locator.
- ENTITY_ANCHOR / HEADER_OR_COLUMN_ANCHOR: treat these as anchors, not final answers, unless the human explicitly marks them as target values.
- ROW_SUMMARY_LABEL: require the human to decide whether the gold answer is a row label, a row summary, or a specific cell value.
- RANGE_OR_LOCATION_LABEL: treat the field as evidence-location guidance unless the human explicitly enters a final answer value.
- EVIDENCE_REQUIREMENT_SUMMARY: use it to guide evidence review, not automatic answer scoring.
- POLICY_OR_REVIEW_PLACEHOLDER: exclude from official denominator until the user fills policy and inclusion columns.

Suggested policy topics:
- Hidden rows/columns: do not score hidden content unless the user explicitly approves a hidden-content policy.
- Formula values: decide whether to score formula text, calculated value, displayed value, or abstain.
- Date/number formatting: decide acceptable normalized formats before scoring.
- Aggregation questions: require an explicit aggregation method and evidence span before scoring.
- Header ambiguity: require a confirmed target header and, when needed, required entity anchors.
- Answer value vs evidence locator vs keyword anchor: score only the confirmed answer value or summary; use locators and keyword anchors only as citation/evidence requirements.
"""


def source_paths_from_manifest(manifest: Mapping[str, Any]) -> dict[str, Path]:
    source_inputs = manifest.get("source_inputs") if isinstance(manifest.get("source_inputs"), Mapping) else {}
    paths = {}
    for key in ("answer_generation_inputs", "evidence_objects", "compiled_answers"):
        entry = source_inputs.get(key) if isinstance(source_inputs.get(key), Mapping) else {}
        path = clean(entry.get("path"))
        if not path:
            raise SystemExit(f"source manifest missing {key}.path")
        paths[key] = resolve_repo_path(path)
    return paths


def source_artifact_files(source_artifact_dir: Path) -> dict[str, Path]:
    return {
        "manifest": source_artifact_dir / "manifest.json",
        "llm_answer_probe_report": source_artifact_dir / "llm_answer_probe_report.json",
        "llm_answer_probe_inputs": source_artifact_dir / "llm_answer_probe_inputs.jsonl",
        "llm_answer_probe_outputs": source_artifact_dir / "llm_answer_probe_outputs.jsonl",
        "gold_intent_role_probe_jsonl": source_artifact_dir / "gold_intent_role_probe.jsonl",
        "gold_intent_role_probe_csv": source_artifact_dir / "gold_intent_role_probe.csv",
    }


def user_decision_columns_blank(rows: Iterable[Mapping[str, Any]]) -> bool:
    return all(all(clean(row.get(column)) == "" for column in USER_DECISION_COLUMNS) for row in rows)


def file_snapshots(paths: Iterable[Path]) -> list[dict[str, Any]]:
    return [file_snapshot(path) for path in paths]


def file_snapshot(path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else REPO_ROOT / path
    exists = resolved.exists()
    return {
        "path": repo_relative(resolved),
        "exists": exists,
        "sha256": sha256_file(resolved) if exists else "",
        "bytes": resolved.stat().st_size if exists else 0,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"missing JSON file: {repo_relative(path)}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"JSON file is not an object: {repo_relative(path)}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"missing JSONL file: {repo_relative(path)}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"missing CSV file: {repo_relative(path)}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def keyed_by_query_id(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {clean(row.get("query_id")): row for row in rows if clean(row.get("query_id"))}


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def artifact_entry(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() else "",
    }


def compact_json(value: object) -> str:
    return json.dumps(value if value is not None else "", ensure_ascii=False, sort_keys=True)


def parse_json_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def first_mapping(*values: object) -> dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping) and value:
            return dict(value)
    return {}


def first_list(*values: object) -> list[Any]:
    for value in values:
        if isinstance(value, list):
            return value
    return []


def nested(value: Any, *keys: Any) -> Any:
    current = value
    for key in keys:
        if isinstance(current, Mapping):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return None
    return current


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y"}


def int_or_zero(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
