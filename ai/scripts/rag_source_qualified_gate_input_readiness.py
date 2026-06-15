"""Validate source-qualified promotion-gate input contract.

This report checks only whether canonical source-qualified metrics are present
and cleanly sourced. It does not evaluate retrieval quality thresholds and does
not turn diagnostic retrieval output into promotion evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from rag_build_promotion_gate_metrics import SOURCE_QUALIFIED_REQUIRED


DEFAULT_METRICS = Path("reports/rag_eval/rag-ingestion/rag_ingestion_a5_promotion_gate_metrics.json")
DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/a5_c2_source_qualified_report_contract_readiness.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_readiness(
        metrics_report_path=Path(args.metrics_report),
        expected_retrieval_backend=args.expected_retrieval_backend,
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload["status"] == "PASS" else 2


def build_readiness(*, metrics_report_path: Path, expected_retrieval_backend: str) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    report = read_metrics_report(metrics_report_path, blockers)
    metrics = dict(report.get("metrics") or {}) if isinstance(report, Mapping) else {}
    canonical_names = set(metrics.get("canonical_metric_names") or report.get("canonical_metric_names") or [])
    required_names = required_canonical_names()
    missing_names = sorted(name for name in required_names if name not in canonical_names)
    gate_input_missing = list(metrics.get("gate_input_missing") or report.get("gate_input_missing") or [])
    gate_input_missing_count = int(metrics.get("gate_input_missing_count") or report.get("gate_input_missing_count") or 0)
    derived_sources = dict(metrics.get("derived_metric_sources") or report.get("derived_metric_sources") or {})
    retrieval_backend = metrics.get("retrieval_backend")

    if missing_names:
        blockers.append("canonical_metric_names missing required source-qualified metrics")
    if gate_input_missing_count != 0:
        blockers.append("gate_input_missing_count must be 0")
    if gate_input_missing:
        blockers.append("gate_input_missing must be empty")
    if derived_sources:
        blockers.append("derived_metric_sources must be empty for source-qualified readiness")
    if retrieval_backend == "library_search":
        blockers.append("library_search report cannot be source-qualified promotion-grade vector input")
    if expected_retrieval_backend and retrieval_backend != expected_retrieval_backend:
        blockers.append(f"retrieval_backend must be {expected_retrieval_backend}")

    if metrics.get("promotion_evidence") is not True:
        warnings.append(
            "retrieval metrics are diagnostic-only; C2 source-qualified input can PASS without implying promotion"
        )

    return {
        "run_id": utc_run_id(),
        "status": "PASS" if not blockers else "FAIL",
        "report_role": "source_qualified_gate_input_readiness",
        "promotion_evidence": False,
        "metrics_report": str(metrics_report_path),
        "gate_input_missing_count": gate_input_missing_count,
        "gate_input_missing": gate_input_missing,
        "canonical_metric_names": sorted(canonical_names),
        "required_canonical_metric_names": required_names,
        "missing_canonical_metric_names": missing_names,
        "derived_metric_sources": derived_sources,
        "retrieval_backend": retrieval_backend,
        "retrieval_backend_identity": metrics.get("retrieval_backend_identity") or {},
        "source_reports": metrics.get("source_reports") or [],
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "notes": [
            "This checks source-qualified metric presence only.",
            "It does not evaluate threshold quality or execute promotion.",
            "Diagnostic vector reports remain diagnostic until rerun with explicit promotion evidence.",
        ],
    }


def required_canonical_names() -> list[str]:
    return sorted(
        f"{source_name}.{metric_name}"
        for source_name, metric_names in SOURCE_QUALIFIED_REQUIRED.items()
        for metric_name in metric_names
    )


def read_metrics_report(path: Path, blockers: list[str]) -> dict[str, Any]:
    if not path.exists():
        blockers.append(f"metrics_report missing: {path}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        blockers.append(f"metrics_report must be a JSON object: {path}")
        return {}
    return payload


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-report", default=str(DEFAULT_METRICS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--expected-retrieval-backend", default="vector")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
