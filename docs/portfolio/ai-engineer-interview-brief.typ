#let white = rgb("#ffffff")
#let black = rgb("#111111")
#let gray = rgb("#666666")
#let light = rgb("#dddddd")

#set document(title: "", author: "")

#set page(
  paper: "a4",
  margin: (top: 18mm, right: 17mm, bottom: 18mm, left: 17mm),
  fill: white,
)

#set text(
  font: ("Malgun Gothic", "Arial"),
  size: 9.4pt,
  fill: black,
  lang: "ko",
)

#set par(leading: 0.9em, spacing: 0.45em)

#let section(title) = {
  text(size: 9.6pt, weight: "bold", fill: black)[#title]
  v(2pt)
  line(length: 100%, stroke: 0.45pt + black)
  v(10pt)
}

#let entry-title(title, meta) = {
  if meta == "" {
    text(size: 11.2pt, weight: "bold")[#title]
  } else {
    grid(
      columns: (1fr, auto),
      column-gutter: 12pt,
      align: horizon,
      text(size: 11.2pt, weight: "bold")[#title],
      text(size: 8pt, fill: gray)[#meta],
    )
  }
  v(7pt)
}

#let row(label, body) = {
  grid(
    columns: (18mm, 1fr),
    column-gutter: 8pt,
    text(size: 7.7pt, weight: "bold", fill: gray)[#label],
    text(size: 9.05pt)[#body],
  )
  v(5.6pt)
}

#let entry(title, meta, rows) = {
  entry-title(title, meta)
  for item in rows {
    row(item.at(0), item.at(1))
  }
  v(12pt)
}

#let divider() = {
  v(3pt)
  line(length: 100%, stroke: 0.35pt + light)
  v(11pt)
}

#section("이전 경력")

#entry(
  "㈜에트넷 · Developer · 2022.07–2023.03",
  "",
  (
    ("역할", [상담사가 셋톱박스, 모뎀, 공유기, IoT 장비 상태를 원격으로 확인하는 대시보드를 정리했습니다.]),
    ("작업", [로그 조회, 통계 가공, 차트 화면, 배포 환경 상태 확인을 구현하고, Java/Flask 기반 API와 React 화면을 함께 다뤘습니다.]),
  ),
)

#divider()

#entry(
  "㈜써밋라이즈에듀 · Backend Engineer · 2024.07–2026.06",
  "",
  (
    ("역할", [문서 처리 작업, API 계약, 배포 운영 흐름을 담당했습니다. 긴 작업을 API 안에서 직접 처리하지 않고 작업 상태와 실행 책임을 분리하는 구조를 다뤘습니다.]),
    ("구조", [메인 API에서 문서 작업 생성, 상태 변경, 결과 반영을 구현했습니다.#linebreak()실제 처리 모듈이 연결되지 않은 OCR/멀티모달·추천 응답 구간은 mock 데이터로 대체해#linebreak()API 계약, 상태 전이, 결과 반영 흐름을 검증했습니다.]),
    ("작업", [배포 환경, 비동기 작업 큐, 임시 접근 URL, 중복 실행 방지, 작업 상태 전이를 다뤘습니다. 긴 작업의 추적과 검증에 필요한 요소였습니다.]),
  ),
)

#v(7pt)

#section("핵심 프로젝트")

#entry(
  "async-ocr-rag-multimodal-pipeline · 2026 · 근거 중심 문서 QA",
  "",
  (
    ("문제", [문서 질문답변 시스템의 핵심 위험은 답변 문장보다 근거 경계 관리라고 봤습니다. 어떤 근거로 답했는지, 근거가 부족할 때 어디에서 중단했는지를 설명할 수 있어야 합니다.]),
    ("설계", [검색 후보와 최종 답변 근거를 분리했습니다. 답변에는 문서 위치, 표 값, 행/열 맥락처럼 확인된 근거만 연결하도록 했습니다.]),
    ("처리 흐름", [질문에 맞는 문서 후보를 찾고, 근거를 묶습니다. 근거가 충분할 때만 답변을 생성·점검합니다. 근거 부족 시 중단하고, 단계별 실패 지점을 따로 볼 수 있게 했습니다.]),
    ("문서 해석", [Excel은 값 하나만이 아니라 어떤 행, 기간, 컬럼에서 나온 값인지가 중요합니다. PDF도 페이지 번호뿐 아니라 어느 단락이나 표에서 나온 정보인지 함께 남기도록 설계했습니다.]),
    ("확인 방식", [실행마다 검색 후보 수, 통과·제외된 근거, 누락 조건, 중단 사유를 기록합니다. 이를 통해 실패 케이스에서도 병목을 좁힐 수 있습니다.]),
    ("원칙", [근거가 부족한 답변을 억지로 성공 처리하지 않습니다. 성능 개선은 새 측정 결과가 있을 때만 판단하고, 민감한 원문 질문/답변은 저장하지 않습니다.]),
  ),
)
