"""Top-level entry point for the full-capability smoke runner.

Delegates to `ai/scripts/smoke_runner.py`, which holds the real
implementation. This wrapper exists so developers running from the repo
root can invoke the smoke runner without `cd ai/` first:

    python scripts/smoke_all.py                         # compatibility wrapper
    python scripts/operational/smoke_all.py             # canonical path
    python scripts/operational/smoke_all.py --only MOCK,RAG
    python scripts/operational/smoke_all.py --report smoke-report.json

All CLI flags forward verbatim. Use `python scripts/operational/smoke_all.py
--help` for the current workflow and pair it with the local infrastructure
notes in the repository README.

Kept deliberately thin — the real logic (HTTP orchestration, shape
assertions, report building) lives in the worker package so the
ai tests can import it directly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    worker_dir = Path(__file__).resolve().parents[2]
    here = worker_dir.parent
    if not worker_dir.is_dir():
        print(
            f"ERROR: ai directory not found at {worker_dir}. "
            "Run from the repo root.",
            file=sys.stderr,
        )
        return 2

    # Add ai to sys.path so `scripts.smoke_runner` (which imports
    # `app.*`) resolves the same way `python -m scripts.smoke_runner`
    # does when invoked from inside ai/.
    sys.path.insert(0, str(worker_dir))
    # chdir so relative default paths (eval/datasets/samples/...) resolve.
    os.chdir(worker_dir)

    from scripts.smoke_runner import main as runner_main

    return runner_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
