# Official Metric Pre-Execution Smoke Report v1

- Status: `OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS_WITH_DIAGNOSTIC_WARNINGS`
- Registry-backed official input rows: `29`
- Rows by track: `{"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19}`
- Official metric execution started: `false`
- Tuning run started: `false`
- Promotion evidence: `false`
- Validation ok: `true`
- TEXT potential support coverage gaps: `1`

## CSV Inputs

| Track | Rows | SHA256 | Denominator key | Metric lane |
| --- | ---: | --- | --- | --- |
| `pdf_business_ocr_mm` | `4` | `6bb09a0a61f4e3bea76869c6893c67ab810720e188814e3e8113740288a79998` | `track_c_pdf_question_gold_v2_human_audit_approved` | `answer_citation` |
| `text_namu_v2_1` | `6` | `03764d1d7aa682cd8646d9028b6219fdbeba8a4eb219a87a285a162f16702cd6` | `track_b_text_namu_v2_1_question_gold_v2_human_audit_approved` | `answer_citation` |
| `xlsx_business_structured` | `19` | `b28f42ad395b90b97795decc0b3cc91f0dc4fa515f22863d72c66508bb666f40` | `track_a_xlsx_question_gold_v2_human_audit_approved` | `answer_citation` |

## Validation

- `PASS`

## Diagnostic Warnings

- `TEXT expected_answer support coverage has diagnostic-only potential gaps`

Official metric execution still not started, tuning still not started, promotion evidence not created.
