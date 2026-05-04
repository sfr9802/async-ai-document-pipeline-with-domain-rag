# Track B — TEXT Retrieval E2E Phase Plan

이 디렉토리는 `docs/track_b_text_retrieval_e2e_plan.md`의 단일 플랜을 phase 단위 실행 계획으로 다시 나눈 것이다. 목표는 기존 TEXT 기반 retrieval을 LLM 최종 답변, citation, groundedness까지 포함한 E2E 진단 체계로 기록하는 것이다.

이 트랙은 diagnostic-only다. XLSX/PDF candidate promotion, location metric, vector gate 판단과 섞지 않는다.

## Progress Log

Phase별 진행 내역은 [rag_text_retrieval_e2e_progress.md](rag_text_retrieval_e2e_progress.md)에 기록한다. Track B가 완료되거나 안정 checkpoint에 도달하면 durable entry를 `docs/rag-ingestion-progress.md`로 합병한다.

## Phase Map

| Phase | 문서 | 목적 | 다음 phase 진입 조건 |
|---|---|---|---|
| B0 | [phase_b0_backend_identity.md](phase_b0_backend_identity.md) | TEXT retrieval backend identity 확정 | TEXT-only 평가 가능 여부와 path mixing 여부 기록 |
| B1 | [phase_b1_gold_v0.md](phase_b1_gold_v0.md) | E2E gold v0 10-20개 작성 | schema validation pass, abstain row 포함 |
| B2 | [phase_b2_retrieval_diagnostic.md](phase_b2_retrieval_diagnostic.md) | retrieval-only Hit/MRR/source recall 진단 | query_results와 failure_reason 생성 |
| B3 | [phase_b3_context_assembly.md](phase_b3_context_assembly.md) | prompt context 구성 재현성 기록 | selected chunk ids, prompt hash, evidence drop 기록 |
| B4 | [phase_b4_llm_answer_eval.md](phase_b4_llm_answer_eval.md) | LLM answer correctness와 guardrail 평가 | answer/citation/latency/token 결과 생성 |
| B5 | [phase_b5_citation_support.md](phase_b5_citation_support.md) | citation이 answer claim을 지지하는지 검증 | claim-level support 결과 생성 |
| B6 | [phase_b6_summary_regression.md](phase_b6_summary_regression.md) | summary와 regression compare 생성 | run id 기반 비교 가능 |
| B7 | [phase_b7_scale_and_stabilize.md](phase_b7_scale_and_stabilize.md) | row 수를 50-100개로 확장하고 기준 안정화 | diagnostic threshold 후보만 제안 |

## Non-Negotiable Rules

1. `promotion_evidence=false`와 `evidence_role=diagnostic`을 모든 report에 유지한다.
2. `retrieval_backend_identity`가 없으면 E2E 결과를 해석하지 않는다.
3. LLM-as-judge는 보조 판정으로만 사용하고 deterministic check를 먼저 실행한다.
4. answer correctness와 citation groundedness를 별도 metric으로 기록한다.
5. XLSX/PDF metric, candidate promotion gate, vector namespace promotion과 직접 연결하지 않는다.
6. prompt template, system prompt, model id, temperature, top_k, context assembly policy는 hash 또는 명시 값으로 고정한다.
7. fixture backend 결과는 smoke로만 기록하고 운영 TEXT retrieval 성능으로 주장하지 않는다.

## Planned Artifact Namespace

| 종류 | 경로 |
|---|---|
| Gold CSV | `eval/gold_queries_text_e2e_v0.csv` |
| Prompt template | `prompts/rag_text_e2e_v0.md` |
| Backend identity report | `reports/rag_text_backend_identity_report.json` |
| Gold validation report | `reports/rag_text_e2e_gold_validate_report.json` |
| Retrieval diagnostic report | `reports/rag_text_retrieval_diagnostic_report.json` |
| Context assembly report | `reports/rag_text_context_assembly_report.json` |
| Answer eval report | `reports/rag_text_e2e_answer_eval_report.json` |
| Citation support report | `reports/rag_text_e2e_citation_support_report.json` |
| Summary report | `reports/rag_text_e2e_summary.json` |
| Regression compare report | `reports/rag_text_e2e_regression_compare.json` |

## Execution Order

```text
B0 backend identity
  -> B1 gold v0
  -> B2 retrieval-only diagnostic
  -> B3 context assembly
  -> B4 LLM answer eval
  -> B5 citation support check
  -> B6 summary/regression compare
  -> B7 scale to 50-100 rows
```

## Stop Conditions

Stop and record the blocker instead of continuing when any of the following is true.

- TEXT backend identity is unknown.
- TEXT-only filtering is impossible and PDF/XLSX hits cannot be separated.
- gold rows cannot be bound to expected source or chunk evidence.
- prompt/model/config cannot be hashed or recorded.
- LLM answers cannot emit citations in a parseable form.
- reports would be reused as promotion evidence.
