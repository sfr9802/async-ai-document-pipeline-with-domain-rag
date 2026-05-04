# Archive Manifest

Generated during the 2026-05-04 preservation cleanup. This manifest records every file moved into `archive/` during this cleanup and also records blocked move attempts.

## Scope Rules

- No files were deleted.
- Operating code under `core-api/`, `ai-worker/app/`, `ai-worker/ai_worker/`, and `ai-worker/tests/` was not moved.
- Test-blocking and workflow-blocking inputs such as `eval/gold_queries_v0.csv`, `samples/*.json`, `datasets/**`, `rag-data-canary/`, `local-storage/`, and `rag-data/` were left in place.
- `imported_by_production` means direct import/reference from protected runtime code, not documentation references or script default output paths.

## Categories

| Category | Meaning | Reuse Rule |
|---|---|---|
| `result-log` | Runtime, build, test, or script log output | Use only as historical evidence; regenerate with active commands for current proof. |
| `generated-report` | RAG smoke/eval/readiness report JSON | Treat as historical provenance, not active promotion evidence. |
| `result-json` | Generated metrics, baseline, descriptor, or manifest JSON | Review current scripts before relying on it. |
| `result-csv` | Generated CSV output | Use as historical output only; active gold CSV stays outside archive. |
| `eval-dry-run` | Dry-run eval/gold output | Historical dry-run only; not an active fixture. |
| `blocked-open-handle` | Intended move was blocked by a live file handle | Left in place and should be retried only after the owning process exits. |

## Move Records

| Original Path | Archive Path | Category | imported_by_production | risk_level | Reason |
|---|---|---|---|---|---|
| `reports/strict_B_hardened_xlsx_canary_gold.csv` | `archive/results/2026-05-04-root-rag-reports/csv/strict_B_hardened_xlsx_canary_gold.csv` | result-csv | no | low | Generated canary/eval CSV output; active gold input remains in eval/. |
| `reports/a5_c4_promote_time_hard_block_validation.json` | `archive/results/2026-05-04-root-rag-reports/json/a5_c4_promote_time_hard_block_validation.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/full72_missing_xlsx_care_retry_manifest.json` | `archive/results/2026-05-04-root-rag-reports/json/full72_missing_xlsx_care_retry_manifest.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/full72_missing_xlsx_reimport_manifest.json` | `archive/results/2026-05-04-root-rag-reports/json/full72_missing_xlsx_reimport_manifest.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/initial_baseline_bootstrap_proposal.json` | `archive/results/2026-05-04-root-rag-reports/json/initial_baseline_bootstrap_proposal.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/initial_immutable_vector_baseline_descriptor.json` | `archive/results/2026-05-04-root-rag-reports/json/initial_immutable_vector_baseline_descriptor.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/rag_ingestion_a5_c_report_metrics.json` | `archive/results/2026-05-04-root-rag-reports/json/rag_ingestion_a5_c_report_metrics.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/rag_ingestion_a5_c2_canonical_metrics.json` | `archive/results/2026-05-04-root-rag-reports/json/rag_ingestion_a5_c2_canonical_metrics.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/rag_ingestion_a5_promotion_gate_baseline.json` | `archive/results/2026-05-04-root-rag-reports/json/rag_ingestion_a5_promotion_gate_baseline.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/rag_ingestion_a5_promotion_gate_metrics.json` | `archive/results/2026-05-04-root-rag-reports/json/rag_ingestion_a5_promotion_gate_metrics.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/rag_ingestion_d_vector_canonical_metrics.json` | `archive/results/2026-05-04-root-rag-reports/json/rag_ingestion_d_vector_canonical_metrics.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/rag_ingestion_promotion_gate_baseline.json` | `archive/results/2026-05-04-root-rag-reports/json/rag_ingestion_promotion_gate_baseline.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/rag_ingestion_promotion_gate_metrics.json` | `archive/results/2026-05-04-root-rag-reports/json/rag_ingestion_promotion_gate_metrics.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/rag_retrieval_full72_vector_quality_breakdown.json` | `archive/results/2026-05-04-root-rag-reports/json/rag_retrieval_full72_vector_quality_breakdown.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/scoped_candidate_indexing_report.dry-run.json` | `archive/results/2026-05-04-root-rag-reports/json/scoped_candidate_indexing_report.dry-run.json` | result-json | no | low | Generated metrics/baseline/manifest JSON archived as provenance. |
| `reports/ai-worker-full72-reimport.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-full72-reimport.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-full72-reimport.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-full72-reimport.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1b.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1b.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1b.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1b.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1d.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1d.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1d.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1d.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1e.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1e.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1e.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1e.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1f.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1f.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1f.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1f.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1g.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1g.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1g.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1g.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1h.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1h.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1h.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1h.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1i.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1i.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1i.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1i.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1j.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1j.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live-p1j.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live-p1j.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-live.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-live.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/ai-worker-preb.log` | `archive/results/2026-05-04-root-rag-reports/logs/ai-worker-preb.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-canary.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-canary.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live-p1.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live-p1.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live-p1.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live-p1.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live-p1b.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live-p1b.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live-p1b.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live-p1b.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live-p1c.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live-p1c.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live-p1c.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live-p1c.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live-p1d.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live-p1d.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live-p1d.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live-p1d.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-live.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-live.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-preb-rerun.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-preb-rerun.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/core-api-preb.log` | `archive/results/2026-05-04-root-rag-reports/logs/core-api-preb.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/git_diff_check_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/git_diff_check_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/mvn_compile_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/mvn_compile_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/mvn_targeted_tests_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/mvn_targeted_tests_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/py_compile_final_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/py_compile_final_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/py_compile_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/py_compile_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/pytest_pdf_ocr_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/pytest_pdf_ocr_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/pytest_targeted_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/pytest_targeted_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_build_promotion_gate_metrics_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_build_promotion_gate_metrics_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_gold_query_rebind_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_gold_query_rebind_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_ingestion_promotion_gate_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_ingestion_promotion_gate_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_ingestion_sample_batch_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_ingestion_sample_batch_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_ingestion_smoke_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_ingestion_smoke_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_pdf_ingestion_sample_batch_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_pdf_ingestion_sample_batch_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_pdf_ingestion_smoke_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_pdf_ingestion_smoke_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_pdf_ocr_fallback_smoke_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_pdf_ocr_fallback_smoke_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_retrieval_eval_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_retrieval_eval_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/rag_retrieval_eval_validate_stdout.log` | `archive/results/2026-05-04-root-rag-reports/logs/rag_retrieval_eval_validate_stdout.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/runtime-logs/ai-worker-a5-20260504083453.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/runtime-logs/ai-worker-a5-20260504083453.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/runtime-logs/ai-worker-a5-20260504083453.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/runtime-logs/ai-worker-a5-20260504083453.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/runtime-logs/ai-worker-a5-20260504083525.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/runtime-logs/ai-worker-a5-20260504083525.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/runtime-logs/ai-worker-a5-20260504083525.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/runtime-logs/ai-worker-a5-20260504083525.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/runtime-logs/core-api-a5-20260504083424.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/runtime-logs/core-api-a5-20260504083424.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/runtime-logs/core-api-a5.err.log` | `archive/results/2026-05-04-root-rag-reports/logs/runtime-logs/core-api-a5.err.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/runtime-logs/core-api-a5.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/runtime-logs/core-api-a5.out.log` | result-log | no | low | Generated runtime/test/build log; not imported by production or tests. |
| `reports/a5_c1_sample_batch_indexing_readiness.json` | `archive/results/2026-05-04-root-rag-reports/reports/a5_c1_sample_batch_indexing_readiness.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/a5_c2_source_qualified_report_contract_readiness.json` | `archive/results/2026-05-04-root-rag-reports/reports/a5_c2_source_qualified_report_contract_readiness.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/a5_c3_immutable_baseline_readiness.json` | `archive/results/2026-05-04-root-rag-reports/reports/a5_c3_immutable_baseline_readiness.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/a5_d_vector_backend_readiness.json` | `archive/results/2026-05-04-root-rag-reports/reports/a5_d_vector_backend_readiness.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/a5_hardened_xlsx_canary_consistency_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/a5_hardened_xlsx_canary_consistency_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/candidate_namespace_cleanup_upsert_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/candidate_namespace_cleanup_upsert_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/full72_docv_scope_classification_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/full72_docv_scope_classification_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/full72_missing_xlsx_care_retry_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/full72_missing_xlsx_care_retry_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/full72_missing_xlsx_reimport_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/full72_missing_xlsx_reimport_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/initial_baseline_bootstrap_readiness.json` | `archive/results/2026-05-04-root-rag-reports/reports/initial_baseline_bootstrap_readiness.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/missing_scope_docv_resolution_plan.json` | `archive/results/2026-05-04-root-rag-reports/reports/missing_scope_docv_resolution_plan.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/pdf_xlsx_candidate_embedding_consistency_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/pdf_xlsx_candidate_embedding_consistency_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/preb_pdf_smoke_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/preb_pdf_smoke_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/preb_xlsx_smoke_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/preb_xlsx_smoke_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_candidate_scope_path_readiness.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_candidate_scope_path_readiness.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_gold_query_rebind_dry_run_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_gold_query_rebind_dry_run_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_gold_query_rebind_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_gold_query_rebind_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_ingestion_a5_promotion_gate_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_ingestion_a5_promotion_gate_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_ingestion_hardened_xlsx_c2_reimport_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_ingestion_hardened_xlsx_c2_reimport_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_ingestion_hardened_xlsx_canary_reimport_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_ingestion_hardened_xlsx_canary_reimport_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_ingestion_promotion_gate_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_ingestion_promotion_gate_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_ingestion_sample_batch_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_ingestion_sample_batch_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_ingestion_smoke_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_ingestion_smoke_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_path_separation_readiness.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_path_separation_readiness.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_pdf_ingestion_sample_batch_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_pdf_ingestion_sample_batch_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_pdf_ingestion_smoke_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_pdf_ingestion_smoke_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_pdf_ocr_fallback_smoke_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_pdf_ocr_fallback_smoke_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_retrieval_eval_dry_gold_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_retrieval_eval_dry_gold_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_retrieval_eval_full72_vector_diagnostic_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_retrieval_eval_full72_vector_diagnostic_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_retrieval_eval_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_retrieval_eval_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/rag_retrieval_eval_validate_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/rag_retrieval_eval_validate_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/scoped_candidate_indexing_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/scoped_candidate_indexing_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/scoped_search_unit_text_repair_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/scoped_search_unit_text_repair_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/strict_B_hardened_xlsx_canary_gold_rebind_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/strict_B_hardened_xlsx_canary_gold_rebind_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/strict_B_hardened_xlsx_canary_retrieval_eval_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/strict_B_hardened_xlsx_canary_retrieval_eval_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `reports/strict_D_hardened_xlsx_canary_vector_eval_report.json` | `archive/results/2026-05-04-root-rag-reports/reports/strict_D_hardened_xlsx_canary_vector_eval_report.json` | generated-report | no | low | Generated RAG smoke/eval/readiness report archived as provenance. |
| `eval/gold_queries_v0.dry-run.csv` | `archive/experiments/evaluation/2026-05-04-root-eval-dry-runs/gold_queries_v0.dry-run.csv` | eval-dry-run | no | low | Dry-run gold query output; active `eval/gold_queries_v0.csv` is test-blocking and remains in place. |
| `reports/runtime-logs/core-api-a5-20260504083424.out.log` | `archive/results/2026-05-04-root-rag-reports/logs/runtime-logs/core-api-a5-20260504083424.out.log` | result-log | no | low | Generated runtime log; initial move was blocked by an open handle, then moved after the handle was released. |

## Explicitly Kept In Place

| Path | Reason |
|---|---|
| `ai-worker/app/**` | FastAPI/worker runtime code. |
| `ai-worker/ai_worker/**` | Operational SearchUnit indexing package and golden-retrieval helpers. |
| `ai-worker/eval/**` | Active/legacy eval harness already has internal organization and import paths. |
| `core-api/**` | Spring Boot API, DB migrations, catalog/indexing services, and tests. |
| `scripts/*.py` | Several root scripts are directly loaded by tests or used as active operational helpers. |
| `eval/gold_queries_v0.csv` | Hard test dependency and active eval input. |
| `samples/*.json` | Active smoke/sample manifests; at least one is directly checked by tests. |
| `datasets/**` | Source datasets and fixtures, including KoViDoRe and XLSX canary inputs. |
| `rag-data-canary/` | Current generated vector/canary artifact; workflow-blocking, not production-imported. |
| `local-storage/` and `rag-data/` | Runtime default paths in configuration. |
