# C2. Metadata Projection Readiness

## 목표

SearchUnit DB에 있는 PDF location metadata가 vector hit 결과에서도 복원되는지 검증한다. page hit가 있어도 `physical_page_index`나 `bbox`가 vector-returned metadata에 없으면 citation location metric은 실패할 수 있다.

## 입력

- `reports/pdf_candidate_scope_report.json`
- SearchUnit `location_json`
- ragmeta chunk metadata
- vector hit conversion 결과
- OCR trust metadata

## 확인 항목

| 항목 | 기준 |
|---|---|
| `physical_page_index` | PDF text/table/page chunk에서 복원 가능 |
| `page_no` | 복원 가능 |
| `page_label` | 있으면 복원 가능 |
| `bbox` | text/table/OCR block에서 복원 가능 |
| `section_path` | 있으면 복원 가능 |
| `block_type` | 모든 PDF SearchUnit에서 복원 가능 |
| `ocr_used` | 모든 PDF SearchUnit에서 복원 가능 |
| `ocr_confidence` | OCR row에서 복원 가능 |
| `citation_text` | vector hit 또는 source lookup으로 복원 가능 |

## 작업

1. DB SearchUnit metadata와 ragmeta chunk metadata를 비교한다.
2. vector hit conversion에서 Java `JsonNode` shape와 Python `dict` shape 차이를 확인한다.
3. missing `physical_page_index`, `page_no`, `bbox`, `ocr_confidence` row id 목록을 추출한다.
4. block type별 bbox requirement를 적용한다.
5. metadata projection blocker를 저장 누락, chunk 변환 누락, hit 변환 누락, source lookup 누락으로 분류한다.

## 산출물

- `reports/pdf_vector_metadata_projection_readiness.json`
- 필요 시 `reports/rag_pdf_ocr_trust_readiness.json`

## 완료 기준

```text
metadata_projection_blocker_count=0
missing_physical_page_index_for_page_bound_chunks=0
missing_bbox_for_text_block_chunks=0
missing_ocr_confidence_for_ocr_chunks=0
vector_hit_location_reconstruction_failure_count=0
block_type_bbox_policy_applied=true
```

## 다음 단계 조건

C4 indexing과 C5 diagnostic은 C2가 통과한 뒤 진행한다. C2가 실패한 상태의 retrieval metric은 ranking failure와 metadata projection failure가 섞인다.
