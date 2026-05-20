from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"
STATUS_JSONL = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "status.jsonl"


def test_progress_doc_current_board_uses_latest_scored_baseline_not_backend_unavailable():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = text.split("## Short History", 1)[0]

    assert "official_denominator_source_bound_index_build_ready_load_checked" in current_text
    assert "official_metric_execution_started=true" in current_text
    assert "official_scoring_attempt_count=29" in current_text
    assert "PASS=8" in current_text
    assert "CITATION_UNSUPPORTED=11" in current_text
    assert "PARTIAL_OR_UNSUPPORTED=10" in current_text
    assert "XLSX runtime candidate" in current_text
    assert "XLSX=19/19" in current_text
    assert "PDF table/value candidate" in current_text
    assert "PASS=29/29" in current_text
    assert "official_answer_citation_agentic_loop_run_v1" in current_text
    assert "scored_count=29" in current_text
    assert "PASS=1" in current_text
    assert "faiss_gpu_used=true" in current_text
    assert "diagnostic_live_generation_fixture_all_index_not_official_denominator_representative" in current_text
    assert "baseline_comparison_is_model_quality_comparable=false" in current_text
    assert "llm_backend=noop" in current_text
    assert "chunk-only citation locators" in current_text
    assert "not canonical SearchUnit" in current_text
    assert "STRUCTURED_ADAPTER_NOT_WIRED=22" in current_text
    assert "eval/indexes/rag-data" in current_text
    assert "Human-facing rolling docs" in current_text
    assert "primary append-only\nhuman report file" in current_text
    assert "append the\nshort entry here instead of creating another report" in current_text
    assert "Per-run Markdown" in current_text
    assert "source-bound official-denominator SearchUnit export/build is now unblocked" in current_text
    assert "BUILD_READY_LOAD_CHECK_PASSED" in current_text
    assert "rerun_allowed=true" in current_text
    assert "29/29 official" in current_text
    assert "SearchUnit citation payload wiring is implemented" in current_text
    assert "XLSX/PDF deterministic adapter opt-in wiring is implemented" in current_text
    assert "report-only" in current_text
    assert "pytest ai/tests --rag-current -q" in current_text
    assert "full `ai/tests`\n  now mirrors the current profile" in current_text
    assert "broad/nightly legacy\n  suites" in current_text
    assert "status.jsonl" in current_text

    assert "SCORER_BACKEND_UNAVAILABLE" not in current_text
    assert "scorer/backend is unavailable" not in current_text
    assert "wire or start the official answer/citation scorer/backend" not in current_text
    assert "Wire or start the official answer/citation scorer/backend" not in current_text


def test_progress_doc_does_not_keep_stale_current_profile_test_count():
    text = PROGRESS_DOC.read_text(encoding="utf-8")

    assert "Current verification:" in text
    assert "0 skipped" in text
    assert "0 failed" in text
    assert "current focused profile is 61 tests" not in text


def test_progress_doc_explains_pre_execution_smoke_is_not_latest_metric_status():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = text.split("## Short History", 1)[0]

    assert "pre-execution artifact" in current_text
    assert "official_metric_execution_started=false" in current_text
    assert "must not be read\nas the latest metric execution status" in current_text


def test_progress_doc_scorer_backend_unavailable_only_in_short_history():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    headings_with_unavailable = []
    current_heading = ""
    current_body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if "SCORER_BACKEND_UNAVAILABLE" in "\n".join(current_body):
                headings_with_unavailable.append(current_heading)
            current_heading = line.removeprefix("## ").strip()
            current_body = []
        else:
            current_body.append(line)
    if "SCORER_BACKEND_UNAVAILABLE" in "\n".join(current_body):
        headings_with_unavailable.append(current_heading)

    assert headings_with_unavailable == ["Short History"]


def test_progress_doc_records_v3_1_7_queue_closure_without_metric_promotion():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = text.split("## Short History", 1)[0]

    assert "official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit" in current_text
    assert "active queue cleared" in current_text
    assert "all-track residual inventory" in current_text
    assert "text_namu_v2_0012" in current_text
    assert "text_namu_v2_0084" in current_text
    assert "gold_policy_review_packet_preparation" in current_text
    assert "pdfwin_b1c6527f848018640ad5ed231877c662" in current_text
    assert "diagnostic-only" in current_text
    assert "not promotion evidence" in current_text
    assert "no official nDCG/MRR/Hit@K" in current_text
    assert "Lane A/B/C not collapsed" in current_text


def test_progress_doc_records_v3_1_8_gold_policy_packet_without_metric_promotion():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = text.split("## Short History", 1)[0]

    assert "official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation" in current_text
    assert "human gold-policy packet-preparation run" in current_text
    assert "text_namu_v2_0012" in current_text
    assert "text_namu_v2_0084" in current_text
    assert "keep_current_strict_reference_boundary" in current_text
    assert "approve_scorer_or_renderer_review_without_gold_mutation" in current_text
    assert "revise_gold_or_label_policy" in current_text
    assert "active implementation queue remains empty" in current_text
    assert "diagnostic-only" in current_text
    assert "not promotion evidence" in current_text
    assert "no official nDCG/MRR/Hit@K" in current_text
    assert "no behavior, gold, label, production, denominator, retrieval, scorer, renderer, silver, or promotion mutation" in current_text


def test_progress_doc_records_v3_1_9_user_gold_policy_override_without_behavior_promotion():
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = text.split("## Short History", 1)[0]

    assert (
        "official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement"
        in current_text
    )
    assert "user-approved gold policy override application" in current_text
    assert "five TEXT rows changed by user decision" in current_text
    assert "text_namu_v2_0012" in current_text
    assert "text_namu_v2_0084" in current_text
    assert "behavior_change_made=false" in current_text
    assert "renderer/scorer/retrieval/production/silver/promotion behavior changed: none" in current_text
    assert "scoring-only remeasurement" in current_text
    assert "no official nDCG/MRR/Hit@K" in current_text
    assert "Lane A/B/C not collapsed" in current_text
    assert "promotion_evidence=false" in current_text


def test_progress_doc_records_v3_2_3_no_behavior_diagnostic_without_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = "official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation"
    assert run_id in current_text
    assert run_id in measurements
    assert run_id in triage
    assert "six query ids / 12 failing lane items" in current_text
    assert "Lane A-only frozen replay residuals" in current_text
    assert "text_namu_v2_0012" in current_text
    assert "text_namu_v2_0077" in current_text
    assert "v3_2_4_pdf_context_provenance" in current_text
    assert "v3_2_6_text_prompt_span_rule" in current_text
    assert "no per-run\n  Markdown, results JSONL, failure attribution, audit payload" in current_text
    assert "No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed" in measurements
    assert "v3_2_5` is not approved by v3_2_3 alone" in triage
    assert "No prompt, renderer, scorer, retrieval, export, index, gold" in triage


def test_progress_doc_records_v3_2_4_pdf_context_provenance_without_behavior_change():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = "official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic"
    assert run_id in current_text
    assert run_id in triage
    assert run_id in measurements
    assert "v3_2_4 `gq_auto_010` PDF context provenance" in measurements
    assert "No behavior/index/export mutation" in measurements
    assert "gq_auto_010" in current_text
    assert "open_because_v3_1_6_expansion_not_wired_into_v3_2_measurement" in current_text
    assert "7bf516bf-2a17-4303-86d8-3cffaa04846e" in current_text
    assert "pdfwin_b1c6527f848018640ad5ed231877c662" in current_text
    assert "retrieval_context_rerun=false" in current_text
    assert "retrieval_context_source_run_id=official_answer_citation_agentic_loop_run_v3_comparable_live_measurement" in current_text
    assert "v3_2_5 is\n  therefore needed as a measurement-source/context-assembly overlay" in current_text
    assert "not an\n  index/export rebuild" in current_text
    assert "No live generation, prompt, renderer, scorer, retrieval" in current_text
    assert "No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed" in triage
    assert "This is not a TEXT prompt residual" in triage
    assert "measurement-source selection / context\n  assembly overlay" in triage


def test_progress_doc_records_v3_2_5_pdf_context_reconciliation_fix_without_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = "official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix"
    assert run_id in current_text
    assert run_id in measurements
    assert run_id in triage
    assert "official_answer_citation_v3_2_5_gq_auto_010_pdf_context_reconciliation_fixed" in current_text
    assert "reuses the existing v3_1_6 safe PDF\n  paragraph/window sidecar for `gq_auto_010` only" in current_text
    assert "pdfwin_b1c6527f848018640ad5ed231877c662" in current_text
    assert "PASS from v3_2_2 `24/29`, `26/29`, `25/29` to `24/29`, `27/29`, `26/29`" in current_text
    assert "non-target unexpected deltas are `0`" in current_text
    assert "No\n  index/export rebuild, gold, expected answer" in current_text
    assert "v3_2_5 `gq_auto_010` PDF Context Reconciliation Fix" in measurements
    assert "Lane B `live_llm_retrieval_topk` | 26/29 | 27/29 | +1" in measurements
    assert "Lane C `live_llm_query_bound_oracle` | 25/29 | 26/29 | +1" in measurements
    assert "Citation support averages remain Lane A/B/C=`1.0`, `1.0`, `1.0`" in measurements
    assert "Denominator remains 29 rows: PDF=`4`, TEXT=`6`, XLSX=`19`" in measurements
    assert "closed_by_existing_v3_1_6_pdf_window_overlay" in triage
    assert "Remaining live B/C actionable queue" in triage
    assert "v3_2_6_text_prompt_span_rule" in triage
    assert "No per-run Markdown report was written" in triage


def test_progress_doc_records_v3_2_6_text_prompt_span_rule_remeasurement_without_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = "official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement"
    assert run_id in current_text
    assert run_id in measurements
    assert run_id in triage
    assert "official_answer_citation_v3_2_6_text_prompt_span_rule_remeasured" in current_text
    assert "target-scoped TEXT prompt/span rule" in current_text
    assert "`text_namu_v2_0014` Lane C changed from `LLM_EXPECTED_SPAN_MISMATCH` to `PASS`" in current_text
    assert "`text_namu_v2_0017` and `text_namu_v2_0084` remain diagnostic-only prompt/span residuals" in current_text
    assert "unexpected deltas are `0`" in current_text
    assert "v3_2_6 TEXT Prompt/Span Rule Remeasurement" in measurements
    assert "Lane C `live_llm_query_bound_oracle` | 26/29 | 27/29 | +1" in measurements
    assert "Lane B `live_llm_retrieval_topk` | 27/29 | 27/29 | 0" in measurements
    assert "Citation support averages remain Lane A/B/C=`1.0`, `1.0`, `1.0`" in measurements
    assert "text_namu_v2_0014" in triage
    assert "closed_by_text_prompt_span_rule" in triage
    assert "diagnostic_only_after_prompt_rule" in triage
    assert "No per-run Markdown report was written" in triage


def test_progress_doc_records_v3_2_7_closure_without_promotion_or_next_phase():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = "official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup"
    assert run_id in current_text
    assert run_id in measurements
    assert run_id in triage
    assert "official_answer_citation_v3_2_7_post_fix_sequence_closed" in current_text
    assert "v3_2_5 and v3_2_6 are the only implementation-changing post-v3_2_2 phases" in current_text
    assert "Lane A/B/C are now `24/29`, `27/29`, `27/29`" in current_text
    assert "no next implementation phase is opened" in current_text
    assert "v3_2_7 Post-Fix Closure" in measurements
    assert "Lane C `live_llm_query_bound_oracle` | 25/29 | 27/29 | +2" in measurements
    assert "official nDCG, MRR, Hit@K, and collapsed Lane A/B/C score remain deferred" in measurements
    assert "gq_auto_010" in triage
    assert "text_namu_v2_0014" in triage
    assert "text_namu_v2_0017" in triage
    assert "text_namu_v2_0084" in triage
    assert "diagnostic_only_after_prompt_rule" in triage
    assert "No per-run Markdown report was written" in triage
    assert "No gold, expected answer, supporting evidence" in triage


def test_progress_doc_records_v3_3_0_source_of_truth_audit_without_reopening_queue():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = "official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit"
    assert run_id in current_text
    assert run_id in measurements
    assert run_id in triage
    assert "official_answer_citation_v3_3_0_source_of_truth_audit_completed" in current_text
    assert "source-of-truth audit only" in current_text
    assert "Lane A/B/C remain `24/29`, `27/29`, `27/29`" in current_text
    assert "active implementation queue remains empty" in current_text
    assert "v3_3_0 Post-Closure Source-Of-Truth Audit" in measurements
    assert "status-ledger-only audit" in measurements
    assert "v3_2_7 remains status-ledger-only" in measurements
    assert "v3_2_4 PDF provenance diagnostic" in measurements
    assert "behavior_change_made=false for v3_3_0" in measurements
    assert "implementation_change_made=false for v3_3_0" in measurements
    assert "scorer_behavior_mutation=false" in measurements
    assert "v3_3_0 Post-Closure Source-Of-Truth Audit" in triage
    assert "No next implementation phase is opened" in triage
    assert "text_namu_v2_0017" in triage
    assert "text_namu_v2_0084" in triage
    assert "No per-run Markdown report was written" in triage


def test_progress_docs_record_v3_3_2_retrieval_label_design_packet_without_metrics():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = (
        "official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_"
        "label_design_packet"
    )
    assert run_id in current_text
    assert run_id in measurements
    assert run_id in triage
    assert "v3_3_2 retrieval-label design packet" in current_text
    assert "not yet an official retrieval qrels denominator" in current_text
    assert (
        "official nDCG, MRR, Hit@K, and any collapsed Lane A/B/C score remain blocked"
        in " ".join(current_text.split())
    )
    assert "v3_3_2 Retrieval Label-Design Packet" in measurements
    assert "No label/denominator/runtime/metric mutation" in measurements
    assert "Current denominator snapshot remains 29 answer/citation rows" in measurements
    assert "Structured adapter policy" in measurements
    assert "v3_3_2 Retrieval Relevance/Answerability Label-Design Packet" in triage
    assert "label_status=pending" in triage
    assert "No official nDCG, MRR, Hit@K, or collapsed Lane A/B/C score was computed" in triage
    assert "The active implementation queue remains empty and no next implementation" in triage


def test_progress_docs_record_v3_4_0_official_retrieval_metric_contract_without_metrics():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = "official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract"
    contract_json = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_contract.json"
    )
    qrels_schema_json = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract_qrels_schema.json"
    )

    assert run_id in current_text
    assert run_id in measurements
    assert run_id in triage
    assert "v3_4_0 official retrieval metric contract" in current_text
    assert contract_json in current_text
    assert qrels_schema_json in current_text
    assert contract_json in measurements
    assert qrels_schema_json in measurements
    assert contract_json in triage
    assert qrels_schema_json in triage
    assert "denominator policy options A/B/C" in current_text
    assert "Official nDCG, MRR, Hit@K, and any collapsed Lane A/B/C score remain blocked" in current_text
    assert "Legacy XLSX retrieval CSV and silver" in current_text
    assert "v3_4_0 Official Retrieval Metric Contract" in measurements
    assert "Qrels denominator policy options remain user-owned" in measurements
    assert "Default Hit@K/MRR positive rule" in measurements
    assert "Default nDCG gain is the relevance grade" in measurements
    assert "No prompt, retrieval, renderer, scorer, index/export, production, silver" in measurements
    assert "v3_4_0 Official Retrieval Metric Contract" in triage
    assert "Options A all 29 rows, B track-by-track opening, C only rows with settled retrieval labels" in triage
    assert "No official nDCG, MRR, Hit@K, micro/macro retrieval metric" in triage
    assert "Official answer/citation results and official retrieval metrics must remain" in triage


def test_progress_docs_record_v3_4_1_official_retrieval_qrels_candidate_packet_without_metrics():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_flat = " ".join(triage.split())

    run_id = "official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet"
    qrels_jsonl = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_"
        "qrels_candidates.jsonl"
    )
    qrels_csv = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_"
        "qrels_candidates.csv"
    )
    summary_json = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_"
        "summary.json"
    )

    assert "official_retrieval_qrels_candidate_packet_v3_4_1_ready_for_human_review" in current_text
    assert run_id in current_text
    assert run_id in triage
    assert qrels_jsonl in current_text
    assert qrels_csv in current_text
    assert summary_json in current_text
    assert qrels_jsonl in triage
    assert qrels_csv in triage
    assert summary_json in triage
    assert "219 rows across 29 query_ids" in current_text
    assert "PDF=22, TEXT=24, XLSX=173" in " ".join(current_text.split())
    assert "`relevance_label=pending`" in current_text
    assert "`answerability_label=pending`" in current_text
    assert "`label_status=pending_user_review`" in current_text
    assert "`generation_source=false`" in current_text
    assert "`promotion_evidence=false`" in current_text
    assert "No official Hit@K, MRR, nDCG" in " ".join(current_text.split())
    assert "v3_4_1 Official Retrieval Qrels Candidate Packet" in triage
    assert "| qrels candidate rows | 219 |" in triage
    assert "| XLSX candidates | 173 |" in triage
    assert "`suggested_label_reason` is diagnostic review context only" in triage
    assert "No official Hit@K, MRR, nDCG, micro/macro retrieval aggregate" in triage


def test_progress_doc_records_v3_4_1a_human_minimal_review_packet_without_metrics():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]

    run_id = (
        "official_answer_citation_agentic_loop_run_v3_4_1a_"
        "official_retrieval_qrels_human_minimal_review_packet"
    )
    policy_json = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1a_"
        "official_retrieval_qrels_human_minimal_review_packet_qrels_policy_approval.json"
    )
    query_group_csv = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1a_"
        "official_retrieval_qrels_human_minimal_review_packet_qrels_human_query_group_review.csv"
    )
    ambiguous_csv = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1a_"
        "official_retrieval_qrels_human_minimal_review_packet_qrels_ambiguous_candidate_review.csv"
    )
    auto_label_plan = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1a_"
        "official_retrieval_qrels_human_minimal_review_packet_qrels_auto_label_plan.json"
    )
    summary_json = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1a_"
        "official_retrieval_qrels_human_minimal_review_packet_summary.json"
    )

    assert "official_retrieval_qrels_human_minimal_review_packet_v3_4_1a_ready" in current_text
    assert run_id in current_text
    assert policy_json in current_text
    assert query_group_csv in current_text
    assert ambiguous_csv in current_text
    assert auto_label_plan in current_text
    assert summary_json in current_text
    assert "reduced from 219 raw candidate rows to 29 query-group rows plus 30 candidate-unit ambiguity rows" in " ".join(
        current_text.split()
    )
    assert "estimated 59 review rows total" in " ".join(current_text.split())
    assert "Expected answer/supporting evidence fields are omitted" in current_text
    assert "Codex recommendations are not final labels" in current_text
    assert "auto-labeling is not applied" in " ".join(current_text.split())
    assert "official Hit@K, MRR, nDCG" in current_text


def test_progress_and_triage_docs_record_v3_4_2_exact_evidence_qrels_without_metrics():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = "official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels"
    qrels_jsonl = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_"
        "official_retrieval_qrels.jsonl"
    )
    coverage_json = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_"
        "qrels_coverage_summary.json"
    )
    exclusion_jsonl = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels_"
        "qrels_exclusion_ledger.jsonl"
    )

    assert "official_exact_evidence_retrieval_qrels_v3_4_2_ready_metrics_deferred" in current_text
    assert run_id in current_text
    assert qrels_jsonl in current_text
    assert coverage_json in current_text
    assert exclusion_jsonl in current_text
    assert "Included query groups=28" in current_text
    assert "excluded query groups=1" in current_text
    assert "`gq_auto_010`" in current_text
    assert "`standalone_query_missing_year`" in current_text
    assert "not a retrieval miss, failure, negative, or unanswerable row" in " ".join(
        current_text.split()
    )
    assert "Official qrels unit rows=140" in current_text
    assert "qrels positives=28" in current_text
    assert "official exact-evidence retrieval metrics" in " ".join(current_text.split())
    assert "`source_bound_search_unit_exact_answer_evidence_smoke`" in current_text
    assert "small official exact-evidence retrieval smoke benchmark" in " ".join(
        current_text.split()
    )
    assert "metric-pipeline validation and regression guarding" in " ".join(current_text.split())
    assert "not statistically representative product performance" in " ".join(
        current_text.split()
    )
    assert "README headline performance claims from this 28-query set are blocked" in " ".join(
        current_text.split()
    )
    assert "binary exact-evidence nDCG@K" in current_text
    assert "v3_4_3 official exact-evidence Hit@K/MRR/binary nDCG computation is ready" in " ".join(
        current_text.split()
    )
    assert "did not compute Hit@K, MRR, nDCG" in " ".join(current_text.split())

    assert "`v3_4_2 official exact-evidence retrieval qrels labels applied`" in triage
    assert "## v3_4_2 Official Exact-Evidence Retrieval Qrels Labels Applied" in triage
    assert run_id in triage
    assert qrels_jsonl in triage
    assert coverage_json in triage
    assert exclusion_jsonl in triage
    assert "| included query groups | 28 |" in triage
    assert "| excluded query groups | 1 |" in triage
    assert "| excluded query_id | `gq_auto_010` |" in triage
    assert "| qrels positives | 28 |" in triage
    assert "not a broad topical semantic relevance benchmark" in triage
    assert "`source_bound_search_unit_exact_answer_evidence_smoke`" in triage
    assert "small official exact-evidence retrieval smoke benchmark" in " ".join(
        triage.split()
    )
    assert "valid for metric-pipeline validation and regression guarding" in " ".join(
        triage.split()
    )
    assert "not statistically representative product performance" in " ".join(
        triage.split()
    )
    assert "README headline performance claims from this 28-query set are blocked" in " ".join(
        triage.split()
    )
    assert "`not_official_positive_for_exact_evidence_metric`" in triage
    assert "No official Hit@K, MRR, nDCG" in triage


def test_progress_and_triage_docs_record_v3_4_3_exact_evidence_smoke_metrics():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_flat = " ".join(triage.split())

    run_id = "official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation"
    metrics_json = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_"
        "metrics.json"
    )
    per_query_jsonl = (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation_"
        "per_query.jsonl"
    )

    assert "official_exact_evidence_retrieval_smoke_metrics_v3_4_3_computed_small_sample" in current_text
    assert run_id in current_text
    assert metrics_json in current_text
    assert per_query_jsonl in current_text
    assert "Lane B `live_llm_retrieval_topk` only" in current_flat
    assert "Included query count=28" in current_flat
    assert "excluded query count=1" in current_flat
    assert "`gq_auto_010`" in current_text
    assert "PDF=3, TEXT=6, XLSX=19" in current_flat
    assert "Hit@1=27/28" in current_flat
    assert "Hit@3=28/28" in current_flat
    assert "Hit@5=28/28" in current_flat
    assert "MRR@5=27.5/28" in current_flat
    assert "0.9868189197704093" in current_text
    assert "small_sample_warning=true" in current_text
    assert "readme_headline_allowed=false" in current_text
    assert "regression_guard_allowed=true" in current_text
    assert "one query changes the score by about 3.57 percentage points" in current_flat
    assert "No graded nDCG" in current_text
    assert "threshold tuning" in current_text
    assert "winner selection" in current_text

    assert "`v3_4_3 official exact-evidence retrieval smoke metrics computed`" in triage
    assert "## v3_4_3 Official Exact-Evidence Retrieval Smoke Metrics" in triage
    assert run_id in triage
    assert metrics_json in triage
    assert per_query_jsonl in triage
    assert "| included query groups | 28 |" in triage
    assert "| excluded query groups | 1 |" in triage
    assert "| excluded query_id | `gq_auto_010` |" in triage
    assert "| source-family counts | PDF=3, TEXT=6, XLSX=19 |" in triage
    assert "| primary ranking surface | Lane B `live_llm_retrieval_topk` |" in triage
    assert "| Hit@1 | 27/28 = 0.9642857142857143 |" in triage
    assert "| Hit@3 | 28/28 = 1.0 |" in triage
    assert "| Hit@5 | 28/28 = 1.0 |" in triage
    assert "| MRR@5 | 27.5/28 = 0.9821428571428571 |" in triage
    assert "| binary exact-evidence nDCG@5 | 0.9868189197704093 |" in triage
    assert "`small_sample_warning=true`" in triage
    assert "`readme_headline_allowed=false`" in triage
    assert "`regression_guard_allowed=true`" in triage
    assert "One query changes the score by about 3.57 percentage points" in triage_flat
    assert "no graded nDCG was computed from ungraded labels" in triage_flat
    assert "Lane C query-bound oracle is reference-only" in triage_flat
    assert "No Lane A/B/C collapsed score" in triage_flat


def test_progress_doc_records_v3_4_4_readme_artifacts_and_silver_boundary_without_triage_change():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = "official_answer_citation_agentic_loop_run_v3_4_4_readme_retrieval_smoke_and_silver_readiness_artifacts"

    assert "readme_retrieval_smoke_card_v3_4_4_ready_silver_generation_blocked" in current_text
    assert "v3_4_4 README retrieval-smoke/silver-readiness artifacts" in current_text
    assert run_id in current_text
    assert "compact README metric card JSON, README insertion snippet, and silver-readiness summary" in current_flat
    assert "verified v3_4_3 Lane B exact-evidence smoke metrics" in current_flat
    assert "README integration is snippet-only" in current_flat
    assert "`pending_manual_integration=true`" in current_text
    assert "`readme_headline_allowed=false`" in current_text
    assert "`regression_guard_allowed=true`" in current_text
    assert "small-sample regression guard" in current_flat
    assert "not statistically representative product performance" in current_flat
    assert "Silver generation remains blocked" in current_text
    assert "TEXT=0, PDF=3, XLSX=4, total=7" in current_text
    assert "below the 100-row pilot and 1000-row target" in current_flat
    assert "official-denominator SearchUnits remain excluded from dev/holdout silver" in current_flat
    assert "no silver rows were generated" in current_flat
    assert run_id not in triage
    assert "v3_4_4 README retrieval-smoke/silver-readiness artifacts" not in triage


def test_progress_doc_records_v3_5_0_capacity_expansion_without_triage_change():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_id = (
        "official_answer_citation_agentic_loop_run_v3_5_0_"
        "strict_non_official_source_bound_capacity_expansion"
    )

    assert "strict_non_official_source_bound_capacity_expansion_v3_5_0_pilot_ready" in current_text
    assert "v3_5_0 strict non-official source-bound capacity expansion" in current_text
    assert run_id in current_text
    assert "previous strict inventory remains TEXT=0, PDF=3, XLSX=4, total=7" in current_flat
    assert "new manifest-ready source candidates are TEXT=350, PDF=3, XLSX=4, total=357" in current_flat
    assert "pilot threshold is met" in current_flat
    assert "1000-row target is not met" in current_flat
    assert "silver generation remains blocked" in current_flat
    assert "recommended next phase is `v3_5_1_pilot_silver_source_manifest_freeze`" in current_flat
    assert "No questions, expected answers, supporting evidence, labels, qrels, silver JSONL rows" in current_flat
    assert run_id not in triage
    assert "v3_5_0 strict non-official source-bound capacity expansion" not in triage


def test_progress_doc_records_v3_5_1_to_v3_5_3_source_material_phases_without_triage_change():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")

    run_ids = (
        "official_answer_citation_agentic_loop_run_v3_5_1_pilot_silver_source_manifest_freeze",
        (
            "official_answer_citation_agentic_loop_run_v3_5_2_"
            "xlsx_source_value_manifest_repair_and_acquisition"
        ),
        (
            "official_answer_citation_agentic_loop_run_v3_5_3_"
            "pdf_page_bbox_source_text_manifest_repair_and_acquisition"
        ),
    )

    assert "v3_5_1 pilot source manifest freeze" in current_text
    assert "freezes TEXT=350, PDF=3, XLSX=4, total=357 source-only rows" in current_flat
    assert "balanced pilot threshold is not met" in current_flat
    assert "target_threshold_met=false" in current_flat
    assert "v3_5_2 XLSX source-value manifest repair" in current_text
    assert "locator-complete XLSX rows from actual workbooks" in current_flat
    assert "freezes 321 manifest-ready overlay rows toward the XLSX target" in current_flat
    assert "Combined source counts are TEXT=350, PDF=3, XLSX=325, total=678" in current_flat
    assert "No query or expected_answer_text was used as source material" in current_flat
    assert "v3_5_3 PDF page/bbox source-text manifest repair" in current_text
    assert "extracts 322 PDF source rows from approved existing PDF source documents" in current_flat
    assert "Final source counts are TEXT=350, PDF=325, XLSX=325, total=1000" in current_flat
    assert "balanced_pilot_threshold_met=true" in current_flat
    assert "target_threshold_met=true" in current_flat
    assert "silver_generation_allowed=false" in current_flat
    for run_id in run_ids:
        assert run_id in current_text
        assert run_id not in triage


def test_status_jsonl_records_compact_v3_5_1_to_v3_5_3_source_material_events():
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected = {
        "official_answer_citation_agentic_loop_run_v3_5_1_pilot_silver_source_manifest_freeze": (
            "pilot_silver_source_manifest_freeze_v3_5_1",
            "source_manifest_freeze_only_no_silver_generation",
        ),
        (
            "official_answer_citation_agentic_loop_run_v3_5_2_"
            "xlsx_source_value_manifest_repair_and_acquisition"
        ): (
            "xlsx_source_value_manifest_repair_and_acquisition_v3_5_2",
            "source_value_manifest_repair_only_no_silver_generation",
        ),
        (
            "official_answer_citation_agentic_loop_run_v3_5_3_"
            "pdf_page_bbox_source_text_manifest_repair_and_acquisition"
        ): (
            "pdf_page_bbox_source_text_manifest_repair_and_acquisition_v3_5_3",
            "source_text_manifest_repair_only_no_silver_generation",
        ),
    }

    for run_id, (event_type, run_class) in expected.items():
        matches = [
            event
            for event in events
            if event.get("run_id") == run_id and event.get("event_type") == event_type
        ]
        assert len(matches) == 1
        event = matches[0]
        assert event["run_class"] == run_class
        assert event["triage_doc_updated"] is False
        assert event["silver_generation_allowed"] is False
        assert event["silver_jsonl_rows_created"] is False
        assert event["candidate_artifacts_used_as_generation_source"] is False
        assert "pilot_source_manifest_rows" not in event
        assert "xlsx_source_value_manifest_rows" not in event
        assert "pdf_source_text_manifest_rows" not in event
        assert "xlsx_manifest_ready_candidate_rows" not in event
        assert "pdf_manifest_ready_candidate_rows" not in event
        assert "balanced_capacity_summary" not in event


def test_progress_doc_records_v3_5_4_balanced_source_manifest_freeze_without_triage_change():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    run_id = "official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze"

    assert "v3_5_4 balanced source-only manifest freeze" in current_text
    assert run_id in current_text
    assert "TEXT=350, PDF=325, XLSX=325, total=1000 source-only rows" in current_flat
    assert "sample packet counts are TEXT=25, PDF=25, XLSX=25" in current_flat
    assert "preferred_mix_met=true" in current_flat
    assert "target_threshold_met=true" in current_flat
    assert "silver_generation_allowed=false" in current_flat
    assert "v3_5_5_balanced_source_manifest_quality_audit" in current_flat
    assert run_id not in triage


def test_status_jsonl_records_compact_v3_5_4_source_manifest_freeze_event():
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "balanced_silver_source_manifest_freeze_v3_5_4"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "balanced_source_manifest_freeze_only_no_silver_generation"
    assert event["triage_doc_updated"] is False
    assert event["frozen_counts_by_source_family"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert event["audit_sample_packet_counts_by_source_family"] == {
        "TEXT": 25,
        "PDF": 25,
        "XLSX": 25,
        "total": 75,
    }
    assert event["silver_generation_allowed"] is False
    assert event["silver_jsonl_rows_created"] is False
    assert event["candidate_artifacts_used_as_generation_source"] is False
    assert "balanced_source_manifest_jsonl" in event["artifact_paths"]
    assert "freeze_summary_json" in event["artifact_paths"]
    assert "audit_sample_packet_jsonl" in event["artifact_paths"]
    assert "balanced_source_manifest_rows" not in event
    assert "freeze_audit_rows" not in event
    assert "audit_sample_packet_rows" not in event
    assert "next_phase_policy_boundary" not in event


def test_progress_status_and_triage_gate_record_v3_5_5_quality_audit():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "balanced_source_manifest_quality_audit_v3_5_5"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "source_quality_audit_only_no_silver_generation"
    assert event["input_counts_by_source_family"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert event["normalized_source_hash_repetition_group_count"] == 17
    assert event["normalized_source_hash_repetition_row_count"] == 57
    assert event["recommended_repair_queue_count"] == event["critical_repair_required_count"]
    assert event["silver_generation_allowed"] is False
    assert "quality_summary_json" in event["artifact_paths"]
    assert "manifest_validation_jsonl" in event["artifact_paths"]
    assert "audit_sample_review_packet_jsonl" in event["artifact_paths"]
    assert "duplicate_hash_audit_jsonl" in event["artifact_paths"]
    assert "recommended_repair_queue_jsonl" in event["artifact_paths"]
    for large_field in (
        "balanced_source_manifest_rows",
        "manifest_validation_rows",
        "duplicate_hash_audit_rows",
        "audit_sample_review_packet_rows",
        "recommended_repair_queue_rows",
        "next_phase_policy_boundary",
    ):
        assert large_field not in event

    assert "v3_5_5 balanced source-manifest quality audit" in current_text
    assert run_id in current_text
    assert "TEXT=350, PDF=325, XLSX=325, total=1000 frozen v3_5_4 source-only rows" in current_flat
    assert "duplicate hash repetitions are 17 groups/57 rows" in current_flat
    assert "critical_repair_required_count=" in current_flat
    assert "recommended_repair_queue_count=" in current_flat
    assert "silver_generation_allowed=false" in current_flat

    if event["recommended_repair_queue_count"] == 0:
        assert run_id not in triage
    else:
        assert run_id in triage
        assert "Source-Quality Repair Queue" in triage
