"""Audit supplemental PDF answer-evidence object readiness.

This script is diagnostic-only. It reads existing parser/evidence artifacts and
does not run PageIndex, retrieval, reranking, parser expansion, DB writes,
SearchUnit writes, LLM answer generation, or judge calls.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    REPORT_DIR,
    artifact_identity,
    bbox_key,
    display_path,
    iter_jsonl,
    latest_supplemental_artifact_dir,
    read_json,
    resolve_path,
    short_text,
    sorted_counter,
    supplemental_output_path_blockers,
    to_int,
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.csv"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_improvement_claimed": False,
}

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "anchor_type",
    "query",
    "answer_allowed",
    "evidence_ready",
    "locator_only_risk",
    "keyword_only_risk",
    "page_only_risk",
    "bbox_only_risk",
    "paragraph_context_present",
    "section_context_present",
    "nearby_context_present",
    "table_like_context_candidate",
    "ocr_needed_candidate",
    "native_text_candidate",
    "evidence_text_chars",
    "evidence_context_chars",
    "reason",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    evidence_path = resolve_path(args.evidence_jsonl) if args.evidence_jsonl else artifact_dir / "answer_evidence_objects.jsonl"
    parsed_blocks_path = resolve_path(args.parsed_blocks) if args.parsed_blocks else artifact_dir / "parsed_blocks.jsonl"
    manifest_path = resolve_path(args.manifest) if args.manifest else artifact_dir / "supplemental_pdf_manifest.json"
    diagnostic_report_path = resolve_path(args.answer_evidence_report)
    json_report_path = resolve_path(args.report)
    csv_report_path = resolve_path(args.csv)
    output_path_blockers = supplemental_output_path_blockers({
        "json_report": json_report_path,
        "csv_report": csv_report_path,
    })
    if output_path_blockers:
        print(json.dumps({
            "status": "FAIL_CLOSED_UNSAFE_OUTPUT_PATH",
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
            "blockers": output_path_blockers,
        }, ensure_ascii=False, indent=2))
        return 2

    payload = build_quality_audit(
        artifact_dir=artifact_dir,
        evidence_path=evidence_path,
        parsed_blocks_path=parsed_blocks_path,
        manifest_path=manifest_path,
        diagnostic_report_path=diagnostic_report_path,
        json_report_path=json_report_path,
        csv_report_path=csv_report_path,
    )
    write_json(json_report_path, payload["report"])
    write_csv(csv_report_path, payload["rows"], CSV_FIELDS)
    print(json.dumps({
        "status": payload["report"]["status"],
        "json_report": display_path(json_report_path),
        "csv_report": display_path(csv_report_path),
        "counts": payload["report"]["counts"],
        "blockers": payload["report"]["blockers"],
    }, ensure_ascii=False, indent=2))
    return 0 if not payload["report"]["blockers"] else 2


def build_quality_audit(
    *,
    artifact_dir: Path,
    evidence_path: Path,
    parsed_blocks_path: Path,
    manifest_path: Path,
    diagnostic_report_path: Path,
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

    parsed_profile = build_parsed_block_profile(parsed_blocks_path, warnings)
    manifest_profile = build_manifest_profile(manifest_path, warnings)
    diagnostic_report = read_json(diagnostic_report_path) if diagnostic_report_path.exists() else {}
    if diagnostic_report and diagnostic_report.get("promotion_evidence") is not False:
        blockers.append("answer evidence diagnostic report must keep promotion_evidence=false")
    if diagnostic_report and diagnostic_report.get("evidence_role") != "diagnostic":
        blockers.append("answer evidence diagnostic report must keep evidence_role=diagnostic")

    rows = [
        audit_row(row, parsed_profile, manifest_profile)
        for row in evidence_rows
    ]
    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and counts["evidence_ready_count"] < counts["answer_allowed_count"]:
        status = "PASS_WITH_EVIDENCE_READINESS_RISKS"
    report = {
        "schema_version": "pdf_supplemental_answer_evidence_quality_audit_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "answer_generation_execution": "not_run_by_this_script",
        "actual_generated_answer_output": False,
        "deterministic_answer_draft_created_by_this_script": False,
        "readiness_policy": {
            "paragraph_context_min_chars": 40,
            "nearby_context_min_chars": 80,
            "table_like_context_min_chars": 60,
            "keyword_only_can_be_ready_only_with_nearby_context": True,
            "table_like_context_is_candidate_only": True,
            "row_column_value_semantics_claimed": False,
        },
        "input_artifacts": [
            artifact_identity(evidence_path),
            artifact_identity(parsed_blocks_path),
            artifact_identity(manifest_path),
            artifact_identity(diagnostic_report_path),
        ],
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
        },
        "artifact_dir": display_path(artifact_dir),
        "counts": counts,
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "answer_allowed is inherited from the existing diagnostic object; evidence_ready is stricter.",
            "keyword_only_risk is not treated as proof of answer failure when nearby context is content-bearing.",
            "table-like blocks remain heuristic candidates and do not claim row/column/value semantics.",
            "OCR-needed and native-text readiness are file/evidence profiles, not gold denominators.",
        ],
    }
    return {"report": report, "rows": rows}


def build_parsed_block_profile(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"parsed blocks JSONL missing: {display_path(path)}")
        return {"by_block": {}, "by_file": {}}
    by_block: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    by_file: dict[str, dict[str, bool]] = defaultdict(lambda: {"ocr_used": False, "native_text": False})
    for block in iter_jsonl(path):
        relative_path = str(block.get("relative_path") or "")
        page_no = to_int(block.get("page_no")) or 0
        key = (relative_path, page_no, bbox_key(block.get("bbox")))
        by_block[key] = block
        if truthy(block.get("ocr_used")):
            by_file[relative_path]["ocr_used"] = True
        elif str(block.get("text") or "").strip():
            by_file[relative_path]["native_text"] = True
    return {"by_block": by_block, "by_file": dict(by_file)}


def build_manifest_profile(path: Path, warnings: list[str]) -> dict[str, dict[str, bool]]:
    if not path.exists():
        warnings.append(f"supplemental PDF manifest missing: {display_path(path)}")
        return {}
    payload = read_json(path)
    result: dict[str, dict[str, bool]] = {}
    for row in payload.get("pdfs") or []:
        relative_path = str(row.get("relative_path") or "")
        if not relative_path:
            continue
        result[relative_path] = {
            "ocr_needed": truthy(row.get("likely_ocr_needed_pdf")),
            "native_text": truthy(row.get("likely_native_text_pdf")) or truthy(row.get("text_layer_present")),
        }
    return result


def audit_row(
    evidence: Mapping[str, Any],
    parsed_profile: Mapping[str, Any],
    manifest_profile: Mapping[str, Mapping[str, bool]],
) -> dict[str, Any]:
    citation = evidence.get("citation") if isinstance(evidence.get("citation"), Mapping) else {}
    relative_path = str(evidence.get("relative_path") or citation.get("relative_path") or "")
    page_no = to_int(citation.get("page_no")) or 0
    block = (parsed_profile.get("by_block") or {}).get((relative_path, page_no, bbox_key(citation.get("bbox"))), {})
    file_profile = (manifest_profile.get(relative_path) or (parsed_profile.get("by_file") or {}).get(relative_path) or {})

    evidence_text = compact_text(
        evidence.get("evidence_text")
        or evidence.get("evidence_text_excerpt")
        or evidence.get("paragraph_summary")
        or ""
    )
    nearby_context = compact_text(evidence.get("nearby_context") or "")
    section_title = compact_text(evidence.get("section_title") or "")
    paragraph_summary = compact_text(evidence.get("paragraph_summary") or evidence_text)
    evidence_text_chars = len(evidence_text)
    evidence_context_chars = len(compact_text(" ".join(part for part in [nearby_context, section_title] if part)))

    paragraph_context_present = truthy(evidence.get("paragraph_context_present")) and len(paragraph_summary) >= 40
    section_context_present = bool(section_title)
    nearby_context_present = bool(nearby_context)
    table_like_context_candidate = truthy(evidence.get("table_like_context_candidate")) or truthy(block.get("table_like_block_candidate"))

    locator_available = bool(citation.get("page_no") or citation.get("bbox"))
    content_available = bool(evidence_text or nearby_context or section_title)
    locator_only_risk = truthy(evidence.get("locator_only_object")) or bool(locator_available and not content_available)
    page_only_risk = truthy(evidence.get("page_only_risk")) or bool(citation.get("page_no") and not (evidence_text or nearby_context))
    bbox_only_risk = truthy(evidence.get("bbox_only_risk")) or bool(citation.get("bbox") and not evidence_text)
    keyword_only_risk = truthy(evidence.get("keyword_only_risk")) or keyword_only_candidate(evidence_text, nearby_context)

    ocr_needed_candidate = (
        truthy(evidence.get("ocr_evidence_used"))
        or truthy(evidence.get("lower_trust_ocr"))
        or truthy(block.get("ocr_used"))
        or truthy(file_profile.get("ocr_needed"))
        or truthy(file_profile.get("ocr_used"))
    )
    native_text_candidate = (
        not ocr_needed_candidate
        and (truthy(file_profile.get("native_text")) or bool(evidence_text or nearby_context))
    )

    content_reasons: list[str] = []
    if paragraph_context_present and evidence_text_chars >= 40:
        content_reasons.append("paragraph_block_text_present")
    if nearby_context_present and len(nearby_context) >= 80:
        content_reasons.append("nearby_context_present")
    if section_context_present and evidence_text_chars >= 80:
        content_reasons.append("section_with_content_text_present")
    if table_like_context_candidate and evidence_text_chars >= 60:
        content_reasons.append("table_like_candidate_with_text")
    keyword_without_context = keyword_only_risk and len(nearby_context) < 80 and evidence_text_chars < 80
    answer_allowed = truthy(evidence.get("answer_allowed"))
    evidence_ready = bool(
        answer_allowed
        and content_reasons
        and not locator_only_risk
        and not page_only_risk
        and not bbox_only_risk
        and not keyword_without_context
    )
    reason = readiness_reason(
        evidence_ready=evidence_ready,
        answer_allowed=answer_allowed,
        content_reasons=content_reasons,
        locator_only_risk=locator_only_risk,
        keyword_only_risk=keyword_only_risk,
        keyword_without_context=keyword_without_context,
        page_only_risk=page_only_risk,
        bbox_only_risk=bbox_only_risk,
    )
    return {
        "query_id": evidence.get("query_id"),
        "dataset_source": evidence.get("dataset_source"),
        "file_name": evidence.get("file_name"),
        "anchor_type": evidence.get("anchor_type"),
        "query": evidence.get("query"),
        "answer_allowed": answer_allowed,
        "evidence_ready": evidence_ready,
        "locator_only_risk": locator_only_risk,
        "keyword_only_risk": keyword_only_risk,
        "page_only_risk": page_only_risk,
        "bbox_only_risk": bbox_only_risk,
        "paragraph_context_present": paragraph_context_present,
        "section_context_present": section_context_present,
        "nearby_context_present": nearby_context_present,
        "table_like_context_candidate": table_like_context_candidate,
        "ocr_needed_candidate": ocr_needed_candidate,
        "native_text_candidate": native_text_candidate,
        "evidence_text_chars": evidence_text_chars,
        "evidence_context_chars": evidence_context_chars,
        "reason": reason,
    }


def readiness_reason(
    *,
    evidence_ready: bool,
    answer_allowed: bool,
    content_reasons: list[str],
    locator_only_risk: bool,
    keyword_only_risk: bool,
    keyword_without_context: bool,
    page_only_risk: bool,
    bbox_only_risk: bool,
) -> str:
    if not answer_allowed:
        return "answer_not_allowed_by_source_object"
    if locator_only_risk:
        return "locator_only_content_missing"
    if page_only_risk:
        return "page_only_content_missing"
    if bbox_only_risk:
        return "bbox_only_content_missing"
    if keyword_without_context:
        return "keyword_only_without_sufficient_context"
    if not content_reasons:
        return "content_context_below_readiness_threshold"
    if evidence_ready and keyword_only_risk:
        return "ready_with_keyword_risk_mitigated_by_context"
    if evidence_ready:
        return "ready:" + "|".join(content_reasons)
    return "not_ready_unknown"


def keyword_only_candidate(evidence_text: str, nearby_context: str) -> bool:
    if not evidence_text:
        return False
    if len(evidence_text) >= 80:
        return False
    if len(nearby_context) >= len(evidence_text) + 40:
        return False
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", evidence_text)
    return len(tokens) <= 8


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    answer_allowed = sum(1 for row in rows if row.get("answer_allowed") is True)
    ready = sum(1 for row in rows if row.get("evidence_ready") is True)
    native_rows = [row for row in rows if row.get("native_text_candidate") is True]
    ocr_rows = [row for row in rows if row.get("ocr_needed_candidate") is True]
    elec_rows = [row for row in rows if row.get("dataset_source") == "elec"]
    lh_rows = [row for row in rows if row.get("dataset_source") == "lh"]
    return {
        "evidence_object_count": total,
        "answer_allowed_count": answer_allowed,
        "evidence_ready_count": ready,
        "answer_evidence_ready_rate": rate(ready, total),
        "locator_only_object_count": sum(1 for row in rows if row.get("locator_only_risk") is True),
        "keyword_only_risk_count": sum(1 for row in rows if row.get("keyword_only_risk") is True),
        "page_only_risk_count": sum(1 for row in rows if row.get("page_only_risk") is True),
        "bbox_only_risk_count": sum(1 for row in rows if row.get("bbox_only_risk") is True),
        "paragraph_context_present_count": sum(1 for row in rows if row.get("paragraph_context_present") is True),
        "section_context_present_count": sum(1 for row in rows if row.get("section_context_present") is True),
        "nearby_context_present_count": sum(1 for row in rows if row.get("nearby_context_present") is True),
        "table_like_context_candidate_count": sum(1 for row in rows if row.get("table_like_context_candidate") is True),
        "native_text_object_count": len(native_rows),
        "ocr_needed_object_count": len(ocr_rows),
        "native_text_ready_rate": ready_rate(native_rows),
        "ocr_needed_ready_rate": ready_rate(ocr_rows),
        "elec_ready_rate": ready_rate(elec_rows),
        "lh_ready_rate": ready_rate(lh_rows),
        "dataset_source_counts": sorted_counter(Counter(str(row.get("dataset_source") or "unknown") for row in rows)),
        "readiness_reason_counts": sorted_counter(Counter(str(row.get("reason") or "") for row in rows)),
    }


def ready_rate(rows: list[Mapping[str, Any]]) -> float | None:
    if not rows:
        return None
    return rate(sum(1 for row in rows if row.get("evidence_ready") is True), len(rows))


def rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    return latest_supplemental_artifact_dir()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--evidence-jsonl", default=None)
    parser.add_argument("--parsed-blocks", default=None)
    parser.add_argument("--manifest", default=None)
    parser.add_argument(
        "--answer-evidence-report",
        default=str(REPORT_DIR / "rag_pdf_supplemental_answer_evidence_diagnostic_report.json"),
    )
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
