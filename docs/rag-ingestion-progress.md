# RAG Ingestion Progress

Last compacted: 2026-05-07 KST.

This file is the compact status index for RAG ingestion work. It no longer
stores every turn-level log. Command-level detail should live in generated
reports, review packs, and external archive manifests referenced below.

## Current Summary

- The ingestion v2 foundation is implemented on top of the existing
  `source_file -> extracted_artifact -> search_unit` production path.
- XLSX/PDF SearchUnits must keep citation-capable metadata before indexing:
  `parser_version`, `location_json`, and `citation_text`.
- `embedding_text`, `bm25_text`, `display_text`, `citation_text`, and
  `debug_text` remain separate contract fields.
- Current work is split into independent lanes: XLSX, TEXT/NAMU, PDF, and
  answer-shape diagnostics. Do not collapse their denominators.
- Promotion remains conservative. Diagnostic passes are not promotion evidence
  unless a report explicitly says `promotion_evidence=true`.

## Current Lane Status

| Lane | Status | Current denominator / metric | Next action |
|---|---|---|---|
| XLSX retrieval/evidence | `APPROVED_FOR_XLSX_SILVER_GENERATION_STRICT` | Official retrieval/evidence denominator `23`; answer denominator `0`; live smoke `Hit@10=1.0`, `MRR@10=0.942`, citation accuracy `1.0` | Generate XLSX silver only through the strict XLSX wrapper path. Keep answer generation out of scope. |
| XLSX legacy diagnostic | Historical / superseded for wrapper defaults | Legacy Track A reviewed diagnostic denominator `35`; exact location recovered by top 10 | Keep only as historical diagnostic evidence. Do not use as current wrapper default. |
| TEXT/NAMU | Review / candidate-prep lane | Prior diagnostic retrieval positive denominator `47`; current R8 answer denominator `0`; v2 review pack remains non-official | Review v2 candidates and collect actual generated answer output before any R8 citation-support denominator. |
| PDF | Policy/review lane | PDF answer denominator `0`; supplemental/manual review packs prepared; file lookup companion prepared | Finish user/policy review for expected evidence, answerability, table/page/bbox policy, and FILE vs CONTENT routing. |
| PDF/XLSX answer shape | Diagnostic-only | 72 diagnostic rows were exercised; official PDF/XLSX answer denominators remain `0` | Only open answer metrics after inputs contain concrete cited content and policy rows are resolved. |
| Storage/artifacts | Cleaned with protected artifacts held | Workspace reduced to 8.353 GiB after externalizing generated/cache payloads | Keep large raw outputs outside the repo; retain only small current summaries and official registries. |

## Active Guardrails

- Do not run broad candidate indexing. Use scoped identity and
  `allowUnscoped=false`.
- Do not mutate immutable baselines, `rag-data-canary`, or candidate artifacts
  during diagnostic/report-only work.
- Do not treat bootstrap descriptors, diagnostic reports, dry-run previews, or
  local LLM smoke output as promotion evidence.
- Keep hidden XLSX content out of query, gold, candidate, and answer surfaces.
- Keep PDF native text authoritative; OCR fallback remains lower-trust metadata.
- Keep active and historical eval paths separate. Current worker eval code lives
  under `ai-worker/eval/`.
- Current SearchUnit indexing CLI is `python -m app.cli.search_unit_indexing`
  from `ai-worker/`.
- For Phase 7 v4 style eval work, use `rag_chunks.jsonl` for answerability joins;
  do not substitute `chunks_v4.jsonl`.
- Generated raw outputs should prefer an external runtime root such as
  `../_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/`.

## Canonical References

Planning and orientation:

- `docs/codex-rag-ingestion-next-steps.md`
- `docs/rag-ingestion-p1-next-plan.md`
- `docs/track_a_xlsx_retrieval_improvement_plan.md`
- `docs/track_b_text_retrieval_e2e_plan.md`
- `docs/track_c_pdf_embedding_preparation_plan.md`

Current reports and registries:

- `ai-worker/eval/eval_queries/official_denominator_registry.json`
- `ai-worker/eval/reports/rag-ingestion/xlsx_pre_silver_risk_closure_20260507.md`
- `ai-worker/eval/reports/rag-ingestion/xlsx_pre_silver_risk_closure_20260507.json`
- `ai-worker/eval/reports/rag-ingestion/xlsx_end_to_end_preflight_20260507.md`
- `ai-worker/eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_human_review_official_positive_v0_vector_diagnostic_report.json`
- `ai-worker/eval/reports/rag-ingestion/rag_xlsx_human_review_official_positive_v0_retrieval_performance_summary.json`
- `ai-worker/eval/reports/rag-ingestion/rag_text_answer_intent_alignment_report.json`
- `docs/eval/text_answer_intent_prompt_contract.md`
- `docs/eval/pdf_xlsx_answer_intent_prompt_contract.md`

External archive manifests:

- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_210945\external_archive_manifest.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_212609\external_archive_manifest.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_212609\external_archive_manifest.csv`

## Short History

| Date | Milestone |
|---|---|
| 2026-05-03 | Added ingestion v2 schema/provenance foundation and SearchUnit v2 metadata. |
| 2026-05-03 | Exposed v2 citation fields in library search responses and added XLSX smoke tooling. |
| 2026-05-03 | Proved live XLSX/PDF smoke paths and captured initial report artifacts. |
| 2026-05-03 | Added PDF native parser route, batch smoke scaffolding, and report-only promotion gate seed. |
| 2026-05-04 | Hardened SearchUnit indexing identity, hidden XLSX leakage checks, and candidate consistency reports. |
| 2026-05-04 | Achieved full72 candidate embedding consistency pass while keeping promotion blocked. |
| 2026-05-05 | Completed Track A XLSX A0-A6 diagnostic cleanup; no promotion evidence produced. |
| 2026-05-05 | Consolidated A/B/C checkpoint; Track C remained policy-pending and diagnostic-only. |
| 2026-05-06 | Normalized user review signals and kept XLSX/PDF/TEXT denominators separate. |
| 2026-05-06 | Added PDF/XLSX answer-shape serializer/compiler diagnostics; answer denominators stayed `0`. |
| 2026-05-07 | Prepared PDF manual/supplemental review packs and TEXT/NAMU v2 review artifacts. |
| 2026-05-07 | Approved strict XLSX silver generation path after pre-silver risk closure. |
| 2026-05-07 | Externalized large generated/cache payloads while holding active protected artifacts. |

## Next Recommended Steps

1. Run XLSX silver generation only through the strict wrapper path approved by
   `xlsx_pre_silver_risk_closure_20260507`.
2. Before any XLSX answer-generation or promotion lane, add a focused excluded
   row / hidden negative leakage probe.
3. Resolve PDF review decisions for table-like evidence, page-only evidence,
   bbox policy, answerability, and FILE vs CONTENT routing.
4. Review TEXT/NAMU v2 candidates before changing the official denominator
   registry or running R8 citation support.
5. Keep future progress entries short: status, reports, counts, verification,
   and next action only. Do not paste full command transcripts or raw report
   payloads into this file.

## Append Policy

New entries should use this compact form:

```markdown
## YYYY-MM-DD - short title

- Status: `...`
- Scope: ...
- Evidence: `path/to/report.json`, `path/to/report.md`
- Counts: key numbers only
- Verification: command summary and result
- Next: one or two concrete actions
```

If an entry needs more than about 25 lines, write the detailed evidence to a
report file and link it here.


## 2026-05-08 - Reviewed TEXT/PDF gold cleanup and silver generation

- Status: `completed_diagnostic_candidate_freeze`.
- Scope: cleaned human-reviewed TEXT v2 labels, cleaned PDF FILE lookup companion labels, froze denominator candidates, generated tuning-only silver sets.
- Evidence: `ai-worker/eval/reports/rag-ingestion/gold_cleanup_report.md`, `ai-worker/eval/reports/rag-ingestion/silver_generation_report.md`, `ai-worker/eval/reports/rag-ingestion/denominator_manifest.json`.
- Counts: TEXT main candidates `69`, TEXT abstain diagnostics `10`, PDF FILE lookup candidates `15`, silver manifest rows `5`.
- Policies: official denominator registry unchanged; PDF FILE lookup is file identity only; no page/bbox/table/row/column/value success claimed.
- Known exclusions: label conflicts, missing required overrides, `NEEDS_SECOND_REVIEW`, source `needs_review`, TEXT abstain diagnostics, and weak/mixed PDF FILE lookup rows stay out of main positive denominators.
- Verification: silver leakage status `PASS` with exact gold query/id/source/expected-id overlaps all zero.
- Next: review the generated silver manifest, then create an explicit silver-only tuning config before running `python scripts\phase7_human_gold_tune.py`; evaluate only on frozen cleaned gold candidates after that.


## 2026-05-08 - Silver-only tuning first pass and shadow-lane plan

- Status: `silver_tuning_diagnostic_pass_complete`.
- Scope: created explicit silver-only tuning config, selected retrieval profiles using silver rows only, evaluated frozen cleaned gold candidates after selection, and added OCR/IDP/multimodal diagnostic shadow-lane contract scaffolding.
- Evidence: `ai-worker/eval/configs/silver_only_tuning_config.yaml`, `ai-worker/eval/reports/rag-ingestion/silver_tuning_run_report.md`, `ai-worker/eval/reports/rag-ingestion/gold_eval_after_silver_tuning_report.md`, `ai-worker/eval/reports/rag-ingestion/before_after_metric_delta.md`, `ai-worker/eval/reports/rag-ingestion/ocr_idp_multimodal_shadow_lane_plan.md`.
- Counts: silver TEXT positive `120`, TEXT hard negative `91`, TEXT abstain diagnostic `10`, PDF FILE lookup positive `4`, PDF FILE lookup hard negative `4`; frozen gold eval TEXT main `69`, TEXT abstain diagnostic `10`, PDF FILE lookup positive `15`, PDF FILE lookup diagnostic `4`.
- Verification: `python ai-worker\scripts\rag_silver_only_tuning_pass.py --config ai-worker\eval\configs\silver_only_tuning_config.yaml` passed; `python -m scripts.run_phase7_silver_500_full_eval --reports-root eval/reports --report-only` passed from `ai-worker/`; focused pytest set passed with legacy PDF manual CSV tests skipped only when the historical artifact is absent.
- Result: selected TEXT profile `tuned_text_section_boost_bm25`; selected PDF FILE lookup profile `baseline_pdf_file_identity_tokens`; TEXT frozen-gold MRR@10 improved `+0.0105`, Hit@10 unchanged, PDF FILE lookup unchanged and file-identity only.
- Next: review TEXT Hit@5 regression before promotion talk; keep OCR/IDP/multimodal rows diagnostic-only unless a later policy explicitly promotes a shadow lane.


## 2026-05-09 - Silver tuning delta review and shadow diagnostics

- Status: `diagnostic_review_complete`.
- Scope: analyzed frozen-gold query deltas after silver-only profile selection, reviewed PDF FILE lookup rank errors by file identity only, and ran small report-only OCR/IDP/multimodal shadow samples.
- Evidence: `ai-worker/eval/reports/rag-ingestion/silver_tuning_query_delta_report.md`, `ai-worker/eval/reports/rag-ingestion/text_hit5_regression_review.md`, `ai-worker/eval/reports/rag-ingestion/pdf_file_lookup_rank_error_analysis.md`, `ai-worker/eval/reports/rag-ingestion/ocr_shadow_small_sample_report.md`, `ai-worker/eval/reports/rag-ingestion/idp_shadow_small_sample_report.md`, `ai-worker/eval/reports/rag-ingestion/multimodal_shadow_small_sample_report.md`, `ai-worker/eval/reports/rag-ingestion/local_resource_diagnostic_smoke_report.md`, `ai-worker/eval/reports/rag-ingestion/rag_candidate_index_lineage_report.json`.
- Counts: TEXT query deltas `69` rows with improved `5`, regressed `4`, unchanged `60`; Hit@5 lost `1`, recovered `0`; PDF FILE lookup top10-not-top3 `6`, generic filename confusions `3`, similar filename confusions `7`; shadow diagnostic units OCR `2`, IDP `2`, multimodal `1`.
- Verification: corrected PDF FILE lookup selection to a silver-only identity pool, reran silver tuning and diagnostic analysis scripts, confirmed local DB with read-only doctor and lineage checks, confirmed local llama.cpp `gemma4-e2b-local` with a diagnostic-only JSON smoke, focused pytest for silver tuning diagnostics and shadow contracts passed, and official denominator registry diff remained empty.
- Result: `tuned_text_section_boost_bm25` remains `diagnostic_only` because frozen-gold Hit@5 regressed despite MRR@10 improvement; PDF FILE lookup stays file identity only; OCR/IDP/multimodal rows remain `DIAGNOSTIC_ONLY`.
- Next: review the lost Hit@5 query and PDF file-identity hard negative expansion rules before any candidate-profile promotion discussion.


## 2026-05-09 - TEXT diagnostic lock and PDF FILE lookup hard negatives v2

- Status: `diagnostic_locked_pdf_hneg_v2_complete`.
- Scope: kept `tuned_text_section_boost_bm25` diagnostic-only, traced `text_namu_v2_0058`, hardened PDF FILE lookup selection leakage guards, generated silver-only v2 hard negatives, and ran the optional report-only PDF hneg v2 selection pass.
- Evidence: `ai-worker/eval/reports/rag-ingestion/text_namu_v2_0058_rank_trace.md`, `ai-worker/eval/reports/rag-ingestion/pdf_file_lookup_hard_negative_v2_report.md`, `ai-worker/eval/review/gold_silver_tuning/silver_pdf_file_lookup_hard_negative_v2.csv`, `ai-worker/eval/reports/rag-ingestion/silver_tuning_run_report_pdf_hneg_v2.md`, `ai-worker/eval/reports/rag-ingestion/gold_eval_after_silver_tuning_report_pdf_hneg_v2.md`.
- Counts: `text_namu_v2_0058` rank `5 -> 6`; v2 PDF hard negatives `12` from `4` silver train file identities; frozen gold file identities excluded by guard `14`; frozen gold document_version_id exclusions `0` because current frozen rows have no populated docv values.
- Verification: `python ai-worker\scripts\rag_silver_only_tuning_pass.py --config ai-worker\eval\configs\silver_only_tuning_config.yaml` passed; `python ai-worker\scripts\rag_text_rank_trace.py --config ai-worker\eval\configs\silver_only_tuning_config.yaml` passed; `python ai-worker\scripts\rag_pdf_file_lookup_hard_negative_v2.py --config ai-worker\eval\configs\silver_only_tuning_config.yaml` passed; `python ai-worker\scripts\rag_silver_only_tuning_pass.py --config ai-worker\eval\configs\silver_only_tuning_config_pdf_hneg_v2.yaml` passed; focused pytest returned `9 passed, 5 skipped`; official denominator registry diff remained empty.
- Result: TEXT remains diagnostic-only; PDF FILE lookup remains `baseline_pdf_file_identity_tokens`, file identity only, with no content/page/bbox/table/row/column/value success claim.
- Next: try a capped or bucket-gated TEXT section boost and expand PDF generic filename identity coverage only from non-gold-safe silver or future reviewed non-frozen sources.


## 2026-05-09 - Answer sufficiency and recovery-loop bridge

- Status: `diagnostic_runtime_bridge_complete`.
- Scope: added deterministic fail-closed answer sufficiency judging, targeted clarification routing, a guarded adapter over the existing internal `AgentLoopController`, lane policies for TEXT/XLSX/PDF/OCR/IDP/multimodal evidence, and a report-only diagnostic harness.
- Evidence: `ai-worker/app/capabilities/rag/answer_recovery.py`, `ai-worker/scripts/rag_answer_recovery_diagnostic.py`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_existing_components_report.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_loop_plan.md`, `ai-worker/eval/reports/rag-ingestion/answer_sufficiency_diagnostic_report.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_trace.jsonl`.
- Counts: evaluated `10` cases; initially supported `3`; recovered after loop `1`; clarification needed `1`; unsupported after recovery `4`; lane mismatch `1`; hidden XLSX blocked `1`; PDF FILE lookup content mixing blocked `1`; OCR/IDP/multimodal diagnostic evidence used `1/1/1`; average loop iterations `1.8`; citation coverage `0.7 -> 0.8`.
- Verification: `python ai-worker\scripts\rag_answer_recovery_diagnostic.py --reports-dir ai-worker\eval\reports\rag-ingestion` passed; focused pytest returned `20 passed, 5 skipped`; official denominator registry diff remained empty.
- Result: no answer denominator promotion, no production index mutation, no broad indexing, no frozen-gold training/profile selection; `tuned_text_section_boost_bm25` remains diagnostic-only and PDF FILE lookup remains file identity only.
- Next: wire this bridge behind a diagnostic runtime flag in the live RAG answer path, then compare recovered citations against human-reviewed answer-shape cases before any denominator discussion.


## 2026-05-09 - Expanded answer recovery diagnostics

- Status: `expanded_diagnostic_eval_complete`.
- Scope: scaled the answer sufficiency/recovery harness from smoke cases to lane-separated diagnostic cases using existing reviewed/silver/diagnostic artifacts only, and kept all answer denominator, profile, shadow-lane, and index-mutation guardrails closed.
- Evidence: `ai-worker/eval/reports/rag-ingestion/answer_sufficiency_expanded_diagnostic_report.md`, `ai-worker/eval/reports/rag-ingestion/answer_sufficiency_expanded_diagnostic_report.json`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_expanded_trace.jsonl`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_lane_breakdown.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_failure_taxonomy.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_wrongly_supported_review.csv`.
- Counts: total `185`; TEXT `75`, XLSX `38`, PDF CONTENT `40`, PDF FILE lookup `28`, OCR `1`, IDP `2`, multimodal `1`; recovered after loop `5`; wrongly supported `10` silver PDF FILE hard-negative identity cases; unsupported correctly blocked `18`; hidden XLSX attempts blocked `3`; PDF FILE content-mixing attempts blocked `4`; diagnostic-only evidence blocked `8`.
- Verification: `python ai-worker\scripts\rag_answer_recovery_diagnostic.py` passed; `python -m pytest ai-worker/tests/test_rag_answer_recovery_bridge.py` returned `15 passed`; official denominator registry diff remained empty.
- Result: `tuned_text_section_boost_bm25` remains diagnostic-only; PDF FILE lookup remains file identity only with no content/page/bbox/table/row/column/value success claim; explicit file-identity intent now prevents filename marker false positives such as `전기요금표`.
- Next: review the `wrongly_supported` PDF FILE hard-negative rows, then add identity-correctness checks before treating file-identity answer sufficiency as anything beyond diagnostic.


## 2026-05-09 - PDF FILE answer sufficiency calibration

- Status: `answer_recovery_policy_calibrated`.
- Scope: analyzed PDF FILE lookup wrongly-supported hard negatives, required exact/canonical file identity verification for PDF FILE support, and kept file identity separate from content/page/bbox/table/row/column/value semantics.
- Evidence: `ai-worker/eval/reports/rag-ingestion/pdf_file_lookup_wrongly_supported_root_cause.md`, `ai-worker/eval/reports/rag-ingestion/answer_sufficiency_expanded_diagnostic_report.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_tuning_readiness_after_calibration.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_wrongly_supported_review.csv`.
- Counts: expanded total `185`; PDF FILE lookup `28`; wrongly supported `10 -> 0`; PDF FILE unsupported correctly blocked `18`; hidden XLSX attempts blocked `3`; PDF FILE content-mixing blocked `4`; diagnostic-only evidence blocked `8`; recovered after loop `5`.
- Verification: `python ai-worker\scripts\rag_pdf_file_lookup_wrongly_supported_root_cause.py` passed; `python ai-worker\scripts\rag_answer_recovery_diagnostic.py` passed; `python -m pytest ai-worker/tests/test_rag_answer_recovery_bridge.py` returned `20 passed`; official denominator registry diff remained empty.
- Result: tuning readiness is `true_for_narrow_silver_only_calibration`; production promotion and official answer denominator readiness remain `false`.
- Next: run only a narrow silver-only calibration pass if needed; do not run broad tuning or promotion until identity-correctness remains stable on fresh diagnostic rows.


## 2026-05-10 - Narrow answer recovery silver calibration

- Status: `narrow_silver_calibration_complete`.
- Scope: added explicit diagnostic-only calibration config, evaluated deterministic policy variants over the expanded answer recovery diagnostic set, and selected the current exact/canonical PDF FILE identity policy without broad tuning or promotion.
- Evidence: `ai-worker/eval/configs/answer_recovery_narrow_silver_calibration.yaml`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_narrow_calibration_report.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_narrow_calibration_report.json`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_narrow_calibration_variants.csv`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_narrow_calibration_selected_policy.json`.
- Counts: variants `6`; selected `calibrated_identity_exact_v1`; total `185`; wrongly supported `0`; recovered after loop `5`; unsupported correctly blocked `32`; hidden XLSX blocked `3`; PDF FILE content-mixing blocked `4`; diagnostic-only evidence blocked `8`; citation coverage `0.935135 -> 0.962162`.
- Verification: `python ai-worker\scripts\rag_answer_recovery_narrow_calibration.py --config ai-worker\eval\configs\answer_recovery_narrow_silver_calibration.yaml` passed; `python -m pytest ai-worker/tests/test_rag_answer_recovery_bridge.py ai-worker/tests/test_rag_answer_recovery_narrow_calibration.py` returned `24 passed`; official denominator registry diff remained empty.
- Result: readiness remains `true_for_narrow_silver_only_calibration`; production promotion and official answer denominator readiness remain `false`.
- Next: collect fresh non-frozen diagnostic PDF FILE identity rows, then rerun the same narrow calibration before any broader tuning discussion.


## 2026-05-10 - Answer recovery safe recall tuning v1

- Status: `safe_recall_report_only_complete`.
- Scope: ran `answer_recovery_safe_recall_tuning_v1` as a diagnostic-only sibling of the narrow calibration; no broad tuning, no production promotion, no official denominator opening, no production index mutation, no broad indexing, and no frozen-gold selection/training.
- Evidence: `ai-worker/eval/configs/answer_recovery_safe_recall_tuning.yaml`, `ai-worker/scripts/rag_answer_recovery_safe_recall_tuning.py`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_safe_recall_baseline.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_missed_safe_recovery_analysis.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_safe_recall_tuning_report.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_safe_recall_selected_policy.json`.
- Counts: variants `6`; selected `baseline_selected_policy` over `calibrated_identity_exact_v1`; full diagnostic total `185`; selection rows `173` after excluding frozen-gold-sourced rows `12`; wrongly supported `0`; recovered after loop `5`; unsupported correctly blocked `32`; hidden XLSX blocked `3`; PDF FILE content-mixing blocked `4`; diagnostic-only evidence blocked `8`; citation coverage `0.935135 -> 0.962162`; safe recovery candidate count `0`.
- Verification: `python ai-worker/scripts/rag_answer_recovery_safe_recall_tuning.py --config ai-worker/eval/configs/answer_recovery_safe_recall_tuning.yaml` passed; focused pytest returned `31 passed`; official denominator registry diff remained empty.
- Result: allowed TEXT/XLSX/PDF CONTENT safe-context variants produced no safe recall or citation-coverage improvement on the current diagnostic set, so the selected policy remains diagnostic-only with production promotion ready `false` and official answer denominator ready `false`.
- Next: add fresh non-frozen diagnostic rows with actual unsupported positive cases before another safe-recall attempt; keep PDF FILE lookup exact/canonical identity only.


## 2026-05-10 - Answer recovery safe recall missed-row triage v1

- Status: `missed_row_triage_report_only_complete`.
- Scope: analyzed the rows behind recovered-after-loop, remaining citation-uncovered, and unsupported-correctly-blocked counts from `answer_recovery_safe_recall_tuning_v1`; no policy promotion, official answer denominator opening, production index mutation, broad indexing, frozen-gold training/selection, local LLM judging, or Optuna tuning.
- Evidence: `ai-worker/eval/configs/answer_recovery_safe_recall_missed_row_triage.yaml`, `ai-worker/scripts/rag_answer_recovery_safe_recall_missed_row_triage.py`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_safe_recall_missed_row_triage.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_safe_recall_missed_row_triage.json`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_safe_recall_missed_row_triage.csv`.
- Counts: triage rows `37`; recovered-after-loop focus `5`; citation-uncovered focus `7`; unsupported-correctly-blocked focus `32`; category counts SAFE_EXISTING `5`, SAFE_CANONICAL `0`, INDEX_SCOPE_MISSING `5`, POLICY_BLOCKED_CORRECTLY `17`, GOLD_POLICY_REQUIRED `6`, DIAGNOSTIC_ONLY_DO_NOT_PROMOTE `4`, UNKNOWN `0`; selection rows stayed `173` after excluding frozen-gold-sourced rows `12`.
- Verification: `python ai-worker/scripts/rag_answer_recovery_safe_recall_missed_row_triage.py --config ai-worker/eval/configs/answer_recovery_safe_recall_missed_row_triage.yaml` passed; focused pytest returned `37 passed`; official denominator registry diff remained empty.
- Result: safe recovery category was found only for the existing five TEXT loop recoveries, and they remain diagnostic evidence. No production promotion was made because the report does not establish fresh non-frozen gold, official denominator readiness, or a production-safe policy change.
- Next: gather fresh non-frozen unsupported-positive diagnostic rows with human policy decisions before another safe-recall attempt.


## 2026-05-10 - Answer recovery embedding readiness v1

- Status: `embedding_readiness_report_only_complete`.
- Scope: inspected existing embedding/vector conventions, source-chunk provenance, staging namespace safety, and leakage risks for recovered, citation-uncovered, and unsupported-correctly-blocked answer recovery rows; no production index mutation, staging vector write, official denominator opening, policy promotion, frozen-gold selection/training, expected-answer embedding, or label embedding.
- Evidence: `ai-worker/eval/configs/answer_recovery_embedding_readiness.yaml`, `ai-worker/scripts/rag_answer_recovery_embedding_readiness.py`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_readiness.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_readiness.json`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_backfill_manifest.jsonl`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_namespace_inventory.json`.
- Counts: manifest rows `37`; EMBED_STAGING_PRODUCTION_ELIGIBLE_SOURCE `5`; SKIP_HIDDEN_XLSX `3`; SKIP_DIAGNOSTIC_ONLY_SHADOW `6`; SKIP_PDF_FILE_CONTENT_MIXING_RISK `4`; SKIP_FROZEN_GOLD_DERIVED_EVAL_CONTENT `4`; SKIP_EXPECTED_ANSWER_OR_LABEL `7`; SKIP_POLICY_BLOCKED `6`; REVIEW_GOLD_POLICY_REQUIRED `2`; INDEX_SCOPE_MISSING causes indexing-scope policy `3` and diagnostic-only source `2`.
- Backend: local FAISS/SentenceTransformer conventions and existing indexes were detected, but `embedding_backend_available=false` for this step because no configured diagnostic staging namespace exists and the runner is report-only; staging backfill status `skipped_backend_unavailable`.
- Verification: `python ai-worker/scripts/rag_answer_recovery_embedding_readiness.py --config ai-worker/eval/configs/answer_recovery_embedding_readiness.yaml` passed; new focused pytest returned `9 passed`; production index and official denominator registry were not changed.
- Result: the five safe-existing TEXT rows have stable canonical chunk IDs and are already present in the local Namu embedded source index, but would only be eligible for a future diagnostic namespace backfill. Hidden XLSX, diagnostic-only, PDF FILE content-mixing, frozen-gold-derived, and expected-answer/label surfaces remain blocked.
- Next: if staging embedding is needed, first create an explicit diagnostic namespace setup and source-text materialization check; keep official denominator and production promotion closed.


## 2026-05-10 - Answer recovery embedding backend contract recheck v1

- Status: `backend_available_detection_bug_fixed`.
- Scope: reran `answer_recovery_embedding_backend_contract_recheck_v1` as diagnostic/report-only and split backend availability from staging backfill, namespace existence, and write permission.
- Evidence: `ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_backend_contract_recheck.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_backend_contract_recheck.json`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_readiness.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_readiness.json`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_existing_embedding_retrieval_probe.json`.
- Backend: previous readiness backend value `false`; corrected backend value `true`; root cause was runner-side conflation of `perform_staging_backfill=false` / missing staging namespace with backend unavailability.
- Backfill: corrected staging backfill status `skipped_backfill_disabled_by_config`; backend probe succeeded with `BAAI/bge-m3` dimension `1024`; vector write attempted `false`; namespace created `false`; production mutation `false`; denominator opened `false`.
- Follow-on probe: `answer_recovery_existing_embedding_retrieval_probe_v1` started and passed read-only over the five safe existing source rows; all five target chunks were found at rank `1` in top-10 from namespace `namu-v4-2008-2026-04-retrieval-title-section-mseq512`.
- Verification: backend contract runner passed; readiness runner passed; retrieval probe runner passed; focused readiness pytest `16 passed`; focused answer-recovery bundle `53 passed`; py_compile passed for the new/updated scripts.
- Warnings: live embedding runs emitted existing environment warnings for `requests` dependency versions, deprecated `TRANSFORMERS_CACHE`, and PyTorch `expandable_segments` unsupported on this platform.
- Result: official denominator registry unchanged; production promotion ready `false`; official answer denominator ready `false`; no expected answers, labels, hidden XLSX, PDF FILE content-mixing, or diagnostic-only evidence was made support-eligible.


## 2026-05-10 - answer_recovery_report_artifact_compaction_v1

- Status: `compact_report_default_enabled`; artifact_profile=`compact`.
- Compact reports generated: `ai-worker/eval/reports/rag-ingestion/answer_recovery_tuning_report.md`, `ai-worker/eval/reports/rag-ingestion/answer_recovery_tuning_report.json`.
- Legacy debug artifacts cleaned: `true` for generated embedding/backend/probe CSV/MD/JSON, JSONL manifest, and namespace inventory; tracked legacy artifacts were not removed.
- Debug artifacts emitted: `false` by default; debug profile remains available behind explicit `artifact_profile=debug` or reporting flags.
- Guardrails: production mutation=`false`; denominator opened=`false`; production promotion ready=`false`; official answer denominator ready=`false`; vector write attempted=`false`.
- Verification: compact report runner passed with live backend/probe path; backend contract and readiness runners also passed in compact/default mode with `--skip-backend-probe`; focused compaction pytest `5 passed`; focused answer-recovery bundle `38 passed`.
- Known warnings: focused pytest still emits pre-existing environment warnings for `requests` dependency versions, pytest-asyncio default fixture loop scope, and FAISS/numpy deprecation; live backend run also emits existing `TRANSFORMERS_CACHE` and PyTorch `expandable_segments` warnings.


## 2026-05-10 - Existing dataset license and noncommercial usage gate v1

- Status: `PASS_WITH_GAPS`.
- Scope: enriched existing manifests with license/usage metadata for noncommercial internal OCR/MM and RAG experiments; no production mutation, no official denominator change.
- Evidence: `ai-worker/eval/reports/rag-ingestion/existing_manifest_license_usage_gate.md`, `ai-worker/eval/reports/rag-ingestion/existing_manifest_license_usage_gate.json`, `ai-worker/eval/reports/rag-ingestion/existing_manifest_license_summary_by_source.md`, `ai-worker/eval/reports/rag-ingestion/existing_manifest_experiment_readiness.md`, `ai-worker/eval/review/retrieval_dataset_supplementation/existing_manifest_license_enriched.json`, `ai-worker/eval/review/retrieval_dataset_supplementation/license_review_required_rows.csv`.
- Counts: manifests `28`; rows `2115`; canonical rows `1053`; license verified/unknown/blocker `1236/591/0`; source terms ambiguous `288`; internal eval ready `1524`; embedding ready `440`; vector staging ready `410`; OCR/MM ready `796`; RAG ready `262`; review required `2055`.
- Result: diagnostic-only; support_eligible_ocr_mm_count=`0`; annotation_answer_embedding_count=`0`; pdf_file_content_mixing_support_count=`0`; hidden_xlsx_exposed=`false`; promotion_evidence=`false`.
- Next: targeted supplementation only for license/readiness gaps, especially row-specific PRISM/public-institution terms, public-data catalog license fields, and OCR/MM vector-staging eligibility.


## 2026-05-11 - Phase 2A-2 review-unlock estimate and license-first collection prioritization

- Status: `review_unlock_estimate_complete`.
- Scope: quantified fixed-denominator review unlock potential versus new all-qualified collection needs before any Phase 2B collection; no source manifest mutation, no official denominator change, no production index/vector/namespace mutation.
- Files read: `ai-worker/eval/review/retrieval_dataset_supplementation/existing_manifest_license_enriched.csv`, `ai-worker/eval/review/retrieval_dataset_supplementation/license_review_required_rows.csv`, `ai-worker/eval/reports/rag-ingestion/existing_manifest_experiment_readiness.md`, `ai-worker/eval/reports/rag-ingestion/existing_manifest_license_summary_by_source.md`, `ai-worker/eval/reports/rag-ingestion/existing_manifest_license_usage_gate.md`, and the Phase 1 CSV/MD summaries under `docs/phase1_*`.
- Generated artifact set: `phase2_review_unlock_estimate.md`, `phase2_review_unlock_estimate.json`, `phase2_review_priority_matrix.csv`, `phase2_collection_priority_matrix.csv`, `phase2_denominator_risk_report.md`, `phase2_rag_retrieval_core_breakdown.csv`, `phase2_visual_shadow_breakdown.csv`. Current reproducible output location is ignored `.tmp/phase2-review-unlock/`; these diagnostic artifacts are not committed under `docs/`.
- Denominator interpretation: RAG retrieval core is lane-based on `TEXT_NAMU`, `XLSX`, `PDF_CONTENT`; row vector readiness is `262/512` and canonical vector readiness is `131/252`. Visual shadow is lane-based on `OCR_IMAGE`, `OCR_ANNOTATION`, `MULTIMODAL_IMAGE`, `MULTIMODAL_ANNOTATION`, `OCR_SHADOW`, `IMAGE_ARCHIVE`; row vector readiness is `140/1244` and canonical vector readiness is `70/622`. Row-level and canonical-level denominators must stay paired in reports.
- Review-first sources: high-priority `PUBLIC_DATA_PORTAL` / data.go.kr and `SEOUL_OPEN_DATA`; also `HUGGING_FACE` with dataset-specific license isolation, current `KOSIS` rows until item-level/equivalent evidence is captured, `DART` with document-level rights evidence, `UNKNOWN_SOURCE`, and `WIKIMEDIA_COMMONS` rows that remain ambiguous or mixed.
- Collect-now sources: `PADDLEOCR_GITHUB`; future `KOSIS` or explicitly licensed KOGL/public-data rows can move to `COLLECT_NOW` only when item-level/equivalent evidence is attached and the row is all-qualified before denominator inclusion.
- Diagnostic-only sources: `FUNSD` for OCR/MM diagnostics only; `NAMU` as noncommercial-limited and never public/support/gold by default; `PRISM` and `PUBLIC_INSTITUTION` as parser-smoke or diagnostic-only until item-level KOGL/equivalent evidence exists.
- Blocked/do-not-promote sources: no observed source family was separately classified as `BLOCKED_OR_DO_NOT_PROMOTE`; unsafe, inferred, missing, ambiguous, or source-family-only evidence still has effective vector/public/support/gold eligibility forced to `0`.
- Review-unlock estimate: RAG retrieval core needs `148` existing rows or `71` canonical rows promoted to reach `0.80`; conservative current review-first unlock is `128` rows / `60` canonical rows, so it does not fully reach target without stronger item-level evidence for currently diagnostic parser-smoke families. Visual shadow needs `856` rows / `428` canonical rows; current conservative review-first unlock is `278` rows / `139` canonical rows.
- New-collection estimate: if the denominator grows, RAG retrieval core needs `738` all-qualified new rows or `353` all-qualified canonical rows; visual shadow needs `4276` all-qualified new rows or `2138` all-qualified canonical rows. Adding unreviewed or diagnostic-only data worsens denominator rates.
- Guardrails: official_denominator_registry_changed=`false`; production_index_mutation=`false`; production_vector_write=`false`; namespace_created=`false`; support_eligible_ocr_mm_count=`0`; annotation_answer_embedding_count=`0`; hidden_xlsx_exposed=`false`; promotion_evidence=`false`.
- Verification: `python -m py_compile ai-worker/scripts/rag_phase2_review_unlock_estimator.py` passed; `python -m pytest ai-worker/tests/test_rag_phase2_review_unlock_estimator.py` passed; `python ai-worker/scripts/rag_phase2_review_unlock_estimator.py --out-dir .tmp/phase2-review-unlock/` passed; `python -m json.tool .tmp/phase2-review-unlock/phase2_review_unlock_estimate.json` passed; `git diff --quiet -- ai-worker/eval/eval_queries/official_denominator_registry.json` passed; `git diff --check` passed.
- Next Phase 2B recommendation: review existing data.go.kr and Seoul open-data rows first by capturing item-level 이용허락범위/KOGL/equivalent evidence; only then collect narrow KOSIS/explicit public-license rows that are all-qualified at ingestion time. Current KOSIS rows remain review-first because the observed evidence is configured source-family terms, not item-level/equivalent row evidence. Keep FUNSD, NAMU, PRISM/public-institution-without-item-license, and DART-without-document-rights out of public/support/gold and readiness-promotion claims.


## 2026-05-11 - Phase 2B diagnostic-readiness view separation

- Status: `repo_hygiene_and_generated_artifact_containment_complete`.
- Command run: `python ai-worker/scripts/rag_phase2_review_unlock_estimator.py --out-dir .tmp/phase2-review-unlock/`.
- Ignored output directory: `.tmp/phase2-review-unlock/`; `.tmp/` is already ignored, and no `.gitignore` exceptions are kept for Phase 2 diagnostic reports.
- Generated artifact names and SHA-256 hashes: `phase2_collection_priority_matrix.csv`=`ac3d99b2f7b28eadcf6fa7b8a325d5f4d8353660609028201e1462641c742e88`; `phase2_denominator_risk_report.md`=`c47ad915035e8124d71943417f9d6f3e85514eba750df466c29b00ab81a194e8`; `phase2_rag_retrieval_core_breakdown.csv`=`917445c983894d427cf2d775b556d188991077a241e31bf50c13300ebebfa2f3`; `phase2_review_priority_matrix.csv`=`f49931010f5d2975a4db5c8631aac5b7abe25e8935a94eb1637c212df35c80bd`; `phase2_review_unlock_estimate.json`=`0639cfd6bc4c8fd09132778b63880500ada50af49df23cffb3e999de356736f0`; `phase2_review_unlock_estimate.md`=`5c44f6440871a9de6d793dba342a7b099ca9936cf3a2a82fbb42e736d402894b`; `phase2_visual_shadow_breakdown.csv`=`dff97125143af6b85bfcf67e3395167d54463957c2c5a9c286469a654be12c57`.
- Official readiness unchanged: RAG retrieval core stays `262/512` rows and `131/252` canonical; visual shadow stays `140/1244` rows and `70/622` canonical.
- Official after conservative unlock: RAG retrieval core projects to `390/512` rows and `191/252` canonical; visual shadow projects to `418/1244` rows and `209/622` canonical.
- Promotion-scope current summary: RAG retrieval core is `0/0` rows and `0/0` canonical with rate `N/A`, reason `no_currently_eligible_promotion_scope_units`; visual shadow is `50/50` rows and `25/25` canonical. These views are diagnostic/report-only.
- KOSIS mixed-state summary: vector_stage_eligible `2` rows / `1` canonical; support_eligible `0`; gold_candidate_allowed `0`; license_evidence_level `source_family_or_terms_page_only`; review_required_reason `source_family_terms_only_requires_item_level_or_equivalent_evidence`.
- NAMU warning: counted in official RAG vector readiness, but blocked from public/support/gold promotion by noncommercial-limited diagnostic policy.
- Diagnostic-only policy assumptions: promotion-scope excludes diagnostic-only rows, noncommercial-limited rows, parser-smoke-only rows without item-level/equivalent evidence, research-only rows, unsafe/ambiguous/inferred/missing-license rows, and rows still requiring user license review. These exclusions do not mutate official denominators.
- Guardrails: official_denominator_registry_changed=`false`; production_index_mutation=`false`; production_vector_write=`false`; namespace_created=`false`; support_eligible_ocr_mm_count=`0`; annotation_answer_embedding_count=`0`; hidden_xlsx_exposed=`false`; promotion_evidence=`false`.
- Local generated docs cleanup: removed only known generated `docs/phase2_*` diagnostic files, including the previous consolidated Phase 2 markdown; no broad ignored-file cleanup was run.
- Verification: `python -m py_compile ai-worker/scripts/rag_phase2_review_unlock_estimator.py` passed; `python -m pytest ai-worker/tests/test_rag_phase2_review_unlock_estimator.py` passed with `14 passed`; `python ai-worker/scripts/rag_phase2_review_unlock_estimator.py --out-dir .tmp/phase2-review-unlock/` passed; `python -m json.tool .tmp/phase2-review-unlock/phase2_review_unlock_estimate.json` passed; `git diff --quiet -- ai-worker/eval/eval_queries/official_denominator_registry.json` passed; `git diff --check` passed.


## 2026-05-11 - Phase 2B pipeline validation, not model-quality tuning

- Status: `pipeline_validation_complete_tuning_blocked`.
- Commands run: `python -m py_compile ai-worker/scripts/rag_phase2_review_unlock_estimator.py`; `python -m pytest ai-worker/tests/test_rag_query_orchestrator_vector_tools.py`; `python -m pytest ai-worker/tests/test_rag_phase2_review_unlock_estimator.py ai-worker/tests/test_rag_phase2_pipeline_validation.py`; `python ai-worker/scripts/rag_phase2_review_unlock_estimator.py --out-dir .tmp/phase2-review-unlock/`; `python -m json.tool .tmp/phase2-review-unlock/phase2_review_unlock_estimate.json`.
- Validation status: estimator tests `14 passed`; pipeline validation tests included in combined Phase 2 run `18 passed`; vector-tool regression `12 passed`. Existing environment warnings remain limited to dependency-version, pytest-asyncio, and FAISS/numpy warnings.
- Ignored output directory: `.tmp/phase2-review-unlock/`; generated diagnostic artifacts remain ignored and reproducible, with no `docs/phase2_*` committed output.
- Generated artifact names and SHA-256 hashes: `phase2_collection_priority_matrix.csv`=`f16b41ce1cd8e14e7d48a7071c2fe1b6afeb6182d0d766bd3b631644f792030f`; `phase2_denominator_risk_report.md`=`13f24a5303cb4667b362a2c89b10bf72b031585022ec56ba1e3e9704c84d8669`; `phase2_rag_retrieval_core_breakdown.csv`=`917445c983894d427cf2d775b556d188991077a241e31bf50c13300ebebfa2f3`; `phase2_review_priority_matrix.csv`=`50ff07742f31ca037f6551da6b7c50e3dda51899e6c6a6aa7afb355e91bead2b`; `phase2_review_unlock_estimate.json`=`7e200fa84d13dce60d3c843e2ee2eed072d0df480c7cacb6c902ae112e5ba2d4`; `phase2_review_unlock_estimate.md`=`5fa201e1a3fe8de5748b984b9a0aadbc6f19399d8a5aa3085c600448105cd618`; `phase2_visual_shadow_breakdown.csv`=`dff97125143af6b85bfcf67e3395167d54463957c2c5a9c286469a654be12c57`.
- Denominator/report assertions: official RAG readiness remains `262/512` rows and `131/252` canonical; official after conservative unlock remains `390/512` rows and `191/252` canonical. Promotion-scope RAG current is `0/0` rows and canonical with rate `N/A`; promotion-scope visual current is `50/50` rows and `25/25` canonical.
- Diagnostic routing assertions: diagnostic-only source families remain excluded from public/support/gold; NAMU remains noncommercial-limited and emits the vector-readiness promotion-block warning; FUNSD remains OCR/MM diagnostic-only; KOSIS keeps vector-stage eligibility separate from support/gold ineligibility.
- Diagnostic retrieval smoke: a synthetic in-memory diagnostic namespace validates source_family_id, license status, policy posture, canonical row id, lane, support/gold/public flags, and vector id metadata through SearchUnit chunk metadata and vector-tool evidence conversion. It does not create namespaces, write production vectors, or touch production indexes.
- Dataset/source-family license status summary: `PUBLIC_DATA_PORTAL` and `SEOUL_OPEN_DATA` are `LICENSE_INFERRED_FROM_CATALOG_BUT_UNVERIFIED`; `KOSIS` is `VERIFIED_OPEN_PUBLIC_DATA` but evidence is source-family/terms-level only; `FUNSD` is `VERIFIED_RESEARCH_ONLY`; `NAMU` is `VERIFIED_NONCOMMERCIAL_ONLY`; `HUGGING_FACE` is mixed `SOURCE_LICENSE_NOT_FOUND` and `VERIFIED_OPEN_LICENSE` and remains dataset-specific review-first; `PADDLEOCR_GITHUB` is `VERIFIED_OPEN_LICENSE`; `PRISM` and `PUBLIC_INSTITUTION` are `SOURCE_LICENSE_NOT_FOUND`; `DART` is `SOURCE_TERMS_FOUND_BUT_AMBIGUOUS`.
- Guardrails: official_denominator_registry_changed=`false`; production_index_mutation=`false`; production_vector_write=`false`; namespace_created=`false`; support_eligible_ocr_mm_count=`0`; annotation_answer_embedding_count=`0`; hidden_xlsx_exposed=`false`; promotion_evidence=`false`.
- Progress-log content boundary: aggregate-only counts, source-family names, policy labels, and hashes are recorded; no row-level copyrighted/raw-ish data, full license text, full URLs, or evidence excerpts are included.
- Tuning note: model-quality tuning is still blocked until promotion-scope RAG has reviewed all-qualified units with expected answer/evidence and answerability/relevance labels.


## 2026-05-11 - Collected dataset license evidence refresh

- Status: `license_evidence_refresh_complete`.
- Scope: revisited collected-source license/terms pages and updated the companion license gate policy for this session's collected manifests; original manifests remain unchanged.
- Pages/APIs checked: FUNSD terms page, Hugging Face dataset APIs for `HuggingFaceM4/ChartQA`, `nielsr/docvqa_1200_examples`, and `mychen76/receipt_cord_ocr_v2`, PaddleOCR GitHub license API/page, data.go.kr catalog JSON license fields for collected dataset ids, Seoul Open Data dataset page `OA-1176`, KOSIS use guide, OpenDART terms, PRISM sample task pages, NamuWiki license page, and public-data portal policy/KOGL type guide.
- License evidence updates: data.go.kr item-level catalog JSON now separates unrestricted rows, KOGL Type 1, KOGL Type 2 noncommercial, and KOGL Type 4 noncommercial/no-derivatives; Seoul `OA-1176` is KOGL Type 1 while statbook-list rows stay catalog-unverified; HF ChartQA remains GPL-3.0 review-isolated; HF DocVQA/CORD mirrors are explicitly `SOURCE_LICENSE_NOT_FOUND` because the revisited API returned no dataset license; Wikimedia public-domain metadata now maps to open public data.
- Counts after regeneration: verified/unknown/blocker `1424/591/0`; source terms ambiguous or inferred `100`; internal eval allowed `1524`; embedding allowed `578`; vector DB internal allowed `546`; public release allowed `142`; review required `1893`; OCR/MM ready `796`; RAG ready `312`.
- Guardrails: official_denominator_registry_changed=`false`; production_index_mutation=`false`; production_vector_write=`false`; namespace_created=`false`; support_eligible_ocr_mm_count=`0`; annotation_answer_embedding_count=`0`; hidden_xlsx_exposed=`false`; promotion_evidence=`false`.
- Verification: `python -m py_compile ai-worker/scripts/rag_existing_manifest_license_usage_gate.py` passed; focused license gate pytest `12 passed`; license gate regeneration passed; JSON validation passed for regenerated reports/manifests; official denominator diff remained empty; `git diff --check` passed.


## 2026-05-11 - License-refresh Phase 2 readiness recheck and portfolio cleanup

- Status: `license_refresh_recheck_complete_portfolio_cleanup_done`.
- Scope: reran the license gate and Phase 2 review-unlock estimator after item-level/catalog license evidence refresh; moved non-core tracked frontend design handoff, legacy static UI, and legacy eval-note material to `archive/experiments/`; moved ignored legacy smoke CSV/JSONL residue out to `../_external_workspace_archive/async-ocr-rag-multimodal-pipeline/2026-05-11-portfolio-cleanup/`.
- Current license-gate counts: manifests `28`; rows `2115`; canonical rows `1053`; verified/unknown/blocker `1424/591/0`; source terms ambiguous or inferred `100`; internal eval ready `1524`; embedding ready `578`; vector DB internal ready `546`; public release allowed `142`; review required `1893`; OCR/MM ready `796`; RAG ready `312`.
- Current Phase 2 denominator interpretation after refresh: official RAG retrieval row vector readiness `304/512` and canonical `152/252`; conservative review unlock reaches `390/512` rows and `191/252` canonical. Official visual shadow row vector readiness `144/1244` and canonical `72/622`; conservative review unlock reaches `416/1244` rows and `208/622` canonical.
- Promotion-scope view after refresh: RAG retrieval core `40/40` rows and `20/20` canonical; visual shadow `54/56` rows and `27/28` canonical. This remains diagnostic/report-only and does not create support/gold/public-release evidence.
- Repository hygiene result: `frontend/` now contains only `frontend/app/` and `frontend/index.html`; `ai-worker/eval/legacy/` and ignored `ai-worker/eval/legacy_agent_loop_ab/` are no longer in the active tree. Active reports, manifests, scripts, tests, official denominator, and runtime pipeline directories were preserved.
- Verification: `python -m py_compile ai-worker/scripts/rag_existing_manifest_license_usage_gate.py ai-worker/scripts/rag_phase2_review_unlock_estimator.py` passed; focused pytest bundle returned `42 passed`; license gate regeneration passed; Phase 2 estimator regeneration passed; JSON validation passed for license-gate JSON and `.tmp/phase2-review-unlock/phase2_review_unlock_estimate.json`; official denominator diff remained empty; `git diff --check` passed.
- Guardrails: official_denominator_registry_changed=`false`; production_index_mutation=`false`; production_vector_write=`false`; namespace_created=`false`; support_eligible_ocr_mm_count=`0`; annotation_answer_embedding_count=`0`; hidden_xlsx_exposed=`false`; promotion_evidence=`false`.
