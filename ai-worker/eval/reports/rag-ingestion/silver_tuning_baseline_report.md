# Silver Tuning Baseline Report

- Status: `PASS`.
- Role: baseline before silver-only diagnostic profile selection.
- Official denominator registry changed: `false`.
- PDF FILE lookup semantics: file identity only.

## Lane Metrics

| lane | profile/status | rows | Hit@10 | MRR@10 | recall@10 | notes |
|---|---|---:|---:|---:|---:|---|
| TEXT_MAIN_POSITIVE | `baseline_text_title_section_bm25` | 69 | 0.8696 | 0.7605 | 0.8696 |  |
| TEXT_ABSTAIN_DIAGNOSTIC | `baseline_text_title_section_bm25` | 10 |  |  |  | diagnostic_only_not_main_positive |
| PDF_FILE_LOOKUP | `baseline_pdf_file_identity_tokens` | 15 | 0.9333 | 0.4850 | 0.9333 | file_identity_confusion_rate=0.6667; file_identity_only |
| PDF_FILE_LOOKUP_DIAGNOSTIC | `baseline_pdf_file_identity_tokens` | 4 | 0.2500 | 0.2500 | 0.2500 | file_identity_confusion_rate=0.7500; file_identity_only |
| XLSX | `REPORT_ONLY_INCLUDED` |  |  |  |  |  |

## Notes

- phase7_human_gold_tune.py remains the older gold-50/silver-500 CLI. This pass uses the explicit silver_only_tuning_config.yaml so frozen cleaned gold candidates are evaluated only after silver profile selection.
