# Scripts

Root `scripts/*.py` entrypoints are kept for compatibility, but canonical
implementations may live in categorized subdirectories.

## Categories

| Path | Role |
|---|---|
| `operational/` | Repeatable developer/operator commands such as demo and smoke wrappers. |
| `maintenance/` | Reserved for repeatable maintenance commands that are safe to run with explicit inputs. |
| `needs_review/` | Reserved for scripts that need a data-contract or migration review before relocation. |

## Compatibility Wrappers

These root files remain as stable command paths and delegate to
`scripts/operational/`:

| Compatibility Path | Canonical Implementation |
|---|---|
| `scripts/demo.py` | `scripts/operational/demo.py` |
| `scripts/e2e_smoke.py` | `scripts/operational/e2e_smoke.py` |
| `scripts/smoke_all.py` | `scripts/operational/smoke_all.py` |

Keep wrappers thin. New logic should go in the categorized implementation file.

## Active RAG Helpers

The remaining root-level `rag_*` and candidate/index scripts are intentionally
not moved yet. Several are loaded directly by tests or use fixed default paths
such as `eval/gold_queries_v0.csv`, `samples/*.json`, `reports/*.json`, and
`rag-data-canary/`.

Before moving one of these scripts, first check:

- direct test loads in `ai-worker/tests/test_rag_ingestion_scaffolding.py`
- default input/output paths inside the script
- whether it can mutate DB, index, namespace, gold query, or baseline state
- whether docs still show the root compatibility path

If any of those checks are uncertain, keep the script in place or move it only
after adding a compatibility wrapper and updating tests.
