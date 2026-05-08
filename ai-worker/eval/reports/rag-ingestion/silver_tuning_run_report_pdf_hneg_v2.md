# Silver Tuning Run Report

- Status: `PASS`.
- Selection data: `silver_only`.
- Frozen gold rows used for training: `0`.
- Selected TEXT profile: `tuned_text_section_boost_bm25`.
- Selected PDF FILE lookup profile: `baseline_pdf_file_identity_tokens`.
- PDF FILE lookup selection pool: `silver_pdf_file_lookup_train_rows_only`; frozen gold eval rows used: `false`.
- PDF FILE lookup selection pool candidate count: `4`; frozen-gold-only identities used: `0`.
- PDF FILE lookup frozen-gold document_version_id values used: `0`.

## TEXT Candidates

| profile | objective | Hit@10 | MRR@10 | recall@10 | hard_negative_confusion_rate |
|---|---:|---:|---:|---:|---:|
| `tuned_text_section_boost_bm25` | 0.7870 | 0.8250 | 0.7243 | 0.8250 | 0.0110 |
| `baseline_text_title_section_bm25` | 0.7783 | 0.8167 | 0.7148 | 0.8167 | 0.0110 |
| `tuned_text_chunk_balanced_bm25` | 0.7567 | 0.7917 | 0.6996 | 0.7917 | 0.0110 |

## PDF FILE Lookup Candidates

| profile | objective | Hit@10 | MRR@10 | recall@10 | hard_negative_confusion_rate |
|---|---:|---:|---:|---:|---:|
| `baseline_pdf_file_identity_tokens` | 0.8719 | 1.0000 | 0.8125 | 1.0000 | 0.2500 |
| `tuned_pdf_file_identity_metadata_boost` | 0.8719 | 1.0000 | 0.8125 | 1.0000 | 0.2500 |
