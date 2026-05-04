"""Build promotion-gate metrics from RAG ingestion smoke/eval reports.

The output intentionally separates source-qualified canonical metrics from
legacy aggregate compatibility metrics. Missing canonical inputs are reported
through gate_input_missing; they are not silently converted into passing
defaults.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_XLSX_REPORT = Path("reports/rag_ingestion_sample_batch_report.json")
DEFAULT_PDF_REPORT = Path("reports/rag_pdf_ingestion_sample_batch_report.json")
DEFAULT_RETRIEVAL_REPORT = Path("reports/rag_retrieval_eval_report.json")
DEFAULT_OCR_REPORT = Path("reports/rag_pdf_ocr_fallback_smoke_report.json")
DEFAULT_OUTPUT = Path("reports/rag_ingestion_promotion_gate_metrics.json")

SOURCE_QUALIFIED_REQUIRED = {
    "xlsx": (
        "parser_success_rate",
        "unsupported_file_rate",
        "fatal_warning_count",
        "zero_indexable_chunk_count",
        "missing_required_metadata_count",
        "hidden_content_leakage_count",
        "parsing_latency_p95_seconds",
        "indexing_latency_p95_seconds",
    ),
    "pdf": (
        "parser_success_rate",
        "unsupported_file_rate",
        "fatal_warning_count",
        "zero_indexable_chunk_count",
        "missing_required_metadata_count",
        "missing_page_metadata_count",
        "inconsistent_location_page_metadata_count",
        "invalid_pdf_location_count",
        "missing_pdf_citation_text_count",
        "hidden_content_leakage_count",
        "parsing_latency_p95_seconds",
        "indexing_latency_p95_seconds",
    ),
    "ocr": (
        "unsupported_file_rate",
        "fatal_warning_count",
        "ocr_confidence_avg",
        "low_trust_ocr_chunk_count",
        "hidden_content_leakage_count",
        "parsing_latency_p95_seconds",
        "indexing_latency_p95_seconds",
    ),
    "retrieval": (
        "Hit@10",
        "MRR@10",
        "citation_accuracy",
        "hidden_content_leakage_count",
        "indexing_filtered_hit_count",
        "required_index_version_mismatch_count",
        "embedding_status_mismatch_count",
        "candidate_index_mismatch_count",
    ),
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    xlsx = read_json(Path(args.xlsx_report))
    pdf = read_json(Path(args.pdf_report))
    retrieval = read_json(Path(args.retrieval_report))
    ocr = read_json(Path(args.ocr_report)) if Path(args.ocr_report).exists() else {}

    gate_input_missing: list[str] = []
    derived_metric_sources: dict[str, str] = {}
    source_qualified = build_source_qualified_metrics(
        xlsx=xlsx,
        pdf=pdf,
        ocr=ocr,
        retrieval=retrieval,
        missing=gate_input_missing,
        derived_metric_sources=derived_metric_sources,
    )
    canonical_metrics = flatten_source_qualified(source_qualified)

    xlsx_metrics = source_qualified["xlsx"]
    pdf_metrics = source_qualified["pdf"]
    ocr_metrics = source_qualified["ocr"]
    retrieval_metrics = source_qualified["retrieval"]

    missing_required = int_metric(xlsx_metrics, "missing_required_metadata_count") + int_metric(
        pdf_metrics,
        "missing_required_metadata_count",
    )
    zero_indexable = int_metric(xlsx_metrics, "zero_indexable_chunk_count") + int_metric(
        pdf_metrics,
        "zero_indexable_chunk_count",
    )
    unsupported_file_rate = max(
        float_metric(xlsx_metrics, "unsupported_file_rate"),
        float_metric(pdf_metrics, "unsupported_file_rate"),
        float_metric(ocr_metrics, "unsupported_file_rate"),
    )
    fatal_warning_count = (
        int_metric(xlsx_metrics, "fatal_warning_count")
        + int_metric(pdf_metrics, "fatal_warning_count")
        + int_metric(ocr_metrics, "fatal_warning_count")
    )
    parsing_latency_p95_seconds = max(
        float_metric(xlsx_metrics, "parsing_latency_p95_seconds"),
        float_metric(pdf_metrics, "parsing_latency_p95_seconds"),
        float_metric(ocr_metrics, "parsing_latency_p95_seconds"),
    )
    indexing_latency_p95_seconds = max(
        float_metric(xlsx_metrics, "indexing_latency_p95_seconds"),
        float_metric(pdf_metrics, "indexing_latency_p95_seconds"),
        float_metric(ocr_metrics, "indexing_latency_p95_seconds"),
    )
    hidden_content_leakage_count = (
        int_metric(xlsx_metrics, "hidden_content_leakage_count")
        + int_metric(pdf_metrics, "hidden_content_leakage_count")
        + int_metric(ocr_metrics, "hidden_content_leakage_count")
        + int_metric(retrieval_metrics, "hidden_content_leakage_count")
    )
    missing_table_metadata = required_compat_int(
        gate_input_missing,
        dict(xlsx.get("metrics") or {}),
        "missing_table_metadata_count",
        "xlsx",
    )

    metrics = {
        **canonical_metrics,
        "source_qualified_metrics": source_qualified,
        "canonical_metric_names": sorted(canonical_metrics.keys()),
        "derived_metric_sources": derived_metric_sources,
        "parser_success_rate": min(
            float_metric(xlsx_metrics, "parser_success_rate"),
            float_metric(pdf_metrics, "parser_success_rate"),
        ),
        "unsupported_file_rate": unsupported_file_rate,
        "zero_indexable_chunk_count": zero_indexable,
        "required_metadata_completeness": 1.0 if missing_required == 0 else 0.0,
        "missing_required_metadata_count": missing_required,
        "xlsx_citation_location_accuracy": optional_float(
            dict(retrieval.get("metrics") or {}),
            "xlsx_citation_location_accuracy",
            default=0.0,
        ),
        "pdf_citation_location_accuracy": optional_float(
            dict(retrieval.get("metrics") or {}),
            "pdf_citation_location_accuracy",
            default=0.0,
        ),
        "table_detection_accuracy": 1.0 if missing_table_metadata == 0 else 0.0,
        "OCR_needed_count": ocr_needed_count(ocr),
        "hit_at_10": float_metric(retrieval_metrics, "Hit@10"),
        "mrr_at_10": float_metric(retrieval_metrics, "MRR@10"),
        "Hit@10": float_metric(retrieval_metrics, "Hit@10"),
        "MRR@10": float_metric(retrieval_metrics, "MRR@10"),
        "citation_accuracy": float_metric(retrieval_metrics, "citation_accuracy"),
        "citation_location_accuracy": optional_float(
            dict(retrieval.get("metrics") or {}),
            "citation_location_accuracy",
            "citation_accuracy",
            default=float_metric(retrieval_metrics, "citation_accuracy"),
        ),
        "parsing_latency_p95_seconds": parsing_latency_p95_seconds,
        "indexing_latency_p95_seconds": indexing_latency_p95_seconds,
        "fatal_warning_count": fatal_warning_count,
        "hidden_content_leakage_count": hidden_content_leakage_count,
        "embedding_filtered_eval": bool((retrieval.get("metrics") or {}).get("embedding_filtered_eval")),
        "required_embedding_status": (retrieval.get("metrics") or {}).get("required_embedding_status"),
        "required_index_version": (retrieval.get("metrics") or {}).get("required_index_version"),
        "indexing_filtered_hit_count": int_metric(retrieval_metrics, "indexing_filtered_hit_count"),
        "result_empty_count": required_compat_int(
            gate_input_missing,
            dict(retrieval.get("metrics") or {}),
            "result_empty_count",
            "retrieval",
        ),
        "gold_label_invalid_count": required_compat_int(
            gate_input_missing,
            dict(retrieval.get("metrics") or {}),
            "gold_label_invalid_count",
            "retrieval",
        ),
        "candidate_index_mismatch_count": int_metric(retrieval_metrics, "candidate_index_mismatch_count"),
        "embedding_status_mismatch_count": int_metric(retrieval_metrics, "embedding_status_mismatch_count"),
        "required_index_version_mismatch_count": int_metric(
            retrieval_metrics,
            "required_index_version_mismatch_count",
        ),
        "overall_failure_reason_counts": dict((retrieval.get("metrics") or {}).get("overall_failure_reason_counts") or {}),
        "bucket_failure_reason_counts": dict((retrieval.get("metrics") or {}).get("bucket_failure_reason_counts") or {}),
        "bucket_metrics": dict(retrieval.get("bucket_metrics") or {}),
        "retrieval_report_path": str(args.retrieval_report),
        "retrieval_backend": retrieval.get("retrieval_backend"),
        "retrieval_backend_identity": dict(retrieval.get("backend_identity") or {}),
        "promotion_evidence": bool(retrieval.get("promotion_evidence")),
        "evidence_role": retrieval.get("evidence_role") or "diagnostic",
        "candidate_valid_hit_count": optional_int(dict(retrieval.get("metrics") or {}), "candidate_valid_hit_count"),
        "null_index_version_hit_count": optional_int(dict(retrieval.get("metrics") or {}), "null_index_version_hit_count"),
        "wrong_index_version_hit_count": optional_int(dict(retrieval.get("metrics") or {}), "wrong_index_version_hit_count"),
        "unembedded_hit_count": optional_int(dict(retrieval.get("metrics") or {}), "unembedded_hit_count"),
        "candidate_index_version": args.candidate_index_version,
        "baseline_index_version": args.baseline_index_version,
        "pdf_missing_page_metadata_count": int_metric(pdf_metrics, "missing_page_metadata_count"),
        "pdf_inconsistent_location_page_metadata_count": int_metric(
            pdf_metrics,
            "inconsistent_location_page_metadata_count",
        ),
        "source_reports": [
            str(args.xlsx_report),
            str(args.pdf_report),
            str(args.retrieval_report),
            str(args.ocr_report),
        ],
    }
    metrics["gate_input_missing_count"] = len(gate_input_missing)
    metrics["gate_input_missing"] = gate_input_missing
    if ocr_metrics.get("ocr_confidence_avg") is not None:
        metrics["OCR_confidence_avg"] = float_metric(ocr_metrics, "ocr_confidence_avg")

    payload = {
        "run_id": utc_run_id(),
        "status": "COMPLETED",
        "metrics": metrics,
        "source_qualified_metrics": source_qualified,
        "canonical_metrics": canonical_metrics,
        "gate_input_missing_count": len(gate_input_missing),
        "gate_input_missing": gate_input_missing,
        "notes": [
            "Canonical source-qualified metric names are authoritative for C2 readiness.",
            "Legacy aggregate metrics remain only for older gate compatibility.",
            "Derived metrics record their source and are not treated as silent defaults.",
        ],
    }
    write_json(Path(args.output), payload)
    if args.baseline_output:
        baseline = {
            "candidate_snapshot": True,
            "candidate_snapshot_baseline": True,
            "baseline_index_version": args.baseline_index_version,
            "candidate_index_version": args.candidate_index_version,
            "retrieval_backend": retrieval.get("retrieval_backend"),
            "notes": [
                "This file mirrors the current candidate retrieval metrics.",
                "Do not use it as an immutable baseline for promotion decisions.",
            ],
            "metrics": {
                "Hit@10": metrics["Hit@10"],
                "MRR@10": metrics["MRR@10"],
                "hit_at_10": metrics["hit_at_10"],
                "mrr_at_10": metrics["mrr_at_10"],
            },
        }
        write_json(Path(args.baseline_output), baseline)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_source_qualified_metrics(
    *,
    xlsx: dict[str, Any],
    pdf: dict[str, Any],
    ocr: dict[str, Any],
    retrieval: dict[str, Any],
    missing: list[str],
    derived_metric_sources: dict[str, str],
) -> dict[str, dict[str, Any]]:
    raw = {
        "xlsx": dict(xlsx.get("metrics") or {}),
        "pdf": dict(pdf.get("metrics") or {}),
        "ocr": dict(ocr.get("metrics") or {}),
        "retrieval": dict(retrieval.get("metrics") or {}),
    }
    derived: dict[str, dict[str, Callable[[], Any]]] = {
        "xlsx": {
            "hidden_content_leakage_count": lambda: raw["xlsx"].get("hidden_search_unit_leakage_count"),
        },
        "pdf": {
            "unsupported_file_rate": lambda: derive_unsupported_file_rate(pdf),
            "fatal_warning_count": lambda: derive_fatal_warning_count(pdf),
            "hidden_content_leakage_count": lambda: derive_hidden_leakage_count(pdf),
        },
        "ocr": {
            "unsupported_file_rate": lambda: derive_unsupported_file_rate(ocr),
            "fatal_warning_count": lambda: derive_fatal_warning_count(ocr),
            "ocr_confidence_avg": lambda: (ocr.get("db_report") or {}).get("ocr_confidence_avg"),
            "low_trust_ocr_chunk_count": lambda: (ocr.get("db_report") or {}).get("low_trust_ocr_chunk_count"),
            "hidden_content_leakage_count": lambda: derive_hidden_leakage_count(ocr),
            "parsing_latency_p95_seconds": lambda: derive_latency(ocr, "parsing_latency_seconds"),
            "indexing_latency_p95_seconds": lambda: derive_latency(ocr, "indexing_latency_seconds"),
        },
    }
    result: dict[str, dict[str, Any]] = {}
    for source_name, keys in SOURCE_QUALIFIED_REQUIRED.items():
        source_result: dict[str, Any] = {}
        for key in keys:
            canonical_key = f"{source_name}.{key}"
            value = raw[source_name].get(key)
            if value is None or value == "":
                derive = derived.get(source_name, {}).get(key)
                if derive is not None:
                    derived_value = derive()
                    if derived_value is not None and derived_value != "":
                        derived_metric_sources[canonical_key] = f"diagnostic_only:{derived_value}"
            if value is None or value == "":
                missing.append(canonical_key)
                source_result[key] = None
            else:
                source_result[key] = value
        result[source_name] = source_result
    return result


def flatten_source_qualified(source_qualified: dict[str, dict[str, Any]]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for source_name, metrics in source_qualified.items():
        for key, value in metrics.items():
            flattened[f"{source_name}.{key}"] = value
    return flattened


def derive_unsupported_file_rate(report: dict[str, Any]) -> float | None:
    metrics = report.get("metrics")
    if isinstance(metrics, dict) and metrics.get("unsupported_file_rate") is not None:
        return float(metrics["unsupported_file_rate"])
    status = str(report.get("status") or "").upper()
    if status == "SKIPPED" and report.get("warnings"):
        return 1.0
    if status in {"PASSED", "COMPLETED"} or int(report.get("failed") or 0) == 0:
        return 0.0
    return None


def derive_fatal_warning_count(report: dict[str, Any]) -> int | None:
    metrics = report.get("metrics")
    if isinstance(metrics, dict) and metrics.get("fatal_warning_count") is not None:
        return int(metrics["fatal_warning_count"])
    if "errors" in report:
        return len(report.get("errors") or [])
    samples = report.get("samples")
    if isinstance(samples, list):
        return sum(len(item.get("errors") or []) for item in samples if isinstance(item, dict))
    if str(report.get("status") or "").upper() in {"PASSED", "SKIPPED", "COMPLETED"}:
        return 0
    return None


def derive_hidden_leakage_count(report: dict[str, Any]) -> int | None:
    metrics = report.get("metrics")
    if isinstance(metrics, dict):
        if metrics.get("hidden_content_leakage_count") is not None:
            return int(metrics["hidden_content_leakage_count"])
        if metrics.get("hidden_search_unit_leakage_count") is not None:
            return int(metrics["hidden_search_unit_leakage_count"])
    if str(report.get("status") or "").upper() in {"PASSED", "SKIPPED", "COMPLETED"}:
        return 0
    if int(report.get("failed") or 0) == 0 and report.get("samples") is not None:
        return 0
    return None


def derive_latency(report: dict[str, Any], key: str) -> float | None:
    metrics = report.get("metrics")
    canonical_key = key.replace("_seconds", "_p95_seconds")
    if isinstance(metrics, dict) and metrics.get(canonical_key) is not None:
        return float(metrics[canonical_key])
    if report.get(key) is not None:
        return float(report[key])
    if str(report.get("status") or "").upper() == "SKIPPED":
        return 0.0
    return None


def ocr_needed_count(report: dict[str, Any]) -> int:
    db_report = report.get("db_report") or {}
    if report.get("status") == "PASSED":
        return int(db_report.get("ocr_search_unit_count") or 0)
    return 0


def required_compat_int(missing: list[str], metrics: dict[str, Any], key: str, source_name: str) -> int:
    value = metrics.get(key)
    if value is None or value == "":
        missing.append(f"{source_name}.{key}")
        return 0
    return int(value)


def float_metric(metrics: dict[str, Any], key: str) -> float:
    value = metrics.get(key)
    if value is None or value == "":
        return 0.0
    return float(value)


def int_metric(metrics: dict[str, Any], key: str) -> int:
    value = metrics.get(key)
    if value is None or value == "":
        return 0
    return int(value)


def optional_float(metrics: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = metrics.get(key)
        if value is not None and value != "":
            return float(value)
    return default


def optional_int(metrics: dict[str, Any], key: str, default: int = 0) -> int:
    value = metrics.get(key)
    if value is None or value == "":
        return default
    return int(value)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx-report", default=str(DEFAULT_XLSX_REPORT))
    parser.add_argument("--pdf-report", default=str(DEFAULT_PDF_REPORT))
    parser.add_argument("--retrieval-report", default=str(DEFAULT_RETRIEVAL_REPORT))
    parser.add_argument("--ocr-report", default=str(DEFAULT_OCR_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--baseline-output")
    parser.add_argument("--candidate-index-version", default="rag-ingestion-v2-candidate")
    parser.add_argument("--baseline-index-version", default="rag-ingestion-v2-baseline")
    return parser.parse_args(argv)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


if __name__ == "__main__":
    sys.exit(main())
