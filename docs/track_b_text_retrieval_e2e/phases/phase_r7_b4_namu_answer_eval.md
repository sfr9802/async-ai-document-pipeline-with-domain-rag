# R7 — B4-namu LLM Answer Eval

## Goal

TEXT retrieval + context + LLM answer까지 포함한 E2E 성능을 기록한다.

## New Files

```text
scripts/rag_text_namu_v4_answer_eval.py
ai-worker/tests/test_rag_text_namu_v4_answer_eval.py
reports/rag_text_namu_v4_answer_eval_report.json
ai-worker/eval/eval_queries/text_namu_v4_answers_v0.jsonl
```

## Evaluation Order

1. Deterministic checks first.
2. Optional LLM judge second.
3. Judge result alone으로 PASS 처리하지 않는다.

## Deterministic Checks

```text
must_contain_terms present
must_not_contain_terms absent
expected answer summary terms covered
allowed abstain respected
unsupported claim count
citation ids returned when required
```

## Metrics

```text
answer_correctness_rule_score
must_contain_pass_rate
must_not_contain_pass_rate
abstain_correctness
unsupported_answer_count
empty_context_answer_count
hallucination_risk_count
latency_p50/p95
prompt_token_count
completion_token_count
```

## Required Report Fields

```json
{
  "status": "COMPLETED | BLOCKED",
  "llm_model": "...",
  "temperature": 0,
  "prompt_template_sha256": "...",
  "context_report_sha256": "...",
  "gold_csv_sha256": "...",
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

## Acceptance Criteria

- B3 context report exists.
- Prompt template hash is recorded.
- deterministic result와 optional judge result가 분리된다.
