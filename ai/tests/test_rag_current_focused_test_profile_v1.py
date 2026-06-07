from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

from ai.tests import rag_current_profile

ROOT = Path(__file__).resolve().parents[2]
CONFTEST_PATH = ROOT / "ai" / "tests" / "conftest.py"


REQUIRED_CURRENT_PROFILE_SENTINELS = frozenset(
    {
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_election_result_query_uses_llm_adjudicator_for_xlsx_route",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_adjudicator_reason_is_redacted_from_frontend_diagnostics",
        "ai/tests/test_fastapi_product_rag_preview_route_v1.py::test_product_rag_preview_unscoped_query_without_source_family_adjudicator_fails_closed",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v5_6_3_official_metric_backend_probe_does_not_mutate_protected_or_export_training_surfaces",
        "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py::test_v62_registers_resolves_current_and_keeps_v61_as_rollback",
        "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py::test_denominator_reality_ledgers_and_metric_lanes_expose_coverage_limits",
        "ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py::test_v63_registers_current_and_keeps_v62_rollback",
        "ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py::test_single_report_policy_and_artifact_hashes",
        "ai/tests/test_rag_v64_e2e_coverage_and_failure_taxonomy_nonprod_contract.py::test_v64_registers_current_and_keeps_v63_as_rollback",
        "ai/tests/test_rag_v64_e2e_coverage_and_failure_taxonomy_nonprod_contract.py::test_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_v65_report_schema_current_resolver_and_v64_rollback",
        "ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py::test_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_report_schema_current_resolver_and_v65_rollback",
        "ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py::test_v651_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_v66_schema_current_and_rollback",
        "ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py::test_v66_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py::test_v67_schema_current_and_rollback",
        "ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py::test_v67_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py::test_v68_schema_current_and_rollback",
        "ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py::test_v68_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::test_v69_schema_current_and_rollback",
        "ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::test_v69_single_primary_report_status_docs_and_hash_contract",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_v70_registers_explicitly_and_v64_recovery_is_current",
        "ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py::test_required_fields_and_protected_surfaces_stay_closed",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_v701_registers_explicitly_and_preserves_live_current_v69",
        "ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py::test_v701_records_v70_as_premature_closeout_marker_only",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_guardrail_cleanup_current_alias_and_runner_are_relaxed_but_leakage_guards_stay",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_real_repo_local_hybrid_backend_builds_index_queries_and_rejects_replay_backend",
    }
)


def load_conftest():
    spec = importlib.util.spec_from_file_location("rag_current_conftest_for_tests", CONFTEST_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_profile_data_lives_in_shared_support_module() -> None:
    profile_spec = importlib.util.find_spec("ai.tests.rag_current_profile")
    assert profile_spec is not None
    profile = importlib.import_module("ai.tests.rag_current_profile")
    rag_conftest = load_conftest()

    assert rag_conftest.CURRENT_RAG_TEST_NODEIDS is profile.CURRENT_RAG_TEST_NODEIDS
    assert rag_conftest.NON_CURRENT_RAG_TEST_FILES is profile.NON_CURRENT_RAG_TEST_FILES
    assert rag_conftest.CURRENT_RAG_TEST_FILES == profile.current_rag_test_files()


def test_current_profile_includes_required_official_candidate_and_pdf_tests() -> None:
    rag_conftest = load_conftest()
    required_nodeids = rag_current_profile.CURRENT_RAG_TEST_NODEIDS

    assert REQUIRED_CURRENT_PROFILE_SENTINELS <= required_nodeids
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
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py",
        "ai/tests/test_rag_diagnostic_status_sync.py",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
        "ai/tests/test_fastapi_phase1_diagnostic_rag_route_v1.py",
        "ai/tests/test_rag_v61_true_rag_corpus_expansion_and_metric_split_hardening_contract.py",
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
        "tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::"
        "test_v69_schema_current_and_rollback"
    )
    windows_selected = selected.replace("/", "\\")
    nonselected_same_file = (
        "tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::"
        "test_nonexistent_historical_current_alias_assertion"
    )

    assert rag_conftest.is_rag_current_required_nodeid(selected)
    assert rag_conftest.is_rag_current_required_nodeid(windows_selected)
    assert not rag_conftest.is_rag_current_required_nodeid(nonselected_same_file)


def test_current_profile_marker_assignment_is_nodeid_scoped() -> None:
    rag_conftest = load_conftest()
    selected = (
        "tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::"
        "test_v69_schema_current_and_rollback"
    )
    nonselected_same_file = (
        "tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py::"
        "test_nonexistent_historical_current_alias_assertion"
    )

    assert "rag_current" in rag_conftest.current_marker_names_for_nodeid(selected)
    assert rag_conftest.current_marker_names_for_nodeid(nonselected_same_file) == ()
