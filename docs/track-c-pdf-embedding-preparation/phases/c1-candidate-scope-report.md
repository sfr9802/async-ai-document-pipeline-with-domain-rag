# C1. PDF Candidate Scope Report

## 목표

PDF 전용 candidate scope를 확정한다. 이 phase는 어떤 `documentVersionIds`, parser version, block type, OCR row가 Track C 대상인지 정하는 단계다.

## 입력

- C0 snapshot
- PDF gold/query rows
- SearchUnit rows
- PDF page metadata
- parser version metadata

## Scope 계약

```text
index_version = rag-ingestion-v2-pdf-candidate-v1
artifact_dir   = rag-data-pdf-candidate-v1
parser_versions = pdf-extract-v1, pdf-extract-v2
source_file_type = PDF
```

## 작업

1. PDF gold/query 대상 `document_version_id`를 추출한다.
2. parser version별 SearchUnit count를 확인한다.
3. `location_json`, `citation_text`, `embedding_text` completeness를 확인한다.
4. `pdf_page_metadata` coverage를 확인한다.
5. text block, table block, page summary, document summary 분포를 기록한다.
6. OCR row를 native PDF row와 분리한다.
7. unsupported parser version, mixed path, XLSX namespace 유입 여부를 확인한다.

## 산출물

- `reports/pdf_candidate_scope_report.json`

## 완료 기준

```text
missing_location_json_count=0
missing_citation_text_count=0
missing_embedding_text_count=0
missing_page_metadata_count=0
path_mixing_count=0
unsupported_parser_version_count=0
document_version_ids recorded
block_type_distribution recorded
ocr_row_count recorded
```

## 다음 단계 조건

C2와 C3는 C1의 explicit scope를 입력으로 사용한다. scope가 불명확하면 metadata projection 누락과 text contract 누락을 정확히 분류할 수 없다.
