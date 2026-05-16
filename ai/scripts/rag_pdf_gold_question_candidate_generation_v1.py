"""Generate diagnostic PDF question/expected-answer candidates with a local LLM."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_local_llm_expected_answer_generation_v1 import (  # noqa: E402
    DEFAULT_BACKEND,
    DEFAULT_MODEL,
    call_local_llm_strict_json,
    clean,
    local_llm_entry_blockers,
    read_jsonl,
    repo_relative,
    resolve_base_url,
    utc_timestamp,
    write_json,
)

from rag_question_quality_gate_v1 import classify_question  # noqa: E402


REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_INPUT_JSONL = REPORT_DIR / "pdf_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_OUTPUT_JSON = REVIEW_DIR / "rag_pdf_gold_question_candidate_generation_v1.json"
DEFAULT_OUTPUT_MD = REVIEW_DIR / "rag_pdf_gold_question_candidate_generation_v1.md"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_generation(
        input_jsonl=Path(args.input_jsonl),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        max_tokens=args.max_tokens,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "generated_candidates": report["summary"]["generated_candidates"],
                "rejected_candidates": report["summary"]["rejected_candidates"],
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
    parser.add_argument("--input-jsonl", default=str(DEFAULT_INPUT_JSONL))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=["llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=900)
    return parser.parse_args(argv)


def run_generation(
    *,
    input_jsonl: Path,
    output_report: Path,
    output_md: Path,
    backend: str = DEFAULT_BACKEND,
    base_url: str = "",
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 120,
    max_tokens: int = 900,
    llm_client: Any | None = None,
    skip_probe: bool = False,
) -> dict[str, Any]:
    resolved = resolve_base_url(backend, base_url)
    rows = read_jsonl(input_jsonl)
    blockers = []
    if not skip_probe:
        blockers = local_llm_entry_blockers(
            backend=backend,
            base_url=resolved,
            model=model,
            check_endpoint=True,
            timeout_seconds=min(timeout_seconds, 5),
        )
    if blockers:
        report = base_report(
            status="LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
            input_jsonl=input_jsonl,
            output_report=output_report,
            output_md=output_md,
            backend=backend,
            base_url=resolved,
            model=model,
            rows=rows,
        )
        report["blockers"] = blockers
        write_outputs(report, output_report, output_md)
        return report

    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in rows:
        reasons = eligibility_rejection_reasons(row)
        if reasons:
            rejected.append(rejected_row(row, reasons))
            continue
        prompt = build_prompt(row)
        try:
            parsed, meta = call_local_llm_strict_json(
                backend=backend,
                base_url=resolved,
                model=model,
                prompt=prompt,
                temperature=0.0,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                llm_client=llm_client,
            )
            candidate = candidate_from_payload(row, parsed, meta)
            post_reasons = candidate_rejection_reasons(candidate)
            if post_reasons:
                rejected.append(rejected_row(row, post_reasons, candidate=candidate))
            else:
                candidates.append(candidate)
        except Exception as exc:
            rejected.append(rejected_row(row, [f"LOCAL_LLM_OUTPUT_INVALID:{type(exc).__name__}: {exc}"]))

    status = "PDF_LOCAL_LLM_CANDIDATE_GENERATION_COMPLETE"
    report = base_report(
        status=status,
        input_jsonl=input_jsonl,
        output_report=output_report,
        output_md=output_md,
        backend=backend,
        base_url=resolved,
        model=model,
        rows=rows,
    )
    report["candidates"] = candidates
    report["rejected_rows"] = rejected
    report["summary"].update(
        {
            "generated_candidates": len(candidates),
            "rejected_candidates": len(rejected),
            "input_rows": len(rows),
        }
    )
    write_outputs(report, output_report, output_md)
    return report


def base_report(
    *,
    status: str,
    input_jsonl: Path,
    output_report: Path,
    output_md: Path,
    backend: str,
    base_url: str,
    model: str,
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "rag_pdf_gold_question_candidate_generation_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "pdf_business_ocr_mm",
        "diagnostic_only": True,
        "model_assisted_diagnostic_only": True,
        "human_review_required": True,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "external_api_used": False,
        "local_llm": {"backend": backend, "base_url": base_url, "model": clean(model), "temperature": 0},
        "summary": {"input_rows": len(rows), "generated_candidates": 0, "rejected_candidates": 0},
        "candidates": [],
        "rejected_rows": [],
        "blockers": [],
        "source_artifacts": {"input_jsonl": repo_relative(input_jsonl)},
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
        "validation": {"ok": True, "errors": []},
    }


def eligibility_rejection_reasons(row: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if clean(row.get("content_evidence_lane")) != "pdf_content_evidence":
        reasons.append("PDF_FILE_IDENTITY_LANE_BLOCKED")
    query_id = clean(row.get("query_id"))
    if query_id.startswith("expanded_pdf_file_lookup"):
        reasons.append("PLACEHOLDER_QUERY_ID")
    evidence = source_bound_evidence_text(row)
    if not evidence:
        reasons.append("EMPTY_PROPOSED_EVIDENCE")
    questionish = clean(row.get("question") or row.get("matched_text"))
    quality = classify_question(
        questionish,
        query_id=query_id,
        track="pdf_business_ocr_mm",
        region_type=clean(row.get("region_type")),
        evidence_text=evidence,
    )
    content_paragraphs = content_nearby_paragraphs(row)
    if "PDF_HEADING_OR_TITLE_AS_QUERY" in quality["classifications"] and not content_paragraphs:
        reasons.append("PDF_HEADING_OR_TITLE_AS_QUERY")
    if "PDF_TABLE_LABEL_AS_QUERY" in quality["classifications"] and not content_paragraphs:
        reasons.append("PDF_TABLE_LABEL_AS_QUERY")
    if "표지" in clean(row.get("matched_text")) and not content_paragraphs:
        reasons.append("PDF_HEADING_OR_TITLE_AS_QUERY")
    if list_value(row.get("nearby_paragraphs")) and not content_paragraphs:
        reasons.append("PDF_LOCATOR_ONLY_NEARBY_CONTEXT")
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    if row.get("page") is None and locator.get("page") is None:
        reasons.append("PDF_CITATION_LOCATOR_MISSING_PAGE")
    if not row.get("bbox") and not locator.get("bbox"):
        reasons.append("PDF_CITATION_LOCATOR_MISSING_BBOX")
    if not clean(row.get("search_unit_id") or locator.get("search_unit_id")):
        reasons.append("PDF_CITATION_LOCATOR_MISSING_SEARCH_UNIT")
    return sorted(set(reasons))


def candidate_rejection_reasons(candidate: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    question = clean(candidate.get("rewritten_question_ko"))
    answer = clean(candidate.get("expected_answer_ko"))
    quote = clean(candidate.get("supporting_evidence_quote"))
    evidence = clean(candidate.get("source_bound_evidence_text"))
    quality = classify_question(question, query_id=clean(candidate.get("query_id")), track="pdf_business_ocr_mm")
    if quality["primary_classification"] != "NATURAL_LANGUAGE_QUESTION":
        reasons.extend(quality["classifications"])
    if not answer:
        reasons.append("EMPTY_PROPOSED_ANSWER")
    if answer and answer == question:
        reasons.append("ANSWER_EQUALS_QUESTION")
    if not quote or normalize(quote) not in normalize(evidence):
        reasons.append("PDF_SUPPORTING_EVIDENCE_QUOTE_NOT_IN_SOURCE")
    if answer and normalize(answer) not in normalize(evidence):
        reasons.append("PDF_EXPECTED_ANSWER_UNSUPPORTED")
    if clean(candidate.get("answerability_label_proposed")) != "ANSWERABLE":
        reasons.append("PDF_NOT_ANSWERABLE")
    return sorted(set(reasons))


def candidate_from_payload(row: Mapping[str, Any], payload: Mapping[str, Any], meta: Mapping[str, Any]) -> dict[str, Any]:
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    citation_locator = {
        "page": row.get("page") if row.get("page") is not None else locator.get("page"),
        "bbox": row.get("bbox") if row.get("bbox") else locator.get("bbox"),
        "region_type": clean(row.get("region_type") or locator.get("region_type")),
        "search_unit_id": clean(row.get("search_unit_id") or locator.get("search_unit_id")),
    }
    return {
        "schema_version": "rag_pdf_gold_question_candidate_generation_row_v1",
        "track": "pdf_business_ocr_mm",
        "query_id": clean(row.get("query_id")),
        "original_question": clean(row.get("question") or row.get("query_id")),
        "rewritten_question_ko": clean(payload.get("rewritten_question_ko")),
        "expected_answer_ko": clean(payload.get("expected_answer_ko")),
        "supporting_evidence_quote": clean(payload.get("supporting_evidence_quote")),
        "answerability_label_proposed": clean(payload.get("answerability_label_proposed")),
        "relevance_label_proposed": clean(payload.get("relevance_label_proposed")),
        "confidence": clean(payload.get("confidence")),
        "reason": clean(payload.get("reason")),
        "source_bound_evidence_text": source_bound_evidence_text(row),
        "matched_text": clean(row.get("matched_text")),
        "nearby_paragraphs": list_value(row.get("nearby_paragraphs")),
        "page": citation_locator["page"],
        "bbox": citation_locator["bbox"],
        "region_type": citation_locator["region_type"],
        "search_unit_id": citation_locator["search_unit_id"],
        "document_version_id": clean(row.get("document_version_id")),
        "file": clean(row.get("file") or row.get("source_file_id")),
        "citation_locator": citation_locator,
        "content_evidence_lane": clean(row.get("content_evidence_lane")),
        "human_review_required": True,
        "model_assisted_diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "official_denominator_current": False,
        "local_llm_meta": dict(meta),
    }


def build_prompt(row: Mapping[str, Any]) -> str:
    evidence = {
        "matched_text": clean(row.get("matched_text")),
        "nearby_paragraphs": list_value(row.get("nearby_paragraphs")),
        "page": row.get("page"),
        "bbox": row.get("bbox"),
        "region_type": clean(row.get("region_type")),
        "search_unit_id": clean(row.get("search_unit_id")),
        "document_version_id": clean(row.get("document_version_id")),
        "file": clean(row.get("file") or row.get("source_file_id")),
        "citation_locator": row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {},
    }
    return (
        "PDF source-bound evidence only. Do not add outside knowledge. "
        "Return exactly one JSON object with keys: rewritten_question_ko, expected_answer_ko, "
        "supporting_evidence_quote, answerability_label_proposed, relevance_label_proposed, confidence, reason. "
        "If evidence is only a heading/title/table label, mark answerability_label_proposed as NOT_ANSWERABLE. "
        "The supporting_evidence_quote must be copied from the evidence.\n\n"
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    )


def rejected_row(row: Mapping[str, Any], reasons: list[str], *, candidate: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "query_id": clean(row.get("query_id")),
        "track": "pdf_business_ocr_mm",
        "rejection_reasons": sorted(set(reasons)),
        "candidate": dict(candidate or {}),
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def source_bound_evidence_text(row: Mapping[str, Any]) -> str:
    parts = [clean(row.get("matched_text"))]
    parts.extend(content_nearby_paragraphs(row))
    return "\n".join(part for part in parts if part)


def content_nearby_paragraphs(row: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for item in list_value(row.get("nearby_paragraphs")):
        text = clean(item)
        if not text:
            continue
        if " > p." in text and "bbox" in text:
            continue
        values.append(text)
    return values


def write_outputs(report: Mapping[str, Any], output_report: Path, output_md: Path) -> None:
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    return "\n".join(
        [
            "# PDF Gold Question Candidate Generation v1",
            "",
            f"- Status: `{report.get('status')}`",
            f"- Generated candidates: `{summary.get('generated_candidates')}`",
            f"- Rejected candidates: `{summary.get('rejected_candidates')}`",
            f"- Official metric input rows: `{report.get('official_metric_input_rows')}`",
            f"- Promotion evidence: `{str(report.get('promotion_evidence')).lower()}`",
        ]
    ) + "\n"


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize(value: str) -> str:
    return "".join(clean(value).lower().split())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
