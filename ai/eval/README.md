# Evaluation Harness Samples

이 파일은 TEXT/PDF/XLSX의 query -> evidence -> response 표면을 빠르게 보여주는 샘플입니다.
대표 성능 benchmark나 promotion evidence가 아닙니다.

샘플 수는 총 64개입니다. 기존 balanced sample 50개(TEXT 10, PDF 20, XLSX 20)에 v3_22 XLSX display-value/cell-range diagnostic sample 14개를 더했습니다. Portfolio-facing sample과 diagnostic locator sample을 함께 쓰되,
`Response` 칸에는 저장 응답/어댑터 응답 excerpt, 최신 diagnostic answer derivation 출력(PDF/XLSX: deterministic compiler + local LLM polish, TEXT: source-bound local LLM rewrite verifier), stored residual excerpt, 또는 fail-closed 상태가 들어갈 수 있습니다. PDF에서 목차 점선, 단독 섹션 번호, 페이지 번호, 숫자축처럼 content window가 얇은 행은 답변처럼 노출하지 않고 `PDF_CONTENT_WINDOW_TOO_THIN`으로 표시합니다.

- Query/response samples: 64개 (TEXT 10, PDF 20, XLSX 34)
- Current RAG status: `V4_7_PREOFFICIAL_EXTERNAL_HOLDOUT_CANDIDATE_MANIFEST_REGISTRATION_READY`
- Sensitive-topic README display exclusion: enabled
- Diagnostic-only policy: unchanged

## Query / Response Samples

이 표는 query -> evidence -> response 흐름을 빠르게 확인하기 위한 샘플 표입니다. Representative benchmark가 아니며, 공식 denominator나 promotion evidence로 사용하지 않습니다.

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

## Evaluation Boundary

- 이 sample README는 대표 benchmark가 아닙니다.
- Phase 1 is closed as `phase1_diagnostic_contract_closure_fastapi_diagnostic_integration_ready`, diagnostic-only after v3_22, with default-disabled FastAPI diagnostic/internal query and readiness routes; v4 is opened as `v4_source_grounded_runtime_locator_and_finetune_readiness_opened`; v4_1 is `diagnostic_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod_ready`; v4_2 is `diagnostic_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod_ready`; v4_3 is `diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod_ready`; v4_4 is `diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod_ready`; v4_5 is `diagnostic_v4_5_finetune_readiness_packet_nonprod_ready`; v4_5_1 is `diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready`; v4_5_2 is `diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready`; v4_5_3 is `diagnostic_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod_ready`; v4_6 is `diagnostic_v4_6_ft_route_policy_dry_run_preflight_nonprod_ready`; v4_6_1 is `diagnostic_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod_ready`; v4_6_2 is `diagnostic_v4_6_2_ft_route_policy_fixture_contract_nonprod_ready`; v4_6_3 is `diagnostic_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod_ready`; v4_6_4 is `diagnostic_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod_ready`; v4_6_5 is `diagnostic_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod_ready`; v4_6_6 is `diagnostic_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod_ready`; v4_6_7 is `diagnostic_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod_ready`; v4_6_8 is `diagnostic_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod_ready`; v4_6_9 is `diagnostic_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod_ready`; v4_6_10 is `diagnostic_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod_ready`; v4_6_11 is `diagnostic_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod_ready`; v4_6_12 is `diagnostic_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod_ready`; v4_6 closeout is `v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout_ready` without opening v4_7.
- v4 is a non-production readiness charter for persisted/runtime-adjacent SourceAtom paths, family-separated XLSX locator and PDF file-identity work, real blind/OOD holdout and leakage-audit infrastructure, and fine-tuning readiness only after evidence and split gates. The default-disabled FastAPI diagnostic readiness route now defaults to the latest v4_6_12 runtime replay route-parity report, projects v4_6_12 route redaction/parity state, v4_6_10 replay/preflight state when present, and v4_6_6 holdout-gap/blocker ledgers through sanitized fields only, the default-disabled holdout-candidate validation route checks request-body candidate rows in memory with hash-only identity output and no manifest/sidecar/dataset/job/checkpoint writes, and the default-disabled FT-A dry-run input validation route reuses the v4_6_4 manifest-row contract in memory without exporting dry-run inputs, prompts, datasets, jobs, checkpoints, official metrics, promotion evidence, product-success evidence, or live-readiness claims.
- Official exact-evidence retrieval smoke는 28-query small-sample regression guard일 뿐, representative product-performance benchmark가 아닙니다.
- v3 comparable live diagnostic, v3_8 resolver diagnostics, v3_20 non-production DB/index/cache smoke, v3_22 XLSX display-value contract는 구분해서 읽어야 합니다.
- Promotion evidence, threshold tuning, winner selection, production mutation, qrels/gold/label/expected answer/supporting evidence mutation과 무관합니다.
- SourceAtom/source registry가 citation truth이고, vector index metadata는 candidate generation surface일 뿐입니다.
- `production_routing=false`, `official_metric=false`, `official_metric_input_rows=0`, `official_metric_lift=false`, `product_success_evidence_allowed=false`, `promotion_evidence=false`, `fine_tuning_readiness_only=true`, `fine_tuning_started=false`, `fine_tuning_executed=false`, `live_db_index_cache_readiness=false`.
- TEXT/PDF/XLSX metrics are not collapsed into one headline score.
