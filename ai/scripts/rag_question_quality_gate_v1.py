"""Question-quality gate for diagnostic PDF/XLSX gold-candidate drafts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_local_llm_expected_answer_generation_v1 import (  # noqa: E402
    clean,
    read_json,
    repo_relative,
    utc_timestamp,
    write_json,
)


REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_HUMAN_AUDIT_V1 = REVIEW_DIR / "rag_human_audit_packet_v1.json"
DEFAULT_REPORT_JSON = REPORT_DIR / "question_quality_gate_report_v1.json"
DEFAULT_REPORT_MD = REPORT_DIR / "question_quality_gate_report_v1.md"

NATURAL_LANGUAGE_QUESTION = "NATURAL_LANGUAGE_QUESTION"
UNSAFE_FOR_OFFICIAL_DENOMINATOR = "UNSAFE_FOR_OFFICIAL_DENOMINATOR"
QUESTION_WORDS = (
    "무엇",
    "어떻게",
    "언제",
    "어디",
    "누가",
    "얼마",
    "몇",
    "어떤",
    "왜",
    "인가",
    "인가요",
    "되나요",
    "나요",
    "있나요",
    "말해",
    "알려",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_gate(
        human_audit_v1_path=Path(args.human_audit_v1),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "input_rows": report["summary"]["input_rows"],
                "eligible_rows": report["summary"]["official_candidate_eligible_rows"],
                "rejected_rows": report["summary"]["rejected_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human-audit-v1", default=str(DEFAULT_HUMAN_AUDIT_V1))
    parser.add_argument("--output-report", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_REPORT_MD))
    return parser.parse_args(argv)


def run_gate(*, human_audit_v1_path: Path, output_report: Path, output_md: Path) -> dict[str, Any]:
    source = read_json(human_audit_v1_path)
    rows = [row for row in source.get("actionable_rows") or [] if isinstance(row, Mapping)]
    evaluated = [evaluate_row(row) for row in rows]
    counts = Counter(classification for row in evaluated for classification in row["classifications"])
    report = {
        "schema_version": "rag_question_quality_gate_report_v1",
        "generated_at": utc_timestamp(),
        "status": "QUESTION_QUALITY_GATE_COMPLETE",
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "source_artifacts": {"human_audit_v1": repo_relative(human_audit_v1_path)},
        "summary": {
            "input_rows": len(evaluated),
            "official_candidate_eligible_rows": sum(1 for row in evaluated if row["official_candidate_eligible"]),
            "rejected_rows": sum(1 for row in evaluated if not row["official_candidate_eligible"]),
            "classification_counts": dict(sorted(counts.items())),
        },
        "rows": evaluated,
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
        "validation": {"ok": True, "errors": []},
    }
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def evaluate_row(row: Mapping[str, Any]) -> dict[str, Any]:
    query_id = clean(row.get("query_id") or row.get("row_id"))
    track = clean(row.get("track"))
    question = clean(row.get("question") or row.get("rewritten_question_ko"))
    proposed_answer = clean(row.get("proposed_answer") or row.get("expected_answer_ko"))
    proposed_evidence = clean(
        row.get("proposed_evidence") or row.get("supporting_evidence_quote") or row.get("source_bound_evidence_text")
    )
    quality = classify_question(
        question,
        query_id=query_id,
        track=track,
        region_type=clean(row.get("region_type")),
        evidence_text=proposed_evidence,
        answer_text=proposed_answer,
    )
    classifications = list(quality["classifications"])
    if proposed_answer and proposed_answer == question:
        classifications.append("ANSWER_EQUALS_QUESTION")
    if not proposed_answer:
        classifications.append("EMPTY_PROPOSED_ANSWER")
    if not proposed_evidence:
        classifications.append("EMPTY_PROPOSED_EVIDENCE")
    if track == "pdf_business_ocr_mm" and clean(row.get("content_evidence_lane")) == "pdf_file_identity":
        classifications.append("PDF_FILE_IDENTITY_LANE")
    if track == "xlsx_business_structured":
        if query_id.startswith("expanded_xlsx_constraint") or question.startswith("expanded_xlsx_constraint"):
            classifications.append("XLSX_PLACEHOLDER_CONSTRAINT")
        if not clean(row.get("metric")):
            classifications.append("XLSX_MISSING_METRIC")
        if not clean(row.get("period")):
            classifications.append("XLSX_MISSING_PERIOD")
        if not clean(row.get("aggregation")) or not list_value(row.get("filters")):
            classifications.append("XLSX_MISSING_AGGREGATION_OR_FILTER")

    classifications = sorted(set(classifications))
    eligible = (
        classifications == [NATURAL_LANGUAGE_QUESTION]
        or (NATURAL_LANGUAGE_QUESTION in classifications and no_rejecting_classifications(classifications))
    )
    if not eligible and UNSAFE_FOR_OFFICIAL_DENOMINATOR not in classifications:
        classifications.append(UNSAFE_FOR_OFFICIAL_DENOMINATOR)
    return {
        "query_id": query_id,
        "track": track,
        "question": question,
        "primary_classification": quality["primary_classification"],
        "classifications": sorted(set(classifications)),
        "official_candidate_eligible": eligible,
    }


def classify_question(
    question: str,
    *,
    query_id: str = "",
    track: str = "",
    region_type: str = "",
    evidence_text: str = "",
    answer_text: str = "",
) -> dict[str, Any]:
    question = clean(question)
    query_id = clean(query_id)
    classifications: list[str] = []
    if not question:
        classifications.append("EMPTY_OR_MISSING_QUESTION")
    if query_id and question == query_id:
        classifications.append("PLACEHOLDER_QUERY_ID")
    if question.startswith("expanded_pdf_file_lookup"):
        classifications.append("PLACEHOLDER_QUERY_ID")
    if question.startswith("expanded_xlsx_constraint"):
        classifications.append("XLSX_PLACEHOLDER_CONSTRAINT")
    if answer_text and clean(answer_text) == question:
        classifications.append("ANSWER_EQUALS_QUESTION")

    lowered_region = region_type.lower()
    if track == "pdf_business_ocr_mm" or lowered_region:
        if lowered_region in {"title", "document_title", "heading", "section_heading"}:
            classifications.append("PDF_HEADING_OR_TITLE_AS_QUERY")
        if lowered_region in {"table", "table_label", "table_caption", "table_caption_footnote"}:
            classifications.append("PDF_TABLE_LABEL_AS_QUERY")
    if question and evidence_text and normalize(question) == normalize(evidence_text):
        classifications.append("PDF_CONTENT_SNIPPET_AS_QUERY")
    if is_bullet_or_fragment(question):
        classifications.append("PDF_OCR_FRAGMENT_AS_QUERY")
    if is_table_label(question):
        classifications.append("PDF_TABLE_LABEL_AS_QUERY")
    if is_title_like(question) and not is_natural_question(question):
        classifications.append("PDF_HEADING_OR_TITLE_AS_QUERY")
    if not classifications and is_natural_question(question):
        classifications.append(NATURAL_LANGUAGE_QUESTION)
    if not classifications:
        classifications.append("PDF_CONTENT_SNIPPET_AS_QUERY")
    return {
        "primary_classification": classifications[0],
        "classifications": sorted(set(classifications)),
    }


def no_rejecting_classifications(classifications: list[str]) -> bool:
    return not any(item != NATURAL_LANGUAGE_QUESTION for item in classifications)


def is_natural_question(question: str) -> bool:
    if not question or len(question) < 8:
        return False
    if question.endswith("?") or question.endswith("？"):
        return True
    return any(word in question for word in QUESTION_WORDS)


def is_bullet_or_fragment(question: str) -> bool:
    if not question:
        return False
    if question.startswith(("▪", "•", "-", "·")):
        return True
    if re.search(r"\s,\s|,\s*$", question):
        return True
    if len(question) > 24 and not is_natural_question(question) and not re.search(r"[.?!다요까]$", question):
        return True
    return False


def is_title_like(question: str) -> bool:
    if not question:
        return False
    if len(question) <= 24 and not any(ch in question for ch in "?.다요까"):
        return True
    if len(question.split()) <= 4 and not is_natural_question(question):
        return True
    return False


def is_table_label(question: str) -> bool:
    return bool(re.search(r"(표|Table|통계|추이|비교|현황)$", question, flags=re.IGNORECASE))


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", clean(value).lower())


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    return "\n".join(
        [
            "# Question Quality Gate Report v1",
            "",
            f"- Status: `{report.get('status')}`",
            f"- Input rows: `{summary.get('input_rows')}`",
            f"- Eligible rows: `{summary.get('official_candidate_eligible_rows')}`",
            f"- Rejected rows: `{summary.get('rejected_rows')}`",
            f"- Official metric input rows: `{report.get('official_metric_input_rows')}`",
            f"- Promotion evidence: `{str(report.get('promotion_evidence')).lower()}`",
        ]
    ) + "\n"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
