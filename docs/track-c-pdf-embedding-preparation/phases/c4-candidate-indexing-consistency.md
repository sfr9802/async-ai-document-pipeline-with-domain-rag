# C4. PDF Candidate Indexing Consistency

## 목표

PDF 전용 candidate namespace에 명시 scope만 indexing하고, candidate rows, embedding records, ragmeta chunks, vector namespace가 같은 대상을 가리키는지 증명한다.

## 입력

- `ai-worker/eval/reports/rag-ingestion/pdf_candidate_scope_report.json`
- C2 metadata projection readiness report
- C3 embedding text contract audit report
- explicit PDF `documentVersionIds`

## 작업 원칙

```text
allowUnscoped=false
sourceFileTypes=["PDF"]
parserVersions=["pdf-extract-v1", "pdf-extract-v2"]
expectedIndexVersion=rag-ingestion-v2-pdf-candidate-v1
indexVersion=rag-ingestion-v2-pdf-candidate-v1
explicit documentVersionIds 사용
```

## 작업

1. C1 scope report에서 explicit `documentVersionIds`를 추출한다.
2. 필요한 경우 PDF scoped rows만 requeue한다.
3. PDF candidate indexing을 실행한다.
4. claimed, indexed, failed count를 확인한다.
5. embedding_record 생성 여부를 확인한다.
6. ragmeta chunks 생성 여부를 확인한다.
7. namespace, chunk sha, embedding text sha consistency를 확인한다.
8. XLSX candidate namespace와 full72 baseline artifact가 변경되지 않았음을 확인한다.

## 산출물

- `ai-worker/eval/reports/rag-ingestion/pdf_candidate_indexing_report.json`
- `ai-worker/eval/reports/rag-ingestion/pdf_candidate_embedding_consistency_report.json`

## 완료 기준

```text
claimed > 0
indexed = claimed
failed = 0
not_embedded_count=0
index_version_mismatch_count=0
embedding_record_missing_count=0
candidate_chunk_missing_count=0
vector_namespace_mismatch_count=0
chunk_sha_mismatch_count=0
xlsx_artifact_changed=false
immutable_baseline_changed=false
```

## 다음 단계 조건

C5 PDF-only vector diagnostic은 C4가 PASS일 때만 실행한다. C4가 실패하면 diagnostic 결과가 stale chunk, mixed namespace, missing embedding record의 영향을 받을 수 있다.
