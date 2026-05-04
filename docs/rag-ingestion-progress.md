# RAG Ingestion Progress Log

This document tracks implementation progress for the xlsx/pdf RAG ingestion expansion.
Append a new entry after each work turn so design choices, code changes, verification, and remaining work stay visible.

## 2026-05-03 - xlsx/pdf ingestion v2 MVP foundation

### Goal

Move from abstract xlsx/pdf RAG ingestion design into a concrete MVP implementation on the existing local PostgreSQL/Flyway and `source_file -> extracted_artifact -> search_unit` flow.

### Completed

- Added Flyway migration `V7__document_ingestion_v2.sql`.
  - New v2 tables: `document`, `document_version`, `parsed_artifact`.
  - Supporting tables: `table_metadata`, `cell_metadata`, `pdf_page_metadata`, `embedding_record`, `index_build`, `citation`, `eval_dataset`, `eval_query`, `eval_result`.
  - Extended `search_unit` with v2 fields:
    - `document_id`
    - `document_version_id`
    - `parsed_artifact_id`
    - `source_file_name`
    - `source_file_type`
    - `chunk_type`
    - `location_type`
    - `location_json`
    - `embedding_text`
    - `bm25_text`
    - `display_text`
    - `citation_text`
    - `debug_text`
    - `parser_name`
    - `parser_version`
    - `index_version`
    - `quality_score`
    - `confidence_score`
    - `acl_tags`
- Added JPA persistence classes for v2 document provenance:
  - `DocumentV2JpaEntity`
  - `DocumentV2JpaRepository`
  - `DocumentVersionJpaEntity`
  - `DocumentVersionJpaRepository`
  - `ParsedArtifactV2JpaEntity`
  - `ParsedArtifactV2JpaRepository`
- Updated `DocumentCatalogService`.
  - OCR/XLSX import now creates or refreshes v2 `document`, `document_version`, and primary `parsed_artifact` records.
  - Imported `search_unit` rows now receive v2 ingestion metadata through `applyIngestionV2`.
  - XLSX location JSON includes sheet/range/table/header-ish location fields and `hidden_policy=exclude_hidden`.
  - PDF/OCR location JSON includes page fields, bbox when present, section path, block type, OCR flags, and OCR confidence when available.
  - Citation text is generated as:
    - XLSX: `file > sheet > cell_range`
    - PDF/OCR: `file > p.N > bbox [...]` when bbox exists
- Updated `SearchUnitJpaEntity`.
  - Added v2 columns and getters.
  - Added `applyIngestionV2`.
  - Added `indexVersion` support when marking a unit embedded.
- Updated `SearchUnitIndexingService`.
  - Claim payload now prefers `embedding_text` over legacy `text_content`.
  - Claim metadata now exposes v2 fields such as `locationJson`, `citationText`, `parserVersion`, `chunkType`, and scores.
  - Added v2 citation gate:
    - xlsx/pdf v2 SearchUnits require `parser_version`, `location_json`, and `citation_text`.
    - Units missing required citation/location metadata are skipped instead of indexed.
- Updated worker completion contract.
  - Python `SearchUnitIndexEmbeddedRequest` includes optional `indexVersion`.
  - Worker loop sends the index version returned by the live indexer back to Spring.
- Added Python chunk text builder.
  - New file: `ai-worker/app/capabilities/rag/chunk_text_builder.py`
  - Separates:
    - `embedding_text`
    - `bm25_text`
    - `display_text`
    - `citation_text`
    - `debug_text`
- Added parser artifact fixtures.
  - `ai-worker/tests/fixtures/parsed_artifacts/xlsx_v2_sample.json`
  - `ai-worker/tests/fixtures/parsed_artifacts/pdf_v2_sample.json`
- Added/updated tests for Java and Python paths.
- Fixed Spring bootstrapping blocker in `JobExecutionService` by marking the public constructor with `@Autowired`.

### Verification

- Java compile:
  - `mvn -f core-api/pom.xml -DskipTests compile`
  - Result: passed
- Java targeted tests:
  - `mvn -f core-api/pom.xml test "-Dtest=DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest"`
  - Result: 26 tests passed
- Python targeted tests:
  - `python -m pytest tests/test_chunk_text_builder.py tests/test_search_unit_indexing.py tests/test_search_unit_indexing_loop.py`
  - Result: 17 tests passed
- Flyway/local PostgreSQL verification:
  - Local database applied migrations v1 through v7 successfully.
  - Confirmed v2 tables exist.
  - Confirmed `search_unit` v2 columns exist.
- Diff hygiene:
  - `git diff --check`
  - Result: passed

### Important Decisions

- Keep the existing `source_file -> extracted_artifact -> search_unit` production path.
- Add v2 document provenance alongside the existing path instead of replacing the path in one step.
- Do not index xlsx/pdf SearchUnits without citation-capable location metadata.
- Keep `embedding_text`, `bm25_text`, `display_text`, and `citation_text` separate.
- Keep OCR confidence lower-trust metadata explicit; do not treat OCR as equivalent to native PDF text.

### Remaining Work

- Populate `table_metadata`, `cell_metadata`, and `pdf_page_metadata` from parsed artifacts.
- Add true PDF text extraction path with `pymupdf`/bbox support beyond the current OCR-oriented path.
- Add Spring API endpoints for index build, promotion, rollback, and eval run.
- Add smoke test that uploads/loads one xlsx and one pdf fixture and verifies generated DB rows end to end.
- Add eval gate implementation for candidate `index_version` promotion.

### Next Recommended Step

Run an actual xlsx sample through the current `XLSX_EXTRACT` path and verify that rows are created in:

- `source_file`
- `extracted_artifact`
- `document`
- `document_version`
- `parsed_artifact`
- `search_unit`

Then inspect the generated `search_unit.location_json`, `citation_text`, `parser_version`, and `embedding_status`.

## 2026-05-03 - v2 citation response and xlsx ingestion smoke runner

### Goal

Continue the xlsx/pdf ingestion MVP by making v2 citation fields visible in the user-facing library search response and adding a repeatable smoke runner for generated XLSX samples.

### Completed

- Updated `DocumentCatalogController` search response.
  - `SearchUnitResponse` now exposes v2 fields:
    - `sourceFileType`
    - `chunkType`
    - `locationType`
    - `locationJson`
    - `displayText`
    - `citationText`
    - `parserName`
    - `parserVersion`
    - `indexVersion`
  - `Citation` now exposes:
    - `citationText`
    - `locationType`
    - `locationJson`
    - `chunkType`
    - `parserVersion`
    - `indexVersion`
    - `physicalPageIndex`
    - `pageNo`
    - `pageLabel`
  - Citation rendering now prefers v2 `location_json` over legacy `metadata_json`.
  - XLSX citation now resolves `sheet_name`, `sheet_index`, `cell_range`, and `table_id` from v2 location JSON.
  - PDF citation now resolves `physical_page_index`, `page_no`, `page_label`, and `bbox` from v2 location JSON.
- Added controller tests for v2 citation rendering.
  - XLSX test verifies that v2 location JSON overrides stale legacy metadata.
  - PDF test verifies physical page index, logical page number, page label, bbox, and parser version exposure.
- Added `scripts/rag_ingestion_smoke.py`.
  - Generates a sample XLSX workbook with:
    - visible sheet
    - hidden sheet
    - merged title cell
    - Excel table
    - hidden column
    - formula cells
  - Uploads the file through `/api/v1/library/source-files`.
  - Starts `/api/v1/library/source-files/{sourceFileId}/xlsx-extract`.
  - Polls `/api/v1/jobs/{jobId}`.
  - Optionally checks PostgreSQL through `docker exec ... psql`.
  - Verifies minimum v2 DB conditions:
    - source file is `READY`
    - extracted artifacts exist
    - document version exists
    - parsed artifact exists
    - SearchUnits exist
    - v2-ready SearchUnits have `parser_version`, `location_json`, and `citation_text`
    - no spreadsheet SearchUnit is missing required v2 citation metadata

### Verification

- Java targeted tests:
  - `mvn -f core-api/pom.xml test "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest"`
  - Result: 34 tests passed
- Python syntax check:
  - `python -m py_compile scripts/rag_ingestion_smoke.py`
  - Result: passed
- Smoke runner help check:
  - `python scripts/rag_ingestion_smoke.py --help`
  - Result: passed
- Python targeted tests:
  - `python -m pytest tests/test_chunk_text_builder.py tests/test_search_unit_indexing.py tests/test_search_unit_indexing_loop.py tests/test_xlsx_extract_capability.py`
  - Result: 24 tests passed

### Important Decisions

- User-facing citation should not depend only on legacy `metadata_json`.
- `location_json` is the authoritative source for xlsx/pdf citation when present.
- The smoke runner should generate its own XLSX file so the test is repeatable and does not depend on a manually maintained binary fixture.
- DB validation remains explicit and environment-aware; the smoke runner can skip DB checks with `--skip-db-check` when only API/job behavior is being tested.

### Remaining Work

- Run the new smoke runner against live `core-api` and `ai-worker`.
- Add a PDF smoke runner once true PDF text extraction and page/bbox metadata are wired beyond OCR-lite.
- Populate normalized `table_metadata`, `cell_metadata`, and `pdf_page_metadata` tables from parsed artifacts.
- Add index build/promotion/rollback API and eval gate implementation.

### Next Recommended Step

Start `core-api` and `ai-worker`, then run:

```powershell
python scripts/rag_ingestion_smoke.py
```

If only the HTTP job flow is being checked without DB access:

```powershell
python scripts/rag_ingestion_smoke.py --skip-db-check
```

## 2026-05-03 - next execution plan for live samples, PDF parser, eval gate

### Goal

Fix the next implementation sequence for RAG ingestion v2 without expanding into hybrid retrieval, reranking, or agentic RAG.

### Current Priority

1. Run the live XLSX smoke runner against `core-api` and `ai-worker`.
2. Add a batch XLSX smoke manifest for 8-10 real samples.
3. Implement `pdf-extract-v1` native text extraction before OCR fallback.
4. Persist and expose PDF page/block/bbox metadata.
5. Create xlsx/pdf gold query v0.
6. Implement candidate `index_version` eval gate.
7. Add promotion/rollback API skeleton after the gate has concrete metrics.

### Live XLSX Smoke Checklist

- Confirm infra:
  - `docker compose ps`
  - Flyway is at v7.
  - PostgreSQL contains `document`, `document_version`, `parsed_artifact`, and v2 `search_unit` columns.
- Confirm services:
  - `core-api` is running on `http://localhost:8080`.
  - `ai-worker` is running with `XLSX_EXTRACT` enabled.
  - Worker can reach `core-api`.
  - Internal secret configuration matches between core and worker if enabled.
- Run:
  - `python scripts/rag_ingestion_smoke.py`
- DB failure triage queries:

```sql
select id, original_file_name, file_type, status, status_detail
from source_file
order by uploaded_at desc
limit 10;

select id, capability, status, error_code, error_message, created_at, updated_at
from job
order by created_at desc
limit 10;

select artifact_id, source_file_id, artifact_type, pipeline_version, storage_uri
from extracted_artifact
where source_file_id = :source_file_id
order by artifact_type;

select id, document_id, source_file_id, parse_status, parse_status_detail
from document_version
where source_file_id = :source_file_id;

select id, parser_name, parser_version, file_type, quality_score
from parsed_artifact
where source_file_id = :source_file_id;

select id, unit_type, unit_key, chunk_type, source_file_type,
       parser_version, citation_text, location_json, embedding_status
from search_unit
where source_file_id = :source_file_id
order by unit_type, unit_key;

select count(*) as missing_required_v2_metadata
from search_unit
where source_file_id = :source_file_id
  and source_file_type in ('SPREADSHEET', 'PDF')
  and (parser_version is null or location_json is null or citation_text is null);
```

### Batch XLSX Smoke Manifest Shape

Batch smoke should be manifest-driven so real samples can be added without changing test code.

```json
{
  "manifest_version": "rag-ingestion-batch-v0",
  "default_expectations": {
    "min_search_units": 3,
    "require_parser_version": true,
    "require_location_json": true,
    "require_citation_text": true,
    "hidden_policy": "exclude_hidden"
  },
  "samples": [
    {
      "sample_id": "xlsx_simple_table_001",
      "path": "samples/xlsx/simple_table.xlsx",
      "file_type": "xlsx",
      "bucket": "xlsx_lookup",
      "expected": {
        "min_tables": 1,
        "min_row_group_chunks": 1,
        "must_have_sheet_names": ["매출현황"],
        "must_have_cell_ranges": ["A3:F20"],
        "must_exclude_hidden": true
      }
    }
  ]
}
```

Recommended 8-10 XLSX sample buckets:

- `xlsx_simple_table`: one visible sheet, one clean Excel table.
- `xlsx_multi_sheet_hidden`: visible and hidden sheets; hidden excluded by default.
- `xlsx_merged_header`: merged title/header cells.
- `xlsx_multirow_header`: two or more header rows requiring flattened header paths.
- `xlsx_formula_cached_value`: formula text plus cached value.
- `xlsx_date_number_format`: date, percent, currency, and unit formatting.
- `xlsx_large_row_group`: large sheet that must produce row-group chunks.
- `xlsx_sparse_blank_cells`: sparse data and blank cells.
- `xlsx_units_currency_period`: unit, currency, and period columns.
- `xlsx_mixed_text_table`: explanatory text plus table in one sheet.

### PDF Sample Classification

- Native text PDF:
  - Text layer exists.
  - Extracted character count per page is above threshold.
  - Blocks have usable bbox coordinates.
  - OCR is not needed.
- Table-centered PDF:
  - Text layer may exist, but answer evidence is mostly in tables.
  - Page contains many aligned text blocks, table ruling lines, or dense cell-like layout.
  - Needs table chunk and optionally markdown display text.
- OCR-needed PDF:
  - Text layer missing or nearly empty.
  - Image coverage is high.
  - Native extraction yields low text density.
  - OCR confidence must be stored and used as lower-trust metadata.

### PDF Parser v1 Contract

Use `pymupdf` as `pdf-extract-v1` for native text first. OCR remains fallback.

```json
{
  "document_version_id": "docv_contract_001",
  "parser_name": "pymupdf",
  "parser_version": "pdf-extract-v1",
  "file_type": "pdf",
  "pages": [
    {
      "physical_page_index": 0,
      "page_no": 1,
      "page_label": "1",
      "width": 595.0,
      "height": 842.0,
      "text_layer_present": true,
      "ocr_used": false,
      "blocks": [
        {
          "block_id": "p0_b0",
          "block_type": "paragraph",
          "text": "계약의 목적은 ...",
          "bbox": [72.0, 100.0, 520.0, 160.0],
          "reading_order": 0,
          "section_path": ["1. 목적"]
        }
      ],
      "tables": []
    }
  ],
  "warnings": [],
  "quality_score": 0.88
}
```

SearchUnit `location_json` example:

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
  "ocr_confidence": null
}
```

### Gold Query v0 CSV

Recommended CSV columns:

```text
query_id,bucket,query,expected_file_name,expected_document_version_id,
expected_chunk_type,expected_location_type,expected_sheet_name,
expected_cell_range,expected_physical_page_index,expected_page_no,
expected_page_label,expected_bbox,expected_answer_text,
must_contain_terms,source_sample_id,label_status,notes
```

Minimum query counts:

- `xlsx_lookup`: 15
- `xlsx_aggregation`: 10
- `xlsx_header_ambiguous`: 10
- `xlsx_formula_value`: 10
- `pdf_page_lookup`: 15
- `pdf_section_question`: 15
- `pdf_table_lookup`: 10
- `pdf_ocr_noise`: 8
- `mixed_text_table`: 10

Minimum v0 total: 103 queries.

### Candidate Index Promotion Gate

Initial promotion thresholds:

- `parser_success_rate >= 0.95`
- `unsupported_file_rate <= 0.05`
- `zero_indexable_chunk_count = 0`
- `required_metadata_completeness >= 0.98`
- `xlsx_citation_location_accuracy >= 0.90`
- `pdf_citation_location_accuracy >= 0.85`
- `table_detection_accuracy >= 0.80`
- `OCR_confidence_avg >= 0.75` for OCR-needed bucket only
- `Hit@10 >= baseline - 0.05`
- `MRR@10 >= baseline - 0.05`
- `citation_accuracy >= 0.85`
- `parsing_latency_p95 <= 30s` for normal-sized docs
- `indexing_latency_p95 <= 60s` for smoke batch
- `fatal_warning_count = 0`

### P0 Implementation Work

Spring:

- Add batch smoke DB verification queries to a reusable script or test helper.
- Add PDF parser capability/job route only after Python `pdf-extract-v1` artifact contract exists.
- Add `pdf_page_metadata` population from parsed artifact.
- Add `index_build` status model and repository.
- Add promotion gate result storage in `eval_result`.
- Add minimal promotion/rollback controller skeleton after gate result exists.

Python:

- Add `pdf-extract-v1` parser using PyMuPDF.
- Emit PDF parsed artifact JSON.
- Build page/paragraph/table SearchUnit drafts from PDF parsed artifact.
- Add PDF chunk text builder integration.
- Add PDF parser unit tests with native text fixture.
- Add batch XLSX smoke manifest runner.
- Add gold query CSV fixture and validation script.

### Immediate Commands

```powershell
docker compose ps
docker exec aipipeline-postgres psql -U aipipeline -d aipipeline -c "select version, description, success from flyway_schema_history order by installed_rank;"
python scripts/rag_ingestion_smoke.py
```

If smoke fails, inspect latest source/job rows first, then SearchUnit v2 metadata completeness.

## 2026-05-03 - PDF native parser route, batch smoke scaffolding, and promotion gate seed

### Goal

Continue the RAG ingestion v2 P0 sequence after the xlsx/pdf foundation: validate live XLSX smoke readiness, add native PDF extraction v1, add real-sample smoke scaffolding, and seed the promotion gate/eval files without broad retrieval changes.

### Completed

- Confirmed local infra status:
  - PostgreSQL and Redis are healthy under Docker Compose.
  - Flyway schema history is applied through v7.
  - `document`, `document_version`, `parsed_artifact`, and v2 `search_unit` columns exist.
- Attempted live XLSX smoke:
  - `python scripts/rag_ingestion_smoke.py`
  - Result: failed because `core-api` was not reachable on `http://localhost:8080`.
- Added `PDF_EXTRACT` end-to-end wiring.
  - Spring enum/dispatch/validation/controller/callback path now supports `/api/v1/library/source-files/{sourceFileId}/pdf-extract`.
  - PDF worker capability emits `PDF_PARSED_JSON` and `PDF_PLAINTEXT`.
  - `DocumentCatalogService` imports native PDF parsed artifacts into v2 document provenance and `search_unit` rows with PDF `location_json`, `citation_text`, parser metadata, bbox, page labels, and `ocr_used=false`.
- Added native PDF parser v1 in the worker.
  - Uses PyMuPDF/`fitz` when available.
  - Emits `parser_name=pymupdf`, `parser_version=pdf-extract-v1`, page/block/bbox metadata, warnings for empty text layers, and no OCR fallback in v1.
- Added real-sample XLSX batch smoke scaffolding.
  - `samples/rag_ingestion_manifest.json`
  - `scripts/rag_ingestion_sample_batch.py`
  - Uses 8 existing XLSX files under `datasets/xlsx`.
- Added PDF smoke runner.
  - `scripts/rag_pdf_ingestion_smoke.py`
  - Supports `--file` or generated text-layer PDF fallback and validates PDF v2 metadata when DB access is available.
- Added eval/promotion seed artifacts.
  - `eval/gold_queries_v0.csv`
  - `ai-worker/eval/harness/rag_ingestion_promotion_gate.py`
  - `ai-worker/tests/test_rag_ingestion_scaffolding.py`

### Verification

- Java compile:
  - `mvn -f core-api\pom.xml -DskipTests compile`
  - Result: passed
- Java targeted tests:
  - `mvn -f core-api\pom.xml test "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest,JobSubmissionValidatorTest,RedisJobDispatchAdapterTest"`
  - Result: 97 tests passed
- Python syntax checks:
  - `python -m py_compile scripts\rag_ingestion_smoke.py scripts\rag_ingestion_sample_batch.py scripts\rag_pdf_ingestion_smoke.py`
  - `python -m py_compile app\capabilities\pdf\__init__.py app\capabilities\pdf\artifact_builder.py app\capabilities\pdf\service.py app\capabilities\registry.py app\core\config.py eval\harness\rag_ingestion_promotion_gate.py tests\test_pdf_extract_capability.py tests\test_rag_ingestion_scaffolding.py`
  - Result: passed
- Python targeted tests:
  - `python -m pytest tests\test_chunk_text_builder.py tests\test_search_unit_indexing.py tests\test_search_unit_indexing_loop.py tests\test_xlsx_extract_capability.py tests\test_pdf_extract_capability.py tests\test_rag_ingestion_scaffolding.py`
  - Result: 31 passed, 2 skipped
  - Skipped tests require `fitz` in the current Python 3.13 environment.
- Smoke runner help checks:
  - `python scripts\rag_ingestion_sample_batch.py --help`
  - `python scripts\rag_pdf_ingestion_smoke.py --help`
  - `python scripts\rag_ingestion_smoke.py --help`
  - Result: passed
- Manifest sanity:
  - 8 manifest samples found and all referenced XLSX files exist.
- Diff hygiene:
  - `git diff --check`
  - Result: passed, with only existing LF-to-CRLF warnings.

### Important Decisions

- Kept the existing production path and added `PDF_EXTRACT` beside OCR/XLSX instead of replacing OCR-lite.
- Native PDF v1 does not OCR empty pages; it emits `PDF_TEXT_LAYER_EMPTY` and `OCR_REQUIRED` warnings.
- `PDF_PARSED_JSON` is the primary parsed artifact for native PDF, while `PDF_PLAINTEXT` is a supporting artifact.
- Gold query v0 rows remain seed placeholders until live ingestion creates stable document/chunk/location ids.

### Remaining Work

- Start `core-api` and `ai-worker`, then rerun `python scripts/rag_ingestion_smoke.py`.
- Run `python scripts/rag_ingestion_sample_batch.py` against live services and inspect the generated report.
- Run `python scripts/rag_pdf_ingestion_smoke.py` after the live worker has PyMuPDF available.
- Populate normalized `pdf_page_metadata`, `table_metadata`, and `cell_metadata`.
- Replace placeholder gold rows with live document/chunk/location ids after sample ingestion.

### Next Recommended Step

Bring up `core-api` and `ai-worker`, then run the generated XLSX smoke first. If that passes, run the sample batch and PDF smoke runners before moving to normalized metadata table population.

## 2026-05-03 - live XLSX/PDF smoke completed and report artifacts captured

### Goal

Close the remaining P0 evidence gap from the previous entry by running the generated XLSX smoke, real XLSX batch smoke, and PDF smoke against live `core-api`, `ai-worker`, Redis, and PostgreSQL.

### Completed

- Started local `core-api` and `ai-worker` with RAG/OCR-heavy startup disabled for a focused ingestion smoke run.
- Fixed live smoke blockers found during execution:
  - Added UTF-8 decoding to smoke-runner `docker exec psql` calls so Korean citation JSON does not fail on Windows CP949 stdout decoding.
  - Raised Spring multipart limits to support multi-MB real XLSX uploads.
  - Added `UPLOAD_TOO_LARGE` handling for multipart size failures.
  - Increased worker core-api request timeout to 60s for large artifact upload/import callbacks.
  - Added PyMuPDF to the active Python dependency path as `pymupdf>=1.26,<2`; Python 3.13 installed `pymupdf 1.27.2.3`.
- Generated XLSX live smoke passed:
  - Command: `python scripts\rag_ingestion_smoke.py`
  - Report: `reports/rag_ingestion_smoke_report.json`
  - Result: `status=PASSED`, source `READY`, job `SUCCEEDED`, `search_unit_count=3`, `missing_citation_count=0`.
- Real XLSX batch smoke passed:
  - Command: `python scripts\rag_ingestion_sample_batch.py`
  - Report: `reports/rag_ingestion_sample_batch_report.json`
  - Result: `total_samples=8`, `passed=8`, `failed=0`.
  - Metrics: `parser_success_rate=1.0`, `zero_indexable_chunk_count=0`, `missing_required_metadata_count=0`.
  - Replaced one mislabeled `.xlsx` sample that was not a ZIP workbook with a valid vehicle-registration workbook.
  - Added expected sheet and citation-pattern checks to the manifest-backed batch runner.
- PDF live smoke passed:
  - Command: `python scripts\rag_pdf_ingestion_smoke.py`
  - Report: `reports/rag_pdf_ingestion_smoke_report.json`
  - Result: `status=PASSED`, source `READY`, job `SUCCEEDED`, `pdf_search_unit_count=4`, `missing_pdf_citation_metadata=0`, `invalid_pdf_location_count=0`.

### DB Checks

- Aggregate v2 metadata completeness:
  - `spreadsheet_units=9362`
  - `spreadsheet_missing_metadata=0`
  - `pdf_units=4`
  - `pdf_missing_metadata=0`
  - `xlsx_jobs=37`
  - `pdf_jobs=1`
- Parsed artifact summary:
  - `XLSX_WORKBOOK_JSON | openpyxl | xlsx-extract-v1 | xlsx = 34`
  - `PDF_PARSED_JSON | pymupdf | pdf-extract-v1 | pdf = 1`
- Latest PDF artifacts:
  - `PDF_PARSED_JSON`
  - `PDF_PLAINTEXT`
  - both with `pipeline_version=pdf-extract-v1`

### Verification

- Java compile:
  - `mvn -f core-api\pom.xml -DskipTests compile`
  - Result: passed
- Java targeted tests:
  - `mvn -f core-api\pom.xml test "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest,JobSubmissionValidatorTest,RedisJobDispatchAdapterTest"`
  - Result: 97 tests passed
- Python syntax checks:
  - `python -m py_compile scripts\rag_ingestion_smoke.py scripts\rag_ingestion_sample_batch.py scripts\rag_pdf_ingestion_smoke.py`
  - Result: passed
- Python targeted tests:
  - `python -m pytest tests\test_chunk_text_builder.py tests\test_search_unit_indexing.py tests\test_search_unit_indexing_loop.py tests\test_xlsx_extract_capability.py tests\test_pdf_extract_capability.py tests\test_rag_ingestion_scaffolding.py`
  - Result: 33 tests passed
- Diff hygiene:
  - `git diff --check`
  - Result: passed, with only LF-to-CRLF working-copy warnings.

### Remaining Work

- Expand `eval/gold_queries_v0.csv` from seed rows toward the 70-80 target and bind rows to live document/chunk/location ids.
- Populate normalized `pdf_page_metadata`, `table_metadata`, and `cell_metadata`.
- Add index build/promote/rollback/eval API workflow on top of the current offline promotion gate skeleton.

## 2026-05-03 - P1 real PDF batch smoke runner and live report

### Goal

Move the PDF side from a single smoke sample to a repeatable real-sample batch smoke at the start of P1.

### Completed

- Added `samples/rag_pdf_ingestion_manifest.json`.
  - Uses 8 real PDFs from `datasets/golden/kovidore-economic/hf_snapshot/pdfs`.
  - Covers `pdf_native_text`, `pdf_section_question`, `pdf_table_lookup`, and `pdf_multi_page` buckets.
- Added `scripts/rag_pdf_ingestion_sample_batch.py`.
  - Reads a PDF manifest.
  - Uploads each PDF.
  - Starts `pdf-extract`.
  - Polls job completion.
  - Optionally validates PostgreSQL rows.
  - Writes `reports/rag_pdf_ingestion_sample_batch_report.json`.
- Updated `ai-worker/tests/test_rag_ingestion_scaffolding.py`.
  - Verifies PDF manifest sample paths.
  - Verifies PDF batch DB-report validation behavior.
- Ran the new PDF batch smoke against live `core-api`, `ai-worker`, Redis, and PostgreSQL.
  - Result: 8/8 passed.
  - Report: `reports/rag_pdf_ingestion_sample_batch_report.json`.
  - Aggregate metrics:
    - `parser_success_rate=1.0`
    - `zero_indexable_chunk_count=0`
    - `missing_required_metadata_count=0`
    - `invalid_pdf_location_count=0`
    - `missing_pdf_citation_text_count=0`

### Verification

- Python syntax:
  - `python -m py_compile scripts\rag_pdf_ingestion_sample_batch.py scripts\rag_pdf_ingestion_smoke.py scripts\rag_ingestion_sample_batch.py`
  - Result: passed
- Smoke runner help:
  - `python scripts\rag_pdf_ingestion_sample_batch.py --help`
  - Result: passed
- Python scaffolding tests:
  - `python -m pytest ai-worker\tests\test_rag_ingestion_scaffolding.py`
  - Result: 7 passed
- Python targeted ingestion tests:
  - `python -m pytest tests\test_chunk_text_builder.py tests\test_search_unit_indexing.py tests\test_search_unit_indexing_loop.py tests\test_xlsx_extract_capability.py tests\test_pdf_extract_capability.py tests\test_rag_ingestion_scaffolding.py`
  - Result: 35 passed
- Live PDF batch smoke:
  - `python scripts\rag_pdf_ingestion_sample_batch.py`
  - Result: 8 passed, 0 failed
- DB metadata completeness:
  - `pdf_units=43094`
  - `pdf_missing_metadata=0`
  - `pdf_page_metadata_count=0`
  - `table_metadata_count=0`
  - `cell_metadata_count=0`
- Diff hygiene:
  - `git diff --check`
  - Result: passed, with existing LF-to-CRLF working-copy warnings

### Important Decisions

- Kept the runner manifest-driven, mirroring the existing XLSX batch smoke pattern.
- Treated bbox as required for actual PDF text block chunks, not document-summary rows.
- Did not start retrieval, hybrid search, reranker, or promotion API work in this slice.

### Remaining Work

- Populate `pdf_page_metadata` from `PDF_PARSED_JSON`.
- Populate `table_metadata` from XLSX/PDF parsed artifacts.
- Expand and live-bind `eval/gold_queries_v0.csv`.
- Add retrieval smoke and report-only eval gate persistence.

### Next Recommended Step

Implement `pdf_page_metadata` population first, then make the PDF batch runner enforce normalized page metadata coverage in addition to `search_unit.location_json` completeness.

## 2026-05-03 - P1 normalized metadata, eval persistence, and report-only gate

### Goal

Lift the XLSX/PDF RAG ingestion MVP from parser smoke coverage to P1 normalized metadata and report-only promotion-gate readiness without changing the production `source_file -> extracted_artifact -> search_unit` path.

### Completed

- Populated normalized PDF page metadata from `PDF_PARSED_JSON`.
  - Live DB sanity: `pdf_page_metadata_count=635`.
  - PDF batch coverage: `missing_page_metadata_count=0`, `inconsistent_location_page_metadata_count=0`.
- Populated normalized XLSX table and cell metadata from `XLSX_WORKBOOK_JSON`.
  - Live DB sanity: `table_metadata_count=3702`, `cell_metadata_count=191541`.
  - XLSX batch coverage: `missing_table_metadata_count=0`, `hidden_search_unit_leakage_count=0`.
  - Detected `row_group` regions are saved as table metadata even when explicit Excel tables also exist.
  - Cell metadata export is capped per sheet/workbook to keep callback payloads stable for large real workbooks.
- Added PaddleOCR fallback skeleton for low-quality/image-only PDF extraction.
  - Native text PDFs stay on `pdf-extract-v1` with `ocr_used=false`.
  - OCR fallback uses `pdf-extract-v2`, `ocr_engine=paddleocr`, page/bbox citations, and lower-trust confidence metadata when PaddleOCR is available.
  - Live OCR smoke was skipped in this environment because `paddleocr` is not installed.
- Expanded gold query schema and validator.
  - `eval/gold_queries_v0.csv` now has 36 live-bound seed rows across XLSX/PDF/mixed buckets.
  - Retrieval eval emits Hit@1/3/5/10, MRR@10, citation location accuracy, XLSX/PDF location accuracy, hidden leakage, and bucket metrics.
- Persisted a report-only promotion gate result to `eval_result`.
  - Gate result: `BLOCKED`.
  - Blocking reasons: XLSX citation accuracy, PDF citation accuracy, and overall citation accuracy are below initial thresholds.
  - Promotion was not executed.
- Added minimal index build/eval/promote/rollback API skeleton.
  - Live API check: an index build attached to the blocked eval result became `EVAL_FAILED`.
  - `promote` returned 409 unless the build is `EVAL_PASSED`.

### Verification

- Java compile:
  - `mvn -f core-api/pom.xml -DskipTests compile`
  - Result: passed
- Java targeted tests:
  - `mvn -f core-api/pom.xml test "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest,JobSubmissionValidatorTest,RedisJobDispatchAdapterTest,IndexBuildControllerTest,IndexPromotionGateTest,EvalResultPersistenceTest"`
  - Result: 109 passed
- Python syntax:
  - `python -m py_compile scripts/rag_ingestion_smoke.py scripts/rag_ingestion_sample_batch.py scripts/rag_pdf_ingestion_smoke.py scripts/rag_pdf_ingestion_sample_batch.py scripts/rag_pdf_ocr_fallback_smoke.py scripts/rag_retrieval_eval.py ai-worker/eval/harness/rag_ingestion_promotion_gate.py ai-worker/eval/harness/rag_ingestion_retrieval_eval.py`
  - Result: passed
- Python targeted tests:
  - `python -m pytest ai-worker/tests/test_chunk_text_builder.py ai-worker/tests/test_search_unit_indexing.py ai-worker/tests/test_search_unit_indexing_loop.py ai-worker/tests/test_xlsx_extract_capability.py ai-worker/tests/test_pdf_extract_capability.py ai-worker/tests/test_rag_ingestion_scaffolding.py ai-worker/tests/test_gold_query_validator.py ai-worker/tests/test_retrieval_eval_harness.py ai-worker/tests/test_promotion_gate_persistence.py`
  - Result: 51 passed, 1 warning
- Live smokes and reports:
  - `python scripts/rag_ingestion_smoke.py`: passed, `reports/rag_ingestion_smoke_report.json`
  - `python scripts/rag_ingestion_sample_batch.py`: 8 passed, 0 failed, `reports/rag_ingestion_sample_batch_report.json`
  - `python scripts/rag_pdf_ingestion_smoke.py`: passed, `reports/rag_pdf_ingestion_smoke_report.json`
  - `python scripts/rag_pdf_ingestion_sample_batch.py`: 8 passed, 0 failed, `reports/rag_pdf_ingestion_sample_batch_report.json`
  - `python scripts/rag_pdf_ocr_fallback_smoke.py`: skipped, `reports/rag_pdf_ocr_fallback_smoke_report.json`
- Retrieval eval:
  - `python scripts/rag_retrieval_eval.py --validate-only --report reports/rag_retrieval_eval_validate_report.json`: passed, 36 rows
  - `python scripts/rag_retrieval_eval.py --report reports/rag_retrieval_eval_report.json`: completed
  - Metrics: `Hit@10=0.3333`, `MRR@10=0.0956`, `citation_accuracy=0.1944`, `xlsx_citation_location_accuracy=0.2143`, `pdf_citation_location_accuracy=0.125`, `hidden_content_leakage_count=0`
- Promotion gate:
  - `python ai-worker/eval/harness/rag_ingestion_promotion_gate.py --metrics-report reports/rag_ingestion_promotion_gate_metrics.json --baseline-report reports/rag_ingestion_promotion_gate_baseline.json --index-version rag-ingestion-v2-candidate --gate-report reports/rag_ingestion_promotion_gate_report.json --db-dsn postgresql://aipipeline:aipipeline_pw@localhost:5433/aipipeline --eval-dataset-id rag-ingestion-gold-v0 --eval-dataset-name rag-ingestion-gold-v0 --eval-dataset-version v0 --baseline-index-version rag-ingestion-v2-baseline`
  - Result: `BLOCKED`, persisted to `eval_result`
- DB sanity:
  - `spreadsheet_missing_metadata=0`
  - `pdf_missing_metadata=0`
  - `eval_result`: `BLOCKED=2`

### Important Decisions

- Hidden sheets/columns remain excluded from search/indexing by default; hidden flags are retained in metadata without exposing hidden content values.
- XLSX aggregation remains retrieval-only in v0: success means retrieving the needed table/range, not computing the answer.
- OCR remains fallback-only and lower-trust; native text extraction is still authoritative when present.
- Promotion remains report-only. A passing eval can unlock a state transition later, but this slice does not auto-promote any candidate index.

### Remaining Work

- Install PaddleOCR or provide a real scanned/image-only PDF sample to run live OCR confidence smoke instead of the current skip path.
- Improve the actual retrieval/search path before expecting the P1 gate to pass; current live metrics are intentionally blocked by citation-location accuracy.
- Expand the gold query file toward 70-80 labeled rows and add a live `pdf_ocr_noise` row once OCR samples are available.
- Replace smoke placeholder latency metrics with measured parser/indexing p95 timings.

## 2026-05-03 - query-level retrieval eval failure analysis and gate breakdown

### Goal

Make RAG ingestion v2 retrieval eval failures diagnosable at query level, decompose XLSX/PDF location metrics, strengthen gold validation, and feed structured failure breakdown into the report-only promotion gate before considering any retrieval changes.

### Completed Changes

- Extended `ai-worker/eval/harness/rag_ingestion_retrieval_eval.py`.
  - Added `query_results[]` with expected labels, candidate/baseline index versions, top-k results, citation/location metadata, parser/index metadata, per-hit `match_breakdown`, final outcome, `failure_reason`, and `label_status`.
  - Added failure taxonomy support for empty results, expected file/sheet/table/range/page/bbox misses, hidden leakage, invalid gold labels, index mismatch, embedding/index contract mismatch, unsupported buckets, policy errors, and unknown failures.
  - Added XLSX metric decomposition: file, sheet, table, range overlap, range contains, exact range.
  - Added PDF metric decomposition: file, page, bbox overlap, exact bbox.
  - Added common counters: result empty, invalid gold, candidate/index/embedding mismatch, hidden leakage, bucket and overall failure reason counts.
  - Added per-query search error capture so one slow query does not destroy the whole report.
  - Kept legacy `per_query` for backward compatibility while adding richer `query_results`.
- Strengthened gold query validation.
  - Required missing columns are fatal.
  - Positive XLSX rows with active range policies require sheet and A1-style range.
  - Positive PDF/OCR rows require page binding.
  - Negative hidden-policy rows can be evaluated as negative tests without positive location binding.
  - Invalid rows are reported as invalid/gold-label failures instead of silent retrieval misses.
- Updated `scripts/rag_build_promotion_gate_metrics.py`.
  - Carries retrieval failure breakdown, bucket metrics, candidate/baseline versions, retrieval report path, and index/embedding mismatch counters into gate metrics.
  - Marks generated baseline output as a candidate snapshot rather than an immutable baseline.
  - Fail-closes missing source-qualified gate inputs such as `pdf.unsupported_file_rate`, `pdf.fatal_warning_count`, and `ocr.fatal_warning_count`.
- Updated `ai-worker/eval/harness/rag_ingestion_promotion_gate.py`.
  - Persists structured `failure_reason_json` with metric threshold failures, bucket failures, failure reason distribution, eval result id, report path, and candidate version.
  - Blocks candidate snapshots used as baselines.
  - Blocks non-zero gate input missing counts and non-zero indexing/candidate/required-index/embedding mismatch counters.
- Added/updated tests for report shape, failure classification, XLSX range matching, PDF page/bbox matching, hidden negative behavior, invalid gold rows, gate failure persistence, baseline snapshot rejection, and gate hard-blocking of index-contract mismatch counts.
- Did not change ingestion/search text/ranking. Query-level evidence showed the dominant current blocker is required index/version readiness, not a proven search-text structure defect.

### Subagents Used

- Bernoulli (`code_mapper`)
  - Mapped eval, search, metadata, and gate paths.
  - Key finding: eval uses `/api/v1/library/search`; current `per_query` was too shallow and gate lacked failure breakdown.
- Lagrange (`retrieval_eval_analyst`)
  - Analyzed `reports/rag_retrieval_eval_report.json` and `eval/gold_queries_v0.csv`.
  - Key finding: aggregate metrics mixed positive rows, hidden-policy probes, stale/binding issues, and strict location misses; implement query-level decomposition before retrieval changes.
- Planck (`xlsx_context_analyst`)
  - Found XLSX search text lacks some structure bridges, but agreed after follow-up to defer retrieval changes until enhanced report proves this is dominant.
- Boyle (`pdf_chunking_analyst`)
  - Found PDF page/bbox misses were conflated and recommended page/bbox decomposition before changing PDF search text.
- Bohr (`migration_reviewer`)
  - Confirmed no schema change is needed for report-only query-level details; JSON report and existing eval/gate JSONB fields are enough.
- Archimedes and Dewey (`reviewer`)
  - Found gate artifact inconsistency, misleading candidate mismatch classification, unsafe candidate-baseline snapshot behavior, hardcoded passing gate inputs, partial source omission, and missing hard gate checks for index-contract mismatch.
  - Issues were addressed by regenerating reports, splitting mismatch reasons, marking baseline snapshots, fail-closing missing source inputs, and adding hard gate checks.

### Reports Generated

- `reports/rag_retrieval_eval_validate_report.json`
- `reports/rag_retrieval_eval_report.json`
- `reports/rag_ingestion_promotion_gate_metrics.json`
- `reports/rag_ingestion_promotion_gate_baseline.json`
- `reports/rag_ingestion_promotion_gate_report.json`

### Current Metrics

- Current report run: `2026-05-03T140556Z`
- `Hit@10 = 0.0`
- `MRR@10 = 0.0`
- `citation_accuracy = 0.0`
- `xlsx_citation_location_accuracy = 0.0`
- `pdf_citation_location_accuracy = 0.0`
- `xlsx_file_hit@10 = 0.82`
- `xlsx_sheet_hit@10 = 0.78`
- `xlsx_range_overlap@10 = 0.76`
- `pdf_file_hit@10 = 0.6818`
- `pdf_page_hit@10 = 0.5909`
- `pdf_bbox_overlap@10 = 0.5294`
- `result_empty_count = 8`
- `gold_label_invalid_count = 0`
- `hidden_content_leakage_count = 0`
- `indexing_filtered_hit_count = 629`
- `required_index_version_mismatch_count = 64`
- Overall failure reason counts:
  - `required_index_version_mismatch = 64`
  - `search_result_empty = 8`

### Gate Result

- Gate decision: `BLOCKED`
- Persisted eval result: `eval_result_db2194f2954f4272a9f713047c85648f`
- Blocking reasons:
  - candidate snapshot baseline is not an immutable baseline
  - XLSX/PDF/overall citation accuracy below thresholds
  - parsing latency p95 above threshold
  - source-qualified gate inputs missing
  - indexing-filtered hits are non-zero
  - required index version mismatches are non-zero
- Promotion was not executed.

### Verification

- Java compile:
  - `mvn -f core-api/pom.xml -DskipTests compile`
  - Result: passed
- Java targeted tests:
  - `mvn -f core-api/pom.xml test "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest,JobSubmissionValidatorTest,RedisJobDispatchAdapterTest,IndexBuildControllerTest,IndexPromotionGateTest,EvalResultPersistenceTest"`
  - Result: 112 passed
- Python syntax:
  - `python -m py_compile scripts/rag_ingestion_smoke.py scripts/rag_ingestion_sample_batch.py scripts/rag_pdf_ingestion_smoke.py scripts/rag_pdf_ingestion_sample_batch.py ai-worker/eval/harness/rag_ingestion_retrieval_eval.py ai-worker/eval/harness/rag_ingestion_promotion_gate.py`
  - Result: passed
- Python ingestion/test suite:
  - `python -m pytest tests/test_chunk_text_builder.py tests/test_search_unit_indexing.py tests/test_search_unit_indexing_loop.py tests/test_xlsx_extract_capability.py tests/test_pdf_extract_capability.py tests/test_rag_ingestion_scaffolding.py`
  - Result: 43 passed, 1 warning
- Python eval/gate tests:
  - `python -m pytest tests/test_retrieval_eval_harness.py tests/test_gold_query_validator.py tests/test_promotion_gate_persistence.py tests/test_rag_ingestion_scaffolding.py`
  - Result: 38 passed
- Diff hygiene:
  - `git diff --check`
  - Result: passed with existing LF-to-CRLF warnings only

### Remaining Work

- Run or repair the candidate indexing path so search units become `EMBEDDED` under `rag-ingestion-v2-candidate`; the current query-level report shows `required_index_version_mismatch` dominates.
- Regenerate XLSX/PDF source reports with explicit `unsupported_file_rate` and `fatal_warning_count` metrics to clear source-qualified gate input gaps.
- Provide an immutable baseline report instead of using the generated candidate snapshot baseline.
- After index readiness is fixed and a fresh query-level report is available, reconsider only minimal retrieval changes if failures shift to structure-text/ranking reasons.
- Continue gold query cleanup for hidden negative policy rows and mixed-text/table bindings.

### Risks

- Current library search still returns many stale/non-candidate hits, so retrieval-text tuning would be premature.
- The generated baseline file is intentionally marked as a candidate snapshot; it should not be used to pass promotion gates.
- Gate input missing counts are now fail-closed, so older smoke reports may keep the gate blocked until regenerated with the new metric fields.

## 2026-05-03 - P1 wrap-up follow-up: OCR live proof, eval binding, and blocked gate

### Goal

Wrap up the remaining P1 ingestion work without broadening into hybrid retrieval/reranking, keeping promotion report-only.

### Completed

- Installed and validated the PaddleOCR fallback path in the local Python runtime.
  - Final compatible live pair used for this Windows/Python 3.13 environment: `paddleocr>=3.3.3,<3.4`, `paddlepaddle>=3.2,<3.3`.
  - Updated the Paddle provider to use PaddleOCR 3.x `predict(...)` and normalize `rec_texts`/`rec_scores`/`rec_boxes` result shapes.
  - OCR fallback smoke passed with `ocr_search_unit_count=2`, `ocr_page_metadata_count=1`, `ocr_confidence_avg=0.9987`, and `low_trust_ocr_chunk_count=1`.
- Tightened PDF native/OCR behavior.
  - Native text smoke now verifies `ocr_used_count=0`.
  - OCR fallback remains active for image-only/empty text-layer PDFs and page-local fallback avoids OCRing entire large PDFs when only one page needs fallback.
- Strengthened batch smoke reports.
  - XLSX batch report now includes measured parser/indexing latency p95, `unsupported_file_rate=0.0`, and `fatal_warning_count=0`.
  - PDF batch runner accepts `pymupdf+paddleocr/pdf-extract-v2` when fallback is actually used while still enforcing page metadata/location/citation coverage.
- Expanded/rebound retrieval gold candidate data.
  - `eval/gold_queries_v0.csv` has 72 schema-valid rows.
  - Rebind report: `rebound_count=65`, `missing_binding_count=7`.
  - The 72-row file is a live-bound candidate seed set, not a human-reviewed gold set.
- Regenerated report-only promotion gate output.
  - Latest gate persisted as `BLOCKED`.
  - Blocking reasons: candidate-snapshot baseline, citation-location accuracy below threshold, and parsing latency p95 above 30s.
  - Promotion was not executed.

### Latest Verification Snapshot

- Java compile: passed.
- Java targeted tests: 109 passed.
- Python targeted tests including OCR provider tests: 61 passed, 1 warning.
- Python final syntax check for patched smoke/provider files: passed.
- `git diff --check`: passed.
- Generated/live smoke results:
  - XLSX generated smoke: passed.
  - XLSX real batch smoke: passed.
  - PDF native smoke: passed with `ocr_used_count=0`.
  - PDF real batch smoke: passed after fallback-compatible validation.
  - OCR fallback smoke: passed.

### Current DB Sanity Snapshot

- `pdf_page_metadata_count=4446`.
- `table_metadata_count=9025`.
- `cell_metadata_count=257956`.
- `spreadsheet_missing_metadata=0`.
- `pdf_missing_metadata=0`.
- `eval_result`: `BLOCKED=12` at the time of the final sanity query.

### Important Caveats

- Retrieval eval is now intentionally strict about `EMBEDDED`/candidate index binding. Current catalog search can find many correct locations, but rows are still `PENDING`/`index_version=null`, so promotion metrics stay blocked.
- The current baseline report is a candidate snapshot, not an immutable production baseline; the gate correctly refuses promotion.
- Gold queries need human review before they should be called final gold. Highest priority review rows are the 7 missing rebind rows and auto-generated PDF table/page rows with numeric or clipped query surfaces.
- Real PDF batch latency p95 remains slightly above the initial 30s threshold when OCR fallback is enabled on sparse pages.

## 2026-05-03 - SearchUnit text/indexing contract hardening and hidden XLSX leakage guardrails

### Goal

Close the remaining gap between parsed PDF/XLSX artifacts, searchable `search_unit` text fields, indexing claims, and promotion/eval honesty without weakening citation/location gates or replacing the existing `source_file -> extracted_artifact -> search_unit` production path.

### Completed

- Hardened SearchUnit text generation for PDF/XLSX v2 imports.
  - `embedding_text` now carries source, citation, chunk type, sheet/table/range/header context for XLSX, and page/section/block/OCR trust context for PDF/OCR.
  - `bm25_text`, `display_text`, and `citation_text` stay distinct so `debug_text` does not become the user-facing surface.
  - `content_sha256` now follows the indexable text contract by hashing `embedding_text` first, then legacy `text_content`.
- Hardened SearchUnit indexing.
  - Claim embeddability now uses `embedding_text` before legacy `text_content`.
  - XLSX/PDF v2 SearchUnits still require `parser_version`, `location_json`, and `citation_text` before indexing.
  - Added stricter v2 location checks for XLSX sheet/range and PDF page/bbox/OCR confidence metadata.
  - Worker embedded callback now sends `embedding_model`, `embedding_text_sha256`, and `vector_id`; Spring persists matching `embedding_record` rows when completion is accepted.
- Hardened hidden XLSX handling in both worker extraction and Spring import.
  - Hidden rows/columns preserve coordinate placeholders so visible columns after hidden columns keep their original cell references.
  - Hidden column formulas, protected hidden cells, hidden cell markers, hidden header cells, and raw table/chunk header arrays are filtered before they can enter SearchUnit metadata, normalized `cell_metadata`/`table_metadata`, or embedding text.
  - Protected sheets that are too large to scan hidden cells safely are marked non-indexable instead of searched.
  - Spring import now treats `hiddenRows`, `hiddenColumns`, `hiddenColumnIndexes`, `hiddenCells`, and `hidden_cells` as server-side trust-boundary filters even if a stale worker artifact still includes the hidden values in `cells`, `formulas`, `headers`, tables, or chunks.
- Hardened retrieval eval and promotion gates.
  - Retrieval eval now records and enforces `embedding_status=EMBEDDED` and a required candidate `index_version`.
  - Promotion gate requires hidden leakage metrics, required metadata counts, and index-contract counters instead of treating absent values as success.
  - Metrics builder now records missing source-qualified gate inputs instead of defaulting critical counters/latencies to passing values.
  - Candidate snapshot baselines remain explicitly blocked.
- Hardened index build promotion.
  - `RagIndexBuildService` rejects distinct `indexVersion`/`candidateIndexVersion` at build creation.
  - Attach/promote requires eval result index versions to match the build before a PASSED eval can promote a candidate.

### Subagents Used

- Nonomi mapped the ingestion/indexing/retrieval code paths and identified that current retrieval eval is library-search based.
- Mari compared `rag-ingestion-progress.md` with implementation and flagged contract drift around hidden content and OCR metadata.
- Shiroko audited DB/indexing state and confirmed all current SearchUnits were still `PENDING` with no `embedding_record` or `ragmeta.chunks`.
- Feynman audited eval/gate behavior and recommended embedded/index-version filtering before claiming retrieval quality.
- Boyle reviewed metadata/security risks and pushed hidden XLSX filtering to the Spring import boundary.
- Socrates reviewed the implementation diff and found index-version promotion mismatch risks.
- Popper reviewed eval/gate false-positive paths and found missing-counter/defaulting risks.
- Avicenna reviewed hidden XLSX leakage paths and found protected hidden cell, hidden header, stale cell metadata, and raw header leakage paths; those were fixed.

### Reports Generated

- `reports/rag_retrieval_eval_validate_report.json`
- `reports/rag_retrieval_eval_report.json`
- `reports/rag_ingestion_promotion_gate_metrics.json`
- `reports/rag_ingestion_promotion_gate_report.json`

### Current Metrics

- Retrieval eval remains strict and blocked:
  - `Hit@10 = 0.0`
  - `MRR@10 = 0.0`
  - `citation_accuracy = 0.0`
  - `xlsx_citation_location_accuracy = 0.0`
  - `pdf_citation_location_accuracy = 0.0`
  - `hidden_content_leakage_count = 0`
  - `embedding_filtered_eval = true`
  - `required_embedding_status = EMBEDDED`
  - `required_index_version = rag-ingestion-v2-candidate`
  - `indexing_filtered_hit_count = 629`
  - `required_index_version_mismatch_count = 64`
  - `result_empty_count = 8`
- DB sanity after this turn:
  - `search_unit`: `PENDING = 216377`
  - `embedding_record = 0`
  - `ragmeta.chunks = 0`

### Gate Result

- Gate decision: `BLOCKED`
- Latest persisted eval result from this turn: `eval_result_1e92815f201e439299ac2338b7934e13`
- Blocking reasons:
  - baseline report is a candidate snapshot, not an immutable baseline
  - XLSX/PDF/overall citation accuracy below thresholds
  - parsing latency p95 above threshold
  - source-qualified gate inputs missing
  - indexing-filtered hits are non-zero
  - required index-version mismatches are non-zero
- Promotion was not executed.

### Verification

- Java compile:
  - `mvn -f core-api/pom.xml -DskipTests compile`
  - Result: passed
- Java targeted tests:
  - `mvn -f core-api/pom.xml test "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest,JobSubmissionValidatorTest,RedisJobDispatchAdapterTest,IndexBuildControllerTest,IndexPromotionGateTest,EvalResultPersistenceTest"`
  - Result: 117 passed
- Python syntax:
  - `python -m py_compile scripts/rag_ingestion_smoke.py scripts/rag_ingestion_sample_batch.py scripts/rag_pdf_ingestion_smoke.py scripts/rag_pdf_ingestion_sample_batch.py scripts/rag_retrieval_eval.py ai-worker/eval/harness/rag_ingestion_promotion_gate.py ai-worker/eval/harness/rag_ingestion_retrieval_eval.py scripts/rag_build_promotion_gate_metrics.py`
  - Result: passed
- Python tests:
  - `python -m pytest ai-worker/tests/test_chunk_text_builder.py ai-worker/tests/test_search_unit_indexing.py ai-worker/tests/test_search_unit_indexing_loop.py ai-worker/tests/test_xlsx_extract_capability.py ai-worker/tests/test_pdf_extract_capability.py ai-worker/tests/test_rag_ingestion_scaffolding.py ai-worker/tests/test_gold_query_validator.py ai-worker/tests/test_retrieval_eval_harness.py ai-worker/tests/test_promotion_gate_persistence.py`
  - Result: 75 passed, 1 warning
- Eval validation:
  - `python scripts/rag_retrieval_eval.py --validate-only --report reports/rag_retrieval_eval_validate_report.json`
  - Result: passed, 72 rows
- Eval report:
  - `python scripts/rag_retrieval_eval.py --report reports/rag_retrieval_eval_report.json`
  - Result: completed; metrics remain blocked because current rows are not embedded under the required candidate index.
- Promotion metrics/gate:
  - `python scripts/rag_build_promotion_gate_metrics.py --candidate-index-version rag-ingestion-v2-candidate --baseline-index-version rag-ingestion-v2-baseline`
  - Result: completed
  - `python ai-worker/eval/harness/rag_ingestion_promotion_gate.py --metrics-report reports/rag_ingestion_promotion_gate_metrics.json --baseline-report reports/rag_ingestion_promotion_gate_baseline.json --index-version rag-ingestion-v2-candidate --gate-report reports/rag_ingestion_promotion_gate_report.json --db-dsn postgresql://aipipeline:aipipeline_pw@localhost:5433/aipipeline --eval-dataset-id rag-ingestion-gold-v0 --eval-dataset-name rag-ingestion-gold-v0 --eval-dataset-version v0 --baseline-index-version rag-ingestion-v2-baseline`
  - Result: blocked as expected
- Diff hygiene:
  - `git diff --check`
  - Result: passed with existing LF-to-CRLF warnings only

### Not Run

- Live ingestion smoke scripts were not run in this final hardening pass:
  - `python scripts/rag_ingestion_smoke.py`
  - `python scripts/rag_ingestion_sample_batch.py`
  - `python scripts/rag_pdf_ingestion_smoke.py`
  - `python scripts/rag_pdf_ingestion_sample_batch.py`
- Reason: `localhost:8000` ai-worker health check refused connection. Postgres, Redis, and core-api were up.

### Remaining Work

- Run or wire the SearchUnit indexing worker so eligible PDF/XLSX SearchUnits become `EMBEDDED` under `rag-ingestion-v2-candidate`.
- Verify `embedding_record` and `ragmeta.chunks` are populated by the existing indexing abstraction, then rerun retrieval eval and gate.
- Add a promotion-grade vector retrieval backend; current retrieval eval still calls library search and cannot by itself prove dense/vector retrieval quality.
- Regenerate PDF/XLSX source reports with all source-qualified gate inputs present.
- Replace the candidate snapshot baseline with an immutable baseline report.
- Consider service-side eval metric contract validation before trusting manually inserted PASSED eval rows.
- Address broader security work separately: ACL/tenant filtering for library search/vector retrieval and fail-closed internal secret behavior outside dev/test.

### Risks

- This turn prevents false promotion and hidden XLSX leakage paths, but it does not yet prove actual vector retrieval quality.
- Current DB state has no embedded SearchUnits, so strict eval correctly reports zero retrieval/citation success for the required candidate index.
- Older smoke reports may keep `gate_input_missing_count` non-zero until regenerated with the new required metrics.

## 2026-05-04 - A.5 Pre-B hardening with additional XLSX data

### Goal

Use newly acquired XLSX data to prove hardened XLSX ingestion/indexing readiness before strict B/C evaluation. This is not retrieval tuning or promotion evidence.

### Completed In This Slice

- Added separate hardened XLSX manifest at `samples/rag_ingestion_hardened_xlsx_manifest.json`.
- Kept `xlsx-extract-v2-hidden-safe` with `hidden_policy=exclude_hidden`, `hidden_policy_version=exclude-hidden-v1`, and `sanitizer_version=exclude-hidden-v1` as the hardened marker contract.
- Extended SearchUnit claim scope with plural `sourceFileIds`, `documentVersionIds`, `sourceFileTypes`, `parserVersions`, `expectedIndexVersion`, `limit`, and `allowUnscoped`.
- Changed scoped repository claim queries to use PostgreSQL `FOR UPDATE SKIP LOCKED` and required `embedding_text`, `citation_text`, and `location_json`.
- Made canary/batch worker claim requests default to `allowUnscoped=false`.
- Added ragmeta namespace migration `V10__ragmeta_chunks_versioned_namespace.sql` so `ragmeta.chunks` upserts use `(index_version, chunk_id)` and widened `embedding_record.vector_id`.
- Added library-search eval root `retrieval_backend=library_search` and candidate-valid/stale-hit counters.
- Changed gold rebind to fail closed on missing bindings unless `--diagnostic-only` or `--allow-stale-bindings` is explicit.
- Started C4 promote-time hard-block validation in Spring so a PASSED eval row alone is not enough to promote.

### Current Status Labels

- A path proof: `PASS`
- A.5 Pre-B hardening: `PASS`
- B-mini diagnostic: `PASS / DIAGNOSTIC_ONLY`
- B full72 readiness: `DIAGNOSTIC_ONLY`
- C1 batch indexing readiness: `PASS`
- C2 report contract readiness: `FAIL`
- C3 immutable baseline readiness: `FAIL`
- C4 promote-time safety readiness: `PASS`
- Promotion gate: `BLOCKED`
- Vector retrieval readiness: `NOT_IMPLEMENTED`

### Verification Update

- Hardened XLSX canary reimport:
  - `reports/rag_ingestion_hardened_xlsx_canary_reimport_report.json`
  - samples: `xlsx_hardened_surgery_hidden_rows_001`, `xlsx_hardened_transit_date_001`
  - result: `2 passed / 0 failed`
  - source_file_ids: `632c83f2-df65-4b53-bf0a-e88ea23fe3b9`, `6f03eb1b-8f1d-4241-ba04-b00f8485d489`
  - document_version_ids: `docv_ea483b5a43086e05`, `docv_b24282189b1610cb`
  - parser marker: `xlsx-extract-v2-hidden-safe`
  - hidden marker mismatches: `0`
- Scoped canary indexing:
  - command scope: `documentVersionIds + sourceFileTypes=SPREADSHEET + parserVersions=xlsx-extract-v2-hidden-safe + expectedIndexVersion=rag-ingestion-v2-candidate`
  - result: `151 claimed / 151 indexed / 0 failed`
  - consistency report: `reports/a5_hardened_xlsx_canary_consistency_report.json`
  - `EMBEDDED = 151`, candidate index count `151`
  - embedding_record missing `0`, candidate chunk missing `0`
  - embeddingTextSha256 mismatches `0`
  - vector namespace mismatches `0`
  - hidden leakage `0`
  - outside-scope recent embedded count `0`
- Gold rebind:
  - gold: `reports/strict_B_hardened_xlsx_canary_gold.csv`
  - report: `reports/strict_B_hardened_xlsx_canary_gold_rebind_report.json`
  - row_count `4`, missing_binding_count `0`, stale_binding_count `0`
- B-mini retrieval diagnostic:
  - report: `reports/strict_B_hardened_xlsx_canary_retrieval_eval_report.json`
  - retrieval_backend `library_search`
  - top_k `50`
  - Hit@10 `0.75`, MRR@10 `0.75`
  - required_index_version_mismatch_count `0`
  - candidate_index_mismatch_count `0`
  - embedding_status_mismatch_count `0`
  - indexing_filtered_hit_count `56` from stale raw library-search hits
  - candidate_valid_hit_count `23`
  - hidden_content_leakage_count `0`
- C split reports:
  - C1: `reports/a5_c1_sample_batch_indexing_readiness.json` => `PASS`
  - C2: `reports/a5_c2_source_qualified_report_contract_readiness.json` => `FAIL`
  - C3: `reports/a5_c3_immutable_baseline_readiness.json` => `FAIL`
  - C4: `reports/a5_c4_promote_time_hard_block_validation.json` => `PASS`
- Promotion gate:
  - report: `reports/rag_ingestion_a5_promotion_gate_report.json`
  - decision: `BLOCKED`
  - expected blockers include candidate snapshot baseline, missing source-qualified gate inputs, library-search/stale-hit contamination, citation thresholds, and latency threshold.

### Remaining Work

- Regenerate PDF/OCR source-qualified reports with canonical metric names so C2 can pass.
- Keep full72 readiness diagnostic-only until every expected document_version_id is candidate-indexed.
- Replace candidate snapshot baseline with an immutable baseline report before any promotion attempt.
- Implement promotion-grade vector retrieval backend separately; current B-mini remains library-search smoke only.

## 2026-05-04 - C2/C3/D continuation

### Goal

Regenerate and harden canonical source-qualified reports for C2, prepare immutable baseline evidence for C3 without accepting candidate snapshots, and implement a separate D-stage vector retrieval backend path. This continuation still does not attempt promotion.

### Completed In This Slice

- Regenerated XLSX/PDF/OCR source reports with canonical metric names.
- Hardened `scripts/rag_build_promotion_gate_metrics.py` so derived metrics are recorded as diagnostic provenance and no longer clear missing canonical gate inputs.
- Added canonical `source_qualified_metrics`, `canonical_metrics`, and `canonical_metric_names` output.
- Added `scripts/rag_prepare_immutable_baseline.py` to reject candidate snapshot baselines and materialize immutable descriptors only when hash/provenance/dataset/backend requirements pass.
- Hardened the Python promotion gate to require immutable baseline hash, provenance, dataset version, and non-candidate baseline evidence.
- Hardened Spring promote-time checks so missing zero-counters, object-shaped failure payloads, mismatched required index version, and missing baseline dataset version block promotion.
- Added D-stage vector retrieval eval support through the existing FAISS/index metadata path, with explicit `--retrieval-backend vector`.
- Added vector hit conversion that preserves candidate index contract fields and reconstructs XLSX/PDF location metadata when vector chunk metadata is stored in Java JsonNode shape.
- Wrote separate D reports instead of overwriting B-mini library-search evidence.

### Current Reports

- C2 canonical metrics: `reports/rag_ingestion_a5_c2_canonical_metrics.json`
- C2 readiness: `reports/a5_c2_source_qualified_report_contract_readiness.json`
- C3 immutable baseline readiness: `reports/a5_c3_immutable_baseline_readiness.json`
- D vector canary eval: `reports/strict_D_hardened_xlsx_canary_vector_eval_report.json`
- D vector canonical metrics: `reports/rag_ingestion_d_vector_canonical_metrics.json`
- D vector readiness: `reports/a5_d_vector_backend_readiness.json`

### Verification Update

- C2 source-qualified report contract:
  - status: `PASS`
  - `gate_input_missing_count = 0`
  - `gate_input_missing = []`
  - `derived_metric_sources = {}`
  - canonical report includes XLSX, PDF, OCR, and retrieval metric namespaces.
- C3 immutable baseline readiness:
  - status: `FAIL`
  - expected blockers: candidate snapshot baseline, non-vector/missing baseline backend, missing baseline citation metric.
  - no immutable baseline descriptor was written.
- D vector backend canary:
  - status: `PASS` for hardened XLSX canary scope only.
  - retrieval backend: `vector`
  - backend identity: FAISS `rag-data-canary` with candidate namespace filter.
  - gold row count: `4`
  - top_k: `50`
  - Hit@10: `1.0`
  - MRR@10: `0.3482`
  - citation_accuracy: `1.0`
  - xlsx_citation_location_accuracy: `1.0`
  - candidate_valid_hit_count: `200`
  - indexing_filtered_hit_count: `0`
  - required_index_version_mismatch_count: `0`
  - embedding_status_mismatch_count: `0`
  - candidate_index_mismatch_count: `0`
  - hidden_content_leakage_count: `0`
- Targeted Python tests:
  - `python -m pytest ai-worker/tests/test_retrieval_eval_harness.py ai-worker/tests/test_rag_ingestion_scaffolding.py ai-worker/tests/test_promotion_gate_persistence.py`
  - result: `39 passed`
- Java promotion gate tests:
  - `mvn -f core-api/pom.xml test "-Dtest=IndexPromotionGateTest"`
  - result: `11 passed`

### Current Status Labels

- A path proof: `PASS`
- A.5 Pre-B hardening: `PASS`
- B-mini diagnostic: `PASS / DIAGNOSTIC_ONLY`
- B full72 readiness: `DIAGNOSTIC_ONLY`
- C1 batch indexing readiness: `PASS`
- C2 report contract readiness: `PASS`
- C3 immutable baseline readiness: `FAIL`
- C4 promote-time safety readiness: `PASS`
- D vector backend canary readiness: `PASS`
- Promotion gate: `BLOCKED`
- Vector retrieval readiness: `PASS` for hardened canary scope only; not full72 or promotion evidence.

### Remaining Work

- Build a real immutable baseline from a previous promoted vector index and frozen eval dataset.
- Run vector-backed full72 only after every expected document_version_id is candidate-indexed.
- Keep promotion blocked until C3 has a valid immutable baseline and the promotion-scope indexing contract is complete.
- Decide thresholds for promotion-grade vector retrieval after canary scope expands beyond the current four hardened XLSX gold rows.

## 2026-05-04 - path-separation readiness and candidate consistency reports

### Goal

Add report-only readiness surfaces that prove TEXT/PDF/XLSX path separation and PDF/XLSX candidate embedding consistency before any full72 or promotion claim.

### Completed In This Slice

- Added `scripts/rag_path_separation_readiness.py`.
  - Default output: `reports/rag_path_separation_readiness.json`.
  - Reports TEXT/XLSX/PDF path summaries, parser and artifact breakdowns, SearchUnit contract completeness, normalized metadata coverage, embedding/index contract status, retrieval backend separation, path mixing findings, blockers, and warnings.
  - Fails closed on missing PDF/XLSX parser/location/citation/embedding text, hidden XLSX leakage, hidden-policy contract drift, missing `embedding_record` or `ragmeta.chunks`, vector eval artifacts using non-vector backends, path mixing, and missing normalized metadata coverage.
- Added `scripts/pdf_xlsx_candidate_embedding_consistency.py`.
  - Default output: `reports/pdf_xlsx_candidate_embedding_consistency_report.json`.
  - Defaults to `sourceFileTypes=SPREADSHEET/PDF`, parser versions `xlsx-extract-v2-hidden-safe/pdf-extract-v1/pdf-extract-v2`, `expectedIndexVersion=rag-ingestion-v2-candidate`, and `allowUnscoped=false`.
  - Defaults document version scope from `eval/gold_queries_v0.csv` only, using the unique `expected_document_version_id` values from the 72 gold rows. Report-derived scope is opt-in through `--derive-from-report`.
  - Fails or reports diagnostic-only when full72 scope cannot be proven, and checks embedded status, index version, embedding records, ragmeta chunks, vector namespace, chunk-to-embedding SHA consistency, outside-scope recent rows, hidden leakage, and XLSX hidden-policy/version evidence.
- Hardened the Python promotion gate so `retrieval_backend=library_search` is diagnostic-only and cannot pass promotion; promotion evidence now also requires vector backend identity and matching candidate namespace filter.
- Hardened the SearchUnit CLI so candidate non-dry-run indexing defaults `--index-version` from `--expected-index-version`, fills missing expected version when candidate `--index-version` is explicit, rejects mismatched explicit versions, and requires a hard identity scope unless `--allow-unscoped` is explicit. Version-omitted live runs also require a hard identity scope because the loaded FAISS build may already be a candidate index. For the full72 report path that scope remains the gold CSV document-version set.

### Verification Update

- Syntax check:
  - `python -m py_compile scripts/rag_path_separation_readiness.py scripts/pdf_xlsx_candidate_embedding_consistency.py scripts/rag_build_promotion_gate_metrics.py scripts/rag_prepare_immutable_baseline.py scripts/rag_retrieval_eval.py ai-worker/ai_worker/search_unit_indexing.py ai-worker/eval/harness/rag_ingestion_promotion_gate.py`
  - result: passed
- Targeted Python tests:
  - `python -m pytest ai-worker/tests/test_retrieval_eval_harness.py ai-worker/tests/test_rag_ingestion_scaffolding.py ai-worker/tests/test_promotion_gate_persistence.py ai-worker/tests/test_search_unit_indexing_loop.py`
  - result: `70 passed`
- Java promotion gate tests:
  - `mvn -f core-api/pom.xml test "-Dtest=IndexPromotionGateTest"`
  - result: `11 passed`
- Diff hygiene:
  - `git diff --check`
  - result: passed; Git reported existing LF-to-CRLF working-copy warnings only.
  - Additional tracked/untracked whitespace check for new report/test/doc files: passed.
- Live report generation:
  - `python scripts/rag_path_separation_readiness.py`
  - result: report written with `status=FAIL`; blockers are current live DB readiness blockers, not script failure.
  - current key evidence: TEXT count `0`, XLSX count `22623`, PDF count `215633`, hidden XLSX leakage `0`, XLSX hidden-policy mismatch `0`, XLSX hidden-policy-version mismatch `22318`, candidate-index-involved PDF/XLSX rows `163`, missing `embedding_record` `0`, missing `ragmeta.chunks` `0`.
  - current blockers include missing PDF/XLSX `embedding_text`, XLSX hidden-policy-version drift in legacy rows, candidate vector namespace mismatches on existing indexed rows, unmatched XLSX SearchUnit metadata `8005`, missing XLSX table metadata coverage, and missing PDF page metadata coverage.
  - `python scripts/pdf_xlsx_candidate_embedding_consistency.py`
  - result: report written with `status=FAIL`.
  - current key evidence: gold query rows `72`, unique scoped document versions `7`, scoped rows `8203`, all scoped rows `PENDING`, hidden leakage `0`, XLSX hidden-policy mismatch `0`, XLSX hidden-policy-version mismatch `0`.
  - current blockers: `not_embedded_count`, `index_version_mismatch_count`, `embedding_record_missing_count`, and `candidate_chunk_missing_count` are non-zero; `docv_154d379a5bc66fa3`, `docv_5100e8a29cb45d87`, `docv_855a38a33b2f9eb2`, and `docv_afb3922c61912678` have no scoped candidate rows under the required PDF/XLSX parser/version filter.

### Current Status Labels

- Path-separation readiness: `FAIL`
- PDF/XLSX candidate embedding consistency: `FAIL`
- Promotion gate: `BLOCKED`

### Subagents Used And Findings

- `code_mapper`: confirmed the production path still flows through source file/catalog records into extracted or parsed artifacts and then SearchUnit rows; text, PDF, and XLSX have distinct parser/source type signals, and vector eval uses the FAISS/candidate metadata path rather than the library-search smoke path.
- `db_index_auditor`: confirmed candidate embedding must be scoped by explicit document version IDs, source file types, parser versions, and candidate index version; unscoped non-dry-run candidate indexing remains unsafe unless explicitly allowed and documented.
- `eval_gate_reviewer`: confirmed library-search diagnostics and vector eval reports are separated, C3 still rejects candidate snapshot baselines, and promotion remains blocked when backend/index/baseline evidence is missing or mismatched.
- `xlsx_pdf_path_reviewer`: confirmed PDF/XLSX metadata contracts are distinct from plain text paths, but current live data still has parser/version drift, normalized metadata gaps, and legacy XLSX/PDF rows that cannot be treated as hardened promotion evidence.
- `implementation_worker`: added the two report scripts, tightened Python promotion/backend checks, tightened the SearchUnit candidate CLI scope guard, and added targeted tests. The orchestrator tightened the candidate consistency script afterward so default full72 scope comes from gold CSV only, not broad report-derived guesses.
- `final_reviewer`: found false-pass risks in candidate CLI scope, hidden-policy evidence, vector backend identity, per-SearchUnit XLSX metadata coverage, and embedding SHA semantics. Those items were fixed before concluding this slice.

### Remaining Work

- Candidate-index the full expected PDF/XLSX document version scope before rerunning the consistency report.
- Resolve normalized metadata gaps reported by `rag_path_separation_readiness.json`.
- Keep library-search reports as ingestion/citation smoke only; use vector-backed reports for promotion evidence.
- Build a real immutable baseline from a previous promoted vector index and frozen eval dataset. C3 remains `FAIL`, so promotion remains `BLOCKED`.

## 2026-05-04 - full72 candidate embedding consistency pass

### Goal

Pass the full72 PDF/XLSX candidate embedding consistency check before attempting any baseline or promotion claim.

### Completed In This Slice

- Classified the 7 unique `expected_document_version_id` values from `eval/gold_queries_v0.csv` and wrote `reports/full72_docv_scope_classification_report.json`.
- Resolved the four previously missing/stale scoped docvs:
  - `docv_154d379a5bc66fa3`: legacy XLSX binding replaced by existing `xlsx-extract-v2-hidden-safe` candidate docv.
  - `docv_5100e8a29cb45d87`: stale XLSX binding reimported from a valid workbook payload, then rebound.
  - `docv_855a38a33b2f9eb2`: legacy XLSX binding replaced by existing `xlsx-extract-v2-hidden-safe` candidate docv.
  - `docv_afb3922c61912678`: legacy XLSX binding reimported through the hidden-safe path with visible sheet content only, then rebound.
- Repaired scoped PDF SearchUnit text metadata only for the full72 docv set; `reports/scoped_search_unit_text_repair_report.json` reports repaired rows without broad mutation.
- Rebound the gold CSV and wrote `reports/rag_gold_query_rebind_report.json` with `rebound_count=0`, `missing_binding_count=0`, `stale_binding_count=0` after the final preserve-valid run.
- Applied scope-only candidate namespace cleanup/upsert policy. `reports/candidate_namespace_cleanup_upsert_report.json` reports no vector-id, chunk SHA, or stale embedded-state mismatch after the scoped run.
- Ran scoped candidate indexing with `allowUnscoped=false` over the final 7 full72 docvs only. `reports/scoped_candidate_indexing_report.json` reports `claimed=8615`, `indexed=8615`, `failed=0`; 3 rows were already candidate-embedded, yielding 8618 candidate rows total.
- Split candidate promotion-scope path readiness from global path hygiene. `reports/rag_candidate_scope_path_readiness.json` is candidate-scope only and does not treat global legacy drift as a promotion-scope blocker.

### Current Evidence

- `reports/pdf_xlsx_candidate_embedding_consistency_report.json`: `PASS`.
  - Candidate rows: `8618`; policy-excluded rows: `9`.
  - `not_embedded_count=0`.
  - `index_version_mismatch_count=0`.
  - `embedding_record_missing_count=0`.
  - `candidate_chunk_missing_count=0`.
  - vector namespace mismatch count: `0`.
  - chunk SHA mismatch count: `0`.
  - hidden leakage count: `0`.
  - missing scoped candidate docv count: `0`.
- `reports/rag_candidate_scope_path_readiness.json`: `PASS` for the final full72 candidate docv set only.
- `reports/rag_retrieval_eval_full72_vector_diagnostic_report.json`: vector-only full72 diagnostic completed after consistency passed. This is diagnostic evidence only, not promotion evidence while C3 is blocked.
  - The report now carries `promotion_evidence=false` and `evidence_role=diagnostic`.
- `reports/rag_ingestion_a5_promotion_gate_report.json`: regenerated from the full72 vector diagnostic and remains `BLOCKED`; the current reasons include the diagnostic-only evidence marker and the invalid candidate-snapshot baseline.

### Baseline And Gate Status

- C3 immutable baseline readiness remains `FAIL`.
  - `reports/a5_c3_immutable_baseline_readiness.json` rejects the current descriptor because it is a candidate snapshot and lacks immutable baseline provenance/complete baseline metrics.
- `reports/initial_baseline_bootstrap_proposal.json` records the bootstrap-only path for creating a first immutable vector baseline if no previous promoted vector index exists.
- Promotion gate remains `BLOCKED`.
- No library-search report, hardened XLSX canary report, or candidate snapshot was used as immutable baseline evidence.

### Remaining Work

- Design `INITIAL_BASELINE_BOOTSTRAP` if no previous promoted vector index exists; this must be a first-baseline creation procedure, not a promotion gate pass.
- Diagnose vector retrieval quality separately from indexing consistency, especially PDF page/bbox location matching in the full72 vector diagnostic.
- Keep global path hygiene readiness separate from candidate promotion-scope readiness until legacy parser/path drift is retired or explicitly excluded.

## 2026-05-04 - initial baseline bootstrap design and full72 vector quality breakdown

### Goal

Create a concrete `INITIAL_BASELINE_BOOTSTRAP` path for the first immutable vector baseline, keep it separate from promotion, and decompose the completed full72 vector diagnostic into actionable retrieval-quality buckets.

### Completed

- Added `scripts/rag_bootstrap_initial_vector_baseline.py`.
  - Writes `reports/initial_immutable_vector_baseline_descriptor.json`.
  - Writes `reports/initial_baseline_bootstrap_readiness.json`.
  - Requires vector backend identity, candidate namespace filter, eval dataset hash, retrieval/metrics report hashes, FAISS artifact hash, embedding model, document-version scope, and bootstrap provenance.
  - Marks the descriptor with `baseline_type=INITIAL_BASELINE_BOOTSTRAP`, `bootstrap_status=BOOTSTRAP_READY_NOT_PROMOTION`, `promotion_evidence=false`, `promotion_gate_effect=none`, and `usable_as_baseline_for_future_candidates=true`.
- Extended `scripts/rag_prepare_immutable_baseline.py`.
  - Validates `INITIAL_BASELINE_BOOTSTRAP` descriptors under separate rules.
  - Keeps candidate snapshot baselines rejected.
  - Rejects `library_search` reports as immutable baseline evidence.
- Added `scripts/rag_full72_vector_quality_breakdown.py`.
  - Writes `reports/rag_retrieval_full72_vector_quality_breakdown.json`.
  - Separates matched rows, retrieval/ranking suspects, policy/matching-rule suspects, chunk-granularity suspects, and gold/table-binding suspects.
- Updated `ai-worker/tests/test_rag_ingestion_scaffolding.py` with guards for:
  - bootstrap descriptor creation,
  - C3 readiness passing only for a valid bootstrap descriptor,
  - missing vector namespace fail-close,
  - `library_search` immutable-baseline rejection,
  - PDF page/bbox metadata-projection vs ranking classification.

### Current Evidence

- `reports/initial_baseline_bootstrap_readiness.json`: `PASS`.
  - `baseline_type=INITIAL_BASELINE_BOOTSTRAP`.
  - `bootstrap_status=BOOTSTRAP_READY_NOT_PROMOTION`.
  - `promotion_evidence=false`.
  - `candidate_namespace_filter=rag-ingestion-v2-candidate`.
  - blockers: `[]`.
- `reports/initial_immutable_vector_baseline_descriptor.json`: created.
  - `baseline_index_version=initial-full72-vector-baseline-v0`.
  - `source_candidate_index_version=rag-ingestion-v2-candidate`.
  - `retrieval_backend=vector`.
  - includes gold CSV SHA, retrieval report SHA, metrics report SHA, FAISS artifact hash, vector index hash, backend identity, embedding model, and full72 document-version scope.
- `reports/rag_retrieval_full72_vector_quality_breakdown.json`: `COMPLETED`.
  - query count: `72`.
  - matched rows: `31`.
  - retrieval/ranking suspects: `23`.
  - policy/matching-rule suspects: `10`.
  - chunk-granularity suspects: `5`.
  - gold/table-binding suspects: `3`.
- PDF split:
  - `pdf_page_policy_missing_physical_or_label=10`.
  - `pdf_expected_page_absent_in_top10=10`.
  - `pdf_expected_file_absent_in_top10=2`.
  - `correct_page_no_hit_but_missing_physical_page_index=10`.
  - `correct_page_no_hit_but_missing_bbox=5`.
- XLSX split:
  - `xlsx_lookup`: still strong, `18/18` matched.
  - `xlsx_expected_file_absent_in_top10=11`.
  - `xlsx_range_ranking_or_chunk_granularity_mismatch=5`.
  - `xlsx_table_metadata_or_gold_binding_mismatch=2`.
  - `xlsx_other_location_mismatch=1`.

### Gate/Baseline Status

- C3 immutable baseline readiness is now `PASS` for the bootstrap descriptor:
  - `reports/a5_c3_immutable_baseline_readiness.json`.
  - `baseline_type=INITIAL_BASELINE_BOOTSTRAP`.
  - `candidate_snapshot=false`.
  - `promotion_evidence=false`.
  - `reasons=[]`.
- Promotion gate remains `BLOCKED`.
  - `reports/rag_ingestion_a5_promotion_gate_report.json`.
  - Remaining reasons:
    - `xlsx_citation_location_accuracy must be >= 0.90`.
    - `pdf_citation_location_accuracy must be >= 0.85`.
    - `citation_accuracy must be >= 0.85`.
    - `parsing_latency_p95 must be <= 30.00`.
    - `retrieval report must declare promotion_evidence=true for promotion`.
    - `gate_input_missing_count must be 0`.
- Candidate snapshot baselines remain invalid immutable baseline inputs.
- The full72 vector diagnostic remains diagnostic-only and is not promotion evidence.

### Verification

- Python syntax check:
  - `python -m py_compile scripts/rag_prepare_immutable_baseline.py scripts/rag_retrieval_eval.py scripts/rag_build_promotion_gate_metrics.py scripts/rag_bootstrap_initial_vector_baseline.py scripts/rag_full72_vector_quality_breakdown.py ai-worker/eval/harness/rag_ingestion_promotion_gate.py`
  - result: passed.
- Python targeted tests:
  - `python -m pytest ai-worker/tests/test_retrieval_eval_harness.py ai-worker/tests/test_rag_ingestion_scaffolding.py ai-worker/tests/test_promotion_gate_persistence.py`
  - result: `54 passed`.
- Java promotion gate tests:
  - `mvn -f core-api/pom.xml test "-Dtest=IndexPromotionGateTest"`
  - result: `11 passed`.
- Diff hygiene:
  - `git diff --check`
  - result: passed; Git still reports existing LF-to-CRLF working-copy warnings.
- Report-only promotion gate rerun:
  - Used the bootstrap descriptor as baseline input.
  - Result remained `BLOCKED`; the command exits non-zero for blocked gates.

### Important Decisions

- `INITIAL_BASELINE_BOOTSTRAP` is a first-baseline creation procedure, not a promotion decision.
- Bootstrap descriptors may be used as future baseline evidence only when fully hash/provenance-backed and explicitly marked `promotion_evidence=false`.
- Candidate snapshot metrics files are still not immutable baselines.
- `library_search` reports remain ingestion/citation smoke only and cannot become immutable baseline or promotion evidence.
- Candidate promotion-scope readiness remains separate from global path hygiene; global legacy drift stays backlog, not a full72 candidate-scope blocker.
- No hybrid search, reranking, parser expansion, threshold relaxation, or promotion execution was introduced in this slice.

### Remaining Work

- Decide the next action from the new breakdown:
  - fix PDF vector metadata projection/page-bbox matching evidence,
  - clean gold labels for hidden/formula/generic PDF rows,
  - or start a retrieval-tuning slice after evidence cleanup.
- Add a dedicated readiness check for vector metadata projection if the next slice targets PDF page/bbox evidence.
- Regenerate full72 vector diagnostic after any metadata projection or gold-label cleanup.
- Rebuild promotion metrics after `xlsx.hidden_content_leakage_count` has canonical source-qualified evidence instead of a diagnostic derived value.

### Risks

- The initial baseline is bootstrapped from the current candidate vector artifact by hash. It is acceptable as a first immutable baseline descriptor, but it must not be described as a promoted prior index.
- PDF `page_no` sometimes appears in top hits while `physical_page_index` or `bbox` is missing from vector-returned location metadata, so current `pdf_page_hit@10=0.0` mixes ranking failures with metadata/matching-policy failures.
- Some XLSX formula/date/hidden-policy rows appear to ask for content not currently present in indexed embedding text; treating those as pure retrieval failures would be misleading.
- Hidden negative rows are not yet isolated as `hidden_policy=negative`; current hidden bucket scores as positive retrieval failures.
