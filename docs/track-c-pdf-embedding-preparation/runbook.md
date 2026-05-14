# Track C Runbook

이 문서는 phase 문서의 명령 예시를 한 곳에 모은 실행용 runbook이다. 실제 명령은 구현된 스크립트 옵션에 맞춰 조정한다.

## C0 Evidence Freeze

```bash
python scripts/rag_pdf_current_diagnostic_snapshot.py \
  --retrieval-report reports/rag_retrieval_eval_full72_vector_diagnostic_report.json \
  --quality-breakdown reports/rag_retrieval_full72_vector_quality_breakdown.json \
  --gold eval/gold_queries_v0.csv \
  --baseline-descriptor reports/initial_immutable_vector_baseline_descriptor.json \
  --lineage-report reports/rag_candidate_index_lineage_report.json \
  --output reports/rag_pdf_current_diagnostic_snapshot.json
```

## C1 Candidate Scope

```bash
python scripts/pdf_candidate_scope_report.py \
  --gold eval/gold_queries_v0.csv \
  --expected-location-type pdf \
  --parser-versions pdf-extract-v1 pdf-extract-v2 \
  --report reports/pdf_candidate_scope_report.json
```

## C2 Metadata Projection Readiness

```bash
python scripts/pdf_vector_metadata_projection_readiness.py \
  --scope-report reports/pdf_candidate_scope_report.json \
  --report reports/pdf_vector_metadata_projection_readiness.json
```

## C3 Embedding Text Contract Audit

```bash
python scripts/rag_pdf_embedding_text_contract_audit.py \
  --scope-report reports/pdf_candidate_scope_report.json \
  --report reports/rag_pdf_embedding_text_contract_audit.json
```

## C3 Repair: PDF SearchUnit Surface Backfill

Run dry-run first and review `sample_repairs`. Apply only when the mutation
scope is exactly the C1 PDF scope.

```bash
python scripts/rag_pdf_search_unit_surface_repair.py \
  --scope-report reports/pdf_candidate_scope_report.json \
  --report reports/rag_pdf_search_unit_surface_repair_report.json
```

```bash
python scripts/rag_pdf_search_unit_surface_repair.py \
  --scope-report reports/pdf_candidate_scope_report.json \
  --report reports/rag_pdf_search_unit_surface_repair_report.json \
  --apply
```

## C4 Candidate Indexing

Do not run C4 while C2 or C3 is `FAIL`. The current indexing wrapper does not
fall back to the full72 gold scope for Track C. Consume the C1 PDF scope
report directly so the run stays restricted to the PDF document/source/parser
scope.

Runtime prerequisites:

- Core API must be configured with
  `AIPIPELINE_SEARCH_UNIT_INDEXING_CANDIDATE_INDEX_VERSION=rag-ingestion-v2-pdf-candidate-v1`.
- Worker must write the PDF artifact dir, for example
  `AIPIPELINE_WORKER_RAG_INDEX_DIR=rag-data-pdf-candidate-v1`.
- If the default Core API on port `8080` is still configured for the legacy
  candidate namespace, run a separate local Core API port for C4 and point the
  worker at it with `AIPIPELINE_WORKER_CORE_API_BASE_URL`.

```bash
python scripts/rag_scoped_candidate_indexing.py \
  --scope-report reports/pdf_candidate_scope_report.json \
  --source-file-type PDF \
  --parser-version pdf-extract-v1 \
  --parser-version pdf-extract-v2 \
  --expected-index-version rag-ingestion-v2-pdf-candidate-v1 \
  --artifact-dir rag-data-pdf-candidate-v1 \
  --output reports/pdf_candidate_indexing_report.json
```

To refresh report-only artifact identity after a completed C4 indexing run,
use metadata enrichment instead of re-indexing:

```bash
python scripts/rag_scoped_candidate_indexing.py \
  --scope-report reports/pdf_candidate_scope_report.json \
  --artifact-dir rag-data-pdf-candidate-v1 \
  --enrich-existing-report \
  --output reports/pdf_candidate_indexing_report.json
```

```bash
python scripts/pdf_candidate_embedding_consistency.py \
  --scope-report reports/pdf_candidate_scope_report.json \
  --c2-report reports/pdf_vector_metadata_projection_readiness.json \
  --c3-report reports/rag_pdf_embedding_text_contract_audit.json \
  --indexing-report reports/pdf_candidate_indexing_report.json \
  --expected-index-version rag-ingestion-v2-pdf-candidate-v1 \
  --report reports/pdf_candidate_embedding_consistency_report.json
```

## C5 PDF-only Vector Diagnostic

```bash
python scripts/rag_pdf_vector_diagnostic.py \
  --gold eval/gold_queries_v0.csv \
  --c4-consistency-report reports/pdf_candidate_embedding_consistency_report.json \
  --expected-location-type pdf \
  --index-version rag-ingestion-v2-pdf-candidate-v1 \
  --artifact-dir rag-data-pdf-candidate-v1 \
  --promotion-evidence false \
  --evidence-role diagnostic \
  --report reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json
```

## C6 Failure Breakdown

```bash
python scripts/rag_pdf_vector_quality_breakdown.py \
  --eval-report reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json \
  --gold eval/gold_queries_v0.csv \
  --c2-report reports/pdf_vector_metadata_projection_readiness.json \
  --report reports/rag_pdf_vector_quality_breakdown.json
```

## C7 Gold Policy Review

```bash
python scripts/rag_pdf_gold_policy_review.py \
  --quality-breakdown reports/rag_pdf_vector_quality_breakdown.json \
  --gold eval/gold_queries_v0.csv \
  --c1-report reports/pdf_candidate_scope_report.json \
  --c2-report reports/pdf_vector_metadata_projection_readiness.json \
  --c3-report reports/rag_pdf_embedding_text_contract_audit.json \
  --report reports/rag_pdf_gold_policy_review.json
```

## C8 Case-Level Diagnostic Review

Use these only after C7.1, C6.1, and C5.1 reviewed diagnostics are complete.
These commands are diagnostic-only and must not be treated as promotion
evidence or broad retrieval tuning.

```bash
python scripts/rag_pdf_retrieval_tuning_case_pack.py
```

```bash
python scripts/rag_pdf_c8_case_investigation.py
```

```bash
python scripts/rag_pdf_c8_rank_probe.py
```

```bash
python scripts/rag_pdf_c8_case_level_review.py
```

```bash
python scripts/rag_pdf_c8_case_decision_overlay.py
```

Guardrails for C8.4:

- It writes only `reports/rag_pdf_c8_case_decision_overlay.json`.
- It does not write a candidate CSV manifest.
- It requires the current reviewed manifest hash to match the C8.3 input manifest hash.
- It requires reviewed manifest denominator counts to stay `22/16/6/0` for total/positive/table-deferred/excluded.
- It records query rewrites as overlay proposals only.

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
  ai-worker/tests/test_rag_pdf_search_unit_surface_repair.py \
  ai-worker/tests/test_pdf_candidate_embedding_consistency.py \
  ai-worker/tests/test_rag_pdf_vector_diagnostic.py \
  ai-worker/tests/test_rag_pdf_vector_quality_breakdown.py \
  ai-worker/tests/test_rag_pdf_gold_policy_review.py
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
