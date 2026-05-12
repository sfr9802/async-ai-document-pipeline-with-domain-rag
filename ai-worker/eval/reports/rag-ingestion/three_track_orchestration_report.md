# 3-track RAG Orchestration Report

Generated: 2026-05-11 KST

## Status

`implemented_diagnostic_only`

This change defines the query-time orchestration contract for three separated
RAG tracks:

| Track | Scope |
|---|---|
| `text_namuwiki_animation` | Namuwiki animation-domain TEXT RAG, not general business text RAG |
| `xlsx_business_structured` | Business spreadsheet structured RAG with sheet/table/row/column context |
| `pdf_business_ocr_mm` | Business OCR/MM document RAG with page/bbox/region context |

The system must not interpret these as one integrated vector quality pool.
Namespace/index scope, retrieval contracts, and eval denominators remain
track-specific.

## Changed files

- `.gitignore`
- `ai-worker/app/capabilities/rag_orchestrator/graph.py`
- `ai-worker/app/capabilities/rag_orchestrator/state.py`
- `ai-worker/app/capabilities/rag_orchestrator/capability.py`
- `ai-worker/app/capabilities/rag_orchestrator/tools.py`
- `ai-worker/app/capabilities/rag_orchestrator/vector_tools.py`
- `ai-worker/app/capabilities/rag_orchestrator/xlsx_tools.py`
- `ai-worker/app/capabilities/rag_orchestrator/pdf_tools.py`
- `ai-worker/eval/harness/rag_ingestion_retrieval_eval.py`
- `ai-worker/scripts/rag_query_intent_routing_matrix.py`
- `ai-worker/scripts/rag_xlsx_retrieval_performance_diagnostic.py`
- `ai-worker/tests/test_rag_query_orchestrator_graph.py`
- `ai-worker/tests/test_rag_query_orchestrator_capability.py`
- `ai-worker/tests/test_rag_query_orchestrator_vector_tools.py`
- `ai-worker/tests/test_retrieval_eval_harness.py`
- `ai-worker/tests/test_rag_query_intent_routing_matrix.py`
- `docs/eval/denominator_policy.md`
- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion/xlsx-retrieval/README.md`
- `docs/track_b_text_retrieval_e2e/README.md`
- `docs/track-c-pdf-embedding-preparation/README.md`
- `ai-worker/eval/reports/rag-ingestion/README.md`
- `ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.md`

## Route schema

The route decision payload is now carried in orchestrator state, capability
output, and trace:

- `route`
- `routes`
- `route_confidence`
- `reason`
- `required_evidence_type`
- `allow_fallback`
- `fallback_routes`
- `multi_route`
- `deterministic_hints`
- `metadata_guards`
- `llm_decision_used`
- `post_retrieval_validation`

Route selection uses deterministic query hints plus policy/source metadata
guards. Optional LLM suggestions can only narrow inside the guarded route set;
they cannot relax source type, parser, or namespace constraints. XLSX/PDF
questions are blocked from silently falling into `text_namuwiki_animation` when
policy metadata indicates spreadsheet or PDF input.

## Namespace and index scope policy

- `text_namuwiki_animation`: TEXT source type, namu-v4 domain rows, separate
  denominator from legacy B-app smoke.
- `xlsx_business_structured`: SPREADSHEET source type, XLSX parser/version
  scope, hidden-safe spreadsheet evidence contract.
- `pdf_business_ocr_mm`: PDF source type, PDF parser/version scope, page and
  layout metadata contract.

The fake graph and vector wrappers still use post-filtering in the POC path.
Production readiness still requires a safe retrieval API that enforces tenant,
ACL, source type, parser version, index version, and embedding status before or
inside vector ranking.

## XLSX evidence contract

XLSX candidate retrieval and context assembly are separated. The assembled
context includes:

- `file`
- `sheet`
- `table_id`
- `table_range`
- `matched_cells`
- `header_rows`
- `target_rows`
- `target_columns`
- `row_values`
- `column_headers`
- `nearby_rows`
- `merged_cell_context`
- `table_title_candidate`
- `score`

Context assembly policy: same row, header row, target column header, nearby
rows, merged parent cells, sheet name, and table title candidate. Flatten-only
evidence is diagnostic fallback and receives
`xlsx_context_diagnostic_only_missing_structure`.

## PDF evidence contract

PDF candidate retrieval and context assembly are separated. The assembled
context includes:

- `file`
- `page`
- `region_type`
- `bbox`
- `matched_text`
- `section_heading`
- `table_caption_footnote`
- `nearby_paragraphs`
- `OCR_confidence`
- `score`

Context assembly policy: matched block, page number, bbox, section heading,
table/caption/footnote, nearby paragraph, and OCR confidence if available.
Missing OCR/MM layout metadata is diagnostic-only and receives
`pdf_context_diagnostic_only_missing_layout`.

## Eval denominator policy

The retrieval eval harness reports route/xlsx/pdf metric families separately.
Cross-track averages must not be interpreted as quality:

- route: `routing_accuracy`, `wrong_route_rate`, `fallback_success_rate`,
  `multi_route_success_rate`, `low_confidence_route_count`
- xlsx: `target_cell_hit`, `target_row_hit`, `header_included`,
  `target_column_included`, `surrounding_context_included`,
  `sheet_resolution_accuracy`
- pdf: `page_hit`, `region_hit`, `bbox_available`,
  `table_or_caption_included`, `nearby_paragraph_included`,
  `OCR_confidence_available`

Route metrics remain diagnostic-only until route gold labels and fallback
outcomes are human-reviewed. Gold evidence creation, evidence judgment,
answerability labels, and final gold policy remain user-owned.

## Verification

```text
python -m py_compile app/capabilities/rag_orchestrator/state.py app/capabilities/rag_orchestrator/graph.py app/capabilities/rag_orchestrator/xlsx_tools.py app/capabilities/rag_orchestrator/pdf_tools.py app/capabilities/rag_orchestrator/tools.py app/capabilities/rag_orchestrator/vector_tools.py app/capabilities/rag_orchestrator/capability.py eval/harness/rag_ingestion_retrieval_eval.py scripts/rag_query_intent_routing_matrix.py scripts/rag_xlsx_retrieval_performance_diagnostic.py
```

Result: passed.

```text
python -m pytest -q -p no:cacheprovider tests/test_rag_query_orchestrator_graph.py tests/test_rag_query_orchestrator_capability.py tests/test_rag_query_orchestrator_vector_tools.py tests/test_retrieval_eval_harness.py tests/test_rag_query_intent_routing_matrix.py
```

Result: `59 passed, 8 warnings`.

## Remaining risks

- Production vector retrieval still uses bounded overfetch plus post-filtering in
  this POC wrapper; pre-ranking fail-closed filters are still required.
- Route metrics are diagnostic-only until route gold labels exist.
- XLSX/PDF answer-generation denominators remain `0` until human-reviewed
  expected answer/evidence and answerability labels exist.
- PDF layout/OCR confidence coverage depends on parser metadata availability;
  missing layout stays diagnostic-only.

## 2026-05-12 Diagnostic Routing Update

Status: `implemented_diagnostic_only`; machine-readable report:
`ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.json`.

Implemented/verified behavior:

- Query-time route diagnostics now expose `query_id`, safe query text, primary
  route, candidate routes, route scores, selected route reason, deterministic
  hints, LLM adjudicator call status/output, validation status, policy guards,
  blocked flags, evidence lane, fallback plan/attempts, final diagnostic status,
  denominator scope, and no-mutation flags.
- Rule-based route scoring runs before the LLM. The LLM adjudicator is called
  only for ambiguous or hard queries, returns strict JSON, and fails closed on
  invalid/unsafe output.
- Deterministic hard guards run before the LLM and cannot be overridden by it:
  hidden XLSX, generic PDF filename identity, policy-excluded PDF rows,
  TEXT/Namu unresolved rows, denominator mutation, production vector writes,
  and diagnostic-only promotion remain code-owned constraints.
- Ambiguous source intent uses `diagnostic_multi_route` or a bounded fallback
  path, not official route success.
- The bounded fallback loop is capped at one scoped fallback route attempt:
  `routed -> retrieved -> evidence_sufficiency -> optional fallback_attempted
  -> final_diagnostic_only`.
- `text_namuwiki_animation`, `xlsx_business_structured`, and
  `pdf_business_ocr_mm` remain separate tracks with separate denominator scopes.
- PDF content-evidence and FILE/document identity lanes remain separate.
  Generic filename-only PDF identity is rejected with
  `stable_identity_required`.
- XLSX hidden/excluded candidates are rejected before answer/citation surfacing
  with `hidden_negative_or_excluded_row_guard`.
- SearchUnit indexing metadata now preserves `bm25_text` separately and records
  embedding text as presence/hash metadata without merging it into display,
  citation, or debug text.
- Capability output now carries `loop_states`, `fallback_attempts`, and
  `evidence_sufficiency`, and `sourceMetadata` reaches route guards and
  diagnostics.

Gold/policy state preserved:

- XLSX draft `gold_v0.1` retrieval/evidence candidates remain `23`; pending
  evidence rows `gq_xlsx_date_number_format_003` and
  `gq_xlsx_aggregation_001` remain excluded.
- XLSX answer-generation denominator remains `0`.
- PDF excluded rows `6` plus stable-identity-required rows `3` remain excluded
  and are not retrieval failures.
- TEXT/Namu unresolved carry-forward rows `23` remain excluded from
  `gold_v0.1`; resolution attempted remains `false`.

Route label preparation:

- Route gold label review pack and applied diagnostic label artifact now exist.
- Fallback outcome label review pack and applied diagnostic label artifact now
  exist.
- Therefore do not compute official routing accuracy, wrong-route rate,
  fallback success, or multi-route success.
- Needed future label columns: `query_id`, reviewed primary route, reviewed
  candidate routes, expected evidence lane, fallback allowed, fallback expected
  route, fallback outcome label, wrong-route label, reviewer, reviewed time, and
  notes.

## 2026-05-12 Route/Fallback Label Review Pack v1

Status: `generated_diagnostic_only_pending_human_review`.

Generated review packs:

- `ai-worker/eval/review/route_gold_label_review_pack_v1.md` / `.json`
- `ai-worker/eval/review/fallback_outcome_label_review_pack_v1.md` / `.json`

Counts:

- Human review rows: `8` total (`5` route, `3` fallback).
- Codex diagnostic-only auto-classified rows: `8` total (`4` route, `4`
  fallback).
- Official metric input rows: `0`.

Human-owned label fields are separated in each pack:
`reviewed_primary_route`, `reviewed_candidate_routes`,
`expected_evidence_lane`, `fallback_allowed`, `fallback_expected_route`,
`fallback_outcome_label`, `wrong_route_label`, `reviewer`, `reviewed_time`, and
`notes`.

Codex auto-classified only mechanical diagnostic guard outcomes:
invalid/missing LLM JSON fail-closed, hard policy route blocks,
hidden/excluded XLSX guards, generic PDF filename-only identity guards,
fallback attempts beyond one, and unscoped fallback blocks. These rows remain
`official_metric_input=false`.

Prefilled route/lane fields in the review packs are diagnostic hints, not gold
labels. Route/fallback metrics remain diagnostic-only until the packs are
reviewed and applied.

Guardrails held for pack generation:

- `official_denominator_registry.json` changed: `false`.
- Official denominator opened/frozen: `false`.
- Production namespace mutated: `false`.
- Production vector index mutated/written: `false`.
- Candidate artifact or immutable baseline mutated: `false`.
- Diagnostic-only row promoted: `false`.
- PDF content evidence and FILE/document identity lanes aggregated: `false`.
- XLSX hidden/excluded content exposed: `false`.
- Policy-excluded rows counted as retrieval failures: `false`.

## 2026-05-12 Route/Fallback Label Review Applied v1

Status: `applied_diagnostic_only`.

Applied artifacts:

- `ai-worker/eval/review/route_gold_label_review_applied_v1.md` / `.json`
- `ai-worker/eval/review/fallback_outcome_label_review_applied_v1.md` /
  `.json`

The user provided Korean memo-style decisions. Codex treated those memo labels
as authoritative human review input and normalized them into the required
schema columns. Original review packs were left unchanged because the applied
artifacts preserve the source pack and record normalized user decisions
separately.

Counts:

- Route human rows applied: `5`.
- Fallback human rows applied: `3`.
- Codex diagnostic-only auto-classified rows unchanged: `8`.
- Official metric input rows: `0`.
- Clarification-required rows: `3`.
- Deferred OCR/parsing/source-context rows: `2`.

User memo normalization:

| query_id | user memo | normalized result |
|---|---|---|
| `route_review_text_namuwiki_animation_001` | `올바른 라우트` | `text_namuwiki_animation`, `text_content`, `correct_route`, no fallback |
| `route_review_xlsx_business_structured_001` | `정책상 사용자에게 재질문 유도` | `xlsx_business_structured`, `xlsx_structured_evidence`, `fallback_to_user_clarification`, `correct_track_but_query_under_specified` |
| `route_review_pdf_content_evidence_001` | `PDF 본문 근거 검색 맞음` | `pdf_business_ocr_mm`, `pdf_content_evidence`, `correct_route`, not FILE identity |
| `route_review_pdf_file_identity_001` | `PDF 언급이 있으므로 PDF 파일 색인 라우트` | `pdf_business_ocr_mm`, `pdf_file_identity`, stable identity required, generic filename-only still blocked |
| `route_review_ambiguous_multi_route_001` | `OCR 및 파싱을 통해 키워드 추출 후 라우팅` | `diagnostic_multi_route`, `fallback_deferred_until_source_context_extraction`, not direct single-route success |
| `fallback_review_xlsx_to_pdf_001` | `풀백하여 사용자에게 질문 재유도` | clarification required; original `pdf_business_ocr_mm` fallback hint overridden and not counted as success |
| `fallback_review_text_pdf_ambiguous_001` | `풀백하여 사용자에게 질문 재유도` | clarification required; not TEXT fallback success and not PDF fallback success |
| `fallback_review_pdf_content_file_identity_lane_001` | `OCR 및 파싱을 통해 키워드 추출 후 라우팅` | scoped `pdf_business_ocr_mm` handling after OCR/parsing; PDF CONTENT and FILE identity lanes remain separate |

No exact existing enum constants were found for these memo labels. The applied
artifacts therefore use report-only label strings such as
`fallback_to_user_clarification`,
`fallback_deferred_until_source_context_extraction`, and
`fallback_deferred_until_ocr_parse_keywords`; production routing behavior was
not changed.

Diagnostic metric handling:

- `reviewed_route_metrics_diagnostic`: `5` applied route labels, `3` correct
  route confirmations, `1` clarification-required route, and `1`
  source-context-required route.
- `reviewed_fallback_metrics_diagnostic`: `3` applied fallback labels, `0`
  route retrieval fallback successes, `0` cross-track fallback successes, `2`
  clarification-required rows, and `1` PDF-scoped deferred OCR/parsing row.
- Clarification-required rows are not counted as retrieval fallback success.
- Deferred OCR/parsing rows are not counted as direct route success.
- PDF content/file identity lane transitions are not aggregated into one
  success metric.

Guardrails held for applied labels:

- `official_denominator_registry.json` changed: `false`.
- Official denominator opened/frozen: `false`.
- Production namespace mutated: `false`.
- Production vector index mutated/written: `false`.
- Candidate artifact or immutable baseline mutated: `false`.
- Diagnostic-only row promoted: `false`.
- PDF content evidence and FILE/document identity lanes aggregated: `false`.
- XLSX hidden/excluded content exposed: `false`.
- Policy-excluded rows counted as retrieval failures: `false`.

## 2026-05-12 XLSX Hidden/Excluded Leakage Probe

Status: `PASS`.

Generated artifacts:

- `ai-worker/eval/reports/rag-ingestion/xlsx_hidden_excluded_leakage_probe_report.md`
  / `.json`

Scope:

- Diagnostic-only surface scan before any XLSX answer-generation or promotion
  lane.
- No retrieval run, answer-generation run, vector write, production namespace
  mutation, candidate artifact mutation, immutable baseline mutation, or
  official denominator registry update.

Counts:

- Normalized XLSX excluded rows probed: `14`.
- Normalized hidden-negative rows probed: `3`.
- Route/fallback hidden-excluded guard rows probed: `2`.
- Total probe target rows: `16`.
- Surface leakage count: `0`.

Surface result:

- Query surfaces: `PASS`.
- Candidate surface: `PASS`.
- Debug/public surfaces: `PASS`.
- Official denominator surface: `PASS`.
- Answer and citation surfaces: `NOT_OPENED`.

Guardrails held:

- `official_denominator_registry.json` changed: `false`.
- Official denominator opened/frozen: `false`.
- Production namespace/vector/index mutated or written: `false`.
- Candidate artifact or immutable baseline mutated: `false`.
- XLSX hidden/excluded content exposed: `false`.
- Policy-excluded rows counted as retrieval failures: `false`.
- Route/fallback applied labels remain diagnostic-only.
- PDF content evidence and FILE/document identity lanes remain separate.

## 2026-05-12 XLSX Strict Silver Generation

Status: `COMPLETED_DIAGNOSTIC_ONLY`.

Generated artifacts:

- `ai-worker/eval/reports/rag-ingestion/xlsx_strict_silver_generation_report.md`
  / `.json`
- External runtime manifest:
  `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\xlsx_strict_silver_generation\xlsx_strict_silver_retrieval_evidence_manifest.jsonl`

Scope:

- XLSX retrieval/evidence silver only through the strict pre-silver gate and
  current XLSX retrieval wrapper.
- No XLSX answer-generation, production promotion, denominator registry
  mutation, production namespace/vector/index mutation, candidate artifact
  mutation, or immutable baseline mutation.
- No repo-local canonical silver artifact was created because the repo does not
  define a dedicated XLSX strict silver artifact path; the compact report records
  the external manifest identity.
- Repo-local full-manifest writes are blocked by
  `assert_external_silver_output_path`; `repo_local_silver_manifest_written`
  remains `false`.

Counts and metrics:

- Input denominator rows: `23`.
- Generated silver rows: `23`.
- Pending evidence rows excluded: `2`
  (`gq_xlsx_date_number_format_003`,
  `gq_xlsx_aggregation_001`).
- Normalized excluded rows excluded: `14`.
- Normalized hidden-negative rows excluded: `3`.
- Diagnostic-only fallback rows: `0`.
- Hit@10 `1.0`, MRR@10 `0.942`, XLSX citation location accuracy `1.0`.
- Strict silver metadata completeness: target cell, target row, header, target
  column, surrounding context, sheet resolution, and citation locator
  completeness are all `1.0`.

Guardrails held:

- Hidden/excluded leakage result: `PASS`; surface leakage count `0`.
- Answer/citation surfaces remain `NOT_OPENED`.
- Policy-excluded rows counted as retrieval failures: `false`.
- Route/fallback applied labels remain diagnostic-only.
- PDF content evidence and FILE/document identity lanes remain separate.
- No flattened-only evidence was promoted as strict structured evidence.
- Full manifest emission is skipped when guardrail validation fails.

Verification:

```text
python -m py_compile app/capabilities/rag_orchestrator/state.py app/capabilities/rag_orchestrator/graph.py app/capabilities/rag_orchestrator/citation_verify.py app/capabilities/rag_orchestrator/capability.py app/capabilities/rag_orchestrator/vector_tools.py app/capabilities/rag_orchestrator/xlsx_tools.py app/capabilities/rag_orchestrator/pdf_tools.py eval/harness/rag_ingestion_retrieval_eval.py scripts/rag_query_intent_routing_matrix.py scripts/rag_gold_policy_applied_decisions.py
```

Result: passed.

```text
python -m pytest -q -p no:cacheprovider tests/test_rag_query_orchestrator_evidence.py tests/test_rag_query_orchestrator_graph.py tests/test_rag_query_orchestrator_capability.py tests/test_rag_query_orchestrator_vector_tools.py tests/test_rag_query_orchestrator_citation_verify.py tests/test_search_unit_indexing.py tests/test_golden_retrieval_eval.py tests/test_retrieval_eval_harness.py tests/test_rag_xlsx_answer_context_assembly.py tests/test_rag_xlsx_content_drop_trace.py tests/test_rag_answer_recovery_report_artifact_compaction.py tests/test_rag_reviewed_gold_policy_normalization.py tests/test_rag_gold_policy_resolution_packet.py tests/test_rag_gold_policy_decision_draft.py tests/test_rag_gold_policy_user_review_sheet.py tests/test_rag_gold_policy_user_approved_resolutions.py tests/test_rag_gold_policy_applied_decisions.py tests/test_rag_query_intent_routing_matrix.py
```

Result: `158 passed, 8 warnings`.

```text
mvn -q -Dtest=SearchUnitIndexingServiceTest test
```

Result: passed with Mockito/ByteBuddy dynamic-agent warnings only.

```text
git diff --quiet -- ai-worker/eval/eval_queries/official_denominator_registry.json
```

Result: unchanged.

Review pack verification:

```text
python -m py_compile scripts/route_label_review_packs.py
```

Result: passed.

Applied label verification:

```text
python -m py_compile scripts/route_label_review_applied.py
```

Result: passed.

```text
python -m pytest -q -p no:cacheprovider tests/test_route_label_review_applied.py tests/test_route_label_review_packs.py tests/test_rag_query_orchestrator_graph.py tests/test_rag_query_orchestrator_capability.py tests/test_retrieval_eval_harness.py
```

Result: passed.

```text
python -m json.tool ai-worker/eval/review/route_gold_label_review_applied_v1.json
python -m json.tool ai-worker/eval/review/fallback_outcome_label_review_applied_v1.json
python -m json.tool ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.json
git diff --check
git diff --quiet -- ai-worker/eval/eval_queries/official_denominator_registry.json
```

Result: passed.

```text
python -m pytest -q -p no:cacheprovider tests/test_route_label_review_packs.py tests/test_rag_query_orchestrator_graph.py tests/test_rag_query_orchestrator_capability.py
```

Result: passed.

```text
python -m json.tool ai-worker/eval/review/route_gold_label_review_pack_v1.json
python -m json.tool ai-worker/eval/review/fallback_outcome_label_review_pack_v1.json
python -m json.tool ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.json
git diff --check
git diff --quiet -- ai-worker/eval/eval_queries/official_denominator_registry.json
```

Result: passed.

XLSX hidden/excluded leakage probe verification:

```text
python -m py_compile scripts/rag_xlsx_hidden_excluded_leakage_probe.py scripts/rag_xlsx_retrieval_performance_diagnostic.py scripts/rag_xlsx_human_review_gold_normalizer.py scripts/route_label_review_applied.py
```

Result: passed.

```text
python -m pytest -q -p no:cacheprovider tests/test_rag_xlsx_hidden_excluded_leakage_probe.py tests/test_rag_xlsx_track_a_scripts.py tests/test_route_label_review_applied.py
```

Result: `26 passed, 1 warning`.

```text
python -m json.tool ai-worker/eval/reports/rag-ingestion/xlsx_hidden_excluded_leakage_probe_report.json
python -m json.tool ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.json
git diff --quiet -- ai-worker/eval/eval_queries/official_denominator_registry.json
```

Result: passed.

## 2026-05-13 PDF Strict Silver Diagnostic Slice

Status: `COMPLETED_DIAGNOSTIC_ONLY`.

Generated artifacts:

- `ai-worker/eval/reports/rag-ingestion/pdf_strict_silver_generation_report.md`
  / `.json`
- External runtime manifest:
  `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\pdf_strict_silver_generation\pdf_strict_silver_retrieval_evidence_manifest.jsonl`

Scope:

- PDF retrieval/evidence diagnostic silver only for `pdf_business_ocr_mm`.
- PDF answer generation, route/fallback official metrics, official denominator
  registry mutation, production namespace/vector/index mutation, candidate
  artifact mutation, and immutable baseline mutation remain closed.
- PDF CONTENT evidence and FILE/document identity lanes remain separate. Generic
  filename-only identity remains blocked with `stable_identity_required`.
- No repo-local canonical PDF strict silver manifest exists, so the full
  manifest is external-only and repo output is limited to the compact report.
- Repo-local full-manifest writes are blocked by
  `assert_external_pdf_silver_output_path`.

Counts and metrics:

- Input denominator rows: `7`.
- Generated strict silver rows: `0`.
- Diagnostic-only fallback rows: `7`.
- Policy-excluded rows: `6`.
- Stable-identity-required rows excluded: `3`.
- Pending/deferred OCR or parsing rows: `2`.
- PDF answer-generation denominator: `0`.
- `bbox_available`: `0.571`.
- `table_or_caption_included`: `0.0`.
- `nearby_paragraph_included`: `0.0`.
- `OCR_confidence_available`: `0.0`.
- Citation locator completeness: `0.0`.
- Metadata key-presence completeness: `1.0`.
- Metadata non-empty/value completeness: `0.473`.
- `page_hit` and `region_hit` are `null` because this strict slice did not run
  live retrieval; it validated pre-silver evidence completeness only.

Strict outcome:

- Current active PDF artifacts identify the 7 current-policy positive controls,
  but they do not expose source search unit id/rank, parser/source metadata,
  OCR confidence, or nearby paragraph context needed for strict silver
  promotion.
- All 7 input denominator rows therefore remain diagnostic-only with
  `pdf_context_diagnostic_only_missing_layout`; no diagnostic-only row was
  promoted.
- Flattened-only evidence is rejected as strict structured/layout evidence.

Guardrails held:

- Answer/citation generation surfaces remain `NOT_OPENED`.
- Promotion evidence created: `false`.
- Policy-excluded rows and stable-identity-required rows are not counted as
  retrieval failures.
- Route/fallback labels remain diagnostic-only and are not official metrics.
- Production namespace/vector/index, candidate artifacts, immutable baselines,
  and `official_denominator_registry.json` were not mutated.
- PDF content evidence and FILE/document identity lanes were not aggregated.

Verification:

```text
python -m py_compile ai-worker/scripts/rag_pdf_strict_silver_generation.py ai-worker/app/capabilities/rag_orchestrator/pdf_tools.py ai-worker/app/capabilities/rag_orchestrator/graph.py ai-worker/app/capabilities/rag_orchestrator/state.py ai-worker/app/capabilities/rag_orchestrator/capability.py ai-worker/app/capabilities/rag_orchestrator/vector_tools.py ai-worker/eval/harness/rag_ingestion_retrieval_eval.py ai-worker/scripts/route_label_review_applied.py
```

Result: passed.

```text
python -m pytest -q -p no:cacheprovider ai-worker/tests/test_rag_pdf_strict_silver_generation.py ai-worker/tests/test_rag_pdf_gold_policy_review.py ai-worker/tests/test_rag_pdf_file_lookup_companion_pack.py ai-worker/tests/test_rag_file_content_lane_readiness.py ai-worker/tests/test_route_label_review_applied.py ai-worker/tests/test_rag_gold_policy_applied_decisions.py ai-worker/tests/test_retrieval_eval_harness.py ai-worker/tests/test_rag_query_orchestrator_graph.py
```

Result: `73 passed, 5 skipped, 7 warnings`.

```text
python -m json.tool ai-worker/eval/reports/rag-ingestion/pdf_strict_silver_generation_report.json
python -m json.tool ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.json
git diff --check
git diff --quiet -- ai-worker/eval/eval_queries/official_denominator_registry.json
```

Result: passed; `git diff --check` emitted line-ending warnings only.

Guardrail confirmation:

- `official_denominator_registry.json` changed: `false`.
- Official denominator opened/frozen: `false`.
- Production namespace mutated: `false`.
- Production vector index mutated: `false`.
- Production vector written: `false`.
- Diagnostic-only row promoted: `false`.
- PDF content/file identity lanes aggregated: `false`.
- Hidden XLSX exposed: `false`.
- Policy-excluded rows counted as retrieval failures: `false`.

Remaining blockers:

- Route/fallback labels are applied only in diagnostic artifacts; official
  route/fallback metric promotion remains blocked by denominator policy.
- Production vector retrieval still needs pre-ranking fail-closed tenant, ACL,
  source type, parser version, index version, and embedding-status enforcement.
- PDF strict silver promotion remains blocked until active artifacts provide
  source search unit id/rank, parser/source metadata, nearby paragraph context,
  OCR confidence when relevant, and citation locator completeness.
- PDF table-ish rows still require parser/table or policy review before strict
  table/caption evidence can be promoted.
- TEXT/Namu answer/citation-support denominator stays closed until actual
  generated answer output exists.
- XLSX/PDF answer-generation denominators remain `0`.
