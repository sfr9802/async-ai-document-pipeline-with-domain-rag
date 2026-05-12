# Fallback Outcome Label Review Pack v1

- Generated at: `2026-05-12T10:28:09.827647Z`
- Status: `PASS`
- Scope: diagnostic-only label preparation; this is not official route metric evidence.
- Source report: `ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.json`
- Human review rows: `3`
- Codex diagnostic-only auto-classified rows: `4`
- Guardrails: official denominator registry unchanged, production namespace/vector unchanged, PDF CONTENT and FILE identity lanes separated, XLSX hidden/excluded content not surfaced.

## Required Columns

`query_id`, `safe_query_text`, `source_type_hint`, `reviewed_primary_route`, `reviewed_candidate_routes`, `expected_evidence_lane`, `fallback_allowed`, `fallback_expected_route`, `fallback_outcome_label`, `wrong_route_label`, `denominator_scope`, `reviewer`, `reviewed_time`, `notes`

## Human Review Rows

| query_id | safe_query_text | source_type_hint | expected_evidence_lane | fallback_expected_route | notes |
|---|---|---|---|---|---|
| fallback_review_xlsx_to_pdf_001 | 합계? | xlsx_business_structured_short_query | xlsx_structured_evidence | pdf_business_ocr_mm | Human must label whether this bounded fallback was allowed and whether outcome is success, blocked, or wrong route. | 풀백하여 사용자에게 질문 재유도.
| fallback_review_text_pdf_ambiguous_001 | 본문 내용을 찾아줘 | text_pdf_ambiguous | none | 풀백하여 사용자에게 질문 재유도. | Human must decide the route label and whether fallback should be allowed for TEXT/PDF ambiguity. |
| fallback_review_pdf_content_file_identity_lane_001 | PDF에서 이 문서와 본문 근거를 확인해줘 | pdf_content_vs_file_identity | pdf_content_evidence | pdf_business_ocr_mm | Human must decide whether fallback across PDF CONTENT and FILE identity lanes is allowed; lanes stay separate. | OCR 및 파싱을 통해 키워드 추출 후 라우팅

## Codex Diagnostic-Only Auto-Classified Rows

| query_id | safe_query_text | source_type_hint | expected_evidence_lane | fallback_outcome_label | codex_classification |
|---|---|---|---|---|---|
| fallback_auto_pdf_generic_filename_identity_blocked_001 | 계약서 PDF 파일 찾아줘 | pdf_file_identity_guard | pdf_file_identity | fallback_blocked_by_policy | stable_identity_required_blocks_fallback |
| fallback_auto_max_attempts_guard_001 | second fallback attempt guard | bounded_fallback_guard | none | fallback_blocked_max_attempts | maximum_one_fallback_attempt_enforced |
| fallback_auto_unscoped_retrieval_blocked_001 | unscoped fallback guard | allow_unscoped_false_guard | none | fallback_blocked_unscoped | unscoped_fallback_blocked |
| fallback_auto_xlsx_hidden_excluded_blocked_001 | [redacted xlsx excluded-row fallback guard] | xlsx_hidden_or_excluded_guard | xlsx_structured_evidence | fallback_blocked_by_policy | hidden_or_excluded_xlsx_fallback_blocked |

## Metric Policy

- `official_metric_input_rows`: `0`.
- Route/fallback metrics remain diagnostic-only until this pack is reviewed.
- Prefilled lanes and routes are diagnostic hints, not gold labels.

## Guardrails

- `official_denominator_registry_path`: `"ai-worker/eval/eval_queries/official_denominator_registry.json"`
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
- `allow_unscoped`: `false`
