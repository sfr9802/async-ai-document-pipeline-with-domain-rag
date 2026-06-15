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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"

DEFAULT_METRIC_INPUT_CONFIG = REPORT_DIR / "metric_input_v1.json"
DEFAULT_DENOMINATOR_REGISTRY = EVAL_QUERY_DIR / "official_denominator_registry.json"
DEFAULT_PRE_EXECUTION_SMOKE = REPORT_DIR / "smoke_v1.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "baseline_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "baseline_v1.md"
DEFAULT_SCORER_RESULTS_JSONL = REPORT_DIR / "scorer_v1.jsonl"

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
SCORER_EXTRA_RESULT_FIELDS = (
    "actual_answer",
    "generated_answer",
    "generated_citations",
    "retrieved_support",
    "score_details",
    "scorer_backend_mode",
    "scorer_backend_name",
    "scorer_backend_version",
)
SCORER_FALSE_ONLY_KEYS = (
    "tuning_run_started",
    "promotion_evidence",
    "threshold_tuning",
    "gold_mutation",
    "denominator_mutation",
    "production_mutation",
    "production_namespace_vector_index_mutation",
    "production_vector_written",
)
XLSX_CITATION_DIAGNOSTIC_SUBTYPE_TAXONOMY = {
    "support_cell_inside_locator_range_but_locator_too_broad": (
        "The official supporting cell falls inside the cited XLSX range, but the citation is a broad range instead "
        "of the exact cell or target row."
    ),
    "support_cell_not_in_locator_range": (
        "The official supporting cell is outside the generated citation locator range."
    ),
    "support_value_present_but_cell_address_not_precise": (
        "The support value appears in citation text, but the citation does not identify the precise support cell."
    ),
    "answer_target_column_missing": (
        "The cited XLSX row contains the target column/value, but the generated answer omitted that target field."
    ),
    "hidden_excluded_leakage": (
        "Hidden or policy-excluded XLSX content appeared on an answer/citation surface."
    ),
}

ScoreFn = Callable[[Mapping[str, str]], Mapping[str, Any]]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scorer = scorer_from_results_jsonl(Path(args.scorer_results_jsonl)) if args.scorer_results_jsonl else None
    report = run_first_metric(
        metric_input_config_path=Path(args.metric_input_config),
        denominator_registry_path=Path(args.denominator_registry),
        pre_execution_smoke_path=Path(args.pre_execution_smoke),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        scorer=scorer,
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
        default=str(DEFAULT_SCORER_RESULTS_JSONL),
        help=(
            "Official scorer output JSONL keyed by query_id. "
            "Pass an empty string only to exercise the fail-closed backend-unavailable path."
        ),
    )
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
) -> dict[str, Any]:
    report = build_report(
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        scorer=scorer,
    )
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    scorer_results_path = nested_mapping(report, "scorer_backend", "results_jsonl").get("path")
    if scorer_results_path:
        report["artifact_paths"]["scorer_results_jsonl"] = scorer_results_path
        report["artifact_paths"]["scorer_results_jsonl_sha256"] = nested_mapping(
            report, "scorer_backend", "results_jsonl"
        ).get("sha256")
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
    official_query_ids = {clean(row.get("query_id")) for row in rows}
    scorer_query_ids = set(getattr(scorer, "query_ids")) if scorer is not None and hasattr(scorer, "query_ids") else None
    if len(rows) != EXPECTED_TOTAL:
        validation_errors.append(f"official input row count must be {EXPECTED_TOTAL}, got {len(rows)}")
    if row_count_by_track != EXPECTED_SPLIT:
        validation_errors.append(f"official input track split mismatch: {row_count_by_track}")
    if scorer_query_ids is not None:
        if len(scorer_query_ids) != EXPECTED_TOTAL:
            validation_errors.append(f"scorer results row count must be {EXPECTED_TOTAL}, got {len(scorer_query_ids)}")
        missing_scorer_ids = sorted(official_query_ids - scorer_query_ids)
        extra_scorer_ids = sorted(scorer_query_ids - official_query_ids)
        if missing_scorer_ids:
            validation_errors.append(f"scorer results missing official query_ids: {missing_scorer_ids}")
        if extra_scorer_ids:
            validation_errors.append(f"scorer results contain non-official query_ids: {extra_scorer_ids}")

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
    execution_blocker_category = execution_blocker_category_from(status, blocker_category, execution_started)
    primary_failure_category = None if execution_blocker_category else blocker_category
    status_detail = status_detail_from(status, execution_blocker_category, primary_failure_category, diagnostic_warnings)
    track_aggregates = build_track_aggregates(row_results)
    failure_category_counts = dict(
        sorted(Counter(clean(row.get("failure_category")) for row in row_results).items())
    )
    scored_count = sum(
        1
        for row in row_results
        if row.get("answer_score") is not None and row.get("citation_support_score") is not None
    )
    answer_score_pass_count = sum(1 for row in row_results if row.get("answer_score") == 1.0)
    citation_support_score_pass_count = sum(1 for row in row_results if row.get("citation_support_score") == 1.0)
    error_count = sum(1 for row in row_results if row.get("failure_category") != PASS_CATEGORY)
    skipped_count = sum(1 for row in row_results if row.get("scoring_attempted") is not True)
    diagnostic_xlsx_citation_failure_subtype_counts = dict(
        sorted(
            Counter(
                clean(row.get("diagnostic_xlsx_citation_failure_subtype"))
                for row in row_results
                if clean(row.get("diagnostic_xlsx_citation_failure_subtype"))
            ).items()
        )
    )
    skipped_or_error_rows = [
        {
            "query_id": row["query_id"],
            "track": row["track"],
            "failure_category": row["failure_category"],
            "failure_detail": row["failure_detail"],
            **(
                {"diagnostic_xlsx_citation_failure_subtype": row["diagnostic_xlsx_citation_failure_subtype"]}
                if clean(row.get("diagnostic_xlsx_citation_failure_subtype"))
                else {}
            ),
        }
        for row in row_results
        if row["failure_category"] != PASS_CATEGORY
    ]
    scorer_results_path = getattr(scorer, "results_jsonl_path", None) if scorer is not None else None

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": REPORT_ROLE,
        "official_metric": True,
        "official_metric_execution_started": execution_started,
        "official_scoring_attempt_count": attempt_count,
        "blocker_category": blocker_category,
        "execution_blocker_category": execution_blocker_category,
        "primary_failure_category": primary_failure_category,
        "status_detail": status_detail,
        "scored_count": scored_count,
        "answer_score_pass_count": answer_score_pass_count,
        "citation_support_score_pass_count": citation_support_score_pass_count,
        "error_count": error_count,
        "skipped_count": skipped_count,
        "failure_category_counts": failure_category_counts,
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
        "baseline_metrics": build_baseline_metrics(track_aggregates),
        "baseline_metric_policy": {
            "scope": "per-track observation only",
            "cross_track_average": "not optimization, not tuning target",
            "threshold_tuning": False,
            "promotion_evidence": False,
            "winner_selection": False,
        },
        "skipped_or_error_rows": skipped_or_error_rows,
        "diagnostic_warnings": diagnostic_warnings,
        "failure_taxonomy": failure_taxonomy(row_results),
        "diagnostic_xlsx_citation_failure_subtype_taxonomy": XLSX_CITATION_DIAGNOSTIC_SUBTYPE_TAXONOMY,
        "diagnostic_xlsx_citation_failure_subtype_counts": diagnostic_xlsx_citation_failure_subtype_counts,
        "diagnostic_xlsx_citation_failure_subtype_policy": {
            "diagnostic_only": True,
            "official_failure_category_unchanged": True,
            "tuning_target": False,
            "threshold_tuning": False,
            "promotion_evidence": False,
        },
        "scorer_backend": scorer_backend_summary(
            scorer=scorer,
            rows=row_results,
            scorer_results_path=scorer_results_path,
        ),
        "validation": {
            "ok": not validation_errors,
            "errors": sorted(dict.fromkeys(validation_errors)),
            "warnings": sorted(dict.fromkeys(validation_warnings)),
        },
        "artifact_paths": {"report_json": "", "report_md": ""},
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
    score_error = score_validation_error(answer_score, citation_score, raw_category)
    category = (
        SCORER_INVALID_RESULT
        if score_error
        else raw_category or (PASS_CATEGORY if answer_score == 1.0 and citation_score == 1.0 else "PARTIAL_OR_UNSUPPORTED")
    )
    result = base_row_result(
        row,
        scoring_attempted=True,
        answer_score=answer_score,
        citation_support_score=citation_score,
        failure_category=category,
        failure_detail=score_error or clean(score.get("failure_detail")),
    )
    for key in SCORER_EXTRA_RESULT_FIELDS:
        if key in score:
            result[key] = score[key]
    subtype_info = xlsx_citation_diagnostic_subtype(row=row, score=score, result=result)
    if subtype_info:
        result["diagnostic_xlsx_citation_failure_subtype"] = subtype_info["subtype"]
        result["diagnostic_xlsx_citation_failure_subtype_detail"] = subtype_info["detail"]
        result["diagnostic_xlsx_citation_failure_subtype_signals"] = subtype_info["signals"]
        result["diagnostic_xlsx_citation_failure_subtype_policy"] = {
            "diagnostic_only": True,
            "official_failure_category_unchanged": True,
            "tuning_target": False,
            "threshold_tuning": False,
            "promotion_evidence": False,
        }
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
        "csv_path": clean(row.get("_csv_path")),
        "csv_row_index": int_value(row.get("_row_index")),
        "scoring_attempted": scoring_attempted,
        "answer_score": answer_score,
        "citation_support_score": citation_support_score,
        "failure_category": failure_category,
        "failure_detail": failure_detail,
        "diagnostic_labels": {
            "route_label": first_present(row, ("route_label", "expected_route", "route")),
            "fallback_label": first_present(row, ("fallback_label", "fallback_outcome_label", "fallback_outcome")),
            "diagnostic_only": True,
        },
    }


def build_track_aggregates(row_results: list[Mapping[str, Any]]) -> dict[str, Any]:
    aggregates: dict[str, Any] = {}
    for track in TRACKS:
        track_rows = [row for row in row_results if row.get("track") == track]
        failure_counts = Counter(clean(row.get("failure_category")) for row in track_rows)
        subtype_counts = Counter(
            clean(row.get("diagnostic_xlsx_citation_failure_subtype"))
            for row in track_rows
            if clean(row.get("diagnostic_xlsx_citation_failure_subtype"))
        )
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
            "error_count": sum(1 for row in track_rows if row.get("failure_category") != PASS_CATEGORY),
            "skipped_count": sum(1 for row in track_rows if row.get("scoring_attempted") is not True),
            "failure_category_counts": dict(sorted(failure_counts.items())),
            "diagnostic_xlsx_citation_failure_subtype_counts": dict(sorted(subtype_counts.items())),
        }
    return aggregates


def build_baseline_metrics(track_aggregates: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    per_track: dict[str, Any] = {}
    for track, item in track_aggregates.items():
        row_count = int_value(item.get("row_count"))
        scored_count = int_value(item.get("scored_count"))
        pass_count = int_value(nested_mapping(item, "failure_category_counts").get(PASS_CATEGORY))
        answer_pass_count = int_value(item.get("answer_score_pass_count"))
        citation_pass_count = int_value(item.get("citation_support_score_pass_count"))
        per_track[track] = {
            "row_count": row_count,
            "scored_count": scored_count,
            "pass_count": pass_count,
            "pass_rate": ratio(pass_count, row_count),
            "answer_pass_count": answer_pass_count,
            "answer_pass_rate": ratio(answer_pass_count, row_count),
            "citation_support_pass_count": citation_pass_count,
            "citation_support_pass_rate": ratio(citation_pass_count, row_count),
        }
    return {
        "per_track": per_track,
        "cross_track_average": None,
        "cross_track_average_note": "not optimization, not tuning target",
    }


def blocker_category_from_results(row_results: list[Mapping[str, Any]]) -> str | None:
    categories = [clean(row.get("failure_category")) for row in row_results if row.get("failure_category") != PASS_CATEGORY]
    if not categories:
        return None
    counts = Counter(categories)
    return counts.most_common(1)[0][0]


def execution_blocker_category_from(status: str, blocker_category: str | None, execution_started: bool) -> str | None:
    if status == "FAIL_CLOSED_INPUT_VALIDATION":
        return INPUT_VALIDATION_FAILED
    if not execution_started and blocker_category:
        return blocker_category
    return None


def status_detail_from(
    status: str,
    execution_blocker_category: str | None,
    primary_failure_category: str | None,
    diagnostic_warnings: list[Mapping[str, Any]],
) -> str:
    if execution_blocker_category == INPUT_VALIDATION_FAILED:
        return "FAIL_CLOSED_INPUT_VALIDATION"
    if execution_blocker_category == SCORER_BACKEND_UNAVAILABLE:
        return "EXECUTION_BLOCKED_SCORER_BACKEND_UNAVAILABLE"
    if primary_failure_category:
        return "SCORED_BASELINE_PARTIAL"
    if status == "PASS_WITH_DIAGNOSTIC_WARNINGS" or diagnostic_warnings:
        return "SCORED_BASELINE_PASS_WITH_DIAGNOSTIC_WARNINGS"
    return "SCORED_BASELINE_PASS"


def score_validation_error(answer_score: float | None, citation_score: float | None, category: str) -> str:
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
    return ""


def xlsx_citation_diagnostic_subtype(
    *,
    row: Mapping[str, Any],
    score: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    if clean(row.get("_track") or row.get("track")) != "xlsx_business_structured":
        return {}
    if clean(result.get("failure_category")) == PASS_CATEGORY:
        return {}

    score_details = as_mapping(score.get("score_details"))
    failure_detail = clean(result.get("failure_detail"))
    citation_match_detail = clean(score_details.get("citation_match_detail"))
    generated_citations = score.get("generated_citations")
    citation_failure_context = (
        isinstance(generated_citations, list)
        or "XLSX citation" in failure_detail
        or "XLSX citation" in citation_match_detail
        or "leakage_ok=False" in failure_detail
        or "leakage_ok=False" in citation_match_detail
    )
    if not citation_failure_context:
        return {}
    first_citation = generated_citations[0] if isinstance(generated_citations, list) and generated_citations else {}
    first_citation = first_citation if isinstance(first_citation, Mapping) else {}
    locator = as_mapping(first_citation.get("locator"))
    citation_text = clean(first_citation.get("citation_text"))
    generated_answer = clean(score.get("generated_answer"))
    expected_answer = clean(score_details.get("expected_answer") or row.get("expected_answer"))
    support_cell = first_cell_ref(score_details.get("supporting_evidence") or row.get("supporting_evidence"))
    locator_range = clean(locator.get("range"))
    matched_cells = [clean(value).upper() for value in list_value(locator.get("matched_cells"))]
    support_value_present = expected_answer_supported_by_text(expected_answer, citation_text)
    answer_value_present = expected_answer_supported_by_text(expected_answer, generated_answer)
    support_cell_inside = bool(support_cell and cell_in_any_range(support_cell, [locator_range, *matched_cells]))
    locator_is_exact_cell = bool(
        support_cell
        and (
            locator_range.upper() == support_cell
            or matched_cells == [support_cell]
            or (not matched_cells and locator_range.upper() == support_cell)
        )
    )
    leakage_count = int_value(score_details.get("xlsx_hidden_excluded_surface_leakage_count"))
    leakage_failed = "leakage_ok=False" in failure_detail or "leakage_ok=False" in citation_match_detail

    signals = {
        "supporting_evidence_cell": support_cell,
        "citation_locator_range": locator_range,
        "citation_locator_matched_cells": matched_cells,
        "support_cell_inside_locator_range": support_cell_inside,
        "locator_is_exact_support_cell": locator_is_exact_cell,
        "support_value_present_in_citation_text": support_value_present,
        "answer_score": result.get("answer_score"),
        "citation_support_score": result.get("citation_support_score"),
        "answer_value_present_in_generated_answer": answer_value_present,
        "xlsx_hidden_excluded_surface_leakage_count": leakage_count,
    }

    if leakage_count > 0 or leakage_failed:
        return subtype_result("hidden_excluded_leakage", signals)
    if result.get("answer_score") != 1.0 and support_value_present and not answer_value_present:
        return subtype_result("answer_target_column_missing", signals)
    if support_cell and not support_cell_inside:
        return subtype_result("support_cell_not_in_locator_range", signals)
    if support_cell_inside and not locator_is_exact_cell:
        return subtype_result("support_cell_inside_locator_range_but_locator_too_broad", signals)
    if support_value_present and not locator_is_exact_cell:
        return subtype_result("support_value_present_but_cell_address_not_precise", signals)
    return {}


def subtype_result(subtype: str, signals: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "subtype": subtype,
        "detail": XLSX_CITATION_DIAGNOSTIC_SUBTYPE_TAXONOMY[subtype],
        "signals": dict(signals),
    }


def expected_answer_supported_by_text(expected_answer: str, text: str) -> bool:
    expected = normalized_text(expected_answer)
    target = normalized_text(text)
    if not expected or not target:
        return False
    expected_variants = {expected, strip_expected_answer_suffix(expected)}
    expected_variants = {value for value in expected_variants if value}
    if any(value in target for value in expected_variants):
        return True
    numeric_tokens = [normalized_text(token) for token in cell_value_tokens(expected_answer)]
    if numeric_tokens and all(token in target for token in numeric_tokens):
        return True
    return False


def strip_expected_answer_suffix(value: str) -> str:
    for suffix in ("입니다", "이다", "명", "원", "개"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value


def cell_value_tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"\d{4}-\d{2}-\d{2}|\d[\d,]*", clean(value))
        if token
    ]


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


def scorer_backend_summary(
    *,
    scorer: ScoreFn | None,
    rows: list[Mapping[str, Any]],
    scorer_results_path: Path | None,
) -> dict[str, Any]:
    if scorer is None:
        return {
            "backend_name": "",
            "backend_mode": "",
            "backend_version": "",
            "official_rows_consumed": len(rows),
            "official_result_rows_written": 0,
            "source_load_errors": [],
            "results_jsonl": None,
            "tuning_run_started": False,
            "promotion_evidence": False,
            "threshold_tuning": False,
            "gold_mutation": False,
            "denominator_mutation": False,
            "production_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_written": False,
            "validation": {"ok": True, "errors": []},
        }

    scorer_query_ids = getattr(scorer, "query_ids", None)
    result_rows = len(scorer_query_ids) if scorer_query_ids is not None else sum(
        1 for row in rows if row.get("scoring_attempted") is True
    )
    backend_name = clean(getattr(scorer, "backend_name", "")) or "official_deterministic_artifact_scorer"
    backend_mode = clean(getattr(scorer, "backend_mode", "")) or "deterministic_existing_generation_artifact_scoring"
    backend_version = clean(getattr(scorer, "backend_version", "")) or "v1"
    return {
        "backend_name": backend_name,
        "backend_mode": backend_mode,
        "backend_version": backend_version,
        "official_rows_consumed": len(rows),
        "official_result_rows_written": result_rows,
        "source_load_errors": [clean(error) for error in getattr(scorer, "load_errors", []) if clean(error)],
        "results_jsonl": file_identity(scorer_results_path),
        "tuning_run_started": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "gold_mutation": False,
        "denominator_mutation": False,
        "production_mutation": False,
        "production_namespace_vector_index_mutation": False,
        "production_vector_written": False,
        "validation": {
            "ok": not bool(getattr(scorer, "load_errors", [])),
            "errors": [clean(error) for error in getattr(scorer, "load_errors", []) if clean(error)],
        },
    }


def scorer_from_results_jsonl(path: Path) -> ScoreFn:
    results, load_errors = read_jsonl_by_query_id(path)
    load_errors.extend(scorer_guardrail_errors(results))

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
    setattr(scorer, "query_ids", set(results))
    setattr(scorer, "results_jsonl_path", path)
    setattr(scorer, "results_jsonl_sha256", sha256_file(path) if path.exists() else None)
    first_result = next(iter(results.values()), {})
    setattr(scorer, "backend_name", clean(first_result.get("scorer_backend_name")))
    setattr(scorer, "backend_mode", clean(first_result.get("scorer_backend_mode")))
    setattr(scorer, "backend_version", clean(first_result.get("scorer_backend_version")))
    return scorer


def scorer_guardrail_errors(results: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    for query_id, row in sorted(results.items()):
        for key in SCORER_FALSE_ONLY_KEYS:
            if row.get(key) is True:
                errors.append(f"scorer result {query_id} {key} must be false")
        score_details = as_mapping(row.get("score_details"))
        for key in SCORER_FALSE_ONLY_KEYS:
            if score_details.get(key) is True:
                errors.append(f"scorer result {query_id} score_details.{key} must be false")
    return errors


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


def failure_taxonomy(row_results: list[Mapping[str, Any]] | None = None) -> dict[str, str]:
    taxonomy_reference = {
        PASS_CATEGORY: "Answer and citation/support scores passed according to the scorer result.",
        INPUT_VALIDATION_FAILED: "Input config, registry, smoke, application, or CSV validation failed before scoring.",
        SCORER_EXCEPTION: "The configured scorer raised an exception for the row.",
        SCORER_INVALID_RESULT: "The scorer returned missing, out-of-range, or contradictory score fields.",
        SCORER_RESULT_MISSING: "The scorer results JSONL did not include this official query_id.",
        "ANSWER_UNSUPPORTED": "The generated answer did not support the expected answer.",
        "CITATION_UNSUPPORTED": "The generated citation/support evidence did not support the answer.",
        "PARTIAL_OR_UNSUPPORTED": "The scorer returned non-passing scores without a more specific category.",
    }
    categories = {clean(row.get("failure_category")) for row in row_results or [] if clean(row.get("failure_category"))}
    if not categories:
        categories = set(taxonomy_reference)
    if SCORER_BACKEND_UNAVAILABLE in categories:
        taxonomy_reference[SCORER_BACKEND_UNAVAILABLE] = "No official scorer/backend was configured; no score was fabricated."
    return {category: taxonomy_reference.get(category, "Scorer-provided category.") for category in sorted(categories)}


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
        f"- Status detail: `{report['status_detail']}`",
        f"- Official metric execution started: `{str(report['official_metric_execution_started']).lower()}`",
        f"- Scoring attempts: `{report['official_scoring_attempt_count']}`",
        f"- Scored / skipped / error: `{report['scored_count']}` / `{report['skipped_count']}` / `{report['error_count']}`",
        f"- Answer pass count: `{report['answer_score_pass_count']}`",
        f"- Citation support pass count: `{report['citation_support_score_pass_count']}`",
        f"- Blocker category: `{report.get('blocker_category') or ''}`",
        f"- Execution blocker category: `{report.get('execution_blocker_category') or ''}`",
        f"- Primary failure category: `{report.get('primary_failure_category') or ''}`",
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
    if report.get("primary_failure_category") and not report.get("execution_blocker_category"):
        lines.extend(
            [
                "",
                "`blocker_category` is retained for schema compatibility. In this scored baseline it is not a scorer backend blocker; it is the primary scored failure category.",
            ]
        )
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
            f"`{item['citation_support_score_pass_count']}` | "
            f"`{item['failure_category_counts'].get(PASS_CATEGORY, 0)}` | "
            f"`{item['error_count']}` | `{item['skipped_count']}` |"
        )
    lines.extend(["", "## Failure Categories", ""])
    for category, count in report["failure_category_counts"].items():
        lines.append(f"- `{category}`: `{count}`")
    if report["diagnostic_xlsx_citation_failure_subtype_counts"]:
        lines.extend(["", "## XLSX Diagnostic Citation Failure Subtypes", ""])
        lines.append("Diagnostic-only subtype counts; official failure categories are unchanged.")
        lines.append("")
        for subtype, count in report["diagnostic_xlsx_citation_failure_subtype_counts"].items():
            lines.append(f"- `{subtype}`: `{count}`")
    if report["diagnostic_warnings"]:
        lines.extend(["", "## Diagnostic Warnings", ""])
        for warning in report["diagnostic_warnings"]:
            lines.append(f"- `{warning['query_id']}`: `{warning['warning']}` - `{warning['reason']}`")
    if report["skipped_or_error_rows"]:
        lines.extend(["", "## Skipped Or Error Rows", ""])
        for row in report["skipped_or_error_rows"][:20]:
            subtype = clean(row.get("diagnostic_xlsx_citation_failure_subtype"))
            suffix = f" / `{subtype}`" if subtype else ""
            lines.append(f"- `{row['query_id']}` (`{row['track']}`): `{row['failure_category']}`{suffix}")
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
    return value if isinstance(value, list) else []


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


def first_cell_ref(value: Any) -> str:
    match = re.search(r"\b([A-Z]{1,3})([1-9][0-9]*)\b", clean(value).upper())
    return match.group(0) if match else ""


def cell_in_any_range(cell_ref: str, ranges: list[str]) -> bool:
    cell = parse_cell_ref(cell_ref)
    if not cell:
        return False
    return any(cell_in_range_tuple(cell, cell_range) for cell_range in ranges if clean(cell_range))


def cell_in_range_tuple(cell: tuple[int, int], range_ref: str) -> bool:
    parsed = parse_range_ref(range_ref)
    if not parsed:
        return False
    start_col, start_row, end_col, end_row = parsed
    col, row = cell
    return start_col <= col <= end_col and start_row <= row <= end_row


def parse_cell_ref(value: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\$?([A-Z]{1,3})\$?([1-9][0-9]*)", clean(value).upper())
    if not match:
        return None
    return column_number(match.group(1)), int(match.group(2))


def parse_range_ref(value: str) -> tuple[int, int, int, int] | None:
    cleaned = clean(value).upper().replace("$", "")
    if "!" in cleaned:
        cleaned = cleaned.rsplit("!", 1)[1]
    parts = cleaned.split(":", 1)
    if len(parts) == 1:
        cell = parse_cell_ref(parts[0])
        if not cell:
            return None
        col, row = cell
        return col, row, col, row
    start = parse_cell_ref(parts[0])
    end = parse_cell_ref(parts[1])
    if not start or not end:
        return None
    start_col, start_row = start
    end_col, end_row = end
    return min(start_col, end_col), min(start_row, end_row), max(start_col, end_col), max(start_row, end_row)


def column_number(column: str) -> int:
    value = 0
    for char in column:
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value


def normalized_text(value: Any) -> str:
    return re.sub(r"[\s,.;:|()]+", "", clean(value).lower())


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
