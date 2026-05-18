"""Smoke-check registry-backed official metric inputs before execution.

This report is diagnostic/read-only. It verifies that the registry-backed
question-gold v2 CSV inputs are internally consistent before the official
answer/citation metric is run. It does not run metrics, mutate registries,
rewrite gold rows, tune thresholds, or write production vectors.
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
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"
DEFAULT_METRIC_INPUT_CONFIG = REPORT_DIR / "metric_input_v1.json"
DEFAULT_DENOMINATOR_REGISTRY = EVAL_QUERY_DIR / "official_denominator_registry.json"
DEFAULT_REGISTRY_APPLICATION_REPORT = REPORT_DIR / "official_question_gold_v2_registry_application_report.json"
DEFAULT_XLSX_LEAKAGE_REPROBE = REPORT_DIR / "xlsx_answer_citation_hidden_excluded_leakage_reprobe.json"
DEFAULT_TEXT_CORPUS = AI_WORKER_ROOT / "eval" / "corpora" / "namu-v4-structured-combined" / "rag_chunks.jsonl"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "smoke_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "smoke_v1.md"

SCHEMA_VERSION = "official_metric_pre_execution_smoke_report_v1"
TRACKS = ("pdf_business_ocr_mm", "text_namu_v2_1", "xlsx_business_structured")
QUESTION_GOLD_KIND = "question_answer_citation_gold_v2"
REQUIRED_COLUMNS = (
    "query_id",
    "question",
    "expected_answer",
    "supporting_evidence",
    "track",
    "citation_locator",
    "human_label",
    "human_review_status",
    "human_approved_gold",
    "official_denominator_current",
    "official_metric_input",
    "promotion_evidence",
    "gold_promoted",
)
PDF_REQUIRED_LOCATOR_FIELDS = ("page", "bbox", "region_type", "search_unit_id")
XLSX_REQUIRED_LOCATOR_FIELDS = ("matched_cells", "sheet", "range", "search_unit_id", "document_version_id")
TEXT_REQUIRED_LOCATOR_FIELDS = ("cited_chunk_ids",)
PDF_ALLOWED_TABLE_BBOX_GRANULARITIES = {"", "row_only", "table_only"}
PDF_ALLOWED_TABLE_REGION_TYPES = {"paragraph", "table_body"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_smoke(
        metric_input_config_path=Path(args.metric_input_config),
        denominator_registry_path=Path(args.denominator_registry),
        registry_application_report_path=Path(args.registry_application_report),
        xlsx_leakage_reprobe_path=Path(args.xlsx_leakage_reprobe),
        text_corpus_path=Path(args.text_corpus),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "official_metric_input_rows": report["official_input_summary"]["row_count"],
                "official_metric_input_rows_by_track": report["official_input_summary"]["row_count_by_track"],
                "potential_support_coverage_gap_count": len(
                    report["text_support_diagnostic"]["potential_support_coverage_gap"]
                ),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metric-input-config", default=str(DEFAULT_METRIC_INPUT_CONFIG))
    parser.add_argument("--denominator-registry", default=str(DEFAULT_DENOMINATOR_REGISTRY))
    parser.add_argument("--registry-application-report", default=str(DEFAULT_REGISTRY_APPLICATION_REPORT))
    parser.add_argument("--xlsx-leakage-reprobe", default=str(DEFAULT_XLSX_LEAKAGE_REPROBE))
    parser.add_argument("--text-corpus", default=str(DEFAULT_TEXT_CORPUS))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_smoke(
    *,
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    registry_application_report_path: Path,
    xlsx_leakage_reprobe_path: Path,
    text_corpus_path: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    config = read_json(metric_input_config_path)
    registry = read_json(denominator_registry_path)
    registry_application = read_json(registry_application_report_path)
    xlsx_leakage = read_json(xlsx_leakage_reprobe_path)

    report = build_report(
        metric_input_config=config,
        metric_input_config_path=metric_input_config_path,
        denominator_registry=registry,
        denominator_registry_path=denominator_registry_path,
        registry_application_report=registry_application,
        registry_application_report_path=registry_application_report_path,
        xlsx_leakage_reprobe=xlsx_leakage,
        xlsx_leakage_reprobe_path=xlsx_leakage_reprobe_path,
        text_corpus_path=text_corpus_path,
    )
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_report(
    *,
    metric_input_config: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry: Mapping[str, Any],
    denominator_registry_path: Path,
    registry_application_report: Mapping[str, Any],
    registry_application_report_path: Path,
    xlsx_leakage_reprobe: Mapping[str, Any],
    xlsx_leakage_reprobe_path: Path,
    text_corpus_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    registry_entries = question_gold_registry_entries(denominator_registry)
    registry_by_path = {clean(value.get("path")): (key, value) for key, value in registry_entries.items()}
    config_lanes = nested_mapping(metric_input_config, "metric_lanes")
    config_artifacts = nested_mapping(metric_input_config, "official_metric_input_artifacts")
    application_artifacts = nested_mapping(registry_application_report, "official_metric_input_artifacts")

    csv_reports: dict[str, Any] = {}
    all_rows: list[dict[str, str]] = []
    for track, artifact in sorted(application_artifacts.items()):
        if track not in TRACKS or not isinstance(artifact, Mapping):
            continue
        csv_path = REPO_ROOT / clean(artifact.get("path"))
        rows = read_csv_rows(csv_path)
        all_rows.extend(rows)
        csv_reports[track] = csv_check(
            track=track,
            path=csv_path,
            rows=rows,
            registry_by_path=registry_by_path,
            config_lane=config_lanes.get(track) if isinstance(config_lanes.get(track), Mapping) else {},
            config_artifact=config_artifacts.get(track) if isinstance(config_artifacts.get(track), Mapping) else {},
            registry_application_artifact=artifact,
        )
        errors.extend(csv_reports[track]["errors"])

    errors.extend(candidate_manifest_consistency_errors(metric_input_config, csv_reports))
    errors.extend(artifact_consistency_errors(metric_input_config, registry_application_report, csv_reports))
    official_by_track = {track: int_value(row.get("row_count")) for track, row in csv_reports.items()}
    official_total = sum(official_by_track.values())
    track_split = dict(sorted(Counter(clean(row.get("track")) for row in all_rows).items()))
    query_ids = [clean(row.get("query_id")) for row in all_rows]
    duplicate_query_ids = sorted(key for key, count in Counter(query_ids).items() if key and count > 1)
    if duplicate_query_ids:
        errors.append(f"duplicate query_id across official inputs: {', '.join(duplicate_query_ids)}")

    pdf_diagnostic = pdf_locator_diagnostic(csv_reports.get("pdf_business_ocr_mm", {}).get("rows", []))
    xlsx_diagnostic = xlsx_locator_diagnostic(
        csv_reports.get("xlsx_business_structured", {}).get("rows", []),
        xlsx_leakage_reprobe,
    )
    text_diagnostic = text_support_diagnostic(
        csv_reports.get("text_namu_v2_1", {}).get("rows", []),
        text_corpus_path=text_corpus_path,
    )
    errors.extend(pdf_diagnostic["errors"])
    errors.extend(xlsx_diagnostic["errors"])
    errors.extend(text_diagnostic["errors"])
    if text_diagnostic["potential_support_coverage_gap"]:
        warnings.append("TEXT expected_answer support coverage has diagnostic-only potential gaps")

    if official_total != 29:
        errors.append(f"registry-backed official input row count must be 29, got {official_total}")
    expected_split = {"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19}
    if official_by_track != expected_split:
        errors.append(f"registry-backed official input track split mismatch: {official_by_track}")
    if track_split != expected_split:
        errors.append(f"CSV row track split mismatch: {track_split}")

    metric_lanes = {
        track: {
            "denominator_key": csv_reports[track]["denominator_key"],
            "csv_path": csv_reports[track]["path"],
            "row_count": csv_reports[track]["row_count"],
            "sha256": csv_reports[track]["sha256"],
            "metric_lane": csv_reports[track]["metric_lane"],
        }
        for track in sorted(csv_reports)
    }
    validation_ok = not errors
    status = (
        "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS_WITH_DIAGNOSTIC_WARNINGS"
        if validation_ok and warnings
        else (
            "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS"
            if validation_ok
            else "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_FAIL_CLOSED"
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "official_metric_pre_execution_smoke",
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_execution_started": False,
        "official_metric_execution_status": "NOT_STARTED",
        "tuning_run_started": False,
        "promotion_evidence": False,
        "promotion_evidence_created": False,
        "metric_execution_readiness_status": (
            "REGISTRY_BACKED_INPUT_CONSISTENCY_SMOKE_PASS_OFFICIAL_METRIC_NOT_EXECUTED"
            if validation_ok
            else "REGISTRY_BACKED_INPUT_CONSISTENCY_SMOKE_FAIL_CLOSED"
        ),
        "source_of_truth": {
            "metric_input_config": repo_relative(metric_input_config_path),
            "denominator_registry": repo_relative(denominator_registry_path),
            "registry_application_report": repo_relative(registry_application_report_path),
        },
        "official_input_summary": {
            "row_count": official_total,
            "row_count_by_track": official_by_track,
            "query_id_count": len(query_ids),
            "query_id_unique_count": len(set(query_ids)),
            "metric_lane_by_track": {track: row["metric_lane"] for track, row in metric_lanes.items()},
            "official_metric_input_rows_registry_backed": True,
        },
        "artifact_consistency": {
            "metric_lanes": metric_lanes,
            "metric_input_config_status": clean(metric_input_config.get("status")),
            "registry_application_status": clean(registry_application_report.get("status")),
            "denominator_registry_schema_version": clean(denominator_registry.get("schema_version")),
            "registry_sha256": sha256_file(denominator_registry_path),
            "config_sha256": sha256_file(metric_input_config_path),
            "registry_application_report_sha256": sha256_file(registry_application_report_path),
        },
        "csv_checks": {
            track: {
                key: value
                for key, value in row.items()
                if key not in {"rows", "errors"}
            }
            for track, row in sorted(csv_reports.items())
        },
        "pdf_locator_diagnostic": pdf_diagnostic,
        "xlsx_locator_diagnostic": xlsx_diagnostic,
        "text_support_diagnostic": text_diagnostic,
        "guardrails": {
            "official_metric_execution_still_not_started": True,
            "official_metric_execution_started": False,
            "tuning_run_started": False,
            "promotion_evidence": False,
            "promotion_evidence_created": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_written": False,
            "gold_label_rewrite": False,
            "expected_answer_rewrite": False,
            "official_denominator_inclusion_changed": False,
            "winner_selection": False,
            "cross_track_optimization": False,
        },
        "artifact_paths": {
            "metric_input_config": repo_relative(metric_input_config_path),
            "denominator_registry": repo_relative(denominator_registry_path),
            "registry_application_report": repo_relative(registry_application_report_path),
            "xlsx_leakage_reprobe": repo_relative(xlsx_leakage_reprobe_path),
            "text_corpus": repo_relative(text_corpus_path),
            "report_json": "",
            "report_md": "",
        },
        "validation": {"ok": validation_ok, "errors": sorted(dict.fromkeys(errors)), "warnings": sorted(dict.fromkeys(warnings))},
    }


def question_gold_registry_entries(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    entries = {}
    for key, value in nested_mapping(registry, "official_diagnostic_denominators").items():
        if isinstance(value, Mapping) and clean(value.get("denominator_kind")) == QUESTION_GOLD_KIND:
            entries[clean(key)] = value
    return entries


def csv_check(
    *,
    track: str,
    path: Path,
    rows: Sequence[dict[str, str]],
    registry_by_path: Mapping[str, tuple[str, Mapping[str, Any]]],
    config_lane: Mapping[str, Any],
    config_artifact: Mapping[str, Any],
    registry_application_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    csv_sha = sha256_file(path)
    rel_path = repo_relative(path)
    fieldnames = list(rows[0].keys()) if rows else []
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing_columns:
        errors.append(f"{rel_path} missing required columns: {', '.join(missing_columns)}")
    query_ids = [clean(row.get("query_id")) for row in rows]
    duplicate_query_ids = sorted(key for key, count in Counter(query_ids).items() if key and count > 1)
    if duplicate_query_ids:
        errors.append(f"{rel_path} duplicate query_id: {', '.join(duplicate_query_ids)}")
    if any(clean(row.get("track")) != track for row in rows):
        errors.append(f"{rel_path} contains rows outside track {track}")
    official_input_count = sum(parse_bool(row.get("official_metric_input")) for row in rows)
    if official_input_count != len(rows):
        errors.append(f"{rel_path} official_metric_input true count mismatch")
    if any(parse_bool(row.get("promotion_evidence")) for row in rows):
        errors.append(f"{rel_path} promotion_evidence must remain false")
    if any(clean(row.get("human_label")) != "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE" for row in rows):
        errors.append(f"{rel_path} human_label must stay INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE")
    if any(not parse_bool(row.get("human_approved_gold")) for row in rows):
        errors.append(f"{rel_path} human_approved_gold must be true")
    registry_key, registry_entry = registry_by_path.get(rel_path, ("", {}))
    if not registry_key:
        errors.append(f"{rel_path} missing from official question-gold registry entries")
    expected_rows = int_value(registry_entry.get("row_count"))
    if expected_rows and expected_rows != len(rows):
        errors.append(f"{rel_path} row count mismatch against registry")
    if clean(registry_entry.get("sha256")) and clean(registry_entry.get("sha256")) != csv_sha:
        errors.append(f"{rel_path} sha256 mismatch against registry")
    if clean(registry_application_artifact.get("sha256")) != csv_sha:
        errors.append(f"{rel_path} sha256 mismatch against registry application report")
    if clean(config_artifact.get("sha256")) != csv_sha:
        errors.append(f"{rel_path} sha256 mismatch against metric input config")
    if clean(config_lane.get("candidate_path")) != rel_path:
        errors.append(f"{rel_path} path mismatch against metric input config lane")
    if int_value(config_lane.get("official_metric_input_rows_current")) != len(rows):
        errors.append(f"{rel_path} metric input config current row count mismatch")
    if clean(config_lane.get("denominator_key")) and clean(config_lane.get("denominator_key")) != registry_key:
        errors.append(f"{rel_path} denominator_key mismatch against registry")
    metric_lane = clean(registry_entry.get("metric_lane") or config_lane.get("metric_lane"))
    if metric_lane != "answer_citation":
        errors.append(f"{rel_path} metric_lane must be answer_citation")
    locators = [parse_locator(row) for row in rows]
    locator_parse_errors = [qid for qid, locator in zip(query_ids, locators) if locator.get("_parse_error")]
    if locator_parse_errors:
        errors.append(f"{rel_path} citation_locator parse failed: {', '.join(locator_parse_errors)}")
    locator_complete = sum(1 for locator in locators if locator and not locator.get("_parse_error"))
    if locator_complete != len(rows):
        errors.append(f"{rel_path} citation_locator completeness mismatch")
    return {
        "track": track,
        "path": rel_path,
        "row_count": len(rows),
        "query_id_unique": not duplicate_query_ids,
        "required_columns_present": not missing_columns,
        "required_columns": list(REQUIRED_COLUMNS),
        "missing_required_columns": missing_columns,
        "official_metric_input_true_count": official_input_count,
        "citation_locator_complete_count": locator_complete,
        "sha256": csv_sha,
        "denominator_key": registry_key,
        "metric_lane": metric_lane,
        "rows": list(rows),
        "errors": errors,
    }


def artifact_consistency_errors(
    metric_input_config: Mapping[str, Any],
    registry_application_report: Mapping[str, Any],
    csv_reports: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    expected_by_track = {track: int_value(row.get("row_count")) for track, row in csv_reports.items()}
    if clean(metric_input_config.get("status")) != "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED":
        errors.append("metric input config must be registry-backed and not executed")
    if metric_input_config.get("official_metric_execution_started") is not False:
        errors.append("metric input config official_metric_execution_started must be false")
    if metric_input_config.get("tuning_run_started") is not False:
        errors.append("metric input config tuning_run_started must be false")
    if metric_input_config.get("promotion_evidence") is True:
        errors.append("metric input config promotion_evidence must be false")
    if int_value(metric_input_config.get("official_metric_input_rows")) != sum(expected_by_track.values()):
        errors.append("metric input config official_metric_input_rows mismatch")
    if normalize_int_mapping(nested_mapping(metric_input_config, "official_metric_input_rows_by_track")) != expected_by_track:
        errors.append("metric input config official_metric_input_rows_by_track mismatch")
    if clean(registry_application_report.get("status")) != "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLIED":
        errors.append("registry application report must be applied")
    if registry_application_report.get("official_metric_execution_started") is not False:
        errors.append("registry application report official_metric_execution_started must be false")
    if registry_application_report.get("tuning_run_started") is not False:
        errors.append("registry application report tuning_run_started must be false")
    if registry_application_report.get("promotion_evidence") is True:
        errors.append("registry application report promotion_evidence must be false")
    if int_value(registry_application_report.get("official_metric_input_rows")) != sum(expected_by_track.values()):
        errors.append("registry application official_metric_input_rows mismatch")
    if normalize_int_mapping(nested_mapping(registry_application_report, "official_metric_input_rows_by_track")) != expected_by_track:
        errors.append("registry application official_metric_input_rows_by_track mismatch")
    return errors


def candidate_manifest_consistency_errors(
    metric_input_config: Mapping[str, Any],
    csv_reports: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    manifest_rows = [
        row for row in metric_input_config.get("candidate_manifest") or [] if isinstance(row, Mapping)
    ]
    if not manifest_rows:
        return ["metric input config candidate_manifest is required for no-rewrite smoke"]
    manifest_by_query_id = {clean(row.get("query_id")): row for row in manifest_rows}
    csv_by_query_id: dict[str, Mapping[str, str]] = {}
    for report in csv_reports.values():
        for row in report.get("rows") or []:
            if isinstance(row, Mapping):
                csv_by_query_id[clean(row.get("query_id"))] = row
    errors: list[str] = []
    missing_from_manifest = sorted(set(csv_by_query_id) - set(manifest_by_query_id))
    extra_manifest_rows = sorted(set(manifest_by_query_id) - set(csv_by_query_id))
    if missing_from_manifest:
        errors.append(f"CSV rows missing from metric input config candidate_manifest: {', '.join(missing_from_manifest)}")
    if extra_manifest_rows:
        errors.append(f"metric input config candidate_manifest rows missing from CSV inputs: {', '.join(extra_manifest_rows)}")
    for query_id in sorted(set(csv_by_query_id) & set(manifest_by_query_id)):
        csv_row = csv_by_query_id[query_id]
        manifest = manifest_by_query_id[query_id]
        for field in ("track", "question", "expected_answer", "supporting_evidence"):
            if clean(csv_row.get(field)) != clean(manifest.get(field)):
                errors.append(f"{query_id} {field} differs from metric input config candidate_manifest")
        if parse_locator(csv_row) != (manifest.get("citation_locator") if isinstance(manifest.get("citation_locator"), Mapping) else {}):
            errors.append(f"{query_id} citation_locator differs from metric input config candidate_manifest")
        if parse_bool(csv_row.get("official_metric_input")) != (manifest.get("official_metric_input") is True):
            errors.append(f"{query_id} official_metric_input differs from metric input config candidate_manifest")
        if parse_bool(csv_row.get("promotion_evidence")) != (manifest.get("promotion_evidence") is True):
            errors.append(f"{query_id} promotion_evidence differs from metric input config candidate_manifest")
    return errors


def pdf_locator_diagnostic(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    errors: list[str] = []
    table_rows: list[dict[str, Any]] = []
    incompatible_rows: list[str] = []
    complete_count = 0
    for row in rows:
        qid = clean(row.get("query_id"))
        locator = parse_locator(row)
        missing = [field for field in PDF_REQUIRED_LOCATOR_FIELDS if not locator.get(field)]
        bbox = locator.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            missing.append("bbox[4]")
        region_type = clean(locator.get("region_type"))
        granularity = clean(locator.get("bbox_granularity"))
        if not missing:
            complete_count += 1
        else:
            errors.append(f"PDF row {qid} citation locator missing: {', '.join(sorted(set(missing)))}")
        if region_type not in PDF_ALLOWED_TABLE_REGION_TYPES:
            incompatible_rows.append(qid)
        if granularity not in PDF_ALLOWED_TABLE_BBOX_GRANULARITIES:
            incompatible_rows.append(qid)
        if region_type == "table_body" or granularity in {"row_only", "table_only"}:
            table_rows.append(
                {
                    "query_id": qid,
                    "region_type": region_type,
                    "bbox_granularity": granularity or "not_set",
                    "scorer_required_fields_present": not missing,
                    "diagnostic_scorer_compatible": not missing
                    and granularity in PDF_ALLOWED_TABLE_BBOX_GRANULARITIES
                    and region_type in PDF_ALLOWED_TABLE_REGION_TYPES,
                }
            )
    if incompatible_rows:
        errors.append(f"PDF locator has unsupported table/body locator type: {', '.join(sorted(set(incompatible_rows)))}")
    return {
        "ok": not errors,
        "checked_rows": len(rows),
        "complete_locator_rows": complete_count,
        "table_bbox_locator_rows": table_rows,
        "allowed_bbox_granularity_values": sorted(PDF_ALLOWED_TABLE_BBOX_GRANULARITIES),
        "allowed_region_type_values": sorted(PDF_ALLOWED_TABLE_REGION_TYPES),
        "diagnostic_only_check": True,
        "errors": errors,
    }


def xlsx_locator_diagnostic(rows: Sequence[Mapping[str, str]], leakage: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    missing_rows: list[dict[str, Any]] = []
    official_qids = {clean(row.get("query_id")) for row in rows}
    for row in rows:
        locator = parse_locator(row)
        missing = [field for field in XLSX_REQUIRED_LOCATOR_FIELDS if not locator.get(field)]
        if missing:
            missing_rows.append({"query_id": clean(row.get("query_id")), "missing": missing})
    if missing_rows:
        errors.append("XLSX official rows missing required locator fields")
    hidden_excluded_qids = {
        clean(row.get("query_id"))
        for row in nested_sequence(leakage, "query_results")
        if row.get("hidden_negative") is True or clean(row.get("row_source")) == "normalized_excluded"
    }
    overlap = sorted(official_qids & hidden_excluded_qids)
    if overlap:
        errors.append(f"XLSX official rows overlap hidden/excluded leakage probe rows: {', '.join(overlap)}")
    surface_leakage_count = max(
        int_value(nested_mapping(leakage, "metrics").get("surface_leakage_count")),
        int_value(nested_mapping(leakage, "counts").get("surface_leakage_count")),
    )
    if clean(leakage.get("status")) != "PASS" or surface_leakage_count != 0:
        errors.append("XLSX hidden/excluded leakage reprobe must remain PASS with zero surface leakage")
    return {
        "ok": not errors,
        "checked_rows": len(rows),
        "required_locator_fields": list(XLSX_REQUIRED_LOCATOR_FIELDS),
        "complete_locator_rows": len(rows) - len(missing_rows),
        "missing_locator_rows": missing_rows,
        "hidden_excluded_leakage_reprobe_status": clean(leakage.get("status")),
        "hidden_excluded_surface_leakage_count": surface_leakage_count,
        "official_hidden_excluded_query_overlap": overlap,
        "errors": errors,
    }


def text_support_diagnostic(rows: Sequence[Mapping[str, str]], *, text_corpus_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    chunk_ids_by_query: dict[str, list[str]] = {}
    target_chunk_ids: set[str] = set()
    for row in rows:
        qid = clean(row.get("query_id"))
        locator = parse_locator(row)
        cited_chunk_ids = [clean(value) for value in locator.get("cited_chunk_ids") or [] if clean(value)]
        chunk_ids_by_query[qid] = cited_chunk_ids
        target_chunk_ids.update(cited_chunk_ids)
        if not cited_chunk_ids:
            errors.append(f"TEXT row {qid} missing cited_chunk_ids")
    chunk_text_by_id = load_chunk_texts(text_corpus_path, target_chunk_ids)
    missing_chunk_ids = sorted(target_chunk_ids - set(chunk_text_by_id))
    if missing_chunk_ids:
        errors.append(f"TEXT cited_chunk_ids missing from corpus: {', '.join(missing_chunk_ids)}")

    potential_gaps: list[dict[str, Any]] = []
    for row in rows:
        qid = clean(row.get("query_id"))
        cited_chunk_ids = chunk_ids_by_query.get(qid, [])
        combined_text = " ".join(chunk_text_by_id.get(chunk_id, "") for chunk_id in cited_chunk_ids)
        expected_answer = clean(row.get("expected_answer"))
        supporting_evidence = clean(row.get("supporting_evidence"))
        expected_in_chunks = normalized_contains(combined_text, expected_answer)
        supporting_in_chunks = normalized_contains(combined_text, supporting_evidence)
        if expected_answer and not expected_in_chunks:
            potential_gaps.append(
                {
                    "query_id": qid,
                    "cited_chunk_ids": cited_chunk_ids,
                    "reason": "expected_answer_not_exactly_covered_by_cited_chunk_text_after_normalization",
                    "supporting_evidence_covered_by_cited_chunk_text": supporting_in_chunks,
                    "diagnostic_only": True,
                }
            )
    return {
        "ok": not errors,
        "checked_rows": len(rows),
        "text_corpus_path": repo_relative(text_corpus_path),
        "cited_chunk_id_count": len(target_chunk_ids),
        "cited_chunk_ids_found": len(chunk_text_by_id),
        "missing_cited_chunk_ids": missing_chunk_ids,
        "potential_support_coverage_gap": potential_gaps,
        "diagnostic_only_check": True,
        "errors": errors,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["official_input_summary"]
    lines = [
        "# Official Metric Pre-Execution Smoke Report v1",
        "",
        f"- Status: `{report['status']}`",
        f"- Registry-backed official input rows: `{summary['row_count']}`",
        f"- Rows by track: `{json.dumps(summary['row_count_by_track'], ensure_ascii=False, sort_keys=True)}`",
        f"- Official metric execution started: `{str(report['official_metric_execution_started']).lower()}`",
        f"- Tuning run started: `{str(report['tuning_run_started']).lower()}`",
        f"- Promotion evidence: `{str(report['promotion_evidence']).lower()}`",
        f"- Validation ok: `{str(report['validation']['ok']).lower()}`",
        f"- TEXT potential support coverage gaps: `{len(report['text_support_diagnostic']['potential_support_coverage_gap'])}`",
        "",
        "## CSV Inputs",
        "",
        "| Track | Rows | SHA256 | Denominator key | Metric lane |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for track, row in sorted(report["csv_checks"].items()):
        lines.append(
            f"| `{track}` | `{row['row_count']}` | `{row['sha256']}` | `{row['denominator_key']}` | `{row['metric_lane']}` |"
        )
    lines.extend(["", "## Validation", ""])
    if report["validation"]["errors"]:
        lines.extend(f"- ERROR: `{error}`" for error in report["validation"]["errors"])
    else:
        lines.append("- `PASS`")
    if report["validation"]["warnings"]:
        lines.extend(["", "## Diagnostic Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in report["validation"]["warnings"])
    lines.extend(
        [
            "",
            "Official metric execution still not started, tuning still not started, promotion evidence not created.",
        ]
    )
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_locator(row: Mapping[str, str]) -> dict[str, Any]:
    raw = clean(row.get("citation_locator"))
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"_parse_error": str(exc)}
    return payload if isinstance(payload, dict) else {"_parse_error": "citation_locator is not an object"}


def load_chunk_texts(path: Path, target_ids: set[str]) -> dict[str, str]:
    if not target_ids or not path.exists():
        return {}
    found: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, Mapping):
                continue
            chunk_id = clean(payload.get("chunk_id") or payload.get("id"))
            if chunk_id in target_ids:
                found[chunk_id] = clean(payload.get("chunk_text") or payload.get("text") or payload.get("content"))
                if len(found) == len(target_ids):
                    break
    return found


def normalized_contains(haystack: str, needle: str) -> bool:
    normalized_haystack = normalize_text(haystack)
    normalized_needle = normalize_text(needle)
    return bool(normalized_needle) and normalized_needle in normalized_haystack


def normalize_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣ぁ-ゟ゠-ヿ一-龯]+", "", clean(value)).lower()


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


def normalize_int_mapping(payload: Mapping[str, Any]) -> dict[str, int]:
    return {clean(key): int_value(value) for key, value in payload.items() if clean(key)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(value: Any) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "y"}


def int_value(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
