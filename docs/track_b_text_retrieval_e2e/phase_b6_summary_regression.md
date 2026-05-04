# B6 — Summary And Regression Compare

## Goal

retrieval, context, answer, citation report를 한눈에 볼 수 있는 summary로 합치고 다음 run과 비교할 수 있게 만든다.

## Inputs

- `reports/rag_text_backend_identity_report.json`
- `reports/rag_text_e2e_gold_validate_report.json`
- `reports/rag_text_retrieval_diagnostic_report.json`
- `reports/rag_text_context_assembly_report.json`
- `reports/rag_text_e2e_answer_eval_report.json`
- `reports/rag_text_e2e_citation_support_report.json`
- previous summary report, if available

## Work Items

1. 모든 report의 `run_id`, `gold_csv_sha256`, prompt/config hash 일치 여부를 검사한다.
2. 핵심 metric을 summary로 모은다.
3. 이전 run이 있으면 delta를 계산한다.
4. regression threshold는 gate가 아니라 diagnostic warning으로 표시한다.
5. `promotion_evidence=false`가 유지되는지 검사한다.

## Summary Metrics

| Metric | 의미 |
|---|---|
| `retrieval_hit_at_10` | expected evidence retrieval 성공률 |
| `expected_evidence_in_context_rate` | context에 expected evidence 포함된 비율 |
| `answer_correctness_rate` | expected answer와 일치한 비율 |
| `grounded_answer_rate` | 정답이면서 citation/context로 지지되는 비율 |
| `citation_support_rate` | citation이 claim을 지지한 비율 |
| `hallucination_count` | 문서와 충돌하거나 문서에 없는 주장 수 |
| `total_latency_ms_p95` | 전체 latency p95 |

## Outputs

- `reports/rag_text_e2e_summary.json`
- `reports/rag_text_e2e_regression_compare.json`

## Done Criteria

```text
summary report exists
run_id exists
core metrics are present
previous run comparison is possible when previous report exists
diagnostic warnings are separated from gates
promotion_evidence=false is preserved
```

## Verification Command

```bash
python scripts/rag_text_e2e_failure_breakdown.py \
  --retrieval-report reports/rag_text_retrieval_diagnostic_report.json \
  --context-report reports/rag_text_context_assembly_report.json \
  --answer-report reports/rag_text_e2e_answer_eval_report.json \
  --citation-report reports/rag_text_e2e_citation_support_report.json \
  --report reports/rag_text_e2e_summary.json

python scripts/rag_text_e2e_regression_compare.py \
  --current reports/rag_text_e2e_summary.json \
  --previous reports/previous/rag_text_e2e_summary.json \
  --report reports/rag_text_e2e_regression_compare.json
```
