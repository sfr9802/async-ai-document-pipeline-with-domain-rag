# C6. PDF Failure Breakdown

## 목표

PDF vector diagnostic 실패를 retrieval, metadata, gold policy, chunk granularity로 분리한다. 이 phase가 끝나야 PDF retrieval tuning이 필요한지, gold/policy 수정이 먼저인지 판단할 수 있다.

## 입력

- `ai-worker/eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json`
- C5 query-level result detail
- C2 metadata projection readiness report
- C7 후보 gold rows

## Failure Taxonomy

| Failure type | 설명 |
|---|---|
| `PDF_METADATA_PROJECTION_MISSING_PHYSICAL_PAGE` | page_no는 맞지만 physical_page_index가 vector hit에 없음 |
| `PDF_METADATA_PROJECTION_MISSING_BBOX` | page는 맞지만 bbox가 없음 |
| `PDF_EXPECTED_FILE_ABSENT_IN_TOP10` | expected file이 top10에 없음 |
| `PDF_EXPECTED_PAGE_ABSENT_IN_TOP10` | expected file은 있으나 expected page가 없음 |
| `PDF_BBOX_POLICY_MISMATCH` | bbox overlap/contain/exact 정책 문제 |
| `PDF_TABLE_GOLD_BINDING_MISMATCH` | table/page gold binding 의심 |
| `PDF_CHUNK_GRANULARITY_ISSUE` | chunk가 너무 크거나 작아 evidence가 분산됨 |
| `PDF_OCR_TRUST_CONTRACT_MISMATCH` | OCR confidence/trust marker 문제 |
| `PDF_TRUE_RETRIEVAL_RANKING_FAILURE` | metadata/gold/policy 문제가 아닌 순수 검색 실패 |

## 작업

1. C5 결과를 query 단위로 분해한다.
2. top10에 expected file/page/bbox가 있는지 확인한다.
3. hit는 있으나 metadata가 부족한 경우 C2 blocker와 연결한다.
4. table, page label, OCR, bbox overlap 정책 문제를 C7 후보로 표시한다.
5. chunk granularity issue와 true ranking failure를 분리한다.
6. 모든 query에 `failure_type`, `evidence`, `next_action`을 기록한다.

## 산출물

- `ai-worker/eval/reports/rag-ingestion/rag_pdf_vector_quality_breakdown.json`

## 완료 기준

```text
UNKNOWN failure count=0
metadata vs ranking 분리 완료
gold_policy_candidate_count recorded
chunk_granularity_candidate_count recorded
query별 next_action 존재
```

## 다음 단계 조건

C7은 C6에서 gold/policy 의심으로 분류된 row를 우선 검토한다. `PDF_TRUE_RETRIEVAL_RANKING_FAILURE`만 남은 뒤에야 retrieval tuning 후보를 논의한다.
