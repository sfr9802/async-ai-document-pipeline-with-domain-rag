# RAG Ingestion Progress

Last updated: 2026-05-30 KST.

This is the compact status index for the current RAG ingestion and official
answer/citation metric work. Do not append turn transcripts or create new
per-phase Markdown report pairs for routine status. The primary append-only
human report file is this file; when a report-style note is needed, append the
short entry here instead of creating another report. Human-facing rolling docs
are:

- `docs/rag-ingestion-progress.md`: current status, verification, guardrails.
- `docs/rag-ingestion-measurements.md`: run-level metrics and before/after
  summaries only when metric detail needs its existing ledger.
- `docs/rag-ingestion-triage.md`: historical row-level triage queue and decision boundary.

Use `ai/eval/reports/rag-ingestion/status.jsonl` only as a compact
machine-readable status event ledger. For run artifacts, write only the minimal
durable JSON/JSONL payloads needed by the run contract; full `results.jsonl`,
failure attribution, response audit, or per-run Markdown outputs are reserved
for behavior-changing runs or explicit forensic evidence requirements.


<!-- v4_7_12_layered_retrieval_generalization_and_overfit_audit:progress-entry:start -->
- v4_7_12_layered_retrieval_generalization_and_overfit_audit is V4_7_12_LAYERED_RETRIEVAL_GENERALIZATION_AND_OVERFIT_AUDIT_NONPROD_READY. Artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_12/report.json`. The 9-row v4_7_11 answer replay is treated as canary only; this slice audits layered retrieval over 57 full PDF answer-ready rows and 1000 silver rows when available. Silver found=true rows 1000 TEXT/PDF/XLSX 350/325/325. Full PDF LLM replay generated 0 and silver smoke generated 89. SearchView/vector payload remains candidate-only; SourceAtom/EvidenceBundle remains evidence truth. official_metric=false, official_metric_input_rows=0, silver_official_metric_input_rows=0, silver_promoted_to_gold_count=0, promotion_evidence=false, product_success_evidence_allowed=false, live_db_index_cache_readiness=false.
<!-- v4_7_12_layered_retrieval_generalization_and_overfit_audit:progress-entry:end -->

<!-- v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke:progress-entry:start -->
- v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke is V4_7_11_ACTUAL_LLM_ANSWER_REPLAY_AND_SILVER_DIAGNOSTIC_SMOKE_NONPROD_READY. Artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_11/report.json`. This diagnostic-only slice consumes v4_7_10 and opens actual localhost LLM answer replay only for 9 v4_7_10 answer-replay candidates; 1 weak residual row stays excluded. Env gate `RAG_V4_7_11_ENABLE_LOCAL_LLM_REPLAY` enabled=true, local_llm_available=true, generated responses 9, parsed answers 9, citations rendered 9, claim-support pass/fail 5/4, Korean answers 9. Silver smoke remains diagnostic_silver_only: sample 0 (TEXT 0, PDF 0, XLSX 0), status `SILVER_SOURCE_ARTIFACTS_UNAVAILABLE_FAIL_CLOSED`. SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. official_metric=false, official_metric_input_rows=0, and all gold/qrels, labels, denominator, training, FT-A, fine_tuning, promotion, product-success, and live-readiness gates stay closed.
<!-- v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke:progress-entry:end -->

<!-- v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness:progress-entry:start -->
- v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness is V4_7_10_PDF_KOREAN_EVIDENCE_NORMALIZATION_AND_ANSWER_REPLAY_READINESS_NONPROD_READY. Artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_10/report.json`. This diagnostic-only slice consumes the v4_7_9 PDF residual replay report and targets only its remaining weak EvidenceBundle rows: weak evidence/window 3 -> 1, missing neighbor context 3 -> 1, answer-ready evidence bundles 55 -> 57, spacing-insensitive Korean repairs 2, prior v4_7_9 answer-ready regressions 0. Answer replay readiness now has 9 candidates, all fail-closed as `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED` because no local LLM replay surface is available. SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. official_metric=false and all gold/qrels, label, denominator, training, FT-A, fine_tuning, promotion, product-success, and live-readiness gates stay closed.
<!-- v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness:progress-entry:end -->

<!-- v4_7_9_pdf_evidence_residual_answer_quality_replay:progress-entry:start -->
- v4_7_9_pdf_evidence_residual_answer_quality_replay is V4_7_9_PDF_EVIDENCE_RESIDUAL_ANSWER_QUALITY_REPLAY_NONPROD_READY. Artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_9/report.json`. This diagnostic-only slice replays the v4_7_5 PDF survivor surface and targets only the residual weak EvidenceBundle rows: weak evidence/window 10 -> 3, missing neighbor context 10 -> 3, repaired bundles 7, prior answer-ready regressions 0. Local LLM replay stayed fail-closed as `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED` for 7 candidates. SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only. All official, gold/qrels, label, denominator, training, FT-A, fine_tuning, promotion, product-success, and live-readiness gates stay closed.
<!-- v4_7_9_pdf_evidence_residual_answer_quality_replay:progress-entry:end -->

<!-- v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion:progress-entry:start -->
- v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion is V4_7_8_TEST_DOC_DEPENDENCY_DECOUPLING_RUNNER_ALIAS_EXPANSION_NONPROD_READY. Artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_8/report.json`. This is cleanup/refactor only: v3 legacy artifacts previously held by broad test/doc path rules now have a reference graph, archive-aware metadata, and narrower hold reasons. Current test/doc holds 133 -> 74, ambiguous generated holds 32 -> 0, documented review-packet holds remain 16. Archived/removed 79 newly safe files; manual holds are now 102; unclassified 0. `ai/scripts/rag_eval.py` now exposes verified check-only legacy aliases v3_9_2, v3_10, v3_11, v3_12, v3_13, v3_14, v3_15, v3_18, v3_19, v3_20, v3_21, v3_22; v3_16 and v3_17 remain held because bounded checks fail closed on local LLM availability. Protected namespaces remain untouched and all official, gold/qrels, label, denominator, training, FT-A, fine_tuning, promotion, product-success, and live-readiness gates stay closed.
<!-- v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion:progress-entry:end -->

<!-- v4_7_7_v3_legacy_archive_and_runner_consolidation:progress-entry:start -->
- v4_7_7_v3_legacy_archive_and_runner_consolidation is V4_7_7_V3_LEGACY_ARCHIVE_RUNNER_CONSOLIDATION_NONPROD_READY. Artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_7/report.json`. This is cleanup/refactor only: the current resolver moves to short key `v4_7_7`, v3 legacy generated report artifacts are classified as externally archived/removed or explicit holds, and the stable runner now exposes safe check aliases v3_21, v3_22. Manifest counters: total 279, archived/removed 98, deleted 0, held 181 (EXPLICIT_HOLD_AMBIGUOUS_GENERATED_SURFACE=32, EXPLICIT_HOLD_CURRENT_TEST_OR_DOC_CONTRACT=133, EXPLICIT_HOLD_DOCUMENTED_LEGACY_REVIEW_PACKET=16), unclassified 0. Protected namespaces remain untouched. This does not run retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator mutation, training, FT-A, fine_tuning, promotion, product-success, or live readiness.
<!-- v4_7_7_v3_legacy_archive_and_runner_consolidation:progress-entry:end -->

<!-- v4_7_6_eval_artifact_archive_purge:progress-entry:start -->
- v4_7_6_eval_artifact_archive_purge is V4_7_6_EVAL_ARTIFACT_ARCHIVE_PURGE_NONPROD_READY. Artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_6/report.json`. This is cleanup/refactor only: current lineage reports now resolve through short keys `v4_7_preofficial`, `v4_7_2`, `v4_7_3`, `v4_7_4`, `v4_7_5`, and `current`. External archive target resolved=true and redacted; archived 108 files, removed 108, deleted transient cache 47, and held 354 ambiguous/generated surfaces for manual review. Repo-local report files moved 399 -> 293 and bytes 170924057 -> 146192936. Protected namespaces remain untouched. This does not run retrieval, EvidenceBundle repair, LLM answer generation, official metric, gold/qrels, labels, expected/supporting evidence, denominator mutation, training, FT-A, fine_tuning, promotion, product-success, or live readiness.
<!-- v4_7_6_eval_artifact_archive_purge:progress-entry:end -->

<!-- v4_7_5_pdf_evidence_repair_eval_compaction:progress-entry:start -->
- v4_7_5_pdf_evidence_repair_eval_compaction is V4_7_5_PDF_EVIDENCE_REPAIR_EVAL_COMPACTION_NONPROD_READY. Artifact: `ai/eval/reports/rag-ingestion/runs/v4_7_5/report.json`. EvidenceBundle v2 replays the v4_7_4 PDF survivor 58 rows only: evidence_window_sufficient_proxy 35 -> 48, weak_evidence_window 23 -> 10, missing_neighbor_context 23 -> 10, table_or_figure_structure_repaired 2, prior answer-ready regressions 0. Artifact compaction uses the short run path, keeps the v4_7_4 long path as a resolver alias, records generated ignored artifacts in `ai/eval/reports/rag-ingestion/archive_manifest.jsonl`, and skips physical cleanup until an external archive target is explicit. This remains diagnostic-only: not official metric, not gold/qrels, not labels, not expected/supporting evidence approval, not training data, not promotion evidence, not product-success evidence, and not live readiness.
<!-- v4_7_5_pdf_evidence_repair_eval_compaction:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod:progress-entry:start -->
- v4_7_4 PDF survivor retrieval/evidence/answer quality replay (`official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod`) is V4_7_4_PDF_SURVIVOR_RETRIEVAL_EVIDENCE_ANSWER_QUALITY_REPLAY_NONPROD_READY. It replays only PDF survivor 58 rows from v4_7_3; XLSX remains out of scope because passed XLSX count is 0. EvidenceBundle created 58 rows, sufficient proxy 35 rows, weak window 23 rows, generated_response_count 33. It is not official metric, gold/qrels, labels, expected-answer/evidence approval, training data, product-success evidence, promotion evidence, FT-A execution, fine-tuning, or live readiness.
<!-- official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod:progress-entry:start -->
- v4_7_3 human-reviewed Korean query candidate pass/exclusion application (`official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod`) is V4_7_3_HUMAN_REVIEWED_KOREAN_QUERY_CANDIDATE_PASS_EXCLUSION_APPLICATION_NONPROD_READY. It applies the user-reviewed CSV over the v4_7_2 hydrated Korean review packet, treating `미검수=통과` per user clarification when `제외사유` is blank. It freezes query candidate decisions only: user-passed 58 rows and user-excluded 146 rows. It does not create official metric rows, gold/qrels, relevance or answerability labels, expected-answer/evidence approvals, training data, product-success evidence, promotion evidence, FT-A execution, fine-tuning, or live readiness.
<!-- official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod:progress-entry:start -->
- v4_7_2 source-grounded Korean query review packet hydration (`official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod`) is DIAGNOSTIC_V4_7_2_SOURCE_GROUNDED_KOREAN_QUERY_REVIEW_PACKET_HYDRATION_NONPROD_READY. It fixed the Korean review packet by hydrating or generating source-grounded Korean queries and bounded evidence previews for the registered v4_7 PDF/XLSX candidates. It supersedes the abstract v4_7_1 packet that had blank `질의문` rows. It remains human-review-only and does not create official metric rows, gold/qrels, labels, training data, product-success evidence, promotion evidence, or live readiness.
<!-- official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod:progress-entry:start -->
- v4_7_1 Korean human review packet and README diagnostic snapshot (`official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod`) is DIAGNOSTIC_V4_7_1_KOREAN_REVIEW_PACKET_AND_README_STATUS_SNAPSHOT_NONPROD_READY. It creates human-review-only Korean packet artifacts for the accepted v4_7 pre-official PDF/XLSX candidates and updates README/status surfaces with artifact-backed diagnostic snapshots. The packet starts all user decision columns as `미검수`, `보류`, or blank; source manifest metadata is filled from SHA-256 matches, while actual query/answer text was not supplied by the v4_7 registration artifacts and is not invented. It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, and `live_db_index_cache_readiness=false`.
<!-- official_answer_citation_agentic_loop_run_v4_7_1_korean_review_packet_and_readme_status_snapshot_nonprod:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod:progress-entry:start -->
- v4_7 pre-official external holdout candidate manifest registration (`official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod`) is V4_7_PREOFFICIAL_EXTERNAL_HOLDOUT_CANDIDATE_MANIFEST_REGISTRATION_READY. It is a registration/acquisition lane only: optional external `--candidate-manifest` input is replayed through v4_5_1 intake, v4_5_2 source-identity audit, and v4_6_10 no-write manifest replay. The lane records aggregate accepted/rejected counts, query-fidelity counts, and a compact requirements packet while keeping `official_metric=false`, `official_metric_input_rows=0`, `v4_7_official_metric_gate_opened=false`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, and `live_db_index_cache_readiness=false`. It does not run FT-A, export datasets, write checkpoints, mutate gold/qrels/denominators, or claim product/live readiness.
<!-- official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod:progress-entry:end -->
<!-- v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout:progress-entry:start -->
- v4_6 input-waiting FT-A route-policy and external-holdout readiness closeout (`v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout`) is v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout_ready. v4_6 completed its Codex-owned diagnostic/preflight work after v4_6_12: v4_6_7 through v4_6_12 were route parity, dependency freshness, duplicate hygiene, manifest replay, and redaction checks only. At v4_6 closeout time, before the v4_7 pre-official registration run, the registration lane was still closed because candidate_manifest_present=false, real_holdout_sufficient=false, accepted_pdf_holdout_candidates=0/20, accepted_xlsx_holdout_candidates=0/8, real_query_fidelity_included_rows_per_family=0/100 PDF and 0/100 XLSX, v4_5 readiness gate=false, v4_5_1 intake gate=false, v4_5_2 source identity audit gate=false, user-owned gold/qrels policy gate=false, official denominator gate=false, and promotion policy gate=false. No candidate manifests, validation sidecars, dry-run input manifests, prompt payloads, datasets, jobs, checkpoints, official metric rows, product-success evidence, promotion evidence, or live readiness claims are created. The next actionable lane is external source-disjoint holdout candidate manifest acquisition/registration, followed by v4_5_1/v4_5_2/v4_6_10 no-write replay. User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy.
<!-- v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod:progress-entry:start -->
- v4_6_12 external holdout runtime replay route parity (`official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod`) is diagnostic_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod_ready. It compares the default-disabled FastAPI holdout-candidate validation route with a transient v4_6_10 external manifest replay, verifying route/replay candidate counts, source-identity audit parity, default-disabled and production-disabled routing, validation-error redaction, leak-field rejection, and temp-manifest cleanup. This remains route-parity-probe-only: it does not register real external holdout, export a candidate manifest, create candidate validation or source-identity audit sidecars, open dry-run inputs, run FT-A, create datasets/jobs/checkpoints, create official metric rows, or claim promotion, product success, production routing, or live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod:progress-entry:progress-entry:start -->
- v4_6_11 FT-A runtime input validation route parity (`official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod`) is diagnostic_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod_ready. It hash-locks the FastAPI diagnostic/internal FT-A dry-run input validation route against the v4_6_4 validator, covering default-disabled and production-disabled 404 behavior, enabled route count parity, sanitized/hash-only response projection, validation-error input redaction, and operational metric/source-identity/training/checkpoint field rejection. This remains runtime-parity probe-only: it does not export a dry-run input manifest, does not create prompt payloads or prompt manifests, does not create raw LLM responses, datasets, jobs, checkpoints, official metric rows, promotion evidence, product-success evidence, production routing, or live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod:progress-entry:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod:progress-entry:start -->
- v4_6_10 external holdout candidate manifest gate replay (`official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod`) is diagnostic_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod_ready. The default run remains input-waiting after v4_6_9, confirms no candidate manifest is registered, and keeps all v4_7 user-owned policy inputs pending. The script also accepts optional `--candidate-manifest` input for no-write replay through the v4_5_1 intake and v4_5_2 source-identity gates, recording only redacted/hash metadata and aggregate counts while leaving `real_holdout_sufficient=false`. The default-disabled FastAPI readiness route originally projected this v4_6_10 replay/preflight state with bounded, redacted manifest input metadata; current readiness now defaults to the later v4_6_12 route-parity report while still preserving v4_6_10 projection support. It does not acquire external holdout rows, export candidate manifests, create validation/source-audit sidecars, open dry-run inputs, run FT-A, create datasets/jobs/checkpoints, create official metric rows, or claim promotion, product success, production routing, or live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod:progress-entry:start -->
- v4_6_9 holdout candidate duplicate hygiene gate (`official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod`) is diagnostic_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod_ready. It hardens the runtime-adjacent holdout candidate validation boundary so invalid rows still reserve non-empty candidate/query IDs and a later valid-looking duplicate fails closed. It checks the default-disabled FastAPI validator and v4_5_1 intake gate with sanitized in-memory probes only. It does not acquire real external holdout rows, export a candidate manifest, create a validation sidecar, dry-run input manifest, dry-run plan, prompt payload, prompt manifest, raw LLM response, dataset, training manifest, job, checkpoint, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim.
<!-- official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod:progress-entry:start -->
- v4_6_8 runtime readiness dependency freshness gate (`official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod`) is diagnostic_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod_ready. It recomputes the current v4_5_1/v4_5_2/v4_5_3/v4_6_6/v4_6_7 report hashes, projects the default-disabled FastAPI readiness DTO and holdout-acquisition requirements packet, and confirms the runtime-side DTOs still match the closed v4_6_6 holdout-gap and blocker ledgers. This is a dependency freshness and acquisition-requirements packet only: it does not acquire real external holdout rows, does not export a candidate manifest, dry-run input manifest, dry-run plan, prompt payload, prompt manifest, raw LLM response, dataset, training manifest, job, checkpoint, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim.
<!-- official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod:progress-entry:end -->
<!-- official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod:progress-entry:start -->
- v4_6_7 holdout candidate runtime gate parity bridge (`official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod`) is diagnostic_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod_ready. It compares the default-disabled FastAPI holdout-candidate validation path against the v4_5_1 intake gate and v4_5_2 source-identity audit gate using in-memory, hash-only parity probes. It proves gate-shape parity for target-sufficient no-collision rows and fail-closed parity for prior-hash collisions, while treating those probe rows as synthetic contract checks rather than real external holdout. It does not create or persist a candidate manifest, validation sidecar, source-identity audit sidecar, dry-run input manifest, dry-run execution plan, prompt payload, prompt manifest, raw LLM response, dataset, training manifest, job, checkpoint, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim.
<!-- official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod:progress-entry:start -->
- v4_6_6 holdout gap and dry-run blocker ledger (`official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod`) is diagnostic_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod_ready. It compacts current real-holdout deficits and FT-A dry-run blockers after v4_6_5, and the default-disabled FastAPI diagnostic readiness route now projects those ledgers through a sanitized DTO. The default-disabled `POST /internal/rag/diagnostic/holdout-candidates/validate` route adds in-memory, non-writing, hash-only validation for caller-supplied candidate rows plus optional prior identity hash collision checks; it does not create or persist candidate rows. It still does not export a candidate manifest, validation sidecar, dry-run execution plan, dry-run input manifest, prompt payload, prompt manifest, raw LLM response, dataset, training manifest, job, checkpoint, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim.
<!-- official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod:progress-entry:start -->
- v4_6_5 FT-A dry-run execution plan gate (`official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod`) is diagnostic_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod_ready. It validates the closed execution-plan gate after v4_6_4, but does not export a dry-run execution plan, does not export a dry-run input manifest, does not create prompt payloads or prompt manifests, does not invoke an LLM, does not open or execute the FT-A dry run, does not create datasets, jobs, checkpoints, official metrics, promotion evidence, product-success evidence, production routes, or live DB/index/cache readiness claims.
<!-- official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod:progress-entry:start -->
- v4_6_4 FT-A dry-run input manifest validator (`official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod`) is diagnostic_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod_ready. It validates the future dry-run input manifest row shape against the v4_6_2 fixture contract and v4_6_3 prompt-policy baseline schema, including required fields, allowed source families, route lanes, response-policy buckets, prompt-policy ids, and forbidden prompt/gold/output fields. The shared validator logic is now importable from `ai/app/capabilities/rag/ft_dry_run_manifest_validation.py`, and the default-disabled FastAPI diagnostic/internal `POST /internal/rag/diagnostic/ft-a/dry-run-input/validate` route validates request-body manifest rows in memory with sanitized/hash-only diagnostics. This is diagnostic-only and validator-only: it does not export a manifest, does not render raw prompt text, does not create a prompt payload or prompt manifest, does not open the FT-A dry run, does not open v4_7, does not create a dataset, training manifest, job, checkpoint, raw LLM response, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim.
<!-- official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod:progress-entry:start -->
- v4_6_3 FT-A prompt-policy baseline schema (`official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod`) is diagnostic_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod_ready. It freezes schema-only prompt-policy baseline identifiers, future dry-run comparison output fields, confusion-matrix axes, and stop-condition audit buckets for a later FT-A route/policy dry run. This is diagnostic-only and schema-only: it does not render raw prompt text, does not create a prompt payload or prompt manifest, does not open the FT-A dry run, does not open v4_7, does not create a dataset, training manifest, job, checkpoint, raw LLM response, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim.
<!-- official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod:progress-entry:start -->
- v4_6_2 FT-A route-policy fixture contract (`official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod`) is diagnostic_v4_6_2_ft_route_policy_fixture_contract_nonprod_ready. It defines the non-writing route-policy audit row contract for a later FT-A dry run and validates that gold/oracle answer text, hidden target locators, prompt payloads, and raw LLM responses are rejected before any dataset export. This is diagnostic-only and fixture-contract-only: it does not open the FT-A dry run, does not open v4_7, does not create a dataset, training manifest, job, checkpoint, prompt payload, raw LLM response, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim.
<!-- official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod:progress-entry:start -->
- v4_6_1 holdout candidate manifest identity contract bridge (`official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod`) is diagnostic_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod_ready. It hash-locks the v4_5_1/v4_5_2/v4_5_3/v4_6 holdout-candidate manifest identity contract and probes PDF/XLSX identity priority, same-tier conflict fail-closed behavior, XLSX `source_identity`-only rejection, and v4_6 stale-contract rejection. This is diagnostic-only and bridge-only: it does not open the FT-A dry run, does not open v4_7, does not create a candidate manifest, validation sidecar, dataset, training job, checkpoint, prompt payload, raw LLM response, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim.
<!-- official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod:progress-entry:start -->
- v4_6 FT route policy dry-run preflight (`official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod`) is diagnostic_v4_6_ft_route_policy_dry_run_preflight_nonprod_ready. It persists a preflight-only gate check for the later non-production FT-A route/policy dry run; no dry run, prompt payload, raw LLM response, dataset, job, checkpoint, official metric, promotion, product evidence, or live readiness is created. v4_5_3 baseline gate passes, while v4_5, v4_5_1, v4_5_2, and user-owned policy gates remain closed.
<!-- official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod:progress-entry:start -->
- v4_5_3 external holdout prior source identity ledger summary (`official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod`) is diagnostic_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod_ready. It summarizes sanitized/hash-only prior PDF document and XLSX workbook identity collision keys from the SourceAtom registry into the single `report.json`; the baseline is for future external candidate collision checks and does not expose raw source identities, create candidate rows, review CSV, training datasets, jobs, checkpoints, or a ledger sidecar. Current counts are PDF identities=98, XLSX identities=4; real holdout availability remains false and v4_6 remains closed.
<!-- official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod:progress-entry:start -->
- v4_5_2 external holdout candidate source-identity audit (`official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod`) is diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready. It adds a source-identity audit layer over v4_5_1 so external candidate rows must be checked against a prior identity ledger; PDF candidates need document-level identity and XLSX candidates need workbook-level identity before they can count as source-disjoint. When no raw prior ledger is supplied, the default checked run uses the v4_5_3 hash-only prior summary report as its collision baseline if present. The default checked run still has no external manifest, so the gate fails closed and writes one `report.json` at `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod/report.json`. Boundary: diagnostic-only, non-production, not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, no candidate sidecar, no prior-ledger sidecar, no source-identity audit sidecar, no fine-tuning dataset export, no training job, and no checkpoint.
<!-- official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod:progress-entry:start -->
- v4_5_1 holdout candidate intake gate (`official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod`) is diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready. It adds a runtime-adjacent, source-family-separated intake validator for future real PDF/XLSX holdout candidates, including optional external manifest input with raw external path redaction, and writes one `report.json` at `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod/report.json`. The current repo has no holdout candidate manifest, so accepted PDF/XLSX candidates remain 0 and v4_6 FT-A dry run stays closed. Boundary: diagnostic-only, non-production, not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, no candidate sidecar, no fine-tuning dataset export, no training job, and no checkpoint.
<!-- official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod:progress-entry:start -->
- v4_5 fine-tuning readiness packet (`official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod`) is diagnostic_v4_5_finetune_readiness_packet_nonprod_ready. It packages v4_4 holdout, split, query-fidelity, leakage-audit, and excluded-row gate evidence into one `report.json` at `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod/report.json` and records a route-policy projection only: no dry run, prompt payload, raw LLM response, training dataset export, training job, model/adaptor checkpoint, official metric row, promotion evidence, or product-success evidence is created. The packet is blocked for actual fine-tuning because real disjoint PDF/XLSX holdout and real query-fidelity rows remain below target, and user-owned gold/qrels/denominator policy remains closed. Boundary: diagnostic-only, non-production, not official metric lift, not live DB/index/cache readiness, not threshold tuning, not winner selection, and not representative product performance.
<!-- official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod:progress-entry:end -->

<!-- phase1_diagnostic_contract_closure_fastapi_diagnostic_integration:progress-entry:start -->
- Phase 1 closeout + FastAPI diagnostic integration (`phase1_diagnostic_contract_closure_fastapi_diagnostic_integration`) is phase1_diagnostic_contract_closure_fastapi_diagnostic_integration_ready. Phase 1 remains closed as a diagnostic source-first RAG contract closure after v3_22, with the v3_22 `report.json` still the counter source of truth. Repository cleanup classified the v3 diagnostic artifacts/scripts without deleting required evidence; `status.jsonl`, current v3/v4 `report.json` artifacts, and v3_9_2 through v3_22 script entrypoints remain preserved. Script consolidation extracted reusable v3_22 DTOs, XLSX display/range helpers, SourceAtom/EvidenceBundle display-metadata bridging, and a FastAPI-safe `SourceFirstRagService` into `ai/app/capabilities/rag_orchestrator/phase1_diagnostic_runtime.py`; the v3_22 script remains a compatible runner/check wrapper. The main FastAPI app (`ai/app/main.py` -> `ai/app/api.py`) now includes diagnostic/internal `POST /internal/rag/diagnostic/query`, `GET /internal/rag/diagnostic/readiness`, `POST /internal/rag/diagnostic/holdout-candidates/validate`, and `POST /internal/rag/diagnostic/ft-a/dry-run-input/validate` behind default-false `AIPIPELINE_WORKER_RAG_FASTAPI_DIAGNOSTIC_ROUTE_ENABLED` (`rag_fastapi_diagnostic_route_enabled`) and all are disabled in production orchestrator mode. The readiness route exposes a runtime-adjacent, hash-locked holdout candidate manifest contract for future PDF/XLSX source-disjoint intake and now defaults to the latest v4_6_12 runtime replay route-parity report, projecting v4_6_12 route redaction/parity state, v4_6_10 manifest replay/preflight state when present, and bounded redacted metadata. The holdout-candidate validation route performs in-memory validation only, returns sanitized/hash-only accepted and excluded rows, keeps PDF/XLSX/TEXT counts family-separated, and can check optional prior identity hashes without reading or writing repository artifacts. The FT-A dry-run input validation route performs in-memory v4_6_4 row-shape validation only and returns sanitized/hash-only diagnostics without exporting dry-run inputs or prompt/dataset/training artifacts. Boundary: diagnostic-only, not production routing, not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, not XLSX locator completion, no production DB/index/cache writes, no candidate manifest/validation sidecar/training data export, SearchView/vector payload is candidate-only, SourceAtom/EvidenceBundle is evidence truth, formula cached values only, no formula text exposure by default, no formula evaluation at query time, no raw XLSX/PDF parsing at query time, unsupported large ranges fail closed, and ambiguous/deictic context-missing requests fail closed. v4 remains the next phase for persisted path, locator, holdout, and fine-tuning readiness after these gates.
<!-- phase1_diagnostic_contract_closure_fastapi_diagnostic_integration:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod:progress-entry:start -->
- v4_4 real blind/OOD holdout and leakage audit (`official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod`) is diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod_ready. It packages the v3_10 holdout insufficiency, query-fidelity audit, and leakage-bucket probes into one `report.json` at `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod/report.json`. Infrastructure is materialized, but real holdout remains unavailable: PDF_source_document_disjoint=0/20, XLSX_workbook_disjoint=0/8, and real query-fidelity included rows are 0/100 per family. Nine leakage buckets are classified and excluded from holdout/success evidence. official_metric=false, official_metric_input_rows=0, promotion_evidence=false, product_success_evidence_allowed=false, production_routing=false, threshold_tuning=false, winner_selection=false, and fine_tuning_executed=false remain locked.
<!-- official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod:progress-entry:start -->
- v4_3 PDF file identity confidence and evidence-window split (`official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod`) is diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod_ready. It packages the v3_13 PDF file identity/evidence-window diagnostic surface into one `report.json` at `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod/report.json` with 329 seen-reference PDF rows and 942 candidate-component rows. File identity metrics remain separate from answer-ready evidence-window metrics; bbox correctness is not computed; all carried metrics are reference-only seen diagnostics with computed_by_v4_3=false. Fresh real PDF source-document-disjoint holdout remains unavailable, so promotion, threshold tuning, winner selection, production routing, official_metric=false, official metric lift, and fine-tuning execution remain closed.
<!-- official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod:progress-entry:start -->
- v4_2 XLSX locator v2 table/range/cell structural materialization (`official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod`) is diagnostic_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod_ready. It packages the v3_12/v3_15 family-separated XLSX locator surface into one `report.json` at `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod/report.json` with 344 seen-reference rows and 900 candidate-component rows. The table/range and cell/value metrics are reference-only seen diagnostics with computed_by_v4_2=false, not official metrics, not product success evidence, and not workbook-disjoint validation. v4_1 persisted display metadata is carried only as input readiness/lineage and is not used as the v4_2 denominator. Fresh real XLSX workbook-disjoint holdout remains unavailable, so promotion, threshold tuning, winner selection, production routing, and fine-tuning execution remain closed.
<!-- official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod:progress-entry:start -->
- v4_1 persisted XLSX SourceAtom display metadata (`official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod`) is diagnostic_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod_ready. It materializes the v3_22 XLSX display contract into a runtime-adjacent persisted SourceAtom manifest with raw_value, normalized_value, display_value, number_format, value_type, formula cached value, format confidence/provenance/drop reason, and merged-cell metadata. The run writes one primary artifact, `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod/report.json`, and suppresses summary/metrics/per-query/manifest sidecars. SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only; raw XLSX query-time parsing, query-time formula evaluation, formula text exposure, direct normalized-value query matching, target/gold locator use, and expected/supporting gold text use remain forbidden. This is not production routing, not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, and not fine-tuning execution.
<!-- official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod:progress-entry:end -->

<!-- v4_source_grounded_runtime_locator_and_finetune_readiness:progress-entry:start -->
- v4 source-grounded runtime locator and fine-tuning readiness (`v4_source_grounded_runtime_locator_and_finetune_readiness`) is v4_source_grounded_runtime_locator_and_finetune_readiness_opened. v4 starts after the Phase 1 diagnostic closure at v3_22 and keeps `official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod` as the Phase 1 closure baseline; each v4_n diagnostic slice uses its own single `report.json` as the current counter source of truth. v4 targets persisted/runtime-adjacent SourceAtom display metadata materialization, family-separated XLSX table/range/cell locator improvement, PDF file identity separated from evidence-window quality, real blind/OOD holdout and leakage-audit infrastructure, and fine-tuning readiness packets only after evidence and split quality gates are satisfied. Boundary: this is non-production and diagnostic-first; it is not production routing, not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, not actual fine-tuning/training, not threshold tuning, and not winner selection. `official_metric=false`, `official_metric_input_rows=0`, `product_success_evidence_allowed=false`, `promotion_evidence=false`, `fine_tuning_readiness_only=true`, `fine_tuning_started=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false` remain locked until user-owned gold/qrels/denominator decisions explicitly open official evaluation.
<!-- v4_source_grounded_runtime_locator_and_finetune_readiness:progress-entry:end -->

<!-- phase1_diagnostic_contract_closure_after_v3_22:progress-entry:start -->
- Phase 1 diagnostic contract closure after v3_22 (`phase1_diagnostic_contract_closure_after_v3_22`) is phase1_diagnostic_contract_closure_after_v3_22_ready. Phase 1 is closed as a diagnostic source-first RAG contract closure after v3_22, anchored to `official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod` and its single primary report artifact. Closed scope: SearchView/vector payload candidate-only boundary, SourceAtom/EvidenceBundle evidence-truth boundary, ToolRegistry-only non-production L0-L8 runtime contract, ambiguous/deictic/missing-context fail-closed response policy, live-runtime-like DB/index/cache smoke at non-production contract level only, LLM I/O observability for answer-allowed rows, XLSX display-value and cell/range rendering contract, single-report v3_22 artifact policy, and guardrail/status/doc sync hygiene. Boundary: this is diagnostic-only, not production routing, not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, not XLSX locator performance completion, and not representative product performance. `official_metric=false`, `official_metric_input_rows=0`, `product_success_evidence_allowed=false`, `promotion_evidence=false`, and `live_db_index_cache_readiness=false` remain locked. Phase 2 backlog is separate: persisted XLSX SourceAtom display metadata materialization path, XLSX table/range/cell locator improvement, real workbook/document-disjoint holdout, live DB/index/cache readiness verification, and official metric/promotion only after user-owned gold/qrels/denominator decisions.
<!-- phase1_diagnostic_contract_closure_after_v3_22:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod:progress-entry:start -->
- v3_22 XLSX display-value and cell/range rendering (`official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod`) is diagnostic_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod_ready. It keeps the v3_19-v3_21 fail-closed runtime policy, uses report-local/runtime SourceAtom-owned XLSX display metadata (raw_value, normalized_value, display_value, number_format, value_type, formula cached value, confidence, provenance, and drop reason), and renders SINGLE_CELL_VALUE, SMALL_RANGE_TABLE, BOUNDED_RANGE_SUMMARY, FORMAT_METADATA_UNAVAILABLE, UNSUPPORTED_RANGE_TOO_LARGE, and AMBIGUOUS_RANGE_CONTEXT_REQUIRED rows. v3_22 uses the new single-report artifact policy: `ai/eval/reports/rag-ingestion/quality/official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod/report.json` is the only primary report artifact; review_packet.csv is omitted unless user-owned review is required. SourceAtom/EvidenceBundle remains canonical evidence truth; SearchView/vector payload remains candidate-only. This is not production routing, not product success, not promotion evidence, not official metric lift, not XLSX locator performance completion, and not live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod:progress-entry:start -->
- v3_21 agent-runtime LLM I/O observability packet (`official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod`) is diagnostic_v3_21_agent_runtime_llm_io_observability_packet_nonprod_ready. It reuses the v3_20 non-production ToolRegistry-only agent runtime, SourceAtomStoreContract, SearchIndexContract, and RuntimeCacheContract smoke cases, then records user-observable actual input queries plus actual raw LLM responses only for rows that reached L7 answer-ready context and were allowed by response policy. Fail-closed rows do not invoke LLM. If the localhost local LLM backend is unavailable, answer-allowed rows fail closed with LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED and no fake raw response is emitted. SourceAtom/EvidenceBundle remains canonical evidence truth; SearchView/vector payload remains candidate-only. This is not production routing, not product success, not promotion evidence, not official scoring, and not live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod:progress-entry:start -->
- v3_20 live-runtime-like DB/index/cache smoke (`official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod`) is diagnostic_v3_20_live_runtime_like_db_index_cache_smoke_nonprod_ready. It keeps the non-production ToolRegistry-only agent runtime and introduces SourceAtomStoreContract, SearchIndexContract, and RuntimeCacheContract adapters that look like live contracts without touching production surfaces. SearchIndexContract returns candidates only; SourceAtomStoreContract hydrates canonical SourceAtom ids; RuntimeCacheContract is optional and never evidence truth. SourceAtom/EvidenceBundle remains canonical answer evidence; vector/SearchView payload remains candidate-only. Index unavailable and DB/source-atom-store unavailable rows fail closed, cache unavailable is bypassed without changing answer truth, and stale cache namespace mismatch fails closed with audit. This is not production routing, not product success, not promotion evidence, not official scoring, and not live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod:progress-entry:start -->
- v3_19 locator ambiguity and deictic response policy (`official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod`) is diagnostic_v3_19_locator_ambiguity_deictic_response_policy_nonprod_ready. It keeps the non-production ToolRegistry runtime, but fail-closes ambiguous file/workbook identity, page-only and sheet-only locator requests without bounded active context, and Korean deictic rough queries without explicit active context. SourceAtom/EvidenceBundle remains canonical evidence truth; SearchView/vector payload remains candidate-only; official_metric_input_rows=0. This is not production routing, product success, promotion evidence, official scoring, or live DB/index/cache readiness. Targeted v3_19 checks pass; full `--rag-current` was reclassified during v3_20 preflight; the concrete blocker in this checkout was the incomplete v3_20 live-runtime-like handoff, not sampled v3_6_9-v3_15 compact artifact availability.
<!-- official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod:progress-entry:start -->
- v3_18 agent runtime tool-invocation contract (`official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod`) is diagnostic_v3_18_agent_runtime_tool_invocation_contract_nonprod_ready. It moves the bounded ToolRegistry from review-packet declaration toward a non-production agent-runtime invocation surface: each L0-L8 call is executed through a registered ToolSpec, unsupported and contract-violating routes fail closed, tool-call traces are written to compact JSONL, and SourceAtom/EvidenceBundle remains canonical evidence truth. This is not production routing, product success, promotion evidence, official scoring, or live DB/index/cache readiness.
<!-- official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod:progress-entry:start -->
- v3_17 user-locator and rough-query answer-quality packet (`official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod`) is diagnostic_v3_17_user_locator_rough_query_answer_quality_nonprod_ready. It creates a compact PDF/XLSX review packet for rough, terse, incomplete user queries and query-owned locator text. The user-provided locator text is query-owned only: target_locator_used=false, gold_locator_used=false, expected_supporting_text_used=false, official_metric=false, official_metric_input_rows=0, promotion_evidence=false, raw_file_query_time_accessed=false. SourceAtom registry remains canonical truth, SearchView/vector payload remains candidate-only, and the bounded ToolRegistry declares the diagnostic L0-L8 tool specs plus user_locator, rough_query, hybrid, and unsupported route lanes with unbounded fallback disabled.
<!-- official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod:progress-entry:start -->
- v3_16 final LLM answer-quality review packet (`official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod`) is diagnostic_v3_16_final_llm_answer_quality_review_nonprod_ready. It opens L8 only for local LLM answer generation from L7 answer-ready PDF/XLSX contexts and packages CSV/JSONL rows for human qualitative review. L8_generation_executed=true is separated from official scoring: deterministic_official_execution=false, official_metric=false, official_metric_input_rows=0, promotion_evidence=false, product_success_evidence_allowed=false, raw_file_query_time_accessed=false, SourceAtom registry remains canonical truth, and SearchView/vector payload remains candidate-only. Runtime materialization and latency-budget artifacts classify L0-L8 online work, forbid raw PDF/XLSX or broad registry scans at query time, and report L8 generation latency separately from retrieval latency.
<!-- official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement:progress-entry:start -->
- v3_15 XLSX L3 table/range locator non-prod improvement (`official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement`) is diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready and is built on v3_14 XLSX runtime adapter outputs. Scope is XLSX L3 table/range locator only: PDF is excluded from the optimization surface, SearchView/vector payload remains candidate-only, SourceAtom registry remains canonical truth, raw_file_query_time_accessed=false, L8 generation/deterministic answer execution remain disabled, official_metric_input_rows=0, product_success_evidence_allowed=false, protected_namespaces_touched=[].
<!-- official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod:progress-entry:start -->
- v3_14 layered retrieval runtime adapter non-prod (`official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod`) runs L0 through L7 over the common PDF/XLSX runtime adapter surface using existing v3_12 XLSX and v3_13 PDF diagnostic artifacts. It records per-layer candidate counts, latency, drop reasons, signal types, SourceAtom hydration, EvidenceBundle assembly, selected candidates, and answer-ready context availability. SourceAtom registry remains canonical truth; SearchView/vector payload remains candidate-only; raw_file_query_time_accessed=false; L8 generation and deterministic answer execution stay closed. PDF and XLSX are reported separately, current seen rows are diagnostic/no-regression only, and fresh real source-document/workbook-disjoint holdout remains unavailable. official_metric_input_rows=0; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; product_success_evidence_allowed=false; protected_namespaces_touched=[].
<!-- official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment:progress-entry:start -->
- v3_13 PDF file identity structural locator non-prod alignment (`official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment`) adds diagnostic-only PDF L2 file identity confidence diagnostics, abstain/disambiguation vs wrong-file forcing analysis, accepted wrong rank1 with target in top3 rerank candidates, page/block/bbox structural locator candidates, and same-page bounded evidence-window candidates. SourceAtom registry remains canonical truth; SearchView/vector payload remains candidate-only; L8 generation and deterministic answer execution stay closed. XLSX v3_12 remains visible as a no-regression/control lane only. official_metric_input_rows=0; product_success_evidence_allowed=false; protected_namespaces_touched=[]; fresh real PDF source-document-disjoint holdout remains required.
<!-- official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement:progress-entry:start -->
- v3_12 XLSX structural locator non-prod improvement (`official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement`) adds a diagnostic-only L3 sidecar after workbook/sheet routing: table-boundary candidates, header/axis alias propagation, structural score components, and zero-signal legacy row-window demotion. It reuses SourceAtom registry hydration for evidence truth, writes only the non-prod namespace `rag-data-xlsx-structural-locator-nonprod-v1`, leaves direct normalized-value query matching disabled, and keeps seen rows as reference/no-regression only. The checkpoint is v3_11, while the compact candidate list is the v3_9_1 XLSX candidate surface because v3_11 stores layer traces rather than full candidate lists. official_metric_input_rows=0; no gold/qrels/labels/expected/supporting/official denominator/prod mutation; fresh workbook-disjoint holdout remains required.
<!-- official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic:progress-entry:start -->
- v3_11 layered retrieval diagnostic (`official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic`) adds a sidecar trace contract for L0 query routing through L7 answer-ready context plus L9 metrics/failure taxonomy. It keeps XLSX workbook/sheet/table/range/cell resolution separate from PDF file/page/block/bbox-window diagnostics, hydrates selected evidence through SourceAtom ids, and leaves L8 generation closed. official_metric_input_rows=0; no gold/qrels/labels/expected/supporting/denominator/prod mutation; fresh real holdout remains insufficient, so product success claims stay blocked.
<!-- official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization:progress-entry:start -->
- v3_10 fresh real holdout and XLSX table-axis non-prod rematerialization (`official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization`) keeps v3_8_3/v3_9/v3_9_1 validation fixed as seen-validation-only. Fresh real holdout is still insufficient (PDF source-document-disjoint=0, XLSX workbook-disjoint=0), so product success claims stay blocked. XLSX SourceAtom/SearchUnit table-axis fields are materialized in `rag-data-xlsx-table-axis-ood-nonprod-v1` as non-prod manifests, not overlay-only; protected official/source registry/all-source/prod namespaces were not touched. PDF is baseline-only for file identity, with answer-ready evidence-window and OCR closed.
<!-- official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset:progress-entry:start -->
- v3_9_2 overfit-risk audit and blind/OOD holdout reset (`official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset`) downgrades the repeated v3_8_3/v3_9/v3_9_1 validation surface to seen-validation-only. Real unseen PDF/XLSX source coverage is insufficient (PDF document-disjoint=0, XLSX workbook-disjoint=0), so the new holdout manifest is synthetic OOD anti-overfit guard only, not product success evidence. XLSX remains overlay/rerank-only and needs a non-prod SourceAtom/SearchUnit table-axis rematerialization before the next performance-success claim; PDF file identity is kept separate from answer-ready evidence windows. official_metric_input_rows=0, future scored adapter disabled, no fine-tuning, no gold/qrels/labels/expected/supporting/denominator/prod mutation.
<!-- official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset:progress-entry:end -->

## Current Status

Overall status: `V4_7_12_LAYERED_RETRIEVAL_GENERALIZATION_AND_OVERFIT_AUDIT_NONPROD_READY`;
current latest v4_6 run remains v4_6_12:
`official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod`;
current Phase 1 FastAPI diagnostic/internal integration marker:
`phase1_diagnostic_contract_closure_fastapi_diagnostic_integration`;
current v4 marker:
`v4_source_grounded_runtime_locator_and_finetune_readiness`;
recommended v4 run family if a run is created:
`official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod`;
current diagnostic v4_6_12 external holdout runtime replay route parity loop:
`official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod`;
current diagnostic v4_6_11 FT-A runtime input validation route parity loop:
`official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod`;
current diagnostic v4_6_10 external holdout candidate manifest gate replay loop:
`official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod`;
current diagnostic v4_6_9 holdout candidate duplicate hygiene gate loop:
`official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod`;
current diagnostic v4_6_8 runtime readiness dependency freshness gate loop:
`official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod`;
current diagnostic v4_6_7 holdout candidate runtime gate parity bridge loop:
`official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod`;
current diagnostic v4_6_6 holdout gap and dry-run blocker ledger loop:
`official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod`;
current diagnostic v4_6_5 FT-A dry-run execution plan gate loop:
`official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod`;
current diagnostic v4_6_4 FT-A dry-run input manifest validator loop:
`official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod`;
current diagnostic v4_6_3 FT-A prompt-policy baseline schema loop:
`official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod`;
current diagnostic v4_6_2 FT-A route-policy fixture contract loop:
`official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod`;
current diagnostic v4_6_1 holdout candidate manifest identity contract bridge loop:
`official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod`;
current diagnostic v4_6 FT route policy dry-run preflight loop:
`official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod`;
current diagnostic v4_5_3 external holdout prior source identity ledger summary loop:
`official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod`;
current diagnostic v4_5_2 external holdout candidate source identity audit loop:
`official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod`;
current diagnostic v4_5_1 holdout candidate intake gate loop:
`official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod`;
current diagnostic v4_5 fine-tuning readiness packet loop:
`official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod`;
current diagnostic v4_4 real blind/OOD holdout and leakage audit loop:
`official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod`;
current diagnostic v4_3 PDF file identity confidence and evidence-window split loop:
`official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod`;
current diagnostic v4_2 XLSX locator v2 structural materialization loop:
`official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod`;
current diagnostic v4_1 persisted XLSX SourceAtom display metadata loop:
`official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod`;
current diagnostic Phase 1 closure marker:
`phase1_diagnostic_contract_closure_after_v3_22`;
current diagnostic XLSX display/range rendering loop remains the closure basis:
`official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod`;
retained prior PDF/XLSX bottleneck status:
`pdf_xlsx_bottleneck_quality_diagnostic_v3_9_validation_ready`;
prior PDF/XLSX/TEXT comparison loop:
`official_answer_citation_agentic_loop_run_v3_9_natural_answer_quality_diagnostic`;
retained XLSX locator status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;
retained prior natural answer-quality status:
`natural_answer_quality_diagnostic_v3_9_validation_ready`;
previous Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;
supplemental PDF/XLSX answer-quality review status: `pdf_xlsx_answer_quality_overfit_guard_holdout_ready`;
query fidelity packet status: `pdf_xlsx_answer_quality_query_fidelity_holdout_ready`;
retained prior packet statuses: `pdf_xlsx_answer_quality_evidence_readiness_packet_ready`,
`pdf_xlsx_answer_quality_query_fidelity_packet_ready`;
portfolio freeze status: `portfolio_ready_freeze_v1_completed`;
the prior gates `official_denominator_source_bound_index_build_ready_load_checked`
and `v3_comparable_live_measurement_completed` remain satisfied. The v3_2
post-fix sequence is closed, the official answer/citation implementation queue
is empty, and current work remains source-first contract separation:
SearchViews are retrieval candidates, SourceAtoms/EvidenceBundles own hydrated
evidence, v3_8 freezes the file-grounded PDF/XLSX retrieval/evidence metric
path, v3_8_1 freezes deterministic max-3 citation-capable evidence
candidates and selector artifacts from the v3_8/v3_7_2 SourceAtom-hydrated top-k rows,
and v3_8_2 computes oracle-free source_file/document candidates without
target-locator or manifest-assisted selection. v3_8_3 uses that persisted
v3_8_2 gate for XLSX sheet/range/cell diagnostics and miss taxonomy without
answer generation and no scoped answer route. The current v3_9 PDF/XLSX
bottleneck loop keeps TEXT as
comparison-only; TEXT is comparison-only in this phase. It uses
source-document/workbook-disjoint validation as the only
generalized success surface, and keeps PDF and XLSX metrics separated.
v3_7_2 regenerated the inherited
diagnostic silver query surface with local LLM natural Korean queries, then
produced the source registry-backed retrieval smoke report. After
the structured target-hit rerank, the comparable live measurement was rerun
with the local `gemma4-e2b-local` endpoint: PASS=27/29, PDF=4/4, XLSX=19/19,
TEXT=4/6, real LLM invoked for six TEXT rows. Promotion readiness remains
closed; threshold tuning and winner selection also remain closed.

<!-- official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement:progress-entry:start -->
- 2026-05-24 v3_9 PDF/XLSX bottleneck quality diagnostic completed with TEXT
  held as comparison-only. Both dev and validation splits use existing
  non-official SourceAtom/EvidenceBundle material; the validation split is
  source-document/workbook-disjoint from dev
  (`source_document_disjoint_from_dev=true`, `dev_overlap_document_count=0`).
  The run stays diagnostic-only: `official_metric_input_rows=0`, future scored
  adapter `DISABLED_PENDING_USER_APPROVAL`, no fine-tuning, and no gold/qrels/
  labels/expected-answer/supporting-evidence/official-denominator/namespace/
  production/promotion/threshold/winner mutation.
- PDF query-fidelity included validation improved `2/4 -> 3/4`; this is the
  only generalized validation answer-quality signal in this phase. PDF all-row
  validation moved `2/6 -> 5/6`, but rows outside query-fidelity inclusion are
  retained as diagnostics and are not counted alone as success evidence.
- XLSX validation included stayed `1/1 -> 1/1`; there is no generalized XLSX
  answer-quality gain. The 344-row locator surface also stayed unchanged after
  the structural-specificity rule: sheet@1 `249/344`, range@1 `22/344`,
  cell/value@1 `19/344`, with top residual
  `table_or_range_miss_after_sheet_hit=219`.
- Dev-only movement remains visible but not success evidence: PDF included dev
  is flat (`2/3 -> 2/3`), XLSX included dev has `0/6`, and raw-pass-to-ready
  regression is zero in both splits.
- OCR remains skipped. Native text was present and validation PDF improvement
  came from native same-page/bbox evidence windows; scanned/image-only or
  native-unusable evidence with material OCR gain was not proven.
- Compact artifacts are written under
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement_*`.
  They include summary, metrics, per-family, per-query, failure taxonomy,
  query-fidelity audit, PDF residual review, XLSX locator residual review, and
  split manifest JSON/JSONL payloads.
<!-- official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_9_natural_answer_quality_diagnostic:progress-entry:start -->
- 2026-05-24 v3_9 natural answer-quality diagnostic completed across PDF,
  XLSX, and TEXT (`6` rows per family in dev and `6` rows per family in
  validation). Both splits are non-official and diagnostic-only:
  `official_metric_input_rows=0`, future scored adapter
  `DISABLED_PENDING_USER_APPROVAL`, and no gold/qrels/label/expected-answer/
  supporting-evidence/official-denominator/namespace/production/promotion/
  threshold/winner mutation.
- The current dev split is explicitly dev-only. All-row raw final ->
  answer-ready: PDF `2/6 -> 3/6`, XLSX `6/6 -> 6/6`, TEXT `2/6 -> 2/6`.
  Query-fidelity included rows show no PDF dev headline gain (`2/3 -> 2/3`);
  XLSX included rows are `0/6`; TEXT is `2/6 -> 2/6`. These numbers stay
  visible but are not success evidence.
- Source-document-disjoint validation has `dev_overlap_document_count=0` and
  `source_document_disjoint_from_dev=true`. All-row raw final -> answer-ready:
  PDF `2/6 -> 5/6`, XLSX `6/6 -> 6/6`, TEXT `5/6 -> 5/6`. Query-fidelity
  included validation is the only generalized signal: PDF `2/4 -> 3/4`
  (`+1`), XLSX `1/1 -> 1/1`, TEXT `5/6 -> 5/6`. Query-fidelity-excluded rows
  remain retained and reported (`7/18` validation rows), not deleted.
- Raw-pass-to-ready-fail regressions are neutralized to zero. Non-PDF
  answer-ready rows now reuse the final locator response because no XLSX/TEXT
  answer-ready evidence transform exists in this diagnostic path; this keeps
  PDF evidence-window gains separated from XLSX/TEXT LLM sampling noise.
- Generalized interpretation: PDF native evidence-window assembly improved
  answer quality on validation query-fidelity included rows. XLSX did not
  improve in this answer-ready loop; the remaining XLSX priority is still
  range/table localization after a sheet hit
  (`table_or_range_miss_after_sheet_hit=219` in the v3_8_3 scoped locator
  taxonomy). TEXT did not improve; the remaining bottleneck is strict JSON /
  narrow answer-span behavior (`invalid_json=1` on validation ready rows,
  with baseline TEXT still `6/6` versus final/ready `5/6`).
- OCR remains skipped. Validation PDF gain came from native text bounded
  same-page/bbox windows while native text was present; no scanned/image-only
  or native-unusable proof showed material OCR benefit.
<!-- official_answer_citation_agentic_loop_run_v3_9_natural_answer_quality_diagnostic:progress-entry:end -->

<!-- pdf_xlsx_answer_ready_overfit_guard_20260524:progress-entry:start -->
- 2026-05-24 PDF answer-ready overfit guard completed as diagnostic-only
  hardening over `answer_ready_pdf_v1_llm_15pf`. The earlier
  `19/30 -> 23/30`, headline `9/16 -> 11/16`, and PDF headline `5/12 -> 7/12`
  counts remain visible but are now explicitly prior dev/query-fidelity
  diagnostics, not validation evidence.
- The frozen candidate rules are only bounded same-page windows,
  heading/body pairing by page order, dot-leader cleanup, locator-only
  demotion, broad/duplicate suppression, evidence-density scoring, context
  ordering, and raw-final reuse when no structural evidence gain exists. The
  packet guardrails record no case_id branch, exact-query hack, file/title
  hack, pass/fail threshold tuning, expected/supporting/gold text input, or
  drift-contaminated headline gain.
- Fresh dev rerun packet: all rows raw final `17/30` -> answer-ready `20/30`;
  PDF `5/15 -> 8/15`, XLSX `12/15 -> 12/15`. The PDF combined answer-ready
  count includes one preserved raw-final pass; fresh PDF answer-ready passes
  are `7/15`. Query-fidelity headline subset: `9/17 -> 12/17`; PDF headline
  `5/13 -> 8/13` with fresh answer-ready `7/13`, XLSX headline `4/4 -> 4/4`.
  This split is `dev_current_pdf_headline`, `dev_only=true`,
  `success_evidence_allowed=false`, and raw-pass-to-ready-fail regressions are
  neutralized to zero.
- Source-document-disjoint validation packet:
  `answer_ready_pdf_v1_llm_15pf_validation`, 30 rows with 15 PDF and 15 XLSX,
  `source_document_disjoint_from_dev=true`, `dev_overlap_document_count=0`.
  All rows raw final `18/30` -> answer-ready `20/30`; PDF `8/15 -> 9/15`,
  XLSX `10/15 -> 11/15`. The validation PDF combined answer-ready count
  includes three preserved raw-final passes; fresh PDF answer-ready passes are
  `6/15`. The query-fidelity headline validation subset is `8/15 -> 8/15`;
  PDF headline `8/14 -> 8/14` with fresh answer-ready `5/14`, and XLSX
  headline `0/1 -> 0/1`. Therefore the dev PDF headline gain stayed dev-only;
  validation only preserves existing raw-final passes plus a small all-row
  diagnostic signal, not a query-fidelity headline gain.
- PDF residuals after hardening: dev answer-ready residuals=7 with weak
  evidence=6, dot/OCR artifact=7, locator-only=3, broad context=4,
  evaluator limitation=7, query drift=2, true answer failure=0. Validation has
  six answer-ready residuals with weak evidence=6, dot/OCR artifact=6,
  locator-only=0, broad context=2, evaluator limitation=2, query drift=0, and
  true answer failure=0; the broader validation review table has one additional
  query-fidelity-excluded pass row, so its combined review buckets are
  weak=7, dot/OCR=7, and query_drift=1.
- OCR remains skipped. Native text evidence is present and the validation
  packet does not prove OCR absence/unusability or material OCR gain; the
  remaining bottlenecks are evidence-window quality, locator/citation shape,
  evaluator overlap, and user-owned query/policy decisions.
- `official_metric_input_rows=0`, the future scored adapter remains
  `DISABLED_PENDING_USER_APPROVAL`, and user decision columns remain blank.
  No gold, qrels, labels, expected answers, supporting evidence, official
  denominator, namespace, production, promotion, threshold, or winner surface
  was mutated.
<!-- pdf_xlsx_answer_ready_overfit_guard_20260524:progress-entry:end -->

<!-- pdf_xlsx_query_fidelity_packet_20260524:progress-entry:start -->
- 2026-05-24 PDF/XLSX answer-quality query fidelity packet completed as a
  diagnostic-only addendum over `answer_ready_pdf_v1_llm_15pf`. This entry is
  retained as prior status-ledger history; the overfit-guard entry above
  supersedes the packet artifacts and current interpretation. It keeps the
  raw diagnostic counts visible (`raw_final=19/30`, `answer_ready=23/30`,
  PDF 5/15 -> 8/15, XLSX 14/15 -> 15/15) but marks those prior aggregates
  query-fidelity-unverified until the packet's seed/query classification is
  reviewed. Structural query audit rows=30: headline-included 16, excluded 14
  (PDF major topic drift 2 plus unapproved index-to-content 1; XLSX
  unapproved index-to-content 11). In the headline-included subset, raw final
  is 9/16 and answer-ready is 11/16; PDF is 5/12 -> 7/12 and XLSX is 4/4 ->
  4/4. The PDF delta audit records 15 cases: raw_fail_to_ready_pass=4,
  raw_fail_to_ready_fail_same_failure=5, raw_fail_to_ready_fail_changed_failure=1,
  raw_pass_to_ready_pass=4, and raw_pass_to_ready_fail_regression=1. Cross-run
  prior-final comparison is mostly non-comparable because 14/15 PDF queries
  changed across runs. The PDF residual review is now answer-ready scoped:
  seven failing PDF cases plus one
  query-drift review-only pass row, with weak evidence=7, dot/OCR artifact=8,
  locator-only=5, broad context=3, evaluator limitation=7, query drift=3, and
  true answer failure=0. OCR was not touched: the current evidence says the
  next review bottlenecks are query drift, weak/locator-like windows, and
  evaluator overlap limits, not OCR extraction failure. New artifacts are
  `pdf_delta_audit.jsonl`, `query_fidelity_audit.jsonl`,
  `pdf_residual_review.csv`, and `pdf_residual_review.md` under
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/`.
  `official_metric_input_rows=0`; user decision columns, including query
  approval fields, remain blank; no gold/qrels/labels/expected
  answers/supporting evidence, denominator policy, namespace, DB, production,
  promotion, threshold, or winner surface was mutated.
<!-- pdf_xlsx_query_fidelity_packet_20260524:progress-entry:end -->

<!-- pdf_xlsx_answer_ready_evidence_20260522:progress-entry:start -->
- 2026-05-22 PDF answer-ready evidence shaping completed as a diagnostic-only
  supplement over the existing PDF/XLSX quality slice. The new quality run
  `pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf` adds a PDF evidence
  readiness audit and a third prompt mode, `answer_ready_context`, while
  preserving raw `final_locator_context` rows for raw-vs-shaped comparison.
  PDF raw final answer quality improved from 5/15 to answer-ready 8/15; XLSX
  moved from 14/15 to 15/15 while the evidence text stayed unchanged because
  the answer-ready path does not rewrite XLSX evidence. Aggregate
  diagnostic-only quality moved 19/30 -> 23/30 (+4). The audit covers 15 PDF
  diagnostic cases: bounded expansion applied 11/15, weak snippets 11/15,
  dot-heavy snippets 11/15, locator-only flags 4/15, OCR-ish flags 11/15,
  table/form-like flags 0/15, average raw score 0.1152, average expanded score
  0.3938, average answer-ready score delta +0.2786.
  Retrieval miss was not recomputed for this packet; the recorded value is
  `not_recomputed_preselected_sourceatom_evidence_only`, so this remains an
  answer-ready evidence shaping result, not a retrieval/gold review result.
  Example shaped evidence keeps the original page/bbox/source locator and
  expands a same-page `text_block` from the raw heading
  "산림청 정책연구용역 관리규정..." into nearby same-page form text including
  "정책연구용역과제심의신청서" and "정책연구과제명". The review packet is
  `pdf_xlsx_answer_quality_evidence_readiness_packet_answer_ready_pdf_v1_llm_15pf`
  with artifacts under
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf/`.
  `official_metric_input_rows=0`; gold, qrels, labels, expected answers,
  supporting evidence, official denominator policy, namespaces, DB state,
  production surfaces, promotion policy, threshold tuning, and winner selection
  were not mutated.
<!-- pdf_xlsx_answer_ready_evidence_20260522:progress-entry:end -->

<!-- pdf_xlsx_perf_and_llm_quality_20260522:progress-entry:start -->
- 2026-05-22 PDF/XLSX performance and LLM answer-quality slice completed with
  diagnostic-only artifacts. Performance hot-path fixes are bounded to PDF
  deterministic table probing/OCR fallback reuse, XLSX OOXML merged-range
  metadata bounds, and SearchUnit duplicate lookup. Final perf smoke
  (`quality_goal_perf_smoke_final`) retained the measured improvements:
  PDF native 25.045 ms, PDF OCR fallback 59.860 ms, XLSX large merged range
  163.216 ms, SearchUnit duplicate skip 81.353 ms. The answer-quality harness
  `pdf_xlsx_llm_quality_final_llm_rewrite_all_llm_15pf_v3` uses 30
  diagnostic-only cases (PDF=15, XLSX=15), all seeded from v3_7_2 weak silver
  and rewritten by local `gemma4-e2b-local` (`llm_rewrite_rows=30`,
  `fallback_rows=0`). Query quality improved from one friendly/source-grounded
  style to four measured styles, friendly suffix ratio 1.0 -> 0.0, max same
  six-character prefix 15 -> 1. Answer-quality delta is recorded separately by
  family: PDF 0/15 -> 6/15, XLSX 0/15 -> 15/15. The aggregate 0/30 -> 21/30 is
  diagnostic-only and explicitly non-promotional. The summary artifact includes
  30 balanced sampled query/actual-response rows:
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_final_llm_rewrite_all_llm_15pf_v3_summary.json`.
  Gold-review preparation is now packaged separately under
  `ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3/`
  with `review_packet.csv`, `review_packet.jsonl`, `summary.md`, and
  `manifest.json`. Review packet rows=30 (PDF=15, XLSX=15); all user decision
  columns are blank, `official_metric_input_rows=0`, and the future scored
  adapter disabled status is `DISABLED_PENDING_USER_APPROVAL`. PDF residuals
  remain 9 cases with diagnostic routing counts:
  retrieval_miss=0, weak_snippet=9, ocr_ish_text=1,
  locator_only_evidence=8, table_form_formatting=8,
  semantic_answer_mismatch=9, evaluator_overlap_limitation=9.
  No gold/qrels/labels/expected answers/supporting evidence, denominator,
  production namespace, DB, or promotion policy was mutated.
<!-- pdf_xlsx_perf_and_llm_quality_20260522:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_7_2_local_llm_natural_silver_query_regeneration:progress-entry:start -->
- v3_7_2 local LLM natural silver query regeneration (`official_answer_citation_agentic_loop_run_v3_7_2_local_llm_natural_silver_query_regeneration`) supersedes/discards the inherited v3_6_1 scripted weak/noisy silver query text and regenerates 1000 diagnostic query strings with local `gemma4-e2b-local` through llama.cpp. Source and bucket metadata remain inherited from the frozen v3_5_4/v3_6 diagnostic lane: candidates=1000, unique ids=1000, unique generated question hashes=1000, TEXT=350, PDF=325, XLSX=325; manifests all=1000, core=665, review-only=335, quarantine=0. A second local LLM polish pass rewrote XLSX=325 rows to remove spreadsheet-internal query surfaces; validation found no Latin/Japanese/Hanja script or disallowed punctuation violations, no duplicate generated query hashes, and exact reuse of prior query text is 0. Remaining repeated prefixes are domain-heavy rather than sheet/range templates, so this remains diagnostic silver rather than human gold. No gold/qrels/label/expected-answer/supporting-evidence mutation, retrieval metric, answer metric, citation metric, DB write, production change, prompt/scorer tuning, or promotion was performed.
<!-- official_answer_citation_agentic_loop_run_v3_7_2_local_llm_natural_silver_query_regeneration:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_7_0_source_registry_materialization:progress-entry:start -->
- v3_7_0 source registry materialization (`official_answer_citation_agentic_loop_run_v3_7_0_source_registry_materialization`) materializes 136280 non-production SourceAtoms from existing source data with TEXT=135608, PDF=329, XLSX=343. No production DB, DB write/migration, vector index build, prompt/scorer tuning, gold/qrels/label/expected-answer/supporting-evidence mutation, retrieval metric, answer metric, or citation metric was performed. outcome=SOURCE_REGISTRY_MATERIALIZED_READY; next_allowed_phase=v3_7_1_all_source_citable_nonprod_index_build; no-vector hydration=true; no-vector citation render=true; snapshot_only=3; retrieval_only_uncanonicalized=0; official overlap=29 protected regression rows; vector_metadata_used_as_canonical_citation_source=false.
<!-- official_answer_citation_agentic_loop_run_v3_7_0_source_registry_materialization:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_7_1_all_source_citable_nonprod_index_build:progress-entry:start -->
- v3_7_1 all-source citable non-production index build (`official_answer_citation_agentic_loop_run_v3_7_1_all_source_citable_nonprod_index_build`) builds `ai/eval/indexes/rag-data-all-source-citable-nonprod-v1` from SourceAtom-backed SearchViews only: search_views=136280, TEXT=135608, PDF=329, XLSX=343, snapshot_only=3, official overlap=29 protected regression rows. outcome=ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILT; next_allowed_phase=v3_7_2_source_registry_backed_retrieval_smoke; no-vector hydration=true; no-vector citation render=true; vector_metadata_used_as_canonical_citation_source=false; faiss_gpu_used=false. This is diagnostic-only non-production indexing, not retrieval/answer/citation metric computation, not a hybrid baseline, not prompt/scorer tuning, not promotion, and not gold/qrels/label/expected-answer/supporting-evidence mutation.
<!-- official_answer_citation_agentic_loop_run_v3_7_1_all_source_citable_nonprod_index_build:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_7_2_source_registry_backed_retrieval_smoke_report:progress-entry:start -->
- v3_7_2 source registry-backed retrieval smoke report (`official_answer_citation_agentic_loop_run_v3_7_2_source_registry_backed_retrieval_smoke_report`) fixes the measurement contract to SearchView -> SourceAtom -> EvidenceBundle -> Citation render and reports contract survival by track without answer-quality scoring. Primary routing mode=query_source_family_routed_for_structured_tracks; routed source families=["PDF","XLSX"]; TEXT: queries=356, top-k returned=1780, same-track@k=356, target@k=20, hydration=1780, evidence render=1780, citation render=1780, top failure=track_mismatch; PDF: queries=329, top-k returned=1645, same-track@k=329, target@k=266, hydration=1645, evidence render=1645, citation render=1645, top failure=snapshot_only; XLSX: queries=344, top-k returned=1720, same-track@k=344, target@k=34, hydration=1720, evidence render=1720, citation render=1720, top failure=none. Mixed all-source FAISS top-k is retained only as baseline diagnostic: PDF mixed same-track@k=9, off-track returned=1634, cross-family TEXT dominance=328; XLSX mixed same-track@k=30, off-track returned=1690, cross-family TEXT dominance=344. The official/gold query surfaces are sealed no-regression checks only; silver diagnostic failure distribution is coverage/failure-discovery only. At this smoke step, Promotion readiness remains closed, comparable live measurement remained deferred, and no prompt/scorer/renderer/index/source-registry/gold/qrels/label/expected-answer/supporting-evidence mutation was performed.
<!-- official_answer_citation_agentic_loop_run_v3_7_2_source_registry_backed_retrieval_smoke_report:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_comparable_live_measurement:progress-entry:start -->
- v3 comparable live measurement rerun (`official_answer_citation_agentic_loop_run_v3_comparable_live_measurement`) was replayed after the v3_7_2 structured target-hit rerank using local `gemma4-e2b-local` through llama.cpp and the same 29-row official denominator. outcome=COMPARABLE_LIVE_MEASUREMENT_V3_COMPLETED; PASS=27/29; PDF=4/4 and XLSX=19/19 were retained by deterministic source-bound structured adapters; TEXT=4/6 used real LLM synthesis, with `text_namu_v2_0017` and `text_namu_v2_0077` remaining PARTIAL_OR_UNSUPPORTED. `baseline_comparison_is_model_quality_comparable=true`, `real_llm_backend_used=true`, `source_bound_index_used=true`; promotion_evidence=false, promotion_gate_auto_run=false, threshold_tuning=false, winner_selection=false, and no prompt/gold/qrels/label/expected-answer/supporting-evidence mutation was performed.
<!-- official_answer_citation_agentic_loop_run_v3_comparable_live_measurement:progress-entry:end -->












<!-- official_answer_citation_agentic_loop_run_v3_8_file_grounded_retrieval_eval:progress-entry:start -->
- v3_8 file-grounded retrieval eval (`official_answer_citation_agentic_loop_run_v3_8_file_grounded_retrieval_eval`) computes XLSX/PDF retrieval/evidence metrics before answer generation from v3_7_2 SourceAtom-hydrated top-k rows. XLSX queries=344, workbook_hit@5=317/344; PDF queries=329, page_hit@5=266/329. No XLSX/PDF collapsed headline score, answer metric, prompt/scorer tuning, gold/qrels/label/expected-answer/supporting-evidence mutation, index mutation, DB write, or promotion evidence was produced; FAISS/vector search remains candidate generation only and citation truth remains SourceAtom/source-registry hydrated.
<!-- official_answer_citation_agentic_loop_run_v3_8_file_grounded_retrieval_eval:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_8_1_evidence_selector_v1:progress-entry:start -->
- v3_8_1 evidence selector (`official_answer_citation_agentic_loop_run_v3_8_1_evidence_selector_v1`) freezes deterministic max-3 citation-capable evidence candidate artifacts over the v3_8/v3_7_2 PDF/XLSX top-k surface before answer generation. XLSX queries=344, selector_target_hit@3=29/344, selector_file_hit@3=315/344; PDF queries=329, selector_target_hit@3=251/329, selector_file_hit@3=268/329. target SourceAtom ids are used for selector metrics only, not candidate ordering; selector_file_hit now compares against the registry target identity surface, but it remains diagnostic-only and not production file-resolution evidence. No answer generation, XLSX/PDF collapsed headline score, prompt/scorer tuning, gold/qrels/label/expected-answer/supporting-evidence mutation, index mutation, DB write, or promotion evidence was produced.
<!-- official_answer_citation_agentic_loop_run_v3_8_1_evidence_selector_v1:progress-entry:end -->

<!-- official_answer_citation_agentic_loop_run_v3_8_2_oracle_free_file_resolve:progress-entry:start -->
- v3_8_2 oracle-free file resolve (`official_answer_citation_agentic_loop_run_v3_8_2_oracle_free_file_resolve`) computes ranked source_file/document candidates before scoped retrieval or answer generation, using query/source metadata, SourceAtom/source-registry hydration, SearchView/index candidate metadata, literal file mentions, and source-family intent only. XLSX queries=344, file_resolve@1=136/344, abstain=44/344; PDF queries=329, file_resolve@1=65/329, abstain=182/329. Gold/target SourceAtom ids and manifest targets are metrics-only, not resolver inputs; wrong-file low-confidence cases abstain/disambiguate instead of forcing a file. No scoped FAISS answer route, answer generation, XLSX/PDF collapsed headline score, prompt/scorer tuning, gold/qrels/label/expected-answer/supporting-evidence mutation, index mutation, DB write, or promotion evidence was produced.
<!-- official_answer_citation_agentic_loop_run_v3_8_2_oracle_free_file_resolve:progress-entry:end -->




<!-- portfolio_ready_freeze_v1:progress-entry:start -->
- Portfolio-ready final artifact freeze (`portfolio_ready_freeze_v1`) closes this pass as README/progress/status hygiene only. Root README now carries the portfolio overview, source-first contract, supported source families, minimal pytest demo path, and links to the compact progress/measurement/eval surfaces. The v3 comparable live diagnostic result remains PASS=27/29 with PDF=4/4, XLSX=19/19, TEXT=4/6, and the v3_4_3 exact-evidence retrieval smoke remains a 28-query small-sample regression guard only, not representative product performance. No XLSX/PDF resolver performance work, answer generation, prompt/scorer tuning, production mutation, official denominator mutation, gold/qrels/label/expected-answer/supporting-evidence mutation, promotion, threshold tuning, winner selection, or Lane A/B/C score collapse was performed. Post-freeze backlog remains XLSX bounded range/cell locator improvement, PDF file identity resolver improvement, PDF bbox/OCR trust policy after file identity stabilizes, optional silver live-generation experiment, and an official representative benchmark only after user-approved labels/qrels/denominator policy.
<!-- portfolio_ready_freeze_v1:progress-entry:end -->

<!-- portfolio_repo_cleanup_20260522:progress-entry:start -->
- Portfolio repository cleanup (`portfolio_repo_cleanup_20260522`) externalized local runtime payloads, the Namu v4 structured combined corpus payload, legacy root-level PDF candidate index files, and legacy root-level PDF diagnostic report JSON files to a redacted external runtime archive. Python/Maven cache directories were deleted where Windows permissions allowed. The current `ai/eval/reports/rag-ingestion/`, `ai/eval/source_registry/`, and `ai/eval/indexes/` generated evidence remains local-only because the current pytest profiles read those paths directly. This cleanup made no metric, resolver, gold/qrels/label/expected-answer/supporting-evidence, production index, threshold, winner-selection, promotion, or answer-generation changes.
<!-- portfolio_repo_cleanup_20260522:progress-entry:end -->

<!-- portfolio_readme_nexon_contact_surface_cleanup_20260522:progress-entry:start -->
- Portfolio README contact-surface cleanup (`portfolio_readme_nexon_contact_surface_cleanup_20260522`) reorganized root `README.md` and `ai/eval/README.md` around a reviewer-facing PDF/XLSX/TEXT sample surface: project summary, source-first `SearchView -> SourceAtom -> EvidenceBundle -> Citation render` contract, portfolio-facing query/evidence/response table, diagnostic status, local verification path, and next-work guardrails. Raw PDF text_block / TEXT chunk locator samples were moved into a diagnostic section of `ai/eval/README.md` and kept out of the portfolio-facing table. No metric recomputation, answer generation, local LLM call, gold/qrels/label/expected-answer/supporting-evidence mutation, official denominator mutation, production mutation, promotion evidence, threshold tuning, winner selection, or Lane A/B/C collapse was performed. Verification: Markdown link/table checks passed; `python -X utf8 -m pytest ai/tests --rag-current -q` passed with 325 passed / 8 warnings after restoring the required lowercase `production promotion` guardrail wording; `python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q` passed with 325 passed / 8 warnings. Remaining post-freeze work stays XLSX range/cell locator improvement, PDF file identity confidence, PDF bbox/OCR trust policy, optional diagnostic-only silver live-generation, and representative benchmark policy only after user-approved labels/qrels/denominator decisions.
<!-- portfolio_readme_nexon_contact_surface_cleanup_20260522:progress-entry:end -->







<!-- official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic:progress-entry:start -->
- v3_8_3 XLSX scoped cell resolve (`official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic`) computes sheet/table-range/cell-value diagnostics after the v3_8_2 oracle-free workbook/document gate and before answer generation. XLSX queries=344, sheet_resolve@1=249/344, table_or_range_resolve@1=22/344, cell_or_value_resolve@1=19/344, abstain=44/344. Target SourceAtom/manifest locator data is metrics-only, not resolver input; PDF rows are excluded instead of collapsed with XLSX. No scoped answer route, answer generation, prompt/scorer tuning, gold/qrels/label/expected-answer/supporting-evidence mutation, index mutation, DB write, or promotion evidence was produced.
<!-- official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic:progress-entry:end -->




<!-- official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic:progress-entry:start -->
- v3_9_1 XLSX SourceAtom table-axis + PDF file-identity diagnostic (`official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic`) keeps PDF and XLSX metrics separate and leaves TEXT comparison-only. XLSX table_or_range@3=29/344, cell/value@3=26/344, signal-empty rank1=257/300; query-fidelity validation included=118/170. PDF file_resolve@1=66/329, @3=129/329, abstain=182/329. The run is diagnostic-only: official_metric_input_rows=0, future scored adapter disabled, no fine-tuning, no gold/qrels/label/expected-answer/supporting-evidence mutation, no DB write, and no promotion/threshold/winner surface.
<!-- official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic:progress-entry:end -->

- Official first-run baseline is `status=BLOCKED_OR_PARTIAL`,
  `status_detail=SCORED_BASELINE_PARTIAL`,
  `official_metric_execution_started=true`, `official_scoring_attempt_count=29`,
  `scored_count=29`, PASS=8, CITATION_UNSUPPORTED=11,
  PARTIAL_OR_UNSUPPORTED=10.
- XLSX runtime candidate is report-only and deterministic: PASS=26/29,
  XLSX=19/19, local LLM/GPU used=false.
- PDF table/value candidate now has official-compatible source-bound locators
  for `gq_auto_010`, `gq_auto_030`, and `gq_pdf_section_question_001`;
  report-only, no promotion, PASS=29/29, and it does not overwrite the
  official first-run baseline. expected answers/supporting evidence are for
  scoring/audit only.
- `official_answer_citation_agentic_loop_run_v1` is a separate diagnostic
  live-generation artifact family. `ai/eval/indexes/rag-data` was rebuilt in
  WSL2 with CUDA FAISS; `faiss_gpu_used=true`; result rows=29, scored_count=29,
  PASS=1, promotion_evidence=false. PASS=1/29 is
  `diagnostic_live_generation_fixture_all_index_not_official_denominator_representative`,
  with CORPUS_COVERAGE_MISS=6, STRUCTURED_ADAPTER_NOT_WIRED=22,
  SCORER_COMPATIBILITY_MISMATCH=1, `llm_backend=noop`,
  chunk-only citation locators, not canonical SearchUnit payloads, and
  `baseline_comparison_is_model_quality_comparable=false`.
- source-bound official-denominator SearchUnit export/build is now unblocked
  and load-checked at `ai/eval/indexes/rag-data-official-denominator-v1`.
  The readiness state is `BUILD_READY_LOAD_CHECK_PASSED`,
  blocked_query_ids=[], target_index_built=true, load_check_passed=true,
  rerun_allowed=true, and the built index contains 29/29 official rows
  across PDF=4, TEXT=6, XLSX=19.
- SearchUnit citation payload wiring is implemented in the live runner, and
  XLSX/PDF deterministic adapter opt-in wiring is implemented for retrieved
  source-bound SearchUnits. These remain report-only/candidate wiring changes,
  not promoted result surfaces.

### Answer/Citation Closure

- v3 comparable live measurement remains diagnostic-only: Lane A/B/C PASS are
  `24/29`, `27/29`, `27/29` after the v3_2_7 closure path; Lane A is replay,
  B/C are live LLM surfaces.
- `official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit`
  records that the active queue cleared while all-track residual inventory
  remains for `text_namu_v2_0012`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0077`, and `text_namu_v2_0084`.
  It points to `gold_policy_review_packet_preparation`; `pdfwin_b1c6527f848018640ad5ed231877c662`
  remains the PDF expansion proof. This is diagnostic-only, not promotion
  evidence, no official nDCG/MRR/Hit@K was computed, and Lane A/B/C not collapsed.
- `official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation`
  is the human gold-policy packet-preparation run for the same five TEXT rows.
  The allowed decision options are `keep_current_strict_reference_boundary`,
  `approve_scorer_or_renderer_review_without_gold_mutation`, and
  `revise_gold_or_label_policy`. The active implementation queue remains empty;
  diagnostic-only, not promotion evidence, no official nDCG/MRR/Hit@K, and no
  behavior, gold, label, production, denominator, retrieval, scorer, renderer,
  silver, or promotion mutation occurred.
  In short: no behavior, gold, label, production, denominator, retrieval, scorer, renderer, silver, or promotion mutation.
- `official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement`
  applied a user-approved gold policy override application: five TEXT rows
  changed by user decision (`text_namu_v2_0012`, `text_namu_v2_0014`,
  `text_namu_v2_0017`, `text_namu_v2_0077`, `text_namu_v2_0084`).
  The run records five TEXT rows changed by user decision.
  `behavior_change_made=false`; renderer/scorer/retrieval/production/silver/promotion
  behavior changed: none. The scoring-only remeasurement keeps
  In short: renderer/scorer/retrieval/production/silver/promotion behavior changed: none.
  promotion_evidence=false, no official nDCG/MRR/Hit@K, and Lane A/B/C not collapsed.
- `official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation`
  classified six query ids / 12 failing lane items. `text_namu_v2_0012` and
  `text_namu_v2_0077` are Lane A-only frozen replay residuals; `v3_2_4_pdf_context_provenance`
  gates `gq_auto_010`; `v3_2_6_text_prompt_span_rule` is limited to live TEXT
  B/C rows. It produced no per-run
  Markdown, results JSONL, failure attribution, audit payload, official ranking metric,
  or collapsed Lane A/B/C score.
- `official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic`
  found `gq_auto_010` was open because
  `open_because_v3_1_6_expansion_not_wired_into_v3_2_measurement`: current B/C
  cited `7bf516bf-2a17-4303-86d8-3cffaa04846e`, while
  `pdfwin_b1c6527f848018640ad5ed231877c662` held the numeric span.
  `retrieval_context_rerun=false` and
  `retrieval_context_source_run_id=official_answer_citation_agentic_loop_run_v3_comparable_live_measurement`;
  v3_2_5 is
  therefore needed as a measurement-source/context-assembly overlay, not an
  index/export rebuild. No live generation, prompt, renderer, scorer, retrieval,
  index/export, gold, label, denominator, silver, production, or promotion changed.
- `official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix`
  reached `official_answer_citation_v3_2_5_gq_auto_010_pdf_context_reconciliation_fixed`
  and reuses the existing v3_1_6 safe PDF
  paragraph/window sidecar for `gq_auto_010` only. The `pdfwin_b1c6527f848018640ad5ed231877c662`
  overlay changed Lane A/B/C PASS from v3_2_2 `24/29`, `26/29`, `25/29` to
  `24/29`, `27/29`, `26/29`; PASS from v3_2_2 `24/29`, `26/29`, `25/29` to `24/29`, `27/29`, `26/29`;
  non-target unexpected deltas are `0`. No
  index/export rebuild, gold, expected answer, supporting evidence, label,
  denominator, silver, production, promotion, threshold tuning, winner
  selection, official retrieval ranking metric, or collapsed Lane A/B/C score changed.
- `official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement`
  reached `official_answer_citation_v3_2_6_text_prompt_span_rule_remeasured`.
  It applied a target-scoped TEXT prompt/span rule; `text_namu_v2_0014` Lane C
  changed from `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`; `text_namu_v2_0014` Lane C changed from `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`; `text_namu_v2_0017` and
  `text_namu_v2_0084` remain diagnostic-only prompt/span residuals; unexpected
  deltas are `0`.
  Residual status: `text_namu_v2_0017` and `text_namu_v2_0084` remain diagnostic-only prompt/span residuals.
- `official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup`
  records `official_answer_citation_v3_2_7_post_fix_sequence_closed`.
  v3_2_5 and v3_2_6 are the only implementation-changing post-v3_2_2 phases;
  Lane A/B/C are now `24/29`, `27/29`, `27/29`, and no next implementation
  phase is opened. Status remains: no next implementation phase is opened.
- `official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit`
  is source-of-truth audit only and records
  `official_answer_citation_v3_3_0_source_of_truth_audit_completed`. Lane A/B/C
  remain `24/29`, `27/29`, `27/29`, and the active implementation queue remains empty.
  Audit status: Lane A/B/C remain `24/29`, `27/29`, `27/29`.

### Retrieval And Qrels State

- v3_3_2 retrieval-label design packet
  `official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet`
  records that the 29-row set is the official answer/citation denominator, not
  yet an official retrieval qrels denominator. It is not yet an official retrieval qrels denominator.
  Official nDCG, MRR, Hit@K, and
  any collapsed Lane A/B/C score remain blocked until relevance/answerability
  labels and evidence policy are settled.
  The same blocker remains: official nDCG, MRR, Hit@K, and any collapsed Lane A/B/C score remain blocked.
- v3_4_0 official retrieval metric contract
  `official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json`
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_qrels_schema.json`.
  The contract defines denominator policy options A/B/C. Official nDCG, MRR,
  Hit@K, and any collapsed Lane A/B/C score remain blocked. Official nDCG, MRR, Hit@K, and any collapsed Lane A/B/C score remain blocked;
  Legacy XLSX
  retrieval CSV and silver retrieval-evidence files are prohibited as current
  official qrels.
  Legacy XLSX retrieval CSV and silver retrieval-evidence files are prohibited as current official qrels.
- v3_4_1 marker
  `official_retrieval_qrels_candidate_packet_v3_4_1_ready_for_human_review`;
  run `official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.jsonl`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_qrels_candidates.csv`,
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_summary.json`.
  It contains 219 rows across 29 query_ids: PDF=22, TEXT=24, XLSX=173, with
  `relevance_label=pending`, `answerability_label=pending`,
  `label_status=pending_user_review`, `generation_source=false`, and
  `promotion_evidence=false`. No official Hit@K, MRR, nDCG was computed.
- v3_4_1a marker `official_retrieval_qrels_human_minimal_review_packet_v3_4_1a_ready`;
  run `official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_policy_approval.json`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_human_query_group_review.csv`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_ambiguous_candidate_review.csv`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_qrels_auto_label_plan.json`,
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_summary.json`.
  Review burden is reduced from 219 raw candidate rows to 29 query-group rows plus 30 candidate-unit ambiguity rows;
  estimated 59 review rows total. Expected answer/supporting
  evidence fields are omitted; Codex recommendations are not final labels;
  auto-labeling is not applied; official Hit@K, MRR, nDCG remain blocked.
  Policy reminder: Expected answer/supporting evidence fields are omitted.
- v3_4_2 marker `official_exact_evidence_retrieval_qrels_v3_4_2_ready_metrics_deferred`;
  run `official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_official_retrieval_qrels.jsonl`,
  `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_coverage_summary.json`,
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_qrels_exclusion_ledger.jsonl`.
  Included query groups=28; excluded query groups=1 (`gq_auto_010`,
  `standalone_query_missing_year`). The exclusion is not a retrieval miss,
  failure, negative, or unanswerable row. Official qrels unit rows=140;
  qrels positives=28; the metric family is official exact-evidence retrieval
  metrics with scope `source_bound_search_unit_exact_answer_evidence_smoke`.
  This is a small official exact-evidence retrieval smoke benchmark for
  metric-pipeline validation and regression guarding, not statistically
  representative product performance. README headline performance claims from this 28-query set are blocked.
  README headline performance claims remain blocked; future nDCG must be binary exact-evidence nDCG@K unless full
  graded relevance labels are created; v3_4_2 did not compute Hit@K, MRR, nDCG.
  v3_4_3 official exact-evidence Hit@K/MRR/binary nDCG computation is ready.
- v3_4_3 marker `official_exact_evidence_retrieval_smoke_metrics_v3_4_3_computed_small_sample`;
  run `official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation`
  wrote `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_metrics.json`
  and `ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_per_query.jsonl`.
  Primary ranking surface is Lane B `live_llm_retrieval_topk` only. Included
  query count=28; excluded query count=1 (`gq_auto_010`); PDF=3, TEXT=6,
  XLSX=19. Micro metrics: Hit@1=27/28, Hit@3=28/28, Hit@5=28/28,
  MRR@5=27.5/28, binary exact-evidence nDCG@5=0.9868189197704093.
  `small_sample_warning=true`, `readme_headline_allowed=false`,
  `regression_guard_allowed=true`; one query changes the score by about 3.57
  percentage points. No graded nDCG, threshold tuning, winner selection, or
  README headline claim was made.
- v3_4_4 marker `readme_retrieval_smoke_card_v3_4_4_ready_silver_generation_blocked`;
  v3_4_4 README retrieval-smoke/silver-readiness artifacts
  `official_answer_citation_agentic_loop_run_v3_4_4_readme_retrieval_smoke_and_silver_readiness_artifacts`
  created a compact README metric card JSON, README insertion snippet, and
  silver-readiness summary from the verified v3_4_3 Lane B exact-evidence
  smoke metrics. README integration is snippet-only (`pending_manual_integration=true`):
  `readme_headline_allowed=false`, `regression_guard_allowed=true`; the card
  remains a small-sample regression guard, not statistically representative
  product performance. Silver generation remains blocked: TEXT=0, PDF=3,
  XLSX=4, total=7, below the 100-row pilot and 1000-row target;
  official-denominator SearchUnits remain excluded from dev/holdout silver,
  and no silver rows were generated.

### Source Material And Diagnostic Silver

- v3_5_0 strict non-official source-bound capacity expansion
  `official_answer_citation_agentic_loop_run_v3_5_0_strict_non_official_source_bound_capacity_expansion`
  has marker `strict_non_official_source_bound_capacity_expansion_v3_5_0_pilot_ready`:
  previous strict inventory remains TEXT=0, PDF=3, XLSX=4, total=7; new
  manifest-ready source candidates are TEXT=350, PDF=3, XLSX=4, total=357;
  pilot threshold is met; 1000-row target is not met; silver generation remains
  blocked; recommended next phase is `v3_5_1_pilot_silver_source_manifest_freeze`.
  No questions, expected answers, supporting evidence, labels, qrels, silver
  JSONL rows, prompt, retrieval, renderer, scorer, index/export, production,
  threshold tuning, winner selection, promotion evidence, README representative
  claim, or Lane A/B/C collapsed score changed.
- v3_5_1 pilot source manifest freeze
  (`official_answer_citation_agentic_loop_run_v3_5_1_pilot_silver_source_manifest_freeze`)
  freezes TEXT=350, PDF=3, XLSX=4, total=357 source-only rows; balanced pilot
  threshold is not met; target_threshold_met=false.
- v3_5_2 XLSX source-value manifest repair
  (`official_answer_citation_agentic_loop_run_v3_5_2_xlsx_source_value_manifest_repair_and_acquisition`)
  reconstructs locator-complete XLSX rows from actual workbooks and freezes
  321 manifest-ready overlay rows toward the XLSX target. Combined source
  counts are TEXT=350, PDF=3, XLSX=325, total=678. No query or
  expected_answer_text was used as source material.
- v3_5_3 PDF page/bbox source-text manifest repair
  (`official_answer_citation_agentic_loop_run_v3_5_3_pdf_page_bbox_source_text_manifest_repair_and_acquisition`)
  extracts 322 PDF source rows from approved existing PDF source documents.
  Final source counts are TEXT=350, PDF=325, XLSX=325, total=1000;
  balanced_pilot_threshold_met=true, target_threshold_met=true,
  silver_generation_allowed=false.
- v3_5_4 balanced source-only manifest freeze
  (`official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze`)
  freezes TEXT=350, PDF=325, XLSX=325, total=1000 source-only rows. sample
  packet counts are TEXT=25, PDF=25, XLSX=25; preferred_mix_met=true,
  target_threshold_met=true, silver_generation_allowed=false; next phase is
  v3_5_5_balanced_source_manifest_quality_audit.
- v3_5_5 balanced source-manifest quality audit
  (`official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit`)
  validates TEXT=350, PDF=325, XLSX=325, total=1000 frozen v3_5_4 source-only
  rows. duplicate hash repetitions are 17 groups/57 rows;
  critical_repair_required_count=0, recommended_repair_queue_count=0,
  silver_generation_allowed=false.
- v3_6_0 low-touch weak/noisy silver policy application
  (`official_answer_citation_agentic_loop_run_v3_6_0_low_touch_noisy_silver_policy_application`)
  records user_policy_decision_applied=true, low_touch_human_review_required=false,
  generated silver rows=0.
- v3_6_1 balanced weak/noisy silver candidate generation
  (`official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation`)
  creates 1000 diagnostic weak/noisy candidate rows: TEXT=350, PDF=325,
  XLSX=325, total=1000; blocked rows=0. This is not gold, not official
  denominator/qrels, not promotion evidence.
- v3_6_2 weak/noisy silver candidate sanity eval
  (`official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval`)
  has candidate_sanity_passed=true; bucket counts are core=665, review-only=335,
  quarantine=0, blocked=0; hash contract=normalized question sha256;
  v3_6_3 diagnostic weak/noisy silver manifest freeze is allowed=true.
- v3_6_3 diagnostic weak/noisy silver manifest freeze
  (`official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze`)
  freezes 1000 diagnostic rows: core=665, review-only=335, quarantine=0.
  official proximity rows remain review-only=3; v3_6_4 diagnostic-only
  weak/noisy silver metric is allowed=true.
- v3_6_4 diagnostic-only weak/noisy silver metric
  (`official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric`)
  measures core_only=665, review_only_challenge=335, all_diagnostic=1000.
  live generation coverage=0/1000 and answer/citation proxy metrics fail
  closed; core_only is the main interpretable diagnostic bucket.
- v3_6_5 rough failure-bucket triage
  (`official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage`)
  keeps v3_6_4 diagnostic-only: no live silver generation, no DB writes, no
  index/export rebuild, and DB-derived generation/gold/qrels remain blocked.
- v3_6_6 diagnostic reference sidecar and runtime surface probe
  (`official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe`)
  builds a diagnostic reference sidecar: all=1000, core=665, review-only=335,
  quarantine=0; core smoke strict JSON answers returned=30. Review-only remains
  stress-only, and DB-derived generation/gold/qrels remain blocked.
- v3_6_7 runtime stability probe for core-only
  (`official_answer_citation_agentic_loop_run_v3_6_7_runtime_stability_probe_for_core_only`)
  reruns the inherited core smoke sample as diagnostic-only evidence:
  attempted=30, strict JSON answers=30, citation surface valid=0. This is not
  gold/qrels/official denominator/labels, not README performance evidence, and
  no prompt/retrieval/scorer/renderer/index/export/DB mutation was performed.
- v3_6_8 non-production all-source index materialization
  (`official_answer_citation_agentic_loop_run_v3_6_8_nonprod_all_source_index_materialization_and_canonical_payload_wiring`)
  builds `ai/eval/indexes/rag-data-all-source-nonprod-v1` with accepted source
  units={"PDF":329,"TEXT":135608,"XLSX":343,"total":136280}. Load-check
  passed=true; canonical payload families=["PDF","TEXT","XLSX"]; no-LLM render
  valid count=50; outcome=ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED;
  next_allowed_phase=v3_6_9_core_only_live_diagnostic_metric; blocking buckets=[].
  This is diagnostic-only non-production indexing, not a promotion run, not an
  official representative metric, and not README performance evidence.
- v3_6_8 source-registry-first evidence bundle architecture audit
  (`official_answer_citation_agentic_loop_run_v3_6_8_source_registry_first_evidence_bundle_architecture_audit`)
  stops the all-source index expansion path. Search indexes remain candidate
  generators only; outcome=SEARCHUNIT_OVERLOADED_BLOCKER;
  next_allowed_phase=SearchUnit/SearchView/SourceAtom refactor;
  blocking buckets=["SEARCHUNIT_OVERLOADED_BLOCKER"]; SearchUnit is overloaded
  because it acts as retrieval unit, source atom, citation unit, evidence unit,
  metric/qrels unit, and LLM context unit.
- v3_6_9 SearchUnit/SearchView/SourceAtom refactor
  (`official_answer_citation_agentic_loop_run_v3_6_9_searchunit_searchview_sourceatom_refactor`)
  introduces a durable source-first Python contract where SearchViews are
  retrieval candidates and EvidenceBundles hydrate through SourceAtoms before
  citation rendering. outcome=SEARCHUNIT_SEARCHVIEW_SOURCEATOM_CONTRACT_READY;
  next_allowed_phase=source registry materialization; next blocking work=
  ["SOURCE_REGISTRY_MATERIALIZATION_REQUIRED"]; no-vector render count=3;
  vector_payload_used_as_evidence_truth=false. No production DB, DB
  write/migration, index/export rebuild, prompt/scorer tuning,
  gold/qrels/label/expected-answer/supporting-evidence mutation, or official
  metric scoring was performed.

## Track Board

| Track | Current state | Current metric/evidence | Next action |
|---|---|---|---|
| Source architecture | v3_8_3 now uses persisted v3_8_2 workbook/document gates for XLSX scoped sheet/range/cell diagnostics plus miss taxonomy | XLSX-only metrics are reported separately; target SourceAtom/manifest data is metrics-only; citation truth remains source-registry hydrated, not vector metadata | Use the taxonomy to improve scoped evidence/cell resolution, then open PDF page/span resolve only after the gate contract is stable. |
| `text_namu_v2_1` | v3_2_7 closes the post-fix implementation queue; `text_namu_v2_0017` and `text_namu_v2_0084` remain diagnostic-only | Lane A/B/C: `24/29`, `27/29`, `27/29`; `text_namu_v2_0012` and `text_namu_v2_0077` are frozen Lane A replay residuals | Do not reopen gold policy automatically. |
| `xlsx_business_structured` | v3_8_3 scoped cell diagnostic is computed after the v3_8_2 workbook/document gate with legacy rows marked dev-only and a workbook-disjoint validation split | sheet_resolve@1 `249/344` (baseline `248/344`); validation sheet@1 `112/170` (baseline `111/170`); table_or_range_resolve@1 `22/344`; cell_or_value_resolve@1 `19/344`; abstain `44/344`; top miss bucket table_or_range_miss_after_sheet_hit `219`; oracle-free input violations `0`; official_metric_input_rows `0` | Keep range/cell work diagnostic-only; do not count dev-only gains without validation evidence. |
| `pdf_business_ocr_mm` | v3_8_2 oracle-free resolver is computed before scoped retrieval | file_resolve@1 `65/329`; file_resolve@3 `129/329`; abstain `182/329`; wrong-file block `57/329`; upstream v3_8 page_hit@5 `266/329` | Improve PDF file identity confidence, then defer exact bbox overlap and OCR trust policy to a later slice. |
| Report artifacts | Human narrative stays in three rolling docs; machine evidence stays compact | `status.jsonl` plus compact current v3_6_9 and later diagnostic artifacts required by the current RAG profile | Avoid per-run Markdown and full forensic payloads unless the run contract requires them. |

## 2026-05-22 - PDF/XLSX Performance Checkpoint

Scope: non-gold, synthetic ingestion/indexing benchmark plus bounded hot-path
fixes. No local LLM, DB, GPU, production index, official denominator, gold,
qrels, label, expected-answer, or supporting-evidence surface was used or
mutated.

Commands and artifacts:

- Baseline:
  `python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label baseline_before_optimization --warmups 1 --iterations 3 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_baseline_before_optimization.json`
- Final comparable:
  `python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label final_after_pdf_probe_optimization_comparable_3x --warmups 1 --iterations 3 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_final_after_pdf_probe_optimization_comparable_3x.json`
- Final stability check:
  `python -X utf8 ai\scripts\rag_pdf_xlsx_perf_benchmark.py --label final_after_optimization --warmups 1 --iterations 5 --output ai\eval\reports\rag-ingestion\perf\pdf_xlsx_perf_final_after_optimization.json`

Measured median latency:

| Case | Baseline | Final comparable | Delta | Note |
|---|---:|---:|---:|---|
| PDF native text, no supported tables | 27.698 ms | 22.932 ms | -17.2% | Page-level table marker prefilter avoids the narrow table parser on ordinary pages. |
| PDF OCR fallback blank pages | 61.102 ms | 62.064 ms | +1.6% | Comparable run was noise/slightly slower; 5x stability run was 59.504 ms (-2.6%). Rendering/PNG encoding dominates this synthetic case. |
| XLSX large merged range | 20,191.989 ms | 165.670 ms | -99.2% | Dangerous merged-range metadata uses bounded OOXML scan instead of full openpyxl style binding. |
| SearchUnit duplicate skip | 114.690 ms | 79.897 ms | -30.3% | Existing chunks are keyed by stable index id before duplicate checks. |

Checkpoint log:

| Checkpoint | Files changed | Hypothesis | Validation | Result | Remaining risk |
|---|---|---|---|---|---|
| Benchmark harness | `ai/scripts/rag_pdf_xlsx_perf_benchmark.py` | Existing repo had no focused PDF/XLSX parse/index performance benchmark. | Baseline command above. | Reproducible synthetic JSON artifacts recorded under local ignored `ai/eval/reports/rag-ingestion/perf/`. | Synthetic results are regression evidence, not representative production performance. |
| PDF parser/OCR path | `ai/app/capabilities/pdf/service.py`, `ai/tests/test_rag_pdf_answer_citation_table_value_candidate_v1.py` | The deterministic PDF table parser is narrow and can be skipped when page text lacks its supported markers; OCR fallback should not reopen the PDF per page. | Targeted PDF tests; benchmark final comparable. | PDF native synthetic path improved -17.2%; OCR handle reuse preserved behavior but measured benefit is small/noisy. | Real PaddleOCR scanned-PDF smoke still needs restored scanned PDFs/provider setup. |
| XLSX metadata/read bounds | `ai/app/capabilities/xlsx/service.py`, `ai/tests/test_rag_xlsx_answer_citation_runtime_precision_candidate_v1.py` | Full openpyxl metadata load explodes on large merged ranges; read and merged-cell maps should respect existing row/column safety bounds. | Targeted XLSX test; benchmark final comparable. | XLSX merged-range synthetic path improved -99.2%; peak tracemalloc fell from 348,611.6 KiB to 6,430.8 KiB. | OOXML fast path is only used for expensive merged ranges; non-dangerous workbooks keep the existing second pass. |
| Shared duplicate lookup | `ai/app/capabilities/rag/search_unit_indexing.py`, `ai/tests/test_rag_source_bound_official_denominator_index.py` | Duplicate skip was O(incoming docs x existing chunks). | Shared namespace/diagnostic metadata regression test; benchmark final comparable. | Synthetic duplicate skip improved -30.3% without dropping namespace, diagnostic-only, SourceAtom, or registry metadata. | FAISS full staged rewrite remains the next shared-indexing bottleneck when chunks actually change. |

## Current Verification Command

Windows/Python current env:

```powershell
python -X utf8 -m pytest ai/tests --rag-current -q
python -X utf8 -m pytest ai/tests -m "rag_current or rag_official_metric or rag_pdf_current" -q
```

Current verification: local results are recorded in this progress log. After
the v3_20/v3_21 shared-helper cleanup and report-ignore policy cleanup,
`python -X utf8 -m pytest ai/tests --rag-current -q` -> 480 passed, 0 skipped,
0 failed, 8 warnings.

Current test surface is intentionally compact after legacy test deletion:
`python -X utf8 -m pytest ai/tests --rag-current -q`; full `ai/tests`
  now mirrors the current profile and no longer carries broad/nightly legacy
  suites.

The pre-execution smoke report is a pre-execution artifact, so
`official_metric_execution_started=false` there is expected and must not be read
as the latest metric execution status.

## Current Source-Of-Truth Artifacts

Human-facing rolling docs:

- `docs/rag-ingestion-progress.md`
- `docs/rag-ingestion-measurements.md`
- `docs/rag-ingestion-triage.md`

Machine-readable official/status surfaces:

- `ai/eval/reports/rag-ingestion/status.jsonl`
- compact v3_6_9 and later diagnostic artifacts required by the current RAG
  profile, including v3_10-v3_15 root artifacts and v3_16-v3_21
  quality/runtime packet directories.
- `ai/eval/silver/answer_citation_silver_manifest_v1.json`
- `ai/eval/silver/answer_citation_silver_readiness_v1.json`

As of the 2026-05-21 report cleanup, `ai/eval/reports/` intentionally keeps
only `rag-ingestion/`, and that directory keeps `status.jsonl` plus compact
current v3_6_9 and later diagnostic artifacts required by the current RAG
profile. Older
`rag-ingestion` payloads, including the
official baseline/scorer/input/smoke/source-bound files and v3_1-v3_6_8
diagnostics, are consolidated under a redacted external runtime archive.
The former `ai/eval/reports/phase7/` and
`ai/eval/reports/legacy-baseline-final/` trees are also archived under the
same redacted external runtime archive family.
The previous 2026-05-19 external archive remains a compatibility fallback.
Repo-local archive payloads are externalized under a redacted external
workspace archive.

Per-run Markdown reports under `ai/eval/reports/rag-ingestion/` are no longer
the human-facing surface. The ongoing narrative stays in the three rolling docs
above.

## Guardrails

- `tuning_run_started=false`
- `promotion_evidence=false`
- `threshold_tuning=false`
- `winner_selection=false`
- `production_mutation=false`
- `denominator_mutation=false`
- Silver policy remains anti-overfit: silver is not gold, not official
  denominator, not promotion evidence, expected values are audit-only, and the
  official 29 query_ids are excluded from dev/holdout tuning silver.
- Current silver overlap with the official denominator remains
  `TEXT=0, XLSX=0, PDF=0`.
- The official-denominator source-bound index, build/load check, and canonical
  SearchUnit citation payload wiring are already available; 29/29 source-bound
  SearchUnits overlap the official denominator, but safe non-official
  source-bound source manifests are still missing, so silver generation stays
  closed until safe silver-source data coverage is settled.
- Expected answer and supporting evidence are not used for generation.
- Silver expected values are audit-only and silver cases must not be used as
  generation input.
- Official 29 query_ids are excluded from dev/holdout tuning silver.
- Gold CSVs, official denominator registry, human labels, production namespace,
  vector indexes, and immutable first-run baseline artifacts remain protected.
- v3 diagnostic lanes stay diagnostic-only. Lane B/C PASS counts are not
  promotion evidence, and Lane A/B/C must not be collapsed into a single
  official score.

## Next Recommended Steps

1. Use `v3_8_3_xlsx_scoped_cell_resolve_diagnostic` miss taxonomy to analyze
   XLSX range/cell misses without opening answer generation.
2. Keep v3_8/v3_8_1/v3_8_2/v3_8_3 diagnostic-only while adding bbox/range-overlap and
   hidden-negative policy only in a later bounded slice.
3. Keep the official answer/citation implementation queue closed unless a later
   user-owned policy decision reopens TEXT answerability/gold boundaries.
4. Do not create silver rows or change expected answers, supporting evidence,
   relevance labels, answerability labels, or gold policy unless explicitly
   requested.
5. Keep report output compact: necessary machine artifacts plus this rolling
   status page, not per-run Markdown report families.
6. Keep the compact `ai/tests` surface current; extend existing files for
   routine coverage and create a new test file only for a durable subsystem.

## Short History

| Date | Compact entry |
|---|---|
| 2026-05-16 | Historical first-run attempt was blocked with `SCORER_BACKEND_UNAVAILABLE`; active first-run artifacts were later regenerated and this state is superseded. |
| 2026-05-17 | Official first-run baseline scored 29/29 rows and remained partial: PASS=8, CITATION_UNSUPPORTED=11, PARTIAL_OR_UNSUPPORTED=10. |
| 2026-05-17 | XLSX runtime candidate reached PASS=26/29 and PDF table/value candidate reached PASS=29/29 as report-only deterministic candidates. |
| 2026-05-17 | Source-bound official-denominator index was built/load-checked for 29/29 rows, then v2 diagnostic scoring reached PASS=20/29 with schema mismatches fail-closed. |
| 2026-05-18 | v3_1-v3_1_6 moved from locator/renderer triage to the safe PDF paragraph/window expansion proof; active queue became empty. |
| 2026-05-19 | v3_1_9 through v3_3_2 settled user-approved TEXT gold-policy override, v3_2 closure, and retrieval-label design without opening official retrieval metrics. |
| 2026-05-19 | v3_4 created exact-evidence retrieval qrels and a small 28-query smoke metric, explicitly not representative product performance. |
| 2026-05-20 | v3_5-v3_6 built the balanced source-only manifest and diagnostic weak/noisy silver path, then stopped at source-first architecture separation. |
| 2026-05-20 | v3_6_8 and v3_6_9 proved all-source non-production indexing and a SearchUnit/SearchView/SourceAtom contract; source registry materialization is next. |
| 2026-05-21 | v3_7_2 superseded the inherited 1000 weak/noisy silver query surface with local LLM natural Korean queries while preserving diagnostic-only, non-promotion boundaries. |
| 2026-05-21 | v3_7_2 source registry-backed retrieval smoke separates top-k returned candidates from same-track@k, target@k, and contract survival; promotion readiness remains closed. |
| 2026-05-21 | v3_8 freezes PDF/XLSX file-grounded retrieval/evidence metrics before answer generation, with separate denominators and SourceAtom/source-registry citation truth. |
| 2026-05-21 | v3_8_1 freezes deterministic max-3 evidence selector artifacts before answer generation; selector_file_hit uses registry target identity for metrics only and remains diagnostic-only. |
| 2026-05-21 | v3_8_2 computes oracle-free source_file/document resolve metrics with separate PDF/XLSX denominators, abstain/wrong-file blocking, and no answer generation or promotion evidence. |
| 2026-05-21 | v3_8_3 computes XLSX scoped sheet/range/cell diagnostics and miss taxonomy from persisted v3_8_2 workbook gates without answer generation or promotion evidence. |
