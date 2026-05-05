# A6 - Rerun And Compare

## 목표

A2-A5 결과를 diagnostic-only로 재평가하고, positive metric과 hidden-negative leakage를 분리해서 최종 summary를 만듭니다.

## 평가 세트

| 세트 | 목적 |
|---|---|
| `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive.csv` | 기존 v3 positive 기준 |
| `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv` | query/policy review 후 기준 |
| `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_hidden_negative.csv` 또는 hidden-negative report input | leakage 확인 전용 |

## 평가 지표

| 지표 | 목표 |
|---|---:|
| Hit@10 | `1.0` 유지 |
| MRR@10 | `0.8857` 이상 유지 또는 소폭 개선 |
| XLSX file hit@10 | `1.0` 유지 |
| XLSX sheet hit@10 | `1.0` 유지 |
| XLSX range overlap@10 | `0.9143` 이상 유지 또는 개선 |
| XLSX range contains@10 | `0.9143` 이상 유지 또는 개선 |
| XLSX exact range@10 | `0.8857` 이상 유지 또는 개선 |
| XLSX citation location accuracy | 1차 목표 `0.9143`, 2차 목표 `0.9429` |
| hidden_content_leakage_count | `0` 유지 |

## 비교 원칙

1. 전체 평균만 보지 않습니다.
2. 4개 degraded query의 before/after rank와 range match를 함께 봅니다.
3. metric이 올라가도 query/gold/policy가 과하게 쉬워졌는지 확인합니다.
4. hidden-negative는 positive metric에 섞지 않습니다.
5. v2를 만들었더라도 v1/v2 비교는 diagnostic-only입니다.

## 작업

1. reviewed CSV schema/gold validation을 실행합니다.
2. candidate v1 diagnostic을 재실행합니다.
3. A5에서 v2를 만든 경우 v2 diagnostic도 실행합니다.
4. hidden-negative leakage diagnostic을 재실행합니다.
5. v2/v3 또는 before/after comparison을 생성합니다.
6. failure breakdown을 갱신합니다.
7. 최종 summary에 promotion 금지 marker를 확인합니다.

## 산출물

| 파일 | 역할 |
|---|---|
| `reports/rag_xlsx_v3_after_cleanup_metric_compare.json` | before/after metric 비교 |
| `reports/rag_xlsx_v3_after_cleanup_failure_breakdown.json` | 최종 failure breakdown |
| `reports/rag_xlsx_hidden_negative_leakage_diagnostic.json` | hidden-negative leakage 재확인 |
| `reports/rag_xlsx_v3_retrieval_performance_summary.json` | 최종 diagnostic summary |

## 완료 기준

```text
reviewed_gold_validation_pass=true
positive_diagnostic_completed=true
hidden_negative_diagnostic_completed=true
hidden_content_leakage_count=0
promotion_evidence=false
evidence_role=diagnostic
baseline_hash_unchanged=true
candidate_v1_mutated=false
```

## 테스트/검증 예시

```bash
python -m py_compile \
  scripts/rag_xlsx_retrieval_performance_diagnostic.py \
  scripts/rag_xlsx_v2_v3_metric_compare.py \
  scripts/rag_xlsx_v3_failure_breakdown.py \
  scripts/rag_xlsx_v3_vector_quality_breakdown.py

python scripts/rag_retrieval_eval.py \
  --validate-only \
  --gold ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv \
  --report reports/rag_xlsx_v3_positive_reviewed_validate_report.json

python scripts/rag_xlsx_retrieval_performance_diagnostic.py
python scripts/rag_xlsx_v2_v3_metric_compare.py
python scripts/rag_xlsx_v3_failure_breakdown.py
git diff --check
```

Java/Spring promotion gate test는 이 Track A가 promotion evidence를 만들지 않았다는 guardrail을 확인할 때만 좁게 실행합니다.
