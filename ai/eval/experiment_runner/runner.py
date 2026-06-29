from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from ai.eval.experiment_runner.actual_rag import run_actual_rag_experiment
from ai.eval.experiment_runner.config import ExperimentRunConfig
from ai.eval.experiment_runner.metadata import build_run_metadata


ExperimentBackend = Callable[[ExperimentRunConfig], Any]


def default_backend(config: ExperimentRunConfig) -> Any:
    if config.experiment == "actual-rag":
        return run_actual_rag_experiment(config)
    raise ValueError(f"unsupported experiment: {config.experiment}")


def run_experiment(
    config: ExperimentRunConfig,
    *,
    argv: Sequence[str],
    environ: Mapping[str, str],
    backend: ExperimentBackend = default_backend,
) -> dict[str, Any]:
    metadata = build_run_metadata(config, argv=argv, environ=environ)
    if config.output_mode == "dry-run":
        return {**metadata, "backend_invoked": False}
    backend_result = backend(config)
    return {
        **metadata,
        "backend_invoked": True,
        "metadata": metadata,
        "backend_result": backend_result,
    }
