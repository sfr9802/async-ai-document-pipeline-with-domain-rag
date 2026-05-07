# XLSX Pre-Silver Risk Closure - 2026-05-07

## Status

`APPROVED_FOR_XLSX_SILVER_GENERATION_STRICT`

Scope: XLSX retrieval/evidence silver generation only. XLSX answer-generation official denominator remains `0`.

## Decision Table

| Issue | Decision | Status |
| --- | --- | --- |
| Official XLSX eval can accidentally use generic AGENT/orchestrator | Fail closed for eval_mode=official track=XLSX when AGENT/orchestrator or combined retrieval is selected. | closed |
| Diagnostic agentic XLSX loop can lose track/namespace | Diagnostic agentic path requires explicit allow flag and per-iteration XLSX namespace checks. | closed |
| Invalid LLM JSON / keyword-only answers can leak as unstructured success | Always emit schema-valid diagnostic rows; invalid JSON and keyword-only are diagnostic failures, never official metrics. | closed |
| 23-row human-review denominator vs legacy 35-row v3 ambiguity | Current XLSX wrapper default is 23-row human-review retrieval/evidence denominator; v3 35-row is retained only as legacy diagnostic. | closed |
| Artifact resolver can silently miss/tamper current artifacts | Strict pre-silver resolver verifies registry hashes and row counts; canonical reports/source snapshot are allowlisted. | closed |
| Normalized excluded-row hidden leakage was not fully reprobed | Residual warning, not blocker for 23-row retrieval/evidence silver generation: excluded rows are not in official denominator and no silver rows were generated. Add normalized excluded leakage probe before answer-generation/promotion. | residual_warning |
| Protected registry hash bridge could drift after mutable denominator metadata updates | Protect registry by policy validation instead of a static SHA pin; require current XLSX 23-row default and answer denominator 0. | closed |
| Normalizer validation failure could overwrite existing official artifacts before failing | Validation failures write FAIL reports only and skip normalized/official/jsonl artifact writes. | closed |
| Diagnostic agentic allow flag could imply a working runner without runtime wiring | Current XLSX wrapper has no diagnostic agentic runner; explicit allow now fails closed after config validation. | closed |
| Official XLSX wrapper accepted mismatched candidate_index_version / required_index_version strings | Official XLSX eval now requires candidate_index_version and required_index_version to equal rag-ingestion-v2-xlsx-candidate-v1. | closed |
| Generic retrieval eval CLI could validate current XLSX official denominator as library_search promotion evidence | The generic harness now fails closed for current XLSX human-review official gold filenames and reports no promotion evidence. | closed |
| Strict JSON report had stale duplicated command-result text for LLM invalid JSON count and pytest count | Command-result summaries must agree with structured probe counts and verification_results. | closed |

## Denominator Lineage

- Normalized XLSX rows: `50`
- Current official XLSX retrieval/evidence denominator: `23`
- XLSX answer-generation official denominator: `0`
- Legacy XLSX v3 reviewed positive denominator: `35`, marked `current_default=false` and `superseded_by=track_a_xlsx_human_review_normalized_v0`
- `gq_xlsx_date_number_format_003` and `gq_xlsx_aggregation_001` remain non-official.

## Route And Orchestrator Guard

- Official XLSX eval is `eval_mode=official`, `retrieval_backend=vector`, namespace `rag-ingestion-v2-xlsx-candidate-v1`.
- Generic AGENT/orchestrator and combined retrieval are fail-closed for official XLSX eval.
- Candidate and required index versions must equal `rag-ingestion-v2-xlsx-candidate-v1`.
- Generic retrieval eval now fails closed for the current XLSX human-review official gold artifacts, including `library_search + --promotion-evidence` probes.
- Current wrapper reports `diagnostic_agentic_runner_available=false`; diagnostic agentic allow fails closed unless a scoped runner is explicitly implemented later.
- Diagnostic loop validators require track/namespace, no global fallback, no TEXT/PDF retriever, no external search, bounded iterations, and stop reason.

## Retrieval Smoke

- Status: `COMPLETED`
- Denominator rows: `23`
- Repeatability stable: `True`
- Candidate order stable: `True`
- Hit@10: `1.0`
- MRR@10: `0.942`
- XLSX citation/location accuracy: `1.0`

## LLM Diagnostic Smoke

- Status: `PASS_WITH_WARNINGS` diagnostic-only
- Repeat status signature stable: `True`
- Output rows: `10`
- Invalid JSON count: `3`
- Keyword-only rejected count: `5`
- Output row schema valid: `True`
- Official metric included: `false` for all rows
- Answer-generation denominator included: `false` for all rows

## Subagents Used

- OrchestratorRiskAgent (Misono Mika the 2nd): Current XLSX wrapper bypasses generic AGENT/orchestrator; Generic harness/AGENT/orchestrator remains unsafe for official XLSX unless fail-closed; Need official route guard and no-global fallback checks
- LLMShapeRiskAgent (Iochi Mari the 2nd): Invalid JSON already became diagnostic rows but status accounting was too loose; Keyword-only answers were flagged but needed explicit rejection/classification; LLM output is isolated from official metrics and denominator remains 0
- DenominatorLineageAgent (Yurizono Seia the 2nd): 23-row human-review denominator exists beside legacy 35-row v3; Registry needed current default and superseded markers; Diagnostic answer-generation flags must not be official denominator fields
- ArtifactResolutionAgent (Takanashi Hoshino the 2nd): Current artifact hashes existed but consumers did not enforce them; Source snapshot and current reports needed gitignore allowlisting; mtime latest source selection is unsafe for preflight lanes
- RedTeamRiskClosureAgent (Hayase Yuuka the 2nd): Do not call repo-wide denominator current while old scripts remain legacy; LLM diagnostic failures must not look like green official gates; Hidden leakage coverage should be scoped as residual warning unless normalized excluded rows are probed

## Commands Run

- `python -m py_compile ai-worker\scripts\rag_xlsx_pre_silver_risk_closure.py ai-worker\scripts\rag_xlsx_retrieval_performance_diagnostic.py ai-worker\scripts\rag_pdf_xlsx_llm_answer_probe.py ai-worker\scripts\rag_xlsx_human_review_gold_normalizer.py ai-worker\scripts\rag_pdf_supplemental_common.py ai-worker\eval\harness\rag_ingestion_retrieval_eval.py` -> passed
- `python -m pytest ai-worker\tests\test_rag_xlsx_pre_silver_risk_closure.py ai-worker\tests\test_rag_xlsx_track_a_scripts.py ai-worker\tests\test_rag_xlsx_human_review_gold_normalizer.py ai-worker\tests\test_pdf_xlsx_answer_repair.py ai-worker\tests\test_rag_xlsx_answer_context_assembly.py ai-worker\tests\test_rag_xlsx_content_drop_trace.py ai-worker\tests\test_retrieval_eval_harness.py ai-worker\tests\test_phase7_v4_guardrails.py ai-worker\tests\test_rag_pdf_supplemental_guardrails.py -q` -> 145 passed, 1 warning
- `python scripts\rag_xlsx_human_review_gold_normalizer.py --review-pack eval\artifacts\eval_runs\xlsx_human_review_gold_normalization_20260507T091500Z\source_xlsx_gold_human_review_pack_used.csv --run-id 20260507Tpreflight --source-label xlsx_human_review_preflight_source_snapshot --update-registry` -> passed; normalized=50; official_positive=23; answer_denominator=0
- `python scripts\rag_xlsx_retrieval_performance_diagnostic.py --top-k 10 --report eval\reports\rag-ingestion\rag_retrieval_eval_xlsx_human_review_official_positive_v0_vector_diagnostic_report.json --summary eval\reports\rag-ingestion\rag_xlsx_human_review_official_positive_v0_retrieval_performance_summary.json --hidden-report eval\reports\rag-ingestion\rag_xlsx_human_review_official_positive_v0_hidden_negative_leakage_diagnostic.json` -> passed; Hit@10=1.0; MRR@10=0.942; XLSX citation/location=1.0
- `python scripts\rag_xlsx_retrieval_performance_diagnostic.py --top-k 10 --report eval\reports\rag-ingestion\rag_retrieval_eval_xlsx_human_review_official_positive_v0_vector_diagnostic_report_repeat.json --summary eval\reports\rag-ingestion\rag_xlsx_human_review_official_positive_v0_retrieval_performance_summary_repeat.json --hidden-report eval\reports\rag-ingestion\rag_xlsx_human_review_official_positive_v0_hidden_negative_leakage_diagnostic_repeat.json` -> passed; repeat metrics and candidate order stable
- `python scripts\rag_pdf_xlsx_llm_answer_probe.py --source-artifact-dir eval\artifacts\eval_runs\pdf_xlsx_answer_shape_xlsx_generalization_audit_20260506T061055Z --max-rows 10 --run-id 20260507Tpre_silver_strict_live --run-prefix xlsx_pre_silver_llm_answer_probe --temperature 0.0 --max-tokens 300 --timeout-seconds 120 --allow-diagnostic-failures` -> passed as diagnostic; PASS_WITH_WARNINGS; invalid_json=3; keyword_only_rejected=5; official answer denominator=0
- `python scripts\rag_pdf_xlsx_llm_answer_probe.py --source-artifact-dir eval\artifacts\eval_runs\pdf_xlsx_answer_shape_xlsx_generalization_audit_20260506T061055Z --max-rows 10 --run-id 20260507Tpre_silver_strict_live_repeat --run-prefix xlsx_pre_silver_llm_answer_probe --temperature 0.0 --max-tokens 300 --timeout-seconds 120 --allow-diagnostic-failures` -> passed as diagnostic; repeat status signature stable

## Verification

- `diagnostic_llm_smoke`: PASS_WITH_WARNINGS diagnostic-only; schema-valid failure rows; official denominator 0
- `focused_pytest`: 145 passed, 1 warning
- `protected_source_blockers`: []
- `py_compile`: passed
- `registry_sanity`: passed
- `retrieval_repeatability`: stable
- `retrieval_smoke`: passed
- `generic_current_xlsx_guard`: ROUTE_GUARD_FAILED for library_search + --promotion-evidence on current XLSX official gold

## Residual Risks

- Legacy Track A v3 scripts remain as historical diagnostic entrypoints. Strict approval applies to the current XLSX wrapper/retrieval-evidence path.
- Normalized human-review EXCLUDED/PENDING rows are excluded from official metrics, but a separate normalized excluded-row leakage probe should be added before any future answer-generation or promotion lane.
- Local LLM answer quality remains diagnostic-only; invalid JSON and keyword-only outputs are captured as diagnostic failures and must not be used as official XLSX answer-generation evidence.
- Current artifacts are verified in this workspace and allowlisted from .gitignore; repository durability still depends on committing/preserving the generated registry, artifacts, reports, and tests.

## Final Recommendation

Proceed to XLSX retrieval/evidence silver generation only. Do not enable XLSX official answer generation or aggregate LLM smoke results into official metrics.
