# Evaluation Harness Samples

이 파일은 TEXT/PDF/XLSX의 query -> evidence -> response 표면을 빠르게 보여주는 샘플입니다.
대표 성능 benchmark나 promotion evidence가 아닙니다.

샘플 수는 총 100개입니다. Portfolio-facing samples는 v3 comparable live diagnostic에서 PASS된 저장 응답/어댑터 응답 excerpt이고, Diagnostic / Raw Locator samples는 locator/source hydration 확인용입니다. Diagnostic 행의 `Response` 칸에는 최신 diagnostic answer derivation 출력(PDF/XLSX: deterministic compiler + local LLM polish, TEXT: source-bound local LLM rewrite verifier), stored residual excerpt, 또는 fail-closed 상태가 들어갈 수 있습니다. PDF에서 목차 점선, 단독 섹션 번호, 페이지 번호, 숫자축처럼 content window가 얇은 행은 답변처럼 노출하지 않고 `PDF_CONTENT_WINDOW_TOO_THIN`으로 표시합니다.

- Portfolio-facing samples: 27개 (PDF 4, XLSX 19, TEXT 4)
- Diagnostic / Raw Locator samples: 73개 (PDF 24, XLSX 25, TEXT 24)

## Portfolio-Facing Samples

외부 리뷰어가 query -> evidence -> response 흐름을 빠르게 확인할 수 있도록, raw text_block/hash/location id를 직접 묻는 질의는 제외했습니다. 이 표는 representative benchmark가 아니라 저장된 diagnostic/live comparable sample surface입니다.

| Track | Query | Evidence surface | Response |
|---|---|---|---|
| PDF | 2월 실업률은 전년 같은 달보다 어떻게 변했나요? | PDF page citation: 2021_03_recent_economic_trends.pdf p.8 (paragraph) | 실업률은 4.9%로 전년동월대비 0.8%p 상승 |
| PDF | 1월 산업활동에서 생산 지표는 어떻게 움직였나요? | PDF page citation: 2021_03_recent_economic_trends.pdf p.5 (paragraph) | 1월 산업활동에서 광공업 생산, 서비스업 생산, 건설투자는 감소했습니다. |
| PDF | 2020년 한국 원달러 기말 환율은 얼마인가요? | PDF page citation: 2021_03_recent_economic_trends.pdf p.65 (table_body) | 2020년 한국 원달러 기말 환율은 1,088.0입니다. |
| PDF | 2024년 수출입차 금액은 얼마인가요? | PDF page citation: 2025_12_recent_economic_trends.pdf p.61 (table_body) | 2024년 수출입차 금액은 6,836.1입니다. |
| TEXT | 자동판매기 미궁 방랑 애니 3기 방영 시기는 문서에 어떻게 적혀 있어 | TEXT chunk/source context: text_namu_v2_1, 92c87287 | 자동판매기로 다시 태어난 나는 미궁을 방랑한다를 원작으로 하는 TV 애니메이션 시리즈 중 제3기의 방영 시기는 2026년 4월입니다. |
| TEXT | 유우야키의 나이와 생일은 어떻게 적혀 있어 | TEXT chunk/source context: text_namu_v2_1, 7be08880 | 유우야키의 나이는 16세이고 생일은 9월 29일입니다. |
| TEXT | 엑스맨 구십칠 등장인물 목록에 애드버서리는 어떤 식으로 올라와 | TEXT chunk/source context: text_namu_v2_1, 1048928e | 애드버리는 앨리슨 실리스미스(카메오)로 등장합니다. |
| TEXT | 소드아트 오디널 스케일은 어떤 극장판을 가리켜 | TEXT chunk/source context: text_namu_v2_1, 65f737bb | 소드 아트 온라인의 극장판은 2017년 2월 18일에 일본에서 개봉한 극장판 애니메이션이다. |
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

## Diagnostic / Raw Locator Samples

이 섹션은 일반 사용자 질의 품질을 보여주기 위한 샘플이 아니라 locator/source hydration 확인용입니다.
PDF text block, chunk id, hash, location id가 prompt에 직접 노출되거나 resolver 상태만 확인하는 행은 portfolio-facing sample에서 제외합니다.

| Track | Query | Evidence surface | Response |
|---|---|---|---|
| TEXT | 실바니안 실크 고양이 가족 설명은 어떤 성격과 역할을 말해 | TEXT chunk/source context: text_namu_v2_1, 18d62717 | diagnostic residual: stored LLM response excerpt; bucket=LLM_SYNTHESIS_REGRESSED; 유럽판에서 실크 고양이 소년은 상냥하고 배려심이 넘치며, 소녀는 패션 디자이너를 꿈꾼다. |
| TEXT | 미츠하는 타키를 만나려고 어디로 향했어 | TEXT chunk/source context: text_namu_v2_1, 2b77d0ce | diagnostic residual: stored LLM response excerpt; bucket=LLM_SYNTHESIS_REGRESSED; 미츠하는 자신과 몸이 바뀌고 있는 타키를 실제로 만나기 위해 도쿄로 향했다. |
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
| PDF | 분야별 전문가 인터뷰 개요를 자세히 알려주세요. | PDF raw/source locator: prism_1400000-202500030_d0150004_001_1_최종보고서..._및_단계별_추진방안_연구.pdf p.4 (text_block), srcatom da37fb44 | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| PDF | 접경지역 산불방지 단계별 추진계획안에 대해 알고 싶습니다. | PDF raw/source locator: prism_1400000-202500030_d0150004_001_1_최종보고서..._및_단계별_추진방안_연구.pdf p.5 (text_block), srcatom b4cc617a | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| PDF | 제안 개요에 대한 핵심적인 내용을 요약해 주시겠어요? | PDF raw/source locator: dart_dongsung_auditor_audit_report_2025.pdf p.2 (text_block), srcatom b84b4232 | 본인은 동성제약주식회사의 감사로서 2024년 1월 1일부터 2024년 12월 31일 까지 제68기 사업년도의 회계 및 업무에 대한 감사실시 결과를 다음과 같이 보고합니다. Page 2. |
| PDF | 남북관계의 안정적 관리가 국가적 과제로 부상함에 따른 정부의 대응 방안은 무엇인가요? | PDF raw/source locator: prism_1400000-202500030_d0150012_000_1_사단법인_..._및_단계별_추진방안_연구.pdf p.3 (text_block), srcatom 92b97943 | ◯남북관계의 안정적 관리가 국가적 과제로 부상함에 따라, 정부는 기존 남북 합의 중 이 Page 3. |
| PDF | 2018년 평양정상회담 이후 미국과 협의하여 병해충방제용 약제 50톤을 지원한 사실에 대해 알고 싶습니다. | PDF raw/source locator: prism_1400000-202500030_d0150012_000_1_사단법인_..._및_단계별_추진방안_연구.pdf p.4 (text_block), srcatom dd9040a3 | －2018년 평양정상회담 이후 미국과 협의를 통해 병해충방제용 약제 50톤을 지원하였으나, 회담에 Page 4. |
| PDF | 추진배경과 필요성에 대한 내용을 중심으로 검색해 주세요. | PDF raw/source locator: prism_1262000-202500026_d0150009_001_1_정책연구용역_문헌유사도_검사_결과서.pdf p.3 (text_block), srcatom 3872f438 | 13 1% [KCI 논문] KCI 논문 - 제목 : 동남아시아 신흥공여국의 부상 : 인도네시아와 태국의 국제개발협력 정책을 중심으로 - 저자 : 이진영(전북대학교) - 발행년 : 2024.06 Page 3. |
| PDF | 제1장 서론에 대해 자세히 알려주세요. | PDF raw/source locator: prism_1400000-202500030_d0150004_001_1_최종보고서..._및_단계별_추진방안_연구.pdf p.3 (text_block), srcatom 41adabf4 | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| PDF | 9쪽 부분의 요약문을 찾을 수 있나요? | PDF raw/source locator: prism_1230000-202500002_d0150014_001_1_중간보고서...회계_수수료_운영개선_방안.pdf p.7 (text_block), srcatom 2959f4cc | diagnostic-only fail-closed: PDF_CONTENT_WINDOW_TOO_THIN |
| XLSX | 다른 경로에서 생기는 갈등 상황에 대해 자세히 알려주세요. | XLSX scoped locator: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A402:D451 D402 | diagnostic-only fail-closed: XLSX_QUERY_ANCHOR_MISSING |
| XLSX | 과학기술자료실에서 파괴와 재생의 시작에 대해 검색해 주세요. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A9402:J9451 A9402 | diagnostic-only fail-closed: XLSX_QUERY_ANCHOR_MISSING |
| XLSX | 대덕구 컴퓨터 윈도우탑재 제품 정보 알려주세요. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A9852:J9901 A9852 | diagnostic-only fail-closed: XLSX_QUERY_ANCHOR_MISSING |
| XLSX | 현재 현황 정보에 대해 간단히 설명해 주시겠어요? | XLSX scoped locator: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A102:D151 D102 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 과학기술정보통신부 자료 정보 확인 부탁드립니다. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A9102:J9151 A9102 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 장기요양기관 현황 내용을 자세히 살펴보고 싶습니다. | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A752:J801 G752 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 과학기술자료실 도서정보 정보 확인하고 싶어요. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A8702:J8751 A8702 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 장기요양기관 시설 현황에서 기관명과 주소를 찾아주세요. | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A1102:J1151 J1102 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 과학기술정보통신부 국립과천과학관 도서정보 확인 부탁드립니다. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A5352:J5401 A5352 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 현황 정보를 확인하는 과정이 궁금합니다. | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A802:J851 J802 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 국립과천과학관 도서정보 2025년 5월 자료 확인해주세요. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A8702:J8751 A8702 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 장기요양기관 시설 현황 정보가 필요해요 | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A1102:J1151 J1102 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 과학기술정보통신부 자료 확인 | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A9102:J9151 A9102 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 장기요양기관의 현재 상태를 점검하고 싶습니다. | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A752:J801 G752 | diagnostic-only fail-closed: XLSX_QUERY_ANCHOR_MISSING |
| XLSX | 장기요양기관의 주요 데이터를 찾아볼 수 있을까요? | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A1102:J1151 J1102 | diagnostic-only fail-closed: XLSX_QUERY_ANCHOR_MISSING |
| XLSX | 국립과천과학관 도서정보 핵심 내용 검색해 주세요. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A1902:J1951 A1902 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 국립과천과학관 도서정보 항목들 간단히 알려주세요. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A1652:J1701 A1652 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 장기요양기관의 상세 내역을 보여주세요. | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A1102:J1151 J1102 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 특정 숫자가 들어간 현황 값을 확인해 주세요. | XLSX scoped locator: 서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx / 철도 A52:D101 D52 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 장기요양기관 시설 현황에서 숫자 데이터 정확히 알려주세요 | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A1102:J1151 J1102 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 과학기술자료실 데이터 구조가 궁금합니다. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A1652:J1701 A1652 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 과천과학관 도서정보 20250513 정보 알려주세요 | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A1552:J1601 A1552 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 장기요양기관 시설 현황 정보 알려주세요 | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A1102:J1151 J1102 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 장기요양기관의 시설 현황 정보 좀 찾아주세요. | XLSX scoped locator: 국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx / 일반현황 A752:J801 G752 | diagnostic-only fail-closed: XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY |
| XLSX | 과학기술자료실에서 숫자 384번 항목의 값을 확인해 주세요. | XLSX scoped locator: 과학기술정보통신부 국립과천과학관_과학기술자료실 도서정보_20250513.xlsx / Sheet1 A752:J801 A752 | diagnostic-only fail-closed: XLSX_QUERY_ANCHOR_MISSING |
| TEXT | 마키노 유이 김정선 작사 노래 정보 | TEXT raw source locator: 6ec273bc, hash 2aa4a177 | 노래는 마키노 유이/김정선, 작사는 카와이 에리, 한국어 개사는 고정민, 작곡/편곡은 쿠보타 미나로 표시됩니다. |
| TEXT | 아자야카니 마와리다시타 히비의 아름다운 느낌은 무엇인가요? | TEXT raw source locator: 6d7911eb, hash bb42486d | source-bound local LLM verifier fail-closed: lyric_excerpt_policy_guard |
| TEXT | 고마워 또 만나자 | TEXT raw source locator: 3d3e5440, hash dd8ec2d1 | source-bound local LLM draft: 증거에는 곡 가사 일부가 포함되어 있으나, README 샘플에서는 가사 원문 인용을 생략했습니다. |
| TEXT | 금빛 물결 노래 한국어 개사 관련 정보는 무엇인가요? | TEXT raw source locator: e992d216, hash ffd821e0 | 한국어 개사는 고정민으로 표시되며, 노래는 아라이 아키노/장아름, 작사/작곡은 아라이 아키노로 표시됩니다. |
| TEXT | 운디네 노래 마키노 유이 | TEXT raw source locator: ca1a4355, hash 1f82461a | 노래는 마키노 유이/정여진, 작사는 카와이 에리, 작곡은 쿠보타 미나로 표시됩니다. |
| TEXT | 아라이 아키노 노래 가사 검색해 주세요. | TEXT raw source locator: a838a261, hash 9da058c6 | source-bound local LLM draft: 증거는 곡의 제목/가수/작사·작곡·편곡 같은 메타데이터와 가사 일부가 있는 chunk임을 보여주며, README 샘플에서는 가사 원문 인용을 생략했습니다. |
| TEXT | 사와다 조지 작곡 노래 정보 검색 | TEXT raw source locator: d411b7e7, hash 7ee5c2b4 | SONOROUS 항목에서 Choro Club이 작사/작곡/편곡, 스트링스 편곡은 사와다 조지로 표시됩니다. |
| TEXT | 이토 에리코 작곡 사쿠라이 야스시의 노래를 검색해 주세요. | TEXT raw source locator: a5eb5182, hash 87cc3d0f | 해당 삽입곡은 마키노 유이가 노래하고, 작사는 이토 에리코, 작곡/편곡은 사쿠라이 야스시로 표시됩니다. |
| TEXT | 온지 마사유키 작화감독 정보 알려주세요. | TEXT raw source locator: 4354d136, hash 9d72960a | 전화 총 작화감독은 온지 마사유키(音地正行)입니다. |
| TEXT | 타케시타 켄이치 오쿠노 코타 인물 정보 | TEXT raw source locator: 8c659721, hash 1c9e812c | 타케시타 켄이치 오쿠노 코타 (奥野耕太)는 언급된 인물 중 한 명입니다. |
| TEXT | 이노우에 히데키가 혼자 만든 4화의 뛰어난 작화에 대한 내용은 무엇인가요? | TEXT raw source locator: 8674df01, hash 635675ee | 이노우에 히데키가 거의 혼자 만든 4화가 뛰어난 작화로 화제를 불렀으며, 사토 준이치 총감독이 이후의 시리즈는 3기 4화의 작화에 맞췄다고 할 정도로 큰 반향이 있었다. |
| TEXT | 교토 애니메이션에서 제작한 연애 게임 원작 학원편 애니메이션의 감독은 누구인가요? | TEXT raw source locator: 4d07e639, hash e4dab086 | 감독은 이시하라 타츠야이다. |
| TEXT | 아버지와의 불화로 농구선수라는 꿈을 접은 토모야의 고등학교 생활 | TEXT raw source locator: 12df9bc1, hash ad1112ec | 아버지와의 불화로 농구선수라는 꿈을 접은 오카자키 토모야는 고등학교에서 불량아로 유명하다. 개학 첫날, 토모야는 교문까지 이어지는 벚꽃이 흩날리는 언덕길에서 같은 3학년인 후루카와 나기사를 만난다. |
| TEXT | 2007년 3월 교토판의 방영 종료 후에 제작이 발표된 내용이 무엇인가요? | TEXT raw source locator: 97ac5ddd, hash 8a335403 | 2007년 3월 교토판 Kanon의 방영 종료 후에 간단한 PV를 보여주며 제작이 발표되어 동년 10월부터 방영되었다. |
| TEXT | 2010년 4월 30일부로 블루레이 발매 정보는 무엇인가요? | TEXT raw source locator: a9fef59a, hash 07a3e9a1 | 블루레이는 2010년 4월 30일부로 발매되었다. |
| TEXT | 1기가 평균 판매량과 2기의 판매량을 알려주세요. | TEXT raw source locator: 3b56206f, hash ade1450e | 1기가 평균 판매량은 24,940장이며, 2기는 평균 19,991장으로 상업적으로 상당한 성공을 거두었다. |
| TEXT | 미라지 오카자키 등장인물 성우 정보 | TEXT raw source locator: cbee17e6, hash d141566a | 오카자키 토모야의 성우는 일본 나카무라 유이치, 한국 대원방송 표영재, 미라지 김진홍으로 표시됩니다. |
| TEXT | 벚꽃이 흩날리는 언덕길에서 연출된 장면은 무엇입니까? | TEXT raw source locator: d578b5a2, hash a8768f9f | 벚꽃이 흩날리는 언덕길 장면으로 묘사됩니다. |
| TEXT | 제10회 천재 소녀의 도전 내용이 무엇인가요? | TEXT raw source locator: 1ebe776c, hash b900056c | 제10회 제목은 천재 소녀의 도전으로 표시됩니다. |
| TEXT | 제20회에서 숨겨진 과거에 대해 무엇을 다루나요? | TEXT raw source locator: b0f3ae85, hash 0a2ad11d | 제20회 제목은 숨겨진 과거로 표시됩니다. |
| TEXT | 문서가 설명하는 작품의 줄거리는 무엇입니까? | TEXT raw source locator: bf804c1d, hash 807fed7a | 이 문서가 설명하는 작품이나 인물 등에 대한 줄거리, 결말, 반전 요소 등을 직·간접적으로 포함하고 있습니다. 1~4화는 공통 루트이며, 후루카와 나기사 루트의 스토리를 바탕으로 흘러가지만 주요 등장인물들은 전부 소개하는 프롤로그 성격이 강합니다. |
| TEXT | 나기사가 병으로 쓰러진 것과 달리 후코는 어떻게 되었나요? | TEXT raw source locator: 6372029d, hash 1671c2a0 | 원작에서 나기사가 병으로 쓰러진 것과 달리, 후코는 사라질 때까지 함께하는 것으로 설명됩니다. |

## Evaluation Boundary

- 이 sample README는 대표 benchmark가 아닙니다.
- Official exact-evidence retrieval smoke는 28-query small-sample regression guard일 뿐, representative product-performance benchmark가 아닙니다.
- v3 comparable live diagnostic과 v3_8 계열 resolver diagnostics는 구분해서 읽어야 합니다.
- Promotion evidence, threshold tuning, winner selection, production mutation, qrels/gold/label/expected answer/supporting evidence mutation과 무관합니다.
- SourceAtom/source registry가 citation truth이고, vector index metadata는 candidate generation surface일 뿐입니다.
- TEXT/PDF/XLSX metrics are not collapsed into one headline score.
