# RAG Ingestion Measurements

Last updated: 2026-05-18 KST.

This is the rolling human-readable measurement ledger for RAG ingestion and
official answer/citation diagnostics. Keep this file append-style: add new
measurement sections at the top, keep older sections as compact history, and do
not create per-run Markdown reports for routine diagnostic runs.

Machine-readable JSON/JSONL artifacts can remain under
`ai/eval/reports/rag-ingestion/`, but those files are evidence payloads, not the
primary human report surface.

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

The official first-run baseline is a scored partial baseline and is not a
scorer backend blocker. It remains the immutable reference point; later rows in
this ladder are diagnostic deltas, not promotion evidence.

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
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage_triage_queue.json`.
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

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_actual_response_audit.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_answer_span_diagnostics.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_remaining_triage_queue.json`

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

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_actual_response_audit.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage_triage_delta.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_priority_1_5_triage_strict_json_diagnostics.json`

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

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_results.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_failure_attribution.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_actual_response_audit.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_triage_queue.json`

## Rolling Report Policy

Use these three human-facing files:

- `docs/rag-ingestion-progress.md`: current status, verification, guardrails, next steps.
- `docs/rag-ingestion-measurements.md`: measurement ladder and run-level before/after metrics.
- `docs/rag-ingestion-triage.md`: row-level triage queue, fixes, residuals, and user-decision boundaries.

Do not add new per-run Markdown reports for routine row-level triage. When a
task explicitly asks for diagnostic Markdown artifacts, keep the ongoing
human-readable story in these rolling docs as well.
