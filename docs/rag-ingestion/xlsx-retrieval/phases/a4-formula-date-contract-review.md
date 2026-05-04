# A4 - Formula/Date Contract Review

## 목표

`FORMULA_DATE_CONTRACT_MISMATCH` 1건이 검색 실패인지, query surface 문제인지, embedding/bm25/display/citation text contract 문제인지 분리합니다.

## 대상

| Query id | 현재 category |
|---|---|
| `gq_xlsx_date_number_format_001` | `FORMULA_DATE_CONTRACT_MISMATCH` |

## Surface 정의

| Surface | 의미 |
|---|---|
| `RAW_FORMULA` | `=SUM(...)` 같은 수식 문자열 자체 |
| `CACHED_VALUE` | Excel 계산 결과 값 |
| `DISPLAY_FORMATTED_VALUE` | 통화, 퍼센트, 단위 등이 적용된 표시값 |
| `DATE_FORMATTED_VALUE` | 날짜 형식이 적용된 표시값 |
| `RAW_SERIAL_VALUE` | Excel 내부 날짜/숫자 serial |

## 검토 질문

1. 사용자의 query가 raw formula를 묻는가, 표시값을 묻는가?
2. expected cell/range에 raw formula, cached value, formatted value가 각각 존재하는가?
3. `embedding_text`, `bm25_text`, `display_text`, `citation_text` 중 어느 surface에 값이 들어 있는가?
4. citation/display에는 있는데 embedding에는 빠져 있는가?
5. query wording 수정으로 충분한가?
6. embedding text contract 변경이 필요하다면 candidate v2가 필요한가?

## 작업

1. A1 evidence에서 해당 row의 expected range와 top-k hit를 확인합니다.
2. DB/SearchUnit 또는 available report에서 `embedding_text`, `bm25_text`, `display_text`, `citation_text` surface를 비교합니다.
3. XLSX artifact에서 raw formula, cached/display value, formatted date를 확인합니다.
4. expected surface를 하나로 확정합니다.
5. query-only 수정 가능 여부와 embedding contract 변경 필요 여부를 분리합니다.
6. embedding contract 변경이 필요하면 [A5](a5-candidate-v2-decision.md)로 넘깁니다.

## 산출물

| 파일 | 역할 |
|---|---|
| `reports/rag_xlsx_formula_date_contract_review.json` | expected surface와 결정 |
| `reports/rag_xlsx_formula_date_surface_presence.json` | surface별 presence matrix |

## 완료 기준

```text
reviewed_query_id=gq_xlsx_date_number_format_001
expected_surface in [RAW_FORMULA, CACHED_VALUE, DISPLAY_FORMATTED_VALUE, DATE_FORMATTED_VALUE, RAW_SERIAL_VALUE]
surface_presence_matrix_present=true
next_action in [QUERY_REWRITE, GOLD_POLICY_REVIEW, EMBEDDING_CONTRACT_CHANGE, DEFER]
```

## 금지 사항

- raw formula나 hidden cell value를 무조건 embedding surface에 추가하지 않습니다.
- formula/date row를 evidence 없이 true retrieval failure로 재분류하지 않습니다.
- embedding contract 변경이 필요하다고 판단되기 전에는 candidate v2 namespace를 만들지 않습니다.
