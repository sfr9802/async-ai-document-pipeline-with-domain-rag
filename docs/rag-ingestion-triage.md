<!-- xlsx_pdf_source_native_candidate_surface_rebuild_20260620:triage-entry:start -->
- xlsx_pdf_source_native_candidate_surface_rebuild_20260620: Checkpoint A now treats `SourceAtomNonprodRouteSelectedCandidateSurfaceV1` as a dirty partial candidate surface for Checkpoint B. The 2026-06-19/2026-06-20 reports remain historical dirty-run diagnostics only, not official quality evidence and not a basis for new metric comparison. Before any gold29, RunStore-only locator, silver500, or docs/reviewer metric lane resumes, Checkpoint B must select a fresh run ID/checkpoint or recreate the collection and produce a complete manifest. The existing manifest reports `indexed_count=136280`, file-byte manifest hash `sha256:ce82ba9bec39e54902d35812b2b79659a26510058b7cb59733cf0a5c1f544673`, no production namespace, no diagnostic hash vector, and no FAISS active retrieval; because the build resumed from checkpoint, it should be described as dirty/resumed context rather than a fresh full re-upsert.
- Gold plateau remains: corrected report `reports/rag_eval/actual_rag_eval_gold29_xlsx_pdf_candidate_surface_same_source_row_strict_v2_local_bge_m3_local_llm_det_nonprod_20260620/report.json` is report-only and keeps `official_metric=false`, `official_metric_input_rows=0`, and `bounded_evidence_gate_v1`; versus exact baseline `reports/rag_eval/actual_rag_eval_gold29_xlsx_pdf_vector_db_det_reindexed_20260615/report.json`, strict E2E stays `0/29=0.0`, exact/alias answer correctness stays `0/29=0.0`, evidence_recall@10 stays `10/29=0.344828`, gate allowed/insufficient stays `5/24`, and unsupported-after-gate stays `0.0`. Citation-supported rows are `18` versus baseline `22`, provisional judged correctness is `3/29=0.103448`, provisional E2E is `1/29=0.034483`, and `selected_evidence_has_value_missing_axis=23`. Do not describe this as a strict quality gain, plateau break, or local-LLM answer-generation result.
- Silver is diagnostic churn, not promotion evidence: corrected silver `reports/rag_eval/actual_rag_eval_silver500_xlsx_candidate_surface_same_source_row_strict_v3_local_bge_m3_det_nonprod_20260620/report.json` keeps strict denominators skipped (`0/0`, 500 unknown-answerability diagnostic rows). It allows one more row (`7/493 -> 8/492`) but citation-supported rows fall `379 -> 303`, provisional judged correctness is `3/500=0.006`, weak_evidence_match_recall@10 is `0/500=0.0`, and residual `selected_evidence_has_value_missing_axis=478`.
- RunStore locator triage: final auditable RunStore `reports/rag_eval/actual_rag_eval_gold29_xlsx_locator_runstore_same_source_row_strict_v3_local_bge_m3_local_llm_20260620/run.sqlite` emitted only `run.sqlite`, records `anchor_classifier_model=gemma4-e2b-local`, `official_metric_input_rows=0`, 29 items, 11 tool invocations, 31 candidates, 0 accepted, all 31 rejected as `missing_validated_required_axes_after_tool`, `complete_validated_axis_candidate_count=0`, one split-axis row, `source_row_context_candidate_count=0`, and gate/residual delta 0. The single source-row-context doc-identity mismatch is fail-closed and candidate-auditable through `tool_candidates.source_row_context_source_atom_id` and `tool_candidates.source_row_context_doc_id`.
- Remaining bottleneck: same-candidate axis co-location remains blocked by mixed `period`, `row_entity`, `target_column`, and `display_value` gaps, not just period provenance. In the corrected RunStore, best-candidate missing-axis patterns include `["row_entity","display_value"]` on five invocations, `["period"]` on two, `["period","display_value"]` on two, and broader mixed gaps on two. Borrowing axes across same sheet/range remains unsafe unless the source-owned identity proof is strong enough to satisfy the unchanged gate; removing required axes would be gate loosening.
- Boundary and next checkpoint: leak/raw-payload scans over corrected reports and the auditable RunStore found no raw prompt/response/tool payload, authorization, API key, or secret strings. RunStore guardrails saw forbidden `title`, `workbook_id`, and `workbook_version_id` metadata but did not use or reject them (`forbidden_input_fields_used=[]`, `forbidden_input_fields_rejected=[]`); candidate inputs stayed source-owned locator/date/display metadata. Do not open official metrics, source intake/indexing, latest/current pointers, gold/silver/qrels/labels/expected/denominator mutation, raw XLSX/PDF query-time parsing, formula/normalized-value shortcuts, title/file shortcuts, row-specific repairs, retrieved-context-only citation promotion, or gate loosening. Korean-public external archives remain candidate-only and unprofiled until a later explicit approval opens that successor gate.
<!-- xlsx_pdf_source_native_candidate_surface_rebuild_20260620:triage-entry:end -->

<!-- selected_evidence_failure_decomposition_20260618:triage-entry:start -->
- selected_evidence_failure_decomposition_20260618: The selected-evidence-local-LLM answer-discipline lane remains report-only and non-production after the new decomposition run `reports/rag_eval/actual_rag_eval_selected_evidence_failure_decomposition_nonprod_20260618/report.json`. Gate outcome is unchanged versus the frozen v4 answer-discipline report: allowed/abstained `3/3`, unsupported-before/after `0.5/0.0`, citation_supported `6`, and clean local LLM gate-blocked `2`. The residual split rules out empty retrieval and corpus-coverage expansion for this slice (`retrieval_empty=0`, `selected_evidence_absent=0`, `corpus_coverage_suspected_missing=0`, `coverage_gaps=[]`, `external_archive_recommended=false`) and points instead to selected-evidence anchor/materialization under the unchanged gate (`selected_evidence_anchor_missing=3`, `selected_evidence_value_present_anchor_missing=3`, final-gate `true_insufficient_evidence=3`); two separate pre-fallback local LLM drafts are now counted as `pre_fallback_true_insufficient_evidence=2` rather than final failures. Overfit/leakage and heuristic audits stayed clean for configured rule surfaces: no gold/expected/qrels/labels/IDs as runtime inputs, no row-specific/dataset-specific/literal configured rules, and no raw prompt/response payloads. Next safe target is general selected-evidence package assembly and anchor/value materialization for already-retrieved evidence, not external archive intake, silver/gold mutation, row-specific fixes, local LLM answer polish, or `bounded_evidence_gate_v1` loosening.
- selected_evidence_gate_aligned_fallback_20260618: Follow-up report-only run `reports/rag_eval/actual_rag_eval_selected_evidence_gate_aligned_fallback_nonprod_20260618/report.json` validates the general package-assembly repair without changing `bounded_evidence_gate_v1`: clean local LLM answers that fail the unchanged gate can fall back to a source-native selected-evidence sentence only when that fallback itself validates as `allow_answer`. Live delta versus the decomposition report is allowed/abstained `3/3 -> 4/2`, insufficient packages `3 -> 2`, unsupported-before/after `0.5/0.0 -> 0.333333/0.0`, selected_evidence_anchor_missing `3 -> 2`, selected_evidence_value_present_anchor_missing `3 -> 2`, final-gate true_insufficient_evidence `3 -> 2`, and clean local LLM gate-blocked `2 -> 1`; citation_supported remains `6`. The single measured fallback is `text_namu_v2_0077` (`local_llm_gate_aligned_fallback_count=1`, status `gate_aligned_deterministic_fallback`). `text_namu_v2_0014` and `text_namu_v2_0084` remain blocked, so this is a bounded diagnostic improvement, not an official metric or readiness claim. Dataset sufficiency still reports `coverage_gaps=[]`, `external_archive_recommended=false`, and `external_archive_used=false`; overfit/heuristic/raw-payload audits remain clean, and no latest/current/source-registry/runs/gold/silver/qrels/labels/expected/denominator surface was opened.
<!-- selected_evidence_failure_decomposition_20260618:triage-entry:end -->

<!-- report_namespace_cleanup_v1:triage-entry:start -->
- report_namespace_cleanup_v1: scattered machine-report paths are now physically merged under `reports/rag_eval/`. `reports/` is a tracked public allowlist only; `reports/rag_eval/` is the ignored actual-RAG run/latest/Weaviate-manifest namespace; `reports/rag_eval/rag-ingestion/` is the ignored legacy/current diagnostic ladder namespace moved from `ai/eval/reports/rag-ingestion/`; `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` are the tracked human ledgers; `docs/rag_eval/` is documentation, not a machine report sink. Active entrypoints and legacy report-writing scripts now share the consolidated path contract. Deletion/move triage remains conservative: no protected current/latest/gold/qrels/label/expected/denominator/source-registry/index/silver surface was moved or deleted. Residual test debt is limited to non-current historical suites that still expect older current aliases or archived phase7/legacy fixtures; the current freeze gate and cleanup/path contract pass.
<!-- report_namespace_cleanup_v1:triage-entry:end -->

<!-- portfolio_freeze_v1:triage-entry:start -->
- portfolio_freeze_v1: README/eval README/roadmap/portfolio source claims are aligned to the current non-production latest report `actual_rag_eval_query_formulation_v3_agentic_guard_nonprod_20260614_v4`. Safe public framing is AI backend / agent-ready boundary work: route-selected Weaviate retrieval, SearchUnit/SearchView candidate-only diagnostics, SourceAtom/EvidenceBundle citation evidence truth, selected-evidence citation verification, fail-closed response policy, and redacted trace/report guardrails. Actual Response Smoke is response policy smoke only, not an answer-quality score; XLSX cell/range/axis citation structure is explainable, but XLSX-wide response-smoke success is not claimable. The only test repair was fixture-only: a reject packet fixture stopped sharing the `3기` anchor so it again exercises `likely_reject` under the current conservative evidence-mapping policy. Remaining non-claimable items: official metric, production/live readiness, product success, autonomous agent completion, broader agent-loop ready/opened, final answer quality, strict XLSX/PDF/TEXT headline score, or any gold/qrels/label/expected/denominator mutation.
<!-- portfolio_freeze_v1:triage-entry:end -->

<!-- actual_rag_eval_xlsx_pdf_vector_db_source_evidence_quality:triage-entry:start -->
- actual_rag_eval_xlsx_pdf_vector_db_source_evidence_quality: non-production route-selected SourceAtom v2 was rebuilt/re-upserted (`indexed_count=136280`, `skipped_count=0`, valid manifest) and a separate live schema check returned no mismatches with v2 XLSX/PDF axis properties present. Post-reindex report-only runs are `reports/rag_eval/actual_rag_eval_gold29_xlsx_pdf_vector_db_det_reindexed_20260615/report.json` and `reports/rag_eval/actual_rag_eval_silver500_xlsx_vector_db_det_reindexed_20260615/report.json`; each emitted only `report.json` and kept `--append-registry`/`--write-latest` off. Guardrails stayed closed: evidence gate unchanged, unsupported-after-gate `0.0`, retrieved-context-only citations not promoted, raw prompt/response payloads false, production routing false, and latest/current/source_registry/runs registry/gold/silver/qrels/labels/expected/denominator unchanged. Live impact is partial: gold allowed/insufficient and strict E2E stayed `5/24` and `0.0`, but citation precision/recall improved `0.230769/0.375 -> 0.363636/0.571429`; silver stayed diagnostic-only with allowed/insufficient `7/493`, citation_supported `321 -> 379`, and residual `selected_evidence_has_value_missing_axis=478 -> 479`. Triage conclusion: stale v2 index materialization is resolved, but XLSX selected-evidence assembly remains the main blocker because the XLSX-heavy silver diagnostic lane still has scoped expansion `888/0` while gold stays `38/4`. Next safe target is general source-native XLSX evidence representation/retrieval/package assembly, not raw XLSX/PDF query-time parsing, filename/workbook/title shortcuts, formula/normalized-value shortcuts, new silver rows, denominator changes, row-specific repairs, local LLM repair, or protected-surface mutation.
<!-- actual_rag_eval_xlsx_pdf_vector_db_source_evidence_quality:triage-entry:end -->

<!-- actual_rag_eval_query_formulation_v3_agentic_guard_nonprod:triage-entry:start -->
- actual_rag_eval_query_formulation_v3_agentic_guard_nonprod: Normal route-selected Weaviate query formulation now has `weaviate_query_reformulation_v3` for bounded Korean numeral normalization, punctuation-normalized numeric/title variants, and original-order content-anchor compaction only when a numeric normalization trigger exists; numeric alias replacement is token-boundary based so unrelated Korean substrings are not rewritten. The earlier v2 static English alias gain is retracted from the active path because code-local `X-Men`/`Adversary`/`Project` translations were too heuristic. Fresh report `reports/rag_eval/actual_rag_eval_query_formulation_v3_agentic_guard_nonprod_20260614_v4/report.json` emitted only `report.json`, moved latest pointers, kept planner mode off, and preserved official_metric=false, production routing closed, raw prompt/response artifacts false, retrieved-context-only citation promotion false, and gate loosening false. The current live result is conservative: allowed/blocked remains `5/1`, citation_supported is `8`, query_count_per_item is `4.833333`, and `text_namu_v2_0014` no longer retrieves the target Adversary/Alison line. Agentic execute-once is also narrowed: only sanitized query-text retrieval probes may execute by default; PDF/XLSX tool use, selected-evidence LLM retry, and run-local memory reuse remain deferred without an explicit future execution gate. Triage conclusion: v3 reduces heuristic risk but does not improve the live residual, so broader agent-loop readiness remains false; next work should be source-backed alias/anchor evidence design or selected-package anchor composition under the unchanged gate, not row-specific aliases, gold/qrels/label/expected/denominator mutation, gate loosening, or retrieved-context-only citation promotion.
<!-- actual_rag_eval_query_formulation_v3_agentic_guard_nonprod:triage-entry:end -->

<!-- actual_rag_eval_agentic_loop_review_nonprod:triage-entry:start -->
- actual_rag_eval_agentic_loop_review_nonprod: Broader agent-loop review is now live-measured in `reports/rag_eval/actual_rag_eval_agentic_loop_review_nonprod_20260613/report.json`, emitted as `report.json` only after Weaviate finished startup and became healthy. `agentic_loop_review` remains review-only and fail-closed: `broader_agent_loop_ready=false`, `broader_agent_loop_opened=false`, production routing closed, official metrics false, raw prompt/response payloads false, gate loosening false, retrieved-context-only citation promotion false, and protected/gold/qrels/label/expected/denominator mutation false. Live gate outcome stayed allowed/blocked `5/1`; the lone residual remains `text_namu_v2_0014` with insufficient evidence. The planner proposed `run_local_memory_reuse` for `missing_query_anchor`, but executed no retrieval/tool/LLM/memory action, produced zero gate delta, and kept final citations selected-evidence-only. Triage conclusion: bounded one-action checkpoints are measurable and safe, but this live checkpoint does not prove quality improvement or broader-loop readiness. The residual still requires a general retrieval/query formulation repair under the unchanged gate, not row-specific aliases, expected/qrels/label expansion, gate loosening, or a broad agent loop.
<!-- actual_rag_eval_agentic_loop_review_nonprod:triage-entry:end -->

<!-- actual_rag_eval_agentic_planner_run_local_memory_nonprod:triage-entry:start -->
- actual_rag_eval_agentic_planner_run_local_memory_nonprod: Execute-once now has a bounded run-local memory path. It builds memory only from same-run rows already allowed by the evidence gate and only from their selected SourceAtom/EvidenceBundle evidence, then lets a failed row reuse at most one matching memory context based on query text and source-evidence text overlap before re-running the deterministic composer and unchanged gate. The fake regression proves one insufficient-evidence row can improve from allowed/blocked `1/1` to `2/0` with one memory lookup, zero retrieval, zero tools, zero LLM retry, selected-evidence-only final citations, raw prompt/response artifacts false, and no query_id/row_id/target_id or expected/qrels/label/baseline/legacy inputs. The live six-row route-selected text-gold run is still blocked by Weaviate timeout at `http://localhost:8080`, so no live metric delta exists and latest pointers remain unchanged. Next safe step after Weaviate is reachable is a live execute-once report; broader agent-loop review should remain one-action, fail-closed, and evidence-gated.
<!-- actual_rag_eval_agentic_planner_run_local_memory_nonprod:triage-entry:end -->

<!-- actual_rag_eval_agentic_planner_llm_retry_redesign_nonprod:triage-entry:start -->
- actual_rag_eval_agentic_planner_llm_retry_redesign_nonprod: Execute-once now has a planner-owned selected-evidence LLM rewrite path for `unsupported_generation` failures. It runs after the selected-evidence composer and evidence gate, builds one retry prompt from query text, selected SourceAtom/EvidenceBundle evidence, public gate diagnostics, and bounded previous-answer preview, then accepts the rewrite only if the unchanged evidence gate allows it. The fake regression proves one unsupported-generation row can improve from allowed/blocked `0/1` to `1/0` with exactly one LLM retry, zero extra retrieval, zero tool calls, selected-evidence-only final citations, raw prompt/response artifacts false, and no query_id/row_id/target_id or expected/qrels/label/baseline/legacy inputs. The live six-row route-selected text-gold run is still blocked by Weaviate timeout at `http://localhost:8080`, so no live metric delta exists and latest pointers remain unchanged. Next safe step after Weaviate is reachable is a live execute-once report; run-local memory remains the next design rung, and broader agent loops remain closed.
<!-- actual_rag_eval_agentic_planner_llm_retry_redesign_nonprod:triage-entry:end -->

<!-- actual_rag_eval_agentic_planner_tool_use_narrow_nonprod:triage-entry:start -->
- actual_rag_eval_agentic_planner_tool_use_narrow_nonprod: Execute-once now has one narrow source-derived locator tool path for PDF/XLSX failures, still bounded to non-production actual-RAG diagnostics after selected-evidence composer and evidence gate. The planner classifies insufficient PDF/XLSX retrieved contexts as `tool_required_pdf` or `tool_required_xlsx`, proposes `pdf_locator_tool` or `xlsx_cell_or_table_tool`, and executes at most one locator context derived from retrieved source fields before re-running the deterministic selected-evidence composer and unchanged gate. The fake PDF regression proves one blocked row can improve from allowed/blocked `0/1` to `1/0` with exactly one tool call and zero extra retrieval queries, while official_metric=false, raw prompt/response artifacts false, query_id/row_id/target_id and expected/qrels/label fields absent, retrieved-context-only citation promotion false, and gate loosening false. The live six-row route-selected text-gold run is still blocked by Weaviate timeout at `http://localhost:8080`, so no live metric delta exists and latest pointers remain unchanged. Next safe step after Weaviate is reachable is the same live execute-once tool-use report; broader tool use, memory, and LLM retry remain closed.
<!-- actual_rag_eval_agentic_planner_tool_use_narrow_nonprod:triage-entry:end -->

<!-- actual_rag_eval_agentic_planner_execute_once_nonprod:triage-entry:start -->
- actual_rag_eval_agentic_planner_execute_once_nonprod: Execute-once is implemented as a bounded non-production checkpoint, not a broad agent loop. It runs after selected-evidence composer and evidence gate, ignores scorer `failure_labels` for planner selection, sanitizes the extra retrieval item so query_id/row_id/target_id and expected/qrels/label/baseline/legacy fields cannot steer the probe, executes only query-text/route-selected probe actions, then re-runs the deterministic selected-evidence composer and unchanged evidence gate. Tests prove one fake blocked row can improve from allowed/blocked `0/1` to `1/0` after exactly one extra sanitized query, with official_metric=false, raw prompt/response artifacts false, gate loosening false, and retrieved-context-only citation promotion false. The live six-row route-selected text-gold run remains blocked by Weaviate timeout at `http://localhost:8080`, so no live metric delta exists yet and latest pointers remain unchanged. Next safe step after Weaviate is reachable is the same execute-once live report, not Tool-use/LLM retry/memory broadening.
<!-- actual_rag_eval_agentic_planner_execute_once_nonprod:triage-entry:end -->

<!-- actual_rag_eval_agentic_planner_dry_run_nonprod:triage-entry:start -->
- actual_rag_eval_agentic_planner_dry_run_nonprod: The dry-run planner is implemented as a diagnostic checkpoint after the selected-evidence composer and evidence gate, not as an execution loop. It classifies failed rows and records exactly one proposed action per failed row while preserving the existing gate outcome, official_metric=false, raw prompt/response artifact flags false, production routing closed, and retrieved-context-only citations diagnostic-only. Guardrails reject query_id/row_id/target_id aliasing, expected answer/evidence expansion, qrels/label use, baseline_topk or legacy-output use, per-row alias tables, single-residual composer/gate loosening, planner execution counters, and forbidden decision fields. Focused planner tests and the full metric-generation file pass, including a fake-Weaviate regression proving dry-run does not add retrieval queries beyond the planner-off baseline. The fresh live six-row report is blocked by local Weaviate timeout at `http://localhost:8080`, so there is no new report-backed residual delta and no latest pointer movement. Execute-once is not ready from this evidence; the next safe step is a separate user-approved bounded execution checkpoint after Weaviate is reachable, with unchanged evidence-gate validation as the acceptance condition.
<!-- actual_rag_eval_agentic_planner_dry_run_nonprod:triage-entry:end -->

<!-- actual_rag_eval_adversary_corpus_coverage_audit_nonprod:triage-entry:start -->
- actual_rag_eval_adversary_corpus_coverage_audit_nonprod: The Adversary/Alison Sealy-Smith audit is implemented as an explicit report-only `corpus_coverage_audit` block, selected by `--corpus-coverage-audit-query-id text_namu_v2_0014` plus target anchors. Fresh report `actual_rag_eval_adversary_corpus_coverage_audit_nonprod_20260613_v3` emitted only `report.json`, kept Weaviate route-selected retrieval and rollback_key=`weaviate_full_index_nonprod_rollback`, and kept gold/qrels/labels/answerability/expected/denominator/source-registry/current mutation, official metrics, production routing, broad planner, Memory Agent, Tool Agent, and raw prompt/response artifacts closed. The classification is `tokenization_alias_failure` with corpus_presence=`corpus_present`; source-registry target_anchor_hit=true with matching_source_atom_count=`4`, strong_target_anchor_hit_count=`2`, and active index checkpoint source_atom_id_match_count=`4`; active main retrieval target_anchor_hit=false and collision_count=`3`, while both full-index and route-selected target-anchor probes hit the target anchors (`2` hits each) and route_selected route_filter_sent=true. Therefore the next safe target is normal-query tokenization/alias/query formulation with collision handling, not corpus expansion, route-selected filter rollback, gold mutation, or composer loosening.
<!-- actual_rag_eval_adversary_corpus_coverage_audit_nonprod:triage-entry:end -->

<!-- actual_rag_eval_selected_evidence_same_doc_residual_checkpoint_j_nonprod:triage-entry:start -->
- actual_rag_eval_selected_evidence_same_doc_residual_checkpoint_j_nonprod: Checkpoint J adds bounded same-document residual retrieval for route-selected Weaviate queries with query variants. The residual probe uses only source-owned `doc_id` values already returned by Weaviate plus query-only variants, caps docs and per-doc candidates, records policy=`bounded_query_variant_same_doc_weaviate_v1`, and keeps local corpus scan, FAISS, SearchUnit/SearchView, gold/expected/qrels/labels/IDs, broad planner, and retrieved-context-only citation promotion closed. Fresh report `actual_rag_eval_selected_evidence_same_doc_residual_checkpoint_j_nonprod_20260613` emitted only `report.json`, kept Weaviate route-selected retrieval and rollback_key=`weaviate_full_index_nonprod_rollback`, and kept raw prompt/response artifacts false. Outcome did not improve versus Checkpoint I: allowed/blocked stayed `5/1`, unsupported-after-gate stayed `0.0`, and retrieved-context-only citations stayed `0`. The remaining blocked row is still `text_namu_v2_0014`; same-doc residual retrieval added three contexts from the X-Men document but still no retrieved text/title contains `Adversary`, `애드버서리`, or `어드버서리`, so the composer/gate correctly abstains. Next safe target is an explicit corpus-coverage audit for the Adversary/Alison Sealy-Smith entry before further retrieval broadening.
<!-- actual_rag_eval_selected_evidence_same_doc_residual_checkpoint_j_nonprod:triage-entry:end -->

<!-- actual_rag_eval_selected_evidence_route_query_variant_checkpoint_i_nonprod:triage-entry:start -->
- actual_rag_eval_selected_evidence_route_query_variant_checkpoint_i_nonprod: Checkpoint I adds bounded query-only alias variants for route-selected Weaviate retrieval. The adapter derives at most 8 variants from query text only, records `weaviate_query_reformulation_v1`, round-robin merges variant hits, and keeps full-index rollback in single-query mode. Fresh report `actual_rag_eval_selected_evidence_route_query_variant_checkpoint_i_nonprod_20260613` emitted only `report.json`, kept Weaviate route-selected retrieval and rollback_key=`weaviate_full_index_nonprod_rollback`, and kept raw prompt/response artifacts false. Evidence-gate outcome did not improve versus Checkpoint H: allowed/blocked stayed `5/1`, unsupported-after-gate stayed `0.0`, and retrieved-context-only citations stayed `0`. The remaining blocked row is still `text_namu_v2_0014`; query variants retrieved an `엑스맨 '97` context but no retrieved text/title contains `Adversary`, `애드버서리`, or `어드버서리`, so the composer/gate correctly abstains. Next safe target is a bounded source-owned same-document residual retrieval or corpus-coverage audit for the Adversary entry, not composer loosening, gold mutation, broad planner, or retrieved-context-only citation promotion.
<!-- actual_rag_eval_selected_evidence_route_query_variant_checkpoint_i_nonprod:triage-entry:end -->

<!-- actual_rag_eval_selected_evidence_query_focus_repair_checkpoint_h_nonprod:triage-entry:start -->
- actual_rag_eval_selected_evidence_query_focus_repair_checkpoint_h_nonprod: Checkpoint H repairs two implementation-owned deterministic residuals without touching protected gold/qrels/labels/answerability/expected/denominator/source-registry/current surfaces. The deterministic composer now scores full selected contexts in addition to line/sentence fragments, so line-broken attribute evidence for `text_namu_v2_0012` remains selected and cited; the evidence gate now matches compact Korean anchors to spaced Korean title text, so `소드아트` can be supported by `소드 아트`. Fresh report `actual_rag_eval_selected_evidence_query_focus_repair_checkpoint_h_nonprod_20260612` emitted only `report.json`, kept Weaviate route-selected retrieval and rollback_key=`weaviate_full_index_nonprod_rollback`, and kept raw prompt/response artifacts false. Gate result improved from Checkpoint G deterministic markdown enforce allowed/blocked `3/3` to `5/1`, while unsupported-after-gate stayed `0.0` and retrieved-context-only citations stayed `0`. Remaining blocked row is `text_namu_v2_0014`, missing `구십칠` and `애드버서리`; those anchors are absent from the current retrieved contexts, so the next safe checkpoint is retrieval/query formulation repair for that row, not composer loosening, gold mutation, or retrieved-context-only citation promotion.
<!-- actual_rag_eval_selected_evidence_query_focus_repair_checkpoint_h_nonprod:triage-entry:end -->

<!-- actual_rag_eval_selected_evidence_portfolio_sidecar_checkpoint_g_nonprod:triage-entry:start -->
- actual_rag_eval_selected_evidence_portfolio_sidecar_checkpoint_g_nonprod: Checkpoint G explicit portfolio sidecar is implemented behind `--write-portfolio-experiment-summary` and requires at least one `--portfolio-comparison-report`; routine runs without the flag still emit no portfolio Markdown. Fresh run `actual_rag_eval_selected_evidence_portfolio_sidecar_checkpoint_g_nonprod_20260612_v2` emitted `report.json` plus `portfolio_experiment_summary.md` only because the flag was present. Boundary and guardrails held: Weaviate route-selected, rollback_key=`weaviate_full_index_nonprod_rollback`, raw prompt/response artifacts false, official metric rows `0`, protected mutations false. Sidecar includes answer diff, citation diff, gate before/after, unsupported blocked count, abstain count, selected-evidence citation precision, retrieved-context-only citation count, residual failure taxonomy, and next recommendations; sidecar payload checks found no raw prompt/response fields. The final portfolio diagnostic conclusion is unchanged: deterministic selected-evidence composer is the strongest current lane; local LLM and one-retry remain diagnostic-only and weaker under the gate. Remaining work is future implementation-owned query-focus/evidence-selection repair for the three deterministic blocked rows, not gold/qrels/label mutation.
<!-- actual_rag_eval_selected_evidence_portfolio_sidecar_checkpoint_g_nonprod:triage-entry:end -->

<!-- actual_rag_eval_selected_evidence_comparison_checkpoint_f_nonprod:triage-entry:start -->
- actual_rag_eval_selected_evidence_comparison_checkpoint_f_nonprod: Checkpoint F comparison is implemented as report-only `portfolio_experiment_comparison` behind repeated `--portfolio-comparison-report LABEL=PATH`; compared reports are post-run evidence only and are never composer/generation inputs. Fresh final report `actual_rag_eval_selected_evidence_comparison_checkpoint_f_report_nonprod_20260612` embedded 9 lanes and emitted only `report.json`, with Weaviate route-selected boundary, rollback_key=`weaviate_full_index_nonprod_rollback`, raw prompt/response artifacts false, official metric rows `0`, protected mutations false, and portfolio sidecar false. Extractive-v1 shows the remaining bottleneck clearly: selected-evidence citation precision only `0.183673` because citation_supported=`9` and retrieved_context_only_diagnostic=`40`; enforce blocks `4` rows to hold unsupported-after-gate at `0.0`. Deterministic selected-evidence variants all hold selected-evidence citation precision `1.0`, retrieved_context_only_diagnostic=`0`, unsupported-after-gate `0.0`, and allowed/blocked=`3/3`. Local LLM remains diagnostic-only and weaker: allowed/blocked=`1/5`; bounded retry accepted `0/4` attempts. Residual deterministic failures are implementation-owned query-focus/evidence-selection failures, not gold mutation requests: `text_namu_v2_0012` missing `유우야키`, `text_namu_v2_0014` missing `구십칠`/`애드버서리`, and `text_namu_v2_0084` missing `소드아트`. Next target is Checkpoint G explicit sidecar flag; keep official metrics, gold/qrels/labels/answerability/expected/denominator/source-registry/current mutation, broad planner, Memory Agent, Tool Agent, and raw prompt/response artifacts closed.
<!-- actual_rag_eval_selected_evidence_comparison_checkpoint_f_nonprod:triage-entry:end -->

<!-- actual_rag_eval_selected_evidence_retry_checkpoint_e_nonprod:triage-entry:start -->
- actual_rag_eval_selected_evidence_retry_checkpoint_e_nonprod: Checkpoint E bounded local-composer retry is implemented behind explicit `--selected-evidence-composer-retry-mode bounded-once`. The retry is max one attempt per item, triggers only after evidence-gate insufficiency or query-focus anchor feedback, and its input policy is query text plus selected SourceAtom/EvidenceBundle evidence plus missing query-focus anchors when present plus previous bounded answer preview. It does not use gold/qrels/labels/answerability/expected evidence or answers, denominator fields, query IDs, row IDs, target IDs, baseline top-k, or legacy outputs. Fresh report `actual_rag_eval_selected_evidence_retry_checkpoint_e_nonprod_20260612` used Weaviate route-selected retrieval, emitted only `report.json`, kept rollback_key=`weaviate_full_index_nonprod_rollback`, raw prompt/response artifacts false, official metric rows `0`, protected mutations false, and portfolio sidecar false. Retry summary: attempts=`4`, accepted=`0`, rejected=`4`, errors=`0`, status_counts=`{"not_triggered":2,"rejected_gate_insufficient":4}`. Evidence gate enforce stayed fail-closed: unsupported_answer_rate `0.833333 -> 0.0`, blocked=`5`, allowed=`1`, citation_supported=`6`, retrieved_context_only_diagnostic=`0`. Residuals remain implementation-owned: `text_namu_v2_0012` insufficient evidence; `text_namu_v2_0014`, `text_namu_v2_0017`, `text_namu_v2_0077`, and `text_namu_v2_0084` still missing entity/query anchors after one retry. Next target is Checkpoint F comparison across extractive-v1, deterministic selected-evidence composer, local LLM composer, formatter variants, and evidence-gate diagnostic vs enforce; keep official metrics, gold/qrels/labels/answerability/expected/denominator/source-registry/current mutation, broad planner, Memory Agent, Tool Agent, and raw prompt/response artifacts closed.
<!-- actual_rag_eval_selected_evidence_retry_checkpoint_e_nonprod:triage-entry:end -->

<!-- actual_rag_eval_selected_evidence_local_llm_checkpoint_d_nonprod:triage-entry:start -->
- actual_rag_eval_selected_evidence_local_llm_checkpoint_d_nonprod: Checkpoint D optional local LLM selected-evidence composer is implemented behind explicit `--answer-composer selected-evidence-local-llm-v1` and reuses the existing localhost-only helper. Fresh report `actual_rag_eval_selected_evidence_local_llm_checkpoint_d_nonprod_20260612` used Weaviate route-selected SourceAtom/EvidenceBundle retrieval, emitted only `report.json`, kept rollback_key=`weaviate_full_index_nonprod_rollback`, raw prompt/response artifacts false, official metric false, and protected mutations false. Local helper was available: status counts `generated=5`, `unsupported_or_empty_deterministic_fallback=1`; only hashes, bounded previews, and backend/status metadata are persisted. Evidence gate enforce kept unsupported_answer_rate after gate at `0.0`, but local generation regressed gate compatibility versus Checkpoint C: allowed `3 -> 1`, blocked `3 -> 5`, citation_supported `8 -> 6`, retrieved_context_only_diagnostic stays `0`. Residuals: `text_namu_v2_0012`=`insufficient_evidence`; `text_namu_v2_0014`, `text_namu_v2_0017`, `text_namu_v2_0077`, `text_namu_v2_0084`=`missing_entity_anchor`. Next target is Checkpoint E bounded one-retry using only query text, selected evidence, missing anchors, and previous bounded answer preview; do not open gold/qrels/labels/answerability/expected/denominator/source-registry/current mutation, broad planner, Memory Agent, Tool Agent, or raw prompt/response artifacts.
<!-- actual_rag_eval_selected_evidence_local_llm_checkpoint_d_nonprod:triage-entry:end -->

<!-- actual_rag_eval_selected_evidence_citation_formatter_checkpoint_c_nonprod:triage-entry:start -->
- actual_rag_eval_selected_evidence_citation_formatter_checkpoint_c_nonprod: Checkpoint C selected-evidence citation formatter variants are implemented for the deterministic selected-evidence composer. `--selected-evidence-citation-format` supports `compact`, `evidence-id`, `source-locator`, and `markdown-portfolio`; formatter output is display-only under `answer_composer.formatted_citations`, while structured final citations remain selected-evidence-only and are still evidence-gate validated. Fresh report `actual_rag_eval_selected_evidence_citation_formatter_checkpoint_c_nonprod_20260612` used Weaviate route-selected SourceAtom/EvidenceBundle retrieval, emitted only `report.json`, kept rollback_key=`weaviate_full_index_nonprod_rollback`, raw prompt/response artifacts false, official metric false, and protected mutations false. Evidence gate enforce remains compatible: unsupported_answer_rate `0.5 -> 0.0`, unsupported blocked=`3`, citation_supported=`8`, retrieved_context_only_diagnostic=`0`. Residual failures remain `missing_query_anchor` on `text_namu_v2_0012`, `text_namu_v2_0014`, and `text_namu_v2_0084`; this is implementation-owned retry/gate-feedback work, not gold mutation. Next target is Checkpoint D only if an existing localhost-only LLM helper is available; otherwise record deterministic fallback/unavailable and continue to Checkpoint E bounded one-retry design.
<!-- actual_rag_eval_selected_evidence_citation_formatter_checkpoint_c_nonprod:triage-entry:end -->

<!-- actual_rag_eval_selected_evidence_composer_checkpoint_b_nonprod:triage-entry:start -->
- actual_rag_eval_selected_evidence_composer_checkpoint_b_nonprod: Checkpoint A inventory and Checkpoint B deterministic composer are complete for the first six-row non-production route-selected pass. `--answer-composer selected-evidence-deterministic-v1` is explicit and default `extractive-v1` is preserved for comparison. The composer is invoked after Weaviate route-selected SourceAtom/EvidenceBundle retrieval and before evidence-gate enforcement, with input policy `query_text_and_selected_sourceatom_evidence_only_no_gold_qrels_labels_ids_or_baseline`. The fresh report `actual_rag_eval_selected_evidence_composer_checkpoint_b_nonprod_20260612_v4` emitted only `report.json`, kept boundary=`weaviate`, collection=`SourceAtomNonprodRouteSelectedV2`, route_mode=`route_selected`, rollback_key=`weaviate_full_index_nonprod_rollback`, raw prompt/response artifacts false, portfolio sidecar false, and protected mutations false. Evidence gate enforce kept unsupported_answer_rate `0.5 -> 0.0`, blocked `3` unsupported answers, and final citations are selected-evidence-only: supported=`8`, retrieved_context_only_diagnostic=`0`. Focused composer/citation/route-selected tests, current focused profile, syntax, report contract, and protected-surface status checks passed; broad full-file `python -X utf8 -m pytest ai/tests/test_actual_rag_eval_metric_generation.py -q` timed out after `184` seconds, leaving residual risk outside the focused slices. Remaining failures are not a gold-policy question: `text_namu_v2_0012`, `text_namu_v2_0014`, and `text_namu_v2_0084` fail `missing_query_anchor` after gate validation. Next implementation-owned target is Checkpoint C citation formatter variants, then bounded retry only after gate feedback; do not open official metrics, gold/qrels/labels/answerability/expected/denominator/source-registry/current mutation, broad planner, Memory Agent, Tool Agent, or raw prompt/response artifacts.
<!-- actual_rag_eval_selected_evidence_composer_checkpoint_b_nonprod:triage-entry:end -->

<!-- actual_rag_eval_weaviate_source_atom_boundary_nonprod:triage-entry:start -->
- actual_rag_eval_weaviate_source_atom_boundary_nonprod: the SourceAtom/EvidenceBundle retrieval lane now selects route-selected v2 through the explicit non-production default config `ai/eval/configs/weaviate_route_selected_nonprod_default.json`, while preserving the full-index Weaviate rollback config `ai/eval/configs/weaviate_full_index_nonprod_rollback.json`. Routine default run `actual_rag_eval_weaviate_route_selected_nonprod_default_report_only_20260612_v2` emitted exactly `report.json`, selected active_retrieval_backend=`weaviate_hybrid`, active_retrieval_service_boundary=`weaviate`, collection=`SourceAtomNonprodRouteSelectedV2`, schema_version_source_atom=`weaviate_source_atom_v2`, route_planner_version=`weaviate_route_planner_v1`, fallback_used=false, fail_closed_on_unavailable=true, rollback_key=`weaviate_full_index_nonprod_rollback`, and promotion_decision=`blocked_keep_full_index_rollback` because the routine path intentionally does not run A/B. Route filters (`source_family=TEXT`, `granularity=paragraph|heading_context_block|caption`, `retrieval_route=text_general`) are sent to Weaviate; Python post-filtering remains safety validation only.
- actual_rag_eval_weaviate_route_selected_hybrid_store_ab_nonprod: the explicit A/B gate run `actual_rag_eval_weaviate_route_selected_nonprod_default_ab_20260612_v2` validates the route-selected default candidate and writes route sidecars only because `--weaviate-route-ab-mode text,mixed,routed` was supplied. V2 index `SourceAtomNonprodRouteSelectedV2` materializes taxonomy, source-owned structural locator metadata, and metadata-only policy: index_object_count=`136280`, vectorized_object_count=`136184`, metadata_only_object_count=`96`, vectorized_object_ratio=`0.999296`, vectorized_by_granularity=`{"heading_context_block":8,"paragraph":135927,"table_row":249}`, and metadata_only_by_granularity=`{"cell":96}`. The sidecar compares Lane A full-index rollback (`SourceAtomNonprod`), Lane B TEXT-only, Lane C mixed-pool, and Lane D route-selected over the existing 6-row text regression set, plus a 29-row mixed route diagnostic from the existing v5_5 packet. Guardrails are clean in every lane: Weaviate invoked=true; local corpus scan, source-native layered retrieval, diagnostic hash vectors, FAISS active retrieval, and SearchUnit/SearchView candidate surfaces are false; gold/qrels/labels/expected/denominator/current/source-registry/human fields were not mutated; raw prompt/response payloads were not written. TEXT did not degrade: Lane A/B/D weak@10 all `0.666667`, text_route_degradation_count=`0`, text_route_degradation_ok=true. Mixed-route diagnostic confirms route pollution and route-selected recovery: Lane C mixed-pool pollution=`127`, while Lane D route-selected wrong_source_family=`0`; Lane D weak@10 stayed `0.413793` versus Lane C `0.413793`, duplicate rate fell `0.017241 -> 0.0`, and same-doc duplicate rate fell `0.293103 -> 0.151724`. Recommendation is `promote_route_selected_nonprod_default`, with blockers `[]`. Next target is selected-evidence answer composer/citation formatter; broad planner, Memory Agent, Tool Agent, gold expansion, readiness gates, and retrieved-context-only citation promotion remain closed.
<!-- actual_rag_eval_weaviate_source_atom_boundary_nonprod:triage-entry:end -->

<!-- actual_rag_eval_source_native_evidence_gate_nonprod:triage-entry:start -->
- actual_rag_eval_source_native_evidence_gate_nonprod: the bounded evidence/citation gate is ready for the non-production source-native real-RAG lane. Diagnostic mode records decisions without changing generated answers; enforce mode abstains with `제공된 근거만으로는 답할 수 없습니다.` when production-available evidence is insufficient. Fresh diagnostic/enforce runs (`actual_rag_eval_text_gold_evidence_gate_diagnostic_nonprod_20260611_v4` / `actual_rag_eval_text_gold_evidence_gate_enforce_nonprod_20260611_v3`) both selected source_native/hybrid with BGE-M3, replayed the frozen legacy baseline only after retrieval/generation, and wrote explicit quality-gate sidecars beside `report.json`. Current enforce result: `3/6` sufficient packages allowed, `3/6` insufficient packages abstained/blocked, unsupported_answer_rate `0.5 -> 0.0`, guardrails valid with no violations. The blocked rows are not blocked by gold or expected evidence; they fail query-focus anchors against the generated answer plus selected evidence: `text_namu_v2_0012` missing age/birthday anchors, `text_namu_v2_0014` missing Adversary/X-Men-97 anchors, and `text_namu_v2_0084` missing Sword Art/Ordinal anchors. Citation validation now counts only citations into selected SourceAtom/EvidenceBundle evidence as supported (`18`), while retrieved-context-only citation matches (`42`) remain diagnostic. Remaining bottleneck: `extractive-v1` still emits broad extracted answers and broad citation lists, so the next repair target is a bounded selected-evidence answer composer/citation formatter, not an uncontrolled retrieval retry loop or a broad Agentic RAG graph.
<!-- actual_rag_eval_source_native_evidence_gate_nonprod:triage-entry:end -->

<!-- actual_rag_eval_legacy_real_rag_quality_gate_nonprod:triage-entry:start -->
- actual_rag_eval_legacy_real_rag_quality_gate_nonprod: the legacy-free source-native quality gate is ready as non-production diagnostic evidence. It uses the existing `gold_queries_text_namu_v2_1_question_gold_v2.csv` six-row gold set and the frozen `actual_rag_eval_text_gold_single_vector_final_20260611` SearchUnit/SearchView report only for post-run comparison. The fresh run selected source_native/hybrid with BGE-M3 and wrote `report.json` plus explicit quality-gate comparison artifacts because this is not a routine run. Item-level gate rows classify answer delta, evidence package status, evidence/citation support, failure labels, and diagnostic critic state for every query. Current result: `6/6` comparable, `0` not comparable, `3` legacy_wrong_real_correct, `1` both_correct_different_wording, `2` both_wrong_different, `3` sufficient evidence packages, `3` insufficient evidence packages, and guardrails valid with no violations. This does not open official metrics, promotion, product-success, live-readiness, gold/qrels/label/answerability/expected mutation, or a broad agentic loop. Remaining implementation-owned next target is an evidence/citation validator plus abstention policy for the insufficient packages; generator replacement and agentic retrieval loops stay separate later goals.
<!-- actual_rag_eval_legacy_real_rag_quality_gate_nonprod:triage-entry:end -->

<!-- actual_rag_eval_source_native_evidence_resolution_loop_nonprod:triage-entry:start -->
- actual_rag_eval_source_native_evidence_resolution_loop_nonprod: the evidence-resolution loop is closed as non-production diagnostic infrastructure. Routine source-native eval can now generate a reviewable evidence mapping CSV only with `--write-human-review-packet`, keep all human fields blank, ingest a separate human-reviewed CSV through `--reviewed-evidence-mapping-csv`, create a run-local derived overlay plus `reviewed_evidence_mapping_patch.json`, and report denominator_changes without mutating the source dataset or human-owned gold/qrels/labels. The final routine real-data report remains `report.json` only and selected source_native/hybrid with BGE-M3/FAISS. The explicit review-packet run wrote `30` spreadsheet rows. Strict answer/evidence/citation denominators remain closed at `0/0` for the real six rows because answerability is still unknown; provisional judged answer, weak evidence@10, resolved evidence availability, and provisional E2E are all `3/6`. Remaining blockers are human-owned review decisions, not implementation gaps: answerability labels, accepted evidence mappings, expected answer/evidence correctness, relevance labels, and gold policy. Retrieval v2, evidence validator, citation validator, final answer generator, gold expansion, and readiness gate remain separate later goals.
<!-- actual_rag_eval_source_native_evidence_resolution_loop_nonprod:triage-entry:end -->

<!-- actual_rag_eval_source_native_phase0_phase2_full_corpus_bge_m3_nonprod:triage-entry:start -->
- actual_rag_eval_source_native_phase0_phase2_full_corpus_bge_m3_nonprod: Phase 0-2 stabilization is ready as non-production diagnostic infrastructure. Source-native remains the routine candidate surface, SourceAtom/EvidenceBundle remains evidence truth, SearchUnit/SearchView is not the default actual-RAG candidate surface and is available only as explicit legacy/debug comparison, and routine output remains `report.json` only. Full-corpus expected-evidence resolution now finds review-only source-native candidates without mutating gold/qrels or feeding expected evidence into retrieval: 19 candidates, 2 resolved candidates, 4 unresolved rows, 6 collision warnings. BGE-M3/FAISS is active (`BAAI/bge-m3`, `cuda:0`, `IndexFlatIP`, dim 1024, 136280 units); diagnostic hash vectors are not mislabeled as BGE-M3. Remaining blockers are diagnostic-only and actionable: unknown answerability keeps strict answer/evidence denominators closed; 2 rows are present_not_retrieved; 3 have unresolved expected-evidence IDs after review-only resolution; citations and answer judge still fail for part of the six-row diagnostic denominator. Next phase should be retrieval v2 plus evidence/citation validator planning; actual generator, broad agentic planner, gold expansion, and readiness gate remain later-phase and not claimable from this run.
<!-- actual_rag_eval_source_native_phase0_phase2_full_corpus_bge_m3_nonprod:triage-entry:end -->

<!-- actual_rag_eval_source_native_legacy_cleanup_nonprod:triage-entry:start -->
- actual_rag_eval_source_native_legacy_cleanup_nonprod: cleanup/fencing is complete as a non-production maintenance lane. Routine actual-RAG auto surface remains source_native when source-native units are available; SearchUnit/SearchView is explicit legacy comparison/debug only, routine candidate-surface use is disabled, and auto fallback to SearchUnit/SearchView is false. Routine output-mode single remains `report.json` only; legacy sidecars require explicit legacy mode, and human review packet CSV remains the explicit exception. Cleanup report: `reports/rag_eval/rag-ingestion/runs/actual_rag_eval_source_native_legacy_cleanup_nonprod/report.json`. This lane did not tune retrieval ranking, rebuild/replace source-native indexes, move `current`, mutate protected source registry/index/eval query/gold/qrels/labels/answerability/expected/denominator surfaces, write raw prompt/response artifacts, or open official/product/promotion/live-readiness gates. Existing BGE-M3/layered/MMR artifacts are held as diagnostic evidence for separate future repair lanes; remaining debt is source-native ranking/query formulation, BGE-M3 artifacts held read-only with future remeasurement only when explicitly opened or not current, and `extractive-v1` answer generation replacement.
<!-- actual_rag_eval_source_native_legacy_cleanup_nonprod:triage-entry:end -->

<!-- actual_rag_eval_source_native_bge_m3_mmr_nonprod:triage-entry:start -->
- actual_rag_eval_source_native_bge_m3_mmr_nonprod: GPU BGE-M3 source-native index replacement is complete for the non-production actual-RAG routine surface. The additive index at `ai/eval/indexes/rag-data-all-source-citable-nonprod-bge-m3-v1` has embedding_model=`BAAI/bge-m3`, embedding_device=`cuda:0`, dimension=`1024`, chunk_count/faiss_index_ntotal=`136280/136280`, faiss_row_id_mismatch_count=`0`, and closed index-build leakage flags. Fresh fixture and text-golden routine runs selected source_native/hybrid, kept SearchUnit/SearchView as `legacy_comparison_debug_only`, disabled routine SearchUnit/SearchView candidate use, and emitted only `report.json`. Text-golden diagnostic retrieval now reports source-native Hit@K/nDCG plus `mmr_selected` selection diagnostics: selected hit@10=`0.5`, nDCG@10=`0.327377`; vector hit@10=`0.666667`, nDCG@10=`0.559368`; hybrid hit@10=`0.666667`, nDCG@10=`0.502964`; MMR lambda=`0.65` underperformed with hit@10=`0.333333`, nDCG@10=`0.123843`. The local llama.cpp judge run was available (`gemma4-e2b-local`) and added bounded semantic sample judge reasons/confidence without raw prompt/response artifacts, but answer generation itself is still `extractive-v1`. Compared to the diagnostic-hash text run, provisional answer/evidence/E2E diagnostics moved from `0.333333` to `0.5` and source_native_present_not_retrieved_count moved `3 -> 2`; these are diagnostic-only deltas, not official/product/promotion/live-readiness claims. Remaining bottlenecks: source-native ranking/query formulation, MMR candidate selection policy, and real LLM answer generation wiring. Future retrieval-quality lane outside cleanup: evaluate source-native ranking/MMR diagnostics while preserving no gold/qrels/expected/label leakage. No gold/qrels/labels/answerability/expected fields, strict denominator, current alias, source registry truth, production config, official gates, raw prompt/response artifacts, or routine sidecars changed.
<!-- actual_rag_eval_source_native_bge_m3_mmr_nonprod:triage-entry:end -->

<!-- actual_rag_eval_source_native_vector_index_audit_nonprod:triage-entry:start -->
- actual_rag_eval_source_native_vector_index_audit_nonprod: actual-RAG target is source-native RAG, not SearchUnit/SearchView tuning. SearchUnit/SearchView is demoted to `legacy_comparison_debug_only`; SourceAtom/EvidenceBundle remains evidence truth; BM25 is lexical-anchor candidate generation; vector is semantic/paraphrase candidate generation only; hybrid merges BM25/vector candidates; final answers must fail closed or abstain when evidence is insufficient. The latest fixture and text-golden routine reports selected surface=`source_native`, backend=`hybrid`, emitted exactly one `report.json`, and recorded `semantic_quality_claim_allowed=false`. The text-golden audit proves the current local FAISS/id-map path is connected and hydrated (`faiss_index_ntotal/id_map/source_native_unit_count=136280/136280/136280`, faiss_row_id_mismatch_count=0, vector invoked for 6/6 items, 60 vector candidates, 0 hydration failures), but it is still `connected_semantic_quality_unproven` because it uses `codex-diagnostic-hashing-vector-v1` on `cpu_existing_nonprod_index`, not GPU BGE-M3. BM25/vector/hybrid all return non-empty candidate sets, but BM25/vector top-k overlap is 0.0, hybrid carries both candidate families, and vector contribution to final selected top-k is 0.0 while BM25 contribution is 9.5 on average. Post-retrieval target diagnostics remain explicitly non-oracle: BM25/vector/hybrid expected-anchor recall@k is 0.333333/0.166667/0.333333 and target-present-not-retrieved count is 4/5/4; expected/gold/qrels/IDs/baseline fields are not candidate-generation inputs. Remaining bottlenecks are diagnostic-hash embedding quality and source-native ranking after replacement. GPU BGE-M3 index build and hybrid/vector selection remeasurement are future non-cleanup repair lanes before any semantic-quality, product-success, promotion, production-routing, or live-readiness claim. No gold/qrels/labels/answerability/expected fields, strict denominator, current alias, source registry/index contents, official gate, production config, raw prompt/response artifact, or routine sidecar changed.
<!-- actual_rag_eval_source_native_vector_index_audit_nonprod:triage-entry:end -->

<!-- actual_rag_eval_single_artifact_vector_hybrid_nonprod:triage-entry:start -->
- actual_rag_eval_single_artifact_vector_hybrid_nonprod: routine actual-RAG eval artifact sprawl is closed for new default runs: `--output-mode single` writes only `report.json`, while legacy sidecars require explicit legacy mode. The actual eval retrieval path now supports BM25/vector/hybrid/auto and verified `auto` selected hybrid with BGE-M3 embeddings on CUDA plus local FAISS. Human review output is an explicit single CSV exception only. BM25 fallback no longer imports the FAISS-dependent v6_3 module, and missing per-item backend comparisons are reported as unavailable instead of clean zero rates. Remaining weak points are answer quality and citation policy, because generation is still `extractive-v1`; external VectorDB parity remains optional/unconfigured; text-golden strict denominators remain constrained by existing human-owned label/evidence coverage. Query-only candidate generation is enforced for index lookup; expected answers/evidence/qrels/query IDs/row IDs/target IDs/baseline top-k are not candidate-generation inputs. No gold/qrels/labels/answerability labels, strict denominator policy, source registry, current alias, official metric, product-success, promotion, production routing, or live-readiness surface changed.
<!-- actual_rag_eval_single_artifact_vector_hybrid_nonprod:triage-entry:end -->

<!-- actual_rag_eval_evidence_mapping_packet_nonprod:triage-entry:start -->
- actual_rag_eval_evidence_mapping_packet_nonprod: the evidence mapping review packet is wired into actual RAG eval as non-mutating, human-reviewable metric infrastructure. It converts resolver candidates into CSV/JSONL/Markdown/summary sidecars under `reports/rag_eval/<run_id>/`, enriches candidates with source-owned metadata where available, redacts local paths, carries packet counts through summary, registry, latest pointers, comparison, Markdown report, and compact status events, and keeps all human-owned decision fields blank. The latest text-golden packet run still has expected_evidence_id_missing_count=`6` and expected_evidence_id_unresolved_count=`6`; packet candidates=`14`, likely_accept=`0`, possible_match=`0`, review_needed=`9`, likely_reject=`5`, priorities P0/P1/P2/P3/P4=`0/11/0/3/0`, and source metadata resolved/unresolved=`14/0`. Low-confidence candidates are clearer now but still not accepted: blockers are source-family mismatch, missing numeric/date anchors such as `2026년`, `4월`, `16`, and `29일`, and weak/generic overlap without a source-owned mapping. Remaining weak points are human acceptance/rejection of proposed mappings, source-owned doc_id/chunk_id bridge decisions, answerability labels, final citation policy, and final semantic judge policy. Next repair targets: have a human review the packet and, only after explicit approval, add source-owned mapping metadata outside gold/qrels or open a separate human-owned gold/qrels update lane. No retriever ranking, gold/qrels/labels, answerability labels, denominator, official metric, product-success, promotion, production routing, current movement, or live-readiness surface changed.
<!-- actual_rag_eval_evidence_mapping_packet_nonprod:triage-entry:end -->

<!-- actual_rag_eval_expected_evidence_resolution_bridge_nonprod:triage-entry:start -->
- actual_rag_eval_expected_evidence_resolution_bridge_nonprod: the expected-evidence bridge is wired into actual RAG eval as non-mutating metric infrastructure. It resolves high-confidence fixture evidence, writes candidate/review sidecars, and carries evidence-resolution counts through summary, registry, latest pointers, comparison, Markdown report, and compact status events. The text-golden run still has expected_evidence_id_missing_count=`6` and expected_evidence_id_unresolved_count=`6`; index candidate lookup found 14 candidates but all were low-confidence review-only because numeric/date anchors were absent or overlap was generic. Remaining weak points are source-owned evidence ID mapping, answerability labels, accepted gold evidence mappings, final citation policy, and final semantic judge policy. Next repair targets: build a human-reviewable mapping packet from the low-confidence candidates, repair source metadata/doc_id mapping outside gold/qrels, and keep retrieval-ranking changes separate from this diagnostic bridge. No retriever ranking, gold/qrels/labels, denominator, official metric, product-success, promotion, production routing, or live-readiness surface changed.
<!-- actual_rag_eval_expected_evidence_resolution_bridge_nonprod:triage-entry:end -->

<!-- actual_rag_eval_run_accumulation_comparison_nonprod:triage-entry:start -->
- actual_rag_eval_run_accumulation_comparison_nonprod: actual-RAG runs now accumulate through registry/latest/status/index artifacts under the existing report structure, but this remains non-production diagnostic infrastructure. Latest/comparison loaders validate explicit closed-gate fields and fail closed when official rows, protected namespace touches, raw prompt/response payload persistence, gold/qrels/label mutation, denominator mutation, promotion, product-success, or live-readiness flags are ambiguous. Fresh text-golden comparison showed no metric movement: judged_answer_correctness_provisional=`0/6`, weak_evidence_match_recall@10=`0/6`, e2e_rag_success_provisional=`0/3`, citation_precision=`0/13`, citation_recall=`0/3`, retrieval_empty_rate=`0.5`, pipeline_error_count=`0`, gold_missing_count=`6`, expected_evidence_id_unresolved_count=`6`. Remaining weak points are still real: text CSV answerability labels are missing, strict exact/evidence/E2E denominators are unavailable, expected evidence IDs do not resolve, retrieval_empty_rate stays 0.5, the heuristic judge is provisional, and citation/semantic judge policy is not final. Next repair targets: reduce retrieval-empty text queries without ranking shortcuts, repair evidence ID mapping from source-owned metadata, and only then consider stricter human-owned gold/qrels review. No retriever ranking, gold/qrels/labels, denominator, official metric, product-success, promotion, production routing, or live-readiness surface changed.
<!-- actual_rag_eval_run_accumulation_comparison_nonprod:triage-entry:end -->

<!-- actual_rag_eval_metric_semantics_repair_nonprod:triage-entry:start -->
- actual_rag_eval_metric_semantics_repair_nonprod: the first actual-RAG loop remains successful and runnable, but provisional metric semantics were repaired because `e2e_rag_success_provisional` and weak evidence matching were too permissive. Fixed: provisional E2E now fails when the provisional answer judge fails; weak evidence text-only matches require non-generic anchors and all numeric/date anchors from expected answer/evidence; the provisional judge fails when required numeric/date answer anchors are missing from generated text; answer/context consistency and citation/retrieved-context consistency are reported as diagnostic rates rather than quality claims; inferred-answerable metrics are separated and do not mutate unknown gold labels; expected evidence ID missing/unresolved diagnostics are recorded. Repaired text-golden run changed weak_evidence_match_recall@10 from `1/6` to `0/6` and e2e_rag_success_provisional from `1/6` to `0/3` while judged_answer_correctness_provisional stayed `0/6`. Remaining weak points: the heuristic judge is still deterministic and provisional, anchor extraction is simple, exact evidence IDs are unresolved in the current text CSV run, citation policy is not final, and human-owned answerability/relevance/gold decisions remain open. No retriever ranking, gold/qrels/labels, denominator, official metric, product-success, promotion, production routing, or live-readiness surface changed.
<!-- actual_rag_eval_metric_semantics_repair_nonprod:triage-entry:end -->

<!-- actual_rag_eval_pragmatic_metric_generation_nonprod:triage-entry:start -->
- actual_rag_eval_pragmatic_metric_generation_nonprod: pragmatic actual-RAG metric generation is now runnable before final gold policy. Known weak points are intentional and recorded: incomplete gold rows are executable with warnings; strict answer correctness remains exact/alias only; provisional judged correctness defaults to deterministic text/evidence overlap; weak evidence/context support are repair signals, not official quality claims; citation metrics are unavailable or partial when generated citations are absent; the default generator adapter is `extractive-v1` unless a richer repo generation path is wired. Existing text golden CSV compatibility is confirmed, but `gold_queries_text_namu_v2_1_question_gold_v2.csv` lacks answerability labels, so strict answer/evidence/E2E denominators stay unavailable while provisional and diagnostic signals run. Optional `--judge-mode local-llm` can use the existing localhost-only llama.cpp/Ollama/openai-compatible helper when a local Docker/GPU model is running, but automated tests use deterministic fixtures only. Human-owned follow-ups remain expected answers, expected evidence, relevance labels, answerability labels, final citation policy, and final semantic/LLM judge policy. current remains `v6_9_answer_quality_gate_packet_nonprod`; no official metric, product-success, promotion, production routing, gold/qrels mutation, denominator mutation, or retriever-ranking improvement is opened.
<!-- actual_rag_eval_pragmatic_metric_generation_nonprod:triage-entry:end -->

<!-- v6_9_1_retrieval_smoke_pre_review_packet_nonprod:triage-entry:start -->
- v6_9_1_retrieval_smoke_pre_review_packet_nonprod: v5_5/v6_5 bridge remains unusable for current metric unlock (bridgeable_rows=0; legacy_blocked_reason=no_safe_read_only_label_qrels_bridge_available). A new current SearchUnit/SearchView review packet was created with blank human-owned relevance, answerability, qrels, denominator, and expected-evidence fields. Hit@K/MRR/nDCG retrieval ranking metrics remain closed.
<!-- v6_9_1_retrieval_smoke_pre_review_packet_nonprod:triage-entry:end -->

<!-- v6_9_answer_quality_gate_packet_nonprod:triage-entry:start -->
- v6_9_answer_quality_gate_packet_nonprod: answer-quality review preparation is embedded in primary report.json only with hashes for generated answers, citations, expected answers, supporting evidence, and qrels payloads. human-owned pass/fail, relevance, answerability, official denominator, and promotion fields are blank. no official/product/promotion/live-readiness claim is opened.
<!-- v6_9_answer_quality_gate_packet_nonprod:triage-entry:end -->

<!-- v6_8_metric_gated_retrieval_quality_engineering_nonprod:triage-entry:start -->
- v6_8_metric_gated_retrieval_quality_engineering_nonprod: v6_5 bridgeable_rows=0 keeps true RAG retrieval metrics closed; computed_only_denominator=0 with blocked_reason=no_safe_read_only_label_qrels_bridge_available. Engineering diagnostics summarize candidate availability, hydration, and fail-closed counters without scoring Hit@k, MRR, nDCG, tool quality, or answer quality. no official/product/promotion/live-readiness claim is opened.
<!-- v6_8_metric_gated_retrieval_quality_engineering_nonprod:triage-entry:end -->

<!-- v6_7_agentic_retry_fail_closed_policy_nonprod:triage-entry:start -->
- v6_7_agentic_retry_fail_closed_policy_nonprod: RAG/tool path selection, verification, retry count, and fail-closed reasons are embedded in primary report.json only. Retries require a new allowed signal and may not use expected answers, supporting evidence, or qrels. no official/product/promotion/live-readiness claim is opened.
<!-- v6_7_agentic_retry_fail_closed_policy_nonprod:triage-entry:end -->

<!-- v6_6_structured_tool_operation_taxonomy_nonprod:triage-entry:start -->
- v6_6_structured_tool_operation_taxonomy_nonprod: PDF/TEXT/XLSX structured operation states are recorded in primary report.json only. Tool surfaces are unavailable in this diagnostic packet, so tool execution and hydration fail closed without raw tool/prompt/response payloads. SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only; tool outputs are excluded from Hit@k/MRR/nDCG. no official/product/promotion/live-readiness claim is opened.
<!-- v6_6_structured_tool_operation_taxonomy_nonprod:triage-entry:end -->













<!-- v6_5_1_gold29_actual_response_smoke_nonprod:triage-entry:start -->
- v6_5_1_gold29_actual_response_smoke_nonprod: actual response review packet is embedded in primary report.json only. v5_5 gold/qrels/expected/supporting/relevance/answerability artifacts remain read-only; qrels/expected/supporting are hash-only post-render review metadata and never candidate-generation inputs. SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. v7_0 remains a premature marker; v6_6-v6_9 remain missing/unskipped. no official/product/promotion/live-readiness claim is opened.
<!-- v6_5_1_gold29_actual_response_smoke_nonprod:triage-entry:end -->

<!-- v6_5_retrieval_metric_unlock_packet_nonprod:triage-entry:start -->
- v6_5_retrieval_metric_unlock_packet_nonprod: read-only bridge audit for v5_5 keeps approved gold/qrels/expected/supporting/relevance/answerability artifacts immutable and uses them only after sanitized v6_4 candidate generation for bridge eligibility. Non-bridge/ambiguous rows=29 are preserved in the compact in-report human review packet with hashes only. v7_0 remains a premature marker; v6_6-v6_9 remain missing/unskipped, so no v7 completion is claimed. no official/product/promotion/live-readiness claim is opened.
<!-- v6_5_retrieval_metric_unlock_packet_nonprod:triage-entry:end -->

<!-- v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod:triage-entry:start -->
- v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod: `v7_0_e2e_eval_architecture_closeout_nonprod` is preserved and classified as a premature closeout marker. Missing/unskipped required predecessors: none; no v7 completion is claimed from v7_0. `v6_4_e2e_coverage_and_failure_taxonomy_nonprod` is preserved as the historical recovered diagnostic current after 300-row coverage and failure taxonomy checks. v7_0_1 does not move current; live current resolves to `v6_9_answer_quality_gate_packet_nonprod`. Historical recovery movement from `v7_0_e2e_eval_architecture_closeout_nonprod` to `v6_4_e2e_coverage_and_failure_taxonomy_nonprod` is audit context only. no official/product/promotion/live-readiness claim is opened.
<!-- v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod:triage-entry:end -->

<!-- v7_0_e2e_eval_architecture_closeout_nonprod:triage-entry:start -->
- v7_0_e2e_eval_architecture_closeout_nonprod: diagnostic-only E2E evaluation architecture closeout is recorded as a premature marker only. The required predecessor checkpoint gaps are audited, v6_3 is preserved as rollback and source evidence, and remaining gold/qrels/expected evidence/relevance/answerability/official denominator/promotion decisions stay human-owned. current resolves to `v6_9_answer_quality_gate_packet_nonprod`. Its earlier current movement is superseded by the recovered diagnostic current; historical movement was from `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report` to `v7_0_e2e_eval_architecture_closeout_nonprod`; current moved from `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report` to `v7_0_e2e_eval_architecture_closeout_nonprod` historically; rollback key is `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`. no official/product/promotion/live-readiness claim is opened.
<!-- v7_0_e2e_eval_architecture_closeout_nonprod:triage-entry:end -->









































<!-- v6_4_e2e_coverage_and_failure_taxonomy_nonprod:triage-entry:start -->
- v6_4_e2e_coverage_and_failure_taxonomy_nonprod: v6_4 recovery records 300-row vector/BM25/hybrid candidate availability, a bounded SourceAtom/EvidenceBundle evidence-only render expansion, and a failure taxonomy. Retrieval computed-only denominator remains 0, coverage-adjusted denominator remains 300, and current moved from `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report` to `v6_4_e2e_coverage_and_failure_taxonomy_nonprod`. no official/product/promotion/live-readiness claim is opened.
<!-- v6_4_e2e_coverage_and_failure_taxonomy_nonprod:triage-entry:end -->



<!-- v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report:triage-entry:start -->
- v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report: diagnostic-only bge-m3 + FAISS E2E plumbing smoke is available, but retrieval labels/qrels, answer-quality evaluation, performance tuning, quality tuning, reranking, query rewrite, chunking/materialization improvements, and production readiness remain deferred. Vector, BM25, hybrid, structured-tool, E2E pipeline, agentic-answer, and denominator-reality metrics stay separated. Tool outputs cannot improve Hit@k/MRR/nDCG. Evidence-only answer render is not an answer-quality metric. Leakage probes pass for materialization, embedding input, FAISS ID map/query, BM25, hybrid merge, hydration, tool planning/execution, rendering, citation verification, metric computation, report generation, status append, and current alias resolution. The run keeps one primary report.json and does not emit deprecated separate JSON/JSONL report files. current moved from `v6_2_source_derived_materialization_scaleout_and_denominator_reality_check` to `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`; rollback key is `v6_2_source_derived_materialization_scaleout_and_denominator_reality_check`. no official/product/promotion/live-readiness claim is opened.
<!-- v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report:triage-entry:end -->

<!-- v6_2_source_derived_materialization_scaleout_and_denominator_reality_check:triage-entry:start -->
- v6_2_source_derived_materialization_scaleout_and_denominator_reality_check: diagnostic-only source-derived materialization scale is available from the citable non-production SearchView manifest, but v5_8 balanced diagnostic rows are not treated as authorized label truth. computed-only and coverage-adjusted true RAG metrics therefore fail closed with no authorized after-the-fact labels while coverage-adjusted metrics preserve the 300-row attempted denominator. Structured PDF/XLSX/TEXT operations remain tool-lane-only; tool outputs cannot improve Hit@k/MRR/nDCG. Leakage probes pass for materialization, candidate text construction, classify, retrieval, hydrate, tool planning/execution, synthesis, citation verification, metric computation, report generation, status append, and current alias resolution. current moved from `v6_1_true_rag_corpus_expansion_and_metric_split_hardening` to `v6_2_source_derived_materialization_scaleout_and_denominator_reality_check`; rollback key is `v6_1_true_rag_corpus_expansion_and_metric_split_hardening`. no official/product/promotion/live-readiness claim is opened. local LLM/GPU usage is optional and env-gated. Remaining blocker: no authorized after-the-fact labels for the v5_8 balanced diagnostic rows, and optional external VectorDB parity remains disabled/fail-closed.
<!-- v6_2_source_derived_materialization_scaleout_and_denominator_reality_check:triage-entry:end -->

<!-- v6_1_true_rag_corpus_expansion_and_metric_split_hardening:triage-entry:start -->
- v6_1_true_rag_corpus_expansion_and_metric_split_hardening: diagnostic-only true RAG retrieval is restricted to pre-materialized source-derived SearchUnit/SearchView payloads and the repo-local SQLite/BM25 backend. Structured PDF/XLSX/TEXT operations remain tool-lane-only; XLSX calculation, aggregation, filtering, and formula-sensitive operations cannot become true RAG retrieval hits. Leakage probes pass for classify, retrieval, hydrate, tool planning/execution, synthesis, citation verification, metric computation, and report generation. current moved from `v6_0_agentic_true_rag_and_tool_loop_rewrite` to `v6_1_true_rag_corpus_expansion_and_metric_split_hardening`; rollback key is `v6_0_agentic_true_rag_and_tool_loop_rewrite`. true RAG retrieval, structured tool, and agentic answer metrics are separated. local LLM/GPU usage is optional and env-gated. no official/product/promotion/live-readiness claim is opened. Remaining blocker: optional external VectorDB parity is disabled/fail-closed and not required for v6_1.
<!-- v6_1_true_rag_corpus_expansion_and_metric_split_hardening:triage-entry:end -->

<!-- v6_0_agentic_true_rag_and_tool_loop_rewrite:triage-entry:start -->
- v6_0_agentic_true_rag_and_tool_loop_rewrite: existing PDF/XLSX file-level retrieval plus runtime parser/search, archived top-k replay, projection adapters, forced routing, row-specific exceptions, source-title/workbook filename shortcuts, formula shortcuts, normalized answer matching, and qrels/gold/expected/supporting/citation-locator candidate construction are isolated as legacy non-RAG/tool/extraction path. Relaxed gates: nonprod index/cache mutation, current alias movement, local agentic loop execution, and structured tool execution. Retained guardrails: oracle/eval field candidate-input ban, gold/qrels/expected/supporting/relevance/answerability mutation ban, production namespace mutation ban, bounded raw prompt/response storage, and SourceAtom/EvidenceBundle evidence truth. The true RAG lane uses pre-materialized SearchUnit/SearchView over the repo-local SQLite/BM25 hybrid backend. current moved from `v5_6` to `v6_0_agentic_true_rag_and_tool_loop_rewrite`; rollback key is `v5_6`. Remaining blockers are full source-derived gold/silver materialization expansion and optional external VectorDB parity beyond the repo-local hybrid backend.
<!-- v6_0_agentic_true_rag_and_tool_loop_rewrite:triage-entry:end -->

<!-- v6_0_true_rag_retrieval_rewrite:triage-entry:start -->
- v6_0_true_rag_retrieval_rewrite: remaining blockers are a configured real non-production vector/hybrid backend endpoint, backend call proof, and cost proof before `real_vectordb_metric=true` can be set. The current run records backend unavailable fail-closed behavior without fake/noop/replay candidates. Deterministic LangGraph hard guards remain code-owned and cannot be relaxed by LLM adjudication. legacy non-RAG paths stay isolated, and the structured tool lane remains separate from true RAG retrieval. This is diagnostic-only, current remains `v5_6`, and no gold/qrels/labels/expected/supporting evidence, official denominator, production index/source registry mutation, training/fine-tuning/FT-A, promotion, product-success, or live-readiness gate is opened.
<!-- v6_0_true_rag_retrieval_rewrite:triage-entry:end -->

<!-- v5_8_retrieval_metric_evaluation_framework_diagnostic_nonprod:triage-entry:start -->
- v5_8_retrieval_metric_evaluation_framework_diagnostic_nonprod: v5_8 separates official-source smoke, valid-live retrieval, balanced diagnostic, and stress/challenge diagnostic tiers. Attempted rows are never silently dropped: row eligibility and exclusion ledgers record no-candidate/uncomputed rows, leakage quarantine, and denominator tier for every row. Remaining blockers for a real VectorDB metric are a real non-production adapter, isolation proof from target/qrels/baseline/query_id/row_id/case_id/source-title shortcut fields, and real latency/cost counters. Remaining blockers for answer-quality metrics are separate user-owned expected/supporting/pass-fail policy gates; current remains `v5_6`.
<!-- v5_8_retrieval_metric_evaluation_framework_diagnostic_nonprod:triage-entry:end -->

<!-- v5_7_2_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod:triage-entry:start -->
- v5_7_2_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod: two-process fence now removes target/qrels/baseline/topk/query_id/row_id from candidate generation and emits sealed live-hybrid candidate lists from a sanitized SourceAtom projection. valid_live_retrieval_metric_rows=18 and leakage_probe_failed_count=0. Remaining blockers for a real VectorDB retrieval metric: replace the run-local projection with a nonprod VectorDB/hybrid adapter, record real backend latency/cost, prove index/cache readiness without production promotion, add balanced TEXT/PDF/XLSX non-official expansion rows, and keep answer-quality/fine-tuning gates closed until separately opened.
<!-- v5_7_2_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod:triage-entry:end -->

<!-- v5_7_1_retrieval_metric_integrity_audit_diagnostic_nonprod:triage-entry:start -->
- v5_7_1_retrieval_metric_integrity_audit_diagnostic_nonprod: v5_7 prior retrieval metric is reclassified as `diagnostic parity/replay only; not product retrieval quality`. All 29 candidate lists are identical to baseline_topk_new and top-1 equals the target search unit; the 28 eligible rows are `baseline_parity_only`, while the valid live retrieval denominator is 0. Blockers before opening a real VectorDB retrieval metric: replace baseline_topk replay with a query-content-driven live vector/hybrid path, remove query_id/row_id keyed lookup from scoring, prove target/qrels/baseline/expected/supporting/citation fields are unavailable to candidate generation, record nonzero live retrieval latency/cost, and exclude leakage-probe-failed rows from the metric denominator.
<!-- v5_7_1_retrieval_metric_integrity_audit_diagnostic_nonprod:triage-entry:end -->

<!-- v5_7_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod:triage-entry:start -->
- v5_7_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod: heuristic inventory rows=15 are recorded in `reports/rag_eval/rag-ingestion/runs/v5_7_vector_llm_candidate_routing/heuristic_inventory.jsonl` with existing historical occurrences blocked from direct deletion and rejected in the v5_7 route/candidate scoring path. Regression attribution is empty because the v5_7 diagnostic vector candidates preserve the v5_6 full-packet new retrieval baseline; future remediation lanes are pre-classified as route, vector candidate generation, hybrid ranking, evidence assembly, answer synthesis, latency/cost, infrastructure fail-closed, or metric-ineligible. Fine-tuning readiness is reserved only for repeated answer synthesis/citation-discipline failures after retrieval and evidence are correct; retrieval/candidate/evidence-boundary failures are not FT candidates.
<!-- v5_7_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod:triage-entry:end -->

<!-- v5_6_full_packet_route_retrieval_comparison_diagnostic_nonprod:triage-entry:start -->
- v5_6_full_packet_route_retrieval_comparison_diagnostic_nonprod: full v5_5 packet route comparison is diagnostic-only and separate from `current=v5_6`. Row diagnostics keep duplicate supporting_evidence_id rows distinct via citation-locator/search-unit precision keys; duplicate evidence id is an audit note only. Invalid manifest, nonzero official_metric_input_rows, protected namespace touch, raw prompt/response payloads, and answer-metric opening remain fail-closed.
<!-- v5_6_full_packet_route_retrieval_comparison_diagnostic_nonprod:triage-entry:end -->

<!-- runtime_rag_heuristic_generalization_refactor:triage-entry:start -->
### Runtime RAG heuristic generalization refactor

- Scope: remove dataset-shaped runtime heuristics from the app-level PDF table parser and route graph policy layer while keeping the work diagnostic-only.
- PDF table parser: replace the previous Korean economic-table marker/templates with a conservative native-text numeric-grid detector. It extracts explicit repeated row-label/value structures only, preserves page/block/bbox provenance, and does not claim semantic table understanding.
- Route policy: keep row-specific diagnostic policy outside `graph.py` in `route_policy_manifest.json`; the loader rejects schema drift, duplicate IDs, nonzero `official_metric_input_rows`, or protected namespace touches.
- Safe action: use LLM route adjudication only for ambiguous routing inside the existing diagnostic schema; deterministic hard guards and the manifest cannot be relaxed by LLM output.
- Fine-tuning note: treat residual classes that cannot be resolved by deterministic layout parsing, OCR trust metadata, or versioned policy manifests as future fine-tuning-readiness candidates only after split, leakage, source-evidence, and user-owned gold/denominator gates are opened.
- Closed gates: official metric, gold/qrels/labels/expected/supporting evidence, denominator mutation, source registry/index mutation, training/fine-tuning/FT-A, fine-tuning dataset export, checkpoint/job, promotion, product-success evidence, and live-readiness remain closed.
<!-- runtime_rag_heuristic_generalization_refactor:triage-entry:end -->

<!-- nec_2026_local_election_xlsx_source_collection_diagnostic_nonprod:triage-entry:start -->
### NEC 2026 local-election XLSX source collection route

- Scope: `nec_2026_local_election_xlsx` is a direct diagnostic route for the newly downloaded NEC XLSX workbooks. It does not move `current` from `v5_6`.
- Retrieval shape: parsed votes are chunked by contiguous `(request_id, contest_label)` spans (2012 preview spans), raw display rows by request block, and source requests by request id. Default candidate search views use parsed_votes/national_summary atoms only; source_requests and raw_display_rows are excluded from retrieval-default views.
- Code-4 caution: 1 stale manifest/verification counter warning(s) are recorded; verification.json and code-4 sidecars are the authority for actual district rendering.
- Fail-closed status: official_metric_input_rows=0, source_registry_mutated=false, index_rebuilt=false, training_dataset_created=false, fine_tuning_dataset_export_created=false, protected_namespaces_touched=[].
<!-- nec_2026_local_election_xlsx_source_collection_diagnostic_nonprod:triage-entry:end -->

<!-- v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run:triage-entry:start -->
### v5_5 user approval ingestion boundary

- Run key: `v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run`
- Primary artifact: `reports/rag_eval/rag-ingestion/runs/v5_5/report.json`
- Scope: exactly the 29 v5_4 user review packet rows. It excludes all 1000 silver rows, v5_2/v5_3 residual rows, overlay-90, XLSX candidate-state rows, and PDF/TEXT residual taxonomy rows from denominator/label creation.
- Evidence IDs are derived only from `machine_existing_citation_locator_hint`; TEXT uses `cited_chunk_ids`, while XLSX/PDF use `search_unit_id` with the full locator preserved for row-level precision audit.
- Duplicate evidence IDs are recorded as diagnostic metadata, not silently collapsed. Run-local official-eval artifacts are ignored and protected namespaces remain untouched.
- Training, fine-tuning, FT-A, promotion, product-success, and live-readiness remain closed.
<!-- v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run:triage-entry:end -->

<!-- v5_4_user_owned_official_eval_approval_packet:triage-entry:start -->
### v5_4 user-owned official-eval approval packet

- Scope: materialize only the user-owned approval schema, policy template, and 29-row review packet over the existing registry-backed official snapshot.
- Do not fill expected answers, supporting evidence, relevance, answerability, denominator, gold/qrels, promotion, reviewer, or reviewed_at decisions; those remain user-owned and pending_user_review.
- Machine context: `machine_*` columns are non-final review hints copied from existing source rows and are not official metric inputs, qrels, labels, expected answers, supporting evidence approvals, or denominator rows.
- Closed gates: official_metric_dry_run_opened=false, official_metric_input_rows=0, official_metric_input_rows_created=0, training_dataset_created=false, fine_tuning_dataset_export_created=false, promotion_evidence=false, protected_namespaces_touched=[].
<!-- v5_4_user_owned_official_eval_approval_packet:triage-entry:end -->

<!-- v5_3_pdf_text_residual_retrieval_evidence_hardening:triage-entry:start -->
### v5_3 PDF/TEXT residual retrieval/evidence hardening

- Residual basis: frozen v4_7_18 aggregate TEXT misses=118 and PDF misses=60; v5_3 does not create a row-level residual mask.
- Overlay sample: v4_7_16 overlay-90 gives TEXT target_not_in_topk=28/30 and PDF target_not_in_topk=12/30; this is sample triage, not a full-denominator bucket claim.
- Safe action: keep PDF/TEXT candidate/evidence hardening diagnostic-only; reject raw PDF query-time parsing, full-page dumps, expected/supporting text, locator shortcuts, and row-specific thresholds.
- User gate reached: future official-metric dry-run remains blocked until explicit user-owned gold/qrels, expected/supporting evidence, relevance, answerability, denominator, and promotion-policy approvals exist.
- Fail-closed status: v5_3-created official_metric_input_rows=0, official_metric_input_rows_created=0, existing registry-backed official rows remain read-only and are not opened for v5_3 scoring, training_dataset_created=false, fine_tuning_dataset_export_created=false, protected_namespaces_touched=[].
<!-- v5_3_pdf_text_residual_retrieval_evidence_hardening:triage-entry:end -->

<!-- v5_2_xlsx_residual_candidate_only_retrieval_engineering:triage-entry:start -->
### v5_2 XLSX residual candidate-state taxonomy

- Residual basis: frozen v4_7_18 aggregate XLSX result has 299 misses. v5_2 does not create a row-level residual mask.
- Candidate-state buckets: zero_candidate_structural_gap=78, budget_exhausted_diversity_gap=109, bounded_candidate_rank_gap_upper_bound=138, unclassified_residual_overlap_aggregate=299.
- Safe action: future work may probe already-materialized structural/header/axis aliases or deterministic candidate diversity, but v5_2 applies no repair and claims no safe gain.
- Fail-closed status: official_metric_input_rows=0, official_metric_input_rows_created=0, training_dataset_created=false, fine_tuning_dataset_export_created=false, protected_namespaces_touched=[].
<!-- v5_2_xlsx_residual_candidate_only_retrieval_engineering:triage-entry:end -->

<!-- v5_1_official_eval_gate_scaffolding:triage-entry:start -->
### v5_1 official eval gate scaffolding

- User-owned approval artifacts: gold set creation/review, expected answer, expected/supporting evidence, relevance label, answerability label, official denominator policy, gold/qrels policy, and promotion policy. All remain `missing_required_external_input`; Codex may not infer them.
- Codex-owned validator-name placeholders: approval-artifact schema, qrels/gold consistency, expected evidence shape, relevance/answerability labels, denominator policy, protected namespace diff, official-row builder-disabled guard, and training export guard.
- FT readiness compatibility: schema-compatible only, no dataset export. Future examples remain blocked until official eval and user-owned approval gates exist.
- Fail-closed status: official_metric_input_rows=0, official_metric_input_rows_created=0, official_metric_input_rows_scope=v5_1_scaffold_created_rows_only, blocked_by_user_owned_gold_qrels_or_denominator_gate=true, protected_namespaces_touched=[].
<!-- v5_1_official_eval_gate_scaffolding:triage-entry:end -->

<!-- v5_0_v4_closeout_and_v5_gate_plan:triage-entry:start -->
### v5_0 v4 closeout and v5 gate plan

- Basis: `v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` freezes v4 as diagnostic-only source-first, candidate-only, lineage-reproducible work. `v5_0` remains explicit after v5_1; `v4_7_18` remains explicit and checkable.
- User-owned decisions: golden set creation/review, expected answer and expected/supporting evidence judgment, relevance and answerability labels, gold policy, official denominator policy, and promotion policy.
- Codex-owned work: implementation, test, report, path, indexing-scope, protected-surface, and failure-taxonomy work only; ambiguous non-gold choices stay fail-closed and diagnostic-only.
- XLSX residual backlog / engineering backlog: XLSX 299 misses, 78 zero-candidate rows, and 109 budget-exhausted rows remain visible; `accept_materialized_axis_value_overlay_diagnostic_only` remains the frozen v4_7_18 repair decision.
- Official metric opening preconditions: user-approved gold/qrels/labels/expected evidence, frozen denominator, metric definitions, blocked/deferred metric policy, and protected-surface diffs.
- Live-readiness and promotion preconditions: accepted official metrics, live DB/index/cache rollout evidence, redaction/leakage/latency/rollback/monitoring evidence, and user-approved promotion/product-success policy.
<!-- v5_0_v4_closeout_and_v5_gate_plan:triage-entry:end -->

<!-- v4_7_12_layered_retrieval_generalization_and_overfit_audit:triage-entry:start -->
### v4_7_12 Layered Retrieval Generalization Boundary

- Architecture preserved: true; vector-as-evidence violations 0; unsafe shortcuts 0.
- Full PDF replay: eligible 57, env_enabled=false, generated 0.
- Silver retrieval audit: found=true, rows 1000, top fail reasons {'TEXT': 'target_not_in_topk', 'PDF': 'contract_survived_same_track', 'XLSX': 'target_not_in_topk'}.
- Overfit signals: canary-to-full-PDF drop 52, PDF-to-XLSX retrieval drop 0, repeated prefix clusters 11.
- Closed gates: gold/qrels/labels/expected/supporting evidence/denominator/training/FT-A/fine_tuning/promotion/product-success/live-readiness remain closed.
<!-- v4_7_12_layered_retrieval_generalization_and_overfit_audit:triage-entry:end -->
<!-- v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke:triage-entry:start -->
### v4_7_11 Actual LLM Replay Boundary

- Scope: v4_7_10 answer-replay candidates only; the single weak residual row remains fail-closed and excluded from LLM generation.
- Local LLM policy: `RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY=1` plus localhost endpoint availability is required. Disabled/unavailable rows emit no fake, noop, deterministic extractive, raw prompt, or raw response payload.
- Answer audit: generated 9; parsed answers 9; citation rendered/grounded 9/9; claim-support pass/fail 5/4; unsupported claim risk 4; evidence underuse 4; non-Korean flags 0.
- Silver lane: diagnostic_silver_only, status `SILVER_SOURCE_ARTIFACTS_UNAVAILABLE_FAIL_CLOSED`, source files mutated=false, official metric input rows=0, promoted-to-gold count=0.
- Closed gates: official_metric=false, official_metric_input_rows=0, gold/qrels/labels/expected/supporting evidence/denominator/training/FT-A/fine_tuning/promotion/product-success/live-readiness remain closed.
<!-- v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke:triage-entry:end -->
<!-- v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness:triage-entry:start -->
### v4_7_10 PDF Korean Evidence Normalization Boundary

- Scope: v4_7_9 residual weak PDF rows only; v4_7_9 answer-ready rows are protected no-regression rows.
- Repair policy: SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only.
- Bounded repair: spacing-insensitive Korean evidence normalization over the existing query text and existing SourceAtom citation span only; no raw PDF broad scan, hidden target/gold locator, expected/supporting gold text, source-file title shortcut, direct answer-value matching, or full-page dump.
- Result: weak evidence/window 3 -> 1; missing neighbor context 3 -> 1; answer-ready evidence bundles 55 -> 57; spacing-insensitive Korean repairs 2.
- Remaining row-level fail-closed reason: requires user-owned gold/evidence judgment or new source material for the listed row hashes.
- Answer replay: 9 answer-replay candidates remain fail-closed with `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`; no raw prompt or raw response payload is written.
- Closed gates: official_metric=false, official_metric_input_rows=0, gold/qrels/labels/expected/supporting evidence/denominator/training/FT-A/fine_tuning/promotion/product-success/live-readiness remain closed.
<!-- v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness:triage-entry:end -->
<!-- v4_7_9_pdf_evidence_residual_answer_quality_replay:triage-entry:start -->
### v4_7_9 PDF Residual Evidence Replay Boundary

- Scope: v4_7_5 PDF survivor rows only; prior answer-ready rows are protected no-regression rows.
- Repair policy: SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only.
- Bounded repair: same-page SourceAtom/block/window metadata only; no raw PDF broad scan, hidden target/gold locator, expected/supporting gold text, source-file title shortcut, direct answer-value matching, or full-page dump.
- Residual after repair: weak evidence/window 3; missing neighbor context 3.
- Answer replay: 7 repaired candidates were eligible, but local LLM was unavailable and therefore failed closed with `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`.
- Closed gates: official_metric=false, official_metric_input_rows=0, gold/qrels/labels/expected/supporting evidence/denominator/training/FT-A/fine_tuning/promotion/product-success/live-readiness remain closed.
<!-- v4_7_9_pdf_evidence_residual_answer_quality_replay:triage-entry:end -->
<!-- v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion:triage-entry:start -->
### v4_7_8 Test/Doc Dependency Decoupling And Runner Alias Expansion

- Run key: `v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion`
- Primary artifact: `reports/rag_eval/rag-ingestion/runs/v4_7_8/report.json`
- Reference graph: `reports/rag_eval/rag-ingestion/runs/v4_7_8/v3_legacy_hold_reduction_manifest.jsonl` records sample readers for each v3 legacy artifact and separates test/doc readers from script/core readers.
- Archive/purge: safe generated root-level v3 artifacts, v3_16 generated quality payloads, and nonessential ambiguous v3_9 response/taxonomy payloads were copied to an external v4_7_8 archive namespace, SHA-256 verified, and removed repo-local.
- Narrowed holds: documented review packets remain held; retained v3_9 metric/per-family/per-query payloads are `REVIEW_MANUAL_HOLD`; retained v3_17-v3_22 quality payloads remain current contract holds only where current checks or docs still need them.
- Runner consolidation: `ai/scripts/rag_eval.py` owns `current`, `v4_7_8`, prior v4_7 cleanup keys, and verified check-only aliases v3_9_2, v3_10, v3_11, v3_12, v3_13, v3_14, v3_15, v3_18, v3_19, v3_20, v3_21, v3_22. Held entrypoints: v3_16=check returned nonzero or opened a forbidden gate; alias not added, v3_17=check returned nonzero or opened a forbidden gate; alias not added.
- Closed gates: retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator mutation, training, FT-A, fine_tuning, promotion, product-success evidence, and live DB/index/cache readiness.
- Held count: 102; unclassified count: 0; archive copy failures: 0; hash verification failures: 0.
<!-- v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion:triage-entry:end -->
<!-- v4_7_7_v3_legacy_archive_and_runner_consolidation:triage-entry:start -->
### v4_7_7 V3 Legacy Archive And Runner Consolidation

- Run key: `v4_7_7_v3_legacy_archive_and_runner_consolidation`
- Primary artifact: `reports/rag_eval/rag-ingestion/runs/v4_7_7/report.json`
- EXTERNALLY_ARCHIVED_REMOVED: v4_7_6 verified archive copies and removed repo-local generated v3 artifacts.
- EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT: repo-local v3 artifacts still read by current tests/docs remain held with reasons.
- EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET: documented legacy review packet surfaces remain held until their readers move.
- Runner consolidation: `ai/scripts/rag_eval.py` owns the current short key plus safe check aliases `v3_21` and `v3_22`; `v3_16` and older unverified legacy entrypoints remain explicit holds.
- Closed gates: retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator mutation, training, FT-A, fine_tuning, promotion, product-success evidence, and live DB/index/cache readiness.
- Held count: 181; held breakdown: current test/doc contract 133, documented review packet 16, ambiguous generated surface 32. Unclassified count: 0.
<!-- v4_7_7_v3_legacy_archive_and_runner_consolidation:triage-entry:end -->
<!-- v4_7_6_eval_artifact_archive_purge:triage-entry:start -->
### v4_7_6 Eval Artifact Cleanup Decision Boundary

- Run key: `v4_7_6_eval_artifact_archive_purge`
- Primary artifact: `reports/rag_eval/rag-ingestion/runs/v4_7_6/report.json`
- KEEP_PROTECTED: eval queries, source registry, indexes, silver, source-of-truth/gold/qrels/denominator surfaces, raw user review evidence, and non-generated source/test/doc files.
- KEEP_CURRENT_MINIMAL: status ledger, archive manifest, v4_7 lineage short report paths, and current resolver-required compatibility reports.
- ARCHIVE_THEN_REMOVE: verified ignored/generated legacy diagnostic payloads already represented by report/status/docs. Archive copies are hash-verified before repo-local removal.
- DELETE_ONLY: transient Python/pytest caches and empty directories.
- REVIEW_MANUAL_HOLD: ambiguous generated-looking files, raw local path/source disclosure risks, and anything still referenced by tests/docs/core. Held count: 354.
- Closed gates: retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator mutation, training, FT-A, fine_tuning, promotion, product-success evidence, and live DB/index/cache readiness.
<!-- v4_7_6_eval_artifact_archive_purge:triage-entry:end -->
<!-- v4_7_5_pdf_evidence_repair_eval_compaction:triage-entry:start -->
### v4_7_5 PDF Evidence Repair Failure Taxonomy And Cleanup Boundary

- Run key: `v4_7_5_pdf_evidence_repair_eval_compaction`
- Primary artifact: `reports/rag_eval/rag-ingestion/runs/v4_7_5/report.json`
- Evidence boundary: SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. Query-time raw PDF parsing, broad SourceAtom scans, hidden target/gold locators, expected/supporting gold text, and source-file title shortcuts remain disabled.
- Failure taxonomy after repair: RIGHT_PAGE_WEAK_WINDOW 10; CONTEXT_NEIGHBOR_MISSING 10; TABLE_OR_FIGURE_STRUCTURE_LOST 0; UNSUPPORTED_CLAIM_RISK 0; ANSWER_READY 48; CONTRACT_FAIL_CLOSED 10.
- Cleanup boundary: generated ignored artifacts are inventoried in `reports/rag_eval/rag-ingestion/archive_manifest.jsonl` with hashes and classifications. Physical cleanup is skipped because the external archive target was not revalidated in this slice. Protected namespaces, raw user CSV/uploaded review evidence, source manifests, and current-profile v4_7_2/v4_7_3/v4_7_4/v4_7_5 evidence remain preserved.
- XLSX remains parked because v4_7_3 passed XLSX count is 0. This is not official metric, product-success evidence, promotion evidence, FT-A execution, fine-tuning, training data, or live DB/index/cache readiness.
<!-- v4_7_5_pdf_evidence_repair_eval_compaction:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod:triage-entry:start -->
### v4_7_4 PDF Survivor Failure Taxonomy And Decision Boundary

- Run: `official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod`
- Scope: PDF survivor 58 rows from v4_7_3 only. XLSX remains parked because v4_7_3 passed XLSX count is 0.
- Evidence boundary: SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. Query-time raw PDF parsing, broad SourceAtom scans, hidden target/gold locator use, expected/supporting gold text use, and source-file title shortcuts remain disabled.
- Failure buckets: FILE_IDENTITY_MISS 0; FILE_IDENTITY_AMBIGUOUS 0; RIGHT_FILE_WRONG_PAGE 0; RIGHT_PAGE_WEAK_WINDOW 23; TABLE_OR_FIGURE_STRUCTURE_LOST 2; CONTEXT_NEIGHBOR_MISSING 23; EVIDENCE_UNDERUSE 7; OVER_ABSTAIN 0; UNSUPPORTED_CLAIM_RISK 8; ANSWER_READY 35; CONTRACT_FAIL_CLOSED 25.
- It is not official metric, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, not training data, and not live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod:triage-entry:start -->
### v4_7_3 Human-Reviewed Korean Query Candidate Decision Boundary

- Run: `official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod`
- Boundary: this step applies user review decisions to v4_7_2 query candidates only. It does not approve relevance, answerability, expected answers, supporting evidence, qrels, gold records, official denominator rows, or official metric input.
- User clarification: CSV `검수상태=미검수` is not pending for this file; it is interpreted as pass 표기로 override when `제외사유` is blank. Non-empty `제외사유` remains user exclusion text and is preserved in the embedded ledger.
- Applied counters: reviewed rows 204; passed query candidates 58; excluded rows 146; passed PDF 58; passed XLSX 0.
- Residual risks: all passed query candidates are PDF; all XLSX candidates are user-excluded in this review; expected answers/evidence and relevance/answerability labels remain unresolved; official metric and FT-A remain closed.
- It is not official metric, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, not training data, and not live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod:triage-entry:start -->
### v4_7_2 Source-Grounded Korean Query Review Packet Hydration Triage

- Run: `official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod`
- Root cause: v4_7_1 treated missing query text in the registration artifacts as a reason to leave every review query blank, even though source-disjoint candidate sources were registered and extractable source content was available.
- Fix: v4_7_2 searches for linked query fields first, then uses the local LLM in strict-JSON mode to draft source-grounded Korean query candidates from bounded PDF text and XLSX workbook structure. Deterministic query templates stay disabled and unavailable as a fallback.
- Reviewable rows: 204; PDF 100; XLSX 104; extraction_failed 0; non-empty `질의문` 204.
- User-owned fields remain blank/default. Machine draft answer/evidence columns are non-official hints and require review.
- It is not official metric, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, not training data, and not live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod:triage-entry:start -->
### v4_7_1 Korean Review Packet And README Diagnostic Snapshot Triage

- Run: `official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod`
- The packet covers PDF 100 rows and XLSX 104 rows from the accepted v4_7 pre-official candidate manifest registration.
- It is human-review-only. Codex did not fill expected answers, supporting evidence, relevance labels, answerability labels, denominator inclusion, qrels, gold, or promotion decisions.
- The `source_manifest_*` columns and redacted preview/locator columns are filled from SHA-256 matches against the `source_collection` manifest.
- The v4_7 registration artifacts did not contain actual query/answer text, so `질의문`, `기대답변_한국어`, and `근거판단_한국어` remain blank.
- Actual artifact-backed query/answer examples are exported separately in `actual_query_llm_response_examples_ko.csv` from v3_22 answer-allowed LLM rows, not from v4_7.
- It is not official metric, not product-success evidence, not promotion evidence, not FT-A execution, not fine-tuning, and not live DB/index/cache readiness.
- Remaining user-owned actions: provide or adjudicate actual query/evidence context, then decide gold/qrels, expected evidence, relevance, answerability, official denominator inclusion, and promotion policy.
<!-- official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod:triage-entry:start -->
### v4_7 Preofficial External Holdout Candidate Manifest Registration Triage

- Run: `official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod`
- Resolver key: `v4_7_preofficial`; primary report resolves to `reports/rag_eval/rag-ingestion/runs/v4_7_preofficial/report.json`. Legacy long-path alias remains compatibility-only.
- This opens only the v4_7 pre-official external holdout candidate manifest acquisition/registration lane.
- Candidate rows are accepted only if v4_5_1/v4_5_2-compatible validation accepts them, PDF identity is document-level, XLSX identity is workbook-level, prior SourceAtom identity collisions are excluded, leakage buckets are empty, protected oracle fields are absent, and query-fidelity included rows meet the registration target.
- It is not official metric, not FT-A dry-run execution, not fine-tuning, not dataset export, not promotion evidence, not product-success evidence, not production routing, and not live DB/index/cache readiness.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `v4_7_official_metric_gate_opened=false`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, and `live_db_index_cache_readiness=false`.
- User-owned gold/qrels, official denominator, expected-answer evidence, and promotion policy gates remain closed before any official metric or promotion lane.
<!-- official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod:triage-entry:end -->
<!-- v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout:triage-entry:start -->
### v4_6 Input-Waiting FT-A Route-Policy And External-Holdout Readiness Closeout Triage

- Marker: `v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout`
- Latest run remains: `official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod`
- v4_6 completed its Codex-owned diagnostic/preflight work and is now input-waiting.
- v4_6_7 through v4_6_12 were checks only: route parity, dependency freshness, duplicate hygiene, manifest replay, and redaction checks.
- At v4_6 closeout time, before v4_7 pre-official registration, the registration lane was closed because candidate_manifest_present=false, real_holdout_sufficient=false, accepted PDF holdout candidates were 0/20, accepted XLSX holdout candidates were 0/8, and real query-fidelity included rows were 0/100 for PDF and 0/100 for XLSX. Current v4_7 registration resolves only the candidate-manifest/source-disjointness blocker; user-owned gold/qrels, expected evidence, official denominator, and promotion policy gates remain closed.
- Do not open v4_7 official metric, FT-A, promotion, product-success, or live-readiness gates from this marker; do not create official metric rows, training datasets, jobs, checkpoints, promotion evidence, or live readiness claims.
- Next actionable lane: external source-disjoint holdout candidate manifest acquisition/registration, followed by v4_5_1/v4_5_2/v4_6_10 no-write replay.
- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy.
<!-- v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod:triage-entry:start -->
### v4_6_12 External Holdout Runtime Replay Route Parity Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod/report.json`; single-report contract remains active.
- v4_6_12 is diagnostic-only, non-production, and route-parity-probe-only.
- It verifies the FastAPI holdout-candidate validation route matches v4_6_10 transient manifest replay counts/audit state and redacts route validation errors.
- It is not real holdout registration, not candidate manifest export, not validation/source-audit sidecar creation, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `live_db_index_cache_readiness=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion gate.
<!-- official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod:triage-entry:triage-entry:start -->
### v4_6_11 FT-A Runtime Input Validation Route Parity Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod/report.json`; single-report contract remains active.
- v4_6_11 is diagnostic-only, non-production, and runtime-parity-probe-only.
- It verifies the FastAPI FT-A dry-run input validation route preserves v4_6_4 validator counts, rejects forbidden prompt/gold/output and operational fields, redacts validation error input, and stays default-disabled and production-disabled.
- It is not dry-run input manifest export, not FT-A dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `live_db_index_cache_readiness=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion gate.
<!-- official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod:triage-entry:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod:triage-entry:start -->
### v4_6_10 External Holdout Candidate Manifest Gate Replay Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod/report.json`; single-report contract remains active.
- v4_6_10 is diagnostic-only and external-holdout-candidate-manifest-gate-replay-only. The default artifact confirms the external candidate manifest is still missing and keeps the v4_7 opening preflight closed.
- Optional `--candidate-manifest` input is a no-write replay through v4_5_1/v4_5_2 only; it records redacted/hash input metadata and aggregate gate outcomes, not raw candidate rows or raw source identities.
- The default-disabled FastAPI readiness route originally projected the v4_6_10 report's bounded manifest replay/preflight fields, redacted provided manifest input paths, and failed closed on sidecar/raw-surface openings or inconsistent replay counters. Current readiness now defaults to the later v4_6_12 route-parity report while retaining v4_6_10 projection support. The default-disabled FT-A dry-run input validation route reuses the v4_6_4 row-shape contract in memory and returns sanitized/hash-only diagnostics without exporting dry-run inputs, prompt payloads, datasets, jobs, checkpoints, official metrics, promotion evidence, product-success evidence, or live-readiness claims.
- It is not external holdout acquisition, not real holdout availability, not candidate manifest export, not validation/source-audit sidecar creation, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `real_holdout_sufficient=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.
<!-- official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod:triage-entry:start -->
### v4_6_9 Holdout Candidate Duplicate Hygiene Gate Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod/report.json`; single-report contract remains active.
- v4_6_9 is diagnostic-only and duplicate-hygiene-gate-only. It checks that invalid-first duplicate candidate/query IDs fail closed across runtime and v4_5_1 script validation.
- It proves duplicate boundary hardening only; it is not real holdout availability, not external holdout acquisition, not candidate manifest export, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `real_holdout_sufficient=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.
<!-- official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod:triage-entry:start -->
### v4_6_8 Runtime Readiness Dependency Freshness Gate Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod/report.json`; single-report contract remains active.
- v4_6_8 is diagnostic-only, dependency-freshness-gate-only, and external-holdout-acquisition-requirements-packet-only.
- It proves current dependency freshness and FastAPI DTO projection consistency only; it is not real holdout availability, not external holdout acquisition, not candidate manifest export, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `real_holdout_sufficient=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.
<!-- official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod:triage-entry:start -->
### v4_6_7 Holdout Candidate Runtime Gate Parity Bridge Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod/report.json`; single-report contract remains active.
- v4_6_7 is diagnostic-only and parity-bridge-only. It compares runtime-adjacent FastAPI holdout validation with v4_5_1/v4_5_2 script gates using in-memory hash-only probes.
- The bridge proves contract consistency only; it is not real holdout availability, not external holdout acquisition, not candidate manifest export, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `real_holdout_sufficient=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.
<!-- official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod:triage-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod:triage-entry:start -->
### v4_6_6 Holdout Gap And Dry-Run Blocker Ledger Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod/report.json`; single-report contract remains active.
- v4_6_6 is diagnostic-only, non-production, ledger-only infrastructure over existing v4_4 through v4_6_5 reports.
- It is not external holdout acquisition, not candidate manifest export, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- The FastAPI holdout-candidate validation route is an internal, default-disabled, non-writing projection of this contract: candidate rows are request-body input only, accepted/excluded rows are hash-only, raw source identities and local paths are not exposed, and optional prior identity hashes are collision checks rather than persisted ledgers.
- Codex-owned next work remains acquiring or registering source-disjoint candidates and rerunning non-gold gates; user-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion-adjacent evaluation.
<!-- official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod:triage-entry:start -->
### v4_6_5 FT-A Dry-Run Execution Plan Gate Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod/report.json`; single-report contract remains active.
- v4_6_5 is diagnostic-only, non-production, execution-plan-gate-only FT-A dry-run preparation.
- It is not the FT-A dry run, not dry-run execution, not manifest export, not prompt payload creation, not dataset export, and not a v4_7 opening.
- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion-adjacent evaluation.
<!-- official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod:triage-entry:end -->

# RAG Ingestion Triage

<!-- v4_7_18_triage_start -->
- v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility accepts the diagnostic-only materialized axis-value overlay: `accept_materialized_axis_value_overlay_diagnostic_only`. It uses already-materialized SourceAtom axis/header text only and records rejected rules ['direct_normalized_value_matching', 'raw_xlsx_query_time_parsing', 'source_title_or_workbook_shortcut', 'query_id_case_id_hack', 'formula_text_or_formula_evaluation', 'target_or_gold_locator_candidate_scoring']; formatted-value and broader cell scoring remain inconclusive. XLSX improves 17 -> 26 target hits, but still has 299 misses, 78 zero-candidate rows, and 109 budget-exhausted rows. Repeated-prefix projection gains 1 row; explicit demotion/dedup stays inconclusive to avoid row-specific tuning. Lineage reproducibility is reported via `REQUIRED_RUNNER_MODULES_TRACKED_AND_NOT_IGNORED` and ignored report/status artifacts remain local-only.
<!-- v4_7_18_triage_end -->

<!-- v4_7_17_triage_start -->
- v4_7_17_candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit validates the v4_7_16 candidate-only generalization boundary: candidate-set digest matches recomputation and stays stable when target/gold/supporting/query-id fields are poisoned, proving those fields do not construct or score candidates; target labels remain after-the-fact diagnostic evaluation only. XLSX table-axis repair decision remains keep_inconclusive_low_gain_candidate_only: safe sheet/row/column/range axes add 2 target hits from 310 baseline misses, with overlay XLSX target_not_in_topk 28 and repeated-prefix overlap with target miss 20. No direct normalized value matching, raw XLSX query-time parsing, source-title/workbook shortcut, formula exposure, target/gold locator use, silver/gold/qrels, label, expected/supporting evidence, denominator, source registry, cache, production DB, or index mutation.
<!-- v4_7_17_triage_end -->

<!-- v4_7_16_triage_start -->
- v4_7_16_target_recall_repair_prototype diagnostic-only repair decisions: accepted TEXT_SAFE_LEXICAL_SEARCHUNIT_SEARCHVIEW_REPAIR because fixed candidate-only TEXT source-registry tokens gain 212 target hits with zero target-hit regressions; inconclusive XLSX_SAFE_TABLE_AXIS_SEARCHUNIT_SEARCHVIEW_REPAIR because safe sheet/row/column/range axes gain only 2 target hits; rejected DIRECT_NORMALIZED_VALUE_MATCHING, RAW_XLSX_QUERY_TIME_PARSING, SOURCE_FILE_TITLE_SHORTCUT, TARGET_GOLD_EXPECTED_SUPPORTING_LOCATOR_USE, and ROW_SPECIFIC_THRESHOLD_OR_QUERY_ID_HACK. The 90-row v4_7_13 overlay remains summarized as diagnostic queues only: retrieval target not in top-k 68 {'PDF': 12, 'TEXT': 28, 'XLSX': 28}. No silver/gold/qrels, label, expected/supporting evidence, denominator, source registry, cache, production DB, or index mutation.
<!-- v4_7_16_triage_end -->

<!-- v4_7_15_triage_start -->
- v4_7_15_read_only_searchindex_replay_projection diagnostic-only repair projection: retrieval target not in top-k 68 {'TEXT': 28, 'PDF': 12, 'XLSX': 28}; target-hit evidence/context repair 14 {'TEXT': 2, 'PDF': 10, 'XLSX': 2}; query-specificity fixture review 3 {'TEXT': 0, 'PDF': 3, 'XLSX': 0}; no repair projection 5. Secondary overlap: TEXT evidence-window overlap with target miss 28; XLSX repeated-prefix total 22 with 20 target misses and 2 target-hit rows; PDF evidence-window total 16 with 10 target-hit rows, and query-too-broad primary review 3. Diagnostic-only projection; no silver/gold/qrels, label, expected/supporting evidence, denominator, source registry, cache, production DB, or index mutation.
<!-- v4_7_15_triage_end -->

<!-- v4_7_14_triage_start -->
- v4_7_14_diagnostic_precondition_hardening diagnostic-only root-cause queues: TEXT target_not_in_topk 28 and evidence_mismatch_after_family_route 30; XLSX target_not_in_topk 28 and repeated_prefix_cluster 22; PDF evidence_window_insufficient 16, source_family_route_ok_but_evidence_mismatch 17, and query_too_broad 5. These are diagnostic-only queues; silver, gold, qrels, labels, expected/supporting evidence, denominator rows, source registry, cache, production DB, and indexes are not mutated. SearchView/vector payload remains candidate-only; SourceAtom/EvidenceBundle remains evidence truth.
<!-- v4_7_14_triage_end -->

<!-- v4_7_13_triage_start -->
- v4_7_13 live replay status: `LIVE_SILVER_RETRIEVAL_REPLAY_UNAVAILABLE_FAIL_CLOSED`. Full PDF status: `FULL_PDF_LLM_REPLAY_UNAVAILABLE_FAIL_CLOSED`. TEXT silver explanation: TEXT smoke failures are mainly weak-likely-answerable queries whose family route survived but whose target SourceAtom was usually not in top-k, so the selected evidence did not contain enough answer-bearing context. The model therefore produced supported or unsupported insufficient_evidence despite query-level likely_unanswerable=false. SearchView/vector payload remains candidate-only; SourceAtom/EvidenceBundle remains evidence truth.
<!-- v4_7_13_triage_end -->

Last updated: 2026-06-06 KST.

This is the rolling row-level triage ledger. Keep it append-style like
`docs/rag-ingestion-progress.md`: add new triage entries here instead of
creating one Markdown file per run. Machine artifacts should stay compact:
write only the summary, queue, decision/inventory JSONL, and status event that a
triage phase actually needs. For report-style human summaries, append the short
entry to `docs/rag-ingestion-progress.md`; update this file only when row-level
queue or decision-boundary detail belongs here.

Historical `_archive/legacy` artifact paths below are logical provenance names.
Their physical generated payloads may live in the external runtime archive under
redacted external runtime archive paths.
As of the 2026-05-21 cleanup, the current repo-local report directory keeps
`status.jsonl` plus compact current v3_6_9 and later diagnostic artifacts required by the current RAG profile; older triage payloads are consolidated under
the redacted external runtime archive.
The former non-rag report trees, `phase7/` and `legacy-baseline-final/`, are
archived under the same redacted external runtime archive family.

<!-- official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod:triage-entry:start -->
### v4_6_4 FT-A Dry-Run Input Manifest Validator Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod/report.json`; single-report contract remains active.
- v4_6_4 is diagnostic-only, non-production, validator-only FT-A dry-run input manifest preparation.
- It validates manifest row shape and rejects prompt/gold/output leakage; it is not the FT-A dry run, not manifest export, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps raw prompt text, prompt manifests, raw LLM responses, datasets, training manifests, jobs, checkpoints, official metrics, promotion evidence, and product-success evidence absent.
- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion gate.
<!-- official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod:triage-entry:start -->
### v4_6_3 FT-A Prompt-Policy Baseline Schema Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod/report.json`; single-report contract remains active.
- v4_6_3 is diagnostic-only, non-production, schema-only FT-A prompt-policy baseline preparation.
- It freezes prompt-policy baseline identifiers and future dry-run output fields; it is not the FT-A dry run, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps raw prompt text, prompt manifests, raw LLM responses, datasets, training manifests, jobs, checkpoints, official metrics, promotion evidence, and product-success evidence absent.
- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion gate.
<!-- official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod:triage-entry:start -->
### v4_6_2 FT-A Route-Policy Fixture Contract Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod/report.json`; single-report contract remains active.
- v4_6_2 is diagnostic-only, non-production, FT-A route-policy fixture contract only.
- The contract prepares row-shape and leakage/no-go rules only; it is not the FT-A dry run, not dataset export, and not a v4_7 opening.
- It rejects gold/oracle answer text, supporting evidence, target/gold locators, prompt payloads, raw LLM responses, final answers, direct answer values, and local file paths as model inputs.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion gate.
<!-- official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod:triage-entry:start -->
### v4_6_1 Holdout Candidate Manifest Identity Contract Bridge Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod/report.json`; single-report contract remains active.
- v4_6_1 is diagnostic-only, non-production, holdout-candidate manifest identity contract bridge only.
- The bridge proves contract consistency only; it is not split sufficiency, not holdout availability, not the FT-A dry run, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `v4_6_ft_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- No candidate manifest, validation sidecar, training dataset, job, checkpoint, prompt payload, raw LLM response, production route, or live DB/index/cache readiness claim is created.
- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.
<!-- official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod:triage-entry:start -->
### v4_6 FT Route Policy Dry-Run Preflight Triage

- Run: `official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod/report.json`; single-report contract remains active.
- v4_6 is preflight only and is not the FT-A dry run itself.
- The current default run keeps the dry run closed because v4_5, v4_5_1, v4_5_2, and user-owned gold/qrels/denominator policy gates are not open.
- v4_5_3 prior identity baseline provenance is accepted only as hash-only SourceAtom-registry-derived evidence; raw source identities and local paths remain unexposed.
- SearchView/vector payload remains candidate-only; SourceAtom/EvidenceBundle and the source registry remain evidence truth.
- No official metric rows, promotion evidence, product-success evidence, dataset export, training job, checkpoint, production route, or live DB/index/cache readiness claim is created.
- GPU is not required for this deterministic preflight; future FT-A training, embedding, or local LLM workloads should use GPU when the gates actually open.
<!-- official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod:triage-entry:start -->
### v4_5_3 External Holdout Prior Source Identity Ledger Summary Triage

- Run: `official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod/report.json`; single-report contract remains active.
- v4_5_3 is diagnostic hash-only prior identity baseline infrastructure, not a v4_6 fine-tuning dry run.
- Hash records are derived from existing SourceAtom registry PDF document and XLSX workbook identities only; raw local paths and raw source identities are not exposed.
- The summary does not create external holdout candidates, labels, qrels, denominator rows, review packets, training data, jobs, or checkpoints.
- Current default run still has no external candidate manifest, so real holdout availability and source-identity audit gate readiness remain closed.
- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy.
- GPU is not required for this deterministic hash summary; future training, embedding, or LLM/index workloads should use GPU when opened.
<!-- official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod:triage-entry:start -->
### v4_5_2 External Holdout Candidate Source Identity Audit Triage

- Run: `official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod/report.json`; single-report contract remains active.
- v4_5_2 is diagnostic source-identity audit infrastructure over external holdout candidate manifests, not a v4_6 fine-tuning dry run.
- Candidate manifests, raw prior identity ledgers, and v4_5_3 hash-only prior summary reports are read as input only; external paths are redacted and inputs are not copied into the run directory.
- PDF candidates require document-level identity; XLSX candidates require workbook-level identity. XLSX row/cell-level `source_identity` alone is not accepted as workbook-disjoint proof.
- Prior source identity collisions are excluded before candidate counts or query-fidelity rows can satisfy gates.
- Current default run has no manifest; it can consume the v4_5_3 hash-only prior summary baseline, but the source-identity audit gate still fails closed until accepted external candidates exist.
- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy; user-owned label/qrels/denominator policy stays closed.
- GPU is not required for this deterministic source-identity audit; future training, embedding, or LLM/index workloads should use GPU when opened.
<!-- official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod:triage-entry:start -->
### v4_5_1 Holdout Candidate Intake Gate Triage

- Run: `official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod/report.json`; single-report contract remains active.
- v4_5_1 is a diagnostic holdout-candidate intake gate, not a v4_6 fine-tuning dry run.
- Optional candidate manifest paths are read as input only; external paths are redacted and the manifest is not copied into the run directory.
- Current candidate manifest is absent, so accepted PDF source-document-disjoint and XLSX workbook-disjoint candidates remain below target.
- Candidate rows are allowed only when source family, source/workbook identity, disjointness, query-fidelity inclusion, leakage exclusion, protected oracle-field absence, and raw local path absence are satisfied.
- Protected target/gold/expected/supporting fields are rejected as candidate input, not silently used.
- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy; user-owned label/qrels/denominator policy stays closed.
- GPU is not required for this deterministic intake validator; future training, embedding, or LLM/index workloads should use GPU when opened.
- Next lane: provide real source-disjoint PDF/XLSX candidate rows, then rerun the intake gate before opening any v4_6 FT-A dry run.
<!-- official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod:triage-entry:start -->
### v4_5 Fine-Tuning Readiness Packet Triage

- Run: `official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod/report.json`; single-report contract remains active.
- v4_5 is a diagnostic fine-tuning-readiness packet, not actual fine-tuning/training.
- Evidence path quality is read from v4_4 guardrails: SourceAtom/EvidenceBundle remains evidence truth and SearchView/vector remains candidate-only.
- Split quality remains blocked: PDF source-document-disjoint and XLSX workbook-disjoint holdout counts are below target, and real query-fidelity rows remain below the per-family target.
- Leakage audit infrastructure is carried forward as exclusion coverage, not as leakage-free or product-success evidence.
- SFT, DPO, and reward-model lanes are all blocked; no dataset export, training job, prompt payload, raw LLM response, or checkpoint is created.
- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy.
- GPU is not required for this deterministic readiness packet; future training or LLM/index workloads should use GPU when opened.
- Next lane: acquire real source-disjoint PDF/XLSX holdout identities and user-owned label/qrels/denominator policy before opening any fine-tuning dataset export.
<!-- official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod:triage-entry:end -->

<!-- phase1_diagnostic_contract_closure_fastapi_diagnostic_integration:triage-entry:start -->
### Phase 1 Closeout FastAPI Diagnostic Integration Triage

- Marker: `phase1_diagnostic_contract_closure_fastapi_diagnostic_integration`.
- FastAPI surface: diagnostic/internal `POST /internal/rag/diagnostic/query`, `GET /internal/rag/diagnostic/readiness`, `POST /internal/rag/diagnostic/holdout-candidates/validate`, and `POST /internal/rag/diagnostic/ft-a/dry-run-input/validate`, default-disabled by `AIPIPELINE_WORKER_RAG_FASTAPI_DIAGNOSTIC_ROUTE_ENABLED` and disabled in production orchestrator mode.
- The route calls `SourceFirstRagService`; v3 script logic is not embedded directly in the handler.
- The readiness route exposes the hash-locked holdout candidate manifest contract needed by v4_5_1/v4_5_2/v4_5_3/v4_6: accepted source families, PDF/XLSX identity priority, same-tier identity conflict fail-closed behavior, minimum targets, raw external path redaction, and forbidden gold/target/supporting/expected fields. XLSX `source_identity` alone is not workbook proof. It is input-only and creates no candidate manifest, validation sidecar, training dataset, job, checkpoint, official metric, promotion evidence, product-success evidence, or live readiness claim.
- The holdout-candidate validation route accepts only request-body `candidate_rows` plus optional hash-only prior identity records. It rejects missing required contract fields, protected oracle fields, prompt/LLM payload fields, raw local paths, leakage buckets, forbidden readiness/official/promotion fields, XLSX `source_identity`-only workbook proof, same-tier identity conflicts, and prior identity hash collisions. It returns family-separated counts and deficits without creating manifests, sidecars, datasets, jobs, checkpoints, official metrics, promotion evidence, product-success evidence, or live readiness claims.
- The FT-A dry-run input validation route accepts only request-body `manifest_rows`. It rejects missing required v4_6_4 fields, unsupported source families/route lanes/response-policy buckets/prompt-policy ids, and prompt/gold/output/path-like leakage fields, while returning row/query ids as hashes and model input field names only. It creates no dry-run input manifest, prompt payload, prompt manifest, raw LLM response, dataset, training manifest, job, checkpoint, official metric, promotion evidence, product-success evidence, or live readiness claim.
- Query-time policy remains fail-closed for ambiguous workbook/file identity, deictic requests without bounded active context, unsupported large ranges, unavailable index/source-atom store, stale cache namespace mismatch, and any contract violation.
- SearchView/vector payload remains candidate-only; SourceAtom/EvidenceBundle remains evidence truth; XLSX display metadata is bridged into the runtime EvidenceBundle without exposing formula text.
- Formula cached values may be used; formula text is not exposed by default; formulas are not evaluated at query time; raw XLSX/PDF files are not parsed at query time.
- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy.
- Codex-owned non-gold decisions remain implementation, paths, tests, docs, report generation, namespace/indexing scope, failure classification, diagnostic-only classification, and denominator-policy application after user approval.
- Not production routing, not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, not XLSX locator completion, and no production DB/index/cache writes.
<!-- phase1_diagnostic_contract_closure_fastapi_diagnostic_integration:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod:triage-entry:start -->
### v4_4 Real Blind/OOD Holdout And Leakage Audit Triage

- Run: `official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod/report.json`; single-report contract remains active.
- v4_4 materializes holdout, split, query-fidelity, leakage-bucket, and excluded-row ledger infrastructure.
- PDF source-document-disjoint and XLSX workbook-disjoint real holdout rows remain unavailable; TEXT remains comparison/control only.
- Fresh real holdout remains unavailable, so synthetic OOD rows are anti-overfit guards only and cannot be interpreted as product success.
- Leakage buckets classified and excluded: answer_value_in_query, index_to_content_query, source_title_leak, file_title_leak, exact_query_hack, major_topic_drift, unnatural_sheet_or_cell_reference, target_locator_leak, gold_supporting_expected_text_leak.
- Direct normalized answer-value matching, target/gold locator use, expected/supporting gold text use, vector payload as evidence truth, threshold tuning, winner selection, promotion evidence, production routing, and fine-tuning execution remain forbidden.
- GPU is not required for this slice because the runner performs deterministic audit materialization only; future embedding/LLM/index workloads should prefer GPU when available.
- Next lane: v4_5 fine-tuning readiness packet only after preserving these split and leakage gates.
<!-- official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod:triage-entry:start -->
### v4_3 PDF File Identity Confidence And Evidence-Window Split Triage

- Run: `official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod/report.json`; single-report contract remains active.
- v4_3 keeps XLSX/TEXT lanes excluded and reports PDF diagnostics separately.
- The 329-row denominator remains the v3_13 PDF file-identity/evidence-window seen diagnostic surface.
- File identity metrics are kept separate from answer-ready evidence-window metrics; bbox correctness remains uncomputed without independent gold-free evidence.
- PDF file-identity and evidence-window metrics are `reference_only_seen_diagnostic` with `computed_by_v4_3=false`.
- Fresh real source-document-disjoint holdout remains unavailable, so seen-reference/no-regression rows cannot be interpreted as product success.
- Direct normalized-value matching, raw answer value scoring, target/gold locator use, expected/supporting gold text use, source/file title shortcuts, official_metric=false, threshold tuning, winner selection, promotion evidence, production routing, and fine-tuning execution remain forbidden.
- GPU is not required for this slice because the runner performs deterministic JSON materialization only; future embedding/LLM/index workloads should prefer GPU when available.
- Next lane: real blind/OOD holdout and leakage-audit infrastructure.
<!-- official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod:triage-entry:start -->
### v4_2 XLSX Locator v2 Table/Range/Cell Structural Materialization Triage

- Run: `official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod/report.json`; single-report contract remains active.
- v4_2 keeps PDF/TEXT lanes excluded and reports XLSX locator diagnostics separately.
- The 344-row denominator remains the v3_12/v3_15 XLSX locator surface; v4_1 display metadata rows are input readiness only.
- Table/range and cell/value metrics are `reference_only_seen_diagnostic` with `computed_by_v4_2=false`.
- Fresh real workbook-disjoint holdout remains unavailable, so seen-reference/no-regression rows cannot be interpreted as product success.
- Direct normalized-value matching, raw answer value scoring, target/gold locator use, expected/supporting gold text use, source/file title shortcuts, threshold tuning, winner selection, promotion evidence, production routing, and fine-tuning execution remain forbidden.
- GPU is not required for this slice because the runner performs deterministic JSON materialization only; future embedding/LLM/index workloads should prefer GPU when available.
- Next lane: runtime-adjacent XLSX metadata bridge only after preserving this holdout-aware locator contract.
<!-- official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod:triage-entry:start -->
### v4_1 Persisted XLSX SourceAtom Display Metadata Triage

- Run: `official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod/report.json`; single-report contract is active.
- v4_1 closes the first persisted/runtime-adjacent gap after v3_22: XLSX display metadata now exists as SourceAtom-owned manifest fields instead of only report-local runtime fixture data.
- Formula cells carry cached values only; formula text is not exposed and formulas are not evaluated at query time.
- Missing display metadata remains explicit low-confidence raw fallback with FORMAT_METADATA_UNAVAILABLE.
- SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only.
- No raw XLSX query-time parsing, direct normalized-value query matching, target/gold locator use, expected/supporting gold text use, official metric rows, promotion evidence, product-success evidence, production mutation, or fine-tuning execution is allowed.
- GPU is not required for this slice because the runner performs deterministic materialization/replay only; future embedding/LLM/index workloads should prefer GPU when available.
- Next lane: v4_2 XLSX locator v2 table/range/cell structural materialization.
<!-- official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod:triage-entry:end -->

<!-- v4_source_grounded_runtime_locator_and_finetune_readiness:triage-entry:start -->
### v4 Source-Grounded Runtime Locator And Fine-Tuning Readiness Triage

- v4 marker: `v4_source_grounded_runtime_locator_and_finetune_readiness`.
- Recommended run family if a run is created: `official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`.
- Scope: persisted/runtime-adjacent SourceAtom display metadata materialization, family-separated XLSX table/range/cell locator work and XLSX table/range/cell locator improvement, PDF file identity separated from answer-ready evidence-window quality, real blind/OOD holdout and leakage-audit infrastructure, and fine-tuning readiness only after evidence and split quality gates.
- Boundary: v4 is non-production and diagnostic-first. It is not production routing, product success evidence, promotion evidence, official metric lift, live DB/index/cache readiness, actual fine-tuning/training, threshold tuning, winner selection, or a collapsed PDF/XLSX/TEXT headline score.
- Guardrails: SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only; raw XLSX/PDF query-time parsing, direct normalized answer-value query matching, target/gold/supporting/expected locator use, formula evaluation, and formula-text exposure stay closed.
- User-owned decisions remain limited to golden set creation/review, expected answer/evidence judgment, relevance and answerability labels, gold policy, official denominator policy, and promotion policy.
- official metric/promotion only after user-owned gold/qrels/denominator decisions explicitly open that gate.
- Completed v4_1-v4_3: v4_1 persisted XLSX SourceAtom display metadata materialization, v4_2 XLSX locator v2, and v4_3 PDF file identity split. v4_4 real blind/OOD holdout and leakage audit infrastructure is now materialized but still fail-closed on real holdout availability. Next technical lane: v4_5 fine-tuning readiness packet.
<!-- v4_source_grounded_runtime_locator_and_finetune_readiness:triage-entry:end -->

<!-- phase1_diagnostic_contract_closure_after_v3_22:triage-entry:start -->
### Phase 1 Diagnostic Contract Closure After v3_22 Triage

- Closure: `phase1_diagnostic_contract_closure_after_v3_22`.
- Closed scope: SearchView/vector payload candidate-only boundary; SourceAtom/EvidenceBundle evidence-truth boundary; ToolRegistry-only non-production L0-L8 runtime contract; ambiguous/deictic/missing-context fail-closed response policy; live-runtime-like DB/index/cache smoke at non-production contract level only; LLM I/O observability for answer-allowed rows; XLSX display-value and cell/range rendering contract; single-report v3_22 artifact policy; guardrail/status/doc sync hygiene.
- Boundary: diagnostic-only closure after v3_22. It is not production routing, not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, not XLSX locator performance completion, and not representative product performance.
- Carry-forward Phase 2 backlog: persisted XLSX SourceAtom display metadata materialization path; XLSX table/range/cell locator improvement; real workbook/document-disjoint holdout; live DB/index/cache readiness verification; official metric/promotion only after user-owned gold/qrels/denominator decisions.
- User-owned decisions remain limited to golden set creation, golden set review, expected answer/evidence judgment, relevance/answerability label judgment, gold policy decision, and official denominator/promotion policy decision.
<!-- phase1_diagnostic_contract_closure_after_v3_22:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod:triage-entry:start -->
### v3_22 XLSX Display-Value And Cell/Range Rendering Triage

- Run: `official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod/report.json`; single-report contract is active.
- Formatting uses bounded materialized SourceAtom/runtime metadata only; missing or ambiguous display metadata falls back to raw_value with low confidence and FORMAT_METADATA_UNAVAILABLE.
- Formula cells use cached values only; formula text is not exposed and formulas are not evaluated at query time.
- Small ranges render as bounded tables, broad bounded ranges render compact summaries, unsupported large ranges and ambiguous/deictic context-missing rows fail closed without LLM invocation.
- SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only; official_metric_input_rows stays 0.
- This is not production routing, not product success, not promotion evidence, not official metric lift, and not live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod:triage-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod:triage-entry:start -->
### v3_21 Agent Runtime LLM I/O Observability Triage

- Run: `official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod`
- Scope: diagnostic-only non-production packet for actual input query and actual raw LLM response observability after L7 answer-ready context.
- Fail-closed rows do not invoke LLM; unsupported, deictic-context-missing, index unavailable, DB unavailable, and stale cache namespace cases remain policy or adapter fail-closed.
- LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED is recorded when the localhost local LLM backend is unavailable; no noop, deterministic extractive substitute, or smoke final_answer is emitted as raw_llm_response.
- SourceAtom/EvidenceBundle remains evidence truth for prompt evidence previews and parsed final answers; SearchView/vector payload remains candidate-only.
- User-owned review fields remain blank and non-scoring; official_metric_input_rows stays 0.
- This is not production routing and not live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod:triage-entry:end -->

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
  `reports/rag_eval/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/review_packet.csv`.
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
`reports/rag_eval/rag-ingestion/`, together with later compact v3_7/v3_8
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

- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_official_retrieval_qrels.jsonl`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_coverage_summary.json`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_exclusion_ledger.jsonl`

Metric artifacts:

- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_metrics.json`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_per_query.jsonl`

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

- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.jsonl`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.csv`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_human_query_group_review.csv`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_ambiguous_candidate_review.csv`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`

Applied qrels artifacts:

- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_official_retrieval_qrels.jsonl`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_coverage_summary.json`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_exclusion_ledger.jsonl`

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
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`
- `reports/rag_eval/rag-ingestion/status.jsonl`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`

Human-review artifacts:

- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.jsonl`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.csv`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_summary.json`

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

- `reports/rag_eval/rag-ingestion/status.jsonl`
- `ai/eval/eval_queries/official_denominator_registry.json`
- `reports/rag_eval/rag-ingestion/metric_input_v1.json`
- `reports/rag_eval/rag-ingestion/source_bound_readiness_v1.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`

Contract artifacts:

- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_qrels_schema.json`

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
- `reports/rag_eval/rag-ingestion/metric_input_v1.json`
- `reports/rag_eval/rag-ingestion/source_bound_readiness_v1.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/build.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json`
- `ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json`
- `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`

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
- `reports/rag_eval/rag-ingestion/source_bound_readiness_v1.json`
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
  `reports/rag_eval/rag-ingestion/status.jsonl`

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
  `reports/rag_eval/rag-ingestion/status.jsonl`

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
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json`
- Results:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl`
- Failure attribution:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_failure.json`
- Actual response audit:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_audit.jsonl`
- TEXT prompt/span diagnostics:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_text_prompt_span_diagnostics.jsonl`
- Queue:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_queue.json`
- Status event:
  `reports/rag_eval/rag-ingestion/status.jsonl`

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
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_summary.json`
- Results:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_results.jsonl`
- Failure attribution:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_failure.json`
- Actual response audit:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_audit.jsonl`
- PDF context diagnostics:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_pdf_context_diagnostics.jsonl`
- Queue:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_queue.json`
- Status event:
  `reports/rag_eval/rag-ingestion/status.jsonl`

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
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_summary.json`
- Diagnostics:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_pdf_context_provenance_diagnostics.jsonl`
- Recommended queue:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_queue.json`
- Status event:
  `reports/rag_eval/rag-ingestion/status.jsonl`

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
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_summary.json`
- Diagnostics:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_diagnostics.jsonl`
- Reconciled queue:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_queue.json`
- Status event:
  `reports/rag_eval/rag-ingestion/status.jsonl`

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
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline_summary.json`
- v3_2_0 results:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline_results.jsonl`
- v3_2_1 residual triage:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage_residual_triage.jsonl`
- v3_2_2 summary:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement_summary.json`
- v3_2_2 results:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement_results.jsonl`

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
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_summary.json`
- Applied overrides:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_applied_overrides.jsonl`
- Gold diff:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_gold_diff.jsonl`
- Rescored results:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_rescored_results.jsonl`
- Remaining queue:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_remaining_triage_queue.json`

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
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_summary.json`
- Human review packet:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_human_review_packet.json`
- Decision matrix:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_decision_matrix.jsonl`
- Remaining queue:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation_remaining_triage_queue.json`

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
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_summary.json`
- Residual inventory:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_all_track_residual_inventory.jsonl`
- Remaining queue:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_remaining_triage_queue.json`
- User decision packet:
  `reports/rag_eval/rag-ingestion/official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit_user_decision_packet.json`

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
  `reports/rag_eval/rag-ingestion/_archive/legacy/v3_1_1_post_locator_queue.json`.
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
`reports/rag_eval/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json`

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
  `reports/rag_eval/rag-ingestion/_archive/legacy/v3_1_2_span_queue.json`.
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
`reports/rag_eval/rag-ingestion/_archive/legacy/v3_1_3_remaining_queue.json`

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
  `reports/rag_eval/rag-ingestion/_archive/legacy/v3_1_3_remaining_queue.json`.
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
`reports/rag_eval/rag-ingestion/_archive/legacy/v3_1_4_pdf_residual_queue.json`

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
  `reports/rag_eval/rag-ingestion/_archive/legacy/v3_1_4_pdf_residual_queue.json`.
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

<!-- repo_cleanup_20260609_diagnostic_inventory:triage-entry:start -->
### 2026-06-09 Repo Cleanup Diagnostic Decision Boundary

- Run key: `repo_cleanup_20260609_diagnostic_inventory`
- Primary artifact: `reports/rag_eval/rag-ingestion/runs/repo_cleanup_20260609_diagnostic_inventory/report.json`
- ACTIVE_SOURCE / PROTECTED: tracked source, tests, README/docs, `ai/eval/rag_eval_registry.py`, `ai/scripts/rag_eval.py`, current profile tests, official denominator/gold/qrels/eval-query/silver/source-registry/index surfaces, and the `v6_9` current report/status chain.
- DIAGNOSTIC_ARTIFACT_HOLD: ignored `reports/rag_eval/rag-ingestion/**`, report/status/archive manifests, v3-v7 run bundles, sidecars required by report artifact maps, and historical `quality/**` evidence. Do not bulk-delete; external archive plus hash verification is required before any future removal.
- GENERATED_ARTIFACT_HOLD: generated but useful or user-facing local outputs such as portfolio PDFs/reports, `node_modules`, local notes, `output`, `local-storage`, and `.tmp`. `.tmp` is held because recursive inspection produced permission noise in this checkout.
- LEGACY_DIAGNOSTIC_HOLD: v3/v4/v5 scripts and reports that are still registry-, test-, or doc-readable. Preserve compatibility aliases unless a dedicated cleanup run proves readers moved.
- SAFE_TRANSIENT_DELETE: root/AI `.pytest_cache`, Python `__pycache__`/bytecode, `core-api/target`, and `frontend/app/dist`. Initial removal count: 20 directories, 357 files, 6,825,734 bytes; verification-created cache sweeps removed 16 directories/178 files/9,122,698 bytes, 8 directories/72 files/3,747,180 bytes, and 9 directories/123 files/3,652,483 bytes.
- Closed gates: official metric, gold/qrels/labels, expected/supporting evidence, denominator mutation, training, FT-A, fine-tuning, promotion, product-success evidence, production routing, and live DB/index/cache readiness.

<!-- repo_cleanup_20260609_diagnostic_inventory:triage-entry:end -->

- Verification is recorded in `docs/rag-ingestion-progress.md`: both current
  pytest profiles PASS with 133 tests, py_compile PASS, doctor selected checks
  PASS, and `git diff --check` PASS with line-ending warnings only.

Remaining queue after v3_1_5:

| Priority | Query ID | Current issue |
|---:|---|---|
| 1 | `gq_auto_010` | Safe source-bound PDF paragraph/window coverage decision: raw PDF contains the numeric span, but current SearchUnit surfaces do not. |

Machine remaining-queue artifact:
`reports/rag_eval/rag-ingestion/_archive/legacy/v3_1_5_gq010_coverage_queue.json`

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
  `reports/rag_eval/rag-ingestion/_archive/legacy/v3_1_5_gq010_coverage_queue.json`.
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
logical/externalized provenance path
`reports/rag_eval/rag-ingestion/v3_1_6_gq010_pdfwin_queue.json`; the physical
payload is resolved through the external runtime archive when it is not present
repo-locally.

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
