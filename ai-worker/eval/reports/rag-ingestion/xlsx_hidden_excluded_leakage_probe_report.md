# XLSX Hidden/Excluded Leakage Probe Report

- Generated at: `2026-05-12T14:01:08.150941Z`
- Status: `PASS`
- Scope: diagnostic-only; no retrieval, answer generation, vector write, registry update, or promotion.
- Probe target rows: `16`
- Normalized excluded rows: `14`
- Normalized hidden-negative rows: `3`
- Route/fallback hidden-excluded guard rows: `2`
- Surface leakage count: `0`
- Policy-excluded rows counted as retrieval failures: `False`

## Guardrails

- `official_denominator_registry_changed`: `false`
- `production_namespace_mutated`: `false`
- `production_vector_index_mutated`: `false`
- `production_vector_written`: `false`
- `candidate_artifact_mutated`: `false`
- `immutable_baseline_mutated`: `false`
- `diagnostic_only_row_promoted`: `false`
- `answer_generation_denominator_opened`: `false`
- `route_fallback_labels_official_metric`: `false`
- `pdf_content_and_file_identity_aggregated`: `false`
- `hidden_excluded_content_exposed`: `false`
- `hidden_xlsx_content_exposed`: `false`
- `query_surface_exposed`: `false`
- `candidate_surface_exposed`: `false`
- `answer_citation_debug_surface_exposed`: `false`
- `policy_excluded_rows_counted_as_retrieval_failures`: `false`

## Surface Coverage

| Surface | Files | Existing | Leakage | Status |
|---|---:|---:|---:|---|
| query | 2 | 2 | 0 | PASS |
| candidate | 1 | 1 | 0 | PASS |
| answer | 0 | 0 | 0 | NOT_OPENED |
| citation | 0 | 0 | 0 | NOT_OPENED |
| debug_public | 4 | 4 | 0 | PASS |
| official_denominator | 1 | 1 | 0 | PASS |

## Target Rows

| query_id | source | hidden_negative | reasons |
|---|---|---:|---|
| gq_xlsx_lookup_002 | normalized_excluded | False | must_contain_terms_not_in_bound_evidence, human_evidence_mismatch |
| gq_xlsx_hidden_policy_003 | normalized_excluded | True | invalid_or_empty_citation_locator, missing_sheet, missing_range, must_contain_terms_not_in_bound_evidence, human_policy_excluded |
| gq_xlsx_aggregation_003 | normalized_excluded | False | invalid_or_empty_citation_locator, missing_sheet, missing_range, must_contain_terms_not_in_bound_evidence, human_policy_excluded |
| gq_auto_013 | normalized_excluded | False | must_contain_terms_not_in_bound_evidence, human_evidence_mismatch |
| gq_auto_032 | normalized_excluded | False | must_contain_terms_not_in_bound_evidence, human_evidence_mismatch |
| gq_auto_033 | normalized_excluded | False | must_contain_terms_not_in_bound_evidence, human_evidence_mismatch |
| gq_auto_039 | normalized_excluded | False | must_contain_terms_not_in_bound_evidence, human_evidence_mismatch |
| gq_auto_041 | normalized_excluded | False | must_contain_terms_not_in_bound_evidence, human_evidence_mismatch |
| gq_auto_042 | normalized_excluded | False | must_contain_terms_not_in_bound_evidence, human_evidence_mismatch |
| gq_xlsx_formula_value_001 | normalized_excluded | False | invalid_or_empty_citation_locator, missing_sheet, missing_range, must_contain_terms_not_in_bound_evidence, human_policy_excluded |
| gq_xlsx_formula_value_002 | normalized_excluded | False | invalid_or_empty_citation_locator, missing_sheet, missing_range, must_contain_terms_not_in_bound_evidence, human_policy_excluded |
| gq_xlsx_formula_value_003 | normalized_excluded | False | invalid_or_empty_citation_locator, missing_sheet, missing_range, must_contain_terms_not_in_bound_evidence, human_policy_excluded |
| gq_xlsx_hidden_policy_001 | normalized_excluded | True | invalid_or_empty_citation_locator, missing_sheet, missing_range, missing_must_contain_terms, human_policy_excluded |
| gq_xlsx_hidden_policy_002 | normalized_excluded | True | invalid_or_empty_citation_locator, missing_sheet, missing_range, missing_must_contain_terms, human_policy_excluded |
| route_auto_xlsx_hidden_excluded_guard_001 | route_applied_hidden_guard | True | hidden_negative_or_excluded_row_guard |
| fallback_auto_xlsx_hidden_excluded_blocked_001 | fallback_applied_hidden_guard | True | hidden_negative_or_excluded_row_guard |

## Validation

- `ok`: `True`
- No validation errors.
