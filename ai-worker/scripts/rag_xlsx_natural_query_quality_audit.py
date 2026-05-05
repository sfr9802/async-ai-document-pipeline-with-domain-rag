"""Audit XLSX v3 naturalized query quality without running promotion."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_NATURALIZED_CSV = Path("eval/eval_queries/gold_queries_xlsx_v3_naturalized.csv")
DEFAULT_SOURCE_V2 = Path("eval/eval_queries/gold_queries_xlsx_v2.csv")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_xlsx_natural_query_quality_audit.json")

GENERIC_QUERY_TERMS = {
    "구분",
    "기간",
    "날짜",
    "합계",
    "총계",
    "비고",
    "내용",
    "표",
    "데이터",
    "현황",
    "대중교통구분",
    "승차총승객수",
    "장기요양기관이름",
    "증감률",
}

QUESTION_OR_REQUEST_MARKERS = {
    "인가요",
    "무엇",
    "어디",
    "찾아줘",
    "알려줘",
    "확인",
    "보여",
    "검색",
}

BINDING_COLUMNS = [
    "expected_file_name",
    "expected_document_version_id",
    "expected_chunk_type",
    "expected_location_type",
    "expected_sheet_name",
    "expected_cell_range",
    "expected_table_id",
    "expected_physical_page_index",
    "expected_page_no",
    "expected_page_label",
    "expected_bbox",
    "range_match_policy",
    "hidden_policy",
    "requires_formula_value",
    "requires_formatted_value",
    "requires_aggregation",
    "label_status",
    "v2_label_status",
    "v2_range_match_policy",
    "harness_range_match_policy",
    "contract_value_surface",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    naturalized_path = Path(args.naturalized_csv)
    source_path = Path(args.source_v2)
    rows = read_csv_rows(naturalized_path)
    source_rows = read_csv_rows(source_path) if source_path.exists() else []
    payload = build_audit(
        rows=rows,
        source_rows=source_rows,
        naturalized_path=naturalized_path,
        source_path=source_path,
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload["quality_status"] != "FAIL" else 1


def build_audit(
    *,
    rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    naturalized_path: Path,
    source_path: Path,
) -> dict[str, Any]:
    label_counts = Counter(row.get("v2_label_status", "unknown") for row in rows)
    hidden_terms = hidden_value_terms(rows)

    empty_query = [row for row in rows if not row.get("query", "").strip()]
    query_same_as_seed = [
        row
        for row in rows
        if normalize_query(row.get("query", "")) and normalize_query(row.get("query", "")) == normalize_query(row.get("query_seed") or row.get("original_query", ""))
    ]
    too_short = [row for row in rows if len(normalize_query(row.get("query", ""))) < 6]
    too_generic = [row for row in rows if is_too_generic(row.get("query", ""))]
    anchor_missing = [row for row in rows if not has_anchor_term(row)]
    hidden_value_in_positive = [
        row
        for row in rows
        if row.get("v2_label_status") == "positive" and query_contains_any(row.get("query", ""), hidden_terms)
    ]
    formula_contract_violations = [row for row in rows if formula_contract_violated(row)]
    date_format_contract_violations = [row for row in rows if date_format_contract_violated(row)]
    range_policy_missing = [row for row in rows if not row.get("range_match_policy", "").strip()]
    binding_changes = binding_change_rows(source_rows, rows)
    duplicate_groups, near_duplicate_pairs = duplicate_or_near_duplicate_queries(rows)
    unnatural_keyword_only = [row for row in rows if keyword_only_query(row.get("query", ""))]

    fatal_counts = {
        "empty_query_count": len(empty_query),
        "query_same_as_seed_count": len(query_same_as_seed),
        "too_short_query_count": len(too_short),
        "too_generic_query_count": len(too_generic),
        "anchor_term_missing_count": len(anchor_missing),
        "hidden_value_in_positive_query_count": len(hidden_value_in_positive),
        "formula_contract_violation_count": len(formula_contract_violations),
        "date_format_contract_violation_count": len(date_format_contract_violations),
        "range_policy_missing_count": len(range_policy_missing),
        "expected_binding_changed_count": len(binding_changes),
        "unnatural_keyword_only_query_count": len(unnatural_keyword_only),
    }
    warning_counts = {
        "duplicate_or_near_duplicate_query_count": len(duplicate_groups) + len(near_duplicate_pairs),
    }
    quality_status = "FAIL" if any(fatal_counts.values()) else (
        "PASS_WITH_WARNINGS" if any(warning_counts.values()) else "PASS"
    )

    harness_validation = validate_with_current_harness(rows)
    if not harness_validation.get("ok"):
        quality_status = "FAIL"

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_natural_query_quality_audit",
        "promotion_evidence": False,
        "evidence_role": "gold_v3_naturalized_query_quality",
        "source_naturalized_csv": str(naturalized_path),
        "source_v2_csv": str(source_path) if source_rows else None,
        "quality_status": quality_status,
        "row_count": len(rows),
        "positive_row_count": label_counts.get("positive", 0),
        "negative_hidden_policy_row_count": label_counts.get("negative_hidden_policy", 0),
        "deferred_row_count": label_counts.get("deferred", 0),
        "excluded_row_count": label_counts.get("excluded", 0),
        **fatal_counts,
        **warning_counts,
        "harness_validation": harness_validation,
        "v2_label_status_distribution": dict(sorted(label_counts.items())),
        "empty_query_ids": ids(empty_query),
        "query_same_as_seed_ids": ids(query_same_as_seed),
        "too_short_query_ids": ids(too_short),
        "too_generic_query_ids": ids(too_generic),
        "anchor_term_missing_query_ids": ids(anchor_missing),
        "hidden_value_in_positive_query_ids": ids(hidden_value_in_positive),
        "formula_contract_violation_query_ids": ids(formula_contract_violations),
        "date_format_contract_violation_query_ids": ids(date_format_contract_violations),
        "range_policy_missing_query_ids": ids(range_policy_missing),
        "expected_binding_changed_rows": binding_changes,
        "duplicate_query_groups": duplicate_groups,
        "near_duplicate_query_pairs": near_duplicate_pairs,
        "unnatural_keyword_only_query_ids": ids(unnatural_keyword_only),
        "hidden_value_terms_used_for_positive_scan": sorted(hidden_terms),
        "notes": [
            "This audit checks query-surface quality only and does not run retrieval or promotion.",
            "Expected binding comparison uses v2 query_id rows when eval/gold_queries_xlsx_v2.csv is available.",
            "Hidden negative rows remain valid in the mixed manifest but must be excluded from positive retrieval metrics.",
        ],
    }


def hidden_value_terms(rows: Iterable[Mapping[str, str]]) -> set[str]:
    terms: set[str] = set()
    for row in rows:
        if row.get("v2_label_status") == "negative_hidden_policy":
            for value in (row.get("query_seed", ""), row.get("original_query", ""), row.get("must_not_contain_terms", "")):
                terms.update(term for term in split_terms(value) if len(normalize_query(term)) >= 2)
        elif row.get("bucket") == "xlsx_hidden_policy" and row.get("v2_label_status") == "positive":
            seed = (row.get("query_seed") or row.get("original_query") or "").strip()
            if seed:
                terms.add(seed)
    return terms


def has_anchor_term(row: Mapping[str, str]) -> bool:
    query = row.get("query", "")
    candidates: list[str] = []
    for value in (
        row.get("must_contain_terms", ""),
        row.get("expected_answer_text", ""),
        row.get("query_seed", ""),
        row.get("original_query", ""),
    ):
        candidates.extend(split_terms(value))
    compact_query = normalize_query(query)
    for term in candidates:
        compact_term = normalize_query(term)
        if len(compact_term) >= 2 and compact_term in compact_query:
            return True
    return False


def formula_contract_violated(row: Mapping[str, str]) -> bool:
    expects_formula = row.get("requires_formula_value", "").lower() == "true" or row.get("contract_value_surface") == "RAW_FORMULA"
    if not expects_formula:
        return False
    query = row.get("query", "")
    if "수식" in query:
        return False
    formula_terms = [term for term in split_terms(row.get("must_contain_terms", "")) if "/" in term or "-" in term or "=" in term]
    return not any(term in query for term in formula_terms)


def date_format_contract_violated(row: Mapping[str, str]) -> bool:
    if row.get("contract_value_surface") != "DATE_FORMATTED_VALUE":
        return False
    query = row.get("query", "")
    date_terms = [
        term
        for term in split_terms(";".join([row.get("must_contain_terms", ""), row.get("query_seed", ""), row.get("original_query", "")]))
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", term)
    ]
    if any(term in query for term in date_terms):
        return False
    return "날짜" not in query and "지정일자" not in query


def binding_change_rows(source_rows: list[Mapping[str, str]], rows: list[Mapping[str, str]]) -> list[dict[str, Any]]:
    if not source_rows:
        return []
    source_by_id = {row.get("query_id", ""): row for row in source_rows}
    changes: list[dict[str, Any]] = []
    for row in rows:
        source = source_by_id.get(row.get("query_id", ""))
        if not source:
            changes.append({"query_id": row.get("query_id", ""), "changed_columns": ["query_id_missing_from_v2"]})
            continue
        changed = [
            column
            for column in BINDING_COLUMNS
            if column in source and str(source.get(column, "")) != str(row.get(column, ""))
        ]
        if changed:
            changes.append({"query_id": row.get("query_id", ""), "changed_columns": changed})
    return changes


def duplicate_or_near_duplicate_queries(rows: list[Mapping[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_normalized: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        normalized = normalize_query(row.get("query", ""))
        if normalized:
            by_normalized[normalized].append(row)
    duplicate_groups = [
        {
            "normalized_query": key,
            "query_ids": [row.get("query_id", "") for row in grouped],
            "queries": sorted({row.get("query", "") for row in grouped}),
        }
        for key, grouped in sorted(by_normalized.items())
        if len(grouped) > 1
    ]

    near_duplicate_pairs: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for left_index, left in enumerate(rows):
        for right in rows[left_index + 1:]:
            if first_anchor(left) != first_anchor(right):
                continue
            left_query = normalize_query(left.get("query", ""))
            right_query = normalize_query(right.get("query", ""))
            if len(left_query) < 10 or len(right_query) < 10:
                continue
            ratio = SequenceMatcher(None, left_query, right_query).ratio()
            if ratio >= 0.96:
                pair = tuple(sorted([left.get("query_id", ""), right.get("query_id", "")]))
                if pair not in seen_pairs:
                    near_duplicate_pairs.append(
                        {
                            "query_ids": list(pair),
                            "queries": [left.get("query", ""), right.get("query", "")],
                            "similarity": round(ratio, 4),
                        }
                    )
                    seen_pairs.add(pair)
    return duplicate_groups, near_duplicate_pairs


def first_anchor(row: Mapping[str, str]) -> str:
    for value in (row.get("must_contain_terms", ""), row.get("query_seed", ""), row.get("expected_answer_text", "")):
        for term in split_terms(value):
            normalized = normalize_query(term)
            if len(normalized) >= 2:
                return normalized
    return ""


def is_too_generic(query: str) -> bool:
    compact = normalize_query(query)
    return compact in {normalize_query(term) for term in GENERIC_QUERY_TERMS}


def keyword_only_query(query: str) -> bool:
    compact = normalize_query(query)
    if not compact:
        return True
    if any(marker in query for marker in QUESTION_OR_REQUEST_MARKERS):
        return False
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", query)
    return len(tokens) <= 3


def query_contains_any(query: str, terms: set[str]) -> bool:
    compact = normalize_query(query)
    return any(normalize_query(term) and normalize_query(term) in compact for term in terms)


def split_terms(value: str) -> list[str]:
    terms: list[str] = []
    for raw_term in str(value or "").replace(",", ";").split(";"):
        term = raw_term.strip()
        if not term:
            continue
        terms.append(term)
        terms.extend(part for part in re.split(r"\s+", term) if part)
    return terms


def normalize_query(value: str) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").lower(), flags=re.UNICODE)


def ids(rows: Iterable[Mapping[str, str]]) -> list[str]:
    return [str(row.get("query_id", "")) for row in rows]


def validate_with_current_harness(rows: list[dict[str, str]]) -> dict[str, Any]:
    ai_worker = Path(__file__).resolve().parents[1]
    root = ai_worker.parent
    if str(ai_worker) not in sys.path:
        sys.path.insert(0, str(ai_worker))
    try:
        from eval.harness.rag_ingestion_retrieval_eval import validate_gold_rows  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - defensive CLI report path
        return {
            "ok": False,
            "import_error": f"{type(exc).__name__}: {exc}",
            "row_count": len(rows),
            "error_count": None,
            "row_error_count": None,
        }

    result = validate_gold_rows(rows)
    return {
        "ok": result.ok,
        "row_count": result.row_count,
        "error_count": len(result.errors),
        "row_error_count": len(result.row_errors),
        "bucket_counts": result.bucket_counts,
        "sample_errors": result.errors[:10],
    }


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--naturalized-csv", default=str(DEFAULT_NATURALIZED_CSV))
    parser.add_argument("--source-v2", default=str(DEFAULT_SOURCE_V2))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
