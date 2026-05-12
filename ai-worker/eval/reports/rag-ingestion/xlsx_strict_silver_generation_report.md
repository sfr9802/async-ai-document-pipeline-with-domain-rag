# XLSX Strict Silver Generation Report

Status: `COMPLETED_DIAGNOSTIC_ONLY`

Scope: XLSX retrieval/evidence silver generation only. Answer-generation and production promotion remain closed.

## Counts

| Item | Count |
|---|---:|
| Input denominator rows | `23` |
| Generated silver rows | `23` |
| Excluded normalized rows | `27` |
| Pending evidence rows excluded | `2` |
| Normalized hidden-negative rows excluded | `3` |
| Diagnostic-only fallback rows | `0` |

## Retrieval/Evidence Metrics

| Metric | Value |
|---|---:|
| Hit@10 | `1.0` |
| MRR@10 | `0.942` |
| XLSX citation location accuracy | `1.0` |
| target_cell_hit | `1.0` |
| target_row_hit | `1.0` |
| header_included | `1.0` |
| target_column_included | `1.0` |
| surrounding_context_included | `1.0` |
| sheet_resolution_accuracy | `1.0` |
| citation locator completeness | `1.0` |

## Hidden/Excluded Leakage

- Status: `PASS`
- Probe target rows: `16`
- Surface leakage count: `0`
- Policy-excluded rows counted as retrieval failures: `false`
- Answer surface: `NOT_OPENED`
- Citation surface: `NOT_OPENED`

## Artifact Decision

- Repo silver artifact written: `false`
- External silver artifact: `D:\_external_runtime_artifacts\async-ocr-rag-multimodal-pipeline\rag-ingestion\xlsx_strict_silver_generation\xlsx_strict_silver_retrieval_evidence_manifest.jsonl`
- Decision: no canonical XLSX strict silver artifact path exists in the repo, so the full manifest is outside the repo and this report stays compact.

## Guardrails

| Guardrail | Value |
|---|---:|
| official_denominator_registry_changed | `false` |
| official_denominator_opened_or_frozen | `false` |
| xlsx_answer_generation_denominator_opened | `false` |
| production_namespace_mutated | `false` |
| production_vector_index_mutated | `false` |
| production_vector_written | `false` |
| repo_local_silver_manifest_written | `false` |
| candidate_artifact_mutated | `false` |
| immutable_baseline_mutated | `false` |
| diagnostic_only_row_promoted | `false` |
| hidden_xlsx_exposed | `false` |
| policy_excluded_rows_counted_as_retrieval_failures | `false` |
| route_fallback_labels_promoted_to_official_metrics | `false` |
| pdf_content_file_lanes_aggregated | `false` |

## Validation

- OK: `true`
- No guardrail errors.
