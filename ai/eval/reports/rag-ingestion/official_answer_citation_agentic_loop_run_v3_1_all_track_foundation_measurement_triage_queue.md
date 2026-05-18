# official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement Failure Triage Queue

This queue contains only rows with at least one failing diagnostic lane.

| Rank | Query ID | Family | Category | Failing lanes | Fix type | Next step |
|---:|---|---|---|---|---|---|
| 1 | `gq_pdf_section_question_001` | PDF | `LLM_STRICT_JSON_PARSE_FAILURE` | `live_llm_retrieval_topk, live_llm_query_bound_oracle` | `citation_payload` | `inspect_prompt_and_strict_json_response` |
| 2 | `text_namu_v2_0012` | TEXT | `LLM_STRICT_JSON_PARSE_FAILURE` | `v3_primary_replay, live_llm_retrieval_topk, live_llm_query_bound_oracle` | `citation_payload` | `inspect_prompt_and_strict_json_response` |
| 3 | `gq_auto_010` | PDF | `PDF_BBOX_LOCATOR_LOSS` | `live_llm_retrieval_topk, live_llm_query_bound_oracle` | `locator_preservation` | `repair_pdf_locator_preservation` |
| 4 | `gq_auto_023` | XLSX | `XLSX_CELL_LOCATOR_LOSS` | `live_llm_retrieval_topk` | `locator_preservation` | `repair_xlsx_locator_preservation` |
| 5 | `gq_xlsx_lookup_008` | XLSX | `XLSX_CELL_LOCATOR_LOSS` | `live_llm_retrieval_topk` | `locator_preservation` | `repair_xlsx_locator_preservation` |
| 6 | `text_namu_v2_0014` | TEXT | `LLM_TRUE_PARTIAL_SYNTHESIS` | `v3_primary_replay, live_llm_retrieval_topk, live_llm_query_bound_oracle` | `prompt_answer_renderer` | `prompt_answer_renderer_triage` |
| 7 | `text_namu_v2_0017` | TEXT | `LLM_TRUE_PARTIAL_SYNTHESIS` | `v3_primary_replay, live_llm_retrieval_topk, live_llm_query_bound_oracle` | `prompt_answer_renderer` | `prompt_answer_renderer_triage` |
| 8 | `text_namu_v2_0077` | TEXT | `LLM_TRUE_PARTIAL_SYNTHESIS` | `v3_primary_replay, live_llm_retrieval_topk, live_llm_query_bound_oracle` | `prompt_answer_renderer` | `prompt_answer_renderer_triage` |
| 9 | `text_namu_v2_0084` | TEXT | `LLM_TRUE_PARTIAL_SYNTHESIS` | `v3_primary_replay, live_llm_retrieval_topk` | `prompt_answer_renderer` | `prompt_answer_renderer_triage` |
| 10 | `gq_auto_037` | XLSX | `LLM_EXPECTED_SPAN_MISMATCH` | `live_llm_query_bound_oracle` | `prompt_answer_renderer` | `row_level_answer_span_triage` |
| 11 | `gq_auto_043` | XLSX | `LLM_EXPECTED_SPAN_MISMATCH` | `live_llm_retrieval_topk, live_llm_query_bound_oracle` | `prompt_answer_renderer` | `row_level_answer_span_triage` |
| 12 | `gq_xlsx_date_number_format_001` | XLSX | `LLM_EXPECTED_SPAN_MISMATCH` | `live_llm_retrieval_topk, live_llm_query_bound_oracle` | `prompt_answer_renderer` | `row_level_answer_span_triage` |
