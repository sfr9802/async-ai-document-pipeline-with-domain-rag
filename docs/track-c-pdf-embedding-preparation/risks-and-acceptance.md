# Risks And Acceptance

이 문서는 Track C 전체의 phase 경계 리스크와 최종 완료 기준을 모은다. 각 phase 문서에는 phase-local gate를 두고, 이 문서는 전체 트랙을 닫을 때 확인한다.

## Phase 경계 리스크

| 리스크 | 대응 |
|---|---|
| C2/C3 readiness 없이 C4 indexing을 먼저 실행 | C4 입력에 C2/C3 PASS report를 요구한다 |
| C5/C6 diagnostic이 promotion evidence처럼 해석됨 | 모든 report에 `promotion_evidence=false`, `evidence_role=diagnostic`을 반복 기록한다 |
| C6에서 gold ambiguity가 발견됐는데 C7을 일회성 최종 단계로 처리 | C7 policy 정리 후 필요한 query는 C6 breakdown으로 재분류한다 |
| C0 baseline freeze가 약해 C4 이후 변경 범위를 판단하지 못함 | C0와 C4 모두 baseline hash, XLSX artifact 변경 여부, namespace mismatch를 확인한다 |
| bbox 없는 document summary를 text/OCR block failure로 오분류 | [contracts.md](contracts.md)의 block type별 bbox requirement를 판정 기준으로 사용한다 |
| OCR fallback row가 native PDF row와 같은 신뢰도로 섞임 | OCR confidence와 `lower_trust_ocr` marker를 C2/C3/C7에서 반복 확인한다 |
| stale legacy PDF row가 candidate evidence에 섞임 | explicit `documentVersionIds`, parser scope, `allowUnscoped=false`를 사용한다 |

## 전체 완료 기준

Track C는 다음이 모두 만족될 때 1차 완료로 본다.

```text
PDF candidate scope 확정
PDF metadata projection readiness PASS
PDF embedding_text contract audit PASS
PDF candidate indexing consistency PASS
vector hit에서 physical_page_index/page_no/page_label/bbox/section_path/ocr metadata 복원 가능
PDF-only vector diagnostic report 생성
PDF failure breakdown에서 metadata/ranking/gold/policy 분리
promotion_evidence=false 유지
immutable baseline과 XLSX candidate artifact 변경 없음
```

정량 gate:

| 항목 | 목표 |
|---|---:|
| metadata projection blocker | `0` |
| missing physical_page_index for page-bound chunks | `0` |
| missing bbox for text/OCR block chunks | `0` |
| missing ocr_confidence for OCR chunks | `0` |
| not_embedded_count | `0` |
| index_version_mismatch_count | `0` |
| embedding_record_missing_count | `0` |
| candidate_chunk_missing_count | `0` |
| vector_namespace_mismatch_count | `0` |
| chunk_sha_mismatch_count | `0` |
| UNKNOWN failure count | `0` |
| invalid_gold_count | `0` |
| page_policy_ambiguous_count | `0` |
| table_policy_ambiguous_count | `0` |
| ocr_policy_ambiguous_count | `0` |

## Retrieval Tuning 시작 조건

다음 조건이 모두 충족되기 전에는 PDF retrieval tuning을 시작하지 않는다.

```text
metadata_projection_blocker_count=0
text_contract_blocker_count=0
indexing_consistency_blocker_count=0
gold_policy_blocker_count=0
true_retrieval_ranking_failure_count > 0
```

이 조건이 충족되면 Track C는 밑작업을 완료한 것으로 보고, 후속 retrieval/ranking 개선은 별도 트랙으로 분리한다.
