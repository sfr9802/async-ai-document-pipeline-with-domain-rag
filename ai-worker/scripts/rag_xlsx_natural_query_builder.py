"""Build XLSX gold v3 naturalized query manifests without promotion.

The v3 manifest is a candidate query-surface refresh over v2. It preserves
the v2 expected file/sheet/range/document binding and range policy, replaces
only the harness ``query`` surface with manually naturalized Korean questions,
and keeps the original query as ``original_query``/``query_seed``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_XLSX_V2 = Path("eval/eval_queries/gold_queries_xlsx_v2.csv")
DEFAULT_FORMULA_DATE_REVIEW = Path("eval/reports/rag-ingestion/rag_xlsx_formula_date_contract_review.json")
DEFAULT_HIDDEN_NEGATIVE_PLAN = Path("eval/reports/rag-ingestion/rag_xlsx_hidden_negative_eval_plan.json")
DEFAULT_CHUNK_GRANULARITY_REVIEW = Path("eval/reports/rag-ingestion/rag_xlsx_chunk_granularity_review.json")
DEFAULT_NATURALIZED_CSV = Path("eval/eval_queries/gold_queries_xlsx_v3_naturalized.csv")
DEFAULT_POSITIVE_CSV = Path("eval/eval_queries/gold_queries_xlsx_v3_positive.csv")
DEFAULT_BUILD_REPORT = Path("eval/reports/rag-ingestion/rag_xlsx_natural_query_build_report.json")
DEFAULT_POSITIVE_EXPORT_REPORT = Path("eval/reports/rag-ingestion/rag_xlsx_v3_positive_export_report.json")
DEFAULT_DATASET_ID = "gold_queries_xlsx_v3_naturalized"
DEFAULT_DATASET_VERSION = "xlsx_v3_naturalized_candidate_manifest_50"
DEFAULT_POSITIVE_DATASET_ID = "gold_queries_xlsx_v3_positive"
DEFAULT_POSITIVE_DATASET_VERSION = "xlsx_v3_positive_diagnostic_manifest"

EXTRA_V3_COLUMNS = [
    "original_query",
    "query_seed",
    "naturalization_status",
    "naturalization_strategy",
    "naturalization_anchor_terms",
    "naturalization_notes",
]

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
    "label_status",
    "v2_label_status",
    "v2_range_match_policy",
    "harness_range_match_policy",
    "contract_value_surface",
]

NATURALIZED_QUERIES = {
    "gq_xlsx_lookup_001": "1호선 승차 쪽 찾아줘.",
    "gq_xlsx_lookup_002": "신분당선 어디쯤 있어?",
    "gq_xlsx_lookup_003": "의정부경전철 승차 자료 어디야?",
    "gq_xlsx_lookup_004": "우이신설선 201905 행 찾아줘.",
    "gq_xlsx_lookup_005": "경인선 월별 승차 찾아줘.",
    "gq_xlsx_lookup_006": "수인선 월별 승차 찾아줘.",
    "gq_xlsx_lookup_007": "청운노인요양원 주소 쪽 찾아줘.",
    "gq_xlsx_lookup_008": "부여효요양원 주소 쪽 찾아줘.",
    "gq_xlsx_header_ambiguous_001": "대중교통구분 표 대충 찾아줘.",
    "gq_xlsx_header_ambiguous_002": "승차총승객수 있는 데 찾아줘.",
    "gq_xlsx_header_ambiguous_003": "청운노인요양원 이름 나오는 쪽 찾아줘.",
    "gq_xlsx_header_ambiguous_004": "예산군 법정동명 쪽 찾아줘.",
    "gq_xlsx_formula_value_001": "증감률 수식 있는 데 찾아줘.",
    "gq_xlsx_formula_value_002": "D4/E4-1 수식 어디야?",
    "gq_xlsx_formula_value_003": "D5/E5-1 수식 어디야?",
    "gq_xlsx_date_number_format_001": "2008-06-25 지정일자 찾아줘.",
    "gq_xlsx_date_number_format_002": "2015-06-02 지정일자 찾아줘.",
    "gq_xlsx_date_number_format_003": "163,443,126 승객수 찾아줘.",
    "gq_xlsx_date_number_format_004": "12,000,000,000 매출 쪽 찾아줘.",
    "gq_xlsx_hidden_policy_001": "secret 숨겨진 거 검색해줘.",
    "gq_xlsx_hidden_policy_002": "숨김 시트 검색해줘.",
    "gq_xlsx_hidden_policy_003": "증감률 보이는 데 찾아줘.",
    "gq_xlsx_aggregation_001": "버스 승차 쪽 찾아줘.",
    "gq_xlsx_aggregation_002": "1호선 승객 쪽 찾아줘.",
    "gq_xlsx_aggregation_003": "매출 증감률 수식 쪽 찾아줘.",
    "gq_mixed_text_table_001": "과학기술자료실 표 찾아줘.",
    "gq_mixed_text_table_002": "도서정보 표 어디야?",
    "gq_mixed_text_table_003": "국립과천과학관 자료 쪽 찾아줘.",
    "gq_auto_012": "5호선 승차 쪽 찾아줘.",
    "gq_auto_013": "진명실버홈 행 찾아줘.",
    "gq_auto_017": "우이신설선 승차 쪽 찾아줘.",
    "gq_auto_018": "하얀민들레노인요양원 행 찾아줘.",
    "gq_auto_022": "9호선 승차 쪽 찾아줘.",
    "gq_auto_023": "해뜨는요양원2 행 찾아줘.",
    "gq_auto_027": "신분당선 승차 자료 쪽 찾아줘.",
    "gq_auto_028": "해오름요양원 행 찾아줘.",
    "gq_auto_031": "8호선 승차 쪽 찾아줘.",
    "gq_auto_032": "달서한독요양원 행 찾아줘.",
    "gq_auto_033": "정성요양원 행 찾아줘.",
    "gq_auto_034": "의정부경전철 승차 쪽 찾아줘.",
    "gq_auto_035": "3호선 승차 쪽 찾아줘.",
    "gq_auto_036": "경인선 승차 쪽 찾아줘.",
    "gq_auto_037": "안산선 승차 쪽 찾아줘.",
    "gq_auto_038": "일산선 승차 쪽 찾아줘.",
    "gq_auto_039": "경의선 승차 쪽 찾아줘.",
    "gq_auto_040": "수인선 승차 쪽 찾아줘.",
    "gq_auto_041": "인하요양원 행 찾아줘.",
    "gq_auto_042": "축복전문요양원 행 찾아줘.",
    "gq_auto_043": "신논현요양원 행 찾아줘.",
    "gq_auto_044": "인천은빛요양원 행 찾아줘.",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_path = Path(args.xlsx_v2)
    naturalized_path = Path(args.output_csv)
    positive_path = Path(args.positive_csv)
    source_rows = read_csv_rows(source_path)
    formula_date = read_optional_json(Path(args.formula_date_review))
    hidden_plan = read_optional_json(Path(args.hidden_negative_plan))
    chunk_review = read_optional_json(Path(args.chunk_granularity_review))

    naturalized_rows = build_naturalized_rows(source_rows)
    positive_rows = select_positive_rows(naturalized_rows)

    fieldnames = v3_fieldnames(source_rows)
    write_csv(naturalized_path, naturalized_rows, fieldnames)
    write_csv(positive_path, positive_rows, fieldnames)

    source_sha = sha256_file(source_path)
    naturalized_sha = sha256_file(naturalized_path)
    positive_sha = sha256_file(positive_path)
    naturalized_validation = validate_with_current_harness(naturalized_rows)
    positive_validation = validate_with_current_harness(positive_rows)
    binding_changes = binding_change_rows(source_rows, naturalized_rows)

    build_report = build_report_payload(
        args=args,
        source_rows=source_rows,
        naturalized_rows=naturalized_rows,
        positive_rows=positive_rows,
        source_sha=source_sha,
        naturalized_sha=naturalized_sha,
        positive_sha=positive_sha,
        naturalized_validation=naturalized_validation,
        positive_validation=positive_validation,
        binding_changes=binding_changes,
        formula_date=formula_date,
        hidden_plan=hidden_plan,
        chunk_review=chunk_review,
    )
    positive_export_report = build_positive_export_report(
        args=args,
        source_rows=source_rows,
        naturalized_rows=naturalized_rows,
        positive_rows=positive_rows,
        naturalized_sha=naturalized_sha,
        positive_sha=positive_sha,
        positive_validation=positive_validation,
    )
    write_json(Path(args.build_report), build_report)
    write_json(Path(args.positive_export_report), positive_export_report)
    print_report(build_report)
    return 0


def build_naturalized_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    missing = sorted(set(row.get("query_id", "") for row in rows) - set(NATURALIZED_QUERIES))
    if missing:
        raise ValueError("missing naturalized query mappings: " + ", ".join(missing))
    unexpected = sorted(set(NATURALIZED_QUERIES) - {row.get("query_id", "") for row in rows})
    if unexpected:
        raise ValueError("naturalized query mappings have no v2 row: " + ", ".join(unexpected))

    output: list[dict[str, str]] = []
    for row in rows:
        query_id = row["query_id"]
        original_query = row.get("query", "")
        next_row = dict(row)
        next_row["query"] = NATURALIZED_QUERIES[query_id]
        next_row["original_query"] = original_query
        next_row["query_seed"] = original_query
        next_row["naturalization_status"] = "naturalized"
        next_row["naturalization_strategy"] = strategy_for_row(row)
        next_row["naturalization_anchor_terms"] = anchor_terms_for_row(row)
        next_row["naturalization_notes"] = notes_for_row(row)
        output.append(next_row)
    return output


def select_positive_rows(rows: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    return [
        dict(row)
        for row in rows
        if row.get("v2_label_status") == "positive"
        and row.get("label_status") == "bound"
        and row.get("expected_location_type") == "xlsx"
    ]


def strategy_for_row(row: Mapping[str, str]) -> str:
    label = row.get("v2_label_status", "")
    bucket = row.get("bucket", "")
    purpose = row.get("eval_purpose", "")
    surface = row.get("contract_value_surface", "")
    if label == "negative_hidden_policy":
        return "hidden_policy_negative_natural_language_probe"
    if surface == "RAW_FORMULA" or row.get("requires_formula_value") == "true":
        return "raw_formula_contract_question"
    if surface == "DATE_FORMATTED_VALUE":
        return "formatted_date_contract_question"
    if purpose == "table_range_policy":
        return "table_range_policy_question"
    if purpose == "chunk_granularity":
        return "chunk_granularity_question"
    if bucket == "xlsx_aggregation":
        return "table_or_row_range_question"
    return "lookup_question"


def anchor_terms_for_row(row: Mapping[str, str]) -> str:
    terms: list[str] = []
    for value in (row.get("must_contain_terms", ""), row.get("expected_answer_text", ""), row.get("query", "")):
        for term in split_terms(value):
            if term and term not in terms:
                terms.append(term)
    return ";".join(terms[:8])


def notes_for_row(row: Mapping[str, str]) -> str:
    notes = [
        "manual_v3_naturalized_query",
        "preserves_v2_expected_binding",
        "promotion_evidence_false",
    ]
    if row.get("v2_label_status") != "positive":
        notes.append("not_in_positive_retrieval_manifest")
    if row.get("v2_label_status") == "negative_hidden_policy":
        notes.append("hidden_negative_metric_only")
    if row.get("contract_value_surface") in {"RAW_FORMULA", "DATE_FORMATTED_VALUE"}:
        notes.append(f"contract_value_surface={row.get('contract_value_surface')}")
    return "; ".join(notes)


def split_terms(value: str) -> list[str]:
    terms: list[str] = []
    for raw_term in str(value or "").replace(",", ";").split(";"):
        term = raw_term.strip()
        if not term:
            continue
        terms.append(term)
        terms.extend(part for part in re.split(r"\s+", term) if part)
    return terms


def binding_change_rows(source_rows: list[Mapping[str, str]], output_rows: list[Mapping[str, str]]) -> list[dict[str, Any]]:
    source_by_id = {row.get("query_id", ""): row for row in source_rows}
    changes: list[dict[str, Any]] = []
    for row in output_rows:
        source = source_by_id.get(row.get("query_id", ""), {})
        changed = [
            column
            for column in BINDING_COLUMNS
            if column in source and str(source.get(column, "")) != str(row.get(column, ""))
        ]
        if changed:
            changes.append({"query_id": row.get("query_id", ""), "changed_columns": changed})
    return changes


def v3_fieldnames(rows: list[Mapping[str, str]]) -> list[str]:
    if not rows:
        return EXTRA_V3_COLUMNS
    fieldnames = list(rows[0].keys())
    for column in EXTRA_V3_COLUMNS:
        if column not in fieldnames:
            fieldnames.append(column)
    return fieldnames


def build_report_payload(
    *,
    args: argparse.Namespace,
    source_rows: list[Mapping[str, str]],
    naturalized_rows: list[Mapping[str, str]],
    positive_rows: list[Mapping[str, str]],
    source_sha: str,
    naturalized_sha: str,
    positive_sha: str,
    naturalized_validation: Mapping[str, Any],
    positive_validation: Mapping[str, Any],
    binding_changes: list[Mapping[str, Any]],
    formula_date: Mapping[str, Any],
    hidden_plan: Mapping[str, Any],
    chunk_review: Mapping[str, Any],
) -> dict[str, Any]:
    label_counts = Counter(row.get("v2_label_status", "unknown") for row in naturalized_rows)
    bucket_counts = Counter(row.get("bucket", "unknown") for row in naturalized_rows)
    strategy_counts = Counter(row.get("naturalization_strategy", "unknown") for row in naturalized_rows)
    same_as_seed = [
        row.get("query_id", "")
        for row in naturalized_rows
        if row.get("query", "").strip() == row.get("query_seed", "").strip()
    ]
    hidden_negative_ids = [
        row.get("query_id", "")
        for row in naturalized_rows
        if row.get("v2_label_status") == "negative_hidden_policy"
    ]
    excluded_from_positive = [
        row.get("query_id", "")
        for row in naturalized_rows
        if row.get("query_id", "") not in {positive.get("query_id", "") for positive in positive_rows}
    ]

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED" if not binding_changes else "COMPLETED_WITH_BINDING_WARNINGS",
        "report_role": "xlsx_natural_query_v3_build_report",
        "promotion_evidence": False,
        "evidence_role": "gold_v3_naturalized_candidate_manifest",
        "source_xlsx_v2": str(args.xlsx_v2),
        "source_xlsx_v2_sha256": source_sha,
        "source_formula_date_review": str(args.formula_date_review),
        "source_hidden_negative_plan": str(args.hidden_negative_plan),
        "source_chunk_granularity_review": str(args.chunk_granularity_review),
        "source_report_statuses": {
            "formula_date_contract_review": formula_date.get("status"),
            "hidden_negative_eval_plan": hidden_plan.get("status"),
            "chunk_granularity_review": chunk_review.get("status"),
        },
        "dataset": {
            "path": str(args.output_csv),
            "dataset_id": args.dataset_id,
            "version": args.dataset_version,
            "row_count": len(naturalized_rows),
            "sha256": naturalized_sha,
        },
        "positive_dataset": {
            "path": str(args.positive_csv),
            "dataset_id": args.positive_dataset_id,
            "version": args.positive_dataset_version,
            "row_count": len(positive_rows),
            "sha256": positive_sha,
        },
        "row_count": len(naturalized_rows),
        "source_row_count": len(source_rows),
        "positive_row_count": len(positive_rows),
        "v2_label_status_distribution": dict(sorted(label_counts.items())),
        "bucket_distribution": dict(sorted(bucket_counts.items())),
        "naturalization_strategy_distribution": dict(sorted(strategy_counts.items())),
        "query_seed_preserved_count": sum(1 for row in naturalized_rows if row.get("query_seed")),
        "original_query_preserved_count": sum(1 for row in naturalized_rows if row.get("original_query")),
        "query_same_as_seed_count": len(same_as_seed),
        "query_same_as_seed_query_ids": same_as_seed,
        "hidden_negative_query_ids": hidden_negative_ids,
        "positive_manifest_excludes_query_ids": excluded_from_positive,
        "binding_preserved": not binding_changes,
        "binding_changed_count": len(binding_changes),
        "binding_changed_rows": list(binding_changes),
        "naturalized_harness_validation": dict(naturalized_validation),
        "positive_harness_validation": dict(positive_validation),
        "baseline_status": {
            "promotion_executed": False,
            "promotion_evidence": False,
            "immutable_baseline_descriptor_modified": False,
            "baseline_artifact_or_hash_modified": False,
            "gold_queries_v0_modified": False,
            "gold_queries_xlsx_v1_modified": False,
            "gold_queries_xlsx_v2_modified": False,
        },
        "important_decisions": [
            "V3 naturalized is a candidate manifest, not a promotion baseline.",
            "Only the query surface is changed; original_query and query_seed preserve the v2 surface.",
            "Positive diagnostic CSV includes only v2_label_status=positive, label_status=bound, expected_location_type=xlsx rows.",
            "Hidden-negative rows remain in the mixed manifest but are excluded from positive Hit@K/MRR diagnostics.",
            "Formula/date rows preserve RAW_FORMULA, DATE_FORMATTED_VALUE, or DISPLAY_FORMATTED_VALUE intent in the query text.",
            "No thresholds, hybrid search, reranking, parser changes, promotion flags, or immutable baselines are changed.",
        ],
    }


def build_positive_export_report(
    *,
    args: argparse.Namespace,
    source_rows: list[Mapping[str, str]],
    naturalized_rows: list[Mapping[str, str]],
    positive_rows: list[Mapping[str, str]],
    naturalized_sha: str,
    positive_sha: str,
    positive_validation: Mapping[str, Any],
) -> dict[str, Any]:
    included_ids = {row.get("query_id", "") for row in positive_rows}
    excluded_rows = [row for row in naturalized_rows if row.get("query_id", "") not in included_ids]
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_v3_positive_export_report",
        "promotion_evidence": False,
        "evidence_role": "positive_diagnostic_manifest_export",
        "source_xlsx_v2": str(args.xlsx_v2),
        "source_naturalized_csv": str(args.output_csv),
        "source_naturalized_sha256": naturalized_sha,
        "output_csv": str(args.positive_csv),
        "output_sha256": positive_sha,
        "source_row_count": len(source_rows),
        "naturalized_row_count": len(naturalized_rows),
        "positive_row_count": len(positive_rows),
        "include_filter": {
            "v2_label_status": "positive",
            "label_status": "bound",
            "expected_location_type": "xlsx",
        },
        "excluded_v2_label_status_distribution": dict(
            sorted(Counter(row.get("v2_label_status", "unknown") for row in excluded_rows).items())
        ),
        "excluded_query_ids": [row.get("query_id", "") for row in excluded_rows],
        "validation": dict(positive_validation),
        "notes": [
            "Negative hidden-policy, deferred, and excluded rows are not included in this positive diagnostic manifest.",
            "This export does not run promotion and does not mark promotion_evidence=true.",
        ],
    }


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


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be an object: {path}")
    return payload


def write_csv(path: Path, rows: Iterable[Mapping[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    parser.add_argument("--xlsx-v2", default=str(DEFAULT_XLSX_V2))
    parser.add_argument("--formula-date-review", default=str(DEFAULT_FORMULA_DATE_REVIEW))
    parser.add_argument("--hidden-negative-plan", default=str(DEFAULT_HIDDEN_NEGATIVE_PLAN))
    parser.add_argument("--chunk-granularity-review", default=str(DEFAULT_CHUNK_GRANULARITY_REVIEW))
    parser.add_argument("--output-csv", default=str(DEFAULT_NATURALIZED_CSV))
    parser.add_argument("--positive-csv", default=str(DEFAULT_POSITIVE_CSV))
    parser.add_argument("--build-report", default=str(DEFAULT_BUILD_REPORT))
    parser.add_argument("--positive-export-report", default=str(DEFAULT_POSITIVE_EXPORT_REPORT))
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID)
    parser.add_argument("--dataset-version", default=DEFAULT_DATASET_VERSION)
    parser.add_argument("--positive-dataset-id", default=DEFAULT_POSITIVE_DATASET_ID)
    parser.add_argument("--positive-dataset-version", default=DEFAULT_POSITIVE_DATASET_VERSION)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
