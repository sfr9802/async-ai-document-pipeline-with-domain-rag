# R0 — B2 Scope Correction

## Goal

기존 B2를 `B-app app-catalog TEXT canary smoke`로 재라벨링하고, Track B 대표 본선인 `B-namu`가 아직 평가되지 않았음을 명시한다.

## Scope

기존 B2 결과는 보존한다. 삭제하거나 실패로 덮어쓰지 않는다. 단, 의미를 아래처럼 좁힌다.

```text
B2-app이 증명한 것:
  - app catalog TEXT import/search smoke는 실행됨.
  - TEXT-only filter는 path mixing 없이 동작함.
  - 현재 B1 synthetic natural query surface는 lexical library_search와 잘 맞지 않음.

B2-app이 증명하지 않은 것:
  - namu-v4-structured-combined 기반 기존 TEXT retrieval 성능.
  - production-style text retrieval emit 성능.
  - LLM answer까지 포함한 실제 TEXT E2E 성능.
```

## Changes

수정 대상:

```text
docs/track_b_text_retrieval_e2e/rag_text_retrieval_e2e_progress.md
docs/track_b_text_retrieval_e2e/phase_b2_retrieval_diagnostic.md
```

추가 report:

```text
reports/rag_text_b2_scope_correction_report.json
```

## Required Report Fields

```json
{
  "status": "COMPLETED",
  "scope_correction": true,
  "previous_b2_label": "retrieval diagnostic",
  "new_b2_label": "B-app app-catalog TEXT canary smoke",
  "representative_of_namu_v4": false,
  "representative_of_existing_text_retrieval": false,
  "b2_app_report_path": "reports/rag_text_retrieval_diagnostic_report.json",
  "b2_namu_status": "NOT_STARTED",
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

## Phase Status Board Update

```text
B2 app-catalog retrieval diagnostic:
  diagnostic_completed / smoke_only

B2-namu corpus inventory:
  planned

B2-namu retrieval diagnostic:
  blocked_on_B2_namu_inventory

B3 context assembly:
  blocked_on_B2_namu_retrieval
```

## Acceptance Criteria

- 기존 B2 metric을 삭제하지 않는다.
- B2 0점이 namu-v4 성능으로 해석되지 않도록 문구를 추가한다.
- `promotion_evidence=false`, `evidence_role=diagnostic` 유지.
- B3/B4/B5는 `B2-app`이 아니라 `B2-namu` 이후로 연결된다.
