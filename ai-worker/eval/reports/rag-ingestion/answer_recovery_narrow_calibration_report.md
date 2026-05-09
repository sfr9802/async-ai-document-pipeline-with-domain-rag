# Answer Recovery Narrow Calibration Report

- Status: `PASS`.
- Selected policy: `calibrated_identity_exact_v1`.
- Tuning ready: `true_for_narrow_silver_only_calibration`.
- Production promotion ready: `false`.
- Official answer denominator ready: `false`.
- Frozen gold used for selection: `false`.
- Official denominator registry changed: `false`.

## Before/After Counts

- before_calibration_wrongly_supported_count: `10`
- after_calibration_wrongly_supported_count: `0`
- after_hidden_xlsx_surface_attempt_count: `3`
- after_pdf_file_lookup_content_mixing_attempt_count: `4`
- after_diagnostic_only_evidence_blocked_count: `8`

## Selected Counts

- total_evaluated: `185`
- initially_supported: `148`
- recovered_after_loop: `5`
- wrongly_supported_count: `0`
- unsupported_correctly_blocked_count: `32`
- clarification_needed_count: `6`
- hidden_xlsx_surface_attempt_count: `3`
- pdf_file_lookup_content_mixing_attempt_count: `4`
- diagnostic_only_evidence_blocked_count: `8`
- citation_coverage_before: `0.935135`
- citation_coverage_after: `0.962162`
- average_loop_iterations: `1.814815`

## Rejected Variants

- strict_support_score_0_85: no recovery or citation-coverage improvement
- retry_uncited_diagnostic_only: no recovery or citation-coverage improvement
- unsafe_pdf_file_token_overlap_support: wrongly_supported_count > 0, weakens PDF FILE identity exactness
- unsafe_hidden_xlsx_support: wrongly_supported_count > 0, weakens hidden XLSX blocking
- unsafe_diagnostic_only_support: wrongly_supported_count > 0, weakens diagnostic-only evidence blocking

## Guardrails

- official_denominator_registry_changed: `False`
- official_answer_denominator_opened: `False`
- production_index_mutation: `False`
- broad_indexing: `False`
- frozen_gold_training_rows: `0`
- frozen_gold_profile_selection: `False`
- tuned_text_section_boost_bm25_promotion_status: `diagnostic_only`
- ocr_idp_multimodal_denominator_role: `DIAGNOSTIC_ONLY`
- native_pdf_text_outranks_ocr_fallback: `True`
- pdf_file_lookup_semantics: `file_identity_only`
- pdf_file_lookup_success_claims: `content=False, page=False, bbox=False, table=False, row=False, column=False, value=False`
- production_promotion_ready: `False`
- official_answer_denominator_ready: `False`
