<!-- actual_rag_eval_source_native_surface_nonprod:measurements-entry:start -->
### actual_rag_eval_source_native_surface_nonprod

- Scope: source-native actual-RAG retrieval surface wiring and comparison. Retrieval surface is now separate from retrieval backend: `--retrieval-surface auto` prefers SourceAtom/EvidenceBundle-backed source-native units, while SearchUnit/SearchView is retained as a legacy baseline inside the same `report.json`. Expected evidence is used only after retrieval for diagnostics and source-presence probes. No gold/qrels/labels/answerability/expected fields, strict denominator policy, current alias, official metric, product-success, production routing, or live-readiness surface changed.
- Fixture report: `reports/rag_eval/actual_rag_eval_fixture_source_native_surface_final_20260611_v3/report.json`; directory files=`report.json` only; selected_surface=`source_native`; selected_backend=`hybrid`; vector_index_kind=`faiss`; embedding_model=`codex-diagnostic-hashing-vector-v1`; embedding_device=`cpu_existing_nonprod_index`; gpu_used_for_embedding=false; indexed_unit_count=136280; vector_dim=128; fallback_reason=`existing_source_native_index_uses_diagnostic_hash_vectors_not_gpu_bge_m3`. GPU preflight itself found CUDA available on `NVIDIA GeForce RTX 5080`.
- Fixture surface comparison: source_native_expected_evidence_text_presence_rate=0.5, searchunit_expected_evidence_text_presence_rate=0.0, expected_evidence_normalized_present_in_source_native_count=1, source_native_target_span_absent_count=1, searchunit_target_span_absent_count=2, source_native_beats_searchunit_count=1, searchunit_beats_source_native_count=0, both_surfaces_fail_count=1.
- Text-golden report: `reports/rag_eval/actual_rag_eval_text_gold_source_native_surface_final_20260611_v2/report.json`; compared_to=`actual_rag_eval_text_gold_source_native_surface_final_20260611`; directory files=`report.json` only; selected_surface=`source_native`; selected_backend=`hybrid`; vector_index_kind=`faiss`; indexed_unit_count=136280; gpu_used_for_embedding=false with the same explicit diagnostic-hash-index fallback reason.
- Text-golden surface comparison: source_native_expected_evidence_text_presence_rate=1.0, searchunit_expected_evidence_text_presence_rate=0.0, expected_evidence_exact_present_in_source_native_count=1, expected_evidence_normalized_present_in_source_native_count=6, expected_anchor_present_in_source_native_count=6, expected_anchor_present_in_searchunit_count=5, source_native_target_span_present_but_not_retrieved_count=4, source_native_target_span_absent_count=0, searchunit_target_span_absent_count=6, source_native_beats_searchunit_count=2, searchunit_beats_source_native_count=0, both_surfaces_fail_count=4. This demotes SearchUnit/SearchView as the default actual-RAG surface and points the next repair target at source-native retrieval ranking/query formulation rather than corpus coverage.
- Text-golden backend comparison: bm25/vector/hybrid candidate_count_avg=10.0/10.0/10.0, bm25/vector/hybrid retrieval_empty_rate=0.0/0.0/0.0, vector_latency_ms_p50=2.0191, vector_latency_ms_p95=2.3071, bm25_latency_ms_p50=558.00555, bm25_latency_ms_p95=6652.7183, hybrid_latency_ms_p50=560.1265, hybrid_latency_ms_p95=6654.702, vector_index_available=true, gpu_used_for_embedding_count=0.
<!-- actual_rag_eval_source_native_surface_nonprod:measurements-entry:end -->

<!-- actual_rag_eval_evidence_mapping_packet_nonprod:measurements-entry:start -->
### actual_rag_eval_evidence_mapping_packet_nonprod

- Scope: deterministic human-reviewable evidence mapping packet for actual RAG eval expected-evidence candidates. The packet is built from resolver candidates, retrieved contexts, and current source/index metadata for diagnostic review only. It does not mutate gold/qrels/labels, add answerability labels, alter strict denominator policy, change normal RAG retrieval inputs, tune retriever ranking, move `current`, or promote official/product/live-readiness metrics.
- New sidecars: `reports/rag_eval/<run_id>/evidence_mapping_review_packet.csv`, `evidence_mapping_review_packet.jsonl`, `evidence_mapping_review_packet.md`, and `evidence_mapping_packet_summary.json`. Human-owned fields remain blank; machine recommendations are not gold mappings.
- Fixture packet run: `reports/rag_eval/actual_rag_eval_fixture_20260611_034228/rag_eval_summary.json`; packet candidates=2, likely_accept=1, possible_match=1, review_needed=0, likely_reject=0, priorities P0/P1/P2/P3/P4=0/0/0/0/2, source_metadata_resolved_candidate_count=2, source_metadata_unresolved_candidate_count=0, source_metadata_redacted_path_count=1, human_decision_fields_filled_by_codex=false. This is controlled fixture evidence only.
- Text-golden packet run: `reports/rag_eval/actual_rag_eval_text_gold_20260611_034237/rag_eval_summary.json`; compared_to=`actual_rag_eval_text_gold_20260610_152153`; evidence rows=6, expected_evidence_id_missing_count=6, expected_evidence_id_unresolved_count=6, expected_evidence_resolution_candidate_count=14, packet candidates=14, likely_accept=0, possible_match=0, review_needed=9, likely_reject=5, priorities P0/P1/P2/P3/P4=0/11/0/3/0, source_metadata_resolved_candidate_count=14, source_metadata_unresolved_candidate_count=0, source_metadata_redacted_path_count=0, human_decision_fields_filled_by_codex=false.
- Text-golden comparison: expected_evidence_id_missing_count stayed 6->6, expected_evidence_id_unresolved_count stayed 6->6, expected_evidence_id_resolved_candidate_count stayed 0->0, expected_evidence_resolution_candidate_count stayed 14->14, resolved_evidence_available_rate stayed 0/6. Packet metrics are new relative to the previous run, so comparison marks packet candidate/recommendation/source-metadata rows as unavailable/new rather than improvement.
- Review packet examples: likely_reject rows include the `자동판매기 미궁 방랑` evidence where a PDF candidate has source-family mismatch and retrieved TEXT candidates miss required `2026년`/`4월` anchors; review_needed rows include the `유우야키` birthday candidate with `9월` overlap but missing required `16`/`29일`, and `엑스맨 구십칠` rows with weak/rare-entity overlap but no accepted source-owned mapping.
<!-- actual_rag_eval_evidence_mapping_packet_nonprod:measurements-entry:end -->

<!-- actual_rag_eval_expected_evidence_resolution_bridge_nonprod:measurements-entry:start -->
### actual_rag_eval_expected_evidence_resolution_bridge_nonprod

- Scope: deterministic expected-evidence resolution bridge for actual RAG eval reports. It maps expected evidence rows to retrieved-context or current-index candidates for diagnostics only. It does not mutate gold/qrels/labels, alter strict denominator policy, change RAG generation inputs, tune retriever ranking, move `current`, or promote official/product/live-readiness metrics.
- New sidecars: `reports/rag_eval/<run_id>/evidence_resolution_candidates.jsonl` and `reports/rag_eval/<run_id>/evidence_resolution_review.md`. Per-item rows include `expected_evidence_resolution`; summaries include diagnostic counts and provisional resolved-evidence metrics. Registry/latest/status/index surfaces continue under `reports/rag_eval/` plus `ai/eval/reports/rag-ingestion/status.jsonl`.
- Fixture bridge run: `reports/rag_eval/actual_rag_eval_fixture_20260610_152143/rag_eval_summary.json`; evidence rows=1, missing IDs=1, exact resolved=0, candidate resolved=1, unresolved=0, candidates=1, high/medium/low=1/0/0, resolved_evidence_available_rate=1/1, resolved_evidence_recall@3_provisional=1/1, citation_matches_resolved_evidence_precision_provisional=1/1, citation_matches_resolved_evidence_recall_provisional=1/1, e2e_rag_success_resolved_evidence_provisional=1/1. This is controlled fixture evidence only.
- Text-golden bridge run: `reports/rag_eval/actual_rag_eval_text_gold_20260610_152153/rag_eval_summary.json`; compared_to=`actual_rag_eval_text_gold_20260610_142731`; evidence rows=6, missing IDs=6, exact resolved=0, candidate resolved=0, unresolved=6, candidates=14, high/medium/low=0/0/6, review_only=6, resolved_evidence_available_rate=0/6, resolved_evidence_recall@10_provisional=0/0 unavailable, citation_matches_resolved_evidence_precision_provisional=0/0 unavailable, citation_matches_resolved_evidence_recall_provisional=0/0 unavailable, e2e_rag_success_resolved_evidence_provisional=0/0 unavailable.
- Text-golden before/after evidence-resolution comparison: previous run lacked new evidence-resolution candidate/provisional fields; expected_evidence_id_missing_count stayed 6->6, expected_evidence_id_unresolved_count stayed 6->6, expected_evidence_id_resolved_candidate_count is new current 0, expected_evidence_resolution_candidate_count is new current 14, resolved_evidence_available_rate is new current 0/6. No strict metric became available.
- Unresolved reason summary: current-index diagnostic lookup produced only low-confidence review candidates. Examples include missing `2026년` for the `2026년 4월` evidence row, missing `16`/`29일` for the birthday row, and generic `등장인물` overlap for the X-Men row. Low-confidence candidates are review-only and do not count as resolved.
<!-- actual_rag_eval_expected_evidence_resolution_bridge_nonprod:measurements-entry:end -->

<!-- actual_rag_eval_run_accumulation_comparison_nonprod:measurements-entry:start -->
### actual_rag_eval_run_accumulation_comparison_nonprod

- Scope: focused run-accumulation and comparison support for `ai/eval/actual_rag_eval.py`, `ai/scripts/rag_actual_eval.py`, `ai/tests/test_actual_rag_eval_metric_generation.py`, generated `reports/rag_eval/` artifacts, latest pointers, and compact `ai/eval/reports/rag-ingestion/status.jsonl` events. No retriever-ranking improvement, gold/qrels/label mutation, denominator mutation, official metric promotion, current alias movement, production routing, product-success claim, or live-readiness claim was made.
- Registry/latest artifacts: `reports/rag_eval/runs.jsonl`, `reports/rag_eval/latest.json`, `reports/rag_eval/latest_fixture.json`, `reports/rag_eval/latest_text_gold.json`, and generated index `reports/rag_eval/README.md`.
- Fixture baseline: `reports/rag_eval/actual_rag_eval_fixture_20260610_142701/rag_eval_summary.json`; items=2; exact_or_alias_answer_correctness=0/1, evidence_recall@3=0/1, citation_precision=0/1, citation_recall=0/1, judged_answer_correctness_provisional=0/1, weak_evidence_match_recall@3=0/1, e2e_rag_success_provisional=0/1, retrieval_empty_rate=0.5, pipeline_error_count=0.
- Fixture comparison run: `reports/rag_eval/actual_rag_eval_fixture_20260610_142714/rag_eval_summary.json`; compared_to=`actual_rag_eval_fixture_20260610_142701`; exact_or_alias_answer_correctness=1/1 (delta +1.0), evidence_recall@3=1/1 (+1.0), citation_precision=1/1 (+1.0), citation_recall=1/1 (+1.0), judged_answer_correctness_provisional=1/1 (+1.0), weak_evidence_match_recall@3=1/1 (+1.0), e2e_rag_success_provisional=1/1 (+1.0), retrieval_empty_rate=0.5 (unchanged), pipeline_error_count=0 (unchanged). These fixture deltas are controlled-context smoke evidence only.
- Text-golden baseline: `reports/rag_eval/actual_rag_eval_text_gold_20260610_142724/rag_eval_summary.json`; items=6; exact_or_alias_answer_correctness=0/0 unavailable; evidence_recall@10=0/0 unavailable; citation_precision=0/13; citation_recall=0/3; judged_answer_correctness_provisional=0/6; weak_evidence_match_recall@10=0/6; e2e_rag_success_provisional=0/3; retrieval_empty_rate=0.5; pipeline_error_count=0; schema_warning_count=12; gold_missing_count=6; expected_evidence_id_missing_count=6; expected_evidence_id_unresolved_count=6.
- Text-golden comparison run: `reports/rag_eval/actual_rag_eval_text_gold_20260610_142731/rag_eval_summary.json`; compared_to=`actual_rag_eval_text_gold_20260610_142724`; all comparable metrics were unchanged: judged_answer_correctness_provisional=0/6, weak_evidence_match_recall@10=0/6, e2e_rag_success_provisional=0/3, citation_precision=0/13, citation_recall=0/3, retrieval_empty_rate=0.5, pipeline_error_count=0, gold_missing_count=6, expected_evidence_id_unresolved_count=6. Strict exact/evidence/E2E denominators remain unavailable because the text CSV lacks answerability labels.
- Guardrail fields now persist in the new accumulated summaries, registry events, latest pointers, and compact status events: official_metric_input_rows=0, official_metric_input_rows_created=0, official_metric_input_rows_consumed=0, protected_namespaces_touched=[], raw_prompt_payload_written=false, raw_response_payload_written=false, official_metric=false, promotion_evidence=false, product_success_evidence_allowed=false, live_readiness_claim=false.
<!-- actual_rag_eval_run_accumulation_comparison_nonprod:measurements-entry:end -->

<!-- actual_rag_eval_metric_semantics_repair_nonprod:measurements-entry:start -->
### actual_rag_eval_metric_semantics_repair_nonprod

- Scope: focused metric-semantics repair for `ai/eval/actual_rag_eval.py`, `ai/scripts/rag_actual_eval.py`, tests, generated report formatting, and docs/progress. No retriever-ranking improvement, gold/qrels mutation, official metric promotion, current alias movement, production routing, or product-success claim was made.
- Repaired text-golden run: `reports/rag_eval/actual_rag_eval_text_gold_20260610/rag_eval_summary.json`; items=6; answerability_distribution={'answerable': 0, 'unanswerable': 0, 'unknown': 6}; pipeline_error_count=0. Before repair: judged_answer_correctness_provisional=0/6, weak_evidence_match_recall@10=1/6, e2e_rag_success_provisional=1/6, answer_supported_by_retrieved_context_provisional=3/3, citation_overlap_provisional=13/13. After repair: judged_answer_correctness_provisional=0/6, weak_evidence_match_recall@10=0/6, e2e_rag_success_provisional=0/3, answer_extracted_from_retrieved_context_rate=3/3 diagnostic, citation_points_to_retrieved_context_rate=13/13 diagnostic.
- Evidence ID diagnostics for the repaired text-golden run: expected_evidence_id_missing_count=6, expected_evidence_id_unresolved_count=6, expected_evidence_text_match_candidate_count=0. Per-item `evidence_id_diagnostics` are written to `rag_eval_items.jsonl`; unresolved IDs do not block the run and do not mutate qrels/gold.
- Inferred-answerable metrics for the repaired text-golden run are separate from strict metrics because answerability labels are missing: exact_or_alias_answer_correctness_inferred_answerable=0/6, evidence_recall@10_inferred_answerable=0/6, e2e_rag_success_inferred_answerable=0/6. No gold answerability label was mutated.
- Repaired fixture run: `reports/rag_eval/actual_rag_eval_pragmatic_smoke_20260610/rag_eval_summary.json`; judged_answer_correctness_provisional=2/2, weak_evidence_match_recall@3=2/2, e2e_rag_success_provisional=2/2, e2e_rag_success_inferred_answerable=1/1, answer_extracted_from_retrieved_context_rate=2/2 diagnostic, citation_points_to_retrieved_context_rate=2/2 diagnostic.
- False-positive repairs: provisional E2E now fails if the answer judge fails; weak evidence text-only matches require a non-generic anchor and all numeric/date anchors from the expected answer/evidence; the deterministic provisional judge also fails when expected numeric/date answer anchors are missing from the generated answer.
<!-- actual_rag_eval_metric_semantics_repair_nonprod:measurements-entry:end -->

<!-- actual_rag_eval_pragmatic_metric_generation_nonprod:measurements-entry:start -->
### actual_rag_eval_pragmatic_metric_generation_nonprod

- Superseded for current semantics by `actual_rag_eval_metric_semantics_repair_nonprod`; values below are retained as the first-loop baseline.
- Example run: `reports/rag_eval/actual_rag_eval_pragmatic_smoke_20260610/rag_eval_summary.json`; items=3; answerability_distribution={'answerable': 2, 'unanswerable': 1, 'unknown': 0}; pipeline_error_count=0.
- Strict metrics: exact_or_alias_answer_correctness=1/1, evidence_recall@1=2/2, evidence_recall@3=2/2, citation_precision=1/1, citation_recall=1/1, abstention_accuracy=1/1, e2e_rag_success_strict=1/1. These denominators include only rows with the specific required gold signal.
- Provisional metrics: judged_answer_correctness_provisional=2/2, weak_evidence_match_recall@1=2/2, weak_evidence_match_recall@3=2/2, answer_supported_by_retrieved_context_provisional=1/2, citation_overlap_provisional=1/1, e2e_rag_success_provisional=2/2. These are computed with weak assumptions and are not a replacement for strict metrics.
- Diagnostics: retrieval_empty_rate=0.333333, generation_empty_rate=0.0, citation_empty_rate=0.666667, average_context_count=0.666667, average_context_chars=28.5, schema_warning_count=5, gold_missing_count=1, missing_expected_answer_count=2, missing_expected_evidence_count=1, missing_answerability_label_count=0.
- Judge: default `heuristic_overlap_v1` deterministic provisional judge, external_api_calls=false. Optional local LLM judge is configured by `--judge-mode local-llm` and remains report-versioned.
- Existing text golden CSV run: `reports/rag_eval/actual_rag_eval_text_gold_20260610/rag_eval_summary.json`; items=6; answerability_distribution={'answerable': 0, 'unanswerable': 0, 'unknown': 6}; pipeline_error_count=0. Because the CSV lacks answerability labels, strict exact/evidence/E2E denominators are unavailable; strict citation_precision=0/13 and citation_recall=0/3 still run where citations and expected evidence are present. Provisional metrics include judged_answer_correctness_provisional=0/6, weak_evidence_match_recall@10=1/6, answer_supported_by_retrieved_context_provisional=3/3, citation_overlap_provisional=13/13, and e2e_rag_success_provisional=1/6. Diagnostics: retrieval_empty_count=3, generation_empty_count=0, citation_empty_count=3, schema_warning_count=12, gold_missing_count=6, missing_answerability_label_count=6.
<!-- actual_rag_eval_pragmatic_metric_generation_nonprod:measurements-entry:end -->

<!-- v6_9_1_retrieval_smoke_pre_review_packet_nonprod:measurements-entry:start -->
### v6_9_1_retrieval_smoke_pre_review_packet_nonprod

- Review packet: selected_queries=9; selected_queries_by_family={'PDF': 3, 'TEXT': 3, 'XLSX': 3}; candidate_rows_by_backend={'vector': 45, 'bm25': 45, 'hybrid': 45}; candidate_rows_by_family={'PDF': 45, 'TEXT': 45, 'XLSX': 45}.
- Metric gate: retrieval_quality_metric_computed=false; answer_quality_metric_computed=false; computed_only_denominator=0; coverage_adjusted_denominator=300; blocked_reason=pending_user_owned_qrels_denominator_review_for_current_searchunit_searchview_surface; Hit@K/MRR/nDCG remain uncomputed until user-approved current qrels/denominator exists.
- Boundary: SearchView/vector payload is candidate-only; SourceAtom/EvidenceBundle is evidence truth; tool-output rows are excluded from retrieval ranking metrics. human-owned relevance, answerability, qrels, denominator, and expected-evidence fields remain blank.
<!-- v6_9_1_retrieval_smoke_pre_review_packet_nonprod:measurements-entry:end -->

<!-- v6_9_answer_quality_gate_packet_nonprod:measurements-entry:start -->
### v6_9_answer_quality_gate_packet_nonprod

- Answer-quality gate packet: rows=29; rows_by_family={'PDF': 4, 'TEXT': 6, 'XLSX': 19}; human_owned_blank_rows=29; agentic_verification_state_counts={'passed': 10, 'failed': 0, 'skipped_no_answer': 19, 'not_applicable': 0}.
- Metrics policy: answer_quality_metric_computed=false; agentic_answer_metric_computed=false; expected/supporting text is excluded, generated answers are redacted to hashes, and human-owned decisions are blank. No official/product/promotion/live-readiness claim is opened.
<!-- v6_9_answer_quality_gate_packet_nonprod:measurements-entry:end -->

<!-- v6_8_metric_gated_retrieval_quality_engineering_nonprod:measurements-entry:start -->
### v6_8_metric_gated_retrieval_quality_engineering_nonprod

- Retrieval-quality gate: safe_read_only_denominator_available=false; retrieval_quality_metric_computed=false; computed_only_denominator=0; coverage_adjusted_denominator=300; blocked_reason=no_safe_read_only_label_qrels_bridge_available; Hit@k/MRR/nDCG remain uncomputed.
- Denominator separation: v6_4 coverage_adjusted_denominator=300; metric_denominator_separate_from_v6_4_coverage_denominator=true; official_denominator_mutation=false.
- Engineering diagnostics only: backend counters={'vector': {'attempted_rows': 300, 'with_candidates_rows': 299, 'no_candidate_rows': 1, 'hydrated_rows': 299, 'hydration_failed_rows': 0, 'computed_only_denominator': 0, 'retrieval_quality_metric_computed': False, 'backend_latency_ms_available': False, 'backend_latency_ms_p50': None, 'backend_latency_ms_p95': None, 'tool_outputs_counted_as_rag_hit': False}, 'bm25': {'attempted_rows': 300, 'with_candidates_rows': 300, 'no_candidate_rows': 0, 'hydrated_rows': 300, 'hydration_failed_rows': 0, 'computed_only_denominator': 0, 'retrieval_quality_metric_computed': False, 'backend_latency_ms_available': False, 'backend_latency_ms_p50': None, 'backend_latency_ms_p95': None, 'tool_outputs_counted_as_rag_hit': False}, 'hybrid': {'attempted_rows': 300, 'with_candidates_rows': 300, 'no_candidate_rows': 0, 'hydrated_rows': 300, 'hydration_failed_rows': 0, 'computed_only_denominator': 0, 'retrieval_quality_metric_computed': False, 'backend_latency_ms_available': False, 'backend_latency_ms_p50': None, 'backend_latency_ms_p95': None, 'tool_outputs_counted_as_rag_hit': False}}; family counters={'PDF': {'gold29_rows': 4, 'v6_4_coverage_rows': 100, 'tool_operation_rows': 4, 'tool_result_available_rows': 0, 'final_answer_rendered_rows': 4, 'final_citation_verified_rows': 4, 'fail_closed_rows': 0, 'retrieval_quality_metric_computed': False}, 'TEXT': {'gold29_rows': 6, 'v6_4_coverage_rows': 100, 'tool_operation_rows': 6, 'tool_result_available_rows': 0, 'final_answer_rendered_rows': 6, 'final_citation_verified_rows': 6, 'fail_closed_rows': 0, 'retrieval_quality_metric_computed': False}, 'XLSX': {'gold29_rows': 19, 'v6_4_coverage_rows': 100, 'tool_operation_rows': 19, 'tool_result_available_rows': 0, 'final_answer_rendered_rows': 0, 'final_citation_verified_rows': 0, 'fail_closed_rows': 19, 'retrieval_quality_metric_computed': False}}. Availability, latency, and fail-closed counters are not quality metrics. No official/product/promotion/live-readiness claim is opened.
<!-- v6_8_metric_gated_retrieval_quality_engineering_nonprod:measurements-entry:end -->

<!-- v6_7_agentic_retry_fail_closed_policy_nonprod:measurements-entry:start -->
### v6_7_agentic_retry_fail_closed_policy_nonprod

- Agentic loop diagnostics: rows=29; selected_path_counts={'rag_only': 10, 'tool_only': 0, 'rag_then_tool': 0, 'tool_then_rag': 0, 'none_fail_closed': 19}; verification_state_counts={'passed': 10, 'failed': 0, 'skipped_no_answer': 19, 'not_applicable': 0}; retry_attempted_rows=0.
- Metrics policy: agentic_loop_metric_computed=false; answer_quality_metric_computed=false; expected/qrels/supporting evidence are not used for selection or retry. No official/product/promotion/live-readiness claim is opened.
<!-- v6_7_agentic_retry_fail_closed_policy_nonprod:measurements-entry:end -->

<!-- v6_6_structured_tool_operation_taxonomy_nonprod:measurements-entry:start -->
### v6_6_structured_tool_operation_taxonomy_nonprod

- Source check: v6_5_1 attempted_rows=29; rendered=10; citation_verified=10; fail_closed=19.
- Structured tool taxonomy: rows=29; rows_by_family={'PDF': 4, 'TEXT': 6, 'XLSX': 19}; operation_state_counts={'pdf_page_span_extract': 0, 'pdf_locator_lookup': 4, 'text_span_lookup': 6, 'xlsx_table_slice': 0, 'xlsx_cell_lookup': 19, 'xlsx_filter': 0, 'xlsx_aggregate': 0, 'no_tool_required': 0, 'unsupported_tool_request': 0, 'tool_surface_unavailable': 0, 'tool_execution_failed': 0, 'tool_result_empty': 0, 'tool_result_hydration_failed': 0}.
- Metric policy: tool_metric_official=false; retrieval_quality_metric_computed=false; answer_quality_metric_computed=false; tool outputs are excluded from Hit@k/MRR/nDCG. No official/product/promotion/live-readiness claim is opened.
<!-- v6_6_structured_tool_operation_taxonomy_nonprod:measurements-entry:end -->













<!-- v6_5_1_gold29_actual_response_smoke_nonprod:measurements-entry:start -->
### v6_5_1_gold29_actual_response_smoke_nonprod

- v6_5 source check: audited_rows=29; bridgeable_rows=0; bridged retrieval metric computed=false; coverage_adjusted_denominator remains 300 from v6_4.
- v5_5 actual response smoke: attempted=29; rendered=10; citation_verified=10; fail_closed=19; families={'PDF': 4, 'TEXT': 6, 'XLSX': 19}.
- Metrics policy: retrieval_quality_metric_computed=false; answer_quality_metric_computed=false; Hit@k/MRR/nDCG not computed because v6_5 bridgeable_rows=0. No official/product/promotion/live-readiness claim is opened.
<!-- v6_5_1_gold29_actual_response_smoke_nonprod:measurements-entry:end -->

<!-- v6_5_retrieval_metric_unlock_packet_nonprod:measurements-entry:start -->
### v6_5_retrieval_metric_unlock_packet_nonprod

- Source checks: v6_4 attempted_rows=300, family_breakdown={'PDF': 100, 'TEXT': 100, 'XLSX': 100}, computed_only_denominator_before_bridge=0, answer_quality_metric_computed=false.
- v5_5 read-only bridge: approved_items=29; audited_rows=29; bridgeable_rows=0; state_counts={'exact_search_unit_bridge': 0, 'exact_source_atom_bridge': 0, 'locator_precision_bridge': 0, 'duplicate_evidence_ambiguous': 2, 'stale_locator_no_bridge': 10, 'family_mismatch_no_bridge': 0, 'source_identity_mismatch_no_bridge': 0, 'no_current_v6_4_candidate_surface': 17, 'unsupported_tool_only_row': 0}.
- Bridged diagnostic metric: computed=false; bridged_metric_denominator=0; bridgeable_rows_preserved_for_human_review=0; coverage_adjusted_denominator remains 300 from `v6_4_e2e_coverage_and_failure_taxonomy_nonprod` and is not replaced by the bridged read-only metric denominator. Explicit user-owned retrieval qrels/denominator approval is required before Hit@k/MRR/nDCG can be computed. No official/product/promotion/live-readiness claim is opened.
<!-- v6_5_retrieval_metric_unlock_packet_nonprod:measurements-entry:end -->

<!-- v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod:measurements-entry:start -->
### v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod

- v7_0 audit: premature closeout marker; v7_0_preserved=True; completion_claim_allowed=False; missing_predecessors=0.
- v6_4 recovery: run=v6_4_e2e_coverage_and_failure_taxonomy_nonprod; attempted_rows=300; family_breakdown={'PDF': 100, 'TEXT': 100, 'XLSX': 100}; bounded_e2e_rows=30; computed_only_denominator=0; coverage_adjusted_denominator=300.
- Current alias: v7_0_1 does not move current; live current resolves to `v6_9_answer_quality_gate_packet_nonprod`. Historical recovery movement from `v7_0_e2e_eval_architecture_closeout_nonprod` to `v6_4_e2e_coverage_and_failure_taxonomy_nonprod` is audit context only; rollback key is `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`. No official/product/promotion/live-readiness claim is opened.
<!-- v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod:measurements-entry:end -->

<!-- v7_0_e2e_eval_architecture_closeout_nonprod:measurements-entry:start -->
- v7_0 premature closeout marker: source_run=`v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`; source_payload_sha256=e315b2c0fa90e8977b00b3029feab47604d86a52e0ba039c2bedbbc8fbde4054; source_artifact_report_sha256=8b21adb1be596a22b7ba824ef0bd95848c453b4d19547d444b8de893a3f35634.
- Metrics: no new retrieval-quality, answer-quality, official, product, promotion, or live-readiness metric is computed; v6_3 vector/BM25/hybrid/tool/E2E lanes remain diagnostic-only and separated.
- Current alias: current moved from `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report` to `v7_0_e2e_eval_architecture_closeout_nonprod` historically, but `v7_0_e2e_eval_architecture_closeout_nonprod` is preserved as a premature closeout marker and `v6_9_answer_quality_gate_packet_nonprod` supersedes it as current; rollback key is `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`. There is no official/product/promotion/live-readiness claim.
<!-- v7_0_e2e_eval_architecture_closeout_nonprod:measurements-entry:end -->









































<!-- v6_4_e2e_coverage_and_failure_taxonomy_nonprod:measurements-entry:start -->
### v6_4_e2e_coverage_and_failure_taxonomy_nonprod

- Boundary: diagnostic-only, non-production; no official/product/promotion/live-readiness claim is opened.
- 300-row coverage: attempted=300; family_breakdown={'PDF': 100, 'TEXT': 100, 'XLSX': 100}; coverage_adjusted_denominator=300; computed_only_denominator=0; exclusion_reason=no_authorized_after_fact_label_available.
- Candidate availability: vector={'attempted_rows': 300, 'with_candidates_rows': 299, 'no_candidate_rows': 1, 'hydrated_rows': 299, 'hydration_failed_rows': 0, 'coverage_adjusted_denominator': 300, 'computed_only_denominator': 0, 'retrieval_metric_computed_count': 0, 'coverage_limited_reason': 'no_authorized_after_fact_label_available', 'tool_outputs_counted_as_rag_hit': False, 'tool_success_contributed_to_hit_at_k': False, 'tool_success_contributed_to_mrr': False, 'tool_success_contributed_to_ndcg': False}; bm25={'attempted_rows': 300, 'with_candidates_rows': 300, 'no_candidate_rows': 0, 'hydrated_rows': 300, 'hydration_failed_rows': 0, 'coverage_adjusted_denominator': 300, 'computed_only_denominator': 0, 'retrieval_metric_computed_count': 0, 'coverage_limited_reason': 'no_authorized_after_fact_label_available', 'tool_outputs_counted_as_rag_hit': False, 'tool_success_contributed_to_hit_at_k': False, 'tool_success_contributed_to_mrr': False, 'tool_success_contributed_to_ndcg': False}; hybrid={'attempted_rows': 300, 'with_candidates_rows': 300, 'no_candidate_rows': 0, 'hydrated_rows': 300, 'hydration_failed_rows': 0, 'coverage_adjusted_denominator': 300, 'computed_only_denominator': 0, 'retrieval_metric_computed_count': 0, 'coverage_limited_reason': 'no_authorized_after_fact_label_available', 'tool_outputs_counted_as_rag_hit': False, 'tool_success_contributed_to_hit_at_k': False, 'tool_success_contributed_to_mrr': False, 'tool_success_contributed_to_ndcg': False}.
- Bounded E2E expansion: source_rows=3; expanded_rows=30; rows_by_family={'PDF': 10, 'TEXT': 10, 'XLSX': 10}; hydration_source=SourceAtom/EvidenceBundle; answer_quality_metric_computed=false.
- failure taxonomy: {'no_candidate': 1, 'vector_no_candidate': 1, 'bm25_no_candidate': 0, 'hybrid_no_candidate': 0, 'hydration_failed': 0, 'citation_verification_failed': 0, 'tool_required': 100, 'tool_unsupported': 0, 'context_required': 100, 'local_llm_disabled': 30, 'label_unavailable': 300, 'answer_quality_gate_closed': 300, 'protected_surface_blocked': 0}.
- Current alias: current moved from `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report` to `v6_4_e2e_coverage_and_failure_taxonomy_nonprod`; rollback key is `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`.
<!-- v6_4_e2e_coverage_and_failure_taxonomy_nonprod:measurements-entry:end -->



<!-- v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report:measurements-entry:start -->
### v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report

- Boundary: diagnostic-only, non-production; no official/product/promotion/live-readiness claim is opened.
- Materialization: source_derived_search_view_count=300; family_counts={'PDF': 100, 'TEXT': 100, 'XLSX': 100}.
- bge-m3: model_ready=True; embedding_dim=1024; embedding_count=300; device=cpu; gpu_used=False.
- FAISS: index_type=IndexFlatIP; vector_count=300; query_count=300; query_latency_ms={'min': 0.0121, 'p50': 0.0131, 'p95': 0.0144, 'max': 9.7694}.
- E2E smoke: attempted=3; retrieved=3; hydrated=3; answer_rendered=3; citation_verified=3; answer_quality_metric_computed=false.
- Denominator reality: attempted=300; computed-only=0; coverage-adjusted=300; label_limited=True.
- Current alias: current moved from `v6_2_source_derived_materialization_scaleout_and_denominator_reality_check` to `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`; rollback key is `v6_2_source_derived_materialization_scaleout_and_denominator_reality_check`. Report consolidation keeps one primary report.json; deprecated separate JSON/JSONL report files are not emitted.
<!-- v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report:measurements-entry:end -->

<!-- v6_2_source_derived_materialization_scaleout_and_denominator_reality_check:measurements-entry:start -->
### v6_2_source_derived_materialization_scaleout_and_denominator_reality_check

- Boundary: diagnostic-only, non-production; no official/product/promotion/live-readiness claim is opened.
- Materialization: indexed_search_unit_count=300; indexed_search_view_count=300; meaningful_text_count=300; family_counts={'PDF': 100, 'TEXT': 100, 'XLSX': 100}.
- Denominator reality: attempted=300; computed-only and coverage-adjusted rows=0/300; excluded=300; exclusion_breakdown={'no_authorized_after_fact_label_available': 300}.
- true_rag_retrieval_metric: attempted=300; computed=0; coverage_limited=True; coverage_adjusted_denominator=300.
- Backend: namespace `v6_2_true_rag_nonprod_materialization_scaleout_denominator_reality`; backend_kind=repo_local_sqlite_bm25; query_count=300; candidate_distribution={'min': 5, 'p50': 5.0, 'p95': 5, 'max': 5}; query_latency_ms={'min': 0.7151, 'p50': 0.9044, 'p95': 2.0578, 'max': 2.739}; build_latency_ms=632.9212.
- Current alias: current moved from `v6_1_true_rag_corpus_expansion_and_metric_split_hardening` to `v6_2_source_derived_materialization_scaleout_and_denominator_reality_check`; rollback key is `v6_1_true_rag_corpus_expansion_and_metric_split_hardening`. local LLM/GPU usage is optional and env-gated; no raw prompt/response payloads are written.
<!-- v6_2_source_derived_materialization_scaleout_and_denominator_reality_check:measurements-entry:end -->

<!-- v6_1_true_rag_corpus_expansion_and_metric_split_hardening:measurements-entry:start -->
### v6_1_true_rag_corpus_expansion_and_metric_split_hardening

- Boundary: diagnostic-only, non-production; no official/product/promotion/live-readiness claim is opened.
- Backend: namespace `v6_1_true_rag_nonprod_corpus_expansion_metric_split`; indexed_search_unit_count=11; indexed_search_view_count=11; query_count=7; candidate_distribution={'p50': 3.0, 'p95': 4.0, 'max': 4.0}; query_latency_ms={'p50': 0.1268, 'p95': 0.6616, 'max': 0.6616}; build_latency_ms=505.398.
- Metric split: true RAG retrieval, structured tool, and agentic answer metrics are separated; structured tool outputs are excluded from Hit@k/MRR/nDCG.
- true_rag_retrieval_metric={'hit_at_1': 1.0, 'hit_at_3': 1.0, 'hit_at_5': 1.0, 'mrr_at_5': 1.0, 'ndcg_at_5': 1.0}; structured_tool_metric_rows=3; agentic_answer_metric_computed=False.
- Current alias: current moved from `v6_0_agentic_true_rag_and_tool_loop_rewrite` to `v6_1_true_rag_corpus_expansion_and_metric_split_hardening`; rollback key is `v6_0_agentic_true_rag_and_tool_loop_rewrite`.
- local LLM/GPU usage is optional and env-gated; baseline checks pass without requiring local LLM or GPU. No raw prompt/response payloads are written.
<!-- v6_1_true_rag_corpus_expansion_and_metric_split_hardening:measurements-entry:end -->

<!-- v6_0_agentic_true_rag_and_tool_loop_rewrite:measurements-entry:start -->
### v6_0_agentic_true_rag_and_tool_loop_rewrite

- Boundary: legacy non-RAG/tool/extraction path is isolated; true RAG uses pre-materialized SearchUnit/SearchView over the repo-local SQLite/BM25 hybrid backend.
- Backend: repo-local SQLite/BM25 hybrid; namespace `v6_0_true_rag_nonprod_agentic_tool_loop`; indexed_search_unit_count=10; query_count=5; p50_latency_ms=0.1658; p95_latency_ms=0.4867.
- true RAG metrics: gold_29 rows=29; silver_1000 rows=1000; family_breakdown={"PDF": {"hit_at_1": 1.0, "indexed_units": 5, "query_count": 1}, "TEXT": {"hit_at_1": 1.0, "indexed_units": 3, "query_count": 2}, "XLSX": {"hit_at_1": 1.0, "indexed_units": 6, "query_count": 2}}; tool_outputs_excluded=true.
- Tool lane: tool_required_row_ratio=0.4; tool metrics stay separate from true RAG retrieval metrics.
- Current alias: current moved from `v5_6` to `v6_0_agentic_true_rag_and_tool_loop_rewrite`; rollback key is `v5_6`.
- Agentic answer quality: gold_29 answer_quality_metric_computed=true; raw prompt/response storage remains disabled.
<!-- v6_0_agentic_true_rag_and_tool_loop_rewrite:measurements-entry:end -->

<!-- v6_0_true_rag_retrieval_rewrite:measurements-entry:start -->
### v6_0_true_rag_retrieval_rewrite

- Boundary: legacy non-RAG paths remain isolated; current remains `v5_6`; this is diagnostic-only.
- true_rag_retrieval_metric: attempted=3, computed=0, no_candidate_count=3, family_breakdown={"PDF": {"attempted_rows": 1, "computed_rows": 0, "metric_computed": false, "no_candidate_count": 1}, "TEXT": {"attempted_rows": 1, "computed_rows": 0, "metric_computed": false, "no_candidate_count": 1}, "XLSX": {"attempted_rows": 1, "computed_rows": 0, "metric_computed": false, "no_candidate_count": 1}}.
- real nonprod backend invoked: false; real_vectordb_metric=false; latency_unavailable_reason=nonprod_backend_url_missing; cost_unavailable_reason=backend unavailable or did not return cost counters.
- structured tool lane remains separate from the RAG lane; XLSX calculation, aggregation, and filtering questions are classified as `structured_tool_required` and excluded from the true RAG retrieval denominator.
<!-- v6_0_true_rag_retrieval_rewrite:measurements-entry:end -->

<!-- v5_8_retrieval_metric_evaluation_framework_diagnostic_nonprod:measurements-entry:start -->
### v5_8_retrieval_metric_evaluation_framework_diagnostic_nonprod

- valid_live_retrieval_metric: attempted=29, computed=18, coverage_adjusted_denominator=29, coverage_adjusted_metrics={"hit_at_1": 0.172414, "hit_at_3": 0.172414, "hit_at_5": 0.172414, "mrr_at_5": 0.172414, "ndcg_at_5": 0.172414}.
- balanced_diagnostic_retrieval_metric: rows=300, family_split={'PDF': 100, 'TEXT': 100, 'XLSX': 100}, computed_only_metrics={"hit_at_1": 0.233333, "hit_at_3": 0.3, "hit_at_5": 0.303333, "mrr_at_5": 0.264167, "ndcg_at_5": 0.274212}, not_official_qrels=true, promotion_evidence=false, product_success_evidence_allowed=false.
- Backend adapter: run_local_sanitized_projection_adapter; nonprod_vector_backend_available=false; real_vectordb_metric=false; answer-quality metric remains closed; current remains `v5_6`.
<!-- v5_8_retrieval_metric_evaluation_framework_diagnostic_nonprod:measurements-entry:end -->

<!-- v5_7_2_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod:measurements-entry:start -->
- v5_7_2 restatement: `v5_7_prior_baseline_parity_metric` denominator=28 keeps the old 1.0000 replay/parity values; `v5_7_2_valid_live_retrieval_metric` denominator=18 and computed=true with metrics={"hit_at_1": 0.222222, "hit_at_3": 0.222222, "hit_at_5": 0.222222, "mrr_at_5": 0.222222, "ndcg_at_5": 0.222222}. Leakage failures: target/qrels/baseline=0, identity=0, source_shortcut=0. Expanded diagnostic denominator=89 over family_breakdown={'XLSX': 90}; answer-quality deltas remain closed.
<!-- v5_7_2_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod:measurements-entry:end -->

<!-- v5_7_1_retrieval_metric_integrity_audit_diagnostic_nonprod:measurements-entry:start -->
### v5_7_1_retrieval_metric_integrity_audit_diagnostic_nonprod

- Scope: diagnostic-only metric integrity audit over `v5_7_vector_llm_candidate_routing` using the v5_6 full-packet new retrieval metric as prior baseline; no answer-quality metric is computed.
- Restatement: `v5_7_baseline_parity_metric` denominator=28 with the prior 1.0000 values; `v5_7_valid_live_retrieval_metric` denominator=0 and computed=false; `v5_7_oracle_seeded_or_synthetic_candidate_metric` denominator=0.
- Origin/probe counters: candidate_list_identical_to_baseline_topk_new_count=29; top1_equals_target_search_unit_id_count=29; baseline_topk_replay_count=145; synthetic_candidate_count=116; real_non_target_candidate_count=0; leakage_probe_failed_count=29.
<!-- v5_7_1_retrieval_metric_integrity_audit_diagnostic_nonprod:measurements-entry:end -->

<!-- v5_7_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod:measurements-entry:start -->
### v5_7_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod

- Scope: diagnostic-only vector/LLM candidate routing over the v5_6 full-packet baseline; source_official_metric_input_rows=29, route_comparison_rows=29, retrieval_metric_eligible_rows=28, answer_metric_rows=0.
- Retrieval metrics:

| metric | v5_6 full-packet new baseline | v5_7 diagnostic | delta |
| --- | ---: | ---: | ---: |
| hit_at_1 | 1.0000 | 1.0000 | 0.0000 |
| hit_at_3 | 1.0000 | 1.0000 | 0.0000 |
| hit_at_5 | 1.0000 | 1.0000 | 0.0000 |
| mrr_at_5 | 1.0000 | 1.0000 | 0.0000 |
| ndcg_at_5 | 1.0000 | 1.0000 | 0.0000 |

- Latency/cost counters: vector_candidate_adapter_invoked_count=29; vector_search_latency_ms_p50=0.0; vector_search_latency_ms_p95=0.0; llm_adjudication_invoked_count=0; llm_adjudication_latency_ms_p50=0.0; llm_adjudication_latency_ms_p95=0.0; llm_token_estimate_total=0; fail_closed_count=0.
- Regression attribution rows: 0; fine-tuning readiness candidate rows: 0; answer quality metric remains closed.
<!-- v5_7_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod:measurements-entry:end -->

<!-- v5_6_full_packet_route_retrieval_comparison_diagnostic_nonprod:measurements-entry:start -->
### v5_6_full_packet_route_retrieval_comparison_diagnostic_nonprod

- Policy: diagnostic-only route/retrieval delta over read-only v5_5 source rows; answer-quality scored execution remains closed.
- Denominators: route_comparison_rows=29; retrieval_metric_eligible_rows=28; answer_metric_rows=0.
- Old retrieval: Hit@1=0.4643; Hit@3=0.4643; Hit@5=0.4643; MRR@5=0.4643; nDCG@5=0.4643.
- New retrieval: Hit@1=1.0; Hit@3=1.0; Hit@5=1.0; MRR@5=1.0; nDCG@5=1.0.
- Interpretation: diagnostic_retrieval_delta_only=true; quality_delta_claim_supported=false; official_metric_input_rows=0; scored_answer_rows=0.
<!-- v5_6_full_packet_route_retrieval_comparison_diagnostic_nonprod:measurements-entry:end -->

<!-- nec_2026_local_election_xlsx_source_collection_diagnostic_nonprod:measurements-entry:start -->
## NEC 2026 local-election XLSX source collection route

- Run key: `nec_2026_local_election_xlsx`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/nec_2026_local_election_xlsx/report.json`
- Interpretation: direct diagnostic source-collection route only; `current` remains `v5_6`.

| counter | value |
| --- | --- |
| status | NEC_2026_LOCAL_ELECTION_XLSX_SOURCE_COLLECTION_DIAGNOSTIC_NONPROD_READY |
| workbook_count | 8 |
| verified_xlsx_count | 8 |
| visible_sheet_count | 32 |
| native_excel_table_count | 0 |
| source_request_chunk_count | 543 |
| raw_display_request_block_count | 543 |
| parsed_votes_contest_span_count | 2012 |
| search_unit_preview_rows | 3106 |
| source_atom_rows | 13152 |
| search_view_rows | 13152 |
| retrieval_default_included_sheets | ["parsed_votes", "national_summary"] |
| retrieval_default_excluded_sheets | ["source_requests", "raw_display_rows"] |
| code4_provenance_warning_count | 1 |
| official_metric_input_rows | 0 |
| official_metric_input_rows_created | 0 |
| source_registry_mutated | false |
| index_rebuilt | false |
| live_db_index_cache_readiness | false |
<!-- nec_2026_local_election_xlsx_source_collection_diagnostic_nonprod:measurements-entry:end -->

<!-- v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run:measurements-entry:start -->
## v5_5 user-approved official metric dry-run input

- Run key: `v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v5_5/report.json`
- Interpretation: user-approved 29-row v5_4 packet ingestion and official metric input-contract dry-run only. No answer-generation scorer, final official metric, training, fine-tuning, promotion, product-success, or live-readiness evidence.

| Counter | Value |
|---|---:|
| source_v5_4_packet_rows | 29 |
| text_namu_v2_1_rows | 6 |
| xlsx_business_structured_rows | 19 |
| pdf_business_ocr_mm_rows | 4 |
| user_approved_gold_packet_rows | 29 |
| user_approved_denominator_rows | 29 |
| user_approved_qrels_rows | 29 |
| user_approved_expected_answers_rows | 29 |
| official_metric_input_rows | 29 |
| official_metric_input_rows_created | 29 |
| official_metric_dry_run_opened | true |
| official_metric_dry_run_executed | true |
| answer_quality_metric_computed | false |
| duplicate_supporting_evidence_id_count | 1 |
<!-- v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run:measurements-entry:end -->

<!-- v5_4_user_owned_official_eval_approval_packet:measurements-entry:start -->
## v5_4 user-owned official-eval approval packet

- Run key: `v5_4_user_owned_official_eval_approval_packet`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v5_4/report.json`
- Interpretation: packet-only user approval materialization. No official metric dry-run, no official metric rows, and no user-owned final fields filled by Codex.

| counter | value |
| --- | --- |
| status | V5_4_USER_OWNED_OFFICIAL_EVAL_APPROVAL_PACKET_NONPROD_READY |
| source_run_id | v5_3_pdf_text_residual_retrieval_evidence_hardening |
| current_resolves_to | v5_4 |
| review_surface_source | existing_registry_backed_29_official_snapshot |
| user_approval_packet_created | true |
| user_policy_template_created | true |
| user_review_packet_created | true |
| user_review_packet_xlsx_created | true |
| user_review_packet_row_count | 29 |
| user_owned_final_fields_filled_by_codex | false |
| official_metric_input_rows | 0 |
| official_metric_input_rows_created | 0 |
| official_metric_dry_run_opened | false |
| official_eval_user_gate_ready | false |
| training_dataset_created | false |
| fine_tuning_dataset_export_created | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |
| protected_namespaces_touched | [] |
<!-- v5_4_user_owned_official_eval_approval_packet:measurements-entry:end -->

<!-- v5_3_pdf_text_residual_retrieval_evidence_hardening:measurements-entry:start -->
## v5_3 PDF/TEXT residual retrieval/evidence hardening

- Run key: `v5_3_pdf_text_residual_retrieval_evidence_hardening`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v5_3/report.json`
- Interpretation: aggregate PDF/TEXT residual taxonomy plus overlay-90 sample root-cause taxonomy. No row-level residual mask or new repair is created.

| counter | value |
| --- | --- |
| status | V5_3_PDF_TEXT_RESIDUAL_RETRIEVAL_EVIDENCE_HARDENING_DIAGNOSTIC_NONPROD_READY |
| source_run_id | v5_2_xlsx_residual_candidate_only_retrieval_engineering |
| current_resolves_to | v5_3 |
| v4_closeout_basis | v4_7_18 |
| text_v4_7_18_combined_target_hit_count | 232 |
| text_v4_7_18_combined_target_miss_count | 118 |
| pdf_v4_7_18_combined_target_hit_count | 265 |
| pdf_v4_7_18_combined_target_miss_count | 60 |
| pdf_text_residual_aggregate_count | 178 |
| text_candidate_count | 1714 |
| text_zero_candidate_row_count | 2 |
| text_candidate_budget_exhaustion_count | 336 |
| pdf_candidate_overlay_attempted_row_count | 0 |
| overlay_90_text_sample_row_count | 30 |
| overlay_90_pdf_sample_row_count | 30 |
| overlay_90_text_target_not_in_topk_total | 28 |
| overlay_90_pdf_target_not_in_topk_total | 12 |
| overlay_90_sample_scope | overlay_90_sample_not_full_pdf_text_denominator |
| family_target_hit_regression_count | {"PDF": 0, "TEXT": 0, "XLSX": 0} |
| safe_repair_applied | false |
| safe_gain_claimed | false |
| official_metric_input_rows | 0 |
| official_metric_input_rows_created | 0 |
| training_dataset_created | false |
| fine_tuning_dataset_export_created | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |
<!-- v5_3_pdf_text_residual_retrieval_evidence_hardening:measurements-entry:end -->

<!-- v5_2_xlsx_residual_candidate_only_retrieval_engineering:measurements-entry:start -->
## v5_2 XLSX residual candidate-state taxonomy

- Run key: `v5_2_xlsx_residual_candidate_only_retrieval_engineering`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v5_2/report.json`
- Interpretation: candidate-state taxonomy only. Exact row-level residual overlap remains unavailable without a safe non-oracle residual mask.

| counter | value |
| --- | --- |
| status | V5_2_XLSX_RESIDUAL_CANDIDATE_ONLY_RETRIEVAL_ENGINEERING_DIAGNOSTIC_NONPROD_READY |
| source_run_id | v5_1_official_eval_gate_scaffolding |
| current_alias_at_write_time | v5_2 |
| v4_closeout_basis | v4_7_18 |
| xlsx_row_count | 325 |
| xlsx_v4_7_18_combined_target_hit_count | 26 |
| xlsx_v4_7_18_combined_target_miss_count | 299 |
| residual_overlap_counts_available | false |
| candidate_budget_per_query | 5 |
| xlsx_candidate_count | 881 |
| zero_candidate_structural_gap | 78 |
| budget_exhausted_diversity_gap | 109 |
| bounded_candidate_rank_gap_upper_bound | 138 |
| unclassified_residual_overlap_aggregate | 299 |
| candidate_count_distribution | {"0": 78, "1": 58, "2": 31, "3": 14, "4": 1, "5": 143} |
| family_target_hit_regression_count | {"PDF": 0, "TEXT": 0, "XLSX": 0} |
| safe_repair_applied | false |
| safe_gain_claimed | false |
| official_metric_input_rows | 0 |
| official_metric_input_rows_created | 0 |
| training_dataset_created | false |
| training_manifest_jsonl_created | false |
| fine_tuning_dataset_export_created | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |
<!-- v5_2_xlsx_residual_candidate_only_retrieval_engineering:measurements-entry:end -->

<!-- v5_1_official_eval_gate_scaffolding:measurements-entry:start -->
## v5_1 official eval gate scaffolding

- Run key: `v5_1_official_eval_gate_scaffolding`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v5_1/report.json`
- Interpretation: schema and validator scaffold only; no official metric input rows, gold/qrels, denominator rows, training data, or promotion surface.

| counter | value |
| --- | --- |
| status | V5_1_OFFICIAL_EVAL_GATE_SCAFFOLDING_DIAGNOSTIC_NONPROD_READY |
| source_run_id | v5_0_v4_closeout_and_v5_gate_plan |
| current_alias_at_write_time | v5_1 |
| v4_closeout_basis | v4_7_18 |
| official_eval_scaffold_created | true |
| official_eval_user_gate_ready | false |
| official_eval_approval_artifact_found | false |
| official_metric_input_rows | 0 |
| official_metric_input_rows_created | 0 |
| official_metric_input_rows_scope | v5_1_scaffold_created_rows_only |
| existing_registry_backed_official_metric_input_rows_snapshot | 29 |
| blocked_by_user_owned_gold_qrels_or_denominator_gate | true |
| missing_user_owned_approval_artifact_count | 8 |
| gold_mutation | false |
| qrels_mutation | false |
| label_mutation | false |
| expected_answer_mutation | false |
| supporting_evidence_mutation | false |
| denominator_mutation | false |
| training_dataset_created | false |
| training_manifest_jsonl_created | false |
| training_job_created | false |
| fine_tuning_dataset_export_created | false |
| fine_tuning | false |
| fine_tuning_started | false |
| fine_tuning_executed | false |
| ft_a_execution | false |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |
<!-- v5_1_official_eval_gate_scaffolding:measurements-entry:end -->

<!-- v5_0_v4_closeout_and_v5_gate_plan:measurements-entry:start -->
## v5_0 v4 closeout and v5 gate plan

- Run key: `v5_0_v4_closeout_and_v5_gate_plan`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v5_0/report.json`
- Interpretation: diagnostic-only closeout and gate planning; not official scoring, promotion, product-success evidence, or live readiness.

| counter | value |
| --- | --- |
| status | V5_0_V4_CLOSEOUT_AND_V5_GATE_PLAN_DIAGNOSTIC_NONPROD_READY |
| v4_closeout_source_of_truth | v4_7_18 |
| v4_closeout_basis_short_run_id | v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility |
| current_alias_at_write_time | v5_0 |
| source_report_status | V4_7_18_XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_AND_LINEAGE_REPRODUCIBILITY_NONPROD_READY |
| source_report_sha256 | 3a682ff580ebd3e2db78c013e1b9402bd576b43d2f313b414a293118462b8b8e |
| lineage_reproducibility_status | LINEAGE_REPRODUCIBILITY_HARDENED_DIAGNOSTIC_ONLY |
| xlsx_materialization_repair_status | XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_ACCEPTED_DIAGNOSTIC_ONLY |
| xlsx_materialization_repair_decision | accept_materialized_axis_value_overlay_diagnostic_only |
| text_hit_count | 232 |
| text_miss_count | 118 |
| pdf_hit_count | 265 |
| pdf_miss_count | 60 |
| xlsx_hit_count | 26 |
| xlsx_miss_count | 299 |
| xlsx_zero_candidate_row_count | 78 |
| xlsx_candidate_budget_exhaustion_count | 109 |
| family_target_hit_regression_count | {"PDF": 0, "TEXT": 0, "XLSX": 0} |
| official_metric_opening_preconditions_satisfied | false |
| live_readiness_promotion_preconditions_satisfied | false |
| official_metric_input_rows | 0 |
| silver_official_metric_input_rows | 0 |
| silver_promoted_to_gold_count | 0 |
| gold_mutation | false |
| qrels_mutation | false |
| label_mutation | false |
| denominator_mutation | false |
| training_dataset_created | false |
| fine_tuning | false |
| ft_a_execution | false |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |
<!-- v5_0_v4_closeout_and_v5_gate_plan:measurements-entry:end -->

<!-- v4_7_12_layered_retrieval_generalization_and_overfit_audit:measurements-entry:start -->
### v4_7_12 Layered Retrieval Generalization And Overfit Audit

- Run key: `v4_7_12_layered_retrieval_generalization_and_overfit_audit`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_12/report.json`
- Silver retrieval audit: `ai/eval/reports/rag-ingestion/runs/v4_7_12/silver_layered_retrieval_audit.json`
- Interpretation: diagnostic-only architecture/generalization audit. Not official scoring, not promotion evidence, not product-success evidence, and not live-readiness.

| Counter | Value |
|---|---:|
| v4_7_11_canary_row_count | 9 |
| pdf_full_replay_eligible_count | 57 |
| pdf_generated_response_count | 0 |
| silver_manifest_found | True |
| silver_total_row_count | 1000 |
| silver_text_count | 350 |
| silver_pdf_count | 325 |
| silver_xlsx_count | 325 |
| silver_retrieval_audit_row_count | 1000 |
| silver_llm_smoke_sample_count | 90 |
| silver_generated_response_count | 89 |
| canary_to_full_pdf_quality_drop_count | 52 |
| pdf_to_xlsx_retrieval_drop_count | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | False |
<!-- v4_7_12_layered_retrieval_generalization_and_overfit_audit:measurements-entry:end -->
<!-- v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke:measurements-entry:start -->
### v4_7_11 Actual LLM Answer Replay And Silver Diagnostic Smoke

- Run key: `v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_11/report.json`
- Answer review packet: `ai/eval/reports/rag-ingestion/runs/v4_7_11/answer_review_packet_ko.jsonl`
- Source artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_10/report.json`
- Local LLM env gate: `RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY`
- Boundary: diagnostic-only localhost LLM replay over v4_7_10 EvidenceBundle-ready rows. No raw prompt or raw response payload is written to Markdown/status; no official metric, gold/qrels/labels/expected/supporting evidence mutation, denominator mutation, training/fine_tuning/FT-A, promotion, product success, or live-readiness is opened.
- Replay result: candidates 9; skipped weak residual 1; generated 9; parsed answers 9; citations rendered 9; claim-support pass/fail 5/4; unsupported/evidence-underuse 4/4; Korean answers 9; non-Korean flags 0.
- Silver diagnostic smoke: status `SILVER_SOURCE_ARTIFACTS_UNAVAILABLE_FAIL_CLOSED`; sample 0 (TEXT 0, PDF 0, XLSX 0); generated 0; official input rows 0.

| Counter | Value |
|---|---:|
| abstain_count | 0 |
| answer_review_packet_row_count | 9 |
| broad_source_atom_scan_attempt_count | 0 |
| citation_grounded_to_evidence_count | 9 |
| citation_malformed_count | 0 |
| citation_rendered_count | 9 |
| claim_support_verifier_fail_count | 4 |
| claim_support_verifier_pass_count | 5 |
| denominator_mutation | false |
| direct_answer_value_matching_used_count | 0 |
| evidence_truth_violation_count | 0 |
| evidence_underuse_flag_count | 4 |
| expected_answer_mutation | false |
| expected_or_supporting_gold_text_used_count | 0 |
| fine_tuning | false |
| ft_a_execution | false |
| full_page_dump_used_count | 0 |
| generated_response_count | 9 |
| gold_mutation | false |
| hidden_target_locator_used_count | 0 |
| invalid_json_count | 0 |
| korean_final_answer_count | 9 |
| label_mutation | false |
| live_db_index_cache_readiness | false |
| llm_invoked_count | 9 |
| local_llm_available | true |
| local_llm_invocation_failed_fail_closed_count | 0 |
| local_llm_replay_disabled_fail_closed_count | 0 |
| local_llm_replay_env_enabled | true |
| local_llm_unavailable_fail_closed_count | 0 |
| non_korean_answer_flag_count | 0 |
| noop_or_extractive_generator_used | false |
| official_metric | false |
| official_metric_input_rows | 0 |
| parsed_final_answer_present_count | 9 |
| path_leakage_flag_count | 0 |
| pdf_survivor_row_count | 58 |
| product_success_evidence_allowed | false |
| promotion_evidence | false |
| prompt_leakage_flag_count | 0 |
| qrels_mutation | false |
| raw_llm_response_present_count | 0 |
| raw_pdf_query_time_parsing_count | 0 |
| raw_xlsx_query_time_parsing_count | 0 |
| response_leakage_flag_count | 0 |
| silver_abstain_count | 0 |
| silver_candidate_available_count | 0 |
| silver_citation_rendered_count | 0 |
| silver_claim_support_verifier_fail_count | 0 |
| silver_claim_support_verifier_pass_count | 0 |
| silver_fail_closed_count | 0 |
| silver_generated_response_count | 0 |
| silver_llm_invoked_count | 0 |
| silver_official_metric_input_rows | 0 |
| silver_parsed_final_answer_present_count | 0 |
| silver_promoted_to_gold_count | 0 |
| silver_smoke_pdf_count | 0 |
| silver_smoke_sample_count | 0 |
| silver_smoke_text_count | 0 |
| silver_smoke_xlsx_count | 0 |
| source_file_title_shortcut_used_count | 0 |
| supporting_evidence_mutation | false |
| training_dataset_created | false |
| truncated_or_malformed_response_count | 0 |
| unsupported_claim_risk_count | 4 |
| v4_7_10_answer_ready_evidence_bundle_count | 57 |
| v4_7_10_answer_replay_candidate_count | 9 |
| v4_7_10_replayed_candidate_count | 9 |
| v4_7_10_skipped_weak_residual_count | 1 |
| vector_payload_evidence_truth_violation_count | 0 |
<!-- v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke:measurements-entry:end -->
<!-- v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness:measurements-entry:start -->
### v4_7_10 PDF Korean Evidence Normalization And Answer Replay Readiness

- Run key: `v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_10/report.json`
- Source artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_9/report.json`
- Boundary: diagnostic-only spacing-insensitive Korean evidence normalization over existing SourceAtom spans. No raw PDF broad scan, no gold/qrels/labels/expected/supporting evidence mutation, no denominator mutation, no training/fine_tuning/FT-A, no promotion, no live-readiness.
- Before/after: weak evidence/window 3 -> 1; missing neighbor context 3 -> 1.
- Answer-ready evidence bundles: 55 -> 57.
- Local LLM status: `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`; no raw prompt or raw response payload is written.

| Counter | Value |
|---|---:|
| pdf_survivor_row_count | 58 |
| answer_ready_evidence_bundle_count_before | 55 |
| v4_7_9_residual_weak_evidence_window_count_before | 3 |
| residual_weak_evidence_window_count_before | 3 |
| residual_weak_evidence_window_count_after | 1 |
| missing_neighbor_context_count_before | 3 |
| missing_neighbor_context_count_after | 1 |
| v4_7_9_repaired_evidence_bundle_count | 7 |
| newly_repaired_evidence_bundle_count | 2 |
| korean_normalization_repair_count | 2 |
| korean_normalized_evidence_repair_count | 2 |
| total_repaired_evidence_bundle_count_since_v4_7_5 | 9 |
| answer_ready_evidence_bundle_count | 57 |
| new_answer_replay_ready_count | 2 |
| answer_replay_ready_count | 9 |
| answer_replay_candidate_count | 9 |
| llm_invoked_count | 0 |
| local_llm_unavailable_fail_closed_count | 9 |
| generated_response_count | 0 |
| parsed_final_answer_present_count | 0 |
| citation_rendered_count | 0 |
| claim_support_verifier_pass_count | 0 |
| claim_support_verifier_fail_count | 0 |
| unsupported_claim_risk_count | 0 |
| evidence_underuse_flag_count | 0 |
| regression_count_for_v4_7_9_answer_ready_rows | 0 |
| official_metric_input_rows | 0 |
<!-- v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness:measurements-entry:end -->
<!-- v4_7_9_pdf_evidence_residual_answer_quality_replay:measurements-entry:start -->
### v4_7_9 PDF Evidence Residual Answer Quality Replay

- Run key: `v4_7_9_pdf_evidence_residual_answer_quality_replay`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_9/report.json`
- Local LLM status: `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`; no raw prompt or raw response payload is written.

| Counter | Value |
|---|---:|
| answer_replay_candidate_count | 7 |
| citation_rendered_count | 0 |
| claim_support_verifier_fail_count | 0 |
| claim_support_verifier_pass_count | 0 |
| evidence_underuse_flag_count | 0 |
| generated_response_count | 0 |
| llm_invoked_count | 0 |
| local_llm_unavailable_fail_closed_count | 7 |
| missing_neighbor_context_count_after | 3 |
| missing_neighbor_context_count_before | 10 |
| official_metric_input_rows | 0 |
| parsed_final_answer_present_count | 0 |
| pdf_survivor_row_count | 58 |
| prior_answer_ready_evidence_bundle_count | 48 |
| regression_count_for_prior_answer_ready_rows | 0 |
| repaired_evidence_bundle_count | 7 |
| residual_weak_evidence_window_count_after | 3 |
| residual_weak_evidence_window_count_before | 10 |
| unsupported_claim_risk_count | 0 |
<!-- v4_7_9_pdf_evidence_residual_answer_quality_replay:measurements-entry:end -->
<!-- v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion:measurements-entry:start -->
### v4_7_8 Test/Doc Dependency Decoupling And Runner Alias Expansion

- Run key: `v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_8/report.json`
- Interpretation: cleanup/refactor counters only. No retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator, training, FT-A, promotion, product-success, or live-readiness surface is opened.

| Counter | Before | After |
|---|---:|---:|
| hold_current_test_or_doc_contract | 133 | 74 |
| hold_documented_legacy_review_packet | 16 | 16 |
| hold_ambiguous_generated_surface | 32 | 0 |
| review_manual_hold_narrowed | 0 | 12 |
| v3_legacy_manual_hold_count | 181 | 102 |
| safe_runner_check_alias_count | 2 | 12 |
| archived_count | 0 | 79 |
| removed_count | 0 | 79 |
| unclassified_count | 0 | 0 |
| archive_copy_failed_count | 0 | 0 |
| hash_verification_failed_count | 0 | 0 |
<!-- v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion:measurements-entry:end -->
<!-- v4_7_7_v3_legacy_archive_and_runner_consolidation:measurements-entry:start -->
### v4_7_7 V3 Legacy Archive And Runner Consolidation

- Run key: `v4_7_7_v3_legacy_archive_and_runner_consolidation`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_7/report.json`
- Interpretation: archive-aware cleanup/refactor counters only. No retrieval, EvidenceBundle, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator, training, FT-A, promotion, product-success, or live-readiness surface is opened.

| Counter | Value |
|---|---:|
| v3_legacy_artifact_count | 279 |
| v3_legacy_archived_or_removed_count | 98 |
| v3_legacy_deleted_count | 0 |
| v3_legacy_manual_hold_count | 181 |
| v3_legacy_unclassified_count | 0 |
| safe_runner_check_alias_count | 2 |
| hold_current_test_or_doc_contract | 133 |
| hold_documented_legacy_review_packet | 16 |
| hold_ambiguous_generated_surface | 32 |
<!-- v4_7_7_v3_legacy_archive_and_runner_consolidation:measurements-entry:end -->
<!-- v4_7_6_eval_artifact_archive_purge:measurements-entry:start -->
### v4_7_6 Eval Artifact Archive And Purge

- Run key: `v4_7_6_eval_artifact_archive_purge`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_6/report.json`
- Interpretation: cleanup/refactor counters only. No retrieval, EvidenceBundle, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator, training, FT-A, promotion, product-success, or live-readiness surface is opened.

| Counter | Before | After |
|---|---:|---:|
| repo_local_report_file_count | 399 | 293 |
| repo_local_report_bytes | 170924057 | 146192936 |
| long_path_literal_count | 1589 | 1586 |
| direct_report_path_dependency_count | 60 | 57 |
| archived_count | 0 | 108 |
| removed_count | 0 | 108 |
| deleted_count | 0 | 47 |
| manual_hold_count | 0 | 354 |
<!-- v4_7_6_eval_artifact_archive_purge:measurements-entry:end -->
<!-- v4_7_5_pdf_evidence_repair_eval_compaction:measurements-entry:start -->
### v4_7_5 PDF Evidence Repair And Eval Surface Compaction

- Run key: `v4_7_5_pdf_evidence_repair_eval_compaction`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_5/report.json`
- Interpretation: diagnostic proxy before/after over the v4_7_4 PDF survivor 58 rows only. No official metric, gold/qrels, expected answers, supporting evidence approval, labels, training data, promotion evidence, product-success evidence, or live readiness is opened.

| Counter | Before v4_7_4 | After v4_7_5 | Delta |
|---|---:|---:|---:|
| evidence_window_sufficient_proxy_count | 35 | 48 | 13 |
| weak_evidence_window_count | 23 | 10 | -13 |
| missing_neighbor_context_count | 23 | 10 | -13 |
| answer_ready_evidence_bundle_count | 35 | 48 | 13 |
| fail_closed_before_llm_count | 23 | 10 | -13 |
| generated_response_count | 33 | 0 | -33 |
| parsed_final_answer_present_count | 33 | 0 | -33 |
| citation_rendered_count | 33 | 0 | -33 |
| claim_support_verifier_pass_count | 25 | 0 | -25 |
| claim_support_verifier_fail_count | 8 | 0 | -8 |
| unsupported_claim_risk_count | 8 | 0 | -8 |
| evidence_underuse_flag_count | 7 | 0 | -7 |
| non_korean_answer_flag_count | 0 | 0 | 0 |
| table_or_figure_structure_repaired_count | 0 | 2 | 2 |
| regression_count_for_prior_answer_ready_rows | 0 | 0 | 0 |
<!-- v4_7_5_pdf_evidence_repair_eval_compaction:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod:measurements-entry:start -->
### v4_7_4 PDF Survivor Retrieval/Evidence/Answer Quality Replay

- Run: `official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod`
- Resolver key: `v4_7_4`; legacy long-path alias remains supported by `ai/eval/rag_eval_registry.py`. Row-level replay detail is embedded in `report.json` only.
- Interpretation: all metrics are diagnostic proxies over the v4_7_3 PDF survivor candidate set. They are not official metric rows and do not use gold/qrels, expected answers, supporting evidence approvals, hidden target locators, or source-file title shortcuts.

| Counter | Value |
|---|---:|
| pdf_survivor_row_count | 58 |
| xlsx_rows_in_scope | 0 |
| file_identity_hit_proxy_at1 | 58 |
| file_identity_hit_proxy_at3 | 58 |
| page_locator_signal_present_count | 58 |
| block_candidate_available_count | 58 |
| evidence_bundle_created_count | 58 |
| source_atom_hydration_success_count | 58 |
| evidence_window_sufficient_proxy_count | 35 |
| weak_evidence_window_count | 23 |
| citation_support_proxy_count | 30 |
| generated_response_count | 33 |
| unsupported_claim_risk_count | 8 |
| context_understanding_miss_count | 0 |
| official_metric_input_rows | 0 |
| training_dataset_created | false |
<!-- official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod:measurements-entry:start -->
### v4_7_3 Human-Reviewed Korean Query Candidate Pass/Exclusion Application

- Run: `official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod`
- Resolver key: `v4_7_3`; primary report resolves to `ai/eval/reports/rag-ingestion/runs/v4_7_3/report.json`. Legacy long-path alias remains compatibility-only, and sidecar ledgers are embedded in `report.json` instead of written as JSONL.
- Interpretation: `검수상태=미검수` is user-clarified as pass only when `제외사유` is blank. Non-empty `제외사유` means user-excluded. Query candidate pass remains separate from gold/qrels, labels, expected answers/evidence, and official denominator decisions.

| Counter | Value |
|---|---:|
| reviewed_csv_row_count | 204 |
| reviewed_csv_pdf_rows | 100 |
| reviewed_csv_xlsx_rows | 104 |
| user_passed_query_candidate_row_count | 58 |
| user_excluded_row_count | 146 |
| passed_counts_by_family | PDF 58, XLSX 0, TEXT 0 |
| excluded_counts_by_family | PDF 42, XLSX 104, TEXT 0 |
| official_metric_input_rows | 0 |
| gold_jsonl_created | false |
| qrels_jsonl_created | false |
| labels_jsonl_created | false |
| training_dataset_created | false |
| ft_a_execution | false |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |
<!-- official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod:measurements-entry:start -->
### v4_7_2 Source-Grounded Korean Query Review Packet Hydration

- Run: `official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod`
- Primary artifacts: `report.json`, `review_packet_ko_hydrated.xlsx`, `review_packet_ko_hydrated.csv`, `review_packet_ko_hydrated.jsonl`, `review_guidelines_ko.md`, `review_summary_ko.json` under `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod`.
- Interpretation: hydrated Korean query/evidence/locator previews are machine-owned review hints only. They are not gold/qrels, labels, official metric input, training data, FT-A execution, promotion evidence, product-success evidence, or live readiness evidence.

| Counter | Value |
|---|---:|
| prior_packet_row_count | 204 |
| prior_packet_non_empty_query_count | 0 |
| hydrated_packet_row_count | 204 |
| hydrated_packet_non_empty_query_count | 204 |
| hydrated_pdf_row_count | 100 |
| hydrated_xlsx_row_count | 104 |
| extraction_failed_row_count | 0 |
| existing_query_reused_count | 0 |
| deterministic_query_generated_count | 0 |
| local_llm_query_generated_count | 204 |
| official_metric_input_rows | 0 |
| qrels_mutation | false |
| gold_mutation | false |
| label_mutation | false |
| training_dataset_created | false |
<!-- official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod:measurements-entry:start -->
### v4_7_1 Korean Review Packet And README Diagnostic Snapshot

- Run: `official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod`
- Primary artifacts: `report.json`, `review_packet_ko.xlsx`, `review_packet_ko.csv`, `review_packet_ko.jsonl`, `actual_query_llm_response_examples_ko.csv`, `review_guidelines_ko.md`, `review_summary_ko.json` under `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod`.
- Source evidence: v4_7 pre-official registration report plus external manifest SHA-256 `15b2f5f61a03bf588bf49d74a95a11259e2a6a83c0a32a727625344cae7af58c`; source metadata fields are filled from SHA-256 matches against the `source_collection` manifest; actual LLM response examples are from v3_22 answer-allowed rows only.
- Interpretation: Korean packet artifacts are user-owned review surfaces. They are not gold/qrels, expected answer, supporting evidence, official metric input, training data, FT-A execution, promotion evidence, product-success evidence, or live readiness evidence.

| Counter | Value |
|---|---:|
| human_review_only | true |
| review_packet_row_count | 204 |
| review_packet_pdf_rows | 100 |
| review_packet_xlsx_rows | 104 |
| review_packet_text_rows | 0 |
| review_packet_source_rows_have_actual_query_text | false |
| review_packet_source_rows_have_evidence_context | false |
| review_packet_source_rows_have_source_manifest_metadata | true |
| source_manifest_metadata_rows_matched | 204 |
| source_manifest_metadata_rows_missing | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| ft_a_execution | false |
| fine_tuning | false |
| live_db_index_cache_readiness | false |

`preofficial_candidate_thresholds_met=true` in v4_7 means intake thresholds only; `real_holdout_sufficient=false` remains because official denominator, gold/qrels, expected evidence, and promotion gates are still closed and user-owned.
<!-- official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod:measurements-entry:start -->
### v4_7 Preofficial External Holdout Candidate Manifest Registration

- Run: `official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod`
- v4 name: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Resolver key: `v4_7_preofficial`; primary report resolves to `ai/eval/reports/rag-ingestion/runs/v4_7_preofficial/report.json`.
- Source evidence: v4_5_1/v4_5_2/v4_6_10-compatible candidate manifest contract, v4_5_3 prior identity hash baseline, and optional external candidate manifest input. This is pre-official registration evidence only.
- Interpretation: accepted counts here are candidate registration counters, not official metric rows, not promotion evidence, not product success evidence, and not FT-A execution.

| Counter | Value |
|---|---:|
| preofficial_external_holdout_candidate_manifest_registration_only | true |
| registration_gate_passed | true |
| candidate_manifest_available | true |
| candidate_rows_registered | 204 |
| accepted_pdf_holdout_candidates | 20/20 |
| accepted_xlsx_holdout_candidates | 8/8 |
| real_query_fidelity_included_rows_per_family | 100/100 PDF, 104/100 XLSX |
| rejected_candidate_count | 0 |
| source_identity_collision_count | 0 |
| preofficial_candidate_thresholds_met | true |
| real_holdout_sufficient | false |
| official_metric_input_rows | 0 |
| v4_7_official_metric_gate_opened | false |
| product_success_evidence_allowed | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |

Artifact policy: single ignored `report.json`; no candidate manifest sidecar, validation JSONL, source-identity audit JSONL, dry-run input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, official metric results, or per-run Markdown is created. Raw candidate rows, raw source identities, and raw local paths are not embedded.
<!-- official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod:measurements-entry:end -->
<!-- v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout:measurements-entry:start -->
### v4_6 Input-Waiting FT-A Route-Policy And External-Holdout Readiness Closeout

- Marker: `v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout`
- Latest run: `official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod`
- Interpretation: v4_6 completed Codex-owned diagnostic/preflight work and is waiting on external source-disjoint holdout candidate manifest acquisition/registration plus user-owned policy decisions. This is a closeout marker only, not a new parity probe, not v4_7, not official evaluation, and not product/live readiness.

| Counter | Value |
|---|---:|
| v4_6_codex_owned_diagnostic_preflight_work_completed | true |
| v4_6_7_through_v4_6_12_checks_only | route parity, dependency freshness, duplicate hygiene, manifest replay, redaction checks |
| candidate_manifest_present | false |
| real_holdout_sufficient | false |
| accepted_pdf_holdout_candidates | 0/20 |
| accepted_xlsx_holdout_candidates | 0/8 |
| real_query_fidelity_included_rows_per_family | 0/100 PDF, 0/100 XLSX |
| v4_5_readiness_gate | false |
| v4_5_1_intake_gate | false |
| v4_5_2_source_identity_audit_gate | false |
| user_owned_gold_qrels_policy_gate | false |
| official_denominator_gate | false |
| promotion_policy_gate | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |
| product_success_evidence_allowed | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |

No candidate manifest, validation sidecar, dry-run input manifest, prompt payload, dataset, job, checkpoint, official metric row, product-success evidence, promotion evidence, or live-readiness claim is created by this closeout marker.
<!-- v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod:measurements-entry:start -->
### v4_6_12 External Holdout Runtime Replay Route Parity

- Run: `official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod/report.json`
- Source evidence: v4_6_7/v4_6_10/v4_6_11 report hashes, FastAPI holdout-candidate validation route, and transient external-manifest replay against v4_6_10.
- Interpretation: route/replay parity and redaction are deterministic contract checks only. This is not real external holdout registration, not candidate manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| external_holdout_runtime_replay_route_parity_only | true |
| runtime_parity_probe_only | true |
| route_candidate_counts_match_v4_6_10_replay | true |
| route_source_identity_audit_matches_v4_6_10_replay | true |
| enabled_validation_error_raw_input_redacted | true |
| route_response_sanitized | true |
| transient_external_manifest_deleted | true |
| fastapi_readiness_default_report | v4_6_12 |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Artifact policy: single ignored `report.json`; no route-parity sidecar, candidate manifest, validation JSONL, source-identity audit JSONL, dry-run input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, official metric result, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod:measurements-entry:measurements-entry:start -->
### v4_6_11 FT-A Runtime Input Validation Route Parity

- Run: `official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod/report.json`
- Source evidence: v4_6_4/v4_6_5/v4_6_6/v4_6_10 report hashes and the FastAPI diagnostic/internal FT-A dry-run input validation route.
- Interpretation: route parity and redaction are measured as deterministic contract checks only. This is not dry-run input manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, not product-success evidence, and not live readiness.

| Counter | Value |
|---|---:|
| ft_a_runtime_input_validation_route_parity_only | true |
| runtime_parity_probe_only | true |
| disabled_route_status_code | 404 |
| production_disabled_route_status_code | 404 |
| enabled_valid_probe_status_code | 200 |
| enabled_validation_error_status_code | 422 |
| script_runtime_counts_match | true |
| contract_metadata_bridge_present | true |
| runtime_response_sanitized | true |
| runtime_rejects_operational_metric_identity_fields | true |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Artifact policy: single ignored `report.json`; no route-parity sidecar, dry-run input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, official metric result, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod:measurements-entry:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod:measurements-entry:start -->
### v4_6_10 External Holdout Candidate Manifest Gate Replay

- Run: `official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod`
- v4 name: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod/report.json`
- Source evidence: v4_5_1/v4_5_2/v4_5_3/v4_6_6/v4_6_8/v4_6_9 report hashes and the empty external holdout candidate manifest boundary. Optional `--candidate-manifest` replay is input-only and records redacted/hash metadata plus aggregate v4_5_1/v4_5_2 gate outcomes without writing sidecars.
- Interpretation: the default artifact is an input-waiting manifest replay and v4_7-closed preflight only. Optional manifest replay is a no-write gate check, not external holdout acquisition, not candidate manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| external_holdout_candidate_manifest_gate_replay_only | true |
| gate_passed | false |
| candidate_manifest_present | false |
| candidate_manifest_input_provided | false |
| candidate_rows_replayed | 0 |
| fastapi_readiness_default_report_at_v4_6_10 | v4_6_10 |
| fastapi_readiness_projects_manifest_replay | true |
| fastapi_readiness_rejects_inconsistent_replay_counters | true |
| missing_user_owned_input_count | 6 |
| codex_owned_dependency_checks_passed | true |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |

Artifact policy: single ignored `report.json`; no manifest replay sidecar, official metric preflight sidecar, candidate manifest, validation JSONL, source-identity audit JSONL, dry-run plan/input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, official metric results, or per-run Markdown is created. Optional manifest input is not copied into the run directory and raw candidate rows/source identities are not embedded in v4_6_10. This is not a v4_7 opening.
<!-- official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod:measurements-entry:start -->
### v4_6_9 Holdout Candidate Duplicate Hygiene Gate

- Run: `official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod`
- v4 name: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod/report.json`
- Source evidence: sanitized in-memory duplicate probes against the default-disabled FastAPI holdout validator and v4_5_1 intake gate.
- Interpretation: this is a deterministic duplicate-hygiene check only. It is not real external holdout acquisition, not candidate manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| holdout_candidate_duplicate_hygiene_gate_only | true |
| duplicate_hygiene_gate_passed | true |
| runtime_invalid_first_duplicate_rejected | true |
| script_invalid_first_duplicate_rejected | true |
| runtime_script_duplicate_hygiene_consistent | true |
| distinct_query_rows_preserved_without_identity_count_inflation | true |
| accepted_duplicate_row_count | 0 |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |

Artifact policy: single ignored `report.json`; no duplicate-hygiene sidecar, candidate manifest sidecar, validation JSONL, source-identity audit JSONL, dry-run plan/input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod:measurements-entry:start -->
### v4_6_8 Runtime Readiness Dependency Freshness Gate

- Run: `official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod`
- v4 name: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod/report.json`
- Source evidence: current report hashes for v4_5_1, v4_5_2, v4_5_3, v4_6_6, and v4_6_7 plus FastAPI readiness/holdout-candidate validation DTO projections.
- Interpretation: this is a deterministic dependency-freshness and acquisition-requirements packet only. It is not real external holdout acquisition, not candidate manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| runtime_readiness_dependency_freshness_gate_only | true |
| external_holdout_acquisition_requirements_packet_only | true |
| all_source_report_hashes_current | true |
| runtime_readiness_dto_projection_matches_v4_6_6 | true |
| holdout_validation_contract_hash_matches | true |
| forbidden_surface_violation_count | 0 |
| raw_source_identity_or_path_leak_count | 0 |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |

Artifact policy: single ignored `report.json`; no acquisition sidecar, candidate manifest sidecar, validation JSONL, source-identity audit JSONL, dry-run plan/input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod:measurements-entry:start -->
### v4_6_7 Holdout Candidate Runtime Gate Parity Bridge

- Run: `official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod`
- v4 name: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod/report.json`
- Source evidence: in-memory parity probes against FastAPI holdout candidate validation, v4_5_1 intake, v4_5_2 source-identity audit, and v4_5_3-compatible prior hash records.
- Interpretation: this is a deterministic contract-parity check only. It is not real external holdout acquisition, not manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| holdout_candidate_runtime_gate_parity_bridge_only | true |
| runtime_parity_probe_only | true |
| probe_case_count | 2 |
| all_parity_checks_passed | true |
| runtime_candidate_intake_gate_matches_v4_5_1 | true |
| runtime_source_identity_audit_gate_matches_v4_5_2 | true |
| runtime_prior_hash_collision_matches_v4_5_2 | true |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_execution_plan_exported | false |
| dry_run_input_manifest_exported | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |

Artifact policy: single ignored `report.json`; no runtime parity sidecar, candidate manifest sidecar, validation JSONL, source-identity audit JSONL, dry-run plan/input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod:measurements-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod:measurements-entry:start -->
### v4_6_6 Holdout Gap And Dry-Run Blocker Ledger

- Run: `official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod`
- v4 name: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, holdout-gap and dry-run-blocker ledger only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod/report.json`
- Source evidence: v4_4 through v4_6_5 diagnostic reports.

| Field | Value |
| --- | --- |
| holdout_gap_and_dry_run_blocker_ledger_only | true |
| real_holdout_sufficient | false |
| candidate_manifest_present | false |
| candidate_manifest_exported | false |
| accepted_pdf_holdout_candidates | 0 |
| accepted_xlsx_holdout_candidates | 0 |
| pdf_source_document_disjoint_needed | 20 |
| xlsx_workbook_disjoint_needed | 8 |
| all_non_gold_source_gates_passed | false |
| dry_run_blocker_count | 7 |
| dry_run_execution_plan_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| v4_7_official_metric_gate_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds holdout_gap_ledger, dry_run_blocker_ledger, source_report_inputs, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no holdout-gap sidecar, dry-run-blocker sidecar, candidate manifest sidecar, dry-run execution plan sidecar, dry-run input manifest sidecar, prompt manifest, raw LLM response, dataset sidecar, training manifest, training job, checkpoint, review CSV, official metric result, or per-run Markdown.
<!-- official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod:measurements-entry:start -->
### v4_6_5 FT-A Dry-Run Execution Plan Gate

- Run: `official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod`
- v4 name: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, FT-A dry-run execution-plan-gate only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod/report.json`
- Source evidence: v4_6_4 FT-A dry-run input manifest validator report.

| Field | Value |
| --- | --- |
| ft_a_dry_run_execution_plan_gate_only | true |
| dry_run_execution_plan_schema_check_passed | true |
| dry_run_execution_plan_gate_passed | false |
| dry_run_execution_plan_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the dry-run execution plan contract, dry_run_execution_plan_gate, source_report_inputs, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no dry-run execution plan sidecar, dry-run input manifest sidecar, prompt manifest, raw LLM response, dataset sidecar, training manifest, training job, checkpoint, review CSV, official metric result, or per-run Markdown.
<!-- official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod:measurements-entry:end -->

# RAG Ingestion Measurements

<!-- v4_7_18_measurements_start -->
## v4_7_18 XLSX candidate-only materialization repair and lineage reproducibility

- Run key: `v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_18/report.json`

| counter | value |
| --- | --- |
| status | V4_7_18_XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_AND_LINEAGE_REPRODUCIBILITY_NONPROD_READY |
| source_run_id | v4_7_17_candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit |
| lineage_reproducibility_status | LINEAGE_REPRODUCIBILITY_HARDENED_DIAGNOSTIC_ONLY |
| required_runner_module_tracking_status | REQUIRED_RUNNER_MODULES_TRACKED_AND_NOT_IGNORED |
| source_candidate_set_sha256_matches_recomputed | true |
| poisoned_oracle_field_digest_stable | true |
| poisoned_oracle_field_evaluation_changed | true |
| topk_artifact_row_count | 1029 |
| filtered_replay_row_count | 1000 |
| excluded_row_count | 29 |
| xlsx_materialization_repair_status | XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_ACCEPTED_DIAGNOSTIC_ONLY |
| xlsx_materialization_repair_decision | accept_materialized_axis_value_overlay_diagnostic_only |
| xlsx_baseline_target_hit_count | 15 |
| xlsx_v4_7_17_combined_target_hit_count | 17 |
| xlsx_v4_7_18_combined_target_hit_count | 26 |
| xlsx_v4_7_18_gain_over_v4_7_17_count | 9 |
| xlsx_gain_rate_per_v4_7_17_miss | 9/308 |
| xlsx_target_hit_regression_count | 0 |
| xlsx_candidate_count | 881 |
| xlsx_zero_candidate_row_count | 78 |
| xlsx_candidate_budget_exhaustion_count | 109 |
| direct_normalized_answer_value_matching | false |
| raw_xlsx_query_time_parsing | false |
| formula_evaluation | false |
| formula_text_exposure | false |
| source_file_title_shortcut_used | false |
| official_metric_input_rows | 0 |
<!-- v4_7_18_measurements_end -->

<!-- v4_7_17_measurements_start -->
## v4_7_17 candidate-only generalization validation and XLSX table-axis repair audit

- Run key: `v4_7_17_candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_17/report.json`

| counter | value |
| --- | --- |
| status | V4_7_17_CANDIDATE_ONLY_GENERALIZATION_VALIDATION_AND_XLSX_TABLE_AXIS_REPAIR_AUDIT_NONPROD_READY |
| source_run_id | v4_7_16_target_recall_repair_prototype |
| candidate_only_generalization_status | CANDIDATE_ONLY_GENERALIZATION_VALIDATED_DIAGNOSTIC_ONLY |
| source_candidate_set_sha256_matches_recomputed | true |
| poisoned_oracle_field_digest_stable | true |
| poisoned_oracle_field_evaluation_changed | true |
| source_v4_7_16_baseline_target_hit_count | 300 |
| source_v4_7_16_combined_target_hit_count | 514 |
| source_v4_7_16_baseline_miss_to_hit_count | 214 |
| xlsx_table_axis_audit_status | XLSX_TABLE_AXIS_REPAIR_AUDIT_INCONCLUSIVE_DIAGNOSTIC_ONLY |
| xlsx_table_axis_repair_decision | keep_inconclusive_low_gain_candidate_only |
| xlsx_baseline_to_combined | 15 -> 17 |
| xlsx_table_axis_candidate_count | 133 |
| xlsx_table_axis_target_hit_gain_count | 2 |
| xlsx_table_axis_gain_rate_per_baseline_miss | 2/310 |
| xlsx_target_hit_regression_count | 0 |
| xlsx_overlay_target_not_in_topk_total | 28 |
| xlsx_repeated_prefix_cluster_overlap_with_target_miss | 20 |
| source_topk_sha256_verified | true |
| source_topk_resolved_via_archive | true |
| official_metric_input_rows | 0 |
| direct_normalized_answer_value_matching | false |
| raw_xlsx_query_time_parsing | false |
| source_file_title_shortcut_used | false |
<!-- v4_7_17_measurements_end -->

<!-- v4_7_16_measurements_start -->
## v4_7_16 target recall repair prototype

- Run key: `v4_7_16_target_recall_repair_prototype`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_16/report.json`

| counter | value |
| --- | --- |
| status | V4_7_16_TARGET_RECALL_REPAIR_PROTOTYPE_NONPROD_READY |
| source_run_id | v4_7_15_read_only_searchindex_replay_projection |
| candidate_budget_per_query | 5 |
| baseline_target_hit_count | 300 |
| combined_target_hit_count | 514 |
| baseline_miss_to_hit_count | 214 |
| baseline_hit_to_miss_count | 0 |
| TEXT baseline_to_combined | 20 -> 232 |
| TEXT prototype_candidate_count | 1714 |
| TEXT baseline_miss_to_hit_count | 212 |
| XLSX baseline_to_combined | 15 -> 17 |
| XLSX prototype_candidate_count | 133 |
| XLSX baseline_miss_to_hit_count | 2 |
| PDF baseline_to_combined | 265 -> 265 |
| PDF target_hit_regression_count | 0 |
| overlay_90_retrieval_target_not_in_topk | 68 |
| source_topk_sha256_verified | true |
| source_topk_resolved_via_archive | true |
| official_metric_input_rows | 0 |
| direct_normalized_answer_value_matching | false |
| raw_xlsx_query_time_parsing | false |
| source_file_title_shortcut_used | false |
<!-- v4_7_16_measurements_end -->

<!-- v4_7_15_measurements_start -->
## v4_7_15 read-only SearchIndexContract replay projection

- Run key: `v4_7_15_read_only_searchindex_replay_projection`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_15/report.json`

| counter | value |
| --- | --- |
| status | V4_7_15_READ_ONLY_SEARCHINDEX_REPLAY_PROJECTION_NONPROD_READY |
| read_only_searchindexcontract_replay_status | READ_ONLY_SEARCHINDEXCONTRACT_REPLAY_UNBLOCKED_ARCHIVED_TOPK_DIAGNOSTIC_ONLY |
| source_topk_sha256_verified | true |
| source_topk_resolved_via_archive | true |
| v3_7_0_source_registry_manifest_record_count | 5 |
| v3_7_1_index_manifest_record_count | 5 |
| replay_input_row_count | 1000 |
| replay_counts_by_family | {"PDF": 325, "TEXT": 350, "XLSX": 325} |
| topk_envelope_count | 5000 |
| sourceatom_hydration_success_envelope_count | 5000 |
| evidencebundle_renderable_envelope_count | 5000 |
| citation_renderable_envelope_count | 5000 |
| vector_payload_evidence_truth_violation_count | 0 |
| projection_input_row_count | 90 |
| retrieval_target_not_in_topk_projection_count | 68 |
| target_hit_evidence_context_repair_projection_count | 14 |
| query_specificity_fixture_review_projection_count | 3 |
| no_repair_projection_count | 5 |
| overlay_rows_missing_from_audit_count | 0 |
| live_retrieval_quality_failure_count | 0 |
| claim_support_fail_count | 0 |
| parser_failure_count | 0 |
| official_metric_input_rows | 0 |
<!-- v4_7_15_measurements_end -->

<!-- v4_7_14_measurements_start -->
## v4_7_14 diagnostic precondition hardening

- Run key: `v4_7_14_diagnostic_precondition_hardening`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_14/report.json`

| counter | value |
| --- | --- |
| status | V4_7_14_DIAGNOSTIC_PRECONDITION_HARDENING_NONPROD_READY |
| live_retrieval_preflight_status | LIVE_RETRIEVAL_PRECONDITION_UNAVAILABLE_FAIL_CLOSED |
| live_retrieval_precondition_unavailable_count | 1 |
| live_retrieval_quality_failure_count | 0 |
| local_llm_preflight_status | LOCAL_LLM_UNAVAILABLE_GENERATION_NOT_ATTEMPTED_FAIL_CLOSED |
| llm_unavailable_skip_count | 57 |
| generated_response_count | 0 |
| parser_failure_count | 0 |
| claim_support_fail_count | 0 |
| citation_failure_count | 0 |
| unsupported_answer_count | 0 |
| claim_support_not_evaluated_due_to_no_generation_count | 57 |
| silver_answerability_overlay_row_count | 90 |
| official_metric_input_rows | 0 |
<!-- v4_7_14_measurements_end -->

<!-- v4_7_13_measurements_start -->
## v4_7_13 live retrieval answerability and full PDF replay

| counter | value |
| --- | --- |
| status | V4_7_13_LIVE_RETRIEVAL_ANSWERABILITY_AND_FULL_PDF_REPLAY_NONPROD_READY |
| live_silver_retrieval_env_enabled | true |
| live_silver_retrieval_row_count | 0 |
| pdf_full_replay_env_enabled | true |
| pdf_full_replay_eligible_count | 57 |
| pdf_generated_response_count | 0 |
| silver_answerability_overlay_row_count | 90 |
| silver_prior_insufficient_evidence_count | 64 |
| silver_prior_claim_support_pass/fail | 60/30 |
| tooling_counter_scope_mismatch_count | 0 |
| official_metric_input_rows | 0 |
<!-- v4_7_13_measurements_end -->

Last updated: 2026-06-06 KST.

This is the rolling human-readable measurement ledger for RAG ingestion and
official answer/citation diagnostics. Keep this file append-style: add new
measurement sections at the top, keep older sections as compact history, and do
not create per-run Markdown reports for routine diagnostic runs.

Machine-readable JSON/JSONL artifacts are evidence payloads, not the primary
human report surface. As of the 2026-05-21 cleanup, `ai/eval/reports/` keeps
only `rag-ingestion/`, and that directory keeps `status.jsonl` plus compact current v3_6_9 and later diagnostic artifacts required by the current RAG profile. Older measurement payloads, including the official
baseline/scorer/input/smoke files and v3_1-v3_6_8 diagnostics, live in:

the redacted external runtime archive.

Historical `_archive/legacy` artifact paths in older entries are logical
provenance names. Their physical generated payloads may live in the external
runtime archive under redacted external archive paths.

<!-- official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod:measurements-entry:start -->
### v4_6_4 FT-A Dry-Run Input Manifest Validator

- Run: `official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, validator-only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod/report.json`
- Source evidence: v4_6_2 FT-A route-policy fixture contract and v4_6_3 prompt-policy baseline schema reports.

| Diagnostic count | Value |
| --- | ---: |
| ft_a_dry_run_input_manifest_validator_only | true |
| manifest_validator_schema_check_passed | true |
| dry_run_input_manifest_gate_passed | false |
| fixture_contract_gate_ready | true |
| prompt_policy_baseline_gate_ready | true |
| fixture_row_count | 6 |
| accepted_manifest_row_count | 1 |
| excluded_manifest_row_count | 5 |
| gold_or_prompt_or_output_rejection_count | 3 |
| manifest_rows_exported | false |
| raw_prompt_text_embedded | false |
| prompt_payload_created | false |
| prompt_manifest_created | false |
| raw_llm_response_payload_created | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| v4_7_official_metric_gate_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the dry-run input manifest contract, validation probes, dry_run_input_manifest_gate, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no dry-run input manifest sidecar, prompt manifest, raw LLM response, dataset sidecar, training manifest, training job, checkpoint, review CSV, or per-run Markdown.
<!-- official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod:measurements-entry:start -->
### v4_6_3 FT-A Prompt-Policy Baseline Schema

- Run: `official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, schema-only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod/report.json`
- Source evidence: v4_6_2 FT-A route-policy fixture contract report.

| Diagnostic count | Value |
| --- | ---: |
| ft_a_prompt_policy_baseline_schema_only | true |
| prompt_policy_baseline_schema_check_passed | true |
| dry_run_prompt_baseline_gate_passed | false |
| fixture_contract_gate_ready | true |
| future_dry_run_required_output_count | 4 |
| stop_condition_audit_bucket_count | 5 |
| raw_prompt_text_embedded | false |
| prompt_payload_created | false |
| raw_llm_response_payload_created | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| v4_7_official_metric_gate_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the prompt-policy baseline schema, prompt_policy_baseline_gate, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no raw prompt text, prompt payload, raw LLM response, dataset sidecar, training manifest, training job, checkpoint, review CSV, or per-run Markdown.
<!-- official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod:measurements-entry:start -->
### v4_6_2 FT-A Route-Policy Fixture Contract

- Run: `official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, fixture-contract-only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod/report.json`
- Source evidence: v4_6 preflight report and v4_6_1 holdout manifest identity contract bridge report.

| Diagnostic count | Value |
| --- | ---: |
| ft_route_policy_fixture_contract_only | true |
| fixture_contract_schema_ready | true |
| fixture_contract_schema_check_passed | true |
| dry_run_dataset_gate_passed | false |
| fixture_validation_probe_count | 5 |
| accepted_fixture_probe_count | 1 |
| rejected_fixture_probe_count | 4 |
| gold_oracle_field_rejection_count | 3 |
| dataset_export_gate_opened | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| v4_7_official_metric_gate_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the FT-A fixture contract, validation probes, fixture_contract_gate, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no prompt payload, raw LLM response, dataset sidecar, training manifest, training job, checkpoint, review CSV, or per-run Markdown.
<!-- official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod:measurements-entry:start -->
### v4_6_1 Holdout Candidate Manifest Identity Contract Bridge

- Run: `official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, identity-contract bridge only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod/report.json`
- Source evidence: v4_5_1/v4_5_2/v4_5_3 reports expose the shared holdout manifest contract hash, and v4_6 source report inputs re-lock those same hashes.

| Diagnostic count | Value |
| --- | ---: |
| holdout_candidate_manifest_identity_contract_bridge_only | true |
| contract_bridge_gate_passed | true |
| contract_hashes_match | true |
| identity_probe_passed | true |
| v4_6_hash_mismatch_rejection_passed | true |
| identity_contract_probe_count | 5 |
| identity_contract_probe_passed_count | 5 |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| v4_7_official_metric_gate_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the shared contract hash, source report input hashes, identity probe results, contract_bridge_gate, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no candidate manifest, validation sidecar, source-identity audit sidecar, prompt payload, raw LLM response, dataset sidecar, training job, checkpoint, review CSV, or per-run Markdown.
<!-- official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod:measurements-entry:start -->
### v4_6 FT Route Policy Dry-Run Preflight

- Run: `official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, preflight-only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod/report.json`
- Source evidence: v4_5/v4_5_1/v4_5_2/v4_5_3 report inputs are hash-locked in `source_report_inputs`; v4_5_3 supplies the hash-only prior identity baseline.

| Diagnostic count | Value |
| --- | ---: |
| ft_route_policy_dry_run_preflight_only | true |
| all_preflight_gates_passed | false |
| v4_5_readiness_gate_passed | false |
| v4_5_1_candidate_intake_gate_passed | false |
| v4_5_2_source_identity_audit_gate_passed | false |
| v4_5_3_prior_identity_baseline_gate_passed | true |
| user_owned_gold_policy_gate_passed | false |
| official_denominator_gate_passed | false |
| promotion_policy_gate_passed | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the preflight gates, source report input hashes, v4_5_3 prior identity hash-set provenance, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no prompt payload, raw LLM response, dataset sidecar, training job, checkpoint, review CSV, or per-run Markdown.
<!-- official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod:measurements-entry:start -->
### v4_5_3 External Holdout Prior Source Identity Ledger Summary

- Run: `official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, hash-only prior source-identity ledger summary only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod/report.json`
- Source evidence: `ai/eval/source_registry/source_atom_registry_v1.jsonl` PDF/XLSX SourceAtom rows.

| Diagnostic count | Value |
| --- | ---: |
| prior_source_identity_ledger_summary_only | true |
| prior_identity_collision_baseline_available | true |
| prior_identity_hash_record_count | 102 |
| prior_pdf_identity_count | 98 |
| prior_xlsx_identity_count | 4 |
| prior_pdf_source_atom_count | 329 |
| prior_xlsx_source_atom_count | 343 |
| path_like_source_identity_count | 0 |
| path_like_identity_key_candidate_count | 0 |
| path_like_raw_locator_row_count | 669 |
| candidate_manifest_present | false |
| candidate_manifest_rows | 0 |
| real_holdout_available | false |
| real_holdout_sufficient | false |
| v4_6_ft_dry_run_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the hash-only `prior_identity_ledger_summary`, metrics, guardrails, source registry input hashes, verification, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no raw prior identity values, prior identity ledger sidecar, candidate manifest sidecar, validation JSONL, review CSV, training manifest, dataset sidecar, checkpoint, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod:measurements-entry:start -->
### v4_5_2 External Holdout Candidate Source Identity Audit

- Run: `official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, external holdout candidate source-identity audit only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod/report.json`
- Source evidence: v4_5_1 candidate intake gate plus optional external candidate manifest, optional raw prior identity ledger input, and the v4_5_3 hash-only prior summary report when available.

| Diagnostic count | Value |
| --- | ---: |
| source_identity_audit_ready | true |
| candidate_manifest_input_provided | false |
| candidate_manifest_input_path_kind | not_provided |
| prior_identity_ledger_input_provided | false |
| prior_identity_ledger_input_path_kind | not_provided |
| prior_identity_summary_report_defaulted_from_v4_5_3 | true |
| prior_identity_summary_report_path_kind | repo_relative |
| candidate_manifest_present | false |
| candidate_manifest_rows | 0 |
| prior_identity_ledger_present | false |
| prior_identity_rows | 0 |
| prior_identity_summary_report_present | true |
| prior_identity_summary_hash_records | 102 |
| prior_identity_baseline_present | true |
| source_identity_audit_gate_passed | false |
| source_identity_collision_count | 0 |
| accepted_pdf_holdout_candidates | 0/20 |
| accepted_xlsx_holdout_candidates | 0/8 |
| real_query_fidelity_included_rows_per_family | 0/100 PDF, 0/100 XLSX |
| real_holdout_available | false |
| real_holdout_sufficient | false |
| v4_6_ft_dry_run_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds candidate_manifest_input, prior_identity_ledger_input, prior_identity_summary_report_input, the compact hash-only prior summary bridge, source_identity_audit_gate, accepted/excluded sanitized candidate rows, metrics, guardrails, source lineage, verification, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no candidate manifest sidecar, prior identity ledger sidecar, validation JSONL, review CSV, training manifest, dataset sidecar, checkpoint, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod:measurements-entry:start -->
### v4_5_1 Holdout Candidate Intake Gate

- Run: `official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, holdout-candidate-intake only, single `report.json`.
- Candidate manifest input: optional external manifest path is input-only; raw external paths are redacted in reports/status.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod/report.json`
- Source evidence: v4_5 fine-tuning-readiness packet plus v4_4 holdout/leakage gates.

| Diagnostic count | Value |
| --- | ---: |
| candidate_intake_schema_ready | true |
| candidate_manifest_input_provided | false |
| candidate_manifest_input_path_kind | not_provided |
| candidate_manifest_present | false |
| candidate_manifest_rows | 0 |
| candidate_intake_gate_passed | false |
| accepted_pdf_holdout_candidates | 0/20 |
| accepted_xlsx_holdout_candidates | 0/8 |
| real_query_fidelity_included_rows_per_family | 0/100 PDF, 0/100 XLSX |
| excluded_holdout_candidate_count | 0 |
| v4_6_ft_dry_run_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds candidate_manifest_input, candidate_intake_gate, accepted/excluded sanitized candidate rows, metrics, guardrails, source lineage, verification, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no candidate manifest sidecar, validation JSONL, review CSV, training manifest, dataset sidecar, checkpoint, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod:measurements-entry:start -->
### v4_5 Fine-Tuning Readiness Packet

- Run: `official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, fine-tuning-readiness only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod/report.json`
- Source evidence: v4_4 real blind/OOD holdout and leakage-audit report.

| Diagnostic count | Value |
| --- | ---: |
| readiness_gate_passed | false |
| evidence_path_quality_gate_passed | true |
| split_quality_gate_passed | false |
| leakage_audit_gate_passed | true |
| PDF_source_document_disjoint | 0/20 |
| XLSX_workbook_disjoint | 0/8 |
| real_query_fidelity_included_rows_per_family | 0/100 PDF, 0/100 XLSX |
| leakage_bucket_count | 9 |
| leakage_excluded_count | 9 |
| fine_tuning_dataset_exports_created | 0 |
| sft_ready | false |
| dpo_ready | false |
| reward_model_ready | false |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| fine_tuning_started | false |
| fine_tuning_executed | false |
| ft_route_policy_dry_run_executed | false |
| route_policy_projection_recorded | true |
| gpu_required_for_this_slice | false |
| gpu_required_for_future_training_when_opened | true |

Counter source-of-truth: `report.json` embeds readiness_gates, fine_tuning_lanes, ft_route_policy_dry_run, metrics, family_separated_readiness, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV, training manifest, dataset sidecar, checkpoint, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod:measurements-entry:end -->

<!-- phase1_diagnostic_contract_closure_fastapi_diagnostic_integration:measurements-entry:start -->
### Phase 1 Closeout FastAPI Diagnostic Integration

- Marker: `phase1_diagnostic_contract_closure_fastapi_diagnostic_integration`
- Routes: `POST /internal/rag/diagnostic/query`, `GET /internal/rag/diagnostic/readiness`, `POST /internal/rag/diagnostic/holdout-candidates/validate`, `POST /internal/rag/diagnostic/ft-a/dry-run-input/validate`
- Feature flag: `AIPIPELINE_WORKER_RAG_FASTAPI_DIAGNOSTIC_ROUTE_ENABLED` / `rag_fastapi_diagnostic_route_enabled`
- Primary app: `ai/app/main.py` exposes `app = create_app()`; `ai/app/api.py` owns the only discovered `FastAPI(...)` factory.
- Counter source-of-truth: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod/report.json`
- Script inventory: `ai/scripts/README.md`; no required v3 artifact/script was deleted.

| Integration check | Value |
| --- | --- |
| diagnostic route default-enabled | false |
| disabled in production orchestrator mode | true |
| diagnostic route tests | 35 passed |
| readiness route holdout candidate manifest contract | exposed, input-only, hash-locked, no writes |
| FT-A dry-run input validation route | exposed, input-only, sanitized/hash-only, no writes |
| v3_22 script entrypoint | retained and imports `phase1_diagnostic_runtime` helpers |
| SourceAtom/EvidenceBundle display metadata bridge | present for XLSX bundles |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

This section records integration and cleanup checks only. It does not add a new performance, quality, promotion, official metric, or product-success measurement. `report.json` and `status.jsonl` remain ignored artifacts; no review packet was created by this closeout.
<!-- phase1_diagnostic_contract_closure_fastapi_diagnostic_integration:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod:measurements-entry:start -->
### v4_4 Real Blind/OOD Holdout And Leakage Audit

- Run: `official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, family-separated PDF/XLSX holdout infrastructure, TEXT comparison/control only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod/report.json`
- Source evidence: v3_10 holdout manifest, v3_10 query-fidelity audit, v3_10 leakage audit, v4_2 XLSX locator report, and v4_3 PDF file-identity split report.

| Diagnostic count | Value |
| --- | ---: |
| real_holdout_available | false |
| PDF_source_document_disjoint | 0/20 |
| XLSX_workbook_disjoint | 0/8 |
| query_fidelity_included_rows_per_family | 0/100 |
| query_fidelity_audit_rows | 200 |
| leakage_bucket_count | 9 |
| leakage_excluded_count | 9 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| fine_tuning_executed | false |
| gpu_required_for_this_slice | false |

Counter source-of-truth: `report.json` embeds summary, metrics, holdout_manifest, split_manifest, query_fidelity_audit, leakage_audit, excluded_row_ledger, family_separated_metrics, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV, sidecar manifest, metrics sidecar, audit sidecar, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod:measurements-entry:start -->
### v4_3 PDF File Identity Confidence And Evidence-Window Split

- Run: `official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, family-separated PDF-only, single `report.json`, `official_metric=false`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod/report.json`
- Metric provenance: PDF file-identity and evidence-window counts are v3_13 reference-only seen diagnostics with `computed_by_v4_3=false`.

| Diagnostic count | Value |
| --- | ---: |
| pdf_file_identity_rows | 329 |
| pdf_candidate_component_rows | 942 |
| file_resolve_at1 | 66/329 |
| file_resolve_at3 | 129/329 |
| abstain_or_disambiguation_count | 182 |
| accepted_wrong_rank1_with_target_in_top3_count | 63 |
| wrong_file_forcing_accepted_count | 81 |
| same_page_bounded_evidence_window_candidate_at3 | 341/942 |
| answer_ready_window_sufficient_at_query | 251/329 |
| bbox_correctness_metric_computed | false |
| source_document_disjoint_validation_rows | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| fine_tuning_executed | false |
| gpu_required_for_this_slice | false |

Counter source-of-truth: `report.json` embeds summary, metrics, per-query PDF file-identity split manifest, failure taxonomy, source run references, holdout policy, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV, sidecar manifest, metrics sidecar, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod:measurements-entry:start -->
### v4_2 XLSX Locator v2 Table/Range/Cell Structural Materialization

- Run: `official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, family-separated XLSX-only, single `report.json`.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod/report.json`
- Metric provenance: table/range and cell/value counts are v3_12/v3_15 reference-only seen diagnostics with `computed_by_v4_2=false`.

| Diagnostic count | Value |
| --- | ---: |
| xlsx_locator_v2_rows | 344 |
| xlsx_locator_v2_candidate_component_rows | 900 |
| table_or_range_at1 | 23/344 |
| table_or_range_at3 | 29/344 |
| cell_or_value_at1 | 21/344 |
| cell_or_value_at3 | 26/344 |
| table_or_range_miss_after_sheet_hit_count | 228 |
| cell_or_value_miss_after_range_hit_count | 2 |
| abstain_or_disambiguation_count | 44 |
| sheet_or_workbook_locator_miss_count | 49 |
| workbook_disjoint_validation_rows | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| fine_tuning_executed | false |
| gpu_required_for_this_slice | false |

Counter source-of-truth: `report.json` embeds summary, metrics, per-query XLSX locator v2 manifest, candidate flow, failure taxonomy, source run references, holdout policy, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV, sidecar manifest, metrics sidecar, or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod:measurements-entry:start -->
### v4_1 Persisted XLSX SourceAtom Display Metadata

- Run: `official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod`
- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Run family: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Policy: diagnostic-only, non-production, single `report.json`; persisted/runtime-adjacent XLSX SourceAtom display metadata only.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod/report.json`

| Diagnostic count | Value |
| --- | ---: |
| persisted_xlsx_sourceatom_display_metadata_rows | 17 |
| persisted_display_value_available_count | 15 |
| persisted_raw_value_fallback_count | 1 |
| formula_cached_value_used_count | 1 |
| format_confidence_high_count | 16 |
| format_confidence_low_count | 1 |
| runtime_contract_violation_count | 0 |
| vector_payload_evidence_truth_violation_count | 0 |
| raw_xlsx_query_time_parsing_count | 0 |
| formula_evaluated_at_query_time_count | 0 |
| official_metric_input_rows | 0 |
| product_success_evidence_allowed | false |
| promotion_evidence | false |
| fine_tuning_executed | false |
| live_db_index_cache_readiness | false |
| gpu_required_for_this_slice | false |

Counter source-of-truth: `report.json` embeds summary, metrics, persisted_sourceatom_manifest, v3_22_rendering_contract_replay, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV or per-run Markdown is created.
<!-- official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod:measurements-entry:end -->

<!-- v4_source_grounded_runtime_locator_and_finetune_readiness:measurements-entry:start -->
### v4 Source-Grounded Runtime Locator And Fine-Tuning Readiness Charter

- v4 name: `v4_source_grounded_runtime_locator_and_finetune_readiness`
- Recommended run family if a run is created: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`
- Phase 1 closure basis: `official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod`
- Counter source-of-truth remains: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod/report.json`
- Charter: v4 extends the Phase 1 diagnostic source-first RAG contract into persisted/runtime-adjacent paths, improves family-separated XLSX locator and PDF file-identity bottlenecks, builds real blind/OOD holdout and leakage-audit infrastructure, and prepares fine-tuning lanes only after evidence and split quality gates are satisfied.

| v4 opening gate | Value |
| --- | --- |
| official_metric_input_rows | 0 |
| product_success_evidence_allowed | false |
| promotion_evidence | false |
| production_routing | false |
| live_db_index_cache_readiness | false |
| real_blind_ood_holdout_available | false |
| fine_tuning_readiness_only | true |
| fine_tuning_started | false |
| fine_tuning_executed | false |
| threshold_tuning | false |
| winner_selection | false |

Interpretation: v4 is opened as a non-production diagnostic charter, not as a scored run. Fine-tuning is a readiness lane only; any official evaluation, promotion, or production-readiness claim remains closed until user-owned gold/qrels/denominator decisions explicitly open it.
<!-- v4_source_grounded_runtime_locator_and_finetune_readiness:measurements-entry:end -->

<!-- phase1_diagnostic_contract_closure_after_v3_22:measurements-entry:start -->
### Phase 1 Diagnostic Contract Closure After v3_22

- Closure: `phase1_diagnostic_contract_closure_after_v3_22`
- Closure basis run: `official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod`
- Counter source-of-truth: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod/report.json`
- Artifact policy: single primary report artifact only. `status.jsonl is ignored`, `report.json is ignored`, and optional `review_packet.csv` remains user-owned/optional and ignored; it was not created for the closure.

| Diagnostic count | Value |
| --- | ---: |
| report_row_count | 14 |
| xlsx_answer_allowed_count | 10 |
| llm_invoked_count | 10 |
| raw_llm_response_present_count | 10 |
| parsed_final_answer_present_count | 10 |
| fail_closed_no_llm_invocation_count | 4 |
| display_value_used_count | 8 |
| raw_value_fallback_count | 1 |
| runtime_contract_violation_count | 0 |
| vector_payload_evidence_truth_violation_count | 0 |
| official_metric_input_rows | 0 |
| product_success_evidence_allowed | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |
| review_csv_created | false |

Interpretation: Phase 1 is closed as a diagnostic contract closure only. These v3_22 counters are not production routing, product success evidence, promotion evidence, official metric lift, live DB/index/cache readiness, XLSX locator performance completion, or representative product performance.
<!-- phase1_diagnostic_contract_closure_after_v3_22:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod:measurements-entry:start -->
### v3_22 XLSX Display-Value And Cell/Range Rendering

- Run: `official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod`
- Policy: diagnostic-only, non-production, SourceAtom/EvidenceBundle-owned XLSX display metadata; no raw XLSX query-time parsing, no sidecar primary artifacts, no review CSV unless user-owned review is required.
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod/report.json`

| Diagnostic count | Value |
| --- | ---: |
| report_row_count | 14 |
| xlsx_case_count | 14 |
| xlsx_answer_allowed_count | 10 |
| llm_invoked_count | 10 |
| raw_llm_response_present_count | 10 |
| parsed_final_answer_present_count | 10 |
| single_cell_value_count | 7 |
| small_range_table_count | 1 |
| bounded_range_summary_count | 1 |
| display_value_used_count | 8 |
| raw_value_fallback_count | 1 |
| format_metadata_unavailable_count | 1 |
| formula_cached_value_used_count | 1 |
| blank_cell_answer_count | 1 |
| unsupported_range_too_large_count | 1 |
| ambiguous_range_context_required_count | 2 |
| runtime_contract_violation_count | 0 |
| vector_payload_evidence_truth_violation_count | 0 |
| raw_file_query_time_accessed | false |
| official_metric_input_rows | 0 |
| review_csv_created | false |

Counter source-of-truth: `report.json` embeds summary, metrics, per_query, route/user/runtime/adapter/LLM/formatting audits, guardrails, leakage, prompt_manifest, verification, changed_files, residual_risks, and next_recommendation. The run directory intentionally does not write summary.json, metrics.json, per_query.jsonl, audit JSONL files, llm_io_packet.jsonl, guardrail_audit.json, leakage_audit.jsonl, or prompt_manifest.json.
<!-- official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod:measurements-entry:start -->
### v3_21 Agent Runtime LLM I/O Observability Packet

- Run: `official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod`
- Policy: diagnostic-only, non-production LLM I/O observability; fail-closed rows do not invoke LLM, local LLM unavailable rows emit no fake raw response, and all raw I/O stays in ignored JSONL/CSV artifacts rather than status or Markdown.

| Diagnostic count | Value |
| --- | ---: |
| llm_io_packet_row_count | 10 |
| llm_invocation_audit_row_count | 5 |
| llm_invoked_count | 5 |
| raw_llm_response_present_count | 5 |
| parsed_final_answer_present_count | 5 |
| fail_closed_no_llm_invocation_count | 5 |
| local_llm_unavailable_fail_closed_count | 0 |
| prompt_leakage_flag_count | 0 |
| response_leakage_flag_count | 0 |
| path_leakage_flag_count | 0 |
| evidence_truth_violation_count | 0 |
| vector_payload_evidence_truth_violation_count | 0 |
| runtime_contract_violation_count | 0 |
| production_write_attempt_count | 0 |
| broad_source_atom_scan_attempt_count | 0 |
| official_metric_input_rows | 0 |

Artifacts: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod/summary.json`, `metrics.json`, `per_query.jsonl`, `agent_tool_call_trace.jsonl`, `route_policy_audit.jsonl`, `runtime_contract_audit.jsonl`, `user_response_policy_audit.jsonl`, `db_contract_audit.jsonl`, `index_contract_audit.jsonl`, `cache_contract_audit.jsonl`, `live_runtime_smoke_audit.jsonl`, `llm_io_packet.jsonl`, `llm_io_packet.csv`, `llm_invocation_audit.jsonl`, `local_llm_readiness.json`, `prompt_manifest.json`, `guardrail_audit.json`, `leakage_audit.jsonl`, `review_packet.jsonl`, and `review_packet.csv`.

Counter source-of-truth: `metrics.json` carries the LLM invocation, leakage, adapter, and guardrail counters; `status.jsonl` records only counts, paths, hashes, and policy flags, not raw prompts or raw responses.
<!-- official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod:measurements-entry:start -->
### v3_20 Live-Runtime-Like DB/Index/Cache Smoke

- Run: `official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod`
- Policy: diagnostic-only, non-production live-runtime-like adapter smoke; no official metric, promotion, production DB/index/cache write, raw PDF/XLSX query-time parsing, broad SourceAtom scan, target/gold/supporting/expected locator use, or vector-payload evidence truth.

| Diagnostic count | Value |
| --- | ---: |
| live_runtime_smoke_row_count | 10 |
| db_contract_audit_row_count | 11 |
| index_contract_audit_row_count | 7 |
| cache_contract_audit_row_count | 10 |
| agent_tool_call_trace_row_count | 82 |
| db_available_count | 10 |
| db_unavailable_fail_closed_count | 1 |
| index_available_count | 6 |
| index_unavailable_fail_closed_count | 1 |
| cache_hit_count | 1 |
| cache_miss_count | 7 |
| cache_unavailable_count | 1 |
| cache_namespace_mismatch_blocked_count | 1 |
| runtime_contract_violation_count | 0 |
| production_write_attempt_count | 0 |
| broad_source_atom_scan_attempt_count | 0 |
| vector_payload_evidence_truth_violation_count | 0 |
| official_metric_input_rows | 0 |

Artifacts: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod/summary.json`, `metrics.json`, `per_query.jsonl`, `agent_tool_call_trace.jsonl`, `route_policy_audit.jsonl`, `runtime_contract_audit.jsonl`, `user_response_policy_audit.jsonl`, `db_contract_audit.jsonl`, `index_contract_audit.jsonl`, `cache_contract_audit.jsonl`, `live_runtime_smoke_audit.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `review_packet.jsonl`, and `review_packet.csv`.

Counter source-of-truth: `metrics.json` carries the adapter availability, fail-closed, cache, and guardrail counters; `status.jsonl` is a compact event ledger with acceptance counters and artifact hashes.
<!-- official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod:measurements-entry:start -->
### v3_19 Locator Ambiguity And Deictic Response Policy

- Run: `official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod`
- Policy: diagnostic-only, non-production response-policy hardening; ambiguous locator and missing-context deictic rows ask for clarification instead of answering.

| Diagnostic count | Value |
| --- | ---: |
| review_packet_row_count | 53 |
| agent_tool_call_trace_row_count | 469 |
| user_response_policy_audit_row_count | 53 |
| ambiguous_locator_count | 6 |
| ambiguous_locator_nonabstained_count | 0 |
| page_only_locator_count | 5 |
| page_only_locator_nonabstained_count | 0 |
| sheet_only_locator_count | 1 |
| sheet_only_locator_nonabstained_count | 0 |
| deictic_query_count | 18 |
| deictic_context_missing_count | 17 |
| deictic_context_missing_nonabstained_count | 0 |
| duplicate_query_hash_count | 9 |
| duplicate_query_text_group_count | 9 |
| rough_query_abstain_count | 13 |
| over_abstain_review_candidate_count | 0 |
| runtime_contract_violation_count | 0 |
| official_metric_input_rows | 0 |

Artifacts: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod/summary.json`, `metrics.json`, `per_query.jsonl`, `agent_tool_call_trace.jsonl`, `route_policy_audit.jsonl`, `runtime_contract_audit.jsonl`, `user_response_policy_audit.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `review_packet.jsonl`, and `review_packet.csv`.

Counter source-of-truth: `metrics.json` carries the full bucket maps and diagnostic counters; `status.jsonl` is a compact event ledger with the acceptance and headline diagnostic counters.

Verification note: the v3_19 `--check`, runtime-policy tests, artifact hash-lock test, guardrail test, status-sync test, py_compile, diff checks, protected-surface checks, and ignored-artifact checks pass in this checkout. The broad current-profile gate was reclassified during v3_20 preflight: sampled older v3_6_9-v3_15 compact artifact locks were available in this checkout, while the concrete blocker was the incomplete v3_20 live-runtime-like DB/index/cache handoff. This remains diagnostic-only and not a v3_19 official metric or promotion signal.
<!-- official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod:measurements-entry:start -->
### v3_18 Agent Runtime Tool Invocation Contract

- Run: `official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod`
- Policy: diagnostic-only, non-production agent runtime contract; no official metric, promotion, threshold tuning, winner selection, production DB/index write, raw PDF/XLSX query-time parsing, broad registry scan, target/gold/supporting/expected locator use, or vector-payload evidence truth.

| Diagnostic count | Value |
| --- | ---: |
| review_packet_row_count | 44 |
| agent_tool_call_trace_row_count | 388 |
| user_locator_query_count | 29 |
| rough_query_count | 14 |
| rough_query_abstain_count | 6 |
| over_abstain_review_candidate_count | 0 |
| unsupported_route_count | 1 |
| runtime_contract_violation_count | 0 |
| official_metric_input_rows | 0 |

Artifacts: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod/summary.json`, `metrics.json`, `per_query.jsonl`, `agent_tool_call_trace.jsonl`, `route_policy_audit.jsonl`, `runtime_contract_audit.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `review_packet.csv`, and `review_packet.jsonl`.
<!-- official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod:measurements-entry:start -->
### v3_17 User-Locator And Rough-Query Review Packet

- Run: `official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod`
- Policy: diagnostic-only answer-quality review; no official metric, score lift, promotion, threshold tuning, winner selection, production DB write, raw PDF/XLSX query-time parsing, target/gold locator use, expected/supporting text use, or direct normalized answer-value query matching.
- User locator policy: locator text is allowed only when it appears in the user query. Artifact target/gold/supporting/expected locator text is forbidden.
- Runtime evidence policy: resolved user locators hydrate through SourceAtom registry; SearchView/vector payload remains candidate-only.

| Diagnostic count | Value |
| --- | ---: |
| generated_response_count | 39 |
| review_packet_row_count | 39 |
| parse_ok_count | 39 |
| invalid_json_count | 0 |
| citation_rendered_count | 32 |
| abstain_count | 10 |
| user_locator_query_count | 21 |
| user_locator_resolved_count | 20 |
| user_locator_unresolved_count | 1 |
| rough_query_count | 18 |
| rough_query_abstain_count | 6 |
| unique_query_hash_count | 21 |
| hallucination_risk_flag_count | 0 |
| unsupported_claim_risk_count | 0 |
| xlsx_value_formatting_risk_count | 17 |
| over_abstain_review_candidate_count | 3 |
| official_metric_input_rows | 0 |

Artifacts: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod/summary.json`, `metrics.json`, `per_family.json`, `per_query.jsonl`, `responses.jsonl`, `review_packet.csv`, `review_packet.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `prompt_manifest.json`, `user_locator_parse_audit.jsonl`, `user_locator_resolution_audit.jsonl`, `rough_query_bucket_audit.jsonl`, `tool_registry.json`, `route_policy_audit.jsonl`, `runtime_materialization_plan.json`, and `latency_budget_contract.json`.
<!-- official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod:measurements-entry:start -->
### v3_16 Final LLM Answer-Quality Review Packet

- Run: `official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod`
- Policy: diagnostic-only local LLM answer generation for human review; no score lift, official metric, promotion, threshold tuning, winner selection, gold/qrels/label mutation, expected/supporting evidence mutation, raw PDF/XLSX query-time access, or production DB write.
- Inputs: v3_15 XLSX L7 contexts, v3_14 PDF/XLSX runtime traces, v3_13 PDF answer-ready controls, SourceAtom registry, and existing local LLM review conventions.
- Local LLM unavailable behavior: fail explicitly with `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`; no noop or extractive substitute is allowed.

| Diagnostic count | Value |
| --- | ---: |
| generated_response_count | 60 |
| review_packet_row_count | 60 |
| parse_ok_count | 60 |
| invalid_json_count | 0 |
| truncated_or_malformed_response_count | 0 |
| citation_rendered_count | 50 |
| abstain_count | 10 |
| unsupported_claim_risk_count | 0 |
| evidence_underuse_flag_count | 0 |
| xlsx_value_formatting_risk_count | 16 |
| pdf_weak_evidence_window_flag_count | 6 |
| official_metric_input_rows | 0 |
| L8_generation_executed | true |
| deterministic_official_execution | false |
| p95_llm_elapsed_ms | 2160.201 |

Runtime materialization and latency budget: L0-L8 are classified exactly once across `ingestion_time_materialized`, `index_time_materialized`, `query_time_lightweight`, `query_time_cacheable`, or `forbidden_query_time_work`; raw PDF/XLSX query-time parsing, full workbook/sheet scans, full PDF page/block scans, broad SourceAtom scans, and vector-payload-as-evidence-truth are forbidden. L8 generation latency is diagnostic-only and is not mixed into retrieval latency.

Artifacts: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod/review_packet.csv`, `review_packet.jsonl`, `responses.jsonl`, `summary.json`, `metrics.json`, `per_family.json`, `per_query.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `prompt_manifest.json`, `local_llm_readiness.json`, `runtime_materialization_plan.json`, `latency_budget_contract.json`, `per_layer_online_work_audit.jsonl`, `cache_key_contract.json`, and `forbidden_query_time_work_audit.json`.
<!-- official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement:measurements-entry:start -->
### v3_15 XLSX L3 Table/Range Locator Diagnostic

- Run: `official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement`
- Policy: diagnostic-only XLSX L3 table/range locator improvement; official_metric_input_rows=0; no answer generation, deterministic execution, promotion, threshold tuning, winner selection, direct normalized value matching, or product success claim.
- Inputs: v3_14 XLSX runtime adapter trace/per-query artifacts, v3_12 XLSX structural score components, v3_12 metrics-only eval reference flags, and SourceAtom registry joins. No raw XLSX/PDF query-time access.
- Metric boundary: table_or_range@1/@3 are metrics-only diagnostics from the v3_12 reference eval artifact, not v3_15 recomputed success metrics; cell/value@1/@3 are downstream diagnostics and not an optimization target.

| Metric | Value |
| --- | ---: |
| XLSX rows | 344 |
| PDF rows | 0 |
| L3 output availability | 300/344 |
| SourceAtom hydrated after L3 | 300/344 |
| EvidenceBundle assembled after L5 | 300/344 |
| answer-ready context available after L7 | 300/344 |
| L3 zero-output rows | 44 |
| raw_file_query_time_accessed | false |
| L8_executed | false |
<!-- official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod:measurements-entry:start -->
## 2026-05-25 - v3_14 Layered Retrieval Runtime Adapter Non-Prod

- Run: `official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod`
- Policy: diagnostic-only runtime adapter; official_metric_input_rows=0; product_success_evidence_allowed=false; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no L8 generation, deterministic answer execution, promotion, threshold tuning, or winner selection.
- Scope: query-time L0-L7 adapter replay over existing v3_12 XLSX and v3_13 PDF diagnostic artifacts. This measures trace completeness, candidate flow, latency instrumentation, and guardrails, not score lift.
- Holdout: fresh real source-document/workbook-disjoint holdout remains unavailable; current seen rows are diagnostic/no-regression only.

| Runtime adapter metric | value |
| --- | ---: |
| total runtime adapter rows | 673 |
| PDF rows | 329 |
| XLSX rows | 344 |
| median total retrieval latency ms | 0.0429 |
| p95 total retrieval latency ms | 0.06362 |
| max L4 hydrated candidate count | 3 |
| raw_file_query_time_accessed | false |
| L8_executed | false |

Per-family latency and candidate-count summaries are reported separately in the compact metrics, latency, candidate-flow, and per-family artifacts. No PDF/XLSX headline score, official metric, product success evidence, or promotion evidence is produced.
<!-- official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment:measurements-entry:start -->
## 2026-05-25 - v3_13 PDF File Identity Structural Locator Non-Prod Alignment

- Run: `official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment`
- Policy: diagnostic-only; official_metric_input_rows=0; product_success_evidence_allowed=false; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no answer generation, deterministic answer execution, fine-tuning, threshold tuning, winner selection, or promotion.
- Scope: PDF L2/L3 catch-up only. File identity metrics are reported separately from evidence-window metrics. XLSX v3_12 remains a visible control lane, not optimized in v3_13.
- Holdout: still insufficient. Fresh real PDF source-document-disjoint holdout is required before product success evidence.

| Lane | metric | value |
| --- | --- | ---: |
| PDF file identity | file_resolve@1 | 66/329 |
| PDF file identity | file_resolve@3 | 129/329 |
| PDF file identity | abstain_or_disambiguation | 182/329 |
| PDF file identity | accepted wrong rank1 with target in top3 | 63/329 |
| PDF file identity | wrong-file forcing delta from v3_11 | 0/329 |
| PDF structural locator | page candidates | 942/942 |
| PDF structural locator | block candidates | 942/942 |
| PDF structural locator | bbox candidates | 942/942 |
| PDF evidence window | same-page bounded candidates | 341/942 |
| PDF evidence window | answer-ready sufficiency | 251/329 |
| PDF evidence window | bbox correctness | not computed |
| XLSX v3_12 control | optimized in v3_13 | false |
| XLSX v3_12 control | cell_or_value@1 | 21/344 |

Reference: v3_11 PDF file_resolve@1 was 66/329. The wrong-file forcing delta is explicitly disclosed as zero because v3_13 does not change PDF file selection.
<!-- official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement:measurements-entry:start -->
## 2026-05-25 - v3_12 XLSX Structural Locator Non-Prod Improvement

- Run: `official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement`
- Policy: diagnostic-only; official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no answer generation, fine-tuning, threshold tuning, winner selection, or promotion.
- Scope: XLSX L3 structural locator only, after workbook/sheet routing. The checkpoint is v3_11; the compact candidate surface is the v3_9_1 XLSX candidate JSONL because v3_11 stores layer traces rather than candidate lists. PDF lanes and production namespaces are not touched.
- Holdout: still insufficient. Seen-reference lift is no-regression evidence only, not product success.

| XLSX diagnostic metric | v3_11 seen reference | v3_12 non-prod structural locator |
| --- | ---: | ---: |
| table_or_range@1 | 23/344 | 23/344 |
| table_or_range@3 | 29/344 | 29/344 |
| cell_or_value@1 | 20/344 | 21/344 |
| cell_or_value@3 | 26/344 | 26/344 |
| rank1 reranked count | n/a | 11 |
| structural-signal-empty rank1 | n/a | 0/300 |
| zero-signal legacy candidate demotion opportunities | n/a | 796 |
| zero-signal legacy rank1 demotions | n/a | 0 |
| table_or_range@1 gain/loss | n/a | +1/-1 |
| cell_or_value@1 gain/loss | n/a | +1/-0 |

Delta is diagnostic only: cell_or_value@1 +1 on seen-reference rows; table_or_range@1 delta 0 with row-level gain/loss churn shown above.
<!-- official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic:measurements-entry:start -->
## 2026-05-25 - v3_11 Layered Retrieval Diagnostic

- Run: `official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic`
- Policy: diagnostic-only; official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no answer generation, fine-tuning, threshold tuning, or winner selection.
- Layer contract: L0 query routing, L1 coarse candidates, L2 file/workbook identity, L3 structural locator, L4 SourceAtom hydration, L5 EvidenceBundle assembly, L6 evidence selector, L7 answer-ready context, L9 metrics/failure taxonomy. L8 generation/deterministic execution is skipped by design.
- Holdout: still insufficient. Existing seen validation is retained only for no-regression and layer attribution.

| Family/lane | Diagnostic metric | Value |
| --- | --- | ---: |
| XLSX | sheet@1 | 251/344 |
| XLSX | table_or_range@3 | 29/344 |
| XLSX | cell_or_value@3 | 26/344 |
| XLSX | signal-empty rank1 | 0/300 |
| PDF file identity | file_resolve@1 | 66/329 |
| PDF file identity | file_resolve@3 | 129/329 |
| PDF evidence window | bbox_present@3 | 7/942 |

PDF bbox correctness and answer-ready window sufficiency are explicitly not computed in this run; the lane records availability/decomposition only.
<!-- official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization:measurements-entry:start -->
## 2026-05-24 - v3_10 Fresh Real Holdout and XLSX Table-Axis Non-Prod Rematerialization

- Run: `official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization`
- Policy: diagnostic-only; official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no fine-tuning, no threshold tuning, no winner selection.
- Fresh real holdout: insufficient. PDF source-document-disjoint=0/20 target, XLSX workbook-disjoint=0/8 target, real query-fidelity included rows PDF=0 and XLSX=0 against the 100/family target.
- Synthetic OOD guard: 200 query candidates, anti-overfit guard only, product success evidence disallowed.
- XLSX table-axis materialization: `rag-data-xlsx-table-axis-ood-nonprod-v1`, SourceAtom rows=343, SearchUnit rows=343, overlay_only=false.

| XLSX lane | old seen reference | v3_10 non-prod seen smoke | fresh real holdout |
| --- | --- | --- | --- |
| signal-empty rank1 | 257/300 | 0/300 | 0/0 |
| table_or_range@3 | 29/344 | 29/344 | 0/0 |
| cell_or_value@3 | 26/344 | 26/344 | 0/0 |

PDF file identity baseline is kept separate from answer-ready evidence windows: v3_9_1 seen reference file_resolve@1=66/329; fresh real PDF baseline is blocked by missing source-document-disjoint holdout.
<!-- official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset:measurements-entry:start -->
## 2026-05-24 - v3_9_2 Overfit Risk Audit and Blind/OOD Holdout Reset

Run ID: `official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset`.

Scope:

- Diagnostic-only audit over v3_8_3, v3_9, and v3_9_1 artifacts.
- `official_metric_input_rows=0`; future scored adapter remains `DISABLED_PENDING_USER_APPROVAL`.
- Existing validation rows are now seen-validation-only and cannot be future success evidence.
- Fresh real holdout is insufficient: PDF source-document-disjoint `0`, XLSX workbook-disjoint `0`.

Key counts:

| Item | Count |
|---|---:|
| overfit delta rows | 48 |
| insufficient_blind_evidence labels | 48 |
| metric_tradeoff labels | 6 |
| synthetic OOD guard candidates | 14 |
| headline synthetic OOD guard rows | 14 |

Conclusion: no v3_9_1 improvement is preserved as future product success evidence. The useful retained signal is diagnostic direction: XLSX needs non-prod table-axis rematerialization, while PDF file identity must be evaluated separately from answer-ready evidence-window quality.
<!-- official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic:measurements-entry:start -->


## 2026-05-24 - v3_9_1 XLSX Table-Axis and PDF File Identity Diagnostic

Run family:
`official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic`

Scope:

- Diagnostic-only SourceAtom/SearchUnit locator experiment for XLSX plus oracle-free PDF file identity remeasurement.
- `official_metric_input_rows=0`; future scored adapter remains `DISABLED_PENDING_USER_APPROVAL`.
- No fine-tuning, gold/qrels/labels/expected-answer/supporting-evidence mutation, official denominator mutation, DB/production write, threshold tuning, winner selection, or promotion evidence.
- PDF, XLSX, and TEXT are not collapsed: TEXT is comparison-only, PDF file identity is separate from PDF answer-ready evidence windows.

XLSX 344-row locator surface:

| Metric | v3_8_3 baseline | v3_9_1 |
|---|---:|---:|
| sheet@1 | 249/344 | 251/344 |
| sheet@3 | 249/344 | 251/344 |
| table_or_range@1 | 22/344 | 23/344 |
| table_or_range@3 | 30/344 | 29/344 |
| cell_or_value@1 | 19/344 | 20/344 |
| cell_or_value@3 | 23/344 | 26/344 |
| signal-empty rank1 | 261/300 | 257/300 |

Workbook-disjoint XLSX validation movement:

| Metric | v3_8_3 validation | v3_9_1 validation |
|---|---:|---:|
| sheet@1 | 112/170 | 114/170 |
| sheet@3 | 112/170 | 114/170 |
| table_or_range@1 | 2/170 | 3/170 |
| table_or_range@3 | 6/170 | 9/170 |
| cell_or_value@1 | 2/170 | 3/170 |
| cell_or_value@3 | 6/170 | 9/170 |

XLSX query-fidelity validation included `118/170` rows, above the 30-row minimum. Excluded rows are retained in the audit and separated from headline interpretation.

PDF file identity, separate from answer-ready evidence-window quality:

| Metric | v3_8_2 baseline | v3_9_1 |
|---|---:|---:|
| file_resolve@1 | 65/329 | 66/329 |
| file_resolve@3 | 129/329 | 129/329 |
| abstain | 182/329 | 182/329 |
| wrong_file_block | 57/329 | 60/329 |

Interpretation:

- XLSX rank1 zero-signal pressure moved only slightly, from `261/300` to `257/300`; most remaining rank1 candidates still lack usable table-axis locator signals.
- XLSX validation movement exists at @1 and @3, but the dominant residual remains table/range localization after the workbook/sheet stage.
- PDF file identity gained one rank1 hit and blocked more wrong-file rank1 candidates, while @3 and abstain stayed flat.
- The prior PDF answer-ready gain remains a separate preselected-SourceAtom evidence-window result and is not counted as file-identity improvement here.
<!-- official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic:measurements-entry:end -->

## 2026-05-24 - v3_9 PDF/XLSX Bottleneck Quality Diagnostic

Purpose: focus the current phase on PDF evidence-window quality and XLSX
sheet/range/cell locator bottlenecks. TEXT is comparison-only and is not folded
into a PDF/XLSX headline.

Run ID: `official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement`.

Commands:

```powershell
python -X utf8 ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py --run-id official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label v3_9_pdf_xlsx_bottleneck_quality_improvement_dev_6pf --cases-per-family 6 --source-families PDF,XLSX --max-tokens 220 --query-max-tokens 160 --timeout-seconds 90
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label v3_9_pdf_xlsx_bottleneck_quality_improvement_validation_6pf --cases-per-family 6 --source-families PDF,XLSX --split-role validation_holdout --dev-summary ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_pdf_xlsx_bottleneck_quality_improvement_dev_6pf_summary.json --max-tokens 220 --query-max-tokens 160 --timeout-seconds 90
```

Split policy:

| Split | Rows | Families | Source-document/workbook disjoint from dev | Role |
|---|---:|---|---|---|
| Dev | 12 | PDF=6, XLSX=6 | n/a | dev-only diagnostic |
| Validation | 12 | PDF=6, XLSX=6 | true (`dev_overlap_document_count=0`) | non-official holdout |

Query-fidelity included score:

| Split | Family | Included rows | Raw final pass | Answer-ready pass | Interpretation |
|---|---|---:|---:|---:|---|
| Dev | PDF | 3 | 2/3 | 2/3 | dev-only, flat |
| Dev | XLSX | 0 | 0/0 | 0/0 | excluded as index-to-content or answer-value-in-query |
| Validation | PDF | 4 | 2/4 | 3/4 | generalized diagnostic signal (+1) |
| Validation | XLSX | 1 | 1/1 | 1/1 | flat; not generalized locator improvement |

All-row answer-quality score:

| Split | Family | Raw final pass | Answer-ready pass | Delta | Raw-pass regression |
|---|---|---:|---:|---:|---:|
| Dev | PDF | 2/6 | 3/6 | +1 | 0 |
| Dev | XLSX | 6/6 | 6/6 | 0 | 0 |
| Validation | PDF | 2/6 | 5/6 | +3 | 0 |
| Validation | XLSX | 6/6 | 6/6 | 0 | 0 |

Locator and residual notes:

- XLSX locator 344-row surface: range@1 `22/344`, cell/value@1 `19/344`;
  sheet@1 remains `249/344`, and top residual bucket remains
  `table_or_range_miss_after_sheet_hit=219`.
- Direct normalized-value query matching remains banned; direct normalized-value query matching remains banned. The current accepted
  structural-specificity tie-breaker is safe on the unit guard but did not move
  the persisted v3_8_3 locator metrics.
- PDF validation evidence-window readiness improved with native same-page/bbox
  windows: bounded expansion `6/6`, average raw score `0.1321`, expanded
  `0.5386`, delta `+0.4065`.
- Validation query-fidelity excluded rows: `7/12` (`PDF=2`, `XLSX=5`), kept in
  artifacts and excluded from generalized success claims.
- OCR was skipped because native text was present and no scanned/image-only or
  native-unusable candidate proved material OCR gain.

Artifacts:

| Artifact | Path |
|---|---|
| Summary | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_summary.json` |
| Metrics | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_metrics.json` |
| Per-family | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_per_family.json` |
| Per-query | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_per_query.jsonl` |
| Failure taxonomy | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_failure_taxonomy.json` |
| Query fidelity audit | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_query_fidelity_audit.jsonl` |
| PDF residual review | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_pdf_residual_review.jsonl` |
| XLSX locator residual review | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_xlsx_locator_residual_review.jsonl` |
| Split manifest | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_split_manifest.json` |

Verification is recorded in the final Korean report and status event; this
section will be amended only if a required verification command fails.

## 2026-05-24 - v3_9 Natural Answer-Quality Diagnostic

Purpose: measure actual answer-quality movement for natural, less-friendly
Korean queries across PDF, XLSX, and TEXT while keeping SourceAtom/EvidenceBundle
citations and all official surfaces closed.

Run ID: `official_answer_citation_agentic_loop_run_v3_9_natural_answer_quality_diagnostic`.

Commands:

```powershell
python -X utf8 ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py --label v3_9_natural_answer_quality_dev_6pf --cases-per-family 6 --source-families PDF,XLSX,TEXT --max-tokens 220 --query-max-tokens 160 --timeout-seconds 90
python -X utf8 ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py --label v3_9_natural_answer_quality_validation_6pf --cases-per-family 6 --source-families PDF,XLSX,TEXT --split-role validation_holdout --dev-summary ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_summary.json --max-tokens 220 --query-max-tokens 160 --timeout-seconds 90
python -X utf8 ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py --run-label v3_9_natural_answer_quality_dev_6pf
python -X utf8 ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py --run-label v3_9_natural_answer_quality_validation_6pf --previous-run-label v3_9_natural_answer_quality_dev_6pf
```

Split policy:

| Split | Rows | Families | Source-document disjoint from dev | Role |
|---|---:|---|---|---|
| Dev | 18 | PDF=6, XLSX=6, TEXT=6 | n/a | dev-only diagnostic |
| Validation | 18 | PDF=6, XLSX=6, TEXT=6 | true (`dev_overlap_document_count=0`) | non-official holdout |

All-row answer-quality score:

| Split | Family | Raw final pass | Answer-ready pass | Delta | Raw-pass regression |
|---|---|---:|---:|---:|---:|
| Dev | PDF | 2/6 | 3/6 | +1 | 0 |
| Dev | XLSX | 6/6 | 6/6 | 0 | 0 |
| Dev | TEXT | 2/6 | 2/6 | 0 | 0 |
| Validation | PDF | 2/6 | 5/6 | +3 | 0 |
| Validation | XLSX | 6/6 | 6/6 | 0 | 0 |
| Validation | TEXT | 5/6 | 5/6 | 0 | 0 |

Query-fidelity included score:

| Split | Family | Included rows | Raw final pass | Answer-ready pass | Interpretation |
|---|---|---:|---:|---:|---|
| Dev | PDF | 3 | 2/3 | 2/3 | dev-only, no headline gain |
| Dev | XLSX | 0 | 0/0 | 0/0 | excluded as index-to-content |
| Dev | TEXT | 6 | 2/6 | 2/6 | dev-only, flat |
| Validation | PDF | 4 | 2/4 | 3/4 | generalized diagnostic signal (+1) |
| Validation | XLSX | 1 | 1/1 | 1/1 | flat; mostly index-to-content excluded |
| Validation | TEXT | 6 | 5/6 | 5/6 | flat |

Failure and structure notes:

- Validation query-fidelity excluded rows: `7/18` (`PDF=2`, `XLSX=5`), kept in
  artifacts and excluded from generalized success claims.
- Validation PDF native text readiness: bounded expansion `6/6`, average raw
  answer-ready score `0.1277`, expanded `0.5367`, delta `+0.4090`.
- Validation residual after answer-ready: PDF has `low_evidence_overlap=1`;
  TEXT has `invalid_json=1`; XLSX has no answer-ready residual in this small
  preselected evidence slice.
- Non-PDF answer-ready rows reuse final locator responses. This neutralizes
  sampling regressions and keeps PDF evidence-window gains separate from XLSX
  and TEXT.
- Raw-pass-to-ready-fail regression stayed `raw_pass_to_ready_fail_regression=0`
  on both dev and validation.
- All-family `answer_quality` aggregate blocks remain diagnostic aggregates
  only (`diagnostic_aggregate_only=true`, `headline_allowed=false`); the
  reportable evidence is the family-separated query-fidelity validation table.
- The XLSX bottleneck did not move here. The active structural locator
  bottleneck remains the v3_8_3 scoped taxonomy:
  `table_or_range_miss_after_sheet_hit=219`.
- OCR was skipped because native text was present and the validation gain came
  from native same-page/bbox expansion, not OCR.

Artifacts:

| Artifact | Path |
|---|---|
| Dev summary | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_summary.json` |
| Dev metrics | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_metrics.json` |
| Dev per-family | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_per_family.json` |
| Dev per-query | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_per_query.jsonl` |
| Validation summary | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_summary.json` |
| Validation metrics | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_metrics.json` |
| Validation per-family | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_per_family.json` |
| Validation per-query | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_per_query.jsonl` |
| Dev review packet | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_v3_9_natural_answer_quality_dev_6pf/` |
| Validation review packet | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_v3_9_natural_answer_quality_validation_6pf/` |

Verification:

| Check | Result |
|---|---|
| `python -X utf8 -m py_compile ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py` | passed |
| `python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "pdf_answer_ready or pdf_xlsx_answer_quality_review_packet or v3_9 or natural_answer_quality_benchmark_can_opt_in_text or non_pdf_answer_ready_reuses"` | 21 passed, 95 deselected |
| `python -X utf8 -m pytest ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_9_natural_answer_quality_does_not_mutate_protected_surfaces -q` | 1 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_9_review_packet_query_fidelity_matches_compact_metrics -q` | 1 passed |
| `python -X utf8 -m pytest -p no:cacheprovider ai/tests/test_rag_diagnostic_status_sync.py::test_progress_measurements_triage_and_status_record_v3_9_natural_answer_quality_without_promotion -q` | 1 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q` | 3 passed |
| `python -X utf8 -m pytest ai/tests --rag-current -q` | 376 passed, 8 warnings |
| `git diff --check` | passed; line-ending warnings only |
| `python -X utf8 ai/scripts/rag_pdf_xlsx_perf_benchmark.py --label v3_9_natural_answer_quality_perf_smoke --warmups 1 --iterations 1 --output %TEMP%\codex-v3_9-natural-answer-quality-perf-smoke.json` | PDF native 25.225 ms, PDF OCR fallback 77.776 ms, XLSX merged range 285.717 ms, SearchUnit duplicate skip 103.475 ms |

Temporary files removed: `%TEMP%\codex-v3_9-natural-answer-quality-perf-smoke.json`.
Untracked files are checked in the final `git status --short --untracked-files=all`.

## 2026-05-24 - XLSX v3_8_3 Scoped Locator Anti-Overfit Validation

Purpose: harden the post-v3_8_3 XLSX scoped sheet/table-range/cell diagnostic
resolver without opening answer generation, official metrics, qrels, gold, or
promotion surfaces.

Commands:

```powershell
python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "v3_8_3_xlsx_query_locator_signals_normalize_page_sheet_names"
python -X utf8 -m py_compile ai/scripts/rag_official_answer_citation_agentic_loop_run_v1.py
python -X utf8 ai/scripts/rag_official_answer_citation_agentic_loop_run_v1.py --run-id official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic
python -X utf8 -m pytest ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_8_3_xlsx_scoped_cell_resolve_artifacts_are_registered_hash_locked_and_compact ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_8_3_xlsx_scoped_cell_resolve_writer_emits_compact_artifacts_and_summary_hashes -q
```

Split policy:

| Split | Rows | Workbook disjoint from dev | Source-identity disjoint from dev | Role |
|---|---:|---|---|---|
| Protected regression | 19 | n/a | n/a | sealed no-regression check |
| Dev | 155 | n/a | n/a | legacy v3_8_3 rows, dev-only |
| Validation | 170 | true | true | workbook-disjoint non-official validation |

Diagnostic locator metrics:

| Scope | sheet@1 baseline -> current | range@1 baseline -> current | cell/value@1 baseline -> current | abstain baseline -> current |
|---|---:|---:|---:|---:|
| Overall XLSX | 248/344 -> 249/344 | 22/344 -> 22/344 | 19/344 -> 19/344 | 44/344 -> 44/344 |
| Protected | 17/19 -> 17/19 | 17/19 -> 17/19 | 17/19 -> 17/19 | 1/19 -> 1/19 |
| Dev | 120/155 -> 120/155 | 3/155 -> 3/155 | 0/155 -> 0/155 | 9/155 -> 9/155 |
| Validation | 111/170 -> 112/170 | 2/170 -> 2/170 | 2/170 -> 2/170 | 34/170 -> 34/170 |

Interpretation:

- The only generalized gain is validation sheet@1 +1 from generic page-style
  sheet-name normalization (`26페이지` matching `26p`). It is diagnostic-only
  and not an official Hit@K/MRR/nDCG claim.
- Dev-only rows did not improve, so there is no dev-only pass-count gain being
  counted as success.
- Table/range and cell/value metrics stayed unchanged; the top remaining bucket
  remains `table_or_range_miss_after_sheet_hit=219`.
- A direct normalized-value query signal was tried and rejected because it
  regressed one validation cell/value pass. The frozen candidate rules now keep
  row/column/date and page-sheet normalization but do not use normalized-value
  text as a direct scoring signal.
- `official_metric_input_rows=0`; future scored adapter status remains
  `DISABLED_PENDING_USER_APPROVAL`; no PDF/OCR optimization was opened.

Artifacts:

| Artifact | Path |
|---|---|
| Summary | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_summary.json` |
| Metrics + compact miss matrix | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_metrics.json` |
| Per-query diagnostics | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_per_query.jsonl` |
| Per-family diagnostics | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_per_family.json` |
| Status ledger | `ai/eval/reports/rag-ingestion/status.jsonl` |

Verification:

| Check | Result |
|---|---|
| `python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "v3_8_3"` | 12 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_8_3_xlsx_scoped_cell_resolve_artifacts_are_registered_hash_locked_and_compact ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_8_3_xlsx_scoped_cell_resolve_writer_emits_compact_artifacts_and_summary_hashes -q` | 2 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_8_3_xlsx_scoped_cell_resolve_without_promotion -q` | 1 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_8_3_xlsx_scoped_cell_resolve_does_not_mutate_source_registry_or_protected_surfaces -q` | 1 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q` | 3 passed |
| `python -X utf8 -m pytest ai/tests --rag-current -q` | 367 passed, 8 warnings |
| `python -X utf8 -m py_compile ai/scripts/rag_official_answer_citation_agentic_loop_run_v1.py ai/scripts/rag_pdf_xlsx_perf_benchmark.py` | passed |
| `python -X utf8 ai/scripts/rag_pdf_xlsx_perf_benchmark.py --label v3_8_3_xlsx_scoped_locator_validation_smoke --warmups 1 --iterations 1 --output %TEMP%\codex-v3_8_3-xlsx-perf-smoke.json` | PDF native 30.625 ms, PDF OCR fallback 65.236 ms, XLSX merged range 198.396 ms, SearchUnit duplicate skip 95.566 ms |
| `git diff --check` | passed; line-ending warnings only |

Changed tracked files:

- `ai/scripts/rag_official_answer_citation_agentic_loop_run_v1.py`
- `ai/tests/test_rag_answer_citation_silver_manifest_v1.py`
- `ai/tests/test_rag_current_focused_test_profile_v1.py`
- `ai/tests/test_rag_diagnostic_status_sync.py`
- `ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py`
- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`

Temporary files removed: `%TEMP%\codex-v3_8_3-xlsx-perf-smoke.json`,
`%TEMP%\codex-v3_8_3-xlsx-baseline.json`. Untracked files: none.

## 2026-05-24 - PDF Answer-Ready Overfit Guard And Holdout

Purpose: keep PDF answer-ready evidence work diagnostic-only while separating
dev gains from validation evidence before any residual optimization.

Commands:

```powershell
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label answer_ready_pdf_v1_llm_15pf --cases-per-family 15 --max-tokens 220 --query-max-tokens 180 --timeout-seconds 90 --split-role dev_current_pdf_headline
python -X utf8 ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py --run-label answer_ready_pdf_v1_llm_15pf
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label answer_ready_pdf_v1_llm_15pf_validation --cases-per-family 15 --max-tokens 220 --query-max-tokens 180 --timeout-seconds 90 --split-role validation_holdout --dev-summary ai\eval\reports\rag-ingestion\quality\pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_summary.json
python -X utf8 ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py --run-label answer_ready_pdf_v1_llm_15pf_validation --previous-run-label answer_ready_pdf_v1_llm_15pf
```

Split policy:

| Split | Rows | PDF rows | XLSX rows | Source-document disjoint from dev | Success evidence allowed |
|---|---:|---:|---:|---|---|
| Dev current PDF headline | 30 | 15 | 15 | n/a | false |
| Validation holdout | 30 | 15 | 15 | true, overlap=0 | true, diagnostic-only |

Answer quality:

| Split/scope | Raw final pass | Combined answer-ready pass | Fresh answer-ready pass | Raw-final reused pass | Delta combined vs raw |
|---|---:|---:|---:|---:|---:|
| Dev all rows | 17/30 | 20/30 | 19/30 | 1/30 | +3 |
| Dev PDF all rows | 5/15 | 8/15 | 7/15 | 1/15 | +3 |
| Dev XLSX all rows | 12/15 | 12/15 | 12/15 | 0/15 | +0 |
| Dev query-fidelity headline | 9/17 | 12/17 | 11/17 | 1/17 | +3 |
| Dev PDF headline | 5/13 | 8/13 | 7/13 | 1/13 | +3 |
| Validation all rows | 18/30 | 20/30 | 17/30 | 3/30 | +2 |
| Validation PDF all rows | 8/15 | 9/15 | 6/15 | 3/15 | +1 |
| Validation XLSX all rows | 10/15 | 11/15 | 11/15 | 0/15 | +1 |
| Validation query-fidelity headline | 8/15 | 8/15 | 5/15 | 3/15 | +0 |
| Validation PDF headline | 8/14 | 8/14 | 5/14 | 3/14 | +0 |

Interpretation:

- The prior `19/30 -> 23/30`, headline `9/16 -> 11/16`, and PDF headline
  `5/12 -> 7/12` counts are retained only as prior dev/query-fidelity
  diagnostics.
- The fresh dev PDF headline gain is not counted as success by itself:
  `dev_only=true` and `success_evidence_allowed=false`.
- The source-document-disjoint holdout gives a small combined all-row PDF
  diagnostic gain (`8/15 -> 9/15`), but that combined count includes three
  raw-final reused passes. It has no query-fidelity headline PDF gain
  (`8/14 -> 8/14`) and fresh PDF answer-ready headline passes are `5/14`.
  Residual optimization should not claim generalized PDF answer-ready success
  from the dev headline count alone.
- Raw-pass-to-ready-fail regressions are zero in both dev and validation after
  the raw-final reuse guard.

PDF evidence readiness:

| Split | Bounded expansion | Weak snippets | Dot-heavy | Locator-only | OCR-ish | Avg raw score | Avg expanded score | Avg delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dev | 12/15 | 11/15 | 11/15 | 3/15 | 12/15 | 0.1235 | 0.4501 | +0.3266 |
| Validation | 15/15 | 11/15 | 11/15 | 0/15 | 14/15 | 0.1184 | 0.5291 | +0.4107 |

Residual review:

| Split | Answer-ready failed rows | Query-excluded review-only rows | Weak evidence | Dot/OCR artifact | Locator-only | Broad context | Evaluator limitation | Query drift | True answer failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dev answer-ready failures | 7 | 0 | 6 | 7 | 3 | 4 | 7 | 2 | 0 |
| Validation answer-ready failures | 6 | 0 | 6 | 6 | 0 | 2 | 2 | 0 | 0 |
| Validation full review table | 6 | 1 | 7 | 7 | 0 | 2 | 2 | 1 | 0 |

Primary artifacts:

- Dev summary:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_summary.json`
- Dev packet:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/`
- Validation summary:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_validation_summary.json`
- Validation packet:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf_validation/`
- Perf smoke:
  `ai/eval/reports/rag-ingestion/perf/pdf_xlsx_perf_answer_ready_overfit_guard_smoke.json`

Boundary and OCR rationale:

- `official_metric_input_rows=0` in both packets.
- The future scored adapter remains `DISABLED_PENDING_USER_APPROVAL`.
- Expected answers, supporting evidence, gold fields, qrels, labels, official
  denominator, namespace isolation, production, promotion, thresholds, and
  winner selection remain unchanged.
- OCR was skipped because validation did not prove native text absence or
  unusability, and OCR-ish residuals are still mixed with weak evidence,
  locator/citation shape, evaluator overlap, and query-policy issues.

Verification completed for this entry:

```powershell
python -X utf8 -m py_compile ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py ai\scripts\rag_pdf_xlsx_anti_overfit_audit.py
python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "pdf_xlsx_answer_quality_review_packet or pdf_answer_ready or query_fidelity or anti_overfit"
python -X utf8 ai\scripts\rag_pdf_xlsx_anti_overfit_audit.py
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label answer_ready_pdf_overfit_guard_perf_smoke --warmups 1 --iterations 1 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_answer_ready_overfit_guard_smoke.json
python -X utf8 -m pytest ai/tests/test_rag_diagnostic_status_sync.py -q -k "pdf_answer_ready or query_fidelity or status_jsonl"
python -X utf8 -m pytest ai/tests/test_rag_anti_shortcut_guardrail_audit_v1.py ai/tests/test_rag_diagnostic_guardrail_git_diff.py -q
python -X utf8 -m pytest ai/tests --rag-current -q
git diff --name-only -- ai/eval/eval_queries ai/eval/source_registry ai/eval/indexes ai/eval/silver ai/eval/reports/rag-ingestion/baseline_v1.json ai/eval/reports/rag-ingestion/metric_input_v1.json ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl
git diff --cached --name-only -- ai/eval/eval_queries ai/eval/source_registry ai/eval/indexes ai/eval/silver ai/eval/reports/rag-ingestion/baseline_v1.json ai/eval/reports/rag-ingestion/metric_input_v1.json ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl
git diff --check
git status --short --untracked-files=all
```

Results: focused packet tests `15 passed`; status sync `4 passed`; guardrail
tests `39 passed`; current profile `361 passed`. The first current-profile
attempt correctly failed on temporary anti-overfit audit files in the report
root; those files were removed and the audit default now writes to the system
temp directory instead of the protected report root.

Protected diff checks reported no tracked or staged changes under eval queries,
source registry, indexes, silver, official baseline/config, or candidate JSONL
surfaces. `git diff --check` passed with line-ending warnings only. `git status
--short --untracked-files=all` showed no untracked files.

Changed tracked files:

- `ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py`
- `ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py`
- `ai/scripts/rag_pdf_xlsx_anti_overfit_audit.py`
- `ai/tests/test_rag_answer_citation_silver_manifest_v1.py`
- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`

New tracked files: none. New repo-local scratch artifacts: none. Temporary
files removed: accidental report-root `rag_pdf_xlsx_anti_overfit_audit.json`
and `.csv`, plus the system-temp anti-overfit audit JSON/CSV created by the
final scanner run.

## 2026-05-22 - PDF Answer-Ready Evidence Readiness Audit

Purpose: improve diagnostic PDF answer quality by shaping retrieved PDF
evidence into answer-ready snippets, without changing gold labels, qrels,
expected answers, supporting evidence, denominator policy, namespace isolation,
or diagnostic-only semantics. XLSX stays in the run only as a no-regression
control.

Commands:

```powershell
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label answer_ready_pdf_v1_llm_15pf --cases-per-family 15 --max-tokens 220 --query-max-tokens 180 --timeout-seconds 90
python -X utf8 ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py --run-label answer_ready_pdf_v1_llm_15pf
```

Answer quality:

| Family | Raw final locator context | Normalized/expanded answer-ready context | Delta |
|---|---:|---:|---:|
| PDF | 5/15 | 8/15 | +3 |
| XLSX | 14/15 | 15/15 | +1 |
| Aggregate diagnostic-only | 19/30 | 23/30 | +4 |

Query fidelity addendum, 2026-05-24:

| Scope | Rows | Raw final pass | Answer-ready pass | Delta |
|---|---:|---:|---:|---:|
| All rows, query-fidelity-unverified | 30 | 19/30 | 23/30 | +4 |
| Headline-included fidelity subset | 16 | 9/16 | 11/16 | +2 |
| PDF headline-included subset | 12 | 5/12 | 7/12 | +2 |
| XLSX headline-included subset | 4 | 4/4 | 4/4 | +0 |

Query drift classification:

| Family | Headline included | Excluded | Severity counts |
|---|---:|---:|---|
| PDF | 12 | 3 | index_to_content_query=1, major_topic_drift=2, minor_specificity_change=7, style_only=5 |
| XLSX | 4 | 11 | index_to_content_query=11, minor_specificity_change=2, style_only=2 |

Rows excluded from the headline subset are not deleted. They remain in the
review packet with blank user decision fields and require user query approval
before any future official-adjacent adapter could consider them.

PDF Evidence Readiness:

| Metric | Value |
|---|---:|
| PDF audit cases | 15 |
| Bounded expansion applied | 11 |
| Weak snippets | 11 |
| Dot-heavy snippets | 11 |
| Locator-only flags | 4 |
| OCR-ish flags | 11 |
| Table/form-like flags | 0 |
| Average raw answer-ready score | 0.1152 |
| Average expanded answer-ready score | 0.3938 |
| Average answer-ready score delta | +0.2786 |
| XLSX context changed | false |

Primary artifacts:

- Run id:
  `pdf_xlsx_answer_quality_evidence_readiness_packet_answer_ready_pdf_v1_llm_15pf`
- Summary:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_summary.json`
- Full responses:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_responses.jsonl`
- PDF evidence-readiness audit:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_pdf_evidence_readiness_audit.jsonl`
- Review packet:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/`
- PDF delta audit:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/pdf_delta_audit.jsonl`
- Query fidelity audit:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/query_fidelity_audit.jsonl`
- PDF residual review:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/pdf_residual_review.md`

The audit records raw snippets, normalized snippets, original locator/page/bbox
metadata, character length, query overlap, repeated punctuation ratio,
text-density, locator-only/table-form/OCR-ish flags, answer-ready score, and
whether bounded expansion was applied. Example expansion keeps the original
page/bbox/source locator and expands a same-page PDF `text_block` heading
"산림청 정책연구용역 관리규정..." into nearby same-page form text including
"정책연구용역과제심의신청서" and "정책연구과제명". Expansion is capped by
same-page lines/chars and uses PDF block windows only as diagnostic context; it
does not mutate source PDFs or official gold surfaces.

Non-gold decisions and rationale:

- Dot leaders/repeated punctuation and excessive whitespace are normalized only
  in diagnostic evidence text; page numbers, decimals, legal/article numbers,
  citations, and original source metadata are preserved.
- Weak PDF snippets are expanded with same-page manifest neighbors first and
  same-page PDF block windows second when a local PDF path is available. Full
  pages are not dumped.
- Answer-ready score uses structural evidence-quality signals only: density,
  query overlap, repeated-punctuation ratio, and weak locator/table/OCR flags.
  It is not tuned against gold answers.
- Retrieval miss is reported as
  `not_recomputed_preselected_sourceatom_evidence_only`; this run measures
  answer-ready shaping on existing diagnostic PDF cases, not retrieval recall.

Remaining user-owned gold/policy decisions:

- answerable
- relevance
- expected answer
- supporting evidence
- pass/fail
- denominator eligibility
- policy note
- review approval
- query intent preserved
- query approval
- query policy note

PDF residual review after query-fidelity audit:

| Bucket | Count |
|---|---:|
| answer-ready failing PDF cases | 7 |
| residual-review rows, including query-drift pass rows | 8 |
| weak evidence | 7 |
| dot/OCR artifact | 8 |
| broad context | 3 |
| locator-only | 5 |
| table/form | 0 |
| query drift | 3 |
| evaluator limitation | 7 |
| true answer failure | 0 |

OCR decision: skipped for this slice. The diagnostic evidence points to query
drift, weak/locator-like evidence windows, and evaluator overlap limits before
OCR extraction failure. OCR-ish text remains measured but is not predictive
enough here to justify provider/source changes.

Guardrail status: `official_metric_input_rows=0`,
`future_scored_adapter=DISABLED_PENDING_USER_APPROVAL`, no promotion evidence,
no threshold tuning, no winner selection, and no gold/qrels/label/expected
answer/supporting evidence/denominator/namespace mutation.

Changed files for this slice:

- `ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py`
- `ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py`
- `ai/tests/test_rag_answer_citation_silver_manifest_v1.py`
- `ai/tests/test_rag_diagnostic_status_sync.py`
- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`
- `ai/eval/reports/rag-ingestion/status.jsonl`

Verification commands run:

```powershell
python -X utf8 -m py_compile ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py
python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_answer_ready_normalization_collapses_dot_leaders_without_touching_numbers ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_answer_ready_expansion_uses_bounded_same_page_neighbors_and_preserves_locator ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_answer_ready_score_demotes_locator_only_dot_heavy_evidence ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_answer_ready_dry_run_audit_is_diagnostic_only_and_keeps_xlsx_unchanged -q
python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_xlsx_answer_quality_review_packet_pairs_final_run_rows_and_keeps_user_fields_blank ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_xlsx_answer_quality_review_packet_future_adapter_stays_disabled_until_user_approval -q
python -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "pdf_xlsx_answer_quality_review_packet or pdf_answer_ready"
python -X utf8 -m pytest ai/tests/test_rag_source_bound_official_denominator_index.py::test_pdf_xlsx_llm_quality_benchmark_dry_run_records_silver_seed_and_policy ai/tests/test_rag_source_bound_official_denominator_index.py::test_pdf_xlsx_llm_quality_benchmark_joins_silver_without_locator_only_cross_join ai/tests/test_rag_source_bound_official_denominator_index.py::test_pdf_xlsx_llm_quality_benchmark_scores_locator_and_value_grounding -q
python -X utf8 -m pytest ai/tests/test_rag_diagnostic_status_sync.py::test_progress_measurements_triage_and_status_record_pdf_xlsx_quality_review_packet_without_promotion ai/tests/test_rag_diagnostic_status_sync.py::test_progress_measurements_triage_and_status_record_pdf_answer_ready_evidence_without_promotion -q
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 -m pytest ai/tests/test_rag_anti_shortcut_guardrail_audit_v1.py -q
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label answer_ready_pdf_v1_perf_smoke --warmups 1 --iterations 1 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_answer_ready_pdf_v1_smoke.json
git diff --check
```

Latest verification output after the 2026-05-24 quality rerun:
`python -m pytest ai/tests --rag-current -q` -> 351 passed, 8 warnings;
targeted packet/answer-ready tests -> 10 passed; status sync addendum tests ->
2 passed; source-bound benchmark tests -> 4 passed; anti-shortcut guardrail
tests -> 9 passed; py_compile PASS; protected gold/denominator diff empty;
`git diff --check` PASS with line-ending warnings only.

Performance smoke result: PDF native 27.804 ms, PDF OCR fallback 69.389 ms,
XLSX large merged range 239.061 ms, SearchUnit duplicate skip 121.446 ms. This
is a no-regression smoke for the existing performance path, not a new
representative product-performance claim.

## 2026-05-22 - PDF/XLSX LLM Query And Answer-Quality Benchmark

Purpose: measure whether locator-rich PDF/XLSX context and stricter answer
contracts improve local-LLM answer grounding without changing gold, qrels,
labels, expected answers, supporting evidence, denominators, namespaces, DB
state, or diagnostic-only policy. The benchmark is diagnostic-only and uses
generation-allowed non-official SearchView rows joined to the v3_7_2 weak
silver natural-query manifest as rewrite seeds. Silver rows are seeds only, not
gold or official labels.

Environment assumptions:

- Windows/PowerShell workspace:
  repo root path redacted
- Local OpenAI-compatible llama.cpp endpoint:
  `http://localhost:8081/v1`
- Model label: `gemma4-e2b-local`
- Benchmark script:
  `ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py`

Commands:

```powershell
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label final_llm_rewrite_all_llm_15pf_v3 --cases-per-family 15 --max-tokens 220 --query-max-tokens 180 --timeout-seconds 90
python -X utf8 ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py --run-label final_llm_rewrite_all_llm_15pf_v3
python -X utf8 -m pytest ai/tests/test_rag_source_bound_official_denominator_index.py -q
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label quality_goal_perf_smoke_final --warmups 1 --iterations 1 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_quality_goal_smoke_final.json
```

Inputs and policy:

| Item | Value |
|---|---|
| SearchView manifest | `ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl` |
| Silver seed manifest | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_7_2_local_llm_natural_silver_query_regeneration_llm_natural_silver_manifest_all.jsonl` |
| Join key | `source_family+source_identity+locator_fingerprint` |
| Cases | PDF=15, XLSX=15 |
| Silver seed rows | 30/30 |
| LLM rewrite rows | 30/30 |
| Fallback rows | 0 |
| Manifest partition | `core=30` |
| Promotion / tuning | false / false |

Query quality:

| Metric | Friendly baseline | LLM-rewritten final |
|---|---:|---:|
| Query count | 30 | 30 |
| Style count | 1 | 4 |
| Style distribution | `source_grounded=30` | `source_grounded=11`, `messy_user_like=10`, `terse_question=8`, `short_fragment=1` |
| Friendly suffix ratio | 1.0000 | 0.0000 |
| Max same six-character prefix | 15 | 1 |
| Average characters | 157.000 | 30.267 |

Answer quality:

| Family | Baseline legacy context | Final locator context | Delta |
|---|---:|---:|---:|
| PDF | 0/15 | 6/15 | +6 |
| XLSX | 0/15 | 15/15 | +15 |
| Aggregate diagnostic-only | 0/30 | 21/30 | +21 |

Failure taxonomy:

| Mode | Residuals |
|---|---|
| Baseline legacy context | `pdf_locator_missing=15`, `xlsx_locator_missing=15`, `low_evidence_overlap=10` |
| Final locator context | `low_evidence_overlap=9`, `locator_only_answer=1`, `pdf_locator_missing=1` |

Primary artifacts:

- Summary with 30 balanced sampled query/actual-response rows:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_final_llm_rewrite_all_llm_15pf_v3_summary.json`
- Full response JSONL:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_final_llm_rewrite_all_llm_15pf_v3_responses.jsonl`

Gold-review packet:

- Run id:
  `pdf_xlsx_answer_quality_gold_review_packet_final_llm_rewrite_all_llm_15pf_v3`
- Artifact directory:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/`
- Review CSV:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/review_packet.csv`
- Review JSONL:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/review_packet.jsonl`
- Markdown summary:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/summary.md`
- Manifest / schema validation:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/manifest.json`

Review packet rows=30. The packet pairs the 60 response rows into one row per
case, rehydrates SourceAtom evidence/locator data from the benchmark manifest,
keeps user-owned columns blank, sets `official_metric_candidate=FALSE`, and
records `official_metric_input_rows=0`. The future scored adapter is disabled
with status `DISABLED_PENDING_USER_APPROVAL`; it is documentation and schema
surface only until the user fills and approves review decisions and a separate
scored-eval integration change is made.

PDF residual review taxonomy:

| Likely cause | Count |
|---|---:|
| retrieval_miss | 0 |
| weak_snippet | 9 |
| ocr_ish_text | 1 |
| locator_only_evidence | 8 |
| table_form_formatting | 8 |
| semantic_answer_mismatch | 9 |
| evaluator_overlap_limitation | 9 |

User-owned decisions needed next:

- answerable
- relevance
- expected answer
- supporting evidence
- pass/fail
- denominator eligibility
- policy note
- review approval

Non-gold decisions and rationale:

- Existing v3_7_2 weak silver was used only as a query rewrite seed because it
  is diagnostic-only, not gold, not qrels, not official denominator, and not
  promotion evidence.
- The review packet generator pairs existing diagnostic response rows and
  SourceAtom evidence only; it does not use expected answers or supporting
  evidence and does not create official metric inputs.
- Locator-only silver matching was disabled; seed joins require source family,
  source identity, and locator fingerprint to avoid cross-document leakage.
- Query source-overlap misses are recorded as warnings, not fallback triggers,
  because Korean spacing, translation, and English/Korean paraphrase can make
  exact lexical validation too brittle; hard failures remain copy-seed,
  friendly-template ending, internal surface leak, parse failure, and length
  bounds.
- PDF scoring now requires bbox when bbox is available, and XLSX scoring
  requires cell/range when available; this measures citation/evidence
  usability rather than accepting doc/page or workbook-only locators.
- Long XLSX normalized text values accept meaningful token overlap while
  numeric values still require numeric equivalence; this avoids requiring a
  whole long cell string to be repeated verbatim.

Remaining diagnostic risks:

- PDF residuals are mostly low-evidence-overlap/answer-renderer behavior on
  very terse source snippets; improving those may require row-level answer
  policy or gold review before changing expected answer semantics.
- Query style is improved but still skewed toward source-grounded and terse
  question forms; broader style distribution can be tuned diagnostically, but
  should not be used as a promotion gate.
- The review packet is ready for human adjudication, but all blank user-owned
  fields must remain non-scoring until the user supplies explicit decisions.

## 2026-05-22 - PDF/XLSX Ingestion Performance Benchmark

Purpose: establish a measured, reproducible performance baseline for PDF and
XLSX ingestion paths before and after bounded hot-path fixes. Inputs are
synthetic and generated in memory to avoid gold, qrels, labels, official
denominator rows, production namespaces, and production indexes.

Environment assumptions:

- Windows/PowerShell workspace:
  repo root path redacted
- Python: `python -X utf8` (`Python 3.13.0` in this run)
- Benchmark script:
  `ai/scripts/rag_pdf_xlsx_perf_benchmark.py`
- Memory observation: `tracemalloc` peak KiB, not process RSS.

Commands:

```powershell
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label baseline_before_optimization --warmups 1 --iterations 3 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_baseline_before_optimization.json
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label final_after_pdf_probe_optimization_comparable_3x --warmups 1 --iterations 3 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_final_after_pdf_probe_optimization_comparable_3x.json
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label final_after_optimization --warmups 1 --iterations 5 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_final_after_optimization.json
```

Input sizes:

| Input | Shape |
|---|---|
| PDF native text | 8 pages, 72 text blocks/page, no supported deterministic table markers |
| PDF OCR fallback | 6 blank pages, fake OCR provider, 110 DPI render path |
| XLSX large merged range | 1 sheet, merged range `A1:ALL1000`, 40 visible rows after merge |
| SearchUnit duplicate skip | 1,800 synthetic docs/chunks, non-production diagnostic namespace |

Median latency:

| Case | Baseline 3x | Final comparable 3x | Delta |
|---|---:|---:|---:|
| PDF native text, no supported tables | 27.698 ms | 22.932 ms | -17.2% |
| PDF OCR fallback blank pages | 61.102 ms | 62.064 ms | +1.6% |
| XLSX large merged range | 20,191.989 ms | 165.670 ms | -99.2% |
| SearchUnit duplicate skip | 114.690 ms | 79.897 ms | -30.3% |

Median peak `tracemalloc`:

| Case | Baseline 3x | Final comparable 3x | Delta |
|---|---:|---:|---:|
| PDF native text, no supported tables | 408.5 KiB | 408.0 KiB | -0.1% |
| PDF OCR fallback blank pages | 43.1 KiB | 42.5 KiB | -1.4% |
| XLSX large merged range | 348,611.6 KiB | 6,430.8 KiB | -98.2% |
| SearchUnit duplicate skip | 2,227.0 KiB | 2,277.7 KiB | +2.3% |

5x final stability check:

| Case | Final 5x median |
|---|---:|
| PDF native text, no supported tables | 23.273 ms |
| PDF OCR fallback blank pages | 59.504 ms |
| XLSX large merged range | 159.260 ms |
| SearchUnit duplicate skip | 79.277 ms |

Profile ranking before code changes:

1. XLSX dangerous merged range: `openpyxl.load_workbook(read_only=False)`
   spent almost the entire 20.7 seconds in merged-cell/style binding.
2. PDF OCR fallback: `_render_pdf_page_png` was called once per OCR-needed
   page; rendering/PNG encoding dominated the synthetic blank-page case.
3. SearchUnit duplicate skip: `_is_duplicate_indexed` performed a repeated
   scan over existing chunks for every incoming document.
4. PDF native table extraction: deterministic table parsing was narrow enough
   to prefilter safely by the same supported marker families.

Policy: this is performance evidence only. It is not official retrieval
quality, not answer/citation promotion evidence, and not a representative
product-performance claim. No user-owned gold decision was needed.

## 2026-05-21 - Report Artifact Layout Rollup

Purpose: make the repo-local report surface small enough to scan while keeping
older evidence reproducible through the external archive resolver.

Current repo-local machine payloads:

- `ai/eval/reports/rag-ingestion/status.jsonl`
- Compact current v3_6_9 and later diagnostic artifacts required by the current
  RAG profile, including v3_10-v3_15 root artifacts and v3_16-v3_21
  quality/runtime packet directories.

Archived payload families:

- `ai/eval/reports/rag-ingestion/*` except the compact current files listed above:
  redacted external runtime archive for legacy RAG-ingestion reports
- former `ai/eval/reports/phase7/` and
  `ai/eval/reports/legacy-baseline-final/`:
  redacted external runtime archive for legacy report trees

Reader contract: use this file for metric ladder context, use
`docs/rag-ingestion-triage.md` for queue/row-level decisions, and use
`docs/rag-ingestion-progress.md` for current status and guardrails.

## Current Measurement Ladder

| Stage | Run family | Scope | Key result | Guardrail |
|---|---|---|---|---|
| Official first-run baseline | `official_answer_citation_metric_first_run_v1` | 29 official rows | PASS `8/29`, `CITATION_UNSUPPORTED=11`, `PARTIAL_OR_UNSUPPORTED=10` | Diagnostic baseline only |
| v1 diagnostic live-generation | `official_answer_citation_agentic_loop_run_v1` | Fixture-all index, noop/extractive generation | PASS `1/29`; fixture-all/noop/chunk-only limitations | `promotion_evidence=false` |
| Source-bound index readiness | `official_answer_citation_source_bound_index_build_readiness_v1` | 29 source-bound SearchUnits | `BUILD_READY_LOAD_CHECK_PASSED` | Non-production index only |
| v3 comparable live measurement | `official_answer_citation_agentic_loop_run_v3_comparable_live_measurement` | 29 rows, structured adapter retained for XLSX/PDF | PASS `27/29`; PDF `4/4`, XLSX `19/19`, TEXT `4/6` | Diagnostic-only; not answer/citation promotion evidence |
| v3_8_3 XLSX scoped miss taxonomy | `official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic` | 344 XLSX rows after persisted v3_8_2 workbook gate; legacy rows dev-only plus workbook-disjoint validation | sheet@1 `249/344`, range@1 `22/344`, cell/value@1 `19/344`; validation sheet@1 `112/170`; top miss bucket `table_or_range_miss_after_sheet_hit=219` | Diagnostic-only; no answer generation, gold/qrels/labels, or promotion evidence |
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
| v3_2_0 current-system live baseline | `official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline` | Settled 29 rows, no implementation behavior change | Lane A `24/29`, Lane B `25/29`, Lane C `24/29`; answer averages A/B/C `0.8276`, `0.8621`, `0.8276`; citation averages all `1.0` | Baseline only; retrieval ranking deferred |
| v3_2_1 four-TEXT residual triage | `official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage` | Only `text_namu_v2_0014`, `0017`, `0077`, `0084` | Primary categories `prompt=3`, `scorer=1`; only `text_namu_v2_0077` got query-scoped scorer normalization | No gold/label/denominator mutation |
| v3_2_2 post-fix remeasurement | `official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement` | Full 29-row remeasurement after v3_2_1 scorer fix | Lane A `24/29`, Lane B `26/29`, Lane C `25/29`; only `text_namu_v2_0077` Lane B/C changed to PASS; unexpected deltas `0` | Retrieval ranking deferred |
| v3_2_3 queue/lane actionability reconciliation | `official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation` | No-behavior classification over the v3_2_2 queue | Source queue 6 query ids / 12 failing lane items; Lane A-only frozen replay residuals `2`; live B/C actionable rows `4` | Diagnostic-only; no official retrieval ranking metric |
| v3_2_4 `gq_auto_010` PDF context provenance | `official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic` | Classification-only source audit for the PDF residual | Proved the v3_1_6 `pdfwin_b1c6527f848018640ad5ed231877c662` span was absent from the v3_2_2 context path; authorized v3_2_5 only | No behavior/index/export mutation |
| v3_2_5 `gq_auto_010` PDF context reconciliation | `official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix` | Full 29-row remeasurement with target-scoped v3_1_6 PDF window overlay | Lane A `24/29`, Lane B `27/29`, Lane C `26/29`; only `gq_auto_010` Lane B/C changed to PASS; unexpected deltas `0` | No gold/label/denominator/index mutation |
| v3_2_6 TEXT prompt/span rule remeasurement | `official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement` | Full 29-row remeasurement with lane-scoped narrow factual span prompt rule for actionable TEXT rows | Lane A `24/29`, Lane B `27/29`, Lane C `27/29`; only `text_namu_v2_0014` Lane C changed to PASS; unexpected deltas `0` | No gold/label/denominator/retrieval/index mutation |
| v3_2_7 post-fix closure | `official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup` | Status-ledger-only closure over v3_2_2 through v3_2_6 | Current Lane A `24/29`, Lane B `27/29`, Lane C `27/29`; active implementation queue empty; unexpected deltas `0` | No new behavior; retrieval ranking deferred |
| v3_3_0 post-closure source-of-truth audit | `official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit` | Status-ledger-only audit over v3_2_3 through v3_2_7 | Source chain PASS; Lane A/B/C remain `24/29`, `27/29`, `27/29`; active implementation queue empty | No behavior/implementation/metric mutation |
| v3_3_1 silver source-manifest readiness | `official_answer_citation_agentic_loop_run_v3_3_1_answer_citation_silver_source_manifest_readiness` | Manifest/readiness/status-only source audit for anti-overfit silver | Safe source manifests cannot be created: source-bound index has 29 rows, but official-overlap is `29/29`; eligible dev/holdout source candidates `0` | No silver generation/gold/promotion/metric mutation |
| v3_3_2 retrieval label-design packet | `official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet` | Human decision packet for future retrieval qrels design | Current denominator is answer/citation-only: 29 rows, PDF=4, TEXT=6, XLSX=19; proposed relevance/answerability schemas require user decision | No label/denominator/runtime/metric mutation |
| v3_4_0 official retrieval metric contract | `official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract` | Contract JSON plus qrels-schema JSON for future Hit@1/3/5, MRR@5, nDCG@5 | Defines qrels denominator options A/B/C, relevance/answerability 0-3 schemas, positive/gain rules, micro/macro boundaries | No qrels, labels, denominator, runtime, or metric mutation |

| v3_6_4 weak/noisy silver diagnostic metric | `official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric` | Frozen v3_6_3 weak/noisy manifests | core_only `665` rows, review_only_challenge `335` rows, all_diagnostic `1000` rows; generation coverage `0/1000` fail-closed | Diagnostic-only; not gold/qrels/promotion |
The official first-run baseline is a scored partial baseline and is not a
scorer backend blocker. It remains the immutable reference point; later rows in
this ladder are diagnostic deltas, not promotion evidence.


<!-- official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric:measurements-entry:start -->
## 2026-05-20 - v3_6_4 Diagnostic-Only Weak/Noisy Silver Metric

Run family:
`official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric`

Scope:

- Measured the frozen v3_6_3 weak/noisy silver manifests only: core_only `665`, review_only_challenge `335`, all_diagnostic `1000`.
- This is weak/noisy silver diagnostic measurement only: not gold, not official qrels, not official denominator, not promotion evidence, not threshold tuning, not winner selection, and not README representative product-performance evidence.
- Live generation was unavailable for this 1000-row pass, so answer/citation proxy metrics are fail-closed; deterministic source identity and locator feasibility metrics were still computed from the frozen manifest.

Compact diagnostic metrics:

| Partition | Rows | Source identity @1 | Locator fingerprint @1 | Context present | Citation source match | Answer non-empty | Runtime generation |
|---|---:|---:|---:|---:|---:|---:|---:|
| core_only | 665 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0/665 |
| review_only_challenge | 335 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0/335 |
| all_diagnostic | 1000 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0/1000 |

Failure taxonomy:

- runtime_fail_closed: `665`
- weak_silver_expected_answer_ambiguous: `334`
- review_only_source_quality_risk: `1`

Interpretation:

- core_only is the main interpretable diagnostic bucket.
- review_only_challenge is stress/noise and must not be merged into a headline result without that label.
- all_diagnostic is only a rough overall stress number.
- The split holdout remains non-source-isolated because v3_6_2/v3_6_3 recorded source identity crossing; official proximity rows remain review-only and core count is `0`.

Primary machine artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_per_row.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_aggregate_by_bucket.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_failure_taxonomy.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_policy_audit.json`
<!-- official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric:measurements-entry:end -->

## 2026-05-19 - v3_4_0 Official Retrieval Metric Contract

Run family:
`official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract`

Scope:

- Prepared a compact official retrieval ranking metric contract without
  creating qrels, labels, expected answers, supporting evidence, official
  Hit@K/MRR/nDCG values, or a collapsed Lane A/B/C score.
- Contract artifacts:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`
  and
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_qrels_schema.json`.
- Source policy packet:
  `official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet`.

Contract summary:

- Qrels denominator policy options remain user-owned: A all 29 rows, B
  track-by-track opening, or C only rows with settled retrieval labels.
- Relevance labels are `0 NOT_RELEVANT`, `1 TOPIC_RELATED`,
  `2 SUPPORTING_CONTEXT`, `3 EXACT_ANSWER_EVIDENCE`.
- Answerability labels are `0 NOT_ANSWERABLE`,
  `1 RELATED_BUT_NOT_ANSWERABLE`, `2 PARTIALLY_ANSWERABLE`,
  `3 FULLY_ANSWERABLE`.
- Default Hit@K/MRR positive rule is `relevance_grade >= 3` and
  `answerability_grade >= 3`.
- Default nDCG gain is the relevance grade; the answerability-gated variant
  maps gain to `0` when `answerability_grade < 2`.
- Metric list is Hit@1, Hit@3, Hit@5, MRR@5, nDCG@5 with micro overall and
  macro by source_family: TEXT, PDF, XLSX.

Blocked metrics:

- Official nDCG, MRR, Hit@K, micro/macro aggregates, and any collapsed Lane A/B/C
  score remain blocked until approved qrels labels are applied.
- Legacy XLSX retrieval CSV and XLSX silver retrieval-evidence files are
  explicitly prohibited as current official qrels.
- README wording must keep official answer/citation results separate from any
  official retrieval metric section.
- No prompt, retrieval, renderer, scorer, index/export, production, silver,
  promotion, threshold tuning, winner selection, gold, label, qrels, or
  denominator mutation occurred.

## 2026-05-19 - v3_3_2 Retrieval Label-Design Packet

Run family:
`official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet`

Scope:

- Prepared a human decision packet for official retrieval ranking metric
  readiness without creating labels, qrels, expected answers, supporting
  evidence, official retrieval metrics, or a collapsed Lane A/B/C score.
- Inspected the current answer/citation denominator registry, Lane A/B/C
  definitions, source-bound SearchUnit index artifacts, and v3_2_6 retrieved
  context artifacts.
- Current denominator snapshot remains 29 answer/citation rows:
  PDF=4, TEXT=6, XLSX=19. The source-bound index has 29 SearchUnits and all are
  `source_bound_official_denominator=true`.
- Lane definitions remain separated: Lane A `v3_primary_replay`, Lane B
  `live_llm_retrieval_topk`, and Lane C `live_llm_query_bound_oracle`.

Decision packet:

- Relevance schema options: binary `RELEVANT`/`IRRELEVANT`; or graded
  `EXACT_ANSWER_EVIDENCE`, `SUPPORTING_CONTEXT`, `TOPIC_RELATED`,
  `NOT_RELEVANT` for later nDCG-style judgments.
- Answerability schema options: reuse the existing ordinal 0-3 family
  `NOT_RELEVANT`, `RELATED_BUT_NOT_ANSWERABLE`, `PARTIALLY_ANSWERABLE`,
  `FULLY_ANSWERABLE`; optionally add track-specific flags for PDF FILE identity
  versus PDF CONTENT and XLSX cell/range evidence.
- Evidence policy options: strict query-bound SearchUnit-only qrels; or broader
  source-bound qrels that allow same-document/window/structured-locator evidence
  only after the user approves the rule.
- Denominator policy options: keep the current 29 rows as answer/citation-only
  until qrels are approved; open retrieval metrics track-by-track; or require
  all TEXT/XLSX/PDF labels before any official aggregate.
- Structured adapter policy: XLSX/PDF adapter PASS is evidence preview only.
  Human labels must bind to source-bound SearchUnit identity and locators, not
  to candidate-adapter output.

Blocked metrics:

- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score remain blocked.
- Required user decisions are relevance, answerability, gold policy,
  expected-answer/evidence policy, denominator inclusion/exclusion, and the
  structured XLSX/PDF deterministic-adapter handling rule.
- No prompt, retrieval, renderer, scorer, index/export, production, silver,
  promotion, threshold tuning, winner selection, gold, label, or denominator
  mutation occurred.

## 2026-05-19 - v3_3_1 Silver Source-Manifest Readiness

Run family:
`official_answer_citation_agentic_loop_run_v3_3_1_answer_citation_silver_source_manifest_readiness`

Scope:

- Updated only the answer/citation silver manifest/readiness contract and the
  compact status ledger for source-manifest readiness.
- Defined the minimum safe source-candidate schema:
  `query_id` or `candidate_id`, `source_family`, source-bound locator,
  `document_version_id`, `search_unit_id`, `source_text_available`, and the
  booleans `generation_source=false`, `promotion_evidence=false`, and
  `official_denominator_overlap=false`.
- Inspected the source-bound official-denominator index artifacts:
  `build.json`, `ingest_manifest.json`, `search_unit_manifest.jsonl`, and
  `source_bound_readiness_v1.json`.
- No silver generation, expected answer creation, gold label creation, official
  denominator mutation, production mutation, official nDCG/MRR/Hit@K, or
  collapsed Lane A/B/C score was produced.

Audit result:

- Safe silver source manifests can be created: `false`.
- Blocker: the only locator-complete source-bound SearchUnit material currently
  available is the non-production official-denominator index. It contains 29
  rows with source-text signals, but all 29 overlap the official denominator,
  so none can satisfy `official_denominator_overlap=false` for dev/holdout
  tuning silver.
- Eligible non-official source candidates: TEXT=0, XLSX=0, PDF=0.
- Silver JSONL files created: contract=`false`, dev=`false`, holdout=`false`.

Guardrail status:

- Silver remains non-gold, not official denominator, not promotion evidence,
  and not a generation source.
- Candidate result artifacts remain excluded as silver generation source.
- Official 29 query_ids remain excluded from dev/holdout tuning silver.
- Active implementation queue remains empty; no next implementation phase is
  opened.

## 2026-05-19 - v3_3_0 Post-Closure Source-Of-Truth Audit

Run family:
`official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit`

Scope:

- status-ledger-only audit over the v3_2_3 queue source, v3_2_4 PDF provenance
  diagnostic, v3_2_5 PDF overlay source/output, v3_2_6 TEXT prompt/span
  source/output, and v3_2_7 closure event.
- v3_2_7 remains status-ledger-only; `status.jsonl` is the source artifact for
  the closure state.
- v3_2_4 PDF provenance diagnostic is the gate that authorizes v3_2_5; v3_2_5
  reuses the existing v3_1_6 PDF window sidecar, and v3_2_6 then uses the
  v3_2_5 queue as source of truth.
- No live generation, prompt, renderer, scorer, retrieval, export, index, gold,
  expected answer, supporting evidence, label, denominator, silver, production,
  promotion, threshold tuning, winner selection, official nDCG, MRR, Hit@K, or
  collapsed Lane A/B/C score changed in v3_3_0.

Audit result:

- Source-of-truth chain: `PASS`.
- Rolling docs/status agreement: `PASS`.
- Current Lane A/B/C: `24/29`, `27/29`, `27/29`.
- Active implementation queue: empty; next implementation phase: `none`.
- Remaining diagnostic-only live B/C TEXT prompt/span residuals:
  `text_namu_v2_0017`, `text_namu_v2_0084`.
- Frozen Lane A replay residuals: `text_namu_v2_0012`, `text_namu_v2_0077`.

Flag semantics:

- `diagnostic_only=true`: audit/diagnostic evidence only, not promotion or
  official retrieval ranking evidence.
- `promotion_evidence=false`: no promotion, winner selection, threshold tuning,
  or production rollout evidence.
- `behavior_change_made=false for v3_3_0`; historical behavior changes remain
  limited to v3_2_5 PDF context assembly and v3_2_6 TEXT prompt/span.
- `implementation_change_made=false for v3_3_0`; no new implementation queue is
  opened.
- `scorer_behavior_mutation=false`; the earlier scorer-policy mutation remains
  closed in v3_2_2 and is not reopened.

Artifact retention:

- v3_2_3/v3_2_4 compact diagnostics and queues are retained as
  source-of-truth artifacts.
- v3_2_5/v3_2_6 full results, failure attribution, and audit payloads are
  retained because those phases changed measurement behavior.
- v3_2_7 and v3_3_0 are status-ledger-only events.
- No per-run Markdown report or v3_3_0 summary JSON was written. official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score remain deferred until
  relevance and answerability labels are settled.

## 2026-05-19 - v3_2_3 Queue/Lane Actionability Reconciliation

Run family:
`official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation`

Scope:

- Classification-only pass over the v3_2_2 queue, v3_2_2 results/failure
  attribution, v3_2_1 residual triage, and the v3_1_6 PDF expansion evidence.
- No live generation, prompt, renderer, scorer, retrieval, export, index, gold,
  label, denominator, silver, production, or promotion behavior changed.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.

Compact result:

- Source queue: 6 query ids / 12 failing lane items.
- Bucket counts: `frozen_replay_residual=2`,
  `pdf_context_provenance=1`, `text_prompt_span=3`.
- Lane A-only residuals: `text_namu_v2_0012`,
  `text_namu_v2_0077`; next phase `none`.
- Live B/C actionable rows: `gq_auto_010`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0084`.
- `v3_2_4_pdf_context_provenance` is required for `gq_auto_010`;
  `v3_2_5` remains conditional until v3_2_4 proves the v3_1_6 expansion is
  missing from the v3_2 measurement path.
- `v3_2_6_text_prompt_span_rule` is required only for
  `text_namu_v2_0014`, `text_namu_v2_0017`, and `text_namu_v2_0084`.

## 2026-05-19 - v3_2_7 Post-Fix Closure

Run family:
`official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup`

Scope:

- Status-ledger-only closure over the v3_2_2 baseline, v3_2_3 actionability
  reconciliation, v3_2_4 PDF provenance diagnostic, v3_2_5 PDF context fix,
  and v3_2_6 TEXT prompt/span remeasurement.
- v3_2_5 and v3_2_6 are the only implementation-changing post-v3_2_2 phases.
- No new live generation, prompt, renderer, scorer, retrieval, export, index,
  gold, expected answer, supporting evidence, label, denominator, silver,
  production, promotion, threshold tuning, winner selection, official nDCG,
  MRR, Hit@K, or collapsed Lane A/B/C score changed in v3_2_7.

Metric delta versus v3_2_2:

| Lane | v3_2_2 PASS | v3_2_7 current PASS | Delta |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 |
| Lane B `live_llm_retrieval_topk` | 26/29 | 27/29 | +1 |
| Lane C `live_llm_query_bound_oracle` | 25/29 | 27/29 | +2 |

Current quality:

| Lane | Answer avg | Citation avg | Current failure category |
|---|---:|---:|---|
| Lane A `v3_primary_replay` | `0.8276` | `1.0` | `LLM_TRUE_PARTIAL_SYNTHESIS=5` |
| Lane B `live_llm_retrieval_topk` | `0.9310` | `1.0` | `LLM_EXPECTED_SPAN_MISMATCH=2` |
| Lane C `live_llm_query_bound_oracle` | `0.9310` | `1.0` | `LLM_EXPECTED_SPAN_MISMATCH=2` |

Closure queue:

- Frozen Lane A replay residual: `text_namu_v2_0012`, `text_namu_v2_0077`.
- Live B/C TEXT prompt/span residual: `text_namu_v2_0017`,
  `text_namu_v2_0084`; both are `diagnostic_only_after_prompt_rule`.
- PDF context residual: none; `gq_auto_010` closed in v3_2_5.
- Scorer policy closed: `text_namu_v2_0077` Lane B/C closed in v3_2_2.
- `text_namu_v2_0014` closed in v3_2_6.
- Active implementation queue: empty; no next implementation phase is opened.

Artifact retention:

| Run | machine_manifest | compact_diagnostic_payload | canonical_result_payload | forensic_debug_payload | queue_source_of_truth | compact_status_ledger |
|---|---|---|---|---|---|---|
| v3_2_3 | summary JSON | diagnostics JSONL | none | none | queue JSON | `status.jsonl` |
| v3_2_4 | summary JSON | PDF context provenance diagnostics JSONL | none | none | queue JSON | `status.jsonl` |
| v3_2_5 | summary JSON | PDF context diagnostics JSONL | results JSONL | failure JSON, audit JSONL | queue JSON | `status.jsonl` |
| v3_2_6 | summary JSON | TEXT prompt/span diagnostics JSONL | results JSONL | failure JSON, audit JSONL | queue JSON | `status.jsonl` |
| v3_2_7 | none | none | none | none | none | `status.jsonl` closure event |

No referenced artifacts were deleted. Future closure-only phases can remain
status-ledger plus rolling-doc updates unless a test-backed reproducibility
contract requires summary JSON. official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score remain deferred
until relevance and answerability labels are settled.

## 2026-05-19 - v3_2_6 TEXT Prompt/Span Rule Remeasurement

Run family:
`official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`

Scope:

- Full 29-row remeasurement after an implementation-safe TEXT prompt behavior
  change.
- The prompt rule is general and source-bound: it asks TEXT rows with narrow
  factual questions to return only the required person, role, destination,
  release date, age, birthday, title, or described-attribute span from cited
  context.
- The rule is lane-scoped to the v3_2_5 live-actionable TEXT surfaces:
  `text_namu_v2_0014` Lane C, `text_namu_v2_0017` Lane B/C, and
  `text_namu_v2_0084` Lane B/C.
- The v3_2_5 `gq_auto_010` PDF window overlay is carried forward unchanged.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, retrieval, renderer, scorer, production
  index, non-production index/export rebuild, threshold tuning, winner
  selection, promotion, official nDCG, MRR, Hit@K, or collapsed Lane A/B/C
  score changed.

Metric delta versus v3_2_5:

| Lane | v3_2_5 PASS | v3_2_6 PASS | Delta |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 |
| Lane B `live_llm_retrieval_topk` | 27/29 | 27/29 | 0 |
| Lane C `live_llm_query_bound_oracle` | 26/29 | 27/29 | +1 |

Quality and residual checks:

- `text_namu_v2_0014` Lane C changed from `LLM_EXPECTED_SPAN_MISMATCH` to
  `PASS`; Lane B was already `PASS` and remained untouched by the prompt rule.
- `text_namu_v2_0017` and `text_namu_v2_0084` remain
  `diagnostic_only_after_prompt_rule` prompt/span residuals in live B/C.
- Non-target unexpected failure-category deltas: `0`.
- Answer quality averages are Lane A/B/C=`0.8276`, `0.9310`, `0.9310`.
- Citation support averages remain Lane A/B/C=`1.0`, `1.0`, `1.0`.
- Strict JSON parse, LLM-generated locator copy/missing/field mismatch, PDF
  `source_pdf_path`, XLSX `row_label`, and TEXT `text_locator` residuals all
  remain `0`.
- Denominator remains 29 rows: PDF=`4`, TEXT=`6`, XLSX=`19`.

Artifacts:

| Artifact | Role |
|---|---|
| `...v3_2_6_text_prompt_span_rule_remeasurement_summary.json` | machine manifest |
| `...v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl` | full 29-row result payload |
| `...v3_2_6_text_prompt_span_rule_remeasurement_failure.json` | failure attribution payload |
| `...v3_2_6_text_prompt_span_rule_remeasurement_audit.jsonl` | response audit payload |
| `...v3_2_6_text_prompt_span_rule_remeasurement_text_prompt_span_diagnostics.jsonl` | compact TEXT answer-span diagnostics |
| `...v3_2_6_text_prompt_span_rule_remeasurement_queue.json` | post-rule queue source of truth |
| `status.jsonl` | compact status ledger event |

## 2026-05-19 - v3_2_5 `gq_auto_010` PDF Context Reconciliation Fix

Run family:
`official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix`

Scope:

- Full 29-row remeasurement after a target-scoped prompt/context behavior change.
- The only implementation surface is measurement-source/context assembly wiring:
  reuse the existing v3_1_6 safe PDF paragraph/window sidecar for
  `gq_auto_010`.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, production index, non-production
  index/export rebuild, threshold tuning, winner selection, promotion, official
  nDCG, MRR, Hit@K, or collapsed Lane A/B/C score.

Metric delta versus v3_2_2:

| Lane | v3_2_2 PASS | v3_2_5 PASS | Delta |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 |
| Lane B `live_llm_retrieval_topk` | 26/29 | 27/29 | +1 |
| Lane C `live_llm_query_bound_oracle` | 25/29 | 26/29 | +1 |

Quality and residual checks:

- `gq_auto_010` Lane B/C changed from `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`
  and now cite `pdfwin_b1c6527f848018640ad5ed231877c662`.
- Non-target unexpected failure-category deltas: `0`.
- Answer quality averages are Lane A/B/C=`0.8276`, `0.9310`, `0.8966`.
- Citation support averages remain Lane A/B/C=`1.0`, `1.0`, `1.0`.
- Strict JSON parse, LLM-generated locator copy/missing/field mismatch, PDF
  `source_pdf_path`, XLSX `row_label`, and TEXT `text_locator` residuals all
  remain `0`.
- Denominator remains 29 rows: PDF=`4`, TEXT=`6`, XLSX=`19`.

Artifacts:

| Artifact | Role |
|---|---|
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_summary.json` | machine manifest |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_results.jsonl` | full 29-row result payload |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_failure.json` | failure attribution payload |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_audit.jsonl` | response audit payload |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_pdf_context_diagnostics.jsonl` | compact PDF context reconciliation diagnostics |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_queue.json` | post-fix queue source of truth |
| `status.jsonl` | compact status ledger event |

## 2026-05-19 - v3_2_0 to v3_2_2 Current Baseline, Residual Triage, And Remeasurement

Run families:

- `official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline`
- `official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage`
- `official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement`

v3_2_0 baseline:

| Lane | PASS | Answer avg | Citation avg |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | `24/29` | `0.8276` | `1.0` |
| Lane B `live_llm_retrieval_topk` | `25/29` | `0.8621` | `1.0` |
| Lane C `live_llm_query_bound_oracle` | `24/29` | `0.8276` | `1.0` |

v3_2_1 residual triage:

| Query ID | Primary | Secondary | Action |
|---|---|---|---|
| `text_namu_v2_0014` | prompt | - | diagnostic-only |
| `text_namu_v2_0017` | prompt | scorer | diagnostic-only |
| `text_namu_v2_0077` | scorer | prompt | query-scoped Korean polite/plain past-tense scorer normalization |
| `text_namu_v2_0084` | prompt | - | diagnostic-only |

v3_2_2 remeasurement:

| Lane | v3_2_0 | v3_2_2 | Delta |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | `24/29` | `24/29` | `0` |
| Lane B `live_llm_retrieval_topk` | `25/29` | `26/29` | `+1` |
| Lane C `live_llm_query_bound_oracle` | `24/29` | `25/29` | `+1` |

Comparison:

- The only failure-category changes are `text_namu_v2_0077` Lane B and Lane C:
  `LLM_EXPECTED_SPAN_MISMATCH -> PASS`.
- Unexpected failure-category changes: `0`.
- Official retrieval ranking metrics remain deferred because relevance and
  answerability labels are not settled.
- No gold rows, expected answers, supporting evidence, relevance labels,
  answerability labels, denominator membership, retrieval ranking policy,
  production behavior, silver, or promotion behavior changed.

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

<!-- repo_cleanup_20260609_diagnostic_inventory:measurements-entry:start -->
### 2026-06-09 Repo Cleanup Diagnostic Inventory

- Run key: `repo_cleanup_20260609_diagnostic_inventory`
- Primary artifact: `ai/eval/reports/rag-ingestion/runs/repo_cleanup_20260609_diagnostic_inventory/report.json`
- Interpretation: repository hygiene counters only. These are not retrieval, answer-quality, official metric, promotion, product-success, or live-readiness metrics.

| Counter | Value |
|---|---:|
| active tracked files before cleanup | 870 |
| initial repo-local transient directories removed | 20 |
| initial repo-local transient files removed | 357 |
| initial transient bytes removed | 6,825,734 |
| post-verification cache directories removed | 16 |
| post-verification cache files removed | 178 |
| post-verification cache bytes removed | 9,122,698 |
| no-cache verification prep cache directories removed | 8 |
| no-cache verification prep cache files removed | 72 |
| no-cache verification prep cache bytes removed | 3,747,180 |
| final broad-profile cache directories removed | 9 |
| final broad-profile cache files removed | 123 |
| final broad-profile cache bytes removed | 3,652,483 |
| diagnostic report artifacts deleted | 0 |
| protected gold/qrels/denominator/source/index/silver surfaces mutated | 0 |
| ambiguous generated or diagnostic surfaces held | all ambiguous surfaces |

<!-- repo_cleanup_20260609_diagnostic_inventory:measurements-entry:end -->

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
<!-- actual_rag_eval_single_artifact_vector_hybrid_nonprod:measurement-entry:start -->
## actual_rag_eval_single_artifact_vector_hybrid_nonprod - 2026-06-11

- Policy: non-production diagnostic actual-RAG eval only; no official metric, promotion evidence, product-success evidence, live-readiness claim, gold/qrels/label mutation, denominator mutation, or source registry mutation.
- Fixture primary artifact: `reports/rag_eval/actual_rag_eval_fixture_single_vector_final_20260611/report.json`; directory file count: `1` (`report.json` only).
- Text-golden primary artifact: `reports/rag_eval/actual_rag_eval_text_gold_single_vector_final_20260611/report.json`; directory file count: `1` (`report.json` only); comparison target: `actual_rag_eval_text_gold_single_vector_20260611`.
- Human-review exception proof: `reports/rag_eval/actual_rag_eval_fixture_review_packet_final_20260611/` contains `report.json` and `human_review_packet.csv` only, with `3` rows and blank human-owned fields.
- Retrieval backend for fixture/text-golden: requested `auto`, selected `hybrid`; BM25 enabled `true`, vector enabled `true`, hybrid enabled `true`; embedding model `BAAI/bge-m3`; embedding device `cuda:0`; gpu_used_for_embedding `true`; vector index kind `faiss`; vector index type `IndexFlatIP`; vector_dim `1024`; indexed_unit_count `300`.
- GPU preflight: `gpu_available=true`, `cuda_available=true`, `nvidia_smi_available=true`, `torch_available=true`, `torch_cuda_available=true`, device `cuda:0`, device_name `NVIDIA GeForce RTX 5080`.
- Fixture backend comparison: bm25/vector/hybrid empty rates `0.0/0.0/0.0`; candidate averages `3.5/5.0/5.0`; BM25-vector overlap avg `0.5`; p50 latency ms BM25/vector/hybrid `4.37135/22.85195/27.285`; embedding_build_latency_ms `11841.3546`; index_load_or_build_latency_ms `0.2383`; gpu_used_for_embedding_count `2`.
- Text-golden backend comparison: bm25/vector/hybrid empty rates `0.5/0.0/0.0`; candidate averages `2.166667/10.0/10.0`; BM25-vector overlap avg `0.5`; p50 latency ms BM25/vector/hybrid `4.528/8.5211/13.1208`; embedding_build_latency_ms `12049.0907`; index_load_or_build_latency_ms `0.3386`; gpu_used_for_embedding_count `6`.
- External VectorDB: not configured/invoked; local FAISS is non-production local vector index proof, not production VectorDB parity.
<!-- actual_rag_eval_single_artifact_vector_hybrid_nonprod:measurement-entry:end -->
