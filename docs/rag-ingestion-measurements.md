# RAG Ingestion Measurements

Last updated: 2026-05-19 KST.

This is the rolling human-readable measurement ledger for RAG ingestion and
official answer/citation diagnostics. Keep this file append-style: add new
measurement sections at the top, keep older sections as compact history, and do
not create per-run Markdown reports for routine diagnostic runs.

Machine-readable JSON/JSONL artifacts can remain under
`ai/eval/reports/rag-ingestion/`, but those files are evidence payloads, not the
primary human report surface.
Historical `_archive/legacy` artifact paths in older entries are logical
provenance names. Their physical generated payloads may live in the external
runtime archive under
`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\`.

## Current Measurement Ladder

| Stage | Run family | Scope | Key result | Guardrail |
|---|---|---|---|---|
| Official first-run baseline | `official_answer_citation_metric_first_run_v1` | 29 official rows | PASS `8/29`, `CITATION_UNSUPPORTED=11`, `PARTIAL_OR_UNSUPPORTED=10` | Diagnostic baseline only |
| v1 diagnostic live-generation | `official_answer_citation_agentic_loop_run_v1` | Fixture-all index, noop/extractive generation | PASS `1/29`; fixture-all/noop/chunk-only limitations | `promotion_evidence=false` |
| Source-bound index readiness | `official_answer_citation_source_bound_index_build_readiness_v1` | 29 source-bound SearchUnits | `BUILD_READY_LOAD_CHECK_PASSED` | Non-production index only |
| v3 comparable live measurement | `official_answer_citation_agentic_loop_run_v3_comparable_live_measurement` | 29 rows, structured adapter retained for XLSX/PDF | PASS `24/29` | Not all-track LLM quality |
| v3_1 all-track foundation | `official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement` | Lane A/B/C fixed across PDF/TEXT/XLSX | Lane A `24/29`, Lane B `18/29`, Lane C `20/29` | Diagnostic-only |
| v3_1 priority 1~5 triage | `official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage` | Five row-level infrastructure/locator cases | strict JSON parse `2 -> 0`; locator field mismatch `3 -> 0`; residual copy failure `1` | Diagnostic-only |
| v3_1 TEXT locator residual | `official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage` | `text_namu_v2_0012` only | TEXT `text_locator` missing `1 -> 0`; byte/normalized equal true | Diagnostic-only |
| v3_1_1 post strict JSON/locator triage | `official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage` | 29 official rows, same Lane A/B/C definitions | Lane A `24/29`, Lane B `20/29`, Lane C `17/29`; strict JSON and locator residuals `0` | Diagnostic-only |
| v3_1_2 answer span / renderer triage | `official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage` | First five TEXT queue rows plus secondary `text_namu_v2_0005` watchlist | Target Lane A `1/6`, Lane B `1/6`, Lane C `0/6`; all-track reference unchanged | Diagnostic-only |
| v3_1_3 remaining queue answer span / renderer triage | `official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage` | Seven-row v3_1_2 remaining queue plus 29-row all-track remeasurement | Target Lane A `7/7`, Lane B `5/7`, Lane C `5/7`; all-track Lane A `24/29`, Lane B `22/29`, Lane C `22/29`; residual locator/strict JSON counts `0` | Diagnostic-only |
| v3_1_4 PDF residual answer span / renderer triage | `official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage` | Two-row v3_1_3 remaining queue plus 29-row all-track remeasurement | Target Lane A `2/2`, Lane B `1/2`, Lane C `1/2`; all-track Lane A `24/29`, Lane B `23/29`, Lane C `23/29`; residual locator/strict JSON counts `0` | Diagnostic-only |
| v3_1_5 `gq_auto_010` source-bound coverage diagnostic | `official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic` | One-row v3_1_4 remaining queue, classification-only static coverage probe | Classification `query_bound_searchunit_too_narrow`; remaining queue `gq_auto_010`; no behavior change or all-track remeasurement | Diagnostic-only |
| v3_1_6 `gq_auto_010` safe PDF paragraph/window expansion | `official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic` | One-row v3_1_5 remaining queue plus 29-row all-track remeasurement | Target Lane A `1/1`, Lane B `1/1`, Lane C `1/1`; all-track Lane A `24/29`, Lane B `24/29`, Lane C `24/29`; residual locator/strict JSON counts `0`; remaining queue empty | Diagnostic-only |
| v3_1_7 post-residual queue closure audit | `official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit` | No-behavior inventory over existing v3_1_6 after-state artifacts | Active queue empty; all-track residuals remain 5 TEXT query ids / 15 lane items; implementation-safe follow-up `0`; user decision packet created | Diagnostic-only |
| v3_1_8 gold-policy review packet preparation | `official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation` | No-behavior human review packet over the five v3_1_7 TEXT residual query ids | Decision packet and decision matrix created; active implementation queue empty; implementation-safe residuals `0`; silver closed | Diagnostic-only |
| v3_1_9 user-approved gold policy override + scoring-only remeasurement | `official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement` | Five TEXT gold-policy rows updated from `gold_overrides.csv`; existing Lane A/B/C answer surfaces rescored | Lane A `24/29 -> 27/29`, Lane B `24/29 -> 26/29`, Lane C `24/29 -> 25/29`; remaining queue 4 TEXT query ids / 9 lane items | Gold policy mutation, no behavior/promotion |

The official first-run baseline is a scored partial baseline and is not a
scorer backend blocker. It remains the immutable reference point; later rows in
this ladder are diagnostic deltas, not promotion evidence.

## 2026-05-19 - v3_1_9 User-Approved Gold Policy Override Application And Scoring-Only Remeasurement

Run family:
`official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement`

Scope:

- This run applied the user-approved `gold_overrides.csv` policy source of
  truth for exactly five TEXT rows: `text_namu_v2_0012`,
  `text_namu_v2_0014`, `text_namu_v2_0017`, `text_namu_v2_0077`, and
  `text_namu_v2_0084`.
- Active gold path: `ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv`.
  The v2 CSV was updated in place because the current official denominator
  registry, metric input config, smoke report, and loader tests reference that
  path directly.
- This is a gold policy mutation run:
  `run_class=user_approved_gold_policy_override_application`,
  `user_policy_decision_applied=true`, `expected_answer_mutation=true`,
  `supporting_evidence_mutation=true`, and `gold_policy_mutation=true`.
- It is not renderer, scorer, retrieval, production, silver, or promotion work:
  `behavior_change_made=false`, `renderer_mutation=false`,
  `scorer_behavior_mutation=false`, `retrieval_mutation=false`,
  `production_mutation=false`, `silver_rows_created=false`, and
  `promotion_evidence=false`.

Scoring-only remeasurement:

| Lane | Before | After |
|---|---:|---:|
| Lane A `v3_primary_replay` | `24/29` PASS | `27/29` PASS |
| Lane B `live_llm_retrieval_topk` | `24/29` PASS | `26/29` PASS |
| Lane C `live_llm_query_bound_oracle` | `24/29` PASS | `25/29` PASS |

Boundaries:

- Existing Lane A/B/C generated answer surfaces were reused; live generation was
  not rerun.
- Expected answers, supporting evidence, and gold fields were not used as
  generation source.
- Official nDCG, MRR, Hit@K, and any collapsed Lane A/B/C score were not
  computed.
- The official denominator query-id set remained 29 rows and did not change.

Remaining queue:

- `text_namu_v2_0014`: Lane C remains non-PASS.
- `text_namu_v2_0017`: Lane B/C remain non-PASS.
- `text_namu_v2_0077`: Lane A/B/C remain non-PASS.
- `text_namu_v2_0084`: Lane A/B/C remain non-PASS.
- These residuals are now implementation-safe for a later renderer/scorer/
  prompt/retrieval phase because the user gold policy is settled. No additional
  user policy packet is required from v3_1_9.

## 2026-05-19 - v3_1_8 Gold-Policy Review Packet Preparation

Run family:
`official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation`

Scope:

- No generation, retrieval, renderer, scorer, threshold, denominator,
  production, gold, relevance, answerability, expected-answer, supporting
  evidence, silver, or promotion behavior changed.
- This is a human policy packet preparation step, not a metric improvement and
  not an official retrieval metric run.
- Lane A/B/C remain separated; official nDCG, MRR, Hit@K, and any collapsed
  Lane A/B/C score were not computed.

Packet:

- Query ids: `text_namu_v2_0012`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0077`, `text_namu_v2_0084`.
- Residual lane items carried from v3_1_7: `15`.
- Decision options for every item:
  `keep_current_strict_reference_boundary`,
  `approve_scorer_or_renderer_review_without_gold_mutation`, and
  `revise_gold_or_label_policy`.
- Human-review-only policy material is present in the packet where recovered
  from existing official artifacts, but it is explicitly
  `generation_source=false`, `not_silver_source=true`, and
  `not_gold_mutation=true`.

Decision:

- Active implementation queue: empty.
- Implementation-safe residual count: `0`.
- Silver remains closed.
- v3_1_6 sibling-hash drift was recorded as metadata drift only; historical
  artifacts were not rewritten.

## 2026-05-18 - v3_1_7 Post-Residual Queue Closure And Residual Inventory Audit

Run family:
`official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit`

Scope:

- No generation, retrieval, renderer, scorer, prompt, threshold, denominator,
  production, gold, relevance, or answerability behavior changed.
- The run reconciles two facts: the v3_1_6 active remaining triage queue is
  empty, while the reconstructed 29-row all-track after-state still has five
  non-PASS rows by lane.
- The all-track after-state was recovered from existing artifacts; no live
  all-track generation was rerun.

Closure:

- v3_1_6 semantic closure assertions passed: `gq_auto_010` PASS in Lane A/B/C,
  safe PDF paragraph/window expansion applied with
  `pdfwin_b1c6527f848018640ad5ed231877c662`, locator-safe metadata available,
  remaining queue empty, strict JSON/locator residuals zero, and no non-target
  unexpected changes.
- v3_1_7 also recorded a source-artifact hash audit. Several v3_1_6 summary
  hash fields no longer match current sibling artifact bytes, so this is
  recorded as metadata drift for audit visibility; it did not reopen generation
  or promotion work.

All-track residual inventory after v3_1_6:

| Lane | PASS | Non-PASS | Residual category |
|---|---:|---:|---|
| Lane A `v3_primary_replay` | `24/29` | `5/29` | `LLM_TRUE_PARTIAL_SYNTHESIS` |
| Lane B `live_llm_retrieval_topk` | `24/29` | `5/29` | `LLM_EXPECTED_SPAN_MISMATCH` |
| Lane C `live_llm_query_bound_oracle` | `24/29` | `5/29` | `LLM_EXPECTED_SPAN_MISMATCH` |

Residual query ids:
`text_namu_v2_0012`, `text_namu_v2_0014`, `text_namu_v2_0017`,
`text_namu_v2_0077`, `text_namu_v2_0084`.

Bucket counts:

- `gold_policy_review_candidate=15`
- `answer_renderer_followup_candidate=15`
- `scorer_normalization_review_candidate=3`
- `implementation_safe_followup=0`
- `retrieval_context_followup_candidate=0`
- `relevance_label_review_candidate=0`
- `answerability_label_review_candidate=0`

Decision:

- Active implementation queue: empty.
- All residuals require user gold-policy review before any safe implementation
  claim.
- Recommended next phase: `gold_policy_review_packet_preparation`.
- Official nDCG, MRR, Hit@K, and a collapsed Lane A/B/C score were not
  computed. Future metric choices remain non-binding design notes only.

## 2026-05-18 - v3_1_6 `gq_auto_010` Safe PDF Paragraph/Window Expansion Diagnostic

Run family:
`official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic`

Scope:

- Source of truth is the v3_1_5 machine remaining queue:
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_5_gq010_coverage_queue.json`.
- Target row: `gq_auto_010` only.
- This was a behavior-changing diagnostic branch because source-bound prompt
  context assembly changed. It was not answer renderer work, gold work,
  official retrieval metric work, or a promotion run.
- Safe PDF paragraph/window expansion was attempted and applied. Locator-safe
  metadata was available from the same `source_pdf_path`, same
  `document_version_id`, page `8`, physical page index `7`, bbox
  `[63.65, 95.06, 341.94, 163.68]`, region type `paragraph_window`, and
  expansion unit `pdfwin_b1c6527f848018640ad5ed231877c662`.
- No non-production index/export repair was applied and no production index was
  touched.

Target queue before/after:

| Lane | Before | After |
|---|---:|---:|
| Lane A `v3_primary_replay` | `1/1` PASS | `1/1` PASS |
| Lane B `live_llm_retrieval_topk` | `0/1` PASS | `1/1` PASS |
| Lane C `live_llm_query_bound_oracle` | `0/1` PASS | `1/1` PASS |

All-track before/after:

| Lane | Before v3_1_4 | After v3_1_6 |
|---|---:|---:|
| Lane A `v3_primary_replay` | `24/29` PASS | `24/29` PASS |
| Lane B `live_llm_retrieval_topk` | `23/29` PASS | `24/29` PASS |
| Lane C `live_llm_query_bound_oracle` | `23/29` PASS | `24/29` PASS |

Residual status:

- Strict JSON parse residuals by lane: `0`.
- LLM-generated locator copy/missing/field mismatch residuals by lane: `0`.
- PDF `source_pdf_path` mismatch: `0`.
- XLSX `row_label` mismatch: `0`.
- TEXT `text_locator` missing: `0`.
- Non-target context expansion query ids: none.
- Non-target unexpected change count: `0`.

Guardrails:

- `diagnostic_only=true`, `promotion_evidence=false`,
  `promotion_gate_auto_run=false`, `threshold_tuning=false`,
  `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`,
  `generation_used_supporting_evidence=false`,
  `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`; audit numeric spans were post-generation
  coverage/scoring probes only.
- `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`.
- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score were not computed.

Artifact classes:

| Artifact | Retention class |
|---|---|
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_summary.json` | `machine_manifest` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_results.jsonl` | `canonical_result_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_failure_attribution.json` | `forensic_debug_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_actual_response_audit.jsonl` | `response_audit_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_answer_span_diagnostics.jsonl` | `compact_answer_span_diagnostic_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_context_expansion_diagnostics.jsonl` | `compact_pdf_context_expansion_diagnostic_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_remaining_triage_queue.json` | `queue_source_of_truth` |
| `status.jsonl` | `compact_status_ledger` |

Remaining queue after v3_1_6: empty.

## 2026-05-18 - v3_1_5 `gq_auto_010` Source-Bound Coverage Diagnostic

Run family:
`official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic`

Scope:

- Source of truth is the v3_1_4 machine remaining queue:
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_4_pdf_residual_queue.json`.
- Target row: `gq_auto_010` only.
- This run is classification-only and diagnostic-only. It did not invoke live
  generation, change answer rendering/scoring, rebuild indexes, mutate the
  denominator/gold/labels/production namespace, or create silver/gold/promotion
  evidence.
- Audit numeric spans were used only as post-hoc static coverage probes. Raw
  expected/supporting/gold fields were not used as generation source and
  reference span text was not embedded in generation-facing artifacts.

Coverage probe result:

| Probe surface | Contains all audit numeric spans? |
|---|---|
| v3_1_4 cited context for Lane B/C | no |
| Current cited SearchUnit `7bf516bf-2a17-4303-86d8-3cffaa04846e` | no |
| Any same-document SearchUnit in the current source-bound index | no |
| Adjacent page/window SearchUnits in the current source-bound index | no |
| Raw/source PDF text extraction, safe local source | yes |

Classification:

`query_bound_searchunit_too_narrow`

Rationale: the cited SearchUnit supports the general claim that unemployment
rose across all age groups, but it does not include the numeric answer span.
The raw PDF extraction contains the span on the same source page, while the
current SearchUnit/export surfaces available to the source-bound index do not.
That is enough to keep the issue in retrieval/context coverage triage, but not
enough to patch retrieval/index behavior in this run.

Measurement status:

- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.
- No 29-row all-track remeasurement was run because no generation, retrieval,
  index, export, renderer, or scorer behavior changed.
- No non-production index/export repair was applied.
- Verification recorded in `docs/rag-ingestion-progress.md`: both current
  pytest profiles PASS with 133 tests, py_compile PASS, doctor selected checks
  PASS, and `git diff --check` PASS with line-ending warnings only.

Artifact classes:

| Artifact | Retention class |
|---|---|
| `...v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_summary.json` | `machine_manifest` |
| `...v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_context_coverage_diagnostics.jsonl` | `compact_coverage_diagnostic_payload` |
| `...v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_remaining_triage_queue.json` | `queue_source_of_truth` |
| `status.jsonl` | `compact_status_ledger` |

Remaining queue after v3_1_5:

1. `gq_auto_010`

## 2026-05-18 - v3_1_4 PDF Residual Answer Span / Renderer Triage

Run family:
`official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage`

Scope:

- Source of truth is the v3_1_3 machine remaining queue:
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_3_remaining_queue.json`.
- Target rows: `gq_auto_010`, `gq_pdf_section_question_001`.
- Behavior changes were limited to a source-bound PDF table-axis renderer for
  repeated amount/growth columns and post-generation diagnostic classification
  of PDF context insufficiency.
- 29-row all-track remeasurement was performed because renderer behavior
  changed.
- No per-run Markdown report was created.

Target queue before/after:

| Lane | Before PASS | After PASS | Answer span mismatch before | Answer span mismatch after |
|---|---:|---:|---:|---:|
| Lane A `v3_primary_replay` | 2/2 | 2/2 | 0 | 0 |
| Lane B `live_llm_retrieval_topk` | 0/2 | 1/2 | 2 | 1 |
| Lane C `live_llm_query_bound_oracle` | 0/2 | 1/2 | 2 | 1 |

29-row all-track before/after:

| Lane | v3_1_3 before PASS | v3_1_4 after PASS | Answer span mismatch before | Answer span mismatch after |
|---|---:|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 | 0 |
| Lane B `live_llm_retrieval_topk` | 22/29 | 23/29 | 7 | 6 |
| Lane C `live_llm_query_bound_oracle` | 22/29 | 23/29 | 7 | 6 |

Residual checks:

| Residual | Target after | All-track after |
|---|---:|---:|
| Strict JSON parse failure | 0 by lane | 0 by lane |
| LLM-generated locator copy failure | 0 by lane | 0 by lane |
| LLM-generated locator missing failure | 0 by lane | 0 by lane |
| LLM-generated locator field mismatch | 0 by lane | 0 by lane |
| PDF `source_pdf_path` mismatch | 0 | 0 |
| XLSX `row_label` mismatch | 0 | 0 |
| TEXT `text_locator` missing | 0 | 0 |

Row outcome:

| Query ID | Before failing lanes | After failing lanes | Classification |
|---|---|---|---|
| `gq_auto_010` | B, C | B, C | Retrieval/context insufficiency: the cited paragraph says the unemployment rate rose across all age groups but does not contain the numeric answer span. |
| `gq_pdf_section_question_001` | B, C | none | Source-bound PDF table-axis disambiguation selected the `수출입차 금액` value `518.4` instead of the adjacent import amount. |

Guardrails:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- Reference spans and expected/supporting fields remain post-generation
  scoring/audit inputs only.

Artifact classes:

| Artifact | Retention class |
|---|---|
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_summary.json` | `machine_manifest` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_results.jsonl` | `canonical_result_payload` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_failure_attribution.json` | `forensic_debug_payload` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_actual_response_audit.jsonl` | `response_audit_payload` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_answer_span_diagnostics.jsonl` | `compact_answer_span_diagnostic_payload` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_remaining_triage_queue.json` | `queue_source_of_truth` |

Remaining queue after v3_1_4:

1. `gq_auto_010`

## 2026-05-18 - v3_1_3 Remaining Queue Answer Span / Renderer Triage

Run family:
`official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage`

Scope:

- Source of truth is the v3_1_2 machine remaining queue:
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json`.
- Target rows: `gq_auto_010`, `gq_auto_024`, `gq_auto_030`,
  `gq_auto_043`, `gq_pdf_section_question_001`,
  `gq_xlsx_date_number_format_001`, `text_namu_v2_0005`.
- Behavior changes were limited to prompt answer instructions, source-bound
  answer renderer shaping, and post-generation scorer compatibility
  normalization.
- 29-row all-track remeasurement was performed because generation/renderer/
  scorer behavior changed.
- No per-run Markdown report was created.

Target queue before/after:

| Lane | Before PASS | After PASS | Answer span mismatch before | Answer span mismatch after |
|---|---:|---:|---:|---:|
| Lane A `v3_primary_replay` | 7/7 | 7/7 | 0 | 0 |
| Lane B `live_llm_retrieval_topk` | 3/7 | 5/7 | 4 | 2 |
| Lane C `live_llm_query_bound_oracle` | 0/7 | 5/7 | 7 | 2 |

29-row all-track before/after:

| Lane | v3_1_1 before PASS | v3_1_3 after PASS | Answer span mismatch before | Answer span mismatch after |
|---|---:|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 | 0 |
| Lane B `live_llm_retrieval_topk` | 20/29 | 22/29 | 9 | 7 |
| Lane C `live_llm_query_bound_oracle` | 17/29 | 22/29 | 12 | 7 |

Residual checks:

| Residual | Target after | All-track after |
|---|---:|---:|
| Strict JSON parse failure | 0 by lane | 0 by lane |
| LLM-generated locator copy failure | 0 by lane | 0 by lane |
| LLM-generated locator missing failure | 0 by lane | 0 by lane |
| LLM-generated locator field mismatch | 0 by lane | 0 by lane |
| PDF `source_pdf_path` mismatch | 0 | 0 |
| XLSX `row_label` mismatch | 0 | 0 |
| TEXT `text_locator` missing | 0 | 0 |

Row outcome:

| Query ID | Before failing lanes | After failing lanes | Classification |
|---|---|---|---|
| `gq_auto_010` | B, C | B, C | PDF context lacks expected numeric span (`4.9%`, `0.8%p`); keep diagnostic-only. |
| `gq_auto_024` | C | none | Korean source phrase renderer restored Lane C. |
| `gq_auto_030` | C | none | Prompt table-axis instruction selected `1,088.0`. |
| `gq_auto_043` | B, C | none | XLSX date normalized/renderer compatibility. |
| `gq_pdf_section_question_001` | B, C | B, C | PDF table value disambiguation still selects import amount `6,317.7` instead of trade-balance amount; keep diagnostic-only. |
| `gq_xlsx_date_number_format_001` | B, C | none | XLSX date normalized/renderer compatibility. |
| `text_namu_v2_0005` | C | none | Korean answer rendering fixed Lane C; Lane A/B did not regress. |

Guardrails:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- Reference spans and expected/supporting fields remain post-generation
  scoring/audit inputs only.

Artifact classes:

| Artifact | Retention class |
|---|---|
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_summary.json` | `machine_manifest` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_results.jsonl` | `canonical_result_payload` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_failure_attribution.json` | `forensic_debug_payload` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_actual_response_audit.jsonl` | `response_audit_payload` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_answer_span_diagnostics.jsonl` | `compact_answer_span_diagnostic_payload` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_remaining_triage_queue.json` | `queue_source_of_truth` |

Remaining queue after v3_1_3:

1. `gq_auto_010`
2. `gq_pdf_section_question_001`

## 2026-05-18 - v3_1_2 Answer Span / Renderer Triage Batch 1

Run family:
`official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage`

Scope:

- Classification-only diagnostic run over existing v3_1_1 post-triage
  artifacts.
- First TEXT batch selected from the machine triage queue:
  `text_namu_v2_0012`, `text_namu_v2_0014`, `text_namu_v2_0017`,
  `text_namu_v2_0077`, `text_namu_v2_0084`.
- `text_namu_v2_0005` included only as a secondary TEXT watchlist row because
  the machine queue ranks it 12 and its post-triage failure is Lane C-only.
- No new all-track rerun was performed because this run changed no generation,
  renderer, scorer, locator, or retrieval behavior.

Queue source of truth:

- Adopted
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_1_post_locator_queue.json`.
- This machine artifact supersedes the stale human Later Triage Queue text when
  they differ. The stale text omitted `text_namu_v2_0012` and
  `text_namu_v2_0005` and included `gq_auto_037`, while the machine artifact
  ranks the first five TEXT rows first and places `text_namu_v2_0005` at rank
  12.

Metrics:

| Metric | Result |
|---|---:|
| Target diagnostic rows | 6 |
| Primary first-batch rows | 5 |
| Secondary watchlist rows | 1 |
| Target Lane A PASS | 1/6 |
| Target Lane B PASS | 1/6 |
| Target Lane C PASS | 0/6 |
| Primary first-batch Lane A/B/C PASS | 0/5 each |
| All-track reference Lane A PASS | 24/29 |
| All-track reference Lane B PASS | 20/29 |
| All-track reference Lane C PASS | 17/29 |
| All-track answer span mismatches | Lane A=0, Lane B=9, Lane C=12 |
| Strict JSON parse residual | 0 |
| LLM-generated locator copy residual | 0 |
| PDF `source_pdf_path` mismatch | 0 |
| XLSX `row_label` mismatch | 0 |
| TEXT `text_locator` missing | 0 |

Diagnostic category counts across target lanes:

| Category | Count |
|---|---:|
| diagnostic-only expected-span mismatch | 16 |
| answer too narrow | 15 |
| answer too broad | 3 |
| Korean synthesis/paraphrase mismatch | 3 |
| renderer formatting mismatch | 4 |
| scorer normalization gap | 3 |
| pass | 2 |

Interpretation:

- The first five TEXT rows remain failures in all lanes, but their strict JSON
  and locator residuals are clear.
- `text_namu_v2_0005` is not promoted into the first batch; it remains a
  secondary watchlist case with Lane A/B PASS and Lane C answer-renderer/span
  failure.
- Reference spans are used only after generation for audit-only scoring
  diagnostics. The artifact stores reference span hashes and counts, not raw
  expected/supporting/gold text for generation.
- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `generation_used_expected_answer=false`.
- `generation_used_gold_fields=false`.
- `generation_used_supporting_evidence=false`.

Primary machine artifacts:

| Artifact | Retention class | Current reason |
|---|---|---|
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_summary.json` | `machine_manifest` | Run-level counts, guardrails, source artifact identities, artifact hashes, and no-Markdown policy. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_results.jsonl` | `canonical_result_payload` | Full six-row lane payload needed for reproducibility and current artifact tests. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_spans.jsonl` | `canonical_result_payload` | Compact answer-span/renderer classification payload. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json` | `queue_source_of_truth` | Authoritative next queue after removing the first five TEXT rows. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_failure.json` | `forensic_debug_payload` | Taxonomy and row attribution details; kept because current guardrail tests read it. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_audit.jsonl` | `forensic_debug_payload` | Strict JSON, locator, citation, and answer audit details for regression forensics. |

Minimum artifact set proposal for future classification-only runs:

- Required durable set: `summary.json`, compact diagnostics JSONL,
  remaining queue JSON, and `status.jsonl`.
- Optional/debug-only candidate after test-contract update: full
  `results.jsonl`, failure attribution JSON, and actual response audit JSONL.
- Do not delete current v3_1_2/v3_1_3/v3_1_4 artifacts yet: the current test
  contract lists the durable JSON/JSONL families as expected report artifacts
  and asserts their guardrails.
- Do not create per-run Markdown for routine classification-only runs.

## 2026-05-18 - v3_1_1 Post Strict JSON / Locator Triage Measurement

Run family:
`official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage`

Scope:

- 29 official denominator rows.
- Lane A: v3 primary replay.
- Lane B: live LLM over source-bound retrieved top-k context.
- Lane C: live LLM over query-bound SearchUnit context only.

Metrics:

| Metric | Result |
|---|---:|
| Source family counts | PDF=4, TEXT=6, XLSX=19 |
| Lane A PASS | 24/29 |
| Lane B PASS | 20/29 |
| Lane C PASS | 17/29 |
| Lane B/C strict JSON parse failure | 0 |
| Lane B/C LLM-generated locator copy failure | 0 |
| PDF `source_pdf_path` mismatch | 0 |
| XLSX `row_label` mismatch | 0 |
| TEXT `text_locator` missing | 0 |
| Answer span mismatches | Lane B=9, Lane C=12 |
| Existing v3_1 PASS regressions recorded | 4 query/lane cases, all answer-span category |

Interpretation:

- Strict JSON and locator-copy infrastructure residuals are cleared for the
  post-triage measurement.
- Remaining triage should move to answer span / answer renderer behavior.
- The recorded regression count is diagnostic evidence, not a promotion gate.
- `generation_used_expected_answer=false`.
- `generation_used_gold_fields=false`.
- `generation_used_supporting_evidence=false`.
- `promotion_evidence=false`.

## 2026-05-18 - TEXT Locator Residual Triage

Run family:
`official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage`

Target row:

- `text_namu_v2_0012`

Metrics:

| Metric | Before | After |
|---|---:|---:|
| TEXT `text_locator` missing | 1 | 0 |
| LLM-generated locator missing failure | 1 | 0 |
| LLM-generated locator field mismatch failure | 0 | 0 |
| TEXT `text_locator` byte-equal | false/empty | true |
| TEXT `text_locator` normalized-equal | false/empty | true |

The repair uses only the source-bound canonical locator JSON already present in
prompt context. It does not use expected answers, supporting evidence, or gold
fields for generation.

## 2026-05-18 - Priority 1~5 Strict JSON / Locator Triage

Run family:
`official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage`

Target rows:

- `gq_pdf_section_question_001`
- `text_namu_v2_0012`
- `gq_auto_010`
- `gq_auto_023`
- `gq_xlsx_lookup_008`

Metrics:

| Metric | Before | After | Note |
|---|---:|---:|---|
| Lane B strict JSON parse failure | 2 | 0 | Parse failure removed |
| Strict JSON schema repair applied | 0 | 2 | Counted separately, not hidden as pure clean output |
| LLM-generated locator copy failure | 5 | 1 | Missing locator fields included |
| LLM-generated locator field mismatch | 3 | 0 | PDF path and XLSX row-label byte mismatches cleared |
| LLM-generated locator missing-field/missing-locator failure | 0 | 1 | `text_namu_v2_0012` residual |
| PDF `source_pdf_path` mismatch | 1 | 0 | `gq_auto_010` fixed |
| XLSX `row_label` mismatch | 2 | 0 | `gq_auto_023`, `gq_xlsx_lookup_008` fixed |

Interpretation:

- This is not promotion evidence.
- `answer_score` and `citation_support_score` are reference-only.
- `generation_used_expected_answer=false`.
- `generation_used_gold_fields=false`.
- `generation_used_supporting_evidence=false`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.

Primary machine artifacts:

- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_results.jsonl`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_summary.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_failure.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_audit.jsonl`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_delta.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_strict_json.json`

## 2026-05-18 - v3_1 All-Track Foundation Measurement

Run family:
`official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement`

Lane definitions:

- Lane A: v3 primary replay.
- Lane B: live LLM over source-bound retrieved top-k context.
- Lane C: live LLM over query-bound SearchUnit context only.

Current counts:

| Lane | PASS | Notes |
|---|---:|---|
| Lane A | 24/29 | Structured adapter retained for XLSX/PDF; TEXT uses LLM synthesis |
| Lane B | 18/29 | Before priority triage: strict JSON and locator-copy failures present |
| Lane C | 20/29 | Query-bound oracle-context isolation |

Interpretation:

- Lane A/B/C must not be mixed into one official score.
- The run is a foundation diagnostic, not silver/gold/promotion evidence.
- The triage queue had 12 rows before priority 1~5 stabilization.

Primary machine artifacts:

- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_results.jsonl`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_summary.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_failure.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_audit.jsonl`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_queue.json`

## Rolling Report Policy

Use these three human-facing files:

- `docs/rag-ingestion-progress.md`: current status, verification, guardrails, next steps.
- `docs/rag-ingestion-measurements.md`: measurement ladder and run-level before/after metrics.
- `docs/rag-ingestion-triage.md`: row-level triage queue, fixes, residuals, and user-decision boundaries.

Do not add new per-run Markdown reports for routine row-level triage. When a
report-style note is needed, append the short human-readable entry to
`docs/rag-ingestion-progress.md`; update this measurements ledger only for
run-level metric detail that belongs here. For machine outputs, prefer the
smallest durable JSON/JSONL set required by the run contract plus the
append-only status ledger; do not emit full `results.jsonl`, failure
attribution, or response audit payloads unless behavior changed or a
test-backed forensic contract requires them.
