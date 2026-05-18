from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

# Keep the current RAG test surface intentionally compact. Routine diagnostic
# phases should extend these files instead of adding new test_*.py files.
CURRENT_RAG_TEST_FILES = frozenset(
    {
        "ai/tests/test_rag_current_focused_test_profile_v1.py",
        "ai/tests/test_rag_official_answer_citation_metric_first_run_v1.py",
        "ai/tests/test_rag_official_metric_pre_execution_smoke_v1.py",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py",
        "ai/tests/test_rag_source_bound_official_denominator_index.py",
        "ai/tests/test_rag_xlsx_answer_citation_runtime_precision_candidate_v1.py",
        "ai/tests/test_rag_pdf_answer_citation_table_value_candidate_v1.py",
        "ai/tests/test_rag_diagnostic_status_sync.py",
        "ai/tests/test_rag_report_only_tuning_dry_run_plan.py",
        "ai/tests/test_rag_canonical_artifact_audit_v1.py",
        "ai/tests/test_rag_anti_shortcut_guardrail_audit_v1.py",
        "ai/tests/test_rag_diagnostic_guardrail_git_diff.py",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
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
    rel_file = normalized_nodeid(nodeid).split("::", 1)[0]
    return rel_file in CURRENT_RAG_TEST_FILES or rel_file.replace("tests/", "ai/tests/", 1) in CURRENT_RAG_TEST_FILES


def current_marker_names_for_nodeid(nodeid: str) -> tuple[str, ...]:
    rel_file = normalized_nodeid(nodeid).split("::", 1)[0]
    canonical = rel_file.replace("tests/", "ai/tests/", 1)
    if canonical not in CURRENT_RAG_TEST_FILES:
        return ()
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
