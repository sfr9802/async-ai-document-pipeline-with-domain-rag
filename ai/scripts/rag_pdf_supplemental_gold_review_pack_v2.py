"""Create a diagnostic-only v2 supplemental PDF review draft.

The v2 draft keeps the existing v1 pack intact, rewrites the 80 content
queries into less templated Korean surfaces, and adds file-lookup companion
rows that ask only for PDF identity. It does not run an LLM, judge, retrieval,
reranking, parser expansion, DB/SearchUnit/index/candidate/baseline mutation,
promotion, official denominator, or gold-policy update.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    REPORT_DIR,
    ROOT,
    display_path,
    resolve_path,
    sorted_counter,
    utc_timestamp,
    write_csv,
    write_json,
    write_jsonl,
)


REVIEW_DIR = ROOT / "ai" / "eval" / "review" / "pdf_supplemental_gold_review"
DEFAULT_V1_CSV = REVIEW_DIR / "pdf_supplemental_gold_review_pack.csv"
DEFAULT_V1_JSONL = REVIEW_DIR / "pdf_supplemental_gold_review_pack.jsonl"
DEFAULT_V1_SUMMARY = REPORT_DIR / "rag_pdf_supplemental_gold_review_pack_summary.json"
DEFAULT_V2_CSV = REVIEW_DIR / "pdf_supplemental_gold_review_pack_v2.csv"
DEFAULT_V2_JSONL = REVIEW_DIR / "pdf_supplemental_gold_review_pack_v2.jsonl"
DEFAULT_V2_MD = REVIEW_DIR / "pdf_supplemental_gold_review_pack_v2.md"
DEFAULT_V2_SUMMARY = REPORT_DIR / "rag_pdf_supplemental_gold_review_pack_v2_summary.json"

SCHEMA_VERSION = "pdf_supplemental_gold_review_pack_v2"
CONTENT_LOOKUP_TRACK = "PDF_SUPPLEMENTAL_CONTENT_LOOKUP"
FILE_LOOKUP_TRACK = "PDF_SUPPLEMENTAL_FILE_LOOKUP"
FILE_LOOKUP_BY_METADATA = "PDF_FILE_LOOKUP_BY_METADATA"
FILE_LOOKUP_BY_CONTENT_ANCHOR = "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR"

USER_COLUMNS = [
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]

BASE_COLUMNS = [
    "track",
    "query_id",
    "parent_query_id",
    "query_surface_type",
    "dataset",
    "source_file_name",
    "expected_file_name",
    "expected_document_identity",
    "page_no",
    "page_label",
    "section_path",
    "query",
    "original_query",
    "expected_evidence_excerpt",
    "evidence_object_summary",
    "deterministic_draft",
    "review_lane",
    "recommended_lookup_lane",
    "recommended_review_action",
    "recommended_expected_evidence_scope",
    "recommended_file_lookup_policy",
    "suggested_gold_decision",
    "suggested_answerability_label",
    "suggested_relevance_label",
    "suggested_expected_evidence_policy",
    "suggested_denominator_policy",
    "risk_tags",
    "diagnostic_reason",
    "v2_query_rewrite_reason",
    "natural_query_terms",
    *USER_COLUMNS,
]

GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "promotion_evidence": False,
    "official_denominator_changed": False,
    "codex_gold_policy_decision_applied": False,
    "pdf_c7_policy_decision_applied": False,
    "external_cloud_llm_run": False,
    "live_llm_run": False,
    "live_llm_answer_generation_run": False,
    "local_llm_run": False,
    "optional_judge_run": False,
    "retrieval_tuning_applied": False,
    "reranking_applied": False,
    "parser_expansion_applied": False,
    "db_mutation_applied": False,
    "searchunit_mutation_applied": False,
    "candidate_artifact_changed": False,
    "immutable_baseline_changed": False,
    "table_semantics_success_claimed": False,
    "row_column_value_semantics_claimed": False,
    "bbox_contract_success_not_claimed": True,
    "official_gold_created": False,
    "promotion_artifact_created": False,
    "existing_pack_overwritten": False,
}

GENERIC_QUERY_PATTERNS = [
    "이 문서에서 전기요금 관련 기준이 설명된 부분 확인해줘.",
    "이 문서에서 전기요금 기준이 표로 정리된 부분 확인해줘.",
    "이 문서에서 조건이나 금액이 설명된 부분 찾아줘.",
    "이 문서에서 관련 기준이 설명된 부분 확인해줘.",
    "이 문서에서 표로 정리된 부분 확인해줘.",
]

STOP_TERMS = {
    "문서",
    "부분",
    "관련",
    "기준",
    "확인",
    "내용",
    "포함",
    "있습니다",
    "따른다",
    "해당",
    "사항",
    "표",
    "후보",
    "영역",
    "파일",
}

FOCUS_PATTERNS = [
    (re.compile(r"기후환경요금|연료비조정|슈퍼유저|전력량요금|기본요금|사용전력량|kWh", re.I), "전기요금 산정 근거"),
    (re.compile(r"전기상담|사이버지점|스마트 한전|고객|전화상담", re.I), "전기상담 채널 안내"),
    (re.compile(r"계절|하계|동계|봄|가을|겨울", re.I), "계절별 요금 적용"),
    (re.compile(r"계약전력|고압|저압|주택용|일반용", re.I), "전력 계약 구분"),
    (re.compile(r"제출물|제품자료|시공상세|공사기록|준공|성적서", re.I), "공사 제출물"),
    (re.compile(r"안전관리|정전작업|전기안전|환경관리|검측|검사", re.I), "공사 안전 기준"),
    (re.compile(r"LHCS|KCS", re.I), "LH 기준 참조"),
    (re.compile(r"임대료|보증금|전용면적|세대|주택", re.I), "주택 조건"),
]

TOPIC_RULES = [
    (re.compile(r"계절이\s*변동|계절변동일|일수계산"), "계절 변동일 기준 일수계산"),
    (re.compile(r"사이버지점|스마트\s*한전|국번없이\s*123|전기상담|전화상담"), "전기상담 채널"),
    (re.compile(r"기후환경요금"), "기후환경요금 단가와 부과 방식"),
    (re.compile(r"연료비조정"), "연료비조정요금 부과 방식"),
    (re.compile(r"슈퍼유저"), "슈퍼유저요금 적용 기간"),
    (re.compile(r"가구별\s*평균사용량|단계별로\s*요금단가"), "가구별 평균사용량 단계별 요금단가"),
    (re.compile(r"계약전력\s*300\s*kW\s*미만", re.I), "계약전력 300kW 미만 기준"),
    (re.compile(r"전력량요금"), "전력량요금 단가"),
    (re.compile(r"기본요금"), "기본요금 구분"),
    (re.compile(r"하계|동계|봄·가을철|겨울철|여름철"), "계절별 요금 구간"),
    (re.compile(r"공사사진|사진촬영"), "공사사진 촬영 기준"),
    (re.compile(r"공사기록|준공|성적서"), "준공 서류 제출 기준"),
    (re.compile(r"시공상세도"), "시공상세도 제출 기준"),
    (re.compile(r"제품자료"), "제품자료 제출 기준"),
    (re.compile(r"제출물"), "제출물 검토 기준"),
    (re.compile(r"안전관리"), "전기공사 안전관리 기준"),
    (re.compile(r"정전작업|통전시\s*조치"), "전기작업 안전조치"),
    (re.compile(r"환경관리"), "전기공사 환경관리 적용 범위"),
    (re.compile(r"용어의\s*정의"), "용어 정의 참조 기준"),
    (re.compile(r"참고\s*기준"), "참고 기준"),
    (re.compile(r"LHCS|KCS", re.I), "LH 기준 참조 조항"),
    (re.compile(r"임대료|보증금"), "임대료와 보증금 조건"),
    (re.compile(r"전용면적|세대"), "주택 면적과 세대 조건"),
]

CONTENT_FRAMES = [
    "{focus}에서 {a}와 {b}가 어떻게 연결되는지 확인해줘",
    "{a} 기준을 볼 때 {focus} 설명이 어디까지 이어지는지 확인해줘",
    "{focus} 항목 중 {a} 관련 근거를 자연어로 검수하고 싶어",
    "{a}와 {b}가 함께 언급된 근거 문장을 확인해줘",
    "{focus} 설명에서 {a} 부분이 실제 근거로 충분한지 봐줘",
    "{a} 항목의 적용 조건과 근거 문맥을 확인해줘",
    "{focus}에서 {a}가 어떤 조건으로 설명되는지 찾아줘",
    "{a} 내용이 {b}와 같은 맥락인지 검수해줘",
]


class V2BuildError(RuntimeError):
    def __init__(self, blockers: list[str]):
        self.blockers = blockers
        super().__init__("; ".join(blockers))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_v2_pack(
            v1_csv=Path(args.v1_csv),
            v1_jsonl=Path(args.v1_jsonl),
            v1_summary=Path(args.v1_summary),
            v2_csv=Path(args.v2_csv),
            v2_jsonl=Path(args.v2_jsonl),
            v2_md=Path(args.v2_md),
            v2_summary=Path(args.v2_summary),
            allow_overwrite_v2=args.allow_overwrite_v2,
        )
    except V2BuildError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "blockers": exc.blockers}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({
        "status": report["status"],
        "v1_content_row_count": report["v1_content_row_count"],
        "v2_total_row_count": report["v2_total_row_count"],
        "unique_query_count": report["unique_query_count"],
        "lane_counts": report["lane_counts"],
        "v2_csv": report["output_artifacts"]["csv"]["path"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-csv", default=str(DEFAULT_V1_CSV))
    parser.add_argument("--v1-jsonl", default=str(DEFAULT_V1_JSONL))
    parser.add_argument("--v1-summary", default=str(DEFAULT_V1_SUMMARY))
    parser.add_argument("--v2-csv", default=str(DEFAULT_V2_CSV))
    parser.add_argument("--v2-jsonl", default=str(DEFAULT_V2_JSONL))
    parser.add_argument("--v2-md", default=str(DEFAULT_V2_MD))
    parser.add_argument("--v2-summary", default=str(DEFAULT_V2_SUMMARY))
    parser.add_argument("--allow-overwrite-v2", action="store_true")
    return parser.parse_args(argv)


def build_v2_pack(
    *,
    v1_csv: Path = DEFAULT_V1_CSV,
    v1_jsonl: Path = DEFAULT_V1_JSONL,
    v1_summary: Path = DEFAULT_V1_SUMMARY,
    v2_csv: Path = DEFAULT_V2_CSV,
    v2_jsonl: Path = DEFAULT_V2_JSONL,
    v2_md: Path = DEFAULT_V2_MD,
    v2_summary: Path = DEFAULT_V2_SUMMARY,
    allow_overwrite_v2: bool = False,
) -> dict[str, Any]:
    v1_csv = resolve_path(v1_csv)
    v1_jsonl = resolve_path(v1_jsonl)
    v1_summary = resolve_path(v1_summary)
    v2_csv = resolve_path(v2_csv)
    v2_jsonl = resolve_path(v2_jsonl)
    v2_md = resolve_path(v2_md)
    v2_summary = resolve_path(v2_summary)
    blockers = validate_paths(
        v1_csv,
        v1_jsonl,
        v1_summary,
        v2_csv,
        v2_jsonl,
        v2_md,
        v2_summary,
        allow_overwrite_v2=allow_overwrite_v2,
    )
    if blockers:
        raise V2BuildError(blockers)

    v1_rows = read_csv_rows(v1_csv)
    v1_jsonl_rows = read_jsonl_rows(v1_jsonl)
    v1_summary_payload = read_json_object(v1_summary)
    validate_v1_inputs(v1_rows, v1_jsonl_rows, v1_summary_payload, blockers)
    if blockers:
        raise V2BuildError(blockers)

    v1_json_by_id = {str(row.get("query_id") or ""): row for row in v1_jsonl_rows}
    v2_rows: list[dict[str, Any]] = []
    for index, row in enumerate(v1_rows):
        json_row = v1_json_by_id.get(str(row.get("query_id") or ""), {})
        content_row, natural_terms = build_content_row(row, json_row, index)
        v2_rows.append(content_row)
        v2_rows.append(build_file_metadata_row(content_row, index))
        v2_rows.append(build_file_anchor_row(content_row, natural_terms, index))

    validate_v2_rows(v1_rows, v2_rows, blockers)
    if blockers:
        raise V2BuildError(blockers)

    write_csv(v2_csv, v2_rows, BASE_COLUMNS)
    write_jsonl(v2_jsonl, [jsonl_payload(row) for row in v2_rows])
    report = build_summary(v1_rows, v2_rows, v1_csv, v1_jsonl, v1_summary, v2_csv, v2_jsonl, v2_md, v2_summary)
    write_json(v2_summary, report)
    v2_md.write_text(build_markdown(report), encoding="utf-8")
    return report


def validate_paths(*paths: Path, allow_overwrite_v2: bool) -> list[str]:
    v1_csv, v1_jsonl, v1_summary, v2_csv, v2_jsonl, v2_md, v2_summary = paths
    blockers: list[str] = []
    for label, path in {"v1_csv": v1_csv, "v1_jsonl": v1_jsonl, "v1_summary": v1_summary}.items():
        if not path.exists():
            blockers.append(f"{label} missing: {display_path(path)}")
    v1_targets = {v1_csv.resolve(), v1_jsonl.resolve(), v1_summary.resolve()}
    for label, path in {"v2_csv": v2_csv, "v2_jsonl": v2_jsonl, "v2_md": v2_md, "v2_summary": v2_summary}.items():
        resolved = path.resolve()
        display = display_path(resolved)
        if resolved in v1_targets:
            blockers.append(f"{label} would overwrite an existing v1 pack artifact: {display}")
        if "_v2" not in resolved.name:
            blockers.append(f"{label} must use a v2 filename: {display}")
        if "supplemental" not in display.lower():
            blockers.append(f"{label} must stay supplemental-specific: {display}")
        if path.exists() and not allow_overwrite_v2:
            blockers.append(f"{label} already exists; pass --allow-overwrite-v2 for explicit regeneration: {display}")
    return blockers


def validate_v1_inputs(v1_rows: list[dict[str, str]], jsonl_rows: list[dict[str, Any]], summary: Mapping[str, Any], blockers: list[str]) -> None:
    if len(v1_rows) != 80:
        blockers.append(f"v1 CSV row count expected 80, got {len(v1_rows)}")
    if len(jsonl_rows) != 80:
        blockers.append(f"v1 JSONL row count expected 80, got {len(jsonl_rows)}")
    if summary.get("review_row_count") != 80:
        blockers.append(f"v1 summary review_row_count expected 80, got {summary.get('review_row_count')!r}")
    for key, expected in {
        "promotion_evidence": False,
        "official_denominator_changed": False,
        "codex_gold_policy_decision_applied": False,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
        "bbox_contract_success_not_claimed": True,
    }.items():
        if summary.get(key) != expected:
            blockers.append(f"v1 summary guardrail {key} expected {expected!r}, got {summary.get(key)!r}")
    query_ids = [row.get("query_id", "") for row in v1_rows]
    if len(query_ids) != len(set(query_ids)):
        blockers.append("v1 CSV has duplicate query_id values")


def build_content_row(row: Mapping[str, str], json_row: Mapping[str, Any], index: int) -> tuple[dict[str, Any], list[str]]:
    text = " ".join([
        row.get("expected_evidence_excerpt", ""),
        row.get("deterministic_draft", ""),
        row.get("section_path", ""),
        row.get("evidence_object_summary", ""),
    ])
    terms = derive_natural_terms(row, text)
    query = natural_content_query(row, terms, index)
    merged = dict(row)
    merged.update(GUARDRAILS)
    merged.update({
        "track": CONTENT_LOOKUP_TRACK,
        "parent_query_id": row.get("query_id", ""),
        "query_surface_type": CONTENT_LOOKUP_TRACK,
        "expected_file_name": "",
        "expected_document_identity": document_identity(row),
        "query": query,
        "original_query": row.get("query", ""),
        "recommended_lookup_lane": CONTENT_LOOKUP_TRACK,
        "recommended_review_action": "USER_REVIEW_CONTENT_QUERY_SURFACE_AND_EVIDENCE",
        "recommended_expected_evidence_scope": "content_evidence_excerpt_or_context_only",
        "recommended_file_lookup_policy": "not_a_file_lookup_row",
        "v2_query_rewrite_reason": "generic v1 template replaced with content-grounded natural Korean query; source_file_name excluded",
        "natural_query_terms": terms,
    })
    for column in USER_COLUMNS:
        merged[column] = ""
    return merged, terms


def build_file_metadata_row(content_row: Mapping[str, Any], index: int) -> dict[str, Any]:
    file_name = str(content_row.get("source_file_name") or "")
    dataset = str(content_row.get("dataset") or "")
    section = clean_phrase(str(content_row.get("section_path") or ""))
    query = f"{dataset} supplemental 자료에서 파일명 {file_name}의 문서 식별 정보를 확인해줘"
    if section:
        query = f"{dataset} supplemental 자료에서 파일명 {file_name}와 {shorten(section, 28)} 항목의 문서 식별 정보를 확인해줘"
    return file_lookup_row(
        content_row,
        suffix="file_meta_v2",
        lane=FILE_LOOKUP_BY_METADATA,
        query=query,
        expected_evidence=f"expected_file_name={file_name}; dataset={dataset}; document_identity={document_identity(content_row)}",
        reason="metadata lookup companion row; expected evidence is file identity only",
        index=index,
    )


def build_file_anchor_row(content_row: Mapping[str, Any], terms: list[str], index: int) -> dict[str, Any]:
    file_name = str(content_row.get("source_file_name") or "")
    anchor = terms[0] if terms else clean_phrase(str(content_row.get("section_path") or ""))
    second = terms[1] if len(terms) > 1 else clean_phrase(str(content_row.get("dataset") or "PDF"))
    if anchor and second and anchor != second:
        query = f"{join_with_and(anchor, second)} 내용이 들어 있는 PDF 파일명을 찾아줘"
    elif anchor:
        query = f"{anchor} 내용이 들어 있는 PDF 파일명을 찾아줘"
    else:
        query = f"{document_identity(content_row)}에 해당하는 PDF 파일명을 확인해줘"
    return file_lookup_row(
        content_row,
        suffix="file_anchor_v2",
        lane=FILE_LOOKUP_BY_CONTENT_ANCHOR,
        query=query,
        expected_evidence=f"expected_file_name={file_name}; content_anchor={anchor}; document_identity={document_identity(content_row)}",
        reason="content-anchor file lookup companion row; no page, bbox, or table semantics required",
        index=index,
    )


def file_lookup_row(
    content_row: Mapping[str, Any],
    *,
    suffix: str,
    lane: str,
    query: str,
    expected_evidence: str,
    reason: str,
    index: int,
) -> dict[str, Any]:
    row = {key: content_row.get(key, "") for key in BASE_COLUMNS}
    parent_query_id = str(content_row.get("parent_query_id") or content_row.get("query_id") or f"row_{index:04d}")
    file_name = str(content_row.get("source_file_name") or "")
    row.update(GUARDRAILS)
    row.update({
        "track": FILE_LOOKUP_TRACK,
        "query_id": f"{parent_query_id}__{suffix}",
        "parent_query_id": parent_query_id,
        "query_surface_type": lane,
        "source_file_name": file_name,
        "expected_file_name": file_name,
        "expected_document_identity": document_identity(content_row),
        "page_no": "",
        "page_label": "",
        "section_path": "",
        "query": query,
        "original_query": content_row.get("query", ""),
        "expected_evidence_excerpt": expected_evidence,
        "evidence_object_summary": "document identity lookup only; page, bbox, table, and row/column/value semantics are not required",
        "deterministic_draft": "",
        "review_lane": lane,
        "recommended_lookup_lane": lane,
        "recommended_review_action": "USER_REVIEW_FILE_IDENTITY_LOOKUP_ONLY",
        "recommended_expected_evidence_scope": "expected_file_name_or_document_identity_only",
        "recommended_file_lookup_policy": "no_page_bbox_table_semantics_required",
        "suggested_gold_decision": "USER_REVIEW_REQUIRED_FILE_LOOKUP_COMPANION",
        "suggested_answerability_label": "file_identity_answerability_requires_user_review",
        "suggested_relevance_label": "file_identity_relevance_requires_user_review",
        "suggested_expected_evidence_policy": "expected_file_name_or_document_identity_only",
        "suggested_denominator_policy": "no_official_change_user_must_decide",
        "risk_tags": ["file_lookup_companion", "no_page_bbox_table_semantics_required"],
        "diagnostic_reason": reason,
        "v2_query_rewrite_reason": reason,
        "natural_query_terms": [],
    })
    for column in USER_COLUMNS:
        row[column] = ""
    return row


def natural_content_query(row: Mapping[str, str], terms: list[str], index: int) -> str:
    a = terms[0] if terms else fallback_term(row)
    b = terms[1] if len(terms) > 1 else fallback_secondary(row, a)
    focus = focus_for(" ".join([row.get("expected_evidence_excerpt", ""), row.get("section_path", ""), a, b]))
    if a == b:
        b = fallback_secondary(row, a)
    frame_index = index % 8
    if frame_index == 0:
        query = f"{focus}에서 {with_subject_particle(join_with_and(a, b))} 어떻게 연결되는지 확인해줘"
    elif frame_index == 1:
        query = f"{a} 기준을 볼 때 {focus} 설명이 어디까지 이어지는지 확인해줘"
    elif frame_index == 2:
        query = f"{focus} 항목 중 {a} 관련 근거를 자연어로 검수하고 싶어"
    elif frame_index == 3:
        query = f"{with_subject_particle(join_with_and(a, b))} 함께 언급된 근거 문장을 확인해줘"
    elif frame_index == 4:
        query = f"{focus} 설명에서 {a} 부분이 실제 근거로 충분한지 봐줘"
    elif frame_index == 5:
        query = f"{a} 항목의 적용 조건과 근거 문맥을 확인해줘"
    elif frame_index == 6:
        query = f"{focus}에서 {with_subject_particle(a)} 어떤 조건으로 설명되는지 찾아줘"
    else:
        query = f"{a} 내용이 {with_and_particle(b)} 같은 맥락인지 검수해줘"
    query = re.sub(r"\s+", " ", query).strip()
    source_file_name = row.get("source_file_name", "")
    if source_file_name and source_file_name in query:
        query = query.replace(source_file_name, "해당 PDF")
    return query


def derive_natural_terms(row: Mapping[str, str], text: str) -> list[str]:
    section = natural_section(row.get("section_path", ""))
    topic = topic_from_text(text)
    terms: list[str] = []
    if topic:
        terms.append(topic)
    if section and section.lower() != topic.lower():
        terms.append(section)
    for extracted in extract_terms(text, dataset=row.get("dataset", "")):
        normalized = extracted.lower()
        if not any(normalized in term.lower() or term.lower() in normalized for term in terms):
            terms.append(extracted)
        if len(terms) >= 3:
            break
    if not terms:
        terms.append(fallback_term(row))
    return [shorten(term, 34) for term in terms[:3]]


def topic_from_text(text: str) -> str:
    compact = re.sub(r"\s+", " ", text or "")
    for pattern, label in TOPIC_RULES:
        if pattern.search(compact):
            return label
    return ""


def natural_section(section: str) -> str:
    section = clean_phrase(section)
    section = re.sub(r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*시행\s*", "", section)
    section = re.sub(r"^\d+\.\s*", "", section)
    section = section.replace("|", " ")
    section = re.sub(r"\b([가-힣A-Za-z0-9()]+)\s+\1\b", r"\1", section)
    return shorten(section, 30)


def join_with_and(left: str, right: str) -> str:
    if not right or left == right:
        return left
    return f"{with_and_particle(left)} {right}"


def with_and_particle(value: str) -> str:
    return f"{value}{'과' if has_final_consonant(value) else '와'}"


def with_subject_particle(value: str) -> str:
    return f"{value}{'이' if has_final_consonant(value) else '가'}"


def has_final_consonant(value: str) -> bool:
    for char in reversed(value.strip()):
        if "가" <= char <= "힣":
            return (ord(char) - ord("가")) % 28 != 0
        if char.isdigit():
            return char in {"0", "1", "3", "6", "7", "8"}
        if char.isalpha():
            return False
    return False


def extract_terms(text: str, *, dataset: str) -> list[str]:
    clean = re.sub(r"https?://\S+|www\.\S+|[A-Za-z0-9_.+-]+\.pdf", " ", text or "")
    clean = clean.replace("…", " ")
    candidates: list[str] = []
    for pattern in [
        r"[가-힣A-Za-z0-9()ㆍ·/%~+\-]{2,24}요금[가-힣A-Za-z0-9()ㆍ·/%~+\-]{0,16}",
        r"[가-힣A-Za-z0-9()ㆍ·/%~+\-]{2,24}관리[가-힣A-Za-z0-9()ㆍ·/%~+\-]{0,16}",
        r"[가-힣A-Za-z0-9()ㆍ·/%~+\-]{2,24}제출[가-힣A-Za-z0-9()ㆍ·/%~+\-]{0,16}",
        r"[가-힣A-Za-z0-9()ㆍ·/%~+\-]{2,24}공사[가-힣A-Za-z0-9()ㆍ·/%~+\-]{0,16}",
        r"[가-힣A-Za-z0-9()ㆍ·/%~+\-]{2,24}기준[가-힣A-Za-z0-9()ㆍ·/%~+\-]{0,16}",
        r"(?:LHCS|KCS)\s*(?:\d+\s*){2,}",
        r"\d[\d,]*(?:\.\d+)?\s*(?:원|kWh|kw|%|개월|년|월|일|㎡|세대|호)",
        r"[가-힣][가-힣0-9()ㆍ·/%~+\- ]{3,24}",
    ]:
        candidates.extend(re.findall(pattern, clean, flags=re.I))
    scored: list[tuple[int, str]] = []
    for candidate in candidates:
        phrase = clean_phrase(candidate)
        if not useful_phrase(phrase):
            continue
        score = len(phrase)
        if re.search(r"요금|제출|시공|안전|관리|전력|계약|사용량|LHCS|KCS|kWh|원", phrase, re.I):
            score += 20
        if dataset == "lh" and re.search(r"공사|시공|제출|안전|LHCS|KCS", phrase, re.I):
            score += 15
        scored.append((score, phrase))
    result: list[str] = []
    seen: set[str] = set()
    for _, phrase in sorted(scored, key=lambda item: (-item[0], item[1])):
        normalized = phrase.lower()
        if normalized in seen:
            continue
        if any(normalized in prior.lower() or prior.lower() in normalized for prior in result):
            continue
        seen.add(normalized)
        result.append(shorten(phrase, 32))
        if len(result) >= 3:
            break
    return result


def clean_phrase(value: str) -> str:
    value = re.sub(r"[\[\]{}\"'`]", " ", value or "")
    value = re.sub(r"\s+", " ", value).strip(" ,.;:|/-")
    value = re.sub(r"^(evidence|nearby|quality_reason|citation)=", "", value)
    return value.strip()


def useful_phrase(phrase: str) -> bool:
    if len(phrase) < 2 or len(phrase) > 40:
        return False
    lowered = phrase.lower()
    if lowered.endswith(".pdf"):
        return False
    if any(term == phrase for term in STOP_TERMS):
        return False
    if sum(1 for char in phrase if char.isdigit()) > max(10, len(phrase) // 2):
        return bool(re.search(r"원|kWh|%|년|월|일|LHCS|KCS", phrase, re.I))
    return True


def focus_for(text: str) -> str:
    for pattern, focus in FOCUS_PATTERNS:
        if pattern.search(text or ""):
            return focus
    return "PDF 근거 문맥"


def fallback_term(row: Mapping[str, str]) -> str:
    for key in ("section_path", "expected_evidence_excerpt", "deterministic_draft", "dataset"):
        terms = extract_terms(row.get(key, ""), dataset=row.get("dataset", ""))
        if terms:
            return terms[0]
    return "핵심 근거"


def fallback_secondary(row: Mapping[str, str], first: str) -> str:
    section = clean_phrase(row.get("section_path", ""))
    if section and section != first:
        return shorten(section, 24)
    dataset = row.get("dataset", "").strip()
    return "근거 문맥" if not dataset else f"{dataset} 자료"


def document_identity(row: Mapping[str, Any]) -> str:
    dataset = str(row.get("dataset") or "")
    file_name = str(row.get("source_file_name") or "")
    section = clean_phrase(str(row.get("section_path") or ""))
    parts = [part for part in [dataset, file_name, shorten(section, 40)] if part]
    return " / ".join(parts)


def shorten(value: str, max_chars: int) -> str:
    value = clean_phrase(value)
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


def validate_v2_rows(v1_rows: list[Mapping[str, str]], v2_rows: list[Mapping[str, Any]], blockers: list[str]) -> None:
    if len(v2_rows) != len(v1_rows) * 3:
        blockers.append(f"v2 row count expected {len(v1_rows) * 3}, got {len(v2_rows)}")
    query_ids = [str(row.get("query_id") or "") for row in v2_rows]
    duplicates = [query_id for query_id, count in Counter(query_ids).items() if query_id and count > 1]
    if duplicates:
        blockers.append(f"duplicate query_id values in v2: {duplicates[:5]}")
    for row in v2_rows:
        for column in USER_COLUMNS:
            if row.get(column) not in ("", None):
                blockers.append(f"user column not blank: {row.get('query_id')} {column}")
        for key, expected in {
            "promotion_evidence": False,
            "official_denominator_changed": False,
            "codex_gold_policy_decision_applied": False,
            "table_semantics_success_claimed": False,
            "row_column_value_semantics_claimed": False,
            "bbox_contract_success_not_claimed": True,
        }.items():
            if row.get(key) != expected:
                blockers.append(f"{row.get('query_id')} guardrail {key} expected {expected!r}, got {row.get(key)!r}")
        if row.get("track") == CONTENT_LOOKUP_TRACK:
            old_query = str(row.get("original_query") or "")
            query = str(row.get("query") or "")
            if query in GENERIC_QUERY_PATTERNS or query == old_query:
                blockers.append(f"content query remained generic: {row.get('query_id')}")
            file_name = str(row.get("source_file_name") or "")
            if file_name and file_name in query:
                blockers.append(f"content query leaks source_file_name: {row.get('query_id')}")
        if row.get("track") == FILE_LOOKUP_TRACK:
            if row.get("page_no") or row.get("page_label") or row.get("section_path"):
                blockers.append(f"file lookup row should not require page/section locator: {row.get('query_id')}")
            if row.get("review_lane") not in {FILE_LOOKUP_BY_METADATA, FILE_LOOKUP_BY_CONTENT_ANCHOR}:
                blockers.append(f"invalid file lookup lane: {row.get('query_id')} {row.get('review_lane')}")
    content_queries = [str(row.get("query") or "") for row in v2_rows if row.get("track") == CONTENT_LOOKUP_TRACK]
    if len(set(content_queries)) < max(60, len(v1_rows) // 2):
        blockers.append(f"content query uniqueness too low: {len(set(content_queries))}/{len(content_queries)}")


def build_summary(
    v1_rows: list[Mapping[str, str]],
    v2_rows: list[Mapping[str, Any]],
    v1_csv: Path,
    v1_jsonl: Path,
    v1_summary: Path,
    v2_csv: Path,
    v2_jsonl: Path,
    v2_md: Path,
    v2_summary: Path,
) -> dict[str, Any]:
    lane_counts = sorted_counter(Counter(str(row.get("review_lane") or "") for row in v2_rows))
    track_counts = sorted_counter(Counter(str(row.get("track") or "") for row in v2_rows))
    content_queries = [str(row.get("query") or "") for row in v2_rows if row.get("track") == CONTENT_LOOKUP_TRACK]
    all_queries = [str(row.get("query") or "") for row in v2_rows]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "PASS",
        **GUARDRAILS,
        "evidence_role": "diagnostic",
        "analysis_role": "diagnostic_v2_query_surface_and_file_lookup_review_draft_only",
        "v1_content_row_count": len(v1_rows),
        "v2_total_row_count": len(v2_rows),
        "v2_content_row_count": len(content_queries),
        "v2_file_lookup_row_count": sum(1 for row in v2_rows if row.get("track") == FILE_LOOKUP_TRACK),
        "unique_query_count": len(set(all_queries)),
        "unique_content_query_count": len(set(content_queries)),
        "duplicate_query_id_count": len(v2_rows) - len({row.get("query_id") for row in v2_rows}),
        "user_columns_blank": all(all(row.get(column, "") == "" for column in USER_COLUMNS) for row in v2_rows),
        "lane_counts": lane_counts,
        "track_counts": track_counts,
        "file_lookup_lanes": [FILE_LOOKUP_BY_METADATA, FILE_LOOKUP_BY_CONTENT_ANCHOR],
        "content_query_source_file_name_leak_count": sum(
            1
            for row in v2_rows
            if row.get("track") == CONTENT_LOOKUP_TRACK
            and row.get("source_file_name")
            and str(row.get("source_file_name")) in str(row.get("query"))
        ),
        "generic_template_query_count": sum(1 for row in v2_rows if row.get("query") in GENERIC_QUERY_PATTERNS),
        "input_artifacts": {
            "v1_csv": artifact_snapshot(v1_csv),
            "v1_jsonl": artifact_snapshot(v1_jsonl),
            "v1_summary": artifact_snapshot(v1_summary),
        },
        "output_artifacts": {
            "csv": artifact_snapshot(v2_csv, exists=True),
            "jsonl": artifact_snapshot(v2_jsonl, exists=True),
            "markdown": artifact_snapshot(v2_md, exists=True),
            "summary_json": artifact_snapshot(v2_summary, exists=True),
        },
        "notes": [
            "v1 pack artifacts were read only and not overwritten.",
            "Content lookup rows exclude source_file_name from query text.",
            "File lookup companion rows expect file/document identity only and do not require bbox, page, or table semantics.",
            "recommended_* and suggested_* fields are diagnostic suggestions only; user_* fields remain blank.",
        ],
    }


def build_markdown(report: Mapping[str, Any]) -> str:
    lane_lines = "\n".join(f"| {lane} | {count} |" for lane, count in report["lane_counts"].items())
    track_lines = "\n".join(f"| {track} | {count} |" for track, count in report["track_counts"].items())
    return f"""# PDF Supplemental Gold Review Pack v2

이 v2 draft는 v1 pack을 overwrite하지 않고 생성한 diagnostic-only review draft입니다.
content lookup query surface와 PDF file lookup companion lane을 분리했습니다.

## Artifacts

- CSV: `{report["output_artifacts"]["csv"]["path"]}`
- JSONL: `{report["output_artifacts"]["jsonl"]["path"]}`
- Summary: `{report["output_artifacts"]["summary_json"]["path"]}`

## Counts

- v1 content rows read: `{report["v1_content_row_count"]}`
- v2 total rows: `{report["v2_total_row_count"]}`
- v2 content rows: `{report["v2_content_row_count"]}`
- v2 file lookup rows: `{report["v2_file_lookup_row_count"]}`
- unique queries: `{report["unique_query_count"]}`
- unique content queries: `{report["unique_content_query_count"]}`

| track | rows |
| --- | ---: |
{track_lines}

| review_lane | rows |
| --- | ---: |
{lane_lines}

## Review Boundaries

- `PDF_SUPPLEMENTAL_CONTENT_LOOKUP` rows use naturalized content queries and do not include `source_file_name` in the query text.
- `PDF_FILE_LOOKUP_BY_METADATA` rows check document identity by metadata such as expected file name.
- `PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR` rows check document identity from a content anchor.
- File lookup rows do not require page, bbox, table semantics, or row-column-value semantics.
- `user_*` columns remain blank. Only `recommended_*` and `suggested_*` fields provide diagnostic suggestions.

## Guardrails

- `promotion_evidence=false`
- `official_denominator_changed=false`
- `codex_gold_policy_decision_applied=false`
- `pdf_c7_policy_decision_applied=false`
- `table_semantics_success_claimed=false`
- `row_column_value_semantics_claimed=false`
- `bbox_contract_success_not_claimed=true`
- live/cloud/local LLM call and optional judge were not run.
- Retrieval tuning, reranking, parser expansion, DB/SearchUnit/index/candidate/baseline changes were not performed.
"""


def jsonl_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload.update(GUARDRAILS)
    payload["diagnostic_only_review_pack_v2_row"] = True
    return payload


def artifact_snapshot(path: Path, *, exists: bool | None = None) -> dict[str, Any]:
    exists = path.exists() if exists is None else exists
    return {
        "path": display_path(path),
        "exists": exists,
        "sha256": sha256_file(path) if path.exists() else None,
        "size_bytes": path.stat().st_size if path.exists() else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {display_path(path)}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
