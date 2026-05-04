# A3 - Range Policy Review

## 목표

`RANGE_POLICY_MISMATCH` 1건을 retrieval 실패로 볼지, gold range policy mismatch로 볼지 판정합니다.

## 대상

| Query id | 현재 category |
|---|---|
| `gq_auto_041` | `RANGE_POLICY_MISMATCH` |

## 검토 질문

1. expected range가 너무 좁게 bound 되어 있는가?
2. top hit range가 expected range를 포함하거나 의미적으로 같은 row group/table group인가?
3. 사용자가 답변 citation으로 받아들일 수 있는 range인가?
4. `EXACT_RANGE`가 필요한 질의인가?
5. `CONTAINS_EXPECTED` 또는 `OVERLAP_RANGE`가 더 타당한가?
6. policy 변경이 metric을 인위적으로 부풀리는 것은 아닌가?

## Policy 선택 기준

| Policy | 사용 조건 |
|---|---|
| `EXACT_RANGE` | 특정 행/셀/정확한 표 범위를 반드시 찾아야 하는 질의 |
| `CONTAINS_EXPECTED` | 더 큰 table chunk가 expected range를 포함해도 citation으로 허용 가능한 질의 |
| `OVERLAP_RANGE` | row-group/table chunk granularity 때문에 정확한 범위보다 overlap evidence가 중요한 질의 |
| `NONE` | hidden negative 또는 non-positive policy probe |

## 작업

1. A1 evidence에서 expected range와 top-k range를 나란히 비교합니다.
2. current policy 기준 pass/fail과 alternate policy 기준 pass/fail을 dry-run 계산합니다.
3. human citation acceptability를 기록합니다.
4. policy 변경 시 reviewed CSV에만 반영합니다.
5. policy 변경이 positive metric을 쉽게 만드는 shortcut인지 점검합니다.

## 산출물

| 파일 | 역할 |
|---|---|
| `reports/rag_xlsx_range_policy_review.json` | 유지/변경 결정과 evidence |
| `reports/rag_xlsx_range_policy_dry_run_impact.json` | alternate policy별 metric 영향 |

## 완료 기준

```text
reviewed_query_id=gq_auto_041
policy_decision in [KEEP, CHANGE_IN_REVIEWED_CSV, DEFER_AS_GOLD_BINDING_ISSUE]
policy_reason_present=true
metric_inflation_risk_reviewed=true
```

## 금지 사항

- 전체 range policy threshold를 완화하지 않습니다.
- policy 변경을 promotion evidence로 취급하지 않습니다.
- `eval/gold_queries_v0.csv` 또는 immutable baseline 관련 파일을 건드리지 않습니다.
