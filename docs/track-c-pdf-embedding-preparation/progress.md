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
| C4 Candidate Indexing Consistency | `PASS` | `reports/pdf_candidate_indexing_report.json` (`status=PASS`, sha256 `7f4853897e2a184e06e55025931d6924e7933f46aceb013550100b7caa785a6c`); `reports/pdf_candidate_embedding_consistency_report.json` (`status=PASS`, sha256 `311569fe45f6c0b834e9a6b8f1ace065fa035ec143cc8a8c05fb930eb173abc1`) | Proceed only to C5/C6 diagnostics; do not treat C4 as retrieval or promotion evidence |
| C5 PDF-only Vector Diagnostic | `PASS_WITH_WARNINGS` | `reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json` (`status=PASS_WITH_WARNINGS`, sha256 `4c23f777a64045096ffda2afe322c06a04b394076bdc52f05367ce7f38309e38`) | Run C6 failure breakdown for 14 ranking/location failures |
| C6 Failure Breakdown | `PASS` | `reports/rag_pdf_vector_quality_breakdown.json` (`status=PASS`, sha256 `39036a5d6e0eac013c926e98917eff85ee7a585331da760fd86f44a9849475d5`) | Proceed to C7 gold policy review for 7 gold/policy candidates and 1 chunk-granularity candidate |
| C7 Gold Policy Review | `PASS_WITH_WARNINGS` | `reports/rag_pdf_gold_policy_review.json` (`status=PASS_WITH_WARNINGS`, sha256 `0d31ebf7b5f4e92c17b4fe87ace95160342d009ded2b5d4726a16757f4312a1d`) | Review 8 relabel candidates and rerun C6 if accepted; do not start retrieval tuning yet |
| C7.1 Policy Decision Overlay | `PASS_WITH_WARNINGS` | `reports/rag_pdf_gold_policy_decision_overlay.json` (`status=PASS_WITH_WARNINGS`, sha256 `f06c5c19d10951db5462edf5930d577f2f4eadee50c61a61d526fa00cf738982`); `eval/gold_queries_pdf_v1_reviewed.csv` (sha256 `442b116e6c0141e05ee6114b7732951ffd578d6fac10aa255ca0b3f1b4814c03`) | Use reviewed manifest for C6.1/C5.1; keep 6 table rows pending |
| C6.1 Policy-Applied Reclassification | `PASS` | `reports/rag_pdf_vector_quality_breakdown_after_policy.json` (`status=PASS`, sha256 `74fffc37c4349f3f58309522756be507e81cb5cb5cf0bed69b957ea491ce68e8`) | Package 7 reviewed non-table failures for C8 |
| C5.1 Reviewed PDF Vector Diagnostic | `PASS_WITH_WARNINGS` | `reports/rag_retrieval_eval_pdf_v1_reviewed_vector_diagnostic_report.json` (`status=PASS_WITH_WARNINGS`, sha256 `c8424c4acd0e16d7f03b40789b673ae1351578393981a4bd21a0cae3a59f46b8`) | Treat metrics as diagnostic; do not promote or baseline |
| C8 Retrieval Tuning Case Pack | `PASS` | `reports/rag_pdf_retrieval_tuning_case_pack.json` (`status=PASS`, sha256 `2c45059affe749fc5b2565d6f693c8eee7054a865b91642093e06257266b8dd7`) | Investigate the 7 cases individually before any tuning |
| C8.1 Case-Level Investigation | `PASS` | `reports/rag_pdf_c8_case_investigation_report.json` (`status=PASS`, sha256 `f6919bd71e03df66e62388c9db93d061e129d0df929f2bd877c395711cb41b83`) | Review 5 query-surface cases, 1 file-recall case, and 1 embedding-surface case before any narrow change |
| C8.2 Rank Probe | `PASS` | `reports/rag_pdf_c8_rank_probe_report.json` (`status=PASS`, sha256 `88a4c53cbe187f9fb6459d03d7a2d5a34b3c1f2816e63f7bff6f6e287de7fb47`) | Continue case-level review; do not run broad tuning |
| C8.3 Case-Level Review | `PASS_WITH_WARNINGS` | `reports/rag_pdf_c8_case_level_review_report.json` (`status=PASS_WITH_WARNINGS`, sha256 `4eec88d6fc734b9c4d80ac7890c7231832eb652b2a58aa70448dd1545c2bc5c3`) | Use C8.4 overlay for manual label/query/page/file decisions; no broad tuning |
| C8.4 Case Decision Overlay | `PASS_WITH_WARNINGS` | `reports/rag_pdf_c8_case_decision_overlay.json` (`status=PASS_WITH_WARNINGS`, sha256 `cb231fde587f2406a378cdcbb11b7d8102e84ede17289600646b60077cc482e2`) | Decide whether to accept overlay query rewrites and resolve 2 pending case-review rows before any diagnostic rerun |

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

## 2026-05-05 - Track C C4 PDF candidate indexing consistency

### Goal

- Build the PDF-only candidate namespace `rag-ingestion-v2-pdf-candidate-v1`.
- Keep indexing scoped to the C1 PDF `document_version_ids`, `source_file_ids`, parser versions, and `source_file_type=PDF`.
- Prove SearchUnit status/claim/index metadata, `embedding_record`, and `ragmeta.chunks` consistency without running retrieval, promotion, baseline updates, or XLSX candidate artifact mutation.

### Completed

- Added `scripts/pdf_candidate_embedding_consistency.py`.
- Added `ai-worker/tests/test_pdf_candidate_embedding_consistency.py`.
- Updated `scripts/rag_scoped_candidate_indexing.py` so C4 can consume `reports/pdf_candidate_scope_report.json` directly and avoid accidental full72 gold-scope unioning.
- Updated `docs/track-c-pdf-embedding-preparation/runbook.md` with the C4 scope-report indexing and consistency commands.
- Ran a scoped dry-run/diagnostic, confirmed the C1 scope is exactly 3 PDF document versions, 3 source files, `PDF`, and `pdf-extract-v1/v2`.
- Started a temporary Core API on port `8081` with `AIPIPELINE_SEARCH_UNIT_INDEXING_CANDIDATE_INDEX_VERSION=rag-ingestion-v2-pdf-candidate-v1`, because the existing local Core API on port `8080` was configured for the old candidate namespace.
- Ran a 1-row canary, then full scoped C4 indexing into `rag-data-pdf-candidate-v1`.
- Generated the C4 consistency proof report and marked C4 `PASS`.

### Current Evidence

- C4 dry-run:
  - path: `reports/pdf_candidate_indexing_dry_run_report.json`
  - status: `PASS`
  - sha256: `ac87895c185cd82c24c6a5d5de95da63e9d12cdac5afee102bdc59bd7aa735d1`
  - scope: 3 C1 PDF document versions, 3 C1 source files, source file type `PDF`, parser versions `pdf-extract-v1/pdf-extract-v2`
  - dry-run claimed/indexed rows: `0` by worker design; dry-run does not call claim or mutate state
- C4 canary:
  - path: `reports/pdf_candidate_indexing_canary_report.json`
  - status: `FAIL` only because `max_cycles=1` intentionally stopped before the full scope emptied
  - sha256: `9413223bebd294d934b21dc232bfeb8eb6a472e2300030dcf50db5e5054543c7`
  - claimed/indexed/failed: `1/1/0`
- C4 indexing report:
  - path: `reports/pdf_candidate_indexing_report.json`
  - status: `PASS`
  - sha256: `32e8ee1cae3ef99a70ec13098993031f38d2b289f5801037d7fb0af6c0fbfd39`
  - non-dry-run: `true`
  - `allowUnscoped=false`
  - expected index version: `rag-ingestion-v2-pdf-candidate-v1`
  - totals: `claimed=8193`, `indexed=8193`, `failed=0`, `stale=0`, `skipped_local=0`
  - note: the prior canary indexed the first row, so full-run totals are `8193`; final consistency covers all `8194` candidate rows
- C4 consistency report:
  - path: `reports/pdf_candidate_embedding_consistency_report.json`
  - status: `PASS`
  - sha256: `4247be2171cdfa968fe4a874c34f4871a2c023264c9be0890a354f8fabfc985d`
  - scoped rows: `8203`
  - candidate rows: `8194`
  - policy-excluded rows: `9`
  - status counts: `EMBEDDED=8194`, `SKIPPED=9`
  - index version counts: `rag-ingestion-v2-pdf-candidate-v1=8194`, `UNKNOWN=9`
  - blocker counters: all C4 mismatch/missing counters `0`
- PDF candidate artifact:
  - path: `rag-data-pdf-candidate-v1`
  - `build.json` index version: `rag-ingestion-v2-pdf-candidate-v1`
  - embedding model: `BAAI/bge-m3`
  - dimension: `1024`
  - chunk count: `8194`
  - `ingest_manifest.json` document count: `3`

### Gate/Baseline Status

- Promotion was not run.
- Retrieval was not run.
- Baseline pass was not attempted.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- `retrieval_execution=not_run_by_this_script`.
- `promotion_execution=not_run_by_this_script`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- `allowUnscoped=false`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_scoped_candidate_indexing.py scripts/pdf_candidate_embedding_consistency.py ai-worker/tests/test_pdf_candidate_embedding_consistency.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_pdf_candidate_embedding_consistency.py -q`
  - result: `4 passed`.
- Command:
  - `python scripts/rag_scoped_candidate_indexing.py --dry-run --scope-report reports/pdf_candidate_scope_report.json --source-file-type PDF --parser-version pdf-extract-v1 --parser-version pdf-extract-v2 --expected-index-version rag-ingestion-v2-pdf-candidate-v1 --output reports/pdf_candidate_indexing_dry_run_report.json`
  - result: `status=PASS`; exact C1 PDF scope; no mutation.
- Command:
  - `python scripts/rag_scoped_candidate_indexing.py --scope-report reports/pdf_candidate_scope_report.json --source-file-type PDF --parser-version pdf-extract-v1 --parser-version pdf-extract-v2 --expected-index-version rag-ingestion-v2-pdf-candidate-v1 --batch-size 1 --limit 1 --max-cycles 1 --output reports/pdf_candidate_indexing_canary_report.json`
  - result: canary claim/callback applied; `claimed=1`, `indexed=1`, `failed=0`; report status `FAIL` because the run was intentionally limited to one cycle.
- Command:
  - `python scripts/rag_scoped_candidate_indexing.py --scope-report reports/pdf_candidate_scope_report.json --source-file-type PDF --parser-version pdf-extract-v1 --parser-version pdf-extract-v2 --expected-index-version rag-ingestion-v2-pdf-candidate-v1 --batch-size 200 --limit 200 --max-cycles 60 --output reports/pdf_candidate_indexing_report.json`
  - result: `status=PASS`; `claimed=8193`, `indexed=8193`, `failed=0`.
- Command:
  - `python scripts/pdf_candidate_embedding_consistency.py --scope-report reports/pdf_candidate_scope_report.json --c2-report reports/pdf_vector_metadata_projection_readiness.json --c3-report reports/rag_pdf_embedding_text_contract_audit.json --indexing-report reports/pdf_candidate_indexing_report.json --expected-index-version rag-ingestion-v2-pdf-candidate-v1 --report reports/pdf_candidate_embedding_consistency_report.json`
  - result: `status=PASS`; all C4 mismatch/missing counters `0`.

### Important Decisions

- C4 consumes the C1 scope report directly; full72 gold CSV scope is not unioned unless explicitly requested with `--include-gold-scope`.
- The local Core API on port `8080` still has default candidate namespace `rag-ingestion-v2-candidate`; C4 indexing used a temporary port `8081` process configured for `rag-ingestion-v2-pdf-candidate-v1`.
- C4 success proves candidate indexing consistency only. It does not prove retrieval quality, promotion readiness, or baseline pass.
- The 9 skipped rows remain policy-excluded and visible: document summaries and lower-trust OCR rows without required confidence.

### Remaining Work

- Run C5 PDF-only vector diagnostic separately after C4, still with `promotion_evidence=false`.
- Keep C6/C7 separate from C4; use C5/C6 to classify vector diagnostic and failure causes before any gold policy review.
- Decide in C7 or a dedicated parser/gold policy step whether PDF table gold rows require table-like SearchUnits or can remain paragraph/page-backed.

### Risks

- The default `core-api` configuration still points to `rag-ingestion-v2-candidate`; future C4 reruns need the same explicit candidate namespace configuration or a persistent config change.
- The lower-level worker CLI still needs disciplined scoped use; this C4 path is safe because the wrapper consumed C1 `document_version_ids` and `source_file_ids` with `allowUnscoped=false`.
- C4 did not run retrieval or baseline checks by design, so no ranking-quality conclusion should be drawn from this PASS.

## 2026-05-05 - Track C C4 risk hardening and C5 PDF-only vector diagnostic

### Goal

- Close the remaining C4 contract risks without running global cleanup, global reset, promotion, or baseline.
- Run C5 as PDF-only vector diagnostic evidence against `rag-ingestion-v2-pdf-candidate-v1`.

### Completed

- Hardened lower-level candidate CLI validation so any `candidate` index version, including `rag-ingestion-v2-pdf-candidate-v1`, requires hard identity scope for non-dry-run use unless `--allow-unscoped` is explicit.
- Updated `scripts/rag_scoped_candidate_indexing.py` so `--scope-report` inherits and verifies `indexing_cli_scope.expectedIndexVersion`, can write to an explicit `--artifact-dir`, and can enrich an existing C4 indexing report without re-indexing.
- Enriched `reports/pdf_candidate_indexing_report.json` with Track C common fields, `promotion_evidence=false`, `evidence_role=diagnostic`, resolved artifact dir, and `build.json`/`ingest_manifest.json`/`faiss.index` hashes.
- Updated `scripts/pdf_candidate_embedding_consistency.py` so it requires the C4 indexing report contract fields, proves artifact identity, records producer/consumer reconciliation, and checks outside-scope PDF candidate rows with a separate SQL query.
- Added `scripts/rag_pdf_vector_diagnostic.py` and tests for C5 PDF-only vector diagnostic filtering, diagnostic-only flags, C4 prerequisite validation, and warning classification.
- Regenerated C4 consistency and C5 diagnostic reports after C4 report enrichment.

### Current Evidence

- C4 indexing report:
  - path: `reports/pdf_candidate_indexing_report.json`
  - status: `PASS`
  - sha256: `7f4853897e2a184e06e55025931d6924e7933f46aceb013550100b7caa785a6c`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
  - `allowUnscoped=false`
  - artifact hashes:
    - `build.json`: `9ca90cfe739fb668b5a154420b1cc6c73fcd61a728c0c0b368866799c5d1ee91`
    - `ingest_manifest.json`: `4c055ba195d66e504951d78b295218cdbd9f563c62467149ad1340bb29b4437b`
    - `faiss.index`: `25b03739c2831391a01023f7c49a7420d08073312e26f7665d4e72addc30b480`
- C4 consistency report:
  - path: `reports/pdf_candidate_embedding_consistency_report.json`
  - status: `PASS`
  - sha256: `311569fe45f6c0b834e9a6b8f1ace065fa035ec143cc8a8c05fb930eb173abc1`
  - scoped rows: `8203`
  - candidate rows: `8194`
  - policy-excluded rows: `9`
  - `outside_scope_pdf_candidate_count=0`
  - all C4 index/embedding/chunk mismatch counters: `0`
  - indexing reconciliation: `newly_indexed_count=8193`, `previously_embedded_count=1`, `final_embedded_candidate_count=8194`
- C5 PDF-only vector diagnostic:
  - path: `reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json`
  - status: `PASS_WITH_WARNINGS`
  - sha256: `4c23f777a64045096ffda2afe322c06a04b394076bdc52f05367ce7f38309e38`
  - filtered rows: `22` PDF bound positives
  - bucket counts: `pdf_page_lookup=8`, `pdf_section_question=8`, `pdf_table_lookup=6`
  - `Hit@10=0.8636`, `MRR@10=0.5122`
  - `pdf_citation_location_accuracy=0.3182`
  - `pdf_file_hit@10=0.9545`, `pdf_page_hit@10=0.4091`, `pdf_bbox_overlap@10=0.2353`
  - gate counters: all candidate index / required index version / embedding status / location-type blockers `0`
  - `metadata_projection_failure_count=0`
  - `true_retrieval_ranking_failure_count=14`
  - failure reason counts: `expected_page_not_found=12`, `bbox_mismatch=1`, `expected_file_not_found=1`, `unknown=1`

### Gate/Baseline Status

- Promotion was not run.
- Baseline pass was not attempted.
- C5 is vector retrieval diagnostic only, with `promotion_evidence=false` and `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- C1 scope only: PDF document versions, source file ids, parser versions, and `source_file_type=PDF`.
- Global delete/reset was not run.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_scoped_candidate_indexing.py scripts/pdf_candidate_embedding_consistency.py scripts/rag_pdf_vector_diagnostic.py ai-worker/tests/test_pdf_candidate_embedding_consistency.py ai-worker/tests/test_rag_pdf_vector_diagnostic.py ai-worker/tests/test_search_unit_indexing_loop.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_pdf_candidate_embedding_consistency.py ai-worker/tests/test_rag_pdf_vector_diagnostic.py ai-worker/tests/test_search_unit_indexing_loop.py -q`
  - result: `35 passed, 1 warning`.
- Command:
  - `python scripts/rag_scoped_candidate_indexing.py --scope-report reports/pdf_candidate_scope_report.json --artifact-dir rag-data-pdf-candidate-v1 --enrich-existing-report --output reports/pdf_candidate_indexing_report.json`
  - result: report metadata enriched; no indexing/retrieval/promotion/baseline/cleanup run.
- Command:
  - `python scripts/pdf_candidate_embedding_consistency.py --scope-report reports/pdf_candidate_scope_report.json --c2-report reports/pdf_vector_metadata_projection_readiness.json --c3-report reports/rag_pdf_embedding_text_contract_audit.json --indexing-report reports/pdf_candidate_indexing_report.json --expected-index-version rag-ingestion-v2-pdf-candidate-v1 --report reports/pdf_candidate_embedding_consistency_report.json`
  - result: `status=PASS`; `outside_scope_pdf_candidate_count=0`; all C4 mismatch counters `0`.
- Command:
  - `python scripts/rag_pdf_vector_diagnostic.py --gold eval/gold_queries_v0.csv --expected-location-type pdf --index-version rag-ingestion-v2-pdf-candidate-v1 --artifact-dir rag-data-pdf-candidate-v1 --promotion-evidence false --evidence-role diagnostic --report reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json`
  - result: `status=PASS_WITH_WARNINGS`; gate counters `0`; ranking/location failures remain for C6.

### Important Decisions

- C4 report enrichment is metadata-only and exists to strengthen proof fields after the completed scoped indexing run; it is not an indexing rerun.
- C5 PASS_WITH_WARNINGS means the diagnostic gate is usable for C6 classification, not that promotion or baseline is ready.
- The canary/full-run count mismatch is now represented explicitly as `previously_embedded_count=1`.

### Remaining Work

- Run C6 failure breakdown against the 14 C5 ranking/location failures.
- Classify the `unknown=1` C5 failure before gold policy review.
- Keep C7 gold policy separate from retrieval tuning or promotion.

### Risks

- The default Core API config still points at the legacy candidate namespace, so future live C4 indexing still requires explicit Core API/worker candidate namespace configuration.
- C5 table rows currently have `pdf_table_lookup` page hit `0.0`; C6/C7 must decide whether this is a ranking issue, table extraction issue, or gold policy issue.
- C5 has 14 true retrieval ranking/location failures, so no promotion or baseline conclusion should be drawn from this diagnostic.

## 2026-05-05 - Track C C6 PDF failure breakdown

### Goal

- Classify C5 PDF-only vector diagnostic failures into metadata, ranking, gold/policy, table binding, bbox policy, OCR trust, and chunk granularity buckets.
- Keep C6 read-only over existing reports; do not rerun retrieval, indexing, promotion, baseline, cleanup, or reset.

### Completed

- Added `scripts/rag_pdf_vector_quality_breakdown.py`.
- Added `ai-worker/tests/test_rag_pdf_vector_quality_breakdown.py`.
- Updated `docs/track-c-pdf-embedding-preparation/runbook.md` with the C6 command and targeted test entry.
- Generated `reports/rag_pdf_vector_quality_breakdown.json`.
- Marked C6 `PASS` because `UNKNOWN` failures are `0`, metadata/ranking/gold-policy/chunk groups are separated, and every query has `next_action`.

### Current Evidence

- C6 failure breakdown:
  - path: `reports/rag_pdf_vector_quality_breakdown.json`
  - status: `PASS`
  - sha256: `39036a5d6e0eac013c926e98917eff85ee7a585331da760fd86f44a9849475d5`
  - query count: `22`
  - matched query count: `7`
  - failed query count: `15`
  - `unknown_failure_count=0`
  - `metadata_projection_failure_count=0`
  - `gold_policy_candidate_count=7`
  - `chunk_granularity_candidate_count=1`
  - `true_retrieval_ranking_failure_count=7`
- Failure type counts:
  - `MATCHED=7`
  - `PDF_BBOX_POLICY_MISMATCH=1`
  - `PDF_CHUNK_GRANULARITY_ISSUE=1`
  - `PDF_EXPECTED_FILE_ABSENT_IN_TOP10=1`
  - `PDF_EXPECTED_PAGE_ABSENT_IN_TOP10=6`
  - `PDF_TABLE_GOLD_BINDING_MISMATCH=6`
- C6 completion criteria:
  - `unknown_failure_count_zero=true`
  - `metadata_vs_ranking_separated=true`
  - `gold_policy_candidate_count_recorded=true`
  - `chunk_granularity_candidate_count_recorded=true`
  - `all_queries_have_next_action=true`

### Gate/Baseline Status

- Promotion was not run.
- Baseline pass was not attempted.
- Retrieval was not rerun by C6.
- Indexing was not run by C6.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_pdf_vector_quality_breakdown.py ai-worker/tests/test_rag_pdf_vector_quality_breakdown.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_vector_quality_breakdown.py -q`
  - result: `4 passed`.
- Command:
  - `python scripts/rag_pdf_vector_quality_breakdown.py --eval-report reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json --gold eval/gold_queries_v0.csv --c2-report reports/pdf_vector_metadata_projection_readiness.json --report reports/rag_pdf_vector_quality_breakdown.json`
  - result: `status=PASS`; `UNKNOWN=0`; query-level `next_action` present.
- Command:
  - `python -m pytest ai-worker/tests/test_pdf_candidate_embedding_consistency.py ai-worker/tests/test_rag_pdf_vector_diagnostic.py ai-worker/tests/test_rag_pdf_vector_quality_breakdown.py ai-worker/tests/test_search_unit_indexing_loop.py -q`
  - result: `39 passed, 1 warning`.

### Important Decisions

- `gq_auto_020` was not left as `unknown`; top-k evidence shows expected file/page/physical page was present but expected chunk type was not, so it is classified as `PDF_CHUNK_GRANULARITY_ISSUE`.
- All `pdf_table_lookup` failures are classified as `PDF_TABLE_GOLD_BINDING_MISMATCH` C7 candidates before retrieval tuning, because table bucket file recall is present but expected page binding is consistently absent.
- The single `bbox_mismatch` row is classified as `PDF_BBOX_POLICY_MISMATCH`, not metadata projection failure, because the supporting correct-page hit is page-level and lacks bbox by contract.

### Remaining Work

- Run C7 gold policy review for the 7 gold/policy candidates and 1 chunk granularity candidate.
- Decide whether PDF table gold rows should bind to table-like units, page-level units, or paragraph/bbox evidence.
- Keep the 7 true retrieval ranking failures out of tuning discussion until C7 resolves policy/gold candidates.

### Risks

- C6 classification is deterministic report analysis, not a retrieval-quality improvement.
- Table/page/bbox policy decisions in C7 may change how some C6 rows should be interpreted; if so, add a follow-up C6 reclassification entry instead of editing this evidence.
- No promotion or baseline readiness is implied by C6 `PASS`.

## 2026-05-05 - Track C C7 PDF gold policy review

### Goal

- Confirm before C7 that C6 is usable input: `UNKNOWN=0`, query-level `next_action` exists, and gold/policy candidates are recorded.
- Review PDF page/bbox/table/OCR/chunk gold policy candidates without mutating gold rows or running retrieval/indexing/promotion/baseline.
- Record relabel/reclassification candidates separately from true retrieval ranking failures.

### Completed

- Added `scripts/rag_pdf_gold_policy_review.py`.
- Added `ai-worker/tests/test_rag_pdf_gold_policy_review.py`.
- Updated `docs/track-c-pdf-embedding-preparation/runbook.md` with the C7 command and targeted test entry.
- Generated `reports/rag_pdf_gold_policy_review.json`.
- Marked C7 `PASS_WITH_WARNINGS`: invalid/ambiguous policy counters are `0`, but 8 relabel candidates must be reviewed before retrieval tuning.

### Current Evidence

- C7 gold policy review:
  - path: `reports/rag_pdf_gold_policy_review.json`
  - status: `PASS_WITH_WARNINGS`
  - sha256: `0d31ebf7b5f4e92c17b4fe87ace95160342d009ded2b5d4726a16757f4312a1d`
  - reviewed candidate count: `8`
  - `invalid_gold_count=0`
  - `page_policy_ambiguous_count=0`
  - `table_policy_ambiguous_count=0`
  - `ocr_policy_ambiguous_count=0`
  - `relabel_candidate_count=8`
  - `relabel_candidate_rows_recorded=true`
- Decision category counts:
  - `RELABEL_TABLE_PAGE_BINDING=6`
  - `RELABEL_BBOX_OR_PAGE_FALLBACK=1`
  - `RELABEL_CHUNK_TYPE_POLICY=1`
- C7 policy category counts:
  - `relabel_candidate=8`
- Post-C7 decision:
  - `metadata_projection_blocker_count=0`
  - `text_contract_blocker_count=0`
  - `indexing_consistency_blocker_count=0`
  - `gold_policy_blocker_count=0`
  - `true_retrieval_ranking_failure_count=7`
  - `post_c7_reclassification_required=true`
  - `retrieval_tuning_candidate_ready=false`

### Gate/Baseline Status

- Promotion was not run.
- Baseline pass was not attempted.
- Retrieval was not run by C7.
- Indexing was not run by C7.
- Gold CSV mutation was not run by C7.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_pdf_gold_policy_review.py ai-worker/tests/test_rag_pdf_gold_policy_review.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_gold_policy_review.py -q`
  - result: `4 passed`.
- Command:
  - `python scripts/rag_pdf_gold_policy_review.py --quality-breakdown reports/rag_pdf_vector_quality_breakdown.json --gold eval/gold_queries_v0.csv --c1-report reports/pdf_candidate_scope_report.json --c2-report reports/pdf_vector_metadata_projection_readiness.json --c3-report reports/rag_pdf_embedding_text_contract_audit.json --report reports/rag_pdf_gold_policy_review.json`
  - result: `status=PASS_WITH_WARNINGS`; invalid/ambiguous counters `0`; relabel candidates `8`.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_gold_policy_review.py ai-worker/tests/test_rag_pdf_vector_quality_breakdown.py ai-worker/tests/test_rag_pdf_vector_diagnostic.py ai-worker/tests/test_pdf_candidate_embedding_consistency.py ai-worker/tests/test_search_unit_indexing_loop.py -q`
  - result: `43 passed, 1 warning`.

### Important Decisions

- `PDF_TABLE_GOLD_BINDING_MISMATCH` rows are not treated as retrieval failures yet; all 6 are relabel candidates for table/page binding policy.
- `PDF_BBOX_POLICY_MISMATCH` is a relabel candidate because the supporting correct-page hit is page-level and bbox is optional for page summaries, while the gold row expects paragraph bbox.
- `PDF_CHUNK_GRANULARITY_ISSUE` is a relabel candidate because same-page paragraph evidence conflicts with page-level expected chunk policy.
- Raw C6 `failure_reason_counts.unknown=1` is not a C7 blocker because C6 reclassified it to `PDF_CHUNK_GRANULARITY_ISSUE`; downstream should use C6/C7 policy categories rather than raw C5 failure reasons.

### Remaining Work

- Review the 8 relabel candidates and decide whether to update gold labels, matching policy, or exclude specific rows from metric use.
- If any relabel/policy decision is accepted, rerun C6 and add a follow-up C6 reclassification entry.
- Do not start retrieval tuning until relabel candidates are resolved or explicitly deferred.

### Risks

- C7 is a policy review report, not a gold mutation or quality improvement.
- `retrieval_tuning_candidate_ready=false` because relabel candidates remain.
- C2/C3 remain `PASS_WITH_WARNINGS`; their warnings stay visible even though C7 found no metadata/gold-policy blockers.

## 2026-05-05 - Track C C7.1 policy overlay and reviewed PDF diagnostic

### Goal

- Resolve the 8 C7 relabel candidates with an explicit policy overlay.
- Generate a separate reviewed PDF manifest without mutating `eval/gold_queries_v0.csv`.
- Reclassify C6 under the reviewed policy and create a C8 case pack for the remaining 7 non-table failures.
- Keep promotion, baseline updates, broad retrieval tuning, parser expansion, reindexing, and PDF candidate artifact regeneration out of scope.

### Completed

- Added `scripts/rag_pdf_policy_common.py`.
- Added `scripts/rag_pdf_gold_policy_decision_overlay.py`.
- Added `scripts/rag_pdf_vector_quality_breakdown_after_policy.py`.
- Added `scripts/rag_pdf_reviewed_vector_diagnostic.py`.
- Added `scripts/rag_pdf_retrieval_tuning_case_pack.py`.
- Added targeted tests for the four new Track C follow-up scripts.
- Generated `reports/rag_pdf_gold_policy_decision_overlay.json`.
- Generated `eval/gold_queries_pdf_v1_reviewed.csv`.
- Generated `reports/rag_pdf_v1_reviewed_manifest_report.json`.
- Generated `reports/rag_pdf_vector_quality_breakdown_after_policy.json`.
- Generated `reports/rag_retrieval_eval_pdf_v1_reviewed_vector_diagnostic_report.json`.
- Generated `reports/rag_pdf_retrieval_tuning_case_pack.json`.

### Current Evidence

- C7.1 policy overlay:
  - path: `reports/rag_pdf_gold_policy_decision_overlay.json`
  - status: `PASS_WITH_WARNINGS`
  - sha256: `f06c5c19d10951db5462edf5930d577f2f4eadee50c61a61d526fa00cf738982`
  - relabel candidates: `8`
  - resolved candidates: `8`
  - unresolved candidates: `0`
  - decisions: `DEFER_TO_TABLE_EXTRACTION=6`, `ACCEPT_PAGE_WITH_OPTIONAL_BBOX=1`, `ACCEPT_CHUNK_TYPE_POLICY_RELABEL=1`
  - `table_specific_retrieval_proven=false`
- Reviewed PDF manifest:
  - path: `eval/gold_queries_pdf_v1_reviewed.csv`
  - sha256: `442b116e6c0141e05ee6114b7732951ffd578d6fac10aa255ca0b3f1b4814c03`
  - report: `reports/rag_pdf_v1_reviewed_manifest_report.json`
  - report sha256: `e6795d768b9448431b789909c53f87bdd2127d78f1e8f28f1853e9391edcfb03`
  - `total_pdf_rows=22`
  - `table_deferred_count=6`
  - `reviewed_positive_metric_eligible_count=16`
- C6.1 policy-applied breakdown:
  - path: `reports/rag_pdf_vector_quality_breakdown_after_policy.json`
  - status: `PASS`
  - sha256: `74fffc37c4349f3f58309522756be507e81cb5cb5cf0bed69b957ea491ce68e8`
  - `raw_query_count=22`
  - `policy_resolved_count=8`
  - `policy_unresolved_count=0`
  - `table_deferred_count=6`
  - `true_retrieval_ranking_failure_count=7`
  - `retrieval_tuning_candidate_ready_for_reviewed_non_table_set=true`
  - `retrieval_tuning_candidate_ready_for_all_pdf=false`
- C5.1 reviewed PDF vector diagnostic:
  - path: `reports/rag_retrieval_eval_pdf_v1_reviewed_vector_diagnostic_report.json`
  - status: `PASS_WITH_WARNINGS`
  - sha256: `c8424c4acd0e16d7f03b40789b673ae1351578393981a4bd21a0cae3a59f46b8`
  - `reviewed_query_count=22`
  - `reviewed_positive_metric_denominator=16`
  - `deferred_table_count=6`
  - `Hit@1=0.1875`
  - `Hit@3=0.3125`
  - `Hit@5=0.4375`
  - `Hit@10=0.5625`
  - `MRR@10=0.2766`
  - `pdf_file_hit@10=0.9375`
  - `pdf_page_hit@10=0.5625`
  - `pdf_bbox_overlap@10=0.3636`
  - `pdf_policy_adjusted_location_accuracy=0.5625`
  - `pdf_exact_bbox_location_accuracy=0.3636`
  - `table_specific_success_count=0`
  - `metadata_projection_failure_count=0`
  - `true_retrieval_ranking_failure_count=7`
- C8 case pack:
  - path: `reports/rag_pdf_retrieval_tuning_case_pack.json`
  - status: `PASS`
  - sha256: `2c45059affe749fc5b2565d6f693c8eee7054a865b91642093e06257266b8dd7`
  - `case_count=7`
  - `next_action_counts.FILE_RECALL_INVESTIGATION=1`
  - `next_action_counts.PAGE_RANKING_INVESTIGATION=6`
  - `retrieval_tuning_executed=false`

### Gate/Baseline Status

- Promotion was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.
- Gold v0 mutated: `false`.
- Retrieval tuning executed: `false`.
- Reindexing executed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_pdf_gold_policy_decision_overlay.py scripts/rag_pdf_vector_quality_breakdown_after_policy.py scripts/rag_pdf_reviewed_vector_diagnostic.py scripts/rag_pdf_retrieval_tuning_case_pack.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_gold_policy_decision_overlay.py -q`
  - result: `3 passed`.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_vector_quality_breakdown_after_policy.py -q`
  - result: `3 passed`.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_reviewed_vector_diagnostic.py -q`
  - result: `4 passed`.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_retrieval_tuning_case_pack.py -q`
  - result: `3 passed`.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_gold_policy_review.py ai-worker/tests/test_rag_pdf_vector_quality_breakdown.py ai-worker/tests/test_rag_pdf_vector_diagnostic.py ai-worker/tests/test_pdf_candidate_embedding_consistency.py ai-worker/tests/test_search_unit_indexing_loop.py -q`
  - result: `43 passed, 1 warning`.
- Command:
  - `python scripts/rag_pdf_gold_policy_decision_overlay.py`
  - result: `status=PASS_WITH_WARNINGS`; decisions `6/1/1`; reviewed manifest `22` rows with `16` eligible and `6` table-deferred.
- Command:
  - `python scripts/rag_pdf_vector_quality_breakdown_after_policy.py`
  - result: `status=PASS`; true retrieval/ranking failures remain `7`.
- Command:
  - `python scripts/rag_pdf_reviewed_vector_diagnostic.py`
  - result: `status=PASS_WITH_WARNINGS`; reviewed denominator `16`; table-deferred `6`; true failures `7`.
- Command:
  - `python scripts/rag_pdf_retrieval_tuning_case_pack.py`
  - result: `status=PASS`; case count `7`.
- Command:
  - `git diff --check`
  - result: passed; emitted CRLF normalization warnings only.

### Important Decisions

- The 6 `RELABEL_TABLE_PAGE_BINDING` rows are `DEFER_TO_TABLE_EXTRACTION`, preserved as `table_deferred`, and excluded from reviewed positive metrics.
- The single bbox/page fallback row is accepted only under `PAGE_WITH_OPTIONAL_BBOX`; it counts as page policy success but not exact bbox success.
- The single chunk-type row is accepted under `PAGE_OR_PARAGRAPH_SAME_PAGE`; it counts as same-page paragraph policy success, not table or bbox success.
- The C5.1 reviewed diagnostic recomputes reviewed metrics from existing C5 query-level top-k evidence; it does not run a live DB/vector search.
- C8 is a case pack only. It records next actions for the 7 remaining failures and does not tune retrieval.

### Remaining Work

- Investigate the 7 C8 cases individually.
- Start with the 1 `FILE_RECALL_INVESTIGATION` case and 6 `PAGE_RANKING_INVESTIGATION` cases.
- Keep broad tuning, promotion, baseline updates, and reindexing blocked until case-level evidence identifies a narrow next change.

### Risks

- Table-specific retrieval is still not proven because current PDF table rows have no table-like SearchUnits.
- Reviewed C5.1 is a policy-adjusted diagnostic recomputation from preserved C5 top-k evidence, not a fresh live vector search.
- The reviewed non-table set is ready for case-level investigation, but all-PDF readiness remains false while table rows are deferred.

## 2026-05-05 - Track C C8.1 case-level investigation

### Goal

- Investigate the 7 reviewed non-table C8 failures before any retrieval tuning.
- Use read-only DB/SearchUnit surface evidence when available.
- Keep the work diagnostic-only and do not mutate gold, baselines, indexes, or candidate artifacts.

### Completed

- Added `scripts/rag_pdf_c8_case_investigation.py`.
- Added `ai-worker/tests/test_rag_pdf_c8_case_investigation.py`.
- Generated `reports/rag_pdf_c8_case_investigation_report.json`.

### Current Evidence

- C8.1 case-level investigation:
  - path: `reports/rag_pdf_c8_case_investigation_report.json`
  - status: `PASS`
  - sha256: `f6919bd71e03df66e62388c9db93d061e129d0df929f2bd877c395711cb41b83`
  - `case_count=7`
  - `db_inspection_used=true`
  - root causes:
    - `SHORT_OR_GENERIC_QUERY_SURFACE_TOO_WEAK=5`
    - `CROSS_DOCUMENT_REPEATED_TABLE_LABEL_FILE_RECALL=1`
    - `EXPECTED_PAGE_PRESENT_BUT_DENSE_RANKING_MISS=1`
  - refined next actions:
    - `QUERY_SURFACE_REVIEW=5`
    - `FILE_RECALL_INVESTIGATION=1`
    - `EMBEDDING_SURFACE_REVIEW=1`
  - `broad_tuning_recommended=false`
  - `table_specific_retrieval_proven=false`
  - all 7 expected pages have indexed SearchUnits and matching `embedding_record` / `ragmeta.chunks` rows.
  - 6 rows with expected bbox have exact bbox evidence on the expected page; `gq_auto_025` has no expected bbox in the reviewed manifest.

### Gate/Baseline Status

- Promotion was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.
- Gold v0 mutated: `false`.
- Retrieval tuning executed: `false`.
- Reindexing executed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_pdf_c8_case_investigation.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_c8_case_investigation.py -q`
  - result: `3 passed`.
- Command:
  - `python scripts/rag_pdf_c8_case_investigation.py`
  - result: `status=PASS`; root causes `5/1/1`; refined next actions `5/1/1`.

### Important Decisions

- The next work should not be broad retrieval tuning.
- Five cases are better treated first as query-surface review because the queries are short or generic: `목 차`, `기간중`, `달러`.
- One case remains file-recall investigation: `gq_pdf_section_question_002`.
- One case should be embedding-surface review before any tuning: `gq_pdf_section_question_003`.

### Remaining Work

- Manually review the 5 short/generic query surfaces and decide whether they should be rewritten, excluded, or kept as stress cases.
- Inspect the 1 file-recall case for cross-document date/file disambiguation.
- Inspect the 1 embedding-surface case for numeric/table surface weakness before proposing a narrow retrieval change.

### Risks

- The C8.1 report reads local DB SearchUnit surfaces; if the DB changes, rerun the script and update the report hash.
- C8.1 still does not prove table-specific retrieval.
- No case-level finding is sufficient by itself to justify broad tuning.

## 2026-05-05 - Track C C8.2 rank probe

### Goal

- Probe the 7 C8 reviewed non-table failures at top-100 depth without tuning, promotion, reindexing, or gold mutation.
- Separate file/document recall, strict page recall, bbox recall, page aggregation simulation, and lexical evidence.
- Keep C8.2 as diagnostic-only evidence for case-level investigation.

### Completed

- Added `scripts/rag_pdf_c8_rank_probe.py`.
- Added `ai-worker/tests/test_rag_pdf_c8_rank_probe.py`.
- Generated `reports/rag_pdf_c8_rank_probe_report.json`.

### Current Evidence

- C8.2 rank probe:
  - path: `reports/rag_pdf_c8_rank_probe_report.json`
  - status: `PASS`
  - sha256: `88a4c53cbe187f9fb6459d03d7a2d5a34b3c1f2816e63f7bff6f6e287de7fb47`
  - `case_count=7`
  - `top_k=100`
  - `db_candidate_unit_count=8194`
  - `wrong_index_version_hit_count=0`
  - `non_embedded_hit_count=0`
  - expected file/docv found in top-100: `7/7`
  - strict expected page found in top-100: `6/7`
  - strict expected page found in top-10: `0/7`
  - exact bbox found in top-100: `5/7`
  - page aggregation simulation top-10 success: `0/7`
  - refined next actions:
    - `QUERY_SURFACE_REVIEW=5`
    - `FILE_DISAMBIGUATION_REVIEW=1`
    - `LEXICAL_EXACT_PHRASE_PROBE_REVIEW=1`

### Rank Findings

- `gq_pdf_page_lookup_003`: expected page rank `63`; exact bbox rank `63`; next action `QUERY_SURFACE_REVIEW`.
- `gq_pdf_section_question_002`: expected file/docv/page first rank `13`, exact bbox rank `49`; next action `FILE_DISAMBIGUATION_REVIEW`.
- `gq_pdf_section_question_003`: expected file/docv first rank `1`, but strict expected page absent in top-100; expected page exact phrase exists in corpus; next action `LEXICAL_EXACT_PHRASE_PROBE_REVIEW`.
- `gq_auto_009`: expected page/exact bbox rank `20`; next action `QUERY_SURFACE_REVIEW`.
- `gq_auto_014`: expected page/exact bbox rank `31`; corpus exact phrase unit count `221`; next action `QUERY_SURFACE_REVIEW`.
- `gq_auto_019`: expected page/exact bbox rank `17`; next action `QUERY_SURFACE_REVIEW`.
- `gq_auto_025`: expected page rank `29`; no expected bbox in reviewed manifest; next action `QUERY_SURFACE_REVIEW`.

### Gate/Baseline Status

- Promotion was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.
- Gold v0 mutated: `false`.
- Retrieval tuning executed: `false`.
- Reindexing executed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_pdf_c8_rank_probe.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_c8_rank_probe.py -q`
  - result: `5 passed`.
- Command:
  - `python scripts/rag_pdf_c8_rank_probe.py`
  - result: `status=PASS`; `case_count=7`; strict expected page top-100 `6/7`; strict expected page top-10 `0/7`; gate counters `0/0`.

### Important Decisions

- C8.2 does not justify broad retrieval tuning.
- File/doc recall is not the dominant blocker for the 7 reviewed non-table cases because all 7 expected files/docvs appear in top-100.
- The remaining work is case-level: 5 query-surface reviews, 1 file disambiguation review, and 1 lexical/exact-phrase probe review.
- Page aggregation remains only a simulation and did not place any expected page group into top-10.

### Remaining Work

- Manually review the 5 short/generic query surfaces before proposing any query rewrite or label decision.
- Investigate `gq_pdf_section_question_002` as a cross-document/file disambiguation case.
- Investigate `gq_pdf_section_question_003` for why exact lexical evidence exists but the expected page is absent from top-100.

### Risks

- C8.2 uses the local DB and existing `rag-data-pdf-candidate-v1` artifact; rerun it if either changes.
- Table-specific retrieval is still not proven and table-deferred rows remain outside this reviewed positive denominator.
- C8.2 is not promotion evidence and does not update a baseline.

## 2026-05-05 - Track C C8.3 case-level review

### Goal

- Review the 7 C8 reviewed non-table failures case-by-case before any retrieval tuning.
- Separate the remaining cases into query-surface, file-disambiguation, and lexical/exact-phrase review groups.
- Produce a diagnostic-only case decision report with row-level evidence and proposed next steps.

### Completed

- Added `scripts/rag_pdf_c8_case_level_review.py`.
- Added `ai-worker/tests/test_rag_pdf_c8_case_level_review.py`.
- Generated `reports/rag_pdf_c8_case_level_review_report.json`.

### Current Evidence

- C8.3 case-level review:
  - path: `reports/rag_pdf_c8_case_level_review_report.json`
  - status: `PASS_WITH_WARNINGS`
  - sha256: `4eec88d6fc734b9c4d80ac7890c7231832eb652b2a58aa70448dd1545c2bc5c3`
  - `case_count=7`
  - decision counts:
    - `REWRITE_QUERY_SURFACE=5`
    - `REQUIRE_FILE_DISAMBIGUATION_POLICY=1`
    - `REQUIRE_EMBEDDING_SURFACE_REVIEW=1`
  - next action counts:
    - `QUERY_SURFACE_REVIEW=5`
    - `FILE_DISAMBIGUATION_REVIEW=1`
    - `LEXICAL_EXACT_PHRASE_PROBE_REVIEW=1`
  - proposed query rewrites: `5`
  - query surface audit:
    - rewritten surfaces changed from original: `5`
    - filename leaks: `0`
    - document version leaks: `0`
    - `.pdf` extension leaks: `0`
    - Latin letter leaks: `0`
    - Korean surfaces: `5`
  - gold binding review required: `0`
  - expected page review required: `1`
  - file disambiguation policy required: `1`
  - embedding surface review required: `1`

### Case Decisions

- `gq_pdf_page_lookup_003`: `REWRITE_QUERY_SURFACE`; expected page rank `63`, exact bbox rank `63`, page group rank `45`, exact phrase units `12`, competing exact phrase pages `5`.
- `gq_pdf_section_question_002`: `REQUIRE_FILE_DISAMBIGUATION_POLICY`; expected file/docv/page rank `13`, exact bbox rank `49`, exact phrase units `26`, competing exact phrase pages `12`.
- `gq_pdf_section_question_003`: `REQUIRE_EMBEDDING_SURFACE_REVIEW` with `REQUIRE_EXPECTED_PAGE_REVIEW`; expected file/docv rank `1`, strict expected page absent in top-100, exact phrase units `2`, competing exact phrase pages `0`.
- `gq_auto_009`: `REWRITE_QUERY_SURFACE`; expected page/exact bbox rank `20`, page group rank `14`, exact phrase units `24`, competing exact phrase pages `8`.
- `gq_auto_014`: `REWRITE_QUERY_SURFACE`; expected page/exact bbox rank `31`, page group rank `21`, exact phrase units `221`, competing exact phrase pages `63`.
- `gq_auto_019`: `REWRITE_QUERY_SURFACE`; expected page/exact bbox rank `17`, page group rank `11`, exact phrase units `24`, competing exact phrase pages `8`.
- `gq_auto_025`: `REWRITE_QUERY_SURFACE`; expected page rank `29`, exact bbox rank `null`, page group rank `23`, exact phrase units `12`, competing exact phrase pages `5`.

### Gate/Baseline Status

- Promotion was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.
- Gold v0 mutated: `false`.
- Retrieval tuning executed: `false`.
- Reindexing executed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_pdf_c8_case_level_review.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_c8_case_level_review.py -q`
  - result: `3 passed`.
- Command:
  - `python scripts/rag_pdf_c8_case_level_review.py`
  - result: `status=PASS_WITH_WARNINGS`; `case_count=7`; decision counts `5/1/1`; proposed query rewrites `5`.

### Important Decisions

- C8.3 does not justify broad retrieval tuning.
- The 5 query-surface cases should be handled through query/label-surface rewrite or explicitly kept as stress cases.
- `gq_pdf_section_question_002` needs file/date disambiguation policy before any retrieval experiment.
- `gq_pdf_section_question_003` needs expected-page and embedding-surface review before any retrieval experiment.
- Page aggregation remains only a simulation and table-specific retrieval is still not proven.

### Remaining Work

- Apply C8.3 decisions to reviewed labels/query surfaces/page/file policy in a separate case decision pass.
- Keep broad tuning, hybrid search, reranker work, parser expansion, reindexing, promotion, and baseline updates blocked until the case decisions are resolved.

## 2026-05-05 - Track C C8.3 reinforcement and C8.4 case decision overlay

### Goal

- Reinforce C8.3 with query-surface audit and reviewed-manifest policy traceability.
- Add the next report-only pass for applying C8.3 decisions as overlay evidence without mutating any CSV manifest.
- Keep C8.4 as manual decision support, not retrieval tuning or promotion evidence.

### Completed

- Reinforced `scripts/rag_pdf_c8_case_level_review.py` with query-surface audit counts and source reviewed-policy fields.
- Added `scripts/rag_pdf_c8_case_decision_overlay.py`.
- Added `ai-worker/tests/test_rag_pdf_c8_case_decision_overlay.py`.
- Regenerated `reports/rag_pdf_c8_case_level_review_report.json`.
- Generated `reports/rag_pdf_c8_case_decision_overlay.json`.

### Current Evidence

- C8.3 reinforced case-level review:
  - path: `reports/rag_pdf_c8_case_level_review_report.json`
  - status: `PASS_WITH_WARNINGS`
  - sha256: `4eec88d6fc734b9c4d80ac7890c7231832eb652b2a58aa70448dd1545c2bc5c3`
  - query surface audit counts:
    - `rewrite_count=5`
    - `changed_from_original_count=5`
    - `filename_leak_count=0`
    - `document_version_leak_count=0`
    - `pdf_extension_leak_count=0`
    - `latin_letter_count=0`
    - `korean_surface_count=5`
- C8.4 case decision overlay:
  - path: `reports/rag_pdf_c8_case_decision_overlay.json`
  - status: `PASS_WITH_WARNINGS`
  - sha256: `cb231fde587f2406a378cdcbb11b7d8102e84ede17289600646b60077cc482e2`
  - `case_count=7`
  - source decision counts:
    - `REWRITE_QUERY_SURFACE=5`
    - `REQUIRE_FILE_DISAMBIGUATION_POLICY=1`
    - `REQUIRE_EMBEDDING_SURFACE_REVIEW=1`
  - manifest action counts:
    - `QUERY_SURFACE_REWRITE_OVERLAY=5`
    - `MARK_CASE_REVIEW_PENDING=2`
  - reviewed manifest denominator:
    - `total_pdf_rows=22`
    - `positive_metric_eligible_count=16`
    - `table_deferred_count=6`
    - `excluded_count=0`
  - query surface leakage:
    - checked: `5`
    - leaks: `0`
  - `candidate_manifest_written=false`
  - `gold_v0_mutated=false`
  - `reviewed_manifest_mutated=false`

### Gate/Baseline Status

- Promotion was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.
- Gold v0 mutated: `false`.
- Reviewed manifest mutated: `false`.
- Candidate manifest written: `false`.
- Retrieval tuning executed: `false`.
- Reindexing executed: `false`.

### Verification

- Command:
  - `python -m py_compile scripts/rag_pdf_c8_case_level_review.py scripts/rag_pdf_c8_case_decision_overlay.py`
  - result: passed.
- Command:
  - `python -m pytest ai-worker/tests/test_rag_pdf_c8_case_level_review.py ai-worker/tests/test_rag_pdf_c8_case_decision_overlay.py -q`
  - result: `7 passed`.
- Command:
  - `python scripts/rag_pdf_c8_case_level_review.py`
  - result: `status=PASS_WITH_WARNINGS`; blockers empty.
- Command:
  - `python scripts/rag_pdf_c8_case_decision_overlay.py`
  - result: `status=PASS_WITH_WARNINGS`; blockers empty; no candidate CSV written.

### Important Decisions

- C8.4 is report-only. It records proposed query rewrites and pending case-review decisions but does not write a manifest.
- The 5 query-surface rewrites are overlay proposals only and do not leak expected file names, document version ids, PDF extensions, or Latin filename/title tokens.
- The 2 unresolved rows are overlay-marked as case-review pending:
  - `gq_pdf_section_question_002`: file disambiguation policy required.
  - `gq_pdf_section_question_003`: expected-page and embedding-surface review required.
- Broad retrieval tuning remains blocked.

### Remaining Work

- Manually accept, revise, or reject the 5 query rewrite overlay proposals.
- Resolve the 2 case-review pending rows before creating any reviewed manifest patch or rerunning diagnostics.
- Do not run promotion, broad retrieval tuning, hybrid search, reranker work, parser expansion, reindexing, or baseline update.

## 2026-05-05 - Track C C8.4 cleanup pass

### Completed

- Removed stale C8.4 wording that referred to a case-decision candidate manifest.
- Regenerated `reports/rag_pdf_c8_case_decision_overlay.json` as a report-only overlay.
- Removed regenerated local cache/temp files only:
  - `scripts/__pycache__/`
  - `ai-worker/tests/__pycache__/`
  - `.pytest_cache/`
  - `.ruff_cache/`
  - `.tmp/core-api-b2.stderr.log`
  - `.tmp/core-api-b2.stdout.log`
- Preserved Track C diagnostic scripts, tests, reports, reviewed manifest, and `rag-data-pdf-candidate-v1/`.

### Current Evidence

- C8.4 case decision overlay:
  - path: `reports/rag_pdf_c8_case_decision_overlay.json`
  - status: `PASS_WITH_WARNINGS`
  - sha256: `6a914cc1c8f2b0e8eee952819fba1d1e7abe2aef8ba949fcfd4150e2f62b54fa`
  - `candidate_manifest_written=false`
  - `gold_v0_mutated=false`
  - `reviewed_manifest_mutated=false`
  - `retrieval_tuning_executed=false`

### Gate/Baseline Status

- Promotion was not run.
- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- PDF candidate namespace: `rag-ingestion-v2-pdf-candidate-v1`.
- PDF artifact dir: `rag-data-pdf-candidate-v1`.
- Immutable baseline changed: `false`.
- XLSX candidate artifact changed: `false`.
- Gold v0 mutated: `false`.
- Reviewed manifest mutated: `false`.
- Candidate manifest written: `false`.
- Retrieval tuning executed: `false`.
- Reindexing executed: `false`.
