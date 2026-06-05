from __future__ import annotations

from pathlib import Path

import pytest

from ai.tests.rag_current_profile import (
    CURRENT_RAG_TEST_FILES,
    CURRENT_RAG_TEST_NODEIDS,
    MARKER_DESCRIPTIONS,
    NON_CURRENT_RAG_TEST_FILES,
    canonical_nodeid,
    current_marker_names_for_nodeid,
    is_rag_current_required_nodeid,
    normalized_nodeid,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


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
