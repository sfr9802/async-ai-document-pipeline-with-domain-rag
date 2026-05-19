# RAG Ingestion Triage

Last updated: 2026-05-19 KST.

This is the rolling row-level triage ledger. Keep it append-style like
`docs/rag-ingestion-progress.md`: add new triage entries here instead of
creating one Markdown file per run. Machine artifacts should stay compact:
write only the summary, queue, decision/inventory JSONL, and status event that a
triage phase actually needs. For report-style human summaries, append the short
entry to `docs/rag-ingestion-progress.md`; update this file only when row-level
queue or decision-boundary detail belongs here.

Historical `_archive/legacy` artifact paths below are logical provenance names.
Their physical generated payloads may live in the external runtime archive under
`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\`.

## Triage Policy

- Triage is diagnostic-only unless the user explicitly changes scope.
- Do not change expected answers, supporting evidence, relevance labels,
  answerability labels, or gold policy without a user decision.
- Do not create silver/gold/promotion evidence during triage.
- Do not use expected answers, supporting evidence, or gold fields as generation
  source.
- Keep Lane A/B/C separated in interpretation.

## Current Phase

Phase:
`user gold policy decision applied - implementation-safe residual queue open`

Status:
priority 1~5 plus the remaining `text_namu_v2_0012` TEXT locator residual have
completed diagnostic stabilization. The full 29-row post-triage measurement now
has strict JSON parse failure, LLM-generated locator copy failure, PDF
`source_pdf_path` mismatch, XLSX `row_label` mismatch, and TEXT `text_locator`
missing all at zero. v3_1_2 recorded the first classification-only
answer-span/renderer batch, v3_1_3 processed the v3_1_2 remaining queue with
general prompt/renderer/scorer-compatibility changes, and v3_1_4 processed the
PDF residual queue with source-bound table-axis disambiguation. v3_1_5 then
processed the v3_1_4 remaining queue as a classification-only coverage
diagnostic for `gq_auto_010`, and v3_1_6 applied a safe same-page source-bound
PDF paragraph/window expansion for the same row. The current machine remaining
queue is empty. v3_1_7 then created the all-track residual inventory and
confirmed that the active implementation queue is empty even though policy-bound
all-track residuals still exist. v3_1_8 prepared the human gold-policy packet
and decision matrix for those five rows. v3_1_9 has now applied the user-owned
`gold_overrides.csv` decision source and rescored existing Lane A/B/C surfaces
without live generation.

Source foundation run:
`official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement`

Current triage run:
`official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement`

Previous all-track source run:
`official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage`

## v3_1_9 User Decision Applied And Post-Rescore Queue

Source run:
`official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_summary.json`
- Applied overrides:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_applied_overrides.jsonl`
- Gold diff:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_gold_diff.jsonl`
- Rescored results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_rescored_results.jsonl`
- Remaining queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_remaining_triage_queue.json`

Applied override rows:

| Query ID | Source family | User decision applied | Gold-policy action |
|---|---|---|---|
| `text_namu_v2_0012` | TEXT | user decision applied | Narrow expected answer and supporting evidence to age/birthday scope |
| `text_namu_v2_0014` | TEXT | user decision applied | Narrow to the supported Adversary cameo entry |
| `text_namu_v2_0017` | TEXT | user decision applied | Narrow to the currently supported Silk Cat boy description |
| `text_namu_v2_0077` | TEXT | user decision applied | Narrow to the destination answer, Tokyo |
| `text_namu_v2_0084` | TEXT | user decision applied | Drop the catchphrase and keep the film-description span |

Scoring-only result after user policy application:

| Lane | Before | After |
|---|---:|---:|
| Lane A `v3_primary_replay` | `24/29` PASS | `27/29` PASS |
| Lane B `live_llm_retrieval_topk` | `24/29` PASS | `26/29` PASS |
| Lane C `live_llm_query_bound_oracle` | `24/29` PASS | `25/29` PASS |

Post-rescore remaining queue:

| Query ID | Remaining lane failures | Classification |
|---|---|---|
| `text_namu_v2_0014` | Lane C | Implementation-safe residual after settled gold policy |
| `text_namu_v2_0017` | Lane B/C | Implementation-safe residual after settled gold policy |
| `text_namu_v2_0077` | Lane A/B/C | Implementation-safe residual after settled gold policy |
| `text_namu_v2_0084` | Lane A/B/C | Implementation-safe residual after settled gold policy |

v3_1_8 is now user decision applied, not awaiting user policy decision. The
remaining queue does not require another user policy packet unless a concrete
conflict appears between override rows and official denominator metadata.
Later work may inspect renderer, scorer, prompt, or retrieval behavior for the
four remaining query ids, but v3_1_9 itself did not implement those changes.

Guardrail status:

- User-approved gold policy mutation occurred:
  `expected_answer_mutation=true`, `supporting_evidence_mutation=true`,
  `gold_policy_mutation=true`, `user_policy_decision_applied=true`.
- No renderer/scorer/retrieval/production/silver/promotion behavior changed.
- Existing generated answer surfaces were rescored only; live generation was
  not rerun.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.

## v3_1_8 Gold-Policy Review Packet Status

Source run:
`official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_summary.json`
- Human review packet:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_human_review_packet.json`
- Decision matrix:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_decision_matrix.jsonl`
- Remaining queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_remaining_triage_queue.json`

Current status:

- User decision has been applied by v3_1_9.
- The v3_1_8 packet is no longer awaiting user policy decision.
- Active implementation queue has moved from empty/policy-blocked to the v3_1_9
  implementation-safe residual queue above.
- Silver remains closed.
- v3_1_6 sibling-hash drift was recorded as metadata drift only; historical
  v3_1_6 artifacts were not rewritten.
- Raw expected/supporting/gold-policy material is present only inside the human
  review packet with `human_review_only=true`, `generation_source=false`,
  `not_silver_source=true`, and `not_gold_mutation=true`.

User decision options for every row:

- `keep_current_strict_reference_boundary`
- `approve_scorer_or_renderer_review_without_gold_mutation`
- `revise_gold_or_label_policy`

The user-approved decision source has been applied from `gold_overrides.csv`.
Do not create another user policy packet unless override metadata conflicts
with the official denominator.

Policy-review rows:

| Query ID | Source family | Lane failures | Packet status |
|---|---|---|---|
| `text_namu_v2_0012` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; all lanes PASS after v3_1_9 rescore |
| `text_namu_v2_0014` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; Lane C remains implementation-safe residual |
| `text_namu_v2_0017` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; Lane B/C remain implementation-safe residuals |
| `text_namu_v2_0077` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; Lane A/B/C remain implementation-safe residuals |
| `text_namu_v2_0084` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; Lane A/B/C remain implementation-safe residuals |

Guardrail status:

- Diagnostic-only.
- Not promotion evidence.
- No renderer, scorer, retrieval, denominator, production, silver, gold,
  expected-answer, supporting-evidence, relevance-label, answerability-label, or
  human-label mutation.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score.

## v3_1_7 Residual Inventory And Decision Boundary

Source run:
`official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_summary.json`
- Residual inventory:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_all_track_residual_inventory.jsonl`
- Remaining queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_remaining_triage_queue.json`
- User decision packet:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_user_decision_packet.json`

Decision boundary:

- Active remaining queue: cleared.
- Active implementation queue: empty.
- All-track residuals still exist: five TEXT query ids across all three lanes.
- No residual is currently safe to fix without a user gold/relevance/
  answerability policy decision.
- Do not change expected answers, supporting evidence, labels, scorer policy, or
  renderer behavior from this inventory alone.

Residual query ids:

| Query ID | Source family | Lane failures | Current handling |
|---|---|---|---|
| `text_namu_v2_0012` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |
| `text_namu_v2_0014` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |
| `text_namu_v2_0017` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |
| `text_namu_v2_0077` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |
| `text_namu_v2_0084` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |

Residual buckets:

- `gold_policy_review_candidate=15`
- `answer_renderer_followup_candidate=15`
- `scorer_normalization_review_candidate=3`
- `implementation_safe_followup=0`
- `retrieval_context_followup_candidate=0`
- `relevance_label_review_candidate=0`
- `answerability_label_review_candidate=0`

Packet status:
superseded by v3_1_8 packet preparation above; active implementation queue
remains empty until a user policy decision is applied.

## Post-Triage Queue

Source run:
`official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage`

Strict JSON / locator residual count: `0`.

Queue source of truth:

- The authoritative queue is the machine artifact
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_1_post_locator_queue.json`.
- If this file and human queue notes differ, use the machine artifact. That is
  why the first batch includes `text_namu_v2_0012`, and why
  `text_namu_v2_0005` is kept as queue rank 12 instead of being dropped.
- The older Later Triage Queue text was stale: it omitted
  `text_namu_v2_0012` and `text_namu_v2_0005`, and included `gq_auto_037`,
  which is not in the machine post-triage queue.

The post-triage queue is answer-span / answer-renderer oriented:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `text_namu_v2_0012` | TEXT answer synthesis / expected span |
| 2 | `text_namu_v2_0014` | TEXT answer synthesis / expected span |
| 3 | `text_namu_v2_0017` | TEXT answer synthesis / expected span |
| 4 | `text_namu_v2_0077` | TEXT answer synthesis / expected span |
| 5 | `text_namu_v2_0084` | TEXT answer synthesis / expected span |
| 6 | `gq_auto_010` | PDF answer span |
| 7 | `gq_auto_024` | PDF/XLSX answer span |
| 8 | `gq_auto_030` | PDF answer span |
| 9 | `gq_auto_043` | XLSX answer span |
| 10 | `gq_pdf_section_question_001` | PDF answer span |
| 11 | `gq_xlsx_date_number_format_001` | XLSX date/number answer span |
| 12 | `text_namu_v2_0005` | TEXT answer span |

Recorded post-triage metrics:

- Lane A PASS: `24/29`.
- Lane B PASS: `20/29`.
- Lane C PASS: `17/29`.
- Lane B/C strict JSON parse failure: `0`.
- Lane B/C LLM-generated locator copy failure: `0`.
- PDF `source_pdf_path` mismatch: `0`.
- XLSX `row_label` mismatch: `0`.
- TEXT `text_locator` missing: `0`.
- Existing v3_1 PASS regressions recorded: `4` query/lane cases, all answer-span category.

## Answer Span / Renderer Batch 1 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage`

Scope:

- Diagnostic-only, classification-only over v3_1_1 artifacts.
- No generation prompt, output parser, answer renderer, normalization, scorer,
  locator-copy, or SearchUnit payload behavior was changed.
- No all-track rerun was performed because no behavior changed before this
  diagnostic artifact.

Selected rows:

| Query ID | Queue decision | Lane result | Diagnostic classification |
|---|---|---|---|
| `text_namu_v2_0012` | first batch, rank 1 | Lane A/B/C fail | diagnostic-only expected-span mismatch, answer too narrow, scorer normalization gap |
| `text_namu_v2_0014` | first batch, rank 2 | Lane A/B/C fail | diagnostic-only expected-span mismatch, answer too narrow; Lane C also flags answer too broad, renderer formatting, and Korean paraphrase mismatch |
| `text_namu_v2_0017` | first batch, rank 3 | Lane A/B/C fail | diagnostic-only expected-span mismatch, answer too narrow; Lane A also flags renderer formatting mismatch |
| `text_namu_v2_0077` | first batch, rank 4 | Lane A/B/C fail | diagnostic-only expected-span mismatch; mixed answer too broad / too narrow flags by lane, with Lane B Korean renderer/paraphrase mismatch |
| `text_namu_v2_0084` | first batch, rank 5 | Lane A/B/C fail | diagnostic-only expected-span mismatch and answer too narrow |
| `text_namu_v2_0005` | secondary watchlist, rank 12 | Lane A/B pass, Lane C fail | Lane C diagnostic-only expected-span mismatch, answer too narrow, renderer formatting mismatch, Korean paraphrase mismatch |

Target-batch metrics:

- Target rows: `6`.
- Primary first-batch rows: `5`.
- Secondary watchlist rows: `1`.
- Target Lane A PASS: `1/6`.
- Target Lane B PASS: `1/6`.
- Target Lane C PASS: `0/6`.
- Primary first-batch Lane A/B/C PASS: `0/5` each.
- Diagnostic categories across target lanes:
  `diagnostic_only_expected_span_mismatch=16`, `answer_too_narrow=15`,
  `answer_too_broad=3`, `renderer_formatting_mismatch=4`,
  `korean_synthesis_paraphrase_mismatch=3`, `scorer_normalization_gap=3`,
  `pass=2`.

Guardrail result:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- Reference spans are audit-only; the diagnostic artifact stores hashes/counts
  and does not embed raw reference span text for generation.

Remaining queue after batch 1:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `gq_auto_010` | PDF answer span |
| 2 | `gq_auto_024` | PDF/XLSX answer span |
| 3 | `gq_auto_030` | PDF answer span |
| 4 | `gq_auto_043` | XLSX answer span |
| 5 | `gq_pdf_section_question_001` | PDF answer span |
| 6 | `gq_xlsx_date_number_format_001` | XLSX date/number answer span |
| 7 | `text_namu_v2_0005` | secondary TEXT watchlist, Lane C-only answer renderer/span |

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json`

Artifact policy for this triage lane:

- Queue source of truth: the machine remaining-queue JSON above.
- Human-facing source of truth: this rolling triage document plus
  `docs/rag-ingestion-progress.md` and `docs/rag-ingestion-measurements.md`.
- Canonical classification payload: v3_1_2
  `answer_span_diagnostics.jsonl`; use it for row/lane category inspection
  before opening full debug payloads.
- Forensic debug payloads: v3_1_2 `results.jsonl`,
  `failure_attribution.json`, and `actual_response_audit.jsonl`. Keep them for
  now because artifact tests read them and because they preserve strict
  JSON/locator regression evidence.
- Stale or previous queue text must not override the machine queue. The older
  stale mention of `gq_auto_037` is retained only as historical drift evidence
  above, not as an active queue item.
- Per-run Markdown reports remain out of scope for routine classification-only
  triage.

## Remaining Queue Batch 2 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage`

Source of truth:

- The authoritative input queue is
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json`.
- Rolling docs are human-facing narrative only. If docs and machine queue
  differ, use the machine queue. The stale `gq_auto_037` human queue wording is
  not active.

Scope:

- Target rows: `gq_auto_010`, `gq_auto_024`, `gq_auto_030`,
  `gq_auto_043`, `gq_pdf_section_question_001`,
  `gq_xlsx_date_number_format_001`, `text_namu_v2_0005`.
- Allowed changes used: prompt answer instructions, source-bound answer
  renderer, and post-generation scorer compatibility normalization.
- Forbidden work stayed closed: no expected/supporting/gold mutation, no
  silver/gold/promotion evidence, no threshold tuning, no winner selection, no
  production namespace mutation, and no candidate artifacts as generation
  source.

Target row changes:

| Query ID | Before | After | Category |
|---|---|---|---|
| `gq_auto_010` | Lane B/C fail | Lane B/C fail | PDF retrieval/context answer-span insufficiency; expected numeric span not in cited context. |
| `gq_auto_024` | Lane C fail | PASS all lanes | Korean source phrase renderer / paraphrase compatibility. |
| `gq_auto_030` | Lane C fail | PASS all lanes | PDF table value selected correctly after prompt table-axis instruction. |
| `gq_auto_043` | Lane B/C fail | PASS all lanes | XLSX date normalized-value compatibility. |
| `gq_pdf_section_question_001` | Lane B/C fail | Lane B/C fail | PDF table repeated amount/growth columns still select wrong value. |
| `gq_xlsx_date_number_format_001` | Lane B/C fail | PASS all lanes | XLSX date normalized-value compatibility. |
| `text_namu_v2_0005` | Lane C fail | PASS all lanes | Korean answer-renderer/language drift fixed; Lane A/B unchanged PASS. |

Metrics:

- Target Lane A/B/C PASS: `7/7`, `5/7`, `5/7` after v3_1_3
  (before: `7/7`, `3/7`, `0/7`).
- Target answer-span mismatch Lane A/B/C: `0`, `2`, `2` after v3_1_3
  (before: `0`, `4`, `7`).
- 29-row all-track Lane A/B/C PASS: `24/29`, `22/29`, `22/29` after
  v3_1_3 (before v3_1_1: `24/29`, `20/29`, `17/29`).
- 29-row all-track answer-span mismatch Lane A/B/C: `0`, `7`, `7` after
  v3_1_3 (before: `0`, `9`, `12`).
- Strict JSON parse residual remains `0` by lane.
- LLM-generated locator copy/missing/field mismatch residual remains `0` by
  lane.
- PDF `source_pdf_path` mismatch, XLSX `row_label` mismatch, and TEXT
  `text_locator` missing remain `0`.

Remaining queue after v3_1_3:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `gq_auto_010` | PDF cited context does not include the expected numeric span (`4.9%`, `0.8%p`). |
| 2 | `gq_pdf_section_question_001` | PDF table repeated amount/growth groups still require value disambiguation for `수출입차 금액`. |

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_3_remaining_queue.json`

Guardrail audit:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`.

## PDF Residual Batch 3 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage`

Source of truth:

- The authoritative input queue is
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_3_remaining_queue.json`.
- Rolling docs are human-facing narrative only. If docs and machine queue
  differ, use the machine queue.

Scope:

- Target rows: `gq_auto_010`, `gq_pdf_section_question_001`.
- Allowed changes used: source-bound PDF table-axis answer renderer for
  repeated amount/growth columns, plus post-generation diagnostic
  classification for PDF context insufficiency.
- Forbidden work stayed closed: no expected/supporting/gold mutation, no
  silver/gold/promotion evidence, no threshold tuning, no winner selection, no
  production namespace mutation, and no candidate artifacts as generation
  source.

Target row changes:

| Query ID | Before | After | Category |
|---|---|---|---|
| `gq_auto_010` | Lane B/C fail | Lane B/C fail | Retrieval/context insufficiency: cited paragraph lacks the numeric span, so the renderer must not invent it. |
| `gq_pdf_section_question_001` | Lane B/C fail | PASS all lanes | Source-bound PDF table-axis disambiguation selected `수출입차 금액` value `518.4`. |

Metrics:

- Target Lane A/B/C PASS: `2/2`, `1/2`, `1/2` after v3_1_4
  (before: `2/2`, `0/2`, `0/2`).
- Target answer-span mismatch Lane A/B/C: `0`, `1`, `1` after v3_1_4
  (before: `0`, `2`, `2`).
- 29-row all-track Lane A/B/C PASS: `24/29`, `23/29`, `23/29` after
  v3_1_4 (before v3_1_3: `24/29`, `22/29`, `22/29`).
- 29-row all-track answer-span mismatch Lane A/B/C: `0`, `6`, `6` after
  v3_1_4 (before: `0`, `7`, `7`).
- Strict JSON parse residual remains `0` by lane.
- LLM-generated locator copy/missing/field mismatch residual remains `0` by
  lane.
- PDF `source_pdf_path` mismatch, XLSX `row_label` mismatch, and TEXT
  `text_locator` missing remain `0`.

Remaining queue after v3_1_4:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `gq_auto_010` | Source-bound retrieval/context coverage: cited context lacks numeric answer span. |

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_4_pdf_residual_queue.json`

Guardrail audit:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`.

## Source-Bound Coverage Batch 4 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic`

Source of truth:

- The authoritative input queue is
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_4_pdf_residual_queue.json`.
- Queue preflight confirmed only `gq_auto_010` remains, strict JSON /
  locator residual count is `0`, `diagnostic_only=true`,
  `promotion_evidence=false`, and `reference_span_text_embedded=false`.

Scope:

- Target row: `gq_auto_010` only.
- This was classification-only: no live generation, answer renderer/scorer
  change, SearchUnit export change, index rebuild, denominator mutation, gold
  mutation, label mutation, production mutation, threshold tuning, winner
  selection, promotion gate, or official retrieval metric computation.
- Audit numeric spans were used only as post-hoc static coverage probes and
  were recorded by hash/count in the compact diagnostic artifact.

Coverage findings:

| Surface | Result |
|---|---|
| v3_1_4 Lane B/C cited SearchUnit | `7bf516bf-2a17-4303-86d8-3cffaa04846e` |
| Current cited SearchUnit contains all audit numeric spans | no |
| Any same-document SearchUnit contains all audit numeric spans | no |
| Any adjacent page/window SearchUnit contains all audit numeric spans | no |
| Raw/source PDF text extraction contains all audit numeric spans | yes |

Classification:

`query_bound_searchunit_too_narrow`

Rationale: Lane A still passes through v3 primary replay. Lane B/C fail with
`LLM_EXPECTED_SPAN_MISMATCH` while citing the same source-bound paragraph. The
paragraph supports the general unemployment-rise claim but does not contain the
numeric answer span. Raw PDF extraction can see the numeric span on the same
source page, but the current query-bound cited SearchUnit and same-document
SearchUnit surfaces in the non-production official denominator index do not.

Repair decision:

- No non-production SearchUnit export/windowing/index repair was applied in
  this run.
- No 29-row all-track remeasurement was necessary because no retrieval,
  export, index, generation, renderer, or scorer behavior changed.
- The next decision is whether to implement a safe source-bound PDF
  paragraph/window expansion before live generation.
- Verification is recorded in `docs/rag-ingestion-progress.md`: both current
  pytest profiles PASS with 133 tests, py_compile PASS, doctor selected checks
  PASS, and `git diff --check` PASS with line-ending warnings only.

Remaining queue after v3_1_5:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `gq_auto_010` | Safe source-bound PDF paragraph/window coverage decision: raw PDF contains the numeric span, but current SearchUnit surfaces do not. |

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_5_gq010_coverage_queue.json`

Guardrail audit:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`.
- `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`.
- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score were not computed.

## Source-Bound Coverage Repair Branch Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic`

Source of truth:

- The authoritative input queue is
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_5_gq010_coverage_queue.json`.
- Queue preflight confirmed only `gq_auto_010` remained and the v3_1_5
  classification was `query_bound_searchunit_too_narrow`.

Scope:

- Target row: `gq_auto_010` only.
- Safe PDF paragraph/window expansion was attempted and applied.
- Locator-safe metadata was available: same `source_pdf_path`, same
  `document_version_id`, page `8`, physical page index `7`, bbox
  `[63.65, 95.06, 341.94, 163.68]`, region type `paragraph_window`, and
  expansion unit `pdfwin_b1c6527f848018640ad5ed231877c662`.
- The expansion came from safe local source PDF extraction and was represented
  as non-production diagnostic context expansion. It did not mutate the
  official denominator registry, production indexes, gold, labels, expected
  answers, or supporting evidence.

Result:

| Lane | Before v3_1_6 | After v3_1_6 |
|---|---|---|
| Lane A `v3_primary_replay` | PASS | PASS |
| Lane B `live_llm_retrieval_topk` | `LLM_EXPECTED_SPAN_MISMATCH` | PASS |
| Lane C `live_llm_query_bound_oracle` | `LLM_EXPECTED_SPAN_MISMATCH` | PASS |

All-track remeasurement:

- Required because prompt context assembly changed.
- Lane A/B/C PASS changed from `24/29`, `23/29`, `23/29` to `24/29`,
  `24/29`, `24/29`.
- Strict JSON parse residuals, LLM-generated locator copy/missing/field mismatch
  residuals, PDF `source_pdf_path` mismatch, XLSX `row_label` mismatch, and
  TEXT `text_locator` missing remain zero.
- No non-target row received context expansion and no non-target unexpected
  change was recorded.

Remaining queue after v3_1_6: empty.

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/v3_1_6_gq010_pdfwin_queue.json`

Guardrail audit:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`.
- `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`.
- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score were not computed.

## TEXT Locator Residual Result

`text_namu_v2_0012` TEXT locator residual:

- TEXT `text_locator` missing: `1 -> 0`.
- LLM-generated locator missing failure: `1 -> 0`.
- `text_locator_byte_equal=true`.
- `text_locator_normalized_equal=true`.
- The row now fails on answer span / synthesis, not locator schema.

## Priority 1~5 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage`.

| Priority | Query ID | Original issue | Current result |
|---:|---|---|---|
| 1 | `gq_pdf_section_question_001` | Lane B strict JSON parse failure | Parse failure removed; now answer-span triage remains |
| 2 | `text_namu_v2_0012` | Lane B strict JSON parse failure | Parse failure removed after schema repair accounting; TEXT locator residual removed by the later residual run |
| 3 | `gq_auto_010` | PDF `source_pdf_path` locator mismatch | PDF path byte-equal and normalized-equal |
| 4 | `gq_auto_023` | XLSX `row_label` locator mismatch | Row label byte-equal and normalized-equal |
| 5 | `gq_xlsx_lookup_008` | XLSX `row_label` locator mismatch | Row label byte-equal and normalized-equal |

Priority 1~5 metrics:

- Strict JSON parse failure: `2 -> 0`.
- Strict JSON schema repair applied: `0 -> 2`.
- LLM-generated locator copy failure: `5 -> 1`.
- LLM-generated locator field mismatch: `3 -> 0`.
- LLM-generated locator missing-field/missing-locator failure: `0 -> 1`.
- PDF `source_pdf_path` mismatch: `1 -> 0`.
- XLSX `row_label` mismatch: `2 -> 0`.

Residual:

- The `text_namu_v2_0012` TEXT locator missing/schema residual was removed by
  the later TEXT locator residual run.
- Remaining priority 1~5 failures are answer-span / answer-renderer failures,
  not strict JSON or locator-copy failures.

## Next Triage Step

The v3_1_6 machine remaining queue is empty. Keep future work diagnostic-only
unless the user explicitly opens a new repair branch: do not create silver,
change gold, tune thresholds, run a promotion gate, mutate production, or
synthesize missing numeric spans.

## Later Triage Queue

After v3_1_6, use the machine remaining-queue artifact above rather than older
stale human lists. Current later queue: empty.

## User-Decision Boundary

Leave these as user decisions:

- Expected answer changes.
- Supporting evidence changes.
- Relevance label changes.
- Answerability label changes.
- Gold policy changes.
- Silver/gold promotion decisions.
