from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"
STATUS_JSONL = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "status.jsonl"


def require_v3_7_2_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return
    message = "missing v3_7_2 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_7_2_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v3_8_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return
    message = "missing v3_8 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_8_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v3_8_1_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return
    message = "missing v3_8_1 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_8_1_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v3_8_2_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return
    message = "missing v3_8_2 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_8_2_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


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


def test_progress_status_and_triage_gate_record_v3_6_0_policy_application_without_generation():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_6_0_low_touch_noisy_silver_policy_application"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "low_touch_noisy_silver_policy_application_v3_6_0"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "policy_application_only_no_generated_silver_rows"
    assert event["user_policy_decision_applied"] is True
    assert event["low_touch_human_review_required"] is False
    assert event["weak_silver_candidate_count"] == 0
    assert event["weak_silver_candidates_created"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["official_gold_labels_created"] is False
    assert event["official_metric_denominator_usage_allowed"] is False
    assert event["readme_representative_product_performance_claim"] is False
    assert event["promotion_evidence"] is False
    assert "generation_contract_json" in event["artifact_paths"]
    assert "user_decision_matrix_jsonl" in event["artifact_paths"]
    assert "guardrail_summary_json" in event["artifact_paths"]
    assert "generation_contract" not in event
    assert "user_decision_matrix_rows" not in event
    assert "guardrail_summary" not in event

    assert "v3_6_0 low-touch weak/noisy silver policy application" in current_text
    assert run_id in current_text
    assert "user_policy_decision_applied=true" in current_flat
    assert "low_touch_human_review_required=false" in current_flat
    assert "generated silver rows=0" in current_flat
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_6_1_candidate_generation_without_official_labels():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "balanced_weak_noisy_silver_candidate_generation_v3_6_1"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "weak_noisy_silver_candidate_generation_diagnostic_only"
    assert event["weak_silver_candidate_count"] == 1000
    assert event["source_family_counts"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert event["query_quality_profile_counts"] == {
        "ambiguous_but_source_answerable": 200,
        "clean_source_grounded": 450,
        "noisy_user_like": 100,
        "numeric_table_or_locator_hard": 100,
        "short_keyword_or_fragment": 150,
    }
    assert event["blocked_generation_row_count"] == 0
    assert event["split_counts"] == {
        "weak_silver_exploration": 700,
        "weak_silver_holdout": 200,
        "weak_silver_stress_smoke_candidate": 100,
    }
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["promotion_evidence"] is False
    assert event["triage_doc_updated"] is False
    assert "weak_silver_candidates_jsonl" in event["artifact_paths"]
    assert "policy_compliance_audit_json" in event["artifact_paths"]
    assert "weak_silver_candidate_rows" not in event
    assert "generation_blocked_rows" not in event
    assert "policy_compliance_audit" not in event

    assert "v3_6_1 balanced weak/noisy silver candidate generation" in current_text
    assert run_id in current_text
    assert "1000 diagnostic weak/noisy candidate rows" in current_flat
    assert "TEXT=350, PDF=325, XLSX=325, total=1000" in current_flat
    assert "blocked rows=0" in current_flat
    assert "not gold, not official denominator/qrels, not promotion evidence" in current_flat
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_6_2_sanity_eval_without_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "weak_noisy_silver_candidate_sanity_eval_v3_6_2"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "weak_noisy_silver_candidate_sanity_eval_diagnostic_only"
    assert event["candidate_row_count"] == 1000
    assert event["candidate_sanity_passed"] is True
    assert event["bucket_counts"] == {
        "blocked_candidate": 0,
        "core_pass_quality_candidate": 665,
        "quarantine_candidate": 0,
        "review_only_challenge_candidate": 335,
    }
    assert event["quarantine_candidate_count"] == 0
    assert event["blocked_candidate_count"] == 0
    assert event["source_identity_groups_crossing_split_roles_count"] == 74
    assert event["split_independence_warning"] == "source_identity_groups_cross_split_roles_diagnostic_holdout_warning"
    assert event["hash_contract"]["generated_question_hash_contract"] == (
        "normalized_question_sha256_lowercase_whitespace_collapsed"
    )
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["triage_doc_updated"] is False
    assert "candidate_sanity_summary_json" in event["artifact_paths"]
    assert "candidate_sanity_per_row_jsonl" in event["artifact_paths"]
    assert "candidate_quarantine_rows_jsonl" in event["artifact_paths"]
    assert "candidate_sanity_per_row" not in event
    assert "source_candidate_rows" not in event

    assert "v3_6_2 weak/noisy silver candidate sanity eval" in current_text
    assert run_id in current_text
    assert "candidate_sanity_passed=true" in current_flat
    assert "bucket counts are core=665, review-only=335, quarantine=0, blocked=0" in current_flat
    assert "hash contract=normalized question sha256" in current_flat
    assert "v3_6_3 diagnostic weak/noisy silver manifest freeze is allowed=true" in current_flat
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_6_3_manifest_freeze_without_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_weak_noisy_silver_manifest_freeze_v3_6_3"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_weak_noisy_silver_manifest_freeze_only"
    assert event["manifest_row_count"] == 1000
    assert event["core_manifest_row_count"] == 665
    assert event["review_only_manifest_row_count"] == 335
    assert event["quarantine_manifest_row_count"] == 0
    assert event["manifest_freeze_passed"] is True
    assert event["bucket_counts"] == {
        "blocked_candidate": 0,
        "core_pass_quality_candidate": 665,
        "quarantine_candidate": 0,
        "review_only_challenge_candidate": 335,
    }
    assert event["official_proximity_review_row_count"] == 3
    assert event["source_identity_groups_crossing_split_roles_count"] == 74
    assert event["hash_contract"] == "normalized_question_sha256_lowercase_whitespace_collapsed"
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["triage_doc_updated"] is False
    assert "manifest_summary_json" in event["artifact_paths"]
    assert "manifest_all_jsonl" in event["artifact_paths"]
    assert "manifest_core_jsonl" in event["artifact_paths"]
    assert "manifest_review_only_jsonl" in event["artifact_paths"]
    assert "manifest_rows_all" not in event
    assert "source_candidate_rows" not in event
    assert "sanity_rows" not in event

    assert "v3_6_3 diagnostic weak/noisy silver manifest freeze" in current_text
    assert run_id in current_text
    assert "freezes 1000 diagnostic rows" in current_flat
    assert "core=665, review-only=335, quarantine=0" in current_flat
    assert "official proximity rows remain review-only=3" in current_flat
    assert "v3_6_4 diagnostic-only weak/noisy silver metric is allowed=true" in current_flat
    assert run_id not in triage


def test_progress_status_measurements_and_triage_gate_record_v3_6_4_metric_without_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_flat = " ".join(measurements.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_only_weak_noisy_silver_metric_v3_6_4"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "weak_noisy_silver_metric_diagnostic_only"
    assert event["diagnostic_row_count"] == 1000
    assert event["manifest_counts"] == {
        "all_diagnostic": 1000,
        "core_only": 665,
        "review_only_challenge": 335,
        "quarantine": 0,
    }
    assert event["runtime_generation_succeeded_row_count"] == 0
    assert event["runtime_generation_fail_closed_row_count"] == 1000
    assert event["runtime_generation_coverage_rate"] == 0.0
    assert event["fail_closed_reasons"] == []
    assert event["generation_fail_closed_reasons"]
    assert event["source_identity_groups_crossing_split_roles_count"] == 74
    assert event["split_independence_warning"] == "source_identity_groups_cross_split_roles_diagnostic_holdout_warning"
    assert event["official_proximity_review_row_count"] == 3
    assert event["official_proximity_core_row_count"] == 0
    assert event["generated_expected_answers_are_gold"] is False
    assert event["official_metric"] is False
    assert event["official_metric_denominator_usage_allowed"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["triage_doc_updated"] is False
    for artifact_key in (
        "summary_json",
        "per_row_jsonl",
        "aggregate_by_bucket_json",
        "failure_taxonomy_json",
        "sample_review_jsonl",
        "policy_audit_json",
        "next_phase_recommendation_json",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "per_row_metric_rows",
        "aggregate_by_bucket",
        "failure_taxonomy",
        "sample_review_rows",
        "policy_audit",
        "next_phase_recommendation",
        "manifest_rows_all",
    ):
        assert large_field not in event

    assert "v3_6_4 diagnostic-only weak/noisy silver metric" in current_text
    assert run_id in current_text
    assert "core_only=665, review_only_challenge=335, all_diagnostic=1000" in current_flat
    assert "live generation coverage=0/1000" in current_flat
    assert "answer/citation proxy metrics fail closed" in current_flat
    assert "core_only is the main interpretable diagnostic bucket" in current_flat
    assert run_id in measurements
    assert "v3_6_4 Diagnostic-Only Weak/Noisy Silver Metric" in measurements
    assert "core_only `665`, review_only_challenge `335`, all_diagnostic `1000`" in measurements_flat
    assert "Live generation was unavailable" in measurements
    assert "not gold, not official qrels, not official denominator" in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_6_5_without_metric_measurements_or_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_flat = " ".join(measurements.split())
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_rough_failure_bucket_triage_v3_6_5"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_only_rough_failure_bucket_triage"
    assert event["diagnostic_row_count"] == 1000
    assert event["multi_label_blocker_bucket_counts"]["runtime_generation_surface_unavailable"] == 1000
    assert event["multi_label_blocker_bucket_counts"]["answer_proxy_reference_missing_from_v3_6_3_manifest"] == 1000
    assert event["multi_label_blocker_bucket_counts"]["weak_silver_expected_answer_ambiguous"] == 334
    assert event["multi_label_blocker_bucket_counts"]["review_only_source_quality_noise"] == 334
    assert event["local_llm_usage_allowed"] is True
    assert event["local_llm_usage_scope"] == "capability_probe_and_runtime_surface_audit_only"
    assert event["local_llm_live_silver_generation_attempted"] is False
    assert event["local_llm_live_silver_generation_allowed"] is False
    assert event["local_llm_metric_scoring_attempted"] is False
    assert event["local_llm_metric_scoring_allowed"] is False
    assert event["external_llm_api_allowed"] is False
    assert event["external_llm_api_attempted"] is False
    assert event["db_usage_allowed"] is True
    assert event["db_usage_scope"] == "read_only_reference_and_runtime_surface_audit_only"
    assert event["db_write_allowed"] is False
    assert event["db_migration_allowed"] is False
    assert event["db_index_rebuild_allowed"] is False
    assert event["production_db_usage_allowed"] is False
    assert event["db_results_as_gold_allowed"] is False
    assert event["db_results_as_official_qrels_allowed"] is False
    assert event["db_results_as_generation_source_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["measurements_doc_updated"] is False
    assert event["triage_doc_updated"] is False
    for artifact_key in (
        "summary_json",
        "per_row_jsonl",
        "blocker_matrix_json",
        "runtime_surface_audit_json",
        "reference_surface_audit_json",
        "db_surface_audit_json",
        "local_llm_surface_audit_json",
        "policy_audit_json",
        "next_phase_recommendation_json",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "per_row_triage_rows",
        "blocker_matrix",
        "runtime_surface_audit",
        "reference_surface_audit",
        "db_surface_audit",
        "local_llm_surface_audit",
        "policy_audit",
        "next_phase_recommendation",
        "per_row_metric_rows",
        "source_candidate_rows",
    ):
        assert large_field not in event

    assert "v3_6_5 rough failure-bucket triage" in current_text
    assert run_id in current_text
    assert "no live silver generation" in current_flat
    assert "no DB writes" in current_flat
    assert "DB-derived generation/gold/qrels remain blocked" in current_flat
    assert run_id not in measurements
    assert "v3_6_5 Runtime Surface Audit And Rough Failure Buckets" not in measurements
    assert "LLM generation/scoring `0/0`, DB writes `0`" not in measurements_flat
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_6_6_without_metric_measurements_or_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_reference_sidecar_and_runtime_surface_probe_v3_6_6"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_only_reference_sidecar_and_runtime_surface_probe"
    assert event["diagnostic_reference_sidecar_complete"] is True
    assert event["sidecar_row_counts"] == {
        "all_diagnostic": 1000,
        "core_only": 665,
        "quarantine": 0,
        "review_only_challenge": 335,
    }
    assert event["diagnostic_row_count"] == 1000
    assert event["core_smoke_sample_target_row_count"] == 30
    assert event["core_smoke_generation_attempted_row_count"] <= 30
    assert event["core_smoke_strict_json_answer_returned_row_count"] <= event[
        "core_smoke_generation_attempted_row_count"
    ]
    assert event["core_smoke_generation_succeeded_row_count"] <= event["core_smoke_generation_attempted_row_count"]
    assert event["local_llm_usage_scope"] == "diagnostic_only_core_smoke_runtime_probe_only"
    assert event["local_llm_live_silver_generation_allowed"] is False
    assert event["local_llm_metric_scoring_allowed"] is False
    assert event["external_llm_api_allowed"] is False
    assert event["external_llm_api_attempted"] is False
    assert event["db_usage_scope"] == "read_only_reference_and_runtime_surface_probe_only"
    assert event["db_read_only_probe_attempted"] is True
    assert event["db_write_attempted"] is False
    assert event["db_migration_attempted"] is False
    assert event["db_index_rebuild_attempted"] is False
    assert event["db_write_migration_reindex_attempted"] is False
    assert event["production_db_used"] is False
    assert event["db_results_as_generation_source_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["measurements_doc_updated"] is False
    assert event["triage_doc_updated"] is False
    assert event["review_only_remains_stress_only"] is True
    assert event["official_proximity_rows_remain_out_of_core"] is True
    assert event["recommended_next_phase"] in {
        "v3_6_7_core_only_live_diagnostic_weak_noisy_silver_metric",
        "v3_6_7_runtime_stability_probe_for_core_only",
        "v3_6_7_manifest_locator_live_retrieval_probe",
        "v3_6_7_reference_sidecar_recovery_or_compaction_fix",
    }
    for artifact_key in (
        "summary_json",
        "reference_sidecar_jsonl",
        "core_smoke_sample_jsonl",
        "runtime_probe_summary_json",
        "db_retrieval_surface_audit_json",
        "policy_audit_json",
        "next_phase_recommendation_json",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "reference_sidecar_rows",
        "core_smoke_sample_rows",
        "runtime_probe_summary",
        "db_retrieval_surface_audit",
        "policy_audit",
        "next_phase_recommendation",
        "per_row_triage_rows",
        "per_row_metric_rows",
    ):
        assert large_field not in event

    assert "v3_6_6 diagnostic reference sidecar and runtime surface probe" in current_text
    assert run_id in current_text
    assert "all=1000, core=665, review-only=335, quarantine=0" in current_flat
    assert "strict JSON answers returned=" in current_flat
    assert "Review-only remains stress-only" in current_flat
    assert "DB-derived generation/gold/qrels remain blocked" in current_flat
    assert (
        "Overall status: `diagnostic_reference_sidecar_runtime_surface_probe_v3_6_6_complete`;" in progress
        or "Overall status: `diagnostic_runtime_stability_probe_v3_6_7_complete`;" in progress
        or "Overall status: `diagnostic_nonprod_all_source_index_materialization_v3_6_8_complete`;" in progress
        or "Overall status: `diagnostic_source_registry_architecture_audit_v3_6_8_searchunit_overloaded_blocked`;" in progress
        or "Overall status: `diagnostic_searchunit_searchview_sourceatom_refactor_v3_6_9_contract_ready`;" in progress
        or "Overall status: `diagnostic_source_registry_materialization_v3_7_0_ready`;" in progress
        or "Overall status: `diagnostic_all_source_citable_nonprod_index_v3_7_1_built`;" in progress
        or "Overall status: `local_llm_natural_silver_query_regeneration_v3_7_2_done`;" in progress
        or "Overall status: `diagnostic_source_registry_backed_retrieval_smoke_v3_7_2_report_done`;" in progress
        or "Overall status: `diagnostic_file_grounded_retrieval_eval_v3_8_computed`;" in progress
        or "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_6_7_runtime_stability_probe_without_metric_measurements_or_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_6_7_runtime_stability_probe_for_core_only"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_runtime_stability_probe_for_core_only_v3_6_7"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_only_runtime_stability_probe_for_core_only"
    assert event["source_v3_6_6_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe"
    )
    assert event["sidecar_row_counts"] == {
        "all_diagnostic": 1000,
        "core_only": 665,
        "quarantine": 0,
        "review_only_challenge": 335,
    }
    assert event["runtime_probe_row_count"] == 30
    assert event["runtime_probe_core_only"] is True
    assert event["review_only_rows_attempted"] == 0
    assert event["official_proximity_rows_attempted"] == 0
    assert event["runtime_attempted_row_count"] <= 30
    assert event["strict_json_answer_returned_row_count"] <= event["runtime_attempted_row_count"]
    assert event["citation_surface_valid_row_count"] <= event["runtime_attempted_row_count"]
    assert event["local_llm_usage_scope"] == "diagnostic_only_core_runtime_stability_probe_only"
    assert event["local_llm_live_silver_generation_allowed"] is False
    assert event["local_llm_live_silver_generation_attempted"] is False
    assert event["local_llm_metric_scoring_allowed"] is False
    assert event["local_llm_metric_scoring_attempted"] is False
    assert event["external_llm_api_allowed"] is False
    assert event["external_llm_api_attempted"] is False
    assert event["db_usage_scope"] == "read_only_inherited_surface_status_only"
    assert event["db_read_only_probe_attempted"] is False
    assert event["db_write_attempted"] is False
    assert event["db_migration_attempted"] is False
    assert event["db_index_rebuild_attempted"] is False
    assert event["db_write_migration_reindex_attempted"] is False
    assert event["production_db_used"] is False
    assert event["db_results_as_generation_source_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["measurements_doc_updated"] is False
    assert event["triage_doc_updated"] is False
    assert event["recommended_next_phase"] in {
        "v3_6_7_core_only_live_diagnostic_weak_noisy_silver_metric",
        "v3_6_7_manifest_locator_live_retrieval_probe",
        "v3_6_7_runtime_stability_probe_for_core_only",
        "v3_6_7_reference_sidecar_recovery_or_compaction_fix",
    }
    for artifact_key in (
        "summary_json",
        "runtime_attempts_jsonl",
        "runtime_stability_summary_json",
        "policy_audit_json",
        "next_phase_recommendation_json",
        "source_v3_6_6_summary_json",
        "source_v3_6_6_core_smoke_sample_jsonl",
        "source_v3_6_6_reference_sidecar_jsonl",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "runtime_attempt_rows",
        "runtime_stability_summary",
        "policy_audit",
        "next_phase_recommendation",
        "reference_sidecar_rows",
        "core_smoke_sample_rows",
        "per_row_triage_rows",
        "per_row_metric_rows",
    ):
        assert large_field not in event

    assert "v3_6_7 runtime stability probe for core-only" in current_text
    assert run_id in current_text
    assert "attempted=" in current_flat
    assert "strict JSON answers=" in current_flat
    assert "citation surface valid=" in current_flat
    assert "not gold/qrels/official denominator/labels" in current_flat
    assert "no prompt/retrieval/scorer/renderer/index/export/DB mutation was performed" in current_flat
    assert (
        "Overall status: `diagnostic_runtime_stability_probe_v3_6_7_complete`;" in progress
        or "Overall status: `diagnostic_nonprod_all_source_index_materialization_v3_6_8_complete`;" in progress
        or "Overall status: `diagnostic_source_registry_architecture_audit_v3_6_8_searchunit_overloaded_blocked`;" in progress
        or "Overall status: `diagnostic_searchunit_searchview_sourceatom_refactor_v3_6_9_contract_ready`;" in progress
        or "Overall status: `diagnostic_source_registry_materialization_v3_7_0_ready`;" in progress
        or "Overall status: `diagnostic_all_source_citable_nonprod_index_v3_7_1_built`;" in progress
        or "Overall status: `local_llm_natural_silver_query_regeneration_v3_7_2_done`;" in progress
        or "Overall status: `diagnostic_source_registry_backed_retrieval_smoke_v3_7_2_report_done`;" in progress
        or "Overall status: `diagnostic_file_grounded_retrieval_eval_v3_8_computed`;" in progress
        or "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_6_8_nonprod_all_source_without_metric_measurements_or_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_6_8_"
        "nonprod_all_source_index_materialization_and_canonical_payload_wiring"
    )
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_nonprod_all_source_index_materialization_v3_6_8"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_only_nonprod_all_source_index_materialization"
    assert event["outcome"] == "ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED"
    assert set(event["outcome_choices"]) == {
        "ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED",
        "ALL_SOURCE_INDEX_BUILT_PAYLOAD_PARTIAL",
        "INDEX_MATERIALIZATION_BLOCKED",
        "PAYLOAD_WIRED_BUT_LLM_CITATION_COPY_BLOCKED",
    }
    assert event["next_allowed_phase"] == "v3_6_9_core_only_live_diagnostic_metric"
    assert event["recommended_next_phase"] == event["next_allowed_phase"]
    assert event["no_generic_probe_recommended"] is True
    assert "manifest_locator" not in event["recommended_next_phase"]
    assert event["index_namespace"] == "rag-data-all-source-nonprod-v1"
    assert event["index_or_export_mutation"] is True
    assert event["index_or_export_mutation_scope"] == "non_production_only"
    assert event["load_check"]["passed"] is True
    assert event["load_check"]["official_29_rows_remain_protected_and_identifiable"] is True
    assert event["load_check"]["v3_5_4_source_rows_represented"] + event["load_check"][
        "v3_5_4_source_rows_blocked"
    ] == 1000
    assert event["payload_contract"]["families_with_canonical_payload"] == ["PDF", "TEXT", "XLSX"]
    assert event["payload_contract"]["families_with_valid_no_llm_render"] == ["PDF", "TEXT", "XLSX"]
    assert event["retrieval_smoke"]["canonical_payload_available_count"] == 50
    assert event["retrieval_smoke"]["no_llm_citation_render_valid_count"] == 50
    assert event["core_only_live_diagnostic_metric_allowed"] is True
    assert event["measurements_doc_updated"] is False
    assert event["triage_doc_updated"] is False
    assert event["production_db_used"] is False
    assert event["db_write_attempted"] is False
    assert event["db_migration_attempted"] is False
    assert event["db_index_rebuild_attempted"] is False
    assert event["production_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["official_gold_labels_created"] is False
    assert event["answer_metric_computed"] is False
    assert event["citation_metric_computed"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["readme_performance_claim_mutation"] is False
    for artifact_key in (
        "summary_json",
        "source_inventory_json",
        "index_build_summary_json",
        "payload_contract_summary_json",
        "retrieval_smoke_diagnostics_jsonl",
        "failure_buckets_json",
        "index_faiss",
        "index_build_json",
        "index_ingest_manifest_json",
        "index_search_unit_manifest_jsonl",
        "index_source_inventory_json",
        "index_payload_contract_summary_json",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "source_inventory",
        "index_build_summary",
        "payload_contract_summary",
        "retrieval_smoke_diagnostics",
        "failure_buckets",
        "search_unit_manifest_rows",
        "raw_source_units",
    ):
        assert large_field not in event

    assert "v3_6_8 non-production all-source index materialization" in current_text
    assert run_id in current_text
    assert "outcome=ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED" in current_flat
    assert "next_allowed_phase=v3_6_9_core_only_live_diagnostic_metric" in current_flat
    assert "diagnostic-only non-production indexing" in current_flat
    assert "not a promotion run" in current_flat
    assert "not an official representative metric" in current_flat
    assert (
        "Overall status: `diagnostic_nonprod_all_source_index_materialization_v3_6_8_complete`;" in progress
        or "Overall status: `diagnostic_source_registry_architecture_audit_v3_6_8_searchunit_overloaded_blocked`;"
        in progress
        or "Overall status: `diagnostic_searchunit_searchview_sourceatom_refactor_v3_6_9_contract_ready`;"
        in progress
        or "Overall status: `diagnostic_source_registry_materialization_v3_7_0_ready`;" in progress
        or "Overall status: `diagnostic_all_source_citable_nonprod_index_v3_7_1_built`;" in progress
        or "Overall status: `local_llm_natural_silver_query_regeneration_v3_7_2_done`;" in progress
        or "Overall status: `diagnostic_source_registry_backed_retrieval_smoke_v3_7_2_report_done`;" in progress
        or "Overall status: `diagnostic_file_grounded_retrieval_eval_v3_8_computed`;" in progress
        or "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_6_8_source_registry_architecture_audit_without_metric_measurements_or_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_6_8_"
        "source_registry_first_evidence_bundle_architecture_audit"
    )
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_source_registry_architecture_audit_v3_6_8"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_only_source_registry_first_architecture_audit"
    assert event["outcome"] == "SEARCHUNIT_OVERLOADED_BLOCKER"
    assert set(event["outcome_choices"]) == {
        "SOURCE_REGISTRY_EVIDENCE_ARCHITECTURE_READY",
        "SEARCHUNIT_OVERLOADED_BLOCKER",
        "SOURCE_REGISTRY_MISSING_BLOCKER",
        "VECTOR_DB_COUPLING_BLOCKER",
        "TRACK_ROUTING_OVERFIT_BLOCKER",
    }
    assert event["next_allowed_phase"] == "SearchUnit/SearchView/SourceAtom refactor"
    assert event["recommended_next_phase"] == event["next_allowed_phase"]
    assert event["no_generic_probe_recommended"] is True
    assert "manifest_locator" not in event["recommended_next_phase"]
    assert event["source_registry_first_policy"] is True
    assert event["vector_db_role"] == "candidate_generator_only"
    assert event["index_or_export_mutation"] is False
    assert event["source_atom_search_view_evidence_bundle_separation_validated"] is False
    assert event["searchunit_overloaded"] is True
    assert event["blocking_buckets"] == ["SEARCHUNIT_OVERLOADED_BLOCKER"]
    assert event["measurements_doc_updated"] is False
    assert event["triage_doc_updated"] is False
    assert event["production_db_used"] is False
    assert event["db_write_attempted"] is False
    assert event["db_migration_attempted"] is False
    assert event["db_index_rebuild_attempted"] is False
    assert event["production_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["official_gold_labels_created"] is False
    assert event["answer_metric_computed"] is False
    assert event["citation_metric_computed"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["readme_performance_claim_mutation"] is False
    for artifact_key in (
        "summary_json",
        "source_object_audit_json",
        "searchunit_role_audit_json",
        "evidence_bundle_contract_json",
        "track_routing_audit_json",
        "failure_buckets_json",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "source_object_audit",
        "searchunit_role_audit",
        "evidence_bundle_contract",
        "track_routing_audit",
        "failure_buckets",
        "source_atom_rows",
        "evidence_bundle_rows",
    ):
        assert large_field not in event

    assert "v3_6_8 source-registry-first evidence bundle architecture audit" in current_text
    assert run_id in current_text
    assert "outcome=SEARCHUNIT_OVERLOADED_BLOCKER" in current_flat
    assert "next_allowed_phase=SearchUnit/SearchView/SourceAtom refactor" in current_flat
    assert "Search indexes remain candidate generators only" in current_flat
    assert (
        "Overall status: `diagnostic_source_registry_architecture_audit_v3_6_8_searchunit_overloaded_blocked`;"
        in progress
        or "Overall status: `diagnostic_searchunit_searchview_sourceatom_refactor_v3_6_9_contract_ready`;"
        in progress
        or "Overall status: `diagnostic_source_registry_materialization_v3_7_0_ready`;" in progress
        or "Overall status: `diagnostic_all_source_citable_nonprod_index_v3_7_1_built`;" in progress
        or "Overall status: `local_llm_natural_silver_query_regeneration_v3_7_2_done`;" in progress
        or "Overall status: `diagnostic_source_registry_backed_retrieval_smoke_v3_7_2_report_done`;" in progress
        or "Overall status: `diagnostic_file_grounded_retrieval_eval_v3_8_computed`;" in progress
        or "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_6_9_searchunit_searchview_sourceatom_refactor_without_metric_measurements_or_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_6_9_"
        "searchunit_searchview_sourceatom_refactor"
    )
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_searchunit_searchview_sourceatom_refactor_v3_6_9"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_only_source_first_contract_refactor"
    assert event["outcome"] == "SEARCHUNIT_SEARCHVIEW_SOURCEATOM_CONTRACT_READY"
    assert set(event["outcome_choices"]) == {
        "SEARCHUNIT_SEARCHVIEW_SOURCEATOM_CONTRACT_READY",
        "SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_BLOCKED",
        "SOURCE_REGISTRY_MATERIALIZATION_REQUIRED",
        "VECTOR_METADATA_DECOUPLING_REQUIRED",
    }
    assert event["next_allowed_phase"] == "source registry materialization"
    assert event["recommended_next_phase"] == event["next_allowed_phase"]
    assert event["no_generic_probe_recommended"] is True
    assert "manifest_locator" not in event["recommended_next_phase"]
    assert event["source_registry_first_policy"] is True
    assert event["vector_db_role"] == "candidate_generator_only"
    assert event["source_atom_search_view_contract_validated"] is True
    assert event["source_atom_search_view_evidence_bundle_separation_validated"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["source_registry_materialization_required"] is True
    assert event["db_migration_required_for_minimal_python_refactor"] is False
    assert event["index_or_export_mutation"] is False
    assert event["measurements_doc_updated"] is False
    assert event["triage_doc_updated"] is False
    assert event["production_db_used"] is False
    assert event["db_write_attempted"] is False
    assert event["db_migration_attempted"] is False
    assert event["db_index_rebuild_attempted"] is False
    assert event["production_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["official_gold_labels_created"] is False
    assert event["answer_metric_computed"] is False
    assert event["citation_metric_computed"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["readme_performance_claim_mutation"] is False
    for artifact_key in (
        "summary_json",
        "contract_refactor_json",
        "search_view_adapter_diagnostics_json",
        "source_atom_hydration_smoke_json",
        "failure_buckets_json",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "contract_refactor",
        "search_view_adapter_diagnostics",
        "source_atom_hydration_smoke",
        "failure_buckets",
        "source_atom_rows",
        "evidence_bundle_rows",
    ):
        assert large_field not in event

    assert "v3_6_9 SearchUnit/SearchView/SourceAtom refactor" in current_text
    assert run_id in current_text
    assert "outcome=SEARCHUNIT_SEARCHVIEW_SOURCEATOM_CONTRACT_READY" in current_flat
    assert "next_allowed_phase=source registry materialization" in current_flat
    assert "SearchViews are retrieval candidates" in current_flat
    assert "vector_payload_used_as_evidence_truth=false" in current_flat
    assert (
        "Overall status: `diagnostic_searchunit_searchview_sourceatom_refactor_v3_6_9_contract_ready`;" in progress
        or "Overall status: `diagnostic_source_registry_materialization_v3_7_0_ready`;" in progress
        or "Overall status: `diagnostic_all_source_citable_nonprod_index_v3_7_1_built`;" in progress
        or "Overall status: `local_llm_natural_silver_query_regeneration_v3_7_2_done`;" in progress
        or "Overall status: `diagnostic_source_registry_backed_retrieval_smoke_v3_7_2_report_done`;" in progress
        or "Overall status: `diagnostic_file_grounded_retrieval_eval_v3_8_computed`;" in progress
        or "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_7_0_source_registry_materialization_without_metrics_or_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_7_0_"
        "source_registry_materialization"
    )
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_source_registry_materialization_v3_7_0"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_only_source_registry_materialization"
    assert event["outcome"] == "SOURCE_REGISTRY_MATERIALIZED_READY"
    assert set(event["outcome_choices"]) == {
        "SOURCE_REGISTRY_MATERIALIZED_READY",
        "SOURCE_REGISTRY_MATERIALIZED_PARTIAL",
        "SOURCE_REGISTRY_MATERIALIZATION_BLOCKED",
        "RAW_SOURCE_LINEAGE_BLOCKED",
        "SNAPSHOT_ONLY_POLICY_BLOCKED",
    }
    assert event["next_allowed_phase"] == "v3_7_1_all_source_citable_nonprod_index_build"
    assert event["v3_7_1_all_source_citable_nonprod_index_build_allowed"] is True
    assert event["source_registry_first_policy"] is True
    assert event["vector_db_role"] == "candidate_generator_only"
    assert event["source_registry_materialized"] is True
    assert event["source_atom_registry_version"] == "source-registry-v1"
    assert event["no_vector_evidence_bundle_hydration_passed"] is True
    assert event["no_vector_citation_rendering_passed"] is True
    assert event["vector_metadata_used_as_canonical_citation_source"] is False
    assert event["official_denominator_source_atoms_protected_regression_scope"] is True
    assert event["measurements_doc_updated"] is False
    assert event["triage_doc_updated"] is False
    assert event["production_db_used"] is False
    assert event["db_write_attempted"] is False
    assert event["db_migration_attempted"] is False
    assert event["db_index_rebuild_attempted"] is False
    assert event["production_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["official_gold_labels_created"] is False
    assert event["retrieval_metric_computed"] is False
    assert event["answer_metric_computed"] is False
    assert event["citation_metric_computed"] is False
    assert event["hybrid_retrieval_baseline_computed"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["readme_performance_claim_mutation"] is False
    for artifact_key in (
        "summary_json",
        "source_inventory_json",
        "materialization_diagnostics_jsonl",
        "hydration_smoke_json",
        "failure_buckets_json",
        "source_atom_registry_jsonl",
        "source_atom_registry_build_json",
        "source_atom_registry_inventory_json",
        "source_atom_registry_blocked_jsonl",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "source_atom_rows",
        "materialization_diagnostics",
        "source_inventory",
        "failure_buckets",
        "hydration_smoke",
    ):
        assert large_field not in event

    assert "v3_7_0 source registry materialization" in current_text
    assert run_id in current_text
    assert "outcome=SOURCE_REGISTRY_MATERIALIZED_READY" in current_flat
    assert "next_allowed_phase=v3_7_1_all_source_citable_nonprod_index_build" in current_flat
    assert "no-vector hydration=true" in current_flat
    assert "vector_metadata_used_as_canonical_citation_source=false" in current_flat
    assert (
        "Overall status: `diagnostic_source_registry_materialization_v3_7_0_ready`;" in progress
        or "Overall status: `diagnostic_all_source_citable_nonprod_index_v3_7_1_built`;" in progress
        or "Overall status: `local_llm_natural_silver_query_regeneration_v3_7_2_done`;" in progress
        or "Overall status: `diagnostic_source_registry_backed_retrieval_smoke_v3_7_2_report_done`;" in progress
        or "Overall status: `diagnostic_file_grounded_retrieval_eval_v3_8_computed`;" in progress
        or "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_7_1_all_source_citable_nonprod_index_without_metrics_or_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_7_1_"
        "all_source_citable_nonprod_index_build"
    )
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_all_source_citable_nonprod_index_build_v3_7_1"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_only_all_source_citable_nonprod_index_build"
    assert event["outcome"] == "ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILT"
    assert set(event["outcome_choices"]) == {
        "ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILT",
        "ALL_SOURCE_CITABLE_INDEX_PARTIAL",
        "ALL_SOURCE_CITABLE_INDEX_BLOCKED",
        "SOURCE_REGISTRY_NOT_READY",
    }
    assert event["next_allowed_phase"] == "v3_7_2_source_registry_backed_retrieval_smoke"
    assert event["source_registry_outcome"] == "SOURCE_REGISTRY_MATERIALIZED_READY"
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["search_view_source_atom_contract"] is True
    assert event["vector_db_role"] == "candidate_generator_only"
    assert event["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert event["vector_metadata_used_as_canonical_citation_source"] is False
    assert event["vector_metadata_used_as_evidence_truth"] is False
    assert event["search_view_count"] == 136280
    assert event["official_overlap_count"] == 29
    assert event["snapshot_only_count"] == 3
    assert event["load_check"]["passed"] is True
    assert event["hydration_smoke_summary"]["families_passed"] == ["PDF", "TEXT", "XLSX"]
    assert event["hydration_smoke_summary"]["no_vector_evidence_bundle_hydration_passed"] is True
    assert event["hydration_smoke_summary"]["no_vector_citation_rendering_passed"] is True
    assert event["measurements_doc_updated"] is False
    assert event["triage_doc_updated"] is False
    assert event["production_db_used"] is False
    assert event["db_write_attempted"] is False
    assert event["db_migration_attempted"] is False
    assert event["db_index_rebuild_attempted"] is False
    assert event["production_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["retrieval_metric_computed"] is False
    assert event["answer_metric_computed"] is False
    assert event["citation_metric_computed"] is False
    assert event["hybrid_retrieval_baseline_computed"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["readme_performance_claim_mutation"] is False
    for artifact_key in (
        "summary_json",
        "source_inventory_json",
        "index_build_summary_json",
        "hydration_smoke_json",
        "failure_buckets_json",
        "index_faiss",
        "index_build_json",
        "index_ingest_manifest_json",
        "index_search_view_manifest_jsonl",
        "index_source_inventory_json",
        "index_hydration_smoke_json",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "source_inventory",
        "index_build_summary",
        "hydration_smoke",
        "failure_buckets",
        "search_view_rows",
        "blocked_search_view_rows",
    ):
        assert large_field not in event

    assert "v3_7_1 all-source citable non-production index build" in current_text
    assert run_id in current_text
    assert "outcome=ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILT" in current_flat
    assert "next_allowed_phase=v3_7_2_source_registry_backed_retrieval_smoke" in current_flat
    assert "no-vector hydration=true" in current_flat
    assert "vector_metadata_used_as_canonical_citation_source=false" in current_flat
    assert (
        "Overall status: `diagnostic_all_source_citable_nonprod_index_v3_7_1_built`;" in progress
        or "Overall status: `local_llm_natural_silver_query_regeneration_v3_7_2_done`;" in progress
        or "Overall status: `diagnostic_source_registry_backed_retrieval_smoke_v3_7_2_report_done`;" in progress
        or "Overall status: `diagnostic_file_grounded_retrieval_eval_v3_8_computed`;" in progress
        or "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_7_2_source_registry_backed_retrieval_smoke_without_promotion():
    require_v3_7_2_local_artifacts(STATUS_JSONL)
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_7_2_"
        "source_registry_backed_retrieval_smoke_report"
    )
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_source_registry_backed_retrieval_smoke_report_v3_7_2"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["run_class"] == "diagnostic_only_source_registry_backed_retrieval_smoke_report"
    assert event["contract_path"] == ["SearchView", "SourceAtom", "EvidenceBundle", "Citation render"]
    assert event["official_gold_usage"] == "sealed_no_regression_check_only"
    assert event["silver_usage"] == "diagnostic_failure_distribution_only"
    assert event["headline_aggregate_success_rate_reported"] is False
    assert event["retrieval_score_primary_metric"] is False
    assert event["answer_quality_metric_computed"] is False
    assert event["answer_metric_computed"] is False
    assert event["citation_metric_computed"] is False
    assert event["promotion_evidence"] is False
    assert event["promotion_readiness_opened"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["readme_performance_claim_mutation"] is False
    assert event["measurements_doc_updated"] is False
    assert event["triage_doc_updated"] is False
    assert event["production_db_used"] is False
    assert event["db_write_attempted"] is False
    assert event["db_migration_attempted"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["official_gold_labels_created"] is False
    assert "silver_precision" not in json.dumps(event, ensure_ascii=False).lower()
    assert "silver precision" not in json.dumps(event, ensure_ascii=False).lower()
    assert event["retrieval_routing_mode"] == "query_source_family_routed_for_structured_tracks"
    assert event["routed_source_families"] == ["PDF", "XLSX"]
    assert event["family_routed_missing_query_key_count"] == 0
    assert event["family_routed_missing_query_keys"] == []
    assert event["mixed_retrieval_baseline"]["candidate_pool_mode"] == (
        "mixed_all_source_faiss_topk_before_family_routing"
    )
    assert set(event["per_track_breakdown"]) == {"TEXT", "PDF", "XLSX"}
    for track in ("PDF", "XLSX"):
        routed = event["per_track_breakdown"][track]
        mixed = event["mixed_retrieval_baseline"]["tracks"][track]
        assert routed["same_track_hit_at_k_count"] == routed["query_count"]
        assert routed["off_track_returned_count"] == 0
        assert routed["failure_bucket_counts"]["track_mismatch"] == 0
        assert routed["retrieval_diagnostic_bucket_counts"]["family_route_missing"] == 0
        assert mixed["off_track_returned_count"] > 0
        assert mixed["retrieval_diagnostic_bucket_counts"]["cross_family_text_dominance"] > 0
    for artifact_key in (
        "summary_json",
        "topk_rows_jsonl",
        "failure_buckets_json",
        "per_track_breakdown_json",
        "silver_1000_diagnostic_overlay_json",
        "source_atom_registry_jsonl",
        "index_search_view_manifest_jsonl",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "full_evidence_bundles",
        "failure_buckets",
        "silver_1000_diagnostic_overlay",
    ):
        assert large_field not in event

    assert "v3_7_2 source registry-backed retrieval smoke report" in current_text
    assert run_id in current_text
    assert "SearchView -> SourceAtom -> EvidenceBundle -> Citation render" in current_flat
    assert "Primary routing mode=query_source_family_routed_for_structured_tracks" in current_flat
    assert "Mixed all-source FAISS top-k is retained only as baseline diagnostic" in current_flat
    assert "silver diagnostic failure distribution" in current_flat
    assert "Promotion readiness remains closed" in current_flat
    assert (
        "Overall status: `diagnostic_source_registry_backed_retrieval_smoke_v3_7_2_report_done`;" in progress
        or "Overall status: `diagnostic_file_grounded_retrieval_eval_v3_8_computed`;" in progress
        or "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_8_file_grounded_retrieval_eval_without_promotion():
    require_v3_8_local_artifacts(STATUS_JSONL)
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_8_file_grounded_retrieval_eval"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_file_grounded_retrieval_eval_v3_8"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_FILE_GROUNDED_RETRIEVAL_EVAL_COMPUTED"
    assert event["run_class"] == "diagnostic_only_file_grounded_retrieval_eval"
    assert event["source_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_7_2_"
        "source_registry_backed_retrieval_smoke_report"
    )
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["answer_generation_metric_computed"] is False
    assert event["answer_metric_computed"] is False
    assert event["prompt_mutation"] is False
    assert event["scorer_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["silver_mutation"] is False
    assert event["promotion_evidence"] is False
    assert event["promotion_gate"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["source_atom_registry_canonical_truth_used_for_metrics"] is True
    assert event["vector_db_role"] == "candidate_generator_only"
    assert event["vector_metadata_used_as_canonical_citation_source"] is False
    assert event["vector_metadata_used_as_evidence_truth"] is False
    assert event["xlsx_pdf_collapsed_score_reported"] is False
    assert set(event["per_source_family"]) == {"PDF", "XLSX"}
    assert event["source_family_counts"]["PDF"] > 0
    assert event["source_family_counts"]["XLSX"] > 0
    assert event["fail_closed_reasons"] == []
    for artifact_key in (
        "summary_json",
        "metrics_json",
        "per_query_jsonl",
        "per_family_json",
        "status_jsonl",
        "progress_doc",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "metrics",
        "per_query_rows",
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "full_evidence_bundles",
    ):
        assert large_field not in event

    assert "v3_8 file-grounded retrieval eval" in current_text
    assert run_id in current_text
    assert "XLSX/PDF retrieval/evidence metrics before answer generation" in current_flat
    assert "No XLSX/PDF collapsed headline score" in current_flat
    assert "FAISS/vector search remains candidate generation only" in current_flat
    assert "SourceAtom/source-registry hydrated" in current_flat
    assert (
        "Overall status: `diagnostic_file_grounded_retrieval_eval_v3_8_computed`;" in progress
        or "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_8_1_evidence_selector_without_promotion():
    require_v3_8_1_local_artifacts(STATUS_JSONL)
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_8_1_evidence_selector_v1"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_evidence_selector_v3_8_1"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_EVIDENCE_SELECTOR_V1_COMPUTED"
    assert event["run_class"] == "diagnostic_only_evidence_selector_v1"
    assert event["source_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_7_2_"
        "source_registry_backed_retrieval_smoke_report"
    )
    assert event["parent_file_grounded_eval_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_8_file_grounded_retrieval_eval"
    )
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["answer_generation_metric_computed"] is False
    assert event["answer_metric_computed"] is False
    assert event["prompt_mutation"] is False
    assert event["scorer_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["silver_mutation"] is False
    assert event["promotion_evidence"] is False
    assert event["promotion_gate"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["source_atom_registry_canonical_truth_used_for_selection"] is True
    assert event["selector_uses_target_source_atom_ids_for_selection"] is False
    assert event["target_source_atom_ids_used_for_metrics_only"] is True
    assert event["vector_db_role"] == "candidate_generator_only"
    assert event["vector_metadata_used_as_canonical_citation_source"] is False
    assert event["vector_metadata_used_as_evidence_truth"] is False
    assert event["xlsx_pdf_collapsed_score_reported"] is False
    assert set(event["per_source_family"]) == {"PDF", "XLSX"}
    assert event["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert event["fail_closed_reasons"] == []
    for artifact_key in (
        "summary_json",
        "metrics_json",
        "per_query_jsonl",
        "per_family_json",
        "status_jsonl",
        "progress_doc",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "metrics",
        "per_query_rows",
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "full_evidence_bundles",
    ):
        assert large_field not in event

    assert "v3_8_1 evidence selector" in current_text
    assert run_id in current_text
    assert "deterministic max-3 citation-capable evidence candidates" in current_flat
    assert "target SourceAtom ids are used for selector metrics only" in current_flat
    assert "No answer generation" in current_flat
    assert (
        "Overall status: `diagnostic_evidence_selector_v3_8_1_computed`;" in progress
        or "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_8_2_oracle_free_file_resolve_without_promotion():
    require_v3_8_2_local_artifacts(STATUS_JSONL)
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_8_2_oracle_free_file_resolve"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_oracle_free_file_resolve_v3_8_2"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_ORACLE_FREE_FILE_RESOLVE_COMPUTED"
    assert event["run_class"] == "diagnostic_only_oracle_free_file_resolve_v1"
    assert event["source_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_7_2_"
        "source_registry_backed_retrieval_smoke_report"
    )
    assert event["parent_file_grounded_eval_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_8_file_grounded_retrieval_eval"
    )
    assert event["parent_evidence_selector_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_8_1_evidence_selector_v1"
    )
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["answer_generation_metric_computed"] is False
    assert event["answer_metric_computed"] is False
    assert event["prompt_mutation"] is False
    assert event["scorer_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["official_qrels_created"] is False
    assert event["official_relevance_labels_created"] is False
    assert event["official_answerability_labels_created"] is False
    assert event["silver_mutation"] is False
    assert event["promotion_evidence"] is False
    assert event["promotion_gate"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["file_resolve_oracle_free"] is True
    assert event["oracle_assisted_file_resolve"] is False
    assert event["oracle_free_input_violation_count"] == 0
    assert event["resolver_uses_target_source_atom_ids_for_selection"] is False
    assert event["target_source_atom_ids_used_for_metrics_only"] is True
    assert event["source_atom_registry_canonical_truth_used_for_resolution"] is True
    assert event["vector_db_role"] == "candidate_generator_only"
    assert event["vector_metadata_used_as_canonical_citation_source"] is False
    assert event["vector_metadata_used_as_evidence_truth"] is False
    assert event["xlsx_pdf_collapsed_score_reported"] is False
    assert set(event["per_source_family"]) == {"PDF", "XLSX"}
    assert event["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert event["fail_closed_reasons"] == []
    for artifact_key in (
        "summary_json",
        "metrics_json",
        "per_query_jsonl",
        "per_family_json",
        "status_jsonl",
        "progress_doc",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "metrics",
        "per_query_rows",
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "full_evidence_bundles",
    ):
        assert large_field not in event

    assert "v3_8_2 oracle-free file resolve" in current_text
    assert run_id in current_text
    assert "ranked source_file/document candidates" in current_flat
    assert "Gold/target SourceAtom ids and manifest targets are metrics-only" in current_flat
    assert "No scoped FAISS answer route" in current_flat
    assert "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
    assert run_id not in measurements
    assert run_id not in triage
