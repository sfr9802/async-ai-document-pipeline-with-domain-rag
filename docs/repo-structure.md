# Repository Structure

This repository is a split Spring Boot plus Python worker document pipeline.
PostgreSQL owns durable job, artifact, catalog, and indexing state. Redis is
the dispatch signal. The Python worker executes capabilities through the
claim-before-execute `TaskRunner` path.

## Entrypoints

| Path | Status | Purpose |
|---|---|---|
| `core-api/src/main/java/com/aipipeline/coreapi/CoreApiApplication.java` | active | Spring Boot API entrypoint. Owns job state, catalog state, Flyway migrations, internal claim/callback endpoints, and Redis dispatch. |
| `ai-worker/app/main.py` | active primary worker | Foreground worker process. Run from `ai-worker/` with `python -m app.main`; consumes Redis and calls `TaskRunner.handle`. |
| `ai-worker/app/api.py` | active but narrow FastAPI surface | Defines `create_app()` and `POST /internal/tasks/ocr-extract`. The route wraps the same `TaskRunner` path and currently supports only `OCR_EXTRACT`. |
| `ai-worker/ai_worker/search_unit_indexing.py` | active operational CLI | SearchUnit indexing loop. Not a FastAPI route and not the Redis job consumer. |
| `docker-compose.yml` | local infra | Starts PostgreSQL and Redis by default; optional MinIO and Ollama profiles. It does not start `core-api` or `ai-worker`. |

## FastAPI Boundary

The FastAPI boundary is deliberately small:

- `FastAPI()` appears in `ai-worker/app/api.py`.
- No in-repo `APIRouter`, `include_router`, `Depends`, or `lifespan` usage was found.
- The only route is `POST /internal/tasks/ocr-extract`.
- `ai-worker/app/main.py` exports `app = create_app()`, but the primary runtime is still `run()`, which starts the Redis consumer.
- No repository-owned `uvicorn` command or container command was found.

Because this endpoint has no route-level auth dependency, do not expose it as a
public service without a separate security review.

## Main Directories

| Directory | Status | Purpose |
|---|---|---|
| `core-api/` | active | Spring service, DB migrations, catalog/indexing services, internal worker endpoints, Redis dispatch, tests. |
| `ai-worker/app/` | active | Worker runtime, capabilities, queue consumer, clients, storage resolver, FastAPI endpoint. |
| `ai-worker/app/capabilities/` | active | Capability implementations for RAG, OCR, PDF, XLSX, multimodal, agent, and RAG orchestrator work. |
| `ai-worker/ai_worker/` | active | Operational packages such as SearchUnit indexing and golden-retrieval fixture/eval helpers. |
| `ai-worker/eval/` | active but isolated | Eval harnesses and historical eval material. Production runtime should not import from here. |
| `ai-worker/scripts/` | mixed active/eval | Eval, tuning, dataset, fixture, and report-generation helpers. |
| `scripts/` | active operational helpers | Root-level smoke, ingestion, readiness, promotion-gate, repair, baseline, and candidate indexing scripts. |
| `docs/` | active docs | Architecture, local run, RAG ingestion progress/plans, and structure docs. |
| `eval/` | active eval input | Root gold query CSVs used by RAG ingestion tests and scripts. |
| `samples/` | active inputs | Smoke/sample manifests used by scripts and tests. |
| `datasets/` | active/reference data | Dataset snapshots and benchmark material, including KoViDoRe and XLSX canary inputs. |
| `reports/` | generated working evidence | Default output location for root RAG scripts. Old generated outputs may be moved to `archive/results/`. |
| `rag-data/` | runtime/index data | Default RAG index directory from worker configuration. |
| `rag-data-canary/` | generated workflow artifact | Candidate/canary vector artifact. Workflow-blocking, not production-imported. |
| `local-storage/` | runtime data | Local artifact blob storage default for core API and worker. |
| `archive/` | historical | Preserved generated outputs and future retired material. See `archive/README.md` and `archive/MANIFEST.md`. |

## Active Root Scripts

| Script | Purpose |
|---|---|
| `scripts/demo.py` | Compatibility wrapper for `scripts/operational/demo.py`. |
| `scripts/e2e_smoke.py` | Compatibility wrapper for `scripts/operational/e2e_smoke.py`. |
| `scripts/smoke_all.py` | Compatibility wrapper for `scripts/operational/smoke_all.py`. |
| `scripts/operational/demo.py` | One-command platform demo. |
| `scripts/operational/e2e_smoke.py` | End-to-end async pipeline smoke test. |
| `scripts/operational/smoke_all.py` | Delegates to the worker smoke runner. |
| `scripts/rag_ingestion_smoke.py` | XLSX RAG ingestion v2 smoke. |
| `scripts/rag_ingestion_sample_batch.py` | Manifest-driven XLSX ingestion sample batch runner. |
| `scripts/rag_pdf_ingestion_smoke.py` | PDF RAG ingestion metadata smoke. |
| `scripts/rag_pdf_ingestion_sample_batch.py` | Manifest-driven PDF ingestion sample batch runner. |
| `scripts/rag_pdf_ocr_fallback_smoke.py` | PDF OCR fallback smoke. |
| `scripts/rag_retrieval_eval.py` | CLI wrapper for the active RAG ingestion retrieval eval harness. |
| `scripts/rag_build_promotion_gate_metrics.py` | Builds promotion-gate metrics from generated smoke/eval reports. |
| `scripts/rag_path_separation_readiness.py` | Read-only TEXT/PDF/XLSX path-separation readiness report. |
| `scripts/rag_candidate_scope_path_readiness.py` | Candidate-scope PDF/XLSX path readiness report. |
| `scripts/pdf_xlsx_candidate_embedding_consistency.py` | Read-only PDF/XLSX candidate embedding consistency report. |
| `scripts/rag_full72_docv_scope_classification.py` | Full72 gold document-version scope classification and planning. |
| `scripts/rag_full72_vector_quality_breakdown.py` | Full72 vector diagnostic breakdown. |
| `scripts/rag_scoped_candidate_indexing.py` | Scoped candidate SearchUnit indexing runner. |
| `scripts/rag_scoped_search_unit_text_repair.py` | Scoped live-DB repair for missing SearchUnit text fields. |
| `scripts/rag_candidate_namespace_cleanup.py` | Scoped candidate namespace cleanup/retire helper. |
| `scripts/rag_gold_query_rebind.py` | Rebinds RAG ingestion gold queries from the live catalog DB. |
| `scripts/rag_prepare_immutable_baseline.py` | Validates/materializes immutable RAG-ingestion baseline evidence. |
| `scripts/rag_bootstrap_initial_vector_baseline.py` | Bootstrap helper for the first immutable vector baseline descriptor. |

## Archive Policy

Use `archive/` only for material that is no longer active. When a file is
uncertain, keep it in place or mark it as `needs_review`; do not move it merely
because it looks old.

During the 2026-05-04 cleanup, only generated root outputs were moved. The
following were intentionally kept because they are active, test-blocking,
workflow-blocking, or runtime defaults:

- `eval/gold_queries_v0.csv`
- `samples/*.json`
- `datasets/**`
- `rag-data-canary/`
- `local-storage/`
- `rag-data/`
- root `scripts/*.py`
- all `core-api/**`, `ai-worker/app/**`, `ai-worker/ai_worker/**`, and `ai-worker/tests/**`

The second cleanup pass moved only clean tracked operational scripts into
`scripts/operational/` and left root compatibility wrappers in place. Modified
or untracked RAG scripts were not relocated to avoid bundling unrelated active
work into the structure commit.
