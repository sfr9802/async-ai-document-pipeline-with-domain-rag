# Source-Native Actual RAG Roadmap

## Current Scope

Actual RAG evaluation is non-production diagnostic infrastructure. Phase 0 through Phase 2 stabilize the measurable source-native pipeline only. This document now records the legacy/source-native stabilization baseline; the active scalable SourceAtom/EvidenceBundle retrieval service boundary for the Weaviate lane is Weaviate hybrid/vector/BM25, not local source-native layered candidate generation.

- Kept: SourceAtom/EvidenceBundle as the evidence truth surface.
- Legacy baseline: source-native retrieval remains available for explicit diagnostic comparison, while Weaviate-backed retrieval is the active service-boundary lane when a Weaviate backend is selected.
- Kept: query-only candidate generation. Expected answers, expected evidence, qrels, answerability labels, relevance labels, row IDs, target IDs, and baseline top-k are not retrieval inputs.
- Kept: strict, provisional, inferred-answerable, and diagnostic metric tiers as separate report surfaces.
- Default-off: SearchUnit/SearchView is legacy debug/comparison only and is not the default actual RAG candidate surface.
- Diagnostic-only: extractive-v1 answer generation, answer/context consistency checks, citation/context consistency checks, source-native Hit@K/nDCG, MMR selection diagnostics, FAISS/local source-native comparison, and diagnostic vector fallback metrics.
- Route-selected store candidate: Weaviate A/B mode now compares full-index, TEXT-only, mixed-pool, and route-selected retrieval without replacing the default path. The `SourceAtomNonprodRouteSelectedV2` collection materializes route taxonomy, source-owned structural locator metadata, and metadata-only vectorization policy. The fresh A/B run is guardrail-clean, shows no TEXT degradation, keeps mixed-route weak evidence recall at Lane C level, removes source-family pollution, lowers same-document duplicate pressure, and recommends `promote_route_selected_nonprod_default` as the next non-production step.
- Active portfolio experiment checkpoint: `--answer-composer selected-evidence-deterministic-v1` now adds an opt-in deterministic selected-evidence composer after route-selected Weaviate retrieval and before evidence-gate validation. It uses query text plus selected SourceAtom/EvidenceBundle evidence only, preserves `extractive-v1` as the comparison baseline, narrows final citations to selected evidence, and keeps routine output at `report.json` only. The first six-row Checkpoint B report records citation retrieved-context-only leakage `42 -> 0` versus the extractive-v1 evidence-gate baseline while evidence-gate enforce still holds unsupported-answer rate after gate at `0.0`.
- Citation formatter checkpoint: `--selected-evidence-citation-format compact|evidence-id|source-locator|markdown-portfolio` now formats selected-evidence citations without changing evidence authority. The first Checkpoint C report uses `markdown-portfolio`, still emits only `report.json`, keeps retrieved-context-only citations diagnostic-only, and holds evidence-gate enforce at unsupported-answer rate after gate `0.0`.
- Optional local LLM composer checkpoint: `--answer-composer selected-evidence-local-llm-v1` reuses the existing localhost-only helper and persists only prompt/response hashes, bounded answer previews, and backend/status metadata. The first Checkpoint D report shows the helper was available (`generated=5`, deterministic fallback=`1`) and artifact-safe, but gate compatibility regressed versus the deterministic formatter (`allowed 3 -> 1`, `blocked 3 -> 5`) while unsupported-after-gate remained `0.0`. Treat this as portfolio experiment evidence for a bounded retry design, not as a promotion or readiness signal.
- Bounded retry checkpoint: `--selected-evidence-composer-retry-mode bounded-once` adds max-one local-composer retry after evidence-gate insufficiency or query-focus anchor feedback. Retry input is limited to query text, selected evidence, missing query-focus anchors when present, and the previous bounded answer preview; retry prompt/response payloads are not written. The first Checkpoint E report attempted four retries, accepted none, kept `report.json` as the only artifact, preserved the Weaviate route-selected boundary and rollback key, and held unsupported-after-gate at `0.0`.
- Portfolio comparison checkpoint: repeated `--portfolio-comparison-report LABEL=PATH` embeds report-only answer/citation/gate diffs in `portfolio_experiment_comparison`. The first Checkpoint F comparison has 9 lanes, records selected-evidence answer and citation diffs `6/6` versus extractive diagnostic, moves retrieved-context-only citation diagnostics `40 -> 0` for selected-evidence lanes, and keeps deterministic selected-evidence enforce at unsupported-after-gate `0.0` with selected-evidence citation precision `1.0`.
- Portfolio sidecar checkpoint: `--write-portfolio-experiment-summary` writes `portfolio_experiment_summary.md` only when explicit comparison reports are supplied. The first Checkpoint G sidecar includes answer diff, citation diff, gate before/after, unsupported blocked count, abstain count, selected-evidence citation precision, retrieved-context-only citation count, residual failure taxonomy, and no raw prompt/response payload fields.
- Query-focus repair checkpoint: deterministic selected-evidence composition now scores full selected contexts when query anchors are split across lines, and the evidence gate matches compact Korean query anchors against spaced Korean title text for longer Hangul anchors. The first Checkpoint H report keeps Weaviate route-selected retrieval and `report.json` only, improves deterministic enforce allowed/blocked `3/3 -> 5/1`, keeps retrieved-context-only citations at `0`, and keeps unsupported-after-gate at `0.0`.
- Query-variant retrieval checkpoint: route-selected Weaviate retrieval now has bounded query-only alias variants (`weaviate_query_reformulation_v1`) for mixed Korean/Latin title/entity terms. The first Checkpoint I report keeps the same Weaviate route-selected boundary and full-index rollback, emits only `report.json`, and proves variants were used without gold/expected/qrels/labels/IDs. Outcomes remain `5/1` allowed/blocked because the residual `text_namu_v2_0014` still lacks any retrieved text/title containing `Adversary`, `애드버서리`, or `어드버서리`; this is diagnostic residual retrieval/corpus coverage work, not a citation or gate-loosening target.
- Same-document residual checkpoint: route-selected Weaviate retrieval now has a bounded source-owned same-document residual probe (`bounded_query_variant_same_doc_weaviate_v1`) that uses only doc IDs already returned by Weaviate plus query-only variants. The first Checkpoint J report keeps the same boundary and rollback, emits only `report.json`, and shows the probe ran for the X-Men row but still did not retrieve any `Adversary`/`애드버서리`/`어드버서리` text. The next safe lane is explicit corpus-coverage audit before any broader retrieval expansion.
- Corpus-coverage audit checkpoint: `text_namu_v2_0014` is report-backed as `corpus_present` with tokenization/alias failure and collision pressure, not corpus absence or route-filter failure. This keeps the next target on general query/evidence formulation under the unchanged gate.
- Query-formulation v3 / portfolio-freeze-v1 checkpoint: the latest pointer now references `actual_rag_eval_query_formulation_v3_agentic_guard_nonprod_20260614_v4`. Static English alias gain from v2 is retracted from the active normal-query path; v3 keeps bounded query-text-only Korean numeral/punctuation/content-anchor variants, emits only `report.json`, keeps `--agentic-planner-mode off`, and preserves allowed/blocked `5/1`, unsupported-after-gate `0.0`, retrieved-context-only citations `0`, and citation_supported `8`. This is agent-ready boundary evidence, not broader-loop readiness.
- XLSX/PDF SourceAtom v2 reindex checkpoint: report-only post-reindex runs improved citation support (`13 -> 22`) and citation precision/recall (`0.230769/0.375 -> 0.363636/0.571429`) without improving allowed answers or strict E2E. XLSX/PDF cell/axis locator structure is claimable as evidence representation, while XLSX-wide response-smoke success is not claimable.

## Phase 0

Phase 0 locks the contract and roadmap:

- Source-native actual RAG remains diagnostic-only.
- SearchUnit/SearchView is fenced behind explicit legacy/debug comparison.
- Routine output mode writes one `report.json`.
- Human review packets are generated only behind an explicit flag.
- Reviewed mapping ingest is generated only from an explicit separate human-reviewed CSV input.
- No gold, qrels, expected answer, expected evidence, answerability label, relevance label, human decision field, denominator, source registry, current alias, or production namespace is mutated.

## Phase 1

Phase 1 adds review-only full-corpus expected-evidence resolution:

- The resolver searches SourceAtom/EvidenceBundle text across the source-native corpus after retrieval.
- Retrieved-only behavior remains available as a diagnostic scope.
- Expected evidence is allowed only in explicit evidence-resolution mode or after retrieval, never as retrieval candidate-generation input.
- Resolver candidates are machine recommendations for human review only. They do not create gold, qrels, answerability labels, relevance labels, or official denominators.
- Optional CSV review packets leave all human-owned decision fields blank.
- Reviewed CSV ingest reads only explicit human decision fields from a separate file, creates a run-local derived overlay plus patch proposal, and reports denominator changes without overwriting the source dataset.

## Phase 2

Phase 2 stabilizes source-native vector reporting:

- For legacy/source-native diagnostic comparison only, prefer a BAAI/bge-m3 source-native FAISS `IndexFlatIP` path when available.
- Record model name, model revision when available, device, dimension, corpus count, corpus fingerprint or text hashes, build/load latency, FAISS capability, and fallback reason.
- If BGE-M3 or FAISS is unavailable, report an explicit diagnostic fallback.
- `codex-diagnostic-hashing-vector-v1` must never be labeled as BAAI/bge-m3 and cannot support semantic-quality claims.
- CPU FAISS is acceptable when GPU FAISS is unavailable, as long as the report states the fallback reason.

## Not Claimable

Do not claim product success, live readiness, official metric promotion, autonomous agent completion, broader agent loop readiness/opening, XLSX-wide response-smoke success, retrieval-quality improvement, or final-answer quality when strict denominators are unavailable or the generator remains diagnostic-only.

## Later Phases

Later phases are out of scope for the Phase 0-2 stabilization goal:

- non-production default wiring for the route-selected Weaviate retrieval lane
- route-selected retrieval v2 ranking and query formulation for the remaining deterministic blocked row
- evidence validator
- citation validator
- actual answer generator
- broad agentic planner
- gold expansion
- production readiness gate
