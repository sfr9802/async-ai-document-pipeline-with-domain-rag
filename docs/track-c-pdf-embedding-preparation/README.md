# Track C - PDF Embedding Preparation

이 디렉토리는 `docs/track_c_pdf_embedding_preparation_plan.md`의 통합 플랜을 실행 가능한 phase 문서로 다시 나눈 것이다.

목표는 PDF vector retrieval 개선을 바로 시작하기 전에, PDF citation location 평가에 필요한 metadata projection, embedding text contract, candidate indexing consistency를 먼저 증명하는 것이다.

3-track orchestration에서 이 lane의 track 이름은 `pdf_business_ocr_mm`이다.
목표는 business OCR/MM document RAG이며, OCR text flatten-only 검색이나
page-only keyword lookup이 아니다. PDF retrieval은 candidate retrieval과
layout-aware context assembly를 분리한다.

## Layout-aware retrieval contract

PDF answer handoff evidence bundle은 다음 필드를 포함한다.

| Field | Policy |
|---|---|
| `file`, `page` | source file and resolved page identity |
| `region_type` | paragraph/table/caption/footnote/heading 등 region type |
| `bbox` | layout coordinates when available |
| `matched_text` | matched OCR/native block text |
| `section_heading` | heading/section path nearest to the matched block |
| `table/caption/footnote` | table/caption/footnote context when present |
| `nearby_paragraphs` | local paragraph neighborhood |
| `OCR_confidence` | OCR confidence when provided by parser metadata |
| `score` | retrieval score carried from the candidate |

Context assembly policy is: matched block, page number, bbox, section heading,
table/caption/footnote, nearby paragraph, and OCR confidence if available.
If OCR/MM layout metadata is absent, the row remains diagnostic-only with
`pdf_context_diagnostic_only_missing_layout`.

## 읽는 순서

1. [contracts.md](contracts.md) - PDF metadata, citation, embedding text, namespace 계약
2. [phase-map.md](phase-map.md) - C0~C7 의존성, phase gate, stop 조건
3. [artifacts-and-reports.md](artifacts-and-reports.md) - 스크립트와 report 산출물 매트릭스
4. [risks-and-acceptance.md](risks-and-acceptance.md) - 전체 리스크, 정량 gate, 최종 완료 기준
5. [progress.md](progress.md) - phase별 진행 내역과 합병용 작업 로그
6. [runbook.md](runbook.md) - phase별 명령 예시와 검증 명령
7. [phases/](phases/) - 실제 실행 단위별 상세 플랜

## Phase 개요

| Phase | 문서 | 목표 | 다음 단계로 넘어가는 조건 |
|---|---|---|---|
| C0 | [PDF evidence freeze](phases/c0-evidence-freeze.md) | 현재 PDF diagnostic 문제를 기준선으로 고정 | baseline hash와 PDF failure counter 기록 |
| C1 | [PDF candidate scope report](phases/c1-candidate-scope-report.md) | PDF 전용 candidate scope와 parser/document 범위를 확정 | location, citation, embedding text, page metadata 누락 없음 |
| C2 | [Metadata projection readiness](phases/c2-metadata-projection-readiness.md) | DB metadata가 vector hit까지 복원되는지 확인 | page, bbox, section, OCR metadata projection blocker 없음 |
| C3 | [Embedding text contract audit](phases/c3-embedding-text-contract-audit.md) | PDF embedding/bm25/display/citation surface 계약 검증 | page, section, table, OCR trust surface 누락 없음 |
| C4 | [PDF candidate indexing consistency](phases/c4-candidate-indexing-consistency.md) | PDF-only namespace에 명시 scope만 indexing | claimed=indexed, failed=0, namespace/hash mismatch 없음 |
| C5 | [PDF-only vector diagnostic](phases/c5-pdf-only-vector-diagnostic.md) | metadata/indexing이 통과한 뒤 PDF vector retrieval 진단 | diagnostic report 생성, projection failure와 ranking failure 분리 |
| C6 | [PDF failure breakdown](phases/c6-failure-breakdown.md) | 실패를 metadata, ranking, gold, policy, granularity로 분류 | UNKNOWN failure 없음, query별 next_action 존재 |
| C7 | [PDF gold policy review](phases/c7-gold-policy-review.md) | page/bbox/table/OCR gold binding이 평가 가능한지 확정 | invalid/ambiguous gold policy counter가 0, 필요 시 C6 재분류 완료 |

## 불변 원칙

- PDF retrieval tuning은 C2~C4가 통과한 뒤에만 판단한다.
- 모든 신규 PDF report는 `promotion_evidence=false`, `evidence_role=diagnostic`으로 시작한다.
- PDF candidate namespace는 XLSX/full72 diagnostic artifact와 섞지 않는다.
- candidate indexing은 `allowUnscoped=false`와 explicit `documentVersionIds`를 기본값으로 둔다.
- native PDF와 OCR fallback은 metadata와 trust marker로 분리한다.
- document summary, page summary, text block, table block은 bbox 요구 조건을 다르게 평가한다.
- immutable baseline, XLSX candidate artifact, legacy global cleanup은 이 트랙의 phase gate로 다루지 않는다.

## 1차 완료 정의

Track C 밑작업은 다음이 모두 충족되면 완료로 본다.

```text
PDF candidate scope 확정
metadata projection readiness PASS
embedding_text contract audit PASS
PDF candidate indexing consistency PASS
vector hit에서 page/bbox/section/OCR metadata 복원 가능
PDF-only vector diagnostic report 생성
failure breakdown에서 metadata/ranking/gold/policy 분리
promotion_evidence=false 유지
immutable baseline과 XLSX candidate artifact 변경 없음
```
