# Track B — 기존 TEXT Retrieval + LLM 응답 E2E 성능 기록 상세 플랜

> Phase 단위 재계획 문서는 `docs/track_b_text_retrieval_e2e/README.md`에서 시작한다. 이 원문은 상세 설계의 기준 문서로 보존한다.

## 1. 목적

이 트랙의 목적은 기존 text 기반 retrieval을 **LLM 최종 응답까지 포함한 E2E 품질**로 기록하는 것이다. 기존 retrieval metric만으로는 사용자가 실제로 받는 답변 품질을 알 수 없다. 따라서 retrieval, context assembly, LLM answer, citation support, hallucination/unsupported claim 여부를 하나의 진단 체계로 기록한다.

이 트랙은 XLSX/PDF candidate promotion과 분리한다. TEXT E2E는 운영 품질 관찰과 regression 탐지를 위한 진단이며, XLSX/PDF location metric 또는 vector promotion gate와 섞지 않는다.

---

## 2. 현재 전제와 주의점

현재 RAG ingestion 진행 기록상 path-separation readiness에서는 TEXT count가 0으로 관찰된 이력이 있다. 따라서 이 트랙의 첫 작업은 “TEXT retrieval”이 정확히 어떤 backend를 의미하는지 고정하는 것이다.

가능한 backend는 다음 중 하나다.

| 후보 backend | 설명 | 주의점 |
|---|---|---|
| `library_search` | 현재 `/api/v1/library/search` 기반 검색 | PDF/XLSX stale hit와 섞이지 않도록 source type filter 필요 |
| `legacy_text_index` | 기존 text 문서용 별도 index가 있다면 해당 경로 | index identity/hash 기록 필요 |
| `vector_text_candidate` | TEXT SearchUnit을 별도 candidate vector namespace로 색인 | 아직 구현/인덱싱 상태 확인 필요 |
| `manual_fixture_backend` | 초기 smoke용 fixture retrieval | 운영 backend 성능으로 주장하면 안 됨 |

가장 먼저 해야 할 일은 `retrieval_backend_identity`를 명시하는 것이다. 이 값이 없으면 E2E 리포트는 재현성과 해석 가능성이 떨어진다.

---

## 3. 원칙

1. **TEXT E2E는 XLSX/PDF metric과 분리한다.**
   - XLSX의 `xlsx_citation_location_accuracy`와 TEXT answer correctness를 한 report에서 gate metric처럼 섞지 않는다.

2. **LLM-as-judge 단독 평가를 금지한다.**
   - LLM judge는 보조로만 사용한다.
   - deterministic check를 반드시 포함한다.

3. **prompt/model/config를 hash로 고정한다.**
   - model, prompt template, temperature, max tokens, tool settings, retrieval backend identity를 report에 기록한다.

4. **answer correctness와 groundedness를 분리한다.**
   - 답이 맞아도 citation이 근거를 지원하지 않으면 grounded answer로 보지 않는다.
   - citation이 있어도 답이 틀리면 correctness 실패다.

5. **abstention을 평가한다.**
   - 검색 근거가 없을 때 모른다고 답하는 것도 품질이다.
   - 없는 정보를 만들어내면 hallucination으로 기록한다.

6. **초기에는 diagnostic-only로 둔다.**
   - promotion evidence로 쓰지 않는다.
   - threshold는 regression 관찰용으로만 둔다.

---

## 4. 범위

### 포함

- 기존 TEXT retrieval backend identity 확정.
- TEXT E2E gold schema 작성.
- retrieval + context assembly + LLM answer harness 작성.
- answer deterministic check 작성.
- citation support checker 작성.
- optional LLM judge 작성.
- latency/token/cost proxy 기록.
- 10~20개 smoke query 실행 후 50~100개로 확장.

### 제외

- XLSX/PDF vector promotion.
- PDF embedding metadata projection.
- XLSX range policy tuning.
- hybrid search/reranking 적용.
- production prompt 자동 교체.
- model provider 변경.
- human-reviewed benchmark라고 과장하는 것.

---

## 5. E2E 평가 구조

TEXT E2E는 다음 5단계로 분리해서 기록한다.

```text
User query
  -> Retrieval
  -> Context assembly
  -> LLM answer generation
  -> Citation/grounding validation
  -> Answer scoring
```

각 단계에서 실패 원인을 따로 남긴다.

| 단계 | 주요 질문 |
|---|---|
| Retrieval | 정답 근거 chunk가 top-k에 들어왔는가? |
| Context assembly | top-k 중 올바른 chunk가 prompt context에 포함되었는가? |
| LLM answer | 답변이 expected answer와 일치하는가? |
| Citation support | citation된 근거가 답변의 핵심 주장을 실제로 지원하는가? |
| Guardrail | 근거 없는 주장, 과잉 일반화, 잘못된 abstention이 있는가? |

---

## 6. Gold CSV 설계

### 파일

```text
eval/gold_queries_text_e2e_v0.csv
```

### 권장 컬럼

```csv
query_id,bucket,query,expected_answer_summary,expected_source_ids,expected_chunk_ids,expected_citation_texts,must_contain_terms,must_not_contain_terms,allowed_abstain,answer_type,difficulty,label_status,notes
```

### 컬럼 설명

| 컬럼 | 설명 |
|---|---|
| `query_id` | 안정적인 query id |
| `bucket` | 평가 bucket |
| `query` | 사용자 질의 |
| `expected_answer_summary` | 정답 요약. 긴 답변 전문이 아니라 검증 가능한 핵심 내용 |
| `expected_source_ids` | 정답 근거가 들어 있는 source/document ids |
| `expected_chunk_ids` | 가능하면 chunk 단위 expected id |
| `expected_citation_texts` | citation support 확인용 핵심 근거 문구 |
| `must_contain_terms` | 답변에 반드시 포함되어야 하는 용어 |
| `must_not_contain_terms` | 답변에 나오면 안 되는 용어 또는 hallucination marker |
| `allowed_abstain` | 근거가 없으면 abstain 허용 여부 |
| `answer_type` | fact/procedure/summary/comparison/abstain 등 |
| `difficulty` | easy/medium/hard |
| `label_status` | draft/bound/reviewed/deprecated |
| `notes` | 수동 검토 메모 |

### Bucket 권장안

| Bucket | 목적 | 초기 row 수 |
|---|---:|---:|
| `text_fact_lookup` | 단일 사실 검색 | 5 |
| `text_policy_question` | 정책/규칙 문서 질의 | 5 |
| `text_procedure` | 절차형 답변 | 5 |
| `text_multi_chunk_summary` | 여러 chunk 요약 | 5 |
| `text_comparison` | 두 개 이상 항목 비교 | 5 |
| `text_abstain_required` | 근거 없음/답변 거부 필요 | 5 |

초기 smoke는 10~20개로 시작하고, 이후 최소 50개 이상으로 늘린다.

---

## 7. Harness 설계

### 추천 스크립트

| 스크립트 | 목적 |
|---|---|
| `scripts/rag_text_e2e_gold_validator.py` | gold CSV schema와 binding 검증 |
| `scripts/rag_text_retrieval_diagnostic.py` | retrieval only 진단 |
| `scripts/rag_text_e2e_answer_eval.py` | retrieval + LLM answer E2E 실행 |
| `scripts/rag_text_citation_support_check.py` | citation이 answer claim을 지원하는지 검사 |
| `scripts/rag_text_e2e_failure_breakdown.py` | 실패 원인 taxonomy 생성 |
| `scripts/rag_text_e2e_regression_compare.py` | 이전 run과 metric 비교 |

### Harness 입력

```text
gold CSV
retrieval backend identity
retrieval top_k
context assembly policy
prompt template
LLM model id
temperature
max output tokens
run id
```

### Harness 출력

```text
retrieval results
context chunks
prompt hash
answer text
citation list
judge result
rule-check result
latency/token metrics
failure reason
```

---

## 8. Prompt와 LLM config 고정

### 필수 기록 항목

```json
{
  "llm_model": "...",
  "temperature": 0,
  "max_output_tokens": 800,
  "prompt_template_sha256": "...",
  "system_prompt_sha256": "...",
  "retrieval_backend": "...",
  "retrieval_backend_identity": "...",
  "context_assembly_policy": "top_k_ordered_dedup_v0",
  "top_k": 10,
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

### 기본 answer instruction

TEXT E2E 평가용 prompt는 다음 원칙을 가져야 한다.

```text
1. 제공된 context 안에서만 답한다.
2. 근거가 없으면 모른다고 답한다.
3. 답변의 핵심 주장마다 citation을 붙인다.
4. citation 없는 추측을 하지 않는다.
5. 문서에 없는 최신 정보나 외부 지식을 보태지 않는다.
```

---

## 9. 평가 지표

### Retrieval metric

| 지표 | 의미 |
|---|---|
| `Hit@1/3/5/10` | expected source/chunk가 top-k 안에 있는지 |
| `MRR@10` | expected evidence의 rank 품질 |
| `source_recall@10` | expected source 단위 recall |
| `chunk_recall@10` | expected chunk 단위 recall |
| `result_empty_count` | 검색 결과 없음 |
| `wrong_source_top1_count` | top1이 다른 source인 경우 |

### Context assembly metric

| 지표 | 의미 |
|---|---|
| `context_selected_chunk_count` | prompt에 들어간 chunk 수 |
| `context_token_count` | context token 수 |
| `expected_chunk_in_context_count` | expected evidence가 context에 들어갔는지 |
| `duplicate_context_chunk_count` | 중복 chunk 수 |
| `context_truncation_count` | token limit 때문에 잘린 횟수 |

### Answer metric

| 지표 | 의미 |
|---|---|
| `answer_correctness` | expected answer와 일치 여부 |
| `must_contain_pass` | 필수 용어 포함 여부 |
| `must_not_contain_pass` | 금지 용어 미포함 여부 |
| `abstention_correctness` | abstain해야 할 때 abstain 했는지 |
| `unsupported_claim_count` | 근거 없는 주장 수 |
| `hallucination_count` | 문서와 충돌하거나 문서에 없는 주장 수 |

### Citation/grounding metric

| 지표 | 의미 |
|---|---|
| `citation_present_rate` | 답변에 citation이 있는 비율 |
| `citation_support_rate` | citation이 실제 answer claim을 지원하는 비율 |
| `expected_citation_hit_rate` | expected citation evidence가 사용되었는지 |
| `citation_mismatch_count` | citation이 엉뚱한 chunk를 가리킨 횟수 |
| `answer_supported_by_context` | 답변 핵심 주장이 context로 지지되는지 |

### 운영 metric

| 지표 | 의미 |
|---|---|
| `retrieval_latency_ms_p50/p95` | 검색 latency |
| `llm_latency_ms_p50/p95` | LLM latency |
| `total_latency_ms_p50/p95` | 전체 latency |
| `prompt_tokens_avg` | 평균 prompt token |
| `completion_tokens_avg` | 평균 output token |
| `cost_proxy` | provider 비용이 있으면 추정값 |

---

## 10. Scoring 방식

### 1차 deterministic check

다음 항목은 rule-based로 먼저 본다.

```text
must_contain_terms 포함 여부
must_not_contain_terms 미포함 여부
expected source/chunk/citation 사용 여부
allowed_abstain 처리 여부
answer가 비어 있는지
citation이 존재하는지
```

### 2차 LLM judge

LLM judge는 다음 항목만 보조 판정한다.

```text
expected_answer_summary와 의미적으로 일치하는가?
답변이 citation context로 충분히 지지되는가?
불필요한 추론이나 과장된 claim이 있는가?
```

LLM judge 출력은 JSON으로 제한한다.

```json
{
  "answer_correct": true,
  "grounded": true,
  "unsupported_claim_count": 0,
  "hallucination_count": 0,
  "abstention_correct": null,
  "reason": "..."
}
```

### 최종 판정

최종 pass는 아래 조건을 모두 만족해야 한다.

```text
retrieval_hit = true
expected_evidence_in_context = true
answer_correct = true
citation_supported = true
unsupported_claim_count = 0
must_not_contain_pass = true
```

단, `allowed_abstain=true` row는 다음 조건도 pass로 인정한다.

```text
retrieval_hit = false
answer abstains correctly
unsupported_claim_count = 0
```

---

## 11. Failure taxonomy

| Failure reason | 설명 |
|---|---|
| `retrieval_expected_source_miss` | expected source가 top-k에 없음 |
| `retrieval_expected_chunk_miss` | source는 맞지만 expected chunk가 없음 |
| `context_expected_chunk_dropped` | 검색에는 있었지만 prompt context에서 빠짐 |
| `context_truncated_evidence` | token limit 때문에 evidence가 잘림 |
| `answer_incorrect_despite_evidence` | 근거가 있는데 답변이 틀림 |
| `answer_overgeneralized` | 근거보다 넓은 결론을 말함 |
| `unsupported_claim` | citation으로 지지되지 않는 claim |
| `citation_missing` | citation이 없음 |
| `citation_wrong_chunk` | citation이 엉뚱한 chunk를 가리킴 |
| `abstention_should_have_answered` | 근거가 있는데 모른다고 답함 |
| `abstention_should_have_refused` | 근거가 없는데 답을 지어냄 |
| `judge_uncertain` | LLM judge가 불확실하다고 판단 |
| `gold_label_invalid` | gold 자체가 불충분하거나 binding이 깨짐 |

---

## 12. 리포트 설계

### Retrieval report

```text
reports/rag_text_retrieval_diagnostic_report.json
```

포함 항목:

```json
{
  "retrieval_backend": "...",
  "retrieval_backend_identity": "...",
  "gold_csv": "eval/gold_queries_text_e2e_v0.csv",
  "gold_csv_sha256": "...",
  "top_k": 10,
  "metrics": {
    "Hit@10": 0.0,
    "MRR@10": 0.0,
    "source_recall@10": 0.0
  },
  "query_results": []
}
```

### E2E answer report

```text
reports/rag_text_e2e_answer_eval_report.json
```

포함 항목:

```json
{
  "llm_model": "...",
  "prompt_template_sha256": "...",
  "temperature": 0,
  "promotion_evidence": false,
  "evidence_role": "diagnostic",
  "metrics": {
    "answer_correctness_rate": 0.0,
    "grounded_answer_rate": 0.0,
    "citation_support_rate": 0.0,
    "unsupported_claim_count": 0,
    "hallucination_count": 0
  },
  "query_results": []
}
```

### Citation support report

```text
reports/rag_text_e2e_citation_support_report.json
```

포함 항목:

```json
{
  "citation_present_rate": 0.0,
  "citation_support_rate": 0.0,
  "citation_mismatch_count": 0,
  "unsupported_claim_count": 0,
  "per_claim_results": []
}
```

### Summary report

```text
reports/rag_text_e2e_summary.json
```

한눈에 볼 수 있는 summary를 둔다.

```json
{
  "status": "DIAGNOSTIC_COMPLETED",
  "row_count": 20,
  "retrieval_hit_at_10": 0.0,
  "answer_correctness_rate": 0.0,
  "grounded_answer_rate": 0.0,
  "citation_support_rate": 0.0,
  "hallucination_count": 0,
  "total_latency_ms_p95": 0,
  "promotion_evidence": false
}
```

---

## 13. 단계별 실행 계획

## B0. TEXT backend identity 확정

### 목표

평가 대상이 무엇인지 명확히 한다.

### 작업

1. 현재 text SearchUnit 또는 legacy text index 존재 여부 확인.
2. `/api/v1/library/search` 결과에서 TEXT/PDF/XLSX가 섞이는지 확인.
3. TEXT-only filter가 가능한지 확인.
4. backend identity를 report에 고정한다.

### 산출물

- `reports/rag_text_backend_identity_report.json`

### 완료 기준

```text
retrieval_backend가 명확함
backend artifact 또는 API identity가 기록됨
TEXT/PDF/XLSX path mixing 여부가 기록됨
TEXT-only 평가 가능 여부가 기록됨
```

---

## B1. Gold v0 작성

### 목표

E2E 평가가 가능한 최소 gold set을 만든다.

### 작업

1. 10~20개 smoke row 작성.
2. 각 row에 expected answer summary 작성.
3. expected source/chunk/citation binding 작성.
4. abstain row 포함.
5. gold validator 실행.

### 산출물

- `eval/gold_queries_text_e2e_v0.csv`
- `reports/rag_text_e2e_gold_validate_report.json`

### 완료 기준

```text
row_count >= 10
schema validation pass
expected_source_ids 누락 0
must_contain_terms 누락 최소화
abstain_required bucket 포함
```

---

## B2. Retrieval-only diagnostic

### 목표

LLM 답변 전에 retrieval이 기대 근거를 가져오는지 확인한다.

### 작업

1. gold query별 top-k retrieval 실행.
2. expected source/chunk hit 기록.
3. context 후보 chunk 기록.
4. result empty와 wrong source top1 기록.

### 산출물

- `reports/rag_text_retrieval_diagnostic_report.json`

### 완료 기준

```text
query_results[] 존재
Hit@K/MRR 계산
failure_reason 분류
retrieval backend identity 포함
```

---

## B3. Context assembly 기록

### 목표

retrieval 결과가 LLM prompt에 어떻게 들어가는지 재현 가능하게 만든다.

### 작업

1. top-k 결과 dedup.
2. context token budget 적용.
3. expected evidence가 prompt에 포함되는지 확인.
4. prompt hash와 context chunk ids 기록.

### 산출물

- `reports/rag_text_context_assembly_report.json`

### 완료 기준

```text
context token count 기록
selected chunk ids 기록
expected evidence dropped 여부 기록
prompt_template_sha256 기록
```

---

## B4. LLM answer E2E 실행

### 목표

사용자 최종 답변 품질을 측정한다.

### 작업

1. temperature 0으로 LLM 호출.
2. answer text와 citation 추출.
3. deterministic check 실행.
4. LLM judge 보조 판정 실행.
5. failure taxonomy 부여.

### 산출물

- `reports/rag_text_e2e_answer_eval_report.json`

### 완료 기준

```text
answer_correctness_rate 계산
citation_support_rate 계산
unsupported_claim_count 계산
hallucination_count 계산
latency/token 기록
```

---

## B5. Citation support check

### 목표

답변의 citation이 실제로 답변 claim을 지지하는지 검증한다.

### 작업

1. 답변을 claim 단위로 분해.
2. 각 claim의 citation chunk를 찾음.
3. citation text가 claim을 직접 또는 간접 지지하는지 판정.
4. citation mismatch를 기록.

### 산출물

- `reports/rag_text_e2e_citation_support_report.json`

### 완료 기준

```text
citation_present_rate 계산
citation_support_rate 계산
citation_mismatch_count 계산
per_claim_results[] 기록
```

---

## B6. Summary와 regression compare

### 목표

다음 run과 비교 가능한 summary를 만든다.

### 작업

1. retrieval, answer, citation report를 합친 summary 작성.
2. 이전 run이 있으면 metric delta 계산.
3. regression threshold를 diagnostic warning으로 표시.

### 산출물

- `reports/rag_text_e2e_summary.json`
- `reports/rag_text_e2e_regression_compare.json`

### 완료 기준

```text
핵심 metric summary 존재
run id 존재
previous run과 비교 가능
promotion_evidence=false 유지
```

---

## 14. 실행 명령 예시

```bash
python scripts/rag_text_e2e_gold_validator.py \
  --gold eval/gold_queries_text_e2e_v0.csv \
  --report reports/rag_text_e2e_gold_validate_report.json

python scripts/rag_text_retrieval_diagnostic.py \
  --gold eval/gold_queries_text_e2e_v0.csv \
  --backend library_search \
  --source-file-type TEXT \
  --top-k 10 \
  --report reports/rag_text_retrieval_diagnostic_report.json

python scripts/rag_text_e2e_answer_eval.py \
  --gold eval/gold_queries_text_e2e_v0.csv \
  --retrieval-report reports/rag_text_retrieval_diagnostic_report.json \
  --prompt-template prompts/rag_text_e2e_v0.md \
  --temperature 0 \
  --report reports/rag_text_e2e_answer_eval_report.json

python scripts/rag_text_citation_support_check.py \
  --answer-report reports/rag_text_e2e_answer_eval_report.json \
  --report reports/rag_text_e2e_citation_support_report.json

python scripts/rag_text_e2e_failure_breakdown.py \
  --answer-report reports/rag_text_e2e_answer_eval_report.json \
  --citation-report reports/rag_text_e2e_citation_support_report.json \
  --report reports/rag_text_e2e_summary.json
```

---

## 15. 테스트 계획

### Python syntax

```bash
python -m py_compile \
  scripts/rag_text_e2e_gold_validator.py \
  scripts/rag_text_retrieval_diagnostic.py \
  scripts/rag_text_e2e_answer_eval.py \
  scripts/rag_text_citation_support_check.py \
  scripts/rag_text_e2e_failure_breakdown.py \
  scripts/rag_text_e2e_regression_compare.py
```

### Unit tests

```bash
python -m pytest \
  ai-worker/tests/test_text_e2e_gold_validator.py \
  ai-worker/tests/test_text_e2e_answer_eval.py \
  ai-worker/tests/test_text_citation_support.py
```

### Existing guardrail tests

```bash
python -m pytest \
  ai-worker/tests/test_retrieval_eval_harness.py \
  ai-worker/tests/test_rag_ingestion_scaffolding.py \
  ai-worker/tests/test_promotion_gate_persistence.py
```

---

## 16. 초기 성공 기준

TEXT E2E는 처음부터 높은 threshold를 요구하지 않는다. 우선은 측정 체계를 완성하는 것이 목표다.

### Smoke 완료 기준

```text
gold row_count >= 10
retrieval backend identity 고정
retrieval diagnostic report 생성
answer eval report 생성
citation support report 생성
summary report 생성
promotion_evidence=false
```

### 1차 품질 목표

| 지표 | 목표 |
|---|---:|
| result_empty_count | 가능한 낮게 |
| expected_evidence_in_context_rate | `>= 0.80` |
| answer_correctness_rate | `>= 0.70` smoke 목표 |
| grounded_answer_rate | `>= 0.70` smoke 목표 |
| citation_support_rate | `>= 0.70` smoke 목표 |
| hallucination_count | `0` 목표 |
| unsupported_claim_count | 가능한 낮게 |

초기 목표는 gate threshold가 아니라 진단 기준이다. 실제 threshold는 row 수가 늘고 gold 품질이 안정된 뒤 정한다.

---

## 17. 주요 리스크와 대응

| 리스크 | 대응 |
|---|---|
| TEXT backend가 실제로 비어 있음 | backend identity report에서 먼저 fail-close |
| PDF/XLSX hit가 TEXT 평가에 섞임 | source type/path filter와 path mixing counter 추가 |
| LLM judge가 틀린 답을 맞다고 평가 | deterministic check 우선, judge는 보조로 제한 |
| prompt 변경으로 run 간 비교가 깨짐 | prompt hash와 config 기록 |
| retrieval은 맞는데 context assembly에서 evidence가 빠짐 | context assembly report 분리 |
| citation은 있지만 claim을 지원하지 않음 | claim-level citation support checker 사용 |
| abstain이 실패로만 처리됨 | allowed_abstain row를 별도 scoring |
| E2E 결과를 promotion metric처럼 오해 | diagnostic marker와 별도 report namespace 유지 |

---

## 18. 최종 판단

TEXT 트랙은 지금 최적화보다 **측정 체계 구축**이 먼저다. 특히 retrieval metric만 보면 “근거가 top-k에 있었다”는 사실만 알 수 있고, 사용자가 받은 답이 맞았는지는 알 수 없다.

우선순위는 다음과 같다.

```text
1. TEXT backend identity 고정
2. E2E gold v0 10~20개 작성
3. retrieval-only diagnostic 실행
4. context assembly 기록
5. LLM answer eval 실행
6. citation support check 실행
7. summary/regression report 생성
8. row 수를 50~100개로 확장
```

이 트랙의 산출물은 운영 품질 관찰과 regression 탐지에 가치가 있다. 다만 XLSX/PDF promotion 판단에는 직접 섞지 않는 것이 맞다.
