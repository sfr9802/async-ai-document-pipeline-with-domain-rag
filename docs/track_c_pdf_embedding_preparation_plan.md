# Track C — PDF Embedding 밑작업 상세 플랜

> 단계별 실행 플랜은 [`track-c-pdf-embedding-preparation/README.md`](track-c-pdf-embedding-preparation/README.md) 아래로 분리했다.
> 이 파일은 초기 통합 플랜과 원문 맥락을 보존하는 문서이며, 실제 phase 실행 순서와 gate는 하위 디렉토리 문서를 기준으로 한다.

## 1. 목적

이 트랙의 목적은 PDF vector retrieval 개선을 바로 시작하기 전에, PDF embedding과 citation location 평가에 필요한 **metadata projection, embedding_text contract, candidate indexing consistency**를 먼저 증명하는 것이다.

현재 PDF 쪽은 검색 품질과 metadata projection 문제가 섞여 있다. full72 vector diagnostic/quality breakdown에서는 `page_no`가 맞는 hit가 있는데도 vector-returned metadata에 `physical_page_index` 또는 `bbox`가 빠져 location metric이 실패하는 형태가 관찰됐다. 이 상태에서 retrieval tuning을 먼저 하면 원인을 잘못 최적화할 가능성이 높다.

따라서 PDF 트랙의 첫 목표는 다음이다.

```text
검색 결과가 PDF citation에 필요한 page/bbox/section/OCR metadata를 온전히 반환하는지 증명한다.
```

---

## 2. 현재 문제 인식

PDF diagnostic에서 주의해야 할 분리는 다음과 같다.

| 현상 | 가능한 원인 | 먼저 해야 할 일 |
|---|---|---|
| expected page_no는 top hit에 있음 | retrieval은 일부 성공 | vector metadata projection 확인 |
| physical_page_index가 없음 | metadata 저장 또는 hit 변환 누락 | projection readiness 검사 |
| bbox가 없음 | PDF block chunk metadata 누락 또는 table/doc summary 예외 | block type별 bbox policy 정리 |
| expected file이 top10에 없음 | 실제 retrieval/ranking 문제 가능 | metadata 문제가 제거된 후 판단 |
| table row/page가 애매함 | gold binding 또는 table chunk policy 문제 | table/page gold policy review |
| OCR row 신뢰도 불명확 | lower-trust metadata 누락 | OCR confidence/trust policy 확인 |

즉 현재 PDF는 “검색이 못 찾는다”와 “찾았지만 location evidence가 부족하다”를 분리해야 한다.

---

## 3. 원칙

1. **PDF retrieval tuning 전에 metadata projection readiness를 먼저 통과시킨다.**
   - `physical_page_index`, `page_no`, `page_label`, `bbox`, `section_path`, `ocr_used`, `ocr_confidence`가 vector hit에서 복원되는지 확인한다.

2. **native PDF와 OCR fallback을 분리한다.**
   - native text는 `ocr_used=false`.
   - OCR fallback은 lower-trust metadata와 confidence를 반드시 남긴다.

3. **document summary chunk와 text block chunk를 같은 bbox 기준으로 평가하지 않는다.**
   - text block에는 bbox가 필요하다.
   - document-level summary는 bbox가 없을 수 있다.
   - page summary는 page-level location 기준이 필요하다.

4. **PDF와 XLSX candidate namespace를 섞지 않는다.**
   - PDF 전용 candidate namespace를 사용한다.
   - XLSX-only diagnostic index와 full72 baseline artifact를 변경하지 않는다.

5. **promotion evidence를 만들지 않는다.**
   - 모든 신규 PDF report는 `promotion_evidence=false`, `evidence_role=diagnostic`으로 시작한다.

---

## 4. 범위

### 포함

- PDF SearchUnit metadata projection readiness.
- PDF embedding_text/bm25/display/citation contract audit.
- PDF candidate scope report.
- PDF-only candidate namespace 설계.
- PDF candidate indexing consistency report.
- PDF-only vector diagnostic.
- PDF page/bbox failure breakdown.
- OCR trust metadata 확인.

### 제외

- hybrid search/reranking.
- PDF parser 대규모 교체.
- XLSX query/range tuning.
- TEXT LLM E2E 평가.
- promotion gate 통과 시도.
- immutable baseline 재작성.
- global legacy PDF row cleanup을 promotion-scope blocker처럼 다루는 것.

---

## 5. PDF metadata contract

### SearchUnit `location_json` 권장 구조

```json
{
  "type": "pdf",
  "physical_page_index": 4,
  "page_no": 5,
  "page_label": "v",
  "bbox": [72.0, 120.0, 510.0, 680.0],
  "section_path": ["3. 계약 조건", "3.2 해지 조건"],
  "block_type": "paragraph",
  "ocr_used": false,
  "ocr_confidence": null,
  "parser_name": "pymupdf",
  "parser_version": "pdf-extract-v1"
}
```

### 필수 필드

| 필드 | text block | table block | page summary | document summary | OCR block |
|---|---:|---:|---:|---:|---:|
| `physical_page_index` | 필수 | 필수 | 필수 | 선택 | 필수 |
| `page_no` | 필수 | 필수 | 필수 | 선택 | 필수 |
| `page_label` | 권장 | 권장 | 권장 | 선택 | 권장 |
| `bbox` | 필수 | 필수 또는 table bbox | 선택 | 선택 | 필수 |
| `section_path` | 권장 | 권장 | 선택 | 선택 | 권장 |
| `block_type` | 필수 | 필수 | 필수 | 필수 | 필수 |
| `ocr_used` | 필수 | 필수 | 필수 | 필수 | 필수 |
| `ocr_confidence` | null 허용 | null 허용 | null 허용 | null 허용 | 필수 |

### citation text 권장 형식

```text
{file_name} > p.{page_no} > bbox [{x0},{y0},{x1},{y1}]
```

page label이 의미 있는 문서에서는 다음도 허용한다.

```text
{file_name} > page_label {page_label} / p.{page_no} > bbox [...]
```

---

## 6. PDF embedding_text contract

PDF `embedding_text`에는 검색에 필요한 구조 정보가 들어가야 하지만, debug dump나 parser 내부 raw JSON을 그대로 넣으면 안 된다.

### 포함해야 할 정보

```text
source file name
page number / page label
section path
block type
paragraph text or table text
caption/header if present
OCR trust marker if OCR used
citation text surface
```

### 예시

```text
source: example.pdf
page: 5
page_label: v
section: 3. 계약 조건 > 3.2 해지 조건
block_type: paragraph
ocr_used: false
citation: example.pdf > p.5 > bbox [72.0,120.0,510.0,680.0]
text: 계약 해지 조건은 ...
```

### OCR 예시

```text
source: scanned-example.pdf
page: 2
block_type: ocr_text
ocr_used: true
ocr_confidence: 0.82
trust: lower_trust_ocr
citation: scanned-example.pdf > p.2 > bbox [50.0,80.0,540.0,700.0]
text: ...
```

### 제외해야 할 정보

```text
parser debug dump
full raw JSON
hidden/internal fields
stack trace or warnings as searchable content
binary/image metadata unrelated to answer
untrusted OCR text without lower-trust marker
```

---

## 7. 산출물

### 신규 또는 갱신할 스크립트

| 스크립트 | 목적 |
|---|---|
| `scripts/pdf_candidate_scope_report.py` | PDF candidate scope, parser version, docv 범위 확인 |
| `scripts/pdf_vector_metadata_projection_readiness.py` | vector hit에서 page/bbox/location metadata 복원 가능 여부 확인 |
| `scripts/pdf_candidate_embedding_consistency.py` | PDF candidate rows, embedding_record, ragmeta chunks, namespace consistency 확인 |
| `scripts/rag_pdf_embedding_text_contract_audit.py` | embedding_text/bm25/display/citation surface audit |
| `scripts/rag_pdf_vector_diagnostic.py` | PDF-only vector diagnostic 실행 |
| `scripts/rag_pdf_vector_quality_breakdown.py` | page/bbox/gold/ranking failure 분해 |
| `scripts/rag_pdf_gold_policy_review.py` | PDF page/table/OCR gold row policy review |
| `scripts/rag_pdf_ocr_trust_readiness.py` | OCR confidence/trust metadata readiness 확인 |

### 리포트

| 리포트 | 목적 |
|---|---|
| `reports/pdf_candidate_scope_report.json` | PDF candidate scope와 parser/version 분포 |
| `reports/pdf_vector_metadata_projection_readiness.json` | page/bbox/section/OCR metadata projection readiness |
| `reports/pdf_candidate_embedding_consistency_report.json` | candidate indexing consistency |
| `reports/rag_pdf_embedding_text_contract_audit.json` | embedding_text contract audit |
| `reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json` | PDF-only vector diagnostic |
| `reports/rag_pdf_vector_quality_breakdown.json` | PDF 실패 taxonomy breakdown |
| `reports/rag_pdf_gold_policy_review.json` | page/table/OCR gold policy review |
| `reports/rag_pdf_ocr_trust_readiness.json` | OCR trust metadata readiness |

---

## 8. 단계별 실행 계획

## C0. PDF evidence freeze

### 목표

현재 PDF diagnostic 문제를 기준선으로 고정한다.

### 작업

1. 현재 full72 vector diagnostic report hash 기록.
2. PDF query subset 추출.
3. PDF failure breakdown의 page/bbox 관련 counter 기록.
4. baseline/candidate artifact 변경 없음 확인.

### 산출물

- `reports/rag_pdf_current_diagnostic_snapshot.json`

### 완료 기준

```text
promotion_evidence=false
evidence_role=diagnostic
current PDF failure counters recorded
baseline hash unchanged
```

---

## C1. PDF candidate scope report

### 목표

PDF 전용 candidate scope를 명확히 한다.

### 권장 namespace

```text
index_version = rag-ingestion-v2-pdf-candidate-v1
artifact_dir   = rag-data-pdf-candidate-v1
```

### parser version scope

```text
pdf-extract-v1
pdf-extract-v2
```

`pdf-extract-v1`은 native text 중심, `pdf-extract-v2`는 OCR fallback 가능 path로 본다.

### 작업

1. PDF gold/query 대상 document_version_id 추출.
2. parser_version별 SearchUnit count 확인.
3. `location_json`, `citation_text`, `embedding_text` completeness 확인.
4. `pdf_page_metadata` coverage 확인.
5. text block/table/page summary/document summary 분포 확인.
6. OCR row 분리.

### 산출물

- `reports/pdf_candidate_scope_report.json`

### 완료 기준

```text
missing_location_json_count=0
missing_citation_text_count=0
missing_embedding_text_count=0
missing_page_metadata_count=0
path_mixing_count=0
unsupported_parser_version_count=0
```

---

## C2. Metadata projection readiness

### 목표

SearchUnit DB에는 metadata가 있어도 vector hit로 돌아올 때 누락되면 citation metric은 실패한다. 이 단계는 vector-returned hit에서 metadata가 복원되는지 검증한다.

### 확인 항목

| 항목 | 기준 |
|---|---|
| `physical_page_index` | PDF text/table/page chunk에서 복원 가능해야 함 |
| `page_no` | 복원 가능해야 함 |
| `page_label` | 있으면 복원되어야 함 |
| `bbox` | text/table/OCR block에서는 복원 가능해야 함 |
| `section_path` | 있으면 복원되어야 함 |
| `block_type` | 모든 PDF SearchUnit에서 복원 가능해야 함 |
| `ocr_used` | 모든 PDF SearchUnit에서 복원 가능해야 함 |
| `ocr_confidence` | OCR row에서 복원 가능해야 함 |
| `citation_text` | vector hit 또는 source lookup을 통해 복원 가능해야 함 |

### 작업

1. DB SearchUnit metadata와 ragmeta chunk metadata 비교.
2. vector hit conversion 결과 확인.
3. Java JsonNode shape 또는 Python dict shape 차이 확인.
4. missing `physical_page_index`/`bbox` row id 목록 추출.
5. block_type별 bbox requirement 적용.
6. metadata projection blocker 분류.

### 산출물

- `reports/pdf_vector_metadata_projection_readiness.json`

### 완료 기준

```text
metadata_projection_blocker_count=0
missing_physical_page_index_for_page_bound_chunks=0
missing_bbox_for_text_block_chunks=0
missing_ocr_confidence_for_ocr_chunks=0
vector_hit_location_reconstruction_failure_count=0
```

---

## C3. PDF embedding_text contract audit

### 목표

PDF 검색 질의가 page/section/table text를 찾을 수 있도록 embedding_text가 충분한 구조 surface를 갖고 있는지 확인한다.

### 확인 항목

| 항목 | 기준 |
|---|---|
| source file surface | 파일명이 embedding_text 또는 metadata에 있음 |
| page surface | page_no/page_label이 검색 또는 metadata에 있음 |
| section surface | section_path가 있으면 embedding_text에 반영 |
| table surface | table text 또는 markdown이 포함 |
| caption/header surface | 존재 시 포함 |
| OCR trust marker | OCR row에서 lower-trust marker 포함 |
| debug contamination | debug_text가 embedding_text로 유입되지 않음 |

### 작업

1. PDF row sample 추출.
2. embedding_text/bm25_text/display_text/citation_text 비교.
3. block_type별 text contract 충족 여부 확인.
4. table-centered PDF row의 table surface 점검.
5. OCR row의 confidence/trust marker 점검.

### 산출물

- `reports/rag_pdf_embedding_text_contract_audit.json`

### 완료 기준

```text
missing_page_surface_count=0
missing_section_surface_for_sectioned_rows=0
missing_table_surface_for_table_rows=0
ocr_trust_marker_missing_count=0
debug_text_leakage_count=0
```

---

## C4. PDF candidate indexing

### 목표

PDF 전용 candidate namespace에 명시 scope만 indexing한다.

### 작업 원칙

```text
allowUnscoped=false
sourceFileTypes=["PDF"]
parserVersions=["pdf-extract-v1", "pdf-extract-v2"]
expectedIndexVersion=rag-ingestion-v2-pdf-candidate-v1
indexVersion=rag-ingestion-v2-pdf-candidate-v1
explicit documentVersionIds 사용
```

### 작업

1. candidate scope report에서 documentVersionIds 추출.
2. 필요한 경우 PDF scoped rows requeue.
3. candidate indexing 실행.
4. embedding_record 생성 확인.
5. ragmeta chunks 생성 확인.
6. namespace/hash consistency 확인.

### 산출물

- `reports/pdf_candidate_indexing_report.json`
- `reports/pdf_candidate_embedding_consistency_report.json`

### 완료 기준

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
```

---

## C5. PDF-only vector diagnostic

### 목표

metadata projection과 indexing consistency가 통과한 후 PDF-only vector retrieval을 진단한다.

### Gold filter

```text
expected_location_type=pdf
label_status=bound
positive rows only
hidden/policy negative 제외
```

### 지표

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

### 산출물

- `reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json`
- `reports/rag_pdf_vector_quality_breakdown.json`

### 완료 기준

```text
retrieval_backend=vector
promotion_evidence=false
evidence_role=diagnostic
index/version/filtering mismatch counters=0
metadata_projection_failure_count=0 또는 분리 기록
```

---

## C6. PDF failure breakdown

### 목표

PDF 실패를 retrieval, metadata, gold policy, chunk granularity로 분리한다.

### Taxonomy

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

### 산출물

- `reports/rag_pdf_vector_quality_breakdown.json`

### 완료 기준

```text
UNKNOWN failure count=0
metadata vs ranking 분리 완료
query별 next_action 존재
```

---

## C7. PDF gold policy review

### 목표

PDF page/bbox/table/OCR row의 expected label이 평가 가능한지 확인한다.

### 검토 포인트

- `page_no`와 `physical_page_index`가 모두 필요한가?
- page label이 roman numeral 또는 appendix label일 때 어떻게 판정할 것인가?
- table row는 bbox exact가 필요한가, table bbox overlap이면 되는가?
- OCR row는 confidence threshold를 어떻게 둘 것인가?
- generic PDF query가 특정 page를 기대하기에 너무 모호한가?

### 산출물

- `reports/rag_pdf_gold_policy_review.json`

### 완료 기준

```text
invalid_gold_count=0
page_policy_ambiguous_count=0
table_policy_ambiguous_count=0
ocr_policy_ambiguous_count=0
```

---

## 9. 실행 명령 예시

```bash
python scripts/pdf_candidate_scope_report.py \
  --gold eval/gold_queries_v0.csv \
  --expected-location-type pdf \
  --parser-versions pdf-extract-v1 pdf-extract-v2 \
  --report reports/pdf_candidate_scope_report.json

python scripts/pdf_vector_metadata_projection_readiness.py \
  --scope-report reports/pdf_candidate_scope_report.json \
  --report reports/pdf_vector_metadata_projection_readiness.json

python scripts/rag_pdf_embedding_text_contract_audit.py \
  --scope-report reports/pdf_candidate_scope_report.json \
  --report reports/rag_pdf_embedding_text_contract_audit.json

python scripts/rag_scoped_candidate_indexing.py \
  --source-file-types PDF \
  --parser-versions pdf-extract-v1 pdf-extract-v2 \
  --expected-index-version rag-ingestion-v2-pdf-candidate-v1 \
  --index-version rag-ingestion-v2-pdf-candidate-v1 \
  --allow-unscoped false \
  --report reports/pdf_candidate_indexing_report.json

python scripts/pdf_candidate_embedding_consistency.py \
  --expected-index-version rag-ingestion-v2-pdf-candidate-v1 \
  --artifact-dir rag-data-pdf-candidate-v1 \
  --report reports/pdf_candidate_embedding_consistency_report.json

python scripts/rag_pdf_vector_diagnostic.py \
  --gold eval/gold_queries_v0.csv \
  --expected-location-type pdf \
  --index-version rag-ingestion-v2-pdf-candidate-v1 \
  --artifact-dir rag-data-pdf-candidate-v1 \
  --promotion-evidence false \
  --evidence-role diagnostic \
  --report reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json

python scripts/rag_pdf_vector_quality_breakdown.py \
  --eval-report reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json \
  --report reports/rag_pdf_vector_quality_breakdown.json
```

---

## 10. 테스트 계획

### Python syntax

```bash
python -m py_compile \
  scripts/pdf_candidate_scope_report.py \
  scripts/pdf_vector_metadata_projection_readiness.py \
  scripts/pdf_candidate_embedding_consistency.py \
  scripts/rag_pdf_embedding_text_contract_audit.py \
  scripts/rag_pdf_vector_diagnostic.py \
  scripts/rag_pdf_vector_quality_breakdown.py \
  scripts/rag_pdf_gold_policy_review.py \
  scripts/rag_pdf_ocr_trust_readiness.py
```

### Targeted tests

```bash
python -m pytest \
  ai-worker/tests/test_pdf_extract_capability.py \
  ai-worker/tests/test_retrieval_eval_harness.py \
  ai-worker/tests/test_rag_ingestion_scaffolding.py \
  ai-worker/tests/test_search_unit_indexing_loop.py
```

### Java guardrail tests

```bash
mvn -f core-api/pom.xml test "-Dtest=IndexPromotionGateTest,SearchUnitIndexingServiceTest,DocumentCatalogServiceTest"
```

### Diff hygiene

```bash
git diff --check
```

---

## 11. 완료 기준

PDF embedding 밑작업은 다음 조건을 만족하면 1차 완료로 본다.

```text
1. PDF candidate scope가 명확함
2. PDF metadata projection readiness PASS
3. PDF embedding_text contract audit PASS
4. PDF candidate indexing consistency PASS
5. vector hit에서 physical_page_index/page_no/page_label/bbox/section_path/ocr metadata 복원 가능
6. PDF-only vector diagnostic report 생성
7. PDF failure breakdown에서 metadata/ranking/gold/policy가 분리됨
8. promotion_evidence=false 유지
9. immutable baseline과 XLSX candidate artifact가 변경되지 않음
```

정량 기준은 다음과 같다.

| 항목 | 목표 |
|---|---:|
| metadata projection blocker | `0` |
| missing physical_page_index for page-bound chunks | `0` |
| missing bbox for text/OCR block chunks | `0` |
| missing ocr_confidence for OCR chunks | `0` |
| not_embedded_count | `0` |
| index_version_mismatch_count | `0` |
| embedding_record_missing_count | `0` |
| candidate_chunk_missing_count | `0` |
| vector_namespace_mismatch_count | `0` |
| chunk_sha_mismatch_count | `0` |

PDF retrieval metric 목표는 metadata projection이 통과한 뒤 설정한다. 그 전에는 `pdf_citation_location_accuracy`가 낮아도 검색 실패로 단정하지 않는다.

---

## 12. 주요 리스크와 대응

| 리스크 | 대응 |
|---|---|
| page_no hit를 retrieval success로 보는데 physical_page_index가 빠져 metric 실패 | metadata projection readiness로 분리 |
| bbox 없는 document summary를 text block 실패로 오분류 | block_type별 bbox requirement 적용 |
| OCR text를 native text와 같은 신뢰도로 처리 | lower-trust marker와 confidence 필수화 |
| PDF parser expansion으로 범위가 커짐 | parser 변경 금지, projection/contract audit 우선 |
| PDF와 XLSX candidate namespace가 섞임 | PDF-only namespace 사용 |
| stale legacy PDF row가 candidate evidence에 섞임 | explicit docv/parser/index scope와 `allowUnscoped=false` 사용 |
| gold page/table binding이 애매한데 retrieval failure로 처리 | gold policy review 별도 수행 |

---

## 13. 최종 판단

PDF 트랙은 지금 바로 retrieval tuning을 시작하기보다 **metadata projection과 embedding contract를 먼저 증명해야 한다**. 현재 PDF location metric은 순수 ranking 실패와 metadata 누락이 섞여 있기 때문에, 이걸 분리하지 않으면 잘못된 방향으로 개선할 가능성이 크다.

우선순위는 다음과 같다.

```text
1. PDF candidate scope report
2. vector metadata projection readiness
3. embedding_text contract audit
4. PDF-only candidate indexing consistency
5. PDF-only vector diagnostic
6. PDF vector quality breakdown
7. PDF gold policy review
8. 그 다음에 retrieval/ranking 개선 여부 판단
```

PDF의 핵심은 “정답 page를 찾는가” 이전에 “정답 page/bbox metadata가 vector hit에서 신뢰 가능하게 돌아오는가”다. 이 조건이 통과해야 PDF retrieval metric을 제대로 해석할 수 있다.
