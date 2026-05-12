# Gold Policy User-Approved Resolutions v1

- Status: `PASS`
- Generated at: `2026-05-12T03:37:23.645127+00:00`
- Source decision draft: `ai-worker/eval/review/rag_gold_policy_decision_draft_v1.json`
- Source review sheet: `ai-worker/eval/review/rag_gold_policy_user_review_sheet_v1.md`
- This artifact records user gold-policy decisions only. It is not a frozen official denominator.

## Counts

- XLSX approved draft candidates: `23`
- XLSX pending evidence: `2`
- PDF approved excludes: `6`
- PDF excluded because stable identity is required: `3`
- TEXT/Namu carried forward unresolved: `23`

## Draft Candidate Manifest

- Status: `DRAFT_ONLY_NOT_FROZEN`
- XLSX draft candidate IDs: `gq_xlsx_lookup_001`, `gq_xlsx_lookup_004`, `gq_xlsx_lookup_005`, `gq_xlsx_lookup_006`, `gq_xlsx_lookup_007`, `gq_xlsx_lookup_008`, `gq_xlsx_date_number_format_001`, `gq_xlsx_aggregation_002`, `gq_auto_012`, `gq_auto_017`, `gq_auto_018`, `gq_auto_022`, `gq_auto_023`, `gq_auto_028`, `gq_auto_031`, `gq_auto_034`, `gq_auto_035`, `gq_auto_036`, `gq_auto_037`, `gq_auto_038`, `gq_auto_040`, `gq_auto_043`, `gq_auto_044`
- XLSX pending evidence excluded from manifest: `gq_xlsx_date_number_format_003`, `gq_xlsx_aggregation_001`
- Official denominator registry mutation: `false`

## XLSX Pending Evidence

- `gq_xlsx_date_number_format_003`: keep pending; candidate manifest inclusion is `false`; expected answer status `NOT_FINAL`, evidence status `PENDING_VERIFICATION`.
- `gq_xlsx_aggregation_001`: keep pending; candidate manifest inclusion is `false`; expected answer status `USER_REQUIRED`, evidence status `USER_REQUIRED`.

## PDF Exclusions

- Approved 6-row exclude batch: `pdf_file_lookup_content_anchor_004`, `pdf_file_lookup_content_anchor_012`, `pdf_file_lookup_content_anchor_013`, `pdf_file_lookup_content_anchor_014`, `pdf_file_lookup_content_anchor_015`, `pdf_file_lookup_metadata_002`
- Stable-identity-required excludes: `pdf_file_lookup_content_anchor_017`, `pdf_file_lookup_content_anchor_018`, `pdf_file_lookup_content_anchor_020`
- These rows are not retrieval failures and are not content-evidence positives.

## TEXT/Namu Carry-Forward

- Unresolved rows: `23`
- Row IDs: `text_namu_v2_0006`, `text_namu_v2_0010`, `text_namu_v2_0013`, `text_namu_v2_0019`, `text_namu_v2_0020`, `text_namu_v2_0023`, `text_namu_v2_0024`, `text_namu_v2_0027`, `text_namu_v2_0029`, `text_namu_v2_0031`, `text_namu_v2_0033`, `text_namu_v2_0043`, `text_namu_v2_0044`, `text_namu_v2_0066`, `text_namu_v2_0067`, `text_namu_v2_0078`, `text_namu_v2_0080`, `text_namu_v2_0082`, `text_namu_v2_0091`, `text_namu_v2_0092`, `text_namu_v2_0093`, `text_namu_v2_0094`, `text_namu_v2_0095`
- Resolution attempted: `false`
- Include in gold_v0.1: `false`

## Guardrails

- official_denominator_registry.json changed: `False`
- retrieval variants ran: `False`
- production namespace mutated: `False`
- diagnostic-only row promoted: `False`
- policy-excluded rows counted as retrieval failures: `False`
