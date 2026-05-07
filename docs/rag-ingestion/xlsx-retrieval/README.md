# Track A - XLSX Retrieval Diagnostic 완료 기록

## 목적

이 문서는 XLSX retrieval Track A의 완료 아카이브입니다.

Track A는 broad retrieval tuning, reranking, parser expansion, hidden-content mixing, candidate reindexing을 하지 않았습니다. 2026-05-07 strict pre-silver 기준으로 현재 XLSX wrapper의 공식 retrieval/evidence denominator는 human-review projection 23행이며, legacy XLSX v3 35행은 historical diagnostic 비교용으로만 보존합니다.

## 최종 상태

| 항목 | 결과 |
|---|---|
| Phase status | A0-A6 `COMPLETED` |
| Evidence role | `promotion_evidence=false`, `evidence_role=diagnostic` |
| Current XLSX wrapper positive gold | `ai-worker/eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv` |
| Current XLSX wrapper official retrieval/evidence denominator | `23` |
| Current XLSX answer-generation official denominator | `0` |
| Strict pre-silver status | `APPROVED_FOR_XLSX_SILVER_GENERATION_STRICT` |
| Strict pre-silver report | `ai-worker/eval/reports/rag-ingestion/xlsx_pre_silver_risk_closure_20260507.md` |
| Legacy v3 positive reviewed gold | `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv` |
| Archived original positive gold | `archive/results/2026-05-05-eval-query-lineage-cleanup/csv/gold_queries_xlsx_v3_positive.csv` 보존, active denominator 아님 |
| Candidate index version | `rag-ingestion-v2-xlsx-candidate-v1` |
| Candidate v2 decision | `ai-worker/eval/reports/rag-ingestion/xlsx_candidate_v2_decision.json` -> `SKIP` |
| Candidate v1 mutated | `false` |
| Candidate v2 created | `false` |
| Immutable baseline changed | `false` |
| `ai-worker/eval/indexes/rag-data-canary` changed | `false` |
| Hidden content leakage | `0` |

## 현재 Strict Pre-Silver 지표

| Metric | Value | Notes |
|---|---:|---|
| Denominator | `23` | human-review official positive retrieval/evidence projection |
| Hit@10 | `1.0` | live XLSX retrieval smoke |
| MRR@10 | `0.942` | live XLSX retrieval smoke |
| xlsx_citation_location_accuracy | `1.0` | current wrapper namespace/index |
| XLSX answer-generation denominator | `0` | LLM smoke remains diagnostic-only |
| Retrieval repeatability | `stable` | candidate ids and metrics matched repeat run |

## Legacy v3 A0-A6 지표

| Metric | Before | Final reviewed | Notes |
|---|---:|---:|---|
| Hit@10 | `1.0` | `1.0` | 유지 |
| MRR@10 | `0.8857` | `0.8857` | identity-rank metric, location-rank metric 아님 |
| XLSX range overlap@10 | `0.9143` | `1.0` | 개선 |
| XLSX range contains@10 | `0.9143` | `1.0` | 개선 |
| XLSX exact range@10 | `0.8857` | `1.0` | 개선 |
| xlsx_citation_location_accuracy | `0.8857` | `1.0` | 35개 positive 모두 top 10 안에서 exact location 확인 |
| hidden_content_leakage_count | `0` | `0` | hidden-negative diagnostic only |

최종 failure breakdown:

| Field | Value |
|---|---:|
| `query_count` | `35` |
| `failed_or_degraded_count` | `0` |
| `category_counts.MATCHED` | `35` |

## Location-Rank 주의점

이 결과는 promotion pass가 아닙니다. 모든 reviewed positive query가 top 10 안에서 exact XLSX citation location을 찾는다는 점은 증명했지만, top-citation quality는 아직 별도 관리가 필요합니다.

| Metric | Value |
|---|---:|
| location_hit@1 | `0.6` |
| location_hit@3 | `0.8857` |
| location_hit@5 | `0.9714` |
| location_hit@10 | `1.0` |
| location_mrr@10 | `0.7467` |

`gq_auto_042`는 exact location이 여전히 rank 5 이후에 있으므로 watch item으로 남깁니다. 이후 promotion-grade readiness가 필요하면 Track A candidate indexing, exact row policy, hidden-safe constraint를 바꾸지 말고 별도의 ranking 또는 duplicate-document-version 조사를 열어야 합니다.

## Phase 요약

| Phase | Status | Evidence/report | Result |
|---|---|---|---|
| A0 evidence freeze | `COMPLETED` | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_candidate_lineage_before_tuning.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_current_diagnostic_snapshot.json` | baseline/canary hash unchanged, hidden leakage 0 |
| A1 failure case review | `COMPLETED` | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_failure_case_review.json` | 4 degraded rows classified, true retrieval ranking failure 0 |
| A2 query surface review | `COMPLETED` | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_query_surface_patch_plan.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_query_surface_before_after_compare.json` | safe query-only reviewed manifest created |
| A3 range policy review | `COMPLETED` | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_range_policy_review.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_range_policy_dry_run_impact.json` | exact row policy kept |
| A4 formula/date contract review | `COMPLETED` | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_formula_date_contract_review.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_formula_date_surface_presence.json` | expected surface existed; query rewrite, not candidate v2 |
| A5 candidate v2 decision | `COMPLETED` | `ai-worker/eval/reports/rag-ingestion/xlsx_candidate_v2_decision.json` | `SKIP` |
| A6 rerun and compare | `COMPLETED` | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_after_cleanup_metric_compare.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_after_cleanup_failure_breakdown.json` | `MATCHED=35`, degraded 0 |

## Reviewed hard-case 업데이트

| Query id | Reviewed query | Reviewed expected metadata | Result |
|---|---|---|---|
| `gq_xlsx_lookup_002` | `신분당선 2019년 5월 승차총승객수 알려줘.` | `expected_answer_text=신분당선 승차총승객수`, `must_contain_terms=신분당선;승차총승객수` | exact location recovered at `location_rank=3` |
| `gq_auto_041` | `인하요양원 소재지 정보 찾아줘.` | `expected_answer_text=인하요양원 소재지`, `must_contain_terms=인하요양원;소재지` | exact location recovered at `location_rank=3` |

2026-05-07 preflight 이후 XLSX retrieval wrapper의 기본 positive denominator는 human-review official projection인 `ai-worker/eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv`입니다. Legacy v3 reviewed manifest `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv`는 과거 Track A evidence와 비교용으로 보존하지만, wrapper default는 아닙니다.

## Guardrails

1. 모든 Track A report는 diagnostic-only입니다: `promotion_evidence=false`, `evidence_role=diagnostic`.
2. Hidden-negative rows는 leakage diagnostic에만 쓰며 positive Hit@K/MRR에는 섞지 않습니다.
3. `rag-ingestion-v2-xlsx-candidate-v1`과 `ai-worker/eval/indexes/rag-data-xlsx-candidate-v1`은 mutate하지 않았습니다.
4. Candidate v2 namespace는 생성하지 않았습니다.
5. Immutable baseline artifacts, `ai-worker/eval/indexes/rag-data-canary`, full72 promotion-gate inputs는 변경하지 않았습니다.
6. Hybrid search, reranking, parser expansion, answer generation, broad reindex, global range-policy relaxation은 도입하지 않았습니다.

## Evidence 위치

- [Consolidated progress](../../rag-ingestion-progress.md) - 2026-05-05 Track A entries에 user-facing phase merge가 기록되어 있습니다.
- [Phase progress archive](phase-progress.md) - A0-A6 실행 상세 기록입니다.
- [A0 evidence freeze](phases/a0-evidence-freeze.md)
- [A1 failure case review](phases/a1-failure-case-review.md)
- [A2 query surface review](phases/a2-query-surface-review.md)
- [A3 range policy review](phases/a3-range-policy-review.md)
- [A4 formula/date contract review](phases/a4-formula-date-contract-review.md)
- [A5 candidate v2 decision](phases/a5-candidate-v2-decision.md)
- [A6 rerun and compare](phases/a6-rerun-and-compare.md)

## 다음 작업

1. `gq_auto_042`를 location-rank quality watch item으로 유지합니다.
2. Promotion-grade 작업은 Track A diagnostic evidence와 분리합니다.
3. Text/PDF diagnostic tracks는 XLSX Track A를 promotion evidence로 재사용하지 않고 별도 진행합니다.
