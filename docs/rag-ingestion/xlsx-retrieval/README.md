# Track A - XLSX Retrieval 개선 재계획

## 목적

이 문서 묶음은 XLSX 전용 후보 인덱스에서 자연어 질의 기반 검색의 range/location 정확도를 개선하기 위한 phase plan입니다. 현재 증거상 검색 자체가 무너진 상태는 아닙니다. `Hit@10=1.0`, XLSX file/sheet hit는 `1.0`, hidden leakage는 `0`, `TRUE_RETRIEVAL_RANKING_FAILURE=0`입니다.

따라서 Track A의 초점은 broad retrieval tuning이 아니라 다음 4개 location miss를 원인별로 분리하고 최소 수정하는 것입니다.

| Category | Count | 우선 처리 |
|---|---:|---|
| `QUERY_NATURALIZATION_DRIFT` | 2 | 자연어 query surface 검토 |
| `RANGE_POLICY_MISMATCH` | 1 | range match policy 검토 |
| `FORMULA_DATE_CONTRACT_MISMATCH` | 1 | formula/date value surface contract 검토 |
| `TRUE_RETRIEVAL_RANKING_FAILURE` | 0 | 현재 phase에서는 알고리즘 튜닝 대상 아님 |

## 현재 기준값

| 항목 | 현재 값 |
|---|---:|
| Gold source | `eval/gold_queries_xlsx_v3_positive.csv` |
| Positive row count | `35` |
| Candidate index version | `rag-ingestion-v2-xlsx-candidate-v1` |
| Vector artifact dir | `rag-data-xlsx-candidate-v1` |
| Hit@10 | `1.0` |
| MRR@10 | `0.8857` |
| XLSX file hit@10 | `1.0` |
| XLSX sheet hit@10 | `1.0` |
| XLSX range overlap@10 | `0.9143` |
| XLSX range contains@10 | `0.9143` |
| XLSX exact range@10 | `0.8857` |
| XLSX citation location accuracy | `0.8857` |
| Hidden content leakage count | `0` |

Degraded query ids는 현재 breakdown 기준으로 다음 4개입니다.

| Query id | Category | Phase |
|---|---|---|
| `gq_xlsx_lookup_002` | `QUERY_NATURALIZATION_DRIFT` | [A2](phases/a2-query-surface-review.md) |
| `gq_auto_042` | `QUERY_NATURALIZATION_DRIFT` | [A2](phases/a2-query-surface-review.md) |
| `gq_auto_041` | `RANGE_POLICY_MISMATCH` | [A3](phases/a3-range-policy-review.md) |
| `gq_xlsx_date_number_format_001` | `FORMULA_DATE_CONTRACT_MISMATCH` | [A4](phases/a4-formula-date-contract-review.md) |

## 공통 원칙

1. 모든 신규/갱신 report는 `promotion_evidence=false`, `evidence_role=diagnostic`을 유지합니다.
2. `initial-full72-vector-baseline-v0`, `rag-data-canary`, 기존 immutable baseline descriptor/hash는 변경하지 않습니다.
3. 기존 `rag-ingestion-v2-xlsx-candidate-v1`과 `rag-data-xlsx-candidate-v1`은 직접 mutate하지 않습니다.
4. hidden-negative row는 leakage diagnostic으로만 평가하고 positive Hit@K/MRR에는 섞지 않습니다.
5. `source_file -> extracted_artifact -> search_unit` path를 유지합니다.
6. XLSX SearchUnit은 `parser_version`, `location_json`, `citation_text`, `embedding_text`가 없으면 candidate indexing 대상이 아닙니다.
7. hidden sheet/row/column content는 SearchUnit text, normalized metadata, embedding text, vector metadata에 들어가면 안 됩니다.
8. hybrid search, reranking, parser expansion, answer generation 변경은 이 Track A phase의 기본 범위가 아닙니다.

## Phase 의존성

```text
A0 evidence freeze
  -> A1 failure case review
      -> A2 query surface review
      -> A3 range policy review
      -> A4 formula/date contract review
          -> A5 candidate v2 decision, only if needed
              -> A6 rerun and compare
```

A2, A3, A4는 A1의 evidence가 고정된 뒤 병렬로 진행할 수 있습니다. A5는 항상 실행하는 phase가 아니라 decision gate입니다.

## Phase 문서

| Phase | 문서 | 완료 시 얻는 것 |
|---|---|---|
| A0 | [evidence freeze](phases/a0-evidence-freeze.md) | 비교 가능한 현재 상태 snapshot |
| A1 | [failure case review](phases/a1-failure-case-review.md) | 4개 degraded query의 row별 next action |
| A2 | [query surface review](phases/a2-query-surface-review.md) | 자연어 wording 수정 여부와 reviewed CSV 후보 |
| A3 | [range policy review](phases/a3-range-policy-review.md) | range policy 유지/변경 결정 |
| A4 | [formula/date contract review](phases/a4-formula-date-contract-review.md) | raw/display/date/formula surface 계약 결정 |
| A5 | [candidate v2 decision](phases/a5-candidate-v2-decision.md) | v2 namespace 생성 또는 명시적 skip 결정 |
| A6 | [rerun and compare](phases/a6-rerun-and-compare.md) | 최종 diagnostic summary와 hidden leakage 재확인 |

Phase별 실제 진행 내역은 [phase-progress.md](phase-progress.md)에 기록합니다. Track A 작업이 끝나면 해당 로그를 `docs/rag-ingestion-progress.md`에 합병하고 이 임시 로그는 정리합니다.

## 공통 산출물 네이밍

Track A 산출물은 다음 규칙을 따릅니다.

```text
reports/rag_xlsx_*                    # XLSX 전용 diagnostic/report
eval/gold_queries_xlsx_v3_*           # XLSX v3 query manifest 계열
rag-ingestion-v2-xlsx-candidate-*     # XLSX-only candidate index_version
rag-data-xlsx-candidate-*             # XLSX-only vector artifact dir
```

`full72`, `promotion`, `baseline` 이름이 들어간 산출물은 이 Track A 결과를 직접 승격하는 용도로 사용하지 않습니다.
