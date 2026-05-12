# Fallback Outcome Label Review Applied v1

- Generated at: `2026-05-12T13:09:47.715928Z`
- Status: `PASS`
- Scope: Korean memo labels normalized into diagnostic-only review columns.
- Source review pack: `ai-worker/eval/review/fallback_outcome_label_review_pack_v1.json`
- Original review pack modified: `false`
- Applied human review rows: `3`
- Codex diagnostic-only auto-classified rows unchanged: `4`
- Official metric input rows: `0`

## Applied Labels

| query_id | user memo | reviewed_primary_route | expected_evidence_lane | fallback_allowed | fallback_expected_route | fallback_outcome_label | wrong_route_label | final_action |
|---|---|---|---|---|---|---|---|---|
| fallback_review_xlsx_to_pdf_001 | 풀백하여 사용자에게 질문 재유도 | xlsx_business_structured | xlsx_structured_evidence | false | null | fallback_to_user_clarification | pdf_fallback_not_success | clarification_required |
| fallback_review_text_pdf_ambiguous_001 | 풀백하여 사용자에게 질문 재유도 | diagnostic_multi_route | none | false | null | fallback_to_user_clarification | ambiguous_requires_user_clarification | clarification_required |
| fallback_review_pdf_content_file_identity_lane_001 | OCR 및 파싱을 통해 키워드 추출 후 라우팅 | pdf_business_ocr_mm | pdf_content_evidence | true | pdf_business_ocr_mm | fallback_deferred_until_ocr_parse_keywords | no_cross_track_wrong_route_but_lane_separation_required | ocr_parse_keywords_required |

## Diagnostic Metrics

- `official_metric`: `false`
- `metric_namespace`: `reviewed_fallback_metrics_diagnostic`
- `applied_fallback_labels`: `3`
- `route_retrieval_fallback_success_count`: `0`
- `cross_track_fallback_success_count`: `0`
- `clarification_required_count`: `2`
- `pdf_scoped_deferred_ocr_parse_count`: `1`
- `clarification_required_rows_not_counted_as_fallback_success`: `true`
- `pdf_lane_transition_not_aggregated_as_success`: `true`

## Mapping Notes

- Korean memo decisions are treated as authoritative human review input for this phase.
- Exact production enum constants were not found for these labels; report-only label strings were used.
- Prefilled fallback routes from the original pack remain diagnostic hints and were overridden where the user memo required clarification or OCR/parsing first.
- Route/fallback metrics remain diagnostic-only.

## Guardrails

- `official_denominator_registry_path`: `ai-worker/eval/eval_queries/official_denominator_registry.json`
- `official_denominator_registry_changed`: `false`
- `official_denominator_opened_or_frozen`: `false`
- `production_namespace_mutated`: `false`
- `production_vector_index_mutated`: `false`
- `production_vector_written`: `false`
- `candidate_artifact_mutated`: `false`
- `immutable_baseline_mutated`: `false`
- `diagnostic_only_row_promoted`: `false`
- `pdf_content_and_file_identity_aggregated`: `false`
- `hidden_xlsx_content_exposed`: `false`
- `policy_excluded_rows_counted_as_retrieval_failures`: `false`
- `route_metrics_official`: `false`
- `fallback_metrics_official`: `false`
