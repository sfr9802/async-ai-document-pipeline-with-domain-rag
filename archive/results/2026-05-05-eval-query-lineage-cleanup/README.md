# Eval Query Lineage Cleanup Archive

This archive holds CSV manifests and one-off lineage scripts removed from the
active eval/script directories on 2026-05-05.

These files are preserved for provenance only. Do not use them as default
promotion or baseline-comparison denominators, and do not treat archived scripts
as active eval entrypoints.

Current official diagnostic denominators are recorded in:

```text
ai-worker/eval/eval_queries/official_denominator_registry.json
```

Archived CSVs:

| file | reason |
|---|---|
| `csv/gold_queries_v0.csv` | mixed full72 XLSX/PDF source; split into current Track A XLSX and Track C PDF denominators |
| `csv/gold_queries_xlsx_v1.csv` | intermediate XLSX reviewed subset |
| `csv/gold_queries_xlsx_v2.csv` | intermediate XLSX mixed candidate manifest |
| `csv/gold_queries_xlsx_v3_naturalized.csv` | mixed naturalized candidate manifest with non-positive rows |
| `csv/gold_queries_xlsx_v3_positive.csv` | less-explicit positive manifest superseded by reviewed positives |

Archived scripts:

| file | reason |
|---|---|
| `scripts/pdf_xlsx_candidate_embedding_consistency.py` | mixed full72 candidate consistency, superseded by lane-specific XLSX/PDF diagnostics |
| `scripts/rag_bootstrap_initial_vector_baseline.py` | full72 bootstrap baseline helper, superseded by A/B/C baseline snapshots |
| `scripts/rag_candidate_scope_path_readiness.py` | mixed full72 candidate-scope readiness helper |
| `scripts/rag_full72_docv_scope_classification.py` | full72 document-version classification helper |
| `scripts/rag_full72_vector_quality_breakdown.py` | full72 vector-quality breakdown helper |
| `scripts/rag_gold_query_rebind.py` | old `gold_queries_v0` live rebind helper |
| `scripts/rag_promotion_grade_vector_eval_readiness.py` | full72 promotion-grade preflight tied to archived mixed lineage |
| `scripts/rag_query_evidence_cleanup_plan.py` | old full72 query-evidence cleanup planner |
| `scripts/rag_xlsx_gold_quality_audit.py` | v1/v2 XLSX gold audit helper |
| `scripts/rag_xlsx_gold_v2_builder.py` | generated archived `gold_queries_xlsx_v2.csv` |
| `scripts/rag_xlsx_natural_query_builder.py` | generated archived v3 naturalized/positive CSVs |
| `scripts/rag_xlsx_natural_query_quality_audit.py` | audited archived v3 naturalized CSV |
| `scripts/rag_xlsx_promotion_grade_eval_readiness.py` | v1 promotion-readiness preflight tied to old baseline lineage |
| `scripts/rag_xlsx_query_evidence_review.py` | generated archived `gold_queries_xlsx_v1.csv` |
| `scripts/rag_xlsx_v2_v3_metric_compare.py` | v2-vs-v3 historical metric comparison |
| `scripts/rag_xlsx_v3_vector_quality_breakdown.py` | old v3 positive vector-quality breakdown helper |
