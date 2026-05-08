# PDF FILE Lookup Rank Error Analysis

- Status: `PASS`.
- Profile: `baseline_pdf_file_identity_tokens`.
- Semantics: `file_identity_only`.
- Content/page/bbox/table/row/column/value success claimed: `false`.

## Summary

- Gold positive rows: `15`.
- Diagnostic rows: `4`.
- Expected file in top 10 but not top 3: `6`.
- Generic filename confusions: `3`.
- Similar filename confusions: `7`.
- Document-version-id confusions: `0`.

## Top 10 But Not Top 3

| split | query_id | expected_file | rank | top1 |
|---|---|---|---:|---|
| `gold_positive` | `pdf_file_lookup_content_anchor_005` | `2024년도+1월+1일+시행+전기요금표(종합)_출력용.pdf` | 8.0000 | `20210101(low).pdf` |
| `gold_positive` | `pdf_file_lookup_content_anchor_009` | `20220401(law).pdf` | 4.0000 | `2023년도+11월+9일+시행+전기요금표(주택용저압)_출력용.pdf` |
| `gold_positive` | `pdf_file_lookup_content_anchor_010` | `2024년도+1월+1일+시행+전기요금표(주택용저압)_출력용.pdf` | 4.0000 | `20210101(low).pdf` |
| `gold_positive` | `pdf_file_lookup_metadata_001` | `20210101(low).pdf` | 4.0000 | `2024년도+1월+1일+시행+전기요금표(주택용저압)_출력용.pdf` |
| `gold_positive` | `pdf_file_lookup_metadata_003` | `20220401(high).pdf` | 5.0000 | `2024년도+4월+1일+시행+전기요금표(종합)_출력용.pdf` |
| `gold_positive` | `pdf_file_lookup_metadata_004` | `20220401(law).pdf` | 5.0000 | `2024년도+4월+1일+시행+전기요금표(종합)_출력용.pdf` |

## Generic Filename Confusions

| split | query_id | expected_file | rank | top1 |
|---|---|---|---:|---|
| `diagnostic` | `pdf_file_lookup_content_anchor_011` | `file.pdf` |  | `20210101(low).pdf` |
| `diagnostic` | `pdf_file_lookup_content_anchor_019` | `file (3).pdf` |  | `20210101(low).pdf` |
| `diagnostic` | `pdf_file_lookup_content_anchor_021` | `file (5).pdf` |  | `20210101(low).pdf` |

## Recommended Hard Negatives

- Add same-year and same-month files from a different family as hard negatives.
- Add same family with adjacent month or adjacent effective-date files as hard negatives.
- Add generic filename families such as file.pdf, file (3).pdf, and file (10).pdf as identity-confusion negatives.
- When document_version_id is populated, add same filename with mismatched document_version_id as a separate identity negative.
- Keep content-anchor text only as query provenance; success remains expected file identity.
