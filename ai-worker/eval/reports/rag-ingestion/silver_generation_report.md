# Silver Generation Report

## Status

- Status: `silver_generated_tuning_only`.
- Gold eval rows were excluded from silver training by query id, query text, source query id, and expected id checks.
- Official gold: `false` for every silver row.

## Outputs

- `silver_text_positive_train.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_text_positive_train.csv`
- `silver_text_hard_negative_train.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_text_hard_negative_train.csv`
- `silver_text_abstain_diagnostic.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_text_abstain_diagnostic.csv`
- `silver_pdf_file_lookup_positive_train.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_pdf_file_lookup_positive_train.csv`
- `silver_pdf_file_lookup_hard_negative_train.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_pdf_file_lookup_hard_negative_train.csv`
- `silver_manifest.csv`: `ai-worker/eval/review/gold_silver_tuning/silver_manifest.csv`

## Row Counts

- `silver_text_positive_train`: `120`
- `silver_text_hard_negative_train`: `91`
- `silver_text_abstain_diagnostic`: `10`
- `silver_pdf_file_lookup_positive_train`: `4`
- `silver_pdf_file_lookup_hard_negative_train`: `4`
- `silver_manifest`: `5`

## Silver Leakage Checks

- Status: `PASS`.
- Exact query-id overlaps: `0`.
- Exact query text overlaps: `0`.
- Source query-id overlaps: `0`.
- Expected-id overlaps: `0`.
- Duplicate silver queries: `95`.

## Gold/Silver Separation Proof

- The frozen gold candidate keys were collected from cleaned TEXT main positive rows and PDF FILE lookup positive rows.
- TEXT silver positives come from Phase 7 manual-curated silver rows only when expected document/chunk ids do not overlap frozen gold ids and evidence is found in the referenced chunk.
- TEXT hard negatives reuse query surfaces only against wrong ids and remain `TUNING_ONLY`.
- PDF FILE lookup silver rows use expected file identity only and exclude frozen gold source query ids and query text.

## PDF FILE Lookup Guardrails

- `retrieval_lane=pdf_file_lookup` on PDF silver rows.
- `expected_evidence_policy=EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY`.
- No page, bbox, table, row, column, or value semantics are used or claimed.

## Recommended Next Command

```powershell
python ai-worker/scripts/rag_reviewed_gold_cleanup_and_silver_generation.py
```
