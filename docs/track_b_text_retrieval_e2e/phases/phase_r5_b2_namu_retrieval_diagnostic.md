# R5 — B2-namu Retrieval-Only Diagnostic

## Goal

namu-v4 corpus/gold에 대해 retrieval-only metric을 생성한다. 이 단계가 Track B 본선의 실제 B2다.

## New Files

```text
ai-worker/scripts/rag_text_namu_v4_retrieval_diagnostic.py
ai-worker/tests/test_rag_text_namu_v4_retrieval_diagnostic.py
ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_retrieval_emit.jsonl
ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_retrieval_diagnostic_report.json
```

## Inputs

```text
ai-worker/eval/eval_queries/gold_queries_text_namu_v4_v0.csv
ai-worker/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl
fresh diagnostic retrieval output only
```

## Metrics

```text
Hit@1/3/5/10
MRR@10
page_Hit@1/3/5/10
section_Hit@1/3/5/10
chunk_Hit@1/3/5/10
source_recall@10
page_recall@10
section_recall@10
chunk_recall@10
empty_result_count
wrong_source_count
missing_expected_chunk_count
missing_chunk_resolution_count
expected_not_in_corpus_count
retrieval_error_count
```

## Positive Denominator Policy

```text
positive denominator:
  rows with label_status=bound and allowed_abstain=false

excluded from positive denominator:
  abstain rows
  needs_review rows
  router UNKNOWN/MIXED rows

current R3 policy:
  positive denominator count = 47
  needs_review excluded count = 3
```

## Required Report Fields

```json
{
  "status": "PASS | PASS_WITH_WARNINGS | FAIL",
  "lane": "B_NAMU_TEXT_CONTENT",
  "retrieval_backend": "fresh_diagnostic_lexical_bm25",
  "corpus": "namu-v4-structured-combined",
  "context_source_field": "chunk_text",
  "query_count": 0,
  "positive_denominator_count": 47,
  "needs_review_excluded_count": 3,
  "fresh_emit_path": "ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_retrieval_emit.jsonl",
  "reused_emit": false,
  "existing_emit_reused": false,
  "Hit@10": 0.0,
  "MRR@10": 0.0,
  "empty_result_count": 0,
  "missing_chunk_resolution_count": 0,
  "retrieval_metrics_computed": true,
  "llm_answer_eval_run": false,
  "citation_eval_run": false,
  "promotion_run": false,
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

## Acceptance Criteria

- B2-namu report exists and parses.
- `missing_chunk_resolution_count=0` for metric-bearing rows.
- Metric denominator is explicit and uses the R3 positive `47` rows.
- The R3 `needs_review` `3` rows are excluded and listed separately.
- Existing emits are not reused.
- 기존 B2-app report와 경로가 혼합되지 않는다.
