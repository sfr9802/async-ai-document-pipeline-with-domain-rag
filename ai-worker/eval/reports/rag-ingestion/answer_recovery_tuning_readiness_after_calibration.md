# Answer Recovery Tuning Readiness After Calibration

- Status: `PASS`.
- Tuning ready: `true_for_narrow_silver_only_calibration`.
- Production promotion ready: `False`.
- Official answer denominator ready: `False`.
- Reason: No wrongly-supported cases remain and diagnostic guardrails pass.

## Counts

- total_evaluated: `185`
- wrongly_supported_count: `0`
- unsupported_correctly_blocked_count: `32`
- hidden_xlsx_surface_attempt_count: `3`
- pdf_file_lookup_content_mixing_attempt_count: `4`
- diagnostic_only_evidence_blocked_count: `8`
- recovered_after_loop: `5`

## Guardrails

- official_denominator_registry_changed: `False`
- official_answer_denominator_opened: `False`
- production_index_mutation: `False`
- broad_indexing: `False`
- frozen_gold_training_rows: `0`
- frozen_gold_profile_selection: `False`
- tuned_text_section_boost_bm25_promotion_status: `diagnostic_only`
- pdf_file_lookup_semantics: `file_identity_only`
- pdf_file_lookup_success_claims: `content=False, page=False, bbox=False, table=False, row=False, column=False, value=False`
- ocr_idp_multimodal_denominator_role: `DIAGNOSTIC_ONLY`
- native_pdf_text_outranks_ocr_fallback: `True`

- Next: Proceed only to narrow silver-only calibration; do not run broad tuning or production promotion.
