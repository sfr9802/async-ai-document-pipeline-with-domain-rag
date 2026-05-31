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
| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; `current` resolves to `v4_7_17`, `v4_7_16_target_recall_repair_prototype` remains explicit, `v4_7_15_read_only_searchindex_replay_projection` remains explicit, `v4_7_14_diagnostic_precondition_hardening` remains explicit, `v4_7_13_live_retrieval_answerability_and_full_pdf_replay` remains explicit, `v4_7_12_layered_retrieval_generalization_and_overfit_audit` records layered retrieval audit rows 1057, `v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness`, `v4_7_9_pdf_evidence_residual_answer_quality_replay`, and prior v4_7 cleanup keys remain checkable without opening official metrics. |
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

v4 scripts remain diagnostic/non-production and write one ignored `report.json`
per run. Actual fine-tuning remains closed until real disjoint splits and
user-owned gold/qrels/denominator policy exist.
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
| `required_by_current_tests` | `status.jsonl`, current v3/v4 `report.json` artifacts, and v3_9_2 through v3_22 scripts. |
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
