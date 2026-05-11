# RAG Ingestion Progress

Last updated: 2026-05-11 KST.

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

## Track Board

| Track | Current state | Current denominator / metric | Next action |
|---|---|---|---|
| `xlsx_business_structured` | `APPROVED_FOR_XLSX_SILVER_GENERATION_STRICT` for retrieval/evidence only | Official retrieval/evidence denominator `23`; answer-generation denominator `0`; live smoke Hit@10 `1.0`, MRR@10 `0.942`, citation accuracy `1.0` | Generate XLSX silver only through the strict wrapper. Before answer-generation or promotion work, add a focused excluded-row / hidden-negative leakage probe. |
| XLSX legacy diagnostic | Historical / superseded | Legacy Track A reviewed diagnostic denominator `35`; exact location recovered by top 10 | Preserve only as historical diagnostic evidence. Do not use as the current wrapper default. |
| `text_namuwiki_animation` | Review / candidate-prep lane | Bound TEXT/NAMU diagnostic positive denominator `47`; current answer/citation-support denominator not opened | Review v2 candidates and collect actual generated answer output before any R8 citation-support denominator. Keep NAMU noncommercial-limited and out of public/support/gold promotion by default. |
| `pdf_business_ocr_mm` | Policy/review lane | Conservative PDF positive controls `7`; candidate rows `9`; diagnostic-only rows `6`; answer denominator `0` | Resolve user/policy decisions for expected evidence, answerability, table/page/bbox policy, and FILE vs CONTENT routing. |
| Route/orchestration metrics | Diagnostic-only | Route gold labels and fallback outcome labels do not exist yet | Add route labels before interpreting routing accuracy, wrong-route rate, fallback success, or multi-route success as metrics. |
| Answer recovery | Diagnostic-only | Expanded diagnostic run used `185` cases; no official answer denominator opened | Keep recovery-loop results out of promotion until human-reviewed answer/evidence and identity-correctness labels exist. |

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
| Support-eligible OCR/MM count | `0` |
| Annotation-answer embedding count | `0` |

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

## Next Recommended Steps

1. Run XLSX silver generation only through the strict wrapper path approved by
   `xlsx_pre_silver_risk_closure_20260507`.
2. Add the focused normalized excluded-row / hidden-negative leakage probe before
   opening any XLSX answer-generation or promotion lane.
3. Resolve PDF review decisions for page/table/bbox evidence, answerability, and
   FILE vs CONTENT routing.
4. Review TEXT/NAMU v2 candidates and actual generated answers before changing
   R8 citation-support denominators.
5. Add route gold labels and fallback outcome labels before interpreting route
   metrics as anything beyond diagnostics.
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
