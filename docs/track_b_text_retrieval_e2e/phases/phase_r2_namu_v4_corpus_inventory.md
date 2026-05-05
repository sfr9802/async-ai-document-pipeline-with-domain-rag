# R2 — namu-v4 Corpus Inventory

## Goal

`namu-v4-structured-combined`를 Track B TEXT 본선 corpus로 등록하기 전에 구조, hash, schema, context field를 검증한다.

## Expected Directory

```text
ai-worker/eval/corpora/namu-v4-structured-combined/
```

## Expected Files

```text
pages_v4.jsonl
chunks_v4.jsonl
rag_chunks.jsonl
validation_report.json
split_manifest.json
split_manifest.report.json
```

## New Files

```text
scripts/rag_text_namu_v4_corpus_inventory.py
ai-worker/tests/test_rag_text_namu_v4_corpus_inventory.py
reports/rag_text_namu_v4_corpus_inventory_report.json
```

## Checks

```text
1. directory exists
2. required files exist
3. each JSONL is parseable
4. row counts are non-zero
5. sha256 is recorded for each file
6. rag_chunks chunk_id is unique
7. rag_chunks has a raw context field, preferably chunk_text
8. empty chunk_text count is recorded
9. page_id / section_path / title metadata presence is recorded
10. embedding_text/text_for_embedding/debug_text fields are not selected as LLM context source
11. validation_report counts match pages_v4/chunks_v4 row counts
12. validation_report duplicate/empty/schema-mismatch counters are clean
13. split_manifest doc ids exactly match pages_v4 page ids
14. split_manifest declared doc counts match split doc_ids, total, and pages_v4 row count
15. split_manifest.report has zero doc/group leakage and distribution counts match rag_chunks
16. chunk_text has no internal raw JSON marker leakage and does not equal embedding_text
```

## Required Report Fields

```json
{
  "status": "PASS | FAIL",
  "corpus_dir": "ai-worker/eval/corpora/namu-v4-structured-combined",
  "files": {
    "pages_v4.jsonl": {"exists": true, "row_count": 0, "sha256": "..."},
    "chunks_v4.jsonl": {"exists": true, "row_count": 0, "sha256": "..."},
    "rag_chunks.jsonl": {"exists": true, "row_count": 0, "sha256": "..."}
  },
  "rag_chunks_schema": {
    "chunk_id_unique": true,
    "raw_context_field": "chunk_text",
    "empty_chunk_text_count": 0,
    "missing_page_id_count": 0,
    "missing_section_path_count": 0
  },
  "context_policy": {
    "allowed_context_fields": ["chunk_text", "text"],
    "disallowed_context_fields": ["embedding_text", "text_for_embedding", "debug_text"]
  },
  "hardened_consistency": {
    "validation_report": {"clean": true},
    "split_manifest": {"doc_counts_clean": true},
    "split_manifest_report": {"clean": true}
  },
  "raw_context_trust": {
    "raw_context_trust_counters_clean": true
  },
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

## Acceptance Criteria

- `status=PASS` only when `rag_chunks.jsonl` exists, parseable, has unique chunk ids, and has non-empty raw context text.
- `chunk_text`가 없으면 fail-closed. 단, `text`가 동등한 raw field로 확인되면 report에 명시하고 통과 가능.
- Auxiliary validation/split reports must be present, parseable, and consistent with JSONL row counts.
- `split_manifest.json` must have per-split declared counts that match the actual split `doc_ids`.
- Split leakage counters and raw-context trust counters must be clean.
- R3/R4는 R2 PASS 전까지 blocked.
