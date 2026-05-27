from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"
STATUS_JSONL = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "status.jsonl"
V4_7_CURRENT_STATUS = "V4_7_PREOFFICIAL_EXTERNAL_HOLDOUT_CANDIDATE_MANIFEST_REGISTRATION_READY"
V4_6_CLOSEOUT_CURRENT_STATUS = V4_7_CURRENT_STATUS
V4_6_12_CURRENT_STATUS = V4_6_CLOSEOUT_CURRENT_STATUS
V4_6_11_CURRENT_STATUS = V4_6_12_CURRENT_STATUS
V4_6_10_CURRENT_STATUS = V4_6_11_CURRENT_STATUS
V4_6_9_CURRENT_STATUS = V4_6_10_CURRENT_STATUS
V4_6_8_CURRENT_STATUS = V4_6_9_CURRENT_STATUS
V4_6_7_CURRENT_STATUS = V4_6_8_CURRENT_STATUS
V4_6_6_CURRENT_STATUS = V4_6_7_CURRENT_STATUS
V4_6_5_CURRENT_STATUS = V4_6_6_CURRENT_STATUS
V4_6_4_CURRENT_STATUS = V4_6_5_CURRENT_STATUS
V4_6_3_CURRENT_STATUS = V4_6_4_CURRENT_STATUS
V4_6_2_CURRENT_STATUS = V4_6_3_CURRENT_STATUS
V4_6_1_CURRENT_STATUS = V4_6_2_CURRENT_STATUS
V4_6_CURRENT_STATUS = V4_6_2_CURRENT_STATUS
V4_5_3_CURRENT_STATUS = V4_6_CURRENT_STATUS
V4_6_SCRIPT = "rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py"
V4_6_1_SCRIPT = "rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py"
V4_6_2_SCRIPT = "rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py"
V4_6_3_SCRIPT = "rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py"
V4_6_4_SCRIPT = "rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod.py"
V4_6_5_SCRIPT = "rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py"
V4_6_6_SCRIPT = "rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py"
V4_6_8_SCRIPT = "rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod.py"
V4_6_9_SCRIPT = "rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod.py"
V4_6_10_SCRIPT = "rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod.py"
V4_6_11_SCRIPT = "rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py"
V4_6_12_SCRIPT = "rag_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod.py"
V4_7_SCRIPT = "rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py"


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


def require_v3_8_3_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return
    message = "missing v3_8_3 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_8_3_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_pdf_xlsx_answer_quality_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return
    message = "missing PDF/XLSX answer-quality local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_PDF_XLSX_ANSWER_QUALITY_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v3_9_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return
    message = "missing v3_9 natural answer-quality local report artifacts: " + ", ".join(
        str(path) for path in missing
    )
    if os.environ.get("RAG_V3_9_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v4_3_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return
    pytest.fail("missing v4_3 local report artifacts: " + ", ".join(str(path) for path in missing))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def test_measurements_doc_keeps_current_artifact_layout_and_v3_comparable_counts():
    text = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    flat_text = " ".join(text.split())

    assert (
        "compact current v3_6_9, v3_7_0, v3_7_1, v3_7_2, v3_8, v3_8_1, v3_8_2, v3_8_3 machine artifacts, and current v3_9 quality artifacts"
        in flat_text
        or "compact current v3_6_9 and later diagnostic artifacts required by the current RAG profile" in flat_text
    )
    assert "latest v3_6_9 SearchUnit/SearchView/SourceAtom refactor artifacts" not in text
    assert "| v3 comparable live measurement |" in text
    assert "PASS `27/29`; PDF `4/4`, XLSX `19/19`, TEXT `4/6`" in text
    assert "PASS `24/29` | Not all-track LLM quality" not in text
    assert "Diagnostic-only; not answer/citation promotion evidence" in text


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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
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
    assert (
        "Overall status: `diagnostic_oracle_free_file_resolve_v3_8_2_computed`;" in progress
        or "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
    )
    assert run_id not in measurements
    assert run_id not in triage


def test_progress_status_and_triage_gate_record_v3_8_3_xlsx_scoped_cell_resolve_without_promotion():
    require_v3_8_3_local_artifacts(STATUS_JSONL)
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_xlsx_scoped_cell_resolve_v3_8_3"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_XLSX_SCOPED_CELL_RESOLVE_COMPUTED"
    assert event["run_class"] == "diagnostic_only_xlsx_scoped_cell_resolve_v1"
    assert event["source_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_7_2_"
        "source_registry_backed_retrieval_smoke_report"
    )
    assert event["parent_file_resolve_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_8_2_oracle_free_file_resolve"
    )
    assert event["file_resolve_gate_run_id"] == (
        "official_answer_citation_agentic_loop_run_v3_8_2_oracle_free_file_resolve"
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
    assert event["xlsx_only"] is True
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
    assert set(event["per_source_family"]) == {"XLSX"}
    assert event["source_family_counts"] == {"XLSX": 344}
    assert event["all_xlsx_query_count"] == 344
    assert event["v3_8_2_gate_row_found_count"] == 344
    assert event["v3_8_2_gate_missing_count"] == 0
    assert event["v3_8_2_gate_duplicate_query_id_count"] == 0
    assert event["fail_closed_reasons"] == []
    for artifact_key in (
        "summary_json",
        "metrics_json",
        "per_query_jsonl",
        "per_family_json",
        "per_family_jsonl",
        "status_jsonl",
        "progress_doc",
    ):
        assert artifact_key in event["artifact_paths"]
    for large_field in (
        "metrics",
        "per_query_rows",
        "per_family_rows",
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "full_evidence_bundles",
    ):
        assert large_field not in event

    assert "v3_8_3 XLSX scoped cell resolve" in current_text
    assert run_id in current_text
    assert "after the v3_8_2 oracle-free workbook/document gate" in current_flat
    assert "Target SourceAtom/manifest locator data is metrics-only" in current_flat
    assert "no scoped answer route" in current_flat
    assert "`official_metric_input_rows=0`" in current_text
    assert "retained XLSX locator status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress or (
        "Overall status: `diagnostic_xlsx_scoped_cell_resolve_v3_8_3_computed`;" in progress
    )
    assert run_id in measurements
    assert "top miss bucket `table_or_range_miss_after_sheet_hit=219`" in measurements
    assert "Metrics + compact miss matrix" in measurements
    assert "sheet@1 baseline -> current" in measurements
    assert run_id in triage
    assert "direct normalized-value query matching" in triage
    assert "official_metric_input_rows=0" in triage


def test_progress_measurements_triage_and_status_record_pdf_xlsx_quality_review_packet_without_promotion():
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "pdf_xlsx_answer_quality_gold_review_packet_final_llm_rewrite_all_llm_15pf_v3"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "pdf_xlsx_answer_quality_gold_review_packet"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "PDF_XLSX_ANSWER_QUALITY_GOLD_REVIEW_PACKET_READY"
    assert event["source_run_label"] == "final_llm_rewrite_all_llm_15pf_v3"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["namespace_mutation"] is False
    assert event["review_packet_row_count"] == 30
    assert event["source_family_counts"] == {"PDF": 15, "XLSX": 15}
    assert event["baseline_quality_pass_counts"] == {"PDF": 0, "XLSX": 0}
    assert event["final_quality_pass_counts"] == {"PDF": 6, "XLSX": 15}
    assert event["aggregate_diagnostic_only"] == "21/30"
    assert event["pdf_residual_count"] == 9
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["user_decision_columns_blank"] is True
    for artifact_key in ("manifest_json", "review_csv", "review_jsonl", "summary_md"):
        assert artifact_key in event["artifact_paths"]

    packet_dir = "ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_final_llm_rewrite_all_llm_15pf_v3"
    assert packet_dir in current_text
    assert "Review packet rows=30" in current_flat
    assert "future scored adapter disabled" in current_flat
    assert run_id in measurements
    assert "PDF residual review taxonomy" in measurements
    assert "User-owned decisions needed next" in measurements
    assert run_id in triage
    assert "answerable, relevance, expected answer, supporting evidence, pass/fail, denominator eligibility, and policy note" in triage
    assert "No official metric input rows are created" in triage


def test_progress_measurements_triage_and_status_record_pdf_answer_ready_evidence_without_promotion():
    require_pdf_xlsx_answer_quality_local_artifacts(STATUS_JSONL)
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "pdf_xlsx_answer_quality_evidence_readiness_packet_answer_ready_pdf_v1_llm_15pf"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "pdf_xlsx_answer_quality_evidence_readiness_packet"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "PDF_XLSX_ANSWER_QUALITY_EVIDENCE_READINESS_PACKET_READY"
    assert event["source_run_label"] == "answer_ready_pdf_v1_llm_15pf"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["namespace_mutation"] is False
    assert event["review_packet_row_count"] == 30
    assert event["source_family_counts"] == {"PDF": 15, "XLSX": 15}
    assert event["final_quality_pass_counts"] == {"PDF": 5, "XLSX": 14}
    assert event["answer_ready_quality_pass_counts"] == {"PDF": 8, "XLSX": 15}
    assert event["aggregate_raw_final_diagnostic_only"] == "19/30"
    assert event["aggregate_answer_ready_diagnostic_only"] == "23/30"
    assert event["pdf_quality_delta_answer_ready_minus_raw_final"] == 3
    assert event["aggregate_quality_delta_answer_ready_minus_raw_final"] == 4
    readiness = event["pdf_evidence_readiness_summary"]
    assert readiness["avg_raw_answer_ready_score"] == 0.1152
    assert readiness["avg_expanded_answer_ready_score"] == 0.3938
    assert readiness["avg_answer_ready_score_delta"] == 0.2786
    assert readiness["bounded_expansion_applied_count"] == 11
    assert readiness["weak_snippet_count"] == 11
    assert readiness["dot_heavy_count"] == 11
    assert readiness["locator_only_count"] == 4
    assert readiness["ocr_ish_count"] == 11
    assert readiness["table_form_like_count"] == 0
    assert readiness["xlsx_context_changed"] is False
    assert readiness["retrieval_miss_assessment"] == "not_recomputed_preselected_sourceatom_evidence_only"
    for artifact_key in (
        "manifest_json",
        "review_csv",
        "review_jsonl",
        "summary_md",
        "source_summary_json",
        "source_responses_jsonl",
        "pdf_evidence_readiness_audit_jsonl",
    ):
        assert artifact_key in event["artifact_paths"]

    packet_dir = "ai/eval/reports/rag-ingestion/quality/pdf_xlsx_answer_quality_review_packet_answer_ready_pdf_v1_llm_15pf"
    assert "pdf_xlsx_answer_quality_evidence_readiness_packet_ready" in current_text
    assert packet_dir in current_text
    assert "PDF raw final answer quality improved from 5/15 to answer-ready 8/15" in current_flat
    assert "Aggregate diagnostic-only quality moved 19/30 -> 23/30 (+4)" in current_flat
    assert "bounded expansion applied 11/15" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert run_id in measurements
    assert "PDF Evidence Readiness" in measurements
    assert "| XLSX | 14/15 | 15/15 | +1 |" in measurements
    assert "`not_recomputed_preselected_sourceatom_evidence_only`" in measurements
    assert run_id in triage
    assert "packet summary/status records" in triage
    assert "Remaining user-owned gold/policy decisions" in triage
    assert "No official metric input rows are created" in triage


def test_progress_measurements_triage_and_status_record_pdf_query_fidelity_packet_without_promotion():
    require_pdf_xlsx_answer_quality_local_artifacts(STATUS_JSONL)
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "pdf_xlsx_answer_quality_query_fidelity_packet_answer_ready_pdf_v1_llm_15pf"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "pdf_xlsx_answer_quality_query_fidelity_packet"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "PDF_XLSX_ANSWER_QUALITY_QUERY_FIDELITY_PACKET_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["namespace_mutation"] is False
    assert event["aggregate_raw_final_diagnostic_only"] == "19/30"
    assert event["aggregate_answer_ready_diagnostic_only"] == "23/30"
    assert event["query_fidelity_summary"]["rows"] == 30
    assert event["query_fidelity_summary"]["headline_included"] == 16
    assert event["query_fidelity_summary"]["excluded"] == 14
    assert event["query_fidelity_summary"]["by_family"]["PDF"]["excluded"] == 3
    assert event["query_fidelity_summary"]["by_family"]["XLSX"]["excluded"] == 11
    assert event["headline_quality_counts"]["query_fidelity_subset"]["rows"] == 16
    assert event["headline_quality_counts"]["query_fidelity_subset"]["answer_ready_pass"] == 11
    assert event["headline_quality_counts"]["query_fidelity_subset"]["by_family"]["PDF"]["answer_ready_pass"] == 7
    assert event["headline_quality_counts"]["query_fidelity_subset"]["by_family"]["XLSX"]["answer_ready_pass"] == 4
    assert event["pdf_delta_audit_summary"]["pdf_case_count"] == 15
    assert event["pdf_delta_audit_summary"]["delta_bucket_counts"]["raw_fail_to_ready_pass"] == 4
    assert event["pdf_residual_review_summary"]["rows"] == 8
    assert event["pdf_residual_review_summary"]["bucket_counts"]["true_answer_failure"] == 0
    assert event["ocr_rationale"]["decision"] == "skipped"
    assert event["user_decision_columns_blank"] is True
    assert "query_approval" in event["user_owned_decisions_needed"]
    for artifact_key in (
        "manifest_json",
        "review_csv",
        "review_jsonl",
        "summary_md",
        "pdf_delta_audit_jsonl",
        "query_fidelity_audit_jsonl",
        "pdf_residual_review_csv",
        "pdf_residual_review_md",
    ):
        assert artifact_key in event["artifact_paths"]

    assert "pdf_xlsx_answer_quality_query_fidelity_packet_ready" in current_text
    assert run_id in triage
    assert "query-fidelity-unverified" in current_flat
    assert "headline-included 16" in current_flat
    assert "| Headline-included fidelity subset | 16 | 9/16 | 11/16 | +2 |" in measurements
    assert "Rows excluded from the headline subset are not deleted" in measurements
    assert "OCR decision: skipped" in measurements
    assert "future official-adjacent adapter is still disabled" in triage


def test_progress_measurements_triage_and_status_record_v3_9_natural_answer_quality_without_promotion():
    dev_metrics_path = (
        ROOT
        / "ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_metrics.json"
    )
    dev_per_family_path = (
        ROOT
        / "ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_per_family.json"
    )
    dev_per_query_path = (
        ROOT
        / "ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_dev_6pf_per_query.jsonl"
    )
    validation_metrics_path = (
        ROOT
        / "ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_metrics.json"
    )
    validation_per_family_path = (
        ROOT
        / "ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_per_family.json"
    )
    validation_per_query_path = (
        ROOT
        / "ai/eval/reports/rag-ingestion/quality/pdf_xlsx_llm_quality_v3_9_natural_answer_quality_validation_6pf_per_query.jsonl"
    )
    require_v3_9_local_artifacts(
        STATUS_JSONL,
        dev_metrics_path,
        dev_per_family_path,
        dev_per_query_path,
        validation_metrics_path,
        validation_per_family_path,
        validation_per_query_path,
    )

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_id = "official_answer_citation_agentic_loop_run_v3_9_natural_answer_quality_diagnostic"
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "natural_answer_quality_diagnostic_v3_9"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "NATURAL_ANSWER_QUALITY_DIAGNOSTIC_V3_9_VALIDATION_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["adapter_enabled"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    for flag in (
        "gold_mutation",
        "label_mutation",
        "qrels_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "namespace_mutation",
        "production_mutation",
    ):
        assert event[flag] is False

    assert event["source_families"] == ["PDF", "XLSX", "TEXT"]
    assert event["source_family_counts"] == {"PDF": 6, "XLSX": 6, "TEXT": 6}
    assert event["dev_split"]["dev_only"] is True
    assert event["dev_split"]["success_evidence_allowed"] is False
    assert event["validation_split"]["success_evidence_allowed"] is True
    assert event["validation_split"]["source_document_disjoint_from_dev"] is True
    assert event["validation_split"]["dev_overlap_document_count"] == 0
    assert event["dev_split"]["raw_pass_to_ready_fail_regression"] == 0
    assert event["validation_split"]["raw_pass_to_ready_fail_regression"] == 0
    assert event["validation_split"]["query_fidelity_included_count"] == 11
    assert event["validation_split"]["query_fidelity_excluded_count"] == 7
    assert event["validation_split"]["generalized_signal"] == {
        "family": "PDF",
        "query_fidelity_included_raw_final": "2/4",
        "query_fidelity_included_answer_ready": "3/4",
        "delta": 1,
    }
    assert event["query_fidelity_excluded_rows_retained"] is True
    assert event["query_fidelity_classifier_synced_between_metrics_and_packet"] is True
    assert event["raw_pass_to_ready_fail_regression_neutralized"] is True
    assert event["non_pdf_answer_ready_reuses_final_locator_response"] is True
    assert "ai/eval/reports/rag-ingestion/status.jsonl" not in event["changed_tracked_files"]
    assert event["ocr_rationale"]["decision"] == "skipped"
    assert event["ocr_rationale"]["ocr_touched"] is False

    hash_contract = {
        "dev_metrics_json": ("dev_metrics_json_sha256", dev_metrics_path),
        "dev_per_family_json": ("dev_per_family_json_sha256", dev_per_family_path),
        "dev_per_query_jsonl": ("dev_per_query_jsonl_sha256", dev_per_query_path),
        "validation_metrics_json": ("validation_metrics_json_sha256", validation_metrics_path),
        "validation_per_family_json": ("validation_per_family_json_sha256", validation_per_family_path),
        "validation_per_query_jsonl": ("validation_per_query_jsonl_sha256", validation_per_query_path),
    }
    for path_key, (hash_key, path) in hash_contract.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    validation_per_family = json.loads(validation_per_family_path.read_text(encoding="utf-8"))
    validation_metrics = json.loads(validation_metrics_path.read_text(encoding="utf-8"))
    dev_metrics = json.loads(dev_metrics_path.read_text(encoding="utf-8"))
    assert dev_metrics["case_selection"]["source_document_disjoint_from_dev"] == "not_applicable_dev_split"
    assert validation_metrics["answer_quality"]["answer_ready_context"]["diagnostic_aggregate_only"] is True
    assert validation_metrics["answer_quality"]["answer_ready_context"]["headline_allowed"] is False
    assert validation_metrics["answer_quality"]["answer_ready_context"]["no_collapsed_cross_family_score"] is True
    assert validation_per_family["no_collapsed_cross_family_score"] is True
    assert validation_per_family["families"]["PDF"]["query_fidelity_included_count"] == 4
    assert validation_per_family["families"]["PDF"]["raw_final_pass_like"] == 2
    assert validation_per_family["families"]["PDF"]["answer_pass_like"] == 5
    assert validation_per_family["families"]["XLSX"]["query_fidelity_excluded_count"] == 5
    assert validation_per_family["families"]["TEXT"]["failure_category_counts"] == {"invalid_json": 1}

    validation_rows = [
        json.loads(line) for line in validation_per_query_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(validation_rows) == 18
    assert sum(1 for row in validation_rows if row["query_fidelity_headline_included"]) == 11
    assert sum(1 for row in validation_rows if not row["query_fidelity_headline_included"]) == 7
    assert all(row["official_metric_input_rows"] == 0 for row in validation_rows)
    assert all("expected_answer" not in row and "supporting_evidence" not in row for row in validation_rows)

    assert "natural_answer_quality_diagnostic_v3_9_validation_ready" in current_text
    assert run_id in current_text
    assert "Query-fidelity included validation is the only generalized signal: PDF `2/4 -> 3/4`" in current_flat
    assert "dev-only" in current_flat
    assert "`table_or_range_miss_after_sheet_hit=219`" in current_text
    assert "`invalid_json=1`" in current_text
    assert "OCR remains skipped" in current_flat
    assert run_id in measurements
    assert "| Validation | PDF | 4 | 2/4 | 3/4 | generalized diagnostic signal (+1) |" in measurements
    assert "| Validation | XLSX | 1 | 1/1 | 1/1 | flat; mostly index-to-content excluded |" in measurements
    assert "Validation query-fidelity excluded rows: `7/18`" in measurements
    assert "raw_pass_to_ready_fail_regression=0" in measurements
    assert run_id in triage
    assert "Generalized validation signal exists only for PDF query-fidelity included" in triage
    assert "Codex-owned diagnostic decisions" in triage
    assert "User-owned decisions remain only" in triage


def test_progress_measurements_triage_and_status_record_v3_9_pdf_xlsx_bottleneck_quality_without_promotion():
    run_id = "official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement"
    artifact_paths = {
        "summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_summary.json",
        "metrics_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_metrics.json",
        "per_family_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_family.json",
        "per_query_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_query.jsonl",
        "failure_taxonomy_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_failure_taxonomy.json",
        "query_fidelity_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_query_fidelity_audit.jsonl",
        "pdf_residual_review_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_pdf_residual_review.jsonl",
        "xlsx_locator_residual_review_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_locator_residual_review.jsonl",
        "split_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_split_manifest.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "pdf_xlsx_bottleneck_quality_improvement_v3_9"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "PDF_XLSX_BOTTLENECK_QUALITY_DIAGNOSTIC_V3_9_VALIDATION_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["adapter_enabled"] is False
    assert event["fine_tuning_executed"] is False
    assert event["promotion_evidence"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    for flag in (
        "gold_mutation",
        "label_mutation",
        "qrels_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "namespace_mutation",
        "production_mutation",
    ):
        assert event[flag] is False

    assert event["source_families"] == ["PDF", "XLSX"]
    assert event["text_comparison_only"] is True
    assert event["source_family_counts"] == {"PDF": 6, "XLSX": 6}
    assert event["dev_split"]["dev_only"] is True
    assert event["dev_split"]["success_evidence_allowed"] is False
    assert event["validation_split"]["source_document_disjoint_from_dev"] is True
    assert event["validation_split"]["dev_overlap_document_count"] == 0
    assert event["validation_split"]["query_fidelity_included_count"] == 5
    assert event["validation_split"]["query_fidelity_excluded_count"] == 7
    assert event["validation_split"]["generalized_signal"]["PDF"] == {
        "delta": 1,
        "generalized": True,
        "query_fidelity_included_answer_ready": "3/4",
        "query_fidelity_included_raw_final": "2/4",
    }
    assert event["validation_split"]["generalized_signal"]["XLSX"]["delta"] == 0
    assert event["query_fidelity_excluded_rows_retained"] is True
    assert event["raw_pass_to_ready_fail_regression_neutralized"] is True
    assert event["ocr_rationale"]["decision"] == "skipped"
    assert event["ocr_rationale"]["ocr_touched"] is False
    assert event["xlsx_locator_metrics"]["table_or_range_resolve"]["@1"]["numerator"] == 22
    assert event["xlsx_locator_metrics"]["cell_or_value_resolve"]["@1"]["numerator"] == 19
    assert event["xlsx_locator_metrics"]["direct_normalized_value_query_matching_used"] is False
    assert event["pdf_metrics"]["file_resolve_reference"]["file_resolve@1"]["numerator"] == 65

    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = path_key.replace("_jsonl", "").replace("_json", "") + "_sha256"
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert "pdf_xlsx_bottleneck_quality_diagnostic_v3_9_validation_ready" in current_text
    assert run_id in current_text
    assert "TEXT is comparison-only" in current_flat
    assert "PDF query-fidelity included validation improved `2/4 -> 3/4`" in current_flat
    assert "XLSX validation included stayed `1/1 -> 1/1`" in current_flat
    assert "`table_or_range_miss_after_sheet_hit=219`" in current_text
    assert "OCR remains skipped" in current_flat
    assert run_id in measurements
    assert "| Validation | PDF | 4 | 2/4 | 3/4 | generalized diagnostic signal (+1) |" in measurements
    assert "| Validation | XLSX | 1 | 1/1 | 1/1 | flat; not generalized locator improvement |" in measurements
    assert "XLSX locator 344-row surface: range@1 `22/344`, cell/value@1 `19/344`" in measurements
    assert "direct normalized-value query matching remains banned" in measurements
    assert run_id in triage
    assert "PDF generalized validation signal exists" in triage
    assert "XLSX generalized answer-quality signal does not exist" in triage
    assert "Fine-tuning remains deferred" in triage
    assert "User-owned decisions remain only" in triage


def test_progress_measurements_triage_and_status_record_v3_9_1_xlsx_table_axis_pdf_file_identity_without_promotion():
    run_id = "official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic"
    artifact_paths = {
        "summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_summary.json",
        "metrics_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_metrics.json",
        "per_family_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_family.json",
        "per_query_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_query.jsonl",
        "failure_taxonomy_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_failure_taxonomy.json",
        "query_fidelity_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_query_fidelity_audit.jsonl",
        "split_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_split_manifest.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_9_1_XLSX_TABLE_AXIS_PDF_FILE_IDENTITY_COMPUTED"
    assert event["run_class"] == "diagnostic_only_xlsx_sourceatom_table_axis_pdf_file_identity"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["answer_generation_metric_computed"] is False
    assert event["answer_metric_computed"] is False
    assert event["fine_tuning_started"] is False
    assert event["promotion_evidence"] is False
    assert event["promotion_gate"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["measurements_doc_updated"] is True
    assert event["triage_doc_updated"] is True
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "production_mutation",
    ):
        assert event[flag] is False
    assert event["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert set(event["per_source_family"]) == {"XLSX", "PDF_FILE_IDENTITY", "PDF_CONTENT", "TEXT"}
    assert event["per_source_family"]["XLSX"]["locator_signal_count_distribution"]["signal_empty_rank1_count"] == 257
    assert event["per_source_family"]["XLSX"]["metrics"]["table_or_range_resolve@1"]["numerator"] == 23
    assert event["per_source_family"]["XLSX"]["metrics"]["cell_or_value_resolve@1"]["numerator"] == 20
    assert event["per_source_family"]["PDF_FILE_IDENTITY"]["metrics"]["file_resolve@1"]["numerator"] == 66
    assert event["per_source_family"]["PDF_FILE_IDENTITY"]["metrics"]["file_resolve@3"]["numerator"] == 129
    assert event["per_source_family"]["PDF_FILE_IDENTITY"]["metrics"]["abstain_rate"]["numerator"] == 182
    assert event["per_source_family"]["PDF_FILE_IDENTITY"]["metrics"]["wrong_file_block_rate"]["numerator"] == 60
    assert event["per_source_family"]["PDF_CONTENT"]["computed_in_this_run"] is False
    assert event["per_source_family"]["TEXT"]["comparison_only"] is True
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["answer_value_in_query_success_evidence_used"] is False
    assert event["index_to_content_success_evidence_used"] is False
    assert event["file_or_source_title_leak_success_evidence_used"] is False
    assert event["fail_closed_reasons"] == []
    hash_keys = {
        "summary_json": "summary_json_sha256",
        "metrics_json": "metrics_json_sha256",
        "per_family_json": "per_family_json_sha256",
        "per_query_jsonl": "per_query_jsonl_sha256",
        "failure_taxonomy_json": "failure_taxonomy_json_sha256",
        "query_fidelity_audit_jsonl": "query_fidelity_audit_jsonl_sha256",
        "split_manifest_json": "split_manifest_json_sha256",
    }
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        assert event["artifact_sha256"][hash_keys[path_key]] == sha256_file(path)

        assert (
            "diagnostic_v3_9_1_xlsx_table_axis_pdf_file_identity_computed" in current_text
            or "diagnostic_v3_9_2_overfit_risk_audit_holdout_reset_ready" in current_text
            or "diagnostic_v3_10_fresh_real_holdout_insufficient_xlsx_table_axis_nonprod_materialized"
            in current_text
            or "diagnostic_v3_11_layered_retrieval_ready" in current_text
            or "diagnostic_v3_12_xlsx_structural_locator_nonprod_improvement_ready" in current_text
            or "diagnostic_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_ready" in current_text
            or "diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod_ready" in current_text
            or "diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready" in current_text
        )
    assert run_id in current_text
    assert "keeps PDF and XLSX metrics separate" in current_flat
    assert "query-fidelity validation included=118/170" in current_flat
    assert "PDF file_resolve@1=66/329" in current_flat
    assert "no fine-tuning" in current_flat
    assert run_id in measurements
    assert "| signal-empty rank1 | 261/300 | 257/300 |" in measurements
    assert "| table_or_range@1 | 2/170 | 3/170 |" in measurements
    assert "| cell_or_value@3 | 6/170 | 9/170 |" in measurements
    assert "| file_resolve@1 | 65/329 | 66/329 |" in measurements
    assert "| abstain | 182/329 | 182/329 |" in measurements
    assert "PDF file identity, separate from answer-ready evidence-window quality" in measurements
    assert run_id in triage
    assert "Direct normalized-value query matching remains banned" in triage
    assert "XLSX `locator_signal_count=0` rank1 pressure" in triage
    assert "Not a fine-tuning handoff yet" in triage
    assert "OCR remains closed" in triage


def test_progress_measurements_triage_and_status_record_v3_9_2_overfit_risk_audit_holdout_reset():
    run_id = "official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset"
    artifact_paths = {
        "summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_summary.json",
        "metrics_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_metrics.json",
        "overfit_risk_by_delta_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_overfit_risk_by_delta.jsonl",
        "seen_surface_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_seen_surface_manifest.json",
        "fresh_holdout_candidate_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_fresh_holdout_candidate_manifest.json",
        "fresh_holdout_split_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_fresh_holdout_split_manifest.json",
        "query_fidelity_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_query_fidelity_audit.jsonl",
        "leakage_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_leakage_audit.jsonl",
        "architecture_scope_assessment_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_architecture_scope_assessment.json",
        "failure_taxonomy_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_failure_taxonomy.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_9_2_overfit_risk_audit_and_blind_holdout_reset"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_9_2_OVERFIT_RISK_AUDIT_AND_BLIND_HOLDOUT_RESET_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["fine_tuning_executed"] is False
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["label_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["production_mutation"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["seen_validation_downgraded_to_seen_validation_only"] is True
    assert event["fresh_holdout_sufficient"] is False
    assert event["real_unseen_holdout_sufficient"] is False
    assert event["synthetic_ood_guard_used"] is True
    assert event["product_success_evidence_allowed"] is False
    assert event["xlsx_nonprod_rematerialization_needed"] is True
    assert event["pdf_file_identity_answer_window_kept_separate"] is True
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = (
            "summary_json_sha256"
            if path_key == "summary_json"
            else path_key.replace("_jsonl", "").replace("_json", "") + "_sha256"
        )
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert (
        "Overall status: `diagnostic_v3_9_2_overfit_risk_audit_holdout_reset_ready`;" in progress
        or "Overall status: `diagnostic_v3_10_fresh_real_holdout_insufficient_xlsx_table_axis_nonprod_materialized`;"
        in progress
        or "Overall status: `diagnostic_v3_11_layered_retrieval_ready`;" in progress
        or "Overall status: `diagnostic_v3_12_xlsx_structural_locator_nonprod_improvement_ready`;" in progress
        or "Overall status: `diagnostic_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod_ready`;" in progress
        or "Overall status: `diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_16_final_llm_answer_quality_review_nonprod_ready`;" in progress
        or "Overall status: `diagnostic_v3_17_user_locator_rough_query_answer_quality_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_18_agent_runtime_tool_invocation_contract_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_19_locator_ambiguity_deictic_response_policy_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_20_live_runtime_like_db_index_cache_smoke_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_21_agent_runtime_llm_io_observability_packet_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod_ready`;"
        in progress
        or "Overall status: `v4_source_grounded_runtime_locator_and_finetune_readiness_opened`;"
        in progress
        or "Overall status: `diagnostic_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_5_finetune_readiness_packet_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod_ready`;"
        in progress
        or f"Overall status: `{V4_6_CURRENT_STATUS}`;" in progress
        or "Overall status: `phase1_diagnostic_contract_closure_after_v3_22_ready`;"
        in progress
    )
    assert "seen-validation-only" in current_flat
    assert "PDF document-disjoint=0, XLSX workbook-disjoint=0" in current_flat
    assert "synthetic OOD anti-overfit guard only" in current_flat
    assert "overlay/rerank-only" in current_flat
    assert run_id in measurements
    assert "Fresh real holdout is insufficient" in measurements
    assert "| synthetic OOD guard candidates | 14 |" in measurements
    assert "no v3_9_1 improvement is preserved as future product success evidence" in measurements
    assert run_id in triage
    assert "`likely_general` future-success evidence count is `0`" in triage
    assert "Leakage-adjacent" in triage
    assert "Pause performance success claims" in triage


def test_progress_measurements_triage_and_status_record_v3_10_fresh_holdout_xlsx_table_axis_nonprod():
    run_id = "official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization"
    artifact_paths = {
        "summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_summary.json",
        "metrics_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_metrics.json",
        "fresh_real_holdout_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_fresh_real_holdout_manifest.json",
        "seen_surface_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_seen_surface_manifest.json",
        "query_fidelity_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_query_fidelity_audit.jsonl",
        "leakage_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_leakage_audit.jsonl",
        "xlsx_nonprod_sourceatom_manifest_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_nonprod_sourceatom_manifest.jsonl",
        "xlsx_nonprod_searchunit_manifest_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_nonprod_searchunit_manifest.jsonl",
        "xlsx_nonprod_index_build_summary_json": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_nonprod_index_build_summary.json",
        "xlsx_table_axis_eval_per_query_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_table_axis_eval_per_query.jsonl",
        "failure_taxonomy_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_failure_taxonomy.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type")
        == "diagnostic_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_10_FRESH_REAL_HOLDOUT_INSUFFICIENT_XLSX_TABLE_AXIS_NONPROD_MATERIALIZED"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["fresh_real_holdout_acquired"] is False
    assert event["fresh_real_holdout_sufficient"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["xlsx_nonprod_table_axis_materialized"] is True
    assert event["xlsx_nonprod_overlay_only"] is False
    assert event["xlsx_nonprod_namespace"] == "rag-data-xlsx-table-axis-ood-nonprod-v1"
    assert event["pdf_file_identity_baseline_only"] is True
    assert event["pdf_answer_ready_evidence_window_metric_computed"] is False
    assert event["ocr_touched"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = (
            "summary_json_sha256"
            if path_key == "summary_json"
            else path_key.replace("_jsonl", "").replace("_json", "") + "_sha256"
        )
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert (
        "Overall status: `diagnostic_v3_10_fresh_real_holdout_insufficient_xlsx_table_axis_nonprod_materialized`;"
        in progress
        or "Overall status: `diagnostic_v3_11_layered_retrieval_ready`;" in progress
        or "Overall status: `diagnostic_v3_12_xlsx_structural_locator_nonprod_improvement_ready`;" in progress
        or "Overall status: `diagnostic_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod_ready`;" in progress
        or "Overall status: `diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_16_final_llm_answer_quality_review_nonprod_ready`;" in progress
        or "Overall status: `diagnostic_v3_17_user_locator_rough_query_answer_quality_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_18_agent_runtime_tool_invocation_contract_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_19_locator_ambiguity_deictic_response_policy_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_20_live_runtime_like_db_index_cache_smoke_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_21_agent_runtime_llm_io_observability_packet_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod_ready`;"
        in progress
        or "Overall status: `v4_source_grounded_runtime_locator_and_finetune_readiness_opened`;"
        in progress
        or "Overall status: `diagnostic_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_5_finetune_readiness_packet_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready`;"
        in progress
        or "Overall status: `diagnostic_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod_ready`;"
        in progress
        or f"Overall status: `{V4_6_CURRENT_STATUS}`;" in progress
        or "Overall status: `phase1_diagnostic_contract_closure_after_v3_22_ready`;"
        in progress
    )
    assert "seen-validation-only" in current_flat
    assert "Fresh real holdout is still insufficient" in current_flat
    assert "PDF source-document-disjoint=0, XLSX workbook-disjoint=0" in current_flat
    assert "not overlay-only" in current_flat
    assert "answer-ready evidence-window and OCR closed" in current_flat
    assert run_id in measurements
    assert "Synthetic OOD guard: 200 query candidates" in measurements
    assert "| signal-empty rank1 | 257/300 | 0/300 | 0/0 |" in measurements
    assert "v3_9_1 seen reference file_resolve@1=66/329" in measurements
    assert run_id in triage
    assert "There is no performance success claim in v3_10" in triage
    assert "PDF work is limited to file identity baseline accounting" in triage


def test_progress_measurements_triage_and_status_record_v3_11_layered_retrieval():
    run_id = "official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic"
    artifact_paths = {
        "summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_summary.json",
        "bootstrap_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_bootstrap.json",
        "metrics_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_metrics.json",
        "per_family_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_family.json",
        "per_query_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_query.jsonl",
        "layer_trace_sample_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_layer_trace_sample.jsonl",
        "query_routing_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_query_routing_audit.jsonl",
        "query_guardrail_summary_json": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_query_guardrail_summary.json",
        "selected_evidence_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_selected_evidence.jsonl",
        "failure_taxonomy_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_failure_taxonomy.json",
        "guardrail_audit_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_guardrail_audit.json",
        "holdout_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_holdout_manifest.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == "diagnostic_v3_11_layered_retrieval"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_11_LAYERED_RETRIEVAL_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["fresh_real_holdout_sufficient"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["answer_generation_executed"] is False
    assert event["pdf_file_identity_answer_window_kept_separate"] is True
    assert event["pdf_bbox_correctness_metric_computed"] is False
    assert event["ocr_touched"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["layers_skipped_by_design"] == ["L8_GENERATION_OR_DETERMINISTIC_EXECUTION"]
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = (
            "summary_json_sha256"
            if path_key == "summary_json"
            else path_key.replace("_jsonl", "").replace("_json", "") + "_sha256"
        )
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert (
        "diagnostic_v3_11_layered_retrieval_ready" in progress
        or "diagnostic_v3_12_xlsx_structural_locator_nonprod_improvement_ready" in progress
        or "diagnostic_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_ready" in progress
        or "diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod_ready" in progress
        or "diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready" in progress
    )
    assert "L0 query routing through L7 answer-ready context plus L9 metrics" in current_flat
    assert "leaves L8 generation closed" in current_flat
    assert run_id in measurements
    assert "Layer contract: L0 query routing" in measurements
    assert "| XLSX | table_or_range@3 | 29/344 |" in measurements
    assert "| PDF file identity | file_resolve@1 | 66/329 |" in measurements
    assert "bbox correctness and answer-ready window sufficiency are explicitly not computed" in measurements
    assert run_id in triage
    assert "XLSX remains blocked mainly at table/range and cell locator layers" in triage
    assert "PDF remains a file-identity-first bottleneck" in triage
    assert "no product performance or promotion claim is made" in triage


def test_progress_measurements_triage_and_status_record_v3_12_xlsx_structural_locator():
    run_id = "official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement"
    artifact_paths = {
        "summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_summary.json",
        "metrics_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_metrics.json",
        "per_family_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_family.json",
        "xlsx_structural_locator_eval_per_query_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_structural_locator_eval_per_query.jsonl",
        "xlsx_score_components_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_score_components.jsonl",
        "xlsx_layer_trace_per_query_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_layer_trace_per_query.jsonl",
        "xlsx_nonprod_sourceatom_manifest_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_nonprod_sourceatom_manifest.jsonl",
        "xlsx_nonprod_searchunit_manifest_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_nonprod_searchunit_manifest.jsonl",
        "xlsx_nonprod_index_build_summary_json": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_xlsx_nonprod_index_build_summary.json",
        "leakage_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_leakage_audit.jsonl",
        "failure_taxonomy_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_failure_taxonomy.json",
        "guardrail_audit_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_guardrail_audit.json",
        "holdout_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_holdout_manifest.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_12_xlsx_structural_locator_nonprod_improvement"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_12_XLSX_STRUCTURAL_LOCATOR_NONPROD_IMPROVEMENT_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["fresh_real_holdout_sufficient"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["answer_generation_executed"] is False
    assert event["index_namespace"] == "rag-data-xlsx-structural-locator-nonprod-v1"
    assert event["source_index_namespace"] == "rag-data-xlsx-table-axis-ood-nonprod-v1"
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["raw_answer_value_for_query_scoring_used"] is False
    assert event["protected_namespaces_touched"] == []
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = (
            "summary_json_sha256"
            if path_key == "summary_json"
            else path_key.replace("_jsonl", "").replace("_json", "") + "_sha256"
        )
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert (
        "diagnostic_v3_12_xlsx_structural_locator_nonprod_improvement_ready" in progress
        or "diagnostic_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_ready" in progress
        or "diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod_ready" in progress
        or "diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready" in progress
    )
    assert "table-boundary candidates, header/axis alias propagation" in current_flat
    assert "fresh workbook-disjoint holdout remains required" in current_flat
    assert run_id in measurements
    assert "| cell_or_value@1 | 20/344 | 21/344 |" in measurements
    assert "| structural-signal-empty rank1 | n/a | 0/300 |" in measurements
    assert "| table_or_range@1 gain/loss | n/a | +1/-1 |" in measurements
    assert "| cell_or_value@1 gain/loss | n/a | +1/-0 |" in measurements
    assert "Delta is diagnostic only" in measurements
    assert run_id in triage
    assert "Merged-header lift is not claimed" in triage
    assert "no product success or promotion claim is allowed" in triage


def test_progress_measurements_triage_and_status_record_v3_13_pdf_file_identity_structural_locator():
    run_id = "official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment"
    artifact_paths = {
        "summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_summary.json",
        "metrics_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_metrics.json",
        "per_family_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_family.json",
        "pdf_structural_locator_eval_per_query_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_pdf_structural_locator_eval_per_query.jsonl",
        "pdf_layer_trace_per_query_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_pdf_layer_trace_per_query.jsonl",
        "pdf_score_components_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_pdf_score_components.jsonl",
        "pdf_nonprod_manifest_summary_json": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_pdf_nonprod_manifest_summary.json",
        "leakage_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_leakage_audit.jsonl",
        "failure_taxonomy_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_failure_taxonomy.json",
        "guardrail_audit_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_guardrail_audit.json",
        "holdout_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_holdout_manifest.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_13_pdf_file_identity_structural_locator_nonprod_alignment"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_13_PDF_FILE_IDENTITY_STRUCTURAL_LOCATOR_NONPROD_ALIGNMENT_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["fresh_real_holdout_sufficient"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["answer_generation_executed"] is False
    assert event["deterministic_answer_execution_executed"] is False
    assert event["index_namespace"] == "rag-data-pdf-structural-locator-nonprod-v1"
    assert event["source_index_namespace"] == "rag-data-all-source-citable-nonprod-v1"
    assert event["pdf_file_identity_answer_window_kept_separate"] is True
    assert event["pdf_bbox_correctness_metric_computed"] is False
    assert event["xlsx_v3_12_control_lane_only"] is True
    assert event["protected_namespaces_touched"] == []
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = (
            "summary_json_sha256"
            if path_key == "summary_json"
            else path_key.replace("_jsonl", "").replace("_json", "") + "_sha256"
        )
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert (
        "diagnostic_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_ready" in progress
        or "diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod_ready" in progress
        or "diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready" in progress
    )
    assert "PDF L2 file identity confidence diagnostics" in current_flat
    assert "same-page bounded evidence-window candidates" in current_flat
    assert "XLSX v3_12 remains visible as a no-regression/control lane only" in current_flat
    assert run_id in measurements
    assert "| PDF file identity | file_resolve@1 |" in measurements
    assert "| PDF evidence window | bbox correctness | not computed |" in measurements
    assert "| XLSX v3_12 control | optimized in v3_13 | false |" in measurements
    assert "wrong-file forcing delta" in measurements
    assert run_id in triage
    assert "accepted wrong rank1 with target in top3" in triage
    assert "bbox correctness is not claimed" in triage
    assert "fresh real PDF source-document-disjoint holdout remains required" in triage


def test_progress_measurements_triage_and_status_record_v3_14_layered_retrieval_runtime_adapter():
    run_id = "official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod"
    artifact_paths = {
        "summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_summary.json",
        "metrics_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_metrics.json",
        "per_family_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_family.json",
        "per_query_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_query.jsonl",
        "layer_trace_per_query_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_layer_trace_per_query.jsonl",
        "latency_summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_latency_summary.json",
        "candidate_flow_summary_json": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_candidate_flow_summary.json",
        "failure_taxonomy_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_failure_taxonomy.json",
        "guardrail_audit_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_guardrail_audit.json",
        "leakage_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_leakage_audit.jsonl",
        "holdout_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_holdout_manifest.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_14_LAYERED_RETRIEVAL_RUNTIME_ADAPTER_NONPROD_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["fresh_real_holdout_sufficient"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["answer_generation_executed"] is False
    assert event["deterministic_answer_execution_executed"] is False
    assert event["L8_executed"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["total_pdf_rows"] == 329
    assert event["total_xlsx_rows"] == 344
    assert event["total_runtime_adapter_rows"] == 673
    assert event["layers_skipped_by_design"] == ["L8_GENERATION_OR_DETERMINISTIC_EXECUTION"]
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = (
            "summary_json_sha256"
            if path_key == "summary_json"
            else path_key.replace("_jsonl", "").replace("_json", "") + "_sha256"
        )
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert (
        "diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod_ready" in progress
        or "diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready" in progress
    )
    assert "runs L0 through L7 over the common PDF/XLSX runtime adapter surface" in current_flat
    assert "raw_file_query_time_accessed=false" in current_flat
    assert "L8 generation and deterministic answer execution stay closed" in current_flat
    assert "fresh real source-document/workbook-disjoint holdout remains unavailable" in current_flat
    assert run_id in measurements
    assert "| total runtime adapter rows | 673 |" in measurements
    assert "| PDF rows | 329 |" in measurements
    assert "| XLSX rows | 344 |" in measurements
    assert "| raw_file_query_time_accessed | false |" in measurements
    assert "| L8_executed | false |" in measurements
    assert "Per-family latency and candidate-count summaries are reported separately" in measurements
    assert run_id in triage
    assert "runtime adapter success is trace completeness, not score lift" in triage
    assert "PDF and XLSX remain separated" in triage
    assert "future scored adapter remains disabled" in triage


def test_progress_measurements_triage_and_status_record_v3_15_xlsx_l3_table_range_locator():
    run_id = "official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement"
    artifact_paths = {
        "summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_summary.json",
        "metrics_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_metrics.json",
        "per_family_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_family.json",
        "per_query_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_per_query.jsonl",
        "layer_trace_per_query_jsonl": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_layer_trace_per_query.jsonl",
        "latency_summary_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_latency_summary.json",
        "candidate_flow_summary_json": ROOT
        / f"ai/eval/reports/rag-ingestion/{run_id}_candidate_flow_summary.json",
        "failure_taxonomy_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_failure_taxonomy.json",
        "guardrail_audit_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_guardrail_audit.json",
        "leakage_audit_jsonl": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_leakage_audit.jsonl",
        "holdout_manifest_json": ROOT / f"ai/eval/reports/rag-ingestion/{run_id}_holdout_manifest.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_15_XLSX_L3_TABLE_RANGE_LOCATOR_NONPROD_IMPROVEMENT_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert event["fresh_real_holdout_sufficient"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["answer_generation_executed"] is False
    assert event["deterministic_answer_execution_executed"] is False
    assert event["L8_executed"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["total_pdf_rows"] == 0
    assert event["total_xlsx_rows"] == 344
    assert event["total_runtime_adapter_rows"] == 344
    assert event["optimization_surface"] == "XLSX_L3_TABLE_RANGE_LOCATOR_ONLY"
    assert event["layers_skipped_by_design"] == ["L8_GENERATION_OR_DETERMINISTIC_EXECUTION"]
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = (
            "summary_json_sha256"
            if path_key == "summary_json"
            else path_key.replace("_jsonl", "").replace("_json", "") + "_sha256"
        )
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert "diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready" in progress
    assert "built on v3_14 XLSX runtime adapter outputs" in current_flat
    assert "XLSX L3 table/range locator only" in current_flat
    assert "raw_file_query_time_accessed=false" in current_flat
    assert "SourceAtom registry remains canonical truth" in current_flat
    assert "SearchView/vector payload remains candidate-only" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert run_id in measurements
    assert "| XLSX rows | 344 |" in measurements
    assert "| PDF rows | 0 |" in measurements
    assert "| raw_file_query_time_accessed | false |" in measurements
    assert "| L8_executed | false |" in measurements
    assert "table_or_range@1/@3 are metrics-only diagnostics" in measurements
    assert "from the v3_12 reference eval artifact" in measurements
    assert run_id in triage
    assert "v3_15 optimizes table/range candidate availability, not direct value matching" in triage
    assert "PDF is excluded from the optimization surface" in triage
    assert "fresh workbook-disjoint holdout remains required" in triage


def test_progress_measurements_triage_and_status_record_v3_16_final_llm_answer_quality_review_packet():
    run_id = "official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod"
    output_dir = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id
    artifact_paths = {
        "summary_json": output_dir / "summary.json",
        "metrics_json": output_dir / "metrics.json",
        "per_family_json": output_dir / "per_family.json",
        "per_query_jsonl": output_dir / "per_query.jsonl",
        "responses_jsonl": output_dir / "responses.jsonl",
        "review_packet_csv": output_dir / "review_packet.csv",
        "review_packet_jsonl": output_dir / "review_packet.jsonl",
        "guardrail_audit_json": output_dir / "guardrail_audit.json",
        "leakage_audit_jsonl": output_dir / "leakage_audit.jsonl",
        "prompt_manifest_json": output_dir / "prompt_manifest.json",
        "local_llm_readiness_json": output_dir / "local_llm_readiness.json",
        "runtime_materialization_plan_json": output_dir / "runtime_materialization_plan.json",
        "latency_budget_contract_json": output_dir / "latency_budget_contract.json",
        "per_layer_online_work_audit_jsonl": output_dir / "per_layer_online_work_audit.jsonl",
        "cache_key_contract_json": output_dir / "cache_key_contract.json",
        "forbidden_query_time_work_audit_json": output_dir / "forbidden_query_time_work_audit.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_16_FINAL_LLM_ANSWER_QUALITY_REVIEW_NONPROD_READY"
    assert event["diagnostic_only"] is True
    assert event["L8_generation_executed"] is True
    assert event["deterministic_official_execution"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert event["generated_response_count"] == 60
    assert event["review_packet_row_count"] == 60
    assert event["parse_ok_count"] + event["invalid_json_count"] == 60
    assert event["truncated_or_malformed_response_count"] == event["invalid_json_count"]
    assert event["latency_budget"]["budget_role"] == "diagnostic_only"
    assert event["latency_budget"]["promotion_evidence"] is False
    assert event["latency_budget"]["l8_generation_latency_reported_separately"] is True
    assert event["runtime_materialization"]["L8_FINAL_LLM_ANSWER_GENERATION"] == "query_time_cacheable"
    assert "prompt_template" not in event
    assert "responses" not in event
    assert "per_query_rows" not in event
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = "summary_json_sha256" if path_key == "summary_json" else f"{path_key}_sha256"
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert "diagnostic_v3_16_final_llm_answer_quality_review_nonprod_ready" in progress
    assert "opens L8 only for local LLM answer generation" in current_flat
    assert "deterministic_official_execution=false" in current_flat
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "SourceAtom registry remains canonical truth" in current_flat
    assert "SearchView/vector payload remains candidate-only" in current_flat
    assert "Runtime materialization and latency-budget artifacts classify L0-L8 online work" in current_flat
    assert run_id in measurements
    assert "| generated_response_count | 60 |" in measurements
    assert "| parse_ok_count |" in measurements
    assert "| invalid_json_count |" in measurements
    assert "| p95_llm_elapsed_ms |" in measurements
    assert "| official_metric_input_rows | 0 |" in measurements
    assert "| L8_generation_executed | true |" in measurements
    assert "| deterministic_official_execution | false |" in measurements
    assert "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED" in measurements
    assert "runtime_materialization_plan.json" in measurements
    assert "latency_budget_contract.json" in measurements
    assert run_id in triage
    assert "not retrieval improvement and not official scoring" in triage
    assert "User-owned review fields remain blank" in triage
    assert "fails closed" in triage
    assert "latency budget is diagnostic-only" in triage


def test_progress_measurements_triage_and_status_record_v3_17_user_locator_rough_query_packet():
    run_id = "official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod"
    output_dir = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id
    artifact_paths = {
        "summary_json": output_dir / "summary.json",
        "metrics_json": output_dir / "metrics.json",
        "per_family_json": output_dir / "per_family.json",
        "per_query_jsonl": output_dir / "per_query.jsonl",
        "responses_jsonl": output_dir / "responses.jsonl",
        "review_packet_csv": output_dir / "review_packet.csv",
        "review_packet_jsonl": output_dir / "review_packet.jsonl",
        "guardrail_audit_json": output_dir / "guardrail_audit.json",
        "leakage_audit_jsonl": output_dir / "leakage_audit.jsonl",
        "prompt_manifest_json": output_dir / "prompt_manifest.json",
        "user_locator_parse_audit_jsonl": output_dir / "user_locator_parse_audit.jsonl",
        "user_locator_resolution_audit_jsonl": output_dir / "user_locator_resolution_audit.jsonl",
        "rough_query_bucket_audit_jsonl": output_dir / "rough_query_bucket_audit.jsonl",
        "tool_registry_json": output_dir / "tool_registry.json",
        "route_policy_audit_jsonl": output_dir / "route_policy_audit.jsonl",
        "runtime_materialization_plan_json": output_dir / "runtime_materialization_plan.json",
        "latency_budget_contract_json": output_dir / "latency_budget_contract.json",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_17_user_locator_rough_query_answer_quality_nonprod"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_17_USER_LOCATOR_ROUGH_QUERY_ANSWER_QUALITY_NONPROD_READY"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_text_used"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert event["user_locator_query_count"] > 0
    assert event["user_locator_resolved_count"] > 0
    assert event["user_locator_unresolved_count"] > 0
    assert event["rough_query_count"] > 0
    assert event["rough_query_abstain_count"] > 0
    assert event["unique_query_hash_count"] > 0
    assert event["duplicate_query_hash_groups"]
    assert event["route_policy_lanes"] == ["user_locator", "rough_query", "hybrid", "unsupported"]
    assert event["tool_registry_version"] == "rag_tool_registry_l0_l8_v1"
    assert event["runtime_materialization"]["L8_FINAL_LLM_ANSWER_GENERATION"] == "query_time_cacheable"
    assert "prompt_template" not in event
    assert "responses" not in event
    assert "per_query_rows" not in event
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = "summary_json_sha256" if path_key == "summary_json" else f"{path_key}_sha256"
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert "diagnostic_v3_17_user_locator_rough_query_answer_quality_nonprod_ready" in progress
    assert "user-provided locator text is query-owned only" in current_flat
    assert "target_locator_used=false" in current_flat
    assert "gold_locator_used=false" in current_flat
    assert "expected_supporting_text_used=false" in current_flat
    assert "SourceAtom registry remains canonical truth" in current_flat
    assert "SearchView/vector payload remains candidate-only" in current_flat
    assert "bounded ToolRegistry" in current_flat
    assert run_id in measurements
    assert "| user_locator_query_count |" in measurements
    assert "| user_locator_resolved_count |" in measurements
    assert "| user_locator_unresolved_count |" in measurements
    assert "| rough_query_count |" in measurements
    assert "| rough_query_abstain_count |" in measurements
    assert "| unique_query_hash_count |" in measurements
    assert "| official_metric_input_rows | 0 |" in measurements
    assert "tool_registry.json" in measurements
    assert "route_policy_audit.jsonl" in measurements
    assert run_id in triage
    assert "rough, terse, incomplete user queries" in triage
    assert "locator-bounds answerability" in triage
    assert "User-owned review fields remain blank" in triage
    assert "not official scoring" in triage


def test_progress_measurements_triage_and_status_record_v3_18_agent_runtime_tool_invocation_contract():
    run_id = "official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod"
    output_dir = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id
    artifact_paths = {
        "summary_json": output_dir / "summary.json",
        "metrics_json": output_dir / "metrics.json",
        "per_query_jsonl": output_dir / "per_query.jsonl",
        "agent_tool_call_trace_jsonl": output_dir / "agent_tool_call_trace.jsonl",
        "route_policy_audit_jsonl": output_dir / "route_policy_audit.jsonl",
        "runtime_contract_audit_jsonl": output_dir / "runtime_contract_audit.jsonl",
        "guardrail_audit_json": output_dir / "guardrail_audit.json",
        "leakage_audit_jsonl": output_dir / "leakage_audit.jsonl",
        "review_packet_csv": output_dir / "review_packet.csv",
        "review_packet_jsonl": output_dir / "review_packet.jsonl",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_18_agent_runtime_tool_invocation_contract_nonprod"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_18_AGENT_RUNTIME_TOOL_INVOCATION_CONTRACT_NONPROD_READY"
    assert event["diagnostic_only"] is True
    assert event["agent_runtime_nonprod"] is True
    assert event["agent_runtime_product_ready"] is False
    assert event["tool_registry_only_invocation"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_text_used"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["route_policy_lanes"] == ["user_locator", "rough_query", "hybrid", "unsupported"]
    assert event["tool_registry_version"] == "rag_tool_registry_l0_l8_v1"
    assert event["agent_tool_call_trace_row_count"] > 0
    assert event["review_packet_row_count"] > 0
    assert event["user_locator_query_count"] > 0
    assert event["rough_query_count"] > 0
    assert event["rough_query_abstain_count"] >= 0
    assert event["over_abstain_review_candidate_count"] >= 0
    assert event["unsupported_route_count"] > 0
    assert event["runtime_contract_violation_count"] == 0
    assert "prompt_template" not in event
    assert "responses" not in event
    assert "per_query_rows" not in event
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = "summary_json_sha256" if path_key == "summary_json" else f"{path_key}_sha256"
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert "diagnostic_v3_18_agent_runtime_tool_invocation_contract_nonprod_ready" in progress
    assert "non-production agent-runtime invocation surface" in current_flat
    assert "registered ToolSpec" in current_flat
    assert "unsupported and contract-violating routes fail closed" in current_flat
    assert "SourceAtom/EvidenceBundle remains canonical evidence truth" in current_flat
    assert "not production routing" in current_flat
    assert "official_metric_input_rows | 0" in measurements
    assert "agent_tool_call_trace.jsonl" in measurements
    assert "runtime_contract_audit.jsonl" in measurements
    assert "over_abstain_review_candidate_count" in measurements
    assert run_id in triage
    assert "LOCATION_NOT_FOUND" in triage
    assert "AMBIGUOUS_LOCATOR" in triage
    assert "OUT_OF_BOUNDS_LOCATOR" in triage
    assert "UNSUPPORTED_LOCATOR_FORMAT" in triage
    assert "CONTRACT_VIOLATION" in triage
    assert "not human answerability labels" in triage
    assert "Rough-query over-abstain diagnostics remain review aids" in triage


def test_progress_measurements_triage_and_status_record_v3_19_locator_ambiguity_deictic_response_policy():
    run_id = "official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod"
    output_dir = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id
    artifact_paths = {
        "summary_json": output_dir / "summary.json",
        "metrics_json": output_dir / "metrics.json",
        "per_query_jsonl": output_dir / "per_query.jsonl",
        "agent_tool_call_trace_jsonl": output_dir / "agent_tool_call_trace.jsonl",
        "route_policy_audit_jsonl": output_dir / "route_policy_audit.jsonl",
        "runtime_contract_audit_jsonl": output_dir / "runtime_contract_audit.jsonl",
        "user_response_policy_audit_jsonl": output_dir / "user_response_policy_audit.jsonl",
        "guardrail_audit_json": output_dir / "guardrail_audit.json",
        "leakage_audit_jsonl": output_dir / "leakage_audit.jsonl",
        "review_packet_jsonl": output_dir / "review_packet.jsonl",
        "review_packet_csv": output_dir / "review_packet.csv",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_19_locator_ambiguity_deictic_response_policy_nonprod"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_19_LOCATOR_AMBIGUITY_DEICTIC_RESPONSE_POLICY_NONPROD_READY"
    assert event["diagnostic_only"] is True
    assert event["agent_runtime_nonprod"] is True
    assert event["agent_runtime_product_ready"] is False
    assert event["tool_registry_only_invocation"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_text_used"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["route_policy_lanes"] == ["user_locator", "rough_query", "hybrid", "unsupported"]
    assert event["tool_registry_version"] == "rag_tool_registry_l0_l8_v1"
    assert event["review_packet_row_count"] > 0
    assert event["agent_tool_call_trace_row_count"] > 0
    assert event["user_response_policy_audit_row_count"] > 0
    assert event["ambiguous_locator_nonabstained_count"] == 0
    assert event["page_only_locator_nonabstained_count"] == 0
    assert event["sheet_only_locator_nonabstained_count"] == 0
    assert event["deictic_context_missing_nonabstained_count"] == 0
    assert event["duplicate_query_hash_count"] >= 1
    assert event["duplicate_query_text_group_count"] >= 1
    assert event["runtime_contract_violation_count"] == 0
    assert "prompt_template" not in event
    assert "responses" not in event
    assert "per_query_rows" not in event
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = "summary_json_sha256" if path_key == "summary_json" else f"{path_key}_sha256"
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert "diagnostic_v3_19_locator_ambiguity_deictic_response_policy_nonprod_ready" in progress
    assert "page-only" in current_flat
    assert "sheet-only" in current_flat
    assert "Korean deictic rough queries" in current_flat
    assert "SourceAtom/EvidenceBundle remains canonical evidence truth" in current_flat
    assert "SearchView/vector payload remains candidate-only" in current_flat
    assert "not production routing" in current_flat
    assert "user_response_policy_audit.jsonl" in measurements
    assert "| ambiguous_locator_nonabstained_count | 0 |" in measurements
    assert "| page_only_locator_nonabstained_count | 0 |" in measurements
    assert "| sheet_only_locator_nonabstained_count | 0 |" in measurements
    assert "| deictic_context_missing_nonabstained_count | 0 |" in measurements
    assert "| official_metric_input_rows | 0 |" in measurements
    assert run_id in triage
    assert "CONTEXT_REQUIRED" in triage
    assert "BOUNDED_BROAD_RANGE" in triage
    assert "Duplicate query text" in triage
    assert "No target/gold/supporting/expected locator text" in triage
    assert "metrics.json` carries the full bucket maps" in measurements


def test_progress_measurements_triage_and_status_record_v3_20_live_runtime_like_db_index_cache_smoke():
    run_id = "official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod"
    output_dir = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id
    artifact_paths = {
        "summary_json": output_dir / "summary.json",
        "metrics_json": output_dir / "metrics.json",
        "per_query_jsonl": output_dir / "per_query.jsonl",
        "agent_tool_call_trace_jsonl": output_dir / "agent_tool_call_trace.jsonl",
        "route_policy_audit_jsonl": output_dir / "route_policy_audit.jsonl",
        "runtime_contract_audit_jsonl": output_dir / "runtime_contract_audit.jsonl",
        "user_response_policy_audit_jsonl": output_dir / "user_response_policy_audit.jsonl",
        "db_contract_audit_jsonl": output_dir / "db_contract_audit.jsonl",
        "index_contract_audit_jsonl": output_dir / "index_contract_audit.jsonl",
        "cache_contract_audit_jsonl": output_dir / "cache_contract_audit.jsonl",
        "live_runtime_smoke_audit_jsonl": output_dir / "live_runtime_smoke_audit.jsonl",
        "guardrail_audit_json": output_dir / "guardrail_audit.json",
        "leakage_audit_jsonl": output_dir / "leakage_audit.jsonl",
        "review_packet_jsonl": output_dir / "review_packet.jsonl",
        "review_packet_csv": output_dir / "review_packet.csv",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_20_live_runtime_like_db_index_cache_smoke_nonprod"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_20_LIVE_RUNTIME_LIKE_DB_INDEX_CACHE_SMOKE_NONPROD_READY"
    assert event["diagnostic_only"] is True
    assert event["agent_runtime_nonprod"] is True
    assert event["agent_runtime_product_ready"] is False
    assert event["tool_registry_only_invocation"] is True
    assert event["live_db_index_cache_readiness"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["source_atom_store_canonical_truth"] is True
    assert event["search_index_candidate_only"] is True
    assert event["runtime_cache_evidence_truth"] is False
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_text_used"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["route_policy_lanes"] == ["user_locator", "rough_query", "hybrid", "unsupported"]
    assert event["tool_registry_version"] == "rag_tool_registry_l0_l8_v1"
    assert event["live_runtime_smoke_row_count"] > 0
    assert event["agent_tool_call_trace_row_count"] > 0
    assert event["db_contract_audit_row_count"] > 0
    assert event["index_contract_audit_row_count"] > 0
    assert event["cache_contract_audit_row_count"] > 0
    assert event["db_unavailable_fail_closed_count"] >= 1
    assert event["index_unavailable_fail_closed_count"] >= 1
    assert event["cache_namespace_mismatch_blocked_count"] >= 1
    assert event["runtime_contract_violation_count"] == 0
    assert event["production_write_attempt_count"] == 0
    assert event["broad_source_atom_scan_attempt_count"] == 0
    assert event["vector_payload_evidence_truth_violation_count"] == 0
    assert "prompt_template" not in event
    assert "responses" not in event
    assert "per_query_rows" not in event
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = "summary_json_sha256" if path_key == "summary_json" else f"{path_key}_sha256"
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert "diagnostic_v3_20_live_runtime_like_db_index_cache_smoke_nonprod_ready" in progress
    assert "live-runtime-like DB/index/cache smoke" in current_flat
    assert "not production routing" in current_flat
    assert "not live DB/index/cache readiness" in current_flat
    assert "SourceAtomStoreContract hydrates canonical SourceAtom ids" in current_flat
    assert "SearchIndexContract returns candidates only" in current_flat
    assert "RuntimeCacheContract is optional and never evidence truth" in current_flat
    assert "db_contract_audit.jsonl" in measurements
    assert "index_contract_audit.jsonl" in measurements
    assert "cache_contract_audit.jsonl" in measurements
    assert "live_runtime_smoke_audit.jsonl" in measurements
    assert "| official_metric_input_rows | 0 |" in measurements
    assert "| runtime_contract_violation_count | 0 |" in measurements
    assert "| production_write_attempt_count | 0 |" in measurements
    assert "| broad_source_atom_scan_attempt_count | 0 |" in measurements
    assert "| vector_payload_evidence_truth_violation_count | 0 |" in measurements
    assert run_id in triage
    assert "INDEX_UNAVAILABLE" in triage
    assert "SOURCE_ATOM_STORE_UNAVAILABLE" in triage
    assert "CACHE_NAMESPACE_MISMATCH" in triage
    assert "Cache unavailable is optional" in triage


def test_progress_measurements_triage_and_status_record_v3_21_agent_runtime_llm_io_observability_packet():
    run_id = "official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod"
    output_dir = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id
    artifact_paths = {
        "summary_json": output_dir / "summary.json",
        "metrics_json": output_dir / "metrics.json",
        "per_query_jsonl": output_dir / "per_query.jsonl",
        "agent_tool_call_trace_jsonl": output_dir / "agent_tool_call_trace.jsonl",
        "route_policy_audit_jsonl": output_dir / "route_policy_audit.jsonl",
        "runtime_contract_audit_jsonl": output_dir / "runtime_contract_audit.jsonl",
        "user_response_policy_audit_jsonl": output_dir / "user_response_policy_audit.jsonl",
        "db_contract_audit_jsonl": output_dir / "db_contract_audit.jsonl",
        "index_contract_audit_jsonl": output_dir / "index_contract_audit.jsonl",
        "cache_contract_audit_jsonl": output_dir / "cache_contract_audit.jsonl",
        "live_runtime_smoke_audit_jsonl": output_dir / "live_runtime_smoke_audit.jsonl",
        "llm_io_packet_jsonl": output_dir / "llm_io_packet.jsonl",
        "llm_io_packet_csv": output_dir / "llm_io_packet.csv",
        "llm_invocation_audit_jsonl": output_dir / "llm_invocation_audit.jsonl",
        "local_llm_readiness_json": output_dir / "local_llm_readiness.json",
        "prompt_manifest_json": output_dir / "prompt_manifest.json",
        "guardrail_audit_json": output_dir / "guardrail_audit.json",
        "leakage_audit_jsonl": output_dir / "leakage_audit.jsonl",
        "review_packet_jsonl": output_dir / "review_packet.jsonl",
        "review_packet_csv": output_dir / "review_packet.csv",
    }
    require_v3_9_local_artifacts(STATUS_JSONL, *artifact_paths.values())

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_21_agent_runtime_llm_io_observability_packet_nonprod"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] in {
        "DIAGNOSTIC_V3_21_AGENT_RUNTIME_LLM_IO_OBSERVABILITY_PACKET_NONPROD_READY",
        "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
    }
    assert event["diagnostic_only"] is True
    assert event["agent_runtime_nonprod"] is True
    assert event["agent_runtime_product_ready"] is False
    assert event["tool_registry_only_invocation"] is True
    assert event["live_db_index_cache_readiness"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["source_atom_store_canonical_truth"] is True
    assert event["search_index_candidate_only"] is True
    assert event["runtime_cache_evidence_truth"] is False
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["actual_llm_responses_are_required_when_llm_invoked"] is True
    assert event["noop_or_extractive_generator_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_text_used"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["route_policy_lanes"] == ["user_locator", "rough_query", "hybrid", "unsupported"]
    assert event["tool_registry_version"] == "rag_tool_registry_l0_l8_v1"
    assert event["llm_io_packet_row_count"] > 0
    assert event["runtime_contract_violation_count"] == 0
    assert event["prompt_leakage_flag_count"] == 0
    assert event["response_leakage_flag_count"] == 0
    assert event["path_leakage_flag_count"] == 0
    assert event["evidence_truth_violation_count"] == 0
    assert "prompt_template" not in event
    assert "raw_llm_response" not in event
    assert "responses" not in event
    assert "per_query_rows" not in event
    for path_key, path in artifact_paths.items():
        assert event["artifact_paths"][path_key] == path.relative_to(ROOT).as_posix()
        hash_key = "summary_json_sha256" if path_key == "summary_json" else f"{path_key}_sha256"
        assert event["artifact_sha256"][hash_key] == sha256_file(path)

    assert run_id in current_text
    assert "diagnostic_v3_21_agent_runtime_llm_io_observability_packet_nonprod" in progress
    assert "LLM I/O observability packet" in current_flat
    assert "actual raw LLM responses" in current_flat
    assert "not production routing" in current_flat
    assert "not live DB/index/cache readiness" in current_flat
    assert "llm_io_packet.jsonl" in measurements
    assert "llm_invocation_audit.jsonl" in measurements
    assert "local_llm_readiness.json" in measurements
    assert "prompt_manifest.json" in measurements
    assert "| official_metric_input_rows | 0 |" in measurements
    assert "| runtime_contract_violation_count | 0 |" in measurements
    assert "| prompt_leakage_flag_count | 0 |" in measurements
    assert "| response_leakage_flag_count | 0 |" in measurements
    assert "| path_leakage_flag_count | 0 |" in measurements
    assert run_id in triage
    assert "Fail-closed rows do not invoke LLM" in triage
    assert "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED" in triage
    assert "SourceAtom/EvidenceBundle remains evidence truth" in triage


def test_progress_measurements_triage_and_status_record_v3_22_xlsx_display_value_and_range_rendering_single_report():
    run_id = "official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
    output_dir = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id
    report_path = output_dir / "report.json"
    require_v3_9_local_artifacts(STATUS_JSONL, report_path)

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split("### v3_22 XLSX Display-Value And Cell/Range Rendering", 1)[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split("### v3_22 XLSX Display-Value And Cell/Range Rendering Triage", 1)[1].split("\n### ", 1)[0]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id
        and event.get("event_type") == "diagnostic_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == "DIAGNOSTIC_V3_22_XLSX_VALUE_FORMATTING_AND_CELL_RANGE_ANSWER_RENDERING_NONPROD_READY"
    assert event["diagnostic_only"] is True
    assert event["single_report_artifact_contract"] is True
    assert event["agent_runtime_nonprod"] is True
    assert event["agent_runtime_product_ready"] is False
    assert event["tool_registry_only_invocation"] is True
    assert event["live_db_index_cache_readiness"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["source_atom_store_canonical_truth"] is True
    assert event["search_index_candidate_only"] is True
    assert event["runtime_cache_evidence_truth"] is False
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_text_used"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["raw_xlsx_query_time_parsing_forbidden"] is True
    assert event["formula_evaluation_at_query_time"] is False
    assert event["human_review_required"] is False
    assert event["review_csv_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["report_row_count"] == report["metrics"]["report_row_count"] == len(report["per_query"])
    assert event["single_cell_value_count"] >= 7
    assert event["small_range_table_count"] >= 1
    assert event["bounded_range_summary_count"] >= 1
    assert event["format_metadata_unavailable_count"] >= 1
    assert event["unsupported_range_too_large_count"] >= 1
    assert event["ambiguous_range_context_required_count"] >= 1
    assert event["runtime_contract_violation_count"] == 0
    assert event["vector_payload_evidence_truth_violation_count"] == 0
    assert "prompt_template" not in event
    assert "raw_llm_response" not in event
    assert "responses" not in event
    assert "per_query" not in event

    assert run_id in current_text
    assert "diagnostic_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod_ready" in progress
    assert (
        "XLSX display/range rendering loop" in current_flat
        or "persisted XLSX SourceAtom display metadata materialization loop" in current_flat
    )
    assert "single-report artifact policy" in current_flat
    assert "not production routing" in current_flat
    assert "not product success" in current_flat
    assert "not promotion evidence" in current_flat
    assert "not official metric lift" in current_flat
    assert "not live DB/index/cache readiness" in current_flat
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "The run directory intentionally does not write summary.json" in measurements_section
    assert "llm_io_packet.jsonl" in measurements_section
    assert "prompt_manifest.json" in measurements_section
    assert "no review CSV unless user-owned review is required" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| review_csv_created | false |" in measurements_section
    assert run_id in triage_section
    assert "single-report contract is active" in triage_section
    assert "FORMAT_METADATA_UNAVAILABLE" in triage_section
    assert "Formula cells use cached values only" in triage_section
    assert "fail closed without LLM invocation" in triage_section
    assert "SourceAtom/EvidenceBundle remains evidence truth" in triage_section


def test_phase1_diagnostic_contract_closure_after_v3_22_records_boundary_and_backlog():
    closure_id = "phase1_diagnostic_contract_closure_after_v3_22"
    closure_status = "PHASE1_DIAGNOSTIC_CONTRACT_CLOSURE_AFTER_V3_22_READY"
    closure_event_type = "phase1_diagnostic_contract_closure_after_v3_22_ready"
    v3_22_run_id = "official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
    v3_22_report_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / "quality"
        / v3_22_run_id
        / "report.json"
    )
    require_v3_9_local_artifacts(STATUS_JSONL, v3_22_report_path)

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### Phase 1 Diagnostic Contract Closure After v3_22",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### Phase 1 Diagnostic Contract Closure After v3_22 Triage",
        1,
    )[1].split("\n### ", 1)[0]
    report = json.loads(v3_22_report_path.read_text(encoding="utf-8"))
    summary = report["summary"]
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == closure_id and event.get("event_type") == closure_event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == closure_status
    assert event["phase1_closed"] is True
    assert event["closure_basis_run_id"] == v3_22_run_id
    assert event["counter_source_of_truth"] == v3_22_report_path.relative_to(ROOT).as_posix()
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["xlsx_locator_performance_completion"] is False
    assert event["representative_product_performance"] is False
    assert event["source_atom_registry_mutated"] is False
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["raw_xlsx_query_time_parsing_forbidden"] is True
    assert event["formula_evaluation_at_query_time"] is False
    assert event["formula_text_visible_to_user_default"] is False
    assert event["review_csv_created"] is False
    assert event["review_csv_optional_only_for_user_owned_decision"] is True
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {
        "v3_22_report_json": v3_22_report_path.relative_to(ROOT).as_posix(),
        "status_jsonl": "ai/eval/reports/rag-ingestion/status.jsonl",
        "progress_doc": "docs/rag-ingestion-progress.md",
        "measurements_doc": "docs/rag-ingestion-measurements.md",
        "triage_doc": "docs/rag-ingestion-triage.md",
    }
    assert event["artifact_sha256"]["v3_22_report_json_sha256"] == sha256_file(v3_22_report_path)
    assert event["v3_22_counters"] == {
        "report_row_count": 14,
        "xlsx_answer_allowed_count": 10,
        "llm_invoked_count": 10,
        "raw_llm_response_present_count": 10,
        "parsed_final_answer_present_count": 10,
        "fail_closed_no_llm_invocation_count": 4,
        "display_value_used_count": 8,
        "raw_value_fallback_count": 1,
        "runtime_contract_violation_count": 0,
        "vector_payload_evidence_truth_violation_count": 0,
        "official_metric_input_rows": 0,
        "review_csv_created": False,
    }
    for key, expected in event["v3_22_counters"].items():
        assert summary[key] == expected, key

    assert event["phase1_closed_scope"] == [
        "SearchView/vector payload candidate-only boundary",
        "SourceAtom/EvidenceBundle evidence-truth boundary",
        "ToolRegistry-only non-production L0-L8 runtime contract",
        "Ambiguous/deictic/missing-context fail-closed response policy",
        "Live-runtime-like DB/index/cache smoke at non-production contract level only",
        "LLM I/O observability for answer-allowed rows",
        "XLSX display-value and cell/range rendering contract",
        "Single-report v3_22 artifact policy",
        "Guardrail/status/doc sync hygiene",
    ]
    assert event["phase2_backlog"] == [
        "persisted XLSX SourceAtom display metadata materialization path",
        "XLSX table/range/cell locator improvement",
        "real workbook/document-disjoint holdout",
        "live DB/index/cache readiness verification",
        "official metric/promotion only after user-owned gold/qrels/denominator decisions",
    ]
    assert event["user_owned_decisions_remain_limited_to"] == [
        "golden set creation",
        "golden set review",
        "expected answer/evidence judgment",
        "relevance/answerability label judgment",
        "gold policy decision",
        "official denominator/promotion policy decision",
    ]
    assert "prompt_template" not in event
    assert "raw_llm_response" not in event
    assert "responses" not in event
    assert "per_query" not in event

    assert closure_event_type in current_text
    assert closure_id in current_text
    assert "Phase 1 is closed as a diagnostic source-first RAG contract closure after v3_22" in current_flat
    for phrase in (
        "not production routing",
        "not product success evidence",
        "not promotion evidence",
        "not official metric lift",
        "not live DB/index/cache readiness",
        "not XLSX locator performance completion",
        "not representative product performance",
    ):
        assert phrase in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert v3_22_report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| report_row_count | 14 |" in measurements_section
    assert "| display_value_used_count | 8 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| product_success_evidence_allowed | false |" in measurements_section
    assert "| promotion_evidence | false |" in measurements_section
    assert "| live_db_index_cache_readiness | false |" in measurements_section
    assert "single primary report artifact" in measurements_section
    assert "status.jsonl is ignored" in measurements_section
    assert "report.json is ignored" in measurements_section
    assert "review_packet.csv" in measurements_section
    assert "SearchView/vector payload candidate-only boundary" in triage_section
    assert "SourceAtom/EvidenceBundle evidence-truth boundary" in triage_section
    assert "ToolRegistry-only non-production L0-L8 runtime contract" in triage_section
    assert "persisted XLSX SourceAtom display metadata materialization path" in triage_section


def test_phase1_fastapi_diagnostic_integration_records_cleanup_route_and_boundary():
    marker = "phase1_diagnostic_contract_closure_fastapi_diagnostic_integration"
    event_type = "phase1_diagnostic_contract_closure_fastapi_diagnostic_integration_ready"
    status = "PHASE1_DIAGNOSTIC_CONTRACT_CLOSURE_FASTAPI_DIAGNOSTIC_INTEGRATION_READY"
    v3_22_run_id = "official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
    v3_22_report_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / "quality"
        / v3_22_run_id
        / "report.json"
    )
    require_v3_9_local_artifacts(STATUS_JSONL, v3_22_report_path)

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### Phase 1 Closeout FastAPI Diagnostic Integration",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### Phase 1 Closeout FastAPI Diagnostic Integration Triage",
        1,
    )[1].split("\n### ", 1)[0]
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == marker and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == status
    assert event["phase1_closed"] is True
    assert event["repository_cleanup_completed"] is True
    assert event["script_inventory_updated"] is True
    assert event["required_v3_artifacts_deleted"] is False
    assert event["v3_22_report_preserved"] is True
    assert event["v3_22_script_entrypoint_retained"] is True
    assert event["reusable_runtime_logic_extracted"] is True
    assert event["fastapi_integration_ready"] is True
    assert event["fastapi_primary_app"] == "ai/app/main.py -> app = create_app()"
    assert event["fastapi_factory"] == "ai/app/api.py:create_app"
    assert event["route_path"] == "/internal/rag/diagnostic/query"
    assert event["route_method"] == "POST"
    assert event["route_scope"] == "diagnostic_internal"
    assert event["feature_flag"] == "AIPIPELINE_WORKER_RAG_FASTAPI_DIAGNOSTIC_ROUTE_ENABLED"
    assert event["settings_field"] == "rag_fastapi_diagnostic_route_enabled"
    assert event["feature_flag_default_enabled"] is False
    assert event["production_orchestrator_mode_enabled"] is False
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["xlsx_locator_completion_claimed"] is False
    assert event["no_production_db_index_cache_writes"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["raw_xlsx_query_time_parsing_forbidden"] is True
    assert event["raw_pdf_query_time_parsing_forbidden"] is True
    assert event["formula_cached_values_only"] is True
    assert event["formula_text_visible_to_user_default"] is False
    assert event["formula_evaluation_at_query_time"] is False
    assert event["unsupported_large_ranges_fail_closed"] is True
    assert event["ambiguous_deictic_context_missing_fail_closed"] is True
    assert event["review_packet_created_by_closeout"] is False
    assert event["artifact_sha256"]["v3_22_report_json_sha256"] == sha256_file(v3_22_report_path)
    assert event["v3_22_counters"]["report_row_count"] == 14
    assert event["v3_22_counters"]["official_metric_input_rows"] == 0
    assert event["v3_22_counters"]["review_csv_created"] is False

    assert marker in current_text
    assert "POST /internal/rag/diagnostic/query" in current_text
    assert "GET /internal/rag/diagnostic/readiness" in current_text
    assert "AIPIPELINE_WORKER_RAG_FASTAPI_DIAGNOSTIC_ROUTE_ENABLED" in current_text
    for phrase in (
        "not production routing",
        "not product success evidence",
        "not promotion evidence",
        "not official metric lift",
        "not live DB/index/cache readiness",
        "not XLSX locator completion",
    ):
        assert phrase in current_flat
    assert "diagnostic route default-enabled | false" in measurements_section
    assert "diagnostic route tests | 35 passed" in measurements_section
    assert "FT-A dry-run input validation route | exposed, input-only, sanitized/hash-only, no writes" in measurements_section
    assert "readiness route holdout candidate manifest contract | exposed, input-only, hash-locked, no writes" in measurements_section
    assert "v3_22 script entrypoint | retained" in measurements_section
    assert "SourceAtom/EvidenceBundle display metadata bridge | present" in measurements_section
    assert "does not add a new performance, quality, promotion, official metric, or product-success measurement" in measurements_section
    assert "User-owned decisions remain" in triage_section
    assert "Codex-owned non-gold decisions remain" in triage_section
    assert "hash-locked holdout candidate manifest contract" in triage_section
    assert "XLSX `source_identity` alone is not workbook proof" in triage_section
    assert "forbidden gold/target/supporting/expected fields" in triage_section
    assert "SearchView/vector payload remains candidate-only" in triage_section
    assert "SourceAtom/EvidenceBundle remains evidence truth" in triage_section
    for bucket in (
        "required_by_current_tests",
        "required_by_docs_or_status_sync",
        "ignored_diagnostic_artifact",
        "external_archive_candidate",
        "legacy_script_entrypoint_to_keep",
        "reusable_runtime_logic_to_extract",
        "dead_temp_or_scratch_candidate",
    ):
        assert bucket in scripts_readme


def test_v4_0_charter_status_opening_records_boundary_and_non_promotion_status():
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_event_type = "v4_source_grounded_runtime_locator_and_finetune_readiness_opened"
    v4_status = "V4_SOURCE_GROUNDED_RUNTIME_LOCATOR_AND_FINETUNE_READINESS_OPENED"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    v4_1_current_status = "diagnostic_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod_ready"
    v4_2_current_status = "diagnostic_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod_ready"
    v4_3_current_status = "diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod_ready"
    v4_4_current_status = "diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod_ready"
    v4_5_current_status = "diagnostic_v4_5_finetune_readiness_packet_nonprod_ready"
    v4_5_1_current_status = "diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready"
    v4_5_2_current_status = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready"
    v3_22_run_id = "official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
    v3_22_report_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / "quality"
        / v3_22_run_id
        / "report.json"
    )
    require_v3_9_local_artifacts(STATUS_JSONL, v3_22_report_path)

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4 Source-Grounded Runtime Locator And Fine-Tuning Readiness Charter",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4 Source-Grounded Runtime Locator And Fine-Tuning Readiness Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == v4_id and event.get("event_type") == v4_event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == v4_status
    assert event["v4_opened"] is True
    assert event["phase1_closed"] is True
    assert event["closure_basis_run_id"] == v3_22_run_id
    assert event["counter_source_of_truth"] == v3_22_report_path.relative_to(ROOT).as_posix()
    assert event["recommended_run_family_if_created"] == v4_run_family
    assert event["goal_statement"] == (
        "v4 extends the Phase 1 diagnostic source-first RAG contract into persisted/runtime-adjacent paths, "
        "improves family-separated XLSX locator and PDF file-identity bottlenecks, builds real blind/OOD holdout "
        "and leakage-audit infrastructure, and prepares fine-tuning lanes only after evidence and split quality "
        "gates are satisfied. v4 remains non-production and non-promotional until user-owned gold/qrels/denominator "
        "decisions explicitly open official evaluation."
    )
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["representative_product_performance"] is False
    assert event["pdf_xlsx_text_collapsed_headline_product_score"] is False
    assert event["persisted_runtime_adjacent_paths_targeted"] is True
    assert event["xlsx_locator_family_separated"] is True
    assert event["pdf_file_identity_family_separated"] is True
    assert event["real_blind_ood_holdout_infrastructure_targeted"] is True
    assert event["real_blind_ood_holdout_available"] is False
    assert event["leakage_audit_infrastructure_targeted"] is True
    assert event["finetune_readiness_targeted"] is True
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["source_atom_registry_mutated"] is False
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["raw_xlsx_query_time_parsing_forbidden"] is True
    assert event["raw_pdf_query_time_parsing_forbidden"] is True
    assert event["direct_normalized_answer_value_query_matching_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["formula_evaluation_at_query_time"] is False
    assert event["formula_text_visible_to_user_default"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is False
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["prompt_payload_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["label_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["production_mutation"] is False
    assert event["db_or_production_namespace_written"] is False
    assert event["artifact_paths"] == {
        "v3_22_report_json": v3_22_report_path.relative_to(ROOT).as_posix(),
        "status_jsonl": "ai/eval/reports/rag-ingestion/status.jsonl",
        "progress_doc": "docs/rag-ingestion-progress.md",
        "measurements_doc": "docs/rag-ingestion-measurements.md",
        "triage_doc": "docs/rag-ingestion-triage.md",
    }
    assert event["artifact_sha256"]["v3_22_report_json_sha256"] == sha256_file(v3_22_report_path)
    assert "report_json" not in event["artifact_paths"]
    assert "review_packet.csv" not in event["artifact_paths"].values()
    assert "prompt_template" not in event
    assert "raw_llm_response" not in event
    assert "responses" not in event
    assert "per_query" not in event

    assert event["v4_target_lanes"] == [
        "v4_1_persisted_xlsx_sourceatom_display_metadata_materialization",
        "v4_2_xlsx_locator_v2_table_range_cell_structural_materialization",
        "v4_3_pdf_file_identity_confidence_and_evidence_window_split",
        "v4_4_real_blind_ood_holdout_and_leakage_audit",
        "v4_5_finetune_readiness_packet",
    ]
    assert event["fine_tuning_opening_gates"] == [
        "persisted evidence path stable",
        "locator and evidence errors classified",
        "real disjoint splits available",
        "leakage buckets excluded",
        "user-owned label/qrels/denominator policy approved for official-adjacent evaluation",
    ]
    assert event["user_owned_decisions_remain_limited_to"] == [
        "golden set creation",
        "golden set review",
        "expected answer/evidence judgment",
        "relevance/answerability label judgment",
        "gold policy decision",
        "official denominator policy",
        "promotion policy",
    ]

    assert (
        f"Overall status: `{v4_event_type}`;" in current_text
        or f"Overall status: `{v4_1_current_status}`;" in current_text
        or f"Overall status: `{v4_2_current_status}`;" in current_text
        or f"Overall status: `{v4_3_current_status}`;" in current_text
        or f"Overall status: `{v4_4_current_status}`;" in current_text
        or f"Overall status: `{v4_5_current_status}`;" in current_text
        or f"Overall status: `{v4_5_1_current_status}`;" in current_text
        or f"Overall status: `{v4_5_2_current_status}`;" in current_text
        or f"Overall status: `{V4_5_3_CURRENT_STATUS}`;" in current_text
    )
    assert v4_id in current_text
    assert v4_run_family in current_text
    assert "v4 starts after the Phase 1 diagnostic closure at v3_22" in current_flat
    assert "persisted/runtime-adjacent SourceAtom display metadata materialization" in current_flat
    assert "family-separated XLSX table/range/cell locator improvement" in current_flat
    assert "PDF file identity separated from evidence-window quality" in current_flat
    assert "real blind/OOD holdout and leakage-audit infrastructure" in current_flat
    for phrase in (
        "not production routing",
        "not product success evidence",
        "not promotion evidence",
        "not official metric lift",
        "not live DB/index/cache readiness",
        "not actual fine-tuning/training",
        "not threshold tuning",
        "not winner selection",
    ):
        assert phrase in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_readiness_only=true" in current_flat
    assert "fine_tuning_started=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat

    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert v3_22_report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| product_success_evidence_allowed | false |" in measurements_section
    assert "| promotion_evidence | false |" in measurements_section
    assert "| production_routing | false |" in measurements_section
    assert "| live_db_index_cache_readiness | false |" in measurements_section
    assert "| real_blind_ood_holdout_available | false |" in measurements_section
    assert "| fine_tuning_readiness_only | true |" in measurements_section
    assert "| fine_tuning_started | false |" in measurements_section
    assert "| fine_tuning_executed | false |" in measurements_section
    assert "Fine-tuning is a readiness lane only" in measurements_section

    assert v4_id in triage_section
    assert v4_run_family in triage_section
    assert "family-separated XLSX table/range/cell locator work" in triage_section
    assert "PDF file identity separated from answer-ready evidence-window quality" in triage_section
    assert "raw XLSX/PDF query-time parsing" in triage_section
    assert "direct normalized answer-value query matching" in triage_section
    assert "target/gold/supporting/expected locator use" in triage_section
    assert "actual fine-tuning/training" in triage_section
    assert "v4_1 persisted XLSX SourceAtom display metadata materialization" in triage_section

    assert (
        f"Current RAG status: `{v4_event_type}`" in readme
        or f"Current RAG status: `{v4_1_current_status}`" in readme
        or f"Current RAG status: `{v4_2_current_status}`" in readme
        or f"Current RAG status: `{v4_3_current_status}`" in readme
        or f"Current RAG status: `{v4_4_current_status}`" in readme
        or f"Current RAG status: `{v4_5_current_status}`" in readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in readme
    )
    assert "fine_tuning_executed=false" in readme
    assert (
        f"Current RAG status: `{v4_event_type}`" in eval_readme
        or f"Current RAG status: `{v4_1_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_2_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_3_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_4_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in eval_readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in eval_readme
    )
    assert "fine_tuning_executed=false" in eval_readme
    assert "XLSX table/range/cell locator improvement" in triage_section
    assert "official metric/promotion only after user-owned gold/qrels/denominator decisions" in triage_section


def test_v4_1_persisted_xlsx_sourceatom_display_metadata_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod"
    event_type = "diagnostic_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod"
    current_status = f"{event_type}_ready"
    v4_2_current_status = "diagnostic_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod_ready"
    v4_3_current_status = "diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod_ready"
    v4_4_current_status = "diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod_ready"
    v4_5_current_status = "diagnostic_v4_5_finetune_readiness_packet_nonprod_ready"
    v4_5_1_current_status = "diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready"
    v4_5_2_current_status = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready"
    status = "DIAGNOSTIC_V4_1_PERSISTED_XLSX_SOURCEATOM_DISPLAY_METADATA_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_1 Persisted XLSX SourceAtom Display Metadata",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_1 Persisted XLSX SourceAtom Display Metadata Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["persisted_xlsx_sourceatom_display_metadata"] is True
    assert event["persisted_xlsx_sourceatom_display_metadata_rows"] == 17
    assert event["persisted_display_value_available_count"] == 15
    assert event["persisted_raw_value_fallback_count"] == 1
    assert event["formula_cached_value_used_count"] == 1
    assert event["runtime_contract_violation_count"] == 0
    assert event["vector_payload_evidence_truth_violation_count"] == 0
    assert event["raw_xlsx_query_time_parsing_count"] == 0
    assert event["formula_evaluated_at_query_time_count"] == 0
    assert event["official_metric_input_rows"] == 0
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["official_metric"] is False
    assert event["official_metric_lift"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["source_atom_registry_mutated"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["raw_xlsx_query_time_parsing_forbidden"] is True
    assert event["formula_evaluation_at_query_time"] is False
    assert event["formula_text_visible_to_user_default"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is True
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["persisted_sourceatom_manifest_jsonl_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gpu_required_for_this_slice"] is False

    assert report["schema_version"] == "rag_v4_1_persisted_xlsx_sourceatom_display_metadata_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["summary"]["single_report_artifact_contract"] is True
    assert report["summary"]["sidecar_primary_artifacts_suppressed"] is True
    assert report["metrics"]["official_metric_input_rows"] == 0
    assert report["guardrails"]["protected_namespaces_touched"] == []

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{v4_2_current_status}`;" in current_text
        or f"Overall status: `{v4_3_current_status}`;" in current_text
        or f"Overall status: `{v4_4_current_status}`;" in current_text
        or f"Overall status: `{v4_5_current_status}`;" in current_text
        or f"Overall status: `{v4_5_1_current_status}`;" in current_text
        or f"Overall status: `{v4_5_2_current_status}`;" in current_text
        or f"Overall status: `{V4_5_3_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{v4_2_current_status}`" in readme
        or f"Current RAG status: `{v4_3_current_status}`" in readme
        or f"Current RAG status: `{v4_4_current_status}`" in readme
        or f"Current RAG status: `{v4_5_current_status}`" in readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{v4_2_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_3_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_4_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in eval_readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in eval_readme
    )
    assert run_id in current_text
    assert v4_id in current_text
    assert v4_run_family in current_text
    assert "current diagnostic v4_1 persisted XLSX SourceAtom display metadata loop" in current_text
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| persisted_xlsx_sourceatom_display_metadata_rows | 17 |" in measurements_section
    assert "| persisted_display_value_available_count | 15 |" in measurements_section
    assert "| persisted_raw_value_fallback_count | 1 |" in measurements_section
    assert "| runtime_contract_violation_count | 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| product_success_evidence_allowed | false |" in measurements_section
    assert "| promotion_evidence | false |" in measurements_section
    assert "| fine_tuning_executed | false |" in measurements_section
    assert "| gpu_required_for_this_slice | false |" in measurements_section
    assert "no review CSV or per-run Markdown is created" in measurements_section

    assert run_id in triage_section
    assert "SourceAtom-owned manifest fields" in triage_section
    assert "Formula cells carry cached values only" in triage_section
    assert "SearchView/vector payload remains candidate-only" in triage_section
    assert "No raw XLSX query-time parsing" in triage_section
    assert "future embedding/LLM/index workloads should prefer GPU when available" in triage_section
    assert "Next lane: v4_2 XLSX locator v2" in triage_section


def test_v4_2_xlsx_locator_v2_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod"
    event_type = "diagnostic_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod"
    current_status = f"{event_type}_ready"
    v4_3_current_status = "diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod_ready"
    v4_4_current_status = "diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod_ready"
    v4_5_current_status = "diagnostic_v4_5_finetune_readiness_packet_nonprod_ready"
    v4_5_1_current_status = "diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready"
    v4_5_2_current_status = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready"
    status = "DIAGNOSTIC_V4_2_XLSX_LOCATOR_V2_TABLE_RANGE_CELL_STRUCTURAL_MATERIALIZATION_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_2 XLSX Locator v2 Table/Range/Cell Structural Materialization",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_2 XLSX Locator v2 Table/Range/Cell Structural Materialization Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["xlsx_locator_v2_rows"] == 344
    assert event["xlsx_locator_v2_candidate_component_rows"] == 900
    assert event["pdf_rows_included"] == 0
    assert event["text_rows_included"] == 0
    assert event["seen_reference_only_rows"] == 344
    assert event["workbook_disjoint_validation_rows"] == 0
    assert event["fresh_real_holdout_available"] is False
    assert event["table_or_range_at1"]["numerator"] == 23
    assert event["table_or_range_at1"]["computed_by_v4_2"] is False
    assert event["table_or_range_at1"]["metric_role"] == "reference_only_seen_diagnostic"
    assert event["cell_or_value_at1"]["numerator"] == 21
    assert event["cell_or_value_at1"]["computed_by_v4_2"] is False
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["family_separated_xlsx_only"] is True
    assert event["pdf_lane_excluded"] is True
    assert event["text_lane_excluded"] is True
    assert event["source_atom_registry_mutated"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["raw_answer_value_for_query_scoring_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is True
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["xlsx_locator_v2_manifest_jsonl_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gpu_required_for_this_slice"] is False
    assert event["holdout_policy"]["seen_reference_success_claim_allowed"] is False

    assert report["schema_version"] == "rag_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["summary"]["single_report_artifact_contract"] is True
    assert report["summary"]["sidecar_primary_artifacts_suppressed"] is True
    assert report["metrics"]["official_metric_input_rows"] == 0
    assert report["metrics"]["display_metadata_coverage"]["coverage_role"] == "input_readiness_only_not_locator_denominator"
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["holdout_policy"]["blocked_reason"] == "fresh real XLSX workbook-disjoint holdout unavailable"

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{v4_3_current_status}`;" in current_text
        or f"Overall status: `{v4_4_current_status}`;" in current_text
        or f"Overall status: `{v4_5_current_status}`;" in current_text
        or f"Overall status: `{v4_5_1_current_status}`;" in current_text
        or f"Overall status: `{v4_5_2_current_status}`;" in current_text
        or f"Overall status: `{V4_5_3_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{v4_3_current_status}`" in readme
        or f"Current RAG status: `{v4_4_current_status}`" in readme
        or f"Current RAG status: `{v4_5_current_status}`" in readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{v4_3_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_4_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in eval_readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in eval_readme
    )
    assert run_id in current_text
    assert v4_id in current_text
    assert v4_run_family in current_text
    assert "current diagnostic v4_2 XLSX locator v2 structural materialization loop" in current_text
    assert "current diagnostic v4_1 persisted XLSX SourceAtom display metadata loop" in current_text
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| xlsx_locator_v2_rows | 344 |" in measurements_section
    assert "| xlsx_locator_v2_candidate_component_rows | 900 |" in measurements_section
    assert "| table_or_range_at1 | 23/344 |" in measurements_section
    assert "| cell_or_value_at1 | 21/344 |" in measurements_section
    assert "| workbook_disjoint_validation_rows | 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| product_success_evidence_allowed | false |" in measurements_section
    assert "| promotion_evidence | false |" in measurements_section
    assert "| fine_tuning_executed | false |" in measurements_section
    assert "| gpu_required_for_this_slice | false |" in measurements_section
    assert "computed_by_v4_2=false" in measurements_section
    assert "no review CSV, sidecar manifest, metrics sidecar, or per-run Markdown is created" in measurements_section

    assert run_id in triage_section
    assert "PDF/TEXT lanes excluded" in triage_section
    assert "v3_12/v3_15 XLSX locator surface" in triage_section
    assert "v4_1 display metadata rows are input readiness only" in triage_section
    assert "`reference_only_seen_diagnostic` with `computed_by_v4_2=false`" in triage_section
    assert "Fresh real workbook-disjoint holdout remains unavailable" in triage_section
    assert "future embedding/LLM/index workloads should prefer GPU when available" in triage_section


def test_v4_3_pdf_file_identity_split_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod"
    event_type = "diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod"
    current_status = f"{event_type}_ready"
    v4_4_current_status = "diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod_ready"
    v4_5_current_status = "diagnostic_v4_5_finetune_readiness_packet_nonprod_ready"
    v4_5_1_current_status = "diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready"
    v4_5_2_current_status = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready"
    status = "DIAGNOSTIC_V4_3_PDF_FILE_IDENTITY_CONFIDENCE_AND_EVIDENCE_WINDOW_SPLIT_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_3 PDF File Identity Confidence And Evidence-Window Split",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_3 PDF File Identity Confidence And Evidence-Window Split Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["pdf_file_identity_rows"] == 329
    assert event["pdf_candidate_component_rows"] == 942
    assert event["xlsx_rows_included"] == 0
    assert event["text_rows_included"] == 0
    assert event["seen_reference_only_rows"] == 329
    assert event["source_document_disjoint_validation_rows"] == 0
    assert event["fresh_real_holdout_available"] is False
    assert event["file_resolve_at1"]["numerator"] == 66
    assert event["file_resolve_at1"]["computed_by_v4_3"] is False
    assert event["file_resolve_at1"]["metric_role"] == "reference_only_seen_diagnostic"
    assert event["answer_ready_window_sufficient_at_query"]["numerator"] == 251
    assert event["answer_ready_window_sufficient_at_query"]["computed_by_v4_3"] is False
    assert event["pdf_file_identity_answer_window_kept_separate"] is True
    assert event["bbox_correctness_metric_computed"] is False
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["family_separated_pdf_only"] is True
    assert event["xlsx_lane_excluded"] is True
    assert event["text_lane_excluded"] is True
    assert event["source_atom_registry_mutated"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["raw_answer_value_for_query_scoring_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is True
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["pdf_file_identity_split_manifest_jsonl_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gpu_required_for_this_slice"] is False
    assert event["holdout_policy"]["seen_reference_success_claim_allowed"] is False
    assert event["holdout_policy"]["real_unseen_registry_counts"] == {"PDF_source_document_disjoint": 0}

    assert report["schema_version"] == "rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_report_v1"
    assert report["run_id"] == run_id
    assert report["official_metric"] is False
    assert report["summary"]["status"] == status
    assert report["summary"]["single_report_artifact_contract"] is True
    assert report["summary"]["sidecar_primary_artifacts_suppressed"] is True
    assert report["metrics"]["official_metric_input_rows"] == 0
    assert report["metrics"]["pdf_file_identity_metrics"]["source_metric_scope"] == (
        "diagnostic_only_seen_reference_file_identity_confidence_no_rerank"
    )
    assert report["metrics"]["pdf_evidence_window_metrics"]["source_metric_scope"] == (
        "diagnostic_only_same_page_bbox_window_availability_not_answer_generation"
    )
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["holdout_policy"]["blocked_reason"] == "fresh real PDF source-document-disjoint holdout unavailable"

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{v4_4_current_status}`;" in current_text
        or f"Overall status: `{v4_5_current_status}`;" in current_text
        or f"Overall status: `{v4_5_1_current_status}`;" in current_text
        or f"Overall status: `{v4_5_2_current_status}`;" in current_text
        or f"Overall status: `{V4_5_3_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{v4_4_current_status}`" in readme
        or f"Current RAG status: `{v4_5_current_status}`" in readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{v4_4_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in eval_readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in eval_readme
    )
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    assert (
        (
            "python -X utf8 -m py_compile "
            "ai\\scripts\\rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py"
        )
        in readme_verify_section
        or (
            "python -X utf8 -m py_compile "
            "ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py"
        )
        in readme_verify_section
        or (
            "python -X utf8 -m py_compile "
            "ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py"
        )
        in readme_verify_section
        or (
            "python -X utf8 -m py_compile "
            "ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py"
        )
        in readme_verify_section
            or (
                "python -X utf8 -m py_compile "
                "ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py"
            )
            in readme_verify_section
            or (
                "python -X utf8 -m py_compile "
                "ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py"
            )
            in readme_verify_section
            or ("python -X utf8 -m py_compile ai\\scripts\\" + V4_6_SCRIPT) in readme_verify_section
            or ("python -X utf8 -m py_compile ai\\scripts\\" + V4_6_1_SCRIPT) in readme_verify_section
            or ("python -X utf8 -m py_compile ai\\scripts\\" + V4_6_2_SCRIPT) in readme_verify_section
        )
    assert (
        (
            "python -X utf8 ai\\scripts\\rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py --check"
        )
        in readme_verify_section
        or (
            "python -X utf8 ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py --check"
        )
        in readme_verify_section
        or (
            "python -X utf8 ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py --check"
        )
        in readme_verify_section
        or (
            "python -X utf8 ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py --check"
        )
        in readme_verify_section
            or (
                "python -X utf8 ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py --check"
            )
            in readme_verify_section
            or (
                "python -X utf8 ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py --check"
            )
            in readme_verify_section
            or ("python -X utf8 ai\\scripts\\" + V4_6_SCRIPT + " --check") in readme_verify_section
            or ("python -X utf8 ai\\scripts\\" + V4_6_1_SCRIPT + " --check") in readme_verify_section
            or ("python -X utf8 ai\\scripts\\" + V4_6_2_SCRIPT + " --check") in readme_verify_section
        )
    assert "rag_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod.py --check" not in readme_verify_section
    assert run_id in current_text
    assert v4_id in current_text
    assert v4_run_family in current_text
    assert "current diagnostic v4_3 PDF file identity confidence and evidence-window split loop" in current_text
    assert "current diagnostic v4_2 XLSX locator v2 structural materialization loop" in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| pdf_file_identity_rows | 329 |" in measurements_section
    assert "| pdf_candidate_component_rows | 942 |" in measurements_section
    assert "| file_resolve_at1 | 66/329 |" in measurements_section
    assert "| file_resolve_at3 | 129/329 |" in measurements_section
    assert "| same_page_bounded_evidence_window_candidate_at3 | 341/942 |" in measurements_section
    assert "| answer_ready_window_sufficient_at_query | 251/329 |" in measurements_section
    assert "| bbox_correctness_metric_computed | false |" in measurements_section
    assert "| source_document_disjoint_validation_rows | 0 |" in measurements_section
    assert "| official_metric | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| product_success_evidence_allowed | false |" in measurements_section
    assert "| promotion_evidence | false |" in measurements_section
    assert "| fine_tuning_executed | false |" in measurements_section
    assert "| gpu_required_for_this_slice | false |" in measurements_section
    assert "computed_by_v4_3=false" in measurements_section
    assert "no review CSV, sidecar manifest, metrics sidecar, or per-run Markdown is created" in measurements_section
    assert "Phase 1 closure baseline" in progress
    assert "each v4_n diagnostic slice uses its own single `report.json` as the current counter source of truth" in progress

    assert run_id in triage_section
    assert "XLSX/TEXT lanes excluded" in triage_section
    assert "v3_13 PDF file-identity/evidence-window seen diagnostic surface" in triage_section
    assert "File identity metrics are kept separate from answer-ready evidence-window metrics" in triage_section
    assert "`reference_only_seen_diagnostic` with `computed_by_v4_3=false`" in triage_section
    assert "Fresh real source-document-disjoint holdout remains unavailable" in triage_section
    assert "future embedding/LLM/index workloads should prefer GPU when available" in triage_section
    assert "Completed v4_1-v4_3" in triage
    assert (
        "Next technical lane: v4_4 real blind/OOD holdout and leakage audit" in triage
        or "v4_4 real blind/OOD holdout and leakage audit infrastructure is now materialized" in triage
    )


def test_v4_4_real_blind_ood_holdout_leakage_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod"
    event_type = "diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod"
    current_status = f"{event_type}_ready"
    v4_5_current_status = "diagnostic_v4_5_finetune_readiness_packet_nonprod_ready"
    v4_5_1_current_status = "diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready"
    v4_5_2_current_status = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready"
    status = "DIAGNOSTIC_V4_4_REAL_BLIND_OOD_HOLDOUT_AND_LEAKAGE_AUDIT_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_4 Real Blind/OOD Holdout And Leakage Audit",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_4 Real Blind/OOD Holdout And Leakage Audit Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["real_blind_ood_holdout_infrastructure_ready"] is True
    assert event["leakage_audit_infrastructure_ready"] is True
    assert event["query_fidelity_audit_present"] is True
    assert event["real_holdout_available"] is False
    assert event["real_holdout_sufficient"] is False
    assert event["real_unseen_registry_counts"] == {
        "PDF_source_document_disjoint": 0,
        "XLSX_workbook_disjoint": 0,
    }
    assert event["real_query_fidelity_included_counts"] == {"PDF": 0, "XLSX": 0, "TEXT": 0}
    assert event["leakage_bucket_count"] == 9
    assert event["leakage_excluded_count"] == 9
    assert event["source_atom_registry_mutated"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["direct_normalized_answer_value_query_matching_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is True
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gpu_required_for_this_slice"] is False

    assert report["schema_version"] == "rag_v4_4_real_blind_ood_holdout_and_leakage_audit_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["metrics"]["official_metric_input_rows"] == 0
    assert report["metrics"]["real_holdout_available"] is False
    assert report["holdout_manifest"]["blocked_reason"] == (
        "fresh real PDF source-document-disjoint and XLSX workbook-disjoint holdout unavailable"
    )
    assert report["guardrails"]["protected_namespaces_touched"] == []

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{v4_5_current_status}`;" in current_text
        or f"Overall status: `{v4_5_1_current_status}`;" in current_text
        or f"Overall status: `{v4_5_2_current_status}`;" in current_text
        or f"Overall status: `{V4_5_3_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{v4_5_current_status}`" in readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in eval_readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in eval_readme
    )
    assert (
        (
            "python -X utf8 -m py_compile "
            "ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py"
        )
        in readme_verify_section
        or (
            "python -X utf8 -m py_compile "
            "ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py"
        )
        in readme_verify_section
        or (
            "python -X utf8 -m py_compile "
            "ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py"
        )
        in readme_verify_section
            or (
                "python -X utf8 -m py_compile "
                "ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py"
            )
            in readme_verify_section
            or (
                "python -X utf8 -m py_compile "
                "ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py"
            )
            in readme_verify_section
            or ("python -X utf8 -m py_compile ai\\scripts\\" + V4_6_SCRIPT) in readme_verify_section
            or ("python -X utf8 -m py_compile ai\\scripts\\" + V4_6_1_SCRIPT) in readme_verify_section
            or ("python -X utf8 -m py_compile ai\\scripts\\" + V4_6_2_SCRIPT) in readme_verify_section
        )
    assert (
        (
            "python -X utf8 ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py --check"
        )
        in readme_verify_section
        or (
            "python -X utf8 ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py --check"
        )
        in readme_verify_section
        or (
            "python -X utf8 ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py --check"
        )
        in readme_verify_section
            or (
                "python -X utf8 ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py --check"
            )
            in readme_verify_section
            or (
                "python -X utf8 ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py --check"
            )
            in readme_verify_section
            or ("python -X utf8 ai\\scripts\\" + V4_6_SCRIPT + " --check") in readme_verify_section
            or ("python -X utf8 ai\\scripts\\" + V4_6_1_SCRIPT + " --check") in readme_verify_section
            or ("python -X utf8 ai\\scripts\\" + V4_6_2_SCRIPT + " --check") in readme_verify_section
        )
    assert "current diagnostic v4_4 real blind/OOD holdout and leakage audit loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| real_holdout_available | false |" in measurements_section
    assert "| PDF_source_document_disjoint | 0/20 |" in measurements_section
    assert "| XLSX_workbook_disjoint | 0/8 |" in measurements_section
    assert "| query_fidelity_included_rows_per_family | 0/100 |" in measurements_section
    assert "| leakage_bucket_count | 9 |" in measurements_section
    assert "| leakage_excluded_count | 9 |" in measurements_section
    assert "| official_metric | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "single `report.json`" in measurements_section

    assert run_id in triage_section
    assert "PDF source-document-disjoint" in triage_section
    assert "XLSX workbook-disjoint" in triage_section
    assert "TEXT remains comparison/control only" in triage_section
    assert "answer_value_in_query" in triage_section
    assert "gold_supporting_expected_text_leak" in triage_section
    assert "Fresh real holdout remains unavailable" in triage_section
    assert "future embedding/LLM/index workloads should prefer GPU when available" in triage_section


def test_v4_5_finetune_readiness_packet_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod"
    event_type = "diagnostic_v4_5_finetune_readiness_packet_nonprod"
    current_status = f"{event_type}_ready"
    v4_5_1_current_status = "diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod_ready"
    v4_5_2_current_status = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready"
    status = "DIAGNOSTIC_V4_5_FINETUNE_READINESS_PACKET_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_5 Fine-Tuning Readiness Packet",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_5 Fine-Tuning Readiness Packet Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["readiness_gate_passed"] is False
    assert event["split_quality_gate_passed"] is False
    assert event["leakage_audit_gate_passed"] is True
    assert event["real_unseen_registry_counts"] == {
        "PDF_source_document_disjoint": 0,
        "XLSX_workbook_disjoint": 0,
    }
    assert event["leakage_bucket_count"] == 9
    assert event["leakage_excluded_count"] == 9
    assert event["source_atom_registry_mutated"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["direct_normalized_answer_value_query_matching_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is True
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["training_manifest_jsonl_created"] is False
    assert event["fine_tuning_lanes_json_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gpu_required_for_this_slice"] is False
    assert event["gpu_required_for_future_training_when_opened"] is True

    assert report["schema_version"] == "rag_v4_5_finetune_readiness_packet_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["metrics"]["official_metric_input_rows"] == 0
    assert report["metrics"]["readiness_gate_passed"] is False
    assert report["readiness_gates"]["split_quality_gate"]["passed"] is False
    assert report["readiness_gates"]["leakage_audit_gate"]["passed"] is True
    assert report["source_run_references"]["previous_gate_run_id"].endswith("_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod")
    assert report["guardrails"]["protected_namespaces_touched"] == []

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{v4_5_1_current_status}`;" in current_text
        or f"Overall status: `{v4_5_2_current_status}`;" in current_text
        or f"Overall status: `{V4_5_3_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_1_current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in eval_readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_5 fine-tuning readiness packet loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert (
        "rag_v4_5_finetune_readiness_packet_nonprod.py" in readme_verify_section
        or "rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py" in readme_verify_section
        or "rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py" in readme_verify_section
        or "rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py" in readme_verify_section
        or V4_6_SCRIPT in readme_verify_section
        or V4_6_1_SCRIPT in readme_verify_section
        or V4_6_2_SCRIPT in readme_verify_section
    )

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| readiness_gate_passed | false |" in measurements_section
    assert "| split_quality_gate_passed | false |" in measurements_section
    assert "| leakage_audit_gate_passed | true |" in measurements_section
    assert "| PDF_source_document_disjoint | 0/20 |" in measurements_section
    assert "| XLSX_workbook_disjoint | 0/8 |" in measurements_section
    assert "| fine_tuning_dataset_exports_created | 0 |" in measurements_section
    assert "| sft_ready | false |" in measurements_section
    assert "| dpo_ready | false |" in measurements_section
    assert "| reward_model_ready | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| gpu_required_for_future_training_when_opened | true |" in measurements_section
    assert "no review CSV, training manifest, dataset sidecar, checkpoint, or per-run Markdown is created" in measurements_section

    assert run_id in triage_section
    assert "diagnostic fine-tuning-readiness packet" in triage_section
    assert "not actual fine-tuning/training" in triage_section
    assert "Split quality remains blocked" in triage_section
    assert "Leakage audit infrastructure is carried forward as exclusion coverage" in triage_section
    assert "SFT, DPO, and reward-model lanes are all blocked" in triage_section
    assert "user-owned label/qrels/denominator policy" in triage_section
    assert "rag_v4_5_finetune_readiness_packet_nonprod.py" in scripts_readme


def test_v4_5_1_holdout_candidate_intake_gate_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod"
    event_type = "diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_5_1_HOLDOUT_CANDIDATE_INTAKE_GATE_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_5_1 Holdout Candidate Intake Gate",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_5_1 Holdout Candidate Intake Gate Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["holdout_candidate_intake_only"] is True
    assert event["candidate_intake_schema_ready"] is True
    assert event["candidate_manifest_present"] is False
    assert event["candidate_manifest_rows"] == 0
    assert event["candidate_manifest_jsonl_created"] is False
    assert event["candidate_validation_jsonl_created"] is False
    assert event["candidate_intake_gate_passed"] is False
    assert event["readiness_gate_passed"] is False
    assert event["readiness_decision"] == "blocked_pending_holdout_candidate_manifest_and_user_policy"
    assert event["accepted_pdf_holdout_candidates"] == 0
    assert event["accepted_xlsx_holdout_candidates"] == 0
    assert event["real_unseen_registry_counts"] == {
        "PDF_source_document_disjoint": 0,
        "XLSX_workbook_disjoint": 0,
    }
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["v4_6_ft_dry_run_opened"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []

    assert report["schema_version"] == "rag_v4_5_1_holdout_candidate_intake_gate_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["metrics"]["candidate_manifest_rows"] == 0
    assert report["metrics"]["candidate_intake_gate_passed"] is False
    assert report["candidate_intake_gate"]["blocked_reasons"] == [
        "candidate_manifest_missing",
        "real_disjoint_holdout_candidates_below_target",
        "real_query_fidelity_candidates_below_target",
    ]
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["v4_6_ft_dry_run_opened"] is False

    v4_5_2_current_status = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready"
    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{v4_5_2_current_status}`;" in current_text
        or f"Overall status: `{V4_5_3_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_2_current_status}`" in eval_readme
        or f"Current RAG status: `{V4_5_3_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_5_1 holdout candidate intake gate loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert (
        "rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py" in readme_verify_section
        or "rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py" in readme_verify_section
        or "rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py" in readme_verify_section
        or V4_6_SCRIPT in readme_verify_section
        or V4_6_1_SCRIPT in readme_verify_section
        or V4_6_2_SCRIPT in readme_verify_section
    )

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| candidate_manifest_present | false |" in measurements_section
    assert "| candidate_manifest_rows | 0 |" in measurements_section
    assert "| candidate_intake_gate_passed | false |" in measurements_section
    assert "| accepted_pdf_holdout_candidates | 0/20 |" in measurements_section
    assert "| accepted_xlsx_holdout_candidates | 0/8 |" in measurements_section
    assert "| v4_6_ft_dry_run_opened | false |" in measurements_section
    assert "| fine_tuning_dataset_exports_created | 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no candidate manifest sidecar, validation JSONL, review CSV" in measurements_section

    assert run_id in triage_section
    assert "not a v4_6 fine-tuning dry run" in triage_section
    assert "Current candidate manifest is absent" in triage_section
    assert "Protected target/gold/expected/supporting fields are rejected" in triage_section
    assert "user-owned label/qrels/denominator policy" in triage_section
    assert "rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py" in scripts_readme
    assert "v4_5_1" in v4_plan


def test_v4_5_2_external_holdout_candidate_source_identity_audit_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod"
    event_type = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_5_2_EXTERNAL_HOLDOUT_CANDIDATE_SOURCE_IDENTITY_AUDIT_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_5_2 External Holdout Candidate Source Identity Audit",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_5_2 External Holdout Candidate Source Identity Audit Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["external_holdout_candidate_source_identity_audit_only"] is True
    assert event["source_identity_audit_ready"] is True
    assert event["candidate_manifest_present"] is False
    assert event["candidate_manifest_rows"] == 0
    assert event["prior_identity_ledger_present"] is False
    assert event["prior_identity_rows"] == 0
    assert event["prior_identity_summary_report_present"] is True
    assert event["prior_identity_summary_hash_records"] == 102
    assert event["prior_identity_baseline_present"] is True
    assert event["source_identity_audit_gate_passed"] is False
    assert event["source_identity_collision_count"] == 0
    assert event["source_identity_audit_excluded_count"] == 0
    assert event["real_holdout_available"] is False
    assert event["real_holdout_sufficient"] is False
    assert event["readiness_gate_passed"] is False
    assert event["readiness_decision"] == "blocked_pending_external_manifest_identity_audit_and_user_policy"
    assert event["accepted_pdf_holdout_candidates"] == 0
    assert event["accepted_xlsx_holdout_candidates"] == 0
    assert event["real_unseen_registry_counts"] == {
        "PDF_source_document_disjoint": 0,
        "XLSX_workbook_disjoint": 0,
    }
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["v4_6_ft_dry_run_opened"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []

    assert report["schema_version"] == "rag_v4_5_2_external_holdout_candidate_source_identity_audit_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["metrics"]["candidate_manifest_rows"] == 0
    assert report["metrics"]["prior_identity_rows"] == 0
    assert report["metrics"]["prior_identity_summary_report_present"] is True
    assert report["metrics"]["prior_identity_summary_hash_records"] == 102
    assert report["metrics"]["prior_identity_baseline_present"] is True
    assert report["metrics"]["source_identity_audit_gate_passed"] is False
    assert report["source_identity_audit_gate"]["blocked_reasons"] == [
        "candidate_manifest_missing",
        "real_disjoint_holdout_candidates_below_target",
        "real_query_fidelity_candidates_below_target",
    ]
    assert report["source_identity_audit_gate"]["prior_identity_hash_summary_present"] is True
    assert report["source_identity_audit_gate"]["prior_identity_baseline_present"] is True
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["v4_6_ft_dry_run_opened"] is False

    v4_5_3_current_status = "diagnostic_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod_ready"
    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{v4_5_3_current_status}`;" in current_text
        or f"Overall status: `{V4_6_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{v4_5_3_current_status}`" in readme
        or f"Current RAG status: `{V4_6_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{v4_5_3_current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_5_2 external holdout candidate source identity audit loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert (
        "rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py" in readme_verify_section
        or "rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py" in readme_verify_section
        or V4_6_SCRIPT in readme_verify_section
        or V4_6_1_SCRIPT in readme_verify_section
        or V4_6_2_SCRIPT in readme_verify_section
    )

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| candidate_manifest_present | false |" in measurements_section
    assert "| candidate_manifest_rows | 0 |" in measurements_section
    assert "| prior_identity_ledger_present | false |" in measurements_section
    assert "| prior_identity_rows | 0 |" in measurements_section
    assert "| prior_identity_summary_report_present | true |" in measurements_section
    assert "| prior_identity_summary_hash_records | 102 |" in measurements_section
    assert "| prior_identity_baseline_present | true |" in measurements_section
    assert "| source_identity_audit_gate_passed | false |" in measurements_section
    assert "| source_identity_collision_count | 0 |" in measurements_section
    assert "| v4_6_ft_dry_run_opened | false |" in measurements_section
    assert "| fine_tuning_dataset_exports_created | 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no candidate manifest sidecar, prior identity ledger sidecar" in measurements_section

    assert run_id in triage_section
    assert "not a v4_6 fine-tuning dry run" in triage_section
    assert "no manifest" in triage_section
    assert "v4_5_3 hash-only prior summary baseline" in triage_section
    assert "PDF candidates require document-level identity" in triage_section
    assert "user-owned label/qrels/denominator policy" in triage_section
    assert "rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py" in scripts_readme
    assert "v4_5_2" in v4_plan
    assert "v4_5_2_external_holdout_candidate_source_identity_audit_nonprod" in v4_plan


def test_v4_5_3_external_holdout_prior_identity_summary_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod"
    event_type = "diagnostic_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_5_3_EXTERNAL_HOLDOUT_PRIOR_SOURCE_IDENTITY_LEDGER_SUMMARY_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_5_3 External Holdout Prior Source Identity Ledger Summary",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_5_3 External Holdout Prior Source Identity Ledger Summary Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["prior_source_identity_ledger_summary_only"] is True
    assert event["prior_identity_collision_baseline_available"] is True
    assert event["prior_identity_hash_record_count"] == 102
    assert event["prior_pdf_identity_count"] == 98
    assert event["prior_xlsx_identity_count"] == 4
    assert event["candidate_manifest_present"] is False
    assert event["candidate_manifest_rows"] == 0
    assert event["source_identity_audit_gate_passed"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["v4_6_ft_dry_run_opened"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []

    assert report["schema_version"] == "rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["prior_source_identity_ledger_summary_only"] is True
    assert report["prior_identity_collision_baseline_available"] is True
    assert report["prior_identity_ledger_jsonl_created"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert report["raw_source_identity_values_embedded"] is False
    assert report["raw_local_path_values_exposed"] is False
    assert report["metrics"]["prior_identity_hash_record_count"] == 102
    assert report["metrics"]["prior_pdf_identity_count"] == 98
    assert report["metrics"]["prior_xlsx_identity_count"] == 4
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["v4_6_ft_dry_run_opened"] is False

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_5_3 external holdout prior source identity ledger summary loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert (
        "rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py" in readme_verify_section
        or V4_6_SCRIPT in readme_verify_section
        or V4_6_1_SCRIPT in readme_verify_section
        or V4_6_2_SCRIPT in readme_verify_section
    )

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| prior_source_identity_ledger_summary_only | true |" in measurements_section
    assert "| prior_identity_collision_baseline_available | true |" in measurements_section
    assert "| prior_identity_hash_record_count | 102 |" in measurements_section
    assert "| prior_pdf_identity_count | 98 |" in measurements_section
    assert "| prior_xlsx_identity_count | 4 |" in measurements_section
    assert "| candidate_manifest_present | false |" in measurements_section
    assert "| v4_6_ft_dry_run_opened | false |" in measurements_section
    assert "| fine_tuning_dataset_exports_created | 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no raw prior identity values" in measurements_section

    assert run_id in triage_section
    assert "not a v4_6 fine-tuning dry run" in triage_section
    assert "raw local paths and raw source identities are not exposed" in triage_section
    assert "User-owned decisions remain gold set creation/review" in triage_section
    assert "rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py" in scripts_readme
    assert "v4_5_3" in v4_plan
    assert "v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod" in v4_plan


def test_v4_6_ft_route_policy_preflight_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod"
    event_type = "diagnostic_v4_6_ft_route_policy_dry_run_preflight_nonprod"
    current_status = V4_6_CURRENT_STATUS
    status = "DIAGNOSTIC_V4_6_FT_ROUTE_POLICY_DRY_RUN_PREFLIGHT_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6 FT Route Policy Dry-Run Preflight",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6 FT Route Policy Dry-Run Preflight Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["ft_route_policy_dry_run_preflight_only"] is True
    assert event["all_preflight_gates_passed"] is False
    assert event["v4_5_readiness_gate_passed"] is False
    assert event["v4_5_1_candidate_intake_gate_passed"] is False
    assert event["v4_5_2_source_identity_audit_gate_passed"] is False
    assert event["v4_5_3_prior_identity_baseline_gate_passed"] is True
    assert event["user_owned_gold_policy_gate_passed"] is False
    assert event["official_denominator_gate_passed"] is False
    assert event["promotion_policy_gate_passed"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert set(event["source_report_inputs"]) == {"v4_5", "v4_5_1", "v4_5_2", "v4_5_3"}

    assert report["schema_version"] == "rag_v4_6_ft_route_policy_dry_run_preflight_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["ft_route_policy_dry_run_preflight_only"] is True
    assert report["v4_6_ft_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["metrics"]["v4_5_3_prior_identity_baseline_gate_passed"] is True
    assert report["metrics"]["all_preflight_gates_passed"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["fine_tuning_dataset_export_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["source_atom_registry_canonical_truth"] is True
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["target_locator_used"] is False
    assert report["guardrails"]["gold_locator_used"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_3_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_3_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_3_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6 FT route policy dry-run preflight loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert (
        "rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py" in readme_verify_section
        or V4_6_1_SCRIPT in readme_verify_section
        or V4_6_2_SCRIPT in readme_verify_section
    )

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| ft_route_policy_dry_run_preflight_only | true |" in measurements_section
    assert "| all_preflight_gates_passed | false |" in measurements_section
    assert "| v4_5_3_prior_identity_baseline_gate_passed | true |" in measurements_section
    assert "| ft_route_policy_dry_run_opened | false |" in measurements_section
    assert "| ft_route_policy_dry_run_executed | false |" in measurements_section
    assert "| fine_tuning_dataset_exports_created | 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no prompt payload, raw LLM response, dataset sidecar, training job, checkpoint" in measurements_section

    assert run_id in triage_section
    assert "preflight only" in triage_section
    assert "not the FT-A dry run itself" in triage_section
    assert "user-owned gold/qrels/denominator" in triage_section
    assert "rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py" in scripts_readme
    assert "v4_6" in v4_plan
    assert "v4_6_ft_route_policy_dry_run_preflight_nonprod" in v4_plan


def test_v4_6_1_holdout_manifest_identity_contract_bridge_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod"
    event_type = "diagnostic_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod"
    current_status = V4_6_1_CURRENT_STATUS
    status = "DIAGNOSTIC_V4_6_1_HOLDOUT_CANDIDATE_MANIFEST_IDENTITY_CONTRACT_BRIDGE_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_1 Holdout Candidate Manifest Identity Contract Bridge",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_1 Holdout Candidate Manifest Identity Contract Bridge Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["holdout_candidate_manifest_identity_contract_bridge_only"] is True
    assert event["contract_bridge_gate_passed"] is True
    assert event["contract_hashes_match"] is True
    assert event["identity_probe_passed"] is True
    assert event["v4_6_hash_mismatch_rejection_passed"] is True
    assert event["identity_contract_probe_count"] == 5
    assert event["identity_contract_probe_passed_count"] == 5
    assert event["v4_6_ft_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_5_1", "v4_5_2", "v4_5_3", "v4_6"}
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["holdout_candidate_manifest_identity_contract_bridge_only"] is True
    assert report["contract_bridge_gate"]["passed"] is True
    assert report["contract_bridge_gate"]["contract_hashes_match"] is True
    assert report["contract_bridge_gate"]["identity_probe_passed"] is True
    assert report["contract_bridge_gate"]["v4_6_hash_mismatch_rejection_passed"] is True
    assert len(report["contract_bridge_gate"]["observed_contract_hashes"]) == 6
    assert set(report["contract_bridge_gate"]["observed_contract_hashes"].values()) == {
        report["holdout_candidate_manifest_contract_hash"]
    }
    assert all(row["passed"] is True for row in report["identity_contract_probe_results"])
    assert report["metrics"]["identity_contract_probe_count"] == 5
    assert report["metrics"]["identity_contract_probe_passed_count"] == 5
    assert report["metrics"]["v4_7_official_metric_gate_opened"] is False
    assert report["metrics"]["fine_tuning_dataset_exports_created"] == 0
    assert report["v4_6_ft_dry_run_opened"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["fine_tuning_dataset_export_created"] is False
    assert report["guardrails"]["training_manifest_jsonl_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["source_atom_evidence_bundle_evidence_truth"] is True
    assert report["guardrails"]["searchview_vector_payload_candidate_only"] is True
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_3_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_3_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_3_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6_1 holdout candidate manifest identity contract bridge loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert V4_6_1_SCRIPT in readme_verify_section or V4_6_2_SCRIPT in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| holdout_candidate_manifest_identity_contract_bridge_only | true |" in measurements_section
    assert "| contract_bridge_gate_passed | true |" in measurements_section
    assert "| contract_hashes_match | true |" in measurements_section
    assert "| identity_probe_passed | true |" in measurements_section
    assert "| v4_6_hash_mismatch_rejection_passed | true |" in measurements_section
    assert "| identity_contract_probe_count | 5 |" in measurements_section
    assert "| identity_contract_probe_passed_count | 5 |" in measurements_section
    assert "| ft_route_policy_dry_run_opened | false |" in measurements_section
    assert "| ft_route_policy_dry_run_executed | false |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "| fine_tuning_dataset_exports_created | 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no candidate manifest, validation sidecar" in measurements_section
    assert "prompt payload, raw LLM response, dataset sidecar, training job, checkpoint" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "holdout-candidate manifest identity contract bridge only" in triage_section
    assert "not the FT-A dry run" in triage_section
    assert "not a v4_7 opening" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert V4_6_1_SCRIPT in scripts_readme
    assert "v4_6_1" in v4_plan
    assert "v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod" in v4_plan


def test_v4_6_2_ft_route_policy_fixture_contract_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod"
    event_type = "diagnostic_v4_6_2_ft_route_policy_fixture_contract_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_6_2_FT_ROUTE_POLICY_FIXTURE_CONTRACT_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_2 FT-A Route-Policy Fixture Contract",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_2 FT-A Route-Policy Fixture Contract Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["ft_route_policy_fixture_contract_only"] is True
    assert event["fixture_contract_schema_ready"] is True
    assert event["fixture_contract_schema_check_passed"] is True
    assert event["dry_run_dataset_gate_passed"] is False
    assert event["fixture_validation_probe_count"] == 5
    assert event["accepted_fixture_probe_count"] == 1
    assert event["rejected_fixture_probe_count"] == 4
    assert event["gold_oracle_field_rejection_count"] == 3
    assert event["dataset_export_gate_opened"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["prompt_payload_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_6", "v4_6_1"}
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_2_ft_route_policy_fixture_contract_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["ft_route_policy_fixture_contract_only"] is True
    assert report["ft_a_fixture_contract"]["lane"] == "FT-A"
    assert report["ft_a_fixture_contract"]["row_source"] == "route_policy_audit_rows_only"
    assert "expected_answer" in report["ft_a_fixture_contract"]["forbidden_model_input_fields"]
    assert report["fixture_contract_gate"]["fixture_contract_schema_check_passed"] is True
    assert report["fixture_contract_gate"]["dry_run_dataset_gate_passed"] is False
    assert report["fixture_contract_gate"]["dataset_export_gate_opened"] is False
    assert report["fixture_contract_gate"]["blocked_reasons"] == [
        "dry_run_and_dataset_export_require_all_v4_6_preflight_gates"
    ]
    assert report["metrics"]["fixture_validation_probe_count"] == 5
    assert report["metrics"]["accepted_fixture_probe_count"] == 1
    assert report["metrics"]["rejected_fixture_probe_count"] == 4
    assert report["metrics"]["gold_oracle_field_rejection_count"] == 3
    assert report["metrics"]["dataset_export_gate_opened"] is False
    assert report["metrics"]["v4_7_official_metric_gate_opened"] is False
    assert report["metrics"]["fine_tuning_dataset_exports_created"] == 0
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["prompt_payload_created"] is False
    assert report["raw_llm_response_payload_created"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["fine_tuning_dataset_export_created"] is False
    assert report["guardrails"]["training_manifest_jsonl_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["source_atom_evidence_bundle_evidence_truth"] is True
    assert report["guardrails"]["searchview_vector_payload_candidate_only"] is True
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_3_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_3_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_3_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6_2 FT-A route-policy fixture contract loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert V4_6_2_SCRIPT in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| ft_route_policy_fixture_contract_only | true |" in measurements_section
    assert "| fixture_contract_schema_ready | true |" in measurements_section
    assert "| fixture_contract_schema_check_passed | true |" in measurements_section
    assert "| dry_run_dataset_gate_passed | false |" in measurements_section
    assert "| fixture_validation_probe_count | 5 |" in measurements_section
    assert "| accepted_fixture_probe_count | 1 |" in measurements_section
    assert "| rejected_fixture_probe_count | 4 |" in measurements_section
    assert "| gold_oracle_field_rejection_count | 3 |" in measurements_section
    assert "| dataset_export_gate_opened | false |" in measurements_section
    assert "| ft_route_policy_dry_run_opened | false |" in measurements_section
    assert "| ft_route_policy_dry_run_executed | false |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "| fine_tuning_dataset_exports_created | 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no prompt payload, raw LLM response, dataset sidecar, training manifest" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "FT-A route-policy fixture contract only" in triage_section
    assert "not the FT-A dry run" in triage_section
    assert "not dataset export" in triage_section
    assert "not a v4_7 opening" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert V4_6_2_SCRIPT in scripts_readme
    assert "v4_6_2" in v4_plan
    assert "v4_6_2_ft_route_policy_fixture_contract_nonprod" in v4_plan


def test_v4_6_3_ft_a_prompt_policy_baseline_schema_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod"
    event_type = "diagnostic_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_6_3_FT_A_PROMPT_POLICY_BASELINE_SCHEMA_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_3 FT-A Prompt-Policy Baseline Schema",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_3 FT-A Prompt-Policy Baseline Schema Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["ft_a_prompt_policy_baseline_schema_only"] is True
    assert event["prompt_policy_baseline_schema_check_passed"] is True
    assert event["dry_run_prompt_baseline_gate_passed"] is False
    assert event["fixture_contract_gate_ready"] is True
    assert event["future_dry_run_required_output_count"] == 4
    assert event["stop_condition_audit_bucket_count"] == 5
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["prompt_payload_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_6_2"}
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_3_ft_a_prompt_policy_baseline_schema_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["ft_a_prompt_policy_baseline_schema_only"] is True
    assert report["prompt_policy_baseline_schema"]["prompt_only_baseline_schema_frozen"] is True
    assert report["prompt_policy_baseline_schema"]["raw_prompt_text_embedded"] is False
    assert report["prompt_policy_baseline_schema"]["prompt_payload_created"] is False
    assert report["prompt_policy_baseline_gate"]["prompt_policy_baseline_schema_check_passed"] is True
    assert report["prompt_policy_baseline_gate"]["dry_run_prompt_baseline_gate_passed"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_4_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_4_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_4_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6_3 FT-A prompt-policy baseline schema loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert V4_6_3_SCRIPT in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| ft_a_prompt_policy_baseline_schema_only | true |" in measurements_section
    assert "| prompt_policy_baseline_schema_check_passed | true |" in measurements_section
    assert "| dry_run_prompt_baseline_gate_passed | false |" in measurements_section
    assert "| future_dry_run_required_output_count | 4 |" in measurements_section
    assert "| stop_condition_audit_bucket_count | 5 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no raw prompt text, prompt payload, raw LLM response, dataset sidecar" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "schema-only" in triage_section
    assert "not the FT-A dry run" in triage_section
    assert "not prompt payload creation" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert V4_6_3_SCRIPT in scripts_readme
    assert "v4_6_3" in v4_plan
    assert "v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod" in v4_plan


def test_v4_6_4_ft_a_dry_run_input_manifest_validator_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod"
    event_type = "diagnostic_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_6_4_FT_A_DRY_RUN_INPUT_MANIFEST_VALIDATOR_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_4 FT-A Dry-Run Input Manifest Validator",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_4 FT-A Dry-Run Input Manifest Validator Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["ft_a_dry_run_input_manifest_validator_only"] is True
    assert event["manifest_validator_schema_check_passed"] is True
    assert event["dry_run_input_manifest_gate_passed"] is False
    assert event["prompt_policy_baseline_gate_ready"] is True
    assert event["fixture_row_count"] == 6
    assert event["accepted_manifest_row_count"] == 1
    assert event["excluded_manifest_row_count"] == 5
    assert event["gold_or_prompt_or_output_rejection_count"] == 3
    assert event["manifest_rows_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["prompt_payload_created"] is False
    assert event["prompt_manifest_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_6_2", "v4_6_3"}
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_4_ft_a_dry_run_input_manifest_validator_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["ft_a_dry_run_input_manifest_validator_only"] is True
    assert report["dry_run_input_manifest_contract"]["manifest_validator_schema_ready"] is True
    assert report["dry_run_input_manifest_contract"]["manifest_rows_exported"] is False
    assert report["dry_run_input_manifest_gate"]["manifest_validator_schema_check_passed"] is True
    assert report["dry_run_input_manifest_gate"]["dry_run_input_manifest_gate_passed"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_5_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_5_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_5_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6_4 FT-A dry-run input manifest validator loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert V4_6_4_SCRIPT in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| ft_a_dry_run_input_manifest_validator_only | true |" in measurements_section
    assert "| manifest_validator_schema_check_passed | true |" in measurements_section
    assert "| dry_run_input_manifest_gate_passed | false |" in measurements_section
    assert "| accepted_manifest_row_count | 1 |" in measurements_section
    assert "| excluded_manifest_row_count | 5 |" in measurements_section
    assert "| gold_or_prompt_or_output_rejection_count | 3 |" in measurements_section
    assert "| manifest_rows_exported | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no dry-run input manifest sidecar, prompt manifest, raw LLM response" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "validator-only" in triage_section
    assert "not the FT-A dry run" in triage_section
    assert "not manifest export" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert V4_6_4_SCRIPT in scripts_readme
    assert "v4_6_4" in v4_plan
    assert "v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod" in v4_plan


def test_v4_6_5_ft_a_dry_run_execution_plan_gate_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod"
    event_type = "diagnostic_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_6_5_FT_A_DRY_RUN_EXECUTION_PLAN_GATE_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_5 FT-A Dry-Run Execution Plan Gate",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_5 FT-A Dry-Run Execution Plan Gate Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["ft_a_dry_run_execution_plan_gate_only"] is True
    assert event["dry_run_execution_plan_schema_check_passed"] is True
    assert event["dry_run_execution_plan_gate_passed"] is False
    assert event["dry_run_execution_plan_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["prompt_payload_created"] is False
    assert event["prompt_manifest_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_6_4"}
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_5_ft_a_dry_run_execution_plan_gate_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["ft_a_dry_run_execution_plan_gate_only"] is True
    assert report["dry_run_execution_plan_contract"]["execution_plan_schema_ready"] is True
    assert report["dry_run_execution_plan_contract"]["dry_run_execution_plan_exported"] is False
    assert report["dry_run_execution_plan_gate"]["dry_run_execution_plan_schema_check_passed"] is True
    assert report["dry_run_execution_plan_gate"]["dry_run_execution_plan_gate_passed"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_5_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_5_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_5_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6_5 FT-A dry-run execution plan gate loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert V4_6_5_SCRIPT in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| ft_a_dry_run_execution_plan_gate_only | true |" in measurements_section
    assert "| dry_run_execution_plan_schema_check_passed | true |" in measurements_section
    assert "| dry_run_execution_plan_gate_passed | false |" in measurements_section
    assert "| dry_run_execution_plan_exported | false |" in measurements_section
    assert "| dry_run_input_manifest_exported | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no dry-run execution plan sidecar, dry-run input manifest sidecar, prompt manifest, raw LLM response" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "execution-plan-gate-only" in triage_section
    assert "not the FT-A dry run" in triage_section
    assert "not dry-run execution" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert V4_6_5_SCRIPT in scripts_readme
    assert "v4_6_5" in v4_plan
    assert "v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod" in v4_plan


def test_v4_6_6_holdout_gap_blocker_ledger_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod"
    event_type = "diagnostic_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_6_6_HOLDOUT_GAP_AND_DRY_RUN_BLOCKER_LEDGER_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_6 Holdout Gap And Dry-Run Blocker Ledger",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_6 Holdout Gap And Dry-Run Blocker Ledger Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["holdout_gap_and_dry_run_blocker_ledger_only"] is True
    assert event["real_holdout_available"] is False
    assert event["real_holdout_sufficient"] is False
    assert event["candidate_manifest_present"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["all_non_gold_source_gates_passed"] is False
    assert event["dry_run_blocker_count"] >= 6
    assert event["dry_run_execution_plan_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["prompt_payload_created"] is False
    assert event["prompt_manifest_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {
        "v4_4",
        "v4_5",
        "v4_5_1",
        "v4_5_2",
        "v4_5_3",
        "v4_6",
        "v4_6_1",
        "v4_6_2",
        "v4_6_3",
        "v4_6_4",
        "v4_6_5",
    }
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["holdout_gap_and_dry_run_blocker_ledger_only"] is True
    assert report["holdout_gap_ledger"]["real_holdout_sufficient"] is False
    assert report["holdout_gap_ledger"]["deficits"]["pdf_source_document_disjoint_needed"] == 20
    assert report["holdout_gap_ledger"]["deficits"]["xlsx_workbook_disjoint_needed"] == 8
    assert report["dry_run_blocker_ledger"]["all_non_gold_source_gates_passed"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_7_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_7_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_7_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6_6 holdout gap and dry-run blocker ledger loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert V4_6_6_SCRIPT in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| holdout_gap_and_dry_run_blocker_ledger_only | true |" in measurements_section
    assert "| real_holdout_sufficient | false |" in measurements_section
    assert "| candidate_manifest_exported | false |" in measurements_section
    assert "| all_non_gold_source_gates_passed | false |" in measurements_section
    assert "| dry_run_execution_plan_exported | false |" in measurements_section
    assert "| dry_run_input_manifest_exported | false |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no holdout-gap sidecar, dry-run-blocker sidecar, candidate manifest sidecar" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "ledger-only" in triage_section
    assert "not external holdout acquisition" in triage_section
    assert "not dry-run execution" in triage_section
    assert "user-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert V4_6_6_SCRIPT in scripts_readme
    assert "v4_6_6" in v4_plan
    assert "v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod" in v4_plan


def test_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod"
    event_type = "diagnostic_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_6_7_HOLDOUT_CANDIDATE_RUNTIME_GATE_PARITY_BRIDGE_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    script_name = "rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py"
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_7 Holdout Candidate Runtime Gate Parity Bridge",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_7 Holdout Candidate Runtime Gate Parity Bridge Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["holdout_candidate_runtime_gate_parity_bridge_only"] is True
    assert event["runtime_parity_probe_only"] is True
    assert event["all_parity_checks_passed"] is True
    assert event["runtime_candidate_intake_gate_matches_v4_5_1"] is True
    assert event["runtime_source_identity_audit_gate_matches_v4_5_2"] is True
    assert event["runtime_prior_hash_collision_matches_v4_5_2"] is True
    assert event["real_holdout_sufficient"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["dry_run_execution_plan_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["prompt_payload_created"] is False
    assert event["prompt_manifest_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_5_1", "v4_5_2", "v4_5_3", "v4_6_6"}
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["holdout_candidate_runtime_gate_parity_bridge_only"] is True
    assert report["runtime_gate_parity"]["all_parity_checks_passed"] is True
    assert report["real_holdout_sufficient"] is False
    assert report["candidate_manifest_exported"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_8_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_8_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_8_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6_7 holdout candidate runtime gate parity bridge loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert script_name in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| holdout_candidate_runtime_gate_parity_bridge_only | true |" in measurements_section
    assert "| runtime_parity_probe_only | true |" in measurements_section
    assert "| all_parity_checks_passed | true |" in measurements_section
    assert "| real_holdout_sufficient | false |" in measurements_section
    assert "| candidate_manifest_exported | false |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no runtime parity sidecar, candidate manifest sidecar" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "parity-bridge-only" in triage_section
    assert "not real holdout availability" in triage_section
    assert "not dry-run execution" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert script_name in scripts_readme
    assert "v4_6_7" in v4_plan
    assert "v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod" in v4_plan


def test_v4_6_8_runtime_readiness_dependency_freshness_gate_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod"
    event_type = "diagnostic_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_6_8_RUNTIME_READINESS_DEPENDENCY_FRESHNESS_GATE_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    script_name = V4_6_8_SCRIPT
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_8 Runtime Readiness Dependency Freshness Gate",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_8 Runtime Readiness Dependency Freshness Gate Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["runtime_readiness_dependency_freshness_gate_only"] is True
    assert event["external_holdout_acquisition_requirements_packet_only"] is True
    assert event["all_source_report_hashes_current"] is True
    assert event["runtime_readiness_dto_projection_matches_v4_6_6"] is True
    assert event["holdout_validation_contract_hash_matches"] is True
    assert event["forbidden_surface_violation_count"] == 0
    assert event["raw_source_identity_or_path_leak_count"] == 0
    assert event["real_holdout_sufficient"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_5_1", "v4_5_2", "v4_5_3", "v4_6_6", "v4_6_7"}
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_8_runtime_readiness_dependency_freshness_gate_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["runtime_readiness_dependency_freshness_gate_only"] is True
    assert report["dependency_freshness_gate"]["gate_passed"] is True
    assert report["real_holdout_sufficient"] is False
    assert report["candidate_manifest_exported"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_9_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_9_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_9_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6_8 runtime readiness dependency freshness gate loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert script_name in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| runtime_readiness_dependency_freshness_gate_only | true |" in measurements_section
    assert "| external_holdout_acquisition_requirements_packet_only | true |" in measurements_section
    assert "| all_source_report_hashes_current | true |" in measurements_section
    assert "| runtime_readiness_dto_projection_matches_v4_6_6 | true |" in measurements_section
    assert "| real_holdout_sufficient | false |" in measurements_section
    assert "| candidate_manifest_exported | false |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "no acquisition sidecar, candidate manifest sidecar" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "dependency-freshness-gate-only" in triage_section
    assert "not real holdout availability" in triage_section
    assert "not dry-run execution" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert script_name in scripts_readme
    assert "v4_6_8" in v4_plan
    assert "v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod" in v4_plan


def test_v4_6_9_holdout_candidate_duplicate_hygiene_gate_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod"
    event_type = "diagnostic_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod"
    current_status = f"{event_type}_ready"
    status = "DIAGNOSTIC_V4_6_9_HOLDOUT_CANDIDATE_DUPLICATE_HYGIENE_GATE_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    script_name = V4_6_9_SCRIPT
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_9 Holdout Candidate Duplicate Hygiene Gate",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_9 Holdout Candidate Duplicate Hygiene Gate Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["holdout_candidate_duplicate_hygiene_gate_only"] is True
    assert event["duplicate_hygiene_gate_passed"] is True
    assert event["runtime_invalid_first_duplicate_rejected"] is True
    assert event["script_invalid_first_duplicate_rejected"] is True
    assert event["real_holdout_sufficient"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_5_1", "v4_6_7", "v4_6_8"}
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["holdout_candidate_duplicate_hygiene_gate_only"] is True
    assert report["duplicate_hygiene_gate"]["gate_passed"] is True
    assert report["duplicate_hygiene_gate"]["runtime_invalid_first_duplicate_rejected"] is True
    assert report["duplicate_hygiene_gate"]["script_invalid_first_duplicate_rejected"] is True
    assert report["real_holdout_sufficient"] is False
    assert report["candidate_manifest_exported"] is False
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert (
        f"Overall status: `{current_status}`;" in current_text
        or f"Overall status: `{V4_6_10_CURRENT_STATUS}`;" in current_text
    )
    assert (
        f"Current RAG status: `{current_status}`" in readme
        or f"Current RAG status: `{V4_6_10_CURRENT_STATUS}`" in readme
    )
    assert (
        f"Current RAG status: `{current_status}`" in eval_readme
        or f"Current RAG status: `{V4_6_10_CURRENT_STATUS}`" in eval_readme
    )
    assert "current diagnostic v4_6_9 holdout candidate duplicate hygiene gate loop" in current_text
    assert "current diagnostic v4_6_8 runtime readiness dependency freshness gate loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert script_name in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| holdout_candidate_duplicate_hygiene_gate_only | true |" in measurements_section
    assert "| duplicate_hygiene_gate_passed | true |" in measurements_section
    assert "| runtime_invalid_first_duplicate_rejected | true |" in measurements_section
    assert "| script_invalid_first_duplicate_rejected | true |" in measurements_section
    assert "| real_holdout_sufficient | false |" in measurements_section
    assert "| candidate_manifest_exported | false |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "sanitized in-memory duplicate probes" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "duplicate-hygiene-gate-only" in triage_section
    assert "not external holdout acquisition" in triage_section
    assert "not dry-run execution" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert script_name in scripts_readme
    assert "v4_6_9" in v4_plan
    assert "v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod" in v4_plan


def test_v4_6_10_external_holdout_manifest_gate_replay_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod"
    event_type = "diagnostic_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod"
    current_status = V4_6_10_CURRENT_STATUS
    status = "DIAGNOSTIC_V4_6_10_EXTERNAL_HOLDOUT_CANDIDATE_MANIFEST_GATE_REPLAY_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    script_name = V4_6_10_SCRIPT
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_10 External Holdout Candidate Manifest Gate Replay",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_10 External Holdout Candidate Manifest Gate Replay Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["external_holdout_candidate_manifest_gate_replay_only"] is True
    assert event["gate_passed"] is False
    assert event["gate_opened"] is False
    assert event["candidate_manifest_present"] is False
    assert event["candidate_rows_replayed"] == 0
    assert event["missing_user_owned_input_count"] == 6
    assert event["codex_owned_dependency_checks_passed"] is True
    assert event["real_holdout_sufficient"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_5_1", "v4_5_2", "v4_5_3", "v4_6_6", "v4_6_8", "v4_6_9"}
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["external_holdout_candidate_manifest_gate_replay_only"] is True
    assert report["external_holdout_candidate_manifest_gate_replay"]["gate_passed"] is False
    assert report["external_holdout_candidate_manifest_gate_replay"]["candidate_manifest_present"] is False
    assert report["external_holdout_candidate_manifest_gate_replay"]["candidate_rows_replayed"] == 0
    assert report["official_metric_opening_preflight"]["gate_passed"] is False
    assert report["official_metric_opening_preflight"]["missing_user_owned_input_count"] == 6
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["source_report_inputs"] == event["source_report_inputs"]
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report

    assert f"Overall status: `{current_status}`;" in current_text
    assert f"Current RAG status: `{current_status}`" in readme
    assert f"Current RAG status: `{current_status}`" in eval_readme
    assert "current diagnostic v4_6_10 external holdout candidate manifest gate replay loop" in current_text
    assert "current diagnostic v4_6_9 holdout candidate duplicate hygiene gate loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert script_name in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| external_holdout_candidate_manifest_gate_replay_only | true |" in measurements_section
    assert "| gate_passed | false |" in measurements_section
    assert "| candidate_manifest_present | false |" in measurements_section
    assert "| candidate_rows_replayed | 0 |" in measurements_section
    assert "| missing_user_owned_input_count | 6 |" in measurements_section
    assert "| codex_owned_dependency_checks_passed | true |" in measurements_section
    assert "| real_holdout_sufficient | false |" in measurements_section
    assert "| candidate_manifest_exported | false |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "not a v4_7 opening" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "external-holdout-candidate-manifest-gate-replay-only" in triage_section
    assert "not a v4_7 opening" in triage_section
    assert "not external holdout acquisition" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert script_name in scripts_readme
    assert "v4_6_10" in v4_plan
    assert "v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod" in v4_plan


def test_v4_6_11_ft_a_runtime_input_validation_route_parity_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod"
    event_type = "diagnostic_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod"
    current_status = V4_6_11_CURRENT_STATUS
    status = "DIAGNOSTIC_V4_6_11_FT_A_RUNTIME_INPUT_VALIDATION_ROUTE_PARITY_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    script_name = V4_6_11_SCRIPT
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_11 FT-A Runtime Input Validation Route Parity",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_11 FT-A Runtime Input Validation Route Parity Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["ft_a_runtime_input_validation_route_parity_only"] is True
    assert event["runtime_parity_probe_only"] is True
    assert event["script_runtime_counts_match"] is True
    assert event["contract_metadata_bridge_present"] is True
    assert event["runtime_response_sanitized"] is True
    assert event["runtime_rejects_operational_metric_identity_fields"] is True
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_6_4", "v4_6_5", "v4_6_6", "v4_6_10"}

    assert report["schema_version"] == "rag_v4_6_11_ft_a_runtime_input_validation_route_parity_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["ft_a_runtime_input_validation_route_parity_only"] is True
    assert report["ft_a_runtime_input_validation_route_parity"]["script_runtime_counts_match"] is True
    assert report["ft_a_runtime_input_validation_route_parity"]["runtime_response_sanitized"] is True
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["source_report_inputs"] == event["source_report_inputs"]

    assert f"Overall status: `{current_status}`;" in current_text
    assert f"Current RAG status: `{current_status}`" in readme
    assert f"Current RAG status: `{current_status}`" in eval_readme
    assert "current diagnostic v4_6_11 FT-A runtime input validation route parity loop" in current_text
    assert "current diagnostic v4_6_10 external holdout candidate manifest gate replay loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert script_name in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| ft_a_runtime_input_validation_route_parity_only | true |" in measurements_section
    assert "| runtime_parity_probe_only | true |" in measurements_section
    assert "| disabled_route_status_code | 404 |" in measurements_section
    assert "| production_disabled_route_status_code | 404 |" in measurements_section
    assert "| enabled_valid_probe_status_code | 200 |" in measurements_section
    assert "| enabled_validation_error_status_code | 422 |" in measurements_section
    assert "| script_runtime_counts_match | true |" in measurements_section
    assert "| runtime_response_sanitized | true |" in measurements_section
    assert "| dry_run_input_manifest_exported | false |" in measurements_section
    assert "| ft_route_policy_dry_run_opened | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "not FT-A dry-run execution" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "runtime-parity-probe-only" in triage_section
    assert "not dry-run input manifest export" in triage_section
    assert "not FT-A dry-run execution" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert script_name in scripts_readme
    assert "v4_6_11" in v4_plan
    assert "v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod" in v4_plan


def test_v4_6_12_external_holdout_runtime_replay_route_parity_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
    event_type = "diagnostic_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
    current_status = V4_6_12_CURRENT_STATUS
    status = "DIAGNOSTIC_V4_6_12_EXTERNAL_HOLDOUT_RUNTIME_REPLAY_ROUTE_PARITY_NONPROD_READY"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_run_family = (
        "official_answer_citation_agentic_loop_run_v4_"
        "source_grounded_runtime_locator_and_finetune_readiness_nonprod"
    )
    script_name = V4_6_12_SCRIPT
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6_12 External Holdout Runtime Replay Route Parity",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6_12 External Holdout Runtime Replay Route Parity Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    v4_plan = (ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md").read_text(
        encoding="utf-8"
    )
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["v4_name"] == v4_id
    assert event["run_family"] == v4_run_family
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["external_holdout_runtime_replay_route_parity_only"] is True
    assert event["runtime_parity_probe_only"] is True
    assert event["route_candidate_counts_match_v4_6_10_replay"] is True
    assert event["route_source_identity_audit_matches_v4_6_10_replay"] is True
    assert event["route_response_sanitized"] is True
    assert event["transient_external_manifest_deleted"] is True
    assert event["candidate_manifest_exported"] is False
    assert event["candidate_manifest_jsonl_created"] is False
    assert event["candidate_validation_jsonl_created"] is False
    assert event["source_identity_audit_jsonl_created"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["review_csv_created"] is False
    assert event["per_run_markdown_created"] is False
    assert set(event["source_report_inputs"]) == {"v4_6_7", "v4_6_10", "v4_6_11"}

    assert report["schema_version"] == "rag_v4_6_12_external_holdout_runtime_replay_route_parity_report_v1"
    assert report["run_id"] == run_id
    assert report["summary"]["status"] == status
    assert report["diagnostic_only"] is True
    assert report["external_holdout_runtime_replay_route_parity_only"] is True
    assert report["external_holdout_runtime_replay_route_parity"]["route_response_sanitized"] is True
    assert report["external_holdout_runtime_replay_route_parity"]["route_candidate_counts_match_v4_6_10_replay"] is True
    assert report["candidate_manifest_exported"] is False
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["source_report_inputs"] == event["source_report_inputs"]

    assert f"Overall status: `{current_status}`;" in current_text
    assert f"Current RAG status: `{current_status}`" in readme
    assert f"Current RAG status: `{current_status}`" in eval_readme
    assert "current diagnostic v4_6_12 external holdout runtime replay route parity loop" in current_text
    assert "current diagnostic v4_6_11 FT-A runtime input validation route parity loop" in current_text
    assert run_id in current_text
    assert v4_id in current_text
    assert "official_metric=false" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "product_success_evidence_allowed=false" in current_flat
    assert "promotion_evidence=false" in current_flat
    assert "fine_tuning_executed=false" in current_flat
    assert "live_db_index_cache_readiness=false" in current_flat
    assert script_name in readme_verify_section

    assert run_id in measurements_section
    assert v4_id in measurements_section
    assert v4_run_family in measurements_section
    assert report_path.relative_to(ROOT).as_posix() in measurements_section
    assert "| external_holdout_runtime_replay_route_parity_only | true |" in measurements_section
    assert "| runtime_parity_probe_only | true |" in measurements_section
    assert "| route_candidate_counts_match_v4_6_10_replay | true |" in measurements_section
    assert "| route_response_sanitized | true |" in measurements_section
    assert "| transient_external_manifest_deleted | true |" in measurements_section
    assert "| candidate_manifest_exported | false |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "not real external holdout registration" in measurements_section

    assert run_id in triage_section
    assert "diagnostic-only" in triage_section
    assert "route-parity-probe-only" in triage_section
    assert "not real holdout registration" in triage_section
    assert "not a v4_7 opening" in triage_section
    assert "User-owned gold/qrels/denominator/promotion decisions remain closed" in triage_section
    assert script_name in scripts_readme
    assert "v4_6_12" in v4_plan
    assert "v4_6_12_external_holdout_runtime_replay_route_parity_nonprod" in v4_plan


def test_v4_6_input_waiting_closeout_records_status_docs_and_keeps_v4_7_closed():
    run_id = "v4_6_input_waiting_ft_a_route_policy_and_external_holdout_readiness_closeout"
    event_type = run_id
    current_status = V4_6_CLOSEOUT_CURRENT_STATUS
    status = "V4_6_INPUT_WAITING_FT_A_ROUTE_POLICY_AND_EXTERNAL_HOLDOUT_READINESS_CLOSEOUT_READY"
    latest_run_id = "official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_6 Input-Waiting FT-A Route-Policy And External-Holdout Readiness Closeout",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_6 Input-Waiting FT-A Route-Policy And External-Holdout Readiness Closeout Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == status
    assert event["diagnostic_only"] is True
    assert event["v4_name"] == v4_id
    assert event["latest_run_id"] == latest_run_id
    assert event["v4_6_codex_owned_diagnostic_preflight_work_completed"] is True
    assert event["v4_6_input_waiting"] is True
    assert event["v4_6_7_through_v4_6_12_checks_only"] == [
        "route_parity",
        "dependency_freshness",
        "duplicate_hygiene",
        "manifest_replay",
        "redaction_checks",
    ]
    assert event["candidate_manifest_present"] is False
    assert event["real_holdout_sufficient"] is False
    assert event["accepted_pdf_holdout_candidates"] == 0
    assert event["accepted_pdf_holdout_candidate_target"] == 20
    assert event["accepted_xlsx_holdout_candidates"] == 0
    assert event["accepted_xlsx_holdout_candidate_target"] == 8
    assert event["real_query_fidelity_included_rows_per_family"] == {"PDF": 0, "XLSX": 0}
    assert event["real_query_fidelity_included_rows_per_family_target"] == 100
    assert event["v4_5_readiness_gate"] is False
    assert event["v4_5_1_intake_gate"] is False
    assert event["v4_5_2_source_identity_audit_gate"] is False
    assert event["user_owned_gold_qrels_policy_gate"] is False
    assert event["official_denominator_gate"] is False
    assert event["promotion_policy_gate"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["candidate_validation_jsonl_created"] is False
    assert event["source_identity_audit_jsonl_created"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["prompt_payload_created"] is False
    assert event["fine_tuning_dataset_export_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["product_success_evidence_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["next_actionable_lane"] == (
        "external_source_disjoint_holdout_candidate_manifest_acquisition_registration_then_"
        "v4_5_1_v4_5_2_v4_6_10_no_write_replay"
    )
    assert event["user_owned_decisions_remain_limited_to"] == [
        "gold set creation/review",
        "expected answer/evidence judgment",
        "relevance/answerability labels",
        "gold policy",
        "official denominator policy",
        "promotion policy",
    ]

    assert f"Overall status: `{current_status}`;" in current_text
    assert f"Current RAG status: `{current_status}`" in readme
    assert f"Current RAG status: `{current_status}`" in eval_readme
    assert "current latest v4_6 run remains v4_6_12" in current_text
    assert latest_run_id in current_text
    assert "v4_6 completed its Codex-owned diagnostic/preflight work" in current_flat
    assert "v4_7 remains closed" in current_flat
    assert "candidate_manifest_present=false" in current_flat
    assert "accepted_pdf_holdout_candidates=0/20" in current_flat
    assert "accepted_xlsx_holdout_candidates=0/8" in current_flat
    assert "real_query_fidelity_included_rows_per_family=0/100 PDF and 0/100 XLSX" in current_flat
    assert "external source-disjoint holdout candidate manifest acquisition/registration" in current_flat

    assert run_id in measurements_section
    assert "| candidate_manifest_present | false |" in measurements_section
    assert "| real_holdout_sufficient | false |" in measurements_section
    assert "| accepted_pdf_holdout_candidates | 0/20 |" in measurements_section
    assert "| accepted_xlsx_holdout_candidates | 0/8 |" in measurements_section
    assert "| real_query_fidelity_included_rows_per_family | 0/100 PDF, 0/100 XLSX |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "No candidate manifest, validation sidecar, dry-run input manifest, prompt payload" in measurements_section

    assert run_id in triage_section
    assert "v4_6 completed its Codex-owned diagnostic/preflight work" in triage_section
    assert "v4_6_7 through v4_6_12 were checks only" in triage_section
    assert "v4_7 remains closed" in triage_section
    assert "User-owned decisions remain gold set creation/review" in triage_section
    assert "Do not open v4_7" in triage_section


def test_v4_7_preofficial_external_holdout_registration_records_status_docs_and_guardrails():
    run_id = "official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod"
    event_type = "diagnostic_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod"
    current_status = V4_7_CURRENT_STATUS
    report_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_text = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_text.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    measurements_section = measurements.split(
        "### v4_7 Preofficial External Holdout Candidate Manifest Registration",
        1,
    )[1].split("\n### ", 1)[0]
    triage = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_section = triage.split(
        "### v4_7 Preofficial External Holdout Candidate Manifest Registration Triage",
        1,
    )[1].split("\n### ", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_verify_section = readme.split("## How To Verify Locally", 1)[1].split("## Repo Map", 1)[0]
    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["status"] == current_status
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert event["diagnostic_only"] is True
    assert event["preofficial_external_holdout_candidate_manifest_registration_only"] is True
    assert event["registration_gate_passed"] is True
    assert event["candidate_manifest_available"] is True
    assert event["candidate_rows_registered"] >= 204
    assert event["accepted_pdf_holdout_candidates"] >= 20
    assert event["accepted_xlsx_holdout_candidates"] >= 8
    assert event["real_query_fidelity_included_counts"]["PDF"] >= 100
    assert event["real_query_fidelity_included_counts"]["XLSX"] >= 100
    assert event["rejected_candidate_count"] == 0
    assert event["source_identity_collision_count"] == 0
    assert event["preofficial_candidate_thresholds_met"] is True
    assert event["real_holdout_sufficient"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["promotion_evidence"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["candidate_manifest_jsonl_created"] is False
    assert event["candidate_validation_jsonl_created"] is False
    assert event["source_identity_audit_jsonl_created"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["protected_namespaces_touched"] == []
    assert "prompt_manifest" not in event
    assert "raw_llm_response" not in event

    assert report["schema_version"] == "rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_report_v1"
    assert report["status"] == current_status
    assert report["diagnostic_only"] is True
    assert report["preofficial_external_holdout_candidate_manifest_registration_only"] is True
    assert report["registration_gate_passed"] is True
    assert report["candidate_manifest_available"] is True
    assert report["accepted_pdf_holdout_candidates"] >= 20
    assert report["accepted_xlsx_holdout_candidates"] >= 8
    assert report["rejected_candidate_count"] == 0
    assert report["rejection_buckets"] == {}
    assert report["real_holdout_sufficient"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["candidate_manifest_jsonl_created"] is False
    assert report["candidate_validation_jsonl_created"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert "expected_answer" in report["user_input_requirements_packet"]["forbidden_fields"]
    assert report["user_input_requirements_packet"]["xlsx_workbook_identity_proof"]["source_identity_only_rejected"] is True

    assert f"Overall status: `{current_status}`;" in current_text
    assert f"Current RAG status: `{current_status}`" in readme
    assert f"Current RAG status: `{current_status}`" in eval_readme
    assert run_id in current_text
    assert "pre-official external holdout candidate manifest registration" in current_flat
    assert "official_metric_input_rows=0" in current_flat
    assert "v4_7_official_metric_gate_opened=false" in current_flat
    assert V4_7_SCRIPT in readme_verify_section
    assert V4_7_SCRIPT in scripts_readme

    assert run_id in measurements_section
    assert "| preofficial_external_holdout_candidate_manifest_registration_only | true |" in measurements_section
    assert "| registration_gate_passed | true |" in measurements_section
    assert "| candidate_manifest_available | true |" in measurements_section
    assert "| accepted_pdf_holdout_candidates | 20/20 |" in measurements_section
    assert "| accepted_xlsx_holdout_candidates | 8/8 |" in measurements_section
    assert "| rejected_candidate_count | 0 |" in measurements_section
    assert "| official_metric_input_rows | 0 |" in measurements_section
    assert "| v4_7_official_metric_gate_opened | false |" in measurements_section
    assert "not official metric rows" in measurements_section

    assert run_id in triage_section
    assert "opens only the v4_7 pre-official external holdout candidate manifest" in triage_section
    assert "not official metric" in triage_section
    assert "not FT-A dry-run execution" in triage_section
    assert "User-owned gold/qrels" in triage_section
