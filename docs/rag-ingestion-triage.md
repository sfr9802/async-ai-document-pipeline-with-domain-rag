# RAG Ingestion Triage

Last updated: 2026-05-18 KST.

This is the rolling row-level triage ledger. Keep it append-style like
`docs/rag-ingestion-progress.md`: add new triage entries here instead of
creating one Markdown file per run.

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
`row-level failure triage - answer span / renderer diagnostics`

Status:
priority 1~5 plus the remaining `text_namu_v2_0012` TEXT locator residual have
completed diagnostic stabilization. The full 29-row post-triage measurement now
has strict JSON parse failure, LLM-generated locator copy failure, PDF
`source_pdf_path` mismatch, XLSX `row_label` mismatch, and TEXT `text_locator`
missing all at zero. The first answer-span/renderer batch has been recorded as
v3_1_2 diagnostic-only classification over existing post-triage artifacts.

Source foundation run:
`official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement`

Current triage run:
`official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage`

Previous all-track source run:
`official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage`

## Post-Triage Queue

Source run:
`official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage`

Strict JSON / locator residual count: `0`.

Queue source of truth:

- The authoritative queue is the machine artifact
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage_triage_queue.json`.
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
`ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage_remaining_triage_queue.json`

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

Proceed from the v3_1_2 remaining queue. Keep this diagnostic-only: do not
create silver, change gold, tune thresholds, or run a promotion gate.

## Later Triage Queue

After batch 1, use the machine remaining-queue artifact above rather than the
older stale human list. Current later queue:

- `gq_auto_010`
- `gq_auto_024`
- `gq_auto_030`
- `gq_auto_043`
- `gq_pdf_section_question_001`
- `gq_xlsx_date_number_format_001`
- `text_namu_v2_0005`

## User-Decision Boundary

Leave these as user decisions:

- Expected answer changes.
- Supporting evidence changes.
- Relevance label changes.
- Answerability label changes.
- Gold policy changes.
- Silver/gold promotion decisions.
