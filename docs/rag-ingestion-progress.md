# RAG Ingestion Progress

Last updated: 2026-05-19 KST.

This is the compact status index for the current RAG ingestion and official
answer/citation metric work. Do not append turn transcripts or create new
per-phase Markdown report pairs for routine status. The primary append-only
human report file is this file; when a report-style note is needed, append the
short entry here instead of creating another report. Human-facing rolling docs
are:

- `docs/rag-ingestion-progress.md`: current status, verification, guardrails.
- `docs/rag-ingestion-measurements.md`: run-level metrics and before/after
  summaries only when metric detail needs its existing ledger.
- `docs/rag-ingestion-triage.md`: row-level triage queue and decision boundary.

Use `ai/eval/reports/rag-ingestion/status.jsonl` only as a
compact machine-readable status event ledger. For run artifacts, write only the
minimal durable JSON/JSONL payloads needed by the run contract; full
`results.jsonl`, failure attribution, response audit, or per-run Markdown
outputs are reserved for behavior-changing runs or explicit forensic evidence
requirements.

## Current Status

Overall status: `official_answer_citation_v3_1_9_user_gold_policy_override_application_recorded`;
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
- v3_1_3 remaining-queue answer span / renderer triage
  `official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage`
  used the v3_1_2 machine remaining queue as source of truth:
  `gq_auto_010`, `gq_auto_024`, `gq_auto_030`, `gq_auto_043`,
  `gq_pdf_section_question_001`, `gq_xlsx_date_number_format_001`, and
  `text_namu_v2_0005`. This run changed only source-bound prompt answer
  instructions, answer rendering, and post-generation scorer compatibility
  normalization; it did not use expected answers, supporting evidence, gold
  fields, or candidate artifacts as generation source. Target Lane PASS changed
  from A/B/C=`7/7`, `3/7`, `0/7` to `7/7`, `5/7`, `5/7`. The 29-row
  all-track remeasurement changed Lane A/B/C PASS from `24/29`, `20/29`,
  `17/29` to `24/29`, `22/29`, `22/29`. Answer-span mismatches changed from
  Lane A/B/C=`0`, `9`, `12` to `0`, `7`, `7`. Strict JSON parse residual,
  LLM-generated locator copy/missing/field mismatch residual, PDF
  `source_pdf_path` mismatch, XLSX `row_label` mismatch, and TEXT
  `text_locator` missing all remain zero. Remaining queue is now
  `gq_auto_010` and `gq_pdf_section_question_001`.
- v3_1_4 PDF residual answer span / renderer triage
  `official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage`
  used the v3_1_3 machine remaining queue as source of truth and processed
  `gq_auto_010` plus `gq_pdf_section_question_001`. The only generation-facing
  change is a source-bound PDF table-axis renderer for repeated amount/growth
  columns; expected/supporting/gold/reference spans remain post-generation
  scoring/audit inputs only. Target Lane A/B/C PASS changed from `2/2`,
  `0/2`, `0/2` to `2/2`, `1/2`, `1/2`. The 29-row all-track remeasurement
  changed Lane A/B/C PASS from `24/29`, `22/29`, `22/29` to `24/29`,
  `23/29`, `23/29`. Answer-span mismatches changed from Lane A/B/C=`0`, `7`,
  `7` to `0`, `6`, `6`. Strict JSON parse residual, LLM-generated locator
  copy/missing/field mismatch residual, PDF `source_pdf_path` mismatch, XLSX
  `row_label` mismatch, and TEXT `text_locator` missing all remain zero.
  `gq_pdf_section_question_001` now PASSes B/C via source-bound table-axis
  disambiguation (`518.4`); `gq_auto_010` remains as retrieval/context
  insufficiency because the cited SearchUnit context lacks the numeric answer
  span.
- v3_1_5 source-bound retrieval/context coverage diagnostic
  `official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic`
  used the v3_1_4 machine remaining queue as source of truth and verified that
  the active residual is `gq_auto_010` only. This run is classification-only:
  no generation, renderer, scorer, SearchUnit export, index, denominator, gold,
  label, production, tuning, or promotion behavior changed. Lane A still passes
  through v3 primary replay; Lane B/C remain `LLM_EXPECTED_SPAN_MISMATCH` while
  citing SearchUnit `7bf516bf-2a17-4303-86d8-3cffaa04846e`. The cited
  paragraph supports the general unemployment-rise claim but does not contain
  the numeric answer span. Static source probing found the numeric span in raw
  PDF text extraction on the same source page, but not in the current cited
  SearchUnit, not in any same-document SearchUnit, and not in adjacent
  page/window SearchUnits in the current source-bound index. Final
  classification: `query_bound_searchunit_too_narrow`. No non-production
  export/index repair was applied, so no 29-row all-track remeasurement was
  necessary. Remaining queue stays `gq_auto_010`.
- v3_1_6 safe PDF paragraph/window expansion diagnostic
  `official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic`
  used the v3_1_5 machine remaining queue as source of truth and processed
  `gq_auto_010` only. This is a behavior-changing diagnostic branch, not answer
  renderer work, gold work, official retrieval metric work, or a promotion run.
  It added deterministic same-page source-bound PDF paragraph/window context
  before live generation using safe local PDF extraction, with locator-valid
  provenance: same `source_pdf_path`, same `document_version_id`, page `8`,
  physical page index `7`, bbox `[63.65, 95.06, 341.94, 163.68]`, region type
  `paragraph_window`, and deterministic expansion unit
  `pdfwin_b1c6527f848018640ad5ed231877c662`. Target Lane A/B/C PASS changed
  from `1/1`, `0/1`, `0/1` to `1/1`, `1/1`, `1/1`. Because prompt-context
  behavior changed, the 29-row all-track remeasurement was run; all-track Lane
  A/B/C PASS changed from `24/29`, `23/29`, `23/29` to `24/29`, `24/29`,
  `24/29`. Strict JSON parse, LLM-generated locator copy/missing/field
  mismatch, PDF `source_pdf_path`, XLSX `row_label`, and TEXT `text_locator`
  residual counts remain zero. No non-production index/export rebuild was
  applied. Remaining queue is empty.
- v3_1_7 post-residual queue closure audit
  `official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit`
  reconciles the empty v3_1_6 active queue with the 29-row all-track residual
  state. The active queue cleared, but all-track residual inventory still
  exists for five TEXT query ids: `text_namu_v2_0012`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0077`, and `text_namu_v2_0084`.
  Residual lane items=15: `gold_policy_review_candidate=15`,
  `answer_renderer_followup_candidate=15`, `scorer_normalization_review_candidate=3`,
  and `implementation_safe_followup=0`. A user-decision packet was created;
  no residual is safe to fix without a user gold/relevance/answerability
  policy decision. Recommended next phase:
  `gold_policy_review_packet_preparation`.
- v3_1_8 human gold-policy packet-preparation run
  `official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation`
  converts that recommendation into a compact human review packet for exactly
  five TEXT rows: `text_namu_v2_0012`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0077`, and `text_namu_v2_0084`.
  Decision options are `keep_current_strict_reference_boundary`,
  `approve_scorer_or_renderer_review_without_gold_mutation`, and
  `revise_gold_or_label_policy`. The active implementation queue remains empty:
  `implementation_safe_residual_count=0`, silver remains closed, and v3_1_6
  sibling-hash drift is recorded as metadata drift only, not fixed by rewriting
  historical artifacts.
- v3_1_8 is diagnostic-only and not promotion evidence: no behavior, gold, label, production, denominator, retrieval, scorer, renderer, silver, or promotion mutation occurred; no live all-track generation was rerun; no
  official nDCG/MRR/Hit@K was computed; and Lane A/B/C not collapsed. Raw
  expected/supporting/gold-policy material appears only in the human review
  packet with `human_review_only=true` and `generation_source=false`.
- v3_1_9 user-approved gold policy override application
  `official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement`
  applied `gold_overrides.csv` as the user-owned source of truth. This is a
  user-approved gold policy override application, not another diagnostic packet
  preparation run. five TEXT rows changed by user decision:
  `text_namu_v2_0012`, `text_namu_v2_0014`, `text_namu_v2_0017`,
  `text_namu_v2_0077`, and `text_namu_v2_0084`. The active gold file stays
  `gold_queries_text_namu_v2_1_question_gold_v2.csv`; the v2 CSV was updated
  in place because the current loader and registry contract still reference
  that path directly. Gold hash changed from
  `03764d1d7aa682cd8646d9028b6219fdbeba8a4eb219a87a285a162f16702cd6` to
  `0f9e24e68494b85ad6e4b85c84c1519a62dd596612c6bd269d58ca9017e1a4b4`.
- v3_1_9 scoring-only remeasurement reused existing Lane A/B/C answer surfaces;
  live generation was not rerun. `behavior_change_made=false`;
  renderer/scorer/retrieval/production/silver/promotion behavior changed: none.
  `expected_answer_mutation=true`, `supporting_evidence_mutation=true`,
  `gold_policy_mutation=true`, `user_policy_decision_applied=true`.
  scoring-only remeasurement changed Lane A/B/C PASS from `24/29`, `24/29`,
  `24/29` to `27/29`, `26/29`, `25/29`. no official nDCG/MRR/Hit@K was
  computed; Lane A/B/C not collapsed; `promotion_evidence=false`.
  Post-rescore remaining queue contains four implementation-safe TEXT query ids
  (`text_namu_v2_0014`, `text_namu_v2_0017`, `text_namu_v2_0077`,
  `text_namu_v2_0084`) across nine lane items. No additional user policy packet
  is required unless a concrete metadata conflict appears.
- v3_1_7 stayed diagnostic-only and not promotion evidence: no behavior changed,
  no live all-track generation was rerun, no production/denominator/gold/label
  mutation occurred, no official nDCG/MRR/Hit@K was computed, and
  Lane A/B/C not collapsed. The v3_1_6 PDF expansion unit remains
  `pdfwin_b1c6527f848018640ad5ed231877c662`.
- Answer/citation silver strategy is recorded in
  `ai/eval/silver/answer_citation_silver_manifest_v1.json`; readiness is
  `ai/eval/silver/answer_citation_silver_readiness_v1.json`. Its purpose is an
  anti-overfit generalization guard, and the policy is explicit: silver is not
  gold, not official denominator, not promotion evidence, and not used for
  generation. expected values are audit-only, candidate result rows are not
  silver generation source, and official 29 query_ids are excluded from
  dev/holdout tuning silver. Initial source-bound silver JSONL files were not
  created because safe source-bound answer/citation source manifests are still
  missing: TEXT=0, XLSX=0, PDF=0. The official-denominator source-bound index,
  build/load check, and canonical SearchUnit citation payload wiring are already
  available; silver generation stays closed until safe silver-source data
  coverage is settled.
- Current test surface is intentionally compact after legacy test deletion:
  `python -X utf8 -m pytest ai/tests --rag-current -q`; full `ai/tests`
  now mirrors the current profile and no longer carries broad/nightly legacy
  suites.
- Report cleanup keeps human-facing status in three rolling docs and treats
  `ai/eval/reports/rag-ingestion/` Markdown files as generated/local-only.
  Machine JSON/JSONL artifacts should be the smallest durable set needed for
  the phase; full forensic payloads are not routine outputs.

## Track Board

| Track | Current state | Current metric/evidence | Next action |
|---|---|---|---|
| `text_namu_v2_1` | v3_1_9 applied the user-approved gold policy override for five TEXT residual rows | Lane A/B/C after scoring-only remeasurement: `27/29`, `26/29`, `25/29`; remaining queue has 4 implementation-safe TEXT query ids / 9 lane items | Later implementation-safe renderer/scorer/prompt/retrieval work may inspect remaining residuals without reopening gold policy. |
| `xlsx_business_structured` | v3_1_3 improved remaining XLSX date rows through source-bound answer/scorer compatibility | target XLSX rows now PASS in Lane B/C; XLSX `row_label` mismatch=0 | Keep date/number compatibility general; do not tune thresholds. |
| `pdf_business_ocr_mm` | v3_1_6 applied safe same-page source-bound PDF paragraph/window context expansion for `gq_auto_010` | Target Lane B/C now PASS with locator-valid `pdfwin_b1c6527f848018640ad5ed231877c662`; all-track Lane B/C now `24/29`; residual strict JSON/locator counts stay `0` | Queue cleared; keep expansion guarded and do not broaden it. |
| Current tests | `--rag-current` profile isolates official metric, source-of-truth, candidate, and guardrail tests | Legacy `ai/tests/test_*.py` suites outside the current profile were deleted | Keep the compact profile green; extend existing files for routine diagnostic coverage. Create a new test file only for a durable new subsystem and update the keep-set in the same change. |
| Report artifacts | Classification-only, packet-preparation, and v3_1_9 policy-application phases use compact JSON/JSONL artifacts plus the status ledger | v3_1_9 creates only summary, applied overrides, gold diff, rescored results, remaining queue, and compact status event | Append human report notes to this progress file; do not create per-run Markdown or full forensic payloads unless behavior changes or a test-backed forensic contract requires them. |

## Current Verification Command

Windows/Python current env:

```powershell
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q
```

Current verification:
local results recorded in this progress log. Latest `--rag-current` verification
after the v3_1_9 updates: 145 passed, 0 skipped, 0 failed. Marker profile
`rag_current or rag_official_metric or rag_pdf_current`: 145 passed,
0 deselected, 0 failed.

Additional 2026-05-19 local verification for v3_1_9 user-approved gold policy
override application and scoring-only remeasurement:

- `python -X utf8 ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py --run-id official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement`: PASS; applied the user-approved override contract, wrote compact v3_1_9 artifacts, and appended `status.jsonl`.
- Targeted contract check:
  `python -X utf8 -m pytest ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_9_user_gold_policy_override_application_and_rescore_is_guarded ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_9_gold_csv_contains_only_the_user_approved_text_overrides ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_1_9_user_gold_policy_override_without_behavior_promotion -q`: PASS, 3 passed.
- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 145 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 145 passed.
- v3_1_9 mutation/guardrail summary:
  `run_class=user_approved_gold_policy_override_application`,
  `diagnostic_only=false`, `expected_answer_mutation=true`,
  `supporting_evidence_mutation=true`, `gold_policy_mutation=true`,
  `user_policy_decision_applied=true`, `behavior_change_made=false`,
  `renderer_mutation=false`, `scorer_behavior_mutation=false`,
  `retrieval_mutation=false`, `production_mutation=false`,
  `silver_rows_created=false`, `promotion_evidence=false`,
  `official_ndcg_computed=false`, `official_mrr_computed=false`,
  `official_hit_at_k_computed=false`, and `lane_score_collapsed=false`.

Additional 2026-05-19 local verification for v3_1_8 gold-policy review packet
preparation:

- `python -X utf8 ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py --run-id official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation`: PASS; wrote the v3_1_8 diagnostic-only summary, human review packet, decision matrix, empty remaining queue, and compact status event.
- `python -X utf8 -m pytest ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_8_gold_policy_packet_preparation_is_compact_and_guarded ai/tests/test_rag_diagnostic_status_sync.py::test_progress_doc_records_v3_1_8_gold_policy_packet_without_metric_promotion ai/tests/test_rag_current_focused_test_profile_v1.py::test_current_profile_includes_required_official_candidate_and_pdf_tests -q`: PASS, 3 passed.
- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 141 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 141 passed.
- v3_1_8 diagnostic-only confirmed: `diagnostic_only=true`,
  `promotion_evidence=false`, `behavior_change_made=false`,
  `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`,
  `expected_answer_mutation=false`, `supporting_evidence_mutation=false`,
  `relevance_label_mutation=false`, `answerability_label_mutation=false`,
  `candidate_artifacts_as_generation_source=false`,
  `generation_used_expected_answer=false`,
  `generation_used_supporting_evidence=false`,
  `generation_used_gold_fields=false`, `official_ndcg_computed=false`,
  `official_mrr_computed=false`, `official_hit_at_k_computed=false`, and
  `lane_score_collapsed=false`.

Additional 2026-05-18 local verification for v3_1_7 post-residual queue
closure and residual inventory audit:

- `python -X utf8 ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py --run-id official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit`: PASS; wrote the v3_1_7 diagnostic-only summary, residual inventory, remaining queue, user decision packet, silver readiness audit, and compact status event.
- `python -X utf8 -m pytest ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py -q`: PASS, 30 passed.
- `python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py ai/tests/test_rag_diagnostic_status_sync.py -q`: PASS, 8 passed.
- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 139 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 139 passed.
- v3_1_7 diagnostic-only confirmed: `diagnostic_only=true`,
  `promotion_evidence=false`, `behavior_change_made=false`,
  `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`,
  `expected_answer_mutation=false`, `supporting_evidence_mutation=false`,
  `relevance_label_mutation=false`, `answerability_label_mutation=false`,
  `candidate_artifacts_as_generation_source=false`,
  `generation_used_expected_answer=false`,
  `generation_used_supporting_evidence=false`,
  `generation_used_gold_fields=false`, `reference_span_text_embedded=false`,
  `official_ndcg_computed=false`, `official_mrr_computed=false`,
  `official_hit_at_k_computed=false`, and `lane_score_collapsed=false`.

Additional 2026-05-18 local verification for v3_1_5 `gq_auto_010`
source-bound retrieval/context coverage diagnostic:

- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 133 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 133 passed.
- `python -X utf8 -m py_compile ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py ai\tests\test_rag_official_metric_artifact_source_of_truth_audit_v1.py ai\tests\test_rag_current_focused_test_profile_v1.py`: PASS.
- `cd ai; python -m scripts.doctor --json --only schemas,faiss_index,build_json,runtime_model_match`: overall PASS; schemas, faiss_index, build_json, runtime_model_match PASS; capability_readiness WARN is present but not part of the selected checks.
- `git diff --check`: PASS with line-ending warnings only.
- Diagnostic-only confirmed for v3_1_5: `diagnostic_only=true`,
  `promotion_evidence=false`, `promotion_gate_auto_run=false`,
  `threshold_tuning=false`, `winner_selection=false`,
  `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`,
  `candidate_artifacts_as_generation_source=false`,
  `generation_used_expected_answer=false`,
  `generation_used_supporting_evidence=false`,
  `generation_used_gold_fields=false`, and
  `reference_span_text_embedded=false`.
- Metric guardrails confirmed: official nDCG, MRR, Hit@K, and collapsed Lane
  A/B/C score were not computed. No non-production index/export fix was
  applied, so no 29-row all-track remeasurement was necessary.

Additional 2026-05-18 local verification for v3_1_6 `gq_auto_010` safe PDF
paragraph/window expansion diagnostic:

- `python -X utf8 ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py --run-id official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic`: PASS; wrote the v3_1_6 behavior-changing diagnostic artifact set.
- `python -X utf8 -m pytest ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_1_6_gq_auto_010_pdf_paragraph_window_expansion_is_guarded -q`: PASS.
- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 134 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 134 passed.
- `python -X utf8 -m py_compile ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py ai\tests\test_rag_official_metric_artifact_source_of_truth_audit_v1.py ai\tests\test_rag_current_focused_test_profile_v1.py`: PASS.
- `cd ai; python -m scripts.doctor --json --only schemas,faiss_index,build_json,runtime_model_match`: overall PASS; schemas, faiss_index, build_json, runtime_model_match PASS; capability_readiness WARN is present but not part of the selected checks.
- `git diff --check`: PASS with line-ending warnings only.
- Diagnostic-only confirmed for v3_1_6: `diagnostic_only=true`,
  `promotion_evidence=false`, `promotion_gate_auto_run=false`,
  `threshold_tuning=false`, `winner_selection=false`,
  `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`,
  `candidate_artifacts_as_generation_source=false`,
  `generation_used_expected_answer=false`,
  `generation_used_supporting_evidence=false`,
  `generation_used_gold_fields=false`, and
  `reference_span_text_embedded=false`.
- Metric guardrails confirmed: official nDCG, MRR, Hit@K, and collapsed Lane
  A/B/C score were not computed. No production index and no non-production
  official denominator index/export were rebuilt.

Additional 2026-05-18 local verification for v3_1_4 PDF residual answer span /
renderer triage:

- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 132 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 132 passed.
- `python -X utf8 -m py_compile ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py ai\tests\test_rag_official_metric_artifact_source_of_truth_audit_v1.py ai\tests\test_rag_current_focused_test_profile_v1.py`: PASS.
- `cd ai; python -m scripts.doctor --json --only schemas,faiss_index,build_json,runtime_model_match`: overall PASS; schemas, faiss_index, build_json, runtime_model_match PASS; capability_readiness WARN is present but not part of the selected checks.
- `git diff --check`: PASS with line-ending warnings only.
- Diagnostic-only confirmed for v3_1_4: `diagnostic_only=true`,
  `promotion_evidence=false`, `promotion_gate_auto_run=false`,
  `threshold_tuning=false`, `winner_selection=false`,
  `candidate_artifacts_as_generation_source=false`,
  `generation_used_expected_answer=false`,
  `generation_used_gold_fields=false`,
  `generation_used_supporting_evidence=false`, and
  `reference_span_text_embedded=false`.

Additional 2026-05-18 local verification for v3_1_3 remaining-queue answer
span / renderer triage:

- `python -X utf8 -m pytest ai/tests --rag-current -q`: PASS, 131 passed.
- `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q`: PASS, 131 passed.
- `python -X utf8 -m py_compile ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py ai\tests\test_rag_official_metric_artifact_source_of_truth_audit_v1.py ai\tests\test_rag_current_focused_test_profile_v1.py`: PASS.
- `cd ai; python -m scripts.doctor --json --only schemas,faiss_index,build_json,runtime_model_match`: overall PASS; schemas, faiss_index, build_json, runtime_model_match PASS; capability_readiness WARN is present but not part of the selected checks.
- `git diff --check`: PASS with line-ending warnings only.
- Diagnostic-only confirmed for v3_1_3: `diagnostic_only=true`,
  `promotion_evidence=false`, `promotion_gate_auto_run=false`,
  `threshold_tuning=false`, `winner_selection=false`,
  `candidate_artifacts_as_generation_source=false`,
  `generation_used_expected_answer=false`,
  `generation_used_gold_fields=false`,
  `generation_used_supporting_evidence=false`, and
  `reference_span_text_embedded=false`.

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

- `v3_1_foundation_results.jsonl`: `5A871163121ABB4849B74CA2A33DD06757C84994C2E35064CDFF765F8562024D`
- `v3_1_foundation_summary.json`: `474B950C6289362A3BE33880B755FB2361EA98F0AAD9EFC3A6FEC2FE72AA8688`
- `v3_1_foundation_failure.json`: `51377761AC0BE5AD8AAD7EA89655366907A389E139573A7B547A4627B3E30C08`
- `v3_1_foundation_audit.jsonl`: `FC3E31C699C6791CECD4FE3E1B8B120C54C9B10FBA121FE967D4CEA84A493BBD`
- `v3_1_foundation_queue.json`: `9426CE189C04080290027EFC923F38E60E5BE58EB6FF65FE572A6EFCBE837380`

## Current Source-Of-Truth Artifacts

Human-facing rolling docs:

- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`

Machine-readable official artifacts:

Report-directory cleanup now keeps the repo-local surface compact. Active
machine artifacts stay under `ai/eval/reports/rag-ingestion/` only when a test
or runner contract still needs the local path. Historical generated/local-only
payloads are externalized under:

`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\repo-wide-cleanup-20260519\reports\rag-ingestion-legacy\`

Repo-local archive payloads are externalized under:

`D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260519-repo-wide-cleanup\files\archive\`

- `ai/eval/reports/rag-ingestion/baseline_v1.json`
- `ai/eval/reports/rag-ingestion/scorer_v1.jsonl`
- `ai/eval/reports/rag-ingestion/metric_input_v1.json`
- `ai/eval/reports/rag-ingestion/smoke_v1.json`
- `ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl`
- `ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl`
- `ai/eval/reports/rag-ingestion/v3_1_6_gq010_pdfwin_results.jsonl`
- `ai/eval/reports/rag-ingestion/v3_1_6_gq010_pdfwin_summary.json`
- `ai/eval/reports/rag-ingestion/v3_1_6_gq010_pdfwin_failure.json`
- `ai/eval/reports/rag-ingestion/v3_1_6_gq010_pdfwin_audit.jsonl`
- `ai/eval/reports/rag-ingestion/v3_1_6_gq010_pdfwin_spans.jsonl`
- `ai/eval/reports/rag-ingestion/v3_1_6_gq010_pdfwin_context.jsonl`
- `ai/eval/reports/rag-ingestion/v3_1_6_gq010_pdfwin_queue.json`
- `ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json`
- `ai/eval/reports/rag-ingestion/status.jsonl`
- `ai/eval/silver/answer_citation_silver_manifest_v1.json`
- `ai/eval/silver/answer_citation_silver_readiness_v1.json`

Per-run Markdown reports under `ai/eval/reports/rag-ingestion/` are no longer
the human-facing surface. The v3_1_2, v3_1_3, and v3_1_4 answer-span/renderer
triage runs intentionally created only machine JSON/JSONL artifacts. v3_1_5
uses the smaller classification-only set: summary JSON, compact coverage
diagnostics JSONL, remaining queue JSON, and one compact
`status.jsonl` event. v3_1_6 is behavior-changing because
prompt context assembly now admits a locator-safe source PDF expansion sidecar,
so it uses the full JSON/JSONL artifact family. The ongoing narrative stays in
the three rolling docs above.

### v3_1_2 Artifact Retention Classes

Current policy: do not delete diagnostic artifacts that are already referenced
by tests or rolling docs. Classify first, then reduce future classification-only
emission only after the test contract is updated in the same change.

| Artifact | Primary class | Retention note |
|---|---|---|
| `docs/rag-ingestion-progress.md` | `human_facing_source_of_truth` | Current status, verification, guardrails, and artifact policy. |
| `docs/rag-ingestion-measurements.md` | `human_facing_source_of_truth` | Measurement ledger and minimum artifact-set recommendation. |
| `docs/rag-ingestion-triage.md` | `human_facing_source_of_truth` | Queue decisions and row-level triage policy. |
| `ai/eval/reports/rag-ingestion/status.jsonl` | `compact_status_ledger` | Append-only machine status event ledger used for compact sync. |
| `...v3_1_2_answer_span_renderer_triage_summary.json` | `machine_manifest` | Run-level manifest, guardrails, source artifact identities, and hashes. |
| `...v3_1_2_answer_span_renderer_triage_results.jsonl` | `canonical_result_payload` | Full row/lane payload for reproducibility; current tests require it. |
| `...v3_1_2_answer_span_renderer_triage_failure_attribution.json` | `forensic_debug_payload` | Row attribution and taxonomy detail; current tests require guardrail coverage. |
| `...v3_1_2_answer_span_renderer_triage_actual_response_audit.jsonl` | `forensic_debug_payload` | Locator/strict-JSON/response audit; useful for regression forensics. |
| `...v3_1_2_answer_span_renderer_triage_answer_span_diagnostics.jsonl` | `canonical_result_payload` | Compact classification payload for answer span / renderer diagnostics. |
| `...v3_1_2_answer_span_renderer_triage_remaining_triage_queue.json` | `queue_source_of_truth` | Authoritative next queue after batch 1. |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_summary.json` | `machine_manifest` | Run-level manifest with target and all-track before/after metrics. |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_results.jsonl` | `canonical_result_payload` | Seven-row remaining-queue lane payload used by artifact tests. |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_failure_attribution.json` | `forensic_debug_payload` | Row attribution and guardrail coverage for changed renderer/scorer behavior. |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_actual_response_audit.jsonl` | `response_audit_payload` | Required because generation/renderer/scorer behavior changed. |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_answer_span_diagnostics.jsonl` | `compact_answer_span_diagnostic_payload` | Compact row/lane classification for the seven remaining rows. |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_remaining_triage_queue.json` | `queue_source_of_truth` | Authoritative queue after v3_1_3: `gq_auto_010`, `gq_pdf_section_question_001`. |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_summary.json` | `machine_manifest` | Run-level manifest with PDF residual target and all-track before/after metrics. |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_results.jsonl` | `canonical_result_payload` | Two-row PDF residual lane payload used by artifact tests. |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_failure_attribution.json` | `forensic_debug_payload` | Row attribution and guardrail coverage for changed PDF renderer behavior. |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_actual_response_audit.jsonl` | `response_audit_payload` | Required because generation/renderer behavior changed. |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_answer_span_diagnostics.jsonl` | `compact_answer_span_diagnostic_payload` | Compact row/lane classification for the two PDF residual rows. |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_remaining_triage_queue.json` | `queue_source_of_truth` | Authoritative queue after v3_1_4: `gq_auto_010`. |
| `...v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_summary.json` | `machine_manifest` | Classification-only source-bound coverage manifest with v3_1_4 queue preflight and guardrails. |
| `...v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_context_coverage_diagnostics.jsonl` | `compact_coverage_diagnostic_payload` | Static SearchUnit/raw-PDF span coverage probe for `gq_auto_010`; not an official retrieval metric. |
| `...v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_remaining_triage_queue.json` | `queue_source_of_truth` | Authoritative queue after v3_1_5: `gq_auto_010`. |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_summary.json` | `machine_manifest` | Behavior-changing diagnostic manifest with v3_1_5 queue preflight, target/all-track before/after, guardrails, and artifact hashes. |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_results.jsonl` | `canonical_result_payload` | One-row target lane payload showing Lane A/B/C PASS after safe source-bound expansion. |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_failure_attribution.json` | `forensic_debug_payload` | Row attribution and guardrail coverage for the behavior-changing diagnostic branch. |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_actual_response_audit.jsonl` | `response_audit_payload` | Required because generation prompt context behavior changed. |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_answer_span_diagnostics.jsonl` | `compact_answer_span_diagnostic_payload` | Compact target row/lane answer-span classification after expansion. |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_context_expansion_diagnostics.jsonl` | `compact_pdf_context_expansion_diagnostic_payload` | Expansion provenance, locator metadata, citation use, and audit-only span coverage. |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_remaining_triage_queue.json` | `queue_source_of_truth` | Authoritative queue after v3_1_6: empty. |
| `...v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_summary.json` | `machine_manifest` | Closure/inventory manifest showing active queue cleared while five TEXT all-track residuals remain. |
| `...v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_all_track_residual_inventory.jsonl` | `compact_residual_inventory_payload` | 15 lane residual items for the five TEXT query ids. |
| `...v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_remaining_triage_queue.json` | `queue_source_of_truth` | Empty implementation queue with policy-bound residuals carried separately. |
| `...v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_user_decision_packet.json` | `human_decision_packet_seed` | First policy-review seed packet without raw policy material. |
| `...v3_1_8_gold_policy_review_packet_preparation_summary.json` | `machine_manifest` | Diagnostic-only human packet preparation manifest. |
| `...v3_1_8_gold_policy_review_packet_preparation_human_review_packet.json` | `human_policy_review_packet` | Five TEXT policy-review items with generated answers, locators, and human-review-only policy material. |
| `...v3_1_8_gold_policy_review_packet_preparation_decision_matrix.jsonl` | `compact_decision_matrix_payload` | One row per policy-review query id with the three allowed user decision options. |
| `...v3_1_8_gold_policy_review_packet_preparation_remaining_triage_queue.json` | `queue_source_of_truth` | Empty implementation queue: `implementation_safe_residual_count=0`. |

For routine classification-only or packet-preparation runs like v3_1_5, v3_1_7,
and v3_1_8, the minimum durable set is a summary JSON, compact diagnostics or
decision payload, remaining queue JSON, and the compact status ledger. Full
`results.jsonl`, failure attribution JSON, and actual response audit JSONL
remain required for behavior-changing families but are not required for the
compact v3_1_8 packet-preparation run.

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
- v3_1_5 through v3_1_8 did not compute official nDCG, MRR, Hit@K, or any
  single collapsed Lane A/B/C score.

## Next Recommended Steps

1. The active implementation queue remains empty. The only open work is human
   policy review for the five TEXT rows in the v3_1_8 packet.
2. User decision options are `keep_current_strict_reference_boundary`,
   `approve_scorer_or_renderer_review_without_gold_mutation`, or
   `revise_gold_or_label_policy`; do not apply any option inside a diagnostic
   Codex run.
3. Do not create silver rows or change expected answers, supporting evidence,
   relevance labels, answerability labels, or gold policy unless the user makes
   that specific decision.
4. Keep v3_1 diagnostic-only. Do not treat Lane B/C PASS counts as promotion
   evidence and do not mix Lane A/B/C into a single official score.
5. Keep the compact `ai/tests` surface current; extend existing files for
   routine coverage and create a new test file only when a durable new subsystem
   needs one.
6. Keep report output compact. New phases should record only the necessary
   machine artifacts plus an appended entry in this progress file; avoid
   per-run Markdown and full forensic payloads unless the run contract
   explicitly needs them.

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
| 2026-05-18 | Recorded v3_1_3 remaining-queue answer span / renderer triage as diagnostic-only: target Lane B/C PASS improved to `5/7`, all-track Lane B/C PASS improved to `22/29`, strict JSON/locator residuals stayed `0`, and the remaining queue is `gq_auto_010`, `gq_pdf_section_question_001`. |
| 2026-05-18 | Recorded v3_1_4 PDF residual answer span / renderer triage as diagnostic-only: `gq_pdf_section_question_001` Lane B/C now PASS through source-bound PDF table-axis disambiguation, all-track Lane B/C PASS improved to `23/29`, residual strict JSON/locator counts stayed `0`, and the remaining queue is `gq_auto_010`. |
| 2026-05-18 | Recorded v3_1_5 `gq_auto_010` source-bound coverage diagnostic as classification-only: current cited/same-document/adjacent SearchUnits lack the audit numeric span, raw PDF extraction contains it, classification is `query_bound_searchunit_too_narrow`, no behavior/index/export change was applied, and the remaining queue stays `gq_auto_010`. |
| 2026-05-18 | Recorded v3_1_6 `gq_auto_010` safe source-bound PDF paragraph/window expansion diagnostic: target Lane B/C now PASS with locator-valid `pdfwin_b1c6527f848018640ad5ed231877c662`, all-track Lane B/C now `24/29`, residual strict JSON/locator counts remain `0`, no index/export/gold/label/production mutation was applied, and the remaining queue is empty. |
| 2026-05-18 | Cleaned the rag-ingestion report top level by moving 21 legacy generated/local-only diagnostic payloads into `ai/eval/reports/rag-ingestion/_archive/legacy/`; no payloads were deleted and the focused test contract resolves archived legacy files explicitly. |
| 2026-05-19 | Externalized repo-local archive payloads by file type: docs/code/provenance bundles moved under `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260519-repo-wide-cleanup\files\archive\`, generated reports/logs moved under `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\repo-wide-cleanup-20260519\reports\`, and future report-style notes stay appended here instead of creating per-run Markdown. |
