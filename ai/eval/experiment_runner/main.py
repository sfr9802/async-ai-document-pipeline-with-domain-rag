from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Mapping, Sequence, TextIO

from ai.eval.experiment_runner.config import build_experiment_config
from ai.eval.experiment_runner.runner import ExperimentBackend, default_backend, run_experiment


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO = sys.stdout,
    repo_root: Path | None = None,
    backend: ExperimentBackend = default_backend,
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ if environ is None else environ)
    config = build_experiment_config(args, environ=env, repo_root=repo_root or Path(__file__).resolve().parents[3])
    result = run_experiment(config, argv=args, environ=env, backend=backend)
    stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
