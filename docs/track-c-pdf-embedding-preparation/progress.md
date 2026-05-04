# Track C PDF Embedding Preparation Progress Log

This document tracks phase-by-phase progress for Track C PDF embedding preparation.
It follows the structure of `docs/rag-ingestion-progress.md` so entries can be merged back after Track C is complete.

Append a new entry after each work turn. Keep completed work, evidence, verification, remaining work, and risks separate.

## Status Vocabulary

| Status | Meaning |
|---|---|
| `PLANNED` | Phase is defined but not started |
| `IN_PROGRESS` | Work has started but the phase gate has not passed |
| `PASS` | Phase gate passed with required evidence |
| `PASS_WITH_WARNINGS` | Gate passed, but warnings must remain visible |
| `FAIL` | Phase ran and produced blocker evidence |
| `BLOCKED` | Phase cannot continue because an earlier gate or environment dependency is missing |
| `DIAGNOSTIC_ONLY` | Evidence is intentionally not promotion evidence |

## Current Phase Status

Last updated: `2026-05-05`

| Phase | Status | Evidence | Next Action |
|---|---|---|---|
| C0 Evidence Freeze | `PASS` | `reports/rag_pdf_current_diagnostic_snapshot.json` (`status=PASS`, sha256 `a680a2d096237b7cc0f7318377f0790cd29d558a7ac11a772246ee7daa4ebd63`) | Use snapshot as C1 input |
| C1 Candidate Scope Report | `PASS_WITH_WARNINGS` | `reports/pdf_candidate_scope_report.json` (`status=PASS_WITH_WARNINGS`, sha256 `3d8dba892d50bfa10dd62f33404c06ae517a4f2cb3fedca7fa1971956c55244a`) | Use explicit PDF scope for C2/C3; keep structured warnings visible |
| C2 Metadata Projection Readiness | `PASS_WITH_WARNINGS` | `reports/pdf_vector_metadata_projection_readiness.json` (`status=PASS_WITH_WARNINGS`, sha256 `113c064589ece17e3f36696c754445ebbc7c8ced5dc69bad7dc6fac3abb647cc`) | Proceed to C4; stored PDF candidate ragmeta projection remains deferred until C4 |
| C3 Embedding Text Contract Audit | `PASS_WITH_WARNINGS` | `reports/rag_pdf_embedding_text_contract_audit.json` (`status=PASS_WITH_WARNINGS`, sha256 `c470521af3d6a05cfba0f5cfc06bcce3c4d37e35a421ef84b572b37baec32646`) | Proceed to C4; keep skipped/policy-excluded rows visible |
| C4 Candidate Indexing Consistency | `PLANNED` | No PDF-only candidate indexing report yet | Run scoped PDF candidate indexing and implement/run the C4 consistency report |
| C5 PDF-only Vector Diagnostic | `PLANNED` | No PDF-only vector diagnostic report yet | Run diagnostic after C4 consistency passes |
| C6 Failure Breakdown | `PLANNED` | No PDF failure taxonomy report yet | Split metadata/ranking/gold/policy failures |
| C7 Gold Policy Review | `PLANNED` | No gold policy report yet | Review page/table/OCR/bbox policy after C6 |

## Merge Policy

- Keep this file chronological and append-only during Track C execution.
- Use one dated entry per work turn, matching the section style in `docs/rag-ingestion-progress.md`.
- Record only evidence actually produced in that turn.
- Do not mark a phase `PASS` unless the report, command, or test output is listed under `Current Evidence` or `Verification`.
- Keep `promotion_evidence=false`, `evidence_role=diagnostic`, namespace, baseline, and XLSX artifact status visible in every C4+ diagnostic entry.
- When C7 changes a gold/page/table/OCR policy, add a follow-up C6 entry for reclassification instead of editing old C6 results.
- After Track C is complete, merge the dated entries into `docs/rag-ingestion-progress.md` and keep this file as temporary source material or delete it in that cleanup commit.

## Entry Template

```markdown
## YYYY-MM-DD - Track C Cn short title

### Goal

- ...

### Completed

- ...

### Current Evidence

- ...

### Gate/Baseline Status

- Promotion was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.

### Verification

- Command:
  - `...`
  - result: ...

### Important Decisions

- ...

### Remaining Work

- ...

### Risks

- ...
```

## 2026-05-05 - Track C phase plan split and progress log seed

### Goal

- Split the original Track C PDF embedding preparation plan into phase-level docs.
- Add a Track C-local progress log that can later be merged into `docs/rag-ingestion-progress.md`.
- Keep the work documentation-only; no retrieval, indexing, promotion, or baseline mutation.

### Completed

- Created `docs/track-c-pdf-embedding-preparation/README.md`.
- Created `docs/track-c-pdf-embedding-preparation/contracts.md`.
- Created `docs/track-c-pdf-embedding-preparation/phase-map.md`.
- Created `docs/track-c-pdf-embedding-preparation/artifacts-and-reports.md`.
- Created `docs/track-c-pdf-embedding-preparation/risks-and-acceptance.md`.
- Created `docs/track-c-pdf-embedding-preparation/runbook.md`.
- Created C0~C7 phase documents under `docs/track-c-pdf-embedding-preparation/phases/`.
- Added this progress log as `docs/track-c-pdf-embedding-preparation/progress.md`.

### Current Evidence

- Track C phase docs exist and are linked from the directory README.
- C0~C7 are still `PLANNED`; no phase execution report has been generated yet.
- The phase map preserves the required order:
  - `C0/C1 -> C2/C3 -> C4 -> C5/C6 -> C7`
  - C7 may return to C6 when gold policy changes require reclassification.

### Gate/Baseline Status

- Promotion was not run.
- No Track C report sets `promotion_evidence=true`.
- No PDF candidate indexing was run in this documentation pass.
- Immutable baseline artifacts were not intentionally changed.
- XLSX candidate artifacts were not intentionally changed.

### Verification

- Diff hygiene:
  - `git diff --check`
  - result: passed with an existing CRLF warning for `docs/rag-ingestion-progress.md`.
- New Track C docs whitespace scan:
  - `rg -n "[ \\t]+$" "docs\\track-c-pdf-embedding-preparation" "docs\\track_c_pdf_embedding_preparation_plan.md"`
  - result: no trailing whitespace matches.

### Important Decisions

- Track C progress will be recorded locally in this directory until the work is complete.
- The progress file uses the same major section names as `docs/rag-ingestion-progress.md` to make later merging straightforward.
- Phase status remains separate from phase plans so future work can update status without rewriting the plan docs.

### Remaining Work

- Start C0 by freezing the current PDF diagnostic snapshot.
- Update the `Current Phase Status` table after each phase turn.
- Merge completed Track C entries back into `docs/rag-ingestion-progress.md` after the Track C work is finished.

### Risks

- This entry documents planning and structure only; it does not prove PDF metadata projection, embedding text contract, candidate indexing, vector diagnostic quality, or gold policy readiness.
- The repository already has unrelated modified/untracked reports and docs, so future Track C entries should keep changed artifact scope explicit.

## 2026-05-05 - Track C C0 PDF current diagnostic snapshot

### Goal

- Freeze the current PDF diagnostic baseline before C1/C2/C3 work.
- Record current full72 PDF counters, report hashes, and baseline/XLSX artifact unchanged checks without running retrieval, indexing, promotion, or cleanup.

### Completed

- Added `scripts/rag_pdf_current_diagnostic_snapshot.py`.
- Added the C0 command to `docs/track-c-pdf-embedding-preparation/runbook.md`.
- Generated `reports/rag_pdf_current_diagnostic_snapshot.json`.
- Updated the current phase table so only C0 is marked `PASS`.

### Current Evidence

- C0 snapshot:
  - path: `reports/rag_pdf_current_diagnostic_snapshot.json`
  - status: `PASS`
  - run_id: `2026-05-04T163332Z`
  - sha256: `a680a2d096237b7cc0f7318377f0790cd29d558a7ac11a772246ee7daa4ebd63`
- Input full72 vector diagnostic:
  - path: `reports/rag_retrieval_eval_full72_vector_diagnostic_report.json`
  - sha256: `6d69284ffafbda18d08622adfd5d8e41186309e1f70441cb9c3b40d79132873c`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
- PDF gold/query subset:
  - PDF query count: `22`
  - PDF positive count: `22`
  - query coverage complete: `true`
  - duplicate/missing/extra PDF query ids: none
  - buckets: `pdf_page_lookup=8`, `pdf_section_question=8`, `pdf_table_lookup=6`
  - document versions: `docv_88368b8b12ba3f38`, `docv_8b23a58c27c5518a`, `docv_fe2470815512a395`
- Current PDF diagnostic counters:
  - `pdf_file_hit@10=0.9091`
  - `pdf_page_hit@10=0.0`
  - `pdf_bbox_overlap@10=0.0`
  - `pdf_citation_location_accuracy=0.0`
  - `page_no_hit_at_top_k_count=10`
  - `correct_page_no_hit_but_missing_physical_page_index_count=10`
  - `correct_page_no_hit_but_missing_bbox_count=5`
  - `expected_file_absent_in_top_k_count=2`
  - `expected_page_no_absent_in_top_k_count=12`
  - `expected_bbox_overlap_absent_in_top_k_count=17`

### Gate/Baseline Status

- Promotion was not run.
- Retrieval was not run.
- PDF candidate indexing was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_pdf_current_diagnostic_snapshot.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_current_diagnostic_snapshot.py`
  - result: `6 passed`.
- Command:
  - `python scripts/rag_pdf_current_diagnostic_snapshot.py --output reports/rag_pdf_current_diagnostic_snapshot.json`
  - result: `status=PASS`; PDF query count `22`; query coverage complete `true`; page_no hit `10`; missing physical page index `10`; missing bbox `5`; PDF candidate artifact exists `false`; immutable baseline changed `false`; XLSX candidate artifact changed `false`.
- Command:
  - `rg -n "[ \\t]+$" docs\\track-c-pdf-embedding-preparation scripts\\rag_pdf_current_diagnostic_snapshot.py ai-worker\\tests\\test_rag_pdf_current_diagnostic_snapshot.py reports\\rag_pdf_current_diagnostic_snapshot.json`
  - result: no trailing whitespace matches.
- Command:
  - `git diff --check`
  - result: passed; emitted existing CRLF warnings for unrelated working-tree files.

### Important Decisions

- C0 is intentionally file-based: it reads existing reports/CSV/artifacts and does not connect to the DB.
- The current PDF metric state is frozen as diagnostic evidence only. It is not interpreted as ranking failure until C2/C3/C4 pass.
- C1 should start from the explicit PDF document scope recorded by C0, not from a broad unscoped PDF scan.
- Existing `rag-data-pdf-candidate-v1` now fails C0 unless a future workflow explicitly introduces a controlled override.

### Remaining Work

- Implement and run `scripts/pdf_candidate_scope_report.py` for C1.
- Keep C2/C3 blocked until C1 produces `reports/pdf_candidate_scope_report.json`.
- Keep C4/C5/C6/C7 blocked until their documented prerequisite reports exist.

### Risks

- C0 does not prove metadata projection readiness, embedding text contract, PDF candidate indexing consistency, vector diagnostic quality, or gold policy readiness.
- The PDF candidate artifact dir does not exist yet, which is expected for C0 and should not be created before C2/C3 pass.

## 2026-05-05 - Track C C1 PDF candidate scope report

### Goal

- Build and run a read-only PDF candidate scope report from the C0 snapshot.
- Confirm the explicit PDF SearchUnit scope before any C2/C3 projection or text-contract work.
- Keep retrieval, indexing, promotion, and artifact mutation out of C1.

### Completed

- Added `scripts/pdf_candidate_scope_report.py`.
- Added `ai-worker/tests/test_pdf_candidate_scope_report.py`.
- Generated `reports/pdf_candidate_scope_report.json`.
- Updated `docs/track-c-pdf-embedding-preparation/runbook.md` with the C1 syntax/test command.
- Updated the C4 runbook command so future indexing consumes the C1 explicit scope report.
- Updated the current phase table so C1 is marked `PASS_WITH_WARNINGS`.

### Current Evidence

- C1 scope report:
  - path: `reports/pdf_candidate_scope_report.json`
  - status: `PASS_WITH_WARNINGS`
  - run_id: `2026-05-04T165009Z`
  - sha256: `3d8dba892d50bfa10dd62f33404c06ae517a4f2cb3fedca7fa1971956c55244a`
- Explicit PDF scope:
  - PDF query count: `22`
  - PDF positive count: `22`
  - document versions: `docv_88368b8b12ba3f38`, `docv_8b23a58c27c5518a`, `docv_fe2470815512a395`
  - source files: `105eb112-2bc4-4f35-a877-f0a6dd487288`, `2847f7af-cfe4-41de-8393-58912df2dba9`, `80ee7b61-102e-425d-80dc-d4d693bf8be8`
  - bucket/location mismatch count: `0`
- C1 required gate counters:
  - `scoped_search_unit_count=8203`
  - `candidate_rows=8203`
  - `missing_location_json_count=0`
  - `missing_citation_text_count=0`
  - `missing_embedding_text_count=0`
  - `missing_page_metadata_count=0`
  - `path_mixing_count=0`
  - `unsupported_parser_version_count=0`
- Metadata and OCR summary:
  - page-bound SearchUnits: `8203`
  - distinct page references: `237`
  - matched page metadata count: `237`
  - native PDF rows: `8190`
  - OCR rows: `13`
  - OCR confidence missing count: `6`
  - OCR bbox missing count: `3`
  - parser versions: `pdf-extract-v1=2863`, `pdf-extract-v2=5340`
  - embedding statuses: `EMBEDDED=8194`, `SKIPPED=9`
  - source file statuses: `READY=3`
- Structured C1 warnings:
  - `ocr_confidence_missing_count=6`
  - `missing_required_bbox_count=3`
  - `ocr_bbox_missing_count=3`
  - `embedding_status_counts.SKIPPED=9`

### Gate/Baseline Status

- Promotion was not run.
- Retrieval was not run.
- PDF candidate indexing was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- `retrieval_execution=not_run_by_this_script`.
- `indexing_execution=not_run_by_this_script`.
- `promotion_execution=not_run_by_this_script`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- `allowUnscoped=false`.
- Existing PDF candidate artifact dir: `false`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/pdf_candidate_scope_report.py ai-worker/tests/test_pdf_candidate_scope_report.py`
  - result: passed.
- Command:
  - `python scripts/pdf_candidate_scope_report.py --output reports/pdf_candidate_scope_report.json`
  - result: `status=PASS_WITH_WARNINGS`; scoped SearchUnits `8203`; candidate rows `8203`; all required C1 blocker counters `0`; OCR confidence missing `6`.
- Command:
  - `python -m pytest ai-worker/tests/test_pdf_candidate_scope_report.py`
  - result: `6 passed`.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_current_diagnostic_snapshot.py ai-worker/tests/test_pdf_candidate_scope_report.py`
  - result: `12 passed`.

### Important Decisions

- C1 derives scope from the C0 snapshot and PDF gold rows, not from a broad unscoped PDF scan.
- C1 includes PDF gold rows only when `expected_location_type=pdf`; pdf bucket/location mismatches are blockers.
- OCR confidence gaps are a visible C1 warning, not a C1 blocker. C2/C3 must classify them before C4 indexing.
- `missing_required_bbox_count=3` remains visible for C2/C3 readiness even though the documented C1 blocker counters passed.
- C1 remains diagnostic-only and does not create `rag-data-pdf-candidate-v1`.
- C4 indexing must consume `reports/pdf_candidate_scope_report.json` or an equivalent explicit `documentVersionIds`/`sourceFileIds` scope.

### Remaining Work

- Implement and run `scripts/pdf_vector_metadata_projection_readiness.py` for C2.
- Implement and run `scripts/rag_pdf_embedding_text_contract_audit.py` for C3.
- Keep C4 blocked until C2/C3 explicitly pass or resolve their warnings.

### Risks

- C1 does not prove vector metadata projection, embedding text contract, indexing consistency, retrieval quality, or gold policy readiness.
- OCR confidence missing count `6`, OCR bbox missing count `3`, and `SKIPPED=9` embedding statuses need C2/C3 classification before PDF candidate indexing.

## 2026-05-05 - Track C C2/C3 readiness audits

### Goal

- Run the C2 metadata projection readiness audit and C3 embedding text contract audit from the explicit C1 PDF scope.
- Keep both audits read-only and diagnostic-only: no retrieval, indexing, promotion, candidate artifact creation, baseline mutation, or XLSX artifact mutation.
- If the current evidence fails, preserve the failure as blocker evidence and identify the smallest repair surface before C4.

### Completed

- Added `scripts/pdf_vector_metadata_projection_readiness.py`.
- Added `scripts/rag_pdf_embedding_text_contract_audit.py`.
- Added `ai-worker/tests/test_pdf_vector_metadata_projection_readiness.py`.
- Added `ai-worker/tests/test_rag_pdf_embedding_text_contract_audit.py`.
- Generated `reports/pdf_vector_metadata_projection_readiness.json`.
- Generated `reports/rag_pdf_embedding_text_contract_audit.json`.
- Updated `docs/track-c-pdf-embedding-preparation/runbook.md` with C0~C3 syntax/test commands and the focused Java guardrail command.
- Updated this progress table so C2/C3 are `FAIL` and C4 is `BLOCKED`.
- Fixed the future SearchUnit claim metadata path so `locationJson` is projected as a plain JSON map instead of a Jackson `JsonNode` shape.

### Current Evidence

- C2 metadata projection readiness:
  - path: `reports/pdf_vector_metadata_projection_readiness.json`
  - status: `FAIL`
  - run_id: `2026-05-04T175858Z`
  - sha256: `fbc6749941fc03da324e94b05257e83bed2a331b44bd279cb9f5642d997f3edb`
  - scoped rows: `8203`
  - indexable rows: `8194`
  - policy-excluded rows: `9`
  - `metadata_projection_blocker_count=24345`
  - current ragmeta joined embedded rows: `8194`
  - current ragmeta `locationJson` Jackson shape count: `8194`
  - current ragmeta unusable location count: `8194`
  - current ragmeta missing physical page index count: `8194`
  - current ragmeta missing text-block bbox count: `7957`
  - expected PDF candidate namespace chunk count: `0` before C4
  - sample blocker rows: `25` current-ragmeta Jackson-shape projection examples
- C3 embedding text contract audit:
  - path: `reports/rag_pdf_embedding_text_contract_audit.json`
  - status: `FAIL`
  - run_id: `2026-05-04T175857Z`
  - sha256: `9f5f79e1a2416c7e93defd240557757f36fc0d47d5efd17db71a290e438305bd`
  - scoped rows: `8203`
  - indexable rows: `8194`
  - policy-excluded rows: `9`
  - `text_contract_blocker_count=32723`
  - missing source surface in `embedding_text`: `8179`
  - missing page surface in `embedding_text`: `8179`
  - missing citation surface in `embedding_text`: `8179`
  - missing block type surface in `embedding_text`: `8179`
  - embedded OCR trust marker missing count: `7`
  - leakage counters: all `0`
- C1 warning classification:
  - OCR confidence missing rows are policy-excluded before C4: `6`
  - document summaries are policy-excluded before C4: `3`
  - skipped searchable rows remain visible for C4 exclusion: `9`
  - page/document bbox absence is warning-only after chunk-type policy: `3`
  - current PDF table gold rows have no table-like SearchUnits: `6`

### Gate/Baseline Status

- Promotion was not run.
- Retrieval was not run.
- PDF candidate indexing was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- `retrieval_execution=not_run_by_this_script`.
- `indexing_execution=not_run_by_this_script`.
- `promotion_execution=not_run_by_this_script`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- `allowUnscoped=false`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.
- C4 is `BLOCKED` until C2/C3 pass.

### Verification

- Command:
  - `python -m py_compile scripts/pdf_vector_metadata_projection_readiness.py scripts/rag_pdf_embedding_text_contract_audit.py ai-worker/tests/test_pdf_vector_metadata_projection_readiness.py ai-worker/tests/test_rag_pdf_embedding_text_contract_audit.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_pdf_vector_metadata_projection_readiness.py ai-worker/tests/test_rag_pdf_embedding_text_contract_audit.py`
  - result: `11 passed`.
- Command:
  - `python scripts/pdf_vector_metadata_projection_readiness.py --output reports/pdf_vector_metadata_projection_readiness.json`
  - result: `status=FAIL`; exit code `2` as expected for blocker evidence; report written.
- Command:
  - `python scripts/rag_pdf_embedding_text_contract_audit.py --output reports/rag_pdf_embedding_text_contract_audit.json`
  - result: `status=FAIL`; exit code `2` as expected for blocker evidence; report written.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_current_diagnostic_snapshot.py ai-worker/tests/test_pdf_candidate_scope_report.py ai-worker/tests/test_pdf_vector_metadata_projection_readiness.py ai-worker/tests/test_rag_pdf_embedding_text_contract_audit.py`
  - result: `20 passed`.
- Command:
  - `mvn -f core-api/pom.xml test "-Dtest=SearchUnitIndexingServiceTest#claim_index_metadata_keeps_location_json_as_plain_map_not_jackson_node_shape"`
  - result: `BUILD SUCCESS`; `1` test passed.

### Important Decisions

- C2 source SearchUnit metadata is complete for indexable rows, but current ragmeta metadata projection is not usable proof for vector-hit reconstruction.
- Existing ragmeta rows under the current non-PDF-candidate index version are diagnostic evidence only. They do not count as PDF candidate namespace proof.
- The Java claim path now serializes parsed JSON metadata as plain maps for future indexing, but existing ragmeta rows were not rewritten.
- C3 treats raw content-only `embedding_text` as a blocker even when `bm25_text` and `citation_text` contain source/page/bbox context.
- OCR rows without confidence remain policy-excluded before C4; embedded OCR rows must carry an explicit lower-trust marker before C3 can pass.

### Remaining Work

- Repair or rebuild PDF SearchUnit `embedding_text` so indexable rows include source, page, citation, block type, and OCR trust context.
- Refresh/rebuild the PDF candidate namespace after the C2/C3 repairs so ragmeta chunks contain usable plain PDF location metadata.
- Rerun C2 and C3 after repair; keep C4 blocked until both reports pass.
- Decide in C7 or a dedicated repair step whether PDF table gold rows require table-like SearchUnits or can remain paragraph/page-backed.

### Risks

- C2/C3 are failing by design on the current DB state; moving to C4 now would likely preserve bad vector metadata and context-poor embeddings.
- The Java serialization fix only affects future claims and callbacks. Existing `ragmeta.chunks` rows still need a controlled rebuild or repair path.
- C3 is intentionally stricter than current legacy PDF embedding behavior, so the repair may require a SearchUnit text-surface regeneration step before candidate indexing.

## 2026-05-05 - Track C C2/C3 repair follow-through

### Goal

- Continue after the C2/C3 failure evidence and clear the missing PDF SearchUnit text/metadata surfaces before C4.

### Completed

- Added `scripts/rag_pdf_search_unit_surface_repair.py`.
- Added `ai-worker/tests/test_rag_pdf_search_unit_surface_repair.py`.
- Hardened the repair scope to C1 `document_version_ids`, `source_file_ids`, `source_file_type=PDF`, and C1 parser versions.
- Ran repair dry-run, reviewed scoped mutation samples, and applied the repair to the local DB.
- Reran C2 and C3 after repair; both moved from `FAIL` to `PASS_WITH_WARNINGS`.
- Updated `docs/track-c-pdf-embedding-preparation/runbook.md` with the C3 repair command and test coverage.
- Updated this progress table so C2/C3 are `PASS_WITH_WARNINGS` and C4 is `PLANNED`.

### Current Evidence

- C3 repair:
  - path: `reports/rag_pdf_search_unit_surface_repair_report.json`
  - status: `PASS`
  - run_id: `2026-05-04T181038Z`
  - sha256: `ad720a7172b702745db86a915efa3f1a2ee5a48b71474110705eb7f3c66deec6`
  - dry-run/apply scope: `8203` scoped rows, `8194` indexable rows, `9` policy-excluded rows
  - before repair: `repair_needed_count=8179`, `state_reset_needed_count=8194`, `mutation_needed_count=8194`
  - after repair: `repair_needed_count=0`, `state_reset_needed_count=0`, `mutation_needed_count=0`
  - updated SearchUnit rows: `8194`
  - deleted embedding records: `0`
  - deleted ragmeta chunks: `0`
- C2 metadata projection readiness:
  - path: `reports/pdf_vector_metadata_projection_readiness.json`
  - status: `PASS_WITH_WARNINGS`
  - run_id: `2026-05-04T181046Z`
  - sha256: `113c064589ece17e3f36696c754445ebbc7c8ced5dc69bad7dc6fac3abb647cc`
  - `metadata_projection_blocker_count=0`
  - vector-hit reconstruction failure count: `0`
  - current ragmeta joined embedded rows: `0`
  - expected PDF candidate namespace chunk count: `0` before C4
- C3 embedding text contract audit:
  - path: `reports/rag_pdf_embedding_text_contract_audit.json`
  - status: `PASS_WITH_WARNINGS`
  - run_id: `2026-05-04T181046Z`
  - sha256: `c470521af3d6a05cfba0f5cfc06bcce3c4d37e35a421ef84b572b37baec32646`
  - `text_contract_blocker_count=0`
  - checked embedding text rows: `8194`
  - source/page/citation/block surfaces present: `8194`
  - embedded OCR trust marker missing count: `0`
  - leakage counters: all `0`

### Gate/Baseline Status

- Promotion was not run.
- Retrieval was not run.
- PDF candidate indexing was not run.
- SearchUnit repair was applied to the local DB only.
- `promotion_evidence=false`.
- `evidence_role=diagnostic` or `repair_diagnostic`.
- `retrieval_execution=not_run_by_this_script`.
- `indexing_execution=not_run_by_this_script`.
- `promotion_execution=not_run_by_this_script`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- `allowUnscoped=false`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.
- C4 is no longer blocked by C2/C3, but it has not been run.

### Verification

- Command:
  - `python -m py_compile scripts/rag_pdf_current_diagnostic_snapshot.py scripts/pdf_candidate_scope_report.py scripts/pdf_vector_metadata_projection_readiness.py scripts/rag_pdf_embedding_text_contract_audit.py scripts/rag_pdf_search_unit_surface_repair.py ai-worker/tests/test_rag_pdf_current_diagnostic_snapshot.py ai-worker/tests/test_pdf_candidate_scope_report.py ai-worker/tests/test_pdf_vector_metadata_projection_readiness.py ai-worker/tests/test_rag_pdf_embedding_text_contract_audit.py ai-worker/tests/test_rag_pdf_search_unit_surface_repair.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_current_diagnostic_snapshot.py ai-worker/tests/test_pdf_candidate_scope_report.py ai-worker/tests/test_pdf_vector_metadata_projection_readiness.py ai-worker/tests/test_rag_pdf_embedding_text_contract_audit.py ai-worker/tests/test_rag_pdf_search_unit_surface_repair.py`
  - result: `29 passed`.
- Command:
  - `python scripts/rag_pdf_search_unit_surface_repair.py --output reports/rag_pdf_search_unit_surface_repair_report.json`
  - result: `status=PASS_WITH_WARNINGS`; dry-run reported `mutation_needed_count=8194`.
- Command:
  - `python scripts/rag_pdf_search_unit_surface_repair.py --apply --output reports/rag_pdf_search_unit_surface_repair_report.json`
  - result: `status=PASS`; `updated_search_unit_count=8194`; post-apply `mutation_needed_count=0`.
- Command:
  - `python scripts/pdf_vector_metadata_projection_readiness.py --output reports/pdf_vector_metadata_projection_readiness.json`
  - result: `status=PASS_WITH_WARNINGS`; exit code `0`.
- Command:
  - `python scripts/rag_pdf_embedding_text_contract_audit.py --output reports/rag_pdf_embedding_text_contract_audit.json`
  - result: `status=PASS_WITH_WARNINGS`; exit code `0`.
- Command:
  - `mvn -f core-api/pom.xml test "-Dtest=SearchUnitIndexingServiceTest#claim_index_metadata_keeps_location_json_as_plain_map_not_jackson_node_shape"`
  - result: `BUILD SUCCESS`; `1` test passed.

### Important Decisions

- C2/C3 pass now means the scoped SearchUnit source surfaces are ready for C4, not that PDF candidate vectors already exist.
- Existing legacy ragmeta rows were not deleted or rewritten; C4 must create and verify the PDF candidate namespace.
- SearchUnit rows were reset to `PENDING` so the candidate indexing path can re-claim and re-embed the repaired text.
- OCR rows without confidence and document summaries remain policy-excluded; they must stay visible as warnings through C4.

### Remaining Work

- Run scoped C4 candidate indexing for `rag-ingestion-v2-pdf-candidate-v1`.
- Implement or finish `scripts/pdf_candidate_embedding_consistency.py` before calling C4 complete.
- Verify PDF candidate ragmeta chunk metadata after C4, including plain `locationJson`/`location_json`, citation text, page index, bbox, and chunk identity.
- Decide in C7 or a dedicated parser/gold policy step whether PDF table gold rows require table-like SearchUnits or can remain paragraph/page-backed.

### Risks

- C2 currently has no stored PDF candidate ragmeta chunks to compare because C4 has not created the candidate namespace yet.
- The local DB now has repaired SearchUnits in `PENDING`; running unrelated broad indexing before C4 could consume those rows outside the intended PDF candidate flow.
- C4 consistency is not proven until the PDF-only candidate index and report exist.
