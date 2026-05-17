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
        "ai/tests/test_rag_source_bound_official_denominator_index.py::test_text_query_discards_off_track_xlsx_search_unit_from_scored_citations",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v2_1_citation_contract_repair_artifacts_discard_off_track_citations",
        "ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_includes_required_official_candidate_and_pdf_tests",
    }

    for nodeid in required_nodeids:
        assert rag_conftest.is_rag_current_required_nodeid(nodeid), nodeid


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

    assert existing_test_files == rag_conftest.CURRENT_RAG_TEST_FILES
