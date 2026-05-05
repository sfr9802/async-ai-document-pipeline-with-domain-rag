# R3 — namu-v4 Query/Gold Binding

## Goal

namu-v4 retrieval-only 및 answer E2E에 사용할 query/gold seed를 corpus에 bind한다.

## New Files

```text
scripts/rag_text_namu_v4_gold_builder.py
scripts/rag_text_namu_v4_gold_validator.py
ai-worker/tests/test_rag_text_namu_v4_gold_validator.py
ai-worker/eval/eval_queries/gold_queries_text_namu_v4_v0.csv
reports/rag_text_namu_v4_gold_build_report.json
reports/rag_text_namu_v4_gold_validate_report.json
```

## Gold CSV Schema

```csv
query_id,bucket,query,expected_page_ids,expected_section_ids,expected_chunk_ids,expected_answer_summary,must_contain_terms,must_not_contain_terms,allowed_abstain,answer_type,label_status,source_dataset,notes
```

## Recommended Buckets

```text
text_fact_lookup
text_policy_question
text_multi_chunk_summary
text_procedure
text_comparison
text_abstain_required
```

## Binding Policy

```text
positive rows:
  require at least one expected_page_id or expected_chunk_id

chunk-level positive rows:
  expected_chunk_ids must resolve in rag_chunks.jsonl
  chunk doc_id must be in expected_page_ids
  expected_section_ids must resolve both on rag_chunks and pages_v4 sections
  expected_section_path from source must match rag_chunks.section_path

abstain rows:
  expected ids may be empty
  excluded from positive Hit/MRR denominator
  do not fabricate abstain rows when the selected seed has no true unanswerable rows

ambiguous rows:
  label_status=needs_review
  excluded from retrieval metric denominator
  current manual seed keeps allowed_abstain=false and uses text_policy_question
```

## Acceptance Criteria

- Validator status is `PASSED` before B2-namu retrieval diagnostic.
- Missing chunk ids are blockers, not silent misses.
- Abstain rows are counted separately.
- Current manual seed has `47` positive rows, `3` needs_review policy rows, and `0` fabricated abstain rows.
- Bucket counts match `text_fact_lookup=31`, `text_multi_chunk_summary=16`, `text_policy_question=3`.
- Validator report must keep `allowed_abstain_true_count=0`, `section_path_mismatch_count=0`, and `source_dataset_is_manual_curated_seed=true`.
- `expected_section_path` recorded in CSV notes is rechecked against `rag_chunks.section_path`; mismatch is a blocker.
- `promotion_evidence=false`, `evidence_role=diagnostic`.
