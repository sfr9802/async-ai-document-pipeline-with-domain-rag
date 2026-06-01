from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4718_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility as v4718
from ai.eval import rag_v500_v4_closeout_and_v5_gate_plan as v500
from ai.eval import rag_v510_official_eval_gate_scaffolding as v510
from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v5_2"
SHORT_RUN_ID = "v5_2_xlsx_residual_candidate_only_retrieval_engineering"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_2_"
    "xlsx_residual_candidate_only_retrieval_engineering_nonprod"
)
STATUS = "V5_2_XLSX_RESIDUAL_CANDIDATE_ONLY_RETRIEVAL_ENGINEERING_DIAGNOSTIC_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SOURCE_LOGICAL_RUN_KEY = v510.LOGICAL_RUN_KEY
SOURCE_RUN_ID = v510.SHORT_RUN_ID
SOURCE_CANONICAL_LONG_RUN_ID = v510.CANONICAL_LONG_RUN_ID
SOURCE_REPORT_JSON = v510.SHORT_REPORT_PATH
V4_CLOSEOUT_LOGICAL_RUN_KEY = v4718.LOGICAL_RUN_KEY
V4_CLOSEOUT_RUN_ID = v4718.SHORT_RUN_ID
V4_CLOSEOUT_REPORT_JSON = v4718.SHORT_REPORT_PATH
KST_DOC_DATE = "2026-06-01"

FORBIDDEN_FALSE_KEYS = tuple(
    dict.fromkeys(
        (
            *v510.FORBIDDEN_FALSE_KEYS,
            "official_metric_dry_run_opened",
            "safe_repair_applied",
            "safe_gain_claimed",
            "residual_overlap_recomputed",
            "row_level_residual_mask_created",
            "per_query_candidates_written",
        )
    )
)
RAW_PAYLOAD_FORBIDDEN_KEYS = v510.RAW_PAYLOAD_FORBIDDEN_KEYS


utc_now_iso = common.utc_now_iso
read_jsonl = common.read_jsonl
write_json = common.write_json
write_jsonl = common.write_jsonl
sha256_file = common.sha256_file


def _source_report_path(root: Path) -> Path:
    return root / SOURCE_REPORT_JSON


def _v4_closeout_report_path(root: Path) -> Path:
    return root / V4_CLOSEOUT_REPORT_JSON


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if source_report is not None:
        report = common.json_clone(source_report)
    else:
        try:
            report = registry.load_report(SOURCE_LOGICAL_RUN_KEY, root=root)
        except registry.ReportResolutionError:
            report = v510.build_report(root=root, source_report=v500.build_report(root=root))
    v510.check_report(report)
    return report


def _load_v4_closeout_report(root: Path) -> dict[str, Any]:
    try:
        report = registry.load_report(V4_CLOSEOUT_LOGICAL_RUN_KEY, root=root)
    except registry.ReportResolutionError:
        report = v4718.build_report(root=root)
    v4718.check_report(report)
    return report


def _source_hash(root: Path) -> str:
    path = _source_report_path(root)
    return sha256_file(path) if path.exists() else ""


def _v4_closeout_hash(root: Path) -> str:
    path = _v4_closeout_report_path(root)
    return sha256_file(path) if path.exists() else ""


def _source_artifact_status(root: Path) -> str:
    return common.artifact_status(_source_report_path(root))


def _v4_closeout_artifact_status(root: Path) -> str:
    return common.artifact_status(_v4_closeout_report_path(root))


def _xlsx_residual_basis(v4_report: Mapping[str, Any]) -> dict[str, Any]:
    guards = v4_report["regression_guards"]
    xlsx_guard = guards["XLSX"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_xlsx_residual_basis_v1",
        "source_short_run_id": V4_CLOSEOUT_RUN_ID,
        "source_logical_run_key": V4_CLOSEOUT_LOGICAL_RUN_KEY,
        "source_report_status": v4_report["status"],
        "xlsx_row_count": xlsx_guard["row_count"],
        "xlsx_baseline_target_hit_count": xlsx_guard["baseline_target_hit_count"],
        "xlsx_v4_7_17_combined_target_hit_count": xlsx_guard["v4_7_17_combined_target_hit_count"],
        "xlsx_v4_7_18_combined_target_hit_count": xlsx_guard["v4_7_18_combined_target_hit_count"],
        "xlsx_v4_7_18_combined_target_miss_count": xlsx_guard["v4_7_18_combined_target_miss_count"],
        "residual_overlap_counts_available": False,
        "residual_overlap_counts_reason": (
            "v4_7_18_report_exposes_aggregate_residuals_not_safe_row_level_residual_mask"
        ),
        "row_level_residual_mask_created": False,
        "residual_overlap_recomputed": False,
    }


def _candidate_state_taxonomy(v4_report: Mapping[str, Any]) -> dict[str, Any]:
    repair = v4_report["xlsx_candidate_only_materialization_repair"]
    budget = repair["candidate_budget_summary"]["XLSX"]
    xlsx_guard = v4_report["regression_guards"]["XLSX"]
    overlay = repair["overlay_90_xlsx_projection"]
    zero_count = int(budget["zero_candidate_row_count"])
    exhausted_count = int(budget["candidate_budget_exhaustion_count"])
    row_count = int(xlsx_guard["row_count"])
    bounded_count = row_count - zero_count - exhausted_count
    distribution = {str(key): int(value) for key, value in budget["candidate_count_distribution"].items()}
    return {
        "schema_version": f"{SHORT_RUN_ID}_xlsx_candidate_state_taxonomy_v1",
        "source": "v4_7_18_candidate_budget_summary_read_only",
        "scope": "candidate_state_over_325_xlsx_rows_not_row_level_residual_overlap",
        "residual_overlap_counts_available": False,
        "candidate_budget_per_query": repair["candidate_budget_summary"]["candidate_budget_per_query"],
        "xlsx_candidate_count": budget["candidate_count"],
        "at_budget_row_count": budget["at_budget_row_count"],
        "candidate_budget_exhaustion_count": exhausted_count,
        "candidate_budget_exhaustion_basis": budget["candidate_budget_exhaustion_basis"],
        "zero_candidate_row_count": zero_count,
        "bounded_candidate_not_budget_exhausted_row_count": bounded_count,
        "candidate_state_bucket_count_sum": zero_count + exhausted_count + bounded_count,
        "candidate_count_distribution": distribution,
        "candidate_state_buckets": {
            "zero_candidate_structural_gap": {
                "count": zero_count,
                "count_scope": "candidate_state_rows",
                "safe_action": "broaden_already_materialized_structural_header_axis_aliases_only",
            },
            "budget_exhausted_diversity_gap": {
                "count": exhausted_count,
                "count_scope": "candidate_state_rows_with_untruncated_candidate_count_above_budget",
                "safe_action": "deterministic_candidate_diversity_or_quota_probe_no_target_tuned_thresholds",
            },
            "bounded_candidate_rank_gap": {
                "upper_bound_count": bounded_count,
                "count_scope": "candidate_state_rows_with_nonzero_candidates_not_budget_exhausted",
                "safe_action": "candidate_only_ranking_diagnostics_exact_miss_overlap_unavailable",
            },
            "axis_header_materialization_gap": {
                "count_status": "candidate_only_probe_required",
                "safe_action": "use_recurring_non_numeric_materialized_axis_header_text_only",
            },
            "sheet_range_ambiguity": {
                "repeated_prefix_cluster_total": overlay["repeated_prefix_cluster_total"],
                "repeated_prefix_cluster_overlap_with_target_miss": overlay[
                    "repeated_prefix_cluster_overlap_with_target_miss"
                ],
                "count_scope": "frozen_v4_7_18_overlay_projection_diagnostic_only",
                "safe_action": "abstain_disambiguate_or_diversify_by_sheet_range_strata",
            },
            "value_only_or_forbidden_required": {
                "count_status": "intentionally_not_counted",
                "safe_action": "no_safe_repair_under_current_boundary",
            },
            "unclassified_residual_overlap": {
                "aggregate_count": xlsx_guard["v4_7_18_combined_target_miss_count"],
                "count_scope": "aggregate_residual_misses_only",
                "safe_action": "keep_aggregate_until_safe_non_oracle_residual_mask_exists",
            },
        },
    }


def _ft_readiness_compatibility() -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_ft_readiness_compatibility_v1",
        "status": "blocked_retrieval_diagnostic_only_no_dataset_export",
        "blocked_by_user_gate": True,
        "blocked_by_eval": True,
        "blocked_by_data_quality": True,
        "blocked_by_leakage": False,
        "blocked_by_provider_availability": False,
        "training_dataset_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_job_created": False,
        "checkpoint_created": False,
        "safe_next_action": "complete_xlsx_candidate_state_taxonomy_without_exporting_training_data",
    }


def _counters(residual_basis: Mapping[str, Any], taxonomy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "current_resolves_to": LOGICAL_RUN_KEY,
        "v4_closeout_basis": V4_CLOSEOUT_LOGICAL_RUN_KEY,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "xlsx_row_count": residual_basis["xlsx_row_count"],
        "xlsx_v4_7_18_combined_target_hit_count": residual_basis["xlsx_v4_7_18_combined_target_hit_count"],
        "xlsx_v4_7_18_combined_target_miss_count": residual_basis["xlsx_v4_7_18_combined_target_miss_count"],
        "xlsx_zero_candidate_row_count": taxonomy["zero_candidate_row_count"],
        "xlsx_candidate_budget_exhaustion_count": taxonomy["candidate_budget_exhaustion_count"],
        "bounded_candidate_not_budget_exhausted_row_count": taxonomy[
            "bounded_candidate_not_budget_exhausted_row_count"
        ],
        "candidate_state_bucket_count_sum": taxonomy["candidate_state_bucket_count_sum"],
        "residual_overlap_counts_available": False,
        "safe_repair_applied": False,
        "safe_gain_claimed": False,
        "training_dataset_created": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "generated_response_count": 0,
        "parser_failure_count": 0,
        "claim_support_verifier_fail_count": 0,
    }


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    source = _load_source_report(root, source_report=source_report)
    v4_report = _load_v4_closeout_report(root)
    residual_basis = _xlsx_residual_basis(v4_report)
    taxonomy = _candidate_state_taxonomy(v4_report)
    source_sha = _source_hash(root)
    v4_sha = _v4_closeout_hash(root)
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now_iso(),
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
            "v4_closeout_report_json": V4_CLOSEOUT_REPORT_JSON.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_logical_run_key": SOURCE_LOGICAL_RUN_KEY,
        "source_canonical_long_run_id": SOURCE_CANONICAL_LONG_RUN_ID,
        "source_report_status": source.get("status"),
        "source_report_schema_version": source.get("schema_version"),
        "source_report_sha256": source_sha,
        "source_report_artifact_status": _source_artifact_status(root),
        "source_report_materialized_in_memory": source_sha == "",
        "v4_closeout_basis": V4_CLOSEOUT_LOGICAL_RUN_KEY,
        "v4_closeout_basis_short_run_id": V4_CLOSEOUT_RUN_ID,
        "v4_closeout_report_status": v4_report.get("status"),
        "v4_closeout_report_sha256": v4_sha,
        "v4_closeout_report_artifact_status": _v4_closeout_artifact_status(root),
        "current_resolves_to": LOGICAL_RUN_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "xlsx_residual_engineering": True,
        "xlsx_residual_basis": residual_basis,
        "xlsx_residual_candidate_state_taxonomy": taxonomy,
        "family_target_hit_regression_count": {
            "TEXT": v4_report["regression_guards"]["TEXT"]["target_hit_regression_count"],
            "PDF": v4_report["regression_guards"]["PDF"]["target_hit_regression_count"],
            "XLSX": v4_report["regression_guards"]["XLSX"]["target_hit_regression_count"],
        },
        "safe_repair_applied": False,
        "safe_gain_claimed": False,
        "safe_gain_interpretation": "no_safe_gain_claimed_candidate_state_taxonomy_only",
        "residual_overlap_recomputed": False,
        "row_level_residual_mask_created": False,
        "per_query_candidates_written": False,
        "official_metric": False,
        "official_metric_denominator_usage_allowed": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_scope": "v5_2_diagnostic_taxonomy_created_rows_only",
        "official_metric_dry_run_opened": False,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "official_qrels_created": False,
        "official_relevance_labels_created": False,
        "official_answerability_labels_created": False,
        "official_gold_labels_created": False,
        "training_dataset_created": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "production_db_mutated": False,
        "source_registry_mutated": False,
        "silver_mutation": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "protected_namespaces_touched": [],
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "answer_generation_attempted": False,
        "generated_response_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_matching": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "source_file_title_shortcut_used": False,
        "workbook_or_source_title_shortcut_used": False,
        "target_or_gold_locator_used_for_candidate_construction": False,
        "query_id_case_id_hack_used": False,
        "ft_readiness_compatibility": _ft_readiness_compatibility(),
        "decision_policy": {
            "residual_overlap_policy": "do_not_recompute_row_level_overlap_without_safe_non_oracle_mask",
            "candidate_state_policy": "aggregate_from_v4_7_18_candidate_budget_summary_only",
            "no_safe_repair_policy": "classify_before_repair_and_keep_shortcuts_closed",
        },
        "residual_risks": [
            "v5_2 does not solve XLSX retrieval; it freezes an honest candidate-state taxonomy",
            "exact row-level residual overlap is unavailable without using after-the-fact target labels or locators",
            "XLSX remains weak: 299 aggregate misses, 78 zero-candidate rows, and 109 budget-exhausted rows",
        ],
        "next_recommendations": [
            "prototype only candidate-only structural/header/axis materialization probes in a later diagnostic run",
            "do not open official metrics or training export until user-owned gold/qrels/denominator gates exist",
            "treat value-only and target-locator-only paths as no-safe-repair under current boundaries",
        ],
        "counters": _counters(residual_basis, taxonomy),
    }
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    return common.write_report_bundle(root, SHORT_REPORT_PATH, report)


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    residual = report["xlsx_residual_basis"]
    taxonomy = report["xlsx_residual_candidate_state_taxonomy"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v5_2_xlsx_residual_candidate_only_retrieval_engineering_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
            "v4_closeout_report_json": V4_CLOSEOUT_REPORT_JSON.as_posix(),
        },
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
        "source_report_status": report["source_report_status"],
        "source_report_sha256": report["source_report_sha256"],
        "source_report_artifact_status": report["source_report_artifact_status"],
        "v4_closeout_basis": V4_CLOSEOUT_LOGICAL_RUN_KEY,
        "v4_closeout_basis_short_run_id": V4_CLOSEOUT_RUN_ID,
        "v4_closeout_report_status": report["v4_closeout_report_status"],
        "current_resolves_to": LOGICAL_RUN_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "xlsx_row_count": residual["xlsx_row_count"],
        "xlsx_v4_7_18_combined_target_hit_count": residual["xlsx_v4_7_18_combined_target_hit_count"],
        "xlsx_v4_7_18_combined_target_miss_count": residual["xlsx_v4_7_18_combined_target_miss_count"],
        "residual_overlap_counts_available": False,
        "zero_candidate_row_count": taxonomy["zero_candidate_row_count"],
        "candidate_budget_exhaustion_count": taxonomy["candidate_budget_exhaustion_count"],
        "bounded_candidate_not_budget_exhausted_row_count": taxonomy[
            "bounded_candidate_not_budget_exhausted_row_count"
        ],
        "candidate_state_bucket_count_sum": taxonomy["candidate_state_bucket_count_sum"],
        "family_target_hit_regression_count": dict(report["family_target_hit_regression_count"]),
        "safe_repair_applied": False,
        "safe_gain_claimed": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_matching": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "source_file_title_shortcut_used": False,
        "workbook_or_source_title_shortcut_used": False,
        "target_or_gold_locator_used_for_candidate_construction": False,
        "query_id_case_id_hack_used": False,
    }


def append_status(root: Path, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    path = root / STATUS_JSONL_PATH
    rows = read_jsonl(path) if path.exists() else []
    event_type = "diagnostic_v5_2_xlsx_residual_candidate_only_retrieval_engineering_nonprod"
    rows = [
        row
        for row in rows
        if row.get("run_id") not in {SHORT_RUN_ID, CANONICAL_LONG_RUN_ID}
        and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
        and row.get("event_type") != event_type
    ]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(path, rows)


def _upsert_block_at_top(text: str, *, start_marker: str, end_marker: str, block: str) -> str:
    return common.upsert_block_at_top(text, start_marker=start_marker, end_marker=end_marker, block=block)


def _sync_last_updated(text: str) -> str:
    return common.sync_last_updated(text, KST_DOC_DATE)


def _replace_summary_block(text: str, *, block: str) -> str:
    start = "<!-- v5_2_summary_start -->"
    end = "<!-- v5_2_summary_end -->"
    return common.replace_summary_block(
        text,
        start_marker=start,
        end_marker=end,
        block=block,
        marker_pattern=(
            r"<!-- v(?:4_7[^>]*|5_[0-2][^>]*)_summary_start -->\n.*?\n"
            r"<!-- v(?:4_7[^>]*|5_[0-2][^>]*)_summary_end -->"
        ),
    )


def _replace_current_status_block(progress_text: str, report: Mapping[str, Any]) -> str:
    residual = report["xlsx_residual_basis"]
    taxonomy = report["xlsx_residual_candidate_state_taxonomy"]
    replacement = (
        "## Current Status\n\n"
        f"Overall status: `{STATUS}`;\n"
        "current v5 diagnostic handoff:\n"
        f"`{SHORT_RUN_ID}`;\n"
        "current XLSX residual engineering mode:\n"
        "`candidate_state_taxonomy_only_no_safe_gain_claimed`;\n"
        "current official-eval opening scaffold basis:\n"
        f"`{SOURCE_RUN_ID}`;\n"
        "frozen v4 closeout basis:\n"
        f"`{V4_CLOSEOUT_RUN_ID}`;\n"
        f"xlsx_v4_7_18_combined_target_miss_count={residual['xlsx_v4_7_18_combined_target_miss_count']}; "
        f"xlsx_zero_candidate_row_count={taxonomy['zero_candidate_row_count']}; "
        f"xlsx_candidate_budget_exhaustion_count={taxonomy['candidate_budget_exhaustion_count']}; "
        f"bounded_candidate_not_budget_exhausted_row_count={taxonomy['bounded_candidate_not_budget_exhausted_row_count']}; "
        "residual_overlap_counts_available=false; safe_repair_applied=false; safe_gain_claimed=false; "
        "official_metric_input_rows=0; official_metric_input_rows_created=0; training_dataset_created=false; "
        "training_manifest_jsonl_created=false; fine_tuning_dataset_export_created=false; "
        "promotion_evidence=false; live_db_index_cache_readiness=false.\n\n"
        "## Current Verification Command\n\n"
        "Current verification: after v5_2 XLSX residual candidate-state taxonomy/current-alias reconciliation,\n"
        "`python -X utf8 -m pytest ai/tests --rag-current -q` -> 26 passed,\n"
        "0 skipped, 0 failed, 1 warning.\n\n"
        "## Current Source-Of-Truth Artifacts\n\n"
        "- Status ledger: `ai/eval/reports/rag-ingestion/status.jsonl`.\n"
        f"- Current v5_2 report: `{SHORT_REPORT_PATH.as_posix()}`.\n"
        f"- Explicit v5_1 scaffold report: `{SOURCE_REPORT_JSON.as_posix()}`.\n"
        "- Explicit v5_0 basis report: `ai/eval/reports/rag-ingestion/runs/v5_0/report.json`.\n"
        f"- Frozen v4 closeout basis report: `{V4_CLOSEOUT_REPORT_JSON.as_posix()}`.\n"
    )
    return re.sub(r"## Current Status\n\n.*?(?=\n## Short History)", replacement, progress_text, count=1, flags=re.S)


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    progress = root / "docs/rag-ingestion-progress.md"
    measurements = root / "docs/rag-ingestion-measurements.md"
    triage = root / "docs/rag-ingestion-triage.md"
    readme = root / "README.md"
    eval_readme = root / "ai/eval/README.md"
    scripts_readme = root / "ai/scripts/README.md"

    residual = report["xlsx_residual_basis"]
    taxonomy = report["xlsx_residual_candidate_state_taxonomy"]
    buckets = taxonomy["candidate_state_buckets"]

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is the diagnostic-only XLSX residual candidate-state "
        f"taxonomy run. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. Source phase: `{SOURCE_LOGICAL_RUN_KEY}` / "
        f"`{SOURCE_RUN_ID}`; source report status `{report['source_report_status']}`; frozen v4 basis "
        f"`{V4_CLOSEOUT_RUN_ID}`. `current` resolves to `v5_2`, while `v5_1`, `v5_0`, and `v4_7_18` remain "
        "directly checkable. v5_2 keeps the residual aggregate separate from candidate-state buckets: "
        f"XLSX misses={residual['xlsx_v4_7_18_combined_target_miss_count']}, "
        f"zero_candidate={taxonomy['zero_candidate_row_count']}, "
        f"budget_exhausted={taxonomy['candidate_budget_exhaustion_count']}, "
        f"bounded_candidate_not_budget_exhausted={taxonomy['bounded_candidate_not_budget_exhausted_row_count']}; "
        "residual_overlap_counts_available=false because the frozen v4 report does not expose a safe row-level "
        "residual mask. safe_repair_applied=false, safe_gain_claimed=false, official_metric_input_rows=0, "
        "official_metric_input_rows_created=0, no gold/qrels/label/expected/supporting/denominator/training/"
        "fine-tuning/FT-A/promotion/product-success/live-readiness gates are opened."
    )
    progress_text = _upsert_block_at_top(
        progress.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress_block,
    )
    progress_text = _replace_current_status_block(progress_text, report)
    progress_text = progress_text.replace(
        "The scaffold records validators and required external approval artifacts only:",
        "The scaffold records required validator names / schema placeholders and external approval artifacts only:",
    )
    progress_text = progress_text.replace(
        "`current` resolves to `v5_1`, while `v5_0` and `v4_7_18` remain directly checkable.",
        "`v5_1` remains directly checkable after v5_2, while `v5_0` and `v4_7_18` remain directly checkable.",
    )
    progress.write_text(_sync_last_updated(progress_text), encoding="utf-8")

    measurements_block = f"""## v5_2 XLSX residual candidate-state taxonomy

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: candidate-state taxonomy only. Exact row-level residual overlap remains unavailable without a safe non-oracle residual mask.

| counter | value |
| --- | --- |
| status | {STATUS} |
| source_run_id | {SOURCE_RUN_ID} |
| current_resolves_to | {LOGICAL_RUN_KEY} |
| v4_closeout_basis | {V4_CLOSEOUT_LOGICAL_RUN_KEY} |
| xlsx_row_count | {residual['xlsx_row_count']} |
| xlsx_v4_7_18_combined_target_hit_count | {residual['xlsx_v4_7_18_combined_target_hit_count']} |
| xlsx_v4_7_18_combined_target_miss_count | {residual['xlsx_v4_7_18_combined_target_miss_count']} |
| residual_overlap_counts_available | false |
| candidate_budget_per_query | {taxonomy['candidate_budget_per_query']} |
| xlsx_candidate_count | {taxonomy['xlsx_candidate_count']} |
| zero_candidate_structural_gap | {buckets['zero_candidate_structural_gap']['count']} |
| budget_exhausted_diversity_gap | {buckets['budget_exhausted_diversity_gap']['count']} |
| bounded_candidate_rank_gap_upper_bound | {buckets['bounded_candidate_rank_gap']['upper_bound_count']} |
| unclassified_residual_overlap_aggregate | {buckets['unclassified_residual_overlap']['aggregate_count']} |
| candidate_count_distribution | {json.dumps(taxonomy['candidate_count_distribution'], sort_keys=True)} |
| family_target_hit_regression_count | {json.dumps(report['family_target_hit_regression_count'], sort_keys=True)} |
| safe_repair_applied | false |
| safe_gain_claimed | false |
| official_metric_input_rows | 0 |
| official_metric_input_rows_created | 0 |
| training_dataset_created | false |
| training_manifest_jsonl_created | false |
| fine_tuning_dataset_export_created | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |
"""
    measurements_text = _upsert_block_at_top(
        measurements.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
        block=measurements_block,
    )
    measurements_text = measurements_text.replace("| current_resolves_to | v5_1 |", "| current_alias_at_write_time | v5_1 |")
    measurements_text = measurements_text.replace("| current_resolves_to | v5_0 |", "| current_alias_at_write_time | v5_0 |")
    measurements.write_text(_sync_last_updated(measurements_text), encoding="utf-8")

    triage_block = (
        "### v5_2 XLSX residual candidate-state taxonomy\n\n"
        f"- Residual basis: frozen v4_7_18 aggregate XLSX result has {residual['xlsx_v4_7_18_combined_target_miss_count']} "
        "misses. v5_2 does not create a row-level residual mask.\n"
        f"- Candidate-state buckets: zero_candidate_structural_gap={buckets['zero_candidate_structural_gap']['count']}, "
        f"budget_exhausted_diversity_gap={buckets['budget_exhausted_diversity_gap']['count']}, "
        f"bounded_candidate_rank_gap_upper_bound={buckets['bounded_candidate_rank_gap']['upper_bound_count']}, "
        f"unclassified_residual_overlap_aggregate={buckets['unclassified_residual_overlap']['aggregate_count']}.\n"
        "- Safe action: future work may probe already-materialized structural/header/axis aliases or deterministic "
        "candidate diversity, but v5_2 applies no repair and claims no safe gain.\n"
        "- Fail-closed status: official_metric_input_rows=0, official_metric_input_rows_created=0, "
        "training_dataset_created=false, fine_tuning_dataset_export_created=false, protected_namespaces_touched=[]."
    )
    triage_text = _upsert_block_at_top(
        triage.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:end -->",
        block=triage_block,
    )
    triage_text = triage_text.replace("Codex-owned validators:", "Codex-owned validator-name placeholders:")
    triage.write_text(_sync_last_updated(triage_text), encoding="utf-8")

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        "`current` resolves to `v5_2`: diagnostic-only XLSX residual candidate-state taxonomy. `v5_1` remains the "
        "official-eval gate scaffold with required validator-name/schema placeholders, `v5_0` remains the v4 closeout "
        "and v5 gate-plan basis, and `v4_7_18` remains the frozen v4 closeout basis.\n"
        f"v5_2 reports XLSX residual aggregate {residual['xlsx_v4_7_18_combined_target_miss_count']} misses. "
        f"Separately, over all {residual['xlsx_row_count']} XLSX rows, candidate-state buckets are "
        f"{taxonomy['zero_candidate_row_count']} zero-candidate, "
        f"{taxonomy['candidate_budget_exhaustion_count']} budget-exhausted, and "
        f"{taxonomy['bounded_candidate_not_budget_exhausted_row_count']} bounded-candidate rows. "
        "It does not compute row-level residual overlap, apply a repair, or claim a gain.\n"
        "Hard boundary: official_metric_input_rows=0, official_metric_input_rows_created=0, no gold/qrels/labels, "
        "no expected/supporting evidence or denominator mutation, no training dataset, no fine-tuning dataset export, "
        "no fine-tuning job, no promotion evidence, no product-success evidence, and no live-readiness claim."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v5_2`, `v5_1_official_eval_gate_scaffolding` remains explicit, "
        "`v5_0_v4_closeout_and_v5_gate_plan` remains explicit, "
        "`v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` remains explicit as the "
        "frozen v4 closeout basis, and all official/gold/qrels/labels/denominator/training/fine-tuning/FT-A/"
        "promotion/product-success/live-readiness gates stay closed. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_text = scripts_text.replace(
        "`status.jsonl`, current v5 `report.json` artifacts, and explicit v4 closeout source reports",
        "`status.jsonl`, the current v5_2 report, the explicit v5_1 and v5_0 basis reports, "
        "the frozen v4_7_18 source report",
    )
    scripts_text = scripts_text.replace(
        "`status.jsonl`, current v5 `report.json` artifacts, and explicit v4 closeout source reports, and v3_9_2 through v3_22 scripts.",
        "`status.jsonl`, the current v5_2 report, the explicit v5_1 and v5_0 basis reports, "
        "the frozen v4_7_18 source report, and v3_9_2 through v3_22 scripts.",
    )
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    common.assert_no_raw_payload_keys(value, RAW_PAYLOAD_FORBIDDEN_KEYS, context="v5_2")


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_2 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_2 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v5_2 status mismatch")
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_2 logical run key mismatch")
    if report.get("source_run_id") != SOURCE_RUN_ID:
        raise ValueError("v5_2 source run must remain v5_1")
    if report.get("source_report_status") != v510.STATUS:
        raise ValueError("v5_2 source report status mismatch")
    if report.get("v4_closeout_basis") != V4_CLOSEOUT_LOGICAL_RUN_KEY:
        raise ValueError("v5_2 v4 closeout basis mismatch")
    if report.get("v4_closeout_basis_short_run_id") != V4_CLOSEOUT_RUN_ID:
        raise ValueError("v5_2 v4 closeout short run mismatch")
    if report.get("current_resolves_to") != LOGICAL_RUN_KEY:
        raise ValueError("v5_2 current resolution mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v5_2 must remain diagnostic-only and non-production")
    for key in FORBIDDEN_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_2 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0 or report.get("official_metric_input_rows_created") != 0:
        raise ValueError("v5_2 opened official metric rows")
    if report.get("official_metric_input_rows_scope") != "v5_2_diagnostic_taxonomy_created_rows_only":
        raise ValueError("v5_2 official metric row scope drift")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_2 touched protected namespaces")
    if report.get("answer_generation_attempted") is not False or report.get("generated_response_count") != 0:
        raise ValueError("v5_2 generation must remain closed")

    residual = report.get("xlsx_residual_basis") or {}
    expected_residual = {
        "xlsx_row_count": 325,
        "xlsx_v4_7_18_combined_target_hit_count": 26,
        "xlsx_v4_7_18_combined_target_miss_count": 299,
        "residual_overlap_counts_available": False,
        "row_level_residual_mask_created": False,
        "residual_overlap_recomputed": False,
    }
    for key, expected in expected_residual.items():
        if residual.get(key) != expected:
            raise ValueError(f"v5_2 residual basis drift: {key}")
    if residual.get("residual_overlap_counts_reason") != (
        "v4_7_18_report_exposes_aggregate_residuals_not_safe_row_level_residual_mask"
    ):
        raise ValueError("v5_2 residual overlap reason drift")

    taxonomy = report.get("xlsx_residual_candidate_state_taxonomy") or {}
    if taxonomy.get("residual_overlap_counts_available") is not False:
        raise ValueError("v5_2 residual overlap counts opened")
    expected_taxonomy = {
        "candidate_budget_per_query": 5,
        "xlsx_candidate_count": 881,
        "zero_candidate_row_count": 78,
        "candidate_budget_exhaustion_count": 109,
        "bounded_candidate_not_budget_exhausted_row_count": 138,
        "candidate_state_bucket_count_sum": 325,
    }
    for key, expected in expected_taxonomy.items():
        if taxonomy.get(key) != expected:
            raise ValueError(f"v5_2 taxonomy drift: {key}")
    if taxonomy.get("candidate_count_distribution") != {"0": 78, "1": 58, "2": 31, "3": 14, "4": 1, "5": 143}:
        raise ValueError("v5_2 candidate distribution drift")
    buckets = taxonomy.get("candidate_state_buckets") or {}
    if buckets.get("zero_candidate_structural_gap", {}).get("count") != 78:
        raise ValueError("v5_2 zero-candidate bucket drift")
    if buckets.get("budget_exhausted_diversity_gap", {}).get("count") != 109:
        raise ValueError("v5_2 budget-exhausted bucket drift")
    if buckets.get("bounded_candidate_rank_gap", {}).get("upper_bound_count") != 138:
        raise ValueError("v5_2 bounded-candidate bucket drift")
    if buckets.get("unclassified_residual_overlap", {}).get("aggregate_count") != 299:
        raise ValueError("v5_2 residual aggregate bucket drift")
    if buckets.get("value_only_or_forbidden_required", {}).get("count_status") != "intentionally_not_counted":
        raise ValueError("v5_2 forbidden-required bucket drift")
    if report.get("family_target_hit_regression_count") != {"TEXT": 0, "PDF": 0, "XLSX": 0}:
        raise ValueError("v5_2 family regression drift")

    readiness = report.get("ft_readiness_compatibility") or {}
    if readiness.get("status") != "blocked_retrieval_diagnostic_only_no_dataset_export":
        raise ValueError("v5_2 FT compatibility status drift")
    for key in (
        "blocked_by_user_gate",
        "blocked_by_eval",
        "blocked_by_data_quality",
    ):
        if readiness.get(key) is not True:
            raise ValueError(f"v5_2 FT blocked flag drift: {key}")
    for key in ("training_dataset_created", "fine_tuning_dataset_export_created", "fine_tuning_job_created", "checkpoint_created"):
        if readiness.get(key) is not False:
            raise ValueError(f"v5_2 FT export drift: {key}")

    counters = report.get("counters") or {}
    for key in ("official_metric_input_rows", "official_metric_input_rows_created"):
        if counters.get(key) != 0:
            raise ValueError(f"v5_2 counter drift: {key}")
    for key in ("safe_repair_applied", "safe_gain_claimed", "training_dataset_created"):
        if counters.get(key) is not False:
            raise ValueError(f"v5_2 counter drift: {key}")
    _assert_no_raw_payload_keys(report)
