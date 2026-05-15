"""Generate PDF answer/citation diagnostic review input.

The generator consumes only strict-ready PDF CONTENT evidence rows from the
latest PDF evidence readiness repair report. Answer drafts are deterministic
and evidence-derived; no external API, official denominator, production index,
candidate artifact, immutable baseline, or gold registry is opened.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"

DEFAULT_READINESS_REPORT = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_OUTPUT_JSONL = REPORT_DIR / "pdf_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_REPORT_JSON = REPORT_DIR / "pdf_answer_citation_diagnostic_report.json"
DEFAULT_REPORT_MD = REPORT_DIR / "pdf_answer_citation_diagnostic_report.md"

SCHEMA_VERSION = "pdf_answer_citation_diagnostic_report_v1"
ROW_SCHEMA_VERSION = "pdf_answer_citation_diagnostic_review_input_v1"
TRACK = "pdf_business_ocr_mm"
PDF_CONTENT_EVIDENCE = "pdf_content_evidence"
PDF_FILE_IDENTITY = "pdf_file_identity"
DISALLOWED_BBOX_SOURCES = {"generated_estimate", "full_page_fallback"}
DISALLOWED_LAYOUT_METHODS = {"generated_bbox_estimate", "full_page_fallback_bbox"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_generation(
        readiness_report=Path(args.readiness_report),
        output_jsonl=Path(args.output_jsonl),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "review_input": report["artifact_paths"]["review_input_jsonl"],
                "generated_answer_rows": report["generated_answer_rows"],
                "clean_pass_rows": report["clean_pass_rows"],
                "official_metric_input_rows": report["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] != "FAILED_GUARDRAIL" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-report", default=str(DEFAULT_READINESS_REPORT))
    parser.add_argument("--output-jsonl", default=str(DEFAULT_OUTPUT_JSONL))
    parser.add_argument("--output-report", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_REPORT_MD))
    return parser.parse_args(argv)


def run_generation(
    *,
    readiness_report: Path,
    output_jsonl: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    report, rows = build_report_and_rows(readiness_report=readiness_report)
    report["artifact_paths"]["review_input_jsonl"] = repo_relative(output_jsonl)
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    if report["validation"]["ok"]:
        write_jsonl(output_jsonl, rows)
        report["artifact_paths"]["review_input_jsonl_written"] = True
        report["artifact_paths"]["review_input_jsonl_sha256"] = sha256_file(output_jsonl)
    else:
        report["artifact_paths"]["review_input_jsonl_written"] = False
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_report_and_rows(*, readiness_report: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = read_json(readiness_report)
    source_rows = source.get("repair_rows") if isinstance(source.get("repair_rows"), list) else []
    included_rows: list[dict[str, Any]] = []
    excluded: dict[str, list[str]] = {
        "diagnostic_fallback": [],
        "file_identity_lane": [],
        "policy_excluded_or_identity_blocked": [],
    }
    for row in source_rows:
        if not isinstance(row, Mapping):
            continue
        reason = exclusion_reason(row)
        query_id = clean(row.get("query_id"))
        if reason:
            excluded[reason].append(query_id)
            continue
        included_rows.append(build_review_row(row))

    validation_errors = validation_errors_for(source=source, review_rows=included_rows)
    bucket_counts = count_buckets(included_rows)
    status = "PASS" if not validation_errors else "FAILED_GUARDRAIL"
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "pdf_answer_citation_diagnostic_review_input",
        "track": TRACK,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "diagnostic_answer_generation_run": True,
        "answer_generation_scope": "diagnostic_only",
        "model_assisted_diagnostic_only": False,
        "local_llm_run": False,
        "external_api_used": False,
        "pdf_answer_generation_denominator_opened": False,
        "input_rows": len(source_rows),
        "strict_ready_rows": len(included_rows),
        "generated_answer_rows": len(included_rows),
        "answer_support_pass_count": sum(1 for row in included_rows if row["answer_claims_supported"] is True),
        "citation_locator_valid_count": sum(1 for row in included_rows if row["citation_locator_valid"] is True),
        "clean_pass_rows": bucket_counts["clean_pass"],
        "cleanup_rows": sum(
            bucket_counts[key]
            for key in (
                "cleanup_required",
                "answer_rewrite_required",
                "citation_locator_incomplete",
                "unsupported_answer",
            )
        ),
        "unresolved_rows": bucket_counts["unresolved_diagnostic"],
        "lane_policy_blocked_rows": bucket_counts["lane_policy_blocked"],
        "answer_rewrite_required_rows": bucket_counts["answer_rewrite_required"],
        "citation_locator_incomplete_rows": bucket_counts["citation_locator_incomplete"],
        "unsupported_answer_rows": bucket_counts["unsupported_answer"],
        "official_metric_input_rows": sum(1 for row in included_rows if row.get("official_metric_input") is not False),
        "excluded_query_ids": excluded,
        "bucket_counts": bucket_counts,
        "guardrails": {
            "official_metric_input_rows_remain_zero": True,
            "official_denominator_registry_opened": False,
            "official_denominator_registry_mutation": False,
            "gold_registry_mutation": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_index_mutation": False,
            "production_vector_written": False,
            "promotion_evidence_created": False,
            "model_assisted_outputs_promoted_to_gold": False,
            "content_file_identity_lane_merge": False,
            "filename_only_identity_accepted": False,
        },
        "lane_guard": {
            "content_file_identity_lane_merge": False,
            "file_identity_rows_used_as_content_evidence": False,
            "filename_only_identity_accepted": False,
            "policy_excluded_rows_used": False,
            "diagnostic_fallback_rows_used": False,
        },
        "source_artifacts": {
            "readiness_report": file_identity(readiness_report),
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
    }
    return report, included_rows


def exclusion_reason(row: Mapping[str, Any]) -> str:
    if row.get("strict_ready") is not True or "diagnostic_only_fallback" in set(row.get("blocker_classifications") or []):
        return "diagnostic_fallback"
    if clean(row.get("content_evidence_lane")) != PDF_CONTENT_EVIDENCE:
        return "file_identity_lane"
    file_lane = row.get("file_identity_lane") if isinstance(row.get("file_identity_lane"), Mapping) else {}
    if (
        file_lane.get("filename_only_identity_accepted") is True
        or row.get("policy_excluded") is True
        or row.get("not_answerable") is True
        or not clean(row.get("source_file_id"))
        or not clean(row.get("stable_source_identity") or row.get("document_version_id"))
        or not clean(row.get("extracted_artifact_id"))
    ):
        return "policy_excluded_or_identity_blocked"
    return ""


def build_review_row(row: Mapping[str, Any]) -> dict[str, Any]:
    answer = clean(row.get("diagnostic_answer_override") or deterministic_answer(row))
    claims = [answer] if answer else []
    support_text = normalize_text(" ".join([clean(row.get("matched_text")), *list_value(row.get("nearby_paragraphs"))]))
    claims_supported = bool(claims) and all(normalize_text(claim) in support_text for claim in claims)
    locator_valid = citation_locator_valid(row)
    lane_ok = lane_checks_pass(row)
    citation_matches = locator_valid and citation_text_matches_source_bound_evidence(row)
    if not lane_ok:
        bucket = "lane_policy_blocked"
    elif not answer:
        bucket = "unresolved_diagnostic"
    elif not locator_valid:
        bucket = "citation_locator_incomplete"
    elif not claims_supported:
        bucket = "unsupported_answer"
    elif citation_matches:
        bucket = "clean_pass"
    else:
        bucket = "cleanup_required"
    return {
        "schema_version": ROW_SCHEMA_VERSION,
        "query_id": clean(row.get("query_id")),
        "track": TRACK,
        "generated_answer": answer,
        "diagnostic_answer": answer,
        "answer_claims": claims,
        "citation_items": [
            {
                "citation_text": clean(row.get("citation_text")),
                "citation_locator": row.get("citation_locator"),
                "search_unit_id": clean(row.get("search_unit_id")),
            }
        ],
        "source_file_id": clean(row.get("source_file_id")),
        "document_version_id": clean(row.get("document_version_id")),
        "stable_source_identity": clean(row.get("stable_source_identity") or row.get("document_version_id")),
        "extracted_artifact_id": clean(row.get("extracted_artifact_id")),
        "search_unit_id": clean(row.get("search_unit_id")),
        "search_unit_rank": int_or_none(row.get("search_unit_rank")),
        "retrieval_rank": int_or_none(row.get("retrieval_rank")),
        "parser_version": clean(row.get("parser_version")),
        "page": int_or_none(row.get("page")),
        "physical_page_index": int_or_none(row.get("physical_page_index")),
        "bbox": row.get("bbox") if isinstance(row.get("bbox"), list) else [],
        "bbox_source": clean(row.get("bbox_source")),
        "region_type": clean(row.get("region_type")),
        "matched_text": clean(row.get("matched_text")),
        "citation_text": clean(row.get("citation_text")),
        "citation_locator": row.get("citation_locator"),
        "section_heading": clean(row.get("section_heading")),
        "table_caption_footnote": clean(row.get("table_caption_footnote")),
        "nearby_paragraphs": list_value(row.get("nearby_paragraphs")),
        "native_text_available": row.get("native_text_available") is True,
        "OCR_confidence": row.get("OCR_confidence"),
        "OCR_fallback_used": row.get("OCR_fallback_used") is True,
        "content_evidence_lane": clean(row.get("content_evidence_lane")),
        "file_identity_lane": row.get("file_identity_lane"),
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "answer_supported_by_matched_text_or_nearby_paragraph": claims_supported,
        "answer_claims_supported": claims_supported,
        "citation_locator_valid": locator_valid,
        "citation_locator_has_page_bbox_region_search_unit": citation_locator_has_required_fields(row),
        "citation_text_matches_source_bound_evidence": citation_matches,
        "no_file_identity_lane_used_as_content_evidence": clean(row.get("content_evidence_lane")) == PDF_CONTENT_EVIDENCE,
        "no_filename_only_identity_acceptance": not filename_only_identity_accepted(row),
        "no_policy_excluded_row_used": row.get("policy_excluded") is not True,
        "no_diagnostic_fallback_row_used": row.get("strict_ready") is True,
        "bucket": bucket,
    }


def deterministic_answer(row: Mapping[str, Any]) -> str:
    return clean(row.get("matched_text"))


def citation_locator_valid(row: Mapping[str, Any]) -> bool:
    return (
        citation_locator_has_required_fields(row)
        and row.get("source_bound_bbox") is True
        and clean(row.get("bbox_source")) not in DISALLOWED_BBOX_SOURCES
        and clean(row.get("layout_resolution_method")) not in DISALLOWED_LAYOUT_METHODS
    )


def citation_locator_has_required_fields(row: Mapping[str, Any]) -> bool:
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    return (
        nonempty(locator.get("page"))
        and nonempty(locator.get("bbox"))
        and bool(clean(locator.get("region_type")))
        and bool(clean(locator.get("search_unit_id")))
    )


def citation_text_matches_source_bound_evidence(row: Mapping[str, Any]) -> bool:
    citation_text = clean(row.get("citation_text"))
    if not citation_text:
        return False
    source_text = normalize_text(" ".join([clean(row.get("matched_text")), *list_value(row.get("nearby_paragraphs"))]))
    normalized_citation = normalize_text(citation_text)
    if source_text and (normalized_citation in source_text or source_text in normalized_citation):
        return True

    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    page = clean(locator.get("page"))
    bbox = locator.get("bbox") if isinstance(locator.get("bbox"), list) else []
    if not page or not bbox:
        return False
    bbox_tokens = [clean(value) for value in bbox]
    compact_citation = normalize_text(citation_text)
    page_matches = f"p.{page}" in compact_citation or f"page{page}" in compact_citation
    return page_matches and all(token and token in compact_citation for token in bbox_tokens)


def lane_checks_pass(row: Mapping[str, Any]) -> bool:
    return (
        clean(row.get("content_evidence_lane")) == PDF_CONTENT_EVIDENCE
        and not filename_only_identity_accepted(row)
        and row.get("policy_excluded") is not True
        and row.get("strict_ready") is True
    )


def filename_only_identity_accepted(row: Mapping[str, Any]) -> bool:
    file_lane = row.get("file_identity_lane") if isinstance(row.get("file_identity_lane"), Mapping) else {}
    return file_lane.get("filename_only_identity_accepted") is True or row.get("filename_only_identity_accepted") is True


def count_buckets(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    buckets = {
        "clean_pass": 0,
        "cleanup_required": 0,
        "answer_rewrite_required": 0,
        "citation_locator_incomplete": 0,
        "unsupported_answer": 0,
        "lane_policy_blocked": 0,
        "unresolved_diagnostic": 0,
    }
    for row in rows:
        bucket = clean(row.get("bucket"))
        if bucket in buckets:
            buckets[bucket] += 1
    return buckets


def validation_errors_for(*, source: Mapping[str, Any], review_rows: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    if source.get("official_metric") is True:
        errors.append("pdf source report must keep official_metric=false")
    if source.get("promotion_evidence") is True:
        errors.append("pdf source report must keep promotion_evidence=false")
    if int_value(source.get("official_metric_input_rows")) != 0:
        errors.append("source official_metric_input_rows must remain 0")
    if sum(1 for row in review_rows if row.get("official_metric_input") is not False) != 0:
        errors.append("official_metric_input_rows must remain 0")
    lane = source.get("lane_separation") if isinstance(source.get("lane_separation"), Mapping) else {}
    if lane.get("content_and_file_identity_aggregated") is True:
        errors.append("pdf content and file identity lanes must remain separate")
    guardrails = source.get("guardrails") if isinstance(source.get("guardrails"), Mapping) else {}
    for key in (
        "official_denominator_registry_opened",
        "official_denominator_registry_mutation",
        "gold_registry_mutation",
        "candidate_artifact_mutation",
        "immutable_baseline_mutation",
        "production_namespace_vector_index_mutation",
        "production_vector_index_mutation",
        "production_vector_written",
    ):
        if source.get(key) is True or guardrails.get(key) is True:
            errors.append(f"pdf source guardrail violation: {key}=true")
    return errors


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# PDF Answer/Citation Diagnostic Report",
        "",
        f"- Status: `{report['status']}`",
        "- Scope: diagnostic-only PDF answer/citation review input.",
        f"- Input rows: `{report['input_rows']}`",
        f"- Strict-ready rows: `{report['strict_ready_rows']}`",
        f"- Generated answer rows: `{report['generated_answer_rows']}`",
        f"- Answer support pass: `{report['answer_support_pass_count']}`",
        f"- Citation locator valid: `{report['citation_locator_valid_count']}`",
        f"- Clean pass rows: `{report['clean_pass_rows']}`",
        f"- Cleanup rows: `{report['cleanup_rows']}`",
        f"- Unresolved rows: `{report['unresolved_rows']}`",
        f"- Lane policy blocked rows: `{report['lane_policy_blocked_rows']}`",
        f"- Official metric input rows: `{report['official_metric_input_rows']}`",
        f"- PDF answer generation denominator opened: `{str(report['pdf_answer_generation_denominator_opened']).lower()}`",
        "",
        "## Buckets",
        "",
    ]
    for bucket, count in report["bucket_counts"].items():
        lines.append(f"- `{bucket}`: `{count}`")
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() else None,
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def int_value(value: Any) -> int:
    parsed = int_or_none(value)
    return parsed if parsed is not None else 0


def list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    return []


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return True


def clean(value: Any) -> str:
    return str(value or "").strip()


def normalize_text(value: Any) -> str:
    return "".join(clean(value).split())


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
