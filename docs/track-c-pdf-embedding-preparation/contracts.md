# Track C Contracts

이 문서는 C0~C7 전 phase가 공유하는 PDF metadata, embedding text, citation, namespace 계약이다. phase 문서가 더 구체적인 기준을 제시하지 않는 한 이 파일을 우선한다.

## Location Metadata

PDF SearchUnit의 `location_json` 권장 구조:

```json
{
  "type": "pdf",
  "physical_page_index": 4,
  "page_no": 5,
  "page_label": "v",
  "bbox": [72.0, 120.0, 510.0, 680.0],
  "section_path": ["3. 계약 조건", "3.2 해지 조건"],
  "block_type": "paragraph",
  "ocr_used": false,
  "ocr_confidence": null,
  "parser_name": "pymupdf",
  "parser_version": "pdf-extract-v1"
}
```

필드 요구 조건:

| 필드 | text block | table block | page summary | document summary | OCR block |
|---|---:|---:|---:|---:|---:|
| `physical_page_index` | 필수 | 필수 | 필수 | 선택 | 필수 |
| `page_no` | 필수 | 필수 | 필수 | 선택 | 필수 |
| `page_label` | 권장 | 권장 | 권장 | 선택 | 권장 |
| `bbox` | 필수 | 필수 또는 table bbox | 선택 | 선택 | 필수 |
| `section_path` | 권장 | 권장 | 선택 | 선택 | 권장 |
| `block_type` | 필수 | 필수 | 필수 | 필수 | 필수 |
| `ocr_used` | 필수 | 필수 | 필수 | 필수 | 필수 |
| `ocr_confidence` | null 허용 | null 허용 | null 허용 | null 허용 | 필수 |

## Citation Text

기본 형식:

```text
{file_name} > p.{page_no} > bbox [{x0},{y0},{x1},{y1}]
```

page label이 의미 있는 문서에서는 다음 형식도 허용한다.

```text
{file_name} > page_label {page_label} / p.{page_no} > bbox [...]
```

`document_summary`처럼 bbox가 선택인 block은 bbox 없는 citation을 failure로 보지 않는다. 단, `text block`, `table block`, `OCR block`은 bbox 또는 table bbox 정책을 명시해야 한다.

## Embedding Text

PDF `embedding_text`에는 검색에 필요한 구조 surface를 넣되 parser 내부 dump를 넣지 않는다.

포함해야 할 정보:

```text
source file name
page number / page label
section path
block type
paragraph text or table text
caption/header if present
OCR trust marker if OCR used
citation text surface
```

예시:

```text
source: example.pdf
page: 5
page_label: v
section: 3. 계약 조건 > 3.2 해지 조건
block_type: paragraph
ocr_used: false
citation: example.pdf > p.5 > bbox [72.0,120.0,510.0,680.0]
text: 계약 해지 조건은 ...
```

OCR 예시:

```text
source: scanned-example.pdf
page: 2
block_type: ocr_text
ocr_used: true
ocr_confidence: 0.82
trust: lower_trust_ocr
citation: scanned-example.pdf > p.2 > bbox [50.0,80.0,540.0,700.0]
text: ...
```

제외해야 할 정보:

```text
parser debug dump
full raw JSON
hidden/internal fields
stack trace or warnings as searchable content
binary/image metadata unrelated to answer
untrusted OCR text without lower-trust marker
```

## Candidate Namespace

PDF 전용 candidate namespace:

```text
index_version = rag-ingestion-v2-pdf-candidate-v1
artifact_dir   = rag-data-pdf-candidate-v1
```

지원 parser scope:

```text
pdf-extract-v1
pdf-extract-v2
```

`pdf-extract-v1`은 native text 중심, `pdf-extract-v2`는 OCR fallback 가능 path로 본다.

## Evidence Policy

모든 신규 report는 다음 값을 유지한다.

```text
promotion_evidence=false
evidence_role=diagnostic
```

이 트랙은 promotion gate 통과나 immutable baseline 갱신이 목적이 아니다. PDF-only 진단이 끝나기 전에는 낮은 retrieval metric을 ranking 실패로 단정하지 않는다.
