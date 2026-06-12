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

Do not claim product success, live readiness, official metric promotion, retrieval-quality improvement, or final-answer quality when strict denominators are unavailable or the generator remains diagnostic-only.

## Later Phases

Later phases are out of scope for the Phase 0-2 stabilization goal:

- non-production default wiring for the route-selected Weaviate retrieval lane
- selected-evidence answer composer and citation formatter after retrieval routing is promoted
- retrieval v2 ranking and query formulation
- evidence validator
- citation validator
- actual answer generator
- broad agentic planner
- gold expansion
- production readiness gate
