"""Probe XLSX normalized excluded/hidden-negative leakage surfaces.

This diagnostic-only probe is intentionally read-only. It does not run
retrieval, generate answers, write vectors, update the official denominator
registry, mutate candidate artifacts, or promote any row. It checks whether
normalized XLSX excluded rows or hidden/excluded guard rows have leaked into
configured query, candidate, answer, citation, debug, or public surfaces.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"

DEFAULT_NORMALIZED_CSV = EVAL_QUERY_DIR / "gold_queries_xlsx_human_review_normalized_v0.csv"
DEFAULT_OFFICIAL_POSITIVE_CSV = (
    EVAL_QUERY_DIR / "gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv"
)
DEFAULT_ROUTE_APPLIED_JSON = REVIEW_DIR / "route_gold_label_review_applied_v1.json"
DEFAULT_FALLBACK_APPLIED_JSON = REVIEW_DIR / "fallback_outcome_label_review_applied_v1.json"
DEFAULT_THREE_TRACK_REPORT_JSON = REPORT_DIR / "three_track_orchestration_report.json"
DEFAULT_THREE_TRACK_REPORT_MD = REPORT_DIR / "three_track_orchestration_report.md"
DEFAULT_REGISTRY = EVAL_QUERY_DIR / "official_denominator_registry.json"
DEFAULT_JSON_OUTPUT = REPORT_DIR / "xlsx_hidden_excluded_leakage_probe_report.json"
DEFAULT_MD_OUTPUT = REPORT_DIR / "xlsx_hidden_excluded_leakage_probe_report.md"

SCHEMA_VERSION = "xlsx_hidden_excluded_leakage_probe_v1"
HIDDEN_EXCLUDED_FLAG = "hidden_negative_or_excluded_row_guard"
EXCLUDED_POLICY = "EXCLUDED"
MIN_TOKEN_LENGTH = 8

SENSITIVE_FIELDS = [
    "query",
    "safe_query_text",
    "evidence_summary",
    "evidence_headers",
    "evidence_row_values",
    "evidence_cell_values",
    "deterministic_compiled_answer",
    "expected_answer_text_existing",
    "user_expected_answer_text",
    "normalized_expected_answer_text",
    "must_contain_terms_existing",
    "normalized_must_contain_terms_json",
    "citation_locator",
]

SURFACE_ORDER = [
    "query",
    "candidate",
    "answer",
    "citation",
    "debug_public",
    "official_denominator",
]


@dataclass(frozen=True)
class SurfaceSpec:
    surface: str
    path: Path
    json_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class SensitiveToken:
    query_id: str
    row_source: str
    field: str
    token: str

    @property
    def sha256(self) -> str:
        return sha256_text(self.token)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    surface_specs = [parse_surface_spec(value) for value in args.surface_file]
    if not surface_specs:
        surface_specs = default_surface_specs(
            official_positive_csv=Path(args.official_positive_csv),
            official_denominator_registry=Path(args.official_denominator_registry),
            route_applied_json=Path(args.route_applied_json),
            fallback_applied_json=Path(args.fallback_applied_json),
            three_track_report_json=Path(args.three_track_report_json),
        )
    report = build_probe_report(
        normalized_csv=Path(args.normalized_csv),
        official_positive_csv=Path(args.official_positive_csv),
        route_applied_json=Path(args.route_applied_json),
        fallback_applied_json=Path(args.fallback_applied_json),
        three_track_report_json=Path(args.three_track_report_json),
        official_denominator_registry=Path(args.official_denominator_registry),
        surface_specs=surface_specs,
    )
    json_output = Path(args.json_output)
    md_output = Path(args.md_output)
    write_json(json_output, report)
    md_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "json_output": repo_relative(json_output),
                "md_output": repo_relative(md_output),
                "probe_target_row_count": report["counts"]["probe_target_row_count"],
                "surface_leakage_count": report["counts"]["surface_leakage_count"],
                "official_denominator_registry_changed": report["guardrails"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-csv", default=str(DEFAULT_NORMALIZED_CSV))
    parser.add_argument("--official-positive-csv", default=str(DEFAULT_OFFICIAL_POSITIVE_CSV))
    parser.add_argument("--route-applied-json", default=str(DEFAULT_ROUTE_APPLIED_JSON))
    parser.add_argument("--fallback-applied-json", default=str(DEFAULT_FALLBACK_APPLIED_JSON))
    parser.add_argument("--three-track-report-json", default=str(DEFAULT_THREE_TRACK_REPORT_JSON))
    parser.add_argument("--official-denominator-registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument(
        "--surface-file",
        action="append",
        default=[],
        help="Surface/path pair in the form surface=path. May be repeated.",
    )
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--md-output", default=str(DEFAULT_MD_OUTPUT))
    return parser.parse_args(argv)


def build_probe_report(
    *,
    normalized_csv: Path,
    official_positive_csv: Path,
    route_applied_json: Path,
    fallback_applied_json: Path,
    three_track_report_json: Path,
    official_denominator_registry: Path,
    surface_specs: Sequence[SurfaceSpec],
) -> dict[str, Any]:
    normalized_rows = read_csv_rows(normalized_csv)
    official_positive_rows = read_csv_rows(official_positive_csv) if official_positive_csv.exists() else []
    route_applied = read_json_if_exists(route_applied_json)
    fallback_applied = read_json_if_exists(fallback_applied_json)
    three_track_report = read_json_if_exists(three_track_report_json)

    excluded_rows = [row for row in normalized_rows if clean(row.get("derived_denominator_policy")) == EXCLUDED_POLICY]
    hidden_negative_rows = [row for row in excluded_rows if is_hidden_negative_row(row)]
    route_guard_rows = hidden_guard_rows(route_applied)
    fallback_guard_rows = hidden_guard_rows(fallback_applied)
    guard_rows = [
        *target_guard_rows(route_guard_rows, "route_applied_hidden_guard"),
        *target_guard_rows(fallback_guard_rows, "fallback_applied_hidden_guard"),
    ]
    target_rows = [*target_normalized_rows(excluded_rows), *guard_rows]
    sensitive_tokens = collect_sensitive_tokens(excluded_rows)
    official_positive_query_ids = {clean(row.get("query_id")) for row in official_positive_rows if clean(row.get("query_id"))}
    excluded_query_ids = {clean(row.get("query_id")) for row in excluded_rows if clean(row.get("query_id"))}
    official_positive_overlap_ids = sorted(excluded_query_ids & official_positive_query_ids)
    registry_overlap_ids: list[str] | None = None

    surface_scan = scan_surfaces(surface_specs=surface_specs, sensitive_tokens=sensitive_tokens)
    surface_violations = [violation for scan in surface_scan for violation in scan["violations"]]
    coverage = surface_coverage(surface_scan)
    three_track_guardrails = three_track_guardrail_summary(three_track_report)
    applied_guardrails = applied_guardrail_summary(route_applied, fallback_applied)

    guardrails = {
        "diagnostic_only": True,
        "promotion_evidence_created": False,
        "official_metric_created": False,
        "official_denominator_registry_changed": False,
        "official_denominator_opened_or_frozen": bool(three_track_report.get("official_denominator_opened_or_frozen", False)),
        "production_namespace_mutated": bool(three_track_report.get("production_namespace_mutated", False)),
        "production_vector_index_mutated": bool(three_track_report.get("production_vector_index_mutated", False)),
        "production_vector_written": bool(three_track_report.get("production_vector_written", False)),
        "candidate_artifact_mutated": False,
        "immutable_baseline_mutated": False,
        "diagnostic_only_row_promoted": bool(three_track_report.get("diagnostic_only_row_promoted", False)),
        "answer_generation_denominator_opened": xlsx_answer_generation_denominator(three_track_report) != 0,
        "route_fallback_labels_official_metric": applied_guardrails["route_or_fallback_metric_official"],
        "pdf_content_and_file_identity_aggregated": bool(
            applied_guardrails["pdf_content_and_file_identity_aggregated"]
            or three_track_guardrails["pdf_content_and_file_identity_aggregated"]
        ),
        "hidden_excluded_content_exposed": bool(surface_violations),
        "hidden_xlsx_content_exposed": bool(surface_violations),
        "query_surface_exposed": coverage.get("query", {}).get("leakage_count", 0) > 0,
        "candidate_surface_exposed": bool(
            coverage.get("candidate", {}).get("leakage_count", 0) > 0 or official_positive_overlap_ids
        ),
        "answer_citation_debug_surface_exposed": any(
            violation["surface"] in {"answer", "citation", "debug_public"}
            for violation in surface_violations
        ),
        "policy_excluded_rows_counted_as_retrieval_failures": bool(
            official_positive_overlap_ids
            or bool(registry_overlap_ids)
            or three_track_guardrails["policy_excluded_rows_counted_as_retrieval_failures"]
        ),
        "route_fallback_applied_labels_diagnostic_only": not applied_guardrails["route_or_fallback_metric_official"],
    }
    validation = validate_report_inputs(
        guardrails=guardrails,
        surface_violations=surface_violations,
        official_positive_overlap_ids=official_positive_overlap_ids,
        registry_overlap_ids=registry_overlap_ids,
        route_guard_rows=route_guard_rows,
        fallback_guard_rows=fallback_guard_rows,
        surface_scan=surface_scan,
    )
    status = "PASS" if validation["ok"] else "FAIL"
    hidden_negative_query_ids = [clean(row.get("query_id")) for row in hidden_negative_rows if clean(row.get("query_id"))]
    counts = {
        "normalized_total_row_count": len(normalized_rows),
        "normalized_excluded_row_count": len(excluded_rows),
        "normalized_hidden_negative_row_count": len(hidden_negative_rows),
        "route_hidden_excluded_guard_row_count": len(route_guard_rows),
        "fallback_hidden_excluded_guard_row_count": len(fallback_guard_rows),
        "hidden_excluded_guard_row_count": len(route_guard_rows) + len(fallback_guard_rows),
        "probe_target_row_count": len(target_rows),
        "sensitive_token_count": len(sensitive_tokens),
        "surface_file_count": len(surface_specs),
        "surface_leakage_count": len(surface_violations),
        "official_positive_overlap_count": len(official_positive_overlap_ids),
        "official_registry_overlap_count": None,
        "retrieval_failure_count_for_policy_excluded_rows": 0,
    }
    metrics = {
        "hidden_content_leakage_count": len(surface_violations),
        "hidden_negative_pass_count": len(hidden_negative_query_ids) if not surface_violations else 0,
        "search_error_count": 0,
        "result_empty_count": 0,
        "normalized_excluded_surface_leakage_count": len(surface_violations),
        "policy_excluded_retrieval_failure_count": 0,
    }
    query_results = target_query_results(target_rows, surface_violations)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": utc_timestamp(),
        "report_role": "xlsx_normalized_excluded_hidden_negative_leakage_probe",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "retrieval_run": False,
        "answer_generation_run": False,
        "source_artifacts": {
            "normalized_csv": file_identity(normalized_csv),
            "official_positive_csv": file_identity(official_positive_csv),
            "route_applied_json": file_identity(route_applied_json),
            "fallback_applied_json": file_identity(fallback_applied_json),
            "three_track_report_json": file_identity(three_track_report_json),
            "official_denominator_registry": registry_reference(official_denominator_registry),
        },
        "counts": counts,
        "hidden_negative_row_count": len(hidden_negative_query_ids),
        "hidden_negative_query_ids": hidden_negative_query_ids,
        "metrics": metrics,
        "query_results": query_results,
        "target_rows": target_rows,
        "sensitive_token_policy": {
            "raw_values_written_to_report": False,
            "fields_scanned": SENSITIVE_FIELDS,
            "minimum_token_length": MIN_TOKEN_LENGTH,
            "token_identity": "sha256_only",
        },
        "surface_coverage": coverage,
        "surface_scan": [
            {
                "surface": scan["surface"],
                "path": scan["path"],
                "exists": scan["exists"],
                "leakage_count": scan["leakage_count"],
                "status": scan["status"],
            }
            for scan in surface_scan
        ],
        "surface_violations": surface_violations,
        "denominator_checks": {
            "official_positive_overlap_ids": official_positive_overlap_ids,
            "official_denominator_registry_overlap_ids": registry_overlap_ids,
            "official_denominator_registry_overlap_status": "NOT_CHECKED_PROTECTED",
            "policy_excluded_rows_counted_as_retrieval_failures": guardrails[
                "policy_excluded_rows_counted_as_retrieval_failures"
            ],
            "reason": (
                "Policy-excluded XLSX rows are scanned for leakage only; retrieval is not run "
                "and excluded rows are not inserted into positive or official metric denominators."
            ),
        },
        "guardrails": guardrails,
        "validation": validation,
        "notes": [
            "Route/fallback applied labels are diagnostic analysis inputs only.",
            "PDF CONTENT evidence and FILE/document identity lanes remain separate.",
            "Raw excluded-row query, answer, evidence, citation, and debug text is not written to this report.",
        ],
    }


def target_normalized_rows(rows: Iterable[Mapping[str, str]]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for row in rows:
        query_id = clean(row.get("query_id"))
        tokens = list(field_tokens(row, query_id=query_id, row_source="normalized_excluded"))
        targets.append(
            {
                "query_id": query_id,
                "row_source": "normalized_excluded",
                "derived_denominator_policy": clean(row.get("derived_denominator_policy")),
                "hidden_negative": is_hidden_negative_row(row),
                "answer_generation_denominator": 0,
                "official_metric_input": False,
                "retrieval_failure_input": False,
                "reason_codes": split_reason_codes(row.get("derived_policy_reasons")),
                "sensitive_token_count": len(tokens),
                "sensitive_token_sha256": sorted({token.sha256 for token in tokens}),
            }
        )
    return targets


def target_guard_rows(rows: Iterable[Mapping[str, Any]], row_source: str) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for row in rows:
        targets.append(
            {
                "query_id": clean(row.get("query_id")),
                "row_source": row_source,
                "derived_denominator_policy": "DIAGNOSTIC_ONLY_GUARD",
                "hidden_negative": True,
                "answer_generation_denominator": 0,
                "official_metric_input": bool(row.get("official_metric_input", False)),
                "retrieval_failure_input": False,
                "reason_codes": list(row.get("blocked_flags") or []),
                "safe_query_redacted": "[redacted" in clean(row.get("safe_query_text")).lower(),
            }
        )
    return targets


def target_query_results(
    target_rows: Sequence[Mapping[str, Any]], surface_violations: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    violations_by_id: dict[str, list[Mapping[str, Any]]] = {}
    for violation in surface_violations:
        violations_by_id.setdefault(str(violation.get("query_id", "")), []).append(violation)
    results: list[dict[str, Any]] = []
    for row in target_rows:
        query_id = str(row.get("query_id", ""))
        row_violations = violations_by_id.get(query_id, [])
        hidden_leakage = bool(row_violations)
        results.append(
            {
                "query_id": query_id,
                "row_source": row.get("row_source", ""),
                "hidden_negative": bool(row.get("hidden_negative", False)),
                "hidden_leakage": hidden_leakage,
                "final_match_outcome": "leakage_detected" if hidden_leakage else "blocked_no_surface_leakage",
                "official_metric_input": bool(row.get("official_metric_input", False)),
                "retrieval_failure_input": bool(row.get("retrieval_failure_input", False)),
                "answer_generation_denominator": row.get("answer_generation_denominator", 0),
                "surface_violation_count": len(row_violations),
                "surface_violations": [
                    {
                        "surface": violation.get("surface", ""),
                        "path": violation.get("path", ""),
                        "fields": violation.get("fields", []),
                        "token_sha256": violation.get("token_sha256", []),
                    }
                    for violation in row_violations
                ],
            }
        )
    return results


def collect_sensitive_tokens(rows: Iterable[Mapping[str, str]]) -> list[SensitiveToken]:
    tokens: list[SensitiveToken] = []
    for row in rows:
        query_id = clean(row.get("query_id"))
        tokens.extend(field_tokens(row, query_id=query_id, row_source="normalized_excluded"))
    deduped: dict[tuple[str, str, str], SensitiveToken] = {}
    for token in tokens:
        deduped[(token.query_id, token.field, token.sha256)] = token
    return list(deduped.values())


def field_tokens(row: Mapping[str, str], *, query_id: str, row_source: str) -> Iterable[SensitiveToken]:
    for field in SENSITIVE_FIELDS:
        raw = clean(row.get(field))
        if not raw:
            continue
        values = sensitive_fragments(field, raw)
        for value in values:
            normalized = normalize_surface_token(value)
            if is_sensitive_token(normalized):
                yield SensitiveToken(query_id=query_id, row_source=row_source, field=field, token=normalized)


def sensitive_fragments(field: str, raw: str) -> list[str]:
    values = [raw]
    if field == "normalized_must_contain_terms_json":
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            loaded = []
        if isinstance(loaded, list):
            values.extend(str(item) for item in loaded)
    if field in {"must_contain_terms_existing", "query", "safe_query_text"}:
        values.extend(re.split(r"[\s,;|/]+", raw))
    return values


def scan_surfaces(*, surface_specs: Sequence[SurfaceSpec], sensitive_tokens: Sequence[SensitiveToken]) -> list[dict[str, Any]]:
    scans: list[dict[str, Any]] = []
    for spec in surface_specs:
        path = Path(spec.path)
        violations_by_row: dict[tuple[str, str, str], dict[str, Any]] = {}
        exists = path.exists()
        if exists:
            text = surface_text(path, spec.json_fields)
            for token in sensitive_tokens:
                if token.token and token.token in text:
                    key = (spec.surface, repo_relative(path), token.query_id)
                    violation = violations_by_row.setdefault(
                        key,
                        {
                            "surface": spec.surface,
                            "path": repo_relative(path),
                            "query_id": token.query_id,
                            "row_source": token.row_source,
                            "fields": [],
                            "token_sha256": [],
                        },
                    )
                    if token.field not in violation["fields"]:
                        violation["fields"].append(token.field)
                    if token.sha256 not in violation["token_sha256"]:
                        violation["token_sha256"].append(token.sha256)
        violations = list(violations_by_row.values())
        scans.append(
            {
                "surface": spec.surface,
                "path": repo_relative(path),
                "json_fields": list(spec.json_fields),
                "exists": exists,
                "status": "PASS" if exists and not violations else "FAIL" if violations else "MISSING",
                "leakage_count": len(violations),
                "violations": violations,
            }
        )
    return scans


def surface_coverage(scans: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    coverage = {
        surface: {"configured_file_count": 0, "existing_file_count": 0, "leakage_count": 0, "status": "NOT_CONFIGURED"}
        for surface in SURFACE_ORDER
    }
    for scan in scans:
        surface = str(scan["surface"])
        if surface not in coverage:
            coverage[surface] = {
                "configured_file_count": 0,
                "existing_file_count": 0,
                "leakage_count": 0,
                "status": "NOT_CONFIGURED",
            }
        coverage[surface]["configured_file_count"] += 1
        if scan.get("exists"):
            coverage[surface]["existing_file_count"] += 1
        coverage[surface]["leakage_count"] += int(scan.get("leakage_count") or 0)
    for surface, values in coverage.items():
        if values["configured_file_count"] == 0:
            values["status"] = "NOT_OPENED" if surface in {"answer", "citation"} else "NOT_CONFIGURED"
        elif values["leakage_count"]:
            values["status"] = "FAIL"
        elif values["existing_file_count"] == values["configured_file_count"]:
            values["status"] = "PASS"
        else:
            values["status"] = "MISSING_INPUT"
    return coverage


def validate_report_inputs(
    *,
    guardrails: Mapping[str, Any],
    surface_violations: Sequence[Mapping[str, Any]],
    official_positive_overlap_ids: Sequence[str],
    registry_overlap_ids: Sequence[str],
    route_guard_rows: Sequence[Mapping[str, Any]],
    fallback_guard_rows: Sequence[Mapping[str, Any]],
    surface_scan: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    if surface_violations:
        errors.append("excluded or hidden-negative raw content surfaced")
    if official_positive_overlap_ids:
        errors.append("normalized excluded rows overlapped official positive CSV")
    if registry_overlap_ids:
        errors.append("normalized excluded query ids appeared in official denominator registry")
    for key in [
        "official_denominator_registry_changed",
        "official_denominator_opened_or_frozen",
        "production_namespace_mutated",
        "production_vector_index_mutated",
        "production_vector_written",
        "candidate_artifact_mutated",
        "immutable_baseline_mutated",
        "diagnostic_only_row_promoted",
        "answer_generation_denominator_opened",
        "route_fallback_labels_official_metric",
        "pdf_content_and_file_identity_aggregated",
        "hidden_xlsx_content_exposed",
        "policy_excluded_rows_counted_as_retrieval_failures",
    ]:
        if guardrails.get(key) is not False:
            errors.append(f"guardrail {key} expected false")
    if not route_guard_rows:
        errors.append("route hidden/excluded guard row not found")
    if not fallback_guard_rows:
        errors.append("fallback hidden/excluded guard row not found")
    missing_required_surfaces = [
        scan["path"]
        for scan in surface_scan
        if scan["surface"] in {"query", "candidate", "debug_public", "official_denominator"} and not scan["exists"]
    ]
    if missing_required_surfaces:
        errors.append("missing required surface files: " + ", ".join(missing_required_surfaces))
    return {"ok": not errors, "errors": errors}


def render_markdown(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    guardrails = report["guardrails"]
    lines = [
        "# XLSX Hidden/Excluded Leakage Probe Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Status: `{report['status']}`",
        "- Scope: diagnostic-only; no retrieval, answer generation, vector write, registry update, or promotion.",
        f"- Probe target rows: `{counts['probe_target_row_count']}`",
        f"- Normalized excluded rows: `{counts['normalized_excluded_row_count']}`",
        f"- Normalized hidden-negative rows: `{counts['normalized_hidden_negative_row_count']}`",
        f"- Route/fallback hidden-excluded guard rows: `{counts['hidden_excluded_guard_row_count']}`",
        f"- Surface leakage count: `{counts['surface_leakage_count']}`",
        f"- Policy-excluded rows counted as retrieval failures: `{guardrails['policy_excluded_rows_counted_as_retrieval_failures']}`",
        "",
        "## Guardrails",
        "",
    ]
    for key in [
        "official_denominator_registry_changed",
        "production_namespace_mutated",
        "production_vector_index_mutated",
        "production_vector_written",
        "candidate_artifact_mutated",
        "immutable_baseline_mutated",
        "diagnostic_only_row_promoted",
        "answer_generation_denominator_opened",
        "route_fallback_labels_official_metric",
        "pdf_content_and_file_identity_aggregated",
        "hidden_excluded_content_exposed",
        "hidden_xlsx_content_exposed",
        "query_surface_exposed",
        "candidate_surface_exposed",
        "answer_citation_debug_surface_exposed",
        "policy_excluded_rows_counted_as_retrieval_failures",
    ]:
        lines.append(f"- `{key}`: `{json.dumps(guardrails[key], ensure_ascii=False)}`")
    lines.extend(["", "## Surface Coverage", "", "| Surface | Files | Existing | Leakage | Status |", "|---|---:|---:|---:|---|"])
    for surface in SURFACE_ORDER:
        values = report["surface_coverage"].get(surface, {})
        lines.append(
            "| "
            + " | ".join(
                [
                    surface,
                    str(values.get("configured_file_count", 0)),
                    str(values.get("existing_file_count", 0)),
                    str(values.get("leakage_count", 0)),
                    str(values.get("status", "")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Target Rows", "", "| query_id | source | hidden_negative | reasons |", "|---|---|---:|---|"])
    for row in report["target_rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(str(row.get("query_id", ""))),
                    escape_md(str(row.get("row_source", ""))),
                    str(row.get("hidden_negative", False)),
                    escape_md(", ".join(str(reason) for reason in row.get("reason_codes", []))),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Validation", ""])
    validation = report["validation"]
    lines.append(f"- `ok`: `{validation['ok']}`")
    if validation["errors"]:
        for error in validation["errors"]:
            lines.append(f"- `{escape_md(error)}`")
    else:
        lines.append("- No validation errors.")
    return "\n".join(lines) + "\n"


def hidden_guard_rows(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in ["codex_diagnostic_only_rows", "applied_human_review_rows", "human_review_rows"]:
        for row in artifact.get(section, []) or []:
            if not isinstance(row, Mapping):
                continue
            flags = {str(flag) for flag in row.get("blocked_flags") or []}
            source_hint = clean(row.get("source_type_hint"))
            classification = clean(row.get("codex_classification"))
            if (
                HIDDEN_EXCLUDED_FLAG in flags
                or source_hint == "xlsx_hidden_or_excluded_guard"
                or "hidden_or_excluded" in classification
            ):
                rows.append(dict(row))
    return rows


def applied_guardrail_summary(route_applied: Mapping[str, Any], fallback_applied: Mapping[str, Any]) -> dict[str, bool]:
    route_guardrails = route_applied.get("guardrails", {}) if isinstance(route_applied.get("guardrails"), Mapping) else {}
    fallback_guardrails = (
        fallback_applied.get("guardrails", {}) if isinstance(fallback_applied.get("guardrails"), Mapping) else {}
    )
    return {
        "route_or_fallback_metric_official": bool(
            route_applied.get("route_metrics_official", False)
            or route_applied.get("fallback_metrics_official", False)
            or fallback_applied.get("route_metrics_official", False)
            or fallback_applied.get("fallback_metrics_official", False)
        ),
        "pdf_content_and_file_identity_aggregated": bool(
            route_guardrails.get("pdf_content_and_file_identity_aggregated", False)
            or fallback_guardrails.get("pdf_content_and_file_identity_aggregated", False)
        ),
    }


def three_track_guardrail_summary(report: Mapping[str, Any]) -> dict[str, bool]:
    pdf_track = report.get("tracks", {}).get("pdf_business_ocr_mm", {}) if isinstance(report.get("tracks"), Mapping) else {}
    pdf_guards = set(pdf_track.get("guardrails", []) or []) if isinstance(pdf_track, Mapping) else set()
    return {
        "policy_excluded_rows_counted_as_retrieval_failures": bool(
            report.get("policy_excluded_rows_counted_as_retrieval_failures", False)
        ),
        "pdf_content_and_file_identity_aggregated": bool(
            report.get("pdf_content_and_file_identity_aggregated", False)
            or "content_evidence_and_file_document_identity_lanes_aggregated" in pdf_guards
        ),
    }


def xlsx_answer_generation_denominator(report: Mapping[str, Any]) -> int:
    tracks = report.get("tracks", {}) if isinstance(report.get("tracks"), Mapping) else {}
    xlsx = tracks.get("xlsx_business_structured", {}) if isinstance(tracks.get("xlsx_business_structured"), Mapping) else {}
    try:
        return int(xlsx.get("answer_generation_denominator", 0))
    except (TypeError, ValueError):
        return -1


def is_hidden_negative_row(row: Mapping[str, str]) -> bool:
    query_id = clean(row.get("query_id")).lower()
    hidden_policy = clean(row.get("hidden_policy")).lower()
    v2_status = clean(row.get("v2_label_status")).lower()
    eval_purpose = clean(row.get("eval_purpose")).lower()
    return (
        "hidden_policy" in query_id
        or hidden_policy in {"negative", "hidden_negative"}
        or v2_status == "negative_hidden_policy"
        or eval_purpose == "hidden_policy_negative"
    )


def split_reason_codes(value: Any) -> list[str]:
    text = clean(value)
    return [part for part in re.split(r"[;,]+", text) if part]


def default_surface_specs(
    *,
    official_positive_csv: Path,
    official_denominator_registry: Path,
    route_applied_json: Path,
    fallback_applied_json: Path,
    three_track_report_json: Path,
) -> list[SurfaceSpec]:
    return [
        SurfaceSpec("query", route_applied_json),
        SurfaceSpec("query", fallback_applied_json),
        SurfaceSpec("candidate", official_positive_csv),
        SurfaceSpec("debug_public", three_track_report_json),
        SurfaceSpec("debug_public", DEFAULT_THREE_TRACK_REPORT_MD),
        SurfaceSpec("debug_public", REPO_ROOT / "docs" / "rag-ingestion-progress.md"),
        SurfaceSpec("debug_public", REPO_ROOT / "docs" / "eval" / "denominator_policy.md"),
    ]


def parse_surface_spec(value: str) -> SurfaceSpec:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--surface-file must use surface=path")
    surface, path_value = value.split("=", 1)
    surface = surface.strip()
    if not surface:
        raise argparse.ArgumentTypeError("surface must not be blank")
    path, separator, fields = path_value.partition("::")
    json_fields = tuple(field.strip() for field in fields.split(",") if field.strip()) if separator else ()
    return SurfaceSpec(surface, Path(path), json_fields)


def surface_text(path: Path, json_fields: Sequence[str]) -> str:
    if not json_fields:
        return path.read_text(encoding="utf-8", errors="ignore")
    values: list[Any] = []
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                values.extend(selected_json_values(payload, json_fields))
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            payload = {}
        values.extend(selected_json_values(payload, json_fields))
    return "\n".join(json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values)


def selected_json_values(payload: Any, fields: Sequence[str]) -> Iterable[Any]:
    if not isinstance(payload, Mapping):
        return
    for field in fields:
        if field in payload:
            yield payload[field]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else "",
    }


def registry_reference(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "opened": False,
        "exists_checked": False,
        "bytes": None,
        "sha256": None,
        "mutation_check": "external_git_diff_only",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def normalize_surface_token(value: str) -> str:
    return re.sub(r"\s+", " ", clean(value))


def is_sensitive_token(value: str) -> bool:
    if len(value) < MIN_TOKEN_LENGTH:
        return False
    lowered = value.lower()
    if lowered in {"policy_excluded", "not_answerable", "evidence_mismatch", "exclude_hidden"}:
        return False
    if lowered.startswith("{") and len(value) < 24:
        return False
    return True


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
