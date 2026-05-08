# Reviewed Gold Cleanup Report

## Status

- Status: `completed_diagnostic_candidate_freeze`.
- Official denominator registry changed: `false`.
- Promotion evidence: `false`.
- The reviewed input rows were normalized as source-review signals only; Codex did not decide true gold labels.

## Inputs

- `text_review_csv`: `ai-worker/eval/review/text_namu_v2_gold_review/text_namu_v2_gold_review_pack - text_namu_v2_gold_review_pack.csv` (`sha256=5a2407089a5c5c22cf8f0101b76bba23a8c991fe7d2fa3f7fb89e395b56e4d0a`, `bytes=218141`).
- `pdf_file_lookup_review_csv`: `ai-worker/eval/review/pdf_supplemental_gold_review/pdf_gold_review_pack_manual_v1_file_lookup_companion - pdf_gold_review_pack_manual_v1_file_lookup_companion.csv` (`sha256=c77f8b431c2cef5dffac5a968606c309eb653ec506efeb7ad37190c45f8b2b9a`, `bytes=29850`).
- `official_denominator_registry`: `ai-worker/eval/eval_queries/official_denominator_registry.json` (`sha256=8f5e6bde33ff7cd68cfcc3d43bca976ca59799b78e490fab440ec2651c52fc22`, `bytes=8455`).

## Outputs

- `text_gold_main_positive_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/text_gold_main_positive_clean.csv`
- `text_gold_abstain_diagnostic_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/text_gold_abstain_diagnostic_clean.csv`
- `text_gold_deferred_or_excluded_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/text_gold_deferred_or_excluded_clean.csv`
- `pdf_file_lookup_gold_positive_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/pdf_file_lookup_gold_positive_clean.csv`
- `pdf_file_lookup_diagnostic_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/pdf_file_lookup_diagnostic_clean.csv`
- `pdf_file_lookup_deferred_or_excluded_clean.csv`: `ai-worker/eval/review/gold_silver_tuning/pdf_file_lookup_deferred_or_excluded_clean.csv`

## TEXT Cleanup Counts

- Main positive candidates: `69`.
- Abstain diagnostic rows: `10`.
- Deferred or excluded rows: `21`.
- Counts by cleanup status: `{'CLEANED_POSITIVE': 69, 'DEFERRED_LABEL_CONFLICT': 7, 'DEFERRED_MISSING_ANSWERABILITY': 2, 'DEFERRED_NEEDS_SECOND_REVIEW': 3, 'DIAGNOSTIC_ONLY': 8, 'EXCLUDED_BY_CONSERVATIVE_POLICY': 8, 'MISSING_REQUIRED_OVERRIDE': 3}`.
- Counts by denominator role: `{'DEFERRED': 21, 'TEXT_ABSTAIN_DIAGNOSTIC': 10, 'TEXT_MAIN_POSITIVE_GOLD_CANDIDATE': 69}`.
- Conflicts found: `9` rows.
- Missing required overrides: `3` rows.
- Rows deferred for NEEDS_SECOND_REVIEW: `3` rows.

## PDF FILE Lookup Cleanup Counts

- FILE lookup candidates: `15`.
- Diagnostic rows: `4`.
- Deferred or excluded rows: `9`.
- Counts by cleanup status: `{'CLEANED_FILE_LOOKUP_POSITIVE': 15, 'DEFERRED_MIXED_GOLD_DECISION': 1, 'DIAGNOSTIC_OR_EXCLUDED_BY_FILE_LOOKUP_POLICY': 12}`.
- Counts by denominator role: `{'DEFERRED': 9, 'PDF_FILE_LOOKUP_DIAGNOSTIC': 4, 'PDF_FILE_LOOKUP_GOLD_CANDIDATE': 15}`.
- Generic filename identity-risk rows: `11`.
- Mixed user-decision rows: `1`.

## Normalization Rules

- TEXT: trimmed whitespace on all fields.
- TEXT: treated empty strings as null for validation decisions.
- TEXT: split comma/semicolon/pipe user decision cells only to detect conflicts.
- TEXT: did not choose a gold label for conflicting answerability cells.
- TEXT: did not modify provenance columns.
- PDF FILE lookup: trimmed whitespace on all fields.
- PDF FILE lookup: treated empty strings as null for validation decisions.
- PDF FILE lookup: normalized clear FILE lookup positives to ANSWERABLE_AS_FILE_LOOKUP.
- PDF FILE lookup: normalized clear FILE lookup evidence policy to EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY.
- PDF FILE lookup: kept NOT_ANSWERABLE, IRRELEVANT, PARTIAL, REVISE_EXPECTED_EVIDENCE, mixed decisions, and weak generic filenames out of official positives.

## Deferred Rows

- TEXT label conflicts: `text_namu_v2_0019, text_namu_v2_0020, text_namu_v2_0027, text_namu_v2_0033, text_namu_v2_0066, text_namu_v2_0067, text_namu_v2_0078, text_namu_v2_0080, text_namu_v2_0082`.
- TEXT missing overrides: `text_namu_v2_0006, text_namu_v2_0013, text_namu_v2_0029`.
- TEXT NEEDS_SECOND_REVIEW: `text_namu_v2_0010, text_namu_v2_0078, text_namu_v2_0080`.
- PDF mixed decisions: `pdf_file_lookup_content_anchor_017`.
- PDF generic filename risk rows: `pdf_file_lookup_content_anchor_011, pdf_file_lookup_content_anchor_012, pdf_file_lookup_content_anchor_013, pdf_file_lookup_content_anchor_014, pdf_file_lookup_content_anchor_015, pdf_file_lookup_content_anchor_016, pdf_file_lookup_content_anchor_017, pdf_file_lookup_content_anchor_018, pdf_file_lookup_content_anchor_019, pdf_file_lookup_content_anchor_020, pdf_file_lookup_content_anchor_021`.

## PDF FILE Lookup Guardrails

- Companion rows are FILE lookup only.
- They are not part of the PDF content retrieval denominator.
- Evaluation target is expected file identity only.
- No success is claimed for page, bbox, table, row, column, or value semantics.
- `GENERIC_FILENAME_IDENTITY_RISK` was added for generic filename rows and weak identity rows were kept diagnostic or deferred.

## Recommended Next Command

```powershell
python ai-worker/scripts/rag_reviewed_gold_cleanup_and_silver_generation.py
```
