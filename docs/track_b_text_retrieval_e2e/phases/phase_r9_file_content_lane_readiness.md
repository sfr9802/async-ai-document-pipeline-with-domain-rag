# R9 — XLSX/PDF FILE vs CONTENT Lane Readiness Report

## Goal

현재 준비 상태를 명확히 분리해 future work가 잘못된 lane으로 진행되지 않게 한다.

## New Files

```text
scripts/rag_file_content_lane_readiness.py
reports/rag_file_content_lane_readiness_report.json
```

## Lane Readiness Table

```text
B_NAMU_TEXT_CONTENT:
  blocked until R2/R3, then ready for R5

TEXT_FILE_LOOKUP:
  planned; requires text document/page metadata lookup design

XLSX_CONTENT:
  diagnostic-ready using Track A reviewed XLSX content set

XLSX_FILE_LOOKUP:
  not ready; requires file-level searchable metadata index

PDF_CONTENT:
  blocked on Track C metadata projection readiness

PDF_FILE_LOOKUP:
  not ready; requires file-level searchable metadata index
```

## File Lookup Index Requirements

```text
file_name
title
source path
document title
document version
file_type
sheet names for XLSX
page titles / section headings for PDF
captions / table names
upload/import metadata
detected keywords
```

## Acceptance Criteria

- XLSX/PDF file lookup is not reported as ready because content vector exists.
- PDF content is blocked until metadata projection requirements are met.
- XLSX content is labeled diagnostic-ready, not promotion-ready.
