from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFTEST_PATH = ROOT / "ai" / "tests" / "conftest.py"


def load_conftest():
    spec = importlib.util.spec_from_file_location("rag_current_conftest_for_tests", CONFTEST_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_profile_includes_required_official_candidate_and_pdf_tests() -> None:
    rag_conftest = load_conftest()
    required_nodeids = {
        "ai/tests/test_rag_official_answer_citation_metric_first_run_v1.py::test_latest_first_run_artifacts_are_scored_baseline_not_backend_unavailable",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_source_of_truth_audit_reports_current_scored_baseline",
        "ai/tests/test_rag_xlsx_answer_citation_runtime_precision_candidate_v1.py::test_runtime_candidate_run_emits_report_only_artifacts_without_mutating_baseline",
        "ai/tests/test_rag_pdf_answer_citation_table_value_candidate_v1.py::test_pdf_candidate_run_carries_forward_xlsx_runtime_and_scores_three_pdf_rows",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_pdf_query_discards_off_track_xlsx_search_unit_from_scored_citations",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_result_row_separates_query_bound_from_same_track_context_citations",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_v2_2_noop_backend_cannot_be_real_llm_validation",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_v2_2_unavailable_backend_fail_closes_rows_without_promotion",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_v2_2_prompt_context_uses_same_track_source_bound_citations_only",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_v2_2_structured_adapter_output_is_retained_without_llm_overwrite",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_v3_run_id_is_separate_and_source_bound_defaults_are_locked",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_v3_requires_completed_v2_2_preflight_before_generation",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_v3_structured_rows_are_retained_and_text_rows_use_llm",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_v3_prompt_context_modes_exclude_off_track_and_gold_candidate_text",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_v3_text_namu_0017_diagnostic_fields_are_emitted",
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_text_query_discards_off_track_xlsx_search_unit_from_scored_citations",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v2_1_citation_contract_repair_artifacts_discard_off_track_citations",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v2_2_llm_backend_validation_artifact_is_diagnostic_only",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_comparable_live_measurement_artifacts_are_separate_and_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_all_track_foundation_measurement_artifacts_are_separate_and_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_3_remaining_queue_answer_span_renderer_triage_is_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_4_pdf_residual_answer_span_renderer_triage_is_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_5_gq_auto_010_source_bound_context_coverage_diagnostic_is_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_6_gq_auto_010_pdf_paragraph_window_expansion_is_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_7_post_residual_queue_closure_inventory_is_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_8_gold_policy_packet_preparation_is_compact_and_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_9_user_gold_policy_override_application_and_rescore_is_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_9_gold_csv_contains_only_the_user_approved_text_overrides",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_0_current_system_live_baseline_is_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_1_text_residual_triage_and_scorer_policy_are_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_2_post_fix_remeasurement_compares_only_intended_scorer_delta",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_3_queue_lane_actionability_reconciliation_is_compact_and_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_4_gq_auto_010_pdf_context_provenance_is_compact_no_behavior_and_source_bound",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_5_gq_auto_010_pdf_context_reconciliation_full_remeasurement_is_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_5_gq_auto_010_reconciliation_changes_only_target_lane_bc",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_5_pdf_context_reconciliation_overlay_is_target_scoped_and_locator_valid",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_6_text_prompt_span_rule_remeasurement_is_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_6_text_prompt_span_rule_changes_only_actionable_live_text_lanes",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_6_queue_uses_v3_2_5_queue_as_source_of_truth",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_7_post_fix_closure_status_event_is_guarded_and_compact",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_2_7_closure_uses_v3_2_6_queue_as_source_of_truth",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_3_0_post_closure_source_of_truth_audit_is_status_only_and_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_3_2_retrieval_label_design_packet_blocks_metrics_until_user_decisions",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_4_0_official_retrieval_metric_contract_blocks_metrics_until_qrels_are_approved",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_4_1_official_retrieval_qrels_candidate_packet_is_pending_human_review_only",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_is_policy_only",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_4_2_applies_user_exact_evidence_qrels_and_excludes_ambiguous_query",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_4_3_computes_lane_b_exact_evidence_retrieval_smoke_metrics_only",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_4_4_readme_metric_card_and_silver_readiness_artifacts_are_guarded",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_7_pdf_prompt_context_expansion_is_target_bound_and_query_bound",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_2_5_pdf_context_reconciliation_fix_without_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_2_6_text_prompt_span_rule_remeasurement_without_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_2_7_closure_without_promotion_or_next_phase",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_3_0_source_of_truth_audit_without_reopening_queue",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_docs_record_v3_3_2_retrieval_label_design_packet_without_metrics",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_docs_record_v3_4_0_official_retrieval_metric_contract_without_metrics",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_docs_record_v3_4_1_official_retrieval_qrels_candidate_packet_without_metrics",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_4_1a_human_minimal_review_packet_without_metrics",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_and_triage_docs_record_v3_4_2_exact_evidence_qrels_without_metrics",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_and_triage_docs_record_v3_4_3_exact_evidence_smoke_metrics",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_4_4_readme_artifacts_and_silver_boundary_without_triage_change",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_5_0_capacity_expansion_without_triage_change",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_5_1_to_v3_5_3_source_material_phases_without_triage_change",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_status_jsonl_records_compact_v3_5_1_to_v3_5_3_source_material_events",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_5_4_balanced_source_manifest_freeze_without_triage_change",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_status_jsonl_records_compact_v3_5_4_source_manifest_freeze_event",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_5_5_quality_audit",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_0_policy_application_without_generation",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_1_candidate_generation_without_official_labels",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_2_sanity_eval_without_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_3_manifest_freeze_without_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_measurements_and_triage_gate_record_v3_6_4_metric_without_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_5_without_metric_measurements_or_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_6_without_metric_measurements_or_promotion",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_2_5_pdf_context_reconciliation_does_not_mutate_gold_denominator_or_runtime_artifacts",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_2_6_text_prompt_span_rule_does_not_mutate_gold_denominator_or_runtime_artifacts",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_2_7_closure_does_not_mutate_gold_denominator_or_runtime_artifacts",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_3_0_source_of_truth_audit_does_not_mutate_gold_denominator_or_runtime_artifacts",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_4_4_readme_artifacts_do_not_mutate_protected_surfaces_or_silver_rows",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_5_0_capacity_expansion_does_not_mutate_protected_surfaces_or_silver_rows",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_5_1_to_v3_5_3_source_material_phases_do_not_mutate_protected_surfaces_or_silver_rows",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_5_4_balanced_freeze_does_not_mutate_protected_surfaces_or_silver_rows",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_5_5_quality_audit_does_not_mutate_v3_5_4_protected_surfaces_or_silver_rows",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_1_weak_noisy_candidate_generation_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_2_sanity_eval_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_3_manifest_freeze_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_4_metric_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_5_triage_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_6_sidecar_probe_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_residual_audit_does_not_mutate_protected_artifacts",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_0_capacity_summary_locks_schema_and_previous_strict_inventory",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_0_manifest_ready_candidates_are_source_bound_and_non_official",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_0_keeps_silver_rows_closed_and_official_ids_excluded",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_0_acquisition_plan_is_track_separated_and_non_generating",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_1_pilot_source_manifest_freeze_is_source_only_and_text_heavy",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_2_xlsx_repair_uses_actual_workbook_values_not_query_or_expected_answer",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_3_pdf_repair_records_page_bbox_text_hash_and_provenance",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_4_balanced_source_manifest_freeze_locks_counts_and_source_only_policy",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_4_balanced_manifest_rows_are_non_official_with_family_locator_hash_contracts",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_4_sample_packet_is_manifest_derived_source_only_and_balanced",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_5_quality_audit_summary_artifacts_and_v3_5_4_inputs_are_locked",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_5_duplicate_hash_audit_sample_packet_and_repair_queue_are_source_only",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_5_source_material_phases_create_no_silver_rows_or_label_payloads",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_0_low_touch_noisy_policy_application_records_user_decision_without_rows",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_1_weak_noisy_candidate_rows_are_source_bound_non_gold_and_mixed",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_1_policy_compliance_audit_locks_inputs_splits_and_canonical_silver",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_2_candidate_sanity_eval_artifacts_are_compact_guarded_and_feasible",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_6_2_sanity_hash_contract_is_registered_and_matches_artifacts",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_3_diagnostic_manifest_freeze_counts_policy_and_flags",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_6_3_manifest_freeze_artifacts_are_registered_and_hash_locked",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_4_diagnostic_metric_preserves_manifest_partitions_and_guardrails",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_4_diagnostic_metric_fails_closed_if_review_flags_enter_core",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_6_4_diagnostic_metric_artifacts_are_registered_and_hash_locked",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_5_rough_failure_bucket_triage_policy_and_surface_audits",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_6_5_runtime_audit_artifacts_are_registered_hash_locked_and_compact",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_6_reference_sidecar_runtime_and_retrieval_probe_are_diagnostic_only",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_6_source_policy_validation_fails_closed_on_inherited_llm_or_db_mutation_flags",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_6_6_sidecar_runtime_probe_artifacts_are_registered_hash_locked_and_compact",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_7_runtime_stability_probe_is_core_only_diagnostic_and_non_promoting",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_7_source_policy_validation_fails_closed_on_smoke_generation_input_leakage",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_6_7_runtime_stability_probe_artifacts_are_registered_hash_locked_and_compact",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_7_runtime_stability_probe_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_7_runtime_stability_probe_without_metric_measurements_or_promotion",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_8_nonprod_all_source_summary_locks_outcome_and_guardrails",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_8_source_inventory_and_index_files_preserve_scope_and_exclusions",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_8_search_unit_manifest_has_namespace_split_and_canonical_payloads",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_8_retrieval_smoke_exposes_compact_canonical_envelopes_only",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_8_no_llm_render_helper_and_retrieval_only_guardrail",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_8_rejects_v3_5_4_rows_with_forbidden_generation_or_label_fields",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_8_source_registry_audit_summary_locks_source_first_policy_and_exit",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_8_source_atom_no_vector_hydration_render_and_evidence_bundle_helpers",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_9_source_atom_search_view_contract_hydrates_evidence_without_vector_truth",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_9_retrieval_context_payload_exposes_search_view_and_source_atom_refs",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_6_9_searchunit_searchview_sourceatom_refactor_summary_locks_exit_and_guardrails",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_7_0_source_registry_materialization_artifacts_lock_source_first_contract",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_7_0_source_registry_no_vector_hydration_and_citation_smoke",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_7_1_all_source_citable_nonprod_index_is_source_atom_backed_without_vector_truth",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_7_2_source_registry_backed_retrieval_smoke_report_tracks_contract_survival_by_track",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_6_8_nonprod_index_and_payload_artifacts_are_registered_hash_locked_and_compact",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_6_8_source_registry_architecture_audit_artifacts_are_registered_hash_locked_and_compact",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_6_9_searchunit_searchview_sourceatom_refactor_artifacts_are_registered_hash_locked_and_compact",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_7_2_source_registry_backed_retrieval_smoke_artifacts_are_registered_hash_locked_and_compact",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_8_nonprod_materialization_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_8_source_registry_architecture_audit_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_6_9_searchunit_searchview_sourceatom_refactor_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_7_0_source_registry_materialization_does_not_mutate_protected_surfaces_or_promote_silver",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_7_1_all_source_citable_nonprod_index_does_not_mutate_source_registry_or_protected_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_7_2_source_registry_backed_retrieval_smoke_does_not_mutate_source_registry_or_protected_surfaces",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_8_nonprod_all_source_without_metric_measurements_or_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_8_source_registry_architecture_audit_without_metric_measurements_or_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_6_9_searchunit_searchview_sourceatom_refactor_without_metric_measurements_or_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_7_0_source_registry_materialization_without_metrics_or_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_7_1_all_source_citable_nonprod_index_without_metrics_or_promotion",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_7_2_source_registry_backed_retrieval_smoke_without_promotion",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_includes_required_official_candidate_and_pdf_tests",
    }

    for nodeid in required_nodeids:
        assert rag_conftest.is_rag_current_required_nodeid(nodeid), nodeid
        rel_file, test_name = nodeid.split("::", 1)
        assert f"def {test_name}(" in (ROOT / rel_file).read_text(encoding="utf-8"), nodeid


def test_current_profile_excludes_missing_artifact_noise_from_default_current_loop() -> None:
    rag_conftest = load_conftest()
    historical = (
        "ai/tests/test_rag_answer_recovery_bridge.py::test_diagnostic_harness_emits_reports_and_trace"
    )
    optional = "ai/tests/test_eval_harness.py::TestCommittedSampleDatasets::test_rag_sample_parses"

    assert not rag_conftest.is_rag_current_required_nodeid(historical)
    assert not rag_conftest.is_rag_current_required_nodeid(optional)
    assert "rag_current" in rag_conftest.MARKER_DESCRIPTIONS
    assert "rag_external_artifact" not in rag_conftest.MARKER_DESCRIPTIONS
    assert "rag_optional_dataset" not in rag_conftest.MARKER_DESCRIPTIONS


def test_ai_tests_directory_contains_only_current_profile_files() -> None:
    rag_conftest = load_conftest()
    existing_test_files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "ai" / "tests").glob("test_*.py")
    }
    forbidden_name_fragments = ("scratch", "tmp", "temp", "adhoc", "ad_hoc", "legacy", "unused")

    assert existing_test_files == rag_conftest.CURRENT_RAG_TEST_FILES
    assert not [
        rel_path
        for rel_path in existing_test_files
        if any(fragment in Path(rel_path).name.lower() for fragment in forbidden_name_fragments)
    ]
    for rel_path in sorted(rag_conftest.CURRENT_RAG_TEST_FILES):
        assert "def test_" in (ROOT / rel_path).read_text(encoding="utf-8"), rel_path
