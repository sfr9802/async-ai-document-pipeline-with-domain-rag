# R6 — B3-namu Context Assembly

## Goal

B2-namu/R5 fresh retrieval emit의 top-k 결과를 파일 기반 diagnostic answer context로 조립한다.

R6는 Track C C4 Candidate Indexing Consistency와 병렬로 진행되었지만 C4 파일, DB, indexing, namespace, worker claim, SearchUnit state를 건드리지 않는다.

## Status

`PASS_WITH_WARNINGS`

- R5 fresh emit만 사용했다.
- Context source는 R2 `namu-v4-structured-combined/rag_chunks.jsonl`의 `chunk_text`만 사용했다.
- `embedding_text`, `text_for_embedding`, `debug_text`는 answer context로 사용하지 않았다.
- `promotion_evidence=false`, `evidence_role=diagnostic`을 유지했다.
- LLM answer eval, citation eval, promotion, indexing은 실행하지 않았다.
- Positive denominator는 R3 `bound` 47 rows이며, `needs_review` 3 rows는 제외했다.
- R5 retrieval miss는 R6 taxonomy로 carry-over했다.

## New Files

```text
ai-worker/scripts/rag_text_namu_v4_context_assembly.py
ai-worker/tests/test_rag_text_namu_v4_context_assembly.py
ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_context_assembly.jsonl
ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_context_assembly_report.json
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
      "doc_id": "...",
      "title": "...",
      "section_path": ["..."],
      "text": "raw chunk_text only",
      "score": 0.0
    }
  ]
}
```

## Guardrails

```text
1. context text must come from rag_chunks.jsonl chunk_text only
2. embedding_text must not be used
3. text_for_embedding must not be used
4. debug_text must not be used
5. duplicate chunk ids are removed or counted
6. empty contexts are allowed only if retrieval result is empty and must be counted
7. R5 retrieval miss is preserved as R6 taxonomy, not hidden
8. C4/PDF/indexing/SearchUnit paths are out of scope
```

## Report Metrics

```text
status=PASS_WITH_WARNINGS
positive_denominator_count=47
needs_review_excluded_count=3
needs_review_query_ids=gold_seed_0048,gold_seed_0049,gold_seed_0050
context_rows_written=50
expected_context_present_count=29
context_empty_count=0
missing_retrieval_result_count=0
missing_expected_source_count=10
missing_expected_chunk_count=8
missing_corpus_chunk_join_count=0
empty_chunk_text_count=0
context_truncated_count=0
duplicate_chunk_dedup_count=0
wrong_source_count_carryover_from_R5=10
missing_expected_chunk_count_carryover_from_R5=18
empty_result_count_carryover_from_R5=0
retrieval_error_count_carryover_from_R5=0
```

## Acceptance Criteria

- `context_field=chunk_text`.
- Disallowed context fields are not used.
- `missing_corpus_chunk_join_count=0`.
- `empty_chunk_text_count=0`.
- `c4_files_touched=false`.
- `db_mutation_run=false`.
- `indexing_run=false`.
- `worker_claim_run=false`.
- `promotion_run=false`.
- `llm_answer_eval_run=false`.
- `citation_eval_run=false`.
- `r7_ready=true`; R7 answer eval is not run by R6.
