# RAG v7 E2E Evaluation Plan

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
