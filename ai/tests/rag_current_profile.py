from __future__ import annotations


# Keep the current RAG test surface intentionally compact. Routine diagnostic
# phases should add exact nodeids here instead of pulling broad historical files
# into the default current loop.
CURRENT_RAG_TEST_NODEIDS = frozenset(
    {
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_data_lives_in_shared_support_module",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_includes_required_official_candidate_and_pdf_tests",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_excludes_missing_artifact_noise_from_default_current_loop",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_ai_tests_directory_classifies_current_and_historical_profile_files",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_rag_current_collect_only_matches_exact_nodeid_allowlist",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_accepts_collected_prefixes_and_windows_nodeids",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_marker_assignment_is_nodeid_scoped",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_route_is_default_disabled_and_production_disabled",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_election_query_stays_default_off_and_production_disabled",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_enabled_success_returns_frontend_safe_dto_without_gold_or_raw_leakage",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_election_result_query_uses_llm_adjudicator_for_xlsx_route",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_adjudicator_reason_is_redacted_from_frontend_diagnostics",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_unscoped_query_without_source_family_adjudicator_fails_closed",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_backend_unavailable_and_deictic_queries_fail_closed_without_llm",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_citation_and_evidence_cards_support_text_pdf_and_xlsx_shapes",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_preserves_duplicate_supporting_evidence_id_rows_by_locator",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_validation_errors_and_mutation_surfaces_are_redacted",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_0_closeout_gate_plan_does_not_mutate_protected_or_promote_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_1_official_eval_gate_scaffold_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_2_xlsx_residual_taxonomy_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_3_pdf_text_residual_hardening_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_4_user_owned_approval_packet_does_not_mutate_protected_or_open_official_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_5_user_approved_official_metric_dry_run_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_6_official_metric_scored_execution_fail_closed_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_6_2_official_metric_backend_enabled_preflight_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_6_3_official_metric_backend_probe_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_current_board_records_v563_backend_probe_v562_preflight_and_v560_baseline",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_does_not_keep_stale_current_profile_test_count",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v5_diagnostic_common_helpers_preserve_write_doc_and_payload_semantics",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v477_registry_resolves_current_and_previous_short_keys",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v4712_explicit_check_builds_in_memory_and_current_uses_v560_with_v550_v540_v530_v520_v510_v500_v4718_explicit",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v4718_written_report_status_docs_current_alias_and_explicit_historical_aliases",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v500_current_profile_checks_frozen_v4718_basis_guardrails_without_recomputing",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v500_closeout_report_freezes_v4718_basis_and_keeps_all_gates_closed",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v500_written_report_status_docs_current_alias_and_ignored_artifacts",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v500_check_report_rejects_opened_gates_source_drift_raw_payloads_and_counter_drift",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v500_write_path_synthesizes_v4718_source_report_when_prior_ignored_report_is_missing",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v510_official_eval_gate_scaffold_represents_user_owned_inputs_and_zero_rows",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v510_written_report_status_docs_current_alias_and_ignored_artifacts",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v510_check_report_rejects_opened_user_gates_official_rows_training_and_raw_payloads",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v510_write_path_synthesizes_v500_source_report_when_prior_ignored_report_is_missing",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v520_xlsx_residual_candidate_state_taxonomy_keeps_residual_overlap_fail_closed",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v520_written_report_status_docs_current_alias_and_ignored_artifacts",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v520_check_report_rejects_row_level_overlap_shortcuts_official_rows_and_training",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v520_write_path_synthesizes_v510_source_report_when_prior_ignored_report_is_missing",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v530_pdf_text_residual_retrieval_evidence_hardening_records_scope_and_boundaries",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v530_written_report_status_docs_current_alias_and_ignored_artifacts",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v530_check_report_rejects_shortcuts_official_rows_training_and_residual_drift",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v530_write_path_validates_report_before_writing_and_synthesizes_v520_source_report",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v540_user_owned_approval_packet_materializes_blank_user_fields_and_closes_metric_gate",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v540_written_report_status_docs_current_alias_and_packet_artifacts",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v540_check_report_rejects_filled_user_fields_official_rows_training_and_dry_run",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v540_write_path_validates_report_before_writing_and_synthesizes_v530_source_report",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v550_user_approved_gold_packet_ingests_only_v540_rows_and_builds_official_inputs",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v550_written_report_status_docs_current_alias_and_official_artifacts",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v550_check_report_rejects_scope_expansion_missing_user_approval_and_closed_surface_drift",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v550_check_report_rejects_written_child_artifact_hash_and_payload_drift",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v550_write_path_validates_report_before_writing_and_synthesizes_v540_source_report",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v560_fail_closed_consumes_only_v550_official_metric_input_and_records_duplicate_policy",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v560_injected_answer_and_scorer_backends_score_all_29_rows_without_raw_payloads",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v560_check_report_rejects_scope_expansion_fake_noop_metrics_and_protected_drift",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v560_write_path_writes_scored_result_failure_attribution_status_and_ignored_artifacts",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v560_write_path_validates_report_before_writing_and_uses_v550_source",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v562_env_gate_disabled_records_execution_gate_disabled_without_fake_metrics",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v562_env_enabled_answer_backend_unreachable_is_not_execution_gate_disabled",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v562_answer_generation_model_unavailable_is_separate_from_backend_unreachable",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v562_scorer_preflight_failures_are_separate_after_answer_backend_probe",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v562_injected_answer_and_scorer_backends_score_all_29_rows_after_non_gold_probes",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v562_check_report_rejects_scope_expansion_fake_quality_metrics_and_v56_hash_drift",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v562_write_path_writes_preflight_status_without_measurements_when_unscored",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v562_write_path_validates_report_before_writing_and_uses_v550_source",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v563_env_gate_disabled_records_execution_gate_disabled_without_fake_metrics",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v563_env_enabled_preflight_failure_categories_are_precise",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v563_injected_answer_and_scorer_backends_score_all_29_rows_after_non_gold_probes",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v563_scoring_runtime_failure_fails_closed_without_partial_quality_metric",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v563_check_report_rejects_scope_expansion_fake_quality_metrics_and_prior_hash_drift",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v563_write_path_writes_preflight_status_without_measurements_when_unscored",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v563_write_path_validates_report_before_writing_and_uses_v550_source",
    }
)

CURRENT_RAG_TEST_FILES = frozenset(nodeid.split("::", 1)[0] for nodeid in CURRENT_RAG_TEST_NODEIDS)

NON_CURRENT_RAG_TEST_FILES = frozenset(
    {
        "ai/tests/test_experiment_dependency_cleanup_contract.py",
        "ai/tests/test_fastapi_phase1_diagnostic_rag_route_v1.py",
        "ai/tests/test_multimodal_provider_contract_v1.py",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
        "ai/tests/test_rag_anti_shortcut_guardrail_audit_v1.py",
        "ai/tests/test_rag_canonical_artifact_audit_v1.py",
        "ai/tests/test_rag_eval_v475_contract.py",
        "ai/tests/test_rag_eval_v476_cleanup_contract.py",
        "ai/tests/test_rag_nec_2026_local_election_xlsx_route.py",
        "ai/tests/test_rag_official_answer_citation_metric_first_run_v1.py",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py",
        "ai/tests/test_rag_official_metric_pre_execution_smoke_v1.py",
        "ai/tests/test_rag_pdf_answer_citation_table_value_candidate_v1.py",
        "ai/tests/test_rag_report_only_tuning_dry_run_plan.py",
        "ai/tests/test_rag_source_bound_official_denominator_index.py",
        "ai/tests/test_rag_v4_7_2_korean_review_packet_hydration_contract.py",
        "ai/tests/test_rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_contract.py",
        "ai/tests/test_rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_contract.py",
        "ai/tests/test_rag_v571_retrieval_metric_integrity_audit_contract.py",
        "ai/tests/test_rag_v572_live_retrieval_denominator_and_row_expansion_contract.py",
        "ai/tests/test_rag_v58_retrieval_metric_evaluation_framework_contract.py",
        "ai/tests/test_rag_v59_real_nonprod_structured_hybrid_retrieval_reset_contract.py",
        "ai/tests/test_rag_v60_true_rag_retrieval_rewrite_contract.py",
        "ai/tests/test_rag_v57_vector_llm_candidate_routing_contract.py",
        "ai/tests/test_rag_xlsx_answer_citation_runtime_precision_candidate_v1.py",
    }
)

# v6_4 moves `current` back from the premature v7_0 closeout marker to the
# recovered E2E coverage/failure-taxonomy profile. Keep this current surface
# focused on the recovery contract plus still-relevant preview, guardrail, and rollback checks;
# historical resolver/status files remain directly checkable outside
# `--rag-current`.
CURRENT_RAG_TEST_NODEIDS = frozenset(
    {
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_data_lives_in_shared_support_module",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_includes_required_official_candidate_and_pdf_tests",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_excludes_missing_artifact_noise_from_default_current_loop",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_ai_tests_directory_classifies_current_and_historical_profile_files",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_rag_current_collect_only_matches_exact_nodeid_allowlist",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_accepts_collected_prefixes_and_windows_nodeids",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_marker_assignment_is_nodeid_scoped",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_route_is_default_disabled_and_production_disabled",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_election_query_stays_default_off_and_production_disabled",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_enabled_success_returns_frontend_safe_dto_without_gold_or_raw_leakage",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_election_result_query_uses_llm_adjudicator_for_xlsx_route",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_adjudicator_reason_is_redacted_from_frontend_diagnostics",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_unscoped_query_without_source_family_adjudicator_fails_closed",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_backend_unavailable_and_deictic_queries_fail_closed_without_llm",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_citation_and_evidence_cards_support_text_pdf_and_xlsx_shapes",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_preserves_duplicate_supporting_evidence_id_rows_by_locator",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_validation_errors_and_mutation_surfaces_are_redacted",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_0_closeout_gate_plan_does_not_mutate_protected_or_promote_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_1_official_eval_gate_scaffold_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_2_xlsx_residual_taxonomy_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_3_pdf_text_residual_hardening_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_4_user_owned_approval_packet_does_not_mutate_protected_or_open_official_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_5_user_approved_official_metric_dry_run_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_6_official_metric_scored_execution_fail_closed_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_6_2_official_metric_backend_enabled_preflight_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_6_3_official_metric_backend_probe_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py::test_v62_registers_resolves_current_and_keeps_v61_as_rollback",
        "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py::test_materialization_scaleout_sanitizes_source_derived_payloads_and_quality",
        "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py::test_denominator_reality_ledgers_and_metric_lanes_expose_coverage_limits",
        "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py::test_backend_tool_and_agentic_lanes_are_separate_and_fail_closed",
        "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py::test_leakage_probes_and_local_llm_gpu_paths_are_fail_closed",
        "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py::test_report_bundle_writes_required_artifacts_docs_and_status",
        "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py::test_required_report_fields_and_protected_surfaces_are_closed",
        "ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py::test_v63_registers_current_and_keeps_v62_rollback",
        "ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py::test_bge_m3_faiss_vector_retrieval_and_hydration_are_real_and_separate",
        "ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py::test_e2e_answer_render_citation_and_agentic_guardrails",
        "ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py::test_single_report_policy_and_artifact_hashes",
        "ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py::test_required_report_fields_leakage_and_protected_surfaces_are_closed",
        "ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py::test_embedding_matrix_rejects_fake_zero_and_random_vectors",
        "ai/tests/test_rag_v64_e2e_coverage_and_failure_taxonomy_nonprod_contract.py::test_v64_registers_current_and_keeps_v63_as_rollback",
        "ai/tests/test_rag_v64_e2e_coverage_and_failure_taxonomy_nonprod_contract.py::test_300_row_coverage_family_breakdown_and_candidate_availability",
        "ai/tests/test_rag_v64_e2e_coverage_and_failure_taxonomy_nonprod_contract.py::test_failure_taxonomy_and_metric_denominators_stay_fail_closed",
        "ai/tests/test_rag_v64_e2e_coverage_and_failure_taxonomy_nonprod_contract.py::test_bounded_e2e_render_hydrates_only_source_atom_evidence_bundle",
        "ai/tests/test_rag_v64_e2e_coverage_and_failure_taxonomy_nonprod_contract.py::test_report_leakage_guard_answer_quality_and_protected_surfaces_are_closed",
        "ai/tests/test_rag_v64_e2e_coverage_and_failure_taxonomy_nonprod_contract.py::test_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_v70_registers_explicitly_and_v64_recovery_is_current",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_source_v63_e2e_architecture_is_hash_locked_and_closed",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_report_bundle_writes_single_report_status_docs_and_plan",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_required_fields_and_protected_surfaces_stay_closed",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_v701_registers_explicitly_and_current_resolves_to_v64",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_v701_records_v70_as_premature_closeout_marker_only",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_predecessor_closeout_guard_rejects_missing_without_skip_reason",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_v701_links_v64_recovery_and_preserves_diagnostic_boundaries",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_report_bundle_writes_one_primary_report_status_docs_and_plan",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_no_raw_prompt_response_or_tool_to_rag_leakage",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_legacy_non_rag_paths_are_inventoried_with_owner_call_site_risk_and_isolated",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_true_rag_schema_allows_safe_source_ids_and_rejects_oracle_eval_shortcuts",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_materialization_builds_pdf_xlsx_text_search_units_without_raw_query_time_parsing",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_real_repo_local_hybrid_backend_builds_index_queries_and_rejects_replay_backend",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_langgraph_agentic_loop_has_bounded_retry_and_route_node_cannot_make_candidates",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_tool_lane_is_available_bounded_and_excluded_from_true_rag_hit_metrics",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_metric_policy_reuses_gold_29_and_silver_1000_read_only_with_separate_lanes",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_guardrail_cleanup_current_alias_and_runner_are_relaxed_but_leakage_guards_stay",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_report_bundle_artifacts_docs_status_and_ledgers_are_written_consistently",
    }
)
CURRENT_RAG_TEST_FILES = frozenset(nodeid.split("::", 1)[0] for nodeid in CURRENT_RAG_TEST_NODEIDS)
NON_CURRENT_RAG_TEST_FILES = (
    NON_CURRENT_RAG_TEST_FILES
    | {
        "ai/tests/test_rag_diagnostic_status_sync.py",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py",
        "ai/tests/test_rag_v61_true_rag_corpus_expansion_and_metric_split_hardening_contract.py",
    }
) - CURRENT_RAG_TEST_FILES

MARKER_DESCRIPTIONS = {
    "rag_current": "current RAG official answer/citation work loop",
    "rag_official_metric": "official first-run answer/citation metric tests",
    "rag_xlsx_runtime_candidate": "XLSX runtime precision candidate tests",
    "rag_pdf_current": "current PDF answer/citation table/value candidate tests",
    "rag_artifact_source_of_truth": "official metric artifact source-of-truth audit tests",
    "rag_guardrail_current": "current report-only and no-mutation guardrail tests",
}


def current_rag_test_files() -> frozenset[str]:
    return CURRENT_RAG_TEST_FILES


def is_rag_current_required_nodeid(nodeid: str) -> bool:
    canonical = canonical_nodeid(nodeid)
    return canonical in CURRENT_RAG_TEST_NODEIDS


def current_marker_names_for_nodeid(nodeid: str) -> tuple[str, ...]:
    canonical_node = canonical_nodeid(nodeid)
    if canonical_node not in CURRENT_RAG_TEST_NODEIDS:
        return ()
    canonical = canonical_node.split("::", 1)[0]
    markers = {"rag_current"}
    if "official_answer_citation_metric_first_run" in canonical or "official_metric_pre_execution" in canonical:
        markers.add("rag_official_metric")
    if "source_of_truth_audit" in canonical:
        markers.add("rag_artifact_source_of_truth")
    if "xlsx_answer_citation_runtime_precision_candidate" in canonical:
        markers.add("rag_xlsx_runtime_candidate")
    if "pdf_answer_citation_table_value_candidate" in canonical:
        markers.add("rag_pdf_current")
    if any(token in canonical for token in ("guardrail", "anti_shortcut", "report_only_tuning", "current_focused")):
        markers.add("rag_guardrail_current")
    return tuple(sorted(markers))


def normalized_nodeid(nodeid: str) -> str:
    return nodeid.replace("\\", "/")


def canonical_nodeid(nodeid: str) -> str:
    normalized = normalized_nodeid(nodeid)
    if normalized.startswith("tests/"):
        return normalized.replace("tests/", "ai/tests/", 1)
    return normalized
