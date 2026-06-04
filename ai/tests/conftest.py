from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

# Keep the current RAG test surface intentionally compact. Routine diagnostic
# phases should add exact nodeids here instead of pulling broad historical files
# into the default current loop.
CURRENT_RAG_TEST_NODEIDS = frozenset(
    {
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_includes_required_official_candidate_and_pdf_tests",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_excludes_missing_artifact_noise_from_default_current_loop",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_ai_tests_directory_classifies_current_and_historical_profile_files",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_rag_current_collect_only_matches_exact_nodeid_allowlist",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_accepts_collected_prefixes_and_windows_nodeids",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_marker_assignment_is_nodeid_scoped",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_route_is_default_disabled_and_production_disabled",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_enabled_success_returns_frontend_safe_dto_without_gold_or_raw_leakage",
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
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_current_board_records_v562_backend_enabled_preflight_and_v560_baseline",
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
    }
)

CURRENT_RAG_TEST_FILES = frozenset(nodeid.split("::", 1)[0] for nodeid in CURRENT_RAG_TEST_NODEIDS)

NON_CURRENT_RAG_TEST_FILES = frozenset(
    {
        "ai/tests/test_fastapi_phase1_diagnostic_rag_route_v1.py",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
        "ai/tests/test_rag_anti_shortcut_guardrail_audit_v1.py",
        "ai/tests/test_rag_canonical_artifact_audit_v1.py",
        "ai/tests/test_rag_eval_v475_contract.py",
        "ai/tests/test_rag_eval_v476_cleanup_contract.py",
        "ai/tests/test_rag_official_answer_citation_metric_first_run_v1.py",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py",
        "ai/tests/test_rag_official_metric_pre_execution_smoke_v1.py",
        "ai/tests/test_rag_pdf_answer_citation_table_value_candidate_v1.py",
        "ai/tests/test_rag_report_only_tuning_dry_run_plan.py",
        "ai/tests/test_rag_source_bound_official_denominator_index.py",
        "ai/tests/test_rag_v4_7_2_korean_review_packet_hydration_contract.py",
        "ai/tests/test_rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_contract.py",
        "ai/tests/test_rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_contract.py",
        "ai/tests/test_rag_xlsx_answer_citation_runtime_precision_candidate_v1.py",
    }
)

MARKER_DESCRIPTIONS = {
    "rag_current": "current RAG official answer/citation work loop",
    "rag_official_metric": "official first-run answer/citation metric tests",
    "rag_xlsx_runtime_candidate": "XLSX runtime precision candidate tests",
    "rag_pdf_current": "current PDF answer/citation table/value candidate tests",
    "rag_artifact_source_of_truth": "official metric artifact source-of-truth audit tests",
    "rag_guardrail_current": "current report-only and no-mutation guardrail tests",
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--rag-current",
        action="store_true",
        default=False,
        help="collect only the current RAG official metric / candidate / guardrail focused profile",
    )


def pytest_configure(config: pytest.Config) -> None:
    for marker, description in MARKER_DESCRIPTIONS.items():
        config.addinivalue_line("markers", f"{marker}: {description}")


def pytest_ignore_collect(collection_path: object, config: pytest.Config) -> bool | None:
    if not config.getoption("--rag-current"):
        return None
    path = Path(str(collection_path))
    if path.suffix != ".py" or not path.name.startswith("test_"):
        return None
    rel_path = repo_relative_path(path)
    if rel_path.startswith("ai/tests/") and rel_path not in CURRENT_RAG_TEST_FILES:
        return True
    return None


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        for marker in current_marker_names_for_nodeid(item.nodeid):
            item.add_marker(getattr(pytest.mark, marker))

    if config.getoption("--rag-current"):
        selected = [item for item in items if is_rag_current_required_nodeid(item.nodeid)]
        deselected = [item for item in items if not is_rag_current_required_nodeid(item.nodeid)]
        if deselected:
            config.hook.pytest_deselected(items=deselected)
            items[:] = selected


def repo_relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


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
