# Track A - XLSX Retrieval Diagnostic

이 파일은 기존 링크 호환을 위한 짧은 entrypoint입니다. 완료된 Track A 아카이브는 아래 문서를 기준으로 봅니다.

- [XLSX retrieval diagnostic 완료 기록](rag-ingestion/xlsx-retrieval/README.md)
- [Consolidated RAG ingestion progress](rag-ingestion-progress.md)

## 완료 요약

Track A는 이번 diagnostic pass 기준으로 완료되었습니다.

| 항목 | 결과 |
|---|---|
| Phase status | A0-A6 `COMPLETED` |
| Evidence role | `promotion_evidence=false`, `evidence_role=diagnostic` |
| A5 candidate v2 decision | `SKIP` |
| Candidate v1 mutated | `false` |
| Candidate v2 created | `false` |
| Immutable baseline changed | `false` |
| `rag-data-canary` changed | `false` |
| Final failure breakdown | `MATCHED=35`, `failed_or_degraded_count=0` |
| Final location accuracy | `xlsx_citation_location_accuracy 0.8857 -> 1.0` |
| Hidden leakage | `hidden_content_leakage_count=0` |

강해진 XLSX location 결과는 여전히 diagnostic vector evidence이며 promotion evidence가 아닙니다. 기존 less-explicit manifest `eval/gold_queries_xlsx_v3_positive.csv`는 보존했고, reviewed 변경은 `eval/gold_queries_xlsx_v3_positive_reviewed.csv`에만 있습니다.

## 남은 watch item

`gq_auto_042`는 exact location이 아직 rank 5 이후에 있으므로 location-rank quality watch item으로 남깁니다. Promotion-grade readiness는 Track A candidate-v1 artifact를 mutate하거나 hidden-safe/range-policy guardrail을 약화하지 말고, 별도의 ranking 또는 duplicate-document-version 조사로 진행해야 합니다.
