"""Prepare a compact TEXT/Namu answer/citation review diagnostic report.

This script is report-only. It reads existing review/policy artifacts, records
which TEXT/Namu rows could move to answer/citation review, and fails closed when
actual generated answer outputs are missing. It does not run retrieval, answer
generation, citation scoring, indexing, or denominator mutation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections.abc import Iterable
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_TEXT_REVIEW_PACK = (
    REVIEW_DIR
    / "text_namu_v2_gold_review"
    / "text_namu_v2_gold_review_pack - text_namu_v2_gold_review_pack.csv"
)
DEFAULT_NORMALIZATION_REPORT = REPORT_DIR / "rag_reviewed_gold_policy_normalization_report.json"
DEFAULT_APPLIED_DECISIONS = REVIEW_DIR / "rag_gold_policy_applied_decisions_v1.json"
DEFAULT_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
DEFAULT_ROUTE_APPLIED = REVIEW_DIR / "route_gold_label_review_applied_v1.json"
DEFAULT_FALLBACK_APPLIED = REVIEW_DIR / "fallback_outcome_label_review_applied_v1.json"
DEFAULT_REPORT_JSON = REPORT_DIR / "rag_text_namu_answer_citation_review_prep_report.json"
DEFAULT_REPORT_MD = REPORT_DIR / "rag_text_namu_answer_citation_review_prep_report.md"

DEFAULT_GENERATED_ANSWER_CANDIDATE_PATHS = [
    REPORT_DIR / "rag_text_namu_generated_answer_review_input.jsonl",
    REPORT_DIR / "rag_text_namu_v4_answer_eval_report.json",
    REPORT_DIR / "rag_text_namu_v4_answer_eval.jsonl",
    REPORT_DIR / "rag_text_namu_v4_citation_support_report.json",
    REPORT_DIR / "rag_text_namu_v4_citation_support.jsonl",
    AI_WORKER_ROOT / "eval" / "eval_queries" / "text_namu_v4_answers_v0.jsonl",
]

ACTUAL_GENERATED_ANSWER_FIELDS = {
    "actual_generated_answer_output",
    "actual_llm_answer_generation_run",
    "live_llm_run",
    "local_llm_run",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_arg = args.generated_answer_artifact or [str(path) for path in DEFAULT_GENERATED_ANSWER_CANDIDATE_PATHS]
    generated_paths = [Path(path) for path in generated_arg]
    report = build_report(
        text_review_pack=Path(args.text_review_pack),
        normalization_report=Path(args.normalization_report),
        applied_decisions=Path(args.applied_decisions),
        denominator_registry=Path(args.denominator_registry),
        route_applied=Path(args.route_applied),
        fallback_applied=Path(args.fallback_applied),
        generated_answer_artifacts=generated_paths,
    )
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    write_json(json_path, report)
    write_text(md_path, render_markdown(report))
    print_json(
        {
            "status": report["status"],
            "report": repo_relative(json_path),
            "markdown": repo_relative(md_path),
            "candidate_review_rows": report["answer_citation_review_preparation"][
                "candidate_review_rows_count"
            ],
            "generated_answer_available": report["generated_answer_availability"][
                "actual_generated_answer_output_available"
            ],
            "official_metric_input_rows": report["official_metric_input_rows"],
        }
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-review-pack", default=str(DEFAULT_TEXT_REVIEW_PACK))
    parser.add_argument("--normalization-report", default=str(DEFAULT_NORMALIZATION_REPORT))
    parser.add_argument("--applied-decisions", default=str(DEFAULT_APPLIED_DECISIONS))
    parser.add_argument("--denominator-registry", default=str(DEFAULT_DENOMINATOR_REGISTRY))
    parser.add_argument("--route-applied", default=str(DEFAULT_ROUTE_APPLIED))
    parser.add_argument("--fallback-applied", default=str(DEFAULT_FALLBACK_APPLIED))
    parser.add_argument(
        "--generated-answer-artifact",
        action="append",
        default=None,
    )
    parser.add_argument("--output-json", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_REPORT_MD))
    return parser.parse_args(argv)


def build_report(
    *,
    text_review_pack: Path,
    normalization_report: Path,
    applied_decisions: Path,
    denominator_registry: Path,
    route_applied: Path,
    fallback_applied: Path,
    generated_answer_artifacts: Iterable[Path],
) -> dict[str, Any]:
    registry_sha_before = sha256_if_exists(denominator_registry)
    review_rows, review_columns = read_csv_if_exists(text_review_pack)
    normalization = read_json_if_exists(normalization_report)
    applied = read_json_if_exists(applied_decisions)
    registry = read_json_if_exists(denominator_registry)
    text = ((normalization.get("tracks") or {}).get("text_namu_v2") or {})
    applied_text = (((applied.get("applied_decisions") or {}).get("text_namu_v2_unresolved_carry_forward")) or {})
    generated = inspect_generated_answer_artifacts(generated_answer_artifacts)
    route_state = route_fallback_state(route_applied=route_applied, fallback_applied=fallback_applied)
    registry_text_answer_keys = text_answer_citation_registry_keys(registry)

    groups = classify_text_rows(text=text, applied_text=applied_text)
    candidate_ids = clean_list(text.get("proposed_official_candidate_query_ids"))
    generated_answer_ids = set(generated["actual_generated_answer_query_ids"])
    generated_answer_available = bool(generated_answer_ids)
    generated_answer_missing_ids = [query_id for query_id in candidate_ids if query_id not in generated_answer_ids]
    text_answer_or_citation_opened = bool(registry_text_answer_keys)
    official_metric_input_rows = int(generated["official_metric_input_rows"]) + int(
        route_state["official_metric_input_rows"]
    )

    errors = source_artifact_errors(
        text_review_pack=text_review_pack,
        review_rows=review_rows,
        normalization_report=normalization_report,
        normalization=normalization,
        text=text,
        candidate_ids=candidate_ids,
        applied_decisions=applied_decisions,
        applied=applied,
        applied_text=applied_text,
        denominator_registry=denominator_registry,
        registry=registry,
    )
    errors.extend(validation_errors(
        groups=groups,
        registry_text_answer_keys=registry_text_answer_keys,
        official_metric_input_rows=official_metric_input_rows,
        route_state=route_state,
        generated=generated,
        candidate_ids=candidate_ids,
    ))
    registry_sha_after = sha256_if_exists(denominator_registry)
    status = "FAIL" if errors else (
        "BLOCKED_GENERATED_ANSWER_OUTPUT_MISSING"
        if generated_answer_missing_ids
        else "READY_DIAGNOSTIC_ONLY"
    )

    return {
        "schema_version": "rag_text_namu_answer_citation_review_prep_report_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "text_namu_answer_citation_review_preparation_diagnostic",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_artifacts": {
            "text_review_pack": artifact_info(text_review_pack, expected_rows=100),
            "reviewed_gold_policy_normalization_report": artifact_info(normalization_report),
            "gold_policy_applied_decisions": artifact_info(applied_decisions),
            "official_denominator_registry": artifact_info(denominator_registry),
            "route_gold_label_review_applied": artifact_info(route_applied),
            "fallback_outcome_label_review_applied": artifact_info(fallback_applied),
        },
        "text_review_pack": {
            "row_count": len(review_rows),
            "columns": review_columns,
            "candidate_default_policy_counts": count_field(review_rows, "candidate_default_policy"),
            "user_final_gold_policy_counts": count_field(review_rows, "user_final_gold_policy"),
            "user_answerability_label_counts": count_field(review_rows, "user_answerability_label"),
            "user_relevance_label_counts": count_field(review_rows, "user_relevance_label"),
        },
        "normalization_source": {
            "row_count": int(text.get("row_count") or 0),
            "normalized_bucket_counts": dict(text.get("normalized_bucket_counts") or {}),
            "proposed_official_candidate_count": len(candidate_ids),
            "unresolved_user_review_count": int(text.get("unresolved_user_review_count") or 0),
            "policy_excluded_count": len(clean_list(text.get("policy_excluded_query_ids"))),
            "source_verification_required_count": len(
                clean_list(text.get("source_verification_required_query_ids"))
            ),
            "diagnostic_only_count": len(clean_list(text.get("diagnostic_only_query_ids"))),
        },
        "answer_citation_review_preparation": {
            "candidate_review_rows_count": len(candidate_ids),
            "candidate_review_query_ids": candidate_ids,
            "candidate_review_status": (
                "BLOCKED_PENDING_ACTUAL_GENERATED_ANSWER_OUTPUT"
                if generated_answer_missing_ids
                else "READY_FOR_DIAGNOSTIC_REVIEW_PREP"
            ),
            "generated_answer_missing_count": len(generated_answer_missing_ids),
            "generated_answer_missing_query_ids": generated_answer_missing_ids,
            "generated_answer_missing_rows_diagnostic_only": True,
            "generated_answer_missing_counted_as_failure": False,
            "actual_generated_answer_output_required_next": bool(generated_answer_missing_ids),
            "next_required_artifact": (
                "TEXT/Namu generated answer output JSONL with query_id, generated answer text, cited chunk ids, "
                "generation provenance, and official_metric_input=false until policy opens the denominator."
            ),
        },
        "row_groups": groups,
        "blocked_row_accounting": {
            "unresolved_text_namu_rows_not_promoted": True,
            "unresolved_carry_forward_count": groups["applied_unresolved_carry_forward"]["count"],
            "policy_blocked_rows_count": groups["policy_blocked_not_failure"]["count"],
            "policy_blocked_rows_counted_as_failures": False,
            "source_binding_review_required_count": groups["source_binding_review_required"]["count"],
            "diagnostic_only_default_count": groups["diagnostic_only_default"]["count"],
        },
        "generated_answer_availability": generated,
        "official_denominator_policy": {
            "registry_text_answer_or_citation_keys": registry_text_answer_keys,
            "text_answer_citation_official_denominator_opened": bool(registry_text_answer_keys),
            "official_denominator_registry_changed": registry_sha_before != registry_sha_after,
            "official_denominator_registry_sha256_before": registry_sha_before,
            "official_denominator_registry_sha256_after": registry_sha_after,
        },
        "citation_support_metric_runner": {
            "official_metric_input_rows": official_metric_input_rows,
            "status": "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY",
            "diagnostic_candidate_rows": len(candidate_ids),
            "official_metric_computed": False,
            "diagnostic_only_rows_counted_as_official_failures": False,
        },
        "route_fallback_applied_labels": route_state,
        "official_metric_input_rows": official_metric_input_rows,
        "guardrails": {
            "official_denominator_registry_changed": registry_sha_before != registry_sha_after,
            "official_denominator_opened_or_frozen": text_answer_or_citation_opened,
            "text_answer_denominator_opened": text_answer_or_citation_opened,
            "text_citation_support_denominator_opened": text_answer_or_citation_opened,
            "official_metric_input_rows": official_metric_input_rows,
            "production_namespace_mutated": False,
            "production_vector_index_mutated": False,
            "production_vector_written": False,
            "candidate_artifact_mutated": False,
            "immutable_baseline_mutated": False,
            "diagnostic_only_row_promoted": False,
            "policy_blocked_rows_counted_as_failures": False,
            "route_fallback_applied_labels_diagnostic_only": route_state["diagnostic_only"],
        },
        "validation": {
            "errors": errors,
            "ok": not errors,
            "exclusive_classification_total": groups["exclusive_status_counts"]["total"],
            "text_review_pack_row_count_matches_normalization": len(review_rows)
            == int(text.get("row_count") or len(review_rows)),
        },
        "remaining_blockers": remaining_blockers(generated_answer_missing_ids, registry_text_answer_keys),
    }


def classify_text_rows(*, text: Mapping[str, Any], applied_text: Mapping[str, Any]) -> dict[str, Any]:
    rows = text.get("rows") if isinstance(text.get("rows"), list) else []
    all_ids = [clean(row.get("query_id")) for row in rows if isinstance(row, Mapping) and clean(row.get("query_id"))]
    if not all_ids:
        all_ids = sorted(
            set().union(
                clean_list(text.get("proposed_official_candidate_query_ids")),
                clean_list(text.get("policy_excluded_query_ids")),
                clean_list(text.get("source_verification_required_query_ids")),
                clean_list(text.get("diagnostic_only_query_ids")),
                clean_list(applied_text.get("query_ids")),
            )
        )

    markers = text.get("review_marker_buckets") if isinstance(text.get("review_marker_buckets"), Mapping) else {}
    proposed = clean_list(text.get("proposed_official_candidate_query_ids"))
    policy_blocked = clean_list(text.get("policy_excluded_query_ids"))
    source_binding = clean_list(text.get("source_verification_required_query_ids"))
    diagnostic_only = clean_list(text.get("diagnostic_only_query_ids"))
    expected_revision = clean_list(text.get("expected_answer_or_evidence_revision_query_ids"))
    needs_second = clean_list(markers.get("needs_second_review"))
    evidence_too_broad = clean_list(markers.get("evidence_too_broad"))
    ambiguous = clean_list(markers.get("ambiguous_query"))
    carry_forward = clean_list(applied_text.get("query_ids"))

    remaining = set(all_ids)
    exclusive: dict[str, list[str]] = {}

    def take(name: str, ids: Iterable[str]) -> None:
        selected = sorted(set(ids).intersection(remaining))
        exclusive[name] = selected
        remaining.difference_update(selected)

    take("candidate_review_prep_generated_answer_missing", proposed)
    take("policy_blocked_not_failure", policy_blocked)
    take("source_binding_review_required", source_binding)
    take("diagnostic_only_default", diagnostic_only)
    take("expected_answer_or_evidence_revision", expected_revision)
    take("needs_second_review", needs_second)
    take("evidence_too_broad", evidence_too_broad)
    take("ambiguous_query_unresolved", ambiguous)
    take("unresolved_carry_forward_other", carry_forward)
    if remaining:
        exclusive["unclassified_diagnostic_only"] = sorted(remaining)

    groups = {
        "candidate_review_prep_generated_answer_missing": row_group(
            exclusive.get("candidate_review_prep_generated_answer_missing", []),
            status="diagnostic_only_until_actual_generated_answer_exists",
            promoted=False,
        ),
        "applied_unresolved_carry_forward": row_group(
            carry_forward,
            status=clean(applied_text.get("status")) or "APPLIED_CARRY_FORWARD_UNCHANGED",
            promoted=False,
        ),
        "policy_blocked_not_failure": row_group(
            policy_blocked,
            status="policy_blocked_not_failure",
            promoted=False,
            counted_as_failure=False,
        ),
        "source_binding_review_required": row_group(
            source_binding,
            status="source_binding_review_required",
            promoted=False,
        ),
        "diagnostic_only_default": row_group(
            diagnostic_only,
            status="diagnostic_only_default",
            promoted=False,
        ),
        "expected_answer_or_evidence_revision": row_group(
            expected_revision,
            status="unresolved_expected_answer_or_evidence_revision",
            promoted=False,
        ),
        "exclusive_status_counts": {
            "counts": {name: len(ids) for name, ids in exclusive.items()},
            "total": sum(len(ids) for ids in exclusive.values()),
            "query_ids_by_status": exclusive,
        },
    }
    return groups


def inspect_generated_answer_artifacts(paths: Iterable[Path]) -> dict[str, Any]:
    artifact_rows: list[dict[str, Any]] = []
    actual_rows: list[dict[str, Any]] = []
    path_states: list[dict[str, Any]] = []
    json_payloads_seen = False
    parse_errors: list[str] = []
    for path in paths:
        state: dict[str, Any] = {
            "path": repo_relative(path),
            "exists": path.exists(),
            "row_count": 0,
            "actual_generated_answer_rows": 0,
            "official_metric_input_rows": 0,
            "sha256": sha256_if_exists(path),
        }
        if path.exists() and path.suffix.lower() == ".jsonl":
            rows, row_parse_errors = read_jsonl_with_errors(path)
            parse_errors.extend(row_parse_errors)
            state["row_count"] = len(rows)
            state["parse_error_count"] = len(row_parse_errors)
            state["parse_errors"] = row_parse_errors
            state["actual_generated_answer_rows"] = sum(1 for row in rows if is_actual_generated_answer_row(row))
            state["official_metric_input_rows"] = sum(1 for row in rows if row.get("official_metric_input") is True)
            artifact_rows.extend(rows)
            actual_rows.extend(row for row in rows if is_actual_generated_answer_row(row))
        elif path.exists() and path.suffix.lower() == ".json":
            json_payloads_seen = True
            payload = read_json_if_exists(path)
            state["row_count"] = int(payload.get("query_count") or payload.get("row_count") or 0)
            state["actual_generated_answer_rows"] = 0
            state["json_payload_not_counted_as_required_jsonl"] = True
            state["official_metric_input_rows"] = int(payload.get("official_metric_input_rows") or 0) + (
                1 if payload.get("official_metric_input") is True else 0
            )
            artifact_rows.append(payload)
        path_states.append(state)

    contract_errors = generated_answer_contract_errors_by_query(actual_rows)
    query_counts = Counter(clean(row.get("query_id")) for row in actual_rows if clean(row.get("query_id")))
    duplicate_query_ids = sorted(query_id for query_id, count in query_counts.items() if count > 1)
    actual_count = sum(int(state["actual_generated_answer_rows"]) for state in path_states)
    actual_query_ids = sorted({clean(row.get("query_id")) for row in actual_rows if clean(row.get("query_id"))})
    return {
        "actual_generated_answer_output_available": bool(actual_query_ids),
        "actual_generated_answer_row_count": actual_count,
        "actual_generated_answer_query_ids": actual_query_ids,
        "official_metric_input_rows": sum(int(state["official_metric_input_rows"]) for state in path_states),
        "official_denominator_mutation_rows": sum(
            1 for row in artifact_rows if row.get("official_denominator_mutation") is True
        ),
        "generated_answer_contract_error_count": len(contract_errors),
        "generated_answer_contract_errors_by_query_id": contract_errors,
        "generated_answer_parse_error_count": len(parse_errors),
        "generated_answer_parse_errors": parse_errors,
        "generated_answer_duplicate_query_ids": duplicate_query_ids,
        "json_payloads_not_counted_as_required_jsonl": json_payloads_seen,
        "candidate_artifacts": path_states,
        "missing_required_artifacts": [state["path"] for state in path_states if not state["exists"]],
        "deterministic_or_expected_answer_fields_not_treated_as_actual": True,
        "normalized_actual_generated_answer_rows": [
            {
                "query_id": clean(row.get("query_id")),
                "answer_text_present": bool(clean(row.get("generated_answer") or row.get("answer") or row.get("final_answer"))),
            }
            for row in actual_rows
        ],
    }


def is_actual_generated_answer_row(row: Mapping[str, Any]) -> bool:
    if row.get("dry_run_preview_used_as_actual_answer") is True:
        return False
    answer_text = clean(row.get("generated_answer") or row.get("answer") or row.get("final_answer"))
    if not clean(row.get("query_id")) or not answer_text:
        return False
    return any(row.get(field) is True for field in ACTUAL_GENERATED_ANSWER_FIELDS)


def generated_answer_contract_errors_by_query(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for index, row in enumerate(rows, start=1):
        row_errors = generated_answer_contract_errors(row)
        if row_errors:
            errors[clean(row.get("query_id")) or f"<row:{index}>"] = row_errors
    return errors


def generated_answer_contract_errors(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if row.get("dry_run_preview_used_as_actual_answer") is True:
        errors.append("dry-run previews must not be used as generated answer output")
    if not clean(row.get("query_id")):
        errors.append("query_id is required")
    if not clean(row.get("safe_query_text") or row.get("query")):
        errors.append("safe query text is required")
    if not clean(row.get("generated_answer") or row.get("answer") or row.get("final_answer")):
        errors.append("generated answer text is required")
    cited = clean_id_list(row.get("cited_chunk_ids"))
    retrieved = clean_id_list(row.get("retrieved_chunk_ids"))
    if not cited:
        errors.append("cited chunk ids are required")
    if not retrieved:
        errors.append("retrieved chunk ids are required")
    if cited and retrieved and not set(cited).issubset(set(retrieved)):
        errors.append("cited chunk ids must be present in retrieved chunk ids")
    citation_items = row.get("citation_items")
    if not isinstance(citation_items, list) or not citation_items:
        errors.append("citation text or citation locator is required for each cited chunk")
    else:
        item_by_chunk = {
            clean(item.get("chunk_id")): item for item in citation_items if isinstance(item, Mapping)
        }
        for chunk_id in cited:
            item = item_by_chunk.get(chunk_id)
            if not item:
                errors.append(f"{chunk_id}: citation item is missing")
                continue
            if not clean(item.get("citation_text")) and not item.get("citation_locator"):
                errors.append(f"{chunk_id}: citation text or citation locator is required")
    generation = row.get("generation_provenance")
    if not isinstance(generation, Mapping):
        errors.append("generation provenance is required")
    else:
        if not clean(generation.get("generator_name")):
            errors.append("generation provenance generator_name is required")
        if not clean(generation.get("answer_generation_execution")):
            errors.append("generation provenance answer_generation_execution is required")
        if generation.get("actual_generated_answer_output") is not True:
            errors.append("generation provenance actual_generated_answer_output must be true")
        if generation.get("official_metric_input") is not False:
            errors.append("generation provenance official_metric_input must be false")
    retrieval = row.get("retrieval_provenance")
    if not isinstance(retrieval, Mapping) or not (
        clean(retrieval.get("retrieval_run_id")) or clean(retrieval.get("source_artifact_id"))
    ):
        errors.append("retrieval run id or source artifact id is required")
    elif retrieval.get("production_index_used") is not False:
        errors.append("retrieval provenance production_index_used must be false")
    elif retrieval.get("production_index_mutation") is not False:
        errors.append("retrieval provenance production_index_mutation must be false")
    prompt = row.get("prompt_model_config_provenance")
    if not isinstance(prompt, Mapping):
        errors.append("prompt/model/config provenance is required")
    else:
        if not clean(prompt.get("prompt_template_sha256")):
            errors.append("prompt/model/config provenance prompt_template_sha256 is required")
        if not clean(prompt.get("model_name")):
            errors.append("prompt/model/config provenance model_name is required")
    if row.get("diagnostic_only") is not True:
        errors.append("diagnostic_only must be true")
    if row.get("official_metric_input") is not False:
        errors.append("official_metric_input must be explicit boolean false")
    if row.get("official_denominator_mutation") is not False:
        errors.append("official_denominator_mutation must be explicit boolean false")
    return errors


def route_fallback_state(*, route_applied: Path, fallback_applied: Path) -> dict[str, Any]:
    route = read_json_if_exists(route_applied)
    fallback = read_json_if_exists(fallback_applied)
    route_counts = route.get("counts") if isinstance(route.get("counts"), Mapping) else {}
    fallback_counts = fallback.get("counts") if isinstance(fallback.get("counts"), Mapping) else {}
    route_rows = row_like_dicts(route)
    fallback_rows = row_like_dicts(fallback)
    counted_official_rows = int(route_counts.get("official_metric_input_rows") or 0) + int(
        fallback_counts.get("official_metric_input_rows") or 0
    )
    row_official_rows = sum(
        1 for row in route_rows + fallback_rows if row.get("official_metric_input") is True
    )
    denominator_mutation_rows = sum(
        1 for row in route_rows + fallback_rows if row.get("official_denominator_mutation") is True
    )
    official_rows = counted_official_rows + row_official_rows
    artifacts_exist = route_applied.exists() and fallback_applied.exists()
    diagnostic_only = (
        artifacts_exist
        and route.get("diagnostic_only") is True
        and fallback.get("diagnostic_only") is True
        and not bool(route.get("route_metrics_official"))
        and not bool(fallback.get("fallback_metrics_official"))
        and official_rows == 0
        and denominator_mutation_rows == 0
    )
    return {
        "diagnostic_only": diagnostic_only,
        "route_artifact_exists": route_applied.exists(),
        "fallback_artifact_exists": fallback_applied.exists(),
        "route_metrics_official": bool(route.get("route_metrics_official")),
        "fallback_metrics_official": bool(fallback.get("fallback_metrics_official")),
        "official_metric_input_rows": official_rows,
        "row_official_metric_input_rows": row_official_rows,
        "official_denominator_mutation_rows": denominator_mutation_rows,
        "applied_labels_promoted_to_official_metrics": False,
    }


def row_like_dicts(payload: object) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            rows.extend(row_like_dicts(item))
    elif isinstance(payload, Mapping):
        if "query_id" in payload and (
            "official_metric_input" in payload or "official_denominator_mutation" in payload
        ):
            rows.append(dict(payload))
        for value in payload.values():
            if isinstance(value, (list, dict)):
                rows.extend(row_like_dicts(value))
    return rows


def validation_errors(
    *,
    groups: Mapping[str, Any],
    registry_text_answer_keys: list[str],
    official_metric_input_rows: int,
    route_state: Mapping[str, Any],
    generated: Mapping[str, Any],
    candidate_ids: list[str],
) -> list[str]:
    errors: list[str] = []
    if registry_text_answer_keys:
        errors.append("TEXT answer/citation denominator appears opened in registry")
    if official_metric_input_rows != 0:
        errors.append("official_metric_input_rows must remain 0")
    if int(generated.get("official_denominator_mutation_rows") or 0) != 0:
        errors.append("generated answer artifacts must not mutate official denominators")
    generated_contract_errors = generated.get("generated_answer_contract_errors_by_query_id")
    if isinstance(generated_contract_errors, Mapping) and generated_contract_errors:
        for query_id, row_errors in sorted(generated_contract_errors.items()):
            if isinstance(row_errors, list):
                for row_error in row_errors:
                    errors.append(f"{query_id}: {row_error}")
            else:
                errors.append(f"{query_id}: generated answer contract error")
    parse_errors = generated.get("generated_answer_parse_errors")
    if isinstance(parse_errors, list):
        for parse_error in parse_errors:
            errors.append(f"generated answer artifact JSONL parse error: {parse_error}")
    duplicate_query_ids = clean_list(generated.get("generated_answer_duplicate_query_ids"))
    if duplicate_query_ids:
        errors.append(f"generated answer artifacts contain duplicate query ids: {', '.join(duplicate_query_ids)}")
    actual_query_ids = set(clean_list(generated.get("actual_generated_answer_query_ids")))
    extra_query_ids = sorted(actual_query_ids.difference(set(candidate_ids)))
    if extra_query_ids:
        errors.append(f"generated answer artifacts contain non-candidate query ids: {', '.join(extra_query_ids)}")
    if groups["applied_unresolved_carry_forward"]["promoted"] is not False:
        errors.append("unresolved carry-forward rows must not be promoted")
    if groups["policy_blocked_not_failure"].get("counted_as_failure") is not False:
        errors.append("policy-blocked rows must not be counted as failures")
    if route_state.get("official_metric_input_rows") != 0:
        errors.append("route/fallback applied labels must remain outside official metric input")
    if route_state.get("official_denominator_mutation_rows") != 0:
        errors.append("route/fallback applied labels must not mutate official denominators")
    if not route_state.get("route_artifact_exists") or not route_state.get("fallback_artifact_exists"):
        errors.append("route/fallback applied artifacts must exist for this prep report")
    if route_state.get("diagnostic_only") is not True:
        errors.append("route/fallback applied labels must be diagnostic-only")
    if route_state.get("route_metrics_official") or route_state.get("fallback_metrics_official"):
        errors.append("route/fallback applied labels must remain diagnostic-only")
    return errors


def source_artifact_errors(
    *,
    text_review_pack: Path,
    review_rows: list[dict[str, str]],
    normalization_report: Path,
    normalization: Mapping[str, Any],
    text: Mapping[str, Any],
    candidate_ids: list[str],
    applied_decisions: Path,
    applied: Mapping[str, Any],
    applied_text: Mapping[str, Any],
    denominator_registry: Path,
    registry: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if not text_review_pack.exists():
        errors.append("TEXT review pack is missing")
    if not review_rows:
        errors.append("TEXT review pack has no rows")
    if not normalization_report.exists():
        errors.append("reviewed gold policy normalization report is missing")
    if not normalization:
        errors.append("reviewed gold policy normalization report is missing or invalid JSON")
    if not text:
        errors.append("normalization report missing tracks.text_namu_v2")
    text_row_count = int(text.get("row_count") or 0)
    if text_row_count <= 0:
        errors.append("normalization report TEXT row_count must be positive")
    elif review_rows and len(review_rows) != text_row_count:
        errors.append(f"TEXT review pack row count {len(review_rows)} does not match normalization row_count {text_row_count}")
    if not candidate_ids:
        errors.append("TEXT answer/citation prep candidate ids are missing")
    if not applied_decisions.exists():
        errors.append("gold policy applied decisions artifact is missing")
    if not applied:
        errors.append("gold policy applied decisions artifact is missing or invalid JSON")
    if not applied_text:
        errors.append("applied decisions missing text_namu_v2_unresolved_carry_forward")
    if not denominator_registry.exists():
        errors.append("official denominator registry is missing")
    if not registry:
        errors.append("official denominator registry is missing or invalid JSON")
    return errors


def remaining_blockers(generated_missing_ids: list[str], registry_keys: list[str]) -> list[str]:
    blockers = [
        "Official TEXT answer/citation-support denominator remains closed.",
        "Route/fallback applied labels remain diagnostic-only and are not official metric inputs.",
    ]
    if generated_missing_ids:
        blockers.append("Actual generated TEXT/Namu answer outputs are missing for candidate review rows.")
    if not registry_keys:
        blockers.append("No reviewed registry artifact authorizes opening TEXT answer/citation-support denominators.")
    return blockers


def text_answer_citation_registry_keys(registry: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    for section_name in ("current_defaults", "official_diagnostic_denominators"):
        section = registry.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for key, value in section.items():
            text = json.dumps(value, ensure_ascii=False).lower()
            key_l = str(key).lower()
            if ("text" in key_l or "namu" in key_l or "text" in text or "namu" in text) and (
                "answer" in key_l or "citation" in key_l or "answer" in text or "citation" in text
            ):
                keys.append(f"{section_name}.{key}")
    return sorted(keys)


def render_markdown(report: Mapping[str, Any]) -> str:
    prep = report["answer_citation_review_preparation"]
    blocked = report["blocked_row_accounting"]
    generated = report["generated_answer_availability"]
    guardrails = report["guardrails"]
    lines = [
        "# TEXT/Namu Answer/Citation Review Prep",
        "",
        "## Status",
        "",
        f"- status: `{report['status']}`",
        f"- diagnostic_only: `{report['diagnostic_only']}`",
        f"- promotion_evidence: `{report['promotion_evidence']}`",
        f"- official_metric_input_rows: `{report['official_metric_input_rows']}`",
        "",
        "## Row Counts",
        "",
        f"- candidate review rows: `{prep['candidate_review_rows_count']}`",
        f"- generated-answer-missing rows: `{prep['generated_answer_missing_count']}`",
        f"- unresolved carry-forward rows: `{blocked['unresolved_carry_forward_count']}`",
        f"- policy-blocked rows: `{blocked['policy_blocked_rows_count']}`",
        f"- source-binding review rows: `{blocked['source_binding_review_required_count']}`",
        f"- diagnostic-only default rows: `{blocked['diagnostic_only_default_count']}`",
        "",
        "## Generated Answer Availability",
        "",
        f"- actual generated answer output available: `{generated['actual_generated_answer_output_available']}`",
        f"- actual generated answer rows: `{generated['actual_generated_answer_row_count']}`",
        f"- next required artifact: `{prep['next_required_artifact']}`",
        "",
        "## Guardrails",
        "",
        f"- official denominator registry changed: `{guardrails['official_denominator_registry_changed']}`",
        f"- text answer denominator opened: `{guardrails['text_answer_denominator_opened']}`",
        f"- text citation denominator opened: `{guardrails['text_citation_support_denominator_opened']}`",
        f"- policy-blocked rows counted as failures: `{guardrails['policy_blocked_rows_counted_as_failures']}`",
        f"- route/fallback applied labels diagnostic-only: `{guardrails['route_fallback_applied_labels_diagnostic_only']}`",
    ]
    return "\n".join(lines) + "\n"


def row_group(
    query_ids: Iterable[str],
    *,
    status: str,
    promoted: bool,
    counted_as_failure: bool | None = None,
) -> dict[str, Any]:
    ids = sorted(set(clean_list(query_ids)))
    payload: dict[str, Any] = {
        "count": len(ids),
        "query_ids": ids,
        "status": status,
        "promoted": promoted,
    }
    if counted_as_failure is not None:
        payload["counted_as_failure"] = counted_as_failure
    return payload


def artifact_info(path: Path, expected_rows: int | None = None) -> dict[str, Any]:
    info = {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_if_exists(path),
    }
    if expected_rows is not None:
        info["expected_row_count"] = expected_rows
    return info


def count_field(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts = Counter(clean(row.get(field)) or "<blank>" for row in rows)
    return dict(sorted(counts.items()))


def read_csv_if_exists(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    rows, _errors = read_jsonl_with_errors(path)
    return rows


def read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.exists():
        return rows, errors
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{repo_relative(path)}:{line_number}: {exc.msg}")
                continue
            if isinstance(payload, dict):
                rows.append(payload)
            else:
                errors.append(f"{repo_relative(path)}:{line_number}: row must be a JSON object")
    return rows, errors


def clean_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, Iterable):
        return []
    return [clean(item) for item in value if clean(item)]


def clean_id_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.replace("|", ";").replace(",", ";").split(";") if part.strip()]
    if not isinstance(value, Iterable):
        return []
    return [clean(item) for item in value if clean(item)]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


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
