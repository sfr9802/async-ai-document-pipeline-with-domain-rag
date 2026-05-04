# Codex Task Brief: RAG Ingestion v2 Next Steps

> Purpose: give Codex a repo-friendly implementation brief for the next RAG ingestion work turn.
> Scope: XLSX/PDF ingestion v2 MVP, real sample validation, PDF native text extraction, smoke/eval gate preparation.

---

## 0. How Codex should work on this task

Start in **plan-first mode**.

Before editing code:

1. Inspect the repository structure.
2. Locate the existing files/classes/scripts named in this document.
3. Summarize what already exists and what is missing.
4. Propose a small implementation plan.
5. Then implement P0 items in order.

Do not perform broad refactors. Do not replace the existing production ingestion path. Extend it carefully.

At the end of the task, provide:

- files changed
- tests/commands run
- failures or skipped checks
- DB checks performed
- remaining work
- an appended progress-log entry

---

## 1. Current project state

The project already has an XLSX/PDF RAG ingestion v2 foundation.

Completed foundation:

- Flyway migration `V7__document_ingestion_v2.sql` was added.
- New v2 tables exist:
  - `document`
  - `document_version`
  - `parsed_artifact`
  - `table_metadata`
  - `cell_metadata`
  - `pdf_page_metadata`
  - `embedding_record`
  - `index_build`
  - `citation`
  - `eval_dataset`
  - `eval_query`
  - `eval_result`
- `search_unit` was extended with v2 fields:
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
- Existing production path is intentionally preserved:
  - `source_file -> extracted_artifact -> search_unit`
- v2 provenance is added beside the existing path:
  - `document_version -> parsed_artifact -> search_unit/chunk -> index_version`
- User-facing search/citation response now exposes v2 fields.
- `location_json` is authoritative for XLSX/PDF citation when present.
- XLSX citation rendering resolves:
  - `sheet_name`
  - `sheet_index`
  - `cell_range`
  - `table_id`
- PDF citation rendering resolves:
  - `physical_page_index`
  - `page_no`
  - `page_label`
  - `bbox`
- Python chunk text builder exists:
  - `ai-worker/app/capabilities/rag/chunk_text_builder.py`
- Existing smoke runner exists:
  - `scripts/rag_ingestion_smoke.py`
- Existing fixture examples exist:
  - `ai-worker/tests/fixtures/parsed_artifacts/xlsx_v2_sample.json`
  - `ai-worker/tests/fixtures/parsed_artifacts/pdf_v2_sample.json`

Verification already reported as passing:

```bash
mvn -f core-api/pom.xml -DskipTests compile
mvn -f core-api/pom.xml test "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest"
python -m pytest tests/test_chunk_text_builder.py tests/test_search_unit_indexing.py tests/test_search_unit_indexing_loop.py tests/test_xlsx_extract_capability.py
python -m py_compile scripts/rag_ingestion_smoke.py
git diff --check
```

---

## 2. Current objective

The next step is **not** to add hybrid retrieval, reranking, or agentic RAG.

The next step is to prove that the current v2 ingestion pipeline works against real XLSX/PDF data:

1. Run live XLSX smoke validation.
2. Add a real-sample XLSX batch smoke runner.
3. Implement native PDF text extraction v1 with page/block/bbox metadata.
4. Add a PDF ingestion smoke runner.
5. Create gold query v0 seed data.
6. Implement or stub an index promotion eval gate that can block bad candidate `index_version` promotion.

---

## 3. Non-goals for this task

Do **not** implement these unless explicitly requested later:

- hybrid retrieval
- reranker
- agentic RAG
- LLM-as-judge as primary evaluation
- full OCR optimization
- formula recalculation engine for Excel
- legacy `.xls` support
- large-scale dashboard
- vector DB migration
- broad rewrite of `source_file -> extracted_artifact -> search_unit`

Reason: current risk is ingestion/citation correctness, not retrieval model sophistication.

---

## 4. First repository inspection commands

Run these before editing code:

```bash
pwd
git status --short
find . -maxdepth 3 -type f | sed 's#^./##' | sort | head -200
rg "XLSX_EXTRACT|OCR_EXTRACT|applyIngestionV2|location_json|citation_text|parser_version|index_version" -n .
rg "rag_ingestion_smoke|chunk_text_builder|parsed_artifact|pdf_page_metadata|table_metadata|cell_metadata" -n .
rg "DocumentCatalogService|SearchUnitJpaEntity|SearchUnitIndexingService|SearchUnitResponse|Citation" -n core-api ai-worker scripts || true
```

If paths differ, locate equivalent files with `rg` and continue.

---

## 5. Hard implementation rules

1. Keep the existing production path:
   - `source_file -> extracted_artifact -> search_unit`
2. Add v2 metadata beside the old path. Do not remove legacy fields.
3. Do not index XLSX/PDF/OCR `search_unit` rows unless these are present:
   - `parser_version`
   - `location_json`
   - `citation_text`
4. XLSX `location_json` must preserve, when available:
   - `type = xlsx`
   - `sheet_name`
   - `sheet_index`
   - `table_id`
   - `cell_range`
   - `row_range`
   - `header_path`
   - `contains_formula`
   - `contains_merged_cell`
   - `hidden_policy`
5. PDF `location_json` must preserve, when available:
   - `type = pdf`
   - `physical_page_index`
   - `page_no`
   - `page_label`
   - `bbox`
   - `section_path`
   - `block_type`
   - `ocr_used`
   - `ocr_confidence`
6. OCR output must not be treated as equal-trust native PDF text.
7. `embedding_text`, `bm25_text`, `display_text`, `citation_text`, `debug_text` must remain separate.
8. Do not edit an already-applied Flyway migration if avoidable. Add a new migration such as `V8__...sql` for schema changes.
9. Every new parser/indexing behavior must have tests or smoke validation.
10. Append a progress-log entry after the work turn.

---

## 6. P0 implementation plan

### P0-A. Run live XLSX smoke validation

Goal: prove the existing generated XLSX smoke runner works against live `core-api`, `ai-worker`, and local DB.

Command:

```bash
python scripts/rag_ingestion_smoke.py
```

If only HTTP/job behavior is available:

```bash
python scripts/rag_ingestion_smoke.py --skip-db-check
```

Expected behavior:

- generated XLSX is uploaded
- XLSX extract job completes
- DB rows are created in:
  - `source_file`
  - `extracted_artifact`
  - `document`
  - `document_version`
  - `parsed_artifact`
  - `search_unit`
- v2-ready XLSX `search_unit` rows have:
  - `parser_version`
  - `location_json`
  - `citation_text`

If the smoke fails, fix the smallest defect first. Do not move to PDF work until the failure cause is understood.

#### DB validation SQL

Use these or adapt to the project’s DB client.

```sql
select id, status, original_file_name, created_at
from source_file
order by created_at desc
limit 10;

select id, source_file_id, artifact_type, created_at
from extracted_artifact
order by created_at desc
limit 10;

select id, source_file_name, source_file_type, parser_version, location_type,
       location_json, citation_text, embedding_status, created_at
from search_unit
order by created_at desc
limit 20;

select count(*) as missing_v2_citation_metadata
from search_unit
where source_file_type in ('xlsx', 'pdf', 'ocr')
  and (
    parser_version is null
    or location_json is null
    or citation_text is null
  );
```

Required result:

```text
missing_v2_citation_metadata = 0
```

---

### P0-B. Add real XLSX sample batch smoke runner

Goal: validate real captured XLSX files, not only generated fixtures.

Add or update:

```text
samples/rag_ingestion_manifest.json
scripts/rag_ingestion_sample_batch.py
```

The script must:

1. Read a manifest.
2. Upload each XLSX file.
3. Trigger XLSX extract.
4. Poll job status.
5. Validate DB rows when DB access is available.
6. Produce a JSON report.
7. Fail non-zero when required metadata is missing.

#### Manifest schema

```json
{
  "samples": [
    {
      "sample_id": "xlsx_001_simple_table",
      "file_path": "samples/xlsx/sales_q3.xlsx",
      "file_type": "xlsx",
      "expected_sheets": ["매출현황"],
      "expected_min_search_units": 5,
      "expected_citation_patterns": [
        "sales_q3.xlsx > 매출현황 >"
      ],
      "features": ["simple_table"],
      "notes": "basic table lookup sample"
    }
  ]
}
```

Start with 8-10 XLSX files if available:

| sample type | recommended count |
|---|---:|
| simple table | 2 |
| merged cells | 2 |
| formula cells | 2 |
| multiple sheets | 2 |
| hidden row/column/sheet | 1-2 |

#### Batch smoke output

Write a report such as:

```text
reports/rag_ingestion_sample_batch_report.json
```

Report fields:

```json
{
  "run_id": "2026-05-03T120000",
  "total_samples": 10,
  "passed": 9,
  "failed": 1,
  "samples": [
    {
      "sample_id": "xlsx_001_simple_table",
      "status": "PASSED",
      "source_file_id": 123,
      "job_id": 456,
      "search_unit_count": 12,
      "missing_required_metadata_count": 0,
      "warnings": []
    }
  ]
}
```

Acceptance criteria:

- upload success: 100% for readable files
- parse success: >= 90% for real XLSX sample corpus
- missing required v2 metadata: 0
- zero indexable chunk count: 0
- report file generated
- targeted tests pass

---

### P0-C. Implement native PDF text extraction v1

Goal: add a true PDF text-layer parser beyond OCR-lite.

Preferred library:

```python
PyMuPDF / fitz
```

If dependency is missing, locate the correct requirements file and add it there.

Find requirements files:

```bash
find . -iname '*requirements*.txt' -o -iname 'pyproject.toml' -o -iname 'Pipfile' -o -iname 'poetry.lock'
```

Parser behavior:

1. Open PDF.
2. For each page:
   - record `physical_page_index` as 0-based index
   - record `page_no` as 1-based number
   - record `page_label` when available, otherwise string of `page_no`
   - record page width/height
   - detect whether text layer exists
   - extract text blocks with bbox and reading order
3. Do not OCR in v1.
4. If a page has no text blocks, add warning:
   - `PDF_TEXT_LAYER_EMPTY`
   - `OCR_REQUIRED`
5. Store parsed artifact.
6. Generate page/block/paragraph `search_unit` rows with PDF `location_json`.

#### PDF parsed artifact target schema

```json
{
  "document_version_id": "docv_pdf_001",
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
          "section_path": []
        }
      ],
      "tables": []
    }
  ],
  "warnings": [],
  "quality_score": 0.88
}
```

#### PDF `search_unit.location_json` target schema

```json
{
  "type": "pdf",
  "physical_page_index": 0,
  "page_no": 1,
  "page_label": "1",
  "bbox": [72.0, 100.0, 520.0, 160.0],
  "section_path": [],
  "block_type": "paragraph",
  "ocr_used": false,
  "ocr_confidence": null
}
```

#### PDF citation target

```text
contract.pdf > p.1 > bbox [72.0,100.0,520.0,160.0]
```

Acceptance criteria:

- parser produces `parsed_artifact` for native text PDF
- PDF `search_unit` rows contain `parser_version`, `location_json`, and `citation_text`
- page metadata includes `physical_page_index`, `page_no`, and `page_label`
- no native PDF block is indexed without citation metadata
- empty text layer pages are warned and not silently treated as valid text

---

### P0-D. Add PDF smoke runner

Add:

```text
scripts/rag_pdf_ingestion_smoke.py
```

The script must:

1. Accept a PDF path or generate a minimal text-layer PDF if the repo already has a safe generator utility.
2. Upload the PDF.
3. Trigger the PDF parse/extract flow.
4. Poll job status.
5. Validate DB rows.
6. Check PDF `location_json` and `citation_text`.

Suggested command:

```bash
python scripts/rag_pdf_ingestion_smoke.py --file samples/pdf/native_text_sample.pdf
```

Required DB checks:

```sql
select id, source_file_name, source_file_type, parser_version, location_json, citation_text
from search_unit
where source_file_type in ('pdf', 'ocr')
order by created_at desc
limit 20;

select count(*) as missing_pdf_citation_metadata
from search_unit
where source_file_type in ('pdf', 'ocr')
  and (
    parser_version is null
    or location_json is null
    or citation_text is null
  );
```

Required result:

```text
missing_pdf_citation_metadata = 0
```

---

### P0-E. Create gold query v0 seed file

Goal: start an evaluation loop for real XLSX/PDF samples.

Add:

```text
eval/gold_queries_v0.csv
```

CSV schema:

```csv
query_id,bucket,query,expected_file_name,expected_document_id,expected_document_version_id,expected_chunk_id,expected_location_type,expected_sheet_name,expected_cell_range,expected_page_no,expected_page_label,expected_bbox_required,relevance,notes
```

Buckets and minimum seed counts:

| bucket | minimum count |
|---|---:|
| xlsx_lookup | 15 |
| xlsx_formula_value | 10 |
| xlsx_header_ambiguous | 10 |
| pdf_page_lookup | 15 |
| pdf_section_question | 15 |
| pdf_table_lookup | 10 |
| mixed_text_table | 10 |

Initial target:

```text
70-80 gold queries
```

Do not block the implementation if full 70-80 manual queries are not available. Add the CSV template and seed as many as current samples support, then document the shortage.

---

### P0-F. Add candidate index promotion gate skeleton

Goal: make `index_version` promotion measurable and block obviously bad candidates.

Add a service, script, or testable module depending on the repo structure.

Minimum gate inputs:

- `index_version`
- parser success summary
- metadata completeness summary
- citation accuracy summary
- retrieval metric summary when gold queries are available

Minimum gate thresholds:

| metric | threshold |
|---|---:|
| parser_success_rate | >= 0.90 |
| zero_indexable_chunk_count | = 0 |
| missing_required_metadata_count | = 0 |
| xlsx_citation_location_accuracy | >= 0.85 |
| pdf_citation_location_accuracy | >= 0.80 |
| Hit@10 | >= baseline - 0.05 |
| fatal_warning_count | = 0 |

Gate output:

```json
{
  "index_version": "candidate-20260503-001",
  "decision": "BLOCKED",
  "metrics": {
    "parser_success_rate": 0.92,
    "missing_required_metadata_count": 3,
    "hit_at_10": 0.81
  },
  "reasons": [
    "missing_required_metadata_count must be 0"
  ]
}
```

Acceptance criteria:

- gate can return `PASSED` or `BLOCKED`
- gate explains blocking reasons
- gate is testable without a live LLM
- promotion is not allowed when required citation metadata is missing

---

## 7. P1 tasks after P0 passes

Only start these after P0 smoke/eval skeleton is stable:

1. Populate `pdf_page_metadata` from PDF parsed artifacts.
2. Populate `table_metadata` from XLSX/PDF table artifacts.
3. Populate `cell_metadata` for XLSX detail traces.
4. Add Spring API endpoints for:
   - index build
   - promote
   - rollback
   - eval run
5. Add retrieval eval runner using `gold_queries_v0.csv`.
6. Add normalized citation table writes.

---

## 8. Suggested code locations

The exact repo layout may differ. Use `rg` to confirm.

Likely Java/Spring files:

```text
core-api/src/main/java/**/DocumentCatalogService*.java
core-api/src/main/java/**/DocumentCatalogController*.java
core-api/src/main/java/**/SearchUnitJpaEntity*.java
core-api/src/main/java/**/SearchUnitIndexingService*.java
core-api/src/main/resources/db/migration/V7__document_ingestion_v2.sql
```

Likely Python files:

```text
ai-worker/app/capabilities/rag/chunk_text_builder.py
ai-worker/tests/fixtures/parsed_artifacts/xlsx_v2_sample.json
ai-worker/tests/fixtures/parsed_artifacts/pdf_v2_sample.json
scripts/rag_ingestion_smoke.py
```

Likely new files:

```text
samples/rag_ingestion_manifest.json
scripts/rag_ingestion_sample_batch.py
scripts/rag_pdf_ingestion_smoke.py
eval/gold_queries_v0.csv
reports/.gitkeep
```

If the project convention puts scripts/tests elsewhere, follow the existing convention.

---

## 9. Test commands to run

Run targeted checks first:

```bash
mvn -f core-api/pom.xml -DskipTests compile
mvn -f core-api/pom.xml test "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitIndexingServiceTest,SearchUnitIndexingControllerTest"
python -m pytest tests/test_chunk_text_builder.py tests/test_search_unit_indexing.py tests/test_search_unit_indexing_loop.py tests/test_xlsx_extract_capability.py
python -m py_compile scripts/rag_ingestion_smoke.py
```

After adding new scripts/tests, also run:

```bash
python -m py_compile scripts/rag_ingestion_sample_batch.py
python -m py_compile scripts/rag_pdf_ingestion_smoke.py
```

If PDF parser tests are added:

```bash
python -m pytest tests/test_pdf_extract_capability.py tests/test_chunk_text_builder.py
```

Always finish with:

```bash
git diff --check
git status --short
```

---

## 10. Required completion report format

When finished, respond with this structure:

```text
## Summary
- ...

## Files changed
- ...

## Verification
- [passed/failed/skipped] command ...

## DB checks
- ...

## Known issues
- ...

## Remaining work
- ...

## Progress log entry added
- yes/no, path: ...
```

If any test or smoke check is skipped, say exactly why.

---

## 11. Progress log entry template

Append a new entry to the existing progress log, if present.

Suggested file:

```text
rag-ingestion-progress.md
```

Entry template:

```markdown
## 2026-05-03 - real sample ingestion smoke and PDF parser v1

### Goal

Validate real XLSX/PDF ingestion v2 behavior and add the next smoke/eval foundation.

### Completed

- ...

### Verification

- ...

### Important Decisions

- ...

### Remaining Work

- ...

### Next Recommended Step

- ...
```

---

## 12. Codex copy-paste prompt

Use this prompt when starting a fresh Codex task:

```text
You are working in this repository as a coding agent. Implement the next RAG ingestion v2 MVP step.

Current state:
- The project already has document/document_version/parsed_artifact tables, search_unit v2 fields, v2 citation response exposure, chunk_text_builder.py, parsed artifact fixtures, and scripts/rag_ingestion_smoke.py.
- The production ingestion path source_file -> extracted_artifact -> search_unit must be preserved.
- XLSX/PDF/OCR search units must not be indexed unless parser_version, location_json, and citation_text are present.
- XLSX location_json must preserve sheet/cell/table metadata.
- PDF location_json must preserve physical_page_index, page_no, page_label, bbox, block_type, OCR flags.

Your P0 tasks, in order:
1. Inspect the repo and summarize existing files/classes/scripts relevant to XLSX/PDF ingestion v2.
2. Run or prepare the live XLSX smoke validation for scripts/rag_ingestion_smoke.py.
3. Add a real-sample XLSX batch smoke runner using samples/rag_ingestion_manifest.json.
4. Add native PDF text extraction v1 with PyMuPDF/page/block/bbox metadata, without OCR optimization.
5. Add a PDF smoke runner that verifies parser_version, location_json, and citation_text for PDF search units.
6. Add eval/gold_queries_v0.csv template and seed rows if real sample labels are available.
7. Add a candidate index promotion gate skeleton that blocks promotion when required citation metadata is missing.
8. Add or update targeted tests.
9. Append a progress-log entry.

Non-goals:
- no hybrid retrieval
- no reranker
- no agentic RAG
- no full OCR optimization
- no broad refactor of existing ingestion
- no vector DB migration

Use a plan-first approach. Before editing, inspect the repo and provide a concise implementation plan. After editing, run targeted Java/Python tests and report skipped checks honestly.
```
