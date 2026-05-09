# PDF FILE Lookup Wrongly Supported Root Cause

- Status: `PASS`.
- Scope: diagnostic-only analysis of pre-calibration wrongly-supported cases.
- Policy: PDF FILE lookup remains file identity only; no page/bbox/table/row/column/value success is claimed.

## Counts

- case_count: `10`
- filename_token_overlap_only: `10`
- sufficiency_judge_issue: `10`

## Cases

| case_id | query_id | target_file_name | candidate_file_name | classifications |
|---|---|---|---|---|
| expanded_pdf_file_lookup_005 | silver_pdf_file_hneg_v2_0001 | `2024년도+4월+1일+시행+전기요금표(종합)_출력용.pdf` | `2024년도+7월+1일+시행+전기요금표(종합).pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |
| expanded_pdf_file_lookup_006 | silver_pdf_file_hneg_v2_0002 | `2024년도+4월+1일+시행+전기요금표(종합)_출력용.pdf` | `2025년도+4월+1일+시행+전기요금표(종합).pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |
| expanded_pdf_file_lookup_008 | silver_pdf_file_hneg_v2_0004 | `2024년도+7월+1일+시행+전기요금표(종합).pdf` | `2024년도+4월+1일+시행+전기요금표(종합)_출력용.pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |
| expanded_pdf_file_lookup_009 | silver_pdf_file_hneg_v2_0005 | `2024년도+7월+1일+시행+전기요금표(종합).pdf` | `2025년도+4월+1일+시행+전기요금표(종합).pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |
| expanded_pdf_file_lookup_010 | silver_pdf_file_hneg_v2_0006 | `2024년도+7월+1일+시행+전기요금표(종합).pdf` | `23.05.16+시행_전기요금표_종합.pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |
| expanded_pdf_file_lookup_011 | silver_pdf_file_hneg_v2_0007 | `2025년도+4월+1일+시행+전기요금표(종합).pdf` | `2024년도+4월+1일+시행+전기요금표(종합)_출력용.pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |
| expanded_pdf_file_lookup_012 | silver_pdf_file_hneg_v2_0008 | `2025년도+4월+1일+시행+전기요금표(종합).pdf` | `2024년도+7월+1일+시행+전기요금표(종합).pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |
| expanded_pdf_file_lookup_013 | silver_pdf_file_hneg_v2_0009 | `2025년도+4월+1일+시행+전기요금표(종합).pdf` | `23.05.16+시행_전기요금표_종합.pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |
| expanded_pdf_file_lookup_015 | silver_pdf_file_hneg_v2_0011 | `23.05.16+시행_전기요금표_종합.pdf` | `2024년도+7월+1일+시행+전기요금표(종합).pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |
| expanded_pdf_file_lookup_016 | silver_pdf_file_hneg_v2_0012 | `23.05.16+시행_전기요금표_종합.pdf` | `2025년도+4월+1일+시행+전기요금표(종합).pdf` | `filename_token_overlap_only, sufficiency_judge_issue` |

## Recommended Fix

- Require exact/canonical target file identity match before PDF FILE lookup can be SUPPORTED.
- Fail closed on hard-negative labels, filename-token-only overlap, generic filenames without strong ids, document_version_id mismatch, and source_file_id mismatch.
- Keep answer_intent=file_identity in the PDF FILE lookup lane while still blocking content/page/bbox/table/row/column/value claims.
