"""Write diagnostic-only XLSX/PDF agentic route-loop reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


AI_WORKER = Path(__file__).resolve().parents[1]
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))

from eval.harness.xlsx_pdf_route_trace import (  # noqa: E402
    DEFAULT_PDF_REPORT,
    DEFAULT_XLSX_HIDDEN_REPORT,
    DEFAULT_XLSX_REPORT,
    OFFICIAL_REGISTRY,
    DiagnosticReporter,
    TraceConfig,
    default_agentic_report_paths,
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    default_json, default_md = default_agentic_report_paths(args.date)
    config = TraceConfig(
        date=args.date,
        max_xlsx_queries=args.max_xlsx_queries,
        max_pdf_queries=args.max_pdf_queries,
        xlsx_report=Path(args.xlsx_report),
        xlsx_hidden_report=Path(args.xlsx_hidden_report),
        pdf_report=Path(args.pdf_report),
        official_registry=Path(args.official_registry),
        report_path=Path(args.report) if args.report else default_json,
        markdown_path=Path(args.markdown) if args.markdown else default_md,
        max_retries=args.max_retries,
    )
    reporter = DiagnosticReporter()
    payload = reporter.agentic_loop_report(config)
    reporter.write(payload, json_path=config.report_path or default_json, markdown_path=config.markdown_path or default_md)
    print(json.dumps(stdout_summary(payload, config.report_path or default_json, config.markdown_path or default_md), ensure_ascii=False, indent=2))
    return 0 if payload.get("status") != "FAIL" else 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="20260507")
    parser.add_argument("--max-xlsx-queries", type=int, default=5)
    parser.add_argument("--max-pdf-queries", type=int, default=5)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--xlsx-report", default=str(DEFAULT_XLSX_REPORT))
    parser.add_argument("--xlsx-hidden-report", default=str(DEFAULT_XLSX_HIDDEN_REPORT))
    parser.add_argument("--pdf-report", default=str(DEFAULT_PDF_REPORT))
    parser.add_argument("--official-registry", default=str(OFFICIAL_REGISTRY))
    parser.add_argument("--report", default=None)
    parser.add_argument("--markdown", default=None)
    return parser.parse_args(argv)


def stdout_summary(payload: dict, report: Path, markdown: Path) -> dict:
    return {
        "status": payload.get("status"),
        "report_role": payload.get("report_role"),
        "promotion_evidence": payload.get("promotion_evidence"),
        "official_denominator_changed": payload.get("official_denominator_changed"),
        "route_counts": payload.get("route_counts"),
        "agentic_retry_summary": payload.get("agentic_retry_summary"),
        "guardrail_failures": payload.get("guardrail_failures"),
        "report": str(report),
        "markdown": str(markdown),
    }


if __name__ == "__main__":
    raise SystemExit(main())
