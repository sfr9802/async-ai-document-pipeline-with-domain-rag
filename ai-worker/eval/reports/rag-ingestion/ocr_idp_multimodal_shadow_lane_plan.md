# OCR/IDP/Multimodal Shadow Lane Plan

## Status

- Status: `diagnostic_shadow_lane_plan`.
- Official denominator registry changed: `false`.
- Production index mutation: `not_allowed`.
- Broad indexing: `not_allowed`.
- Promotion evidence: `false`.

## Lane Boundaries

| Lane | Role | Denominator policy |
|---|---|---|
| TEXT | Native text content retrieval | Keep separate from XLSX/PDF/OCR/IDP/multimodal lanes. |
| XLSX | Structured spreadsheet retrieval | Use only approved strict wrapper artifacts. |
| PDF CONTENT | Native PDF text/content retrieval | Native PDF text is higher trust than OCR fallback. |
| PDF FILE lookup | File/document identity lookup only | Do not claim page, bbox, table, row, column, or value success. |
| OCR shadow | OCR fallback diagnostic SearchUnits | Diagnostic-only until explicit promotion policy exists. |
| IDP shadow | Table/key-value ExtractionUnits | Diagnostic-only; no official row/column/value success claim. |
| Multimodal shadow | Caption/figure diagnostic units | Retrieval expansion or triage only; not official evidence. |

## Trust Tiers

- `NATIVE_TEXT_HIGH`: native PDF/TEXT parser evidence with stable location metadata.
- `STRUCTURED_XLSX_HIGH`: strict XLSX wrapper evidence with hidden-safe policy and location metadata.
- `OCR_MEDIUM`: OCR fallback text, lower trust than native text.
- `IDP_TABLE_MEDIUM`: extracted table/key-value structure, diagnostic until reviewed.
- `MULTIMODAL_CAPTION_LOW`: generated or heuristic caption text, expansion-only by default.
- `DIAGNOSTIC_ONLY`: non-promotable evidence used for reports and risk discovery.

## OCR Shadow SearchUnit Contract

OCR shadow rows may be converted to SearchUnit-shaped diagnostic payloads only when all contract fields exist:

- `parser_version`
- `location_json`
- `citation_text`
- `embedding_text`
- `bm25_text`
- `display_text`
- `debug_text`

Required OCR provenance fields:

- `source_file_id`
- `source_file_name`
- `page_no` or `physical_page_index`
- `ocr_engine`
- `ocr_engine_version`
- `ocr_dpi`
- `ocr_language`
- `ocr_confidence`
- `native_text_conflict`
- `fallback_reason`

Policy:

- OCR fallback is lower trust than native PDF text.
- If native text and OCR both exist for the same page/region, native text wins retrieval/citation precedence.
- OCR rows are diagnostic by default and cannot enter official denominators without an explicit policy change and tests.

## IDP ExtractionUnit Contract

IDP output starts as an `ExtractionUnit`, not an official SearchUnit denominator row.

Key-value unit fields:

- `unit_id`
- `lane=IDP_SHADOW`
- `trust_tier=IDP_TABLE_MEDIUM`
- `key_text`
- `value_text`
- `confidence`
- `location_json`
- `citation_text`
- `parser_version`

Table unit fields:

- `table_id`
- `row_index`
- `column_index`
- `row_label`
- `column_label`
- `cell_value`
- `confidence`
- `location_json`
- `citation_text`
- `parser_version`

Policy:

- IDP table/key-value rows remain diagnostic until human review and denominator policy explicitly approve them.
- Reports may say "IDP extracted candidate row/cell/value", but must not claim official row/column/value success.
- `citation_text` must describe the extraction scope, not pretend that generated structure is native PDF text.

## Multimodal Caption Contract

Caption/figure units are diagnostic evidence by default.

Required fields:

- `unit_id`
- `lane=MULTIMODAL_SHADOW`
- `trust_tier=MULTIMODAL_CAPTION_LOW`
- `caption_text`
- `caption_source`
- `confidence`
- `location_json`
- `citation_text`
- `embedding_text`
- `bm25_text`
- `debug_text`

Policy:

- Captions may be used for retrieval expansion, triage, or query reformulation diagnostics.
- Captions must not be used as official gold evidence.
- Hallucination risk must be tracked by confidence bucket and source type.

## Native Text vs OCR Conflict Policy

1. If native PDF text has usable text and location metadata, use `NATIVE_TEXT_HIGH`.
2. If OCR exists for the same page or bbox, store it as `OCR_MEDIUM` diagnostic fallback.
3. If native text and OCR disagree, do not merge them silently.
4. Reports must record `native_text_conflict=true` and cite both provenance records.
5. Promotion requires a case-level review before OCR can override native text.

## Confidence Buckets

| Bucket | Range | Default action |
|---|---:|---|
| `HIGH` | `>= 0.90` | Diagnostic candidate; still not official by default. |
| `MEDIUM` | `>= 0.70 and < 0.90` | Diagnostic review queue. |
| `LOW` | `< 0.70` | Do not use for retrieval expansion unless explicitly requested. |
| `UNKNOWN` | missing confidence | Diagnostic-only and blocked from promotion. |

## Diagnostic-Only Denominator Policy

- OCR shadow, IDP shadow, and multimodal shadow rows have denominator role `DIAGNOSTIC_ONLY`.
- They are excluded from official denominators unless an explicit policy names the lane, trust tier, review status, and promotion gate.
- Official denominator counts for TEXT, XLSX, PDF CONTENT, and PDF FILE lookup remain unchanged.
- PDF FILE lookup remains file identity only even when OCR/IDP/caption evidence exists nearby.

## Promotion Gates

Before any shadow lane can be promoted:

- Contract fields are complete for every promoted row.
- Hidden content and source leakage checks pass.
- Native text vs OCR conflicts are reviewed case-by-case.
- OCR/IDP/multimodal confidence buckets are reported.
- Official denominator registry change is explicit and reviewed.
- Tests prove diagnostic rows cannot enter official denominators by default.
- Tests prove native PDF text outranks OCR fallback.
- Tests prove multimodal captions are diagnostic-only by default.

## Current Minimal Scaffolding

- `ai-worker/app/capabilities/rag/shadow_lane_contract.py` defines `ExtractionUnit`, trust tiers, diagnostic SearchUnit conversion, and fail-closed denominator checks.
- `ai-worker/tests/test_shadow_lane_contract.py` verifies OCR/IDP/multimodal rows are diagnostic-only, native text outranks OCR fallback, and caption units keep contract fields without becoming official evidence.
