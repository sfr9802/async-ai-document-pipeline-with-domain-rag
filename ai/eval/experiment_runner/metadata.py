from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai.eval.experiment_runner.config import ExperimentRunConfig, path_value_for_metadata


RUN_METADATA_SCHEMA_VERSION = "experiment_runner.run_metadata.v1"
PATH_ARG_OPTIONS = {"--dataset", "--context-jsonl", "--output-dir", "--report-root"}
PATH_ENV_KEYS = {
    "RAG_EXPERIMENT_DATASET",
    "RAG_EXPERIMENT_CONTEXT_JSONL",
    "RAG_EXPERIMENT_OUTPUT_DIR",
    "RAG_EXPERIMENT_REPORT_ROOT",
}


def _git_commit(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def build_run_metadata(
    config: ExperimentRunConfig,
    *,
    argv: Sequence[str],
    environ: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": RUN_METADATA_SCHEMA_VERSION,
        "experiment": config.experiment,
        "run_id": config.run_id,
        "output_mode": config.output_mode,
        "profile": config.profile,
        "report_root": config.report_root_for_metadata(),
        "argv": _argv_for_metadata(argv, repo_root=config.repo_root),
        "observed_env": _observed_env_for_metadata(config.observed_env, repo_root=config.repo_root),
        "git_commit": _git_commit(config.repo_root),
    }


def _argv_for_metadata(argv: Sequence[str], *, repo_root: Path) -> list[str]:
    metadata_argv: list[str] = []
    redact_next = False
    for token in argv:
        if redact_next:
            metadata_argv.append(path_value_for_metadata(token, repo_root))
            redact_next = False
            continue
        if token in PATH_ARG_OPTIONS:
            metadata_argv.append(token)
            redact_next = True
            continue
        option, separator, value = token.partition("=")
        if separator and option in PATH_ARG_OPTIONS:
            metadata_argv.append(f"{option}={path_value_for_metadata(value, repo_root)}")
            continue
        metadata_argv.append(token)
    return metadata_argv


def _observed_env_for_metadata(observed_env: Mapping[str, str], *, repo_root: Path) -> dict[str, str]:
    return {
        key: path_value_for_metadata(value, repo_root) if key in PATH_ENV_KEYS else value
        for key, value in observed_env.items()
    }
