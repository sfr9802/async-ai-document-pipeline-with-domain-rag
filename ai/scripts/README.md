# Worker Scripts

`ai/scripts/` is the canonical home for worker-owned smoke, ingestion,
readiness, eval, dataset, and report-generation commands.

Most worker scripts can run from `ai/` unless a script documents another
working directory:

```bash
cd ai
python -m scripts.rag_retrieval_eval --help
python scripts/operational/e2e_smoke.py
```

## Actual RAG Eval CLI

New experiment work should feel like using a backend, not adding another fat
script. Put reusable behavior under `ai/eval/` backend modules, then dispatch it
through the thin runner entrypoint in module form
`python -m ai.eval.experiment_runner.main`.

```bash
python -X utf8 -m ai.eval.experiment_runner.main \
  --experiment actual-rag \
  --run-id <run_id> \
  --profile local \
  --dry-run
```

For a real actual-RAG execution, pass the dataset and choose the output mode:

```bash
RAG_EXPERIMENT_PROFILE=weaviate \
python -X utf8 -m ai.eval.experiment_runner.main \
  --experiment actual-rag \
  --run-id <run_id> \
  --dataset <eval-items.jsonl> \
  --index current \
  --top-k 10 \
  --output-mode report-json
```

The experiment runner rejects `--output-mode run-sqlite` until runstore wiring is
promoted into this facade. It records whitelisted `RAG_EXPERIMENT_*` env values,
argv, git commit, report root, run id, profile, and output mode before dispatch.
Path-like argv/env values for dataset, context, output, and report-root inputs
are stored as repo-relative paths or redacted outside the repo. Secret env vars
are not copied into metadata.
The eval dataset schema/loader, answer judging helpers, agentic XLSX taxonomy
and verifier helpers, and XLSX locator SQLite store now live in focused backend
modules: `ai/eval/actual_rag_dataset.py`,
`ai/eval/actual_rag_judging.py`, `ai/eval/actual_rag_agentic_xlsx.py`, and
`ai/eval/xlsx_locator_run_store.py`. Do not reimplement those contracts in
experiment scripts.

`rag_actual_eval.py` remains the legacy-compatible direct CLI for the pragmatic
actual-RAG evaluation loop:
The `python -m ai.scripts.rag_actual_eval` examples below are repo-root
commands. If you are already in `ai/`, use `python -m scripts.rag_actual_eval`
and `eval/...` paths instead.

```bash
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset <eval-items.jsonl> \
  --index current \
  --output-dir reports/rag_eval/<run_id> \
  --top-k 10 \
  --retrieval-surface auto \
  --retrieval-backend auto \
  --output-mode single \
  --judge-mode heuristic \
  --resolve-expected-evidence \
  --evidence-resolution-scope full-corpus-review-only \
  --append-registry \
  --write-latest \
  --compare-to previous
```

It loads incomplete eval items with warnings, selects a retrieval surface,
runs retrieval/context assembly, generates answers through the current
extractive adapter, captures citations when present, and writes one primary
routine artifact:

- `report.json`

Use `--output-mode legacy` only for compatibility/debugging when the older
`rag_eval_items.jsonl`, `rag_eval_summary.json`, Markdown, and diagnostic
sidecar set is explicitly needed. `--output-mode both` is transition-only.

Use `--retrieval-surface auto` for the current diagnostic lane. Auto prefers
SourceAtom/EvidenceBundle-backed source-native units and runs bounded
deterministic layered retrieval over source-native units only. SearchUnit/
SearchView is no longer a routine actual-RAG candidate surface; it remains
available only as explicit legacy/debug comparison with
`--legacy-surface-comparison`. `report.json` contains the selected surface,
fallback reason, source-native layered retrieval diagnostics, source presence
probes, GPU/vector diagnostics, source-native Hit@K/nDCG diagnostics, MMR
selection diagnostics, and BM25/vector/hybrid backend comparison in the same
file. MMR is recorded as the `mmr_selected` selection strategy, not as MRR or
reciprocal-rank. Expected answers, expected evidence, qrels, row IDs, query
IDs, target IDs, and baseline top-k are excluded from candidate generation;
expected evidence is used only after retrieval or in explicit full-corpus
diagnostic evidence-resolution mode.

Use `--write-human-review-packet` when a human review packet is explicitly
needed. Single mode then writes exactly one extra file:

- `human_review_packet.csv`

Expected-evidence resolution is deterministic and non-mutating. The CLI default
scope is `full-corpus`; current evidence-gate runs pass
`--evidence-resolution-scope full-corpus-review-only` explicitly. That mode
searches the full SourceAtom/EvidenceBundle corpus without mixing retrieved
contexts into the resolver candidate pool. `retrieved-only` keeps the older
retrieved-context diagnostic behavior, while `index-candidate-lookup` and
`both` are explicit legacy diagnostics. Expected answers, expected evidence,
aliases, qrels, row IDs, query IDs, target IDs, or baseline top-k must not be
candidate-generation input. Resolution is recorded as diagnostic lookup only
and must not alter the RAG retrieval results, answer generation inputs, gold
files, qrels, or official denominators. Medium-confidence mappings count as
resolved only with `--count-medium-evidence-resolution`; low-confidence
candidates are written for review inside `report.json` but do not count as
resolved.

`--write-human-review-packet` turns resolver candidates into a source-owned
human review CSV. Packet rows include current source metadata when available,
redacted local-path diagnostics, deterministic machine recommendations, review
priorities, and blank human-owned decision fields. The machine recommendation
fields are not gold mappings, qrels, answerability labels, or official metrics.
This packet is only for diagnostic review and must not be used to tune retriever
ranking or claim product/live readiness.

Use `--reviewed-evidence-mapping-csv <path>` only after a separate human-owned
review file exists. The runner reads explicit human decision fields, rejects
blank human decision rows, rejects machine recommendations used as human
decisions, creates a run-local derived overlay plus
`reviewed_evidence_mapping_patch.json`, and records `reviewed_mapping_*` and
`denominator_changes` in `report.json`. It does not overwrite the eval dataset,
gold, qrels, labels, expected fields, source registry, or production namespaces.

Use `--quality-gate-baseline <report-or-run-dir>` or
`--quality-gate-baseline auto` only for explicit legacy-free parity gates. The
fresh real-RAG run still uses source-native query-text-only retrieval first; the
frozen SearchUnit/SearchView report is loaded afterward for comparison and is
marked `legacy_baseline_replayed_not_executed=true`. The command writes
`legacy_real_rag_quality_gate_report.json` and
`legacy_real_rag_quality_gate_items.jsonl` beside `report.json` with item-level
answer parity, evidence package status, citation support, diagnostic critic
fields, failure labels, not-comparable reasons, and guardrail status.

Use `--evidence-gate-mode off|diagnostic|enforce` to run the bounded
evidence/citation gate over production-available fields only. Diagnostic mode
computes `answer_gate_decision`, selected-evidence citation validation, anchor
coverage, and would-abstain counts without changing generated answers. Enforce
mode abstains with `제공된 근거만으로는 답할 수 없습니다.` when selected
SourceAtom/EvidenceBundle evidence or citation support is insufficient. The gate
does not read expected answers, expected evidence, qrels, labels, legacy output,
row IDs, or target IDs for enforcement, and it never starts a retrieval loop.

Use `--answer-composer selected-evidence-deterministic-v1` only for the
non-production selected-evidence composer experiment. The default is
`extractive-v1`. The deterministic composer runs after retrieval and before the
evidence gate, reads only query text plus selected SourceAtom/EvidenceBundle
evidence, and narrows final citations to selected evidence. It must be paired
with normal guardrail checks; retrieved-context-only citations remain
diagnostic-only.

Use `--selected-evidence-citation-format compact|evidence-id|source-locator|markdown-portfolio`
to format selected-evidence citations for that composer. The formatter is
display-only: final structured citations are still selected-evidence-only and
the evidence gate remains authoritative. Markdown portfolio formatting writes no
extra sidecar by itself.

The deterministic composer includes the Checkpoint H query-focus repair behavior:
it can use a full selected SourceAtom/EvidenceBundle passage when query anchors
are split across lines, and the gate can match compact Korean query anchors
against spaced Korean title text. The repair keeps the same CLI flags and
report-only contract; no new gold/qrels/label, denominator, source-registry, or
current alias mutation is required.

For Weaviate `route_selected` runs, Checkpoint I also records bounded query-only
alias variants under `weaviate_query_reformulation`. These variants are derived
only from the query text, capped at 8, and merged before the existing
route-selected duplicate/safety filters. Full-index rollback remains available
through its separate config and does not use the route-selected variant path.

Checkpoint J records bounded same-document residual probes under
`weaviate_post_processing.same_doc_residual_*`. This path uses only SourceAtom
`doc_id` values already returned by Weaviate plus the query variants; it does
not scan the local corpus, use FAISS, call SearchUnit/SearchView, or read
gold/expected/qrels/labels/IDs.

`--append-registry` appends `reports/rag_eval/runs.jsonl` and a compact
`actual_rag_eval_run` event to `reports/rag_eval/rag-ingestion/status.jsonl`.
`--write-latest` updates `reports/rag_eval/latest.json`,
dataset-specific latest pointers such as `latest_text_gold.json` or
`latest_fixture.json`, and the generated `reports/rag_eval/README.md` index.
`--compare-to previous`, `--compare-to latest`, or `--compare-to <summary-or-run-dir>`
adds non-production comparison rows to `report.json`. Use fresh run IDs for
canonical evidence; an explicit `--output-dir` is treated as the caller-owned
destination.

The report separates strict headline metrics, provisional RAG metrics,
inferred-answerable metrics, diagnostic consistency metrics, and scalar
diagnostics. Strict answer, evidence, citation, and E2E denominators require
human-owned answerability labels. Provisional E2E requires the provisional answer judge to pass and
weak/strict evidence at the configured top-k; text-only weak evidence matching
requires non-generic anchors and all numeric/date anchors from the gold signal.
The separate `e2e_rag_success_resolved_evidence_provisional` variant also
requires the answer judge to pass and resolved evidence at the configured top-k.
`answer_extracted_from_retrieved_context_rate` and
`citation_points_to_retrieved_context_rate` are diagnostic consistency checks,
not answer correctness or citation correctness. `--context-jsonl` can feed
deterministic precomputed RAG outputs for smoke tests. `--judge-mode local-llm`
is an opt-in localhost-only semantic judge path that reuses the existing
llama.cpp/Ollama/openai-compatible helper; tests must continue to use
deterministic fixtures and must not require model calls. Use
`--provisional-require-citations` only when the provisional E2E variant should
also require strict citation pass.

Retrieval backends are selected with `--retrieval-backend bm25|vector|hybrid|auto`.
`auto` prefers hybrid when the local vector path is available. The current
source-native vector path prefers the additive non-production BGE-M3 FAISS
`IndexFlatIP` when present and keeps the older
`codex-diagnostic-hashing-vector-v1` FAISS index as diagnostic fallback only.
Build or refresh the BGE-M3 index with `--build-source-native-bge-m3-index`;
embedding uses CUDA when available, while persisted search uses local CPU FAISS.
This local FAISS path is not an external production VectorDB. External VectorDB
use remains optional and must be explicitly non-production.

For the Weaviate SourceAtom service-boundary lane, start the local nonprod
service from repo root:

```bash
docker compose -f docker-compose.weaviate.yml up -d
```

Then index SourceAtom/EvidenceBundle source-native units into Weaviate with
local BAAI/bge-m3 vectors:

```bash
RAG_VECTOR_DB=weaviate \
WEAVIATE_URL=http://localhost:8080 \
WEAVIATE_GRPC_PORT=50051 \
WEAVIATE_COLLECTION_SOURCE_ATOM=SourceAtomNonprod \
WEAVIATE_NAMESPACE=actual_rag_eval_nonprod \
WEAVIATE_USE_LOCAL_DOCKER=true \
EMBEDDING_MODEL=BAAI/bge-m3 \
EMBEDDING_DEVICE=auto \
python -X utf8 -m ai.scripts.rag_weaviate_source_atom_index
```

The index command writes
`reports/rag_eval/weaviate_source_atom_index_manifest_nonprod/index_manifest.json`
and refuses to silently index zero records. The active non-production indexing
path streams SourceAtom/EvidenceBundle units through local sentence-transformers
`BAAI/bge-m3`, checkpoints every successful upsert batch, and can resume without
embedding or upserting already completed SourceAtom IDs:

```bash
python -X utf8 -m ai.scripts.rag_weaviate_source_atom_index \
  --batch-size 64 \
  --manifest-path reports/rag_eval/weaviate_source_atom_index_manifest_nonprod_streaming_full/index_manifest.json \
  --checkpoint-path reports/rag_eval/weaviate_source_atom_index_manifest_nonprod_streaming_full/index_checkpoint.json
```

Use `--reset-checkpoint` only for an intentional fresh non-production rebuild.
The CLI rejects the old `source-native-faiss-bge-m3` vector-transfer shortcut;
FAISS remains diagnostic/offline comparison only and is not an active Weaviate
indexing or retrieval dependency. Successful streaming manifests must record
`index_vector_source=streaming-bge-m3`, `embedding_source=sentence_transformers_bge_m3_streaming`,
`faiss_used_for_index_seed=false`, and `faiss_used_for_active_retrieval=false`.

For the route-selected store candidate, build the explicit v2 non-production
collection so route taxonomy fields, safe structural locator metadata, and the
metadata-only vectorization policy are materialized in Weaviate:

```bash
python -X utf8 -m ai.scripts.rag_weaviate_source_atom_index \
  --schema-version weaviate_source_atom_v2 \
  --weaviate-collection-name SourceAtomNonprodRouteSelectedV2 \
  --batch-size 64 \
  --manifest-path reports/rag_eval/weaviate_source_atom_index_manifest_nonprod_route_selected_v2/index_manifest.json \
  --checkpoint-path reports/rag_eval/weaviate_source_atom_index_manifest_nonprod_route_selected_v2/index_checkpoint.json
```

The v2 policy vectorizes paragraphs, heading-context blocks, table rows,
table summaries, and captions. Cells, page blocks, metadata-only records, empty
fragments, repeated headers/footers, and local path/source trace fields are not
vectorized by default. Source-owned workbook/sheet/cell-range/page/bbox locator
metadata is stored as filterable context, not blindly treated as semantic
evidence text. Existing v1 indexes are historical full-index baselines; do not
rewrite them to make v2 claims.

The active Weaviate eval backend is the explicit route-selected non-production
default config path:

```bash
RAG_VECTOR_DB=weaviate \
WEAVIATE_URL=http://localhost:8080 \
WEAVIATE_GRPC_PORT=50051 \
WEAVIATE_NAMESPACE=actual_rag_eval_nonprod \
ACTUAL_RAG_EVAL_WEAVIATE_CONFIG_PATH=ai/eval/configs/weaviate_route_selected_nonprod_default.json \
EMBEDDING_MODEL=BAAI/bge-m3 \
EMBEDDING_DEVICE=auto \
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv \
  --retrieval-surface source-native \
  --retrieval-backend weaviate-hybrid \
  --output-mode single \
  --evidence-resolution-scope full-corpus-review-only \
  --run-id actual_rag_eval_weaviate_route_selected_nonprod_default_report_only_20260612_v2 \
  --append-registry \
  --write-latest
```

This routine command writes `report.json` only. The report must show
active_retrieval_backend=`weaviate_hybrid`,
active_retrieval_service_boundary=`weaviate`,
collection=`SourceAtomNonprodRouteSelectedV2`,
schema_version_source_atom=`weaviate_source_atom_v2`,
route_planner_version=`weaviate_route_planner_v1`, route filters sent to
Weaviate, fallback_used=false, fail_closed_on_unavailable=true, and
rollback_key=`weaviate_full_index_nonprod_rollback`. In this lane, metadata
filters are sent to Weaviate, candidates are hydrated from Weaviate result
payloads, and local source-native layered retrieval, diagnostic hash vectors,
FAISS, local corpus scans, and SearchUnit/SearchView candidate surfaces are
forbidden. If Weaviate is unavailable or a query fails, the run fails or is
invalid with an explicit fallback reason; it must not complete by falling back
to the local Python retrieval path.

For the selected-evidence citation-formatter portfolio checkpoint, keep the same
route-selected Weaviate config and add the explicit composer, formatter, and evidence gate:

```bash
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv \
  --retrieval-surface source-native \
  --retrieval-backend weaviate-hybrid \
  --output-mode single \
  --evidence-resolution-scope full-corpus-review-only \
  --evidence-gate-mode enforce \
  --answer-composer selected-evidence-deterministic-v1 \
  --selected-evidence-citation-format markdown-portfolio \
  --run-id actual_rag_eval_selected_evidence_citation_formatter_checkpoint_c_nonprod_20260612 \
  --append-registry \
  --write-latest
```

This checkpoint command also writes only `report.json`; portfolio markdown
sidecars remain closed unless `--write-portfolio-experiment-summary` is used
with explicit comparison reports.

For the query-focus repair follow-on checkpoint, rerun the deterministic
selected-evidence composer with the same route-selected Weaviate boundary:

```bash
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv \
  --retrieval-surface source-native \
  --retrieval-backend weaviate-hybrid \
  --output-mode single \
  --evidence-resolution-scope full-corpus-review-only \
  --evidence-gate-mode enforce \
  --answer-composer selected-evidence-deterministic-v1 \
  --selected-evidence-citation-format markdown-portfolio \
  --run-id actual_rag_eval_selected_evidence_query_focus_repair_checkpoint_h_nonprod_20260612 \
  --append-registry \
  --write-latest
```

The first Checkpoint H report improved deterministic enforce allowed/blocked
from `3/3` to `5/1`, kept retrieved-context-only citations at `0`, and kept
unsupported-after-gate at `0.0`.

For the optional local LLM selected-evidence composer checkpoint, keep the same
route-selected Weaviate config and select the localhost-only composer explicitly:

```bash
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv \
  --retrieval-surface source-native \
  --retrieval-backend weaviate-hybrid \
  --output-mode single \
  --evidence-resolution-scope full-corpus-review-only \
  --evidence-gate-mode enforce \
  --answer-composer selected-evidence-local-llm-v1 \
  --selected-evidence-citation-format markdown-portfolio \
  --run-id actual_rag_eval_selected_evidence_local_llm_checkpoint_d_nonprod_20260612 \
  --append-registry \
  --write-latest
```

This path reuses the existing local helper, rejects non-local endpoints, stores
only hashes/bounded previews/backend metadata for prompt/response surfaces, and
falls back deterministically when the helper is unavailable or unsupported. The
first Checkpoint D report proved artifact hygiene but did not beat the
deterministic composer under the evidence gate: allowed rows changed `3 -> 1`
and blocked rows changed `3 -> 5` versus Checkpoint C, while
unsupported-after-gate stayed `0.0`.

For the bounded retry checkpoint, keep the local selected-evidence composer and
enable a single evidence-gate-triggered retry explicitly:

```bash
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv \
  --retrieval-surface source-native \
  --retrieval-backend weaviate-hybrid \
  --output-mode single \
  --evidence-resolution-scope full-corpus-review-only \
  --evidence-gate-mode enforce \
  --answer-composer selected-evidence-local-llm-v1 \
  --selected-evidence-citation-format markdown-portfolio \
  --selected-evidence-composer-retry-mode bounded-once \
  --run-id actual_rag_eval_selected_evidence_retry_checkpoint_e_nonprod_20260612 \
  --append-registry \
  --write-latest
```

Retry input is limited to query text, selected evidence, missing query-focus
anchors when present, and the previous bounded answer preview. Retry output is
accepted only if the evidence gate allows it, and reports store hashes, bounded
previews, status counts, and backend metadata rather than raw prompt/response
payloads. The first Checkpoint E run attempted four retries, accepted none, and
kept unsupported-after-gate at `0.0`, so it is fail-closed experiment evidence
rather than an answer-quality improvement.

For the report-only portfolio comparison checkpoint, first generate the selected
matrix lanes, then run a final deterministic markdown portfolio report with
explicit comparison inputs:

```bash
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv \
  --retrieval-surface source-native \
  --retrieval-backend weaviate-hybrid \
  --output-mode single \
  --evidence-resolution-scope full-corpus-review-only \
  --evidence-gate-mode enforce \
  --answer-composer selected-evidence-deterministic-v1 \
  --selected-evidence-citation-format markdown-portfolio \
  --portfolio-comparison-report extractive_diagnostic=reports/rag_eval/<extractive_diagnostic_run>/report.json \
  --portfolio-comparison-report extractive_enforce=reports/rag_eval/<extractive_enforce_run>/report.json \
  --portfolio-comparison-report deterministic_diagnostic=reports/rag_eval/<deterministic_diagnostic_run>/report.json \
  --portfolio-comparison-report local_llm_enforce=reports/rag_eval/<local_llm_run>/report.json \
  --run-id actual_rag_eval_selected_evidence_comparison_checkpoint_f_report_nonprod_20260612 \
  --append-registry \
  --write-latest
```

This embeds `portfolio_experiment_comparison` in `report.json` only. Compared
reports are post-run evidence, not generation inputs. The Checkpoint F report
must keep `portfolio_experiment_sidecar_written=false`; the Markdown portfolio
sidecar remains closed until a future explicit sidecar flag.

To emit the portfolio sidecar explicitly, add
`--write-portfolio-experiment-summary` to the same comparison command. The
sidecar path is `reports/rag_eval/<run_id>/portfolio_experiment_summary.md`;
the flag requires at least one `--portfolio-comparison-report` and renders from
bounded comparison data only, without raw prompt/response payloads.

Use the preserved full-index rollback config only when explicitly rolling back
or comparing the baseline:

```bash
RAG_VECTOR_DB=weaviate \
WEAVIATE_URL=http://localhost:8080 \
WEAVIATE_GRPC_PORT=50051 \
WEAVIATE_NAMESPACE=actual_rag_eval_nonprod \
ACTUAL_RAG_EVAL_WEAVIATE_CONFIG_PATH=ai/eval/configs/weaviate_full_index_nonprod_rollback.json \
EMBEDDING_MODEL=BAAI/bge-m3 \
EMBEDDING_DEVICE=auto \
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv \
  --retrieval-surface source-native \
  --retrieval-backend weaviate-hybrid \
  --output-mode single \
  --evidence-resolution-scope full-corpus-review-only \
  --run-id actual_rag_eval_weaviate_full_index_nonprod_rollback_<date>
```

For route-selected non-production A/B comparison, use the route-selected default
config and add `--weaviate-route-ab-mode text,mixed,routed` explicitly:

```bash
RAG_VECTOR_DB=weaviate \
WEAVIATE_URL=http://localhost:8080 \
WEAVIATE_GRPC_PORT=50051 \
WEAVIATE_NAMESPACE=actual_rag_eval_nonprod \
ACTUAL_RAG_EVAL_WEAVIATE_CONFIG_PATH=ai/eval/configs/weaviate_route_selected_nonprod_default.json \
EMBEDDING_MODEL=BAAI/bge-m3 \
EMBEDDING_DEVICE=auto \
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv \
  --retrieval-surface source-native \
  --retrieval-backend weaviate-hybrid \
  --weaviate-route-ab-mode text,mixed,routed \
  --output-mode single \
  --evidence-resolution-scope full-corpus-review-only \
  --run-id actual_rag_eval_weaviate_route_selected_nonprod_default_ab_20260612_v2 \
  --append-registry \
  --write-latest
```

This writes the normal `report.json` plus
`route_selected_hybrid_evidence_store_ab_report.json` and
`route_selected_hybrid_evidence_store_ab_items.jsonl`. The sidecar includes the
six-row TEXT regression lanes plus mixed-route diagnostic rows from the existing
29-row v5_5 packet. Routine single-output runs without
`--weaviate-route-ab-mode` still write only `report.json` unless another
explicit sidecar mode such as the quality gate is requested.

## Legacy Experiment Source Cleanup

Versioned v3/v4 worker scripts, one-off Phase 7 CLIs, and the old
official-answer/citation experiment monolith were removed from the tracked
source tree. Historical machine reports can remain in ignored report
namespaces, but new work must use the experiment runner plus focused backend
modules instead of adding or reviving versioned scripts.

## Categories

| Path | Role |
|---|---|
| `operational/` | Repeatable developer/operator commands such as demo and smoke wrappers. |
| `maintenance/` | Reserved for repeatable maintenance commands that are safe to run with explicit inputs. |
| `dataset/` | Dataset and fixture generation helpers. |
| `needs_review/` | Reserved for scripts that need a data-contract or migration review before relocation. |

`maintenance/` and `needs_review/` are classification buckets, not proof that a
relocation already happened. As of the 2026-06-25 cleanup checkpoint, only
`ai/scripts/maintenance/README.md` is tracked in these buckets and no tracked
script has been moved into `needs_review/`.

## Report And Artifact Namespaces

RAG reports now use explicit namespaces instead of ad-hoc script defaults. The
constants live in `ai/eval/report_paths.py`; new scripts should import that
module rather than spelling these roots by hand.

| Namespace | Path | Git policy | Role |
|---|---|---|---|
| Public portfolio reports | `reports/` allowlist | Track only `portfolio_agentops_report.md` and `agentops_sample_trace.json` | Small sanitized public artifacts |
| Actual RAG reports | `reports/rag_eval/` | Ignored/generated | `report.json` runs, latest pointers, run registry, Weaviate manifests |
| Legacy/current RAG ingestion reports | `reports/rag_eval/rag-ingestion/` | Ignored/generated | v3-v7 diagnostic ladder reports, `status.jsonl`, short-key/current evidence |
| Human-facing handoff notes | `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, `docs/rag-ingestion-triage.md` | Ignored/local-only | Worker-authored append-only status, measurements, and triage notes; not execution source of truth |

Do not move ignored machine artifacts into docs. For portfolio/freezing work,
summarize evidence through the code-owned registry/runner and keep machine
payloads local/generated unless a run contract explicitly names a tracked
artifact. Local `docs/rag-ingestion-*.md` files remain the worker-authored
rolling handoff surface, but new scripts and experiments must not require them
to exist or update them automatically.

## Dependency Boundaries

Use the smallest install surface that matches the command being run:

| Scope | Install surface | Applies to |
|---|---|---|
| Worker/runtime | `pip install -r ai/requirements.txt` | FastAPI worker, RAG/PDF/XLSX capability code, Weaviate and local retrieval adapters |
| Tests | `pip install -r ai/requirements.txt -r ai/requirements-dev.txt` or `pip install -e "ai[dev,experiments]"` | pytest plus experiment contract checks |
| Experiment tooling | `pip install -e "ai[experiments]"` from repo root, or `pip install -e ".[experiments]"` from `ai/` | Optuna/plot/report helpers such as `tune.py`, `summarize_study.py`, and round-refinement diagnostics |
| Optional OCR fallback | `pip install "paddleocr>=3.3.3,<3.4" "paddlepaddle>=3.2,<3.3"` | Live PaddleOCR fallback smoke only; native PDF/XLSX tests do not require it |

Do not add experiment-only dependencies to the default worker runtime unless an
active serving path imports them directly. Conversely, a script that needs an
experiment-only package should fail with an explicit dependency message or live
under the experiment install surface, not silently become a production
requirement.

## Canonical Worker Paths

Default script inputs should stay inside `ai/`; generated report outputs should
use the explicit report namespaces:

| Kind | Path |
|---|---|
| Gold/query CSVs | `eval/eval_queries/` |
| Text corpora | `eval/corpora/` |
| Dataset snapshots | `eval/datasets/` |
| Ingestion manifests | `fixtures/manifests/` |
| Legacy/current RAG ingestion reports | `reports/rag_eval/rag-ingestion/` |
| FAISS/vector artifacts | `eval/indexes/` |

Root-level `scripts/`, `eval/`, `samples/`, `datasets/`, and `rag-data*`
directories are legacy/compatibility locations. Root `reports/rag_eval/` is the
active actual-RAG machine report namespace, but it remains ignored/generated;
root `reports/` itself is tracked only through the small public allowlist above.
Do not add new defaults that write unclassified report payloads outside these
namespaces.

## Lineage Policy

Active eval scripts must not default to archived gold-query CSVs. Official
diagnostic denominators are fixed in:

```text
eval/eval_queries/official_denominator_registry.json
```

Legacy full72/XLSX v1-v3 builder and comparison scripts were moved to:

```text
redacted external workspace archive path
```

Keep those scripts provenance-only unless a follow-up explicitly restores or
ports one to the current denominator registry.

## Legacy Diagnostic Source Policy

The cleanup policy changed from preservation-first to runner-first. Versioned
v3/v4 worker scripts, Phase 7 execution CLIs, and the old official-answer /
citation experiment monolith are no longer tracked source. Historical reports
may remain in ignored report namespaces or an external archive, but new work
must use `python -m ai.eval.experiment_runner.main` plus focused backend modules.
`ai/eval/actual_rag_eval.py` is now a legacy-compatible facade, while the
actual backend is split across focused modules such as
`ai/eval/actual_rag_core_base.py`, `ai/eval/actual_rag_core_xlsx.py`,
`ai/eval/actual_rag_core_quality.py`, `ai/eval/actual_rag_runner.py`, and
`ai/eval/actual_rag_cli.py`. Those modules remain explicit cleanup targets for
future responsibility-based extraction, not examples for adding new one-off
experiment code.

Additional legacy wrappers removed in this cleanup include the XLSX/PDF route
trace direct scripts, local-LLM gold-question candidate generator scripts,
strict silver generation scripts, and the Phase 7 silver seed selector. When
one of those lanes needs to return, add a focused backend mode behind
`experiment_runner` instead of restoring the deleted script.

Keep reusable logic in importable modules under `ai/eval/` or application
capability modules. Add runner configuration, environment variables, or command
arguments for new experiments instead of adding another versioned one-off
script. When a legacy report is needed for comparison, read it as explicit
input evidence; do not restore the old source entrypoint.

Worker-authored rolling notes may stay in ignored local `docs/` files, but
new experiment-runner-backed commands must not require those files to exist and
must not update them automatically. Older diagnostic modules that still mention
local docs are historical compatibility surfaces, not templates for new work.
