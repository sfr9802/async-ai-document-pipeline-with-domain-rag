# official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage

- Diagnostic-only 29-row post strict JSON / locator triage measurement.
- Total rows: `29`.
- Rows by source family: `{"PDF": 4, "TEXT": 6, "XLSX": 19}`.
- Lane counts: `{"live_llm_query_bound_oracle": {"adapter_retained_count": 0, "answer_partial_unsupported_count": 12, "citation_unsupported_count": 0, "failure_counts": {"LLM_EXPECTED_SPAN_MISMATCH": 12, "PASS": 17}, "llm_generated_locator_failure_count": 0, "llm_invoked_count": 29, "pass_count": 17, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 29}, "live_llm_retrieval_topk": {"adapter_retained_count": 0, "answer_partial_unsupported_count": 9, "citation_unsupported_count": 0, "failure_counts": {"LLM_EXPECTED_SPAN_MISMATCH": 9, "PASS": 20}, "llm_generated_locator_failure_count": 0, "llm_invoked_count": 29, "pass_count": 20, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 29}, "v3_primary_replay": {"adapter_retained_count": 23, "answer_partial_unsupported_count": 5, "citation_unsupported_count": 0, "failure_counts": {"LLM_TRUE_PARTIAL_SYNTHESIS": 5, "PASS": 24}, "llm_generated_locator_failure_count": 0, "llm_invoked_count": 6, "pass_count": 24, "query_bound_evidence_gap_count": 0, "schema_mismatch_residual_count": 0, "scored_count": 29}}`.
- Strict JSON parse failures by lane: `{"live_llm_query_bound_oracle": 0, "live_llm_retrieval_topk": 0, "v3_primary_replay": 0}`.
- LLM-generated locator copy failures by lane: `{"live_llm_query_bound_oracle": 0, "live_llm_retrieval_topk": 0, "v3_primary_replay": 0}`.
- PDF source_pdf_path mismatches: `0`.
- XLSX row_label mismatches: `0`.
- TEXT text_locator missing: `0`.
- v3_1 PASS regressions: `4`.
- Promotion evidence: `false`.
