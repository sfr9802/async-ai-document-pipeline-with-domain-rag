# XLSX End-to-End Preflight - 2026-05-07

Final status: `APPROVED_FOR_XLSX_SILVER_GENERATION`

Approval scope: XLSX retrieval/evidence silver generation only. This phase did
not generate silver data, did not tune retrieval, did not change TEXT/NAMU or
PDF behavior, and did not create an XLSX answer-generation denominator.

## Route Map

| Track | Current route | Namespace / corpus | Isolation result |
|---|---|---|---|
| XLSX | `scripts/rag_xlsx_retrieval_performance_diagnostic.py` | `rag-ingestion-v2-xlsx-candidate-v1`, `eval/indexes/rag-data-xlsx-candidate-v1` | Uses only the XLSX vector namespace and the 23-row human-review retrieval projection. Missing projection fails instead of falling back. |
| TEXT/NAMU | `scripts/rag_text_namu_v4_retrieval_diagnostic.py` | `eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl` | Separate local lexical diagnostic; not changed. |
| PDF | `scripts/rag_pdf_vector_diagnostic.py` | `rag-ingestion-v2-pdf-candidate-v1` | Separate vector diagnostic; not changed. |

The patched XLSX wrapper does not import `AgentCapability`,
`AgentLoopRunner`, `QueryRewriter`, or `rag_orchestrator` components. The
generic AGENT loop remains a future-use risk and must not be used for official
XLSX gold or promotion eval without explicit track/namespace/index policy.

## Denominator Summary

| Item | Value |
|---|---:|
| Normalized XLSX rows | `50` |
| Official XLSX retrieval/evidence denominator | `23` |
| XLSX answer-generation denominator | `0` |
| Diagnostic-only rows | `3` |
| Pending/source-verification rows | `10` |
| Excluded rows | `14` |

Special-row checks:

- `gq_xlsx_date_number_format_003`: `DIAGNOSTIC_ONLY`, not official positive.
- `gq_xlsx_aggregation_001`: `DIAGNOSTIC_ONLY`, not official positive.

Official artifacts:

- `ai-worker/eval/eval_queries/gold_queries_xlsx_human_review_normalized_v0.csv`
- `ai-worker/eval/eval_queries/gold_queries_xlsx_human_review_normalized_v0.jsonl`
- `ai-worker/eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0.csv`
- `ai-worker/eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv`
- `ai-worker/eval/eval_queries/official_denominator_registry.json`

## Query-To-Answer Pipeline

1. The 23 official human-review rows are projected into the retrieval harness
   schema as XLSX-only rows.
2. The XLSX diagnostic wrapper builds FAISS/ragmeta vector search pinned to
   `rag-ingestion-v2-xlsx-candidate-v1`.
3. `evaluate_gold_rows()` checks identity, index version, embedding status,
   file, sheet, range overlap, range containment, and exact range.
4. The XLSX LLM answer probe reads only XLSX evidence rows and builds a
   structured `answer_prompt_payload` containing file, sheet, range, search
   unit id, document version id, and citation locators.
5. LLM citation validation rejects missing citation source, wrong sheet, wrong
   range, partial range overlap, wrong file, wrong document version id, and
   wrong search unit id.
6. LLM answer results remain diagnostic-only and are not official XLSX answer
   scores.

## Live Checks

Retrieval/evidence smoke:

| Metric | Value |
|---|---:|
| Rows | `23` |
| Hit@1 | `0.913` |
| Hit@3 | `1.0` |
| Hit@10 | `1.0` |
| MRR@10 | `0.942` |
| XLSX citation location accuracy | `1.0` |
| Search errors | `0` |
| Index-version mismatches | `0` |
| Embedding-status mismatches | `0` |
| Hidden content leakage | `0` |

Repeatability:

- Retrieval repeat stable ignoring run metadata: `true`
- Retrieval repeat hash: `07a6a065094578d7`
- LLM parser/validator repeat stable: `true`
- LLM repeat hash: `1e2a5fa3a7b2bb9f`

Diagnostic LLM smoke:

| Field | Value |
|---|---:|
| Local LLM run | `true` |
| Rows | `10` |
| Answer-allowed rows | `6` |
| LLM answers | `4` |
| LLM abstains | `6` |
| Invalid JSON count | `2` |
| Grounding validation status | `DIAGNOSTIC_FAILURE` |
| Diagnostic grounding failure count | `4` |
| Citation-not-in-context count | `0` |
| Keyword-echo-only count | `4` |
| Official XLSX answer denominator | `0` |

Decision: this is a diagnostic warning only. It does not block XLSX
retrieval/evidence silver generation, but it blocks any claim of official XLSX
answer-generation quality.

## Subagents

Phase A read-only agents:

- RouteMapAgent
- DenominatorRegistryAgent
- ContextPromptAgent
- AgenticLoopAgent
- CacheRepeatabilityAgent
- LLMGroundingAgent
- TestAndCIReviewAgent
- RedTeamReviewerAgent

Follow-up resolution agents:

- DenominatorConflictResolutionAgent
- PatchSurfaceAgent

Phase E verification agents:

- VerificationRouteAgent
- VerificationDenominatorAgent
- VerificationContextPromptAgent
- VerificationAgenticLoopAgent
- VerificationGroundingAgent
- VerificationTestAgent

Completed verification agents were closed after their findings were integrated.

## Reconciled Decisions

| Issue | Decision | Status |
|---|---|---|
| 23-row denominator meaning | It is the official XLSX retrieval/evidence denominator, not an answer-generation denominator. | Resolved |
| Human-review official CSV did not match retrieval harness schema | Emit a separate 23-row retrieval projection and default XLSX wrapper to it. | Resolved |
| LLM citation parser accepted weak locators | Preserve and validate source/file/docv/search_unit identity and exact ranges. | Resolved |
| Generic agent loop can drop XLSX constraints | Current XLSX eval bypasses it; future use remains blocked until policy is carried through every loop. | Residual risk |
| Tuning sweep disabled but not enforced | `scripts.tune` now honors `allow_tuning_sweep=false`. | Resolved |

## Commands

```powershell
python -m py_compile ai-worker\eval\harness\rag_ingestion_retrieval_eval.py ai-worker\scripts\rag_xlsx_human_review_gold_normalizer.py ai-worker\scripts\rag_xlsx_retrieval_performance_diagnostic.py ai-worker\scripts\rag_pdf_xlsx_llm_answer_probe.py ai-worker\scripts\tune.py
```

```powershell
cd ai-worker
python -m pytest tests\test_rag_xlsx_human_review_gold_normalizer.py tests\test_rag_xlsx_track_a_scripts.py tests\test_pdf_xlsx_answer_repair.py tests\test_phase7_v4_guardrails.py tests\test_retrieval_eval_harness.py tests\test_tune.py tests\test_promotion_gate_persistence.py tests\test_rag_query_orchestrator_vector_tools.py -q
# 124 passed, 2 warnings
```

```powershell
python scripts\rag_xlsx_human_review_gold_normalizer.py --review-pack eval\artifacts\eval_runs\xlsx_human_review_gold_normalization_20260507T091500Z\source_xlsx_gold_human_review_pack_used.csv --run-id 20260507Tpreflight --source-label xlsx_human_review_preflight_source_snapshot --update-registry
```

```powershell
python scripts\rag_xlsx_retrieval_performance_diagnostic.py --top-k 10 --report eval\reports\rag-ingestion\rag_retrieval_eval_xlsx_human_review_official_positive_v0_vector_diagnostic_report.json --summary eval\reports\rag-ingestion\rag_xlsx_human_review_official_positive_v0_retrieval_performance_summary.json --hidden-report eval\reports\rag-ingestion\rag_xlsx_human_review_official_positive_v0_hidden_negative_leakage_diagnostic.json
```

```powershell
python scripts\rag_pdf_xlsx_llm_answer_probe.py --source-artifact-dir eval\artifacts\eval_runs\pdf_xlsx_answer_shape_xlsx_generalization_audit_20260506T061055Z --max-rows 10 --run-id 20260507Tpreflight_live --run-prefix xlsx_preflight_llm_answer_probe --temperature 0.0 --max-tokens 300 --timeout-seconds 120
```

## Residual Risks

- LLM answer smoke is deterministic but diagnostic-failing due keyword-only
  answers and invalid JSON. Do not use it for official answer-generation
  metrics.
- Generic AGENT and orchestrator loops remain unsafe for official XLSX
  gold/promotion eval until explicit track/namespace/index policy is carried
  through rewrite/retry/tool calls.
- Old `answer_generation_inputs.prompt_context` artifacts can be mixed/truncated.
  Current preflight answer probing uses the structured XLSX evidence payload
  instead.
- Direct shared harness CLI defaults are generic. Official XLSX eval should use
  the XLSX wrapper or explicit vector/XLSX flags.

## Strict Pre-Silver Supersession Note

The original LLM smoke artifact links in this report predate the strict diagnostic-output schema hardening. For LLM shape proof, use `ai-worker/eval/reports/rag-ingestion/xlsx_pre_silver_risk_closure_20260507.json` and the `xlsx_pre_silver_llm_answer_probe_20260507Tpre_silver_strict_live*` artifacts. The original approval remains scoped to XLSX retrieval/evidence only.

