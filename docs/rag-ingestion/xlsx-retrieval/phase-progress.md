# Track A - XLSX Retrieval Phase Progress

이 파일은 Track A phase별 진행 내역을 임시로 기록하는 작업 로그입니다. 작성 형식은 `docs/rag-ingestion-progress.md`의 날짜별 기록을 따르되, 범위를 XLSX retrieval Track A로 제한합니다.

Track A가 완료되면 이 파일의 확정 내용을 `docs/rag-ingestion-progress.md`에 합병하고, 이 임시 로그는 삭제하거나 archive note만 남깁니다.

## 기록 원칙

1. phase별 완료 여부를 evidence와 함께 기록합니다.
2. `promotion_evidence=false`, `evidence_role=diagnostic` 여부를 매 entry마다 확인합니다.
3. hidden-negative leakage는 positive metric과 분리해서 적습니다.
4. candidate v1 artifact를 mutate했는지 여부를 명시합니다.
5. immutable baseline, `ai-worker/eval/indexes/rag-data-canary`, full72 promotion gate 입력 변경 여부를 명시합니다.
6. 완료/보류/차단 상태를 구분하고, 차단 사유는 다음 action과 함께 남깁니다.

## Phase Status

| Phase | Status | Last update | Evidence/report | Notes |
|---|---|---|---|---|
| A0 evidence freeze | `COMPLETED` | 2026-05-05 | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_candidate_lineage_before_tuning.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_current_diagnostic_snapshot.json` | current diagnostic evidence frozen; guardrail hash/status checks pass; positive row count 35; hidden leakage 0 |
| A1 failure case review | `COMPLETED` | 2026-05-05 | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_failure_case_review.json` | 4 degraded rows reviewed; true retrieval ranking failure count 0; unreviewed degraded ids now fail closed |
| A2 query surface review | `COMPLETED` | 2026-05-05 | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_query_surface_patch_plan.json`, `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_query_surface_before_after_compare.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_remaining_hard_case_probe.json` | semantic-anchor probe recovered `gq_xlsx_lookup_002`; `gq_auto_042` remains recovered |
| A3 range policy review | `COMPLETED` | 2026-05-05 | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_range_policy_review.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_range_policy_dry_run_impact.json` | exact policy kept; sheet_summary contains/overlap is metric inflation risk |
| A4 formula/date contract review | `COMPLETED` | 2026-05-05 | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_formula_date_contract_review.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_formula_date_surface_presence.json` | expected surface exists in exact SearchUnit; next action was query rewrite, not candidate v2 |
| A5 candidate v2 decision | `COMPLETED` | 2026-05-05 | `ai-worker/eval/reports/rag-ingestion/xlsx_candidate_v2_decision.json` | `SKIP`; A2/A4 were query-only and A3 kept policy |
| A6 rerun and compare | `COMPLETED` | 2026-05-05 | `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_after_cleanup_metric_compare.json`, `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_after_cleanup_failure_breakdown.json` | diagnostic rerun completed; location accuracy `0.8857 -> 1.0`; `MATCHED=35`; hidden leakage 0 |

## Current Baseline Snapshot

This section summarizes the existing evidence that motivated the phase split. It is not a completed A0 freeze report.

| 항목 | 현재 값 |
|---|---:|
| Positive gold | `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive.csv` |
| Positive row count | `35` |
| Candidate index version | `rag-ingestion-v2-xlsx-candidate-v1` |
| Vector artifact dir | `ai-worker/eval/indexes/rag-data-xlsx-candidate-v1` |
| Hit@10 | `1.0` |
| MRR@10 | `0.8857` |
| XLSX range overlap@10 | `0.9143` |
| XLSX range contains@10 | `0.9143` |
| XLSX exact range@10 | `0.8857` |
| XLSX citation location accuracy | `0.8857` |
| Hidden content leakage count | `0` |

Known degraded rows:

| Query id | Category | Target phase |
|---|---|---|
| `gq_xlsx_lookup_002` | `QUERY_NATURALIZATION_DRIFT` | A2 |
| `gq_auto_042` | `QUERY_NATURALIZATION_DRIFT` | A2 |
| `gq_auto_041` | `RANGE_POLICY_MISMATCH` | A3 |
| `gq_xlsx_date_number_format_001` | `FORMULA_DATE_CONTRACT_MISMATCH` | A4 |

## Progress Log

### 2026-05-05 - Remaining hard-case probe and fail-closed script gates

#### Scope

- Continue after A6 because two cases remained weak or unresolved in the first cleanup pass.
- Keep the work query/gold-review only; no candidate v2, global policy relaxation, broad reindex, baseline/canary mutation, hidden-negative mixing, reranking, or parser change.
- Add contract checks so phase scripts cannot report completion on missing evidence or invalid comparison inputs.

#### Changes

- Added semantic-anchor hard-case probe:
  - `scripts/rag_xlsx_remaining_hard_case_probe.py`.
- Hardened Track A phase scripts:
  - `scripts/rag_xlsx_current_diagnostic_snapshot.py` now checks report status, hidden leakage, candidate artifact presence/version, and baseline/canary hashes before `COMPLETED`.
  - `scripts/rag_xlsx_v3_failure_case_review.py` now blocks unreviewed degraded ids and duplicate query ids.
  - `scripts/rag_xlsx_formula_date_contract_phase_review.py` now requires DB surface evidence for the expected `document_version_id`, blocks missing reviewed-gold updates, and redacts URI/key-value DSNs.
  - `scripts/rag_xlsx_candidate_v2_decision.py` now blocks failed inputs and does not hard-code `SKIP` when candidate v2 is required.
  - `scripts/rag_xlsx_after_cleanup_compare.py` now validates before/after gold and report query-id contracts, duplicate/blank report rows, required finite metrics, hidden leakage, promotion flags, candidate decision status, and location-rank metrics.
  - `scripts/rag_xlsx_remaining_hard_case_probe.py` now fails closed when semantic-anchor metadata is missing and uses reviewed metadata overrides for accepted hard-case labels.
- Added focused regression tests:
  - `ai-worker/tests/test_rag_xlsx_track_a_scripts.py`.

#### Evidence

- `gq_xlsx_lookup_002`:
  - Rejected broad `신분당선` because it missed semantic anchor term `승차총승객수`.
  - Applied safe query-only rewrite: `신분당선 2019년 5월 승차총승객수 알려줘.`.
  - Exact location recovered at `location_rank=3`.
- `gq_auto_041`:
  - Kept exact row policy; broad `sheet_summary A1:J30761` is still not accepted as a row citation.
  - Applied corpus-backed rewrite: `인하요양원 소재지 정보 찾아줘.`.
  - Updated reviewed metadata to `expected_answer_text=인하요양원 소재지`, `must_contain_terms=인하요양원;소재지`.
  - Exact location recovered at `location_rank=3`.
- Final reviewed failure breakdown:
  - `failed_or_degraded_count=0`.
  - `category_counts.MATCHED=35`.

#### Metrics

| Metric | Before | Final reviewed | Notes |
|---|---:|---:|---|
| Hit@10 | `1.0` | `1.0` | maintained |
| MRR@10 | `0.8857` | `0.8857` | identity-rank metric, not location-rank metric |
| XLSX range overlap@10 | `0.9143` | `1.0` | improved |
| XLSX range contains@10 | `0.9143` | `1.0` | improved |
| XLSX exact range@10 | `0.8857` | `1.0` | improved |
| xlsx_citation_location_accuracy | `0.8857` | `1.0` | all 35 rows have exact location within top 10 |
| location_hit@1 | - | `0.6` | diagnostic-only location-rank decomposition |
| location_hit@3 | - | `0.8857` | diagnostic-only location-rank decomposition |
| location_hit@5 | - | `0.9714` | only `gq_auto_042` remains after rank 5 |
| location_hit@10 | - | `1.0` | all exact locations found by rank 10 |
| location_mrr@10 | - | `0.7467` | diagnostic-only; shows top-citation quality is weaker than Hit@10 |
| hidden_content_leakage_count | `0` | `0` | hidden-negative only |

#### Validation

- Commands:
  - `python -m py_compile scripts\rag_xlsx_current_diagnostic_snapshot.py scripts\rag_xlsx_v3_failure_case_review.py scripts\rag_xlsx_formula_date_contract_phase_review.py scripts\rag_xlsx_candidate_v2_decision.py scripts\rag_xlsx_after_cleanup_compare.py scripts\rag_xlsx_remaining_hard_case_probe.py`.
  - `python scripts\rag_xlsx_remaining_hard_case_probe.py --apply-updates`.
  - `python scripts\rag_xlsx_current_diagnostic_snapshot.py`.
  - `python scripts\rag_xlsx_v3_failure_case_review.py`.
  - `python scripts\rag_xlsx_formula_date_contract_phase_review.py`.
  - `python scripts\rag_xlsx_candidate_v2_decision.py`.
  - `python scripts\rag_xlsx_retrieval_performance_diagnostic.py --positive-gold eval\gold_queries_xlsx_v3_positive_reviewed.csv --report reports\rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json --summary reports\rag_xlsx_v3_positive_reviewed_retrieval_performance_summary.json --hidden-report reports\rag_xlsx_v3_positive_reviewed_hidden_negative_leakage_diagnostic.json`.
  - `python scripts\rag_xlsx_v3_failure_breakdown.py --v3-report reports\rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json --v3-gold eval\gold_queries_xlsx_v3_positive_reviewed.csv --output reports\rag_xlsx_v3_after_cleanup_failure_breakdown.json`.
  - `python scripts\rag_xlsx_after_cleanup_compare.py`.
  - `python -m pytest -q -p no:cacheprovider ai-worker\tests\test_rag_xlsx_track_a_scripts.py`.
- Results:
  - Track A script tests: `13 passed`.
  - A6 compare status: `COMPLETED`, blockers empty.
  - Hidden leakage remains `0`.

#### Status

- Track A is diagnostically complete for this pass.
- This is still diagnostic evidence only, not promotion evidence. Location-rank decomposition shows top-citation quality remains weaker than aggregate Hit@10/MRR.

#### Next

1. Treat `gq_auto_042` as the remaining location-rank quality watch item because its exact location is still after rank 5.
2. If promotion-grade readiness is required later, open a separate ranking/duplicate-document-version investigation instead of changing Track A candidate indexing, exact row policy, or hidden-safe constraints.

### 2026-05-05 - A2-A6 reviewed query cleanup and final diagnostic compare

#### Scope

- Execute Track A phases A2 through A6 after A1 evidence was fixed.
- Keep all changes diagnostic-only and candidate-v1 based.
- Do not create candidate v2, mutate `ai-worker/eval/indexes/rag-data-xlsx-candidate-v1`, run broad reindexing, or change immutable baseline/canary artifacts.

#### Changes

- Added A2 query surface review script:
  - `scripts/rag_xlsx_query_surface_review.py`.
- Added A3 range policy review script:
  - `scripts/rag_xlsx_range_policy_review.py`.
- Added A4 formula/date phase review script:
  - `scripts/rag_xlsx_formula_date_contract_phase_review.py`.
- Added A5 decision script:
  - `scripts/rag_xlsx_candidate_v2_decision.py`.
- Added A6 metric compare script:
  - `scripts/rag_xlsx_after_cleanup_compare.py`.
- Generated/updated reviewed manifest and diagnostic reports:
  - `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_query_surface_patch_plan.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_positive_reviewed_retrieval_performance_summary.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_positive_reviewed_hidden_negative_leakage_diagnostic.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_query_surface_before_after_compare.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_range_policy_review.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_range_policy_dry_run_impact.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_formula_date_contract_review.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_formula_date_surface_presence.json`.
  - `ai-worker/eval/reports/rag-ingestion/xlsx_candidate_v2_decision.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_after_cleanup_metric_compare.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_after_cleanup_failure_breakdown.json`.

#### Evidence

- A2 reviewed query patches:
  - `gq_xlsx_lookup_002`: `신분당선 어디쯤 있어?` -> `신분당선 승차총승객수 찾아줘.`
  - `gq_auto_042`: `축복전문요양원 행 찾아줘.` -> `축복전문요양원 장기요양기관 정보 찾아줘.`
- A2 result:
  - Query quality audit passed.
  - `gq_auto_042` recovered exact location match.
  - `gq_xlsx_lookup_002` remains a realistic hard case.
- A3 decision:
  - `gq_auto_041` keeps `EXACT_RANGE`.
  - Accepting rank-2 `sheet_summary` `A1:J30761` as contains/overlap would raise metric from `31/35` to `32/35`, but it is a high inflation risk for a row-level query.
- A4 decision:
  - `gq_xlsx_date_number_format_001` expected surface is `DATE_FORMATTED_VALUE`.
  - Read-only DB/SearchUnit evidence found the exact `A2:J51` row group contains `2008-06-25`, `지정일자`, and `청운노인요양원` in embedding/bm25 text.
  - The next action is `QUERY_REWRITE`, not `EMBEDDING_CONTRACT_CHANGE`.
  - Reviewed query became `청운노인요양원 지정일자 찾아줘.` and recovered location match.
- A5 decision:
  - `decision=SKIP`.
  - Reason: `QUERY_ONLY`, `RANGE_POLICY_ONLY`.
  - Candidate v1 mutated: `false`.
- A6 result:
  - After-cleanup degraded query ids: `gq_xlsx_lookup_002`, `gq_auto_041`.
  - After-cleanup category counts: `MATCHED=33`, `QUERY_NATURALIZATION_DRIFT=1`, `RANGE_POLICY_MISMATCH=1`.
  - This initial A6 pass is superseded by the later remaining hard-case probe entry above.

#### Metrics

| Metric | Before | After | Notes |
|---|---:|---:|---|
| Hit@10 | `1.0` | `1.0` | maintained |
| MRR@10 | `0.8857` | `0.8857` | maintained |
| XLSX range overlap@10 | `0.9143` | `0.9714` | improved |
| XLSX range contains@10 | `0.9143` | `0.9714` | improved |
| XLSX exact range@10 | `0.8857` | `0.9429` | improved |
| xlsx_citation_location_accuracy | `0.8857` | `0.9429` | reached A6 second target |
| hidden_content_leakage_count | `0` | `0` | hidden-negative only |

#### Guardrails

- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- Candidate v1 mutated: `false`.
- Candidate v2 created: `false`.
- Immutable baseline changed: `false`.
- `ai-worker/eval/indexes/rag-data-canary` changed: `false`.
- Hidden-negative rows remain separate from positive retrieval metrics.
- No hybrid search, reranking, parser expansion, answer generation, broad reindex, or global range-policy relaxation was introduced.

#### Validation

- Commands:
  - `python -m py_compile scripts\rag_xlsx_query_surface_review.py scripts\rag_xlsx_range_policy_review.py scripts\rag_xlsx_formula_date_contract_phase_review.py`.
  - `python -m py_compile scripts\rag_xlsx_candidate_v2_decision.py scripts\rag_xlsx_after_cleanup_compare.py scripts\rag_xlsx_v3_failure_breakdown.py`.
  - `python scripts\rag_xlsx_query_surface_review.py`.
  - `python scripts\rag_xlsx_range_policy_review.py`.
  - `python scripts\rag_xlsx_formula_date_contract_phase_review.py`.
  - `python scripts\rag_xlsx_retrieval_performance_diagnostic.py --positive-gold eval\gold_queries_xlsx_v3_positive_reviewed.csv --report reports\rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json --summary reports\rag_xlsx_v3_positive_reviewed_retrieval_performance_summary.json --hidden-report reports\rag_xlsx_v3_positive_reviewed_hidden_negative_leakage_diagnostic.json`.
  - `python scripts\rag_xlsx_candidate_v2_decision.py`.
  - `python scripts\rag_xlsx_v3_failure_breakdown.py --v3-report reports\rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json --v3-gold eval\gold_queries_xlsx_v3_positive_reviewed.csv --output reports\rag_xlsx_v3_after_cleanup_failure_breakdown.json`.
  - `python scripts\rag_xlsx_after_cleanup_compare.py`.
- Results:
  - Reviewed gold validation passed with `row_count=35`.
  - Positive diagnostic completed.
  - Hidden-negative diagnostic completed with `hidden_content_leakage_count=0`.
  - A5 candidate v2 decision completed with `decision=SKIP`.
  - A6 completion criteria passed: `promotion_evidence=false`, `evidence_role=diagnostic`, `candidate_v1_mutated=false`.

#### Status

- Phase status: `COMPLETED` for A2, A3, A4, A5, and A6.
- This initial A6 pass was followed by the remaining hard-case probe entry above.

#### Next

1. Superseded by the remaining hard-case probe entry above.

### 2026-05-05 - A0/A1 evidence freeze and failure case review

#### Scope

- Execute Track A A0 and A1 only.
- Generate reproducible scripts for current XLSX v3 diagnostic snapshot and degraded-row review.
- Keep the work diagnostic-only; do not run query rewrite, range-policy edits, formula/date contract edits, candidate v2 indexing, baseline promotion, or broad reindexing.

#### Changes

- Added A0 snapshot script:
  - `scripts/rag_xlsx_current_diagnostic_snapshot.py`.
- Added A1 review script:
  - `scripts/rag_xlsx_v3_failure_case_review.py`.
- Generated A0 reports:
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_candidate_lineage_before_tuning.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_current_diagnostic_snapshot.json`.
- Generated A1 report:
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_failure_case_review.json`.

#### Evidence

- A0 lineage/snapshot inputs:
  - `ai-worker/eval/eval_queries/gold_queries_xlsx_v3_positive.csv`.
  - `ai-worker/eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_vector_diagnostic_report.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_retrieval_performance_summary.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_failure_breakdown.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_hidden_negative_leakage_diagnostic.json`.
- A0 completion markers:
  - `positive_row_count=35`.
  - `candidate_index_version=rag-ingestion-v2-xlsx-candidate-v1`.
  - `retrieval_backend=vector`.
  - `hidden_content_leakage_count=0`.
  - `baseline_hash_unchanged=true`.
  - `rag_data_canary_hash_unchanged=true`.
- A1 reviewed degraded rows:
  - `gq_xlsx_lookup_002`: `QUERY_NATURALIZATION_DRIFT`, next `A2_QUERY_SURFACE_REVIEW`.
  - `gq_auto_042`: `QUERY_NATURALIZATION_DRIFT`, next `A2_QUERY_SURFACE_REVIEW`.
  - `gq_auto_041`: `RANGE_POLICY_MISMATCH`, next `A3_RANGE_POLICY_REVIEW`.
  - `gq_xlsx_date_number_format_001`: `FORMULA_DATE_CONTRACT_MISMATCH`, next `A4_FORMULA_DATE_CONTRACT_REVIEW`.
- A1 completion markers:
  - `reviewed_degraded_query_count=4`.
  - `unknown_category_count=0`.
  - `unclassified_next_action_count=0`.
  - `true_retrieval_ranking_failure_count=0`.

#### Metrics

| Metric | Before | After | Notes |
|---|---:|---:|---|
| Hit@10 | `1.0` | `1.0` | snapshot only |
| MRR@10 | `0.8857` | `0.8857` | snapshot only |
| xlsx_citation_location_accuracy | `0.8857` | `0.8857` | snapshot only |
| hidden_content_leakage_count | `0` | `0` | hidden-negative only |

#### Guardrails

- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- Candidate v1 mutated: `false`.
- Immutable baseline changed: `false`.
- `ai-worker/eval/indexes/rag-data-canary` changed: `false`.
- Hidden-negative rows remain separate from positive retrieval metrics.

#### Validation

- Commands:
  - `python -m py_compile scripts\rag_xlsx_current_diagnostic_snapshot.py scripts\rag_xlsx_v3_failure_case_review.py`.
  - `python scripts\rag_xlsx_current_diagnostic_snapshot.py`.
  - `python scripts\rag_xlsx_v3_failure_case_review.py`.
- Results:
  - py_compile completed successfully.
  - A0 generated lineage and snapshot reports with `positive_row_count=35` and `degraded_query_count=4`.
  - A1 generated failure-case review with `reviewed_degraded_query_count=4`, `unknown_category_count=0`, and `true_retrieval_ranking_failure_count=0`.

#### Status

- Phase status: `COMPLETED` for A0 and A1.
- A2/A3/A4 are ready to start from fixed A1 evidence, but no A2/A3/A4 changes were made in this entry.

#### Next

1. Execute A2 query surface review for `gq_xlsx_lookup_002` and `gq_auto_042`.
2. Execute A3 range policy review for `gq_auto_041`.
3. Execute A4 formula/date contract review for `gq_xlsx_date_number_format_001`.
4. Run A5 only if A2-A4 prove candidate v2 is necessary.

### 2026-05-05 - Track A phase documentation split

#### Scope

- Split the original Track A XLSX retrieval improvement plan into phase-specific docs under `docs/rag-ingestion/xlsx-retrieval/`.
- Add this temporary phase progress log for later merge into `docs/rag-ingestion-progress.md`.
- Keep the work docs-only; no script, eval, report, baseline, or vector artifact changes are part of this entry.

#### Changes

- Added Track A overview:
  - `docs/rag-ingestion/xlsx-retrieval/README.md`.
- Added phase docs:
  - `docs/rag-ingestion/xlsx-retrieval/phases/a0-evidence-freeze.md`.
  - `docs/rag-ingestion/xlsx-retrieval/phases/a1-failure-case-review.md`.
  - `docs/rag-ingestion/xlsx-retrieval/phases/a2-query-surface-review.md`.
  - `docs/rag-ingestion/xlsx-retrieval/phases/a3-range-policy-review.md`.
  - `docs/rag-ingestion/xlsx-retrieval/phases/a4-formula-date-contract-review.md`.
  - `docs/rag-ingestion/xlsx-retrieval/phases/a5-candidate-v2-decision.md`.
  - `docs/rag-ingestion/xlsx-retrieval/phases/a6-rerun-and-compare.md`.
- Updated `docs/track_a_xlsx_retrieval_improvement_plan.md` into a short entrypoint that links to the split phase docs.

#### Evidence

- This entry only reorganizes the plan. It does not claim that A0-A6 have been executed.
- The current evidence snapshot remains based on existing XLSX v3 positive diagnostic outputs:
  - `ai-worker/eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_vector_diagnostic_report.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_retrieval_performance_summary.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_failure_breakdown.json`.
  - `ai-worker/eval/reports/rag-ingestion/rag_xlsx_hidden_negative_leakage_diagnostic.json`.

#### Guardrails

- `promotion_evidence=true` was not introduced.
- No immutable baseline artifact was changed.
- `ai-worker/eval/indexes/rag-data-canary` was not changed.
- `rag-ingestion-v2-xlsx-candidate-v1` was not mutated.
- Hidden-negative rows remain separate from positive retrieval metrics.

#### Validation

- Link targets under `docs/rag-ingestion/xlsx-retrieval/` were checked.
- New markdown files were checked for trailing whitespace.
- `git diff --check` completed without whitespace errors; existing CRLF warning on `docs/rag-ingestion-progress.md` remains unrelated to this Track A docs split.

#### Next

1. Execute A0 and generate `ai-worker/eval/reports/rag-ingestion/rag_xlsx_candidate_lineage_before_tuning.json`.
2. Execute A1 and generate `ai-worker/eval/reports/rag-ingestion/rag_xlsx_v3_failure_case_review.json`.
3. Only after A1, decide whether A2/A3/A4 can proceed independently.

## Entry Template

Use this template for future phase work:

```markdown
### YYYY-MM-DD - <phase id> <short title>

#### Scope

- ...

#### Changes

- ...

#### Evidence

- Reports:
  - `ai-worker/eval/reports/rag-ingestion/...`
- CSV/manifests:
  - `eval/...`

#### Metrics

| Metric | Before | After | Notes |
|---|---:|---:|---|
| Hit@10 | - | - | - |
| MRR@10 | - | - | - |
| xlsx_citation_location_accuracy | - | - | - |
| hidden_content_leakage_count | - | - | hidden-negative only |

#### Guardrails

- `promotion_evidence=false`.
- `evidence_role=diagnostic`.
- Candidate v1 mutated: `false`.
- Immutable baseline changed: `false`.
- `ai-worker/eval/indexes/rag-data-canary` changed: `false`.

#### Validation

- Commands:
  - `...`
- Results:
  - `...`

#### Status

- Phase status: `COMPLETED | PARTIAL | BLOCKED | DEFERRED`.
- Blocker, if any: ...

#### Next

1. ...
```
