# Before/After Metric Delta

- Status: `PASS`.
- Baseline TEXT profile: `baseline_text_title_section_bm25`.
- After TEXT profile: `tuned_text_section_boost_bm25`.
- Baseline PDF FILE lookup profile: `baseline_pdf_file_identity_tokens`.
- After PDF FILE lookup profile: `baseline_pdf_file_identity_tokens`.

## TEXT_MAIN_POSITIVE

| metric | before | after | delta |
|---|---:|---:|---:|
| Hit@1 | 0.7101 | 0.7246 | 0.0145 |
| Hit@3 | 0.7971 | 0.7971 | 0.0000 |
| Hit@5 | 0.8406 | 0.8261 | -0.0145 |
| Hit@10 | 0.8696 | 0.8696 | 0.0000 |
| MRR@10 | 0.7605 | 0.7710 | 0.0105 |
| recall@10 | 0.8696 | 0.8696 | 0.0000 |

## TEXT_ABSTAIN_DIAGNOSTIC

| metric | before | after | delta |
|---|---:|---:|---:|

## PDF_FILE_LOOKUP

| metric | before | after | delta |
|---|---:|---:|---:|
| Hit@1 | 0.3333 | 0.3333 | 0.0000 |
| Hit@3 | 0.5333 | 0.5333 | 0.0000 |
| Hit@5 | 0.8667 | 0.8667 | 0.0000 |
| Hit@10 | 0.9333 | 0.9333 | 0.0000 |
| MRR@10 | 0.4850 | 0.4850 | 0.0000 |
| recall@10 | 0.9333 | 0.9333 | 0.0000 |
| file_identity_confusion_rate | 0.6667 | 0.6667 | 0.0000 |

## PDF_FILE_LOOKUP_DIAGNOSTIC

| metric | before | after | delta |
|---|---:|---:|---:|
| Hit@1 | 0.2500 | 0.2500 | 0.0000 |
| Hit@3 | 0.2500 | 0.2500 | 0.0000 |
| Hit@5 | 0.2500 | 0.2500 | 0.0000 |
| Hit@10 | 0.2500 | 0.2500 | 0.0000 |
| MRR@10 | 0.2500 | 0.2500 | 0.0000 |
| recall@10 | 0.2500 | 0.2500 | 0.0000 |
| file_identity_confusion_rate | 0.7500 | 0.7500 | 0.0000 |
