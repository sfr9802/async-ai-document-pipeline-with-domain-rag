"""Run the first official answer/citation metric attempt for question-gold v2.

This runner consumes only the registry-backed question-gold v2 CSV inputs.
It validates the config, registry, registry-application report, smoke report,
and actual CSV hashes before any scoring attempt. If no official scorer/backend
is available, it writes a fail-closed BLOCKED_OR_PARTIAL report without
fabricating metric results.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"

DEFAULT_METRIC_INPUT_CONFIG = REPORT_DIR / "official_metric_input_config_v1.json"
DEFAULT_DENOMINATOR_REGISTRY = EVAL_QUERY_DIR / "official_denominator_registry.json"
DEFAULT_PRE_EXECUTION_SMOKE = REPORT_DIR / "official_metric_pre_execution_smoke_report_v1.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "official_answer_citation_metric_first_run_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "official_answer_citation_metric_first_run_v1.md"
DEFAULT_SCORER_RESULTS_JSONL_NAME = "official_answer_citation_scorer_results_v1.jsonl"
DEFAULT_PDF_GENERATION_JSONL_NAME = "pdf_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_XLSX_GENERATION_JSONL_NAME = "xlsx_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_XLSX_LEAKAGE_REPROBE_NAME = "xlsx_answer_citation_hidden_excluded_leakage_reprobe.json"
DEFAULT_TEXT_POLICY_PACKET = Path("ai/eval/review/rag_text_namu_answer_citation_policy_review_packet_v2_1.json")

SCHEMA_VERSION = "official_answer_citation_metric_first_run_v1"
REPORT_ROLE = "official_answer_citation_metric_first_run"
QUESTION_GOLD_KIND = "question_answer_citation_gold_v2"
TRACKS = ("pdf_business_ocr_mm", "text_namu_v2_1", "xlsx_business_structured")
EXPECTED_SPLIT = {"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19}
EXPECTED_TOTAL = 29
PASS_CATEGORY = "PASS"
SCORER_BACKEND_UNAVAILABLE = "SCORER_BACKEND_UNAVAILABLE"
INPUT_VALIDATION_FAILED = "INPUT_VALIDATION_FAILED"
SCORER_EXCEPTION = "SCORER_EXCEPTION"
SCORER_INVALID_RESULT = "SCORER_INVALID_RESULT"
SCORER_RESULT_MISSING = "SCORER_RESULT_MISSING"
SCORER_BACKEND_NAME = "official_deterministic_artifact_scorer"
SCORER_BACKEND_VERSION = "v1"
NULL_SCORE_FAILURE_CATEGORIES = {SCORER_EXCEPTION, SCORER_RESULT_MISSING}

ScoreFn = Callable[[Mapping[str, str]], Mapping[str, Any]]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scorer_results_jsonl_path: Path | None = None
    scorer_backend_metadata: dict[str, Any] = {}
    if args.scorer_results_jsonl:
        scorer_results_jsonl_path = Path(args.scorer_results_jsonl)
        scorer = scorer_from_results_jsonl(scorer_results_jsonl_path)
    elif args.disable_scorer_backend:
        scorer = None
    else:
        scorer_paths = resolve_scorer_backend_paths(args)
        scorer_results_jsonl_path = scorer_paths["scorer_results_output"]
        preflight_errors = input_validation_errors_before_scorer_execution(
            metric_input_config_path=Path(args.metric_input_config),
            denominator_registry_path=Path(args.denominator_registry),
            pre_execution_smoke_path=Path(args.pre_execution_smoke),
        )
        if preflight_errors:
            scorer_backend_metadata = scorer_backend_skipped_metadata(
                output_jsonl=scorer_results_jsonl_path,
                validation_errors=preflight_errors,
            )
            scorer_results_jsonl_path = None
            scorer = None
        else:
            scorer_backend_metadata = run_official_scorer_backend(
                metric_input_config_path=Path(args.metric_input_config),
                denominator_registry_path=Path(args.denominator_registry),
                pre_execution_smoke_path=Path(args.pre_execution_smoke),
                output_jsonl=scorer_results_jsonl_path,
                pdf_generation_jsonl=scorer_paths["pdf_generation_jsonl"],
                xlsx_generation_jsonl=scorer_paths["xlsx_generation_jsonl"],
                text_policy_packet=scorer_paths["text_policy_packet"],
                xlsx_leakage_reprobe=scorer_paths["xlsx_leakage_reprobe"],
            )
            scorer = scorer_from_results_jsonl(scorer_results_jsonl_path)
    report = run_first_metric(
        metric_input_config_path=Path(args.metric_input_config),
        denominator_registry_path=Path(args.denominator_registry),
        pre_execution_smoke_path=Path(args.pre_execution_smoke),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        scorer=scorer,
        scorer_results_jsonl_path=scorer_results_jsonl_path,
        scorer_backend_metadata=scorer_backend_metadata,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "official_metric_execution_started": report["official_metric_execution_started"],
                "official_metric_input_rows": report["official_input_summary"]["row_count"],
                "official_scoring_attempt_count": report["official_scoring_attempt_count"],
                "blocker_category": report.get("blocker_category"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return exit_code_for_report(report)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metric-input-config", default=str(DEFAULT_METRIC_INPUT_CONFIG))
    parser.add_argument("--denominator-registry", default=str(DEFAULT_DENOMINATOR_REGISTRY))
    parser.add_argument("--pre-execution-smoke", default=str(DEFAULT_PRE_EXECUTION_SMOKE))
    parser.add_argument(
        "--scorer-results-jsonl",
        default="",
        help=(
            "Optional official scorer output JSONL keyed by query_id. "
            "When omitted, the built-in deterministic artifact scorer writes and consumes a results JSONL."
        ),
    )
    parser.add_argument(
        "--disable-scorer-backend",
        action="store_true",
        help="Fail closed with SCORER_BACKEND_UNAVAILABLE instead of running the built-in scorer backend.",
    )
    parser.add_argument(
        "--scorer-results-output",
        default="",
        help="Output JSONL path for the built-in scorer backend. Defaults beside the first-run report inputs.",
    )
    parser.add_argument("--pdf-generation-jsonl", default="")
    parser.add_argument("--xlsx-generation-jsonl", default="")
    parser.add_argument("--text-policy-packet", default="")
    parser.add_argument("--xlsx-leakage-reprobe", default="")
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_first_metric(
    *,
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    output_report: Path,
    output_md: Path,
    scorer: ScoreFn | None = None,
    scorer_results_jsonl_path: Path | None = None,
    scorer_backend_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    report = build_report(
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        scorer=scorer,
        scorer_results_jsonl_path=scorer_results_jsonl_path,
        scorer_backend_metadata=scorer_backend_metadata,
    )
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_report(
    *,
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    scorer: ScoreFn | None = None,
    scorer_results_jsonl_path: Path | None = None,
    scorer_backend_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = read_json(metric_input_config_path)
    registry = read_json(denominator_registry_path)
    smoke = read_json(pre_execution_smoke_path)
    application_report_path = resolve_application_report_path(config, smoke)
    application = read_json(application_report_path) if application_report_path else {}

    consumed = consume_official_inputs(
        config=config,
        registry=registry,
        application=application,
        smoke=smoke,
    )
    rows = consumed["rows"]
    validation_errors = list(consumed["errors"])
    validation_warnings = list(consumed["warnings"])
    diagnostic_warnings = diagnostic_warnings_from_smoke(smoke)
    if diagnostic_warnings:
        validation_warnings.append("TEXT expected_answer support coverage has diagnostic-only potential gaps")
    if scorer is not None:
        validation_errors.extend(clean(error) for error in getattr(scorer, "load_errors", []) if clean(error))

    row_count_by_track = dict(sorted(Counter(row["_track"] for row in rows).items()))
    if len(rows) != EXPECTED_TOTAL:
        validation_errors.append(f"official input row count must be {EXPECTED_TOTAL}, got {len(rows)}")
    if row_count_by_track != EXPECTED_SPLIT:
        validation_errors.append(f"official input track split mismatch: {row_count_by_track}")
    scorer_result_ids = getattr(scorer, "result_query_ids", None) if scorer is not None else None
    if scorer_result_ids is not None:
        official_ids = {clean(row.get("query_id")) for row in rows}
        unexpected = sorted(set(scorer_result_ids) - official_ids)
        if unexpected:
            validation_errors.append("unexpected scorer result query_id values: " + ", ".join(unexpected))

    if validation_errors:
        row_results = [
            row_result_from_failure(row, category=INPUT_VALIDATION_FAILED, detail="input validation failed")
            for row in rows
        ]
        attempt_count = 0
        blocker_category = INPUT_VALIDATION_FAILED
        status = "FAIL_CLOSED_INPUT_VALIDATION"
    elif scorer is None:
        row_results = [
            row_result_from_failure(
                row,
                category=SCORER_BACKEND_UNAVAILABLE,
                detail="No official answer/citation scoring backend was configured for registry-backed question-gold v2 inputs.",
            )
            for row in rows
        ]
        attempt_count = 0
        blocker_category = SCORER_BACKEND_UNAVAILABLE
        status = "BLOCKED_OR_PARTIAL"
    else:
        row_results, attempt_count = score_rows(rows, scorer)
        blocker_category = blocker_category_from_results(row_results)
        if blocker_category:
            status = "BLOCKED_OR_PARTIAL"
        elif diagnostic_warnings:
            status = "PASS_WITH_DIAGNOSTIC_WARNINGS"
        else:
            status = "PASS"

    execution_started = attempt_count > 0
    track_aggregates = build_track_aggregates(row_results)
    overall_aggregates = build_overall_aggregates(row_results)
    skipped_or_error_rows = [
        {
            "query_id": row["query_id"],
            "track": row["track"],
            "failure_category": row["failure_category"],
            "failure_detail": row["failure_detail"],
        }
        for row in row_results
        if row["failure_category"] != PASS_CATEGORY
    ]

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": REPORT_ROLE,
        "official_metric": True,
        "official_metric_execution_started": execution_started,
        "official_scoring_attempt_count": attempt_count,
        "scored_count": overall_aggregates["scored_count"],
        "skipped_count": overall_aggregates["skipped_count"],
        "error_count": overall_aggregates["error_count"],
        "failure_category_counts": overall_aggregates["failure_category_counts"],
        "answer_score_pass_count": overall_aggregates["answer_score_pass_count"],
        "citation_support_score_pass_count": overall_aggregates["citation_support_score_pass_count"],
        "blocker_category": blocker_category,
        "tuning_run_started": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "gold_mutation": False,
        "denominator_mutation": False,
        "production_mutation": False,
        "candidate_artifact_mutation": False,
        "immutable_baseline_mutation": False,
        "production_namespace_vector_index_mutation": False,
        "production_vector_written": False,
        "cross_track_average_optimization_allowed": False,
        "cross_track_averages_computed": False,
        "winner_selection": False,
        "route_fallback_labels_policy": "diagnostic_only_not_used_for_scoring",
        "run_boundary": {
            "statement": (
                "This is an official answer/citation metric first-run report; "
                "it is not tuning and not promotion evidence."
            ),
            "not_tuning": True,
            "not_promotion_evidence": True,
            "no_threshold_changes": True,
            "no_gold_mutation": True,
            "no_denominator_mutation": True,
            "no_production_mutation": True,
            "no_cross_track_average_optimization": True,
        },
        "source_artifacts": {
            "metric_input_config": file_identity(metric_input_config_path),
            "denominator_registry": file_identity(denominator_registry_path),
            "pre_execution_smoke_report": file_identity(pre_execution_smoke_path),
            "registry_application_report": file_identity(application_report_path) if application_report_path else None,
        },
        "consumed_config": file_identity(metric_input_config_path),
        "consumed_registry": file_identity(denominator_registry_path),
        "consumed_csvs": consumed["csvs"],
        "official_input_summary": {
            "row_count": len(rows),
            "row_count_by_track": row_count_by_track,
            "expected_row_count": EXPECTED_TOTAL,
            "expected_row_count_by_track": EXPECTED_SPLIT,
            "registry_backed": True,
            "metric_lane_by_track": {
                track: consumed["csvs"].get(track, {}).get("metric_lane") for track in TRACKS
            },
        },
        "row_results": row_results,
        "track_aggregates": track_aggregates,
        "baseline_metrics": {
            "per_track": {
                track: {
                    "row_count": item["row_count"],
                    "scored_count": item["scored_count"],
                    "answer_pass_count": item["answer_score_pass_count"],
                    "citation_support_pass_count": item["citation_support_score_pass_count"],
                    "pass_count": item["pass_count"],
                    "answer_pass_rate": rate(item["answer_score_pass_count"], item["row_count"]),
                    "citation_support_pass_rate": rate(item["citation_support_score_pass_count"], item["row_count"]),
                    "pass_rate": rate(item["pass_count"], item["row_count"]),
                }
                for track, item in track_aggregates.items()
            },
            "cross_track_average": None,
            "cross_track_average_note": "not optimization, not tuning target",
        },
        "baseline_metric_policy": {
            "scope": "per-track observation only",
            "cross_track_average": "not optimization, not tuning target",
            "threshold_tuning": False,
            "winner_selection": False,
            "promotion_evidence": False,
        },
        "skipped_or_error_rows": skipped_or_error_rows,
        "diagnostic_warnings": diagnostic_warnings,
        "failure_taxonomy": failure_taxonomy(),
        "validation": {
            "ok": not validation_errors,
            "errors": sorted(dict.fromkeys(validation_errors)),
            "warnings": sorted(dict.fromkeys(validation_warnings)),
        },
        "scorer_backend": scorer_backend_metadata or {},
        "artifact_paths": {
            "report_json": "",
            "report_md": "",
            "scorer_results_jsonl": repo_relative(scorer_results_jsonl_path) if scorer_results_jsonl_path else "",
            "scorer_results_jsonl_sha256": sha256_file(scorer_results_jsonl_path)
            if scorer_results_jsonl_path and scorer_results_jsonl_path.exists()
            else None,
        },
        "next_step_recommendation": next_step_recommendation(status, blocker_category),
    }
    return report


def consume_official_inputs(
    *,
    config: Mapping[str, Any],
    registry: Mapping[str, Any],
    application: Mapping[str, Any],
    smoke: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    csvs: dict[str, dict[str, Any]] = {}

    config_artifacts = nested_mapping(config, "official_metric_input_artifacts")
    config_lanes = nested_mapping(config, "metric_lanes")
    application_artifacts = nested_mapping(application, "official_metric_input_artifacts")
    smoke_csv_checks = nested_mapping(smoke, "csv_checks")
    smoke_metric_lanes = nested_mapping(smoke, "artifact_consistency", "metric_lanes")
    registry_entries = nested_mapping(registry, "official_diagnostic_denominators")

    if config.get("official_metric_execution_started") is not False:
        errors.append("metric input config official_metric_execution_started must be false before first run")
    if config.get("tuning_run_started") is not False:
        errors.append("metric input config tuning_run_started must be false")
    if config.get("promotion_evidence") is not False:
        errors.append("metric input config promotion_evidence must be false")
    if config.get("cross_track_averages_computed") is not False:
        errors.append("metric input config cross_track_averages_computed must be false")
    if smoke.get("status") not in {
        "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS",
        "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS_WITH_DIAGNOSTIC_WARNINGS",
    }:
        errors.append(f"pre-execution smoke status is not PASS/PASS_WITH_DIAGNOSTIC_WARNINGS: {smoke.get('status')}")
    if smoke.get("official_metric_execution_started") is not False:
        errors.append("pre-execution smoke official_metric_execution_started must be false")
    errors.extend(source_guardrail_errors("metric input config", config))
    errors.extend(source_guardrail_errors("registry application report", application))
    errors.extend(source_guardrail_errors("pre-execution smoke", smoke))

    for track in TRACKS:
        artifact = as_mapping(config_artifacts.get(track)) or as_mapping(config_lanes.get(track))
        if not artifact:
            errors.append(f"{track} missing from metric input config")
            continue
        rel_path = clean(artifact.get("path") or artifact.get("csv_path") or artifact.get("candidate_path"))
        csv_path = resolve_repo_path(rel_path)
        if not csv_path.exists():
            errors.append(f"{track} CSV missing: {rel_path}")
            csv_rows: list[dict[str, str]] = []
            actual_sha = ""
        else:
            csv_rows = read_csv_rows(csv_path)
            actual_sha = sha256_file(csv_path)

        denominator_key = clean(artifact.get("denominator_key"))
        registry_entry = as_mapping(registry_entries.get(denominator_key))
        application_artifact = as_mapping(application_artifacts.get(track))
        smoke_csv = as_mapping(smoke_csv_checks.get(track))
        smoke_lane = as_mapping(smoke_metric_lanes.get(track))

        expected_sources = {
            "metric input config": clean(artifact.get("sha256")),
            "registry": clean(registry_entry.get("sha256")),
            "registry application report": clean(application_artifact.get("sha256")),
            "smoke csv_checks": clean(smoke_csv.get("sha256")),
            "smoke artifact_consistency": clean(smoke_lane.get("sha256")),
        }
        for source, expected_sha in expected_sources.items():
            if expected_sha and expected_sha != actual_sha:
                errors.append(f"{rel_path} sha256 mismatch against {source}: {actual_sha} != {expected_sha}")
            elif not expected_sha:
                errors.append(f"{rel_path} sha256 missing from {source}")

        expected_rows = {
            "metric input config": int_value(artifact.get("row_count") or artifact.get("official_metric_input_rows_current")),
            "registry": int_value(registry_entry.get("row_count") or registry_entry.get("official_metric_input_rows")),
            "registry application report": int_value(application_artifact.get("row_count")),
            "smoke csv_checks": int_value(smoke_csv.get("row_count")),
        }
        for source, expected in expected_rows.items():
            if expected and expected != len(csv_rows):
                errors.append(f"{rel_path} row count mismatch against {source}: {len(csv_rows)} != {expected}")
            elif not expected:
                errors.append(f"{rel_path} row count missing from {source}")

        if clean(registry_entry.get("denominator_kind")) != QUESTION_GOLD_KIND:
            errors.append(f"{denominator_key} denominator_kind must be {QUESTION_GOLD_KIND}")
        metric_lane = clean(artifact.get("metric_lane") or registry_entry.get("metric_lane") or smoke_csv.get("metric_lane"))
        if metric_lane != "answer_citation":
            errors.append(f"{rel_path} metric_lane must be answer_citation")
        if any(clean(row.get("track")) != track for row in csv_rows):
            errors.append(f"{rel_path} contains rows outside track {track}")
        if any(not parse_bool(row.get("official_metric_input")) for row in csv_rows):
            errors.append(f"{rel_path} all rows must keep official_metric_input=true")
        if any(parse_bool(row.get("promotion_evidence")) for row in csv_rows):
            errors.append(f"{rel_path} promotion_evidence must remain false")

        csvs[track] = {
            "path": repo_relative(csv_path),
            "row_count": len(csv_rows),
            "sha256": actual_sha,
            "denominator_key": denominator_key,
            "metric_lane": metric_lane,
        }
        for index, row in enumerate(csv_rows, start=1):
            enriched = dict(row)
            enriched["_track"] = track
            enriched["_csv_path"] = repo_relative(csv_path)
            enriched["_row_index"] = index
            rows.append(enriched)

    return {"rows": rows, "csvs": csvs, "errors": errors, "warnings": warnings}


def score_rows(rows: list[Mapping[str, Any]], scorer: ScoreFn) -> tuple[list[dict[str, Any]], int]:
    results: list[dict[str, Any]] = []
    attempts = 0
    for row in rows:
        attempts += 1
        try:
            raw_score = scorer(row)
            results.append(row_result_from_score(row, raw_score))
        except Exception as exc:  # pragma: no cover - exercised through behavior, not exception type.
            results.append(
                row_result_from_failure(
                    row,
                    category=SCORER_EXCEPTION,
                    detail=f"{type(exc).__name__}: {exc}",
                    attempted=True,
                )
            )
    return results, attempts


def row_result_from_score(row: Mapping[str, Any], score: Mapping[str, Any]) -> dict[str, Any]:
    answer_score = float_or_none(score.get("answer_score"))
    citation_raw = score.get("citation_support_score") if "citation_support_score" in score else score.get("citation_score")
    citation_score = float_or_none(citation_raw)
    raw_category = clean(score.get("failure_category"))
    score_error = scorer_result_guardrail_error(score) or score_validation_error(answer_score, citation_score, raw_category)
    category = SCORER_INVALID_RESULT if score_error else raw_category or category_from_scores(answer_score, citation_score)
    result = base_row_result(
        row,
        scoring_attempted=True,
        answer_score=answer_score,
        citation_support_score=citation_score,
        failure_category=category,
        failure_detail=score_error or clean(score.get("failure_detail")),
    )
    result.update(score_payload_fields(score))
    return result


def row_result_from_failure(
    row: Mapping[str, Any],
    *,
    category: str,
    detail: str,
    attempted: bool = False,
) -> dict[str, Any]:
    return base_row_result(
        row,
        scoring_attempted=attempted,
        answer_score=None,
        citation_support_score=None,
        failure_category=category,
        failure_detail=detail,
    )


def base_row_result(
    row: Mapping[str, Any],
    *,
    scoring_attempted: bool,
    answer_score: float | None,
    citation_support_score: float | None,
    failure_category: str,
    failure_detail: str,
) -> dict[str, Any]:
    return {
        "query_id": clean(row.get("query_id")),
        "track": clean(row.get("_track") or row.get("track")),
        "question": clean(row.get("question")),
        "csv_path": clean(row.get("_csv_path")),
        "csv_row_index": int_value(row.get("_row_index")),
        "scoring_attempted": scoring_attempted,
        "answer_score": answer_score,
        "citation_support_score": citation_support_score,
        "failure_category": failure_category,
        "failure_detail": failure_detail,
        "generated_answer": "",
        "actual_answer": "",
        "generated_citations": [],
        "retrieved_support": [],
        "scorer_backend_name": "",
        "scorer_backend_version": "",
        "scorer_backend_mode": "",
        "production_mutation": False,
        "score_details": {},
        "diagnostic_labels": {
            "route_label": first_present(row, ("route_label", "expected_route", "route")),
            "fallback_label": first_present(row, ("fallback_label", "fallback_outcome_label", "fallback_outcome")),
            "diagnostic_only": True,
        },
    }


def score_payload_fields(score: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "generated_answer": clean(score.get("generated_answer") or score.get("actual_answer")),
        "actual_answer": clean(score.get("actual_answer") or score.get("generated_answer")),
        "generated_citations": list_value(score.get("generated_citations") or score.get("generated_citation_items")),
        "retrieved_support": list_value(score.get("retrieved_support") or score.get("retrieved_evidence")),
        "scorer_backend_name": clean(score.get("scorer_backend_name")),
        "scorer_backend_version": clean(score.get("scorer_backend_version")),
        "scorer_backend_mode": clean(score.get("scorer_backend_mode")),
        "production_mutation": False,
        "score_details": as_mapping(score.get("score_details")),
    }


def build_track_aggregates(row_results: list[Mapping[str, Any]]) -> dict[str, Any]:
    aggregates: dict[str, Any] = {}
    for track in TRACKS:
        track_rows = [row for row in row_results if row.get("track") == track]
        failure_counts = Counter(clean(row.get("failure_category")) for row in track_rows)
        aggregates[track] = {
            "row_count": len(track_rows),
            "attempted_count": sum(1 for row in track_rows if row.get("scoring_attempted") is True),
            "scored_count": sum(
                1
                for row in track_rows
                if row.get("answer_score") is not None and row.get("citation_support_score") is not None
            ),
            "answer_score_pass_count": sum(1 for row in track_rows if row.get("answer_score") == 1.0),
            "citation_support_score_pass_count": sum(
                1 for row in track_rows if row.get("citation_support_score") == 1.0
            ),
            "pass_count": sum(1 for row in track_rows if row.get("failure_category") == PASS_CATEGORY),
            "error_count": sum(1 for row in track_rows if row.get("failure_category") != PASS_CATEGORY),
            "skipped_count": sum(1 for row in track_rows if row.get("scoring_attempted") is not True),
            "failure_category_counts": dict(sorted(failure_counts.items())),
        }
    return aggregates


def build_overall_aggregates(row_results: list[Mapping[str, Any]]) -> dict[str, Any]:
    failure_counts = Counter(clean(row.get("failure_category")) for row in row_results)
    return {
        "row_count": len(row_results),
        "attempted_count": sum(1 for row in row_results if row.get("scoring_attempted") is True),
        "scored_count": sum(
            1
            for row in row_results
            if row.get("answer_score") is not None and row.get("citation_support_score") is not None
        ),
        "skipped_count": sum(1 for row in row_results if row.get("scoring_attempted") is not True),
        "error_count": sum(1 for row in row_results if row.get("failure_category") != PASS_CATEGORY),
        "answer_score_pass_count": sum(1 for row in row_results if row.get("answer_score") == 1.0),
        "citation_support_score_pass_count": sum(1 for row in row_results if row.get("citation_support_score") == 1.0),
        "failure_category_counts": dict(sorted(failure_counts.items())),
    }


def blocker_category_from_results(row_results: list[Mapping[str, Any]]) -> str | None:
    categories = [clean(row.get("failure_category")) for row in row_results if row.get("failure_category") != PASS_CATEGORY]
    if not categories:
        return None
    counts = Counter(categories)
    return counts.most_common(1)[0][0]


def score_validation_error(answer_score: float | None, citation_score: float | None, category: str) -> str:
    if category in NULL_SCORE_FAILURE_CATEGORIES and answer_score is None and citation_score is None:
        return ""
    if answer_score is None:
        return "answer_score is required"
    if citation_score is None:
        return "citation_support_score is required"
    if not 0.0 <= answer_score <= 1.0:
        return f"answer_score out of range: {answer_score}"
    if not 0.0 <= citation_score <= 1.0:
        return f"citation_support_score out of range: {citation_score}"
    if category == PASS_CATEGORY and (answer_score != 1.0 or citation_score != 1.0):
        return "failure_category PASS requires answer_score=1.0 and citation_support_score=1.0"
    if category == "ANSWER_UNSUPPORTED" and answer_score == 1.0:
        return "failure_category ANSWER_UNSUPPORTED contradicts answer_score=1.0"
    if category == "CITATION_UNSUPPORTED" and citation_score == 1.0:
        return "failure_category CITATION_UNSUPPORTED contradicts citation_support_score=1.0"
    if category == "PARTIAL_OR_UNSUPPORTED" and answer_score == 1.0 and citation_score == 1.0:
        return "failure_category PARTIAL_OR_UNSUPPORTED contradicts passing scores"
    return ""


def scorer_result_guardrail_error(score: Mapping[str, Any]) -> str:
    false_only_keys = (
        "production_mutation",
        "production_namespace_vector_index_mutation",
        "production_vector_written",
        "promotion_evidence",
        "threshold_tuning",
        "tuning_run_started",
        "gold_mutation",
        "denominator_mutation",
        "candidate_artifact_mutation",
        "immutable_baseline_mutation",
        "winner_selection",
        "cross_track_averages_computed",
    )
    violations = [key for key in false_only_keys if score.get(key) is True]
    if violations:
        return "forbidden scorer result guardrail flag true: " + ", ".join(violations)
    return ""


def category_from_scores(answer_score: float | None, citation_score: float | None) -> str:
    if answer_score == 1.0 and citation_score == 1.0:
        return PASS_CATEGORY
    if answer_score == 1.0 and citation_score != 1.0:
        return "CITATION_UNSUPPORTED"
    if answer_score != 1.0 and citation_score == 1.0:
        return "ANSWER_UNSUPPORTED"
    return "PARTIAL_OR_UNSUPPORTED"


def source_guardrail_errors(label: str, payload: Mapping[str, Any]) -> list[str]:
    if not payload:
        return [f"{label} is missing or empty"]
    false_only_keys = (
        "official_metric_execution_started",
        "tuning_run_started",
        "promotion_evidence",
        "promotion_evidence_created",
        "threshold_tuning",
        "expected_answer_rewrite",
        "gold_label_rewrite",
        "gold_registry_mutation",
        "gold_mutation",
        "denominator_mutation",
        "official_denominator_inclusion_changed",
        "production_mutation",
        "production_namespace_vector_index_mutation",
        "production_vector_index_mutation",
        "production_vector_written",
        "winner_selection",
        "cross_track_optimization",
        "cross_track_averages_computed",
    )
    errors: list[str] = []
    for source in (payload, nested_mapping(payload, "guardrails")):
        for key in false_only_keys:
            if source.get(key) is True:
                errors.append(f"{label} {key} must be false")
    if payload.get("cross_track_average_optimization_allowed") is True:
        errors.append(f"{label} cross_track_average_optimization_allowed must be false")
    return sorted(dict.fromkeys(errors))


def resolve_scorer_backend_paths(args: argparse.Namespace) -> dict[str, Path]:
    report_dir = Path(args.metric_input_config).parent
    return {
        "scorer_results_output": Path(args.scorer_results_output)
        if args.scorer_results_output
        else report_dir / DEFAULT_SCORER_RESULTS_JSONL_NAME,
        "pdf_generation_jsonl": Path(args.pdf_generation_jsonl)
        if args.pdf_generation_jsonl
        else report_dir / DEFAULT_PDF_GENERATION_JSONL_NAME,
        "xlsx_generation_jsonl": Path(args.xlsx_generation_jsonl)
        if args.xlsx_generation_jsonl
        else report_dir / DEFAULT_XLSX_GENERATION_JSONL_NAME,
        "xlsx_leakage_reprobe": Path(args.xlsx_leakage_reprobe)
        if args.xlsx_leakage_reprobe
        else report_dir / DEFAULT_XLSX_LEAKAGE_REPROBE_NAME,
        "text_policy_packet": Path(args.text_policy_packet)
        if args.text_policy_packet
        else resolve_repo_path(DEFAULT_TEXT_POLICY_PACKET.as_posix()),
    }


def input_validation_errors_before_scorer_execution(
    *,
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
) -> list[str]:
    config = read_json(metric_input_config_path)
    registry = read_json(denominator_registry_path)
    smoke = read_json(pre_execution_smoke_path)
    application_report_path = resolve_application_report_path(config, smoke)
    application = read_json(application_report_path) if application_report_path else {}
    consumed = consume_official_inputs(
        config=config,
        registry=registry,
        application=application,
        smoke=smoke,
    )
    errors = list(consumed["errors"])
    rows = consumed["rows"]
    row_count_by_track = dict(sorted(Counter(row["_track"] for row in rows).items()))
    if len(rows) != EXPECTED_TOTAL:
        errors.append(f"official input row count must be {EXPECTED_TOTAL}, got {len(rows)}")
    if row_count_by_track != EXPECTED_SPLIT:
        errors.append(f"official input track split mismatch: {row_count_by_track}")
    return sorted(dict.fromkeys(clean(error) for error in errors if clean(error)))


def scorer_backend_skipped_metadata(*, output_jsonl: Path, validation_errors: Sequence[str]) -> dict[str, Any]:
    return {
        "backend_name": SCORER_BACKEND_NAME,
        "backend_version": SCORER_BACKEND_VERSION,
        "backend_mode": "deterministic_existing_generation_artifact_scoring",
        "backend_skipped_before_execution": True,
        "backend_skip_reason": "input validation failed before scorer backend execution",
        "results_jsonl": {
            "path": repo_relative(output_jsonl),
            "exists": output_jsonl.exists(),
            "sha256": None,
            "written": False,
        },
        "official_result_rows_written": 0,
        "production_mutation": False,
        "production_namespace_vector_index_mutation": False,
        "production_vector_written": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "tuning_run_started": False,
        "validation": {"ok": False, "errors": sorted(dict.fromkeys(validation_errors))},
    }


def run_official_scorer_backend(
    *,
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    output_jsonl: Path,
    pdf_generation_jsonl: Path,
    xlsx_generation_jsonl: Path,
    text_policy_packet: Path,
    xlsx_leakage_reprobe: Path,
) -> dict[str, Any]:
    config = read_json(metric_input_config_path)
    registry = read_json(denominator_registry_path)
    smoke = read_json(pre_execution_smoke_path)
    application_report_path = resolve_application_report_path(config, smoke)
    application = read_json(application_report_path) if application_report_path else {}
    consumed = consume_official_inputs(
        config=config,
        registry=registry,
        application=application,
        smoke=smoke,
    )
    rows = consumed["rows"]
    pdf_rows, pdf_errors = read_jsonl_generation_by_query_id(pdf_generation_jsonl)
    xlsx_rows, xlsx_errors = read_jsonl_generation_by_query_id(xlsx_generation_jsonl)
    text_rows, text_errors = read_text_policy_packet_by_query_id(text_policy_packet)
    xlsx_leakage = read_json(xlsx_leakage_reprobe)
    sources = {
        "pdf_business_ocr_mm": {
            "rows": pdf_rows,
            "path": pdf_generation_jsonl,
            "load_errors": pdf_errors,
            "source_kind": "pdf_answer_citation_diagnostic_review_input",
        },
        "text_namu_v2_1": {
            "rows": text_rows,
            "path": text_policy_packet,
            "load_errors": text_errors,
            "source_kind": "text_namu_policy_review_packet_user_surface",
        },
        "xlsx_business_structured": {
            "rows": xlsx_rows,
            "path": xlsx_generation_jsonl,
            "load_errors": xlsx_errors,
            "source_kind": "xlsx_answer_citation_diagnostic_review_input",
        },
    }
    result_rows = [score_official_row(row, sources=sources, xlsx_leakage=xlsx_leakage) for row in rows]
    write_jsonl(output_jsonl, result_rows)
    return {
        "backend_name": SCORER_BACKEND_NAME,
        "backend_version": SCORER_BACKEND_VERSION,
        "backend_mode": "deterministic_existing_generation_artifact_scoring",
        "results_jsonl": file_identity(output_jsonl),
        "source_artifacts": {
            "pdf_generation_jsonl": file_identity(pdf_generation_jsonl),
            "xlsx_generation_jsonl": file_identity(xlsx_generation_jsonl),
            "text_policy_packet": file_identity(text_policy_packet),
            "xlsx_leakage_reprobe": file_identity(xlsx_leakage_reprobe),
        },
        "source_load_errors": sorted(pdf_errors + xlsx_errors + text_errors),
        "official_rows_consumed": len(rows),
        "official_result_rows_written": len(result_rows),
        "production_mutation": False,
        "production_namespace_vector_index_mutation": False,
        "production_vector_written": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "tuning_run_started": False,
        "validation": {"ok": not consumed["errors"], "errors": consumed["errors"]},
    }


def score_official_row(
    row: Mapping[str, Any],
    *,
    sources: Mapping[str, Mapping[str, Any]],
    xlsx_leakage: Mapping[str, Any],
) -> dict[str, Any]:
    track = clean(row.get("_track") or row.get("track"))
    query_id = clean(row.get("query_id"))
    source = as_mapping(sources.get(track))
    source_path = source.get("path") if isinstance(source.get("path"), Path) else Path("")
    source_errors = [clean(error) for error in list_value(source.get("load_errors")) if clean(error)]
    if source_errors:
        return scorer_exception_result(
            row,
            detail=f"{track} generation artifact load failed: " + " | ".join(source_errors),
            source_path=source_path,
        )
    generation_rows = as_mapping(source.get("rows"))
    generation = as_mapping(generation_rows.get(query_id))
    if not generation:
        detail = f"{track} generation row missing in {repo_relative(source_path)}"
        if source_errors:
            detail += "; source_load_errors=" + " | ".join(source_errors)
        return scorer_exception_result(row, detail=detail, source_path=source_path)

    generated_answer = generated_answer_from_generation(track, generation)
    retrieved_support = retrieved_support_from_generation(track, generation)
    generated_citations = generated_citations_from_generation(track, generation)
    answer_pass, answer_detail = answer_supported_by_generated_answer(row, generated_answer, track)
    citation_pass, citation_detail = citation_supported_by_generation(
        row,
        generation=generation,
        generated_citations=generated_citations,
        retrieved_support=retrieved_support,
        xlsx_leakage=xlsx_leakage,
        track=track,
    )
    answer_score = 1.0 if answer_pass else 0.0
    citation_score = 1.0 if citation_pass else 0.0
    category = category_from_scores(answer_score, citation_score)
    detail_parts = [part for part in (answer_detail if not answer_pass else "", citation_detail if not citation_pass else "") if part]
    return {
        "query_id": query_id,
        "track": track,
        "question": clean(row.get("question")),
        "generated_answer": generated_answer,
        "actual_answer": generated_answer,
        "generated_citations": generated_citations,
        "retrieved_support": retrieved_support,
        "answer_score": answer_score,
        "citation_support_score": citation_score,
        "failure_category": category,
        "failure_detail": "; ".join(detail_parts),
        "scoring_attempted": True,
        "scorer_backend_name": SCORER_BACKEND_NAME,
        "scorer_backend_version": SCORER_BACKEND_VERSION,
        "scorer_backend_mode": "deterministic_existing_generation_artifact_scoring",
        "source_generation_artifact": repo_relative(source_path),
        "production_mutation": False,
        "score_details": {
            "expected_answer": clean(row.get("expected_answer")),
            "supporting_evidence": clean(row.get("supporting_evidence")),
            "answer_match_detail": answer_detail,
            "citation_match_detail": citation_detail,
            "diagnostic_route_fallback_labels_used_for_scoring": False,
            "xlsx_hidden_excluded_surface_leakage_count": xlsx_surface_leakage_count(xlsx_leakage)
            if track == "xlsx_business_structured"
            else None,
        },
    }


def scorer_exception_result(row: Mapping[str, Any], *, detail: str, source_path: Path) -> dict[str, Any]:
    return {
        "query_id": clean(row.get("query_id")),
        "track": clean(row.get("_track") or row.get("track")),
        "question": clean(row.get("question")),
        "generated_answer": "",
        "actual_answer": "",
        "generated_citations": [],
        "retrieved_support": [],
        "answer_score": None,
        "citation_support_score": None,
        "failure_category": SCORER_EXCEPTION,
        "failure_detail": detail,
        "scoring_attempted": True,
        "scorer_backend_name": SCORER_BACKEND_NAME,
        "scorer_backend_version": SCORER_BACKEND_VERSION,
        "scorer_backend_mode": "deterministic_existing_generation_artifact_scoring",
        "source_generation_artifact": repo_relative(source_path),
        "production_mutation": False,
        "score_details": {"diagnostic_route_fallback_labels_used_for_scoring": False},
    }


def generated_answer_from_generation(track: str, generation: Mapping[str, Any]) -> str:
    if track == "text_namu_v2_1":
        return extract_short_answer(
            clean(generation.get("generated_short_answer") or generation.get("suggested_extractive_answer_not_gold"))
        )
    return clean(generation.get("generated_answer") or generation.get("actual_answer") or generation.get("diagnostic_answer"))


def extract_short_answer(value: str) -> str:
    marker = "**Short answer:**"
    if marker not in value:
        return clean(value)
    tail = value.split(marker, 1)[1].strip()
    return clean(tail.split("\n\n", 1)[0])


def retrieved_support_from_generation(track: str, generation: Mapping[str, Any]) -> list[Any]:
    if track == "text_namu_v2_1":
        return list_value(generation.get("evidence_spans"))
    if track == "xlsx_business_structured":
        support: list[Any] = []
        for citation in list_value(generation.get("citation_items")):
            if isinstance(citation, Mapping) and clean(citation.get("citation_text")):
                support.append(clean(citation.get("citation_text")))
        return support
    support = []
    for key in ("matched_text", "citation_text"):
        if clean(generation.get(key)):
            support.append(clean(generation.get(key)))
    support.extend(list_value(generation.get("nearby_paragraphs")))
    return support


def generated_citations_from_generation(track: str, generation: Mapping[str, Any]) -> list[Any]:
    citations = list_value(generation.get("citation_items"))
    if citations:
        return citations
    if track == "text_namu_v2_1":
        return [
            {
                "cited_chunk_ids": list_value(generation.get("cited_chunk_ids")),
                "evidence_spans": list_value(generation.get("evidence_spans")),
            }
        ]
    locator = generation.get("citation_locator")
    return [{"citation_locator": locator}] if isinstance(locator, Mapping) else []


def answer_supported_by_generated_answer(row: Mapping[str, Any], generated_answer: str, track: str) -> tuple[bool, str]:
    expected = clean(row.get("expected_answer"))
    if not expected:
        return False, "expected_answer is empty"
    if not generated_answer:
        return False, "generated_answer is empty"
    if normalized_contains(expected, generated_answer):
        return True, "expected_answer normalized substring matched generated_answer"
    if track == "xlsx_business_structured" and numeric_tokens(expected):
        generated_compact = normalize_digits(generated_answer)
        missing = [token for token in numeric_tokens(expected) if normalize_digits(token) not in generated_compact]
        if not missing:
            return True, "expected numeric/date tokens matched generated_answer"
    return False, "generated_answer did not support expected_answer after deterministic normalization"


def citation_supported_by_generation(
    row: Mapping[str, Any],
    *,
    generation: Mapping[str, Any],
    generated_citations: Sequence[Any],
    retrieved_support: Sequence[Any],
    xlsx_leakage: Mapping[str, Any],
    track: str,
) -> tuple[bool, str]:
    locator = parse_json_mapping(row.get("citation_locator"))
    support_text = " ".join(clean(item) for item in retrieved_support)
    supporting_evidence = clean(row.get("supporting_evidence"))
    if track == "text_namu_v2_1":
        cited_ids = set(clean(item) for item in list_value(generation.get("cited_chunk_ids")) if clean(item))
        for citation in generated_citations:
            if isinstance(citation, Mapping):
                cited_ids.update(clean(item) for item in list_value(citation.get("cited_chunk_ids")) if clean(item))
        gold_ids = set(clean(item) for item in list_value(locator.get("cited_chunk_ids")) if clean(item))
        id_match = bool(gold_ids & cited_ids)
        support_match = normalized_contains(supporting_evidence, support_text)
        if id_match and support_match:
            return True, "TEXT chunk id and supporting_evidence matched"
        return False, f"TEXT citation unsupported: chunk_id_match={id_match}, supporting_evidence_match={support_match}"
    if track == "xlsx_business_structured":
        leakage_ok = xlsx_leakage_passed(xlsx_leakage)
        generation_locator = first_locator(generated_citations, generation)
        locator_match = xlsx_locator_matches(locator, generation_locator)
        support_match = (
            normalized_contains(clean(row.get("expected_answer")), support_text)
            or normalized_contains(supporting_evidence, json.dumps(generation_locator, ensure_ascii=False))
        )
        if leakage_ok and locator_match and support_match:
            return True, "XLSX locator/support matched and hidden/excluded leakage guard passed"
        return (
            False,
            "XLSX citation unsupported: "
            f"leakage_ok={leakage_ok}, locator_match={locator_match}, support_match={support_match}",
        )
    generation_locator = first_locator(generated_citations, generation)
    locator_match = pdf_locator_matches(locator, generation_locator)
    support_match = normalized_contains(supporting_evidence, support_text)
    if locator_match and support_match:
        return True, "PDF locator and supporting_evidence matched"
    return False, f"PDF citation unsupported: locator_match={locator_match}, supporting_evidence_match={support_match}"


def read_jsonl_generation_by_query_id(path: Path) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    rows, errors = read_jsonl_by_query_id(path)
    return dict(rows), errors


def read_text_policy_packet_by_query_id(path: Path) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    payload = read_json(path)
    errors: list[str] = []
    if not path.exists():
        return {}, [f"text policy packet missing: {path}"]
    if payload.get("diagnostic_only") is not True:
        errors.append("text policy packet must remain diagnostic_only=true")
    if payload.get("promotion_evidence") is True:
        errors.append("text policy packet promotion_evidence must remain false")
    rows = nested_sequence(payload, "user_review", "rows_requiring_human_decision")
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        query_id = clean(row.get("query_id"))
        if not query_id:
            errors.append(f"text policy packet row {index} missing query_id")
            continue
        if query_id in by_id:
            errors.append(f"text policy packet duplicate query_id {query_id}")
            continue
        by_id[query_id] = row
    return by_id, errors


def scorer_from_results_jsonl(path: Path) -> ScoreFn:
    results, load_errors = read_jsonl_by_query_id(path)

    def scorer(row: Mapping[str, str]) -> Mapping[str, Any]:
        query_id = clean(row.get("query_id"))
        if query_id not in results:
            return {
                "answer_score": None,
                "citation_support_score": None,
                "failure_category": SCORER_RESULT_MISSING,
                "failure_detail": f"missing scorer result for query_id {query_id}",
            }
        return results[query_id]

    setattr(scorer, "load_errors", load_errors)
    setattr(scorer, "result_query_ids", set(results))
    return scorer


def diagnostic_warnings_from_smoke(smoke: Mapping[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for row in nested_sequence(smoke, "text_support_diagnostic", "potential_support_coverage_gap"):
        warnings.append(
            {
                "query_id": clean(row.get("query_id")),
                "track": "text_namu_v2_1",
                "warning": "potential_support_coverage_gap",
                "reason": clean(row.get("reason")),
                "diagnostic_only": True,
            }
        )
    return warnings


def failure_taxonomy() -> dict[str, str]:
    return {
        PASS_CATEGORY: "Answer and citation/support scores passed according to the scorer result.",
        SCORER_BACKEND_UNAVAILABLE: "No official scorer/backend was configured; no score was fabricated.",
        INPUT_VALIDATION_FAILED: "Input config, registry, smoke, application, or CSV validation failed before scoring.",
        SCORER_EXCEPTION: "The configured scorer raised an exception for the row.",
        SCORER_INVALID_RESULT: "The scorer returned missing, out-of-range, or contradictory score fields.",
        SCORER_RESULT_MISSING: "The scorer results JSONL did not include this official query_id.",
        "ANSWER_UNSUPPORTED": "The generated answer did not support the expected answer.",
        "CITATION_UNSUPPORTED": "The generated citation/support evidence did not support the answer.",
        "PARTIAL_OR_UNSUPPORTED": "The scorer returned non-passing scores without a more specific category.",
    }


def next_step_recommendation(status: str, blocker_category: str | None) -> str:
    if blocker_category == SCORER_BACKEND_UNAVAILABLE:
        return (
            "Wire or start the official answer/citation scoring backend, then rerun this same runner; "
            "do not tune thresholds or create promotion evidence."
        )
    if status == "FAIL_CLOSED_INPUT_VALIDATION":
        return "Fix the source-of-truth consistency error, regenerate the first-run report, and do not score partial inputs."
    if status == "BLOCKED_OR_PARTIAL":
        return "Inspect failed row categories per track before any tuning or promotion discussion."
    return "Review per-track official results separately; keep tuning and promotion evidence closed."


def exit_code_for_report(report: Mapping[str, Any]) -> int:
    if report.get("status") == "FAIL_CLOSED_INPUT_VALIDATION":
        return 2
    if report.get("blocker_category") == SCORER_BACKEND_UNAVAILABLE and int_value(report.get("official_scoring_attempt_count")) == 0:
        return 3
    if report.get("status") == "BLOCKED_OR_PARTIAL":
        return 4
    return 0


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["official_input_summary"]
    lines = [
        "# Official Answer/Citation Metric First Run v1",
        "",
        f"- Status: `{report['status']}`",
        f"- Official metric execution started: `{str(report['official_metric_execution_started']).lower()}`",
        f"- Scoring attempts: `{report['official_scoring_attempt_count']}`",
        f"- Scored / skipped / error: `{report['scored_count']}` / `{report['skipped_count']}` / `{report['error_count']}`",
        f"- Answer pass count: `{report['answer_score_pass_count']}`",
        f"- Citation support pass count: `{report['citation_support_score_pass_count']}`",
        f"- Blocker category: `{report.get('blocker_category') or ''}`",
        f"- Rows consumed: `{summary['row_count']}`",
        f"- Rows by track: `{json.dumps(summary['row_count_by_track'], ensure_ascii=False, sort_keys=True)}`",
        f"- Scorer results JSONL: `{report['artifact_paths'].get('scorer_results_jsonl') or ''}`",
        f"- Tuning run started: `{str(report['tuning_run_started']).lower()}`",
        f"- Promotion evidence: `{str(report['promotion_evidence']).lower()}`",
        f"- Threshold tuning: `{str(report['threshold_tuning']).lower()}`",
        f"- Production mutation: `{str(report['production_mutation']).lower()}`",
        f"- Denominator mutation: `{str(report['denominator_mutation']).lower()}`",
        f"- Gold mutation: `{str(report['gold_mutation']).lower()}`",
        f"- Cross-track averages computed: `{str(report['cross_track_averages_computed']).lower()}`",
        "",
        "This report is not tuning and not promotion evidence. Cross-track averages are not optimization and not a tuning target.",
        "",
        "## Consumed Inputs",
        "",
        f"- Config: `{report['consumed_config']['path']}` (`{report['consumed_config']['sha256']}`)",
        f"- Registry: `{report['consumed_registry']['path']}` (`{report['consumed_registry']['sha256']}`)",
        "",
        "| Track | Rows | SHA256 |",
        "| --- | ---: | --- |",
    ]
    for track, item in report["consumed_csvs"].items():
        lines.append(f"| `{track}` | `{item['row_count']}` | `{item['sha256']}` |")
    lines.extend(
        [
            "",
            "## Per-Track Counts",
            "",
            "| Track | Rows | Attempted | Scored | Answer pass | Citation pass | Pass | Errors | Skipped |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for track, item in report["track_aggregates"].items():
        lines.append(
            f"| `{track}` | `{item['row_count']}` | `{item['attempted_count']}` | "
            f"`{item['scored_count']}` | `{item['answer_score_pass_count']}` | "
            f"`{item['citation_support_score_pass_count']}` | `{item['pass_count']}` | "
            f"`{item['error_count']}` | `{item['skipped_count']}` |"
        )
    lines.extend(["", "## Failure Categories", ""])
    for category, count in report.get("failure_category_counts", {}).items():
        lines.append(f"- `{category}`: `{count}`")
    if report["diagnostic_warnings"]:
        lines.extend(["", "## Diagnostic Warnings", ""])
        for warning in report["diagnostic_warnings"]:
            lines.append(f"- `{warning['query_id']}`: `{warning['warning']}` - `{warning['reason']}`")
    if report["skipped_or_error_rows"]:
        lines.extend(["", "## Skipped Or Error Rows", ""])
        for row in report["skipped_or_error_rows"][:20]:
            lines.append(f"- `{row['query_id']}` (`{row['track']}`): `{row['failure_category']}`")
        if len(report["skipped_or_error_rows"]) > 20:
            lines.append(f"- ... `{len(report['skipped_or_error_rows']) - 20}` more rows")
    lines.extend(["", "## Next Step", "", report["next_step_recommendation"], ""])
    return "\n".join(lines)


def resolve_application_report_path(config: Mapping[str, Any], smoke: Mapping[str, Any]) -> Path | None:
    rel = clean(nested_mapping(config, "source_artifacts").get("registry_application_report"))
    if not rel:
        rel = clean(nested_mapping(smoke, "artifact_paths").get("registry_application_report"))
    return resolve_repo_path(rel) if rel else None


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path: Path) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_jsonl_by_query_id(path: Path) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    rows: dict[str, Mapping[str, Any]] = {}
    errors: list[str] = []
    if not path.exists():
        return rows, [f"scorer results JSONL missing: {path}"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid scorer result JSON on line {line_number}: {exc}")
                continue
            if not isinstance(payload, Mapping):
                errors.append(f"scorer result line {line_number} must be a JSON object")
                continue
            query_id = clean(payload.get("query_id"))
            if not query_id:
                errors.append(f"missing scorer result query_id on line {line_number}")
                continue
            if query_id in rows:
                errors.append(f"duplicate scorer result query_id {query_id} on line {line_number}")
                continue
            rows[query_id] = payload
    return rows, errors


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_identity(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": "", "exists": False, "sha256": None}
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def nested_sequence(payload: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return []
        current = current.get(key)
    return [row for row in current if isinstance(row, Mapping)] if isinstance(current, list) else []


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def list_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None or value == "":
        return []
    return [value]


def parse_json_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    try:
        payload = json.loads(clean(value))
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def normalized_contains(expected: str, actual: str) -> bool:
    expected_norm = normalize_for_score(expected)
    actual_norm = normalize_for_score(actual)
    if not expected_norm or not actual_norm:
        return False
    return expected_norm in actual_norm


def normalize_for_score(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", clean(value)).lower()
    return "".join(char for char in normalized if char.isalnum())


def normalize_digits(value: Any) -> str:
    return "".join(re.findall(r"\d+", unicodedata.normalize("NFKC", clean(value))))


def numeric_tokens(value: Any) -> list[str]:
    normalized = unicodedata.normalize("NFKC", clean(value))
    return [token for token in re.findall(r"\d[\d,.\-/]*\d|\d", normalized) if normalize_digits(token)]


def first_locator(citations: Sequence[Any], generation: Mapping[str, Any]) -> Mapping[str, Any]:
    for citation in citations:
        if not isinstance(citation, Mapping):
            continue
        for key in ("locator", "citation_locator"):
            locator = citation.get(key)
            if isinstance(locator, Mapping):
                return locator
    locator = generation.get("citation_locator")
    if isinstance(locator, Mapping):
        return locator
    return nested_mapping(generation, "formatter_input", "citation_locator_metadata")


def pdf_locator_matches(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    if not expected or not actual:
        return False
    for key in ("search_unit_id", "page", "region_type"):
        if clean(expected.get(key)) != clean(actual.get(key)):
            return False
    expected_bbox = list_value(expected.get("bbox"))
    actual_bbox = list_value(actual.get("bbox"))
    if not expected_bbox or not actual_bbox or len(expected_bbox) != len(actual_bbox):
        return False
    return all(float_equal(expected_value, actual_value) for expected_value, actual_value in zip(expected_bbox, actual_bbox))


def xlsx_locator_matches(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    if not expected or not actual:
        return False
    for key in ("sheet", "search_unit_id", "document_version_id"):
        if clean(expected.get(key)) and clean(expected.get(key)) != clean(actual.get(key)):
            return False
    expected_cells = [clean(cell) for cell in list_value(expected.get("matched_cells")) if clean(cell)]
    actual_cells = [clean(cell) for cell in list_value(actual.get("matched_cells")) if clean(cell)]
    actual_range = clean(actual.get("range"))
    if expected_cells:
        return all(
            cell in actual_cells
            or any(cell_or_range_contains(cell, candidate) for candidate in actual_cells)
            or cell_or_range_contains(cell, actual_range)
            for cell in expected_cells
        )
    expected_range = clean(expected.get("range"))
    return bool(expected_range and (expected_range == actual_range or ranges_overlap(expected_range, actual_range)))


def cell_or_range_contains(cell: str, candidate: str) -> bool:
    if not cell or not candidate:
        return False
    if ":" not in candidate:
        return clean(cell).upper() == clean(candidate).upper()
    parsed_cell = parse_cell(cell)
    parsed_range = parse_range(candidate)
    if not parsed_cell or not parsed_range:
        return False
    col, row = parsed_cell
    min_col, min_row, max_col, max_row = parsed_range
    return min_col <= col <= max_col and min_row <= row <= max_row


def ranges_overlap(left: str, right: str) -> bool:
    left_range = parse_range(left)
    right_range = parse_range(right)
    if not left_range or not right_range:
        return False
    left_min_col, left_min_row, left_max_col, left_max_row = left_range
    right_min_col, right_min_row, right_max_col, right_max_row = right_range
    return not (
        left_max_col < right_min_col
        or right_max_col < left_min_col
        or left_max_row < right_min_row
        or right_max_row < left_min_row
    )


def parse_range(value: str) -> tuple[int, int, int, int] | None:
    parts = clean(value).upper().split(":")
    if len(parts) == 1:
        cell = parse_cell(parts[0])
        if not cell:
            return None
        col, row = cell
        return col, row, col, row
    if len(parts) != 2:
        return None
    start = parse_cell(parts[0])
    end = parse_cell(parts[1])
    if not start or not end:
        return None
    return min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1])


def parse_cell(value: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)", clean(value).upper())
    if not match:
        return None
    col = 0
    for char in match.group(1):
        col = col * 26 + ord(char) - ord("A") + 1
    return col, int(match.group(2))


def float_equal(left: Any, right: Any) -> bool:
    try:
        return abs(float(left) - float(right)) <= 0.01
    except (TypeError, ValueError):
        return clean(left) == clean(right)


def row_texts(formatter_input: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for item in list_value(formatter_input.get("nearby_rows")):
        if isinstance(item, Mapping) and clean(item.get("row_text")):
            texts.append(clean(item.get("row_text")))
    for item in list_value(formatter_input.get("row_values")):
        if isinstance(item, Mapping):
            text = clean(item.get("row_text"))
            value = clean(item.get("value"))
            if text:
                texts.append(text)
            elif value:
                texts.append(value)
    return texts


def xlsx_leakage_passed(payload: Mapping[str, Any]) -> bool:
    if not payload:
        return False
    guardrails = as_mapping(payload.get("guardrails"))
    return (
        clean(payload.get("status")) == "PASS"
        and xlsx_surface_leakage_count(payload) == 0
        and guardrails.get("hidden_excluded_content_exposed") is not True
        and guardrails.get("production_namespace_mutated") is not True
        and guardrails.get("production_vector_index_mutated") is not True
        and guardrails.get("production_vector_written") is not True
    )


def xlsx_surface_leakage_count(payload: Mapping[str, Any]) -> int:
    return max(
        int_value(nested_mapping(payload, "counts").get("surface_leakage_count")),
        int_value(nested_mapping(payload, "metrics").get("normalized_excluded_surface_leakage_count")),
    )


def rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def parse_bool(value: Any) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "y"}


def int_value(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def first_present(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = clean(row.get(key))
        if value:
            return value
    return ""


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
