# Archive

This directory preserves historical material that should remain available for
provenance or reproduction, but should not be treated as active runtime,
evaluation, tuning, or promotion evidence.

The archive is intentionally conservative. Active service code, active tests,
current migrations, current fixtures, and workflow-blocking inputs stay outside
this directory until a separate review proves they are safe to move.

## Layout

| Path | Contents |
|---|---|
| `MANIFEST.md` | Per-file movement record for this archive. |
| `results/` | Generated logs, reports, metrics, CSVs, and miscellaneous outputs. |
| `experiments/` | Historical or dry-run experiment artifacts. |
| `scripts/` | Reserved for future legacy, one-off, deprecated, or needs-review scripts. |

## Active Locations

These locations remain part of the active repository surface:

| Path | Role |
|---|---|
| `core-api/` | Spring Boot API, catalog/indexing services, DB migrations, Redis dispatch, worker callbacks. |
| `ai-worker/app/` | Python worker runtime, FastAPI task endpoint, queue consumer, capability registry, TaskRunner path. |
| `ai-worker/ai_worker/` | Operational Python packages, including SearchUnit indexing and golden-retrieval helpers. |
| `ai-worker/eval/` | Active and legacy eval harnesses with their own internal organization. |
| `scripts/` | Operational smoke, ingestion, readiness, promotion-gate, and baseline helpers. |
| `eval/` | Root RAG ingestion gold query inputs. |
| `samples/` | Smoke/sample manifests used by active scripts and tests. |
| `datasets/` | Source datasets and benchmark fixtures. |
| `rag-data/`, `local-storage/` | Runtime default paths from configuration. |
| `rag-data-canary/` | Current generated canary/vector artifact used by RAG verification workflows. |
| `scripts/operational/` | Canonical location for repeatable demo and smoke commands. |

## Rules

- Do not delete archived files as part of cleanup work.
- Add a row to `MANIFEST.md` for every archived file.
- Treat archived reports as historical evidence only. Regenerate from active
  scripts before using them for current promotion or rollout decisions.
- Mark uncertain material as `needs_review` instead of moving active code or
  active fixtures.
- Do not archive files that are imported by production code or loaded by tests
  unless the import/test paths are updated in the same reviewed change.
