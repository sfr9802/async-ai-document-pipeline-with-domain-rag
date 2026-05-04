# B0 — TEXT Backend Identity

## Goal

평가 대상 retrieval backend를 먼저 고정한다. 이 phase가 끝나기 전에는 E2E answer 품질을 주장하지 않는다.

## Key Questions

| 질문 | 기록 위치 |
|---|---|
| TEXT retrieval backend는 `library_search`, `legacy_text_index`, `vector_text_candidate`, `manual_fixture_backend` 중 무엇인가? | `retrieval_backend` |
| backend artifact, API route, index version, vector namespace, config hash는 무엇인가? | `retrieval_backend_identity` |
| `/api/v1/library/search` 결과에 TEXT/PDF/XLSX가 섞이는가? | `path_mixing` |
| TEXT-only filter가 가능한가? | `text_only_filter_supported` |
| fixture나 stale index가 포함되는가? | `operational_claim_allowed` |

## Work Items

1. 현재 repo에서 TEXT SearchUnit, legacy text index, library search route를 확인한다.
2. 실제 검색 API 또는 index artifact가 TEXT-only 평가를 지원하는지 확인한다.
3. PDF/XLSX stale hit가 섞일 수 있으면 mixing counter와 exclusion rule을 정의한다.
4. backend identity report schema를 확정한다.
5. backend가 비어 있거나 fixture뿐이면 fail-closed 상태로 기록한다.

## Output

`reports/rag_text_backend_identity_report.json`

권장 shape:

```json
{
  "retrieval_backend": "library_search",
  "retrieval_backend_identity": {
    "api_route": "/api/v1/library/search",
    "index_version": null,
    "artifact_dir": null,
    "config_sha256": null
  },
  "text_only_filter_supported": false,
  "path_mixing": {
    "text_count": 0,
    "pdf_count": 0,
    "xlsx_count": 0,
    "unknown_count": 0
  },
  "operational_claim_allowed": false,
  "promotion_evidence": false,
  "evidence_role": "diagnostic"
}
```

## Done Criteria

```text
retrieval_backend is not empty
retrieval_backend_identity is recorded
TEXT/PDF/XLSX path mixing status is recorded
TEXT-only evaluation feasibility is recorded
fixture-only or empty backend cannot proceed as operational evidence
```

## Verification

최소 검증은 문서/코드 경로 확인과 backend identity report 생성이다. live API가 준비되어 있지 않으면 report에 `operational_claim_allowed=false`를 남긴다.
