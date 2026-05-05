# C5. PDF-only Vector Diagnostic

## 목표

metadata projection과 PDF candidate indexing consistency가 통과한 뒤, PDF-only vector retrieval을 diagnostic evidence로 실행한다.

## 입력

- `ai-worker/eval/reports/rag-ingestion/pdf_candidate_scope_report.json`
- `ai-worker/eval/reports/rag-ingestion/pdf_vector_metadata_projection_readiness.json`
- `ai-worker/eval/reports/rag-ingestion/rag_pdf_embedding_text_contract_audit.json`
- `ai-worker/eval/reports/rag-ingestion/pdf_candidate_embedding_consistency_report.json`
- PDF gold rows

## Gold Filter

```text
expected_location_type=pdf
label_status=bound
positive rows only
hidden/policy negative 제외
```

## 지표

| 지표 | 의미 |
|---|---|
| `Hit@10` | expected evidence가 top10에 있는지 |
| `MRR@10` | expected evidence rank |
| `pdf_file_hit@10` | expected file hit |
| `pdf_page_hit@10` | expected page hit |
| `pdf_bbox_overlap@10` | bbox overlap hit |
| `pdf_citation_location_accuracy` | citation location 기준 최종 정확도 |
| `result_empty_count` | 결과 없음 |
| `metadata_projection_failure_count` | hit는 있으나 metadata 부족 |
| `true_retrieval_ranking_failure_count` | metadata 문제가 아닌 순수 검색 실패 |

## 작업

1. PDF-only gold filter를 적용한다.
2. `rag-ingestion-v2-pdf-candidate-v1` index와 `ai-worker/eval/indexes/rag-data-pdf-candidate-v1` artifact만 사용한다.
3. vector backend로 diagnostic을 실행한다.
4. report에 `promotion_evidence=false`, `evidence_role=diagnostic`을 기록한다.
5. index/version/filtering mismatch counters를 확인한다.
6. metadata projection failure와 true ranking failure를 분리 기록한다.

## 산출물

- `ai-worker/eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json`
- C6 입력용 query-level result detail

## 완료 기준

```text
retrieval_backend=vector
promotion_evidence=false
evidence_role=diagnostic
index_version=rag-ingestion-v2-pdf-candidate-v1
artifact_dir=ai-worker/eval/indexes/rag-data-pdf-candidate-v1
index/version/filtering mismatch counters=0
metadata_projection_failure_count=0 또는 분리 기록
query_level_results_available=true
```

## 다음 단계 조건

C6는 C5 report의 query-level detail을 입력으로 실패 taxonomy를 작성한다. C5는 promotion proof가 아니라 diagnostic proof다.
