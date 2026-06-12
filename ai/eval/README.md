## 한눈에 보기

| 항목 | 내용 |
|---|---|
| 문서 목적 | RAG 평가 샘플과 진단 결과를 사람이 빠르게 확인하기 위한 README |
| 대상 문서 | TEXT, PDF, XLSX |
| 샘플 수 | 총 64개: TEXT 10개, PDF 20개, XLSX 34개 |
| 보여주는 흐름 | 질문 → 근거 위치 → 응답 |
| 핵심 포인트 | 근거 기반 답변, citation 검증, fail-closed 처리, 한국어 검수 패킷 생성 |
| 운영 반영 여부 | 운영 배포나 공식 성능 지표가 아닌 diagnostic-only 자료 |

샘플은 기존 balanced sample 50개(TEXT 10, PDF 20, XLSX 20)에 v3_22 XLSX display-value/cell-range diagnostic sample 14개를 더한 구성입니다.
`Response` 칸에는 저장 응답, 어댑터 응답 excerpt, 최신 diagnostic answer derivation 출력, stored residual excerpt, 또는 fail-closed 상태가 들어갈 수 있습니다.

PDF에서 목차 점선, 단독 섹션 번호, 페이지 번호, 숫자축처럼 실제 답변 근거로 보기 어려운 content window는 답변처럼 노출하지 않고 `PDF_CONTENT_WINDOW_TOO_THIN`으로 표시합니다.
이런 처리는 성능을 좋아 보이게 만들기 위한 장치가 아니라, 근거가 약한 답변을 막기 위한 방어선입니다.

## Actual RAG Eval Infrastructure

`ai/eval/actual_rag_eval.py` and `python -m ai.scripts.rag_actual_eval`
implement the current pragmatic actual-RAG evaluation loop:

```text
eval dataset -> retrieval surface selection -> BM25/vector/hybrid retrieval -> context assembly -> answer generation -> citation capture -> metrics -> report.json
```

Retrieval backend and retrieval surface are separate. `--retrieval-backend auto`
selects hybrid when vector retrieval is available, while
`--retrieval-surface auto` hard-selects a SourceAtom/EvidenceBundle-backed
source-native corpus when source-native units can be loaded. Routine
source-native retrieval uses bounded deterministic layered retrieval over
source-owned units only, redacts raw local paths in reports, and prefers the
additive non-production BGE-M3 source-native FAISS index when present. Build it
with `--build-source-native-bge-m3-index`; the build embeds source-native units
on CUDA when available and stores a CPU FAISS `IndexFlatIP` sidecar under
`ai/eval/indexes/rag-data-all-source-citable-nonprod-bge-m3-v1`. If that index
is missing, the runner records the diagnostic-hash fallback instead of silently
downgrading to legacy SearchUnit/SearchView. SearchUnit/SearchView is no longer
a routine actual-RAG candidate surface; it remains available only as explicit
legacy/debug comparison with `--legacy-surface-comparison`. SourceAtom and
EvidenceBundle remain the evidence-truth surfaces.

The active service-boundary lane is Weaviate, not Chroma. Use
`--retrieval-backend weaviate-vector|weaviate-bm25|weaviate-hybrid` with
`RAG_VECTOR_DB=weaviate`, `WEAVIATE_URL`, `WEAVIATE_GRPC_PORT`,
`WEAVIATE_COLLECTION_SOURCE_ATOM`, `WEAVIATE_NAMESPACE`, and
`EMBEDDING_MODEL=BAAI/bge-m3`. The Weaviate lane embeds queries locally with
BAAI/bge-m3, sends vector, BM25, or hybrid search requests to Weaviate, and
hydrates candidates only from Weaviate result payloads. It must not invoke the
Python source-native layered retrieval path, local corpus scans, FAISS,
diagnostic hash vectors, or SearchUnit/SearchView as the active candidate
surface. If Weaviate is unavailable or a query fails, the run fails explicitly
with `weaviate_unavailable`; it must not silently fall back to local
source-native retrieval while reporting a Weaviate backend.

The Weaviate index manifest for the direct BGE-M3 lane is
`reports/rag_eval/weaviate_source_atom_index_manifest_nonprod_streaming_full/index_manifest.json`.
It is produced by `ai.scripts.rag_weaviate_source_atom_index` through streaming
sentence-transformers BGE-M3 embedding and batch upsert checkpoints, not by
transferring vectors out of the local source-native FAISS artifact. Resume runs
skip checkpointed SourceAtom IDs before embedding or upserting them again.

Route-selected Weaviate A/B comparison is explicit non-production mode only:
`--weaviate-route-ab-mode text,mixed,routed`. It writes the explicit sidecars
`route_selected_hybrid_evidence_store_ab_report.json` and
`route_selected_hybrid_evidence_store_ab_items.jsonl` beside the normal
`report.json`. Lane A is current full-index hybrid retrieval, Lane B is
TEXT-only retrieval, Lane C is mixed-pool diagnostic retrieval, and Lane D is
deterministic route-selected retrieval. The route taxonomy is conservative:
`source_family` is `TEXT|PDF|XLSX|UNKNOWN`, `granularity` is one of
`paragraph`, `heading_context_block`, `page_block`, `table_summary`,
`table_row`, `cell`, `caption`, `metadata_only`, or `unknown`, and
`retrieval_route` is one of `text_general`, `pdf_paragraph`, `pdf_table`,
`xlsx_table`, `xlsx_cell_trace`, `mixed_fallback`, or `unknown`. The planner
uses query text only and reports that it did not use gold, expected evidence,
qrels, labels, IDs, or legacy outputs. Route filters are pushed to Weaviate
where the schema supports them; Python post-filtering is safety validation
only.

The non-production route-selected v2 schema/index materializes route taxonomy,
safe structural locator metadata, and metadata-only vectorization policy in
`SourceAtomNonprodRouteSelectedV2`. Its manifest records
`index_object_count=136280`, `vectorized_object_count=136184`,
`metadata_only_object_count=96`, and `vectorized_object_ratio=0.999296`;
individual XLSX cells are metadata-only by default while paragraphs,
heading-context blocks, and table rows remain vectorized. The current
route-selected A/B report is guardrail-clean, shows no TEXT degradation, removes
mixed-route source-family pollution, reduces same-document duplicate pressure
after bounded duplicate collapse, and recommends
`promote_route_selected_nonprod_default` as the next non-production step. The
default active path is still unchanged until that promotion is explicitly wired.

Dataset rows may be incomplete. Fatal schema errors are limited to unusable
items such as missing `id`, missing `query`, invalid JSON/JSONL, or malformed
field types. Missing `answerability`, `expected_answer`, aliases,
`expected_evidence`, or citation gold are non-fatal warnings.

Metrics are intentionally separated:

| Tier | Purpose |
|---|---|
| strict | Clean-denominator metrics such as exact/alias correctness, evidence recall@k, citation precision/recall, abstention accuracy, and strict E2E success. Strict answer, evidence, citation, and E2E denominators require human-owned answerability labels. |
| provisional | Broader best-effort RAG signals such as judged answer correctness, anchor-gated weak evidence recall, resolved-evidence recall, citation matches to resolved evidence, and provisional E2E success. Provisional E2E requires the provisional answer judge to pass; weak evidence or resolved evidence alone is insufficient. Text-only weak evidence and expected-evidence resolution require non-generic anchors and all numeric/date anchors from the expected answer/evidence for high-confidence matches. |
| inferred-answerable | Unknown-answerability rows with expected answer and expected evidence can be scored in a separate inferred tier for iteration only. The gold answerability label is not mutated. |
| diagnostic | Pipeline and data-quality signals such as empty retrieval/generation/citations, schema warnings, full-corpus review-only evidence ID resolution counts, gold missing counts, canonical failure labels, answer/context consistency, citation/retrieved-context consistency, source-native Hit@K/nDCG over post-retrieval expected-evidence diagnostics, and `mmr_selected` ranking diagnostics. MMR is recorded as a selection strategy, not as MRR/reciprocal-rank. These consistency and retrieval diagnostics are not official quality metrics. |

Default runs use a deterministic heuristic provisional judge. An opt-in
localhost-only local LLM judge is available with `--judge-mode local-llm`, but
automated tests use deterministic fixtures and do not require external model
calls.

Routine runs now default to a single primary artifact:
`reports/rag_eval/<run_id>/report.json`. That one file embeds run metadata,
items, metrics, comparison rows, evidence-resolution diagnostics, backend
comparison metrics, GPU/vector preflight, guardrails, assumptions,
limitations, and next repair targets. Legacy output mode can still emit the
older `rag_eval_items.jsonl`, `rag_eval_summary.json`, Markdown, and evidence
sidecars for compatibility/debugging, but it is not the default.

Expected-evidence resolution is deterministic and non-mutating. The CLI default
scope is `full-corpus`; current evidence-gate runs pass
`--evidence-resolution-scope full-corpus-review-only` explicitly. Retrieved-only
behavior remains available with `--evidence-resolution-scope retrieved-only`,
and old query-index diagnostics remain explicit with `index-candidate-lookup`
or `both`. Expected answers, aliases, expected evidence, qrels, row IDs, query
IDs, target IDs, and baseline top-k are not retrieval candidate-generation
inputs. Resolution scoring remains diagnostic and non-mutating.

Human review output is opt-in with `--write-human-review-packet`. When set,
the runner writes exactly one additional CSV packet,
`reports/rag_eval/<run_id>/human_review_packet.csv`, with blank human-owned
decision fields. It does not write CSV+JSONL+Markdown+summary sidecars in
single mode and does not create gold mappings, qrels, answerability labels,
official metrics, retriever-ranking claims, product-success evidence, or
live-readiness claims.

A reviewed mapping file can be ingested only through the separate explicit
`--reviewed-evidence-mapping-csv` input. That path reads human-owned decisions
from a separate CSV, creates a run-local derived overlay plus
`reviewed_evidence_mapping_patch.json`, reports `denominator_changes`, and
does not overwrite the original dataset or mutate gold/qrels/labels. Blank
human decision rows and machine recommendations used as human decisions are
rejected.

Legacy-free parity quality gates are explicit comparison runs, not routine
output. Pass `--quality-gate-baseline <report-or-run-dir>` or
`--quality-gate-baseline auto` to run the selected source-native actual-RAG lane
first and then compare its item-level evidence package against a frozen
SearchUnit/SearchView report. The baseline is replayed only after retrieval and
generation complete; it is never a candidate-generation input. This writes
`legacy_real_rag_quality_gate_report.json` and
`legacy_real_rag_quality_gate_items.jsonl` beside `report.json`, with answer
parity, evidence package status, citation support, diagnostic critic fields,
not-comparable reasons, and guardrail status.

`--evidence-gate-mode off|diagnostic|enforce` controls the bounded
SourceAtom/EvidenceBundle evidence gate for the real-RAG lane. `off` preserves
existing answers, `diagnostic` records allow/block decisions without changing
answers, and `enforce` replaces unsupported answers with the bounded abstention
`제공된 근거만으로는 답할 수 없습니다.`. The gate uses only query text,
generated answer, selected source-native evidence, citation targets, source IDs,
text hashes, and query/answer anchors. Expected answers/evidence, qrels, labels,
legacy outputs, row IDs, and target IDs remain evaluation-only and are not
enforcement inputs.

Accumulated runs stay under `reports/rag_eval/<run_id>/` and can now append a
machine-readable run registry plus latest pointers:

```bash
python -X utf8 -m ai.scripts.rag_actual_eval \
  --dataset ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv \
  --top-k 10 \
  --retrieval-surface auto \
  --retrieval-backend auto \
  --output-mode single \
  --resolve-expected-evidence \
  --evidence-resolution-scope full-corpus-review-only \
  --quality-gate-baseline auto \
  --append-registry \
  --write-latest \
  --compare-to previous
```

The current registry/index surfaces are `reports/rag_eval/runs.jsonl`,
`reports/rag_eval/latest.json`, dataset-specific pointers such as
`reports/rag_eval/latest_text_gold.json`, and `reports/rag_eval/README.md`.
Actual eval now supports `--retrieval-backend bm25|vector|hybrid|auto`.
`auto` prefers hybrid when the local vector backend is available; otherwise it
records the vector/GPU failover reason and falls back without silence. The
current source-native vector path can load the additive non-production BGE-M3
FAISS `IndexFlatIP` built from SourceAtom/EvidenceBundle-owned units; the older
`codex-diagnostic-hashing-vector-v1` index remains a diagnostic fallback and
legacy comparison point only. Local FAISS is not an external production
VectorDB. The external VectorDB lane for this goal is Weaviate. FAISS is
demoted to diagnostic/offline baseline only for that lane, and Chroma was not
selected because Weaviate gives the clearer service boundary, collection
schema, metadata filtering, and BM25/vector hybrid search contract needed for
Agentic RAG scale-out. External VectorDB use must be explicitly
non-production, must report `external_vector_db.invoked=true`, and is recorded
separately from the local FAISS path.

Comparison sections and backend comparison metrics are non-production
diagnostics only. They do not promote strict, provisional, inferred-answerable,
retrieval, vector, hybrid, or diagnostic metrics to official metric,
product-success, promotion, or live-readiness evidence.

Phase 0-2 source-native contracts are documented in
`docs/rag_eval/roadmap_source_native.md`,
`docs/rag_eval/metric_contract.md`, and
`docs/rag_eval/failure_taxonomy.md`.

## 실제 질문·근거·응답 샘플

아래 표는 실제 query → evidence → response 흐름을 빠르게 확인하기 위한 샘플입니다.
대표 benchmark가 아니며, 공식 denominator나 promotion evidence로 사용하지 않습니다.

| Track | Query | Evidence surface | Response |
|---|---|---|---|
| TEXT | 자동판매기 미궁 방랑 애니 3기 방영 시기는 문서에 어떻게 적혀 있어 | TEXT chunk/source context: text_namu_v2_1, 92c87287 | 자동판매기로 다시 태어난 나는 미궁을 방랑한다를 원작으로 하는 TV 애니메이션 시리즈 중 제3기의 방영 시기는 2026년 4월입니다. |
| TEXT | 유우야키의 나이와 생일은 어떻게 적혀 있어 | TEXT chunk/source context: text_namu_v2_1, 7be08880 | 유우야키의 나이는 16세이고 생일은 9월 29일입니다. |
| TEXT | 엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와 | TEXT chunk/source context: text_namu_v2_1, 1048928e | 애드버리는 앨리슨 실리스미스(카메오)로 등장합니다. |
| TEXT | 소드아트 오디널 스케일은 어떤 극장판을 가리켜 | TEXT chunk/source context: text_namu_v2_1, 65f737bb | 소드 아트 온라인의 극장판은 2017년 2월 18일에 일본에서 개봉한 극장판 애니메이션이다. |
| TEXT | 실바니안 실크 고양이 가족 설명은 어떤 성격과 역할을 말해 | TEXT chunk/source context: text_namu_v2_1, 18d62717 | diagnostic residual: stored LLM response excerpt; bucket=LLM_SYNTHESIS_REGRESSED; 유럽판에서 실크 고양이 소년은 상냥하고 배려심이 넘치며, 소녀는 패션 디자이너를 꿈꾼다. |
| TEXT | 미츠하는 타키를 만나려고 어디로 향했어 | TEXT chunk/source context: text_namu_v2_1, 2b77d0ce | diagnostic residual: stored LLM response excerpt; bucket=LLM_SYNTHESIS_REGRESSED; 미츠하는 자신과 몸이 바뀌고 있는 타키를 실제로 만나기 위해 도쿄로 향했다. |
| TEXT | 마키노 유이 김정선 작사 노래 정보 | TEXT raw source locator: 6ec273bc, hash 2aa4a177 | 노래는 마키노 유이/김정선, 작사는 카와이 에리, 한국어 개사는 고정민, 작곡/편곡은 쿠보타 미나로 표시됩니다. |
| TEXT | 금빛 물결 노래 한국어 개사 관련 정보는 무엇인가요? | TEXT raw source locator: e992d216, hash ffd821e0 | 한국어 개사는 고정민으로 표시되며, 노래는 아라이 아키노/장아름, 작사/작곡은 아라이 아키노로 표시됩니다. |
| TEXT | 온지 마사유키 작화감독 정보 알려주세요. | TEXT raw source locator: 4354d136, hash 9d72960a | 전화 총 작화감독은 온지 마사유키(音地正行)입니다. |
| TEXT | 교토 애니메이션에서 제작한 연애 게임 원작 학원편 애니메이션의 감독은 누구인가요? | TEXT raw source locator: 4d07e639, hash e4dab086 | 감독은 이시하라 타츠야이다. |
| PDF | 2월 실업률은 전년 같은 달보다 어떻게 변했나요? | PDF page citation: 2021_03_recent_economic_trends.pdf p.8 (paragraph) | 실업률은 4.9%로 전년동월대비 0.8%p 상승 |
| PDF | 1월 산업활동에서 생산 지표는 어떻게 움직였나요? | PDF page citation: 2021_03_recent_economic_trends.pdf p.5 (paragraph) | 1월 산업활동에서 광공업 생산, 서비스업 생산, 건설투자는 감소했습니다. |
| PDF | 2020년 한국 원달러 기말 환율은 얼마인가요? | PDF page citation: 2021_03_recent_economic_trends.pdf p.65 (table_body) | 2020년 한국 원달러 기말 환율은 1,088.0입니다. |
| PDF | 2024년 수출입차 금액은 얼마인가요? | PDF page citation: 2025_12_recent_economic_trends.pdf p.61 (table_body) | 2024년 수출입차 금액은 6,836.1입니다. |
| PDF | 산림청 정책연구용역 관리규정 별지 제1호서식에 대해 알려주세요. | PDF raw/source locator: prism_1400000-202500030_d0150010_000_1_과제_신청서_및_세부연구계획서_임업수출교역팀.pdf p.1 (text_block), srcatom c7a9c32a | ■ 산림청 정책연구용역 관리규정 [별지 제1호서식] <제정 2017.00.00.> Page 1. |
| PDF | 경쟁입찰 시 적정 수행기관 선정을 위한 협상에 의한 계약 추진 방법은 무엇인가요? | PDF raw/source locator: prism_1833000-202600003_d0150013_000_1_2025년...원회_과제_선정_결과보고서.pdf p.2 (text_block), srcatom fe8a4ad3 | - 경쟁입찰에 의해 진행될 경우, 적정 수행기관 선정을 위해 협상에 의한 계약 추진 Page 2. |
| PDF | 사업보고서 내용을 확인하고 싶은데 어떤 정보가 포함되어 있나요? | PDF raw/source locator: dart_dongsung_business_report_2026_20260407_correction.pdf p.3 (text_block), srcatom 70c5c5f4 | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| PDF | 투자자 보호를 위하여 필요한 사항은 무엇인지 자세히 알려주세요. | PDF raw/source locator: dart_dongsung_business_report_2025_20250321.pdf p.2 (text_block), srcatom 9505a327 | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| PDF | 정관의 주요 내용은 무엇이며, 어떤 사항을 다루고 있습니까? | PDF raw/source locator: dart_dongsung_auditor_audit_report_2025.pdf p.2 (text_block), srcatom b84b4232 | 본인은 동성제약주식회사의 감사로서 2024년 1월 1일부터 2024년 12월 31일 까지 제68기 사업년도의 회계 및 업무에 대한 감사실시 결과를 다음과 같이 보고합니다. Page 2. |
| PDF | 감사보고서에서 확인해야 할 핵심적인 사항은 무엇인가요? | PDF raw/source locator: dart_dongsung_audit_report_2025.pdf p.3 (text_block), srcatom 20613607 | 감사의견 우리는 동성제약 주식회사(이하 "회사")의 재무제표를 감사하였습니다. Page 3. |
| PDF | 감사보고서의 주요 내용은 무엇이며 어떤 점을 다루고 있습니까? | PDF raw/source locator: dart_dongsung_audit_report_2025.pdf p.3 (text_block), srcatom 20613607 | 감사의견 우리는 동성제약 주식회사(이하 "회사")의 재무제표를 감사하였습니다. Page 3. |
| PDF | 내부감시장치에 대한 감사의 의견서는 어떻게 구성되어 있습니까? | PDF raw/source locator: dart_dongsung_auditor_internal_control_opinion_2025.pdf p.1 (text_block), srcatom 7fd1d022 | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| PDF | 내부회계관리제도운영보고서의 핵심 사항을 찾아주세요. | PDF raw/source locator: dart_dongsung_internal_accounting_report_2025.pdf p.1 (text_block), srcatom a8829e35 | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| PDF | 보고기간 종료일 현재 재무상태표에 실제로 존재하는 항목을 확인해 주세요. | PDF raw/source locator: dart_dongsung_internal_accounting_report_2025.pdf p.4 (text_block), srcatom 220deb01 | 재무상태표에 기록되어 있는 자산, 부채 및 자본은 보고기간 종료일 현재 실제로 존재하여야 한다. Page 4. |
| PDF | 영업보고서의 주요 내용은 무엇이며 어떤 정보를 포함하고 있습니까? | PDF raw/source locator: dart_dongsung_audit_report_2025.pdf p.3 (text_block), srcatom 20613607 | 감사의견 우리는 동성제약 주식회사(이하 "회사")의 재무제표를 감사하였습니다. Page 3. |
| PDF | 전자공시시스템에서 특정 정보를 찾는 방법을 알려주세요. | PDF raw/source locator: dart_dongsung_sales_report_2025.pdf p.4 (text_block), srcatom c67e2b12 | 전자공시시스템 dart.fss.or.kr Page 3 Page 4. |
| PDF | 조달사업의 외부 환경변화에 따른 보고서의 내용은 무엇을 다루나요? | PDF raw/source locator: prism_1230000-202500002_d0150004_001_1_최종보고서...수수료_운영개선_방안_최종.pdf p.5 (text_block), srcatom 2da88112 | ▣ 조달사업의 내·외부 환경변화에 따른 조달특별회계 운영개선 방안 Page 5. |
| PDF | 국립청소년활동시설 이용 인원의 지역별 분포 현황을 알려주세요. | PDF raw/source locator: prism_1384000-202500002_d0150004_002_1_정책환경_...개선_연구_최종보고서_인쇄.pdf p.3 (text_block), srcatom 6217f8ff | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| PDF | 주민등록인구 변화에 대한 현황 기준을 확인하고 싶습니다. | PDF raw/source locator: prism_1384000-202500002_d0150004_002_1_정책환경_...개선_연구_최종보고서_인쇄.pdf p.4 (text_block), srcatom 1de1c37b | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| PDF | 제1장 서론 부분의 주요 내용은 무엇을 다루고 있습니까? | PDF raw/source locator: alio_2023_management_evaluation_report.pdf p.4 (text_block), srcatom 990b970f | 2023년도 기타공공기관 경영실적평가 실시 개요 Page 4. |
| XLSX | 2019년 2월 5호선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A352:D401 D352 | 2019년 2월 5호선의 승차총승객수는 15,446,522명입니다. |
| XLSX | 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까? | XLSX sheet/range/cell: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A702:J751 C702 | 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 41786입니다. |
| XLSX | 2017년 12월 9호선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A452:D501 D452 | 8,048,476명입니다. |
| XLSX | 2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까? | XLSX sheet/range/cell: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A752:J801 G752 | 해뜨는요양원2의 시도 시군구 법정동명은 대구광역시 북구 복현동입니다. |
| XLSX | 2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까? | XLSX sheet/range/cell: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A802:J851 J802 | 대구광역시 수성구 파동로51길 96 (파동)입니다. |
| XLSX | 2018년 7월 8호선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A402:D451 D402 | 2018년 7월 8호선의 승차총승객수는 5,630,084명입니다. |
| XLSX | 2018년 5월 의정부경전철의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A552:D601 D552 | 1,095,397명입니다. |
| XLSX | 2018년 11월 3호선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A52:D101 D52 | 17,956,555명입니다. |
| XLSX | 2019년 4월 안산선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A152:D201 D152 | 4,230,809명입니다. |
| XLSX | 2018년 9월 일산선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A202:D251 D202 | 3,258,215명입니다. |
| XLSX | 2019년 3월에 지정된 신논현요양원의 설치신고일자는 언제입니까? | XLSX sheet/range/cell: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A1052:J1101 I1052 | 2019-03-15입니다. |
| XLSX | 2022년 5월에 지정된 인천은빛요양원의 기관별 상세주소는 무엇입니까? | XLSX sheet/range/cell: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A1102:J1151 J1102 | 인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)입니다. |
| XLSX | 2008년 6월에 지정된 청운노인요양원의 지정일자는 정확히 언제입니까? | XLSX sheet/range/cell: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A2:J51 H2 | 2008-06-25입니다. |
| XLSX | 2017년 11월 1호선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A2:D51 D2 | 8,633,618명입니다. |
| XLSX | 2019년 5월 우이신설선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A602:D602 D602 | 1,469,681명입니다. |
| XLSX | 2018년 4월 경인선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A102:D151 D102 | 10,356,250명입니다. |
| XLSX | 2019년 2월 수인선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A302:D351 D302 | 1,124,736명입니다. |
| XLSX | 2008년 6월에 지정된 청운노인요양원의 기관별 상세주소는 무엇입니까? | XLSX sheet/range/cell: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A2:J51 J2 | 서울특별시 종로구 비봉길 76 (구기동)입니다. |
| XLSX | 2015년 6월에 지정된 부여효요양원의 기관별 상세주소는 무엇입니까? | XLSX sheet/range/cell: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A5002:J5051 J5002 | 충청남도 부여군 석성면 왕릉로 773 (석성면)입니다. |
| XLSX | 대덕구 컴퓨터 윈도우탑재 제품 정보 알려주세요. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A9852:J9901 A9852 | diagnostic-only fail-closed: XLSX_QUERY_ANCHOR_MISSING |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 셀 A1 값 알려줘 | SourceAtom: atom-xlsx-a1-int; Book.xlsx / Sheet1 A1; mode=SINGLE_CELL_VALUE | 42 |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 셀 B1 퍼센트 표시값 알려줘 | SourceAtom: atom-xlsx-b1-percent; Book.xlsx / Sheet1 B1; mode=SINGLE_CELL_VALUE | 12.5% |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 셀 C1 통화 표시값 알려줘 | SourceAtom: atom-xlsx-c1-currency; Book.xlsx / Sheet1 C1; mode=SINGLE_CELL_VALUE | $1,234.50 |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 셀 D1 날짜 표시값 알려줘 | SourceAtom: atom-xlsx-d1-date; Book.xlsx / Sheet1 D1; mode=SINGLE_CELL_VALUE | 2023-07-17 |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 셀 D2 일시 표시값 알려줘 | SourceAtom: atom-xlsx-d2-datetime; Book.xlsx / Sheet1 D2; mode=SINGLE_CELL_VALUE | 2023-07-17 09:30 |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 셀 E1 빈 셀인지 알려줘 | SourceAtom: atom-xlsx-e1-blank; Book.xlsx / Sheet1 E1; mode=SINGLE_CELL_VALUE | E1 셀은 비어 있습니다. |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 셀 F1 수식 캐시 표시값 알려줘 | SourceAtom: atom-xlsx-f1-formula-cached; Book.xlsx / Sheet1 F1; mode=SINGLE_CELL_VALUE | 168 |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 범위 A1:B2 값을 표로 알려줘 | SourceAtoms: atom-xlsx-a1-int, atom-xlsx-a2-text, atom-xlsx-b1-percent, atom-xlsx-b2-merged; mode=SMALL_RANGE_TABLE | A1: 42<br>B1: 12.5%<br>A2: 서울<br>B2: Header total |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 범위 A1:E20 값을 요약해줘 | SourceAtoms: atom-xlsx-summary-1..5; Book.xlsx / Sheet1 A1:E20; mode=BOUNDED_RANGE_SUMMARY | Book.xlsx 시트 Sheet1 범위 A1:E20의 일부 값은 A1이 42, B1이 12.5%, C1이 $1,234.50, D1이 2023-07-17 등으로 요약될 수 있습니다. |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 셀 G1 값 알려줘 | SourceAtom: atom-xlsx-g1-missing-format; Book.xlsx / Sheet1 G1; mode=FORMAT_METADATA_UNAVAILABLE | 9999.5 |
| XLSX v3_22 | 이 표에서 선택한 범위 값을 알려줘 | No selected SourceAtom; mode=AMBIGUOUS_RANGE_CONTEXT_REQUIRED | diagnostic-only fail-closed: 답변하려면 파일/문서, 시트, 범위, 페이지 또는 셀을 더 구체적으로 지정해 주세요. |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 범위 A1:Z1000 값을 전부 알려줘 | SourceAtom: atom-xlsx-large-range; Book.xlsx / Sheet1 A1:Z1000; mode=UNSUPPORTED_RANGE_TOO_LARGE | diagnostic-only fail-closed: UNSUPPORTED_RANGE_TOO_LARGE |
| XLSX v3_22 | Sheet1 시트 셀 A1 값 알려줘 | No selected SourceAtom; mode=AMBIGUOUS_RANGE_CONTEXT_REQUIRED | diagnostic-only fail-closed: 답변하려면 파일/문서, 시트, 범위, 페이지 또는 셀을 더 구체적으로 지정해 주세요. |
| XLSX v3_22 | Book.xlsx 시트 Sheet1 셀 A1 값 알려줘 | No selected SourceAtom; mode=FORMAT_METADATA_UNAVAILABLE; index unavailable case | diagnostic-only fail-closed: 요청한 위치를 찾지 못했습니다. 제공된 위치 범위 안에서 답변하지 않습니다. |

## 평가 경계

이 README는 외부에 보여줄 수 있는 샘플 설명서이지만, 공식 성능 점수표는 아닙니다.
아래 경계는 의도적으로 강하게 유지합니다.

| 항목 | 정책 |
|---|---|
| 대표 benchmark 여부 | 아님 |
| promotion evidence 여부 | 아님 |
| production routing | `false` |
| official metric | `false` |
| official metric input rows | `0` |
| product success evidence allowed | `false` |
| fine-tuning readiness | readiness-only |
| fine-tuning 실행 여부 | 실행하지 않음 |
| live DB index cache readiness | `false` |
| TEXT/PDF/XLSX metric 통합 | 하나의 headline score로 합치지 않음 |

## 정리와 보고 표면

현재 RAG diagnostic `current`는 `v6_9_answer_quality_gate_packet_nonprod`입니다. `ai/eval/reports/rag-ingestion/**`의 machine report/status/run sidecar는 generated/local-only diagnostic evidence로 취급하고, 사람이 읽는 최신 상태와 정리 근거는 `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, `docs/rag-ingestion-triage.md`에 둡니다.

삭제가 애매한 legacy 또는 generated diagnostic artifact는 hold가 기본입니다. 안전 삭제는 `.pytest_cache`, `__pycache__`, bytecode, `core-api/target`, `frontend/app/dist` 같은 transient cache/build output으로 제한하며, gold/qrels/official denominator/eval query/source registry/index/silver/current report/status 표면은 정리 대상이 아닙니다.
