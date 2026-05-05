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
| `ai-worker/app/cli/search_unit_indexing.py` | active operational CLI | SearchUnit indexing loop. Not a FastAPI route and not the Redis job consumer. |
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
| `ai-worker/app/cli/` | active | Operational CLI entrypoints such as SearchUnit indexing. |
| `ai-worker/eval/` | active but isolated | Eval harnesses, golden-retrieval helpers, eval datasets, reports, and historical eval material. Production runtime should not import from here. |
| `ai-worker/scripts/` | mixed active/eval | Eval, tuning, dataset, fixture, and report-generation helpers. |
| `ai-worker/fixtures/` | active worker fixtures | Small committed fixtures and ingestion manifests used by worker scripts and tests. |
| `ai-worker/eval/eval_queries/` | active eval input | RAG ingestion gold/query CSVs and routing matrices. |
| `ai-worker/eval/corpora/` | active eval input | Text corpora used by Track B and related retrieval diagnostics. |
| `ai-worker/eval/datasets/` | active/reference data | Dataset snapshots and benchmark material, including KoViDoRe, sample, and XLSX canary inputs. |
| `ai-worker/eval/reports/rag-ingestion/` | generated working evidence | Default RAG ingestion diagnostic/readiness report location. |
| `ai-worker/eval/indexes/` | generated vector/index data | Worker-local FAISS/vector artifacts such as `rag-data`, `rag-data-canary`, and candidate indexes. |
| `docs/` | active docs | Architecture, local run, RAG ingestion progress/plans, and structure docs. |
| `local-storage/` | runtime data | Local artifact blob storage default for core API and worker. |
| `archive/` | historical | Preserved generated outputs and future retired material. See `archive/README.md` and `archive/MANIFEST.md`. |

Root-level `scripts/`, `eval/`, `evals/`, `samples`, `datasets/`, `reports/`,
and `rag-data*` directories are no longer active paths. The old
`ai-worker/evals/` data directory and `ai-worker/ai_worker/` Python package
have also been retired. If an old command recreates one of those paths, treat it
as a compatibility bug and move the input/output back under the canonical
`ai-worker/eval/`, `ai-worker/scripts/`, or `ai-worker/app/cli/` location.

## Worker Scripts

| Script | Purpose |
|---|---|
| `ai-worker/scripts/operational/demo.py` | One-command platform demo. |
| `ai-worker/scripts/operational/e2e_smoke.py` | End-to-end async pipeline smoke test. |
| `ai-worker/scripts/operational/smoke_all.py` | Delegates to the worker smoke runner. |
| `ai-worker/scripts/rag_ingestion_smoke.py` | XLSX RAG ingestion v2 smoke. |
| `ai-worker/scripts/rag_ingestion_sample_batch.py` | Manifest-driven XLSX ingestion sample batch runner. |
| `ai-worker/scripts/rag_pdf_ingestion_smoke.py` | PDF RAG ingestion metadata smoke. |
| `ai-worker/scripts/rag_pdf_ingestion_sample_batch.py` | Manifest-driven PDF ingestion sample batch runner. |
| `ai-worker/scripts/rag_pdf_ocr_fallback_smoke.py` | PDF OCR fallback smoke. |
| `ai-worker/scripts/rag_retrieval_eval.py` | CLI wrapper for the active RAG ingestion retrieval eval harness. |
| `ai-worker/scripts/rag_build_promotion_gate_metrics.py` | Builds promotion-gate metrics from generated smoke/eval reports. |
| `ai-worker/scripts/rag_path_separation_readiness.py` | Read-only TEXT/PDF/XLSX path-separation readiness report. |
| `ai-worker/scripts/rag_candidate_scope_path_readiness.py` | Candidate-scope PDF/XLSX path readiness report. |
| `ai-worker/scripts/pdf_xlsx_candidate_embedding_consistency.py` | Read-only PDF/XLSX candidate embedding consistency report. |
| `ai-worker/scripts/rag_scoped_candidate_indexing.py` | Scoped candidate SearchUnit indexing runner. |
| `ai-worker/scripts/rag_scoped_search_unit_text_repair.py` | Scoped live-DB repair for missing SearchUnit text fields. |
| `ai-worker/scripts/rag_candidate_namespace_cleanup.py` | Scoped candidate namespace cleanup/retire helper. |
| `ai-worker/scripts/rag_gold_query_rebind.py` | Rebinds RAG ingestion gold queries from the live catalog DB. |
| `ai-worker/scripts/rag_prepare_immutable_baseline.py` | Validates/materializes immutable RAG-ingestion baseline evidence. |
| `ai-worker/scripts/rag_candidate_index_lineage_report.py` | Diagnostic-only lineage report for immutable baseline and candidate vector artifacts. |
| `ai-worker/scripts/rag_xlsx_*` | XLSX query/evidence/candidate diagnostic helpers. |
| `ai-worker/scripts/rag_text_*` | TEXT Track B diagnostic helpers. |
| `ai-worker/scripts/rag_pdf_*` and `ai-worker/scripts/pdf_*` | PDF diagnostic/readiness helpers. |

## Archive Policy

Use `archive/` only for material that is no longer active. When a file is
uncertain, keep it in place or mark it as `needs_review`; do not move it merely
because it looks old.

During the 2026-05-05 cleanup, worker-owned scripts, eval inputs, dataset
snapshots, manifests, generated reports, and FAISS/vector artifacts were moved
under `ai-worker/`. The remaining active root directories are service or
workspace boundaries: `core-api/`, `ai-worker/`, `frontend/`, `docs/`,
`local-storage/`, and `archive/`.

Keep future worker artifacts inside the worker tree:

- scripts and command helpers: `ai-worker/scripts/`
- manifests and small fixtures: `ai-worker/fixtures/`
- gold/query inputs: `ai-worker/eval/eval_queries/`
- corpora and dataset snapshots: `ai-worker/eval/corpora/` or `ai-worker/eval/datasets/`
- RAG ingestion reports: `ai-worker/eval/reports/rag-ingestion/`
- FAISS/vector artifacts: `ai-worker/eval/indexes/`
