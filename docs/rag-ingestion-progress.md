# RAG Ingestion Progress

Last updated: 2026-05-21 KST.

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

Use `ai/eval/reports/rag-ingestion/status.jsonl` only as a compact
machine-readable status event ledger. For run artifacts, write only the minimal
durable JSON/JSONL payloads needed by the run contract; full `results.jsonl`,
failure attribution, response audit, or per-run Markdown outputs are reserved
for behavior-changing runs or explicit forensic evidence requirements.

## Current Status

Overall status: `diagnostic_source_registry_backed_retrieval_smoke_v3_7_2_report_done`;
the prior gates `official_denominator_source_bound_index_build_ready_load_checked`
and `v3_comparable_live_measurement_completed` remain satisfied. The v3_2
post-fix sequence is closed, the official answer/citation implementation queue
is empty, and current work remains source-first contract separation:
SearchViews are retrieval candidates, SourceAtoms/EvidenceBundles own hydrated
evidence, and v3_7_2 has regenerated the inherited diagnostic silver query
surface with local LLM natural Korean queries, then produced the
source registry-backed retrieval smoke report without opening promotion or
comparable live measurement.




<!-- official_answer_citation_agentic_loop_run_v3_7_2_local_llm_natural_silver_query_regeneration:progress-entry:start -->
- v3_7_2 local LLM natural silver query regeneration (`official_answer_citation_agentic_loop_run_v3_7_2_local_llm_natural_silver_query_regeneration`) supersedes/discards the inherited v3_6_1 scripted weak/noisy silver query text and regenerates 1000 diagnostic query strings with local `gemma4-e2b-local` through llama.cpp. Source and bucket metadata remain inherited from the frozen v3_5_4/v3_6 diagnostic lane: candidates=1000, unique ids=1000, unique generated question hashes=1000, TEXT=350, PDF=325, XLSX=325; manifests all=1000, core=665, review-only=335, quarantine=0. A second local LLM polish pass rewrote XLSX=325 rows to remove spreadsheet-internal query surfaces; validation found no Latin/Japanese/Hanja script or disallowed punctuation violations, no duplicate generated query hashes, and exact reuse of prior query text is 0. Remaining repeated prefixes are domain-heavy rather than sheet/range templates, so this remains diagnostic silver rather than human gold. No gold/qrels/label/expected-answer/supporting-evidence mutation, retrieval metric, answer metric, citation metric, DB write, production change, prompt/scorer tuning, or promotion was performed.
<!-- official_answer_citation_agentic_loop_run_v3_7_2_local_llm_natural_silver_query_regeneration:progress-entry:end -->


<!-- official_answer_citation_agentic_loop_run_v3_7_0_source_registry_materialization:progress-entry:start -->
- v3_7_0 source registry materialization (`official_answer_citation_agentic_loop_run_v3_7_0_source_registry_materialization`) materializes 136280 non-production SourceAtoms from existing source data with TEXT=135608, PDF=329, XLSX=343. No production DB, DB write/migration, vector index build, prompt/scorer tuning, gold/qrels/label/expected-answer/supporting-evidence mutation, retrieval metric, answer metric, or citation metric was performed. outcome=SOURCE_REGISTRY_MATERIALIZED_READY; next_allowed_phase=v3_7_1_all_source_citable_nonprod_index_build; no-vector hydration=true; no-vector citation render=true; snapshot_only=122; retrieval_only_uncanonicalized=0; official overlap=29 protected regression rows; vector_metadata_used_as_canonical_citation_source=false.
<!-- official_answer_citation_agentic_loop_run_v3_7_0_source_registry_materialization:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_7_1_all_source_citable_nonprod_index_build:progress-entry:start -->
- v3_7_1 all-source citable non-production index build (`official_answer_citation_agentic_loop_run_v3_7_1_all_source_citable_nonprod_index_build`) builds `ai/eval/indexes/rag-data-all-source-citable-nonprod-v1` from SourceAtom-backed SearchViews only: search_views=136280, TEXT=135608, PDF=329, XLSX=343, snapshot_only=122, official overlap=29 protected regression rows. outcome=ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILT; next_allowed_phase=v3_7_2_source_registry_backed_retrieval_smoke; no-vector hydration=true; no-vector citation render=true; vector_metadata_used_as_canonical_citation_source=false; faiss_gpu_used=false. This is diagnostic-only non-production indexing, not retrieval/answer/citation metric computation, not a hybrid baseline, not prompt/scorer tuning, not promotion, and not gold/qrels/label/expected-answer/supporting-evidence mutation.
<!-- official_answer_citation_agentic_loop_run_v3_7_1_all_source_citable_nonprod_index_build:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_7_2_source_registry_backed_retrieval_smoke_report:progress-entry:start -->
- v3_7_2 source registry-backed retrieval smoke report (`official_answer_citation_agentic_loop_run_v3_7_2_source_registry_backed_retrieval_smoke_report`) fixes the measurement contract to SearchView -> SourceAtom -> EvidenceBundle -> Citation render and reports contract survival by track without answer-quality scoring. Primary routing mode=query_source_family_routed_for_structured_tracks; routed source families=["PDF","XLSX"]; TEXT: queries=356, top-k returned=1780, same-track@k=356, target@k=20, hydration=1780, evidence render=1780, citation render=1780, top failure=track_mismatch; PDF: queries=329, top-k returned=1645, same-track@k=329, target@k=112, hydration=1645, evidence render=1645, citation render=1645, top failure=snapshot_only; XLSX: queries=344, top-k returned=1720, same-track@k=344, target@k=13, hydration=1720, evidence render=1720, citation render=1720, top failure=snapshot_only. Mixed all-source FAISS top-k is retained only as baseline diagnostic: PDF mixed same-track@k=9, off-track returned=1634, cross-family TEXT dominance=328; XLSX mixed same-track@k=31, off-track returned=1689, cross-family TEXT dominance=344. The official/gold query surfaces are sealed no-regression checks only; silver diagnostic failure distribution is coverage/failure-discovery only. Promotion readiness remains closed, comparable live measurement remains deferred, and no prompt/scorer/renderer/index/source-registry/gold/qrels/label/expected-answer/supporting-evidence mutation was performed.
<!-- official_answer_citation_agentic_loop_run_v3_7_2_source_registry_backed_retrieval_smoke_report:progress-entry:end -->

- Official first-run baseline is `status=BLOCKED_OR_PARTIAL`,
  `status_detail=SCORED_BASELINE_PARTIAL`,
  `official_metric_execution_started=true`, `official_scoring_attempt_count=29`,
  `scored_count=29`, PASS=8, CITATION_UNSUPPORTED=11,
  PARTIAL_OR_UNSUPPORTED=10.
- XLSX runtime candidate is report-only and deterministic: PASS=26/29,
  XLSX=19/19, local LLM/GPU used=false.
- PDF table/value candidate now has official-compatible source-bound locators
  for `gq_auto_010`, `gq_auto_030`, and `gq_pdf_section_question_001`;
  report-only, no promotion, PASS=29/29, and it does not overwrite the
  official first-run baseline. expected answers/supporting evidence are for
  scoring/audit only.
- `official_answer_citation_agentic_loop_run_v1` is a separate diagnostic
  live-generation artifact family. `ai/eval/indexes/rag-data` was rebuilt in
  WSL2 with CUDA FAISS; `faiss_gpu_used=true`; result rows=29, scored_count=29,
  PASS=1, promotion_evidence=false. PASS=1/29 is
  `diagnostic_live_generation_fixture_all_index_not_official_denominator_representative`,
  with CORPUS_COVERAGE_MISS=6, STRUCTURED_ADAPTER_NOT_WIRED=22,
  SCORER_COMPATIBILITY_MISMATCH=1, `llm_backend=noop`,
  chunk-only citation locators, not canonical SearchUnit payloads, and
  `baseline_comparison_is_model_quality_comparable=false`.
- source-bound official-denominator SearchUnit export/build is now unblocked
  and load-checked at `ai/eval/indexes/rag-data-official-denominator-v1`.
  The readiness state is `BUILD_READY_LOAD_CHECK_PASSED`,
  blocked_query_ids=[], target_index_built=true, load_check_passed=true,
  rerun_allowed=true, and the built index contains 29/29 official rows
  across PDF=4, TEXT=6, XLSX=19.
- SearchUnit citation payload wiring is implemented in the live runner, and
  XLSX/PDF deterministic adapter opt-in wiring is implemented for retrieved
  source-bound SearchUnits. These remain report-only/candidate wiring changes,
  not promoted result surfaces.

### Answer/Citation Closure

- v3 comparable live measurement remains diagnostic-only: Lane A/B/C PASS are
  `24/29`, `27/29`, `27/29` after the v3_2_7 closure path; Lane A is replay,
  B/C are live LLM surfaces.
- `official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit`
  records that the active queue cleared while all-track residual inventory
  remains for `text_namu_v2_0012`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0077`, and `text_namu_v2_0084`.
  It points to `gold_policy_review_packet_preparation`; `pdfwin_b1c6527f848018640ad5ed231877c662`
  remains the PDF expansion proof. This is diagnostic-only, not promotion
  evidence, no official nDCG/MRR/Hit@K was computed, and Lane A/B/C not collapsed.
- `official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation`
  is the human gold-policy packet-preparation run for the same five TEXT rows.
  The allowed decision options are `keep_current_strict_reference_boundary`,
  `approve_scorer_or_renderer_review_without_gold_mutation`, and
  `revise_gold_or_label_policy`. The active implementation queue remains empty;
  diagnostic-only, not promotion evidence, no official nDCG/MRR/Hit@K, and no
  behavior, gold, label, production, denominator, retrieval, scorer, renderer,
  silver, or promotion mutation occurred.
  In short: no behavior, gold, label, production, denominator, retrieval, scorer, renderer, silver, or promotion mutation.
- `official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement`
  applied a user-approved gold policy override application: five TEXT rows
  changed by user decision (`text_namu_v2_0012`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0077`, `text_namu_v2_0084`).
  The run records five TEXT rows changed by user decision.
  `behavior_change_made=false`; renderer/scorer/retrieval/production/silver/promotion
  behavior changed: none. The scoring-only remeasurement keeps
  In short: renderer/scorer/retrieval/production/silver/promotion behavior changed: none.
  promotion_evidence=false, no official nDCG/MRR/Hit@K, and Lane A/B/C not collapsed.
- `official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation`
  classified six query ids / 12 failing lane items. `text_namu_v2_0012` and
  `text_namu_v2_0077` are Lane A-only frozen replay residuals; `v3_2_4_pdf_context_provenance`
  gates `gq_auto_010`; `v3_2_6_text_prompt_span_rule` is limited to live TEXT
  B/C rows. It produced no per-run
  Markdown, results JSONL, failure attribution, audit payload, official ranking metric,
  or collapsed Lane A/B/C score.
- `official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic`
  found `gq_auto_010` was open because
  `open_because_v3_1_6_expansion_not_wired_into_v3_2_measurement`: current B/C
  cited `7bf516bf-2a17-4303-86d8-3cffaa04846e`, while
  `pdfwin_b1c6527f848018640ad5ed231877c662` held the numeric span.
  `retrieval_context_rerun=false` and
  `retrieval_context_source_run_id=official_answer_citation_agentic_loop_run_v3_comparable_live_measurement`;
  v3_2_5 is
  therefore needed as a measurement-source/context-assembly overlay, not an
  index/export rebuild. No live generation, prompt, renderer, scorer, retrieval,
  index/export, gold, label, denominator, silver, production, or promotion changed.
- `official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix`
  reached `official_answer_citation_v3_2_5_gq_auto_010_pdf_context_reconciliation_fixed`
  and reuses the existing v3_1_6 safe PDF
  paragraph/window sidecar for `gq_auto_010` only. The `pdfwin_b1c6527f848018640ad5ed231877c662`
  overlay changed Lane A/B/C PASS from v3_2_2 `24/29`, `26/29`, `25/29` to
  `24/29`, `27/29`, `26/29`; PASS from v3_2_2 `24/29`, `26/29`, `25/29` to `24/29`, `27/29`, `26/29`;
  non-target unexpected deltas are `0`. No
  index/export rebuild, gold, expected answer, supporting evidence, label,
  denominator, silver, production, promotion, threshold tuning, winner
  selection, official retrieval ranking metric, or collapsed Lane A/B/C score changed.
- `official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`
  reached `official_answer_citation_v3_2_6_text_prompt_span_rule_remeasured`.
  It applied a target-scoped TEXT prompt/span rule; `text_namu_v2_0014` Lane C
  changed from `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`; `text_namu_v2_0014` Lane C changed from `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`; `text_namu_v2_0017` and
  `text_namu_v2_0084` remain diagnostic-only prompt/span residuals; unexpected
  deltas are `0`.
  Residual status: `text_namu_v2_0017` and `text_namu_v2_0084` remain diagnostic-only prompt/span residuals.
- `official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup`
  records `official_answer_citation_v3_2_7_post_fix_sequence_closed`.
  v3_2_5 and v3_2_6 are the only implementation-changing post-v3_2_2 phases;
  Lane A/B/C are now `24/29`, `27/29`, `27/29`, and no next implementation
  phase is opened. Status remains: no next implementation phase is opened.
- `official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit`
  is source-of-truth audit only and records
  `official_answer_citation_v3_3_0_source_of_truth_audit_completed`. Lane A/B/C
  remain `24/29`, `27/29`, `27/29`, and the active implementation queue remains empty.
  Audit status: Lane A/B/C remain `24/29`, `27/29`, `27/29`.

### Retrieval And Qrels State

- v3_3_2 retrieval-label design packet
  `official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet`
  records that the 29-row set is the official answer/citation denominator, not
  yet an official retrieval qrels denominator. It is not yet an official retrieval qrels denominator.
  Official nDCG, MRR, Hit@K, and
  any collapsed Lane A/B/C score remain blocked until relevance/answerability
  labels and evidence policy are settled.
  The same blocker remains: official nDCG, MRR, Hit@K, and any collapsed Lane A/B/C score remain blocked.
- v3_4_0 official retrieval metric contract
  `official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_qrels_schema.json`.
  The contract defines denominator policy options A/B/C. Official nDCG, MRR,
  Hit@K, and any collapsed Lane A/B/C score remain blocked. Official nDCG, MRR, Hit@K, and any collapsed Lane A/B/C score remain blocked;
  Legacy XLSX
  retrieval CSV and silver retrieval-evidence files are prohibited as current
  official qrels.
  Legacy XLSX retrieval CSV and silver retrieval-evidence files are prohibited as current official qrels.
- v3_4_1 marker
  `official_retrieval_qrels_candidate_packet_v3_4_1_ready_for_human_review`;
  run `official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.jsonl`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.csv`,
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_summary.json`.
  It contains 219 rows across 29 query_ids: PDF=22, TEXT=24, XLSX=173, with
  `relevance_label=pending`, `answerability_label=pending`,
  `label_status=pending_user_review`, `generation_source=false`, and
  `promotion_evidence=false`. No official Hit@K, MRR, nDCG was computed.
- v3_4_1a marker `official_retrieval_qrels_human_minimal_review_packet_v3_4_1a_ready`;
  run `official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_policy_approval.json`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_human_query_group_review.csv`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_ambiguous_candidate_review.csv`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_auto_label_plan.json`,
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_summary.json`.
  Review burden is reduced from 219 raw candidate rows to 29 query-group rows plus 30 candidate-unit ambiguity rows;
  estimated 59 review rows total. Expected answer/supporting
  evidence fields are omitted; Codex recommendations are not final labels;
  auto-labeling is not applied; official Hit@K, MRR, nDCG remain blocked.
  Policy reminder: Expected answer/supporting evidence fields are omitted.
- v3_4_2 marker `official_exact_evidence_retrieval_qrels_v3_4_2_ready_metrics_deferred`;
  run `official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_official_retrieval_qrels.jsonl`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_coverage_summary.json`,
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_exclusion_ledger.jsonl`.
  Included query groups=28; excluded query groups=1 (`gq_auto_010`,
  `standalone_query_missing_year`). The exclusion is not a retrieval miss,
  failure, negative, or unanswerable row. Official qrels unit rows=140;
  qrels positives=28; the metric family is official exact-evidence retrieval
  metrics with scope `source_bound_search_unit_exact_answer_evidence_smoke`.
  This is a small official exact-evidence retrieval smoke benchmark for
  metric-pipeline validation and regression guarding, not statistically
  representative product performance. README headline performance claims from this 28-query set are blocked.
  README headline performance claims remain blocked; future nDCG must be binary exact-evidence nDCG@K unless full
  graded relevance labels are created; v3_4_2 did not compute Hit@K, MRR, nDCG.
  v3_4_3 official exact-evidence Hit@K/MRR/binary nDCG computation is ready.
- v3_4_3 marker `official_exact_evidence_retrieval_smoke_metrics_v3_4_3_computed_small_sample`;
  run `official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_metrics.json`
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_per_query.jsonl`.
  Primary ranking surface is Lane B `live_llm_retrieval_topk` only. Included
  query count=28; excluded query count=1 (`gq_auto_010`); PDF=3, TEXT=6,
  XLSX=19. Micro metrics: Hit@1=27/28, Hit@3=28/28, Hit@5=28/28,
  MRR@5=27.5/28, binary exact-evidence nDCG@5=0.9868189197704093.
  `small_sample_warning=true`, `readme_headline_allowed=false`,
  `regression_guard_allowed=true`; one query changes the score by about 3.57
  percentage points. No graded nDCG, threshold tuning, winner selection, or
  README headline claim was made.
- v3_4_4 marker `readme_retrieval_smoke_card_v3_4_4_ready_silver_generation_blocked`;
  v3_4_4 README retrieval-smoke/silver-readiness artifacts
  `official_answer_citation_agentic_loop_run_v3_4_4_readme_retrieval_smoke_and_silver_readiness_artifacts`
  created a compact README metric card JSON, README insertion snippet, and
  silver-readiness summary from the verified v3_4_3 Lane B exact-evidence
  smoke metrics. README integration is snippet-only (`pending_manual_integration=true`):
  `readme_headline_allowed=false`, `regression_guard_allowed=true`; the card
  remains a small-sample regression guard, not statistically representative
  product performance. Silver generation remains blocked: TEXT=0, PDF=3,
  XLSX=4, total=7, below the 100-row pilot and 1000-row target;
  official-denominator SearchUnits remain excluded from dev/holdout silver,
  and no silver rows were generated.

### Source Material And Diagnostic Silver

- v3_5_0 strict non-official source-bound capacity expansion
  `official_answer_citation_agentic_loop_run_v3_5_0_strict_non_official_source_bound_capacity_expansion`
  has marker `strict_non_official_source_bound_capacity_expansion_v3_5_0_pilot_ready`:
  previous strict inventory remains TEXT=0, PDF=3, XLSX=4, total=7; new
  manifest-ready source candidates are TEXT=350, PDF=3, XLSX=4, total=357;
  pilot threshold is met; 1000-row target is not met; silver generation remains
  blocked; recommended next phase is `v3_5_1_pilot_silver_source_manifest_freeze`.
  No questions, expected answers, supporting evidence, labels, qrels, silver
  JSONL rows, prompt, retrieval, renderer, scorer, index/export, production,
  threshold tuning, winner selection, promotion evidence, README representative
  claim, or Lane A/B/C collapsed score changed.
- v3_5_1 pilot source manifest freeze
  (`official_answer_citation_agentic_loop_run_v3_5_1_pilot_silver_source_manifest_freeze`)
  freezes TEXT=350, PDF=3, XLSX=4, total=357 source-only rows; balanced pilot
  threshold is not met; target_threshold_met=false.
- v3_5_2 XLSX source-value manifest repair
  (`official_answer_citation_agentic_loop_run_v3_5_2_xlsx_source_value_manifest_repair_and_acquisition`)
  reconstructs locator-complete XLSX rows from actual workbooks and freezes
  321 manifest-ready overlay rows toward the XLSX target. Combined source
  counts are TEXT=350, PDF=3, XLSX=325, total=678. No query or
  expected_answer_text was used as source material.
- v3_5_3 PDF page/bbox source-text manifest repair
  (`official_answer_citation_agentic_loop_run_v3_5_3_pdf_page_bbox_source_text_manifest_repair_and_acquisition`)
  extracts 322 PDF source rows from approved existing PDF source documents.
  Final source counts are TEXT=350, PDF=325, XLSX=325, total=1000;
  balanced_pilot_threshold_met=true, target_threshold_met=true,
  silver_generation_allowed=false.
- v3_5_4 balanced source-only manifest freeze
  (`official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze`)
  freezes TEXT=350, PDF=325, XLSX=325, total=1000 source-only rows. sample
  packet counts are TEXT=25, PDF=25, XLSX=25; preferred_mix_met=true,
  target_threshold_met=true, silver_generation_allowed=false; next phase is
  v3_5_5_balanced_source_manifest_quality_audit.
- v3_5_5 balanced source-manifest quality audit
  (`official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit`)
  validates TEXT=350, PDF=325, XLSX=325, total=1000 frozen v3_5_4 source-only
  rows. duplicate hash repetitions are 17 groups/57 rows;
  critical_repair_required_count=0, recommended_repair_queue_count=0,
  silver_generation_allowed=false.
- v3_6_0 low-touch weak/noisy silver policy application
  (`official_answer_citation_agentic_loop_run_v3_6_0_low_touch_noisy_silver_policy_application`)
  records user_policy_decision_applied=true, low_touch_human_review_required=false,
  generated silver rows=0.
- v3_6_1 balanced weak/noisy silver candidate generation
  (`official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation`)
  creates 1000 diagnostic weak/noisy candidate rows: TEXT=350, PDF=325,
  XLSX=325, total=1000; blocked rows=0. This is not gold, not official
  denominator/qrels, not promotion evidence.
- v3_6_2 weak/noisy silver candidate sanity eval
  (`official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval`)
  has candidate_sanity_passed=true; bucket counts are core=665, review-only=335,
  quarantine=0, blocked=0; hash contract=normalized question sha256;
  v3_6_3 diagnostic weak/noisy silver manifest freeze is allowed=true.
- v3_6_3 diagnostic weak/noisy silver manifest freeze
  (`official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze`)
  freezes 1000 diagnostic rows: core=665, review-only=335, quarantine=0.
  official proximity rows remain review-only=3; v3_6_4 diagnostic-only
  weak/noisy silver metric is allowed=true.
- v3_6_4 diagnostic-only weak/noisy silver metric
  (`official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric`)
  measures core_only=665, review_only_challenge=335, all_diagnostic=1000.
  live generation coverage=0/1000 and answer/citation proxy metrics fail
  closed; core_only is the main interpretable diagnostic bucket.
- v3_6_5 rough failure-bucket triage
  (`official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage`)
  keeps v3_6_4 diagnostic-only: no live silver generation, no DB writes, no
  index/export rebuild, and DB-derived generation/gold/qrels remain blocked.
- v3_6_6 diagnostic reference sidecar and runtime surface probe
  (`official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe`)
  builds a diagnostic reference sidecar: all=1000, core=665, review-only=335,
  quarantine=0; core smoke strict JSON answers returned=30. Review-only remains
  stress-only, and DB-derived generation/gold/qrels remain blocked.
- v3_6_7 runtime stability probe for core-only
  (`official_answer_citation_agentic_loop_run_v3_6_7_runtime_stability_probe_for_core_only`)
  reruns the inherited core smoke sample as diagnostic-only evidence:
  attempted=30, strict JSON answers=30, citation surface valid=0. This is not
  gold/qrels/official denominator/labels, not README performance evidence, and
  no prompt/retrieval/scorer/renderer/index/export/DB mutation was performed.
- v3_6_8 non-production all-source index materialization
  (`official_answer_citation_agentic_loop_run_v3_6_8_nonprod_all_source_index_materialization_and_canonical_payload_wiring`)
  builds `ai/eval/indexes/rag-data-all-source-nonprod-v1` with accepted source
  units={"PDF":329,"TEXT":135608,"XLSX":343,"total":136280}. Load-check
  passed=true; canonical payload families=["PDF","TEXT","XLSX"]; no-LLM render
  valid count=50; outcome=ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED;
  next_allowed_phase=v3_6_9_core_only_live_diagnostic_metric; blocking buckets=[].
  This is diagnostic-only non-production indexing, not a promotion run, not an
  official representative metric, and not README performance evidence.
- v3_6_8 source-registry-first evidence bundle architecture audit
  (`official_answer_citation_agentic_loop_run_v3_6_8_source_registry_first_evidence_bundle_architecture_audit`)
  stops the all-source index expansion path. Search indexes remain candidate
  generators only; outcome=SEARCHUNIT_OVERLOADED_BLOCKER;
  next_allowed_phase=SearchUnit/SearchView/SourceAtom refactor;
  blocking buckets=["SEARCHUNIT_OVERLOADED_BLOCKER"]; SearchUnit is overloaded
  because it acts as retrieval unit, source atom, citation unit, evidence unit,
  metric/qrels unit, and LLM context unit.
- v3_6_9 SearchUnit/SearchView/SourceAtom refactor
  (`official_answer_citation_agentic_loop_run_v3_6_9_searchunit_searchview_sourceatom_refactor`)
  introduces a durable source-first Python contract where SearchViews are
  retrieval candidates and EvidenceBundles hydrate through SourceAtoms before
  citation rendering. outcome=SEARCHUNIT_SEARCHVIEW_SOURCEATOM_CONTRACT_READY;
  next_allowed_phase=source registry materialization; next blocking work=
  ["SOURCE_REGISTRY_MATERIALIZATION_REQUIRED"]; no-vector render count=3;
  vector_payload_used_as_evidence_truth=false. No production DB, DB
  write/migration, index/export rebuild, prompt/scorer tuning,
  gold/qrels/label/expected-answer/supporting-evidence mutation, or official
  metric scoring was performed.

## Track Board

| Track | Current state | Current metric/evidence | Next action |
|---|---|---|---|
| Source architecture | v3_6_9 SearchUnit/SearchView/SourceAtom contract is ready; legacy SearchUnit entity is still overloaded | SourceAtom hydration smoke passes without vector payload as evidence truth; source registry materialization required | Materialize durable source registry before more retrieval metric work. |
| `text_namu_v2_1` | v3_2_7 closes the post-fix implementation queue; `text_namu_v2_0017` and `text_namu_v2_0084` remain diagnostic-only | Lane A/B/C: `24/29`, `27/29`, `27/29`; `text_namu_v2_0012` and `text_namu_v2_0077` are frozen Lane A replay residuals | Do not reopen gold policy automatically. |
| `xlsx_business_structured` | Source-bound answer/scorer compatibility is stable | XLSX target rows PASS in Lane B/C; XLSX `row_label` mismatch=0 | Keep date/number compatibility general; do not tune thresholds. |
| `pdf_business_ocr_mm` | `gq_auto_010` is closed by reusing the v3_1_6 safe PDF window sidecar | B/C cite `pdfwin_b1c6527f848018640ad5ed231877c662` and PASS; no index/export rebuild | No PDF follow-up unless a regression reopens it. |
| Report artifacts | Human narrative stays in three rolling docs; machine evidence stays compact | `status.jsonl` plus summary/diagnostic JSON where required by tests | Avoid per-run Markdown and full forensic payloads unless the run contract requires them. |

## Current Verification Command

Windows/Python current env:

```powershell
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q
```

Current verification: local results recorded in this progress log. Latest
current-profile evidence after the v3_7_2 routing smoke update is
`python -X utf8 -m pytest ai/tests --rag-current -q` -> 276 passed, 0 skipped,
0 failed, 1 warning.
Targeted v3_7_2 source-registry routing/status/hash/guardrail checks also pass.

Current test surface is intentionally compact after legacy test deletion:
`python -X utf8 -m pytest ai/tests --rag-current -q`; full `ai/tests`
  now mirrors the current profile and no longer carries broad/nightly legacy
  suites.

The pre-execution smoke report is a pre-execution artifact, so
`official_metric_execution_started=false` there is expected and must not be read
as the latest metric execution status.

## Current Source-Of-Truth Artifacts

Human-facing rolling docs:

- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`

Machine-readable official/status surfaces:

- `ai/eval/reports/rag-ingestion/status.jsonl`
- latest v3_6_9 SearchUnit/SearchView/SourceAtom refactor JSON artifacts:
  summary, contract refactor, adapter diagnostics, SourceAtom hydration smoke,
  and failure buckets.
- `ai/eval/silver/answer_citation_silver_manifest_v1.json`
- `ai/eval/silver/answer_citation_silver_readiness_v1.json`

As of the 2026-05-21 report cleanup, `ai/eval/reports/` intentionally keeps
only `rag-ingestion/`, and that directory keeps only `status.jsonl` plus the
latest v3_6_9 machine artifacts. Older `rag-ingestion` payloads, including the
official baseline/scorer/input/smoke/source-bound files and v3_1-v3_6_8
diagnostics, are consolidated under
`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\repo-wide-cleanup-20260521\reports\rag-ingestion-legacy\`.
The former `ai/eval/reports/phase7/` and
`ai/eval/reports/legacy-baseline-final/` trees are also archived under
`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\repo-wide-cleanup-20260521\reports\`.
The previous 2026-05-19 external archive remains a compatibility fallback.
Repo-local archive payloads are externalized under
`D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260519-repo-wide-cleanup\files\archive\`.

Per-run Markdown reports under `ai/eval/reports/rag-ingestion/` are no longer
the human-facing surface. The ongoing narrative stays in the three rolling docs
above.

## Guardrails

- `tuning_run_started=false`
- `promotion_evidence=false`
- `threshold_tuning=false`
- `winner_selection=false`
- `production_mutation=false`
- `denominator_mutation=false`
- Silver policy remains anti-overfit: silver is not gold, not official
  denominator, not promotion evidence, expected values are audit-only, and the
  official 29 query_ids are excluded from dev/holdout tuning silver.
- Current silver overlap with the official denominator remains
  `TEXT=0, XLSX=0, PDF=0`.
- The official-denominator source-bound index, build/load check, and canonical
  SearchUnit citation payload wiring are already available; 29/29 source-bound
  SearchUnits overlap the official denominator, but safe non-official
  source-bound source manifests are still missing, so silver generation stays
  closed until safe silver-source data coverage is settled.
- Expected answer and supporting evidence are not used for generation.
- Silver expected values are audit-only and silver cases must not be used as
  generation input.
- Official 29 query_ids are excluded from dev/holdout tuning silver.
- Gold CSVs, official denominator registry, human labels, production namespace,
  vector indexes, and immutable first-run baseline artifacts remain protected.
- v3 diagnostic lanes stay diagnostic-only. Lane B/C PASS counts are not
  promotion evidence, and Lane A/B/C must not be collapsed into a single
  official score.

## Next Recommended Steps

1. Materialize the source registry behind the v3_6_9 SourceAtom/SearchView
   contract before opening more retrieval metric work.
2. Keep the official answer/citation implementation queue closed unless a later
   user-owned policy decision reopens TEXT answerability/gold boundaries.
3. Do not create silver rows or change expected answers, supporting evidence,
   relevance labels, answerability labels, or gold policy unless explicitly
   requested.
4. Keep report output compact: necessary machine artifacts plus this rolling
   status page, not per-run Markdown report families.
5. Keep the compact `ai/tests` surface current; extend existing files for
   routine coverage and create a new test file only for a durable subsystem.

## Short History

| Date | Compact entry |
|---|---|
| 2026-05-16 | Historical first-run attempt was blocked with `SCORER_BACKEND_UNAVAILABLE`; active first-run artifacts were later regenerated and this state is superseded. |
| 2026-05-17 | Official first-run baseline scored 29/29 rows and remained partial: PASS=8, CITATION_UNSUPPORTED=11, PARTIAL_OR_UNSUPPORTED=10. |
| 2026-05-17 | XLSX runtime candidate reached PASS=26/29 and PDF table/value candidate reached PASS=29/29 as report-only deterministic candidates. |
| 2026-05-17 | Source-bound official-denominator index was built/load-checked for 29/29 rows, then v2 diagnostic scoring reached PASS=20/29 with schema mismatches fail-closed. |
| 2026-05-18 | v3_1-v3_1_6 moved from locator/renderer triage to the safe PDF paragraph/window expansion proof; active queue became empty. |
| 2026-05-19 | v3_1_9 through v3_3_2 settled user-approved TEXT gold-policy override, v3_2 closure, and retrieval-label design without opening official retrieval metrics. |
| 2026-05-19 | v3_4 created exact-evidence retrieval qrels and a small 28-query smoke metric, explicitly not representative product performance. |
| 2026-05-20 | v3_5-v3_6 built the balanced source-only manifest and diagnostic weak/noisy silver path, then stopped at source-first architecture separation. |
| 2026-05-20 | v3_6_8 and v3_6_9 proved all-source non-production indexing and a SearchUnit/SearchView/SourceAtom contract; source registry materialization is next. |
| 2026-05-21 | v3_7_2 superseded the inherited 1000 weak/noisy silver query surface with local LLM natural Korean queries while preserving diagnostic-only, non-promotion boundaries. |
| 2026-05-21 | v3_7_2 source registry-backed retrieval smoke separates top-k returned candidates from same-track@k, target@k, and contract survival; promotion readiness remains closed. |
