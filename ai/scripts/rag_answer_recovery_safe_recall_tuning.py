"""Run report-only safe recall tuning after narrow answer recovery calibration.

This script consumes existing diagnostic answer recovery artifacts and evaluates
small deterministic policy variants. It does not run broad indexing, mutate
production indexes, open official answer denominators, train on frozen gold, or
promote any production profile.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rag_answer_recovery_narrow_calibration as narrow  # noqa: E402
import rag_answer_recovery_report_artifacts as report_artifacts  # noqa: E402

AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "answer_recovery_safe_recall_tuning.yaml"
DEFAULT_REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"

TEXT = "TEXT"
XLSX = "XLSX"
PDF_CONTENT = "PDF_CONTENT"
PDF_FILE_LOOKUP = "PDF_FILE_LOOKUP"
OCR_SHADOW = "OCR_SHADOW"
IDP_SHADOW = "IDP_SHADOW"
MULTIMODAL_SHADOW = "MULTIMODAL_SHADOW"
SHADOW_LANES = {OCR_SHADOW, IDP_SHADOW, MULTIMODAL_SHADOW}

SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
NEEDS_RECOVERY = "NEEDS_RECOVERY"
NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"

PDF_FILE_HARD_NEGATIVE_BLOCKS = {
    "PDF_FILE_HARD_NEGATIVE_IDENTITY",
    "PDF_FILE_IDENTITY_MISMATCH",
    "PDF_FILE_DOCUMENT_VERSION_ID_MISMATCH",
    "PDF_FILE_SOURCE_FILE_ID_MISMATCH",
}
PDF_FILE_AMBIGUOUS_BLOCKS = {
    "PDF_FILE_GENERIC_FILENAME_AMBIGUOUS",
}
PDF_FILE_CONTENT_CLAIM_KEYS = ("content", "page", "bbox", "table", "row", "column", "value")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config)
    report_dir = resolve_path(args.reports_dir or DEFAULT_REPORT_DIR)
    report_dir.mkdir(parents=True, exist_ok=True)
    config = report_artifacts.with_reporting_overrides(
        load_config(config_path),
        report_artifacts.reporting_overrides_from_args(args),
    )
    payload = run_safe_recall_tuning(config=config, config_path=config_path, report_dir=report_dir)
    write_outputs(config, payload)
    selected = payload["tuning_report"]["selected_policy"]
    print(
        json.dumps(
            {
                "status": payload["tuning_report"]["status"],
                "selected_variant": selected["variant_name"],
                "wrongly_supported_count": selected["counts"]["wrongly_supported_count"],
                "recovered_after_loop": selected["counts"]["recovered_after_loop"],
                "production_promotion_ready": selected["production_promotion_ready"],
                "official_answer_denominator_ready": selected["official_answer_denominator_ready"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORT_DIR))
    report_artifacts.add_reporting_args(parser)
    return parser.parse_args(argv)


def run_safe_recall_tuning(
    *,
    config: Mapping[str, Any],
    config_path: Path,
    report_dir: Path,
) -> dict[str, Any]:
    validation_errors = validate_config(config)
    if validation_errors:
        raise ValueError("Unsafe safe-recall tuning config: " + "; ".join(validation_errors))

    ensure_narrow_artifacts(config)
    expanded_report_path = resolve_path(config["diagnostic_inputs"]["answer_sufficiency_expanded_report"])
    expanded = read_json(expanded_report_path)
    case_results = expanded["case_results"]
    selection_case_results, excluded_frozen_rows = split_selection_rows(case_results, config)
    source_violations = source_guardrail_violations(case_results, config)
    baseline_variant = baseline_variant_from_config(config)
    full_baseline = variant_metrics(case_results, baseline_variant, baseline_counts=None)
    full_baseline["accepted"] = True
    full_baseline["rejection_reasons"] = []
    selection_baseline = variant_metrics(selection_case_results, baseline_variant, baseline_counts=None)
    selection_baseline["accepted"] = True
    selection_baseline["rejection_reasons"] = []

    source_artifacts = build_source_artifact_proof(config)
    guardrails = build_guardrail_status(config)
    official_diff = official_registry_diff_proof()
    guardrails["official_denominator_registry_changed"] = official_diff["changed"]

    baseline_report = build_baseline_report(
        config=config,
        config_path=config_path,
        expanded_report_path=expanded_report_path,
        baseline=full_baseline,
        source_artifacts=source_artifacts,
        guardrails=guardrails,
        official_diff=official_diff,
        source_violations=source_violations,
        excluded_frozen_rows=excluded_frozen_rows,
    )
    missed_analysis = build_missed_analysis(case_results, baseline=full_baseline, config=config)

    variants: list[dict[str, Any]] = []
    for variant in config["variants"]:
        metrics = variant_metrics(case_results, variant, baseline_counts=full_baseline)
        selection_metrics = variant_metrics(selection_case_results, variant, baseline_counts=selection_baseline)
        metrics["selection_metrics"] = selection_metrics
        metrics["excluded_frozen_gold_row_count"] = len(excluded_frozen_rows)
        metrics["rejection_reasons"] = rejection_reasons(
            metrics,
            variant,
            full_baseline,
            config,
            selection_metrics=selection_metrics,
            selection_baseline=selection_baseline,
            source_violations=source_violations,
        )
        metrics["accepted"] = not metrics["rejection_reasons"] and not official_diff["changed"]
        metrics["recovered_after_loop_delta_vs_baseline"] = (
            metrics["counts"]["recovered_after_loop"] - full_baseline["counts"]["recovered_after_loop"]
        )
        metrics["citation_coverage_delta_vs_baseline"] = round(
            metrics["counts"]["citation_coverage_after"] - full_baseline["counts"]["citation_coverage_after"],
            6,
        )
        metrics["selection_recovered_after_loop_delta_vs_baseline"] = (
            selection_metrics["counts"]["recovered_after_loop"] - selection_baseline["counts"]["recovered_after_loop"]
        )
        metrics["selection_citation_coverage_delta_vs_baseline"] = round(
            selection_metrics["counts"]["citation_coverage_after"]
            - selection_baseline["counts"]["citation_coverage_after"],
            6,
        )
        metrics["lane_level_recovery_deltas"] = lane_recovery_deltas(metrics, full_baseline)
        variants.append(metrics)

    selected = select_variant(variants, selection_baseline)
    if official_diff["changed"]:
        selected = dict(selected)
        selected["accepted"] = False
        selected["rejection_reasons"] = [
            *selected.get("rejection_reasons", []),
            "official_denominator_registry_changed",
        ]

    selected_policy = build_selected_policy(selected, config, guardrails)
    decision_ready = selected_policy["diagnostic_only"] and not official_diff["changed"] and not source_violations
    tuning_report = {
        "schema_version": "answer_recovery_safe_recall_tuning_report_v1",
        "status": "PASS" if decision_ready else "BLOCKED",
        "config_path": repo_relative(config_path),
        "mode": config["mode"],
        "scope": {
            "broad_tuning": False,
            "production_promotion": False,
            "official_answer_denominator_opening": False,
            "production_index_mutation": False,
            "broad_indexing": False,
            "frozen_gold_selection_or_training": False,
        },
        "decision": {
            "selected_variant": selected_policy["variant_name"],
            "reason": selection_reason(selected, full_baseline),
            "production_promotion_ready": False,
            "official_answer_denominator_ready": False,
        },
        "selected_policy": selected_policy,
        "baseline_counts": full_baseline["counts"],
        "selection_baseline_counts": selection_baseline["counts"],
        "selection_excluded_frozen_gold_row_count": len(excluded_frozen_rows),
        "selection_excluded_frozen_gold_rows": excluded_frozen_rows,
        "source_guardrail_violations": source_violations,
        "variants": variants,
        "rejected_variants": [
            {"variant_name": row["variant_name"], "rejection_reasons": row["rejection_reasons"]}
            for row in variants
            if row["variant_name"] != selected["variant_name"] or row["rejection_reasons"]
        ],
        "guardrail_status": guardrails,
        "official_denominator_registry_diff_proof": official_diff,
        "frozen_gold_proof": frozen_gold_proof(config, excluded_frozen_rows),
        "missed_analysis_path": repo_relative(resolve_path(config["report_paths"]["missed_analysis_json"])),
        "baseline_path": repo_relative(resolve_path(config["report_paths"]["baseline_json"])),
    }
    return {
        "baseline_report": baseline_report,
        "missed_analysis": missed_analysis,
        "tuning_report": tuning_report,
        "selected_policy": selected_policy,
    }


def validate_config(config: Mapping[str, Any]) -> list[str]:
    errors: list[str] = report_artifacts.validate_reporting_config(config)
    knobs = config.get("allowed_tuning_knobs", {})
    if int(knobs.get("max_loop_iterations", 0)) > 2:
        errors.append("max_loop_iterations must remain <= 2")
    if int(knobs.get("max_query_rewrites", 0)) > 3:
        errors.append("max_query_rewrites must remain <= 3")
    for blocked_key in (
        "production_profile_changes",
        "official_denominator_changes",
        "broad_indexing",
        "frozen_gold_selection_or_training",
    ):
        if bool(knobs.get(blocked_key, False)):
            errors.append(f"{blocked_key} must remain false")
    if config.get("excluded_frozen_gold_ids", {}).get("use_for_selection") is not False:
        errors.append("frozen gold use_for_selection must remain false")
    if config.get("excluded_frozen_gold_ids", {}).get("use_for_training") is not False:
        errors.append("frozen gold use_for_training must remain false")
    for variant in config.get("variants", []):
        errors.extend(static_variant_rejections(variant, config))
    return errors


def split_selection_rows(
    case_results: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], list[dict[str, str]]]:
    excluded_sources = set(config.get("excluded_frozen_gold_ids", {}).get("source_files", []))
    selection_rows: list[Mapping[str, Any]] = []
    excluded_rows: list[dict[str, str]] = []
    for row in case_results:
        source_artifact = str(row.get("source_artifact", ""))
        if source_artifact in excluded_sources:
            excluded_rows.append(
                {
                    "case_id": str(row.get("case_id", "")),
                    "lane": str(row.get("lane", "")),
                    "case_type": str(row.get("case_type", "")),
                    "source_artifact": source_artifact,
                }
            )
        else:
            selection_rows.append(row)
    return selection_rows, excluded_rows


def source_guardrail_violations(
    case_results: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    max_iterations = int(config["allowed_tuning_knobs"]["max_loop_iterations"])
    max_rewrites = int(config["allowed_tuning_knobs"]["max_query_rewrites"])
    violations: list[dict[str, Any]] = []
    for row in case_results:
        loop_result = row.get("loop_result")
        if not loop_result:
            continue
        loop_iterations = int(loop_result.get("loop_iterations", 0))
        query_rewrites = int(loop_result.get("query_rewrite_count", 0))
        if loop_iterations > max_iterations:
            violations.append(
                {
                    "case_id": row.get("case_id"),
                    "field": "loop_iterations",
                    "observed": loop_iterations,
                    "cap": max_iterations,
                }
            )
        if query_rewrites > max_rewrites:
            violations.append(
                {
                    "case_id": row.get("case_id"),
                    "field": "query_rewrite_count",
                    "observed": query_rewrites,
                    "cap": max_rewrites,
                }
            )
    return violations


def variant_metrics(
    case_results: Sequence[Mapping[str, Any]],
    variant: Mapping[str, Any],
    baseline_counts: Mapping[str, Any] | None,
) -> dict[str, Any]:
    lane_breakdown: dict[str, dict[str, int]] = {}
    before_coverages: list[float] = []
    after_coverages: list[float] = []
    loop_iterations: list[int] = []
    counts = Counter()
    recovered_case_ids: list[str] = []
    opportunity_case_ids: list[str] = []

    for row in case_results:
        before = transform_decision(row, row["before_decision"], variant)
        after = transform_decision(row, row["after_decision"], variant)
        lane = row["lane"]
        expected_support = bool(row.get("expected_official_support_allowed"))
        item = lane_breakdown.setdefault(
            lane,
            {
                "total": 0,
                "initially_supported": 0,
                "supported_after_recovery": 0,
                "recovered_after_loop": 0,
                "wrongly_supported": 0,
                "unsupported_correctly_blocked": 0,
                "clarification_needed": 0,
            },
        )
        item["total"] += 1
        initially_supported = before["sufficiency_status"] == SUPPORTED
        if initially_supported:
            item["initially_supported"] += 1
            counts["initially_supported"] += 1

        opportunity_by_variant = recoverable_by_variant(row, before, after, variant)
        if opportunity_by_variant:
            opportunity_case_ids.append(str(row["case_id"]))
        recovered_by_variant, recovered_after = actual_safe_recovery_decision(row, after, variant)
        if recovered_by_variant:
            after = recovered_after
            recovered_case_ids.append(str(row["case_id"]))

        if after["sufficiency_status"] == SUPPORTED:
            item["supported_after_recovery"] += 1
        if after["sufficiency_status"] == SUPPORTED and not expected_support:
            item["wrongly_supported"] += 1
            counts["wrongly_supported_count"] += 1
        if after["sufficiency_status"] != SUPPORTED and not expected_support:
            item["unsupported_correctly_blocked"] += 1
            counts["unsupported_correctly_blocked_count"] += 1
        if row["route"]["action"] == "ASK_CLARIFICATION" or after["sufficiency_status"] == NEEDS_CLARIFICATION:
            item["clarification_needed"] += 1
            counts["clarification_needed_count"] += 1

        recovered_after_loop = bool(row.get("loop_result") and after["sufficiency_status"] == SUPPORTED)
        if recovered_by_variant and not initially_supported:
            recovered_after_loop = True
        if recovered_after_loop:
            item["recovered_after_loop"] += 1
            counts["recovered_after_loop"] += 1

        loop_result = row.get("loop_result")
        if loop_result:
            loop_iterations.append(int(loop_result["loop_iterations"]))
        before_coverages.append(float(before.get("citation_coverage", 0.0)))
        after_coverages.append(float(after.get("citation_coverage", 0.0)))
        if is_hidden_xlsx_case(row) and after["sufficiency_status"] != SUPPORTED:
            counts["hidden_xlsx_surface_attempt_count"] += 1
        if is_pdf_file_content_mixing_case(row) and after["sufficiency_status"] != SUPPORTED:
            counts["pdf_file_lookup_content_mixing_attempt_count"] += 1
        counts["diagnostic_only_evidence_blocked_count"] += diagnostic_only_block_increment(row, before, after)

    metrics = {
        "variant_name": variant["name"],
        "base_policy": variant.get("base_policy", "calibrated_identity_exact_v1"),
        "enabled_lanes": list(variant.get("enabled_lanes", [])),
        "pdf_file_identity_exactness_rule": variant.get(
            "pdf_file_identity_exactness_rule", "exact_or_canonical_identity_required"
        ),
        "filename_token_overlap_support": bool(variant.get("filename_token_overlap_support", False)),
        "hidden_xlsx_blocking": variant.get("hidden_xlsx_blocking", "enabled"),
        "diagnostic_only_support": variant.get("diagnostic_only_support", "disabled"),
        "max_loop_iterations": max_loop_iterations(variant),
        "max_query_rewrites": max_query_rewrites(variant),
        "total_evaluated": len(case_results),
        "counts": {
            "total_evaluated": len(case_results),
            "initially_supported": counts["initially_supported"],
            "recovered_after_loop": counts["recovered_after_loop"],
            "wrongly_supported_count": counts["wrongly_supported_count"],
            "unsupported_correctly_blocked_count": counts["unsupported_correctly_blocked_count"],
            "clarification_needed_count": counts["clarification_needed_count"],
            "hidden_xlsx_surface_attempt_count": counts["hidden_xlsx_surface_attempt_count"],
            "pdf_file_lookup_content_mixing_attempt_count": counts["pdf_file_lookup_content_mixing_attempt_count"],
            "diagnostic_only_evidence_blocked_count": counts["diagnostic_only_evidence_blocked_count"],
            "citation_coverage_before": average(before_coverages),
            "citation_coverage_after": average(after_coverages),
            "average_loop_iterations": average(loop_iterations),
        },
        "lane_breakdown": dict(sorted(lane_breakdown.items())),
        "safe_context_recovered_case_ids": recovered_case_ids,
        "safe_context_opportunity_case_ids": opportunity_case_ids,
        "accepted": False,
        "rejection_reasons": [],
    }
    if baseline_counts is not None:
        metrics["recovered_after_loop_delta_vs_baseline"] = (
            metrics["counts"]["recovered_after_loop"] - baseline_counts["counts"]["recovered_after_loop"]
        )
        metrics["citation_coverage_delta_vs_baseline"] = round(
            metrics["counts"]["citation_coverage_after"] - baseline_counts["counts"]["citation_coverage_after"],
            6,
        )
    return metrics


def transform_decision(
    row: Mapping[str, Any],
    decision: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> dict[str, Any]:
    transformed = deepcopy(dict(decision))
    blocked = set(transformed.get("blocked_lanes", []))

    if (
        variant.get("pdf_file_identity_exactness_rule", "exact_or_canonical_identity_required")
        != "exact_or_canonical_identity_required"
        or variant.get("filename_token_overlap_support") is True
    ) and row["lane"] == PDF_FILE_LOOKUP:
        if blocked.intersection(PDF_FILE_HARD_NEGATIVE_BLOCKS | PDF_FILE_AMBIGUOUS_BLOCKS):
            transformed["sufficiency_status"] = SUPPORTED
            transformed["failure_type"] = ""
            transformed["blocked_lanes"] = []
            transformed["official_support"] = True

    if variant.get("hidden_xlsx_blocking") == "disabled" and "XLSX_HIDDEN_CONTENT" in blocked:
        transformed["sufficiency_status"] = SUPPORTED
        transformed["failure_type"] = ""
        transformed["blocked_lanes"] = []
        transformed["official_support"] = True

    if variant.get("diagnostic_only_support") == "enabled" and (
        row["lane"] in SHADOW_LANES or blocked.intersection(SHADOW_LANES)
    ):
        transformed["sufficiency_status"] = SUPPORTED
        transformed["failure_type"] = ""
        transformed["blocked_lanes"] = []
        transformed["official_support"] = True

    return transformed


def recoverable_by_variant(
    row: Mapping[str, Any],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> bool:
    del before
    if after["sufficiency_status"] == SUPPORTED:
        return False
    if not bool(row.get("expected_official_support_allowed")):
        return False
    if unsafe_blocked_lanes(row, after):
        return False
    enabled_lanes = set(variant.get("enabled_lanes", []))
    lane = row["lane"]
    if lane not in enabled_lanes:
        return False
    if lane == PDF_FILE_LOOKUP:
        return False
    if lane == TEXT:
        return bool(variant.get("text_context_expansion")) and after.get("failure_type") == "INSUFFICIENT_EVIDENCE"
    if lane == XLSX:
        if after.get("failure_type") == "NEEDS_USER_CONSTRAINT":
            return False
        return bool(variant.get("xlsx_strict_wrapper_only")) and after.get("failure_type") == "INSUFFICIENT_EVIDENCE"
    if lane == PDF_CONTENT:
        return (
            bool(variant.get("pdf_content_native_text_only"))
            and after.get("failure_type") == "INSUFFICIENT_EVIDENCE"
            and after.get("best_trust_tier", "") != "OCR_MEDIUM"
        )
    return False


def actual_safe_recovery_decision(
    row: Mapping[str, Any],
    current_after: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    post_expansion = row.get("safe_recall_post_expansion_decision", {})
    if isinstance(post_expansion, Mapping) and variant["name"] in post_expansion:
        candidate = post_expansion[variant["name"]]
    else:
        candidate = post_expansion
    if not isinstance(candidate, Mapping):
        return False, deepcopy(dict(current_after))
    transformed = deepcopy(dict(candidate))
    if transformed.get("sufficiency_status") != SUPPORTED:
        return False, deepcopy(dict(current_after))
    if int(transformed.get("cited_evidence_count", 0)) <= 0:
        return False, deepcopy(dict(current_after))
    if float(transformed.get("citation_coverage", 0.0)) < 1.0:
        return False, deepcopy(dict(current_after))
    if unsafe_blocked_lanes(row, transformed):
        return False, deepcopy(dict(current_after))
    return True, transformed


def unsafe_blocked_lanes(row: Mapping[str, Any], decision: Mapping[str, Any]) -> bool:
    blocked = set(row["before_decision"].get("blocked_lanes", [])) | set(decision.get("blocked_lanes", []))
    if row["lane"] in SHADOW_LANES or blocked.intersection(SHADOW_LANES):
        return True
    if "XLSX_HIDDEN_CONTENT" in blocked:
        return True
    if row["lane"] == PDF_FILE_LOOKUP:
        return True
    if blocked.intersection(PDF_FILE_HARD_NEGATIVE_BLOCKS | PDF_FILE_AMBIGUOUS_BLOCKS):
        return True
    return False


def rejection_reasons(
    metrics: Mapping[str, Any],
    variant: Mapping[str, Any],
    baseline: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    selection_metrics: Mapping[str, Any] | None = None,
    selection_baseline: Mapping[str, Any] | None = None,
    source_violations: Sequence[Mapping[str, Any]] = (),
) -> list[str]:
    reasons = static_variant_rejections(variant, config)
    counts = metrics["counts"]
    baseline_counts = baseline["counts"]
    if counts["wrongly_supported_count"] > 0:
        reasons.append("wrongly_supported_count > 0")
    if counts["hidden_xlsx_surface_attempt_count"] < baseline_counts["hidden_xlsx_surface_attempt_count"]:
        reasons.append("weakens hidden XLSX blocking")
    if counts["pdf_file_lookup_content_mixing_attempt_count"] < baseline_counts["pdf_file_lookup_content_mixing_attempt_count"]:
        reasons.append("weakens PDF FILE content-mixing blocking")
    if counts["diagnostic_only_evidence_blocked_count"] < baseline_counts["diagnostic_only_evidence_blocked_count"]:
        reasons.append("weakens diagnostic-only evidence blocking")
    if source_violations:
        reasons.append("source loop/rewrite cap violation")
    comparable_metrics = selection_metrics or metrics
    comparable_baseline = selection_baseline or baseline
    if variant["name"] != "baseline_selected_policy" and not reasons:
        if (
            comparable_metrics["counts"]["recovered_after_loop"]
            <= comparable_baseline["counts"]["recovered_after_loop"]
            and comparable_metrics["counts"]["citation_coverage_after"]
            <= comparable_baseline["counts"]["citation_coverage_after"]
        ):
            reasons.append("no recovery or citation-coverage improvement")
    return sorted(set(reasons), key=reasons.index)


def static_variant_rejections(variant: Mapping[str, Any], config: Mapping[str, Any]) -> list[str]:
    del config
    reasons: list[str] = []
    if variant.get("pdf_file_identity_exactness_rule", "exact_or_canonical_identity_required") != (
        "exact_or_canonical_identity_required"
    ):
        reasons.append("weakens PDF FILE identity exactness")
    if variant.get("filename_token_overlap_support") is True:
        reasons.append("allows filename token overlap support")
    if variant.get("hidden_xlsx_blocking", "enabled") != "enabled":
        reasons.append("weakens hidden XLSX blocking")
    if variant.get("diagnostic_only_support", "disabled") != "disabled":
        reasons.append("allows diagnostic-only evidence as support")
    if bool(variant.get("production_profile_changes", False)):
        reasons.append("changes production profiles")
    if bool(variant.get("official_denominator_changes", False)):
        reasons.append("opens official answer denominators")
    if bool(variant.get("broad_indexing", False)):
        reasons.append("runs broad indexing")
    if bool(variant.get("frozen_gold_selection_or_training", False)):
        reasons.append("uses frozen gold for selection or training")
    if max_loop_iterations(variant) > 2:
        reasons.append("max loop iterations exceeds 2")
    if max_query_rewrites(variant) > 3:
        reasons.append("max query rewrites exceeds 3")
    claims = variant.get("pdf_file_lookup_success_claims", {})
    if any(bool(claims.get(key, False)) for key in PDF_FILE_CONTENT_CLAIM_KEYS):
        reasons.append("PDF FILE lookup claims content/page/bbox/table/row/column/value success")
    return reasons


def select_variant(variants: Sequence[Mapping[str, Any]], baseline: Mapping[str, Any]) -> dict[str, Any]:
    accepted = [dict(row) for row in variants if row["accepted"]]
    if not accepted:
        return dict(baseline)
    def selection_counts(row: Mapping[str, Any]) -> Mapping[str, Any]:
        return row.get("selection_metrics", row)["counts"]

    accepted.sort(
        key=lambda row: (
            row["counts"]["wrongly_supported_count"] == 0,
            selection_counts(row)["recovered_after_loop"] - baseline["counts"]["recovered_after_loop"],
            selection_counts(row)["citation_coverage_after"] - baseline["counts"]["citation_coverage_after"],
            row["variant_name"] == "baseline_selected_policy",
        ),
        reverse=True,
    )
    return accepted[0]


def build_baseline_report(
    *,
    config: Mapping[str, Any],
    config_path: Path,
    expanded_report_path: Path,
    baseline: Mapping[str, Any],
    source_artifacts: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    official_diff: Mapping[str, Any],
    source_violations: Sequence[Mapping[str, Any]],
    excluded_frozen_rows: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    return {
        "schema_version": "answer_recovery_safe_recall_baseline_v1",
        "status": "PASS" if not official_diff["changed"] else "BLOCKED",
        "config_path": repo_relative(config_path),
        "source_report": repo_relative(expanded_report_path),
        "baseline_policy": config["baseline_policy"],
        "counts": baseline["counts"],
        "lane_breakdown": baseline["lane_breakdown"],
        "source_artifacts": source_artifacts,
        "official_denominator_registry_diff_proof": official_diff,
        "frozen_gold_proof": frozen_gold_proof(config, excluded_frozen_rows),
        "source_guardrail_violations": list(source_violations),
        "guardrails": guardrails,
    }


def build_missed_analysis(
    case_results: Sequence[Mapping[str, Any]],
    *,
    baseline: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    del baseline
    excluded_sources = set(config.get("excluded_frozen_gold_ids", {}).get("source_files", []))
    rows: list[dict[str, Any]] = []
    counts_by_lane = Counter()
    counts_by_reason = Counter()
    safe_candidate_count = 0
    for row in case_results:
        status = row["after_decision"]["sufficiency_status"]
        if status == SUPPORTED:
            continue
        classification = classify_missed_case(row)
        counts_by_lane[row["lane"]] += 1
        counts_by_reason[classification["reason"]] += 1
        if classification["safe_recovery_candidate"]:
            safe_candidate_count += 1
        rows.append(
            {
                "case_id": row["case_id"],
                "lane": row["lane"],
                "case_type": row["case_type"],
                "status": status,
                "failure_type": row["after_decision"].get("failure_type", ""),
                "route_action": row["route"]["action"],
                "classification_reason": classification["reason"],
                "safe_recovery_candidate": classification["safe_recovery_candidate"],
                "do_not_recover_reason": classification["do_not_recover_reason"],
                "blocked_lanes": row["after_decision"].get("blocked_lanes", []),
                "selection_role": "excluded_frozen_gold"
                if row.get("source_artifact") in excluded_sources
                else "selection_candidate",
            }
        )
    return {
        "schema_version": "answer_recovery_missed_safe_recovery_analysis_v1",
        "status": "diagnostic_only",
        "total_missed_or_blocked": len(rows),
        "safe_recovery_candidate_count": safe_candidate_count,
        "counts_by_lane": dict(sorted(counts_by_lane.items())),
        "counts_by_reason": dict(sorted(counts_by_reason.items())),
        "rows": rows,
    }


def classify_missed_case(row: Mapping[str, Any]) -> dict[str, Any]:
    lane = row["lane"]
    case_type = row.get("case_type", "")
    decision = row["after_decision"]
    blocked = set(decision.get("blocked_lanes", []))
    expected_support = bool(row.get("expected_official_support_allowed"))
    do_not_recover = ""

    if lane == OCR_SHADOW:
        reason = "OCR_DIAGNOSTIC_ONLY_BLOCKED"
        do_not_recover = "OCR rows remain DIAGNOSTIC_ONLY."
    elif lane == IDP_SHADOW:
        reason = "IDP_DIAGNOSTIC_ONLY_BLOCKED"
        do_not_recover = "IDP rows remain DIAGNOSTIC_ONLY."
    elif lane == MULTIMODAL_SHADOW:
        reason = "MULTIMODAL_DIAGNOSTIC_ONLY_BLOCKED"
        do_not_recover = "Multimodal rows remain DIAGNOSTIC_ONLY."
    elif lane == PDF_FILE_LOOKUP and blocked.intersection(PDF_FILE_HARD_NEGATIVE_BLOCKS):
        reason = "PDF_FILE_HARD_NEGATIVE_DO_NOT_RECOVER"
        do_not_recover = "PDF FILE hard-negative identity rows must fail closed."
    elif lane == PDF_FILE_LOOKUP and (case_type == "pdf_file_lookup_content_mixing" or "PDF_FILE_LOOKUP" in blocked):
        reason = "PDF_FILE_IDENTITY_AMBIGUOUS"
        do_not_recover = "PDF FILE lookup remains file identity only and separate from PDF CONTENT."
    elif lane == PDF_FILE_LOOKUP:
        reason = "PDF_FILE_IDENTITY_AMBIGUOUS"
        do_not_recover = "Exact or canonical file identity is missing or ambiguous."
    elif lane == XLSX and "XLSX_HIDDEN_CONTENT" in blocked:
        reason = "POLICY_CORRECTLY_BLOCKED"
        do_not_recover = "Hidden XLSX content must stay out of query, candidate, gold, and answer surfaces."
    elif lane == XLSX and decision.get("failure_type") == "NEEDS_USER_CONSTRAINT":
        reason = "XLSX_NEEDS_USER_METRIC_OR_PERIOD"
        do_not_recover = "Needs user metric or period; strict wrapper expansion must not guess."
    elif lane == XLSX:
        reason = "XLSX_NEEDS_ROW_COLUMN_CONTEXT"
    elif lane == PDF_CONTENT and decision.get("best_trust_tier") == "OCR_MEDIUM":
        reason = "PDF_CONTENT_NATIVE_TEXT_INSUFFICIENT"
        do_not_recover = "OCR fallback remains lower trust and diagnostic-only."
    elif lane == PDF_CONTENT:
        reason = "PDF_CONTENT_NEEDS_PAGE_CONTEXT"
    elif lane == TEXT and row["route"]["action"] == "ASK_CLARIFICATION":
        reason = "TEXT_NEEDS_ENTITY_TITLE_DISAMBIGUATION"
    elif lane == TEXT and row.get("loop_result", {}).get("query_rewrite_count", 0):
        reason = "TEXT_NEEDS_QUERY_REWRITE"
    elif lane == TEXT:
        reason = "TEXT_NEEDS_ADJACENT_CONTEXT"
    else:
        reason = "POLICY_CORRECTLY_BLOCKED"

    safe_recovery_candidate = expected_support and not do_not_recover and not unsafe_blocked_lanes(row, decision)
    if not expected_support and not do_not_recover:
        do_not_recover = "Current diagnostic label expects no official support; recovering would be false support."
        if reason not in {
            "OCR_DIAGNOSTIC_ONLY_BLOCKED",
            "IDP_DIAGNOSTIC_ONLY_BLOCKED",
            "MULTIMODAL_DIAGNOSTIC_ONLY_BLOCKED",
            "PDF_FILE_HARD_NEGATIVE_DO_NOT_RECOVER",
        }:
            reason = "TRUE_UNANSWERABLE" if lane in {TEXT, PDF_CONTENT} else "POLICY_CORRECTLY_BLOCKED"

    return {
        "reason": reason,
        "safe_recovery_candidate": safe_recovery_candidate,
        "do_not_recover_reason": do_not_recover,
    }


def build_selected_policy(
    selected: Mapping[str, Any],
    config: Mapping[str, Any],
    guardrails: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "answer_recovery_safe_recall_selected_policy_v1",
        "variant_name": selected["variant_name"],
        "base_policy": selected.get("base_policy", "calibrated_identity_exact_v1"),
        "diagnostic_only": True,
        "production_promotion_ready": False,
        "official_answer_denominator_ready": False,
        "policy": {
            "enabled_lanes": selected.get("enabled_lanes", []),
            "pdf_file_identity_exactness_rule": selected.get(
                "pdf_file_identity_exactness_rule", "exact_or_canonical_identity_required"
            ),
            "hidden_xlsx_blocking": selected.get("hidden_xlsx_blocking", "enabled"),
            "diagnostic_only_support": selected.get("diagnostic_only_support", "disabled"),
            "max_loop_iterations": min(
                int(selected.get("max_loop_iterations", 2)),
                int(config["allowed_tuning_knobs"]["max_loop_iterations"]),
            ),
            "max_query_rewrites": min(
                int(selected.get("max_query_rewrites", 3)),
                int(config["allowed_tuning_knobs"]["max_query_rewrites"]),
            ),
        },
        "counts": selected["counts"],
        "lane_breakdown": selected["lane_breakdown"],
        "rejection_reasons": selected.get("rejection_reasons", []),
        "guardrails": dict(guardrails),
    }


def build_guardrail_status(config: Mapping[str, Any]) -> dict[str, Any]:
    assertions = dict(config["guardrail_assertions"])
    assertions["production_index_mutation"] = False
    assertions["broad_indexing"] = False
    assertions["official_answer_denominator_opened"] = False
    assertions["production_promotion_ready"] = False
    assertions["official_answer_denominator_ready"] = False
    assertions["diagnostic_only_evidence_support"] = False
    assertions["hidden_xlsx_content_blocked"] = True
    assertions["pdf_file_identity_exactness_rule"] = "exact_or_canonical_identity_required"
    return assertions


def build_source_artifact_proof(config: Mapping[str, Any]) -> dict[str, Any]:
    proof: dict[str, Any] = {}
    for key, value in config["diagnostic_inputs"].items():
        path = resolve_path(value)
        entry: dict[str, Any] = {
            "path": repo_relative(path),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
        }
        if path.exists() and path.suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as handle:
                entry["line_count"] = sum(1 for _ in handle)
        proof[key] = entry
    return proof


def ensure_narrow_artifacts(config: Mapping[str, Any]) -> None:
    baseline = config["baseline_policy"]
    required = [
        resolve_path(baseline["source_report"]),
        resolve_path(baseline["source_selected_policy"]),
    ]
    if all(path.exists() for path in required):
        return
    if not report_artifacts.reporting_options(config)["emit_stage_reports"]:
        return
    narrow_config_path = resolve_path(baseline["source_config"])
    narrow_config = report_artifacts.with_reporting_overrides(
        narrow.load_config(narrow_config_path),
        dict(config.get("reporting") or {}),
    )
    report_dir = DEFAULT_REPORT_DIR
    report = narrow.run_calibration(config=narrow_config, config_path=narrow_config_path, report_dir=report_dir)
    narrow.write_outputs(narrow_config, report)


def write_outputs(config: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    options = report_artifacts.reporting_options(config)
    paths = config["report_paths"]
    if options["emit_stage_reports"]:
        write_json(resolve_path(paths["baseline_json"]), payload["baseline_report"])
        write_text(resolve_path(paths["baseline_md"]), render_baseline_md(payload["baseline_report"]))
        write_json(resolve_path(paths["missed_analysis_json"]), payload["missed_analysis"])
        write_text(resolve_path(paths["missed_analysis_md"]), render_missed_analysis_md(payload["missed_analysis"]))
        write_json(resolve_path(paths["tuning_report_json"]), payload["tuning_report"])
        write_text(resolve_path(paths["tuning_report_md"]), render_tuning_report_md(payload["tuning_report"]))
        write_json(resolve_path(paths["selected_policy_json"]), payload["selected_policy"])
        write_text(resolve_path(paths["rejected_variants_md"]), render_rejected_variants_md(payload["tuning_report"]))
    if options["emit_csv"]:
        write_csv(resolve_path(paths["variants_csv"]), payload["tuning_report"]["variants"])


def render_baseline_md(payload: Mapping[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        "# Answer Recovery Safe Recall Baseline",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Baseline policy: `{payload['baseline_policy']['name']}`.",
        "- Broad tuning: `false`.",
        "- Production promotion ready: `false`.",
        "- Official answer denominator ready: `false`.",
        f"- Official denominator registry changed: `{payload['official_denominator_registry_diff_proof']['changed']}`.",
        f"- Frozen gold used for selection: `{payload['frozen_gold_proof']['used_for_selection']}`.",
        f"- Frozen gold used for training: `{payload['frozen_gold_proof']['used_for_training']}`.",
        f"- Frozen-gold rows excluded from selection: `{payload['frozen_gold_proof']['excluded_from_selection_row_count']}`.",
        f"- Source loop/rewrite cap violations: `{len(payload['source_guardrail_violations'])}`.",
        "",
        "## Counts",
        "",
    ]
    for key in (
        "total_evaluated",
        "initially_supported",
        "recovered_after_loop",
        "wrongly_supported_count",
        "unsupported_correctly_blocked_count",
        "clarification_needed_count",
        "hidden_xlsx_surface_attempt_count",
        "pdf_file_lookup_content_mixing_attempt_count",
        "diagnostic_only_evidence_blocked_count",
        "citation_coverage_before",
        "citation_coverage_after",
        "average_loop_iterations",
    ):
        lines.append(f"- {key}: `{counts[key]}`")
    lines.extend(["", "## Lane Breakdown", ""])
    lines.extend(render_lane_table(payload["lane_breakdown"]))
    lines.extend(
        [
            "",
            "## Proof",
            "",
            f"- Registry diff command: `{payload['official_denominator_registry_diff_proof']['command']}`.",
            f"- Registry diff empty: `{payload['official_denominator_registry_diff_proof']['diff_empty']}`.",
            "- Frozen gold profile selection: `false`.",
            "- Frozen gold training rows: `0`.",
            "",
        ]
    )
    return "\n".join(lines)


def render_missed_analysis_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Answer Recovery Missed Safe Recovery Analysis",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Total missed or blocked: `{payload['total_missed_or_blocked']}`.",
        f"- Safe recovery candidates: `{payload['safe_recovery_candidate_count']}`.",
        "",
        "## By Lane",
        "",
    ]
    for key, value in payload["counts_by_lane"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## By Reason", ""])
    for key, value in payload["counts_by_reason"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Rows", ""])
    for row in payload["rows"]:
        blocked = ",".join(row["blocked_lanes"]) or "none"
        lines.append(
            f"- `{row['case_id']}` {row['lane']} {row['status']} "
            f"reason=`{row['classification_reason']}` safe_candidate=`{row['safe_recovery_candidate']}` "
            f"selection_role=`{row['selection_role']}` blocked=`{blocked}`"
        )
    lines.append("")
    return "\n".join(lines)


def render_tuning_report_md(payload: Mapping[str, Any]) -> str:
    selected = payload["selected_policy"]
    lines = [
        "# Answer Recovery Safe Recall Tuning Report",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Selected variant: `{selected['variant_name']}`.",
        f"- Decision: {payload['decision']['reason']}",
        "- Diagnostic only: `true`.",
        "- Production promotion ready: `false`.",
        "- Official answer denominator ready: `false`.",
        f"- Frozen-gold rows excluded from selection: `{payload['selection_excluded_frozen_gold_row_count']}`.",
        f"- Source loop/rewrite cap violations: `{len(payload['source_guardrail_violations'])}`.",
        "",
        "## Selected Counts",
        "",
    ]
    for key, value in selected["counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Variants", ""])
    lines.append(
        "| variant | recovered_delta | citation_delta | wrongly_supported | hidden_blocked | pdf_file_mixing_blocked | diagnostic_only_blocked | accepted | rejected_reason |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|---|")
    for row in payload["variants"]:
        counts = row["counts"]
        reasons = "; ".join(row["rejection_reasons"]) or ""
        lines.append(
            f"| {row['variant_name']} | {row['recovered_after_loop_delta_vs_baseline']} | "
            f"{row['citation_coverage_delta_vs_baseline']} | {counts['wrongly_supported_count']} | "
            f"{counts['hidden_xlsx_surface_attempt_count']} | "
            f"{counts['pdf_file_lookup_content_mixing_attempt_count']} | "
            f"{counts['diagnostic_only_evidence_blocked_count']} | {row['accepted']} | {reasons} |"
        )
    lines.extend(["", "## Lane-Level Recovery Deltas", ""])
    for row in payload["variants"]:
        deltas = ", ".join(f"{lane}={delta}" for lane, delta in row["lane_level_recovery_deltas"].items())
        lines.append(f"- {row['variant_name']}: `{deltas}`")
    lines.extend(["", "## Guardrails", ""])
    for key, value in payload["guardrail_status"].items():
        if isinstance(value, Mapping):
            compact = ", ".join(f"{subkey}={subvalue}" for subkey, subvalue in value.items())
            lines.append(f"- {key}: `{compact}`")
        else:
            lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def render_rejected_variants_md(payload: Mapping[str, Any]) -> str:
    lines = ["# Answer Recovery Safe Recall Rejected Variants", ""]
    for row in payload["variants"]:
        if row["variant_name"] == payload["selected_policy"]["variant_name"] and not row["rejection_reasons"]:
            continue
        reasons = "; ".join(row["rejection_reasons"]) or "not selected"
        lines.append(f"- `{row['variant_name']}`: {reasons}")
    lines.append("")
    return "\n".join(lines)


def render_lane_table(lane_breakdown: Mapping[str, Mapping[str, int]]) -> list[str]:
    lines = [
        "| lane | total | initially_supported | supported_after_recovery | recovered_after_loop | wrongly_supported | unsupported_correctly_blocked | clarification_needed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for lane, row in lane_breakdown.items():
        lines.append(
            f"| {lane} | {row['total']} | {row['initially_supported']} | "
            f"{row['supported_after_recovery']} | {row['recovered_after_loop']} | "
            f"{row['wrongly_supported']} | {row['unsupported_correctly_blocked']} | "
            f"{row['clarification_needed']} |"
        )
    return lines


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "variant_name",
        "accepted",
        "rejection_reasons",
        "total_evaluated",
        "initially_supported",
        "recovered_after_loop",
        "recovered_after_loop_delta_vs_baseline",
        "wrongly_supported_count",
        "unsupported_correctly_blocked_count",
        "clarification_needed_count",
        "hidden_xlsx_surface_attempt_count",
        "pdf_file_lookup_content_mixing_attempt_count",
        "diagnostic_only_evidence_blocked_count",
        "citation_coverage_before",
        "citation_coverage_after",
        "citation_coverage_delta_vs_baseline",
        "average_loop_iterations",
        "selection_total_evaluated",
        "selection_recovered_after_loop_delta_vs_baseline",
        "selection_citation_coverage_delta_vs_baseline",
        "safe_context_opportunity_count",
        "safe_context_recovered_count",
        "excluded_frozen_gold_row_count",
        "lane_level_recovery_deltas",
        "pdf_file_identity_exactness_rule",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            counts = row["counts"]
            writer.writerow(
                {
                    "variant_name": row["variant_name"],
                    "accepted": row["accepted"],
                    "rejection_reasons": ";".join(row["rejection_reasons"]),
                    "total_evaluated": counts["total_evaluated"],
                    "initially_supported": counts["initially_supported"],
                    "recovered_after_loop": counts["recovered_after_loop"],
                    "recovered_after_loop_delta_vs_baseline": row["recovered_after_loop_delta_vs_baseline"],
                    "wrongly_supported_count": counts["wrongly_supported_count"],
                    "unsupported_correctly_blocked_count": counts["unsupported_correctly_blocked_count"],
                    "clarification_needed_count": counts["clarification_needed_count"],
                    "hidden_xlsx_surface_attempt_count": counts["hidden_xlsx_surface_attempt_count"],
                    "pdf_file_lookup_content_mixing_attempt_count": counts["pdf_file_lookup_content_mixing_attempt_count"],
                    "diagnostic_only_evidence_blocked_count": counts["diagnostic_only_evidence_blocked_count"],
                    "citation_coverage_before": counts["citation_coverage_before"],
                    "citation_coverage_after": counts["citation_coverage_after"],
                    "citation_coverage_delta_vs_baseline": row["citation_coverage_delta_vs_baseline"],
                    "average_loop_iterations": counts["average_loop_iterations"],
                    "selection_total_evaluated": row["selection_metrics"]["counts"]["total_evaluated"],
                    "selection_recovered_after_loop_delta_vs_baseline": row[
                        "selection_recovered_after_loop_delta_vs_baseline"
                    ],
                    "selection_citation_coverage_delta_vs_baseline": row[
                        "selection_citation_coverage_delta_vs_baseline"
                    ],
                    "safe_context_opportunity_count": len(row["safe_context_opportunity_case_ids"]),
                    "safe_context_recovered_count": len(row["safe_context_recovered_case_ids"]),
                    "excluded_frozen_gold_row_count": row["excluded_frozen_gold_row_count"],
                    "lane_level_recovery_deltas": json.dumps(
                        row["lane_level_recovery_deltas"], ensure_ascii=False, sort_keys=True
                    ),
                    "pdf_file_identity_exactness_rule": row["pdf_file_identity_exactness_rule"],
                }
            )


def is_hidden_xlsx_case(row: Mapping[str, Any]) -> bool:
    blocked = set(row["before_decision"].get("blocked_lanes", [])) | set(row["after_decision"].get("blocked_lanes", []))
    return row["lane"] == XLSX and "XLSX_HIDDEN_CONTENT" in blocked


def is_pdf_file_content_mixing_case(row: Mapping[str, Any]) -> bool:
    return row["lane"] == PDF_FILE_LOOKUP and row.get("case_type") == "pdf_file_lookup_content_mixing"


def diagnostic_only_block_increment(
    row: Mapping[str, Any],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> int:
    if after["sufficiency_status"] == SUPPORTED:
        return 0
    blocked = set(before.get("blocked_lanes", [])) | set(after.get("blocked_lanes", []))
    count = 0
    if row["lane"] in SHADOW_LANES:
        count += 1
    if blocked.intersection(SHADOW_LANES):
        count += 1
    return count


def lane_recovery_deltas(metrics: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, int]:
    lanes = set(metrics["lane_breakdown"]) | set(baseline["lane_breakdown"])
    return {
        lane: int(metrics["lane_breakdown"].get(lane, {}).get("recovered_after_loop", 0))
        - int(baseline["lane_breakdown"].get(lane, {}).get("recovered_after_loop", 0))
        for lane in sorted(lanes)
    }


def selection_reason(selected: Mapping[str, Any], baseline: Mapping[str, Any]) -> str:
    if selected["variant_name"] == "baseline_selected_policy":
        return "No safe recall variant improved recovery or citation coverage without guardrail regression; kept calibrated_identity_exact_v1."
    recovered_delta = selected["counts"]["recovered_after_loop"] - baseline["counts"]["recovered_after_loop"]
    citation_delta = selected["counts"]["citation_coverage_after"] - baseline["counts"]["citation_coverage_after"]
    return (
        f"Selected variant improved recovered_after_loop by {recovered_delta} "
        f"and citation_coverage_after by {round(citation_delta, 6)} without guardrail regression."
    )


def baseline_variant_from_config(config: Mapping[str, Any]) -> dict[str, Any]:
    for variant in config["variants"]:
        if variant["name"] == "baseline_selected_policy":
            return dict(variant)
    return {
        "name": "baseline_selected_policy",
        "base_policy": config["baseline_policy"]["name"],
        "enabled_lanes": [],
        "pdf_file_identity_exactness_rule": "exact_or_canonical_identity_required",
        "hidden_xlsx_blocking": "enabled",
        "diagnostic_only_support": "disabled",
        "max_loop_iterations": 2,
        "max_query_rewrites": 3,
    }


def frozen_gold_proof(
    config: Mapping[str, Any],
    excluded_frozen_rows: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    frozen = config.get("excluded_frozen_gold_ids", {})
    return {
        "used_for_selection": bool(frozen.get("use_for_selection", True)),
        "used_for_training": bool(frozen.get("use_for_training", True)),
        "source_files": frozen.get("source_files", []),
        "excluded_from_selection_row_count": len(excluded_frozen_rows),
        "excluded_from_selection_rows": list(excluded_frozen_rows),
        "training_rows": 0,
        "profile_selection_rows": 0,
    }


def official_registry_diff_proof() -> dict[str, Any]:
    registry = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
    rel = registry.relative_to(REPO_ROOT).as_posix()
    unstaged_quiet = subprocess.run(
        ["git", "diff", "--quiet", "--", rel],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    staged_quiet = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", rel],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    changed = unstaged_quiet.returncode != 0 or staged_quiet.returncode != 0
    return {
        "path": rel,
        "command": f"git diff --quiet -- {rel}; git diff --cached --quiet -- {rel}",
        "changed": changed,
        "unstaged_diff_empty": unstaged_quiet.returncode == 0,
        "staged_diff_empty": staged_quiet.returncode == 0,
        "diff_empty": not changed,
        "diff_stdout_bytes": 0,
    }


def max_loop_iterations(variant: Mapping[str, Any]) -> int:
    return int(variant.get("max_loop_iterations", 2))


def max_query_rewrites(variant: Mapping[str, Any]) -> int:
    return int(variant.get("max_query_rewrites", 3))


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def average(values: Sequence[float | int]) -> float:
    return round(sum(float(value) for value in values) / len(values), 6) if values else 0.0


def resolve_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai":
        return REPO_ROOT / path
    return AI_WORKER_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
