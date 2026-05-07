"""Build a PDF gold review pack in the same CSV shape as TEXT/XLSX packs.

The queries in MANUAL_QUERY_REVIEWS were written manually by Codex after
reviewing the user-provided TEXT and XLSX gold review packs. The script may
populate locator/review columns, but it must not generate query text.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
DEFAULT_SOURCE_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "pdf_supplemental_gold_review"
    / "pdf_supplemental_gold_review_pack.csv"
)
DEFAULT_EVIDENCE_JSONL = (
    AI_WORKER_ROOT
    / "eval"
    / "artifacts"
    / "eval_runs"
    / "pdf_supplemental_elec_lh_20260506T_supplemental_diag"
    / "answer_evidence_objects.jsonl"
)
DEFAULT_OUTPUT_DIR = AI_WORKER_ROOT / "eval" / "review" / "pdf_supplemental_gold_review"
DEFAULT_REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
DEFAULT_PREFIX = "pdf_gold_review_pack_manual_v1"
SUMMARY_NAME = "rag_pdf_gold_review_pack_manual_v1_summary.json"

TEXT_REVIEW_REFERENCE = Path(r"D:/다운/text_gold_review_pack - text_gold_review_pack.csv")
XLSX_REVIEW_REFERENCE = Path(r"D:/다운/xlsx_gold_review_pack - xlsx_gold_review_pack.csv")

PACK_COLUMNS = [
    "track",
    "query_id",
    "review_group",
    "bucket",
    "query",
    "expected_answer_text",
    "must_contain_terms",
    "expected_document_version_id",
    "expected_file_name",
    "expected_page_no",
    "expected_physical_page_index",
    "expected_page_label",
    "expected_section_id",
    "expected_chunk_id",
    "expected_sheet_name",
    "expected_cell_range",
    "expected_table_id",
    "expected_bbox",
    "suggested_gold_decision",
    "suggested_answerability_label",
    "suggested_relevance_label",
    "suggested_expected_evidence_policy",
    "suggested_denominator_policy",
    "suggested_issue_tags",
    "suggested_notes",
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]

USER_COLUMNS = [col for col in PACK_COLUMNS if col.startswith("user_")]


MANUAL_QUERY_REVIEWS: dict[str, dict[str, str]] = {
    "supp_elec_d73432a97b_p1_0005": {
        "query": "계절 바뀌면 주택용 저압 요금 계산 어떻게 하더라",
        "must_contain_terms": "계절변동일;일수계산;주택용전력(저압)",
        "query_style": "underspecified",
    },
    "supp_elec_d73432a97b_p2_0004": {
        "query": "한전 상담 채널 모아둔 부분 찾아줘",
        "must_contain_terms": "사이버지점;스마트 한전;전기상담",
        "query_style": "location_lookup",
    },
    "supp_elec_5db341e8bf_p1_0010": {
        "query": "계약전력 300kW 미만 조건 나오는 전기요금 쪽",
        "must_contain_terms": "계약전력 300kW미만",
        "query_style": "underspecified",
    },
    "supp_elec_5db341e8bf_p2_0009": {
        "query": "전기요금 종합 안내의 상담 링크들 찾아줘",
        "must_contain_terms": "사이버지점;스마트 한전;트위터;페이스북",
        "query_style": "location_lookup",
    },
    "supp_elec_8be2c46ed9_p1_0013": {
        "query": "기후환경요금 7.3원 근거 알려줘",
        "must_contain_terms": "기후환경요금단가;7.3원",
        "query_style": "fact_lookup",
    },
    "supp_elec_8be2c46ed9_p1_0014": {
        "query": "스마트 한전 앱 안내 어디야",
        "must_contain_terms": "스마트 한전;아이폰;안드로이드폰",
        "query_style": "short_location_lookup",
    },
    "supp_elec_8be2c46ed9_p1_0015": {
        "query": "123 전화상담 시간",
        "must_contain_terms": "국번없이 123;365일;24시간",
        "query_style": "underspecified",
    },
    "supp_elec_6bd1f748a3_p1_0018": {
        "query": "저압 기후환경 7.3원",
        "must_contain_terms": "주택용 저압;기후환경요금;7.3원",
        "query_style": "keywordish",
    },
    "supp_elec_6bd1f748a3_p1_0019": {
        "query": "저압 요금표에 한전 온라인 상담 안내도 있어",
        "must_contain_terms": "주택용 저압;사이버지점;스마트 한전",
        "query_style": "fact_location_hybrid",
    },
    "supp_elec_6bd1f748a3_p1_0020": {
        "query": "국번없이 123 안내문 찾아줘",
        "must_contain_terms": "국번없이 123;전화상담",
        "query_style": "location_lookup",
    },
    "supp_elec_c456f27e5d_p1_0023": {
        "query": "고압 기후환경요금 9원 부분",
        "must_contain_terms": "주택용 고압;기후환경요금;9원",
        "query_style": "underspecified",
    },
    "supp_elec_c456f27e5d_p1_0024": {
        "query": "2023년 주택용 고압 상담 123",
        "must_contain_terms": "2023년;주택용 고압;전기상담;123",
        "query_style": "keywordish",
    },
    "supp_elec_5632eb03a2_p1_0028": {
        "query": "저압 기후환경 9원 근거",
        "must_contain_terms": "주택용 저압;기후환경요금;9원",
        "query_style": "keywordish",
    },
    "supp_elec_5632eb03a2_p1_0029": {
        "query": "24시간 전기상담 문구",
        "must_contain_terms": "365일;24시간;전기상담",
        "query_style": "short_fact_lookup",
    },
    "supp_elec_625588fd70_p1_0034": {
        "query": "주택용 저압 기타계절 항목",
        "must_contain_terms": "주택용전력(저압);기타계절",
        "query_style": "keywordish",
    },
    "supp_elec_625588fd70_p1_0035": {
        "query": "1000kW 미만 조건 어디 나와",
        "must_contain_terms": "계약전력;1,000kW미만",
        "query_style": "underspecified",
    },
    "supp_elec_bc85e2bfb2_p1_0039": {
        "query": "하계 슈퍼유저 736.2원 적용 조건",
        "must_contain_terms": "하계;슈퍼유저요금;736.2원",
        "query_style": "fact_lookup",
    },
    "supp_elec_bc85e2bfb2_p1_0040": {
        "query": "산업용전력 갑 1 계약전력 기준",
        "must_contain_terms": "산업용전력(갑)Ⅰ;계약전력 300kW미만",
        "query_style": "keywordish",
    },
    "supp_elec_8659b3db62_p1_0043": {
        "query": "고압 동계 601.3원",
        "must_contain_terms": "주택용 고압;동계;601.3원",
        "query_style": "underspecified",
    },
    "supp_elec_8659b3db62_p1_0044": {
        "query": "고압 요금표 상담 안내",
        "must_contain_terms": "주택용 고압;전기상담;123",
        "query_style": "location_lookup",
    },
    "supp_elec_493679be9f_p1_0048": {
        "query": "저압 동계 슈퍼유저 단가 736.2원",
        "must_contain_terms": "주택용 저압;동계;736.2원",
        "query_style": "fact_lookup",
    },
    "supp_elec_493679be9f_p1_0049": {
        "query": "저압 한전 상담 채널",
        "must_contain_terms": "주택용 저압;한전;상담 채널",
        "query_style": "keywordish",
    },
    "supp_elec_0cc37a0bed_p1_0054": {
        "query": "2024년 4월 하계 736.2원",
        "must_contain_terms": "2024년 4월;하계;736.2원",
        "query_style": "keywordish",
    },
    "supp_elec_0cc37a0bed_p1_0055": {
        "query": "산업용전력 갑 조건",
        "must_contain_terms": "산업용전력(갑)Ⅰ;계약전력",
        "query_style": "underspecified",
    },
    "supp_lh_67760ba504_p1_0148": {
        "query": "LH 일반사항 적용 대상",
        "must_contain_terms": "LH;발주;건설공사;전문시방서",
        "query_style": "keywordish",
    },
    "supp_lh_67760ba504_p4_0150": {
        "query": "건설사업관리 정의 뭐였지",
        "must_contain_terms": "건설사업관리;건설산업기본법 제2조",
        "query_style": "underspecified",
    },
    "supp_lh_7e8ae40964_p6_0086": {
        "query": "사급자재 LHCS 10 10 20 05",
        "must_contain_terms": "사급자재;LHCS 10 10 20 05",
        "query_style": "reference_lookup",
    },
    "supp_lh_7e8ae40964_p13_0087": {
        "query": "시공상세도 제출할 때 협의조정 내용 포함해야 해",
        "must_contain_terms": "시공상세도;협의조정;제출시기",
        "query_style": "policy_question",
    },
    "supp_lh_7e8ae40964_p14_0088": {
        "query": "시공상세도 승인 받아도 책임 남아",
        "must_contain_terms": "시공상세도면;승인;수급인 책임",
        "query_style": "natural_question",
    },
    "supp_lh_a5094fc9ae_p5_0091": {
        "query": "전기공사 지급자재 시공한계 기준",
        "must_contain_terms": "전기공사;지급자재;시공한계",
        "query_style": "keywordish",
    },
    "supp_lh_a5094fc9ae_p7_0092": {
        "query": "변질품 손상품 자재 기준",
        "must_contain_terms": "자재;감독자 확인;변질품;손상품",
        "query_style": "keywordish",
    },
    "supp_lh_a5094fc9ae_p10_0093": {
        "query": "전기공사 준공 서류 뭐 내야 해",
        "must_contain_terms": "전기공사;준공;제출서류;LHCS 10 10 35",
        "query_style": "natural_question",
    },
    "supp_lh_a5094fc9ae_p16_0094": {
        "query": "조명기구 세대분전반 시공확인",
        "must_contain_terms": "조명기구;세대분전반;시공확인",
        "query_style": "keywordish",
    },
    "supp_lh_a5094fc9ae_p18_0095": {
        "query": "전기공사 안전관리 기준",
        "must_contain_terms": "전기공사;안전관리;안전ㆍ보건관리",
        "query_style": "fact_lookup",
    },
    "supp_lh_54d981d143_p1_0096": {
        "query": "안전 보건관리 일반사항",
        "must_contain_terms": "안전;보건관리;일반사항",
        "query_style": "keywordish",
    },
    "supp_lh_31623e878a_p1_0101": {
        "query": "총칙 위임 세부사항 기준",
        "must_contain_terms": "총칙;위임된 세부사항",
        "query_style": "underspecified",
    },
    "supp_lh_31623e878a_p9_0103": {
        "query": "급수 가스 인허가 업무 기준",
        "must_contain_terms": "급수공사;가스공사;인·허가 업무",
        "query_style": "keywordish",
    },
    "supp_lh_31623e878a_p15_0104": {
        "query": "사용자재 신품 품질 조건",
        "must_contain_terms": "사용자재;장비;신품;품질",
        "query_style": "keywordish",
    },
    "supp_lh_31623e878a_p21_0105": {
        "query": "품질관리 LHCS 10 10 15",
        "must_contain_terms": "품질관리;LHCS 10 10 15",
        "query_style": "reference_lookup",
    },
    "supp_lh_1633f5fc74_p3_0107": {
        "query": "예비 준공검사 요건",
        "must_contain_terms": "예비 준공검사;약식기성검사;제출서류",
        "query_style": "short_fact_lookup",
    },
    "supp_lh_1633f5fc74_p4_0108": {
        "query": "준공대가 검사 조건",
        "must_contain_terms": "준공대가;검사;품질시험검사 성과 총괄표",
        "query_style": "keywordish",
    },
    "supp_lh_1633f5fc74_p8_0109": {
        "query": "수량 검측 장비 근로자 준비",
        "must_contain_terms": "수량 검측;장비;근로자",
        "query_style": "keywordish",
    },
    "supp_lh_a4995bcd89_p1_0111": {
        "query": "관련 기준 KCS 10 10 05",
        "must_contain_terms": "관련 기준;KCS 10 10 05",
        "query_style": "reference_lookup",
    },
    "supp_lh_a4995bcd89_p8_0113": {
        "query": "경고장 3번 건설기술인 교체",
        "must_contain_terms": "건설기술인;교체;경고장 3차",
        "query_style": "natural_question",
    },
    "supp_lh_a4995bcd89_p13_0114": {
        "query": "확인측량 지구계 경계 비교검토",
        "must_contain_terms": "확인측량;지구계 경계;지적측량;비교검토",
        "query_style": "keywordish",
    },
    "supp_lh_a4995bcd89_p14_0115": {
        "query": "공사현장 표지 설치 기준",
        "must_contain_terms": "공사현장 표지;제작;설치",
        "query_style": "fact_lookup",
    },
    "supp_lh_6acf57500f_p1_0121": {
        "query": "소방 전기 같이 도급받으면 하도급관리 따르나",
        "must_contain_terms": "소방공사;전기공사;건설공사 하도급관리",
        "query_style": "natural_question",
    },
    "supp_lh_6acf57500f_p12_0123": {
        "query": "공사대금 문자 서비스 빠진 내용 기준",
        "must_contain_terms": "공사대금지급 알림;SMS;건설공사 하도급관리",
        "query_style": "underspecified",
    },
    "supp_elec_bc85e2bfb2_p1_0036": {
        "query": "주택용 저압 기본요금 910원 표",
        "must_contain_terms": "주택용 저압;기본요금;910;전력량요금",
        "query_style": "table_value_lookup",
    },
    "supp_elec_bc85e2bfb2_p3_0038": {
        "query": "토요일 공휴일 계산기준 시간대",
        "must_contain_terms": "토요일;공휴일;계산기준;시간대",
        "query_style": "table_context_lookup",
    },
    "supp_elec_0cc37a0bed_p1_0051": {
        "query": "2024년 4월 저압 기본요금 구간",
        "must_contain_terms": "2024년 4월;주택용 저압;기본요금",
        "query_style": "table_value_lookup",
    },
    "supp_elec_0cc37a0bed_p3_0053": {
        "query": "최대부하 시간대 공휴일 기준",
        "must_contain_terms": "최대부하;시간대;공휴일 계산기준",
        "query_style": "table_context_lookup",
    },
    "supp_elec_65556c2c63_p1_0071": {
        "query": "2023년 5월 저압 요금 구간",
        "must_contain_terms": "2023년 5월;주택용 저압;요금 구간",
        "query_style": "table_value_lookup",
    },
    "supp_elec_65556c2c63_p2_0072": {
        "query": "일반용 을 산업용 을 토요일 기준",
        "must_contain_terms": "일반용전력(을);산업용전력(을);토요일",
        "query_style": "table_context_lookup",
    },
    "supp_elec_d73432a97b_p1_0001": {
        "query": "기타계절 동계 슈퍼유저 704.5원",
        "must_contain_terms": "기타계절;동계;슈퍼유저요금;704.5원",
        "query_style": "keywordish",
    },
    "supp_elec_d73432a97b_p2_0002": {
        "query": "가구별 평균사용량 단계별 계산",
        "must_contain_terms": "가구별 평균사용량;단계별;요금단가",
        "query_style": "formula_context_lookup",
    },
    "supp_elec_5db341e8bf_p1_0006": {
        "query": "종합표 동계 704.5원",
        "must_contain_terms": "종합;동계;704.5원",
        "query_style": "underspecified",
    },
    "supp_elec_8be2c46ed9_p1_0011": {
        "query": "연료비조정요금 뭐 반영해",
        "must_contain_terms": "연료비조정요금;석탄;천연가스;유류",
        "query_style": "natural_question",
    },
    "supp_elec_8be2c46ed9_p2_0012": {
        "query": "고압 사용량표 201부터",
        "must_contain_terms": "주택용 고압;사용량별 요금표;201",
        "query_style": "underspecified",
    },
    "supp_elec_6bd1f748a3_p1_0016": {
        "query": "저압 연료비조정단가 사용전력량",
        "must_contain_terms": "주택용 저압;연료비조정단가;사용전력량",
        "query_style": "keywordish",
    },
    "supp_elec_c456f27e5d_p1_0021": {
        "query": "고압 연료비조정 상하한",
        "must_contain_terms": "주택용 고압;연료비조정요금;상하한 ±5원",
        "query_style": "keywordish",
    },
    "supp_elec_c456f27e5d_p1_0025": {
        "query": "부가세랑 전력산업기반기금 계산",
        "must_contain_terms": "부가가치세;10%;전력사업기반기금;3.7%",
        "query_style": "formula_context_lookup",
    },
    "supp_elec_c456f27e5d_p2_0022": {
        "query": "고압 요금표 201 251 301 구간",
        "must_contain_terms": "주택용 고압;201;251;301",
        "query_style": "table_value_lookup",
    },
    "supp_elec_5632eb03a2_p1_0026": {
        "query": "저압 연료비조정 방식",
        "must_contain_terms": "주택용 저압;연료비조정요금;부과방식",
        "query_style": "short_fact_lookup",
    },
    "supp_elec_5632eb03a2_p1_0030": {
        "query": "청구금액 뭐 더해서 계산해",
        "must_contain_terms": "청구금액;전기요금;부가가치세;전력산업기반기금",
        "query_style": "natural_question",
    },
    "supp_elec_5632eb03a2_p2_0027": {
        "query": "계절 바뀌는 사용량표",
        "must_contain_terms": "계절;일수계산;사용량별 요금표",
        "query_style": "underspecified",
    },
    "supp_elec_625588fd70_p1_0031": {
        "query": "2024년 10월 동계 736.2원",
        "must_contain_terms": "2024년 10월;동계;736.2원",
        "query_style": "keywordish",
    },
    "supp_elec_625588fd70_p2_0032": {
        "query": "산업용 을 전기차 충전요금",
        "must_contain_terms": "산업용전력(을);전기자동차충전전력요금",
        "query_style": "table_context_lookup",
    },
    "supp_elec_bc85e2bfb2_p2_0037": {
        "query": "고압 A 경부하 중간부하 최대부하",
        "must_contain_terms": "고압 A;경부하;중간부하;최대부하",
        "query_style": "table_value_lookup",
    },
    "supp_elec_625588fd70_p3_0033": {
        "query": "봄가을철 시간대만으로 충분해",
        "must_contain_terms": "봄·가을철;3~5월;9~10월",
        "query_style": "underspecified_control",
    },
    "supp_elec_845dd6d1b2_p3_0058": {
        "query": "7월 요금표 봄가을철 시간대",
        "must_contain_terms": "7월;봄·가을철;시간대",
        "query_style": "table_control",
    },
    "supp_elec_ffe06a10cb_p3_0063": {
        "query": "보완전력 부족전력요금 표 조각",
        "must_contain_terms": "일반용보완전력요금;분산에너지사업자부족전력요금",
        "query_style": "underspecified_control",
    },
    "supp_elec_d73432a97b_p1_0003": {
        "query": "기후환경 5.3원만 있으면 돼",
        "must_contain_terms": "기후환경요금;5.3원",
        "query_style": "underspecified_control",
    },
    "supp_elec_5db341e8bf_p1_0008": {
        "query": "종합표 5.3원 단가 문구",
        "must_contain_terms": "종합;기후환경요금 단가;5.3원",
        "query_style": "keywordish_control",
    },
    "supp_elec_6bd1f748a3_p2_0017": {
        "query": "사용량별 요금표 제목만 있는 부분",
        "must_contain_terms": "사용량별 요금표;1주택수가구",
        "query_style": "control_lookup",
    },
    "supp_lh_7e8ae40964_p1_0090": {
        "query": "용어의 정의 KCS 참조",
        "must_contain_terms": "용어의 정의;KCS 10 10 10",
        "query_style": "reference_control",
    },
    "supp_lh_7e8ae40964_p19_0089": {
        "query": "건강친화형 주택 자체평가 이행확인서",
        "must_contain_terms": "건강친화형 주택;자체평가 이행확인서",
        "query_style": "reference_control",
    },
    "supp_lh_31623e878a_p3_0102": {
        "query": "지하주차장 옥내소화전 참조문",
        "must_contain_terms": "지하주차장;옥내소화전;LHCS 10 10 10 05",
        "query_style": "reference_control",
    },
    "supp_lh_1633f5fc74_p2_0106": {
        "query": "하자검사 쪽 제출 기준",
        "must_contain_terms": "하자검사;제출;LHCS 10 10 10 05",
        "query_style": "underspecified_control",
    },
    "supp_lh_1633f5fc74_p14_0110": {
        "query": "관련 법규 다음 사항은 따른다 부분",
        "must_contain_terms": "관련 법규;다음 사항;LHCS 10 10 10 05",
        "query_style": "reference_control",
    },
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_pack(
        source_csv=Path(args.source_csv),
        evidence_jsonl=Path(args.evidence_jsonl),
        output_dir=Path(args.output_dir),
        report_dir=Path(args.report_dir),
        prefix=args.prefix,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", default=str(DEFAULT_SOURCE_CSV))
    parser.add_argument("--evidence-jsonl", default=str(DEFAULT_EVIDENCE_JSONL))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    return parser.parse_args(argv)


def build_pack(
    *,
    source_csv: Path,
    evidence_jsonl: Path,
    output_dir: Path,
    report_dir: Path,
    prefix: str,
) -> dict[str, Any]:
    source_rows = read_csv(source_csv)
    validate_source(source_rows)
    evidence_by_id = read_evidence(evidence_jsonl)
    output_rows = [build_row(row, evidence_by_id.get(row["query_id"], {})) for row in source_rows]
    validate_output(output_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{prefix}.csv"
    jsonl_path = output_dir / f"{prefix}.jsonl"
    md_path = output_dir / f"{prefix}.md"
    summary_path = report_dir / SUMMARY_NAME
    for path in [csv_path, jsonl_path, md_path, summary_path]:
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")

    summary = build_summary(output_rows, source_csv, evidence_jsonl, csv_path, jsonl_path, md_path, summary_path)
    write_csv(csv_path, output_rows)
    write_jsonl(jsonl_path, output_rows)
    write_markdown(md_path, summary)
    write_json(summary_path, summary)

    return {
        "status": "PASS",
        "csv": rel(csv_path),
        "jsonl": rel(jsonl_path),
        "markdown": rel(md_path),
        "summary": rel(summary_path),
        "row_count": len(output_rows),
        "unique_query_count": len({row["query"] for row in output_rows}),
        "query_style_counts": summary["query_style_counts"],
        "review_group_counts": summary["review_group_counts"],
        "bucket_counts": summary["bucket_counts"],
    }


def build_row(source: dict[str, str], evidence: dict[str, Any]) -> dict[str, str]:
    manual = MANUAL_QUERY_REVIEWS[source["query_id"]]
    suggested = suggest_review(source["review_lane"])
    citation = evidence.get("citation") or {}
    bbox = citation.get("bbox", "")
    physical_page_index = citation.get("physical_page_index", "")
    if physical_page_index == "" and source["page_no"].isdigit():
        physical_page_index = str(int(source["page_no"]) - 1)
    tags = [
        f"pdf_review_lane:{source['review_lane']}",
        f"query_style:{manual['query_style']}",
        "codex_first_pass_review",
    ]
    if manual["query_style"].startswith("underspecified"):
        tags.append("intentionally_unfriendly_query")
    if "TABLE" in source["review_lane"]:
        tags.append("table_semantics_not_claimed")
    if source["review_lane"].startswith("FALSE_POSITIVE"):
        tags.append("false_positive_control")
    row = {
        "track": "PDF",
        "query_id": source["query_id"],
        "review_group": review_group(source["review_lane"]),
        "bucket": bucket(source),
        "query": manual["query"],
        "expected_answer_text": clean_text(source["expected_evidence_excerpt"]),
        "must_contain_terms": manual["must_contain_terms"],
        "expected_document_version_id": "",
        "expected_file_name": source["source_file_name"],
        "expected_page_no": source["page_no"],
        "expected_physical_page_index": str(physical_page_index),
        "expected_page_label": source["page_label"],
        "expected_section_id": "",
        "expected_chunk_id": "",
        "expected_sheet_name": "",
        "expected_cell_range": "",
        "expected_table_id": "",
        "expected_bbox": bbox,
        "suggested_gold_decision": suggested["gold_decision"],
        "suggested_answerability_label": suggested["answerability"],
        "suggested_relevance_label": suggested["relevance"],
        "suggested_expected_evidence_policy": suggested["evidence_policy"],
        "suggested_denominator_policy": suggested["denominator_policy"],
        "suggested_issue_tags": ";".join(tags),
        "suggested_notes": (
            f"Codex first-pass PDF review. Query manually written from PDF evidence, "
            f"using TEXT/XLSX pack style as reference. Original lane={source['review_lane']}. "
            f"Official denominator/promotion not changed."
        ),
    }
    for column in USER_COLUMNS:
        row[column] = ""
    return row


def suggest_review(lane: str) -> dict[str, str]:
    if lane in {"READY_SECTION_SUMMARY", "READY_EXTRACTIVE_CONTEXT"}:
        return {
            "gold_decision": "KEEP_POSITIVE",
            "answerability": "ANSWERABLE",
            "relevance": "RELEVANT",
            "evidence_policy": "KEEP_CURRENT_EVIDENCE",
            "denominator_policy": "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW",
        }
    if lane == "HIGH_CONFIDENCE_TABLE_CANDIDATE":
        return {
            "gold_decision": "REVISE_EXPECTED_EVIDENCE",
            "answerability": "UNCLEAR",
            "relevance": "PARTIAL",
            "evidence_policy": "REVISE_EXPECTED_EVIDENCE",
            "denominator_policy": "DEFER",
        }
    if lane == "READY_RESTRICTED_TABLE_CONTEXT":
        return {
            "gold_decision": "REVISE_EXPECTED_EVIDENCE",
            "answerability": "UNCLEAR",
            "relevance": "PARTIAL",
            "evidence_policy": "REVISE_EXPECTED_EVIDENCE",
            "denominator_policy": "DEFER",
        }
    return {
        "gold_decision": "RELABEL_NEGATIVE",
        "answerability": "NOT_ANSWERABLE",
        "relevance": "IRRELEVANT",
        "evidence_policy": "DEFER",
        "denominator_policy": "EXCLUDE_POSITIVE_DENOMINATOR",
    }


def review_group(lane: str) -> str:
    if lane in {"READY_SECTION_SUMMARY", "READY_EXTRACTIVE_CONTEXT"}:
        return "positive_retrieval_review"
    if lane in {"HIGH_CONFIDENCE_TABLE_CANDIDATE", "READY_RESTRICTED_TABLE_CONTEXT"}:
        return "table_or_range_policy_review"
    return "deferred_or_excluded_review"


def bucket(source: dict[str, str]) -> str:
    lane = source["review_lane"]
    if lane in {"HIGH_CONFIDENCE_TABLE_CANDIDATE", "READY_RESTRICTED_TABLE_CONTEXT"}:
        return "pdf_table_context_review"
    if lane.startswith("ABSTAIN"):
        return "pdf_abstain_control"
    if lane.startswith("FALSE_POSITIVE"):
        return "pdf_reference_control"
    return "pdf_electric_fee_lookup" if source["dataset"] == "elec" else "pdf_lh_spec_lookup"


def build_summary(
    rows: list[dict[str, str]],
    source_csv: Path,
    evidence_jsonl: Path,
    csv_path: Path,
    jsonl_path: Path,
    md_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "rag_pdf_gold_review_pack_manual_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": rel(source_csv),
        "evidence_jsonl": rel(evidence_jsonl),
        "text_review_reference": str(TEXT_REVIEW_REFERENCE),
        "xlsx_review_reference": str(XLSX_REVIEW_REFERENCE),
        "outputs": {
            "csv": rel(csv_path),
            "jsonl": rel(jsonl_path),
            "markdown": rel(md_path),
            "summary": rel(summary_path),
        },
        "row_count": len(rows),
        "unique_query_count": len({row["query"] for row in rows}),
        "query_style_counts": dict(Counter(MANUAL_QUERY_REVIEWS[row["query_id"]]["query_style"] for row in rows)),
        "review_group_counts": dict(Counter(row["review_group"] for row in rows)),
        "bucket_counts": dict(Counter(row["bucket"] for row in rows)),
        "suggested_gold_decision_counts": dict(Counter(row["suggested_gold_decision"] for row in rows)),
        "suggested_denominator_policy_counts": dict(Counter(row["suggested_denominator_policy"] for row in rows)),
        "intentionally_unfriendly_query_count": sum(
            1 for row in rows if "intentionally_unfriendly_query" in row["suggested_issue_tags"]
        ),
        "query_text_authored_by_codex": True,
        "query_text_generated_by_script": False,
        "same_columns_as_text_xlsx_review_pack": True,
        "user_columns_blank": True,
        "official_pdf_gold_created": False,
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
        "reference_hashes": [snapshot_file(path) for path in [TEXT_REVIEW_REFERENCE, XLSX_REVIEW_REFERENCE]],
    }


def validate_source(rows: list[dict[str, str]]) -> None:
    if len(rows) != 80:
        raise ValueError(f"Expected 80 PDF source rows, got {len(rows)}")
    ids = [row["query_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source query_id")
    mismatch = sorted(set(ids) ^ set(MANUAL_QUERY_REVIEWS))
    if mismatch:
        raise ValueError(f"Manual query map mismatch: {mismatch}")


def validate_output(rows: list[dict[str, str]]) -> None:
    if len(rows) != 80:
        raise ValueError(f"Expected 80 output rows, got {len(rows)}")
    if list(rows[0]) != PACK_COLUMNS:
        raise ValueError("Output columns do not match TEXT/XLSX review pack shape")
    ids = [row["query_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate output query_id")
    queries = [row["query"] for row in rows]
    if len(queries) != len(set(queries)):
        raise ValueError("Duplicate output query")
    for row in rows:
        for column in USER_COLUMNS:
            if row[column] != "":
                raise ValueError(f"{row['query_id']} has non-blank {column}")
        if row["expected_file_name"] and row["expected_file_name"] in row["query"]:
            raise ValueError(f"{row['query_id']} leaks expected_file_name in query")
        if re.search(r"\.pdf\b", row["query"], re.IGNORECASE):
            raise ValueError(f"{row['query_id']} leaks PDF filename literal in query")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_evidence(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            query_id = record.get("query_id")
            if query_id and query_id not in out:
                out[query_id] = record
    return out


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PACK_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    text = f"""# PDF Gold Review Pack Manual v1

Generated at: {summary["generated_at"]}

This pack uses the same 32-column CSV shape as the user-provided TEXT and XLSX
gold review packs. Query text was manually authored by Codex; the script only
fills locator and first-pass review columns.

## Counts

- Rows: `{summary["row_count"]}`
- Unique queries: `{summary["unique_query_count"]}`
- Intentionally unfriendly queries: `{summary["intentionally_unfriendly_query_count"]}`

## Review Groups

{format_counts(summary["review_group_counts"])}

## Buckets

{format_counts(summary["bucket_counts"])}

## Guardrails

- `official_pdf_gold_created=false`
- `official_denominator_changed=false`
- `promotion_evidence=false`
- `codex_gold_policy_decision_applied=false`
- `pdf_c7_policy_decision_applied=false`
- `table_semantics_success_claimed=false`
- `row_column_value_semantics_claimed=false`
- `bbox_contract_success_not_claimed=true`
- `live_llm_run=false`
- `optional_judge_run=false`
"""
    path.write_text(text, encoding="utf-8")


def format_counts(counts: dict[str, int]) -> str:
    return "\n".join(f"- `{key}`: `{value}`" for key, value in sorted(counts.items()))


def clean_text(value: str) -> str:
    return " ".join((value or "").split())


def snapshot_file(path: Path) -> dict[str, Any]:
    exists = path.exists()
    data = path.read_bytes() if exists else b""
    return {
        "path": str(path),
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
