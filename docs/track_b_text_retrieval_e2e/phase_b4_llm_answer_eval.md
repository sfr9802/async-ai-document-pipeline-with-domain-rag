# B4 — LLM Answer E2E

## Goal

사용자가 받는 최종 답변의 correctness, abstention, unsupported claim, hallucination을 측정한다.

## Inputs

- `eval/gold_queries_text_e2e_v0.csv`
- `reports/rag_text_retrieval_diagnostic_report.json`
- `reports/rag_text_context_assembly_report.json`
- `prompts/rag_text_e2e_v0.md`
- fixed LLM config

## Fixed Config v0

```json
{
  "temperature": 0,
  "max_output_tokens": 800,
  "context_assembly_policy": "top_k_ordered_dedup_v0",
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

## Answer Instruction

```text
1. 제공된 context 안에서만 답한다.
2. 근거가 없으면 모른다고 답한다.
3. 답변의 핵심 주장마다 citation을 붙인다.
4. citation 없는 추측을 하지 않는다.
5. 문서에 없는 최신 정보나 외부 지식을 보태지 않는다.
```

## Work Items

1. temperature 0으로 answer generation을 실행한다.
2. answer text와 citation list를 parseable form으로 저장한다.
3. deterministic check를 먼저 실행한다.
4. LLM judge는 보조 판정으로만 실행한다.
5. answer failure와 retrieval/context failure를 분리해 taxonomy를 붙인다.
6. latency, prompt token, completion token, cost proxy를 기록한다.

## Deterministic Checks

```text
must_contain_terms included
must_not_contain_terms absent
expected source/chunk/citation used
allowed_abstain handled
answer is non-empty when answer is required
citation exists when answer is non-abstain
```

## Output

`reports/rag_text_e2e_answer_eval_report.json`

## Done Criteria

```text
answer_correctness_rate calculated
must_contain_pass calculated
must_not_contain_pass calculated
abstention_correctness calculated
unsupported_claim_count recorded
hallucination_count recorded
latency/token metrics recorded
LLM judge output is separated from deterministic checks
```

## Verification Command

```bash
python scripts/rag_text_e2e_answer_eval.py \
  --gold eval/gold_queries_text_e2e_v0.csv \
  --retrieval-report reports/rag_text_retrieval_diagnostic_report.json \
  --context-report reports/rag_text_context_assembly_report.json \
  --prompt-template prompts/rag_text_e2e_v0.md \
  --temperature 0 \
  --report reports/rag_text_e2e_answer_eval_report.json
```
