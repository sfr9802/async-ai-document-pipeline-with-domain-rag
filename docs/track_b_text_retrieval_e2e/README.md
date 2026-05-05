# Track B — Query Intent Routing + namu-v4 TEXT E2E

이 디렉토리는 Track B를 `B-app` smoke와 `B-namu` 본선으로 다시 나눈 phase-level 실행 계획이다. 기존 app catalog TEXT canary 결과는 보존하지만, Track B 대표 metric은 `namu-v4-structured-combined` 기반 TEXT content retrieval/QA에서 새로 만든다.

상태는 diagnostic-only다. promotion, XLSX/PDF candidate mutation, immutable baseline 수정, `ai-worker/eval/indexes/rag-data-canary` 수정과 섞지 않는다.

## Source Notes

- 기존 `B2 retrieval diagnostic`은 `B-app app-catalog TEXT canary smoke`로 재라벨링한다.
- `B2-app`의 Hit/MRR 0점은 namu-v4 성능이나 기존 TEXT retrieval 전체 실패로 해석하지 않는다.
- `B-namu` context에는 `chunk_text` 또는 동등한 raw text field만 사용한다. `embedding_text`, `text_for_embedding`, `debug_text`는 LLM context로 쓰지 않는다.
- FILE lookup과 CONTENT lookup은 서로 다른 objective로 분리한다.

## Progress Log

Phase별 진행 내역은 [rag_text_retrieval_e2e_progress.md](rag_text_retrieval_e2e_progress.md) 하나로 통합한다.

- 이 파일이 Track B 전체 이력, `B-app` smoke / `B-namu` mainline 관계, R0-R9 세부 phase 상태, evidence 판단, gate/blocker 판단의 source-of-truth다.
- 기존 `phases/phase_progress.md`는 중복 source-of-truth라 삭제했다.
- Track B가 stable checkpoint에 도달하거나 intentionally paused 되었을 때 durable entry를 `docs/rag-ingestion-progress.md`로 병합한다.

## Canonical Paths

경로 표기는 repo root 기준 상대경로를 canonical로 쓴다. `ai-worker` 안에서 스크립트를 실행할 때만 괄호 안의 `ai-worker` cwd 기준 경로를 사용한다.

| Artifact | Canonical repo-root path | `ai-worker` cwd path |
|---|---|---|
| R1 routing matrix CSV | `ai-worker/eval/eval_queries/query_intent_routing_matrix_v0.csv` | `eval/eval_queries/query_intent_routing_matrix_v0.csv` |
| R3 namu-v4 gold CSV | `ai-worker/eval/eval_queries/gold_queries_text_namu_v4_v0.csv` | `eval/eval_queries/gold_queries_text_namu_v4_v0.csv` |
| Track B reports | `ai-worker/eval/reports/rag-ingestion/*.json` | `eval/reports/rag-ingestion/*.json` |
| Track B scripts | `ai-worker/scripts/*.py` | `scripts/*.py` |

Historical shorthand such as `reports/...`, `scripts/...`, or bare `eval/...` must be read with this table before citing an artifact.

## Lane Map

| Lane | 목적 | 대표 corpus/backend | 현재 상태 |
|---|---|---|---|
| `B-app` | app catalog TEXT import/search smoke | small TEXT canary + `library_search` | 완료, smoke-only; B-namu/namu-v4/production-style TEXT evidence로 인용 금지 |
| `B-namu` | 단순 텍스트 문서 검색/QA 본선 | `namu-v4-structured-combined` | R6 context assembly completed with `PASS_WITH_WARNINGS`; R7 answer eval planned, not run |
| `XLSX_CONTENT` | XLSX 내부 내용 검색 | XLSX vector candidate | diagnostic-ready |
| `XLSX_FILE` | XLSX 파일 자체 검색 | file/document metadata index | not ready |
| `PDF_CONTENT` | PDF 내부 내용 검색 | PDF vector candidate + page/bbox metadata | blocked on Track C |
| `PDF_FILE` | PDF 파일 자체 검색 | file/document metadata index | not ready |

## Current Phase Map

| Phase | 문서 | 목적 | 다음 phase 진입 조건 |
|---|---|---|---|
| R0 | [phase_r0_b2_scope_correction.md](phases/phase_r0_b2_scope_correction.md) | 기존 B2를 B-app smoke-only로 재라벨링 | scope correction report 생성 |
| R1 | [phase_r1_query_intent_routing_matrix.md](phases/phase_r1_query_intent_routing_matrix.md) | TEXT/XLSX/PDF와 FILE/CONTENT lane 분리 | routing matrix/report 생성 |
| R2 | [phase_r2_namu_v4_corpus_inventory.md](phases/phase_r2_namu_v4_corpus_inventory.md) | namu-v4 corpus 구조/hash/context field 검증 | inventory PASS |
| R3 | [phase_r3_namu_v4_gold_binding.md](phases/phase_r3_namu_v4_gold_binding.md) | namu-v4 query/gold seed를 corpus에 bind | gold validator PASSED |
| R4 | [phase_r4_namu_v4_retrieval_emit_inventory.md](phases/phase_r4_namu_v4_retrieval_emit_inventory.md) | 기존 retrieval emit 재사용 가능성 판단 | existing emit 사용 또는 fresh run 결정 |
| R5 | [phase_r5_b2_namu_retrieval_diagnostic.md](phases/phase_r5_b2_namu_retrieval_diagnostic.md) | 실제 B2-namu retrieval-only metric 생성 | 완료: fresh emit/report 존재, denominator 명시 |
| R6 | [phase_r6_b3_namu_context_assembly.md](phases/phase_r6_b3_namu_context_assembly.md) | retrieval top-k를 raw chunk_text context로 조립 | 완료: context emit/report 존재 |
| R7 | [phase_r7_b4_namu_answer_eval.md](phases/phase_r7_b4_namu_answer_eval.md) | LLM answer correctness와 guardrail 평가 | planned/ready; R6 report를 입력으로 사용 |
| R8 | [phase_r8_b5_namu_citation_support.md](phases/phase_r8_b5_namu_citation_support.md) | answer claim의 citation support 검증 | claim-level support report 존재 |
| R9 | [phase_r9_file_content_lane_readiness.md](phases/phase_r9_file_content_lane_readiness.md) | XLSX/PDF/TEXT FILE vs CONTENT lane readiness 분리 | readiness report 존재 |

## Supporting Docs

| 문서 | 역할 |
|---|---|
| [query_intent_taxonomy.md](query_intent_taxonomy.md) | Query intent schema, FILE/CONTENT signals, lane mapping |
| [phase_b0_backend_identity.md](phase_b0_backend_identity.md) | Legacy B-app backend identity smoke plan |
| [phase_b1_gold_v0.md](phase_b1_gold_v0.md) | Legacy B-app gold v0 smoke plan |
| [phase_b2_retrieval_diagnostic.md](phase_b2_retrieval_diagnostic.md) | Legacy B2-app retrieval diagnostic, now smoke-only |
| [phase_b3_context_assembly.md](phase_b3_context_assembly.md) | Superseded by R6 for B-namu |
| [phase_b4_llm_answer_eval.md](phase_b4_llm_answer_eval.md) | Superseded by R7 for B-namu |
| [phase_b5_citation_support.md](phase_b5_citation_support.md) | Superseded by R8 for B-namu |
| [phase_b6_summary_regression.md](phase_b6_summary_regression.md) | Retained as summary/regression follow-up after B5-namu |
| [phase_b7_scale_and_stabilize.md](phase_b7_scale_and_stabilize.md) | Retained as later scale/stabilize follow-up |

## Non-Negotiable Rules

1. `promotion_evidence=false`와 `evidence_role=diagnostic`을 모든 Track B report에 유지한다.
2. `B2-app` metric을 `B-namu` 대표 metric으로 사용하지 않는다.
3. XLSX/PDF FILE lookup을 CONTENT retrieval metric에 섞지 않는다.
4. UNKNOWN/MIXED router row, abstain row, needs_review row는 positive Hit/MRR denominator에 자동으로 넣지 않는다.
5. hidden negative row를 positive denominator에 섞지 않는다.
6. `embedding_text`, `text_for_embedding`, `debug_text`를 LLM answer context로 사용하지 않는다.
7. library-search/app-catalog smoke report를 immutable baseline 또는 promotion evidence로 사용하지 않는다.

## Planned Artifact Namespace

| 종류 | 경로 |
|---|---|
| B2 scope correction report | `ai-worker/eval/reports/rag-ingestion/rag_text_b2_scope_correction_report.json` |
| Query intent routing CSV | `ai-worker/eval/eval_queries/query_intent_routing_matrix_v0.csv` |
| Query intent routing report | `ai-worker/eval/reports/rag-ingestion/rag_query_intent_routing_matrix_report.json` |
| namu-v4 corpus inventory report | `ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_corpus_inventory_report.json` |
| namu-v4 gold CSV | `ai-worker/eval/eval_queries/gold_queries_text_namu_v4_v0.csv` |
| namu-v4 gold reports | `ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_gold_build_report.json`, `ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_gold_validate_report.json` |
| namu-v4 retrieval emit inventory | `ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_retrieval_emit_inventory_report.json` |
| B2-namu retrieval diagnostic emit | `ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_retrieval_emit.jsonl` |
| B2-namu retrieval diagnostic report | `ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_retrieval_diagnostic_report.json` |
| B3-namu contexts | `ai-worker/eval/eval_queries/text_namu_v4_contexts_v0.jsonl`, `ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_context_assembly_report.json` |
| B4-namu answers | `ai-worker/eval/eval_queries/text_namu_v4_answers_v0.jsonl`, `ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_answer_eval_report.json` |
| B5-namu citation support | `ai-worker/eval/reports/rag-ingestion/rag_text_namu_v4_citation_support_report.json` |
| FILE/CONTENT readiness | `ai-worker/eval/reports/rag-ingestion/rag_file_content_lane_readiness_report.json` |

## Execution Order

```text
R0 B2-app scope correction
  -> R1 query intent routing matrix
  -> R2 namu-v4 corpus inventory
  -> R3 namu-v4 gold binding
  -> R4 retrieval emit inventory
  -> R5 B2-namu retrieval diagnostic
  -> R6 B3-namu context assembly
  -> R7 B4-namu answer eval
  -> R8 B5-namu citation support
  -> R9 file/content lane readiness
```

## Stop Conditions

Stop and record the blocker instead of continuing when any of the following is true.

- R2 corpus inventory does not confirm a parseable `rag_chunks.jsonl`.
- R2 cannot identify a raw context field such as `chunk_text` or an equivalent `text`.
- R3 gold rows cannot resolve expected chunk/page evidence.
- R4 existing emit has unresolved chunk ids or mismatched query ids and no fresh diagnostic retrieval path is chosen.
- R5 denominator is ambiguous or mixes `B-app` and `B-namu`.
- R6 would have to use embedding/debug text as LLM context.
- R7/R8 would be reused as promotion evidence.
