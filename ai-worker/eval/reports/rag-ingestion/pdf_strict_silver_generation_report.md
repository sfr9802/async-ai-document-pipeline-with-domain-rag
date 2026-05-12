# PDF Strict Silver Generation Report

Status: `COMPLETED_DIAGNOSTIC_ONLY`

Scope: PDF retrieval/evidence diagnostic silver only. Answer generation, route/fallback official metrics, and production promotion remain closed.

## Counts

| Item | Count |
|---|---:|
| Input denominator rows | `7` |
| Generated strict silver rows | `0` |
| Policy-excluded rows | `6` |
| Stable-identity-required rows excluded | `3` |
| Pending/deferred OCR or parsing rows | `2` |
| Diagnostic-only fallback rows | `7` |
| PDF answer-generation denominator | `0` |

## Retrieval/Evidence Metrics

| Metric | Value |
|---|---:|
| page_hit | `None` |
| region_hit | `None` |
| bbox_available | `0.571` |
| table_or_caption_included | `0.0` |
| nearby_paragraph_included | `0.0` |
| OCR_confidence_available | `0.0` |
| citation_locator_completeness | `0.0` |
| metadata_key_presence_completeness | `1.0` |
| metadata_nonempty_value_completeness | `0.473` |

## Lane Separation

- Status: `PASS`
- Content evidence lane: `pdf_content_evidence`
- File identity lane: `pdf_file_identity`
- Aggregated: `false`

## Artifact Decision

- Repo full manifest written: `false`
- External manifest: `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\pdf_strict_silver_generation\pdf_strict_silver_retrieval_evidence_manifest.jsonl`
- Decision: no canonical PDF strict silver manifest path exists in the repo, so the full manifest is external-only and this report stays compact.

## Guardrails

| Guardrail | Value |
|---|---:|
| official_denominator_registry_changed | `false` |
| official_denominator_opened_or_frozen | `false` |
| promotion_evidence_created | `false` |
| pdf_answer_generation_denominator_opened | `false` |
| production_namespace_mutated | `false` |
| production_vector_index_mutated | `false` |
| production_vector_written | `false` |
| repo_local_pdf_silver_manifest_written | `false` |
| candidate_artifact_mutated | `false` |
| immutable_baseline_mutated | `false` |
| diagnostic_only_row_promoted | `false` |
| policy_excluded_rows_counted_as_retrieval_failures | `false` |
| route_fallback_labels_promoted_to_official_metrics | `false` |
| pdf_content_file_lanes_aggregated | `false` |

## Validation

- OK: `true`
- Errors: `0`

Answer/citation generation surfaces remain `NOT_OPENED`.
