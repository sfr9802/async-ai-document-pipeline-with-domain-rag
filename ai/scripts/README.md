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

`rag_actual_eval.py` runs the pragmatic actual-RAG evaluation loop:
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

<!-- v4_diagnostic_runtime_locator_and_finetune_readiness_inventory:start -->
## v4 RAG Diagnostic Runtime/Locator/Fine-Tuning Readiness Inventory

| Script | Role |
|---|---|
| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; `current` resolves to `v6_9_answer_quality_gate_packet_nonprod`. The v6 chain remains diagnostic-only, v5_5 keeps the read-only 29-row user-approved official input source, v5_6/v5_6_2/v5_6_3 remain fail-closed official-metric backend probes, and promotion/product-success/training/fine-tuning/live-readiness stay closed. |
| `rag_eval.py nec_2026_local_election_xlsx` | Direct 2026 NEC local-election XLSX diagnostic route; verifies the external source collection and writes preview-only source manifest, workbook artifact, and synthetic search-unit/source-atom/search-view artifacts while leaving `current`, official/gold/qrels/denominator/training/promotion/live gates closed. |
| `rag_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod.py` | Persists the v3_22 XLSX display metadata contract into SourceAtom-owned runtime-adjacent fields. |
| `rag_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod.py` | Packages family-separated XLSX table/range/cell locator diagnostics from seen-reference v3 surfaces. |
| `rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py` | Keeps PDF file identity confidence separate from answer-ready evidence-window diagnostics. |
| `rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py` | Materializes real blind/OOD holdout and leakage-audit infrastructure while fail-closing on unavailable source-disjoint holdout. |
| `rag_v4_5_finetune_readiness_packet_nonprod.py` | Builds the fine-tuning-readiness-only packet after v4_4 gates; no dataset export, training job, checkpoint, official metric, promotion, or product-success evidence is emitted. |
| `rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py` | Validates optional external real holdout candidate manifest input before any v4_6 FT dry run; the manifest is read as input only, raw external paths are redacted, and no candidate sidecar, training dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |
| `rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py` | Validates optional external holdout candidate manifests against either a raw prior identity ledger input or the v4_5_3 hash-only prior summary report so PDF document and XLSX workbook collisions are excluded before any v4_6 FT dry run; no sidecar, training dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |
| `rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py` | Builds the hash-only prior source-identity baseline used by v4_5_2/v4_6; raw source identity values and raw local paths are not embedded, and no prior-ledger sidecar, candidate manifest, training dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |
| `rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py` | Checks whether the non-production FT-A route/policy dry-run lane may open; it remains preflight-only while v4_5/v4_5_1/v4_5_2/v4_5_3 and user-owned policy gates are closed and emits no dataset, job, checkpoint, raw prompt, raw LLM response, official metric, promotion, or product-success evidence. |
| `rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py` | Hash-locks the v4_5_1/v4_5_2/v4_5_3/v4_6 holdout-candidate manifest identity contract and probes PDF/XLSX identity priority, conflict fail-closed behavior, XLSX source_identity-only rejection, and v4_6 stale-contract rejection; no manifest, dataset, job, checkpoint, prompt, raw LLM response, official metric, promotion, or product-success evidence is emitted. |
| `rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py` | Defines and validates the non-writing FT-A route/policy fixture contract for a later dry run; it rejects gold/oracle/prompt/raw-response fields and emits no dataset, job, checkpoint, raw prompt, raw LLM response, official metric, promotion, or product-success evidence. |
| `rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py` | Freezes a schema-only prompt-policy baseline contract for a later FT-A route/policy dry run; no raw prompt text, prompt manifest, raw LLM response, dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |
| `rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod.py` | Validates the schema for a future FT-A dry-run input manifest without exporting that manifest; prompt/gold/output fields are rejected and no prompt manifest, raw LLM response, dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. The reusable validator contract also lives in `ai/app/capabilities/rag/ft_dry_run_manifest_validation.py` for the default-disabled FastAPI diagnostic route. |
| `rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py` | Defines the closed FT-A dry-run execution plan gate without exporting the plan or manifest and without creating prompts, raw LLM responses, datasets, jobs, checkpoints, official metrics, promotion, or product-success evidence. |
| `rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py` | Compacts real-holdout deficits and FT-A dry-run blockers into one closed diagnostic ledger without exporting candidate manifests, dry-run plans, prompts, raw LLM responses, datasets, jobs, checkpoints, official metrics, promotion, or product-success evidence. |
| `rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py` | Compares the default-disabled FastAPI holdout-candidate validator against v4_5_1/v4_5_2 script gates with in-memory hash-only probes; no manifest, sidecar, dataset, job, checkpoint, dry-run, prompt, raw LLM response, official metric, promotion, or product-success evidence is emitted. |
| `rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod.py` | Rechecks v4_5_1/v4_5_2/v4_5_3/v4_6_6/v4_6_7 report-hash freshness and projects FastAPI readiness/holdout-acquisition requirements without acquiring candidates, exporting manifests, opening dry runs, or emitting official/promotion/product/live readiness evidence. |
| `rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod.py` | Checks strict holdout candidate duplicate hygiene across the default-disabled FastAPI validator and v4_5_1 intake gate; invalid-first duplicate IDs fail closed without writing manifests, sidecars, dry-run inputs, datasets, jobs, checkpoints, official metrics, promotion, or product-success evidence. |
| `rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod.py` | Replays the external holdout candidate manifest gate after v4_6_9. The default run remains input-waiting with no manifest; optional `--candidate-manifest` is input-only, path-redacted/hash-recorded, emits no raw candidate rows or sidecars, and keeps candidate export, dry-run inputs, datasets, jobs, checkpoints, v4_7, official metrics, promotion, product-success evidence, and live readiness closed. |
| `rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py` | Hash-locks the FastAPI FT-A dry-run input validation route against the v4_6_4 validator. It exercises default-disabled, production-disabled, enabled, validation-error, redaction, and operational-field rejection paths without exporting dry-run inputs, prompt manifests, raw LLM responses, datasets, jobs, checkpoints, official metric rows, promotion evidence, product-success evidence, or live-readiness claims. |
| `rag_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod.py` | Checks the default-disabled FastAPI holdout-candidate validation route against a transient v4_6_10 external manifest replay using hash-only probes. It verifies route count/source-identity parity, validation-error redaction, leak rejection, temp-manifest deletion, and no candidate manifest, validation/source-audit sidecar, dry-run input, dataset, job, checkpoint, official metric, promotion, product-success, or live-readiness opening. |
| `rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py` | Registers or validates optional external PDF/XLSX holdout candidate manifests as pre-official input only. It reuses v4_5_1 intake, v4_5_2 source-identity audit, and v4_6_10 no-write replay, records only aggregate counts plus a compact requirements packet, and keeps official metrics, FT-A execution, fine-tuning, promotion, product-success evidence, and live readiness closed. |
| `rag_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod.py` | Creates the human-review-only Korean review packet for the registered v4_7 pre-official PDF/XLSX candidates, updates README/status snapshot surfaces, and keeps official metrics, FT-A execution, fine-tuning, promotion, product-success evidence, and live readiness closed. |
| `rag_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod.py` | Hydrates the v4_7 Korean human-review packet with local-LLM source-grounded Korean query candidates, bounded evidence previews, and locator previews while keeping official metrics, FT-A execution, fine-tuning, promotion, product-success evidence, training data, and live readiness closed. |
| `rag_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod.py` | Applies the user-reviewed v4_7_2 Korean query candidate CSV as a pass/exclusion decision ledger, interpreting `미검수` as pass per user clarification when `제외사유` is blank, while keeping official metrics, gold/qrels, labels, FT-A execution, fine-tuning, training data, promotion evidence, and live readiness closed. |
| `rag_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod.py` | Replays only the v4_7_3 user-passed PDF survivor candidates through retrieval/evidence/answer-quality proxy diagnostics, using v4_7_2 bounded EvidenceBundle previews and optional local LLM generation while keeping official metrics, gold/qrels, labels, FT-A execution, fine-tuning, training data, promotion evidence, and live readiness closed. |

v4 scripts remain diagnostic/non-production and write a primary ignored
`report.json`; some runs also write contract-required ignored JSON/JSONL
sidecars listed in their status/report artifact maps. Actual fine-tuning
remains closed until real disjoint splits and user-owned gold/qrels/denominator
policy exist.
<!-- v4_diagnostic_runtime_locator_and_finetune_readiness_inventory:end -->

## Categories

| Path | Role |
|---|---|
| `operational/` | Repeatable developer/operator commands such as demo and smoke wrappers. |
| `maintenance/` | Reserved for repeatable maintenance commands that are safe to run with explicit inputs. |
| `dataset/` | Dataset and fixture generation helpers. |
| `needs_review/` | Reserved for scripts that need a data-contract or migration review before relocation. |

## Report And Artifact Namespaces

RAG reports now use explicit namespaces instead of ad-hoc script defaults. The
constants live in `ai/eval/report_paths.py`; new scripts should import that
module rather than spelling these roots by hand.

| Namespace | Path | Git policy | Role |
|---|---|---|---|
| Public portfolio reports | `reports/` allowlist | Track only `portfolio_agentops_report.md` and `agentops_sample_trace.json` | Small sanitized public artifacts |
| Actual RAG reports | `reports/rag_eval/` | Ignored/generated | `report.json` runs, latest pointers, run registry, Weaviate manifests |
| Legacy/current RAG ingestion reports | `reports/rag_eval/rag-ingestion/` | Ignored/generated | v3-v7 diagnostic ladder reports, `status.jsonl`, short-key/current evidence |
| Human-facing ledgers | `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, `docs/rag-ingestion-triage.md` | Tracked | Append-only status, measurements, and triage summaries |

Do not move ignored machine artifacts into tracked docs. For portfolio/freezing
work, summarize the evidence in the tracked ledgers and keep the machine payloads
local/generated unless a run contract explicitly names a tracked artifact.

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

## Phase 1 RAG Diagnostic Closeout Inventory

`rag_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod.py`
is the active Phase 1 closure runner/check script. It remains a legacy
entrypoint for tests and docs, while shared v3_22 source-first runtime DTOs,
XLSX display/range helpers, and FastAPI-safe service boundaries live in
`app/capabilities/rag_orchestrator/phase1_diagnostic_runtime.py`.

| Bucket | Current classification |
|---|---|
| `required_by_current_tests` | `status.jsonl`, the current v6_9 report, v6_0 through v6_8 rollback/source reports and required sidecars, v7_0/v7_0_1 audit reports, v5_6/v5_6_2/v5_6_3 fail-closed official-metric probe reports, the v5_5 run-local official metric dry-run artifacts, the explicit v5_4 packet, v5_3 through v5_0 basis reports, v4_7 lineage reports, and v3_9_2 through v3_22 scripts. |
| `required_by_docs_or_status_sync` | v3_22 `report.json` and the rolling docs/status entries that anchor Phase 1 closure. |
| `ignored_diagnostic_artifact` | RAG ingestion `report.json`, `status.jsonl`, and optional review packets under `reports/rag_eval/rag-ingestion/`. |
| `external_archive_candidate` | Older ignored quality/perf payloads not read by current tests, after exact-stem `rg` and artifact-required gates. |
| `legacy_script_entrypoint_to_keep` | v3_9_2-v3_22 runners/checks, `rag_xlsx_v3_failure_breakdown.py`, and `rag_xlsx_v3_failure_case_review.py`. |
| `reusable_runtime_logic_to_extract` | v3_20 adapter contracts, v3_21 LLM I/O observability, v3_22 XLSX display/range rendering, and single-report status helpers. |
| `dead_temp_or_scratch_candidate` | No v3 scratch script is currently classified as safe to delete from `ai/scripts/`. |

Do not convert diagnostic scripts into production code. Keep v3_19-v3_21 as
runtime/observability predecessors, keep v3_22 as the single-report closure
entrypoint, and keep v4 work in persisted locator/holdout/fine-tuning
readiness lanes only while the diagnostic boundaries remain green.

## Repository Cleanup Experiment Classification (2026-06-04)

This table records the cleanup classification used for the repository cleanup
and experiment dependency repair pass. The pass did not delete or move legacy
experiments because the current RAG docs, tests, and report artifacts still
depend on diagnostic history, ignored evidence, and explicit short-key
checkability.

| Path or surface | Classification | Action | Evidence | Risk | Validation |
|---|---|---|---|---|---|
| `ai/scripts/rag_eval.py`, `ai/eval/rag_eval_registry.py`, `ai/eval/rag_v5*.py`, `ai/eval/rag_v6*.py`, `ai/eval/rag_v70*.py` | active-supported | Preserved; docs updated so `current` resolves to `v6_9_answer_quality_gate_packet_nonprod` while v5 official-metric probe lanes remain explicit fail-closed history. | Registry current alias, `rag_eval.py current --check`, current status/progress entries. | High if current alias, official metric input, or protected namespace semantics drift. | `rag_eval.py current --check`, `rag_eval.py v6_9_answer_quality_gate_packet_nonprod --check`, `pytest --rag-current`. |
| `ai/eval/rag_v4_*.py`, `ai/eval/rag_v3_*.py`, and v3/v4 report-writing checks | active-diagnostic-only | Preserved in place as explicit diagnostic history. | v4/v3 inventory above, current tests requiring old scripts/reports, frozen v4 closeout basis. | High if cleanup removes artifacts that are ignored but still used by checks. | Current RAG focused tests and direct short-key checks. |
| `ai/scripts/tune.py`, `ai/scripts/summarize_study.py`, `ai/eval/experiments/active.yaml` | active-diagnostic-only | Preserved; dependencies scoped to the `experiments` optional group and missing-dependency messages made explicit. | `active.yaml` keeps the Phase 7 template schema-valid but disables full tuning sweeps. | Medium; optional tooling should not become a production dependency. | Experiment dependency cleanup contract test and py_compile smoke. |
| `ai/eval/tune_eval.py` and `ai/eval/tuning/answer_recovery_optuna_objective.py` | active-supported | Preserved as project-side adapters for the installed optuna-round-refinement skill. | Experiment README, answer-recovery readiness script, config references. | Medium; real validation must require datasets instead of silently scoring an empty bundle. | Import/dependency checks; dataset-required behavior documented. |
| `ai/eval/tune_eval_offline.py` | legacy-archived | Preserved in place and documented as legacy replay/offline adapter rather than moved. | Self-identifies as offline sister to `tune_eval.py`; useful for old bundle replay. | Low if preserved; medium if moved because old round bundles may import it. | Classification docs only; no semantic change. |
| `ai/scripts/confirm_*`, `ai/scripts/rerender_variant_verdict.py`, wide-MMR helper scripts | active-diagnostic-only | Preserved. | Script headers and helper imports label silver/diagnostic retrieval comparisons and optuna-winner analysis. | Medium; may read historical reports and ignored outputs. | Current tests and no path moves. |
| `ai/scripts/run_phase7_*`, `ai/scripts/rag_*optuna*`, `ai/eval/configs/*optuna*.yaml` | active-diagnostic-only | Preserved; `jsonschema` added to experiment dependencies for readiness diagnostics. | Phase 7 and answer-recovery configs set tuning/reporting gates explicitly. | High if these were removed because they encode gold/silver policy boundaries. | py_compile and dependency import smoke. |
| `reports/rag_eval/rag-ingestion/*`, `ai/eval/indexes/*`, `ai/eval/eval_queries/*`, `ai/eval/source_registry/*`, `ai/eval/silver/*` | unknown-preserve | No deletion or semantic edits. | Boundary guardian and guardrail tests identify these as protected or evidence-critical even when ignored. | High; deletion or denominator edits would require human gold/eval policy. | Protected diff check and RAG checks. |
| `__pycache__`, `.pytest_cache`, `core-api/target`, `frontend/app/dist` | safe-transient-delete | Removed in the 2026-06-09 cleanup inventory only after path resolution proved every target stayed inside the repo. | `.gitignore` and `frontend/app/.gitignore` classify these as cache/build output; generated report `repo_cleanup_20260609_diagnostic_inventory` records the counters. | Low; they regenerate on test/build. | Re-run current RAG checks and targeted tests after cleanup. |
| legacy-remove | legacy-remove | None. | No experiment had enough evidence to delete without risking diagnostic or gold/eval evidence loss. | N/A | Final diff review. |
