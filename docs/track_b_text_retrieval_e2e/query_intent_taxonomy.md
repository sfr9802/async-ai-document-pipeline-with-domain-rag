# Query Intent Taxonomy

Track B는 natural query를 먼저 routing lane으로 분리한다. 목적은 FILE lookup, CONTENT answer, TEXT/XLSX/PDF corpus를 같은 denominator에 섞지 않는 것이다.

## Schema

```json
{
  "query_id": "...",
  "query": "...",
  "resource_type": "TEXT | XLSX | PDF | UNKNOWN",
  "target_type": "FILE | CONTENT | MIXED | UNKNOWN",
  "answer_mode": "FILE_LIST | CONTENT_ANSWER | CITATION_LOOKUP | ABSTAIN_OR_CLARIFY",
  "retrieval_lane": "B_NAMU_TEXT_CONTENT | TEXT_FILE_LOOKUP | XLSX_CONTENT | XLSX_FILE | PDF_CONTENT | PDF_FILE | APP_TEXT_SMOKE | UNKNOWN",
  "readiness": "READY | DIAGNOSTIC_READY | SMOKE_ONLY | PLANNED | BLOCKED | NOT_READY",
  "reason": "..."
}
```

## Intent Examples

| Query 예시 | resource_type | target_type | retrieval_lane | readiness |
|---|---|---|---|---|
| `이 문서에서 갱신 조건은 뭐야?` | `TEXT` | `CONTENT` | `B_NAMU_TEXT_CONTENT` | `READY_AFTER_INVENTORY` |
| `이 정책 문서 찾아줘` | `TEXT` | `FILE` | `TEXT_FILE_LOOKUP` | `PLANNED` |
| `신분당선 2019년 5월 승차총승객수 알려줘` | `XLSX` | `CONTENT` | `XLSX_CONTENT` | `DIAGNOSTIC_READY` |
| `수술 통계 엑셀 파일 찾아줘` | `XLSX` | `FILE` | `XLSX_FILE` | `NOT_READY` |
| `PDF 3페이지 해지 조건 알려줘` | `PDF` | `CONTENT` | `PDF_CONTENT` | `BLOCKED_ON_TRACK_C` |
| `경제 보고서 PDF 찾아줘` | `PDF` | `FILE` | `PDF_FILE` | `NOT_READY` |
| `자료 찾아줘` | `UNKNOWN` | `MIXED` | `UNKNOWN` | `ABSTAIN_OR_CLARIFY` |

## FILE Query Signal

아래 표현이 강하면 `target_type=FILE`로 본다.

```text
파일
문서
자료
보고서
원본
다운로드
목록
찾아줘
열어줘
어디 있어
```

FILE query의 정답은 content citation이 아니라 file candidate list다.

```text
file_id
file_name
file_type
document_id
document_version_id
title
matched_metadata
score
```

## CONTENT Query Signal

아래 표현이 강하면 `target_type=CONTENT`로 본다.

```text
얼마
몇 명
언제
조건
내용
요약
항목
수치
비율
행
셀
표
페이지
문단
조항
```

CONTENT query는 citation location이 필요하다.

```text
TEXT:
  page_id / section_id / chunk_id / section_path

XLSX:
  file > sheet > range

PDF:
  file > page > bbox / section_path
```

## Classification Rules

1. `expected_location_type=xlsx` 또는 XLSX-specific columns가 있으면 `resource_type=XLSX`.
2. `expected_location_type=pdf` 또는 PDF page/bbox columns가 있으면 `resource_type=PDF`.
3. namu-v4 manifest에서 온 row는 `resource_type=TEXT`.
4. `파일/문서/보고서/찾아줘/목록` 중심이면 `target_type=FILE`.
5. `조건/수치/내용/요약/행/셀/페이지` 중심이면 `target_type=CONTENT`.
6. file signal과 content signal이 모두 강하면 `target_type=MIXED`, `requires_clarification=true`.
7. resource hint가 없고 corpus-bound evidence도 없으면 `resource_type=UNKNOWN`.
