# B2 — Retrieval-Only Diagnostic

## Goal

LLM 호출 전에 retrieval이 expected evidence를 top-k 안에 가져오는지 확인한다.

## Inputs

- `eval/gold_queries_text_e2e_v0.csv`
- `reports/rag_text_backend_identity_report.json`
- `retrieval_backend`
- `retrieval_backend_identity`
- `top_k`

## Work Items

1. gold query별 top-k retrieval을 실행한다.
2. expected source/chunk hit를 분리해 기록한다.
3. result empty, wrong source top1, path mixing을 count한다.
4. retrieval failure를 answer failure와 섞지 않고 별도 taxonomy로 둔다.
5. fixture backend이면 report에 smoke-only marker를 남긴다.

## Metrics

| Metric | 의미 |
|---|---|
| `Hit@1/3/5/10` | expected source 또는 chunk가 top-k 안에 있는지 |
| `MRR@10` | expected evidence rank 품질 |
| `source_recall@10` | source 단위 recall |
| `chunk_recall@10` | chunk 단위 recall |
| `result_empty_count` | 검색 결과 없음 |
| `wrong_source_top1_count` | top1이 expected source가 아닌 경우 |
| `path_mixing_count` | TEXT-only 평가에 PDF/XLSX/unknown이 섞인 경우 |

## Output

`reports/rag_text_retrieval_diagnostic_report.json`

필수 fields:

```json
{
  "retrieval_backend": "...",
  "retrieval_backend_identity": "...",
  "gold_csv": "eval/gold_queries_text_e2e_v0.csv",
  "gold_csv_sha256": "...",
  "top_k": 10,
  "promotion_evidence": false,
  "evidence_role": "diagnostic",
  "metrics": {},
  "query_results": []
}
```

## Done Criteria

```text
query_results[] exists
Hit@K and MRR@10 are calculated
source/chunk hit is separated where ids are available
failure_reason exists for miss cases
retrieval backend identity is included
promotion_evidence=false
```

## Verification Command

```bash
python scripts/rag_text_retrieval_diagnostic.py \
  --gold eval/gold_queries_text_e2e_v0.csv \
  --backend library_search \
  --source-file-type TEXT \
  --top-k 10 \
  --report reports/rag_text_retrieval_diagnostic_report.json
```
