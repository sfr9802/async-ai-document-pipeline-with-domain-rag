"""Generate XLSX strict retrieval/evidence silver manifest and report.

This is the current XLSX retrieval/evidence silver lane only. It must pass the
strict pre-silver gate before emitting any artifact, does not run answer
generation, and does not mutate denominator registries, production vectors,
candidate indexes, candidate artifacts, or immutable baselines.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_xlsx_pre_silver_risk_closure import (  # noqa: E402
    CURRENT_XLSX_RETRIEVAL_GOLD,
    EXPECTED_OFFICIAL_POSITIVE_ROW_COUNT,
    EXPECTED_XLSX_ANSWER_DENOMINATOR,
    SPECIAL_NON_OFFICIAL_QUERY_IDS,
    STRICT_APPROVAL_STATUS,
    XLSX_CANDIDATE_INDEX_DIR,
    XLSX_CANDIDATE_NAMESPACE,
    assert_silver_generation_allowed,
    resolve_current_xlsx_human_review_artifacts,
    validate_official_xlsx_eval_route,
)


REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"

DEFAULT_PRE_SILVER_REPORT = REPORT_DIR / "xlsx_pre_silver_risk_closure_20260507.json"
DEFAULT_OFFICIAL_POSITIVE_CSV = EVAL_QUERY_DIR / "gold_queries_xlsx_human_review_official_positive_v0.csv"
DEFAULT_OFFICIAL_RETRIEVAL_CSV = EVAL_QUERY_DIR / "gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv"
DEFAULT_NORMALIZED_CSV = EVAL_QUERY_DIR / "gold_queries_xlsx_human_review_normalized_v0.csv"
DEFAULT_RETRIEVAL_REPORT = (
    REPORT_DIR / "rag_retrieval_eval_xlsx_human_review_official_positive_v0_vector_diagnostic_report.json"
)
DEFAULT_RETRIEVAL_SUMMARY = (
    REPORT_DIR / "rag_xlsx_human_review_official_positive_v0_retrieval_performance_summary.json"
)
DEFAULT_LEAKAGE_REPORT = REPORT_DIR / "xlsx_hidden_excluded_leakage_probe_report.json"
DEFAULT_THREE_TRACK_REPORT = REPORT_DIR / "three_track_orchestration_report.json"
DEFAULT_REGISTRY = EVAL_QUERY_DIR / "official_denominator_registry.json"
DEFAULT_JSON_OUTPUT = REPORT_DIR / "xlsx_strict_silver_generation_report.json"
DEFAULT_MD_OUTPUT = REPORT_DIR / "xlsx_strict_silver_generation_report.md"
DEFAULT_EXTERNAL_SILVER_OUTPUT = (
    REPO_ROOT.parent
    / "_external_runtime_artifacts"
    / "async-ocr-rag-multimodal-pipeline"
    / "rag-ingestion"
    / "xlsx_strict_silver_generation"
    / "xlsx_strict_silver_retrieval_evidence_manifest.jsonl"
)

SCHEMA_VERSION = "xlsx_strict_silver_generation_report_v1"
SILVER_SCHEMA_VERSION = "xlsx_strict_retrieval_evidence_silver_v1"
PENDING_EVIDENCE_IDS = tuple(sorted(SPECIAL_NON_OFFICIAL_QUERY_IDS))

REQUIRED_XLSX_CITATION_METADATA_FIELDS = (
    "file",
    "sheet",
    "table_id",
    "table_range",
    "matched_cells",
    "header_rows",
    "target_rows",
    "target_columns",
    "row_values",
    "column_headers",
    "nearby_rows",
    "merged_cell_context",
    "table_title_candidate",
    "score",
)

STRICT_REQUIRED_NONEMPTY_FIELDS = (
    "file",
    "sheet",
    "table_range",
    "matched_cells",
    "header_rows",
    "target_rows",
    "target_columns",
    "row_values",
    "column_headers",
    "nearby_rows",
    "score",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report, silver_rows = build_generation(
        pre_silver_report=Path(args.pre_silver_report),
        official_positive_csv=Path(args.official_positive_csv),
        official_retrieval_csv=Path(args.official_retrieval_csv),
        normalized_csv=Path(args.normalized_csv),
        retrieval_report=Path(args.retrieval_report),
        retrieval_summary=Path(args.retrieval_summary),
        leakage_report=Path(args.leakage_report),
        three_track_report=Path(args.three_track_report),
        official_denominator_registry=Path(args.official_denominator_registry),
        silver_output=Path(args.silver_output),
    )
    silver_output = Path(args.silver_output)
    if report["status"] == "COMPLETED_DIAGNOSTIC_ONLY":
        write_jsonl(silver_output, silver_rows)
        report["silver_artifact_policy"]["external_silver_artifact"] = file_identity(silver_output)
        report["silver_artifact_policy"]["external_silver_artifact_written"] = True
    else:
        report["silver_artifact_policy"]["external_silver_artifact"] = file_identity(silver_output)
        report["silver_artifact_policy"]["external_silver_artifact_written"] = False

    json_output = Path(args.json_output)
    md_output = Path(args.md_output)
    write_json(json_output, report)
    md_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "json_output": repo_relative(json_output),
                "md_output": repo_relative(md_output),
                "external_silver_output": str(silver_output.resolve()),
                "input_denominator_row_count": report["counts"]["input_denominator_row_count"],
                "generated_silver_row_count": report["counts"]["generated_silver_row_count"],
                "hidden_excluded_leakage_status": report["hidden_excluded_leakage_result"]["status"],
                "official_denominator_registry_changed": report["guardrails"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "COMPLETED_DIAGNOSTIC_ONLY" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-silver-report", default=str(DEFAULT_PRE_SILVER_REPORT))
    parser.add_argument("--official-positive-csv", default=str(DEFAULT_OFFICIAL_POSITIVE_CSV))
    parser.add_argument("--official-retrieval-csv", default=str(DEFAULT_OFFICIAL_RETRIEVAL_CSV))
    parser.add_argument("--normalized-csv", default=str(DEFAULT_NORMALIZED_CSV))
    parser.add_argument("--retrieval-report", default=str(DEFAULT_RETRIEVAL_REPORT))
    parser.add_argument("--retrieval-summary", default=str(DEFAULT_RETRIEVAL_SUMMARY))
    parser.add_argument("--leakage-report", default=str(DEFAULT_LEAKAGE_REPORT))
    parser.add_argument("--three-track-report", default=str(DEFAULT_THREE_TRACK_REPORT))
    parser.add_argument("--official-denominator-registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--silver-output", default=str(DEFAULT_EXTERNAL_SILVER_OUTPUT))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--md-output", default=str(DEFAULT_MD_OUTPUT))
    return parser.parse_args(argv)


def build_report(**kwargs: Any) -> dict[str, Any]:
    report, _silver_rows = build_generation(**kwargs)
    return report


def build_generation(
    *,
    pre_silver_report: Path = DEFAULT_PRE_SILVER_REPORT,
    official_positive_csv: Path = DEFAULT_OFFICIAL_POSITIVE_CSV,
    official_retrieval_csv: Path = DEFAULT_OFFICIAL_RETRIEVAL_CSV,
    normalized_csv: Path = DEFAULT_NORMALIZED_CSV,
    retrieval_report: Path = DEFAULT_RETRIEVAL_REPORT,
    retrieval_summary: Path = DEFAULT_RETRIEVAL_SUMMARY,
    leakage_report: Path = DEFAULT_LEAKAGE_REPORT,
    three_track_report: Path = DEFAULT_THREE_TRACK_REPORT,
    official_denominator_registry: Path = DEFAULT_REGISTRY,
    silver_output: Path = DEFAULT_EXTERNAL_SILVER_OUTPUT,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    assert_external_silver_output_path(silver_output)
    assert_canonical_strict_inputs(
        official_positive_csv=official_positive_csv,
        official_retrieval_csv=official_retrieval_csv,
        normalized_csv=normalized_csv,
    )
    registry_sha_before = sha256_file(official_denominator_registry)
    pre_silver = load_json(pre_silver_report)
    assert_silver_generation_allowed(pre_silver)
    validate_official_xlsx_eval_route(
        eval_mode="official",
        track="XLSX",
        agent_orchestrator_enabled=False,
        retrieval_backend="vector",
        namespace=XLSX_CANDIDATE_NAMESPACE,
        vector_index_dir=XLSX_CANDIDATE_INDEX_DIR,
        positive_gold=CURRENT_XLSX_RETRIEVAL_GOLD,
        candidate_index_version=XLSX_CANDIDATE_NAMESPACE,
        required_index_version=XLSX_CANDIDATE_NAMESPACE,
        combined_retrieval_enabled=False,
    )
    resolved_artifacts = resolve_current_xlsx_human_review_artifacts(
        registry_path=official_denominator_registry,
        require_source_snapshot=False,
    )

    official_rows = read_csv_rows(official_positive_csv)
    retrieval_rows = read_csv_rows(official_retrieval_csv)
    normalized_rows = read_csv_rows(normalized_csv)
    retrieval_payload = load_json(retrieval_report)
    summary_payload = load_json(retrieval_summary)
    leakage_payload = load_json(leakage_report)
    three_track_payload = load_json(three_track_report)

    official_by_id = {clean(row.get("query_id")): row for row in official_rows}
    retrieval_ids = [clean(row.get("query_id")) for row in retrieval_rows if clean(row.get("query_id"))]
    included_ids = [query_id for query_id in retrieval_ids if query_id in official_by_id]
    missing_official_ids = sorted(set(retrieval_ids) - set(official_by_id))
    pending_ids = set(PENDING_EVIDENCE_IDS)
    normalized_non_generated = [
        row
        for row in normalized_rows
        if clean(row.get("query_id")) and clean(row.get("query_id")) not in set(included_ids)
    ]
    normalized_excluded = [
        row for row in normalized_rows if clean(row.get("derived_denominator_policy")) == "EXCLUDED"
    ]
    normalized_hidden_negative = [row for row in normalized_excluded if is_hidden_negative_row(row)]

    diagnostic_by_id = {
        clean(row.get("query_id")): row
        for row in retrieval_payload.get("query_results", [])
        if isinstance(row, Mapping) and clean(row.get("query_id"))
    }
    silver_rows = [
        silver_row_from_sources(
            query_id=query_id,
            official_row=official_by_id[query_id],
            diagnostic_row=diagnostic_by_id.get(query_id, {}),
        )
        for query_id in included_ids
    ]
    diagnostic_fallback_rows = [
        {
            "query_id": row["query_id"],
            "reason": row["diagnostic_only_reason"],
            "missing_context_fields": row["missing_context_fields"],
        }
        for row in silver_rows
        if row["diagnostic_only"]
    ]
    metadata_completeness = citation_metadata_completeness(silver_rows)
    strict_metrics = strict_silver_metrics(silver_rows)
    retrieval_metrics = summary_payload.get("metrics") or retrieval_payload.get("metrics") or {}
    leakage_counts = leakage_payload.get("counts") if isinstance(leakage_payload.get("counts"), Mapping) else {}
    leakage_metrics = leakage_payload.get("metrics") if isinstance(leakage_payload.get("metrics"), Mapping) else {}
    leakage_guardrails = leakage_payload.get("guardrails") if isinstance(leakage_payload.get("guardrails"), Mapping) else {}
    surface_coverage = leakage_payload.get("surface_coverage") if isinstance(leakage_payload.get("surface_coverage"), Mapping) else {}
    registry_sha_after = sha256_file(official_denominator_registry)
    guardrail_payloads = (three_track_payload, leakage_payload)

    guardrails = {
        "official_denominator_registry_changed": registry_sha_before != registry_sha_after,
        "official_denominator_opened_or_frozen": bool(
            nested_guardrail_flag(
                *guardrail_payloads,
                keys=("official_denominator_opened_or_frozen",),
            )
        ),
        "xlsx_answer_generation_denominator_opened": xlsx_answer_generation_denominator(three_track_payload) != 0,
        "production_namespace_mutated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("production_namespace_mutated",),
        ),
        "production_vector_index_mutated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("production_vector_index_mutated",),
        ),
        "production_vector_written": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("production_vector_written",),
        ),
        "repo_local_silver_manifest_written": silver_output.resolve().is_relative_to(REPO_ROOT.resolve()),
        "candidate_artifact_mutated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("candidate_artifact_mutated",),
        ),
        "immutable_baseline_mutated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=("immutable_baseline_mutated",),
        ),
        "diagnostic_only_row_promoted": bool(
            three_track_payload.get("diagnostic_only_row_promoted", False)
            or leakage_guardrails.get("diagnostic_only_row_promoted", False)
        ),
        "hidden_xlsx_exposed": bool(
            leakage_counts.get("surface_leakage_count", 0)
            or leakage_guardrails.get("hidden_xlsx_content_exposed", False)
            or leakage_guardrails.get("hidden_excluded_content_exposed", False)
        ),
        "policy_excluded_rows_counted_as_retrieval_failures": bool(
            leakage_guardrails.get("policy_excluded_rows_counted_as_retrieval_failures", False)
            or leakage_metrics.get("policy_excluded_retrieval_failure_count", 0)
        ),
        "route_fallback_labels_promoted_to_official_metrics": nested_guardrail_flag(
            *guardrail_payloads,
            keys=(
                "route_fallback_labels_official_metric",
                "route_metrics_official",
                "fallback_metrics_official",
                "official_routing_accuracy_computed",
                "official_wrong_route_rate_computed",
                "official_fallback_success_computed",
                "official_multi_route_success_computed",
                "official_metric_input_rows",
            ),
        ),
        "pdf_content_file_lanes_aggregated": nested_guardrail_flag(
            *guardrail_payloads,
            keys=(
                "pdf_content_and_file_identity_aggregated",
                "pdf_content_file_lanes_aggregated",
                "pdf_lanes_aggregated",
            ),
        ),
        "answer_generation_run": False,
        "answer_citation_surfaces_opened": surface_status(surface_coverage, "answer") != "NOT_OPENED"
        or surface_status(surface_coverage, "citation") != "NOT_OPENED",
        "diagnostic_only_row_promoted_from_flattened_evidence": any(
            row["diagnostic_only"] is False and row["diagnostic_only_reason"] == "flattened_only"
            for row in silver_rows
        ),
    }
    validation_errors = validate_generation(
        included_ids=included_ids,
        missing_official_ids=missing_official_ids,
        pending_ids=pending_ids,
        normalized_rows=normalized_rows,
        silver_rows=silver_rows,
        diagnostic_fallback_rows=diagnostic_fallback_rows,
        guardrails=guardrails,
        pre_silver=pre_silver,
        leakage_payload=leakage_payload,
    )
    status = "COMPLETED_DIAGNOSTIC_ONLY" if not validation_errors else "FAILED_GUARDRAIL"

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "xlsx_strict_retrieval_evidence_silver_generation_diagnostic",
        "track": "xlsx_business_structured",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "answer_generation_run": False,
        "approved_strict_wrapper": {
            "approval_report": repo_relative(pre_silver_report),
            "approval_status": pre_silver.get("status"),
            "strict_guard_script": "ai/scripts/rag_xlsx_pre_silver_risk_closure.py",
            "strict_guard_function": "assert_silver_generation_allowed",
            "retrieval_wrapper_script": "ai/scripts/rag_xlsx_retrieval_performance_diagnostic.py",
            "retrieval_wrapper_default_gold": repo_relative(official_retrieval_csv),
            "legacy_track_a_diagnostic_default_used": False,
            "generic_agent_orchestrator_allowed_for_official_xlsx": False,
        },
        "source_artifacts": {
            "official_positive_csv": file_identity(official_positive_csv),
            "official_retrieval_csv": file_identity(official_retrieval_csv),
            "normalized_csv": file_identity(normalized_csv),
            "retrieval_report": file_identity(retrieval_report),
            "retrieval_summary": file_identity(retrieval_summary),
            "hidden_excluded_leakage_report": file_identity(leakage_report),
            "three_track_report": file_identity(three_track_report),
            "official_denominator_registry": file_identity(official_denominator_registry),
        },
        "resolved_current_xlsx_artifacts": resolved_artifacts,
        "counts": {
            "normalized_row_count": len(normalized_rows),
            "input_denominator_row_count": len(retrieval_rows),
            "generated_silver_row_count": len(silver_rows),
            "strict_structured_row_count": len(silver_rows) - len(diagnostic_fallback_rows),
            "diagnostic_only_fallback_row_count": len(diagnostic_fallback_rows),
            "excluded_row_count": len(normalized_non_generated),
            "normalized_excluded_row_count": len(normalized_excluded),
            "normalized_hidden_negative_row_count": len(normalized_hidden_negative),
            "pending_evidence_row_count": len(pending_ids),
        },
        "included_query_ids": included_ids,
        "excluded_query_ids": {
            "pending_evidence": sorted(pending_ids),
            "normalized_hidden_negative": sorted(clean(row.get("query_id")) for row in normalized_hidden_negative),
            "normalized_excluded": sorted(clean(row.get("query_id")) for row in normalized_excluded),
        },
        "hidden_excluded_leakage_result": {
            "status": leakage_payload.get("status"),
            "probe_target_row_count": leakage_counts.get("probe_target_row_count"),
            "normalized_excluded_row_count": leakage_counts.get("normalized_excluded_row_count"),
            "normalized_hidden_negative_row_count": leakage_counts.get("normalized_hidden_negative_row_count"),
            "hidden_excluded_guard_row_count": leakage_counts.get("hidden_excluded_guard_row_count"),
            "surface_leakage_count": leakage_counts.get("surface_leakage_count", 0),
            "policy_excluded_rows_counted_as_retrieval_failures": leakage_guardrails.get(
                "policy_excluded_rows_counted_as_retrieval_failures", False
            ),
        },
        "surface_status": {
            "query": surface_status(surface_coverage, "query"),
            "candidate": surface_status(surface_coverage, "candidate"),
            "debug_public": surface_status(surface_coverage, "debug_public"),
            "official_denominator": surface_status(surface_coverage, "official_denominator"),
            "answer": surface_status(surface_coverage, "answer"),
            "citation": surface_status(surface_coverage, "citation"),
        },
        "retrieval_evidence_metrics": {
            "metric_source": repo_relative(retrieval_summary),
            "Hit@1": retrieval_metrics.get("Hit@1"),
            "Hit@3": retrieval_metrics.get("Hit@3"),
            "Hit@5": retrieval_metrics.get("Hit@5"),
            "Hit@10": retrieval_metrics.get("Hit@10"),
            "MRR@10": retrieval_metrics.get("MRR@10"),
            "xlsx_file_hit@10": retrieval_metrics.get("xlsx_file_hit@10"),
            "xlsx_sheet_hit@10": retrieval_metrics.get("xlsx_sheet_hit@10"),
            "xlsx_range_overlap@10": retrieval_metrics.get("xlsx_range_overlap@10"),
            "xlsx_range_contains@10": retrieval_metrics.get("xlsx_range_contains@10"),
            "xlsx_exact_range@10": retrieval_metrics.get("xlsx_exact_range@10"),
            "xlsx_citation_location_accuracy": retrieval_metrics.get("xlsx_citation_location_accuracy"),
            "hidden_content_leakage_count": retrieval_metrics.get("hidden_content_leakage_count", 0),
            "result_empty_count": retrieval_metrics.get("result_empty_count", 0),
        },
        "strict_silver_evidence_metrics": {
            "metric_source": "generated_strict_silver_manifest_completeness",
            **strict_metrics,
        },
        "citation_metadata_completeness": metadata_completeness,
        "diagnostic_only_fallback_rows": diagnostic_fallback_rows,
        "silver_manifest_preview": silver_manifest_preview(silver_rows),
        "silver_artifact_policy": {
            "canonical_repo_silver_artifact_defined": False,
            "repo_silver_artifact_written": False,
            "repo_local_full_manifest_allowed": False,
            "full_manifest_location_guard": "assert_external_silver_output_path",
            "decision": (
                "No canonical XLSX strict silver artifact path was found in the repository; "
                "the full 23-row retrieval/evidence manifest is written outside the repo and "
                "only this compact report is committed."
            ),
            "external_runtime_convention": "../_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/",
            "external_silver_artifact": file_identity(silver_output),
            "external_silver_artifact_written": silver_output.exists(),
        },
        "guardrails": guardrails,
        "validation": {
            "ok": not validation_errors,
            "errors": validation_errors,
        },
        "notes": [
            "Generated rows are restricted to the 23-row XLSX retrieval/evidence denominator.",
            "Pending, normalized excluded, and hidden-negative rows are not generated.",
            "Flattened-only evidence is diagnostic-only and is not promoted as strict structured evidence.",
            "Route/fallback applied labels are diagnostic analysis inputs only.",
            "PDF CONTENT evidence and PDF FILE/document identity lanes remain separate.",
        ],
    }
    return report, silver_rows


def assert_external_silver_output_path(silver_output: Path) -> None:
    """Keep the full silver manifest out of repo-local indexes/artifacts."""
    resolved = silver_output.resolve()
    repo_root = REPO_ROOT.resolve()
    if resolved == repo_root or resolved.is_relative_to(repo_root):
        raise ValueError(
            "XLSX strict silver manifest must be written outside the repository; "
            "compact report files are the only repo-local strict silver outputs."
        )


def assert_canonical_strict_inputs(**paths: Path) -> None:
    expected_paths = {
        "official_positive_csv": DEFAULT_OFFICIAL_POSITIVE_CSV,
        "official_retrieval_csv": DEFAULT_OFFICIAL_RETRIEVAL_CSV,
        "normalized_csv": DEFAULT_NORMALIZED_CSV,
    }
    for name, actual in paths.items():
        expected = expected_paths[name]
        if actual.resolve() != expected.resolve():
            raise ValueError(
                f"canonical XLSX strict input required for {name}: "
                f"expected {repo_relative(expected)!r}, got {repo_relative(actual)!r}"
            )


def silver_row_from_sources(
    *,
    query_id: str,
    official_row: Mapping[str, str],
    diagnostic_row: Mapping[str, Any],
) -> dict[str, Any]:
    locator = parse_json_object(official_row.get("citation_locator"))
    headers = parse_json_list(official_row.get("evidence_headers"))
    row_values = parse_json_list(official_row.get("evidence_row_values"))
    cell_values = parse_json_list(official_row.get("evidence_cell_values"))
    content_source_fields = parse_json_list(official_row.get("evidence_content_source_fields"))
    table_range = clean(official_row.get("range") or locator.get("range"))
    target_rows = rows_from_range(table_range)
    target_columns = columns_from_range(table_range)
    header_rows = infer_header_rows(table_range, headers)
    matched_hit = matched_diagnostic_hit(diagnostic_row)
    score = matched_hit.get("score") if matched_hit else None
    nearby_rows = nearby_rows_from_values(row_values)
    metadata = {
        "file": clean(locator.get("file") or official_row.get("citation_locator_file")),
        "sheet": clean(official_row.get("sheet") or locator.get("sheet")),
        "table_id": clean(locator.get("table_id") or official_row.get("expected_table_id")),
        "table_range": table_range,
        "matched_cells": [table_range] if table_range else [],
        "header_rows": header_rows,
        "target_rows": target_rows,
        "target_columns": target_columns,
        "row_values": row_values,
        "column_headers": headers,
        "nearby_rows": nearby_rows,
        "merged_cell_context": [],
        "table_title_candidate": table_title_candidate(official_row),
        "score": score,
    }
    missing = [field for field in STRICT_REQUIRED_NONEMPTY_FIELDS if not nonempty(metadata.get(field))]
    diagnostic_only = bool(missing)
    return {
        "schema_version": SILVER_SCHEMA_VERSION,
        "query_id": query_id,
        "track": "xlsx_business_structured",
        "evidence_lane": "xlsx_structured_evidence",
        "source_searchunit_id": clean(official_row.get("selected_searchunit_id")),
        "source_searchunit_rank": int_or_none(official_row.get("selected_searchunit_rank")),
        "strict_wrapper_path": "ai/scripts/rag_xlsx_retrieval_performance_diagnostic.py",
        "retrieval_denominator_included": True,
        "answer_generation_denominator_included": False,
        "official_metric_input": False,
        "promotion_evidence": False,
        "diagnostic_only": diagnostic_only,
        "diagnostic_only_reason": "flattened_only" if diagnostic_only else "",
        "missing_context_fields": missing,
        "citation_metadata": metadata,
        "citation_locator": {
            "file": metadata["file"],
            "sheet": metadata["sheet"],
            "range": metadata["table_range"],
            "document_version_id": clean(locator.get("document_version_id")),
            "search_unit_id": clean(locator.get("search_unit_id") or official_row.get("selected_searchunit_id")),
        },
        "contract_checks": {
            "locator_parse_status": clean(official_row.get("citation_locator_parse_status")),
            "locator_contract_valid": parse_bool(official_row.get("locator_contract_valid")),
            "expected_answer_contract_valid": parse_bool(official_row.get("expected_answer_contract_valid")),
            "must_contain_terms_contract_valid": parse_bool(official_row.get("must_contain_terms_contract_valid")),
            "content_source_fields": content_source_fields,
            "cell_values_present": bool(cell_values),
        },
    }


def matched_diagnostic_hit(diagnostic_row: Mapping[str, Any]) -> dict[str, Any]:
    results = diagnostic_row.get("top_k_results") if isinstance(diagnostic_row.get("top_k_results"), list) else []
    hit_rank = diagnostic_row.get("hit_rank")
    for result in results:
        if not isinstance(result, Mapping):
            continue
        if result.get("rank") == hit_rank:
            return dict(result)
    for result in results:
        if not isinstance(result, Mapping):
            continue
        breakdown = result.get("match_breakdown") if isinstance(result.get("match_breakdown"), Mapping) else {}
        if breakdown.get("identity_match") and breakdown.get("location_match"):
            return dict(result)
    return {}


def citation_metadata_completeness(silver_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    field_counts = {field: 0 for field in REQUIRED_XLSX_CITATION_METADATA_FIELDS}
    for row in silver_rows:
        metadata = row.get("citation_metadata") if isinstance(row.get("citation_metadata"), Mapping) else {}
        for field in REQUIRED_XLSX_CITATION_METADATA_FIELDS:
            if field in metadata:
                field_counts[field] += 1
    row_count = len(silver_rows)
    locator_complete = sum(1 for row in silver_rows if locator_complete_for_row(row))
    strict_count = sum(1 for row in silver_rows if not row.get("diagnostic_only"))
    return {
        "required_fields": list(REQUIRED_XLSX_CITATION_METADATA_FIELDS),
        "row_count": row_count,
        "field_presence_counts": field_counts,
        "field_presence_ratio": {
            field: ratio(count, row_count) for field, count in field_counts.items()
        },
        "locator_complete_row_count": locator_complete,
        "locator_completeness": ratio(locator_complete, row_count),
        "strict_structured_row_count": strict_count,
        "diagnostic_only_fallback_row_count": row_count - strict_count,
    }


def strict_silver_metrics(silver_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    row_count = len(silver_rows)
    return {
        "target_cell_hit": ratio(
            sum(1 for row in silver_rows if bool(metadata_value(row, "matched_cells"))),
            row_count,
        ),
        "target_row_hit": ratio(
            sum(1 for row in silver_rows if bool(metadata_value(row, "target_rows"))),
            row_count,
        ),
        "header_included": ratio(
            sum(1 for row in silver_rows if bool(metadata_value(row, "header_rows")) and bool(metadata_value(row, "column_headers"))),
            row_count,
        ),
        "target_column_included": ratio(
            sum(1 for row in silver_rows if bool(metadata_value(row, "target_columns"))),
            row_count,
        ),
        "surrounding_context_included": ratio(
            sum(1 for row in silver_rows if bool(metadata_value(row, "nearby_rows")) or bool(metadata_value(row, "row_values"))),
            row_count,
        ),
        "sheet_resolution_accuracy": ratio(
            sum(1 for row in silver_rows if bool(metadata_value(row, "sheet"))),
            row_count,
        ),
        "citation_locator_completeness": ratio(
            sum(1 for row in silver_rows if locator_complete_for_row(row)),
            row_count,
        ),
    }


def validate_generation(
    *,
    included_ids: Sequence[str],
    missing_official_ids: Sequence[str],
    pending_ids: set[str],
    normalized_rows: Sequence[Mapping[str, str]],
    silver_rows: Sequence[Mapping[str, Any]],
    diagnostic_fallback_rows: Sequence[Mapping[str, Any]],
    guardrails: Mapping[str, Any],
    pre_silver: Mapping[str, Any],
    leakage_payload: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    included_set = set(included_ids)
    if len(included_ids) != EXPECTED_OFFICIAL_POSITIVE_ROW_COUNT:
        errors.append(f"expected 23 included rows, got {len(included_ids)}")
    if missing_official_ids:
        errors.append("retrieval denominator rows missing official metadata: " + ", ".join(missing_official_ids))
    if pending_ids & included_set:
        errors.append("pending evidence rows included: " + ", ".join(sorted(pending_ids & included_set)))
    excluded_ids = {
        clean(row.get("query_id"))
        for row in normalized_rows
        if clean(row.get("derived_denominator_policy")) == "EXCLUDED"
    }
    if excluded_ids & included_set:
        errors.append("normalized excluded rows included: " + ", ".join(sorted(excluded_ids & included_set)))
    hidden_ids = {
        clean(row.get("query_id"))
        for row in normalized_rows
        if is_hidden_negative_row(row)
    }
    if hidden_ids & included_set:
        errors.append("hidden-negative rows included: " + ", ".join(sorted(hidden_ids & included_set)))
    if int(pre_silver.get("official_xlsx_answer_generation_denominator", -1)) != EXPECTED_XLSX_ANSWER_DENOMINATOR:
        errors.append("XLSX answer-generation denominator is not 0")
    if pre_silver.get("status") != STRICT_APPROVAL_STATUS:
        errors.append("strict pre-silver report is not approved")
    if leakage_payload.get("status") != "PASS":
        errors.append("hidden/excluded leakage probe is not PASS")
    if diagnostic_fallback_rows:
        errors.append("diagnostic-only fallback rows exist in strict silver manifest")
    for name, value in guardrails.items():
        if name == "answer_generation_run":
            expected = False
        elif name == "diagnostic_only_row_promoted_from_flattened_evidence":
            expected = False
        else:
            expected = False if name != "route_fallback_applied_labels_diagnostic_only" else True
        if value is not expected:
            if isinstance(value, bool) and value:
                errors.append(f"guardrail violation: {name}=true")
    if any(row.get("answer_generation_denominator_included") for row in silver_rows):
        errors.append("silver row entered answer-generation denominator")
    return errors


def silver_manifest_preview(silver_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    preview = []
    for row in silver_rows:
        metadata = row.get("citation_metadata") if isinstance(row.get("citation_metadata"), Mapping) else {}
        preview.append(
            {
                "query_id": row.get("query_id"),
                "source_searchunit_id": row.get("source_searchunit_id"),
                "diagnostic_only": row.get("diagnostic_only"),
                "score": metadata.get("score"),
                "metadata_fields_present": sorted(metadata.keys()),
                "locator_complete": locator_complete_for_row(row),
            }
        )
    return preview


def render_markdown(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    metrics = report["retrieval_evidence_metrics"]
    strict_metrics = report["strict_silver_evidence_metrics"]
    leakage = report["hidden_excluded_leakage_result"]
    guardrails = report["guardrails"]
    metadata = report["citation_metadata_completeness"]
    lines = [
        "# XLSX Strict Silver Generation Report",
        "",
        f"Status: `{report['status']}`",
        "",
        "Scope: XLSX retrieval/evidence silver generation only. Answer-generation and production promotion remain closed.",
        "",
        "## Counts",
        "",
        "| Item | Count |",
        "|---|---:|",
        f"| Input denominator rows | `{counts['input_denominator_row_count']}` |",
        f"| Generated silver rows | `{counts['generated_silver_row_count']}` |",
        f"| Excluded normalized rows | `{counts['excluded_row_count']}` |",
        f"| Pending evidence rows excluded | `{counts['pending_evidence_row_count']}` |",
        f"| Normalized hidden-negative rows excluded | `{counts['normalized_hidden_negative_row_count']}` |",
        f"| Diagnostic-only fallback rows | `{counts['diagnostic_only_fallback_row_count']}` |",
        "",
        "## Retrieval/Evidence Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Hit@10 | `{metrics.get('Hit@10')}` |",
        f"| MRR@10 | `{metrics.get('MRR@10')}` |",
        f"| XLSX citation location accuracy | `{metrics.get('xlsx_citation_location_accuracy')}` |",
        f"| target_cell_hit | `{strict_metrics.get('target_cell_hit')}` |",
        f"| target_row_hit | `{strict_metrics.get('target_row_hit')}` |",
        f"| header_included | `{strict_metrics.get('header_included')}` |",
        f"| target_column_included | `{strict_metrics.get('target_column_included')}` |",
        f"| surrounding_context_included | `{strict_metrics.get('surrounding_context_included')}` |",
        f"| sheet_resolution_accuracy | `{strict_metrics.get('sheet_resolution_accuracy')}` |",
        f"| citation locator completeness | `{metadata.get('locator_completeness')}` |",
        "",
        "## Hidden/Excluded Leakage",
        "",
        f"- Status: `{leakage.get('status')}`",
        f"- Probe target rows: `{leakage.get('probe_target_row_count')}`",
        f"- Surface leakage count: `{leakage.get('surface_leakage_count')}`",
        f"- Policy-excluded rows counted as retrieval failures: `{str(leakage.get('policy_excluded_rows_counted_as_retrieval_failures')).lower()}`",
        f"- Answer surface: `{report['surface_status']['answer']}`",
        f"- Citation surface: `{report['surface_status']['citation']}`",
        "",
        "## Artifact Decision",
        "",
        f"- Repo silver artifact written: `{str(report['silver_artifact_policy']['repo_silver_artifact_written']).lower()}`",
        f"- External silver artifact: `{report['silver_artifact_policy']['external_silver_artifact']['path']}`",
        "- Decision: no canonical XLSX strict silver artifact path exists in the repo, so the full manifest is outside the repo and this report stays compact.",
        "",
        "## Guardrails",
        "",
        "| Guardrail | Value |",
        "|---|---:|",
    ]
    for key in [
        "official_denominator_registry_changed",
        "official_denominator_opened_or_frozen",
        "xlsx_answer_generation_denominator_opened",
        "production_namespace_mutated",
        "production_vector_index_mutated",
        "production_vector_written",
        "repo_local_silver_manifest_written",
        "candidate_artifact_mutated",
        "immutable_baseline_mutated",
        "diagnostic_only_row_promoted",
        "hidden_xlsx_exposed",
        "policy_excluded_rows_counted_as_retrieval_failures",
        "route_fallback_labels_promoted_to_official_metrics",
        "pdf_content_file_lanes_aggregated",
    ]:
        lines.append(f"| {key} | `{str(guardrails[key]).lower()}` |")
    lines.extend(
        [
            "",
            "## Validation",
            "",
            f"- OK: `{str(report['validation']['ok']).lower()}`",
        ]
    )
    if report["validation"]["errors"]:
        lines.extend(f"- `{error}`" for error in report["validation"]["errors"])
    else:
        lines.append("- No guardrail errors.")
    lines.append("")
    return "\n".join(lines)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return data


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_json_object(value: Any) -> dict[str, Any]:
    parsed = parse_json_value(value)
    return parsed if isinstance(parsed, dict) else {}


def parse_json_list(value: Any) -> list[Any]:
    parsed = parse_json_value(value)
    return parsed if isinstance(parsed, list) else []


def parse_json_value(value: Any) -> Any:
    text = clean(value)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def table_title_candidate(row: Mapping[str, str]) -> str | None:
    sheet = clean(row.get("sheet"))
    table_range = clean(row.get("range"))
    if sheet and table_range:
        return f"{sheet} {table_range}"
    return sheet or None


def nearby_rows_from_values(values: Sequence[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, Mapping):
            continue
        row_text = clean(item.get("row_text"))
        if not row_text or row_text in seen:
            continue
        seen.add(row_text)
        rows.append({"row_text": row_text})
    return rows


def rows_from_range(cell_range: str) -> list[int]:
    bounds = range_bounds(cell_range)
    if not bounds:
        return []
    _start_col, start_row, _end_col, end_row = bounds
    return list(range(start_row, end_row + 1))


def columns_from_range(cell_range: str) -> list[str]:
    bounds = range_bounds(cell_range)
    if not bounds:
        return []
    start_col, _start_row, end_col, _end_row = bounds
    return column_range(start_col, end_col)


def infer_header_rows(cell_range: str, headers: Sequence[Any]) -> list[int]:
    del cell_range
    if not headers:
        return []
    return [1]


def range_bounds(cell_range: str) -> tuple[str, int, str, int] | None:
    text = clean(cell_range).upper()
    match = re.match(r"^\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?$", text)
    if not match:
        return None
    start_col = match.group(1)
    start_row = int(match.group(2))
    end_col = match.group(3) or start_col
    end_row = int(match.group(4) or match.group(2))
    if (column_number(end_col), end_row) < (column_number(start_col), start_row):
        start_col, end_col = end_col, start_col
        start_row, end_row = end_row, start_row
    return start_col, start_row, end_col, end_row


def column_range(start: str, end: str) -> list[str]:
    start_number = column_number(start)
    end_number = column_number(end)
    return [column_name(number) for number in range(start_number, end_number + 1)]


def column_number(name: str) -> int:
    value = 0
    for char in name.upper():
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value


def column_name(number: int) -> str:
    chars = []
    value = number
    while value:
        value, remainder = divmod(value - 1, 26)
        chars.append(chr(ord("A") + remainder))
    return "".join(reversed(chars))


def locator_complete_for_row(row: Mapping[str, Any]) -> bool:
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    return bool(locator.get("file") and locator.get("sheet") and locator.get("range"))


def metadata_value(row: Mapping[str, Any], field: str) -> Any:
    metadata = row.get("citation_metadata") if isinstance(row.get("citation_metadata"), Mapping) else {}
    return metadata.get(field)


def surface_status(surface_coverage: Mapping[str, Any], surface: str) -> str:
    item = surface_coverage.get(surface) if isinstance(surface_coverage.get(surface), Mapping) else {}
    return clean(item.get("status")) or "NOT_CONFIGURED"


def xlsx_answer_generation_denominator(report: Mapping[str, Any]) -> int:
    tracks = report.get("tracks") if isinstance(report.get("tracks"), Mapping) else {}
    xlsx = tracks.get("xlsx_business_structured") if isinstance(tracks.get("xlsx_business_structured"), Mapping) else {}
    try:
        return int(xlsx.get("answer_generation_denominator", 0))
    except (TypeError, ValueError):
        return -1


def nested_guardrail_flag(*payloads: Any, keys: Iterable[str]) -> bool:
    key_set = set(keys)
    return any(nested_guardrail_value(payload, key_set) for payload in payloads)


def nested_guardrail_value(value: Any, keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in keys and guardrail_value_is_true(item):
                return True
            if isinstance(item, (Mapping, list, tuple)) and nested_guardrail_value(item, keys):
                return True
    elif isinstance(value, (list, tuple)):
        return any(nested_guardrail_value(item, keys) for item in value)
    return False


def guardrail_value_is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path) if path.resolve().is_relative_to(REPO_ROOT.resolve()) else str(path.resolve()),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def ratio(count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(count / total, 3)


def int_or_none(value: Any) -> int | None:
    try:
        return int(clean(value))
    except (TypeError, ValueError):
        return None


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y", "on"}


def is_hidden_negative_row(row: Mapping[str, str]) -> bool:
    query_id = clean(row.get("query_id")).lower()
    hidden_policy = clean(row.get("hidden_policy")).lower()
    v2_status = clean(row.get("v2_label_status")).lower()
    eval_purpose = clean(row.get("eval_purpose")).lower()
    return (
        "hidden_policy" in query_id
        or hidden_policy in {"negative", "hidden_negative"}
        or v2_status == "negative_hidden_policy"
        or eval_purpose == "hidden_policy_negative"
    )


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    if isinstance(value, Mapping):
        return bool(value)
    return True


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
