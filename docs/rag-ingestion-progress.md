# RAG Ingestion Progress

Last updated: 2026-05-17 KST.

This is the compact status index for the current RAG ingestion and official
answer/citation metric work. Do not append turn transcripts or create new
per-phase `*_v1.json` / `*_v1.md` report pairs for routine status. Use this
file for human-readable status and
`ai/eval/reports/rag-ingestion/rag_current_eval_status.jsonl` for compact
current status events.

## Current Status

Overall status: `official_answer_citation_v2_source_bound_diagnostic_recorded`;
the prior gate `official_denominator_source_bound_index_build_ready_load_checked`
remains satisfied.

- Official first-run baseline is `SCORED_BASELINE_PARTIAL` with
  `official_metric_execution_started=true`, `official_scoring_attempt_count=29`,
  `scored_count=29`, PASS=8, CITATION_UNSUPPORTED=11,
  PARTIAL_OR_UNSUPPORTED=10.
- XLSX runtime candidate is report-only and deterministic: PASS=26/29,
  XLSX=19/19, local LLM/GPU used=false.
- PDF table/value candidate now has official-compatible source-bound locators for
  `gq_auto_010`, `gq_auto_030`, and `gq_pdf_section_question_001`; report-only,
  no promotion, PASS=29/29, and it does not overwrite the official first-run
  baseline or XLSX runtime candidate results.
- Next measurement run `official_answer_citation_agentic_loop_run_v1` is a
  separate diagnostic live-generation artifact family. `ai/eval/indexes/rag-data` was
  rebuilt in WSL2 with Python 3.12, CUDA PyTorch, and CUDA FAISS using
  `AIPIPELINE_WORKER_RAG_FAISS_BUILD_DEVICE=cuda`; embedding ran on `cuda:0`,
  build.json records `faiss_gpu_used=true`, and the agentic loop executed live
  generation. Result rows=29, unique_query_ids=29, scored_count=29, PASS=1,
  CITATION_UNSUPPORTED=25, PARTIAL_OR_UNSUPPORTED=3, promotion_evidence=false.
- Row-level failure attribution for `official_answer_citation_agentic_loop_run_v1`
  classifies PASS=1/29 as
  `diagnostic_live_generation_fixture_all_index_not_official_denominator_representative`,
  not final comparable model-quality performance: primary attribution counts are
  CORPUS_COVERAGE_MISS=6, STRUCTURED_ADAPTER_NOT_WIRED=22, and
  SCORER_COMPATIBILITY_MISMATCH=1; the run used `llm_backend=noop` with
  extractive snippet generation and chunk-only citation locators that are
  not canonical SearchUnit payloads. `baseline_comparison_is_model_quality_comparable=false`.
- source-bound official-denominator SearchUnit export/build is now unblocked
  and load-checked for the non-production target
  `ai/eval/indexes/rag-data-official-denominator-v1`. The readiness artifact is
  `BUILD_READY_LOAD_CHECK_PASSED`: blocked_query_ids=[], missing fields/sources
  are empty, target_index_built=true, load_check_passed=true, and
  rerun_allowed=true. The built index contains `faiss.index`, `build.json`,
  `ingest_manifest.json`, and `search_unit_manifest.jsonl` with 29/29 official
  rows and track counts PDF=4, TEXT=6, XLSX=19.
- SearchUnit citation payload wiring is implemented in the live runner, and
  XLSX/PDF deterministic adapter opt-in wiring is implemented for retrieved
  source-bound SearchUnits. These are wiring changes only: the historical v1 run
  is still fixture-all/noop/chunk-only diagnostic output, report-only candidate
  artifacts are not generation source, and no candidate result is promoted.
- Diagnostic v2
  `official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic` is a
  separate run id and uses only
  `ai/eval/indexes/rag-data-official-denominator-v1`. Preflight passed with no
  stale readiness artifact: result rows=29, unique_query_ids=29,
  scored_count=20, PASS=20, fail-closed=9. Failure attribution is
  CITATION_PAYLOAD_SCHEMA_MISMATCH=9 and PASS=20. The run is diagnostic-only
  with `llm_backend=noop`, `source_bound_index_used=true`,
  `canonical_search_unit_payload_used=true`,
  `adapter_output_from_source_bound_search_units=false`,
  `candidate_artifacts_as_generation_source=false`,
  `generation_used_expected_answer=false`,
  `generation_used_supporting_evidence=false`,
  `generation_used_gold_fields=false`, `promotion_evidence=false`, and
  `baseline_comparison_is_model_quality_comparable=false`.
- Answer/citation silver strategy is recorded in
  `ai/eval/silver/answer_citation_silver_manifest_v1.json`; readiness is
  `ai/eval/silver/answer_citation_silver_readiness_v1.json`. Its purpose is an
  anti-overfit generalization guard, and the policy is explicit: silver is not
  gold, not official denominator, not promotion evidence, and not used for
  generation. expected values are audit-only, candidate result rows are not
  silver generation source, and official 29 query_ids are excluded from
  dev/holdout tuning silver. Initial source-bound silver JSONL files were not
  created because safe source-bound answer/citation source manifests are still
  missing: TEXT=0, XLSX=0, PDF=0. Next step remains source-bound SearchUnit
  export/build and canonical SearchUnit citation payload wiring backed by safe
  source manifests.
- Current test surface is intentionally compact after legacy test deletion:
  `python -X utf8 -m pytest ai/tests --rag-current -q`; full `ai/tests`
  now mirrors the current profile and no longer carries broad/nightly legacy
  suites.
- Hard cleanup kept only the previous 8 source-of-truth/current files in
  `ai/eval/reports/rag-ingestion/`; the explicitly approved next measurement
  adds 4 current run artifacts under the new run id. Historical report/doc
  artifacts were moved to `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\hard-cleanup-20260517`.

## Track Board

| Track | Current state | Current metric/evidence | Next action |
|---|---|---|---|
| `text_namu_v2_1` | Official baseline PASS=6/6; source-bound readiness resolves all 6 from corpus chunks | Source-bound manifest rows=6/6 | Preserve baseline pass state; no TEXT blocker remains. |
| `xlsx_business_structured` | XLSX runtime candidate report-only PASS=19/19; source-bound readiness resolves all 19 from source workbooks | Source-bound manifest rows=19/19 | Keep candidate artifacts report-only; no XLSX blocker remains. |
| `pdf_business_ocr_mm` | PDF source fields now resolve from original PDFs/native text with PaddleOCR reserved as OCR fallback | Source-bound manifest rows=4/4; diagnostic v2 fail-closed on citation payload schema mismatch | Inspect track-mixed top-k and scorer-compatible locator filtering before any comparable rerun. |
| Current tests | `--rag-current` profile isolates official metric, source-of-truth, candidate, and guardrail tests | Legacy `ai/tests/test_*.py` suites outside the current profile were deleted | Keep the compact profile green; recreate deleted legacy tests only when a new task needs them. |

## Current Verification Command

Windows/Python current env:

```powershell
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q
```

Current verification: `--rag-current` 101 passed, 0 skipped, 0 failed.
Marker profile
`rag_current or rag_official_metric or rag_pdf_current`: 101 passed,
0 deselected, 0 failed.

## Current Source-Of-Truth Artifacts

Canonical official artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_metric_first_run_v1.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_metric_first_run_v1.md`
- `ai/eval/reports/rag-ingestion/official_answer_citation_scorer_results_v1.jsonl`
- `ai/eval/reports/rag-ingestion/official_metric_input_config_v1.json`
- `ai/eval/reports/rag-ingestion/official_metric_pre_execution_smoke_report_v1.json`

Current compact candidate/status artifacts:

- `ai/eval/reports/rag-ingestion/xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl`
- `ai/eval/reports/rag-ingestion/pdf_answer_citation_table_value_candidate_results_v1.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_summary.md`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic_summary.md`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_source_bound_index_build_readiness_v1.json`
- `ai/eval/reports/rag-ingestion/rag_current_eval_status.jsonl`
- `ai/eval/silver/answer_citation_silver_manifest_v1.json`
- `ai/eval/silver/answer_citation_silver_readiness_v1.json`

The pre-execution smoke report is a pre-execution artifact, so
`official_metric_execution_started=false` there is expected and must not be read
as the latest metric execution status.

## Guardrails

- `tuning_run_started=false`
- `promotion_evidence=false`
- `threshold_tuning=false`
- `winner_selection=false`
- `production_mutation=false`
- `denominator_mutation=false`
- `gold_mutation=false`
- Expected answer and supporting evidence are not used for generation.
- Silver expected values are audit-only and silver cases must not be used as
  generation input.
- Official 29 query_ids are excluded from dev/holdout tuning silver.
- Gold CSVs, official denominator registry, human labels, production namespace,
  vector indexes, and immutable first-run baseline artifacts remain protected.

## Next Recommended Steps

1. Inspect the diagnostic v2 failure attribution at query/track/stage level:
   PDF and most TEXT rows fail closed on citation payload schema mismatch, while
   XLSX rows pass through the source-bound adapter path.
2. Keep v2 as diagnostic-only until a real LLM backend and comparable setup are
   validated; do not compare the 20 PASS result to the immutable first-run
   baseline as model quality.
3. Keep XLSX/PDF runtime candidates report-only; do not use their PASS=29/29
   observation as the immutable baseline or promotion evidence.
4. Create track-specific dev/holdout/contract silver JSONL only after safe
   source-bound source manifests provide required TEXT, XLSX, and PDF locator
   fields without using official 29 query_ids or report-only candidate rows as
   generation source.
5. Keep the compact `ai/tests` surface current; recreate legacy coverage only
   when an active task needs a fresh, source-grounded test.

## Short History

| Date | Compact entry |
|---|---|
| 2026-05-16 | Historical first-run attempt was blocked with `SCORER_BACKEND_UNAVAILABLE`; the active first-run artifacts were later regenerated and this state is superseded. |
| 2026-05-17 | Official first-run baseline scored 29/29 rows and remained partial: PASS=8, CITATION_UNSUPPORTED=11, PARTIAL_OR_UNSUPPORTED=10. |
| 2026-05-17 | XLSX runtime candidate reached PASS=26/29 and XLSX=19/19, report-only and deterministic. |
| 2026-05-17 | PDF table/value candidate reached PASS=29/29, report-only and deterministic, without baseline/gold/denominator/production mutation. |
| 2026-05-17 | Current focused test profile established for official metric/candidate/guardrail work. |
| 2026-05-17 | Hard cleanup reduced `ai/eval/reports/rag-ingestion/` to 8 current files and externalized 63 historical report/doc artifacts; use the current verification section for the latest focused-profile count. |
| 2026-05-17 | Opened `official_answer_citation_agentic_loop_run_v1` as a separate measurement artifact family; denominator validation passed, agentic loop was enabled, and the run failed closed before generation because `eval/indexes/rag-data` is unavailable. |
| 2026-05-17 | Rebuilt `ai/eval/indexes/rag-data` in WSL2 Python 3.12 with CUDA PyTorch and CUDA FAISS; reran `official_answer_citation_agentic_loop_run_v1` live generation: rows=29, scored_count=29, PASS=1, promotion_evidence=false. |
| 2026-05-17 | Added row-level failure attribution for `official_answer_citation_agentic_loop_run_v1`: current PASS=1/29 is diagnostic under fixture-all/noop/extractive limitations, with primary counts CORPUS_COVERAGE_MISS=6, STRUCTURED_ADAPTER_NOT_WIRED=22, SCORER_COMPATIBILITY_MISMATCH=1. |
| 2026-05-17 | Fixed semantic drift: the agentic-loop run is diagnostic, baseline comparison is not model-quality comparable, and rerun is blocked until a source-bound official-denominator non-production SearchUnit index build path exists. |
| 2026-05-17 | Implemented fail-closed source-bound official-denominator SearchUnit readiness entrypoint plus canonical citation payload and XLSX/PDF adapter opt-in wiring; build/rerun remain blocked by missing source-bound fields for 29/29 rows. |
| 2026-05-17 | Added answer/citation silver manifest/readiness for anti-overfit generalization monitoring; dev/holdout/contract JSONL creation is blocked until safe source-bound source data exists, with TEXT=0, XLSX=0, PDF=0. |
| 2026-05-17 | Rechecked source-bound official denominator readiness against repo source roots, `local-storage`, `D:\_external_runtime_artifacts`, and `D:\_external_workspace_archive`: TEXT 6/6 and XLSX 19/19 resolve from source artifacts, PDF 4/4 resolve source PDF path/document version/page/bbox/SearchUnit from safe locator manifests, and build/rerun remain fail-closed only on PDF `row_label`/`target_column`. |
| 2026-05-17 | Built and load-checked the non-production source-bound official-denominator index at `ai/eval/indexes/rag-data-official-denominator-v1`: 29/29 rows, PDF=4, TEXT=6, XLSX=19, `rerun_allowed=true`; no baseline/gold/denominator/human-label/production mutation. |
| 2026-05-17 | Ran `official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic` against only the source-bound official-denominator index: rows=29, scored_count=20, PASS=20, fail-closed schema mismatches=9, diagnostic-only, no candidate/gold/expected/supporting generation source and no promotion evidence. |
| 2026-05-17 | Deleted legacy `ai/tests/test_*.py` suites outside the current profile; full `ai/tests` now mirrors the compact RAG official metric/candidate/guardrail surface. |
