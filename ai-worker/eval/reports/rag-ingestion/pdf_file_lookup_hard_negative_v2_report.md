# PDF FILE Lookup Hard Negative V2 Report

- Status: `PASS`.
- Source rows: `silver_pdf_file_lookup_train_rows_only`.
- Frozen gold values used for sampling: `false`.
- Frozen gold values used only as exclusion guards: `true`.
- Output CSV: `ai-worker/eval/review/gold_silver_tuning/silver_pdf_file_lookup_hard_negative_v2.csv`.
- PDF FILE lookup semantics: `file_identity_only`.
- Content/page/bbox/table/row/column/value success claimed: `false`.
- Denominator role: `TUNING_ONLY`; official_gold: `false`.

## Counts

- Silver positive rows: `4`.
- Silver train identity candidates: `4`.
- Generated rows: `12`.
- Frozen gold file identities excluded by guard: `14`.
- Frozen gold document_version_id values excluded by guard: `0`.

## Strategy Counts

- `same_metadata_family_wrong_file_identity`: `12`

## Validation

- generated_rows_are_tuning_only: `true`
- generated_rows_official_gold_false: `true`
- generated_rows_exclude_frozen_gold_file_identities: `true`
- generated_rows_exclude_frozen_gold_document_version_ids: `true`
- generated_queries_exclude_frozen_gold_query_text: `true`
