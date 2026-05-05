# R5 — B2-namu Retrieval-Only Diagnostic

## Goal

namu-v4 corpus/gold에 대해 retrieval-only metric을 생성한다. 이 단계가 Track B 본선의 실제 B2다.

## New Files

```text
scripts/rag_text_namu_v4_retrieval_diagnostic.py
ai-worker/tests/test_rag_text_namu_v4_retrieval_diagnostic.py
reports/rag_text_namu_v4_retrieval_diagnostic_report.json
```

## Inputs

```text
ai-worker/eval/eval_queries/gold_queries_text_namu_v4_v0.csv
ai-worker/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl
existing retrieval emit OR fresh diagnostic retrieval output
```

## Metrics

```text
Hit@1/3/5/10
MRR@10
page_hit@1/3/5/10
section_hit@1/3/5/10
chunk_hit@1/3/5/10
source_recall@10
chunk_recall@10
result_empty_count
missing_chunk_resolution_count
expected_not_in_corpus_count
abstain_query_count
path_mixing_count
```

## Positive Denominator Policy

```text
positive denominator:
  rows with label_status=bound and allowed_abstain=false

excluded from positive denominator:
  abstain rows
  needs_review rows
  expected_not_in_corpus rows
  router UNKNOWN/MIXED rows
```

## Required Report Fields

```json
{
  "status": "COMPLETED | BLOCKED",
  "lane": "B_NAMU_TEXT_CONTENT",
  "retrieval_backend": "existing_emit | fresh_diagnostic_retriever",
  "corpus": "namu-v4-structured-combined",
  "context_source_field": "chunk_text",
  "query_count": 0,
  "positive_query_count": 0,
  "Hit@10": 0.0,
  "MRR@10": 0.0,
  "result_empty_count": 0,
  "missing_chunk_resolution_count": 0,
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

## Acceptance Criteria

- B2-namu report exists and parses.
- `missing_chunk_resolution_count=0` for metric-bearing rows.
- Metric denominator is explicit.
- 기존 B2-app report와 경로가 혼합되지 않는다.
