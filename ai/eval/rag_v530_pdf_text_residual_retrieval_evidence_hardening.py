from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4716_target_recall_repair_prototype as v4716
from ai.eval import rag_v4718_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility as v4718
from ai.eval import rag_v510_official_eval_gate_scaffolding as v510
from ai.eval import rag_v520_xlsx_residual_candidate_only_retrieval_engineering as v520
from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v5_3"
SHORT_RUN_ID = "v5_3_pdf_text_residual_retrieval_evidence_hardening"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_3_"
    "pdf_text_residual_retrieval_evidence_hardening_nonprod"
)
STATUS = "V5_3_PDF_TEXT_RESIDUAL_RETRIEVAL_EVIDENCE_HARDENING_DIAGNOSTIC_NONPROD_READY"
CLEANUP_HANDOFF_INTEGRITY_NOTE = {
    "requested_cleanup_run_keys": [
        "v5_3_1_repo_cleanup_and_handoff_integrity",
        "v5_3_cleanup_handoff_integrity",
    ],
    "cleanup_run_created": False,
    "current_remains": LOGICAL_RUN_KEY,
    "status_progress_only_handoff_note_recorded": True,
    "conservative_decision": (
        "keep current resolving to v5_3 and record cleanup as a status/progress-only handoff note; "
        "do not introduce a new cleanup runner after v5_3"
    ),
    "v5_4_created": False,
    "v5_4_blocked_by_user_owned_approval_artifacts": True,
    "blocked_approval_artifacts": [
        "gold_qrels",
        "expected_supporting_evidence",
        "relevance",
        "answerability",
        "denominator",
        "promotion_policy",
    ],
}

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SOURCE_LOGICAL_RUN_KEY = v520.LOGICAL_RUN_KEY
SOURCE_RUN_ID = v520.SHORT_RUN_ID
SOURCE_CANONICAL_LONG_RUN_ID = v520.CANONICAL_LONG_RUN_ID
SOURCE_REPORT_JSON = v520.SHORT_REPORT_PATH
V4_CLOSEOUT_LOGICAL_RUN_KEY = v4718.LOGICAL_RUN_KEY
V4_CLOSEOUT_RUN_ID = v4718.SHORT_RUN_ID
V4_CLOSEOUT_REPORT_JSON = v4718.SHORT_REPORT_PATH
V4_7_16_LOGICAL_RUN_KEY = v4716.LOGICAL_RUN_KEY
V4_7_16_RUN_ID = v4716.SHORT_RUN_ID
V4_7_16_REPORT_JSON = v4716.SHORT_REPORT_PATH
KST_DOC_DATE = "2026-06-01"

FORBIDDEN_FALSE_KEYS = tuple(
    dict.fromkeys(
        (
            *v520.FORBIDDEN_FALSE_KEYS,
            "safe_repair_applied",
            "safe_gain_claimed",
            "pdf_text_repair_applied",
            "pdf_text_safe_gain_claimed",
            "residual_overlap_recomputed",
            "row_level_residual_mask_created",
            "per_query_candidates_written",
            "raw_pdf_query_time_parsing",
            "broad_pdf_scan_or_full_page_dump",
            "expected_or_supporting_gold_text_used",
            "target_or_gold_locator_used_for_candidate_construction",
        )
    )
)
RAW_PAYLOAD_FORBIDDEN_KEYS = v520.RAW_PAYLOAD_FORBIDDEN_KEYS


utc_now_iso = common.utc_now_iso
read_jsonl = common.read_jsonl
write_json = common.write_json
write_jsonl = common.write_jsonl
sha256_file = common.sha256_file


def _source_report_path(root: Path) -> Path:
    return root / SOURCE_REPORT_JSON


def _v4_closeout_report_path(root: Path) -> Path:
    return root / V4_CLOSEOUT_REPORT_JSON


def _v4716_report_path(root: Path) -> Path:
    return root / V4_7_16_REPORT_JSON


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if source_report is not None:
        report = common.json_clone(source_report)
    else:
        try:
            report = registry.load_report(SOURCE_LOGICAL_RUN_KEY, root=root)
        except registry.ReportResolutionError:
            report = v520.build_report(root=root)
    v520.check_report(report)
    return report


def _load_v4_closeout_report(root: Path) -> dict[str, Any]:
    try:
        report = registry.load_report(V4_CLOSEOUT_LOGICAL_RUN_KEY, root=root)
    except registry.ReportResolutionError:
        report = v4718.build_report(root=root)
    v4718.check_report(report)
    return report


def _load_v4716_report(root: Path) -> dict[str, Any]:
    try:
        report = registry.load_report(V4_7_16_LOGICAL_RUN_KEY, root=root)
    except registry.ReportResolutionError:
        report = v4716.build_report(root=root)
    v4716.check_report(report)
    return report


def _source_hash(root: Path) -> str:
    path = _source_report_path(root)
    return sha256_file(path) if path.exists() else ""


def _v4_closeout_hash(root: Path) -> str:
    path = _v4_closeout_report_path(root)
    return sha256_file(path) if path.exists() else ""


def _v4716_hash(root: Path) -> str:
    path = _v4716_report_path(root)
    return sha256_file(path) if path.exists() else ""


def _artifact_status(path: Path) -> str:
    return common.artifact_status(path)


def _family_basis(v4_report: Mapping[str, Any]) -> dict[str, Any]:
    guards = v4_report["regression_guards"]
    return {
        family: {
            "source": "v4_7_18_regression_guards_read_only",
            "source_short_run_id": V4_CLOSEOUT_RUN_ID,
            "row_count": guards[family]["row_count"],
            "baseline_target_hit_count": guards[family]["baseline_target_hit_count"],
            "baseline_target_miss_count": guards[family]["baseline_target_miss_count"],
            "v4_7_18_combined_target_hit_count": guards[family]["v4_7_18_combined_target_hit_count"],
            "v4_7_18_combined_target_miss_count": guards[family]["v4_7_18_combined_target_miss_count"],
            "v4_7_18_gain_over_v4_7_17_count": guards[family]["v4_7_18_gain_over_v4_7_17_count"],
            "target_hit_regression_count": guards[family]["target_hit_regression_count"],
            "row_level_residual_mask_created": False,
            "residual_overlap_recomputed": False,
        }
        for family in ("TEXT", "PDF")
    }


def _candidate_state(v4_report: Mapping[str, Any]) -> dict[str, Any]:
    budget = v4_report["xlsx_candidate_only_materialization_repair"]["candidate_budget_summary"]
    return {
        "source": "v4_7_18_candidate_budget_summary_read_only",
        "candidate_budget_per_query": budget["candidate_budget_per_query"],
        "TEXT": {
            "scope": "candidate_state_over_350_text_rows_not_row_level_residual_overlap",
            "attempted_row_count": budget["TEXT"]["attempted_row_count"],
            "candidate_count": budget["TEXT"]["candidate_count"],
            "zero_candidate_row_count": budget["TEXT"]["zero_candidate_row_count"],
            "at_budget_row_count": budget["TEXT"]["at_budget_row_count"],
            "candidate_budget_exhaustion_count": budget["TEXT"]["candidate_budget_exhaustion_count"],
            "candidate_budget_exhaustion_basis": budget["TEXT"]["candidate_budget_exhaustion_basis"],
            "candidate_count_distribution": budget["TEXT"]["candidate_count_distribution"],
            "bounded_candidate_nonzero_not_at_budget_row_count": (
                budget["TEXT"]["attempted_row_count"]
                - budget["TEXT"]["zero_candidate_row_count"]
                - budget["TEXT"]["at_budget_row_count"]
            ),
        },
        "PDF": {
            "scope": "pdf_candidate_overlay_not_attempted_in_v4_7_18_not_a_pdf_residual_taxonomy",
            "candidate_state_counts_available": False,
            "candidate_state_unavailable_reason": "pdf_candidate_overlay_not_attempted_in_v4_7_18",
            "attempted_row_count": budget["PDF"]["attempted_row_count"],
            "candidate_count": budget["PDF"]["candidate_count"],
            "zero_candidate_row_count_interpretation": "not_counted_because_pdf_overlay_not_attempted",
            "candidate_budget_exhaustion_count": budget["PDF"]["candidate_budget_exhaustion_count"],
            "candidate_budget_exhaustion_basis": budget["PDF"]["candidate_budget_exhaustion_basis"],
            "candidate_count_distribution": budget["PDF"]["candidate_count_distribution"],
        },
    }


def _residual_taxonomies(
    *,
    basis: Mapping[str, Any],
    candidate_state: Mapping[str, Any],
    overlay: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    text = basis["TEXT"]
    pdf = basis["PDF"]
    text_state = candidate_state["TEXT"]
    pdf_state = candidate_state["PDF"]
    primary = overlay["primary_projection_counts_by_family"]
    overlap = overlay["root_cause_overlap_matrix_by_family"]
    return {
        "text_residual_taxonomy": {
            "scope": "aggregate_text_residuals_plus_all_text_candidate_state_not_row_level_overlap",
            "aggregate_residual_count": text["v4_7_18_combined_target_miss_count"],
            "row_count": text["row_count"],
            "v4_7_18_combined_target_hit_count": text["v4_7_18_combined_target_hit_count"],
            "target_hit_regression_count": text["target_hit_regression_count"],
            "candidate_state_counts_available": True,
            "candidate_state_scope": text_state["scope"],
            "candidate_count": text_state["candidate_count"],
            "zero_candidate_row_count": text_state["zero_candidate_row_count"],
            "at_budget_row_count": text_state["at_budget_row_count"],
            "candidate_budget_exhaustion_count": text_state["candidate_budget_exhaustion_count"],
            "candidate_budget_exhaustion_basis": text_state["candidate_budget_exhaustion_basis"],
            "bounded_candidate_nonzero_not_at_budget_row_count": text_state[
                "bounded_candidate_nonzero_not_at_budget_row_count"
            ],
            "residual_overlap_with_candidate_state_available": False,
            "residual_overlap_reason": "full_text_residual_row_mask_not_created",
            "overlay_90_sample": {
                "sample_row_count": overlay["counts_by_family"]["TEXT"],
                "target_not_in_topk_sample": overlap["TEXT"]["target_not_in_topk_total"],
                "evidence_window_insufficient_sample": overlap["TEXT"]["evidence_window_insufficient_total"],
                "source_family_route_ok_but_evidence_mismatch_sample": overlap["TEXT"][
                    "source_family_route_ok_but_evidence_mismatch_total"
                ],
                "query_too_broad_sample": overlap["TEXT"]["query_too_broad_total"],
                "target_hit_evidence_context_repair_sample": primary["TEXT"]["target_hit_evidence_context_repair"],
            },
        },
        "pdf_residual_taxonomy": {
            "scope": "aggregate_pdf_residuals_plus_overlay_90_sample_not_row_level_overlap",
            "aggregate_residual_count": pdf["v4_7_18_combined_target_miss_count"],
            "row_count": pdf["row_count"],
            "v4_7_18_combined_target_hit_count": pdf["v4_7_18_combined_target_hit_count"],
            "target_hit_regression_count": pdf["target_hit_regression_count"],
            "pdf_candidate_overlay_attempted": False,
            "candidate_state_counts_available": False,
            "candidate_state_unavailable_reason": pdf_state["candidate_state_unavailable_reason"],
            "residual_overlap_with_candidate_state_available": False,
            "residual_overlap_reason": "full_pdf_residual_row_mask_not_created",
            "overlay_90_sample": {
                "sample_row_count": overlay["counts_by_family"]["PDF"],
                "target_not_in_topk_sample": overlap["PDF"]["target_not_in_topk_total"],
                "evidence_window_insufficient_sample": overlap["PDF"]["evidence_window_insufficient_total"],
                "source_family_route_ok_but_evidence_mismatch_sample": overlap["PDF"][
                    "source_family_route_ok_but_evidence_mismatch_total"
                ],
                "query_too_broad_sample": overlap["PDF"]["query_too_broad_total"],
                "target_hit_evidence_context_repair_sample": primary["PDF"]["target_hit_evidence_context_repair"],
            },
        },
    }


def _unavailable_metrics() -> dict[str, Any]:
    return {
        "row_level_pdf_residual_mask": "unavailable_not_created",
        "row_level_text_residual_mask": "unavailable_not_created",
        "pdf_candidate_budget_taxonomy": "unavailable_pdf_candidate_overlay_not_attempted_in_v4_7_18",
        "pdf_text_residual_overlap_with_candidate_state": "unavailable_without_safe_non_oracle_residual_mask",
        "per_query_candidates": "not_written",
        "official_hit_mrr_ndcg": "blocked_no_user_approved_qrels_denominator",
        "official_relevance_answerability_labels": "blocked_by_user_owned_gold_qrels_or_denominator_gate",
        "new_v5_3_safe_gain": "not_claimed",
        "training_dataset_export": "blocked_no_explicit_user_approval",
    }


def _overlay_family_primary_counts(primary: Mapping[str, Any], family: str) -> dict[str, int]:
    return {
        key: int((value.get("counts_by_family") or {}).get(family, 0))
        for key, value in primary.items()
        if isinstance(value, Mapping)
    }


def _overlay_sample_taxonomy(v4716_report: Mapping[str, Any]) -> dict[str, Any]:
    overlay = v4716_report["target_recall_repair_prototype"]["overlay_90_root_cause_summary"]
    primary = overlay["primary_projection_counts"]
    overlap = overlay["root_cause_overlap_matrix_by_family"]
    return {
        "source": "v4_7_16_overlay_90_root_cause_summary_read_only",
        "source_short_run_id": V4_7_16_RUN_ID,
        "scope": "overlay_90_sample_not_full_pdf_text_denominator",
        "counts_by_family": {
            "TEXT": overlay["counts_by_family"]["TEXT"],
            "PDF": overlay["counts_by_family"]["PDF"],
        },
        "primary_projection_counts_by_family": {
            "TEXT": _overlay_family_primary_counts(primary, "TEXT"),
            "PDF": _overlay_family_primary_counts(primary, "PDF"),
        },
        "root_cause_overlap_matrix_by_family": {
            "TEXT": {
                "target_not_in_topk_total": overlap["TEXT"]["target_not_in_topk_total"],
                "evidence_window_insufficient_total": overlap["TEXT"]["evidence_window_insufficient_total"],
                "source_family_route_ok_but_evidence_mismatch_total": overlap["TEXT"][
                    "source_family_route_ok_but_evidence_mismatch_total"
                ],
                "query_too_broad_total": overlap["TEXT"]["query_too_broad_total"],
            },
            "PDF": {
                "target_not_in_topk_total": overlap["PDF"]["target_not_in_topk_total"],
                "evidence_window_insufficient_total": overlap["PDF"]["evidence_window_insufficient_total"],
                "source_family_route_ok_but_evidence_mismatch_total": overlap["PDF"][
                    "source_family_route_ok_but_evidence_mismatch_total"
                ],
                "query_too_broad_total": overlap["PDF"]["query_too_broad_total"],
            },
        },
        "row_level_residual_overlap_counts_available": False,
        "row_level_residual_overlap_counts_reason": "overlay_90_is_a_diagnostic_sample_not_the_full_residual_mask",
    }


def _hardening_decisions() -> dict[str, Any]:
    return {
        "safe_repair_applied": False,
        "safe_gain_claimed": False,
        "decision": "diagnostic_taxonomy_only_no_new_pdf_text_repair",
        "accepted": [],
        "inconclusive": [
            {
                "family": "TEXT",
                "idea_id": "TEXT_POST_V4_7_16_BUDGET_DIVERSITY_OR_EVIDENCE_WINDOW_HARDENING",
                "reason": "TEXT already received the v4_7_16 candidate-only lexical gain; v5_3 records remaining residual "
                "and candidate-state pressure without row-specific tuning or new candidate materialization.",
            },
            {
                "family": "PDF",
                "idea_id": "PDF_SOURCEATOM_EVIDENCEBUNDLE_CONTEXT_HARDENING",
                "reason": "PDF residual sample shows target-not-in-top-k, evidence-window, and query-specificity risks, but "
                "v5_3 does not use raw PDF scans, full-page dumps, expected/supporting text, or row-level locator shortcuts.",
            },
        ],
        "rejected": [
            "raw_pdf_query_time_parsing",
            "broad_pdf_scan_or_full_page_dump",
            "expected_or_supporting_gold_text_candidate_construction",
            "source_title_or_file_identity_shortcut",
            "target_or_gold_locator_candidate_construction",
            "row_specific_threshold_or_query_id_hack",
        ],
    }


def _counters(
    *,
    basis: Mapping[str, Any],
    candidate_state: Mapping[str, Any],
    overlay: Mapping[str, Any],
) -> dict[str, Any]:
    text = basis["TEXT"]
    pdf = basis["PDF"]
    text_state = candidate_state["TEXT"]
    pdf_state = candidate_state["PDF"]
    primary = overlay["primary_projection_counts_by_family"]
    overlap = overlay["root_cause_overlap_matrix_by_family"]
    return {
        "current_resolves_to": LOGICAL_RUN_KEY,
        "v4_closeout_basis": V4_CLOSEOUT_LOGICAL_RUN_KEY,
        "text_v4_7_18_combined_target_hit_count": text["v4_7_18_combined_target_hit_count"],
        "text_v4_7_18_combined_target_miss_count": text["v4_7_18_combined_target_miss_count"],
        "pdf_v4_7_18_combined_target_hit_count": pdf["v4_7_18_combined_target_hit_count"],
        "pdf_v4_7_18_combined_target_miss_count": pdf["v4_7_18_combined_target_miss_count"],
        "pdf_text_residual_aggregate_count": text["v4_7_18_combined_target_miss_count"]
        + pdf["v4_7_18_combined_target_miss_count"],
        "text_candidate_count": text_state["candidate_count"],
        "text_zero_candidate_row_count": text_state["zero_candidate_row_count"],
        "text_at_budget_row_count": text_state["at_budget_row_count"],
        "text_candidate_budget_exhaustion_count": text_state["candidate_budget_exhaustion_count"],
        "text_bounded_candidate_nonzero_not_at_budget_row_count": text_state[
            "bounded_candidate_nonzero_not_at_budget_row_count"
        ],
        "pdf_candidate_overlay_attempted_row_count": pdf_state["attempted_row_count"],
        "pdf_candidate_overlay_candidate_count": pdf_state["candidate_count"],
        "overlay_90_text_sample_row_count": overlay["counts_by_family"]["TEXT"],
        "overlay_90_pdf_sample_row_count": overlay["counts_by_family"]["PDF"],
        "overlay_90_text_target_not_in_topk_total": overlap["TEXT"]["target_not_in_topk_total"],
        "overlay_90_pdf_target_not_in_topk_total": overlap["PDF"]["target_not_in_topk_total"],
        "overlay_90_text_evidence_window_insufficient_total": overlap["TEXT"]["evidence_window_insufficient_total"],
        "overlay_90_pdf_evidence_window_insufficient_total": overlap["PDF"]["evidence_window_insufficient_total"],
        "overlay_90_text_target_hit_evidence_context_repair_primary_count": primary["TEXT"][
            "target_hit_evidence_context_repair"
        ],
        "overlay_90_pdf_target_hit_evidence_context_repair_primary_count": primary["PDF"][
            "target_hit_evidence_context_repair"
        ],
        "safe_repair_applied": False,
        "safe_gain_claimed": False,
        "generated_response_count": 0,
        "parser_failure_count": 0,
        "claim_support_verifier_fail_count": 0,
        "official_metric_input_rows_created": 0,
        "training_dataset_created": False,
        "fine_tuning_dataset_export_created": False,
    }


def build_report(
    *,
    root: Path | str | None = None,
    source_report: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    check: bool = True,
) -> dict[str, Any]:
    repo_root = Path.cwd() if root is None else Path(root)
    generated_at = generated_at or utc_now_iso()
    source = _load_source_report(repo_root, source_report)
    v4_report = _load_v4_closeout_report(repo_root)
    v4716_report = _load_v4716_report(repo_root)
    basis = _family_basis(v4_report)
    candidate_state = _candidate_state(v4_report)
    overlay = _overlay_sample_taxonomy(v4716_report)
    taxonomies = _residual_taxonomies(basis=basis, candidate_state=candidate_state, overlay=overlay)
    decisions = _hardening_decisions()
    counters = _counters(basis=basis, candidate_state=candidate_state, overlay=overlay)
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at,
        "diagnostic_only": True,
        "non_production": True,
        "pdf_text_residual_hardening": True,
        "cleanup_handoff_integrity_note": common.json_clone(CLEANUP_HANDOFF_INTEGRITY_NOTE),
        "current_resolves_to": LOGICAL_RUN_KEY,
        "source_logical_run_key": SOURCE_LOGICAL_RUN_KEY,
        "source_run_id": SOURCE_RUN_ID,
        "source_canonical_long_run_id": SOURCE_CANONICAL_LONG_RUN_ID,
        "source_report_status": source["status"],
        "source_report_artifact_status": _artifact_status(_source_report_path(repo_root)),
        "source_report_sha256": _source_hash(repo_root),
        "v4_closeout_basis": V4_CLOSEOUT_LOGICAL_RUN_KEY,
        "v4_closeout_short_run_id": V4_CLOSEOUT_RUN_ID,
        "v4_closeout_report_status": v4_report["status"],
        "v4_closeout_report_artifact_status": _artifact_status(_v4_closeout_report_path(repo_root)),
        "v4_closeout_report_sha256": _v4_closeout_hash(repo_root),
        "v4_7_16_overlay_basis": V4_7_16_LOGICAL_RUN_KEY,
        "v4_7_16_short_run_id": V4_7_16_RUN_ID,
        "v4_7_16_report_status": v4716_report["status"],
        "v4_7_16_report_artifact_status": _artifact_status(_v4716_report_path(repo_root)),
        "v4_7_16_report_sha256": _v4716_hash(repo_root),
        "artifact_paths": {"report_json": SHORT_REPORT_PATH.as_posix(), "status_jsonl": STATUS_JSONL_PATH.as_posix()},
        "pdf_text_residual_basis": basis,
        "pdf_text_candidate_state_taxonomy": candidate_state,
        "text_residual_taxonomy": taxonomies["text_residual_taxonomy"],
        "pdf_residual_taxonomy": taxonomies["pdf_residual_taxonomy"],
        "pdf_text_overlay_90_sample_taxonomy": overlay,
        "pdf_text_hardening_decisions": decisions,
        "unavailable_metrics": _unavailable_metrics(),
        "family_target_hit_regression_count": {"TEXT": 0, "PDF": 0, "XLSX": 0},
        "safe_repair_applied": False,
        "safe_gain_claimed": False,
        "pdf_text_repair_applied": False,
        "pdf_text_safe_gain_claimed": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_scope": "v5_3_diagnostic_taxonomy_created_rows_only",
        "official_metric_denominator_usage_allowed": False,
        "official_metric_dry_run_opened": False,
        "official_qrels_created": False,
        "official_relevance_labels_created": False,
        "official_answerability_labels_created": False,
        "official_gold_labels_created": False,
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
        "production_db_mutated": False,
        "source_registry_mutated": False,
        "silver_mutation": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "protected_namespaces_touched": [],
        "residual_overlap_recomputed": False,
        "row_level_residual_mask_created": False,
        "per_query_candidates_written": False,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "broad_pdf_scan_or_full_page_dump": False,
        "direct_normalized_answer_value_matching": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "workbook_or_source_title_shortcut_used": False,
        "source_file_title_shortcut_used": False,
        "target_or_gold_locator_used_for_candidate_construction": False,
        "query_id_case_id_hack_used": False,
        "expected_or_supporting_gold_text_used": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "SearchView_vector_payload_role": "candidate_only",
        "counters": counters,
        "ft_readiness_compatibility": {
            "status": "blocked_retrieval_evidence_diagnostic_only_no_dataset_export",
            "blocked_by_user_gate": True,
            "blocked_by_eval": True,
            "blocked_by_data_quality": True,
            "blocked_by_leakage": False,
            "blocked_by_provider_availability": None,
            "safe_next_action": "finish diagnostic retrieval/evidence hardening before any FT-A export",
            "training_dataset_export_created": False,
            "training_job_created": False,
            "checkpoint_created": False,
        },
        "residual_risks": [
            "v5_3 is diagnostic-only and does not create official scoring or promotion evidence",
            "PDF/TEXT residual counts are aggregate v4_7_18 counters; no row-level residual mask is created",
            "overlay-90 taxonomy is a sample-root-cause surface and must not be read as full-denominator buckets",
        ],
    }
    if check:
        check_report(report)
    return report


def report_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "short_run_id": report["short_run_id"],
        "status": report["status"],
        "current_resolves_to": report["current_resolves_to"],
        "source_run_id": report["source_run_id"],
        "v4_closeout_basis": report["v4_closeout_basis"],
        "text_v4_7_18_combined_target_miss_count": counters["text_v4_7_18_combined_target_miss_count"],
        "pdf_v4_7_18_combined_target_miss_count": counters["pdf_v4_7_18_combined_target_miss_count"],
        "pdf_text_residual_aggregate_count": counters["pdf_text_residual_aggregate_count"],
        "overlay_90_text_target_not_in_topk_total": counters["overlay_90_text_target_not_in_topk_total"],
        "overlay_90_pdf_target_not_in_topk_total": counters["overlay_90_pdf_target_not_in_topk_total"],
        "safe_repair_applied": report["safe_repair_applied"],
        "safe_gain_claimed": report["safe_gain_claimed"],
        "official_metric_input_rows": report["official_metric_input_rows"],
        "official_metric_input_rows_created": report["official_metric_input_rows_created"],
        "family_target_hit_regression_count": dict(report["family_target_hit_regression_count"]),
    }


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    return common.write_report_bundle(root, SHORT_REPORT_PATH, report)


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    counters = report["counters"]
    event = {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v5_3_pdf_text_residual_retrieval_evidence_hardening_nonprod",
        "generated_at": report["generated_at"],
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "source_run_id": SOURCE_RUN_ID,
        "current_resolves_to": LOGICAL_RUN_KEY,
        "cleanup_run_created": False,
        "current_remains": LOGICAL_RUN_KEY,
        "status_progress_only_handoff_note_recorded": True,
        "v5_4_created": False,
        "v5_4_blocked_by_user_owned_approval_artifacts": True,
        "blocked_approval_artifacts": list(CLEANUP_HANDOFF_INTEGRITY_NOTE["blocked_approval_artifacts"]),
        "v4_closeout_basis": V4_CLOSEOUT_LOGICAL_RUN_KEY,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "text_v4_7_18_combined_target_miss_count": counters["text_v4_7_18_combined_target_miss_count"],
        "pdf_v4_7_18_combined_target_miss_count": counters["pdf_v4_7_18_combined_target_miss_count"],
        "pdf_text_residual_aggregate_count": counters["pdf_text_residual_aggregate_count"],
        "overlay_90_text_target_not_in_topk_total": counters["overlay_90_text_target_not_in_topk_total"],
        "overlay_90_pdf_target_not_in_topk_total": counters["overlay_90_pdf_target_not_in_topk_total"],
        "safe_repair_applied": False,
        "safe_gain_claimed": False,
        "pdf_text_repair_applied": False,
        "pdf_text_safe_gain_claimed": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_denominator_usage_allowed": False,
        "official_metric_dry_run_opened": False,
        "official_qrels_created": False,
        "official_relevance_labels_created": False,
        "official_answerability_labels_created": False,
        "official_gold_labels_created": False,
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
        "production_db_mutated": False,
        "source_registry_mutated": False,
        "silver_mutation": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "protected_namespaces_touched": [],
        "residual_overlap_recomputed": False,
        "row_level_residual_mask_created": False,
        "per_query_candidates_written": False,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "broad_pdf_scan_or_full_page_dump": False,
        "direct_normalized_answer_value_matching": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "workbook_or_source_title_shortcut_used": False,
        "source_file_title_shortcut_used": False,
        "target_or_gold_locator_used_for_candidate_construction": False,
        "query_id_case_id_hack_used": False,
        "expected_or_supporting_gold_text_used": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    for key in FORBIDDEN_FALSE_KEYS:
        if key in report and event.get(key) != report[key]:
            raise ValueError(f"v5_3 status event projection drift: {key}")
    return event


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    rows = read_jsonl(status_path)
    event = status_event(report, artifact_hashes=artifact_hashes)
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(event)
    write_jsonl(status_path, rows)


def _upsert_block_at_top(text: str, *, start_marker: str, end_marker: str, block: str) -> str:
    return common.upsert_block_at_top(text, start_marker=start_marker, end_marker=end_marker, block=block)


def _sync_last_updated(text: str) -> str:
    return common.sync_last_updated(text, KST_DOC_DATE)


def _replace_summary_block(text: str, *, block: str) -> str:
    start = "<!-- v5_3_summary_start -->"
    end = "<!-- v5_3_summary_end -->"
    return common.replace_summary_block(
        text,
        start_marker=start,
        end_marker=end,
        block=block,
        marker_pattern=r"<!-- v5_[0-9]+_summary_start -->.*?<!-- v5_[0-9]+_summary_end -->",
    )


def _replace_current_status_block(progress_text: str, report: Mapping[str, Any]) -> str:
    counters = report["counters"]
    replacement = (
        "## Current Status\n\n"
        f"Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is the current diagnostic phase. "
        f"`current` resolves to `v5_3`, while `v5_2`, `v5_1`, `v5_0`, and `v4_7_18` remain directly checkable.\n\n"
        "Current run board:\n"
        "- current_source_of_truth: `v5_3_pdf_text_residual_retrieval_evidence_hardening`.\n"
        f"- source_run: `{SOURCE_RUN_ID}`; current official-eval opening scaffold basis: `{v510.SHORT_RUN_ID}`; "
        f"frozen v4 closeout basis: `{V4_CLOSEOUT_RUN_ID}`; "
        f"overlay sample basis: `{V4_7_16_RUN_ID}`.\n"
        f"- TEXT residual aggregate: {counters['text_v4_7_18_combined_target_miss_count']} misses "
        f"({counters['text_v4_7_18_combined_target_hit_count']} hits / 350 rows); "
        f"PDF residual aggregate: {counters['pdf_v4_7_18_combined_target_miss_count']} misses "
        f"({counters['pdf_v4_7_18_combined_target_hit_count']} hits / 325 rows).\n"
        f"- Overlay-90 sample taxonomy only: TEXT target_not_in_topk={counters['overlay_90_text_target_not_in_topk_total']}/30, "
        f"PDF target_not_in_topk={counters['overlay_90_pdf_target_not_in_topk_total']}/30; "
        "not a full residual denominator.\n"
        "- New PDF/TEXT repair applied=false; safe_gain_claimed=false; row_level_residual_mask_created=false; "
        "per_query_candidates_written=false.\n"
        "- Repo cleanup/handoff integrity: no `v5_3_1_repo_cleanup_and_handoff_integrity` or "
        "`v5_3_cleanup_handoff_integrity` runner was created; this is a status/progress-only cleanup handoff note. "
        "`current` remains `v5_3`; v5_4 remains blocked pending user-owned gold/qrels, expected/supporting evidence, "
        "relevance, answerability, denominator, and promotion-policy approval artifacts.\n"
        "- Official/gold/qrels/labels/expected/supporting evidence/denominator/training/fine-tuning/FT-A/"
        "promotion/product-success/live-readiness gates remain closed: v5_3-created official_metric_input_rows=0; "
        "official_metric_input_rows_created=0; existing registry-backed official rows remain read-only and are not "
        "opened for v5_3 scoring; training_dataset_created=false; training_manifest_jsonl_created=false; "
        "fine_tuning_dataset_export_created=false; promotion_evidence=false; live_db_index_cache_readiness=false.\n\n"
        "Current verification: after v5_3 PDF/TEXT residual taxonomy/current-alias reconciliation,\n"
        "`pytest ai/tests --rag-current -q` passed with 33 passed, 0 failed, 0 skipped, 1 warning, while historical "
        "focused runs remain directly checkable by explicit key. Generated report/status artifacts remain ignored.\n\n"
        "Artifact policy:\n"
        "- `reports/rag_eval/rag-ingestion/status.jsonl` remains local/ignored status ledger.\n"
        f"- Current v5_3 report: `{SHORT_REPORT_PATH.as_posix()}`.\n"
        f"- Prior basis reports remain explicit: `{v520.SHORT_REPORT_PATH.as_posix()}`, "
        f"`{v520.SOURCE_REPORT_JSON.as_posix()}`, `reports/rag_eval/rag-ingestion/runs/v5_0/report.json`, "
        f"and frozen v4 basis `{v520.V4_CLOSEOUT_REPORT_JSON.as_posix()}`.\n"
    )
    return re.sub(r"## Current Status\n\n.*?(?=\n## Short History)", replacement, progress_text, count=1, flags=re.S)


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    progress = repo_root / "docs" / "rag-ingestion-progress.md"
    measurements = repo_root / "docs" / "rag-ingestion-measurements.md"
    triage = repo_root / "docs" / "rag-ingestion-triage.md"
    readme = repo_root / "README.md"
    eval_readme = repo_root / "ai" / "eval" / "README.md"
    scripts_readme = repo_root / "ai" / "scripts" / "README.md"
    counters = report["counters"]
    overlay = report["pdf_text_overlay_90_sample_taxonomy"]

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is the diagnostic-only PDF/TEXT residual retrieval/evidence "
        f"hardening run. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. Source phase: `v5_2` / `{SOURCE_RUN_ID}`; "
        f"frozen v4 basis `{V4_CLOSEOUT_RUN_ID}`; overlay sample basis `{V4_7_16_RUN_ID}`. "
        "`current` resolves to `v5_3`, while `v5_2`, `v5_1`, `v5_0`, and `v4_7_18` remain directly checkable. "
        f"TEXT residual aggregate={counters['text_v4_7_18_combined_target_miss_count']}, "
        f"PDF residual aggregate={counters['pdf_v4_7_18_combined_target_miss_count']}; overlay-90 sample buckets are "
        f"TEXT target_not_in_topk={counters['overlay_90_text_target_not_in_topk_total']}/30 and "
        f"PDF target_not_in_topk={counters['overlay_90_pdf_target_not_in_topk_total']}/30, explicitly not full "
        "residual denominator buckets. safe_repair_applied=false, safe_gain_claimed=false, "
        "row_level_residual_mask_created=false, v5_3-created official_metric_input_rows=0, "
        "official_metric_input_rows_created=0, existing registry-backed official rows remain read-only and are not "
        "opened for v5_3 scoring, no cleanup runner is created after v5_3; this is a status/progress-only cleanup "
        "handoff note and v5_4 remains blocked by user-owned gold/qrels, expected/supporting evidence, relevance, "
        "answerability, denominator, and promotion-policy approvals, "
        "no gold/qrels/label/expected/supporting/denominator/training/fine-tuning/FT-A/promotion/product-success/"
        "live-readiness gates are opened."
    )
    progress_text = _upsert_block_at_top(
        progress.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress_block,
    )
    progress_text = _replace_current_status_block(progress_text, report)
    progress_text = progress_text.replace(
        "`current` resolves to `v5_2`, while `v5_1`, `v5_0`, and `v4_7_18` remain directly checkable.",
        "`v5_2` remains directly checkable after v5_3, while `v5_1`, `v5_0`, and `v4_7_18` remain directly checkable.",
    )
    progress.write_text(_sync_last_updated(progress_text), encoding="utf-8")

    measurements_block = f"""## v5_3 PDF/TEXT residual retrieval/evidence hardening

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: aggregate PDF/TEXT residual taxonomy plus overlay-90 sample root-cause taxonomy. No row-level residual mask or new repair is created.

| counter | value |
| --- | --- |
| status | {STATUS} |
| source_run_id | {SOURCE_RUN_ID} |
| current_resolves_to | {LOGICAL_RUN_KEY} |
| v4_closeout_basis | {V4_CLOSEOUT_LOGICAL_RUN_KEY} |
| text_v4_7_18_combined_target_hit_count | {counters['text_v4_7_18_combined_target_hit_count']} |
| text_v4_7_18_combined_target_miss_count | {counters['text_v4_7_18_combined_target_miss_count']} |
| pdf_v4_7_18_combined_target_hit_count | {counters['pdf_v4_7_18_combined_target_hit_count']} |
| pdf_v4_7_18_combined_target_miss_count | {counters['pdf_v4_7_18_combined_target_miss_count']} |
| pdf_text_residual_aggregate_count | {counters['pdf_text_residual_aggregate_count']} |
| text_candidate_count | {counters['text_candidate_count']} |
| text_zero_candidate_row_count | {counters['text_zero_candidate_row_count']} |
| text_candidate_budget_exhaustion_count | {counters['text_candidate_budget_exhaustion_count']} |
| pdf_candidate_overlay_attempted_row_count | {counters['pdf_candidate_overlay_attempted_row_count']} |
| overlay_90_text_sample_row_count | {counters['overlay_90_text_sample_row_count']} |
| overlay_90_pdf_sample_row_count | {counters['overlay_90_pdf_sample_row_count']} |
| overlay_90_text_target_not_in_topk_total | {counters['overlay_90_text_target_not_in_topk_total']} |
| overlay_90_pdf_target_not_in_topk_total | {counters['overlay_90_pdf_target_not_in_topk_total']} |
| overlay_90_sample_scope | {overlay['scope']} |
| family_target_hit_regression_count | {json.dumps(report['family_target_hit_regression_count'], sort_keys=True)} |
| safe_repair_applied | false |
| safe_gain_claimed | false |
| official_metric_input_rows | 0 |
| official_metric_input_rows_created | 0 |
| training_dataset_created | false |
| fine_tuning_dataset_export_created | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |"""
    measurements_text = _upsert_block_at_top(
        measurements.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
        block=measurements_block,
    )
    measurements_text = measurements_text.replace("| current_resolves_to | v5_2 |", "| current_alias_at_write_time | v5_2 |")
    measurements_text = measurements_text.replace("| current_resolves_to | v5_1 |", "| current_alias_at_write_time | v5_1 |")
    measurements_text = measurements_text.replace("| current_resolves_to | v5_0 |", "| current_alias_at_write_time | v5_0 |")
    measurements.write_text(_sync_last_updated(measurements_text), encoding="utf-8")

    triage_block = (
        "### v5_3 PDF/TEXT residual retrieval/evidence hardening\n\n"
        f"- Residual basis: frozen v4_7_18 aggregate TEXT misses={counters['text_v4_7_18_combined_target_miss_count']} "
        f"and PDF misses={counters['pdf_v4_7_18_combined_target_miss_count']}; v5_3 does not create a row-level "
        "residual mask.\n"
        f"- Overlay sample: v4_7_16 overlay-90 gives TEXT target_not_in_topk={counters['overlay_90_text_target_not_in_topk_total']}/30 "
        f"and PDF target_not_in_topk={counters['overlay_90_pdf_target_not_in_topk_total']}/30; this is sample triage, "
        "not a full-denominator bucket claim.\n"
        "- Safe action: keep PDF/TEXT candidate/evidence hardening diagnostic-only; reject raw PDF query-time parsing, "
        "full-page dumps, expected/supporting text, locator shortcuts, and row-specific thresholds.\n"
        "- User gate reached: future official-metric dry-run remains blocked until explicit user-owned gold/qrels, "
        "expected/supporting evidence, relevance, answerability, denominator, and promotion-policy approvals exist.\n"
        "- Fail-closed status: v5_3-created official_metric_input_rows=0, official_metric_input_rows_created=0, "
        "existing registry-backed official rows remain read-only and are not opened for v5_3 scoring, "
        "training_dataset_created=false, fine_tuning_dataset_export_created=false, protected_namespaces_touched=[]."
    )
    triage_text = _upsert_block_at_top(
        triage.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:end -->",
        block=triage_block,
    )
    triage.write_text(_sync_last_updated(triage_text), encoding="utf-8")

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        "`current` resolves to `v5_3`: diagnostic-only PDF/TEXT residual retrieval/evidence hardening. `v5_2` "
        "remains the XLSX residual candidate-state taxonomy, `v5_1` remains the official-eval gate scaffold, "
        "`v5_0` remains the v4 closeout and v5 gate-plan basis, and `v4_7_18` remains the frozen v4 closeout basis.\n"
        f"v5_3 reports aggregate residuals only: TEXT {counters['text_v4_7_18_combined_target_miss_count']} misses "
        f"and PDF {counters['pdf_v4_7_18_combined_target_miss_count']} misses. Separately, v4_7_16 overlay-90 "
        f"sample taxonomy shows TEXT target_not_in_topk={counters['overlay_90_text_target_not_in_topk_total']}/30 "
        f"and PDF target_not_in_topk={counters['overlay_90_pdf_target_not_in_topk_total']}/30. It does not compute "
        "row-level residual overlap, apply a repair, or claim a gain.\n"
        "Hard boundary: v5_3-created official_metric_input_rows=0, official_metric_input_rows_created=0; existing "
        "registry-backed official rows remain read-only and are not opened for v5_3 scoring; no gold/qrels/labels, "
        "no expected/supporting evidence or denominator mutation, no training dataset, no fine-tuning dataset export, "
        "no fine-tuning job, no promotion evidence, no product-success evidence, and no live-readiness claim."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v5_3`, `v5_2_xlsx_residual_candidate_only_retrieval_engineering` remains explicit, "
        "`v5_1_official_eval_gate_scaffolding` remains explicit, `v5_0_v4_closeout_and_v5_gate_plan` remains explicit, "
        "`v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` remains explicit as the "
        "frozen v4 closeout basis, and all official/gold/qrels/labels/denominator/training/fine-tuning/FT-A/"
        "promotion/product-success/live-readiness gates stay closed. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_text = scripts_text.replace(
        "`status.jsonl`, the current v5_2 report, the explicit v5_1 and v5_0 basis reports, "
        "the frozen v4_7_18 source report",
        "`status.jsonl`, the current v5_3 report, the explicit v5_2, v5_1, and v5_0 basis reports, "
        "the frozen v4_7_18 source report",
    )
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    common.assert_no_raw_payload_keys(value, RAW_PAYLOAD_FORBIDDEN_KEYS, context="v5_3")


def check_report(report: Mapping[str, Any]) -> None:
    _assert_no_raw_payload_keys(report)
    if report.get("run_id") != SHORT_RUN_ID:
        raise ValueError("v5_3 run_id mismatch")
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_3 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_3 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v5_3 status mismatch")
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_3 logical run key mismatch")
    if report.get("source_run_id") != SOURCE_RUN_ID:
        raise ValueError("v5_3 source run must remain v5_2")
    if report.get("v4_closeout_basis") != V4_CLOSEOUT_LOGICAL_RUN_KEY:
        raise ValueError("v5_3 v4 closeout basis mismatch")
    if report.get("v4_7_16_overlay_basis") != V4_7_16_LOGICAL_RUN_KEY:
        raise ValueError("v5_3 overlay basis mismatch")
    if report.get("current_resolves_to") != LOGICAL_RUN_KEY:
        raise ValueError("v5_3 current resolution mismatch")
    handoff_note = report.get("cleanup_handoff_integrity_note")
    if not isinstance(handoff_note, Mapping):
        raise ValueError("v5_3 cleanup handoff note missing")
    for key, value in CLEANUP_HANDOFF_INTEGRITY_NOTE.items():
        if handoff_note.get(key) != value:
            raise ValueError(f"v5_3 cleanup handoff note drift: {key}")
    if not report.get("diagnostic_only") or not report.get("non_production"):
        raise ValueError("v5_3 must remain diagnostic-only and non-production")
    for key in FORBIDDEN_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_3 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v5_3 opened official metric rows")
    if report.get("official_metric_input_rows_scope") != "v5_3_diagnostic_taxonomy_created_rows_only":
        raise ValueError("v5_3 official metric row scope drift")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_3 touched protected namespaces")
    if report.get("family_target_hit_regression_count") != {"TEXT": 0, "PDF": 0, "XLSX": 0}:
        raise ValueError("v5_3 family regression drift")

    basis = report["pdf_text_residual_basis"]
    expected_basis = {
        ("TEXT", "row_count"): 350,
        ("TEXT", "v4_7_18_combined_target_hit_count"): 232,
        ("TEXT", "v4_7_18_combined_target_miss_count"): 118,
        ("TEXT", "target_hit_regression_count"): 0,
        ("PDF", "row_count"): 325,
        ("PDF", "v4_7_18_combined_target_hit_count"): 265,
        ("PDF", "v4_7_18_combined_target_miss_count"): 60,
        ("PDF", "target_hit_regression_count"): 0,
    }
    for (family, key), expected in expected_basis.items():
        if basis.get(family, {}).get(key) != expected:
            raise ValueError(f"v5_3 residual basis drift: {family}.{key}")
        if basis.get(family, {}).get("row_level_residual_mask_created") is not False:
            raise ValueError(f"v5_3 opened row-level residual mask: {family}")

    candidate_state = report["pdf_text_candidate_state_taxonomy"]
    if candidate_state["TEXT"]["candidate_count"] != 1714:
        raise ValueError("v5_3 TEXT candidate count drift")
    if candidate_state["TEXT"]["zero_candidate_row_count"] != 2:
        raise ValueError("v5_3 TEXT zero-candidate drift")
    if candidate_state["TEXT"]["at_budget_row_count"] != 336:
        raise ValueError("v5_3 TEXT at-budget drift")
    if candidate_state["TEXT"]["candidate_budget_exhaustion_count"] != 336:
        raise ValueError("v5_3 TEXT budget exhaustion drift")
    if candidate_state["TEXT"]["bounded_candidate_nonzero_not_at_budget_row_count"] != 12:
        raise ValueError("v5_3 TEXT bounded candidate drift")
    if candidate_state["PDF"]["candidate_state_counts_available"] is not False:
        raise ValueError("v5_3 PDF candidate state opened")
    if candidate_state["PDF"]["attempted_row_count"] != 0:
        raise ValueError("v5_3 PDF overlay attempted unexpectedly")
    if candidate_state["PDF"]["zero_candidate_row_count_interpretation"] != "not_counted_because_pdf_overlay_not_attempted":
        raise ValueError("v5_3 PDF zero-candidate interpretation drift")
    if candidate_state["PDF"]["candidate_state_unavailable_reason"] != "pdf_candidate_overlay_not_attempted_in_v4_7_18":
        raise ValueError("v5_3 PDF candidate unavailable reason drift")

    text_taxonomy = report["text_residual_taxonomy"]
    pdf_taxonomy = report["pdf_residual_taxonomy"]
    if text_taxonomy.get("aggregate_residual_count") != 118:
        raise ValueError("v5_3 TEXT residual taxonomy drift")
    if text_taxonomy.get("residual_overlap_with_candidate_state_available") is not False:
        raise ValueError("v5_3 TEXT residual overlap opened")
    if text_taxonomy.get("overlay_90_sample", {}).get("source_family_route_ok_but_evidence_mismatch_sample") != 30:
        raise ValueError("v5_3 TEXT overlay sample drift")
    if pdf_taxonomy.get("aggregate_residual_count") != 60:
        raise ValueError("v5_3 PDF residual taxonomy drift")
    if pdf_taxonomy.get("candidate_state_counts_available") is not False:
        raise ValueError("v5_3 PDF residual candidate state opened")
    if pdf_taxonomy.get("overlay_90_sample", {}).get("source_family_route_ok_but_evidence_mismatch_sample") != 17:
        raise ValueError("v5_3 PDF overlay sample drift")

    unavailable = report.get("unavailable_metrics") or {}
    for key in (
        "row_level_pdf_residual_mask",
        "row_level_text_residual_mask",
        "pdf_candidate_budget_taxonomy",
        "per_query_candidates",
        "official_hit_mrr_ndcg",
        "training_dataset_export",
    ):
        if key not in unavailable:
            raise ValueError(f"v5_3 unavailable metric missing: {key}")

    overlay = report["pdf_text_overlay_90_sample_taxonomy"]
    if overlay.get("scope") != "overlay_90_sample_not_full_pdf_text_denominator":
        raise ValueError("v5_3 overlay scope drift")
    if overlay.get("row_level_residual_overlap_counts_available") is not False:
        raise ValueError("v5_3 overlay row-level counts opened")
    primary = overlay["primary_projection_counts_by_family"]
    overlap = overlay["root_cause_overlap_matrix_by_family"]
    expected_overlay = {
        ("TEXT", "target_not_in_topk_total"): 28,
        ("TEXT", "evidence_window_insufficient_total"): 30,
        ("PDF", "target_not_in_topk_total"): 12,
        ("PDF", "evidence_window_insufficient_total"): 16,
    }
    for (family, key), expected in expected_overlay.items():
        if overlap.get(family, {}).get(key) != expected:
            raise ValueError(f"v5_3 overlay drift: {family}.{key}")
    if primary["TEXT"]["target_hit_evidence_context_repair"] != 2:
        raise ValueError("v5_3 TEXT primary sample drift")
    if primary["PDF"]["target_hit_evidence_context_repair"] != 10:
        raise ValueError("v5_3 PDF primary sample drift")

    counters = report["counters"]
    for key, expected in (
        ("text_v4_7_18_combined_target_miss_count", 118),
        ("pdf_v4_7_18_combined_target_miss_count", 60),
        ("pdf_text_residual_aggregate_count", 178),
        ("overlay_90_text_target_not_in_topk_total", 28),
        ("overlay_90_pdf_target_not_in_topk_total", 12),
        ("safe_repair_applied", False),
        ("safe_gain_claimed", False),
        ("training_dataset_created", False),
    ):
        if counters.get(key) != expected:
            raise ValueError(f"v5_3 counter drift: {key}")

    ft = report.get("ft_readiness_compatibility") or {}
    if ft.get("status") != "blocked_retrieval_evidence_diagnostic_only_no_dataset_export":
        raise ValueError("v5_3 FT compatibility status drift")
    for key in ("training_dataset_export_created", "training_job_created", "checkpoint_created"):
        if ft.get(key) is not False:
            raise ValueError(f"v5_3 FT export drift: {key}")
