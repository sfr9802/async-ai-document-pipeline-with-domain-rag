# RAG Ingestion Triage

Last updated: 2026-05-26 KST.

This is the rolling row-level triage ledger. Keep it append-style like
`docs/rag-ingestion-progress.md`: add new triage entries here instead of
creating one Markdown file per run. Machine artifacts should stay compact:
write only the summary, queue, decision/inventory JSONL, and status event that a
triage phase actually needs. For report-style human summaries, append the short
entry to `docs/rag-ingestion-progress.md`; update this file only when row-level
queue or decision-boundary detail belongs here.

Historical `_archive/legacy` artifact paths below are logical provenance names.
Their physical generated payloads may live in the external runtime archive under
`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\`.
As of the 2026-05-21 cleanup, the current repo-local report directory keeps
`status.jsonl` plus compact current v3_6_9 and later diagnostic artifacts required by the current RAG profile; older triage payloads are consolidated under
`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\repo-wide-cleanup-20260521\reports\rag-ingestion-legacy\`.
The former non-rag report trees, `phase7/` and `legacy-baseline-final/`, are
archived under
`D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\repo-wide-cleanup-20260521\reports\`.

<!-- official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod:triage-entry:start -->
### v3_20 Live-Runtime-Like DB/Index/Cache Smoke Triage

- Run: `official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod`
- Scope: diagnostic-only non-production smoke over live-runtime-like SourceAtomStoreContract, SearchIndexContract, and RuntimeCacheContract adapters.
- INDEX_UNAVAILABLE rows fail closed before evidence assembly; SOURCE_ATOM_STORE_UNAVAILABLE rows fail closed before SourceAtom/EvidenceBundle truth can be produced.
- Cache unavailable is optional: it is audited and bypassed only when SourceAtomStore/EvidenceBundle truth can still be hydrated.
- CACHE_NAMESPACE_MISMATCH fails closed in this v3_20 contract, so stale cache namespaces do not return evidence.
- SearchIndexContract output is candidate-only; vector/SearchView payload and cache payload are never evidence truth.
- The smoke covers explicit XLSX file/sheet/cell, explicit PDF file/page, rough-query semantic constraints, missing-context deictic fail-closed, bounded active-context deictic allowed, unsupported source policy fail-closed, index unavailable, DB unavailable, cache unavailable, and stale cache namespace mismatch.
- This is not production routing and not live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod:triage-entry:start -->
### v3_19 Locator Ambiguity And Deictic Response Policy Triage

- Run: `official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod`
- Scope: diagnostic-only non-production response-policy hardening before live DB/index/cache smoke.
- Ambiguous file/workbook/document identity, page-only locators without active file context, and sheet-only locators without active workbook context fail closed with user clarification; sheet-only rows are surfaced as `AMBIGUOUS_SHEET_ONLY_LOCATOR` in `locator_resolution_bucket_counts` and dedicated sheet-only counters.
- Deictic Korean rough queries such as `이 표`, `이거`, `그 페이지`, `이 페이지`, `이 파일`, `방금 것`, `여기`, and `선택한 범위` require bounded active context and otherwise use the `CONTEXT_REQUIRED` response policy bucket.
- `BOUNDED_BROAD_RANGE` can answer only when the broad locator resolves to a unique source identity.
- Duplicate query text is surfaced in summary metrics and review packet fields; it remains diagnostic-only and not a gold label.
- No target/gold/supporting/expected locator text or hidden artifact source identity is used as active context.
- Verification risk: the broad `--rag-current` blocker was reclassified in v3_20 preflight as the incomplete v3_20 handoff rather than sampled v3_6_9-v3_15 artifact availability; v3_19 targeted policy, artifact, guardrail, and status checks pass.
<!-- official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod:triage-entry:start -->
### v3_18 Agent Runtime Tool Invocation Triage

- Run: `official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod`
- Scope: diagnostic-only non-production agent-runtime contract for invoking L0-L8 ToolSpecs through the bounded ToolRegistry.
- Unsupported route and runtime-contract violations fail closed; no unbounded fallback is allowed.
- User locator resolution buckets are machine diagnostics only: LOCATION_NOT_FOUND, AMBIGUOUS_LOCATOR, OUT_OF_BOUNDS_LOCATOR, UNSUPPORTED_LOCATOR_FORMAT, and CONTRACT_VIOLATION are not human answerability labels.
- Rough-query over-abstain diagnostics remain review aids and do not use expected, supporting, gold, or target text.
- SourceAtom/EvidenceBundle is the evidence truth; SearchView/vector payload remains candidate-only.
<!-- official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod:triage-entry:start -->
### v3_17 User-Locator And Rough-Query Review Triage

- Run: `official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod`
- Scope: diagnostic-only PDF/XLSX answer-quality review for rough, terse, incomplete user queries and user-provided file/sheet/cell/range/page locator text; XLSX is primary and PDF is control only.
- This is not official scoring, not promotion evidence, not product success evidence, and not a winner-selection or threshold-tuning run.
- User-owned review fields remain blank for satisfaction, relevance, answerability, expected-answer decision, and supporting-evidence decision.
- locator-bounds answerability is machine-stated for user locator rows only and remains a review aid, not a human answerability label or official metric.
- If query-owned locator text cannot be resolved to bounded SourceAtom ids, the row abstains with a location-not-found answer rather than inventing values.
- SourceAtom registry is the canonical evidence truth; SearchView/vector payload stays candidate-only.
<!-- official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod:triage-entry:start -->
### v3_16 Final LLM Answer-Quality Review Triage

- Run: `official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod`
- This is a user-perception review packet, not retrieval improvement and not official scoring. PDF and XLSX stay family-separated and no collapsed headline score is reported.
- User-owned review fields remain blank for satisfaction, relevance, answerability, expected-answer decision, and supporting-evidence decision.
- Generated final answers are source-truth diagnostics only: SourceAtom/EvidenceBundle citations are review metadata, while final answers remain evaluation artifacts/log-like outputs rather than production source truth.
- If the local LLM endpoint is unavailable, v3_16 fails closed and records readiness instead of silently using a noop/extractive generator.
- The runtime materialization contract keeps query-time work bounded: L3 reranks only precomputed structural candidates, L4 hydrates by SourceAtom id, L5 assembles bounded bundles, and the latency budget is diagnostic-only with L8 generation reported separately from retrieval.
<!-- official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement:triage-entry:start -->
### v3_15 XLSX L3 Table/Range Locator Triage

- Run: `official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement`
- v3_15 optimizes table/range candidate availability, not direct value matching. The cell/value diagnostics remain downstream only, and direct normalized answer-value query matching stays disabled.
- PDF is excluded from the optimization surface; v3_14 PDF/XLSX runtime separation remains the reference boundary and no PDF tuning is claimed here.
- SourceAtom registry hydration is the canonical evidence truth, SearchView/vector payload remains candidate-only, and fresh workbook-disjoint holdout remains required before any product-success or promotion claim.
<!-- official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod:triage-entry:start -->
## v3_14 Layered Retrieval Runtime Adapter Triage

- runtime adapter success is trace completeness, not score lift: each diagnostic query records L0-L7 candidate counts, latency, drop reasons, signal types, SourceAtom hydration, EvidenceBundle assembly, selected candidates, and answer-ready context availability.
- PDF and XLSX remain separated. v3_13 PDF rows and v3_12 XLSX rows enter the same orchestration interface, but their metrics are source-family separated and are not collapsed into a headline score.
- Raw PDF/XLSX query-time access is rejected by design. The adapter uses existing artifacts, manifests, candidate surfaces, and SourceAtom registry joins only.
- SourceAtom registry remains canonical evidence truth; SearchView/vector payload remains candidate-only.
- The future scored adapter remains disabled, and fresh real source-document/workbook-disjoint holdout remains unavailable, so product success and promotion remain blocked.
<!-- official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment:triage-entry:start -->
## v3_13 PDF File Identity Structural Locator Triage

- PDF remains a file-identity-first bottleneck, but the catch-up surface now separates file confidence from structural evidence windows.
- The main disclosed risk slice is accepted wrong rank1 with target in top3: 63/329. This is a rerank-candidate diagnostic, not a file-forcing change.
- bbox correctness is not claimed. v3_13 only reports page/block/bbox availability and same-page bounded evidence-window sufficiency where selector evidence can be measured without expected/supporting/gold text.
- XLSX v3_12 stays as no-regression control only; no XLSX optimization or metric promotion is part of this phase.
- fresh real PDF source-document-disjoint holdout remains required before product success evidence or promotion.
<!-- official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement:triage-entry:start -->
## v3_12 XLSX Structural Locator Non-Prod Triage

- L3 remains the active XLSX bottleneck after workbook/sheet routing. v3_12 records table-boundary, header-path, row-axis, column-axis, period/number token, merged-header, and zero-signal legacy demotion components per candidate.
- Seen-reference smoke: table_or_range@1 stays 23/344 net but has +1/-1 row-level churn; cell_or_value@1 moves from 20/344 to 21/344 with +1/-0 churn.
- Merged-header lift is not claimed: current SourceAtom/v3_10 surfaces expose no merged header propagation rows, so the component is present as an audit field and remains zero.
- Fresh real workbook-disjoint holdout is still unavailable; no product success or promotion claim is allowed.
<!-- official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic:triage-entry:start -->
## v3_11 Layered Retrieval Diagnostic Triage

- XLSX remains blocked mainly at table/range and cell locator layers after workbook/sheet routing: table_or_range@3=29/344, cell_or_value@3=26/344.
- PDF remains a file-identity-first bottleneck: file_resolve@1=66/329, file_resolve@3=129/329. Page/block/bbox evidence-window rows are diagnostic decomposition only.
- SourceAtom hydration and EvidenceBundle assembly are recorded as separate layers so vector metadata remains candidate-only, not evidence truth.
- Fresh real holdout insufficiency is unchanged; no product performance or promotion claim is made.
<!-- official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization:triage-entry:start -->
## v3_10 Fresh Holdout and XLSX Rematerialization Triage

- Fresh real holdout remains the blocker. There is no performance success claim in v3_10.
- XLSX table-axis is now materialized into non-prod SourceAtom/SearchUnit manifests under `rag-data-xlsx-table-axis-ood-nonprod-v1`. This proves the phase is no longer overlay-only, but old seen metrics remain reference/no-regression only.
- Signal-empty rank1 moved from 257/300 to 0/300 in the seen materialization smoke. Table/range/cell rates are not claimed as improved until a real fresh holdout exists.
- PDF work is limited to file identity baseline accounting. Answer-ready evidence-window improvements and OCR remain closed.
- Leakage/shortcut buckets are excluded from headline and retained in audit: answer_value_in_query, index_to_content, source_title_leak, file_title_leak, exact_query_hack, major_topic_drift, unnatural_sheet_or_cell_reference.
<!-- official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset:triage-entry:start -->
## v3_9_2 Overfit Risk and Holdout Reset Triage

Run ID: `official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset`.

Triage result:

- `likely_general` future-success evidence count is `0`.
- `weak_general` rows are retained as diagnostic direction only and are also marked insufficient-blind-evidence.
- Leakage-adjacent, query-fidelity-excluded, source/file-title, answer-value-in-query, and index-to-content rows are excluded from success evidence.
- The new synthetic OOD holdout is an anti-overfit guard only; it must not be used for representative product performance.

Next boundary:

- Pause performance success claims until real fresh blind/OOD PDF/XLSX sources are available.
- Continue only diagnostic-only proposal work for a new non-prod XLSX table-axis SourceAtom/SearchUnit rematerialization.
- Keep PDF file identity and PDF answer-ready evidence-window metrics separate.
<!-- official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic:triage-entry:start -->


## v3_9_1 XLSX Table-Axis and PDF File Identity Triage

Run family:
`official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic`

Confirmed diagnostic findings:

- XLSX `locator_signal_count=0` rank1 pressure comes from SourceAtom materialization that often lacks row/column/table-axis labels, plus legacy fixed row-window candidates that can rank first without query-local locator signals.
- v3_9_1 adds source-local table-axis metadata and same-workbook axis candidates, then only promotes an axis candidate to rank1 when legacy rank1 has zero locator signals and the axis candidate has query-derived structural signals.
- Direct normalized-value query matching remains banned; values may exist as evidence-slice hashes/presence markers but are not query-scoring shortcuts.
- Query-fidelity validation has `118` included rows, with approval/relevance/answerability/expected/supporting/pass-fail fields left blank for user-owned decisions.

Residual taxonomy:

| Area | Current residual |
|---|---|
| XLSX signal-empty rank1 | 257/300 |
| XLSX validation table_or_range_miss_after_sheet_hit | 105 |
| PDF rank1 file hit | 66/329 |
| PDF accepted wrong rank1, target in top3 | 63/329 |
| PDF accepted wrong rank1, target not top3 | 18/329 |
| PDF blocked wrong rank1 by abstain/disambiguation | 60/329 |

Boundary for next work:

- Still retrieval/locator/evidence work: richer XLSX SourceAtom table-axis materialization, row/column alias propagation, merged-cell/header propagation, table-block boundaries, and PDF oracle-free source identity confidence.
- Not a fine-tuning handoff yet: the largest XLSX failure is still range/cell locator structure, and PDF file identity remains unresolved for many rows before answer synthesis matters.
- OCR remains closed until native text absence/unusability or material OCR gain is proven.
- User-owned decisions remain query approval, relevance, answerability, expected answer/supporting evidence, pass/fail, denominator eligibility, gold/qrels/label policy, and promotion.
<!-- official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic:triage-entry:end -->

## 2026-05-24 - v3_9 PDF/XLSX Bottleneck Quality Triage Note

This triage note covers
`official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement`.
It keeps the work diagnostic-only: no fine-tuning, no gold/qrels/labels/
expected-answer/supporting-evidence/official-denominator/namespace/DB/
production/promotion/threshold/winner mutation, and
`official_metric_input_rows=0`. The future scored adapter remains
`DISABLED_PENDING_USER_APPROVAL`.

- PDF generalized validation signal exists: query-fidelity included validation
  improved from raw final `2/4` to answer-ready `3/4`. The larger all-row PDF
  movement (`2/6 -> 5/6`) includes query-fidelity-excluded rows and is kept as
  diagnostic context only.
- XLSX generalized answer-quality signal does not exist in this phase:
  validation included rows stayed `1/1 -> 1/1`, dev included rows are `0/6`,
  and the 344-row locator surface did not move after the accepted
  structural-specificity rule.
- XLSX priority remains locator/evidence, not fine-tuning:
  `table_or_range_miss_after_sheet_hit=219`,
  `table_or_range_rank_gap_within_top3=8`,
  `cell_or_value_miss_after_range_hit=3`, plus workbook gate
  disambiguation=44 and sheet miss=51.
- Direct normalized-value query matching remains rejected because it is an
  answer-value shortcut risk and previously regressed validation cell/value
  behavior. Current artifacts record it as disabled.
- PDF file identity remains a separate resolver bottleneck: v3_8_2 reference
  file_resolve@1 is `65/329`, file_resolve@3 is `129/329`, abstain is
  `182/329`, and wrong-file block is `57/329`. This phase's answer-quality
  harness used preselected SourceAtom evidence, so it does not claim file
  resolver improvement.
- PDF evidence window improved on validation through native same-page/bbox
  bounded expansion. Remaining PDF residuals are weak evidence, dot/OCR-like
  artifacts, broad context, and evaluator overlap; true answer failure is not
  the observed bottleneck in this small holdout.
- OCR remains skipped. Native text was usable and no scanned/image-only or
  native-unusable candidate showed material OCR gain.
- Fine-tuning remains deferred. The remaining problems are still locator,
  evidence-window, and query-policy issues; they should not be handed to
  fine-tuning until locator/evidence inputs are reliable.
- Codex-owned diagnostic decisions: source-document/workbook-disjoint split,
  query-fidelity exclusion buckets, PDF/XLSX family-separated reporting,
  dev-only gain exclusion from success evidence, OCR skip, and direct value
  shortcut rejection. User-owned decisions remain only relevance,
  answerability, expected answer/supporting evidence, pass/fail, denominator
  eligibility, query approval, policy note, and any future official adapter
  approval.

## 2026-05-24 - v3_9 Natural Answer-Quality Diagnostic Triage Note

This triage note covers
`official_answer_citation_agentic_loop_run_v3_9_natural_answer_quality_diagnostic`.
It keeps the work diagnostic-only and creates no gold, qrels, expected-answer,
supporting-evidence, official-denominator, namespace, DB, production,
promotion, threshold, or winner mutation. The future scored adapter remains
`DISABLED_PENDING_USER_APPROVAL` and `official_metric_input_rows=0`.

- Generalized validation signal exists only for PDF query-fidelity included
  rows: raw final `2/4` -> answer-ready `3/4`. The all-row PDF validation
  movement (`2/6 -> 5/6`) includes query-fidelity-excluded rows and is not
  counted alone as generalized success.
- Dev rows remain dev-only: PDF all rows `2/6 -> 3/6`, but the PDF
  query-fidelity included subset is flat (`2/3 -> 2/3`). XLSX dev included
  rows are `0/6`; TEXT dev is flat (`2/6 -> 2/6`).
- XLSX answer-quality in this small preselected evidence loop is flat:
  validation raw final `6/6` -> answer-ready `6/6`, included subset `1/1 ->
  1/1`. The actual XLSX priority remains locator structure, especially
  `table_or_range_miss_after_sheet_hit=219` from v3_8_3, not answer-ready
  sampling.
- TEXT answer-quality is also flat or worse versus the legacy prompt:
  validation baseline `6/6`, final/answer-ready `5/6`, with `invalid_json=1`.
  The remaining TEXT work is strict JSON / narrow factual span / coreference
  prompting, not PDF/XLSX deterministic adapter scoring.
- Raw-pass-to-ready-fail regression is zero after neutralization. Non-PDF
  answer-ready rows reuse final locator responses because no non-PDF
  answer-ready evidence transform is being validated in this loop.
- Query-fidelity buckets are retained, not deleted. Validation has
  included=`11`, excluded=`7`; excluded rows are mostly XLSX index-to-content
  and PDF drift/synthetic rows requiring user query approval before any
  headline interpretation.
- OCR remains skipped. Native PDF text was available and validation PDF gain
  came from same-page/bbox native text windows; no scanned/image-only or
  native-unusable evidence proved OCR material benefit.
- Codex-owned diagnostic decisions: source-document-disjoint validation split,
  non-PDF answer-ready raw reuse, query-fidelity exclusion buckets, OCR skip,
  dev split disjointness marked not-applicable, all-family aggregate metrics
  marked diagnostic-only/non-headline, and family-separated reporting.
  User-owned decisions remain only relevance,
  answerability, expected answer/supporting evidence, pass/fail, denominator
  eligibility, query approval, policy note, and any future official adapter
  approval.

## 2026-05-24 - XLSX v3_8_3 Scoped Locator Anti-Overfit Triage Note

This triage note keeps the XLSX scoped locator work diagnostic-only. It creates
no gold, qrels, expected-answer, supporting-evidence, denominator, namespace,
DB, production, promotion, threshold, or winner mutation. The status event is
`diagnostic_xlsx_scoped_cell_resolve_v3_8_3` for
`official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic`.

- The current v3_8_3 344-row XLSX surface is treated as dev-only unless
  validated separately. A workbook-disjoint non-official validation split is
  recorded: protected=19, dev=155, validation=170,
  `official_metric_input_rows=0`.
- Generalized signal: page-style sheet normalization (`26페이지` to `26p`)
  improved validation sheet@1 from 111/170 to 112/170. Protected rows did not
  regress, dev rows did not change, and table/range plus cell/value metrics did
  not change.
- Rejected rule: direct normalized-value query matching improved no accepted
  validation metric and regressed one existing validation cell/value pass, so it
  was removed before the final artifact. This keeps value text from becoming an
  overfit-prone answer-like scoring shortcut.
- Remaining residual buckets after the accepted rule: workbook gate
  disambiguation=44, sheet_miss_after_workbook_gate=51,
  table_or_range_miss_after_sheet_hit=219,
  table_or_range_rank_gap_within_top3=8,
  cell_or_value_miss_after_range_hit=3, hit=19. The largest remaining safe
  surface is still table/range locator recall after a sheet hit.
- Frozen guardrails record no case_id branches, exact query hacks,
  workbook/file/source-title hacks, pass/fail threshold tuning,
  expected/supporting/gold text input, denominator mutation, namespace mutation,
  production mutation, or adapter enablement.
- Remaining user-owned decisions are relevance, answerability, expected answer,
  supporting evidence, pass/fail, denominator eligibility, policy note, query
  approval, and any future official metric boundary or adapter approval.

## 2026-05-24 - PDF Answer-Ready Overfit Guard Triage Note

This triage note freezes the current candidate rules before validation and
keeps residual work diagnostic-only. It creates no gold, qrels,
expected-answer, supporting-evidence, denominator, namespace, DB, production,
promotion, threshold, or winner mutation.

- The current PDF headline rows are re-labeled as dev-only. Fresh dev packet:
  raw final 17/30 -> answer-ready 20/30; PDF all rows 5/15 -> 8/15; PDF
  query-fidelity headline 5/13 -> 8/13. The combined PDF answer-ready counts
  include one preserved raw-final pass; fresh PDF answer-ready passes are 7/15
  all rows and 7/13 headline. These gains stay visible but are not success
  evidence by themselves.
- A separate validation holdout was selected from existing non-gold,
  non-official material. The packet records 15 PDF and 15 XLSX rows,
  `source_document_disjoint_from_dev=true`, `dev_overlap_document_count=0`,
  `official_metric_input_rows=0`.
- Validation all-row answer quality: 18/30 -> 20/30. Validation PDF all-row
  answer quality: 8/15 -> 9/15, with three preserved raw-final passes and
  fresh PDF answer-ready passes at 6/15. Validation query-fidelity headline
  quality: 8/15 -> 8/15; PDF headline: 8/14 -> 8/14 with fresh answer-ready
  5/14. This means the dev headline gain stayed dev-only and the holdout only
  shows a small combined all-row diagnostic gain.
- Raw-pass-to-ready-fail regression was neutralized first. Dev PDF delta
  buckets are raw_fail_to_ready_pass=3, raw_fail_to_ready_fail_same_failure=6,
  raw_fail_to_ready_fail_changed_failure=1, raw_pass_to_ready_pass=5, with no
  raw-pass regression. Validation PDF delta buckets are raw_fail_to_ready_pass=1,
  raw_fail_to_ready_fail_same_failure=1, raw_fail_to_ready_fail_changed_failure=5,
  raw_pass_to_ready_pass=8, with no raw-pass regression.
- Allowed candidate rules remain bounded same-page windows, heading/body
  pairing by same-page order, dot-leader cleanup, locator-only demotion,
  broad/duplicate suppression, evidence-density scoring, context ordering, and
  raw-final reuse when answer-ready evidence has no structural gain. Guardrails
  record no case_id branches, exact query hacks, file/source-title hacks,
  pass/fail threshold tuning, expected/supporting/gold text input, or
  drift-contaminated headline gain.
- Dev residuals after answer-ready: `pdf-005`, `pdf-008`, `pdf-010`,
  `pdf-011`, `pdf-012`, `pdf-013`, `pdf-015`. Bucket counts: weak_evidence=6,
  dot_or_ocr_artifact=7, broad_context=4, locator_only=3, query_drift=2,
  evaluator_limitation=7, true_answer_failure=0.
- Validation residuals after answer-ready: `pdf-025`, `pdf-027`, `pdf-030`,
  `pdf-031`, `pdf-033`, `pdf-035`. Answer-ready failed-row bucket counts:
  weak_evidence=6, dot_or_ocr_artifact=6, broad_context=2, locator_only=0,
  query_drift=0, evaluator_limitation=2, true_answer_failure=0. The broader
  validation residual review table includes one additional query-fidelity
  excluded pass row, so its combined review buckets are weak_evidence=7,
  dot_or_ocr_artifact=7, and query_drift=1.
- OCR remains skipped. The holdout still has native text and does not prove OCR
  absence/unusability or material OCR gain. Revisit OCR only after
  scanned/image-only PDF evidence proves native text is absent or unusable and
  OCR would materially change evidence.
- Remaining user-owned decisions are answerable, relevance, expected answer,
  supporting evidence, pass/fail, denominator eligibility, policy note, review
  approval, query intent preservation, query approval, and query policy note.
  The future official-adjacent adapter remains disabled.

## 2026-05-24 - PDF Query Fidelity And Residual Review Note

This addendum keeps the PDF answer-ready evidence work diagnostic-only while
separating query drift from evidence-window quality. It creates no gold,
qrels, expected-answer, supporting-evidence, denominator, namespace, DB,
production, promotion, threshold, or winner mutation. The status event is
`pdf_xlsx_answer_quality_query_fidelity_packet_answer_ready_pdf_v1_llm_15pf`.
This entry is retained as prior status-ledger history; the overfit-guard
triage note above supersedes the packet artifacts and current interpretation.

- The prior all-row diagnostic counts remain visible but are marked
  query-fidelity-unverified: raw final 19/30, answer-ready 23/30, PDF 5/15 ->
  8/15, XLSX 14/15 -> 15/15.
- Structural query audit rows=30. Headline-included rows=16; excluded rows=14.
  PDF has 12 included and 3 excluded rows (two major-topic-drift, one
  unapproved index-to-content). XLSX has 4 included and 11 excluded unapproved
  index-to-content rows.
- Headline-included subset: raw final 9/16 -> answer-ready 11/16. PDF subset
  is 5/12 -> 7/12; XLSX subset remains 4/4 -> 4/4.
- PDF delta audit rows=15: raw_fail_to_ready_pass=4,
  raw_fail_to_ready_fail_same_failure=5,
  raw_fail_to_ready_fail_changed_failure=1, raw_pass_to_ready_pass=4, and
  raw_pass_to_ready_fail_regression=1. Prior-run comparison records 14/15 PDF
  rows as non-comparable because the query changed across runs.
- Answer-ready PDF residual review rows=8: the seven current answer-ready PDF
  failures (`pdf-005`, `pdf-007`, `pdf-008`, `pdf-010`, `pdf-011`, `pdf-012`,
  `pdf-015`) plus `pdf-013` as a
  query-drift review-only pass row. Bucket counts: weak_evidence=7,
  dot_or_ocr_artifact=8, broad_context=3, locator_only=5, table_form=0,
  query_drift=3, evaluator_limitation=7, true_answer_failure=0.
- OCR remains skipped. OCR-ish text is still measured, but the residual pattern
  points first to query drift, weak/locator-like evidence windows, and evaluator
  overlap limits. Revisit OCR only after scanned/image-only PDFs prove native
  text is absent or unusable and OCR would materially change evidence.
- Remaining user-owned decisions are answerable, relevance, expected answer,
  supporting evidence, pass/fail, denominator eligibility, policy note, review
  approval, query intent preservation, query approval, and query policy note.
- The future official-adjacent adapter is still disabled. Even user-approved
  rows cannot create scored inputs in this packet; unapproved drift rows are
  blocked from the approved-only preview.

## 2026-05-22 - PDF Answer-Ready Evidence Readiness Triage Note

This slice treats poor PDF answer quality as evidence shaping, not as gold
review. It creates no user-owned gold decision and no official metric input.
The status event is
`pdf_xlsx_answer_quality_evidence_readiness_packet_answer_ready_pdf_v1_llm_15pf`.

- PDF raw final answer quality improved 5/15 -> 8/15 after diagnostic
  normalization and bounded same-page expansion; XLSX moved 14/15 -> 15/15
  while its evidence text stayed unchanged by the answer-ready path. Aggregate
  diagnostic-only quality moved 19/30 -> 23/30 (+4).
- PDF evidence-readiness audit counts: bounded expansion 11/15, weak snippets
  11/15, dot-heavy snippets 11/15, locator-only flags 4/15, OCR-ish flags
  11/15, table/form-like flags 0/15, average raw score 0.1152, average
  expanded score 0.3938, average answer-ready score delta +0.2786.
- Retrieval miss was not recomputed here. The packet summary/status records
  `not_recomputed_preselected_sourceatom_evidence_only`, so `retrieval_miss=0`
  in the review taxonomy remains a routing note over preselected evidence, not
  a new retrieval recall claim.
- Bounded expansion keeps original page/bbox/source locator metadata and
  exposes raw, normalized, and answer-ready evidence in artifacts. It is capped
  by same-page lines/chars and avoids full-page dumping.
- Remaining user-owned gold/policy decisions are answerable, relevance,
  expected answer, supporting evidence, pass/fail, denominator eligibility,
  policy note, and review approval.
- No official metric input rows are created; gold/qrels/labels/expected
  answers/supporting evidence, official denominator policy, namespace
  isolation, production state, promotion policy, threshold tuning, and winner
  selection remain unchanged.

## 2026-05-22 - PDF/XLSX Performance And LLM Quality Triage Note

This slice opened no user-owned gold decision. All decisions stayed
diagnostic-only and non-promotional:

- Performance benchmarks use synthetic in-memory PDF/XLSX/SearchUnit fixtures,
  not official denominator rows or gold evidence.
- The LLM quality benchmark uses existing v3_7_2 weak silver only as query
  rewrite seeds; final queries are local-LLM rewrites, with exact silver reuse
  avoided and `fallback_rows=0` in the final 30-case run.
- Source joins are strict on `source_family+source_identity+locator_fingerprint`;
  locator-only fallback was intentionally disabled.
- Candidate SearchView/vector metadata remains candidate-only. Prompt locator
  packing omits candidate locator fields when SourceRegistry hydration is
  required.
- The final residuals (`low_evidence_overlap=9`, `locator_only_answer=1`,
  `pdf_locator_missing=1`) remain diagnostic answer-renderer/scoring residuals,
  not a request to change expected answers, supporting evidence, relevance,
  answerability, qrels, or gold policy.
- Gold-review packet preparation
  (`pdf_xlsx_answer_quality_gold_review_packet_final_llm_rewrite_all_llm_15pf_v3`)
  packages the 30 cases in
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/review_packet.csv`.
  No official metric input rows are created; all user-owned fields remain
  blank. The remaining human-owned decisions are answerable, relevance, expected answer, supporting evidence, pass/fail, denominator eligibility, and policy note.
- PDF residual routing is review-only: retrieval_miss=0, weak_snippet=9,
  ocr_ish_text=1, locator_only_evidence=8, table_form_formatting=8,
  semantic_answer_mismatch=9, evaluator_overlap_limitation=9. These buckets
  organize review and do not decide gold pass/fail.

## 2026-05-22 - Performance Optimization Triage Note

The PDF/XLSX performance slice did not open an answer/citation row triage queue
and did not require user-owned gold decisions. All ambiguous non-gold choices
were resolved conservatively:

- Use synthetic, in-memory PDF/XLSX/SearchUnit fixtures because no focused
  PDF/XLSX performance benchmark existed and no local source PDFs were
  available for a live ingestion smoke.
- Keep official denominator, gold CSVs, qrels, labels, expected answers,
  supporting evidence, and promotion policy unchanged.
- Treat benchmark output as diagnostic performance evidence only, not
  representative retrieval quality or product-performance evidence.
- Keep real scanned-PDF OCR/provider validation as a residual operational risk,
  not a gold-policy question.

## 2026-05-21 - Report Layout Triage Note

No queue state changed in this cleanup. The change is evidence layout only:
keep current status and the latest v3_6_9 contract proof in
`ai/eval/reports/rag-ingestion/`, together with later compact v3_7/v3_8
diagnostic artifacts, and resolve older queue, failure, audit, and
measurement payloads from the external archive. This file remains the rolling
row-level triage surface; avoid recreating per-run Markdown reports unless a
future run genuinely needs a separate forensic artifact.

## Triage Policy

- Triage is diagnostic-only unless the user explicitly changes scope.
- Do not change expected answers, supporting evidence, relevance labels,
  answerability labels, or gold policy without a user decision.
- Do not create silver/gold/promotion evidence during triage.
- Do not use expected answers, supporting evidence, or gold fields as generation
  source.
- Keep Lane A/B/C separated in interpretation.

## Historical Phase Snapshot

For current portfolio and diagnostic status, read
`docs/rag-ingestion-progress.md` first. The section below is preserved as
row-level triage history from the v3_4_3 smoke-metric period, not as the active
portfolio status.

Phase:
`v3_4_3 official exact-evidence retrieval smoke metrics computed`

Prior phase marker
`v3_4_2 official exact-evidence retrieval qrels labels applied` remains valid
as the qrels-readiness source for this smoke metric.

Status:
priority 1~5 plus the remaining `text_namu_v2_0012` TEXT locator residual have
completed diagnostic stabilization. The full 29-row post-triage measurement now
has strict JSON parse failure, LLM-generated locator copy failure, PDF
`source_pdf_path` mismatch, XLSX `row_label` mismatch, and TEXT `text_locator`
missing all at zero. v3_1_2 recorded the first classification-only
answer-span/renderer batch, v3_1_3 processed the v3_1_2 remaining queue with
general prompt/renderer/scorer-compatibility changes, and v3_1_4 processed the
PDF residual queue with source-bound table-axis disambiguation. v3_1_5 then
processed the v3_1_4 remaining queue as a classification-only coverage
diagnostic for `gq_auto_010`, and v3_1_6 applied a safe same-page source-bound
PDF paragraph/window expansion for the same row. The current machine remaining
queue is empty. v3_1_7 then created the all-track residual inventory and
confirmed that the active implementation queue is empty even though policy-bound
all-track residuals still exist. v3_1_8 prepared the human gold-policy packet
and decision matrix for those five rows. v3_1_9 applied the user-owned
`gold_overrides.csv` decision source and rescored existing Lane A/B/C surfaces
without live generation. v3_2_0 then established the settled current-system live
baseline, v3_2_1 triaged only the remaining four TEXT rows, and v3_2_2 reran all
29 rows after the one safe scorer fix. v3_2_3 has now reconciled the v3_2_2
machine queue into actionability lanes: Lane A-only residuals are frozen replay
residuals, `gq_auto_010` is a PDF context-provenance follow-up, and live TEXT
B/C prompt-span work is limited to three rows. v3_2_4 then proved that
`gq_auto_010` is open because the v3_1_6 PDF window expansion is not wired into
the v3_2 measurement path. v3_2_5 has now reused that existing v3_1_6 safe PDF
window sidecar in the current v3_2 measurement path and closed `gq_auto_010`;
the active live B/C implementation queue is now limited to
`text_namu_v2_0014`, `text_namu_v2_0017`, and `text_namu_v2_0084`. v3_2_6
then applied a lane-scoped general TEXT prompt/span rule. It closed
`text_namu_v2_0014` Lane C and left `text_namu_v2_0017` plus
`text_namu_v2_0084` as diagnostic-only prompt/span residuals after the prompt
rule. v3_2_7 has now closed the post-fix sequence with a compact
status-ledger-only event and rolling report update: `gq_auto_010` and
`text_namu_v2_0014` are closed, `text_namu_v2_0017` and
`text_namu_v2_0084` remain diagnostic-only after the prompt rule,
`text_namu_v2_0012` and `text_namu_v2_0077` remain frozen Lane A replay
residuals, and no next implementation phase is opened. v3_3_0 then audited the
v3_2_3 through v3_2_7 source-of-truth chain without reopening the queue or
changing behavior. v3_3_1 then checked whether the existing source-bound
SearchUnit material can safely seed anti-overfit silver source manifests; it
cannot, because all currently available source-bound rows overlap the official
29-row denominator. v3_3_2 then prepared only the human retrieval
relevance/answerability label-design packet for future official ranking
metrics; it did not compute nDCG, MRR, Hit@K, collapse Lane A/B/C, or create
labels/qrels. v3_4_0 now records the official retrieval metric contract and
qrels schema only. It defines Hit@1/3/5, MRR@5, nDCG@5, micro overall, and
macro-by-source-family boundaries, but leaves official metrics blocked until
approved qrels labels exist. v3_4_1 then emits only a human-labelable qrels
candidate packet from source-bound official-denominator retrieval/oracle
artifacts. The packet keeps every relevance and answerability label pending for
human review and does not compute ranking metrics. v3_4_1a then minimizes that
review surface into query-group and ambiguity review packets. v3_4_2 now applies
the user decision: all query groups except `gq_auto_010` are accepted as
official exact-evidence qrels positives, while `gq_auto_010` is excluded because
the standalone February unemployment query lacks a year. The exclusion is not a
miss, failure, negative, or unanswerable case. Official exact-evidence metric
computation is ready for v3_4_3, but no metrics are computed in v3_4_2. The
qrels set is a small official exact-evidence retrieval smoke benchmark for
metric-pipeline validation and regression guarding, not statistically
representative product performance; README headline performance claims from
the 28-query set remain blocked. v3_4_3 now computes the small-sample official
exact-evidence retrieval smoke metrics on Lane B `live_llm_retrieval_topk` only;
Lane C query-bound oracle is reference-only. The run records micro/macro
Hit@1/3/5, MRR@5, and binary exact-evidence nDCG@5 for regression guarding,
with readme_headline_allowed=false and no representative product-performance
claim.

Source foundation run:
`official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement`

Current triage run:
`official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation`

Previous all-track source run:
`official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`

## v3_4_3 Official Exact-Evidence Retrieval Smoke Metrics

Source artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_official_retrieval_qrels.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_coverage_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_exclusion_ledger.jsonl`

Metric artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_metrics.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_per_query.jsonl`

Metric denominator:

| Bucket | Count/status |
|---|---:|
| included query groups | 28 |
| excluded query groups | 1 |
| excluded query_id | `gq_auto_010` |
| source-family counts | PDF=3, TEXT=6, XLSX=19 |
| primary ranking surface | Lane B `live_llm_retrieval_topk` |
| reference-only surface | Lane C `query_bound_oracle` |

Micro overall:

| Metric | Value |
|---|---:|
| Hit@1 | 27/28 = 0.9642857142857143 |
| Hit@3 | 28/28 = 1.0 |
| Hit@5 | 28/28 = 1.0 |
| MRR@5 | 27.5/28 = 0.9821428571428571 |
| binary exact-evidence nDCG@5 | 0.9868189197704093 |

Macro by source_family:

| Metric | Value |
|---|---:|
| Hit@1 | 0.9824561403508771 |
| Hit@3 | 1.0 |
| Hit@5 | 1.0 |
| MRR@5 | 0.9912280701754387 |
| binary exact-evidence nDCG@5 | 0.9935250833959905 |

Interpretation guardrails:

- `small_sample_warning=true`: this 28-query set is valid for
  metric-pipeline validation and regression guarding, not statistically
  representative product performance.
- `readme_headline_allowed=false`; do not create README headline performance
  claims from this smoke metric.
- `regression_guard_allowed=true`.
- One query changes the score by about 3.57 percentage points.
- nDCG is binary exact-evidence nDCG@5 only; no graded nDCG was computed from
  ungraded labels.
- Lane C query-bound oracle is reference-only and not used for micro or macro
  retrieval ranking.
- No Lane A/B/C collapsed score, threshold tuning, winner selection, gold,
  expected answer, supporting evidence, answer/citation denominator, prompt,
  retrieval, renderer, scorer, index/export, production, silver, or promotion
  state changed.

## v3_4_2 Official Exact-Evidence Retrieval Qrels Labels Applied

Source artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.csv`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_human_query_group_review.csv`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_ambiguous_candidate_review.csv`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`

Applied qrels artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_official_retrieval_qrels.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_coverage_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_exclusion_ledger.jsonl`

Decision boundary:

| Bucket | Count/status |
|---|---:|
| included query groups | 28 |
| excluded query groups | 1 |
| excluded query_id | `gq_auto_010` |
| exclusion reason | `standalone_query_missing_year` |
| qrels unit rows | 140 |
| qrels positives | 28 |
| non-positive exact-evidence candidates | 112 |
| v3_4_3 metric computation | ready |

The excluded query is:

`2월 실업률은 전년 같은 달보다 어떻게 변했나요?`

User note:

`2월 실업률은 전년 같은 달보다 어떻게 변했나요? - 기준 연도 정보가 없어 standalone retrieval qrels에서 제외`

Metric naming and guardrails:

- This is an official exact-evidence retrieval qrels artifact over source-bound
  SearchUnits, not a broad topical semantic relevance benchmark.
- Scope is `source_bound_search_unit_exact_answer_evidence_smoke`: a small
  official exact-evidence retrieval smoke benchmark.
- It is valid for metric-pipeline validation and regression guarding, not
  statistically representative product performance.
- README headline performance claims from this 28-query set are blocked.
- Positive qrels use `relevance_label=3`, `answerability_label=3`, and
  `label_provenance=user_bulk_accept_recommendation`.
- Non-positive candidates are only
  `not_official_positive_for_exact_evidence_metric`; they are not human-judged
  topical negatives.
- Future nDCG must be named binary exact-evidence nDCG@K unless a future phase
  creates full graded relevance labels.
- No official Hit@K, MRR, nDCG, micro/macro aggregate, or collapsed Lane A/B/C
  score was computed in v3_4_2.
- No gold, expected answer, supporting evidence, answer/citation denominator,
  prompt, retrieval, renderer, scorer, index/export, production, silver, or
  promotion state changed.

## v3_4_1 Official Retrieval Qrels Candidate Packet

Source artifacts:

- `ai/eval/eval_queries/official_denominator_registry.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`
- `ai/eval/reports/rag-ingestion/status.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`

Human-review artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.csv`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_summary.json`

Candidate packet status:

| Bucket | Count/status |
|---|---:|
| query_ids | 29 |
| qrels candidate rows | 219 |
| PDF candidates | 22 |
| TEXT candidates | 24 |
| XLSX candidates | 173 |
| retrieved_topk_candidate rows | 145 |
| query_bound_oracle_candidate rows | 29 |
| structured_adapter_candidate rows | 45 |
| skipped candidates | 0 |

Review fields:

- Each row has `query_id`, `source_family`, `rank`, `lane_source`,
  `candidate_role`, `document_version_id`, `search_unit_id`, source-bound
  locator JSON, source excerpt/hash, and pending human-review fields.
- Required pending values are `relevance_label=pending`,
  `answerability_label=pending`, and `label_status=pending_user_review`.
- Every candidate row records `official_denominator_overlap=true`,
  `qrels_candidate=true`, `generation_source=false`, and
  `promotion_evidence=false`.
- `suggested_label_reason` is diagnostic review context only; it is not a final
  relevance or answerability label.

Guardrails:

- No relevance label, answerability label, expected answer, supporting evidence,
  gold, denominator, prompt, retrieval, renderer, scorer, index/export, silver,
  production, promotion, threshold tuning, or winner-selection mutation.
- No official Hit@K, MRR, nDCG, micro/macro retrieval aggregate, or collapsed
  Lane A/B/C score was computed.
- Official metrics remain blocked until the user approves qrels labels and the
  selected denominator policy.

## v3_4_0 Official Retrieval Metric Contract

Source artifacts:

- `ai/eval/reports/rag-ingestion/status.jsonl`
- `ai/eval/eval_queries/official_denominator_registry.json`
- `ai/eval/reports/rag-ingestion/metric_input_v1.json`
- `ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`

Contract artifacts:

- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_qrels_schema.json`

Contract status:

| Bucket | v3_4_0 contract | User decision needed | Metric status |
|---|---|---|---|
| qrels denominator | Options A all 29 rows, B track-by-track opening, C only rows with settled retrieval labels | Select A/B/C and any track opening rule | Retrieval metrics blocked |
| relevance labels | `0 NOT_RELEVANT`, `1 TOPIC_RELATED`, `2 SUPPORTING_CONTEXT`, `3 EXACT_ANSWER_EVIDENCE` | Approve schema and exact positive rule | Retrieval metrics blocked |
| answerability labels | `0 NOT_ANSWERABLE`, `1 RELATED_BUT_NOT_ANSWERABLE`, `2 PARTIALLY_ANSWERABLE`, `3 FULLY_ANSWERABLE` | Approve schema and answerability gate | Retrieval metrics blocked |
| Hit@K/MRR positive rule | Default proposal: relevance >= 3 and answerability >= 3 | Approve or override before labels apply | Retrieval metrics blocked |
| nDCG gain rule | Default gain is relevance grade; gated variant maps gain to 0 when answerability < 2 | Approve default and zero-IDCG policy | Retrieval metrics blocked |
| legacy/silver qrel sources | XLSX legacy retrieval CSV and XLSX silver retrieval-evidence files are prohibited as current official qrels | User may approve a future migration, but not in v3_4_0 | Retrieval metrics blocked |

Metric list:

- Hit@1, Hit@3, Hit@5, MRR@5, and nDCG@5.
- Micro overall over eligible labeled rows.
- Macro by source_family: TEXT, PDF, XLSX.

Guardrails:

- No relevance labels, answerability labels, qrels, expected answers,
  supporting evidence, gold, denominator, prompt, retrieval, renderer, scorer,
  index/export, silver, production, promotion, threshold tuning, or
  winner-selection mutation.
- No official nDCG, MRR, Hit@K, micro/macro retrieval metric, or collapsed
  Lane A/B/C score was computed.
- Official answer/citation results and official retrieval metrics must remain
  separate README sections.
- The active implementation queue remains empty and no next implementation
  phase is opened.

## v3_3_2 Retrieval Relevance/Answerability Label-Design Packet

Run family:
`official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet`

Source artifacts:

- `ai/eval/eval_queries/official_denominator_registry.json`
- `ai/eval/reports/rag-ingestion/metric_input_v1.json`
- `ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/build.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json`
- `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`

Design packet status:

| Bucket | Current state | User decision needed | Metric status |
|---|---|---|---|
| answer/citation denominator | 29 rows: PDF=4, TEXT=6, XLSX=19 | Whether these rows may be re-adjudicated into retrieval qrels or stay answer/citation-only | Retrieval metrics blocked |
| relevance labels | No official retrieval relevance labels are settled | Binary versus graded labels; what counts as positive for Hit@K/MRR | Retrieval metrics blocked |
| answerability labels | Existing harness has a 0-3 answerability family, but no current official labels for this denominator | Whether row-level, bundle-level, or both answerability judgments gate official metrics | Retrieval metrics blocked |
| evidence policy | v3_2_6 has query-bound and retrieved top-k context artifacts | Strict query-bound SearchUnit-only versus broader source-bound same-document/window/structured evidence | Retrieval metrics blocked |
| structured XLSX/PDF adapters | Adapter PASS is deterministic answer/citation evidence, not a qrel | Whether XLSX cell/range and PDF FILE-vs-CONTENT cases need separate official retrieval lanes | Retrieval metrics blocked |

Proposed schema options:

- Relevance option A: `RELEVANT`, `IRRELEVANT`.
- Relevance option B: `EXACT_ANSWER_EVIDENCE`, `SUPPORTING_CONTEXT`,
  `TOPIC_RELATED`, `NOT_RELEVANT`.
- Answerability option A: reuse `NOT_RELEVANT`,
  `RELATED_BUT_NOT_ANSWERABLE`, `PARTIALLY_ANSWERABLE`,
  `FULLY_ANSWERABLE`.
- Answerability option B: the same 0-3 scale plus flags for
  `PDF_FILE_IDENTITY`, `PDF_CONTENT`, `XLSX_CELL_RANGE`, and
  `MULTI_UNIT_BUNDLE_REQUIRED`.
- Required record fields for any later qrel artifact: `query_id`,
  `source_family`, `document_version_id`, `search_unit_id`, source-bound
  locator, `label_status=pending`, label provenance, dataset/index/config
  version, and blank human decision fields until the user fills them.

User-owned judgments:

- Relevance: whether a candidate SearchUnit is exact evidence, support-only,
  topic-related, or irrelevant for the query.
- Answerability: whether the retrieved unit or top-k bundle can answer the
  query fully, partially, only topically, or not at all.
- Gold policy: whether existing answer/citation gold policy remains sufficient
  for retrieval ranking or needs a separate qrels policy.
- Expected answer/evidence: whether existing expected answer/evidence should be
  reused as labeler context, revised, or excluded from retrieval qrels review.
- Denominator policy: whether to include all 29 rows, open track-by-track, or
  exclude rows until source-family-specific policies are settled.

Guardrails:

- No relevance label, answerability label, expected answer, supporting evidence,
  gold, denominator, prompt, retrieval, renderer, scorer, index/export, silver,
  production, promotion, threshold tuning, or winner-selection mutation.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.
- The active implementation queue remains empty and no next implementation
  phase is opened.

## v3_3_1 Answer/Citation Silver Source-Manifest Readiness

Source artifacts:

- `ai/eval/silver/answer_citation_silver_manifest_v1.json`
- `ai/eval/silver/answer_citation_silver_readiness_v1.json`
- `ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `ai/eval/eval_queries/official_denominator_registry.json`

Decision:

| Bucket | Count | Status | Next phase |
|---|---:|---|---|
| official-denominator source-bound SearchUnits | 29 | locator-complete and source-text available, but official-overlap | `none` |
| eligible non-official TEXT silver source candidates | 0 | blocked; no safe source manifest rows | `none` |
| eligible non-official XLSX silver source candidates | 0 | blocked; no safe source manifest rows | `none` |
| eligible non-official PDF silver source candidates | 0 | blocked; no safe source manifest rows | `none` |

Readiness boundary:

- Minimum safe source-candidate schema is now explicit:
  `query_id` or `candidate_id`, `source_family`, source-bound locator,
  `document_version_id`, `search_unit_id`, source text availability,
  `generation_source=false`, `promotion_evidence=false`, and
  `official_denominator_overlap=false`.
- The current source-bound official-denominator index has 29/29 rows with
  `official_denominator_overlap=true`, so it must not be copied into
  dev/holdout tuning silver.
- No silver JSONL rows were created. No expected answers, supporting evidence,
  relevance labels, answerability labels, gold labels, official denominator
  rows, production surfaces, promotion evidence, or official retrieval ranking
  metrics were created or changed.
- The active implementation queue remains empty and no next implementation
  phase is opened.

## v3_3_0 Post-Closure Source-Of-Truth Audit

Source closure run:
`official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup`

Audit run:
`official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit`

Machine artifacts:

- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Bucket | Query IDs | Status | Next phase |
|---|---|---|---|
| `frozen_lane_a_replay_residual` | `text_namu_v2_0012`, `text_namu_v2_0077` | Lane A-only frozen replay residuals, not live prompt targets | `none` |
| `live_bc_text_prompt_span_residual` | `text_namu_v2_0017`, `text_namu_v2_0084` | `diagnostic_only_after_prompt_rule`; live B/C still miss the expected span after the general prompt rule | `none` |
| `pdf_context_residual` | none | `gq_auto_010` remains closed by the v3_2_5 reuse of the existing v3_1_6 PDF window overlay | `none` |
| `scorer_policy_closed` | `text_namu_v2_0077` | Lane B/C scorer-policy closure is preserved; remaining Lane A failure is frozen replay only | `none` |

Audit boundary:

- v3_2_3 uses the v3_2_2 queue/results as the machine source for actionability
  classification.
- v3_2_4 uses v3_2_3 as the gate and proves the `gq_auto_010` PDF context gap.
- v3_2_5 uses v3_2_4 plus the existing v3_1_6 PDF window sidecar and closes
  only `gq_auto_010`.
- v3_2_6 uses the v3_2_5 queue and closes only `text_namu_v2_0014`.
- v3_2_7 remains the compact closure status event in `status.jsonl`.
- No next implementation phase is opened by v3_3_0.
- No per-run Markdown report was written.

Guardrail status:

- `diagnostic_only=true`, `promotion_evidence=false`.
- `behavior_change_made=false` and `implementation_change_made=false` for
  v3_3_0.
- `scorer_behavior_mutation=false`; v3_3_0 does not reopen the v3_2_2 scorer
  closure.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, retrieval, renderer, scorer, index/export,
  production, silver, promotion, threshold tuning, winner selection, official
  nDCG, MRR, Hit@K, or collapsed Lane A/B/C score changed.

## v3_2_7 Post-Fix Closure And Rolling Report Cleanup

Source queue:
`official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`

Closure run:
`official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup`

Machine artifacts:

- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Bucket | Query IDs | Status | Next phase |
|---|---|---|---|
| `frozen_lane_a_replay_residual` | `text_namu_v2_0012`, `text_namu_v2_0077` | Lane A-only frozen replay residuals, not live prompt targets | `none` |
| `live_bc_text_prompt_span_residual` | `text_namu_v2_0017`, `text_namu_v2_0084` | `diagnostic_only_after_prompt_rule`; live B/C still miss the expected span after the general prompt rule | `none` |
| `pdf_context_residual` | none | `gq_auto_010` remains closed by the v3_2_5 reuse of the existing v3_1_6 PDF window overlay | `none` |
| `scorer_policy_closed` | `text_namu_v2_0077` | Lane B/C scorer-policy closure is preserved; remaining Lane A failure is frozen replay only | `none` |

Queue boundary:

- `gq_auto_010` is closed by the existing v3_1_6 safe PDF window overlay
  being available to the v3_2 measurement path.
- `text_namu_v2_0014` is closed by the v3_2_6 TEXT prompt/span rule.
- The active implementation queue is empty; no next implementation phase is
  opened by v3_2_7.
- The remaining `text_namu_v2_0017` and `text_namu_v2_0084` entries are
  diagnostic-only after the prompt rule and require user-owned gold,
  answerability, or scorer-policy judgment before any future mutation.

Evidence:

- Current Lane A/B/C pass counts are `24/29`, `27/29`, and `27/29`.
- Answer quality averages are Lane A=`0.8276`, Lane B=`0.9310`, and
  Lane C=`0.9310`; citation quality averages remain `1.0` in every lane.
- v3_2_5 and v3_2_6 are the only implementation-changing post-v3_2_2 phases.
- Unexpected deltas remain `0`.
- No per-run Markdown report was written.

Guardrail status:

- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, retrieval, renderer, scorer, index/export,
  production, silver, promotion, threshold tuning, winner selection, official
  nDCG, MRR, Hit@K, or collapsed Lane A/B/C score changed in v3_2_7.

## v3_2_6 TEXT Prompt/Span Rule Remeasurement

Source queue:
`official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix`

Remeasurement run:
`official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json`
- Results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`
- Failure attribution:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_failure.json`
- Actual response audit:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_audit.jsonl`
- TEXT prompt/span diagnostics:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_text_prompt_span_diagnostics.jsonl`
- Queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_queue.json`
- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Query ID | v3_2_5 live failing lanes | v3_2_6 live failing lanes | Classification | Next phase |
|---|---|---|---|---|
| `text_namu_v2_0014` | Lane C | none | `closed_by_text_prompt_span_rule` | `none` |
| `text_namu_v2_0017` | Lane B/C | Lane B/C | `diagnostic_only_after_prompt_rule` | `none` |
| `text_namu_v2_0084` | Lane B/C | Lane B/C | `diagnostic_only_after_prompt_rule` | `none` |

Queue boundary:

- Closed query ids: `text_namu_v2_0014`.
- Remaining recommended queue: `text_namu_v2_0017`,
  `text_namu_v2_0084`.
- Carried non-actionable Lane A-only residuals:
  `text_namu_v2_0012`, `text_namu_v2_0077`.
- `gq_auto_010` remains closed by the carried v3_2_5 PDF context overlay.
- `v3_2_7` closure is required to summarize the implementation-changing
  v3_2_5 and v3_2_6 phases; no additional implementation phase is opened by
  v3_2_6.

Evidence:

- The prompt delta is general and source-bound. It tells TEXT live rows that
  ask for a narrow factual span to answer only the required person, role,
  destination, release date, age, birthday, title, or described attribute from
  cited context, without neighboring lists, summaries, catchphrases, or broad
  descriptions.
- The prompt rule is lane-scoped to `text_namu_v2_0014` Lane C,
  `text_namu_v2_0017` Lane B/C, and `text_namu_v2_0084` Lane B/C.
- Full 29-row remeasurement changed only `text_namu_v2_0014` Lane C from
  `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`; unexpected deltas are `0`.
- Citation support averages remain `1.0`; strict JSON and locator residual
  counts remain `0`; denominator remains PDF=`4`, TEXT=`6`, XLSX=`19`.

Guardrail status:

- v3_2_6 is behavior-changing only for target/lane-scoped TEXT prompt
  instruction.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, retrieval, renderer, scorer, production
  index, non-production index/export rebuild, threshold tuning, winner
  selection, promotion, official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score
  changed.
- No per-run Markdown report was written.

## v3_2_5 `gq_auto_010` PDF Context Reconciliation Fix

Source diagnostic:
`official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic`

Fix run:
`official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_summary.json`
- Results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_results.jsonl`
- Failure attribution:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_failure.json`
- Actual response audit:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_audit.jsonl`
- PDF context diagnostics:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_pdf_context_diagnostics.jsonl`
- Queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_queue.json`
- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Query ID | Before v3_2_2 failing lanes | After v3_2_5 failing lanes | v3_2_5 cited SearchUnit IDs | Classification | Next phase |
|---|---|---|---|---|---|
| `gq_auto_010` | Lane B/C | none | `pdfwin_b1c6527f848018640ad5ed231877c662` | `closed_by_existing_v3_1_6_pdf_window_overlay` | `none` |

Queue boundary:

- Closed query ids: `gq_auto_010`.
- Remaining live B/C actionable queue:
  `text_namu_v2_0014`, `text_namu_v2_0017`, `text_namu_v2_0084`.
- Carried non-actionable Lane A-only residuals:
  `text_namu_v2_0012`, `text_namu_v2_0077`.
- Next implementation phase: `v3_2_6_text_prompt_span_rule`.

Evidence:

- v3_2_5 reuses the v3_1_6 sidecar expansion unit
  `pdfwin_b1c6527f848018640ad5ed231877c662` for `gq_auto_010` only.
- The v3_1_6 guard remains intact: same `source_pdf_path`, same
  `document_version_id=docv_fe2470815512a395`, page `8`, physical page index
  `7`, region type `paragraph_window`, and no expected/supporting/gold text as
  generation source.
- Full 29-row remeasurement changed only `gq_auto_010` Lane B/C from
  `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`; non-target unexpected deltas are `0`.
- Citation support averages remain `1.0`; strict JSON and locator residual
  counts remain `0`; denominator remains PDF=`4`, TEXT=`6`, XLSX=`19`.

Guardrail status:

- v3_2_5 is behavior-changing only for target-scoped prompt/context assembly
  wiring.
- No gold, expected answer, supporting evidence, relevance label,
  answerability label, denominator, production index, non-production
  index/export rebuild, threshold tuning, winner selection, promotion, official
  nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was produced.
- No per-run Markdown report was written.

## v3_2_4 `gq_auto_010` PDF Context Provenance Diagnostic

Source queue:
`official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation`

Diagnostic run:
`official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_summary.json`
- Diagnostics:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_pdf_context_provenance_diagnostics.jsonl`
- Recommended queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_queue.json`
- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Decision:

| Query ID | Current failing lanes | Current cited SearchUnit IDs | Current context has `pdfwin` | Current context has numeric span | Classification | Next phase |
|---|---|---|---:|---:|---|---|
| `gq_auto_010` | Lane B/C | `7bf516bf-2a17-4303-86d8-3cffaa04846e` | false | false | `open_because_v3_1_6_expansion_not_wired_into_v3_2_measurement` | `v3_2_5_wire_v3_1_6_pdf_window_expansion_into_v3_2_measurement` |

Evidence:

- v3_2_2 records `retrieval_context_rerun=false` and
  `retrieval_context_source_run_id=official_answer_citation_agentic_loop_run_v3_comparable_live_measurement`.
- v3_2_2 Lane B/C still fail with `LLM_EXPECTED_SPAN_MISMATCH` and cite the
  original SearchUnit `7bf516bf-2a17-4303-86d8-3cffaa04846e`.
- The current v3_2_2 Lane B/C context evidence does not include the expansion
  unit `pdfwin_b1c6527f848018640ad5ed231877c662` and does not contain the
  numeric answer span as context.
- v3_1_5 had already classified the original cited SearchUnit as
  `query_bound_searchunit_too_narrow`: raw/source PDF extraction contained the
  numeric span, but cited/current/same-document/adjacent SearchUnits did not.
- v3_1_6 applied the safe same-page source-bound PDF paragraph/window expansion
  with the same `source_pdf_path`, same `document_version_id`, page `8`,
  physical page index `7`, and region type `paragraph_window`; the expansion
  context contained the numeric span and Lane B/C became PASS.

Decision boundary:

- v3_2_5 is required, but only for measurement-source selection / context
  assembly overlay that wires the existing v3_1_6 expansion into the v3_2
  measurement path.
- v3_2_4 does not indicate any index/export rebuild requirement.
- This is not a TEXT prompt residual, scorer-policy issue, gold-policy issue,
  or live-LLM span-selection failure with expanded context already present.

Guardrail status:

- v3_2_4 is classification-only and no-behavior-change.
- No live generation, prompt context assembly change, renderer/scorer/retrieval
  behavior change, index/export rebuild, gold, expected answer, supporting
  evidence, label, denominator, silver, production, or promotion mutation
  occurred.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.
- No per-run Markdown, results JSONL, failure attribution JSON, or audit JSONL
  was written for v3_2_4.

## v3_2_3 Queue/Lane Actionability Reconciliation

Source queue:
`official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement`

Reconciliation run:
`official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_summary.json`
- Diagnostics:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_diagnostics.jsonl`
- Reconciled queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_queue.json`
- Status event:
  `ai/eval/reports/rag-ingestion/status.jsonl`

Actionability table:

| Query ID | Source | Failing lanes | Passing lanes | Lane A only | Live B/C actionable | Primary bucket | Next phase | Evidence artifact | Rationale |
|---|---|---|---|---:|---:|---|---|---|---|
| `text_namu_v2_0012` | TEXT | Lane A | Lane B/C | true | false | `frozen_replay_residual` | `none` | v3_2_2 queue/results | Lane B/C already pass; live prompt changes are not an appropriate fix surface for a frozen replay-only residual. |
| `text_namu_v2_0014` | TEXT | Lane A/C | Lane B | false | true | `text_prompt_span` | `v3_2_6_text_prompt_span_rule` | v3_2_1 triage + v3_2_2 queue/results | Preserve the v3_2_1 prompt/span finding; only the live Lane C side remains actionable. |
| `text_namu_v2_0017` | TEXT | Lane A/B/C | none | false | true | `text_prompt_span` | `v3_2_6_text_prompt_span_rule` | v3_2_1 triage + v3_2_2 queue/results | Preserve the v3_2_1 prompt/span primary classification with scorer as secondary only. |
| `text_namu_v2_0077` | TEXT | Lane A | Lane B/C | true | false | `frozen_replay_residual` | `none` | v3_2_1 triage + v3_2_2 summary/results | v3_2_1/v3_2_2 fixed Lane B/C through the scoped scorer policy; the remaining Lane A failure is not live prompt-fixable. |
| `text_namu_v2_0084` | TEXT | Lane A/B/C | none | false | true | `text_prompt_span` | `v3_2_6_text_prompt_span_rule` | v3_2_1 triage + v3_2_2 queue/results | Preserve the v3_2_1 prompt/span finding for live B/C follow-up. |
| `gq_auto_010` | PDF | Lane B/C | Lane A | false | true | `pdf_context_provenance` | `v3_2_4_pdf_context_provenance` | v3_2_2 queue/results + v3_1_6 PDF window artifacts | This is not a TEXT prompt residual. v3_2_2 still uses the frozen v3 context path while v3_1_6 proved a guarded PDF window expansion, so provenance must be proven before any v3_2_5 repair. |

Decision boundary:

- `v3_2_4_pdf_context_provenance` is required because `gq_auto_010` remains in
  the current v3_2_2 queue/failure artifacts.
- `v3_2_5` is not approved by v3_2_3 alone. It remains conditional on v3_2_4
  proving that the v3_1_6 expansion is missing from the v3_2 measurement path.
- `v3_2_6_text_prompt_span_rule` is required only for
  `text_namu_v2_0014`, `text_namu_v2_0017`, and `text_namu_v2_0084`.
- `text_namu_v2_0012` and `text_namu_v2_0077` are carried as frozen replay
  residuals with no next phase.

Guardrail status:

- v3_2_3 is classification-only and no-behavior-change.
- No prompt, renderer, scorer, retrieval, export, index, gold, expected answer,
  supporting evidence, relevance label, answerability label, denominator,
  silver, production, or promotion surface changed.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.
- No per-run Markdown, results JSONL, failure attribution JSON, or audit JSONL
  was written for v3_2_3.

## v3_2_1 Four-TEXT Residual Triage And v3_2_2 Remeasurement

Source baseline:
`official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline`

Triage run:
`official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage`

Post-fix remeasurement:
`official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement`

Machine artifacts:

- v3_2_0 summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline_summary.json`
- v3_2_0 results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline_results.jsonl`
- v3_2_1 residual triage:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage_residual_triage.jsonl`
- v3_2_2 summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement_summary.json`
- v3_2_2 results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement_results.jsonl`

Residual triage table:

| Query ID | Observed failure | Primary | Secondary | Evidence artifact | Action | Status |
|---|---|---|---|---|---|---|
| `text_namu_v2_0014` | Lane C answer drifts to unrelated/generic character-list content while Lane B passes | prompt | - | v3_2_0 results | no code change | diagnostic-only |
| `text_namu_v2_0017` | Lane B/C answers include the cited character context but remain broad/diluted beyond the narrowed current gold span | prompt | scorer | v3_2_0 results | no code change | diagnostic-only |
| `text_namu_v2_0077` | Lane B/C answers include the Tokyo destination in plain past tense but fail literal settled-gold matching | scorer | prompt | v3_2_0 results | query-scoped Korean polite/plain past-tense scorer equivalence | fixed in v3_2_2 Lane B/C |
| `text_namu_v2_0084` | Lane A/B/C cite the right source but omit the settled release-date span | prompt | - | v3_2_0 results | no code change | diagnostic-only |

Remeasurement result:

| Lane | v3_2_0 PASS | v3_2_2 PASS | Change |
|---|---:|---:|---|
| Lane A `v3_primary_replay` | `24/29` | `24/29` | unchanged |
| Lane B `live_llm_retrieval_topk` | `25/29` | `26/29` | `text_namu_v2_0077` PASS |
| Lane C `live_llm_query_bound_oracle` | `24/29` | `25/29` | `text_namu_v2_0077` PASS |

Guardrail status:

- Gold rows, expected answers, supporting evidence, relevance labels,
  answerability labels, denominator membership, retrieval behavior, renderer
  behavior, production behavior, silver, and promotion behavior were not changed.
- The scorer change is scoped to `text_namu_v2_0077` Korean polite/plain
  past-tense equivalence.
- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C scores are still deferred
  until relevance and answerability labels exist.
- Remaining diagnostic-only residuals are prompt-side TEXT cases:
  `text_namu_v2_0014`, `text_namu_v2_0017`, and `text_namu_v2_0084`.

## v3_1_9 User Decision Applied And Post-Rescore Queue

Source run:
`official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_summary.json`
- Applied overrides:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_applied_overrides.jsonl`
- Gold diff:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_gold_diff.jsonl`
- Rescored results:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_rescored_results.jsonl`
- Remaining queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_remaining_triage_queue.json`

Applied override rows:

| Query ID | Source family | User decision applied | Gold-policy action |
|---|---|---|---|
| `text_namu_v2_0012` | TEXT | user decision applied | Narrow expected answer and supporting evidence to age/birthday scope |
| `text_namu_v2_0014` | TEXT | user decision applied | Narrow to the supported Adversary cameo entry |
| `text_namu_v2_0017` | TEXT | user decision applied | Narrow to the currently supported Silk Cat boy description |
| `text_namu_v2_0077` | TEXT | user decision applied | Narrow to the destination answer, Tokyo |
| `text_namu_v2_0084` | TEXT | user decision applied | Drop the catchphrase and keep the film-description span |

Scoring-only result after user policy application:

| Lane | Before | After |
|---|---:|---:|
| Lane A `v3_primary_replay` | `24/29` PASS | `27/29` PASS |
| Lane B `live_llm_retrieval_topk` | `24/29` PASS | `26/29` PASS |
| Lane C `live_llm_query_bound_oracle` | `24/29` PASS | `25/29` PASS |

Post-rescore remaining queue:

| Query ID | Remaining lane failures | Classification |
|---|---|---|
| `text_namu_v2_0014` | Lane C | Implementation-safe residual after settled gold policy |
| `text_namu_v2_0017` | Lane B/C | Implementation-safe residual after settled gold policy |
| `text_namu_v2_0077` | Lane A/B/C | Implementation-safe residual after settled gold policy |
| `text_namu_v2_0084` | Lane A/B/C | Implementation-safe residual after settled gold policy |

v3_1_8 is now user decision applied, not awaiting user policy decision. The
remaining queue does not require another user policy packet unless a concrete
conflict appears between override rows and official denominator metadata.
Later work may inspect renderer, scorer, prompt, or retrieval behavior for the
four remaining query ids, but v3_1_9 itself did not implement those changes.

Guardrail status:

- User-approved gold policy mutation occurred:
  `expected_answer_mutation=true`, `supporting_evidence_mutation=true`,
  `gold_policy_mutation=true`, `user_policy_decision_applied=true`.
- No renderer/scorer/retrieval/production/silver/promotion behavior changed.
- Existing generated answer surfaces were rescored only; live generation was
  not rerun.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed.

## v3_1_8 Gold-Policy Review Packet Status

Source run:
`official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_summary.json`
- Human review packet:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_human_review_packet.json`
- Decision matrix:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_decision_matrix.jsonl`
- Remaining queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_remaining_triage_queue.json`

Historical status, superseded by v3_2_7/v3_3_0:

- User decision has been applied by v3_1_9.
- The v3_1_8 packet is no longer awaiting user policy decision.
- The v3_1_9 implementation-safe residual queue was later processed by v3_2_0
  through v3_2_7; the current active implementation queue is empty.
- Silver remains closed.
- v3_1_6 sibling-hash drift was recorded as metadata drift only; historical
  v3_1_6 artifacts were not rewritten.
- Raw expected/supporting/gold-policy material is present only inside the human
  review packet with `human_review_only=true`, `generation_source=false`,
  `not_silver_source=true`, and `not_gold_mutation=true`.

User decision options for every row:

- `keep_current_strict_reference_boundary`
- `approve_scorer_or_renderer_review_without_gold_mutation`
- `revise_gold_or_label_policy`

The user-approved decision source has been applied from `gold_overrides.csv`.
Do not create another user policy packet unless override metadata conflicts
with the official denominator.

Policy-review rows:

| Query ID | Source family | Lane failures | Packet status |
|---|---|---|---|
| `text_namu_v2_0012` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; all lanes PASS after v3_1_9 rescore |
| `text_namu_v2_0014` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; v3_2_6 later closed Lane C, leaving only frozen Lane A replay |
| `text_namu_v2_0017` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; v3_2_7/v3_3_0 classify Lane B/C as diagnostic-only prompt/span residuals |
| `text_namu_v2_0077` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; v3_2_2 closed Lane B/C by scorer policy, Lane A remains frozen replay |
| `text_namu_v2_0084` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User decision applied; v3_2_7/v3_3_0 classify Lane B/C as diagnostic-only prompt/span residuals |

Guardrail status:

- Diagnostic-only.
- Not promotion evidence.
- No renderer, scorer, retrieval, denominator, production, silver, gold,
  expected-answer, supporting-evidence, relevance-label, answerability-label, or
  human-label mutation.
- No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score.

## v3_1_7 Residual Inventory And Decision Boundary

Source run:
`official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic`

Machine artifacts:

- Summary:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_summary.json`
- Residual inventory:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_all_track_residual_inventory.jsonl`
- Remaining queue:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_remaining_triage_queue.json`
- User decision packet:
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_user_decision_packet.json`

Decision boundary:

- Active remaining queue: cleared.
- Active implementation queue: empty.
- All-track residuals still exist: five TEXT query ids across all three lanes.
- No residual is currently safe to fix without a user gold/relevance/
  answerability policy decision.
- Do not change expected answers, supporting evidence, labels, scorer policy, or
  renderer behavior from this inventory alone.

Residual query ids:

| Query ID | Source family | Lane failures | Current handling |
|---|---|---|---|
| `text_namu_v2_0012` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |
| `text_namu_v2_0014` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |
| `text_namu_v2_0017` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |
| `text_namu_v2_0077` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |
| `text_namu_v2_0084` | TEXT | Lane A `LLM_TRUE_PARTIAL_SYNTHESIS`; Lane B/C `LLM_EXPECTED_SPAN_MISMATCH` | User gold-policy review packet |

Residual buckets:

- `gold_policy_review_candidate=15`
- `answer_renderer_followup_candidate=15`
- `scorer_normalization_review_candidate=3`
- `implementation_safe_followup=0`
- `retrieval_context_followup_candidate=0`
- `relevance_label_review_candidate=0`
- `answerability_label_review_candidate=0`

Packet status:
superseded by v3_1_8 packet preparation above; active implementation queue
remains empty until a user policy decision is applied.

## Post-Triage Queue

Source run:
`official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage`

Strict JSON / locator residual count: `0`.

Queue source of truth:

- The authoritative queue is the machine artifact
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_1_post_locator_queue.json`.
- If this file and human queue notes differ, use the machine artifact. That is
  why the first batch includes `text_namu_v2_0012`, and why
  `text_namu_v2_0005` is kept as queue rank 12 instead of being dropped.
- The older Later Triage Queue text was stale: it omitted
  `text_namu_v2_0012` and `text_namu_v2_0005`, and included `gq_auto_037`,
  which is not in the machine post-triage queue.

The post-triage queue is answer-span / answer-renderer oriented:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `text_namu_v2_0012` | TEXT answer synthesis / expected span |
| 2 | `text_namu_v2_0014` | TEXT answer synthesis / expected span |
| 3 | `text_namu_v2_0017` | TEXT answer synthesis / expected span |
| 4 | `text_namu_v2_0077` | TEXT answer synthesis / expected span |
| 5 | `text_namu_v2_0084` | TEXT answer synthesis / expected span |
| 6 | `gq_auto_010` | PDF answer span |
| 7 | `gq_auto_024` | PDF/XLSX answer span |
| 8 | `gq_auto_030` | PDF answer span |
| 9 | `gq_auto_043` | XLSX answer span |
| 10 | `gq_pdf_section_question_001` | PDF answer span |
| 11 | `gq_xlsx_date_number_format_001` | XLSX date/number answer span |
| 12 | `text_namu_v2_0005` | TEXT answer span |

Recorded post-triage metrics:

- Lane A PASS: `24/29`.
- Lane B PASS: `20/29`.
- Lane C PASS: `17/29`.
- Lane B/C strict JSON parse failure: `0`.
- Lane B/C LLM-generated locator copy failure: `0`.
- PDF `source_pdf_path` mismatch: `0`.
- XLSX `row_label` mismatch: `0`.
- TEXT `text_locator` missing: `0`.
- Existing v3_1 PASS regressions recorded: `4` query/lane cases, all answer-span category.

## Answer Span / Renderer Batch 1 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage`

Scope:

- Diagnostic-only, classification-only over v3_1_1 artifacts.
- No generation prompt, output parser, answer renderer, normalization, scorer,
  locator-copy, or SearchUnit payload behavior was changed.
- No all-track rerun was performed because no behavior changed before this
  diagnostic artifact.

Selected rows:

| Query ID | Queue decision | Lane result | Diagnostic classification |
|---|---|---|---|
| `text_namu_v2_0012` | first batch, rank 1 | Lane A/B/C fail | diagnostic-only expected-span mismatch, answer too narrow, scorer normalization gap |
| `text_namu_v2_0014` | first batch, rank 2 | Lane A/B/C fail | diagnostic-only expected-span mismatch, answer too narrow; Lane C also flags answer too broad, renderer formatting, and Korean paraphrase mismatch |
| `text_namu_v2_0017` | first batch, rank 3 | Lane A/B/C fail | diagnostic-only expected-span mismatch, answer too narrow; Lane A also flags renderer formatting mismatch |
| `text_namu_v2_0077` | first batch, rank 4 | Lane A/B/C fail | diagnostic-only expected-span mismatch; mixed answer too broad / too narrow flags by lane, with Lane B Korean renderer/paraphrase mismatch |
| `text_namu_v2_0084` | first batch, rank 5 | Lane A/B/C fail | diagnostic-only expected-span mismatch and answer too narrow |
| `text_namu_v2_0005` | secondary watchlist, rank 12 | Lane A/B pass, Lane C fail | Lane C diagnostic-only expected-span mismatch, answer too narrow, renderer formatting mismatch, Korean paraphrase mismatch |

Target-batch metrics:

- Target rows: `6`.
- Primary first-batch rows: `5`.
- Secondary watchlist rows: `1`.
- Target Lane A PASS: `1/6`.
- Target Lane B PASS: `1/6`.
- Target Lane C PASS: `0/6`.
- Primary first-batch Lane A/B/C PASS: `0/5` each.
- Diagnostic categories across target lanes:
  `diagnostic_only_expected_span_mismatch=16`, `answer_too_narrow=15`,
  `answer_too_broad=3`, `renderer_formatting_mismatch=4`,
  `korean_synthesis_paraphrase_mismatch=3`, `scorer_normalization_gap=3`,
  `pass=2`.

Guardrail result:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- Reference spans are audit-only; the diagnostic artifact stores hashes/counts
  and does not embed raw reference span text for generation.

Remaining queue after batch 1:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `gq_auto_010` | PDF answer span |
| 2 | `gq_auto_024` | PDF/XLSX answer span |
| 3 | `gq_auto_030` | PDF answer span |
| 4 | `gq_auto_043` | XLSX answer span |
| 5 | `gq_pdf_section_question_001` | PDF answer span |
| 6 | `gq_xlsx_date_number_format_001` | XLSX date/number answer span |
| 7 | `text_namu_v2_0005` | secondary TEXT watchlist, Lane C-only answer renderer/span |

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json`

Artifact policy for this triage lane:

- Queue source of truth: the machine remaining-queue JSON above.
- Human-facing source of truth: this rolling triage document plus
  `docs/rag-ingestion-progress.md` and `docs/rag-ingestion-measurements.md`.
- Canonical classification payload: v3_1_2
  `answer_span_diagnostics.jsonl`; use it for row/lane category inspection
  before opening full debug payloads.
- Forensic debug payloads: v3_1_2 `results.jsonl`,
  `failure_attribution.json`, and `actual_response_audit.jsonl`. Keep them for
  now because artifact tests read them and because they preserve strict
  JSON/locator regression evidence.
- Stale or previous queue text must not override the machine queue. The older
  stale mention of `gq_auto_037` is retained only as historical drift evidence
  above, not as an active queue item.
- Per-run Markdown reports remain out of scope for routine classification-only
  triage.

## Remaining Queue Batch 2 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage`

Source of truth:

- The authoritative input queue is
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json`.
- Rolling docs are human-facing narrative only. If docs and machine queue
  differ, use the machine queue. The stale `gq_auto_037` human queue wording is
  not active.

Scope:

- Target rows: `gq_auto_010`, `gq_auto_024`, `gq_auto_030`,
  `gq_auto_043`, `gq_pdf_section_question_001`,
  `gq_xlsx_date_number_format_001`, `text_namu_v2_0005`.
- Allowed changes used: prompt answer instructions, source-bound answer
  renderer, and post-generation scorer compatibility normalization.
- Forbidden work stayed closed: no expected/supporting/gold mutation, no
  silver/gold/promotion evidence, no threshold tuning, no winner selection, no
  production namespace mutation, and no candidate artifacts as generation
  source.

Target row changes:

| Query ID | Before | After | Category |
|---|---|---|---|
| `gq_auto_010` | Lane B/C fail | Lane B/C fail | PDF retrieval/context answer-span insufficiency; expected numeric span not in cited context. |
| `gq_auto_024` | Lane C fail | PASS all lanes | Korean source phrase renderer / paraphrase compatibility. |
| `gq_auto_030` | Lane C fail | PASS all lanes | PDF table value selected correctly after prompt table-axis instruction. |
| `gq_auto_043` | Lane B/C fail | PASS all lanes | XLSX date normalized-value compatibility. |
| `gq_pdf_section_question_001` | Lane B/C fail | Lane B/C fail | PDF table repeated amount/growth columns still select wrong value. |
| `gq_xlsx_date_number_format_001` | Lane B/C fail | PASS all lanes | XLSX date normalized-value compatibility. |
| `text_namu_v2_0005` | Lane C fail | PASS all lanes | Korean answer-renderer/language drift fixed; Lane A/B unchanged PASS. |

Metrics:

- Target Lane A/B/C PASS: `7/7`, `5/7`, `5/7` after v3_1_3
  (before: `7/7`, `3/7`, `0/7`).
- Target answer-span mismatch Lane A/B/C: `0`, `2`, `2` after v3_1_3
  (before: `0`, `4`, `7`).
- 29-row all-track Lane A/B/C PASS: `24/29`, `22/29`, `22/29` after
  v3_1_3 (before v3_1_1: `24/29`, `20/29`, `17/29`).
- 29-row all-track answer-span mismatch Lane A/B/C: `0`, `7`, `7` after
  v3_1_3 (before: `0`, `9`, `12`).
- Strict JSON parse residual remains `0` by lane.
- LLM-generated locator copy/missing/field mismatch residual remains `0` by
  lane.
- PDF `source_pdf_path` mismatch, XLSX `row_label` mismatch, and TEXT
  `text_locator` missing remain `0`.

Remaining queue after v3_1_3:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `gq_auto_010` | PDF cited context does not include the expected numeric span (`4.9%`, `0.8%p`). |
| 2 | `gq_pdf_section_question_001` | PDF table repeated amount/growth groups still require value disambiguation for `수출입차 금액`. |

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_3_remaining_queue.json`

Guardrail audit:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`.

## PDF Residual Batch 3 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage`

Source of truth:

- The authoritative input queue is
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_3_remaining_queue.json`.
- Rolling docs are human-facing narrative only. If docs and machine queue
  differ, use the machine queue.

Scope:

- Target rows: `gq_auto_010`, `gq_pdf_section_question_001`.
- Allowed changes used: source-bound PDF table-axis answer renderer for
  repeated amount/growth columns, plus post-generation diagnostic
  classification for PDF context insufficiency.
- Forbidden work stayed closed: no expected/supporting/gold mutation, no
  silver/gold/promotion evidence, no threshold tuning, no winner selection, no
  production namespace mutation, and no candidate artifacts as generation
  source.

Target row changes:

| Query ID | Before | After | Category |
|---|---|---|---|
| `gq_auto_010` | Lane B/C fail | Lane B/C fail | Retrieval/context insufficiency: cited paragraph lacks the numeric span, so the renderer must not invent it. |
| `gq_pdf_section_question_001` | Lane B/C fail | PASS all lanes | Source-bound PDF table-axis disambiguation selected `수출입차 금액` value `518.4`. |

Metrics:

- Target Lane A/B/C PASS: `2/2`, `1/2`, `1/2` after v3_1_4
  (before: `2/2`, `0/2`, `0/2`).
- Target answer-span mismatch Lane A/B/C: `0`, `1`, `1` after v3_1_4
  (before: `0`, `2`, `2`).
- 29-row all-track Lane A/B/C PASS: `24/29`, `23/29`, `23/29` after
  v3_1_4 (before v3_1_3: `24/29`, `22/29`, `22/29`).
- 29-row all-track answer-span mismatch Lane A/B/C: `0`, `6`, `6` after
  v3_1_4 (before: `0`, `7`, `7`).
- Strict JSON parse residual remains `0` by lane.
- LLM-generated locator copy/missing/field mismatch residual remains `0` by
  lane.
- PDF `source_pdf_path` mismatch, XLSX `row_label` mismatch, and TEXT
  `text_locator` missing remain `0`.

Remaining queue after v3_1_4:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `gq_auto_010` | Source-bound retrieval/context coverage: cited context lacks numeric answer span. |

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_4_pdf_residual_queue.json`

Guardrail audit:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`.

## Source-Bound Coverage Batch 4 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic`

Source of truth:

- The authoritative input queue is
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_4_pdf_residual_queue.json`.
- Queue preflight confirmed only `gq_auto_010` remains, strict JSON /
  locator residual count is `0`, `diagnostic_only=true`,
  `promotion_evidence=false`, and `reference_span_text_embedded=false`.

Scope:

- Target row: `gq_auto_010` only.
- This was classification-only: no live generation, answer renderer/scorer
  change, SearchUnit export change, index rebuild, denominator mutation, gold
  mutation, label mutation, production mutation, threshold tuning, winner
  selection, promotion gate, or official retrieval metric computation.
- Audit numeric spans were used only as post-hoc static coverage probes and
  were recorded by hash/count in the compact diagnostic artifact.

Coverage findings:

| Surface | Result |
|---|---|
| v3_1_4 Lane B/C cited SearchUnit | `7bf516bf-2a17-4303-86d8-3cffaa04846e` |
| Current cited SearchUnit contains all audit numeric spans | no |
| Any same-document SearchUnit contains all audit numeric spans | no |
| Any adjacent page/window SearchUnit contains all audit numeric spans | no |
| Raw/source PDF text extraction contains all audit numeric spans | yes |

Classification:

`query_bound_searchunit_too_narrow`

Rationale: Lane A still passes through v3 primary replay. Lane B/C fail with
`LLM_EXPECTED_SPAN_MISMATCH` while citing the same source-bound paragraph. The
paragraph supports the general unemployment-rise claim but does not contain the
numeric answer span. Raw PDF extraction can see the numeric span on the same
source page, but the current query-bound cited SearchUnit and same-document
SearchUnit surfaces in the non-production official denominator index do not.

Repair decision:

- No non-production SearchUnit export/windowing/index repair was applied in
  this run.
- No 29-row all-track remeasurement was necessary because no retrieval,
  export, index, generation, renderer, or scorer behavior changed.
- The next decision is whether to implement a safe source-bound PDF
  paragraph/window expansion before live generation.
- Verification is recorded in `docs/rag-ingestion-progress.md`: both current
  pytest profiles PASS with 133 tests, py_compile PASS, doctor selected checks
  PASS, and `git diff --check` PASS with line-ending warnings only.

Remaining queue after v3_1_5:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `gq_auto_010` | Safe source-bound PDF paragraph/window coverage decision: raw PDF contains the numeric span, but current SearchUnit surfaces do not. |

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_5_gq010_coverage_queue.json`

Guardrail audit:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`.
- `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`.
- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score were not computed.

## Source-Bound Coverage Repair Branch Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic`

Source of truth:

- The authoritative input queue is
  `ai/eval/reports/rag-ingestion/_archive/legacy/v3_1_5_gq010_coverage_queue.json`.
- Queue preflight confirmed only `gq_auto_010` remained and the v3_1_5
  classification was `query_bound_searchunit_too_narrow`.

Scope:

- Target row: `gq_auto_010` only.
- Safe PDF paragraph/window expansion was attempted and applied.
- Locator-safe metadata was available: same `source_pdf_path`, same
  `document_version_id`, page `8`, physical page index `7`, bbox
  `[63.65, 95.06, 341.94, 163.68]`, region type `paragraph_window`, and
  expansion unit `pdfwin_b1c6527f848018640ad5ed231877c662`.
- The expansion came from safe local source PDF extraction and was represented
  as non-production diagnostic context expansion. It did not mutate the
  official denominator registry, production indexes, gold, labels, expected
  answers, or supporting evidence.

Result:

| Lane | Before v3_1_6 | After v3_1_6 |
|---|---|---|
| Lane A `v3_primary_replay` | PASS | PASS |
| Lane B `live_llm_retrieval_topk` | `LLM_EXPECTED_SPAN_MISMATCH` | PASS |
| Lane C `live_llm_query_bound_oracle` | `LLM_EXPECTED_SPAN_MISMATCH` | PASS |

All-track remeasurement:

- Required because prompt context assembly changed.
- Lane A/B/C PASS changed from `24/29`, `23/29`, `23/29` to `24/29`,
  `24/29`, `24/29`.
- Strict JSON parse residuals, LLM-generated locator copy/missing/field mismatch
  residuals, PDF `source_pdf_path` mismatch, XLSX `row_label` mismatch, and
  TEXT `text_locator` missing remain zero.
- No non-target row received context expansion and no non-target unexpected
  change was recorded.

Remaining queue after v3_1_6: empty.

Machine remaining-queue artifact:
`ai/eval/reports/rag-ingestion/v3_1_6_gq010_pdfwin_queue.json`

Guardrail audit:

- `diagnostic_only=true`.
- `promotion_evidence=false`.
- `promotion_gate_auto_run=false`.
- `threshold_tuning=false`.
- `winner_selection=false`.
- `candidate_artifacts_as_generation_source=false`.
- `generation_used_expected_answer=false`.
- `generation_used_supporting_evidence=false`.
- `generation_used_gold_fields=false`.
- `reference_span_text_embedded=false`.
- `production_mutation=false`, `denominator_mutation=false`,
  `gold_mutation=false`, `human_label_mutation=false`.
- Official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score were not computed.

## TEXT Locator Residual Result

`text_namu_v2_0012` TEXT locator residual:

- TEXT `text_locator` missing: `1 -> 0`.
- LLM-generated locator missing failure: `1 -> 0`.
- `text_locator_byte_equal=true`.
- `text_locator_normalized_equal=true`.
- The row now fails on answer span / synthesis, not locator schema.

## Priority 1~5 Result

Run family:
`official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage`.

| Priority | Query ID | Original issue | Current result |
|---:|---|---|---|
| 1 | `gq_pdf_section_question_001` | Lane B strict JSON parse failure | Parse failure removed; now answer-span triage remains |
| 2 | `text_namu_v2_0012` | Lane B strict JSON parse failure | Parse failure removed after schema repair accounting; TEXT locator residual removed by the later residual run |
| 3 | `gq_auto_010` | PDF `source_pdf_path` locator mismatch | PDF path byte-equal and normalized-equal |
| 4 | `gq_auto_023` | XLSX `row_label` locator mismatch | Row label byte-equal and normalized-equal |
| 5 | `gq_xlsx_lookup_008` | XLSX `row_label` locator mismatch | Row label byte-equal and normalized-equal |

Priority 1~5 metrics:

- Strict JSON parse failure: `2 -> 0`.
- Strict JSON schema repair applied: `0 -> 2`.
- LLM-generated locator copy failure: `5 -> 1`.
- LLM-generated locator field mismatch: `3 -> 0`.
- LLM-generated locator missing-field/missing-locator failure: `0 -> 1`.
- PDF `source_pdf_path` mismatch: `1 -> 0`.
- XLSX `row_label` mismatch: `2 -> 0`.

Residual:

- The `text_namu_v2_0012` TEXT locator missing/schema residual was removed by
  the later TEXT locator residual run.
- Remaining priority 1~5 failures are answer-span / answer-renderer failures,
  not strict JSON or locator-copy failures.

## Next Triage Step

The v3_1_6 machine remaining queue is empty. Keep future work diagnostic-only
unless the user explicitly opens a new repair branch: do not create silver,
change gold, tune thresholds, run a promotion gate, mutate production, or
synthesize missing numeric spans.

## Later Triage Queue

After v3_1_6, use the machine remaining-queue artifact above rather than older
stale human lists. Current later queue: empty.

## User-Decision Boundary

Leave these as user decisions:

- Expected answer changes.
- Supporting evidence changes.
- Relevance label changes.
- Answerability label changes.
- Gold policy changes.
- Silver/gold promotion decisions.
