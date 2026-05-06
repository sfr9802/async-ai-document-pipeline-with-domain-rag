"""Compile deterministic extractive answer drafts for ready evidence objects.

Drafts are diagnostic previews only. They are not LLM-generated answers, gold
evidence, promotion evidence, or answer-quality evaluation results.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    REPORT_DIR,
    artifact_identity,
    display_path,
    iter_jsonl,
    latest_supplemental_artifact_dir,
    read_csv,
    resolve_path,
    short_text,
    sorted_counter,
    supplemental_output_path_blockers,
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
    write_jsonl,
)


DEFAULT_QUALITY_CSV = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.csv"
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_deterministic_answer_draft_report.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_deterministic_answer_draft.csv"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_improvement_claimed": False,
}

CSV_FIELDS = [
    "query_id",
    "answer_draft",
    "citation",
    "source_evidence_text",
    "answer_shape",
    "abstain_reason",
    "locator_only_prevented",
    "keyword_echo_prevented",
    "promotion_evidence",
    "evidence_role",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    evidence_path = resolve_path(args.evidence_jsonl) if args.evidence_jsonl else artifact_dir / "answer_evidence_objects.jsonl"
    quality_csv_path = resolve_path(args.quality_csv)
    draft_jsonl_path = resolve_path(args.draft_jsonl) if args.draft_jsonl else artifact_dir / "deterministic_answer_drafts.jsonl"
    json_report_path = resolve_path(args.report)
    csv_report_path = resolve_path(args.csv)
    output_path_blockers = supplemental_output_path_blockers({
        "draft_jsonl": draft_jsonl_path,
        "json_report": json_report_path,
        "csv_report": csv_report_path,
    })
    if output_path_blockers:
        print(json.dumps({
            "status": "FAIL_CLOSED_UNSAFE_OUTPUT_PATH",
            "draft_jsonl": display_path(draft_jsonl_path),
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
            "blockers": output_path_blockers,
        }, ensure_ascii=False, indent=2))
        return 2

    payload = build_drafts(
        artifact_dir=artifact_dir,
        evidence_path=evidence_path,
        quality_csv_path=quality_csv_path,
        draft_jsonl_path=draft_jsonl_path,
        json_report_path=json_report_path,
        csv_report_path=csv_report_path,
    )
    write_jsonl(draft_jsonl_path, payload["draft_rows"])
    write_json(json_report_path, payload["report"])
    write_csv(csv_report_path, payload["csv_rows"], CSV_FIELDS)
    print(json.dumps({
        "status": payload["report"]["status"],
        "draft_jsonl": display_path(draft_jsonl_path),
        "json_report": display_path(json_report_path),
        "csv_report": display_path(csv_report_path),
        "counts": payload["report"]["counts"],
        "blockers": payload["report"]["blockers"],
    }, ensure_ascii=False, indent=2))
    return 0 if not payload["report"]["blockers"] else 2


def build_drafts(
    *,
    artifact_dir: Path,
    evidence_path: Path,
    quality_csv_path: Path,
    draft_jsonl_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not evidence_path.exists():
        blockers.append(f"answer evidence JSONL missing: {display_path(evidence_path)}")
        evidence_rows: list[dict[str, Any]] = []
    else:
        evidence_rows = [row for row in iter_jsonl(evidence_path)]
    if not quality_csv_path.exists():
        blockers.append(f"quality audit CSV missing: {display_path(quality_csv_path)}")
        quality_by_id: dict[str, dict[str, str]] = {}
    else:
        quality_by_id = {str(row.get("query_id") or ""): row for row in read_csv(quality_csv_path)}

    draft_rows = [draft_row(evidence, quality_by_id.get(str(evidence.get("query_id") or ""), {})) for evidence in evidence_rows]
    csv_rows = [{key: row.get(key) for key in CSV_FIELDS} for row in draft_rows]
    counts = build_counts(draft_rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and counts["abstained_count"]:
        status = "PASS_WITH_ABSTAINS"
    report = {
        "schema_version": "pdf_supplemental_deterministic_answer_draft_report_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "answer_generation_execution": "deterministic_extractive_no_llm",
        "actual_llm_answer_generation_run": False,
        "actual_generated_answer_output": False,
        "deterministic_answer_draft_only": True,
        "answer_draft_is_actual_generated_llm_answer": False,
        "table_like_context_is_candidate_only": True,
        "row_column_value_semantics_claimed": False,
        "input_artifacts": [
            artifact_identity(evidence_path),
            artifact_identity(quality_csv_path),
        ],
        "output_artifacts": {
            "draft_jsonl": display_path(draft_jsonl_path),
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
        },
        "artifact_dir": display_path(artifact_dir),
        "counts": counts,
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "Drafts are created only when evidence_ready=true in the quality audit.",
            "Draft text starts with content, while page and bbox stay in the citation field.",
            "Table-like evidence is described only as a table candidate area.",
            "No cloud/local LLM or optional judge is called.",
        ],
    }
    return {"report": report, "draft_rows": draft_rows, "csv_rows": csv_rows}


def draft_row(evidence: Mapping[str, Any], quality: Mapping[str, str]) -> dict[str, Any]:
    query_id = evidence.get("query_id")
    evidence_ready = truthy(quality.get("evidence_ready"))
    locator_only_risk = truthy(quality.get("locator_only_risk"))
    keyword_only_risk = truthy(quality.get("keyword_only_risk"))
    page_only_risk = truthy(quality.get("page_only_risk"))
    bbox_only_risk = truthy(quality.get("bbox_only_risk"))
    source_text = select_source_text(evidence, keyword_only_risk)
    citation = citation_only(evidence)
    abstain_reason = ""
    answer_draft = ""
    answer_shape = ""
    if not evidence_ready:
        abstain_reason = quality.get("reason") or "evidence_not_ready"
    elif len(source_text) < 40:
        abstain_reason = "source_evidence_text_below_draft_threshold"
    else:
        answer_shape = answer_shape_for(evidence)
        answer_draft = build_answer_text(source_text, answer_shape)
    locator_only_prevented = bool(locator_only_risk or page_only_risk or bbox_only_risk)
    keyword_echo_prevented = bool(keyword_only_risk and answer_draft and normalized(answer_draft) != normalized(str(evidence.get("query") or "")))
    return {
        "query_id": query_id,
        "answer_draft": answer_draft,
        "citation": citation,
        "source_evidence_text": source_text if answer_draft else "",
        "answer_shape": answer_shape,
        "abstain_reason": abstain_reason,
        "locator_only_prevented": locator_only_prevented,
        "keyword_echo_prevented": keyword_echo_prevented,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "live_llm_answer_generation_run": False,
        "optional_judge_run": False,
    }


def select_source_text(evidence: Mapping[str, Any], keyword_only_risk: bool) -> str:
    evidence_text = compact_text(evidence.get("evidence_text") or evidence.get("evidence_text_excerpt") or "")
    nearby_context = compact_text(evidence.get("nearby_context") or "")
    section_title = compact_text(evidence.get("section_title") or "")
    if keyword_only_risk and len(nearby_context) >= 80:
        return short_text(nearby_context, 360)
    if evidence_text:
        return short_text(evidence_text, 320)
    if nearby_context:
        return short_text(nearby_context, 320)
    return short_text(section_title, 160)


def answer_shape_for(evidence: Mapping[str, Any]) -> str:
    if truthy(evidence.get("table_like_context_candidate")):
        return "PDF_TABLE_LIKE_CANDIDATE_WITH_CONTEXT"
    if truthy(evidence.get("section_context_present")):
        return "PDF_SECTION_WITH_SUMMARY"
    return "PDF_PARAGRAPH_WITH_CONTEXT"


def build_answer_text(source_text: str, answer_shape: str) -> str:
    content = claim_text(source_text)
    if answer_shape == "PDF_TABLE_LIKE_CANDIDATE_WITH_CONTEXT":
        return f"표 후보 영역에는 {content} 내용이 포함되어 있습니다."
    return content


def citation_only(evidence: Mapping[str, Any]) -> dict[str, Any]:
    citation = evidence.get("citation") if isinstance(evidence.get("citation"), Mapping) else {}
    return {
        "relative_path": citation.get("relative_path") or evidence.get("relative_path"),
        "file_name": evidence.get("file_name"),
        "page_no": citation.get("page_no"),
        "physical_page_index": citation.get("physical_page_index"),
        "bbox": citation.get("bbox"),
        "source": citation.get("source") or "parser_derived_pdf_locator",
    }


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "draft_object_count": len(rows),
        "draft_created_count": sum(1 for row in rows if row.get("answer_draft")),
        "abstained_count": sum(1 for row in rows if row.get("abstain_reason")),
        "locator_only_prevented_count": sum(1 for row in rows if row.get("locator_only_prevented") is True),
        "keyword_echo_prevented_count": sum(1 for row in rows if row.get("keyword_echo_prevented") is True),
        "promotion_evidence_true_count": sum(1 for row in rows if row.get("promotion_evidence") is not False),
        "evidence_role_counts": sorted_counter(Counter(str(row.get("evidence_role") or "missing") for row in rows)),
        "answer_shape_counts": sorted_counter(Counter(str(row.get("answer_shape") or "ABSTAIN") for row in rows)),
        "abstain_reason_counts": sorted_counter(Counter(str(row.get("abstain_reason") or "") for row in rows if row.get("abstain_reason"))),
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "live_llm_answer_generation_run": False,
        "optional_judge_run": False,
    }


def claim_text(text: str) -> str:
    compact = compact_text(text)
    if not compact:
        return ""
    return short_text(compact, 260)


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    return latest_supplemental_artifact_dir()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--evidence-jsonl", default=None)
    parser.add_argument("--quality-csv", default=str(DEFAULT_QUALITY_CSV))
    parser.add_argument("--draft-jsonl", default=None)
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
