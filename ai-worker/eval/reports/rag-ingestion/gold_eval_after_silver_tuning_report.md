# Gold Eval After Silver Tuning Report

- Status: `PASS`.
- Evaluation data: frozen cleaned gold candidates only.
- Training data: `0` frozen gold rows.
- Selected TEXT profile: `tuned_text_section_boost_bm25`.
- Selected PDF FILE lookup profile: `baseline_pdf_file_identity_tokens`.

## Lane Metrics

| lane | profile/status | rows | Hit@10 | MRR@10 | recall@10 | notes |
|---|---|---:|---:|---:|---:|---|
| TEXT_MAIN_POSITIVE | `tuned_text_section_boost_bm25` | 69 | 0.8696 | 0.7710 | 0.8696 |  |
| TEXT_ABSTAIN_DIAGNOSTIC | `tuned_text_section_boost_bm25` | 10 |  |  |  | diagnostic_only_not_main_positive |
| PDF_FILE_LOOKUP | `baseline_pdf_file_identity_tokens` | 15 | 0.9333 | 0.4850 | 0.9333 | file_identity_confusion_rate=0.6667; file_identity_only |
| PDF_FILE_LOOKUP_DIAGNOSTIC | `baseline_pdf_file_identity_tokens` | 4 | 0.2500 | 0.2500 | 0.2500 | file_identity_confusion_rate=0.7500; file_identity_only |
| XLSX | `REPORT_ONLY_INCLUDED` |  |  |  |  |  |
