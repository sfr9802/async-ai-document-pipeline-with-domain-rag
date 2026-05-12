# RAG Ingestion Progress

Last updated: 2026-05-13 KST.

This file is the compact status index for RAG ingestion. It should not store
turn-level logs, command transcripts, raw report payloads, or per-agent notes.
Keep detailed evidence in report files, review packs, generated manifests, or
external archive manifests and link only the current source of truth here.

## Current Status

Overall status: `diagnostic_pipeline_ready_for_review`; production promotion and
model-quality tuning remain blocked.

- Ingestion v2 is implemented on the production
  `source_file -> extracted_artifact -> search_unit` path.
- XLSX/PDF SearchUnits must preserve citation-capable metadata before indexing:
  `parser_version`, `location_json`, and `citation_text`.
- `embedding_text`, `bm25_text`, `display_text`, `citation_text`, and
  `debug_text` remain separate contract fields.
- Current RAG work is split into three named tracks:
  `text_namuwiki_animation`, `xlsx_business_structured`, and
  `pdf_business_ocr_mm`.
- The three tracks must not be collapsed into one namespace, retrieval contract,
  denominator, or quality average.
- Query-time orchestration contracts are implemented for diagnostics: guarded
  routes, deterministic hints, metadata guards, multi-route/fallback markers,
  and XLSX/PDF evidence-context assembly.
- Production vector retrieval is not yet promoted because the current POC wrapper
  still relies on bounded overfetch plus post-filtering; fail-closed filtering is
  still required before or inside vector ranking.
- License evidence refresh and Phase 2 readiness recheck are complete. The
  resulting readiness views are diagnostic/report-only and do not create
  support, gold, public-release, production-vector, or promotion evidence.
- Generated/ignored eval artifacts were externalized on 2026-05-11. The active
  Namuwiki/text corpus remains local because the text track still depends on it.
- Answer recovery is consolidated in the compact report
  `ai-worker/eval/reports/rag-ingestion/answer_recovery_tuning_report.md`;
  detailed stage/debug reports remain generated artifacts unless explicitly
  re-emitted.

## Track Board

| Track | Current state | Current denominator / metric | Next action |
|---|---|---|---|
| `xlsx_business_structured` | `STRICT_SILVER_GENERATED_DIAGNOSTIC_ONLY` for retrieval/evidence only; normalized excluded-row / hidden-negative leakage probe `PASS` | Official retrieval/evidence denominator `23`; generated strict silver rows `23`; answer-generation denominator `0`; live smoke Hit@10 `1.0`, MRR@10 `0.942`, citation accuracy `1.0` | Review the strict silver report/manifest. Keep answer-generation and promotion closed until any newly opened answer/citation/debug/public surfaces are reprobed. |
| XLSX legacy diagnostic | Historical / superseded | Legacy Track A reviewed diagnostic denominator `35`; exact location recovered by top 10 | Preserve only as historical diagnostic evidence. Do not use as the current wrapper default. |
| `text_namuwiki_animation` | Review / candidate-prep lane | Bound TEXT/NAMU diagnostic positive denominator `47`; current answer/citation-support denominator not opened | Review v2 candidates and collect actual generated answer output before any R8 citation-support denominator. Keep NAMU noncommercial-limited and out of public/support/gold promotion by default. |
| `pdf_business_ocr_mm` | `STRICT_SILVER_DIAGNOSTIC_GATE_COMPLETE` for retrieval/evidence only; no strict rows promoted because active artifacts lack source-unit/layout/OCR context | Conservative PDF positive controls `7`; generated strict silver rows `0`; diagnostic-only fallback rows `7`; policy-excluded rows `6`; stable-identity-required rows `3`; deferred OCR/parsing rows `2`; answer denominator `0` | Add or regenerate PDF evidence with source search unit id/rank, parser/source metadata, nearby paragraphs, bbox/page/region, OCR confidence where relevant, and citation locator metadata before strict silver promotion. Keep FILE/document identity separate from CONTENT evidence. |
| Route/orchestration metrics | Diagnostic-only | Korean memo labels applied in diagnostic-only route/fallback artifacts; official metric input rows remain `0` | Use the applied route/fallback labels for diagnostic analysis only. Create an explicit policy review before interpreting routing accuracy, wrong-route rate, fallback success, or multi-route success as official metrics. |
| Answer recovery | Diagnostic-only consolidation complete | Baseline `calibrated_identity_exact_v1`; compact status `PASS`; `185` cases; triage counts: safe-recoverable report-only `5`, index-scope-missing `5`, policy-blocked-correctly `17`, gold-policy-required `6`, diagnostic-only-do-not-promote `4`, unknown `0`; answer denominator `0`; production promotion `false` | User gold-policy judgment is needed only for the 6 `GOLD_POLICY_REQUIRED` rows. Keep safe recoveries report-only and keep index-scope rows out of retrieval/ranking failure counts until source evidence is proven in-scope and indexed. |

## 2026-05-13 PDF Strict Retrieval/Evidence Diagnostic Slice

Status: `COMPLETED_DIAGNOSTIC_ONLY`; compact reports:

- `ai-worker/eval/reports/rag-ingestion/pdf_strict_silver_generation_report.md`
  / `.json`
- External-only full manifest:
  `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\pdf_strict_silver_generation\pdf_strict_silver_retrieval_evidence_manifest.jsonl`

Counts:

- Input denominator rows: `7`.
- Generated strict silver rows: `0`.
- Diagnostic-only fallback rows: `7`.
- Policy-excluded rows: `6`.
- Stable-identity-required rows excluded: `3`.
- Pending/deferred OCR or parsing rows: `2`.
- PDF answer-generation denominator: `0`.

Evidence gate metrics:

- `bbox_available`: `0.571`.
- `table_or_caption_included`: `0.0`.
- `nearby_paragraph_included`: `0.0`.
- `OCR_confidence_available`: `0.0`.
- Citation locator completeness: `0.0`.
- Metadata key-presence completeness: `1.0`.
- Metadata non-empty/value completeness: `0.473`.
- `page_hit` and `region_hit`: `null`, because no live retrieval was run for
  this diagnostic strict gate.

Interpretation:

- The active PDF C7 controls are retrieval/evidence candidates only. The active
  repo artifacts do not yet expose the source search unit id/rank,
  parser/source metadata, OCR confidence, or nearby paragraph context required
  for strict silver promotion.
- All 7 input rows remain diagnostic-only with
  `pdf_context_diagnostic_only_missing_layout`.
- PDF CONTENT evidence and FILE/document identity lanes remain separate; generic
  filename-only identity remains blocked with `stable_identity_required`.
- Answer/citation generation surfaces remain `NOT_OPENED`.
- Promotion evidence created remains `false`.
- No official denominator, production vector/index/namespace, candidate
  artifact, or immutable baseline mutation occurred.

## Phase 2 And License Readiness

Current license-gate snapshot after the 2026-05-11 refresh:

| Item | Value |
|---|---:|
| Manifests | `28` |
| Rows / canonical rows | `2115` / `1053` |
| License verified / unknown / blocker | `1424` / `591` / `0` |
| Source terms ambiguous or inferred | `100` |
| Internal eval ready | `1524` |
| Embedding ready | `578` |
| Vector DB internal ready | `546` |
| Public release allowed | `142` |
| Review required | `1893` |
| OCR/MM ready | `796` |
| RAG ready | `312` |

Current Phase 2 denominator interpretation:

| Scope | Official current | Conservative review unlock | Promotion-scope current |
|---|---:|---:|---:|
| RAG retrieval core, rows | `304/512` | `390/512` | `40/40` |
| RAG retrieval core, canonical | `152/252` | `191/252` | `20/20` |
| Visual shadow, rows | `144/1244` | `416/1244` | `54/56` |
| Visual shadow, canonical | `72/622` | `208/622` | `27/28` |

Interpretation rules:

- Row-level and canonical-level denominators must be reported together.
- Promotion-scope views are diagnostic/report-only. They do not mutate official
  denominators and do not create gold/support/public-release evidence.
- Review existing data.go.kr and Seoul Open Data rows before collecting more.
- Add new data only when item-level or equivalent license evidence is captured
  before the row enters readiness denominators.
- Keep FUNSD, NAMU, PRISM, public-institution parser-smoke rows, and ambiguous
  DART/Hugging Face rows out of promotion by default until the required
  item-level or document-level evidence exists.

## Guardrails

- Do not run broad candidate indexing. Use scoped identity and
  `allowUnscoped=false`.
- Do not mutate immutable baselines, `rag-data-canary`, candidate artifacts, or
  official denominator files during diagnostic/report-only work.
- Do not treat bootstrap descriptors, dry-run previews, local LLM smoke output,
  answer-recovery diagnostics, or cleanup reports as promotion evidence.
- Keep hidden XLSX content out of query, gold, candidate, answer, and public
  surfaces.
- Keep PDF native text authoritative; OCR fallback is lower-trust metadata unless
  a later policy says otherwise.
- Keep active and historical eval paths separate. Current worker eval code lives
  under `ai-worker/eval/`.
- Current SearchUnit indexing CLI is `python -m app.cli.search_unit_indexing`
  from `ai-worker/`.
- For Phase 7 v4 style answerability joins, use `rag_chunks.jsonl`; do not
  substitute `chunks_v4.jsonl`.
- Generated raw outputs should prefer an external runtime root such as
  `../_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/`.

Current guardrail state:

| Guardrail | State |
|---|---|
| Official denominator registry changed | `false` |
| Production index mutation | `false` |
| Production vector write | `false` |
| Namespace created by diagnostics | `false` |
| Hidden XLSX exposed | `false` |
| Promotion evidence created | `false` |
| XLSX strict repo-local full manifest written | `false` |
| Support-eligible OCR/MM count | `0` |
| Annotation-answer embedding count | `0` |
| Answer recovery embedding backend available | `true` |
| Answer recovery embedding model / dimension | `BAAI/bge-m3` / `1024` |
| Answer recovery current-checkout existing-index probe | `deferred`; local indexes were externalized, so no production or diagnostic namespace was restored or written |

## Canonical References

Planning and orientation:

- `docs/codex-rag-ingestion-next-steps.md`
- `docs/rag-ingestion-p1-next-plan.md`
- `docs/track_a_xlsx_retrieval_improvement_plan.md`
- `docs/track_b_text_retrieval_e2e_plan.md`
- `docs/track_c_pdf_embedding_preparation_plan.md`

Current status and policy:

- `ai-worker/eval/eval_queries/official_denominator_registry.json`
- `docs/eval/denominator_policy.md`
- `ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.md`
- `ai-worker/eval/reports/rag-ingestion/README.md`
- `docs/rag-ingestion/xlsx-retrieval/README.md`
- `docs/track_b_text_retrieval_e2e/README.md`
- `docs/track-c-pdf-embedding-preparation/README.md`

Current diagnostic reports:

- `ai-worker/eval/reports/rag-ingestion/xlsx_pre_silver_risk_closure_20260507.md`
- `ai-worker/eval/reports/rag-ingestion/xlsx_pre_silver_risk_closure_20260507.json`
- `ai-worker/eval/reports/rag-ingestion/xlsx_end_to_end_preflight_20260507.md`
- `ai-worker/eval/reports/rag-ingestion/xlsx_end_to_end_preflight_20260507.json`
- `ai-worker/eval/reports/rag-ingestion/answer_recovery_tuning_report.md`
- `ai-worker/eval/reports/rag-ingestion/answer_recovery_tuning_report.json`
- `ai-worker/eval/reports/rag-ingestion/rag_reviewed_gold_policy_normalization_report.md`
- `ai-worker/eval/reports/rag-ingestion/rag_reviewed_gold_policy_normalization_report.json`
- `ai-worker/eval/reports/rag-ingestion/xlsx_hidden_excluded_leakage_probe_report.md`
- `ai-worker/eval/reports/rag-ingestion/xlsx_hidden_excluded_leakage_probe_report.json`
- `ai-worker/eval/reports/rag-ingestion/xlsx_strict_silver_generation_report.md`
- `ai-worker/eval/reports/rag-ingestion/xlsx_strict_silver_generation_report.json`
- `ai-worker/eval/reports/rag-ingestion/pdf_strict_silver_generation_report.md`
- `ai-worker/eval/reports/rag-ingestion/pdf_strict_silver_generation_report.json`
- `ai-worker/eval/review/rag_gold_policy_resolution_packet_v1.md`
- `ai-worker/eval/review/rag_gold_policy_resolution_packet_v1.json`
- `ai-worker/eval/review/route_gold_label_review_pack_v1.md`
- `ai-worker/eval/review/route_gold_label_review_pack_v1.json`
- `ai-worker/eval/review/fallback_outcome_label_review_pack_v1.md`
- `ai-worker/eval/review/fallback_outcome_label_review_pack_v1.json`
- `ai-worker/eval/review/route_gold_label_review_applied_v1.md`
- `ai-worker/eval/review/route_gold_label_review_applied_v1.json`
- `ai-worker/eval/review/fallback_outcome_label_review_applied_v1.md`
- `ai-worker/eval/review/fallback_outcome_label_review_applied_v1.json`
- `.tmp/phase2-review-unlock/phase2_review_unlock_estimate.md`
- `.tmp/phase2-review-unlock/phase2_review_unlock_estimate.json`

External archive manifests:

- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_210945\external_archive_manifest.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_212609\external_archive_manifest.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_212609\external_archive_manifest.csv`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260511-eval-report-cleanup\archive_summary.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260511-eval-report-cleanup\archive_manifest.csv`
- `..\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\2026-05-11-portfolio-cleanup\`

## Short History

| Date | Milestone |
|---|---|
| 2026-05-03 | Added ingestion v2 schema/provenance foundation, SearchUnit v2 metadata, and initial XLSX/PDF smoke paths. |
| 2026-05-04 | Hardened SearchUnit indexing identity, hidden XLSX leakage checks, and candidate consistency reports. |
| 2026-05-05 | Completed Track A XLSX A0-A6 diagnostic cleanup; promotion evidence remained blocked. |
| 2026-05-06 | Kept XLSX/PDF/TEXT denominators separate and added PDF/XLSX answer-shape diagnostics; answer denominators stayed `0`. |
| 2026-05-07 | Prepared PDF/TEXT review packs, approved strict XLSX silver generation, and externalized large generated/cache payloads. |
| 2026-05-08 to 2026-05-10 | Ran silver-only tuning, PDF FILE hard-negative, answer-recovery, and compact-report diagnostics; all remained diagnostic-only. |
| 2026-05-11 | Refreshed license evidence, reran Phase 2 readiness, implemented 3-track orchestration contracts, and archived ignored eval/report/index/dataset payloads externally. |
| 2026-05-13 | Generated the PDF strict retrieval/evidence diagnostic silver gate report; no strict PDF rows were promoted because active artifacts lack required source-unit/layout/OCR metadata. |

## 2026-05-11 - Answer Recovery Consolidation

- Status: `consolidated_diagnostic_only`; official baseline is
  `calibrated_identity_exact_v1`.
- Consolidated report: `ai-worker/eval/reports/rag-ingestion/answer_recovery_tuning_report.md`
  / `.json`; category counts are recorded there with row-id groups.
- User action required: only the 6 `GOLD_POLICY_REQUIRED` rows need gold-policy
  judgment for expected answer/evidence semantics, answerability/relevance, and
  future denominator inclusion. Codex did not decide those fields.
- Diagnostic-only remains diagnostic-only: 4 OCR/IDP/multimodal rows, the 17
  correctly policy-blocked rows, and the 12 frozen-gold-sourced excluded rows
  do not become promotion, support, or official denominator evidence.
- Denominator and promotion state did not change because
  `official_answer_denominator_opened=false`,
  `official_denominator_registry_changed=false`, and
  `production_promotion_ready=false`.
- Embedding backend recheck is available with `BAAI/bge-m3` and dimension
  `1024`; the current checkout cannot re-run the prior 5/5 rank-1 existing
  embedding probe because local index files were externalized on 2026-05-11.
  Treat that as archived historical evidence, not a current production proof.
- Verification: compact report runner `PASS`; targeted no-cache pytest guardrail
  suite passed `26` tests. A broader stage-artifact-oriented pytest command is
  still expected to fail until detailed generated stage artifacts are restored
  or those tests are converted to compact/in-memory fixtures.

## 2026-05-11 - Reviewed Gold Policy Normalization

- Imported canonical review-pack CSVs under `ai-worker/eval/review/` for
  TEXT/Namu v2 (`100` rows), XLSX human review (`50` rows), and PDF file-lookup
  companion (`28` rows). The accessible XLSX external export matched the repo
  copy by sha256; `/mnt/data` was not mounted in this Windows workspace.
- Normalization report:
  `ai-worker/eval/reports/rag-ingestion/rag_reviewed_gold_policy_normalization_report.md`
  / `.json`; exact proposed-candidate and review-required row ids are recorded
  in the JSON report.
- Proposed candidates remain proposals, not registry gold: TEXT/Namu content
  evidence `66`, XLSX evidence `25`, PDF content evidence `14`, and PDF
  FILE/document identity `5`. The PDF lanes are not summed into a single
  official-candidate denominator.
- Rows kept out of proposed positives: TEXT diagnostic-only defaults `10`,
  TEXT source-binding review `7`, TEXT policy/invalid rows `8`; XLSX source
  verification `10`, evidence mismatch `7`, policy-excluded/not-answerable `7`,
  diagnostic-only `1`; PDF expected-evidence revision `9` and
  NOT_ANSWERABLE/IRRELEVANT issue rows `6`.
- User gold-policy review remains only where expected answer, expected evidence,
  answerability/relevance, or denominator inclusion cannot be safely finalized:
  TEXT `23`, XLSX `35` (`25` candidate-inclusion confirmations plus `10`
  source-verification rows), PDF `9`.
- Guardrails held: no production namespace mutation, no retrieval variant run,
  no official denominator opened, no official denominator registry mutation, and
  no diagnostic-only row promoted. Raw review packs remain local/ignored; the
  canonical report records paths, hashes, counts, and normalized policy buckets.

## 2026-05-12 - Gold Policy Resolution Packet v1

- Scope: report-only resolution packet for XLSX denominator-confirmation rows
  and PDF expected-evidence revision rows. TEXT/Namu unresolved rows were
  carried forward unchanged and not resolved in this task.
- Generated packet: `ai-worker/eval/review/rag_gold_policy_resolution_packet_v1.md`
  / `.json`.
- XLSX processed `25`: `23` recommend
  `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE`, `2` stay
  `KEEP_PENDING_EVIDENCE` because existing strict XLSX normalization already
  flagged evidence/locator contract gaps.
- PDF processed `9`: `6` recommend `EXCLUDE_POLICY_OR_NOT_ANSWERABLE`, `3`
  stay `KEEP_PENDING_USER_REVIEW` for generic-filename file/document identity
  risk. PDF content evidence and FILE/document identity lanes remain separate
  and are not summed.
- User gold-policy decisions still required in this packet: XLSX `25`
  denominator/evidence decisions, PDF `9` expected-evidence/lane decisions, plus
  the unchanged TEXT/Namu `23` for a later TEXT-only review.
- Guardrails held: no retrieval variants ran, no production namespace was
  mutated, `official_denominator_registry.json` was not changed, no official
  denominator was opened, and no diagnostic-only row was promoted.

## 2026-05-12 - Gold Policy Decision Draft v1

- Scope: report-only decision draft derived from
  `ai-worker/eval/review/rag_gold_policy_resolution_packet_v1.json`; no
  official denominator membership was frozen.
- Generated draft: `ai-worker/eval/review/rag_gold_policy_decision_draft_v1.md`
  / `.json`.
- XLSX processed `25`: `23` draft
  `INCLUDE_AS_GOLD_V0_1_CANDIDATE`, `2` remain
  `KEEP_PENDING_EVIDENCE` (`gq_xlsx_date_number_format_003`,
  `gq_xlsx_aggregation_001`).
- PDF processed `9`: `6` draft `EXCLUDE_FROM_GOLD_V0_1`, `3` remain
  `KEEP_PENDING_FILE_IDENTITY_REVIEW` for stable document identity/lane review.
  PDF content evidence and FILE/document identity lanes were not aggregated.
- TEXT/Namu unresolved rows were carried forward unchanged: `23`.
- Guardrails held: no retrieval variants ran, no production namespace was
  mutated, `official_denominator_registry.json` was not changed, no official
  denominator was opened, and no diagnostic-only row was promoted.

## 2026-05-12 - Gold Policy User Review Sheet v1

- Scope: compact user-facing sheet generated from
  `ai-worker/eval/review/rag_gold_policy_decision_draft_v1.json`; no official
  denominator membership was frozen.
- Generated sheet:
  `ai-worker/eval/review/rag_gold_policy_user_review_sheet_v1.md`.
- Actionable row sections: XLSX pending evidence `2`, PDF pending file identity
  `3`. Batch sections: XLSX include candidates `23`, PDF exclude candidates
  `6`. TEXT/Namu unresolved rows `23` were carried forward unchanged.
- Guardrails held: no retrieval variants ran, no production namespace was
  mutated, `official_denominator_registry.json` was not changed, and no
  diagnostic-only row was promoted.

## 2026-05-12 - Gold Policy User-Approved Resolutions v1

- Scope: report-only materialization of the user's review-sheet decisions; no
  official denominator membership was frozen.
- Generated resolutions:
  `ai-worker/eval/review/rag_gold_policy_user_approved_resolutions_v1.md`
  / `.json`.
- User-approved state: XLSX draft `gold_v0.1` candidates `23`; XLSX pending
  evidence `2`; PDF approved excludes `6`; PDF generic-filename rows excluded
  with stable document identity required `3`; TEXT/Namu unresolved carry-forward
  `23`.
- Guardrails held: no retrieval variants ran, no production namespace was
  mutated, `official_denominator_registry.json` was not changed, no official
  denominator was opened, and excluded/PDF policy rows were not counted as
  retrieval failures.

## 2026-05-12 - Gold Policy Applied Decisions v1

- Scope: report-only application of the user decisions already recorded for
  `rag_gold_policy_user_review_sheet_v1`; no official denominator membership
  was frozen.
- Generated applied artifacts:
  `ai-worker/eval/review/rag_gold_policy_applied_decisions_v1.md` / `.json`;
  updated sheet status in
  `ai-worker/eval/review/rag_gold_policy_user_review_sheet_v1.md` to
  `APPLIED`.
- Applied state: XLSX draft `gold_v0.1` candidates `23`; XLSX pending evidence
  `2`; PDF excludes `6`; PDF stable-identity-required excludes `3`; TEXT/Namu
  unresolved carry-forward `23`.
- Guardrails held: no retrieval variants ran, no production namespace was
  mutated, `official_denominator_registry.json` was not changed, no official
  denominator was opened/frozen, no diagnostic-only row was promoted, and PDF
  content/file identity lanes were not aggregated.

## 2026-05-12 - Three-Track Routing Diagnostic Guardrails

- Status: `implemented_diagnostic_only`.
- Evidence: `ai-worker/eval/reports/rag-ingestion/three_track_orchestration_report.md`
  / `.json`.
- Scope: query-time route diagnostics for `text_namuwiki_animation`,
  `xlsx_business_structured`, and `pdf_business_ocr_mm`; no official route
  metrics, denominator, namespace, vector index, or promotion state changed.
- Guardrails added/verified: rule scoring precedes LLM adjudication; the LLM is
  called only for ambiguous/hard diagnostic routes and strict JSON validation
  fails closed; ambiguous routes stay `diagnostic_multi_route` or bounded
  fallback; PDF generic filename-only identity is blocked with
  `stable_identity_required`; XLSX hidden/excluded candidates are blocked with
  `hidden_negative_or_excluded_row_guard`; PDF content and FILE identity lanes
  remain separate.
- Verification: py-compile passed; targeted no-cache pytest passed
  `158` tests; `SearchUnitIndexingServiceTest` passed under Maven; the official
  denominator registry remained unchanged.

## 2026-05-12 - Route/Fallback Label Review Packs v1

- Status: `generated_diagnostic_only_pending_human_review`.
- Evidence: `ai-worker/eval/review/route_gold_label_review_pack_v1.md` /
  `.json`, `ai-worker/eval/review/fallback_outcome_label_review_pack_v1.md` /
  `.json`.
- Counts: human review rows `8`; Codex diagnostic-only auto-classified rows
  `8`; official metric input rows `0`.
- Guardrails held: no official denominator registry change, no production
  namespace/vector/index mutation, no candidate artifact or immutable baseline
  mutation, no diagnostic-only promotion, no PDF lane aggregation, and no XLSX
  hidden/excluded content exposure.
- Next: human review is still required before routing accuracy, wrong-route
  rate, fallback success, or multi-route success can become official metrics.

## 2026-05-12 - Route/Fallback Label Review Applied v1

- Status: `applied_diagnostic_only`.
- Evidence: `ai-worker/eval/review/route_gold_label_review_applied_v1.md` /
  `.json`, `ai-worker/eval/review/fallback_outcome_label_review_applied_v1.md`
  / `.json`.
- Counts: route human rows applied `5`; fallback human rows applied `3`;
  Codex diagnostic-only auto-classified rows unchanged `8`; official metric
  input rows `0`.
- Decisions: `3` clarification-required rows are not fallback successes; `2`
  OCR/parsing/source-context deferred rows are not direct route successes.
- Guardrails held: original review packs left unchanged, no official denominator
  registry change, no production namespace/vector/index mutation, no
  diagnostic-only promotion, no PDF lane aggregation, and no XLSX hidden/excluded
  content exposure.

## 2026-05-12 - XLSX Hidden/Excluded Leakage Probe

- Status: `PASS`; evidence:
  `ai-worker/eval/reports/rag-ingestion/xlsx_hidden_excluded_leakage_probe_report.md`
  / `.json`.
- Scope: diagnostic-only scan before any XLSX answer-generation or promotion
  lane; no retrieval run, answer-generation run, vector write, candidate artifact
  mutation, immutable baseline mutation, or denominator registry update.
- Probe targets: normalized XLSX excluded rows `14`, normalized hidden-negative
  rows `3`, and route/fallback hidden-excluded guard rows `2` (`16` target rows
  total).
- Result: query/candidate/debug-public/official-denominator surfaces had
  leakage count `0`; answer/citation surfaces remain `NOT_OPENED`;
  policy-excluded rows counted as retrieval failures `false`.
- Verification: py-compile passed; targeted no-cache pytest passed `26` tests;
  JSON reports parsed; `official_denominator_registry.json` remained
  unchanged.

## 2026-05-12 - XLSX Strict Silver Generation

- Status: `COMPLETED_DIAGNOSTIC_ONLY`; evidence:
  `ai-worker/eval/reports/rag-ingestion/xlsx_strict_silver_generation_report.md`
  / `.json`.
- Scope: strict XLSX retrieval/evidence silver only through
  `rag_xlsx_pre_silver_risk_closure.py` and
  `rag_xlsx_retrieval_performance_diagnostic.py`; no answer-generation,
  production promotion, registry mutation, candidate artifact mutation, or
  baseline mutation.
- The full JSONL manifest is external-only. Repo-local manifest writes are
  blocked by `assert_external_silver_output_path`, and failed guardrail runs do
  not emit the manifest.
- Counts: input denominator rows `23`, generated silver rows `23`, pending
  evidence rows excluded `2`, normalized excluded rows excluded `14`,
  hidden-negative rows excluded `3`, diagnostic-only fallback rows `0`.
- Result: hidden/excluded leakage `PASS`; answer/citation surfaces
  `NOT_OPENED`; policy-excluded rows counted as retrieval failures `false`;
  citation locator completeness `1.0`.

## Next Recommended Steps

1. Review the XLSX strict silver generation report and external manifest before
   any answer-generation or promotion policy change.
2. Review any newly opened XLSX answer/citation/debug/public surfaces with the
   focused normalized excluded-row / hidden-negative leakage probe before using
   them for answer-generation or promotion.
3. Resolve PDF review decisions for page/table/bbox evidence, answerability, and
   FILE vs CONTENT routing.
4. Review TEXT/NAMU v2 candidates and actual generated answers before changing
   R8 citation-support denominators.
5. Use the applied route/fallback label artifacts for diagnostic analysis only;
   create a separate policy review before any official route metric promotion.
6. For Phase 2B, review high-yield existing public-data rows first; collect new
   rows only with item-level or equivalent evidence captured up front.
7. Keep large generated artifacts outside the repo and preserve only small
   current summaries, official registries, and reviewed artifacts.

## Update Policy

Future updates should edit the current tables above instead of appending a long
daily log. If a new entry is needed, keep it under about 10 lines:

```markdown
## YYYY-MM-DD - short title

- Status: `...`
- Evidence: `path/to/report.json`, `path/to/report.md`
- Counts: key numbers only
- Verification: command summary and result
- Next: one or two concrete actions
```

If the entry needs more detail than that, write or regenerate a report file and
link it from `Canonical References`.
