from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_12_xlsx_structural_locator_nonprod_improvement as v312
import rag_v3_15_xlsx_l3_table_range_locator_nonprod_improvement as v315
import rag_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod as v41


ROOT = v41.ROOT
REPORT_DIR = v41.REPORT_DIR
STATUS_JSONL = v41.STATUS_JSONL
PROGRESS_DOC = v41.PROGRESS_DOC
MEASUREMENTS_DOC = v41.MEASUREMENTS_DOC
TRIAGE_DOC = v41.TRIAGE_DOC
README = v41.README
EVAL_README = v41.EVAL_README

V4_NAME = v41.V4_NAME
V4_RUN_FAMILY = v41.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod"
EVENT_TYPE = "diagnostic_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod"
STATUS = "DIAGNOSTIC_V4_2_XLSX_LOCATOR_V2_TABLE_RANGE_CELL_STRUCTURAL_MATERIALIZATION_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_report_v1"
ROW_SCHEMA_VERSION = "rag_v4_2_xlsx_locator_v2_manifest_row_v1"
CANDIDATE_FLOW_SCHEMA_VERSION = "rag_v4_2_xlsx_locator_v2_candidate_flow_v1"
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v41.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
            "metrics.json",
            "per_query.jsonl",
            "review_packet.csv",
            "summary.json",
            "xlsx_locator_v2_candidate_components.jsonl",
            "xlsx_locator_v2_manifest.jsonl",
        }
    )
)


def clean(value: Any) -> str:
    return v41.clean(value)


def repo_relative(path: Path) -> str:
    return v41.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v41.artifact_path_text(path)


def utc_now() -> str:
    return v41.utc_now()


def sha256_file(path: Path) -> str:
    return v41.sha256_file(path)


def sha256_text(value: str) -> str:
    return v41.sha256_text(value)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v41.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v41.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v41.write_jsonl(path, rows)


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def bool_metric(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Any]:
    numerator = sum(1 for row in rows if row.get(field) is True)
    return {
        "numerator": numerator,
        "denominator": len(rows),
        "ratio": numerator / len(rows) if rows else 0.0,
        "computed_by_v4_2": False,
        "metric_role": "reference_only_seen_diagnostic",
        "optimization_target": False,
        "source_run_id": v312.RUN_ID,
    }


def source_run_references() -> dict[str, Any]:
    return {
        "v3_12_run_id": v312.RUN_ID,
        "v3_12_metrics_json": repo_relative(v312.OUTPUTS["metrics_json"]),
        "v3_12_xlsx_eval_jsonl": repo_relative(v312.OUTPUTS["xlsx_structural_locator_eval_per_query_jsonl"]),
        "v3_12_xlsx_score_components_jsonl": repo_relative(v312.OUTPUTS["xlsx_score_components_jsonl"]),
        "v3_15_run_id": v315.RUN_ID,
        "v3_15_metrics_json": repo_relative(v315.OUTPUTS["metrics_json"]),
        "v3_15_per_query_jsonl": repo_relative(v315.OUTPUTS["per_query_jsonl"]),
        "v4_1_run_id": v41.RUN_ID,
        "v4_1_report_json": repo_relative(v41.REPORT_JSON),
    }


def candidate_feature_summary(score_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    components = [as_mapping(row.get("score_components")) for row in score_rows]
    return {
        "schema_version": CANDIDATE_FLOW_SCHEMA_VERSION,
        "candidate_component_count": len(score_rows),
        "candidate_generation_modes": sorted({clean(row.get("candidate_generation_mode")) for row in score_rows}),
        "table_boundary_candidate_present_count": sum(
            1 for component in components if component.get("table_boundary_candidate_present") is True
        ),
        "header_path_propagated_count": sum(
            1 for component in components if component.get("header_path_propagated") is True
        ),
        "row_axis_alias_candidate_count": sum(
            1 for component in components if int(component.get("row_axis_alias_count") or 0) > 0
        ),
        "column_axis_alias_candidate_count": sum(
            1 for component in components if int(component.get("column_axis_alias_count") or 0) > 0
        ),
        "unit_date_number_token_candidate_count": sum(
            1 for component in components if int(component.get("unit_date_number_token_count") or 0) > 0
        ),
        "zero_signal_legacy_candidate_count": sum(
            1 for component in components if component.get("zero_signal_legacy_row_window_demotion") is True
        ),
        "source_atom_table_axis_same_workbook_count": sum(
            1 for component in components if component.get("source_atom_table_axis_same_workbook") is True
        ),
        "safe_structural_features_only": True,
        "bounded_candidate_pool": True,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "used_gold_or_expected_text": False,
        "source_component_run_id": v312.RUN_ID,
    }


def build_xlsx_locator_v2_manifest(
    eval_rows: Sequence[Mapping[str, Any]],
    score_rows_by_query: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_row in sorted(eval_rows, key=lambda row: clean(row.get("query_id"))):
        query_id = clean(source_row.get("query_id"))
        score_rows = list(score_rows_by_query.get(query_id, []))
        rows.append(
            {
                "schema_version": ROW_SCHEMA_VERSION,
                "run_id": RUN_ID,
                "source_run_id": v312.RUN_ID,
                "query_id": query_id,
                "query_text_sha256": clean(source_row.get("query_text_sha256")),
                "source_family": "XLSX",
                "source_family_separated": True,
                "candidate_generation_mode": (
                    "v4_2_family_separated_xlsx_locator_v2_structural_materialization_"
                    "from_v3_12_seen_reference"
                ),
                "source_candidate_generation_mode": clean(source_row.get("candidate_generation_mode")),
                "old_candidate_count": int(source_row.get("old_candidate_count") or 0),
                "v4_2_candidate_count": int(source_row.get("new_candidate_count") or 0),
                "candidate_component_rows": len(score_rows),
                "old_rank1_source_atom_id_original": clean(source_row.get("old_rank1_source_atom_id_original")),
                "v4_2_rank1_source_atom_id_original": clean(source_row.get("new_rank1_source_atom_id_original")),
                "table_or_range_at1": bool(source_row.get("new_table_or_range@1")),
                "table_or_range_at3": bool(source_row.get("new_table_or_range@3")),
                "cell_or_value_at1": bool(source_row.get("new_cell_or_value@1")),
                "cell_or_value_at3": bool(source_row.get("new_cell_or_value@3")),
                "sheet_at1": bool(source_row.get("new_sheet@1")),
                "sheet_at3": bool(source_row.get("new_sheet@3")),
                "failure_bucket": clean(source_row.get("failure_bucket")),
                "rank1_reranked": bool(source_row.get("rank1_reranked")),
                "locator_v2_features": candidate_feature_summary(score_rows),
                "computed_by_v4_2": False,
                "metric_role": "reference_only_seen_diagnostic",
                "seen_reference_only": True,
                "fresh_real_holdout": False,
                "workbook_disjoint_validation": False,
                "direct_normalized_value_query_matching_used": False,
                "raw_answer_value_for_query_scoring_used": False,
                "used_gold_or_expected_text": False,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
                "success_claim_allowed": False,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
            }
        )
    return rows


def build_metrics(
    rows: Sequence[Mapping[str, Any]],
    score_rows: Sequence[Mapping[str, Any]],
    v3_12_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    failure_counts = Counter(clean(row.get("failure_bucket")) for row in rows)
    component_flow = candidate_feature_summary(score_rows)
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "xlsx_locator_v2_rows": len(rows),
        "xlsx_locator_v2_candidate_component_rows": len(score_rows),
        "pdf_rows_included": 0,
        "text_rows_included": 0,
        "source_family_separated_metrics": {
            "XLSX": {
                "row_count": len(rows),
                "candidate_component_rows": len(score_rows),
                "computed_by_v4_2": False,
                "metric_role": "reference_only_seen_diagnostic",
            },
            "PDF": {"row_count": 0, "excluded": True},
            "TEXT": {"row_count": 0, "excluded": True},
        },
        "seen_reference_only_rows": len(rows),
        "workbook_disjoint_validation_rows": 0,
        "fresh_real_holdout_available": False,
        "fresh_real_holdout_sufficient": False,
        "real_blind_ood_holdout_available": False,
        "real_unseen_registry_counts": {"XLSX_workbook_disjoint": 0},
        "minimum_targets": {"xlsx_unseen_workbooks": 8},
        "query_fidelity_included_rows_per_family_target": 100,
        "table_or_range_at1": bool_metric(rows, "table_or_range_at1"),
        "table_or_range_at3": bool_metric(rows, "table_or_range_at3"),
        "cell_or_value_at1": bool_metric(rows, "cell_or_value_at1"),
        "cell_or_value_at3": bool_metric(rows, "cell_or_value_at3"),
        "table_or_range_miss_after_sheet_hit_count": failure_counts["table_or_range_miss_after_sheet_hit"],
        "cell_or_value_miss_after_range_hit_count": failure_counts["cell_or_value_miss_after_range_hit"],
        "cell_or_value_resolved_at_rank_1_count": failure_counts["cell_or_value_resolved_at_rank_1"],
        "abstain_or_disambiguation_count": failure_counts["abstain_or_no_candidate"]
        + failure_counts["abstain_or_disambiguation"],
        "sheet_or_workbook_locator_miss_count": failure_counts["sheet_or_workbook_locator_miss"],
        "locator_v2_failure_taxonomy": dict(sorted(failure_counts.items())),
        "rank1_reranked_count": sum(1 for row in rows if row.get("rank1_reranked") is True),
        "zero_signal_legacy_candidate_demotions_available_count": component_flow["zero_signal_legacy_candidate_count"],
        "locator_v2_candidate_flow": component_flow,
        "seen_reference_metrics": {
            "computed_by_v4_2": False,
            "metric_role": "reference_only_seen_diagnostic",
            "source_run_id": v312.RUN_ID,
            "table_or_range_at1": bool_metric(rows, "table_or_range_at1"),
            "table_or_range_at3": bool_metric(rows, "table_or_range_at3"),
            "cell_or_value_at1": bool_metric(rows, "cell_or_value_at1"),
            "cell_or_value_at3": bool_metric(rows, "cell_or_value_at3"),
            "v3_12_metrics_schema_version": clean(v3_12_metrics.get("schema_version")),
        },
        "validation_holdout_metrics": {
            "row_count": 0,
            "computed_by_v4_2": False,
            "fresh_real_holdout_available": False,
            "blocked_reason": "fresh real XLSX workbook-disjoint holdout unavailable",
        },
        "synthetic_ood_guard_metrics": {
            "row_count": 0,
            "counted_as_validation_success": False,
            "shortcut_leakage_guard_only": True,
        },
        "display_metadata_coverage": {
            "source_run_id": v41.RUN_ID,
            "coverage_role": "input_readiness_only_not_locator_denominator",
            "persisted_xlsx_sourceatom_display_metadata_rows": read_json(v41.REPORT_JSON)
            .get("metrics", {})
            .get("persisted_xlsx_sourceatom_display_metadata_rows", 0)
            if v41.REPORT_JSON.exists()
            else 0,
        },
        "per_query_rows": len(rows),
        "input_lineage": source_run_references(),
        "denominator_policy": (
            "v4_2 keeps XLSX locator reference metrics on the v3_12/v3_15 344-row seen diagnostic surface; "
            "v4_1 display metadata rows are input readiness only."
        ),
        "not_official_denominator": True,
        "official_metric_denominator_usage_allowed": False,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "live_db_index_cache_readiness": False,
        "gpu_required_for_this_slice": False,
        "local_llm_or_gpu_inference_required": False,
        "single_report_artifact_contract": True,
        "sidecar_primary_artifacts_suppressed": True,
        "review_csv_created": False,
        "human_review_required": False,
    }


def build_holdout_policy(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_holdout_policy_v1",
        "run_id": RUN_ID,
        "seen_reference_only_rows": metrics["seen_reference_only_rows"],
        "workbook_disjoint_validation_rows": 0,
        "fresh_real_holdout_available": False,
        "fresh_real_holdout_sufficient": False,
        "real_blind_ood_holdout_available": False,
        "seen_reference_success_claim_allowed": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "blocked_reason": "fresh real XLSX workbook-disjoint holdout unavailable",
        "interpretation": (
            "The current 344 XLSX rows are seen-reference/no-regression diagnostics only. They do not establish "
            "workbook-disjoint validation, blind/OOD quality, production readiness, promotion evidence, or "
            "fine-tuning readiness beyond infrastructure preparation."
        ),
        "minimum_targets": {"xlsx_unseen_workbooks": 8},
        "query_fidelity_included_rows_per_family_target": 100,
    }


def build_guardrails() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "family_separated_xlsx_only": True,
        "pdf_lane_excluded": True,
        "text_lane_excluded": True,
        "source_atom_evidence_bundle_evidence_truth": True,
        "source_atom_registry_canonical_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "direct_normalized_value_query_matching_used": False,
        "direct_normalized_answer_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "raw_xlsx_query_time_parsing": False,
        "raw_xlsx_query_time_parsing_forbidden": True,
        "full_workbook_sheet_scan_forbidden": True,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "source_title_or_file_name_shortcut_used": False,
        "exact_query_hack_used": False,
        "source_atom_registry_mutated": False,
        "db_or_production_namespace_written": False,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "production_routing": False,
        "official_metric": False,
        "official_metric_lift": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "representative_product_performance": False,
        "pdf_xlsx_text_collapsed_headline_product_score": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_route_policy_dry_run_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "live_db_index_cache_readiness": False,
        "single_report_artifact_contract": True,
        "review_csv_created": False,
        "gpu_required_for_this_slice": False,
        "local_llm_or_gpu_inference_required": False,
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
    holdout_policy: Mapping[str, Any],
) -> dict[str, Any]:
    summary = dict(metrics)
    summary.update(
        {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "event_type": EVENT_TYPE,
            "status": STATUS,
            "v4_name": V4_NAME,
            "run_family": V4_RUN_FAMILY,
            "run_class": "diagnostic_only_xlsx_locator_v2_structural_materialization_nonprod",
            "generated_at": utc_now(),
            "artifact_paths": dict(artifact_paths),
            "review_packet_dir": repo_relative(OUTPUT_DIR),
            "holdout_policy": dict(holdout_policy),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
            "human_review_required": False,
            "diagnostic_only": True,
            "production_routing": False,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "official_metric_lift": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "fine_tuning_readiness_only": True,
            "fine_tuning_started": False,
            "fine_tuning_executed": False,
            "live_db_index_cache_readiness": False,
            "agent_runtime_product_ready": False,
        }
    )
    return summary


def build_verification_section() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_verification_v1",
        "run_id": RUN_ID,
        "commands_required_by_goal": [
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod.py",
            "python -X utf8 ai\\scripts\\rag_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod.py --check",
            "targeted v4_2 XLSX locator v2 tests",
            "targeted artifact/status/guardrail tests",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
            "git diff --cached --check",
            "git check-ignore -v for v4_2 report.json and status.jsonl",
        ],
        "results_recorded_in_final_response": True,
        "gpu_note": "No GPU workload is executed in v4_2 because this slice performs deterministic artifact materialization.",
    }


def build_report(
    *,
    rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    holdout_policy: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    summary = build_summary(metrics=metrics, artifact_paths=artifact_paths, holdout_policy=holdout_policy)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "production_routing": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "live_db_index_cache_readiness": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "single_report_artifact_contract": True,
        "human_review_required": False,
        "review_csv_created": False,
        "artifact_paths": dict(artifact_paths),
        "source_run_references": source_run_references(),
        "input_lineage": source_run_references(),
        "denominator_policy": metrics["denominator_policy"],
        "not_official_denominator": True,
        "official_metric_denominator_usage_allowed": False,
        "summary": summary,
        "metrics": dict(metrics),
        "seen_reference_metrics": metrics["seen_reference_metrics"],
        "validation_holdout_metrics": metrics["validation_holdout_metrics"],
        "synthetic_ood_guard_metrics": metrics["synthetic_ood_guard_metrics"],
        "display_metadata_coverage": metrics["display_metadata_coverage"],
        "locator_v2_candidate_flow": metrics["locator_v2_candidate_flow"],
        "locator_v2_failure_taxonomy": metrics["locator_v2_failure_taxonomy"],
        "xlsx_locator_v2_manifest": list(rows),
        "per_query_rows": {
            "row_count": len(rows),
            "embedded_manifest_field": "xlsx_locator_v2_manifest",
            "sidecar_created": False,
        },
        "holdout_policy": dict(holdout_policy),
        "guardrails": dict(guardrails),
        "guardrail_audit": dict(guardrails),
        "verification": build_verification_section(),
        "changed_files": [
            "ai/scripts/rag_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod.py",
            "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
            "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py",
            "ai/tests/test_rag_diagnostic_guardrail_git_diff.py",
            "ai/tests/test_rag_diagnostic_status_sync.py",
            "ai/tests/test_rag_current_focused_test_profile_v1.py",
            "docs/rag-ingestion-progress.md",
            "docs/rag-ingestion-measurements.md",
            "docs/rag-ingestion-triage.md",
            "README.md",
            "ai/eval/README.md",
            "ai/eval/reports/rag-ingestion/status.jsonl",
        ],
        "residual_risks": [
            "v4_2 packages v3_12/v3_15 XLSX locator diagnostics as reference-only seen rows; it does not prove workbook-disjoint validation.",
            "v4_1 persisted display metadata is reported as input readiness only and is not used as the v4_2 locator denominator.",
            "No official metric input rows, promotion evidence, product-success evidence, threshold tuning, winner selection, or fine-tuning execution are emitted.",
            "GPU inference is not required for this slice because no model, embedding, or index rebuild workload is run.",
        ],
        "next_recommendation": (
            "Proceed to runtime-adjacent XLSX metadata bridge work only after preserving this family-separated locator v2 "
            "contract and collecting real workbook-disjoint holdout evidence."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    eval_rows = read_jsonl(v312.OUTPUTS["xlsx_structural_locator_eval_per_query_jsonl"])
    score_rows = read_jsonl(v312.OUTPUTS["xlsx_score_components_jsonl"])
    v3_12_metrics = read_json(v312.OUTPUTS["metrics_json"])
    score_rows_by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score_row in score_rows:
        score_rows_by_query[clean(score_row.get("query_id"))].append(score_row)
    rows = build_xlsx_locator_v2_manifest(eval_rows, score_rows_by_query)
    metrics = build_metrics(rows, score_rows, v3_12_metrics)
    holdout_policy = build_holdout_policy(metrics)
    guardrails = build_guardrails()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        rows=rows,
        metrics=metrics,
        guardrails=guardrails,
        holdout_policy=holdout_policy,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "metrics": metrics,
        "xlsx_locator_v2_manifest": rows,
        "guardrails": guardrails,
        "holdout_policy": holdout_policy,
    }


def remove_stale_sidecar_artifacts(target_dir: Path) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()


def write_artifacts(artifacts: Mapping[str, Any], *, output_dir: Path | None = None) -> dict[str, Any]:
    target_dir = output_dir or OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    report_path = target_dir / "report.json"
    report = dict(artifacts["report"])
    report["artifact_paths"] = {"report_json": artifact_path_text(report_path)}
    report["summary"] = dict(report["summary"])
    report["summary"]["artifact_paths"] = dict(report["artifact_paths"])
    report["summary"]["single_report_artifact_contract"] = True
    report["summary"]["sidecar_primary_artifacts_suppressed"] = True
    report["summary"]["review_csv_created"] = False
    report["metrics"] = dict(report["metrics"])
    report["metrics"]["single_report_artifact_contract"] = True
    report["metrics"]["sidecar_primary_artifacts_suppressed"] = True
    report["metrics"]["review_csv_created"] = False
    report["review_csv_created"] = False
    report["human_review_required"] = False
    remove_stale_sidecar_artifacts(target_dir)
    write_json(report_path, report)
    return report


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v41.replace_marked_entry(path, marker, entry)


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_2 XLSX locator v2 structural materialization loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_1 persisted XLSX SourceAtom display metadata loop:\n`[^`]+`;",
        "current diagnostic v4_2 XLSX locator v2 structural materialization loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_1 persisted XLSX SourceAtom display metadata loop:\n`{v41.RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")

    readme_text = README.read_text(encoding="utf-8")
    readme_text = re.sub(
        r"Current RAG status: `[^`]+`\.",
        f"Current RAG status: `{EVENT_TYPE}_ready`.",
        readme_text,
        count=1,
    )
    README.write_text(readme_text, encoding="utf-8")

    eval_readme_text = EVAL_README.read_text(encoding="utf-8")
    eval_readme_text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{EVENT_TYPE}_ready`",
        eval_readme_text,
        count=1,
    )
    eval_readme_text = eval_readme_text.replace(
        f"v4_1 is `{v41.EVENT_TYPE}_ready`.",
        f"v4_1 is `{v41.EVENT_TYPE}_ready`; v4_2 is `{EVENT_TYPE}_ready`.",
    )
    EVAL_README.write_text(eval_readme_text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    report_path = report["artifact_paths"]["report_json"]
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v41.v322.v321.v320.v319.refresh_last_updated(doc_path)
    progress_entry = (
        f"- v4_2 XLSX locator v2 table/range/cell structural materialization (`{RUN_ID}`) is "
        f"{EVENT_TYPE}_ready. It packages the v3_12/v3_15 family-separated XLSX locator surface into one "
        f"`report.json` at `{report_path}` with 344 seen-reference rows and 900 candidate-component rows. "
        "The table/range and cell/value metrics are reference-only seen diagnostics with computed_by_v4_2=false, "
        "not official metrics, not product success evidence, and not workbook-disjoint validation. v4_1 persisted "
        "display metadata is carried only as input readiness/lineage and is not used as the v4_2 denominator. "
        "Fresh real XLSX workbook-disjoint holdout remains unavailable, so promotion, threshold tuning, winner "
        "selection, production routing, and fine-tuning execution remain closed."
    )
    measurements_entry = f"""### v4_2 XLSX Locator v2 Table/Range/Cell Structural Materialization

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, family-separated XLSX-only, single `report.json`.
- Primary artifact: `{report_path}`
- Metric provenance: table/range and cell/value counts are v3_12/v3_15 reference-only seen diagnostics with `computed_by_v4_2=false`.

| Diagnostic count | Value |
| --- | ---: |
| xlsx_locator_v2_rows | {metrics["xlsx_locator_v2_rows"]} |
| xlsx_locator_v2_candidate_component_rows | {metrics["xlsx_locator_v2_candidate_component_rows"]} |
| table_or_range_at1 | {metrics["table_or_range_at1"]["numerator"]}/{metrics["table_or_range_at1"]["denominator"]} |
| table_or_range_at3 | {metrics["table_or_range_at3"]["numerator"]}/{metrics["table_or_range_at3"]["denominator"]} |
| cell_or_value_at1 | {metrics["cell_or_value_at1"]["numerator"]}/{metrics["cell_or_value_at1"]["denominator"]} |
| cell_or_value_at3 | {metrics["cell_or_value_at3"]["numerator"]}/{metrics["cell_or_value_at3"]["denominator"]} |
| table_or_range_miss_after_sheet_hit_count | {metrics["table_or_range_miss_after_sheet_hit_count"]} |
| cell_or_value_miss_after_range_hit_count | {metrics["cell_or_value_miss_after_range_hit_count"]} |
| abstain_or_disambiguation_count | {metrics["abstain_or_disambiguation_count"]} |
| sheet_or_workbook_locator_miss_count | {metrics["sheet_or_workbook_locator_miss_count"]} |
| workbook_disjoint_validation_rows | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| fine_tuning_executed | false |
| gpu_required_for_this_slice | false |

Counter source-of-truth: `report.json` embeds summary, metrics, per-query XLSX locator v2 manifest, candidate flow, failure taxonomy, source run references, holdout policy, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV, sidecar manifest, metrics sidecar, or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_2 XLSX Locator v2 Table/Range/Cell Structural Materialization Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_2 keeps PDF/TEXT lanes excluded and reports XLSX locator diagnostics separately.\n"
        "- The 344-row denominator remains the v3_12/v3_15 XLSX locator surface; v4_1 display metadata rows are input readiness only.\n"
        "- Table/range and cell/value metrics are `reference_only_seen_diagnostic` with `computed_by_v4_2=false`.\n"
        "- Fresh real workbook-disjoint holdout remains unavailable, so seen-reference/no-regression rows cannot be interpreted as product success.\n"
        "- Direct normalized-value matching, raw answer value scoring, target/gold locator use, expected/supporting gold text use, source/file title shortcuts, threshold tuning, winner selection, promotion evidence, production routing, and fine-tuning execution remain forbidden.\n"
        "- GPU is not required for this slice because the runner performs deterministic JSON materialization only; future embedding/LLM/index workloads should prefer GPU when available.\n"
        "- Next lane: runtime-adjacent XLSX metadata bridge only after preserving this holdout-aware locator contract.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v41.v322.v321.v320.v319.refresh_last_updated(doc_path)


def artifact_sha256_from_report_paths(artifact_paths: Mapping[str, str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path_text in artifact_paths.items():
        path = Path(path_text)
        if not path.is_absolute():
            path = ROOT / path_text
        if path.exists():
            hashes[f"{key}_sha256"] = sha256_file(path)
    return hashes


def append_status_event(report: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": artifact_sha256_from_report_paths(report["artifact_paths"]),
        "report_json_created": True,
        "review_csv_created": False,
        "summary_json_created": False,
        "per_run_markdown_created": False,
        "raw_llm_response_payload_created": False,
        "prompt_payload_created": False,
        "xlsx_locator_v2_manifest_jsonl_created": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
        "holdout_policy": dict(report["holdout_policy"]),
    }
    event.pop("per_query_rows", None)
    event.pop("seen_reference_metrics", None)
    event.pop("source_family_separated_metrics", None)
    event.pop("locator_v2_candidate_flow", None)
    event.pop("locator_v2_failure_taxonomy", None)
    event.pop("input_lineage", None)
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def run_write() -> dict[str, Any]:
    artifacts = build_artifacts()
    report = write_artifacts(artifacts)
    update_docs(report)
    append_status_event(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        artifacts = build_artifacts()
        metrics = artifacts["metrics"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["report"]["summary"]["status"],
                    "xlsx_locator_v2_rows": metrics["xlsx_locator_v2_rows"],
                    "xlsx_locator_v2_candidate_component_rows": metrics["xlsx_locator_v2_candidate_component_rows"],
                    "table_or_range_at1": metrics["table_or_range_at1"],
                    "cell_or_value_at1": metrics["cell_or_value_at1"],
                    "official_metric_input_rows": metrics["official_metric_input_rows"],
                    "gpu_required_for_this_slice": metrics["gpu_required_for_this_slice"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    report = run_write()
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "report": report["artifact_paths"]["report_json"],
                "status": report["summary"]["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
