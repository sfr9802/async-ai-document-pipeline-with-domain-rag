# C7. PDF Gold Policy Review

## 목표

PDF page, bbox, table, OCR row의 expected label이 평가 가능한지 확인한다. gold binding이 애매하면 retrieval 실패로 처리하지 않는다.

## 입력

- `reports/rag_pdf_vector_quality_breakdown.json`
- PDF gold/query rows
- PDF page metadata
- table block metadata
- OCR confidence/trust metadata

## 검토 포인트

- `page_no`와 `physical_page_index`가 모두 필요한가?
- page label이 roman numeral 또는 appendix label일 때 어떻게 판정할 것인가?
- table row는 bbox exact가 필요한가, table bbox overlap이면 되는가?
- page summary와 document summary는 어떤 location 기준을 적용할 것인가?
- OCR row는 confidence threshold를 어떻게 둘 것인가?
- generic PDF query가 특정 page를 기대하기에 너무 모호한가?

## 작업

1. C6에서 gold/policy 의심으로 분류된 query를 우선 검토한다.
2. page number, physical page index, page label policy를 정리한다.
3. table bbox exact/overlap/containment 기준을 정한다.
4. OCR confidence threshold와 lower-trust handling을 정한다.
5. generic query가 특정 page/bbox gold를 요구하기에 부적합한지 판정한다.
6. invalid gold는 retrieval metric에서 제외하거나 relabel 후보로 분리한다.

## 산출물

- `reports/rag_pdf_gold_policy_review.json`
- 필요 시 relabel 후보 목록

## 완료 기준

```text
invalid_gold_count=0
page_policy_ambiguous_count=0
table_policy_ambiguous_count=0
ocr_policy_ambiguous_count=0
relabel_candidate_rows_recorded=true 또는 relabel_candidate_count=0
```

## Post-C7 판단

C7 이후에도 다음 blocker가 0이면 PDF retrieval/ranking 개선 후보를 따로 만든다.

```text
metadata_projection_blocker_count=0
text_contract_blocker_count=0
indexing_consistency_blocker_count=0
gold_policy_blocker_count=0
true_retrieval_ranking_failure_count > 0
```
