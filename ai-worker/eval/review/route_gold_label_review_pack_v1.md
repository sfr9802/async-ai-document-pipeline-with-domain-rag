# Route Gold Label Review Pack v1

- Generated at: `2026-05-12T10:28:09.827647Z`
- Status: `PASS`
- Scope: diagnostic-only label preparation; this is not official route metric evidence.
- Source report: `ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.json`
- Human review rows: `5`
- Codex diagnostic-only auto-classified rows: `4`
- Guardrails: official denominator registry unchanged, production namespace/vector unchanged, PDF CONTENT and FILE identity lanes separated, XLSX hidden/excluded content not surfaced.

## Required Columns

`query_id`, `safe_query_text`, `source_type_hint`, `reviewed_primary_route`, `reviewed_candidate_routes`, `expected_evidence_lane`, `fallback_allowed`, `fallback_expected_route`, `fallback_outcome_label`, `wrong_route_label`, `denominator_scope`, `reviewer`, `reviewed_time`, `notes`

## Human Review Rows

| query_id | safe_query_text | source_type_hint | expected_evidence_lane | fallback_expected_route | notes |
|---|---|---|---|---|---|
| route_review_text_namuwiki_animation_001 | 애니 작품 내용과 등장인물 설명을 찾아줘 | text_namuwiki_animation | text_content | 올바른 라우트 | Human must confirm primary route and expected TEXT/Namu evidence lane before route metrics. |
| route_review_xlsx_business_structured_001 | 합계? | xlsx_business_structured_short_query | xlsx_structured_evidence | 정책상 사용자에게 재질문 유도 | Short XLSX-shaped query needs human route label before routing accuracy can be computed. |
| route_review_pdf_content_evidence_001 | PDF 본문 근거를 찾아줘 | pdf_content_evidence | pdf_content_evidence | PDF 본문 근거 검색 맞음 | Human must confirm this belongs to PDF CONTENT evidence, not FILE/document identity. |
| route_review_pdf_file_identity_001 | 안정적인 문서 식별자가 있는 PDF 파일을 찾아줘 | pdf_file_identity | pdf_file_identity | PDF 언급이 있으므로 PDF 파일 색인 라우트  | Human must confirm stable document identity policy; generic filename-only identity is not allowed. |
| route_review_ambiguous_multi_route_001 | 이 자료에서 확인해줘 | ambiguous_multi_route | none | OCR 및 파싱을 통해 키워드 추출 후 라우팅 | Ambiguous query needs reviewed route and evidence-lane label before multi-route metrics. |

## Codex Diagnostic-Only Auto-Classified Rows

| query_id | safe_query_text | source_type_hint | expected_evidence_lane | fallback_outcome_label | codex_classification |
|---|---|---|---|---|---|
| route_auto_pdf_generic_filename_identity_blocked_001 | 계약서 PDF 파일 찾아줘 | pdf_file_identity_guard | pdf_file_identity | fallback_blocked_by_policy | generic_filename_only_identity_blocked |
| route_auto_xlsx_hidden_excluded_guard_001 | [redacted xlsx excluded-row guard probe] | xlsx_hidden_or_excluded_guard | xlsx_structured_evidence | fallback_blocked_by_policy | xlsx_hidden_or_excluded_row_blocked |
| route_auto_text_unresolved_carry_forward_guard_001 | TEXT/Namu unresolved carry-forward guard | text_namuwiki_unresolved_guard | text_content | fallback_blocked_by_policy | text_namu_unresolved_rows_excluded |
| route_auto_invalid_llm_json_fail_closed_001 | invalid LLM adjudicator output guard | llm_adjudicator_validation_guard | none | fallback_blocked_invalid_adjudicator | invalid_llm_json_fails_closed |

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
