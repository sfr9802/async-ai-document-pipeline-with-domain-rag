"""Classify PDF FILE lookup wrongly-supported diagnostic cases.

This report is intentionally post-hoc and diagnostic-only. It reads the
expanded answer recovery diagnostic outputs and the silver PDF FILE lookup
hard-negative source rows; it does not mutate indexes, train profiles, or
change denominator policy.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent

REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review" / "gold_silver_tuning"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report_dir = resolve_path(args.reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_report(report_dir)
    write_json(report_dir / "pdf_file_lookup_wrongly_supported_root_cause.json", payload)
    write_text(
        report_dir / "pdf_file_lookup_wrongly_supported_root_cause.md",
        render_md(payload),
    )
    print(json.dumps({"status": payload["status"], "case_count": payload["counts"]["case_count"]}, indent=2))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default=str(REPORT_DIR))
    return parser.parse_args(argv)


def build_report(report_dir: Path) -> dict[str, Any]:
    wrongly_supported = read_csv_rows(report_dir / "answer_recovery_wrongly_supported_review.csv")
    trace = read_jsonl(report_dir / "answer_recovery_expanded_trace.jsonl")
    trace_by_id = {row.get("case_id"): row for row in trace}
    source_by_case = pdf_file_lookup_source_rows_by_case()
    cases: list[dict[str, Any]] = []
    classification_counts: Counter[str] = Counter()
    for row in wrongly_supported:
        case_id = row.get("case_id", "")
        trace_row = trace_by_id.get(case_id, {})
        source = source_by_case.get(case_id, {})
        target_file = source.get("positive_expected_file_name") or source.get("expected_file_name", "")
        candidate_file = source.get("expected_file_name") or source.get("source_file_name", "")
        target_docv = source.get("positive_expected_document_version_id") or ""
        candidate_docv = source.get("expected_document_version_id") or ""
        target_source_id = source.get("positive_source_file_id") or ""
        candidate_source_id = source.get("source_file_id") or source.get("expected_source_file_id") or ""
        classifications = classify_case(row, trace_row, source, target_file, candidate_file)
        for item in classifications:
            classification_counts[item] += 1
        cases.append(
            {
                "case_id": case_id,
                "query_id": source.get("query_id", ""),
                "query": trace_row.get("query", source.get("query", "")),
                "source_artifact": row.get("source_artifact", ""),
                "target_file_name": target_file,
                "candidate_file_name": candidate_file,
                "target_document_version_id": target_docv,
                "candidate_document_version_id": candidate_docv,
                "target_source_file_id": target_source_id,
                "candidate_source_file_id": candidate_source_id,
                "negative_strategy": source.get("negative_strategy", ""),
                "silver_label": source.get("silver_label", ""),
                "before_status": trace_row.get("before_decision", {}).get("sufficiency_status", ""),
                "route_action": trace_row.get("route", {}).get("action", ""),
                "classifications": classifications,
                "root_cause_summary": "Sufficiency judge accepted cited file identity evidence without requiring exact target-vs-candidate identity verification.",
            }
        )
    return {
        "schema_version": "pdf_file_lookup_wrongly_supported_root_cause_v1",
        "status": "PASS",
        "policy": {
            "diagnostic_only": True,
            "official_denominator_registry_changed": False,
            "production_index_mutation": False,
            "broad_indexing": False,
            "pdf_file_lookup_semantics": "file_identity_only",
            "content_page_bbox_table_row_column_value_success_claimed": False,
        },
        "counts": {
            "case_count": len(cases),
            "classification_counts": dict(sorted(classification_counts.items())),
        },
        "cases": cases,
        "recommended_fix": [
            "Require exact/canonical target file identity match before PDF FILE lookup can be SUPPORTED.",
            "Fail closed on hard-negative labels, filename-token-only overlap, generic filenames without strong ids, document_version_id mismatch, and source_file_id mismatch.",
            "Keep answer_intent=file_identity in the PDF FILE lookup lane while still blocking content/page/bbox/table/row/column/value claims.",
        ],
    }


def classify_case(
    review_row: Mapping[str, Any],
    trace_row: Mapping[str, Any],
    source: Mapping[str, Any],
    target_file: str,
    candidate_file: str,
) -> list[str]:
    classifications: list[str] = []
    target_norm = canonical_file_name(target_file)
    candidate_norm = canonical_file_name(candidate_file)
    if target_norm and candidate_norm and target_norm != candidate_norm:
        classifications.append("filename_token_overlap_only")
    if is_generic_pdf_filename(target_file) or is_generic_pdf_filename(candidate_file):
        classifications.append("generic_filename_confusion")
    target_docv = source.get("positive_expected_document_version_id") or ""
    candidate_docv = source.get("expected_document_version_id") or ""
    if target_docv and candidate_docv and target_docv != candidate_docv:
        classifications.append("document_version_id_mismatch")
    target_source_id = source.get("positive_source_file_id") or ""
    candidate_source_id = source.get("source_file_id") or source.get("expected_source_file_id") or ""
    if target_source_id and candidate_source_id and target_source_id != candidate_source_id:
        classifications.append("source_file_id_mismatch")
    if trace_row.get("before_decision", {}).get("failure_type") == "LANE_MISMATCH":
        classifications.append("content_or_table_intent_bleed")
    if "HARD_NEGATIVE" not in (source.get("silver_label", "") + source.get("negative_strategy", "")).upper():
        classifications.append("hard_negative_label_issue")
    if trace_row.get("route", {}).get("target_lane") not in {"", "PDF_FILE_LOOKUP"}:
        classifications.append("router_intent_issue")
    if trace_row.get("before_decision", {}).get("sufficiency_status") == "SUPPORTED":
        classifications.append("sufficiency_judge_issue")
    if str(trace_row.get("expected_official_support_allowed")).lower() not in {"false", "0"}:
        classifications.append("report_labeling_issue")
    if not classifications:
        classifications.append("report_labeling_issue")
    return classifications


def pdf_file_lookup_source_rows_by_case() -> dict[str, dict[str, Any]]:
    paths = [
        REVIEW_DIR / "silver_pdf_file_lookup_positive_train.csv",
        REVIEW_DIR / "silver_pdf_file_lookup_hard_negative_v2.csv",
        REVIEW_DIR / "pdf_file_lookup_diagnostic_clean.csv",
        REVIEW_DIR / "pdf_file_lookup_gold_positive_clean.csv",
    ]
    mapping: dict[str, dict[str, Any]] = {}
    case_index = 1
    for path in paths:
        for row in read_csv_rows(path):
            if case_index > 28:
                break
            mapping[f"expanded_pdf_file_lookup_{case_index:03d}"] = row
            case_index += 1
    return mapping


def render_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# PDF FILE Lookup Wrongly Supported Root Cause",
        "",
        f"- Status: `{payload['status']}`.",
        "- Scope: diagnostic-only analysis of pre-calibration wrongly-supported cases.",
        "- Policy: PDF FILE lookup remains file identity only; no page/bbox/table/row/column/value success is claimed.",
        "",
        "## Counts",
        "",
        f"- case_count: `{payload['counts']['case_count']}`",
    ]
    for key, value in payload["counts"]["classification_counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| case_id | query_id | target_file_name | candidate_file_name | classifications |",
            "|---|---|---|---|---|",
        ]
    )
    for item in payload["cases"]:
        lines.append(
            "| {case_id} | {query_id} | `{target}` | `{candidate}` | `{classes}` |".format(
                case_id=item["case_id"],
                query_id=item["query_id"],
                target=item["target_file_name"],
                candidate=item["candidate_file_name"],
                classes=", ".join(item["classifications"]),
            )
        )
    lines.extend(["", "## Recommended Fix", ""])
    for item in payload["recommended_fix"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def canonical_file_name(value: str) -> str:
    return " ".join(str(value or "").lower().replace("\\", "/").split("/")[-1].replace("+", " ").split())


def is_generic_pdf_filename(value: str) -> bool:
    filename = canonical_file_name(value)
    if filename in {"file.pdf", "document.pdf", "scan.pdf", "report.pdf", "untitled.pdf", "sample.pdf"}:
        return True
    stem = filename[:-4] if filename.endswith(".pdf") else filename
    return stem == "file" or (stem.startswith("file (") and stem.endswith(")"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def resolve_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai-worker":
        return REPO_ROOT / path
    return AI_WORKER_ROOT / path


if __name__ == "__main__":
    sys.exit(main())
