# B5 — Citation Support

## Goal

답변의 citation이 실제 answer claim을 지지하는지 claim 단위로 검증한다.

## Inputs

- `reports/rag_text_e2e_answer_eval_report.json`
- `reports/rag_text_context_assembly_report.json`
- original retrieval chunks or stored context chunks

## Work Items

1. answer를 핵심 claim 단위로 분해한다.
2. 각 claim에 붙은 citation id를 추출한다.
3. citation chunk text가 claim을 직접 또는 간접 지지하는지 판정한다.
4. citation이 없거나 엉뚱한 chunk를 가리키면 failure를 기록한다.
5. expected citation evidence가 실제로 사용됐는지 확인한다.

## Metrics

| Metric | 의미 |
|---|---|
| `citation_present_rate` | 답변에 citation이 있는 비율 |
| `citation_support_rate` | citation이 claim을 지지하는 비율 |
| `expected_citation_hit_rate` | expected evidence가 citation으로 사용된 비율 |
| `citation_mismatch_count` | citation이 엉뚱한 chunk를 가리킨 횟수 |
| `answer_supported_by_context` | 답변 핵심 주장이 context로 지지되는지 |

## Output

`reports/rag_text_e2e_citation_support_report.json`

필수 fields:

```json
{
  "citation_present_rate": 0.0,
  "citation_support_rate": 0.0,
  "citation_mismatch_count": 0,
  "unsupported_claim_count": 0,
  "per_claim_results": []
}
```

## Done Criteria

```text
per_claim_results[] exists
citation_present_rate is calculated
citation_support_rate is calculated
citation_mismatch_count is calculated
unsupported_claim_count is calculated
wrong or missing citation is not counted as grounded answer
```

## Verification Command

```bash
python scripts/rag_text_citation_support_check.py \
  --answer-report reports/rag_text_e2e_answer_eval_report.json \
  --context-report reports/rag_text_context_assembly_report.json \
  --report reports/rag_text_e2e_citation_support_report.json
```
