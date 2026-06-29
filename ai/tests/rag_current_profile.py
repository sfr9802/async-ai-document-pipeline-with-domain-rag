from __future__ import annotations


# Files outside the compact current loop. Keep new diagnostic/reporting tests here
# unless they are explicitly part of the exact current acceptance nodeid set below.
_BASE_NON_CURRENT_RAG_TEST_FILES = frozenset(
    {
        "ai/tests/test_actual_rag_eval_metric_generation.py",
        "ai/tests/test_actual_rag_eval_weaviate_indexing.py",
        "ai/tests/test_actual_rag_eval_weaviate_routes.py",
        "ai/tests/test_actual_rag_eval_agentic_guardrails.py",
        "ai/tests/test_experiment_dependency_cleanup_contract.py",
        "ai/tests/test_experiment_runner_entrypoint.py",
        "ai/tests/test_agentops_portfolio_runtime_contract.py",
        "ai/tests/test_fastapi_phase1_diagnostic_rag_route_v1.py",
        "ai/tests/test_multimodal_provider_contract_v1.py",
        "ai/tests/test_rag_anti_shortcut_guardrail_audit_v1.py",
        "ai/tests/test_rag_canonical_artifact_audit_v1.py",
        "ai/tests/test_rag_eval_v475_contract.py",
        "ai/tests/test_rag_eval_v476_cleanup_contract.py",
        "ai/tests/test_rag_nec_2026_local_election_xlsx_route.py",
        "ai/tests/test_rag_official_answer_citation_metric_first_run_v1.py",
        "ai/tests/test_rag_official_metric_pre_execution_smoke_v1.py",
        "ai/tests/test_rag_pdf_answer_citation_table_value_candidate_v1.py",
        "ai/tests/test_rag_report_only_tuning_dry_run_plan.py",
        "ai/tests/test_rag_v571_retrieval_metric_integrity_audit_contract.py",
        "ai/tests/test_rag_v572_live_retrieval_denominator_and_row_expansion_contract.py",
        "ai/tests/test_rag_v58_retrieval_metric_evaluation_framework_contract.py",
        "ai/tests/test_rag_v59_real_nonprod_structured_hybrid_retrieval_reset_contract.py",
        "ai/tests/test_rag_v60_true_rag_retrieval_rewrite_contract.py",
        "ai/tests/test_rag_v57_vector_llm_candidate_routing_contract.py",
        "ai/tests/test_rag_xlsx_answer_citation_runtime_precision_candidate_v1.py",
    }
)

# v6_9 moves `current` from the v6_8 metric-gated retrieval-quality packet to
# the answer-quality gate packet. Keep this current
# surface focused on the recovery, bridge-audit, response-smoke, and
# tool/RAG-separation/agentic-policy contracts plus still-relevant preview,
# guardrail, and rollback checks; historical resolver/status files remain
# directly checkable outside `--rag-current`.
CURRENT_RAG_TEST_NODEIDS = frozenset(
    {
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_data_lives_in_shared_support_module",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_has_single_canonical_nodeid_definition",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_agentops_portfolio_contract_stays_outside_rag_current_profile",
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
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_v65_report_schema_current_resolver_and_v64_rollback",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_v65_reads_and_verifies_v64_recovery_contract_before_bridge",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_v65_reads_v55_approved_artifacts_immutably",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_bridge_states_are_exhaustive_mutually_exclusive_and_no_rows_drop",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_retrieval_metrics_stay_closed_without_explicit_user_denominator_gate",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_no_gold_qrels_expected_or_baseline_leakage_into_candidate_generation",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_human_review_packet_is_compact_no_decisions_and_no_raw_payloads",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_tool_outputs_answer_quality_official_and_protected_surfaces_stay_closed",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_v70_marker_and_v701_audit_identity_guards",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_protected_namespace_git_status_is_clean_for_v65",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_report_schema_current_resolver_and_v65_rollback",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_reads_and_respects_v65_bridge_audit",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_reads_v55_gold29_read_only_and_attempts_all_rows",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_response_diagnostics_are_compact_and_never_drop_rows",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_candidate_generation_leakage_and_shortcut_guards",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_human_review_packet_contains_actual_answers_but_no_decisions",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_metrics_tools_evidence_truth_and_protected_surfaces_stay_closed",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_v7_marker_guard_remains_active",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_protected_namespace_git_status_is_clean_for_v651",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_v66_schema_current_and_rollback",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_v66_reads_v651_actual_response_smoke_as_rollback",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_v66_tool_and_rag_metrics_are_separate",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_v66_tool_taxonomy_is_exhaustive",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_v66_structured_tool_family_coverage_is_diagnostic_only",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_v66_protected_boundaries_stay_closed",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_v66_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_protected_namespace_git_status_is_clean_for_v66",
        "ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py::test_v67_schema_current_and_rollback",
        "ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py::test_v67_agentic_policy_separates_choices_from_quality",
        "ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py::test_v67_retry_policy_is_fail_closed",
        "ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py::test_v67_agentic_rows_never_drop_and_remain_compact",
        "ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py::test_v67_boundaries_and_protected_surfaces_stay_closed",
        "ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py::test_v67_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py::test_protected_namespace_git_status_is_clean_for_v67",
        "ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py::test_v68_schema_current_and_rollback",
        "ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py::test_v68_retrieval_metric_gate_is_closed_without_safe_bridge",
        "ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py::test_v68_metric_denominators_are_separate",
        "ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py::test_v68_engineering_diagnostics_do_not_score_quality",
        "ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py::test_v68_boundaries_and_protected_surfaces_stay_closed",
        "ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py::test_v68_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py::test_protected_namespace_git_status_is_clean_for_v68",
        "ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::test_v69_schema_current_and_rollback",
        "ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::test_v69_answer_quality_gate_is_review_packet_not_metric",
        "ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::test_v69_no_raw_prompt_response_payloads",
        "ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::test_v69_gate_rows_join_response_tool_agentic_and_retrieval_gate",
        "ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::test_v69_boundaries_and_protected_surfaces_stay_closed",
        "ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::test_v69_single_primary_report_status_handoff_and_hash_contract",
        "ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::test_protected_namespace_git_status_is_clean_for_v69",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_legacy_real_rag_quality_gate_report_scores_answer_evidence_and_critic",
        "ai/tests/test_actual_rag_eval_selected_evidence.py::test_evidence_gate_diagnostic_computes_decision_without_mutating_answer",
        "ai/tests/test_actual_rag_eval_selected_evidence.py::test_evidence_gate_enforce_abstains_unsupported_numeric_and_entity_anchors",
        "ai/tests/test_actual_rag_eval_selected_evidence.py::test_evidence_gate_enforce_abstains_conflicting_numeric_date_evidence",
        "ai/tests/test_actual_rag_eval_selected_evidence.py::test_evidence_gate_enforce_blocks_off_topic_answer_missing_query_anchors_without_gold",
        "ai/tests/test_actual_rag_eval_selected_evidence.py::test_citation_validator_requires_selected_evidence_not_retrieved_context_only",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_citation_validator_rejects_same_doc_chunk_with_different_source_identity",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_run_eval_preserves_citation_source_identity_for_evidence_gate",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_evidence_gate_handles_empty_rows_and_invalid_mode",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_evidence_gate_ignores_expected_evidence_resolution_for_enforcement",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_evidence_gate_does_not_use_title_or_workbook_metadata_as_support",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_validate_actual_rag_guardrails_rejects_semantic_raw_response_without_evidence_gate",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_validate_actual_rag_guardrails_accepts_evidence_gate_without_semantic_samples",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_evidence_gate_summary_is_embedded_in_quality_gate_report",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_quality_gate_baseline_auto_selects_exact_query_id_coverage",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_run_eval_writes_legacy_real_rag_quality_gate_artifacts_without_using_baseline_for_candidates",
        "ai/tests/test_actual_rag_eval_metric_generation.py::test_run_eval_enforce_evidence_gate_before_quality_gate_artifacts_and_preserves_single_output_policy",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_v70_registers_explicitly_and_v64_recovery_is_current",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_source_v63_e2e_architecture_is_hash_locked_and_closed",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_report_bundle_writes_single_report_status_and_worker_handoff",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_required_fields_and_protected_surfaces_stay_closed",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_v701_registers_explicitly_and_preserves_live_current_v69",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_v701_records_v70_as_premature_closeout_marker_only",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_predecessor_closeout_guard_rejects_missing_without_skip_reason",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_v701_links_v64_recovery_and_preserves_diagnostic_boundaries",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_report_bundle_writes_one_primary_report_status_and_worker_handoff",
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
    _BASE_NON_CURRENT_RAG_TEST_FILES
    | {
        "ai/tests/test_rag_v61_true_rag_corpus_expansion_and_metric_split_hardening_contract.py",
        "ai/tests/test_rag_v691_retrieval_smoke_pre_review_packet_nonprod_contract.py",
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
