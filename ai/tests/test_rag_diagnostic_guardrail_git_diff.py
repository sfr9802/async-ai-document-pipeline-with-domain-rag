from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = "ai/eval/eval_queries/official_denominator_registry.json"


def test_official_denominator_registry_has_no_worktree_or_staged_diff():
    unstaged = subprocess.run(
        ["git", "diff", "--quiet", "--", REGISTRY_PATH],
        cwd=ROOT,
        check=False,
    )
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", REGISTRY_PATH],
        cwd=ROOT,
        check=False,
    )

    assert unstaged.returncode == 0
    assert staged.returncode == 0
