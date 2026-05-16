# RAG Ingestion Progress

Last updated: 2026-05-16 KST.

This file is the compact status index for RAG ingestion. It should not store
turn-level logs, command transcripts, raw report payloads, or per-agent notes.
Keep detailed evidence in report files, review packs, generated manifests, or
external archive manifests and link only the current source of truth here.

## Current Status

Overall status: `official_question_gold_v2_metric_first_run_blocked_scorer_backend_unavailable`;
the registry-backed metric inputs are ready, but the first official
answer/citation metric attempt did not start scoring because no official
scorer/backend is wired. Model-quality tuning remains closed.

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
  `ai/eval/reports/rag-ingestion/answer_recovery_tuning_report.md`;
  detailed stage/debug reports remain generated artifacts unless explicitly
  re-emitted.

## Track Board

| Track | Current state | Current denominator / metric | Next action |
|---|---|---|---|
| `xlsx_business_structured` | Evidence/answer-citation readiness remains `DIAGNOSTIC_POLICY_PACKET_READY`; local-LLM question/expected-answer draft candidates were human-reviewed and applied to question-gold v2 | Strict silver rows `23`; clean pass rows `23`; verifier-clean and human-approved candidate rows `19`; registry-backed official metric input rows `19`; denominator policy `question_answer_citation_gold_v2` | First official metric report consumed this track but did not score because the official scorer/backend is unavailable. Wire/start scorer backend and rerun; tuning remains closed. |
| XLSX legacy diagnostic | Historical / superseded | Legacy Track A reviewed diagnostic denominator `35`; exact location recovered by top 10 | Preserve only as historical diagnostic evidence. Do not use as the current wrapper default. |
| `text_namuwiki_animation` | Frozen TEXT/Namu V2.1 policy packet `FROZEN_DIAGNOSTIC_V2_1`; human-approved v2 answer/citation input rows are materialized separately | Generated-answer review rows `66`; clean `60`; cleanup `5`; unresolved `1`; citation supported `65`; registry-backed official metric input rows `6`; denominator policy `question_answer_citation_gold_v2` | First official metric report consumed this track but did not score because the official scorer/backend is unavailable. Preserve `text_namu_v2_0017` as a diagnostic support warning. |
| `pdf_business_ocr_mm` | Locator/bbox evidence readiness remains complete (`7/7`); context v2 resolves native/nearby block text and deterministic table rows; manually authored source-bound drafts were human-reviewed and applied to question-gold v2 | Strict ready rows `7`; native block text resolved `7`; deterministic table-ready rows `2`; manually authored and human-approved candidate rows `4`; registry-backed official metric input rows `4`; denominator policy `question_answer_citation_gold_v2` | First official metric report consumed this track but did not score because the official scorer/backend is unavailable. Wire/start scorer backend and rerun; tuning remains closed. |
| Route/orchestration metrics | Diagnostic-only | Korean memo labels applied in diagnostic-only route/fallback artifacts; official metric input rows remain `0` | Use the applied route/fallback labels for diagnostic analysis only. Create an explicit policy review before interpreting routing accuracy, wrong-route rate, fallback success, or multi-route success as official metrics. |
| Answer recovery | Diagnostic-only consolidation complete | Baseline `calibrated_identity_exact_v1`; compact status `PASS`; `185` cases; triage counts: safe-recoverable report-only `5`, index-scope-missing `5`, policy-blocked-correctly `17`, gold-policy-required `6`, diagnostic-only-do-not-promote `4`, unknown `0`; answer denominator `0`; production promotion `false` | User gold-policy judgment is needed only for the 6 `GOLD_POLICY_REQUIRED` rows. Keep safe recoveries report-only and keep index-scope rows out of retrieval/ranking failure counts until source evidence is proven in-scope and indexed. |

## 2026-05-14 XLSX/PDF Pre-Tuning Diagnostic Readiness

Status: `REPORT_ONLY_READY`.

- XLSX policy packet: `DIAGNOSTIC_POLICY_PACKET_READY`.
- XLSX raw leakage status: `PASS`; pre-leakage support pass rows `23`, final clean pass rows `23`.
- PDF layout gap closure: strict ready rows `4 -> 7`; fallback rows `3 -> 0`.
- PDF answer/citation packet: `DIAGNOSTIC_POLICY_PACKET_READY`; clean pass rows `7`, cleanup `0`, unresolved `0`, lane policy blocked `0`.
- Remaining PDF fallback row ids: `none`; source-bound bbox resolved for `gq_auto_010`, `gq_auto_015`, and `gq_auto_030`.
- PDF strict readiness gate rerun: `true` as diagnostic readiness-gate only; answer generation opened `false`.
- Three-track board is now superseded by the 2026-05-15 v2 question-quality
  refresh: evidence readiness remains complete, but official question-gold is
  incomplete.
- Tuning readiness plan remains report-only; tuning execution remains closed.
- Official metric input rows remain `0` for TEXT/XLSX/PDF.
- Tuning run started: `false`.
- Denominator registry unchanged by this diagnostic/report-only slice.

## 2026-05-15 PDF Answer/Citation Diagnostic Packet

Status: `DIAGNOSTIC_POLICY_PACKET_READY`.

- Evidence: `ai/eval/reports/rag-ingestion/pdf_answer_citation_diagnostic_report.json`
  / `.md`, `pdf_answer_citation_diagnostic_review_input.jsonl`, and
  `rag_pdf_answer_citation_policy_review_packet_v1.json` / `.md`.
- Counts: input `7`, strict ready `7`, generated answer rows `7`, answer
  support pass `7`, citation locator valid `7`, clean pass `7`, cleanup `0`,
  unresolved `0`, lane policy blocked `0`.
- Board: `DIAGNOSTIC_PREFLIGHT_READY`; tuning plan `REPORT_ONLY_READY`.
- Guardrails: `official_metric_input_rows=0`, `tuning_run_started=false`,
  official metrics and denominators closed, denominator registry unchanged.

## 2026-05-15 Report-Only Dry-Run Plan And Human Audit Packet

Status: `REPORT_ONLY_DRY_RUN_PLAN_READY`; human audit packet
`HUMAN_AUDIT_PACKET_READY`.

- Generated plan:
  `ai/eval/reports/rag-ingestion/report_only_tuning_dry_run_plan_v1.json`
  / `.md`.
- Generated human audit packet:
  `ai/eval/review/rag_human_audit_packet_v1.json` / `.md`.
- Generated transition checklist:
  `ai/eval/reports/rag-ingestion/official_metric_transition_readiness_checklist_v1.json`
  / `.md`.
- Board: `DIAGNOSTIC_PREFLIGHT_READY`; tuning readiness plan:
  `REPORT_ONLY_READY`.
- User-action audit rows: total `19` (`pdf_business_ocr_mm=11`,
  `text_namu_v2_1=6`, `xlsx_business_structured=2`); decision types are
  expected answer/evidence semantics, answerability, relevance, final gold
  policy, and official denominator inclusion.
- Non-action diagnostic-only rows summarized: `93`; hidden/excluded XLSX rows
  remain non-candidates; route/fallback metrics remain diagnostic-only.
- Guardrails: `official_metric_input_rows=0`, official denominator registry
  unchanged, `tuning_run_started=false`, production mutation `false`,
  cross-track average `false`.
- Next action: user human audit decisions only. After that, apply decisions
  report-only and generate an official denominator candidate diff preview;
  require explicit user approval before any registry mutation.

## 2026-05-16 PDF/XLSX Question Quality + Local LLM Draft Packet Human Audit

Status: `OFFICIAL_METRIC_INPUT_READY_NOT_EXECUTED`;
human audit packet v2 `HUMAN_AUDIT_PACKET_V2_READY`, human audit completed
`true`.

- Evidence: `ai/eval/reports/rag-ingestion/local_llm_expected_answer_generation_probe_v1.json`,
  `question_quality_gate_report_v1.json`, `ai/eval/review/rag_pdf_gold_question_candidate_generation_v1.json`,
  `ai/eval/review/rag_pdf_manual_question_rewrite_candidates_v1.json`,
  `rag_xlsx_gold_question_candidate_generation_v1.json`,
  `rag_local_llm_expected_answer_verifier_v1.json`, and
  `rag_human_audit_packet_v2_question_quality_local_llm.json`.
- Local LLM: llama.cpp-compatible local endpoint `http://localhost:8081/v1`,
  model `gemma4-e2b-local`; XLSX outputs are diagnostic/model-assisted drafts
  only. PDF questions were manually authored from source-bound context v2.
- Counts: v1 action rows `19`; bad original PDF/XLSX question rows rejected
  `13`; PDF manually authored and verifier-clean candidates `4`; XLSX
  generated and verifier-clean candidates `19`; final v2 action rows `29`
  (`text_namu_v2_1=6`, `pdf_business_ocr_mm=4`,
  `xlsx_business_structured=19`); human labeled rows `29` with
  `INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE`.
- Board: `DIAGNOSTIC_PREFLIGHT_READY`; PDF/XLSX evidence readiness remains
  complete. Official metric setup status is
  `REGISTRY_BACKED_CONFIG_READY_NOT_EXECUTED`.
- Applied decision and metric setup artifacts:
  `ai/eval/review/rag_human_audit_v2_applied_decisions.json`,
  `ai/eval/reports/rag-ingestion/official_denominator_candidate_diff_preview_v1.json`,
  `ai/eval/reports/rag-ingestion/official_question_gold_v2_registry_application_report.json`,
  and `ai/eval/reports/rag-ingestion/official_metric_input_config_v1.json`.
- Materialized official question-gold v2 inputs:
  `ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv`
  (`6` rows), `ai/eval/eval_queries/gold_queries_xlsx_question_gold_v2.csv`
  (`19` rows), and `ai/eval/eval_queries/gold_queries_pdf_question_gold_v2.csv`
  (`4` rows).
- Official metric input rows: total `29`
  (`text_namu_v2_1=6`, `pdf_business_ocr_mm=4`,
  `xlsx_business_structured=19`). These rows are registry-backed metric inputs;
  the first-run report consumed them, but official scoring did not start because
  the scorer/backend is unavailable.
- Registry: `ai/eval/eval_queries/official_denominator_registry.json` now has
  v2 question-gold denominator entries for TEXT/XLSX/PDF. The existing XLSX
  retrieval default `track_a_xlsx_human_review_normalized_v0` remains unchanged.
- Guardrails: `promotion_evidence=false`, `official_metric_execution_started=false`,
  `tuning_run_started=false`, production vector writes `false`, cross-track
  averages `false`.
- Remaining blocker: wire or start the official answer/citation scorer/backend,
  then rerun the same first-run runner. Tuning remains closed.

## 2026-05-16 Official Answer/Citation Metric First Run

Status: `BLOCKED_OR_PARTIAL`; blocker `SCORER_BACKEND_UNAVAILABLE`.

- Evidence:
  `ai/eval/reports/rag-ingestion/official_answer_citation_metric_first_run_v1.json`
  / `.md`.
- Consumed source of truth:
  `ai/eval/reports/rag-ingestion/official_metric_input_config_v1.json`,
  `ai/eval/eval_queries/official_denominator_registry.json`, and
  `ai/eval/reports/rag-ingestion/official_metric_pre_execution_smoke_report_v1.json`.
- Rows consumed: total `29` (`pdf_business_ocr_mm=4`,
  `text_namu_v2_1=6`, `xlsx_business_structured=19`).
- Scoring attempts: `0`; `official_metric_execution_started=false` because no
  official answer/citation scorer/backend was available.
- Row-level result fields were emitted for all 29 rows with
  `answer_score=null`, `citation_support_score=null`, and failure category
  `SCORER_BACKEND_UNAVAILABLE`; no score was fabricated.
- Diagnostic warning preserved: `text_namu_v2_0017`
  `potential_support_coverage_gap`.
- Guardrails: `tuning_run_started=false`, `promotion_evidence=false`,
  threshold tuning `false`, gold/denominator/production mutation `false`,
  cross-track averages `false`, winner selection `false`.
- Next action: wire or start the official answer/citation scoring backend, then
  rerun the same first-run runner. Do not start tuning or create promotion
  evidence from this blocked report.

## 2026-05-15 PDF Gold/Evidence Lineage + v2 Canary

Status: `SUPERSEDED_BY_PDF_EVIDENCE_CONTEXT_V2_NATIVE_TABLE_RECOVERY`.

- Evidence: `ai/eval/reports/rag-ingestion/pdf_gold_evidence_lineage_audit_v1.json`
  / `.md` and `pdf_evidence_object_v2_canary_report.json` / `.md`.
- Lineage: current PDF rows `7`; all `7` had bad vector query surfaces,
  locator-only nearby context, answer-input echoing `matched_text`, and human
  audit v1 inheriting the bad query. Reviewed-v1 matching positives exist, but
  they prove location/retrieval review, not answer-gold question quality.
- Initial v2 canary before native/table recovery: rows `7`; local-LLM answer
  candidates `0`; native block text missing `7`; locator-only context `7`.
  Current context-v2 canary supersedes this with native block text resolved `7`
  and manually authored PDF candidates `4`.
- Guardrails: `official_metric_input_rows=0`, `promotion_evidence=false`,
  `tuning_run_started=false`, official denominator registry unchanged.
- Next: superseded by context v2 native/nearby block recovery, deterministic
  PDF table extraction, and the 2026-05-16 human-reviewed v2 packet above.

## 2026-05-15 Canonical Pack And Anti-Shortcut Audit

Status: `CANONICAL_ARTIFACT_AUDIT_PASS`;
`ANTI_SHORTCUT_GUARDRAIL_AUDIT_PASS`.

- This audit snapshot is superseded for current transition status by the
  PDF/XLSX question-quality/local-LLM v2 packet above.
- Board at the time: `DIAGNOSTIC_PREFLIGHT_READY`; dry-run plan:
  `REPORT_ONLY_DRY_RUN_PLAN_READY`; human audit packet v1:
  `HUMAN_AUDIT_PACKET_READY`.
- Official transition checklist:
  `OFFICIAL_TRANSITION_BLOCKED_PENDING_HUMAN_AUDIT`.
- Guardrails: official metric input rows remain `0`, tuning run started
  `false`, official metrics and denominators closed, denominator registry
  unchanged.
- Remaining blocker: user human audit decisions only.
- Current slim canonical pack keeps board/readiness/dry-run/checklist/human
  audit/progress doc as current reports, and keeps TEXT/XLSX/PDF proof packets
  as generated source proof.
- Cleanup: superseded intermediate review packets moved to external archive
  `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260515T0338-rag-slim-canonical-cleanup`;
  current report/review directories now include README files listing current,
  source-proof, and active legacy-input files.

## 2026-05-13 PDF Strict Retrieval/Evidence Diagnostic Slice

Status: `COMPLETED_DIAGNOSTIC_ONLY`; historical strict-slice report superseded
by the current canonical PDF readiness repair:

- `ai/eval/reports/rag-ingestion/pdf_evidence_readiness_repair_report.md`
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

## 2026-05-13 TEXT/Namu Local LLM Answer/Citation Diagnostic Slice

Status: `DIAGNOSTIC_LOCAL_LLM_REWRITE_V2_COMPLETE`; compact reports:

- `ai/eval/reports/rag-ingestion/rag_text_namu_answer_citation_local_llm_improvement_report.md`
  / `.json`
- `ai/eval/review/rag_text_namu_generated_answer_review_input_local_llm_v2.jsonl`
- `ai/eval/review/rag_text_namu_answer_citation_review_applied_diagnostic_v2.md`
  / `.json`

Run context:

- Local LLM endpoint: `llamacpp` / `gemma4-e2b-local` at
  `http://localhost:8081/v1`.
- GPU runtime confirmed: Docker container `aipipeline-llama-cpp-gemma4` uses
  the CUDA llama.cpp image with `--n-gpu-layers 99`, and container-local
  `nvidia-smi` shows `/llama-server` as a GPU compute process.
- DB access status: local Postgres read-only transaction guard passed, but
  candidate TEXT/Namu chunk ids did not match current `search_unit` rows, so
  `db_context_used=false` and `loaded_search_unit_count=0`.

Counts:

- Generated answer review rows: `66`.
- v1 clean pass / cleanup / rewrite-required: `29` / `5` / `32`.
- v2 clean pass / cleanup / unresolved diagnostic rows: `52` / `5` / `9`.
- v2 literal answer-rewrite-required rows: `9`.
- v2 citation fully supported generated-answer rows: `57`.
- Rows improved / regressed / unchanged: `23` / `0` / `43`.
- Rows blocked by verifier: `9`.
- Rows blocked by DB unavailable: `0`.
- Rows blocked by local LLM unavailable: `0`.
- Official metric input rows: `0`.

Diagnostic target status:

- Minimum diagnostic improvement (`unresolved <= 20`): `true`.
- Metric preview candidate (`clean >= 47` and `unresolved <= 13`): `true`.
- Metric pass candidate (`clean >= 53`, `unresolved <= 10`,
  `citation_supported >= 60`): `false`.
- Official metric: `false`; human-approved policy artifacts are still required
  before opening official answer/citation denominators.

Guardrails:

- All v2 rows remain `diagnostic_only=true`, `official_metric_input=false`,
  and `promotion_evidence=false`.
- Model-assisted v2 rows are not human-approved gold.
- Route/fallback labels remain diagnostic-only and are not mixed into
  answer/citation official metrics.
- No official denominator registry, production namespace/vector/index,
  candidate artifact, immutable baseline, or gold registry mutation occurred.

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
  under `ai/eval/`.
- Current SearchUnit indexing CLI is `python -m app.cli.search_unit_indexing`
  from `ai/`.
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

Current canonical navigation after cleanup:

- `README.md`
- `ai/eval/README.md`
- `ai/eval/eval_queries/README.md`
- `ai/eval/eval_queries/official_denominator_registry.json`
- `ai/scripts/README.md`
- `ai/eval/reports/rag-ingestion/three_track_orchestration_report.md`
- `docs/THIRD_PARTY_DATA_LICENSES.md`
- `docs/rag-ingestion-progress.md`

Detailed diagnostic reports and review packs are generated or externally
archived artifacts unless a later task explicitly promotes a compact file back
to tracked documentation.

External archive manifests:

- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_210945\external_archive_manifest.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_212609\external_archive_manifest.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260507_212609\external_archive_manifest.csv`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260511-eval-report-cleanup\archive_summary.json`
- `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260511-eval-report-cleanup\archive_manifest.csv`
- `..\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\2026-05-11-portfolio-cleanup\`

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
- Scope: documented the active role of each `ai/eval/` directory and
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
  `ai/eval/reports/rag-ingestion/xlsx_pdf_route_trace_diagnostic_20260507.json`,
  `ai/eval/reports/rag-ingestion/xlsx_pdf_route_trace_diagnostic_20260507.md`,
  `ai/eval/reports/rag-ingestion/xlsx_pdf_agentic_route_loop_diagnostic_20260507.json`,
  `ai/eval/reports/rag-ingestion/xlsx_pdf_agentic_route_loop_diagnostic_20260507.md`.
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
  `ai/eval/reports/rag-ingestion/pdf_review_pack_validation_20260507.json`,
  `ai/eval/reports/rag-ingestion/pdf_reviewed_retrieval_evidence_application_20260507.json`,
  `ai/eval/reports/rag-ingestion/pdf_reviewed_route_trace_diagnostic_20260507.json`,
  `ai/eval/reports/rag-ingestion/pdf_reviewed_agentic_route_loop_diagnostic_20260507.json`,
  `ai/eval/reports/rag-ingestion/pdf_xlsx_review_application_manifest_20260507.toml`.
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
  `ai/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_generation_report_20260507.json`,
  `ai/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_generation_report_20260507.md`,
  `ai/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_generation_manifest_v0.json`,
  `ai/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_validation_report_v0.json`.
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
- Consolidated report: `ai/eval/reports/rag-ingestion/answer_recovery_tuning_report.md`
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

- Imported canonical review-pack CSVs under `ai/eval/review/` for
  TEXT/Namu v2 (`100` rows), XLSX human review (`50` rows), and PDF file-lookup
  companion (`28` rows). The accessible XLSX external export matched the repo
  copy by sha256; `/mnt/data` was not mounted in this Windows workspace.
- Normalization report:
  `ai/eval/reports/rag-ingestion/rag_reviewed_gold_policy_normalization_report.md`
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
- Generated packet: `ai/eval/review/rag_gold_policy_resolution_packet_v1.md`
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
  `ai/eval/review/rag_gold_policy_resolution_packet_v1.json`; no
  official denominator membership was frozen.
- Generated draft: `ai/eval/review/rag_gold_policy_decision_draft_v1.md`
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
  `ai/eval/review/rag_gold_policy_decision_draft_v1.json`; no official
  denominator membership was frozen.
- Generated sheet:
  `ai/eval/review/rag_gold_policy_user_review_sheet_v1.md`.
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
  `ai/eval/review/rag_gold_policy_user_approved_resolutions_v1.md`
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
  `ai/eval/review/rag_gold_policy_applied_decisions_v1.md` / `.json`;
  updated sheet status in
  `ai/eval/review/rag_gold_policy_user_review_sheet_v1.md` to
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
- Evidence: `ai/eval/reports/rag-ingestion/three_track_orchestration_report.md`
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
- Evidence: `ai/eval/review/route_gold_label_review_pack_v1.md` /
  `.json`, `ai/eval/review/fallback_outcome_label_review_pack_v1.md` /
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
- Evidence: `ai/eval/review/route_gold_label_review_applied_v1.md` /
  `.json`, `ai/eval/review/fallback_outcome_label_review_applied_v1.md`
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

- Status: `HISTORICAL_PASS_BEFORE_ANSWER_CITATION_SURFACES`; current
  answer/citation policy packet supersedes this as the active XLSX status.
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

- Status: `COMPLETED_DIAGNOSTIC_ONLY_HISTORICAL`; current answer/citation
  policy packet supersedes this as the active XLSX pre-tuning status.
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

## 2026-05-13 - TEXT/Namu Answer-Citation Diagnostic Review Applied

- Status: `APPLIED_DIAGNOSTIC_ONLY`; evidence:
  `ai/eval/review/rag_text_namu_answer_citation_review_applied_diagnostic_v1.md`
  / `.json`.
- Counts: generated-answer rows `66`, draft rows `66`, applied rows `66`;
  `KEEP_DIAGNOSTIC_CANDIDATE=29`, `KEEP_WITH_CLEANUP=5`,
  `ANSWER_REWRITE_REQUIRED=32`.
- Diagnostic preview: `answer_pass_preview_count=29`,
  `cleanup_pass_preview_count=5`, `rewrite_required_count=32`,
  `citation_fully_supported_generated_answer_count=34`,
  `citation_contains_correct_answer_but_generated_answer_incomplete_count=32`.
- Guardrails held: `official_metric_input_rows=0`,
  `official_metric_status=FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY`, no
  official denominator/gold/candidate/baseline/production mutation.
- Verification: apply script returned `APPLIED_DIAGNOSTIC_ONLY`; focused
  no-cache pytest passed `40` tests; applied JSON parsed; protected paths had
  no diff.
- Next: human policy review is still required before any TEXT answer/citation
  denominator can open.

## 2026-05-13 - Pre-5/12 Review And Docs External Archive Cleanup

- Status: `COMPLETED_PRESERVE_ONLY`; external archive:
  `D:\_external_workspace_archive\async-ocr-rag-multimodal-pipeline\20260513T222411-pre-20260512-review-docs-cleanup`.
- Counts: moved files `153`; docs created before 2026-05-12 `77`; pre-5/12
  review `.md/.json/.csv` artifacts `76`; tracked files moved `29`; bytes
  moved `19014890`.
- Preserved exceptions: `docs/THIRD_PARTY_DATA_LICENSES.md` and
  `docs/rag-ingestion-progress.md`.
- Evidence: external `archive_manifest.csv`, `archive_manifest.pre_move.csv`,
  and `archive_summary.json` include original relative paths and SHA256 hashes.
- Verification: manifest rows `153`, hash mismatches `0`, remaining matching
  docs/review cleanup candidates `0`.

## 2026-05-14 - PDF Evidence Metadata And Layout Closure

- Status: `PDF_LAYOUT_GAP_CLOSED_ALL_STRICT_READY`; board
  `DIAGNOSTIC_PREFLIGHT_READY`; tuning plan `REPORT_ONLY_READY`.
- Evidence: `ai/eval/reports/rag-ingestion/pdf_evidence_metadata_enrichment_report.json`
  / `.md`, `pdf_layout_gap_closure_report.json` / `.md`, and refreshed
  `pdf_evidence_readiness_repair_report.json` / `.md`.
- Counts: SearchUnit id `0 -> 7`, parser/source metadata `0 -> 7`,
  nearby paragraphs `0 -> 7`, OCR/native trust `0 -> 7`, citation locator
  completeness `4 -> 7`, strict ready rows `0 -> 4 -> 7`.
- Layout closure: source-bound bbox resolved for `gq_auto_010`,
  `gq_auto_015`, and `gq_auto_030`; fallback rows `3 -> 0`.
- Guardrails: strict gate rerun performed as diagnostic readiness-gate only;
  canonical strict generator not run; `official_metric_input_rows=0`,
  `answer_generation_opened=false`, `tuning_run_started=false`.
- XLSX remains `DIAGNOSTIC_POLICY_PACKET_READY`; TEXT remains
  `FROZEN_DIAGNOSTIC_V2_1`; denominator registry unchanged.

## 2026-05-15 - PDF Evidence Context V2 Native/Table Recovery

- Status: `PDF_EVIDENCE_CONTEXT_V2_READY_FOR_MANUAL_QUERY_AUTHORING`;
  diagnostic-only canary `PDF_EVIDENCE_OBJECT_V2_CANARY_COMPLETE`.
- Evidence: `ai/eval/reports/rag-ingestion/pdf_evidence_context_v2_enrichment_report.json`
  / `.md`, refreshed `pdf_evidence_object_v2_canary_report.json` / `.md`.
- Counts: context rows `7`, native block text resolved `7`, nearby block text
  resolved `7`, deterministic table-ready rows `2`, source-mismatch repair rows
  `1`, chart/table-label blocked rows `1`, title-only blocked rows `1`,
  official metric input rows `0`.
- Parser change: PDF extraction now emits narrow deterministic table records
  for supported native-text tables; cell bbox remains fail-closed as row/table
  granularity, and OCR fragments do not become table/value evidence.
- Guardrails: model/gold/denominator/promotion/tuning remain closed;
  `tuning_run_started=false`; denominator registry unchanged.
- Next: superseded by the completed v2 human audit; apply the completed
  decisions report-only before any denominator diff preview.

## 2026-05-16 - Official Metric Pre-Execution Smoke

- Status: `OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS_WITH_DIAGNOSTIC_WARNINGS`;
  evidence: `ai/eval/reports/rag-ingestion/official_metric_pre_execution_smoke_report_v1.json` / `.md`.
- Counts: registry-backed official input rows `29`; PDF `4`, TEXT `6`, XLSX
  `19`; all three CSV SHA-256 values match registry/application/config.
- Diagnostic note: TEXT `text_namu_v2_0017` remains a
  `potential_support_coverage_gap`; gold CSV text was not modified.
- Guardrails: official metric execution still not started,
  tuning still not started, promotion evidence not created.

## Next Recommended Steps

1. Review the XLSX strict silver generation report and external manifest before
   any answer-generation or promotion policy change.
2. Review any newly opened XLSX answer/citation/debug/public surfaces with the
   focused normalized excluded-row / hidden-negative leakage probe before using
   them for answer-generation or promotion.
3. Wire or start the official answer/citation scorer/backend, then rerun the
   registry-backed v2 first-run runner; do not start tuning in the same step.
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
