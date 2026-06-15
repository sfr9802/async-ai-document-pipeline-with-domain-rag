"""Diagnose retrieval vector interference root causes without mutating indexes.

This script reads Phase 1/2 diagnostic reports and replays a small in-memory
ablation for TEXT_NAMU and PDF_FILE_IDENTITY. It is report-only: no production
index writes, no vector writes, no denominator registry changes, no Optuna, and
no hidden XLSX content access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rag_vector_interference_diagnostic as vector_diag


DEFAULT_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "retrieval_ood_interference_diagnostic.yaml"
DEFAULT_REPORT_JSON = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "retrieval_interference_root_cause_ablation.json"
DEFAULT_REPORT_MD = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "retrieval_interference_root_cause_ablation.md"
DEFAULT_BY_QUERY_CSV = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "retrieval_interference_root_cause_ablation_by_query.csv"

CONDITION_A = vector_diag.CONDITION_A
CONDITION_C = vector_diag.CONDITION_C
CONDITION_E = vector_diag.CONDITION_E
CONDITION_E_NO_QUERY = "E_near_duplicate_metadata_without_query_echo"

TEXT_VARIANTS = [
    "current_profile",
    "content_only",
    "metadata_capped",
    "metadata_removed",
    "hybrid_bm25_materialized",
]

BY_QUERY_FIELDS = [
    "analysis_type",
    "lane",
    "variant",
    "condition",
    "query_id",
    "hit_rank",
    "hit_at_1",
    "hit_at_3",
    "hit_at_5",
    "hit_at_10",
    "mrr_at_10",
    "rank_loss",
    "score_margin",
    "score_margin_collapse",
    "false_positive_top10_count",
    "false_positive_increase",
    "source_document_confusion",
    "lane_confusion",
    "pdf_file_identity_confusion",
    "citation_location_degradation_effective",
    "vector_interference_loss",
    "root_cause_flags",
]

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
MONTH_RE = re.compile(r"(?<!\d)(?:0?[1-9]|1[0-2])(?!\d)")


@dataclass(frozen=True)
class RankedResult:
    metrics: dict[str, Any]
    top_false: vector_diag.Candidate | None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config)
    config = vector_diag.load_config(config_path)
    report, by_query_rows = build_report(config, run_reranker=not args.skip_reranker)

    report_json = resolve_path(args.output_json or DEFAULT_REPORT_JSON)
    report_md = resolve_path(args.output_md or DEFAULT_REPORT_MD)
    by_query_csv = resolve_path(args.by_query_csv or DEFAULT_BY_QUERY_CSV)
    report["outputs"] = {
        "json": repo_relative(report_json),
        "markdown": repo_relative(report_md),
        "by_query_csv": repo_relative(by_query_csv),
    }
    write_json(report_json, report)
    write_text(report_md, render_markdown(report))
    write_by_query(by_query_csv, by_query_rows)
    print(json.dumps({
        "status": report["status"],
        "text_namu_root_cause": report["text_namu_root_cause"]["primary_cause"],
        "phase3_optuna_diagnostic_ready": report["phase3_optuna_diagnostic_ready"],
        "json": repo_relative(report_json),
    }, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    parser.add_argument("--by-query-csv", default=None)
    parser.add_argument("--skip-reranker", action="store_true")
    return parser.parse_args(argv)


def build_report(config: Mapping[str, Any], *, run_reranker: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs = input_paths(config)
    diversity = read_json(inputs["diversity_json"])
    ood_split = read_json(inputs["ood_split_json"])
    vector_report = read_json(inputs["vector_report_json"])
    phase2_rows = read_csv_rows(inputs["vector_by_query_csv"])

    metric_sanity, sanity_rows = metric_sanity_check(phase2_rows, vector_report, diversity)
    baseline = baseline_weakness_check(phase2_rows)
    text_ablation, text_rows = run_text_namu_ablation(config, diversity, run_reranker=run_reranker)
    pdf_ablation, pdf_rows = run_pdf_file_identity_ablation(config)
    ceiling = ceiling_effect_check(diversity, vector_report)
    guardrails = guardrail_status(diversity, ood_split, vector_report)
    root_cause = classify_text_namu_root_cause(text_ablation, metric_sanity, baseline)
    tunable = tunable_parameter_assessment(text_ablation)
    phase3 = phase3_decision(metric_sanity, guardrails, root_cause, ceiling, text_ablation)
    status = "PASS_DIAGNOSTIC_ROOT_CAUSE_IDENTIFIED" if root_cause["decomposed"] else "PASS_WITH_UNRESOLVED_ROOT_CAUSE"

    report = {
        "schema_version": "retrieval_interference_root_cause_ablation_v1",
        "task": "rag_retrieval_interference_root_cause_ablation_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        "scope": "diagnostic_report_only",
        "inputs": {name: repo_relative(path) for name, path in inputs.items()},
        "guardrails": guardrails,
        "production_index_mutation": False,
        "vector_write_attempted": False,
        "official_denominator_registry_changed": False,
        "hidden_xlsx_exposed": False,
        "local_llm_used_for_labels_or_judgments": False,
        "optuna_run": False,
        "pdf_file_lookup_policy": vector_diag.PDF_FILE_IDENTITY_ONLY_POLICY,
        "metric_sanity": metric_sanity,
        "baseline_weakness": baseline,
        "text_namu_ablation": text_ablation,
        "reranker_availability": text_ablation.get("reranker") or {},
        "text_namu_root_cause": root_cause,
        "pdf_file_identity_ablation": pdf_ablation,
        "xlsx_pdf_content_ceiling_effect": ceiling,
        "tunable_parameters": tunable,
        "phase3_optuna_diagnostic_ready": phase3["ready"],
        "phase3_optuna_diagnostic_decision": phase3,
        "dataset_supplementation_priorities": dataset_priorities(root_cause, ceiling, pdf_ablation),
    }
    by_query_rows = sanity_rows + text_rows + pdf_rows
    return report, by_query_rows


def input_paths(config: Mapping[str, Any]) -> dict[str, Path]:
    prerequisites = config.get("prerequisites", {}) if isinstance(config.get("prerequisites"), Mapping) else {}
    outputs = config.get("outputs", {}) if isinstance(config.get("outputs"), Mapping) else {}
    return {
        "diversity_json": resolve_path(str(prerequisites.get("phase1_corpus_diversity_profile", AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "retrieval_corpus_diversity_profile.json"))),
        "ood_split_json": resolve_path(str(outputs.get("split_report_json", AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "retrieval_ood_split_report.json"))),
        "vector_report_json": resolve_path(str(outputs.get("interference_report_json", AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "vector_interference_diagnostic.json"))),
        "vector_by_query_csv": resolve_path(str(outputs.get("interference_by_query_csv", AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "vector_interference_diagnostic_by_query.csv"))),
    }


def metric_sanity_check(
    rows: Sequence[Mapping[str, str]],
    vector_report: Mapping[str, Any],
    diversity: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    baseline_by_query = {
        (row["lane"], row["query_id"]): row
        for row in rows
        if row["condition"] == CONDITION_A
    }
    text_location_available = int(
        (((diversity.get("lanes") or {}).get("TEXT_NAMU") or {}).get("location_json_availability") or {}).get("available_count")
        or 0
    )
    by_query_rows: list[dict[str, Any]] = []
    max_row_loss_delta = 0.0
    for raw in rows:
        row = numeric_row(raw)
        lane = str(row["lane"])
        condition = str(row["condition"])
        baseline = numeric_row(baseline_by_query.get((lane, str(row["query_id"])), raw))
        if condition == CONDITION_A:
            mrr_loss = 0.0
            hit_losses = {f"hit_at_{k}_loss": 0.0 for k in [1, 3, 5, 10]}
        else:
            mrr_loss = max(0.0, float(baseline["mrr_at_10"]) - float(row["mrr_at_10"]))
            hit_losses = {
                f"hit_at_{k}_loss": max(0.0, float(baseline[f"hit_at_{k}"]) - float(row[f"hit_at_{k}"]))
                for k in [1, 3, 5, 10]
            }
        recomputed = 0.0 if condition == CONDITION_A else vector_loss(row)
        max_row_loss_delta = max(max_row_loss_delta, abs(recomputed - float(row["vector_interference_loss"])))
        effective_citation = 0 if lane == "TEXT_NAMU" and text_location_available == 0 else int(row["citation_location_degradation"])
        item = {
            "mrr_loss": round(mrr_loss, 6),
            **hit_losses,
            "rank_loss": float(row["rank_loss"]),
            "score_margin_collapse": float(row["score_margin_collapse"]),
            "false_positive_increase": float(row["false_positive_increase"]),
            "citation_location_degradation_raw": float(row["citation_location_degradation"]),
            "citation_location_degradation_effective": float(effective_citation),
            "lane_confusion": float(row["lane_confusion"]),
            "source_document_confusion": float(row["source_document_confusion"]),
            "pdf_file_identity_confusion": float(row["pdf_file_identity_confusion"]),
            "reported_vector_interference_loss": float(row["vector_interference_loss"]),
            "recomputed_vector_interference_loss": recomputed,
        }
        grouped[(lane, condition)].append(item)
        by_query_rows.append({
            "analysis_type": "metric_sanity",
            "lane": lane,
            "variant": "phase2_reported",
            "condition": condition,
            "query_id": row["query_id"],
            "hit_rank": row["hit_rank"],
            "hit_at_1": row["hit_at_1"],
            "hit_at_3": row["hit_at_3"],
            "hit_at_5": row["hit_at_5"],
            "hit_at_10": row["hit_at_10"],
            "mrr_at_10": row["mrr_at_10"],
            "rank_loss": row["rank_loss"],
            "score_margin": row["score_margin"],
            "score_margin_collapse": row["score_margin_collapse"],
            "false_positive_top10_count": row["false_positive_top10_count"],
            "false_positive_increase": row["false_positive_increase"],
            "source_document_confusion": row["source_document_confusion"],
            "lane_confusion": row["lane_confusion"],
            "pdf_file_identity_confusion": row["pdf_file_identity_confusion"],
            "citation_location_degradation_effective": effective_citation,
            "vector_interference_loss": recomputed,
            "root_cause_flags": "text_location_json_missing_adjusted" if lane == "TEXT_NAMU" and text_location_available == 0 and row["citation_location_degradation"] else "",
        })

    components: dict[str, dict[str, Any]] = defaultdict(dict)
    max_aggregate_delta = 0.0
    reported_metrics = vector_report.get("lane_condition_metrics") or {}
    for (lane, condition), items in sorted(grouped.items()):
        summary = summarize_component_items(items)
        reported_loss = (((reported_metrics.get(lane) or {}).get(condition) or {}).get("vector_interference_loss"))
        if reported_loss is not None:
            max_aggregate_delta = max(max_aggregate_delta, abs(float(reported_loss) - summary["recomputed_vector_interference_loss"]))
        components[lane][condition] = summary
    return {
        "passed": max_row_loss_delta <= 1e-6 and max_aggregate_delta <= 1e-6,
        "max_row_vector_loss_delta": round(max_row_loss_delta, 8),
        "max_aggregate_vector_loss_delta": round(max_aggregate_delta, 8),
        "text_namu_citation_location_degradation_counted_as_real_failure": text_location_available > 0,
        "text_namu_location_json_available_count": text_location_available,
        "component_means_by_lane_condition": {lane: dict(conditions) for lane, conditions in sorted(components.items())},
    }, by_query_rows


def baseline_weakness_check(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for lane, items in group_by(rows, "lane").items():
        base = [numeric_row(row) for row in items if row["condition"] == CONDITION_A]
        if not base:
            continue
        out[lane] = {
            "query_count": len(base),
            "hit_at_1": mean(base, "hit_at_1"),
            "hit_at_3": mean(base, "hit_at_3"),
            "hit_at_5": mean(base, "hit_at_5"),
            "hit_at_10": mean(base, "hit_at_10"),
            "mrr_at_10": mean(base, "mrr_at_10"),
            "not_in_top10_count": sum(1 for row in base if not int(row["hit_at_10"])),
            "avg_false_positives_top10": mean(base, "false_positive_top10_count"),
            "score_margin_distribution": distribution([float(row["score_margin"]) for row in base]),
        }
    return out


def run_text_namu_ablation(
    config: Mapping[str, Any],
    diversity: Mapping[str, Any],
    *,
    run_reranker: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lane_cfg = find_lane(config, "TEXT_NAMU")
    if lane_cfg is None:
        return {"status": "SKIPPED_TEXT_NAMU_LANE_MISSING", "variants": {}}, []
    cases = vector_diag.load_query_cases(lane_cfg)
    max_candidates = int((config.get("interference") or {}).get("max_baseline_candidates_per_lane", 2500))
    variant_reports: dict[str, Any] = {}
    by_query_rows: list[dict[str, Any]] = []
    for variant in TEXT_VARIANTS:
        mode = "hybrid_bm25" if variant == "hybrid_bm25_materialized" else "token_vector"
        candidates = load_text_candidates(lane_cfg, cases, variant, max_candidates=max_candidates)
        rows = evaluate_ablation_conditions(cases, candidates, variant=variant, score_mode=mode)
        variant_reports[variant] = summarize_ablation_rows(rows)
        by_query_rows.extend(format_ablation_rows(rows, variant=variant, lane="TEXT_NAMU"))

    reranker_info = reranker_availability() if run_reranker else reranker_availability_skipped()
    if run_reranker and reranker_info["available"]:
        try:
            candidates = load_text_candidates(lane_cfg, cases, "current_profile", max_candidates=max_candidates)
            rerank_rows = evaluate_rerank_variant(cases, candidates, reranker_info)
            variant_reports["rerank_current_profile"] = summarize_ablation_rows(rerank_rows)
            by_query_rows.extend(format_ablation_rows(rerank_rows, variant="rerank_current_profile", lane="TEXT_NAMU"))
            reranker_info["executed"] = True
        except Exception as exc:  # noqa: BLE001 - report-only fallback
            reranker_info["executed"] = False
            reranker_info["skip_reason"] = f"{type(exc).__name__}: {exc}"
    else:
        reranker_info["executed"] = False
        if not run_reranker:
            reranker_info["skip_reason"] = "disabled_by_cli_or_test"

    current = variant_reports.get("current_profile", {})
    e_loss = (((current.get(CONDITION_E) or {}).get("vector_interference_loss")) or 0.0)
    no_echo_loss = (((current.get(CONDITION_E_NO_QUERY) or {}).get("vector_interference_loss")) or 0.0)
    return {
        "status": "PASS",
        "query_count": len(cases),
        "candidate_count_by_variant": {
            variant: len(load_text_candidates(lane_cfg, cases, variant, max_candidates=max_candidates))
            for variant in TEXT_VARIANTS[:1]
        },
        "variants": variant_reports,
        "reranker": reranker_info,
        "bm25_text_source": "safely_materialized_from_TEXT_NAMU_chunk_text",
        "text_location_json_available_count": int(
            (((diversity.get("lanes") or {}).get("TEXT_NAMU") or {}).get("location_json_availability") or {}).get("available_count")
            or 0
        ),
        "near_duplicate_query_echo_loss": round(float(e_loss), 6),
        "near_duplicate_without_query_echo_loss": round(float(no_echo_loss), 6),
        "query_echo_loss_delta": round(float(e_loss) - float(no_echo_loss), 6),
        "near_duplicate_distractor_policy": "metadata_hard_negative_without_query_echo",
    }, by_query_rows


def run_pdf_file_identity_ablation(config: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lane_cfg = find_lane(config, "PDF_FILE_IDENTITY")
    if lane_cfg is None:
        return {"status": "SKIPPED_PDF_FILE_IDENTITY_LANE_MISSING"}, []
    cases = vector_diag.load_query_cases(lane_cfg)
    base = vector_diag.identity_candidates(lane_cfg)
    rows: list[dict[str, Any]] = []
    classifications: Counter[str] = Counter()
    for condition in [CONDITION_A, CONDITION_C, CONDITION_E, CONDITION_E_NO_QUERY]:
        baseline_by_query: dict[str, Mapping[str, Any]] = {}
        for case in cases:
            candidates = pdf_candidates_for_condition(case, condition, base)
            result = rank_case(case, condition, candidates, score_mode="token_vector")
            if condition == CONDITION_A:
                baseline_by_query[case.query_id] = result.metrics
                enriched = result.metrics
            else:
                baseline = baseline_by_query.get(case.query_id) or rank_case(case, CONDITION_A, base, score_mode="token_vector").metrics
                enriched = with_baseline_deltas(result.metrics, baseline)
            flags = classify_pdf_identity_failure(case, result.top_false, enriched)
            for flag in flags:
                classifications[flag] += 1
            row = dict(enriched)
            row["root_cause_flags"] = ";".join(flags)
            rows.append(row)
    summary = summarize_ablation_rows(rows)
    return {
        "status": "PASS",
        "query_count": len(cases),
        "condition_metrics": summary,
        "classification_counts": dict(sorted(classifications.items())),
        "content_identity_mixing_risk": False,
        "pdf_file_lookup_policy": vector_diag.PDF_FILE_IDENTITY_ONLY_POLICY,
    }, format_ablation_rows(rows, variant="identity_only", lane="PDF_FILE_IDENTITY")


def ceiling_effect_check(diversity: Mapping[str, Any], vector_report: Mapping[str, Any]) -> dict[str, Any]:
    lanes = diversity.get("lanes") or {}
    lane_summary = vector_report.get("lane_summary") or {}
    out: dict[str, Any] = {}
    for lane in ["XLSX", "PDF_CONTENT"]:
        div = lanes.get(lane) or {}
        baseline_mrr = float(((lane_summary.get(lane) or {}).get("baseline_mrr_at_10")) or 0.0)
        classification = str(div.get("classification") or "")
        low_diversity = classification == "LOW_DIVERSITY_HIGH_OVERFIT_RISK"
        out[lane] = {
            "classification": classification,
            "row_count": int(div.get("row_count") or 0),
            "source_document_count": int(div.get("source_document_count") or 0),
            "document_family_count": int(div.get("document_family_count") or 0),
            "chunk_near_duplicate_rate": float(div.get("chunk_near_duplicate_rate") or 0.0),
            "baseline_mrr_at_10": baseline_mrr,
            "ceiling_effect_likely": bool(low_diversity and baseline_mrr >= 0.99),
            "use_for_optuna_approval": False,
        }
    return out


def guardrail_status(*reports: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "production_index_mutation",
        "vector_write_attempted",
        "official_denominator_registry_changed",
        "hidden_xlsx_exposed",
    ]
    status = {key: any(bool(report.get(key)) for report in reports) for key in keys}
    status["pdf_file_lookup_content_claimed"] = any(
        bool(report.get("pdf_file_lookup_content_page_bbox_table_row_column_value_claimed"))
        for report in reports
    )
    status["violation"] = any(status.values())
    return status


def classify_text_namu_root_cause(
    text_ablation: Mapping[str, Any],
    metric_sanity: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    current = (text_ablation.get("variants") or {}).get("current_profile") or {}
    original_e = current.get(CONDITION_E) or {}
    no_echo = current.get(CONDITION_E_NO_QUERY) or {}
    original_loss = float(original_e.get("vector_interference_loss") or 0.0)
    no_echo_loss = float(no_echo.get("vector_interference_loss") or 0.0)
    baseline_text = baseline.get("TEXT_NAMU") or {}
    query_echo_dominant = original_loss > 0.15 and (original_loss - no_echo_loss) >= 0.05 and original_loss >= no_echo_loss * 1.25
    metadata_only_objective = (
        text_ablation.get("near_duplicate_distractor_policy") == "metadata_hard_negative_without_query_echo"
        and abs(original_loss - no_echo_loss) < 0.000001
    )
    primary = (
        "synthetic_near_duplicate_query_echo_on_text_lane_without_file_identity"
        if query_echo_dominant
        else (
            "near_duplicate_metadata_hard_negative_objective_without_query_echo"
            if metadata_only_objective
            else "mixed_baseline_weakness_and_near_duplicate_instability"
        )
    )
    return {
        "decomposed": bool(metric_sanity.get("passed") and (original_loss > 0.0 or metadata_only_objective)),
        "primary_cause": primary,
        "metric_formula_sanity_passed": bool(metric_sanity.get("passed")),
        "metric_artifact_or_real_instability": (
            "metric_arithmetic_valid_but_text_near_duplicate_condition_semantically_artificial"
            if query_echo_dominant
            else (
                "text_near_duplicate_condition_now_metadata_only_diagnostic"
                if metadata_only_objective
                else "real_shadow_retrieval_instability"
            )
        ),
        "evidence": {
            "original_near_duplicate_loss": round(original_loss, 6),
            "without_query_echo_loss": round(no_echo_loss, 6),
            "query_echo_delta": round(original_loss - no_echo_loss, 6),
            "baseline_hit_at_1": baseline_text.get("hit_at_1"),
            "baseline_mrr_at_10": baseline_text.get("mrr_at_10"),
            "baseline_not_in_top10_count": baseline_text.get("not_in_top10_count"),
            "citation_location_degradation_adjusted_for_missing_location_json": not bool(
                metric_sanity.get("text_namu_citation_location_degradation_counted_as_real_failure")
            ),
        },
        "explanation": (
            "TEXT_NAMU near-duplicate diagnostics now use metadata hard negatives without injecting the query text. "
            "That keeps this lane focused on same-title, same-section, same-family, or sibling-document metadata confusion "
            "instead of adding ordinary positive rows or query-echo synthetic positives. Baseline TEXT retrieval is still "
            "evaluated separately."
        ),
    }


def phase3_decision(
    metric_sanity: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    root_cause: Mapping[str, Any],
    ceiling: Mapping[str, Any],
    text_ablation: Mapping[str, Any],
) -> dict[str, Any]:
    low_diversity_respected = all(not item.get("use_for_optuna_approval") for item in ceiling.values())
    objective_uses_official_inputs = True
    ready = (
        bool(metric_sanity.get("passed"))
        and not bool(guardrails.get("violation"))
        and bool(root_cause.get("decomposed"))
        and not objective_uses_official_inputs
        and low_diversity_respected
    )
    blockers = []
    if objective_uses_official_inputs:
        blockers.append("current Phase 2 diagnostic rows are official/frozen inputs and cannot be the Optuna selection objective")
    if root_cause.get("primary_cause") == "synthetic_near_duplicate_query_echo_on_text_lane_without_file_identity":
        blockers.append("TEXT_NAMU near-duplicate objective must be rebuilt without query-echo synthetic distractors")
    return {
        "ready": ready,
        "decision": "NOT_READY_FOR_PHASE3_OPTUNA_DIAGNOSTIC" if not ready else "READY_FOR_DIAGNOSTIC_OPTUNA_WITH_NON_FROZEN_OBJECTIVE",
        "metric_sanity_passed": bool(metric_sanity.get("passed")),
        "guardrail_violation": bool(guardrails.get("violation")),
        "text_namu_loss_decomposed": bool(root_cause.get("decomposed")),
        "optuna_objective_can_use_current_official_rows": False,
        "xlsx_pdf_low_diversity_used_for_approval": False,
        "blockers": blockers,
    }


def tunable_parameter_assessment(text_ablation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "app_wired_parameters": [
            "rag_top_k",
            "rag_candidate_k",
            "rag_reranker",
            "rag_rerank_batch",
            "rag_use_mmr",
            "rag_mmr_lambda",
        ],
        "diagnostic_only_ablation_knobs_not_production_promoted": [
            "TEXT_NAMU scoring text source",
            "metadata cap length",
            "synthetic distractor query echo policy",
            "shadow BM25 materialization",
            "rerank top-N candidate slice",
        ],
        "not_currently_wired_as_safe_profile_parameters": [
            "content-only embedding profile",
            "metadata-capped embedding profile",
            "metadata-removed embedding profile",
            "hybrid BM25 shadow weight",
        ],
        "reranker_available": bool((text_ablation.get("reranker") or {}).get("available")),
        "reranker_executed": bool((text_ablation.get("reranker") or {}).get("executed")),
    }


def dataset_priorities(
    root_cause: Mapping[str, Any],
    ceiling: Mapping[str, Any],
    pdf_ablation: Mapping[str, Any],
) -> list[str]:
    return [
        "TEXT_NAMU: add near-duplicate metadata hard negatives with real same-title, same-section, same-family, and sibling-document distractors; do not add ordinary positives and do not echo the query into synthetic negatives.",
        "TEXT_NAMU: materialize parser_version/location/citation metadata or mark those dimensions not applicable before using citation/location degradation metrics.",
        "PDF_FILE_IDENTITY: add DART, public-institution, and statistical-yearbook exact/canonical filename hard negatives for year, version, similar filename, and document_version/source_file mismatches.",
        "XLSX: add Public Data Portal XLSX, KOSIS Excel, local-government statistical yearbook Excel, and internal work Excel families while preserving hidden-content redaction.",
        "PDF_CONTENT: add DART, public-institution/local-government PDF, and internal report content families with page/bbox/table evidence before treating perfect scores as robustness evidence.",
    ]


def load_text_candidates(
    lane_cfg: Mapping[str, Any],
    cases: Sequence[vector_diag.QueryCase],
    variant: str,
    *,
    max_candidates: int,
) -> list[vector_diag.Candidate]:
    expected_keys = {key for case in cases for key in case.expected_keys}
    source = next(iter(lane_cfg.get("chunk_sources") or []), None)
    if not isinstance(source, Mapping):
        return []
    path = vector_diag.resolve_path(vector_diag.required_str(source, "path"))
    candidates: list[vector_diag.Candidate] = []
    sampled: list[vector_diag.Candidate] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            candidate = text_candidate_from_row(row, variant)
            normalized_keys = {vector_diag.normalize(value) for value in candidate.match_keys}
            if normalized_keys.intersection(expected_keys):
                candidates.append(candidate)
            elif len(sampled) < max_candidates and vector_diag.stable_int(candidate.candidate_id) % 17 == 0:
                sampled.append(candidate)
    candidates.extend(sampled[: max(0, max_candidates - len(candidates))])
    return vector_diag.dedupe_candidates(candidates or sampled[:max_candidates])


def text_candidate_from_row(row: Mapping[str, Any], variant: str) -> vector_diag.Candidate:
    chunk_id = clean_text(row.get("chunk_id")) or short_hash(json.dumps(row, sort_keys=True, default=str))
    doc_id = clean_text(row.get("doc_id")) or clean_text(row.get("document_id")) or chunk_id
    title = first_text(row, ["title", "display_title", "retrieval_title"])
    section_path = row.get("section_path") if isinstance(row.get("section_path"), list) else []
    section = " > ".join(clean_text(part) for part in section_path if clean_text(part))
    section_type = clean_text(row.get("section_type"))
    chunk_text = first_text(row, ["chunk_text", "text"])
    embedding = clean_text(row.get("embedding_text"))
    if variant == "current_profile":
        text = embedding or chunk_text
    elif variant == "content_only":
        text = chunk_text or strip_embedding_metadata(embedding)
    elif variant == "metadata_capped":
        text = "\n".join(part for part in [
            "제목: " + cap_text(title, 80) if title else "",
            "섹션: " + cap_text(section, 120) if section else "",
            "섹션타입: " + cap_text(section_type, 40) if section_type else "",
            "본문:",
            chunk_text,
        ] if part)
    elif variant == "metadata_removed":
        text = strip_embedding_metadata(embedding) or chunk_text
    elif variant == "hybrid_bm25_materialized":
        text = chunk_text or strip_embedding_metadata(embedding)
    else:
        text = embedding or chunk_text
    return vector_diag.Candidate(
        candidate_id=chunk_id,
        lane="TEXT_NAMU",
        source_document_id=doc_id,
        document_family=vector_diag.family_key(title or doc_id),
        source_artifact_id=doc_id,
        parser_version=clean_text(row.get("parser_version")) or "UNKNOWN",
        file_identity="",
        template_shape="text|" + (section_type or "UNKNOWN"),
        text=text,
        citation_available=False,
        location_available=False,
        table_metadata_available=False,
        header_metadata_available=False,
    )


def evaluate_ablation_conditions(
    cases: Sequence[vector_diag.QueryCase],
    base_candidates: Sequence[vector_diag.Candidate],
    *,
    variant: str,
    score_mode: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    baseline_by_query: dict[str, Mapping[str, Any]] = {}
    for condition in [CONDITION_A, CONDITION_E, CONDITION_E_NO_QUERY]:
        for case in cases:
            candidates = candidates_for_text_condition(case, condition, base_candidates)
            result = rank_case(case, condition, candidates, score_mode=score_mode)
            if condition == CONDITION_A:
                baseline_by_query[case.query_id] = result.metrics
                row = dict(result.metrics)
            else:
                row = with_baseline_deltas(result.metrics, baseline_by_query[case.query_id])
            row["root_cause_flags"] = root_flags_for_text(condition, result.top_false)
            rows.append(row)
    return rows


def candidates_for_text_condition(
    case: vector_diag.QueryCase,
    condition: str,
    base_candidates: Sequence[vector_diag.Candidate],
) -> list[vector_diag.Candidate]:
    if condition == CONDITION_A:
        return list(base_candidates)
    if condition == CONDITION_E:
        return list(base_candidates) + vector_diag.near_duplicate_distractors(case, 2)
    if condition == CONDITION_E_NO_QUERY:
        return list(base_candidates) + near_duplicate_without_query_echo(case, 2)
    return list(base_candidates)


def near_duplicate_without_query_echo(case: vector_diag.QueryCase, limit: int) -> list[vector_diag.Candidate]:
    out: list[vector_diag.Candidate] = []
    base_identity = case.expected_file_identity or case.expected_family or case.query_id
    for idx in range(max(1, limit)):
        identity = vector_diag.mutate_identity(base_identity, idx)
        out.append(vector_diag.Candidate(
            candidate_id=f"synthetic_no_query_near_duplicate:{case.lane}:{case.query_id}:{idx}",
            lane=case.lane,
            source_document_id=f"synthetic-near-doc-{idx}",
            document_family=vector_diag.family_key(identity),
            source_artifact_id=f"synthetic-near-artifact-{idx}",
            parser_version=case.parser_version,
            file_identity=identity,
            template_shape=case.template_shape,
            text=" ".join([identity, case.template_shape]),
            citation_available=False,
            location_available=False,
            table_metadata_available=False,
            header_metadata_available=False,
            is_synthetic_distractor=True,
            distractor_kind="near_duplicate_metadata_file_name_without_query_echo",
        ))
    return out


def pdf_candidates_for_condition(
    case: vector_diag.QueryCase,
    condition: str,
    base_candidates: Sequence[vector_diag.Candidate],
) -> list[vector_diag.Candidate]:
    if condition == CONDITION_A:
        return list(base_candidates)
    if condition == CONDITION_C:
        return list(base_candidates) + vector_diag.same_lane_hard_negatives(case, "PDF_FILE_IDENTITY", base_candidates, 80)
    if condition == CONDITION_E:
        return list(base_candidates) + vector_diag.near_duplicate_distractors(case, 2)
    if condition == CONDITION_E_NO_QUERY:
        return list(base_candidates) + near_duplicate_without_query_echo(case, 2)
    return list(base_candidates)


def rank_case(
    case: vector_diag.QueryCase,
    condition: str,
    candidates: Sequence[vector_diag.Candidate],
    *,
    score_mode: str,
) -> RankedResult:
    scored = score_candidates(case, candidates, score_mode=score_mode)
    top10 = scored[:10]
    relevant_ranks = [
        idx + 1
        for idx, (_, candidate) in enumerate(scored[:50])
        if vector_diag.is_relevant(case, candidate)
    ]
    hit_rank = relevant_ranks[0] if relevant_ranks else None
    top_relevant_score = max((score for score, candidate in scored if vector_diag.is_relevant(case, candidate)), default=0.0)
    top_false_score = max((score for score, candidate in top10 if not vector_diag.is_relevant(case, candidate)), default=0.0)
    false_top10 = [candidate for _, candidate in top10 if not vector_diag.is_relevant(case, candidate)]
    top_false = false_top10[0] if false_top10 else None
    metrics = {
        "lane": case.lane,
        "condition": condition,
        "query_id": case.query_id,
        "hit_rank": hit_rank or "",
        "hit_at_1": int(bool(hit_rank and hit_rank <= 1)),
        "hit_at_3": int(bool(hit_rank and hit_rank <= 3)),
        "hit_at_5": int(bool(hit_rank and hit_rank <= 5)),
        "hit_at_10": int(bool(hit_rank and hit_rank <= 10)),
        "mrr_at_10": round((1.0 / hit_rank) if hit_rank and hit_rank <= 10 else 0.0, 6),
        "rank_loss": 0,
        "score_margin": round(top_relevant_score - top_false_score, 6),
        "score_margin_collapse": 0.0,
        "false_positive_top10_count": len(false_top10),
        "false_positive_increase": 0,
        "source_document_confusion": int(bool(top_false and top_false.document_family == case.expected_family)),
        "lane_confusion": int(bool(top_false and top_false.lane != case.lane)),
        "pdf_file_identity_confusion": int(bool(
            case.lane == "PDF_FILE_IDENTITY"
            and top_false
            and vector_diag.normalize(top_false.file_identity) != vector_diag.normalize(case.expected_file_identity)
        )),
        "citation_location_degradation": 0,
        "vector_interference_loss": 0.0,
    }
    return RankedResult(metrics=metrics, top_false=top_false)


def score_candidates(
    case: vector_diag.QueryCase,
    candidates: Sequence[vector_diag.Candidate],
    *,
    score_mode: str,
) -> list[tuple[float, vector_diag.Candidate]]:
    query = token_weights(case.query_text)
    doc_tokens = {candidate.candidate_id: token_weights(candidate.text) for candidate in candidates}
    bm25_stats = bm25_context(doc_tokens.values()) if score_mode == "hybrid_bm25" else None
    raw_bm25: dict[str, float] = {}
    if bm25_stats:
        for candidate in candidates:
            raw_bm25[candidate.candidate_id] = bm25_score(query, doc_tokens[candidate.candidate_id], bm25_stats)
    max_bm25 = max(raw_bm25.values(), default=0.0)
    scored: list[tuple[float, vector_diag.Candidate]] = []
    for candidate in candidates:
        cosine = cosine_score(query, doc_tokens[candidate.candidate_id])
        if score_mode == "hybrid_bm25":
            bm25 = raw_bm25.get(candidate.candidate_id, 0.0) / max_bm25 if max_bm25 else 0.0
            score = 0.60 * cosine + 0.40 * bm25
        else:
            score = cosine
        if case.expected_family and candidate.document_family == case.expected_family:
            score += 0.08
        if case.expected_file_identity and vector_diag.normalize(candidate.file_identity) == vector_diag.normalize(case.expected_file_identity):
            score += 0.15
        scored.append((round(score, 8), candidate))
    scored.sort(key=lambda item: (-item[0], item[1].candidate_id))
    return scored


def evaluate_rerank_variant(
    cases: Sequence[vector_diag.QueryCase],
    base_candidates: Sequence[vector_diag.Candidate],
    reranker_info: Mapping[str, Any],
) -> list[dict[str, Any]]:
    from sentence_transformers import CrossEncoder

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    model = CrossEncoder(
        "BAAI/bge-reranker-v2-m3",
        max_length=512,
        device="cuda" if reranker_info.get("cuda_available") else "cpu",
        cache_folder=str(reranker_info.get("cache_folder") or ""),
        local_files_only=True,
    )
    rows: list[dict[str, Any]] = []
    baseline_by_query: dict[str, Mapping[str, Any]] = {}
    for condition in [CONDITION_A, CONDITION_E, CONDITION_E_NO_QUERY]:
        for case in cases:
            candidates = candidates_for_text_condition(case, condition, base_candidates)
            shortlist = [candidate for _, candidate in score_candidates(case, candidates, score_mode="token_vector")[:24]]
            pairs = [(case.query_text, candidate.text[:800]) for candidate in shortlist]
            scores = model.predict(pairs, batch_size=16, show_progress_bar=False)
            reranked = sorted(zip([float(score) for score in scores], shortlist), key=lambda item: (-item[0], item[1].candidate_id))
            remaining_ids = {candidate.candidate_id for _, candidate in reranked}
            remaining = [(0.0, candidate) for candidate in candidates if candidate.candidate_id not in remaining_ids]
            ordered = reranked + remaining
            result = ranked_result_from_scored(case, condition, ordered)
            if condition == CONDITION_A:
                baseline_by_query[case.query_id] = result.metrics
                row = dict(result.metrics)
            else:
                row = with_baseline_deltas(result.metrics, baseline_by_query[case.query_id])
            row["root_cause_flags"] = root_flags_for_text(condition, result.top_false)
            rows.append(row)
    return rows


def ranked_result_from_scored(
    case: vector_diag.QueryCase,
    condition: str,
    scored: Sequence[tuple[float, vector_diag.Candidate]],
) -> RankedResult:
    top10 = list(scored[:10])
    relevant_ranks = [
        idx + 1
        for idx, (_, candidate) in enumerate(scored[:50])
        if vector_diag.is_relevant(case, candidate)
    ]
    hit_rank = relevant_ranks[0] if relevant_ranks else None
    top_relevant_score = max((score for score, candidate in scored if vector_diag.is_relevant(case, candidate)), default=0.0)
    top_false_score = max((score for score, candidate in top10 if not vector_diag.is_relevant(case, candidate)), default=0.0)
    false_top10 = [candidate for _, candidate in top10 if not vector_diag.is_relevant(case, candidate)]
    top_false = false_top10[0] if false_top10 else None
    return RankedResult(metrics={
        "lane": case.lane,
        "condition": condition,
        "query_id": case.query_id,
        "hit_rank": hit_rank or "",
        "hit_at_1": int(bool(hit_rank and hit_rank <= 1)),
        "hit_at_3": int(bool(hit_rank and hit_rank <= 3)),
        "hit_at_5": int(bool(hit_rank and hit_rank <= 5)),
        "hit_at_10": int(bool(hit_rank and hit_rank <= 10)),
        "mrr_at_10": round((1.0 / hit_rank) if hit_rank and hit_rank <= 10 else 0.0, 6),
        "rank_loss": 0,
        "score_margin": round(top_relevant_score - top_false_score, 6),
        "score_margin_collapse": 0.0,
        "false_positive_top10_count": len(false_top10),
        "false_positive_increase": 0,
        "source_document_confusion": int(bool(top_false and top_false.document_family == case.expected_family)),
        "lane_confusion": int(bool(top_false and top_false.lane != case.lane)),
        "pdf_file_identity_confusion": 0,
        "citation_location_degradation": 0,
        "vector_interference_loss": 0.0,
    }, top_false=top_false)


def with_baseline_deltas(row: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["rank_loss"] = vector_diag.rank_loss(baseline.get("hit_rank"), row.get("hit_rank"))
    out["score_margin_collapse"] = max(0.0, round(float(baseline.get("score_margin", 0.0)) - float(row.get("score_margin", 0.0)), 6))
    out["false_positive_increase"] = max(0, int(row.get("false_positive_top10_count") or 0) - int(baseline.get("false_positive_top10_count") or 0))
    out["vector_interference_loss"] = vector_loss(out)
    return out


def summarize_ablation_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for condition, items in group_by(rows, "condition").items():
        numeric = [numeric_row(row) for row in items]
        out[condition] = {
            "query_count": len(numeric),
            "hit_at_1": mean(numeric, "hit_at_1"),
            "hit_at_3": mean(numeric, "hit_at_3"),
            "hit_at_5": mean(numeric, "hit_at_5"),
            "hit_at_10": mean(numeric, "hit_at_10"),
            "mrr_at_10": mean(numeric, "mrr_at_10"),
            "not_in_top10_count": sum(1 for row in numeric if not int(row["hit_at_10"])),
            "mean_rank_loss": mean(numeric, "rank_loss"),
            "mean_score_margin_collapse": mean(numeric, "score_margin_collapse"),
            "false_positive_increase": mean(numeric, "false_positive_increase"),
            "source_document_confusion": mean(numeric, "source_document_confusion"),
            "lane_confusion": mean(numeric, "lane_confusion"),
            "pdf_file_identity_confusion": mean(numeric, "pdf_file_identity_confusion"),
            "vector_interference_loss": mean(numeric, "vector_interference_loss"),
            "score_margin_distribution": distribution([float(row["score_margin"]) for row in numeric]),
        }
    return out


def format_ablation_rows(rows: Sequence[Mapping[str, Any]], *, variant: str, lane: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append({
            "analysis_type": "ablation",
            "lane": lane,
            "variant": variant,
            "condition": row.get("condition", ""),
            "query_id": row.get("query_id", ""),
            "hit_rank": row.get("hit_rank", ""),
            "hit_at_1": row.get("hit_at_1", 0),
            "hit_at_3": row.get("hit_at_3", 0),
            "hit_at_5": row.get("hit_at_5", 0),
            "hit_at_10": row.get("hit_at_10", 0),
            "mrr_at_10": row.get("mrr_at_10", 0.0),
            "rank_loss": row.get("rank_loss", 0),
            "score_margin": row.get("score_margin", 0.0),
            "score_margin_collapse": row.get("score_margin_collapse", 0.0),
            "false_positive_top10_count": row.get("false_positive_top10_count", 0),
            "false_positive_increase": row.get("false_positive_increase", 0),
            "source_document_confusion": row.get("source_document_confusion", 0),
            "lane_confusion": row.get("lane_confusion", 0),
            "pdf_file_identity_confusion": row.get("pdf_file_identity_confusion", 0),
            "citation_location_degradation_effective": 0,
            "vector_interference_loss": row.get("vector_interference_loss", 0.0),
            "root_cause_flags": row.get("root_cause_flags", ""),
        })
    return out


def root_flags_for_text(condition: str, top_false: vector_diag.Candidate | None) -> str:
    flags = []
    if condition == CONDITION_E and top_false and top_false.is_synthetic_distractor:
        flags.append("synthetic_query_echo_distractor")
    if condition == CONDITION_E_NO_QUERY:
        flags.append("query_echo_removed")
    return ";".join(flags)


def classify_pdf_identity_failure(
    case: vector_diag.QueryCase,
    top_false: vector_diag.Candidate | None,
    row: Mapping[str, Any],
) -> list[str]:
    flags: list[str] = []
    if not top_false:
        return flags
    expected = case.expected_file_identity
    candidate = top_false.file_identity
    if is_generic_filename(expected) or is_generic_filename(candidate):
        flags.append("generic_filename_confusion")
    if year_or_month_mismatch(expected, candidate):
        flags.append("version_year_or_month_confusion")
    if top_false.source_document_id and top_false.source_document_id not in case.expected_keys:
        flags.append("source_document_confusion")
    if vector_diag.normalize(candidate) != vector_diag.normalize(expected):
        flags.append("exact_canonical_identity_mismatch")
    if top_false.lane != "PDF_FILE_IDENTITY":
        flags.append("content_identity_mixing_risk")
    return flags or ["false_positive_identity_candidate"]


def reranker_availability() -> dict[str, Any]:
    cache_folder = Path(os.environ.get("HF_HOME") or os.environ.get("TRANSFORMERS_CACHE") or "C:/llm/hf_cache")
    model_paths = [
        cache_folder / "models--BAAI--bge-reranker-v2-m3",
        cache_folder / "hub" / "models--BAAI--bge-reranker-v2-m3",
    ]
    cache_present = any(path.exists() for path in model_paths)
    try:
        import sentence_transformers  # noqa: F401
        import torch
        package_available = True
        cuda_available = bool(torch.cuda.is_available())
    except Exception:
        package_available = False
        cuda_available = False
    return {
        "available": bool(cache_present and package_available),
        "package_available": package_available,
        "local_model_cache_present": cache_present,
        "cache_folder": str(cache_folder),
        "cuda_available": cuda_available,
        "model": "BAAI/bge-reranker-v2-m3",
    }


def reranker_availability_skipped() -> dict[str, Any]:
    cache_folder = Path(os.environ.get("HF_HOME") or os.environ.get("TRANSFORMERS_CACHE") or "C:/llm/hf_cache")
    model_paths = [
        cache_folder / "models--BAAI--bge-reranker-v2-m3",
        cache_folder / "hub" / "models--BAAI--bge-reranker-v2-m3",
    ]
    return {
        "available": False,
        "package_available": None,
        "local_model_cache_present": any(path.exists() for path in model_paths),
        "cache_folder": str(cache_folder),
        "cuda_available": None,
        "model": "BAAI/bge-reranker-v2-m3",
        "probe_mode": "skipped_reranker_disabled",
    }


def summarize_component_items(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    keys = [
        "mrr_loss",
        "hit_at_1_loss",
        "hit_at_3_loss",
        "hit_at_5_loss",
        "hit_at_10_loss",
        "rank_loss",
        "score_margin_collapse",
        "false_positive_increase",
        "citation_location_degradation_raw",
        "citation_location_degradation_effective",
        "lane_confusion",
        "source_document_confusion",
        "pdf_file_identity_confusion",
        "reported_vector_interference_loss",
        "recomputed_vector_interference_loss",
    ]
    return {key: mean(items, key) for key in keys}


def vector_loss(row: Mapping[str, Any]) -> float:
    loss = 0.0
    loss += min(float(row.get("rank_loss", 0)) / 10.0, 1.0) * 0.35
    loss += min(float(row.get("score_margin_collapse", 0.0)), 1.0) * 0.25
    loss += min(float(row.get("false_positive_increase", 0)) / 10.0, 1.0) * 0.20
    loss += 0.10 * int(float(row.get("lane_confusion", 0)))
    loss += 0.10 * int(float(row.get("pdf_file_identity_confusion", 0)) or float(row.get("xlsx_table_header_confusion", 0) or 0))
    return round(loss, 6)


def bm25_context(token_counters: Iterable[Counter[str]]) -> dict[str, Any]:
    counters = list(token_counters)
    doc_count = max(1, len(counters))
    df: Counter[str] = Counter()
    lengths = []
    for counter in counters:
        lengths.append(sum(counter.values()))
        for token in counter:
            df[token] += 1
    avgdl = sum(lengths) / len(lengths) if lengths else 1.0
    idf = {token: math.log((doc_count - freq + 0.5) / (freq + 0.5) + 1.0) for token, freq in df.items()}
    return {"idf": idf, "avgdl": avgdl}


def bm25_score(query: Counter[str], doc: Counter[str], stats: Mapping[str, Any]) -> float:
    k1 = 1.2
    b = 0.75
    avgdl = float(stats.get("avgdl") or 1.0)
    doc_len = sum(doc.values()) or 1
    total = 0.0
    for token in query:
        tf = doc.get(token, 0)
        if not tf:
            continue
        denom = tf + k1 * (1 - b + b * doc_len / avgdl)
        total += float((stats.get("idf") or {}).get(token, 0.0)) * (tf * (k1 + 1)) / denom
    return total


def token_weights(text: str) -> Counter[str]:
    return Counter(tokenize(text))


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "") if len(token) > 1]


def cosine_score(query: Counter[str], doc: Counter[str]) -> float:
    if not query or not doc:
        return 0.0
    overlap = sum(query[token] * doc.get(token, 0) for token in query)
    q_norm = math.sqrt(sum(value * value for value in query.values()))
    d_norm = math.sqrt(sum(value * value for value in doc.values()))
    if not q_norm or not d_norm:
        return 0.0
    return overlap / (q_norm * d_norm)


def numeric_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in [
        "hit_at_1",
        "hit_at_3",
        "hit_at_5",
        "hit_at_10",
        "mrr_at_10",
        "rank_loss",
        "score_margin",
        "score_margin_collapse",
        "false_positive_top10_count",
        "false_positive_increase",
        "source_document_confusion",
        "lane_confusion",
        "xlsx_table_header_confusion",
        "pdf_file_identity_confusion",
        "citation_location_degradation",
        "vector_interference_loss",
    ]:
        value = out.get(key, 0)
        if value == "":
            out[key] = 0
        elif key.startswith("hit_at") or key.endswith("confusion") or key in {"rank_loss", "false_positive_top10_count", "false_positive_increase", "citation_location_degradation"}:
            out[key] = int(float(value))
        else:
            out[key] = float(value)
    return out


def group_by(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, ""))].append(row)
    return dict(grouped)


def distribution(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "p25": None, "p50": None, "p75": None, "p90": None, "p95": None, "max": None, "mean": None}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": round(ordered[0], 6),
        "p25": percentile(ordered, 0.25),
        "p50": percentile(ordered, 0.50),
        "p75": percentile(ordered, 0.75),
        "p90": percentile(ordered, 0.90),
        "p95": percentile(ordered, 0.95),
        "max": round(ordered[-1], 6),
        "mean": round(sum(ordered) / len(ordered), 6),
    }


def percentile(ordered: Sequence[float], q: float) -> float:
    if not ordered:
        return 0.0
    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return round(ordered[idx], 6)


def mean(items: Sequence[Mapping[str, Any]], key: str) -> float:
    if not items:
        return 0.0
    return round(sum(float(item.get(key) or 0.0) for item in items) / len(items), 6)


def find_lane(config: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    for lane in config.get("lanes", []) or []:
        if isinstance(lane, Mapping) and lane.get("name") == name:
            return lane
    return None


def first_text(mapping: Mapping[str, Any], fields: Sequence[str]) -> str:
    for field in fields:
        value = clean_text(mapping.get(field))
        if value:
            return value
    return ""


def strip_embedding_metadata(value: str) -> str:
    text = clean_text(value)
    marker = "본문:"
    if marker in text:
        return text.split(marker, 1)[1].strip()
    return text


def cap_text(value: str, limit: int) -> str:
    text = clean_text(value)
    return text if len(text) <= limit else text[:limit]


def is_generic_filename(value: str) -> bool:
    name = Path(clean_text(value).replace("\\", "/")).name.lower()
    stem = name[:-4] if name.endswith(".pdf") else name
    return stem in {"file", "document", "scan", "report", "untitled", "sample"} or stem.startswith("file ")


def year_or_month_mismatch(left: str, right: str) -> bool:
    left_years = YEAR_RE.findall(left or "")
    right_years = YEAR_RE.findall(right or "")
    left_months = MONTH_RE.findall(left or "")
    right_months = MONTH_RE.findall(right or "")
    return bool((left_years and right_years and left_years != right_years) or (left_months and right_months and left_months != right_months))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_by_query(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BY_QUERY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in BY_QUERY_FIELDS})


def render_markdown(report: Mapping[str, Any]) -> str:
    root = report["text_namu_root_cause"]
    phase3 = report["phase3_optuna_diagnostic_decision"]
    lines = [
        "# Retrieval Interference Root Cause Ablation",
        "",
        f"Status: `{report['status']}`",
        "",
        "Scope: diagnostic/report-only. No production index or vector writes were attempted.",
        "",
        "## TEXT_NAMU Root Cause",
        "",
        f"- Primary cause: `{root['primary_cause']}`",
        f"- Metric interpretation: `{root['metric_artifact_or_real_instability']}`",
        f"- Original near-duplicate loss: `{root['evidence']['original_near_duplicate_loss']}`",
        f"- No-query-echo near-duplicate loss: `{root['evidence']['without_query_echo_loss']}`",
        f"- Query-echo delta: `{root['evidence']['query_echo_delta']}`",
        "",
        "## Phase 3 Decision",
        "",
        f"- `phase3_optuna_diagnostic_ready`: `{str(report['phase3_optuna_diagnostic_ready']).lower()}`",
        f"- Decision: `{phase3['decision']}`",
    ]
    for blocker in phase3["blockers"]:
        lines.append(f"- Blocker: {blocker}")
    lines.extend([
        "",
        "## Baseline Weakness",
        "",
        "| Lane | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 | not in top10 | avg FP@10 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for lane, item in report["baseline_weakness"].items():
        lines.append(
            f"| `{lane}` | {item['hit_at_1']} | {item['hit_at_3']} | {item['hit_at_5']} | "
            f"{item['hit_at_10']} | {item['mrr_at_10']} | {item['not_in_top10_count']} | {item['avg_false_positives_top10']} |"
        )
    lines.extend([
        "",
        "## Ceiling Effect",
        "",
    ])
    for lane, item in report["xlsx_pdf_content_ceiling_effect"].items():
        lines.append(
            f"- `{lane}`: ceiling_effect_likely=`{str(item['ceiling_effect_likely']).lower()}`, "
            f"classification=`{item['classification']}`, source_docs=`{item['source_document_count']}`, "
            f"families=`{item['document_family_count']}`"
        )
    lines.extend([
        "",
        "## Dataset Supplementation Priorities",
        "",
    ])
    for priority in report["dataset_supplementation_priorities"]:
        lines.append(f"- {priority}")
    lines.extend([
        "",
        "## Guardrails",
        "",
    ])
    for key, value in report["guardrails"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.append("")
    return "\n".join(lines)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def short_hash(value: str) -> str:
    return hashlib.sha256(clean_text(value).encode("utf-8")).hexdigest()[:12]


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
