# Gold Policy Decision Draft v1

- Status: `PASS`
- Generated at: `2026-05-12T03:18:27.044888+00:00`
- Source resolution packet: `ai-worker/eval/review/rag_gold_policy_resolution_packet_v1.json`
- Scope: decision draft only; no official denominator membership is frozen.
- Guardrails: no retrieval variants, no production namespace mutation, no denominator registry change.

## Counts

- XLSX processed: `25`; draft decisions: `{"INCLUDE_AS_GOLD_V0_1_CANDIDATE": 23, "KEEP_PENDING_EVIDENCE": 2}`
- PDF processed: `9`; draft decisions: `{"EXCLUDE_FROM_GOLD_V0_1": 6, "KEEP_PENDING_FILE_IDENTITY_REVIEW": 3}`
- TEXT/Namu carried forward unresolved: `23`

## XLSX Draft Decisions

| query_id | proposed_user_decision | final_denominator_status | citation target |
|---|---|---|---|
| gq_xlsx_lookup_001 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A2:D51` |
| gq_xlsx_lookup_004 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A602:D602` |
| gq_xlsx_lookup_005 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A102:D151` |
| gq_xlsx_lookup_006 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A302:D351` |
| gq_xlsx_lookup_007 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `일반현황 A2:J51` |
| gq_xlsx_lookup_008 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `일반현황 A5002:J5051` |
| gq_xlsx_date_number_format_001 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `일반현황 A2:J51` |
| gq_xlsx_date_number_format_003 | `KEEP_PENDING_EVIDENCE` | `UNRESOLVED` | `철도 A452:D501` |
| gq_xlsx_aggregation_001 | `KEEP_PENDING_EVIDENCE` | `UNRESOLVED` | `USER_REQUIRED USER_REQUIRED` |
| gq_xlsx_aggregation_002 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A2:D51` |
| gq_auto_012 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A352:D401` |
| gq_auto_017 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A602:D602` |
| gq_auto_018 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `일반현황 A702:J751` |
| gq_auto_022 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A452:D501` |
| gq_auto_023 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `일반현황 A752:J801` |
| gq_auto_028 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `일반현황 A802:J851` |
| gq_auto_031 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A402:D451` |
| gq_auto_034 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A552:D601` |
| gq_auto_035 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A52:D101` |
| gq_auto_036 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A102:D151` |
| gq_auto_037 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A152:D201` |
| gq_auto_038 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A202:D251` |
| gq_auto_040 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `철도 A302:D351` |
| gq_auto_043 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `일반현황 A1052:J1101` |
| gq_auto_044 | `INCLUDE_AS_GOLD_V0_1_CANDIDATE` | `NOT_FROZEN` | `일반현황 A1102:J1151` |

## PDF Draft Decisions

| query_id | proposed_user_decision | final_denominator_status | appears_to_be | stable_identity |
|---|---|---|---|---|
| pdf_file_lookup_content_anchor_004 | `EXCLUDE_FROM_GOLD_V0_1` | `EXCLUDED_DRAFT` | `policy_excluded_not_answerable` | `True` |
| pdf_file_lookup_content_anchor_012 | `EXCLUDE_FROM_GOLD_V0_1` | `EXCLUDED_DRAFT` | `policy_excluded_not_answerable` | `False` |
| pdf_file_lookup_content_anchor_013 | `EXCLUDE_FROM_GOLD_V0_1` | `EXCLUDED_DRAFT` | `policy_excluded_not_answerable` | `False` |
| pdf_file_lookup_content_anchor_014 | `EXCLUDE_FROM_GOLD_V0_1` | `EXCLUDED_DRAFT` | `policy_excluded_not_answerable` | `False` |
| pdf_file_lookup_content_anchor_015 | `EXCLUDE_FROM_GOLD_V0_1` | `EXCLUDED_DRAFT` | `policy_excluded_not_answerable` | `False` |
| pdf_file_lookup_content_anchor_017 | `KEEP_PENDING_FILE_IDENTITY_REVIEW` | `UNRESOLVED` | `file_document_identity_lookup_candidate` | `False` |
| pdf_file_lookup_content_anchor_018 | `KEEP_PENDING_FILE_IDENTITY_REVIEW` | `UNRESOLVED` | `file_document_identity_lookup_candidate` | `False` |
| pdf_file_lookup_content_anchor_020 | `KEEP_PENDING_FILE_IDENTITY_REVIEW` | `UNRESOLVED` | `file_document_identity_lookup_candidate` | `False` |
| pdf_file_lookup_metadata_002 | `EXCLUDE_FROM_GOLD_V0_1` | `EXCLUDED_DRAFT` | `policy_excluded_not_answerable` | `True` |

## TEXT/Namu Carry-Forward

- Unresolved rows: `23`
- Resolution attempted: `false`
- expected_answer_or_evidence_revisions: `3`
- second_review: `3`
- invalid_or_ambiguous_query: `12`
- evidence_too_broad: `1`
- source_binding_review_required: `7`

## Remaining User Decisions

- XLSX include-confirmation draft rows: `23`
- XLSX pending evidence rows: `gq_xlsx_date_number_format_003, gq_xlsx_aggregation_001`
- PDF exclusion-confirmation draft rows: `6`
- PDF pending file-identity rows: `pdf_file_lookup_content_anchor_017, pdf_file_lookup_content_anchor_018, pdf_file_lookup_content_anchor_020`
- TEXT/Namu unresolved rows: `23`

## Guardrails

- official_denominator_registry.json changed: `False`
- retrieval variants ran: `False`
- production namespace mutated: `False`
- diagnostic-only row promoted: `False`
- PDF content/file identity lanes aggregated: `False`
