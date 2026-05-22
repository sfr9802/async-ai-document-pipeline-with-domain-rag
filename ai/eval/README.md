# Evaluation Harness Samples

이 파일은 TEXT/PDF/XLSX의 query -> evidence -> response 표면을 빠르게 보여주는 샘플입니다. 
대표 성능 benchmark나 promotion evidence가 아닙니다.

## Portfolio-Facing Samples

| Track | Query | Evidence surface | Response |
|---|---|---|---|
| PDF | 1월 산업활동에서 생산 지표는 어떻게 움직였나요? | PDF page citation: 최근경제동향 PDF p.5 | 1월 산업활동에서 광공업 생산, 서비스업 생산, 건설투자는 감소했습니다. |
| PDF | 2020년 한국 원달러 기말 환율은 얼마인가요? | PDF page citation: 최근경제동향 PDF p.65 | 2020년 한국 원달러 기말 환율은 1,088.0입니다. |
| PDF | 2024년 수출입차 금액은 얼마인가요? | PDF page citation: 최근경제동향 PDF p.61 | 2024년 수출입차 금액은 6,836.1입니다. |
| XLSX | 2019년 2월 5호선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 철도 sheet, D352 | 2019년 2월 5호선의 승차총승객수는 15,446,522명입니다. |
| XLSX | 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까? | XLSX sheet/range/cell: 일반현황 sheet, C702 | 2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 41786입니다. |
| XLSX | 2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까? | XLSX sheet/range/cell: 일반현황 sheet, G752 | 해뜨는요양원2의 시도 시군구 법정동명은 대구광역시 북구 복현동입니다. |
| XLSX | 2018년 7월 8호선의 승차총승객수는 몇 명입니까? | XLSX sheet/range/cell: 철도 sheet, D402 | 2018년 7월 8호선의 승차총승객수는 5,630,084명입니다. |
| TEXT | 자동판매기 미궁 방랑 애니 3기 방영 시기는 문서에 어떻게 적혀 있어 | TEXT chunk/source context | 자동판매기로 다시 태어난 나는 미궁을 방랑한다를 원작으로 하는 TV 애니메이션 시리즈 중 제3기의 방영 시기는 2026년 4월입니다. |
| TEXT | 유우야키의 나이와 생일은 어떻게 적혀 있어 | TEXT chunk/source context | 유우야키의 나이는 16세이고 생일은 9월 29일입니다. |
| TEXT | 미츠하는 타키를 만나려고 어디로 향했어 | TEXT chunk/source context | 미츠하는 타키를 실제로 만나기 위해 도쿄로 향했습니다. |

## Diagnostic / Raw Locator Samples

이 섹션은 일반 사용자 질의 품질을 보여주기 위한 샘플이 아니라 locator/source hydration 확인용입니다. 
PDF text block, chunk id, hash, location id가 prompt에 직접 노출되는 질의는 portfolio-facing sample에서 제외합니다.

| Track | Query | Evidence surface | Response |
|---|---|---|---|
| PDF | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF raw text_block locator | 사 업 보고서가 확인됩니다. |
| PDF | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 75a7abdb | PDF raw text_block locator | 정 관 |
| PDF | PDF 1쪽 text_block에서 확인되는 내용은 무엇인가요? 위치 ed3786f8 | PDF raw text_block locator | PDF 1쪽 text_block에서 확인되는 내용은 감사보고서입니다. |
| PDF | PDF 34쪽 text_block에서 확인되는 내용은 무엇인가요? | PDF raw text_block locator | PDF 34쪽 text_block에서 확인되는 내용은 이혼율입니다. |
| TEXT | 텍스트 조각 8674df01에서 확인되는 내용은 무엇인가요? | TEXT raw chunk locator | 텍스트 조각 8674df01에서 확인되는 내용은 이노우에 히데키의 4화가 뛰어난 작화로 화제를 불렀으며, 사토 준이치가 이후의 시리즈는 3기 4화의 작화에 맞췄다는 것입니다. |
| TEXT | 텍스트 조각 4d07e639에서 확인되는 내용은 무엇인가요? | TEXT raw chunk locator | 텍스트 조각 4d07e639는 CLANNAD의 학원편 일부분을 원작으로 하는 TV 애니메이션입니다. |
| TEXT | 텍스트 조각 12df9bc1에서 확인되는 내용은 무엇인가요? | TEXT raw chunk locator | 텍스트 조각 12df9bc1에서 확인되는 내용은 아버지와의 불화로 농구선수라는 꿈을 접은 오카자키 토모야가 고등학교에서 불량아로 유명하며, 개학 첫날 후루카와 나기사를 만나는 내용입니다. |

## Evaluation Boundary

- 이 sample README는 대표 benchmark가 아닙니다.
- Promotion evidence, threshold tuning, winner selection, production mutation, qrels/gold/label/expected answer/supporting evidence mutation과 무관합니다.
- SourceAtom/source registry가 citation truth이고, vector index metadata는 candidate generation surface일 뿐입니다.
- TEXT/PDF/XLSX metrics are not collapsed into one headline score.
