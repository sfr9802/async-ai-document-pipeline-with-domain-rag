# A1 - Failure Case Review

## 목표

현재 location miss 4건을 단순 실패로 처리하지 않고, query/gold/policy/contract 문제인지 evidence 기반으로 분리합니다.

## 대상

| Query id | 현재 category | 다음 phase |
|---|---|---|
| `gq_xlsx_lookup_002` | `QUERY_NATURALIZATION_DRIFT` | A2 |
| `gq_auto_042` | `QUERY_NATURALIZATION_DRIFT` | A2 |
| `gq_auto_041` | `RANGE_POLICY_MISMATCH` | A3 |
| `gq_xlsx_date_number_format_001` | `FORMULA_DATE_CONTRACT_MISMATCH` | A4 |

## 추출할 evidence

각 row에 대해 다음 정보를 고정 출력합니다.

```text
query_id
query
original_query
query_seed
expected_file_name
expected_document_version_id
expected_sheet_name
expected_cell_range
range_match_policy
v2_label_status
v2_eval_purpose
top_k hits
  rank
  score
  source_file_name
  sheet_name
  cell_range
  table_id
  chunk_type
  citation_text
  location_json
  match_breakdown
failure_reason
category
recommended_next_action
```

## 판단 기준

| 판단 | 기준 |
|---|---|
| Query drift | top-k에 같은 파일/시트가 있고, 질의 wording이 기대 range anchor를 약하게 지시함 |
| Range policy mismatch | top-k result가 합리적 range를 포함하거나 overlap하지만 strict policy와 충돌 |
| Formula/date contract mismatch | 질의가 raw/display/formatted/date surface 중 현재 embedding surface와 다른 값을 요구함 |
| True retrieval failure | 기대 파일 또는 시트가 top10에 전혀 없고 query/gold/policy 문제가 아님 |
| Chunk granularity issue | 기대 range가 한 chunk 안에 없거나 chunk가 너무 커서 match가 불안정함 |

## 산출물

| 파일 | 역할 |
|---|---|
| `reports/rag_xlsx_v3_failure_case_review.json` | 4건의 top-k evidence와 next action |

## 완료 기준

```text
reviewed_degraded_query_count=4
unknown_category_count=0
unclassified_next_action_count=0
true_retrieval_ranking_failure_count=0 또는 별도 근거 기록
```

## 이어지는 결정

- Query drift로 확정된 row는 [A2](a2-query-surface-review.md)로 넘깁니다.
- Range policy 문제로 확정된 row는 [A3](a3-range-policy-review.md)로 넘깁니다.
- Formula/date surface 문제로 확정된 row는 [A4](a4-formula-date-contract-review.md)로 넘깁니다.
- 실제 ranking failure가 새로 확인되면 이 Track A plan 안에서 바로 알고리즘을 고치지 않고 별도 retrieval experiment proposal을 작성합니다.
