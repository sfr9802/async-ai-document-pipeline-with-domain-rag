"""Build a diagnostic-only PDF supplemental gold-review v3 draft.

This is a PDF goldset review draft, not an official gold set. The row source is
the existing PDF supplemental 80-row review pack. XLSX and NamuWiki v4 gold
artifacts are reference material for review-pack shape and natural Korean query
style only; they are not used as PDF gold evidence.

The query surfaces below are manually curated by query_id. The script only
materializes and validates that manual curation into CSV/JSONL/Markdown/summary
artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review" / "pdf_supplemental_gold_review"
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
DEFAULT_SOURCE_CSV = REVIEW_DIR / "pdf_supplemental_gold_review_pack.csv"
DEFAULT_OUTPUT_PREFIX = "pdf_supplemental_gold_review_pack_v3_manual_curated"
SUMMARY_NAME = "rag_pdf_supplemental_gold_review_pack_v3_manual_curated_summary.json"

REFERENCE_FILES = [
    REVIEW_DIR / "pdf_supplemental_gold_review_pack.csv",
    REVIEW_DIR / "pdf_supplemental_gold_review_pack_v2.csv",
    AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "phase7"
    / "7.12_silver_manual_curated"
    / "queries_v4_silver_manual_curated_500.jsonl",
    AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "phase7"
    / "seeds"
    / "gold_seed_50_manual_curated"
    / "gold_seed_50_candidates.csv",
    AI_WORKER_ROOT
    / "eval"
    / "artifacts"
    / "eval_runs"
    / "pdf_xlsx_gold_human_review_pack_20260506T093337Z"
    / "xlsx_gold_human_review_pack.csv",
]

USER_COLUMNS = [
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]

GUARDRAIL_COLUMNS = {
    "diagnostic_only": "true",
    "evidence_role": "diagnostic",
    "promotion_evidence": "false",
    "official_denominator_changed": "false",
    "codex_gold_policy_decision_applied": "false",
    "pdf_c7_policy_decision_applied": "false",
    "table_semantics_success_claimed": "false",
    "row_column_value_semantics_claimed": "false",
    "bbox_contract_success_not_claimed": "true",
    "live_llm_run": "false",
    "optional_judge_run": "false",
    "retrieval_tuning_applied": "false",
    "reranking_applied": "false",
    "parser_expansion_applied": "false",
    "db_searchunit_index_candidate_baseline_changed": "false",
}


MANUAL_CURATIONS: dict[str, dict[str, str]] = {
    "supp_elec_d73432a97b_p1_0005": {
        "query": "주택용 저압 전기요금에서 계절이 바뀌는 날은 사용량별 요금을 어떻게 계산해",
        "file_anchor_query": "계절 변동일 기준으로 일수계산한다고 설명한 주택용 저압 전기요금 PDF를 찾아줘",
        "anchor": "계절 변동일 기준 일수계산",
        "note": "요금표 자체보다 계절변동일 계산 설명을 확인하는 content lookup으로 정리했다.",
    },
    "supp_elec_d73432a97b_p2_0004": {
        "query": "주택용 저압 전기요금 안내에서 한전 상담 채널은 어디에 정리돼 있어",
        "file_anchor_query": "사이버지점과 스마트 한전 앱 같은 상담 채널 안내가 들어 있는 PDF를 찾아줘",
        "anchor": "사이버지점 스마트 한전 전기상담 채널",
        "note": "파일명이나 페이지를 직접 묻지 않고 상담 채널 안내 문맥으로 자연화했다.",
    },
    "supp_elec_5db341e8bf_p1_0010": {
        "query": "전기요금 종합표에서 계약전력 300킬로와트 미만 조건은 어디에 나와",
        "file_anchor_query": "계약전력 300킬로와트 미만 조건을 담은 전기요금 종합 PDF를 찾아줘",
        "anchor": "계약전력 300kW미만",
        "note": "짧은 별표 근거라 section summary 후보로만 검수하도록 했다.",
    },
    "supp_elec_5db341e8bf_p2_0009": {
        "query": "전기요금 종합 안내에서 한전 상담 채널 목록을 확인하고 싶어",
        "file_anchor_query": "트위터 페이스북 블로그 인스타그램 상담 채널 안내가 있는 전기요금 PDF를 찾아줘",
        "anchor": "한전 상담 채널 목록",
        "note": "상담 채널 반복 row를 종합 안내 문맥으로 분리했다.",
    },
    "supp_elec_8be2c46ed9_p1_0013": {
        "query": "2022년 4월 기준 기후환경요금 단가는 얼마로 설명돼 있어",
        "file_anchor_query": "기후환경요금 단가가 7.3원으로 설명된 전기요금 PDF를 찾아줘",
        "anchor": "기후환경요금단가 7.3원",
        "note": "핵심 값은 포함하되 공식 값 성공이 아니라 evidence review로 둔다.",
    },
    "supp_elec_8be2c46ed9_p1_0014": {
        "query": "주택용 고압 전기요금 안내에서 온라인 상담 채널은 어떤 항목으로 안내돼",
        "file_anchor_query": "스마트 한전 앱과 한전 SNS 안내가 있는 주택용 고압 전기요금 PDF를 찾아줘",
        "anchor": "스마트 한전 앱 한전 SNS 안내",
        "note": "상담 채널 내용이 요금 구조 하단 안내인지 확인하는 row다.",
    },
    "supp_elec_8be2c46ed9_p1_0015": {
        "query": "전기상담 전화 123은 어떤 운영 시간으로 안내돼 있어",
        "file_anchor_query": "국번없이 123과 365일 24시간 전화상담 설명이 있는 PDF를 찾아줘",
        "anchor": "국번없이 123 365일 24시간 전화상담",
        "note": "상담 전화 안내를 직접 묻는 자연어 query로 정리했다.",
    },
    "supp_elec_6bd1f748a3_p1_0018": {
        "query": "2022년 4월 주택용 저압 전기요금에서 기후환경요금 단가는 얼마야",
        "file_anchor_query": "주택용 저압 전기요금 구조에서 기후환경요금 7.3원 안내가 있는 PDF를 찾아줘",
        "anchor": "주택용 저압 기후환경요금 7.3원",
        "note": "고압 row와 구분되도록 저압 문맥을 넣었다.",
    },
    "supp_elec_6bd1f748a3_p1_0019": {
        "query": "주택용 저압 전기요금표에서 한전 온라인 상담 안내는 어디에 있어",
        "file_anchor_query": "주택용 저압 전기요금표와 한전 온라인 상담 안내가 함께 있는 PDF를 찾아줘",
        "anchor": "주택용 저압 한전 온라인 상담 안내",
        "note": "반복 상담 안내라도 문서 유형을 구분해 검수할 수 있게 했다.",
    },
    "supp_elec_6bd1f748a3_p1_0020": {
        "query": "주택용 저압 요금표의 전기상담 123 안내 문구를 확인해줘",
        "file_anchor_query": "주택용 저압 요금표에서 국번없이 123 전화상담 안내가 있는 PDF를 찾아줘",
        "anchor": "전기상담 국번없이 123",
        "note": "상담 안내 text evidence 후보로만 유지한다.",
    },
    "supp_elec_c456f27e5d_p1_0023": {
        "query": "2023년 11월 주택용 고압 전기요금에서 기후환경요금 단가는 어떻게 적혀 있어",
        "file_anchor_query": "2023년 11월 시행 주택용 고압 전기요금의 기후환경요금 9원 설명이 있는 PDF를 찾아줘",
        "anchor": "주택용 고압 기후환경요금 9원",
        "note": "시행 시기와 전압 구분을 문장에 넣어 중복 row를 줄였다.",
    },
    "supp_elec_c456f27e5d_p1_0024": {
        "query": "2023년 주택용 고압 요금표에서 전기상담 123 안내가 있는지 확인해줘",
        "file_anchor_query": "2023년 주택용 고압 요금표와 전기상담 123 안내가 함께 있는 PDF를 찾아줘",
        "anchor": "2023년 주택용 고압 전기상담 123",
        "note": "파일명을 쓰지 않고 시행연도와 문서 내용을 anchor로 삼았다.",
    },
    "supp_elec_5632eb03a2_p1_0028": {
        "query": "2023년 11월 주택용 저압 전기요금의 기후환경요금 단가를 확인해줘",
        "file_anchor_query": "2023년 11월 주택용 저압 전기요금에서 기후환경요금 9원을 설명한 PDF를 찾아줘",
        "anchor": "주택용 저압 기후환경요금 9원",
        "note": "고압과 저압을 분리해 사람이 검수하기 쉬운 질의로 만들었다.",
    },
    "supp_elec_5632eb03a2_p1_0029": {
        "query": "2023년 주택용 저압 요금표에서 24시간 전기상담 안내를 찾아줘",
        "file_anchor_query": "2023년 주택용 저압 요금표에 365일 24시간 전화상담 문구가 있는 PDF를 찾아줘",
        "anchor": "365일 24시간 전화상담",
        "note": "상담 채널 row의 구체 anchor를 운영 시간으로 잡았다.",
    },
    "supp_elec_625588fd70_p1_0034": {
        "query": "2024년 10월 시행 전기요금표에서 주택용 저압 기타계절 항목은 어디에 있어",
        "file_anchor_query": "2024년 10월 시행 전기요금에서 주택용 저압 기타계절 항목이 있는 PDF를 찾아줘",
        "anchor": "주택용전력 저압 기타계절",
        "note": "OCR 공백이 섞인 원문을 사람이 검색할 법한 표면으로 정리했다.",
    },
    "supp_elec_625588fd70_p1_0035": {
        "query": "2024년 10월 종합 전기요금표에서 계약전력 1000킬로와트 미만 조건을 찾아줘",
        "file_anchor_query": "계약전력 1000킬로와트 미만 조건이 있는 2024년 10월 전기요금 PDF를 찾아줘",
        "anchor": "계약전력 1,000kW미만",
        "note": "짧은 표 조각이므로 조건 검수 row로 보수적으로 뒀다.",
    },
    "supp_elec_bc85e2bfb2_p1_0039": {
        "query": "2024년 1월 종합 전기요금에서 하계 슈퍼유저요금은 어떻게 적용돼",
        "file_anchor_query": "하계 1000킬로와트시 초과 전력량요금 736.2원 설명이 있는 PDF를 찾아줘",
        "anchor": "하계 1,000kWh초과 736.2원",
        "note": "슈퍼유저요금의 계절과 단가가 핵심 anchor다.",
    },
    "supp_elec_bc85e2bfb2_p1_0040": {
        "query": "2024년 1월 종합 전기요금표에서 산업용전력 갑 1 항목은 어디에 있어",
        "file_anchor_query": "산업용전력 갑 1 계약전력 300킬로와트 미만 항목이 있는 PDF를 찾아줘",
        "anchor": "산업용전력(갑)Ⅰ 계약전력 300kW미만",
        "note": "산업용 항목 lookup으로 상담 안내와 구분했다.",
    },
    "supp_elec_8659b3db62_p1_0043": {
        "query": "2024년 1월 주택용 고압에서 동계 슈퍼유저요금 단가는 얼마야",
        "file_anchor_query": "주택용 고압 동계 1000킬로와트시 초과 601.3원 설명이 있는 PDF를 찾아줘",
        "anchor": "주택용 고압 동계 601.3원",
        "note": "주택용 고압의 동계 슈퍼유저 단가 검수 row다.",
    },
    "supp_elec_8659b3db62_p1_0044": {
        "query": "2024년 1월 주택용 고압 요금표에서 전기상담 안내 문구를 찾아줘",
        "file_anchor_query": "2024년 주택용 고압 요금표에 전기상담 123 문구가 있는 PDF를 찾아줘",
        "anchor": "주택용 고압 전기상담 123",
        "note": "동일 상담 안내라도 문서군 식별에 쓰는 companion anchor를 분리했다.",
    },
    "supp_elec_493679be9f_p1_0048": {
        "query": "2024년 1월 주택용 저압에서 동계 슈퍼유저요금 단가는 어떻게 적혀 있어",
        "file_anchor_query": "주택용 저압 동계 1000킬로와트시 초과 736.2원 설명이 있는 PDF를 찾아줘",
        "anchor": "주택용 저압 동계 736.2원",
        "note": "저압의 동계 슈퍼유저 단가를 고압 row와 구분했다.",
    },
    "supp_elec_493679be9f_p1_0049": {
        "query": "2024년 1월 주택용 저압 요금표의 한전 상담 안내를 확인해줘",
        "file_anchor_query": "2024년 주택용 저압 요금표와 한전 상담 채널 안내가 함께 있는 PDF를 찾아줘",
        "anchor": "주택용 저압 한전 상담 채널",
        "note": "content query에서 source file name은 넣지 않았다.",
    },
    "supp_elec_0cc37a0bed_p1_0054": {
        "query": "2024년 4월 종합 전기요금에서 하계 슈퍼유저요금은 얼마로 적용돼",
        "file_anchor_query": "2024년 4월 종합 전기요금에서 하계 736.2원 슈퍼유저요금 설명이 있는 PDF를 찾아줘",
        "anchor": "2024년 4월 하계 슈퍼유저요금 736.2원",
        "note": "1월 종합표와 구분하기 위해 시행월을 문장화했다.",
    },
    "supp_elec_0cc37a0bed_p1_0055": {
        "query": "2024년 4월 종합 전기요금표의 산업용전력 갑 1 조건을 찾아줘",
        "file_anchor_query": "2024년 4월 전기요금표에서 산업용전력 갑 1 조건이 있는 PDF를 찾아줘",
        "anchor": "2024년 4월 산업용전력(갑)Ⅰ",
        "note": "산업용전력 항목의 section summary 후보로 둔다.",
    },
    "supp_lh_67760ba504_p1_0148": {
        "query": "LH 전문시방서 일반사항에서 이 기준의 적용 대상은 어떻게 설명돼",
        "file_anchor_query": "LH에서 발주하는 건설공사 전문시방서 일반사항이 들어 있는 PDF를 찾아줘",
        "anchor": "LH 발주 건설공사 전문시방서 일반사항",
        "note": "깨진 문구를 쓰지 않고 LH 일반사항의 적용 범위 query로 정리했다.",
    },
    "supp_lh_67760ba504_p4_0150": {
        "query": "LH 시방서에서 건설사업관리는 어떤 법 기준으로 정의돼",
        "file_anchor_query": "건설산업기본법 제2조에 따른 건설사업관리 정의가 있는 LH PDF를 찾아줘",
        "anchor": "건설산업기본법 제2조 건설사업관리",
        "note": "용어 정의 excerpt를 answerable한 자연어 lookup으로 만들었다.",
    },
    "supp_lh_7e8ae40964_p6_0086": {
        "query": "사급자재 제출물은 어떤 LH 기준을 따른다고 되어 있어",
        "file_anchor_query": "사급자재와 LHCS 10 10 20 05가 함께 나오는 LH PDF를 찾아줘",
        "anchor": "사급자재 LHCS 10 10 20 05",
        "note": "짧은 reference 조각이라 extractive context 후보로만 검수한다.",
    },
    "supp_lh_7e8ae40964_p13_0087": {
        "query": "시공상세도 제출 시 다른 공사와 협의 조정한 내용은 어떻게 포함해야 해",
        "file_anchor_query": "시공상세도 제출시기와 협의조정 내용이 함께 나오는 LH PDF를 찾아줘",
        "anchor": "시공상세도 제출시기 협의조정",
        "note": "제출시기 제목과 excerpt 문맥을 자연스럽게 연결했다.",
    },
    "supp_lh_7e8ae40964_p14_0088": {
        "query": "시공상세도면 승인 후에도 수급인 책임은 어떻게 남아 있어",
        "file_anchor_query": "시공상세도면 승인과 수급인 책임 감면 여부가 나오는 LH PDF를 찾아줘",
        "anchor": "시공상세도면 승인 수급인 책임",
        "note": "제품자료 문맥과 섞이지 않게 책임 조항을 핵심으로 삼았다.",
    },
    "supp_lh_a5094fc9ae_p5_0091": {
        "query": "전기공사 지급자재와 시공한계는 어떤 도면이나 시방을 따른다고 되어 있어",
        "file_anchor_query": "전기공사와 소방시설공사 지급자재 시공한계 설명이 있는 LH PDF를 찾아줘",
        "anchor": "전기공사 소방시설공사 지급자재 시공한계",
        "note": "reference code가 아니라 실제 조항 문장 검수 대상으로 만들었다.",
    },
    "supp_lh_a5094fc9ae_p7_0092": {
        "query": "공사용 자재가 변질품이나 손상품이면 어떤 확인 절차가 필요해",
        "file_anchor_query": "공사 자재 감독자 확인과 변질품 손상품 판정 문구가 있는 LH PDF를 찾아줘",
        "anchor": "공사 자재 감독자 확인 변질품 손상품",
        "note": "사진촬영 기준보다 excerpt의 자재 확인 조건을 기준으로 삼았다.",
    },
    "supp_lh_a5094fc9ae_p10_0093": {
        "query": "전기공사 준공 때 제출해야 하는 서류는 어떤 기준을 따라야 해",
        "file_anchor_query": "전기공사 준공 시 제출서류와 LHCS 10 10 35가 나오는 PDF를 찾아줘",
        "anchor": "전기공사 준공 제출서류 LHCS 10 10 35",
        "note": "기타 관련법이라는 section label보다 준공 제출서류를 query anchor로 했다.",
    },
    "supp_lh_a5094fc9ae_p16_0094": {
        "query": "전기공사 품질관리에서 조명기구와 세대분전반은 어떤 시공확인을 받아야 해",
        "file_anchor_query": "조명기구 배선기구 세대분전반 시공확인 내용이 있는 LH PDF를 찾아줘",
        "anchor": "조명기구 배선기구 세대분전반 시공확인",
        "note": "여러 품질관리 문장이 섞여 있어 extractive context 검수로 제한한다.",
    },
    "supp_lh_a5094fc9ae_p18_0095": {
        "query": "전기공사의 안전관리는 어떤 안전 보건 기준을 따른다고 되어 있어",
        "file_anchor_query": "전기공사 안전관리와 안전 보건관리 기준이 함께 나오는 LH PDF를 찾아줘",
        "anchor": "전기공사 안전관리 안전 보건관리",
        "note": "안전관리 section의 직접 문장을 query로 만들었다.",
    },
    "supp_lh_54d981d143_p1_0096": {
        "query": "LH 공사 안전 및 보건관리 기준의 일반사항 적용 범위는 뭐야",
        "file_anchor_query": "LH 공사 안전 및 보건관리 일반사항이 들어 있는 PDF를 찾아줘",
        "anchor": "LH 공사 안전 및 보건관리 일반사항",
        "note": "일반사항 row지만 안전 보건관리 문맥을 살렸다.",
    },
    "supp_lh_31623e878a_p1_0101": {
        "query": "LH 총칙에서 위임된 세부사항은 어떤 공사 기준으로 설명돼",
        "file_anchor_query": "총칙에서 위임된 세부사항을 설명하는 LH 공사 PDF를 찾아줘",
        "anchor": "총칙에서 위임된 세부사항",
        "note": "일반사항의 적용 범위를 확인하는 PDF content lookup이다.",
    },
    "supp_lh_31623e878a_p9_0103": {
        "query": "급수공사와 가스공사 인허가 업무는 어떤 기준을 따른다고 되어 있어",
        "file_anchor_query": "급수공사 가스공사 인허가 업무 기준이 나오는 LH PDF를 찾아줘",
        "anchor": "급수공사 가스공사 인허가 업무",
        "note": "페이지 제목이 깨져도 excerpt의 인허가 업무를 중심으로 했다.",
    },
    "supp_lh_31623e878a_p15_0104": {
        "query": "사용자재와 장비는 어떤 품질 조건을 충족해야 해",
        "file_anchor_query": "사용자재와 장비가 신품이고 품질이 양호해야 한다는 내용의 LH PDF를 찾아줘",
        "anchor": "사용자재 장비 신품 품질 양호",
        "note": "품질보증 section의 실질 문장을 자연어로 바꿨다.",
    },
    "supp_lh_31623e878a_p21_0105": {
        "query": "품질관리에 대한 사항은 어떤 LH 기준을 따른다고 되어 있어",
        "file_anchor_query": "품질관리에 대한 사항과 LHCS 10 10 15가 나오는 PDF를 찾아줘",
        "anchor": "품질관리 LHCS 10 10 15",
        "note": "reference-heavy row라 추출 근거 후보로만 남긴다.",
    },
    "supp_lh_1633f5fc74_p3_0107": {
        "query": "예비 준공검사는 어떤 요건에 따라 실시한다고 되어 있어",
        "file_anchor_query": "예비 준공검사와 약식기성검사 제출서류가 나오는 LH PDF를 찾아줘",
        "anchor": "예비 준공검사 약식기성검사 제출서류",
        "note": "제목과 본문이 엇갈려도 준공검사 중심으로 검수한다.",
    },
    "supp_lh_1633f5fc74_p4_0108": {
        "query": "준공대가 신청을 위한 검사를 받을 때 수급인은 어떤 조건을 만족해야 해",
        "file_anchor_query": "준공대가 신청 검사와 품질시험검사 성과 총괄표가 나오는 PDF를 찾아줘",
        "anchor": "준공대가 신청 검사 품질시험검사 성과 총괄표",
        "note": "준공 검사와 제출물 맥락을 사람이 확인하도록 했다.",
    },
    "supp_lh_1633f5fc74_p8_0109": {
        "query": "수량 검측에 필요한 장비와 근로자는 누가 준비해야 해",
        "file_anchor_query": "수량 검측 장비와 근로자 준비 기준이 나오는 LH PDF를 찾아줘",
        "anchor": "수량 검측 장비 근로자",
        "note": "부피 검측 row를 실제 질문 표면으로 바꿨다.",
    },
    "supp_lh_a4995bcd89_p1_0111": {
        "query": "LH 일반사항에서 관련 기준은 어떤 KCS 항목을 따른다고 되어 있어",
        "file_anchor_query": "KCS 10 10 05 관련 기준을 따르는 LH 일반사항 PDF를 찾아줘",
        "anchor": "관련 기준 KCS 10 10 05",
        "note": "reference code가 중심이지만 READY_EXTRACTIVE_CONTEXT 검수 row다.",
    },
    "supp_lh_a4995bcd89_p8_0113": {
        "query": "건설기술인이 경고장을 세 번 이상 받으면 어떤 기준으로 교체돼",
        "file_anchor_query": "건설기술인의 교체와 경고장 3차 이상 기준이 나오는 LH PDF를 찾아줘",
        "anchor": "건설기술인의 교체 경고장 3차 이상",
        "note": "section title이 좋은 natural query anchor다.",
    },
    "supp_lh_a4995bcd89_p13_0114": {
        "query": "확인측량 때 지구계 경계의 지적측량 결과는 어떻게 비교 검토해야 해",
        "file_anchor_query": "확인측량과 지구계 경계 지적측량 결과 비교검토 내용이 있는 LH PDF를 찾아줘",
        "anchor": "확인측량 지구계 경계 지적측량 비교검토",
        "note": "회의 착수 조건보다 excerpt의 확인측량 조항을 채택했다.",
    },
    "supp_lh_a4995bcd89_p14_0115": {
        "query": "공사현장 표지는 어떤 기준에 따라 제작하고 설치해야 해",
        "file_anchor_query": "공사현장 표지 제작 설치와 LHCS 21 20 05 05가 나오는 PDF를 찾아줘",
        "anchor": "공사현장 표지 제작 설치",
        "note": "section title과 본문이 명확한 extractive row다.",
    },
    "supp_lh_6acf57500f_p1_0121": {
        "query": "소방공사를 전기공사와 함께 도급받으면 관련법령에 없는 내용은 무엇을 따라야 해",
        "file_anchor_query": "소방공사를 전기공사와 함께 도급받은 경우 하도급관리 기준이 나오는 PDF를 찾아줘",
        "anchor": "소방공사 전기공사 함께 도급 건설공사 하도급관리",
        "note": "본문의 조건절을 그대로 자연어 질문으로 바꿨다.",
    },
    "supp_lh_6acf57500f_p12_0123": {
        "query": "공사대금지급 알림 서비스 운영에서 빠진 내용은 어떤 기준을 따라야 해",
        "file_anchor_query": "공사대금지급 알림 서비스와 건설공사 하도급관리가 함께 나오는 PDF를 찾아줘",
        "anchor": "공사대금지급 알림 서비스 건설공사 하도급관리",
        "note": "SMS 서비스 section을 하도급관리 참조 맥락으로 검수한다.",
    },
    "supp_elec_bc85e2bfb2_p1_0036": {
        "query": "2024년 1월 종합 전기요금표에서 주택용 저압 기본요금과 전력량요금 구간을 확인해줘",
        "file_anchor_query": "주택용 저압 기본요금 910원과 전력량요금 120.0원이 보이는 전기요금 PDF를 찾아줘",
        "anchor": "주택용 저압 기본요금 910 전력량요금 120.0",
        "note": "table candidate지만 table semantics 성공으로 승격하지 않는다.",
    },
    "supp_elec_bc85e2bfb2_p3_0038": {
        "query": "계절별 시간대별 구분에서 토요일과 공휴일 계산기준은 어떻게 안내돼",
        "file_anchor_query": "계절별 시간대별 구분과 토요일 공휴일 계산기준이 있는 PDF를 찾아줘",
        "anchor": "계절별 시간대별 구분 토요일 공휴일 계산기준",
        "note": "표 구조 검증이 아니라 추출 근거 후보 검수다.",
    },
    "supp_elec_0cc37a0bed_p1_0051": {
        "query": "2024년 4월 종합 전기요금표의 주택용 저압 기본요금 구간을 확인해줘",
        "file_anchor_query": "2024년 4월 주택용 저압 기본요금 910원 구간이 있는 PDF를 찾아줘",
        "anchor": "2024년 4월 주택용 저압 기본요금 910",
        "note": "1월 동일 표와 구분되도록 시행월을 넣었다.",
    },
    "supp_elec_0cc37a0bed_p3_0053": {
        "query": "2024년 4월 전기요금표에서 최대부하 시간대와 공휴일 계산기준을 확인해줘",
        "file_anchor_query": "최대부하 시간대와 공휴일 계산기준이 함께 나오는 2024년 4월 전기요금 PDF를 찾아줘",
        "anchor": "최대부하 시간대 공휴일 계산기준",
        "note": "표 행열 의미 성공이 아니라 context candidate로 둔다.",
    },
    "supp_elec_65556c2c63_p1_0071": {
        "query": "2023년 5월 종합 전기요금표에서 주택용 저압 요금 구간을 확인해줘",
        "file_anchor_query": "2023년 5월 시행 전기요금표에서 주택용 저압 기본요금 구간이 있는 PDF를 찾아줘",
        "anchor": "2023년 5월 주택용 저압 기본요금 구간",
        "note": "전기요금표 표 후보지만 추출 근거 후보로만 표시한다.",
    },
    "supp_elec_65556c2c63_p2_0072": {
        "query": "일반용전력 을과 산업용전력 을의 토요일 공휴일 계산기준을 확인해줘",
        "file_anchor_query": "일반용전력 을 산업용전력 을과 토요일 공휴일 계산기준이 있는 PDF를 찾아줘",
        "anchor": "일반용전력(을) 산업용전력(을) 토요일 공휴일 계산기준",
        "note": "계약전력 300킬로와트 이상 조건과 계산기준을 함께 검수한다.",
    },
    "supp_elec_d73432a97b_p1_0001": {
        "query": "2021년 주택용 저압에서 기타계절과 동계 슈퍼유저요금 조건을 확인해줘",
        "file_anchor_query": "기타계절 기간과 동계 슈퍼유저요금 704.5원 설명이 있는 PDF를 찾아줘",
        "anchor": "기타계절 동계 슈퍼유저요금 704.5원",
        "note": "restricted table context라 row-column-value 성공을 주장하지 않는다.",
    },
    "supp_elec_d73432a97b_p2_0002": {
        "query": "가구별 평균사용량으로 단계별 요금을 적용하는 방식은 어떻게 계산돼",
        "file_anchor_query": "가구별 평균사용량과 단계별 요금 단가 계산식이 있는 PDF를 찾아줘",
        "anchor": "가구별 평균사용량 단계별 요금 단가",
        "note": "계산식 근거 후보지만 공식 계산 성공은 아니다.",
    },
    "supp_elec_5db341e8bf_p1_0006": {
        "query": "2021년 종합 전기요금표에서 동계 슈퍼유저요금 704.5원 조건을 확인해줘",
        "file_anchor_query": "종합 전기요금표에서 동계 1000킬로와트시 초과 704.5원 설명이 있는 PDF를 찾아줘",
        "anchor": "동계 1,000kWh초과 704.5원",
        "note": "사용량별 요금표의 restricted context 후보로만 둔다.",
    },
    "supp_elec_8be2c46ed9_p1_0011": {
        "query": "연료비조정요금은 어떤 연료비 변동분을 반영한다고 설명돼",
        "file_anchor_query": "석탄 천연가스 유류 변동분을 반영하는 연료비조정요금 설명이 있는 PDF를 찾아줘",
        "anchor": "연료비조정요금 석탄 천연가스 유류",
        "note": "부과방식과 상하한 설명을 추출 근거 후보로 검수한다.",
    },
    "supp_elec_8be2c46ed9_p2_0012": {
        "query": "주택용 고압 사용량별 요금표에서 201킬로와트시 이후 구간 값들을 확인해줘",
        "file_anchor_query": "주택용 고압 사용량별 요금표에서 201 251 301 구간이 나오는 PDF를 찾아줘",
        "anchor": "주택용 고압 사용량별 요금표 201 251 301",
        "note": "숫자 표 후보라 table semantics 대신 extractive evidence로만 본다.",
    },
    "supp_elec_6bd1f748a3_p1_0016": {
        "query": "주택용 저압 전기요금 구조에서 연료비조정요금 부과방식은 어떻게 설명돼",
        "file_anchor_query": "주택용 저압 전기요금 구조에서 연료비조정단가 곱하기 사용전력량 설명이 있는 PDF를 찾아줘",
        "anchor": "연료비조정단가 사용전력량",
        "note": "연료비조정요금 설명 row를 고압과 분리했다.",
    },
    "supp_elec_c456f27e5d_p1_0021": {
        "query": "2023년 주택용 고압 전기요금에서 연료비조정요금 상하한은 어떻게 안내돼",
        "file_anchor_query": "2023년 주택용 고압 전기요금에서 연료비조정요금 상하한 ±5원 설명이 있는 PDF를 찾아줘",
        "anchor": "연료비조정요금 상하한 ±5원",
        "note": "기후환경이 아니라 excerpt의 연료비조정요금을 기준으로 수정했다.",
    },
    "supp_elec_c456f27e5d_p1_0025": {
        "query": "주택용 고압 청구금액에서 부가가치세와 전력산업기반기금은 어떻게 계산돼",
        "file_anchor_query": "부가가치세 10퍼센트와 전력산업기반기금 3.7퍼센트 계산식이 있는 PDF를 찾아줘",
        "anchor": "부가가치세 10% 전력산업기반기금 3.7%",
        "note": "계산식은 expected evidence 후보이며 계산 성공 주장은 하지 않는다.",
    },
    "supp_elec_c456f27e5d_p2_0022": {
        "query": "주택용 고압 사용량별 요금표에서 201킬로와트시부터 이어지는 금액 구간을 확인해줘",
        "file_anchor_query": "주택용 고압 사용량별 요금표 계속 페이지의 201 251 301 구간이 있는 PDF를 찾아줘",
        "anchor": "주택용 고압 사용량별 요금표 계속 201 251 301",
        "note": "숫자 dense table을 restricted evidence로만 검수한다.",
    },
    "supp_elec_5632eb03a2_p1_0026": {
        "query": "2023년 주택용 저압 전기요금에서 연료비조정요금 부과방식은 어떻게 되어 있어",
        "file_anchor_query": "2023년 주택용 저압에서 연료비조정단가와 사용전력량 설명이 있는 PDF를 찾아줘",
        "anchor": "주택용 저압 연료비조정단가 사용전력량",
        "note": "전압 구분과 시행 시기를 포함해 중복을 줄였다.",
    },
    "supp_elec_5632eb03a2_p1_0030": {
        "query": "주택용 저압 청구금액은 전기요금 외에 어떤 항목을 더해서 계산해",
        "file_anchor_query": "청구금액이 전기요금 부가가치세 전력산업기반기금 합으로 설명된 PDF를 찾아줘",
        "anchor": "청구금액 전기요금 부가가치세 전력산업기반기금",
        "note": "계산 공식 row를 자연어 검수 query로 바꿨다.",
    },
    "supp_elec_5632eb03a2_p2_0027": {
        "query": "주택용 저압 사용량별 요금표는 계절이 바뀔 때 어떻게 계산된다고 안내돼",
        "file_anchor_query": "계절 변동일 기준 일수계산과 주택용 저압 사용량별 요금표가 함께 있는 PDF를 찾아줘",
        "anchor": "계절 변동일 기준 일수계산 주택용 저압 사용량별 요금표",
        "note": "표 제목과 주석을 함께 검수하는 restricted context row다.",
    },
    "supp_elec_625588fd70_p1_0031": {
        "query": "2024년 10월 전기요금표에서 동계 슈퍼유저요금 736.2원 조건을 확인해줘",
        "file_anchor_query": "2024년 10월 전기요금표에서 동계 슈퍼유저요금 736.2원 설명이 있는 PDF를 찾아줘",
        "anchor": "2024년 10월 동계 슈퍼유저요금 736.2원",
        "note": "OCR 붙어쓰기 row라 사람이 확인할 자연 query로 정리했다.",
    },
    "supp_elec_625588fd70_p2_0032": {
        "query": "산업용전력 을 표에서 전기자동차 충전전력 요금 항목이 어디에 이어져",
        "file_anchor_query": "산업용전력 을과 전기자동차 충전전력 요금이 함께 나오는 PDF를 찾아줘",
        "anchor": "산업용전력(을) 전기자동차충전전력요금",
        "note": "표 일부라 row-column-value 성공 없이 위치성 evidence로 둔다.",
    },
    "supp_elec_bc85e2bfb2_p2_0037": {
        "query": "일반용전력 을 표에서 고압 A의 경부하 중간부하 최대부하 단가를 확인해줘",
        "file_anchor_query": "일반용전력 을 고압 A 경부하 중간부하 최대부하 단가가 있는 PDF를 찾아줘",
        "anchor": "일반용전력(을) 고압 A 경부하 중간부하 최대부하",
        "note": "dense table evidence 후보지만 행열 의미 성공은 claim하지 않는다.",
    },
    "supp_elec_625588fd70_p3_0033": {
        "query": "계절 시간대 표에서 봄가을철 시간대만으로는 답을 만들 수 있는지 확인해줘",
        "file_anchor_query": "봄가을철 3월에서 5월 9월에서 10월 시간대 표가 있는 PDF를 찾아줘",
        "anchor": "봄가을철 3~5월 9~10월",
        "note": "table-like이나 row-column-value가 부족한 abstain control이다.",
    },
    "supp_elec_845dd6d1b2_p3_0058": {
        "query": "2024년 7월 전기요금표의 계절 시간대 표는 답변 근거로 충분한지 검수해줘",
        "file_anchor_query": "2024년 7월 전기요금표에서 봄가을철 시간대 구분이 있는 PDF를 찾아줘",
        "anchor": "2024년 7월 봄가을철 시간대 구분",
        "note": "검수 control로 두고 official candidate로 승격하지 않는다.",
    },
    "supp_elec_ffe06a10cb_p3_0063": {
        "query": "일반용보완전력요금 표 조각만으로 부족전력요금 설명을 답할 수 있는지 확인해줘",
        "file_anchor_query": "일반용보완전력요금과 분산에너지사업자 부족전력요금이 보이는 PDF를 찾아줘",
        "anchor": "일반용보완전력요금 분산에너지사업자 부족전력요금",
        "note": "표 조각 control로 유지한다.",
    },
    "supp_elec_d73432a97b_p1_0003": {
        "query": "2021년 1월 기준 기후환경요금 단가만으로 답변 근거가 충분한지 확인해줘",
        "file_anchor_query": "기후환경요금 단가 5.3원이 적힌 2021년 주택용 저압 PDF를 찾아줘",
        "anchor": "기후환경요금 단가 5.3원",
        "note": "keyword-only control이라 제외 사유 확인용이다.",
    },
    "supp_elec_5db341e8bf_p1_0008": {
        "query": "종합 전기요금표의 기후환경요금 단가 5.3원 문구만으로 충분한지 검수해줘",
        "file_anchor_query": "기후환경요금 단가 5.3원이 있는 종합 전기요금 PDF를 찾아줘",
        "anchor": "종합 전기요금 기후환경요금 5.3원",
        "note": "짧은 단가 문구라 keyword-only abstain control로 둔다.",
    },
    "supp_elec_6bd1f748a3_p2_0017": {
        "query": "주택용 저압 사용량별 요금표 제목만으로는 답변 근거가 충분한지 확인해줘",
        "file_anchor_query": "주택용 저압 사용량별 요금표와 1주택수가구 사용량별 요금표가 있는 PDF를 찾아줘",
        "anchor": "주택용전력 저압 사용량별 요금표 1주택수가구",
        "note": "표 제목 중심이라 keyword-only abstain control로 남겼다.",
    },
    "supp_lh_7e8ae40964_p1_0090": {
        "query": "용어의 정의가 KCS 기준을 따른다는 문구만으로 충분한지 확인해줘",
        "file_anchor_query": "용어의 정의와 KCS 10 10 10 참조 문구가 있는 LH PDF를 찾아줘",
        "anchor": "용어의 정의 KCS 10 10 10",
        "note": "reference code false-positive control이다.",
    },
    "supp_lh_7e8ae40964_p19_0089": {
        "query": "건강친화형 주택 자체평가 이행확인서 조항이 단순 참조인지 확인해줘",
        "file_anchor_query": "건강친화형 주택 자체평가 이행확인서와 LHCS 참조가 있는 PDF를 찾아줘",
        "anchor": "건강친화형 주택 자체평가 이행확인서",
        "note": "짧은 참조 조항이라 false-positive control로 둔다.",
    },
    "supp_lh_31623e878a_p3_0102": {
        "query": "지하주차장 옥내소화전 관련 조항이 다른 기준을 따른다는 참조문인지 확인해줘",
        "file_anchor_query": "지하주차장 옥내소화전과 LHCS 10 10 10 05 참조가 나오는 PDF를 찾아줘",
        "anchor": "지하주차장 옥내소화전 LHCS 10 10 10 05",
        "note": "reference code만으로 답을 만들지 않는 control이다.",
    },
    "supp_lh_1633f5fc74_p2_0106": {
        "query": "하자검사 정의 근처의 제출 기준이 단순 참조인지 확인해줘",
        "file_anchor_query": "하자검사 정의와 LHCS 10 10 10 05 제출 참조가 함께 있는 PDF를 찾아줘",
        "anchor": "하자검사 LHCS 10 10 10 05",
        "note": "하자검사 문맥과 제출 참조가 섞인 false-positive control이다.",
    },
    "supp_lh_1633f5fc74_p14_0110": {
        "query": "관련 법규 조항에서 다음 사항은 다른 기준에 따른다는 문구만 있는지 확인해줘",
        "file_anchor_query": "관련 법규와 LHCS 10 10 10 05 제출 참조가 있는 PDF를 찾아줘",
        "anchor": "관련 법규 LHCS 10 10 10 05",
        "note": "내용 답변이 아니라 reference-code 제외 사유 확인용이다.",
    },
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_pack(
        source_csv=Path(args.source_csv),
        output_dir=Path(args.output_dir),
        report_dir=Path(args.report_dir),
        output_prefix=args.output_prefix,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", default=str(DEFAULT_SOURCE_CSV))
    parser.add_argument("--output-dir", default=str(REVIEW_DIR))
    parser.add_argument("--report-dir", default=str(REPORT_DIR))
    parser.add_argument("--output-prefix", default=DEFAULT_OUTPUT_PREFIX)
    return parser.parse_args(argv)


def build_pack(*, source_csv: Path, output_dir: Path, report_dir: Path, output_prefix: str) -> dict[str, Any]:
    source_rows = read_csv(source_csv)
    validate_source(source_rows)
    before_hashes = snapshot_files(REFERENCE_FILES)

    output_rows: list[dict[str, str]] = []
    for row in source_rows:
        output_rows.append(make_content_row(row))
        output_rows.append(make_file_metadata_row(row))
        output_rows.append(make_file_anchor_row(row))

    validate_output(output_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{output_prefix}.csv"
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    md_path = output_dir / f"{output_prefix}.md"
    summary_path = report_dir / SUMMARY_NAME
    for path in [csv_path, jsonl_path, md_path, summary_path]:
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")

    summary = build_summary(output_rows, source_csv, csv_path, jsonl_path, md_path, summary_path, before_hashes)
    write_csv(csv_path, output_rows)
    write_jsonl(jsonl_path, output_rows)
    write_markdown(md_path, summary)
    write_json(summary_path, summary)

    after_hashes = snapshot_files(REFERENCE_FILES)
    if before_hashes != after_hashes:
        raise RuntimeError("Source/reference files changed during generation")

    return {
        "status": "PASS",
        "row_count": len(output_rows),
        "content_row_count": count_type(output_rows, "PDF_SUPPLEMENTAL_CONTENT_LOOKUP_MANUAL_CURATED"),
        "file_metadata_row_count": count_type(output_rows, "PDF_FILE_LOOKUP_BY_METADATA"),
        "file_anchor_row_count": count_type(output_rows, "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR"),
        "unique_query_count": len({row["query"] for row in output_rows}),
        "review_lane_counts": dict(Counter(row["review_lane"] for row in output_rows)),
        "csv": rel(csv_path),
        "jsonl": rel(jsonl_path),
        "markdown": rel(md_path),
        "summary": rel(summary_path),
        "promotion_evidence": False,
        "official_denominator_changed": False,
    }


def make_content_row(row: dict[str, str]) -> dict[str, str]:
    manual = MANUAL_CURATIONS[row["query_id"]]
    out = base_v3_row(row)
    out.update(
        {
            "query_id": row["query_id"],
            "parent_query_id": row["query_id"],
            "query_surface_type": "PDF_SUPPLEMENTAL_CONTENT_LOOKUP_MANUAL_CURATED",
            "query": manual["query"],
            "original_query": row["query"],
            "manual_content_anchor": manual["anchor"],
            "manual_curation_note": manual["note"],
            "manual_goldset_role": "pdf_content_review_candidate",
            "expected_file_name": row["source_file_name"],
            "expected_document_identity": document_identity(row),
            "recommended_lookup_lane": "PDF_CONTENT_LOOKUP",
            "recommended_review_action": review_action(row["review_lane"]),
            "recommended_expected_evidence_scope": content_evidence_scope(row["review_lane"]),
            "recommended_file_lookup_policy": "not_file_lookup_row",
        }
    )
    return out


def make_file_metadata_row(row: dict[str, str]) -> dict[str, str]:
    manual = MANUAL_CURATIONS[row["query_id"]]
    out = base_v3_row(row)
    out.update(
        {
            "query_id": f"{row['query_id']}__file_meta_v3",
            "parent_query_id": row["query_id"],
            "query_surface_type": "PDF_FILE_LOOKUP_BY_METADATA",
            "query": metadata_query(row, manual),
            "original_query": row["query"],
            "page_no": "",
            "page_label": "",
            "section_path": "",
            "expected_evidence_excerpt": f"expected_file_name={row['source_file_name']}; document_identity={document_identity(row)}",
            "evidence_object_summary": "",
            "deterministic_draft": "",
            "review_lane": "PDF_FILE_LOOKUP_BY_METADATA",
            "manual_content_anchor": "",
            "manual_curation_note": "파일명과 문서 식별 metadata만 검수하며 page, bbox, table semantics를 요구하지 않는다.",
            "manual_goldset_role": "pdf_file_identity_companion",
            "expected_file_name": row["source_file_name"],
            "expected_document_identity": document_identity(row),
            "recommended_lookup_lane": "PDF_FILE_LOOKUP_BY_METADATA",
            "recommended_review_action": "review_file_identity_only_not_content_gold",
            "recommended_expected_evidence_scope": "expected_file_name_or_document_identity_only",
            "recommended_file_lookup_policy": "metadata_lookup_no_page_bbox_or_table_semantics",
            "suggested_gold_decision": "review_companion_only",
            "suggested_answerability_label": "file_lookup_metadata_only",
            "suggested_relevance_label": "document_identity_relevance_only",
            "suggested_expected_evidence_policy": "expected_file_name_or_document_identity_only",
            "suggested_denominator_policy": "not_official_denominator_file_lookup_companion",
            "risk_tags": append_tag(row.get("risk_tags", ""), "file_lookup_no_content_semantics"),
            "diagnostic_reason": "manual v3 PDF file metadata companion row; no page/bbox/table semantics required",
        }
    )
    return out


def make_file_anchor_row(row: dict[str, str]) -> dict[str, str]:
    manual = MANUAL_CURATIONS[row["query_id"]]
    out = base_v3_row(row)
    out.update(
        {
            "query_id": f"{row['query_id']}__file_anchor_v3",
            "parent_query_id": row["query_id"],
            "query_surface_type": "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR",
            "query": manual["file_anchor_query"],
            "original_query": row["query"],
            "page_no": "",
            "page_label": "",
            "section_path": "",
            "expected_evidence_excerpt": f"expected_file_name={row['source_file_name']}; content_anchor={manual['anchor']}; document_identity={document_identity(row)}",
            "evidence_object_summary": "",
            "deterministic_draft": "",
            "review_lane": "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR",
            "manual_content_anchor": manual["anchor"],
            "manual_curation_note": "수동 content anchor로 PDF 파일 식별 가능성만 검수하며 page, bbox, table semantics를 요구하지 않는다.",
            "manual_goldset_role": "pdf_file_anchor_companion",
            "expected_file_name": row["source_file_name"],
            "expected_document_identity": document_identity(row),
            "recommended_lookup_lane": "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR",
            "recommended_review_action": "review_file_identity_by_content_anchor_only",
            "recommended_expected_evidence_scope": "expected_file_name_or_document_identity_only",
            "recommended_file_lookup_policy": "content_anchor_file_lookup_no_page_bbox_or_table_semantics",
            "suggested_gold_decision": "review_companion_only",
            "suggested_answerability_label": "file_lookup_content_anchor_only",
            "suggested_relevance_label": "document_identity_relevance_only",
            "suggested_expected_evidence_policy": "expected_file_name_or_document_identity_only",
            "suggested_denominator_policy": "not_official_denominator_file_lookup_companion",
            "risk_tags": append_tag(row.get("risk_tags", ""), "file_lookup_no_content_semantics"),
            "diagnostic_reason": "manual v3 PDF file lookup by content anchor companion row; no page/bbox/table semantics required",
        }
    )
    return out


def base_v3_row(row: dict[str, str]) -> dict[str, str]:
    out = {
        "track": row["track"],
        "query_id": "",
        "parent_query_id": "",
        "query_surface_type": "",
        "dataset": row["dataset"],
        "source_file_name": row["source_file_name"],
        "expected_file_name": row["source_file_name"],
        "expected_document_identity": document_identity(row),
        "page_no": row["page_no"],
        "page_label": row["page_label"],
        "section_path": row["section_path"],
        "query": "",
        "original_query": row["query"],
        "manual_content_anchor": "",
        "manual_curation_style_reference": "namuwiki_v4_manual_curated_queries_and_pdf_xlsx_review_pack_shape",
        "manual_curation_basis": "codex_manual_row_by_row_pdf_review_curation_from_existing_diagnostic_evidence",
        "manual_curation_note": "",
        "manual_goldset_role": "",
        "expected_evidence_excerpt": row["expected_evidence_excerpt"],
        "evidence_object_summary": row["evidence_object_summary"],
        "deterministic_draft": row["deterministic_draft"],
        "review_lane": row["review_lane"],
        "recommended_lookup_lane": "",
        "recommended_review_action": "",
        "recommended_expected_evidence_scope": "",
        "recommended_file_lookup_policy": "",
        "suggested_gold_decision": row["suggested_gold_decision"],
        "suggested_answerability_label": row["suggested_answerability_label"],
        "suggested_relevance_label": row["suggested_relevance_label"],
        "suggested_expected_evidence_policy": row["suggested_expected_evidence_policy"],
        "suggested_denominator_policy": row["suggested_denominator_policy"],
        "risk_tags": row["risk_tags"],
        "diagnostic_reason": row["diagnostic_reason"],
    }
    for column in USER_COLUMNS:
        out[column] = ""
    out.update(GUARDRAIL_COLUMNS)
    return out


def review_action(lane: str) -> str:
    if lane.startswith("READY_"):
        return "human_review_candidate_not_official_gold"
    if lane == "HIGH_CONFIDENCE_TABLE_CANDIDATE":
        return "review_as_extractive_table_context_candidate_not_table_semantics"
    if lane.startswith("ABSTAIN_"):
        return "review_control_exclusion_reason_only"
    if lane.startswith("FALSE_POSITIVE_"):
        return "review_false_positive_exclusion_reason_only"
    return "review_diagnostic_only"


def content_evidence_scope(lane: str) -> str:
    if lane == "HIGH_CONFIDENCE_TABLE_CANDIDATE":
        return "extractive_pdf_excerpt_only_no_table_semantics_success"
    if lane == "READY_RESTRICTED_TABLE_CONTEXT":
        return "restricted_pdf_table_like_context_no_row_column_value_semantics"
    if lane.startswith("READY_"):
        return "pdf_page_section_excerpt_for_human_review"
    if lane.startswith("ABSTAIN_"):
        return "diagnostic_control_no_gold_evidence_claim"
    if lane.startswith("FALSE_POSITIVE_"):
        return "false_positive_control_reference_only"
    return "diagnostic_only"


def document_identity(row: dict[str, str]) -> str:
    bits = [row["dataset"], row["source_file_name"]]
    if row.get("section_path"):
        bits.append(row["section_path"])
    return " / ".join(bits)


def metadata_query(row: dict[str, str], manual: dict[str, str]) -> str:
    dataset_label = "전기요금 보조자료" if row["dataset"] == "elec" else "LH 시방서 보조자료"
    section = " ".join(row.get("section_path", "").split())
    if len(section) > 44:
        section = section[:44].rstrip() + " 부분"
    if not section:
        section = "해당 항목"
    return f"문서 목록에서 {dataset_label} 중 {section}와 {manual['anchor']} 검수 항목이 같은 자료로 묶이는지 확인해줘"


def append_tag(existing: str, tag: str) -> str:
    parts = [part.strip() for part in existing.split(";") if part.strip()]
    if tag not in parts:
        parts.append(tag)
    return ";".join(parts)


def build_summary(
    rows: list[dict[str, str]],
    source_csv: Path,
    csv_path: Path,
    jsonl_path: Path,
    md_path: Path,
    summary_path: Path,
    before_hashes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "rag_pdf_supplemental_gold_review_pack_v3_manual_curated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "manual_curation_by": "codex",
        "template_generation_used_for_content_queries": False,
        "source_csv": rel(source_csv),
        "reference_files": [rel(path) for path in REFERENCE_FILES],
        "outputs": {
            "csv": rel(csv_path),
            "jsonl": rel(jsonl_path),
            "markdown": rel(md_path),
            "summary": rel(summary_path),
        },
        "row_count": len(rows),
        "content_row_count": count_type(rows, "PDF_SUPPLEMENTAL_CONTENT_LOOKUP_MANUAL_CURATED"),
        "file_metadata_row_count": count_type(rows, "PDF_FILE_LOOKUP_BY_METADATA"),
        "file_anchor_row_count": count_type(rows, "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR"),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "unique_query_count": len({row["query"] for row in rows}),
        "user_decision_required_count": len(rows),
        "user_columns_blank": True,
        "review_lane_counts": dict(Counter(row["review_lane"] for row in rows)),
        "query_surface_type_counts": dict(Counter(row["query_surface_type"] for row in rows)),
        "manual_goldset_role_counts": dict(Counter(row["manual_goldset_role"] for row in rows)),
        "official_pdf_gold_created": False,
        "existing_gold_csv_overwritten": False,
        "official_denominator_changed": False,
        "promotion_evidence": False,
        "codex_gold_policy_decision_applied": False,
        "pdf_c7_policy_decision_applied": False,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
        "bbox_contract_success_not_claimed": True,
        "live_llm_run": False,
        "optional_judge_run": False,
        "retrieval_tuning_applied": False,
        "reranking_applied": False,
        "parser_expansion_applied": False,
        "db_searchunit_index_candidate_baseline_changed": False,
        "source_reference_hashes_before": before_hashes,
    }


def validate_source(rows: list[dict[str, str]]) -> None:
    if len(rows) != 80:
        raise ValueError(f"Expected 80 PDF source rows, got {len(rows)}")
    ids = [row["query_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source query_id")
    missing = sorted(set(ids) ^ set(MANUAL_CURATIONS))
    if missing:
        raise ValueError(f"Manual curation map mismatch: {missing}")


def validate_output(rows: list[dict[str, str]]) -> None:
    if len(rows) != 240:
        raise ValueError(f"Expected 240 rows, got {len(rows)}")
    ids = [row["query_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate output query_id")
    if len({row["query"] for row in rows}) != len(rows):
        duplicates = [q for q, count in Counter(row["query"] for row in rows).items() if count > 1]
        raise ValueError(f"Duplicate output query text: {duplicates[:5]}")
    for row in rows:
        for col in USER_COLUMNS:
            if row[col] != "":
                raise ValueError(f"{row['query_id']} has non-blank {col}")
        for key, expected in GUARDRAIL_COLUMNS.items():
            if row[key] != expected:
                raise ValueError(f"{row['query_id']} guardrail {key}={row[key]!r}, expected {expected!r}")
        if row["query_surface_type"].startswith("PDF_FILE_LOOKUP"):
            if row["page_no"] or row["page_label"] or row["section_path"]:
                raise ValueError(f"{row['query_id']} file lookup row must not require page/section")


def count_type(rows: list[dict[str, str]], query_surface_type: str) -> int:
    return sum(1 for row in rows if row["query_surface_type"] == query_surface_type)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lane_lines = "\n".join(
        f"- `{lane}`: `{count}`" for lane, count in sorted(summary["review_lane_counts"].items())
    )
    surface_lines = "\n".join(
        f"- `{kind}`: `{count}`" for kind, count in sorted(summary["query_surface_type_counts"].items())
    )
    text = f"""# PDF Supplemental Gold Review Pack v3 Manual Curated Draft

Generated at: {summary["generated_at"]}

This is a diagnostic-only PDF goldset review draft. It does not create official
gold rows, denominator evidence, promotion evidence, PDF C7 policy decisions,
table semantics success, row-column-value semantics success, or bbox success.

## What This Draft Contains

- `80` manually curated PDF content lookup rows.
- `80` PDF file lookup companion rows by metadata.
- `80` PDF file lookup companion rows by content anchor.
- The original v1 query is preserved in `original_query`.
- User decision columns remain blank.

## Human Decisions Still Required

- Whether any content row should be included in a future PDF gold candidate.
- Answerability, relevance, expected evidence policy, and denominator policy.
- Whether table-like contexts are acceptable as extractive evidence only.
- Whether abstain and false-positive controls should remain excluded.

## Review Lane Counts

{lane_lines}

## Query Surface Counts

{surface_lines}

## Guardrails

- `promotion_evidence=false`
- `official_denominator_changed=false`
- `codex_gold_policy_decision_applied=false`
- `pdf_c7_policy_decision_applied=false`
- `table_semantics_success_claimed=false`
- `row_column_value_semantics_claimed=false`
- `bbox_contract_success_not_claimed=true`
- `live_llm_run=false`
- `optional_judge_run=false`
- `db_searchunit_index_candidate_baseline_changed=false`
"""
    path.write_text(text, encoding="utf-8")


def snapshot_files(paths: list[Path]) -> list[dict[str, Any]]:
    return [snapshot_file(path) for path in paths]


def snapshot_file(path: Path) -> dict[str, Any]:
    exists = path.exists()
    data = path.read_bytes() if exists else b""
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
