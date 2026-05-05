# RAG Framework Adoption Review

작성일: 2026-05-04

## Scope

이 문서는 현재 RAG ingestion/query 구조를 실제 코드 기준으로 다시 맵핑하고, LangChain 또는 LangGraph를 도입할지 판단하기 위한 architecture review이다.

이번 판단의 전제는 명확하다.

- ingestion core, parser, SearchUnit 생성, indexing worker, promotion gate는 유지한다.
- 도입 후보는 query-time RAG orchestration이다.
- LangChain 도입은 필수 전제가 아니며, LangGraph 단독 도입 가능성을 우선 본다.
- library-search diagnostic과 promotion-grade vector retrieval은 분리한다.
- ACL/tenant/index_version/source_file_type/parser_version 필터는 LLM 판단이 아니라 code-level fail-closed guard로 둔다.

## Executive Decision

LangChain: 제한적 비추천, 기본 보류.

현재 repo는 이미 자체 parser, artifact, SearchUnit, canonical embedding text, FAISS/ragmeta, eval/gate contract를 갖고 있다. LangChain loader/vectorstore/agent를 넓게 들이면 가장 중요한 ingestion/index/eval contract를 중복하거나 흐릴 가능성이 크다. POC 단계에서는 LangChain을 넣지 않는다.

LangGraph: 제한적 추천.

단, 위치는 query-time orchestration으로 제한한다. PDF/XLSX/TEXT vector search tool 조합, fallback, deterministic citation verification, deterministic XLSX aggregation, evidence merge, answer synthesis 같은 실행 그래프에는 적합하다. ingestion core나 promotion/eval/gate를 graph node로 옮기면 안 된다.

## A. Current Structure Summary

### Spring API

주요 진입점은 `core-api/src/main/java/com/aipipeline/coreapi/catalog/adapter/in/web/DocumentCatalogController.java`이다.

- Base route: `/api/v1/library`
- Source upload: `POST /source-files`
- OCR import job: `POST /source-files/{sourceFileId}/ocr-extract`
- XLSX import job: `POST /source-files/{sourceFileId}/xlsx-extract`
- PDF import job: `POST /source-files/{sourceFileId}/pdf-extract`
- diagnostic library search: `GET /search?query=&limit=`

`DocumentCatalogService.search()`는 JPA lexical search이다. `SearchUnitJpaRepository.searchByText()`가 `textContent`, `bm25Text`, `displayText`, `citationText`, `debugText`를 `LIKE`로 검색한다. 이 경로는 vector retrieval이 아니며, 현재 query-time ACL/tenant/index_version/source_file_type/parser_version 필터도 강제하지 않는다.

### Ingestion Catalog

`DocumentCatalogService`는 callback/import 이후 `source_file`, `document`, `document_version`, `parsed_artifact`, `search_unit`, `table_metadata`, `cell_metadata`, `pdf_page_metadata`를 만든다. SearchUnit v2 필드에는 다음이 포함된다.

- `source_file_type`
- `chunk_type`
- `location_type`
- `location_json`
- `embedding_text`
- `bm25_text`
- `display_text`
- `citation_text`
- `parser_name`
- `parser_version`
- `index_version`
- `acl_tags`

이 구조는 LangChain loader로 대체할 대상이 아니라, 이미 repo의 canonical ingestion contract이다.

### SearchUnit Indexing

내부 indexing API는 `SearchUnitIndexingController`의 `/api/internal/search-units/indexing`이다.

- `POST /claim`
- `POST /{searchUnitId}/embedded`
- `POST /{searchUnitId}/failed`

`SearchUnitIndexingService.claimPending()`은 scoped claim과 `expectedIndexVersion`을 사용한다. claim scope에는 `sourceFileIds`, `documentVersionIds`, `parsedArtifactId`, `searchUnitIds`, `sourceFileTypes`, `parserVersions`가 있다.

worker entrypoint는 `python -m app.cli.search_unit_indexing`이다. worker는 core-api에서 SearchUnit을 claim하고, canonical embedding text를 만들고, FAISS와 `ragmeta.chunks`를 갱신한 뒤, core-api에 embedded/failed callback을 보낸다.

### Vector Retrieval / FAISS / ragmeta.chunks

`ai-worker/app/capabilities/rag/retriever.py`의 `Retriever`가 현재 vector retrieval의 중심이다.

- query parser로 normalized query와 metadata filter를 만든다.
- embedder로 query vector를 만든다.
- `FaissIndex.search()`로 row id를 찾는다.
- `RagMetadataStore.lookup_chunks_by_faiss_rows(index_version, row_ids)`로 `ragmeta.chunks`를 조회한다.
- reranker/MMR/RRF가 optional로 붙는다.
- 결과는 `RetrievedChunk`와 `RetrievalReport`로 나온다.

`ragmeta.chunks`는 `index_version`, `faiss_row_id`, `extra_json`으로 FAISS row를 SearchUnit/citation metadata와 연결한다. `V10__ragmeta_chunks_versioned_namespace.sql` 이후 chunk primary key는 `(index_version, chunk_id)`이다.

### Library Search

library search는 Spring/JPA lexical diagnostic이다. `rag_ingestion_retrieval_eval.py`도 기본값으로 `/api/v1/library/search`를 호출하지만, 이 경로는 ingestion/citation smoke 성격이다.

promotion 후보 evidence는 `--retrieval-backend vector` 경로여야 한다. eval/gate는 library-search 결과를 promotion-grade vector evidence로 인정하지 않는다.

### Eval / Gate

주요 파일은 다음이다.

- `ai-worker/eval/harness/rag_ingestion_retrieval_eval.py`
- `ai-worker/eval/harness/rag_ingestion_promotion_gate.py`
- `scripts/rag_build_promotion_gate_metrics.py`
- `scripts/rag_prepare_immutable_baseline.py`

promotion gate는 deterministic/LLM-free이며 다음 조건을 hard-block한다.

- `retrieval_backend != "vector"`
- `embedding_filtered_eval != true`
- `required_embedding_status != "EMBEDDED"`
- `required_index_version` mismatch
- `gate_input_missing_count > 0`
- `required_index_version_mismatch_count > 0`
- `embedding_status_mismatch_count > 0`
- `candidate_index_mismatch_count > 0`
- `indexing_filtered_hit_count > 0`
- hidden leakage 또는 citation/location 필수 metric 누락

### PDF/XLSX Parser Artifacts

PDF:

- `PDF_PARSED_JSON`
- `PDF_PLAINTEXT`
- pipeline versions: `pdf-extract-v1`, `pdf-extract-v2`

XLSX:

- `XLSX_WORKBOOK_JSON`
- `XLSX_MARKDOWN`
- `XLSX_TABLE_JSON`
- pipeline version: `xlsx-extract-v2-hidden-safe`
- hidden policy: `exclude-hidden-v1`
- `.xls` reject, `.xlsx`/read-only `.xlsm` allowed, macros not executed

### Citation / Location Metadata Flow

현재 citation/location은 여러 표면에 흩어져 있다.

- Spring SearchUnit fields: `citation_text`, `location_json`, `location_type`, `parser_version`, `index_version`
- Spring library response: `SearchUnitResponse` + nested `Citation`
- Python vector response: `RetrievedChunk` + `retrieval_result_row()` + `citation_payload()`
- eval vector adapter: `_vector_chunk_to_eval_hit()`
- `ragmeta.chunks.extra_json`: SearchUnit/citation metadata mirror

따라서 공통 Evidence contract의 재료는 있으나, query-time tool graph가 의존할 단일 Evidence schema는 아직 없다고 보는 편이 맞다.

확인된 gap:

- Spring library-search response는 citation/location shape가 비교적 풍부하지만 lexical diagnostic이다.
- Python vector retrieval row는 `citation`/`grounding`을 내보내지만, row-level `citationText`, `locationJson`, `locationType`, `chunkType`, `parserVersion`, `indexVersion`, `sourceFileType`을 공통 Evidence로 강제하지 않는다.
- `grounding_readiness.hasCitation`은 typed locator가 검증됐다는 뜻이 아니라 citation payload가 만들어졌다는 약한 신호에 가깝다.
- DB에는 `search_unit.acl_tags`가 있으나 current import/query path가 실제 tenant/ACL enforcement를 완성했다고 보면 안 된다.
- normalized XLSX table metadata와 SearchUnit evidence 사이의 direct bridge는 아직 POC가 의존할 만큼 단단하지 않다.
- TEXT는 PDF/XLSX처럼 typed `location_json` contract가 명확하지 않다. 첫 POC에서는 TEXT evidence를 fixture/readiness 대상으로 보고, production contract는 별도로 닫아야 한다.

## B. LangChain Adoption Decision

판단: 제한적 비추천, 기본 보류.

LangChain document loader는 현재 parser/import contract와 충돌한다. PDF/XLSX parser는 이미 native artifact와 SearchUnit metadata를 만든다. 특히 XLSX는 hidden sheet/cell policy, macro non-execution, table/cell metadata, formula cached value 같은 보안/품질 contract가 있어서 generic loader로 바꾸면 위험하다.

LangChain vectorstore도 현재 FAISS + `ragmeta.chunks` + `embedding_record` + promotion gate contract와 중복된다. repo의 vector identity는 SearchUnit stable id, index_version, vector_id, embedding_text_sha256, parser_version과 연결되어 있다. 이걸 LangChain vectorstore abstraction 뒤에 숨기면 gate/debug가 약해진다.

LangChain agent 기능도 POC의 첫 선택지는 아니다. 필요한 것은 broad tool-calling agent가 아니라, fail-closed filter와 deterministic verification이 있는 좁은 query-time graph이다.

LangChain을 도입하지 않는 편이 나은 영역:

- PDF/XLSX/TEXT parser
- SearchUnit 생성
- canonical embedding text
- SearchUnit indexing claim/callback
- `ragmeta.chunks` persistence
- promotion/eval/gate
- ACL/tenant/index_version/source_file_type/parser_version filter enforcement

제한적으로 고려 가능한 영역:

- 문서화용 prompt template 또는 output parser helper
- offline 실험에서만 쓰는 adapter
- LangGraph와 독립적인 small utility가 이미 명확한 가치를 보일 때

POC에는 넣지 않는다.

## C. LangGraph Adoption Decision

판단: query-time에 한해 제한적 추천.

현재 repo에는 이미 `ai-worker/app/capabilities/agent/graph_loop/*`에 experimental LangGraph backend가 있다. 다만 이 backend는 기존 AGENT loop를 `initial_retrieve -> aggregate_candidates -> score_quality -> critic -> decide_next_action -> rewrite -> retrieve_again -> synthesize`로 바꿔 실행하는 실험이다. PDF/XLSX/TEXT tool orchestration graph는 아니다.

LangGraph가 적합한 부분:

- query-time PDF/XLSX/TEXT tool routing
- vector search 결과 merge
- no/weak evidence fallback
- deterministic citation verification
- deterministic XLSX table materialization/aggregation
- answer synthesis 전 evidence gating
- human review handoff state
- eval orchestration wrapper

LangGraph를 ingestion core에 넣으면 안 되는 이유:

- ingestion state는 Spring DB와 worker callback contract가 source of truth이다.
- parser/import/indexing/promotion은 idempotency, transaction, claim token, index_version, embedding record로 이미 안전장치가 있다.
- LangGraph checkpoint는 실행 중 query state에는 맞지만, source_file/job/search_unit/index_build lifecycle을 대체하면 DB state와 checkpoint state가 이중 source of truth가 된다.

## D. Candidate Adoption Areas

도입 후보는 query-time RAG orchestration으로 제한한다.

- `pdf_vector_search_tool`
- `xlsx_vector_search_tool`
- `text_vector_search_tool`
- `citation_lookup_tool`
- `xlsx_table_materialize_tool`
- `xlsx_aggregation_tool`
- `evidence_merge_tool`
- `citation_verify_tool`
- `answer_synthesis_node`

구현 방식은 LangGraph node가 직접 DB broad query를 하지 않고, 기존 Spring API나 기존 Python retrieval function을 wrapper로 호출하는 형태가 우선이다.

## E. Forbidden Adoption Areas

다음 영역은 도입 금지다.

- ingestion core를 LangGraph node로 이전
- PDF/XLSX parser를 LangChain loader로 교체
- SearchUnit 생성 로직 변경
- SearchUnit indexing claim/completion callback 변경
- `embedding_record` / `ragmeta.chunks` identity contract 변경
- promotion/eval/gate 우회
- library-search 결과를 promotion-grade evidence로 사용
- agent가 DB를 직접 broad query
- ACL/tenant/index_version/source_file_type/parser_version 필터를 LLM 판단에 맡기기

## Current Agentic Flow Findings

### 1. 현재 단순 텍스트 문서 agentic flow는 어디에 있는가?

`ai-worker/app/capabilities/agent/*`에 있다.

흐름은 다음과 같다.

`TaskRunner -> CapabilityRegistry -> AUTO/AGENT -> AgentRouter -> if/else dispatch -> RAG -> Retriever -> Generator`

핵심 파일:

- `app/services/task_runner.py`: capability resolve 후 `capability.run(...)`
- `app/capabilities/registry.py`: RAG/OCR/MULTIMODAL/AUTO/AGENT 등록
- `app/capabilities/agent/router.py`: rule/LLM router
- `app/capabilities/agent/capability.py`: action별 if/else dispatch와 optional loop
- `app/capabilities/rag/capability.py`: `INPUT_TEXT`를 query로 디코딩하고 `Retriever.retrieve()` 호출

### 2. 그 flow가 PDF/XLSX로 확장되지 못하는 이유는 무엇인가?

현재 AGENT/AUTO는 query-time file/parser tool router가 아니다.

- router의 supported file mime은 image/PDF 중심이고 XLSX가 없다.
- AGENT constructor는 `rag`, `ocr`, `multimodal`만 받으며 `pdf_extract`, `xlsx_extract`를 tool로 받지 않는다.
- `PDF_EXTRACT`와 `XLSX_EXTRACT`는 registry에 독립 capability로 등록되지만 AGENT tool set으로 주입되지 않는다.
- RAG capability는 `INPUT_TEXT`를 query로 읽는 text retrieval path이다.
- PDF/XLSX는 query-time parser call이 아니라 ingestion 후 SearchUnit/vector evidence로 소비해야 한다.

따라서 확장 방향은 parser를 agent에게 맡기는 것이 아니라, 이미 indexing된 PDF/XLSX/TEXT SearchUnit을 source type별 vector search tool로 감싸는 쪽이다.

### 3. PDF/XLSX/TEXT 검색 결과의 공통 Evidence contract는 있는가?

완성된 단일 contract는 없다.

부분 contract는 있다.

- Python `RetrievedChunk`
- Python `retrieval_result_row()` / `citation_payload()`
- Spring `SearchUnitResponse`
- Spring `Citation`
- eval `_vector_chunk_to_eval_hit()`

하지만 query-time graph가 공통으로 검증할 required fields, filter proof, retrieval backend identity, citation verification result까지 포함하는 단일 schema는 아직 없다.

### 4. 없다면 어떤 schema가 필요한가?

최소 Evidence schema는 다음 필드를 가져야 한다.

```json
{
  "evidence_id": "string",
  "retrieval_backend": "vector",
  "rank": 1,
  "scores": {
    "dense": 0.0,
    "sparse": null,
    "rerank": null,
    "final": 0.0
  },
  "source": {
    "source_file_id": "string",
    "source_file_name": "string",
    "source_file_type": "PDF|SPREADSHEET|TEXT",
    "document_id": "string",
    "document_version_id": "string",
    "parser_name": "string",
    "parser_version": "string"
  },
  "index": {
    "index_version": "string",
    "embedding_status": "EMBEDDED",
    "embedding_model": "string",
    "embedding_text_sha256": "string|null",
    "vector_id": "string|null"
  },
  "unit": {
    "search_unit_id": "string",
    "chunk_id": "string",
    "unit_type": "PAGE|PARAGRAPH|TABLE|ROW_GROUP|...",
    "unit_key": "string",
    "chunk_type": "string"
  },
  "content": {
    "text": "string",
    "display_text": "string|null",
    "snippet": "string",
    "citation_text": "string"
  },
  "location": {
    "location_type": "pdf|xlsx|text",
    "location_json": {},
    "page": {},
    "sheet": {},
    "bbox": null
  },
  "policy": {
    "tenant_id": "string|null",
    "acl_tags": [],
    "acl_checked": true,
    "hidden_policy_version": "exclude-hidden-v1|null",
    "required_filters": {
      "index_version": "string",
      "source_file_type": ["PDF"],
      "parser_version": ["string"]
    }
  },
  "verification": {
    "status": "unchecked|verified|rejected",
    "reasons": []
  }
}
```

### 5. vector retrieval backend를 tool로 감쌀 수 있는가?

가능하다. `Retriever.retrieve(query, filters=None)`가 이미 좋은 wrapper boundary다. 다만 현 `RagMetadataStore.doc_ids_matching()`의 filter whitelist는 `domain/category/language`뿐이므로 POC tool은 source type/index_version/parser_version/ACL 필터를 LLM이 만든 free-form filter로 넘기면 안 된다.

우선은 tool wrapper가 `required_index_version`, `allowed_source_file_types`, `allowed_parser_versions`, `tenant_acl_context`를 code-level guard로 받고, 결과 Evidence를 post-filter/verify하는 형태가 안전하다. 운영 후보가 되려면 retrieval 전에 filter가 적용되는 전용 API 또는 metadata filter 확장이 필요하다.

### 6. citation_text/location_json 검증을 별도 node로 뺄 수 있는가?

가능하고, 그렇게 해야 한다.

`citation_verify_tool`은 LLM node가 아니라 code node여야 한다. 검증 항목은 다음이다.

- `citation_text` nonblank
- `location_json` valid JSON
- `location_type`과 `source_file_type` 일관성
- PDF page/bbox field presence
- XLSX sheet/cell_range/table_id field presence
- TEXT section/span locator presence when source type is TEXT
- `embedding_status == EMBEDDED`
- `index_version == required_index_version`
- parser version allowlist
- hidden policy version
- ACL/tenant guard 통과 여부

### 7. xlsx aggregation은 LLM이 아니라 deterministic tool로 처리할 수 있는가?

가능하고, LLM이 하면 안 된다.

LLM은 aggregation 의도를 구조화할 수는 있지만, 실제 table materialization, range selection, type coercion, sum/avg/count/group-by는 deterministic Python/Spring tool이 해야 한다. 특히 hidden row/cell 제외, cached formula value 사용, number/date format 처리, max row/col cap은 code contract여야 한다.

### 8. LangGraph state에는 무엇만 담을 것인가?

LangGraph state에는 query execution state만 담는다.

- request id / trace id
- user/tenant/ACL context의 resolved snapshot
- normalized query
- structured intent
- required filters
- tool call plan
- Evidence list 또는 Evidence refs
- verification results
- bounded table materialization result refs
- aggregation result
- final answer draft
- errors/fallback reasons

담지 말아야 할 것:

- DB credentials
- unbounded DB query results
- source_file/job/search_unit lifecycle state
- promotion/eval/gate state
- checkpoint를 authoritative index state처럼 쓰는 값

### 9. Spring DB 상태와 LangGraph checkpoint 상태가 충돌하지 않는가?

충돌하지 않게 설계할 수 있다. 조건은 checkpoint가 query-run state만 저장하고, Spring DB의 job/source/search_unit/index_build 상태를 대체하지 않는 것이다.

Spring DB는 ingestion/index/promotion source of truth로 유지한다. LangGraph checkpoint는 retry/resume/debug를 위한 transient execution trace로만 둔다. checkpoint에 `index_version`은 읽기 전용 snapshot으로 저장해도 되지만, active index를 바꾸거나 embedding status를 갱신하면 안 된다.

### 10. 이 POC가 ingestion core 작업과 독립적으로 진행 가능한가?

가능하다.

독립 조건:

- 새 feature flag 또는 별도 capability/endpoint로 격리
- 기존 parser/import/SearchUnit/indexing/gate 파일 수정 금지
- 기존 `Retriever`/Spring response를 wrapper로만 사용
- DB schema 변경 없이 시작
- vector-backed Evidence만 운영 후보로 취급
- library-search는 diagnostic fallback 또는 비교용으로만 표시

## H. Risks

- 현 `/api/v1/library/search`는 ACL/tenant/index_version/source_file_type/parser_version fail-closed query API가 아니다.
- current `Retriever`는 source_file_type/parser_version/index_version filter를 first-class query filter로 받지 않는다.
- `ai-worker/pyproject.toml`에는 LangGraph dependency가 없지만, `ai-worker/requirements.txt`에는 기존 experimental agent loop backend용 `langgraph>=0.2.40,<0.3`가 있다. query-time POC는 dependency를 추가하거나 업그레이드하지 않고, 기존 graph backend와 독립된 optional import/skip 경계를 유지해야 한다.
- 기존 `agent/graph_loop`를 그대로 확장하면 AGENT job dispatch semantics가 바뀔 수 있다.
- XLSX aggregation이 LLM prompt로 구현되면 hidden policy, formula/cached value, numeric coercion이 깨질 수 있다.
- LangGraph checkpoint를 Spring lifecycle state처럼 쓰면 state conflict가 생긴다.
- library-search diagnostic 결과를 POC 성공 증거로 과대 해석할 위험이 있다.

## I. Parallel Work Feasibility

이 POC는 ingestion core 작업과 병렬 진행 가능하다.

안전한 병렬화 조건:

- POC branch는 query-time wrapper, Evidence schema, LangGraph graph, tests/docs만 변경한다.
- ingestion core branch는 parser/SearchUnit/indexing/gate를 계속 진행한다.
- 양쪽이 만나는 contract는 read-only Evidence fields와 `index_version`/`parser_version` allowlist뿐이다.
- ingestion core의 candidate indexing lifecycle이 아직 진행 중이어도, POC는 fixture 또는 existing vector index를 사용해 dry-run할 수 있다.

충돌 가능성이 있는 지점:

- `RetrievedChunk`나 `retrieval_contract.py`를 양쪽이 동시에 크게 바꾸는 경우
- `ragmeta.chunks.extra_json` field naming을 바꾸는 경우
- SearchUnit metadata/citation field를 migration 없이 가정하는 경우

## K. Files / Areas Not To Change

다음은 POC에서 변경하지 않는다.

- `core-api/src/main/java/com/aipipeline/coreapi/catalog/application/service/DocumentCatalogService.java`
- `core-api/src/main/java/com/aipipeline/coreapi/catalog/application/service/SearchUnitIndexingService.java`
- `core-api/src/main/java/com/aipipeline/coreapi/catalog/adapter/in/web/SearchUnitIndexingController.java`
- `core-api/src/main/java/com/aipipeline/coreapi/catalog/application/service/RagIndexBuildService.java`
- `core-api/src/main/resources/db/migration/*`
- `ai-worker/app/capabilities/pdf/*`
- `ai-worker/app/capabilities/xlsx/*`
- `ai-worker/app/capabilities/rag/search_unit_indexing.py`
- `ai-worker/app/services/search_unit_indexing_loop.py`
- `ai-worker/app/cli/search_unit_indexing.py`
- `ai-worker/eval/harness/rag_ingestion_promotion_gate.py`
- `scripts/rag_build_promotion_gate_metrics.py`

기존 `ai-worker/app/capabilities/agent/*`도 첫 POC에서는 가급적 변경하지 않는다. 새 query orchestrator를 별도 module로 두고, 기존 AGENT/AUTO semantics와 분리하는 편이 안전하다.

## L. Next Implementation PR Scope

다음 PR의 추천 범위는 작게 잡는다.

포함:

- `docs/rag_framework_adoption_review.md`
- `docs/rag_query_orchestrator_poc_plan.md`
- optional: `ai-worker/app/capabilities/rag_orchestrator/` 아래 no-op skeleton
- Evidence schema dataclass/Pydantic model
- vector search tool wrapper unit tests using fake `Retriever`
- citation verification node unit tests
- xlsx aggregation deterministic helper unit tests using bounded fixture

제외:

- Spring migration
- parser 변경
- SearchUnit 생성 변경
- indexing callback 변경
- promotion gate 변경
- public endpoint default-on
- LangChain loader/vectorstore/agent 도입
