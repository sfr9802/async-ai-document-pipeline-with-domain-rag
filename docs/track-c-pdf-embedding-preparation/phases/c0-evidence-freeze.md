# C0. PDF Evidence Freeze

## 목표

현재 PDF diagnostic 문제를 기준선으로 고정한다. 이후 phase에서 metadata projection, indexing, gold policy가 바뀌어도 무엇이 개선되었는지 비교할 수 있어야 한다.

## 입력

- 현재 full72 vector diagnostic report
- 현재 PDF query subset
- 현재 PDF page/bbox failure counters
- immutable baseline artifact hash

## 작업

1. full72 vector diagnostic report의 파일 경로와 hash를 기록한다.
2. PDF query subset을 추출하고 query count, positive count, expected file/page/bbox count를 기록한다.
3. `page_no` hit, `physical_page_index` missing, `bbox` missing, expected file/page absent counter를 고정한다.
4. baseline/candidate artifact가 변경되지 않았음을 확인한다.
5. report에 `promotion_evidence=false`, `evidence_role=diagnostic`을 명시한다.

## 산출물

- `ai-worker/eval/reports/rag-ingestion/rag_pdf_current_diagnostic_snapshot.json`

## 완료 기준

```text
promotion_evidence=false
evidence_role=diagnostic
current PDF failure counters recorded
baseline hash unchanged
PDF query subset count recorded
```

## 다음 단계 조건

C1은 C0 snapshot이 있어야 시작한다. C0 없이 C1~C5를 실행하면 기존 문제와 신규 변화가 섞여 Track C diagnostic의 의미가 약해진다.
