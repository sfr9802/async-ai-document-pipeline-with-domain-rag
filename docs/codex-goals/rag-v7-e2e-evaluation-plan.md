# RAG v7 E2E Evaluation Plan

## Objective

Implement `v7_0_e2e_eval_architecture_closeout_nonprod` checkpoint by checkpoint as a diagnostic-only marker after `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`. It is not a completed v7 closeout unless the required v6_4-v6_9 predecessors exist or are explicitly skipped with diagnostic-only reasons.

## Non-Goals

- No gold, qrels, expected evidence, supporting evidence, relevance, answerability, or official denominator creation or mutation.
- No production index, production namespace, production DB/cache, source registry, training dataset, fine-tuning dataset/job/checkpoint, promotion, product-success, or live-readiness mutation or claim.
- No retrieval-quality or answer-quality metric opening without user-owned labels, evidence, denominator, and promotion policy.

## Baseline

- Source run: `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`.
- Source status: `V6_3_E2E_BGE_M3_FAISS_AGENTIC_RAG_SMOKE_SINGLE_REPORT_NONPROD_READY`.
- Source report payload SHA256: `e315b2c0fa90e8977b00b3029feab47604d86a52e0ba039c2bedbbc8fbde4054`.
- Rollback key target: `v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report`.

## Checkpoints

- [x] plan_recovery: Create and maintain the missing referenced v7 plan file in place.
- [x] source_v6_3_evidence_lock: Use the v6_3 report as the source E2E architecture evidence and hash-lock it.
- [x] metric_boundary_closeout: Keep retrieval quality, answer quality, and product success metrics closed.
- [x] rollback_current_contract: Move current to v7_0 only after preserving v6_3 as rollback.
- [x] protected_surface_audit: Record protected surfaces as clean without mutating them.
- [x] human_owned_gate_boundary: Record all remaining quality, denominator, and promotion gates as human-owned.

- [ ] predecessor_checkpoint_guard: v6_4-v6_9 predecessor checkpoints are not all present or explicitly skipped, so v7_0 remains a premature closeout marker only.

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

- `python -X utf8 -m pytest ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py -q`
- `python -X utf8 ai/scripts/rag_eval.py v7_0_e2e_eval_architecture_closeout_nonprod --check`
- `python -X utf8 ai/scripts/rag_eval.py current --check`
- `python -X utf8 ai/scripts/rag_eval.py v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report --check`
- `python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q`
- `python -X utf8 -m pytest ai/tests --rag-current -q`
- `git diff --check`
