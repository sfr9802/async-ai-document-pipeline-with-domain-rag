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
`v3_4_1 official retrieval qrels candidate packet ready for human review`

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
and decision matrix for those five rows. v3_1_9 applied the user-owned
`gold_overrides.csv` decision source and rescored existing Lane A/B/C surfaces
without live generation. v3_2_0 then established the settled current-system live
baseline, v3_2_1 triaged only the remaining four TEXT rows, and v3_2_2 reran all
29 rows after the one safe scorer fix. v3_2_3 has now reconciled the v3_2_2
machine queue into actionability lanes: Lane A-only residuals are frozen replay
residuals, `gq_auto_010` is a PDF context-provenance follow-up, and live TEXT
B/C prompt-span work is limited to three rows. v3_2_4 then proved that
`gq_auto_010` is open because the v3_1_6 PDF window expansion is not wired into
the v3_2 measurement path. v3_2_5 has now reused that existing v3_1_6 safe PDF
window sidecar in the current v3_2 measurement path and closed `gq_auto_010`;
the active live B/C implementation queue is now limited to
`text_namu_v2_0014`, `text_namu_v2_0017`, and `text_namu_v2_0084`. v3_2_6
then applied a lane-scoped general TEXT prompt/span rule. It closed
`text_namu_v2_0014` Lane C and left `text_namu_v2_0017` plus
`text_namu_v2_0084` as diagnostic-only prompt/span residuals after the prompt
rule. v3_2_7 has now closed the post-fix sequence with a compact
status-ledger-only event and rolling report update: `gq_auto_010` and
`text_namu_v2_0014` are closed, `text_namu_v2_0017` and
`text_namu_v2_0084` remain diagnostic-only after the prompt rule,
`text_namu_v2_0012` and `text_namu_v2_0077` remain frozen Lane A replay
residuals, and no next implementation phase is opened. v3_3_0 then audited the
v3_2_3 through v3_2_7 source-of-truth chain without reopening the queue or
changing behavior. v3_3_1 then checked whether the existing source-bound
SearchUnit material can safely seed anti-overfit silver source manifests; it
cannot, because all currently available source-bound rows overlap the official
29-row denominator. v3_3_2 then prepared only the human retrieval
relevance/answerability label-design packet for future official ranking
metrics; it did not compute nDCG, MRR, Hit@K, collapse Lane A/B/C, or create
labels/qrels. v3_4_0 now records the official retrieval metric contract and
qrels schema only. It defines Hit@1/3/5, MRR@5, nDCG@5, micro overall, and
macro-by-source-family boundaries, but leaves official metrics blocked until
approved qrels labels exist. v3_4_1 then emits only a human-labelable qrels
candidate packet from source-bound official-denominator retrieval/oracle
artifacts. The packet keeps every relevance and answerability label pending for
human review and does not compute ranking metrics.

Source foundation run:
`official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement`

Current triage run:
`official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet`

Previous all-track source run:
`official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`

## v3_4_1 Official Retrieval Qrels Candidate Packet

Source artifacts:

- `ai/eval/eval_queries/official_denominator_registry.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`
- `ai/eval/reports/rag-ingestion/status.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`

Human-review artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.csv`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_summary.json`

Candidate packet status:

| Bucket | Count/status |
|---|---:|
| query_ids | 29 |
| qrels candidate rows | 219 |
| PDF candidates | 22 |
| TEXT candidates | 24 |
| XLSX candidates | 173 |
| retrieved_topk_candidate rows | 145 |
| query_bound_oracle_candidate rows | 29 |
| structured_adapter_candidate rows | 45 |
| skipped candidates | 0 |

Review fields:

- Each row has `query_id`, `source_family`, `rank`, `lane_source`,
  `candidate_role`, `document_version_id`, `search_unit_id`, source-bound
  locator JSON, source excerpt/hash, and pending human-review fields.
- Required pending values are `relevance_label=pending`,
  `answerability_label=pending`, and `label_status=pending_user_review`.
- Every candidate row records `official_denominator_overlap=true`,
  `qrels_candidate=true`, `generation_source=false`, and
  `promotion_evidence=false`.
- `suggested_label_reason` is diagnostic review context only; it is not a final
  relevance or answerability label.

Guardrails:

- No relevance label, answerability label, expected answer, supporting evidence,
  gold, denominator, prompt, retrieval, renderer, scorer, index/export, silver,
  production, promotion, threshold tuning, or winner-selection mutation.
- No official Hit@K, MRR, nDCG, micro/macro retrieval aggregate, or collapsed
  Lane A/B/C score was computed.
- Official metrics remain blocked until the user approves qrels labels and the
  selected denominator policy.

## v3_4_0 Official Retrieval Metric Contract

Source artifacts:

- `ai/eval/reports/rag-ingestion/status.jsonl`
- `ai/eval/eval_queries/official_denominator_registry.json`
- `ai/eval/reports/rag-ingestion/metric_input_v1.json`
- `ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`

Contract artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_qrels_schema.json`

Contract status:

| Bucket | v3_4_0 contract | User decision needed | Metric status |
|---|---|---|---|
| qrels denominator | Options A all 29 rows, B track-by-track opening, C only rows with settled retrieval labels | Select A/B/C and any track opening rule | Retrieval metrics blocked |
| relevance labels | `0 NOT_RELEVANT`, `1 TOPIC_RELATED`, `2 SUPPORTING_CONTEXT`, `3 EXACT_ANSWER_EVIDENCE` | Approve schema and exact positive rule | Retrieval metrics blocked |
| answerability labels | `0 NOT_ANSWERABLE`, `1 RELATED_BUT_NOT_ANSWERABLE`, `2 PARTIALLY_ANSWERABLE`, `3 FULLY_ANSWERABLE` | Approve schema and answerability gate | Retrieval metrics blocked |
| Hit@K/MRR positive rule | Default proposal: relevance >= 3 and answerability >= 3 | Approve or override before labels apply | Retrieval metrics blocked |
| nDCG gain rule | Default gain is relevance grade; gated variant maps gain to 0 when answerability < 2 | Approve default and zero-IDCG policy | Retrieval metrics blocked |
| legacy/silver qrel sources | XLSX legacy retrieval CSV and XLSX silver retrieval-evidence files are prohibited as current official qrels | User may approve a future migration, but not in v3_4_0 | Retrieval metrics blocked |

Metric list:

- Hit@1, Hit@3, Hit@5, MRR@5, and nDCG@5.
- Micro overall over eligible labeled rows.
- Macro by source_family: TEXT, PDF, XLSX.

Guardrails:

- No relevance labels, answerability labels, qrels, expected answers,
  supporting evidence, gold, denominator, prompt, retrieval, renderer, scorer,
  index/export, silver, production, promotion, threshold tuning, or
  winner-selection mutation.
- No official nDCG, MRR, Hit@K, micro/macro retrieval metric, or collapsed
  Lane A/B/C score was computed.
- Official answer/citation results and official retrieval metrics must remain
  separate README sections.
- The active implementation queue remains empty and no next implementation
  phase is opened.

## v3_3_2 Retrieval Relevance/Answerability Label-Design Packet

Run family:
`official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet`

Source artifacts:

- `ai/eval/eval_queries/official_denominator_registry.json`
- `ai/eval/reports/rag-ingestion/metric_input_v1.json`
- `ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/build.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`

Design packet status:

| Bucket | Current state | User decision needed | Metric status |
|---|---|---|---|
| answer/citation denominator | 29 rows: PDF=4, TEXT=6, XLSX=19 | Whether these rows may be re-adjudicated into retrieval qrels or stay answer/citation-only | Retrieval metrics blocked |
| relevance labels | No official retrieval relevance labels are settled | Binary versus graded labels; what counts as positive for Hit@K/MRR | Retrieval metrics blocked |
| answerability labels | Existing harness has a 0-3 answerability family, but no current official labels for this denominator | Whether row-level, bundle-level, or both answerability judgments gate official metrics | Retrieval metrics blocked |
| evidence policy | v3_2_6 has query-bound and retrieved top-k context artifacts | Strict query-bound SearchUnit-only versus broader source-bound same-document/window/structured evidence | Retrieval metrics blocked |
| structured XLSX/PDF adapters | Adapter PASS is deterministic answer/citation evidence, not a qrel | Whether XLSX cell/range and PDF FILE-vs-CONTENT cases need separate official retrieval lanes | Retrieval metrics blocked |

Proposed schema options:

- Relevance option A: `RELEVANT`, `IRRELEVANT`.
- Relevance option B: `EXACT_ANSWER_EVIDENCE`, `SUPPORTING_CONTEXT`,
  `TOPIC_RELATED`, `NOT_RELEVANT`.
- Answerability option A: reuse `NOT_RELEVANT`,
  `RELATED_BUT_NOT_ANSWERABLE`, `PARTIALLY_ANSWERABLE`,
  `FULLY_ANSWERABLE`.
- Answerability option B: the same 0-3 scale plus flags for
  `PDF_FILE_IDENTITY`, `PDF_CONTENT`, `XLSX_CELL_RANGE`, and
  `MULTI_UNIT_BUNDLE_REQUIRED`.
- Required record fields for any later qrel artifact: `query_id`,
  `source_family`, `document_version_id`, `search_unit_id`, source-bound
  locator, `label_status=pending`, label provenance, dataset/index/config
  version, and blank human decision fields until the user fills them.

User-owned judgments:

- Relevance: whether a candidate SearchUnit is exact evidence, support-only,
  topic-related, or irrelevant for the query.
- Answerability: whether the retrieved unit or top-k bundle can answer the
  query fully, partially, only topically, or not at all.
- Gold policy: whether existing answer/citation gold policy remains sufficient
  for retrieval ranking or needs a separate qrels policy.
- Expected answer/evidence: whether existing expected answer/evidence should be
  reused as labeler context, revised, or excluded from retrieval qrels review.
- Denominator policy: whether to include all 29 rows, open track-by-track, or
  exclude rows until source-family-specific policies are settled.

Guardrails:

- No relevance label, answerability label, expected answer, supporting evidence,
  gold, denominator, prompt, retrieval, renderer, scorer, index/export, silver,
  production, promotion, threshold tuning, or winner-selection mutation.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.
- The active implementation queue remains empty and no next implementation
  phase is opened.

## v3_3_1 Answer/Citation Silver Source-Manifest Readiness

Source artifacts:

- `ai/eval/silver/answer_citation_silver_manifest_v1.json`
- `ai/eval/silver/answer_citation_silver_readiness_v1.json`
- `ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `ai/eval/eval_queries/official_denominator_registry.json`

Decision:

| Bucket | Count | Status | Next phase |
|---|---:|---|---|
| official-denominator source-bound SearchUnits | 29 | locator-complete and source-text available, but official-overlap | `none` |
| eligible non-official TEXT silver source candidates | 0 | blocked; no safe source manifest rows | `none` |
| eligible non-official XLSX silver source candidates | 0 | blocked; no safe source manifest rows | `none` |
| eligible non-official PDF silver source candidates | 0 | blocked; no safe source manifest rows | `none` |

Readiness boundary:

- Minimum safe source-candidate schema is now explicit:
  `query_id` or `candidate_id`, `source_family`, source-bound locator,
  `document_version_id`, `search_unit_id`, source text availability,
  `generation_source=false`, `promotion_evidence=false`, and
  `official_denominator_overlap=false`.
- The current source-bound official-denominator index has 29/29 rows with
  `official_denominator_overlap=true`, so it must not be copied into
  dev/holdout tuning silver.
- No silver JSONL rows were created. No expected answers, supporting evidence,
  relevance labels, answerability labels, gold labels, official denominator
  rows, production surfaces, promotion evidence, or official retrieval ranking
  metrics were created or changed.
- The active implementation queue remains empty and no next implementation
  phase is opened.

## v3_3_0 Post-Closure Source-Of-Truth Audit

Source closure run:
`official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup`

Audit run:
`official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit`

Machine artifacts:

- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Bucket | Query IDs | Status | Next phase |
|---|---|---|---|
| `frozen_lane_a_replay_residual` | `text_namu_v2_0012`, `text_namu_v2_0077` | Lane A-only frozen replay residuals, not live prompt targets | `none` |
| `live_bc_text_prompt_span_residual` | `text_namu_v2_0017`, `text_namu_v2_0084` | `diagnostic_only_after_prompt_rule`; live B/C still miss the expected span after the general prompt rule | `none` |
| `pdf_context_residual` | none | `gq_auto_010` remains closed by the v3_2_5 reuse of the existing v3_1_6 PDF window overlay | `none` |
| `scorer_policy_closed` | `text_namu_v2_0077` | Lane B/C scorer-policy closure is preserved; remaining Lane A failure is frozen replay only | `none` |

Audit boundary:

- v3_2_3 uses the v3_2_2 queue/results as the machine source for actionability
  classification.
- v3_2_4 uses v3_2_3 as the gate and proves the `gq_auto_010` PDF context gap.
- v3_2_5 uses v3_2_4 plus the existing v3_1_6 PDF window sidecar and closes
  only `gq_auto_010`.
- v3_2_6 uses the v3_2_5 queue and closes only `text_namu_v2_0014`.
- v3_2_7 remains the compact closure status event in `status.jsonl`.
- No next implementation phase is opened by v3_3_0.
- No per-run Markdown report was written.

Guardrail status:

- `diagnostic_only=true`, `promotion_evidence=false`.
- `behavior_change_made=false` and `implementation_change_made=false` for
  v3_3_0.
- `scorer_behavior_mutation=false`; v3_3_0 does not reopen the v3_2_2 scorer
  closure.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, retrieval, renderer, scorer, index/export,
  production, silver, promotion, threshold tuning, winner selection, official
  nDCG, MRR, Hit@K, or collapsed Lane A/B/C score changed.

## v3_2_7 Post-Fix Closure And Rolling Report Cleanup

Source queue:
`official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`

Closure run:
`official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup`

Machine artifacts:

- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Bucket | Query IDs | Status | Next phase |
|---|---|---|---|
| `frozen_lane_a_replay_residual` | `text_namu_v2_0012`, `text_namu_v2_0077` | Lane A-only frozen replay residuals, not live prompt targets | `none` |
| `live_bc_text_prompt_span_residual` | `text_namu_v2_0017`, `text_namu_v2_0084` | `diagnostic_only_after_prompt_rule`; live B/C still miss the expected span after the general prompt rule | `none` |
| `pdf_context_residual` | none | `gq_auto_010` remains closed by the v3_2_5 reuse of the existing v3_1_6 PDF window overlay | `none` |
| `scorer_policy_closed` | `text_namu_v2_0077` | Lane B/C scorer-policy closure is preserved; remaining Lane A failure is frozen replay only | `none` |

Queue boundary:

- `gq_auto_010` is closed by the existing v3_1_6 safe PDF window overlay
  being available to the v3_2 measurement path.
- `text_namu_v2_0014` is closed by the v3_2_6 TEXT prompt/span rule.
- The active implementation queue is empty; no next implementation phase is
  opened by v3_2_7.
- The remaining `text_namu_v2_0017` and `text_namu_v2_0084` entries are
  diagnostic-only after the prompt rule and require user-owned gold,
  answerability, or scorer-policy judgment before any future mutation.

Evidence:

- Current Lane A/B/C pass counts are `24/29`, `27/29`, and `27/29`.
- Answer quality averages are Lane A=`0.8276`, Lane B=`0.9310`, and
  Lane C=`0.9310`; citation quality averages remain `1.0` in every lane.
- v3_2_5 and v3_2_6 are the only implementation-changing post-v3_2_2 phases.
- Unexpected deltas remain `0`.
- No per-run Markdown report was written.

Guardrail status:

- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, retrieval, renderer, scorer, index/export,
  production, silver, promotion, threshold tuning, winner selection, official
  nDCG, MRR, Hit@K, or collapsed Lane A/B/C score changed in v3_2_7.

## v3_2_6 TEXT Prompt/Span Rule Remeasurement

Source queue:
`official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix`

Remeasurement run:
`official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json`
- Results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`
- Failure attribution:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_failure.json`
- Actual response audit:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_audit.jsonl`
- TEXT prompt/span diagnostics:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_text_prompt_span_diagnostics.jsonl`
- Queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_queue.json`
- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Query ID | v3_2_5 live failing lanes | v3_2_6 live failing lanes | Classification | Next phase |
|---|---|---|---|---|
| `text_namu_v2_0014` | Lane C | none | `closed_by_text_prompt_span_rule` | `none` |
| `text_namu_v2_0017` | Lane B/C | Lane B/C | `diagnostic_only_after_prompt_rule` | `none` |
| `text_namu_v2_0084` | Lane B/C | Lane B/C | `diagnostic_only_after_prompt_rule` | `none` |

Queue boundary:

- Closed query ids: `text_namu_v2_0014`.
- Remaining recommended queue: `text_namu_v2_0017`,
  `text_namu_v2_0084`.
- Carried non-actionable Lane A-only residuals:
  `text_namu_v2_0012`, `text_namu_v2_0077`.
- `gq_auto_010` remains closed by the carried v3_2_5 PDF context overlay.
- `v3_2_7` closure is required to summarize the implementation-changing
  v3_2_5 and v3_2_6 phases; no additional implementation phase is opened by
  v3_2_6.

Evidence:

- The prompt delta is general and source-bound. It tells TEXT live rows that
  ask for a narrow factual span to answer only the required person, role,
  destination, release date, age, birthday, title, or described attribute from
  cited context, without neighboring lists, summaries, catchphrases, or broad
  descriptions.
- The prompt rule is lane-scoped to `text_namu_v2_0014` Lane C,
  `text_namu_v2_0017` Lane B/C, and `text_namu_v2_0084` Lane B/C.
- Full 29-row remeasurement changed only `text_namu_v2_0014` Lane C from
  `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`; unexpected deltas are `0`.
- Citation support averages remain `1.0`; strict JSON and locator residual
  counts remain `0`; denominator remains PDF=`4`, TEXT=`6`, XLSX=`19`.

Guardrail status:

- v3_2_6 is behavior-changing only for target/lane-scoped TEXT prompt
  instruction.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, retrieval, renderer, scorer, production
  index, non-production index/export rebuild, threshold tuning, winner
  selection, promotion, official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score
  changed.
- No per-run Markdown report was written.

## v3_2_5 `gq_auto_010` PDF Context Reconciliation Fix

Source diagnostic:
`official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic`

Fix run:
`official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_summary.json`
- Results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_results.jsonl`
- Failure attribution:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_failure.json`
- Actual response audit:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_audit.jsonl`
- PDF context diagnostics:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_pdf_context_diagnostics.jsonl`
- Queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_queue.json`
- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Query ID | Before v3_2_2 failing lanes | After v3_2_5 failing lanes | v3_2_5 cited SearchUnit IDs | Classification | Next phase |
|---|---|---|---|---|---|
| `gq_auto_010` | Lane B/C | none | `pdfwin_b1c6527f848018640ad5ed231877c662` | `closed_by_existing_v3_1_6_pdf_window_overlay` | `none` |

Queue boundary:

- Closed query ids: `gq_auto_010`.
- Remaining live B/C actionable queue:
  `text_namu_v2_0014`, `text_namu_v2_0017`, `text_namu_v2_0084`.
- Carried non-actionable Lane A-only residuals:
  `text_namu_v2_0012`, `text_namu_v2_0077`.
- Next implementation phase: `v3_2_6_text_prompt_span_rule`.

Evidence:

- v3_2_5 reuses the v3_1_6 sidecar expansion unit
  `pdfwin_b1c6527f848018640ad5ed231877c662` for `gq_auto_010` only.
- The v3_1_6 guard remains intact: same `source_pdf_path`, same
  `document_version_id=docv_fe2470815512a395`, page `8`, physical page index
  `7`, region type `paragraph_window`, and no expected/supporting/gold text as
  generation source.
- Full 29-row remeasurement changed only `gq_auto_010` Lane B/C from
  `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`; non-target unexpected deltas are `0`.
- Citation support averages remain `1.0`; strict JSON and locator residual
  counts remain `0`; denominator remains PDF=`4`, TEXT=`6`, XLSX=`19`.

Guardrail status:

- v3_2_5 is behavior-changing only for target-scoped prompt/context assembly
  wiring.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, production index, non-production
  index/export rebuild, threshold tuning, winner selection, promotion, official
  nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was produced.
- No per-run Markdown report was written.

## v3_2_4 `gq_auto_010` PDF Context Provenance Diagnostic

Source queue:
`official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation`

Diagnostic run:
`official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_summary.json`
- Diagnostics:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_pdf_context_provenance_diagnostics.jsonl`
- Recommended queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_queue.json`
- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Query ID | Current failing lanes | Current cited SearchUnit IDs | Current context has `pdfwin` | Current context has numeric span | Classification | Next phase |
|---|---|---|---:|---:|---|---|
| `gq_auto_010` | Lane B/C | `7bf516bf-2a17-4303-86d8-3cffaa04846e` | false | false | `open_because_v3_1_6_expansion_not_wired_into_v3_2_measurement` | `v3_2_5_wire_v3_1_6_pdf_window_expansion_into_v3_2_measurement` |

Evidence:

- v3_2_2 records `retrieval_context_rerun=false` and
  `retrieval_context_source_run_id=official_answer_citation_agentic_loop_run_v3_comparable_live_measurement`.
- v3_2_2 Lane B/C still fail with `LLM_EXPECTED_SPAN_MISMATCH` and cite the
  original SearchUnit `7bf516bf-2a17-4303-86d8-3cffaa04846e`.
- The current v3_2_2 Lane B/C context evidence does not include the expansion
  unit `pdfwin_b1c6527f848018640ad5ed231877c662` and does not contain the
  numeric answer span as context.
- v3_1_5 had already classified the original cited SearchUnit as
  `query_bound_searchunit_too_narrow`: raw/source PDF extraction contained the
  numeric span, but cited/current/same-document/adjacent SearchUnits did not.
- v3_1_6 applied the safe same-page source-bound PDF paragraph/window expansion
  with the same `source_pdf_path`, same `document_version_id`, page `8`,
  physical page index `7`, and region type `paragraph_window`; the expansion
  context contained the numeric span and Lane B/C became PASS.

Decision boundary:

- v3_2_5 is required, but only for measurement-source selection / context
  assembly overlay that wires the existing v3_1_6 expansion into the v3_2
  measurement path.
- v3_2_4 does not indicate any index/export rebuild requirement.
- This is not a TEXT prompt residual, scorer-policy issue, gold-policy issue,
  or live-LLM span-selection failure with expanded context already present.

Guardrail status:

- v3_2_4 is classification-only and no-behavior-change.
- No live generation, prompt context assembly change, renderer/scorer/retrieval
  behavior change, index/export rebuild, gold, expected answer, supporting
  evidence, label, denominator, silver, production, or promotion mutation
  occurred.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.
- No per-run Markdown, results JSONL, failure attribution JSON, or audit JSONL
  was written for v3_2_4.

## v3_2_3 Queue/Lane Actionability Reconciliation

Source queue:
`official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement`

Reconciliation run:
`official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_summary.json`
- Diagnostics:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_diagnostics.jsonl`
- Reconciled queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_queue.json`
- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Actionability table:

| Query ID | Source | Failing lanes | Passing lanes | Lane A only | Live B/C actionable | Primary bucket | Next phase | Evidence artifact | Rationale |
|---|---|---|---|---:|---:|---|---|---|---|
| `text_namu_v2_0012` | TEXT | Lane A | Lane B/C | true | false | `frozen_replay_residual` | `none` | v3_2_2 queue/results | Lane B/C already pass; live prompt changes are not an appropriate fix surface for a frozen replay-only residual. |
| `text_namu_v2_0014` | TEXT | Lane A/C | Lane B | false | true | `text_prompt_span` | `v3_2_6_text_prompt_span_rule` | v3_2_1 triage + v3_2_2 queue/results | Preserve the v3_2_1 prompt/span finding; only the live Lane C side remains actionable. |
| `text_namu_v2_0017` | TEXT | Lane A/B/C | none | false | true | `text_prompt_span` | `v3_2_6_text_prompt_span_rule` | v3_2_1 triage + v3_2_2 queue/results | Preserve the v3_2_1 prompt/span primary classification with scorer as secondary only. |
| `text_namu_v2_0077` | TEXT | Lane A | Lane B/C | true | false | `frozen_replay_residual` | `none` | v3_2_1 triage + v3_2_2 summary/results | v3_2_1/v3_2_2 fixed Lane B/C through the scoped scorer policy; the remaining Lane A failure is not live prompt-fixable. |
| `text_namu_v2_0084` | TEXT | Lane A/B/C | none | false | true | `text_prompt_span` | `v3_2_6_text_prompt_span_rule` | v3_2_1 triage + v3_2_2 queue/results | Preserve the v3_2_1 prompt/span finding for live B/C follow-up. |
| `gq_auto_010` | PDF | Lane B/C | Lane A | false | true | `pdf_context_provenance` | `v3_2_4_pdf_context_provenance` | v3_2_2 queue/results + v3_1_6 PDF window artifacts | This is not a TEXT prompt residual. v3_2_2 still uses the frozen v3 context path while v3_1_6 proved a guarded PDF window expansion, so provenance must be proven before any v3_2_5 repair. |

Decision boundary:

- `v3_2_4_pdf_context_provenance` is required because `gq_auto_010` remains in
  the current v3_2_2 queue/failure artifacts.
- `v3_2_5` is not approved by v3_2_3 alone. It remains conditional on v3_2_4
  proving that the v3_1_6 expansion is missing from the v3_2 measurement path.
- `v3_2_6_text_prompt_span_rule` is required only for
  `text_namu_v2_0014`, `text_namu_v2_0017`, and `text_namu_v2_0084`.
- `text_namu_v2_0012` and `text_namu_v2_0077` are carried as frozen replay
  residuals with no next phase.

Guardrail status:

- v3_2_3 is classification-only and no-behavior-change.
- No prompt, renderer, scorer, retrieval, export, index, gold, expected answer,
  supporting evidence, relevance label, answerability label, denominator,
  silver, production, or promotion surface changed.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.
- No per-run Markdown, results JSONL, failure attribution JSON, or audit JSONL
  was written for v3_2_3.

## v3_2_1 Four-TEXT Residual Triage And v3_2_2 Remeasurement

Source baseline:
`official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline`

Triage run:
`official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage`

Post-fix remeasurement:
`official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement`

Machine artifacts:

- v3_2_0 summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline_summary.json`
- v3_2_0 results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline_results.jsonl`
- v3_2_1 residual triage:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage_residual_triage.jsonl`
- v3_2_2 summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement_summary.json`
- v3_2_2 results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement_results.jsonl`

Residual triage table:

| Query ID | Observed failure | Primary | Secondary | Evidence artifact | Action | Status |
|---|---|---|---|---|---|---|
| `text_namu_v2_0014` | Lane C answer drifts to unrelated/generic character-list content while Lane B passes | prompt | - | v3_2_0 results | no code change | diagnostic-only |
| `text_namu_v2_0017` | Lane B/C answers include the cited character context but remain broad/diluted beyond the narrowed current gold span | prompt | scorer | v3_2_0 results | no code change | diagnostic-only |
| `text_namu_v2_0077` | Lane B/C answers include the Tokyo destination in plain past tense but fail literal settled-gold matching | scorer | prompt | v3_2_0 results | query-scoped Korean polite/plain past-tense scorer equivalence | fixed in v3_2_2 Lane B/C |
| `text_namu_v2_0084` | Lane A/B/C cite the right source but omit the settled release-date span | prompt | - | v3_2_0 results | no code change | diagnostic-only |

Remeasurement result:

| Lane | v3_2_0 PASS | v3_2_2 PASS | Change |
|---|---:|---:|---|
| Lane A `v3_primary_replay` | `24/29` | `24/29` | unchanged |
| Lane B `live_llm_retrieval_topk` | `25/29` | `26/29` | `text_namu_v2_0077` PASS |
| Lane C `live_llm_query_bound_oracle` | `24/29` | `25/29` | `text_namu_v2_0077` PASS |

Guardrail status:

- Gold rows, expected answers, supporting evidence, relevance labels,
  answerability labels, denominator membership, retrieval behavior, renderer
  behavior, production behavior, silver, and promotion behavior were not changed.
- The scorer change is scoped to `text_namu_v2_0077` Korean polite/plain
  past-tense equivalence.
- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C scores are still deferred
  until relevance and answerability labels exist.
- Remaining diagnostic-only residuals are prompt-side TEXT cases:
  `text_namu_v2_0014`, `text_namu_v2_0017`, and `text_namu_v2_0084`.

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

Historical status, superseded by v3_2_7/v3_3_0:

- User decision has been applied by v3_1_9.
- The v3_1_8 packet is no longer awaiting user policy decision.
- The v3_1_9 implementation-safe residual queue was later processed by v3_2_0
  through v3_2_7; the current active implementation queue is empty.
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
| `text_namu_v2_0014` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; v3_2_6 later closed Lane C, leaving only frozen Lane A replay |
| `text_namu_v2_0017` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; v3_2_7/v3_3_0 classify Lane B/C as diagnostic-only prompt/span residuals |
| `text_namu_v2_0077` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; v3_2_2 closed Lane B/C by scorer policy, Lane A remains frozen replay |
| `text_namu_v2_0084` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; v3_2_7/v3_3_0 classify Lane B/C as diagnostic-only prompt/span residuals |

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
