"""Generate a diagnostic-only supplemental PDF gold review pack.

The output is a human-review dataset only. It does not create official gold,
does not change denominators, does not create promotion evidence, and does not
claim table, row/column/value, bbox, OCR, parser, retrieval, DB, SearchUnit,
candidate, baseline, judge, or LLM success.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    EVAL_QUERIES_DIR,
    REPORT_DIR,
    ROOT,
    artifact_identity,
    display_path,
    resolve_path,
    sorted_counter,
    utc_timestamp,
    write_csv,
    write_json,
    write_jsonl,
)
from rag_pdf_supplemental_gold_review_candidate_builder import (
    CANDIDATE_FIELDS,
    OUTPUT_GUARDRAILS,
    CandidateInputPaths,
    FailClosedInputError,
    build_candidate_dataset,
)


DEFAULT_OUTPUT_DIR = ROOT / "ai" / "eval" / "review" / "pdf_supplemental_gold_review"
DEFAULT_REVIEW_CSV = DEFAULT_OUTPUT_DIR / "pdf_supplemental_gold_review_pack.csv"
DEFAULT_REVIEW_JSONL = DEFAULT_OUTPUT_DIR / "pdf_supplemental_gold_review_pack.jsonl"
DEFAULT_REVIEW_MD = DEFAULT_OUTPUT_DIR / "pdf_supplemental_gold_review_pack.md"
DEFAULT_SUMMARY_JSON = REPORT_DIR / "rag_pdf_supplemental_gold_review_pack_summary.json"

SCHEMA_VERSION = "pdf_supplemental_gold_review_pack_v1"
DEFAULT_PACK_SIZE = 80
DEFAULT_HIGH_CONFIDENCE_TABLE_MAX = 6
DEFAULT_RESTRICTED_TABLE_MAX = 15
DEFAULT_CONTROL_MIN = 10
DEFAULT_CONTROL_MAX = 15
DEFAULT_OCR_MAX = 3

USER_COLUMNS = [
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]

REVIEW_PACK_COLUMNS = [
    "track",
    "query_id",
    "dataset",
    "source_file_name",
    "page_no",
    "page_label",
    "section_path",
    "query",
    "expected_evidence_excerpt",
    "evidence_object_summary",
    "deterministic_draft",
    "review_lane",
    "suggested_gold_decision",
    "suggested_answerability_label",
    "suggested_relevance_label",
    "suggested_expected_evidence_policy",
    "suggested_denominator_policy",
    "risk_tags",
    "diagnostic_reason",
    *USER_COLUMNS,
]

READY_LANES = ["READY_SECTION_SUMMARY", "READY_EXTRACTIVE_CONTEXT"]
CONTROL_LANES = [
    "ABSTAIN_TABLE_LIKE_NO_ROW_COLUMN_VALUE",
    "ABSTAIN_KEYWORD_OR_LABEL_ONLY",
    "ABSTAIN_GENERIC_SECTION_CONTEXT",
    "FALSE_POSITIVE_REFERENCE_CODE",
    "FALSE_POSITIVE_BULLET_OR_FORMULA",
    "FALSE_POSITIVE_NOISE",
    "POLICY_OR_DIAGNOSTIC_ONLY",
]

LANE_ORDER = {
    "READY_SECTION_SUMMARY": 0,
    "READY_EXTRACTIVE_CONTEXT": 1,
    "HIGH_CONFIDENCE_TABLE_CANDIDATE": 2,
    "READY_RESTRICTED_TABLE_CONTEXT": 3,
    "ABSTAIN_TABLE_LIKE_NO_ROW_COLUMN_VALUE": 4,
    "ABSTAIN_KEYWORD_OR_LABEL_ONLY": 5,
    "ABSTAIN_GENERIC_SECTION_CONTEXT": 6,
    "FALSE_POSITIVE_REFERENCE_CODE": 7,
    "FALSE_POSITIVE_BULLET_OR_FORMULA": 8,
    "FALSE_POSITIVE_NOISE": 9,
    "OCR_NEEDED_UNSUPPORTED": 10,
    "POLICY_OR_DIAGNOSTIC_ONLY": 11,
}

OUTPUT_GUARDRAILS_WITH_REVIEW: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    **OUTPUT_GUARDRAILS,
    "live_llm_run": False,
    "external_live_llm_run": False,
    "local_llm_run": False,
    "official_gold_created": False,
    "official_denominator_evidence_created": False,
    "promotion_artifact_created": False,
    "existing_gold_csv_overwritten": False,
    "row_column_value_semantics_claimed": False,
    "table_semantics_success_claimed": False,
}

DEFAULT_GOLD_GUARD_PATHS = [
    EVAL_QUERIES_DIR / "gold_queries_pdf_v0.csv",
    EVAL_QUERIES_DIR / "gold_queries_pdf_v1_review_draft.csv",
    EVAL_QUERIES_DIR / "official_denominator_registry.json",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = CandidateInputPaths(
        synthetic_csv=Path(args.synthetic_csv),
        answer_quality_json=Path(args.answer_quality_json),
        answer_quality_csv=Path(args.answer_quality_csv),
        abstain_json=Path(args.abstain_json),
        abstain_csv=Path(args.abstain_csv),
        false_positive_json=Path(args.false_positive_json),
        false_positive_csv=Path(args.false_positive_csv),
        lh_reclassification_json=Path(args.lh_reclassification_json),
        lh_reclassification_csv=Path(args.lh_reclassification_csv),
        precision_json=Path(args.precision_json),
        precision_csv=Path(args.precision_csv),
        canary_json=Path(args.canary_json),
        canary_csv=Path(args.canary_csv),
        inventory_json=Path(args.inventory_json),
        evidence_jsonl=Path(args.evidence_jsonl),
        draft_jsonl=Path(args.draft_jsonl),
    )
    try:
        report = build_review_pack(
            paths=paths,
            output_dir=Path(args.output_dir),
            summary_json_path=Path(args.summary_json),
            pack_size=args.pack_size,
            expected_source_rows=args.expected_source_rows,
            high_confidence_table_max=args.high_confidence_table_max,
            restricted_table_max=args.restricted_table_max,
            control_min=args.control_min,
            control_max=args.control_max,
            ocr_max=args.ocr_max,
            gold_guard_paths=[Path(path) for path in args.gold_guard_path],
        )
    except FailClosedInputError as exc:
        print(json.dumps({"status": "FAIL_CLOSED_INPUT_ERROR", "blockers": exc.blockers}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({
        "status": report["status"],
        "review_row_count": report["review_row_count"],
        "lane_counts": report["lane_counts"],
        "summary_json": report["output_artifacts"]["summary_json"]["path"],
        "review_csv": report["output_artifacts"]["review_csv"]["path"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_paths = CandidateInputPaths()
    parser.add_argument("--synthetic-csv", default=str(default_paths.synthetic_csv))
    parser.add_argument("--answer-quality-json", default=str(default_paths.answer_quality_json))
    parser.add_argument("--answer-quality-csv", default=str(default_paths.answer_quality_csv))
    parser.add_argument("--abstain-json", default=str(default_paths.abstain_json))
    parser.add_argument("--abstain-csv", default=str(default_paths.abstain_csv))
    parser.add_argument("--false-positive-json", default=str(default_paths.false_positive_json))
    parser.add_argument("--false-positive-csv", default=str(default_paths.false_positive_csv))
    parser.add_argument("--lh-reclassification-json", default=str(default_paths.lh_reclassification_json))
    parser.add_argument("--lh-reclassification-csv", default=str(default_paths.lh_reclassification_csv))
    parser.add_argument("--precision-json", default=str(default_paths.precision_json))
    parser.add_argument("--precision-csv", default=str(default_paths.precision_csv))
    parser.add_argument("--canary-json", default=str(default_paths.canary_json))
    parser.add_argument("--canary-csv", default=str(default_paths.canary_csv))
    parser.add_argument("--inventory-json", default=str(default_paths.inventory_json))
    parser.add_argument("--evidence-jsonl", default=str(default_paths.evidence_jsonl))
    parser.add_argument("--draft-jsonl", default=str(default_paths.draft_jsonl))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON))
    parser.add_argument("--pack-size", type=int, default=DEFAULT_PACK_SIZE)
    parser.add_argument("--expected-source-rows", type=int, default=150)
    parser.add_argument("--high-confidence-table-max", type=int, default=DEFAULT_HIGH_CONFIDENCE_TABLE_MAX)
    parser.add_argument("--restricted-table-max", type=int, default=DEFAULT_RESTRICTED_TABLE_MAX)
    parser.add_argument("--control-min", type=int, default=DEFAULT_CONTROL_MIN)
    parser.add_argument("--control-max", type=int, default=DEFAULT_CONTROL_MAX)
    parser.add_argument("--ocr-max", type=int, default=DEFAULT_OCR_MAX)
    parser.add_argument(
        "--gold-guard-path",
        action="append",
        default=[str(path) for path in DEFAULT_GOLD_GUARD_PATHS],
        help="Existing gold or denominator files to hash before and after writing review artifacts.",
    )
    return parser.parse_args(argv)


def build_review_pack(
    *,
    paths: CandidateInputPaths | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    summary_json_path: Path = DEFAULT_SUMMARY_JSON,
    pack_size: int = DEFAULT_PACK_SIZE,
    expected_source_rows: int | None = 150,
    high_confidence_table_max: int = DEFAULT_HIGH_CONFIDENCE_TABLE_MAX,
    restricted_table_max: int = DEFAULT_RESTRICTED_TABLE_MAX,
    control_min: int = DEFAULT_CONTROL_MIN,
    control_max: int = DEFAULT_CONTROL_MAX,
    ocr_max: int = DEFAULT_OCR_MAX,
    gold_guard_paths: list[Path] | None = None,
    enforce_output_path_guard: bool = True,
) -> dict[str, Any]:
    output_dir = resolve_path(output_dir)
    summary_json_path = resolve_path(summary_json_path)
    review_csv_path = output_dir / DEFAULT_REVIEW_CSV.name
    review_jsonl_path = output_dir / DEFAULT_REVIEW_JSONL.name
    review_md_path = output_dir / DEFAULT_REVIEW_MD.name
    blockers = []
    if enforce_output_path_guard:
        blockers = review_pack_output_path_blockers({
            "review_csv": review_csv_path,
            "review_jsonl": review_jsonl_path,
            "review_md": review_md_path,
            "summary_json": summary_json_path,
        })
    if blockers:
        raise FailClosedInputError(blockers)

    gold_guard_paths = [resolve_path(path) for path in (gold_guard_paths if gold_guard_paths is not None else DEFAULT_GOLD_GUARD_PATHS)]
    gold_before = file_snapshots(gold_guard_paths)
    candidate_payload = build_candidate_dataset(paths=paths, expected_source_rows=expected_source_rows)
    selected_rows = select_review_rows(
        candidate_payload["rows"],
        pack_size=pack_size,
        high_confidence_table_max=high_confidence_table_max,
        restricted_table_max=restricted_table_max,
        control_min=control_min,
        control_max=control_max,
        ocr_max=ocr_max,
    )
    review_rows = [review_pack_row(row) for row in selected_rows]
    jsonl_rows = [review_jsonl_row(row) for row in review_rows]
    validate_review_rows(
        review_rows,
        jsonl_rows,
        pack_size=pack_size,
        high_confidence_table_max=high_confidence_table_max,
        restricted_table_max=restricted_table_max,
        ocr_max=ocr_max,
        blockers=blockers,
    )
    if blockers:
        raise FailClosedInputError(blockers)

    write_csv(review_csv_path, review_rows, REVIEW_PACK_COLUMNS)
    write_jsonl(review_jsonl_path, jsonl_rows)
    lane_counts = sorted_counter(Counter(row["review_lane"] for row in review_rows))
    candidate_lane_counts = candidate_payload["summary"]["review_lane_counts"]
    markdown = build_markdown_guide(
        review_csv_path=review_csv_path,
        review_jsonl_path=review_jsonl_path,
        summary_json_path=summary_json_path,
        review_rows=review_rows,
        lane_counts=lane_counts,
    )
    review_md_path.parent.mkdir(parents=True, exist_ok=True)
    review_md_path.write_text(markdown, encoding="utf-8")

    gold_after = file_snapshots(gold_guard_paths)
    gold_files_modified = gold_before != gold_after
    report = build_summary_report(
        candidate_summary=candidate_payload["summary"],
        review_rows=review_rows,
        lane_counts=lane_counts,
        candidate_lane_counts=candidate_lane_counts,
        review_csv_path=review_csv_path,
        review_jsonl_path=review_jsonl_path,
        review_md_path=review_md_path,
        summary_json_path=summary_json_path,
        gold_before=gold_before,
        gold_after=gold_after,
        gold_files_modified=gold_files_modified,
        pack_size=pack_size,
        high_confidence_table_max=high_confidence_table_max,
        restricted_table_max=restricted_table_max,
        control_min=control_min,
        control_max=control_max,
        ocr_max=ocr_max,
    )
    report["output_artifacts"]["summary_json"] = {
        "path": display_path(summary_json_path),
        "exists": True,
    }
    write_json(summary_json_path, report)
    return report


def select_review_rows(
    candidates: list[Mapping[str, Any]],
    *,
    pack_size: int,
    high_confidence_table_max: int,
    restricted_table_max: int,
    control_min: int,
    control_max: int,
    ocr_max: int,
) -> list[Mapping[str, Any]]:
    if pack_size <= 0:
        return []
    selected: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    pools = {
        "ready": ordered_pool(row for row in candidates if row.get("review_lane") in READY_LANES),
        "high": ordered_pool(row for row in candidates if row.get("review_lane") == "HIGH_CONFIDENCE_TABLE_CANDIDATE"),
        "restricted": ordered_pool(row for row in candidates if row.get("review_lane") == "READY_RESTRICTED_TABLE_CONTEXT"),
        "control": ordered_pool(row for row in candidates if row.get("review_lane") in CONTROL_LANES),
        "ocr": ordered_pool(row for row in candidates if row.get("review_lane") == "OCR_NEEDED_UNSUPPORTED"),
    }
    high_target = min(high_confidence_table_max, len(pools["high"]))
    restricted_target = min(restricted_table_max, len(pools["restricted"]))
    control_target = min(control_max, len(pools["control"]), max(control_min, pack_size // 7))
    control_target = min(control_target, max(0, pack_size - high_target - restricted_target))
    ocr_target = min(ocr_max, len(pools["ocr"]), max(0, pack_size // 25))
    ready_target = max(0, pack_size - high_target - restricted_target - control_target - ocr_target)

    add_rows(selected, seen, pools["ready"], ready_target)
    add_rows(selected, seen, pools["high"], high_target)
    add_rows(selected, seen, pools["restricted"], restricted_target)
    add_rows(selected, seen, pools["control"], control_target)
    add_rows(selected, seen, pools["ocr"], ocr_target)

    if len(selected) < pack_size:
        remainder = ordered_pool(row for row in candidates if row.get("query_id") not in seen)
        add_rows(selected, seen, remainder, pack_size - len(selected))
    return sorted(selected, key=selection_sort_key)


def ordered_pool(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    by_dataset: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=selection_sort_key):
        by_dataset[str(row.get("dataset") or "")].append(row)
    interleaved: list[Mapping[str, Any]] = []
    datasets = sorted(by_dataset)
    while any(by_dataset.values()):
        for dataset in datasets:
            if by_dataset[dataset]:
                interleaved.append(by_dataset[dataset].pop(0))
    return interleaved


def add_rows(selected: list[Mapping[str, Any]], seen: set[str], pool: list[Mapping[str, Any]], count: int) -> None:
    for row in pool:
        if count <= 0:
            return
        query_id = str(row.get("query_id") or "")
        if not query_id or query_id in seen:
            continue
        selected.append(row)
        seen.add(query_id)
        count -= 1


def selection_sort_key(row: Mapping[str, Any]) -> tuple[int, str, str, int, str]:
    try:
        page_no = int(str(row.get("page_no") or "0"))
    except ValueError:
        page_no = 0
    return (
        LANE_ORDER.get(str(row.get("review_lane") or ""), 99),
        str(row.get("dataset") or ""),
        str(row.get("source_file_name") or ""),
        page_no,
        str(row.get("query_id") or ""),
    )


def review_pack_row(row: Mapping[str, Any]) -> dict[str, Any]:
    review_row = {key: row.get(key, "") for key in REVIEW_PACK_COLUMNS}
    for column in USER_COLUMNS:
        review_row[column] = ""
    return review_row


def review_jsonl_row(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload.update(OUTPUT_GUARDRAILS_WITH_REVIEW)
    payload["diagnostic_only_review_pack_row"] = True
    payload["user_decision_required"] = True
    payload["official_denominator_changed"] = False
    payload["promotion_evidence"] = False
    payload["codex_gold_policy_decision_applied"] = False
    payload["pdf_c7_policy_decision_applied"] = False
    payload["bbox_contract_success_not_claimed"] = True
    payload["table_semantics_success_claimed"] = False
    payload["row_column_value_semantics_claimed"] = False
    return payload


def validate_review_rows(
    review_rows: list[Mapping[str, Any]],
    jsonl_rows: list[Mapping[str, Any]],
    *,
    pack_size: int,
    high_confidence_table_max: int,
    restricted_table_max: int,
    ocr_max: int,
    blockers: list[str],
) -> None:
    if len(review_rows) != pack_size:
        blockers.append(f"review pack row count mismatch: expected {pack_size}, got {len(review_rows)}")
    query_ids = [str(row.get("query_id") or "") for row in review_rows]
    duplicates = [query_id for query_id, count in Counter(query_ids).items() if query_id and count > 1]
    if duplicates:
        blockers.append(f"duplicated query_id in review pack: {duplicates[:5]}")
    for row in review_rows:
        for column in USER_COLUMNS:
            if row.get(column) not in ("", None):
                blockers.append(f"user column not blank: {row.get('query_id')} {column}")
    lane_counts = Counter(str(row.get("review_lane") or "") for row in review_rows)
    if lane_counts["HIGH_CONFIDENCE_TABLE_CANDIDATE"] > high_confidence_table_max:
        blockers.append("high-confidence table candidate quota exceeded")
    if lane_counts["READY_RESTRICTED_TABLE_CONTEXT"] > restricted_table_max:
        blockers.append("restricted table context quota exceeded")
    if lane_counts["OCR_NEEDED_UNSUPPORTED"] > ocr_max:
        blockers.append("OCR-needed quota exceeded")
    for row in jsonl_rows:
        required_values = {
            "promotion_evidence": False,
            "official_denominator_changed": False,
            "codex_gold_policy_decision_applied": False,
            "pdf_c7_policy_decision_applied": False,
            "table_semantics_success_claimed": False,
            "row_column_value_semantics_claimed": False,
            "bbox_contract_success_not_claimed": True,
        }
        for key, expected in required_values.items():
            if row.get(key) != expected:
                blockers.append(f"guardrail mismatch in {row.get('query_id')}: {key} expected {expected!r}")


def build_summary_report(
    *,
    candidate_summary: Mapping[str, Any],
    review_rows: list[Mapping[str, Any]],
    lane_counts: Mapping[str, int],
    candidate_lane_counts: Mapping[str, int],
    review_csv_path: Path,
    review_jsonl_path: Path,
    review_md_path: Path,
    summary_json_path: Path,
    gold_before: Mapping[str, Mapping[str, Any]],
    gold_after: Mapping[str, Mapping[str, Any]],
    gold_files_modified: bool,
    pack_size: int,
    high_confidence_table_max: int,
    restricted_table_max: int,
    control_min: int,
    control_max: int,
    ocr_max: int,
) -> dict[str, Any]:
    user_decision_required_count = len(review_rows)
    user_columns_blank = all(all(row.get(column, "") == "" for column in USER_COLUMNS) for row in review_rows)
    query_ids = [str(row.get("query_id") or "") for row in review_rows]
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "PASS" if not gold_files_modified else "FAIL_CLOSED_GOLD_FILE_CHANGED",
        **OUTPUT_GUARDRAILS_WITH_REVIEW,
        "evidence_role": "diagnostic",
        "analysis_role": "human_review_pack_only",
        "source_candidate_row_count": candidate_summary.get("source_candidate_row_count"),
        "review_row_count": len(review_rows),
        "requested_pack_size": pack_size,
        "user_decision_required_count": user_decision_required_count,
        "lane_counts": dict(lane_counts),
        "candidate_lane_counts": dict(candidate_lane_counts),
        "quota_policy": {
            "high_confidence_table_candidate_max": high_confidence_table_max,
            "ready_restricted_table_context_max": restricted_table_max,
            "control_min": control_min,
            "control_max": control_max,
            "ocr_needed_max": ocr_max,
        },
        "user_columns": USER_COLUMNS,
        "user_columns_blank": user_columns_blank,
        "duplicate_query_id_count": len(query_ids) - len(set(query_ids)),
        "official_denominator_changed": False,
        "promotion_evidence": False,
        "live_llm_run": False,
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "optional_judge_run": False,
        "codex_gold_policy_decision_applied": False,
        "pdf_c7_policy_decision_applied": False,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
        "bbox_contract_success_not_claimed": True,
        "table_semantics_success_not_claimed": True,
        "official_gold_created": False,
        "official_denominator_evidence_created": False,
        "promotion_artifact_created": False,
        "existing_gold_csv_overwritten": False,
        "gold_files_modified": gold_files_modified,
        "gold_file_snapshots_before": gold_before,
        "gold_file_snapshots_after": gold_after,
        "output_artifacts": {
            "review_csv": artifact_identity(review_csv_path),
            "review_jsonl": artifact_identity(review_jsonl_path),
            "review_markdown": artifact_identity(review_md_path),
            "summary_json": artifact_identity(summary_json_path),
        },
        "input_artifacts": candidate_summary.get("input_artifacts", []),
        "review_csv_columns": REVIEW_PACK_COLUMNS,
        "notes": [
            "suggested_* fields are diagnostic suggestions only and are not official decisions.",
            "HIGH_CONFIDENCE_TABLE_CANDIDATE remains a table evidence candidate, not table semantics success.",
            "READY_RESTRICTED_TABLE_CONTEXT rows are context-only and do not finalize row/column/value semantics.",
            "OCR_NEEDED rows, if any, are diagnostic controls only and not official gold candidates.",
        ],
    }
    return report


def build_markdown_guide(
    *,
    review_csv_path: Path,
    review_jsonl_path: Path,
    summary_json_path: Path,
    review_rows: list[Mapping[str, Any]],
    lane_counts: Mapping[str, int],
) -> str:
    lane_lines = "\n".join(f"| {lane} | {count} |" for lane, count in lane_counts.items())
    return f"""# PDF Supplemental Gold Review Pack

이 pack은 supplemental elec/lh PDF 진단 산출물을 사람이 검수하기 위한 review dataset입니다.
official gold, denominator, promotion evidence는 만들지 않았습니다.

## Artifacts

- CSV: `{display_path(review_csv_path)}`
- JSONL: `{display_path(review_jsonl_path)}`
- Summary: `{display_path(summary_json_path)}`

## Guardrails

- `promotion_evidence=false`
- `evidence_role=diagnostic`
- `official_denominator_changed=false`
- `codex_gold_policy_decision_applied=false`
- `pdf_c7_policy_decision_applied=false`
- `live_llm_run=false`
- `external_cloud_llm_run=false`
- `local_llm_run=false`
- `optional_judge_run=false`
- Retrieval tuning, reranking, parser expansion, DB/SearchUnit/index/candidate/baseline changes were not performed.
- Table semantics, row-column-value semantics, bbox contract success, and OCR-needed answerability are not claimed.

## Counts

- Review rows: `{len(review_rows)}`
- User decision required rows: `{len(review_rows)}`

| review_lane | rows |
| --- | ---: |
{lane_lines}

## 사용자가 결정해야 하는 범위

- gold 포함/제외
- answerability
- relevance
- expected evidence policy
- denominator policy
- table/page/bbox/OCR 관련 policy

## Codex가 결정하지 않은 것

- official denominator
- promotion evidence
- PDF C7 policy
- table semantics success
- bbox success
- OCR-needed answerability

## 추천 검수 순서

1. `READY_SECTION_SUMMARY` / `READY_EXTRACTIVE_CONTEXT` 먼저 확인합니다.
2. `HIGH_CONFIDENCE_TABLE_CANDIDATE`는 table semantics가 아니라 추출 근거 후보로만 확인합니다.
3. `ABSTAIN_*` / `FALSE_POSITIVE_*` control은 제외 사유가 맞는지만 확인합니다.
4. `OCR_NEEDED_UNSUPPORTED`는 이번 official gold 후보로 보지 말고 별도 bucket으로 보류합니다.

## CSV 작성 원칙

`user_*` 컬럼은 모두 비워 두었습니다. 사용자가 검수한 뒤 해당 컬럼만 채우면 됩니다.
`suggested_*` 컬럼은 진단 기반 제안이며 공식 결정으로 적용되지 않았습니다.
"""


def file_snapshots(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for path in paths:
        resolved = resolve_path(path)
        snapshots[display_path(resolved)] = {
            "exists": resolved.exists(),
            "sha256": sha256_file(resolved) if resolved.exists() else None,
            "size_bytes": resolved.stat().st_size if resolved.exists() else None,
        }
    return snapshots


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def review_pack_output_path_blockers(path_by_label: Mapping[str, Path]) -> list[str]:
    blockers: list[str] = []
    protected_names = {
        "gold_queries_pdf_v0.csv",
        "gold_queries_pdf_v1_review_draft.csv",
        "official_denominator_registry.json",
    }
    allowed_roots = [
        (ROOT / "ai" / "eval" / "review").resolve(),
        REPORT_DIR.resolve(),
    ]
    for label, path in path_by_label.items():
        resolved = path.resolve()
        display = display_path(resolved)
        if "supplemental" not in display.lower():
            blockers.append(f"{label} path must be supplemental-specific: {display}")
        if resolved.name.lower() in protected_names:
            blockers.append(f"{label} uses protected gold/denominator filename: {resolved.name}")
        if not any(path_is_relative_to(resolved, root) for root in allowed_roots):
            blockers.append(f"{label} path must stay under eval review or rag-ingestion reports: {display}")
    return blockers


def path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    raise SystemExit(main())
