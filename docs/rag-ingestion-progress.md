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
