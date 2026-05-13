"""Audit TEXT v1 review signals and build a clean TEXT/NAMU v2 review pack.

This workflow is diagnostic-only. It does not promote the current v1 review
pack, does not modify XLSX/PDF behavior, and does not change the official
denominator registry. The v2 rows below are manually curated query surfaces
bound to existing namu-v4 TEXT page/chunk evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from urllib.parse import unquote
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"
CORPUS_DIR = AI_WORKER_ROOT / "eval" / "corpora" / "namu-v4-structured-combined"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review" / "text_namu_v2_gold_review"
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"

V1_REVIEW_CSV = EVAL_QUERY_DIR / "text_gold_review_pack - text_gold_review_pack.csv"
V1_ORIGINAL_CSV = EVAL_QUERY_DIR / "gold_queries_text_namu_v4_v0.csv"
V2_CANDIDATE_CSV = REVIEW_DIR / "text_namu_v2_gold_candidates.csv"
V2_REVIEW_PACK_CSV = REVIEW_DIR / "text_namu_v2_gold_review_pack.csv"
V1_AUDIT_REPORT_JSON = REPORT_DIR / "rag_text_namu_v1_review_audit_report.json"
V2_SUMMARY_JSON = REPORT_DIR / "rag_text_namu_v2_gold_review_workflow_summary.json"
V2_VALIDATION_JSON = REPORT_DIR / "rag_text_namu_v2_gold_review_pack_validation_report.json"
V2_REPORT_MD = REPORT_DIR / "rag_text_namu_v2_gold_review_workflow_report.md"
V2_CLEANUP_EXPANSION_REPORT_MD = REPORT_DIR / "text_namu_v2_gold_cleanup_expansion_report.md"

SOURCE_DATASET = "ai/eval/corpora/namu-v4-structured-combined"
SOURCE_ORIGINAL_GOLD = "ai/eval/eval_queries/gold_queries_text_namu_v4_v0.csv"
SOURCE_SILVER_MANUAL = (
    "ai/eval/reports/phase7/7.12_silver_manual_curated/"
    "queries_v4_silver_manual_curated_500.jsonl"
)

V1_ORIGINAL_REQUIRED_COLUMNS = [
    "query_id",
    "bucket",
    "query",
    "expected_page_ids",
    "expected_section_ids",
    "expected_chunk_ids",
    "expected_answer_summary",
    "must_contain_terms",
    "must_not_contain_terms",
    "allowed_abstain",
    "answer_type",
    "label_status",
    "source_dataset",
    "notes",
]

V1_REVIEW_REQUIRED_COLUMNS = [
    "track",
    "query_id",
    "review_group",
    "bucket",
    "query",
    "expected_answer_text",
    "must_contain_terms",
    "expected_section_id",
    "expected_chunk_id",
    "suggested_gold_decision",
    "suggested_answerability_label",
    "suggested_relevance_label",
    "suggested_expected_evidence_policy",
    "suggested_denominator_policy",
    "suggested_issue_tags",
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]

V2_BUCKETS = [
    "direct_fact_lookup",
    "section_level_summary",
    "scene_quote_description_recall",
    "entity_title_disambiguation",
    "claim_check_wrong_assumption",
    "abstain_not_answerable_diagnostic",
]

V2_ANSWER_TYPES = [
    "short_fact",
    "section_summary",
    "scene_recall",
    "title_disambiguation",
    "claim_check",
    "abstain",
]

TARGET_ROW_COUNT = 100
TARGET_BUCKET_COUNTS = {
    "direct_fact_lookup": 30,
    "section_level_summary": 20,
    "scene_quote_description_recall": 16,
    "entity_title_disambiguation": 14,
    "claim_check_wrong_assumption": 10,
    "abstain_not_answerable_diagnostic": 10,
}
EXPECTED_NEW_BUCKET_COUNTS = {
    "direct_fact_lookup": 15,
    "section_level_summary": 10,
    "scene_quote_description_recall": 8,
    "entity_title_disambiguation": 7,
    "claim_check_wrong_assumption": 5,
    "abstain_not_answerable_diagnostic": 5,
}
INITIAL_50_BUCKET_COUNTS = {
    bucket: TARGET_BUCKET_COUNTS[bucket] - EXPECTED_NEW_BUCKET_COUNTS[bucket]
    for bucket in TARGET_BUCKET_COUNTS
}
BUCKET_ANSWER_TYPE = {
    "direct_fact_lookup": "short_fact",
    "section_level_summary": "section_summary",
    "scene_quote_description_recall": "scene_recall",
    "entity_title_disambiguation": "title_disambiguation",
    "claim_check_wrong_assumption": "claim_check",
    "abstain_not_answerable_diagnostic": "abstain",
}

HUMAN_REVIEW_COLUMNS = [
    "user_final_gold_policy",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_answer_override",
    "user_expected_evidence_override",
    "user_review_notes",
]

CANDIDATE_FIELDNAMES = [
    "query_id",
    "track",
    "bucket",
    "query",
    "expected_answer_text",
    "must_contain_terms",
    "expected_document_ids",
    "expected_page_ids",
    "expected_section_ids",
    "expected_chunk_ids",
    "expected_page_title",
    "expected_section_path",
    "source_url",
    "chunk_text_sha256",
    "source_evidence_quote",
    "answer_type",
    "allowed_abstain",
    "source_dataset",
    "source_original_gold",
    "source_query_id",
    "source_label_status",
    "source_locator",
    "candidate_default_policy",
    "generation_notes",
]

REVIEW_PACK_FIELDNAMES = [*CANDIDATE_FIELDNAMES, *HUMAN_REVIEW_COLUMNS]

FINAL_GOLD_POLICIES = {
    "KEEP_OFFICIAL",
    "DIAGNOSTIC_ONLY",
    "DROP",
    "NEEDS_REVIEW",
}
ANSWERABILITY_LABELS = {
    "ANSWERABLE",
    "PARTIALLY_ANSWERABLE",
    "NOT_ANSWERABLE",
    "AMBIGUOUS",
}
RELEVANCE_LABELS = {
    "RELEVANT",
    "PARTIAL",
    "IRRELEVANT",
    "AMBIGUOUS",
}

OLD_ACTION_LABELS = {
    "KEEP_POSITIVE",
    "REVISE_QUERY",
    "REVISE_EXPECTED_ANSWER",
    "REVISE_EXPECTED_EVIDENCE",
    "RELABEL_NEEDS_REVIEW",
    "RELABEL_NEGATIVE",
    "DEFER",
    "DIAGNOSTIC_ONLY_EXCLUDE",
    "REQUIRE_PARSER_OR_CHUNK_FIX",
}
OLD_ANSWERABILITY_LABELS = {"ANSWERABLE", "PARTIALLY_ANSWERABLE", "NOT_ANSWERABLE", "UNCLEAR", "AMBIGUOUS"}
TIME_SENSITIVE_TERMS = ["예정", "현재", "최근", "올해", "내년"]
KNOWN_PAGE_TITLE_NORMALIZATION_IDS = {
    "text_namu_v2_0009",
    "text_namu_v2_0012",
    "text_namu_v2_0013",
    "text_namu_v2_0015",
    "text_namu_v2_0016",
    "text_namu_v2_0017",
    "text_namu_v2_0021",
    "text_namu_v2_0022",
    "text_namu_v2_0023",
    "text_namu_v2_0024",
    "text_namu_v2_0026",
    "text_namu_v2_0028",
    "text_namu_v2_0029",
    "text_namu_v2_0033",
    "text_namu_v2_0047",
    "text_namu_v2_0048",
}
KNOWN_MUST_CONTAIN_FIX_IDS = {"text_namu_v2_0020", "text_namu_v2_0048"}
KNOWN_TIME_SENSITIVE_QUERY_FIX_IDS = {"text_namu_v2_0005", "text_namu_v2_0007"}
KNOWN_POLICY_NOTE_FIX_IDS = {"text_namu_v2_0045"}
KNOWN_SYNTHETIC_CLIPPED_QUOTE_IDS = {
    "text_namu_v2_0011",
    "text_namu_v2_0014",
    "text_namu_v2_0017",
    "text_namu_v2_0019",
    "text_namu_v2_0024",
    "text_namu_v2_0025",
    "text_namu_v2_0026",
    "text_namu_v2_0027",
    "text_namu_v2_0028",
    "text_namu_v2_0031",
    "text_namu_v2_0032",
    "text_namu_v2_0036",
    "text_namu_v2_0040",
    "text_namu_v2_0041",
    "text_namu_v2_0042",
    "text_namu_v2_0045",
    "text_namu_v2_0046",
    "text_namu_v2_0047",
    "text_namu_v2_0048",
    "text_namu_v2_0049",
}
PRE_REVIEW_POLISH_CHANGES = [
    {
        "query_id": "text_namu_v2_0080",
        "change": "query_rewrite",
        "reason": "clarified subject/object while preserving same source evidence and expected answer",
    },
    {
        "query_id": "text_namu_v2_0083",
        "change": "scene_bucket_replacement",
        "reason": (
            "replaced evaluation-summary-style row with unused source-bound plot-memory row "
            "v4-silver-natural-0074 to preserve 30/20/16/14/10/10 distribution"
        ),
    },
]


MANUAL_CANDIDATES: list[dict[str, str]] = [
    {
        "source_query_id": "gold_seed_0001",
        "bucket": "direct_fact_lookup",
        "query": "책벌레 사서 이야기 3기 애니의 감독과 방영 시기는 어떻게 돼",
        "expected_answer_text": "책벌레 사서 이야기 3기는 라이트 노벨을 원작으로 한 TV 애니메이션 제3기이며, 감독은 혼고 미츠루이고 방영 시기는 2022년 4월이다.",
        "must_contain_terms": "혼고 미츠루;2022년 4월;제3기",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup; v1 query overused document-finder wording.",
    },
    {
        "source_query_id": "gold_seed_0002",
        "bucket": "direct_fact_lookup",
        "query": "마기아 레코드 애니 1기는 언제 방영됐고 분량은 어땠어",
        "expected_answer_text": "마기아 레코드 애니메이션 1기는 2020년 1월부터 1쿨 분량으로 방영되었다.",
        "must_contain_terms": "2020년 1월;1쿨;1기",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup with concise answer anchors.",
    },
    {
        "source_query_id": "gold_seed_0003",
        "bucket": "direct_fact_lookup",
        "query": "아르페지오 애니의 정식 제목과 감독은 뭐야",
        "expected_answer_text": "푸른 강철의 아르페지오 애니메이션의 정식 제목은 푸른 강철의 아르페지오 아르스 노바이며, 감독은 키시 세이지이다.",
        "must_contain_terms": "아르스 노바;키시 세이지",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup; title and director only.",
    },
    {
        "source_query_id": "gold_seed_0004",
        "bucket": "direct_fact_lookup",
        "query": "나노하 20주년 셀렉션은 어떤 내용을 다시 방영한 거야",
        "expected_answer_text": "나노하 20주년 셀렉션은 시리즈 1기와 2기를 극장판화한 내용을 다시 TV 편집판으로 방영하는 애니메이션이며, 방영일은 2024년 10월이다.",
        "must_contain_terms": "1기;2기;TV 편집판;2024년 10월",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup; avoids copying the title as the whole query.",
    },
    {
        "source_query_id": "gold_seed_0005",
        "bucket": "direct_fact_lookup",
        "query": "자동판매기 미궁 방랑 애니 3기 방영 시기는 문서에 어떻게 적혀 있어",
        "expected_answer_text": "자동판매기 미궁 방랑 애니메이션 제3기는 야마모토 타카시가 감독이며, 방영 시기는 2026년 4월이다.",
        "must_contain_terms": "제3기;야마모토 타카시;2026년 4월",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup; expected answer is source-bound to v4 chunk evidence.",
    },
    {
        "source_query_id": "gold_seed_0009",
        "bucket": "direct_fact_lookup",
        "query": "메탈 베이블레이드 첫 애니는 어떤 이야기로 시작해",
        "expected_answer_text": "메탈 베이블레이드 첫 애니는 2009년 4월 방영한 탑블레이드의 후속작으로, 하가네 긴가가 다크 네뷸라와 류우가를 찾아 여행을 떠나는 이야기로 시작한다.",
        "must_contain_terms": "2009년 4월;하가네 긴가;다크 네뷸라;류우가",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup; story anchor without asking for a file.",
    },
    {
        "source_query_id": "gold_seed_0010",
        "bucket": "direct_fact_lookup",
        "query": "이나즈마 일레븐 2025 극장판 상영일은 문서에 언제로 적혀 있어",
        "expected_answer_text": "이나즈마 일레븐 2025 극장판은 두 작품이 동시 개봉되는 극장판이며, 상영일은 2025년 12월 27일이다.",
        "must_contain_terms": "2025년 12월 27일;동시 개봉;극장판",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup; date-centered.",
    },
    {
        "source_query_id": "gold_seed_0011",
        "bucket": "direct_fact_lookup",
        "query": "진화의 열매 애니 1기 감독과 방영 시기는 뭐야",
        "expected_answer_text": "진화의 열매 애니메이션 제1기는 오쿠무라 요시아키가 감독이며, 방영 시기는 2021년 10월이다.",
        "must_contain_terms": "오쿠무라 요시아키;2021년 10월;제1기",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup; title-sparse Korean query.",
    },
    {
        "source_query_id": "gold_seed_0016",
        "bucket": "direct_fact_lookup",
        "query": "몬스노에서 샤를마뉴의 파트너 몬스노는 뭐야",
        "expected_answer_text": "샤를마뉴는 팀의 리더로 설명되며, 파트너 몬스노는 사자 형태의 킹 블레이드이다.",
        "must_contain_terms": "샤를마뉴;킹 블레이드;사자",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct character fact lookup.",
    },
    {
        "source_query_id": "gold_seed_0017",
        "bucket": "direct_fact_lookup",
        "query": "사사키 군이 총알을 막았어 항목에 이름이 보이는 인물은 누구야",
        "expected_answer_text": "해당 항목에는 사사키 군, 카와구치 케이코, 쿠와노 등의 인물이 정리되어 있다.",
        "must_contain_terms": "사사키 군;카와구치 케이코;쿠와노",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct entity-list lookup from a character section.",
    },
    {
        "source_query_id": "gold_seed_0018",
        "bucket": "direct_fact_lookup",
        "query": "하트를 가족처럼 대하는 공룡은 어떤 태도를 보여",
        "expected_answer_text": "해당 공룡은 하트가 육식공룡이라는 사실을 알고도 가족으로 대하며, 결말부에서는 하트와 제대로 이별을 배웅한다.",
        "must_contain_terms": "하트;육식공룡;가족;이별",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct description recall from source-bound character evidence.",
    },
    {
        "source_query_id": "gold_seed_0019",
        "bucket": "direct_fact_lookup",
        "query": "유우야키의 나이와 생일은 어떻게 적혀 있어",
        "expected_answer_text": "유우야키는 나이 16세, 생일 9월 29일로 적혀 있다.",
        "must_contain_terms": "유우야키;16세;9월 29일",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup with deterministic anchors.",
    },
    {
        "source_query_id": "gold_seed_0020",
        "bucket": "direct_fact_lookup",
        "query": "크레용 신짱 유치원 쪽 전직 교사는 누구로 정리돼 있어",
        "expected_answer_text": "크레용 신짱 유치원 인물 항목에서는 코이즈미가 전직 벚꽃반 담임 선생님으로 정리되어 있다.",
        "must_contain_terms": "코이즈미;전직 벚꽃반 담임;유치원",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct section fact lookup.",
    },
    {
        "source_query_id": "gold_seed_0021",
        "bucket": "direct_fact_lookup",
        "query": "엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와",
        "expected_answer_text": "애드버서리는 앨리슨 실리스미스가 맡은 카메오 등장인물로 목록에 올라와 있다.",
        "must_contain_terms": "애드버서리;앨리슨 실리스미스;카메오",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct fact lookup; query avoids Latin title surface.",
    },
    {
        "source_query_id": "gold_seed_0022",
        "bucket": "direct_fact_lookup",
        "query": "블리치 게임 오리지널 인물로 어떤 이름들이 정리돼 있어",
        "expected_answer_text": "게임 오리지널 인물로 스즈나미 코노카, 알트로 프라테어드, 스즈나미 세이겐, 쿠도 후지마루, 쿠도 마츠리가 정리되어 있다.",
        "must_contain_terms": "스즈나미 코노카;알트로 프라테어드;쿠도 후지마루;쿠도 마츠리",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "direct list lookup from bound character section.",
    },
    {
        "source_query_id": "gold_seed_0023",
        "bucket": "section_level_summary",
        "query": "흑집사에서 주인공 친인척 항목은 어떤 가문 중심으로 정리돼",
        "expected_answer_text": "주인공의 가족 및 친인척 항목은 팬텀하이브 가문, 미드포드 가문, 덜레스 가문 등의 인물로 정리되어 있다.",
        "must_contain_terms": "팬텀하이브;미드포드;덜레스",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section-level summary over a character-family section.",
    },
    {
        "source_query_id": "gold_seed_0024",
        "bucket": "section_level_summary",
        "query": "실바니안 실크 고양이 가족 설명은 어떤 성격과 역할을 말해",
        "expected_answer_text": "실크 고양이 가족 설명은 실크고양이 소년이 상냥하고 배려심이 있으며 친구를 위로하고, 가족 중 장남이자 아들들 중 첫째라는 점을 말한다.",
        "must_contain_terms": "실크고양이 소년;상냥;배려심;장남",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section-level summary; answer is concise but source-bound.",
    },
    {
        "source_query_id": "gold_seed_0025",
        "bucket": "section_level_summary",
        "query": "듀얼마스터즈의 증표는 어떤 물건으로 설명돼",
        "expected_answer_text": "듀얼마스터즈의 증표는 대대로 듀얼마스터즈에게 전해지는 증표이며, 초월적인 힘이 깃들어 있는 물건으로 설명된다.",
        "must_contain_terms": "듀얼마스터즈의 증표;대대로;초월적인 힘",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section summary over a setting object.",
    },
    {
        "source_query_id": "gold_seed_0026",
        "bucket": "section_level_summary",
        "query": "죽은 자의 나라 설정은 어떤 사회로 설명돼",
        "expected_answer_text": "죽은 자의 나라는 지하에 존재하는 종교국가이며, 신을 섬기는 사람은 신사라고 불리고 사람들은 휘석이라는 특별한 돌을 지닌다.",
        "must_contain_terms": "지하;종교국가;신사;휘석",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section-level setting summary; avoids long source copy.",
    },
    {
        "source_query_id": "gold_seed_0027",
        "bucket": "section_level_summary",
        "query": "디럭스 대회 설정은 어떤 규모와 목적을 갖고 있었어",
        "expected_answer_text": "디럭스는 무카에 진키가 개최한 대형 대회이자 대형 뱅가드 대회로, 유명 파이터와 카운터 파이터가 참가했고 후에는 최고의 파이터를 포섭하기 위한 진키의 계획으로 밝혀진다.",
        "must_contain_terms": "디럭스;무카에 진키;대형 대회;최고의 파이터",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section-level setting summary from bound evidence.",
    },
    {
        "source_query_id": "gold_seed_0028",
        "bucket": "section_level_summary",
        "query": "원더 킬러는 원더 에그 안에서 어떤 존재로 설명돼",
        "expected_answer_text": "원더 킬러는 원더 에그를 깨고 나온 사람들에게 트라우마를 심은 대상이 구현화된 형태로, 사람과 비슷하지만 눈과 입이 흉측하게 묘사된다.",
        "must_contain_terms": "원더 킬러;트라우마;구현화;흉측",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section-level description summary.",
    },
    {
        "source_query_id": "gold_seed_0029",
        "bucket": "section_level_summary",
        "query": "사카이에상 두부는 소우카이야와 어떤 일로 무너졌어",
        "expected_answer_text": "사카이에상 두부는 싼값에 많은 두부를 파는 전략으로 업계 1위였지만, 요로시상 제약의 신형 클론 야쿠자를 구입하지 않아 소우카이야의 앙심을 사고 흉계로 무너졌다.",
        "must_contain_terms": "사카이에상 두부;요로시상 제약;소우카이야;흉계",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section-level setting summary.",
    },
    {
        "source_query_id": "gold_seed_0030",
        "bucket": "section_level_summary",
        "query": "안티 조이드 무장은 어떤 용도로 쓰이는 장비야",
        "expected_answer_text": "안티 조이드 무장은 대 조이드전을 위해 만들어진 무장으로, 조이드들의 블래스트 무장이나 커스터마이즈 파츠로도 쓰인다.",
        "must_contain_terms": "대 조이드전;블래스트 무장;커스터마이즈 파츠",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section-level object summary.",
    },
    {
        "source_query_id": "gold_seed_0031",
        "bucket": "section_level_summary",
        "query": "파밀리아가 모험자를 모두 잃으면 어떻게 된다고 설명돼",
        "expected_answer_text": "파밀리아가 모험자를 모두 잃어 구성원이 0명이 되면 자동으로 소멸 처리된다고 설명된다.",
        "must_contain_terms": "파밀리아;구성원이 0명;소멸 처리",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section-level rule summary.",
    },
    {
        "source_query_id": "gold_seed_0040",
        "bucket": "section_level_summary",
        "query": "전국 바사라 저지 엔드 방영 후 평가는 어떤 흐름이었어",
        "expected_answer_text": "방영 후 평가는 초반에는 어느 정도 호의적인 반응도 있었지만, 방영이 진행될수록 팬들과 시청자의 반응이 악평 일색으로 기울었다고 설명된다.",
        "must_contain_terms": "방영 후;호의적인 반응;악평 일색",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "section-level evaluation summary.",
    },
    {
        "source_query_id": "gold_seed_0032",
        "bucket": "scene_quote_description_recall",
        "query": "토코의 음악이 어떤 미래에도 없었다고 말하는 쿠키 장면을 확인해줘",
        "expected_answer_text": "쇼코가 키리시마 토코를 언급하며 자신은 수많은 미래에 대한 기억을 갖고 있지만 어느 미래에서도 키리시마 토코의 음악은 존재하지 않았다고 말한다.",
        "must_contain_terms": "쇼코;키리시마 토코;수많은 미래;음악",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "scene recall; shorter than v1 copied-answer query.",
    },
    {
        "source_query_id": "gold_seed_0033",
        "bucket": "scene_quote_description_recall",
        "query": "괴물 배터리라고 불린 야구 콤비는 누구였어",
        "expected_answer_text": "괴물 배터리는 강속구 투수 키요미네 하루카와 수완가 포수 카나메 케이로 이루어진 조합을 가리킨다.",
        "must_contain_terms": "키요미네 하루카;카나메 케이;괴물 배터리",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "recall query with clear entity anchors.",
    },
    {
        "source_query_id": "gold_seed_0034",
        "bucket": "scene_quote_description_recall",
        "query": "오오츠키가 외출 종료 전 미야모토 집에서 뭘 하며 시간을 보냈어",
        "expected_answer_text": "일일외출이 두 시간 정도 남은 오오츠키는 미야모토의 집에서 만화를 보면서 시간을 보낸다.",
        "must_contain_terms": "오오츠키;미야모토의 집;만화;두 시간",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "scene recall; avoids document-finder phrasing.",
    },
    {
        "source_query_id": "gold_seed_0035",
        "bucket": "scene_quote_description_recall",
        "query": "아스나는 오빠 방에서 무엇을 보고 게임에 들어가게 돼",
        "expected_answer_text": "아스나는 우편물을 전해주러 오빠의 방에 들어갔다가 너브 기어와 소드 아트 온라인 패키지를 보게 된다.",
        "must_contain_terms": "아스나;오빠의 방;너브 기어;패키지",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "scene recall with source anchors.",
    },
    {
        "source_query_id": "gold_seed_0036",
        "bucket": "scene_quote_description_recall",
        "query": "아키라가 돌아온 뒤 아츠시는 어떤 말로 위로해",
        "expected_answer_text": "아츠시는 만신창이가 되어 돌아온 야부키를 바라본 뒤, 돌아온 아키라에게 괴로운 역할이었겠다며 위로한다.",
        "must_contain_terms": "아츠시;야부키;아키라;괴로운 역할",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "scene recall from plot evidence.",
    },
    {
        "source_query_id": "gold_seed_0037",
        "bucket": "scene_quote_description_recall",
        "query": "유니가 라라의 우주선을 들고 도망간 이유는 뭐였어",
        "expected_answer_text": "호시조라 형사 메리 앤이 유니를 잡겠다고 쫓아오자, 유니가 라라의 우주선을 들고 도망가 라라는 집이자 우주선을 잃는다.",
        "must_contain_terms": "호시조라 형사 메리 앤;유니;라라;우주선",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "scene recall; concise causal query.",
    },
    {
        "source_query_id": "gold_seed_0038",
        "bucket": "scene_quote_description_recall",
        "query": "하늘도깨비 극장판 결말에서 승객들의 기억은 어떻게 돼",
        "expected_answer_text": "하리 가족의 기억을 포함해 구남매를 제외한 승객들의 기억이 도깨비들에 의해 지워지고, 하리와 두리가 신비와 금비와 함께 비행기 좌석에 앉아 있는 것으로 끝난다.",
        "must_contain_terms": "하리 가족;구남매;기억;도깨비;비행기 좌석",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "scene recall; row kept despite v1 review relevance cell being blank.",
    },
    {
        "source_query_id": "gold_seed_0039",
        "bucket": "scene_quote_description_recall",
        "query": "파리 전투 장면에서 무인 함대와 전함은 어떻게 묘사돼",
        "expected_answer_text": "방어 대형을 한 무인 함대가 빔을 막고, 아이오와급 전함들이 두 동강 나 파리 시가지 곳곳에 흩어진 것으로 묘사된다.",
        "must_contain_terms": "무인 함대;빔;아이오와급 전함;파리 시가지",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "scene recall; retrieval-hard but source-bound.",
    },
    {
        "source_query_id": "gold_seed_0006",
        "bucket": "entity_title_disambiguation",
        "query": "러브 라이브 선샤인의 극장판 문서는 어떤 작품을 말해",
        "expected_answer_text": "러브 라이브 선샤인의 극장판 문서는 러브 라이브! 선샤인!! The School Idol Movie Over the Rainbow를 말하며, 제작 공개는 티비 애니메이션 2기 최종화 직후 이루어졌다.",
        "must_contain_terms": "극장판;The School Idol Movie Over the Rainbow;2기 최종화",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "entity/title disambiguation; query avoids file-location wording.",
    },
    {
        "source_query_id": "gold_seed_0007",
        "bucket": "entity_title_disambiguation",
        "query": "이세계 방랑 밥 2기는 원작과 방영 시기가 어떻게 정리돼",
        "expected_answer_text": "이세계 방랑 밥 2기는 라이트 노벨을 원작으로 하는 TV 애니메이션 제2기이며, 감독은 마츠다 키요시이고 방영 시기는 2025년 10월이다.",
        "must_contain_terms": "라이트 노벨;제2기;마츠다 키요시;2025년 10월",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "title disambiguation with concise fact anchors.",
    },
    {
        "source_query_id": "gold_seed_0008",
        "bucket": "entity_title_disambiguation",
        "query": "꽃이 피는 첫걸음 홈 스위트 홈은 티비판이야 극장판이야",
        "expected_answer_text": "홈 스위트 홈은 티비 애니메이션 꽃이 피는 첫걸음의 극장판이며, 감독은 안도 마사히로이다.",
        "must_contain_terms": "극장판;꽃이 피는 첫걸음;안도 마사히로",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "entity/title disambiguation; resolves TV-vs-movie ambiguity.",
    },
    {
        "source_query_id": "gold_seed_0012",
        "bucket": "entity_title_disambiguation",
        "query": "클라나드 학원편 일부를 원작으로 한 이천칠년 애니 문서는 뭐야",
        "expected_answer_text": "해당 문서는 교토 애니메이션이 제작한 2007년 TV 애니메이션 클라나드 문서로, 원작 게임의 학원편 일부를 바탕으로 한다.",
        "must_contain_terms": "교토 애니메이션;2007년;학원편;클라나드",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "title disambiguation; query keeps Korean surface and avoids raw Latin title.",
    },
    {
        "source_query_id": "gold_seed_0013",
        "bucket": "entity_title_disambiguation",
        "query": "나히아 1기 문서는 원작의 어느 범위를 다뤄",
        "expected_answer_text": "나히아 1기 문서는 나의 히어로 아카데미아 TV 애니메이션 제1기를 말하며, 원작 1권부터 3권까지를 다룬다.",
        "must_contain_terms": "나의 히어로 아카데미아;제1기;1권;3권",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "alias/title disambiguation; source-bound scope question.",
    },
    {
        "source_query_id": "gold_seed_0014",
        "bucket": "entity_title_disambiguation",
        "query": "포켓몬스터 다이아몬드와 펄 계열 애니는 한국에서 어떤 이름으로 방영됐어",
        "expected_answer_text": "해당 애니메이션은 포켓몬스터 애니메이션 시리즈 세 번째 작품이며, 한국에서는 포켓몬스터 디피라는 이름으로 방영되었다.",
        "must_contain_terms": "세 번째 작품;포켓몬스터 디피;한국",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "title/alias disambiguation; natural Korean query.",
    },
    {
        "source_query_id": "gold_seed_0015",
        "bucket": "entity_title_disambiguation",
        "query": "진격의 거인 완결편 총집편 극장판은 어떤 구성의 작품이야",
        "expected_answer_text": "진격의 거인 완결편 총집편 극장판은 티비 애니메이션 더 파이널 시즌 완결편 전편과 후편을 합친 2시간 25분 분량의 총집편이다.",
        "must_contain_terms": "완결편;전편;후편;2시간 25분;총집편",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "title disambiguation; source-bound composition question.",
    },
    {
        "source_query_id": "gold_seed_0041",
        "bucket": "claim_check_wrong_assumption",
        "query": "극장판 시로바코 한국 개봉은 애니플러스 수입 추측만 있었고 확정은 없었어",
        "expected_answer_text": "아니다. 근거에는 2020년 6월 18일 애니플러스샵에 극장판 한국어 광고판이 걸리며 개봉이 확정되었다고 적혀 있다.",
        "must_contain_terms": "아니다;2020년 6월 18일;애니플러스샵;개봉이 확정",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "claim-check row; expected answer corrects a wrong assumption from bound evidence.",
    },
    {
        "source_query_id": "gold_seed_0042",
        "bucket": "claim_check_wrong_assumption",
        "query": "그리드맨 평가는 순수한 슈퍼로봇물이라고만 설명돼",
        "expected_answer_text": "아니다. 근거는 청춘 학원물의 외형, 90년대 슈퍼로봇물의 외형, 특촬물의 뼈대가 결합된 복합적인 작품이라고 설명한다.",
        "must_contain_terms": "아니다;청춘 학원물;슈퍼로봇물;특촬물;복합적인 작품",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "claim-check row with explicit correction.",
    },
    {
        "source_query_id": "gold_seed_0048",
        "bucket": "claim_check_wrong_assumption",
        "query": "디그레이맨 애니는 이천칠년에 방영한 거 맞아",
        "expected_answer_text": "아니다. 근거에는 디그레이맨 애니메이션의 방영 시기가 2006년 10월로 적혀 있다.",
        "must_contain_terms": "아니다;2006년 10월;방영 시기",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "claim-check; v1 needs_review evidence retained but not promoted.",
    },
    {
        "source_query_id": "gold_seed_0049",
        "bucket": "claim_check_wrong_assumption",
        "query": "최강 음양사의 이세계 애니는 이천이십사년에 방영한 거 맞아",
        "expected_answer_text": "아니다. 근거에는 최강 음양사의 이세계 전생기 애니메이션 방영 시기가 2023년 1월로 적혀 있다.",
        "must_contain_terms": "아니다;2023년 1월;방영 시기",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "claim-check; source-bound correction from existing v1 evidence.",
    },
    {
        "source_query_id": "gold_seed_0050",
        "bucket": "claim_check_wrong_assumption",
        "query": "블루 아카이브 첫 회는 폐교 대책위원회가 아니라 다른 동아리 이야기였어",
        "expected_answer_text": "아니다. 근거의 회차 목록에서 첫 회는 아비도스 고등학교 폐교 대책위원회로 적혀 있다.",
        "must_contain_terms": "아니다;첫 회;아비도스 고등학교;폐교 대책위원회",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "claim-check over an ambiguous v1 row; official review candidate requires human confirmation.",
    },
    {
        "source_query_id": "gold_seed_0043",
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "이 국내 흥행 표만 보고 제작비 회수 여부까지 판단할 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 국내 관객 수와 매출 표를 보여주지만 제작비나 손익분기점 정보는 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;국내 관객 수;매출 표;제작비",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "diagnostic-only abstain candidate; no positive denominator unless repo later supports abstain denominator.",
    },
    {
        "source_query_id": "gold_seed_0044",
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "이 평가 근거만으로 제작진의 다음 작품 계획까지 알 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 사카이 카즈오와 하나다 줏키 콤비의 역량, 방영 전 준비, 호평을 말하지만 다음 작품 계획은 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;사카이 카즈오;하나다 줏키;다음 작품 계획",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "diagnostic-only partial/negative answerability candidate.",
    },
    {
        "source_query_id": "gold_seed_0045",
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "영상미 평가만으로 이 작품의 제작비 규모를 알 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 영상미와 타나카 유타의 연출, 아름다운 화면 구성을 평가하지만 제작비 규모는 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;타나카 유타;영상미;제작비",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "diagnostic-only negative denominator candidate.",
    },
    {
        "source_query_id": "gold_seed_0046",
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "오프닝 평가 근거만으로 음악 담당자의 인터뷰 내용을 알 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 오프닝과 엔딩의 개그스러운 노래와 연출, 초반 내용과의 어울림을 말하지만 음악 담당자 인터뷰는 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;오프닝;엔딩;인터뷰",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "diagnostic-only abstain row; prevents positive denominator leakage.",
    },
    {
        "source_query_id": "gold_seed_0047",
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "어두운 주토피아라는 평가만으로 원작 판매량 추이를 알 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 어두운 주토피아라는 평가와 주제, 이야기, 모델링, 캐릭터 모션을 말하지만 원작 판매량 추이는 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;어두운 주토피아;판매량 추이",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "diagnostic-only abstain row; source-bound context but unsupported requested fact.",
    },
]

EXPANSION_CANDIDATES: list[dict[str, str]] = [
    {
        "source_query_id": "v4-silver-natural-0003",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "베리베리 뮤우뮤우 뉴는 어떤 원작과 기념 맥락으로 만들어졌어",
        "expected_answer_text": "베리베리 뮤우뮤우 뉴는 일본 만화 베리베리 뮤우뮤우를 원작으로 하는 TV 애니메이션 신작 제1기이며, 애니메이션 방영 20주년에 맞춰 방영되고 이쿠미 미아 작가의 헌정작이 되었다.",
        "must_contain_terms": "TV 애니메이션 신작 제1기;방영 20주년;이쿠미 미아",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup from manual-curated silver evidence.",
    },
    {
        "source_query_id": "v4-silver-natural-0008",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "아케인 2기는 공개 구성이 문서에 어떻게 설명돼",
        "expected_answer_text": "아케인 2기는 넷플릭스 오리지널 애니메이션 시리즈의 두 번째 시즌이며, 시즌 1처럼 3개의 챕터로 나누어 공개되었고 2024년 11월 9일 1막, 같은 달 23일 3막으로 막을 내렸다.",
        "must_contain_terms": "두 번째 시즌;3개의 챕터;2024년 11월 9일;3막",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup with date anchors as frozen source facts.",
    },
    {
        "source_query_id": "v4-silver-natural-0012",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "로코돌 만화는 작가와 완결 정보가 어떻게 적혀 있어",
        "expected_answer_text": "로코돌 만화는 코스기 코타로가 그린 로컬 아이돌 관련 만화이며, 2022년 2월에 연재가 종료되었고 단행본은 총 10권이 발매되었다.",
        "must_contain_terms": "코스기 코타로;로컬 아이돌;2022년 2월;총 10권",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup from source chunk.",
    },
    {
        "source_query_id": "v4-silver-natural-0013",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "베이블레이드 버스트 다이너마이트 배틀은 시리즈에서 어떤 위치야",
        "expected_answer_text": "베이블레이드 버스트 다이너마이트 배틀은 베이블레이드 버스트 시리즈의 6번째 작품이며, 베이블레이드 시리즈 최초 시즌 6 작품이자 코믹스와 시리즈의 완결편이다.",
        "must_contain_terms": "6번째 작품;최초 시즌 6;완결편",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup from overview chunk.",
    },
    {
        "source_query_id": "v4-silver-natural-0014",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "스페셜 에이는 몇 권으로 완결된 어떤 만화야",
        "expected_answer_text": "스페셜 에이는 미나미 마키가 하나토유메에서 연재한 순정만화이며, 총 17권으로 완결했고 코믹스의 편수는 99회이다.",
        "must_contain_terms": "미나미 마키;순정만화;총 17권;99회",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup from overview chunk.",
    },
    {
        "source_query_id": "v4-silver-natural-0027",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "무직전생 애니 1기 감독과 제작사, 방영 시기는 어떻게 적혀 있어",
        "expected_answer_text": "무직전생 애니메이션 제1기는 감독이 오카모토 마나부이고 제작사는 스튜디오 바인드이며, 방영 시기는 2021년 1월과 2021년 10월이다.",
        "must_contain_terms": "오카모토 마나부;스튜디오 바인드;2021년 1월;2021년 10월",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup with stable source-bound date wording.",
    },
    {
        "source_query_id": "v4-silver-natural-0029",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "드래곤 집을 사다 애니 감독과 방영 시기는 문서에 어떻게 나와",
        "expected_answer_text": "드래곤 집을 사다 애니메이션은 타누키 카오의 만화를 원작으로 하는 TV 애니메이션이며, 감독은 카스가모리 하루키이고 방영 시기는 2021년 4월이다.",
        "must_contain_terms": "타누키 카오;TV 애니메이션;카스가모리 하루키;2021년 4월",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup.",
    },
    {
        "source_query_id": "v4-silver-natural-0043",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "원피스 팬 레터는 어떤 원작과 기념 성격을 가진 애니야",
        "expected_answer_text": "원피스 팬 레터는 오사키 토모히토의 소설 단편집을 원작으로 하는 스핀오프이자 원피스 25주년 기념 TV 스페셜 애니메이션이며, 감독은 이시타니 메구미이다.",
        "must_contain_terms": "오사키 토모히토;스핀오프;25주년 기념;이시타니 메구미",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup from title-partial source evidence.",
    },
    {
        "source_query_id": "v4-silver-natural-0047",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "힘내라 동기짱 애니는 원작과 감독이 어떻게 적혀 있어",
        "expected_answer_text": "힘내라 동기짱 애니메이션은 일본 동인 작가 요무가 연재했던 만화를 원작으로 한 초단편 애니메이션이며, 감독은 코가 카즈오미이다.",
        "must_contain_terms": "요무;초단편 애니메이션;코가 카즈오미",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup from alias source evidence.",
    },
    {
        "source_query_id": "v4-silver-natural-0058",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "빈란드 사가 애니 1기 제작 정보는 어떻게 정리돼",
        "expected_answer_text": "빈란드 사가 애니메이션 제1기는 코믹스 빈란드 사가를 원작으로 하고, 감독은 야부타 슈헤이이며 제작사는 WIT STUDIO이고 방영시기는 2019년 7월이다.",
        "must_contain_terms": "야부타 슈헤이;WIT STUDIO;2019년 7월",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup.",
    },
    {
        "source_query_id": "v4-silver-natural-0077",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "나와 로보코 극장판 감독과 개봉 시기는 문서에 어떻게 나와",
        "expected_answer_text": "극장판 나와 로보코는 일본 만화 나와 로보코를 원작으로 하는 극장판 애니메이션이며, 감독은 다이치 아키타로이고 개봉시기는 2025년 4월 18일이다.",
        "must_contain_terms": "극장판 애니메이션;다이치 아키타로;2025년 4월 18일",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup with source-bound date wording.",
    },
    {
        "source_query_id": "v4-silver-natural-0083",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "너의 색은 어떤 영화제 수상과 초청 정보가 적혀 있어",
        "expected_answer_text": "너의 색은 야마다 나오코가 감독한 일본 오리지널 애니메이션 영화이며, 제26회 상하이 국제영화제 금잔상 최우수 애니메이션 영화상 수상작이고 안시 국제 애니메이션 영화제와 부산국제영화제에 초청되었다.",
        "must_contain_terms": "야마다 나오코;금잔상;최우수 애니메이션 영화상;부산국제영화제",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup.",
    },
    {
        "source_query_id": "v4-silver-natural-0095",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "스파이시 보이 제작자는 어떤 예명으로 설명돼",
        "expected_answer_text": "스파이시 보이의 제작자는 케이트 애로우라는 예명을 쓰는 인디 애니메이션 제작자이며, 제작자 공식 유튜브 채널에서 시청 가능하다고 설명된다.",
        "must_contain_terms": "케이트 애로우;인디 애니메이션 제작자;제작자 공식 유튜브 채널",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup from a short but source-bound chunk.",
    },
    {
        "source_query_id": "v4-silver-natural-0102",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "웨이브 서핑 애니 감독과 방영 시기는 문서에 어떻게 적혀 있어",
        "expected_answer_text": "웨이브 서핑 애니는 MAGES.의 미디어 믹스 WAVE!!를 원안으로 하는 TV 애니메이션이며, 감독은 오자키 타카하루이고 방영 시기는 2021년 1월이다.",
        "must_contain_terms": "MAGES.;오자키 타카하루;2021년 1월",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup.",
    },
    {
        "source_query_id": "v4-silver-natural-0113",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "direct_fact_lookup",
        "query": "기븐 히이라기 극장판은 공개일과 원작 범위가 문서에 어떻게 적혀 있어",
        "expected_answer_text": "문서에는 극장판 기븐 히이라기 믹스가 2024년 1월 27일 공개 예정인 일본 애니메이션 영화이며, 기븐의 두 번째 극장판이고 원작의 6,7권 분량을 다룬다고 적혀 있다.",
        "must_contain_terms": "2024년 1월 27일;두 번째 극장판;6,7권 분량",
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "generation_notes": "expanded direct fact lookup; time-sensitive source wording is explicitly document-bound.",
    },
    {
        "source_query_id": "v4-silver-natural-0001",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "초능력 배척 단체는 어떤 조직으로 설명돼",
        "expected_answer_text": "초능력 배척 단체는 노멀 일반인으로 구성된 과격파 조직이며, 폭탄 테러도 불사하는 사실상 테러리스트이고 주 대상은 초능력자와 초능력 관련 기관이다.",
        "must_contain_terms": "초능력 배척 단체;과격파 조직;테러리스트;초능력자",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level summary from setting evidence.",
    },
    {
        "source_query_id": "v4-silver-natural-0002",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "디아블로 설정은 어떤 장면들로 설명돼",
        "expected_answer_text": "디아블로 설정은 미겔이 소중한 동료가 디아블로가 되게 둘 수 없었다고 설명하고, 냐안에게 이미 디아블로가 된 것이냐며 경악하는 장면으로 제시된다.",
        "must_contain_terms": "디아블로;미겔;소중한 동료;냐안",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level setting summary.",
    },
    {
        "source_query_id": "v4-silver-natural-0009",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "크노소스 관련 근거에서 벨은 신들을 어떻게 의심해",
        "expected_answer_text": "크노소스 관련 근거에서 벨 크라넬은 신들이 탑을 일부러 부쉈을 것이라고 확신하며, 인간들이 탑을 완공해 감동하는 순간에 부쉈을 것이라고 본다.",
        "must_contain_terms": "벨 크라넬;신들이 탑을 일부러 부쉈을 것;확신;완공",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level summary from setting subpage.",
    },
    {
        "source_query_id": "v4-silver-natural-0016",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "요괴체인소드는 외형과 작동 방식이 어떻게 설명돼",
        "expected_answer_text": "요괴체인소드는 검과 톱을 합친듯한 외형을 하고 있으며, 줄을 당기면 진동하고 포트를 장착하면 믹스가 체인소드 모드로 바뀐다고 설명된다.",
        "must_contain_terms": "요괴체인소드;검과 톱;진동;체인소드 모드",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level setting summary.",
    },
    {
        "source_query_id": "v4-silver-natural-0026",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "케무리쿠사 나무 설정에서 미도리는 어떤 역할로 설명돼",
        "expected_answer_text": "케무리쿠사 나무 설정에서 미도리는 0.9화에 싹을 틔우고 1화 사이 현 미도리로 성장했으며, 리츠의 광범위 감시망 형성으로 피해를 크게 줄인 것으로 추정된다고 설명된다.",
        "must_contain_terms": "미도리;0.9화;리츠;광범위 감시망",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level summary from long setting evidence.",
    },
    {
        "source_query_id": "v4-silver-natural-0033",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "로봇트레인 아토 설정에서 제프리는 무엇을 싣고 다녀",
        "expected_answer_text": "로봇트레인 아토 설정에서 제프리는 아토를 가지고 있지 않고, 유닛이라고 부르는 로봇트레인의 추가 장착 장비를 싣고 다닌다.",
        "must_contain_terms": "제프리;아토;유닛;추가 장착 장비",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level setting summary.",
    },
    {
        "source_query_id": "v4-silver-natural-0064",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "백련의 패왕 부정적 평가는 페리시아 장면을 어떻게 지적해",
        "expected_answer_text": "백련의 패왕 부정적 평가에서는 유우토가 페리시아가 화살을 다 막아낼 힘이 있다고 예측하지 못했고, 원작의 먼 거리 표현을 감안해도 문제가 된다고 지적한다.",
        "must_contain_terms": "유우토;페리시아;화살;예측하지 못했고",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level evaluation summary.",
    },
    {
        "source_query_id": "v4-silver-natural-0085",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "블랙 클로버 1기 작화 평가는 어떤 식으로 갈린다고 설명돼",
        "expected_answer_text": "블랙 클로버 1기 평가는 작화에 관해서 평이 갈리고, 작화가 좋은 에피소드는 요시하라 타츠야나 타네무라 아야타카가 참여한 경우가 많다고 설명한다.",
        "must_contain_terms": "작화;요시하라 타츠야;타네무라 아야타카",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level evaluation summary.",
    },
    {
        "source_query_id": "v4-silver-natural-0163",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "이세계 식당 1기 결론 평가는 장단점을 어떻게 정리해",
        "expected_answer_text": "이세계 식당 1기 결론 평가는 원작의 컨셉과 분위기는 잘 살렸지만 각본의 부실함, 작화와 연출의 세부 표현 미흡, 오류, 괴상한 오리지널 연출 때문에 아쉽다는 평가가 많다고 정리한다.",
        "must_contain_terms": "컨셉과 분위기;각본의 부실함;세부 표현 미흡;오리지널 연출",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level evaluation summary.",
    },
    {
        "source_query_id": "v4-silver-natural-0184",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "section_level_summary",
        "query": "건담 지의 레콘기스타 흥행 문단은 시청률을 어떻게 평가해",
        "expected_answer_text": "건담 지의 레콘기스타 흥행 문단은 지레코 시청률이 건빌파 트라이보다 높고 철혈 2기보다 조금 밀리며, 심야방영을 고려하면 나쁘지 않은 수치라고 설명한다.",
        "must_contain_terms": "지레코 시청률;건빌파 트라이;철혈 2기;심야방영",
        "answer_type": "section_summary",
        "allowed_abstain": "false",
        "generation_notes": "expanded section-level summary from long evaluation evidence.",
    },
    {
        "source_query_id": "v4-silver-natural-0011",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "scene_quote_description_recall",
        "query": "메카졸들이 클론을 보자 어떤 이상한 행동을 했어",
        "expected_answer_text": "메카졸들은 클론들이 오자마자 후퇴했고, 오남매는 이상한 행동 때문에 일단 돌아가기로 결정했다.",
        "must_contain_terms": "메카졸;클론;후퇴;오남매",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "expanded scene recall from plot chunk.",
    },
    {
        "source_query_id": "v4-silver-natural-0019",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "scene_quote_description_recall",
        "query": "미츠하는 타키를 만나려고 어디로 향했어",
        "expected_answer_text": "미츠하는 자신과 몸이 바뀌고 있는 타키를 실제로 만나기 위해 도쿄로 향했다.",
        "must_contain_terms": "미츠하;타키;도쿄;몸이 바뀌고",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "expanded scene recall with concise source-supported answer.",
    },
    {
        "source_query_id": "v4-silver-natural-0023",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "scene_quote_description_recall",
        "query": "상인과의 접선장소를 추적하자 무엇이 밝혀져",
        "expected_answer_text": "상인과의 접선장소를 추적하자 상대방은 오로지 원격조종 로봇들이었다는 사실이 밝혀진다.",
        "must_contain_terms": "접선장소;상대방;원격조종 로봇;밝혀진다",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "expanded scene recall.",
    },
    {
        "source_query_id": "v4-silver-natural-0034",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "scene_quote_description_recall",
        "query": "포키는 왜 쓰레기통에서 포근함을 느낀다고 말해",
        "expected_answer_text": "포키는 자신이 음식을 먹는 데 사용되고 버려진 운명이라 쓰레기통에서 포근함을 느낀다고 말한다.",
        "must_contain_terms": "포키;음식을 먹는 데 사용;버려진 운명;쓰레기통",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "expanded scene recall.",
    },
    {
        "source_query_id": "v4-silver-natural-0035",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "scene_quote_description_recall",
        "query": "정체불명의 신호가 들어오자 위성을 어디에 집중해",
        "expected_answer_text": "정체불명의 신호가 들어오자 진행하던 일을 그만두고 위성을 그 신호에 집중한다.",
        "must_contain_terms": "정체불명의 신호;그만두고;위성;집중",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "expanded scene recall; pre-review polish clarified subject/object wording.",
    },
    {
        "source_query_id": "v4-silver-natural-0040",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "scene_quote_description_recall",
        "query": "번사이드가 버즈에게 한 말은 어떤 오마주로 설명돼",
        "expected_answer_text": "번사이드가 버즈에게 진짜 버즈 라이트이어라고 말하는 대사는 토이 스토리에서 우디가 버즈를 비꼴 때 했던 대사의 오마주로 보인다.",
        "must_contain_terms": "번사이드;진짜 버즈 라이트이어;우디;오마주",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "expanded scene recall.",
    },
    {
        "source_query_id": "v4-silver-natural-0045",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "scene_quote_description_recall",
        "query": "엘런의 거짓말 얘기에서 코니와 아르민, 미카사는 어떻게 반응해",
        "expected_answer_text": "코니는 뭐라고 반응하고, 아르민은 엘런이 꾸며낸 거짓말이라고 보며, 미카사는 자신이 가끔 두통에 시달리는 것은 사실이라고 말한다.",
        "must_contain_terms": "코니;아르민;엘런이 꾸며낸 거짓말;미카사",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "expanded scene recall from dialogue-like plot evidence.",
    },
    {
        "source_query_id": "v4-silver-natural-0074",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "scene_quote_description_recall",
        "query": "심의소에서 풀려난 엘런은 어디로 향해",
        "expected_answer_text": "심의소에서 풀려난 엘런은 오래된 고성인 구 조사병단 본부로 향했다.",
        "must_contain_terms": "심의소;풀려난 엘런;구 조사병단 본부",
        "answer_type": "scene_recall",
        "allowed_abstain": "false",
        "generation_notes": "pre-review polish replacement; true plot-memory scene recall replacing evaluation-summary-style row.",
    },
    {
        "source_query_id": "v4-silver-natural-0004",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "entity_title_disambiguation",
        "query": "소드아트 오디널 스케일은 어떤 극장판을 가리켜",
        "expected_answer_text": "소드아트 오디널 스케일은 2017년 2월 18일 일본에서 개봉한 소드 아트 온라인의 극장판 애니메이션을 가리킨다.",
        "must_contain_terms": "2017년 2월 18일;소드 아트 온라인;극장판 애니메이션",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "expanded title disambiguation; omitted stale current-status source clause.",
    },
    {
        "source_query_id": "v4-silver-natural-0017",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "entity_title_disambiguation",
        "query": "폴 프린세스 극장판은 어떤 주제와 개봉 시기로 설명돼",
        "expected_answer_text": "폴 프린세스 극장판은 폴 프린세스를 원작으로 하는 오리지널 극장판 애니메이션이며, 폴댄스를 주제로 하고 개봉 시기는 2023년 11월 23일이다.",
        "must_contain_terms": "오리지널 극장판 애니메이션;폴댄스;2023년 11월 23일",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "expanded title disambiguation.",
    },
    {
        "source_query_id": "v4-silver-natural-0018",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "entity_title_disambiguation",
        "query": "프리큐어 미라클 리프 개봉 발표는 문서에 어떻게 정리돼",
        "expected_answer_text": "문서에는 7월 10일 극장판 힐링굿 프리큐어의 2021년 개봉 예정 소식과 함께 본작이 10월 31일에 개봉 예정이라고 발표되었다고 정리돼 있다.",
        "must_contain_terms": "7월 10일;2021년 개봉 예정;10월 31일;개봉 예정",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "expanded title disambiguation; time-sensitive source wording is explicitly document-bound.",
    },
    {
        "source_query_id": "v4-silver-natural-0037",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "entity_title_disambiguation",
        "query": "극장판 오소마츠 육쌍둥이는 어떤 시기를 다룬 작품이야",
        "expected_answer_text": "극장판 오소마츠 육쌍둥이는 오소마츠 상 형제들의 고교생 시기를 다룬 극장판이며, 일본에서는 2019년 3월 15일 개봉했다.",
        "must_contain_terms": "고교생 시기;극장판;2019년 3월 15일",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "expanded title disambiguation.",
    },
    {
        "source_query_id": "v4-silver-natural-0069",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "entity_title_disambiguation",
        "query": "세일러 문 코스모스 극장판은 어떤 후속작이자 어떤 편을 다뤄",
        "expected_answer_text": "세일러 문 코스모스 극장판은 극장판 미소녀 전사 세일러 문 Eternal의 후속작이며, 원작 코믹스 5기 섀도우 갤럭티카 편을 다룬다.",
        "must_contain_terms": "Eternal의 후속작;원작 코믹스 5기;섀도우 갤럭티카",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "expanded title disambiguation.",
    },
    {
        "source_query_id": "v4-silver-natural-0096",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "entity_title_disambiguation",
        "query": "두 사람의 엘더는 전작과 어떤 관계의 작품이야",
        "expected_answer_text": "두 사람의 엘더는 CARAMEL-BOX에서 2005년 제작한 소녀는 언니를 사랑한다의 정식 후속작이며, 전작으로부터 5년만에 등장한 신작이다.",
        "must_contain_terms": "CARAMEL-BOX;정식 후속작;5년만에;신작",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "expanded title disambiguation.",
    },
    {
        "source_query_id": "v4-silver-natural-0120",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "entity_title_disambiguation",
        "query": "프리 이터널 서머는 시리즈에서 어떤 작품이고 언제 방영됐어",
        "expected_answer_text": "프리 이터널 서머는 Free 시리즈의 두 번째 작품이자 1기 방영 약 1년 뒤의 후속작이며, 감독은 우츠미 히로코이고 방영 시기는 2014년 7월이다.",
        "must_contain_terms": "두 번째 작품;후속작;우츠미 히로코;2014년 7월",
        "answer_type": "title_disambiguation",
        "allowed_abstain": "false",
        "generation_notes": "expanded title disambiguation.",
    },
    {
        "source_query_id": "v4-silver-natural-0145",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "claim_check_wrong_assumption",
        "query": "최약 테이머 애니 1기는 이천이십오년에 방영한 거 맞아",
        "expected_answer_text": "아니다. 문서에는 최약 테이머 애니메이션 제1기의 방영 시기가 2024년 1월로 적혀 있다.",
        "must_contain_terms": "아니다;제1기;2024년 1월",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "expanded claim-check; source_label_status=needs_review expected from wrong_assumption.",
    },
    {
        "source_query_id": "v4-silver-natural-0164",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "claim_check_wrong_assumption",
        "query": "닥터 스톤 애니 1기는 이천이십년에 방영한 거 맞아",
        "expected_answer_text": "아니다. 문서에는 닥터 스톤 애니메이션 제1기의 방영 시기가 2019년 7월로 적혀 있다.",
        "must_contain_terms": "아니다;제1기;2019년 7월",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "expanded claim-check; source_label_status=needs_review expected from wrong_assumption.",
    },
    {
        "source_query_id": "v4-silver-natural-0199",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "claim_check_wrong_assumption",
        "query": "최강의 왕 두 번째 인생 2기는 이천이십칠년에 방영한 거 맞아",
        "expected_answer_text": "아니다. 문서에는 최강의 왕 두 번째 인생 애니메이션 제2기의 방영 시기가 2026년 4월로 적혀 있다.",
        "must_contain_terms": "아니다;제2기;2026년 4월",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "expanded claim-check; source_label_status=needs_review expected from wrong_assumption.",
    },
    {
        "source_query_id": "v4-silver-natural-0205",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "claim_check_wrong_assumption",
        "query": "내 여동생이 이렇게 귀여울 리가 없어 1기는 방영 시기가 이천십일년뿐이야",
        "expected_answer_text": "아니다. 문서에는 방영 시기가 2010년 10월 GOOD 루트와 2011년 2월 TRUE 루트로 적혀 있다.",
        "must_contain_terms": "아니다;2010년 10월;2011년 2월;TRUE 루트",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "expanded claim-check; source_label_status=needs_review expected from wrong_assumption.",
    },
    {
        "source_query_id": "v4-silver-natural-0218",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "claim_check_wrong_assumption",
        "query": "비탄의 망령 애니는 이천이십오년에만 방영하는 거야",
        "expected_answer_text": "아니다. 문서에는 비탄의 망령 애니메이션 방영 시기가 2024년 10월 1쿨과 2025년 10월 2쿨로 적혀 있다.",
        "must_contain_terms": "아니다;2024년 10월;2025년 10월;2쿨",
        "answer_type": "claim_check",
        "allowed_abstain": "false",
        "generation_notes": "expanded claim-check; source_label_status=needs_review expected from wrong_assumption.",
    },
    {
        "source_query_id": "v4-silver-natural-0084",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "스파이 패밀리 평가 근거만으로 위장 가족 임무의 전체 결말을 알 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 1화 퀄리티, 연출력, 작화, 원작 재현, 영상미 같은 평가를 말하지만 전체 결말은 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;퀄리티;영상미;전체 결말",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "expanded diagnostic-only abstain row; adjacent context does not support requested fact.",
    },
    {
        "source_query_id": "v4-silver-natural-0143",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "진격 중학교 에피소드 가이드만으로 제작비 총액을 알 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 에피소드 가이드와 각 화의 줄거리 단서를 제공하지만 제작비 총액은 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;에피소드 가이드;줄거리;제작비 총액",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "expanded diagnostic-only abstain row.",
    },
    {
        "source_query_id": "v4-silver-natural-0213",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "말하자면 막나가기 설명만으로 앨범 판매량을 알 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 말하자면 막나가기의 가사 구성, 곡 전개, 성우 열연을 설명하지만 앨범 판매량은 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;말하자면 막나가기;성우 열연;앨범 판매량",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "expanded diagnostic-only abstain row.",
    },
    {
        "source_query_id": "v4-silver-natural-0357",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "타테야마 아야카 설명만으로 고고학 논문 제목을 알 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 타테야마 아야카가 고고학자로 추정되고 오컬트 관련에 관심이 많다고 설명하지만 고고학 논문 제목은 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;타테야마 아야카;고고학자;고고학 논문 제목",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "expanded diagnostic-only abstain row.",
    },
    {
        "source_query_id": "v4-silver-natural-0436",
        "source_artifact": SOURCE_SILVER_MANUAL,
        "bucket": "abstain_not_answerable_diagnostic",
        "query": "카게 직위 설명만으로 각 마을 역대 카게 명단을 모두 알 수 있어",
        "expected_answer_text": "확인할 수 없음. 근거는 카게가 닌자 5대국의 마을 수장이고 영주와 장로들이 후보를 심사해 임명한다고 설명하지만 역대 카게 명단은 제공하지 않는다.",
        "must_contain_terms": "확인할 수 없음;카게;마을 수장;역대 카게 명단",
        "answer_type": "abstain",
        "allowed_abstain": "true",
        "generation_notes": "expanded diagnostic-only abstain row.",
    },
]

MANUAL_CANDIDATES = [*MANUAL_CANDIDATES, *EXPANSION_CANDIDATES]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "validate":
        pack_path = Path(args.review_pack)
        candidate_rows, _ = read_csv(Path(args.candidates))
        review_rows, review_columns = read_csv(pack_path)
        needed_page_ids, needed_chunk_ids = ids_needed_by_rows(review_rows)
        pages, chunks = load_needed_corpus(Path(args.corpus_dir), needed_page_ids, needed_chunk_ids)
        validation = validate_v2_review_pack(
            review_rows,
            columns=review_columns,
            pages=pages,
            chunks=chunks,
            require_reviewed=args.require_reviewed,
            expected_row_count=TARGET_ROW_COUNT,
        )
        validation = add_candidate_review_pack_equality_validation(
            validation,
            candidate_rows=candidate_rows,
            review_rows=review_rows,
        )
        report = build_validation_report(
            review_pack=pack_path,
            candidate_csv=Path(args.candidates),
            validation=validation,
            candidate_count=len(candidate_rows),
            require_reviewed=args.require_reviewed,
        )
        write_json(Path(args.validation_report), report)
        print_json(
            {
                "status": report["status"],
                "review_pack": normalise_path(pack_path),
                "report": normalise_path(Path(args.validation_report)),
                "derived_policy_counts": report["derived_policy_counts"],
            }
        )
        return 0 if report["status"] == "PASSED" else 1

    summary = run_build(
        v1_review_csv=Path(args.v1_review_csv),
        v1_original_csv=Path(args.v1_original_csv),
        corpus_dir=Path(args.corpus_dir),
        review_dir=Path(args.review_dir),
        audit_report=Path(args.audit_report),
        summary_report=Path(args.summary_report),
        validation_report=Path(args.validation_report),
        md_report=Path(args.md_report),
        cleanup_expansion_report=Path(args.cleanup_expansion_report),
    )
    print_json(
        {
            "status": summary["status"],
            "v1_audit_status": summary["v1_audit"]["status"],
            "candidate_csv": summary["v2_paths"]["candidate_csv"],
            "review_pack_csv": summary["v2_paths"]["review_pack_csv"],
            "bucket_counts": summary["v2_candidate_summary"]["bucket_counts"],
            "validation_status": summary["v2_review_validation"]["status"],
        }
    )
    return 0 if summary["status"] == "COMPLETED" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["build", "validate"], default="build")
    parser.add_argument("--v1-review-csv", default=str(V1_REVIEW_CSV))
    parser.add_argument("--v1-original-csv", default=str(V1_ORIGINAL_CSV))
    parser.add_argument("--corpus-dir", default=str(CORPUS_DIR))
    parser.add_argument("--review-dir", default=str(REVIEW_DIR))
    parser.add_argument("--audit-report", default=str(V1_AUDIT_REPORT_JSON))
    parser.add_argument("--summary-report", default=str(V2_SUMMARY_JSON))
    parser.add_argument("--validation-report", default=str(V2_VALIDATION_JSON))
    parser.add_argument("--md-report", default=str(V2_REPORT_MD))
    parser.add_argument("--cleanup-expansion-report", default=str(V2_CLEANUP_EXPANSION_REPORT_MD))
    parser.add_argument("--review-pack", default=str(V2_REVIEW_PACK_CSV))
    parser.add_argument("--candidates", default=str(V2_CANDIDATE_CSV))
    parser.add_argument("--require-reviewed", action="store_true")
    return parser.parse_args(argv)


def run_build(
    *,
    v1_review_csv: Path,
    v1_original_csv: Path,
    corpus_dir: Path,
    review_dir: Path,
    audit_report: Path,
    summary_report: Path,
    validation_report: Path,
    md_report: Path,
    cleanup_expansion_report: Path,
) -> dict[str, Any]:
    generated_at = utc_timestamp()
    v1_original, original_columns = read_csv(v1_original_csv)
    v1_review, review_columns = read_csv(v1_review_csv)
    previous_candidate_csv = review_dir / V2_CANDIDATE_CSV.name
    previous_candidate_rows: list[dict[str, str]] = []
    if previous_candidate_csv.exists():
        previous_candidate_rows, _ = read_csv(previous_candidate_csv)

    audit = audit_v1_review_pack(
        reviewed_rows=v1_review,
        reviewed_columns=review_columns,
        original_rows=v1_original,
        original_columns=original_columns,
        reviewed_path=v1_review_csv,
        original_path=v1_original_csv,
    )
    write_json(audit_report, audit)

    source_by_id = {clean(row.get("query_id")): row for row in v1_original}
    silver_rows = read_jsonl(REPO_ROOT / SOURCE_SILVER_MANUAL)
    source_by_id.update({clean(row.get("query_id")): row for row in silver_rows})
    needed_source_ids = {candidate["source_query_id"] for candidate in MANUAL_CANDIDATES}
    missing_sources = sorted(source_id for source_id in needed_source_ids if source_id not in source_by_id)
    if missing_sources:
        raise ValueError("manual candidates reference missing source rows: " + ", ".join(missing_sources))

    needed_page_ids, needed_chunk_ids = ids_needed_by_rows(
        source_by_id[source_id] for source_id in sorted(needed_source_ids)
    )
    pages, chunks = load_needed_corpus(corpus_dir, needed_page_ids, needed_chunk_ids)

    candidates = build_v2_candidates(
        manual_candidates=MANUAL_CANDIDATES,
        original_by_id=source_by_id,
        pages=pages,
        chunks=chunks,
    )
    candidate_validation = validate_v2_candidates(candidates, pages=pages, chunks=chunks)
    if candidate_validation["status"] != "PASSED":
        raise ValueError("v2 candidate validation failed; see row_errors in generated summary")

    review_pack_rows = build_v2_review_pack(candidates)
    review_dir.mkdir(parents=True, exist_ok=True)
    candidate_csv = review_dir / V2_CANDIDATE_CSV.name
    review_pack_csv = review_dir / V2_REVIEW_PACK_CSV.name
    write_csv(candidate_csv, candidates, fieldnames=CANDIDATE_FIELDNAMES)
    write_csv(review_pack_csv, review_pack_rows, fieldnames=REVIEW_PACK_FIELDNAMES)

    pack_needed_page_ids, pack_needed_chunk_ids = ids_needed_by_rows(review_pack_rows)
    pack_pages, pack_chunks = load_needed_corpus(corpus_dir, pack_needed_page_ids, pack_needed_chunk_ids)
    review_validation = validate_v2_review_pack(
        review_pack_rows,
        columns=REVIEW_PACK_FIELDNAMES,
        pages=pack_pages,
        chunks=pack_chunks,
        require_reviewed=False,
        expected_row_count=TARGET_ROW_COUNT,
    )
    review_validation = add_candidate_review_pack_equality_validation(
        review_validation,
        candidate_rows=candidates,
        review_rows=review_pack_rows,
    )
    validation_json = build_validation_report(
        review_pack=review_pack_csv,
        candidate_csv=candidate_csv,
        validation=review_validation,
        candidate_count=len(candidates),
        require_reviewed=False,
    )
    write_json(validation_report, validation_json)

    candidate_summary = summarize_candidates(candidates)
    previous_summary = summarize_baseline_candidate_rows(previous_candidate_rows)
    cleanup_changes = cleanup_change_summary(previous_candidate_rows)
    expansion_rows = [row for row in candidates if clean(row.get("query_id")) > "text_namu_v2_0050"]
    expansion_summary = {
        "new_row_count": len(expansion_rows),
        "new_rows_by_bucket": dict(sorted(Counter(row["bucket"] for row in expansion_rows).items())),
        "new_rows_by_policy": dict(
            sorted(Counter(row["candidate_default_policy"] for row in expansion_rows).items())
        ),
        "target_shortfall": max(0, TARGET_ROW_COUNT - len(candidates)),
        "target_shortfall_reason": "" if len(candidates) >= TARGET_ROW_COUNT else "insufficient safe source-bound candidates",
    }
    summary = {
        "run_id": utc_run_id("rag_text_namu_v2_gold_review"),
        "generated_at": generated_at,
        "schema_version": "rag_text_namu_v2_gold_review_workflow_v1",
        "status": "COMPLETED" if validation_json["status"] == "PASSED" else "FAILED",
        "scope": "track_b_text_namu_v2_gold_candidate_review",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "official_denominator_changed": False,
        "gold_csv_modified": False,
        "xlsx_behavior_modified": False,
        "pdf_behavior_modified": False,
        "retrieval_eval_run": False,
        "indexing_run": False,
        "tuning_run": False,
        "live_llm_run": False,
        "v1_audit": {
            "status": audit["status"],
            "reviewed_row_count": audit["row_counts"]["reviewed"],
            "original_row_count": audit["row_counts"]["original"],
            "query_id_set_equal": audit["query_id_checks"]["set_equal"],
            "suspected_issue": audit["classification"]["primary_suspected_issue"],
            "action_label_in_answerability_count": audit["invalid_label_placements"][
                "action_label_in_user_answerability_label_count"
            ],
        },
        "v2_paths": {
            "candidate_csv": normalise_path(candidate_csv),
            "review_pack_csv": normalise_path(review_pack_csv),
            "v1_audit_report": normalise_path(audit_report),
            "validation_report": normalise_path(validation_report),
            "workflow_summary": normalise_path(summary_report),
            "markdown_report": normalise_path(md_report),
            "cleanup_expansion_report": normalise_path(cleanup_expansion_report),
        },
        "v2_candidate_summary": candidate_summary,
        "previous_v2_candidate_summary": previous_summary,
        "cleanup_changes_applied": cleanup_changes,
        "expansion_summary": expansion_summary,
        "pre_review_polish_changes": PRE_REVIEW_POLISH_CHANGES,
        "candidate_validation": candidate_validation,
        "v2_review_validation": validation_json,
        "review_pack_schema": {
            "human_edit_columns": HUMAN_REVIEW_COLUMNS,
            "removed_v1_human_columns": [
                "user_gold_decision",
                "user_expected_evidence_policy",
                "user_denominator_policy",
                "user_issue_tags",
                "user_notes",
            ],
            "denominator_policy_user_editable": False,
        },
        "denominator_policy": conservative_denominator_policy_description(),
        "commands": {
            "build": (
                "python ai/scripts/rag_text_namu_v2_gold_review_workflow.py "
                "--mode build"
            ),
            "validate_review_pack": (
                "python ai/scripts/rag_text_namu_v2_gold_review_workflow.py "
                "--mode validate --review-pack "
                "ai/eval/review/text_namu_v2_gold_review/text_namu_v2_gold_review_pack.csv"
            ),
        },
        "limitations": [
            "v2 rows are review candidates, not final official TEXT gold.",
            "Initial review pack keeps user policy as NEEDS_REVIEW; official denominators remain zero until human review is valid.",
            "Abstain/not-answerable rows are diagnostic-only by default because the current registry has no abstain denominator for Track B.",
            "The workflow validates against rag_chunks.jsonl; chunks_v4.jsonl is intentionally not used because it has a different chunk-id namespace.",
            "No retrieval, indexing, tuning, live LLM, optional judge, or XLSX/PDF behavior change was performed.",
        ],
    }
    write_json(summary_report, summary)
    write_markdown_report(md_report, summary, audit)
    write_markdown_report(cleanup_expansion_report, summary, audit)
    return summary


def audit_v1_review_pack(
    *,
    reviewed_rows: list[dict[str, str]],
    reviewed_columns: list[str],
    original_rows: list[dict[str, str]],
    original_columns: list[str],
    reviewed_path: Path,
    original_path: Path,
) -> dict[str, Any]:
    reviewed_ids = [clean(row.get("query_id")) for row in reviewed_rows]
    original_ids = [clean(row.get("query_id")) for row in original_rows]
    reviewed_id_set = {query_id for query_id in reviewed_ids if query_id}
    original_id_set = {query_id for query_id in original_ids if query_id}
    duplicate_reviewed = sorted(q for q, count in Counter(reviewed_ids).items() if q and count > 1)
    duplicate_original = sorted(q for q, count in Counter(original_ids).items() if q and count > 1)

    raw_vocabs = {
        column: dict(sorted(Counter(clean(row.get(column)) or "<empty>" for row in reviewed_rows).items()))
        for column in [
            "user_gold_decision",
            "user_answerability_label",
            "user_relevance_label",
            "user_expected_evidence_policy",
            "user_denominator_policy",
            "user_issue_tags",
        ]
        if column in reviewed_columns
    }
    action_in_answerability = [
        clean(row.get("query_id"))
        for row in reviewed_rows
        if clean(row.get("user_answerability_label")) in OLD_ACTION_LABELS
    ]
    answerability_in_gold_policy = [
        clean(row.get("query_id"))
        for row in reviewed_rows
        if clean(row.get("user_gold_decision")) in OLD_ANSWERABILITY_LABELS
    ]
    missing_user_relevance = [
        clean(row.get("query_id")) for row in reviewed_rows if not clean(row.get("user_relevance_label"))
    ]
    empty_expected_evidence_policy = [
        clean(row.get("query_id")) for row in reviewed_rows if not clean(row.get("user_expected_evidence_policy"))
    ]
    empty_denominator_policy = [
        clean(row.get("query_id")) for row in reviewed_rows if not clean(row.get("user_denominator_policy"))
    ]
    empty_issue_tags = [
        clean(row.get("query_id")) for row in reviewed_rows if not clean(row.get("user_issue_tags"))
    ]
    finder_queries = [
        clean(row.get("query_id")) for row in original_rows if "찾아줘" in clean(row.get("query"))
    ]
    long_query_ids = [
        clean(row.get("query_id")) for row in original_rows if len(clean(row.get("query"))) >= 80
    ]

    user_gold_decision_counts = Counter(clean(row.get("user_gold_decision")) for row in reviewed_rows)
    expected_answer_issue_count = user_gold_decision_counts.get("REVISE_EXPECTED_ANSWER", 0)
    expected_evidence_issue_count = (
        user_gold_decision_counts.get("REVISE_EXPECTED_EVIDENCE", 0)
        + sum(
            1
            for row in reviewed_rows
            if clean(row.get("user_answerability_label")) == "REVISE_EXPECTED_EVIDENCE"
        )
    )

    report = {
        "run_id": utc_run_id("rag_text_namu_v1_review_audit"),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_text_namu_v1_review_audit_v1",
        "status": "AUDIT_ONLY_NOT_FINAL_GOLD",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "official_denominator_changed": False,
        "inputs": {
            "reviewed_pack": {
                "path": normalise_path(reviewed_path),
                "sha256": sha256_file(reviewed_path),
            },
            "original_candidate_csv": {
                "path": normalise_path(original_path),
                "sha256": sha256_file(original_path),
            },
        },
        "row_counts": {
            "reviewed": len(reviewed_rows),
            "original": len(original_rows),
            "equal": len(reviewed_rows) == len(original_rows),
        },
        "query_id_checks": {
            "reviewed_unique": not duplicate_reviewed,
            "original_unique": not duplicate_original,
            "set_equal": reviewed_id_set == original_id_set,
            "duplicate_reviewed": duplicate_reviewed,
            "duplicate_original": duplicate_original,
            "missing_from_reviewed": sorted(original_id_set - reviewed_id_set),
            "missing_from_original": sorted(reviewed_id_set - original_id_set),
        },
        "column_presence": {
            "reviewed_missing_required_columns": [
                column for column in V1_REVIEW_REQUIRED_COLUMNS if column not in reviewed_columns
            ],
            "original_missing_required_columns": [
                column for column in V1_ORIGINAL_REQUIRED_COLUMNS if column not in original_columns
            ],
        },
        "raw_human_label_vocabularies": raw_vocabs,
        "invalid_label_placements": {
            "action_label_in_user_answerability_label_count": len(action_in_answerability),
            "action_label_in_user_answerability_label_query_ids": action_in_answerability,
            "answerability_label_in_user_gold_decision_count": len(answerability_in_gold_policy),
            "answerability_label_in_user_gold_decision_query_ids": answerability_in_gold_policy,
        },
        "empty_required_human_fields": {
            "user_relevance_label_empty_count": len(missing_user_relevance),
            "user_relevance_label_empty_query_ids": missing_user_relevance,
            "user_expected_evidence_policy_empty_count": len(empty_expected_evidence_policy),
            "user_denominator_policy_empty_count": len(empty_denominator_policy),
            "user_issue_tags_empty_count": len(empty_issue_tags),
        },
        "query_quality_scan": {
            "document_finder_query_count": len(finder_queries),
            "document_finder_query_ids": finder_queries,
            "long_query_count": len(long_query_ids),
            "long_query_ids": long_query_ids,
            "finding": (
                "v1 query surfaces include many document-finder or copied-evidence style queries; "
                "v2 rewrites these manually instead of coercing labels."
            ),
        },
        "classification": {
            "primary_suspected_issue": "human-review-column issue",
            "review_column_corruption_likely": bool(action_in_answerability)
            and len(empty_denominator_policy) == len(reviewed_rows),
            "query_quality_issue_count": len(set(finder_queries + long_query_ids)),
            "expected_answer_issue_count_from_user_gold_decision": expected_answer_issue_count,
            "expected_evidence_issue_count_from_user_signals": expected_evidence_issue_count,
            "human_review_column_issue_count": len(
                set(
                    action_in_answerability
                    + answerability_in_gold_policy
                    + missing_user_relevance
                    + empty_expected_evidence_policy
                    + empty_denominator_policy
                    + empty_issue_tags
                )
            ),
            "denominator_policy_issue_count": len(empty_denominator_policy),
        },
        "decision": (
            "Preserve v1 as diagnostic/audit material only. Do not integrate it as final official TEXT gold "
            "because human-review columns contain invalid placements and denominator fields are empty."
        ),
    }
    return report


def build_v2_candidates(
    *,
    manual_candidates: list[dict[str, str]],
    original_by_id: Mapping[str, Mapping[str, str]],
    pages: Mapping[str, Mapping[str, Any]],
    chunks: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, candidate in enumerate(manual_candidates, start=1):
        source_id = candidate["source_query_id"]
        source = original_by_id[source_id]
        expected_page_ids = source_expected_page_ids(source)
        expected_chunk_ids = source_expected_chunk_ids(source)
        expected_section_ids = source_expected_section_ids(source, chunks, expected_chunk_ids)
        section_paths = unique(
            section_path_for_chunk(chunks.get(chunk_id, {})) or source_section_path(source)
            for chunk_id in expected_chunk_ids
            if chunks.get(chunk_id)
        )
        source_urls = unique(
            clean((chunks.get(chunk_id, {}).get("metadata") or {}).get("source_url"))
            for chunk_id in expected_chunk_ids
            if chunks.get(chunk_id)
        )
        page_titles = unique(
            decoded_source_url_title(source_url)
            for source_url in source_urls
            if decoded_source_url_title(source_url)
        )
        if not page_titles:
            page_titles = unique(
                clean(pages.get(page_id, {}).get("page_title") or pages.get(page_id, {}).get("display_title"))
                for page_id in expected_page_ids
            )
        chunk_texts = [
            clean(chunks.get(chunk_id, {}).get("chunk_text"))
            for chunk_id in expected_chunk_ids
            if chunks.get(chunk_id)
        ]
        chunk_text_hashes = unique(sha256_text(text) for text in chunk_texts if text)
        source_evidence_quote = source_evidence_excerpt(first_non_empty(chunk_texts))
        source_artifact = candidate.get("source_artifact") or SOURCE_ORIGINAL_GOLD
        source_label_status = infer_source_label_status(source)
        source_locator = "; ".join(
            part
            for part in [
                f"source_query_id={source_id}",
                f"source_artifact={source_artifact}",
                "source_namespace=TEXT_NAMU_V4",
                f"page_id={join_ids(expected_page_ids)}",
                f"section_id={join_ids(expected_section_ids)}",
                f"chunk_id={join_ids(expected_chunk_ids)}",
                f"section_path={join_ids(section_paths)}" if section_paths else "",
                f"source_url={join_ids(source_urls)}" if source_urls else "",
                f"chunk_text_sha256={join_ids(chunk_text_hashes)}" if chunk_text_hashes else "",
            ]
            if part
        )
        default_policy = (
            "DIAGNOSTIC_ONLY_DEFAULT"
            if candidate["bucket"] == "abstain_not_answerable_diagnostic"
            else "OFFICIAL_REVIEW_CANDIDATE"
        )
        rows.append(
            {
                "query_id": f"text_namu_v2_{index:04d}",
                "track": "TEXT",
                "bucket": candidate["bucket"],
                "query": candidate["query"],
                "expected_answer_text": candidate["expected_answer_text"],
                "must_contain_terms": candidate["must_contain_terms"],
                "expected_document_ids": join_ids(expected_page_ids),
                "expected_page_ids": join_ids(expected_page_ids),
                "expected_section_ids": join_ids(expected_section_ids),
                "expected_chunk_ids": join_ids(expected_chunk_ids),
                "expected_page_title": join_ids(page_titles),
                "expected_section_path": join_ids(section_paths),
                "source_url": join_ids(source_urls),
                "chunk_text_sha256": join_ids(chunk_text_hashes),
                "source_evidence_quote": source_evidence_quote,
                "answer_type": candidate["answer_type"],
                "allowed_abstain": candidate["allowed_abstain"],
                "source_dataset": SOURCE_DATASET,
                "source_original_gold": source_artifact,
                "source_query_id": source_id,
                "source_label_status": source_label_status,
                "source_locator": source_locator,
                "candidate_default_policy": default_policy,
                "generation_notes": (
                    candidate["generation_notes"]
                    + f"; source_label_status={source_label_status}; "
                    + f"source_answer_type={clean(source.get('answer_type') or source.get('query_type'))}"
                ),
            }
        )
    return rows


def validate_v2_candidates(
    rows: list[dict[str, str]],
    *,
    pages: Mapping[str, Mapping[str, Any]],
    chunks: Mapping[str, Mapping[str, Any]],
    expected_row_count: int | None = TARGET_ROW_COUNT,
) -> dict[str, Any]:
    row_errors: dict[str, list[str]] = defaultdict(list)
    row_warnings: dict[str, list[str]] = defaultdict(list)

    if expected_row_count is not None and len(rows) != expected_row_count:
        row_errors["__dataset__"].append(f"row count must be {expected_row_count}, got {len(rows)}")

    query_ids = [clean(row.get("query_id")) for row in rows]
    duplicate_query_ids = sorted(q for q, count in Counter(query_ids).items() if q and count > 1)
    for query_id in duplicate_query_ids:
        row_errors[query_id].append("duplicate query_id")

    duplicate_queries = duplicate_values(rows, "query")
    duplicate_chunk_ids = duplicate_values(rows, "expected_chunk_ids")
    duplicate_source_urls = duplicate_values(rows, "source_url")
    for value in duplicate_queries:
        for query_id in ids_for_value(rows, "query", value):
            row_errors[query_id].append(f"duplicate query text: {value}")
    for value in duplicate_chunk_ids:
        for query_id in ids_for_value(rows, "expected_chunk_ids", value):
            row_errors[query_id].append(f"duplicate expected_chunk_ids: {value}")
    for value in duplicate_source_urls:
        for query_id in ids_for_value(rows, "source_url", value):
            row_errors[query_id].append(f"duplicate source_url without documented exception: {value}")

    for row in rows:
        query_id = clean(row.get("query_id")) or "<missing>"
        if not re.fullmatch(r"text_namu_v2_\d{4}", query_id):
            row_errors[query_id].append("query_id must match text_namu_v2_####")
        for column in CANDIDATE_FIELDNAMES:
            if not clean(row.get(column)):
                row_errors[query_id].append(f"{column} is required")
        if clean(row.get("track")) != "TEXT":
            row_errors[query_id].append("track must be TEXT")
        bucket = clean(row.get("bucket"))
        answer_type = clean(row.get("answer_type"))
        default_policy = clean(row.get("candidate_default_policy"))
        allowed_abstain = clean(row.get("allowed_abstain")).lower()
        if bucket not in V2_BUCKETS:
            row_errors[query_id].append("bucket is not allowed")
        if answer_type not in V2_ANSWER_TYPES:
            row_errors[query_id].append("answer_type is not allowed")
        if bucket in BUCKET_ANSWER_TYPE and answer_type != BUCKET_ANSWER_TYPE[bucket]:
            row_errors[query_id].append(
                f"bucket {bucket} requires answer_type {BUCKET_ANSWER_TYPE[bucket]}, got {answer_type}"
            )
        if allowed_abstain not in {"true", "false"}:
            row_errors[query_id].append("allowed_abstain must be true or false")
        if default_policy not in {"OFFICIAL_REVIEW_CANDIDATE", "DIAGNOSTIC_ONLY_DEFAULT"}:
            row_errors[query_id].append("candidate_default_policy is not allowed")
        if bucket == "abstain_not_answerable_diagnostic":
            if default_policy != "DIAGNOSTIC_ONLY_DEFAULT":
                row_errors[query_id].append("diagnostic abstain bucket must use DIAGNOSTIC_ONLY_DEFAULT")
            if answer_type != "abstain":
                row_errors[query_id].append("diagnostic abstain bucket must use answer_type=abstain")
            if allowed_abstain != "true":
                row_errors[query_id].append("diagnostic abstain bucket must use allowed_abstain=true")
        else:
            if default_policy != "OFFICIAL_REVIEW_CANDIDATE":
                row_errors[query_id].append("answerable bucket must use OFFICIAL_REVIEW_CANDIDATE")
            if allowed_abstain != "false":
                row_errors[query_id].append("official review candidate must use allowed_abstain=false")
        if not clean(row.get("query")):
            row_errors[query_id].append("query is required")
        if not clean(row.get("expected_answer_text")):
            row_errors[query_id].append("expected_answer_text is required")
        must_terms = split_ids(row.get("must_contain_terms"))
        if allowed_abstain != "true" and not must_terms:
            row_errors[query_id].append("answerable row requires must_contain_terms")
        for term in must_terms:
            if term not in clean(row.get("expected_answer_text")):
                row_errors[query_id].append(
                    f"must_contain_terms item is not literal in expected_answer_text: {term}"
                )
        if any(token in clean(row.get("source_dataset")).lower() for token in ["xlsx", "pdf", "elec", "lh"]):
            row_errors[query_id].append("source_dataset leaks non-TEXT namespace")
        decoded_titles = unique(decoded_source_url_title(url) for url in split_ids(row.get("source_url")))
        if decoded_titles and clean(row.get("expected_page_title")) != join_ids(decoded_titles):
            row_errors[query_id].append(
                "expected_page_title must equal decoded source_url title; "
                f"expected {join_ids(decoded_titles)}, got {clean(row.get('expected_page_title'))}"
            )
        locator_errors = validate_locator(row, pages=pages, chunks=chunks)
        row_errors[query_id].extend(locator_errors)
        for page_id in split_ids(row.get("expected_page_ids")):
            if page_id not in pages:
                row_errors[query_id].append(f"expected_page_id not found: {page_id}")
        for chunk_id in split_ids(row.get("expected_chunk_ids")):
            chunk = chunks.get(chunk_id)
            if chunk is None:
                row_errors[query_id].append(f"expected_chunk_id not found: {chunk_id}")
                continue
            chunk_doc_id = clean(chunk.get("doc_id") or chunk.get("page_id"))
            expected_page_ids = split_ids(row.get("expected_page_ids"))
            if expected_page_ids and chunk_doc_id not in expected_page_ids:
                row_errors[query_id].append(
                    f"chunk {chunk_id} doc_id={chunk_doc_id} outside expected_page_ids={expected_page_ids}"
                )
            if is_empty(chunk.get("chunk_text")):
                row_errors[query_id].append(f"chunk {chunk_id} has empty chunk_text")
        time_terms = sensitive_terms_in_text(clean(row.get("query")) + " " + clean(row.get("expected_answer_text")))
        if time_terms:
            row_warnings[query_id].append("time-sensitive wording present: " + ", ".join(time_terms))
        if clean(row.get("source_label_status")) == "needs_review":
            row_warnings[query_id].append("source_label_status=needs_review requires human attention")

    expected_ids = [f"text_namu_v2_{index:04d}" for index in range(1, len(rows) + 1)]
    if query_ids != expected_ids:
        row_errors["__dataset__"].append("query_id values must be sequential without gaps")
    bucket_counts = dict(sorted(Counter(row["bucket"] for row in rows).items()))
    answer_type_counts = dict(sorted(Counter(row["answer_type"] for row in rows).items()))
    policy_counts = dict(sorted(Counter(row["candidate_default_policy"] for row in rows).items()))
    source_label_status_counts = dict(sorted(Counter(row.get("source_label_status", "") for row in rows).items()))
    source_label_status_needs_review_ids = [
        row["query_id"] for row in rows if clean(row.get("source_label_status")) == "needs_review"
    ]
    target_counts_match = bucket_counts == TARGET_BUCKET_COUNTS
    if expected_row_count is None:
        target_counts_match = True
    elif not target_counts_match:
        row_errors["__dataset__"].append(
            f"bucket counts must match target {TARGET_BUCKET_COUNTS}, got {bucket_counts}"
        )
    nonempty_row_errors = {key: errors for key, errors in row_errors.items() if errors}
    status = "PASSED" if not nonempty_row_errors else "FAILED"
    return {
        "status": status,
        "row_count": len(rows),
        "bucket_counts": bucket_counts,
        "answer_type_counts": answer_type_counts,
        "target_bucket_counts": TARGET_BUCKET_COUNTS,
        "target_counts_match": target_counts_match,
        "duplicate_query_ids": duplicate_query_ids,
        "duplicate_queries": duplicate_queries,
        "duplicate_expected_chunk_ids": duplicate_chunk_ids,
        "duplicate_source_urls": duplicate_source_urls,
        "candidate_default_policy_counts": policy_counts,
        "source_label_status_counts": source_label_status_counts,
        "source_label_status_needs_review_ids": source_label_status_needs_review_ids,
        "row_errors": nonempty_row_errors,
        "row_warnings": {key: warnings for key, warnings in row_warnings.items() if warnings},
    }


def build_v2_review_pack(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        rows.append(
            {
                **candidate,
                "user_final_gold_policy": "NEEDS_REVIEW",
                "user_answerability_label": "",
                "user_relevance_label": "",
                "user_expected_answer_override": "",
                "user_expected_evidence_override": "",
                "user_review_notes": "",
            }
        )
    return rows


def validate_v2_review_pack(
    rows: list[dict[str, str]],
    *,
    columns: list[str],
    pages: Mapping[str, Mapping[str, Any]],
    chunks: Mapping[str, Mapping[str, Any]],
    require_reviewed: bool = False,
    expected_row_count: int | None = None,
) -> dict[str, Any]:
    missing_columns = [column for column in REVIEW_PACK_FIELDNAMES if column not in columns]
    row_errors: dict[str, list[str]] = defaultdict(list)
    row_warnings: dict[str, list[str]] = defaultdict(list)
    derived_policy_counts: Counter[str] = Counter()
    final_policy_counts: Counter[str] = Counter()
    answerability_counts: Counter[str] = Counter()
    relevance_counts: Counter[str] = Counter()

    if missing_columns:
        row_errors["__dataset__"].append("missing required columns: " + ", ".join(missing_columns))

    candidate_validation = validate_v2_candidates(
        rows,
        pages=pages,
        chunks=chunks,
        expected_row_count=expected_row_count,
    )
    for key, errors in candidate_validation["row_errors"].items():
        row_errors[key].extend(errors)
    for key, warnings in candidate_validation["row_warnings"].items():
        row_warnings[key].extend(warnings)

    query_ids = [clean(row.get("query_id")) for row in rows]
    duplicate_query_ids = sorted(q for q, count in Counter(query_ids).items() if q and count > 1)
    for query_id in duplicate_query_ids:
        row_errors[query_id].append("duplicate query_id")

    for index, row in enumerate(rows, start=2):
        query_id = clean(row.get("query_id")) or f"<row:{index}>"
        final_policy = clean(row.get("user_final_gold_policy"))
        answerability = clean(row.get("user_answerability_label"))
        relevance = clean(row.get("user_relevance_label"))
        final_policy_counts[final_policy or "<empty>"] += 1
        answerability_counts[answerability or "<empty>"] += 1
        relevance_counts[relevance or "<empty>"] += 1

        if final_policy and final_policy not in FINAL_GOLD_POLICIES:
            row_errors[query_id].append("user_final_gold_policy has invalid vocabulary")
        if answerability and answerability not in ANSWERABILITY_LABELS:
            row_errors[query_id].append("user_answerability_label has invalid vocabulary")
        if relevance and relevance not in RELEVANCE_LABELS:
            row_errors[query_id].append("user_relevance_label has invalid vocabulary")
        if answerability in OLD_ACTION_LABELS or answerability in FINAL_GOLD_POLICIES:
            row_errors[query_id].append("action/final-policy label is inside answerability column")
        if final_policy in ANSWERABILITY_LABELS:
            row_errors[query_id].append("answerability label is inside final-gold-policy column")
        if relevance in OLD_ACTION_LABELS or relevance in FINAL_GOLD_POLICIES:
            row_errors[query_id].append("action/final-policy label is inside relevance column")

        if require_reviewed and final_policy == "NEEDS_REVIEW":
            row_errors[query_id].append("reviewed mode does not allow NEEDS_REVIEW")
        if require_reviewed and not final_policy:
            row_errors[query_id].append("reviewed mode requires user_final_gold_policy")
        if final_policy == "KEEP_OFFICIAL":
            if not answerability:
                row_errors[query_id].append("official row requires user_answerability_label")
            if not relevance:
                row_errors[query_id].append("official row requires user_relevance_label")
        effective_answer = clean(row.get("user_expected_answer_override")) or clean(row.get("expected_answer_text"))
        if final_policy == "KEEP_OFFICIAL" and answerability in {"ANSWERABLE", "PARTIALLY_ANSWERABLE"}:
            if not effective_answer:
                row_errors[query_id].append("answerable official row requires expected answer text")
            if not split_ids(row.get("must_contain_terms")):
                row_errors[query_id].append("answerable official row requires must_contain_terms")
        for term in split_ids(row.get("must_contain_terms")):
            if term not in effective_answer:
                row_errors[query_id].append(
                    f"must_contain_terms item is not literal in effective expected answer: {term}"
                )

        locator_errors = validate_locator(row, pages=pages, chunks=chunks)
        row_errors[query_id].extend(locator_errors)

        denominator_policy = derive_denominator_policy(
            final_policy=final_policy,
            answerability=answerability,
            relevance=relevance,
            allowed_abstain=clean(row.get("allowed_abstain")).lower(),
        )
        derived_policy_counts[denominator_policy] += 1
        if denominator_policy == "STRICT_OFFICIAL_POSITIVE_DENOMINATOR" and relevance in {"PARTIAL", "AMBIGUOUS"}:
            row_errors[query_id].append("ambiguous/partial relevance cannot enter official denominator")
        if denominator_policy == "STRICT_OFFICIAL_POSITIVE_DENOMINATOR" and not answerability:
            row_errors[query_id].append("missing answerability cannot enter official denominator")
        if denominator_policy == "STRICT_OFFICIAL_POSITIVE_DENOMINATOR" and answerability == "NOT_ANSWERABLE":
            row_errors[query_id].append("NOT_ANSWERABLE cannot enter positive official denominator")
        if final_policy == "KEEP_OFFICIAL" and denominator_policy != "STRICT_OFFICIAL_POSITIVE_DENOMINATOR":
            row_warnings[query_id].append(
                f"KEEP_OFFICIAL row derives {denominator_policy}, not strict positive denominator"
            )

    ok = not {key: errors for key, errors in row_errors.items() if errors}
    return {
        "ok": ok,
        "row_count": len(rows),
        "missing_required_columns": missing_columns,
        "duplicate_query_ids": duplicate_query_ids,
        "duplicate_queries": candidate_validation["duplicate_queries"],
        "duplicate_expected_chunk_ids": candidate_validation["duplicate_expected_chunk_ids"],
        "duplicate_source_urls": candidate_validation["duplicate_source_urls"],
        "bucket_counts": candidate_validation["bucket_counts"],
        "answer_type_counts": candidate_validation["answer_type_counts"],
        "candidate_default_policy_counts": candidate_validation["candidate_default_policy_counts"],
        "target_bucket_counts": candidate_validation["target_bucket_counts"],
        "target_counts_match": candidate_validation["target_counts_match"],
        "source_label_status_counts": candidate_validation["source_label_status_counts"],
        "source_label_status_needs_review_ids": candidate_validation["source_label_status_needs_review_ids"],
        "final_policy_counts": dict(sorted(final_policy_counts.items())),
        "answerability_counts": dict(sorted(answerability_counts.items())),
        "relevance_counts": dict(sorted(relevance_counts.items())),
        "derived_policy_counts": dict(sorted(derived_policy_counts.items())),
        "row_errors": {key: errors for key, errors in row_errors.items() if errors},
        "row_warnings": {key: warnings for key, warnings in row_warnings.items() if warnings},
    }


def add_candidate_review_pack_equality_validation(
    validation: dict[str, Any],
    *,
    candidate_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
) -> dict[str, Any]:
    updated = dict(validation)
    row_errors = defaultdict(list)
    for key, errors in validation.get("row_errors", {}).items():
        row_errors[key].extend(errors)

    candidate_by_id = {clean(row.get("query_id")): row for row in candidate_rows}
    review_by_id = {clean(row.get("query_id")): row for row in review_rows}
    missing_from_review = sorted(set(candidate_by_id) - set(review_by_id))
    extra_in_review = sorted(set(review_by_id) - set(candidate_by_id))
    if len(candidate_rows) != len(review_rows):
        row_errors["__dataset__"].append(
            f"candidate/review row count mismatch: {len(candidate_rows)} vs {len(review_rows)}"
        )
    for query_id in missing_from_review:
        row_errors[query_id].append("candidate row missing from review pack")
    for query_id in extra_in_review:
        row_errors[query_id].append("review pack row has no candidate row")

    compared = 0
    mismatches = 0
    for query_id in sorted(set(candidate_by_id) & set(review_by_id)):
        candidate = candidate_by_id[query_id]
        review = review_by_id[query_id]
        for column in CANDIDATE_FIELDNAMES:
            compared += 1
            if clean(candidate.get(column)) != clean(review.get(column)):
                mismatches += 1
                row_errors[query_id].append(
                    f"review pack candidate column mismatch for {column}"
                )

    nonempty_errors = {key: errors for key, errors in row_errors.items() if errors}
    updated["row_errors"] = nonempty_errors
    updated["ok"] = not nonempty_errors
    updated["candidate_column_equality"] = {
        "status": "PASSED" if mismatches == 0 and not missing_from_review and not extra_in_review else "FAILED",
        "compared_cell_count": compared,
        "mismatch_count": mismatches,
        "missing_from_review_pack": missing_from_review,
        "extra_in_review_pack": extra_in_review,
    }
    return updated


def validate_locator(
    row: Mapping[str, str],
    *,
    pages: Mapping[str, Mapping[str, Any]],
    chunks: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    expected_page_ids = split_ids(row.get("expected_page_ids"))
    expected_section_ids = split_ids(row.get("expected_section_ids"))
    expected_chunk_ids = split_ids(row.get("expected_chunk_ids"))
    expected_section_paths = split_ids(row.get("expected_section_path"))
    source_urls = split_ids(row.get("source_url"))
    expected_hashes = split_ids(row.get("chunk_text_sha256"))
    locator = parse_source_locator(row.get("source_locator"))

    locator_checks = {
        "source_namespace": "TEXT_NAMU_V4",
        "page_id": join_ids(expected_page_ids),
        "section_id": join_ids(expected_section_ids),
        "chunk_id": join_ids(expected_chunk_ids),
        "section_path": join_ids(expected_section_paths),
        "source_url": join_ids(source_urls),
        "chunk_text_sha256": join_ids(expected_hashes),
    }
    for key, expected in locator_checks.items():
        actual = clean(locator.get(key))
        if expected and actual != expected:
            errors.append(f"source_locator {key} mismatch: expected {expected}, got {actual}")
    if clean(row.get("source_query_id")) and clean(locator.get("source_query_id")) != clean(row.get("source_query_id")):
        errors.append("source_locator source_query_id mismatch")

    for page_id in expected_page_ids:
        if page_id not in pages:
            errors.append(f"expected_page_id not found in pages_v4: {page_id}")
    chunk_section_ids: set[str] = set()
    chunk_section_paths: list[str] = []
    chunk_source_urls: list[str] = []
    chunk_hashes: list[str] = []
    chunk_texts: list[str] = []
    for chunk_id in expected_chunk_ids:
        chunk = chunks.get(chunk_id)
        if chunk is None:
            errors.append(f"expected_chunk_id not found in rag_chunks: {chunk_id}")
            continue
        chunk_doc_id = clean(chunk.get("doc_id") or chunk.get("page_id"))
        if expected_page_ids and chunk_doc_id not in expected_page_ids:
            errors.append(f"chunk {chunk_id} doc_id={chunk_doc_id} outside expected_page_ids={expected_page_ids}")
        section_id = clean(chunk.get("section_id"))
        if section_id:
            chunk_section_ids.add(section_id)
        if is_empty(chunk.get("chunk_text")):
            errors.append(f"chunk {chunk_id} has empty chunk_text")
        chunk_section_paths.append(section_path_for_chunk(chunk))
        chunk_url = clean((chunk.get("metadata") or {}).get("source_url"))
        if chunk_url:
            chunk_source_urls.append(chunk_url)
        chunk_text = clean(chunk.get("chunk_text"))
        if chunk_text:
            chunk_texts.append(chunk_text)
            chunk_hashes.append(sha256_text(chunk_text))
    for section_id in expected_section_ids:
        if section_id not in chunk_section_ids:
            errors.append(f"expected_section_id not found on expected chunks: {section_id}")
    if expected_section_paths and join_ids(unique(chunk_section_paths)) != join_ids(expected_section_paths):
        errors.append(
            "expected_section_path does not match referenced chunks: "
            f"{join_ids(unique(chunk_section_paths))}"
        )
    if source_urls and join_ids(unique(chunk_source_urls)) != join_ids(source_urls):
        errors.append(f"source_url does not match referenced chunks: {join_ids(unique(chunk_source_urls))}")
    if expected_hashes and join_ids(unique(chunk_hashes)) != join_ids(expected_hashes):
        errors.append(f"chunk_text_sha256 does not match referenced chunks: {join_ids(unique(chunk_hashes))}")
    quote = clean(row.get("source_evidence_quote"))
    if quote:
        if not any(quote in chunk_text for chunk_text in chunk_texts):
            errors.append("source_evidence_quote is not a literal excerpt of referenced chunk text")
        if quote.endswith("...") and not any(quote in chunk_text for chunk_text in chunk_texts):
            errors.append("source_evidence_quote appears synthetically clipped")
    else:
        errors.append("source_evidence_quote is required")
    if not expected_page_ids and not expected_chunk_ids:
        errors.append("expected evidence locator requires page or chunk id")
    return errors


def derive_denominator_policy(
    *,
    final_policy: str,
    answerability: str,
    relevance: str,
    allowed_abstain: str,
) -> str:
    if final_policy == "DROP":
        return "EXCLUDED_DROP"
    if final_policy == "DIAGNOSTIC_ONLY":
        return "DIAGNOSTIC_ONLY_EXCLUDED"
    if final_policy == "NEEDS_REVIEW" or not final_policy:
        return "PENDING_REVIEW_EXCLUDED"
    if final_policy != "KEEP_OFFICIAL":
        return "INVALID_POLICY_EXCLUDED"
    if relevance != "RELEVANT":
        return "DIAGNOSTIC_ONLY_RELEVANCE_NOT_STRICT"
    if answerability == "ANSWERABLE" and allowed_abstain != "true":
        return "STRICT_OFFICIAL_POSITIVE_DENOMINATOR"
    if answerability == "PARTIALLY_ANSWERABLE":
        return "DIAGNOSTIC_ONLY_PARTIAL_UNSUPPORTED"
    if answerability == "NOT_ANSWERABLE":
        return "DIAGNOSTIC_ONLY_NOT_ANSWERABLE_NO_ABSTAIN_DENOMINATOR"
    if answerability == "AMBIGUOUS" or not answerability:
        return "DIAGNOSTIC_ONLY_ANSWERABILITY_NOT_STRICT"
    return "INVALID_ANSWERABILITY_EXCLUDED"


def build_validation_report(
    *,
    review_pack: Path,
    candidate_csv: Path,
    validation: dict[str, Any],
    candidate_count: int,
    require_reviewed: bool,
) -> dict[str, Any]:
    status = "PASSED" if validation["ok"] else "FAILED"
    return {
        "run_id": utc_run_id("rag_text_namu_v2_review_validation"),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_text_namu_v2_review_pack_validation_v1",
        "status": status,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "official_denominator_changed": False,
        "review_pack": normalise_path(review_pack),
        "candidate_csv": normalise_path(candidate_csv),
        "candidate_count": candidate_count,
        "require_reviewed": require_reviewed,
        "human_columns": HUMAN_REVIEW_COLUMNS,
        "allowed_vocabularies": {
            "user_final_gold_policy": sorted(FINAL_GOLD_POLICIES),
            "user_answerability_label": sorted(ANSWERABILITY_LABELS),
            "user_relevance_label": sorted(RELEVANCE_LABELS),
        },
        "derived_policy_counts": validation["derived_policy_counts"],
        "validation": validation,
        "denominator_policy": conservative_denominator_policy_description(),
    }


def summarize_candidates(rows: list[dict[str, str]]) -> dict[str, Any]:
    source_label_status_counts = dict(sorted(Counter(row.get("source_label_status", "") for row in rows).items()))
    return {
        "row_count": len(rows),
        "bucket_counts": dict(sorted(Counter(row["bucket"] for row in rows).items())),
        "answer_type_counts": dict(sorted(Counter(row["answer_type"] for row in rows).items())),
        "allowed_abstain_counts": dict(sorted(Counter(row["allowed_abstain"] for row in rows).items())),
        "candidate_default_policy_counts": dict(
            sorted(Counter(row["candidate_default_policy"] for row in rows).items())
        ),
        "source_dataset_counts": dict(sorted(Counter(row["source_dataset"] for row in rows).items())),
        "source_original_gold_counts": dict(sorted(Counter(row["source_original_gold"] for row in rows).items())),
        "source_label_status_counts": source_label_status_counts,
        "source_label_status_needs_review_ids": [
            row["query_id"] for row in rows if clean(row.get("source_label_status")) == "needs_review"
        ],
        "diagnostic_only_ids": [
            row["query_id"] for row in rows if row["candidate_default_policy"] == "DIAGNOSTIC_ONLY_DEFAULT"
        ],
    }


def summarize_existing_artifact_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "bucket_counts": dict(sorted(Counter(clean(row.get("bucket")) for row in rows if clean(row.get("bucket"))).items())),
        "answer_type_counts": dict(
            sorted(Counter(clean(row.get("answer_type")) for row in rows if clean(row.get("answer_type"))).items())
        ),
        "candidate_default_policy_counts": dict(
            sorted(
                Counter(
                    clean(row.get("candidate_default_policy"))
                    for row in rows
                    if clean(row.get("candidate_default_policy"))
                ).items()
            )
        ),
    }


def summarize_baseline_candidate_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    if len(rows) == 50:
        return summarize_existing_artifact_rows(rows)
    return {
        "row_count": 50,
        "bucket_counts": dict(INITIAL_50_BUCKET_COUNTS),
        "answer_type_counts": dict(
            sorted(
                Counter(
                    BUCKET_ANSWER_TYPE[bucket]
                    for bucket, count in INITIAL_50_BUCKET_COUNTS.items()
                    for _ in range(count)
                ).items()
            )
        ),
        "candidate_default_policy_counts": {
            "DIAGNOSTIC_ONLY_DEFAULT": INITIAL_50_BUCKET_COUNTS["abstain_not_answerable_diagnostic"],
            "OFFICIAL_REVIEW_CANDIDATE": 50 - INITIAL_50_BUCKET_COUNTS["abstain_not_answerable_diagnostic"],
        },
        "source": "baseline_50_before_cleanup_expansion",
    }


def cleanup_change_summary(previous_rows: list[dict[str, str]]) -> dict[str, Any]:
    previous_by_id = {clean(row.get("query_id")): row for row in previous_rows}
    title_mismatch_ids = []
    clipped_quote_ids = []
    for query_id, row in previous_by_id.items():
        decoded = join_ids(unique(decoded_source_url_title(url) for url in split_ids(row.get("source_url"))))
        if decoded and clean(row.get("expected_page_title")) != decoded:
            title_mismatch_ids.append(query_id)
        quote = clean(row.get("source_evidence_quote"))
        if quote.endswith("..."):
            clipped_quote_ids.append(query_id)
    if len(previous_rows) != 50:
        title_mismatch_ids = sorted(KNOWN_PAGE_TITLE_NORMALIZATION_IDS)
        clipped_quote_ids = sorted(KNOWN_SYNTHETIC_CLIPPED_QUOTE_IDS)
    return {
        "page_title_normalization_count": len(title_mismatch_ids),
        "page_title_normalization_ids": sorted(title_mismatch_ids),
        "known_page_title_normalization_ids": sorted(KNOWN_PAGE_TITLE_NORMALIZATION_IDS),
        "must_contain_fix_count": len(KNOWN_MUST_CONTAIN_FIX_IDS & previous_by_id.keys()),
        "must_contain_fix_ids": sorted(KNOWN_MUST_CONTAIN_FIX_IDS & previous_by_id.keys()),
        "time_sensitive_query_rewrite_count": len(KNOWN_TIME_SENSITIVE_QUERY_FIX_IDS & previous_by_id.keys()),
        "time_sensitive_query_rewrite_ids": sorted(KNOWN_TIME_SENSITIVE_QUERY_FIX_IDS & previous_by_id.keys()),
        "evidence_quote_unclipping_count": len(clipped_quote_ids),
        "evidence_quote_unclipping_ids": sorted(clipped_quote_ids),
        "policy_generation_note_fix_count": len(KNOWN_POLICY_NOTE_FIX_IDS & previous_by_id.keys()),
        "policy_generation_note_fix_ids": sorted(KNOWN_POLICY_NOTE_FIX_IDS & previous_by_id.keys()),
    }


def conservative_denominator_policy_description() -> dict[str, Any]:
    return {
        "source": "official_denominator_registry.json if present; no Track B partial or abstain denominator support found",
        "strict_positive_rule": "KEEP_OFFICIAL + ANSWERABLE + RELEVANT + allowed_abstain=false",
        "partial_answerable": "diagnostic_only unless repo adds explicit partial denominator support",
        "partial_or_ambiguous_relevance": "diagnostic_only",
        "not_answerable": "excluded from positive denominator; diagnostic_only unless repo adds abstain denominator",
        "drop": "excluded",
        "needs_review": "pending and excluded",
        "user_denominator_policy_column": "not present in v2 review pack",
    }


def write_markdown_report(path: Path, summary: Mapping[str, Any], audit: Mapping[str, Any]) -> None:
    lines = [
        "# TEXT/NAMU v2 Gold Candidate Review Workflow",
        "",
        "## Status",
        "",
        "- Status: `diagnostic-only candidate workflow`.",
        "- v1 reviewed pack was not integrated as final official gold.",
        "- Official denominator registry and XLSX/PDF behavior were not changed.",
        "",
        "## v1 Audit Summary",
        "",
        f"- Reviewed rows: `{audit['row_counts']['reviewed']}`.",
        f"- Original rows: `{audit['row_counts']['original']}`.",
        f"- Query-id set equal: `{audit['query_id_checks']['set_equal']}`.",
        "- Primary suspected issue: `human-review-column issue`.",
        "- Evidence:",
        f"  - action labels in `user_answerability_label`: `{audit['invalid_label_placements']['action_label_in_user_answerability_label_count']}`.",
        f"  - empty `user_denominator_policy`: `{audit['empty_required_human_fields']['user_denominator_policy_empty_count']}`.",
        f"  - empty `user_expected_evidence_policy`: `{audit['empty_required_human_fields']['user_expected_evidence_policy_empty_count']}`.",
        f"  - empty `user_issue_tags`: `{audit['empty_required_human_fields']['user_issue_tags_empty_count']}`.",
        f"  - empty `user_relevance_label`: `{audit['empty_required_human_fields']['user_relevance_label_empty_count']}`.",
        "",
        "## v2 Generation",
        "",
        f"- Candidate CSV: `{summary['v2_paths']['candidate_csv']}`.",
        f"- Review pack CSV: `{summary['v2_paths']['review_pack_csv']}`.",
        "- Method: manually curated Korean query surfaces bound to existing namu-v4 `pages_v4.jsonl` and `rag_chunks.jsonl` locators.",
        "- Evidence locator fields include page id, section id, chunk id, source URL, chunk text SHA256, and a short source quote.",
        "- XLSX/PDF namespace leakage controls: source dataset is TEXT/NAMU only and locator validation resolves page/chunk ids in namu-v4 corpus.",
        "- `chunks_v4.jsonl` is not used because it is a separate chunk-id namespace from the active `rag_chunks.jsonl` retrieval path.",
        "",
        "## Counts",
        "",
        f"- Previous candidate rows: `{summary['previous_v2_candidate_summary']['row_count']}`.",
        f"- Current candidate rows: `{summary['v2_candidate_summary']['row_count']}`.",
        f"- Previous policy distribution: `{summary['previous_v2_candidate_summary']['candidate_default_policy_counts']}`.",
        f"- Current policy distribution: `{summary['v2_candidate_summary']['candidate_default_policy_counts']}`.",
        "",
        "### Buckets",
        "",
    ]
    for bucket, count in summary["v2_candidate_summary"]["bucket_counts"].items():
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(["", "### Answer Types", ""])
    for answer_type, count in summary["v2_candidate_summary"]["answer_type_counts"].items():
        lines.append(f"- `{answer_type}`: `{count}`")
    lines.extend(
        [
            "",
            "## Cleanup Changes",
            "",
            f"- Page title normalizations: `{summary['cleanup_changes_applied']['page_title_normalization_count']}`.",
            f"- Must-contain literal fixes: `{summary['cleanup_changes_applied']['must_contain_fix_count']}`.",
            f"- Time-sensitive query rewrites: `{summary['cleanup_changes_applied']['time_sensitive_query_rewrite_count']}`.",
            f"- Evidence quote unclippings: `{summary['cleanup_changes_applied']['evidence_quote_unclipping_count']}`.",
            f"- Policy/generation-note consistency fixes: `{summary['cleanup_changes_applied']['policy_generation_note_fix_count']}`.",
            "",
            "## Expansion Summary",
            "",
            f"- New rows: `{summary['expansion_summary']['new_row_count']}`.",
            f"- New rows by bucket: `{summary['expansion_summary']['new_rows_by_bucket']}`.",
            f"- New rows by policy: `{summary['expansion_summary']['new_rows_by_policy']}`.",
            f"- Target shortfall: `{summary['expansion_summary']['target_shortfall']}`.",
            "",
            "## Pre-Review Polish",
            "",
            "- `text_namu_v2_0080`: query wording clarified while preserving evidence and expected answer.",
            "- `text_namu_v2_0083`: replaced evaluation-summary-style source row with unused plot-memory scene recall `v4-silver-natural-0074`; bucket distribution remains unchanged.",
            "",
            "## Remaining Human Review Items",
            "",
            f"- `source_label_status=needs_review` rows: `{summary['v2_candidate_summary']['source_label_status_needs_review_ids']}`.",
            f"- Diagnostic-only rows: `{summary['v2_candidate_summary']['diagnostic_only_ids']}`.",
            "- Documented exceptions: none.",
        ]
    )
    lines.extend(
        [
            "",
            "## Review Pack Schema",
            "",
            "- Human-edit columns:",
            "  - `user_final_gold_policy`",
            "  - `user_answerability_label`",
            "  - `user_relevance_label`",
            "  - `user_expected_answer_override`",
            "  - `user_expected_evidence_override`",
            "  - `user_review_notes`",
            "- No user denominator-policy column is present. Denominator policy is derived by validation.",
            "",
            "## Denominator Policy",
            "",
            "- Strict official positive denominator: `KEEP_OFFICIAL + ANSWERABLE + RELEVANT + allowed_abstain=false`.",
            "- Partial answerability, partial or ambiguous relevance, and not-answerable rows remain diagnostic-only by default.",
            "- `NEEDS_REVIEW` rows are pending and excluded.",
            "- Abstain/not-answerable candidates are diagnostic-only by default because current Track B policy does not define an abstain denominator.",
            "",
            "## Validation",
            "",
            f"- Candidate validation: `{summary['candidate_validation']['status']}`.",
            f"- Review-pack validation: `{summary['v2_review_validation']['status']}`.",
            f"- Review-pack candidate-column equality: `{summary['v2_review_validation']['validation']['candidate_column_equality']['status']}`.",
            f"- Initial derived policy counts: `{summary['v2_review_validation']['derived_policy_counts']}`.",
            f"- Candidate warnings: `{len(summary['candidate_validation']['row_warnings'])}` rows.",
            f"- Validation report: `{summary['v2_paths']['validation_report']}`.",
            "",
            "Commands:",
            "",
            "```powershell",
            "python ai/scripts/rag_text_namu_v2_gold_review_workflow.py --mode build",
            "python ai/scripts/rag_text_namu_v2_gold_review_workflow.py --mode validate --review-pack ai/eval/review/text_namu_v2_gold_review/text_namu_v2_gold_review_pack.csv",
            "python -m pytest -q ai/tests/test_rag_text_namu_v2_gold_review_workflow.py ai/tests/test_rag_text_namu_v4_gold_validator.py",
            "```",
            "",
            "## Limitations",
            "",
        ]
    )
    for limitation in summary["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    write_text(path, "\n".join(lines))


def ids_needed_by_rows(rows: Iterable[Mapping[str, str]]) -> tuple[set[str], set[str]]:
    page_ids: set[str] = set()
    chunk_ids: set[str] = set()
    for row in rows:
        page_ids.update(source_expected_page_ids(row))
        chunk_ids.update(source_expected_chunk_ids(row))
    return page_ids, chunk_ids


def load_needed_corpus(
    corpus_dir: Path,
    needed_page_ids: set[str],
    needed_chunk_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    pages = load_needed_jsonl(
        corpus_dir / "pages_v4.jsonl",
        id_field="page_id",
        needed_ids=needed_page_ids,
    )
    chunks = load_needed_jsonl(
        corpus_dir / "rag_chunks.jsonl",
        id_field="chunk_id",
        needed_ids=needed_chunk_ids,
    )
    return pages, chunks


def load_needed_jsonl(path: Path, *, id_field: str, needed_ids: set[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    if not needed_ids:
        return found
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSON on line {line_no}: {exc}") from exc
            record_id = clean(record.get(id_field))
            if record_id in needed_ids:
                found[record_id] = dict(record)
                if len(found) == len(needed_ids):
                    break
    return found


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSON on line {line_no}: {exc}") from exc
            rows.append(dict(record))
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], *, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def first_non_empty(values: Iterable[str]) -> str:
    for value in values:
        cleaned = clean(value)
        if cleaned:
            return cleaned
    return ""


def source_expected_page_ids(source: Mapping[str, Any]) -> list[str]:
    return unique(
        split_ids(source.get("expected_page_ids"))
        or split_ids(source.get("expected_document_ids"))
        or split_ids(source.get("expected_doc_ids"))
        or split_ids(source.get("expected_doc_id"))
    )


def source_expected_chunk_ids(source: Mapping[str, Any]) -> list[str]:
    return unique(split_ids(source.get("expected_chunk_ids")) or split_ids(source.get("expected_chunk_id")))


def source_expected_section_ids(
    source: Mapping[str, Any],
    chunks: Mapping[str, Mapping[str, Any]],
    chunk_ids: list[str],
) -> list[str]:
    explicit = split_ids(source.get("expected_section_ids")) or split_ids(source.get("expected_section_id"))
    if explicit:
        return unique(explicit)
    return unique(clean(chunks.get(chunk_id, {}).get("section_id")) for chunk_id in chunk_ids)


def source_section_path(source: Mapping[str, Any]) -> str:
    return " > ".join(as_list(source.get("expected_section_path")))


def section_path_for_chunk(chunk: Mapping[str, Any]) -> str:
    return " > ".join(as_list(chunk.get("section_path")))


def decoded_source_url_title(source_url: str) -> str:
    source_url = clean(source_url)
    if "/w/" not in source_url:
        return ""
    suffix = source_url.split("/w/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    return clean(unquote(suffix).replace("_", " "))


def source_evidence_excerpt(chunk_text: str) -> str:
    text = clean(chunk_text)
    if len(text) <= 700:
        return text
    return text[:700].rstrip()


def infer_source_label_status(source: Mapping[str, Any]) -> str:
    explicit = clean(source.get("label_status"))
    if explicit:
        return explicit
    answerability = clean(source.get("answerability"))
    query_type = clean(source.get("query_type"))
    if answerability and answerability != "answerable":
        return "needs_review"
    if query_type in {"wrong_assumption", "ambiguous"}:
        return "needs_review"
    return "bound"


def parse_source_locator(value: Any) -> dict[str, str]:
    locator: dict[str, str] = {}
    for part in clean(value).split(";"):
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        locator[clean(key)] = clean(raw_value)
    return locator


def duplicate_values(rows: list[Mapping[str, str]], column: str) -> list[str]:
    values = [clean(row.get(column)) for row in rows if clean(row.get(column))]
    return sorted(value for value, count in Counter(values).items() if count > 1)


def ids_for_value(rows: list[Mapping[str, str]], column: str, value: str) -> list[str]:
    return [clean(row.get("query_id")) or "<missing>" for row in rows if clean(row.get(column)) == value]


def sensitive_terms_in_text(text: str) -> list[str]:
    return [term for term in TIME_SENSITIVE_TERMS if term in text]


def split_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean(part) for part in value if clean(part)]
    return [part.strip() for part in clean(value).split(";") if part.strip()]


def join_ids(values: Iterable[str]) -> str:
    return ";".join(value for value in values if value)


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    if isinstance(value, str):
        if ";" in value:
            return split_ids(value)
        return [value] if value else []
    return [clean(value)] if clean(value) else []


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = clean(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def is_empty(value: Any) -> bool:
    return not clean(value)


def normalise_path(path: Path | str) -> str:
    path = Path(path)
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_run_id(prefix: str = "run") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


if __name__ == "__main__":
    sys.exit(main())
