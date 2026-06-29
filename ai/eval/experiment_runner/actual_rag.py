from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ai.eval.experiment_runner.config import ExperimentRunConfig, path_value_for_metadata


def run_actual_rag_experiment(config: ExperimentRunConfig) -> dict[str, Any]:
    """Delegate actual-RAG execution while new experiments migrate off the monolith."""

    if config.output_mode == "run-sqlite":
        raise ValueError("--output-mode run-sqlite is not wired in experiment_runner; use report-json")
    if config.output_mode != "report-json":
        raise ValueError("actual-RAG execution requires --output-mode report-json")

    from ai.eval import actual_rag_eval

    if not hasattr(actual_rag_eval, "run_eval_from_paths"):
        raise RuntimeError("actual_rag_eval.run_eval_from_paths is unavailable")
    if config.dataset_path is None:
        raise ValueError("--dataset or RAG_EXPERIMENT_DATASET is required outside dry-run mode")
    output_dir = config.output_dir or config.report_root / config.run_id
    bundle = actual_rag_eval.run_eval_from_paths(
        dataset_path=config.dataset_path,
        output_dir=output_dir,
        context_jsonl_path=config.context_jsonl_path,
        index=config.index,
        top_k=config.top_k,
        run_id=config.run_id,
        command="python -m ai.eval.experiment_runner.main",
        report_root=config.report_root,
        output_mode="single",
    )
    return _bundle_to_json_safe_result(config, bundle)


def _bundle_to_json_safe_result(config: ExperimentRunConfig, bundle: Any) -> dict[str, Any]:
    if isinstance(bundle, Mapping):
        return _json_safe(bundle, repo_root=config.repo_root)
    return {
        "output_dir": _path_for_metadata(bundle.output_dir, config.repo_root),
        "items_path": _path_for_metadata(bundle.items_path, config.repo_root),
        "summary_path": _path_for_metadata(bundle.summary_path, config.repo_root),
        "markdown_path": _path_for_metadata(bundle.markdown_path, config.repo_root),
        "report_path": _path_for_metadata(bundle.report_path, config.repo_root) if bundle.report_path else None,
        "summary": _json_safe(bundle.summary, repo_root=config.repo_root),
    }


def _json_safe(value: Any, *, repo_root: Path) -> Any:
    if isinstance(value, Path):
        return _path_for_metadata(value, repo_root)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item, repo_root=repo_root) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_safe(item, repo_root=repo_root) for item in value]
    return value


def _path_for_metadata(path: Path, repo_root: Path) -> str:
    return path_value_for_metadata(path, repo_root)
