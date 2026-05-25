# RAG Ingestion Measurements

Last updated: 2026-05-25 KST.

This is the rolling human-readable measurement ledger for RAG ingestion and
official answer/citation diagnostics. Keep this file append-style: add new
measurement sections at the top, keep older sections as compact history, and do
not create per-run Markdown reports for routine diagnostic runs.

Machine-readable JSON/JSONL artifacts are evidence payloads, not the primary
human report surface. As of the 2026-05-21 cleanup, `ai/eval/reports/` keeps
only `rag-ingestion/`, and that directory keeps `status.jsonl` plus compact current v3_6_9 and later diagnostic artifacts required by the current RAG profile. Older measurement payloads, including the official
baseline/scorer/input/smoke files and v3_1-v3_6_8 diagnostics, live in:

`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\repo-wide-cleanup-20260521\reports\rag-ingestion-legacy\`

Historical `_archive/legacy` artifact paths in older entries are logical
provenance names. Their physical generated payloads may live in the external
runtime archive under
`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\`.

<!-- official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod:measurements-entry:start -->
### v3_17 User-Locator And Rough-Query Review Packet

- Run: `official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod`
- Policy: diagnostic-only answer-quality review; no official metric, score lift, promotion, threshold tuning, winner selection, production DB write, raw PDF/XLSX query-time parsing, target/gold locator use, expected/supporting text use, or direct normalized answer-value query matching.
- User locator policy: locator text is allowed only when it appears in the user query. Artifact target/gold/supporting/expected locator text is forbidden.
- Runtime evidence policy: resolved user locators hydrate through SourceAtom registry; SearchView/vector payload remains candidate-only.

| Diagnostic count | Value |
| --- | ---: |
| generated_response_count | 39 |
| review_packet_row_count | 39 |
| parse_ok_count | 39 |
| invalid_json_count | 0 |
| citation_rendered_count | 32 |
| abstain_count | 10 |
| user_locator_query_count | 21 |
| user_locator_resolved_count | 20 |
| user_locator_unresolved_count | 1 |
| rough_query_count | 18 |
| rough_query_abstain_count | 6 |
| unique_query_hash_count | 21 |
| hallucination_risk_flag_count | 0 |
| unsupported_claim_risk_count | 0 |
| xlsx_value_formatting_risk_count | 17 |
| over_abstain_review_candidate_count | 3 |
| official_metric_input_rows | 0 |

Artifacts: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod/summary.json`, `metrics.json`, `per_family.json`, `per_query.jsonl`, `responses.jsonl`, `review_packet.csv`, `review_packet.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `prompt_manifest.json`, `user_locator_parse_audit.jsonl`, `user_locator_resolution_audit.jsonl`, `rough_query_bucket_audit.jsonl`, `tool_registry.json`, `route_policy_audit.jsonl`, `runtime_materialization_plan.json`, and `latency_budget_contract.json`.
<!-- official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod:measurements-entry:start -->
### v3_16 Final LLM Answer-Quality Review Packet

- Run: `official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod`
- Policy: diagnostic-only local LLM answer generation for human review; no score lift, official metric, promotion, threshold tuning, winner selection, gold/qrels/label mutation, expected/supporting evidence mutation, raw PDF/XLSX query-time access, or production DB write.
- Inputs: v3_15 XLSX L7 contexts, v3_14 PDF/XLSX runtime traces, v3_13 PDF answer-ready controls, SourceAtom registry, and existing local LLM review conventions.
- Local LLM unavailable behavior: fail explicitly with `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`; no noop or extractive substitute is allowed.

| Diagnostic count | Value |
| --- | ---: |
| generated_response_count | 60 |
| review_packet_row_count | 60 |
| parse_ok_count | 60 |
| invalid_json_count | 0 |
| truncated_or_malformed_response_count | 0 |
| citation_rendered_count | 50 |
| abstain_count | 10 |
| unsupported_claim_risk_count | 0 |
| evidence_underuse_flag_count | 0 |
| xlsx_value_formatting_risk_count | 16 |
| pdf_weak_evidence_window_flag_count | 6 |
| official_metric_input_rows | 0 |
| L8_generation_executed | true |
| deterministic_official_execution | false |
| p95_llm_elapsed_ms | 2160.201 |

Runtime materialization and latency budget: L0-L8 are classified exactly once across `ingestion_time_materialized`, `index_time_materialized`, `query_time_lightweight`, `query_time_cacheable`, or `forbidden_query_time_work`; raw PDF/XLSX query-time parsing, full workbook/sheet scans, full PDF page/block scans, broad SourceAtom scans, and vector-payload-as-evidence-truth are forbidden. L8 generation latency is diagnostic-only and is not mixed into retrieval latency.

Artifacts: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod/review_packet.csv`, `review_packet.jsonl`, `responses.jsonl`, `summary.json`, `metrics.json`, `per_family.json`, `per_query.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `prompt_manifest.json`, `local_llm_readiness.json`, `runtime_materialization_plan.json`, `latency_budget_contract.json`, `per_layer_online_work_audit.jsonl`, `cache_key_contract.json`, and `forbidden_query_time_work_audit.json`.
<!-- official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement:measurements-entry:start -->
### v3_15 XLSX L3 Table/Range Locator Diagnostic

- Run: `official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement`
- Policy: diagnostic-only XLSX L3 table/range locator improvement; official_metric_input_rows=0; no answer generation, deterministic execution, promotion, threshold tuning, winner selection, direct normalized value matching, or product success claim.
- Inputs: v3_14 XLSX runtime adapter trace/per-query artifacts, v3_12 XLSX structural score components, v3_12 metrics-only eval reference flags, and SourceAtom registry joins. No raw XLSX/PDF query-time access.
- Metric boundary: table_or_range@1/@3 are metrics-only diagnostics from the v3_12 reference eval artifact, not v3_15 recomputed success metrics; cell/value@1/@3 are downstream diagnostics and not an optimization target.

| Metric | Value |
| --- | ---: |
| XLSX rows | 344 |
| PDF rows | 0 |
| L3 output availability | 300/344 |
| SourceAtom hydrated after L3 | 300/344 |
| EvidenceBundle assembled after L5 | 300/344 |
| answer-ready context available after L7 | 300/344 |
| L3 zero-output rows | 44 |
| raw_file_query_time_accessed | false |
| L8_executed | false |
<!-- official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod:measurements-entry:start -->
## 2026-05-25 - v3_14 Layered Retrieval Runtime Adapter Non-Prod

- Run: `official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod`
- Policy: diagnostic-only runtime adapter; official_metric_input_rows=0; product_success_evidence_allowed=false; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no L8 generation, deterministic answer execution, promotion, threshold tuning, or winner selection.
- Scope: query-time L0-L7 adapter replay over existing v3_12 XLSX and v3_13 PDF diagnostic artifacts. This measures trace completeness, candidate flow, latency instrumentation, and guardrails, not score lift.
- Holdout: fresh real source-document/workbook-disjoint holdout remains unavailable; current seen rows are diagnostic/no-regression only.

| Runtime adapter metric | value |
| --- | ---: |
| total runtime adapter rows | 673 |
| PDF rows | 329 |
| XLSX rows | 344 |
| median total retrieval latency ms | 0.0429 |
| p95 total retrieval latency ms | 0.06362 |
| max L4 hydrated candidate count | 3 |
| raw_file_query_time_accessed | false |
| L8_executed | false |

Per-family latency and candidate-count summaries are reported separately in the compact metrics, latency, candidate-flow, and per-family artifacts. No PDF/XLSX headline score, official metric, product success evidence, or promotion evidence is produced.
<!-- official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment:measurements-entry:start -->
## 2026-05-25 - v3_13 PDF File Identity Structural Locator Non-Prod Alignment

- Run: `official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment`
- Policy: diagnostic-only; official_metric_input_rows=0; product_success_evidence_allowed=false; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no answer generation, deterministic answer execution, fine-tuning, threshold tuning, winner selection, or promotion.
- Scope: PDF L2/L3 catch-up only. File identity metrics are reported separately from evidence-window metrics. XLSX v3_12 remains a visible control lane, not optimized in v3_13.
- Holdout: still insufficient. Fresh real PDF source-document-disjoint holdout is required before product success evidence.

| Lane | metric | value |
| --- | --- | ---: |
| PDF file identity | file_resolve@1 | 66/329 |
| PDF file identity | file_resolve@3 | 129/329 |
| PDF file identity | abstain_or_disambiguation | 182/329 |
| PDF file identity | accepted wrong rank1 with target in top3 | 63/329 |
| PDF file identity | wrong-file forcing delta from v3_11 | 0/329 |
| PDF structural locator | page candidates | 942/942 |
| PDF structural locator | block candidates | 942/942 |
| PDF structural locator | bbox candidates | 942/942 |
| PDF evidence window | same-page bounded candidates | 341/942 |
| PDF evidence window | answer-ready sufficiency | 251/329 |
| PDF evidence window | bbox correctness | not computed |
| XLSX v3_12 control | optimized in v3_13 | false |
| XLSX v3_12 control | cell_or_value@1 | 21/344 |

Reference: v3_11 PDF file_resolve@1 was 66/329. The wrong-file forcing delta is explicitly disclosed as zero because v3_13 does not change PDF file selection.
<!-- official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement:measurements-entry:start -->
## 2026-05-25 - v3_12 XLSX Structural Locator Non-Prod Improvement

- Run: `official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement`
- Policy: diagnostic-only; official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no answer generation, fine-tuning, threshold tuning, winner selection, or promotion.
- Scope: XLSX L3 structural locator only, after workbook/sheet routing. The checkpoint is v3_11; the compact candidate surface is the v3_9_1 XLSX candidate JSONL because v3_11 stores layer traces rather than candidate lists. PDF lanes and production namespaces are not touched.
- Holdout: still insufficient. Seen-reference lift is no-regression evidence only, not product success.

| XLSX diagnostic metric | v3_11 seen reference | v3_12 non-prod structural locator |
| --- | ---: | ---: |
| table_or_range@1 | 23/344 | 23/344 |
| table_or_range@3 | 29/344 | 29/344 |
| cell_or_value@1 | 20/344 | 21/344 |
| cell_or_value@3 | 26/344 | 26/344 |
| rank1 reranked count | n/a | 11 |
| structural-signal-empty rank1 | n/a | 0/300 |
| zero-signal legacy candidate demotion opportunities | n/a | 796 |
| zero-signal legacy rank1 demotions | n/a | 0 |
| table_or_range@1 gain/loss | n/a | +1/-1 |
| cell_or_value@1 gain/loss | n/a | +1/-0 |

Delta is diagnostic only: cell_or_value@1 +1 on seen-reference rows; table_or_range@1 delta 0 with row-level gain/loss churn shown above.
<!-- official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic:measurements-entry:start -->
## 2026-05-25 - v3_11 Layered Retrieval Diagnostic

- Run: `official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic`
- Policy: diagnostic-only; official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no answer generation, fine-tuning, threshold tuning, or winner selection.
- Layer contract: L0 query routing, L1 coarse candidates, L2 file/workbook identity, L3 structural locator, L4 SourceAtom hydration, L5 EvidenceBundle assembly, L6 evidence selector, L7 answer-ready context, L9 metrics/failure taxonomy. L8 generation/deterministic execution is skipped by design.
- Holdout: still insufficient. Existing seen validation is retained only for no-regression and layer attribution.

| Family/lane | Diagnostic metric | Value |
| --- | --- | ---: |
| XLSX | sheet@1 | 251/344 |
| XLSX | table_or_range@3 | 29/344 |
| XLSX | cell_or_value@3 | 26/344 |
| XLSX | signal-empty rank1 | 0/300 |
| PDF file identity | file_resolve@1 | 66/329 |
| PDF file identity | file_resolve@3 | 129/329 |
| PDF evidence window | bbox_present@3 | 7/942 |

PDF bbox correctness and answer-ready window sufficiency are explicitly not computed in this run; the lane records availability/decomposition only.
<!-- official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization:measurements-entry:start -->
## 2026-05-24 - v3_10 Fresh Real Holdout and XLSX Table-Axis Non-Prod Rematerialization

- Run: `official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization`
- Policy: diagnostic-only; official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no fine-tuning, no threshold tuning, no winner selection.
- Fresh real holdout: insufficient. PDF source-document-disjoint=0/20 target, XLSX workbook-disjoint=0/8 target, real query-fidelity included rows PDF=0 and XLSX=0 against the 100/family target.
- Synthetic OOD guard: 200 query candidates, anti-overfit guard only, product success evidence disallowed.
- XLSX table-axis materialization: `rag-data-xlsx-table-axis-ood-nonprod-v1`, SourceAtom rows=343, SearchUnit rows=343, overlay_only=false.

| XLSX lane | old seen reference | v3_10 non-prod seen smoke | fresh real holdout |
| --- | --- | --- | --- |
| signal-empty rank1 | 257/300 | 0/300 | 0/0 |
| table_or_range@3 | 29/344 | 29/344 | 0/0 |
| cell_or_value@3 | 26/344 | 26/344 | 0/0 |

PDF file identity baseline is kept separate from answer-ready evidence windows: v3_9_1 seen reference file_resolve@1=66/329; fresh real PDF baseline is blocked by missing source-document-disjoint holdout.
<!-- official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset:measurements-entry:start -->
## 2026-05-24 - v3_9_2 Overfit Risk Audit and Blind/OOD Holdout Reset

Run ID: `official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset`.

Scope:

- Diagnostic-only audit over v3_8_3, v3_9, and v3_9_1 artifacts.
- `official_metric_input_rows=0`; future scored adapter remains `DISABLED_PENDING_USER_APPROVAL`.
- Existing validation rows are now seen-validation-only and cannot be future success evidence.
- Fresh real holdout is insufficient: PDF source-document-disjoint `0`, XLSX workbook-disjoint `0`.

Key counts:

| Item | Count |
|---|---:|
| overfit delta rows | 48 |
| insufficient_blind_evidence labels | 48 |
| metric_tradeoff labels | 6 |
| synthetic OOD guard candidates | 14 |
| headline synthetic OOD guard rows | 14 |

Conclusion: no v3_9_1 improvement is preserved as future product success evidence. The useful retained signal is diagnostic direction: XLSX needs non-prod table-axis rematerialization, while PDF file identity must be evaluated separately from answer-ready evidence-window quality.
<!-- official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset:measurements-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic:measurements-entry:start -->


## 2026-05-24 - v3_9_1 XLSX Table-Axis and PDF File Identity Diagnostic

Run family:
`official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic`

Scope:

- Diagnostic-only SourceAtom/SearchUnit locator experiment for XLSX plus oracle-free PDF file identity remeasurement.
- `official_metric_input_rows=0`; future scored adapter remains `DISABLED_PENDING_USER_APPROVAL`.
- No fine-tuning, gold/qrels/labels/expected-answer/supporting-evidence mutation, official denominator mutation, DB/production write, threshold tuning, winner selection, or promotion evidence.
- PDF, XLSX, and TEXT are not collapsed: TEXT is comparison-only, PDF file identity is separate from PDF answer-ready evidence windows.

XLSX 344-row locator surface:

| Metric | v3_8_3 baseline | v3_9_1 |
|---|---:|---:|
| sheet@1 | 249/344 | 251/344 |
| sheet@3 | 249/344 | 251/344 |
| table_or_range@1 | 22/344 | 23/344 |
| table_or_range@3 | 30/344 | 29/344 |
| cell_or_value@1 | 19/344 | 20/344 |
| cell_or_value@3 | 23/344 | 26/344 |
| signal-empty rank1 | 261/300 | 257/300 |

Workbook-disjoint XLSX validation movement:

| Metric | v3_8_3 validation | v3_9_1 validation |
|---|---:|---:|
| sheet@1 | 112/170 | 114/170 |
| sheet@3 | 112/170 | 114/170 |
| table_or_range@1 | 2/170 | 3/170 |
| table_or_range@3 | 6/170 | 9/170 |
| cell_or_value@1 | 2/170 | 3/170 |
| cell_or_value@3 | 6/170 | 9/170 |

XLSX query-fidelity validation included `118/170` rows, above the 30-row minimum. Excluded rows are retained in the audit and separated from headline interpretation.

PDF file identity, separate from answer-ready evidence-window quality:

| Metric | v3_8_2 baseline | v3_9_1 |
|---|---:|---:|
| file_resolve@1 | 65/329 | 66/329 |
| file_resolve@3 | 129/329 | 129/329 |
| abstain | 182/329 | 182/329 |
| wrong_file_block | 57/329 | 60/329 |

Interpretation:

- XLSX rank1 zero-signal pressure moved only slightly, from `261/300` to `257/300`; most remaining rank1 candidates still lack usable table-axis locator signals.
- XLSX validation movement exists at @1 and @3, but the dominant residual remains table/range localization after the workbook/sheet stage.
- PDF file identity gained one rank1 hit and blocked more wrong-file rank1 candidates, while @3 and abstain stayed flat.
- The prior PDF answer-ready gain remains a separate preselected-SourceAtom evidence-window result and is not counted as file-identity improvement here.
<!-- official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic:measurements-entry:end -->

## 2026-05-24 - v3_9 PDF/XLSX Bottleneck Quality Diagnostic

Purpose: focus the current phase on PDF evidence-window quality and XLSX
sheet/range/cell locator bottlenecks. TEXT is comparison-only and is not folded
into a PDF/XLSX headline.

Run ID: `official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement`.

Commands:

```powershell
python -X utf8 ai\scripts\rag_official_answer_citation_agentic_loop_run_v1.py --run-id official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label v3_9_pdf_xlsx_bottleneck_quality_improvement_dev_6pf --cases-per-family 6 --source-families PDF,XLSX --max-tokens 220 --query-max-tokens 160 --timeout-seconds 90
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label v3_9_pdf_xlsx_bottleneck_quality_improvement_validation_6pf --cases-per-family 6 --source-families PDF,XLSX --split-role validation_holdout --dev-summary ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_pdf_xlsx_bottleneck_quality_improvement_dev_6pf_summary.json --max-tokens 220 --query-max-tokens 160 --timeout-seconds 90
```

Split policy:

| Split | Rows | Families | Source-document/workbook disjoint from dev | Role |
|---|---:|---|---|---|
| Dev | 12 | PDF=6, XLSX=6 | n/a | dev-only diagnostic |
| Validation | 12 | PDF=6, XLSX=6 | true (`dev_overlap_document_count=0`) | non-official holdout |

Query-fidelity included score:

| Split | Family | Included rows | Raw final pass | Answer-ready pass | Interpretation |
|---|---|---:|---:|---:|---|
| Dev | PDF | 3 | 2/3 | 2/3 | dev-only, flat |
| Dev | XLSX | 0 | 0/0 | 0/0 | excluded as index-to-content or answer-value-in-query |
| Validation | PDF | 4 | 2/4 | 3/4 | generalized diagnostic signal (+1) |
| Validation | XLSX | 1 | 1/1 | 1/1 | flat; not generalized locator improvement |

All-row answer-quality score:

| Split | Family | Raw final pass | Answer-ready pass | Delta | Raw-pass regression |
|---|---|---:|---:|---:|---:|
| Dev | PDF | 2/6 | 3/6 | +1 | 0 |
| Dev | XLSX | 6/6 | 6/6 | 0 | 0 |
| Validation | PDF | 2/6 | 5/6 | +3 | 0 |
| Validation | XLSX | 6/6 | 6/6 | 0 | 0 |

Locator and residual notes:

- XLSX locator 344-row surface: range@1 `22/344`, cell/value@1 `19/344`;
  sheet@1 remains `249/344`, and top residual bucket remains
  `table_or_range_miss_after_sheet_hit=219`.
- Direct normalized-value query matching remains banned; direct normalized-value query matching remains banned. The current accepted
  structural-specificity tie-breaker is safe on the unit guard but did not move
  the persisted v3_8_3 locator metrics.
- PDF validation evidence-window readiness improved with native same-page/bbox
  windows: bounded expansion `6/6`, average raw score `0.1321`, expanded
  `0.5386`, delta `+0.4065`.
- Validation query-fidelity excluded rows: `7/12` (`PDF=2`, `XLSX=5`), kept in
  artifacts and excluded from generalized success claims.
- OCR was skipped because native text was present and no scanned/image-only or
  native-unusable candidate proved material OCR gain.

Artifacts:

| Artifact | Path |
|---|---|
| Summary | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_summary.json` |
| Metrics | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_metrics.json` |
| Per-family | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_per_family.json` |
| Per-query | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_per_query.jsonl` |
| Failure taxonomy | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_failure_taxonomy.json` |
| Query fidelity audit | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_query_fidelity_audit.jsonl` |
| PDF residual review | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_pdf_residual_review.jsonl` |
| XLSX locator residual review | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_xlsx_locator_residual_review.jsonl` |
| Split manifest | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_split_manifest.json` |

Verification is recorded in the final Korean report and status event; this
section will be amended only if a required verification command fails.

## 2026-05-24 - v3_9 Natural Answer-Quality Diagnostic

Purpose: measure actual answer-quality movement for natural, less-friendly
Korean queries across PDF, XLSX, and TEXT while keeping SourceAtom/EvidenceBundle
citations and all official surfaces closed.

Run ID: `official_answer_citation_agentic_loop_run_v3_9_natural_answer_quality_diagnostic`.

Commands:

```powershell
python -X utf8 ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py --label v3_9_natural_answer_quality_dev_6pf --cases-per-family 6 --source-families PDF,XLSX,TEXT --max-tokens 220 --query-max-tokens 160 --timeout-seconds 90
python -X utf8 ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py --label v3_9_natural_answer_quality_validation_6pf --cases-per-family 6 --source-families PDF,XLSX,TEXT --split-role validation_holdout --dev-summary ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_summary.json --max-tokens 220 --query-max-tokens 160 --timeout-seconds 90
python -X utf8 ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py --run-label v3_9_natural_answer_quality_dev_6pf
python -X utf8 ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py --run-label v3_9_natural_answer_quality_validation_6pf --previous-run-label v3_9_natural_answer_quality_dev_6pf
```

Split policy:

| Split | Rows | Families | Source-document disjoint from dev | Role |
|---|---:|---|---|---|
| Dev | 18 | PDF=6, XLSX=6, TEXT=6 | n/a | dev-only diagnostic |
| Validation | 18 | PDF=6, XLSX=6, TEXT=6 | true (`dev_overlap_document_count=0`) | non-official holdout |

All-row answer-quality score:

| Split | Family | Raw final pass | Answer-ready pass | Delta | Raw-pass regression |
|---|---|---:|---:|---:|---:|
| Dev | PDF | 2/6 | 3/6 | +1 | 0 |
| Dev | XLSX | 6/6 | 6/6 | 0 | 0 |
| Dev | TEXT | 2/6 | 2/6 | 0 | 0 |
| Validation | PDF | 2/6 | 5/6 | +3 | 0 |
| Validation | XLSX | 6/6 | 6/6 | 0 | 0 |
| Validation | TEXT | 5/6 | 5/6 | 0 | 0 |

Query-fidelity included score:

| Split | Family | Included rows | Raw final pass | Answer-ready pass | Interpretation |
|---|---|---:|---:|---:|---|
| Dev | PDF | 3 | 2/3 | 2/3 | dev-only, no headline gain |
| Dev | XLSX | 0 | 0/0 | 0/0 | excluded as index-to-content |
| Dev | TEXT | 6 | 2/6 | 2/6 | dev-only, flat |
| Validation | PDF | 4 | 2/4 | 3/4 | generalized diagnostic signal (+1) |
| Validation | XLSX | 1 | 1/1 | 1/1 | flat; mostly index-to-content excluded |
| Validation | TEXT | 6 | 5/6 | 5/6 | flat |

Failure and structure notes:

- Validation query-fidelity excluded rows: `7/18` (`PDF=2`, `XLSX=5`), kept in
  artifacts and excluded from generalized success claims.
- Validation PDF native text readiness: bounded expansion `6/6`, average raw
  answer-ready score `0.1277`, expanded `0.5367`, delta `+0.4090`.
- Validation residual after answer-ready: PDF has `low_evidence_overlap=1`;
  TEXT has `invalid_json=1`; XLSX has no answer-ready residual in this small
  preselected evidence slice.
- Non-PDF answer-ready rows reuse final locator responses. This neutralizes
  sampling regressions and keeps PDF evidence-window gains separate from XLSX
  and TEXT.
- Raw-pass-to-ready-fail regression stayed `raw_pass_to_ready_fail_regression=0`
  on both dev and validation.
- All-family `answer_quality` aggregate blocks remain diagnostic aggregates
  only (`diagnostic_aggregate_only=true`, `headline_allowed=false`); the
  reportable evidence is the family-separated query-fidelity validation table.
- The XLSX bottleneck did not move here. The active structural locator
  bottleneck remains the v3_8_3 scoped taxonomy:
  `table_or_range_miss_after_sheet_hit=219`.
- OCR was skipped because native text was present and the validation gain came
  from native same-page/bbox expansion, not OCR.

Artifacts:

| Artifact | Path |
|---|---|
| Dev summary | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_summary.json` |
| Dev metrics | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_metrics.json` |
| Dev per-family | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_per_family.json` |
| Dev per-query | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_per_query.jsonl` |
| Validation summary | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_summary.json` |
| Validation metrics | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_metrics.json` |
| Validation per-family | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_per_family.json` |
| Validation per-query | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_per_query.jsonl` |
| Dev review packet | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_v3_9_natural_answer_quality_dev_6pf/` |
| Validation review packet | `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_v3_9_natural_answer_quality_validation_6pf/` |

Verification:

| Check | Result |
|---|---|
| `python -X utf8 -m py_compile ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py` | passed |
| `python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "pdf_answer_ready or pdf_xlsx_answer_quality_review_packet or v3_9 or natural_answer_quality_benchmark_can_opt_in_text or non_pdf_answer_ready_reuses"` | 21 passed, 95 deselected |
| `python -X utf8 -m pytest ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_9_natural_answer_quality_does_not_mutate_protected_surfaces -q` | 1 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_v3_9_review_packet_query_fidelity_matches_compact_metrics -q` | 1 passed |
| `python -X utf8 -m pytest -p no:cacheprovider ai/tests/test_rag_diagnostic_status_sync.py::test_progress_measurements_triage_and_status_record_v3_9_natural_answer_quality_without_promotion -q` | 1 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q` | 3 passed |
| `python -X utf8 -m pytest ai/tests --rag-current -q` | 376 passed, 8 warnings |
| `git diff --check` | passed; line-ending warnings only |
| `python -X utf8 ai/scripts/rag_pdf_xlsx_perf_benchmark.py --label v3_9_natural_answer_quality_perf_smoke --warmups 1 --iterations 1 --output %TEMP%\codex-v3_9-natural-answer-quality-perf-smoke.json` | PDF native 25.225 ms, PDF OCR fallback 77.776 ms, XLSX merged range 285.717 ms, SearchUnit duplicate skip 103.475 ms |

Temporary files removed: `%TEMP%\codex-v3_9-natural-answer-quality-perf-smoke.json`.
Untracked files are checked in the final `git status --short --untracked-files=all`.

## 2026-05-24 - XLSX v3_8_3 Scoped Locator Anti-Overfit Validation

Purpose: harden the post-v3_8_3 XLSX scoped sheet/table-range/cell diagnostic
resolver without opening answer generation, official metrics, qrels, gold, or
promotion surfaces.

Commands:

```powershell
python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "v3_8_3_xlsx_query_locator_signals_normalize_page_sheet_names"
python -X utf8 -m py_compile ai/scripts/rag_official_answer_citation_agentic_loop_run_v1.py
python -X utf8 ai/scripts/rag_official_answer_citation_agentic_loop_run_v1.py --run-id official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic
python -X utf8 -m pytest ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_8_3_xlsx_scoped_cell_resolve_artifacts_are_registered_hash_locked_and_compact ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_8_3_xlsx_scoped_cell_resolve_writer_emits_compact_artifacts_and_summary_hashes -q
```

Split policy:

| Split | Rows | Workbook disjoint from dev | Source-identity disjoint from dev | Role |
|---|---:|---|---|---|
| Protected regression | 19 | n/a | n/a | sealed no-regression check |
| Dev | 155 | n/a | n/a | legacy v3_8_3 rows, dev-only |
| Validation | 170 | true | true | workbook-disjoint non-official validation |

Diagnostic locator metrics:

| Scope | sheet@1 baseline -> current | range@1 baseline -> current | cell/value@1 baseline -> current | abstain baseline -> current |
|---|---:|---:|---:|---:|
| Overall XLSX | 248/344 -> 249/344 | 22/344 -> 22/344 | 19/344 -> 19/344 | 44/344 -> 44/344 |
| Protected | 17/19 -> 17/19 | 17/19 -> 17/19 | 17/19 -> 17/19 | 1/19 -> 1/19 |
| Dev | 120/155 -> 120/155 | 3/155 -> 3/155 | 0/155 -> 0/155 | 9/155 -> 9/155 |
| Validation | 111/170 -> 112/170 | 2/170 -> 2/170 | 2/170 -> 2/170 | 34/170 -> 34/170 |

Interpretation:

- The only generalized gain is validation sheet@1 +1 from generic page-style
  sheet-name normalization (`26페이지` matching `26p`). It is diagnostic-only
  and not an official Hit@K/MRR/nDCG claim.
- Dev-only rows did not improve, so there is no dev-only pass-count gain being
  counted as success.
- Table/range and cell/value metrics stayed unchanged; the top remaining bucket
  remains `table_or_range_miss_after_sheet_hit=219`.
- A direct normalized-value query signal was tried and rejected because it
  regressed one validation cell/value pass. The frozen candidate rules now keep
  row/column/date and page-sheet normalization but do not use normalized-value
  text as a direct scoring signal.
- `official_metric_input_rows=0`; future scored adapter status remains
  `DISABLED_PENDING_USER_APPROVAL`; no PDF/OCR optimization was opened.

Artifacts:

| Artifact | Path |
|---|---|
| Summary | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_summary.json` |
| Metrics + compact miss matrix | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_metrics.json` |
| Per-query diagnostics | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_per_query.jsonl` |
| Per-family diagnostics | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_per_family.json` |
| Status ledger | `ai/eval/reports/rag-ingestion/status.jsonl` |

Verification:

| Check | Result |
|---|---|
| `python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "v3_8_3"` | 12 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_8_3_xlsx_scoped_cell_resolve_artifacts_are_registered_hash_locked_and_compact ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py::test_v3_8_3_xlsx_scoped_cell_resolve_writer_emits_compact_artifacts_and_summary_hashes -q` | 2 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_diagnostic_status_sync.py::test_progress_status_and_triage_gate_record_v3_8_3_xlsx_scoped_cell_resolve_without_promotion -q` | 1 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_diagnostic_guardrail_git_diff.py::test_v3_8_3_xlsx_scoped_cell_resolve_does_not_mutate_source_registry_or_protected_surfaces -q` | 1 passed |
| `python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q` | 3 passed |
| `python -X utf8 -m pytest ai/tests --rag-current -q` | 367 passed, 8 warnings |
| `python -X utf8 -m py_compile ai/scripts/rag_official_answer_citation_agentic_loop_run_v1.py ai/scripts/rag_pdf_xlsx_perf_benchmark.py` | passed |
| `python -X utf8 ai/scripts/rag_pdf_xlsx_perf_benchmark.py --label v3_8_3_xlsx_scoped_locator_validation_smoke --warmups 1 --iterations 1 --output %TEMP%\codex-v3_8_3-xlsx-perf-smoke.json` | PDF native 30.625 ms, PDF OCR fallback 65.236 ms, XLSX merged range 198.396 ms, SearchUnit duplicate skip 95.566 ms |
| `git diff --check` | passed; line-ending warnings only |

Changed tracked files:

- `ai/scripts/rag_official_answer_citation_agentic_loop_run_v1.py`
- `ai/tests/test_rag_answer_citation_silver_manifest_v1.py`
- `ai/tests/test_rag_current_focused_test_profile_v1.py`
- `ai/tests/test_rag_diagnostic_status_sync.py`
- `ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py`
- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`

Temporary files removed: `%TEMP%\codex-v3_8_3-xlsx-perf-smoke.json`,
`%TEMP%\codex-v3_8_3-xlsx-baseline.json`. Untracked files: none.

## 2026-05-24 - PDF Answer-Ready Overfit Guard And Holdout

Purpose: keep PDF answer-ready evidence work diagnostic-only while separating
dev gains from validation evidence before any residual optimization.

Commands:

```powershell
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label answer_ready_pdf_v1_llm_15pf --cases-per-family 15 --max-tokens 220 --query-max-tokens 180 --timeout-seconds 90 --split-role dev_current_pdf_headline
python -X utf8 ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py --run-label answer_ready_pdf_v1_llm_15pf
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label answer_ready_pdf_v1_llm_15pf_validation --cases-per-family 15 --max-tokens 220 --query-max-tokens 180 --timeout-seconds 90 --split-role validation_holdout --dev-summary ai\eval\reports\rag-ingestion\quality\pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_summary.json
python -X utf8 ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py --run-label answer_ready_pdf_v1_llm_15pf_validation --previous-run-label answer_ready_pdf_v1_llm_15pf
```

Split policy:

| Split | Rows | PDF rows | XLSX rows | Source-document disjoint from dev | Success evidence allowed |
|---|---:|---:|---:|---|---|
| Dev current PDF headline | 30 | 15 | 15 | n/a | false |
| Validation holdout | 30 | 15 | 15 | true, overlap=0 | true, diagnostic-only |

Answer quality:

| Split/scope | Raw final pass | Combined answer-ready pass | Fresh answer-ready pass | Raw-final reused pass | Delta combined vs raw |
|---|---:|---:|---:|---:|---:|
| Dev all rows | 17/30 | 20/30 | 19/30 | 1/30 | +3 |
| Dev PDF all rows | 5/15 | 8/15 | 7/15 | 1/15 | +3 |
| Dev XLSX all rows | 12/15 | 12/15 | 12/15 | 0/15 | +0 |
| Dev query-fidelity headline | 9/17 | 12/17 | 11/17 | 1/17 | +3 |
| Dev PDF headline | 5/13 | 8/13 | 7/13 | 1/13 | +3 |
| Validation all rows | 18/30 | 20/30 | 17/30 | 3/30 | +2 |
| Validation PDF all rows | 8/15 | 9/15 | 6/15 | 3/15 | +1 |
| Validation XLSX all rows | 10/15 | 11/15 | 11/15 | 0/15 | +1 |
| Validation query-fidelity headline | 8/15 | 8/15 | 5/15 | 3/15 | +0 |
| Validation PDF headline | 8/14 | 8/14 | 5/14 | 3/14 | +0 |

Interpretation:

- The prior `19/30 -> 23/30`, headline `9/16 -> 11/16`, and PDF headline
  `5/12 -> 7/12` counts are retained only as prior dev/query-fidelity
  diagnostics.
- The fresh dev PDF headline gain is not counted as success by itself:
  `dev_only=true` and `success_evidence_allowed=false`.
- The source-document-disjoint holdout gives a small combined all-row PDF
  diagnostic gain (`8/15 -> 9/15`), but that combined count includes three
  raw-final reused passes. It has no query-fidelity headline PDF gain
  (`8/14 -> 8/14`) and fresh PDF answer-ready headline passes are `5/14`.
  Residual optimization should not claim generalized PDF answer-ready success
  from the dev headline count alone.
- Raw-pass-to-ready-fail regressions are zero in both dev and validation after
  the raw-final reuse guard.

PDF evidence readiness:

| Split | Bounded expansion | Weak snippets | Dot-heavy | Locator-only | OCR-ish | Avg raw score | Avg expanded score | Avg delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dev | 12/15 | 11/15 | 11/15 | 3/15 | 12/15 | 0.1235 | 0.4501 | +0.3266 |
| Validation | 15/15 | 11/15 | 11/15 | 0/15 | 14/15 | 0.1184 | 0.5291 | +0.4107 |

Residual review:

| Split | Answer-ready failed rows | Query-excluded review-only rows | Weak evidence | Dot/OCR artifact | Locator-only | Broad context | Evaluator limitation | Query drift | True answer failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dev answer-ready failures | 7 | 0 | 6 | 7 | 3 | 4 | 7 | 2 | 0 |
| Validation answer-ready failures | 6 | 0 | 6 | 6 | 0 | 2 | 2 | 0 | 0 |
| Validation full review table | 6 | 1 | 7 | 7 | 0 | 2 | 2 | 1 | 0 |

Primary artifacts:

- Dev summary:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_summary.json`
- Dev packet:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/`
- Validation summary:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_validation_summary.json`
- Validation packet:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf_validation/`
- Perf smoke:
  `ai/eval/reports/rag-ingestion/perf/pdf_xlsx_perf_answer_ready_overfit_guard_smoke.json`

Boundary and OCR rationale:

- `official_metric_input_rows=0` in both packets.
- The future scored adapter remains `DISABLED_PENDING_USER_APPROVAL`.
- Expected answers, supporting evidence, gold fields, qrels, labels, official
  denominator, namespace isolation, production, promotion, thresholds, and
  winner selection remain unchanged.
- OCR was skipped because validation did not prove native text absence or
  unusability, and OCR-ish residuals are still mixed with weak evidence,
  locator/citation shape, evaluator overlap, and query-policy issues.

Verification completed for this entry:

```powershell
python -X utf8 -m py_compile ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py ai\scripts\rag_pdf_xlsx_anti_overfit_audit.py
python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "pdf_xlsx_answer_quality_review_packet or pdf_answer_ready or query_fidelity or anti_overfit"
python -X utf8 ai\scripts\rag_pdf_xlsx_anti_overfit_audit.py
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label answer_ready_pdf_overfit_guard_perf_smoke --warmups 1 --iterations 1 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_answer_ready_overfit_guard_smoke.json
python -X utf8 -m pytest ai/tests/test_rag_diagnostic_status_sync.py -q -k "pdf_answer_ready or query_fidelity or status_jsonl"
python -X utf8 -m pytest ai/tests/test_rag_anti_shortcut_guardrail_audit_v1.py ai/tests/test_rag_diagnostic_guardrail_git_diff.py -q
python -X utf8 -m pytest ai/tests --rag-current -q
git diff --name-only -- ai/eval/eval_queries ai/eval/source_registry ai/eval/indexes ai/eval/silver ai/eval/reports/rag-ingestion/baseline_v1.json ai/eval/reports/rag-ingestion/metric_input_v1.json ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl
git diff --cached --name-only -- ai/eval/eval_queries ai/eval/source_registry ai/eval/indexes ai/eval/silver ai/eval/reports/rag-ingestion/baseline_v1.json ai/eval/reports/rag-ingestion/metric_input_v1.json ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl
git diff --check
git status --short --untracked-files=all
```

Results: focused packet tests `15 passed`; status sync `4 passed`; guardrail
tests `39 passed`; current profile `361 passed`. The first current-profile
attempt correctly failed on temporary anti-overfit audit files in the report
root; those files were removed and the audit default now writes to the system
temp directory instead of the protected report root.

Protected diff checks reported no tracked or staged changes under eval queries,
source registry, indexes, silver, official baseline/config, or candidate JSONL
surfaces. `git diff --check` passed with line-ending warnings only. `git status
--short --untracked-files=all` showed no untracked files.

Changed tracked files:

- `ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py`
- `ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py`
- `ai/scripts/rag_pdf_xlsx_anti_overfit_audit.py`
- `ai/tests/test_rag_answer_citation_silver_manifest_v1.py`
- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`

New tracked files: none. New repo-local scratch artifacts: none. Temporary
files removed: accidental report-root `rag_pdf_xlsx_anti_overfit_audit.json`
and `.csv`, plus the system-temp anti-overfit audit JSON/CSV created by the
final scanner run.

## 2026-05-22 - PDF Answer-Ready Evidence Readiness Audit

Purpose: improve diagnostic PDF answer quality by shaping retrieved PDF
evidence into answer-ready snippets, without changing gold labels, qrels,
expected answers, supporting evidence, denominator policy, namespace isolation,
or diagnostic-only semantics. XLSX stays in the run only as a no-regression
control.

Commands:

```powershell
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label answer_ready_pdf_v1_llm_15pf --cases-per-family 15 --max-tokens 220 --query-max-tokens 180 --timeout-seconds 90
python -X utf8 ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py --run-label answer_ready_pdf_v1_llm_15pf
```

Answer quality:

| Family | Raw final locator context | Normalized/expanded answer-ready context | Delta |
|---|---:|---:|---:|
| PDF | 5/15 | 8/15 | +3 |
| XLSX | 14/15 | 15/15 | +1 |
| Aggregate diagnostic-only | 19/30 | 23/30 | +4 |

Query fidelity addendum, 2026-05-24:

| Scope | Rows | Raw final pass | Answer-ready pass | Delta |
|---|---:|---:|---:|---:|
| All rows, query-fidelity-unverified | 30 | 19/30 | 23/30 | +4 |
| Headline-included fidelity subset | 16 | 9/16 | 11/16 | +2 |
| PDF headline-included subset | 12 | 5/12 | 7/12 | +2 |
| XLSX headline-included subset | 4 | 4/4 | 4/4 | +0 |

Query drift classification:

| Family | Headline included | Excluded | Severity counts |
|---|---:|---:|---|
| PDF | 12 | 3 | index_to_content_query=1, major_topic_drift=2, minor_specificity_change=7, style_only=5 |
| XLSX | 4 | 11 | index_to_content_query=11, minor_specificity_change=2, style_only=2 |

Rows excluded from the headline subset are not deleted. They remain in the
review packet with blank user decision fields and require user query approval
before any future official-adjacent adapter could consider them.

PDF Evidence Readiness:

| Metric | Value |
|---|---:|
| PDF audit cases | 15 |
| Bounded expansion applied | 11 |
| Weak snippets | 11 |
| Dot-heavy snippets | 11 |
| Locator-only flags | 4 |
| OCR-ish flags | 11 |
| Table/form-like flags | 0 |
| Average raw answer-ready score | 0.1152 |
| Average expanded answer-ready score | 0.3938 |
| Average answer-ready score delta | +0.2786 |
| XLSX context changed | false |

Primary artifacts:

- Run id:
  `pdf_xlsx_answer_quality_evidence_readiness_packet_answer_ready_pdf_v1_llm_15pf`
- Summary:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_summary.json`
- Full responses:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_responses.jsonl`
- PDF evidence-readiness audit:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_pdf_evidence_readiness_audit.jsonl`
- Review packet:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/`
- PDF delta audit:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/pdf_delta_audit.jsonl`
- Query fidelity audit:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/query_fidelity_audit.jsonl`
- PDF residual review:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/pdf_residual_review.md`

The audit records raw snippets, normalized snippets, original locator/page/bbox
metadata, character length, query overlap, repeated punctuation ratio,
text-density, locator-only/table-form/OCR-ish flags, answer-ready score, and
whether bounded expansion was applied. Example expansion keeps the original
page/bbox/source locator and expands a same-page PDF `text_block` heading
"산림청 정책연구용역 관리규정..." into nearby same-page form text including
"정책연구용역과제심의신청서" and "정책연구과제명". Expansion is capped by
same-page lines/chars and uses PDF block windows only as diagnostic context; it
does not mutate source PDFs or official gold surfaces.

Non-gold decisions and rationale:

- Dot leaders/repeated punctuation and excessive whitespace are normalized only
  in diagnostic evidence text; page numbers, decimals, legal/article numbers,
  citations, and original source metadata are preserved.
- Weak PDF snippets are expanded with same-page manifest neighbors first and
  same-page PDF block windows second when a local PDF path is available. Full
  pages are not dumped.
- Answer-ready score uses structural evidence-quality signals only: density,
  query overlap, repeated-punctuation ratio, and weak locator/table/OCR flags.
  It is not tuned against gold answers.
- Retrieval miss is reported as
  `not_recomputed_preselected_sourceatom_evidence_only`; this run measures
  answer-ready shaping on existing diagnostic PDF cases, not retrieval recall.

Remaining user-owned gold/policy decisions:

- answerable
- relevance
- expected answer
- supporting evidence
- pass/fail
- denominator eligibility
- policy note
- review approval
- query intent preserved
- query approval
- query policy note

PDF residual review after query-fidelity audit:

| Bucket | Count |
|---|---:|
| answer-ready failing PDF cases | 7 |
| residual-review rows, including query-drift pass rows | 8 |
| weak evidence | 7 |
| dot/OCR artifact | 8 |
| broad context | 3 |
| locator-only | 5 |
| table/form | 0 |
| query drift | 3 |
| evaluator limitation | 7 |
| true answer failure | 0 |

OCR decision: skipped for this slice. The diagnostic evidence points to query
drift, weak/locator-like evidence windows, and evaluator overlap limits before
OCR extraction failure. OCR-ish text remains measured but is not predictive
enough here to justify provider/source changes.

Guardrail status: `official_metric_input_rows=0`,
`future_scored_adapter=DISABLED_PENDING_USER_APPROVAL`, no promotion evidence,
no threshold tuning, no winner selection, and no gold/qrels/label/expected
answer/supporting evidence/denominator/namespace mutation.

Changed files for this slice:

- `ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py`
- `ai/scripts/rag_pdf_xlsx_answer_quality_review_packet.py`
- `ai/tests/test_rag_answer_citation_silver_manifest_v1.py`
- `ai/tests/test_rag_diagnostic_status_sync.py`
- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`
- `ai/eval/reports/rag-ingestion/status.jsonl`

Verification commands run:

```powershell
python -X utf8 -m py_compile ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py
python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_answer_ready_normalization_collapses_dot_leaders_without_touching_numbers ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_answer_ready_expansion_uses_bounded_same_page_neighbors_and_preserves_locator ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_answer_ready_score_demotes_locator_only_dot_heavy_evidence ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_answer_ready_dry_run_audit_is_diagnostic_only_and_keeps_xlsx_unchanged -q
python -X utf8 -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_xlsx_answer_quality_review_packet_pairs_final_run_rows_and_keeps_user_fields_blank ai/tests/test_rag_answer_citation_silver_manifest_v1.py::test_pdf_xlsx_answer_quality_review_packet_future_adapter_stays_disabled_until_user_approval -q
python -m pytest ai/tests/test_rag_answer_citation_silver_manifest_v1.py -q -k "pdf_xlsx_answer_quality_review_packet or pdf_answer_ready"
python -X utf8 -m pytest ai/tests/test_rag_source_bound_official_denominator_index.py::test_pdf_xlsx_llm_quality_benchmark_dry_run_records_silver_seed_and_policy ai/tests/test_rag_source_bound_official_denominator_index.py::test_pdf_xlsx_llm_quality_benchmark_joins_silver_without_locator_only_cross_join ai/tests/test_rag_source_bound_official_denominator_index.py::test_pdf_xlsx_llm_quality_benchmark_scores_locator_and_value_grounding -q
python -X utf8 -m pytest ai/tests/test_rag_diagnostic_status_sync.py::test_progress_measurements_triage_and_status_record_pdf_xlsx_quality_review_packet_without_promotion ai/tests/test_rag_diagnostic_status_sync.py::test_progress_measurements_triage_and_status_record_pdf_answer_ready_evidence_without_promotion -q
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 -m pytest ai/tests/test_rag_anti_shortcut_guardrail_audit_v1.py -q
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label answer_ready_pdf_v1_perf_smoke --warmups 1 --iterations 1 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_answer_ready_pdf_v1_smoke.json
git diff --check
```

Latest verification output after the 2026-05-24 quality rerun:
`python -m pytest ai/tests --rag-current -q` -> 351 passed, 8 warnings;
targeted packet/answer-ready tests -> 10 passed; status sync addendum tests ->
2 passed; source-bound benchmark tests -> 4 passed; anti-shortcut guardrail
tests -> 9 passed; py_compile PASS; protected gold/denominator diff empty;
`git diff --check` PASS with line-ending warnings only.

Performance smoke result: PDF native 27.804 ms, PDF OCR fallback 69.389 ms,
XLSX large merged range 239.061 ms, SearchUnit duplicate skip 121.446 ms. This
is a no-regression smoke for the existing performance path, not a new
representative product-performance claim.

## 2026-05-22 - PDF/XLSX LLM Query And Answer-Quality Benchmark

Purpose: measure whether locator-rich PDF/XLSX context and stricter answer
contracts improve local-LLM answer grounding without changing gold, qrels,
labels, expected answers, supporting evidence, denominators, namespaces, DB
state, or diagnostic-only policy. The benchmark is diagnostic-only and uses
generation-allowed non-official SearchView rows joined to the v3_7_2 weak
silver natural-query manifest as rewrite seeds. Silver rows are seeds only, not
gold or official labels.

Environment assumptions:

- Windows/PowerShell workspace:
  `D:\async-ocr-rag-multimodal-pipeline`
- Local OpenAI-compatible llama.cpp endpoint:
  `http://localhost:8081/v1`
- Model label: `gemma4-e2b-local`
- Benchmark script:
  `ai/scripts/rag_pdf_xlsx_llm_quality_benchmark.py`

Commands:

```powershell
python -X utf8 ai\scripts\rag_pdf_xlsx_llm_quality_benchmark.py --label final_llm_rewrite_all_llm_15pf_v3 --cases-per-family 15 --max-tokens 220 --query-max-tokens 180 --timeout-seconds 90
python -X utf8 ai\scripts\rag_pdf_xlsx_answer_quality_review_packet.py --run-label final_llm_rewrite_all_llm_15pf_v3
python -X utf8 -m pytest ai/tests/test_rag_source_bound_official_denominator_index.py -q
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label quality_goal_perf_smoke_final --warmups 1 --iterations 1 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_quality_goal_smoke_final.json
```

Inputs and policy:

| Item | Value |
|---|---|
| SearchView manifest | `ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl` |
| Silver seed manifest | `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_7_2_local_llm_natural_silver_query_regeneration_llm_natural_silver_manifest_all.jsonl` |
| Join key | `source_family+source_identity+locator_fingerprint` |
| Cases | PDF=15, XLSX=15 |
| Silver seed rows | 30/30 |
| LLM rewrite rows | 30/30 |
| Fallback rows | 0 |
| Manifest partition | `core=30` |
| Promotion / tuning | false / false |

Query quality:

| Metric | Friendly baseline | LLM-rewritten final |
|---|---:|---:|
| Query count | 30 | 30 |
| Style count | 1 | 4 |
| Style distribution | `source_grounded=30` | `source_grounded=11`, `messy_user_like=10`, `terse_question=8`, `short_fragment=1` |
| Friendly suffix ratio | 1.0000 | 0.0000 |
| Max same six-character prefix | 15 | 1 |
| Average characters | 157.000 | 30.267 |

Answer quality:

| Family | Baseline legacy context | Final locator context | Delta |
|---|---:|---:|---:|
| PDF | 0/15 | 6/15 | +6 |
| XLSX | 0/15 | 15/15 | +15 |
| Aggregate diagnostic-only | 0/30 | 21/30 | +21 |

Failure taxonomy:

| Mode | Residuals |
|---|---|
| Baseline legacy context | `pdf_locator_missing=15`, `xlsx_locator_missing=15`, `low_evidence_overlap=10` |
| Final locator context | `low_evidence_overlap=9`, `locator_only_answer=1`, `pdf_locator_missing=1` |

Primary artifacts:

- Summary with 30 balanced sampled query/actual-response rows:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_final_llm_rewrite_all_llm_15pf_v3_summary.json`
- Full response JSONL:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_final_llm_rewrite_all_llm_15pf_v3_responses.jsonl`

Gold-review packet:

- Run id:
  `pdf_xlsx_answer_quality_gold_review_packet_final_llm_rewrite_all_llm_15pf_v3`
- Artifact directory:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/`
- Review CSV:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/review_packet.csv`
- Review JSONL:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/review_packet.jsonl`
- Markdown summary:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/summary.md`
- Manifest / schema validation:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/manifest.json`

Review packet rows=30. The packet pairs the 60 response rows into one row per
case, rehydrates SourceAtom evidence/locator data from the benchmark manifest,
keeps user-owned columns blank, sets `official_metric_candidate=FALSE`, and
records `official_metric_input_rows=0`. The future scored adapter is disabled
with status `DISABLED_PENDING_USER_APPROVAL`; it is documentation and schema
surface only until the user fills and approves review decisions and a separate
scored-eval integration change is made.

PDF residual review taxonomy:

| Likely cause | Count |
|---|---:|
| retrieval_miss | 0 |
| weak_snippet | 9 |
| ocr_ish_text | 1 |
| locator_only_evidence | 8 |
| table_form_formatting | 8 |
| semantic_answer_mismatch | 9 |
| evaluator_overlap_limitation | 9 |

User-owned decisions needed next:

- answerable
- relevance
- expected answer
- supporting evidence
- pass/fail
- denominator eligibility
- policy note
- review approval

Non-gold decisions and rationale:

- Existing v3_7_2 weak silver was used only as a query rewrite seed because it
  is diagnostic-only, not gold, not qrels, not official denominator, and not
  promotion evidence.
- The review packet generator pairs existing diagnostic response rows and
  SourceAtom evidence only; it does not use expected answers or supporting
  evidence and does not create official metric inputs.
- Locator-only silver matching was disabled; seed joins require source family,
  source identity, and locator fingerprint to avoid cross-document leakage.
- Query source-overlap misses are recorded as warnings, not fallback triggers,
  because Korean spacing, translation, and English/Korean paraphrase can make
  exact lexical validation too brittle; hard failures remain copy-seed,
  friendly-template ending, internal surface leak, parse failure, and length
  bounds.
- PDF scoring now requires bbox when bbox is available, and XLSX scoring
  requires cell/range when available; this measures citation/evidence
  usability rather than accepting doc/page or workbook-only locators.
- Long XLSX normalized text values accept meaningful token overlap while
  numeric values still require numeric equivalence; this avoids requiring a
  whole long cell string to be repeated verbatim.

Remaining diagnostic risks:

- PDF residuals are mostly low-evidence-overlap/answer-renderer behavior on
  very terse source snippets; improving those may require row-level answer
  policy or gold review before changing expected answer semantics.
- Query style is improved but still skewed toward source-grounded and terse
  question forms; broader style distribution can be tuned diagnostically, but
  should not be used as a promotion gate.
- The review packet is ready for human adjudication, but all blank user-owned
  fields must remain non-scoring until the user supplies explicit decisions.

## 2026-05-22 - PDF/XLSX Ingestion Performance Benchmark

Purpose: establish a measured, reproducible performance baseline for PDF and
XLSX ingestion paths before and after bounded hot-path fixes. Inputs are
synthetic and generated in memory to avoid gold, qrels, labels, official
denominator rows, production namespaces, and production indexes.

Environment assumptions:

- Windows/PowerShell workspace:
  `D:\async-ocr-rag-multimodal-pipeline`
- Python: `python -X utf8` (`Python 3.13.0` in this run)
- Benchmark script:
  `ai/scripts/rag_pdf_xlsx_perf_benchmark.py`
- Memory observation: `tracemalloc` peak KiB, not process RSS.

Commands:

```powershell
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label baseline_before_optimization --warmups 1 --iterations 3 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_baseline_before_optimization.json
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label final_after_pdf_probe_optimization_comparable_3x --warmups 1 --iterations 3 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_final_after_pdf_probe_optimization_comparable_3x.json
python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label final_after_optimization --warmups 1 --iterations 5 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_final_after_optimization.json
```

Input sizes:

| Input | Shape |
|---|---|
| PDF native text | 8 pages, 72 text blocks/page, no supported deterministic table markers |
| PDF OCR fallback | 6 blank pages, fake OCR provider, 110 DPI render path |
| XLSX large merged range | 1 sheet, merged range `A1:ALL1000`, 40 visible rows after merge |
| SearchUnit duplicate skip | 1,800 synthetic docs/chunks, non-production diagnostic namespace |

Median latency:

| Case | Baseline 3x | Final comparable 3x | Delta |
|---|---:|---:|---:|
| PDF native text, no supported tables | 27.698 ms | 22.932 ms | -17.2% |
| PDF OCR fallback blank pages | 61.102 ms | 62.064 ms | +1.6% |
| XLSX large merged range | 20,191.989 ms | 165.670 ms | -99.2% |
| SearchUnit duplicate skip | 114.690 ms | 79.897 ms | -30.3% |

Median peak `tracemalloc`:

| Case | Baseline 3x | Final comparable 3x | Delta |
|---|---:|---:|---:|
| PDF native text, no supported tables | 408.5 KiB | 408.0 KiB | -0.1% |
| PDF OCR fallback blank pages | 43.1 KiB | 42.5 KiB | -1.4% |
| XLSX large merged range | 348,611.6 KiB | 6,430.8 KiB | -98.2% |
| SearchUnit duplicate skip | 2,227.0 KiB | 2,277.7 KiB | +2.3% |

5x final stability check:

| Case | Final 5x median |
|---|---:|
| PDF native text, no supported tables | 23.273 ms |
| PDF OCR fallback blank pages | 59.504 ms |
| XLSX large merged range | 159.260 ms |
| SearchUnit duplicate skip | 79.277 ms |

Profile ranking before code changes:

1. XLSX dangerous merged range: `openpyxl.load_workbook(read_only=False)`
   spent almost the entire 20.7 seconds in merged-cell/style binding.
2. PDF OCR fallback: `_render_pdf_page_png` was called once per OCR-needed
   page; rendering/PNG encoding dominated the synthetic blank-page case.
3. SearchUnit duplicate skip: `_is_duplicate_indexed` performed a repeated
   scan over existing chunks for every incoming document.
4. PDF native table extraction: deterministic table parsing was narrow enough
   to prefilter safely by the same supported marker families.

Policy: this is performance evidence only. It is not official retrieval
quality, not answer/citation promotion evidence, and not a representative
product-performance claim. No user-owned gold decision was needed.

## 2026-05-21 - Report Artifact Layout Rollup

Purpose: make the repo-local report surface small enough to scan while keeping
older evidence reproducible through the external archive resolver.

Current repo-local machine payloads:

- `ai/eval/reports/rag-ingestion/status.jsonl`
- Compact current v3_6_9 SearchUnit/SearchView/SourceAtom refactor artifacts,
  v3_7 source-registry/index/retrieval-smoke artifacts, and v3_8/v3_8_1/v3_8_2/v3_8_3
  diagnostic retrieval, evidence-selector, oracle-free file-resolve, and XLSX scoped cell-resolve
  artifacts.

Archived payload families:

- `ai/eval/reports/rag-ingestion/*` except the compact current files listed above:
  `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\repo-wide-cleanup-20260521\reports\rag-ingestion-legacy\`
- former `ai/eval/reports/phase7/` and
  `ai/eval/reports/legacy-baseline-final/`:
  `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\repo-wide-cleanup-20260521\reports\`

Reader contract: use this file for metric ladder context, use
`docs/rag-ingestion-triage.md` for queue/row-level decisions, and use
`docs/rag-ingestion-progress.md` for current status and guardrails.

## Current Measurement Ladder

| Stage | Run family | Scope | Key result | Guardrail |
|---|---|---|---|---|
| Official first-run baseline | `official_answer_citation_metric_first_run_v1` | 29 official rows | PASS `8/29`, `CITATION_UNSUPPORTED=11`, `PARTIAL_OR_UNSUPPORTED=10` | Diagnostic baseline only |
| v1 diagnostic live-generation | `official_answer_citation_agentic_loop_run_v1` | Fixture-all index, noop/extractive generation | PASS `1/29`; fixture-all/noop/chunk-only limitations | `promotion_evidence=false` |
| Source-bound index readiness | `official_answer_citation_source_bound_index_build_readiness_v1` | 29 source-bound SearchUnits | `BUILD_READY_LOAD_CHECK_PASSED` | Non-production index only |
| v3 comparable live measurement | `official_answer_citation_agentic_loop_run_v3_comparable_live_measurement` | 29 rows, structured adapter retained for XLSX/PDF | PASS `27/29`; PDF `4/4`, XLSX `19/19`, TEXT `4/6` | Diagnostic-only; not answer/citation promotion evidence |
| v3_8_3 XLSX scoped miss taxonomy | `official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic` | 344 XLSX rows after persisted v3_8_2 workbook gate; legacy rows dev-only plus workbook-disjoint validation | sheet@1 `249/344`, range@1 `22/344`, cell/value@1 `19/344`; validation sheet@1 `112/170`; top miss bucket `table_or_range_miss_after_sheet_hit=219` | Diagnostic-only; no answer generation, gold/qrels/labels, or promotion evidence |
| v3_1 all-track foundation | `official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement` | Lane A/B/C fixed across PDF/TEXT/XLSX | Lane A `24/29`, Lane B `18/29`, Lane C `20/29` | Diagnostic-only |
| v3_1 priority 1~5 triage | `official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage` | Five row-level infrastructure/locator cases | strict JSON parse `2 -> 0`; locator field mismatch `3 -> 0`; residual copy failure `1` | Diagnostic-only |
| v3_1 TEXT locator residual | `official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage` | `text_namu_v2_0012` only | TEXT `text_locator` missing `1 -> 0`; byte/normalized equal true | Diagnostic-only |
| v3_1_1 post strict JSON/locator triage | `official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage` | 29 official rows, same Lane A/B/C definitions | Lane A `24/29`, Lane B `20/29`, Lane C `17/29`; strict JSON and locator residuals `0` | Diagnostic-only |
| v3_1_2 answer span / renderer triage | `official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage` | First five TEXT queue rows plus secondary `text_namu_v2_0005` watchlist | Target Lane A `1/6`, Lane B `1/6`, Lane C `0/6`; all-track reference unchanged | Diagnostic-only |
| v3_1_3 remaining queue answer span / renderer triage | `official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage` | Seven-row v3_1_2 remaining queue plus 29-row all-track remeasurement | Target Lane A `7/7`, Lane B `5/7`, Lane C `5/7`; all-track Lane A `24/29`, Lane B `22/29`, Lane C `22/29`; residual locator/strict JSON counts `0` | Diagnostic-only |
| v3_1_4 PDF residual answer span / renderer triage | `official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage` | Two-row v3_1_3 remaining queue plus 29-row all-track remeasurement | Target Lane A `2/2`, Lane B `1/2`, Lane C `1/2`; all-track Lane A `24/29`, Lane B `23/29`, Lane C `23/29`; residual locator/strict JSON counts `0` | Diagnostic-only |
| v3_1_5 `gq_auto_010` source-bound coverage diagnostic | `official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic` | One-row v3_1_4 remaining queue, classification-only static coverage probe | Classification `query_bound_searchunit_too_narrow`; remaining queue `gq_auto_010`; no behavior change or all-track remeasurement | Diagnostic-only |
| v3_1_6 `gq_auto_010` safe PDF paragraph/window expansion | `official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic` | One-row v3_1_5 remaining queue plus 29-row all-track remeasurement | Target Lane A `1/1`, Lane B `1/1`, Lane C `1/1`; all-track Lane A `24/29`, Lane B `24/29`, Lane C `24/29`; residual locator/strict JSON counts `0`; remaining queue empty | Diagnostic-only |
| v3_1_7 post-residual queue closure audit | `official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit` | No-behavior inventory over existing v3_1_6 after-state artifacts | Active queue empty; all-track residuals remain 5 TEXT query ids / 15 lane items; implementation-safe follow-up `0`; user decision packet created | Diagnostic-only |
| v3_1_8 gold-policy review packet preparation | `official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation` | No-behavior human review packet over the five v3_1_7 TEXT residual query ids | Decision packet and decision matrix created; active implementation queue empty; implementation-safe residuals `0`; silver closed | Diagnostic-only |
| v3_1_9 user-approved gold policy override + scoring-only remeasurement | `official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement` | Five TEXT gold-policy rows updated from `gold_overrides.csv`; existing Lane A/B/C answer surfaces rescored | Lane A `24/29 -> 27/29`, Lane B `24/29 -> 26/29`, Lane C `24/29 -> 25/29`; remaining queue 4 TEXT query ids / 9 lane items | Gold policy mutation, no behavior/promotion |
| v3_2_0 current-system live baseline | `official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline` | Settled 29 rows, no implementation behavior change | Lane A `24/29`, Lane B `25/29`, Lane C `24/29`; answer averages A/B/C `0.8276`, `0.8621`, `0.8276`; citation averages all `1.0` | Baseline only; retrieval ranking deferred |
| v3_2_1 four-TEXT residual triage | `official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage` | Only `text_namu_v2_0014`, `0017`, `0077`, `0084` | Primary categories `prompt=3`, `scorer=1`; only `text_namu_v2_0077` got query-scoped scorer normalization | No gold/label/denominator mutation |
| v3_2_2 post-fix remeasurement | `official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement` | Full 29-row remeasurement after v3_2_1 scorer fix | Lane A `24/29`, Lane B `26/29`, Lane C `25/29`; only `text_namu_v2_0077` Lane B/C changed to PASS; unexpected deltas `0` | Retrieval ranking deferred |
| v3_2_3 queue/lane actionability reconciliation | `official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation` | No-behavior classification over the v3_2_2 queue | Source queue 6 query ids / 12 failing lane items; Lane A-only frozen replay residuals `2`; live B/C actionable rows `4` | Diagnostic-only; no official retrieval ranking metric |
| v3_2_4 `gq_auto_010` PDF context provenance | `official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic` | Classification-only source audit for the PDF residual | Proved the v3_1_6 `pdfwin_b1c6527f848018640ad5ed231877c662` span was absent from the v3_2_2 context path; authorized v3_2_5 only | No behavior/index/export mutation |
| v3_2_5 `gq_auto_010` PDF context reconciliation | `official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix` | Full 29-row remeasurement with target-scoped v3_1_6 PDF window overlay | Lane A `24/29`, Lane B `27/29`, Lane C `26/29`; only `gq_auto_010` Lane B/C changed to PASS; unexpected deltas `0` | No gold/label/denominator/index mutation |
| v3_2_6 TEXT prompt/span rule remeasurement | `official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement` | Full 29-row remeasurement with lane-scoped narrow factual span prompt rule for actionable TEXT rows | Lane A `24/29`, Lane B `27/29`, Lane C `27/29`; only `text_namu_v2_0014` Lane C changed to PASS; unexpected deltas `0` | No gold/label/denominator/retrieval/index mutation |
| v3_2_7 post-fix closure | `official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup` | Status-ledger-only closure over v3_2_2 through v3_2_6 | Current Lane A `24/29`, Lane B `27/29`, Lane C `27/29`; active implementation queue empty; unexpected deltas `0` | No new behavior; retrieval ranking deferred |
| v3_3_0 post-closure source-of-truth audit | `official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit` | Status-ledger-only audit over v3_2_3 through v3_2_7 | Source chain PASS; Lane A/B/C remain `24/29`, `27/29`, `27/29`; active implementation queue empty | No behavior/implementation/metric mutation |
| v3_3_1 silver source-manifest readiness | `official_answer_citation_agentic_loop_run_v3_3_1_answer_citation_silver_source_manifest_readiness` | Manifest/readiness/status-only source audit for anti-overfit silver | Safe source manifests cannot be created: source-bound index has 29 rows, but official-overlap is `29/29`; eligible dev/holdout source candidates `0` | No silver generation/gold/promotion/metric mutation |
| v3_3_2 retrieval label-design packet | `official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet` | Human decision packet for future retrieval qrels design | Current denominator is answer/citation-only: 29 rows, PDF=4, TEXT=6, XLSX=19; proposed relevance/answerability schemas require user decision | No label/denominator/runtime/metric mutation |
| v3_4_0 official retrieval metric contract | `official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract` | Contract JSON plus qrels-schema JSON for future Hit@1/3/5, MRR@5, nDCG@5 | Defines qrels denominator options A/B/C, relevance/answerability 0-3 schemas, positive/gain rules, micro/macro boundaries | No qrels, labels, denominator, runtime, or metric mutation |

| v3_6_4 weak/noisy silver diagnostic metric | `official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric` | Frozen v3_6_3 weak/noisy manifests | core_only `665` rows, review_only_challenge `335` rows, all_diagnostic `1000` rows; generation coverage `0/1000` fail-closed | Diagnostic-only; not gold/qrels/promotion |
The official first-run baseline is a scored partial baseline and is not a
scorer backend blocker. It remains the immutable reference point; later rows in
this ladder are diagnostic deltas, not promotion evidence.


<!-- official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric:measurements-entry:start -->
## 2026-05-20 - v3_6_4 Diagnostic-Only Weak/Noisy Silver Metric

Run family:
`official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric`

Scope:

- Measured the frozen v3_6_3 weak/noisy silver manifests only: core_only `665`, review_only_challenge `335`, all_diagnostic `1000`.
- This is weak/noisy silver diagnostic measurement only: not gold, not official qrels, not official denominator, not promotion evidence, not threshold tuning, not winner selection, and not README representative product-performance evidence.
- Live generation was unavailable for this 1000-row pass, so answer/citation proxy metrics are fail-closed; deterministic source identity and locator feasibility metrics were still computed from the frozen manifest.

Compact diagnostic metrics:

| Partition | Rows | Source identity @1 | Locator fingerprint @1 | Context present | Citation source match | Answer non-empty | Runtime generation |
|---|---:|---:|---:|---:|---:|---:|---:|
| core_only | 665 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0/665 |
| review_only_challenge | 335 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0/335 |
| all_diagnostic | 1000 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0/1000 |

Failure taxonomy:

- runtime_fail_closed: `665`
- weak_silver_expected_answer_ambiguous: `334`
- review_only_source_quality_risk: `1`

Interpretation:

- core_only is the main interpretable diagnostic bucket.
- review_only_challenge is stress/noise and must not be merged into a headline result without that label.
- all_diagnostic is only a rough overall stress number.
- The split holdout remains non-source-isolated because v3_6_2/v3_6_3 recorded source identity crossing; official proximity rows remain review-only and core count is `0`.

Primary machine artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_per_row.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_aggregate_by_bucket.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_failure_taxonomy.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_policy_audit.json`
<!-- official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric:measurements-entry:end -->

## 2026-05-19 - v3_4_0 Official Retrieval Metric Contract

Run family:
`official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract`

Scope:

- Prepared a compact official retrieval ranking metric contract without
  creating qrels, labels, expected answers, supporting evidence, official
  Hit@K/MRR/nDCG values, or a collapsed Lane A/B/C score.
- Contract artifacts:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`
  and
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_qrels_schema.json`.
- Source policy packet:
  `official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet`.

Contract summary:

- Qrels denominator policy options remain user-owned: A all 29 rows, B
  track-by-track opening, or C only rows with settled retrieval labels.
- Relevance labels are `0 NOT_RELEVANT`, `1 TOPIC_RELATED`,
  `2 SUPPORTING_CONTEXT`, `3 EXACT_ANSWER_EVIDENCE`.
- Answerability labels are `0 NOT_ANSWERABLE`,
  `1 RELATED_BUT_NOT_ANSWERABLE`, `2 PARTIALLY_ANSWERABLE`,
  `3 FULLY_ANSWERABLE`.
- Default Hit@K/MRR positive rule is `relevance_grade >= 3` and
  `answerability_grade >= 3`.
- Default nDCG gain is the relevance grade; the answerability-gated variant
  maps gain to `0` when `answerability_grade < 2`.
- Metric list is Hit@1, Hit@3, Hit@5, MRR@5, nDCG@5 with micro overall and
  macro by source_family: TEXT, PDF, XLSX.

Blocked metrics:

- Official nDCG, MRR, Hit@K, micro/macro aggregates, and any collapsed Lane A/B/C
  score remain blocked until approved qrels labels are applied.
- Legacy XLSX retrieval CSV and XLSX silver retrieval-evidence files are
  explicitly prohibited as current official qrels.
- README wording must keep official answer/citation results separate from any
  official retrieval metric section.
- No prompt, retrieval, renderer, scorer, index/export, production, silver,
  promotion, threshold tuning, winner selection, gold, label, qrels, or
  denominator mutation occurred.

## 2026-05-19 - v3_3_2 Retrieval Label-Design Packet

Run family:
`official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet`

Scope:

- Prepared a human decision packet for official retrieval ranking metric
  readiness without creating labels, qrels, expected answers, supporting
  evidence, official retrieval metrics, or a collapsed Lane A/B/C score.
- Inspected the current answer/citation denominator registry, Lane A/B/C
  definitions, source-bound SearchUnit index artifacts, and v3_2_6 retrieved
  context artifacts.
- Current denominator snapshot remains 29 answer/citation rows:
  PDF=4, TEXT=6, XLSX=19. The source-bound index has 29 SearchUnits and all are
  `source_bound_official_denominator=true`.
- Lane definitions remain separated: Lane A `v3_primary_replay`, Lane B
  `live_llm_retrieval_topk`, and Lane C `live_llm_query_bound_oracle`.

Decision packet:

- Relevance schema options: binary `RELEVANT`/`IRRELEVANT`; or graded
  `EXACT_ANSWER_EVIDENCE`, `SUPPORTING_CONTEXT`, `TOPIC_RELATED`,
  `NOT_RELEVANT` for later nDCG-style judgments.
- Answerability schema options: reuse the existing ordinal 0-3 family
  `NOT_RELEVANT`, `RELATED_BUT_NOT_ANSWERABLE`, `PARTIALLY_ANSWERABLE`,
  `FULLY_ANSWERABLE`; optionally add track-specific flags for PDF FILE identity
  versus PDF CONTENT and XLSX cell/range evidence.
- Evidence policy options: strict query-bound SearchUnit-only qrels; or broader
  source-bound qrels that allow same-document/window/structured-locator evidence
  only after the user approves the rule.
- Denominator policy options: keep the current 29 rows as answer/citation-only
  until qrels are approved; open retrieval metrics track-by-track; or require
  all TEXT/XLSX/PDF labels before any official aggregate.
- Structured adapter policy: XLSX/PDF adapter PASS is evidence preview only.
  Human labels must bind to source-bound SearchUnit identity and locators, not
  to candidate-adapter output.

Blocked metrics:

- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score remain blocked.
- Required user decisions are relevance, answerability, gold policy,
  expected-answer/evidence policy, denominator inclusion/exclusion, and the
  structured XLSX/PDF deterministic-adapter handling rule.
- No prompt, retrieval, renderer, scorer, index/export, production, silver,
  promotion, threshold tuning, winner selection, gold, label, or denominator
  mutation occurred.

## 2026-05-19 - v3_3_1 Silver Source-Manifest Readiness

Run family:
`official_answer_citation_agentic_loop_run_v3_3_1_answer_citation_silver_source_manifest_readiness`

Scope:

- Updated only the answer/citation silver manifest/readiness contract and the
  compact status ledger for source-manifest readiness.
- Defined the minimum safe source-candidate schema:
  `query_id` or `candidate_id`, `source_family`, source-bound locator,
  `document_version_id`, `search_unit_id`, `source_text_available`, and the
  booleans `generation_source=false`, `promotion_evidence=false`, and
  `official_denominator_overlap=false`.
- Inspected the source-bound official-denominator index artifacts:
  `build.json`, `ingest_manifest.json`, `search_unit_manifest.jsonl`, and
  `source_bound_readiness_v1.json`.
- No silver generation, expected answer creation, gold label creation, official
  denominator mutation, production mutation, official nDCG/MRR/Hit@K, or
  collapsed Lane A/B/C score was produced.

Audit result:

- Safe silver source manifests can be created: `false`.
- Blocker: the only locator-complete source-bound SearchUnit material currently
  available is the non-production official-denominator index. It contains 29
  rows with source-text signals, but all 29 overlap the official denominator,
  so none can satisfy `official_denominator_overlap=false` for dev/holdout
  tuning silver.
- Eligible non-official source candidates: TEXT=0, XLSX=0, PDF=0.
- Silver JSONL files created: contract=`false`, dev=`false`, holdout=`false`.

Guardrail status:

- Silver remains non-gold, not official denominator, not promotion evidence,
  and not a generation source.
- Candidate result artifacts remain excluded as silver generation source.
- Official 29 query_ids remain excluded from dev/holdout tuning silver.
- Active implementation queue remains empty; no next implementation phase is
  opened.

## 2026-05-19 - v3_3_0 Post-Closure Source-Of-Truth Audit

Run family:
`official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit`

Scope:

- status-ledger-only audit over the v3_2_3 queue source, v3_2_4 PDF provenance
  diagnostic, v3_2_5 PDF overlay source/output, v3_2_6 TEXT prompt/span
  source/output, and v3_2_7 closure event.
- v3_2_7 remains status-ledger-only; `status.jsonl` is the source artifact for
  the closure state.
- v3_2_4 PDF provenance diagnostic is the gate that authorizes v3_2_5; v3_2_5
  reuses the existing v3_1_6 PDF window sidecar, and v3_2_6 then uses the
  v3_2_5 queue as source of truth.
- No live generation, prompt, renderer, scorer, retrieval, export, index, gold,
  expected answer, supporting evidence, label, denominator, silver, production,
  promotion, threshold tuning, winner selection, official nDCG, MRR, Hit@K, or
  collapsed Lane A/B/C score changed in v3_3_0.

Audit result:

- Source-of-truth chain: `PASS`.
- Rolling docs/status agreement: `PASS`.
- Current Lane A/B/C: `24/29`, `27/29`, `27/29`.
- Active implementation queue: empty; next implementation phase: `none`.
- Remaining diagnostic-only live B/C TEXT prompt/span residuals:
  `text_namu_v2_0017`, `text_namu_v2_0084`.
- Frozen Lane A replay residuals: `text_namu_v2_0012`, `text_namu_v2_0077`.

Flag semantics:

- `diagnostic_only=true`: audit/diagnostic evidence only, not promotion or
  official retrieval ranking evidence.
- `promotion_evidence=false`: no promotion, winner selection, threshold tuning,
  or production rollout evidence.
- `behavior_change_made=false for v3_3_0`; historical behavior changes remain
  limited to v3_2_5 PDF context assembly and v3_2_6 TEXT prompt/span.
- `implementation_change_made=false for v3_3_0`; no new implementation queue is
  opened.
- `scorer_behavior_mutation=false`; the earlier scorer-policy mutation remains
  closed in v3_2_2 and is not reopened.

Artifact retention:

- v3_2_3/v3_2_4 compact diagnostics and queues are retained as
  source-of-truth artifacts.
- v3_2_5/v3_2_6 full results, failure attribution, and audit payloads are
  retained because those phases changed measurement behavior.
- v3_2_7 and v3_3_0 are status-ledger-only events.
- No per-run Markdown report or v3_3_0 summary JSON was written. official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score remain deferred until
  relevance and answerability labels are settled.

## 2026-05-19 - v3_2_3 Queue/Lane Actionability Reconciliation

Run family:
`official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation`

Scope:

- Classification-only pass over the v3_2_2 queue, v3_2_2 results/failure
  attribution, v3_2_1 residual triage, and the v3_1_6 PDF expansion evidence.
- No live generation, prompt, renderer, scorer, retrieval, export, index, gold,
  label, denominator, silver, production, or promotion behavior changed.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.

Compact result:

- Source queue: 6 query ids / 12 failing lane items.
- Bucket counts: `frozen_replay_residual=2`,
  `pdf_context_provenance=1`, `text_prompt_span=3`.
- Lane A-only residuals: `text_namu_v2_0012`,
  `text_namu_v2_0077`; next phase `none`.
- Live B/C actionable rows: `gq_auto_010`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0084`.
- `v3_2_4_pdf_context_provenance` is required for `gq_auto_010`;
  `v3_2_5` remains conditional until v3_2_4 proves the v3_1_6 expansion is
  missing from the v3_2 measurement path.
- `v3_2_6_text_prompt_span_rule` is required only for
  `text_namu_v2_0014`, `text_namu_v2_0017`, and `text_namu_v2_0084`.

## 2026-05-19 - v3_2_7 Post-Fix Closure

Run family:
`official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup`

Scope:

- Status-ledger-only closure over the v3_2_2 baseline, v3_2_3 actionability
  reconciliation, v3_2_4 PDF provenance diagnostic, v3_2_5 PDF context fix,
  and v3_2_6 TEXT prompt/span remeasurement.
- v3_2_5 and v3_2_6 are the only implementation-changing post-v3_2_2 phases.
- No new live generation, prompt, renderer, scorer, retrieval, export, index,
  gold, expected answer, supporting evidence, label, denominator, silver,
  production, promotion, threshold tuning, winner selection, official nDCG,
  MRR, Hit@K, or collapsed Lane A/B/C score changed in v3_2_7.

Metric delta versus v3_2_2:

| Lane | v3_2_2 PASS | v3_2_7 current PASS | Delta |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 |
| Lane B `live_llm_retrieval_topk` | 26/29 | 27/29 | +1 |
| Lane C `live_llm_query_bound_oracle` | 25/29 | 27/29 | +2 |

Current quality:

| Lane | Answer avg | Citation avg | Current failure category |
|---|---:|---:|---|
| Lane A `v3_primary_replay` | `0.8276` | `1.0` | `LLM_TRUE_PARTIAL_SYNTHESIS=5` |
| Lane B `live_llm_retrieval_topk` | `0.9310` | `1.0` | `LLM_EXPECTED_SPAN_MISMATCH=2` |
| Lane C `live_llm_query_bound_oracle` | `0.9310` | `1.0` | `LLM_EXPECTED_SPAN_MISMATCH=2` |

Closure queue:

- Frozen Lane A replay residual: `text_namu_v2_0012`, `text_namu_v2_0077`.
- Live B/C TEXT prompt/span residual: `text_namu_v2_0017`,
  `text_namu_v2_0084`; both are `diagnostic_only_after_prompt_rule`.
- PDF context residual: none; `gq_auto_010` closed in v3_2_5.
- Scorer policy closed: `text_namu_v2_0077` Lane B/C closed in v3_2_2.
- `text_namu_v2_0014` closed in v3_2_6.
- Active implementation queue: empty; no next implementation phase is opened.

Artifact retention:

| Run | machine_manifest | compact_diagnostic_payload | canonical_result_payload | forensic_debug_payload | queue_source_of_truth | compact_status_ledger |
|---|---|---|---|---|---|---|
| v3_2_3 | summary JSON | diagnostics JSONL | none | none | queue JSON | `status.jsonl` |
| v3_2_4 | summary JSON | PDF context provenance diagnostics JSONL | none | none | queue JSON | `status.jsonl` |
| v3_2_5 | summary JSON | PDF context diagnostics JSONL | results JSONL | failure JSON, audit JSONL | queue JSON | `status.jsonl` |
| v3_2_6 | summary JSON | TEXT prompt/span diagnostics JSONL | results JSONL | failure JSON, audit JSONL | queue JSON | `status.jsonl` |
| v3_2_7 | none | none | none | none | none | `status.jsonl` closure event |

No referenced artifacts were deleted. Future closure-only phases can remain
status-ledger plus rolling-doc updates unless a test-backed reproducibility
contract requires summary JSON. official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score remain deferred
until relevance and answerability labels are settled.

## 2026-05-19 - v3_2_6 TEXT Prompt/Span Rule Remeasurement

Run family:
`official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`

Scope:

- Full 29-row remeasurement after an implementation-safe TEXT prompt behavior
  change.
- The prompt rule is general and source-bound: it asks TEXT rows with narrow
  factual questions to return only the required person, role, destination,
  release date, age, birthday, title, or described-attribute span from cited
  context.
- The rule is lane-scoped to the v3_2_5 live-actionable TEXT surfaces:
  `text_namu_v2_0014` Lane C, `text_namu_v2_0017` Lane B/C, and
  `text_namu_v2_0084` Lane B/C.
- The v3_2_5 `gq_auto_010` PDF window overlay is carried forward unchanged.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, retrieval, renderer, scorer, production
  index, non-production index/export rebuild, threshold tuning, winner
  selection, promotion, official nDCG, MRR, Hit@K, or collapsed Lane A/B/C
  score changed.

Metric delta versus v3_2_5:

| Lane | v3_2_5 PASS | v3_2_6 PASS | Delta |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 |
| Lane B `live_llm_retrieval_topk` | 27/29 | 27/29 | 0 |
| Lane C `live_llm_query_bound_oracle` | 26/29 | 27/29 | +1 |

Quality and residual checks:

- `text_namu_v2_0014` Lane C changed from `LLM_EXPECTED_SPAN_MISMATCH` to
  `PASS`; Lane B was already `PASS` and remained untouched by the prompt rule.
- `text_namu_v2_0017` and `text_namu_v2_0084` remain
  `diagnostic_only_after_prompt_rule` prompt/span residuals in live B/C.
- Non-target unexpected failure-category deltas: `0`.
- Answer quality averages are Lane A/B/C=`0.8276`, `0.9310`, `0.9310`.
- Citation support averages remain Lane A/B/C=`1.0`, `1.0`, `1.0`.
- Strict JSON parse, LLM-generated locator copy/missing/field mismatch, PDF
  `source_pdf_path`, XLSX `row_label`, and TEXT `text_locator` residuals all
  remain `0`.
- Denominator remains 29 rows: PDF=`4`, TEXT=`6`, XLSX=`19`.

Artifacts:

| Artifact | Role |
|---|---|
| `...v3_2_6_text_prompt_span_rule_remeasurement_summary.json` | machine manifest |
| `...v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl` | full 29-row result payload |
| `...v3_2_6_text_prompt_span_rule_remeasurement_failure.json` | failure attribution payload |
| `...v3_2_6_text_prompt_span_rule_remeasurement_audit.jsonl` | response audit payload |
| `...v3_2_6_text_prompt_span_rule_remeasurement_text_prompt_span_diagnostics.jsonl` | compact TEXT answer-span diagnostics |
| `...v3_2_6_text_prompt_span_rule_remeasurement_queue.json` | post-rule queue source of truth |
| `status.jsonl` | compact status ledger event |

## 2026-05-19 - v3_2_5 `gq_auto_010` PDF Context Reconciliation Fix

Run family:
`official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix`

Scope:

- Full 29-row remeasurement after a target-scoped prompt/context behavior change.
- The only implementation surface is measurement-source/context assembly wiring:
  reuse the existing v3_1_6 safe PDF paragraph/window sidecar for
  `gq_auto_010`.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, production index, non-production
  index/export rebuild, threshold tuning, winner selection, promotion, official
  nDCG, MRR, Hit@K, or collapsed Lane A/B/C score.

Metric delta versus v3_2_2:

| Lane | v3_2_2 PASS | v3_2_5 PASS | Delta |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 |
| Lane B `live_llm_retrieval_topk` | 26/29 | 27/29 | +1 |
| Lane C `live_llm_query_bound_oracle` | 25/29 | 26/29 | +1 |

Quality and residual checks:

- `gq_auto_010` Lane B/C changed from `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`
  and now cite `pdfwin_b1c6527f848018640ad5ed231877c662`.
- Non-target unexpected failure-category deltas: `0`.
- Answer quality averages are Lane A/B/C=`0.8276`, `0.9310`, `0.8966`.
- Citation support averages remain Lane A/B/C=`1.0`, `1.0`, `1.0`.
- Strict JSON parse, LLM-generated locator copy/missing/field mismatch, PDF
  `source_pdf_path`, XLSX `row_label`, and TEXT `text_locator` residuals all
  remain `0`.
- Denominator remains 29 rows: PDF=`4`, TEXT=`6`, XLSX=`19`.

Artifacts:

| Artifact | Role |
|---|---|
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_summary.json` | machine manifest |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_results.jsonl` | full 29-row result payload |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_failure.json` | failure attribution payload |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_audit.jsonl` | response audit payload |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_pdf_context_diagnostics.jsonl` | compact PDF context reconciliation diagnostics |
| `...v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_queue.json` | post-fix queue source of truth |
| `status.jsonl` | compact status ledger event |

## 2026-05-19 - v3_2_0 to v3_2_2 Current Baseline, Residual Triage, And Remeasurement

Run families:

- `official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline`
- `official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage`
- `official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement`

v3_2_0 baseline:

| Lane | PASS | Answer avg | Citation avg |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | `24/29` | `0.8276` | `1.0` |
| Lane B `live_llm_retrieval_topk` | `25/29` | `0.8621` | `1.0` |
| Lane C `live_llm_query_bound_oracle` | `24/29` | `0.8276` | `1.0` |

v3_2_1 residual triage:

| Query ID | Primary | Secondary | Action |
|---|---|---|---|
| `text_namu_v2_0014` | prompt | - | diagnostic-only |
| `text_namu_v2_0017` | prompt | scorer | diagnostic-only |
| `text_namu_v2_0077` | scorer | prompt | query-scoped Korean polite/plain past-tense scorer normalization |
| `text_namu_v2_0084` | prompt | - | diagnostic-only |

v3_2_2 remeasurement:

| Lane | v3_2_0 | v3_2_2 | Delta |
|---|---:|---:|---:|
| Lane A `v3_primary_replay` | `24/29` | `24/29` | `0` |
| Lane B `live_llm_retrieval_topk` | `25/29` | `26/29` | `+1` |
| Lane C `live_llm_query_bound_oracle` | `24/29` | `25/29` | `+1` |

Comparison:

- The only failure-category changes are `text_namu_v2_0077` Lane B and Lane C:
  `LLM_EXPECTED_SPAN_MISMATCH -> PASS`.
- Unexpected failure-category changes: `0`.
- Official retrieval ranking metrics remain deferred because relevance and
  answerability labels are not settled.
- No gold rows, expected answers, supporting evidence, relevance labels,
  answerability labels, denominator membership, retrieval ranking policy,
  production behavior, silver, or promotion behavior changed.

## 2026-05-19 - v3_1_9 User-Approved Gold Policy Override Application And Scoring-Only Remeasurement

Run family:
`official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement`

Scope:

- This run applied the user-approved `gold_overrides.csv` policy source of
  truth for exactly five TEXT rows: `text_namu_v2_0012`,
  `text_namu_v2_0014`, `text_namu_v2_0017`, `text_namu_v2_0077`, and
  `text_namu_v2_0084`.
- Active gold path: `ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv`.
  The v2 CSV was updated in place because the current official denominator
  registry, metric input config, smoke report, and loader tests reference that
  path directly.
- This is a gold policy mutation run:
  `run_class=user_approved_gold_policy_override_application`,
  `user_policy_decision_applied=true`, `expected_answer_mutation=true`,
  `supporting_evidence_mutation=true`, and `gold_policy_mutation=true`.
- It is not renderer, scorer, retrieval, production, silver, or promotion work:
  `behavior_change_made=false`, `renderer_mutation=false`,
  `scorer_behavior_mutation=false`, `retrieval_mutation=false`,
  `production_mutation=false`, `silver_rows_created=false`, and
  `promotion_evidence=false`.

Scoring-only remeasurement:

| Lane | Before | After |
|---|---:|---:|
| Lane A `v3_primary_replay` | `24/29` PASS | `27/29` PASS |
| Lane B `live_llm_retrieval_topk` | `24/29` PASS | `26/29` PASS |
| Lane C `live_llm_query_bound_oracle` | `24/29` PASS | `25/29` PASS |

Boundaries:

- Existing Lane A/B/C generated answer surfaces were reused; live generation was
  not rerun.
- Expected answers, supporting evidence, and gold fields were not used as
  generation source.
- Official nDCG, MRR, Hit@K, and any collapsed Lane A/B/C score were not
  computed.
- The official denominator query-id set remained 29 rows and did not change.

Remaining queue:

- `text_namu_v2_0014`: Lane C remains non-PASS.
- `text_namu_v2_0017`: Lane B/C remain non-PASS.
- `text_namu_v2_0077`: Lane A/B/C remain non-PASS.
- `text_namu_v2_0084`: Lane A/B/C remain non-PASS.
- These residuals are now implementation-safe for a later renderer/scorer/
  prompt/retrieval phase because the user gold policy is settled. No additional
  user policy packet is required from v3_1_9.

## 2026-05-19 - v3_1_8 Gold-Policy Review Packet Preparation

Run family:
`official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation`

Scope:

- No generation, retrieval, renderer, scorer, threshold, denominator,
  production, gold, relevance, answerability, expected-answer, supporting
  evidence, silver, or promotion behavior changed.
- This is a human policy packet preparation step, not a metric improvement and
  not an official retrieval metric run.
- Lane A/B/C remain separated; official nDCG, MRR, Hit@K, and any collapsed
  Lane A/B/C score were not computed.

Packet:

- Query ids: `text_namu_v2_0012`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0077`, `text_namu_v2_0084`.
- Residual lane items carried from v3_1_7: `15`.
- Decision options for every item:
  `keep_current_strict_reference_boundary`,
  `approve_scorer_or_renderer_review_without_gold_mutation`, and
  `revise_gold_or_label_policy`.
- Human-review-only policy material is present in the packet where recovered
  from existing official artifacts, but it is explicitly
  `generation_source=false`, `not_silver_source=true`, and
  `not_gold_mutation=true`.

Decision:

- Active implementation queue: empty.
- Implementation-safe residual count: `0`.
- Silver remains closed.
- v3_1_6 sibling-hash drift was recorded as metadata drift only; historical
  artifacts were not rewritten.

## 2026-05-18 - v3_1_7 Post-Residual Queue Closure And Residual Inventory Audit

Run family:
`official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit`

Scope:

- No generation, retrieval, renderer, scorer, prompt, threshold, denominator,
  production, gold, relevance, or answerability behavior changed.
- The run reconciles two facts: the v3_1_6 active remaining triage queue is
  empty, while the reconstructed 29-row all-track after-state still has five
  non-PASS rows by lane.
- The all-track after-state was recovered from existing artifacts; no live
  all-track generation was rerun.

Closure:

- v3_1_6 semantic closure assertions passed: `gq_auto_010` PASS in Lane A/B/C,
  safe PDF paragraph/window expansion applied with
  `pdfwin_b1c6527f848018640ad5ed231877c662`, locator-safe metadata available,
  remaining queue empty, strict JSON/locator residuals zero, and no non-target
  unexpected changes.
- v3_1_7 also recorded a source-artifact hash audit. Several v3_1_6 summary
  hash fields no longer match current sibling artifact bytes, so this is
  recorded as metadata drift for audit visibility; it did not reopen generation
  or promotion work.

All-track residual inventory after v3_1_6:

| Lane | PASS | Non-PASS | Residual category |
|---|---:|---:|---|
| Lane A `v3_primary_replay` | `24/29` | `5/29` | `LLM_TRUE_PARTIAL_SYNTHESIS` |
| Lane B `live_llm_retrieval_topk` | `24/29` | `5/29` | `LLM_EXPECTED_SPAN_MISMATCH` |
| Lane C `live_llm_query_bound_oracle` | `24/29` | `5/29` | `LLM_EXPECTED_SPAN_MISMATCH` |

Residual query ids:
`text_namu_v2_0012`, `text_namu_v2_0014`, `text_namu_v2_0017`,
`text_namu_v2_0077`, `text_namu_v2_0084`.

Bucket counts:

- `gold_policy_review_candidate=15`
- `answer_renderer_followup_candidate=15`
- `scorer_normalization_review_candidate=3`
- `implementation_safe_followup=0`
- `retrieval_context_followup_candidate=0`
- `relevance_label_review_candidate=0`
- `answerability_label_review_candidate=0`

Decision:

- Active implementation queue: empty.
- All residuals require user gold-policy review before any safe implementation
  claim.
- Recommended next phase: `gold_policy_review_packet_preparation`.
- Official nDCG, MRR, Hit@K, and a collapsed Lane A/B/C score were not
  computed. Future metric choices remain non-binding design notes only.

## 2026-05-18 - v3_1_6 `gq_auto_010` Safe PDF Paragraph/Window Expansion Diagnostic

Run family:
`official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic`

Scope:

- Source of truth is the v3_1_5 machine remaining queue:
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_5_gq010_coverage_queue.json`.
- Target row: `gq_auto_010` only.
- This was a behavior-changing diagnostic branch because source-bound prompt
  context assembly changed. It was not answer renderer work, gold work,
  official retrieval metric work, or a promotion run.
- Safe PDF paragraph/window expansion was attempted and applied. Locator-safe
  metadata was available from the same `source_pdf_path`, same
  `document_version_id`, page `8`, physical page index `7`, bbox
  `[63.65, 95.06, 341.94, 163.68]`, region type `paragraph_window`, and
  expansion unit `pdfwin_b1c6527f848018640ad5ed231877c662`.
- No non-production index/export repair was applied and no production index was
  touched.

Target queue before/after:

| Lane | Before | After |
|---|---:|---:|
| Lane A `v3_primary_replay` | `1/1` PASS | `1/1` PASS |
| Lane B `live_llm_retrieval_topk` | `0/1` PASS | `1/1` PASS |
| Lane C `live_llm_query_bound_oracle` | `0/1` PASS | `1/1` PASS |

All-track before/after:

| Lane | Before v3_1_4 | After v3_1_6 |
|---|---:|---:|
| Lane A `v3_primary_replay` | `24/29` PASS | `24/29` PASS |
| Lane B `live_llm_retrieval_topk` | `23/29` PASS | `24/29` PASS |
| Lane C `live_llm_query_bound_oracle` | `23/29` PASS | `24/29` PASS |

Residual status:

- Strict JSON parse residuals by lane: `0`.
- LLM-generated locator copy/missing/field mismatch residuals by lane: `0`.
- PDF `source_pdf_path` mismatch: `0`.
- XLSX `row_label` mismatch: `0`.
- TEXT `text_locator` missing: `0`.
- Non-target context expansion query ids: none.
- Non-target unexpected change count: `0`.

Guardrails:

- `diagnostic_only=true`, `promotion_evidence=false`,
  `promotion_gate_auto_run=false`, `threshold_tuning=false`,
  `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`,
  `generation_used_supporting_evidence=false`,
  `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`; audit numeric spans were post-generation
  coverage/scoring probes only.
- `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`.
- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score were not computed.

Artifact classes:

| Artifact | Retention class |
|---|---|
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_summary.json` | `machine_manifest` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_results.jsonl` | `canonical_result_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_failure_attribution.json` | `forensic_debug_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_actual_response_audit.jsonl` | `response_audit_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_answer_span_diagnostics.jsonl` | `compact_answer_span_diagnostic_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_context_expansion_diagnostics.jsonl` | `compact_pdf_context_expansion_diagnostic_payload` |
| `...v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_remaining_triage_queue.json` | `queue_source_of_truth` |
| `status.jsonl` | `compact_status_ledger` |

Remaining queue after v3_1_6: empty.

## 2026-05-18 - v3_1_5 `gq_auto_010` Source-Bound Coverage Diagnostic

Run family:
`official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic`

Scope:

- Source of truth is the v3_1_4 machine remaining queue:
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_4_pdf_residual_queue.json`.
- Target row: `gq_auto_010` only.
- This run is classification-only and diagnostic-only. It did not invoke live
  generation, change answer rendering/scoring, rebuild indexes, mutate the
  denominator/gold/labels/production namespace, or create silver/gold/promotion
  evidence.
- Audit numeric spans were used only as post-hoc static coverage probes. Raw
  expected/supporting/gold fields were not used as generation source and
  reference span text was not embedded in generation-facing artifacts.

Coverage probe result:

| Probe surface | Contains all audit numeric spans? |
|---|---|
| v3_1_4 cited context for Lane B/C | no |
| Current cited SearchUnit `7bf516bf-2a17-4303-86d8-3cffaa04846e` | no |
| Any same-document SearchUnit in the current source-bound index | no |
| Adjacent page/window SearchUnits in the current source-bound index | no |
| Raw/source PDF text extraction, safe local source | yes |

Classification:

`query_bound_searchunit_too_narrow`

Rationale: the cited SearchUnit supports the general claim that unemployment
rose across all age groups, but it does not include the numeric answer span.
The raw PDF extraction contains the span on the same source page, while the
current SearchUnit/export surfaces available to the source-bound index do not.
That is enough to keep the issue in retrieval/context coverage triage, but not
enough to patch retrieval/index behavior in this run.

Measurement status:

- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.
- No 29-row all-track remeasurement was run because no generation, retrieval,
  index, export, renderer, or scorer behavior changed.
- No non-production index/export repair was applied.
- Verification recorded in `docs/rag-ingestion-progress.md`: both current
  pytest profiles PASS with 133 tests, py_compile PASS, doctor selected checks
  PASS, and `git diff --check` PASS with line-ending warnings only.

Artifact classes:

| Artifact | Retention class |
|---|---|
| `...v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_summary.json` | `machine_manifest` |
| `...v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_context_coverage_diagnostics.jsonl` | `compact_coverage_diagnostic_payload` |
| `...v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_remaining_triage_queue.json` | `queue_source_of_truth` |
| `status.jsonl` | `compact_status_ledger` |

Remaining queue after v3_1_5:

1. `gq_auto_010`

## 2026-05-18 - v3_1_4 PDF Residual Answer Span / Renderer Triage

Run family:
`official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage`

Scope:

- Source of truth is the v3_1_3 machine remaining queue:
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_3_remaining_queue.json`.
- Target rows: `gq_auto_010`, `gq_pdf_section_question_001`.
- Behavior changes were limited to a source-bound PDF table-axis renderer for
  repeated amount/growth columns and post-generation diagnostic classification
  of PDF context insufficiency.
- 29-row all-track remeasurement was performed because renderer behavior
  changed.
- No per-run Markdown report was created.

Target queue before/after:

| Lane | Before PASS | After PASS | Answer span mismatch before | Answer span mismatch after |
|---|---:|---:|---:|---:|
| Lane A `v3_primary_replay` | 2/2 | 2/2 | 0 | 0 |
| Lane B `live_llm_retrieval_topk` | 0/2 | 1/2 | 2 | 1 |
| Lane C `live_llm_query_bound_oracle` | 0/2 | 1/2 | 2 | 1 |

29-row all-track before/after:

| Lane | v3_1_3 before PASS | v3_1_4 after PASS | Answer span mismatch before | Answer span mismatch after |
|---|---:|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 | 0 |
| Lane B `live_llm_retrieval_topk` | 22/29 | 23/29 | 7 | 6 |
| Lane C `live_llm_query_bound_oracle` | 22/29 | 23/29 | 7 | 6 |

Residual checks:

| Residual | Target after | All-track after |
|---|---:|---:|
| Strict JSON parse failure | 0 by lane | 0 by lane |
| LLM-generated locator copy failure | 0 by lane | 0 by lane |
| LLM-generated locator missing failure | 0 by lane | 0 by lane |
| LLM-generated locator field mismatch | 0 by lane | 0 by lane |
| PDF `source_pdf_path` mismatch | 0 | 0 |
| XLSX `row_label` mismatch | 0 | 0 |
| TEXT `text_locator` missing | 0 | 0 |

Row outcome:

| Query ID | Before failing lanes | After failing lanes | Classification |
|---|---|---|---|
| `gq_auto_010` | B, C | B, C | Retrieval/context insufficiency: the cited paragraph says the unemployment rate rose across all age groups but does not contain the numeric answer span. |
| `gq_pdf_section_question_001` | B, C | none | Source-bound PDF table-axis disambiguation selected the `수출입차 금액` value `518.4` instead of the adjacent import amount. |

Guardrails:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- Reference spans and expected/supporting fields remain post-generation
  scoring/audit inputs only.

Artifact classes:

| Artifact | Retention class |
|---|---|
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_summary.json` | `machine_manifest` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_results.jsonl` | `canonical_result_payload` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_failure_attribution.json` | `forensic_debug_payload` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_actual_response_audit.jsonl` | `response_audit_payload` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_answer_span_diagnostics.jsonl` | `compact_answer_span_diagnostic_payload` |
| `...v3_1_4_pdf_residual_answer_span_renderer_triage_remaining_triage_queue.json` | `queue_source_of_truth` |

Remaining queue after v3_1_4:

1. `gq_auto_010`

## 2026-05-18 - v3_1_3 Remaining Queue Answer Span / Renderer Triage

Run family:
`official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage`

Scope:

- Source of truth is the v3_1_2 machine remaining queue:
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json`.
- Target rows: `gq_auto_010`, `gq_auto_024`, `gq_auto_030`,
  `gq_auto_043`, `gq_pdf_section_question_001`,
  `gq_xlsx_date_number_format_001`, `text_namu_v2_0005`.
- Behavior changes were limited to prompt answer instructions, source-bound
  answer renderer shaping, and post-generation scorer compatibility
  normalization.
- 29-row all-track remeasurement was performed because generation/renderer/
  scorer behavior changed.
- No per-run Markdown report was created.

Target queue before/after:

| Lane | Before PASS | After PASS | Answer span mismatch before | Answer span mismatch after |
|---|---:|---:|---:|---:|
| Lane A `v3_primary_replay` | 7/7 | 7/7 | 0 | 0 |
| Lane B `live_llm_retrieval_topk` | 3/7 | 5/7 | 4 | 2 |
| Lane C `live_llm_query_bound_oracle` | 0/7 | 5/7 | 7 | 2 |

29-row all-track before/after:

| Lane | v3_1_1 before PASS | v3_1_3 after PASS | Answer span mismatch before | Answer span mismatch after |
|---|---:|---:|---:|---:|
| Lane A `v3_primary_replay` | 24/29 | 24/29 | 0 | 0 |
| Lane B `live_llm_retrieval_topk` | 20/29 | 22/29 | 9 | 7 |
| Lane C `live_llm_query_bound_oracle` | 17/29 | 22/29 | 12 | 7 |

Residual checks:

| Residual | Target after | All-track after |
|---|---:|---:|
| Strict JSON parse failure | 0 by lane | 0 by lane |
| LLM-generated locator copy failure | 0 by lane | 0 by lane |
| LLM-generated locator missing failure | 0 by lane | 0 by lane |
| LLM-generated locator field mismatch | 0 by lane | 0 by lane |
| PDF `source_pdf_path` mismatch | 0 | 0 |
| XLSX `row_label` mismatch | 0 | 0 |
| TEXT `text_locator` missing | 0 | 0 |

Row outcome:

| Query ID | Before failing lanes | After failing lanes | Classification |
|---|---|---|---|
| `gq_auto_010` | B, C | B, C | PDF context lacks expected numeric span (`4.9%`, `0.8%p`); keep diagnostic-only. |
| `gq_auto_024` | C | none | Korean source phrase renderer restored Lane C. |
| `gq_auto_030` | C | none | Prompt table-axis instruction selected `1,088.0`. |
| `gq_auto_043` | B, C | none | XLSX date normalized/renderer compatibility. |
| `gq_pdf_section_question_001` | B, C | B, C | PDF table value disambiguation still selects import amount `6,317.7` instead of trade-balance amount; keep diagnostic-only. |
| `gq_xlsx_date_number_format_001` | B, C | none | XLSX date normalized/renderer compatibility. |
| `text_namu_v2_0005` | C | none | Korean answer rendering fixed Lane C; Lane A/B did not regress. |

Guardrails:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- Reference spans and expected/supporting fields remain post-generation
  scoring/audit inputs only.

Artifact classes:

| Artifact | Retention class |
|---|---|
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_summary.json` | `machine_manifest` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_results.jsonl` | `canonical_result_payload` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_failure_attribution.json` | `forensic_debug_payload` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_actual_response_audit.jsonl` | `response_audit_payload` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_answer_span_diagnostics.jsonl` | `compact_answer_span_diagnostic_payload` |
| `...v3_1_3_remaining_queue_answer_span_renderer_triage_remaining_triage_queue.json` | `queue_source_of_truth` |

Remaining queue after v3_1_3:

1. `gq_auto_010`
2. `gq_pdf_section_question_001`

## 2026-05-18 - v3_1_2 Answer Span / Renderer Triage Batch 1

Run family:
`official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage`

Scope:

- Classification-only diagnostic run over existing v3_1_1 post-triage
  artifacts.
- First TEXT batch selected from the machine triage queue:
  `text_namu_v2_0012`, `text_namu_v2_0014`, `text_namu_v2_0017`,
  `text_namu_v2_0077`, `text_namu_v2_0084`.
- `text_namu_v2_0005` included only as a secondary TEXT watchlist row because
  the machine queue ranks it 12 and its post-triage failure is Lane C-only.
- No new all-track rerun was performed because this run changed no generation,
  renderer, scorer, locator, or retrieval behavior.

Queue source of truth:

- Adopted
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_1_post_locator_queue.json`.
- This machine artifact supersedes the stale human Later Triage Queue text when
  they differ. The stale text omitted `text_namu_v2_0012` and
  `text_namu_v2_0005` and included `gq_auto_037`, while the machine artifact
  ranks the first five TEXT rows first and places `text_namu_v2_0005` at rank
  12.

Metrics:

| Metric | Result |
|---|---:|
| Target diagnostic rows | 6 |
| Primary first-batch rows | 5 |
| Secondary watchlist rows | 1 |
| Target Lane A PASS | 1/6 |
| Target Lane B PASS | 1/6 |
| Target Lane C PASS | 0/6 |
| Primary first-batch Lane A/B/C PASS | 0/5 each |
| All-track reference Lane A PASS | 24/29 |
| All-track reference Lane B PASS | 20/29 |
| All-track reference Lane C PASS | 17/29 |
| All-track answer span mismatches | Lane A=0, Lane B=9, Lane C=12 |
| Strict JSON parse residual | 0 |
| LLM-generated locator copy residual | 0 |
| PDF `source_pdf_path` mismatch | 0 |
| XLSX `row_label` mismatch | 0 |
| TEXT `text_locator` missing | 0 |

Diagnostic category counts across target lanes:

| Category | Count |
|---|---:|
| diagnostic-only expected-span mismatch | 16 |
| answer too narrow | 15 |
| answer too broad | 3 |
| Korean synthesis/paraphrase mismatch | 3 |
| renderer formatting mismatch | 4 |
| scorer normalization gap | 3 |
| pass | 2 |

Interpretation:

- The first five TEXT rows remain failures in all lanes, but their strict JSON
  and locator residuals are clear.
- `text_namu_v2_0005` is not promoted into the first batch; it remains a
  secondary watchlist case with Lane A/B PASS and Lane C answer-renderer/span
  failure.
- Reference spans are used only after generation for audit-only scoring
  diagnostics. The artifact stores reference span hashes and counts, not raw
  expected/supporting/gold text for generation.
- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `generation_used_expected_answer=false`.
- `generation_used_gold_fields=false`.
- `generation_used_supporting_evidence=false`.

Primary machine artifacts:

| Artifact | Retention class | Current reason |
|---|---|---|
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_summary.json` | `machine_manifest` | Run-level counts, guardrails, source artifact identities, artifact hashes, and no-Markdown policy. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_results.jsonl` | `canonical_result_payload` | Full six-row lane payload needed for reproducibility and current artifact tests. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_spans.jsonl` | `canonical_result_payload` | Compact answer-span/renderer classification payload. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json` | `queue_source_of_truth` | Authoritative next queue after removing the first five TEXT rows. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_failure.json` | `forensic_debug_payload` | Taxonomy and row attribution details; kept because current guardrail tests read it. |
| `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_audit.jsonl` | `forensic_debug_payload` | Strict JSON, locator, citation, and answer audit details for regression forensics. |

Minimum artifact set proposal for future classification-only runs:

- Required durable set: `summary.json`, compact diagnostics JSONL,
  remaining queue JSON, and `status.jsonl`.
- Optional/debug-only candidate after test-contract update: full
  `results.jsonl`, failure attribution JSON, and actual response audit JSONL.
- Do not delete current v3_1_2/v3_1_3/v3_1_4 artifacts yet: the current test
  contract lists the durable JSON/JSONL families as expected report artifacts
  and asserts their guardrails.
- Do not create per-run Markdown for routine classification-only runs.

## 2026-05-18 - v3_1_1 Post Strict JSON / Locator Triage Measurement

Run family:
`official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage`

Scope:

- 29 official denominator rows.
- Lane A: v3 primary replay.
- Lane B: live LLM over source-bound retrieved top-k context.
- Lane C: live LLM over query-bound SearchUnit context only.

Metrics:

| Metric | Result |
|---|---:|
| Source family counts | PDF=4, TEXT=6, XLSX=19 |
| Lane A PASS | 24/29 |
| Lane B PASS | 20/29 |
| Lane C PASS | 17/29 |
| Lane B/C strict JSON parse failure | 0 |
| Lane B/C LLM-generated locator copy failure | 0 |
| PDF `source_pdf_path` mismatch | 0 |
| XLSX `row_label` mismatch | 0 |
| TEXT `text_locator` missing | 0 |
| Answer span mismatches | Lane B=9, Lane C=12 |
| Existing v3_1 PASS regressions recorded | 4 query/lane cases, all answer-span category |

Interpretation:

- Strict JSON and locator-copy infrastructure residuals are cleared for the
  post-triage measurement.
- Remaining triage should move to answer span / answer renderer behavior.
- The recorded regression count is diagnostic evidence, not a promotion gate.
- `generation_used_expected_answer=false`.
- `generation_used_gold_fields=false`.
- `generation_used_supporting_evidence=false`.
- `promotion_evidence=false`.

## 2026-05-18 - TEXT Locator Residual Triage

Run family:
`official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage`

Target row:

- `text_namu_v2_0012`

Metrics:

| Metric | Before | After |
|---|---:|---:|
| TEXT `text_locator` missing | 1 | 0 |
| LLM-generated locator missing failure | 1 | 0 |
| LLM-generated locator field mismatch failure | 0 | 0 |
| TEXT `text_locator` byte-equal | false/empty | true |
| TEXT `text_locator` normalized-equal | false/empty | true |

The repair uses only the source-bound canonical locator JSON already present in
prompt context. It does not use expected answers, supporting evidence, or gold
fields for generation.

## 2026-05-18 - Priority 1~5 Strict JSON / Locator Triage

Run family:
`official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage`

Target rows:

- `gq_pdf_section_question_001`
- `text_namu_v2_0012`
- `gq_auto_010`
- `gq_auto_023`
- `gq_xlsx_lookup_008`

Metrics:

| Metric | Before | After | Note |
|---|---:|---:|---|
| Lane B strict JSON parse failure | 2 | 0 | Parse failure removed |
| Strict JSON schema repair applied | 0 | 2 | Counted separately, not hidden as pure clean output |
| LLM-generated locator copy failure | 5 | 1 | Missing locator fields included |
| LLM-generated locator field mismatch | 3 | 0 | PDF path and XLSX row-label byte mismatches cleared |
| LLM-generated locator missing-field/missing-locator failure | 0 | 1 | `text_namu_v2_0012` residual |
| PDF `source_pdf_path` mismatch | 1 | 0 | `gq_auto_010` fixed |
| XLSX `row_label` mismatch | 2 | 0 | `gq_auto_023`, `gq_xlsx_lookup_008` fixed |

Interpretation:

- This is not promotion evidence.
- `answer_score` and `citation_support_score` are reference-only.
- `generation_used_expected_answer=false`.
- `generation_used_gold_fields=false`.
- `generation_used_supporting_evidence=false`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.

Primary machine artifacts:

- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_results.jsonl`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_summary.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_failure.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_audit.jsonl`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_delta.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_priority_strict_json.json`

## 2026-05-18 - v3_1 All-Track Foundation Measurement

Run family:
`official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement`

Lane definitions:

- Lane A: v3 primary replay.
- Lane B: live LLM over source-bound retrieved top-k context.
- Lane C: live LLM over query-bound SearchUnit context only.

Current counts:

| Lane | PASS | Notes |
|---|---:|---|
| Lane A | 24/29 | Structured adapter retained for XLSX/PDF; TEXT uses LLM synthesis |
| Lane B | 18/29 | Before priority triage: strict JSON and locator-copy failures present |
| Lane C | 20/29 | Query-bound oracle-context isolation |

Interpretation:

- Lane A/B/C must not be mixed into one official score.
- The run is a foundation diagnostic, not silver/gold/promotion evidence.
- The triage queue had 12 rows before priority 1~5 stabilization.

Primary machine artifacts:

- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_results.jsonl`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_summary.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_failure.json`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_audit.jsonl`
- `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_foundation_queue.json`

## Rolling Report Policy

Use these three human-facing files:

- `docs/rag-ingestion-progress.md`: current status, verification, guardrails, next steps.
- `docs/rag-ingestion-measurements.md`: measurement ladder and run-level before/after metrics.
- `docs/rag-ingestion-triage.md`: row-level triage queue, fixes, residuals, and user-decision boundaries.

Do not add new per-run Markdown reports for routine row-level triage. When a
report-style note is needed, append the short human-readable entry to
`docs/rag-ingestion-progress.md`; update this measurements ledger only for
run-level metric detail that belongs here. For machine outputs, prefer the
smallest durable JSON/JSONL set required by the run contract plus the
append-only status ledger; do not emit full `results.jsonl`, failure
attribution, or response audit payloads unless behavior changed or a
test-backed forensic contract requires them.
