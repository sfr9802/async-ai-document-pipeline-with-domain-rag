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

<!-- v4_diagnostic_runtime_locator_and_finetune_readiness_inventory:start -->
## v4 RAG Diagnostic Runtime/Locator/Fine-Tuning Readiness Inventory

| Script | Role |
|---|---|
| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; `current` resolves to `v5_6`, `v5_6_2_official_metric_backend_enabled_preflight_scored_rerun_nonprod` remains the latest explicit backend-enabled preflight lane, `v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run` remains the read-only 29-row official metric input source, `v5_4_user_owned_official_eval_approval_packet` remains explicit, `v5_3_pdf_text_residual_retrieval_evidence_hardening` remains explicit, `v5_2_xlsx_residual_candidate_only_retrieval_engineering` remains explicit, `v5_1_official_eval_gate_scaffolding` remains explicit, `v5_0_v4_closeout_and_v5_gate_plan` remains explicit, `v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` remains explicit as the frozen v4 closeout basis, and promotion/product-success/training/fine-tuning/live-readiness stay closed. |
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
| `required_by_current_tests` | `status.jsonl`, the current v5_6 report, the explicit v5_6_2 preflight report, the v5_5 run-local official metric dry-run artifacts, the explicit v5_4 packet, v5_3, v5_2, v5_1, and v5_0 basis reports, the frozen v4_7_18 source report, and v3_9_2 through v3_22 scripts. |
| `required_by_docs_or_status_sync` | v3_22 `report.json` and the rolling docs/status entries that anchor Phase 1 closure. |
| `ignored_diagnostic_artifact` | RAG ingestion `report.json`, `status.jsonl`, and optional review packets under `eval/reports/rag-ingestion/`. |
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
| `ai/scripts/rag_eval.py`, `ai/eval/rag_eval_registry.py`, `ai/eval/rag_v5*.py` | active-supported | Preserved; docs updated so `current` resolves to `v5_6` and `v5_6_2` remains explicit. | Registry current alias, `rag_eval.py --check`, current status/progress entries. | High if current alias, official metric input, or protected namespace semantics drift. | `rag_eval.py current --check`, `rag_eval.py v5_6_2 --check`, `pytest --rag-current`. |
| `ai/eval/rag_v4_*.py`, `ai/eval/rag_v3_*.py`, and v3/v4 report-writing checks | active-diagnostic-only | Preserved in place as explicit diagnostic history. | v4/v3 inventory above, current tests requiring old scripts/reports, frozen v4 closeout basis. | High if cleanup removes artifacts that are ignored but still used by checks. | Current RAG focused tests and direct short-key checks. |
| `ai/scripts/tune.py`, `ai/scripts/summarize_study.py`, `ai/eval/experiments/active.yaml` | active-diagnostic-only | Preserved; dependencies scoped to the `experiments` optional group and missing-dependency messages made explicit. | `active.yaml` keeps the Phase 7 template schema-valid but disables full tuning sweeps. | Medium; optional tooling should not become a production dependency. | Experiment dependency cleanup contract test and py_compile smoke. |
| `ai/eval/tune_eval.py` and `ai/eval/tuning/answer_recovery_optuna_objective.py` | active-supported | Preserved as project-side adapters for the installed optuna-round-refinement skill. | Experiment README, answer-recovery readiness script, config references. | Medium; real validation must require datasets instead of silently scoring an empty bundle. | Import/dependency checks; dataset-required behavior documented. |
| `ai/eval/tune_eval_offline.py` | legacy-archived | Preserved in place and documented as legacy replay/offline adapter rather than moved. | Self-identifies as offline sister to `tune_eval.py`; useful for old bundle replay. | Low if preserved; medium if moved because old round bundles may import it. | Classification docs only; no semantic change. |
| `ai/scripts/confirm_*`, `ai/scripts/rerender_variant_verdict.py`, wide-MMR helper scripts | active-diagnostic-only | Preserved. | Script headers and helper imports label silver/diagnostic retrieval comparisons and optuna-winner analysis. | Medium; may read historical reports and ignored outputs. | Current tests and no path moves. |
| `ai/scripts/run_phase7_*`, `ai/scripts/rag_*optuna*`, `ai/eval/configs/*optuna*.yaml` | active-diagnostic-only | Preserved; `jsonschema` added to experiment dependencies for readiness diagnostics. | Phase 7 and answer-recovery configs set tuning/reporting gates explicitly. | High if these were removed because they encode gold/silver policy boundaries. | py_compile and dependency import smoke. |
| `ai/eval/reports/rag-ingestion/*`, `ai/eval/indexes/*`, `ai/eval/eval_queries/*`, `ai/eval/source_registry/*`, `ai/eval/silver/*` | unknown-preserve | No deletion or semantic edits. | Boundary guardian and guardrail tests identify these as protected or evidence-critical even when ignored. | High; deletion or denominator edits would require human gold/eval policy. | Protected diff check and RAG checks. |
| legacy-remove | legacy-remove | None. | No experiment had enough evidence to delete without risking diagnostic or gold/eval evidence loss. | N/A | Final diff review. |
