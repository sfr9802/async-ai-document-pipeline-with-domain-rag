# Worker Scripts

`ai/scripts/` is the canonical home for worker-owned smoke, ingestion,
readiness, eval, dataset, and report-generation commands.

Run commands from `ai/` unless a script documents another working
directory:

```bash
cd ai
python -m scripts.rag_retrieval_eval --help
python scripts/operational/e2e_smoke.py
```

## Categories

| Path | Role |
|---|---|
| `operational/` | Repeatable developer/operator commands such as demo and smoke wrappers. |
| `maintenance/` | Reserved for repeatable maintenance commands that are safe to run with explicit inputs. |
| `dataset/` | Dataset and fixture generation helpers. |
| `needs_review/` | Reserved for scripts that need a data-contract or migration review before relocation. |

## Canonical Worker Paths

Default script inputs and outputs should stay inside `ai/`:

| Kind | Path |
|---|---|
| Gold/query CSVs | `eval/eval_queries/` |
| Text corpora | `eval/corpora/` |
| Dataset snapshots | `eval/datasets/` |
| Ingestion manifests | `fixtures/manifests/` |
| RAG ingestion reports | `eval/reports/rag-ingestion/` |
| FAISS/vector artifacts | `eval/indexes/` |

Root-level `scripts/`, `eval/`, `samples/`, `datasets/`, `reports/`, and
`rag-data*` directories are legacy/compatibility locations. Do not add new
defaults that write there.

## Lineage Policy

Active eval scripts must not default to archived gold-query CSVs. Official
diagnostic denominators are fixed in:

```text
eval/eval_queries/official_denominator_registry.json
```

Legacy full72/XLSX v1-v3 builder and comparison scripts were moved to:

```text
../archive/results/2026-05-05-eval-query-lineage-cleanup/scripts/
```

Keep those scripts provenance-only unless a follow-up explicitly restores or
ports one to the current denominator registry.
