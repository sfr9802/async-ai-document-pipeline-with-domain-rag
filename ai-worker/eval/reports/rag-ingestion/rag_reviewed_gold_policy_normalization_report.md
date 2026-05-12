# Reviewed Gold Policy Normalization Report

- Status: `PASS`
- Generated at: `2026-05-11T03:25:34.744497+00:00`
- Scope: CSV schema/count validation and conservative policy normalization only.
- Guardrail: no production namespace, retrieval variant, or official denominator mutation.

## Imported Files
- `text_namu_v2`: `ai-worker/eval/review/text_namu_v2_gold_review/text_namu_v2_gold_review_pack - text_namu_v2_gold_review_pack.csv` (`100` rows, sha256 `5a2407089a5c5c22cf8f0101b76bba23a8c991fe7d2fa3f7fb89e395b56e4d0a`)
- `xlsx_human_review`: `ai-worker/eval/review/xlsx/제목 없는 스프레드시트 - xlsx_gold_human_review_pack (1).csv` (`50` rows, sha256 `66c883037214dd0679f6e5e05011b1189a71b23c820c0e655accc494e6747073`)
- `pdf_file_lookup_companion`: `ai-worker/eval/review/pdf_supplemental_gold_review/pdf_gold_review_pack_manual_v1_file_lookup_companion - pdf_gold_review_pack_manual_v1_file_lookup_companion.csv` (`28` rows, sha256 `c77f8b431c2cef5dffac5a968606c309eb653ec506efeb7ad37190c45f8b2b9a`)

## Normalized Counts

| Track | Proposed content/evidence candidates | File identity candidates | Frozen official denominator | Diagnostic-only | Source verification / binding | Evidence mismatch | Policy excluded | Revision / second review |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TEXT/Namu | `66` | `0` | `0` | `10` | `7` | `0` | `8` | `6` |
| XLSX | `25` | `0` | `0` | `1` | `10` | `7` | `7` | `0` |
| PDF content/file lanes | `14` | `5` | `0` | `0` | `0` | `0` | `6` | `9` |

## PDF Lane Split

- Content evidence positives: `14`
- File lookup / document identity candidates: `5`
- These lanes are not mixed for scoring.

## Rows Still Requiring User Gold-Policy Judgment

- TEXT/Namu: `23`
- XLSX: `35` (`25` candidate-inclusion confirmations, `10` source-verification rows)
- PDF: `9`

## Guardrails

- Official denominator registry changed: `False`
- Official denominator opened: `False`
- Diagnostic-only row promoted: `False`
- Retrieval variants run: `False`
