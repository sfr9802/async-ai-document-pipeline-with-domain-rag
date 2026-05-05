# Artifacts And Reports

이 문서는 Track C에서 만들거나 갱신할 스크립트와 report의 소유 phase를 정리한다. 실제 구현 시 파일명이 바뀌면 이 표를 먼저 갱신한다.

## Script Matrix

| Phase | 스크립트 | 목적 |
|---|---|---|
| C0 | `ai-worker/scripts/rag_pdf_current_diagnostic_snapshot.py` | 현재 full72/PDF diagnostic hash와 counter freeze |
| C1 | `ai-worker/scripts/pdf_candidate_scope_report.py` | PDF candidate scope, parser version, documentVersionId 범위 확인 |
| C2 | `ai-worker/scripts/pdf_vector_metadata_projection_readiness.py` | vector hit에서 page/bbox/location metadata 복원 가능 여부 확인 |
| C3 | `ai-worker/scripts/rag_pdf_embedding_text_contract_audit.py` | embedding_text/bm25/display/citation surface audit |
| C4 | `ai-worker/scripts/pdf_candidate_clean_rebuild_prepare.py` | 기존 PDF candidate namespace DB rows와 artifact dir 상태가 불일치할 때 C1 scope 안에서만 clean rebuild 준비 |
| C4 | `ai-worker/scripts/pdf_candidate_embedding_consistency.py` | PDF candidate rows, embedding_record, ragmeta chunks, namespace consistency 확인 |
| C5 | `ai-worker/scripts/rag_pdf_vector_diagnostic.py` | PDF-only vector diagnostic 실행 |
| C6 | `ai-worker/scripts/rag_pdf_vector_quality_breakdown.py` | page/bbox/gold/ranking failure 분해 |
| C7 | `ai-worker/scripts/rag_pdf_gold_policy_review.py` | PDF page/table/OCR gold row policy review |
| C2/C3/C7 | `ai-worker/scripts/rag_pdf_ocr_trust_readiness.py` | OCR confidence/trust metadata readiness 확인 |

## Report Matrix

| Phase | 리포트 | 완료 신호 |
|---|---|---|
| C0 | `ai-worker/eval/reports/rag-ingestion/rag_pdf_current_diagnostic_snapshot.json` | baseline hash와 current PDF failure counters recorded |
| C1 | `ai-worker/eval/reports/rag-ingestion/pdf_candidate_scope_report.json` | scope, parser, block type, OCR 분포와 completeness counters recorded |
| C2 | `ai-worker/eval/reports/rag-ingestion/pdf_vector_metadata_projection_readiness.json` | metadata projection blocker count 0 |
| C3 | `ai-worker/eval/reports/rag-ingestion/rag_pdf_embedding_text_contract_audit.json` | text contract blocker count 0 |
| C4 | `ai-worker/eval/reports/rag-ingestion/pdf_candidate_clean_rebuild_prepare_report.json` | C1 scoped stale candidate rows cleaned without broad/global delete |
| C4 | `ai-worker/eval/reports/rag-ingestion/pdf_candidate_indexing_report.json` | claimed=indexed, failed=0 |
| C4 | `ai-worker/eval/reports/rag-ingestion/pdf_candidate_embedding_consistency_report.json` | embedding/chunk/namespace/hash mismatch count 0 |
| C5 | `ai-worker/eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json` | PDF-only vector diagnostic metrics recorded |
| C6 | `ai-worker/eval/reports/rag-ingestion/rag_pdf_vector_quality_breakdown.json` | UNKNOWN failure 0, query별 next_action present |
| C7 | `ai-worker/eval/reports/rag-ingestion/rag_pdf_gold_policy_review.json` | invalid/ambiguous gold policy counters 0 |
| C2/C3/C7 | `ai-worker/eval/reports/rag-ingestion/rag_pdf_ocr_trust_readiness.json` | OCR confidence/trust blocker count 0 |

## Report 공통 필드

모든 Track C 신규 report는 가능한 한 다음 필드를 가진다.

```json
{
  "track": "C",
  "source_file_type": "PDF",
  "promotion_evidence": false,
  "evidence_role": "diagnostic",
  "index_version": "rag-ingestion-v2-pdf-candidate-v1",
  "artifact_dir": "ai-worker/eval/indexes/rag-data-pdf-candidate-v1",
  "generated_at": "...",
  "input_artifacts": [],
  "scope": {
    "document_version_ids": [],
    "parser_versions": ["pdf-extract-v1", "pdf-extract-v2"]
  },
  "counters": {}
}
```

## 변경 금지 Artifact

다음 artifact는 Track C phase gate를 통과하기 위해 갱신하지 않는다.

- immutable full72 baseline artifact
- XLSX-only diagnostic index
- XLSX candidate namespace
- legacy global PDF rows
- promotion evidence bundle

legacy PDF row 정리는 별도 cleanup 트랙으로 분리한다. Track C에서는 explicit scope와 `allowUnscoped=false`로 회피한다.
