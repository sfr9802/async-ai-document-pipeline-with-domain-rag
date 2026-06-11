from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from ai.eval.actual_rag_eval import main


if __name__ == "__main__":
    raise SystemExit(main())
