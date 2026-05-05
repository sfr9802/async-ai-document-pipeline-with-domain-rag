# A2 - Query Surface Review

## 목표

`QUERY_NATURALIZATION_DRIFT` 2건을 대상으로, query가 너무 모호해서 expected range를 놓치는지 검토하고 필요한 경우 reviewed positive CSV를 만듭니다.

## 대상

| Query id | 처리 방향 |
|---|---|
| `gq_xlsx_lookup_002` | 자연어 wording 후보 2-3개 작성 |
| `gq_auto_042` | 자연어 wording 후보 2-3개 작성 |

## 원칙

나쁜 방향:

```text
원래 seed를 그대로 복사한다.
셀 주소나 range를 query에 넣는다.
정답 파일명 또는 시트명을 과하게 노출한다.
hidden value를 query surface에 노출한다.
```

좋은 방향:

```text
사용자가 실제 검색창에 넣을 법한 짧은 한국어 질의를 유지한다.
핵심 엔티티, 지표명, 기간/지역/기관명 anchor를 한 번만 보강한다.
문서 구조 힌트는 최소화한다.
expected range를 직접 알려주지 않는다.
```

## 작업

1. A1 evidence에서 miss row의 top-k hit와 expected range를 확인합니다.
2. 기존 query, original query, query seed를 비교합니다.
3. 후보 query 2-3개를 작성합니다.
4. anchor audit를 실행해서 title/file/sheet/range leakage가 없는지 확인합니다.
5. `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv`를 별도 생성합니다.
6. candidate v1을 그대로 사용해 diagnostic-only vector eval을 재실행합니다.
7. before/after rank와 location match를 row별로 비교합니다.

## 산출물

| 파일 | 역할 |
|---|---|
| `reports/rag_xlsx_query_surface_patch_plan.json` | 후보 wording, anchor audit, 기대 효과 |
| `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv` | reviewed positive diagnostic manifest 후보 |
| `reports/rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json` | reviewed CSV diagnostic report |
| `reports/rag_xlsx_v3_query_surface_before_after_compare.json` | query별 before/after 비교 |

## 완료 기준

```text
reviewed_query_count=2
query_quality_audit_pass=true
hidden_value_in_positive_query_count=0
Hit@10=1.0 유지
MRR@10 기존 대비 큰 폭 하락 없음
hidden_content_leakage_count=0 유지
```

1차 성공 목표는 2건 모두를 무리하게 맞추는 것이 아니라, 최소 1건 이상의 location match 회복 또는 "realistic hard case로 유지" 결정을 evidence와 함께 남기는 것입니다.

## 금지 사항

- query에 cell range, table id, hidden value를 넣지 않습니다.
- `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive.csv`를 바로 overwrite하지 않습니다.
- candidate namespace를 새로 만들지 않습니다. Query-only 검토는 기존 v1 artifact로 충분합니다.
