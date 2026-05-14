"""Diagnostic-only XLSX/PDF route tracing for RAG ingestion v2.

The harness consumes existing XLSX/PDF diagnostic retrieval reports and
normalizes them into route/citation contract rows. It never indexes, promotes,
or generates answers.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER = Path(__file__).resolve().parents[2]
ROOT = AI_WORKER.parent
REPORT_DIR = AI_WORKER / "eval" / "reports" / "rag-ingestion"
QUERY_DIR = AI_WORKER / "eval" / "eval_queries"
OFFICIAL_REGISTRY = QUERY_DIR / "official_denominator_registry.json"

XLSX_INDEX_VERSION = "rag-ingestion-v2-xlsx-candidate-v1"
PDF_INDEX_VERSION = "rag-ingestion-v2-pdf-candidate-v1"
XLSX_PARSER_VERSION = "xlsx-extract-v2-hidden-safe"
PDF_ALLOWED_PARSER_VERSIONS = ("pdf-extract-v1", "pdf-extract-v2")

DEFAULT_XLSX_REPORT = REPORT_DIR / "rag_retrieval_eval_xlsx_human_review_official_positive_v0_vector_diagnostic_report.json"
DEFAULT_XLSX_HIDDEN_REPORT = REPORT_DIR / "rag_xlsx_human_review_official_positive_v0_hidden_negative_leakage_diagnostic.json"
DEFAULT_PDF_REPORT = REPORT_DIR / "rag_retrieval_eval_pdf_vector_diagnostic_report.json"

UNKNOWN = "UNKNOWN_NOT_EXPOSED_BY_SOURCE_REPORT"

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
STATUS_DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"

ROUTE_XLSX_WRAPPER = "XLSX_STRICT_WRAPPER"
ROUTE_PDF_FILE = "PDF_FILE_LOOKUP"
ROUTE_PDF_CONTENT = "PDF_CONTENT_LOOKUP"
ROUTE_TEXT_OUT_OF_SCOPE = "TEXT_OR_NAMU_OUT_OF_SCOPE"

FAIL_NO_EVIDENCE = "no_evidence_retrieved"
FAIL_ROUTE_MISMATCH = "route_mismatch"
FAIL_FILE_CONTENT_MISMATCH = "file_vs_content_route_mismatch"
FAIL_MISSING_CITATION = "missing_citation_text"
FAIL_MISSING_LOCATION = "missing_location_json"
FAIL_INVALID_LOCATION = "invalid_location_json"
FAIL_HIDDEN_LEAKAGE = "hidden_xlsx_content_leakage"
FAIL_ALLOW_UNSCOPED = "allow_unscoped_true"
FAIL_XLSX_STRICT_ROUTE = "xlsx_strict_wrapper_violation"
FAIL_INDEX_SCOPE = "index_scope_mismatch"
FAIL_EMBEDDING_STATUS = "embedding_status_not_embedded"
FAIL_PARSER_VERSION = "parser_version_not_allowed"

RETRY_FAILURES = {
    FAIL_ROUTE_MISMATCH,
    FAIL_FILE_CONTENT_MISMATCH,
    FAIL_MISSING_CITATION,
    FAIL_MISSING_LOCATION,
    FAIL_INVALID_LOCATION,
    FAIL_NO_EVIDENCE,
}


@dataclass(frozen=True)
class TraceConfig:
    date: str = "20260507"
    max_xlsx_queries: int | None = 5
    max_pdf_queries: int | None = 5
    xlsx_report: Path = DEFAULT_XLSX_REPORT
    xlsx_hidden_report: Path = DEFAULT_XLSX_HIDDEN_REPORT
    pdf_report: Path = DEFAULT_PDF_REPORT
    official_registry: Path = OFFICIAL_REGISTRY
    report_path: Path | None = None
    markdown_path: Path | None = None
    max_retries: int = 2


class RouteIntentClassifier:
    """Conservative deterministic route classifier for diagnostic rows."""

    def classify(self, query_result: Mapping[str, Any], *, file_type: str) -> dict[str, str]:
        file_type_upper = clean(file_type).upper()
        bucket = clean(query_result.get("bucket")).lower()
        location_type = clean(query_result.get("expected_location_type")).lower()

        if file_type_upper == "XLSX" or location_type == "xlsx" or bucket.startswith("xlsx_"):
            return {
                "expected_route_hint": ROUTE_XLSX_WRAPPER,
                "actual_route": ROUTE_XLSX_WRAPPER,
                "route_reason": "XLSX rows are constrained to the strict wrapper retrieval-evidence lane.",
            }

        if file_type_upper == "PDF" or location_type in {"pdf", "ocr"} or bucket.startswith("pdf_"):
            if bucket in {"pdf_page_lookup"}:
                route = ROUTE_PDF_FILE
                reason = "PDF page lookup bucket is treated as FILE lookup for diagnostic routing."
            else:
                route = ROUTE_PDF_CONTENT
                reason = "PDF section/table/OCR bucket is treated as CONTENT lookup for diagnostic routing."
            return {
                "expected_route_hint": route,
                "actual_route": route,
                "route_reason": reason + " Gold policy is still review-lane.",
            }

        return {
            "expected_route_hint": ROUTE_TEXT_OUT_OF_SCOPE,
            "actual_route": ROUTE_TEXT_OUT_OF_SCOPE,
            "route_reason": "Non-XLSX/PDF routes are out of scope for this diagnostic.",
        }


class CitationContractValidator:
    """Validate citation-capable metadata without answer generation."""

    def validate_hit(
        self,
        hit: Mapping[str, Any] | None,
        *,
        file_type: str,
        index_scope: str,
    ) -> list[str]:
        if not hit:
            return [FAIL_NO_EVIDENCE]

        failures: list[str] = []
        if not clean(hit.get("citation_text")):
            failures.append(FAIL_MISSING_CITATION)

        location = hit.get("location_json")
        if location in (None, ""):
            failures.append(FAIL_MISSING_LOCATION)
        elif not isinstance(location, Mapping):
            failures.append(FAIL_INVALID_LOCATION)
        elif not location_valid(location, file_type=file_type):
            failures.append(FAIL_INVALID_LOCATION)

        parser_version = clean(hit.get("parser_version"))
        if clean(file_type).upper() == "XLSX" and parser_version != XLSX_PARSER_VERSION:
            failures.append(FAIL_PARSER_VERSION)
        if clean(file_type).upper() == "PDF" and parser_version not in PDF_ALLOWED_PARSER_VERSIONS:
            failures.append(FAIL_PARSER_VERSION)

        if clean(hit.get("index_version")) and clean(hit.get("index_version")) != index_scope:
            failures.append(FAIL_INDEX_SCOPE)
        if clean(hit.get("embedding_status")).upper() not in {"", "EMBEDDED"}:
            failures.append(FAIL_EMBEDDING_STATUS)

        return dedupe(failures)


class EvidenceVerifier:
    """Convert query results and hits into route-trace rows."""

    def __init__(self, validator: CitationContractValidator | None = None) -> None:
        self.validator = validator or CitationContractValidator()

    def build_row(
        self,
        query_result: Mapping[str, Any],
        *,
        file_type: str,
        report: Mapping[str, Any],
        hidden_leakage_status: str,
        classifier: RouteIntentClassifier,
    ) -> dict[str, Any]:
        route = classifier.classify(query_result, file_type=file_type)
        index_scope = report_index_scope(report, file_type=file_type)
        allow_unscoped = allow_unscoped_value(report, index_scope=index_scope)
        hit = select_primary_hit(query_result, file_type=file_type)
        failures = self.validator.validate_hit(hit, file_type=file_type, index_scope=index_scope)
        if allow_unscoped is True or allow_unscoped == UNKNOWN:
            failures.append(FAIL_ALLOW_UNSCOPED)
        if clean(file_type).upper() == "XLSX":
            failures.extend(validate_xlsx_strict_wrapper(report, hit, hidden_leakage_status))
        if clean(file_type).upper() == "PDF":
            failures.extend(validate_pdf_route(route["actual_route"], hit))
        failures = dedupe(failures)

        status = route_status(file_type=file_type, failures=failures)
        location = hit.get("location_json") if isinstance(hit, Mapping) else None
        evidence_source = evidence_source_for_hit(hit, file_type=file_type)
        lookup_route = lookup_route_for_actual_route(route["actual_route"])
        lane_counts = evidence_lane_counts(query_result, file_type=file_type)

        return {
            "query_id": clean(query_result.get("query_id")),
            "query_text": clean(query_result.get("query")),
            "expected_route_hint": route["expected_route_hint"],
            "actual_route": route["actual_route"],
            "route_reason": route["route_reason"],
            "file_type": clean(file_type).upper(),
            "source_file_id": hit_value(hit, "source_file_id"),
            "source_file_name": hit_value(hit, "source_file_name"),
            "document_version_id": document_version_id(hit),
            "extracted_artifact_id": hit_value(hit, "extracted_artifact_id"),
            "search_unit_id": hit_value(hit, "search_unit_id"),
            "parser_version": hit_value(hit, "parser_version"),
            "location_json_present": presence(location),
            "location_json_valid": location_valid(location, file_type=file_type) if isinstance(location, Mapping) else False,
            "citation_text_present": presence(hit.get("citation_text") if isinstance(hit, Mapping) else None),
            "display_text_present": exposed_presence(hit, "display_text"),
            "bm25_text_present": exposed_presence(hit, "bm25_text"),
            "embedding_text_present": exposed_presence(hit, "embedding_text"),
            "evidence_source": evidence_source,
            "lookup_route": lookup_route,
            "allowUnscoped": allow_unscoped,
            "allowUnscoped_source": allow_unscoped_source(report, index_scope=index_scope),
            "index_scope": index_scope,
            "hidden_excluded_leakage": hidden_leakage_status if clean(file_type).upper() == "XLSX" else "NOT_APPLICABLE",
            "route_status": status,
            "failure_category": first_failure(failures),
            "failure_categories": failures,
            "diagnostic_only_reason": diagnostic_only_reason(file_type=file_type, status=status),
            "source_final_match_outcome": query_result.get("final_match_outcome", UNKNOWN),
            "rank": hit.get("rank") if isinstance(hit, Mapping) else None,
            "chunk_type": hit_value(hit, "chunk_type"),
            "page_only_evidence": is_page_only(hit),
            "table_like_evidence": is_table_like(hit),
            "bbox_present": bbox_present(hit),
            "pdf_page_match": pdf_match_value(hit, "pdf_page_match"),
            "pdf_bbox_overlap": pdf_match_value(hit, "pdf_bbox_overlap"),
            "pdf_exact_bbox": pdf_match_value(hit, "pdf_exact_bbox"),
            "expected_page_no": clean(query_result.get("expected_page_no")) or UNKNOWN,
            "actual_page_no": actual_page_no(hit),
            "expected_bbox": clean(query_result.get("expected_bbox")) or UNKNOWN,
            "actual_bbox": actual_bbox(hit),
            "page_policy_status": pdf_policy_status(query_result, policy="page"),
            "bbox_policy_status": pdf_policy_status(query_result, policy="bbox"),
            "ocr_fallback_used": ocr_used(hit),
            "native_pdf_text_used": clean(file_type).upper() == "PDF" and hit is not None and not ocr_used(hit),
            "file_lookup_route": route["actual_route"] == ROUTE_PDF_FILE,
            "content_lookup_route": route["actual_route"] == ROUTE_PDF_CONTENT,
            "evidence_lane_counts": lane_counts,
            "source_report_query_outcome": query_result.get("final_match_outcome"),
            "source_report_failure_reason": query_result.get("failure_reason", UNKNOWN),
            "source_report_failure_reason_exposure": "EXPOSED" if "failure_reason" in query_result else UNKNOWN,
            "pdf_lane_exposure_status": pdf_lane_exposure_status(hit, file_type=file_type),
        }


class ScopedRetriever:
    """Report-replay retriever for diagnostic route verification."""

    def __init__(self, trace_rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = {clean(row.get("query_id")): dict(row) for row in trace_rows}

    def retrieve(self, query_id: str, *, route: str, allow_unscoped: bool = False) -> dict[str, Any] | None:
        if allow_unscoped:
            raise ValueError("allowUnscoped must remain false for this diagnostic")
        row = self._rows.get(clean(query_id))
        if not row:
            return None
        if route == row.get("actual_route"):
            return dict(row)
        candidate = dict(row)
        candidate["failure_categories"] = dedupe([*list(row.get("failure_categories") or []), FAIL_ROUTE_MISMATCH])
        candidate["failure_category"] = first_failure(candidate["failure_categories"])
        candidate["route_status"] = STATUS_REVIEW_REQUIRED if row.get("file_type") == "PDF" else STATUS_FAIL
        return candidate


class RouteRetryController:
    """Bounded diagnostic route retry controller."""

    def __init__(self, *, max_retries: int = 2) -> None:
        if max_retries < 0 or max_retries > 2:
            raise ValueError("max_retries must be in [0, 2]")
        self.max_retries = max_retries

    def run_case(self, row: Mapping[str, Any], retriever: ScopedRetriever) -> dict[str, Any]:
        current_route = clean(row.get("actual_route"))
        attempts: list[dict[str, Any]] = []
        final_row: dict[str, Any] | None = None

        for iteration in range(self.max_retries + 1):
            result = retriever.retrieve(clean(row.get("query_id")), route=current_route, allow_unscoped=False)
            if result is None:
                failure_categories = [FAIL_NO_EVIDENCE]
            else:
                failure_categories = list(result.get("failure_categories") or [])
            retryable = any(reason in RETRY_FAILURES for reason in failure_categories)
            stop_reason = "completed"
            if retryable and iteration < self.max_retries:
                stop_reason = "retry_route_contract_failure"
            elif retryable:
                stop_reason = "max_retries_exhausted"

            attempts.append(
                {
                    "iteration": iteration,
                    "route": current_route,
                    "allowUnscoped": False,
                    "retriever_or_tool_name": route_tool_name(current_route),
                    "candidate_ids": [result.get("search_unit_id")] if result and result.get("search_unit_id") not in (None, UNKNOWN, "") else [],
                    "selected_context_ids": [result.get("search_unit_id")] if result and not retryable and result.get("search_unit_id") not in (None, UNKNOWN, "") else [],
                    "failure_categories": failure_categories,
                    "stop_reason": stop_reason,
                }
            )
            final_row = dict(result or row)
            if not retryable or iteration >= self.max_retries:
                break
            current_route = next_retry_route(current_route, row)

        unresolved = any(reason in RETRY_FAILURES for reason in list((final_row or {}).get("failure_categories") or []))
        final_status = final_row.get("route_status") if final_row else STATUS_FAIL
        if unresolved and final_status == STATUS_PASS:
            final_status = STATUS_DIAGNOSTIC_ONLY

        return {
            "query_id": clean(row.get("query_id")),
            "query_text": clean(row.get("query_text")),
            "file_type": clean(row.get("file_type")),
            "initial_route": clean(row.get("actual_route")),
            "final_route": attempts[-1]["route"] if attempts else clean(row.get("actual_route")),
            "attempt_count": len(attempts),
            "max_retries": self.max_retries,
            "retry_exhausted": bool(attempts and attempts[-1]["stop_reason"] == "max_retries_exhausted"),
            "allowUnscoped": False,
            "route_status": final_status,
            "failure_category": first_failure(list((final_row or {}).get("failure_categories") or [])),
            "failure_categories": list((final_row or {}).get("failure_categories") or []),
            "diagnostic_only_reason": "agentic_route_loop_only_no_answer_generation",
            "iterations": attempts,
        }


class DiagnosticReporter:
    """Build JSON and Markdown reports for route diagnostics."""

    def route_trace_report(self, config: TraceConfig) -> dict[str, Any]:
        xlsx_report = read_json(config.xlsx_report)
        xlsx_hidden_report = read_json(config.xlsx_hidden_report)
        pdf_report = read_json(config.pdf_report)
        classifier = RouteIntentClassifier()
        verifier = EvidenceVerifier()

        hidden_status = hidden_leakage_status(xlsx_hidden_report)
        xlsx_results = limited_results(xlsx_report, config.max_xlsx_queries)
        pdf_results = limited_results(pdf_report, config.max_pdf_queries)
        rows = [
            verifier.build_row(
                result,
                file_type="XLSX",
                report=xlsx_report,
                hidden_leakage_status=hidden_status,
                classifier=classifier,
            )
            for result in xlsx_results
        ]
        rows.extend(
            verifier.build_row(
                result,
                file_type="PDF",
                report=pdf_report,
                hidden_leakage_status="NOT_APPLICABLE",
                classifier=classifier,
            )
            for result in pdf_results
        )

        return base_payload(
            config,
            report_role="xlsx_pdf_route_trace_diagnostic",
            rows=rows,
            source_reports=[config.xlsx_report, config.xlsx_hidden_report, config.pdf_report],
            extra={
                "retrieval_execution": "report_replay_from_existing_diagnostic_reports",
                "agentic_loop_execution": "not_run_by_this_report",
                "xlsx_leakage_probe": xlsx_leakage_summary(xlsx_hidden_report),
                "pdf_file_vs_content_routing": pdf_route_summary(rows),
                "pdf_native_ocr_routing": pdf_native_ocr_summary(rows),
                "pdf_sampling": pdf_sampling_summary(pdf_report, pdf_results),
            },
        )

    def agentic_loop_report(self, config: TraceConfig) -> dict[str, Any]:
        trace_payload = self.route_trace_report(config)
        rows = trace_payload["route_trace_rows"]
        retriever = ScopedRetriever(rows)
        controller = RouteRetryController(max_retries=config.max_retries)
        loop_rows = [controller.run_case(row, retriever) for row in rows]
        return base_payload(
            config,
            report_role="xlsx_pdf_agentic_route_loop_diagnostic",
            rows=rows,
            source_reports=[config.xlsx_report, config.xlsx_hidden_report, config.pdf_report],
            extra={
                "retrieval_execution": "agentic_route_report_replay_only",
                "agentic_loop_execution": "bounded_route_verification_only",
                "answer_generation_execution": "not_run_by_this_script",
                "max_retries": config.max_retries,
                "agentic_route_loop_rows": loop_rows,
                "agentic_retry_summary": retry_summary(loop_rows),
                "xlsx_leakage_probe": trace_payload["xlsx_leakage_probe"],
                "pdf_file_vs_content_routing": trace_payload["pdf_file_vs_content_routing"],
                "pdf_native_ocr_routing": trace_payload["pdf_native_ocr_routing"],
                "pdf_sampling": trace_payload["pdf_sampling"],
            },
        )

    def write(self, payload: Mapping[str, Any], *, json_path: Path, markdown_path: Path) -> None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(payload), encoding="utf-8")


def build_route_trace_report(config: TraceConfig) -> dict[str, Any]:
    return DiagnosticReporter().route_trace_report(config)


def build_agentic_loop_report(config: TraceConfig) -> dict[str, Any]:
    return DiagnosticReporter().agentic_loop_report(config)


def default_route_report_paths(date: str) -> tuple[Path, Path]:
    stem = f"xlsx_pdf_route_trace_diagnostic_{date}"
    return REPORT_DIR / f"{stem}.json", REPORT_DIR / f"{stem}.md"


def default_agentic_report_paths(date: str) -> tuple[Path, Path]:
    stem = f"xlsx_pdf_agentic_route_loop_diagnostic_{date}"
    return REPORT_DIR / f"{stem}.json", REPORT_DIR / f"{stem}.md"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected object JSON at {path}")
    return data


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def limited_results(report: Mapping[str, Any], limit: int | None) -> list[dict[str, Any]]:
    rows = [dict(row) for row in list(report.get("query_results") or [])]
    if limit is None or limit < 0:
        return rows
    return rows[:limit]


def base_payload(
    config: TraceConfig,
    *,
    report_role: str,
    rows: list[dict[str, Any]],
    source_reports: Sequence[Path],
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    counts = status_counts(rows)
    failure_counts = failure_category_counts(rows)
    git = git_summary()
    registry_diff = denominator_registry_diff(config.official_registry)
    protected = protected_artifact_diff()
    source_guardrail_failures = source_report_guardrail_failures(source_reports)
    registry_changed = registry_diff.get("git_diff_empty") is False
    guardrail_failures = []
    if registry_changed:
        guardrail_failures.append("official_denominator_registry_git_diff_not_empty")
    if protected.get("protected_artifact_changed"):
        guardrail_failures.append("protected_artifact_git_status_not_empty")
    guardrail_failures.extend(source_guardrail_failures)
    status = STATUS_FAIL if counts.get(STATUS_FAIL, 0) or guardrail_failures else STATUS_DIAGNOSTIC_ONLY
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": report_role,
        "promotion_evidence": False,
        "official_denominator_changed": registry_changed,
        "official_denominator_changed_by_harness": False,
        "official_denominator_registry_diff": registry_diff,
        "evidence_role": "diagnostic",
        "answer_generation_execution": "not_run_by_this_script",
        "xlsx_answer_denominator": 0,
        "pdf_answer_denominator": 0,
        "answer_denominators_collapsed": False,
        "retrieval_backend": "vector_report_replay",
        "allowUnscoped": False,
        "broad_candidate_indexing_execution": "not_run_by_this_script",
        "search_unit_indexing_cli_execution": "not_run_by_this_script",
        "baseline_mutation_execution": "not_run_by_this_script",
        "candidate_artifact_mutation_execution": "not_run_by_this_script",
        "source_reports": [artifact_identity(path) for path in source_reports],
        "route_counts": counts,
        "failure_category_counts": failure_counts,
        "guardrail_failures": guardrail_failures,
        "source_report_guardrail_failures": source_guardrail_failures,
        "review_required_count": counts.get(STATUS_REVIEW_REQUIRED, 0),
        "diagnostic_only_count": counts.get(STATUS_DIAGNOSTIC_ONLY, 0),
        "route_trace_rows": rows,
        "git_diff_summary": git,
        "protected_artifact_diff": protected,
        "commands": {
            "route_trace": (
                "python scripts\\rag_xlsx_pdf_route_trace_diagnostic.py "
                f"--date {config.date} --max-xlsx-queries {config.max_xlsx_queries} "
                f"--max-pdf-queries {config.max_pdf_queries}"
            ),
            "agentic_loop": (
                "python scripts\\rag_xlsx_pdf_agentic_route_loop_diagnostic.py "
                f"--date {config.date} --max-xlsx-queries {config.max_xlsx_queries} "
                f"--max-pdf-queries {config.max_pdf_queries} --max-retries {config.max_retries}"
            ),
        },
        "conservative_assumptions": [
            "Existing retrieval reports are treated as diagnostic inputs, not promotion evidence.",
            "Fields absent from source reports are reported as UNKNOWN_NOT_EXPOSED_BY_SOURCE_REPORT.",
            "PDF FILE vs CONTENT, table/page, bbox, answerability, and expected-evidence policy remain review-lane.",
            "Native PDF text is preferred over OCR fallback when both are available.",
        ],
        **dict(extra),
    }


def artifact_identity(path: Path) -> dict[str, Any]:
    resolved = resolve_path(path)
    return {
        "path": display_path(resolved),
        "exists": resolved.exists(),
        "sha256": sha256_file(resolved) if resolved.exists() and resolved.is_file() else None,
    }


def denominator_registry_diff(path: Path) -> dict[str, Any]:
    resolved = resolve_path(path)
    repo_scoped = is_under_root(resolved)
    diff = (
        git_capture(["git", "diff", "--", display_path(resolved)])
        if repo_scoped
        else {"ok": True, "stdout": "", "stderr": ""}
    )
    return {
        "path": display_path(resolved),
        "exists": resolved.exists(),
        "sha256": sha256_file(resolved) if resolved.exists() else None,
        "git_diff_empty": diff["ok"] and not diff["stdout"].strip(),
        "git_diff_error": None if diff["ok"] else diff["stderr"],
        "official_denominator_changed": diff["ok"] and bool(diff["stdout"].strip()),
        "official_denominator_changed_by_harness": False,
    }


def protected_artifact_diff() -> dict[str, Any]:
    protected = [
        "ai/eval/indexes/rag-data-canary",
        "ai/eval/indexes/rag-data-xlsx-candidate-v1",
        "ai/eval/indexes/rag-data-pdf-candidate-v1",
        "ai/eval/indexes/rag-data",
    ]
    status = git_capture(["git", "status", "--short", "--", *protected])
    changed = [line for line in status["stdout"].splitlines() if line.strip()] if status["ok"] else []
    return {
        "protected_paths": protected,
        "check_kind": "git_status_tracked_and_unignored_only",
        "git_status_entries": changed,
        "protected_artifact_changed": bool(changed),
        "protected_artifact_changed_by_git_status": bool(changed),
        "diagnostic_limitation": (
            "Ignored protected artifact directories require an external before/after "
            "fingerprint for mutation proof; git status is only a narrow guard."
        ),
    }


def git_summary() -> dict[str, Any]:
    status = git_capture(["git", "status", "--short"])
    diff_stat = git_capture(["git", "diff", "--stat"])
    return {
        "status_short": status["stdout"].splitlines() if status["ok"] else [],
        "diff_stat": diff_stat["stdout"].splitlines() if diff_stat["ok"] else [],
        "status_error": None if status["ok"] else status["stderr"],
        "diff_stat_error": None if diff_stat["ok"] else diff_stat["stderr"],
    }


def git_capture(args: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc)}
    return {"ok": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    candidate = AI_WORKER / path
    if candidate.exists():
        return candidate
    candidate = ROOT / path
    if candidate.exists():
        return candidate
    return (AI_WORKER / path).resolve()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def is_under_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def report_index_scope(report: Mapping[str, Any], *, file_type: str) -> str:
    value = clean(report.get("namespace") or report.get("index_version") or report.get("candidate_index_version"))
    if value:
        return value
    backend_identity = report.get("backend_identity")
    if isinstance(backend_identity, Mapping):
        value = clean(backend_identity.get("index_namespace_filter") or backend_identity.get("required_index_version"))
        if value:
            return value
    return UNKNOWN


def allow_unscoped_value(report: Mapping[str, Any], *, index_scope: str) -> bool | str:
    if "allowUnscoped" in report:
        return bool(report.get("allowUnscoped"))
    backend_identity = report.get("backend_identity")
    if (
        isinstance(backend_identity, Mapping)
        and clean(backend_identity.get("index_namespace_filter")) == clean(index_scope)
        and index_scope != UNKNOWN
    ):
        return False
    return UNKNOWN


def allow_unscoped_source(report: Mapping[str, Any], *, index_scope: str) -> str:
    if "allowUnscoped" in report:
        return "source_report_allowUnscoped"
    if allow_unscoped_value(report, index_scope=index_scope) is False:
        return "inferred_from_backend_identity_index_namespace_filter"
    return UNKNOWN


def validate_xlsx_strict_wrapper(
    report: Mapping[str, Any],
    hit: Mapping[str, Any] | None,
    hidden_leakage_status_value: str,
) -> list[str]:
    failures: list[str] = []
    if report_index_scope(report, file_type="XLSX") != XLSX_INDEX_VERSION:
        failures.append(FAIL_XLSX_STRICT_ROUTE)
    route_guard = report.get("official_route_guard")
    if isinstance(route_guard, Mapping):
        if bool(route_guard.get("agent_orchestrator_enabled")) or bool(route_guard.get("combined_retrieval_enabled")):
            failures.append(FAIL_XLSX_STRICT_ROUTE)
    if hit and clean(hit.get("parser_version")) != XLSX_PARSER_VERSION:
        failures.append(FAIL_XLSX_STRICT_ROUTE)
    if hidden_leakage_status_value == STATUS_FAIL:
        failures.append(FAIL_HIDDEN_LEAKAGE)
    return failures


def validate_pdf_route(actual_route: str, hit: Mapping[str, Any] | None) -> list[str]:
    if not hit:
        return []
    breakdown = hit.get("match_breakdown") if isinstance(hit.get("match_breakdown"), Mapping) else {}
    if actual_route == ROUTE_PDF_FILE and breakdown:
        if not bool(breakdown.get("file_match", False)):
            return [FAIL_FILE_CONTENT_MISMATCH]
    if actual_route == ROUTE_PDF_CONTENT and is_page_only(hit):
        return [FAIL_FILE_CONTENT_MISMATCH]
    return []


def select_primary_hit(query_result: Mapping[str, Any], *, file_type: str) -> dict[str, Any] | None:
    hits = [dict(hit) for hit in list(query_result.get("top_k_results") or []) if isinstance(hit, Mapping)]
    if not hits:
        return None
    file_type_upper = clean(file_type).upper()
    if file_type_upper == "PDF":
        return sorted(
            hits,
            key=lambda hit: (
                0 if not ocr_used(hit) else 1,
                0 if bool((hit.get("match_breakdown") or {}).get("identity_match")) else 1,
                int(hit.get("rank") or 9999),
            ),
        )[0]
    return sorted(
        hits,
        key=lambda hit: (
            0 if bool((hit.get("match_breakdown") or {}).get("identity_match")) else 1,
            0 if bool((hit.get("match_breakdown") or {}).get("location_match")) else 1,
            int(hit.get("rank") or 9999),
        ),
    )[0]


def hidden_leakage_status(hidden_report: Mapping[str, Any]) -> str:
    metrics = hidden_report.get("metrics") if isinstance(hidden_report.get("metrics"), Mapping) else {}
    leakage = int(metrics.get("hidden_content_leakage_count") or 0)
    errors = int(metrics.get("search_error_count") or 0)
    row_count = int(hidden_report.get("hidden_negative_row_count") or 0)
    pass_count = int(metrics.get("hidden_negative_pass_count") or 0)
    validation = hidden_report.get("validation")
    validation_failed = isinstance(validation, Mapping) and validation.get("ok") is False
    metric_mixing = bool(hidden_report.get("positive_metric_mix_allowed", False))
    not_excluded = not bool(hidden_report.get("excluded_from_positive_metrics", True))
    pass_mismatch = row_count > 0 and pass_count != row_count
    if leakage or errors or validation_failed or metric_mixing or not_excluded or pass_mismatch:
        return STATUS_FAIL
    if row_count <= 0:
        return STATUS_DIAGNOSTIC_ONLY
    return STATUS_PASS


def xlsx_leakage_summary(hidden_report: Mapping[str, Any]) -> dict[str, Any]:
    metrics = hidden_report.get("metrics") if isinstance(hidden_report.get("metrics"), Mapping) else {}
    row_count = int(hidden_report.get("hidden_negative_row_count") or 0)
    pass_count = int(metrics.get("hidden_negative_pass_count") or 0)
    validation = hidden_report.get("validation")
    validation_ok = validation.get("ok") if isinstance(validation, Mapping) else UNKNOWN
    return {
        "status": hidden_leakage_status(hidden_report),
        "hidden_negative_row_count": row_count,
        "hidden_content_leakage_count": int(metrics.get("hidden_content_leakage_count") or 0),
        "hidden_negative_pass_count": pass_count,
        "hidden_negative_pass_count_matches_row_count": pass_count == row_count if row_count > 0 else UNKNOWN,
        "validation_ok": validation_ok,
        "positive_metric_mix_allowed": bool(hidden_report.get("positive_metric_mix_allowed", False)),
        "excluded_from_positive_metrics": bool(hidden_report.get("excluded_from_positive_metrics", True)),
        "query_surface_hidden_leakage": int(metrics.get("hidden_content_leakage_count") or 0) > 0,
        "candidate_surface_hidden_leakage": int(metrics.get("hidden_content_leakage_count") or 0) > 0,
        "retrieval_evidence_surface_hidden_leakage": int(metrics.get("hidden_content_leakage_count") or 0) > 0,
        "answer_citation_surface_hidden_leakage": "NOT_EXERCISED_NO_ANSWER_GENERATION",
    }


def pdf_route_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    pdf_rows = [row for row in rows if row.get("file_type") == "PDF"]
    return {
        "file_lookup_route_count": sum(1 for row in pdf_rows if row.get("file_lookup_route")),
        "content_lookup_route_count": sum(1 for row in pdf_rows if row.get("content_lookup_route")),
        "review_required_count": sum(1 for row in pdf_rows if row.get("route_status") == STATUS_REVIEW_REQUIRED),
        "file_content_mismatch_count": sum(
            1 for row in pdf_rows if FAIL_FILE_CONTENT_MISMATCH in list(row.get("failure_categories") or [])
        ),
    }


def pdf_native_ocr_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    pdf_rows = [row for row in rows if row.get("file_type") == "PDF"]
    return {
        "native_pdf_text_evidence_count": sum(1 for row in pdf_rows if row.get("native_pdf_text_used")),
        "ocr_fallback_evidence_count": sum(1 for row in pdf_rows if row.get("ocr_fallback_used")),
        "page_only_evidence_count": sum(1 for row in pdf_rows if row.get("page_only_evidence")),
        "table_like_evidence_count": sum(1 for row in pdf_rows if row.get("table_like_evidence")),
        "bbox_present_count": sum(1 for row in pdf_rows if row.get("bbox_present")),
        "bbox_missing_count": sum(1 for row in pdf_rows if not row.get("bbox_present")),
        "top_k_native_pdf_text_candidate_count": sum(
            int((row.get("evidence_lane_counts") or {}).get("native_pdf_text", 0)) for row in pdf_rows
        ),
        "top_k_ocr_fallback_candidate_count": sum(
            int((row.get("evidence_lane_counts") or {}).get("ocr_fallback_metadata", 0)) for row in pdf_rows
        ),
        "top_k_page_only_candidate_count": sum(
            int((row.get("evidence_lane_counts") or {}).get("page_only", 0)) for row in pdf_rows
        ),
        "top_k_table_like_candidate_count": sum(
            int((row.get("evidence_lane_counts") or {}).get("table_like", 0)) for row in pdf_rows
        ),
        "top_k_bbox_present_candidate_count": sum(
            int((row.get("evidence_lane_counts") or {}).get("bbox_present", 0)) for row in pdf_rows
        ),
        "top_k_bbox_missing_candidate_count": sum(
            int((row.get("evidence_lane_counts") or {}).get("bbox_missing", 0)) for row in pdf_rows
        ),
    }


def pdf_sampling_summary(pdf_report: Mapping[str, Any], sampled_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    source_rows = [row for row in list(pdf_report.get("query_results") or []) if isinstance(row, Mapping)]
    source_counts = dict(sorted(Counter(clean(row.get("bucket")) or "unknown" for row in source_rows).items()))
    sampled_counts = dict(sorted(Counter(clean(row.get("bucket")) or "unknown" for row in sampled_results).items()))
    return {
        "source_pdf_row_count": len(source_rows),
        "sampled_pdf_row_count": len(sampled_results),
        "source_pdf_bucket_counts": source_counts,
        "sampled_pdf_bucket_counts": sampled_counts,
        "table_lane_sampled": sampled_counts.get("pdf_table_lookup", 0) > 0,
        "page_lane_sampled": sampled_counts.get("pdf_page_lookup", 0) > 0,
        "content_lane_sampled": any(
            sampled_counts.get(bucket, 0) > 0
            for bucket in ("pdf_section_question", "pdf_table_lookup", "pdf_ocr_noise")
        ),
    }


def retry_summary(loop_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "case_count": len(loop_rows),
        "retry_exhausted_count": sum(1 for row in loop_rows if row.get("retry_exhausted")),
        "max_attempt_count": max((int(row.get("attempt_count") or 0) for row in loop_rows), default=0),
        "allow_unscoped_true_count": sum(1 for row in loop_rows if bool(row.get("allowUnscoped"))),
    }


def status_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(clean(row.get("route_status")) for row in rows).items()))


def failure_category_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        categories = list(row.get("failure_categories") or [])
        if not categories:
            counter["none"] += 1
        for category in categories:
            counter[clean(category)] += 1
    return dict(sorted(counter.items()))


def route_status(*, file_type: str, failures: Sequence[str]) -> str:
    if failures:
        return STATUS_FAIL
    if clean(file_type).upper() == "PDF":
        return STATUS_REVIEW_REQUIRED
    if clean(file_type).upper() == "XLSX":
        return STATUS_PASS
    return STATUS_DIAGNOSTIC_ONLY


def diagnostic_only_reason(*, file_type: str, status: str) -> str:
    if clean(file_type).upper() == "PDF":
        return "pdf_policy_review_lane_answer_denominator_zero"
    if clean(file_type).upper() == "XLSX":
        return "xlsx_retrieval_evidence_only_answer_denominator_zero"
    return "route_out_of_scope_for_xlsx_pdf_diagnostic"


def evidence_source_for_hit(hit: Mapping[str, Any] | None, *, file_type: str) -> str:
    if not hit:
        return "no_evidence"
    if clean(file_type).upper() == "XLSX":
        return "xlsx_wrapper"
    if clean(file_type).upper() == "PDF":
        return "ocr_fallback_metadata" if ocr_used(hit) else "native_pdf_text"
    return "content_lookup"


def evidence_lane_counts(query_result: Mapping[str, Any], *, file_type: str) -> dict[str, int]:
    hits = [hit for hit in list(query_result.get("top_k_results") or []) if isinstance(hit, Mapping)]
    if clean(file_type).upper() != "PDF":
        return {
            "xlsx_wrapper": len(hits),
            "content_lookup": len(hits),
        }
    counts = Counter()
    for hit in hits:
        if ocr_used(hit):
            counts["ocr_fallback_metadata"] += 1
        else:
            counts["native_pdf_text"] += 1
        if is_page_only(hit):
            counts["page_only"] += 1
        if is_table_like(hit):
            counts["table_like"] += 1
        if bbox_present(hit):
            counts["bbox_present"] += 1
        else:
            counts["bbox_missing"] += 1
        actual_type = clean(hit.get("effective_source_file_type") or hit.get("source_file_type")).upper()
        location = hit.get("location_json")
        location_type = clean(location.get("type")).lower() if isinstance(location, Mapping) else ""
        if actual_type == "PDF" or location_type == "pdf":
            counts["content_lookup"] += 1
    return dict(sorted(counts.items()))


def lookup_route_for_actual_route(route: str) -> str:
    if route == ROUTE_PDF_FILE:
        return "file_lookup"
    if route == ROUTE_PDF_CONTENT:
        return "content_lookup"
    if route == ROUTE_XLSX_WRAPPER:
        return "xlsx_wrapper"
    return "not_applicable"


def source_report_guardrail_failures(source_reports: Sequence[Path]) -> list[str]:
    failures: list[str] = []
    for path in source_reports:
        resolved = resolve_path(path)
        label = display_path(resolved)
        if not resolved.exists():
            failures.append(f"source_report_missing:{label}")
            continue
        try:
            report = read_json(resolved)
        except Exception:
            failures.append(f"source_report_unreadable:{label}")
            continue
        if report.get("promotion_evidence") is True:
            failures.append(f"source_report_promotion_evidence_true:{label}")
        evidence_role = report.get("evidence_role")
        if evidence_role not in (None, "diagnostic"):
            failures.append(f"source_report_evidence_role_not_diagnostic:{label}")
        if report.get("allowUnscoped") is True:
            failures.append(f"source_report_allowUnscoped_true:{label}")
    return failures


def location_valid(location: Any, *, file_type: str) -> bool:
    if not isinstance(location, Mapping):
        return False
    file_type_upper = clean(file_type).upper()
    if file_type_upper == "PDF":
        return any(location.get(key) not in (None, "") for key in ("page", "page_no", "pageNo", "physical_page_index"))
    if file_type_upper == "XLSX":
        has_sheet = any(location.get(key) not in (None, "") for key in ("sheet_name", "sheetName"))
        has_range = any(location.get(key) not in (None, "") for key in ("cell_range", "cellRange", "range", "usedRange", "table_id", "tableId"))
        return has_sheet and has_range
    return False


def document_version_id(hit: Mapping[str, Any] | None) -> str:
    if not isinstance(hit, Mapping):
        return UNKNOWN
    direct = hit.get("document_version_id") or hit.get("documentVersionId")
    if direct not in (None, ""):
        return str(direct)
    location = hit.get("location_json")
    if isinstance(location, Mapping):
        value = location.get("document_version_id") or location.get("documentVersionId")
        if value not in (None, ""):
            return str(value)
    return UNKNOWN


def hit_value(hit: Mapping[str, Any] | None, key: str) -> str:
    if not isinstance(hit, Mapping):
        return UNKNOWN
    value = hit.get(key)
    if value in (None, ""):
        return UNKNOWN
    return str(value)


def presence(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return value not in (None, "")


def exposed_presence(hit: Mapping[str, Any] | None, key: str) -> bool | str:
    if not isinstance(hit, Mapping) or key not in hit:
        return UNKNOWN
    return presence(hit.get(key))


def ocr_used(hit: Mapping[str, Any] | None) -> bool:
    if not isinstance(hit, Mapping):
        return False
    location = hit.get("location_json")
    if isinstance(location, Mapping):
        return bool(location.get("ocr_used") or location.get("ocrUsed"))
    return False


def is_page_only(hit: Mapping[str, Any] | None) -> bool:
    if not isinstance(hit, Mapping):
        return False
    chunk_type = clean(hit.get("chunk_type")).lower()
    location = hit.get("location_json") if isinstance(hit.get("location_json"), Mapping) else {}
    block_type = clean(location.get("block_type")).lower() if isinstance(location, Mapping) else ""
    return chunk_type == "page" or block_type == "page"


def is_table_like(hit: Mapping[str, Any] | None) -> bool:
    if not isinstance(hit, Mapping):
        return False
    chunk_type = clean(hit.get("chunk_type")).lower()
    location = hit.get("location_json") if isinstance(hit.get("location_json"), Mapping) else {}
    block_type = clean(location.get("block_type")).lower() if isinstance(location, Mapping) else ""
    return "table" in chunk_type or "table" in block_type


def bbox_present(hit: Mapping[str, Any] | None) -> bool:
    if not isinstance(hit, Mapping):
        return False
    location = hit.get("location_json")
    if isinstance(location, Mapping):
        bbox = location.get("bbox") or location.get("bounding_box") or location.get("boundingBox")
        return bool(bbox)
    return False


def pdf_match_value(hit: Mapping[str, Any] | None, key: str) -> bool | str:
    if not isinstance(hit, Mapping):
        return UNKNOWN
    breakdown = hit.get("match_breakdown")
    if not isinstance(breakdown, Mapping) or key not in breakdown:
        return UNKNOWN
    return bool(breakdown.get(key))


def actual_page_no(hit: Mapping[str, Any] | None) -> str:
    if not isinstance(hit, Mapping):
        return UNKNOWN
    location = hit.get("location_json")
    if isinstance(location, Mapping):
        for key in ("page_no", "pageNo", "page", "physical_page_index"):
            if location.get(key) not in (None, ""):
                return str(location.get(key))
    return UNKNOWN


def actual_bbox(hit: Mapping[str, Any] | None) -> Any:
    if not isinstance(hit, Mapping):
        return UNKNOWN
    location = hit.get("location_json")
    if isinstance(location, Mapping):
        for key in ("bbox", "bounding_box", "boundingBox"):
            if location.get(key) not in (None, ""):
                return location.get(key)
    return UNKNOWN


def pdf_policy_status(query_result: Mapping[str, Any], *, policy: str) -> str:
    if not is_pdf_query_result(query_result):
        return "NOT_APPLICABLE"
    failure = clean(query_result.get("failure_reason"))
    if policy == "bbox" and (clean(query_result.get("expected_bbox")) or failure == "bbox_mismatch"):
        return STATUS_REVIEW_REQUIRED
    if policy == "page" and (clean(query_result.get("expected_page_no")) or clean(query_result.get("expected_physical_page_index"))):
        return STATUS_REVIEW_REQUIRED
    return STATUS_DIAGNOSTIC_ONLY


def is_pdf_query_result(query_result: Mapping[str, Any]) -> bool:
    bucket = clean(query_result.get("bucket")).lower()
    location_type = clean(query_result.get("expected_location_type")).lower()
    return bucket.startswith("pdf_") or location_type in {"pdf", "ocr"}


def pdf_lane_exposure_status(hit: Mapping[str, Any] | None, *, file_type: str) -> str:
    if clean(file_type).upper() != "PDF":
        return "NOT_APPLICABLE"
    if not isinstance(hit, Mapping):
        return UNKNOWN
    location = hit.get("location_json")
    if isinstance(location, Mapping):
        return "DERIVED_FROM_LOCATION_JSON"
    return UNKNOWN


def first_failure(failures: Sequence[str]) -> str | None:
    return clean(failures[0]) if failures else None


def route_tool_name(route: str) -> str:
    if route == ROUTE_XLSX_WRAPPER:
        return "xlsx_strict_wrapper_candidate_retriever"
    if route == ROUTE_PDF_FILE:
        return "pdf_file_lookup_diagnostic_retriever"
    if route == ROUTE_PDF_CONTENT:
        return "pdf_content_lookup_diagnostic_retriever"
    return "diagnostic_route_retriever"


def next_retry_route(current_route: str, row: Mapping[str, Any]) -> str:
    if row.get("file_type") == "PDF":
        if current_route == ROUTE_PDF_FILE:
            return ROUTE_PDF_CONTENT
        if current_route == ROUTE_PDF_CONTENT:
            return ROUTE_PDF_FILE
    return current_route


def clean(value: Any) -> str:
    return str(value or "").strip()


def dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = clean(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def render_markdown(payload: Mapping[str, Any]) -> str:
    title = payload.get("report_role", "xlsx_pdf_route_diagnostic")
    route_counts = payload.get("route_counts") or {}
    failure_counts = payload.get("failure_category_counts") or {}
    commands = payload.get("commands") or {}
    lines = [
        f"# {title}",
        "",
        f"- Status: `{payload.get('status')}`",
        "- Promotion evidence: `false`",
        f"- Official denominator changed: `{str(payload.get('official_denominator_changed')).lower()}`",
        "- XLSX answer denominator: `0`",
        "- PDF answer denominator: `0`",
        "- Retrieval execution: `" + clean(payload.get("retrieval_execution")) + "`",
        "- Broad candidate indexing: `not_run_by_this_script`",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in sorted(route_counts.items()):
        lines.append(f"| route_status.{key} | {value} |")
    for key, value in sorted(failure_counts.items()):
        lines.append(f"| failure.{key} | {value} |")
    lines.extend(
        [
            "",
            "## XLSX Leakage Probe",
            "",
            "```json",
            json.dumps(payload.get("xlsx_leakage_probe") or {}, ensure_ascii=False, indent=2),
            "```",
            "",
            "## PDF Route Summary",
            "",
            "```json",
            json.dumps(
                {
                    "file_vs_content": payload.get("pdf_file_vs_content_routing") or {},
                    "native_ocr": payload.get("pdf_native_ocr_routing") or {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "## PDF Sampling",
            "",
            "```json",
            json.dumps(payload.get("pdf_sampling") or {}, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Denominator Registry Diff",
            "",
            "```json",
            json.dumps(payload.get("official_denominator_registry_diff") or {}, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    if payload.get("agentic_retry_summary") is not None:
        lines.extend(
            [
                "## Agentic Retry Summary",
                "",
                "```json",
                json.dumps(payload.get("agentic_retry_summary") or {}, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Commands",
            "",
        ]
    )
    for key, value in commands.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Conservative Assumptions",
            "",
        ]
    )
    for assumption in payload.get("conservative_assumptions") or []:
        lines.append(f"- {assumption}")
    lines.append("")
    return "\n".join(lines)
