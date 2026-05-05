# R6 — B3-namu Context Assembly

## Goal

B2-namu top-k retrieval output을 LLM 입력 context로 조립한다.

## New Files

```text
scripts/rag_text_namu_v4_context_assembly.py
ai-worker/tests/test_rag_text_namu_v4_context_assembly.py
reports/rag_text_namu_v4_context_assembly_report.json
eval/text_namu_v4_contexts_v0.jsonl
```

## Context Item Schema

```json
{
  "query_id": "...",
  "query": "...",
  "contexts": [
    {
      "rank": 1,
      "chunk_id": "...",
      "page_id": "...",
      "page_title": "...",
      "section_path": ["..."],
      "text": "raw chunk_text only",
      "score": 0.0
    }
  ]
}
```

## Guardrails

```text
1. context text must come from chunk_text/text only
2. embedding_text must not be used
3. text_for_embedding must not be used
4. debug_text must not be used
5. duplicate chunk ids are removed or counted
6. empty contexts are allowed only if retrieval result is empty and must be counted
```

## Report Metrics

```text
context_query_count
empty_context_count
missing_chunk_text_count
duplicate_chunk_count
context_char_count_p50/p95
context_chunk_count_p50/p95
embedding_prelude_leak_count
disallowed_context_field_count
```

## Acceptance Criteria

- `disallowed_context_field_count=0`.
- `missing_chunk_text_count=0` for non-empty retrieval hits.
- Empty context count is explained by retrieval output, not assembly failure.
