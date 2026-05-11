# Archive

This directory preserves historical material that should remain available for
provenance or reproduction, but should not be treated as active runtime,
evaluation, tuning, or promotion evidence.

The archive is intentionally conservative. Active service code, active tests,
current migrations, current fixtures, and workflow-blocking inputs stay outside
this directory until a separate review proves they are safe to move. Do not add
new large generated payloads here; workspace cleanup uses an external archive
under `../_external_workspace_archive/<repo-name>/<timestamp>/` with a checksum
manifest instead.

## Layout

| Path | Contents |
|---|---|
| `MANIFEST.md` | Per-file movement record for this archive. |
| `results/` | Generated logs, reports, metrics, CSVs, and miscellaneous outputs. |
| `experiments/` | Historical or dry-run experiment artifacts. |
| `experiments/frontend-design-system/` | Historical frontend design-system handoff exports, not the active app. |
| `experiments/frontend-legacy/` | Legacy static frontend bundle retained for provenance. |
| `experiments/eval-legacy/` | Legacy eval notes retained for migration provenance. |
| `scripts/` | Reserved for future legacy, one-off, deprecated, or needs-review scripts. |

Large generated payloads that are no longer active evidence should be moved to
the external archive, not into this tree. Existing entries stay here only as
small provenance records unless a future review proves they should also be
externalized.

## Active Locations

These locations remain part of the active repository surface:

| Path | Role |
|---|---|
| `core-api/` | Spring Boot API, catalog/indexing services, DB migrations, Redis dispatch, worker callbacks. |
| `ai-worker/app/` | Python worker runtime, FastAPI task endpoint, queue consumer, capability registry, TaskRunner path. |
| `ai-worker/scripts/` | Worker-owned smoke, ingestion, readiness, promotion-gate, baseline, and report helpers. |
| `ai-worker/eval/` | Active eval harnesses, gold/review inputs, current reports, datasets, corpora, and local vector artifacts. Legacy-only notes that are not imported by code may live under `archive/experiments/eval-legacy/`. |
| `ai-worker/eval/eval_queries/official_denominator_registry.json` | Current denominator source of truth. |
| `ai-worker/eval/reports/rag-ingestion/` | Active RAG ingestion working-evidence summaries. |
| `ai-worker/eval/indexes/rag-data-canary/`, `rag-data-xlsx-candidate-v1/`, `rag-data-pdf-candidate-v1/` | Current baseline/candidate vector artifacts guarded by descriptors and reports. |
| `frontend/app/`, `frontend/index.html` | Active test frontend surface. Historical design handoff exports are archived. |
| `local-storage/` | Runtime default path shared by core-api and worker; large stale blobs require DB/job-state review before externalization. |

## Rules

- Do not delete archived files as part of cleanup work.
- Add a row to `MANIFEST.md` for every file newly moved into this internal
  archive, but prefer the external archive for generated payloads.
- Treat archived reports as historical evidence only. Regenerate from active
  scripts before using them for current promotion or rollout decisions.
- Mark uncertain material as `needs_review` instead of moving active code or
  active fixtures.
- Do not archive files that are imported by production code or loaded by tests
  unless the import/test paths are updated in the same reviewed change.
