from __future__ import annotations

import sys
import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai"


def _require_ai_on_path() -> None:
    ai_path = str(AI_ROOT)
    if ai_path not in sys.path:
        sys.path.insert(0, ai_path)


def test_experiment_dependency_extra_mirrors_requirements_dev() -> None:
    pyproject = tomllib.loads((AI_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    experiment_extra = set(pyproject["project"]["optional-dependencies"]["experiments"])
    requirements_dev = set()
    for raw_line in (AI_ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            requirements_dev.add(line)

    assert requirements_dev <= experiment_extra


def test_active_experiment_template_is_diagnostic_only_for_legacy_tune_runner() -> None:
    _require_ai_on_path()
    from scripts.tune import (
        active_config_fail_closed_reason,
        load_active_config,
        tuning_sweep_disabled_reason,
    )

    config = load_active_config(AI_ROOT / "eval" / "experiments" / "active.yaml")

    assert active_config_fail_closed_reason(config) is None
    assert tuning_sweep_disabled_reason(config) == (
        "_meta.execution_policy.allow_tuning_sweep=false"
    )


def test_experiment_gitignore_keeps_reproducibility_receipts_trackable() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        "!ai/eval/experiments/rounds/*.json",
        "!ai/eval/experiments/rounds/*.md",
        "!ai/eval/experiments/studies/**/FINAL_BEST.json",
        "!ai/eval/experiments/studies/**/STUDY_SUMMARY.md",
        "!ai/eval/experiments/studies/**/summary.md",
        "ai/eval/experiments/run_output/*",
        "!ai/eval/experiments/run_output/.gitkeep",
    ):
        assert pattern in gitignore

    assert _git_ignore_decision("ai/eval/experiments/run_output/.gitkeep") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/run_output/study_bundle.json") == "ignored"
    assert _git_ignore_decision("ai/eval/experiments/run_output/llm_input.md") == "ignored"
    assert _git_ignore_decision("ai/eval/experiments/rounds/round_01_config.json") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/rounds/round_01_analysis.md") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/FINAL_BEST.json") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/STUDY_SUMMARY.md") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/summary.md") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/study.db") == "ignored"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/plots/plot.png") == "ignored"


def _git_ignore_decision(repo_relative_path: str) -> str:
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--", repo_relative_path],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 1:
        return "trackable"
    assert result.returncode == 0, result.stderr

    pattern_source = result.stdout.split("\t", 1)[0]
    pattern = pattern_source.split(":", 2)[2]
    if pattern.startswith("!"):
        return "trackable"
    return "ignored"
