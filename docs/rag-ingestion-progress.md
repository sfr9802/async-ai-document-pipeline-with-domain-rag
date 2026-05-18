# RAG Ingestion Progress

Last updated: 2026-05-18 KST.

This is the compact status index for the current RAG ingestion and official
answer/citation metric work. Do not append turn transcripts or create new
per-phase Markdown report pairs for routine status. The human-facing report
surface is now three rolling files:

- `docs/rag-ingestion-progress.md`: current status, verification, guardrails.
- `docs/rag-ingestion-measurements.md`: run-level metrics and before/after
  summaries.
- `docs/rag-ingestion-triage.md`: row-level triage queue and decision boundary.

Use `ai/eval/reports/rag-ingestion/rag_current_eval_status.jsonl` only as a
compact machine-readable status event ledger.

## Current Status

Overall status: `official_answer_citation_v3_1_2_answer_span_renderer_triage_recorded`;
the prior gates `official_denominator_source_bound_index_build_ready_load_checked`
and `v3_comparable_live_measurement_completed` remain satisfied.

- Official first-run baseline is `status=BLOCKED_OR_PARTIAL` with
  `status_detail=SCORED_BASELINE_PARTIAL`,
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
- v3 comparable live measurement
  `official_answer_citation_agentic_loop_run_v3_comparable_live_measurement`
  remains diagnostic-only and separate from the immutable first-run baseline:
  rows=29, scored_count=29, PASS=24/29, PDF=4/4, XLSX=19/19, TEXT=1/6.
  PDF/XLSX primary answers are retained structured-adapter outputs; only TEXT
  6 rows use real local LLM synthesis, so v3 is all-track official measurement
  but not all-track LLM quality measurement.
- v3_1 all-track foundation measurement
  `official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement`
  is now recorded before silver-set creation or row-level failure tuning. It is
  diagnostic-only and not silver/gold/promotion evidence. Lane A replays v3
  primary policy; Lane B invokes live LLM on all 29 rows with source-bound
  retrieved top-k context; Lane C invokes live LLM on all 29 rows with
  query-bound SearchUnit context only. Lane B/C strict JSON now records
  LLM-generated `citation_locators`, so PDF bbox and XLSX cell locator handling
  is measured separately from adapter-retained payloads. Lane counts are:
  A PASS=24/29, B PASS=18/29, C PASS=20/29. The triage queue contains 12 rows
  and should be used for the next row-level failure work.
- v3_1 priority 1~5 strict JSON / locator copy triage
  `official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage`
  has been recorded as a diagnostic-only row-level rerun over five triage
  rows: `gq_pdf_section_question_001`, `text_namu_v2_0012`, `gq_auto_010`,
  `gq_auto_023`, and `gq_xlsx_lookup_008`. It uses only source-bound SearchUnit
  context for generation, keeps expected answers/supporting evidence/gold fields
  out of generation, and leaves silver/gold/promotion/tuning untouched. Results:
  strict JSON parse failure `2 -> 0`, with schema repair applications tracked
  separately as `0 -> 2`. LLM-generated locator copy failure is `5 -> 1` when
  missing locator fields are counted, while field mismatches alone are `3 -> 0`.
  PDF `source_pdf_path` mismatch is `1 -> 0`, and XLSX `row_label` mismatch is
  `2 -> 0`. `answer_score` and `citation_support_score` are reference only.
  Locator metrics now distinguish
  `posthoc_payload_locator_preservation_failure_count` from
  `llm_generated_locator_copy_failure_count`.
- v3_1 TEXT locator residual triage
  `official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage`
  removed the remaining `text_namu_v2_0012` TEXT locator residual:
  `text_locator` missing `1 -> 0`, LLM-generated locator missing failure
  `1 -> 0`, and `text_locator` byte-equal / normalized-equal are both true.
  The repair uses only source-bound canonical locator JSON and does not use
  expected answers, supporting evidence, or gold fields for generation.
- v3_1_1 post strict JSON / locator triage all-track measurement
  `official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage`
  reran all 29 official denominator rows with the same Lane A/B/C definitions.
  Results: Lane A PASS=24/29, Lane B PASS=20/29, Lane C PASS=17/29. Lane B/C
  strict JSON parse failure, LLM-generated locator copy failure, PDF
  `source_pdf_path` mismatch, XLSX `row_label` mismatch, and TEXT
  `text_locator` missing are all zero. Remaining failures are answer span /
  answer renderer oriented. Four existing v3_1 PASS query/lane cases are
  recorded as answer-span regressions for diagnostic follow-up.
- v3_1_2 answer span / renderer triage
  `official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage`
  recorded the first diagnostic-only TEXT batch from the machine
  v3_1_1 triage queue artifact. The selected first batch is
  `text_namu_v2_0012`, `text_namu_v2_0014`, `text_namu_v2_0017`,
  `text_namu_v2_0077`, and `text_namu_v2_0084`; `text_namu_v2_0005`
  is included only as a secondary TEXT watchlist row because the machine queue
  places it at priority 12 and its failure is Lane C-only. This run does not
  invoke generation or change renderer/scorer behavior, so the 29-row
  v3_1_1 all-track reference remains Lane A PASS=24/29, Lane B PASS=20/29,
  Lane C PASS=17/29. Target-batch lane counts are Lane A PASS=1/6,
  Lane B PASS=1/6, Lane C PASS=0/6. Strict JSON parse failure,
  LLM-generated locator copy failure, PDF `source_pdf_path` mismatch, XLSX
  `row_label` mismatch, and TEXT `text_locator` missing all remain zero in the
  source post-triage reference.
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
- Report cleanup keeps human-facing status in three rolling docs and treats
  `ai/eval/reports/rag-ingestion/` Markdown files as generated/local-only.
  Machine JSON/JSONL artifacts remain available for reproducibility and tests.

## Track Board

| Track | Current state | Current metric/evidence | Next action |
|---|---|---|---|
| `text_namu_v2_1` | v3_1_2 first answer-span batch recorded; target Lane A PASS=1/6, Lane B PASS=1/6, Lane C PASS=0/6 | strict JSON parse failure=0, TEXT `text_locator` missing=0, and first five TEXT queue rows classified as answer span / renderer diagnostics | Keep `text_namu_v2_0005` as secondary watchlist; continue remaining queue without gold changes. |
| `xlsx_business_structured` | post-triage Lane A PASS=19/19; Lane B PASS=17/19; Lane C PASS=17/19 | XLSX `row_label` mismatch=0 and locator copy failure=0 | Continue date/number/span normalization triage only after preserving locator metrics. |
| `pdf_business_ocr_mm` | post-triage Lane A PASS=4/4; Lane B PASS=2/4; Lane C PASS=0/4 | PDF `source_pdf_path` mismatch=0 and locator copy failure=0 | Continue PDF answer-span triage separately from locator-copy stability. |
| Current tests | `--rag-current` profile isolates official metric, source-of-truth, candidate, and guardrail tests | Legacy `ai/tests/test_*.py` suites outside the current profile were deleted | Keep the compact profile green; recreate deleted legacy tests only when a new task needs them. |

## Current Verification Command

Windows/Python current env:

```powershell
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q
```

Current verification:
local results recorded in this progress log.
`--rag-current` 130 passed, 0 skipped, 0 failed.
Marker profile
`rag_current or rag_official_metric or rag_pdf_current`: 130 passed,
0 deselected, 0 failed.

Additional 2026-05-18 local verification for v3_1_2 answer span / renderer
triage:

- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 130 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 130 passed.
- `python -X utf8 -m py_compile ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py ai\tests\test_rag_diagnostic_guardrail_git_diff.py ai\tests\test_rag_diagnostic_status_sync.py ai\tests\test_rag_official_answer_citation_metric_first_run_v1.py ai\tests\test_rag_official_metric_artifact_source_of_truth_audit_v1.py ai\tests\test_rag_source_bound_official_denominator_index.py`: PASS.
- `cd ai; python -m scripts.doctor --json --only schemas,faiss_index,build_json,runtime_model_match`: overall PASS; schemas, faiss_index, build_json, runtime_model_match PASS; capability_readiness WARN is present but not part of the selected checks.
- `git diff --check`: PASS with line-ending warnings only.
- Diagnostic-only confirmed for the v3_1_2 answer-span/renderer triage:
  `diagnostic_only=true`, `promotion_evidence=false`,
  `promotion_gate_auto_run=false`, `threshold_tuning=false`,
  `winner_selection=false`, `generation_used_expected_answer=false`,
  `generation_used_gold_fields=false`,
  `generation_used_supporting_evidence=false`, strict JSON residual maps are
  zero, locator residual maps are zero, and reference span text is not embedded
  as a generation source.

Additional 2026-05-18 local verification for v3_1 TEXT locator residual and
v3_1_1 post strict JSON / locator triage:

- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 129 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 129 passed.
- `python -X utf8 -m py_compile ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py ai\tests\test_rag_diagnostic_guardrail_git_diff.py ai\tests\test_rag_diagnostic_status_sync.py ai\tests\test_rag_official_answer_citation_metric_first_run_v1.py ai\tests\test_rag_official_metric_artifact_source_of_truth_audit_v1.py ai\tests\test_rag_source_bound_official_denominator_index.py`: PASS.
- `cd ai; python -m scripts.doctor --json --only schemas,faiss_index,build_json,runtime_model_match`: overall PASS; schemas, faiss_index, build_json, runtime_model_match PASS; capability_readiness WARN is present but not part of the selected checks.
- `git diff --check`: PASS.
- Diagnostic-only confirmed for the TEXT residual and post-triage all-track
  runs: `diagnostic_only=true`, `promotion_evidence=false`,
  `promotion_gate_auto_run=false`, `threshold_tuning=false`,
  `winner_selection=false`, `generation_used_expected_answer=false`,
  `generation_used_gold_fields=false`, and
  `generation_used_supporting_evidence=false`.

Additional 2026-05-18 local verification for v3_1 priority 1~5 strict JSON /
locator-copy triage:

- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 127 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 127 passed.
- `python -X utf8 -m py_compile ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py ai\tests\test_rag_diagnostic_guardrail_git_diff.py ai\tests\test_rag_diagnostic_status_sync.py ai\tests\test_rag_official_answer_citation_metric_first_run_v1.py ai\tests\test_rag_official_metric_artifact_source_of_truth_audit_v1.py ai\tests\test_rag_source_bound_official_denominator_index.py`: PASS.
- `cd ai; python -m scripts.doctor --json --only schemas,faiss_index,build_json,runtime_model_match`: overall PASS; schemas, faiss_index, build_json, runtime_model_match PASS; capability_readiness WARN is present but not part of the selected checks.
- `git diff --check`: PASS with line-ending warnings only.
- Diagnostic-only confirmed for the priority run: `diagnostic_only=true`,
  `promotion_evidence=false`, `promotion_gate_auto_run=false`,
  `threshold_tuning=false`, `winner_selection=false`,
  `generation_used_expected_answer=false`, `generation_used_gold_fields=false`,
  and `generation_used_supporting_evidence=false`.

Additional 2026-05-18 local verification for v3_1 all-track foundation
measurement:

- `python -X utf8 -m py_compile ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py ai\tests\test_rag_official_metric_artifact_source_of_truth_audit_v1.py ai\tests\test_rag_current_focused_test_profile_v1.py ai\tests\test_rag_source_bound_official_denominator_index.py`: PASS.
- `cd ai; python -m scripts.doctor --json --only schemas,faiss_index,build_json,runtime_model_match`: overall PASS; schemas, faiss_index, build_json, runtime_model_match PASS; capability_readiness WARN is present but not part of the requested failing checks.
- `git diff --check`: PASS with line-ending warnings only.
- Diagnostic-only confirmed: `promotion_evidence=false`, `threshold_tuning=false`,
  `winner_selection=false`, `promotion_gate_auto_run=false`,
  `candidate_artifacts_as_generation_source=false`,
  `generation_used_expected_answer=false`, `generation_used_gold_fields=false`,
  and `generation_used_supporting_evidence=false`.

v3_1 machine artifact sha256:

- `official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_results.jsonl`: `5A871163121ABB4849B74CA2A33DD06757C84994C2E35064CDFF765F8562024D`
- `official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_summary.json`: `474B950C6289362A3BE33880B755FB2361EA98F0AAD9EFC3A6FEC2FE72AA8688`
- `official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_failure_attribution.json`: `51377761AC0BE5AD8AAD7EA89655366907A389E139573A7B547A4627B3E30C08`
- `official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_actual_response_audit.jsonl`: `FC3E31C699C6791CECD4FE3E1B8B120C54C9B10FBA121FE967D4CEA84A493BBD`
- `official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_triage_queue.json`: `9426CE189C04080290027EFC923F38E60E5BE58EB6FF65FE572A6EFCBE837380`

## Current Source-Of-Truth Artifacts

Human-facing rolling docs:

- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`

Machine-readable official artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_metric_first_run_v1.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_scorer_results_v1.jsonl`
- `ai/eval/reports/rag-ingestion/official_metric_input_config_v1.json`
- `ai/eval/reports/rag-ingestion/official_metric_pre_execution_smoke_report_v1.json`
- `ai/eval/reports/rag-ingestion/xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl`
- `ai/eval/reports/rag-ingestion/pdf_answer_citation_table_value_candidate_results_v1.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v1_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_comparable_live_measurement_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_comparable_live_measurement_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_comparable_live_measurement_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_actual_response_audit.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_triage_queue.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_actual_response_audit.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_triage_delta.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_triage_strict_json_diagnostics.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage_triage_delta.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage_actual_response_audit.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage_triage_queue.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_actual_response_audit.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_answer_span_diagnostics.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_remaining_triage_queue.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_source_bound_index_build_readiness_v1.json`
- `ai/eval/reports/rag-ingestion/rag_current_eval_status.jsonl`
- `ai/eval/silver/answer_citation_silver_manifest_v1.json`
- `ai/eval/silver/answer_citation_silver_readiness_v1.json`

Per-run Markdown reports under `ai/eval/reports/rag-ingestion/` are no longer
the human-facing surface. The v3_1_2 answer-span/renderer triage intentionally
created only machine JSON/JSONL artifacts and keeps the ongoing narrative in
the three rolling docs above.

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

1. Continue from the v3_1_2 remaining queue in
   `docs/rag-ingestion-triage.md`; strict JSON / locator-copy diagnostics are
   cleared and the active queue is answer span / answer renderer cases.
2. Keep v3_1 diagnostic-only. Do not treat Lane B/C PASS counts as promotion
   evidence and do not mix Lane A/B/C into a single official score.
3. Do not create silver rows or change expected answers, supporting evidence,
   relevance labels, answerability labels, or gold policy unless the user makes
   that specific decision.
4. If a future run reintroduces infrastructure/schema/citation payload issues,
   move them back to the top; otherwise continue with `gq_auto_010`,
   `gq_auto_024`, `gq_auto_030`, `gq_auto_043`,
   `gq_pdf_section_question_001`, `gq_xlsx_date_number_format_001`, and the
   secondary TEXT watchlist row `text_namu_v2_0005`.
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
| 2026-05-18 | Regenerated `official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement` with LLM-generated `citation_locators`: 29 rows, Lane A PASS=24/29, Lane B PASS=18/29, Lane C PASS=20/29, all guardrails false for promotion/tuning/gold/silver mutation, actual-response audit and 12-row triage queue recorded. |
| 2026-05-18 | Recorded priority 1~5 strict JSON / locator-copy triage as diagnostic-only: target rows=5, strict JSON parse failure 2->0 with schema repair 0->2, LLM-generated locator copy failure 5->1, field mismatch 3->0, PDF `source_pdf_path` mismatch 1->0, XLSX `row_label` mismatch 2->0, no expected/supporting/gold generation source and no silver/gold/promotion/tuning mutation. |
| 2026-05-18 | Consolidated human-facing rag-ingestion reports into three rolling docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md`; per-run Markdown under `ai/eval/reports/rag-ingestion/` is generated/local-only. |
| 2026-05-18 | Recorded v3_1_2 answer span / renderer triage as diagnostic-only: machine v3_1_1 queue selected the first five TEXT rows, `text_namu_v2_0005` stayed secondary at queue rank 12, no generation was invoked, and no expected/supporting/gold fields were used as generation source. |
