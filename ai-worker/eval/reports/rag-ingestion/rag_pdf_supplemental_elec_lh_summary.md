# Supplemental elec/lh PDF Diagnostic Summary

This report is diagnostic-only. It does not expand Track C official gold, change the denominator, apply C7 policy decisions, create promotion evidence, or run answer generation.

## Dataset

- PDF count: `40`
- elec/lh source counts: `{"elec": 27, "lh": 13}`
- OCR-needed candidates: `10`
- Table-centered candidates: `29`

## Parser Coverage

- Parse success: `40`
- Parse failure: `0`
- Total pages: `778`
- Total blocks: `23573`
- Table-like block candidates: `1919`

## Synthetic Anchors

- Synthetic diagnostic anchors: `150`
- Anchor type counts: `{"paragraph_candidate": 8, "section_title_candidate": 23, "semantic_anchor_candidate": 17, "table_like_block": 102}`

## PageIndex

- Live PageIndex run: `False`
- Tree build success count: `0`
- Navigation success count: `0`
- Oracle navigation missed count: `0`
- Invalid range generated count: `0`

## Answer Evidence

- Evidence objects: `150`
- Answer allowed count: `150`
- Locator-only object count: `0`
- Answer evidence ready rate: `1.0`

## Track C Relationship

- Existing Track C PDF C7 policy-pending rows remain unresolved and user-owned.
- elec/lh synthetic anchors are not official Track C denominator rows.
- PageIndex remains a PDF page/section navigator candidate only.
- bbox, table, value semantics, C7 resolution, promotion readiness, and actual answer quality are not claimed.

## Next Steps

- Manually review anchor rows before any future gold inclusion/exclusion decision.
- Use parser and answer-evidence gaps to decide whether OCR fallback or table-context extraction deserves a separate scoped task.
- Run local PageIndex only with explicit local model and localhost base URL when navigation evidence is needed.
