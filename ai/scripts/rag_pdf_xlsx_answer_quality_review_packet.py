"""Build a diagnostic-only PDF/XLSX answer-quality gold-review packet.

The packet pairs baseline/final local-LLM benchmark responses with the
SourceAtom evidence used by the diagnostic harness. It is for human policy
adjudication only: it does not create gold, qrels, labels, scored official eval
inputs, denominator rows, or promotion evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import rag_pdf_xlsx_llm_quality_benchmark as quality_benchmark


AI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_ROOT.parent
REPORT_DIR = AI_ROOT / "eval" / "reports" / "rag-ingestion"
QUALITY_DIR = REPORT_DIR / "quality"
DEFAULT_RUN_LABEL = "final_llm_rewrite_all_llm_15pf_v3"
DEFAULT_PREVIOUS_FINAL_RUN_LABEL = "final_llm_rewrite_all_llm_15pf_v3"
SCHEMA_VERSION = "rag_pdf_xlsx_answer_quality_review_packet_v1"
RUN_PREFIX = "pdf_xlsx_answer_quality_review_packet"
DEFAULT_MAX_EVIDENCE_CHARS = 2000

ANSWER_USER_DECISION_COLUMNS = [
    "user_answerable",
    "user_relevance",
    "user_expected_answer",
    "user_supporting_evidence",
    "user_pass_fail",
    "user_denominator_eligibility",
    "user_policy_note",
    "user_review_approved",
]

QUERY_USER_DECISION_COLUMNS = [
    "user_query_intent_preserved",
    "user_query_approval",
    "user_query_policy_note",
]

USER_DECISION_COLUMNS = [
    *ANSWER_USER_DECISION_COLUMNS,
    *QUERY_USER_DECISION_COLUMNS,
]

REVIEW_COLUMNS = [
    "case_id",
    "source_type",
    "query",
    "seed_query",
    "query_style",
    "query_drift_severity",
    "query_generation_mode",
    "query_fidelity_headline_included",
    "query_fidelity_exclusion_reason",
    "query_seed_overlap",
    "query_evidence_overlap",
    "baseline_answer",
    "baseline_result",
    "baseline_failure_types",
    "final_answer",
    "final_result",
    "final_failure_types",
    "previous_final_answer",
    "previous_final_result",
    "previous_final_failure_types",
    "previous_final_query",
    "answer_ready_answer",
    "answer_ready_result",
    "answer_ready_failure_types",
    "retrieved_evidence_text",
    "retrieved_evidence_truncated",
    "retrieved_evidence_sha256",
    "normalized_evidence_text",
    "normalized_evidence_sha256",
    "answer_ready_evidence_text",
    "answer_ready_evidence_sha256",
    "raw_answer_ready_score",
    "answer_ready_score",
    "answer_ready_score_delta",
    "bounded_expansion_applied",
    "weak_snippet_flag",
    "dot_heavy_flag",
    "locator_only_flag",
    "table_form_like_flag",
    "ocr_ish_flag",
    "locator_pdf_path",
    "locator_page",
    "locator_bbox",
    "locator_sheet",
    "locator_range",
    "locator_cell",
    "locator_json",
    "normalized_value",
    "failure_category",
    "pdf_residual_likely_causes",
    "codex_diagnostic_note",
    "source_atom_id",
    "search_view_id",
    "locator_fingerprint",
    "join_key_used",
    "weak_silver_candidate_id",
    "source_candidate_id",
    "delta_bucket",
    "prior_delta_bucket",
    "diagnostic_only",
    "not_gold",
    "not_official_denominator",
    "not_official_qrels",
    "official_metric_candidate",
    "promotion_evidence",
    *USER_DECISION_COLUMNS,
]

PDF_RESIDUAL_CAUSES = [
    "retrieval_miss",
    "weak_snippet",
    "ocr_ish_text",
    "locator_only_evidence",
    "table_form_formatting",
    "semantic_answer_mismatch",
    "evaluator_overlap_limitation",
]

PDF_RESIDUAL_REVIEW_COLUMNS = [
    "case_id",
    "query",
    "query_drift_severity",
    "query_generation_mode",
    "query_fidelity_headline_included",
    "answer_ready_result",
    "answer_ready_failure_types",
    "delta_bucket",
    "weak_evidence",
    "dot_or_ocr_artifact",
    "broad_context",
    "locator_only",
    "table_form",
    "query_drift",
    "evaluator_limitation",
    "true_answer_failure",
    "locator_page",
    "locator_bbox",
    "evidence_excerpt",
    "review_note",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary_path = Path(args.summary) if args.summary else default_summary_path(args.run_label)
    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir(args.run_label)
    report = run_packet(
        summary_path=summary_path,
        output_dir=output_dir,
        previous_summary_path=previous_summary_path(args.run_label, args.previous_run_label),
        max_evidence_chars=args.max_evidence_chars,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "artifact_dir": report["artifact_dir"],
                "review_packet_row_count": report["review_packet_row_count"],
                "pdf_residual_count": report["pdf_residuals"]["total_residuals"],
                "official_metric_input_rows": report["official_metric_input_rows"],
                "future_scored_adapter_status": report["future_scored_adapter"]["status"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-label", default=DEFAULT_RUN_LABEL)
    parser.add_argument("--previous-run-label", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--max-evidence-chars", type=int, default=DEFAULT_MAX_EVIDENCE_CHARS)
    return parser.parse_args(argv)


def previous_summary_path(run_label: str, previous_run_label: str = "") -> Path | None:
    if previous_run_label:
        return default_summary_path(previous_run_label)
    if run_label and run_label != DEFAULT_PREVIOUS_FINAL_RUN_LABEL:
        return default_summary_path(DEFAULT_PREVIOUS_FINAL_RUN_LABEL)
    return None


def run_packet(
    *,
    summary_path: Path,
    output_dir: Path,
    previous_summary_path: Path | None = None,
    max_evidence_chars: int = DEFAULT_MAX_EVIDENCE_CHARS,
) -> dict[str, Any]:
    summary_path = resolve_repo_path(summary_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = read_json(summary_path)
    responses_path = resolve_repo_path(clean(summary.get("responses_path")))
    response_rows = read_jsonl(responses_path)
    previous_response_rows: list[Mapping[str, Any]] = []
    previous_summary: Mapping[str, Any] = {}
    if previous_summary_path is not None:
        previous_summary_path = resolve_repo_path(previous_summary_path)
        if previous_summary_path.exists():
            previous_summary = read_json(previous_summary_path)
            previous_responses_path = resolve_repo_path(clean(previous_summary.get("responses_path")))
            if previous_responses_path.exists():
                previous_response_rows = read_jsonl(previous_responses_path)
    cases = load_cases_for_summary(summary)
    review_rows = build_review_rows(
        summary=summary,
        response_rows=response_rows,
        previous_response_rows=previous_response_rows,
        cases=cases,
        max_evidence_chars=max_evidence_chars,
    )
    validation = validate_review_rows(review_rows)
    future_adapter = build_future_scored_adapter_preview(review_rows)
    pdf_residuals = build_pdf_residual_summary(review_rows)
    pdf_delta_rows = build_pdf_delta_audit_rows(review_rows)
    query_fidelity_rows = build_query_fidelity_audit_rows(review_rows)
    pdf_residual_review_rows = build_pdf_residual_review_rows(review_rows)

    review_csv_path = output_dir / "review_packet.csv"
    review_jsonl_path = output_dir / "review_packet.jsonl"
    pdf_delta_audit_path = output_dir / "pdf_delta_audit.jsonl"
    query_fidelity_audit_path = output_dir / "query_fidelity_audit.jsonl"
    pdf_residual_review_csv_path = output_dir / "pdf_residual_review.csv"
    pdf_residual_review_md_path = output_dir / "pdf_residual_review.md"
    summary_md_path = output_dir / "summary.md"
    manifest_path = output_dir / "manifest.json"

    write_csv(review_csv_path, REVIEW_COLUMNS, review_rows)
    write_jsonl(review_jsonl_path, review_rows)
    write_jsonl(pdf_delta_audit_path, pdf_delta_rows)
    write_jsonl(query_fidelity_audit_path, query_fidelity_rows)
    write_csv(pdf_residual_review_csv_path, PDF_RESIDUAL_REVIEW_COLUMNS, pdf_residual_review_rows)

    report = build_report(
        summary=summary,
        previous_summary=previous_summary,
        summary_path=summary_path,
        responses_path=responses_path,
        previous_summary_path=previous_summary_path,
        artifact_dir=output_dir,
        review_rows=review_rows,
        validation=validation,
        future_adapter=future_adapter,
        pdf_residuals=pdf_residuals,
        pdf_delta_rows=pdf_delta_rows,
        query_fidelity_rows=query_fidelity_rows,
        pdf_residual_review_rows=pdf_residual_review_rows,
    )
    report["generated_artifacts"] = {
        "review_csv": artifact_entry(review_csv_path),
        "review_jsonl": artifact_entry(review_jsonl_path),
        "pdf_delta_audit_jsonl": artifact_entry(pdf_delta_audit_path),
        "query_fidelity_audit_jsonl": artifact_entry(query_fidelity_audit_path),
        "pdf_residual_review_csv": artifact_entry(pdf_residual_review_csv_path),
        "pdf_residual_review_md": {"path": repo_relative(pdf_residual_review_md_path), "exists": True},
        "summary_md": {"path": repo_relative(summary_md_path), "exists": True},
        "manifest_json": {"path": repo_relative(manifest_path), "exists": True},
    }
    pdf_residual_review_md_path.write_text(
        render_pdf_residual_review_markdown(report, pdf_residual_review_rows),
        encoding="utf-8",
    )
    report["generated_artifacts"]["pdf_residual_review_md"] = artifact_entry(pdf_residual_review_md_path)
    summary_md_path.write_text(render_markdown(report, review_rows), encoding="utf-8")
    report["generated_artifacts"]["summary_md"] = artifact_entry(summary_md_path)
    write_json(manifest_path, report)
    return report


def build_report(
    *,
    summary: Mapping[str, Any],
    previous_summary: Mapping[str, Any],
    summary_path: Path,
    responses_path: Path,
    previous_summary_path: Path | None,
    artifact_dir: Path,
    review_rows: list[dict[str, str]],
    validation: dict[str, Any],
    future_adapter: dict[str, Any],
    pdf_residuals: dict[str, Any],
    pdf_delta_rows: list[dict[str, Any]],
    query_fidelity_rows: list[dict[str, Any]],
    pdf_residual_review_rows: list[dict[str, str]],
) -> dict[str, Any]:
    case_counts = Counter(row["source_type"] for row in review_rows)
    baseline_pass_counts = Counter(
        row["source_type"] for row in review_rows if result_passed(row["baseline_result"])
    )
    final_pass_counts = Counter(row["source_type"] for row in review_rows if result_passed(row["final_result"]))
    answer_ready_pass_counts = Counter(
        row["source_type"] for row in review_rows if result_passed(row["answer_ready_result"])
    )
    status = "PASS" if validation["ok"] and future_adapter["official_metric_input_rows"] == 0 else "FAIL"
    policy = summary.get("policy") if isinstance(summary.get("policy"), Mapping) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": utc_timestamp(),
        "artifact_dir": repo_relative(artifact_dir),
        "source_run_label": clean(summary.get("run_label")),
        "source_schema_version": clean(summary.get("schema_version")),
        "source_summary": file_identity(summary_path),
        "source_responses": file_identity(responses_path),
        "previous_final_summary": file_identity(previous_summary_path) if previous_summary_path else {},
        "previous_final_run_label": clean(previous_summary.get("run_label")),
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "not_gold": True,
        "not_official_denominator": True,
        "not_official_qrels": True,
        "gold_or_label_mutation": False,
        "qrels_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "namespace_mutation": False,
        "review_packet_row_count": len(review_rows),
        "case_counts_by_source_type": counts_for_families(case_counts),
        "baseline_quality_pass_counts": counts_for_families(baseline_pass_counts),
        "final_quality_pass_counts": counts_for_families(final_pass_counts),
        "answer_ready_quality_pass_counts": counts_for_families(answer_ready_pass_counts),
        "aggregate_diagnostic_only": (
            f"{sum(final_pass_counts.values())}/{sum(case_counts.values())}"
            if sum(case_counts.values())
            else "0/0"
        ),
        "aggregate_diagnostic_only_scope": "legacy_raw_final_alias",
        "aggregate_raw_final_diagnostic_only": (
            f"{sum(final_pass_counts.values())}/{sum(case_counts.values())}"
            if sum(case_counts.values())
            else "0/0"
        ),
        "aggregate_answer_ready_diagnostic_only": (
            f"{sum(answer_ready_pass_counts.values())}/{sum(case_counts.values())}"
            if sum(case_counts.values())
            else "0/0"
        ),
        "source_answer_quality_summary": summary.get("answer_quality", {}),
        "source_failure_taxonomy": summary.get("failure_taxonomy", {}),
        "source_pdf_evidence_readiness_summary": summary.get("pdf_evidence_readiness_summary", {}),
        "source_query_rewrite_summary": summary.get("query_rewrite_summary", {}),
        "source_policy": dict(policy),
        "validation": validation,
        "future_scored_adapter": future_adapter,
        "pdf_residuals": pdf_residuals,
        "pdf_delta_audit_summary": summarize_pdf_delta_rows(pdf_delta_rows),
        "query_fidelity_summary": summarize_query_fidelity_rows(query_fidelity_rows),
        "headline_quality_counts": headline_quality_counts(review_rows),
        "pdf_residual_review_summary": summarize_pdf_residual_review_rows(pdf_residual_review_rows),
        "ocr_rationale": ocr_rationale(pdf_residual_review_rows),
        "prior_metrics_query_fidelity_status": "query_fidelity_unverified_until_this_packet",
        "non_gold_decisions": [
            "Rehydrated SourceAtom evidence from the benchmark manifest instead of raw logs.",
            "Paired baseline/final prompt modes into one diagnostic review row per case.",
            "When present, attached answer-ready PDF context as a separate diagnostic column rather than replacing user-owned gold decisions.",
            "Classified seed/query fidelity structurally and excluded major drift plus unapproved index-to-content rows from headline quality counts without deleting rows.",
            "Kept user-owned adjudication columns blank and official_metric_candidate=false.",
            "Classified PDF residual causes heuristically for review routing only, not pass/fail policy.",
        ],
        "user_owned_decisions_needed": [
            "answerable",
            "relevance",
            "expected_answer",
            "supporting_evidence",
            "pass_fail",
            "denominator_eligibility",
            "policy_note",
            "review_approval",
            "query_intent_preserved",
            "query_approval",
            "query_policy_note",
        ],
        "generated_artifacts": {},
    }


def load_cases_for_summary(summary: Mapping[str, Any]) -> dict[str, quality_benchmark.EvidenceCase]:
    cases_by_family = summary.get("cases_by_family") if isinstance(summary.get("cases_by_family"), Mapping) else {}
    cases_per_family = max([int_value(value) for value in cases_by_family.values()] or [15])
    manifest_path = resolve_repo_path(clean(summary.get("manifest")))
    silver_path = resolve_repo_path(clean(summary.get("silver_manifest")))
    silver_index = quality_benchmark.load_silver_seed_index(silver_path)
    cases = quality_benchmark.load_evidence_cases(
        manifest_path,
        cases_per_family=cases_per_family,
        silver_index=silver_index,
    )
    return {case.case_id: case for case in cases}


def build_review_rows(
    *,
    summary: Mapping[str, Any],
    response_rows: list[Mapping[str, Any]],
    previous_response_rows: list[Mapping[str, Any]],
    cases: Mapping[str, quality_benchmark.EvidenceCase],
    max_evidence_chars: int,
) -> list[dict[str, str]]:
    del summary
    by_case: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in response_rows:
        case_id = clean(row.get("case_id"))
        prompt_mode = clean(row.get("prompt_mode"))
        if prompt_mode in by_case[case_id]:
            raise ValueError(f"duplicate response row for {case_id}/{prompt_mode}")
        by_case[case_id][prompt_mode] = row
    previous_by_case: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in previous_response_rows:
        case_id = clean(row.get("case_id"))
        prompt_mode = clean(row.get("prompt_mode"))
        if prompt_mode in previous_by_case[case_id]:
            raise ValueError(f"duplicate previous response row for {case_id}/{prompt_mode}")
        previous_by_case[case_id][prompt_mode] = row

    review_rows: list[dict[str, str]] = []
    for case_id in sorted(by_case, key=case_sort_key):
        case = cases.get(case_id)
        if case is None:
            raise ValueError(f"case {case_id} is missing from benchmark case loader")
        baseline = by_case[case_id].get("baseline_legacy_context")
        final = by_case[case_id].get("final_locator_context")
        answer_ready = by_case[case_id].get("answer_ready_context") or final
        if baseline is None or final is None:
            raise ValueError(f"case {case_id} does not have both baseline and final rows")
        if clean(baseline.get("query")) != clean(final.get("query")):
            raise ValueError(f"case {case_id} baseline/final query mismatch")
        if answer_ready is not None and clean(answer_ready.get("query")) != clean(final.get("query")):
            raise ValueError(f"case {case_id} answer-ready/final query mismatch")

        baseline_answer = answer_from_response(baseline)
        final_answer = answer_from_response(final)
        answer_ready_answer = answer_from_response(answer_ready)
        previous_final = previous_by_case.get(case_id, {}).get("final_locator_context")
        previous_final_answer = answer_from_response(previous_final) if previous_final else ""
        final_failure_types = failure_types(final)
        final_pass = bool(as_mapping(final.get("score")).get("quality_pass"))
        answer_ready_failure_types = failure_types(answer_ready)
        previous_failure_types = failure_types(previous_final) if previous_final else []
        evidence_profile = as_mapping(answer_ready.get("evidence_readiness")) or as_mapping(final.get("evidence_readiness"))
        pdf_causes = classify_pdf_residual_causes(case=case, final_row=final, final_answer=final_answer)
        query_audit = query_fidelity_audit(
            case=case,
            query=clean(final.get("query")),
            seed_query=clean(final.get("seed_query")),
            evidence_text=case.evidence_text,
        )
        evidence_text, evidence_truncated = truncate_text(case.evidence_text, max_evidence_chars)
        normalized_evidence = clean(evidence_profile.get("normalized_snippet")) or (
            quality_benchmark.normalize_pdf_evidence_snippet(case.evidence_text) if case.family == "PDF" else case.evidence_text
        )
        answer_ready_evidence = clean(evidence_profile.get("answer_ready_snippet")) or normalized_evidence
        locator = dict(case.locator)
        row = {
            "case_id": case_id,
            "source_type": case.family,
            "query": clean(final.get("query")),
            "seed_query": clean(final.get("seed_query")),
            "query_style": clean(final.get("query_style")),
            "query_drift_severity": query_audit["query_drift_severity"],
            "query_generation_mode": query_audit["query_generation_mode"],
            "query_fidelity_headline_included": bool_cell(bool(query_audit["headline_included"])),
            "query_fidelity_exclusion_reason": query_audit["exclusion_reason"],
            "query_seed_overlap": metric_cell(query_audit["seed_query_overlap"]),
            "query_evidence_overlap": metric_cell(query_audit["query_evidence_overlap"]),
            "baseline_answer": baseline_answer,
            "baseline_result": result_label(baseline),
            "baseline_failure_types": "|".join(failure_types(baseline)),
            "final_answer": final_answer,
            "final_result": result_label(final),
            "final_failure_types": "|".join(final_failure_types),
            "answer_ready_answer": answer_ready_answer,
            "answer_ready_result": result_label(answer_ready),
            "answer_ready_failure_types": "|".join(answer_ready_failure_types),
            "retrieved_evidence_text": evidence_text,
            "retrieved_evidence_truncated": bool_cell(evidence_truncated),
            "retrieved_evidence_sha256": sha256_text(case.evidence_text),
            "normalized_evidence_text": normalized_evidence,
            "normalized_evidence_sha256": sha256_text(normalized_evidence),
            "answer_ready_evidence_text": answer_ready_evidence,
            "answer_ready_evidence_sha256": sha256_text(answer_ready_evidence),
            "raw_answer_ready_score": clean(evidence_profile.get("raw_answer_ready_score")),
            "answer_ready_score": clean(evidence_profile.get("answer_ready_score")),
            "answer_ready_score_delta": clean(evidence_profile.get("answer_ready_score_delta")),
            "bounded_expansion_applied": bool_cell(bool(evidence_profile.get("bounded_expansion_applied"))),
            "weak_snippet_flag": bool_cell(bool(evidence_profile.get("weak_snippet_flag"))),
            "dot_heavy_flag": bool_cell(float(evidence_profile.get("dot_leader_or_repeated_punctuation_ratio") or 0.0) >= 0.08),
            "locator_only_flag": bool_cell(bool(evidence_profile.get("locator_only_flag"))),
            "table_form_like_flag": bool_cell(bool(evidence_profile.get("table_form_like_flag"))),
            "ocr_ish_flag": bool_cell(bool(evidence_profile.get("ocr_ish_flag"))),
            "locator_pdf_path": clean(locator.get("source_pdf_path") or locator.get("source_path")),
            "locator_page": clean(locator.get("page")),
            "locator_bbox": compact_json(locator.get("bbox")),
            "locator_sheet": clean(locator.get("sheet")),
            "locator_range": clean(locator.get("range")),
            "locator_cell": clean(locator.get("cell")),
            "locator_json": compact_json(locator),
            "normalized_value": clean(locator.get("normalized_value")),
            "failure_category": failure_category(case.family, final_pass, final_failure_types, pdf_causes),
            "pdf_residual_likely_causes": "|".join(pdf_causes),
            "codex_diagnostic_note": codex_note(case=case, final_pass=final_pass, final_failure_types=final_failure_types, pdf_causes=pdf_causes),
            "source_atom_id": clean(final.get("source_atom_id")),
            "search_view_id": clean(final.get("search_view_id")),
            "locator_fingerprint": clean(final.get("locator_fingerprint")),
            "join_key_used": clean(final.get("join_key_used")),
            "weak_silver_candidate_id": clean(final.get("weak_silver_candidate_id")),
            "source_candidate_id": clean(final.get("source_candidate_id")),
            "delta_bucket": delta_bucket(final_result=final, answer_ready_result=answer_ready),
            "prior_delta_bucket": prior_delta_bucket(previous_result=previous_final, current_result=final),
            "diagnostic_only": "TRUE",
            "not_gold": "TRUE",
            "not_official_denominator": "TRUE",
            "not_official_qrels": "TRUE",
            "official_metric_candidate": "FALSE",
            "promotion_evidence": "FALSE",
        }
        row.update(
            {
                "previous_final_answer": previous_final_answer,
                "previous_final_result": result_label(previous_final) if previous_final else "MISSING_PREVIOUS_FINAL",
                "previous_final_failure_types": "|".join(previous_failure_types),
                "previous_final_query": clean(previous_final.get("query")) if previous_final else "",
            }
        )
        row.update({column: "" for column in USER_DECISION_COLUMNS})
        review_rows.append(row)
    return review_rows


def validate_review_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    seen_case_ids: set[str] = set()
    user_blank = True
    official_metric_input_rows = 0
    for index, row in enumerate(rows, start=1):
        missing = [column for column in REVIEW_COLUMNS if column not in row]
        if missing:
            errors.append(f"row {index} missing columns: {','.join(missing)}")
        case_id = clean(row.get("case_id"))
        if not case_id:
            errors.append(f"row {index} missing case_id")
        if case_id in seen_case_ids:
            errors.append(f"duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)
        for key, expected in (
            ("diagnostic_only", "TRUE"),
            ("not_gold", "TRUE"),
            ("not_official_denominator", "TRUE"),
            ("not_official_qrels", "TRUE"),
            ("official_metric_candidate", "FALSE"),
            ("promotion_evidence", "FALSE"),
        ):
            if clean(row.get(key)).upper() != expected:
                errors.append(f"{case_id or index} has {key}={row.get(key)!r}, expected {expected}")
        if any(clean(row.get(column)) for column in USER_DECISION_COLUMNS):
            user_blank = False
        if clean(row.get("official_metric_candidate")).upper() == "TRUE":
            official_metric_input_rows += 1

    return {
        "ok": not errors,
        "errors": errors,
        "review_packet_row_count": len(rows),
        "unique_case_id_count": len(seen_case_ids),
        "user_decision_columns_blank": user_blank,
        "official_metric_input_rows": official_metric_input_rows,
        "scored_eval_entry_allowed": False,
    }


def build_future_scored_adapter_preview(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    blank_answer_fields = all(not clean(row.get(column)) for row in rows for column in ANSWER_USER_DECISION_COLUMNS)
    blank_query_fields = all(not clean(row.get(column)) for row in rows for column in QUERY_USER_DECISION_COLUMNS)
    approval_candidate_rows = [
        row
        for row in rows
        if clean(row.get("user_review_approved")).lower() in {"true", "yes", "approved"}
        and clean(row.get("user_query_approval")).lower() in {"true", "yes", "approved"}
        and clean(row.get("user_query_intent_preserved")).lower() in {"true", "yes", "approved"}
    ]
    approved_rows = [
        row
        for row in approval_candidate_rows
        if clean(row.get("query_fidelity_headline_included")).upper() == "TRUE"
    ]
    blocked_reasons: list[str] = []
    if blank_answer_fields:
        blocked_reasons.append("user_decision_fields_blank")
    if blank_query_fields:
        blocked_reasons.append("user_query_decision_fields_blank")
    if not approval_candidate_rows:
        blocked_reasons.append("user_review_approved_not_true")
        blocked_reasons.append("user_query_approval_not_true")
    rows_for_fidelity_gate = approval_candidate_rows or rows
    if any(clean(row.get("query_fidelity_headline_included")).upper() != "TRUE" for row in rows_for_fidelity_gate):
        blocked_reasons.append("query_fidelity_exclusions_present")
    blocked_reasons.append("diagnostic_only_packet_not_scored_eval_input")
    return {
        "status": "DISABLED_PENDING_USER_APPROVAL",
        "adapter_enabled": False,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "approved_review_rows_seen": len(approved_rows),
        "approved_only_official_adjacent_rows_seen": len(approved_rows),
        "blocked_reasons": blocked_reasons,
        "would_require_before_enablement": [
            "user-filled answerability and relevance labels",
            "user-approved expected answer and supporting evidence semantics",
            "user pass/fail judgment and denominator eligibility decision",
            "user-approved query intent preservation for each row",
            "separate explicit scored-eval integration change",
        ],
    }


def query_fidelity_audit(
    *,
    case: quality_benchmark.EvidenceCase,
    query: str,
    seed_query: str,
    evidence_text: str,
) -> dict[str, Any]:
    seed_tokens = content_tokens(seed_query)
    query_tokens = content_tokens(query)
    evidence_tokens = content_tokens(evidence_text)
    seed_query_overlap = max(overlap_ratio(seed_tokens, query_tokens), char_ngram_overlap(seed_query, query))
    query_evidence_overlap = max(overlap_ratio(query_tokens, evidence_tokens), char_ngram_overlap(query, evidence_text))
    seed_evidence_overlap = max(overlap_ratio(seed_tokens, evidence_tokens), char_ngram_overlap(seed_query, evidence_text))
    seed_generic = generic_query(seed_tokens)
    index_like_seed = index_like_query(seed_query)
    low_seed_query_overlap = seed_query_overlap < 0.18
    query_source_grounded = query_evidence_overlap >= 0.25

    if clean(query) == clean(seed_query):
        severity = "none"
    elif seed_query_overlap >= 0.65:
        severity = "style_only"
    elif seed_query_overlap >= 0.35:
        severity = "minor_specificity_change"
    elif index_like_seed and query_source_grounded and seed_evidence_overlap < 0.25:
        severity = "index_to_content_query"
    elif seed_generic and query_source_grounded:
        severity = "seed_under_specified"
    elif low_seed_query_overlap and query_source_grounded and not seed_generic and seed_tokens:
        severity = "major_topic_drift"
    elif low_seed_query_overlap and not query_source_grounded:
        severity = "major_topic_drift"
    else:
        severity = "minor_specificity_change"

    if severity == "major_topic_drift":
        mode = "invalid_drift"
    elif severity in {"index_to_content_query", "seed_under_specified"}:
        mode = "source_grounded_synthetic_query"
    else:
        mode = "seed_preserving_rewrite"
    exclusion_reason = ""
    if severity == "major_topic_drift":
        exclusion_reason = "major_topic_drift"
    elif severity == "index_to_content_query":
        exclusion_reason = "index_to_content_query_unapproved"
    return {
        "case_id": case.case_id,
        "family": case.family,
        "seed_query": clean(seed_query),
        "query": clean(query),
        "query_drift_severity": severity,
        "query_generation_mode": mode,
        "headline_included": not exclusion_reason,
        "exclusion_reason": exclusion_reason,
        "seed_query_overlap": round(seed_query_overlap, 4),
        "query_evidence_overlap": round(query_evidence_overlap, 4),
        "seed_evidence_overlap": round(seed_evidence_overlap, 4),
        "diagnostic_only": True,
        "official_metric_candidate": False,
    }


def build_pdf_delta_audit_rows(rows: list[Mapping[str, str]]) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    for row in rows:
        if row["source_type"] != "PDF":
            continue
        audit_rows.append(
            {
                "case_id": row["case_id"],
                "query": row["query"],
                "seed_query": row["seed_query"],
                "query_drift_severity": row["query_drift_severity"],
                "query_generation_mode": row["query_generation_mode"],
                "previous_final_query": row.get("previous_final_query", ""),
                "previous_final_result": row.get("previous_final_result", ""),
                "previous_final_answer": row.get("previous_final_answer", ""),
                "previous_final_failure_types": split_pipe(row.get("previous_final_failure_types")),
                "current_raw_final_result": row["final_result"],
                "current_raw_final_answer": row["final_answer"],
                "current_raw_final_failure_types": split_pipe(row.get("final_failure_types")),
                "answer_ready_result": row["answer_ready_result"],
                "answer_ready_answer": row["answer_ready_answer"],
                "answer_ready_failure_types": split_pipe(row.get("answer_ready_failure_types")),
                "raw_evidence_text": row["retrieved_evidence_text"],
                "normalized_evidence_text": row["normalized_evidence_text"],
                "answer_ready_evidence_text": row["answer_ready_evidence_text"],
                "locator_pdf_path": row["locator_pdf_path"],
                "locator_page": row["locator_page"],
                "locator_bbox": row["locator_bbox"],
                "locator_json": row["locator_json"],
                "bounded_expansion_applied": row["bounded_expansion_applied"] == "TRUE",
                "raw_answer_ready_score": row["raw_answer_ready_score"],
                "answer_ready_score": row["answer_ready_score"],
                "answer_ready_score_delta": row["answer_ready_score_delta"],
                "delta_bucket": row["delta_bucket"],
                "prior_delta_bucket": row["prior_delta_bucket"],
                "diagnostic_only": True,
                "official_metric_candidate": False,
            }
        )
    return audit_rows


def build_query_fidelity_audit_rows(rows: list[Mapping[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": row["case_id"],
            "family": row["source_type"],
            "seed_query": row["seed_query"],
            "query": row["query"],
            "query_style": row["query_style"],
            "query_drift_severity": row["query_drift_severity"],
            "query_generation_mode": row["query_generation_mode"],
            "query_fidelity_headline_included": row["query_fidelity_headline_included"] == "TRUE",
            "query_fidelity_exclusion_reason": row["query_fidelity_exclusion_reason"],
            "query_seed_overlap": float_value(row["query_seed_overlap"]),
            "query_evidence_overlap": float_value(row["query_evidence_overlap"]),
            "diagnostic_only": True,
            "official_metric_candidate": False,
        }
        for row in rows
    ]


def build_pdf_residual_review_rows(rows: list[Mapping[str, str]]) -> list[dict[str, str]]:
    residual_rows: list[dict[str, str]] = []
    for row in rows:
        if row["source_type"] != "PDF":
            continue
        answer_ready_failed = not result_passed(row["answer_ready_result"])
        query_excluded = row["query_fidelity_headline_included"] != "TRUE"
        if not answer_ready_failed and not query_excluded:
            continue
        weak = row["weak_snippet_flag"] == "TRUE"
        dot_or_ocr = row["dot_heavy_flag"] == "TRUE" or row["ocr_ish_flag"] == "TRUE"
        locator_only = row["locator_only_flag"] == "TRUE" or "locator_only_answer" in row["answer_ready_failure_types"]
        table_form = row["table_form_like_flag"] == "TRUE"
        query_drift = query_excluded
        evaluator_limitation = "low_evidence_overlap" in row["answer_ready_failure_types"]
        true_answer_failure = answer_ready_failed and not any(
            [weak, dot_or_ocr, locator_only, table_form, query_drift, evaluator_limitation]
        )
        residual_rows.append(
            {
                "case_id": row["case_id"],
                "query": row["query"],
                "query_drift_severity": row["query_drift_severity"],
                "query_generation_mode": row["query_generation_mode"],
                "query_fidelity_headline_included": row["query_fidelity_headline_included"],
                "answer_ready_result": row["answer_ready_result"],
                "answer_ready_failure_types": row["answer_ready_failure_types"],
                "delta_bucket": row["delta_bucket"],
                "weak_evidence": bool_cell(weak),
                "dot_or_ocr_artifact": bool_cell(dot_or_ocr),
                "broad_context": bool_cell(row["bounded_expansion_applied"] == "TRUE" and evaluator_limitation),
                "locator_only": bool_cell(locator_only),
                "table_form": bool_cell(table_form),
                "query_drift": bool_cell(query_drift),
                "evaluator_limitation": bool_cell(evaluator_limitation),
                "true_answer_failure": bool_cell(true_answer_failure),
                "locator_page": row["locator_page"],
                "locator_bbox": row["locator_bbox"],
                "evidence_excerpt": shorten(row["answer_ready_evidence_text"], 220),
                "review_note": residual_review_note(row, answer_ready_failed=answer_ready_failed, query_excluded=query_excluded),
            }
        )
    return residual_rows


def build_pdf_residual_summary(rows: list[Mapping[str, str]]) -> dict[str, Any]:
    residuals = [
        row
        for row in rows
        if row["source_type"] == "PDF" and not result_passed(row["answer_ready_result"])
    ]
    failure_counts: Counter[str] = Counter()
    cause_counts: Counter[str] = Counter({cause: 0 for cause in PDF_RESIDUAL_CAUSES})
    case_summaries = []
    for row in residuals:
        for failure in split_pipe(row.get("answer_ready_failure_types")):
            failure_counts[failure] += 1
        causes = split_pipe(row.get("pdf_residual_likely_causes"))
        for cause in causes:
            cause_counts[cause] += 1
        case_summaries.append(
            {
                "case_id": row["case_id"],
                "query": row["query"],
                "final_failure_types": split_pipe(row.get("answer_ready_failure_types")),
                "raw_final_failure_types": split_pipe(row.get("final_failure_types")),
                "answer_ready_failure_types": split_pipe(row.get("answer_ready_failure_types")),
                "likely_causes": causes,
                "note": row["codex_diagnostic_note"],
            }
        )
    return {
        "total_residuals": len(residuals),
        "residual_scope": "answer_ready_context",
        "answer_ready_failure_type_counts": dict(sorted(failure_counts.items())),
        "final_failure_type_counts": dict(sorted(failure_counts.items())),
        "likely_cause_counts": {cause: cause_counts[cause] for cause in PDF_RESIDUAL_CAUSES},
        "cases": case_summaries,
        "taxonomy_scope": "diagnostic_routing_only_not_gold_policy",
    }


def summarize_pdf_delta_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "pdf_case_count": len(rows),
        "delta_bucket_counts": dict(sorted(Counter(clean(row.get("delta_bucket")) for row in rows).items())),
        "prior_delta_bucket_counts": dict(sorted(Counter(clean(row.get("prior_delta_bucket")) for row in rows).items())),
    }


def summarize_query_fidelity_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, dict[str, Any]] = {}
    for family in ("PDF", "XLSX"):
        family_rows = [row for row in rows if clean(row.get("family")) == family]
        by_family[family] = {
            "rows": len(family_rows),
            "headline_included": sum(bool(row.get("query_fidelity_headline_included")) for row in family_rows),
            "excluded": sum(not bool(row.get("query_fidelity_headline_included")) for row in family_rows),
            "severity_counts": dict(sorted(Counter(clean(row.get("query_drift_severity")) for row in family_rows).items())),
            "mode_counts": dict(sorted(Counter(clean(row.get("query_generation_mode")) for row in family_rows).items())),
        }
    return {
        "rows": len(rows),
        "headline_included": sum(bool(row.get("query_fidelity_headline_included")) for row in rows),
        "excluded": sum(not bool(row.get("query_fidelity_headline_included")) for row in rows),
        "severity_counts": dict(sorted(Counter(clean(row.get("query_drift_severity")) for row in rows).items())),
        "mode_counts": dict(sorted(Counter(clean(row.get("query_generation_mode")) for row in rows).items())),
        "by_family": by_family,
        "excluded_from_headline_policy": [
            "major_topic_drift",
            "index_to_content_query_without_user_query_approval",
        ],
        "prior_metrics_marked_query_fidelity_unverified": ["21/30", "24/30", "PDF 9/15", "XLSX 15/15"],
    }


def headline_quality_counts(rows: list[Mapping[str, str]]) -> dict[str, Any]:
    return {
        "all_rows_query_fidelity_unverified": quality_count_block(rows),
        "query_fidelity_subset": quality_count_block(
            [row for row in rows if clean(row.get("query_fidelity_headline_included")).upper() == "TRUE"]
        ),
    }


def quality_count_block(rows: list[Mapping[str, str]]) -> dict[str, Any]:
    by_family: dict[str, Any] = {}
    for family in ("PDF", "XLSX"):
        family_rows = [row for row in rows if row["source_type"] == family]
        by_family[family] = {
            "rows": len(family_rows),
            "raw_final_pass": sum(result_passed(row["final_result"]) for row in family_rows),
            "answer_ready_pass": sum(result_passed(row["answer_ready_result"]) for row in family_rows),
            "delta_answer_ready_minus_raw": sum(result_passed(row["answer_ready_result"]) for row in family_rows)
            - sum(result_passed(row["final_result"]) for row in family_rows),
        }
    return {
        "rows": len(rows),
        "raw_final_pass": sum(result_passed(row["final_result"]) for row in rows),
        "answer_ready_pass": sum(result_passed(row["answer_ready_result"]) for row in rows),
        "delta_answer_ready_minus_raw": sum(result_passed(row["answer_ready_result"]) for row in rows)
        - sum(result_passed(row["final_result"]) for row in rows),
        "by_family": by_family,
        "diagnostic_only": True,
    }


def summarize_pdf_residual_review_rows(rows: list[Mapping[str, str]]) -> dict[str, Any]:
    fields = [
        "weak_evidence",
        "dot_or_ocr_artifact",
        "broad_context",
        "locator_only",
        "table_form",
        "query_drift",
        "evaluator_limitation",
        "true_answer_failure",
    ]
    return {
        "rows": len(rows),
        "bucket_counts": {field: sum(row.get(field) == "TRUE" for row in rows) for field in fields},
    }


def ocr_rationale(rows: list[Mapping[str, str]]) -> dict[str, Any]:
    dot_or_ocr = sum(row.get("dot_or_ocr_artifact") == "TRUE" for row in rows)
    query_drift = sum(row.get("query_drift") == "TRUE" for row in rows)
    true_answer = sum(row.get("true_answer_failure") == "TRUE" for row in rows)
    return {
        "ocr_touched": False,
        "decision": "skipped",
        "reason": (
            "OCR-ish text remains measured, but this slice first excludes query drift and reviews answer-ready residuals; "
            "no OCR provider/source mutation is justified until residual review proves OCR is the top blocker after fidelity filtering."
        ),
        "dot_or_ocr_artifact_residual_rows": dot_or_ocr,
        "query_drift_residual_rows": query_drift,
        "true_answer_failure_rows": true_answer,
    }


def classify_pdf_residual_causes(
    *,
    case: quality_benchmark.EvidenceCase,
    final_row: Mapping[str, Any],
    final_answer: str,
) -> list[str]:
    if case.family != "PDF" or bool(as_mapping(final_row.get("score")).get("quality_pass")):
        return []
    failures = set(failure_types(final_row))
    evidence = case.evidence_text
    causes: list[str] = []
    if not clean(evidence):
        causes.append("retrieval_miss")
    if weak_snippet(evidence):
        causes.append("weak_snippet")
    if ocr_ish_text(evidence):
        causes.append("ocr_ish_text")
    if "locator_only_answer" in failures or "pdf_locator_missing" in failures or locator_like_evidence(evidence):
        causes.append("locator_only_evidence")
    if table_or_form_formatting(evidence):
        causes.append("table_form_formatting")
    if "low_evidence_overlap" in failures and final_answer:
        causes.append("semantic_answer_mismatch")
        causes.append("evaluator_overlap_limitation")
    return [cause for cause in PDF_RESIDUAL_CAUSES if cause in causes]


def weak_snippet(text: str) -> bool:
    tokens = quality_benchmark.meaningful_tokens_ordered(text)
    return len(tokens) <= 6 or len(clean(text)) <= 90 or leader_dot_count(text) >= 8


def ocr_ish_text(text: str) -> bool:
    value = clean(text)
    spaced_hangul_pairs = len(re.findall(r"[가-힣]\s+[가-힣]", value))
    compact_hangul_runs = re.findall(r"[가-힣]{18,}", value)
    return spaced_hangul_pairs >= 2 or bool(compact_hangul_runs)


def locator_like_evidence(text: str) -> bool:
    value = clean(text)
    return bool(re.search(r"(page|쪽|p\.)\s*\d+", value, flags=re.I)) or leader_dot_count(value) >= 6


def table_or_form_formatting(text: str) -> bool:
    value = clean(text)
    return leader_dot_count(value) >= 6 or value.count("|") >= 2 or bool(re.search(r"\b[A-Z]{1,3}\d+\b", value))


def leader_dot_count(text: str) -> int:
    return clean(text).count(".") + clean(text).count("·")


def codex_note(
    *,
    case: quality_benchmark.EvidenceCase,
    final_pass: bool,
    final_failure_types: list[str],
    pdf_causes: list[str],
) -> str:
    if final_pass:
        return "Diagnostic final answer passed the harness checks; this is still not gold or scored policy evidence."
    if case.family == "PDF":
        causes = ", ".join(pdf_causes) if pdf_causes else "unclassified PDF residual"
        return (
            "PDF residual is routed for human gold/policy review because final harness failures "
            f"({', '.join(final_failure_types)}) overlap with {causes}."
        )
    return (
        "Final diagnostic answer failed the harness checks; review fields remain blank and no official "
        "metric input is created."
    )


def failure_category(
    family: str,
    final_pass: bool,
    final_failure_types: list[str],
    pdf_causes: list[str],
) -> str:
    if final_pass:
        return "diagnostic_pass_not_gold"
    if family == "PDF" and pdf_causes:
        return "|".join(pdf_causes)
    return "|".join(final_failure_types) or "diagnostic_failure"


def delta_bucket(*, final_result: Mapping[str, Any], answer_ready_result: Mapping[str, Any]) -> str:
    final_pass = bool(as_mapping(final_result.get("score")).get("quality_pass"))
    ready_pass = bool(as_mapping(answer_ready_result.get("score")).get("quality_pass"))
    final_failures = set(failure_types(final_result))
    ready_failures = set(failure_types(answer_ready_result))
    if final_pass and ready_pass:
        return "raw_pass_to_ready_pass"
    if not final_pass and ready_pass:
        return "raw_fail_to_ready_pass"
    if final_pass and not ready_pass:
        return "raw_pass_to_ready_fail_regression"
    if final_failures == ready_failures:
        return "raw_fail_to_ready_fail_same_failure"
    return "raw_fail_to_ready_fail_changed_failure"


def prior_delta_bucket(*, previous_result: Mapping[str, Any] | None, current_result: Mapping[str, Any]) -> str:
    if previous_result is None:
        return "previous_final_missing"
    previous_query = clean(previous_result.get("query"))
    current_query = clean(current_result.get("query"))
    if previous_query and current_query and previous_query != current_query:
        return "cross_run_noncomparable_query_changed"
    previous_pass = bool(as_mapping(previous_result.get("score")).get("quality_pass"))
    current_pass = bool(as_mapping(current_result.get("score")).get("quality_pass"))
    if previous_pass == current_pass:
        return "cross_run_same_result"
    if previous_pass and not current_pass:
        return "cross_run_regressed"
    return "cross_run_improved"


def residual_review_note(row: Mapping[str, str], *, answer_ready_failed: bool, query_excluded: bool) -> str:
    reasons: list[str] = []
    if query_excluded:
        reasons.append(f"query fidelity excluded: {row['query_fidelity_exclusion_reason']}")
    if answer_ready_failed:
        reasons.append(f"answer-ready failed: {row['answer_ready_failure_types'] or 'unclassified'}")
    if row.get("weak_snippet_flag") == "TRUE":
        reasons.append("weak evidence")
    if row.get("dot_heavy_flag") == "TRUE" or row.get("ocr_ish_flag") == "TRUE":
        reasons.append("dot/OCR artifact")
    if not reasons:
        reasons.append("review-only diagnostic row")
    return "; ".join(reasons)


def render_pdf_residual_review_markdown(
    report: Mapping[str, Any],
    residual_rows: list[Mapping[str, str]],
) -> str:
    summary = as_mapping(report.get("pdf_residual_review_summary"))
    lines = [
        "# PDF Residual Review",
        "",
        "- Scope: diagnostic-only PDF residual review; not gold, not qrels, not official metric input.",
        f"- Rows: `{summary.get('rows', len(residual_rows))}`",
        f"- OCR decision: `{as_mapping(report.get('ocr_rationale')).get('decision', 'skipped')}`",
        "",
        "| Bucket | Count |",
        "|---|---:|",
    ]
    for bucket, count in as_mapping(summary.get("bucket_counts")).items():
        lines.append(f"| `{bucket}` | `{count}` |")
    lines.extend(["", "| Case | Drift | Result | Buckets | Note |", "|---|---|---|---|---|"])
    for row in residual_rows:
        buckets = [
            name
            for name in (
                "weak_evidence",
                "dot_or_ocr_artifact",
                "broad_context",
                "locator_only",
                "table_form",
                "query_drift",
                "evaluator_limitation",
                "true_answer_failure",
            )
            if row.get(name) == "TRUE"
        ]
        lines.append(
            f"| `{row['case_id']}` | `{row['query_drift_severity']}` | `{row['answer_ready_result']}` | "
            f"`{', '.join(buckets)}` | {escape_md(row['review_note'])} |"
        )
    return "\n".join(lines) + "\n"


def content_tokens(text: str) -> set[str]:
    generic = GENERIC_QUERY_TOKENS
    return {
        token
        for token in (normalize_content_token(token) for token in quality_benchmark.meaningful_tokens_ordered(text))
        if token and token not in generic and len(token) >= 2
    }


def normalize_content_token(token: str) -> str:
    value = clean(token).casefold()
    for suffix in (
        "입니다",
        "입니까",
        "습니까",
        "에서",
        "에게",
        "한테",
        "으로",
        "까지",
        "부터",
        "라고",
        "이며",
        "하고",
        "하면",
        "되는",
        "되어",
        "의",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "에",
        "로",
        "과",
        "와",
        "도",
        "만",
    ):
        if len(value) > len(suffix) + 1 and value.endswith(suffix):
            return value[: -len(suffix)]
    return value


GENERIC_QUERY_TOKENS = {
    "관련",
    "내용",
    "정보",
    "자료",
    "확인",
    "검색",
    "설명",
    "알려",
    "주세요",
    "무엇",
    "뭐야",
    "뭔가요",
    "어떤",
    "있나요",
    "찾아",
    "데이터",
    "수치",
    "항목",
    "값",
    "국립과천과학관",
    "과학기술자료실",
    "도서정보",
}


def overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def char_ngram_overlap(left: str, right: str, n: int = 3) -> float:
    left_compact = re.sub(r"[^0-9A-Za-z가-힣]+", "", clean(left)).casefold()
    right_compact = re.sub(r"[^0-9A-Za-z가-힣]+", "", clean(right)).casefold()
    if len(left_compact) < n or len(right_compact) < n:
        return 0.0
    left_grams = {left_compact[index : index + n] for index in range(0, len(left_compact) - n + 1)}
    right_grams = {right_compact[index : index + n] for index in range(0, len(right_compact) - n + 1)}
    return overlap_ratio(left_grams, right_grams)


def generic_query(tokens: set[str]) -> bool:
    return len(tokens) <= 1


def index_like_query(text: str) -> bool:
    value = clean(text)
    markers = ("검색", "자료", "정보", "항목", "번호", "데이터", "수치", "도서정보", "전자공시시스템", "경로")
    return any(marker in value for marker in markers)


def answer_from_response(row: Mapping[str, Any]) -> str:
    parsed, parse_ok = quality_benchmark.parse_json_response(clean(row.get("raw_response")))
    if parse_ok:
        return clean(parsed.get("answer"))
    return clean(row.get("raw_response"))


def result_label(row: Mapping[str, Any]) -> str:
    failures = failure_types(row)
    return "PASS" if not failures else "FAIL: " + "|".join(failures)


def failure_types(row: Mapping[str, Any]) -> list[str]:
    score = as_mapping(row.get("score"))
    failures = score.get("failure_types")
    if isinstance(failures, list):
        return [clean(failure) for failure in failures if clean(failure)]
    return []


def result_passed(value: str) -> bool:
    return clean(value).upper() == "PASS"


def render_markdown(report: Mapping[str, Any], review_rows: list[Mapping[str, str]]) -> str:
    pdf_residuals = as_mapping(report.get("pdf_residuals"))
    lines = [
        "# PDF/XLSX Answer-Quality Gold-Review Packet",
        "",
        f"- Status: `{report['status']}`",
        f"- Source run: `{report['source_run_label']}`",
        "- Scope: diagnostic-only; not gold, not qrels, not official denominator input, not promotion evidence.",
        f"- Review CSV: `{report['generated_artifacts']['review_csv']['path']}`",
        f"- Review JSONL: `{report['generated_artifacts']['review_jsonl']['path']}`",
        f"- PDF delta audit: `{report['generated_artifacts']['pdf_delta_audit_jsonl']['path']}`",
        f"- Query fidelity audit: `{report['generated_artifacts']['query_fidelity_audit_jsonl']['path']}`",
        f"- PDF residual review: `{report['generated_artifacts']['pdf_residual_review_md']['path']}`",
        f"- Rows: `{report['review_packet_row_count']}` (`PDF={report['case_counts_by_source_type']['PDF']}`, `XLSX={report['case_counts_by_source_type']['XLSX']}`)",
        "",
        "## Diagnostic Summary",
        "",
        "| Family | Baseline pass | Raw final pass | Answer-ready pass |",
        "|---|---:|---:|---:|",
    ]
    for family in ("PDF", "XLSX"):
        total = report["case_counts_by_source_type"][family]
        baseline = report["baseline_quality_pass_counts"][family]
        final = report["final_quality_pass_counts"][family]
        answer_ready = report["answer_ready_quality_pass_counts"][family]
        lines.append(f"| {family} | `{baseline}/{total}` | `{final}/{total}` | `{answer_ready}/{total}` |")
    readiness = as_mapping(report.get("source_pdf_evidence_readiness_summary"))
    lines.extend(
        [
            "",
            (
                f"Raw final aggregate `{report['aggregate_raw_final_diagnostic_only']}` -> "
                f"answer-ready aggregate `{report['aggregate_answer_ready_diagnostic_only']}` "
            "is diagnostic-only and must not be used as a scored official metric."
            ),
            "",
            "## Query Fidelity",
            "",
            "- Prior diagnostic aggregates (`21/30`, `24/30`, `PDF 9/15`, `XLSX 15/15`) are marked query-fidelity-unverified until this packet's classification is reviewed.",
            f"- Headline-included rows: `{report['query_fidelity_summary']['headline_included']}/{report['query_fidelity_summary']['rows']}`",
            f"- Excluded rows: `{report['query_fidelity_summary']['excluded']}` (major drift or unapproved index-to-content query).",
            "",
            "| Family | Included | Excluded | Raw final pass in included subset | Answer-ready pass in included subset |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    fidelity_by_family = as_mapping(report["query_fidelity_summary"].get("by_family"))
    headline_by_family = as_mapping(report["headline_quality_counts"]["query_fidelity_subset"].get("by_family"))
    for family in ("PDF", "XLSX"):
        family_fidelity = as_mapping(fidelity_by_family.get(family))
        family_headline = as_mapping(headline_by_family.get(family))
        lines.append(
            f"| {family} | `{family_fidelity.get('headline_included', 0)}` | `{family_fidelity.get('excluded', 0)}` | "
            f"`{family_headline.get('raw_final_pass', 0)}/{family_headline.get('rows', 0)}` | "
            f"`{family_headline.get('answer_ready_pass', 0)}/{family_headline.get('rows', 0)}` |"
        )
    lines.extend(
        [
            "",
            "## PDF Evidence Readiness",
            "",
            f"- PDF cases audited: `{readiness.get('pdf_case_count', 0)}`",
            f"- Bounded expansion applied: `{readiness.get('bounded_expansion_applied_count', 0)}`",
            f"- Average answer-ready score delta: `{readiness.get('avg_answer_ready_score_delta', 0.0)}`",
            f"- Retrieval miss assessment: `{readiness.get('retrieval_miss_assessment', 'not_recomputed_preselected_sourceatom_evidence_only')}`",
            "",
            "## PDF Residual Taxonomy",
            "",
            f"- Residual PDF cases: `{pdf_residuals['total_residuals']}` (`{pdf_residuals.get('residual_scope', 'answer_ready_context')}`)",
            "- Taxonomy is Codex diagnostic routing only; user-owned answer/evidence/policy fields stay blank.",
            "",
            "| Likely cause | Count |",
            "|---|---:|",
        ]
    )
    for cause, count in pdf_residuals["likely_cause_counts"].items():
        lines.append(f"| `{cause}` | `{count}` |")
    lines.extend(["", "| Case | Failures | Likely causes | Note |", "|---|---|---|---|"])
    for case in pdf_residuals["cases"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{case['case_id']}`",
                    "`" + ", ".join(case["final_failure_types"]) + "`",
                    "`" + ", ".join(case["likely_causes"]) + "`",
                    escape_md(case["note"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- User decision columns are blank in every generated row.",
            "- `official_metric_candidate` is `FALSE` in every row.",
            "- Future scored adapter preview is disabled and emits `official_metric_input_rows=0`.",
            "- No gold labels, qrels, expected answers, supporting evidence, denominator policy, namespace, DB, or promotion surface is mutated.",
            "",
            "## User-Owned Decisions Needed",
            "",
        ]
    )
    for decision in report["user_owned_decisions_needed"]:
        lines.append(f"- `{decision}`")
    lines.extend(
        [
            "",
            "## Case Preview",
            "",
            "| Case | Type | Raw final | Answer-ready | Drift | Headline | Query |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in review_rows[:10]:
        lines.append(
            f"| `{row['case_id']}` | `{row['source_type']}` | `{row['final_result']}` | "
            f"`{row['answer_ready_result']}` | `{row['query_drift_severity']}` | "
            f"`{row['query_fidelity_headline_included']}` | {escape_md(row['query'])} |"
        )
    return "\n".join(lines) + "\n"


def default_summary_path(run_label: str) -> Path:
    return QUALITY_DIR / f"pdf_xlsx_llm_quality_{run_label}_summary.json"


def default_output_dir(run_label: str) -> Path:
    return QUALITY_DIR / f"{RUN_PREFIX}_{run_label}"


def case_sort_key(case_id: str) -> tuple[str, int, str]:
    family, _, ordinal = case_id.partition("-")
    return (family, int_value(ordinal), case_id)


def truncate_text(value: str, max_chars: int) -> tuple[str, bool]:
    text = clean(value)
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip(), True


def shorten(value: object, max_chars: int) -> str:
    text = clean(value)
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def counts_for_families(counter: Mapping[str, int]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in ("PDF", "XLSX")}


def split_pipe(value: object) -> list[str]:
    return [part for part in clean(value).split("|") if part]


def bool_cell(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def metric_cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value else "0"
    return clean(value)


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError(f"{path} contains a non-object JSONL row")
                rows.append(payload)
    return rows


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
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
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_entry(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() else "",
    }


def file_identity(path: Path) -> dict[str, Any]:
    return artifact_entry(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(clean(value).encode("utf-8")).hexdigest()


def compact_json(value: object) -> str:
    if value in (None, "", [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def int_value(value: object) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def float_value(value: object) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def escape_md(value: object) -> str:
    return clean(value).replace("|", "\\|").replace("\n", " ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean(value: object) -> str:
    return str(value or "").strip()


if __name__ == "__main__":  # pragma: no cover - exercised by CLI smoke.
    raise SystemExit(main())
