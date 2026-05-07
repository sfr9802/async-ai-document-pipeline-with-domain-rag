"""Build a diagnostic-only PDF FILE lookup companion pack.

The source PDF manual v1 content review pack is preserved. This script creates
a separate FILE lookup companion dataset plus a merged review draft. Companion
query text is manually curated in COMPANION_SPECS; the script only materializes
rows and validates guardrails.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review" / "pdf_supplemental_gold_review"
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
DEFAULT_SOURCE_CSV = REVIEW_DIR / "pdf_gold_review_pack_manual_v1.csv"

COMPANION_CSV_NAME = "pdf_gold_review_pack_manual_v1_file_lookup_companion.csv"
COMPANION_JSONL_NAME = "pdf_gold_review_pack_manual_v1_file_lookup_companion.jsonl"
MERGED_CSV_NAME = "pdf_gold_review_pack_manual_v1_with_file_lookup.csv"
MERGED_MD_NAME = "pdf_gold_review_pack_manual_v1_with_file_lookup.md"
SUMMARY_NAME = "rag_pdf_gold_review_pack_manual_v1_file_lookup_summary.json"

COMPANION_COLUMNS = [
    "track",
    "query_id",
    "retrieval_lane",
    "review_group",
    "source_file_name",
    "expected_file_name",
    "expected_document_version_id",
    "expected_page_no",
    "expected_page_label",
    "expected_bbox",
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
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]

MANUAL_V1_USER_COLUMNS = [
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]
USER_COLUMNS = [column for column in COMPANION_COLUMNS if column.startswith("user_")]

CONTENT_LANE = "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR"
METADATA_LANE = "PDF_FILE_LOOKUP_BY_METADATA"

REQUIRED_SUMMARY_GUARDRAILS: dict[str, bool | str] = {
    "promotion_evidence": False,
    "evidence_role": "diagnostic",
    "official_denominator_changed": False,
    "codex_gold_policy_decision_applied": False,
    "pdf_c7_policy_decision_applied": False,
    "live_llm_run": False,
    "external_cloud_llm_run": False,
    "local_llm_run": False,
    "optional_judge_run": False,
    "retrieval_tuning_applied": False,
    "reranking_applied": False,
    "parser_expansion_applied": False,
    "db_mutation_applied": False,
    "searchunit_mutation_applied": False,
    "candidate_artifact_changed": False,
    "immutable_baseline_changed": False,
    "bbox_contract_success_not_claimed": True,
    "table_semantics_success_claimed": False,
    "row_column_value_semantics_claimed": False,
    "file_lookup_success_claimed": False,
}


class FileLookupCompanionError(RuntimeError):
    """Fail-closed error for companion pack generation."""


COMPANION_SPECS: list[dict[str, str]] = [
    {
        "parent_query_id": "supp_elec_d73432a97b_p1_0005",
        "retrieval_lane": CONTENT_LANE,
        "query": "계절 바뀌는 날 일수계산으로 주택용 저압 요금 달라진다는 안내가 있는 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_8be2c46ed9_p1_0015",
        "retrieval_lane": CONTENT_LANE,
        "query": "국번없이 123으로 365일 24시간 전기상담 받는다는 안내문 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_c456f27e5d_p1_0023",
        "retrieval_lane": CONTENT_LANE,
        "query": "주택용 고압 기후환경요금 단가가 9원이라고 적힌 전기요금 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_d73432a97b_p2_0004",
        "retrieval_lane": CONTENT_LANE,
        "query": "사이버지점과 스마트 한전 앱 안내가 같이 있는 전기요금 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_bc85e2bfb2_p1_0039",
        "retrieval_lane": CONTENT_LANE,
        "query": "하계 천킬로와트시 초과분에 736.2원 슈퍼유저요금 적용한다는 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_8659b3db62_p1_0043",
        "retrieval_lane": CONTENT_LANE,
        "query": "주택용 고압 동계 천킬로와트시 초과 단가 601.3원 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_5db341e8bf_p1_0010",
        "retrieval_lane": CONTENT_LANE,
        "query": "계약전력 300킬로와트 미만이라고 표시된 전기요금 기준 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_8be2c46ed9_p1_0013",
        "retrieval_lane": CONTENT_LANE,
        "query": "기후환경요금 단가가 7.3원으로 매년 변동된다고 안내한 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_6bd1f748a3_p1_0018",
        "retrieval_lane": CONTENT_LANE,
        "query": "주택용 저압 전기요금에서 기후환경요금 7.3원을 안내한 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_493679be9f_p1_0048",
        "retrieval_lane": CONTENT_LANE,
        "query": "주택용 저압 동계 천킬로와트시 초과 단가 736.2원 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_67760ba504_p4_0150",
        "retrieval_lane": CONTENT_LANE,
        "query": "건설사업관리를 건설산업기본법 제2조 기준으로 정의한 LH 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_7e8ae40964_p13_0087",
        "retrieval_lane": CONTENT_LANE,
        "query": "시공상세도 제출할 때 다른 공사와 협의조정 내용을 포함하라는 LH 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_7e8ae40964_p14_0088",
        "retrieval_lane": CONTENT_LANE,
        "query": "시공상세도면 승인으로 수급인 책임이 감면되지 않는다는 기준 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_a5094fc9ae_p5_0091",
        "retrieval_lane": CONTENT_LANE,
        "query": "전기공사와 소방시설공사 지급자재 시공한계가 도면이나 시방을 따른다는 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_a5094fc9ae_p7_0092",
        "retrieval_lane": CONTENT_LANE,
        "query": "공사용 자재는 감독자 확인을 받고 변질품 손상품은 불량품으로 보는 기준 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_a5094fc9ae_p10_0093",
        "retrieval_lane": CONTENT_LANE,
        "query": "전기공사 준공 시 제출서류가 LHCS 10 10 35를 따른다는 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_31623e878a_p15_0104",
        "retrieval_lane": CONTENT_LANE,
        "query": "사용자재와 장비가 모두 신품이고 설계도서 요구에 맞아야 한다는 기준 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_a4995bcd89_p8_0113",
        "retrieval_lane": CONTENT_LANE,
        "query": "경고장 3차 이상 받은 건설기술인 교체 기준 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_a4995bcd89_p14_0115",
        "retrieval_lane": CONTENT_LANE,
        "query": "공사현장 표지 제작과 설치 기준이 나오는 LH 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_6acf57500f_p1_0121",
        "retrieval_lane": CONTENT_LANE,
        "query": "소방공사를 전기공사와 같이 도급받은 경우 하도급관리 기준을 따른다는 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_lh_6acf57500f_p12_0123",
        "retrieval_lane": CONTENT_LANE,
        "query": "공사대금지급 알림 서비스에서 빠진 내용은 하도급관리를 따른다는 자료 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_d73432a97b_p1_0005",
        "retrieval_lane": METADATA_LANE,
        "query": "2021년 1월 시행 주택용 저압 전기요금 안내 자료가 문서 목록에 잡히는지 확인해줘",
    },
    {
        "parent_query_id": "supp_elec_5db341e8bf_p2_0009",
        "retrieval_lane": METADATA_LANE,
        "query": "2021년 1월 시행 전기요금 종합 안내 자료가 문서 목록에 잡히는지 확인해줘",
    },
    {
        "parent_query_id": "supp_elec_8be2c46ed9_p1_0013",
        "retrieval_lane": METADATA_LANE,
        "query": "2022년 4월 시행 주택용 고압 전기요금표 자료를 문서 목록에서 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_6bd1f748a3_p1_0018",
        "retrieval_lane": METADATA_LANE,
        "query": "2022년 4월 시행 주택용 저압 전기요금표 자료를 문서 목록에서 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_c456f27e5d_p1_0023",
        "retrieval_lane": METADATA_LANE,
        "query": "2023년 11월 시행 주택용 고압 전기요금표 자료를 문서 목록에서 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_5632eb03a2_p1_0028",
        "retrieval_lane": METADATA_LANE,
        "query": "2023년 11월 시행 주택용 저압 전기요금표 자료를 문서 목록에서 찾아줘",
    },
    {
        "parent_query_id": "supp_elec_625588fd70_p1_0034",
        "retrieval_lane": METADATA_LANE,
        "query": "2024년 10월 시행 전기요금 종합표 자료를 문서 목록에서 찾아줘",
    },
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_file_lookup_pack(
        source_csv=Path(args.source_csv),
        output_dir=Path(args.output_dir),
        report_dir=Path(args.report_dir),
        allow_overwrite=args.allow_overwrite,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", default=str(DEFAULT_SOURCE_CSV))
    parser.add_argument("--output-dir", default=str(REVIEW_DIR))
    parser.add_argument("--report-dir", default=str(REPORT_DIR))
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


def build_file_lookup_pack(
    *,
    source_csv: Path = DEFAULT_SOURCE_CSV,
    output_dir: Path = REVIEW_DIR,
    report_dir: Path = REPORT_DIR,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    source_rows = read_csv(source_csv)
    source_hash_before = snapshot_file(source_csv)
    validate_source_rows(source_rows)
    source_by_id = {row["query_id"]: row for row in source_rows}

    companion_rows = build_companion_rows(source_by_id)
    validate_companion_rows(companion_rows, source_rows)
    merged_rows = [normalize_content_row(row) for row in source_rows] + companion_rows
    validate_merged_rows(merged_rows, source_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    companion_csv = output_dir / COMPANION_CSV_NAME
    companion_jsonl = output_dir / COMPANION_JSONL_NAME
    merged_csv = output_dir / MERGED_CSV_NAME
    merged_md = output_dir / MERGED_MD_NAME
    summary_json = report_dir / SUMMARY_NAME
    output_paths = [companion_csv, companion_jsonl, merged_csv, merged_md, summary_json]
    if not allow_overwrite:
        for path in output_paths:
            if path.exists():
                raise FileLookupCompanionError(f"Refusing to overwrite existing output: {path}")

    summary = build_summary(source_csv, companion_rows, merged_rows, output_paths, source_hash_before)
    validate_summary_guardrails(summary)

    write_csv(companion_csv, companion_rows, COMPANION_COLUMNS)
    write_jsonl(companion_jsonl, companion_rows)
    write_csv(merged_csv, merged_rows, COMPANION_COLUMNS)
    write_markdown(merged_md, summary)
    write_json(summary_json, summary)

    source_hash_after = snapshot_file(source_csv)
    if source_hash_before != source_hash_after:
        raise FileLookupCompanionError("Source manual v1 CSV changed during companion generation")

    return {
        "status": "PASS",
        "source_csv": rel(source_csv),
        "companion_csv": rel(companion_csv),
        "companion_jsonl": rel(companion_jsonl),
        "merged_csv": rel(merged_csv),
        "merged_markdown": rel(merged_md),
        "summary_json": rel(summary_json),
        "companion_row_count": len(companion_rows),
        "merged_row_count": len(merged_rows),
        "content_anchor_count": count_lane(companion_rows, CONTENT_LANE),
        "metadata_count": count_lane(companion_rows, METADATA_LANE),
        "source_overwritten": False,
        "promotion_evidence": False,
        "official_denominator_changed": False,
    }


def build_companion_rows(source_by_id: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    content_idx = 1
    metadata_idx = 1
    for spec in COMPANION_SPECS:
        parent = source_by_id[spec["parent_query_id"]]
        if spec["retrieval_lane"] == CONTENT_LANE:
            query_id = f"pdf_file_lookup_content_anchor_{content_idx:03d}"
            content_idx += 1
        elif spec["retrieval_lane"] == METADATA_LANE:
            query_id = f"pdf_file_lookup_metadata_{metadata_idx:03d}"
            metadata_idx += 1
        else:
            raise FileLookupCompanionError(f"Unknown retrieval_lane: {spec['retrieval_lane']}")
        rows.append(companion_row(query_id=query_id, spec=spec, parent=parent))
    return rows


def companion_row(*, query_id: str, spec: dict[str, str], parent: dict[str, str]) -> dict[str, str]:
    lane = spec["retrieval_lane"]
    parent_lane = extract_review_lane(parent)
    allowed_positive_parent_lanes = {"READY_SECTION_SUMMARY", "READY_EXTRACTIVE_CONTEXT"}
    if parent_lane not in allowed_positive_parent_lanes:
        raise FileLookupCompanionError(
            f"FILE lookup positive parent {parent['query_id']} has disallowed lane {parent_lane}"
        )
    tags = ["PDF_FILE_LOOKUP", "NO_PAGE_OR_BBOX_REQUIRED"]
    tags.append("CONTENT_ANCHOR_REQUIRED" if lane == CONTENT_LANE else "METADATA_LOOKUP")
    if is_generic_filename(parent["expected_file_name"]):
        tags.append("GENERIC_FILENAME")
    return {
        "track": "PDF",
        "query_id": query_id,
        "retrieval_lane": lane,
        "review_group": "file_lookup_companion_review",
        "source_file_name": parent["expected_file_name"],
        "expected_file_name": parent["expected_file_name"],
        "expected_document_version_id": parent["expected_document_version_id"],
        "expected_page_no": parent["expected_page_no"],
        "expected_page_label": parent["expected_page_label"],
        "expected_bbox": parent["expected_bbox"],
        "query": spec["query"],
        "expected_evidence_excerpt": (
            f"expected_file_name={parent['expected_file_name']}; "
            f"content_reference={parent['expected_answer_text'][:240]}"
        ),
        "evidence_object_summary": "",
        "deterministic_draft": "",
        "review_lane": lane,
        "suggested_gold_decision": "KEEP_POSITIVE",
        "suggested_answerability_label": "ANSWERABLE_AS_FILE_LOOKUP",
        "suggested_relevance_label": "RELEVANT",
        "suggested_expected_evidence_policy": "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY",
        "suggested_denominator_policy": "INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE",
        "risk_tags": ";".join(tags),
        "diagnostic_reason": (
            "FILE lookup companion row. Success criterion is expected file identity hit; "
            "page, bbox, table, row, column, and value semantics are diagnostic references only."
        ),
        "user_gold_decision": "",
        "user_answerability_label": "",
        "user_relevance_label": "",
        "user_expected_evidence_policy": "",
        "user_denominator_policy": "",
        "user_issue_tags": "",
        "user_notes": "",
    }


def normalize_content_row(row: dict[str, str]) -> dict[str, str]:
    review_lane = extract_review_lane(row)
    return {
        "track": row["track"],
        "query_id": row["query_id"],
        "retrieval_lane": "PDF_CONTENT_RETRIEVAL_REVIEW",
        "review_group": row["review_group"],
        "source_file_name": row["expected_file_name"],
        "expected_file_name": row["expected_file_name"],
        "expected_document_version_id": row["expected_document_version_id"],
        "expected_page_no": row["expected_page_no"],
        "expected_page_label": row["expected_page_label"],
        "expected_bbox": row["expected_bbox"],
        "query": row["query"],
        "expected_evidence_excerpt": row["expected_answer_text"],
        "evidence_object_summary": "",
        "deterministic_draft": "",
        "review_lane": review_lane,
        "suggested_gold_decision": row["suggested_gold_decision"],
        "suggested_answerability_label": row["suggested_answerability_label"],
        "suggested_relevance_label": row["suggested_relevance_label"],
        "suggested_expected_evidence_policy": row["suggested_expected_evidence_policy"],
        "suggested_denominator_policy": row["suggested_denominator_policy"],
        "risk_tags": row["suggested_issue_tags"],
        "diagnostic_reason": row["suggested_notes"],
        "user_gold_decision": "",
        "user_answerability_label": "",
        "user_relevance_label": "",
        "user_expected_evidence_policy": "",
        "user_denominator_policy": "",
        "user_issue_tags": "",
        "user_notes": "",
    }


def build_summary(
    source_csv: Path,
    companion_rows: list[dict[str, str]],
    merged_rows: list[dict[str, str]],
    output_paths: list[Path],
    source_hash_before: dict[str, Any],
) -> dict[str, Any]:
    companion_lane_counts = dict(Counter(row["retrieval_lane"] for row in companion_rows))
    generic_filename_count = sum(1 for row in companion_rows if "GENERIC_FILENAME" in row["risk_tags"].split(";"))
    summary: dict[str, Any] = {
        "schema_version": "rag_pdf_gold_review_pack_manual_v1_file_lookup_companion",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": rel(source_csv),
        "outputs": {
            "companion_csv": rel(output_paths[0]),
            "companion_jsonl": rel(output_paths[1]),
            "merged_csv": rel(output_paths[2]),
            "merged_markdown": rel(output_paths[3]),
            "summary_json": rel(output_paths[4]),
        },
        "source_hash_before": source_hash_before,
        "source_overwritten": False,
        "companion_row_count": len(companion_rows),
        "merged_row_count": len(merged_rows),
        "manual_v1_content_row_count": len(merged_rows) - len(companion_rows),
        "pdf_file_lookup_by_content_anchor_count": companion_lane_counts.get(CONTENT_LANE, 0),
        "pdf_file_lookup_by_metadata_count": companion_lane_counts.get(METADATA_LANE, 0),
        "companion_retrieval_lane_counts": companion_lane_counts,
        "generic_filename_companion_count": generic_filename_count,
        "generic_filename_handling": (
            "generic filenames are not selected for metadata lookup; if selected for content-anchor lookup "
            "they are tagged GENERIC_FILENAME and remain content-anchor driven"
        ),
        "query_unique": len({row["query"] for row in companion_rows}) == len(companion_rows),
        "merged_query_unique": len({row["query"] for row in merged_rows}) == len(merged_rows),
        "user_columns_blank": True,
        "file_lookup_rows_require_page_success": False,
        "file_lookup_rows_require_bbox_success": False,
        "file_lookup_rows_require_table_value_success": False,
    }
    summary.update(REQUIRED_SUMMARY_GUARDRAILS)
    return summary


def validate_source_rows(rows: list[dict[str, str]]) -> None:
    if len(rows) != 80:
        raise FileLookupCompanionError(f"Expected 80 source manual v1 rows, got {len(rows)}")
    ids = [row["query_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise FileLookupCompanionError("Duplicate source query_id")
    missing = [column for column in MANUAL_V1_USER_COLUMNS if column not in rows[0]]
    if missing:
        raise FileLookupCompanionError(f"Source manual v1 missing user columns: {missing}")


def validate_companion_rows(rows: list[dict[str, str]], source_rows: list[dict[str, str]]) -> None:
    if not 25 <= len(rows) <= 30:
        raise FileLookupCompanionError(f"Companion row count must be 25-30, got {len(rows)}")
    ids = [row["query_id"] for row in rows]
    source_ids = {row["query_id"] for row in source_rows}
    if len(ids) != len(set(ids)):
        raise FileLookupCompanionError("Duplicate companion query_id")
    if source_ids & set(ids):
        raise FileLookupCompanionError("Companion query_id collides with manual v1 query_id")
    queries = [row["query"] for row in rows]
    if len(queries) != len(set(queries)):
        raise FileLookupCompanionError("Companion query text must be unique")
    content_count = count_lane(rows, CONTENT_LANE)
    metadata_count = count_lane(rows, METADATA_LANE)
    if not 18 <= content_count <= 22:
        raise FileLookupCompanionError(f"Content-anchor row count must be 18-22, got {content_count}")
    if not 5 <= metadata_count <= 8:
        raise FileLookupCompanionError(f"Metadata row count must be 5-8, got {metadata_count}")
    if content_count <= metadata_count:
        raise FileLookupCompanionError("Content-anchor rows must outnumber metadata rows")
    for row in rows:
        if list(row) != COMPANION_COLUMNS:
            raise FileLookupCompanionError("Companion row schema mismatch")
        if row["expected_file_name"] and row["expected_file_name"] in row["query"]:
            raise FileLookupCompanionError(f"Companion query leaks filename: {row['query_id']}")
        if re.search(r"\.pdf\b", row["query"], re.IGNORECASE):
            raise FileLookupCompanionError(f"Companion query leaks .pdf literal: {row['query_id']}")
        if row["retrieval_lane"] == METADATA_LANE and is_generic_filename(row["source_file_name"]):
            raise FileLookupCompanionError(f"Generic filename overrepresented in metadata lookup: {row['query_id']}")
        for column in USER_COLUMNS:
            if row[column] != "":
                raise FileLookupCompanionError(f"{row['query_id']} has non-blank user column {column}")
        if "NO_PAGE_OR_BBOX_REQUIRED" not in row["risk_tags"]:
            raise FileLookupCompanionError(f"{row['query_id']} missing NO_PAGE_OR_BBOX_REQUIRED")
        if "table_semantics_success" in row["risk_tags"].lower():
            raise FileLookupCompanionError(f"{row['query_id']} claims table semantics success")
        if row["suggested_denominator_policy"] != "INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE":
            raise FileLookupCompanionError(f"{row['query_id']} has wrong file lookup denominator policy")


def validate_merged_rows(rows: list[dict[str, str]], source_rows: list[dict[str, str]]) -> None:
    expected_count = len(source_rows) + len(COMPANION_SPECS)
    if len(rows) != expected_count:
        raise FileLookupCompanionError(f"Merged row count {len(rows)} != expected {expected_count}")
    ids = [row["query_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise FileLookupCompanionError("Duplicate merged query_id")
    queries = [row["query"] for row in rows]
    if len(queries) != len(set(queries)):
        raise FileLookupCompanionError("Duplicate merged query text")
    for row in rows:
        for column in USER_COLUMNS:
            if row[column] != "":
                raise FileLookupCompanionError(f"Merged row has non-blank user column: {row['query_id']} {column}")


def validate_summary_guardrails(summary: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_SUMMARY_GUARDRAILS if key not in summary]
    if missing:
        raise FileLookupCompanionError(f"Missing summary guardrail key(s): {missing}")
    mismatched = [
        f"{key}={summary[key]!r} expected {expected!r}"
        for key, expected in REQUIRED_SUMMARY_GUARDRAILS.items()
        if summary[key] != expected
    ]
    if mismatched:
        raise FileLookupCompanionError(f"Summary guardrail mismatch: {mismatched}")


def extract_review_lane(row: dict[str, str]) -> str:
    for tag in row.get("suggested_issue_tags", "").split(";"):
        if tag.startswith("pdf_review_lane:"):
            return tag.split(":", 1)[1]
    return ""


def is_generic_filename(file_name: str) -> bool:
    return bool(re.fullmatch(r"file(?: \(\d+\))?\.pdf", file_name.strip(), re.IGNORECASE))


def count_lane(rows: list[dict[str, str]], lane: str) -> int:
    return sum(1 for row in rows if row["retrieval_lane"] == lane)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    text = f"""# PDF Manual v1 With FILE Lookup Companion

Generated at: {summary["generated_at"]}

This is a diagnostic-only merged review draft. The existing manual v1 content
retrieval pack is preserved. FILE lookup rows are evaluated by expected file
identity, not page, bbox, table, row, column, or value semantics.

## Counts

- Manual v1 content rows: `{summary["manual_v1_content_row_count"]}`
- FILE lookup companion rows: `{summary["companion_row_count"]}`
- Merged rows: `{summary["merged_row_count"]}`
- `{CONTENT_LANE}`: `{summary["pdf_file_lookup_by_content_anchor_count"]}`
- `{METADATA_LANE}`: `{summary["pdf_file_lookup_by_metadata_count"]}`
- Generic filename companion rows: `{summary["generic_filename_companion_count"]}`

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
- `bbox_contract_success_not_claimed=true`
- `table_semantics_success_claimed=false`
- `row_column_value_semantics_claimed=false`
- `file_lookup_success_claimed=false`

## Next

After user review, generate content retrieval denominator and FILE lookup
denominator candidates separately.
"""
    path.write_text(text, encoding="utf-8")


def snapshot_file(path: Path) -> dict[str, Any]:
    exists = path.exists()
    data = path.read_bytes() if exists else b""
    import hashlib

    return {
        "path": rel(path),
        "exists": exists,
        "bytes": len(data) if exists else 0,
        "sha256": hashlib.sha256(data).hexdigest() if exists else "",
    }


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
