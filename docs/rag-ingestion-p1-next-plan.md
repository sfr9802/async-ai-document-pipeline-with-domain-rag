# RAG Ingestion v2 P1 실행 계획

작성일: 2026-05-03
대상 단계: P0 ingestion evidence gap 종료 이후 P1 실행
현재 기준: live XLSX/PDF smoke 통과, 실제 XLSX batch smoke 8/8 통과, PDF smoke 통과

---

## 0. 문서 목적

이 문서는 xlsx/pdf RAG ingestion v2의 다음 실행 단계를 정리한다.

현재 P0에서는 다음을 증명했다.

> xlsx/pdf 파일이 live `core-api` / `ai-worker` / PostgreSQL을 거쳐 `search_unit`까지 생성되고, citation metadata가 누락되지 않는다.

하지만 아직 다음은 증명되지 않았다.

> 생성된 `search_unit`들이 실제 검색에서 잘 잡히고, gold query 기준으로 평가 가능하며, 실패한 candidate index가 promotion되지 않는다.

따라서 다음 단계는 추가 parser 설계가 아니라 다음 흐름을 구현하는 것이다.

```text
PDF batch smoke
  -> normalized metadata population
  -> gold query live binding
  -> retrieval smoke
  -> report-only eval gate
  -> index build / promote / rollback skeleton
```

---

## 1. 현재 상태 판단

### 1.1 완료된 항목

| 영역 | 판단 |
|---|---|
| XLSX generated smoke | 통과 |
| 실제 XLSX batch smoke | 8/8 통과 |
| PDF smoke | 통과 |
| XLSX/PDF citation metadata | 누락 0 |
| Java compile/tests | 통과 |
| Python tests | 통과 |
| PyMuPDF live dependency | Python 3.13 기준 해결 |
| P0 ingestion evidence gap | 사실상 닫힘 |

### 1.2 현재 DB 집계

| 항목 | 값 |
|---|---:|
| `spreadsheet_units` | 9362 |
| `spreadsheet_missing_metadata` | 0 |
| `pdf_units` | 4 |
| `pdf_missing_metadata` | 0 |
| `XLSX_WORKBOOK_JSON` parsed artifact | 34 |
| `PDF_PARSED_JSON` parsed artifact | 1 |

### 1.3 냉정한 판단

XLSX 경로는 실제 batch smoke까지 통과했으므로 P1로 넘어갈 수 있다.

PDF 경로는 smoke는 통과했지만 아직 `PDF_PARSED_JSON = 1`, `pdf_units = 4` 수준이다.
즉, “PDF ingestion 경로가 동작한다”는 증거는 있지만, “다양한 실제 PDF에서 안정적이다”는 증거는 부족하다.

따라서 P1 초반에는 PDF batch smoke를 XLSX batch smoke 수준으로 끌어올려야 한다.

---

## 2. 다음 단계 한 줄 결론

확보한 xlsx/pdf 데이터를 기준으로 normalized metadata를 적재하고, gold query를 live `document_version/search_unit/location`에 연결한 뒤, candidate `index_version`을 평가·승격·롤백할 수 있는 P1 워크플로를 구현한다.

---

## 3. P1 우선순위

| 우선순위 | 작업 | 이유 |
|---:|---|---|
| 1 | 실제 PDF batch smoke 추가 | PDF smoke가 1개 수준이면 PDF parser 안정성을 판단하기 어렵다. |
| 2 | `pdf_page_metadata`, `table_metadata`, `cell_metadata` 적재 | gold query와 citation 검증을 live id/location에 묶기 위해 필요하다. |
| 3 | `gold_queries_v0.csv`를 seed에서 실제 평가셋으로 확장 | 평가셋 없이는 index promotion gate가 형식만 남는다. |
| 4 | retrieval smoke 추가 | ingestion은 됐지만 top-k 검색 품질은 아직 별도 검증해야 한다. |
| 5 | offline eval gate 고도화 | promotion API보다 먼저 gate 계산이 실제로 돌아야 한다. |
| 6 | index build/promote/rollback/eval API | 평가 결과를 운영 흐름으로 연결한다. |
| 7 | hybrid/reranker 검토 | P1이 닫힌 뒤에만 의미가 있다. |

---

## 4. P1에서 하지 말아야 할 것

| 하지 말 것 | 이유 |
|---|---|
| hybrid retrieval 도입 | ingestion → retrieval baseline이 아직 없다. |
| reranker 도입 | top-k 후보 품질부터 봐야 한다. |
| LLM 답변 프롬프트 고도화 | citation/retrieval eval이 먼저다. |
| 모든 cell을 무조건 정규화 | row 폭증 가능성이 크다. |
| promotion API부터 구현 | gate 계산 없이 API만 생긴다. |
| OCR 고도화부터 시작 | native PDF와 table/page metadata가 먼저다. |
| gold query 자동 생성만 사용 | live id binding이 부정확해질 수 있다. |

---

## 5. 가장 먼저 할 일: 실제 PDF batch smoke

현재 XLSX는 real batch smoke가 통과했다. PDF도 같은 수준으로 끌어올린다.

### 5.1 추가할 파일

```text
samples/rag_pdf_ingestion_manifest.json
scripts/rag_pdf_ingestion_sample_batch.py
reports/rag_pdf_ingestion_sample_batch_report.json
```

### 5.2 PDF manifest 예시

```json
{
  "manifest_version": "rag-pdf-ingestion-batch-v0",
  "default_expectations": {
    "min_search_units": 1,
    "require_parser_version": true,
    "require_location_json": true,
    "require_citation_text": true,
    "require_page_metadata": true,
    "require_bbox_if_text_block": true
  },
  "samples": [
    {
      "sample_id": "pdf_native_contract_001",
      "path": "datasets/pdf/contract_native_text.pdf",
      "file_type": "pdf",
      "bucket": "pdf_section_question",
      "expected": {
        "min_pages": 1,
        "min_search_units": 3,
        "must_have_parser_name": "pymupdf",
        "must_have_parser_version": "pdf-extract-v1",
        "must_have_ocr_used": false,
        "must_have_page_numbers": true
      }
    },
    {
      "sample_id": "pdf_table_001",
      "path": "datasets/pdf/price_table.pdf",
      "file_type": "pdf",
      "bucket": "pdf_table_lookup",
      "expected": {
        "min_pages": 1,
        "min_search_units": 2,
        "expect_table_like_blocks": true
      }
    }
  ]
}
```

### 5.3 PDF sample bucket 구성

처음 목표는 8~10개 PDF batch smoke다.

| bucket | 최소 개수 | 목적 |
|---|---:|---|
| `pdf_native_text` | 3 | 일반 텍스트 PDF 안정성 |
| `pdf_section_question` | 2 | heading/section 추론 확인 |
| `pdf_table_lookup` | 2 | 표 중심 PDF 검증 |
| `pdf_multi_page` | 2 | page number/page label 검증 |
| `pdf_ocr_required` | 1~2 | OCR fallback 분리 확인 |

### 5.4 PDF batch smoke 검증 항목

```text
- source READY
- job SUCCEEDED
- PDF_PARSED_JSON exists
- PDF_PLAINTEXT exists
- search_unit count >= expected
- parser_name = pymupdf
- parser_version = pdf-extract-v1
- location_json has physical_page_index/page_no/page_label
- citation_text is not null
- missing_pdf_metadata = 0
```

### 5.5 PDF batch smoke 성공 기준

| 항목 | 기준 |
|---|---:|
| 실제 PDF batch smoke | 8~10개 중 90% 이상 통과 |
| PDF metadata missing count | 0 |
| `PDF_PARSED_JSON` 생성 | 모든 native text PDF에서 생성 |
| `PDF_PLAINTEXT` 생성 | 모든 native text PDF에서 생성 |
| `parser_version` | `pdf-extract-v1` |
| `location_json` page fields | 100% 존재 |
| `citation_text` | 100% 존재 |

---

## 6. normalized metadata 적재

현재 `search_unit.location_json`에는 필요한 정보가 들어가고 있다.
하지만 계속 JSON만으로 버티면 eval/gold binding, citation accuracy, page/table 단위 집계가 불편해진다.

P1에서는 normalized table을 채운다.

### 6.1 테이블별 우선순위

| 테이블 | 우선순위 | 판단 |
|---|---:|---|
| `pdf_page_metadata` | P1-1 | PDF citation/page 검증에 바로 필요 |
| `table_metadata` | P1-1 | XLSX/PDF table query 평가에 필요 |
| `embedding_record` | P1-1 | `index_version`과 embedding 재현성에 필요 |
| `index_build` | P1-1 | promotion/rollback의 중심 |
| `cell_metadata` | P1-2 | row/cell 단위 trace에는 유용하지만 폭증 위험 있음 |
| `citation` | P1-2 | retrieval/eval 결과와 연결 후 정규화 |

### 6.2 `cell_metadata` 제한 정책

현재 spreadsheet unit이 9,000개 이상이다. 모든 셀을 무조건 정규화하면 DB row가 급격히 늘어난다.

P1에서는 다음 셀만 저장한다.

```text
cell_metadata P1 정책:
- table header cell
- formula cell
- merged cell
- citation 대상 cell_range 안의 대표 cell
- gold query expected location에 걸린 cell
```

전체 cell-level 정규화는 P2로 미룬다.

### 6.3 normalized metadata 확인 SQL

```sql
select count(*) as pdf_artifacts
from parsed_artifact
where artifact_type = 'PDF_PARSED_JSON';

select count(*) as pdf_pages
from pdf_page_metadata;

select count(*) as table_metadata_count
from table_metadata;

select count(*) as cell_metadata_count
from cell_metadata;
```

PDF search unit metadata completeness:

```sql
select count(*) as pdf_missing_metadata
from search_unit
where source_file_type = 'PDF'
  and (
    parser_version is null
    or location_json is null
    or citation_text is null
    or location_json ->> 'physical_page_index' is null
    or location_json ->> 'page_no' is null
  );
```

XLSX/PDF 전체 metadata completeness:

```sql
select
  count(*) filter (
    where source_file_type = 'SPREADSHEET'
  ) as spreadsheet_units,
  count(*) filter (
    where source_file_type = 'SPREADSHEET'
      and (
        parser_version is null
        or location_json is null
        or citation_text is null
      )
  ) as spreadsheet_missing_metadata,
  count(*) filter (
    where source_file_type = 'PDF'
  ) as pdf_units,
  count(*) filter (
    where source_file_type = 'PDF'
      and (
        parser_version is null
        or location_json is null
        or citation_text is null
      )
  ) as pdf_missing_metadata
from search_unit;
```

---

## 7. gold query v0를 실제 평가셋으로 확장

현재 `eval/gold_queries_v0.csv`는 seed 수준이다.
P1에서는 CSV를 “샘플 질문 파일”이 아니라 실제 평가 가능한 라벨 파일로 바꾼다.

### 7.1 추천 CSV 컬럼

```text
query_id,
bucket,
query,
expected_answer_text,
expected_source_file_id,
expected_file_name,
expected_document_id,
expected_document_version_id,
expected_search_unit_id,
expected_chunk_type,
expected_location_type,
expected_sheet_name,
expected_cell_range,
expected_physical_page_index,
expected_page_no,
expected_page_label,
expected_bbox,
must_contain_terms,
label_status,
labeler,
notes
```

### 7.2 bucket별 목표 개수

처음 목표는 70~80개다.

| bucket | 개수 |
|---|---:|
| `xlsx_lookup` | 15 |
| `xlsx_formula_value` | 10 |
| `xlsx_header_ambiguous` | 10 |
| `xlsx_aggregation` | 10 |
| `pdf_page_lookup` | 10 |
| `pdf_section_question` | 10 |
| `pdf_table_lookup` | 8 |
| `mixed_text_table` | 7 |

총 80개.

### 7.3 중요한 기준

질문 수보다 중요한 것은 live id 매핑이다.

다음 컬럼이 없으면 eval gate가 느슨해진다.

```text
expected_document_version_id
expected_search_unit_id
expected_location_type
expected_sheet_name
expected_cell_range
expected_physical_page_index
expected_page_no
expected_page_label
expected_bbox
```

### 7.4 gold query live binding용 SQL

초기에는 자동 생성보다 수동 라벨이 낫다. 먼저 아래 데이터를 뽑아 사람이 질문을 만든다.

```sql
select
  su.id as search_unit_id,
  su.source_file_name,
  su.source_file_type,
  su.chunk_type,
  su.location_type,
  su.location_json,
  su.citation_text,
  left(coalesce(su.display_text, su.embedding_text, su.text_content), 300) as preview
from search_unit su
where su.source_file_type in ('SPREADSHEET', 'PDF')
order by su.created_at desc
limit 200;
```

---

## 8. retrieval smoke 추가

현재 smoke는 ingestion smoke다.
P1에서는 retrieval smoke가 필요하다.

### 8.1 검증할 내용

1. xlsx/pdf `search_unit`이 index 대상인지
2. `embedding_text`가 실제 embedding claim payload로 나가는지
3. `index_version`이 부여되는지
4. 검색 query를 던졌을 때 expected `search_unit`이 top-k 안에 드는지
5. citation response가 `location_json` 기준으로 렌더링되는지

### 8.2 추가할 파일

```text
scripts/rag_retrieval_smoke.py
reports/rag_retrieval_smoke_report.json
```

### 8.3 입력/출력

```text
input:
- eval/gold_queries_v0.csv

output:
- reports/rag_retrieval_smoke_report.json
```

### 8.4 metrics

```text
- Hit@5
- Hit@10
- MRR@10
- citation_text_completeness
- parser_version_completeness
- location_json_completeness
- returned_chunk_index_version_completeness
- p95 latency
```

### 8.5 retrieval smoke v0 기준

처음에는 강하게 잡지 않는다.
초기 retrieval smoke의 목적은 통과/실패보다 baseline 숫자 확보다.

```text
retrieval smoke v0 기준:
- test query 10개 이상
- Hit@10 >= 0.70
- citation_text present = 100%
- returned chunk has index_version = 100%
- returned chunk has parser_version = 100%
- p95 retrieval latency 기록
```

---

## 9. index build / promotion / rollback

API부터 만들면 껍데기가 된다.
먼저 gate 계산이 실제로 돌아야 한다.

### 9.1 처리 순서

```text
1. candidate index_version 생성
2. index_build row 생성
3. 대상 search_unit selection
4. embedding/indexing 실행
5. embedding_record 저장
6. eval 실행
7. eval_result 저장
8. gate decision 계산
9. passed인 경우만 promote 가능
10. rollback은 이전 active index_version으로 복귀
```

### 9.2 추천 상태 전이

```text
CREATED
  -> BUILDING
  -> BUILT
  -> EVALUATING
  -> EVALUATED
  -> PROMOTED
```

실패 상태:

```text
BUILD_FAILED
EVAL_FAILED
PROMOTION_BLOCKED
ROLLED_BACK
```

### 9.3 promotion gate 단계

아직 gold query가 seed 수준이므로 처음부터 blocking gate로 시작하지 않는다.

| 단계 | gate 성격 |
|---|---|
| v0 | report-only |
| v1 | fatal condition만 block |
| v2 | metric threshold block |
| v3 | bucket regression block |

### 9.4 report-only gate에서 바로 block할 fatal condition

report-only라도 아래는 막아야 한다.

```text
- candidate index_version에 indexable chunk가 0개
- xlsx/pdf search_unit 중 required metadata missing
- parser_version 누락
- citation_text 누락
- location_json 누락
- eval 실행 실패
- fatal_warning_count > 0
```

---

## 10. P1 성공 기준

| 항목 | 기준 |
|---|---:|
| 실제 PDF batch smoke | 8~10개 중 90% 이상 통과 |
| PDF metadata missing count | 0 |
| XLSX metadata missing count | 0 |
| `pdf_page_metadata` 적재 | parsed PDF pages 기준 95% 이상 |
| `table_metadata` 적재 | detected table 기준 90% 이상 |
| gold query v0 | 최소 70개, 권장 80개 |
| gold query live id binding | 90% 이상 |
| retrieval smoke Hit@10 | 최초 baseline 기록 |
| citation response completeness | 100% |
| `index_build` lifecycle | candidate 생성부터 evaluated까지 동작 |
| promotion gate | report 생성 가능 |
| rollback skeleton | 이전 active version으로 복귀 가능 |

---

## 11. 2주 실행 계획

### 11.1 1주차: metadata와 gold query 기반 다지기

| 일차 | 작업 | 산출물 |
|---|---|---|
| 1일차 | 실제 PDF batch smoke runner 작성 | `rag_pdf_ingestion_sample_batch.py` |
| 2일차 | PDF sample manifest 8~10개 작성 및 실행 | PDF batch smoke report |
| 3일차 | `pdf_page_metadata` writer 구현 | page metadata rows |
| 4일차 | `table_metadata` writer 구현 | xlsx/pdf table metadata rows |
| 5일차 | gold query live id binding script 작성 | `gold_queries_v0.csv` 40개 이상 |

1주차 종료 기준:

```text
- PDF batch smoke 통과
- pdf_page_metadata 적재 확인
- table_metadata 적재 확인
- gold query 40개 이상 live id 연결
```

### 11.2 2주차: retrieval eval과 index lifecycle

| 일차 | 작업 | 산출물 |
|---|---|---|
| 1일차 | gold query 70~80개 확장 | completed `gold_queries_v0.csv` |
| 2일차 | retrieval smoke runner 구현 | `rag_retrieval_smoke_report.json` |
| 3일차 | `index_build` lifecycle 구현 | candidate index build |
| 4일차 | eval gate report-only 구현 | `eval_result` 저장 |
| 5일차 | promote/rollback API skeleton | API + targeted tests |

2주차 종료 기준:

```text
- candidate index_version 생성 가능
- eval_result 저장 가능
- promotion decision report 생성 가능
- active index_version 교체/rollback skeleton 동작
```

---

## 12. 오늘 바로 실행할 순서

### 12.1 PDF 실제 샘플 manifest 만들기

```text
samples/rag_pdf_ingestion_manifest.json
```

PDF를 아래 bucket으로 분류한다.

```text
pdf_native_text
pdf_section_question
pdf_table_lookup
pdf_multi_page
pdf_ocr_required
```

### 12.2 PDF batch smoke runner 작성

```text
scripts/rag_pdf_ingestion_sample_batch.py
```

기존 XLSX batch smoke runner 구조를 거의 재사용한다.

검증 항목:

```text
- source READY
- job SUCCEEDED
- PDF_PARSED_JSON exists
- PDF_PLAINTEXT exists
- search_unit count >= expected
- parser_name = pymupdf
- parser_version = pdf-extract-v1
- location_json has physical_page_index/page_no/page_label
- citation_text is not null
- missing_pdf_metadata = 0
```

### 12.3 normalized metadata 적재 현황 확인

```sql
select count(*) as pdf_artifacts
from parsed_artifact
where artifact_type = 'PDF_PARSED_JSON';

select count(*) as pdf_pages
from pdf_page_metadata;

select count(*) as table_metadata_count
from table_metadata;

select count(*) as cell_metadata_count
from cell_metadata;
```

### 12.4 gold query live binding 시작

```sql
select
  su.id as search_unit_id,
  su.source_file_name,
  su.source_file_type,
  su.chunk_type,
  su.location_type,
  su.location_json,
  su.citation_text,
  left(coalesce(su.display_text, su.embedding_text, su.text_content), 300) as preview
from search_unit su
where su.source_file_type in ('SPREADSHEET', 'PDF')
order by su.created_at desc
limit 200;
```

### 12.5 retrieval smoke 설계

```text
input:
- eval/gold_queries_v0.csv

output:
- reports/rag_retrieval_smoke_report.json

metrics:
- Hit@5
- Hit@10
- MRR@10
- citation_text_completeness
- parser_version_completeness
- location_json_completeness
- p95 latency
```

---

## 13. Codex 작업 지시 요약

아래 내용은 Codex에 그대로 전달할 수 있는 작업 지시다.

```text
현재 RAG ingestion v2 P0는 닫혔다.

이미 완료된 것:
- generated XLSX smoke passed
- real XLSX batch smoke passed: 8/8
- PDF smoke passed
- spreadsheet_missing_metadata=0
- pdf_missing_metadata=0
- Java targeted tests 97 passed
- Python targeted tests 33 passed
- PyMuPDF dependency path fixed for Python 3.13

이번 작업 목표:
P1로 넘어가서 실제 PDF batch smoke, normalized metadata writes, gold query live binding, retrieval smoke, index promotion gate skeleton을 구현한다.

절대 하지 말 것:
- hybrid retrieval
- reranker
- LLM answer prompt tuning
- agentic RAG
- 모든 cell_metadata full dump
- promotion API만 먼저 만드는 것

작업 순서:
1. Add `samples/rag_pdf_ingestion_manifest.json`.
2. Add `scripts/rag_pdf_ingestion_sample_batch.py`, modeled after `scripts/rag_ingestion_sample_batch.py`.
3. Validate 8-10 real PDF samples:
   - source READY
   - job SUCCEEDED
   - PDF_PARSED_JSON exists
   - PDF_PLAINTEXT exists
   - search_unit count >= expected
   - parser_name=pymupdf
   - parser_version=pdf-extract-v1
   - location_json has physical_page_index/page_no/page_label
   - citation_text present
   - missing PDF metadata count = 0
4. Implement normalized metadata population:
   - `pdf_page_metadata` from PDF parsed artifact
   - `table_metadata` from XLSX/PDF parsed artifacts
   - keep `cell_metadata` selective for formula/merged/header/citation cells only
5. Expand `eval/gold_queries_v0.csv` toward 70-80 rows and bind rows to live:
   - document_version_id
   - search_unit_id
   - location_json fields
   - citation_text
6. Add `scripts/rag_retrieval_smoke.py`:
   - read gold query CSV
   - run current retrieval path
   - compute Hit@5, Hit@10, MRR@10, citation completeness, p95 latency
   - write `reports/rag_retrieval_smoke_report.json`
7. Implement report-only promotion gate:
   - create candidate index_version
   - run eval
   - write eval_result
   - do not block promotion yet except fatal metadata failures
8. Add progress log entry to `docs/rag-ingestion-progress.md`.

Verification required:
- `mvn -f core-api\pom.xml -DskipTests compile`
- Java targeted tests
- Python targeted tests
- `python -m py_compile` for new scripts
- PDF batch smoke report generated
- Retrieval smoke report generated
- DB metadata completeness queries return 0 missing rows
```

---

## 14. 검증 명령어

### 14.1 Java

```powershell
mvn -f core-api\pom.xml -DskipTests compile
```

Targeted tests:

```powershell
mvn -f core-api\pom.xml test "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest,JobSubmissionValidatorTest,RedisJobDispatchAdapterTest"
```

### 14.2 Python

```powershell
python -m py_compile scripts\rag_ingestion_smoke.py scripts\rag_ingestion_sample_batch.py scripts\rag_pdf_ingestion_smoke.py scripts\rag_pdf_ingestion_sample_batch.py scripts\rag_retrieval_smoke.py
```

```powershell
python -m pytest tests\test_chunk_text_builder.py tests\test_search_unit_indexing.py tests\test_search_unit_indexing_loop.py tests\test_xlsx_extract_capability.py tests\test_pdf_extract_capability.py tests\test_rag_ingestion_scaffolding.py
```

### 14.3 Smoke

```powershell
python scripts\rag_pdf_ingestion_sample_batch.py
```

```powershell
python scripts\rag_retrieval_smoke.py
```

### 14.4 Diff hygiene

```powershell
git diff --check
```

---

## 15. 진행 로그에 남길 entry template

```md
## 2026-05-03 - P1 normalized metadata and retrieval eval progress

### Goal

Move from ingestion smoke success to evaluated, promotable RAG ingestion workflow.

### Completed

- Added real PDF batch smoke manifest and runner.
- Populated `pdf_page_metadata` from `PDF_PARSED_JSON`.
- Populated `table_metadata` from XLSX/PDF parsed artifacts.
- Expanded `eval/gold_queries_v0.csv` with live document/search_unit/location ids.
- Added retrieval smoke runner.
- Added report-only promotion gate skeleton.

### Verification

- PDF batch smoke:
  - Command:
  - Result:
- Retrieval smoke:
  - Command:
  - Result:
- DB metadata completeness:
  - spreadsheet_missing_metadata:
  - pdf_missing_metadata:
  - pdf_page_metadata coverage:
  - table_metadata coverage:
- Java compile/tests:
- Python tests:
- `git diff --check`:

### Important Decisions

- Kept `cell_metadata` selective in P1.
- Kept promotion gate report-only except fatal metadata failures.
- Did not add hybrid/reranker in this phase.

### Remaining Work

- Expand gold query set to full 70-80 rows if not complete.
- Add promote/rollback API after gate result is stable.
- Add bucket-level regression thresholds.

### Next Recommended Step

Run candidate index build against the completed gold query v0 and record the first retrieval baseline.
```

---

## 16. 최종 판단

현재 리스크는 더 이상 “xlsx/pdf가 들어가느냐”가 아니다.
P0에서 그 부분은 충분히 증명했다.

이제 리스크는 세 가지다.

1. PDF 다양성 리스크
   PDF smoke가 통과했지만 PDF real batch 검증은 XLSX만큼 강하지 않다.

2. 평가셋 부재 리스크
   gold query가 seed 수준이면 promotion gate가 의미 없다.

3. index lifecycle 리스크
   candidate index를 만들고, 평가하고, active로 승격하고, rollback하는 흐름이 아직 없다.

따라서 다음 스텝은 아래 순서로 고정한다.

```text
PDF batch smoke
  -> normalized metadata
  -> gold query live binding
  -> retrieval smoke
  -> report-only eval gate
  -> promotion/rollback API skeleton
```
