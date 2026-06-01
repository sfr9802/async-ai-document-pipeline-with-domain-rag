from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFTEST_PATH = ROOT / "ai" / "tests" / "conftest.py"


def current_profile_nodeids() -> set[str]:
    return {
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_includes_required_official_candidate_and_pdf_tests",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_excludes_missing_artifact_noise_from_default_current_loop",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_ai_tests_directory_classifies_current_and_historical_profile_files",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_rag_current_collect_only_matches_exact_nodeid_allowlist",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_accepts_collected_prefixes_and_windows_nodeids",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_marker_assignment_is_nodeid_scoped",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_0_closeout_gate_plan_does_not_mutate_protected_or_promote_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_1_official_eval_gate_scaffold_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_2_xlsx_residual_taxonomy_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_3_pdf_text_residual_hardening_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_4_user_owned_approval_packet_does_not_mutate_protected_or_open_official_surfaces",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_current_board_uses_latest_scored_baseline_not_backend_unavailable",
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_does_not_keep_stale_current_profile_test_count",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v5_diagnostic_common_helpers_preserve_write_doc_and_payload_semantics",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v477_registry_resolves_current_and_previous_short_keys",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v4712_explicit_check_builds_in_memory_and_current_uses_v540_with_v530_v520_v510_v500_v4718_explicit",
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
    }


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
    required_nodeids = current_profile_nodeids()

    assert rag_conftest.CURRENT_RAG_TEST_NODEIDS == required_nodeids
    for nodeid in required_nodeids:
        assert rag_conftest.is_rag_current_required_nodeid(nodeid), nodeid
        rel_file, test_name = nodeid.split("::", 1)
        assert f"def {test_name}(" in (ROOT / rel_file).read_text(encoding="utf-8"), nodeid


def test_current_profile_excludes_missing_artifact_noise_from_default_current_loop() -> None:
    rag_conftest = load_conftest()
    historical = "ai/tests/test_rag_answer_recovery_bridge.py::test_diagnostic_harness_emits_reports_and_trace"
    optional = "ai/tests/test_eval_harness.py::TestCommittedSampleDatasets::test_rag_sample_parses"
    stale_broad_historical = (
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py::"
        "test_v4_6_10_external_holdout_manifest_gate_replay_blocks_without_manifest_policy_and_holdout"
    )

    assert not rag_conftest.is_rag_current_required_nodeid(historical)
    assert not rag_conftest.is_rag_current_required_nodeid(optional)
    assert not rag_conftest.is_rag_current_required_nodeid(stale_broad_historical)
    assert "rag_current" in rag_conftest.MARKER_DESCRIPTIONS
    assert "rag_external_artifact" not in rag_conftest.MARKER_DESCRIPTIONS
    assert "rag_optional_dataset" not in rag_conftest.MARKER_DESCRIPTIONS


def test_ai_tests_directory_classifies_current_and_historical_profile_files() -> None:
    rag_conftest = load_conftest()
    existing_test_files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "ai" / "tests").glob("test_*.py")
    }
    forbidden_name_fragments = ("scratch", "tmp", "temp", "adhoc", "ad_hoc", "legacy", "unused")

    assert not (rag_conftest.CURRENT_RAG_TEST_FILES & rag_conftest.NON_CURRENT_RAG_TEST_FILES)
    assert existing_test_files == rag_conftest.CURRENT_RAG_TEST_FILES | rag_conftest.NON_CURRENT_RAG_TEST_FILES
    assert {
        "ai/tests/test_rag_eval_v475_contract.py",
        "ai/tests/test_rag_eval_v476_cleanup_contract.py",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
        "ai/tests/test_fastapi_phase1_diagnostic_rag_route_v1.py",
    } <= rag_conftest.NON_CURRENT_RAG_TEST_FILES
    assert not [
        rel_path
        for rel_path in existing_test_files
        if any(fragment in Path(rel_path).name.lower() for fragment in forbidden_name_fragments)
    ]
    for nodeid in sorted(rag_conftest.CURRENT_RAG_TEST_NODEIDS):
        rel_file, test_name = nodeid.split("::", 1)
        assert rel_file in rag_conftest.CURRENT_RAG_TEST_FILES
        assert f"def {test_name}(" in (ROOT / rel_file).read_text(encoding="utf-8"), nodeid


def test_rag_current_collect_only_matches_exact_nodeid_allowlist() -> None:
    rag_conftest = load_conftest()
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "pytest", "ai/tests", "--rag-current", "--collect-only", "-q"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    collected = {
        rag_conftest.canonical_nodeid(line.strip())
        for line in result.stdout.splitlines()
        if line.startswith(("tests/", "ai/tests/")) and "::" in line
    }

    assert collected == rag_conftest.CURRENT_RAG_TEST_NODEIDS
    assert "test_rag_answer_citation_silver_manifest_v1.py" not in result.stdout


def test_current_profile_accepts_collected_prefixes_and_windows_nodeids() -> None:
    rag_conftest = load_conftest()
    selected = (
        "tests/test_rag_eval_v477_archive_aware_short_key_contract.py::"
        "test_v510_official_eval_gate_scaffold_represents_user_owned_inputs_and_zero_rows"
    )
    windows_selected = selected.replace("/", "\\")
    nonselected_same_file = (
        "tests/test_rag_eval_v477_archive_aware_short_key_contract.py::"
        "test_v4718_check_report_rejects_shortcuts_opened_gates_raw_payloads_and_regression_drift"
    )

    assert rag_conftest.is_rag_current_required_nodeid(selected)
    assert rag_conftest.is_rag_current_required_nodeid(windows_selected)
    assert not rag_conftest.is_rag_current_required_nodeid(nonselected_same_file)


def test_current_profile_marker_assignment_is_nodeid_scoped() -> None:
    rag_conftest = load_conftest()
    selected = (
        "tests/test_rag_eval_v477_archive_aware_short_key_contract.py::"
        "test_v510_official_eval_gate_scaffold_represents_user_owned_inputs_and_zero_rows"
    )
    nonselected_same_file = (
        "tests/test_rag_eval_v477_archive_aware_short_key_contract.py::"
        "test_v4718_check_report_rejects_shortcuts_opened_gates_raw_payloads_and_regression_drift"
    )

    assert "rag_current" in rag_conftest.current_marker_names_for_nodeid(selected)
    assert rag_conftest.current_marker_names_for_nodeid(nonselected_same_file) == ()
