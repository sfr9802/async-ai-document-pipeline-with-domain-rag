# Verifiable Document RAG Backend

This repository centers on evidence-grounded document answering: retrieval scope
is explicit, SearchView rows remain candidate-only, SourceAtom/EvidenceBundle
objects remain answer-evidence truth, and unsafe paths fail closed.

The AgentOps surface is intentionally thin. It maps the existing deterministic
RAG runtime into tool-style policy and trace records for technical analysis; it
does not create an autonomous agent framework, mutate gold labels, or claim
production readiness.

## Portfolio freeze v1 기준

`portfolio-freeze-v1`은 신규 기능이나 평가 점수 개선이 아니라, 현재 repo
artifact에 맞춘 제출용 claim 정리 기준입니다.

| 항목 | 현재 기준 |
|---|---|
| 기준 report | `reports/rag_eval/latest.json` -> `actual_rag_eval_query_formulation_v3_agentic_guard_nonprod_20260614_v4/report.json` |
| 핵심 claim | 검색 후보와 실제 답변 근거 분리, SourceAtom/EvidenceBundle citation verification, fail-closed response policy, trace/report 기반 검증 |
| Agent 표현 | 완성된 autonomous agent가 아니라, agent-ready/agentic system boundary에 필요한 검색·근거·응답 제어 기반 |
| Actual Response Smoke | answer quality score가 아니라 response policy smoke. 29개 승인 질의에서 10개 answered/citation-verified, 19개 stopped/fail_closed로 기록 |
| XLSX 표현 | sheet/range/cell/axis locator와 citation 구조는 설명 가능. 현재 smoke 기준으로 XLSX-wide success claim은 하지 않음 |
| 금지 claim | production readiness, live readiness, product success, official metric, broader agent loop opened/ready |

## 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 프로젝트 성격 | 문서 검색·질의응답 AI 파이프라인 |
| 처리 문서 | TEXT, PDF, XLSX |
| 핵심 기능 | 문서 파싱, OCR, 검색 인덱싱, RAG 답변 생성, citation 표시 |
| 주요 기술 | Spring Boot, FastAPI, Python, PostgreSQL, Redis, Weaviate, FAISS, React/Vite |
| 구현 방향 | 긴 AI 작업은 비동기 job으로 처리하고, 답변의 원문 근거는 추적 가능한 evidence 구조로 관리 |

## 핵심 목표

AI 문서 검색에서 중요한 것은 답변의 자연스러움만이 아닙니다.  
답변이 실제 문서의 어떤 부분을 근거로 생성되었는지 확인할 수 있어야 합니다.

이 프로젝트는 다음 목표를 기준으로 구현했습니다.

| 목표 | 설명 |
|---|---|
| 문서 유형별 처리 | PDF, XLSX, TEXT 문서를 각 형식에 맞게 파싱 |
| 검색 가능한 단위 구성 | 문서 내용을 검색과 답변 생성에 사용할 수 있는 단위로 정리 |
| 근거 기반 답변 생성 | 질문과 관련된 원문 근거를 찾고 이를 바탕으로 답변 생성 |
| citation 제공 | 답변에 사용된 PDF page, XLSX sheet/cell, TEXT chunk 정보를 함께 반환 |
| 비동기 작업 처리 | OCR, 인덱싱, RAG처럼 오래 걸리는 작업을 job pipeline으로 분리 |

## RAG 응답/근거 예시

아래 예시는 전체 성능 지표를 대체하기 위한 벤치마크가 아니라, 이 프로젝트가 문서 유형별로 어떤 질문을 처리하고 어떤 근거를 함께 반환하는지 보여주는 대표 샘플입니다.

각 응답은 단순 생성 결과가 아니라, 답변에 사용된 원문 위치를 함께 관리합니다.

### PDF 문서 질의

| 질문 | 응답 | 근거 | 확인 가능한 점 |
|---|---|---|---|
| 2020년 한국 원달러 기말 환율은 얼마인가요? | 2020년 한국 원달러 기말 환율은 1,088.0입니다. | 최근경제동향 PDF p.65 | PDF 표 안에서 특정 연도와 항목을 찾고 해당 값을 추출 |
| 2024년 수출입차 금액은 얼마인가요? | 2024년 수출입차 금액은 6,836.1입니다. | 최근경제동향 PDF p.61 | PDF 내 경제지표 표에서 질문 항목과 연도를 매칭 |

### XLSX 문서 질의

아래 XLSX 행은 셀 단위 citation 구조 예시입니다. 현재 `Actual Response Smoke`
정책과 충돌하지 않도록, XLSX 전반의 응답 성공률이나 품질 성공 claim으로
해석하지 않습니다.

| 질문 | 응답 | 근거 | 확인 가능한 점 |
|---|---|---|---|
| 2019년 2월 5호선의 승차총승객수는 몇 명입니까? | 2019년 2월 5호선의 승차총승객수는 15,446,522명입니다. | 철도 sheet, D352 | 조건에 맞는 행을 찾고 특정 셀의 display value를 응답에 사용 |
| 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까? | 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 41786입니다. | 일반현황 sheet, C702 | 기관명과 지정일 조건을 만족하는 행에서 우편번호 셀을 추출 |
| 2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까? | 해뜨는요양원2의 시도 시군구 법정동명은 대구광역시 북구 복현동입니다. | 일반현황 sheet, G752 | 여러 조건을 조합해 행을 찾고 행 내 다른 컬럼 값을 응답 |

### TEXT 문서 질의

| 질문 | 응답 | 근거 | 확인 가능한 점 |
|---|---|---|---|
| 미츠하는 타키를 만나려고 어디로 향했어 | 미츠하는 타키를 실제로 만나기 위해 도쿄로 향했습니다. | TEXT chunk/source context | 서술형 문맥에서 장소 정보를 찾아 자연어로 응답 |
| 유우야키의 나이와 생일은 어떻게 적혀 있어 | 유우야키의 나이는 16세이고 생일은 9월 29일입니다. | TEXT chunk/source context | 한 문맥 안의 여러 속성 값을 함께 추출 |

더 많은 샘플과 XLSX display-value/cell-range 진단 결과는 [Evaluation harness samples](ai/eval/README.md)에 정리했습니다.

## Citation 처리 방식

문서 유형마다 원문 근거를 표현하는 방식이 다르기 때문에, citation을 하나의 문자열로 단순화하지 않고 문서 유형별 evidence 구조로 분리했습니다.

| 문서 유형 | citation 단위 | 예시 |
|---|---|---|
| PDF | page, text/table context | `p.65`, `p.61` |
| XLSX | sheet, range, cell, display value | `철도!D352`, `일반현황!C702` |
| TEXT | chunk, source context | `chunk id`, `source excerpt` |

검색 단계에서 찾은 후보와 최종 답변에 사용된 근거는 분리해서 관리했습니다.

검색 후보는 관련 문서를 찾기 위한 retrieval candidate이고, citation은 사용자가 실제로 확인할 수 있어야 하는 원문 근거입니다.  
이 둘을 구분해 답변 생성 과정과 근거 표시 과정이 섞이지 않도록 했습니다.

| 개념 | 역할 |
|---|---|
| SearchUnit | 검색 인덱싱의 기본 단위 |
| SearchView | retrieval candidate 구성을 위한 검색 표현 |
| SourceAtom | 최종 citation에 사용되는 원문 근거 단위 |
| Evidence contract | PDF/XLSX/TEXT 유형별 근거 표현 규칙 |

## 시스템 흐름

사용자는 문서를 등록하거나 질문을 보냅니다.  
API 서버는 작업을 생성하고 상태를 관리하며, AI worker는 문서 파싱, 검색 인덱싱, 근거 조립, 답변 생성을 비동기로 수행합니다.

```mermaid
flowchart LR
    Client["사용자 / React 화면"] --> Core["Spring Boot API"]

    Core --> DB[("PostgreSQL")]
    Core --> Redis[("Redis dispatch signal")]

    Redis --> Worker["FastAPI / Python worker"]

    Worker --> Parse["OCR / PDF / XLSX parsing"]
    Worker --> Index["SearchUnit / SearchView indexing"]
    Worker --> RAG["Retrieval -> Evidence assembly -> RAG answer"]

    Worker --> Core
    Core --> Result["답변 + 근거 artifact"]
```

## 주요 기능

| 영역 | 구현 내용 |
|---|---|
| 문서 등록 및 작업 관리 | 문서 처리 job 생성, 상태 조회, 결과 artifact 조회 |
| 비동기 AI 처리 | Redis signal 기반 worker dispatch, callback delivery, job 상태 추적 |
| 문서 파싱 | TEXT chunking, PDF text/table 처리, XLSX workbook 구조 및 display value 추출 |
| 검색 인덱싱 | SearchUnit/SearchView 후보 구성, Weaviate route-selected retrieval, FAISS diagnostic baseline |
| RAG 답변 생성 | 검색 결과를 기반으로 답변 생성 및 citation artifact 구성 |
| 근거 추적 | PDF page, XLSX sheet/range/cell, TEXT chunk 단위의 evidence 관리 |
| 평가 도구 | citation/evidence gate, response policy smoke, retrieval diagnostics, diagnostic-only 결과 관리 |
| 화면 구성 | React/Vite 기반 작업 목록, 상태 timeline, 결과 preview 화면 |

## 해결한 문제

### 1. 긴 AI 작업을 요청/응답 흐름에서 분리

OCR, 문서 파싱, 인덱싱, RAG 답변 생성은 처리 시간이 길고 실패 가능성도 있습니다.

이를 API 요청 안에서 직접 처리하지 않고, job pipeline으로 분리했습니다.  
Spring Boot API는 job 생성과 상태 관리를 담당하고, FastAPI worker는 실제 문서 처리와 RAG 작업을 수행합니다.

PostgreSQL은 job 상태와 결과 저장의 기준점으로 사용하고, Redis는 worker dispatch signal 용도로 제한했습니다.

### 2. 답변과 근거를 함께 검증할 수 있는 구조 구성

RAG 시스템에서 검색된 문서 조각이 항상 최종 답변의 직접 근거가 되는 것은 아닙니다.

이 프로젝트에서는 retrieval candidate와 citation evidence를 분리해, 최종 응답에 사용된 원문 위치를 별도로 관리했습니다.  
이를 통해 답변 생성에 사용되는 검색 흐름과 사용자가 검증할 수 있는 citation 흐름을 구분했습니다.

### 3. XLSX 셀 단위 근거 추적

XLSX 문서는 일반 텍스트처럼 chunk만 나누면 답변 근거를 확인하기 어렵습니다.

예를 들어 특정 기관명, 지정일, 노선명 같은 조건으로 행을 찾고, 그 행의 특정 컬럼 값을 답해야 하는 경우가 많습니다.  
따라서 sheet, range, cell, display value를 별도 evidence로 관리해 사용자가 응답에 사용된 값을 셀 단위로 확인할 수 있게 했습니다.

### 4. PDF 표 기반 질의 처리

PDF 문서에서는 본문 텍스트뿐 아니라 표 안의 값이 답변 근거가 되는 경우가 많습니다.

이 프로젝트에서는 PDF page citation을 유지하면서, 표나 경제지표처럼 행/열 맥락이 필요한 질문에 대해 관련 페이지와 값을 함께 추적하도록 구성했습니다.

### 5. 평가 결과와 운영 기준 분리

평가 harness에서 나온 결과를 곧바로 운영 품질처럼 단정하지 않도록 결과의 성격을 구분했습니다.

| 구분 | 의미 |
|---|---|
| diagnostic-only | 원인 분석과 개선 방향 확인용 결과 |
| promotion evidence | 인덱스나 정책 승격 판단에 사용할 수 있는 근거 |
| production promotion | 실제 운영 기준으로 반영된 상태 |

이를 통해 실험용 진단 결과, 승격 판단 근거, 실제 운영 기준이 섞이지 않도록 관리했습니다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| Backend API | Spring Boot |
| AI Worker | FastAPI, Python |
| Database | PostgreSQL |
| Dispatch / Signal | Redis |
| Retrieval | FAISS |
| Frontend | React, Vite |
| Document Processing | PDF parsing, XLSX workbook extraction, OCR |
| Evaluation | answer/citation scorer, retrieval smoke metric |

## 폴더 구조

| 경로 | 역할 |
|---|---|
| [`core-api/`](core-api/) | Spring Boot API 서버 |
| [`ai/app/`](ai/app/) | Python AI worker와 capability 구현 |
| [`ai/eval/`](ai/eval/) | RAG/OCR evaluation harness와 기준 데이터 |
| [`frontend/app/`](frontend/app/) | React/Vite UI |
| [`docker-compose.yml`](docker-compose.yml) | 로컬 PostgreSQL, Redis, 선택형 MinIO/LLM 인프라 구성 |
| [`.env.example`](.env.example) | 로컬 실행 환경 변수 예시 |
| `docs/THIRD_PARTY_DATA_LICENSES.md` | 로컬 전용 외부 데이터 및 라이선스 상세 노트, fresh checkout 기준 source-of-truth 아님 |

## 저장소 artifact 관리

이 저장소는 코드와 진단 evidence를 의도적으로 분리합니다. `portfolio-freeze-v1` 기준 latest pointer는 `reports/rag_eval/latest.json`과 `reports/rag_eval/latest_text_gold.json`이며, 현재 둘 다 `actual_rag_eval_query_formulation_v3_agentic_guard_nonprod_20260614_v4`를 가리킵니다. `reports/rag_eval/rag-ingestion/**` 아래의 `report.json`, `status.jsonl`, run sidecar는 대부분 generated/local-only diagnostic artifact입니다.

보고서 루트는 역할별로 나눕니다. `reports/`에는 작은 public portfolio artifact allowlist만 추적하고, `reports/rag_eval/`은 ignored actual-RAG machine report/latest namespace로 둡니다. `reports/rag_eval/rag-ingestion/`은 legacy/current diagnostic ladder와 short-key check evidence를 보존하는 ignored namespace이며, 현재 diagnostic ladder alias는 `v6_9_answer_quality_gate_packet_nonprod`입니다. 실행 기준은 `ai/eval/rag_eval_registry.py`, `ai/scripts/rag_eval.py`, `ai/eval/report_paths.py`를 통해 확인하고, `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, `docs/rag-ingestion-triage.md`는 작업자가 직접 남기는 로컬 rolling handoff 노트로만 취급합니다.

정리 기준은 보수적입니다. active source, 테스트, README/docs, registry/runner, gold/qrels/official denominator/eval query/source registry/index/silver 표면은 보존합니다. 삭제가 애매한 legacy 또는 diagnostic bundle은 hold로 남기며, 해시 검증된 외부 archive 없이 bulk-delete하지 않습니다. 안전 삭제 대상은 `.pytest_cache`, `__pycache__`, bytecode, `core-api/target`, `frontend/app/node_modules`, `frontend/app/dist`처럼 lockfile이나 빌드로 재생성 가능한 transient cache/dependency/build output으로 제한합니다.

정리 근거의 source-of-truth는 code-owned registry/runner와 generated report namespace입니다. `docs/rag-ingestion-*.md` 및 `docs/codex-goals/*.md`는 세션 인수인계용 로컬 노트이며 fresh checkout이나 실험 실행이 의존하면 안 됩니다. 문서 rolling은 유지하지만 스크립트가 자동으로 읽거나 쓰지 않고, 작업자가 로컬 handoff로 남기는 방식입니다. 2026-06-09 generated report `reports/rag_eval/rag-ingestion/runs/repo_cleanup_20260609_diagnostic_inventory/report.json`은 이전 cleanup inventory입니다.

## 라이선스와 외부 데이터

이 저장소의 직접 작성 코드와 문서는 [Apache License 2.0](LICENSE)을 따릅니다.

단, 외부에서 수집한 PDF, XLSX, 이미지, OCR/MM annotation, 폰트, 공공데이터, Hugging Face dataset mirror, NamuWiki metadata 등은 이 저장소의 Apache-2.0 라이선스로 재허가되지 않습니다.

원천별 이용조건과 내부 diagnostic usage gate는 이 섹션과 코드/fixture별 allowlist를 기준으로 확인하세요. `docs/THIRD_PARTY_DATA_LICENSES.md`가 로컬에 있더라도 fresh checkout source-of-truth로 간주하지 않습니다.
