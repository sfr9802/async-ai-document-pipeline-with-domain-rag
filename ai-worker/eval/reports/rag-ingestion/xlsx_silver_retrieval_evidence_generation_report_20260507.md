# XLSX Silver Retrieval/Evidence Generation

- Status: `XLSX_SILVER_GENERATION_COMPLETE`
- Scope: XLSX retrieval/evidence silver generation only
- Candidate pool: `702`
- Selected silver rows: `500`
- Dev/Holdout: `350` / `150`
- Rejected rows: `3`
- Route guard: `PASS`
- Denominator guard: `PASS`
- Hidden leakage: `PASS_METADATA_ONLY`

## Answer Shape Distribution

| answer_shape | rows |
|---|---:|
| `AGGREGATION_RESULT` | 54 |
| `CELL_VALUE` | 111 |
| `DATE_NUMBER_FORMAT` | 40 |
| `HEADER_SCHEMA_LOOKUP` | 20 |
| `RANGE_LOCATION_SUMMARY` | 170 |
| `ROW_SUMMARY` | 105 |

## Guardrails

- `promotion_evidence=false` for every row.
- Official XLSX retrieval/evidence denominator remains `23`.
- XLSX answer-generation denominator remains `0`.
- Strict XLSX wrapper namespace: `rag-ingestion-v2-xlsx-candidate-v1`.
- FORMULA_VALUE target redistributed because explicit visible formula evidence was unavailable.

## Artifacts

- `candidates_csv`: `ai-worker/eval/eval_queries/xlsx_silver_retrieval_evidence_candidates_v0.csv`
- `candidates_jsonl`: `ai-worker/eval/eval_queries/xlsx_silver_retrieval_evidence_candidates_v0.jsonl`
- `dev_csv`: `ai-worker/eval/eval_queries/xlsx_silver_retrieval_evidence_dev_v0.csv`
- `dev_jsonl`: `ai-worker/eval/eval_queries/xlsx_silver_retrieval_evidence_dev_v0.jsonl`
- `holdout_csv`: `ai-worker/eval/eval_queries/xlsx_silver_retrieval_evidence_holdout_v0.csv`
- `holdout_jsonl`: `ai-worker/eval/eval_queries/xlsx_silver_retrieval_evidence_holdout_v0.jsonl`
- `manifest`: `ai-worker/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_generation_manifest_v0.json`
- `report_json`: `ai-worker/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_generation_report_20260507.json`
- `report_md`: `ai-worker/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_generation_report_20260507.md`
- `selected_csv`: `ai-worker/eval/eval_queries/xlsx_silver_retrieval_evidence_selected_v0.csv`
- `selected_jsonl`: `ai-worker/eval/eval_queries/xlsx_silver_retrieval_evidence_selected_v0.jsonl`
- `validation_report`: `ai-worker/eval/reports/rag-ingestion/xlsx_silver_retrieval_evidence_validation_report_v0.json`
