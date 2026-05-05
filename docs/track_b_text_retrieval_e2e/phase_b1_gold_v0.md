# B1 — Gold v0

## Goal

TEXT E2E smoke 평가용 gold set을 10-20개 만든다. 처음부터 human-reviewed benchmark로 과장하지 않고, binding 가능한 diagnostic seed로 둔다.

## Gold File

`ai-worker/eval/eval_queries/gold_queries_text_e2e_v0.csv`

## Required Columns

```csv
query_id,bucket,query,expected_answer_summary,expected_source_ids,expected_chunk_ids,expected_citation_texts,must_contain_terms,must_not_contain_terms,allowed_abstain,answer_type,difficulty,label_status,notes
```

## Initial Buckets

| Bucket | 목적 | smoke row 목표 |
|---|---:|---:|
| `text_fact_lookup` | 단일 사실 검색 | 2-4 |
| `text_policy_question` | 정책/규칙 문서 질의 | 2-4 |
| `text_procedure` | 절차형 답변 | 2-4 |
| `text_multi_chunk_summary` | 여러 chunk 요약 | 1-3 |
| `text_comparison` | 두 개 이상 항목 비교 | 1-3 |
| `text_abstain_required` | 근거 없음/답변 거부 필요 | 2-4 |

## Work Items

1. B0에서 고정한 backend가 실제로 반환할 수 있는 TEXT corpus를 기준으로 후보 query를 고른다.
2. 각 row에 검증 가능한 `expected_answer_summary`를 작성한다.
3. 가능한 경우 `expected_chunk_ids`까지 binding한다.
4. citation support 확인용 핵심 문구를 `expected_citation_texts`에 남긴다.
5. `allowed_abstain=true` row를 반드시 포함한다.
6. validator가 label status, source id, required columns, duplicate query id를 검사하도록 계획한다.

## Output

- `ai-worker/eval/eval_queries/gold_queries_text_e2e_v0.csv`
- `reports/rag_text_e2e_gold_validate_report.json`

## Done Criteria

```text
row_count >= 10
required columns exist
query_id is unique
expected_source_ids missing count is 0 for non-abstain rows
abstain_required bucket exists
label_status is draft or bound
gold validation report exists
```

## Verification Command

```bash
python scripts/rag_text_e2e_gold_validator.py \
  --gold ai-worker/eval/eval_queries/gold_queries_text_e2e_v0.csv \
  --report reports/rag_text_e2e_gold_validate_report.json
```
