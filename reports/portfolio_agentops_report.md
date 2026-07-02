# RAG 실행 추적/가드 요약

이 문서는 포트폴리오 README를 보조하는 한국어 요약입니다. 이 저장소의
핵심 구현은 문서 RAG이고, 여기서는 그 위에 얇게 얹은 추적/가드 계층이
무엇을 검증하는지만 정리합니다.

이 문서는 공식 성능 지표, 운영 배포 준비, 제품 성과를 주장하지
않습니다. gold, qrels, label, expected answer, supporting evidence도 이
문서 작업에서 생성하거나 변경하지 않습니다.

## 요약

| 항목 | 현재 상태 |
|---|---|
| 기본 포지션 | 근거 검증형 문서 RAG 백엔드 |
| 추적/가드 역할 | RAG 실행 전에 정책을 확인하고, 도구 선택과 최종 결정을 비식별 trace로 남김 |
| 현재 검증 라인 | `current_resolves_to=v6_9_answer_quality_gate_packet_nonprod` |
| 검색 후보 검수 | `v6_9_1_retrieval_smoke_pre_review_packet_nonprod`, 135개 후보 row |
| 응답 정책 확인 | 29개 승인 질의 중 PDF/TEXT 10개는 citation verified 답변, XLSX 19개는 fail-closed |
| 공식 지표 | 닫힘 |
| 운영 준비 상태 | 주장하지 않음 |

## 실행 흐름

```text
요청 컨텍스트
  -> 정책 확인
  -> 허용된 RAG tool 선택
  -> 제한된 후보 범위 확인
  -> SourceAtom / EvidenceBundle 검증
  -> 답변 가능성 판단
  -> 진단 답변 또는 fail-closed
  -> 비식별 trace 기록
```

## 구현된 구성

| 구성 | 코드/자료 |
|---|---|
| RAG 실행부 | `ai/app/capabilities/rag_orchestrator/agent_runtime.py` |
| 추적/가드 adapter | `ai/app/capabilities/rag_orchestrator/agentops_runtime.py` |
| 도구 registry | `ai/app/capabilities/rag_orchestrator/tool_registry.py` |
| Evidence 구조 | `ai/app/capabilities/rag/source_registry.py`, `ai/app/capabilities/rag_orchestrator/evidence.py` |
| 샘플 trace | `reports/agentops_sample_trace.json` |
| Eval runner | `ai/scripts/rag_eval.py` |

## 정책 경계

| 경계 | 처리 방식 |
|---|---|
| 허용되지 않은 tool | fail-closed |
| production namespace 또는 writable indexing scope | fail-closed |
| evidence가 필요한 요청에 evidence id가 없음 | fail-closed |
| 후보 SourceAtom 범위가 비어 있거나 source family가 맞지 않음 | runtime 호출 전 fail-closed |
| 공식 지표 요청 | 사용자 승인 없이 열지 않음 |
| 답변 근거가 부족하거나 애매함 | diagnostic-only handoff 또는 fail-closed |
| raw prompt/source/local path | sample trace에 저장하지 않음 |

## 샘플 Trace

`reports/agentops_sample_trace.json`은 공개 가능한 비식별 trace 예시입니다.

| 필드 | 값 |
|---|---|
| `run_id` | `agentops-portfolio-smoke` |
| `source_family` | `XLSX` |
| 선택 tool | `retrieve_xlsx_table`, `validate_evidence`, `classify_answerability` |
| evidence ref | `evidence_ref:01` |
| policy decision | `allow_diagnostic` |
| final decision | `diagnostic_only_answer` |
| report path | `reports/portfolio_agentops_report.md` |

## 검증

| 명령 | 결과 |
|---|---|
| `python -X utf8 -m pytest ai/tests/test_agentops_portfolio_runtime_contract.py -q` | 28 passed |
| `python -X utf8 -m py_compile ai/app/capabilities/rag_orchestrator/agentops_runtime.py` | passed |
| `python -X utf8 -m json.tool reports/agentops_sample_trace.json` | passed |
| `python -X utf8 ai/scripts/rag_eval.py current --check` | `current_resolves_to=v6_9_answer_quality_gate_packet_nonprod` |
| `python -X utf8 ai/scripts/rag_eval.py v6_9_1_retrieval_smoke_pre_review_packet_nonprod --check` | 135개 review row 확인 |
| `python -X utf8 -m pytest ai/tests/test_rag_v691_retrieval_smoke_pre_review_packet_nonprod_contract.py -q -p no:cacheprovider` | 14 passed |

## 한계

| 항목 | 현재 입장 |
|---|---|
| Answer quality metric | 공식 지표로 열지 않음 |
| Retrieval Hit@K/MRR/nDCG | qrels/denominator 검토 전에는 공식 지표로 열지 않음 |
| Gold/qrels/label | 자동 생성 또는 변경하지 않음 |
| 운영 배포 준비 | 주장하지 않음 |
| AgentOps 표현 | 독립 플랫폼이 아니라 RAG 실행의 추적/가드 보조 계층 |
| 외부 API/local LLM | 이 trace/guard 검증에는 필요하지 않음 |

## 면접에서 설명하기 좋은 포인트

| 질문 포인트 | 짧은 답변 |
|---|---|
| 왜 trace/guard가 필요한가? | RAG가 답변을 만들기 전에 근거 범위와 정책을 확인하고, 왜 답변했거나 멈췄는지 남기기 위해서입니다. |
| 왜 fail-closed인가? | 근거가 약한 자연어 답변을 성공처럼 보이지 않게 하기 위해서입니다. |
| AgentOps라고 부를 수 있나? | 대형 AgentOps 플랫폼은 아니고, RAG runtime 위의 tool/policy/trace 경계를 구현한 작은 진단 계층입니다. |
| 최신 상태는? | `current`는 `v6_9_answer_quality_gate_packet_nonprod` 기준이며, 검색 후보 검수 패킷은 135개 row로 분리되어 있습니다. |
