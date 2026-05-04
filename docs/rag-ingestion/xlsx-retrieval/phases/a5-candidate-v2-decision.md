# A5 - Candidate V2 Decision

## 목표

새 XLSX-only candidate namespace가 필요한지 결정합니다. 이 phase는 기본 실행 phase가 아니라 decision gate입니다.

## v2 생성 조건

아래 중 하나가 A1-A4 evidence로 확인될 때만 v2를 만듭니다.

```text
embedding_text에 필요한 formula/date/display surface가 빠져 있음
chunk granularity 구조 변경이 필요함
ranking feature 또는 text contract 변경이 필요함
기존 candidate v1과 비교 가능한 별도 artifact가 필요함
```

단순 query wording 수정 또는 gold range policy review만으로는 v2가 필요하지 않습니다.

## 권장 namespace

```text
index_version = rag-ingestion-v2-xlsx-candidate-v2
artifact_dir   = rag-data-xlsx-candidate-v2
```

## Scope rule

```text
allowUnscoped=false
sourceFileTypes=["SPREADSHEET"]
parserVersions=["xlsx-extract-v2-hidden-safe"]
hidden_policy_version=exclude-hidden-v1
explicit documentVersionIds/sourceFileIds/searchUnitIds 사용
```

## 작업

1. A1-A4 decision report를 모아 v2 필요 여부를 판단합니다.
2. v2가 필요 없으면 skip report를 남기고 A6로 이동합니다.
3. v2가 필요하면 XLSX-only scope report를 생성합니다.
4. hidden-safe parser version만 포함합니다.
5. scoped candidate indexing을 실행합니다.
6. embedding consistency report를 실행합니다.
7. v1/v2 diagnostic을 같은 query id 기준으로 비교할 준비를 합니다.

## 산출물

| 파일 | 역할 |
|---|---|
| `reports/xlsx_candidate_v2_decision.json` | v2 생성/skip 결정 |
| `reports/xlsx_candidate_v2_scope_report.json` | v2 scope와 hidden-safe coverage |
| `reports/xlsx_candidate_v2_indexing_report.json` | scoped indexing 결과 |
| `reports/xlsx_candidate_v2_embedding_consistency_report.json` | embedding/chunk/namespace consistency |
| `reports/rag_retrieval_eval_xlsx_v3_positive_candidate_v2_vector_diagnostic_report.json` | v2 diagnostic report |

## 완료 기준

v2를 skip하는 경우:

```text
decision=SKIP
reason in [QUERY_ONLY, RANGE_POLICY_ONLY, GOLD_REVIEW_ONLY]
candidate_v1_mutated=false
```

v2를 생성하는 경우:

```text
decision=CREATE_V2
not_embedded_count=0
index_version_mismatch_count=0
embedding_record_missing_count=0
candidate_chunk_missing_count=0
vector_namespace_mismatch_count=0
chunk_sha_mismatch_count=0
hidden_leakage_count=0
```

## 금지 사항

- 전체 PENDING SearchUnit bulk embedding 금지.
- `allowUnscoped=true` 실행 금지.
- 기존 candidate v1 artifact를 덮어쓰기 금지.
- hidden-safe marker가 없는 stale row를 v2 proof에 포함 금지.
