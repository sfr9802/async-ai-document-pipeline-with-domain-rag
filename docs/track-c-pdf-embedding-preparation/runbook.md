# Track C Runbook

이 문서는 phase 문서의 명령 예시를 한 곳에 모은 실행용 runbook이다. 실제 명령은 구현된 스크립트 옵션에 맞춰 조정한다.

모든 명령은 `ai-worker/`에서 실행한다. 아래 `scripts/`, `eval/`, `fixtures/`
경로는 worker 기준 상대 경로다.

## C0 Evidence Freeze

```bash
python scripts/rag_pdf_current_diagnostic_snapshot.py \
  --retrieval-report eval/reports/rag-ingestion/rag_retrieval_eval_full72_vector_diagnostic_report.json \
  --quality-breakdown eval/reports/rag-ingestion/rag_retrieval_full72_vector_quality_breakdown.json \
  --gold eval/eval_queries/gold_queries_v0.csv \
  --baseline-descriptor eval/reports/rag-ingestion/initial_immutable_vector_baseline_descriptor.json \
  --lineage-report eval/reports/rag-ingestion/rag_candidate_index_lineage_report.json \
  --output eval/reports/rag-ingestion/rag_pdf_current_diagnostic_snapshot.json
```

## C1 Candidate Scope

```bash
python scripts/pdf_candidate_scope_report.py \
  --gold eval/eval_queries/gold_queries_v0.csv \
  --expected-location-type pdf \
  --parser-versions pdf-extract-v1 pdf-extract-v2 \
  --report eval/reports/rag-ingestion/pdf_candidate_scope_report.json
```

## C2 Metadata Projection Readiness

```bash
python scripts/pdf_vector_metadata_projection_readiness.py \
  --scope-report eval/reports/rag-ingestion/pdf_candidate_scope_report.json \
  --report eval/reports/rag-ingestion/pdf_vector_metadata_projection_readiness.json
```

## C3 Embedding Text Contract Audit

```bash
python scripts/rag_pdf_embedding_text_contract_audit.py \
  --scope-report eval/reports/rag-ingestion/pdf_candidate_scope_report.json \
  --report eval/reports/rag-ingestion/rag_pdf_embedding_text_contract_audit.json
```

## C3 Repair: PDF SearchUnit Surface Backfill

Run dry-run first and review `sample_repairs`. Apply only when the mutation
scope is exactly the C1 PDF scope.

```bash
python scripts/rag_pdf_search_unit_surface_repair.py \
  --scope-report eval/reports/rag-ingestion/pdf_candidate_scope_report.json \
  --report eval/reports/rag-ingestion/rag_pdf_search_unit_surface_repair_report.json
```

```bash
python scripts/rag_pdf_search_unit_surface_repair.py \
  --scope-report eval/reports/rag-ingestion/pdf_candidate_scope_report.json \
  --report eval/reports/rag-ingestion/rag_pdf_search_unit_surface_repair_report.json \
  --apply
```

## C4 Candidate Indexing

Do not run C4 while C2 or C3 is `FAIL`. The current indexing wrapper does not
consume the C1 scope report directly, so pass the C1 document-version scope
explicitly or implement a C1 `--scope-report` wrapper before broad use.

```bash
python scripts/rag_scoped_candidate_indexing.py \
  --document-version-id docv_88368b8b12ba3f38 \
  --document-version-id docv_8b23a58c27c5518a \
  --document-version-id docv_fe2470815512a395 \
  --source-file-type PDF \
  --parser-version pdf-extract-v1 \
  --parser-version pdf-extract-v2 \
  --expected-index-version rag-ingestion-v2-pdf-candidate-v1 \
  --output eval/reports/rag-ingestion/pdf_candidate_indexing_report.json
```

The consistency script is still a C4 TODO. Do not treat this command as
available until `scripts/pdf_candidate_embedding_consistency.py` exists.

```bash
python scripts/pdf_candidate_embedding_consistency.py \
  --expected-index-version rag-ingestion-v2-pdf-candidate-v1 \
  --artifact-dir eval/indexes/rag-data-pdf-candidate-v1 \
  --report eval/reports/rag-ingestion/pdf_candidate_embedding_consistency_report.json
```

## C5 PDF-only Vector Diagnostic

```bash
python scripts/rag_pdf_vector_diagnostic.py \
  --gold eval/eval_queries/gold_queries_v0.csv \
  --expected-location-type pdf \
  --index-version rag-ingestion-v2-pdf-candidate-v1 \
  --artifact-dir eval/indexes/rag-data-pdf-candidate-v1 \
  --promotion-evidence false \
  --evidence-role diagnostic \
  --report eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json
```

## C6 Failure Breakdown

```bash
python scripts/rag_pdf_vector_quality_breakdown.py \
  --eval-report eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json \
  --report eval/reports/rag-ingestion/rag_pdf_vector_quality_breakdown.json
```

## C0~C3 Syntax Check

```bash
python -m py_compile \
  scripts/rag_pdf_current_diagnostic_snapshot.py \
  scripts/pdf_candidate_scope_report.py \
  scripts/pdf_vector_metadata_projection_readiness.py \
  scripts/rag_pdf_embedding_text_contract_audit.py \
  scripts/rag_pdf_search_unit_surface_repair.py
```

## Future Phase Syntax Check

Run this only after the C4~C7 scripts in the command exist.

```bash
python -m py_compile \
  scripts/pdf_candidate_embedding_consistency.py \
  scripts/rag_pdf_vector_diagnostic.py \
  scripts/rag_pdf_vector_quality_breakdown.py \
  scripts/rag_pdf_gold_policy_review.py \
  scripts/rag_pdf_ocr_trust_readiness.py
```

## Targeted Tests

```bash
python -m pytest \
  ai-worker/tests/test_rag_pdf_current_diagnostic_snapshot.py \
  ai-worker/tests/test_pdf_candidate_scope_report.py \
  ai-worker/tests/test_pdf_vector_metadata_projection_readiness.py \
  ai-worker/tests/test_rag_pdf_embedding_text_contract_audit.py \
  ai-worker/tests/test_rag_pdf_search_unit_surface_repair.py
```

```bash
python -m pytest \
  ai-worker/tests/test_pdf_extract_capability.py \
  ai-worker/tests/test_retrieval_eval_harness.py \
  ai-worker/tests/test_rag_ingestion_scaffolding.py \
  ai-worker/tests/test_search_unit_indexing_loop.py
```

## Java Guardrail Tests

```bash
mvn -f core-api/pom.xml test "-Dtest=IndexPromotionGateTest,SearchUnitIndexingServiceTest,DocumentCatalogServiceTest"
```

```bash
mvn -f core-api/pom.xml test "-Dtest=SearchUnitIndexingServiceTest#claim_index_metadata_keeps_location_json_as_plain_map_not_jackson_node_shape"
```

## Diff Hygiene

```bash
git diff --check
```
