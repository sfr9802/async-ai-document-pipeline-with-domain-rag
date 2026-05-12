# Gold Policy User Review Sheet v1

- Status: `APPLIED`
- Applied at: `2026-05-12T03:41:39.067079+00:00`
- Applied-decision artifact: `ai-worker/eval/review/rag_gold_policy_applied_decisions_v1.json`
- This sheet records user policy decisions only. It does not freeze an official denominator.
- Guardrails: no retrieval variants, no production namespace mutation, no denominator registry edit, no diagnostic-only promotion, and no PDF content/file-identity aggregation.

## Applied Decision Summary

- [x] XLSX include-candidate batch approved as draft `gold_v0.1` candidates only: `23` rows.
- [x] XLSX pending evidence kept out of candidate manifest: `gq_xlsx_date_number_format_003`, `gq_xlsx_aggregation_001`.
- [x] PDF exclude batch approved as `EXCLUDE_FROM_GOLD_V0_1`: `6` rows.
- [x] PDF generic filename identity rejected; stable document identity required; excluded from `gold_v0.1`: `pdf_file_lookup_content_anchor_017`, `pdf_file_lookup_content_anchor_018`, `pdf_file_lookup_content_anchor_020`.
- [x] TEXT/Namu unresolved rows carried forward unchanged and excluded from `gold_v0.1`: `23` rows.

## XLSX Pending Evidence Rows

- `gq_xlsx_date_number_format_003`: `KEEP_PENDING_EVIDENCE`; do not include in `gold_v0.1` candidate manifest until exact evidence/citation sufficiency is verified.
- `gq_xlsx_aggregation_001`: `KEEP_PENDING_EVIDENCE`; do not include in `gold_v0.1`; expected answer and supporting evidence remain `USER_REQUIRED`.

## PDF Applied Exclusions

- Exclude batch: `pdf_file_lookup_content_anchor_004`, `pdf_file_lookup_content_anchor_012`, `pdf_file_lookup_content_anchor_013`, `pdf_file_lookup_content_anchor_014`, `pdf_file_lookup_content_anchor_015`, `pdf_file_lookup_metadata_002`
- Stable-identity-required excludes: `pdf_file_lookup_content_anchor_017`, `pdf_file_lookup_content_anchor_018`, `pdf_file_lookup_content_anchor_020`
- These rows are not retrieval failures and are not content-evidence positives.

## XLSX Draft Candidate Batch

- Draft candidate IDs: `gq_xlsx_lookup_001`, `gq_xlsx_lookup_004`, `gq_xlsx_lookup_005`, `gq_xlsx_lookup_006`, `gq_xlsx_lookup_007`, `gq_xlsx_lookup_008`, `gq_xlsx_date_number_format_001`, `gq_xlsx_aggregation_002`, `gq_auto_012`, `gq_auto_017`, `gq_auto_018`, `gq_auto_022`, `gq_auto_023`, `gq_auto_028`, `gq_auto_031`, `gq_auto_034`, `gq_auto_035`, `gq_auto_036`, `gq_auto_037`, `gq_auto_038`, `gq_auto_040`, `gq_auto_043`, `gq_auto_044`
- What remains not frozen: official denominator registry, official denominator membership, and future scoring policy.

## TEXT/Namu Carry-Forward

- Row IDs: `text_namu_v2_0006`, `text_namu_v2_0010`, `text_namu_v2_0013`, `text_namu_v2_0019`, `text_namu_v2_0020`, `text_namu_v2_0023`, `text_namu_v2_0024`, `text_namu_v2_0027`, `text_namu_v2_0029`, `text_namu_v2_0031`, `text_namu_v2_0033`, `text_namu_v2_0043`, `text_namu_v2_0044`, `text_namu_v2_0066`, `text_namu_v2_0067`, `text_namu_v2_0078`, `text_namu_v2_0080`, `text_namu_v2_0082`, `text_namu_v2_0091`, `text_namu_v2_0092`, `text_namu_v2_0093`, `text_namu_v2_0094`, `text_namu_v2_0095`
- Resolution attempted: `false`
- Include in `gold_v0.1`: `false`

## Guardrail Confirmation

- official_denominator_registry.json changed: `False`
- official denominator opened/frozen: `False`
- retrieval variants ran: `False`
- production namespace mutated: `False`
- diagnostic-only row promoted: `False`
- PDF content/file identity lanes aggregated: `False`
