# Answer Recovery Tuning Report

## Status

- overall_status: `PASS`
- generated_at: `2026-05-11T02:47:54+00:00`
- artifact_profile: `compact`
- production_promotion_ready: `False`
- official_answer_denominator_ready: `False`
- official_denominator_registry_changed: `False`
- production_index_mutation: `False`
- broad_indexing: `False`

## Calibration Summary

- selected_policy: `calibrated_identity_exact_v1`
- safe_recall_selected_policy: `baseline_selected_policy`
- total_evaluated: `185`
- before_calibration_wrongly_supported_count: `10`
- after_calibration_wrongly_supported_count: `0`
- recovered_after_loop: `5`
- citation_coverage_before: `0.935135`
- citation_coverage_after: `0.962162`
- rejected_variant_count: `5`
- key_rejected_variants: `[{"rejection_reasons": ["no recovery or citation-coverage improvement"], "variant_name": "strict_support_score_0_85"}, {"rejection_reasons": ["no recovery or citation-coverage improvement"], "variant_name": "retry_uncited_diagnostic_only"}, {"rejection_reasons": ["wrongly_supported_count > 0", "weakens PDF FILE identity exactness"], "variant_name": "unsafe_pdf_file_token_overlap_support"}, {"rejection_reasons": ["wrongly_supported_count > 0", "weakens hidden XLSX blocking"], "variant_name": "unsafe_hidden_xlsx_support"}, {"rejection_reasons": ["wrongly_supported_count > 0", "weakens diagnostic-only evidence blocking"], "variant_name": "unsafe_diagnostic_only_support"}]`

## Missed / Blocked Recovery Summary

- total_missed_or_blocked: `32`
- safe_recovery_candidates: `0`
- blocked_by_lane: `IDP_SHADOW=2, MULTIMODAL_SHADOW=1, OCR_SHADOW=1, PDF_CONTENT=2, PDF_FILE_LOOKUP=18, TEXT=3, XLSX=5`
- blocked_by_reason: `IDP_DIAGNOSTIC_ONLY_BLOCKED=2, MULTIMODAL_DIAGNOSTIC_ONLY_BLOCKED=1, OCR_DIAGNOSTIC_ONLY_BLOCKED=1, PDF_FILE_HARD_NEGATIVE_DO_NOT_RECOVER=10, PDF_FILE_IDENTITY_AMBIGUOUS=8, POLICY_CORRECTLY_BLOCKED=3, TRUE_UNANSWERABLE=5, XLSX_NEEDS_USER_METRIC_OR_PERIOD=2`

## Triage Consolidation

- category_counts: `SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE=5, SAFE_RECOVERABLE_WITH_CANONICAL_LINKING=0, INDEX_SCOPE_MISSING=5, POLICY_BLOCKED_CORRECTLY=17, GOLD_POLICY_REQUIRED=6, DIAGNOSTIC_ONLY_DO_NOT_PROMOTE=4, UNKNOWN_NEEDS_MANUAL_REVIEW=0`
- row_groups: `promotion_candidate=[], safe_recoverable_report_only=['expanded_text_recovery_015', 'expanded_text_recovery_030', 'expanded_text_recovery_045', 'expanded_text_recovery_060', 'expanded_text_recovery_075'], diagnostic_only=['expanded_idp_shadow_001', 'expanded_idp_shadow_002', 'expanded_multimodal_shadow_001', 'expanded_ocr_shadow_001'], policy_blocked_correctly=['expanded_pdf_file_lookup_005', 'expanded_pdf_file_lookup_006', 'expanded_pdf_file_lookup_007', 'expanded_pdf_file_lookup_008', 'expanded_pdf_file_lookup_009', 'expanded_pdf_file_lookup_010', 'expanded_pdf_file_lookup_011', 'expanded_pdf_file_lookup_012', 'expanded_pdf_file_lookup_013', 'expanded_pdf_file_lookup_014', 'expanded_pdf_file_lookup_015', 'expanded_pdf_file_lookup_016', 'expanded_pdf_file_lookup_021', 'expanded_pdf_file_lookup_028', 'expanded_xlsx_hidden_blocked_001', 'expanded_xlsx_hidden_blocked_002', 'expanded_xlsx_hidden_blocked_003'], index_scope_missing=['expanded_pdf_content_uncited_017', 'expanded_pdf_content_uncited_034', 'expanded_text_uncited_022', 'expanded_text_uncited_044', 'expanded_text_uncited_066'], gold_policy_required=['expanded_pdf_file_lookup_017', 'expanded_pdf_file_lookup_018', 'expanded_pdf_file_lookup_019', 'expanded_pdf_file_lookup_020', 'expanded_xlsx_constraint_013', 'expanded_xlsx_constraint_026'], unknown_needs_manual_review=[], excluded_frozen_gold_sourced=['expanded_pdf_file_lookup_017', 'expanded_pdf_file_lookup_018', 'expanded_pdf_file_lookup_019', 'expanded_pdf_file_lookup_020', 'expanded_pdf_file_lookup_021', 'expanded_pdf_file_lookup_022', 'expanded_pdf_file_lookup_023', 'expanded_pdf_file_lookup_024', 'expanded_pdf_file_lookup_025', 'expanded_pdf_file_lookup_026', 'expanded_pdf_file_lookup_027', 'expanded_pdf_file_lookup_028']`
- frozen_gold_sourced_excluded_count: `12`
- frozen_gold_used_for_selection: `False`
- frozen_gold_used_for_training: `False`
- gold_policy_required_user_review: `[{"case_type": "pdf_file_lookup_identity", "codex_decision": "not_decided", "judgment_needed": "User gold-policy judgment only: expected answer/evidence semantics, answerability/relevance label, and whether a future official denominator may include the row.", "lane": "PDF_FILE_LOOKUP", "reason": "Exact or canonical file identity is missing or ambiguous.", "row_id": "expanded_pdf_file_lookup_017"}, {"case_type": "pdf_file_lookup_identity", "codex_decision": "not_decided", "judgment_needed": "User gold-policy judgment only: expected answer/evidence semantics, answerability/relevance label, and whether a future official denominator may include the row.", "lane": "PDF_FILE_LOOKUP", "reason": "Exact or canonical file identity is missing or ambiguous.", "row_id": "expanded_pdf_file_lookup_018"}, {"case_type": "pdf_file_lookup_identity", "codex_decision": "not_decided", "judgment_needed": "User gold-policy judgment only: expected answer/evidence semantics, answerability/relevance label, and whether a future official denominator may include the row.", "lane": "PDF_FILE_LOOKUP", "reason": "Exact or canonical file identity is missing or ambiguous.", "row_id": "expanded_pdf_file_lookup_019"}, {"case_type": "pdf_file_lookup_identity", "codex_decision": "not_decided", "judgment_needed": "User gold-policy judgment only: expected answer/evidence semantics, answerability/relevance label, and whether a future official denominator may include the row.", "lane": "PDF_FILE_LOOKUP", "reason": "Exact or canonical file identity is missing or ambiguous.", "row_id": "expanded_pdf_file_lookup_020"}, {"case_type": "xlsx_needs_user_constraint", "codex_decision": "not_decided", "judgment_needed": "User gold-policy judgment only: expected answer/evidence semantics, answerability/relevance label, and whether a future official denominator may include the row.", "lane": "XLSX", "reason": "Needs user metric or period; strict wrapper expansion must not guess.", "row_id": "expanded_xlsx_constraint_013"}, {"case_type": "xlsx_needs_user_constraint", "codex_decision": "not_decided", "judgment_needed": "User gold-policy judgment only: expected answer/evidence semantics, answerability/relevance label, and whether a future official denominator may include the row.", "lane": "XLSX", "reason": "Needs user metric or period; strict wrapper expansion must not guess.", "row_id": "expanded_xlsx_constraint_026"}]`
- interpretation: `promotion_candidate=No current row is a production-promotion candidate., safe_recoverable_report_only=Recovered rows remain report-only evidence until human-reviewed answer/evidence labels and an explicit promotion policy exist., index_scope_missing=Do not count as retrieval/ranking failures unless source evidence is proven in-scope and indexed., policy_blocked_correctly=Preserve current fail-closed blocks; do not count as recovery failures., diagnostic_only=Do not promote OCR/IDP/multimodal or other diagnostic-only evidence.`

## Embedding Backend Summary

- embedding_backend_available: `True`
- backend_contract_status: `available`
- backend_provider_constructible: `True`
- backend_probe_embedding_succeeded: `True`
- backend_embedding_model: `BAAI/bge-m3`
- backend_embedding_dimension_detected: `1024`
- staging_backfill_enabled_by_config: `False`
- staging_backfill_status: `skipped_backfill_disabled_by_config`
- vector_write_attempted: `False`
- namespace_created: `False`
- staging_namespace_safe: `True`
- existing_vector_indexes_detected: `False`

## Embedding Readiness Summary

- manifest_rows: `37`
- production_eligible_source_count: `0`
- already_embedded_safe_source_count: `0`
- existing_vector_indexes_detected: `False`
- staging_namespace_safe: `True`
- index_scope_missing_cause_counts: `source_artifact_exists_but_not_embedded=0, canonical_source_mapping_absent=2, indexing_scope_policy=0, source_is_diagnostic_only=0, hidden_xlsx=0, pdf_file_identity_content_ambiguous=0, unavailable_source_content=3, gold_policy_required=0`
- safe_evidence_row_ids: `["expanded_text_recovery_015", "expanded_text_recovery_030", "expanded_text_recovery_045", "expanded_text_recovery_060", "expanded_text_recovery_075"]`
- safe_evidence_chunk_ids: `["77064b8aff166063", "6e49cb019ae006b7", "602bb6e164e1b82f", "61c8254cc3833e68", "4b66eafbcee9f096"]`
- namespace_names: `[]`

## Existing Embedding Retrieval Probe Summary

- probe_status: `DEFERRED`
- defer_reason: `ValueError: No existing embedding namespace found for safe rows`
- target_count: `0`
- found_at_rank_1_count: `0`
- found_in_top_10_count: `0`
- target_found_top_k_count: `0`
- read_only: `True`
- namespace: ``
- rank_summary: ``

## Guardrails

- official_denominator_registry_changed: `False`
- official_answer_denominator_opened: `False`
- production_index_mutation: `False`
- broad_indexing: `False`
- frozen_gold_training_rows: `0`
- frozen_gold_profile_selection: `False`
- expected_answer_or_label_embedding_count: `0`
- hidden_xlsx_support_eligible_count: `0`
- pdf_file_content_mixing_support_eligible_count: `0`
- diagnostic_only_support_eligible_count: `0`
- production_promotion_ready: `False`
- official_answer_denominator_ready: `False`
- vector_write_attempted: `False`
- namespace_created: `False`
- production_eligible_source_count: `0`

## Verification

- runners_executed: `["answer_recovery_narrow_calibration", "answer_recovery_missed_safe_recovery_analysis", "answer_recovery_embedding_backend_contract_recheck", "answer_recovery_embedding_readiness", "answer_recovery_existing_embedding_retrieval_probe"]`
- pytest_results: `not_run_by_report_runner`
- git_diff_check_result: `not_run_by_report_runner`
- official_denominator_registry_json_diff_status: `unchanged`
- official_denominator_registry_json_cached_diff_status: `unchanged`
- official_denominator_registry_diff_proof: `path=ai-worker/eval/eval_queries/official_denominator_registry.json, command=git diff --quiet -- ai-worker/eval/eval_queries/official_denominator_registry.json; git diff --cached --quiet -- ai-worker/eval/eval_queries/official_denominator_registry.json, changed=False, unstaged_diff_empty=True, staged_diff_empty=True, diff_empty=True, diff_stdout_bytes=0`
- known_warnings: `[]`
