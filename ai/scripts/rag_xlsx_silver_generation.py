"""Generate strict XLSX retrieval/evidence silver artifacts.

The command is generation-only: it reads approved XLSX SearchUnit metadata,
writes silver candidate/selected/dev/holdout artifacts, and leaves retrieval,
answer generation, indexing, and official denominators untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


AI_WORKER = Path(__file__).resolve().parents[1]
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))

from eval.harness.xlsx_silver_generation import (  # noqa: E402
    DEFAULT_DB_DSN,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PRE_SILVER_REPORT,
    DEFAULT_REPORT_DIR,
    REPORT_DATE,
    run_generation,
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_generation(
        db_dsn=args.db_dsn,
        output_dir=Path(args.output_dir),
        report_dir=Path(args.report_dir),
        pre_silver_report=Path(args.pre_silver_report),
        selected_limit=args.selected_limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"XLSX_SILVER_GENERATION_COMPLETE", "XLSX_SILVER_GENERATION_PARTIAL_WITH_VALID_ROWS"} else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=REPORT_DATE, help="Report date label. Current v0 filenames are fixed for 20260507.")
    parser.add_argument("--db-dsn", default=DEFAULT_DB_DSN)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--pre-silver-report", default=str(DEFAULT_PRE_SILVER_REPORT))
    parser.add_argument("--selected-limit", type=int, default=500)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
