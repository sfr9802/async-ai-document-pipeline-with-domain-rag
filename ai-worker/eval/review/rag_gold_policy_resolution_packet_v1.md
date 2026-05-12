# Gold Policy Resolution Packet v1

- Status: `PASS`
- Generated at: `2026-05-12T01:54:29.739056+00:00`
- Source normalization report: `ai-worker/eval/reports/rag-ingestion/rag_reviewed_gold_policy_normalization_report.json`
- Scope: XLSX denominator confirmations and PDF expected-evidence revisions only.
- TEXT/Namu unresolved rows are carried forward unchanged.
- No retrieval variants, production namespace mutation, or denominator registry edits were performed.

## Counts

- XLSX processed: `25`; decisions: `{"CONFIRM_INCLUDE_OFFICIAL_CANDIDATE": 23, "KEEP_PENDING_EVIDENCE": 2}`
- PDF processed: `9`; decisions: `{"EXCLUDE_POLICY_OR_NOT_ANSWERABLE": 6, "KEEP_PENDING_USER_REVIEW": 3}`
- TEXT carried forward unresolved: `23`

## XLSX Decisions

| query_id | recommendation | answer source | citation target |
|---|---|---|---|
| gq_xlsx_lookup_001 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A2:D51` |
| gq_xlsx_lookup_004 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A602:D602` |
| gq_xlsx_lookup_005 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A102:D151` |
| gq_xlsx_lookup_006 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A302:D351` |
| gq_xlsx_lookup_007 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `일반현황 A2:J51` |
| gq_xlsx_lookup_008 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `일반현황 A5002:J5051` |
| gq_xlsx_date_number_format_001 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `일반현황 A2:J51` |
| gq_xlsx_date_number_format_003 | `KEEP_PENDING_EVIDENCE` | `expected_answer_text_existing` | `철도 A452:D501` |
| gq_xlsx_aggregation_001 | `KEEP_PENDING_EVIDENCE` | `USER_REQUIRED` | `USER_REQUIRED USER_REQUIRED` |
| gq_xlsx_aggregation_002 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `deterministic_compiled_answer` | `철도 A2:D51` |
| gq_auto_012 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A352:D401` |
| gq_auto_017 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A602:D602` |
| gq_auto_018 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `일반현황 A702:J751` |
| gq_auto_022 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A452:D501` |
| gq_auto_023 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `일반현황 A752:J801` |
| gq_auto_028 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `일반현황 A802:J851` |
| gq_auto_031 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A402:D451` |
| gq_auto_034 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A552:D601` |
| gq_auto_035 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A52:D101` |
| gq_auto_036 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A102:D151` |
| gq_auto_037 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A152:D201` |
| gq_auto_038 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A202:D251` |
| gq_auto_040 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `철도 A302:D351` |
| gq_auto_043 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `일반현황 A1052:J1101` |
| gq_auto_044 | `CONFIRM_INCLUDE_OFFICIAL_CANDIDATE` | `expected_answer_text_existing` | `일반현황 A1102:J1151` |

## PDF Decisions

| query_id | proposed policy | appears to be | stable identity |
|---|---|---|---|
| pdf_file_lookup_content_anchor_004 | `EXCLUDE_POLICY_OR_NOT_ANSWERABLE` | `policy_excluded_not_answerable` | `True` |
| pdf_file_lookup_content_anchor_012 | `EXCLUDE_POLICY_OR_NOT_ANSWERABLE` | `policy_excluded_not_answerable` | `False` |
| pdf_file_lookup_content_anchor_013 | `EXCLUDE_POLICY_OR_NOT_ANSWERABLE` | `policy_excluded_not_answerable` | `False` |
| pdf_file_lookup_content_anchor_014 | `EXCLUDE_POLICY_OR_NOT_ANSWERABLE` | `policy_excluded_not_answerable` | `False` |
| pdf_file_lookup_content_anchor_015 | `EXCLUDE_POLICY_OR_NOT_ANSWERABLE` | `policy_excluded_not_answerable` | `False` |
| pdf_file_lookup_content_anchor_017 | `KEEP_PENDING_USER_REVIEW` | `file_document_identity_lookup_candidate` | `False` |
| pdf_file_lookup_content_anchor_018 | `KEEP_PENDING_USER_REVIEW` | `file_document_identity_lookup_candidate` | `False` |
| pdf_file_lookup_content_anchor_020 | `KEEP_PENDING_USER_REVIEW` | `file_document_identity_lookup_candidate` | `False` |
| pdf_file_lookup_metadata_002 | `EXCLUDE_POLICY_OR_NOT_ANSWERABLE` | `policy_excluded_not_answerable` | `True` |

## Guardrails

- Official denominator registry changed: `False`
- Retrieval variants run: `False`
- Production namespace mutated: `False`
- PDF content/file identity aggregated: `False`
- Diagnostic-only row promoted: `False`
