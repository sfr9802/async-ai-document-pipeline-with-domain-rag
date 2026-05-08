"""Apply prepared PDF review packs as diagnostic retrieval/evidence reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


AI_WORKER = Path(__file__).resolve().parents[1]
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))

from eval.harness.pdf_review_application import (  # noqa: E402
    OFFICIAL_REGISTRY,
    REPORT_DIR,
    REVIEW_DIR,
    ReviewApplicationConfig,
    write_review_application_reports,
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = ReviewApplicationConfig(
        date=args.date,
        review_dir=Path(args.review_dir),
        report_dir=Path(args.report_dir),
        official_registry=Path(args.official_registry),
        max_retries=args.max_retries,
        selected_review_pack=Path(args.review_pack) if args.review_pack else None,
        manifest_path=Path(args.manifest) if args.manifest else None,
    )
    reports = write_review_application_reports(config)
    print(json.dumps(stdout_summary(reports), ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="20260507")
    parser.add_argument("--review-dir", default=str(REVIEW_DIR))
    parser.add_argument("--report-dir", default=str(REPORT_DIR))
    parser.add_argument("--official-registry", default=str(OFFICIAL_REGISTRY))
    parser.add_argument("--review-pack", default=None)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--max-retries", type=int, default=2)
    return parser.parse_args(argv)


def stdout_summary(reports: dict) -> dict:
    validation = reports["validation"]
    application = reports["application"]
    route = reports["route_trace"]
    agentic = reports["agentic_loop"]
    manifest = reports.get("manifest") or {}
    return {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "official_denominator_changed": False,
        "selected_review_pack": validation.get("selected_review_pack", {}).get("path"),
        "source_row_count": application.get("source_row_count"),
        "reviewed_included_row_count": application.get("reviewed_included_row_count"),
        "excluded_row_count": application.get("excluded_row_count"),
        "route_summary": route.get("pdf_reviewed_route_summary"),
        "agentic_retry_summary": agentic.get("agentic_retry_summary"),
        "manifest": reports.get("manifest_path"),
        "manifest_reports": sorted((manifest.get("reports") or {}).keys()),
    }


if __name__ == "__main__":
    raise SystemExit(main())

