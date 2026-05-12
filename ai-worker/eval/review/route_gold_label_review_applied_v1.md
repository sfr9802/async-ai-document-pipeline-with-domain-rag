# Route Gold Label Review Applied v1

- Generated at: `2026-05-12T13:09:47.715928Z`
- Status: `PASS`
- Scope: Korean memo labels normalized into diagnostic-only review columns.
- Source review pack: `ai-worker/eval/review/route_gold_label_review_pack_v1.json`
- Original review pack modified: `false`
- Applied human review rows: `5`
- Codex diagnostic-only auto-classified rows unchanged: `4`
- Official metric input rows: `0`

## Applied Labels

| query_id | user memo | reviewed_primary_route | expected_evidence_lane | fallback_allowed | fallback_expected_route | fallback_outcome_label | wrong_route_label | final_action |
|---|---|---|---|---|---|---|---|---|
| route_review_text_namuwiki_animation_001 | 올바른 라우트 | text_namuwiki_animation | text_content | false | null | fallback_not_applicable | correct_route | direct_route_confirmed |
| route_review_xlsx_business_structured_001 | 정책상 사용자에게 재질문 유도 | xlsx_business_structured | xlsx_structured_evidence | false | null | fallback_to_user_clarification | correct_track_but_query_under_specified | clarification_required |
| route_review_pdf_content_evidence_001 | PDF 본문 근거 검색 맞음 | pdf_business_ocr_mm | pdf_content_evidence | false | null | fallback_not_applicable | correct_route | direct_route_confirmed |
| route_review_pdf_file_identity_001 | PDF 언급이 있으므로 PDF 파일 색인 라우트 | pdf_business_ocr_mm | pdf_file_identity | false | null | fallback_not_applicable | correct_route | stable_file_identity_route_confirmed |
| route_review_ambiguous_multi_route_001 | OCR 및 파싱을 통해 키워드 추출 후 라우팅 | diagnostic_multi_route | none | false | null | fallback_deferred_until_source_context_extraction | ambiguous_requires_source_context | source_context_extraction_required |

## Diagnostic Metrics

- `official_metric`: `false`
- `metric_namespace`: `reviewed_route_metrics_diagnostic`
- `applied_route_labels`: `5`
- `correct_route_count`: `3`
- `clarification_required_count`: `1`
- `source_context_required_count`: `1`
- `direct_single_route_success_count`: `3`
- `deferred_rows_not_counted_as_direct_success`: `true`

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
