"""Audit XLSX answer-path code for gold-set-specific overfit.

The audit is diagnostic-only. It scans production answer-path source files for
hardcoded query IDs, gold answer literals, expected-locator promotion patterns,
domain literals, and default-enabled alias maps. It does not run retrieval,
change gold files, or select answer evidence.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
DEFAULT_XLSX_REVIEW = AI_WORKER_ROOT / "eval" / "review" / "gold_set_review" / "xlsx_gold_review_pack.csv"
DEFAULT_OUTPUT_JSON = Path(tempfile.gettempdir()) / "rag_pdf_xlsx_anti_overfit_audit.json"
DEFAULT_OUTPUT_CSV = Path(tempfile.gettempdir()) / "rag_pdf_xlsx_anti_overfit_audit.csv"
DEFAULT_SCAN_FILES = [
    AI_WORKER_ROOT / "eval" / "harness" / "pdf_xlsx_answer_evidence_serializer.py",
    AI_WORKER_ROOT / "eval" / "harness" / "pdf_xlsx_deterministic_answer_compiler.py",
    AI_WORKER_ROOT / "scripts" / "rag_pdf_xlsx_answer_generation_input_builder.py",
    AI_WORKER_ROOT / "scripts" / "rag_pdf_xlsx_local_llm_answer_runner.py",
    AI_WORKER_ROOT / "scripts" / "rag_pdf_xlsx_answer_shape_evaluator.py",
    AI_WORKER_ROOT / "scripts" / "rag_pdf_xlsx_llm_quality_benchmark.py",
    AI_WORKER_ROOT / "scripts" / "rag_pdf_xlsx_answer_quality_review_packet.py",
]

SCHEMA_VERSION = "rag_pdf_xlsx_anti_overfit_audit_v1"
GOLD_ANSWER_FIELDS = {
    "expected_answer",
    "expected_answer_text",
    "expected_answer_summary",
    "must_contain",
    "must_contain_terms",
}
EXPECTED_LOCATOR_FIELDS = {
    "expected_evidence_location",
    "expected_current_evidence_location",
    "expected_file_name",
    "expected_sheet_name",
    "expected_cell_range",
    "expected_table_id",
    "expected_document_version_id",
}
LANGUAGE_INTENT_STOPWORDS = {
    "찾아줘",
    "찾아",
    "알려줘",
    "알려",
    "어디야",
    "어디",
    "쪽",
    "자료",
    "정보",
    "관련",
    "위치",
    "행",
    "값",
    "좀",
    "주세요",
    "뭐야",
    "뭐",
    "몇",
    "어느",
    "find",
    "show",
    "info",
    "row",
}
GENERIC_AUDIT_TERMS = {
    "answer",
    "bbox",
    "cell",
    "chunk",
    "citation",
    "content",
    "context",
    "diagnostic",
    "docv",
    "evidence",
    "expected",
    "file",
    "gold",
    "header",
    "hidden",
    "locator",
    "mapping",
    "page",
    "policy",
    "query",
    "range",
    "review",
    "row",
    "score",
    "section",
    "sheet",
    "source",
    "table",
    "text",
    "value",
}
REQUIRED_METRICS = [
    "hardcoded_query_id_count",
    "hardcoded_gold_answer_literal_count",
    "hardcoded_expected_locator_usage_count",
    "hardcoded_domain_entity_literal_count",
    "hardcoded_domain_alias_count",
    "gold_field_used_as_answer_evidence_count",
    "gold_field_used_as_candidate_selection_count",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    review_paths = [Path(path) for path in args.xlsx_review]
    scan_files = [Path(path) for path in args.scan_file] if args.scan_file else DEFAULT_SCAN_FILES
    report = run_audit(
        scan_files=scan_files,
        review_paths=review_paths,
        output_json=Path(args.output_json),
        output_csv=Path(args.output_csv),
    )
    print(json.dumps({key: report[key] for key in ["status", *REQUIRED_METRICS]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xlsx-review",
        action="append",
        default=[str(DEFAULT_XLSX_REVIEW)],
        help="XLSX review/gold CSV used only to derive forbidden literals for source scanning.",
    )
    parser.add_argument(
        "--scan-file",
        action="append",
        default=[],
        help="Production answer-path source file to scan. Defaults to the XLSX/PDF answer path.",
    )
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    return parser.parse_args(argv)


def run_audit(
    *,
    scan_files: list[Path],
    review_paths: list[Path],
    output_json: Path,
    output_csv: Path,
) -> dict[str, Any]:
    generated_at = utc_timestamp()
    gold = derive_gold_signals(review_paths)
    findings = scan_source_files(scan_files, gold)
    counts = Counter(finding["category"] for finding in findings)
    metrics = {metric: counts.get(metric, 0) for metric in REQUIRED_METRICS}
    status = "PASS" if all(value == 0 for value in metrics.values()) else "FAIL"
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "scan_scope": "production_xlsx_pdf_answer_path",
        "stopword_source": "language_intent",
        "domain_aliases_enabled_by_default": False,
        "gold_signals_source": [artifact_entry(path) for path in review_paths],
        "scan_files": [artifact_entry(path) for path in scan_files],
        "gold_signal_counts": {
            "query_ids": len(gold["query_ids"]),
            "gold_answer_literals": len(gold["gold_answer_literals"]),
            "domain_terms": len(gold["domain_terms"]),
            "locator_literals": len(gold["locator_literals"]),
        },
        "findings": findings,
        **metrics,
        "assertions": {
            "no_hardcoded_query_ids": metrics["hardcoded_query_id_count"] == 0,
            "no_hardcoded_gold_answer_literals": metrics["hardcoded_gold_answer_literal_count"] == 0,
            "no_expected_locator_used_for_answer_selection": metrics[
                "hardcoded_expected_locator_usage_count"
            ]
            == 0,
            "no_domain_entity_literals_in_production_logic": metrics[
                "hardcoded_domain_entity_literal_count"
            ]
            == 0,
            "no_default_domain_alias_map": metrics["hardcoded_domain_alias_count"] == 0,
            "no_gold_fields_as_answer_evidence": metrics[
                "gold_field_used_as_answer_evidence_count"
            ]
            == 0,
            "no_gold_fields_as_candidate_selection": metrics[
                "gold_field_used_as_candidate_selection_count"
            ]
            == 0,
        },
        "guardrails": {
            "retrieval_tuning_run": False,
            "reranking_run": False,
            "parser_expansion_run": False,
            "threshold_relaxation_run": False,
            "db_mutation_run": False,
            "searchunit_mutation_run": False,
            "gold_file_mutation_run": False,
        },
    }
    write_json(output_json, report)
    write_csv(output_csv, report)
    return report


def derive_gold_signals(paths: Iterable[Path]) -> dict[str, set[str]]:
    query_ids: set[str] = set()
    gold_answer_literals: set[str] = set()
    locator_literals: set[str] = set()
    domain_terms: set[str] = set()
    for path in paths:
        for row in read_csv_rows(path):
            query_id = clean(row.get("query_id"))
            if query_id:
                query_ids.add(query_id)
            for key, value in row.items():
                key_norm = clean(key).lower()
                text = clean(value)
                if not text:
                    continue
                if key_norm in GOLD_ANSWER_FIELDS:
                    gold_answer_literals.update(split_literal_values(text))
                if key_norm in EXPECTED_LOCATOR_FIELDS or key_norm.startswith("expected_"):
                    locator_literals.update(split_literal_values(text))
                if key_norm in GOLD_ANSWER_FIELDS or key_norm == "query":
                    domain_terms.update(extract_domain_terms(text))
    gold_answer_literals = {item for item in gold_answer_literals if scanworthy_literal(item)}
    locator_literals = {item for item in locator_literals if scanworthy_literal(item)}
    domain_terms = {item for item in domain_terms if scanworthy_domain_term(item)}
    return {
        "query_ids": query_ids,
        "gold_answer_literals": gold_answer_literals,
        "locator_literals": locator_literals,
        "domain_terms": domain_terms,
    }


def scan_source_files(scan_files: Iterable[Path], gold: Mapping[str, set[str]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in scan_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        string_literals = python_string_literals(path, text)
        findings.extend(find_hardcoded_literals(path, string_literals, gold))
        findings.extend(find_dangerous_gold_field_usage(path, lines))
    return findings


def find_hardcoded_literals(
    path: Path,
    string_literals: Iterable[dict[str, Any]],
    gold: Mapping[str, set[str]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    query_ids = gold["query_ids"]
    answer_literals = gold["gold_answer_literals"]
    domain_terms = gold["domain_terms"]
    for literal in string_literals:
        value = clean(literal["value"])
        if not value:
            continue
        if value in query_ids:
            findings.append(finding(path, literal["line"], "hardcoded_query_id_count", value))
        if value in answer_literals:
            findings.append(finding(path, literal["line"], "hardcoded_gold_answer_literal_count", value))
        if value in domain_terms:
            findings.append(finding(path, literal["line"], "hardcoded_domain_entity_literal_count", value))
        if alias_context(literal["line_text"]) and (
            value in domain_terms or value in answer_literals
        ):
            findings.append(finding(path, literal["line"], "hardcoded_domain_alias_count", value))
    return findings


def find_dangerous_gold_field_usage(path: Path, lines: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        if not gold_field_name_present(lowered):
            continue
        if diagnostic_only_line(lowered):
            continue
        if answer_evidence_context(lowered):
            findings.append(
                finding(path, index, "gold_field_used_as_answer_evidence_count", line.strip())
            )
        if candidate_selection_context(lowered):
            findings.append(
                finding(path, index, "gold_field_used_as_candidate_selection_count", line.strip())
            )
        if expected_locator_selection_context(lowered):
            findings.append(
                finding(path, index, "hardcoded_expected_locator_usage_count", line.strip())
            )
    return findings


def python_string_literals(path: Path, text: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.splitlines()
    literals: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            line_no = getattr(node, "lineno", 0)
            literals.append(
                {
                    "value": node.value,
                    "line": line_no,
                    "line_text": lines[line_no - 1] if 1 <= line_no <= len(lines) else "",
                    "path": path,
                }
            )
    return literals


def answer_evidence_context(line: str) -> bool:
    return any(token in line for token in ("evidence", "content", "summary", "value", "answer_allowed"))


def candidate_selection_context(line: str) -> bool:
    return any(token in line for token in ("candidate", "select", "bind", "query_bound", "row_values"))


def expected_locator_selection_context(line: str) -> bool:
    return "expected" in line and "locator" in line and any(
        token in line for token in ("content_source", "citation", "selected", "answer_allowed", "query_bound")
    )


def gold_field_name_present(line: str) -> bool:
    return any(
        field in line
        for field in (
            "expected_answer",
            "must_contain",
            "expected_evidence_location",
            "expected_evidence_locator",
        )
    )


def diagnostic_only_line(line: str) -> bool:
    return any(
        token in line
        for token in (
            '"expected_answer',
            '"expected_evidence',
            '"must_contain',
            "answer_has_content_target",
            "keyword_echo_only",
            "location_only_answer",
            "locator_text",
            "diagnostic_only",
            "diagnostic-only",
            "diagnostic only",
            "expected_locator_promoted",
            "locator_promoted_from_expected",
            "row_out",
            "csv_fields",
        )
    )


def alias_context(line: str) -> bool:
    return bool(re.search(r"alias|aliases|synonym|header_alias|domain_alias|mapping", line, flags=re.IGNORECASE))


def split_literal_values(value: str) -> set[str]:
    return {clean(item) for item in re.split(r"[;|,\n\r\t]+", value) if clean(item)}


def extract_domain_terms(value: str) -> set[str]:
    terms = set()
    for token in re.findall(r"[0-9A-Za-z가-힣]+", value):
        token = clean(token)
        if not token:
            continue
        if normalize_anchor(token) in {normalize_anchor(item) for item in LANGUAGE_INTENT_STOPWORDS}:
            continue
        terms.add(token)
    return terms


def scanworthy_literal(value: str) -> bool:
    text = clean(value)
    if len(text) < 2:
        return False
    if normalize_anchor(text) in {normalize_anchor(item) for item in LANGUAGE_INTENT_STOPWORDS}:
        return False
    return True


def scanworthy_domain_term(value: str) -> bool:
    text = clean(value)
    if text.lower() in GENERIC_AUDIT_TERMS:
        return False
    if not re.search(r"[가-힣]", text) and not re.fullmatch(r"\d{4,}", text):
        return False
    if len(normalize_anchor(text)) < 3:
        return False
    if re.fullmatch(r"\d{1,3}", text):
        return False
    return scanworthy_literal(text)


def finding(path: Path, line: int, category: str, literal: str) -> dict[str, Any]:
    return {
        "category": category,
        "file": repo_relative(path),
        "line": line,
        "literal_sha256": sha256_text(literal),
        "literal_preview": redact_literal(literal),
    }


def redact_literal(value: str) -> str:
    text = clean(value)
    if len(text) <= 16:
        return text
    return text[:8] + "..." + text[-4:]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for metric in REQUIRED_METRICS:
            writer.writerow({"metric": metric, "value": report.get(metric, 0)})
        writer.writerow({"metric": "promotion_evidence", "value": False})
        writer.writerow({"metric": "external_live_llm_run", "value": False})
        writer.writerow({"metric": "optional_judge_run", "value": False})


def artifact_entry(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(clean(value).encode("utf-8")).hexdigest()


def normalize_anchor(value: object) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", clean(value)).lower()


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
