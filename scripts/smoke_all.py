"""Compatibility wrapper for scripts/operational/smoke_all.py."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "operational" / "smoke_all.py"
    runpy.run_path(str(target), run_name="__main__")
