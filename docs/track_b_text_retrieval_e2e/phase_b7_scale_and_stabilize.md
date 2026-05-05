# B7 — Scale And Stabilize

## Goal

smoke row 10-20개에서 최소 50개, 가능하면 100개까지 확장한다. 이 phase에서도 promotion threshold를 만들지 않고 diagnostic 기준만 안정화한다.

## Preconditions

```text
B0 backend identity is stable
B1 smoke gold validation passes
B2-B6 reports are generated for smoke rows
major failure taxonomy gaps are understood
```

## Work Items

1. B1 bucket balance를 유지하며 row를 50개 이상으로 확장한다.
2. `label_status=draft` row를 `bound` 또는 `reviewed`로 승격하는 기준을 문서화한다.
3. expected source/chunk/citation binding 품질을 재검토한다.
4. abstain row를 유지해 hallucination regression을 계속 관찰한다.
5. 반복 run을 최소 2회 이상 비교해 metric 변동성을 본다.
6. diagnostic warning threshold 후보를 제안하되 promotion gate로 연결하지 않는다.

## Suggested Diagnostic Targets

| Metric | smoke 목표 | stabilized diagnostic 후보 |
|---|---:|---:|
| `expected_evidence_in_context_rate` | `>= 0.80` | `>= 0.85` |
| `answer_correctness_rate` | `>= 0.70` | `>= 0.80` |
| `grounded_answer_rate` | `>= 0.70` | `>= 0.80` |
| `citation_support_rate` | `>= 0.70` | `>= 0.80` |
| `hallucination_count` | `0` 목표 | `0` 목표 |

이 값은 release gate가 아니다. row 수와 label 품질이 안정된 뒤에도 regression warning 용도로만 둔다.

## Outputs

- `ai-worker/eval/eval_queries/gold_queries_text_e2e_v0.csv` expanded to 50-100 rows
- `reports/rag_text_e2e_summary.json`
- `reports/rag_text_e2e_regression_compare.json`
- optional `reports/rag_text_e2e_gold_quality_notes.md`

## Done Criteria

```text
row_count >= 50
bucket distribution is recorded
label_status distribution is recorded
at least two comparable runs exist
diagnostic thresholds are documented as warnings only
promotion_evidence=false is preserved
```
