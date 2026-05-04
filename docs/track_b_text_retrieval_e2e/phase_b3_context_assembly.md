# B3 — Context Assembly

## Goal

retrieval 결과가 LLM prompt context에 어떻게 들어갔는지 재현 가능하게 기록한다. retrieval이 성공했는데 context assembly에서 evidence가 빠지는 실패를 별도로 잡는다.

## Inputs

- `reports/rag_text_retrieval_diagnostic_report.json`
- prompt template
- context assembly policy
- max context tokens

## Work Items

1. top-k 결과를 stable order로 정렬한다.
2. duplicate chunk를 제거한다.
3. context token budget을 적용한다.
4. expected evidence가 최종 prompt context에 포함됐는지 기록한다.
5. prompt template과 system prompt hash를 기록한다.
6. selected chunk id, dropped chunk id, truncation reason을 query별로 남긴다.

## Context Policy v0

```text
context_assembly_policy=top_k_ordered_dedup_v0
dedup_key=source_id + chunk_id
order=retrieval_rank_ascending
truncate=token_budget_after_system_and_user_prompt
```

## Metrics

| Metric | 의미 |
|---|---|
| `context_selected_chunk_count` | prompt에 들어간 chunk 수 |
| `context_token_count` | context token 수 |
| `expected_chunk_in_context_count` | expected evidence가 context에 포함된 수 |
| `duplicate_context_chunk_count` | dedup된 chunk 수 |
| `context_truncation_count` | token limit 때문에 잘린 횟수 |

## Output

`reports/rag_text_context_assembly_report.json`

## Done Criteria

```text
selected chunk ids are recorded per query
context token count is recorded
expected evidence included/dropped status is recorded
prompt_template_sha256 is recorded
system_prompt_sha256 is recorded
context_assembly_policy is recorded
```

## Verification

retrieval miss는 B2 failure로 유지한다. B3에서는 retrieval hit였지만 prompt context에 들어가지 못한 case만 `context_expected_chunk_dropped` 또는 `context_truncated_evidence`로 분류한다.
