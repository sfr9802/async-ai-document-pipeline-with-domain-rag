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
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_214525\external_archive_manifest.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_214525\external_archive_manifest.csv`

## 2026-05-07 - remaining storage cleanup

- Status: `REMAINING_STORAGE_REDUCED_WITH_ACTIVE_PHASE7_HELD`.
- Scope: moved only ignored/untracked legacy or stale generated payloads to the
  external archive; no tracked files were moved or deleted.
- Evidence:
  `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_214525\external_archive_manifest.json`.
- Counts: workspace size went from `8,968,446,646` bytes (`8.353 GiB`) to
  `6,296,876,287` bytes (`5.864 GiB`); archived `56` files /
  `2,671,570,359` bytes (`2,547.81 MiB`), all SHA256 verified.
- Externalized: legacy v3 corpus payloads, legacy v3 preprocessed/token corpus
  outputs, non-promoted Phase 7 `title-section` comparison index, and the top
  stale generated `local-storage/<job-id>` XLSX runtime outputs.
- Held: active `namu-v4-structured-combined` corpus, promoted
  `retrieval-title-section` index, `rag-data*` baseline/candidates, current
  Phase 7 `rag_chunks_*`, source datasets/gold/review files, and `.git`/LFS.
- Verification: final git status stayed clean; `anime_namu_v3/README.md` and
  promoted retrieval index still exist; active vector hashes are checked in the
  cleanup response.
- Next: migrate remaining large re-runnable eval outputs to explicit external
  runtime roots before generating more Phase 7 or local-storage artifacts.

## 2026-05-07 - eval directory naming cleanup

- Status: `EVAL_DIRECTORY_NAVIGATION_IMPROVED`.
- Scope: documented the active role of each `ai-worker/eval/` directory and
  renamed the low-risk legacy A/B fixture directory from `agent_loop_ab/` to
  `legacy_agent_loop_ab/`.
- Preservation: high-reference eval contract paths such as `harness/`,
  `reports/`, `eval_queries/`, `datasets/`, `review/`, `artifacts/`,
  `corpora/`, `indexes/`, and `golden_retrieval/` were not physically renamed
  because they are used by code, reports, descriptors, fixtures, or gold/review
  workflows.
- Verification: tracked references were updated to the new legacy A/B path;
  historical ignored Phase 7 report mentions were normalized as provenance text.
- Cleanup: validation-created Python `__pycache__` directories were moved to
  `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_220341\external_archive_manifest.json`
  with SHA256 verification, leaving the `eval/` root directory list clean.
- Next: if a future physical rename is needed for `review/` or `artifacts/`,
  first add compatibility wrappers or explicit config indirection because those
  names are already part of the eval/report surface.

## 2026-05-07 - XLSX/PDF route trace diagnostics

- Status: `DIAGNOSTIC_ONLY_ROUTE_TRACE_READY`.
- Scope: added report-replay XLSX/PDF route tracing and bounded agentic
  retrieval-route verification; no answer generation, broad indexing,
  promotion, baseline mutation, or candidate artifact mutation was run.
- Evidence:
  `ai-worker/eval/reports/rag-ingestion/xlsx_pdf_route_trace_diagnostic_20260507.json`,
  `ai-worker/eval/reports/rag-ingestion/xlsx_pdf_route_trace_diagnostic_20260507.md`,
  `ai-worker/eval/reports/rag-ingestion/xlsx_pdf_agentic_route_loop_diagnostic_20260507.json`,
  `ai-worker/eval/reports/rag-ingestion/xlsx_pdf_agentic_route_loop_diagnostic_20260507.md`.
- Counts: route trace `PASS=5`, `REVIEW_REQUIRED=5`, `FAIL=0`;
  XLSX hidden leakage `0`; agentic cases `10`, retry exhausted `0`.
- Verification: py_compile passed; focused pytest bundle passed
  `82 passed`; both diagnostic CLIs regenerated reports with
  `promotion_evidence=false` and denominator registry diff empty.
- Next: use these diagnostics while XLSX/PDF gold and PDF policy review
  decisions remain separate from official answer metrics.

## 2026-05-07 - PDF review pack application

- Status: `PDF_REVIEW_PACK_CONSUMED_DIAGNOSTIC_ONLY`.
- Scope: located and consumed the latest merged PDF manual v1 review pack with
  FILE lookup companion; normalized retrieval/evidence rows without answer
  generation, broad indexing, registry mutation, or candidate artifact writes.
- Evidence:
  `ai-worker/eval/reports/rag-ingestion/pdf_review_pack_validation_20260507.json`,
  `ai-worker/eval/reports/rag-ingestion/pdf_reviewed_retrieval_evidence_application_20260507.json`,
  `ai-worker/eval/reports/rag-ingestion/pdf_reviewed_route_trace_diagnostic_20260507.json`,
  `ai-worker/eval/reports/rag-ingestion/pdf_reviewed_agentic_route_loop_diagnostic_20260507.json`,
  `ai-worker/eval/reports/rag-ingestion/pdf_xlsx_review_application_manifest_20260507.toml`.
- Counts: source rows `108`; complete reviewed rows `0`; official candidates
  `0`; excluded incomplete `108`; route trace `REVIEW_REQUIRED=108`,
  `FAIL=0`; table lane `24`, FILE lookup `28`, CONTENT lookup `80`;
  agentic cases `116`, retry exhausted `7`, max attempts `3`.
- Verification: py_compile passed; focused pytest bundle passed `65 passed`;
  review-application CLI regenerated reports; denominator registry diff empty;
  protected index/canary git status empty.
- Next: apply filled user review decisions through an explicit PDF
  retrieval/evidence normalizer before any registry mutation or live official
  denominator run.

## 2026-05-08 - XLSX strict silver generation v0

- Status: `XLSX_SILVER_GENERATION_COMPLETE`.
- Scope: generated XLSX retrieval/evidence silver only through the strict
  XLSX wrapper path; no retrieval tuning, answer scoring, broad indexing,
  official denominator mutation, or TEXT/PDF behavior change.
- Evidence:
  `ai-worker/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_generation_report_20260507.json`,
  `ai-worker/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_generation_report_20260507.md`,
  `ai-worker/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_generation_manifest_v0.json`,
  `ai-worker/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_validation_report_v0.json`.
- Counts: generated candidates `702`; valid rows `699`; rejected rows `3`
  (`synthetic_label_not_source_bound`); selected silver rows `500`; dev
  rows `350`; holdout rows `150`; official XLSX retrieval/evidence denominator
  `23 -> 23`; XLSX answer-generation denominator `0 -> 0`.
- Verification: generation CLI regenerated the bundle; py_compile passed;
  focused pytest passed `48 passed`; route guard passed; denominator guard
  passed; manifest hashes passed; exact range/cell query leakage `0`; dev/holdout
  source-content/citation/range overlap `0`; hidden check is
  `PASS_METADATA_ONLY` with workbook reopen not run in this phase.
- Next: run an XLSX silver retrieval baseline against `silver_dev`, keeping
  `silver_holdout` sealed for later tuning verification.

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
| 2026-05-07 | Externalized remaining legacy/stale storage payloads and reduced workspace to `5.864 GiB`. |

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
