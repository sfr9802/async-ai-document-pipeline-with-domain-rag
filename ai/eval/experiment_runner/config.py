from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping, Sequence

from ai.eval.report_paths import ACTUAL_RAG_REPORT_ROOT, REPO_ROOT


ENV_PREFIX = "RAG_EXPERIMENT_"
OBSERVED_ENV_KEYS = (
    "RAG_EXPERIMENT_RUN_ID",
    "RAG_EXPERIMENT_PROFILE",
    "RAG_EXPERIMENT_OUTPUT_MODE",
    "RAG_EXPERIMENT_REPORT_ROOT",
    "RAG_EXPERIMENT_DATASET",
    "RAG_EXPERIMENT_CONTEXT_JSONL",
    "RAG_EXPERIMENT_OUTPUT_DIR",
    "RAG_EXPERIMENT_INDEX",
    "RAG_EXPERIMENT_TOP_K",
)
OUTPUT_MODES = ("dry-run", "report-json")
PROFILE_MODES = ("smoke", "local", "weaviate")
PATH_REDACTION = "<redacted:path>"
_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


@dataclass(frozen=True)
class ExperimentRunConfig:
    experiment: str
    run_id: str
    output_mode: str
    profile: str
    report_root: Path
    repo_root: Path
    observed_env: dict[str, str]
    dataset_path: Path | None = None
    output_dir: Path | None = None
    context_jsonl_path: Path | None = None
    index: str = "current"
    top_k: int = 10

    def report_root_for_metadata(self) -> str:
        return path_value_for_metadata(self.report_root, self.repo_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reproducible experiment runner facade")
    parser.add_argument("--experiment", default="actual-rag", choices=("actual-rag",))
    parser.add_argument("--run-id")
    parser.add_argument("--output-mode", help=f"one of: {', '.join(OUTPUT_MODES)}")
    parser.add_argument("--dry-run", action="store_true", help="emit metadata without invoking the experiment backend")
    parser.add_argument("--profile", choices=PROFILE_MODES)
    parser.add_argument("--report-root")
    parser.add_argument("--dataset")
    parser.add_argument("--output-dir")
    parser.add_argument("--context-jsonl")
    parser.add_argument("--index")
    parser.add_argument("--top-k", type=int)
    return parser


def build_experiment_config(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path = REPO_ROOT,
) -> ExperimentRunConfig:
    env = dict(os.environ if environ is None else environ)
    args = build_parser().parse_args(list(argv or ()))
    output_mode = "dry-run" if args.dry_run else (args.output_mode or env.get("RAG_EXPERIMENT_OUTPUT_MODE") or "dry-run")
    if output_mode not in OUTPUT_MODES:
        raise ValueError(f"RAG_EXPERIMENT_OUTPUT_MODE must be one of {', '.join(OUTPUT_MODES)}")
    run_id = args.run_id or env.get("RAG_EXPERIMENT_RUN_ID") or "experiment-dry-run"
    _validate_run_id(run_id)
    profile = args.profile or env.get("RAG_EXPERIMENT_PROFILE") or "smoke"
    if profile not in PROFILE_MODES:
        raise ValueError(f"RAG_EXPERIMENT_PROFILE must be one of {', '.join(PROFILE_MODES)}")
    report_root_value = args.report_root or env.get("RAG_EXPERIMENT_REPORT_ROOT")
    report_root = Path(report_root_value) if report_root_value else ACTUAL_RAG_REPORT_ROOT
    if not report_root.is_absolute():
        report_root = repo_root / report_root
    dataset_path = _optional_repo_path(args.dataset or env.get("RAG_EXPERIMENT_DATASET"), repo_root)
    output_dir = _optional_repo_path(args.output_dir or env.get("RAG_EXPERIMENT_OUTPUT_DIR"), repo_root)
    context_jsonl_path = _optional_repo_path(args.context_jsonl or env.get("RAG_EXPERIMENT_CONTEXT_JSONL"), repo_root)
    index = args.index or env.get("RAG_EXPERIMENT_INDEX") or "current"
    top_k = args.top_k if args.top_k is not None else int(env.get("RAG_EXPERIMENT_TOP_K") or "10")
    if top_k <= 0:
        raise ValueError("RAG_EXPERIMENT_TOP_K must be a positive integer")

    observed_env = {key: env[key] for key in OBSERVED_ENV_KEYS if key in env and env[key]}
    return ExperimentRunConfig(
        experiment=args.experiment,
        run_id=run_id,
        output_mode=output_mode,
        profile=profile,
        report_root=report_root,
        repo_root=repo_root,
        observed_env=observed_env,
        dataset_path=dataset_path,
        output_dir=output_dir,
        context_jsonl_path=context_jsonl_path,
        index=index,
        top_k=top_k,
    )


def _optional_repo_path(value: str | None, repo_root: Path) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def _validate_run_id(run_id: str) -> None:
    if ".." in run_id or _RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError(
            "RAG_EXPERIMENT_RUN_ID must be a safe run label: letters, digits, '.', '_' "
            "or '-' only; no '..', path separators, drive prefixes, or absolute paths"
        )


def path_value_for_metadata(value: str | Path, repo_root: Path) -> str:
    text = str(value)
    if not text:
        return text
    path = Path(text)
    if _is_unportable_absolute_path_text(text, path):
        return PATH_REDACTION
    if PureWindowsPath(text).drive and not path.is_absolute():
        return PATH_REDACTION
    resolved = path if path.is_absolute() else repo_root / path
    try:
        return resolved.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return PATH_REDACTION


def _is_unportable_absolute_path_text(text: str, path: Path) -> bool:
    return (PurePosixPath(text).is_absolute() or PureWindowsPath(text).is_absolute()) and not path.is_absolute()
