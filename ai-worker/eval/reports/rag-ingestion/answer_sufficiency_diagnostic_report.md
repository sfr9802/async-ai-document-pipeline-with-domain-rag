# Answer Sufficiency Diagnostic Report

- Status: `PASS`.
- Diagnostic/runtime bridge only; no official answer denominator opened.
- Production index mutation: `false`; broad indexing: `false`.

## Counts

- total_evaluated: `10`
- initially_supported: `3`
- recovered_after_loop: `1`
- clarification_needed: `1`
- unsupported_after_recovery: `4`
- lane_mismatch: `1`
- hidden_xlsx_blocked: `1`
- pdf_file_lookup_content_mixing_blocked: `1`
- ocr_diagnostic_evidence_used: `1`
- idp_diagnostic_evidence_used: `1`
- multimodal_diagnostic_evidence_used: `1`
- average_loop_iterations: `1.8`
- citation_coverage_before: `0.7`
- citation_coverage_after: `0.8`

## Policy

- diagnostic_runtime_bridge_only: `True`
- official_denominator_registry_changed: `False`
- production_index_mutation: `False`
- broad_indexing: `False`
- frozen_gold_training_rows: `0`
- frozen_gold_profile_selection: `False`
- tuned_text_section_boost_bm25_promotion_status: `diagnostic_only`
- pdf_file_lookup_semantics: `file_identity_only`
- ocr_idp_multimodal_denominator_role: `DIAGNOSTIC_ONLY`
