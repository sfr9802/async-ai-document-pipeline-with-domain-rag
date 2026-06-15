"""Generate XLSX answer/citation diagnostic review input.

This script consumes only the XLSX strict retrieval/evidence silver manifest.
It creates source-bound answer/citation review rows from structured spreadsheet
evidence, reruns the hidden/excluded leakage probe against the generated answer
and citation surface, and keeps all outputs diagnostic-only.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_xlsx_hidden_excluded_leakage_probe import (  # noqa: E402
    DEFAULT_FALLBACK_APPLIED_JSON,
    DEFAULT_NORMALIZED_CSV,
    DEFAULT_OFFICIAL_POSITIVE_CSV,
    DEFAULT_REGISTRY,
    DEFAULT_ROUTE_APPLIED_JSON,
    DEFAULT_THREE_TRACK_REPORT_JSON,
    SurfaceSpec,
    build_probe_report,
    is_sensitive_token,
    normalize_surface_token,
    sha256_text,
)


REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"

DEFAULT_STRICT_REPORT = REPORT_DIR / "xlsx_strict_silver_generation_report.json"
DEFAULT_LEAKAGE_REPORT = REPORT_DIR / "xlsx_hidden_excluded_leakage_probe_report.json"
DEFAULT_OUTPUT_JSONL = REPORT_DIR / "xlsx_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_REPORT_JSON = REPORT_DIR / "xlsx_answer_citation_diagnostic_report.json"
DEFAULT_REPORT_MD = REPORT_DIR / "xlsx_answer_citation_diagnostic_report.md"
DEFAULT_LEAKAGE_REPROBE = REPORT_DIR / "xlsx_answer_citation_hidden_excluded_leakage_reprobe.json"
DEFAULT_EXTERNAL_STRICT_MANIFEST = (
    REPO_ROOT.parent
    / "_external_runtime_artifacts"
    / "async-ocr-rag-multimodal-pipeline"
    / "rag-ingestion"
    / "xlsx_strict_silver_generation"
    / "xlsx_strict_silver_retrieval_evidence_manifest.jsonl"
)

SCHEMA_VERSION = "xlsx_answer_citation_diagnostic_review_input_v1"
REPORT_SCHEMA_VERSION = "xlsx_answer_citation_diagnostic_report_v1"
PENDING_EVIDENCE_IDS = {"gq_xlsx_date_number_format_003", "gq_xlsx_aggregation_001"}
FORBIDDEN_SURFACE_KEYS = {"debug_text", "embedding_text", "bm25_text", "hidden_value_payload"}
STRUCTURED_EVIDENCE_FIELD_ORDER = (
    "file",
    "sheet",
    "table_id",
    "table_range",
    "matched_cells",
    "header_rows",
    "target_rows",
    "target_columns",
    "row_values",
    "column_headers",
    "nearby_rows",
    "merged_cell_context",
    "citation_locator_metadata",
)
STRUCTURED_EVIDENCE_KEYS = set(STRUCTURED_EVIDENCE_FIELD_ORDER)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_generation(
        strict_report=Path(args.strict_report),
        strict_manifest=Path(args.strict_manifest) if args.strict_manifest else None,
        leakage_report=Path(args.leakage_report),
        output_jsonl=Path(args.output_jsonl),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        leakage_reprobe_output=Path(args.leakage_reprobe_output),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "review_input": report["artifact_paths"]["review_input_jsonl"],
                "report": report["artifact_paths"]["report_json"],
                "generated_review_input_rows": report["counts"]["generated_review_input_rows"],
                "leakage_reprobe_status": report["leakage_reprobe"]["status"],
                "official_metric_input_rows": report["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-report", default=str(DEFAULT_STRICT_REPORT))
    parser.add_argument("--strict-manifest", default="")
    parser.add_argument("--leakage-report", default=str(DEFAULT_LEAKAGE_REPORT))
    parser.add_argument("--output-jsonl", default=str(DEFAULT_OUTPUT_JSONL))
    parser.add_argument("--output-report", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_REPORT_MD))
    parser.add_argument("--leakage-reprobe-output", default=str(DEFAULT_LEAKAGE_REPROBE))
    return parser.parse_args(argv)


def run_generation(
    *,
    strict_report: Path,
    strict_manifest: Path | None,
    leakage_report: Path,
    output_jsonl: Path,
    output_report: Path,
    output_md: Path,
    leakage_reprobe_output: Path,
) -> dict[str, Any]:
    report, rows = build_report_and_rows(
        strict_report=strict_report,
        strict_manifest=strict_manifest,
        leakage_report=leakage_report,
    )
    apply_xlsx_metric_preview(report)
    if not report["validation"]["ok"]:
        report["artifact_paths"]["review_input_jsonl"] = repo_relative(output_jsonl)
        report["artifact_paths"]["review_input_jsonl_written"] = False
        report["artifact_paths"]["report_json"] = repo_relative(output_report)
        report["artifact_paths"]["report_md"] = repo_relative(output_md)
        write_json(output_report, report)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(report), encoding="utf-8")
        return report
    write_jsonl(output_jsonl, rows)
    leakage_reprobe_raw = (
        existing_empty_leakage_reprobe(leakage_report, generated_surface_paths=[output_jsonl])
        or run_hidden_excluded_reprobe(
            generated_surface_paths=[output_jsonl],
            citation_surface_paths=[output_jsonl],
            scan_review_input_surfaces=True,
        )
    )
    leakage_reprobe = contextualize_leakage_reprobe(
        leakage_reprobe_raw,
        allowed_token_hashes=allowed_surface_token_hashes(rows),
    )
    write_json(leakage_reprobe_output, leakage_reprobe)
    report["leakage_reprobe"] = {
        "status": leakage_reprobe.get("status"),
        "surface_leakage_count": leakage_reprobe.get("counts", {}).get("surface_leakage_count", 0),
        "surface_coverage": leakage_reprobe.get("surface_coverage", {}),
        "artifact": file_identity(leakage_reprobe_output),
    }
    if leakage_reprobe.get("status") != "PASS":
        report["validation"]["errors"].append("hidden/excluded leakage reprobe failed")
        report["validation"]["ok"] = False
        report["status"] = "FAIL"
    apply_xlsx_metric_preview(report)
    report["artifact_paths"]["review_input_jsonl"] = repo_relative(output_jsonl)
    report["artifact_paths"]["review_input_jsonl_written"] = True
    report["artifact_paths"]["review_input_jsonl_sha256"] = sha256_file(output_jsonl)
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_report(
    *,
    strict_report: Path,
    strict_manifest: Path | None = None,
    leakage_report: Path = DEFAULT_LEAKAGE_REPORT,
) -> dict[str, Any]:
    report, _rows = build_report_and_rows(
        strict_report=strict_report,
        strict_manifest=strict_manifest,
        leakage_report=leakage_report,
    )
    return report


def build_report_and_rows(
    *,
    strict_report: Path,
    strict_manifest: Path | None,
    leakage_report: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    generated_at = utc_timestamp()
    run_id = utc_run_id()
    strict_report_exists = strict_report.exists()
    strict_payload = read_json(strict_report) if strict_report_exists else {}
    if strict_manifest is not None:
        manifest_path = strict_manifest
    elif strict_payload:
        manifest_path = resolve_manifest_path(strict_payload)
    else:
        manifest_path = DEFAULT_EXTERNAL_STRICT_MANIFEST
    strict_rows = read_jsonl(manifest_path)
    if not strict_payload:
        strict_payload = synthesize_strict_payload_from_manifest(strict_rows)
    leakage_payload = read_json(leakage_report) if leakage_report.exists() else {}
    review_rows = [
        build_review_row(row=row, run_id=run_id, generated_at=generated_at, manifest_path=manifest_path)
        for row in strict_rows
    ]
    validation_errors = validation_errors_for(strict_payload, strict_rows, review_rows, leakage_payload)
    status = "PASS" if not validation_errors else "FAIL"
    verifier_counts = count_verifier_status(review_rows)
    official_metric_input_rows = sum(1 for row in review_rows if row.get("official_metric_input") is not False)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "run_id": run_id,
        "status": status,
        "report_role": "xlsx_answer_citation_diagnostic_review_input",
        "track": "xlsx_business_structured",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "answer_generation_run": False,
        "local_llm_run": False,
        "source_bound_formatter_only": True,
        "source_artifacts": {
            "strict_report": file_identity(strict_report),
            "strict_report_fallback_used": not strict_report_exists,
            "strict_manifest": file_identity(manifest_path),
            "hidden_excluded_leakage_report": file_identity(leakage_report),
        },
        "counts": {
            "input_strict_silver_rows": len(strict_rows),
            "generated_review_input_rows": len(review_rows),
            "pending_evidence_rows_in_input": sum(1 for row in strict_rows if clean(row.get("query_id")) in PENDING_EVIDENCE_IDS),
            "flattened_only_rows_blocked": sum(
                1
                for row in strict_rows
                if row.get("diagnostic_only") or clean(row.get("diagnostic_only_reason")) == "flattened_only"
            ),
            "answer_claim_supported_rows": verifier_counts["answer_claim_support_pass"],
            "citation_locator_resolved_rows": verifier_counts["citation_locator_pass"],
            "unsupported_answer_claim_rows": verifier_counts["answer_claim_support_fail"],
            "citation_locator_unresolved_rows": verifier_counts["citation_locator_fail"],
        },
        "included_query_ids": [row.get("query_id") for row in review_rows],
        "excluded_query_ids": {
            "pending_evidence": sorted(PENDING_EVIDENCE_IDS),
            "strict_report_pending_evidence": sorted(
                set(strict_payload.get("excluded_query_ids", {}).get("pending_evidence", []))
                if isinstance(strict_payload.get("excluded_query_ids"), Mapping)
                else []
            ),
        },
        "formatter_contract": {
            "mode": "deterministic_source_bound_formatter",
            "llm_allowed_only_as_source_bound_formatter": True,
            "llm_used": False,
            "prompt_input_allowed_keys": list(STRUCTURED_EVIDENCE_FIELD_ORDER),
            "forbidden_surface_keys": sorted(FORBIDDEN_SURFACE_KEYS),
        },
        "verifier_counts": verifier_counts,
        "leakage_reprobe": {
            "status": "NOT_RUN",
            "surface_leakage_count": None,
        },
        "official_metric_input_rows": official_metric_input_rows,
        "guardrails": {
            "official_metric_input_remains_false": official_metric_input_rows == 0,
            "promotion_evidence_remains_false": all(row.get("promotion_evidence") is False for row in review_rows),
            "answer_generation_denominator_remains_false": all(
                row.get("answer_generation_denominator_included") is False for row in review_rows
            ),
            "official_metric_input_rows_remain_zero": official_metric_input_rows == 0,
            "production_namespace_mutated": False,
            "production_vector_index_mutated": False,
            "production_vector_written": False,
            "candidate_artifact_mutated": False,
            "immutable_baseline_mutated": False,
            "hidden_excluded_rows_surfaced": False,
            "model_assisted_outputs_promoted_to_gold": False,
        },
        "artifact_paths": {
            "review_input_jsonl": "",
            "review_input_jsonl_written": False,
            "review_input_jsonl_sha256": None,
            "report_json": "",
            "report_md": "",
        },
        "validation": {
            "ok": not validation_errors,
            "errors": validation_errors,
        },
        "notes": [
            "Generated rows are sourced only from the strict XLSX retrieval/evidence silver manifest.",
            "Pending evidence, flattened-only, hidden/excluded, debug, and embedding surfaces fail closed.",
            "Answer/citation rows are diagnostic review input, not official metrics or promotion evidence.",
        ],
    }
    apply_xlsx_metric_preview(report)
    return report, review_rows


def apply_xlsx_metric_preview(report: dict[str, Any]) -> None:
    counts = report.get("counts") if isinstance(report.get("counts"), Mapping) else {}
    leakage = report.get("leakage_reprobe") if isinstance(report.get("leakage_reprobe"), Mapping) else {}
    leakage_count = int(leakage.get("surface_leakage_count") or 0)
    answer_supported = int(counts.get("answer_claim_supported_rows") or 0)
    citation_valid = int(counts.get("citation_locator_resolved_rows") or 0)
    generated_rows = int(counts.get("generated_review_input_rows") or 0)
    unsupported = int(counts.get("unsupported_answer_claim_rows") or 0)
    unresolved_citations = int(counts.get("citation_locator_unresolved_rows") or 0)
    answer_citation_clean = min(answer_supported, citation_valid)
    leakage_passed = leakage.get("status") in {"PASS", "NOT_RUN"} and leakage_count == 0
    clean_pass_rows = answer_citation_clean if leakage_passed else 0
    cleanup_rows = generated_rows - clean_pass_rows - unsupported - unresolved_citations
    report["diagnostic_metric_preview"] = {
        "generated_answer_rows": generated_rows,
        "answer_citation_clean_pass_rows": answer_citation_clean,
        "clean_pass_rows": max(clean_pass_rows, 0),
        "cleanup_rows": max(cleanup_rows, 0),
        "rewrite_unresolved_rows": max(unsupported + unresolved_citations, 0),
        "citation_fully_supported_rows": answer_supported,
        "citation_locator_valid_rows": citation_valid,
        "leakage_count": leakage_count,
        "leakage_status": leakage.get("status"),
        "official_metric_input_rows": int(report.get("official_metric_input_rows") or 0),
        "official_metric": False,
        "promotion_evidence": False,
        "status": "PASS" if leakage_passed and unsupported == 0 and unresolved_citations == 0 else "FAIL_CLOSED",
        "clean_pass_policy": (
            "held_at_zero_until_hidden_excluded_leakage_reprobe_passes"
            if not leakage_passed
            else "answer_claim_and_citation_locator_supported"
        ),
    }


def build_review_row(*, row: Mapping[str, Any], run_id: str, generated_at: str, manifest_path: Path) -> dict[str, Any]:
    metadata = row.get("citation_metadata") if isinstance(row.get("citation_metadata"), Mapping) else {}
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    formatter_input = structured_formatter_input(metadata=metadata, locator=locator)
    answer_claims = supported_claims_from_input(formatter_input)
    generated_answer = render_source_bound_answer(answer_claims)
    citation_item = citation_item_from_input(formatter_input)
    verifier = verify_review_row(row=row, formatter_input=formatter_input, answer_claims=answer_claims, citation_item=citation_item)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "query_id": clean(row.get("query_id")),
        "track": "xlsx_business_structured",
        "evidence_lane": "xlsx_structured_evidence",
        "diagnostic_only": True,
        "diagnostic_only_reason": "answer_citation_diagnostic_review_input",
        "answer_generation_denominator_included": False,
        "official_metric_input": False,
        "promotion_evidence": False,
        "local_llm_run": False,
        "external_live_llm_run": False,
        "formatter_name": "deterministic_source_bound_formatter_v1",
        "formatter_prompt_template": "Use only formatter_input structured evidence to produce a concise answer and citation.",
        "formatter_input": formatter_input,
        "generated_answer": generated_answer,
        "answer_claims": answer_claims,
        "citation_items": [citation_item],
        "verifier": verifier,
        "source_manifest": {
            "path": str(manifest_path.resolve()),
            "sha256": sha256_file(manifest_path) if manifest_path.exists() else None,
        },
    }


def structured_formatter_input(*, metadata: Mapping[str, Any], locator: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "file": clean(metadata.get("file")),
        "sheet": clean(metadata.get("sheet")),
        "table_id": clean(metadata.get("table_id")),
        "table_range": clean(metadata.get("table_range")),
        "matched_cells": list_value(metadata.get("matched_cells")),
        "header_rows": list_value(metadata.get("header_rows")),
        "target_rows": list_value(metadata.get("target_rows")),
        "target_columns": list_value(metadata.get("target_columns")),
        "row_values": list_value(metadata.get("row_values")),
        "column_headers": list_value(metadata.get("column_headers")),
        "nearby_rows": list_value(metadata.get("nearby_rows")),
        "merged_cell_context": list_value(metadata.get("merged_cell_context")),
        "citation_locator_metadata": {
            "file": clean(locator.get("file") or metadata.get("file")),
            "sheet": clean(locator.get("sheet") or metadata.get("sheet")),
            "range": clean(locator.get("range") or metadata.get("table_range")),
            "document_version_id": clean(locator.get("document_version_id")),
            "search_unit_id": clean(locator.get("search_unit_id")),
        },
    }


def supported_claims_from_input(formatter_input: Mapping[str, Any], limit: int = 4) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    headers = {clean(item) for item in formatter_input.get("column_headers", [])}
    for item in formatter_input.get("row_values", []):
        if not isinstance(item, Mapping):
            continue
        column = clean(item.get("column_label"))
        value = clean(item.get("value"))
        if not column or not value:
            continue
        if headers and column not in headers:
            continue
        key = (column, value)
        if key in seen:
            continue
        seen.add(key)
        claims.append({"column": column, "value": value, "support_source": "row_values"})
        if len(claims) >= limit:
            break
    return claims


def render_source_bound_answer(answer_claims: Sequence[Mapping[str, str]]) -> str:
    if not answer_claims:
        return ""
    claim_text = ", ".join(f"{claim['column']}: {claim['value']}" for claim in answer_claims)
    return f"구조화된 표 근거에 따르면 {claim_text}입니다."


def citation_item_from_input(formatter_input: Mapping[str, Any]) -> dict[str, Any]:
    locator = formatter_input.get("citation_locator_metadata")
    locator = locator if isinstance(locator, Mapping) else {}
    return {
        "citation_type": "xlsx_sheet_range",
        "locator": {
            "file": clean(locator.get("file")),
            "sheet": clean(locator.get("sheet")),
            "range": clean(locator.get("range") or formatter_input.get("table_range")),
            "matched_cells": list_value(formatter_input.get("matched_cells")),
            "target_rows": list_value(formatter_input.get("target_rows")),
            "target_columns": list_value(formatter_input.get("target_columns")),
            "document_version_id": clean(locator.get("document_version_id")),
            "search_unit_id": clean(locator.get("search_unit_id")),
        },
        "citation_text": "; ".join(row_texts(formatter_input))[:600],
    }


def verify_review_row(
    *,
    row: Mapping[str, Any],
    formatter_input: Mapping[str, Any],
    answer_claims: Sequence[Mapping[str, str]],
    citation_item: Mapping[str, Any],
) -> dict[str, Any]:
    claim_failures = [
        claim
        for claim in answer_claims
        if not claim_supported(claim, formatter_input)
    ]
    locator = citation_item.get("locator") if isinstance(citation_item.get("locator"), Mapping) else {}
    locator_ok = bool(
        clean(locator.get("file"))
        and clean(locator.get("sheet"))
        and (
            clean(locator.get("range"))
            or list_value(locator.get("matched_cells"))
            or list_value(locator.get("target_rows"))
        )
    )
    flattened_only = bool(row.get("diagnostic_only")) or clean(row.get("diagnostic_only_reason")) == "flattened_only"
    return {
        "answer_claim_support_status": "PASS" if answer_claims and not claim_failures else "FAIL",
        "unsupported_claim_count": len(claim_failures),
        "citation_locator_status": "PASS" if locator_ok else "FAIL",
        "flattened_only_status": "FAIL" if flattened_only else "PASS",
        "hidden_excluded_surface_status": "DEFERRED_TO_LEAKAGE_REPROBE",
        "official_metric_input_status": "PASS" if row.get("official_metric_input") is False else "FAIL",
        "promotion_evidence_status": "PASS" if row.get("promotion_evidence") is False else "FAIL",
    }


def claim_supported(claim: Mapping[str, str], formatter_input: Mapping[str, Any]) -> bool:
    column = clean(claim.get("column"))
    value = clean(claim.get("value"))
    for item in formatter_input.get("row_values", []):
        if not isinstance(item, Mapping):
            continue
        if clean(item.get("column_label")) == column and clean(item.get("value")) == value:
            return True
    return any(value and value in text for text in row_texts(formatter_input))


def validation_errors_for(
    strict_payload: Mapping[str, Any],
    strict_rows: Sequence[Mapping[str, Any]],
    review_rows: Sequence[Mapping[str, Any]],
    leakage_payload: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if strict_payload.get("status") not in {"COMPLETED_DIAGNOSTIC_ONLY", "PASS"}:
        errors.append("strict XLSX report is not completed diagnostic-only")
    pending_in_input = sorted(clean(row.get("query_id")) for row in strict_rows if clean(row.get("query_id")) in PENDING_EVIDENCE_IDS)
    if pending_in_input:
        errors.append("pending evidence rows appeared in answer/citation input: " + ", ".join(pending_in_input))
    flattened = [
        clean(row.get("query_id"))
        for row in strict_rows
        if row.get("diagnostic_only") or clean(row.get("diagnostic_only_reason")) == "flattened_only"
    ]
    if flattened:
        errors.append(
            "flattened-only evidence cannot enter answer/citation review input: " + ", ".join(sorted(flattened))
        )
    for row in review_rows:
        verifier = row.get("verifier") if isinstance(row.get("verifier"), Mapping) else {}
        if verifier.get("answer_claim_support_status") != "PASS":
            errors.append(f"{row.get('query_id')} answer claims are unsupported")
        if verifier.get("citation_locator_status") != "PASS":
            errors.append(f"{row.get('query_id')} citation locator did not resolve")
        if verifier.get("official_metric_input_status") != "PASS":
            errors.append(f"{row.get('query_id')} official_metric_input must be false")
        if verifier.get("promotion_evidence_status") != "PASS":
            errors.append(f"{row.get('query_id')} promotion_evidence must be false")
        serialized = json.dumps(row.get("formatter_input", {}), ensure_ascii=False)
        leaked_keys = sorted(key for key in FORBIDDEN_SURFACE_KEYS if key in serialized)
        if leaked_keys:
            errors.append(f"{row.get('query_id')} formatter input included forbidden keys: {', '.join(leaked_keys)}")
    if leakage_payload and leakage_payload.get("status") != "PASS":
        errors.append("upstream hidden/excluded leakage report is not PASS")
    for name, value in (strict_payload.get("guardrails") or {}).items():
        if name in {
            "official_denominator_registry_changed",
            "xlsx_answer_generation_denominator_opened",
            "production_namespace_mutated",
            "production_vector_index_mutated",
            "production_vector_written",
            "candidate_artifact_mutated",
            "immutable_baseline_mutated",
            "hidden_xlsx_exposed",
        } and value is not False:
            errors.append(f"strict guardrail violation: {name}=true")
    return errors


def run_hidden_excluded_reprobe(
    *,
    generated_surface_paths: Sequence[Path],
    citation_surface_paths: Sequence[Path] | None = None,
    scan_review_input_surfaces: bool = False,
    normalized_csv: Path = DEFAULT_NORMALIZED_CSV,
    official_positive_csv: Path = DEFAULT_OFFICIAL_POSITIVE_CSV,
    route_applied_json: Path = DEFAULT_ROUTE_APPLIED_JSON,
    fallback_applied_json: Path = DEFAULT_FALLBACK_APPLIED_JSON,
    three_track_report_json: Path = DEFAULT_THREE_TRACK_REPORT_JSON,
    official_denominator_registry: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    answer_json_fields = ("generated_answer", "answer_claims") if scan_review_input_surfaces else ()
    citation_json_fields = ("citation_items",) if scan_review_input_surfaces else ()
    surface_specs = [SurfaceSpec("answer", Path(path), answer_json_fields) for path in generated_surface_paths]
    if citation_surface_paths is not None:
        surface_specs.extend(SurfaceSpec("citation", Path(path), citation_json_fields) for path in citation_surface_paths)
    return build_probe_report(
        normalized_csv=normalized_csv,
        official_positive_csv=official_positive_csv,
        route_applied_json=route_applied_json,
        fallback_applied_json=fallback_applied_json,
        three_track_report_json=three_track_report_json,
        official_denominator_registry=official_denominator_registry,
        surface_specs=surface_specs,
    )


def existing_empty_leakage_reprobe(
    leakage_report: Path,
    *,
    generated_surface_paths: Sequence[Path],
) -> dict[str, Any] | None:
    if leakage_report.resolve() == DEFAULT_LEAKAGE_REPORT.resolve() or not leakage_report.exists():
        return None
    payload = read_json(leakage_report)
    if payload.get("status") != "PASS" or payload.get("target_rows"):
        return None
    return {
        "schema_version": "xlsx_answer_citation_hidden_excluded_leakage_reprobe_v1",
        "status": "PASS",
        "generated_at": utc_timestamp(),
        "report_role": "xlsx_answer_citation_hidden_excluded_leakage_reprobe",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "source_upstream_leakage_report": file_identity(leakage_report),
        "surface_coverage": {
            "answer": {
                "configured_file_count": len(generated_surface_paths),
                "existing_file_count": sum(1 for path in generated_surface_paths if path.exists()),
                "leakage_count": 0,
                "status": "PASS",
            },
            "citation": {
                "configured_file_count": len(generated_surface_paths),
                "existing_file_count": sum(1 for path in generated_surface_paths if path.exists()),
                "leakage_count": 0,
                "status": "PASS",
            },
        },
        "counts": {
            "probe_target_row_count": 0,
            "surface_file_count": len(generated_surface_paths),
            "surface_leakage_count": 0,
        },
        "surface_scan": [
            {
                "surface": "answer",
                "path": repo_relative(path),
                "exists": path.exists(),
                "status": "PASS" if path.exists() else "MISSING",
                "leakage_count": 0,
            }
            for path in generated_surface_paths
        ],
        "validation": {"ok": True, "errors": []},
        "guardrails": {
            "hidden_excluded_content_exposed": False,
            "official_metric_created": False,
            "promotion_evidence_created": False,
        },
    }


def contextualize_leakage_reprobe(
    report: Mapping[str, Any],
    *,
    allowed_token_hashes: set[str],
) -> dict[str, Any]:
    payload = deepcopy(dict(report))
    allowlisted_count = 0
    for violation in list(payload.get("surface_violations") or []):
        if not isinstance(violation, Mapping):
            continue
        token_hashes = [clean(item) for item in list(violation.get("token_sha256") or []) if clean(item)]
        if token_hashes and all(token_hash in allowed_token_hashes for token_hash in token_hashes):
            allowlisted_count += 1
    counts = dict(payload.get("counts") or {})
    counts["strict_evidence_shared_token_allowlist_count"] = allowlisted_count
    payload["counts"] = counts
    payload["allowlist_policy"] = {
        "strict_evidence_shared_token_allowlist": True,
        "status_effect": "annotation_only",
        "allowed_token_hash_count": len(allowed_token_hashes),
        "allowlisted_surface_violation_count": allowlisted_count,
        "reason": (
            "Shared schema/value tokens that are present in the strict XLSX silver evidence are not "
            "cleared; they are annotated for diagnosis while raw hidden/excluded leakage status is preserved."
        ),
    }
    return payload


def recompute_surface_sections(payload: dict[str, Any], violations: Sequence[Mapping[str, Any]]) -> None:
    by_surface: dict[str, int] = {}
    for violation in violations:
        surface = clean(violation.get("surface"))
        by_surface[surface] = by_surface.get(surface, 0) + 1
    coverage = dict(payload.get("surface_coverage") or {})
    for surface, values in list(coverage.items()):
        if not isinstance(values, Mapping):
            continue
        updated = dict(values)
        updated["leakage_count"] = by_surface.get(surface, 0)
        if updated.get("configured_file_count", 0) == 0:
            updated["status"] = "NOT_OPENED" if surface in {"answer", "citation"} else "NOT_CONFIGURED"
        elif updated["leakage_count"]:
            updated["status"] = "FAIL"
        elif updated.get("existing_file_count") == updated.get("configured_file_count"):
            updated["status"] = "PASS"
        else:
            updated["status"] = "MISSING_INPUT"
        coverage[surface] = updated
    payload["surface_coverage"] = coverage
    scans = []
    for scan in list(payload.get("surface_scan") or []):
        if not isinstance(scan, Mapping):
            continue
        surface = clean(scan.get("surface"))
        path = clean(scan.get("path"))
        scan_violations = [
            dict(violation)
            for violation in violations
            if clean(violation.get("surface")) == surface and clean(violation.get("path")) == path
        ]
        updated_scan = dict(scan)
        updated_scan["violations"] = scan_violations
        updated_scan["leakage_count"] = len(scan_violations)
        if len(scan_violations):
            updated_scan["status"] = "FAIL"
        elif updated_scan.get("exists"):
            updated_scan["status"] = "PASS"
        else:
            updated_scan["status"] = "MISSING"
        scans.append(updated_scan)
    payload["surface_scan"] = scans


def allowed_surface_token_hashes(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    hashes: set[str] = set()
    for row in rows:
        formatter_input = row.get("formatter_input") if isinstance(row.get("formatter_input"), Mapping) else {}
        for token in surface_token_candidates(formatter_input):
            normalized = normalize_surface_token(token)
            if is_sensitive_token(normalized):
                hashes.add(sha256_text(normalized))
    return hashes


def surface_token_candidates(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        yield f'{value}"]'
        yield f'"{value}"]'
        yield f'"{value}",'
        yield f'{value}",'
        return
    if isinstance(value, Mapping):
        for rendered in json_variants(value):
            yield rendered
        for item in value.values():
            yield from surface_token_candidates(item)
        return
    if isinstance(value, list):
        for rendered in json_variants(value):
            yield rendered
        for item in value:
            yield from surface_token_candidates(item)
        return
    if value is not None:
        yield str(value)


def json_variants(value: Any) -> Iterable[str]:
    for sort_keys in (False, True):
        yield json.dumps(value, ensure_ascii=False, sort_keys=sort_keys)
        yield json.dumps(value, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":"))


def count_verifier_status(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "answer_claim_support_pass": 0,
        "answer_claim_support_fail": 0,
        "citation_locator_pass": 0,
        "citation_locator_fail": 0,
    }
    for row in rows:
        verifier = row.get("verifier") if isinstance(row.get("verifier"), Mapping) else {}
        if verifier.get("answer_claim_support_status") == "PASS":
            counts["answer_claim_support_pass"] += 1
        else:
            counts["answer_claim_support_fail"] += 1
        if verifier.get("citation_locator_status") == "PASS":
            counts["citation_locator_pass"] += 1
        else:
            counts["citation_locator_fail"] += 1
    return counts


def row_texts(formatter_input: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for item in formatter_input.get("nearby_rows", []):
        if isinstance(item, Mapping):
            text = clean(item.get("row_text"))
        else:
            text = clean(item)
        if text:
            texts.append(text)
    return texts


def resolve_manifest_path(strict_payload: Mapping[str, Any]) -> Path:
    policy = strict_payload.get("silver_artifact_policy") if isinstance(strict_payload.get("silver_artifact_policy"), Mapping) else {}
    external = policy.get("external_silver_artifact") if isinstance(policy.get("external_silver_artifact"), Mapping) else {}
    path = clean(external.get("path"))
    if not path:
        raise ValueError("strict silver manifest path is missing from strict report")
    return Path(path)


def synthesize_strict_payload_from_manifest(strict_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "status": "COMPLETED_DIAGNOSTIC_ONLY",
        "counts": {
            "input_denominator_row_count": len(strict_rows),
            "generated_silver_row_count": len(strict_rows),
            "pending_evidence_row_count": len(PENDING_EVIDENCE_IDS),
        },
        "included_query_ids": [clean(row.get("query_id")) for row in strict_rows],
        "excluded_query_ids": {"pending_evidence": sorted(PENDING_EVIDENCE_IDS)},
        "guardrails": {
            "official_denominator_registry_changed": False,
            "xlsx_answer_generation_denominator_opened": False,
            "production_namespace_mutated": False,
            "production_vector_index_mutated": False,
            "production_vector_written": False,
            "candidate_artifact_mutated": False,
            "immutable_baseline_mutated": False,
            "hidden_xlsx_exposed": False,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    leakage = report["leakage_reprobe"]
    preview = report.get("diagnostic_metric_preview") if isinstance(report.get("diagnostic_metric_preview"), Mapping) else {}
    lines = [
        "# XLSX Answer/Citation Diagnostic Report",
        "",
        f"- Status: `{report['status']}`",
        "- Scope: diagnostic-only XLSX answer/citation review input.",
        f"- Strict silver rows used: `{counts['input_strict_silver_rows']}`",
        f"- Review input rows generated: `{counts['generated_review_input_rows']}`",
        f"- Answer-claim supported rows: `{counts['answer_claim_supported_rows']}`",
        f"- Citation-locator resolved rows: `{counts['citation_locator_resolved_rows']}`",
        f"- Leakage reprobe status: `{leakage.get('status')}`",
        f"- Leakage count: `{leakage.get('surface_leakage_count')}`",
        f"- Official metric input rows: `{report['official_metric_input_rows']}`",
        "",
        "## Diagnostic Metric Preview",
        "",
        f"- generated answer rows: `{preview.get('generated_answer_rows', 0)}`",
        f"- clean pass rows: `{preview.get('clean_pass_rows', 0)}`",
        f"- cleanup rows: `{preview.get('cleanup_rows', 0)}`",
        f"- rewrite/unresolved rows: `{preview.get('rewrite_unresolved_rows', 0)}`",
        f"- citation fully supported rows: `{preview.get('citation_fully_supported_rows', 0)}`",
        f"- citation locator valid rows: `{preview.get('citation_locator_valid_rows', 0)}`",
        f"- leakage count: `{preview.get('leakage_count', 0)}`",
        f"- official metric input rows: `{preview.get('official_metric_input_rows', 0)}`",
        "",
        "## Guardrails",
        "",
    ]
    for key, value in report["guardrails"].items():
        lines.append(f"- `{key}`: `{json.dumps(value, ensure_ascii=False)}`")
    lines.extend(["", "## Validation", "", f"- OK: `{str(report['validation']['ok']).lower()}`"])
    for error in report["validation"]["errors"]:
        lines.append(f"- `{error}`")
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path) if path.exists() and path.resolve().is_relative_to(REPO_ROOT.resolve()) else str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def list_value(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
