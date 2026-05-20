# Evaluation harness

ai capability 를 위한 가벼운 로컬 우선 eval harness. 프로덕션
파이프라인이 eval 코드를 절대 import 하지 않도록 (그 반대도) `app/`
과 의도적으로 분리되어 있습니다.

## 현재 3트랙 진행 상황

현재 RAG answer/citation 평가는 하나의 통합 점수가 아니라 TEXT, XLSX, PDF
를 분리한 3트랙으로 봅니다. 기준 입력은
`eval_queries/official_denominator_registry.json` 에서 시작하고, 현재
공식 first-run 리포트는
`reports/rag-ingestion/official_answer_citation_metric_first_run_v1.json`
입니다.

| Track | 공식 입력 | 공식 first-run baseline | v3 primary replay | v3_1 Lane B live LLM top-k | v3_1 Lane C query-bound oracle |
|---|---:|---:|---:|---:|---:|
| `text_namu_v2_1` | 6 rows | PASS `6/6` | PASS `1/6` | PASS `1/6` | PASS `2/6` |
| `xlsx_business_structured` | 19 rows | PASS `1/19` | PASS `19/19` | PASS `15/19` | PASS `16/19` |
| `pdf_business_ocr_mm` | 4 rows | PASS `1/4` | PASS `4/4` | PASS `2/4` | PASS `2/4` |

공식 first-run 은 `status=BLOCKED_OR_PARTIAL`,
`status_detail=SCORED_BASELINE_PARTIAL` 상태이고, 전체 `29`행 중 PASS `8`,
error `21`입니다. 이 baseline 은 tuning, threshold tuning, winner selection,
promotion evidence, production mutation, gold mutation 을 모두 하지 않습니다.
`official_answer_citation_agentic_loop_run_v3_comparable_live_measurement`
는 v2.2 backend validation 완료를 전제로 한 별도 artifact family 입니다.
XLSX/PDF structured row 는 deterministic source-bound adapter 답변을
primary answer 로 유지하고, TEXT 6행만 real local LLM synthesis 를 실행합니다.
따라서 `baseline_comparison_is_model_quality_comparable=true` 라도 비교 범위는
`mixed_structured_adapter_retained_and_text_llm_synthesis_rows` 로 읽어야 합니다.
이 실행도 `promotion_evidence=false`, `threshold_tuning=false`,
`winner_selection=false` 이며 29/29 PASS 가 되더라도 promotion gate 를 자동
실행하지 않습니다.

`official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement`
는 이후 실패 케이스 튜닝 전에 고정한 diagnostic-only foundation run 입니다.
Lane A는 v3 primary 정책을 그대로 재생하고, Lane B는 PDF/TEXT/XLSX 29행
전체를 source-bound retrieved top-k context 로 live LLM 생성하며, Lane C는
query-bound SearchUnit context 만으로 live LLM 생성합니다. Lane B/C strict JSON
에는 cited SearchUnit ID뿐 아니라 LLM이 직접 복사한 `citation_locators`도
기록하므로 PDF bbox/XLSX cell locator 처리 여부를 post-hoc adapter payload와
분리해 볼 수 있습니다. 세 lane 의 점수는 서로 섞어 official score 로 읽지
않습니다. 이 run 도 silver/gold/promotion evidence 가 아니며 expected answer,
gold fields, supporting evidence 를 generation source 로 쓰지 않습니다.

`official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage`
는 위 foundation run 의 triage queue 중 priority 1~5만 다시 본 row-level
diagnostic rerun 입니다. strict JSON prompt/schema 를 fail-closed 로 보강하고,
LLM 이 context 안의 canonical locator JSON 을 그대로 복사했는지 byte-equal /
normalized-equal 로 분리 검증합니다. 이번 rerun 에서 strict JSON parse failure 는
`2 -> 0` 이지만 schema repair 적용도 `0 -> 2` 로 별도 기록되었습니다.
LLM-generated locator copy failure 는 누락 필드까지 보수적으로 세면 `5 -> 1`,
field mismatch 만 보면 `3 -> 0` 입니다. PDF `source_pdf_path` mismatch 는
`1 -> 0`, XLSX `row_label` mismatch 는 `2 -> 0` 으로 기록되었습니다. 이 숫자는
promotion evidence 가 아니며, answer/citation score 도 참고용입니다. locator
metric 은 post-hoc payload locator 보존 실패와 LLM-generated locator copy 실패를
별도 지표로 읽어야 합니다.

`official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage`
는 priority 1~5 뒤에 남은 `text_namu_v2_0012` TEXT `text_locator` residual만
다시 본 diagnostic run 입니다. source-bound prompt context 안의 canonical
locator JSON을 copy-safe하게 제공하고, 모델이 비운 nested `text_locator`는
source-bound locator JSON으로만 canonical copy repair 하도록 기록했습니다.
결과적으로 TEXT `text_locator` missing 은 `1 -> 0`, byte-equal /
normalized-equal 은 모두 true 입니다.

`official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage`
는 29개 official denominator 전체를 다시 실행한 post-triage all-track
diagnostic measurement 입니다. Lane A/B/C 정의는 v3_1과 동일합니다. 결과는
Lane A PASS `24/29`, Lane B PASS `20/29`, Lane C PASS `17/29` 이고,
Lane B/C strict JSON parse failure, LLM-generated locator copy failure,
PDF `source_pdf_path` mismatch, XLSX `row_label` mismatch, TEXT `text_locator`
missing 이 모두 `0` 입니다. 남은 queue 는 answer span / answer renderer
성격으로 이동했으며, 이 run 도 promotion/silver/gold/tuning evidence 가
아닙니다.

현재 사람이 가장 먼저 볼 파일은 아래 3개 rolling 문서입니다. run별
Markdown report 는 주 독해 표면으로 보지 않고, 명시 요청된 diagnostic
Markdown과 JSON/JSONL 원자료는 `eval/reports/rag-ingestion/` 아래에 남깁니다.

- `../../docs/rag-ingestion-progress.md`
- `../../docs/rag-ingestion-measurements.md`
- `../../docs/rag-ingestion-triage.md`

## XLSX/PDF Evidence 검색 방식

XLSX/PDF 검색은 "비슷한 문서 하나 찾기"가 아니라, 답변에 붙일 수 있는
근거 위치를 끝까지 남기는 흐름입니다. 그래서 질문을 먼저 트랙으로
라우팅하고, 같은 트랙 안의 SearchUnit 후보만 고른 뒤, citation payload
가 official scorer 에서 다시 검증 가능한지 확인합니다.

XLSX 에서는 workbook, sheet, range, cell, target column, row label 을
근거로 봅니다. 예를 들어 `D602` 같은 cell 이 실제 supporting evidence
이고, 넓은 `A602:D602` range 는 사람이 확인할 수 있는 주변 행입니다.
숨김/제외 셀은 답변, citation, debug-public 표면으로 올라오면 안 되며,
넓은 range 만 있고 target cell 이 흐리면 diagnostic-only 로 남깁니다.

PDF 에서는 file identity 와 content evidence 를 분리합니다. FILE lane 은
어떤 PDF 인지 확인하는 길이고, CONTENT lane 은 page, physical page index,
bbox, region type, matched text, nearby paragraph 로 답을 지지하는 길입니다.
native text 를 우선 쓰고, OCR 은 fallback 성격으로 다룹니다. page/bbox/region
중 하나가 빠지면 official-compatible citation 으로 보지 않습니다.

## 100-row local LLM 응답 샘플

아래 표는 README에 표시할 근거 샘플을 채우기 위해 한 번 실행한 documentation-only 루프입니다. gold `25`행과 silver `75`행을 사용했고, 로컬 OpenAI-compatible llama.cpp endpoint `http://localhost:8081/v1`의 `gemma4-e2b-local`에 `temperature=0`, `max_tokens=96`으로 요청했습니다. 이 루프의 wall-clock latency는 p95 `0.464s`, p99 `0.516s`, max `0.528s`였습니다.

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

## Phase 7 v4 guardrail

현재 active retrieval/eval 기준선은 dataset v4입니다. 새 Phase 7 작업은
아래 artifact 존재를 먼저 확인하고, v3 corpus/cache 를 기본값으로 삼지
않습니다.

- `eval/corpora/namu-v4-structured-combined/pages_v4.jsonl`
- `eval/corpora/namu-v4-structured-combined/chunks_v4.jsonl`
- `eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl`
- `eval/corpora/namu-v4-structured-combined/split_manifest.json`
- `eval/corpora/namu-v4-structured-combined/split_manifest.report.json`
- `eval/corpora/namu-v4-structured-combined/validation_report.json`

Phase 7.7 answerability audit 에서 production retrieval emits 와 join 할 때는
반드시 `rag_chunks.jsonl` 을 사용합니다. `chunks_v4.jsonl` 은 chunk ID
namespace 가 달라 production join 기준으로 쓰지 않습니다.

## 무엇이며 무엇이 아닌가

**무엇:** 한 줌의 순수 Python 메트릭, JSONL-in / JSON+CSV-out 리포트
writer, 그리고 한 명의 개발자가 트래킹 플랫폼, 클라우드 서비스, 모델
서버 없이 커맨드 라인에서 반복할 수 있는 두 개의 harness 함수
(`run_rag_eval`, `run_ocr_eval`).

**무엇이 아닌가:** 진짜 모델-품질 파이프라인의 대체. 실험 데이터베이스도,
리더보드도, 하이퍼파라미터 sweep driver 도, CI 게이팅도 없음. 프로젝트가
flat 파일을 능가할 때 교체 — `app/` 안의 어느 것도 여기 어떤 것에도
의존하지 않음.

## 디렉토리 구조

`eval/` 아래는 "코드", "source-of-truth 입력", "현재 evidence", "재생성
가능한 대형 산출물"이 섞이기 쉬우므로 아래 표를 기준으로 찾습니다.
디렉토리 이름이 비슷해도 역할이 다르면 병합하지 않습니다.

| Path | 역할 | 현재 판단 |
|---|---|---|
| `harness/` | 공통 eval 라이브러리: metrics, JSONL/CSV I/O, retrieval/PDF/XLSX/TEXT scoring helpers. | Source code. 이동 금지. |
| `run_eval.py`, `tune_eval.py`, `tune_eval_offline.py` | legacy CLI entrypoint와 offline tuning runner. | 유지. v3/v4 혼동 주의. |
| `eval_queries/` | 공식/후보 query set, denominator registry, gold/review CSV/JSONL. | Source-of-truth. gold/label/policy는 내용 변경 금지. |
| `datasets/` | raw benchmark/source dataset과 HF snapshot. | Source-of-truth 또는 protected fixture. 임의 외부화 금지. |
| `corpora/` | retrieval corpus material. `namu-v4-structured-combined/`가 active Phase 7 v4 기준. | Active v4는 유지. legacy v3 대형 payload는 외부 archive 가능. |
| `indexes/` | FAISS/vector artifacts. `rag-data-*`와 promoted `retrieval-title-section`은 active/protected. | 대형이지만 descriptor/report 참조 확인 전 이동 금지. |
| `reports/` | 사람이 읽는 summary, current evidence, historical diagnostic report. | 작은 current summary는 유지. raw/generated bulk는 외부 archive 후보. |
| `artifacts/` | `eval_runs/<run_id>/` raw JSONL, local LLM I/O, parsed blocks/pages, PageIndex payload. | 대부분 diagnostic/generated. active report 참조가 없을 때만 외부 archive. |
| `review/` | human review pack, reviewer-facing CSV/MD, manual decision aids. | gold/review 성격이면 보호. |
| `golden_retrieval/` | SearchUnit golden retrieval runner와 fixtures. | 테스트/fixture surface. 이동 금지. |
| `legacy_agent_loop_ab/` | legacy/experimental agent-loop A/B harness fixture and docs. | `_indexes`, `_logs`, run outputs are externalized/regenerable. |
| `experiments/` | Optuna/tuning experiments, study summaries, local run outputs. | summary/config만 의미 있음. DB/plots/run output은 generated. |
| `legacy/` | retired v3 path 설명과 compatibility notes. | Historical reference only. active default로 쓰지 않음. |

### 빠른 길찾기

- XLSX/PDF/TEXT current report를 찾을 때:
  `eval/reports/rag-ingestion/`
- official denominator/gold query를 찾을 때:
  `eval/eval_queries/official_denominator_registry.json`
- active Phase 7 corpus를 찾을 때:
  `eval/corpora/namu-v4-structured-combined/`
- active promoted Phase 7 index cache를 재현할 때:
  `eval/indexes/namu-v4-2008-2026-04-retrieval-title-section-mseq512/`
  (local-only/rebuildable cache name; fresh checkout 에 없을 수 있음)
- generated run payload를 찾을 때:
  `eval/artifacts/eval_runs/<run_id>/`
- legacy v3 reproduction note를 찾을 때:
  `archive/experiments/eval-legacy/v3/README.md`

### 보존/외부화 규칙

1. `eval_queries/`, human-review/gold files, official denominator registry,
   active v4 corpus, active vector baseline/candidate, and current summary
   reports are protected.
2. `artifacts/eval_runs/`, local LLM raw output, PageIndex trees, parsed
   blocks/pages, old diagnostic report bundles, and legacy v3 generated payloads
   should move to the external archive when no active path requires them.
3. Existing references to an externalized path should be treated as historical
   provenance unless active code opens that path. Restore from the external
   archive manifest for reproduction.
4. New large raw outputs should prefer
   `../_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/` or an
   explicit `RAG_*_ROOT` env var rather than accumulating under `eval/`.

## 데이터셋 스키마

### A. Text RAG eval — `eval/datasets/rag_sample.jsonl`

라인당 JSON 객체 하나. `#` 로 시작하는 라인과 빈 라인은 skip 되므로
파일 안에 인라인 코멘트 유지 가능.

| 필드                | 타입            | 필수 | 비고                                                                  |
|---------------------|-----------------|------|-----------------------------------------------------------------------|
| `query`             | string          | yes  | 테스트할 사용자 query.                                                |
| `expected_doc_ids`  | list<string>    | no   | top-k 에 기대하는 doc id. 이 필드 없는 행은 hit@k 와 MRR 집계에서 제외. |
| `expected_keywords` | list<string>    | no   | 생성된 답변에 포함되어야 하는 substring (대소문자 무시 매치).         |
| `notes`             | string          | no   | 작성자용 자유 형식 주석. 채점 안 함.                                  |

예시:

```jsonl
{"query": "who runs the bookshop at the end of the railway line?", "expected_doc_ids": ["anime-003"], "expected_keywords": ["bookshop", "translator"], "notes": "cozy mystery"}
```

### B. OCR eval — `eval/datasets/ocr_sample.jsonl`

| 필드           | 타입    | 필수 | 비고                                                                                  |
|----------------|---------|------|---------------------------------------------------------------------------------------|
| `file`         | string  | yes  | 이 JSONL 파일의 디렉토리에 **상대적인** 경로. 지원: `.png`, `.jpg`, `.jpeg`, `.pdf`. |
| `ground_truth` | string  | yes  | 정확한 기대 추출 텍스트 (UTF-8). CER/WER 패스에서 공백은 정규화됨.                    |
| `language`     | string  | no   | Tesseract 언어 코드 — `eng`, `eng+kor`, `kor`, `jpn`, `chi_sim` 등. CJK 코드의 경우 harness 가 WER 을 `None` 으로 보고하고 행을 WER 집계에서 제외 (whitespace-split WER 이 거기서는 의미 없음). |
| `notes`        | string  | no   | 자유 형식 주석.                                                                       |

예시:

```jsonl
{"file": "samples/hello_world.png", "ground_truth": "HELLO WORLD", "language": "eng", "notes": "bare minimum smoke test"}
```

### C. Multimodal eval — `eval/datasets/multimodal_sample.jsonl` (스키마만, 아직 harness 없음)

| 필드                | 타입         | 필수 | 비고                                                                       |
|---------------------|--------------|------|----------------------------------------------------------------------------|
| `image`             | string       | yes  | JSONL 파일에 상대적인 경로 (OCR 와 같은 규칙).                             |
| `question`          | string       | yes  | 이미지에 대한 자연어 질문.                                                 |
| `expected_answer`   | string       | no   | 정확/substring 매치를 위한 표준 짧은 답변.                                 |
| `expected_keywords` | list<string> | no   | 답변이 포함해야 하는 substring.                                            |
| `expected_labels`   | list<string> | no   | 모델이 식별해야 하는 시각적 레이블 (오브젝트 이름, 색상 등).                |
| `requires_ocr`      | bool         | no   | task 가 답변 전 텍스트 추출을 요구하면 True.                               |
| `language`          | string       | no   | `requires_ocr` 가 true 일 때 OCR/VLM 언어 코드.                            |
| `notes`             | string       | no   | 자유 형식 주석.                                                            |

**상태: placeholder 만.** 아직 multimodal harness 없음. 미래 phase 가
다시 데이터셋 디자인 라운드 없이 scorer 를 wire 할 수 있도록 스키마는
커밋되어 있음. 권장 미래 메트릭 (모두 `eval.harness.metrics` 에서
재사용 가능): exact match, substring match, `keyword_coverage`, label
recall/precision, 그리고 어떤 VLM-보고 OCR 서브필드에 대한 CER.

## 메트릭 (각각의 의미)

- **`hit@k`** — retriever 의 top-k 에 ANY `expected_doc_id` 가 등장하면
  1.0, 그 외 0.0. 행에 `expected_doc_ids` 가 없으면 `None`. "유용한
  것을 회상했는가" 에 대한 단순한 binary 게이트.
- **`reciprocal_rank` / `MRR`** — ranked 리스트에서 첫 매칭 expected
  id 의 1/rank, 없으면 0.0, `expected_doc_ids` 없는 행은 `None`. MRR
  은 non-None 행의 평균. 정답을 1번 위치 대신 5번 위치에 묻는 것을
  벌점.
- **`keyword_coverage`** — 생성된 답변에 substring (대소문자 무시) 으로
  존재하는 `expected_keywords` 의 비율. "generator 가 실제로 그것을
  언급했는가" 에 대한 가장 싼 합리적 신호.
- **`CER`** — 공백 정규화 후 character edit distance / 참조 character
  count. 0.0 이 완벽. ~0.1 이상이면 보통 눈에 띄게 저하된 OCR; ~0.3
  이상이면 출력이 다운스트림 retrieval 에 사용 불가.
- **`WER`** — 공백 분할 단어 레벨에서의 같은 것. CJK 언어에는 의미
  없음 — harness 가 그것들에 대해 `None` 보고.
- **`empty_rate`** — OCR 엔진이 정규화된 character 0 을 생성한 행의
  비율. 높은 empty_rate 는 보통 잘못 설정된 언어팩 또는 읽을 수 없는
  스캔.
- **latency (ms)** — 각 provider 호출의 wall-clock. p50, mean, max
  보고. 새 모델의 회귀 검사에 유용.

## 권장 평가 시퀀스

이 순서로 반복 — 각 단계의 메트릭이 다음을 게이팅:

### 1. Text RAG baseline

**목표:** retriever 가 OCR 을 건드리기 전에 "대부분 맞는 doc, 대부분
맞는 순서" 에 도달하는지 확인.

**실행:**
```bash
cd ai
python -m scripts.build_rag_index --fixture     # 1회
python -m eval.run_eval rag \
  --dataset eval/datasets/rag_sample.jsonl \
  --top-k 5
```

**게이트:** 픽스처에서 `mean_hit_at_k ≥ 0.80` **그리고**
`MRR ≥ 0.50`. 이 아래로 떨어지면 문제는 임베딩/chunking/config 에 있음
— 아직 OCR 로 넘어가지 마세요. `top_k` 올리기 (`--top-k 10`) 는 진단
용으로만 사용하고 fix 로 사용하지 마세요.

### 2. OCR 추출 품질

**목표:** OCR provider 가 *retrieval 입력으로 충분히 깨끗한* 텍스트를
생성하는지 확인. 이는 결합 단계의 사전 조건.

**실행:**
```bash
python -m scripts.make_ocr_sample_fixtures       # 1회
python -m eval.run_eval ocr \
  --dataset eval/datasets/ocr_sample.jsonl
```

**게이트:** 샘플 픽스처에서 `mean_cer ≤ 0.10` 와
`empty_rate == 0.0`. 진짜 큐레이션된 스캔에서는 `mean_cer ≤ 0.20` 이
보통 RAG 다운스트림이 여전히 정상적으로 동작하는 임계값.

CER 이 0.25 위면 진행하지 마세요 — provider 부터 디버그. 흔한 원인:
누락된 언어팩, 너무 낮은 `ocr_pdf_dpi`, low-contrast 스캔에 누락된
전처리.

### 3. OCR + RAG 결합 (미래, 아직 자동화 안 됨)

**목표:** OCR 출력이 진짜 문서에 대해 RAG 입력으로 실제로 사용 가능
한지 end-to-end 테스트.

**거기 도달했을 때:** `{file, ground_truth_text, query,
expected_doc_ids}` 의 작은 결합 데이터셋 빌드, OCR harness 를 돌려
추출된 텍스트 생성, 추출된 텍스트를 `query` 로 RAG harness 에 먹임,
두 hit@k 숫자 비교:

- RAG-on-ground-truth: 상한, OCR 을 완벽하다고 취급.
- RAG-on-OCR-output: 실제 동작.

delta 가 OCR 이 너에게 비용으로 부과하는 것. **게이트:** 두 숫자가
서로 0.10 이내여야 함; 그보다 나쁘면 OCR 품질이 진짜 입력에 대한
retrieval 을 막고 있다는 뜻. **이 단계는 현재 수동** — 이 문서 하단의
"여전히 수동인 것" 참조.

### 4. Multimodal

**목표:** 풀 multimodal 파이프라인 (OCR + vision + fusion + retrieval +
generation) 이 올바른 키워드를 언급하고 올바른 시각적 레이블을 표면화
하는 답변을 생성하는지 확인.

**실행:**
```bash
python -m scripts.make_multimodal_sample_fixtures    # 1회
python -m eval.run_eval multimodal \
  --dataset eval/datasets/multimodal_sample.jsonl
```

**게이트:** 픽스처에서 `mean_keyword_coverage >= 0.60` **그리고**
`mean_substring_match >= 0.50`. 이 아래로 떨어지면 문제는 vision
provider 또는 fusion 단계일 가능성 — stage 단위 진단을 위해
MULTIMODAL_TRACE artifact 확인.

**필터링:** OCR 의존 행만 평가하려면 `--require-ocr-only` 사용. A/B
비교를 위해 vision provider override 하려면
`--vision-provider heuristic|claude` 사용.

**Stage 단위 latency 분석:** `emit_trace=True` (eval 실행 중 자동
활성화) 일 때 harness 가 OCR, vision, retrieval+generation latency 를
별도로 보고. 어느 stage 가 병목인지 식별하는 데 사용.

## `retrieval` 모드 — dense-retrieval baseline 측정

`rag` 모드 (generator 출력도 점수 매김) 와 별도로, `retrieval` 모드는
dense-retrieval 단계 **만** 측정. generator 가 호출되지 않고, 출력은
실행당 4개의 artifact:

```
eval/reports/retrieval-<timestamp>/
├── retrieval_eval_report.json     summary + 행별 메트릭
├── retrieval_eval_report.md       사람이 읽을 수 있는 요약
├── top_k_dump.jsonl               (query, rank) 쌍당 1개 레코드
└── duplicate_analysis.json        query 별 + 집계 dup 통계
```

**행별 메트릭**: hit@1, hit@3, hit@5, mrr@10, ndcg@10 (binary
relevance), dup_rate, unique_doc_coverage, top1_score_margin,
avg_context_token_count, expected_keyword_match_rate.

아래 명령은 **historical v3 reproduction 전용**입니다. Phase 7 이후 active
eval/tuning 기본 경로로 사용하지 마세요. 오프라인 anime 코퍼스에 대해
실행합니다 (Postgres 필요 없음):

```bash
cd ai

# 1. 코퍼스 stage (1회, eval/corpora/anime_namu_v3/README.md 참조)
cp 'D:/port/rag/app/scripts/namu_anime_v3.jsonl' \
   eval/corpora/anime_namu_v3/corpus.jsonl

# 2. 6개 수작업 query 에 대한 스모크 테스트
python -m eval.run_eval retrieval \
    --corpus  eval/corpora/anime_namu_v3/corpus.jsonl \
    --dataset eval/eval_queries/anime_smoke_6.jsonl \
    --top-k 10

# 3. 풀 silver baseline (200개 결정적 합성 query)
python -m eval.run_eval retrieval \
    --corpus  eval/corpora/anime_namu_v3/corpus.jsonl \
    --dataset eval/eval_queries/anime_silver_200.jsonl \
    --top-k 10

# 4. Gold baseline (20개 수작업 큐레이션 query — ground truth 로 신뢰)
python -m eval.run_eval retrieval \
    --corpus  eval/corpora/anime_namu_v3/corpus.jsonl \
    --dataset eval/eval_queries/anime_gold_20.jsonl \
    --top-k 10
```

`retrieval` 모드는 라이브 ragmeta/FAISS 경로도 받아들임 (`--corpus`
생략) — `--offline-corpus` 플래그 없는 legacy `rag` 모드와 같은 동작.

silver vs. gold 의미, 결정적 generator 의 stratification, gold-set
확장 레시피는 [`eval_queries/README.md`](eval_queries/README.md) 참조.
코퍼스 스키마와 re-stage 지침은
[`corpora/anime_namu_v3/README.md`](corpora/anime_namu_v3/README.md)
참조.

### Historical Phase 0 baseline 도구 (post-retrieval)

세 개의 동반 서브커맨드가 기존 retrieval 실행에 대해 동작. 어느 것도
재임베딩하지 않으므로 비용이 쌈.

```bash
# 발행하지 않은 retrieval 실행에 doc/keyword cross-tab 추가
python -m eval.run_eval retrieval-miss-analysis \
    --report-dir eval/reports/_archive/silver200/baseline \
    --top-k 10

# 두 개의 retrieval 실행을 나란히 비교 (deterministic vs opus).
# .md 에 Caveat 블록 + slice 별 retriever_config 자동 발행.
python -m eval.run_eval retrieval-compare \
    --deterministic-report eval/reports/_archive/silver200/baseline/retrieval_eval_report.json \
    --opus-report          eval/reports/_archive/silver200/opus-baseline/retrieval_eval_report.json \
    --deterministic-max-seq-length 8192 \
    --opus-max-seq-length 1024 \
    --out-json eval/reports/phase2/baseline_comparison.json \
    --out-md   eval/reports/phase2/baseline_comparison.md

# 같은 비교지만 deterministic 측에 hyperparameter-tuned 변형 포함.
# 튜닝된 slice (와 그 진단) 는 자체 headline-metrics 표에 렌더링되어
# baseline 숫자와 행을 공유하지 않음.
python -m eval.run_eval retrieval-compare \
    --deterministic-report eval/reports/retrieval-silver200-tuned/retrieval_eval_report.json \
    --opus-report          eval/reports/_archive/silver200/opus-baseline/retrieval_eval_report.json \
    --deterministic-kind tuned \
    --opus-kind baseline \
    --out-json eval/reports/retrieval-tuned-vs-baseline.json \
    --out-md   eval/reports/retrieval-tuned-vs-baseline.md

# 코퍼스에 대한 tokenizer 기반 char/token 길이 분포.
# char 유추 추측 대신 측정된 숫자로 max_seq_length cap 사이즈 결정에 사용.
python -m eval.run_eval analyze-corpus-lengths \
    --corpus eval/corpora/anime_namu_v3/corpus.jsonl \
    --tokenizer BAAI/bge-m3 \
    --out-json eval/reports/phase1/length_analysis.json \
    --out-md   eval/reports/phase1/length_analysis.md
```

전체 Phase 0 trade-off 로그는
[`reports/phase0/tradeoffs.md`](reports/phase0/tradeoffs.md)
에 있음.

### Historical Phase 2A — cross-encoder reranker (`retrieval-rerank`)

`retrieval-rerank` 서브커맨드는 dense retriever 위에 cross-encoder
reranker 를 후처리로 끼움. dense top-N candidate 를 가져와 cross-encoder
로 재정렬한 뒤 final top-K 를 점수. corpus / chunker / preprocessor 는
건드리지 않음 — 순수 retrieval 후처리.

```bash
# 1. Candidate-recall 진단 — reranker 성능 상한 측정.
#    NoOp reranker + top-k=50 + extra-hit-k 로 hit@1/3/5/10/20/50 계산.
python -m eval.run_eval retrieval \
    --corpus  eval/corpora/anime_namu_v3_token_chunked/corpus.combined.token-aware-v1.jsonl \
    --dataset eval/eval_queries/anime_silver_200.jsonl \
    --top-k 50 \
    --extra-hit-k 10 --extra-hit-k 20 --extra-hit-k 50 \
    --out-dir eval/reports/phase2/2a_reranker/candidate-recall-b2

# 2. dense top-20 → cross-encoder rerank → top-10
python -m eval.run_eval retrieval-rerank \
    --corpus  eval/corpora/anime_namu_v3_token_chunked/corpus.combined.token-aware-v1.jsonl \
    --dataset eval/eval_queries/anime_silver_200.jsonl \
    --dense-top-n 20 \
    --final-top-k 10 \
    --reranker-model BAAI/bge-reranker-v2-m3 \
    --reranker-batch-size 16 \
    --out-dir eval/reports/_archive/silver200/token-aware-v1-rerank-top20

# 3. dense top-50 → cross-encoder rerank → top-10
python -m eval.run_eval retrieval-rerank \
    --corpus  eval/corpora/anime_namu_v3_token_chunked/corpus.combined.token-aware-v1.jsonl \
    --dataset eval/eval_queries/anime_silver_200.jsonl \
    --dense-top-n 50 \
    --final-top-k 10 \
    --reranker-model BAAI/bge-reranker-v2-m3 \
    --reranker-batch-size 16 \
    --out-dir eval/reports/_archive/silver200/token-aware-v1-rerank-top50

# 4. 5-slice 비교 (B1 dense / B2 dense / candidate-recall / rerank top20 / rerank top50)
python -m eval.run_eval phase2a-reranker-comparison \
    --slice "B1 dense (combined-old):eval/reports/_archive/silver200/combined-old-chunker/retrieval_eval_report.json" \
    --slice "B2 dense (token-aware-v1):eval/reports/_archive/silver200/token-aware-v1/retrieval_eval_report.json" \
    --slice "B2 dense top50 (candidate-recall):eval/reports/phase2/2a_reranker/candidate-recall-b2/retrieval_eval_report.json" \
    --slice "B2 rerank top20:eval/reports/_archive/silver200/token-aware-v1-rerank-top20/retrieval_eval_report.json" \
    --slice "B2 rerank top50:eval/reports/_archive/silver200/token-aware-v1-rerank-top50/retrieval_eval_report.json" \
    --out-json eval/reports/phase2/2a_reranker/reranker-comparison.json \
    --out-md   eval/reports/phase2/2a_reranker/reranker-comparison.md

# 5. Failure analysis (dense top-10 vs rerank top-20 cross-tab)
python -m eval.run_eval phase2a-reranker-failure-analysis \
    --dense-report-dir  eval/reports/_archive/silver200/token-aware-v1 \
    --rerank-report-dir eval/reports/_archive/silver200/token-aware-v1-rerank-top20 \
    --out-dir eval/reports/phase2/2a_reranker \
    --k-preview 5 --sample-cap 10
```

**Phase 2A silver-200 결과** (RTX 5080 / bge-m3 + bge-reranker-v2-m3):

| run                              | hit@1 | hit@3 | hit@5 | MRR@10 | NDCG@10 | rerank p95 (ms) |
|----------------------------------|------:|------:|------:|-------:|--------:|----------------:|
| B1 dense (combined-old)          | 0.5600 | 0.6700 | 0.6850 | 0.6167 | 0.6428 |               – |
| B2 dense (token-aware-v1)        | 0.5400 | 0.6650 | 0.6800 | 0.6044 | 0.6314 |               – |
| **B2 + rerank top20**            | 0.6050 | 0.6800 | 0.7000 | 0.6526 | 0.6748 |             706 |
| **B2 + rerank top50**            | **0.6150** | **0.7000** | **0.7150** | **0.6657** | **0.6885** |       1840 |

Candidate recall ceiling (B2 dense top-50): hit@10=0.7150, hit@20=0.7700,
hit@50=0.8000. reranker 는 candidate set 안의 순서만 바꿀 수 있으므로 이
값들이 reranker hit@k 의 이론적 상한.

**Caveat**

- rerank latency 는 cross-encoder predict 만의 wall-clock — bi-encoder +
  FAISS 부분은 `mean_retrieval_ms` 에 별도로 잡힘. p95 한 번에 700–1800ms 는
  query-time UX 에 무거우므로 production default 로 승격하기 전에 batch
  처리 / async 호출 설계 필요.
- B1 (combined-old) 와 B2 (combined-token-aware-v1) 는 chunk granularity 가
  다르므로 candidate population 자체가 동일하지 않음 — 직접 비교 시 chunker
  효과 + reranker 효과가 섞여 있음.
- production default 는 여전히 `rag_reranker="off"` (NoOp). reranker 는
  eval CLI 에서만 활성화하며, registry 의 `cross_encoder` 분기를 production
  으로 켤지는 별도 결정.

### Phase 2A-L — reranker latency profiling (`phase2a-latency-sweep`)

`phase2a-latency-sweep` 는 Phase 2A 의 정확도 결과(top20 / top50) 위에서
**latency 분해 + accuracy ↔ latency Pareto frontier + 운영 모드 추천** 을
한 번의 명령으로 만들어내는 evaluation 모드. 정확도 개선이 아니라 reranker
의 latency budget 을 정량화하기 위한 도구.

```bash
# silver-200 + B2 token-aware corpus 에서 6 개 dense_top_n sweep.
# corpus 는 한 번만 빌드, 6 번의 retrieval-rerank 가 동일 인덱스 위에서 돌고,
# 추가로 dense-only candidate-recall sibling 이 hit@10/20/50 상한을 잡는다.
python -m eval.run_eval phase2a-latency-sweep \
    --dataset eval/eval_queries/anime_silver_200.jsonl \
    --corpus  eval/corpora/anime_namu_v3_token_chunked/corpus.combined.token-aware-v1.jsonl \
    --out-dir eval/reports/phase2/2a_latency \
    --final-top-k 10 \
    --dense-top-n 5  --dense-top-n 10 --dense-top-n 15 \
    --dense-top-n 20 --dense-top-n 30 --dense-top-n 50 \
    --breakdown-anchor-dense-top-n 20 \
    --candidate-recall-extra-hit-k 10 --candidate-recall-extra-hit-k 20 --candidate-recall-extra-hit-k 50 \
    --metric mean_hit_at_1 \
    --latency rerank_p95_ms
```

산출물 (`eval/reports/phase2/2a_latency/`):

- `rerank-top{N}/retrieval_eval_report.{json,md}` — 각 config 의 표준
  retrieval-rerank 산출물 (rerank_breakdown_ms 포함).
- `candidate-recall/retrieval_eval_report.{json,md}` — dense-only sibling
  (hit@10/20/50 상한).
- `reranker-latency-breakdown.{json,md}` — anchor config(기본 top20)
  에서의 stage breakdown: `pair_build_ms`, `tokenize_ms`, `forward_ms`,
  `postprocess_ms`, `total_rerank_ms`, `dense_retrieval_ms`,
  `total_query_ms`. 각 stage 마다 avg/p50/p90/p95/p99/max.
- `topn-sweep.{json,md}` — 6 config × accuracy/latency 표.
- `accuracy-latency-frontier.{json,md}` — Pareto frontier (정확도 ↑ / latency ↓
  로 dominance 판정, dominated 항목은 dominator 라벨 명시).
- `recommended-modes.{json,md}` — fast/balanced/quality 후보. budget 옵션
  (`--fast-p95-budget-ms`, `--balanced-p95-budget-ms`,
  `--quality-target-metric`) 으로 선정 기준 조정 가능.

Post-processing 만 다시 돌리고 싶으면 분리 모드 사용:

```bash
# 단일 retrieval-rerank report 의 latency breakdown.
python -m eval.run_eval phase2a-latency-breakdown \
    --report eval/reports/phase2/2a_latency/rerank-top20/retrieval_eval_report.json \
    --out-json eval/reports/phase2/2a_latency/reranker-latency-breakdown.json \
    --out-md   eval/reports/phase2/2a_latency/reranker-latency-breakdown.md

# N 개 retrieval-rerank report → topN sweep.
python -m eval.run_eval phase2a-topn-sweep \
    --slice "top10:eval/reports/phase2/2a_latency/rerank-top10/retrieval_eval_report.json" \
    --slice "top20:eval/reports/phase2/2a_latency/rerank-top20/retrieval_eval_report.json" \
    --slice "top50:eval/reports/phase2/2a_latency/rerank-top50/retrieval_eval_report.json" \
    --candidate-recall-report eval/reports/phase2/2a_latency/candidate-recall/retrieval_eval_report.json \
    --out-json eval/reports/phase2/2a_latency/topn-sweep.json \
    --out-md   eval/reports/phase2/2a_latency/topn-sweep.md

# topn-sweep.json → Pareto frontier + recommended modes.
python -m eval.run_eval phase2a-recommended-modes \
    --sweep-json   eval/reports/phase2/2a_latency/topn-sweep.json \
    --out-md       eval/reports/phase2/2a_latency/recommended-modes.md \
    --out-modes-json eval/reports/phase2/2a_latency/recommended-modes.json \
    --out-frontier-json eval/reports/phase2/2a_latency/accuracy-latency-frontier.json \
    --out-frontier-md   eval/reports/phase2/2a_latency/accuracy-latency-frontier.md
```

**Stage breakdown 측정 메모**

- `CrossEncoderReranker(collect_stage_timings=True)` 일 때만 stage 별 timing
  이 잡힌다. Production default 는 `False` 이므로 retriever / RAG capability /
  registry 경로는 byte-identical.
- `tokenize_ms` 는 host-side; `forward_ms` 는 host→device 전송 + model
  forward + activation 로, GPU 위에서는 `torch.cuda.synchronize()` 로 양쪽
  경계를 잡고 측정. CPU-only 실행에서는 sync 가 no-op 이므로 forward_ms 가
  실측치보다 약간 흐려질 수 있다.
- OOM-fallback path (CUDA OOM 발생 후 half-batch 재시도) 에서는 stage
  breakdown 이 None — 두 batch_size 의 측정을 섞어 보고하는 것을 의도적으로
  피한 결과.
- 이 mode 는 production default 를 변경하지 않는다. `recommended-modes.md`
  는 의사결정 근거이지 자동 적용되는 config 가 아니다.

## eval CLI 실행

두 서브커맨드 모두 stdout 에 짧은 사람용 요약을 출력하고 JSON 리포트
(그리고 기본적으로 CSV) 를 작성. `--out-json` / `--out-csv` 가
전달되지 않으면 리포트는 `eval/reports/{mode}-{timestamp}.{json,csv}`
로 갑니다.

```bash
# Text RAG — 진짜 프로덕션 스택 빌드 (bge-m3 + FAISS + ragmeta)
python -m eval.run_eval rag \
    --dataset eval/datasets/rag_sample.jsonl \
    --out-json eval/reports/rag-latest.json \
    --out-csv  eval/reports/rag-latest.csv \
    --top-k 5

# OCR — 진짜 Tesseract + PyMuPDF provider 빌드
python -m eval.run_eval ocr \
    --dataset eval/datasets/ocr_sample.jsonl \
    --out-json eval/reports/ocr-latest.json \
    --out-csv  eval/reports/ocr-latest.csv

# Multimodal — 풀 MULTIMODAL capability 빌드 (OCR + vision + RAG)
python -m eval.run_eval multimodal \
    --dataset eval/datasets/multimodal_sample.jsonl \
    --out-json eval/reports/multimodal-latest.json \
    --out-csv  eval/reports/multimodal-latest.csv

# Multimodal — Claude vision provider 로 OCR 전용 행
python -m eval.run_eval multimodal \
    --dataset eval/datasets/multimodal_sample.jsonl \
    --require-ocr-only \
    --vision-provider claude
```

CLI 플래그:

| 플래그              | 적용 대상 | 기본값                                                    |
|---------------------|-----------|-----------------------------------------------------------|
| `--dataset PATH`    | 양쪽      | (필수)                                                    |
| `--out-json PATH`   | 양쪽      | `eval/reports/{mode}-<timestamp>.json`                    |
| `--out-csv PATH`    | 양쪽      | `eval/reports/{mode}-<timestamp>.csv`                     |
| `--no-csv`          | 양쪽      | JSON 만 발행                                              |
| `-v` / `--verbose`  | 양쪽      | DEBUG 로깅                                                |
| `--top-k N`         | rag       | worker 의 `AIPIPELINE_WORKER_RAG_TOP_K` (기본 `5`)        |
| `--fail-missing`    | ocr       | 누락된 픽스처 파일을 skip 대신 에러로 취급                |

## 프로그래매틱 사용

Harness 는 단위 테스트 또는 커스텀 runner 용으로 import 가능:

```python
from eval.harness import (
    run_rag_eval, run_ocr_eval,
    cer, wer, hit_at_k, reciprocal_rank, keyword_coverage,
)
```

`run_rag_eval` 와 `run_ocr_eval` 모두 이미 생성된 retriever/generator/
provider 객체를 받음 — config 결합 없음 — 그래서 테스트는 fake 를
넘길 수 있고 커스텀 runner 는 이 패키지를 건드리지 않고 GPU 백엔드
provider 를 넘길 수 있음.

## 무시 규칙 / `.gitignore`

리포트는 생성되며 커밋되어서는 안 됩니다. 로컬에서 git 을 사용한다면
다음 추가:

```
ai/eval/reports/
ai/eval/datasets/samples/
```

`samples/` 폴더는 `scripts/make_ocr_sample_fixtures.py` 가 만든 합성
OCR 픽스처 이미지를 보유; 재생성은 비용이 싸고 폰트에 따라 표류함.

## 여전히 수동 / 아직 자동화되지 않은 것

이것들은 의도적인 phase-범위 라인이지 간과가 아닙니다:

1. **데이터셋 큐레이션.** JSONL 파일을 손으로 작성. 스크래핑 없음, LLM
   생성 질문 없음. 한 명의 개발자의 반복 loop 에서는 작은 큐레이션 셋이
   큰 노이즈 셋을 이김.
2. **OCR → RAG chaining eval.** OCR 출력을 RAG 입력으로 받는 harness
   가 없음. 지금은 OCR harness 실행, OCR_TEXT artifact 를 새 RAG
   데이터셋의 `query` 필드에 복사, RAG harness 재실행, 그 다음 ground-
   truth RAG 실행과 눈으로 비교. 아키텍처가 이 흐름을 지원 —
   [architecture.md](../../docs/architecture.md) 참조 — 그러나 자동화는
   나중 phase 의 몫.
3. **Multimodal 스코어링.** 스키마 커밋, harness 보류.
4. **CI 의 회귀 게이팅.** 메트릭 품질에 관계없이 성공한 실행에서
   harness 는 0 으로 종료. CI 게이팅을 원할 때 CLI 를 JSON 리포트를
   읽고 예: `mean_cer > 0.15` 면 실패하는 후속 실행 체크로 감싸세요.
   임계값을 harness 자체에 baking 하지 마세요 — 그것들은 도구가 아니라
   프로젝트의 release 기준 옆에 살아야 함.
5. **머신 전반의 latency baseline.** 리포트의 latency 는 raw wall-
   clock 숫자. 한 머신 / 한 실행 안에서만 비교 가능. 머신 전반 비교는
   고정 하드웨어 harness 가 필요하고, 이는 여기 범위 밖.
