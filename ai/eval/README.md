# Evaluation harness

`ai/eval`은 RAG/OCR 실험을 로컬에서 반복하고, 결과를 production 코드와 섞지 않기 위한 평가 영역입니다. `app/` 런타임은 eval 코드를 import 하지 않고, eval 쪽도 production 상태를 임의로 바꾸지 않는 것을 기본 경계로 둡니다.

Last updated: 2026-05-21 KST.

## 현재 읽는 순서

루트 README의 지표 스냅샷에서 여기로 넘어왔다면 아래 순서로 보면 됩니다.

1. 이 파일의 `현재 상태`와 `지표 해석`에서 denominator와 promotion 경계를 확인합니다.
2. `v3_7_2 source registry-backed retrieval smoke`에서 새 silver query 표면이 실제 retrieval loop에 들어간 결과를 봅니다.
3. 세부 run ledger는 `../../docs/rag-ingestion-progress.md`, `../../docs/rag-ingestion-measurements.md`, `../../docs/rag-ingestion-triage.md`로 내려갑니다.
4. machine-readable 최신 상태는 `reports/rag-ingestion/status.jsonl`과 각 run summary JSON을 확인합니다.

## 현재 상태

현재 primary track은 `v3_7_2` source registry-backed retrieval smoke report입니다. 핵심 질문은 점수 개선이 아니라, PDF/XLSX 쿼리가 먼저 자기 문서 family 후보 안으로 들어오고, 검색된 SearchView가 SourceAtom으로 hydrate되어 EvidenceBundle과 citation render까지 끊기지 않고 이어지는지입니다. `v3_7_1` index는 이 smoke의 입력 artifact로 유지됩니다.

| 항목 | 현재 값 | 해석 |
|---|---|---|
| 현재 run | `official_answer_citation_agentic_loop_run_v3_7_2_source_registry_backed_retrieval_smoke_report` | PDF/XLSX는 query source-family routed top-k를 primary로 쓰고, SourceAtom hydration, EvidenceBundle render, citation render survival을 track별로 기록 |
| 입력 index | `indexes/rag-data-all-source-citable-nonprod-v1` | `v3_7_1` all-source citable non-production SearchView export |
| SearchViews | `136,280` | TEXT `135,608`, PDF `329`, XLSX `343` |
| Source registry | `source_registry/source_atom_registry_v1.jsonl` | canonical evidence/citation truth |
| v3_7_2 query surfaces | official `29` + silver diagnostic `1000` | official/gold는 sealed no-regression only, silver는 coverage/failure discovery only |
| Silver query surface | `LOCAL_LLM_NATURAL_SILVER_1000_REGENERATED_AND_POLISHED` | 1000 unique query hashes; XLSX 325 rows polished; plain Korean/digit/punctuation validation pass |
| Contract path | SearchView -> SourceAtom -> EvidenceBundle -> Citation render | vector metadata를 evidence truth로 쓰지 않고 source registry에서 hydrate |
| Promotion readiness | explicitly not opened | answer quality, prompt tuning, gold/qrels mutation, comparable live measurement 모두 닫힘 |

## 지표 해석

현재 README에 노출하는 숫자는 서로 다른 표면을 섞지 않습니다. answer/citation score, exact-evidence retrieval smoke, local LLM documentation loop, Phase 7 historical retrieval tuning은 서로 다른 목적의 결과입니다.

| Surface | Denominator | Metric | Current reading |
|---|---:|---|---|
| Official first-run baseline | 29 official rows | PASS `8/29` | 초기 baseline. `BLOCKED_OR_PARTIAL`; tuning/promotion/gold mutation 없음 |
| v3_2_7 answer/citation closure | 29 official rows | Lane A/B/C `24/29`, `27/29`, `27/29` | diagnostic-only. Lane A replay, Lane B retrieval top-k, Lane C query-bound oracle를 합산하지 않음 |
| v3_4_3 exact-evidence retrieval smoke | 28 included rows | Hit@1 `27/28`, Hit@3 `28/28`, Hit@5 `28/28`, MRR@5 `27.5/28`, binary exact-evidence nDCG@5 `0.9868189197704093` | source-bound exact-evidence smoke와 regression guard. 대표 제품 성능 아님 |
| README local LLM response loop | 100 docs sample rows | p95 `0.464s`, p99 `0.516s`, max `0.528s` | query + SearchView evidence만 넣은 documentation-only loop. official metric 아님 |
| v3_7_1 source-first index | 136,280 SearchViews | metric not computed | retrieval/answer/citation 성능 측정 전 단계. vector metadata는 canonical citation source가 아님 |
| v3_7_2 contract smoke | 1,029 query surfaces | returned/same-track/target/contract survival counts | PDF `same-track@k=329/329`, target@k `112/329`; XLSX `same-track@k=344/344`, target@k `10/344`. `topk_returned_count`는 반환 수일 뿐 정답 hit가 아니며 headline aggregate score 아님 |

`nDCG`는 현재 full graded relevance nDCG가 아니라 `binary exact-evidence nDCG@5`입니다. future graded nDCG는 별도 relevance/answerability label 정책이 생긴 뒤에만 같은 이름으로 비교해야 합니다.

## Denominator 정책

- Official answer/citation denominator는 `eval_queries/official_denominator_registry.json`에서 시작하며 현재 29 rows입니다.
- Track mix는 PDF `4`, TEXT `6`, XLSX `19`입니다.
- Retrieval smoke denominator는 `v3_4_2` exact-evidence qrels에서 나온 28 included rows입니다. `gq_auto_010`은 standalone query missing year 이유로 제외됐고, failure/negative로 세지 않습니다.
- `v3_7_2` source registry-backed smoke는 official/gold query를 회귀 확인용으로만 읽고, silver 1000은 취약 locator와 adapter gap 발견용으로만 읽습니다.
- `v3_7_2`의 `topk_returned_count`는 SearchView 후보가 몇 개 반환됐는지입니다. PDF/XLSX primary top-k는 `query_source_family_routed_for_structured_tracks`로 읽고, 기존 all-source mixed 결과는 `mixed_retrieval_baseline`으로만 남겨 TEXT dominance를 진단합니다.
- 현재 mixed baseline은 PDF same-track@k `9/329`, XLSX same-track@k `30/344`로 여전히 TEXT에 잠기지만, routed primary에서는 PDF/XLSX 모두 same-track@k가 query_count와 같습니다. target@k는 별도 ranking/materialization 문제로 분리해 읽습니다.
- Silver/weak-noisy rows는 tuning 후보나 documentation sample이 될 수 있지만 official denominator, official qrels, promotion evidence가 아닙니다.
- Lane A/B/C score는 진단 표면입니다. 하나의 official score로 접지 않습니다.

## 문서 타입별 evidence 구조

TEXT, XLSX, PDF는 같은 vector score 하나로만 읽지 않습니다. 검색 후보는 공통 SearchView로 다룰 수 있지만, 답변과 citation 검증은 타입별 evidence 구조로 돌아옵니다.

| Track | 후보 표면 | evidence truth | citation에서 꼭 남길 것 |
|---|---|---|---|
| TEXT | chunk/search view | SourceAtom text locator | document/version, chunk or text locator, source context |
| XLSX | cell/range search view | workbook/sheet/range/cell payload | workbook, sheet, range, matched cell, row label, target column/value |
| PDF | page/block/bbox search view | PDF file identity + source text locator | file identity, page, physical page index, bbox, region type, matched text |

이 경계 때문에 vector metadata에는 canonical citation payload를 저장하지 않습니다. vector DB는 후보 생성 장치이고, 답변 근거는 source registry hydration 결과를 기준으로 확인합니다.

## v3_7_2 source registry-backed retrieval smoke

이 루프는 새로 재생성한 silver 1000개를 포함해 총 1029개 query surface를 실제 SearchView retrieval path에 태운 diagnostic smoke입니다. answer quality나 citation precision을 채점하지 않고, SearchView 후보가 SourceAtom으로 hydrate되고 EvidenceBundle 및 citation render까지 살아남는지만 track별로 분리해 봅니다.

| Track | Query count | Routed same-track@k | Target@k | Contract survival target@k | Top failure |
|---|---:|---:|---:|---:|---|
| TEXT | 356 | 356 | 20 | 20 | track_mismatch |
| PDF | 329 | 329 | 112 | 112 | snapshot_only |
| XLSX | 344 | 344 | 10 | 10 | snapshot_only |

Silver query surface quality check: rows `1000`, unique query hashes `1000`, duplicate hashes `0`, XLSX polished rows `325`. The current query set has no Latin/Japanese/Hanja or disallowed punctuation violations; repeated domain starts remain visible in source-heavy XLSX/PDF areas, so this is still diagnostic silver, not human gold.

## 100-row local LLM 응답 샘플

아래 표는 v3_7_2 이전 README에 표시할 근거 샘플을 채우기 위해 한 번 실행한 historical documentation-only 루프입니다. gold `25`행과 당시 silver `75`행을 사용했고, 로컬 OpenAI-compatible llama.cpp endpoint `http://localhost:8081/v1`의 `gemma4-e2b-local`에 `temperature=0`, `max_tokens=96`으로 요청했습니다. 이 루프의 wall-clock latency는 p95 `0.464s`, p99 `0.516s`, max `0.528s`였습니다. 현재 silver query 표면은 위 v3_7_2 smoke artifacts를 기준으로 읽습니다.

중요한 경계는 다음과 같습니다. 이 표는 official promotion metric 이 아니며, gold/silver/query/label 을 변경하지 않습니다. 모델 입력에는 `query + SearchView evidence`만 넣었고, `expected_answer` 또는 silver `expected_answer_draft`는 보내지 않았습니다. 표의 locator와 응답은 Markdown 표 렌더링을 위해 줄바꿈과 `|` 문자만 정리했습니다.

| Set | Count | Track mix | Input policy |
|---|---:|---|---|
| gold | 25 | PDF 3, TEXT 6, XLSX 16 | official question-gold v2 query + SearchView evidence |
| silver | 75 | PDF 25, TEXT 25, XLSX 25 | weak/noisy silver query + SearchView evidence |

<details>
<summary>100개 쿼리와 실제 로컬 LLM 응답 보기</summary>

| # | Set | Track | ID | Query | Evidence locator | Actual local LLM response |
|---:|---|---|---|---|---|---|
| 1 | gold | PDF | `gq_auto_024` | 1월 산업활동에서 생산 지표는 어떻게 움직였나요? | 9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.pdf p.5 | 1월 산업활동에서 광공업 생산, 서비스업 생산, 건설투자는 감소했습니다. |
| 2 | gold | PDF | `gq_auto_030` | 2020년 한국 원달러 기말 환율은 얼마인가요? | 9acfa9e6-36ff-4217-a212-c5688c1e88f2-2021_03_recent_economic_trends.pdf p.65 | 2020년 한국 원달러 기말 환율은 1,088.0입니다. |
| 3 | gold | PDF | `gq_pdf_section_question_001` | 2024년 수출입차 금액은 얼마인가요? | 492ca671-e252-45a1-998d-f9a095855b82-2025_12_recent_economic_trends.pdf p.61 | 2024년 수출입차 금액은 6,836.1입니다. |
| 4 | gold | TEXT | `text_namu_v2_0005` | 자동판매기 미궁 방랑 애니 3기 방영 시기는 문서에 어떻게 적혀 있어 | docv_sha256_c9c18da61956de64:4fb4c291efb8b088 | 자동판매기로 다시 태어난 나는 미궁을 방랑한다를 원작으로 하는 TV 애니메이션 시리즈 중 제3기의 방영 시기는 2026년 4월입니다. |
| 5 | gold | TEXT | `text_namu_v2_0012` | 유우야키의 나이와 생일은 어떻게 적혀 있어 | docv_sha256_c9c18da61956de64:474e24d5441aeacd | 유우야키의 나이는 16세이고 생일은 9월 29일입니다. |
| 6 | gold | TEXT | `text_namu_v2_0014` | 엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와 | docv_sha256_c9c18da61956de64:ffa9998ff6067ea2 | 애드버리는 앨리슨 실리스미스로 등장합니다. |
| 7 | gold | TEXT | `text_namu_v2_0017` | 실바니안 실크 고양이 가족 설명은 어떤 성격과 역할을 말해 | docv_sha256_c9c18da61956de64:73557605809705ab | 실바니안 실크 고양이 소년은 상냥하고 배려심이 넘치며, 소녀는 패션 디자이너가 꿈이고, 아기는 반짝이는 것을 좋아합니다. |
| 8 | gold | TEXT | `text_namu_v2_0077` | 미츠하는 타키를 만나려고 어디로 향했어 | docv_sha256_c9c18da61956de64:4035db0b8289111a | 미츠하는 타키를 실제로 만나기 위해 도쿄로 향했습니다. |
| 9 | gold | TEXT | `text_namu_v2_0084` | 소드아트 오디널 스케일은 어떤 극장판을 가리켜 | docv_sha256_c9c18da61956de64:214902951f6edb9e | 소드 아트 온라인 스케일은 2017년에 일본에서 개봉한 소드 아트 온라인의 극장판 애니메이션을 가리킵니다. |
| 10 | gold | XLSX | `gq_auto_012` | 2019년 2월 5호선의 승차총승객수는 몇 명입니까? | 철도:A352:D401:D352 | 2019년 2월 5호선의 승차총승객수는 15,446,522명입니다. |
| 11 | gold | XLSX | `gq_auto_018` | 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까? | 일반현황:A702:J751:C702 | 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 41786입니다. |
| 12 | gold | XLSX | `gq_auto_022` | 2017년 12월 9호선의 승차총승객수는 몇 명입니까? | 철도:A452:D501:D452 | 2017년 12월 9호선의 승차총승객수는 8,048,476명입니다. |
| 13 | gold | XLSX | `gq_auto_023` | 2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까? | 일반현황:A752:J801:G752 | 해뜨는요양원2의 시도 시군구 법정동명은 대구광역시 북구 복현동입니다. |
| 14 | gold | XLSX | `gq_auto_028` | 2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까? | 일반현황:A802:J851:J802 | 해오름요양원의 기관별 상세주소는 대구광역시 수성구 파동로51길 96 (파동)입니다. |
| 15 | gold | XLSX | `gq_auto_031` | 2018년 7월 8호선의 승차총승객수는 몇 명입니까? | 철도:A402:D451:D402 | 2018년 7월 8호선의 승차총승객수는 5,630,084명입니다. |
| 16 | gold | XLSX | `gq_auto_034` | 2018년 5월 의정부경전철의 승차총승객수는 몇 명입니까? | 철도:A552:D601:D552 | 2018년 5월 의정부경전철의 승차총승객수는 1,095,397명입니다. |
| 17 | gold | XLSX | `gq_auto_035` | 2018년 11월 3호선의 승차총승객수는 몇 명입니까? | 철도:A52:D101:D52 | 2018년 11월 3호선의 승차총승객수는 17,956,555명입니다. |
| 18 | gold | XLSX | `gq_auto_037` | 2019년 4월 안산선의 승차총승객수는 몇 명입니까? | 철도:A152:D201:D152 | 2019년 4월 안산선의 승차총승객수는 4,230,809명입니다. |
| 19 | gold | XLSX | `gq_auto_038` | 2018년 9월 일산선의 승차총승객수는 몇 명입니까? | 철도:A202:D251:D202 | 2018년 9월 일산선의 승차총승객수는 3,258,215명입니다. |
| 20 | gold | XLSX | `gq_auto_043` | 2019년 3월에 지정된 신논현요양원의 설치신고일자는 언제입니까? | 일반현황:A1052:J1101:I1052 | 신논현요양원의 설치신고일자는 2019년 3월 15일입니다. |
| 21 | gold | XLSX | `gq_auto_044` | 2022년 5월에 지정된 인천은빛요양원의 기관별 상세주소는 무엇입니까? | 일반현황:A1102:J1151:J1102 | 인천은빛요양원의 기관별 상세주소는 인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)입니다. |
| 22 | gold | XLSX | `gq_xlsx_date_number_format_001` | 2008년 6월에 지정된 청운노인요양원의 지정일자는 정확히 언제입니까? | 일반현황:A2:J51:H2 | 청운노인요양원의 지정일자는 2008년 6월 25일입니다. |
| 23 | gold | XLSX | `gq_xlsx_lookup_001` | 2017년 11월 1호선의 승차총승객수는 몇 명입니까? | 철도:A2:D51:D2 | 2017년 11월 1호선의 승차총승객수는 8,633,618명입니다. |
| 24 | gold | XLSX | `gq_xlsx_lookup_004` | 2019년 5월 우이신설선의 승차총승객수는 몇 명입니까? | 철도:A602:D602:D602 | 2019년 5월 우이신설선의 승차총승객수는 1,469,681명입니다. |
| 25 | gold | XLSX | `gq_xlsx_lookup_005` | 2018년 4월 경인선의 승차총승객수는 몇 명입니까? | 철도:A102:D151:D102 | 2018년 4월 경인선의 승차총승객수는 10,356,250명입니다. |
| 26 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_757f0d6540835485` | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF:docv_pdf_sha256_c962c6c4670fb6d6:su_v3_5_3_pdf_757f0d6540835485:da35af9e1c719996d805ae02f530e41fdced9502e6efb7eeb118 | 사 업 보고서가 확인됩니다. |
| 27 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_887389cc5127724e` | PDF 2쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF:docv_pdf_sha256_c962c6c4670fb6d6:su_v3_5_3_pdf_887389cc5127724e:9fe6ec29cca513850bcdb84f2a94cd09c8568116b5ab2be243bc | 제시된 근거에는 PDF 2쪽 text_block에서 확인되는 내용이 없습니다. |
| 28 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_e9502f273e7e7463` | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 75a7abdb | PDF:docv_pdf_sha256_0a8c344dd9089e62:su_v3_5_3_pdf_e9502f273e7e7463:75a7abdbb6e97f7f1c654a8ae8d98d017436663203610f14547b | 정 관 |
| 29 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_d7e771a4faab32b5` | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 ed3786f8 | PDF:docv_pdf_sha256_ea9a423704676764:su_v3_5_3_pdf_d7e771a4faab32b5:ed3786f81f8599fedfb9897bf1559ad63c46c500b0ef134d5a0f | PDF 1쪽 text_block에서 확인되는 내용은 감사보고서입니다. |
| 30 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_c1ad1edbae354990` | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 cc47e81b | PDF:docv_pdf_sha256_7f315f5e8d34785b:su_v3_5_3_pdf_c1ad1edbae354990:cc47e81be24f72a5d36a5c6c9fe2af12627ce1434cbf8d8eb328 | 감사의 감사보고서가 확인됩니다. |
| 31 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_d90488a0ed563cf7` | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 41d86dbe | PDF:docv_pdf_sha256_6a70a93b17c870d6:su_v3_5_3_pdf_d90488a0ed563cf7:41d86dbea91f4e9a87af9d5d13fbba6f372b2bc16fc564ef1aad | 내부감시장치에 대한 감사의 의견서가 확인됩니다. |
| 32 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_acc949d5f3f54f4f` | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 cec077b7 | PDF:docv_pdf_sha256_a24485cb5b76a5b4:su_v3_5_3_pdf_acc949d5f3f54f4f:cec077b7fbdee6eec731be34ed7e51abb16068f8a82fdf8beeb3 | 내부회계관리제도운영보고서의 1쪽 내용입니다. |
| 33 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_b2d1a09a93906603` | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 2c192fad | PDF:docv_pdf_sha256_f58c23b21a513536:su_v3_5_3_pdf_b2d1a09a93906603:2c192fade15642501bd1f7497e6a330c336299dc6f766dd02f1a | PDF 1쪽 text_block에서 확인되는 내용은 영업보고서입니다. |
| 34 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_956c669e64669362` | PDF 34쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF:docv_pdf_sha256_5046feb2c9a53668:su_v3_5_3_pdf_956c669e64669362:ca5d8c225a3f4ff179727125b599986dc965fa8e79672f2b10dd | PDF 34쪽 text_block에서 확인되는 내용은 이혼율입니다. |
| 35 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_8dab82c054779092` | PDF 3쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF:docv_pdf_sha256_c4bc16f248a4e636:su_v3_5_3_pdf_8dab82c054779092:802ecdd8ecf2e8208a471e12c2e90bd29a19dea186c46b7f731e | 제1장 서론에 대한 내용이 있습니다. |
| 36 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_3a515b577a0e8d56` | PDF 4쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF:docv_pdf_sha256_c4bc16f248a4e636:su_v3_5_3_pdf_3a515b577a0e8d56:63c332cc5a45ab4a07e27b754b40f706ad11ff4a031f739904ec | PDF 4쪽 text_block에서 확인되는 내용은 분야별 전문가 인터뷰 개요입니다. |
| 37 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_a82bb63fd8f925cc` | PDF 2쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 0d8d93c7 | PDF:docv_pdf_sha256_e484657886a7c908:su_v3_5_3_pdf_a82bb63fd8f925cc:0d8d93c73e463988b10d92b6df1c2168292e541e01148569d90b | 제안 개요에 관한 내용입니다. |
| 38 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_d88225c359307f9e` | PDF 2쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 0d154426 | PDF:docv_pdf_sha256_0d6f55d1550bb33d:su_v3_5_3_pdf_d88225c359307f9e:0d15442622c56acd51c5e56aad39a7b87eaa0adb86b160e2bd6f | 제1절 추진배경 및 필요성에 대한 내용이 있습니다. |
| 39 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_9699f486ad9c7c3f` | PDF 6쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF:docv_pdf_sha256_d6f9f3fdc772d786:su_v3_5_3_pdf_9699f486ad9c7c3f:032f182d4afd970592a9afcc1ff459e17124a98f6d0254ed6a41 | 제1장 서론이 있습니다. |
| 40 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_df0cff560cbdfc43` | PDF 9쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF:docv_pdf_sha256_08e4c3ae72c22dd6:su_v3_5_3_pdf_df0cff560cbdfc43:f2fd0dbdd3ea23cfb0a0c4b45c9120f80cbe820fdd3181bdf1fe | 근거 부족 |
| 41 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_f028e11d4db104ae` | PDF 4쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 82ef2650 | PDF:docv_pdf_sha256_364e295a54a4deaa:su_v3_5_3_pdf_f028e11d4db104ae:82ef2650744fcc4bd1b407f3b325423007968dbf65d3d56f0cde | 근거 부족 |
| 42 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_58ceb63d164d846c` | PDF 5쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF:docv_pdf_sha256_af0271f1f89bccc3:su_v3_5_3_pdf_58ceb63d164d846c:63e9c5ff0c0c68a00c6fc9769e09f940126b0aade795d940ea14 | 제시된 근거는 PDF 5쪽 text_block에 대한 내용을 포함하고 있지 않습니다. |
| 43 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_fd58e26cc00c3464` | PDF 6쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 5ac390f0 | PDF:docv_pdf_sha256_af0271f1f89bccc3:su_v3_5_3_pdf_fd58e26cc00c3464:5ac390f0e0ed9fecda16103af83a38f5814c71456d4d43e70681 | 제시된 근거만으로는 PDF 6쪽 text_block에서 확인되는 내용을 알 수 없습니다. |
| 44 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_6e939e922e8815b0` | PDF 4쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 80e892ed | PDF:docv_pdf_sha256_6d455cd427f21d0f:su_v3_5_3_pdf_6e939e922e8815b0:80e892ed9e07f542bef1f599eaff3a5c12cfed2f477056495506 | 제1절 과업개요에 대한 내용이 확인됩니다. |
| 45 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_fe41567737d21f6e` | PDF 5쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 fcd8d23a | PDF:docv_pdf_sha256_6d455cd427f21d0f:su_v3_5_3_pdf_fe41567737d21f6e:fcd8d23ae6a894457a9ebe873f489c1e848036ac214a148254ac | 표 1은 부문별 감축 목표를 나타냅니다. |
| 46 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_e36807fd0a23a7bd` | PDF 6쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 82d388e0 | PDF:docv_pdf_sha256_6d455cd427f21d0f:su_v3_5_3_pdf_e36807fd0a23a7bd:82d388e0fdadcdd4bced5f6afdcaba11de09afea62ec3f969616 | 제시된 근거는 표 30의 내용이며, PDF 6쪽 text_block의 위치 82d388e0에 대한 구체적인 내용을 확인할 수 없습니다. |
| 47 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_0a12b6f91f5e9079` | PDF 4쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 52dc6054 | PDF:docv_pdf_sha256_df0eed84ddf20b3f:su_v3_5_3_pdf_0a12b6f91f5e9079:52dc6054c1b97effe55e38e961a2dafc234158a98b9904339bed | 제시된 근거만으로는 PDF 4쪽 text_block에서 확인되는 내용을 알 수 없습니다. |
| 48 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_4c90faf672a12c69` | PDF 5쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 2f468559 | PDF:docv_pdf_sha256_df0eed84ddf20b3f:su_v3_5_3_pdf_4c90faf672a12c69:2f46855907097cc575a1adcb0ab1182f385dc6d8f239765ca5b4 | 세종시민 대상 환경교육 인식조사에 대한 내용이 5쪽에 확인됩니다. |
| 49 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_cc7617d1d5bcde41` | PDF 6쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 90a94029 | PDF:docv_pdf_sha256_df0eed84ddf20b3f:su_v3_5_3_pdf_cc7617d1d5bcde41:90a94029aa3e50e88c1d2e368d180c12a6a0580ab81465cfbb28 | 표 1은 세종특별자치시 환경교육 지원 조례 2020년 개정 내용에 관한 것입니다. |
| 50 | silver | PDF | `v3_6_1_weak_noisy_silver_v3_5_3_pdf_f3ca1326cdbbe61b` | PDF 3쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 8427c89c | PDF:docv_pdf_sha256_ce9437c5f541ce8e:su_v3_5_3_pdf_f3ca1326cdbbe61b:8427c89c8650282ea7a1008aeaab63914d4c8701d2024dcdf4f7 | 제시된 근거에는 PDF 3쪽 text_block의 내용이 포함되어 있지 않아 확인할 수 없습니다. |
| 51 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000002` | 텍스트 조각 6ec273bc에서 확인되는 내용은 무엇인가요? | chunk 6ec273bc | 텍스트 조각 6ec273bc에서 확인되는 내용은 노래의 작사, 작곡, 편곡 정보와 일본어 가사 일부입니다. |
| 52 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000003` | 텍스트 조각 6d7911eb에서 확인되는 내용은 무엇인가요? | chunk 6d7911eb | 텍스트 조각 6d7911eb에서 확인되는 내용은 "鮮やかに 回り出した日々 いつも いつでも 愛が満ちていた きっと spirale あたたかな 毎日を重ねたら いつの間にか 遠くに来ていたのね 覚えていますか? あの夜 初めて見た きらめきを 星降る桃源郷 みんなで向かった"입니다. |
| 53 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000005` | 텍스트 조각 e992d216에서 확인되는 내용은 무엇인가요? | chunk e992d216 | 텍스트 조각 e992d216에서 확인되는 내용은 '金の波 千の波'입니다. |
| 54 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000008` | 텍스트 조각 a838a261에서 확인되는 내용은 무엇인가요? | chunk a838a261 | 텍스트 조각 a838a261에서 확인되는 내용은 노래의 가사입니다. |
| 55 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000009` | 텍스트 조각 d411b7e7에서 확인되는 내용은 무엇인가요? | chunk d411b7e7 | 텍스트 조각 d411b7e7에서 확인되는 내용은 노래입니다. |
| 56 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000010` | 텍스트 조각 a5eb5182에서 확인되는 내용은 무엇인가요? | chunk a5eb5182 | 텍스트 조각 a5eb5182에서 확인되는 내용은 노래의 작사, 작곡, 편곡 정보와 가사 일부입니다. |
| 57 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000011` | 텍스트 조각 4354d136에서 확인되는 내용은 무엇인가요? | chunk 4354d136 | 텍스트 조각 4354d136에서 확인되는 내용은 전화 총 작화감독이 온지 마사유키이며, 제1화의 제목은 "その やがて訪れる春の風に... 그 이윽고 찾아올 봄바람에..."이고, 제2화의 제목은 "その 笑顔のお客さまは... 그 미소짓는 손님은..."입니다. |
| 58 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000013` | 텍스트 조각 8674df01에서 확인되는 내용은 무엇인가요? | chunk 8674df01 | 텍스트 조각 8674df01에서 확인되는 내용은 이노우에 히데키의 4화가 뛰어난 작화로 화제를 불렀으며, 사토 준이치가 이후의 시리즈는 3기 4화의 작화에 맞췄다는 것입니다. |
| 59 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000016` | 텍스트 조각 4d07e639에서 확인되는 내용은 무엇인가요? | chunk 4d07e639 | 텍스트 조각 4d07e639는 CLANNAD의 학원편 일부분을 원작으로 하는 TV 애니메이션입니다. |
| 60 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000017` | 텍스트 조각 12df9bc1에서 확인되는 내용은 무엇인가요? | chunk 12df9bc1 | 텍스트 조각 12df9bc1에서 확인되는 내용은 아버지와의 불화로 농구선수라는 꿈을 접은 오카자키 토모야가 고등학교에서 불량아로 유명하며, 개학 첫날 후루카와 나기사를 만나는 내용입니다. |
| 61 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000018` | 텍스트 조각 97ac5ddd에서 확인되는 내용은 무엇인가요? | chunk 97ac5ddd | 텍스트 조각 97ac5ddd에서 확인되는 내용은 2007년 3월 교토판 Kanon의 방영 종료 후 간단한 PV를 보여주며 제작이 발표되어 동년 10월부터 방영되었고, 감독은 이시하라 타츠야, 캐릭터 디자인 및 총 작화 감독은 이케다 카즈미, 각본은 시모 후미히코가 모든 에피소드를 집 |
| 62 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000019` | 텍스트 조각 a9fef59a에서 확인되는 내용은 무엇인가요? | chunk a9fef59a | 텍스트 조각 a9fef59a에서 확인되는 내용은 블루레이가 2010년 4월 30일부로 발매되었고 후속작 애프터 스토리의 BD-BOX판은 2011년 4월 20일에 발매되었다는 것입니다. |
| 63 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000020` | 텍스트 조각 3b56206f에서 확인되는 내용은 무엇인가요? | chunk 3b56206f | 텍스트 조각 3b56206f에서 확인되는 내용은 판매량과 BD BOX 수에 대한 정보, 단역 성우들에 대한 언급, 그리고 주인공이 토모야이기 때문에 해설이나 독백은 거의 토모야가 한다는 내용입니다. |
| 64 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000021` | 텍스트 조각 cbee17e6에서 확인되는 내용은 무엇인가요? | chunk cbee17e6 | 텍스트 조각 cbee17e6에서 확인되는 내용은 등장인물 부분입니다. |
| 65 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000022` | 텍스트 조각 d578b5a2에서 확인되는 내용은 무엇인가요? | chunk d578b5a2 | 텍스트 조각 d578b5a2에서 확인되는 내용은 '벚꽃이 흩날리는 언덕길에서'입니다. |
| 66 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000023` | 텍스트 조각 1ebe776c에서 확인되는 내용은 무엇인가요? | chunk 1ebe776c | 텍스트 조각 1ebe776c에서 확인되는 내용은 '思い出の庭を'입니다. |
| 67 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000026` | 텍스트 조각 6372029d에서 확인되는 내용은 무엇인가요? | chunk 6372029d | 텍스트 조각 6372029d에서 확인되는 내용은 나기사가 병으로 쓰러졌던 원작과 달리 후코가 사라질 때까지 함께하고, 후코의 권유로 토모야가 나기사를 이름으로 부르는 등 둘의 사이가 가까워지며, 원작 상당수 루트의 중요 이벤트인 창립제는 애니메이션에서 이때만 등장한다는 것입니다. |
| 68 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000027` | 텍스트 조각 71969830에서 확인되는 내용은 무엇인가요? | chunk 71969830 | 텍스트 조각 71969830에서 확인되는 내용은 이치노세 코토미가 루트와 후코의 연극부 가입 권유를 통해 얽히게 된다는 것입니다. |
| 69 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000029` | 텍스트 조각 b95b6d4d에서 확인되는 내용은 무엇인가요? | chunk b95b6d4d | 텍스트 조각 b95b6d4d에서 확인되는 내용은 후지바야시 쿄와 루트의 스토리를 일부 포함한 오리지널 스토리, 그리고 농구 시합 장면의 퀄리티가 높고 쿄의 부르마와 니삭스 차림을 볼 수 있어 호평받은 화입니다. |
| 70 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000030` | 텍스트 조각 7710b5be에서 확인되는 내용은 무엇인가요? | chunk 7710b5be | 텍스트 조각 7710b5be에서 확인되는 내용은 토모야가 나기사만을 그리워하고, 마지막에 학교에 다시 나온 나기사와 함께 토모요의 시합을 구경하는 모습을 보면서 쿄, 료, 토모요가 토모야를 포기하게 된다는 것입니다. |
| 71 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000031` | 텍스트 조각 ede5ee0d에서 확인되는 내용은 무엇인가요? | chunk ede5ee0d | 텍스트 조각 ede5ee0d에서 확인되는 내용은 나기사가 연극을 할 때까지의 스토리와 후코 루트에서 이미 창립제가 있었기 때문에 해당 축제가 문화제로 변경되었다는 것입니다. |
| 72 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000033` | 텍스트 조각 4abb0f04에서 확인되는 내용은 무엇인가요? | chunk 4abb0f04 | 텍스트 조각 4abb0f04에서 확인되는 내용은 애니메이션에서 전부 짤려나간 토모야의 '나르시스트 나기사' 계획이 '나르시스트 나기사 번외편'(유도한 사람이 메이라서)이긴 하지만 나오는 유일한 화입니다. |
| 73 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000034` | 텍스트 조각 b2677157에서 확인되는 내용은 무엇인가요? | chunk b2677157 | 텍스트 조각 b2677157에서 확인되는 내용은 BD/DVD 수록 번외편(24화)으로, 원작의 토모요 루트를 1화로 압축한 것으로 본편과는 상관없이 원작 팬들을 위한 서비스편이며 학생회장 선거가 끝난 시점부터 토모요 애프터 바로 전까지의 이야기를 담고 있습니다. |
| 74 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000035` | 텍스트 조각 14648bfa에서 확인되는 내용은 무엇인가요? | chunk 14648bfa | 텍스트 조각 14648bfa는 CLANNAD ~AFTER STORY~에 대한 평가를 포함하고 있습니다. |
| 75 | silver | TEXT | `v3_6_1_weak_noisy_silver_v3_5_0_text_namu_v4_000036` | 텍스트 조각 383ba6fc에서 확인되는 내용은 무엇인가요? | chunk 383ba6fc | 텍스트 조각 383ba6fc에서 확인되는 내용은 비평적, 상업적으로 상당한 성공을 거두었으며, 작화, 연출, 미장센, 감정 묘사가 뛰어난 수준이고, 18화의 일제히 차이는 히로인들의 오열 장면이 웬만한 로맨스 영화보다도 애절한 장면으로 평이 높으며, 토모요의 액션씬, |
| 76 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_faa35306153780bb` | Sheet1 A5952:J6001에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:396d7a86-b1ef-4934-b4c6-b70c71a805b8:8a88ea98ff34471db7924c6a7666f653c7c37aa0f13bf6c45f56e3b9f37bcdfd | 제시된 근거에는 Sheet1 A5952:J6001에 대한 정보가 포함되어 있지 않습니다. |
| 77 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_c09c900641f199f6` | Sheet1 A1452:J1501에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:d0d678eb-9a58-4b76-a50f-52de51a5fbbf:79bff1145589ad11ad7a8885f4c0c34dd5b82e59c715e53c8aa4569292d63258 | 근거 부족 |
| 78 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_a5ec1d29a4a49096` | Sheet1 A5552:J5601에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:d5cdab7d-0927-4904-aa8f-e74cc5db44ec:9c6e6249f8c2fdd2678e1c804c8557ddb0e3d45ea939c1387d5cd40341cb39d3 | 근거 부족 |
| 79 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_63475cc6c38e14ea` | Sheet1 A9902:J9951에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:e8ca572e-b8e6-44a9-abdc-9c5f91de06e1:21e33b29bb2cdfe2258caf8d15368cc730ca7903a29f55bc7363d38aa6e7d8ec | 근거 부족 |
| 80 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_5c029509e6d8576b` | 일반현황 A5902:J5951에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:2c70cfe3-e153-4c65-8d47-4c996aa6c7cf:80b2fa4d0f50e35a4cdb2274e5b6b224007ef49b03130e6bc2714e8b34a231ca | 제시된 근거에는 일반현황 A5902:J5951에 대한 구체적인 내용이 포함되어 있지 않습니다. |
| 81 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_80951c51dd7cbbde` | Sheet1 A9602:J9651에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:7dd14cd6-d65a-4a76-b6ea-efd958642ca9:f1461739c8b1cf481dc0e39d68ab8f024f95d6b5c99a0510326b1d566f9e4c21 | 근거 부족 |
| 82 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_5c79879f844c701f` | 일반현황 A7502:J7551에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:14ca326c-6f94-4334-ac30-f96618552296:49d5dcd4f6fa45d01ecd21c5c152305d462e9b1212204d93dce69ed6fd6a8cb8 | 제시된 근거에서 일반현황 A7502:J7551에 해당하는 내용은 확인할 수 없습니다. |
| 83 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_dd604e09016943ec` | Sheet1 A7252:J7301에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:5a888276-f9a5-4435-87a5-8e1749bf5c7a:079ba6e5ddbe45dd32f76d803a14c2ac8cebf476aec2b11e49968705c8745429 | 근거 부족 |
| 84 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_d78c6f5bc6a91905` | 일반현황 A4902:J4951에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:8eea1c0a-3a66-4479-9bdf-c55d711d1c4b:a43686c7b8c9bbcb02e790104386d8dbdcdbf02f4988f8a483074ae96dc1ecbf | 제시된 근거에는 일반현황 A4902:J4951에 대한 구체적인 내용이 포함되어 있지 않습니다. |
| 85 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_e68bc116978cd331` | Sheet1 A7202:J7251에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:07bba0f6-46e8-4ed9-b95c-f24ff674780d:c3b482dfefcbfa4b8879669804f3ddff7c2cd52d502f853490048c6bb6e6fd1b | 근거 부족 |
| 86 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_5d15318a577b9145` | 일반현황 A5452:J5501에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:0b558dd2-e531-4e7d-a5e0-b6775814e8cb:8ce0324f56914156f6a95038ad428f4ca5f145d441f7947629f4698037c2e36b | 제시된 근거에서 일반현황 A5452:J5501에 해당하는 내용은 확인할 수 없습니다. |
| 87 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_8d0b9cf34abbfeac` | 일반현황 A5952:J6001에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:27053d1b-8fd0-4db5-af0c-05c6339860ba:f00113be6fa6817a41a4a2bf2e701d859b070efbfb091dcb3e9c1f724c2389a0 | 제시된 근거에는 일반현황 A5952:J6001에 대한 내용은 포함되어 있지 않습니다. |
| 88 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_f8dd0be78bfa397b` | 일반현황 A3702:J3751에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:2d90bc3f-4480-40d6-9027-6cc4aced66b3:5422de9e48036a1b6bae627eba672830fac43d36132629eef4d18fc91531a196 | 일반현황 A3702:J3751에서 확인되는 내용은 경기도 광주시 초월읍에 위치한 효심요양원 정보입니다. |
| 89 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_6c5b77dc308cc1f1` | Sheet1 A3852:J3901에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:fa0bf712-dc3e-4f24-81f9-09304f0e5546:94c0348fa17b80c8ec73eaa32add2dba4d8ff45a829db8d9e66c9e6eadb370e5 | 근거 부족 |
| 90 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_e874168f8c8d5196` | 일반현황 A1452:J1501에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:4f3c9f9b-f08a-4771-91fa-68902e97592b:603f1e38a80e2ae27384928306d09e9e5737d78258b0ad1edb7478c6dacc8d19 | 제시된 근거에는 일반현황 A1452:J1501에 대한 구체적인 내용은 포함되어 있지 않습니다. |
| 91 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_79c88d780f92e301` | Sheet1 A6002:J6051에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:53c7eeec-152f-46f5-b33f-871b686e6856:40c7c172a0b280b3c3e490cddcc8eb0d77cc7b69eabc05a4c2f6219dc8d839db | 근거 부족 |
| 92 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_0fd8c611a3f22afe` | Sheet1 A5902:J5951에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:da177b11-cdbb-4469-a932-8f2fd05ecde4:0b78eb4fbcb063763ff1d1e7434fc0eef4a8f9b1df69ff9c5d9edb2235c4b089 | 근거 부족 |
| 93 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_8fff95d29d3cb090` | 일반현황 A9202:J9251에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:0e8f2b4a-ff91-4f68-b694-f5b4f18d2e96:8b4cba69e4d9cb43560f16edc6e286370ce93150a86b100b6dcd7e0e8dfb93f6 | 제시된 근거에는 일반현황 A9202:J9251에 대한 정보가 포함되어 있지 않습니다. |
| 94 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_1c5a4287f2684721` | 일반현황 A5702:J5751에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:2d76b924-690d-4f0e-a04e-5dcfc90069c6:d56b2fb1f3d81e59c2228a80bb6f7ef3142fe420eae82930fac3a191eae68b92 | 제시된 근거에는 일반현황 A5702:J5751에 대한 구체적인 내용은 포함되어 있지 않습니다. |
| 95 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_9fe1894462b910ba` | Sheet1 A5402:J5451에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:ca2704d4-88fa-4a63-8a74-2943b78f8c79:d84cb2d5715627a1150298f3dfa988ef54698902d3c5c27725f1669ef61d6d66 | 근거 부족 |
| 96 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_dec93800b74f2efd` | Sheet1 A6552:J6601에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:d24fa867-e773-4f61-8db1-0fd659eea3f8:1ab9cc1fd90a6c14aeeba74ccc94f8fcf04e2e6209a3709b42fd1fe4c41ca2f7 | 근거 부족 |
| 97 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_121b649e4b2addd2` | Sheet1 A1752:J1801에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:2354482c-9441-4dc9-b1e8-08a22aff3d46:f18002cd498e5d658129a0ae8b0b4cdf7e76880ad2aab030a41f50a681dec304 | 근거 부족 |
| 98 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_2458be332907681f` | Sheet1 A502:J551에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:64a662c2-8388-4ad2-9646-133814427c34:44838761ff023aa6dff118f88ab82494cca32c7ccb69a0260d1209c97c1765dd | 근거 부족 |
| 99 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_0d90a2b4d13257fb` | Sheet1 A1052:J1101에서 확인되는 내용은 무엇인가요? | XLSX:docv_2bc2cb4df8c629e4:638e17a2-94b2-4fca-9efe-9af01e18ccfd:b81341f87fe2a6e9af240bb218fc64163acf9796396dfdd3e12c35fe73703779 | 근거 부족 |
| 100 | silver | XLSX | `v3_6_1_weak_noisy_silver_v3_5_2_xlsx_f13934938a90474d` | 일반현황 A9502:J9551에서 확인되는 내용은 무엇인가요? | XLSX:docv_7bddd99c39ffdf1a:6af2499c-1f53-4e01-99c8-8859c6bdc731:ac454bcf97c9f5dd16357d113271cbbfe215d16870e41f6683eb7eaef029803d | 제시된 근거에는 일반현황 A9502:J9551에 대한 구체적인 내용은 포함되어 있지 않습니다. |

</details>

루프 당시 repo 밖 임시 산출물에서 계산한 입력 JSONL SHA-256은 `fe4cc70fb7cb6d565c818f79b1a815742defa9ebc8e61c61f08726572225790a`이고, 로컬 LLM 출력 JSONL SHA-256은 `c2722bfbc85bef845825748e8b983ab3a4e485692c793436c45ed245274d8e0b`입니다.

## Active와 historical 경계

현재 이 파일의 기본 독해 표면은 `v3_7_2` source registry-backed retrieval smoke report와 그 입력인 `v3_7_1` source-first citable index입니다. Phase 7 v4, Phase 2A reranker, anime/namespaced legacy corpus 실험은 historical 또는 별도 track으로만 읽습니다.

| 영역 | 현재 판단 |
|---|---|
| `v3_7_2` source registry-backed retrieval smoke | 현재 RAG ingestion contract-survival report |
| `v3_7_1` source registry/index | `v3_7_2`의 immutable input index |
| Phase 7 v4 retrieval recommendation | historical retrieval tuning context. `candidate_k=40`, MMR on, recommended `mmr_lambda=0.70`은 v3.7 metric이 아님 |
| Phase 2A reranker latency/accuracy | legacy reranker experiment. 현재 production/default path 아님 |
| anime/namespaced legacy corpora | historical reproduction/debug context. 현재 source-registry denominator와 섞지 않음 |

## 디렉토리 길찾기

| Path | 역할 | 현재 주의점 |
|---|---|---|
| `eval_queries/` | official denominator, gold/review/silver candidate query files | gold/label/policy를 임의 변경하지 않음 |
| `source_registry/` | SourceAtom registry와 build inventory | 현재 citation/evidence hydration truth |
| `indexes/rag-data-official-denominator-v1/` | 29-row official source-bound SearchUnit index | protected regression scope |
| `indexes/rag-data-all-source-citable-nonprod-v1/` | 136,280 SearchView all-source diagnostic index | non-production only; v3_7_2 smoke input |
| `reports/rag-ingestion/status.jsonl` | compact machine-readable status ledger | routine status는 여기에 compact event로 남김 |
| `reports/rag-ingestion/` | current durable JSON/JSONL summaries | `v3_7_2_source_registry_backed_retrieval_smoke_report_*`가 최신 contract smoke 산출물 |
| `harness/`, `run_eval.py` | legacy and general eval harness code | active RAG ingestion status와 혼동하지 않음 |
| `corpora/`, `artifacts/`, `legacy/`, `experiments/` | corpora, generated artifacts, retired paths, tuning experiments | active/protected artifact 여부를 확인한 뒤 이동/삭제 |

## 최신 상태 확인

PowerShell 기준으로 가장 빠른 확인 경로는 아래입니다.

```powershell
# compact status ledger tail
Get-Content ai/eval/reports/rag-ingestion/status.jsonl -Tail 5

# current source-registry-backed retrieval smoke summary
Get-Content ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_7_2_source_registry_backed_retrieval_smoke_report_summary.json

# input all-source citable index summary
Get-Content ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_7_1_all_source_citable_nonprod_index_build_summary.json

# rolling human docs
Get-Content docs/rag-ingestion-progress.md -TotalCount 80
```

## 아직 열지 않은 것

- `v3_7_1`은 retrieval/answer/citation metric computation이 아니라 index build와 hydration contract 검증입니다.
- `v3_7_2`도 answer quality, promotion, prompt tuning, gold 반복 튜닝, comparable live measurement를 열지 않았습니다.
- 100-row local LLM 표는 documentation sample입니다. official answer/citation precision, evidence precision, citation precision 또는 promotion gate로 쓰지 않습니다.
- Full graded nDCG, broad product-quality claims, production SLA latency는 아직 열지 않았습니다.
- Silver/weak-noisy set은 일반화 튜닝 후보를 만들기 위한 보조 표면이지, human gold나 official qrels가 아닙니다.
