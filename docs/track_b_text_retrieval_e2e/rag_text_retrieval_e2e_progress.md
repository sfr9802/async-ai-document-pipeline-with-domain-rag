# Track B — TEXT Retrieval E2E Progress Log

This document tracks phase-level execution progress for Track B TEXT retrieval E2E diagnostics.
It follows the style of `docs/rag-ingestion-progress.md`, but stays local to this Track B directory until the work is complete and ready to merge back into the main progress log.

## Merge Note

This is a temporary phase-local progress log.
After Track B phases are completed or intentionally paused, merge the durable entries into `docs/rag-ingestion-progress.md` and keep this file as either an archive or remove it during the docs consolidation pass.

## Phase Status Board

| Phase | Status | Current Evidence | Next Action |
|---|---|---|---|
| B-app B0 backend identity | `diagnostic_completed / smoke_only` | `reports/rag_text_backend_identity_report.json` has `b1_entry_allowed=true`, `blockers=[]`, READY TEXT `text_count=15`, and clean TEXT-filtered API probe | Preserve as app-catalog smoke identity |
| B-app B1 gold v0 | `diagnostic_completed / smoke_only` | `ai-worker/eval/eval_queries/gold_queries_text_e2e_v0.csv` has 12 rows; `reports/rag_text_e2e_gold_validate_report.json` passed with live READY TEXT bindings | Do not use as Track B representative corpus |
| B2-app retrieval diagnostic | `diagnostic_completed / smoke_only` | `reports/rag_text_retrieval_diagnostic_report.json` exists; Hit@10=0.0, MRR@10=0.0, result_empty_count=12, path_mixing_count=0 | Cite with `reports/rag_text_b2_scope_correction_report.json` |
| R0 B2 scope correction | `diagnostic_completed` | `reports/rag_text_b2_scope_correction_report.json`; `phases/phase_progress.md` | Start R1 query routing matrix |
| R1 query routing matrix | `needs_review` | `ai-worker/eval/eval_queries/query_intent_routing_matrix_v0.csv`, `reports/rag_query_intent_routing_matrix_report.json` | Future namu gold is present, but current routing matrix still excludes future inputs from observed lane coverage |
| R2 namu-v4 corpus inventory | `diagnostic_completed` | `reports/rag_text_namu_v4_corpus_inventory_report.json` schema v2 hardened PASS with split-count check | Use `rag_chunks.jsonl` + `chunk_text`; keep auxiliary/split/raw-context checks as R3-R8 gate |
| R3 namu-v4 gold binding | `diagnostic_completed` | `ai-worker/eval/eval_queries/gold_queries_text_namu_v4_v0.csv`, `reports/rag_text_namu_v4_gold_build_report.json`, `reports/rag_text_namu_v4_gold_validate_report.json`; validator current-seed policy PASSED | Keep as R5 entry gate |
| R4 retrieval emit inventory | `diagnostic_completed` | `reports/rag_text_namu_v4_retrieval_emit_inventory_report.json` says `NO_REUSABLE_EXISTING_EMIT` | Do not reuse old emits; R5 needs fresh diagnostic retrieval |
| B2-namu retrieval diagnostic | `ready_for_fresh_diagnostic` | R4 decision `RUN_FRESH_DIAGNOSTIC_RETRIEVAL`, `retrieval_metrics_computed=false` | Generate true TEXT retrieval metrics against namu-v4 with a fresh emit |
| B3-namu context assembly | `blocked_on_B2_namu` | `phases/phase_r6_b3_namu_context_assembly.md` | Assemble raw `chunk_text` contexts |
| B4-namu LLM answer eval | `blocked_on_B3_namu` | `phases/phase_r7_b4_namu_answer_eval.md` | Run deterministic checks and optional judge after context report exists |
| B5-namu citation support | `blocked_on_B4_namu` | `phases/phase_r8_b5_namu_citation_support.md` | Validate claim-level support after answer report exists |
| R9 lane readiness | `planned` | `phases/phase_r9_file_content_lane_readiness.md` | Generate FILE vs CONTENT readiness report |
| B6 summary/regression | `blocked_on_B5_namu` | `phase_b6_summary_regression.md` retained as follow-up | Summarize Track B after B5-namu |

## Status Vocabulary

Use these labels consistently.

| Status | Meaning |
|---|---|
| `planned` | Plan exists, implementation or evidence gathering has not started |
| `in_progress` | Current active phase |
| `blocked_on_Bx` | Waiting for a prior phase artifact |
| `blocked_on_Rx` | Waiting for a replan phase artifact |
| `smoke_only` | Valid diagnostic smoke evidence, not representative Track B performance |
| `diagnostic_completed` | Phase generated diagnostic artifacts but not promotion evidence |
| `ready_for_fresh_diagnostic` | Prior inventory is complete, but the next phase must generate fresh diagnostic output |
| `needs_review` | Output exists but label/report quality needs manual review |
| `paused` | Intentionally stopped with remaining work recorded |
| `merged_to_main_progress` | Durable entry has been copied into `docs/rag-ingestion-progress.md` |

## Evidence Rules

- Keep `promotion_evidence=false` and `evidence_role=diagnostic` in every Track B report.
- Do not call a phase complete unless the output artifact exists or the blocker is explicitly recorded.
- Keep confirmed facts, hypotheses, and open risks separate.
- Record verification commands and results exactly enough to rerun.
- If a backend is fixture-only, stale, mixed with PDF/XLSX, or empty, record it as diagnostic/smoke only.
- Do not merge this progress log into promotion gate notes.

## Entry Template

Copy this template for each work turn.

```markdown
## YYYY-MM-DD - short title

### Goal

- ...

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B0 backend identity | `planned` | `in_progress` | ... |

### Completed

- ...

### Current Evidence

- ...

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

### Next Recommended Step

- ...
```

## 2026-05-05 - Track B phase documentation initialized

### Goal

- Split the original Track B TEXT retrieval E2E plan into phase-level documents.
- Add a local progress log that can collect phase execution history before later consolidation into `docs/rag-ingestion-progress.md`.
- Keep this work documentation-only.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B0 backend identity | none | `planned` | `phase_b0_backend_identity.md` created |
| B1 gold v0 | none | `blocked_on_B0` | `phase_b1_gold_v0.md` created |
| B2 retrieval diagnostic | none | `blocked_on_B1` | `phase_b2_retrieval_diagnostic.md` created |
| B3 context assembly | none | `blocked_on_B2` | `phase_b3_context_assembly.md` created |
| B4 LLM answer eval | none | `blocked_on_B3` | `phase_b4_llm_answer_eval.md` created |
| B5 citation support | none | `blocked_on_B4` | `phase_b5_citation_support.md` created |
| B6 summary/regression | none | `blocked_on_B5` | `phase_b6_summary_regression.md` created |
| B7 scale/stabilize | none | `blocked_on_B6` | `phase_b7_scale_and_stabilize.md` created |

### Completed

- Added Track B phase directory:
  - `docs/track_b_text_retrieval_e2e/`
- Added phase index:
  - `docs/track_b_text_retrieval_e2e/README.md`
- Added phase plans:
  - `phase_b0_backend_identity.md`
  - `phase_b1_gold_v0.md`
  - `phase_b2_retrieval_diagnostic.md`
  - `phase_b3_context_assembly.md`
  - `phase_b4_llm_answer_eval.md`
  - `phase_b5_citation_support.md`
  - `phase_b6_summary_regression.md`
  - `phase_b7_scale_and_stabilize.md`
- Added this local progress log:
  - `rag_text_retrieval_e2e_progress.md`
- Added a pointer from the original Track B plan to the new phase index.

### Current Evidence

- Track B remains diagnostic-only.
- No retrieval eval, indexing, LLM run, or promotion gate run was performed in this documentation slice.
- B0 is the first executable phase because TEXT backend identity must be fixed before gold, retrieval, or answer metrics are interpretable.

### Verification

- Directory listing:
  - `Get-ChildItem -LiteralPath docs\track_b_text_retrieval_e2e`
  - result: phase documents and README exist.
- README link check:
  - result: phase links resolved.
- Whitespace check:
  - `rg -n "[ \t]+$" docs/track_b_text_retrieval_e2e docs/track_b_text_retrieval_e2e_plan.md`
  - result: no trailing whitespace matches.

### Important Decisions

- Keep `docs/track_b_text_retrieval_e2e_plan.md` as the detailed source plan.
- Use this directory-local progress log for Track B execution history until docs consolidation.
- Do not mix Track B TEXT E2E diagnostics with XLSX/PDF promotion evidence.

### Remaining Work

- Execute B0 by inspecting the actual TEXT backend and writing `reports/rag_text_backend_identity_report.json`.
- Update the Phase Status Board after each phase artifact is created or blocked.
- Merge durable progress entries into `docs/rag-ingestion-progress.md` after Track B reaches a stable checkpoint.

### Risks

- If TEXT backend identity is unclear, downstream answer metrics can become misleading.
- If PDF/XLSX hits are not filtered out, Track B may accidentally measure mixed retrieval rather than TEXT retrieval.
- If this local progress file is not merged later, progress history may fragment across docs.

### Next Recommended Step

- Start B0 and record the actual backend identity, path mixing behavior, and TEXT-only filter feasibility.

## 2026-05-05 - B0 backend identity recorded

### Goal

- Execute B0 by identifying the actual TEXT retrieval backend and recording whether Track B can proceed to bound TEXT gold rows.
- Keep the result diagnostic-only and separate from XLSX/PDF promotion evidence.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B0 backend identity | `planned` | `diagnostic_completed` | `reports/rag_text_backend_identity_report.json` |
| B1 gold v0 | `blocked_on_B0` | `blocked_on_B0` | B0 report has `b1_entry_allowed=false` |
| B2 retrieval diagnostic | `blocked_on_B1` | `blocked_on_B1` | No gold v0 exists |
| B3 context assembly | `blocked_on_B2` | `blocked_on_B2` | No retrieval report exists |
| B4 LLM answer eval | `blocked_on_B3` | `blocked_on_B3` | No context report exists |
| B5 citation support | `blocked_on_B4` | `blocked_on_B4` | No answer report exists |
| B6 summary/regression | `blocked_on_B5` | `blocked_on_B5` | No citation report exists |
| B7 scale/stabilize | `blocked_on_B6` | `blocked_on_B6` | No smoke pipeline exists |

### Completed

- Added read-only B0 report generator:
  - `scripts/rag_text_backend_identity.py`
- Added focused unit coverage:
  - `ai-worker/tests/test_rag_text_backend_identity.py`
- Generated B0 artifact:
  - `reports/rag_text_backend_identity_report.json`

### Current Evidence

- B0 backend is `library_search`.
- Backend identity is `GET /api/v1/library/search` -> `DocumentCatalogController.search(query, limit)` -> `DocumentCatalogService.search(query, limit)` -> `SearchUnitJpaRepository.searchByText(query, pageable)`.
- The library-search path is lexical DB search over `SearchUnit` text fields, not vector-grade production Evidence.
- `text_only_filter_supported=false` because the route accepts only `query` and `limit`, and the repository search query has no `source_file_type`, `embedding_status`, or `index_version` predicate.
- Read-only DB snapshot found `text_count=0`, `pdf_count=215633`, `xlsx_count=23028`, `unknown_count=0`, `total_count=238661`.
- Live API probe against `http://localhost:8080/api/v1/library/search?query=test&limit=3` was unavailable because localhost:8080 refused the connection.

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_backend_identity.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_backend_identity.py`
  - result: 3 passed
- Command:
  - `python scripts\rag_text_backend_identity.py --output reports\rag_text_backend_identity_report.json`
  - result: report generated with `promotion_evidence=false`, `evidence_role=diagnostic`, `operational_claim_allowed=false`, `b1_entry_allowed=false`

### Important Decisions

- Keep `retrieval_backend_identity` as the canonical Track B field and include `backend_identity` only as a compatibility alias.
- Do not create B1 gold rows from the current live catalog because there are no TEXT SearchUnits and no TEXT-only library-search filter.
- Treat vector TEXT wrappers and fake text tools as adjacent POC/fixture paths, not as the current B0 backend.

### Remaining Work

- Decide whether Track B should next add a real TEXT-only retrievable corpus/path or explicitly run B1 as fixture-only smoke.
- If using the current library-search path, add a source-type constrained retrieval path before claiming TEXT-only E2E diagnostics.
- Rerun the B0 script after core-api is running if live API result-mixing samples are needed.

### Risks

- Proceeding to B1 without a TEXT-only corpus/path would create misleading gold rows.
- Post-retrieval filtering can count path mixing, but it cannot make `/api/v1/library/search` a TEXT-only backend.
- Local DB counts are a point-in-time snapshot and should be refreshed before any later Track B checkpoint.

### Next Recommended Step

- Keep B1 blocked and prepare the smallest TEXT-only readiness decision: either expose/bind a real TEXT-only search path, or mark the next Track B run as fixture-only smoke with no operational claim.

## 2026-05-05 - B0 TEXT-only library search filter added

### Goal

- Resolve the B0 blocker where `/api/v1/library/search` could not perform TEXT-only retrieval.
- Keep the route diagnostic-only and preserve default unfiltered behavior when no source-type filter is provided.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B0 backend identity | `diagnostic_completed` with filter blocker | `diagnostic_completed` with corpus blocker only | `reports/rag_text_backend_identity_report.json` has `text_only_filter_supported=true` |
| B1 gold v0 | `blocked_on_B0` | `blocked_on_B0` | `b1_entry_allowed=false` because live `text_count=0` |

### Completed

- Added optional repeated query parameter:
  - `GET /api/v1/library/search?query=...&sourceFileTypes=TEXT`
- Threaded `sourceFileTypes` through:
  - `DocumentCatalogController.search`
  - `DocumentCatalogService.search`
  - `SearchUnitJpaRepository.searchByTextAndSourceFileTypes`
- Preserved unfiltered library-search behavior when `sourceFileTypes` is absent or blank.
- Ensured multi-term fallback search uses the same source-type filter.
- Regenerated B0 report.

### Current Evidence

- `text_only_filter_supported=true`.
- `library_search_diagnostics.route_params` now includes `sourceFileTypes`.
- `library_search_diagnostics.unsupported_filters` no longer includes `source_file_type`.
- Read-only DB snapshot still found `text_count=0`, `pdf_count=215633`, `xlsx_count=23028`, `unknown_count=0`, `total_count=238661`.
- Live API probe is still unavailable because localhost:8080 refused the connection.

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_backend_identity.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_backend_identity.py`
  - result: 6 passed
- Command:
  - `mvn -q "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitJpaRepositoryTest" test`
  - result: passed
- Command:
  - `python scripts\rag_text_backend_identity.py --output reports\rag_text_backend_identity_report.json`
  - result: report regenerated; API probe URL includes `sourceFileTypes=MARKDOWN&sourceFileTypes=MD&sourceFileTypes=TEXT&sourceFileTypes=TXT`
- Command:
  - `python -B -c "import json,pathlib; r=json.loads(pathlib.Path('reports/rag_text_backend_identity_report.json').read_text(encoding='utf-8')); assert r['text_only_filter_supported'] is True; assert r['b1_entry_allowed'] is False; assert r['blockers']==['live search_unit snapshot has no TEXT/TXT/MARKDOWN/MD rows']; assert r['promotion_evidence'] is False; assert r['evidence_role']=='diagnostic'"`
  - result: updated B0 report contract ok

### Important Decisions

- Use plural `sourceFileTypes` to match existing scoped indexing conventions.
- Do not treat this as vector-grade or promotion-grade retrieval. The backend remains lexical diagnostic library search.
- Do not proceed to B1 until a real TEXT corpus/path exists, unless the next run is explicitly fixture-only smoke.

### Remaining Work

- Resolve the remaining B0 blocker: live `search_unit` has no TEXT/TXT/MARKDOWN/MD rows.
- Decide whether TEXT corpus should come from existing OCR/Markdown imports, a dedicated TEXT source type import path, or a fixture-only Track B smoke path.
- Rerun B0 with core-api running if API-level sample path-mixing evidence is needed.

### Risks

- `sourceFileTypes` filters on `search_unit.source_file_type`; older rows with only `source_file.file_type` and null SearchUnit type will be excluded when filtered.
- Library search still lacks embedding/index-version/tenant/ACL filters, so it remains diagnostic-only.
- Current B0 report uses local DB counts and should be refreshed after any TEXT corpus import.

### Next Recommended Step

- Inspect available import/corpus paths for creating or binding a small real TEXT corpus without touching XLSX/PDF promotion or vector indexing.

## 2026-05-05 - B0 TEXT corpus import path added

### Goal

- Resolve the B0 blocker where uploaded `.txt`/`.md` files could be registered as source files but could not become `TEXT` SearchUnits.
- Keep this as a narrow catalog import path, not a worker capability, vector promotion path, or PDF/XLSX tuning change.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B0 backend identity | `diagnostic_completed` with corpus path blocker | `diagnostic_completed` with live corpus blocker only | `reports/rag_text_backend_identity_report.json` has `text_corpus_import_path.status=present` |
| B1 gold v0 | `blocked_on_B0` | `blocked_on_B0` | `b1_entry_allowed=false` because no live TEXT rows have been imported yet |

### Completed

- Added synchronous catalog action:
  - `POST /api/v1/library/source-files/{sourceFileId}/text-import`
- Added `DocumentCatalogService.importTextSourceFile(...)`:
  - accepts uploaded plain text / markdown sources,
  - normalizes `.txt`, `.text`, `.md`, `.markdown`, and `text/*` to canonical `TEXT`,
  - creates `DOCUMENT` and `CHUNK` SearchUnits with `source_file_type=TEXT`,
  - fills v2 text fields including `embedding_text`, `bm25_text`, `citation_text`, `location_type=text`, and `location_json`,
  - preserves retry boundary: only `UPLOADED`, `FAILED`, or `EXTRACTION_FAILED` can start.
- Expanded `sourceFileTypes` alias normalization so `TEXT`, `TXT`, `MARKDOWN`, and `MD` query filters cover the same TEXT corpus family.
- Tightened library search and B0 DB counts to READY parent source files only.
- Tightened B1 entry gating so a clean TEXT-filtered API probe is required after live TEXT rows exist.
- Added stale SearchUnit marking for successful TEXT re-imports so old chunks do not remain searchable while preserving FK references.
- Regenerated B0 report with `text_corpus_import_path`.

### Current Evidence

- `text_only_filter_supported=true`.
- `text_corpus_import_path.status=present`.
- `text_corpus_import_path.worker_job_required=false`.
- Live READY DB snapshot still has `text_count=0`, so B1 remains blocked until a real TEXT canary is imported.
- Live API probe is still unavailable because localhost:8080 refused the connection.

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_backend_identity.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_backend_identity.py`
  - result: 6 passed
- Command:
  - `mvn -q "-Dtest=DocumentCatalogControllerTest,DocumentCatalogServiceTest,SearchUnitJpaRepositoryTest" test`
  - result: passed
- Command:
  - `python scripts\rag_text_backend_identity.py --output reports\rag_text_backend_identity_report.json`
  - result: report regenerated with `text_corpus_import_path.status=present`, `path_mixing.source_scope="READY source_file rows only"`, and `b1_entry_allowed=false`
- Command:
  - `python -B -c "import json,pathlib; r=json.loads(pathlib.Path('reports/rag_text_backend_identity_report.json').read_text(encoding='utf-8')); assert r['path_mixing']['source_scope']=='READY source_file rows only'; assert r['blockers']==['live READY search_unit snapshot has no TEXT/TXT/MARKDOWN/MD rows']; assert r['b1_entry_allowed'] is False"`
  - result: READY-gated B0 report contract ok

### Important Decisions

- Do not add a new async `TEXT_EXTRACT` worker capability for B0; this is a smaller catalog import path for already uploaded text sources.
- Do not seed the live DB directly through SQL in this slice. The next corpus evidence should use the app path.
- Do not allow B1 from DB count alone. B1 requires READY TEXT rows plus a clean TEXT-filtered API probe.
- Keep Track B evidence diagnostic-only: `promotion_evidence=false`, `evidence_role=diagnostic`.

### Remaining Work

- Start core-api or use the app route in a local run, upload a small real `.txt`/`.md` canary, call `text-import`, then rerun B0.
- Confirm `sourceFileTypes=TEXT/TXT/MARKDOWN/MD` returns only TEXT-family hits.
- Only after live `text_count>0`, proceed to B1 bound diagnostic gold rows.

### Risks

- The new path is synchronous and intended for small text canaries; larger corpus scaling should be designed separately.
- Stale text chunks are marked non-searchable rather than physically deleted, so old embedding/citation references are preserved but should be treated as historical.
- B0 still cannot claim a live retrievable TEXT corpus until the canary is imported into the local DB and the API probe is verified.
- Library search remains lexical diagnostic search and still lacks embedding/index-version/tenant/ACL filters.

### Next Recommended Step

- Import one small real TEXT canary through `/api/v1/library/source-files/{sourceFileId}/text-import`, rerun B0, and only then open B1.

## 2026-05-05 - B0 blocker cleared and B1 gold v0 bound

### Goal

- Continue unresolved B0 work by proving a live READY TEXT corpus through the app path.
- Proceed only after the B0 blocker is cleared; avoid restarting Track A A1 because Track A progress already records A1 as completed.
- Create B1 diagnostic gold v0 with live TEXT source/chunk bindings and a validator report.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B0 backend identity | `diagnostic_completed` with live corpus blocker | `diagnostic_completed` with blocker cleared | `reports/rag_text_backend_identity_report.json` has `b1_entry_allowed=true` and `blockers=[]` |
| B1 gold v0 | `blocked_on_B0` | `diagnostic_completed` | `ai-worker/eval/eval_queries/gold_queries_text_e2e_v0.csv`, `reports/rag_text_e2e_gold_validate_report.json` |
| B2 retrieval diagnostic | `blocked_on_B1` | `planned` | B1 validation passed; B2 report not generated yet |

### Completed

- Started local core-api against the existing compose PostgreSQL/Redis and confirmed `/actuator/health` returned `UP`.
- Imported a B0 TEXT canary through the public app path:
  - `POST /api/v1/library/source-files`
  - `POST /api/v1/library/source-files/{sourceFileId}/text-import`
  - `GET /api/v1/library/search?...&sourceFileTypes=TEXT&sourceFileTypes=TXT&sourceFileTypes=MARKDOWN&sourceFileTypes=MD`
- Added B1 diagnostic corpus files under:
  - `eval/text_e2e_corpus_v0/`
- Added a corpus manifest with file hashes, import route, parser version, and current local live bindings:
  - `eval/text_e2e_corpus_v0/manifest.json`
- Imported those corpus files through the same app path and bound B1 rows to live source/chunk ids.
- Added B1 gold:
  - `ai-worker/eval/eval_queries/gold_queries_text_e2e_v0.csv`
- Added B1 validator and tests:
  - `scripts/rag_text_e2e_gold_validator.py`
  - `ai-worker/tests/test_rag_text_e2e_gold_validator.py`
- Updated B0 report wording so `next_phase_recommendation` matches `b1_entry_allowed=true`.
- Hardened B1 validation after review:
  - row-level `expected_chunk_ids` must belong to the row's `expected_source_ids`
  - `--skip-db` now produces `SCHEMA_ONLY`, not B1 `PASSED`

### Current Evidence

- B0 report:
  - `text_only_filter_supported=true`
  - `text_corpus_import_path.status=present`
  - `path_mixing.text_count=15`
  - `api_probe.status=OK`
  - `api_result_path_mixing.non_text_count=0`
  - `b1_entry_allowed=true`
  - `blockers=[]`
- B1 validator report:
  - `status=PASSED`
  - `row_count=12`
  - bucket counts include `text_fact_lookup`, `text_policy_question`, `text_procedure`, `text_multi_chunk_summary`, `text_comparison`, and `text_abstain_required`
  - `source_id_count=6`
  - `chunk_id_count=7`
  - `chunk_source_mismatches=[]`
  - live binding blockers empty
  - `promotion_evidence=false`, `evidence_role=diagnostic`

### Verification

- Command:
  - `Invoke-RestMethod -Uri http://localhost:8080/actuator/health -Method Get`
  - result: `status=UP`
- Command:
  - `python scripts\rag_text_backend_identity.py --api-probe-query trackb0textcanary20260505 --output reports\rag_text_backend_identity_report.json`
  - result: B0 regenerated with `b1_entry_allowed=true`, `blockers=[]`
- Command:
  - `python -m py_compile scripts\rag_text_e2e_gold_validator.py scripts\rag_text_backend_identity.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_e2e_gold_validator.py ai-worker\tests\test_rag_text_backend_identity.py`
  - result: 10 passed
- Command:
  - `python scripts\rag_text_e2e_gold_validator.py --gold eval\gold_queries_text_e2e_v0.csv --report reports\rag_text_e2e_gold_validate_report.json`
  - result: B1 validator report `status=PASSED`
- Command:
  - `python scripts\rag_text_e2e_gold_validator.py --skip-db --gold eval\gold_queries_text_e2e_v0.csv --report %TEMP%\rag_text_e2e_gold_validate_schema_only.json`
  - result: expected non-zero exit with report `status=SCHEMA_ONLY`; B1 done was not claimed without live DB binding
- Command:
  - `python -m json.tool eval\text_e2e_corpus_v0\manifest.json`
  - result: manifest JSON parsed

### Important Decisions

- B0/B1 corpus evidence was created through the app upload/import route, not direct SQL seeding.
- Track A A1 was not restarted; `docs/rag-ingestion/xlsx-retrieval/phase-progress.md` already records Track A A1 as `COMPLETED`.
- B1 gold is a diagnostic seed set only. It is not a human-reviewed benchmark and not promotion evidence.
- B2 must keep using TEXT-only `sourceFileTypes` filters because the live catalog still contains many PDF/XLSX rows.

### Remaining Work

- Run B2 retrieval-only diagnostic and generate `reports/rag_text_retrieval_diagnostic_report.json`.
- Keep later B3-B7 blocked until their required prior reports exist.
- Decide later whether the temporary Track B progress entries should be merged into `docs/rag-ingestion-progress.md`.

### Risks

- B1 ids are bound to the current local live catalog. A clean database will need the B1 corpus imported again before live-binding validation can pass; `eval/text_e2e_corpus_v0/manifest.json` records file hashes and current local bindings for that rebind step.
- `library_search` is lexical diagnostic search, not vector-grade or production-grade retrieval evidence.
- The B1 corpus is synthetic and intentionally small, so row-level success must not be generalized to user traffic.

### Next Recommended Step

- Start B2 retrieval diagnostic using `ai-worker/eval/eval_queries/gold_queries_text_e2e_v0.csv` and the TEXT-only library-search filter.

## 2026-05-05 - B2 retrieval-only diagnostic completed

### Goal

- Implement and run the B2 retrieval-only diagnostic against live `library_search`.
- Keep the run TEXT-only and diagnostic-only.
- Separate retrieval failures from later answer/context/citation failures.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B1 gold v0 | `diagnostic_completed` | `diagnostic_completed` | `reports/rag_text_e2e_gold_validate_report.json` rerun with `status=PASSED` |
| B2 retrieval diagnostic | `planned` | `diagnostic_completed` | `reports/rag_text_retrieval_diagnostic_report.json` |
| B3 context assembly | `blocked_on_B2` | `planned` | B2 report exists, but current retrieval produced no expected evidence hits |

### Completed

- Added B2 diagnostic runner:
  - `scripts/rag_text_retrieval_diagnostic.py`
- Added focused unit coverage:
  - `ai-worker/tests/test_rag_text_retrieval_diagnostic.py`
- Generated B2 artifact:
  - `reports/rag_text_retrieval_diagnostic_report.json`

### Current Evidence

- B2 report:
  - `status=COMPLETED`
  - `retrieval_backend=library_search`
  - `source_file_types=["MARKDOWN","MD","TEXT","TXT"]`
  - `query_count=12`
  - `evidence_query_count=10`
  - `abstain_query_count=2`
  - `Hit@1=0.0`, `Hit@3=0.0`, `Hit@5=0.0`, `Hit@10=0.0`
  - `MRR@10=0.0`
  - `source_recall@10=0.0`
  - `chunk_recall@10=0.0`
  - overall Hit/MRR policy is `expected source OR expected chunk`, with separate `source_*` and `chunk_*` Hit/MRR metrics also recorded
  - `result_empty_count=12`
  - `wrong_source_top1_count=0`
  - `path_mixing_count=0`
  - `search_error_count=0`
  - `overall_failure_reason_counts.search_result_empty=10`
- The two abstain rows have no expected source/chunk ids and were excluded from positive Hit/MRR/recall denominators.
- The TEXT-only filter did not return PDF/XLSX/unknown hits in this run.
- Current lexical `library_search` returned empty results for all B1 query phrasings, so the diagnostic identifies retrieval matching failure before any LLM answer step.
- A direct lexical probe for `query=renewed` returned the expected `bluewater_library_access_policy.txt` TEXT source/chunk, so the empty B2 results are not explained by missing corpus or a broken TEXT filter alone.

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_retrieval_diagnostic.py scripts\rag_text_e2e_gold_validator.py scripts\rag_text_backend_identity.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_retrieval_diagnostic.py`
  - result: 7 passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_retrieval_diagnostic.py ai-worker\tests\test_rag_text_e2e_gold_validator.py ai-worker\tests\test_rag_text_backend_identity.py`
  - result: 19 passed
- Command:
  - `Invoke-RestMethod -Uri http://localhost:8080/actuator/health -Method Get`
  - result: `status=UP`
- Command:
  - `python scripts\rag_text_e2e_gold_validator.py --gold eval\gold_queries_text_e2e_v0.csv --report reports\rag_text_e2e_gold_validate_report.json`
  - result: B1 validator report `status=PASSED`
- Command:
  - `python scripts\rag_text_retrieval_diagnostic.py --gold eval\gold_queries_text_e2e_v0.csv --backend library_search --source-file-type TEXT --top-k 10 --report reports\rag_text_retrieval_diagnostic_report.json`
  - result: B2 report generated with `promotion_evidence=false`, `evidence_role=diagnostic`, `path_mixing_count=0`, and `search_error_count=0`
- Command:
  - `Invoke-RestMethod -Uri "http://localhost:8080/api/v1/library/search?query=renewed&limit=3&sourceFileTypes=TEXT" -Method Get`
  - result: returned expected TEXT hits for `bluewater_library_access_policy.txt`, including chunk id `fcf39aae-7c4d-47a1-aa86-546a70182e95`

### Important Decisions

- B2 uses repeated `sourceFileTypes` API parameters and expands `TEXT` to the TEXT-family aliases used by B0/B1.
- Search errors are not counted as empty results.
- Abstain rows are accounted for separately and do not lower positive retrieval metrics.
- This remains diagnostic-only evidence, not vector promotion evidence.

### Remaining Work

- Review why lexical `library_search` returns no hits for the current natural-language B1 query wording.
- Decide whether B3 should intentionally record empty context assembly for this failed retrieval diagnostic or wait for a retrieval/query-matching improvement slice.
- Keep B4-B7 blocked until B3 has a context assembly artifact.

### Risks

- The current B2 report proves the live route executes with a clean TEXT-only filter, but it does not prove useful retrieval.
- Because B1 rows are bound to local live-catalog ids, a clean DB still needs corpus import and rebind before this report can be reproduced.
- If B3 is run immediately, it will likely document empty contexts for all positive evidence rows.

### Next Recommended Step

- Do a narrow B2 follow-up review of `library_search` query matching versus B1 query wording before moving to answer evaluation.

## 2026-05-05 - Track B replan phase files restructured

### Goal

- Rebuild the Track B directory around query intent routing and the namu-v4 TEXT mainline.
- Preserve existing B-app evidence as smoke-only instead of deleting or overwriting it.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B2 retrieval diagnostic | `diagnostic_completed` | `diagnostic_completed / smoke_only` | `phase_b2_retrieval_diagnostic.md`, top Phase Status Board |
| R0 B2 scope correction | none | `planned` | `phases/phase_r0_b2_scope_correction.md` |
| R1 query routing matrix | none | `planned` | `phases/phase_r1_query_intent_routing_matrix.md`, `query_intent_taxonomy.md` |
| R2 namu-v4 corpus inventory | none | `planned` | `phases/phase_r2_namu_v4_corpus_inventory.md` |
| R3-R9 | none | `planned/blocked` | phase files under `phases/` |

### Completed

- Replaced the Track B README with the current lane map and R0-R9 phase map.
- Added query intent taxonomy documentation.
- Added phase files under `docs/track_b_text_retrieval_e2e/phases/`.
- Marked the legacy B2 document as `B2-app` smoke-only and linked the B2-namu mainline phase.
- Updated the top Phase Status Board so B3/B4/B5 no longer proceed from the old app-catalog B2 result.

### Current Evidence

- This was a documentation restructuring pass only.
- No retrieval eval, indexing, tuning, LLM run, report generation, or candidate mutation was performed.

### Verification

- Command:
  - `rg --files docs\track_b_text_retrieval_e2e`
  - result: README, taxonomy doc, legacy B-app phase files, and R0-R9 phase files are present.
- Command:
  - `rg -n "[ \t]+$" docs/track_b_text_retrieval_e2e`
  - result: no trailing whitespace matches.

### Important Decisions

- Keep B-app reports as valid smoke evidence, not representative namu-v4 evidence.
- Use `B-namu` over `namu-v4-structured-combined` as the Track B mainline.
- Keep FILE lookup and CONTENT lookup separate before computing retrieval denominators.

### Remaining Work

- Implement R0/R1/R2 scripts and reports as the first execution slice.
- Do not proceed to B2-namu retrieval diagnostic until R2/R3/R4 establish corpus, gold, and retrieval emit decisions.

### Risks

- Old B-app reports can still be misread if quoted without the `smoke_only` qualifier.
- R2 must verify the raw context field before R6; otherwise answer evaluation could accidentally use embedding/debug text.

### Next Recommended Step

- Start R0 scope correction report generation, then R1 routing matrix and R2 corpus inventory.

## 2026-05-05 - R0 B2 scope correction completed

### Goal

- Execute R0 from `phases/phase_r0_b2_scope_correction.md`.
- Preserve the existing B2-app retrieval diagnostic metrics while narrowing their interpretation to app-catalog TEXT canary smoke.
- Keep B-namu, namu-v4, answer evaluation, and promotion claims out of the legacy B2-app evidence.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B2-app retrieval diagnostic | `diagnostic_completed / smoke_only` | `diagnostic_completed / smoke_only` | `reports/rag_text_retrieval_diagnostic_report.json` preserved |
| R0 B2 scope correction | `planned` | `diagnostic_completed` | `reports/rag_text_b2_scope_correction_report.json`, `phases/phase_progress.md` |
| R1 query routing matrix | `planned` | `planned` | `phases/phase_r1_query_intent_routing_matrix.md` |
| R2 namu-v4 corpus inventory | `planned` | `planned` | `phases/phase_r2_namu_v4_corpus_inventory.md` |
| B2-namu retrieval diagnostic | `blocked_on_R3_R4` | `blocked_on_R3_R4` | Do not use B2-app metrics as B-namu evidence |
| B3/B4/B5 namu phases | `blocked_on_B2_namu/B3_namu/B4_namu` | `blocked_on_B2_namu/B3_namu/B4_namu` | B2-app smoke does not unlock answer/citation phases |

### Completed

- Added phase-local progress tracking:
  - `docs/track_b_text_retrieval_e2e/phases/phase_progress.md`
- Added R0 scope-correction report:
  - `reports/rag_text_b2_scope_correction_report.json`
- Added a direct R0 scope note to the legacy B2-app phase doc:
  - `docs/track_b_text_retrieval_e2e/phase_b2_retrieval_diagnostic.md`

### Current Evidence

- R0 report:
  - `status=COMPLETED`
  - `scope_correction=true`
  - `new_b2_label=B-app app-catalog TEXT canary smoke`
  - `representative_of_namu_v4=false`
  - `representative_of_existing_text_retrieval=false`
  - `b2_namu_status=NOT_STARTED`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
- Preserved B2-app metrics:
  - `Hit@10=0.0`
  - `MRR@10=0.0`
  - `result_empty_count=12`
  - `path_mixing_count=0`
  - `search_error_count=0`

### Gate/Baseline Status

- No retrieval eval rerun was performed.
- No indexing, tuning, LLM run, candidate mutation, immutable baseline update, or `rag-data-canary` update was performed.
- This entry is diagnostic-only and does not alter promotion-gate evidence.

### Verification

- Command:
  - `python -m json.tool reports\rag_text_b2_scope_correction_report.json > $null`
  - result: passed
- Command:
  - `python -B -c "import json, pathlib; r=json.loads(pathlib.Path('reports/rag_text_b2_scope_correction_report.json').read_text(encoding='utf-8')); assert r['status']=='COMPLETED'; assert r['scope_correction'] is True; assert r['new_b2_label']=='B-app app-catalog TEXT canary smoke'; assert r['representative_of_namu_v4'] is False; assert r['representative_of_existing_text_retrieval'] is False; assert r['b2_namu_status']=='NOT_STARTED'; assert r['promotion_evidence'] is False; assert r['evidence_role']=='diagnostic'; assert r['b2_app_report_modified_by_scope_correction'] is False; assert r['acceptance_criteria']['b3_b4_b5_follow_b2_namu_not_b2_app'] is True"`
  - result: passed
- Command:
  - `rg -n "[ \t]+$" docs\track_b_text_retrieval_e2e`
  - result: no trailing whitespace matches
- Command:
  - `git diff --check`
  - result: passed; existing CRLF conversion warnings were printed for modified files

### Important Decisions

- Do not overwrite the historical B2-app diagnostic report to change its meaning.
- Treat `reports/rag_text_b2_scope_correction_report.json` as the authoritative interpretation layer for old B2-app metrics.
- Keep B3/B4/B5 connected to B-namu artifacts, not the B2-app smoke report.

### Remaining Work

- Start R1 query intent routing matrix after R0 verification.
- Do not proceed to B2-namu retrieval diagnostic until R2/R3/R4 establish corpus, gold, and retrieval emit decisions.

### Risks

- `reports/rag_text_retrieval_diagnostic_report.json` still contains historical fields such as `phase=B2` and `smoke_only=false`; cite it with the R0 correction report to avoid misreading it as Track B mainline evidence.
- R2 must still prove the raw context field before R6 context assembly.

### Next Recommended Step

- Verify R0 artifacts, then start R1 query intent routing matrix.

## 2026-05-05 - R1 query intent routing matrix generated

### Goal

- Execute R1 from `phases/phase_r1_query_intent_routing_matrix.md`.
- Build a routing matrix that prevents B-app TEXT smoke, B-namu TEXT, XLSX content, PDF content, file lookup, UNKNOWN, and MIXED rows from sharing one retrieval denominator.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| R1 query routing matrix | `planned` | `needs_review` | `ai-worker/eval/eval_queries/query_intent_routing_matrix_v0.csv`, `reports/rag_query_intent_routing_matrix_report.json` |
| R2 namu-v4 corpus inventory | `planned` | `planned` | R1 records missing namu gold as future input |
| B2-namu retrieval diagnostic | `blocked_on_R3_R4` | `blocked_on_R3_R4` | `B_NAMU_TEXT_CONTENT=0` until R2/R3 create namu gold |
| R9 file/content lane readiness | `planned` | `planned` | FILE lanes explicit, current candidate inputs contain zero FILE rows |

### Completed

- Added R1 diagnostic script:
  - `scripts/rag_query_intent_routing_matrix.py`
- Added tests:
  - `ai-worker/tests/test_rag_query_intent_routing_matrix.py`
- Generated artifacts:
  - `ai-worker/eval/eval_queries/query_intent_routing_matrix_v0.csv`
  - `reports/rag_query_intent_routing_matrix_report.json`
- Updated phase-local progress:
  - `docs/track_b_text_retrieval_e2e/phases/phase_progress.md`

### Current Evidence

- R1 report:
  - `status=NEEDS_REVIEW`
  - `row_count=204`
  - `blockers=[]`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
  - `unknown_count=0`
  - `mixed_file_content_count=0`
- Lane counts:
  - `APP_TEXT_SMOKE=12`
  - `XLSX_CONTENT=170`
  - `PDF_CONTENT=22`
  - `B_NAMU_TEXT_CONTENT=0`
  - `TEXT_FILE_LOOKUP=0`
  - `XLSX_FILE=0`
  - `PDF_FILE=0`
  - `UNKNOWN=0`
- Observed required lane coverage:
  - `B_NAMU_TEXT_CONTENT=false`
  - `XLSX_CONTENT=true`
  - `PDF_CONTENT=true`
  - `XLSX_FILE=false`
  - `PDF_FILE=false`
  - `UNKNOWN=false`
- Positive denominator policy:
  - `must_group_by=["retrieval_lane"]`
  - excludes `BLOCKED`, `NOT_READY`, `PLANNED`, and `SMOKE_ONLY` readiness rows
  - currently only `XLSX_CONTENT` appears in `eligible_denominator_groups_by_lane`
  - `eligible_denominator_groups_by_lane.XLSX_CONTENT.row_count=35`
- Denominator exclusion counts:
  - `source manifest is not the reviewed XLSX positive set=135`
  - `readiness_blocked_excluded=22`
  - `readiness_smoke_only_excluded=12`

### Gate/Baseline Status

- No retrieval eval rerun was performed.
- No indexing, tuning, LLM run, candidate mutation, immutable baseline update, or `rag-data-canary` update was performed.
- R1 is denominator hygiene only and does not change promotion-gate evidence.

### Verification

- Command:
  - `python -m py_compile scripts\rag_query_intent_routing_matrix.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_query_intent_routing_matrix.py`
  - result: 9 passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_query_intent_routing_matrix.py ai-worker\tests\test_rag_text_e2e_gold_validator.py ai-worker\tests\test_rag_text_backend_identity.py ai-worker\tests\test_rag_text_retrieval_diagnostic.py`
  - result: 28 passed
- Command:
  - `python scripts\rag_query_intent_routing_matrix.py`
  - result: wrote `204` routing rows with report `status=NEEDS_REVIEW` and no blockers
- Command:
  - `python -B -c "import csv,json,pathlib; report=json.loads(pathlib.Path('reports/rag_query_intent_routing_matrix_report.json').read_text(encoding='utf-8')); rows=list(csv.DictReader(pathlib.Path('ai-worker/eval/eval_queries/query_intent_routing_matrix_v0.csv').open(encoding='utf-8-sig', newline=''))); group=report['positive_denominator_policy']['eligible_denominator_groups_by_lane']['XLSX_CONTENT']; assert report['status']=='NEEDS_REVIEW'; assert report['blockers']==[]; assert report['promotion_evidence'] is False; assert report['evidence_role']=='diagnostic'; assert report['row_count']==len(rows)==204; assert report['lane_counts']['APP_TEXT_SMOKE']==12; assert report['lane_counts']['XLSX_CONTENT']==170; assert report['lane_counts']['PDF_CONTENT']==22; assert report['completion_criteria']['observed_required_lane_coverage_complete'] is False; assert report['positive_denominator_policy']['must_group_by']==['retrieval_lane']; assert 'PDF_CONTENT' in report['positive_denominator_policy']['exclude_retrieval_lanes']; assert group['row_count']==35; assert len(group['query_ids'])==35; assert report['denominator_exclusion_counts']['source manifest is not the reviewed XLSX positive set']==135"`
  - result: passed
- Command:
  - `rg -n "[ \t]+$" docs\track_b_text_retrieval_e2e scripts\rag_query_intent_routing_matrix.py ai-worker\tests\test_rag_query_intent_routing_matrix.py`
  - result: no trailing whitespace matches
- Command:
  - `git diff --check`
  - result: passed; existing CRLF conversion warnings were printed for modified files

### Important Decisions

- `ai-worker/eval/eval_queries/gold_queries_text_e2e_v0.csv` is `APP_TEXT_SMOKE`, not B-namu evidence.
- Row-level expected location/content metadata takes priority over weak file-like wording such as `찾아줘`.
- Missing `ai-worker/eval/eval_queries/gold_queries_text_namu_v4_v0.csv` is recorded as a future input because R2/R3 have not created it yet.
- Do not claim full observed lane coverage until B-namu/file/unknown rows are actually present or intentionally fixture-tested.

### Remaining Work

- Start R2 namu-v4 corpus inventory.
- Keep B2-namu retrieval diagnostic blocked until R2/R3/R4 complete.

### Risks

- Current candidate inputs contain no actual `B_NAMU_TEXT_CONTENT`, `XLSX_FILE`, `PDF_FILE`, or `UNKNOWN` rows, so R1 is `NEEDS_REVIEW` for observed lane coverage while still producing usable denominator policy.
- PDF content remains blocked until Track C readiness.

### Next Recommended Step

- Start R2 namu-v4 corpus inventory.

## 2026-05-05 - R2 namu-v4 corpus inventory completed

### Goal

- Retry the R1 observed-lane gap before proceeding.
- Verify the active `namu-v4-structured-combined` corpus structure, hashes, JSONL parseability, `rag_chunks` chunk-id uniqueness, and raw context field.
- Keep the result diagnostic-only and suitable for later merge into `docs/rag-ingestion-progress.md`.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| R1 query routing matrix | `needs_review` | `needs_review` | Retry regenerated `reports/rag_query_intent_routing_matrix_report.json`; current candidate inputs still lack B-namu/file/unknown observed rows |
| R2 namu-v4 corpus inventory | `planned` | `diagnostic_completed` | `reports/rag_text_namu_v4_corpus_inventory_report.json` |
| R3 namu-v4 gold binding | `blocked_on_R2` | `planned` | R2 PASS unlocks gold binding |
| R4 retrieval emit inventory | `blocked_on_R2_R3` | `blocked_on_R3` | Still waits for R3 gold |

### Completed

- Added R2 inventory script:
  - `scripts/rag_text_namu_v4_corpus_inventory.py`
- Added focused tests:
  - `ai-worker/tests/test_rag_text_namu_v4_corpus_inventory.py`
- Generated R2 artifact:
  - `reports/rag_text_namu_v4_corpus_inventory_report.json`

### Current Evidence

- R1 retry:
  - `status=NEEDS_REVIEW`
  - `row_count=204`
  - `blockers=[]`
  - Missing observed lanes remain `B_NAMU_TEXT_CONTENT`, `XLSX_FILE`, `PDF_FILE`, and `UNKNOWN`.
- R2 report:
  - `status=PASS`
  - `blockers=[]`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
- File inventory:
  - `pages_v4.jsonl`: `row_count=4314`, `sha256=3acd4e8beba4c905ca21162b14689a3c351b8b6a8c20ee61a605e53208d4bdc9`
  - `chunks_v4.jsonl`: `row_count=48675`, `sha256=b170c9e9dfd9ae07b43ae67105c0ba64dc191bd6be6ac22952e080cbe3498492`
  - `rag_chunks.jsonl`: `row_count=135602`, `sha256=c9c18da61956de6494ca314908841ae7f2df78f313094767c2624d6bcd73cb9a`
- `rag_chunks.jsonl` context evidence:
  - `chunk_id_unique=true`
  - `raw_context_field=chunk_text`
  - `empty_chunk_text_count=0`
  - `page_identity_complete=true`
  - `page_identity_matches_pages_v4=true`
  - `page_identity_missing_from_pages_v4_count=0`
  - `missing_section_path_count=0`
  - `missing_title_count=0`
  - `missing_page_id_count=135602`
  - `missing_doc_id_count=0`
  - `unique_doc_id_count=4314`
  - `page_identifier_field=doc_id`
- `pages_v4.jsonl` identity evidence:
  - `page_id_unique=true`
  - `unique_page_id_count=4314`
  - `missing_page_id_count=0`
  - `duplicate_page_id_count=0`
- Context policy:
  - `chunk_text` is selected for answer context.
  - `embedding_text`, `text_for_embedding`, and `debug_text` are disallowed as LLM context fields.
  - `embedding_text` exists on all `rag_chunks` rows but was not selected.

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_namu_v4_corpus_inventory.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_namu_v4_corpus_inventory.py`
  - result: 11 passed
- Command:
  - `python scripts\rag_query_intent_routing_matrix.py`
  - result: R1 retry wrote `204` routing rows with `status=NEEDS_REVIEW` and no blockers
- Command:
  - `python scripts\rag_text_namu_v4_corpus_inventory.py`
  - result: R2 report generated with `status=PASS`, `raw_context_field=chunk_text`, and `blocker_count=0`

### Important Decisions

- Use `rag_chunks.jsonl`, not `chunks_v4.jsonl`, as the B-namu answerability join fixture.
- Treat missing literal `page_id` in `rag_chunks.jsonl` as a warning because `doc_id` is fully populated and every `doc_id` matches `pages_v4.page_id`.
- Keep R1 as `NEEDS_REVIEW`; retry confirmed the missing lanes are absent from current inputs, not a script crash.

### Remaining Work

- Start R3 namu-v4 gold binding.
- Keep R4/R5 blocked until R3 gold and R4 retrieval emit decisions exist.

### Risks

- Later context assembly must not read `embedding_text`.
- Later joins that require literal `page_id` must explicitly map `doc_id` or provide a separate proof.

### Next Recommended Step

- Start R3 namu-v4 gold binding.

## 2026-05-05 - R2 hardened and R3 namu-v4 gold binding completed

### Goal

- Strengthen R2 before moving forward.
- Build and validate the R3 namu-v4 gold CSV from the manually curated v4 seed.
- Re-run R1 afterward so the new namu gold is visible as a future input.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| R1 query routing matrix | `needs_review` | `needs_review` | `reports/rag_query_intent_routing_matrix_report.json` records future namu gold exists with `row_count=50` |
| R2 namu-v4 corpus inventory | `diagnostic_completed` | `diagnostic_completed` | `reports/rag_text_namu_v4_corpus_inventory_report.json` schema v2 hardened PASS with split-count check |
| R3 namu-v4 gold binding | `planned` | `diagnostic_completed` | `ai-worker/eval/eval_queries/gold_queries_text_namu_v4_v0.csv`, build/validate reports |
| R4 retrieval emit inventory | `blocked_on_R3` | `planned` | R3 validator PASSED |
| B2-namu retrieval diagnostic | `blocked_on_R3_R4` | `blocked_on_R4` | Waits for R4 retrieval emit inventory |

### Completed

- Hardened R2 with auxiliary validation/split report consistency checks and raw-context trust counters.
- Added R3 builder/validator and focused tests.
- Generated `50` namu-v4 gold rows from the manual curated seed.
- Regenerated the R1 routing matrix after R3.

### Current Evidence

- R2:
  - `status=PASS`
  - `schema_version=rag_text_namu_v4_corpus_inventory_v2`
  - `blockers=[]`
  - validation/split consistency checks pass
  - split manifest declared doc counts match split `doc_ids`, total, and `pages_v4` row count
  - raw context remains `chunk_text`
- R3:
  - build `status=COMPLETED`
  - validation `status=PASSED`
  - `row_count=50`
  - `positive_row_count=47`
  - `needs_review_row_count=3`
  - `allowed_abstain=false` for all rows
  - bucket counts are `text_fact_lookup=31`, `text_multi_chunk_summary=16`, `text_policy_question=3`
  - missing page/chunk/section ids are all empty
- R1 retry:
  - still `status=NEEDS_REVIEW`
  - future namu input exists, but observed lane coverage remains intentionally incomplete

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_namu_v4_corpus_inventory.py scripts\rag_text_namu_v4_gold_builder.py scripts\rag_text_namu_v4_gold_validator.py scripts\rag_query_intent_routing_matrix.py scripts\rag_text_e2e_gold_validator.py scripts\rag_text_backend_identity.py scripts\rag_text_retrieval_diagnostic.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_namu_v4_corpus_inventory.py ai-worker\tests\test_rag_text_namu_v4_gold_validator.py ai-worker\tests\test_rag_query_intent_routing_matrix.py ai-worker\tests\test_rag_text_e2e_gold_validator.py ai-worker\tests\test_rag_text_backend_identity.py ai-worker\tests\test_rag_text_retrieval_diagnostic.py`
  - result: 53 passed
- Command:
  - `python scripts\rag_text_namu_v4_corpus_inventory.py`
  - result: R2 `status=PASS`, `blocker_count=0`
- Command:
  - `python scripts\rag_text_namu_v4_gold_builder.py`
  - result: R3 build `status=COMPLETED`, `row_count=50`
- Command:
  - `python scripts\rag_text_namu_v4_gold_validator.py`
  - result: R3 validation `status=PASSED`, `positive_row_count=47`
- Command:
  - `python scripts\rag_query_intent_routing_matrix.py`
  - result: R1 retry `status=NEEDS_REVIEW`, future namu input exists
- Command:
  - custom Python contract assertion over R2/R3/R1 reports
  - result: contract ok

### Important Decisions

- Use `rag_chunks.jsonl` for R3 page/chunk/section binding.
- Do not use `chunks_v4.jsonl` as a silent substitute for answerability joins.
- Do not fabricate abstain rows from the current seed; use `needs_review` policy rows for the 3 partially answerable cases.
- Keep all R2/R3/R1 evidence diagnostic-only.

### Remaining Work

- Start R4 retrieval emit inventory.
- Keep B2-namu metrics blocked until R4 decides emit reuse or fresh retrieval.

### Risks

- R3 validates gold binding only; it does not prove retrieval quality or answer/citation quality.
- R1 observed lane coverage is still incomplete because the new namu gold remains a future input for later retrieval phases.

### Next Recommended Step

- Start R4 retrieval emit inventory.

## 2026-05-05 - R3 Rechecked and R4 Retrieval Emit Inventory Completed

### Goal

- Revalidate the R3 namu-v4 gold CSV before R4.
- Make the current R3 seed policy explicit in validator output.
- Inventory existing retrieval emit artifacts without running retrieval metrics.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| R3 namu-v4 gold binding | `diagnostic_completed` | `diagnostic_completed` | `reports/rag_text_namu_v4_gold_validate_report.json` re-run `PASSED` |
| R4 retrieval emit inventory | `planned` | `diagnostic_completed` | `reports/rag_text_namu_v4_retrieval_emit_inventory_report.json` |
| B2-namu retrieval diagnostic | `blocked_on_R4` | `ready_for_fresh_diagnostic` | R4 decision `RUN_FRESH_DIAGNOSTIC_RETRIEVAL` |

### Completed

- Strengthened R3 validator/test coverage for current seed policy and section-path mismatch blockers.
- Added R4 inventory script/test/report.
- Confirmed existing emit candidates are not reusable for R3 gold IDs.

### Current Evidence

- R3:
  - `status=PASSED`
  - `row_count=50`
  - `positive_row_count=47`
  - `needs_review_row_count=3`
  - `allowed_abstain_true_count=0`
  - `section_path_mismatch_count=0`
  - `source_dataset_is_manual_curated_seed=true`
- R4:
  - `status=NO_REUSABLE_EXISTING_EMIT`
  - `decision=RUN_FRESH_DIAGNOSTIC_RETRIEVAL`
  - `candidate_emit_count=46`
  - `reusable_emit_count=0`
  - `fresh_retrieval_required=true`
  - `retrieval_metrics_computed=false`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
- R5 entry:
  - allowed as fresh diagnostic retrieval only
  - do not reuse the inventoried Phase 7/B-app/XLSX/PDF/file lookup artifacts for metric input

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_namu_v4_gold_validator.py scripts\rag_text_namu_v4_retrieval_emit_inventory.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_namu_v4_gold_validator.py ai-worker\tests\test_rag_text_namu_v4_retrieval_emit_inventory.py`
  - result: 16 passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_namu_v4_corpus_inventory.py ai-worker\tests\test_rag_text_namu_v4_gold_validator.py ai-worker\tests\test_rag_text_namu_v4_retrieval_emit_inventory.py ai-worker\tests\test_rag_query_intent_routing_matrix.py ai-worker\tests\test_rag_text_e2e_gold_validator.py ai-worker\tests\test_rag_text_backend_identity.py ai-worker\tests\test_rag_text_retrieval_diagnostic.py`
  - result: 60 passed
- Command:
  - `python scripts\rag_text_namu_v4_gold_builder.py`
  - result: R3 build `status=COMPLETED`, `row_count=50`
- Command:
  - `python scripts\rag_text_namu_v4_gold_validator.py`
  - result: R3 validation `status=PASSED`, `positive_row_count=47`
- Command:
  - `python scripts\rag_text_namu_v4_retrieval_emit_inventory.py`
  - result: R4 inventory `status=NO_REUSABLE_EXISTING_EMIT`, `decision=RUN_FRESH_DIAGNOSTIC_RETRIEVAL`
- Command:
  - JSON parse and custom contract assertion over R2/R3/R4 reports
  - result: passed
- Command:
  - `rg -n "[ \t]+$" ...`
  - result: no trailing whitespace found in touched R3/R4 files
- Command:
  - `git diff --check`
  - result: passed; only CRLF normalization warnings in the dirty worktree

### Important Decisions

- R3/R4 binding and resolution use `rag_chunks.jsonl`; `chunks_v4.jsonl` remains non-substitute auxiliary inventory context.
- Current R3 seed has no abstain rows; the `3` policy rows stay `needs_review` and out of the positive metric denominator.
- R4 did not compute retrieval metrics; R5 must generate fresh diagnostic retrieval output.

### Remaining Work

- Start R5 B2-namu retrieval diagnostic with a fresh emit.
- Keep R5 metric denominator and excluded `needs_review` rows explicit.

### Risks

- Existing Phase 7 emits can resolve chunks/pages but use the wrong query ID namespace (`v4-llm-silver-*`), so they are not Track B R5 metric evidence.
- R4 proves inventory/decision state only, not retrieval quality.

### Next Recommended Step

- Run R5 fresh B2-namu retrieval diagnostic.
