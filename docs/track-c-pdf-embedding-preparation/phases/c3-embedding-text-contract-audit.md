# C3. PDF Embedding Text Contract Audit

## 목표

PDF 검색 질의가 page, section, table, OCR evidence를 찾을 수 있도록 `embedding_text`, `bm25_text`, `display_text`, `citation_text`가 충분한 구조 surface를 갖고 있는지 확인한다.

## 입력

- `reports/pdf_candidate_scope_report.json`
- PDF SearchUnit rows
- embedding/bm25/display/citation text surfaces
- OCR confidence/trust metadata

## 확인 항목

| 항목 | 기준 |
|---|---|
| source file surface | 파일명이 embedding text 또는 metadata에 있음 |
| page surface | page_no/page_label이 text 또는 metadata에 있음 |
| section surface | section_path가 있으면 embedding text에 반영 |
| table surface | table text 또는 markdown이 포함 |
| caption/header surface | 존재 시 포함 |
| OCR trust marker | OCR row에서 lower-trust marker 포함 |
| debug contamination | debug/raw JSON/stack trace가 searchable text로 유입되지 않음 |

## 작업

1. C1 scope에서 block type별 sample을 추출한다.
2. `embedding_text`, `bm25_text`, `display_text`, `citation_text`를 비교한다.
3. paragraph/table/page summary/document summary/OCR별 text contract를 분리 적용한다.
4. table-centered PDF row의 table surface와 caption/header surface를 점검한다.
5. OCR row의 confidence와 lower-trust marker를 점검한다.
6. parser debug dump, hidden/internal fields, warning text 유입을 검사한다.

## 산출물

- `reports/rag_pdf_embedding_text_contract_audit.json`
- 필요 시 `reports/rag_pdf_ocr_trust_readiness.json`

## 완료 기준

```text
missing_page_surface_count=0
missing_section_surface_for_sectioned_rows=0
missing_table_surface_for_table_rows=0
ocr_trust_marker_missing_count=0
debug_text_leakage_count=0
hidden_or_internal_field_leakage_count=0
```

## 다음 단계 조건

C4 indexing 전에 C3를 통과해야 한다. text contract가 불완전하면 embedding/indexing이 정상이어도 retrieval diagnostic이 잘못 해석된다.
