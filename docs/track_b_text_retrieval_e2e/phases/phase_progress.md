# Track B R-Phase Progress Log

This file records execution progress for Track B R0-R9 phase files under `docs/track_b_text_retrieval_e2e/phases/`.
It follows the dated-entry structure used by `docs/rag-ingestion-progress.md` so durable entries can be merged back without rewriting the narrative.

## Merge Policy

- Keep this log phase-local until Track B reaches a stable checkpoint.
- Merge durable entries into `docs/rag-ingestion-progress.md` after R-phase evidence is complete or intentionally paused.
- Keep `B-app` smoke evidence separate from the `B-namu` mainline.
- Keep every Track B report diagnostic-only unless a later task explicitly opens promotion work.

## R-Phase Status Board

| Phase | Status | Current Evidence | Next Action |
|---|---|---|---|
| R0 B2 scope correction | `diagnostic_completed` | `reports/rag_text_b2_scope_correction_report.json` | Use correction report when citing legacy B2-app metrics |
| R1 query routing matrix | `needs_review` | `eval/query_intent_routing_matrix_v0.csv`, `reports/rag_query_intent_routing_matrix_report.json` | Future namu gold is present, but current routing matrix still excludes future inputs from observed lane coverage |
| R2 namu-v4 corpus inventory | `diagnostic_completed` | `reports/rag_text_namu_v4_corpus_inventory_report.json` schema v2 hardened PASS with split-count check | Use `rag_chunks.jsonl` + `chunk_text`; keep auxiliary/split/raw-context checks as R3-R8 gate |
| R3 namu-v4 gold binding | `diagnostic_completed` | `eval/gold_queries_text_namu_v4_v0.csv`, `reports/rag_text_namu_v4_gold_build_report.json`, `reports/rag_text_namu_v4_gold_validate_report.json`; validator current-seed policy PASSED | R4 completed; keep as R5 entry gate |
| R4 retrieval emit inventory | `diagnostic_completed` | `reports/rag_text_namu_v4_retrieval_emit_inventory_report.json` says `NO_REUSABLE_EXISTING_EMIT` | R5 must generate a fresh diagnostic retrieval emit |
| R5 B2-namu retrieval diagnostic | `ready_for_fresh_diagnostic` | R4 decision `RUN_FRESH_DIAGNOSTIC_RETRIEVAL`, `retrieval_metrics_computed=false` | Generate true namu-v4 retrieval-only metrics with fresh emit |
| R6 B3-namu context assembly | `blocked_on_R5` | `phase_r6_b3_namu_context_assembly.md` | Assemble raw `chunk_text` contexts |
| R7 B4-namu answer eval | `blocked_on_R6` | `phase_r7_b4_namu_answer_eval.md` | Evaluate answers after context report exists |
| R8 B5-namu citation support | `blocked_on_R7` | `phase_r8_b5_namu_citation_support.md` | Validate claim-level citation support |
| R9 file/content lane readiness | `planned` | `phase_r9_file_content_lane_readiness.md` | Generate FILE vs CONTENT readiness report |

## Status Vocabulary

| Status | Meaning |
|---|---|
| `planned` | Plan exists, but implementation or evidence gathering has not started |
| `in_progress` | Current active phase |
| `blocked_on_Rx` | Waiting for a prior R-phase artifact |
| `blocked_on_Bx` | Waiting for a prior B-phase artifact |
| `diagnostic_completed` | Diagnostic artifact exists; promotion evidence was not produced |
| `ready_for_fresh_diagnostic` | Prior inventory is complete, but the next phase must generate fresh diagnostic output |
| `smoke_only` | Valid smoke evidence, not representative mainline performance |
| `needs_review` | Output exists but needs manual or contract review |
| `merged_to_main_progress` | Durable entry has been copied into `docs/rag-ingestion-progress.md` |

## 2026-05-05 - Track B R0 B2 Scope Correction Completed

### Goal

- Start R0 from `phase_r0_b2_scope_correction.md`.
- Reclassify the legacy B2 diagnostic as `B-app app-catalog TEXT canary smoke`.
- Preserve the existing B2 metrics while preventing the 0-score result from being cited as `B-namu`, namu-v4, or production-style TEXT retrieval evidence.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| B2-app retrieval diagnostic | `diagnostic_completed / smoke_only` | `diagnostic_completed / smoke_only` | `reports/rag_text_retrieval_diagnostic_report.json` preserved |
| R0 B2 scope correction | `planned` | `diagnostic_completed` | `reports/rag_text_b2_scope_correction_report.json` |
| R1 query routing matrix | `planned` | `planned` | `phase_r1_query_intent_routing_matrix.md` |
| R2 namu-v4 corpus inventory | `planned` | `planned` | `phase_r2_namu_v4_corpus_inventory.md` |
| R3-R8 B-namu mainline | `planned/blocked` | `blocked_on_R2/R3/R4/R5/R6/R7` | Do not proceed from B2-app smoke |
| R9 file/content lane readiness | `planned` | `planned` | `phase_r9_file_content_lane_readiness.md` |

### Completed

- Added the R0 scope-correction report:
  - `reports/rag_text_b2_scope_correction_report.json`
- Kept the legacy B2 report intact:
  - `reports/rag_text_retrieval_diagnostic_report.json`
- Recorded that the legacy B2 report is now interpreted as B-app smoke-only diagnostic evidence.

### Current Evidence

- R0 report:
  - `status=COMPLETED`
  - `scope_correction=true`
  - `new_b2_label=B-app app-catalog TEXT canary smoke`
  - `representative_of_namu_v4=false`
  - `representative_of_existing_text_retrieval=false`
  - `b2_namu_status=NOT_STARTED`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
- Preserved B2-app metrics:
  - `Hit@10=0.0`
  - `MRR@10=0.0`
  - `result_empty_count=12`
  - `path_mixing_count=0`
  - `search_error_count=0`

### Gate/Baseline Status

- No retrieval eval rerun was performed.
- No indexing, tuning, LLM run, candidate mutation, immutable baseline update, or `rag-data-canary` update was performed.
- The legacy B2-app report remains diagnostic-only and must not be used as promotion evidence.

### Verification

- Command:
  - `python -m json.tool reports\rag_text_b2_scope_correction_report.json > $null`
  - result: passed
- Command:
  - `python -B -c "import json, pathlib; r=json.loads(pathlib.Path('reports/rag_text_b2_scope_correction_report.json').read_text(encoding='utf-8')); assert r['status']=='COMPLETED'; assert r['scope_correction'] is True; assert r['new_b2_label']=='B-app app-catalog TEXT canary smoke'; assert r['representative_of_namu_v4'] is False; assert r['representative_of_existing_text_retrieval'] is False; assert r['b2_namu_status']=='NOT_STARTED'; assert r['promotion_evidence'] is False; assert r['evidence_role']=='diagnostic'; assert r['b2_app_report_modified_by_scope_correction'] is False; assert r['acceptance_criteria']['b3_b4_b5_follow_b2_namu_not_b2_app'] is True"`
  - result: passed
- Command:
  - `rg -n "[ \t]+$" docs\track_b_text_retrieval_e2e`
  - result: no trailing whitespace matches
- Command:
  - `git diff --check`
  - result: passed; existing CRLF conversion warnings were printed for modified files

### Important Decisions

- Do not overwrite the legacy B2 metric report just to change its meaning.
- Use `reports/rag_text_b2_scope_correction_report.json` as the authoritative scope correction.
- Keep B3/B4/B5 on the B-namu path, not the B2-app smoke path.

### Remaining Work

- Start R1 query intent routing matrix after R0 verification passes.

### Risks

- The legacy B2 report still has historical fields such as `phase=B2` and `smoke_only=false`; cite it with the R0 correction report to avoid misinterpretation.
- R2 must verify raw context fields before any R6 answer-context assembly.

### Next Recommended Step

- Verify R0 artifacts, then start R1 query intent routing matrix.

## 2026-05-05 - Track B R1 Query Intent Routing Matrix Generated

### Goal

- Execute R1 from `phase_r1_query_intent_routing_matrix.md`.
- Separate TEXT, XLSX, PDF, FILE lookup, CONTENT lookup, and UNKNOWN/MIXED query lanes before any later retrieval metric chooses a denominator.
- Keep B-app smoke rows, XLSX/PDF content diagnostics, and future B-namu rows visibly separate.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| R0 B2 scope correction | `diagnostic_completed` | `diagnostic_completed` | `reports/rag_text_b2_scope_correction_report.json` |
| R1 query routing matrix | `planned` | `needs_review` | `eval/query_intent_routing_matrix_v0.csv`, `reports/rag_query_intent_routing_matrix_report.json` |
| R2 namu-v4 corpus inventory | `planned` | `planned` | R1 shows `B_NAMU_TEXT_CONTENT=0`; future namu gold is not created yet |
| R3-R8 B-namu mainline | `blocked_on_R2/R3/R4/R5/R6/R7` | `blocked_on_R2/R3/R4/R5/R6/R7` | Do not proceed from B-app smoke rows |
| R9 file/content lane readiness | `planned` | `planned` | FILE lanes are explicit but current candidate inputs contain no file lookup rows |

### Completed

- Added R1 routing script:
  - `scripts/rag_query_intent_routing_matrix.py`
- Added focused unit/CLI coverage:
  - `ai-worker/tests/test_rag_query_intent_routing_matrix.py`
- Generated routing artifacts:
  - `eval/query_intent_routing_matrix_v0.csv`
  - `reports/rag_query_intent_routing_matrix_report.json`

### Current Evidence

- R1 report:
  - `status=NEEDS_REVIEW`
  - `row_count=204`
  - `blockers=[]`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
  - `unknown_count=0`
  - `mixed_file_content_count=0`
- Lane counts:
  - `APP_TEXT_SMOKE=12`
  - `XLSX_CONTENT=170`
  - `PDF_CONTENT=22`
  - `B_NAMU_TEXT_CONTENT=0`
  - `TEXT_FILE_LOOKUP=0`
  - `XLSX_FILE=0`
  - `PDF_FILE=0`
  - `UNKNOWN=0`
- Observed required lane coverage:
  - `B_NAMU_TEXT_CONTENT=false`
  - `XLSX_CONTENT=true`
  - `PDF_CONTENT=true`
  - `XLSX_FILE=false`
  - `PDF_FILE=false`
  - `UNKNOWN=false`
- Positive denominator policy:
  - `must_group_by=["retrieval_lane"]`
  - excludes `BLOCKED`, `NOT_READY`, `PLANNED`, and `SMOKE_ONLY` readiness rows
  - currently only `XLSX_CONTENT` appears in `eligible_denominator_groups_by_lane`
  - `eligible_denominator_groups_by_lane.XLSX_CONTENT.row_count=35`
- Denominator exclusion counts:
  - `source manifest is not the reviewed XLSX positive set=135`
  - `readiness_blocked_excluded=22`
  - `readiness_smoke_only_excluded=12`
- Readiness split:
  - `SMOKE_ONLY=12`
  - `DIAGNOSTIC_READY=170`
  - `BLOCKED=22`
  - `PLANNED=0`
  - `NOT_READY=0`

### Gate/Baseline Status

- No retrieval eval rerun was performed.
- No indexing, tuning, LLM run, candidate mutation, immutable baseline update, or `rag-data-canary` update was performed.
- The routing matrix is diagnostic-only denominator hygiene, not promotion evidence.

### Verification

- Command:
  - `python -m py_compile scripts\rag_query_intent_routing_matrix.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_query_intent_routing_matrix.py`
  - result: 9 passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_query_intent_routing_matrix.py ai-worker\tests\test_rag_text_e2e_gold_validator.py ai-worker\tests\test_rag_text_backend_identity.py ai-worker\tests\test_rag_text_retrieval_diagnostic.py`
  - result: 28 passed
- Command:
  - `python scripts\rag_query_intent_routing_matrix.py`
  - result: wrote `204` routing rows with report `status=NEEDS_REVIEW` and no blockers
- Command:
  - `python -B -c "import csv,json,pathlib; report=json.loads(pathlib.Path('reports/rag_query_intent_routing_matrix_report.json').read_text(encoding='utf-8')); rows=list(csv.DictReader(pathlib.Path('eval/query_intent_routing_matrix_v0.csv').open(encoding='utf-8-sig', newline=''))); group=report['positive_denominator_policy']['eligible_denominator_groups_by_lane']['XLSX_CONTENT']; assert report['status']=='NEEDS_REVIEW'; assert report['blockers']==[]; assert report['promotion_evidence'] is False; assert report['evidence_role']=='diagnostic'; assert report['row_count']==len(rows)==204; assert report['lane_counts']['APP_TEXT_SMOKE']==12; assert report['lane_counts']['XLSX_CONTENT']==170; assert report['lane_counts']['PDF_CONTENT']==22; assert report['completion_criteria']['observed_required_lane_coverage_complete'] is False; assert report['positive_denominator_policy']['must_group_by']==['retrieval_lane']; assert 'PDF_CONTENT' in report['positive_denominator_policy']['exclude_retrieval_lanes']; assert group['row_count']==35; assert len(group['query_ids'])==35; assert report['denominator_exclusion_counts']['source manifest is not the reviewed XLSX positive set']==135"`
  - result: passed
- Command:
  - `rg -n "[ \t]+$" docs\track_b_text_retrieval_e2e scripts\rag_query_intent_routing_matrix.py ai-worker\tests\test_rag_query_intent_routing_matrix.py`
  - result: no trailing whitespace matches
- Command:
  - `git diff --check`
  - result: passed; existing CRLF conversion warnings were printed for modified files

### Important Decisions

- Treat `eval/gold_queries_text_e2e_v0.csv` as `APP_TEXT_SMOKE`, not `B_NAMU_TEXT_CONTENT`.
- Let row-level location metadata override weak file-like wording such as `찾아줘` when the row is clearly content-bound.
- Keep FILE lanes explicit even when current candidate inputs have zero FILE rows.
- Record missing `eval/gold_queries_text_namu_v4_v0.csv` as a future input, not an R1 failure, because R2/R3 have not produced it yet.
- Do not claim full observed lane coverage until B-namu/file/unknown rows are actually present or intentionally fixture-tested.

### Remaining Work

- Start R2 namu-v4 corpus inventory.
- Do not build B-namu gold or B2-namu retrieval metrics until R2 confirms corpus structure, hashes, and raw context fields.

### Risks

- Current candidate inputs contain no actual `B_NAMU_TEXT_CONTENT`, `XLSX_FILE`, `PDF_FILE`, or `UNKNOWN` rows, so R1 is `NEEDS_REVIEW` for observed lane coverage while still producing usable denominator policy.
- PDF content rows remain `BLOCKED` until Track C readiness is complete.

### Next Recommended Step

- Start R2 namu-v4 corpus inventory.

## 2026-05-05 - Track B R2 namu-v4 Corpus Inventory Completed

### Goal

- Retry the R1 incomplete observed-lane issue before moving forward.
- Execute R2 from `phase_r2_namu_v4_corpus_inventory.md`.
- Verify that `namu-v4-structured-combined` is structurally safe to use as the B-namu TEXT mainline corpus.
- Confirm the raw answer-context field before any R3-R8 work can build gold, retrieval emits, context, answers, or citation support.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| R1 query routing matrix | `needs_review` | `needs_review` | Retry regenerated `reports/rag_query_intent_routing_matrix_report.json`; current inputs still lack B-namu/file/unknown observed rows |
| R2 namu-v4 corpus inventory | `planned` | `diagnostic_completed` | `reports/rag_text_namu_v4_corpus_inventory_report.json` |
| R3 namu-v4 gold binding | `blocked_on_R2` | `planned` | R2 PASS unlocks gold binding work |
| R4 retrieval emit inventory | `blocked_on_R2_R3` | `blocked_on_R3` | R4 still waits for R3 gold |
| R5 B2-namu retrieval diagnostic | `blocked_on_R3_R4` | `blocked_on_R3_R4` | No namu-v4 retrieval metrics were run |

### Completed

- Added R2 corpus inventory script:
  - `scripts/rag_text_namu_v4_corpus_inventory.py`
- Added focused unit/CLI coverage:
  - `ai-worker/tests/test_rag_text_namu_v4_corpus_inventory.py`
- Generated R2 report:
  - `reports/rag_text_namu_v4_corpus_inventory_report.json`
- Re-ran R1 routing matrix before R2 and preserved `status=NEEDS_REVIEW` because actual candidate inputs still do not include B-namu/file/unknown observed rows.

### Current Evidence

- R2 report:
  - `status=PASS`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
  - `blockers=[]`
- File inventory:
  - `pages_v4.jsonl`: `row_count=4314`, `sha256=3acd4e8beba4c905ca21162b14689a3c351b8b6a8c20ee61a605e53208d4bdc9`
  - `chunks_v4.jsonl`: `row_count=48675`, `sha256=b170c9e9dfd9ae07b43ae67105c0ba64dc191bd6be6ac22952e080cbe3498492`
  - `rag_chunks.jsonl`: `row_count=135602`, `sha256=c9c18da61956de6494ca314908841ae7f2df78f313094767c2624d6bcd73cb9a`
- `rag_chunks.jsonl` schema evidence:
  - `chunk_id_unique=true`
  - `unique_chunk_id_count=135602`
  - `duplicate_chunk_id_count=0`
  - `raw_context_field=chunk_text`
  - `empty_chunk_text_count=0`
  - `page_identity_complete=true`
  - `page_identity_matches_pages_v4=true`
  - `page_identity_missing_from_pages_v4_count=0`
  - `missing_section_path_count=0`
  - `missing_title_count=0`
  - `missing_page_id_count=135602`
  - `missing_doc_id_count=0`
  - `unique_doc_id_count=4314`
  - `page_identifier_field=doc_id`
- `pages_v4.jsonl` identity evidence:
  - `page_id_unique=true`
  - `unique_page_id_count=4314`
  - `missing_page_id_count=0`
  - `duplicate_page_id_count=0`
- Context policy:
  - allowed context fields: `chunk_text`, `text`
  - selected context field: `chunk_text`
  - disallowed fields: `embedding_text`, `text_for_embedding`, `debug_text`
  - `embedding_text` is present on all `rag_chunks` rows but was not selected as answer context.

### Gate/Baseline Status

- No retrieval eval rerun was performed.
- No indexing, tuning, LLM run, candidate mutation, immutable baseline update, or `rag-data-canary` update was performed.
- R2 is diagnostic corpus inventory only.
- R3 is now unblocked, but R4/R5 remain blocked until R3 produces namu-v4 gold binding evidence.

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_namu_v4_corpus_inventory.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_namu_v4_corpus_inventory.py`
  - result: 11 passed
- Command:
  - `python scripts\rag_query_intent_routing_matrix.py`
  - result: R1 retry wrote `204` routing rows with report `status=NEEDS_REVIEW` and no blockers
- Command:
  - `python scripts\rag_text_namu_v4_corpus_inventory.py`
  - result: R2 report generated with `status=PASS`, `raw_context_field=chunk_text`, and `blocker_count=0`

### Important Decisions

- Use `rag_chunks.jsonl`, not `chunks_v4.jsonl`, as the production retrieval / answerability join fixture for the current B-namu path.
- Treat literal `page_id` absence in `rag_chunks.jsonl` as a recorded schema fact, not an R2 blocker, because `doc_id` is fully populated and every `doc_id` matches `pages_v4.page_id`.
- Keep `embedding_text` visible in the report as a disallowed field that exists, while binding answer context only to `chunk_text`.
- Do not force R1 to `COMPLETED`; it remains `NEEDS_REVIEW` until actual B-namu/file/unknown rows exist or are intentionally fixture-tested.

### Remaining Work

- Start R3 namu-v4 gold binding.
- Keep R4/R5 blocked until R3 produces gold binding evidence and R4 decides the retrieval emit source.

### Risks

- Any later context assembly that reads `embedding_text` instead of `chunk_text` would violate the R2 context policy.
- Later code that requires literal `page_id` from `rag_chunks.jsonl` must either map `doc_id` explicitly or join against a different artifact with proof.
- `chunks_v4.jsonl` has a different row count and should not be used as a silent substitute for current answerability joins.

### Next Recommended Step

- Start R3 namu-v4 gold binding using the R2 PASS report as the entry gate.

## 2026-05-05 - Track B R2 Hardened and R3 Gold Binding Completed

### Goal

- Revisit R2 before proceeding and harden it beyond basic file inventory.
- Execute R3 from `phase_r3_namu_v4_gold_binding.md`.
- Retry the R1 incomplete issue after R3 so future namu gold existence is visible without forcing R1 to completed.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| R1 query routing matrix | `needs_review` | `needs_review` | Retry now records `eval/gold_queries_text_namu_v4_v0.csv` as an existing future input with `row_count=50` |
| R2 namu-v4 corpus inventory | `diagnostic_completed` | `diagnostic_completed` | `reports/rag_text_namu_v4_corpus_inventory_report.json` schema v2 hardened PASS with split-count check |
| R3 namu-v4 gold binding | `planned` | `diagnostic_completed` | `eval/gold_queries_text_namu_v4_v0.csv`, build/validate reports |
| R4 retrieval emit inventory | `blocked_on_R3` | `planned` | R3 validator PASSED, so R4 can decide emit reuse/fresh retrieval |
| R5 B2-namu retrieval diagnostic | `blocked_on_R3_R4` | `blocked_on_R4` | Waits for R4 retrieval emit inventory |

### Completed

- Strengthened R2 inventory script and tests:
  - `scripts/rag_text_namu_v4_corpus_inventory.py`
  - `ai-worker/tests/test_rag_text_namu_v4_corpus_inventory.py`
- Added R3 gold builder/validator and tests:
  - `scripts/rag_text_namu_v4_gold_builder.py`
  - `scripts/rag_text_namu_v4_gold_validator.py`
  - `ai-worker/tests/test_rag_text_namu_v4_gold_validator.py`
- Generated R3 artifacts:
  - `eval/gold_queries_text_namu_v4_v0.csv`
  - `reports/rag_text_namu_v4_gold_build_report.json`
  - `reports/rag_text_namu_v4_gold_validate_report.json`
- Re-ran R1 after R3:
  - `reports/rag_query_intent_routing_matrix_report.json`

### Current Evidence

- R2 hardened report:
  - `status=PASS`
  - `schema_version=rag_text_namu_v4_corpus_inventory_v2`
  - `blockers=[]`
  - auxiliary validation/split files are present and parseable
  - R2 auxiliary validation counts match `pages_v4.jsonl` and `chunks_v4.jsonl`; R3 binding still uses `rag_chunks.jsonl`
  - split manifest doc ids match `pages_v4.page_id`
  - split manifest declared doc counts match split `doc_ids`, total, and `pages_v4` row count
  - split report has zero doc/group leakage
  - raw-context trust counters are clean
- R3 build report:
  - `status=COMPLETED`
  - `row_count=50`
  - `positive_row_count=47`
  - `needs_review_row_count=3`
  - `abstain_or_review_row_count=3`
  - `bucket_counts={"text_fact_lookup":31,"text_multi_chunk_summary":16,"text_policy_question":3}`
- R3 validator report:
  - `status=PASSED`
  - `missing_page_ids=[]`
  - `missing_chunk_ids=[]`
  - `missing_section_ids=[]`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
- R3 CSV policy:
  - all `50` rows have `allowed_abstain=false`
  - the `3` partially answerable/risk rows are `label_status=needs_review`, `bucket=text_policy_question`, `answer_type=claim_check`
  - no fabricated abstain rows were introduced
- R1 retry:
  - `status=NEEDS_REVIEW`
  - `future_inputs[0].exists=true`
  - `future_inputs[0].row_count=50`
  - observed lane coverage is still incomplete because future inputs are not promoted into current observed routing rows

### Gate/Baseline Status

- No retrieval eval, indexing, tuning, LLM run, candidate mutation, immutable baseline update, or `rag-data-canary` update was performed.
- R3 is corpus/gold binding evidence only; R4/R5 still need retrieval emit and metric diagnostics.

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_namu_v4_corpus_inventory.py scripts\rag_text_namu_v4_gold_builder.py scripts\rag_text_namu_v4_gold_validator.py scripts\rag_query_intent_routing_matrix.py scripts\rag_text_e2e_gold_validator.py scripts\rag_text_backend_identity.py scripts\rag_text_retrieval_diagnostic.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_namu_v4_corpus_inventory.py ai-worker\tests\test_rag_text_namu_v4_gold_validator.py ai-worker\tests\test_rag_query_intent_routing_matrix.py ai-worker\tests\test_rag_text_e2e_gold_validator.py ai-worker\tests\test_rag_text_backend_identity.py ai-worker\tests\test_rag_text_retrieval_diagnostic.py`
  - result: 53 passed
- Command:
  - `python scripts\rag_text_namu_v4_corpus_inventory.py`
  - result: R2 report `status=PASS`, `blocker_count=0`, `raw_context_field=chunk_text`
- Command:
  - `python scripts\rag_text_namu_v4_gold_builder.py`
  - result: R3 build report `status=COMPLETED`, `row_count=50`, `positive_row_count=47`, `needs_review_row_count=3`
- Command:
  - `python scripts\rag_text_namu_v4_gold_validator.py`
  - result: R3 validation report `status=PASSED`, `row_count=50`, `positive_row_count=47`, `needs_review_row_count=3`
- Command:
  - `python scripts\rag_query_intent_routing_matrix.py`
  - result: R1 retry report `status=NEEDS_REVIEW`, `row_count=204`, future namu input exists with `row_count=50`
- Command:
  - custom Python contract assertion over R2/R3/R1 reports
  - result: contract ok

### Important Decisions

- Keep `rag_chunks.jsonl` as the R3 binding source, not `chunks_v4.jsonl`.
- Derive `expected_section_ids` from `rag_chunks.section_id`, then validate them against both `rag_chunks` and `pages_v4.sections`.
- Copy `source_evidence` into `expected_answer_summary`; do not synthesize answer text.
- Treat current partially answerable rows as `needs_review` policy rows, not as fabricated abstain rows.

### Remaining Work

- Start R4 retrieval emit inventory.
- Keep B2-namu retrieval metrics blocked until R4 identifies a valid emit source or a fresh retrieval run path.

### Risks

- R1 still has incomplete observed lane coverage by design; R3 only provides a future namu gold input, not current matrix rows.
- R3 does not prove retrieval quality, ranking quality, answer generation, or citation support.

### Next Recommended Step

- Start R4 retrieval emit inventory.

## 2026-05-05 - R3 Rechecked and R4 Retrieval Emit Inventory Completed

### Goal

- Recheck R3 namu-v4 gold binding before moving to R4.
- Strengthen R3 validation so current seed policy and section-path mismatch blockers are explicit.
- Inventory existing retrieval emit artifacts without running retrieval metrics.

### Phase Status Update

| Phase | Previous | Current | Evidence |
|---|---|---|---|
| R3 namu-v4 gold binding | `diagnostic_completed` | `diagnostic_completed` | Validator re-run `PASSED`; current-seed policy criteria all true |
| R4 retrieval emit inventory | `planned` | `diagnostic_completed` | `reports/rag_text_namu_v4_retrieval_emit_inventory_report.json` |
| R5 B2-namu retrieval diagnostic | `blocked_on_R4` | `ready_for_fresh_diagnostic` | R4 decision is `RUN_FRESH_DIAGNOSTIC_RETRIEVAL` |

### Completed

- Added R3 validator checks for:
  - manual curated seed source path
  - expected `50` rows with `47` positive and `3` `needs_review`
  - `allowed_abstain=false` for all rows
  - `expected_section_path` in CSV notes matching `rag_chunks.section_path`
- Added R4 retrieval emit inventory script and focused tests.
- Generated `reports/rag_text_namu_v4_retrieval_emit_inventory_report.json`.

### Current Evidence

- R3 validate report:
  - `status=PASSED`
  - `row_count=50`
  - `positive_row_count=47`
  - `needs_review_row_count=3`
  - `allowed_abstain_true_count=0`
  - `fabricated_abstain_row_count=0`
  - `section_path_mismatch_count=0`
  - `source_dataset_is_manual_curated_seed=true`
- R4 inventory report:
  - `status=NO_REUSABLE_EXISTING_EMIT`
  - `decision=RUN_FRESH_DIAGNOSTIC_RETRIEVAL`
  - `candidate_emit_count=46`
  - `reusable_emit_count=0`
  - `fresh_retrieval_required=true`
  - `retrieval_metrics_computed=false`
  - `promotion_evidence=false`
  - `evidence_role=diagnostic`
- Reuse blocker:
  - all candidate emits have `query_id_mismatch` against `eval/gold_queries_text_namu_v4_v0.csv`
  - Phase 7 tuning/sanity candidates use `v4-llm-silver-*`, not `gold_seed_*`

### Gate/Baseline Status

- No retrieval metric, indexing, tuning, immutable baseline update, promotion, candidate mutation, or `rag-data-canary` update was performed.
- R5 is no longer blocked on R4, but it must produce a fresh diagnostic retrieval emit before computing B2-namu metrics.

### Verification

- Command:
  - `python -m py_compile scripts\rag_text_namu_v4_gold_validator.py scripts\rag_text_namu_v4_retrieval_emit_inventory.py`
  - result: passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_namu_v4_gold_validator.py ai-worker\tests\test_rag_text_namu_v4_retrieval_emit_inventory.py`
  - result: 16 passed
- Command:
  - `python -m pytest -q ai-worker\tests\test_rag_text_namu_v4_corpus_inventory.py ai-worker\tests\test_rag_text_namu_v4_gold_validator.py ai-worker\tests\test_rag_text_namu_v4_retrieval_emit_inventory.py ai-worker\tests\test_rag_query_intent_routing_matrix.py ai-worker\tests\test_rag_text_e2e_gold_validator.py ai-worker\tests\test_rag_text_backend_identity.py ai-worker\tests\test_rag_text_retrieval_diagnostic.py`
  - result: 60 passed
- Command:
  - `python scripts\rag_text_namu_v4_gold_builder.py`
  - result: R3 build report `status=COMPLETED`, `row_count=50`
- Command:
  - `python scripts\rag_text_namu_v4_gold_validator.py`
  - result: R3 validation report `status=PASSED`, `positive_row_count=47`
- Command:
  - `python scripts\rag_text_namu_v4_retrieval_emit_inventory.py`
  - result: R4 report `status=NO_REUSABLE_EXISTING_EMIT`, `decision=RUN_FRESH_DIAGNOSTIC_RETRIEVAL`
- Command:
  - JSON parse and custom contract assertion over R2/R3/R4 reports
  - result: passed
- Command:
  - `rg -n "[ \t]+$" ...`
  - result: no trailing whitespace found in touched R3/R4 files
- Command:
  - `git diff --check`
  - result: passed; only CRLF normalization warnings in the dirty worktree

### Important Decisions

- Keep `rag_chunks.jsonl` as the R3/R4 binding and resolution fixture.
- Do not use `chunks_v4.jsonl` as answerability or gold-binding substitute.
- Do not reuse Phase 7 tuning/sanity, B-app smoke, XLSX, PDF, or file lookup artifacts as R5 metric input.

### Remaining Work

- Start R5 B2-namu retrieval diagnostic with a fresh diagnostic retrieval run.
- Keep the R5 denominator limited to R3 positive rows and explicitly exclude `needs_review` rows from metric denominators unless a later policy task changes that.

### Risks

- Existing Phase 7 emits often have clean chunk/page joins, but their query IDs and purpose do not match Track B R4/R5 evidence requirements.
- R4 inventory proves emit reuse readiness only; it does not prove retrieval quality.

### Next Recommended Step

- Run R5 fresh B2-namu retrieval diagnostic.
