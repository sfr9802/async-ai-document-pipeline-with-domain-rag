# RAG v7 E2E Evaluation Plan

## 2026-06-10 Direction Update

This plan now has an additive pragmatic actual-RAG evaluation lane:
`actual_rag_eval_metric_generation_nonprod`. The lane intentionally moves from
"wait for perfect gold policy" to "build first, measure first, repair later."

The older conservative v7 closeout boundaries still apply to official metrics,
promotion evidence, production routing, and gold/qrels mutation. They no longer
block non-official actual RAG evaluation outputs. Incomplete gold rows are
loaded with warnings; strict metrics keep clean denominators; provisional metrics
use broader partial signals; diagnostic metrics always run when the row is
executable.

Metric-semantics repair note: `actual_rag_eval_metric_semantics_repair_nonprod`
tightened the first loop without changing retriever ranking or gold/qrels. The
provisional E2E metric now requires the provisional answer judge to pass, requires
weak or strict evidence at the configured top-k, and keeps answer/context
consistency as a diagnostic standalone metric that can only act as a conservative
E2E support guard. Weak evidence text matching now requires non-generic anchors,
including all numeric/date anchors from the gold signal. The old context/citation
overlap names are kept only as legacy aliases; reports use
`answer_extracted_from_retrieved_context_rate` and
`citation_points_to_retrieved_context_rate` as diagnostic consistency checks.
Unknown-answerability rows with expected answer/evidence are reported in an
inferred-answerable tier without mutating gold labels.

The concrete entrypoint is:

```bash
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset <path-to-json-or-jsonl> \
  --index current \
  --output-dir reports/rag_eval/<run_id> \
  --top-k 10 \
  --judge-mode heuristic
```

`--judge-mode local-llm` is available as an opt-in localhost-only semantic judge
path using the repo's existing llama.cpp/Ollama/openai-compatible helper. It is
not required for automated tests.

## Objective

Recover from the premature `v7_0_e2e_eval_architecture_closeout_nonprod` closeout by preserving v7_0 as diagnostic audit evidence only, implementing `v6_4_e2e_coverage_and_failure_taxonomy_nonprod`, and keeping v7 completion closed until required predecessor checkpoints exist or are explicitly skipped with diagnostic-only reasons.

## Non-Goals

- No gold, qrels, expected evidence, supporting evidence, relevance, answerability, or official denominator creation or mutation.
- No production index, production namespace, production DB/cache, source registry, training dataset, fine-tuning dataset/job/checkpoint, promotion, product-success, or live-readiness mutation or claim.
- No retrieval-quality or answer-quality metric opening without user-owned labels, evidence, denominator, and promotion policy.
- Do not claim v7 completion from v7_0.

## Corrective Finding

- v7_0 is preserved as diagnostic audit evidence only.
- v7_0 is recorded as a premature closeout marker, not a completed v7 architecture milestone.
- historical v6_4 recovery evidence is preserved, but v7_0_1 does not move current; live current remains `v6_9_answer_quality_gate_packet_nonprod`.

## Required Predecessor Checkpoints

- [x] v6_4_e2e_coverage_and_failure_taxonomy_nonprod: present
- [x] v6_5_retrieval_metric_unlock_packet_nonprod: present
- [x] v6_6_structured_tool_operation_taxonomy_nonprod: present
- [x] v6_7_agentic_retry_fail_closed_policy_nonprod: present
- [x] v6_8_metric_gated_retrieval_quality_engineering_nonprod: present
- [x] v6_9_answer_quality_gate_packet_nonprod: present

## v6_4 Recovery Scope

- Reuse v6_3 source-derived SearchUnit/SearchView materialization.
- Reuse bge-m3, FAISS, BM25, and fixed-weight hybrid retrieval paths.
- Attempt candidate coverage over all 300 rows.
- Preserve PDF/TEXT/XLSX 100/100/100 family breakdown.
- Report vector/BM25/hybrid candidate availability separately.
- Hydrate candidates through SourceAtom/EvidenceBundle only.
- Expand evidence-only E2E render coverage beyond the 3-row smoke using a bounded diagnostic.
- Keep retrieval computed-only denominator at 0 and coverage-adjusted denominator at 300 because labels/qrels remain unavailable.
- Keep tool outputs excluded from Hit@k, MRR, and nDCG.
- Keep answer_quality_metric_computed=false.

## Protected Surfaces

- `ai/eval/eval_queries`
- `ai/eval/source_registry`
- `ai/eval/indexes`
- `ai/eval/silver`
- official metric input surfaces
- qrels/gold/expected/supporting/relevance/answerability surfaces
- denominator surfaces
- production DB/cache/index namespaces

## Verification Commands

- `python -X utf8 -m pytest ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py -q`
- `python -X utf8 ai/scripts/rag_eval.py v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod --check`
- `python -X utf8 ai/scripts/rag_eval.py v6_4_e2e_coverage_and_failure_taxonomy_nonprod --check`
- `python -X utf8 ai/scripts/rag_eval.py current --check`
- `python -X utf8 ai/scripts/rag_eval.py v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report --check`
- `python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q`
- `python -X utf8 -m pytest ai/tests --rag-current -q`
- `git diff --check`
