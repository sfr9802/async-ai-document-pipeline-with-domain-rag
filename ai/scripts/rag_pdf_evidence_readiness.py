"""Build a diagnostic-only PDF evidence readiness artifact.

This does not generate PDF answers and does not rerun retrieval. It projects the
current PDF strict gate inputs into row-level readiness records so missing
SearchUnit/layout/OCR/citation-locator metadata is explicit before any future
strict gate rerun.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"

DEFAULT_PDF_STRICT_REPORT = REPORT_DIR / "pdf_strict_silver_generation_report.json"
DEFAULT_PDF_GOLD_CSV = EVAL_QUERY_DIR / "gold_queries_pdf_v0.csv"
DEFAULT_OUTPUT_JSONL = REPORT_DIR / "pdf_evidence_readiness_rows.jsonl"
DEFAULT_REPORT_JSON = REPORT_DIR / "pdf_evidence_readiness_report.json"
DEFAULT_REPORT_MD = REPORT_DIR / "pdf_evidence_readiness_report.md"
DEFAULT_STRICT_INPUT_IDS = (
    "gq_pdf_page_lookup_001",
    "gq_pdf_section_question_001",
    "gq_auto_010",
    "gq_auto_015",
    "gq_auto_024",
    "gq_auto_029",
    "gq_auto_030",
)
DEFAULT_STABLE_IDENTITY_REQUIRED_IDS = (
    "pdf_file_lookup_content_anchor_017",
    "pdf_file_lookup_content_anchor_018",
    "pdf_file_lookup_content_anchor_020",
)

SCHEMA_VERSION = "pdf_evidence_readiness_row_v1"
REPORT_SCHEMA_VERSION = "pdf_evidence_readiness_report_v1"
TRACK = "pdf_business_ocr_mm"
PDF_CONTENT_EVIDENCE = "pdf_content_evidence"
PDF_FILE_IDENTITY = "pdf_file_identity"
STABLE_IDENTITY_REQUIRED = "stable_identity_required"
STRICT_REQUIRED_FIELDS = (
    "file",
    "document_version_id",
    "page",
    "bbox",
    "region_type",
    "matched_text",
    "section_heading",
    "table_caption_footnote",
    "nearby_paragraphs",
    "OCR_confidence",
    "source_searchunit_id",
    "source_searchunit_rank",
    "parser_source_metadata",
    "citation_locator",
)
PROTECTED_SOURCE_GUARDRAILS = (
    "official_denominator_registry_changed",
    "official_denominator_opened_or_frozen",
    "promotion_evidence_created",
    "pdf_answer_generation_denominator_opened",
    "pdf_content_file_lanes_aggregated",
    "production_namespace_mutated",
    "production_vector_index_mutated",
    "production_vector_written",
    "candidate_artifact_mutated",
    "immutable_baseline_mutated",
    "answer_generation_run",
    "diagnostic_only_row_promoted",
    "repo_local_pdf_silver_manifest_written",
    "route_fallback_labels_promoted_to_official_metrics",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_readiness(
        pdf_strict_report=Path(args.pdf_strict_report),
        pdf_gold_csv=Path(args.pdf_gold_csv),
        output_jsonl=Path(args.output_jsonl),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "rows": report["artifact_paths"]["readiness_rows_jsonl"],
                "strict_gate_readiness_count": report["counts"]["strict_gate_readiness_count"],
                "rows_blocked_by_missing_layout": report["counts"]["rows_blocked_by_missing_layout"],
                "rows_blocked_by_file_identity_ambiguity": report["counts"]["rows_blocked_by_file_identity_ambiguity"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] in {"READY_FOR_STRICT_GATE_RERUN", "DIAGNOSTIC_ONLY_BLOCKED"} else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-strict-report", default=str(DEFAULT_PDF_STRICT_REPORT))
    parser.add_argument("--pdf-gold-csv", default=str(DEFAULT_PDF_GOLD_CSV))
    parser.add_argument("--output-jsonl", default=str(DEFAULT_OUTPUT_JSONL))
    parser.add_argument("--output-report", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_REPORT_MD))
    return parser.parse_args(argv)


def run_readiness(
    *,
    pdf_strict_report: Path,
    pdf_gold_csv: Path,
    output_jsonl: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    report, rows = build_report_and_rows(pdf_strict_report=pdf_strict_report, pdf_gold_csv=pdf_gold_csv)
    write_jsonl(output_jsonl, rows)
    report["artifact_paths"]["readiness_rows_jsonl"] = repo_relative(output_jsonl)
    report["artifact_paths"]["readiness_rows_jsonl_sha256"] = sha256_file(output_jsonl)
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_report(*, pdf_strict_report: Path, pdf_gold_csv: Path) -> dict[str, Any]:
    report, _rows = build_report_and_rows(pdf_strict_report=pdf_strict_report, pdf_gold_csv=pdf_gold_csv)
    return report


def build_report_and_rows(*, pdf_strict_report: Path, pdf_gold_csv: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    strict_report_exists = pdf_strict_report.exists()
    strict_payload = read_json(pdf_strict_report) if strict_report_exists else {}
    gold_rows = {clean(row.get("query_id")): row for row in read_csv_rows(pdf_gold_csv) if clean(row.get("query_id"))}
    if not strict_payload:
        strict_payload = synthesize_strict_payload_from_gold(pdf_gold_csv=pdf_gold_csv, gold_query_ids=list(gold_rows))
    input_ids = [clean(query_id) for query_id in strict_payload.get("input_denominator_query_ids", []) if clean(query_id)]
    rows = [
        readiness_row_from_gold(query_id=query_id, gold_row=gold_rows.get(query_id, {}))
        for query_id in input_ids
    ]
    stable_identity_ids = sorted(
        strict_payload.get("excluded_query_ids", {}).get("stable_identity_required", [])
        if isinstance(strict_payload.get("excluded_query_ids"), Mapping)
        else []
    )
    source_guardrails = source_guardrail_summary(strict_payload)
    counts = readiness_counts(rows, stable_identity_ids)
    status = "READY_FOR_STRICT_GATE_RERUN" if counts["strict_gate_readiness_count"] else "DIAGNOSTIC_ONLY_BLOCKED"
    validation_errors = validation_errors_for(source_guardrails=source_guardrails, rows=rows)
    if validation_errors:
        status = "FAILED_GUARDRAIL"
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "pdf_evidence_readiness_diagnostic",
        "track": TRACK,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "answer_generation_run": False,
        "retrieval_run": False,
        "source_artifacts": {
            "pdf_strict_report": file_identity(pdf_strict_report),
            "pdf_strict_report_fallback_used": not strict_report_exists,
            "pdf_gold_csv": file_identity(pdf_gold_csv),
        },
        "counts": counts,
        "missing_field_diagnosis": missing_field_diagnosis(rows),
        "input_query_ids": input_ids,
        "readiness_rows_preview": rows[:5],
        "lane_separation": {
            PDF_CONTENT_EVIDENCE: {
                "row_count": len(rows),
                "strict_gate_readiness_count": counts["strict_gate_readiness_count"],
            },
            PDF_FILE_IDENTITY: {
                "blocked_by_stable_identity_required": len(stable_identity_ids),
                "stable_identity_required_query_ids": stable_identity_ids,
            },
            "content_and_file_identity_aggregated": False,
        },
        "file_identity_policy": {
            "generic_filename_only_identity_blocked": True,
            "blocker": STABLE_IDENTITY_REQUIRED,
            "blocked_query_ids": stable_identity_ids,
        },
        "source_guardrails": source_guardrails,
        "strict_gate_rerun": {
            "rerun_performed": False,
            "reason": (
                "strict_gate_readiness_count=0; source SearchUnit, parser metadata, OCR confidence, "
                "nearby paragraphs, or layout metadata remains incomplete"
            )
            if counts["strict_gate_readiness_count"] == 0
            else "readiness artifact is sufficient for a separate strict gate rerun",
        },
        "guardrails": {
            **source_guardrails,
            "pdf_answer_generation_opened": bool(source_guardrails.get("answer_generation_run")),
        },
        "artifact_paths": {
            "readiness_rows_jsonl": "",
            "readiness_rows_jsonl_sha256": None,
            "report_json": "",
            "report_md": "",
        },
        "validation": {
            "ok": not validation_errors,
            "errors": validation_errors,
        },
        "notes": [
            "Current PDF strict rows are content-evidence diagnostics, not answer-generation inputs.",
            "Missing SearchUnit id/rank, parser metadata, nearby paragraphs, and OCR confidence keep rows diagnostic-only.",
            "PDF file-identity rows remain separate and generic filename-only identity stays blocked.",
        ],
    }
    return report, rows


def readiness_row_from_gold(*, query_id: str, gold_row: Mapping[str, str]) -> dict[str, Any]:
    citation_metadata = {
        "file": clean(gold_row.get("expected_file_name")),
        "document_version_id": clean(gold_row.get("expected_document_version_id")),
        "page": int_or_none(gold_row.get("expected_page_no")),
        "physical_page_index": int_or_none(gold_row.get("expected_physical_page_index")),
        "bbox": parse_bbox(gold_row.get("expected_bbox")),
        "region_type": clean(gold_row.get("expected_chunk_type")),
        "matched_text": clean(gold_row.get("expected_answer_text") or gold_row.get("must_contain_terms")),
        "section_heading": "",
        "table_caption_footnote": "",
        "nearby_paragraphs": [],
        "OCR_confidence": None,
        "OCR_confidence_status": "missing",
        "source_searchunit_id": "",
        "source_searchunit_rank": None,
        "parser_source_metadata": {},
    }
    citation_locator = {
        "file": citation_metadata["file"],
        "document_version_id": citation_metadata["document_version_id"],
        "page": citation_metadata["page"],
        "physical_page_index": citation_metadata["physical_page_index"],
        "bbox": citation_metadata["bbox"],
        "region_type": citation_metadata["region_type"],
        "search_unit_id": citation_metadata["source_searchunit_id"],
    }
    citation_metadata["citation_locator"] = citation_locator
    missing = [field for field in STRICT_REQUIRED_FIELDS if not nonempty(citation_metadata.get(field))]
    locator_resolves = citation_locator_resolves(citation_locator)
    page_bbox_region_complete = bool(
        nonempty(citation_metadata["page"])
        and nonempty(citation_metadata["bbox"])
        and nonempty(citation_metadata["region_type"])
    )
    strict_ready = not missing
    return {
        "schema_version": SCHEMA_VERSION,
        "query_id": query_id,
        "track": TRACK,
        "evidence_lane": PDF_CONTENT_EVIDENCE,
        "diagnostic_only": True,
        "diagnostic_only_reason": "missing_layout_or_source_metadata" if not strict_ready else "",
        "answer_generation_denominator_included": False,
        "official_metric_input": False,
        "promotion_evidence": False,
        "citation_metadata": citation_metadata,
        "citation_locator": citation_locator,
        "missing_context_fields": missing,
        "readiness": {
            "page_bbox_region_complete": page_bbox_region_complete,
            "matched_text_present": nonempty(citation_metadata["matched_text"]),
            "OCR_confidence_present": nonempty(citation_metadata["OCR_confidence"]),
            "OCR_confidence_or_native_text_na": ocr_confidence_or_native_text_na(citation_metadata),
            "nearby_paragraphs_present": nonempty(citation_metadata["nearby_paragraphs"]),
            "citation_locator_resolves": locator_resolves,
            "source_searchunit_present": nonempty(citation_metadata["source_searchunit_id"]),
            "parser_source_metadata_present": nonempty(citation_metadata["parser_source_metadata"]),
            "strict_gate_ready": strict_ready,
        },
    }


def readiness_counts(rows: Sequence[Mapping[str, Any]], stable_identity_ids: Sequence[str]) -> dict[str, int]:
    return {
        "input_rows": len(rows),
        "rows_with_complete_page_bbox_region": sum(
            1 for row in rows if row.get("readiness", {}).get("page_bbox_region_complete")
        ),
        "rows_with_matched_text": sum(1 for row in rows if row.get("readiness", {}).get("matched_text_present")),
        "rows_with_ocr_confidence": sum(1 for row in rows if row.get("readiness", {}).get("OCR_confidence_present")),
        "rows_with_ocr_confidence_or_native_text_na": sum(
            1 for row in rows if row.get("readiness", {}).get("OCR_confidence_or_native_text_na")
        ),
        "rows_with_nearby_paragraphs": sum(1 for row in rows if row.get("readiness", {}).get("nearby_paragraphs_present")),
        "rows_with_citation_locator": sum(1 for row in rows if row.get("readiness", {}).get("citation_locator_resolves")),
        "rows_blocked_by_missing_layout": sum(
            1
            for row in rows
            if any(
                field in set(row.get("missing_context_fields", []))
                for field in ("bbox", "nearby_paragraphs", "OCR_confidence", "source_searchunit_id", "parser_source_metadata")
            )
        ),
        "rows_blocked_by_file_identity_ambiguity": len(stable_identity_ids),
        "strict_gate_readiness_count": sum(1 for row in rows if row.get("readiness", {}).get("strict_gate_ready")),
        "generated_strict_rows_if_rerun": sum(1 for row in rows if row.get("readiness", {}).get("strict_gate_ready")),
    }


def missing_field_diagnosis(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    diagnosis: dict[str, dict[str, Any]] = {}
    for field in STRICT_REQUIRED_FIELDS:
        query_ids = [
            clean(row.get("query_id"))
            for row in rows
            if field in set(row.get("missing_context_fields", []))
        ]
        diagnosis[field] = {
            "missing_rows": len(query_ids),
            "query_ids": query_ids,
            "reason": missing_field_reason(field),
        }
    return diagnosis


def missing_field_reason(field: str) -> str:
    reasons = {
        "file": "source file identity is missing",
        "document_version_id": "stable document version identity is missing",
        "page": "page locator metadata is missing",
        "bbox": "layout bbox is missing or not parseable",
        "region_type": "layout region type is missing",
        "matched_text": "matched text is missing from the evidence row",
        "section_heading": "section heading is not emitted in current PDF fallback evidence",
        "table_caption_footnote": "table caption or footnote metadata is not emitted in current PDF fallback evidence",
        "nearby_paragraphs": "nearby paragraph context is not emitted in current PDF fallback evidence",
        "OCR_confidence": "OCR confidence is absent and native-text N/A is not explicitly asserted",
        "source_searchunit_id": "strict gate fallback rows do not carry SearchUnit identifiers",
        "source_searchunit_rank": "strict gate fallback rows do not carry retrieval rank",
        "parser_source_metadata": "parser/source metadata is absent from current strict fallback artifacts",
        "citation_locator": "citation locator does not resolve to page plus bbox or SearchUnit",
    }
    return reasons.get(field, "required metadata is missing")


def source_guardrail_summary(strict_payload: Mapping[str, Any]) -> dict[str, bool]:
    upstream = strict_payload.get("guardrails") if isinstance(strict_payload.get("guardrails"), Mapping) else {}
    counts = strict_payload.get("counts") if isinstance(strict_payload.get("counts"), Mapping) else {}
    lane_separation = (
        strict_payload.get("lane_separation") if isinstance(strict_payload.get("lane_separation"), Mapping) else {}
    )
    summary = {
        key: bool(upstream.get(key, False) or (key == "answer_generation_run" and strict_payload.get("answer_generation_run") is True))
        for key in PROTECTED_SOURCE_GUARDRAILS
    }
    summary["answer_generation_run"] = summary["answer_generation_run"] or strict_payload.get("answer_generation_run") is True
    summary["pdf_answer_generation_denominator_opened"] = (
        summary["pdf_answer_generation_denominator_opened"]
        or int_value(counts.get("pdf_answer_generation_denominator")) > 0
    )
    summary["official_denominator_opened_or_frozen"] = (
        summary["official_denominator_opened_or_frozen"]
        or strict_payload.get("official_metric") is True
        or int_value(strict_payload.get("official_metric_input_rows")) > 0
        or int_value(counts.get("official_metric_input_rows")) > 0
    )
    summary["promotion_evidence_created"] = (
        summary["promotion_evidence_created"] or strict_payload.get("promotion_evidence") is True
    )
    summary["pdf_content_file_lanes_aggregated"] = (
        summary["pdf_content_file_lanes_aggregated"]
        or lane_separation.get("content_and_file_identity_aggregated") is True
    )
    return summary


def synthesize_strict_payload_from_gold(*, pdf_gold_csv: Path, gold_query_ids: Sequence[str]) -> dict[str, Any]:
    input_ids = (
        [query_id for query_id in DEFAULT_STRICT_INPUT_IDS if query_id in set(gold_query_ids)]
        if pdf_gold_csv.resolve() == DEFAULT_PDF_GOLD_CSV.resolve()
        else list(gold_query_ids)
    )
    return {
        "status": "COMPLETED_DIAGNOSTIC_ONLY",
        "answer_generation_run": False,
        "counts": {
            "input_denominator_row_count": len(input_ids),
            "generated_silver_row_count": 0,
            "diagnostic_only_fallback_row_count": len(input_ids),
            "stable_identity_required_row_count": len(DEFAULT_STABLE_IDENTITY_REQUIRED_IDS),
            "pdf_answer_generation_denominator": 0,
        },
        "input_denominator_query_ids": input_ids,
        "excluded_query_ids": {
            "stable_identity_required": list(DEFAULT_STABLE_IDENTITY_REQUIRED_IDS),
        },
        "guardrails": {
            key: False for key in PROTECTED_SOURCE_GUARDRAILS
        },
    }


def validation_errors_for(*, source_guardrails: Mapping[str, bool], rows: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    for key in PROTECTED_SOURCE_GUARDRAILS:
        if source_guardrails.get(key) is True:
            errors.append(f"strict guardrail violation: {key}=true")
    for row in rows:
        if row.get("evidence_lane") != PDF_CONTENT_EVIDENCE:
            errors.append(f"{row.get('query_id')} invalid evidence lane")
        if row.get("official_metric_input") is not False:
            errors.append(f"{row.get('query_id')} official_metric_input must be false")
        if row.get("promotion_evidence") is not False:
            errors.append(f"{row.get('query_id')} promotion_evidence must be false")
    return errors


def citation_locator_resolves(locator: Mapping[str, Any]) -> bool:
    return bool(
        clean(locator.get("file"))
        and clean(locator.get("document_version_id"))
        and nonempty(locator.get("page"))
        and clean(locator.get("region_type"))
        and (nonempty(locator.get("bbox")) or clean(locator.get("search_unit_id")))
    )


def ocr_confidence_or_native_text_na(metadata: Mapping[str, Any]) -> bool:
    status = clean(metadata.get("OCR_confidence_status")).lower()
    if nonempty(metadata.get("OCR_confidence")):
        return True
    return status in {"native_text_na", "native_text_not_applicable"}


def render_markdown(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "# PDF Evidence Readiness Report",
        "",
        f"- Status: `{report['status']}`",
        "- Scope: diagnostic-only PDF evidence readiness; answer generation remains closed.",
        f"- Input rows: `{counts['input_rows']}`",
        f"- Rows with complete page/bbox/region: `{counts['rows_with_complete_page_bbox_region']}`",
        f"- Rows with matched text: `{counts['rows_with_matched_text']}`",
        f"- Rows with OCR confidence: `{counts['rows_with_ocr_confidence']}`",
        "- Rows with OCR confidence or explicit native-text N/A: "
        f"`{counts['rows_with_ocr_confidence_or_native_text_na']}`",
        f"- Rows with nearby paragraphs: `{counts['rows_with_nearby_paragraphs']}`",
        f"- Rows with citation locator: `{counts['rows_with_citation_locator']}`",
        f"- Rows blocked by missing layout/source metadata: `{counts['rows_blocked_by_missing_layout']}`",
        f"- Rows blocked by file identity ambiguity: `{counts['rows_blocked_by_file_identity_ambiguity']}`",
        f"- Strict gate readiness count: `{counts['strict_gate_readiness_count']}`",
        f"- Strict gate rerun performed: `{str(report['strict_gate_rerun']['rerun_performed']).lower()}`",
        "",
        "## Guardrails",
        "",
    ]
    for key, value in report["guardrails"].items():
        lines.append(f"- `{key}`: `{json.dumps(value, ensure_ascii=False)}`")
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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
        "path": repo_relative(path),
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


def parse_bbox(value: Any) -> list[float]:
    text = clean(value)
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    parsed: list[float] = []
    for item in payload:
        try:
            parsed.append(float(item))
        except (TypeError, ValueError):
            return []
    return parsed


def int_or_none(value: Any) -> int | None:
    try:
        return int(clean(value))
    except (TypeError, ValueError):
        return None


def int_value(value: Any) -> int:
    parsed = int_or_none(value)
    return parsed if parsed is not None else 0


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    if isinstance(value, (int, float)):
        return True
    return bool(value)


if __name__ == "__main__":
    raise SystemExit(main())
