# official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement

## Purpose

Freeze a diagnostic-only all-track foundation measurement before silver generation or row-level failure tuning.

## Why this run exists

v3 is an all-track official measurement, but PDF/XLSX primary answers are retained structured-adapter outputs. v3_1 records PDF/TEXT/XLSX LLM shadow/foundation lanes separately so later failure triage starts from fixed evidence.

## Guardrails

- `baseline_mutation`: `false`
- `candidate_artifacts_as_generation_source`: `false`
- `denominator_mutation`: `false`
- `diagnostic_only`: `true`
- `generation_used_expected_answer`: `false`
- `generation_used_gold_fields`: `false`
- `generation_used_supporting_evidence`: `false`
- `gold_mutation`: `false`
- `human_label_mutation`: `false`
- `production_mutation`: `false`
- `promotion_evidence`: `false`
- `promotion_gate_auto_run`: `false`
- `threshold_tuning`: `false`
- `winner_selection`: `false`

## Lane Definitions

- Lane A `v3_primary_replay`: v3 primary policy replay; PDF/XLSX retain structured adapters, TEXT uses LLM synthesis.
- Lane B `live_llm_retrieval_topk`: all 29 rows use live LLM synthesis over source-bound retrieved top-k context.
- Lane C `live_llm_query_bound_oracle`: all 29 rows use live LLM synthesis over query-bound SearchUnit context only.

## Overall Result Table

| Lane | Scored | PASS | LLM invoked | Adapter retained | Failure counts |
|---|---:|---:|---:|---:|---|
| `v3_primary_replay` | 29 | 24 | 6 | 23 | `{"LLM_TRUE_PARTIAL_SYNTHESIS": 5, "PASS": 24}` |
| `live_llm_retrieval_topk` | 29 | 18 | 29 | 0 | `{"LLM_EXPECTED_SPAN_MISMATCH": 6, "LLM_STRICT_JSON_PARSE_FAILURE": 2, "PASS": 18, "PDF_BBOX_LOCATOR_LOSS": 1, "XLSX_CELL_LOCATOR_LOSS": 2}` |
| `live_llm_query_bound_oracle` | 29 | 20 | 29 | 0 | `{"LLM_EXPECTED_SPAN_MISMATCH": 9, "PASS": 20}` |

## Per-Track Result Table

| Family | Lane | PASS | Failure counts |
|---|---|---:|---|
| PDF | `v3_primary_replay` | 4 | `{"PASS": 4}` |
| PDF | `live_llm_retrieval_topk` | 2 | `{"LLM_STRICT_JSON_PARSE_FAILURE": 1, "PASS": 2, "PDF_BBOX_LOCATOR_LOSS": 1}` |
| PDF | `live_llm_query_bound_oracle` | 2 | `{"LLM_EXPECTED_SPAN_MISMATCH": 2, "PASS": 2}` |
| TEXT | `v3_primary_replay` | 1 | `{"LLM_TRUE_PARTIAL_SYNTHESIS": 5, "PASS": 1}` |
| TEXT | `live_llm_retrieval_topk` | 1 | `{"LLM_EXPECTED_SPAN_MISMATCH": 4, "LLM_STRICT_JSON_PARSE_FAILURE": 1, "PASS": 1}` |
| TEXT | `live_llm_query_bound_oracle` | 2 | `{"LLM_EXPECTED_SPAN_MISMATCH": 4, "PASS": 2}` |
| XLSX | `v3_primary_replay` | 19 | `{"PASS": 19}` |
| XLSX | `live_llm_retrieval_topk` | 15 | `{"LLM_EXPECTED_SPAN_MISMATCH": 2, "PASS": 15, "XLSX_CELL_LOCATOR_LOSS": 2}` |
| XLSX | `live_llm_query_bound_oracle` | 16 | `{"LLM_EXPECTED_SPAN_MISMATCH": 3, "PASS": 16}` |

## Lane A/B/C Comparison Table

- Lane names: `v3_primary_replay, live_llm_retrieval_topk, live_llm_query_bound_oracle`
- LLM invoked count by lane: `{"live_llm_query_bound_oracle": 29, "live_llm_retrieval_topk": 29, "v3_primary_replay": 6}`
- Adapter retained count by lane: `{"live_llm_query_bound_oracle": 0, "live_llm_retrieval_topk": 0, "v3_primary_replay": 23}`

## PDF Failure/Weakness Summary

`{"live_llm_query_bound_oracle": {"adapter_retained_count": 0, "answer_partial_unsupported_count": 2, "citation_unsupported_count": 0, "failure_counts": {"LLM_EXPECTED_SPAN_MISMATCH": 2, "PASS": 2}, "llm_generated_locator_failure_count": 0, "llm_invoked_count": 4, "pass_count": 2, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 4}, "live_llm_retrieval_topk": {"adapter_retained_count": 0, "answer_partial_unsupported_count": 0, "citation_unsupported_count": 0, "failure_counts": {"LLM_STRICT_JSON_PARSE_FAILURE": 1, "PASS": 2, "PDF_BBOX_LOCATOR_LOSS": 1}, "llm_generated_locator_failure_count": 2, "llm_invoked_count": 4, "pass_count": 2, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 4}, "v3_primary_replay": {"adapter_retained_count": 4, "answer_partial_unsupported_count": 0, "citation_unsupported_count": 0, "failure_counts": {"PASS": 4}, "llm_generated_locator_failure_count": 0, "llm_invoked_count": 0, "pass_count": 4, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 4}}`

## XLSX Failure/Weakness Summary

`{"live_llm_query_bound_oracle": {"adapter_retained_count": 0, "answer_partial_unsupported_count": 3, "citation_unsupported_count": 0, "failure_counts": {"LLM_EXPECTED_SPAN_MISMATCH": 3, "PASS": 16}, "llm_generated_locator_failure_count": 0, "llm_invoked_count": 19, "pass_count": 16, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 19}, "live_llm_retrieval_topk": {"adapter_retained_count": 0, "answer_partial_unsupported_count": 2, "citation_unsupported_count": 0, "failure_counts": {"LLM_EXPECTED_SPAN_MISMATCH": 2, "PASS": 15, "XLSX_CELL_LOCATOR_LOSS": 2}, "llm_generated_locator_failure_count": 2, "llm_invoked_count": 19, "pass_count": 15, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 19}, "v3_primary_replay": {"adapter_retained_count": 19, "answer_partial_unsupported_count": 0, "citation_unsupported_count": 0, "failure_counts": {"PASS": 19}, "llm_generated_locator_failure_count": 0, "llm_invoked_count": 0, "pass_count": 19, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 19}}`

## TEXT Failure/Weakness Summary

`{"live_llm_query_bound_oracle": {"adapter_retained_count": 0, "answer_partial_unsupported_count": 4, "citation_unsupported_count": 0, "failure_counts": {"LLM_EXPECTED_SPAN_MISMATCH": 4, "PASS": 2}, "llm_generated_locator_failure_count": 0, "llm_invoked_count": 6, "pass_count": 2, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 6}, "live_llm_retrieval_topk": {"adapter_retained_count": 0, "answer_partial_unsupported_count": 4, "citation_unsupported_count": 0, "failure_counts": {"LLM_EXPECTED_SPAN_MISMATCH": 4, "LLM_STRICT_JSON_PARSE_FAILURE": 1, "PASS": 1}, "llm_generated_locator_failure_count": 1, "llm_invoked_count": 6, "pass_count": 1, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 6}, "v3_primary_replay": {"adapter_retained_count": 0, "answer_partial_unsupported_count": 5, "citation_unsupported_count": 0, "failure_counts": {"LLM_TRUE_PARTIAL_SYNTHESIS": 5, "PASS": 1}, "llm_generated_locator_failure_count": 0, "llm_invoked_count": 6, "pass_count": 1, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 6}}`

## Locator Preservation Summary

- Citation payload locator preservation failures: `{"PDF": 1, "TEXT": 1, "XLSX": 0}`
- LLM-generated locator failures by source family: `{"PDF": 2, "TEXT": 1, "XLSX": 2}`
- LLM-generated locator failures by lane: `{"live_llm_query_bound_oracle": 0, "live_llm_retrieval_topk": 5, "v3_primary_replay": 0}`

## Citation Payload Summary

`{"live_llm_query_bound_oracle": {"empty_citation_count": 0, "invalid_count": 0, "ok_count": 29}, "live_llm_retrieval_topk": {"empty_citation_count": 2, "invalid_count": 2, "ok_count": 27}, "v3_primary_replay": {"empty_citation_count": 0, "invalid_count": 0, "ok_count": 29}}`

## Failure Triage Queue

See `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement_triage_queue.md`.

## What Is Not Decided In This Run

- No silver set was created.
- No gold, expected answer, supporting evidence, relevance label, or answerability label was changed.
- No threshold tuning, winner selection, or promotion gate was run.
- No failing row was fixed.

## Next Steps

`row_level_failure_triage_after_all_track_foundation_measurement`
