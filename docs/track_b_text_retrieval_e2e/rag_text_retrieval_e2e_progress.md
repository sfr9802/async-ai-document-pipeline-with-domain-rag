# Track B — TEXT Retrieval E2E Progress Log

This document tracks phase-level execution progress for Track B TEXT retrieval E2E diagnostics.
It follows the style of `docs/rag-ingestion-progress.md`, but stays local to this Track B directory until the work is complete and ready to merge back into the main progress log.

## Merge Note

This is a temporary phase-local progress log.
After Track B phases are completed or intentionally paused, merge the durable entries into `docs/rag-ingestion-progress.md` and keep this file as either an archive or remove it during the docs consolidation pass.

## Phase Status Board

| Phase | Status | Current Evidence | Next Action |
|---|---|---|---|
| B0 backend identity | `diagnostic_completed` | `reports/rag_text_backend_identity_report.json` has `b1_entry_allowed=true`, `blockers=[]`, READY TEXT `text_count=15`, and clean TEXT-filtered API probe | Use the fixed backend identity as B1/B2 diagnostic input |
| B1 gold v0 | `diagnostic_completed` | `eval/gold_queries_text_e2e_v0.csv` has 12 rows; `reports/rag_text_e2e_gold_validate_report.json` passed with live READY TEXT bindings | Run B2 retrieval-only diagnostic with TEXT filters |
| B2 retrieval diagnostic | `planned` | Phase plan created in `phase_b2_retrieval_diagnostic.md`; B1 validator passed | Run retrieval-only diagnostic after gold validation |
| B3 context assembly | `blocked_on_B2` | Phase plan created in `phase_b3_context_assembly.md` | Record prompt context selection after retrieval report exists |
| B4 LLM answer eval | `blocked_on_B3` | Phase plan created in `phase_b4_llm_answer_eval.md` | Run deterministic checks and optional judge after context report exists |
| B5 citation support | `blocked_on_B4` | Phase plan created in `phase_b5_citation_support.md` | Validate citation support at claim level after answer report exists |
| B6 summary/regression | `blocked_on_B5` | Phase plan created in `phase_b6_summary_regression.md` | Generate summary and compare against prior run if available |
| B7 scale/stabilize | `blocked_on_B6` | Phase plan created in `phase_b7_scale_and_stabilize.md` | Expand rows only after smoke pipeline is measurable |

## Status Vocabulary

Use these labels consistently.

| Status | Meaning |
|---|---|
| `planned` | Plan exists, implementation or evidence gathering has not started |
| `in_progress` | Current active phase |
| `blocked_on_Bx` | Waiting for a prior phase artifact |
| `diagnostic_completed` | Phase generated diagnostic artifacts but not promotion evidence |
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
| B1 gold v0 | `blocked_on_B0` | `diagnostic_completed` | `eval/gold_queries_text_e2e_v0.csv`, `reports/rag_text_e2e_gold_validate_report.json` |
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
  - `eval/gold_queries_text_e2e_v0.csv`
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

- Start B2 retrieval diagnostic using `eval/gold_queries_text_e2e_v0.csv` and the TEXT-only library-search filter.
