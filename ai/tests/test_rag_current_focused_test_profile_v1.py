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
        "ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_does_not_keep_stale_current_profile_test_count",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py::test_v560_fail_closed_consumes_only_v550_official_metric_input_and_records_duplicate_policy",
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
