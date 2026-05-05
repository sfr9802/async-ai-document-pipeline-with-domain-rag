# R1 — Query Intent Routing Matrix

## Goal

Track B, XLSX, PDF, file lookup, content lookup query를 같은 retrieval metric에 섞지 않도록 routing matrix를 만든다.

## New Files

```text
scripts/rag_query_intent_routing_matrix.py
ai-worker/tests/test_rag_query_intent_routing_matrix.py
reports/rag_query_intent_routing_matrix_report.json
eval/query_intent_routing_matrix_v0.csv
```

## Inputs

우선 아래 파일들을 입력 후보로 둔다. 존재하지 않는 파일은 missing input으로 기록하고 fail/skip policy를 명시한다.

```text
eval/gold_queries_text_e2e_v0.csv
eval/gold_queries_xlsx_v3_naturalized.csv
eval/gold_queries_xlsx_v3_positive.csv
eval/gold_queries_xlsx_v3_positive_reviewed.csv
eval/gold_queries_v0.csv
```

B-namu용 query/gold 파일은 R2/R3 이후 별도로 확정한다.

```text
eval/gold_queries_text_namu_v4_v0.csv
```

## Output CSV Schema

```csv
query_id,source_manifest,query,resource_type,target_type,answer_mode,retrieval_lane,readiness,classification_rule,confidence,requires_clarification,notes
```

## Classification Rules

1. `expected_location_type=xlsx` 또는 XLSX-specific columns가 있으면 `resource_type=XLSX`.
2. `expected_location_type=pdf` 또는 PDF page/bbox columns가 있으면 `resource_type=PDF`.
3. namu-v4 manifest에서 온 row는 `resource_type=TEXT`.
4. `파일/문서/보고서/찾아줘/목록` 중심이면 `target_type=FILE`.
5. `조건/수치/내용/요약/행/셀/페이지` 중심이면 `target_type=CONTENT`.
6. file signal과 content signal이 모두 강하면 `target_type=MIXED`, `requires_clarification=true`.
7. resource hint가 없고 corpus-bound evidence도 없으면 `resource_type=UNKNOWN`.

## Report Metrics

```json
{
  "status": "COMPLETED | NEEDS_REVIEW",
  "row_count": 0,
  "lane_counts": {},
  "readiness_counts": {},
  "ambiguous_count": 0,
  "unknown_count": 0,
  "mixed_file_content_count": 0,
  "blocked_lane_counts": {},
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

## Acceptance Criteria

- `B_NAMU_TEXT_CONTENT`, `XLSX_CONTENT`, `PDF_CONTENT`, `XLSX_FILE`, `PDF_FILE`, `UNKNOWN`이 분리되어 나온다.
- `UNKNOWN` 또는 `MIXED` row는 report에 명시되고 자동으로 positive denominator에 들어가지 않는다.
- XLSX/PDF file lookup row가 content retrieval metric에 섞이지 않는다.
