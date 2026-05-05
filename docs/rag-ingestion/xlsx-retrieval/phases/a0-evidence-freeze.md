# A0 - Evidence Freeze

## 목표

현재 XLSX v3 positive diagnostic 상태를 고정해서 이후 query, policy, contract 수정의 효과를 같은 기준으로 비교할 수 있게 합니다.

이 phase는 변경 작업이 아니라 lineage/snapshot 작업입니다.

## 입력

| 입력 | 기준 |
|---|---|
| Positive gold | `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive.csv` |
| Diagnostic report | `reports/rag_retrieval_eval_xlsx_v3_positive_vector_diagnostic_report.json` |
| Performance summary | `reports/rag_xlsx_v3_retrieval_performance_summary.json` |
| Failure breakdown | `reports/rag_xlsx_v3_failure_breakdown.json` |
| Candidate index version | `rag-ingestion-v2-xlsx-candidate-v1` |
| Artifact dir | `rag-data-xlsx-candidate-v1` |

## 작업

1. positive CSV hash와 row count를 기록합니다.
2. current diagnostic report hash를 기록합니다.
3. candidate index version과 artifact dir hash/descriptor를 기록합니다.
4. hidden-negative leakage report가 positive metric과 분리되어 있는지 확인합니다.
5. immutable baseline과 `rag-data-canary`가 변경되지 않았음을 lineage report에 남깁니다.
6. current metric table을 snapshot report로 고정합니다.

## 산출물

| 파일 | 역할 |
|---|---|
| `reports/rag_xlsx_candidate_lineage_before_tuning.json` | candidate/baseline/artifact lineage |
| `reports/rag_xlsx_v3_current_diagnostic_snapshot.json` | 현재 metric과 degraded query snapshot |

## 완료 기준

```text
promotion_evidence=false
evidence_role=diagnostic
candidate_index_version=rag-ingestion-v2-xlsx-candidate-v1
retrieval_backend=vector
positive_row_count=35
hidden_content_leakage_count=0
baseline_hash_unchanged=true
rag_data_canary_hash_unchanged=true
```

## 금지 사항

- `ai-worker/eval/eval_queries/gold_queries_v0.csv` 수정 금지.
- immutable baseline descriptor/hash 수정 금지.
- candidate v1 vector artifact mutate 금지.
- missing row를 맞추기 위해 broad reindex 실행 금지.
