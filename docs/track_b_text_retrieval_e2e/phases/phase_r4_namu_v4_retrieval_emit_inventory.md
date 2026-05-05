# R4 — namu-v4 Retrieval Emit Inventory or Fresh Retrieval

## Goal

기존 namu-v4 retrieval emit이 있으면 먼저 재사용 가능성을 검증하고, 없으면 fresh diagnostic retrieval path를 명시한다.

## New Files

```text
scripts/rag_text_namu_v4_retrieval_emit_inventory.py
reports/rag_text_namu_v4_retrieval_emit_inventory_report.json
```

## Checks

```text
1. existing retrieval emit files exist or not
2. emit query ids match gold query ids
3. hit chunk ids resolve against rag_chunks.jsonl
4. top_k is recorded
5. retriever identity is recorded
6. score fields are numeric when present
7. no missing chunk resolution
```

## Decision Output

```json
{
  "status": "REUSABLE_EXISTING_EMIT | NO_REUSABLE_EXISTING_EMIT | NO_EXISTING_EMIT | BLOCKED_R3_NOT_PASSED",
  "decision": "USE_EXISTING_EMIT | RUN_FRESH_DIAGNOSTIC_RETRIEVAL | KEEP_R5_BLOCKED",
  "existing_emit_paths": [],
  "missing_chunk_resolution_count": 0,
  "query_id_mismatch_count": 0,
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

## Acceptance Criteria

- 기존 emit을 쓰려면 chunk id resolution이 깨끗해야 한다.
- emit이 없으면 fail이 아니라 `RUN_FRESH_DIAGNOSTIC_RETRIEVAL`로 분기한다.
- R5는 R4 decision이 확정된 뒤 실행한다.

## Current Result

As of 2026-05-05:

- Report: `reports/rag_text_namu_v4_retrieval_emit_inventory_report.json`
- Script: `scripts/rag_text_namu_v4_retrieval_emit_inventory.py`
- Status: `NO_REUSABLE_EXISTING_EMIT`
- Decision: `RUN_FRESH_DIAGNOSTIC_RETRIEVAL`
- Candidate emits inventoried: `46`
- Reusable emits: `0`
- Main blocker for reuse: all candidate emits have `query_id_mismatch` against `eval/gold_queries_text_namu_v4_v0.csv`.
- R5 entry: allowed only as a fresh diagnostic retrieval run; do not reuse Phase 7 tuning/sanity, B-app smoke, XLSX, PDF, or file lookup artifacts as R5 metric input.
- Diagnostic-only: `promotion_evidence=false`, `evidence_role=diagnostic`, `retrieval_metrics_computed=false`.
