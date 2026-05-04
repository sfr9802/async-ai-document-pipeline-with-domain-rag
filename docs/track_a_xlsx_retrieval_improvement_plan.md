# Track A - XLSX Retrieval 개선 플랜

이 문서는 Track A 플랜의 진입점입니다. 상세 실행 계획은 RAG ingestion 하위 문서로 분리했습니다.

## 새 문서 구조

| 문서 | 역할 |
|---|---|
| [README](rag-ingestion/xlsx-retrieval/README.md) | Track A 전체 목표, 현재 기준값, 공통 원칙, phase 의존성 |
| [A0 evidence freeze](rag-ingestion/xlsx-retrieval/phases/a0-evidence-freeze.md) | 현재 diagnostic/artifact/hash를 고정 |
| [A1 failure case review](rag-ingestion/xlsx-retrieval/phases/a1-failure-case-review.md) | 4개 degraded query의 top-k evidence와 원인 분리 |
| [A2 query surface review](rag-ingestion/xlsx-retrieval/phases/a2-query-surface-review.md) | `QUERY_NATURALIZATION_DRIFT` 2건의 자연어 wording 검토 |
| [A3 range policy review](rag-ingestion/xlsx-retrieval/phases/a3-range-policy-review.md) | `RANGE_POLICY_MISMATCH` 1건의 range 판정 정책 검토 |
| [A4 formula/date contract review](rag-ingestion/xlsx-retrieval/phases/a4-formula-date-contract-review.md) | `FORMULA_DATE_CONTRACT_MISMATCH` 1건의 value surface 계약 검토 |
| [A5 candidate v2 decision](rag-ingestion/xlsx-retrieval/phases/a5-candidate-v2-decision.md) | 새 XLSX-only candidate namespace가 필요한지 결정 |
| [A6 rerun and compare](rag-ingestion/xlsx-retrieval/phases/a6-rerun-and-compare.md) | diagnostic 재실행, hidden-negative leakage, before/after 비교 |

## 핵심 판단

Track A는 broad retrieval tuning이 아니라 XLSX v3 positive diagnostic의 location/range miss를 좁게 정리하는 작업입니다.

현재 전제는 다음과 같습니다.

```text
Gold source: eval/gold_queries_xlsx_v3_positive.csv
Positive row count: 35
Candidate index version: rag-ingestion-v2-xlsx-candidate-v1
Vector artifact dir: rag-data-xlsx-candidate-v1
Hit@10: 1.0
MRR@10: 0.8857
XLSX range overlap@10: 0.9143
XLSX range contains@10: 0.9143
XLSX exact range@10: 0.8857
XLSX citation location accuracy: 0.8857
Hidden content leakage count: 0
TRUE_RETRIEVAL_RANKING_FAILURE: 0
```

따라서 우선순위는 다음 순서입니다.

```text
A0. 현재 evidence freeze
A1. degraded 4건 evidence review
A2. query naturalization drift 2건 wording 검토
A3. range policy mismatch 1건 policy 검토
A4. formula/date contract 1건 surface 검토
A5. 필요한 경우에만 XLSX candidate v2 namespace 결정
A6. diagnostic-only rerun과 hidden-negative leakage 재확인
```

모든 산출물은 기본적으로 `promotion_evidence=false`, `evidence_role=diagnostic`입니다. immutable baseline, `rag-data-canary`, full72 promotion gate 입력은 이 Track A 문서 체계에서 변경하지 않습니다.
