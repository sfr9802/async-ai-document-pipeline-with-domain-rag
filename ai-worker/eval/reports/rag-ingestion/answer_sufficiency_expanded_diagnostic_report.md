# Answer Sufficiency Expanded Diagnostic Report

- Status: `PASS`.
- Scope: lane-separated diagnostic evaluation only; no official answer denominator opened.
- Production index mutation: `false`; broad indexing: `false`; official denominator registry changed: `false`.
- TEXT profile: `tuned_text_section_boost_bm25` remains `diagnostic_only`.

## Counts

- total_evaluated: `185`
- initially_supported: `148`
- recovered_after_loop: `5`
- wrongly_supported_count: `0`
- unsupported_correctly_blocked_count: `32`
- diagnostic_only_evidence_blocked_count: `8`
- hidden_xlsx_surface_attempt_count: `3`
- pdf_file_lookup_content_mixing_attempt_count: `4`

## Lane Counts

- IDP_SHADOW: `2` cases (target `10-20`)
- MULTIMODAL_SHADOW: `1` cases (target `10-20`)
- OCR_SHADOW: `1` cases (target `10-20`)
- PDF_CONTENT: `40` cases (target `30-50`)
- PDF_FILE_LOOKUP: `28` cases (target `15-30`)
- TEXT: `75` cases (target `50-100`)
- XLSX: `38` cases (target `30-50`)

## Limitations

- IDP_SHADOW: selected 2; target was 10-20 and only existing artifacts were used.
- MULTIMODAL_SHADOW: selected 1; target was 10-20 and only existing artifacts were used.
- OCR_SHADOW: selected 1; target was 10-20 and only existing artifacts were used.

## Guardrails

- diagnostic_runtime_bridge_only: `True`
- official_answer_denominator_opened: `False`
- official_denominator_registry_changed: `False`
- production_index_mutation: `False`
- broad_indexing: `False`
- frozen_gold_training_rows: `0`
- frozen_gold_profile_selection: `False`
- tuned_text_section_boost_bm25_promotion_status: `diagnostic_only`
- pdf_file_lookup_semantics: `file_identity_only`
- pdf_file_lookup_success_claims: `content=False, page=False, bbox=False, table=False, row=False, column=False, value=False`
- hidden_xlsx_content_surface: `False`
- ocr_idp_multimodal_denominator_role: `DIAGNOSTIC_ONLY`
- native_pdf_text_outranks_ocr_fallback: `True`
- max_loop_iterations: `2`
