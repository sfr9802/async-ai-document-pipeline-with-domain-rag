from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import csv
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]


def windows_long_path(path: Path) -> Path:
    if sys.platform != "win32":
        return path
    path_text = str(path)
    if path_text.startswith("\\\\?\\"):
        return path
    if path.is_absolute():
        return Path("\\\\?\\" + path_text)
    return path


REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
REPORT_ARCHIVE_DIR = REPORT_DIR / "_archive" / "legacy"
EXTERNAL_REPORT_ARCHIVE_DIR = windows_long_path(Path(
    "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
    "rag-ingestion/repo-wide-cleanup-20260519/reports/rag-ingestion-legacy"
))
PRIMARY_EXTERNAL_REPORT_ARCHIVE_DIR = windows_long_path(Path(
    "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
    "rag-ingestion/repo-wide-cleanup-20260521/reports/rag-ingestion-legacy"
))
EXTERNAL_REPORT_ARCHIVE_DIRS = (
    PRIMARY_EXTERNAL_REPORT_ARCHIVE_DIR,
    EXTERNAL_REPORT_ARCHIVE_DIR,
)
README = ROOT / "README.md"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"
REPAIRED_PDF_QUERY_IDS = ("gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001")
RESIDUAL_AUDIT_QUERY_IDS = {
    "gq_auto_030",
    "gq_pdf_section_question_001",
    "text_namu_v2_0017",
}
AGENTIC_RUN_ID = "official_answer_citation_agentic_loop_run_v1"
AGENTIC_V2_RUN_ID = "official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic"
AGENTIC_V2_1_RUN_ID = "official_answer_citation_agentic_loop_run_v2_1_citation_contract_repair"
AGENTIC_V2_2_RUN_ID = "official_answer_citation_agentic_loop_run_v2_2_llm_backend_validation"
AGENTIC_V3_RUN_ID = "official_answer_citation_agentic_loop_run_v3_comparable_live_measurement"
AGENTIC_V3_1_RUN_ID = "official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement"
AGENTIC_V3_1_PRIORITY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage"
)
AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_priority_1_5_triage_strict_json_diagnostics"
)
AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage"
)
AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage"
)
AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage"
)
AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage"
)
AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage"
)
AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic"
)
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic"
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit"
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation"
)
AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement"
)
AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_2_0_current_system_live_baseline"
)
AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_2_1_text_residual_triage"
)
AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_2_2_post_fix_remeasurement"
)
AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation"
)
AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic"
)
AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix"
)
AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement"
)
AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup"
)
AGENTIC_V3_3_0_POST_CLOSURE_SOURCE_OF_TRUTH_AUDIT_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit"
)
AGENTIC_V3_3_2_RETRIEVAL_LABEL_DESIGN_PACKET_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet"
)
AGENTIC_V3_3_3_SILVER_SOURCE_CANDIDATE_DISCOVERY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_3_3_silver_source_candidate_discovery"
)
AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_4_0_official_retrieval_metric_contract"
)
AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet"
)
AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet"
)
AGENTIC_V3_4_2_APPLY_USER_OFFICIAL_RETRIEVAL_QRELS_LABELS_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_4_2_apply_user_official_retrieval_qrels_labels"
)
AGENTIC_V3_4_3_OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_SMOKE_METRIC_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_4_3_official_exact_evidence_retrieval_smoke_metric_computation"
)
AGENTIC_V3_4_4_README_RETRIEVAL_SMOKE_AND_SILVER_READINESS_ARTIFACTS_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_4_4_readme_retrieval_smoke_and_silver_readiness_artifacts"
)
AGENTIC_V3_5_0_STRICT_NON_OFFICIAL_SOURCE_BOUND_CAPACITY_EXPANSION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_0_strict_non_official_source_bound_capacity_expansion"
)
AGENTIC_V3_5_1_PILOT_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_1_pilot_silver_source_manifest_freeze"
)
AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_2_xlsx_source_value_manifest_repair_and_acquisition"
)
AGENTIC_V3_5_3_PDF_PAGE_BBOX_SOURCE_TEXT_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_3_pdf_page_bbox_source_text_manifest_repair_and_acquisition"
)
AGENTIC_V3_5_4_BALANCED_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze"
)
AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit"
)
AGENTIC_V3_6_0_LOW_TOUCH_NOISY_SILVER_POLICY_APPLICATION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_0_low_touch_noisy_silver_policy_application"
)
AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation"
)
AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval"
)
AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze"
)
AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric"
)
AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage"
)
AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe"
)
AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_7_runtime_stability_probe_for_core_only"
)
AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_8_"
    "nonprod_all_source_index_materialization_and_canonical_payload_wiring"
)
AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_8_"
    "source_registry_first_evidence_bundle_architecture_audit"
)
AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_9_"
    "searchunit_searchview_sourceatom_refactor"
)
AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_0_"
    "source_registry_materialization"
)
AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_1_"
    "all_source_citable_nonprod_index_build"
)
AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_2_"
    "local_llm_natural_silver_query_regeneration"
)
AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_2_"
    "source_registry_backed_retrieval_smoke_report"
)
AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_8_file_grounded_retrieval_eval"
)
AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_8_1_evidence_selector_v1"
)
AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_8_2_oracle_free_file_resolve"
)
AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic"
)
AGENTIC_V3_1_PRIORITY_QUERY_IDS = (
    "gq_pdf_section_question_001",
    "text_namu_v2_0012",
    "gq_auto_010",
    "gq_auto_023",
    "gq_xlsx_lookup_008",
)
AGENTIC_DIAGNOSTIC_CLASSIFICATION = (
    "diagnostic_live_generation_fixture_all_index_not_official_denominator_representative"
)
AGENTIC_DIAGNOSTIC_PERFORMANCE_INTERPRETATION = (
    "diagnostic_retrieval_agent_loop_not_final_answer_generation_quality"
)
SOURCE_BOUND_INDEX_BLOCKER = "SOURCE_BOUND_OFFICIAL_DENOMINATOR_SOURCE_FIELDS_MISSING"
REPORT_ARTIFACT_SLUGS = {
    AGENTIC_RUN_ID: "agentic_v1",
    AGENTIC_V2_RUN_ID: "v2_source_bound",
    AGENTIC_V2_1_RUN_ID: "v2_1_citation",
    AGENTIC_V2_2_RUN_ID: "v2_2_backend",
    AGENTIC_V3_RUN_ID: "v3_comparable",
    AGENTIC_V3_1_RUN_ID: "v3_1_foundation",
    AGENTIC_V3_1_PRIORITY_RUN_ID: "v3_1_priority",
    AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID: "v3_1_textloc",
    AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID: "v3_1_1_post_locator",
    AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID: "v3_1_2_span",
    AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID: "v3_1_3_remaining",
    AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID: "v3_1_4_pdf_residual",
    AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID: "v3_1_5_gq010_coverage",
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID: "v3_1_6_gq010_pdfwin",
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID: AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID: AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID: AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID,
    AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID: AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID,
    AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID: AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID,
    AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID: AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID,
    AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID: AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID,
    AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID: AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID,
    AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID: AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
    AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID: AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID,
    AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID: AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID,
    AGENTIC_V3_3_0_POST_CLOSURE_SOURCE_OF_TRUTH_AUDIT_RUN_ID: AGENTIC_V3_3_0_POST_CLOSURE_SOURCE_OF_TRUTH_AUDIT_RUN_ID,
    AGENTIC_V3_3_3_SILVER_SOURCE_CANDIDATE_DISCOVERY_RUN_ID: (
        AGENTIC_V3_3_3_SILVER_SOURCE_CANDIDATE_DISCOVERY_RUN_ID
    ),
    AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID: (
        AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID
    ),
    AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_RUN_ID: (
        AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_RUN_ID
    ),
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID: (
        AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID
    ),
    AGENTIC_V3_4_2_APPLY_USER_OFFICIAL_RETRIEVAL_QRELS_LABELS_RUN_ID: (
        AGENTIC_V3_4_2_APPLY_USER_OFFICIAL_RETRIEVAL_QRELS_LABELS_RUN_ID
    ),
    AGENTIC_V3_4_3_OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_SMOKE_METRIC_RUN_ID: (
        AGENTIC_V3_4_3_OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_SMOKE_METRIC_RUN_ID
    ),
    AGENTIC_V3_4_4_README_RETRIEVAL_SMOKE_AND_SILVER_READINESS_ARTIFACTS_RUN_ID: (
        AGENTIC_V3_4_4_README_RETRIEVAL_SMOKE_AND_SILVER_READINESS_ARTIFACTS_RUN_ID
    ),
    AGENTIC_V3_5_0_STRICT_NON_OFFICIAL_SOURCE_BOUND_CAPACITY_EXPANSION_RUN_ID: (
        AGENTIC_V3_5_0_STRICT_NON_OFFICIAL_SOURCE_BOUND_CAPACITY_EXPANSION_RUN_ID
    ),
    AGENTIC_V3_5_1_PILOT_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID: (
        AGENTIC_V3_5_1_PILOT_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID
    ),
    AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID: (
        AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID
    ),
    AGENTIC_V3_5_3_PDF_PAGE_BBOX_SOURCE_TEXT_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID: (
        AGENTIC_V3_5_3_PDF_PAGE_BBOX_SOURCE_TEXT_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID
    ),
    AGENTIC_V3_5_4_BALANCED_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID: (
        AGENTIC_V3_5_4_BALANCED_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID
    ),
    AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID: (
        AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID
    ),
    AGENTIC_V3_6_0_LOW_TOUCH_NOISY_SILVER_POLICY_APPLICATION_RUN_ID: (
        AGENTIC_V3_6_0_LOW_TOUCH_NOISY_SILVER_POLICY_APPLICATION_RUN_ID
    ),
    AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID: (
        AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID
    ),
    AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID: (
        AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID
    ),
    AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID: (
        AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID
    ),
    AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID: (
        AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID
    ),
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID: (
        AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID
    ),
    AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID: (
        AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID
    ),
    AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID: (
        AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID
    ),
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID: (
        AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID
    ),
    AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID: (
        AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID
    ),
    AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID: (
        AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID
    ),
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID: (
        AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID
    ),
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID: (
        AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID
    ),
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID: (
        AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID
    ),
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID: (
        AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID
    ),
    AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID: AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID: AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID: AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID: AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID,
}
ARCHIVED_REPORT_RUN_IDS = set(REPORT_ARTIFACT_SLUGS) - {
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID,
    AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID,
    AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID,
    AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID,
    AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID,
    AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID,
    AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
    AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID,
    AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID,
    AGENTIC_V3_3_0_POST_CLOSURE_SOURCE_OF_TRUTH_AUDIT_RUN_ID,
    AGENTIC_V3_3_3_SILVER_SOURCE_CANDIDATE_DISCOVERY_RUN_ID,
    AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID,
    AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_RUN_ID,
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID,
    AGENTIC_V3_4_2_APPLY_USER_OFFICIAL_RETRIEVAL_QRELS_LABELS_RUN_ID,
    AGENTIC_V3_4_3_OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_SMOKE_METRIC_RUN_ID,
    AGENTIC_V3_4_4_README_RETRIEVAL_SMOKE_AND_SILVER_READINESS_ARTIFACTS_RUN_ID,
    AGENTIC_V3_5_0_STRICT_NON_OFFICIAL_SOURCE_BOUND_CAPACITY_EXPANSION_RUN_ID,
    AGENTIC_V3_5_1_PILOT_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    AGENTIC_V3_5_3_PDF_PAGE_BBOX_SOURCE_TEXT_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    AGENTIC_V3_5_4_BALANCED_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID,
    AGENTIC_V3_6_0_LOW_TOUCH_NOISY_SILVER_POLICY_APPLICATION_RUN_ID,
    AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID,
    AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID,
    AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID,
    AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID,
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID,
    AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID,
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID,
    AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID,
    AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID,
    AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID,
}
PHYSICALLY_ARCHIVED_REPORT_RUN_IDS = set(REPORT_ARTIFACT_SLUGS) - {
    AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID,
    AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID,
}


def report_artifact_dir(run_id: str) -> Path:
    if run_id not in PHYSICALLY_ARCHIVED_REPORT_RUN_IDS:
        return REPORT_DIR
    return REPORT_ARCHIVE_DIR if REPORT_ARCHIVE_DIR.exists() else PRIMARY_EXTERNAL_REPORT_ARCHIVE_DIR


def archived_report_dir() -> Path:
    return REPORT_ARCHIVE_DIR if REPORT_ARCHIVE_DIR.exists() else PRIMARY_EXTERNAL_REPORT_ARCHIVE_DIR


def report_artifact_path(run_id: str, suffix: str) -> Path:
    return report_artifact_dir(run_id) / f"{REPORT_ARTIFACT_SLUGS[run_id]}_{suffix}"


def report_artifact_repo_relative(run_id: str, suffix: str) -> str:
    logical_dir = REPORT_ARCHIVE_DIR if run_id in ARCHIVED_REPORT_RUN_IDS else REPORT_DIR
    return (logical_dir / f"{REPORT_ARTIFACT_SLUGS[run_id]}_{suffix}").relative_to(ROOT).as_posix()


READINESS_JSON = REPORT_DIR / "source_bound_readiness_v1.json"
AGENTIC_RESULTS = report_artifact_path(AGENTIC_RUN_ID, "results.jsonl")
AGENTIC_SUMMARY_JSON = report_artifact_path(AGENTIC_RUN_ID, "summary.json")
AGENTIC_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_RUN_ID, "failure.json")
AGENTIC_V2_RESULTS = report_artifact_path(AGENTIC_V2_RUN_ID, "results.jsonl")
AGENTIC_V2_SUMMARY_JSON = report_artifact_path(AGENTIC_V2_RUN_ID, "summary.json")
AGENTIC_V2_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V2_RUN_ID, "failure.json")
AGENTIC_V2_1_RESULTS = report_artifact_path(AGENTIC_V2_1_RUN_ID, "results.jsonl")
AGENTIC_V2_1_SUMMARY_JSON = report_artifact_path(AGENTIC_V2_1_RUN_ID, "summary.json")
AGENTIC_V2_1_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V2_1_RUN_ID, "failure.json")
AGENTIC_V2_2_RESULTS = report_artifact_path(AGENTIC_V2_2_RUN_ID, "results.jsonl")
AGENTIC_V2_2_SUMMARY_JSON = report_artifact_path(AGENTIC_V2_2_RUN_ID, "summary.json")
AGENTIC_V2_2_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V2_2_RUN_ID, "failure.json")
AGENTIC_V3_RESULTS = report_artifact_path(AGENTIC_V3_RUN_ID, "results.jsonl")
AGENTIC_V3_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_RUN_ID, "summary.json")
AGENTIC_V3_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_RUN_ID, "failure.json")
AGENTIC_V3_1_RESULTS = report_artifact_path(AGENTIC_V3_1_RUN_ID, "results.jsonl")
AGENTIC_V3_1_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_RUN_ID, "summary.json")
AGENTIC_V3_1_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_RUN_ID, "failure.json")
AGENTIC_V3_1_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_RUN_ID, "queue.json")
AGENTIC_V3_1_PRIORITY_RESULTS = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "results.jsonl")
AGENTIC_V3_1_PRIORITY_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "summary.json")
AGENTIC_V3_1_PRIORITY_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "failure.json")
AGENTIC_V3_1_PRIORITY_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_JSON = REPORT_ARCHIVE_DIR / "v3_1_priority_strict_json.json"
AGENTIC_V3_1_PRIORITY_TRIAGE_DELTA_JSON = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "delta.json")
AGENTIC_V3_1_TEXT_LOCATOR_RESULTS = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "results.jsonl")
AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "summary.json")
AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "summary.md")
AGENTIC_V3_1_TEXT_LOCATOR_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "failure.json")
AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_JSON = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "delta.json")
AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_MD = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "delta.md")
AGENTIC_V3_1_1_POST_RESULTS = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "results.jsonl")
AGENTIC_V3_1_1_POST_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "summary.json")
AGENTIC_V3_1_1_POST_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "summary.md")
AGENTIC_V3_1_1_POST_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "failure.json")
AGENTIC_V3_1_1_POST_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_1_POST_TRIAGE_QUEUE_JSON = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "queue.json")
AGENTIC_V3_1_2_ANSWER_SPAN_RESULTS = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "results.jsonl")
AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "summary.json")
AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "summary.md")
AGENTIC_V3_1_2_ANSWER_SPAN_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "failure.json")
AGENTIC_V3_1_2_ANSWER_SPAN_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "spans.jsonl")
AGENTIC_V3_1_2_ANSWER_SPAN_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "queue.json")
AGENTIC_V3_1_3_REMAINING_QUEUE_RESULTS = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "results.jsonl")
AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "summary.json")
AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "summary.md")
AGENTIC_V3_1_3_REMAINING_QUEUE_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "failure.json")
AGENTIC_V3_1_3_REMAINING_QUEUE_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_3_REMAINING_QUEUE_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "spans.jsonl")
AGENTIC_V3_1_3_REMAINING_QUEUE_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "queue.json")
AGENTIC_V3_1_4_PDF_RESIDUAL_RESULTS = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "results.jsonl")
AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "summary.json")
AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "summary.md")
AGENTIC_V3_1_4_PDF_RESIDUAL_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "failure.json")
AGENTIC_V3_1_4_PDF_RESIDUAL_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_4_PDF_RESIDUAL_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "spans.jsonl")
AGENTIC_V3_1_4_PDF_RESIDUAL_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "queue.json")
AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID, "summary.json")
AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID, "context.jsonl")
AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID, "queue.json")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "results.jsonl")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "summary.json")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "failure.json")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ANSWER_SPAN_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "spans.jsonl")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_CONTEXT_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "context.jsonl")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "queue.json")
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_INVENTORY_JSONL = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "all_track_residual_inventory.jsonl",
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_REMAINING_JSON = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "remaining_triage_queue.json",
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_DECISION_PACKET_JSON = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "user_decision_packet.json",
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SILVER_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "silver_readiness_audit.json",
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    "summary.json",
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_HUMAN_REVIEW_JSON = report_artifact_path(
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    "human_review_packet.json",
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_DECISION_MATRIX_JSONL = report_artifact_path(
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    "decision_matrix.jsonl",
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_REMAINING_JSON = report_artifact_path(
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    "remaining_triage_queue.json",
)
AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_APPLIED_JSONL = report_artifact_path(
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID,
    "applied_overrides.jsonl",
)
AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_DIFF_JSONL = report_artifact_path(
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID,
    "gold_diff.jsonl",
)
AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RESCORED_JSONL = report_artifact_path(
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID,
    "rescored_results.jsonl",
)
AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_REMAINING_JSON = report_artifact_path(
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID,
    "remaining_triage_queue.json",
)
AGENTIC_V3_2_0_RESULTS = report_artifact_path(
    AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID,
    "results.jsonl",
)
AGENTIC_V3_2_0_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_2_0_ATTRIBUTION_JSON = report_artifact_path(
    AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID,
    "failure.json",
)
AGENTIC_V3_2_0_AUDIT_JSONL = report_artifact_path(
    AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID,
    "audit.jsonl",
)
AGENTIC_V3_2_0_QUEUE_JSON = report_artifact_path(
    AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID,
    "queue.json",
)
AGENTIC_V3_2_1_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_2_1_RESIDUAL_TRIAGE_JSONL = report_artifact_path(
    AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID,
    "residual_triage.jsonl",
)
AGENTIC_V3_2_2_RESULTS = report_artifact_path(
    AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID,
    "results.jsonl",
)
AGENTIC_V3_2_2_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID,
    "summary.json",
)
AGENTIC_V3_2_2_ATTRIBUTION_JSON = report_artifact_path(
    AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID,
    "failure.json",
)
AGENTIC_V3_2_2_AUDIT_JSONL = report_artifact_path(
    AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID,
    "audit.jsonl",
)
AGENTIC_V3_2_2_QUEUE_JSON = report_artifact_path(
    AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID,
    "queue.json",
)
AGENTIC_V3_2_3_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID,
    "summary.json",
)
AGENTIC_V3_2_3_DIAGNOSTICS_JSONL = report_artifact_path(
    AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID,
    "diagnostics.jsonl",
)
AGENTIC_V3_2_3_QUEUE_JSON = report_artifact_path(
    AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID,
    "queue.json",
)
AGENTIC_V3_2_4_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_2_4_DIAGNOSTICS_JSONL = report_artifact_path(
    AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID,
    "pdf_context_provenance_diagnostics.jsonl",
)
AGENTIC_V3_2_4_QUEUE_JSON = report_artifact_path(
    AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID,
    "queue.json",
)
AGENTIC_V3_2_5_RESULTS = report_artifact_path(
    AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
    "results.jsonl",
)
AGENTIC_V3_2_5_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
    "summary.json",
)
AGENTIC_V3_2_5_ATTRIBUTION_JSON = report_artifact_path(
    AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
    "failure.json",
)
AGENTIC_V3_2_5_AUDIT_JSONL = report_artifact_path(
    AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
    "audit.jsonl",
)
AGENTIC_V3_2_5_PDF_CONTEXT_DIAGNOSTICS_JSONL = report_artifact_path(
    AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
    "pdf_context_diagnostics.jsonl",
)
AGENTIC_V3_2_5_QUEUE_JSON = report_artifact_path(
    AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
    "queue.json",
)
AGENTIC_V3_2_6_RESULTS = report_artifact_path(
    AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID,
    "results.jsonl",
)
AGENTIC_V3_2_6_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_2_6_ATTRIBUTION_JSON = report_artifact_path(
    AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID,
    "failure.json",
)
AGENTIC_V3_2_6_AUDIT_JSONL = report_artifact_path(
    AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID,
    "audit.jsonl",
)
AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_DIAGNOSTICS_JSONL = report_artifact_path(
    AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID,
    "text_prompt_span_diagnostics.jsonl",
)
AGENTIC_V3_2_6_QUEUE_JSON = report_artifact_path(
    AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID,
    "queue.json",
)
AGENTIC_V3_3_3_SILVER_SOURCE_CANDIDATE_DISCOVERY_INVENTORY_JSON = report_artifact_path(
    AGENTIC_V3_3_3_SILVER_SOURCE_CANDIDATE_DISCOVERY_RUN_ID,
    "candidate_inventory.json",
)
AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_JSON = report_artifact_path(
    AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID,
    "contract.json",
)
AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_QRELS_SCHEMA_JSON = report_artifact_path(
    AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID,
    "qrels_schema.json",
)
AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_JSONL = report_artifact_path(
    AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_RUN_ID,
    "qrels_candidates.jsonl",
)
AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_CSV = report_artifact_path(
    AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_RUN_ID,
    "qrels_candidates.csv",
)
AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_RUN_ID,
    "summary.json",
)
AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_POLICY_APPROVAL_JSON = report_artifact_path(
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID,
    "qrels_policy_approval.json",
)
AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_QUERY_GROUP_REVIEW_CSV = report_artifact_path(
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID,
    "qrels_human_query_group_review.csv",
)
AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_AMBIGUOUS_CANDIDATE_REVIEW_CSV = report_artifact_path(
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID,
    "qrels_ambiguous_candidate_review.csv",
)
AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_AUTO_LABEL_PLAN_JSON = report_artifact_path(
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID,
    "qrels_auto_label_plan.json",
)
AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_MINIMAL_REVIEW_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID,
    "summary.json",
)
AGENTIC_V3_4_2_OFFICIAL_RETRIEVAL_QRELS_JSONL = report_artifact_path(
    AGENTIC_V3_4_2_APPLY_USER_OFFICIAL_RETRIEVAL_QRELS_LABELS_RUN_ID,
    "official_retrieval_qrels.jsonl",
)
AGENTIC_V3_4_2_QRELS_COVERAGE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_4_2_APPLY_USER_OFFICIAL_RETRIEVAL_QRELS_LABELS_RUN_ID,
    "qrels_coverage_summary.json",
)
AGENTIC_V3_4_2_QRELS_EXCLUSION_LEDGER_JSONL = report_artifact_path(
    AGENTIC_V3_4_2_APPLY_USER_OFFICIAL_RETRIEVAL_QRELS_LABELS_RUN_ID,
    "qrels_exclusion_ledger.jsonl",
)
AGENTIC_V3_4_3_RETRIEVAL_SMOKE_METRICS_JSON = report_artifact_path(
    AGENTIC_V3_4_3_OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_SMOKE_METRIC_RUN_ID,
    "metrics.json",
)
AGENTIC_V3_4_3_RETRIEVAL_SMOKE_PER_QUERY_JSONL = report_artifact_path(
    AGENTIC_V3_4_3_OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_SMOKE_METRIC_RUN_ID,
    "per_query.jsonl",
)
AGENTIC_V3_4_4_README_METRIC_CARD_JSON = report_artifact_path(
    AGENTIC_V3_4_4_README_RETRIEVAL_SMOKE_AND_SILVER_READINESS_ARTIFACTS_RUN_ID,
    "readme_metric_card.json",
)
AGENTIC_V3_4_4_README_SECTION_MD = report_artifact_path(
    AGENTIC_V3_4_4_README_RETRIEVAL_SMOKE_AND_SILVER_READINESS_ARTIFACTS_RUN_ID,
    "readme_section.md",
)
AGENTIC_V3_4_4_SILVER_READINESS_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_4_4_README_RETRIEVAL_SMOKE_AND_SILVER_READINESS_ARTIFACTS_RUN_ID,
    "silver_readiness_summary.json",
)
AGENTIC_V3_5_0_CAPACITY_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_5_0_STRICT_NON_OFFICIAL_SOURCE_BOUND_CAPACITY_EXPANSION_RUN_ID,
    "capacity_summary.json",
)
AGENTIC_V3_5_0_MANIFEST_READY_CANDIDATES_JSONL = report_artifact_path(
    AGENTIC_V3_5_0_STRICT_NON_OFFICIAL_SOURCE_BOUND_CAPACITY_EXPANSION_RUN_ID,
    "manifest_ready_candidates.jsonl",
)
AGENTIC_V3_5_0_BLOCKED_OR_CONVERTIBLE_CANDIDATES_JSONL = report_artifact_path(
    AGENTIC_V3_5_0_STRICT_NON_OFFICIAL_SOURCE_BOUND_CAPACITY_EXPANSION_RUN_ID,
    "blocked_or_convertible_candidates.jsonl",
)
AGENTIC_V3_5_0_ACQUISITION_PLAN_JSON = report_artifact_path(
    AGENTIC_V3_5_0_STRICT_NON_OFFICIAL_SOURCE_BOUND_CAPACITY_EXPANSION_RUN_ID,
    "acquisition_plan.json",
)
AGENTIC_V3_5_1_PILOT_SOURCE_MANIFEST_JSONL = report_artifact_path(
    AGENTIC_V3_5_1_PILOT_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    "pilot_source_manifest.jsonl",
)
AGENTIC_V3_5_1_FREEZE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_5_1_PILOT_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    "freeze_summary.json",
)
AGENTIC_V3_5_1_FREEZE_AUDIT_JSONL = report_artifact_path(
    AGENTIC_V3_5_1_PILOT_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    "freeze_audit.jsonl",
)
AGENTIC_V3_5_1_SELECTION_RATIONALE_JSON = report_artifact_path(
    AGENTIC_V3_5_1_PILOT_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    "selection_rationale.json",
)
AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_JSONL = report_artifact_path(
    AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    "xlsx_manifest_ready_candidates.jsonl",
)
AGENTIC_V3_5_2_XLSX_REPAIR_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    "post_xlsx_capacity_summary.json",
)
AGENTIC_V3_5_2_XLSX_REPAIR_AUDIT_JSONL = report_artifact_path(
    AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    "xlsx_blocked_or_convertible_candidates.jsonl",
)
AGENTIC_V3_5_2_XLSX_ACQUISITION_PLAN_JSON = report_artifact_path(
    AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    "xlsx_source_collection_manifest.json",
)
AGENTIC_V3_5_3_PDF_SOURCE_TEXT_MANIFEST_JSONL = report_artifact_path(
    AGENTIC_V3_5_3_PDF_PAGE_BBOX_SOURCE_TEXT_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    "pdf_manifest_ready_candidates.jsonl",
)
AGENTIC_V3_5_3_PDF_REPAIR_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_5_3_PDF_PAGE_BBOX_SOURCE_TEXT_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    "post_pdf_capacity_summary.json",
)
AGENTIC_V3_5_3_PDF_REPAIR_AUDIT_JSONL = report_artifact_path(
    AGENTIC_V3_5_3_PDF_PAGE_BBOX_SOURCE_TEXT_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    "pdf_blocked_or_convertible_candidates.jsonl",
)
AGENTIC_V3_5_3_PDF_ACQUISITION_PLAN_JSON = report_artifact_path(
    AGENTIC_V3_5_3_PDF_PAGE_BBOX_SOURCE_TEXT_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    "pdf_source_collection_manifest.json",
)
AGENTIC_V3_5_3_BALANCED_CAPACITY_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_5_3_PDF_PAGE_BBOX_SOURCE_TEXT_MANIFEST_REPAIR_AND_ACQUISITION_RUN_ID,
    "balanced_capacity_summary.json",
)
AGENTIC_V3_5_4_BALANCED_SOURCE_MANIFEST_JSONL = report_artifact_path(
    AGENTIC_V3_5_4_BALANCED_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    "balanced_source_manifest.jsonl",
)
AGENTIC_V3_5_4_FREEZE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_5_4_BALANCED_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    "freeze_summary.json",
)
AGENTIC_V3_5_4_FREEZE_AUDIT_JSONL = report_artifact_path(
    AGENTIC_V3_5_4_BALANCED_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    "freeze_audit.jsonl",
)
AGENTIC_V3_5_4_AUDIT_SAMPLE_PACKET_JSONL = report_artifact_path(
    AGENTIC_V3_5_4_BALANCED_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    "audit_sample_packet.jsonl",
)
AGENTIC_V3_5_4_NEXT_PHASE_POLICY_BOUNDARY_JSON = report_artifact_path(
    AGENTIC_V3_5_4_BALANCED_SILVER_SOURCE_MANIFEST_FREEZE_RUN_ID,
    "next_phase_policy_boundary.json",
)
AGENTIC_V3_5_5_QUALITY_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID,
    "quality_summary.json",
)
AGENTIC_V3_5_5_MANIFEST_VALIDATION_JSONL = report_artifact_path(
    AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID,
    "manifest_validation.jsonl",
)
AGENTIC_V3_5_5_AUDIT_SAMPLE_REVIEW_PACKET_JSONL = report_artifact_path(
    AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID,
    "audit_sample_review_packet.jsonl",
)
AGENTIC_V3_5_5_DUPLICATE_HASH_AUDIT_JSONL = report_artifact_path(
    AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID,
    "duplicate_hash_audit.jsonl",
)
AGENTIC_V3_5_5_RECOMMENDED_REPAIR_QUEUE_JSONL = report_artifact_path(
    AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID,
    "recommended_repair_queue.jsonl",
)
AGENTIC_V3_5_5_NEXT_PHASE_POLICY_BOUNDARY_JSON = report_artifact_path(
    AGENTIC_V3_5_5_BALANCED_SOURCE_MANIFEST_QUALITY_AUDIT_RUN_ID,
    "next_phase_policy_boundary.json",
)
AGENTIC_V3_6_0_POLICY_APPROVAL_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_0_LOW_TOUCH_NOISY_SILVER_POLICY_APPLICATION_RUN_ID,
    "policy_approval_summary.json",
)
AGENTIC_V3_6_0_GENERATION_CONTRACT_JSON = report_artifact_path(
    AGENTIC_V3_6_0_LOW_TOUCH_NOISY_SILVER_POLICY_APPLICATION_RUN_ID,
    "generation_contract.json",
)
AGENTIC_V3_6_0_USER_DECISION_MATRIX_JSONL = report_artifact_path(
    AGENTIC_V3_6_0_LOW_TOUCH_NOISY_SILVER_POLICY_APPLICATION_RUN_ID,
    "user_decision_matrix.jsonl",
)
AGENTIC_V3_6_0_GUARDRAIL_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_0_LOW_TOUCH_NOISY_SILVER_POLICY_APPLICATION_RUN_ID,
    "guardrail_summary.json",
)
AGENTIC_V3_6_1_WEAK_SILVER_CANDIDATES_JSONL = report_artifact_path(
    AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID,
    "weak_silver_candidates.jsonl",
)
AGENTIC_V3_6_1_GENERATION_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID,
    "generation_summary.json",
)
AGENTIC_V3_6_1_SPLIT_MANIFEST_JSON = report_artifact_path(
    AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID,
    "split_manifest.json",
)
AGENTIC_V3_6_1_QUALITY_DISTRIBUTION_JSON = report_artifact_path(
    AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID,
    "generation_quality_distribution.json",
)
AGENTIC_V3_6_1_BLOCKED_ROWS_JSONL = report_artifact_path(
    AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID,
    "generation_blocked_rows.jsonl",
)
AGENTIC_V3_6_1_POLICY_COMPLIANCE_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID,
    "policy_compliance_audit.json",
)
AGENTIC_V3_6_1_NEXT_PHASE_RECOMMENDATION_JSON = report_artifact_path(
    AGENTIC_V3_6_1_BALANCED_WEAK_NOISY_SILVER_CANDIDATE_GENERATION_RUN_ID,
    "next_phase_recommendation.json",
)
AGENTIC_V3_6_2_CANDIDATE_SANITY_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID,
    "candidate_sanity_summary.json",
)
AGENTIC_V3_6_2_CANDIDATE_SANITY_PER_ROW_JSONL = report_artifact_path(
    AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID,
    "candidate_sanity_per_row.jsonl",
)
AGENTIC_V3_6_2_CANDIDATE_QUARANTINE_ROWS_JSONL = report_artifact_path(
    AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID,
    "candidate_quarantine_rows.jsonl",
)
AGENTIC_V3_6_2_CANDIDATE_METRIC_FEASIBILITY_JSON = report_artifact_path(
    AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID,
    "candidate_metric_feasibility.json",
)
AGENTIC_V3_6_2_SPLIT_INDEPENDENCE_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID,
    "split_independence_audit.json",
)
AGENTIC_V3_6_2_HASH_CONTRACT_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID,
    "hash_contract_audit.json",
)
AGENTIC_V3_6_2_NEXT_PHASE_RECOMMENDATION_JSON = report_artifact_path(
    AGENTIC_V3_6_2_WEAK_NOISY_SILVER_CANDIDATE_SANITY_EVAL_RUN_ID,
    "next_phase_recommendation.json",
)
AGENTIC_V3_6_3_MANIFEST_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID,
    "diagnostic_weak_noisy_silver_manifest_summary.json",
)
AGENTIC_V3_6_3_MANIFEST_ALL_JSONL = report_artifact_path(
    AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID,
    "diagnostic_weak_noisy_silver_manifest_all.jsonl",
)
AGENTIC_V3_6_3_MANIFEST_CORE_JSONL = report_artifact_path(
    AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID,
    "diagnostic_weak_noisy_silver_manifest_core.jsonl",
)
AGENTIC_V3_6_3_MANIFEST_REVIEW_ONLY_JSONL = report_artifact_path(
    AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID,
    "diagnostic_weak_noisy_silver_manifest_review_only.jsonl",
)
AGENTIC_V3_6_3_MANIFEST_QUARANTINE_JSONL = report_artifact_path(
    AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID,
    "diagnostic_weak_noisy_silver_manifest_quarantine.jsonl",
)
AGENTIC_V3_6_3_MANIFEST_POLICY_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID,
    "diagnostic_weak_noisy_silver_manifest_policy_audit.json",
)
AGENTIC_V3_6_3_NEXT_PHASE_RECOMMENDATION_JSON = report_artifact_path(
    AGENTIC_V3_6_3_DIAGNOSTIC_WEAK_NOISY_SILVER_MANIFEST_FREEZE_RUN_ID,
    "diagnostic_weak_noisy_silver_manifest_next_phase_recommendation.json",
)
AGENTIC_V3_6_4_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID,
    "summary.json",
)
AGENTIC_V3_6_4_PER_ROW_JSONL = report_artifact_path(
    AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID,
    "per_row.jsonl",
)
AGENTIC_V3_6_4_AGGREGATE_BY_BUCKET_JSON = report_artifact_path(
    AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID,
    "aggregate_by_bucket.json",
)
AGENTIC_V3_6_4_FAILURE_TAXONOMY_JSON = report_artifact_path(
    AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID,
    "failure_taxonomy.json",
)
AGENTIC_V3_6_4_SAMPLE_REVIEW_JSONL = report_artifact_path(
    AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID,
    "sample_review.jsonl",
)
AGENTIC_V3_6_4_POLICY_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID,
    "policy_audit.json",
)
AGENTIC_V3_6_4_NEXT_PHASE_RECOMMENDATION_JSON = report_artifact_path(
    AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID,
    "next_phase_recommendation.json",
)
AGENTIC_V3_6_5_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_6_5_PER_ROW_JSONL = report_artifact_path(
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    "per_row.jsonl",
)
AGENTIC_V3_6_5_BLOCKER_MATRIX_JSON = report_artifact_path(
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    "blocker_matrix.json",
)
AGENTIC_V3_6_5_RUNTIME_SURFACE_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    "runtime_surface_audit.json",
)
AGENTIC_V3_6_5_REFERENCE_SURFACE_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    "reference_surface_audit.json",
)
AGENTIC_V3_6_5_DB_SURFACE_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    "db_surface_audit.json",
)
AGENTIC_V3_6_5_LOCAL_LLM_SURFACE_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    "local_llm_surface_audit.json",
)
AGENTIC_V3_6_5_POLICY_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    "policy_audit.json",
)
AGENTIC_V3_6_5_NEXT_PHASE_RECOMMENDATION_JSON = report_artifact_path(
    AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID,
    "next_phase_recommendation.json",
)
AGENTIC_V3_6_6_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_6_6_REFERENCE_SIDECAR_JSONL = report_artifact_path(
    AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID,
    "reference_sidecar.jsonl",
)
AGENTIC_V3_6_6_CORE_SMOKE_SAMPLE_JSONL = report_artifact_path(
    AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID,
    "core_smoke_sample.jsonl",
)
AGENTIC_V3_6_6_RUNTIME_PROBE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID,
    "runtime_probe_summary.json",
)
AGENTIC_V3_6_6_DB_RETRIEVAL_SURFACE_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID,
    "db_retrieval_surface_audit.json",
)
AGENTIC_V3_6_6_POLICY_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID,
    "policy_audit.json",
)
AGENTIC_V3_6_6_NEXT_PHASE_RECOMMENDATION_JSON = report_artifact_path(
    AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID,
    "next_phase_recommendation.json",
)
AGENTIC_V3_6_7_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID,
    "summary.json",
)
AGENTIC_V3_6_7_RUNTIME_ATTEMPTS_JSONL = report_artifact_path(
    AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID,
    "runtime_attempts.jsonl",
)
AGENTIC_V3_6_7_RUNTIME_STABILITY_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID,
    "runtime_stability_summary.json",
)
AGENTIC_V3_6_7_POLICY_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID,
    "policy_audit.json",
)
AGENTIC_V3_6_7_NEXT_PHASE_RECOMMENDATION_JSON = report_artifact_path(
    AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID,
    "next_phase_recommendation.json",
)
AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID,
    "summary.json",
)
AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SOURCE_INVENTORY_JSON = report_artifact_path(
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID,
    "source_inventory.json",
)
AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_BUILD_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID,
    "index_build_summary.json",
)
AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_PAYLOAD_CONTRACT_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID,
    "payload_contract_summary.json",
)
AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_RETRIEVAL_SMOKE_DIAGNOSTICS_JSONL = report_artifact_path(
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID,
    "retrieval_smoke_diagnostics.jsonl",
)
AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_FAILURE_BUCKETS_JSON = report_artifact_path(
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID,
    "failure_buckets.json",
)
AGENTIC_V3_6_8_SOURCE_REGISTRY_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID,
    "summary.json",
)
AGENTIC_V3_6_8_SOURCE_REGISTRY_SOURCE_OBJECT_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID,
    "source_object_audit.json",
)
AGENTIC_V3_6_8_SOURCE_REGISTRY_SEARCHUNIT_ROLE_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID,
    "searchunit_role_audit.json",
)
AGENTIC_V3_6_8_SOURCE_REGISTRY_EVIDENCE_BUNDLE_CONTRACT_JSON = report_artifact_path(
    AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID,
    "evidence_bundle_contract.json",
)
AGENTIC_V3_6_8_SOURCE_REGISTRY_TRACK_ROUTING_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID,
    "track_routing_audit.json",
)
AGENTIC_V3_6_8_SOURCE_REGISTRY_FAILURE_BUCKETS_JSON = report_artifact_path(
    AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID,
    "failure_buckets.json",
)
AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID,
    "summary.json",
)
AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_CONTRACT_REFACTOR_JSON = report_artifact_path(
    AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID,
    "contract_refactor.json",
)
AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_ADAPTER_DIAGNOSTICS_JSON = report_artifact_path(
    AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID,
    "search_view_adapter_diagnostics.json",
)
AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_HYDRATION_SMOKE_JSON = report_artifact_path(
    AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID,
    "source_atom_hydration_smoke.json",
)
AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_FAILURE_BUCKETS_JSON = report_artifact_path(
    AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID,
    "failure_buckets.json",
)
AGENTIC_V3_7_0_SOURCE_REGISTRY_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID,
    "summary.json",
)
AGENTIC_V3_7_0_SOURCE_REGISTRY_SOURCE_INVENTORY_JSON = report_artifact_path(
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID,
    "source_inventory.json",
)
AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_DIAGNOSTICS_JSONL = report_artifact_path(
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID,
    "materialization_diagnostics.jsonl",
)
AGENTIC_V3_7_0_SOURCE_REGISTRY_HYDRATION_SMOKE_JSON = report_artifact_path(
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID,
    "hydration_smoke.json",
)
AGENTIC_V3_7_0_SOURCE_REGISTRY_FAILURE_BUCKETS_JSON = report_artifact_path(
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_RUN_ID,
    "failure_buckets.json",
)
AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID,
    "summary.json",
)
AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_SOURCE_INVENTORY_JSON = report_artifact_path(
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID,
    "source_inventory.json",
)
AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_INDEX_BUILD_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID,
    "index_build_summary.json",
)
AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_HYDRATION_SMOKE_JSON = report_artifact_path(
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID,
    "hydration_smoke.json",
)
AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_FAILURE_BUCKETS_JSON = report_artifact_path(
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILD_RUN_ID,
    "failure_buckets.json",
)
AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID,
    "summary.json",
)
AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_CANDIDATES_JSONL = report_artifact_path(
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID,
    "llm_natural_silver_candidates.jsonl",
)
AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_ALL_JSONL = report_artifact_path(
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID,
    "llm_natural_silver_manifest_all.jsonl",
)
AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_CORE_JSONL = report_artifact_path(
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID,
    "llm_natural_silver_manifest_core.jsonl",
)
AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_REVIEW_JSONL = report_artifact_path(
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID,
    "llm_natural_silver_manifest_review_only.jsonl",
)
AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_QUARANTINE_JSONL = report_artifact_path(
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_RUN_ID,
    "llm_natural_silver_manifest_quarantine.jsonl",
)
AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS_JSONL = report_artifact_path(
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID,
    "topk_rows.jsonl",
)
AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_FAILURE_BUCKETS_JSON = report_artifact_path(
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID,
    "failure_buckets.json",
)
AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_PER_TRACK_JSON = report_artifact_path(
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID,
    "per_track_breakdown.json",
)
AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SILVER_OVERLAY_JSON = report_artifact_path(
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID,
    "silver_1000_diagnostic_overlay.json",
)
AGENTIC_V3_8_FILE_GROUNDED_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID,
    "summary.json",
)
AGENTIC_V3_8_FILE_GROUNDED_METRICS_JSON = report_artifact_path(
    AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID,
    "metrics.json",
)
AGENTIC_V3_8_FILE_GROUNDED_PER_QUERY_JSONL = report_artifact_path(
    AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID,
    "per_query.jsonl",
)
AGENTIC_V3_8_FILE_GROUNDED_PER_FAMILY_JSON = report_artifact_path(
    AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID,
    "per_family.json",
)
AGENTIC_V3_8_1_EVIDENCE_SELECTOR_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID,
    "summary.json",
)
AGENTIC_V3_8_1_EVIDENCE_SELECTOR_METRICS_JSON = report_artifact_path(
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID,
    "metrics.json",
)
AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_QUERY_JSONL = report_artifact_path(
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID,
    "per_query.jsonl",
)
AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_FAMILY_JSON = report_artifact_path(
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID,
    "per_family.json",
)
AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_METRICS_JSON = report_artifact_path(
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID,
    "metrics.json",
)
AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_QUERY_JSONL = report_artifact_path(
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID,
    "per_query.jsonl",
)
AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_FAMILY_JSON = report_artifact_path(
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID,
    "per_family.json",
)
AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_METRICS_JSON = report_artifact_path(
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID,
    "metrics.json",
)
AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_QUERY_JSONL = report_artifact_path(
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID,
    "per_query.jsonl",
)
AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSON = report_artifact_path(
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID,
    "per_family.json",
)
AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSONL = report_artifact_path(
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID,
    "per_family.jsonl",
)


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


AGENTIC_INDEX_DIR = ROOT / "ai" / "eval" / "indexes" / "rag-data"
EXPLICIT_GENERATED_REPORT_MARKDOWN_FILENAMES: set[str] = set()
CURRENT_REPORT_PATHS = {
    REPORT_DIR / "baseline_v1.json",
    REPORT_DIR / "scorer_v1.jsonl",
    REPORT_DIR / "metric_input_v1.json",
    REPORT_DIR / "smoke_v1.json",
    REPORT_DIR / "gold_overrides.csv",
    REPORT_DIR / "gold_overrides.jsonl",
    REPORT_DIR / "gold_overrides_summary.json",
    REPORT_DIR / "xlsx_candidate_v1.jsonl",
    REPORT_DIR / "pdf_candidate_v1.jsonl",
    REPORT_DIR / "source_bound_readiness_v1.json",
    REPORT_DIR / "status.jsonl",
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ATTRIBUTION_JSON,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_AUDIT_JSONL,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ANSWER_SPAN_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_CONTEXT_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_REMAINING_TRIAGE_JSON,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_INVENTORY_JSONL,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_REMAINING_JSON,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_DECISION_PACKET_JSON,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SILVER_AUDIT_JSON,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_SUMMARY_JSON,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_HUMAN_REVIEW_JSON,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_DECISION_MATRIX_JSONL,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_REMAINING_JSON,
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_SUMMARY_JSON,
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_APPLIED_JSONL,
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_DIFF_JSONL,
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RESCORED_JSONL,
    AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_REMAINING_JSON,
    AGENTIC_V3_2_0_RESULTS,
    AGENTIC_V3_2_0_SUMMARY_JSON,
    AGENTIC_V3_2_0_ATTRIBUTION_JSON,
    AGENTIC_V3_2_0_AUDIT_JSONL,
    AGENTIC_V3_2_0_QUEUE_JSON,
    AGENTIC_V3_2_1_SUMMARY_JSON,
    AGENTIC_V3_2_1_RESIDUAL_TRIAGE_JSONL,
    AGENTIC_V3_2_2_RESULTS,
    AGENTIC_V3_2_2_SUMMARY_JSON,
    AGENTIC_V3_2_2_ATTRIBUTION_JSON,
    AGENTIC_V3_2_2_AUDIT_JSONL,
    AGENTIC_V3_2_2_QUEUE_JSON,
    AGENTIC_V3_2_3_SUMMARY_JSON,
    AGENTIC_V3_2_3_DIAGNOSTICS_JSONL,
    AGENTIC_V3_2_3_QUEUE_JSON,
    AGENTIC_V3_2_4_SUMMARY_JSON,
    AGENTIC_V3_2_4_DIAGNOSTICS_JSONL,
    AGENTIC_V3_2_4_QUEUE_JSON,
    AGENTIC_V3_2_5_RESULTS,
    AGENTIC_V3_2_5_SUMMARY_JSON,
    AGENTIC_V3_2_5_ATTRIBUTION_JSON,
    AGENTIC_V3_2_5_AUDIT_JSONL,
    AGENTIC_V3_2_5_PDF_CONTEXT_DIAGNOSTICS_JSONL,
    AGENTIC_V3_2_5_QUEUE_JSON,
    AGENTIC_V3_2_6_RESULTS,
    AGENTIC_V3_2_6_SUMMARY_JSON,
    AGENTIC_V3_2_6_ATTRIBUTION_JSON,
    AGENTIC_V3_2_6_AUDIT_JSONL,
    AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_DIAGNOSTICS_JSONL,
    AGENTIC_V3_2_6_QUEUE_JSON,
    AGENTIC_V3_3_3_SILVER_SOURCE_CANDIDATE_DISCOVERY_INVENTORY_JSON,
    AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_JSON,
    AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_QRELS_SCHEMA_JSON,
    AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_JSONL,
    AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_CSV,
    AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_SUMMARY_JSON,
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_POLICY_APPROVAL_JSON,
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_QUERY_GROUP_REVIEW_CSV,
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_AMBIGUOUS_CANDIDATE_REVIEW_CSV,
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_AUTO_LABEL_PLAN_JSON,
    AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_MINIMAL_REVIEW_SUMMARY_JSON,
    AGENTIC_V3_4_2_OFFICIAL_RETRIEVAL_QRELS_JSONL,
    AGENTIC_V3_4_2_QRELS_COVERAGE_SUMMARY_JSON,
    AGENTIC_V3_4_2_QRELS_EXCLUSION_LEDGER_JSONL,
    AGENTIC_V3_4_3_RETRIEVAL_SMOKE_METRICS_JSON,
    AGENTIC_V3_4_3_RETRIEVAL_SMOKE_PER_QUERY_JSONL,
    AGENTIC_V3_4_4_README_METRIC_CARD_JSON,
    AGENTIC_V3_4_4_README_SECTION_MD,
    AGENTIC_V3_4_4_SILVER_READINESS_SUMMARY_JSON,
    AGENTIC_V3_5_0_CAPACITY_SUMMARY_JSON,
    AGENTIC_V3_5_0_MANIFEST_READY_CANDIDATES_JSONL,
    AGENTIC_V3_5_0_BLOCKED_OR_CONVERTIBLE_CANDIDATES_JSONL,
    AGENTIC_V3_5_0_ACQUISITION_PLAN_JSON,
    AGENTIC_V3_5_1_PILOT_SOURCE_MANIFEST_JSONL,
    AGENTIC_V3_5_1_FREEZE_SUMMARY_JSON,
    AGENTIC_V3_5_1_FREEZE_AUDIT_JSONL,
    AGENTIC_V3_5_1_SELECTION_RATIONALE_JSON,
    AGENTIC_V3_5_2_XLSX_SOURCE_VALUE_MANIFEST_JSONL,
    AGENTIC_V3_5_2_XLSX_REPAIR_SUMMARY_JSON,
    AGENTIC_V3_5_2_XLSX_REPAIR_AUDIT_JSONL,
    AGENTIC_V3_5_2_XLSX_ACQUISITION_PLAN_JSON,
    AGENTIC_V3_5_3_PDF_SOURCE_TEXT_MANIFEST_JSONL,
    AGENTIC_V3_5_3_PDF_REPAIR_SUMMARY_JSON,
    AGENTIC_V3_5_3_PDF_REPAIR_AUDIT_JSONL,
    AGENTIC_V3_5_3_PDF_ACQUISITION_PLAN_JSON,
    AGENTIC_V3_5_3_BALANCED_CAPACITY_SUMMARY_JSON,
    AGENTIC_V3_5_4_BALANCED_SOURCE_MANIFEST_JSONL,
    AGENTIC_V3_5_4_FREEZE_SUMMARY_JSON,
    AGENTIC_V3_5_4_FREEZE_AUDIT_JSONL,
    AGENTIC_V3_5_4_AUDIT_SAMPLE_PACKET_JSONL,
    AGENTIC_V3_5_4_NEXT_PHASE_POLICY_BOUNDARY_JSON,
    AGENTIC_V3_5_5_QUALITY_SUMMARY_JSON,
    AGENTIC_V3_5_5_MANIFEST_VALIDATION_JSONL,
    AGENTIC_V3_5_5_AUDIT_SAMPLE_REVIEW_PACKET_JSONL,
    AGENTIC_V3_5_5_DUPLICATE_HASH_AUDIT_JSONL,
    AGENTIC_V3_5_5_RECOMMENDED_REPAIR_QUEUE_JSONL,
    AGENTIC_V3_5_5_NEXT_PHASE_POLICY_BOUNDARY_JSON,
    AGENTIC_V3_6_0_POLICY_APPROVAL_SUMMARY_JSON,
    AGENTIC_V3_6_0_GENERATION_CONTRACT_JSON,
    AGENTIC_V3_6_0_USER_DECISION_MATRIX_JSONL,
    AGENTIC_V3_6_0_GUARDRAIL_SUMMARY_JSON,
    AGENTIC_V3_6_1_WEAK_SILVER_CANDIDATES_JSONL,
    AGENTIC_V3_6_1_GENERATION_SUMMARY_JSON,
    AGENTIC_V3_6_1_SPLIT_MANIFEST_JSON,
    AGENTIC_V3_6_1_QUALITY_DISTRIBUTION_JSON,
    AGENTIC_V3_6_1_BLOCKED_ROWS_JSONL,
    AGENTIC_V3_6_1_POLICY_COMPLIANCE_AUDIT_JSON,
    AGENTIC_V3_6_1_NEXT_PHASE_RECOMMENDATION_JSON,
    AGENTIC_V3_6_2_CANDIDATE_SANITY_SUMMARY_JSON,
    AGENTIC_V3_6_2_CANDIDATE_SANITY_PER_ROW_JSONL,
    AGENTIC_V3_6_2_CANDIDATE_QUARANTINE_ROWS_JSONL,
    AGENTIC_V3_6_2_CANDIDATE_METRIC_FEASIBILITY_JSON,
    AGENTIC_V3_6_2_SPLIT_INDEPENDENCE_AUDIT_JSON,
    AGENTIC_V3_6_2_HASH_CONTRACT_AUDIT_JSON,
    AGENTIC_V3_6_2_NEXT_PHASE_RECOMMENDATION_JSON,
    AGENTIC_V3_6_3_MANIFEST_SUMMARY_JSON,
    AGENTIC_V3_6_3_MANIFEST_ALL_JSONL,
    AGENTIC_V3_6_3_MANIFEST_CORE_JSONL,
    AGENTIC_V3_6_3_MANIFEST_REVIEW_ONLY_JSONL,
    AGENTIC_V3_6_3_MANIFEST_QUARANTINE_JSONL,
    AGENTIC_V3_6_3_MANIFEST_POLICY_AUDIT_JSON,
    AGENTIC_V3_6_3_NEXT_PHASE_RECOMMENDATION_JSON,
    AGENTIC_V3_6_4_SUMMARY_JSON,
    AGENTIC_V3_6_4_PER_ROW_JSONL,
    AGENTIC_V3_6_4_AGGREGATE_BY_BUCKET_JSON,
    AGENTIC_V3_6_4_FAILURE_TAXONOMY_JSON,
    AGENTIC_V3_6_4_SAMPLE_REVIEW_JSONL,
    AGENTIC_V3_6_4_POLICY_AUDIT_JSON,
    AGENTIC_V3_6_4_NEXT_PHASE_RECOMMENDATION_JSON,
    AGENTIC_V3_6_5_SUMMARY_JSON,
    AGENTIC_V3_6_5_PER_ROW_JSONL,
    AGENTIC_V3_6_5_BLOCKER_MATRIX_JSON,
    AGENTIC_V3_6_5_RUNTIME_SURFACE_AUDIT_JSON,
    AGENTIC_V3_6_5_REFERENCE_SURFACE_AUDIT_JSON,
    AGENTIC_V3_6_5_DB_SURFACE_AUDIT_JSON,
    AGENTIC_V3_6_5_LOCAL_LLM_SURFACE_AUDIT_JSON,
    AGENTIC_V3_6_5_POLICY_AUDIT_JSON,
    AGENTIC_V3_6_5_NEXT_PHASE_RECOMMENDATION_JSON,
    AGENTIC_V3_6_6_SUMMARY_JSON,
    AGENTIC_V3_6_6_REFERENCE_SIDECAR_JSONL,
    AGENTIC_V3_6_6_CORE_SMOKE_SAMPLE_JSONL,
    AGENTIC_V3_6_6_RUNTIME_PROBE_SUMMARY_JSON,
    AGENTIC_V3_6_6_DB_RETRIEVAL_SURFACE_AUDIT_JSON,
    AGENTIC_V3_6_6_POLICY_AUDIT_JSON,
    AGENTIC_V3_6_6_NEXT_PHASE_RECOMMENDATION_JSON,
    AGENTIC_V3_6_7_SUMMARY_JSON,
    AGENTIC_V3_6_7_RUNTIME_ATTEMPTS_JSONL,
    AGENTIC_V3_6_7_RUNTIME_STABILITY_SUMMARY_JSON,
    AGENTIC_V3_6_7_POLICY_AUDIT_JSON,
    AGENTIC_V3_6_7_NEXT_PHASE_RECOMMENDATION_JSON,
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SUMMARY_JSON,
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SOURCE_INVENTORY_JSON,
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_BUILD_SUMMARY_JSON,
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_PAYLOAD_CONTRACT_SUMMARY_JSON,
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_RETRIEVAL_SMOKE_DIAGNOSTICS_JSONL,
    AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_6_8_SOURCE_REGISTRY_SUMMARY_JSON,
    AGENTIC_V3_6_8_SOURCE_REGISTRY_SOURCE_OBJECT_AUDIT_JSON,
    AGENTIC_V3_6_8_SOURCE_REGISTRY_SEARCHUNIT_ROLE_AUDIT_JSON,
    AGENTIC_V3_6_8_SOURCE_REGISTRY_EVIDENCE_BUNDLE_CONTRACT_JSON,
    AGENTIC_V3_6_8_SOURCE_REGISTRY_TRACK_ROUTING_AUDIT_JSON,
    AGENTIC_V3_6_8_SOURCE_REGISTRY_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_SUMMARY_JSON,
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_CONTRACT_REFACTOR_JSON,
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_ADAPTER_DIAGNOSTICS_JSON,
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_HYDRATION_SMOKE_JSON,
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_SUMMARY_JSON,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_SOURCE_INVENTORY_JSON,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_DIAGNOSTICS_JSONL,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_HYDRATION_SMOKE_JSON,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_SUMMARY_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_SOURCE_INVENTORY_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_INDEX_BUILD_SUMMARY_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_HYDRATION_SMOKE_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_SUMMARY_JSON,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_CANDIDATES_JSONL,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_ALL_JSONL,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_CORE_JSONL,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_REVIEW_JSONL,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_QUARANTINE_JSONL,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY_JSON,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS_JSONL,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_PER_TRACK_JSON,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SILVER_OVERLAY_JSON,
    AGENTIC_V3_8_FILE_GROUNDED_SUMMARY_JSON,
    AGENTIC_V3_8_FILE_GROUNDED_METRICS_JSON,
    AGENTIC_V3_8_FILE_GROUNDED_PER_QUERY_JSONL,
    AGENTIC_V3_8_FILE_GROUNDED_PER_FAMILY_JSON,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_SUMMARY_JSON,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_METRICS_JSON,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_QUERY_JSONL,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_FAMILY_JSON,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_SUMMARY_JSON,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_METRICS_JSON,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_QUERY_JSONL,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_FAMILY_JSON,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_SUMMARY_JSON,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_METRICS_JSON,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_QUERY_JSONL,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSON,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSONL,
}
PRE_ARCHIVE_LAYOUT_CURRENT_REPORT_PATHS = CURRENT_REPORT_PATHS
ARCHIVED_REPORT_PATHS = {
    AGENTIC_RESULTS,
    AGENTIC_SUMMARY_JSON,
    AGENTIC_ATTRIBUTION_JSON,
    AGENTIC_V2_RESULTS,
    AGENTIC_V2_SUMMARY_JSON,
    AGENTIC_V2_ATTRIBUTION_JSON,
    AGENTIC_V2_1_RESULTS,
    AGENTIC_V2_1_SUMMARY_JSON,
    AGENTIC_V2_1_ATTRIBUTION_JSON,
    AGENTIC_V2_2_RESULTS,
    AGENTIC_V2_2_SUMMARY_JSON,
    AGENTIC_V2_2_ATTRIBUTION_JSON,
    AGENTIC_V3_RESULTS,
    AGENTIC_V3_SUMMARY_JSON,
    AGENTIC_V3_ATTRIBUTION_JSON,
    AGENTIC_V3_1_RESULTS,
    AGENTIC_V3_1_SUMMARY_JSON,
    AGENTIC_V3_1_ATTRIBUTION_JSON,
    AGENTIC_V3_1_AUDIT_JSONL,
    AGENTIC_V3_1_TRIAGE_JSON,
    AGENTIC_V3_1_PRIORITY_RESULTS,
    AGENTIC_V3_1_PRIORITY_SUMMARY_JSON,
    AGENTIC_V3_1_PRIORITY_ATTRIBUTION_JSON,
    AGENTIC_V3_1_PRIORITY_AUDIT_JSONL,
    AGENTIC_V3_1_PRIORITY_TRIAGE_DELTA_JSON,
    AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_JSON,
    AGENTIC_V3_1_TEXT_LOCATOR_RESULTS,
    AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_JSON,
    AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_MD,
    AGENTIC_V3_1_TEXT_LOCATOR_ATTRIBUTION_JSON,
    AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_JSON,
    AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_MD,
    AGENTIC_V3_1_1_POST_RESULTS,
    AGENTIC_V3_1_1_POST_SUMMARY_JSON,
    AGENTIC_V3_1_1_POST_SUMMARY_MD,
    AGENTIC_V3_1_1_POST_ATTRIBUTION_JSON,
    AGENTIC_V3_1_1_POST_AUDIT_JSONL,
    AGENTIC_V3_1_1_POST_TRIAGE_QUEUE_JSON,
    AGENTIC_V3_1_2_ANSWER_SPAN_RESULTS,
    AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_JSON,
    AGENTIC_V3_1_2_ANSWER_SPAN_ATTRIBUTION_JSON,
    AGENTIC_V3_1_2_ANSWER_SPAN_AUDIT_JSONL,
    AGENTIC_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_2_ANSWER_SPAN_REMAINING_TRIAGE_JSON,
    AGENTIC_V3_1_3_REMAINING_QUEUE_RESULTS,
    AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_JSON,
    AGENTIC_V3_1_3_REMAINING_QUEUE_ATTRIBUTION_JSON,
    AGENTIC_V3_1_3_REMAINING_QUEUE_AUDIT_JSONL,
    AGENTIC_V3_1_3_REMAINING_QUEUE_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_3_REMAINING_QUEUE_REMAINING_TRIAGE_JSON,
    AGENTIC_V3_1_4_PDF_RESIDUAL_RESULTS,
    AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON,
    AGENTIC_V3_1_4_PDF_RESIDUAL_ATTRIBUTION_JSON,
    AGENTIC_V3_1_4_PDF_RESIDUAL_AUDIT_JSONL,
    AGENTIC_V3_1_4_PDF_RESIDUAL_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_4_PDF_RESIDUAL_REMAINING_TRIAGE_JSON,
    AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_SUMMARY_JSON,
    AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_TRIAGE_JSON,
}
CURRENT_REPORT_PATHS = {
    REPORT_DIR / "status.jsonl",
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_SUMMARY_JSON,
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_CONTRACT_REFACTOR_JSON,
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_ADAPTER_DIAGNOSTICS_JSON,
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_HYDRATION_SMOKE_JSON,
    AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_SUMMARY_JSON,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_SOURCE_INVENTORY_JSON,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_DIAGNOSTICS_JSONL,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_HYDRATION_SMOKE_JSON,
    AGENTIC_V3_7_0_SOURCE_REGISTRY_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_SUMMARY_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_SOURCE_INVENTORY_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_INDEX_BUILD_SUMMARY_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_HYDRATION_SMOKE_JSON,
    AGENTIC_V3_7_1_ALL_SOURCE_CITABLE_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_SUMMARY_JSON,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_CANDIDATES_JSONL,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_ALL_JSONL,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_CORE_JSONL,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_REVIEW_JSONL,
    AGENTIC_V3_7_2_LOCAL_LLM_NATURAL_SILVER_QUERY_REGEN_MANIFEST_QUARANTINE_JSONL,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY_JSON,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS_JSONL,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_FAILURE_BUCKETS_JSON,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_PER_TRACK_JSON,
    AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SILVER_OVERLAY_JSON,
    AGENTIC_V3_8_FILE_GROUNDED_SUMMARY_JSON,
    AGENTIC_V3_8_FILE_GROUNDED_METRICS_JSON,
    AGENTIC_V3_8_FILE_GROUNDED_PER_QUERY_JSONL,
    AGENTIC_V3_8_FILE_GROUNDED_PER_FAMILY_JSON,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_SUMMARY_JSON,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_METRICS_JSON,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_QUERY_JSONL,
    AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_FAMILY_JSON,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_SUMMARY_JSON,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_METRICS_JSON,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_QUERY_JSONL,
    AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_FAMILY_JSON,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_SUMMARY_JSON,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_METRICS_JSON,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_QUERY_JSONL,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSON,
    AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSONL,
}
ARCHIVED_REPORT_PATHS = (
    ARCHIVED_REPORT_PATHS | (PRE_ARCHIVE_LAYOUT_CURRENT_REPORT_PATHS - CURRENT_REPORT_PATHS)
) - CURRENT_REPORT_PATHS
REGISTERED_REPORT_PATHS = CURRENT_REPORT_PATHS | ARCHIVED_REPORT_PATHS
CURRENT_REPORT_FILENAMES = {path.name for path in CURRENT_REPORT_PATHS}
ARCHIVED_REPORT_FILENAMES = {path.name for path in ARCHIVED_REPORT_PATHS}
ALL_REPORT_FILENAMES = CURRENT_REPORT_FILENAMES | ARCHIVED_REPORT_FILENAMES


ALLOWED_AGENTIC_ATTRIBUTION_CATEGORIES = {
    "CORPUS_COVERAGE_MISS",
    "RETRIEVAL_MISS",
    "CITATION_PAYLOAD_MISSING",
    "CITATION_LOCATOR_INCOMPATIBLE",
    "ANSWER_GENERATION_NOOP_LIMITATION",
    "STRUCTURED_ADAPTER_NOT_WIRED",
    "SCORER_COMPATIBILITY_MISMATCH",
    "REAL_MODEL_OR_RETRIEVAL_QUALITY_FAILURE",
    "UNKNOWN_NEEDS_INSPECTION",
}
ALLOWED_V2_ATTRIBUTION_CATEGORIES = {
    "PASS",
    "RETRIEVAL_MISS",
    "CITATION_PAYLOAD_SCHEMA_MISMATCH",
    "ADAPTER_FAILURE",
    "ANSWER_SYNTHESIS_LIMITATION",
    "SCORER_COMPATIBILITY_MISMATCH",
    "SOURCE_BOUND_MANIFEST_MISMATCH",
}
def test_source_of_truth_audit_reports_current_scored_baseline() -> None:
    first_run = read_json(REPORT_DIR / "baseline_v1.json")
    measurement_doc = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    scorer_rows = read_jsonl(REPORT_DIR / "scorer_v1.jsonl")
    xlsx_rows = read_jsonl(REPORT_DIR / "xlsx_candidate_v1.jsonl")
    pdf_rows = read_jsonl(REPORT_DIR / "pdf_candidate_v1.jsonl")
    smoke = read_json(REPORT_DIR / "smoke_v1.json")

    assert first_run["official_scoring_attempt_count"] == 29
    assert first_run["scored_count"] == 29
    assert first_run["official_metric_execution_started"] is True
    assert first_run["execution_blocker_category"] is None
    assert first_run["primary_failure_category"] == "CITATION_UNSUPPORTED"
    assert first_run["status_detail"] == "SCORED_BASELINE_PARTIAL"
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }
    assert "SCORER_BACKEND_UNAVAILABLE" not in json.dumps(first_run, ensure_ascii=False)
    assert "SCORER_BACKEND_UNAVAILABLE" not in measurement_doc
    assert "official_answer_citation_metric_first_run_v1" in measurement_doc
    assert "PASS `8/29`" in measurement_doc

    assert len(scorer_rows) == 29
    assert len({row["query_id"] for row in scorer_rows}) == 29
    first_run_rows_by_id = {row["query_id"]: row for row in first_run["row_results"]}
    mismatches = [
        row["query_id"]
        for row in scorer_rows
        if first_run_rows_by_id[row["query_id"]]["failure_category"] != row["failure_category"]
    ]
    assert mismatches == []

    assert len(xlsx_rows) == 29
    assert len({row["query_id"] for row in xlsx_rows}) == 29
    assert Counter(row["failure_category"] for row in xlsx_rows) == Counter({"PASS": 26, "PARTIAL_OR_UNSUPPORTED": 3})
    assert sum(
        1
        for row in xlsx_rows
        if row["track"] == "xlsx_business_structured" and row["failure_category"] == "PASS"
    ) == 19
    assert [
        row["query_id"]
        for row in xlsx_rows
        if row["track"] == "pdf_business_ocr_mm" and row["failure_category"] != "PASS"
    ] == ["gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001"]

    assert len(pdf_rows) == 29
    assert len({row["query_id"] for row in pdf_rows}) == 29
    assert Counter(row["failure_category"] for row in pdf_rows) == Counter({"PASS": 29})
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = next(row for row in pdf_rows if row["query_id"] == query_id)
        score_details = row.get("score_details", {})
        locator = row["generated_citations"][0]["citation_locator"]
        assert score_details["deterministic_verification_passed"] is True
        assert score_details["expected_answer_used_for_generation"] is False
        assert score_details["supporting_evidence_used_for_generation"] is False
        assert score_details["gold_fields_used_for_generation"] is False
        assert score_details["source_text_contains_answer_value"] is True
        assert score_details["source_row_contains_target_value"] is True
        assert score_details["source_bound_identity_verified"] is True
        assert score_details["locator_compatibility"] == ["OFFICIAL_COMPATIBLE_LOCATOR"]
        assert locator["file"]
        assert locator["page"]
        assert locator["physical_page_index"] >= 0
        assert locator["bbox"] and len(locator["bbox"]) == 4
        assert locator["search_unit_id"]
        assert locator["document_version_id"]
        assert locator["source_basis"]
        assert locator["source_pdf_path"]
        assert locator["row_label"]
        assert locator["target_column"]
        assert locator["region_type"] in {"paragraph", "table_body"}
        assert locator["region_type"] != "table_row"
        if locator["region_type"] == "table_body":
            assert locator["bbox_granularity"] == "row_only"

    assert smoke["official_metric_execution_started"] is False
    assert smoke["status"] == "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS_WITH_DIAGNOSTIC_WARNINGS"

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_progress = progress.split("## Short History", 1)[0]
    assert "SCORER_BACKEND_UNAVAILABLE" not in current_progress
    assert "official_denominator_source_bound_index_build_ready_load_checked" in current_progress
    assert "PDF table/value candidate now has official-compatible source-bound locators" in current_progress
    assert "official_answer_citation_agentic_loop_run_v1" in current_progress
    assert "promotion_evidence=false" in current_progress
    assert "faiss_gpu_used=true" in current_progress
    assert "baseline_comparison_is_model_quality_comparable=false" in current_progress
    assert "Human-facing rolling docs" in current_progress
    assert "Per-run Markdown" in current_progress
    assert "BUILD_READY_LOAD_CHECK_PASSED" in current_progress
    assert "rerun_allowed=true" in current_progress


def test_v3_6_2_sanity_hash_contract_is_registered_and_matches_artifacts() -> None:
    summary = read_json(AGENTIC_V3_6_2_CANDIDATE_SANITY_SUMMARY_JSON)
    hash_audit = read_json(AGENTIC_V3_6_2_HASH_CONTRACT_AUDIT_JSON)
    expected_artifacts = {
        "candidate_sanity_per_row_jsonl_sha256": AGENTIC_V3_6_2_CANDIDATE_SANITY_PER_ROW_JSONL,
        "candidate_quarantine_rows_jsonl_sha256": AGENTIC_V3_6_2_CANDIDATE_QUARANTINE_ROWS_JSONL,
        "candidate_metric_feasibility_json_sha256": AGENTIC_V3_6_2_CANDIDATE_METRIC_FEASIBILITY_JSON,
        "split_independence_audit_json_sha256": AGENTIC_V3_6_2_SPLIT_INDEPENDENCE_AUDIT_JSON,
        "hash_contract_audit_json_sha256": AGENTIC_V3_6_2_HASH_CONTRACT_AUDIT_JSON,
        "next_phase_recommendation_json_sha256": AGENTIC_V3_6_2_NEXT_PHASE_RECOMMENDATION_JSON,
    }

    assert AGENTIC_V3_6_2_CANDIDATE_SANITY_SUMMARY_JSON in REGISTERED_REPORT_PATHS
    assert AGENTIC_V3_6_2_CANDIDATE_SANITY_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= REGISTERED_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert hash_audit["generated_question_hash_contract"] == "normalized_question_sha256_lowercase_whitespace_collapsed"
    assert hash_audit["raw_question_hash_contract"] is False
    assert hash_audit["normalized_question_hash_match_count"] == 1000
    assert hash_audit["candidate_row_count"] == 1000
    assert "source_candidate_rows_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]


def test_v3_6_3_manifest_freeze_artifacts_are_registered_and_hash_locked() -> None:
    summary = read_json(AGENTIC_V3_6_3_MANIFEST_SUMMARY_JSON)
    expected_artifacts = {
        "manifest_all_jsonl_sha256": AGENTIC_V3_6_3_MANIFEST_ALL_JSONL,
        "manifest_core_jsonl_sha256": AGENTIC_V3_6_3_MANIFEST_CORE_JSONL,
        "manifest_review_only_jsonl_sha256": AGENTIC_V3_6_3_MANIFEST_REVIEW_ONLY_JSONL,
        "manifest_quarantine_jsonl_sha256": AGENTIC_V3_6_3_MANIFEST_QUARANTINE_JSONL,
        "manifest_policy_audit_json_sha256": AGENTIC_V3_6_3_MANIFEST_POLICY_AUDIT_JSON,
        "next_phase_recommendation_json_sha256": AGENTIC_V3_6_3_NEXT_PHASE_RECOMMENDATION_JSON,
    }

    assert AGENTIC_V3_6_3_MANIFEST_SUMMARY_JSON in REGISTERED_REPORT_PATHS
    assert AGENTIC_V3_6_3_MANIFEST_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= REGISTERED_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["manifest_freeze_passed"] is True
    assert summary["manifest_row_count"] == 1000
    assert summary["core_manifest_row_count"] == 665
    assert summary["review_only_manifest_row_count"] == 335
    assert summary["quarantine_manifest_row_count"] == 0
    assert "manifest_summary_json_sha256" not in summary["artifact_sha256"]
    assert "source_candidate_rows_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]


def test_v3_6_4_diagnostic_metric_artifacts_are_registered_and_hash_locked() -> None:
    summary = read_json(AGENTIC_V3_6_4_SUMMARY_JSON)
    aggregate = read_json(AGENTIC_V3_6_4_AGGREGATE_BY_BUCKET_JSON)
    policy_audit = read_json(AGENTIC_V3_6_4_POLICY_AUDIT_JSON)
    expected_artifacts = {
        "per_row_jsonl_sha256": AGENTIC_V3_6_4_PER_ROW_JSONL,
        "aggregate_by_bucket_json_sha256": AGENTIC_V3_6_4_AGGREGATE_BY_BUCKET_JSON,
        "failure_taxonomy_json_sha256": AGENTIC_V3_6_4_FAILURE_TAXONOMY_JSON,
        "sample_review_jsonl_sha256": AGENTIC_V3_6_4_SAMPLE_REVIEW_JSONL,
        "policy_audit_json_sha256": AGENTIC_V3_6_4_POLICY_AUDIT_JSON,
        "next_phase_recommendation_json_sha256": AGENTIC_V3_6_4_NEXT_PHASE_RECOMMENDATION_JSON,
    }

    assert AGENTIC_V3_6_4_SUMMARY_JSON in REGISTERED_REPORT_PATHS
    assert AGENTIC_V3_6_4_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= REGISTERED_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID
    assert summary["manifest_row_count"] == 1000
    assert summary["core_manifest_row_count"] == 665
    assert summary["review_only_manifest_row_count"] == 335
    assert summary["quarantine_manifest_row_count"] == 0
    assert summary["runtime_generation_succeeded_row_count"] == 0
    assert summary["runtime_generation_fail_closed_row_count"] == 1000
    assert aggregate["reporting_partitions"]["core_only"]["row_count"] == 665
    assert aggregate["reporting_partitions"]["review_only_challenge"]["row_count"] == 335
    assert aggregate["reporting_partitions"]["all_diagnostic"]["row_count"] == 1000
    assert policy_audit["diagnostic_only"] is True
    assert policy_audit["official_metric"] is False
    assert policy_audit["official_metric_denominator_usage_allowed"] is False
    assert policy_audit["generated_expected_answers_are_gold"] is False
    assert policy_audit["promotion_evidence"] is False
    assert policy_audit["threshold_tuning"] is False
    assert policy_audit["winner_selection"] is False
    assert policy_audit["readme_representative_product_performance_claim"] is False

    for heavy_key in (
        "manifest_rows_all",
        "manifest_rows_core",
        "source_candidate_rows",
        "sanity_rows",
        "per_row_metric_rows",
        "aggregate_by_bucket",
        "failure_taxonomy",
        "sample_review_rows",
        "policy_audit",
        "next_phase_recommendation",
    ):
        assert heavy_key not in summary
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]
    assert "canonical_silver_manifest_json_sha256" not in summary["artifact_sha256"]


def test_v3_6_5_runtime_audit_artifacts_are_registered_hash_locked_and_compact() -> None:
    summary = read_json(AGENTIC_V3_6_5_SUMMARY_JSON)
    expected_artifacts = {
        "per_row_jsonl_sha256": AGENTIC_V3_6_5_PER_ROW_JSONL,
        "blocker_matrix_json_sha256": AGENTIC_V3_6_5_BLOCKER_MATRIX_JSON,
        "runtime_surface_audit_json_sha256": AGENTIC_V3_6_5_RUNTIME_SURFACE_AUDIT_JSON,
        "reference_surface_audit_json_sha256": AGENTIC_V3_6_5_REFERENCE_SURFACE_AUDIT_JSON,
        "db_surface_audit_json_sha256": AGENTIC_V3_6_5_DB_SURFACE_AUDIT_JSON,
        "local_llm_surface_audit_json_sha256": AGENTIC_V3_6_5_LOCAL_LLM_SURFACE_AUDIT_JSON,
        "policy_audit_json_sha256": AGENTIC_V3_6_5_POLICY_AUDIT_JSON,
        "next_phase_recommendation_json_sha256": AGENTIC_V3_6_5_NEXT_PHASE_RECOMMENDATION_JSON,
    }

    assert AGENTIC_V3_6_5_SUMMARY_JSON in REGISTERED_REPORT_PATHS
    assert AGENTIC_V3_6_5_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= REGISTERED_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID
    assert summary["source_metric_run_id"] == AGENTIC_V3_6_4_DIAGNOSTIC_ONLY_WEAK_NOISY_SILVER_METRIC_RUN_ID
    assert summary["local_llm_live_silver_generation_allowed"] is False
    assert summary["local_llm_metric_scoring_allowed"] is False
    assert summary["external_llm_api_allowed"] is False
    assert summary["db_write_allowed"] is False
    assert summary["db_index_rebuild_allowed"] is False
    assert summary["production_db_usage_allowed"] is False
    for heavy_key in (
        "per_row_metric_rows",
        "source_candidate_rows",
        "candidate_sanity_per_row",
        "per_row_triage_rows",
        "blocker_matrix",
        "runtime_surface_audit",
        "reference_surface_audit",
        "db_surface_audit",
        "local_llm_surface_audit",
        "policy_audit",
        "next_phase_recommendation",
        "raw_llm_response",
        "db_snapshot_rows",
        "prompt_payloads",
    ):
        assert heavy_key not in summary
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]
    assert "canonical_silver_manifest_json_sha256" not in summary["artifact_sha256"]


def test_v3_6_6_sidecar_runtime_probe_artifacts_are_registered_hash_locked_and_compact() -> None:
    summary = read_json(AGENTIC_V3_6_6_SUMMARY_JSON)
    expected_artifacts = {
        "reference_sidecar_jsonl_sha256": AGENTIC_V3_6_6_REFERENCE_SIDECAR_JSONL,
        "core_smoke_sample_jsonl_sha256": AGENTIC_V3_6_6_CORE_SMOKE_SAMPLE_JSONL,
        "runtime_probe_summary_json_sha256": AGENTIC_V3_6_6_RUNTIME_PROBE_SUMMARY_JSON,
        "db_retrieval_surface_audit_json_sha256": AGENTIC_V3_6_6_DB_RETRIEVAL_SURFACE_AUDIT_JSON,
        "policy_audit_json_sha256": AGENTIC_V3_6_6_POLICY_AUDIT_JSON,
        "next_phase_recommendation_json_sha256": AGENTIC_V3_6_6_NEXT_PHASE_RECOMMENDATION_JSON,
    }

    assert AGENTIC_V3_6_6_SUMMARY_JSON in REGISTERED_REPORT_PATHS
    assert AGENTIC_V3_6_6_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= REGISTERED_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID
    assert summary["source_triage_run_id"] == AGENTIC_V3_6_5_ROUGH_FAILURE_BUCKET_TRIAGE_RUN_ID
    assert summary["diagnostic_reference_sidecar_complete"] is True
    assert summary["sidecar_row_counts"] == {
        "all_diagnostic": 1000,
        "core_only": 665,
        "quarantine": 0,
        "review_only_challenge": 335,
    }
    assert summary["local_llm_live_silver_generation_allowed"] is False
    assert summary["local_llm_metric_scoring_allowed"] is False
    assert summary["external_llm_api_allowed"] is False
    assert summary["db_write_allowed"] is False
    assert summary["db_migration_allowed"] is False
    assert summary["db_index_rebuild_allowed"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["lane_a_b_c_collapsed_scoring"] is False
    for heavy_key in (
        "reference_sidecar_rows",
        "core_smoke_sample_rows",
        "runtime_probe_summary",
        "db_retrieval_surface_audit",
        "policy_audit",
        "next_phase_recommendation",
        "per_row_metric_rows",
        "per_row_triage_rows",
        "raw_llm_response",
        "prompt_payloads",
        "db_snapshot_rows",
    ):
        assert heavy_key not in summary
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]
    assert "canonical_silver_manifest_json_sha256" not in summary["artifact_sha256"]
    assert AGENTIC_V3_6_6_REFERENCE_SIDECAR_JSONL.stat().st_size < 5_000_000
    assert AGENTIC_V3_6_6_CORE_SMOKE_SAMPLE_JSONL.stat().st_size < 250_000
    assert AGENTIC_V3_6_6_SUMMARY_JSON.stat().st_size < 250_000


def test_v3_6_7_runtime_stability_probe_artifacts_are_registered_hash_locked_and_compact() -> None:
    summary = read_json(AGENTIC_V3_6_7_SUMMARY_JSON)
    expected_artifacts = {
        "runtime_attempts_jsonl_sha256": AGENTIC_V3_6_7_RUNTIME_ATTEMPTS_JSONL,
        "runtime_stability_summary_json_sha256": AGENTIC_V3_6_7_RUNTIME_STABILITY_SUMMARY_JSON,
        "policy_audit_json_sha256": AGENTIC_V3_6_7_POLICY_AUDIT_JSON,
        "next_phase_recommendation_json_sha256": AGENTIC_V3_6_7_NEXT_PHASE_RECOMMENDATION_JSON,
    }

    assert AGENTIC_V3_6_7_SUMMARY_JSON in REGISTERED_REPORT_PATHS
    assert AGENTIC_V3_6_7_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= REGISTERED_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_6_7_RUNTIME_STABILITY_PROBE_FOR_CORE_ONLY_RUN_ID
    assert summary["source_v3_6_6_run_id"] == (
        AGENTIC_V3_6_6_DIAGNOSTIC_REFERENCE_SIDECAR_AND_RUNTIME_SURFACE_PROBE_RUN_ID
    )
    assert summary["artifact_kind"] == "diagnostic_runtime_stability_probe_for_core_only"
    assert summary["sidecar_row_counts"] == {
        "all_diagnostic": 1000,
        "core_only": 665,
        "quarantine": 0,
        "review_only_challenge": 335,
    }
    assert summary["runtime_probe_row_count"] == 30
    assert summary["runtime_probe_core_only"] is True
    assert summary["review_only_rows_attempted"] == 0
    assert summary["official_proximity_rows_attempted"] == 0
    assert summary["local_llm_live_silver_generation_allowed"] is False
    assert summary["local_llm_metric_scoring_allowed"] is False
    assert summary["external_llm_api_allowed"] is False
    assert summary["db_write_allowed"] is False
    assert summary["db_migration_allowed"] is False
    assert summary["db_index_rebuild_allowed"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["lane_a_b_c_collapsed_scoring"] is False
    for heavy_key in (
        "runtime_attempt_rows",
        "runtime_stability_summary",
        "policy_audit",
        "next_phase_recommendation",
        "reference_sidecar_rows",
        "core_smoke_sample_rows",
        "per_row_metric_rows",
        "per_row_triage_rows",
        "raw_llm_response",
        "prompt_payloads",
        "db_snapshot_rows",
    ):
        assert heavy_key not in summary
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]
    assert "canonical_silver_manifest_json_sha256" not in summary["artifact_sha256"]
    assert AGENTIC_V3_6_7_RUNTIME_ATTEMPTS_JSONL.stat().st_size < 250_000
    assert AGENTIC_V3_6_7_RUNTIME_STABILITY_SUMMARY_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_6_7_SUMMARY_JSON.stat().st_size < 250_000


def test_v3_6_8_nonprod_index_and_payload_artifacts_are_registered_hash_locked_and_compact() -> None:
    summary = read_json(AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SUMMARY_JSON)
    expected_artifacts = {
        "source_inventory_json_sha256": AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SOURCE_INVENTORY_JSON,
        "index_build_summary_json_sha256": AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_BUILD_SUMMARY_JSON,
        "payload_contract_summary_json_sha256": AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_PAYLOAD_CONTRACT_SUMMARY_JSON,
        "retrieval_smoke_diagnostics_jsonl_sha256": AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_RETRIEVAL_SMOKE_DIAGNOSTICS_JSONL,
        "failure_buckets_json_sha256": AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_FAILURE_BUCKETS_JSON,
    }

    assert AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SUMMARY_JSON in REGISTERED_REPORT_PATHS
    assert AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= REGISTERED_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == (
        AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_INDEX_MATERIALIZATION_AND_CANONICAL_PAYLOAD_WIRING_RUN_ID
    )
    assert summary["artifact_kind"] == "diagnostic_nonprod_all_source_index_materialization_and_canonical_payload_wiring"
    assert summary["outcome"] == "ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED"
    assert set(summary["outcome_choices"]) == {
        "ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED",
        "ALL_SOURCE_INDEX_BUILT_PAYLOAD_PARTIAL",
        "INDEX_MATERIALIZATION_BLOCKED",
        "PAYLOAD_WIRED_BUT_LLM_CITATION_COPY_BLOCKED",
    }
    assert summary["next_allowed_phase"] == "v3_6_9_core_only_live_diagnostic_metric"
    assert summary["no_generic_probe_recommended"] is True
    assert "manifest_locator" not in summary["recommended_next_phase"]
    assert summary["index_namespace"] == "rag-data-all-source-nonprod-v1"
    assert summary["index_or_export_mutation"] is True
    assert summary["index_or_export_mutation_scope"] == "non_production_only"
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["official_metric"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["prompt_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["source_inventory_counts"]["accepted_source_units_by_source_family"]["total"] == 136280
    assert summary["source_inventory_counts"]["retrieval_only_uncanonicalized_count"] == 0
    assert summary["load_check"]["passed"] is True
    assert summary["payload_contract"]["families_with_canonical_payload"] == ["PDF", "TEXT", "XLSX"]
    assert summary["payload_contract"]["families_with_valid_no_llm_render"] == ["PDF", "TEXT", "XLSX"]
    assert summary["retrieval_smoke"]["canonical_payload_available_count"] == 50
    assert summary["retrieval_smoke"]["no_llm_citation_render_valid_count"] == 50
    assert summary["blocking_buckets"] == []

    for heavy_key in (
        "source_inventory",
        "index_build_summary",
        "payload_contract_summary",
        "retrieval_smoke_diagnostics",
        "failure_buckets",
        "search_unit_manifest_rows",
        "raw_source_units",
        "generated_answers",
        "prompt_payloads",
        "db_snapshot_rows",
    ):
        assert heavy_key not in summary
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]
    assert "canonical_silver_manifest_json_sha256" not in summary["artifact_sha256"]
    assert AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SUMMARY_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_SOURCE_INVENTORY_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_6_8_NONPROD_ALL_SOURCE_RETRIEVAL_SMOKE_DIAGNOSTICS_JSONL.stat().st_size < 250_000


def test_v3_6_8_source_registry_architecture_audit_artifacts_are_registered_hash_locked_and_compact() -> None:
    summary = read_json(AGENTIC_V3_6_8_SOURCE_REGISTRY_SUMMARY_JSON)
    expected_artifacts = {
        "source_object_audit_json_sha256": AGENTIC_V3_6_8_SOURCE_REGISTRY_SOURCE_OBJECT_AUDIT_JSON,
        "searchunit_role_audit_json_sha256": AGENTIC_V3_6_8_SOURCE_REGISTRY_SEARCHUNIT_ROLE_AUDIT_JSON,
        "evidence_bundle_contract_json_sha256": AGENTIC_V3_6_8_SOURCE_REGISTRY_EVIDENCE_BUNDLE_CONTRACT_JSON,
        "track_routing_audit_json_sha256": AGENTIC_V3_6_8_SOURCE_REGISTRY_TRACK_ROUTING_AUDIT_JSON,
        "failure_buckets_json_sha256": AGENTIC_V3_6_8_SOURCE_REGISTRY_FAILURE_BUCKETS_JSON,
    }

    assert AGENTIC_V3_6_8_SOURCE_REGISTRY_SUMMARY_JSON in REGISTERED_REPORT_PATHS
    assert AGENTIC_V3_6_8_SOURCE_REGISTRY_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= REGISTERED_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_6_8_SOURCE_REGISTRY_FIRST_EVIDENCE_BUNDLE_ARCHITECTURE_AUDIT_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_source_registry_first_evidence_bundle_architecture_audit"
    assert summary["outcome"] == "SEARCHUNIT_OVERLOADED_BLOCKER"
    assert set(summary["outcome_choices"]) == {
        "SOURCE_REGISTRY_EVIDENCE_ARCHITECTURE_READY",
        "SEARCHUNIT_OVERLOADED_BLOCKER",
        "SOURCE_REGISTRY_MISSING_BLOCKER",
        "VECTOR_DB_COUPLING_BLOCKER",
        "TRACK_ROUTING_OVERFIT_BLOCKER",
    }
    assert summary["next_allowed_phase"] == "SearchUnit/SearchView/SourceAtom refactor"
    assert summary["no_generic_probe_recommended"] is True
    assert "manifest_locator" not in summary["recommended_next_phase"]
    assert summary["source_registry_first_policy"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["source_atom_search_view_evidence_bundle_separation_validated"] is False
    assert summary["searchunit_overloaded"] is True
    assert summary["no_vector_hydration_passed"] is True
    assert summary["no_vector_citation_rendering_passed"] is True
    assert summary["track_specific_evidence_bundle_assembly_passed_by_family"] == {
        "PDF": True,
        "TEXT": True,
        "XLSX": True,
    }
    assert summary["blocking_buckets"] == ["SEARCHUNIT_OVERLOADED_BLOCKER"]

    for heavy_key in (
        "raw_source_units",
        "source_atom_rows",
        "evidence_bundle_rows",
        "full_evidence_bundles",
        "retrieval_smoke_diagnostics",
        "generated_answers",
        "prompt_payloads",
        "db_snapshot_rows",
        "search_unit_manifest_rows",
    ):
        assert heavy_key not in summary
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]
    assert "canonical_silver_manifest_json_sha256" not in summary["artifact_sha256"]
    assert AGENTIC_V3_6_8_SOURCE_REGISTRY_SUMMARY_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_6_8_SOURCE_REGISTRY_SOURCE_OBJECT_AUDIT_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_6_8_SOURCE_REGISTRY_EVIDENCE_BUNDLE_CONTRACT_JSON.stat().st_size < 250_000


def test_v3_6_9_searchunit_searchview_sourceatom_refactor_artifacts_are_registered_hash_locked_and_compact() -> None:
    summary = read_json(AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_SUMMARY_JSON)
    expected_artifacts = {
        "contract_refactor_json_sha256": AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_CONTRACT_REFACTOR_JSON,
        "search_view_adapter_diagnostics_json_sha256": AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_ADAPTER_DIAGNOSTICS_JSON,
        "source_atom_hydration_smoke_json_sha256": AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_HYDRATION_SMOKE_JSON,
        "failure_buckets_json_sha256": AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_FAILURE_BUCKETS_JSON,
    }

    assert AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_SUMMARY_JSON in CURRENT_REPORT_PATHS
    assert AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= CURRENT_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_6_9_SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_searchunit_searchview_sourceatom_refactor"
    assert summary["outcome"] == "SEARCHUNIT_SEARCHVIEW_SOURCEATOM_CONTRACT_READY"
    assert set(summary["outcome_choices"]) == {
        "SEARCHUNIT_SEARCHVIEW_SOURCEATOM_CONTRACT_READY",
        "SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_BLOCKED",
        "SOURCE_REGISTRY_MATERIALIZATION_REQUIRED",
        "VECTOR_METADATA_DECOUPLING_REQUIRED",
    }
    assert summary["next_allowed_phase"] == "source registry materialization"
    assert summary["no_generic_probe_recommended"] is True
    assert "manifest_locator" not in summary["recommended_next_phase"]
    assert summary["source_atom_search_view_contract_validated"] is True
    assert summary["source_atom_search_view_evidence_bundle_separation_validated"] is True
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["db_migration_required_for_minimal_python_refactor"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_db_used"] is False
    assert summary["official_metric"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["blocking_buckets"] == []
    assert summary["next_blocking_work"] == ["SOURCE_REGISTRY_MATERIALIZATION_REQUIRED"]

    for heavy_key in (
        "contract_refactor",
        "search_view_adapter_diagnostics",
        "source_atom_hydration_smoke",
        "failure_buckets",
        "raw_source_units",
        "source_atom_rows",
        "evidence_bundle_rows",
        "generated_answers",
        "prompt_payloads",
        "db_snapshot_rows",
    ):
        assert heavy_key not in summary
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]
    assert "canonical_silver_manifest_json_sha256" not in summary["artifact_sha256"]
    assert AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_SUMMARY_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_CONTRACT_REFACTOR_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_6_9_SEARCHUNIT_SOURCEATOM_HYDRATION_SMOKE_JSON.stat().st_size < 250_000


def test_v3_7_2_source_registry_backed_retrieval_smoke_artifacts_are_registered_hash_locked_and_compact() -> None:
    require_v3_7_2_local_artifacts(
        AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY_JSON,
        AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS_JSONL,
        AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_FAILURE_BUCKETS_JSON,
        AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_PER_TRACK_JSON,
        AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SILVER_OVERLAY_JSON,
    )
    summary = read_json(AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY_JSON)
    expected_artifacts = {
        "topk_rows_jsonl_sha256": AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS_JSONL,
        "failure_buckets_json_sha256": AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_FAILURE_BUCKETS_JSON,
        "per_track_breakdown_json_sha256": AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_PER_TRACK_JSON,
        "silver_1000_diagnostic_overlay_json_sha256": (
            AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SILVER_OVERLAY_JSON
        ),
    }

    assert AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY_JSON in CURRENT_REPORT_PATHS
    assert AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY_JSON.exists()
    assert set(expected_artifacts.values()) <= CURRENT_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID
    assert summary["artifact_kind"] == "v3_7_2_source_registry_backed_retrieval_smoke_report"
    assert summary["run_class"] == "diagnostic_only_source_registry_backed_retrieval_smoke_report"
    assert summary["diagnostic_only"] is True
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["retrieval_score_primary_metric"] is False
    assert summary["headline_aggregate_success_rate_reported"] is False
    assert summary["official_metric"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert "silver_precision" not in json.dumps(summary, ensure_ascii=False).lower()
    assert "silver precision" not in json.dumps(summary, ensure_ascii=False).lower()

    for heavy_key in (
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "generated_answers",
        "prompt_payloads",
        "db_snapshot_rows",
        "full_evidence_bundles",
    ):
        assert heavy_key not in summary
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]
    assert AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS_JSONL.stat().st_size < 12_000_000
    assert AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_FAILURE_BUCKETS_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_PER_TRACK_JSON.stat().st_size < 250_000


def test_v3_8_file_grounded_retrieval_eval_artifacts_are_registered_hash_locked_and_compact() -> None:
    require_v3_8_local_artifacts(
        AGENTIC_V3_8_FILE_GROUNDED_SUMMARY_JSON,
        AGENTIC_V3_8_FILE_GROUNDED_METRICS_JSON,
        AGENTIC_V3_8_FILE_GROUNDED_PER_QUERY_JSONL,
        AGENTIC_V3_8_FILE_GROUNDED_PER_FAMILY_JSON,
    )
    summary = read_json(AGENTIC_V3_8_FILE_GROUNDED_SUMMARY_JSON)
    metrics = read_json(AGENTIC_V3_8_FILE_GROUNDED_METRICS_JSON)
    per_family = read_json(AGENTIC_V3_8_FILE_GROUNDED_PER_FAMILY_JSON)
    per_query_rows = read_jsonl(AGENTIC_V3_8_FILE_GROUNDED_PER_QUERY_JSONL)
    expected_artifacts = {
        "metrics_json_sha256": AGENTIC_V3_8_FILE_GROUNDED_METRICS_JSON,
        "per_query_jsonl_sha256": AGENTIC_V3_8_FILE_GROUNDED_PER_QUERY_JSONL,
        "per_family_json_sha256": AGENTIC_V3_8_FILE_GROUNDED_PER_FAMILY_JSON,
    }

    assert AGENTIC_V3_8_FILE_GROUNDED_SUMMARY_JSON in CURRENT_REPORT_PATHS
    assert set(expected_artifacts.values()) <= CURRENT_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID
    assert summary["artifact_kind"] == "v3_8_file_grounded_retrieval_eval_summary"
    assert summary["run_class"] == "diagnostic_only_file_grounded_retrieval_eval"
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["answer_generation_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_canonical_truth_used_for_metrics"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["xlsx_pdf_collapsed_score_reported"] is False
    assert set(summary["per_source_family"]) == {"PDF", "XLSX"}
    assert set(per_family) == {"PDF", "XLSX"}
    assert summary["per_source_family"] == per_family
    assert metrics["per_source_family"] == per_family
    assert len(per_query_rows) == summary["source_family_counts"]["PDF"] + summary["source_family_counts"]["XLSX"]
    assert summary["source_family_counts"]["PDF"] > 0
    assert summary["source_family_counts"]["XLSX"] > 0
    assert summary["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert summary["denominator_audit"]["denominator_scope"] == "diagnostic_v3_7_2_topk_rows_pdf_xlsx_only"
    assert summary["denominator_audit"]["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert summary["denominator_audit"]["query_scope_counts"]["PDF"] == {
        "sealed_gold_no_regression_check": 4,
        "silver_1000_diagnostic_overlay": 325,
    }
    assert summary["denominator_audit"]["query_scope_counts"]["XLSX"] == {
        "sealed_gold_no_regression_check": 19,
        "silver_1000_diagnostic_overlay": 325,
    }
    assert summary["denominator_audit"]["missing_target_mapping_surface_count"] == 0
    assert metrics["denominator_policy"]["row_scope"] == "PDF/XLSX query rows with an existing target mapping surface"
    assert metrics["vector_truth_violation_count"] == 0
    assert metrics["ignored_vector_truth_claim_count"] >= 0
    assert "per_query_rows" not in metrics
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["fail_closed_reasons"] == []
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "readme_performance_claim_json_sha256" not in summary["artifact_sha256"]

    for heavy_key in (
        "metrics",
        "per_query_rows",
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "generated_answers",
        "prompt_payloads",
        "db_snapshot_rows",
        "full_evidence_bundles",
    ):
        assert heavy_key not in summary
    assert AGENTIC_V3_8_FILE_GROUNDED_SUMMARY_JSON.stat().st_size < 500_000
    assert AGENTIC_V3_8_FILE_GROUNDED_METRICS_JSON.stat().st_size < 500_000
    assert AGENTIC_V3_8_FILE_GROUNDED_PER_QUERY_JSONL.stat().st_size < 2_000_000
    assert AGENTIC_V3_8_FILE_GROUNDED_PER_FAMILY_JSON.stat().st_size < 250_000


def test_v3_8_file_grounded_writer_emits_compact_artifacts_and_summary_hashes(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    summary_path = tmp_path / "v3_8_summary.json"
    metrics_path = tmp_path / "v3_8_metrics.json"
    per_query_path = tmp_path / "v3_8_per_query.jsonl"
    per_family_path = tmp_path / "v3_8_per_family.json"

    monkeypatch.setattr(runner, "DEFAULT_V3_8_FILE_GROUNDED_METRICS_JSON", metrics_path)
    monkeypatch.setattr(runner, "DEFAULT_V3_8_FILE_GROUNDED_PER_QUERY_JSONL", per_query_path)
    monkeypatch.setattr(runner, "DEFAULT_V3_8_FILE_GROUNDED_PER_FAMILY_JSON", per_family_path)
    monkeypatch.setattr(
        runner,
        "report_artifact_path",
        lambda run_id, suffix: summary_path
        if run_id == runner.V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID and suffix == "summary.json"
        else tmp_path / f"{run_id}_{suffix}",
    )

    summary = {
        "run_id": runner.V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID,
        "status": "DIAGNOSTIC_FILE_GROUNDED_RETRIEVAL_EVAL_COMPUTED",
        "metrics": {
            "artifact_kind": "v3_8_file_grounded_retrieval_eval_metrics",
            "per_source_family": {"PDF": {"query_count": 1}, "XLSX": {"query_count": 1}},
        },
        "per_query_rows": [
            {"query_id": "pdf_q", "source_family": "PDF"},
            {"query_id": "xlsx_q", "source_family": "XLSX"},
        ],
        "per_source_family": {"PDF": {"query_count": 1}, "XLSX": {"query_count": 1}},
        "artifact_paths": {
            "summary_json": "tmp/v3_8_summary.json",
            "metrics_json": "tmp/v3_8_metrics.json",
            "per_query_jsonl": "tmp/v3_8_per_query.jsonl",
            "per_family_json": "tmp/v3_8_per_family.json",
        },
    }

    runner.write_v3_6_low_touch_weak_noisy_silver_artifacts(summary)

    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert metrics_path.exists()
    assert per_query_path.exists()
    assert per_family_path.exists()
    assert "metrics" not in persisted
    assert "per_query_rows" not in persisted
    assert "per_query_rows" not in json.loads(metrics_path.read_text(encoding="utf-8"))
    assert persisted["per_source_family"] == {"PDF": {"query_count": 1}, "XLSX": {"query_count": 1}}
    assert summary["artifact_sha256"]["metrics_json_sha256"] == sha256_file(metrics_path)
    assert summary["artifact_sha256"]["per_query_jsonl_sha256"] == sha256_file(per_query_path)
    assert summary["artifact_sha256"]["per_family_json_sha256"] == sha256_file(per_family_path)
    assert summary["artifact_sha256"]["summary_json_sha256"] == sha256_file(summary_path)
    assert "summary_json_sha256" not in persisted["artifact_sha256"]


def test_v3_8_1_evidence_selector_artifacts_are_registered_hash_locked_and_compact() -> None:
    require_v3_8_1_local_artifacts(
        AGENTIC_V3_8_1_EVIDENCE_SELECTOR_SUMMARY_JSON,
        AGENTIC_V3_8_1_EVIDENCE_SELECTOR_METRICS_JSON,
        AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_QUERY_JSONL,
        AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_FAMILY_JSON,
    )
    summary = read_json(AGENTIC_V3_8_1_EVIDENCE_SELECTOR_SUMMARY_JSON)
    metrics = read_json(AGENTIC_V3_8_1_EVIDENCE_SELECTOR_METRICS_JSON)
    per_family = read_json(AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_FAMILY_JSON)
    per_query_rows = read_jsonl(AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_QUERY_JSONL)
    expected_artifacts = {
        "metrics_json_sha256": AGENTIC_V3_8_1_EVIDENCE_SELECTOR_METRICS_JSON,
        "per_query_jsonl_sha256": AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_QUERY_JSONL,
        "per_family_json_sha256": AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_FAMILY_JSON,
    }

    assert AGENTIC_V3_8_1_EVIDENCE_SELECTOR_SUMMARY_JSON in CURRENT_REPORT_PATHS
    assert set(expected_artifacts.values()) <= CURRENT_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID
    assert summary["parent_file_grounded_eval_run_id"] == AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID
    assert summary["artifact_kind"] == "v3_8_1_evidence_selector_summary"
    assert summary["run_class"] == "diagnostic_only_evidence_selector_v1"
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["answer_generation_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_canonical_truth_used_for_selection"] is True
    assert summary["selector_uses_target_source_atom_ids_for_selection"] is False
    assert summary["target_source_atom_ids_used_for_metrics_only"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["xlsx_pdf_collapsed_score_reported"] is False
    assert set(summary["per_source_family"]) == {"PDF", "XLSX"}
    assert set(per_family) == {"PDF", "XLSX"}
    assert summary["per_source_family"] == per_family
    assert metrics["per_source_family"] == per_family
    assert len(per_query_rows) == summary["source_family_counts"]["PDF"] + summary["source_family_counts"]["XLSX"]
    assert all(len(row.get("selected_evidence", [])) <= 3 for row in per_query_rows)
    assert summary["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert summary["denominator_audit"]["denominator_scope"] == "diagnostic_v3_7_2_topk_rows_pdf_xlsx_only"
    assert summary["denominator_audit"]["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert metrics["denominator_policy"]["xlsx_and_pdf_are_not_collapsed"] is True
    assert metrics["selector_policy"]["uses_target_source_atom_ids_for_selection"] is False
    assert metrics["selector_policy"]["target_source_atom_ids_used_for_metrics_only"] is True
    assert "per_query_rows" not in metrics
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["fail_closed_reasons"] == []
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]

    for heavy_key in (
        "metrics",
        "per_query_rows",
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "generated_answers",
        "prompt_payloads",
        "db_snapshot_rows",
        "full_evidence_bundles",
    ):
        assert heavy_key not in summary
    assert AGENTIC_V3_8_1_EVIDENCE_SELECTOR_SUMMARY_JSON.stat().st_size < 500_000
    assert AGENTIC_V3_8_1_EVIDENCE_SELECTOR_METRICS_JSON.stat().st_size < 500_000
    assert AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_QUERY_JSONL.stat().st_size < 2_000_000
    assert AGENTIC_V3_8_1_EVIDENCE_SELECTOR_PER_FAMILY_JSON.stat().st_size < 250_000


def test_v3_8_1_evidence_selector_writer_emits_compact_artifacts_and_summary_hashes(
    tmp_path,
    monkeypatch,
) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    summary_path = tmp_path / "v3_8_1_summary.json"
    metrics_path = tmp_path / "v3_8_1_metrics.json"
    per_query_path = tmp_path / "v3_8_1_per_query.jsonl"
    per_family_path = tmp_path / "v3_8_1_per_family.json"

    monkeypatch.setattr(runner, "DEFAULT_V3_8_1_EVIDENCE_SELECTOR_METRICS_JSON", metrics_path)
    monkeypatch.setattr(runner, "DEFAULT_V3_8_1_EVIDENCE_SELECTOR_PER_QUERY_JSONL", per_query_path)
    monkeypatch.setattr(runner, "DEFAULT_V3_8_1_EVIDENCE_SELECTOR_PER_FAMILY_JSON", per_family_path)
    monkeypatch.setattr(
        runner,
        "report_artifact_path",
        lambda run_id, suffix: summary_path
        if run_id == runner.V3_8_1_EVIDENCE_SELECTOR_RUN_ID and suffix == "summary.json"
        else tmp_path / f"{run_id}_{suffix}",
    )

    summary = {
        "run_id": runner.V3_8_1_EVIDENCE_SELECTOR_RUN_ID,
        "status": "DIAGNOSTIC_EVIDENCE_SELECTOR_V1_COMPUTED",
        "metrics": {
            "artifact_kind": "v3_8_1_evidence_selector_metrics",
            "per_source_family": {"PDF": {"query_count": 1}, "XLSX": {"query_count": 1}},
            "per_query_rows": [{"query_id": "heavy_row"}],
        },
        "per_query_rows": [
            {"query_id": "pdf_q", "source_family": "PDF"},
            {"query_id": "xlsx_q", "source_family": "XLSX"},
        ],
        "per_source_family": {"PDF": {"query_count": 1}, "XLSX": {"query_count": 1}},
        "artifact_paths": {
            "summary_json": "tmp/v3_8_1_summary.json",
            "metrics_json": "tmp/v3_8_1_metrics.json",
            "per_query_jsonl": "tmp/v3_8_1_per_query.jsonl",
            "per_family_json": "tmp/v3_8_1_per_family.json",
        },
    }

    runner.write_v3_6_low_touch_weak_noisy_silver_artifacts(summary)

    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert metrics_path.exists()
    assert per_query_path.exists()
    assert per_family_path.exists()
    assert "metrics" not in persisted
    assert "per_query_rows" not in persisted
    assert "per_query_rows" not in json.loads(metrics_path.read_text(encoding="utf-8"))
    assert persisted["per_source_family"] == {"PDF": {"query_count": 1}, "XLSX": {"query_count": 1}}
    assert summary["artifact_sha256"]["metrics_json_sha256"] == sha256_file(metrics_path)
    assert summary["artifact_sha256"]["per_query_jsonl_sha256"] == sha256_file(per_query_path)
    assert summary["artifact_sha256"]["per_family_json_sha256"] == sha256_file(per_family_path)
    assert summary["artifact_sha256"]["summary_json_sha256"] == sha256_file(summary_path)
    assert "summary_json_sha256" not in persisted["artifact_sha256"]


def test_v3_8_2_oracle_free_file_resolve_artifacts_are_registered_hash_locked_and_compact() -> None:
    require_v3_8_2_local_artifacts(
        AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_SUMMARY_JSON,
        AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_METRICS_JSON,
        AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_QUERY_JSONL,
        AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_FAMILY_JSON,
    )
    summary = read_json(AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_SUMMARY_JSON)
    metrics = read_json(AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_METRICS_JSON)
    per_family = read_json(AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_FAMILY_JSON)
    per_query_rows = read_jsonl(AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_QUERY_JSONL)
    expected_artifacts = {
        "metrics_json_sha256": AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_METRICS_JSON,
        "per_query_jsonl_sha256": AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_QUERY_JSONL,
        "per_family_json_sha256": AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_FAMILY_JSON,
    }

    assert AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_SUMMARY_JSON in CURRENT_REPORT_PATHS
    assert set(expected_artifacts.values()) <= CURRENT_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID
    assert summary["parent_file_grounded_eval_run_id"] == AGENTIC_V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID
    assert summary["parent_evidence_selector_run_id"] == AGENTIC_V3_8_1_EVIDENCE_SELECTOR_RUN_ID
    assert summary["artifact_kind"] == "v3_8_2_oracle_free_file_resolve_summary"
    assert summary["run_class"] == "diagnostic_only_oracle_free_file_resolve_v1"
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["answer_generation_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["gold_mutation"] is False
    assert summary["qrels_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["file_resolve_oracle_free"] is True
    assert summary["oracle_assisted_file_resolve"] is False
    assert summary["oracle_free_input_violation_count"] == 0
    assert summary["resolver_uses_target_source_atom_ids_for_selection"] is False
    assert summary["target_source_atom_ids_used_for_metrics_only"] is True
    assert summary["source_atom_registry_canonical_truth_used_for_resolution"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["xlsx_pdf_collapsed_score_reported"] is False
    assert set(summary["per_source_family"]) == {"PDF", "XLSX"}
    assert set(per_family) == {"PDF", "XLSX"}
    assert summary["per_source_family"] == per_family
    assert metrics["per_source_family"] == per_family
    assert len(per_query_rows) == summary["source_family_counts"]["PDF"] + summary["source_family_counts"]["XLSX"]
    assert all(len(row.get("resolved_file_candidates", [])) <= 3 for row in per_query_rows)
    assert summary["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert summary["denominator_audit"]["denominator_scope"] == "diagnostic_v3_7_2_topk_rows_pdf_xlsx_only"
    assert summary["denominator_audit"]["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert metrics["denominator_policy"]["xlsx_and_pdf_are_not_collapsed"] is True
    assert metrics["resolver_policy"]["oracle_free"] is True
    assert metrics["resolver_policy"]["oracle_assisted_file_resolve"] is False
    assert metrics["oracle_free_input_violation_count"] == 0
    assert "per_query_rows" not in metrics
    forbidden_candidate_artifact_keys = {
        "metric_target_file_identity",
        "question_gold_locator_target",
        "official_manifest_target",
        "target_source_atom_ids",
        "target_search_view_ids",
        "target_locator_fingerprint",
        "target_search_unit_id",
        "target_parent_source_unit_id",
        "target_mapping_audit",
        "matched_text_or_value",
        "expected_answer",
        "supporting_evidence",
        "qrels",
        "relevance_label",
        "answerability_label",
    }

    def assert_forbidden_candidate_keys_absent(value: object) -> None:
        if isinstance(value, dict):
            assert not forbidden_candidate_artifact_keys.intersection(value)
            for child in value.values():
                assert_forbidden_candidate_keys_absent(child)
        elif isinstance(value, list):
            for child in value:
                assert_forbidden_candidate_keys_absent(child)

    assert_forbidden_candidate_keys_absent(per_query_rows)
    assert all(
        row.get("metric_overlay_redacted_from_candidate_artifact") is True
        for row in per_query_rows
    )
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["v3_8_summary_sha256_before"] == summary["v3_8_summary_sha256_after"]
    assert summary["v3_8_summary_sha256_unchanged"] is True
    assert summary["v3_8_1_summary_sha256_before"] == summary["v3_8_1_summary_sha256_after"]
    assert summary["v3_8_1_summary_sha256_unchanged"] is True
    assert summary["fail_closed_reasons"] == []
    assert "summary_json_sha256" not in summary["artifact_sha256"]
    assert "official_qrels_jsonl_sha256" not in summary["artifact_sha256"]
    assert "official_labels_jsonl_sha256" not in summary["artifact_sha256"]

    for heavy_key in (
        "metrics",
        "per_query_rows",
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "generated_answers",
        "prompt_payloads",
        "db_snapshot_rows",
        "full_evidence_bundles",
    ):
        assert heavy_key not in summary
    assert AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_SUMMARY_JSON.stat().st_size < 500_000
    assert AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_METRICS_JSON.stat().st_size < 500_000
    assert AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_QUERY_JSONL.stat().st_size < 4_000_000
    assert AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_FAMILY_JSON.stat().st_size < 250_000


def test_v3_8_2_oracle_free_file_resolve_writer_emits_compact_artifacts_and_summary_hashes(
    tmp_path,
    monkeypatch,
) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    summary_path = tmp_path / "v3_8_2_summary.json"
    metrics_path = tmp_path / "v3_8_2_metrics.json"
    per_query_path = tmp_path / "v3_8_2_per_query.jsonl"
    per_family_path = tmp_path / "v3_8_2_per_family.json"

    monkeypatch.setattr(runner, "DEFAULT_V3_8_2_ORACLE_FREE_FILE_RESOLVE_METRICS_JSON", metrics_path)
    monkeypatch.setattr(runner, "DEFAULT_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_QUERY_JSONL", per_query_path)
    monkeypatch.setattr(runner, "DEFAULT_V3_8_2_ORACLE_FREE_FILE_RESOLVE_PER_FAMILY_JSON", per_family_path)
    monkeypatch.setattr(
        runner,
        "report_artifact_path",
        lambda run_id, suffix: summary_path
        if run_id == runner.V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID and suffix == "summary.json"
        else tmp_path / f"{run_id}_{suffix}",
    )

    summary = {
        "run_id": runner.V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID,
        "status": "DIAGNOSTIC_ORACLE_FREE_FILE_RESOLVE_COMPUTED",
        "metrics": {
            "artifact_kind": "v3_8_2_oracle_free_file_resolve_metrics",
            "per_source_family": {"PDF": {"query_count": 1}, "XLSX": {"query_count": 1}},
            "per_query_rows": [{"query_id": "heavy_row"}],
        },
        "per_query_rows": [
            {"query_id": "pdf_q", "source_family": "PDF"},
            {"query_id": "xlsx_q", "source_family": "XLSX"},
        ],
        "per_source_family": {"PDF": {"query_count": 1}, "XLSX": {"query_count": 1}},
        "artifact_paths": {
            "summary_json": "tmp/v3_8_2_summary.json",
            "metrics_json": "tmp/v3_8_2_metrics.json",
            "per_query_jsonl": "tmp/v3_8_2_per_query.jsonl",
            "per_family_json": "tmp/v3_8_2_per_family.json",
        },
    }

    runner.write_v3_6_low_touch_weak_noisy_silver_artifacts(summary)

    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert metrics_path.exists()
    assert per_query_path.exists()
    assert per_family_path.exists()
    assert "metrics" not in persisted
    assert "per_query_rows" not in persisted
    assert "per_query_rows" not in json.loads(metrics_path.read_text(encoding="utf-8"))
    assert persisted["per_source_family"] == {"PDF": {"query_count": 1}, "XLSX": {"query_count": 1}}
    assert summary["artifact_sha256"]["metrics_json_sha256"] == sha256_file(metrics_path)
    assert summary["artifact_sha256"]["per_query_jsonl_sha256"] == sha256_file(per_query_path)
    assert summary["artifact_sha256"]["per_family_json_sha256"] == sha256_file(per_family_path)
    assert summary["artifact_sha256"]["summary_json_sha256"] == sha256_file(summary_path)
    assert "summary_json_sha256" not in persisted["artifact_sha256"]


def test_v3_8_3_xlsx_scoped_cell_resolve_artifacts_are_registered_hash_locked_and_compact() -> None:
    require_v3_8_3_local_artifacts(
        AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_SUMMARY_JSON,
        AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_METRICS_JSON,
        AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_QUERY_JSONL,
        AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSON,
        AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSONL,
    )
    summary = read_json(AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_SUMMARY_JSON)
    metrics = read_json(AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_METRICS_JSON)
    per_family = read_json(AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSON)
    per_family_rows = read_jsonl(AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSONL)
    per_query_rows = read_jsonl(AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_QUERY_JSONL)
    expected_artifacts = {
        "metrics_json_sha256": AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_METRICS_JSON,
        "per_query_jsonl_sha256": AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_QUERY_JSONL,
        "per_family_json_sha256": AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSON,
        "per_family_jsonl_sha256": AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSONL,
    }

    assert AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_SUMMARY_JSON in CURRENT_REPORT_PATHS
    assert set(expected_artifacts.values()) <= CURRENT_REPORT_PATHS
    for key, path in expected_artifacts.items():
        assert path.exists(), path
        assert summary["artifact_sha256"][key] == sha256_file(path)

    assert summary["run_id"] == AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID
    assert summary["parent_file_resolve_run_id"] == AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID
    assert summary["file_resolve_gate_run_id"] == AGENTIC_V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID
    assert summary["artifact_kind"] == "v3_8_3_xlsx_scoped_cell_resolve_summary"
    assert summary["run_class"] == "diagnostic_only_xlsx_scoped_cell_resolve_v1"
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["answer_generation_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["gold_mutation"] is False
    assert summary["qrels_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["silver_mutation"] is False
    assert summary["xlsx_only"] is True
    assert summary["file_resolve_oracle_free"] is True
    assert summary["oracle_assisted_file_resolve"] is False
    assert summary["oracle_free_input_violation_count"] == 0
    assert summary["resolver_uses_target_source_atom_ids_for_selection"] is False
    assert summary["target_source_atom_ids_used_for_metrics_only"] is True
    assert summary["source_atom_registry_canonical_truth_used_for_resolution"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["xlsx_pdf_collapsed_score_reported"] is False
    assert summary["source_family_counts"] == {"XLSX": 344}
    assert summary["all_xlsx_query_count"] == 344
    assert summary["v3_8_2_gate_row_found_count"] == 344
    assert summary["v3_8_2_gate_missing_count"] == 0
    assert summary["v3_8_2_gate_duplicate_query_id_count"] == 0
    assert set(summary["per_source_family"]) == {"XLSX"}
    assert per_family == summary["per_source_family"]
    assert len(per_family_rows) == 1
    assert per_family_rows[0] == metrics["per_family_rows"][0]
    assert per_family_rows[0]["source_family"] == "XLSX"
    assert metrics["per_source_family"] == per_family
    assert per_family_rows[0]["miss_taxonomy"] == per_family["XLSX"]["miss_taxonomy"]
    assert summary["miss_taxonomy"] == per_family["XLSX"]["miss_taxonomy"]
    assert metrics["denominator_policy"]["xlsx_only_denominator"] is True
    assert metrics["denominator_policy"]["pdf_rows_excluded"] is True
    assert metrics["denominator_policy"]["xlsx_and_pdf_are_not_collapsed"] is True
    assert metrics["resolver_policy"]["input_gate"] == "persisted_v3_8_2_oracle_free_file_resolve_per_query_row"
    assert metrics["resolver_policy"]["forbidden_inputs_used_for_selection"] == []
    assert metrics["oracle_free_input_violation_count"] == 0
    assert len(per_query_rows) == 344
    assert len({row["query_id"] for row in per_query_rows}) == 344
    assert all(row["source_family"] == "XLSX" for row in per_query_rows)
    assert all(row["resolve_status"] in {"resolved", "abstain", "disambiguation"} for row in per_query_rows)
    for row in per_query_rows:
        assert set(row["xlsx_miss_taxonomy"]) >= {
            "is_miss",
            "miss_stage",
            "primary_category",
            "reasons",
            "resolver_improvement_hint",
        }
    for metric_name in (
        "sheet_resolve@1",
        "sheet_resolve@3",
        "table_or_range_resolve@1",
        "table_or_range_resolve@3",
        "cell_or_value_resolve@1",
        "cell_or_value_resolve@3",
        "abstain_rate",
        "wrong_workbook_block_rate",
    ):
        expected_numerator = sum(1 for row in per_query_rows if row[metric_name] is True)
        assert per_family["XLSX"]["metrics"][metric_name]["numerator"] == expected_numerator
        assert per_family["XLSX"]["metrics"][metric_name]["denominator"] == len(per_query_rows)
    expected_taxonomy_counts = dict(
        Counter(row["xlsx_miss_taxonomy"]["primary_category"] for row in per_query_rows)
    )
    assert per_family["XLSX"]["miss_taxonomy"]["primary_category_counts"] == expected_taxonomy_counts
    assert all(row.get("v3_8_2_gate_row_found") is True for row in per_query_rows)
    assert all(len(row.get("scoped_cell_candidates", [])) <= 3 for row in per_query_rows)
    assert "per_query_rows" not in metrics

    forbidden_candidate_artifact_keys = {
        "metric_target_file_identity",
        "question_gold_locator_target",
        "official_manifest_target",
        "target_source_atom_ids",
        "target_search_view_ids",
        "target_locator_fingerprint",
        "target_search_unit_id",
        "target_parent_source_unit_id",
        "target_mapping_audit",
        "matched_text_or_value",
        "expected_answer",
        "supporting_evidence",
        "qrels",
        "relevance_label",
        "answerability_label",
    }

    def assert_forbidden_candidate_keys_absent(value: object) -> None:
        if isinstance(value, dict):
            assert not forbidden_candidate_artifact_keys.intersection(value)
            for child in value.values():
                assert_forbidden_candidate_keys_absent(child)
        elif isinstance(value, list):
            for child in value:
                assert_forbidden_candidate_keys_absent(child)

    assert_forbidden_candidate_keys_absent(per_query_rows)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["v3_8_2_summary_sha256_before"] == summary["v3_8_2_summary_sha256_after"]
    assert summary["v3_8_2_summary_sha256_unchanged"] is True
    assert summary["v3_8_2_per_query_sha256_before"] == summary["v3_8_2_per_query_sha256_after"]
    assert summary["v3_8_2_per_query_sha256_unchanged"] is True
    assert summary["fail_closed_reasons"] == []
    assert "summary_json_sha256" not in summary["artifact_sha256"]

    for heavy_key in (
        "metrics",
        "per_query_rows",
        "topk_result_rows",
        "source_atom_rows",
        "search_view_rows",
        "generated_answers",
        "prompt_payloads",
        "db_snapshot_rows",
        "full_evidence_bundles",
        "per_family_rows",
    ):
        assert heavy_key not in summary
    assert AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_SUMMARY_JSON.stat().st_size < 500_000
    assert AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_METRICS_JSON.stat().st_size < 500_000
    assert AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_QUERY_JSONL.stat().st_size < 4_000_000
    assert AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSON.stat().st_size < 250_000
    assert AGENTIC_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSONL.stat().st_size < 250_000


def test_v3_8_3_xlsx_scoped_cell_resolve_writer_emits_compact_artifacts_and_summary_hashes(
    tmp_path,
    monkeypatch,
) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    summary_path = tmp_path / "v3_8_3_summary.json"
    metrics_path = tmp_path / "v3_8_3_metrics.json"
    per_query_path = tmp_path / "v3_8_3_per_query.jsonl"
    per_family_path = tmp_path / "v3_8_3_per_family.json"
    per_family_jsonl_path = tmp_path / "v3_8_3_per_family.jsonl"

    monkeypatch.setattr(runner, "DEFAULT_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_METRICS_JSON", metrics_path)
    monkeypatch.setattr(runner, "DEFAULT_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_QUERY_JSONL", per_query_path)
    monkeypatch.setattr(runner, "DEFAULT_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSON", per_family_path)
    monkeypatch.setattr(
        runner,
        "DEFAULT_V3_8_3_XLSX_SCOPED_CELL_RESOLVE_PER_FAMILY_JSONL",
        per_family_jsonl_path,
    )
    monkeypatch.setattr(
        runner,
        "report_artifact_path",
        lambda run_id, suffix: summary_path
        if run_id == runner.V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID and suffix == "summary.json"
        else tmp_path / f"{run_id}_{suffix}",
    )

    summary = {
        "run_id": runner.V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID,
        "status": "DIAGNOSTIC_XLSX_SCOPED_CELL_RESOLVE_COMPUTED",
        "metrics": {
            "artifact_kind": "v3_8_3_xlsx_scoped_cell_resolve_metrics",
            "per_source_family": {"XLSX": {"query_count": 1}},
            "per_query_rows": [{"query_id": "heavy_row"}],
            "per_family_rows": [{"source_family": "XLSX", "query_count": 1}],
        },
        "per_query_rows": [{"query_id": "xlsx_q", "source_family": "XLSX"}],
        "per_source_family": {"XLSX": {"query_count": 1}},
        "per_family_rows": [{"source_family": "XLSX", "query_count": 1}],
        "artifact_paths": {
            "summary_json": "tmp/v3_8_3_summary.json",
            "metrics_json": "tmp/v3_8_3_metrics.json",
            "per_query_jsonl": "tmp/v3_8_3_per_query.jsonl",
            "per_family_json": "tmp/v3_8_3_per_family.json",
            "per_family_jsonl": "tmp/v3_8_3_per_family.jsonl",
        },
    }

    runner.write_v3_6_low_touch_weak_noisy_silver_artifacts(summary)

    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert metrics_path.exists()
    assert per_query_path.exists()
    assert per_family_path.exists()
    assert per_family_jsonl_path.exists()
    assert "metrics" not in persisted
    assert "per_query_rows" not in persisted
    assert "per_family_rows" not in persisted
    assert "per_query_rows" not in json.loads(metrics_path.read_text(encoding="utf-8"))
    assert read_jsonl(per_family_jsonl_path) == [{"source_family": "XLSX", "query_count": 1}]
    assert persisted["per_source_family"] == {"XLSX": {"query_count": 1}}
    assert summary["artifact_sha256"]["metrics_json_sha256"] == sha256_file(metrics_path)
    assert summary["artifact_sha256"]["per_query_jsonl_sha256"] == sha256_file(per_query_path)
    assert summary["artifact_sha256"]["per_family_json_sha256"] == sha256_file(per_family_path)
    assert summary["artifact_sha256"]["per_family_jsonl_sha256"] == sha256_file(per_family_jsonl_path)
    assert summary["artifact_sha256"]["summary_json_sha256"] == sha256_file(summary_path)
    assert "summary_json_sha256" not in persisted["artifact_sha256"]


def test_pdf_candidate_locator_repair_artifacts_are_locked_to_current_report_only_state() -> None:
    first_run = read_json(REPORT_DIR / "baseline_v1.json")
    input_config = read_json(REPORT_DIR / "metric_input_v1.json")
    xlsx_rows = read_jsonl(REPORT_DIR / "xlsx_candidate_v1.jsonl")
    pdf_rows = read_jsonl(REPORT_DIR / "pdf_candidate_v1.jsonl")
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    smoke = read_json(REPORT_DIR / "smoke_v1.json")

    assert {path.name for path in REPORT_DIR.iterdir() if path.is_file()} == CURRENT_REPORT_FILENAMES
    assert "v3_comparable_summary.md" not in ARCHIVED_REPORT_FILENAMES
    assert not (archived_report_dir() / "v3_comparable_summary.md").exists()
    assert {path.name for path in archived_report_dir().iterdir()} == ARCHIVED_REPORT_FILENAMES
    assert CURRENT_REPORT_FILENAMES | ARCHIVED_REPORT_FILENAMES == ALL_REPORT_FILENAMES
    assert not (REPORT_DIR / "status.md").exists()
    assert {path.name for path in REPORT_DIR.glob("*.md")} == EXPLICIT_GENERATED_REPORT_MARKDOWN_FILENAMES
    assert PROGRESS_DOC.exists()
    assert MEASUREMENTS_DOC.exists()
    assert TRIAGE_DOC.exists()

    assert first_run["scored_count"] == 29
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }
    assert Counter(row["failure_category"] for row in first_run["row_results"]) == Counter(
        {"CITATION_UNSUPPORTED": 11, "PARTIAL_OR_UNSUPPORTED": 10, "PASS": 8}
    )
    first_run_by_id = {row["query_id"]: row for row in first_run["row_results"]}
    scorer_by_id = {
        row["query_id"]: row
        for row in read_jsonl(REPORT_DIR / "scorer_v1.jsonl")
    }
    config_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert set(first_run_by_id) == set(scorer_by_id) == config_query_ids
    assert {
        query_id: row["failure_category"]
        for query_id, row in first_run_by_id.items()
    } == {
        query_id: row["failure_category"]
        for query_id, row in scorer_by_id.items()
    }
    assert [first_run_by_id[query_id]["failure_category"] for query_id in REPAIRED_PDF_QUERY_IDS] == [
        "PARTIAL_OR_UNSUPPORTED",
        "PARTIAL_OR_UNSUPPORTED",
        "PARTIAL_OR_UNSUPPORTED",
    ]

    assert len(xlsx_rows) == 29
    assert len({row["query_id"] for row in xlsx_rows}) == 29
    assert Counter(row["failure_category"] for row in xlsx_rows) == Counter({"PASS": 26, "PARTIAL_OR_UNSUPPORTED": 3})
    assert all(row.get("promotion_evidence") is False for row in xlsx_rows)
    xlsx_by_id = {row["query_id"]: row for row in xlsx_rows}
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = xlsx_by_id[query_id]
        assert row["failure_category"] == "PARTIAL_OR_UNSUPPORTED"
        serialized_row = json.dumps(row, ensure_ascii=False)
        assert "table_value_candidate" not in serialized_row
        assert "OFFICIAL_COMPATIBLE_LOCATOR" not in serialized_row

    assert len(pdf_rows) == 29
    assert len({row["query_id"] for row in pdf_rows}) == 29
    assert Counter(row["failure_category"] for row in pdf_rows) == Counter({"PASS": 29})
    assert all(row.get("promotion_evidence") is False for row in pdf_rows)

    pdf_by_id = {row["query_id"]: row for row in pdf_rows}
    assert all(sum(1 for row in pdf_rows if row["query_id"] == query_id) == 1 for query_id in REPAIRED_PDF_QUERY_IDS)
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = pdf_by_id[query_id]
        score_details = row["score_details"]
        locator = row["generated_citations"][0]["citation_locator"]
        assert score_details["locator_compatibility"] == ["OFFICIAL_COMPATIBLE_LOCATOR"]
        assert score_details["expected_answer_used_for_generation"] is False
        assert score_details["supporting_evidence_used_for_generation"] is False
        assert score_details["gold_fields_used_for_generation"] is False
        assert locator["search_unit_id"].strip()
        assert locator["document_version_id"].strip()
        assert locator["source_pdf_path"].strip()
        assert locator["row_label"].strip()
        assert locator["target_column"].strip()
        assert locator["source_basis"].strip()
        assert numeric_bbox(locator["bbox"])
        if query_id == "gq_auto_010":
            assert locator["region_type"] == "paragraph"
            assert "bbox_granularity" not in locator
        else:
            assert locator["region_type"] == "table_body"
            assert locator["bbox_granularity"] == "row_only"

    status = next(event for event in reversed(status_events) if event.get("event_type") == "pdf_candidate_locator_hardening")
    assert status["event_type"] == "pdf_candidate_locator_hardening"
    assert status["current_focused_result"] == "68 passed, 0 skipped, 0 failed"
    assert status["pdf_candidate_result_count"] == {
        "failure_category_counts": {"PASS": 29},
        "rows": 29,
        "unique_query_ids": 29,
    }
    assert status["pdf_repaired_rows"] == 3
    assert set(status["locator_compatibility_after"]) == set(REPAIRED_PDF_QUERY_IDS)
    assert all(value == ["OFFICIAL_COMPATIBLE_LOCATOR"] for value in status["locator_compatibility_after"].values())
    assert status["guardrails"]["promotion_evidence"] is False
    assert status["guardrails"]["denominator_mutation"] is False
    assert status["guardrails"]["production_mutation"] is False

    assert smoke["official_metric_execution_started"] is False
    assert first_run["official_metric_execution_started"] is True


def test_readme_baseline_section_matches_immutable_first_run_and_separates_candidates() -> None:
    first_run = read_json(REPORT_DIR / "baseline_v1.json")
    readme = README.read_text(encoding="utf-8")
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_progress = progress.split("## Short History", 1)[0]
    current_flat = " ".join(current_progress.split())
    measurements = MEASUREMENTS_DOC.read_text(encoding="utf-8")

    assert "docs/rag-ingestion-progress.md" in readme
    assert "docs/rag-ingestion-measurements.md" in readme
    assert "docs/rag-ingestion-triage.md" in readme
    assert "production promotion" in readme

    assert "official_answer_citation_metric_first_run_v1" in measurements
    assert f"`{first_run['scored_count']}`" in measurements or f"scored_count={first_run['scored_count']}" in current_progress
    assert "PASS `8/29`" in measurements or "PASS=8" in current_progress
    assert "`CITATION_UNSUPPORTED=11`" in measurements or "CITATION_UNSUPPORTED=11" in current_progress
    assert "`PARTIAL_OR_UNSUPPORTED=10`" in measurements or "PARTIAL_OR_UNSUPPORTED=10" in current_progress
    assert "SCORED_BASELINE_PARTIAL" in current_progress
    assert "XLSX runtime candidate" in current_progress
    assert "PASS=26/29" in current_progress
    assert "XLSX=19/19" in current_progress
    assert "PDF table/value candidate" in current_progress
    assert "PASS=29/29" in current_progress
    assert "does not overwrite the official first-run baseline" in current_flat
    assert "expected answers/supporting evidence" in current_flat
    assert AGENTIC_RUN_ID in current_progress
    assert (
        report_artifact_repo_relative(AGENTIC_RUN_ID, "results.jsonl") in current_progress
        or "D:\\_external_runtime_artifacts\\async-ocr-rag-multimodal-pipeline\\rag-ingestion\\"
        in current_progress
    )


def test_agentic_loop_measurement_artifacts_are_separate_fail_closed_current_run() -> None:
    first_run = read_json(REPORT_DIR / "baseline_v1.json")
    input_config = read_json(REPORT_DIR / "metric_input_v1.json")
    summary = read_json(AGENTIC_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_RESULTS)
    measurement_doc = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_RUN_ID
    assert not any(
        event.get("run_id") == AGENTIC_RUN_ID
        and event.get("measurement_classification") == "official_next_run_measurement"
        for event in status_events
    )
    assert summary["baseline_reference"]["run_id"] == "official_answer_citation_metric_first_run_v1"
    assert summary["baseline_reference"]["status_detail"] == "SCORED_BASELINE_PARTIAL"
    assert summary["artifact_provenance"]["immutable_first_run_baseline_overwritten"] is False
    assert summary["artifact_provenance"]["report_only_candidates_promoted"] is False
    assert summary["denominator_count"] == 29
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert summary["validation"]["ok"] is True
    assert summary["pipeline_decision"]["registry_application_report_required"] is False
    assert summary["pipeline_decision"]["registry_application_fallback_used"] is True
    assert summary["artifact_paths"]["failure_attribution_json"] == report_artifact_repo_relative(
        AGENTIC_RUN_ID, "failure.json"
    )
    assert summary["agentic_loop"]["implemented"] is True
    assert summary["agentic_loop"]["enabled"] is True
    assert summary["agentic_loop"]["backend"] in {"legacy", "graph"}
    assert summary["non_production_rag_index_dependency"]["canonical_path"] == "ai/eval/indexes/rag-data"
    assert summary["non_production_rag_index_dependency"]["worker_relative_path"] == "eval/indexes/rag-data"
    assert summary["non_production_rag_index_dependency"]["production_index_path_used"] is False
    assert summary["non_production_rag_index_dependency"]["build_command"] == (
        "cd ai && AIPIPELINE_WORKER_RAG_FAISS_BUILD_DEVICE=cuda "
        "python -m scripts.build_rag_index --fixture all "
        "--index-version official-answer-citation-agentic-loop-v1-nonprod-fixture-all"
    )
    assert summary["non_production_rag_index_dependency"]["build_metadata"] == {
        "faiss_build_device_requested": "cuda",
        "faiss_gpu_count": 1,
        "faiss_gpu_device": 0,
        "faiss_gpu_used": True,
    }
    assert summary["infrastructure_blocker"]["model_quality_regression"] is False
    if summary["failure_counts"] == {"GENERATION_PIPELINE_UNAVAILABLE": 29}:
        assert summary["status"] == "BLOCKED_ACTUAL_GENERATION_PIPELINE_UNAVAILABLE"
        assert summary["measurement_classification"] == "diagnostic_actual_generation_blocked_pipeline_unavailable"
        assert summary["scored_count"] == 0
        assert summary["pass_count"] == 0
        assert summary["agentic_loop"]["executed"] is False
        assert summary["infrastructure_blocker"]["category"] == "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING"
    else:
        assert summary["status"] in {"PASS", "BLOCKED_OR_PARTIAL"}
        assert summary["measurement_classification"] == AGENTIC_DIAGNOSTIC_CLASSIFICATION
        assert summary["performance_interpretation"] == AGENTIC_DIAGNOSTIC_PERFORMANCE_INTERPRETATION
        assert summary["infrastructure_blocker"]["baseline_comparison_is_model_quality_comparable"] is False
        assert summary["corpus_coverage_verdict"]["verdict"] == (
            "fixture_all_index_not_official_denominator_representative"
        )
        assert summary["corpus_coverage_verdict"]["fixture_all_represents_official_mixed_denominator"] is False
        assert summary["corpus_coverage_verdict"]["official_denominator_source_bound_index"] is False
        assert summary["live_runner_verdict"]["current_run_uses_noop_llm"] is True
        assert summary["live_runner_verdict"]["generator"] == "ExtractiveGenerator"
        assert summary["live_runner_verdict"]["citation_locators_normalized_to_official_schema"] is False
        assert summary["diagnostic_limitations"]["chunk_only_citations_not_canonical_search_unit_payloads"] is True
        assert summary["diagnostic_limitations"]["current_pass_is_final_model_quality_regression"] is False
        assert summary["diagnostic_limitations"]["current_pass_is_promotion_evidence"] is False
        assert summary["source_bound_official_denominator_index_design"]["entrypoint_implemented"] is True
        assert summary["source_bound_official_denominator_index_design"]["blocker_category"] == SOURCE_BOUND_INDEX_BLOCKER
        assert summary["source_bound_official_denominator_index_design"]["build_ready"] is False
        assert summary["source_bound_official_denominator_index_design"]["target_index_built"] is False
        assert summary["source_bound_official_denominator_index_design"]["load_check_passed"] is False
        assert summary["source_bound_official_denominator_index_design"]["rerun_allowed"] is False
        assert summary["source_bound_official_denominator_index_design"]["production_index_path_used"] is False
        assert summary["source_bound_official_denominator_index_design"]["candidate_artifacts_as_generation_source"] is False
        assert summary["agentic_loop"]["actual_generation_pipeline_available"] is True
        assert summary["agentic_loop"]["executed"] is True
        assert "GENERATION_PIPELINE_UNAVAILABLE" not in summary["failure_counts"]
        assert all(
            row["generated_answer"] or row["generated_citations"] or row["failure_category"] != "GENERATION_PIPELINE_UNAVAILABLE"
            for row in results
        )
    assert summary["local_llm_used"] is False
    assert summary["local_gpu_used"] is True
    assert summary["guardrails"]["promotion_evidence"] is False
    assert summary["guardrails"]["generation_used_expected_answer"] is False
    assert summary["guardrails"]["generation_used_supporting_evidence"] is False
    assert summary["guardrails"]["denominator_mutation"] is False
    assert summary["guardrails"]["gold_mutation"] is False
    assert summary["guardrails"]["production_mutation"] is False
    assert summary["comparison_to_baseline"]["pass_delta"] == -7
    assert summary["comparison_to_baseline"]["per_track_pass_delta"] == {
        "pdf_business_ocr_mm": 0,
        "text_namu_v2_1": -6,
        "xlsx_business_structured": -1,
    }

    official_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert len(results) == 29
    assert {row["query_id"] for row in results} == official_query_ids
    assert all(row["run_id"] == AGENTIC_RUN_ID for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all(row["agentic_loop_enabled"] is True for row in results)
    assert all(row["local_llm_used"] is False for row in results)
    assert all(row["local_gpu_used"] is True for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert all(
        "pdf_answer_citation_table_value_candidate" not in json.dumps(row, ensure_ascii=False)
        for row in results
    )
    assert all("table_value_candidate" not in json.dumps(row, ensure_ascii=False) for row in results)
    assert all("pdf_candidate" not in json.dumps(row, ensure_ascii=False) for row in results)
    if summary["failure_counts"] == {"GENERATION_PIPELINE_UNAVAILABLE": 29}:
        assert all(row["agentic_loop_executed"] is False for row in results)
        assert all(row["failure_category"] == "GENERATION_PIPELINE_UNAVAILABLE" for row in results)
        assert all(row["infrastructure_blocker_category"] == "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING" for row in results)
    else:
        assert any(row["agentic_loop_executed"] is True for row in results)
        assert all(row["failure_category"] != "GENERATION_PIPELINE_UNAVAILABLE" for row in results)

    assert "official_answer_citation_agentic_loop_run_v1" in measurement_doc
    assert "diagnostic live-generation" in measurement_doc
    assert "fixture-all/noop/chunk-only" in measurement_doc
    assert "promotion_evidence=false" in measurement_doc
    latest = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_RUN_ID
    )
    assert latest["event_type"] == "official_answer_citation_agentic_loop_measurement"
    assert latest["run_id"] == AGENTIC_RUN_ID
    assert latest["result_count"] == 29
    assert latest["unique_query_id_count"] == 29
    assert latest["pass_count"] == summary["pass_count"]
    assert latest["measurement_classification"] == AGENTIC_DIAGNOSTIC_CLASSIFICATION
    assert latest["performance_interpretation"] == AGENTIC_DIAGNOSTIC_PERFORMANCE_INTERPRETATION
    assert latest["infrastructure_blocker"]["baseline_comparison_is_model_quality_comparable"] is False
    assert latest["source_bound_official_denominator_index_design"]["blocker_category"] == SOURCE_BOUND_INDEX_BLOCKER
    assert latest["non_production_rag_index_dependency"]["build_metadata"]["faiss_gpu_used"] is True
    assert latest["promotion_evidence"] is False
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }


def test_agentic_loop_failure_attribution_locks_diagnostic_interpretation() -> None:
    summary = read_json(AGENTIC_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_RESULTS)
    attribution = read_json(AGENTIC_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert attribution["run_id"] == AGENTIC_RUN_ID
    assert attribution["measurement_result"] == {
        "rows": 29,
        "unique_query_ids": 29,
        "scored_count": 29,
        "PASS": 1,
        "CITATION_UNSUPPORTED": 25,
        "PARTIAL_OR_UNSUPPORTED": 3,
    }
    assert attribution["performance_interpretation"] == (
        "diagnostic_retrieval_agent_loop_not_final_answer_generation_quality"
    )
    assert attribution["measurement_classification"] == (
        "diagnostic_live_generation_fixture_all_index_not_official_denominator_representative"
    )
    assert attribution["corpus_coverage_verdict"]["fixture_all_represents_official_mixed_denominator"] is False
    assert attribution["corpus_coverage_verdict"]["official_denominator_source_bound_index"] is False
    assert attribution["corpus_coverage_verdict"]["index_path"] == "ai/eval/indexes/rag-data"
    assert attribution["corpus_coverage_verdict"]["production_index_path_used"] is False
    assert attribution["corpus_coverage_verdict"]["candidate_index_path_used"] is False
    assert attribution["live_runner_verdict"]["canonical_live_generation_runner_available"] is False
    assert attribution["live_runner_verdict"]["current_run_uses_noop_llm"] is True
    assert attribution["live_runner_verdict"]["local_llm_backend_available"] is False
    assert attribution["live_runner_verdict"]["generator"] == "ExtractiveGenerator"
    assert attribution["structured_adapter_wiring_verdict"]["xlsx_candidate_adapter_wired_into_live_path"] is False
    assert attribution["structured_adapter_wiring_verdict"]["pdf_candidate_adapter_wired_into_live_path"] is False
    assert attribution["guardrails"]["promotion_evidence"] is False
    assert attribution["guardrails"]["generation_used_expected_answer"] is False
    assert attribution["guardrails"]["generation_used_supporting_evidence"] is False
    assert attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["measurement_classification"] == attribution["measurement_classification"]
    assert summary["performance_interpretation"] == attribution["performance_interpretation"]
    assert summary["infrastructure_blocker"]["baseline_comparison_is_model_quality_comparable"] is False

    design = attribution["source_bound_official_denominator_index_design"]
    assert design["status"] == "implemented_fail_closed_source_metadata_missing_or_unchecked"
    assert design["blocker_category"] == SOURCE_BOUND_INDEX_BLOCKER
    assert design["target_index_path"] == "ai/eval/indexes/rag-data-official-denominator-v1"
    assert design["entrypoint_implemented"] is True
    assert design["build_ready"] is False
    assert design["target_index_built"] is False
    assert design["load_check_passed"] is False
    assert design["rerun_allowed"] is False
    assert design["production_index_path_used"] is False
    assert design["candidate_index_path_used"] is False
    assert design["candidate_artifacts_as_generation_source"] is False
    assert design["required_fields_by_track"]["text_namu_v2_1"] == [
        "document_id",
        "document_version_id",
        "search_unit_id",
        "text_locator",
    ]
    assert "workbook" in design["required_fields_by_track"]["xlsx_business_structured"]
    assert "bbox" in design["required_fields_by_track"]["pdf_business_ocr_mm"]

    rows = attribution["row_level_attribution"]
    assert len(rows) == 29
    assert {row["query_id"] for row in rows} == {row["query_id"] for row in results}
    assert all(row["primary_attribution"] in ALLOWED_AGENTIC_ATTRIBUTION_CATEGORIES for row in rows)
    assert all(
        set(row["secondary_attributions"]).issubset(ALLOWED_AGENTIC_ATTRIBUTION_CATEGORIES)
        for row in rows
    )
    assert all(row["generation_used_expected_answer"] is False for row in rows)
    assert all(row["generation_used_supporting_evidence"] is False for row in rows)
    assert all(row["generated_answer_present"] is True for row in rows)
    assert all(row["generated_citations_present"] is True for row in rows)
    assert all(row["citation_payload_points_to_retrieved_evidence"] is True for row in rows)
    assert all(row["citation_locator_scorer_compatible"] is False for row in rows)
    assert all(row["retrieved_source_matches_expected_official_source_family"] is False for row in rows)
    assert all(row["llm_backend_noop_limitation"] is True for row in rows)

    assert attribution["primary_attribution_counts"] == {
        "CORPUS_COVERAGE_MISS": 6,
        "SCORER_COMPATIBILITY_MISMATCH": 1,
        "STRUCTURED_ADAPTER_NOT_WIRED": 22,
    }
    assert attribution["per_track_primary_attribution_counts"] == {
        "pdf_business_ocr_mm": {
            "SCORER_COMPATIBILITY_MISMATCH": 1,
            "STRUCTURED_ADAPTER_NOT_WIRED": 3,
        },
        "text_namu_v2_1": {"CORPUS_COVERAGE_MISS": 6},
        "xlsx_business_structured": {"STRUCTURED_ADAPTER_NOT_WIRED": 19},
    }

    latest = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_failure_attribution"
        and event.get("run_id") == AGENTIC_RUN_ID
    )
    assert latest["run_id"] == AGENTIC_RUN_ID
    assert latest["measurement_classification"] == attribution["measurement_classification"]
    assert latest["performance_interpretation"] == attribution["performance_interpretation"]
    assert latest["primary_attribution_counts"] == attribution["primary_attribution_counts"]
    assert latest["baseline_comparison_is_model_quality_comparable"] is False
    assert latest["source_bound_official_denominator_index_design"]["blocker_category"] == SOURCE_BOUND_INDEX_BLOCKER
    assert latest["guardrails"]["promotion_evidence"] is False
    assert summary["artifact_provenance"]["report_only_candidates_promoted"] is False


def test_source_bound_readiness_artifact_records_build_and_load_check_passed() -> None:
    readiness = read_json(READINESS_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert readiness["entrypoint_implemented"] is True
    assert readiness["status"] == "BUILD_READY_LOAD_CHECK_PASSED"
    assert readiness["blocker_category"] is None
    assert readiness["target_index_path"] == "ai/eval/indexes/rag-data-official-denominator-v1"
    assert readiness["index_version"] == (
        "official-answer-citation-agentic-loop-v1-nonprod-official-denominator-source-bound"
    )
    assert readiness["official_denominator_rows"] == 29
    assert readiness["official_rows_by_track"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
    }
    assert readiness["blocked_query_ids"] == []
    assert readiness["missing_fields_by_query_id"] == {}
    assert readiness["missing_source_files_by_query_id"] == {}
    assert readiness["source_bound_locators_by_query_id"]["text_namu_v2_0005"][
        "text_locator"
    ]["source_corpus_path"] == "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl"
    assert readiness["source_bound_locators_by_query_id"]["gq_auto_012"]["row_label"] == (
        "대중교통구분=지하철 | 노선명=5호선 | 년월=201902"
    )
    assert readiness["source_bound_locators_by_query_id"]["gq_auto_012"][
        "target_column"
    ] == "승차총승객수"
    assert readiness["source_bound_locators_by_query_id"]["gq_auto_012"][
        "normalized_value"
    ] == "15446522"
    assert readiness["source_file_inventory_by_query_id"]["gq_auto_012"][0]["exists"] is True
    pdf_inventory = readiness["source_file_inventory_by_query_id"]["gq_auto_010"][0]
    assert pdf_inventory["exists"] is True
    assert pdf_inventory["kind"] == "pdf_locator_manifest"
    assert pdf_inventory["reference"] == "2847f7af-cfe4-41de-8393-58912df2dba9"
    assert pdf_inventory["document_version_id"] == "docv_fe2470815512a395"
    assert pdf_inventory["search_unit_id"] == "7bf516bf-2a17-4303-86d8-3cffaa04846e"
    assert pdf_inventory["source_pdf_path_resolved"] is True
    assert "D:/_external_runtime_artifacts/" in pdf_inventory["source_path"]
    pdf_locator = readiness["source_bound_locators_by_query_id"]["gq_auto_010"]
    assert pdf_locator["source_pdf_path"].endswith("2021_03_recent_economic_trends.pdf")
    assert pdf_locator["document_version_id"] == "docv_fe2470815512a395"
    assert pdf_locator["row_label"] == "▪ 실업률은 모든 연령계층에서 상승"
    assert pdf_locator["target_column"] == "paragraph_text"
    assert pdf_locator["pdf_source_text_locator"]["method"] == "pymupdf_source_pdf_text"
    assert "D:/_external_runtime_artifacts/" in pdf_locator["source_locator_manifest_path"]
    assert "D:/_external_runtime_artifacts/" in "\n".join(readiness["source_roots_checked"])
    assert "D:/_external_workspace_archive/" in "\n".join(readiness["source_roots_checked"])
    assert readiness["build_ready"] is True
    assert readiness["target_index_built"] is True
    assert readiness["load_check_passed"] is True
    assert readiness["rerun_allowed"] is True
    assert readiness["index_build_result"]["official_denominator_rows"] == 29
    assert readiness["index_load_check"]["passed"] is True
    assert readiness["index_load_check"]["track_counts"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert readiness["candidate_artifacts_as_generation_source"] is False
    assert readiness["generation_used_expected_answer"] is False
    assert readiness["generation_used_supporting_evidence"] is False
    assert readiness["production_index_path_used"] is False
    assert readiness["candidate_index_path_used"] is False
    assert readiness["promotion_evidence"] is False

    assert set(readiness["required_fields_by_track"]["text_namu_v2_1"]) == {
        "document_id",
        "document_version_id",
        "search_unit_id",
        "text_locator",
    }
    assert readiness["required_fields_by_track"]["xlsx_business_structured"] == [
        "workbook",
        "sheet",
        "range",
        "cell",
        "row_label",
        "target_column",
        "normalized_value",
        "search_unit_id",
        "document_version_id",
    ]
    assert readiness["required_fields_by_track"]["pdf_business_ocr_mm"] == [
        "source_pdf_path",
        "page",
        "physical_page_index",
        "bbox",
        "region_type",
        "row_label",
        "target_column",
        "search_unit_id",
        "document_version_id",
    ]

    latest = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_source_bound_index_preparation"
    )
    assert latest["source_bound_official_denominator_index_design"]["entrypoint_implemented"] is True
    assert latest["source_bound_official_denominator_index_design"]["blocker_category"] is None
    assert latest["source_bound_official_denominator_index_design"]["blocked_query_count"] == 0
    assert latest["source_bound_official_denominator_index_design"]["required_field_complete_counts"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert latest["source_bound_official_denominator_index_design"]["source_identity_resolved_counts"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert latest["source_bound_official_denominator_index_design"]["missing_fields_by_query_id"] == {}
    assert latest["source_bound_official_denominator_index_design"]["missing_source_files_by_query_id"] == {}
    assert latest["source_bound_official_denominator_index_design"]["target_index_built"] is True
    assert latest["source_bound_official_denominator_index_design"]["load_check_passed"] is True
    assert latest["source_bound_official_denominator_index_design"]["rerun_allowed"] is True
    assert latest["search_unit_citation_payload_wired"] is True
    assert latest["xlsx_source_bound_adapter_opt_in_wired"] is True
    assert latest["pdf_source_bound_adapter_opt_in_wired"] is True
    assert latest["guardrails"]["gold_mutation"] is False
    assert latest["guardrails"]["denominator_mutation"] is False
    assert latest["guardrails"]["production_mutation"] is False


def test_v2_source_bound_diagnostic_artifacts_are_separate_and_guarded() -> None:
    summary = read_json(AGENTIC_V2_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V2_RESULTS)
    attribution = read_json(AGENTIC_V2_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V2_RUN_ID
    assert summary["status"] == "BLOCKED_OR_PARTIAL"
    assert summary["diagnostic_only"] is True
    assert summary["llm_backend"] == "noop"
    assert "noop/extractive" in summary["llm_backend_limitation"]
    assert summary["artifact_provenance"]["immutable_first_run_baseline_overwritten"] is False
    assert summary["artifact_provenance"]["report_only_candidates_promoted"] is False
    assert summary["artifact_provenance"]["run_id_separate_from_first_run"] is True
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert summary["scored_count"] == 20
    assert summary["pass_count"] == 20
    assert summary["failure_counts"] == {
        "PASS": 20,
        "SEARCH_UNIT_LOCATOR_INCOMPLETE": 5,
        "STRUCTURED_LOCATOR_DROPPED": 4,
    }
    assert summary["measurement_classification"] == AGENTIC_V2_RUN_ID
    assert summary["performance_interpretation"] == "source_bound_official_denominator_backend_limited_diagnostic"
    assert summary["source_bound_index_used"] is True
    assert summary["non_production_rag_index_dependency"]["canonical_path"] == (
        "ai/eval/indexes/rag-data-official-denominator-v1"
    )
    assert summary["non_production_rag_index_dependency"]["worker_relative_path"] == (
        "eval/indexes/rag-data-official-denominator-v1"
    )
    assert summary["non_production_rag_index_dependency"]["preflight_errors"] == []
    assert summary["non_production_rag_index_dependency"]["source_bound_artifact_contract_ok"] is True
    assert summary["non_production_rag_index_dependency"]["source_bound_index_load_checked"] is True
    assert summary["non_production_rag_index_dependency"]["satisfied"] is True
    assert summary["non_production_rag_index_dependency"]["rerun_allowed"] is True
    assert summary["non_production_rag_index_dependency"]["candidate_index_path_used"] is False
    assert summary["non_production_rag_index_dependency"]["production_index_path_used"] is False
    assert summary["non_production_rag_index_dependency"]["search_unit_manifest_metadata"] == {
        "all_source_bound": True,
        "row_count": 29,
        "track_counts": {
            "pdf_business_ocr_mm": 4,
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
        },
        "unique_query_id_count": 29,
        "unique_search_unit_id_count": 29,
    }
    assert summary["non_production_rag_index_dependency"]["readiness_artifact"] == {
        "blocked_query_ids": [],
        "load_check_passed": True,
        "missing_fields_by_query_id": {},
        "missing_source_files_by_query_id": {},
        "official_denominator_rows": 29,
        "official_rows_by_track": {
            "pdf_business_ocr_mm": 4,
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
        },
        "path": "ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json",
        "rerun_allowed": True,
        "status": "BUILD_READY_LOAD_CHECK_PASSED",
        "target_index_built": True,
        "target_index_path": "ai/eval/indexes/rag-data-official-denominator-v1",
    }
    assert summary["canonical_search_unit_payload_used"] is True
    assert summary["search_unit_citation_payloads_used"] is True
    assert summary["xlsx_pdf_structured_adapters_enabled"] is True
    assert summary["adapter_output_from_source_bound_search_units"] is False
    assert summary["candidate_artifacts_as_generation_source"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["promotion_evidence"] is False
    assert summary["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["official_score_category_counts"]["PASS"] == summary["pass_count"]
    assert summary["official_score_category_counts"] == {
        "PASS": 20,
        "CITATION_UNSUPPORTED": 0,
        "PARTIAL_OR_UNSUPPORTED": 0,
    }
    assert summary["per_track_counts"] == {
        "pdf_business_ocr_mm": {
            "failure_counts": {"STRUCTURED_LOCATOR_DROPPED": 4},
            "pass_count": 0,
            "row_count": 4,
            "scored_count": 0,
        },
        "text_namu_v2_1": {
            "failure_counts": {"PASS": 1, "SEARCH_UNIT_LOCATOR_INCOMPLETE": 5},
            "pass_count": 1,
            "row_count": 6,
            "scored_count": 1,
        },
        "xlsx_business_structured": {
            "failure_counts": {"PASS": 19},
            "pass_count": 19,
            "row_count": 19,
            "scored_count": 19,
        },
    }

    assert len(results) == 29
    assert len({row["query_id"] for row in results}) == 29
    assert Counter(row["track"] for row in results) == Counter(
        {"xlsx_business_structured": 19, "text_namu_v2_1": 6, "pdf_business_ocr_mm": 4}
    )
    assert Counter(row["failure_category"] for row in results) == Counter(
        {"PASS": 20, "SEARCH_UNIT_LOCATOR_INCOMPLETE": 5, "STRUCTURED_LOCATOR_DROPPED": 4}
    )
    assert Counter(row["score_status"] for row in results) == Counter({"PASS": 20, "FAIL_CLOSED": 9})
    assert all(row["run_id"] == AGENTIC_V2_RUN_ID for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["search_unit_citation_payloads_used"] is True for row in results)
    assert all(row["structured_source_bound_adapters_enabled"] is True for row in results)
    assert any(
        citation.get("structured_adapter_output_from_source_bound_search_unit") is True
        for row in results
        for citation in row["generated_citations"]
    )
    assert not all(
        any(citation.get("structured_adapter_output_from_source_bound_search_unit") is True for citation in row["generated_citations"])
        for row in results
    )

    assert attribution["run_id"] == AGENTIC_V2_RUN_ID
    assert attribution["source_bound_index_used"] is True
    assert attribution["canonical_search_unit_payload_used"] is True
    assert attribution["adapter_output_from_source_bound_search_units"] is False
    assert attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert attribution["primary_attribution_counts"] == {"CITATION_PAYLOAD_SCHEMA_MISMATCH": 9, "PASS": 20}
    assert attribution["per_track_primary_attribution_counts"] == {
        "pdf_business_ocr_mm": {"CITATION_PAYLOAD_SCHEMA_MISMATCH": 4},
        "text_namu_v2_1": {"CITATION_PAYLOAD_SCHEMA_MISMATCH": 5, "PASS": 1},
        "xlsx_business_structured": {"PASS": 19},
    }
    assert set(attribution["primary_attribution_counts"]).issubset(ALLOWED_V2_ATTRIBUTION_CATEGORIES)
    assert all(
        row["primary_attribution"] in ALLOWED_V2_ATTRIBUTION_CATEGORIES
        for row in attribution["row_level_attribution"]
    )
    assert all(
        row["generation_used_expected_answer"] is False
        and row["generation_used_supporting_evidence"] is False
        and row["generation_used_gold_fields"] is False
        and row["promotion_evidence"] is False
        for row in attribution["row_level_attribution"]
    )

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V2_RUN_ID
    )
    assert measurement["source_bound_index_used"] is True
    assert measurement["candidate_artifacts_as_generation_source"] is False
    assert measurement["generation_used_expected_answer"] is False
    assert measurement["generation_used_supporting_evidence"] is False
    assert measurement["generation_used_gold_fields"] is False
    assert measurement["promotion_evidence"] is False
    assert measurement["baseline_comparison_is_model_quality_comparable"] is False
    assert measurement["result_count"] == 29
    assert measurement["unique_query_id_count"] == 29
    assert measurement["scored_count"] == 20
    assert measurement["pass_count"] == 20
    assert measurement["adapter_output_from_source_bound_search_units"] is False

    failure_attribution = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_failure_attribution"
        and event.get("run_id") == AGENTIC_V2_RUN_ID
    )
    assert failure_attribution["primary_attribution_counts"] == {
        "CITATION_PAYLOAD_SCHEMA_MISMATCH": 9,
        "PASS": 20,
    }
    assert failure_attribution["source_bound_index_used"] is True
    assert failure_attribution["canonical_search_unit_payload_used"] is True
    assert failure_attribution["adapter_output_from_source_bound_search_units"] is False
    assert failure_attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert failure_attribution["guardrails"]["promotion_evidence"] is False


def test_v2_1_citation_contract_repair_artifacts_discard_off_track_citations() -> None:
    summary = read_json(AGENTIC_V2_1_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V2_1_RESULTS)
    attribution = read_json(AGENTIC_V2_1_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    assert summary["run_id"] == AGENTIC_V2_1_RUN_ID
    assert summary["measurement_classification"] == AGENTIC_V2_1_RUN_ID
    assert summary["status"] == "BLOCKED_OR_PARTIAL"
    assert summary["diagnostic_only"] is True
    assert summary["llm_backend"] == "noop"
    assert summary["source_bound_index_used"] is True
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert summary["scored_count"] == 29
    assert summary["pass_count"] == 28
    assert summary["failure_counts"] == {
        "PARTIAL_OR_UNSUPPORTED": 1,
        "PASS": 28,
    }
    assert summary["discarded_off_track_citation_count"] == 20
    assert summary["same_track_valid_citation_count"] == 125
    assert summary["query_bound_scored_citation_count"] == 29
    assert summary["non_query_bound_same_track_scored_citation_count"] == 96
    assert summary["schema_mismatch_residual_count"] == 0
    assert summary["all_generated_citations_source_bound"] is True
    assert summary["same_track_generated_citations_source_bound"] is True
    assert summary["scored_citations_source_bound"] is True
    assert summary["adapter_output_for_same_track_citations"] is True
    assert summary["adapter_output_from_source_bound_search_units"] is True
    assert summary["candidate_artifacts_as_generation_source"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["promotion_evidence"] is False
    assert summary["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["per_track_counts"] == {
        "pdf_business_ocr_mm": {
            "failure_counts": {"PASS": 4},
            "pass_count": 4,
            "row_count": 4,
            "scored_count": 4,
        },
        "text_namu_v2_1": {
            "failure_counts": {"PARTIAL_OR_UNSUPPORTED": 1, "PASS": 5},
            "pass_count": 5,
            "row_count": 6,
            "scored_count": 6,
        },
        "xlsx_business_structured": {
            "failure_counts": {"PASS": 19},
            "pass_count": 19,
            "row_count": 19,
            "scored_count": 19,
        },
    }

    assert len(results) == 29
    assert all(row["run_id"] == AGENTIC_V2_1_RUN_ID for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["same_track_valid_citation_count"] > 0 for row in results)
    assert all(row["schema_mismatch_residual_count"] == 0 for row in results)
    assert not any(
        "#xlsx_business_structured" in row["generated_answer"]
        for row in results
        if row["track"] != "xlsx_business_structured"
    )
    assert all(
        citation["citation_payload_validation"]["manifest_track"] == row["track"]
        for row in results
        for citation in row["scored_citations"]
    )
    assert all(
        citation["citation_payload_validation"]["category"] == "OFF_TRACK_CITATION_FOR_QUERY_TRACK"
        for row in results
        for citation in row["discarded_off_track_citations"]
    )
    assert sum(row["discarded_off_track_citation_count"] for row in results) == 20
    assert any(row["discarded_off_track_citation_count"] > 0 for row in results if row["track"] == "pdf_business_ocr_mm")
    assert any(row["discarded_off_track_citation_count"] > 0 for row in results if row["track"] == "text_namu_v2_1")
    assert not any(
        citation["search_unit_citation_payload"]["track"] != row["track"]
        for row in results
        for citation in row["scored_citations"]
    )
    assert all(
        citation["search_unit_citation_payload"]["manifest_query_id"]
        == citation["citation_payload_validation"]["manifest_query_id"]
        for row in results
        for citation in row["generated_citations"]
    )
    assert all(
        citation["citation_payload_validation"]["row_query_id"] == row["query_id"]
        for row in results
        for citation in row["generated_citations"]
    )

    assert attribution["run_id"] == AGENTIC_V2_1_RUN_ID
    assert attribution["source_bound_index_used"] is True
    assert attribution["canonical_search_unit_payload_used"] is True
    assert attribution["discarded_off_track_citation_count"] == 20
    assert attribution["same_track_valid_citation_count"] == 125
    assert attribution["query_bound_scored_citation_count"] == 29
    assert attribution["non_query_bound_same_track_scored_citation_count"] == 96
    assert attribution["schema_mismatch_residual_count"] == 0
    assert attribution["primary_attribution_counts"] == {"ANSWER_SYNTHESIS_LIMITATION": 1, "PASS": 28}
    assert attribution["per_track_primary_attribution_counts"] == {
        "pdf_business_ocr_mm": {"PASS": 4},
        "text_namu_v2_1": {"ANSWER_SYNTHESIS_LIMITATION": 1, "PASS": 5},
        "xlsx_business_structured": {"PASS": 19},
    }
    residual_audit = attribution["residual_failure_audit"]
    assert residual_audit["scope"] == "v2_1_residual_failures_only"
    assert set(residual_audit["target_query_ids"]) == RESIDUAL_AUDIT_QUERY_IDS
    assert set(residual_audit["audited_query_ids"]) == RESIDUAL_AUDIT_QUERY_IDS
    assert residual_audit["non_target_audited_query_ids"] == []
    assert residual_audit["llm_backend_validation_started"] is False
    assert residual_audit["llm_backend_validation_readiness"] == (
        "READY_FOR_LLM_BACKEND_VALIDATION_RESIDUALS_CONFIRMED_AS_SYNTHESIS"
    )
    assert residual_audit["schema_mismatch_residual_count"] == 0
    assert residual_audit["schema_mismatch_residual_count"] == summary["schema_mismatch_residual_count"]
    assert residual_audit["candidate_artifacts_as_generation_source"] is False
    assert residual_audit["expected_supporting_gold_used_for_audit_only"] is True
    assert residual_audit["generation_used_expected_answer"] is False
    assert residual_audit["generation_used_supporting_evidence"] is False
    assert residual_audit["generation_used_gold_fields"] is False
    assert residual_audit["promotion_evidence"] is False
    assert residual_audit["refined_primary_attribution_counts"] == {
        "ANSWER_SYNTHESIS_LIMITATION": 1,
        "PASS": 2,
    }
    assert residual_audit["counts"] == {
        "answer_synthesis_limitation_confirmed": 1,
        "deterministic_extractive_answer_missing_value": 3,
        "query_bound_evidence_contains_answer": 3,
        "query_bound_evidence_contains_citation_support": 3,
        "query_bound_evidence_gap": 0,
        "same_track_non_query_bound_distracted": 1,
        "same_track_non_query_bound_helped": 0,
        "scorer_normalization_issue_possible": 0,
    }
    assert "gq_auto_010" not in residual_audit["audited_query_ids"]
    assert "gq_auto_024" not in residual_audit["audited_query_ids"]

    audit_rows = {row["query_id"]: row for row in residual_audit["rows"]}
    expected_counts = {
        "gq_auto_030": (1, 1, 2, "PASS"),
        "gq_pdf_section_question_001": (1, 1, 2, "PASS"),
        "text_namu_v2_0017": (1, 2, 3, "ANSWER_SYNTHESIS_LIMITATION"),
    }
    results_by_id = {row["query_id"]: row for row in results}
    failed_ids = {row["query_id"] for row in results if row["failure_category"] != "PASS"}
    assert failed_ids == {"text_namu_v2_0017"}
    for query_id, (query_bound, non_query_bound, same_track, refined) in expected_counts.items():
        row = results_by_id[query_id]
        audit_row = audit_rows[query_id]
        assert row["query_bound_scored_citation_count"] == query_bound
        assert row["non_query_bound_same_track_scored_citation_count"] == non_query_bound
        assert row["same_track_valid_citation_count"] == same_track
        assert row["schema_mismatch_residual_count"] == 0
        assert audit_row["query_bound_scored_citation_count"] == query_bound
        assert audit_row["non_query_bound_same_track_scored_citation_count"] == non_query_bound
        assert audit_row["same_track_valid_citation_count"] == same_track
        assert audit_row["refined_primary_attribution"] == refined
        assert audit_row["generation_used_expected_answer"] is False
        assert audit_row["generation_used_supporting_evidence"] is False
        assert audit_row["generation_used_gold_fields"] is False
        assert audit_row["candidate_artifacts_as_generation_source"] is False
        assert audit_row["audit_comparison_only"] is True

    auto_query_bound_text = " ".join(
        citation["citation_text"]
        for citation in results_by_id["gq_auto_030"]["scored_citations"]
        if citation["citation_payload_validation"]["manifest_query_id"] == "gq_auto_030"
    )
    assert "2020" in auto_query_bound_text
    assert "1,088.0" in auto_query_bound_text
    assert audit_rows["gq_auto_030"]["query_bound_evidence_contains_answer"] is True
    assert audit_rows["gq_auto_030"]["query_bound_evidence_contains_citation_support"] is True
    assert audit_rows["gq_auto_030"]["same_track_non_query_bound_evidence_helped_or_distracted"] == "neutral"
    assert audit_rows["gq_auto_030"]["answer_synthesis_limitation_confirmed"] is False
    table_query_bound_text = " ".join(
        citation["citation_text"]
        for citation in results_by_id["gq_pdf_section_question_001"]["scored_citations"]
        if citation["citation_payload_validation"]["manifest_query_id"] == "gq_pdf_section_question_001"
    )
    assert "2024" in table_query_bound_text
    assert "518.4" in table_query_bound_text
    assert audit_rows["gq_pdf_section_question_001"]["query_bound_evidence_contains_answer"] is True
    assert audit_rows["gq_pdf_section_question_001"]["query_bound_evidence_contains_citation_support"] is True
    assert audit_rows["gq_pdf_section_question_001"]["same_track_non_query_bound_evidence_helped_or_distracted"] == "neutral"
    assert audit_rows["gq_pdf_section_question_001"]["scorer_normalization_issue_possible"] is False
    assert audit_rows["text_namu_v2_0017"]["query_bound_evidence_contains_answer"] is True
    assert audit_rows["text_namu_v2_0017"]["query_bound_evidence_contains_citation_support"] is True
    assert audit_rows["text_namu_v2_0017"]["same_track_non_query_bound_evidence_helped_or_distracted"] == "distracted"
    assert audit_rows["text_namu_v2_0017"]["answer_synthesis_limitation_confirmed"] is True
    assert attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert attribution["guardrails"]["promotion_evidence"] is False

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V2_1_RUN_ID
    )
    assert measurement["discarded_off_track_citation_count"] == 20
    assert measurement["same_track_valid_citation_count"] == 125
    assert measurement["query_bound_scored_citation_count"] == 29
    assert measurement["non_query_bound_same_track_scored_citation_count"] == 96
    assert measurement["schema_mismatch_residual_count"] == 0
    assert measurement["candidate_artifacts_as_generation_source"] is False
    assert measurement["generation_used_expected_answer"] is False
    assert measurement["generation_used_supporting_evidence"] is False
    assert measurement["generation_used_gold_fields"] is False
    assert measurement["promotion_evidence"] is False
    assert measurement["residual_failure_audit"]["audited_row_count"] == 3
    assert measurement["residual_failure_audit"]["promotion_evidence"] is False
    failure_attribution_event = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_failure_attribution"
        and event.get("run_id") == AGENTIC_V2_1_RUN_ID
    )
    assert failure_attribution_event["residual_failure_audit"]["audited_row_count"] == 3
    preflight = runner.v2_1_artifact_consistency_preflight(
        summary=summary,
        attribution=attribution,
        rows=results,
        status_events=status_events,
    )
    assert preflight["ok"] is True
    assert preflight["failure_bucket"] is None
    assert preflight["pass_count"] == 28
    assert preflight["per_track_pass_count"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 5,
        "xlsx_business_structured": 19,
    }
    assert preflight["remaining_failure_query_ids"] == ["text_namu_v2_0017"]
    assert preflight["answer_synthesis_limitation_query_ids"] == ["text_namu_v2_0017"]
    assert preflight["query_bound_evidence_gap_count"] == 0
    assert preflight["schema_mismatch_residual_count"] == 0
    assert preflight["promotion_evidence"] is False
    assert preflight["readiness"] == "READY_FOR_LLM_BACKEND_VALIDATION_RESIDUALS_CONFIRMED_AS_SYNTHESIS"
    unexpected_residual_reports = [
        path.name
            for path in REPORT_DIR.iterdir()
            if "residual" in path.name and path.suffix in {".json", ".md"}
            and not path.name.startswith(f"{AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}_")
            and not path.name.startswith(f"{AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID}_")
            and not path.name.startswith(f"{AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID}_")
            and not path.name.startswith(f"{AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID}_")
        ]
    assert unexpected_residual_reports == []
    assert "source-bound denominator index" in summary["pipeline_decision"]["rationale"]
    assert "registry-backed RAG pipeline" not in summary["pipeline_decision"]["rationale"]


def test_v2_2_llm_backend_validation_artifact_is_diagnostic_only() -> None:
    summary = read_json(AGENTIC_V2_2_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V2_2_RESULTS)
    attribution = read_json(AGENTIC_V2_2_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V2_2_RUN_ID
    assert summary["measurement_classification"] == AGENTIC_V2_2_RUN_ID
    assert summary["diagnostic_only"] is True
    assert summary["promotion_evidence"] is False
    assert summary["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["source_bound_index_used"] is True
    assert summary["canonical_search_unit_payload_used"] is True
    assert summary["prompt_context_source_bound_only"] is True
    assert summary["candidate_artifacts_as_generation_source"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["v2_1_artifact_consistency_preflight"]["ok"] is True
    assert summary["v2_1_artifact_consistency_preflight"]["pass_count"] == 28
    assert summary["v2_1_artifact_consistency_preflight"]["query_bound_evidence_gap_count"] == 0
    assert summary["v2_1_artifact_consistency_preflight"]["schema_mismatch_residual_count"] == 0
    assert summary["result_count"] == 29
    assert len(results) == 29
    assert all(row["run_id"] == AGENTIC_V2_2_RUN_ID for row in results)
    assert all(row["diagnostic_only"] is True for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["prompt_context_source_bound_only"] is True for row in results)
    assert all(row["candidate_artifacts_as_generation_source"] is False for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all(
        "pdf_answer_citation_table_value_candidate" not in json.dumps(row, ensure_ascii=False)
        for row in results
    )
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert attribution["run_id"] == AGENTIC_V2_2_RUN_ID
    assert attribution["promotion_evidence"] is False
    assert attribution["v2_1_artifact_consistency_preflight"]["ok"] is True

    bucket_counts = summary["validation_bucket_counts"]
    if summary["llm_backend_validation_status"] == "LLM_BACKEND_UNAVAILABLE_FAIL_CLOSED":
        assert summary["real_llm_backend_used"] is False
        assert summary["local_llm_used"] is False
        assert summary["llm_backend"] != "noop"
        assert bucket_counts == {"LLM_BACKEND_UNAVAILABLE": 29}
        assert all(row["validation_bucket"] == "LLM_BACKEND_UNAVAILABLE" for row in results)
    else:
        assert summary["llm_backend_validation_status"] == "LLM_BACKEND_VALIDATION_COMPLETED"
        assert summary["real_llm_backend_used"] is True
        assert summary["llm_backend"] in {"llamacpp", "openai-compatible", "ollama"}
        assert summary["llm_invoked_row_count"] == 1
        assert summary["retained_without_llm_count"] == 28
        assert bucket_counts["PASS_RETAINED"] >= 28
        assert summary["existing_pass_regression_count"] == 0
        assert summary["schema_mismatch_residual_count"] == 0
        assert summary["query_bound_evidence_gap_count"] == 0
        assert summary["text_namu_v2_0017"]["validation_bucket"] in {
            "LLM_SYNTHESIS_IMPROVED",
            "LLM_SYNTHESIS_REGRESSED",
            "LLM_TIMEOUT_OR_FAIL_CLOSED",
            "CITATION_SUPPORT_REGRESSED",
        }
        structured_rows = [
            row for row in results if row["track"] in {"pdf_business_ocr_mm", "xlsx_business_structured"}
        ]
        assert len(structured_rows) == 23
        assert all(row["structured_adapter_output_retained"] is True for row in structured_rows)
        assert all(row["structured_adapter_overwritten_by_llm"] is False for row in structured_rows)
        retained_rows = [row for row in results if row["validation_bucket"] == "PASS_RETAINED"]
        assert all(row["real_llm_backend_available"] is True for row in retained_rows)
        assert all(row["real_llm_backend_used"] is False for row in retained_rows)
        assert all(row["real_llm_backend_used_for_row"] is False for row in retained_rows)
        target_row = next(row for row in results if row["query_id"] == "text_namu_v2_0017")
        assert target_row["llm_invoked_for_row"] is True
        assert target_row["real_llm_backend_used"] is True
        assert target_row["real_llm_backend_used_for_row"] is True

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V2_2_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["llm_backend_validation_status"] == summary["llm_backend_validation_status"]


def test_v3_comparable_live_measurement_artifacts_are_separate_and_guarded() -> None:
    summary = read_json(AGENTIC_V3_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_RESULTS)
    attribution = read_json(AGENTIC_V3_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    input_config = read_json(REPORT_DIR / "metric_input_v1.json")
    first_run = read_json(REPORT_DIR / "baseline_v1.json")

    assert summary["run_id"] == AGENTIC_V3_RUN_ID
    assert summary["measurement_classification"] == "comparable_live_measurement_v3_not_promotion_evidence"
    assert summary["run_id"] not in {
        AGENTIC_RUN_ID,
        AGENTIC_V2_RUN_ID,
        AGENTIC_V2_1_RUN_ID,
        AGENTIC_V2_2_RUN_ID,
    }
    assert summary["diagnostic_only"] is True
    assert summary["comparable_live_measurement"] is True
    assert summary["promotion_evidence"] is False
    assert summary["write_summary_markdown"] is False
    assert "summary_md" not in summary["artifact_paths"]
    assert not report_artifact_path(AGENTIC_V3_RUN_ID, "summary.md").exists()
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["promotion_gate_auto_run"] is False
    assert summary["v2_2_completed_preflight"]["ok"] is True
    assert summary["source_bound_official_denominator_index_only"] is True
    assert summary["source_bound_index_used"] is True
    assert summary["canonical_search_unit_payload_used"] is True
    assert summary["real_llm_backend_required_for_text_rows"] is True
    assert summary["same_scorer_as_v2_2"] is True
    assert summary["same_denominator_as_v2_2"] is True
    assert summary["baseline_comparison_is_model_quality_comparable"] is True
    assert summary["comparison_scope"] == "mixed_structured_adapter_retained_and_text_llm_synthesis_rows"
    assert summary["structured_rows_policy"]["xlsx_primary_answer_policy"] == "deterministic_source_bound_adapter_retained"
    assert summary["structured_rows_policy"]["llm_overwrites_structured_adapter_output"] is False
    assert summary["text_rows_policy"]["text_rows_use_real_llm_synthesis"] is True
    assert summary["text_rows_policy"]["prompt_context_mode"] in {
        "query-bound-only",
        "same-track-scored-context",
    }
    assert summary["guardrails"] == {
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "baseline_mutation": False,
        "threshold_tuning": False,
        "winner_selection": False,
    }

    assert len(results) == 29
    assert len({row["query_id"] for row in results}) == 29
    config_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert {row["query_id"] for row in results} == config_query_ids
    assert Counter(row["track"] for row in results) == Counter(
        {
            "pdf_business_ocr_mm": 4,
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
        }
    )
    assert summary["result_count"] == 29
    assert sum(summary["result_bucket_counts"].values()) == 29
    assert set(summary["result_bucket_counts"]).issubset(
        {
            "PASS",
            "PARTIAL_OR_UNSUPPORTED",
            "CITATION_UNSUPPORTED",
            "PASS_RETAINED_BY_STRUCTURED_ADAPTER",
            "LLM_SYNTHESIS_PASS",
            "LLM_SYNTHESIS_REGRESSED",
            "STRUCTURED_ADAPTER_REGRESSED",
            "CITATION_SUPPORT_REGRESSED",
            "PROMPT_CONTEXT_POLICY_VIOLATION",
            "SCORER_NORMALIZATION_ISSUE_POSSIBLE",
        }
    )
    assert summary["per_track_counts_by_source_family"]["PDF"]["row_count"] == 4
    assert summary["per_track_counts_by_source_family"]["TEXT"]["row_count"] == 6
    assert summary["per_track_counts_by_source_family"]["XLSX"]["row_count"] == 19

    assert all(row["run_id"] == AGENTIC_V3_RUN_ID for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["candidate_artifacts_as_generation_source"] is False for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert all("human_label" not in row for row in results)

    structured_rows = [
        row for row in results if row["track"] in {"pdf_business_ocr_mm", "xlsx_business_structured"}
    ]
    text_rows = [row for row in results if row["track"] == "text_namu_v2_1"]
    assert len(structured_rows) == 23
    assert all(row["result_bucket"] == "PASS_RETAINED_BY_STRUCTURED_ADAPTER" for row in structured_rows)
    assert all(row["structured_adapter_output_retained"] is True for row in structured_rows)
    assert all(row["structured_adapter_overwritten_by_llm"] is False for row in structured_rows)
    assert all(row["llm_invoked_for_row"] is False for row in structured_rows)
    assert len(text_rows) == 6
    assert all(row["llm_invoked_for_row"] is True for row in text_rows)
    assert all(row["real_llm_backend_used_for_row"] is True for row in text_rows)

    pdf_table_rows = [
        row
        for row in structured_rows
        if any(
            (citation.get("search_unit_citation_payload") or {}).get("region_type") == "table_body"
            for citation in row["scored_citations"]
        )
    ]
    assert pdf_table_rows
    for row in pdf_table_rows:
        locator = row["scored_citations"][0]["search_unit_citation_payload"]
        assert locator["page"]
        assert locator["bbox"] and len(locator["bbox"]) == 4
        assert locator["source_pdf_path"]
        assert locator["row_label"]
        assert locator["target_column"]

    target_row = next(row for row in results if row["query_id"] == "text_namu_v2_0017")
    for key in (
        "llm_output_contains_expected_answer_span_for_scoring",
        "citation_support_present",
        "answer_citation_support_jointly_satisfied",
        "non_query_bound_same_track_context_used",
        "non_query_bound_same_track_context_distracted",
        "scorer_normalization_issue_possible",
        "prompt_context_policy",
    ):
        assert key in target_row["text_namu_v2_0017_diagnostics"]
    if target_row["failure_category"] != "PASS":
        assert summary["next_step_recommendation"] == "failure_tuning_for_text_namu_v2_0017"

    assert first_run["schema_version"] == summary["baseline_reference"]["run_id"]
    baseline_identity = official_file_identity(REPORT_DIR / "baseline_v1.json")
    assert summary["baseline_reference"]["artifact_identity"]["path"] == baseline_identity["path"]
    assert summary["baseline_reference"]["artifact_identity"]["exists"] is True
    assert baseline_identity["exists"] is True
    assert attribution["run_id"] == AGENTIC_V3_RUN_ID
    assert attribution["promotion_evidence"] is False
    assert attribution["guardrails"] == summary["guardrails"]
    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["comparable_live_measurement"] is True
    assert measurement["promotion_gate_auto_run"] is False
    assert measurement["result_bucket_counts"] == summary["result_bucket_counts"]


def test_v3_1_all_track_foundation_measurement_artifacts_are_separate_and_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_RESULTS)
    attribution = read_json(AGENTIC_V3_1_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_AUDIT_JSONL)
    triage = read_json(AGENTIC_V3_1_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    input_config = read_json(REPORT_DIR / "metric_input_v1.json")

    lane_names = {
        "v3_primary_replay",
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    }
    required_guardrails = {
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
    }
    locator_fields = {
        "PDF": {
            "source_pdf_path",
            "page",
            "physical_page_index",
            "bbox",
            "region_type",
            "search_unit_id",
            "document_version_id",
        },
        "XLSX": {
            "workbook",
            "sheet",
            "range",
            "cell",
            "row_label",
            "target_column",
            "normalized_value",
            "search_unit_id",
            "document_version_id",
        },
        "TEXT": {"document_id", "document_version_id", "search_unit_id", "text_locator"},
    }

    assert summary["run_id"] == AGENTIC_V3_1_RUN_ID
    assert summary["measurement_classification"] == "all_track_foundation_measurement_v3_1_diagnostic_only"
    assert summary["run_id"] not in {
        AGENTIC_RUN_ID,
        AGENTIC_V2_RUN_ID,
        AGENTIC_V2_1_RUN_ID,
        AGENTIC_V2_2_RUN_ID,
        AGENTIC_V3_RUN_ID,
    }
    assert summary["total_denominator_rows"] == 29
    assert summary["rows_by_source_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}
    assert summary["diagnostic_only"] is True
    for key, expected in required_guardrails.items():
        assert summary["guardrails"][key] is expected
    assert summary["next_step_recommendation"] == "row_level_failure_triage_after_all_track_foundation_measurement"

    assert set(summary["lane_counts"]) == lane_names
    assert summary["lane_counts"]["live_llm_retrieval_topk"]["llm_invoked_count"] == 29
    assert summary["lane_counts"]["live_llm_query_bound_oracle"]["llm_invoked_count"] == 29
    assert summary["lane_counts"]["v3_primary_replay"]["adapter_retained_count"] == 23
    assert summary["lane_counts"]["v3_primary_replay"]["llm_invoked_count"] == 6
    assert summary["source_family_lane_counts"]["PDF"]["v3_primary_replay"]["pass_count"] == 4
    assert summary["source_family_lane_counts"]["XLSX"]["v3_primary_replay"]["pass_count"] == 19

    assert len(results) == 29
    assert len(audit_rows) == 29
    config_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert {row["query_id"] for row in results} == config_query_ids
    assert Counter(row["source_family"] for row in results) == Counter({"PDF": 4, "TEXT": 6, "XLSX": 19})
    assert all(row["run_id"] == AGENTIC_V3_1_RUN_ID for row in results)
    assert all(set(row["lane_results"]) == lane_names for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert all("human_label" not in row for row in results)

    for row in results:
        family = row["source_family"]
        assert locator_fields[family].issubset(set(row["denominator_locator"]))
        assert row["denominator_search_unit_id"] == row["denominator_locator"]["search_unit_id"]
        assert row["query_bound_search_unit_present"] is True

        lane_a = row["lane_results"]["v3_primary_replay"]
        lane_b = row["lane_results"]["live_llm_retrieval_topk"]
        lane_c = row["lane_results"]["live_llm_query_bound_oracle"]
        assert lane_b["llm_invoked"] is True
        assert lane_c["llm_invoked"] is True
        assert lane_b["answer_origin"] == "LLM_SYNTHESIS"
        assert lane_c["answer_origin"] == "LLM_SYNTHESIS"
        assert lane_b["prompt_context_mode"] == "retrieval_topk_source_bound"
        assert lane_c["prompt_context_mode"] == "query_bound_only_source_bound"
        assert lane_b["generation_used_expected_answer"] is False
        assert lane_c["generation_used_expected_answer"] is False
        assert lane_b["generation_used_gold_fields"] is False
        assert lane_c["generation_used_gold_fields"] is False
        assert lane_b["generation_used_supporting_evidence"] is False
        assert lane_c["generation_used_supporting_evidence"] is False
        assert set(lane_c["cited_search_unit_ids"]).issubset({row["denominator_search_unit_id"]})
        for live_lane in (lane_b, lane_c):
            assert live_lane["llm_generated_locator_validation"]["generated_by_llm"] is True
            assert set(live_lane["llm_generated_locator_validation"]["required_fields"]) == locator_fields[family]
            assert live_lane["llm_generated_locator_validation"]["cited_search_unit_ids"] == live_lane["cited_search_unit_ids"]
            assert isinstance(live_lane["llm_generated_citation_locators"], list)
            for generated_locator in live_lane["llm_generated_citation_locators"]:
                assert "search_unit_id" in generated_locator
            if live_lane["failure_category"] == "PASS":
                assert live_lane["llm_generated_locator_validation"]["ok"] is True
                assert len(live_lane["llm_generated_citation_locators"]) == len(live_lane["cited_search_unit_ids"])
                for generated_locator in live_lane["llm_generated_citation_locators"]:
                    assert locator_fields[family].issubset(set(generated_locator))

        if family in {"PDF", "XLSX"}:
            assert lane_a["answer_origin"] == "STRUCTURED_ADAPTER"
            assert lane_a["llm_invoked"] is False
            assert lane_a["prompt_context_mode"] == "structured_adapter_retained"
        else:
            assert lane_a["answer_origin"] == "LLM_SYNTHESIS"
            assert lane_a["llm_invoked"] is True

    failing_query_ids = {
        row["query_id"]
        for row in results
        if any(lane["failure_category"] != "PASS" for lane in row["lane_results"].values())
    }
    assert {item["query_id"] for item in triage["items"]} == failing_query_ids
    assert all(item["failing_lane_names"] for item in triage["items"])
    assert all(item["query_id"] in failing_query_ids for item in triage["items"])
    assert all(item["safe_to_fix_without_user_gold_decision"] in {True, False} for item in triage["items"])
    assert all(item["requires_user_gold_policy_decision"] in {True, False} for item in triage["items"])

    assert attribution["run_id"] == AGENTIC_V3_1_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert set(attribution["failure_taxonomy"]) >= {
        "PASS",
        "RETRIEVAL_QUERY_BOUND_MISS",
        "CITATION_PAYLOAD_SCHEMA_MISMATCH",
        "LLM_STRICT_JSON_PARSE_FAILURE",
        "PDF_BBOX_LOCATOR_LOSS",
        "XLSX_CELL_LOCATOR_LOSS",
        "SCORER_NORMALIZATION_REVIEW",
        "GOLD_POLICY_REVIEW_CANDIDATE",
    }

    assert all("expected_answer" not in row for row in audit_rows)
    assert all("supporting_evidence" not in row for row in audit_rows)
    assert all(row["query_id"] in config_query_ids for row in audit_rows)
    measurement_doc = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage_doc = TRIAGE_DOC.read_text(encoding="utf-8")
    assert AGENTIC_V3_1_RUN_ID in measurement_doc
    assert AGENTIC_V3_1_RUN_ID in triage_doc
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_RUN_ID}*promotion*"))
    forbidden_status = subprocess.run(
        [
            "git",
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            "ai/eval/silver",
            "ai/eval/review",
            "ai/eval/eval_queries",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert forbidden_status.returncode == 0
    assert_no_unexpected_eval_query_status(forbidden_status.stdout)

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["result_count"] == 29
    assert measurement["lane_counts"] == summary["lane_counts"]


def test_v3_1_priority_1_5_strict_json_locator_triage_artifacts_are_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_PRIORITY_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_PRIORITY_RESULTS)
    attribution = read_json(AGENTIC_V3_1_PRIORITY_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_PRIORITY_AUDIT_JSONL)
    strict_json_diagnostics = read_json(AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_JSON)
    triage_delta = read_json(AGENTIC_V3_1_PRIORITY_TRIAGE_DELTA_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    required_guardrails = {
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
    }

    assert summary["run_id"] == AGENTIC_V3_1_PRIORITY_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_RUN_ID
    assert summary["measurement_classification"] == "priority_1_5_strict_json_locator_triage_diagnostic_only"
    assert summary["target_row_count"] == 5
    assert summary["result_count"] == 5
    assert tuple(summary["target_query_ids"]) == AGENTIC_V3_1_PRIORITY_QUERY_IDS
    assert [row["query_id"] for row in results] == list(AGENTIC_V3_1_PRIORITY_QUERY_IDS)
    assert [row["query_id"] for row in audit_rows] == list(AGENTIC_V3_1_PRIORITY_QUERY_IDS)
    for key, expected in required_guardrails.items():
        assert summary["guardrails"][key] is expected
        assert summary[key] is expected

    assert summary["strict_json_parse_failure_before"] == 2
    assert summary["strict_json_parse_failure_after"] == 0
    assert summary["strict_json_schema_repair_applied_count_before"] == 0
    assert summary["strict_json_schema_repair_applied_count_after"] == 2
    assert summary["llm_generated_locator_copy_failure_before"] == 5
    assert summary["llm_generated_locator_copy_failure_after"] == 1
    assert summary["llm_generated_locator_field_mismatch_failure_before"] == 3
    assert summary["llm_generated_locator_field_mismatch_failure_after"] == 0
    assert summary["llm_generated_locator_missing_failure_before"] == 0
    assert summary["llm_generated_locator_missing_failure_after"] == 1
    assert summary["pdf_source_pdf_path_mismatch_before"] == 1
    assert summary["pdf_source_pdf_path_mismatch_after"] == 0
    assert summary["xlsx_row_label_mismatch_before"] == 2
    assert summary["xlsx_row_label_mismatch_after"] == 0
    assert "posthoc_payload_locator_preservation_failure_count" in summary
    assert "llm_generated_locator_copy_failure_count" in summary
    assert "posthoc_payload_locator_preservation_failure_count" in summary["locator_metric_split"]
    assert "llm_generated_locator_copy_failure_count" in summary["locator_metric_split"]
    assert "llm_generated_locator_missing_failure_count" in summary["locator_metric_split"]
    assert summary["v3_1_artifact_consistency_preflight"]["ok"] is True
    assert summary["score_interpretation"] == "answer_and_citation_scores_are_reference_only_not_promotion_evidence"

    assert attribution["run_id"] == AGENTIC_V3_1_PRIORITY_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert strict_json_diagnostics["run_id"] == AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_ID
    assert strict_json_diagnostics["target_run_id"] == AGENTIC_V3_1_PRIORITY_RUN_ID
    assert strict_json_diagnostics["diagnostic_only"] is True
    assert tuple(strict_json_diagnostics["target_query_ids"]) == AGENTIC_V3_1_PRIORITY_QUERY_IDS[:2]
    measurement_doc = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage_doc = TRIAGE_DOC.read_text(encoding="utf-8")
    assert AGENTIC_V3_1_PRIORITY_RUN_ID in measurement_doc
    assert AGENTIC_V3_1_PRIORITY_RUN_ID in triage_doc
    assert "LLM-generated locator copy failure: `5 -> 1`" in triage_doc

    diagnostic_rows = {row["query_id"]: row for row in strict_json_diagnostics["rows"]}
    for query_id in AGENTIC_V3_1_PRIORITY_QUERY_IDS[:2]:
        after = diagnostic_rows[query_id]["after"]
        assert after["prompt_context_mode"] == "retrieval_topk_source_bound"
        assert after["raw_response_sha256"]
        assert after.get("sanitized_raw_response_excerpt") or after.get("raw_response_excerpt")
        assert after["attempted_schema_keys"] == ["answer", "cited_search_unit_ids", "citation_locators"]
        assert "strict_json_error" in after
        assert "missing_required_keys" in after
        assert "schema_repair_applied" in after
        assert "missing_required_keys_before_repair" in after
        assert after["cited_search_unit_ids_before_parse"]

    rows_by_id = {row["query_id"]: row for row in results}
    pdf_validation = rows_by_id["gq_auto_010"]["lane_results"]["live_llm_retrieval_topk"][
        "llm_generated_locator_validation"
    ]
    pdf_unit_id = rows_by_id["gq_auto_010"]["denominator_search_unit_id"]
    pdf_source_path_check = pdf_validation["field_comparisons_by_search_unit_id"][pdf_unit_id]["source_pdf_path"]
    assert pdf_source_path_check["byte_equal"] is True
    assert pdf_source_path_check["normalized_equal"] is True

    for query_id in ("gq_auto_023", "gq_xlsx_lookup_008"):
        row = rows_by_id[query_id]
        validation = row["lane_results"]["live_llm_retrieval_topk"]["llm_generated_locator_validation"]
        unit_id = row["denominator_search_unit_id"]
        row_label_check = validation["field_comparisons_by_search_unit_id"][unit_id]["row_label"]
        assert row_label_check["byte_equal"] is True
        assert row_label_check["normalized_equal"] is True

    before_by_id = {row["query_id"]: row for row in triage_delta["rows"]}
    assert before_by_id["gq_auto_010"]["before"]["pdf_source_pdf_path_byte_equal"] is False
    assert before_by_id["gq_auto_010"]["after"]["pdf_source_pdf_path_byte_equal"] is True
    for query_id in ("gq_auto_023", "gq_xlsx_lookup_008"):
        assert before_by_id[query_id]["before"]["xlsx_row_label_byte_equal"] is False
        assert before_by_id[query_id]["after"]["xlsx_row_label_byte_equal"] is True
        assert before_by_id[query_id]["after"]["xlsx_row_label_normalized_equal"] is True

    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(strict_json_diagnostics)
    assert_no_gold_generation_source_fields(triage_delta)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_PRIORITY_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_PRIORITY_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_PRIORITY_RUN_ID}*promotion*"))

    forbidden_status = subprocess.run(
        [
            "git",
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            "ai/eval/silver",
            "ai/eval/review",
            "ai/eval/eval_queries",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert forbidden_status.returncode == 0
    assert_no_unexpected_eval_query_status(forbidden_status.stdout)

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_PRIORITY_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["result_count"] == 5
    assert measurement["strict_json_parse_failure_after"] == summary["strict_json_parse_failure_after"]


def test_priority_strict_json_schema_repair_is_counted_separately() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    rows = [
        {
            "lane_results": {
                "live_llm_retrieval_topk": {
                    "failure_category": "PASS",
                    "strict_json_parse_ok": True,
                    "strict_json_diagnostics": {
                        "parse_ok": True,
                        "schema_repair_applied": True,
                        "missing_required_keys_before_repair": ["cited_search_unit_ids"],
                        "missing_required_keys": [],
                    },
                }
            }
        }
    ]

    assert runner.strict_json_parse_failure_count(rows) == 0
    assert runner.strict_json_schema_repair_applied_count(rows) == 1


def test_priority_locator_copy_failure_counts_missing_fields() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    rows = [
        {
            "lane_results": {
                "live_llm_retrieval_topk": {
                    "llm_generated_locator_validation": {
                        "generated_by_llm": True,
                        "ok": False,
                        "missing_fields_by_search_unit_id": {"su_text": ["text_locator"]},
                        "missing_locator_for_search_unit_ids": [],
                        "mismatched_fields_by_search_unit_id": {},
                    }
                }
            }
        }
    ]

    assert runner.llm_generated_locator_copy_failure_count(rows) == 1
    assert runner.llm_generated_locator_field_mismatch_failure_count(rows) == 0
    assert runner.llm_generated_locator_missing_failure_count(rows) == 1


def test_v3_1_text_locator_residual_triage_copies_canonical_text_locator() -> None:
    summary = read_json(AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_TEXT_LOCATOR_RESULTS)
    attribution = read_json(AGENTIC_V3_1_TEXT_LOCATOR_ATTRIBUTION_JSON)
    triage_delta = read_json(AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_PRIORITY_RUN_ID
    assert summary["measurement_classification"] == "text_locator_residual_triage_diagnostic_only"
    assert summary["target_row_count"] == 1
    assert summary["result_count"] == 1
    assert summary["target_query_ids"] == ["text_namu_v2_0012"]
    assert summary["text_locator_missing_count_before"] == 1
    assert summary["text_locator_missing_count_after"] == 0
    assert summary["llm_generated_locator_missing_failure_before"] == 1
    assert summary["llm_generated_locator_missing_failure_after"] == 0
    assert summary["llm_generated_locator_field_mismatch_failure_after"] == 0
    assert summary["text_locator_byte_equal_after"] is True
    assert summary["text_locator_normalized_equal_after"] is True
    assert summary["promotion_evidence"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["guardrails"]["promotion_gate_auto_run"] is False
    assert attribution["run_id"] == AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]

    assert [row["query_id"] for row in results] == ["text_namu_v2_0012"]
    row = results[0]
    assert row["source_family"] == "TEXT"
    assert row["denominator_locator"]["text_locator"]
    for lane_name in ("live_llm_retrieval_topk", "live_llm_query_bound_oracle"):
        lane = row["lane_results"][lane_name]
        validation = lane["llm_generated_locator_validation"]
        unit_id = row["denominator_search_unit_id"]
        generated_locator = next(
            locator for locator in lane["llm_generated_citation_locators"] if locator["search_unit_id"] == unit_id
        )
        text_locator_check = validation["field_comparisons_by_search_unit_id"][unit_id]["text_locator"]
        assert generated_locator["text_locator"]
        assert validation["ok"] is True
        assert validation["missing_fields_by_search_unit_id"] == {}
        assert validation["mismatched_fields_by_search_unit_id"] == {}
        assert text_locator_check["byte_equal"] is True
        assert text_locator_check["normalized_equal"] is True
        assert lane["failure_category"] != "CITATION_PAYLOAD_SCHEMA_MISMATCH"

    delta_row = triage_delta["rows"][0]
    assert delta_row["query_id"] == "text_namu_v2_0012"
    assert delta_row["before"]["text_locator_present"] is False
    assert delta_row["after"]["text_locator_present"] is True
    assert delta_row["after"]["text_locator_byte_equal"] is True
    assert delta_row["after"]["text_locator_normalized_equal"] is True
    assert delta_row["after"]["llm_generated_locator_missing_failure"] is False
    assert delta_row["after"]["llm_generated_locator_field_mismatch_failure"] is False

    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(triage_delta)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["result_count"] == 1


def test_v3_1_1_post_strict_json_locator_triage_all_track_measurement_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_1_POST_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_1_POST_RESULTS)
    attribution = read_json(AGENTIC_V3_1_1_POST_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_1_POST_AUDIT_JSONL)
    triage_queue = read_json(AGENTIC_V3_1_1_POST_TRIAGE_QUEUE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID
    assert summary["measurement_classification"] == "all_track_foundation_measurement_v3_1_1_post_strict_json_locator_triage_diagnostic_only"
    assert summary["total_denominator_rows"] == 29
    assert summary["result_count"] == 29
    assert len(results) == 29
    assert len(audit_rows) == 29
    assert summary["rows_by_source_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}
    assert set(summary["lane_counts"]) == {"v3_primary_replay", "live_llm_retrieval_topk", "live_llm_query_bound_oracle"}
    assert all(set(row["lane_results"]) == set(summary["lane_counts"]) for row in results)
    assert summary["strict_json_parse_failure_count_by_lane"]["live_llm_retrieval_topk"] == 0
    assert summary["strict_json_parse_failure_count_by_lane"]["live_llm_query_bound_oracle"] == 0
    assert summary["llm_generated_locator_copy_failure_count_by_lane"]["live_llm_retrieval_topk"] == 0
    assert summary["llm_generated_locator_copy_failure_count_by_lane"]["live_llm_query_bound_oracle"] == 0
    assert summary["llm_generated_locator_missing_failure_count_by_lane"]["live_llm_retrieval_topk"] == 0
    assert summary["llm_generated_locator_field_mismatch_failure_count_by_lane"]["live_llm_retrieval_topk"] == 0
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0
    assert "answer_span_mismatch_count_by_lane" in summary
    assert "existing_pass_regression_count" in summary["regression_from_v3_1_foundation"]
    assert isinstance(summary["regression_from_v3_1_foundation"]["regressions"], list)
    assert summary["promotion_evidence"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["guardrails"]["promotion_gate_auto_run"] is False
    assert attribution["run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert triage_queue["run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert triage_queue["strict_json_or_locator_residual_count"] == 0
    assert all(
        item["primary_failure_category"]
        not in {"LLM_STRICT_JSON_PARSE_FAILURE", "PDF_BBOX_LOCATOR_LOSS", "XLSX_CELL_LOCATOR_LOSS", "CITATION_PAYLOAD_SCHEMA_MISMATCH"}
        for item in triage_queue["items"]
    )

    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(triage_queue)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["result_count"] == 29
    assert measurement["lane_counts"] == summary["lane_counts"]


def test_v3_1_2_answer_span_renderer_triage_batch_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_2_ANSWER_SPAN_RESULTS)
    attribution = read_json(AGENTIC_V3_1_2_ANSWER_SPAN_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_2_ANSWER_SPAN_AUDIT_JSONL)
    diagnostics = read_jsonl(AGENTIC_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_2_ANSWER_SPAN_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    first_batch = [
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    ]
    target_ids = [*first_batch, "text_namu_v2_0005"]

    assert summary["run_id"] == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert summary["measurement_classification"] == "answer_span_renderer_triage_v3_1_2_diagnostic_only"
    assert summary["write_summary_markdown"] is False
    assert not AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_MD.exists()
    assert summary["target_query_ids"] == target_ids
    assert summary["first_batch_query_ids"] == first_batch
    assert summary["secondary_text_watchlist_query_ids"] == ["text_namu_v2_0005"]
    assert summary["queue_source_of_truth_decision"]["selected_source_type"] == "machine_triage_queue_artifact"
    assert summary["queue_source_of_truth_decision"]["doc_drift_observed"] is True

    assert len(results) == 6
    assert len(audit_rows) == 6
    assert len(diagnostics) == 6
    assert [row["query_id"] for row in results] == target_ids
    assert [row["query_id"] for row in diagnostics] == target_ids
    assert all(row["first_batch_selected"] is True for row in results[:5])
    assert results[-1]["query_id"] == "text_namu_v2_0005"
    assert results[-1]["first_batch_selected"] is False
    assert results[-1]["include_decision"] == "included_as_secondary_text_watchlist_only_queue_rank_12"

    assert summary["lane_counts"]["v3_primary_replay"]["pass_count"] == 1
    assert summary["lane_counts"]["live_llm_retrieval_topk"]["pass_count"] == 1
    assert summary["lane_counts"]["live_llm_query_bound_oracle"]["pass_count"] == 0
    assert summary["answer_span_mismatch_count_by_lane"] == {
        "live_llm_query_bound_oracle": 12,
        "live_llm_retrieval_topk": 9,
        "v3_primary_replay": 0,
    }
    assert all(value == 0 for value in summary["strict_json_parse_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_copy_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_missing_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_field_mismatch_failure_count_by_lane"].values())
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0

    diagnostic_counts = summary["answer_span_renderer_diagnostic_counts"]
    assert diagnostic_counts["diagnostic_only_expected_span_mismatch"] >= 11
    assert diagnostic_counts["answer_too_narrow"] >= 10
    assert diagnostic_counts["renderer_formatting_mismatch"] >= 2
    assert diagnostic_counts["scorer_normalization_gap"] >= 2
    assert "retrieval_context_insufficiency" not in diagnostic_counts

    for row in diagnostics:
        assert row["diagnostic_only"] is True
        assert row["promotion_evidence"] is False
        assert row["reference_span_audit_only"] is True
        assert row["reference_span_text_embedded"] is False
        for lane_diag in row["answer_span_renderer_diagnostics"].values():
            assert "scoring_reference_span_sha256" in lane_diag
            assert lane_diag["reference_span_text_embedded"] is False
            assert lane_diag["generation_used_expected_answer"] is False
            assert lane_diag["generation_used_supporting_evidence"] is False
            assert lane_diag["generation_used_gold_fields"] is False

    assert remaining["run_id"] == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    assert remaining["source_run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert remaining["strict_json_or_locator_residual_count"] == 0
    remaining_ids = [item["query_id"] for item in remaining["items"]]
    assert not set(first_batch).intersection(remaining_ids)
    assert "text_namu_v2_0005" in remaining_ids
    assert remaining_ids[0] == "gq_auto_010"

    assert attribution["run_id"] == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(diagnostics)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["strict_json_parse_failure_count_by_lane"] == summary["strict_json_parse_failure_count_by_lane"]
    assert "strict_json_parse_failure_after" not in measurement
    assert measurement["answer_span_renderer_diagnostic_counts"] == diagnostic_counts

    failure_event = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_failure_attribution"
        and event.get("run_id") == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    )
    assert failure_event["promotion_evidence"] is False
    assert failure_event["diagnostic_only"] is True
    assert failure_event["generation_used_expected_answer"] is False
    assert failure_event["generation_used_supporting_evidence"] is False
    assert failure_event["generation_used_gold_fields"] is False
    assert failure_event["guardrails"] == summary["guardrails"]


def test_v3_1_3_remaining_queue_answer_span_renderer_triage_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_3_REMAINING_QUEUE_RESULTS)
    attribution = read_json(AGENTIC_V3_1_3_REMAINING_QUEUE_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_3_REMAINING_QUEUE_AUDIT_JSONL)
    diagnostics = read_jsonl(AGENTIC_V3_1_3_REMAINING_QUEUE_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_3_REMAINING_QUEUE_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    target_ids = [
        "gq_auto_010",
        "gq_auto_024",
        "gq_auto_030",
        "gq_auto_043",
        "gq_pdf_section_question_001",
        "gq_xlsx_date_number_format_001",
        "text_namu_v2_0005",
    ]

    assert summary["run_id"] == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    assert summary["measurement_classification"] == "remaining_queue_answer_span_renderer_triage_v3_1_3_diagnostic_only"
    assert summary["write_summary_markdown"] is False
    assert not AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_MD.exists()
    assert summary["target_query_ids"] == target_ids
    assert summary["queue_source_of_truth_decision"]["selected_source"] == report_artifact_repo_relative(
        AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "queue.json"
    )
    assert summary["queue_source_of_truth_decision"]["selected_source_type"] == "machine_remaining_queue_artifact"

    assert len(results) == 7
    assert len(audit_rows) == 7
    assert len(diagnostics) == 7
    assert [row["query_id"] for row in results] == target_ids
    assert [row["query_id"] for row in diagnostics] == target_ids
    assert summary["rows_by_source_family"] == {"PDF": 4, "TEXT": 1, "XLSX": 2}
    assert "gq_auto_037" not in summary["target_query_ids"]
    assert "gq_auto_037" not in json.dumps(remaining, ensure_ascii=False)

    assert summary["target_queue_pass_count_before_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 3,
        "v3_primary_replay": 7,
    }
    assert summary["target_queue_pass_count_after_by_lane"] == {
        "live_llm_query_bound_oracle": 5,
        "live_llm_retrieval_topk": 5,
        "v3_primary_replay": 7,
    }
    assert summary["all_track_remeasurement_performed"] is True
    assert summary["all_track_result_count_before"] == 29
    assert summary["all_track_result_count_after"] == 29
    assert summary["all_track_pass_count_before_by_lane"] == {
        "live_llm_query_bound_oracle": 17,
        "live_llm_retrieval_topk": 20,
        "v3_primary_replay": 24,
    }
    assert summary["all_track_pass_count_after_by_lane"] == {
        "live_llm_query_bound_oracle": 22,
        "live_llm_retrieval_topk": 22,
        "v3_primary_replay": 24,
    }
    assert summary["target_queue_answer_span_mismatch_before_by_lane"] == {
        "live_llm_query_bound_oracle": 7,
        "live_llm_retrieval_topk": 4,
        "v3_primary_replay": 0,
    }
    assert summary["target_queue_answer_span_mismatch_after_by_lane"] == {
        "live_llm_query_bound_oracle": 2,
        "live_llm_retrieval_topk": 2,
        "v3_primary_replay": 0,
    }
    assert summary["all_track_answer_span_mismatch_before_by_lane"] == {
        "live_llm_query_bound_oracle": 12,
        "live_llm_retrieval_topk": 9,
        "v3_primary_replay": 0,
    }
    assert summary["all_track_answer_span_mismatch_after_by_lane"] == {
        "live_llm_query_bound_oracle": 7,
        "live_llm_retrieval_topk": 7,
        "v3_primary_replay": 0,
    }
    assert all(value == 0 for value in summary["strict_json_parse_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_copy_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_missing_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_field_mismatch_failure_count_by_lane"].values())
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0
    assert all(
        all(value == 0 for value in item.values()) if isinstance(item, dict) else item == 0
        for item in summary["all_track_residuals_after"].values()
    )
    assert summary["text_namu_v2_0005_lane_a_b_not_degraded"] is True
    assert summary["text_namu_v2_0005_lane_c_improved"] is True

    remaining_ids = [item["query_id"] for item in remaining["items"]]
    assert remaining_ids == ["gq_auto_010", "gq_pdf_section_question_001"]
    assert remaining["strict_json_or_locator_residual_count"] == 0
    assert remaining["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "queue.json"
    )

    for row in diagnostics:
        assert row["diagnostic_only"] is True
        assert row["promotion_evidence"] is False
        assert row["reference_span_audit_only"] is True
        assert row["reference_span_text_embedded"] is False
        for lane_diag in row["answer_span_renderer_diagnostics"].values():
            assert lane_diag["reference_span_text_embedded"] is False
            assert lane_diag["generation_used_expected_answer"] is False
            assert lane_diag["generation_used_supporting_evidence"] is False
            assert lane_diag["generation_used_gold_fields"] is False

    assert attribution["run_id"] == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(diagnostics)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["all_track_remeasurement_performed"] is True
    assert measurement["all_track_pass_count_after_by_lane"] == summary["all_track_pass_count_after_by_lane"]
    assert measurement["queue_source_of_truth_decision"] == summary["queue_source_of_truth_decision"]


def test_v3_1_4_pdf_residual_answer_span_renderer_triage_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_4_PDF_RESIDUAL_RESULTS)
    attribution = read_json(AGENTIC_V3_1_4_PDF_RESIDUAL_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_4_PDF_RESIDUAL_AUDIT_JSONL)
    diagnostics = read_jsonl(AGENTIC_V3_1_4_PDF_RESIDUAL_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_4_PDF_RESIDUAL_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    target_ids = ["gq_auto_010", "gq_pdf_section_question_001"]

    assert summary["run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    assert summary["measurement_classification"] == "pdf_residual_answer_span_renderer_triage_v3_1_4_diagnostic_only"
    assert summary["write_summary_markdown"] is False
    assert not AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_MD.exists()
    assert summary["target_query_ids"] == target_ids
    assert summary["queue_source_of_truth_decision"]["selected_source"] == report_artifact_repo_relative(
        AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "queue.json"
    )
    assert summary["queue_source_of_truth_decision"]["selected_source_type"] == "machine_remaining_queue_artifact"

    assert len(results) == 2
    assert len(audit_rows) == 2
    assert len(diagnostics) == 2
    assert [row["query_id"] for row in results] == target_ids
    assert [row["query_id"] for row in diagnostics] == target_ids
    assert summary["rows_by_source_family"] == {"PDF": 2, "TEXT": 0, "XLSX": 0}

    assert summary["target_queue_pass_count_before_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 2,
    }
    assert summary["target_queue_pass_count_after_by_lane"] == {
        "live_llm_query_bound_oracle": 1,
        "live_llm_retrieval_topk": 1,
        "v3_primary_replay": 2,
    }
    assert summary["all_track_remeasurement_performed"] is True
    assert summary["all_track_before_run_id"] == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    assert summary["all_track_after_run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert summary["all_track_result_count_before"] == 29
    assert summary["all_track_result_count_after"] == 29
    assert summary["all_track_pass_count_before_by_lane"] == {
        "live_llm_query_bound_oracle": 22,
        "live_llm_retrieval_topk": 22,
        "v3_primary_replay": 24,
    }
    assert summary["all_track_pass_count_after_by_lane"] == {
        "live_llm_query_bound_oracle": 23,
        "live_llm_retrieval_topk": 23,
        "v3_primary_replay": 24,
    }
    assert summary["target_queue_answer_span_mismatch_before_by_lane"] == {
        "live_llm_query_bound_oracle": 2,
        "live_llm_retrieval_topk": 2,
        "v3_primary_replay": 0,
    }
    assert summary["target_queue_answer_span_mismatch_after_by_lane"] == {
        "live_llm_query_bound_oracle": 1,
        "live_llm_retrieval_topk": 1,
        "v3_primary_replay": 0,
    }
    assert summary["all_track_answer_span_mismatch_before_by_lane"] == {
        "live_llm_query_bound_oracle": 7,
        "live_llm_retrieval_topk": 7,
        "v3_primary_replay": 0,
    }
    assert summary["all_track_answer_span_mismatch_after_by_lane"] == {
        "live_llm_query_bound_oracle": 6,
        "live_llm_retrieval_topk": 6,
        "v3_primary_replay": 0,
    }
    assert all(value == 0 for value in summary["strict_json_parse_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_copy_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_missing_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_field_mismatch_failure_count_by_lane"].values())
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0
    assert all(
        all(value == 0 for value in item.values()) if isinstance(item, dict) else item == 0
        for item in summary["all_track_residuals_after"].values()
    )

    remaining_ids = [item["query_id"] for item in remaining["items"]]
    assert remaining_ids == ["gq_auto_010"]
    assert remaining["strict_json_or_locator_residual_count"] == 0
    assert remaining["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "queue.json"
    )
    assert summary["pdf_table_axis_disambiguation"]["gq_pdf_section_question_001"]["applied_lanes"] == [
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    ]
    assert summary["pdf_table_axis_disambiguation"]["gq_auto_010"]["classification"] == (
        "retrieval_context_insufficiency"
    )

    for row in diagnostics:
        assert row["diagnostic_only"] is True
        assert row["promotion_evidence"] is False
        assert row["reference_span_audit_only"] is True
        assert row["reference_span_text_embedded"] is False
        for lane_diag in row["answer_span_renderer_diagnostics"].values():
            assert lane_diag["reference_span_text_embedded"] is False
            assert lane_diag["generation_used_expected_answer"] is False
            assert lane_diag["generation_used_supporting_evidence"] is False
            assert lane_diag["generation_used_gold_fields"] is False

    assert attribution["run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(diagnostics)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["all_track_remeasurement_performed"] is True
    assert measurement["all_track_pass_count_after_by_lane"] == summary["all_track_pass_count_after_by_lane"]
    assert measurement["queue_source_of_truth_decision"] == summary["queue_source_of_truth_decision"]


def test_v3_1_5_gq_auto_010_source_bound_context_coverage_diagnostic_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_SUMMARY_JSON)
    diagnostics = read_jsonl(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert summary["measurement_classification"] == (
        "gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_v3_1_5_diagnostic_only"
    )
    assert summary["target_query_ids"] == ["gq_auto_010"]
    assert summary["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "queue.json"
    )
    assert summary["source_queue_preflight"]["only_gq_auto_010_remaining"] is True
    assert summary["source_queue_preflight"]["strict_json_or_locator_residual_count"] == 0
    assert summary["classification_result"]["query_id"] == "gq_auto_010"
    assert summary["classification_result"]["classification"] == "query_bound_searchunit_too_narrow"
    assert summary["classification_result"]["final_queue_decision"] == "remain_in_queue"
    assert summary["non_production_index_or_export_fix_applied"] is False
    assert summary["all_track_remeasurement_performed"] is False
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["artifact_policy"]["minimum_durable_artifacts"] == [
        "summary_json",
        "context_coverage_diagnostics_jsonl",
        "remaining_triage_queue_json",
        "rag_current_eval_status_jsonl",
    ]
    assert "results_jsonl" not in summary["artifact_paths"]
    assert "failure_attribution_json" not in summary["artifact_paths"]
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}_results.jsonl").exists()
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}_failure_attribution.json").exists()
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}_actual_response_audit.jsonl").exists()

    assert len(diagnostics) == 1
    row = diagnostics[0]
    assert row["query_id"] == "gq_auto_010"
    assert row["diagnostic_only"] is True
    assert row["promotion_evidence"] is False
    assert row["reference_span_audit_only"] is True
    assert row["reference_span_text_embedded"] is False
    assert row["audit_numeric_span_probe_source"] == "expected_answer_numeric_tokens_audit_only"
    assert row["audit_numeric_span_count"] == 2
    assert row["v3_1_4_cited_context_contains_all_audit_numeric_spans"] is False
    assert row["current_cited_search_unit_contains_all_audit_numeric_spans"] is False
    assert row["same_document_search_unit_contains_all_audit_numeric_spans"] is False
    assert row["adjacent_page_window_search_unit_contains_all_audit_numeric_spans"] is False
    assert row["raw_source_pdf_text_contains_all_audit_numeric_spans"] is True
    assert row["issue_classification"] == "query_bound_searchunit_too_narrow"
    assert row["behavior_change_made"] is False
    assert row["official_retrieval_metric"] is False
    assert row["generation_used_expected_answer"] is False
    assert row["generation_used_supporting_evidence"] is False
    assert row["generation_used_gold_fields"] is False

    remaining_ids = [item["query_id"] for item in remaining["items"]]
    assert remaining_ids == ["gq_auto_010"]
    assert remaining["strict_json_or_locator_residual_count"] == 0
    assert remaining["source_queue_artifact"] == summary["source_queue_artifact"]
    assert remaining["items"][0]["coverage_classification"] == "query_bound_searchunit_too_narrow"
    assert remaining["items"][0]["recommended_next_step"] == (
        "decide_or_implement_safe_pdf_paragraph_window_expansion_before_live_generation"
    )

    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(diagnostics)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["classification_result"] == summary["classification_result"]
    assert measurement["source_queue_artifact"] == summary["source_queue_artifact"]


def test_v3_1_6_gq_auto_010_pdf_paragraph_window_expansion_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS)
    attribution = read_json(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_AUDIT_JSONL)
    answer_span_rows = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ANSWER_SPAN_DIAGNOSTICS_JSONL)
    expansion_rows = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_CONTEXT_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID
    assert summary["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID, "queue.json"
    )
    assert summary["target_query_ids"] == ["gq_auto_010"]
    assert summary["source_queue_preflight"]["queue_query_ids"] == ["gq_auto_010"]
    assert summary["source_queue_preflight"]["classification"] == "query_bound_searchunit_too_narrow"
    assert summary["source_queue_preflight"]["strict_json_or_locator_residual_count"] == 0
    assert summary["source_queue_preflight"]["ok"] is True
    assert summary["source_queue_preflight"]["errors"] == []
    assert summary["queue_source_of_truth_decision"]["selected_source_type"] == "machine_remaining_queue_artifact"
    assert summary["queue_source_of_truth_decision"]["docs_are_human_facing_narrative_only"] is True

    assert summary["result_count"] == 1
    assert summary["unique_query_id_count"] == 1
    assert summary["target_row_count"] == 1
    assert [row["query_id"] for row in results] == ["gq_auto_010"]
    assert [row["query_id"] for row in audit_rows] == ["gq_auto_010"]
    assert [row["query_id"] for row in answer_span_rows] == ["gq_auto_010"]
    assert [row["query_id"] for row in expansion_rows] == ["gq_auto_010"]

    row = results[0]
    assert set(row["lane_results"]) == {
        "v3_primary_replay",
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    }
    assert row["row_level_classification_change"]["improved_lane_names"] == [
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    ]
    assert row["row_level_classification_change"]["regressed_lane_names"] == []
    assert row["row_level_classification_change"]["unchanged_failed_lane_names"] == []
    assert summary["target_queue_pass_count_before_by_lane"] == {
        "v3_primary_replay": 1,
        "live_llm_retrieval_topk": 0,
        "live_llm_query_bound_oracle": 0,
    }
    assert summary["target_queue_pass_count_after_by_lane"] == {
        "v3_primary_replay": 1,
        "live_llm_retrieval_topk": 1,
        "live_llm_query_bound_oracle": 1,
    }
    assert summary["all_track_remeasurement_performed"] is True
    assert summary["all_track_before_run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert summary["all_track_after_run_id"] == AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    assert summary["all_track_result_count_before"] == 29
    assert summary["all_track_result_count_after"] == 29
    assert summary["all_track_pass_count_before_by_lane"] == {
        "v3_primary_replay": 24,
        "live_llm_retrieval_topk": 23,
        "live_llm_query_bound_oracle": 23,
    }
    assert summary["all_track_pass_count_after_by_lane"] == {
        "v3_primary_replay": 24,
        "live_llm_retrieval_topk": 24,
        "live_llm_query_bound_oracle": 24,
    }
    assert summary["all_track_non_target_context_expansion_query_ids"] == []
    assert summary["all_track_non_target_unexpected_change_count"] == 0

    expansion = expansion_rows[0]
    assert expansion["expansion_policy_name"] == "same_page_pdf_paragraph_line_window_v1"
    assert expansion["expansion_policy_version"] == "v1"
    assert expansion["expansion_attempted"] is True
    assert expansion["expansion_applied"] is True
    assert expansion["locator_safe_metadata_available"] is True
    assert expansion["source_pdf_path"] == row["denominator_locator"]["source_pdf_path"]
    assert expansion["document_version_id"] == row["denominator_locator"]["document_version_id"]
    assert expansion["original_cited_search_unit_ids"] == ["7bf516bf-2a17-4303-86d8-3cffaa04846e"]
    assert expansion["expanded_context_contains_all_audit_numeric_spans"] is True
    assert expansion["audit_numeric_spans_used_only_post_generation"] is True
    assert expansion["reference_span_text_embedded"] is False
    assert expansion["generation_used_expected_answer"] is False
    assert expansion["generation_used_supporting_evidence"] is False
    assert expansion["generation_used_gold_fields"] is False
    assert expansion["generated_answer_cited_expansion_unit_by_lane"] == {
        "live_llm_retrieval_topk": True,
        "live_llm_query_bound_oracle": True,
    }
    assert expansion["generated_answer_cited_original_search_unit_by_lane"] == {
        "live_llm_retrieval_topk": False,
        "live_llm_query_bound_oracle": False,
    }
    assert expansion["locator_validation_passed_by_lane"] == {
        "live_llm_retrieval_topk": True,
        "live_llm_query_bound_oracle": True,
    }
    assert expansion["expansion_unit_ids"] == ["pdfwin_b1c6527f848018640ad5ed231877c662"]
    for unit in expansion["expansion_units"]:
        assert unit["source_pdf_path"] == expansion["source_pdf_path"]
        assert unit["document_version_id"] == expansion["document_version_id"]
        assert unit["page"] == expansion["page"]
        assert unit["physical_page_index"] == expansion["physical_page_index"]
        assert unit["source"] == "pymupdf_source_pdf_same_page_line_window"
        assert unit["expansion_policy_version"] == "v1"
        assert unit["bbox"] == [63.65, 95.06, 341.94, 163.68]
        assert unit["region_type"] == "paragraph_window"
        assert isinstance(unit["bbox"], list) and len(unit["bbox"]) == 4
        assert unit["search_unit_id"].startswith("pdfwin_")
        assert unit["non_production_diagnostic_context_expansion"] is True
        assert unit["normalized_excerpt_sha256"]
    for lane_name in ("live_llm_retrieval_topk", "live_llm_query_bound_oracle"):
        lane = row["lane_results"][lane_name]
        assert lane["cited_search_unit_ids"] == ["pdfwin_b1c6527f848018640ad5ed231877c662"]
        citation_payload = lane["scored_citations"][0]["search_unit_citation_payload"]
        assert citation_payload["source_bound_official_denominator"] is False
        assert citation_payload["source_bound_diagnostic_context_expansion"] is True
        assert citation_payload["locator_schema"] == "pdf_source_bound_context_expansion_v1"

    assert remaining["items"] == []
    assert remaining["processed_query_ids"] == ["gq_auto_010"]
    assert remaining["strict_json_or_locator_residual_count"] == 0
    assert remaining["source_queue_artifact"] == summary["source_queue_artifact"]
    assert remaining["all_track_remeasurement_performed"] is True

    assert summary["behavior_change_made"] is True
    assert summary["context_expansion_attempted"] is True
    assert summary["context_expansion_applied"] is True
    assert summary["non_production_index_or_export_fix_applied"] is False
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["official_ndcg_computed"] is False
    assert summary["official_mrr_computed"] is False
    assert summary["official_hit_at_k_computed"] is False
    assert summary["lane_score_collapsed"] is False
    assert summary["all_track_residuals_after"]["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["all_track_residuals_after"]["xlsx_row_label_mismatch_count"] == 0
    assert summary["all_track_residuals_after"]["text_text_locator_missing_count"] == 0
    assert all(
        value == 0
        for value in summary["all_track_residuals_after"]["strict_json_parse_failure_count_by_lane"].values()
    )
    assert all(
        value == 0
        for value in summary["all_track_residuals_after"]["llm_generated_locator_copy_failure_count_by_lane"].values()
    )
    assert summary["artifact_policy"]["minimum_durable_artifacts"] == [
        "summary_json",
        "results_jsonl",
        "failure_attribution_json",
        "actual_response_audit_jsonl",
        "answer_span_diagnostics_jsonl",
        "context_expansion_diagnostics_jsonl",
        "remaining_triage_queue_json",
        "rag_current_eval_status_jsonl",
    ]
    for key in (
        "results_jsonl",
        "failure_attribution_json",
        "actual_response_audit_jsonl",
        "answer_span_diagnostics_jsonl",
        "context_expansion_diagnostics_jsonl",
        "remaining_triage_queue_json",
    ):
        assert key in summary["artifact_paths"]
        assert f"{key}_sha256" in summary["artifact_paths"]
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID}_summary.md").exists()

    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(answer_span_rows)
    assert_generation_guardrail_flags_false(expansion_rows)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(answer_span_rows)
    assert_no_gold_generation_source_fields(expansion_rows)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["context_expansion_applied"] is True
    assert measurement["all_track_pass_count_after_by_lane"] == summary["all_track_pass_count_after_by_lane"]


def test_v3_1_7_post_residual_queue_closure_inventory_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON)
    inventory_rows = read_jsonl(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_INVENTORY_JSONL)
    remaining = read_json(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_REMAINING_JSON)
    decision_packet = read_json(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_DECISION_PACKET_JSON)
    silver_audit = read_json(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SILVER_AUDIT_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    residual_query_ids = {
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    }
    lane_names = {"v3_primary_replay", "live_llm_retrieval_topk", "live_llm_query_bound_oracle"}

    assert summary["run_id"] == AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    assert summary["diagnostic_only"] is True
    assert summary["promotion_evidence"] is False
    assert summary["behavior_change_made"] is False
    assert summary["active_remaining_queue_empty"] is True
    assert summary["active_remaining_queue_status"] == "cleared"
    assert summary["closure_type"] == "diagnostic_queue_cleared_not_promotion"
    assert summary["source_closure_assertions"]["passed"] is True
    assert summary["all_track_live_generation_rerun"] is False
    assert summary["all_track_result_count_after"] == 29
    assert summary["all_track_reconstruction_matches_v3_1_6_summary"] is True
    assert summary["all_track_pass_count_after_by_lane"] == {
        "v3_primary_replay": 24,
        "live_llm_retrieval_topk": 24,
        "live_llm_query_bound_oracle": 24,
    }
    assert summary["all_track_non_pass_count_after_by_lane"] == {
        "v3_primary_replay": 5,
        "live_llm_retrieval_topk": 5,
        "live_llm_query_bound_oracle": 5,
    }
    assert summary["all_track_answer_span_mismatch_after_by_lane"] == {
        "v3_primary_replay": 0,
        "live_llm_retrieval_topk": 5,
        "live_llm_query_bound_oracle": 5,
    }
    assert set(summary["all_track_residual_query_ids"]) == residual_query_ids
    assert summary["residual_inventory_query_count"] == 5
    assert summary["residual_inventory_lane_item_count"] == 15
    assert summary["residual_inventory_bucket_counts"]["gold_policy_review_candidate"] == 15
    assert summary["residual_inventory_bucket_counts"]["implementation_safe_followup"] == 0
    assert summary["residual_inventory_bucket_counts"]["scorer_normalization_review_candidate"] == 3
    assert summary["any_residual_requires_user_decision"] is True
    assert summary["any_residual_safe_to_fix_without_user_decision"] is False
    assert summary["official_retrieval_metrics_still_blocked"] is True
    assert summary["next_phase"] == "gold_policy_review_packet_preparation"
    assert summary["non_binding_metric_readiness_memo"]["official_ndcg_mrr_hit_at_k_computed"] is False
    assert summary["non_binding_metric_readiness_memo"]["mmr_note"] == (
        "MMR is a retrieval/reranking strategy, not an evaluation metric."
    )
    assert summary["source_artifact_hash_audit"]["mismatch_count"] >= 1
    assert summary["source_artifact_hash_closure_passed"] is False

    assert len(inventory_rows) == 15
    assert {row["query_id"] for row in inventory_rows} == residual_query_ids
    assert {row["lane_name"] for row in inventory_rows} == lane_names
    assert {row["source_family"] for row in inventory_rows} == {"TEXT"}
    for row in inventory_rows:
        assert row["strict_json_parse_passed"] is True
        assert row["citation_locator_validation_passed"] is True
        assert row["citation_support_present"] is True
        assert row["failure_is_answer_span_related"] is True
        assert row["failure_is_gold_policy_related"] is True
        assert row["safe_to_fix_without_user_gold_decision"] is False
        assert row["requires_user_gold_policy_decision"] is True
        assert row["reference_span_text_embedded"] is False
        assert "gold_policy_review_candidate" in row["residual_buckets"]

    assert remaining["items"] == []
    assert remaining["active_implementation_queue_empty"] is True
    assert remaining["all_track_residuals_exist"] is True
    assert remaining["residuals_require_user_policy_review"] is True
    assert set(remaining["all_track_residual_query_ids"]) == residual_query_ids

    assert decision_packet["decision_item_count"] == 5
    assert {item["query_id"] for item in decision_packet["decision_items"]} == residual_query_ids
    for item in decision_packet["decision_items"]:
        assert item["safe_for_human_review_only"] is True
        assert item["raw_reference_text_embedded"] is False
        assert item["raw_supporting_text_embedded"] is False
        assert item["raw_gold_text_embedded"] is False
        assert item["safe_source_excerpt_hashes_counts"]

    assert silver_audit["silver_generation_closed"] is True
    assert silver_audit["silver_rows_created"] is False
    assert silver_audit["official_29_query_ids_excluded_from_silver_tuning_sets"] is True
    assert silver_audit["candidate_artifacts_excluded_as_generation_source"] is True
    assert silver_audit["silver_is_gold"] is False
    assert silver_audit["silver_is_official_denominator"] is False
    assert silver_audit["silver_is_promotion_evidence"] is False

    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(inventory_rows)
    assert_generation_guardrail_flags_false(remaining)
    assert_generation_guardrail_flags_false(decision_packet)
    assert_generation_guardrail_flags_false(silver_audit)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(inventory_rows)
    assert_no_gold_generation_source_fields(remaining)
    assert_no_gold_generation_source_fields(decision_packet)
    assert_no_gold_generation_source_fields(silver_audit)
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID}_summary.md").exists()

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID
    )
    assert measurement["diagnostic_only"] is True
    assert measurement["promotion_evidence"] is False
    assert measurement["active_remaining_queue_empty"] is True
    assert measurement["all_track_residuals_exist"] is True
    assert measurement["recommended_next_phase"] == "gold_policy_review_packet_preparation"
    assert measurement["official_retrieval_metrics_computed"] is False
    assert measurement["lane_score_collapsed"] is False


def test_v3_1_8_gold_policy_packet_preparation_is_compact_and_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_SUMMARY_JSON)
    packet = read_json(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_HUMAN_REVIEW_JSON)
    decision_rows = read_jsonl(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_DECISION_MATRIX_JSONL)
    remaining = read_json(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_REMAINING_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    residual_query_ids = [
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    ]
    decision_options = [
        "keep_current_strict_reference_boundary",
        "approve_scorer_or_renderer_review_without_gold_mutation",
        "revise_gold_or_label_policy",
    ]

    assert summary["run_id"] == AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID
    assert summary["diagnostic_only"] is True
    assert summary["promotion_evidence"] is False
    assert summary["behavior_change_made"] is False
    assert summary["production_mutation"] is False
    assert summary["denominator_mutation"] is False
    assert summary["gold_mutation"] is False
    assert summary["human_label_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["relevance_label_mutation"] is False
    assert summary["answerability_label_mutation"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["candidate_artifacts_as_generation_source"] is False
    assert summary["official_ndcg_computed"] is False
    assert summary["official_mrr_computed"] is False
    assert summary["official_hit_at_k_computed"] is False
    assert summary["lane_score_collapsed"] is False
    assert summary["all_track_live_generation_rerun"] is False
    assert summary["active_implementation_queue_empty"] is True
    assert summary["implementation_safe_residual_count"] == 0
    assert summary["decision_item_count"] == 5
    assert summary["decision_query_ids"] == residual_query_ids
    assert summary["decision_options"] == decision_options
    assert summary["metadata_drift_observed"] is True
    assert summary["source_artifact_hash_closure_required_for_policy_packet"] is False
    assert summary["silver_generation_closed"] is True
    assert summary["silver_rows_created"] is False
    assert summary["human_review_packet_contains_policy_material"] is True
    assert summary["raw_reference_text_embedded_in_generation"] is False
    assert summary["raw_supporting_text_embedded_in_generation"] is False
    assert summary["raw_gold_text_embedded_in_generation"] is False

    assert set(summary["artifact_paths"]) == {
        "summary_json",
        "human_review_packet_json",
        "human_review_packet_json_sha256",
        "decision_matrix_jsonl",
        "decision_matrix_jsonl_sha256",
        "remaining_triage_queue_json",
        "remaining_triage_queue_json_sha256",
        "status_jsonl",
    }
    assert summary["artifact_policy"]["classification_only_minimum_artifact_set"] == [
        "summary_json",
        "human_review_packet_json",
        "decision_matrix_jsonl",
        "remaining_triage_queue_json",
        "status_jsonl",
    ]
    assert summary["artifact_policy"]["full_results_jsonl_created"] is False
    assert summary["artifact_policy"]["failure_attribution_json_created"] is False
    assert summary["artifact_policy"]["actual_response_audit_jsonl_created"] is False
    assert summary["artifact_policy"]["per_run_markdown_report_created"] is False
    for forbidden_key in (
        "results_jsonl",
        "failure_attribution_json",
        "actual_response_audit_jsonl",
        "summary_md",
    ):
        assert forbidden_key not in summary["artifact_paths"]
    for suffix in ("results.jsonl", "failure.json", "audit.jsonl", "summary.md"):
        assert not report_artifact_path(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID, suffix).exists()

    assert packet["decision_item_count"] == 5
    assert [item["query_id"] for item in packet["decision_items"]] == residual_query_ids
    assert packet["decision_options"] == decision_options
    assert packet["human_review_packet_contains_policy_material"] is True
    assert packet["generation_source"] is False
    assert packet["raw_reference_text_embedded_in_generation"] is False
    assert packet["raw_supporting_text_embedded_in_generation"] is False
    assert packet["raw_gold_text_embedded_in_generation"] is False
    for item in packet["decision_items"]:
        assert item["source_family"] == "TEXT"
        assert item["policy_decision_options"] == decision_options
        assert item["requires_user_policy_decision"] is True
        assert item["requires_user_gold_policy_decision"] is True
        assert item["requires_user_relevance_label_decision"] is True
        assert item["requires_user_answerability_label_decision"] is True
        assert item["implementation_safe"] is False
        assert item["raw_reference_text_included"] is True
        assert item["raw_supporting_text_included"] is True
        assert item["raw_gold_text_included"] is True
        assert item["human_review_only"] is True
        assert item["generation_source"] is False
        assert item["not_silver_source"] is True
        assert item["not_gold_mutation"] is True
        assert item["policy_material_excluded_from_generation"] is True
        assert len(item["lane_level_status"]) == 3
        for lane in item["lane_level_status"]:
            assert lane["current_generated_answer"]
            assert lane["generation_source"] is False
            assert lane["human_review_only"] is True
            assert lane["citation_locator_validation_passed"] is True
            locator = lane["citation_locator_search_unit_metadata"]
            assert locator["search_unit_id"]
            assert locator["document_version_id"]
            assert locator["text_locator"]["chunk_id"]
            assert lane["scoring_reference_span_information"]["scoring_reference_span_sha256"]
        material = item["current_policy_material"]
        for key in ("expected_answer", "supporting_evidence"):
            assert material[key]["text"]
            assert material[key]["sha256"]
            assert material[key]["human_review_only"] is True
            assert material[key]["generation_source"] is False
            assert material[key]["not_silver_source"] is True
            assert material[key]["not_gold_mutation"] is True

    assert len(decision_rows) == 5
    assert [row["query_id"] for row in decision_rows] == residual_query_ids
    for row in decision_rows:
        assert row["decision_options"] == decision_options
        assert row["requires_user_policy_decision"] is True
        assert row["implementation_safe"] is False
        assert row["policy_material_generation_source"] is False
        assert row["human_review_only_policy_material_included"] is True

    assert remaining["items"] == []
    assert remaining["active_implementation_queue_empty"] is True
    assert remaining["implementation_safe_residual_count"] == 0
    assert remaining["policy_review_query_ids"] == residual_query_ids
    assert remaining["residuals_require_user_policy_review"] is True

    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(packet)
    assert_generation_guardrail_flags_false(decision_rows)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(decision_rows)
    assert_no_gold_generation_source_fields(remaining)

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID
    )
    assert measurement["diagnostic_only"] is True
    assert measurement["promotion_evidence"] is False
    assert measurement["decision_item_count"] == 5
    assert measurement["decision_query_ids"] == residual_query_ids
    assert measurement["implementation_safe_residual_count"] == 0
    assert measurement["human_review_packet_contains_policy_material"] is True
    assert measurement["raw_reference_text_embedded_in_generation"] is False
    assert measurement["official_ndcg_computed"] is False
    assert measurement["lane_score_collapsed"] is False


def test_v3_1_9_user_gold_policy_override_application_and_rescore_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_SUMMARY_JSON)
    applied_rows = read_jsonl(AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_APPLIED_JSONL)
    diff_rows = read_jsonl(AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_DIFF_JSONL)
    rescored_rows = read_jsonl(AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RESCORED_JSONL)
    remaining = read_json(AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_REMAINING_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    override_query_ids = [
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    ]
    lane_names = ["v3_primary_replay", "live_llm_retrieval_topk", "live_llm_query_bound_oracle"]

    assert summary["run_id"] == AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID
    assert summary["run_class"] == "user_approved_gold_policy_override_application"
    assert summary["diagnostic_only"] is False
    assert summary["user_assertion_count"] == 30
    assert summary["override_source_found"] == "ai/eval/reports/rag-ingestion/gold_overrides.csv"
    assert summary["human_approved_override_source"] == "gold_overrides.csv"
    assert summary["optional_jsonl_override_source_validated"] is True
    assert summary["gold_application_mode"] == "v2_csv_in_place"
    assert summary["gold_versioning_decision"]["selected_path"] == "update_v2_csv_in_place"
    assert summary["override_query_ids"] == override_query_ids
    assert summary["changed_query_ids"] == override_query_ids
    assert summary["changed_row_count"] == 5
    assert summary["changed_rows_by_source_family"] == {"TEXT": 5}
    assert summary["non_text_changed_query_ids"] == []
    assert summary["text_namu_v2_0005_unchanged"] is True
    assert summary["official_denominator_row_count"] == 29
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["official_denominator_query_ids_before"] == summary["official_denominator_query_ids_after"]
    assert len(summary["official_denominator_query_ids_after"]) == 29

    assert summary["user_policy_decision_applied"] is True
    assert summary["expected_answer_mutation"] is True
    assert summary["supporting_evidence_mutation"] is True
    assert summary["gold_policy_mutation"] is True
    assert summary["gold_mutation"] is True
    assert summary["behavior_change_made"] is False
    assert summary["renderer_mutation"] is False
    assert summary["scorer_behavior_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["denominator_query_id_set_mutation"] is False
    assert summary["candidate_artifacts_as_generation_source"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["promotion_evidence"] is False
    assert summary["silver_rows_created"] is False
    assert summary["official_ndcg_computed"] is False
    assert summary["official_mrr_computed"] is False
    assert summary["official_hit_at_k_computed"] is False
    assert summary["lane_score_collapsed"] is False
    assert summary["live_generation_rerun"] is False
    assert summary["all_track_live_generation_rerun"] is False

    assert summary["gold_file_before_sha256"] == "03764d1d7aa682cd8646d9028b6219fdbeba8a4eb219a87a285a162f16702cd6"
    assert summary["gold_file_after_sha256"] == sha256_file(
        ROOT / "ai" / "eval" / "eval_queries" / "gold_queries_text_namu_v2_1_question_gold_v2.csv"
    )
    assert summary["gold_file_before_sha256"] != summary["gold_file_after_sha256"]

    assert summary["lane_names"] == lane_names
    assert set(summary["lane_pass_counts_before"]) == set(lane_names)
    assert set(summary["lane_pass_counts_after"]) == set(lane_names)
    assert summary["lane_pass_counts_before"] == {
        "v3_primary_replay": 24,
        "live_llm_retrieval_topk": 24,
        "live_llm_query_bound_oracle": 24,
    }
    assert summary["rescored_result_count"] == 29
    assert summary["rescored_query_id_count"] == 29
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["remaining_queue"]["implementation_safe_residual_count"] == remaining[
        "implementation_safe_residual_count"
    ]

    assert len(applied_rows) == 5
    assert [row["query_id"] for row in applied_rows] == override_query_ids
    for row in applied_rows:
        assert row["codex_policy_option"] == "revise_gold_or_label_policy"
        assert row["apply_to_official_gold"] is True
        assert row["user_policy_decision_applied"] is True
        assert row["expected_answer_final"]
        assert row["supporting_evidence_final"]
        assert row["expected_answer_sha256"] == sha256_text(row["expected_answer_final"])
        assert row["supporting_evidence_sha256"] == sha256_text(row["supporting_evidence_final"])
        assert row["human_review_only"] is True
        assert row["generation_source"] is False
        assert row["not_silver_source"] is True
        assert row["not_promotion_evidence"] is True

    assert len(diff_rows) == 5
    assert [row["query_id"] for row in diff_rows] == override_query_ids
    for row in diff_rows:
        assert row["source_family"] == "TEXT"
        assert row["changed_fields"] == ["expected_answer", "supporting_evidence"]
        for field in ("expected_answer", "supporting_evidence"):
            diff = row["field_diffs"][field]
            assert diff["before_text"]
            assert diff["after_text"]
            assert diff["before_sha256"]
            assert diff["after_sha256"]
            assert diff["before_sha256"] != diff["after_sha256"] or row["query_id"] == "text_namu_v2_0017"
            assert diff["human_review_only"] is True
            assert diff["generation_source"] is False
            assert diff["not_silver_source"] is True
            assert diff["user_policy_source"] is True

    assert len(rescored_rows) == 29
    assert {row["query_id"] for row in rescored_rows} == set(summary["official_denominator_query_ids_after"])
    for row in rescored_rows:
        assert set(row["lane_results"]) == set(lane_names)
        assert row["generation_used_expected_answer"] is False
        assert row["generation_used_supporting_evidence"] is False
        assert row["generation_used_gold_fields"] is False
        assert row["candidate_artifacts_as_generation_source"] is False
        for lane_name, lane in row["lane_results"].items():
            assert lane_name in lane_names
            assert lane["scoring_only_remeasurement"] is True
            assert lane["live_generation_rerun"] is False
            assert lane["scorer_behavior_mutation"] is False

    assert remaining["run_id"] == AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID
    assert remaining["source_run_id"] == AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID
    assert remaining["user_policy_decision_applied"] is True
    assert remaining["requires_additional_user_policy_packet"] is False
    assert remaining["promotion_evidence"] is False
    assert remaining["silver_rows_created"] is False
    for item in remaining["items"]:
        assert item["implementation_safe"] is True
        assert item["requires_user_gold_policy_decision"] is False

    assert set(summary["artifact_paths"]) == {
        "summary_json",
        "applied_overrides_jsonl",
        "applied_overrides_jsonl_sha256",
        "gold_diff_jsonl",
        "gold_diff_jsonl_sha256",
        "rescored_results_jsonl",
        "rescored_results_jsonl_sha256",
        "remaining_triage_queue_json",
        "remaining_triage_queue_json_sha256",
        "status_jsonl",
    }

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID
    )
    assert measurement["run_class"] == "user_approved_gold_policy_override_application"
    assert measurement["user_policy_decision_applied"] is True
    assert measurement["gold_policy_mutation"] is True
    assert measurement["behavior_change_made"] is False
    assert measurement["promotion_evidence"] is False
    assert measurement["silver_rows_created"] is False


def test_v3_1_9_gold_csv_contains_only_the_user_approved_text_overrides() -> None:
    summary = read_json(AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_SUMMARY_JSON)
    applied_rows = read_jsonl(AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_APPLIED_JSONL)
    gold_rows = {
        row["query_id"]: row
        for row in read_csv(ROOT / "ai" / "eval" / "eval_queries" / "gold_queries_text_namu_v2_1_question_gold_v2.csv")
    }

    assert set(gold_rows) == {
        "text_namu_v2_0005",
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    }
    assert summary["text_namu_v2_0005_unchanged"] is True
    assert sha256_text(
        "\n".join(
            [
                gold_rows["text_namu_v2_0005"]["expected_answer"],
                gold_rows["text_namu_v2_0005"]["supporting_evidence"],
                gold_rows["text_namu_v2_0005"]["citation_locator"],
            ]
        )
    ) == summary["text_namu_v2_0005_after_row_core_sha256"]

    for override in applied_rows:
        gold_row = gold_rows[override["query_id"]]
        assert gold_row["expected_answer"] == override["expected_answer_final"]
        assert gold_row["supporting_evidence"] == override["supporting_evidence_final"]
        assert gold_row["citation_locator"] == override["current_citation_locator"]
        assert gold_row["human_label"] == override["preserved_gold_fields"]["human_label"]
        assert gold_row["human_review_status"] == override["preserved_gold_fields"]["human_review_status"]
        assert gold_row["official_denominator_current"] == override["preserved_gold_fields"][
            "official_denominator_current"
        ]
        assert gold_row["official_metric_input"] == override["preserved_gold_fields"]["official_metric_input"]
        assert gold_row["gold_promoted"] == override["preserved_gold_fields"]["gold_promoted"]

    assert summary["pdf_rows_changed"] == 0
    assert summary["xlsx_rows_changed"] == 0
    assert summary["official_denominator_query_id_set_mutation"] is False


def test_v3_2_0_current_system_live_baseline_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_2_0_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_2_0_RESULTS)
    attribution = read_json(AGENTIC_V3_2_0_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_2_0_AUDIT_JSONL)
    queue = read_json(AGENTIC_V3_2_0_QUEUE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_9_GOLD_POLICY_OVERRIDE_RUN_ID
    assert summary["measurement_classification"] == "post_gold_settled_current_system_live_baseline_v3_2_0"
    assert summary["status"] == "CURRENT_SYSTEM_LIVE_BASELINE_V3_2_0_COMPLETED"
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert len(results) == 29
    assert len(audit_rows) == 29
    assert summary["rows_by_source_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}
    assert set(summary["lane_counts"]) == {"v3_primary_replay", "live_llm_retrieval_topk", "live_llm_query_bound_oracle"}
    assert summary["lane_counts"]["v3_primary_replay"]["pass_count"] == 24
    assert summary["lane_counts"]["live_llm_retrieval_topk"]["pass_count"] == 25
    assert summary["lane_counts"]["live_llm_query_bound_oracle"]["pass_count"] == 24
    assert summary["answer_quality_metrics"]["by_lane"]["live_llm_retrieval_topk"]["average"] == 0.8621
    assert all(metric["average"] == 1.0 for metric in summary["citation_quality_metrics"]["by_lane"].values())
    assert summary["retrieval_ranking_metrics"]["status"] == "deferred"
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["official_ndcg_computed"] is False
    assert summary["official_mrr_computed"] is False
    assert summary["official_hit_at_k_computed"] is False
    assert summary["lane_score_collapsed"] is False
    assert summary["write_summary_markdown"] is False
    assert summary["write_side_markdown"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["relevance_label_mutation"] is False
    assert summary["answerability_label_mutation"] is False
    assert attribution["run_id"] == AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID
    assert queue["run_id"] == AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID
    )
    assert measurement["retrieval_ranking_metrics"]["status"] == "deferred"
    assert measurement["lane_score_collapsed"] is False
    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(queue)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(queue)


def test_v3_2_1_text_residual_triage_and_scorer_policy_are_guarded() -> None:
    summary = read_json(AGENTIC_V3_2_1_SUMMARY_JSON)
    rows = read_jsonl(AGENTIC_V3_2_1_RESIDUAL_TRIAGE_JSONL)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    target_ids = [
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    ]
    assert summary["run_id"] == AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID
    assert summary["status"] == "TEXT_RESIDUAL_TRIAGE_V3_2_1_COMPLETED"
    assert summary["target_query_ids"] == target_ids
    assert summary["result_count"] == 4
    assert [row["row_id"] for row in rows] == target_ids
    assert summary["primary_category_counts"] == {"prompt": 3, "scorer": 1}
    by_id = {row["row_id"]: row for row in rows}
    assert by_id["text_namu_v2_0077"]["primary_category"] == "scorer"
    assert by_id["text_namu_v2_0077"]["secondary_category"] == "prompt"
    assert by_id["text_namu_v2_0077"]["action_taken"].startswith("implementation_fix_applied:")
    assert by_id["text_namu_v2_0014"]["primary_category"] == "prompt"
    assert by_id["text_namu_v2_0017"]["secondary_category"] == "scorer"
    assert by_id["text_namu_v2_0084"]["primary_category"] == "prompt"
    assert all(
        row["evidence_artifact"]
        == report_artifact_repo_relative(
            AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID,
            "results.jsonl",
        )
        for row in rows
    )
    assert summary["implementation_change_made"] is True
    assert summary["v3_2_2_required"] is True
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["relevance_label_mutation"] is False
    assert summary["answerability_label_mutation"] is False
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["lane_score_collapsed"] is False

    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    assert runner.source_bound_answer_equivalent_to_reference(
        row={
            "query_id": "text_namu_v2_0077",
            "question": "미츠하는 타키를 만나려고 어디로 향했어",
            "expected_answer": "도쿄로 향했습니다.",
            "_active_scorer_policies": [runner.V3_2_1_KOREAN_POLITE_PAST_SCORER_POLICY],
        },
        expected_answer="도쿄로 향했습니다.",
        generated_answer="미츠하는 타키를 만나기 위해 도쿄로 향했다.",
    )
    assert not runner.source_bound_answer_equivalent_to_reference(
        row={
            "query_id": "text_namu_v2_0077",
            "question": "미츠하는 타키를 만나려고 어디로 향했어",
            "expected_answer": "도쿄로 향했습니다.",
        },
        expected_answer="도쿄로 향했습니다.",
        generated_answer="미츠하는 타키를 만나기 위해 도쿄로 향했다.",
    )
    assert not runner.source_bound_answer_equivalent_to_reference(
        row={
            "query_id": "not_target",
            "question": "테스트했어",
            "expected_answer": "테스트했습니다.",
        },
        expected_answer="테스트했습니다.",
        generated_answer="테스트했다",
    )

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID
    )
    assert measurement["source_run_id"] == AGENTIC_V3_2_0_CURRENT_SYSTEM_LIVE_BASELINE_RUN_ID
    assert measurement["v3_2_2_required"] is True
    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(rows)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(rows)


def test_v3_2_2_post_fix_remeasurement_compares_only_intended_scorer_delta() -> None:
    summary = read_json(AGENTIC_V3_2_2_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_2_2_RESULTS)
    attribution = read_json(AGENTIC_V3_2_2_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_2_2_AUDIT_JSONL)
    queue = read_json(AGENTIC_V3_2_2_QUEUE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_2_1_TEXT_RESIDUAL_TRIAGE_RUN_ID
    assert summary["measurement_classification"] == "post_fix_full_remeasurement_v3_2_2"
    assert summary["status"] == "POST_FIX_REMEASUREMENT_V3_2_2_COMPLETED"
    assert len(results) == 29
    assert summary["lane_counts"]["v3_primary_replay"]["pass_count"] == 24
    assert summary["lane_counts"]["live_llm_retrieval_topk"]["pass_count"] == 26
    assert summary["lane_counts"]["live_llm_query_bound_oracle"]["pass_count"] == 25
    comparison = summary["comparison_to_v3_2_0"]
    assert comparison["lane_pass_count_delta"] == {
        "live_llm_query_bound_oracle": 1,
        "live_llm_retrieval_topk": 1,
        "v3_primary_replay": 0,
    }
    assert comparison["unexpected_failure_category_change_count"] == 0
    assert {
        (item["query_id"], item["lane_name"], item["before_failure_category"], item["after_failure_category"])
        for item in comparison["failure_category_changes"]
    } == {
        ("text_namu_v2_0077", "live_llm_retrieval_topk", "LLM_EXPECTED_SPAN_MISMATCH", "PASS"),
        ("text_namu_v2_0077", "live_llm_query_bound_oracle", "LLM_EXPECTED_SPAN_MISMATCH", "PASS"),
    }
    row_0077 = next(row for row in results if row["query_id"] == "text_namu_v2_0077")
    assert row_0077["lane_results"]["live_llm_retrieval_topk"]["failure_category"] == "PASS"
    assert row_0077["lane_results"]["live_llm_query_bound_oracle"]["failure_category"] == "PASS"
    assert row_0077["lane_results"]["v3_primary_replay"]["failure_category"] == "LLM_TRUE_PARTIAL_SYNTHESIS"
    assert summary["retrieval_ranking_metrics"]["status"] == "deferred"
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["lane_score_collapsed"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert attribution["run_id"] == AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID
    assert queue["run_id"] == AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID
    )
    assert measurement["comparison_to_v3_2_0"]["unexpected_failure_category_change_count"] == 0
    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(queue)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(queue)


def test_v3_2_3_queue_lane_actionability_reconciliation_is_compact_and_guarded() -> None:
    summary = read_json(AGENTIC_V3_2_3_SUMMARY_JSON)
    diagnostics = read_jsonl(AGENTIC_V3_2_3_DIAGNOSTICS_JSONL)
    queue = read_json(AGENTIC_V3_2_3_QUEUE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID
    assert summary["status"] == "QUEUE_LANE_ACTIONABILITY_RECONCILIATION_V3_2_3_COMPLETED"
    assert summary["measurement_classification"] == "queue_lane_actionability_reconciliation_v3_2_3_no_behavior_change"
    assert summary["run_class"] == "classification_only_queue_lane_actionability_reconciliation"
    assert summary["source_queue_query_count"] == 6
    assert summary["source_lane_residual_count"] == 12
    assert summary["actionability_bucket_counts"] == {
        "frozen_replay_residual": 2,
        "pdf_context_provenance": 1,
        "text_prompt_span": 3,
    }
    assert summary["next_phase_counts"] == {
        "none": 2,
        "v3_2_4_pdf_context_provenance": 1,
        "v3_2_6_text_prompt_span_rule": 3,
    }
    assert summary["lane_a_only_query_ids"] == ["text_namu_v2_0012", "text_namu_v2_0077"]
    assert summary["live_bc_actionable_query_ids"] == [
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0084",
        "gq_auto_010",
    ]
    assert summary["v3_2_4_required"] is True
    assert summary["v3_2_4_scope_query_ids"] == ["gq_auto_010"]
    assert summary["v3_2_5_required"] is False
    assert summary["v3_2_5_decision"] == (
        "deferred_until_v3_2_4_proves_v3_1_6_expansion_missing_from_v3_2_measurement_path"
    )
    assert summary["v3_2_6_required"] is True
    assert summary["v3_2_6_scope_query_ids"] == [
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0084",
    ]
    assert summary["artifact_policy"]["per_run_markdown_written"] is False
    assert summary["artifact_policy"]["results_jsonl_written"] is False
    assert summary["artifact_policy"]["failure_attribution_json_written"] is False
    assert summary["artifact_policy"]["audit_jsonl_written"] is False

    assert len(diagnostics) == 6
    by_id = {row["query_id"]: row for row in diagnostics}
    assert set(by_id) == {
        "gq_auto_010",
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    }
    assert by_id["text_namu_v2_0012"]["lane_a_only"] is True
    assert by_id["text_namu_v2_0012"]["live_bc_actionable"] is False
    assert by_id["text_namu_v2_0012"]["primary_bucket"] == "frozen_replay_residual"
    assert by_id["text_namu_v2_0077"]["lane_a_only"] is True
    assert by_id["text_namu_v2_0077"]["live_bc_actionable"] is False
    assert by_id["text_namu_v2_0077"]["primary_bucket"] == "frozen_replay_residual"
    assert by_id["text_namu_v2_0077"]["passing_lanes"] == [
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    ]
    assert by_id["gq_auto_010"]["source_family"] == "PDF"
    assert by_id["gq_auto_010"]["primary_bucket"] == "pdf_context_provenance"
    assert by_id["gq_auto_010"]["next_phase"] == "v3_2_4_pdf_context_provenance"
    assert by_id["gq_auto_010"]["failing_lanes"] == [
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    ]
    assert "TEXT prompt residual" not in by_id["gq_auto_010"]["rationale"]
    assert {
        query_id
        for query_id, row in by_id.items()
        if row["next_phase"] == "v3_2_6_text_prompt_span_rule"
    } == {"text_namu_v2_0014", "text_namu_v2_0017", "text_namu_v2_0084"}

    assert queue["run_id"] == AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID
    assert [item["query_id"] for item in queue["items"]] == [
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
        "gq_auto_010",
    ]
    assert [item["query_id"] for item in queue["active_items"]] == [
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0084",
        "gq_auto_010",
    ]
    assert [item["query_id"] for item in queue["carried_non_actionable_lane_items"]] == [
        "text_namu_v2_0012",
        "text_namu_v2_0077",
    ]

    for suffix in (
        "results.jsonl",
        "failure.json",
        "audit.jsonl",
        "summary.md",
        "queue.md",
        "audit.md",
    ):
        assert not report_artifact_path(AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID, suffix).exists()

    for payload in (summary, *diagnostics, queue):
        assert payload["diagnostic_only"] is True
        assert payload["promotion_evidence"] is False
        assert payload["generation_used_expected_answer"] is False
        assert payload["generation_used_supporting_evidence"] is False
        assert payload["generation_used_gold_fields"] is False
        assert payload["official_retrieval_metrics_computed"] is False

    for field in (
        "behavior_change_made",
        "implementation_change_made",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "relevance_label_mutation",
        "answerability_label_mutation",
        "official_denominator_query_id_set_mutation",
        "retrieval_mutation",
        "renderer_mutation",
        "scorer_behavior_mutation",
        "live_generation_rerun",
        "lane_score_collapsed",
    ):
        assert summary[field] is False, field
        assert queue["guardrails"][field] is False, field

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID
    )
    assert measurement["source_run_id"] == AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID
    assert measurement["source_queue_query_count"] == 6
    assert measurement["source_lane_residual_count"] == 12
    assert measurement["v3_2_4_required"] is True
    assert measurement["v3_2_5_required"] is False
    assert measurement["v3_2_6_required"] is True
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(queue)


def test_v3_2_4_gq_auto_010_pdf_context_provenance_is_compact_no_behavior_and_source_bound() -> None:
    summary = read_json(AGENTIC_V3_2_4_SUMMARY_JSON)
    diagnostics = read_jsonl(AGENTIC_V3_2_4_DIAGNOSTICS_JSONL)
    queue = read_json(AGENTIC_V3_2_4_QUEUE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID
    assert summary["target_query_ids"] == ["gq_auto_010"]
    assert summary["status"] == "GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_DIAGNOSTIC_V3_2_4_COMPLETED"
    assert summary["measurement_classification"] == (
        "gq_auto_010_pdf_context_provenance_diagnostic_v3_2_4_no_behavior_change"
    )
    assert summary["run_class"] == "classification_only_pdf_context_provenance_diagnostic"
    assert summary["classification"] == "open_because_v3_1_6_expansion_not_wired_into_v3_2_measurement"
    assert summary["current_failing_lanes"] == ["live_llm_retrieval_topk", "live_llm_query_bound_oracle"]
    assert summary["current_passing_lanes"] == ["v3_primary_replay"]
    assert summary["v3_2_2_retrieval_context_source_run_id"] == AGENTIC_V3_RUN_ID
    assert summary["v3_2_2_retrieval_context_rerun"] is False
    assert summary["v3_2_2_retrieval_context_rerun_false_affected_measurement"] is True
    assert summary["pdfwin_search_unit_id"] == "pdfwin_b1c6527f848018640ad5ed231877c662"
    assert summary["pdfwin_present_in_current_prompt_context"] is False
    assert summary["pdfwin_present_in_v3_1_6_artifact_lineage"] is True
    assert summary["current_prompt_context_contains_numeric_answer_span"] is False
    assert summary["v3_1_5_classification"] == "query_bound_searchunit_too_narrow"
    assert summary["v3_1_5_raw_source_pdf_text_contains_numeric_span"] is True
    assert summary["v3_1_5_current_cited_searchunit_contains_numeric_span"] is False
    assert summary["v3_1_6_expansion_applied"] is True
    assert summary["v3_1_6_expansion_unit_ids"] == ["pdfwin_b1c6527f848018640ad5ed231877c662"]
    assert summary["v3_1_6_expanded_context_contains_numeric_span"] is True
    assert summary["expanded_context_present_in_current_v3_2_2_context"] is False
    assert summary["live_llm_span_selection_despite_expanded_context_present"] is False
    assert summary["measurement_artifact_mismatch_detected"] is False
    assert summary["index_or_export_rebuild_required"] is False
    assert summary["v3_2_5_implementation_needed"] is True
    assert summary["v3_2_5_implementation_surface"] == "measurement_source_selection_and_context_assembly_overlay"
    assert summary["recommended_next_phase"] == (
        "v3_2_5_wire_v3_1_6_pdf_window_expansion_into_v3_2_measurement"
    )
    assert summary["artifact_policy"]["per_run_markdown_written"] is False
    assert summary["artifact_policy"]["results_jsonl_written"] is False
    assert summary["artifact_policy"]["failure_attribution_json_written"] is False
    assert summary["artifact_policy"]["audit_jsonl_written"] is False

    assert len(diagnostics) == 1
    row = diagnostics[0]
    assert row["query_id"] == "gq_auto_010"
    assert row["classification"] == summary["classification"]
    assert row["current_cited_search_unit_ids_by_lane"] == {
        "live_llm_query_bound_oracle": ["7bf516bf-2a17-4303-86d8-3cffaa04846e"],
        "live_llm_retrieval_topk": ["7bf516bf-2a17-4303-86d8-3cffaa04846e"],
    }
    assert row["pdfwin_present_in_current_lane_payload_by_lane"] == {
        "live_llm_query_bound_oracle": False,
        "live_llm_retrieval_topk": False,
    }
    assert row["current_lane_context_contains_numeric_answer_span_by_lane"] == {
        "live_llm_query_bound_oracle": False,
        "live_llm_retrieval_topk": False,
    }
    assert row["v3_1_6_after_lane_failure_categories"]["live_llm_query_bound_oracle"] == "PASS"
    assert row["v3_1_6_after_lane_failure_categories"]["live_llm_retrieval_topk"] == "PASS"

    assert queue["run_id"] == AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID
    assert queue["classification"] == summary["classification"]
    assert queue["remaining_recommended_queue_query_ids"] == ["gq_auto_010"]
    assert queue["v3_2_5_required"] is True
    assert queue["items"][0]["implementation_surface"] == "measurement_source_selection_and_context_assembly_overlay"
    assert queue["items"][0]["index_or_export_rebuild_required"] is False

    for suffix in (
        "results.jsonl",
        "failure.json",
        "audit.jsonl",
        "summary.md",
        "queue.md",
        "audit.md",
    ):
        assert not report_artifact_path(AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID, suffix).exists()

    for payload in (summary, row, queue):
        assert payload["diagnostic_only"] is True
        assert payload["promotion_evidence"] is False
        assert payload["generation_used_expected_answer"] is False
        assert payload["generation_used_supporting_evidence"] is False
        assert payload["generation_used_gold_fields"] is False
        assert payload["official_retrieval_metrics_computed"] is False

    for field in (
        "behavior_change_made",
        "implementation_change_made",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "relevance_label_mutation",
        "answerability_label_mutation",
        "official_denominator_query_id_set_mutation",
        "retrieval_mutation",
        "renderer_mutation",
        "scorer_behavior_mutation",
        "live_generation_rerun",
        "retrieval_context_rerun",
        "index_or_export_rebuild_performed",
        "lane_score_collapsed",
    ):
        assert summary[field] is False, field
        assert queue["guardrails"][field] is False, field

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID
    )
    assert measurement["classification"] == summary["classification"]
    assert measurement["v3_2_5_required"] is True
    assert measurement["v3_2_5_implementation_surface"] == "measurement_source_selection_and_context_assembly_overlay"
    assert measurement["index_or_export_rebuild_required"] is False
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(queue)


def test_v3_2_5_gq_auto_010_pdf_context_reconciliation_full_remeasurement_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_2_5_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_2_5_RESULTS)
    attribution = read_json(AGENTIC_V3_2_5_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_2_5_AUDIT_JSONL)
    diagnostics = read_jsonl(AGENTIC_V3_2_5_PDF_CONTEXT_DIAGNOSTICS_JSONL)
    queue = read_json(AGENTIC_V3_2_5_QUEUE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_2_4_GQ_AUTO_010_PDF_CONTEXT_PROVENANCE_RUN_ID
    assert summary["status"] == "GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_FIX_V3_2_5_COMPLETED"
    assert summary["measurement_classification"] == "gq_auto_010_pdf_context_reconciliation_fix_v3_2_5"
    assert summary["run_class"] == "implementation_safe_pdf_context_reconciliation_full_remeasurement"
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert summary["denominator_policy"] == {
        "row_count": 29,
        "rows_by_source_family": {"PDF": 4, "TEXT": 6, "XLSX": 19},
        "source": "current official denominator registry and settled gold CSVs",
        "denominator_mutation": False,
        "query_id_set_mutation": False,
    }
    assert len(results) == 29
    assert len(audit_rows) == 29
    assert len(diagnostics) == 1
    assert attribution["run_id"] == AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID

    assert {lane: summary["lane_counts"][lane]["pass_count"] for lane in summary["lane_counts"]} == {
        "live_llm_query_bound_oracle": 26,
        "live_llm_retrieval_topk": 27,
        "v3_primary_replay": 24,
    }
    assert {lane: summary["citation_quality_metrics"]["by_lane"][lane]["average"] for lane in summary["lane_counts"]} == {
        "live_llm_query_bound_oracle": 1.0,
        "live_llm_retrieval_topk": 1.0,
        "v3_primary_replay": 1.0,
    }
    comparison = summary["comparison_to_v3_2_2"]
    assert comparison["lane_pass_counts_before"] == {
        "live_llm_query_bound_oracle": 25,
        "live_llm_retrieval_topk": 26,
        "v3_primary_replay": 24,
    }
    assert comparison["lane_pass_counts_after"] == {
        "live_llm_query_bound_oracle": 26,
        "live_llm_retrieval_topk": 27,
        "v3_primary_replay": 24,
    }
    assert comparison["lane_pass_count_delta"] == {
        "live_llm_query_bound_oracle": 1,
        "live_llm_retrieval_topk": 1,
        "v3_primary_replay": 0,
    }
    assert comparison["expected_failure_category_change_count"] == 2
    assert comparison["unexpected_failure_category_change_count"] == 0
    assert comparison["gq_auto_010_lane_bc_passed"] is True
    assert comparison["citation_support_averages_all_one"] is True
    assert comparison["denominator_policy"]["rows_by_source_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}

    assert summary["strict_json_parse_failure_count_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 0,
    }
    assert summary["llm_generated_locator_copy_failure_count_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 0,
    }
    assert summary["llm_generated_locator_missing_failure_count_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 0,
    }
    assert summary["llm_generated_locator_field_mismatch_failure_count_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 0,
    }
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0

    assert summary["context_expansion_applied_query_ids"] == ["gq_auto_010"]
    assert summary["context_expansion_unit_ids"] == ["pdfwin_b1c6527f848018640ad5ed231877c662"]
    assert summary["context_expansion_source_run_id"] == AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    assert summary["pdf_context_reconciliation_fix_type"] == (
        "reuse_existing_v3_1_6_safe_pdf_paragraph_window_expansion_sidecar"
    )
    assert summary["index_or_export_rebuild_required"] is False
    assert summary["index_or_export_rebuild_performed"] is False
    assert summary["artifact_policy"]["per_run_markdown_written"] is False
    assert queue["closed_query_ids"] == ["gq_auto_010"]
    assert queue["remaining_recommended_queue_query_ids"] == [
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0084",
    ]

    for suffix in ("summary.md", "queue.md", "audit.md"):
        assert not report_artifact_path(AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID, suffix).exists()

    for field in (
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "relevance_label_mutation",
        "answerability_label_mutation",
        "official_denominator_query_id_set_mutation",
        "renderer_mutation",
        "retrieval_mutation",
        "scorer_behavior_mutation",
        "index_or_export_rebuild_performed",
        "official_retrieval_metrics_computed",
        "lane_score_collapsed",
    ):
        assert summary[field] is False, field
    assert summary["behavior_change_made"] is True
    assert summary["implementation_change_made"] is True
    assert summary["prompt_context_behavior_change"] is True

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID
    )
    assert measurement["comparison_to_v3_2_2"]["unexpected_failure_category_change_count"] == 0
    assert measurement["pdf_context_reconciliation_fix_applied"] is True
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(queue)


def test_v3_2_5_gq_auto_010_reconciliation_changes_only_target_lane_bc() -> None:
    before_rows = read_jsonl(AGENTIC_V3_2_2_RESULTS)
    after_rows = read_jsonl(AGENTIC_V3_2_5_RESULTS)
    before_by_id = {row["query_id"]: row for row in before_rows}
    after_by_id = {row["query_id"]: row for row in after_rows}
    changes = []
    for query_id, after in after_by_id.items():
        before = before_by_id[query_id]
        for lane_name in ("v3_primary_replay", "live_llm_retrieval_topk", "live_llm_query_bound_oracle"):
            before_lane = before["lane_results"][lane_name]
            after_lane = after["lane_results"][lane_name]
            if before_lane["failure_category"] != after_lane["failure_category"]:
                changes.append((query_id, lane_name, before_lane["failure_category"], after_lane["failure_category"]))

    assert changes == [
        ("gq_auto_010", "live_llm_retrieval_topk", "LLM_EXPECTED_SPAN_MISMATCH", "PASS"),
        ("gq_auto_010", "live_llm_query_bound_oracle", "LLM_EXPECTED_SPAN_MISMATCH", "PASS"),
    ]
    target = after_by_id["gq_auto_010"]
    for lane_name in ("live_llm_retrieval_topk", "live_llm_query_bound_oracle"):
        lane = target["lane_results"][lane_name]
        assert lane["cited_search_unit_ids"] == ["pdfwin_b1c6527f848018640ad5ed231877c662"]
        assert lane["citation_support_score"] == 1.0
        assert lane["answer_score"] == 1.0
    non_target_context_expansions = [
        row["query_id"]
        for row in after_rows
        if row["query_id"] != "gq_auto_010" and row.get("context_expansion_diagnostics")
    ]
    assert non_target_context_expansions == []


def test_v3_2_5_pdf_context_reconciliation_overlay_is_target_scoped_and_locator_valid() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    units_by_query_id, preflight = runner.load_v3_2_5_gq_auto_010_pdf_context_expansion_sidecar()
    assert set(units_by_query_id) == {"gq_auto_010"}
    assert preflight["ok"] is True
    assert preflight["target_scoped"] is True
    unit = units_by_query_id["gq_auto_010"][0]
    assert unit["search_unit_id"] == "pdfwin_b1c6527f848018640ad5ed231877c662"
    assert unit["region_type"] == "paragraph_window"
    assert unit["document_version_id"] == "docv_fe2470815512a395"
    assert unit["page"] == 8
    assert unit["physical_page_index"] == 7
    assert "4.9%" in unit["normalized_excerpt"]
    assert "0.8%p" in unit["normalized_excerpt"]

    v3_rows = read_jsonl(AGENTIC_V3_RESULTS)
    target_row = next(row for row in v3_rows if row["query_id"] == "gq_auto_010")
    context = runner.build_v3_prompt_context_from_row(
        target_row,
        use_query_bound_only=True,
        mode="query-bound-only",
        context_expansion_units=units_by_query_id["gq_auto_010"],
    )
    expansion_citations = [item for item in context["citations"] if item.get("context_expansion")]
    assert len(expansion_citations) == 1
    assert expansion_citations[0]["search_unit_id"] == "pdfwin_b1c6527f848018640ad5ed231877c662"
    assert expansion_citations[0]["query_bound"] is True
    assert context["prompt_context_policy"]["diagnostic_context_expansion_count"] == 1
    assert context["prompt_context_policy"]["generation_used_expected_answer"] is False
    assert context["prompt_context_policy"]["generation_used_supporting_evidence"] is False
    assert context["prompt_context_policy"]["generation_used_gold_fields"] is False


def test_v3_2_6_text_prompt_span_rule_remeasurement_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_2_6_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_2_6_RESULTS)
    attribution = read_json(AGENTIC_V3_2_6_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_2_6_AUDIT_JSONL)
    diagnostics = read_jsonl(AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_DIAGNOSTICS_JSONL)
    queue = read_json(AGENTIC_V3_2_6_QUEUE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID
    assert summary["status"] == "TEXT_PROMPT_SPAN_RULE_REMEASUREMENT_V3_2_6_COMPLETED"
    assert summary["measurement_classification"] == "text_prompt_span_rule_remeasurement_v3_2_6"
    assert summary["run_class"] == "implementation_safe_text_prompt_span_rule_full_remeasurement"
    assert summary["target_query_ids"] == [
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0084",
    ]
    assert summary["text_prompt_span_rule_lanes_by_query_id"] == {
        "text_namu_v2_0014": ["live_llm_query_bound_oracle"],
        "text_namu_v2_0017": ["live_llm_retrieval_topk", "live_llm_query_bound_oracle"],
        "text_namu_v2_0084": ["live_llm_retrieval_topk", "live_llm_query_bound_oracle"],
    }
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert len(results) == 29
    assert len(audit_rows) == 29
    assert len(diagnostics) == 3
    assert attribution["run_id"] == AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID
    assert summary["denominator_policy"]["rows_by_source_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}

    comparison = summary["comparison_to_v3_2_5"]
    assert comparison["lane_pass_counts_before"] == {
        "live_llm_query_bound_oracle": 26,
        "live_llm_retrieval_topk": 27,
        "v3_primary_replay": 24,
    }
    assert comparison["lane_pass_counts_after"] == {
        "live_llm_query_bound_oracle": 27,
        "live_llm_retrieval_topk": 27,
        "v3_primary_replay": 24,
    }
    assert comparison["lane_pass_count_delta"] == {
        "live_llm_query_bound_oracle": 1,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 0,
    }
    assert comparison["expected_failure_category_change_count"] == 1
    assert comparison["unexpected_failure_category_change_count"] == 0
    assert comparison["citation_support_averages_all_one"] is True
    assert comparison["target_after_lane_failure_categories"]["text_namu_v2_0014"] == {
        "live_llm_query_bound_oracle": "PASS",
        "live_llm_retrieval_topk": "PASS",
        "v3_primary_replay": "LLM_TRUE_PARTIAL_SYNTHESIS",
    }
    assert comparison["target_after_lane_failure_categories"]["text_namu_v2_0017"] == {
        "live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH",
        "live_llm_retrieval_topk": "LLM_EXPECTED_SPAN_MISMATCH",
        "v3_primary_replay": "LLM_TRUE_PARTIAL_SYNTHESIS",
    }
    assert comparison["target_after_lane_failure_categories"]["text_namu_v2_0084"] == {
        "live_llm_query_bound_oracle": "LLM_EXPECTED_SPAN_MISMATCH",
        "live_llm_retrieval_topk": "LLM_EXPECTED_SPAN_MISMATCH",
        "v3_primary_replay": "LLM_TRUE_PARTIAL_SYNTHESIS",
    }
    assert summary["strict_json_parse_failure_count_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 0,
    }
    assert summary["llm_generated_locator_copy_failure_count_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 0,
    }
    assert summary["llm_generated_locator_missing_failure_count_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 0,
    }
    assert summary["llm_generated_locator_field_mismatch_failure_count_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 0,
    }
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0
    assert summary["context_expansion_applied_query_ids"] == ["gq_auto_010"]
    assert summary["pdf_context_reconciliation_carry_forward_applied"] is True
    assert summary["artifact_policy"]["per_run_markdown_written"] is False

    for suffix in ("summary.md", "queue.md", "audit.md"):
        assert not report_artifact_path(AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID, suffix).exists()

    for field in (
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "relevance_label_mutation",
        "answerability_label_mutation",
        "official_denominator_query_id_set_mutation",
        "renderer_mutation",
        "retrieval_mutation",
        "scorer_behavior_mutation",
        "index_or_export_rebuild_performed",
        "official_retrieval_metrics_computed",
        "lane_score_collapsed",
    ):
        assert summary[field] is False, field
    assert summary["behavior_change_made"] is True
    assert summary["implementation_change_made"] is True
    assert summary["prompt_context_behavior_change"] is True

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID
    )
    assert measurement["comparison_to_v3_2_5"]["unexpected_failure_category_change_count"] == 0
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(queue)


def test_v3_2_6_text_prompt_span_rule_changes_only_actionable_live_text_lanes() -> None:
    before_rows = read_jsonl(AGENTIC_V3_2_5_RESULTS)
    after_rows = read_jsonl(AGENTIC_V3_2_6_RESULTS)
    before_by_id = {row["query_id"]: row for row in before_rows}
    after_by_id = {row["query_id"]: row for row in after_rows}
    changes = []
    for query_id, after in after_by_id.items():
        before = before_by_id[query_id]
        for lane_name in ("v3_primary_replay", "live_llm_retrieval_topk", "live_llm_query_bound_oracle"):
            before_lane = before["lane_results"][lane_name]
            after_lane = after["lane_results"][lane_name]
            if before_lane["failure_category"] != after_lane["failure_category"]:
                changes.append((query_id, lane_name, before_lane["failure_category"], after_lane["failure_category"]))

    assert changes == [
        (
            "text_namu_v2_0014",
            "live_llm_query_bound_oracle",
            "LLM_EXPECTED_SPAN_MISMATCH",
            "PASS",
        ),
    ]
    target = after_by_id["text_namu_v2_0014"]
    assert target["text_prompt_span_rule_lanes"] == ["live_llm_query_bound_oracle"]
    assert target["lane_results"]["live_llm_retrieval_topk"]["text_prompt_span_rule_applied"] is False
    assert target["lane_results"]["live_llm_query_bound_oracle"]["text_prompt_span_rule_applied"] is True
    assert after_by_id["text_namu_v2_0012"]["text_prompt_span_rule_applied"] is False
    assert after_by_id["text_namu_v2_0077"]["text_prompt_span_rule_applied"] is False
    assert after_by_id["gq_auto_010"].get("pdf_context_reconciliation_carry_forward_applied") is True


def test_v3_2_6_queue_uses_v3_2_5_queue_as_source_of_truth() -> None:
    summary = read_json(AGENTIC_V3_2_6_SUMMARY_JSON)
    queue = read_json(AGENTIC_V3_2_6_QUEUE_JSON)

    assert summary["text_prompt_span_preflight"]["source_run_id"] == (
        AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID
    )
    assert summary["text_prompt_span_preflight"]["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
        "queue.json",
    )
    assert queue["source_run_id"] == AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID
    assert queue["closed_query_ids"] == ["text_namu_v2_0014"]
    assert queue["remaining_recommended_queue_query_ids"] == [
        "text_namu_v2_0017",
        "text_namu_v2_0084",
    ]
    assert queue["carried_non_actionable_lane_a_only_query_ids"] == [
        "text_namu_v2_0012",
        "text_namu_v2_0077",
    ]
    assert queue["v3_2_6_required"] is False
    assert queue["v3_2_7_required"] is True
    assert queue["unexpected_failure_category_change_count"] == 0
    assert queue["guardrails"]["retrieval_mutation"] is False
    assert queue["guardrails"]["scorer_behavior_mutation"] is False
    assert queue["guardrails"]["lane_score_collapsed"] is False


def test_v3_2_7_post_fix_closure_status_event_is_guarded_and_compact() -> None:
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "official_answer_citation_agentic_loop_v3_2_7_post_fix_closure"
        and item.get("run_id") == AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID
    )

    assert event["source_run_id"] == AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID
    assert event["baseline_run_id"] == AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID
    assert event["status"] == "POST_FIX_CLOSURE_AND_ROLLING_REPORT_CLEANUP_V3_2_7_COMPLETED"
    assert event["run_class"] == "status_ledger_only_closure_and_rolling_report_cleanup"
    assert event["current_lane_pass_counts"] == {
        "live_llm_query_bound_oracle": 27,
        "live_llm_retrieval_topk": 27,
        "v3_primary_replay": 24,
    }
    assert event["baseline_v3_2_2_lane_pass_counts"] == {
        "live_llm_query_bound_oracle": 25,
        "live_llm_retrieval_topk": 26,
        "v3_primary_replay": 24,
    }
    assert event["lane_pass_count_delta_from_v3_2_2"] == {
        "live_llm_query_bound_oracle": 2,
        "live_llm_retrieval_topk": 1,
        "v3_primary_replay": 0,
    }
    assert event["current_answer_quality_averages_by_lane"] == {
        "live_llm_query_bound_oracle": 0.931,
        "live_llm_retrieval_topk": 0.931,
        "v3_primary_replay": 0.8276,
    }
    assert event["current_citation_quality_averages_by_lane"] == {
        "live_llm_query_bound_oracle": 1.0,
        "live_llm_retrieval_topk": 1.0,
        "v3_primary_replay": 1.0,
    }
    assert event["denominator_policy"] == {
        "denominator_mutation": False,
        "query_id_set_mutation": False,
        "row_count": 29,
        "rows_by_source_family": {"PDF": 4, "TEXT": 6, "XLSX": 19},
    }
    assert event["unexpected_delta_count"] == 0
    assert event["unexpected_delta_sources"] == {
        "v3_2_5_vs_v3_2_2": 0,
        "v3_2_6_vs_v3_2_5": 0,
    }
    assert event["artifact_paths"] == {"status_jsonl": "ai/eval/reports/rag-ingestion/status.jsonl"}
    assert not report_artifact_path(AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID, "summary.md").exists()
    assert not report_artifact_path(AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID, "summary.json").exists()
    assert event["deferred_metrics"]["official_ndcg"]["computed"] is False
    assert event["deferred_metrics"]["official_mrr"]["computed"] is False
    assert event["deferred_metrics"]["official_hit_at_k"]["computed"] is False
    assert event["deferred_metrics"]["collapsed_lane_a_b_c_score"]["computed"] is False
    assert event["guardrails"]["official_retrieval_metrics_computed"] is False
    assert event["guardrails"]["lane_score_collapsed"] is False
    assert event["guardrails"]["gold_mutation"] is False
    assert event["guardrails"]["expected_answer_mutation"] is False
    assert event["guardrails"]["supporting_evidence_mutation"] is False
    assert event["guardrails"]["denominator_mutation"] is False
    assert event["guardrails"]["prompt_context_behavior_change"] is False
    assert_no_gold_generation_source_fields(event)


def test_v3_2_7_closure_uses_v3_2_6_queue_as_source_of_truth() -> None:
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "official_answer_citation_agentic_loop_v3_2_7_post_fix_closure"
        and item.get("run_id") == AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID
    )

    assert event["source_artifacts"]["v3_2_6_queue_json"] == report_artifact_repo_relative(
        AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID,
        "queue.json",
    )
    assert event["source_queue_assertions"]["v3_2_6_queue_v3_2_7_required"] is True
    assert event["v3_2_7_required"] is False
    assert event["v3_2_8_required"] is False
    assert event["next_implementation_phase"] == "none"
    assert event["active_implementation_query_ids"] == []
    assert event["active_implementation_queue_empty"] is True
    assert event["residual_queue_by_bucket"] == {
        "diagnostic_only": ["text_namu_v2_0017", "text_namu_v2_0084"],
        "frozen_lane_a_replay_residual": ["text_namu_v2_0012", "text_namu_v2_0077"],
        "live_bc_text_prompt_span_residual": ["text_namu_v2_0017", "text_namu_v2_0084"],
        "pdf_context_residual": [],
        "scorer_policy_closed": ["text_namu_v2_0077"],
    }
    assert event["closed_by_phase"] == {
        "v3_2_2_scorer_policy": ["text_namu_v2_0077 Lane B", "text_namu_v2_0077 Lane C"],
        "v3_2_5_pdf_context_reconciliation": ["gq_auto_010"],
        "v3_2_6_text_prompt_span_rule": ["text_namu_v2_0014"],
    }
    assert {item["category"] for item in event["artifact_retention_classification"]["v3_2_6"]} == {
        "machine_manifest",
        "canonical_result_payload",
        "forensic_debug_payload",
        "compact_diagnostic_payload",
        "queue_source_of_truth",
    }
    assert event["artifact_retention_classification"]["v3_2_7"][0]["category"] == "compact_status_ledger"
    assert "Future closure-only phases can remain status-ledger" in event[
        "future_artifact_emission_recommendation"
    ]


def test_v3_3_0_post_closure_source_of_truth_audit_is_status_only_and_guarded() -> None:
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "official_answer_citation_agentic_loop_v3_3_0_source_of_truth_audit"
        and item.get("run_id") == AGENTIC_V3_3_0_POST_CLOSURE_SOURCE_OF_TRUTH_AUDIT_RUN_ID
    )

    assert event["source_run_id"] == AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID
    assert event["baseline_run_id"] == AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID
    assert event["status"] == "POST_CLOSURE_HARDENING_SOURCE_OF_TRUTH_AUDIT_V3_3_0_COMPLETED"
    assert event["run_class"] == "status_ledger_only_source_of_truth_audit"
    assert event["diagnostic_only"] is True
    assert event["promotion_evidence"] is False
    assert event["current_lane_pass_counts"] == {
        "live_llm_query_bound_oracle": 27,
        "live_llm_retrieval_topk": 27,
        "v3_primary_replay": 24,
    }
    assert event["active_implementation_queue_empty"] is True
    assert event["next_implementation_phase"] == "none"
    assert event["rolling_docs_status_agreement"]["status"] == "PASS"
    assert event["source_of_truth_audit_result"]["status"] == "PASS"
    assert event["source_of_truth_relationships"]["v3_2_3"]["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_2_2_POST_FIX_REMEASUREMENT_RUN_ID,
        "queue.json",
    )
    assert event["source_of_truth_relationships"]["v3_2_4"]["source_run_id"] == (
        AGENTIC_V3_2_3_QUEUE_LANE_ACTIONABILITY_RUN_ID
    )
    assert event["source_of_truth_relationships"]["v3_2_5"]["overlay_source_run_id"] == (
        AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    )
    assert event["source_of_truth_relationships"]["v3_2_6"]["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_2_5_GQ_AUTO_010_PDF_CONTEXT_RECONCILIATION_RUN_ID,
        "queue.json",
    )
    assert event["source_of_truth_relationships"]["v3_2_7"]["source_artifact"] == (
        "ai/eval/reports/rag-ingestion/status.jsonl"
    )
    assert event["residual_queue_by_bucket"] == {
        "diagnostic_only": ["text_namu_v2_0017", "text_namu_v2_0084"],
        "frozen_lane_a_replay_residual": ["text_namu_v2_0012", "text_namu_v2_0077"],
        "live_bc_text_prompt_span_residual": ["text_namu_v2_0017", "text_namu_v2_0084"],
        "pdf_context_residual": [],
        "scorer_policy_closed": ["text_namu_v2_0077"],
    }
    assert event["flag_semantics"]["behavior_change_made"]["v3_2_7"] is False
    assert event["flag_semantics"]["implementation_change_made"]["v3_2_7"] is False
    assert event["flag_semantics"]["scorer_behavior_mutation"]["v3_2_3_through_v3_2_7"] is False
    assert event["deferred_metrics"]["official_ndcg"]["computed"] is False
    assert event["deferred_metrics"]["official_mrr"]["computed"] is False
    assert event["deferred_metrics"]["official_hit_at_k"]["computed"] is False
    assert event["deferred_metrics"]["collapsed_lane_a_b_c_score"]["computed"] is False
    assert event["guardrails"]["behavior_change_made_in_v3_3_0"] is False
    assert event["guardrails"]["implementation_change_made_in_v3_3_0"] is False
    assert event["guardrails"]["diagnostic_only"] is True
    assert event["guardrails"]["promotion_evidence"] is False
    assert event["guardrails"]["scorer_behavior_mutation"] is False
    assert not report_artifact_path(AGENTIC_V3_3_0_POST_CLOSURE_SOURCE_OF_TRUTH_AUDIT_RUN_ID, "summary.json").exists()
    assert not report_artifact_path(AGENTIC_V3_3_0_POST_CLOSURE_SOURCE_OF_TRUTH_AUDIT_RUN_ID, "summary.md").exists()
    assert_no_gold_generation_source_fields(event)


def test_v3_3_2_retrieval_label_design_packet_blocks_metrics_until_user_decisions() -> None:
    run_id = "official_answer_citation_agentic_loop_run_v3_3_2_retrieval_relevance_answerability_label_design_packet"
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "official_retrieval_label_design_packet_v3_3_2"
        and item.get("run_id") == run_id
    )

    assert event["status"] == "NEEDS_USER_DECISION_FOR_OFFICIAL_RETRIEVAL_QRELS"
    assert event["run_class"] == "human_decision_packet_only"
    assert event["diagnostic_only"] is True
    assert event["promotion_evidence"] is False
    assert event["source_run_id"] == AGENTIC_V3_2_6_TEXT_PROMPT_SPAN_RULE_RUN_ID
    assert event["source_status_run_id"] == AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID
    assert event["denominator_snapshot"] == {
        "row_count": 29,
        "rows_by_source_family": {"PDF": 4, "TEXT": 6, "XLSX": 19},
        "current_contract": "answer_citation_denominator_not_retrieval_qrels",
        "denominator_mutation": False,
    }
    assert event["current_lane_pass_counts"] == {
        "live_llm_query_bound_oracle": 27,
        "live_llm_retrieval_topk": 27,
        "v3_primary_replay": 24,
    }
    assert event["lane_definitions"]["v3_primary_replay"]["structured_adapter_retained_for"] == ["PDF", "XLSX"]
    assert event["lane_definitions"]["live_llm_retrieval_topk"]["context_policy"] == (
        "source_bound_retrieved_topk"
    )
    assert event["lane_definitions"]["live_llm_query_bound_oracle"]["context_policy"] == (
        "query_bound_searchunit_only"
    )

    assert event["source_bound_search_unit_snapshot"] == {
        "manifest_rows": 29,
        "source_bound_official_denominator_true_count": 29,
        "source_text_available_count": 29,
        "promotion_evidence_true_count": 0,
        "candidate_artifact_generation_source_true_count": 0,
    }
    assert set(event["source_artifacts"]) >= {
        "ai/eval/eval_queries/official_denominator_registry.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_results.jsonl",
    }

    schema = event["proposed_label_schema_options"]
    assert schema["relevance"]["binary"] == ["RELEVANT", "IRRELEVANT"]
    assert schema["relevance"]["graded"] == [
        "EXACT_ANSWER_EVIDENCE",
        "SUPPORTING_CONTEXT",
        "TOPIC_RELATED",
        "NOT_RELEVANT",
    ]
    assert schema["answerability"]["ordinal_0_3"] == [
        "NOT_RELEVANT",
        "RELATED_BUT_NOT_ANSWERABLE",
        "PARTIALLY_ANSWERABLE",
        "FULLY_ANSWERABLE",
    ]
    assert schema["human_review_record_fields"]["label_status"] == "pending"
    assert schema["human_review_record_fields"]["decision_fields_blank"] is True
    assert schema["structured_adapter_policy"]["adapter_pass_is_qrel"] is False

    assert event["required_user_decisions"] == [
        "relevance",
        "answerability",
        "gold_policy",
        "expected_answer_evidence_policy",
        "denominator_inclusion_exclusion_policy",
        "structured_xlsx_pdf_deterministic_adapter_policy",
    ]
    assert event["blocked_metrics"] == {
        "official_ndcg": "blocked_until_human_relevance_and_answerability_qrels_exist",
        "official_mrr": "blocked_until_human_relevance_and_answerability_qrels_exist",
        "official_hit_at_k": "blocked_until_human_relevance_and_answerability_qrels_exist",
        "collapsed_lane_a_b_c_score": "blocked_by_lane_separation_policy",
    }

    guardrails = event["guardrails"]
    for key in (
        "relevance_label_mutation",
        "answerability_label_mutation",
        "denominator_mutation",
        "official_denominator_query_id_set_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "gold_mutation",
        "prompt_context_behavior_change",
        "retrieval_mutation",
        "renderer_mutation",
        "scorer_behavior_mutation",
        "index_or_export_rebuild_performed",
        "silver_mutation",
        "production_mutation",
        "promotion_evidence",
        "official_retrieval_metrics_computed",
        "official_ndcg_computed",
        "official_mrr_computed",
        "official_hit_at_k_computed",
        "lane_score_collapsed",
        "implementation_change_made_in_v3_3_2",
        "behavior_change_made_in_v3_3_2",
    ):
        assert guardrails[key] is False, key
    assert event["active_implementation_queue_empty"] is True
    assert event["next_implementation_phase"] == "none"


def test_v3_4_0_official_retrieval_metric_contract_blocks_metrics_until_qrels_are_approved() -> None:
    run_id = AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "official_retrieval_metric_contract_v3_4_0"
        and item.get("run_id") == run_id
    )
    contract = read_json(report_artifact_path(run_id, "contract.json"))
    qrels_schema = read_json(report_artifact_path(run_id, "qrels_schema.json"))

    assert event["status"] == "OFFICIAL_RETRIEVAL_METRIC_CONTRACT_READY_QRELS_REQUIRED"
    assert event["run_class"] == "contract_json_plus_qrels_schema_no_metric_execution"
    assert event["diagnostic_only"] is True
    assert event["promotion_evidence"] is False
    assert event["source_run_id"] == AGENTIC_V3_3_2_RETRIEVAL_LABEL_DESIGN_PACKET_RUN_ID
    assert event["source_status_run_id"] == AGENTIC_V3_2_7_POST_FIX_CLOSURE_RUN_ID
    assert event["denominator_snapshot"] == {
        "row_count": 29,
        "rows_by_source_family": {"PDF": 4, "TEXT": 6, "XLSX": 19},
        "current_contract": "answer_citation_denominator_not_retrieval_qrels",
        "denominator_mutation": False,
        "official_retrieval_qrels_denominator_selected": False,
        "query_id_set_mutation": False,
    }
    assert event["current_lane_pass_counts"] == {
        "live_llm_query_bound_oracle": 27,
        "live_llm_retrieval_topk": 27,
        "v3_primary_replay": 24,
    }
    assert event["current_citation_quality_averages_by_lane"] == {
        "live_llm_query_bound_oracle": 1.0,
        "live_llm_retrieval_topk": 1.0,
        "v3_primary_replay": 1.0,
    }
    assert event["qrels_denominator_policy_options"] == [
        "option_a_all_29_rows",
        "option_b_track_by_track_opening",
        "option_c_only_rows_with_settled_retrieval_labels",
    ]
    assert event["selected_qrels_denominator_policy"] is None
    assert event["official_retrieval_metric_execution_allowed"] is False
    assert event["blocked_metrics"] == {
        "collapsed_lane_a_b_c_score": "blocked_by_lane_separation_policy",
        "macro_by_source_family": "blocked_until_track_qrels_are_approved",
        "micro_overall": "blocked_until_official_qrels_denominator_policy_is_selected_and_labeled",
        "official_hit_at_1": "blocked_until_approved_retrieval_qrels_exist",
        "official_hit_at_3": "blocked_until_approved_retrieval_qrels_exist",
        "official_hit_at_5": "blocked_until_approved_retrieval_qrels_exist",
        "official_mrr_at_5": "blocked_until_approved_retrieval_qrels_exist",
        "official_ndcg_at_5": "blocked_until_approved_retrieval_qrels_exist",
    }

    assert contract["schema_version"] == "official_retrieval_metric_contract_v3_4_0"
    assert contract["official_metric"] is False
    assert contract["official_retrieval_metric_execution_allowed"] is False
    assert contract["official_retrieval_metrics_computed"] is False
    assert contract["qrels_created"] is False
    assert contract["qrels_source"] is None
    assert contract["selected_qrels_denominator_policy"] is None
    assert contract["selected_qrels_denominator_policy_status"] == "USER_DECISION_REQUIRED"
    assert set(contract["qrels_denominator_policy_options"]) == {
        "option_a_all_29_rows",
        "option_b_track_by_track_opening",
        "option_c_only_rows_with_settled_retrieval_labels",
    }
    assert contract["relevance_label_schema"] == [
        {"grade": 0, "label": "NOT_RELEVANT", "official_positive_for_hit_mrr": False},
        {"grade": 1, "label": "TOPIC_RELATED", "official_positive_for_hit_mrr": False},
        {"grade": 2, "label": "SUPPORTING_CONTEXT", "official_positive_for_hit_mrr": False},
        {"grade": 3, "label": "EXACT_ANSWER_EVIDENCE", "official_positive_for_hit_mrr": True},
    ]
    assert contract["answerability_label_schema"] == [
        {"grade": 0, "label": "NOT_ANSWERABLE", "official_positive_for_hit_mrr": False},
        {"grade": 1, "label": "RELATED_BUT_NOT_ANSWERABLE", "official_positive_for_hit_mrr": False},
        {"grade": 2, "label": "PARTIALLY_ANSWERABLE", "official_positive_for_hit_mrr": False},
        {"grade": 3, "label": "FULLY_ANSWERABLE", "official_positive_for_hit_mrr": True},
    ]
    assert contract["positive_rule_for_hit_and_mrr"] == {
        "default_proposal": "relevance_grade >= 3 and answerability_grade >= 3",
        "relevance_min": 3,
        "answerability_min": 3,
    }
    assert contract["ndcg_gain_rules"]["default_proposal"] == {
        "gain": "relevance_grade",
        "allowed_grades": [0, 1, 2, 3],
    }
    assert contract["ndcg_gain_rules"]["answerability_gated_variant"] == {
        "gain": "0 if answerability_grade < 2 else relevance_grade",
        "answerability_min_for_nonzero_gain": 2,
    }
    assert contract["metric_list"] == {
        "ranking_metrics": ["Hit@1", "Hit@3", "Hit@5", "MRR@5", "nDCG@5"],
        "aggregation": {
            "micro_overall": "mean over eligible labeled query rows",
            "macro_by_source_family": ["TEXT", "PDF", "XLSX"],
        },
    }
    assert contract["prohibited_claims"] == {
        "promotion_evidence": False,
        "collapsed_lane_a_b_c_score": False,
        "official_retrieval_metric_until_labels_applied": False,
        "official_ndcg_mrr_hit_at_k_until_qrels_approved": False,
        "readme_metric_claim": False,
    }
    assert contract["readme_wording_boundary"]["official_answer_citation_result_section"] == (
        "separate_from_official_retrieval_metric_section"
    )
    assert contract["readme_wording_boundary"]["readme_mutation_in_v3_4_0"] is False
    assert qrels_schema["schema_role"] == "schema_only_no_qrels_created"
    assert qrels_schema["record_count"] == 0
    assert qrels_schema["official_metric_label_status_required"] == "APPROVED"
    assert qrels_schema["required_boolean_values"] == {
        "generation_source": False,
        "gold": False,
        "promotion_evidence": False,
    }
    assert qrels_schema["source_family_allowed_values"] == ["TEXT", "PDF", "XLSX"]
    assert "expected_answer" in qrels_schema["forbidden_record_fields"]
    assert "supporting_evidence" in qrels_schema["forbidden_record_fields"]
    assert "official_metric_value" in qrels_schema["forbidden_record_fields"]

    prohibited_qrels = set(event["legacy_or_silver_sources_prohibited_as_current_official_qrels"])
    assert "ai/eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv" in prohibited_qrels
    assert "ai/eval/eval_queries/xlsx_silver_retrieval_evidence_candidates_v0.jsonl" in prohibited_qrels
    assert contract["legacy_or_silver_sources_prohibited_as_current_official_qrels"] == (
        qrels_schema["legacy_or_silver_sources_prohibited_as_current_official_qrels"]
    )

    guardrails = event["guardrails"]
    for key in (
        "official_retrieval_metrics_computed",
        "official_ndcg_computed",
        "official_mrr_computed",
        "official_hit_at_k_computed",
        "lane_score_collapsed",
        "relevance_label_created",
        "answerability_label_created",
        "relevance_label_mutation",
        "answerability_label_mutation",
        "qrels_created",
        "qrels_denominator_mutation",
        "denominator_mutation",
        "official_denominator_query_id_set_mutation",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "prompt_context_behavior_change",
        "retrieval_mutation",
        "renderer_mutation",
        "scorer_behavior_mutation",
        "index_or_export_rebuild_performed",
        "silver_mutation",
        "production_mutation",
        "promotion_evidence",
        "threshold_tuning",
        "winner_selection",
        "readme_metric_claim_added",
    ):
        assert guardrails[key] is False, key
    assert guardrails["contract_only"] is True
    assert guardrails["diagnostic_only"] is True
    assert event["active_implementation_queue_empty"] is True
    assert event["next_implementation_phase"] == "none"
    assert not report_artifact_path(run_id, "results.jsonl").exists()
    assert not report_artifact_path(run_id, "summary.json").exists()
    assert not report_artifact_path(run_id, "summary.md").exists()
    assert_no_gold_generation_source_fields(event)
    assert_no_gold_generation_source_fields(contract)
    assert_no_gold_generation_source_fields(qrels_schema)


def test_v3_4_1_official_retrieval_qrels_candidate_packet_is_pending_human_review_only() -> None:
    run_id = AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_RUN_ID
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "official_retrieval_qrels_candidate_packet_v3_4_1"
        and item.get("run_id") == run_id
    )
    summary = read_json(AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_SUMMARY_JSON)
    rows = read_jsonl(AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_JSONL)
    csv_rows = read_csv(AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_CSV)
    csv_fieldnames = list(csv_rows[0]) if csv_rows else []

    assert event["status"] == "OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_READY_FOR_HUMAN_REVIEW"
    assert event["run_class"] == "human_labelable_qrels_candidate_packet_no_metric_execution"
    assert event["diagnostic_only"] is True
    assert event["promotion_evidence"] is False
    assert event["contract_prerequisite"] == {
        "run_id": AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID,
        "status_event_found": True,
        "status": "OFFICIAL_RETRIEVAL_METRIC_CONTRACT_READY_QRELS_REQUIRED",
    }
    assert event["label_design_packet_prerequisite"] == {
        "run_id": AGENTIC_V3_3_2_RETRIEVAL_LABEL_DESIGN_PACKET_RUN_ID,
        "status_event_found": True,
        "status": "NEEDS_USER_DECISION_FOR_OFFICIAL_RETRIEVAL_QRELS",
    }
    assert event["query_count"] == 29
    assert event["qrels_candidate_row_count"] == 219
    assert event["candidates_by_source_family"] == {"PDF": 22, "TEXT": 24, "XLSX": 173}
    assert event["candidates_by_lane_source"] == {"query_bound_oracle": 51, "retrieved_topk": 168}
    assert event["candidates_by_candidate_role"] == {
        "query_bound_oracle_candidate": 29,
        "retrieved_topk_candidate": 145,
        "structured_adapter_candidate": 45,
    }
    assert event["relevance_label_values"] == ["pending"]
    assert event["answerability_label_values"] == ["pending"]
    assert event["label_status"] == "pending_user_review"
    assert event["blocked_metrics"] == {
        "collapsed_lane_a_b_c_score": "blocked_by_lane_separation_policy",
        "official_hit_at_1": "blocked_until_pending_user_review_labels_are_approved",
        "official_hit_at_3": "blocked_until_pending_user_review_labels_are_approved",
        "official_hit_at_5": "blocked_until_pending_user_review_labels_are_approved",
        "official_mrr_at_5": "blocked_until_pending_user_review_labels_are_approved",
        "official_ndcg_at_5": "blocked_until_pending_user_review_labels_are_approved",
    }
    assert event["artifact_paths"]["qrels_candidate_jsonl"] == (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_"
        "qrels_candidates.jsonl"
    )
    assert event["artifact_paths"]["qrels_candidate_csv"] == (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_"
        "qrels_candidates.csv"
    )
    assert event["artifact_paths"]["summary_json"] == (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_4_1_official_retrieval_qrels_candidate_packet_"
        "summary.json"
    )

    assert summary["query_count"] == 29
    assert summary["qrels_candidate_row_count"] == 219
    assert summary["candidates_by_source_family"] == {"PDF": 22, "TEXT": 24, "XLSX": 173}
    assert summary["skipped_candidate_count"] == 0
    assert summary["label_status"] == "pending_user_review"
    assert len(rows) == 219
    assert len(csv_rows) == 219
    assert set(csv_fieldnames) >= {
        "qrels_candidate_id",
        "query_id",
        "source_family",
        "rank",
        "lane_source",
        "candidate_role",
        "document_version_id",
        "search_unit_id",
        "source_locator_json",
        "source_excerpt_sha256",
        "relevance_label",
        "answerability_label",
        "label_status",
    }
    assert len({row["qrels_candidate_id"] for row in rows}) == 219
    assert {row["query_id"] for row in rows} == set(summary["candidate_rows_by_query_id"])
    assert {row["source_family"] for row in rows} == {"PDF", "TEXT", "XLSX"}
    assert {row["lane_source"] for row in rows} == {"query_bound_oracle", "retrieved_topk"}
    assert {row["candidate_role"] for row in rows} == {
        "query_bound_oracle_candidate",
        "retrieved_topk_candidate",
        "structured_adapter_candidate",
    }
    for row in rows:
        assert row["relevance_label"] == "pending"
        assert row["answerability_label"] == "pending"
        assert row["relevance_grade"] is None
        assert row["answerability_grade"] is None
        assert row["label_status"] == "pending_user_review"
        assert row["official_denominator_overlap"] is True
        assert row["qrels_candidate"] is True
        assert row["generation_source"] is False
        assert row["promotion_evidence"] is False
        assert row["final_label_inferred"] is False
        assert row["metric_computation_allowed"] is False
        assert row["document_version_id"]
        assert row["search_unit_id"]
        assert row["source_bound_locator"]
        assert row["source_text_or_value_available"] is True
        assert row["source_excerpt_sha256"]
        assert "no final label inferred" in row["suggested_label_reason"]
    for csv_row in csv_rows:
        assert csv_row["relevance_label"] == "pending"
        assert csv_row["answerability_label"] == "pending"
        assert csv_row["label_status"] == "pending_user_review"
        assert csv_row["generation_source"] == "false"
        assert csv_row["promotion_evidence"] == "false"

    guardrails = event["guardrails"]
    for key in (
        "official_retrieval_metrics_computed",
        "official_ndcg_computed",
        "official_mrr_computed",
        "official_hit_at_k_computed",
        "lane_score_collapsed",
        "relevance_label_mutation",
        "answerability_label_mutation",
        "final_label_created",
        "denominator_mutation",
        "official_denominator_query_id_set_mutation",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "candidate_artifacts_as_generation_source",
        "generation_used_expected_answer",
        "generation_used_supporting_evidence",
        "generation_used_gold_fields",
        "prompt_context_behavior_change",
        "retrieval_mutation",
        "renderer_mutation",
        "scorer_behavior_mutation",
        "index_or_export_rebuild_performed",
        "export_mutation",
        "silver_mutation",
        "production_mutation",
        "promotion_evidence",
        "threshold_tuning",
        "winner_selection",
        "readme_metric_claim_added",
    ):
        assert guardrails[key] is False, key
    assert guardrails["qrels_candidate_packet_created"] is True
    assert guardrails["qrels_candidate_rows_created"] is True
    assert guardrails["label_status_all_pending_user_review"] is True
    assert event["active_implementation_queue_empty"] is True
    assert event["next_implementation_phase"] == "none"
    assert not report_artifact_path(run_id, "results.jsonl").exists()
    assert not report_artifact_path(run_id, "summary.md").exists()
    assert_no_gold_generation_source_fields(event)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(rows)


def test_v3_4_1a_official_retrieval_qrels_human_minimal_review_packet_is_policy_only() -> None:
    run_id = AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "official_retrieval_qrels_human_minimal_review_packet_v3_4_1a"
        and item.get("run_id") == run_id
    )
    policy = read_json(AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_POLICY_APPROVAL_JSON)
    query_rows = read_csv(AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_QUERY_GROUP_REVIEW_CSV)
    ambiguous_rows = read_csv(AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_AMBIGUOUS_CANDIDATE_REVIEW_CSV)
    auto_label_plan = read_json(AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_AUTO_LABEL_PLAN_JSON)
    summary = read_json(AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_MINIMAL_REVIEW_SUMMARY_JSON)

    assert event["status"] == "OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_READY"
    assert event["run_class"] == "human_minimal_review_packet_no_label_application_no_metric_execution"
    assert event["candidate_packet_prerequisite"] == {
        "run_id": AGENTIC_V3_4_1_OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_RUN_ID,
        "status_event_found": True,
        "status": "OFFICIAL_RETRIEVAL_QRELS_CANDIDATE_PACKET_READY_FOR_HUMAN_REVIEW",
    }
    assert event["contract_prerequisite"] == {
        "run_id": AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID,
        "status_event_found": True,
        "status": "OFFICIAL_RETRIEVAL_METRIC_CONTRACT_READY_QRELS_REQUIRED",
    }
    assert event["raw_candidate_row_count"] == 219
    assert event["query_group_count"] == 29
    assert event["ambiguous_candidate_count"] == 30
    assert event["estimated_user_review_rows"] == 59
    assert event["raw_219_row_csv_direct_human_review_required"] is False
    assert event["candidates_by_source_family"] == {"PDF": 22, "TEXT": 24, "XLSX": 173}
    assert event["relevance_label_values"] == ["pending"]
    assert event["answerability_label_values"] == ["pending"]
    assert len(query_rows) == 29
    assert len(ambiguous_rows) == 30
    assert summary["raw_candidate_row_count"] == 219
    assert summary["query_group_count"] == 29
    assert summary["ambiguous_candidate_count"] == 30
    assert summary["estimated_user_review_rows"] == 59
    assert summary["raw_219_row_csv_direct_human_review_required"] is False
    assert summary["query_groups_by_source_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}
    assert summary["ambiguous_candidates_by_source_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 20}

    assert policy["approval_status"] == "pending_user_review"
    assert policy["official_metric_execution_allowed"] is False
    assert policy["qrels_labels_finalized"] is False
    assert policy["hit_mrr_positive_rule"]["rule"] == "relevance_grade >= 3 and answerability_grade >= 3"
    assert policy["ndcg_gain"]["answerability_gated"] is True
    assert policy["expected_answer_supporting_evidence_labeler_context_policy"]["included_in_v3_4_1a"] is False
    assert "Do not silently treat unreviewed candidates" in policy["unjudged_policy"]["default"]

    expected_query_fields = {
        "query_id",
        "source_family",
        "question",
        "expected_answer_labeler_context",
        "supporting_evidence_labeler_context",
        "retrieved_topk_candidate_ids",
        "query_bound_oracle_candidate_ids",
        "structured_adapter_candidate_ids",
        "codex_recommended_positive_candidate_ids",
        "codex_recommended_relevance_label",
        "codex_recommended_answerability_label",
        "user_decision",
        "user_override_positive_candidate_ids",
        "user_note",
    }
    assert set(query_rows[0]) >= expected_query_fields
    for row in query_rows:
        assert row["expected_answer_labeler_context"] == ""
        assert row["supporting_evidence_labeler_context"] == ""
        assert row["labeler_context_policy"] == (
            "omitted_pending_user_policy_expected_answer_supporting_evidence_not_used"
        )
        assert row["codex_recommended_positive_candidate_ids"]
        assert row["codex_recommended_relevance_label"].endswith("pending_user_approval")
        assert row["codex_recommended_answerability_label"].endswith("pending_user_approval")
        assert row["user_decision"] == "pending"

    assert set(ambiguous_rows[0]) >= {
        "review_candidate_unit_id",
        "query_id",
        "source_family",
        "qrels_candidate_ids",
        "document_version_id",
        "search_unit_id",
        "source_locator_json",
        "source_excerpt_sha256",
        "ambiguity_reasons",
        "relevance_label",
        "answerability_label",
        "label_status",
        "generation_source",
        "promotion_evidence",
    }
    for row in ambiguous_rows:
        assert row["relevance_label"] == "pending"
        assert row["answerability_label"] == "pending"
        assert row["label_status"] == "pending_user_review"
        assert row["user_decision"] == "pending"
        assert row["generation_source"] == "false"
        assert row["promotion_evidence"] == "false"
        assert row["source_locator_json"]
        assert row["source_excerpt_sha256"]
        assert row["ambiguity_reasons"]

    assert auto_label_plan["auto_labels_applied"] is False
    assert auto_label_plan["final_labels_created"] is False
    assert auto_label_plan["official_metrics_computed"] is False
    assert auto_label_plan["deterministic_rules"][0]["covered_row_count"] == 102
    assert auto_label_plan["deterministic_rules"][0]["applied_in_v3_4_1a"] is False
    assert auto_label_plan["rows_excluded_from_auto_labeling"]["count"] == 117
    assert auto_label_plan["rows_requiring_user_review"]["query_group_review_row_count"] == 29
    assert auto_label_plan["rows_requiring_user_review"]["ambiguous_candidate_review_row_count"] == 30

    guardrails = event["guardrails"]
    assert guardrails["human_minimal_review_packet_created"] is True
    assert guardrails["qrels_policy_approval_packet_created"] is True
    assert guardrails["query_group_review_created"] is True
    assert guardrails["ambiguous_candidate_review_created"] is True
    assert guardrails["auto_label_plan_created"] is True
    assert guardrails["all_final_labels_remain_pending"] is True
    assert guardrails["expected_answer_labeler_context_included"] is False
    assert guardrails["supporting_evidence_labeler_context_included"] is False
    assert guardrails["per_run_markdown_created"] is False
    for key in (
        "auto_label_plan_applied",
        "official_retrieval_metrics_computed",
        "official_ndcg_computed",
        "official_mrr_computed",
        "official_hit_at_k_computed",
        "lane_score_collapsed",
        "relevance_label_mutation",
        "answerability_label_mutation",
        "final_label_created",
        "denominator_mutation",
        "official_denominator_query_id_set_mutation",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "candidate_artifacts_as_generation_source",
        "generation_used_expected_answer",
        "generation_used_supporting_evidence",
        "generation_used_gold_fields",
        "prompt_context_behavior_change",
        "retrieval_mutation",
        "renderer_mutation",
        "scorer_behavior_mutation",
        "index_or_export_rebuild_performed",
        "export_mutation",
        "silver_mutation",
        "production_mutation",
        "promotion_evidence",
        "threshold_tuning",
        "winner_selection",
        "readme_metric_claim_added",
    ):
        assert guardrails[key] is False, key
    assert not report_artifact_path(run_id, "results.jsonl").exists()
    assert not report_artifact_path(run_id, "summary.md").exists()
    assert_no_gold_generation_source_fields(event)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(policy)
    assert_no_gold_generation_source_fields(auto_label_plan)
    assert_no_gold_generation_source_fields(query_rows)
    assert_no_gold_generation_source_fields(ambiguous_rows)


def test_v3_4_2_applies_user_exact_evidence_qrels_and_excludes_ambiguous_query() -> None:
    run_id = AGENTIC_V3_4_2_APPLY_USER_OFFICIAL_RETRIEVAL_QRELS_LABELS_RUN_ID
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "official_exact_evidence_retrieval_qrels_labels_applied_v3_4_2"
        and item.get("run_id") == run_id
    )
    qrels_rows = read_jsonl(AGENTIC_V3_4_2_OFFICIAL_RETRIEVAL_QRELS_JSONL)
    coverage = read_json(AGENTIC_V3_4_2_QRELS_COVERAGE_SUMMARY_JSON)
    exclusions = read_jsonl(AGENTIC_V3_4_2_QRELS_EXCLUSION_LEDGER_JSONL)
    readme = README.read_text(encoding="utf-8")

    assert event["status"] == "OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_QRELS_READY_METRICS_DEFERRED"
    assert event["run_class"] == "official_exact_evidence_qrels_application_no_metric_execution"
    assert event["metric_family"] == "official exact-evidence retrieval metrics"
    assert event["metric_scope"] == "source_bound_search_unit_exact_answer_evidence_smoke"
    assert event["benchmark_scope"] == "small official exact-evidence retrieval smoke benchmark"
    assert "not statistically representative product performance" in event["small_sample_caveat"]
    assert event["valid_for"] == ["metric_pipeline_validation", "regression_guarding"]
    assert event["not_valid_for"] == [
        "statistically_representative_product_performance",
        "readme_headline_performance_claim",
    ]
    assert event["readme_headline_performance_claim_blocked"] is True
    assert event["statistically_representative_product_performance"] is False
    assert event["minimal_review_prerequisite"] == {
        "run_id": AGENTIC_V3_4_1A_OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_RUN_ID,
        "status_event_found": True,
        "status": "OFFICIAL_RETRIEVAL_QRELS_HUMAN_MINIMAL_REVIEW_PACKET_READY",
    }
    assert event["contract_prerequisite"] == {
        "run_id": AGENTIC_V3_4_0_OFFICIAL_RETRIEVAL_METRIC_CONTRACT_RUN_ID,
        "status_event_found": True,
        "status": "OFFICIAL_RETRIEVAL_METRIC_CONTRACT_READY_QRELS_REQUIRED",
    }
    assert event["included_query_count"] == 28
    assert event["excluded_query_count"] == 1
    assert event["excluded_query_ids"] == ["gq_auto_010"]
    assert event["qrels_unit_row_count"] == 140
    assert event["qrels_positive_count"] == 28
    assert event["qrels_positive_by_source_family"] == {"PDF": 3, "TEXT": 6, "XLSX": 19}
    assert event["qrels_non_positive_exact_evidence_candidate_count"] == 112
    assert event["official_metrics_computed_in_v3_4_2"] is False
    assert event["v3_4_3_ready"] is True
    assert event["future_metric_names"] == {
        "hit_at_k": "official exact-evidence Hit@K",
        "mrr_at_k": "official exact-evidence MRR@K",
        "ndcg_at_k": "binary exact-evidence nDCG@K",
    }

    assert coverage["included_query_count"] == 28
    assert coverage["excluded_query_count"] == 1
    assert coverage["excluded_query_ids"] == ["gq_auto_010"]
    assert coverage["included_query_counts_by_source_family"] == {"PDF": 3, "TEXT": 6, "XLSX": 19}
    assert coverage["excluded_query_counts_by_source_family"] == {"PDF": 1}
    assert coverage["qrels_unit_row_count"] == 140
    assert coverage["qrels_unit_rows_by_source_family"] == {"PDF": 8, "TEXT": 18, "XLSX": 114}
    assert coverage["qrels_positive_count"] == 28
    assert coverage["qrels_non_positive_exact_evidence_candidate_count"] == 112
    assert coverage["same_phase_metric_allowed_by_contract"] is False
    assert coverage["official_metrics_computed_in_v3_4_2"] is False
    assert coverage["v3_4_3_ready"] is True
    assert coverage["metric_family"] == "official exact-evidence retrieval metrics"
    assert coverage["metric_scope"] == "source_bound_search_unit_exact_answer_evidence_smoke"
    assert coverage["benchmark_scope"] == "small official exact-evidence retrieval smoke benchmark"
    assert "metric-pipeline validation" in coverage["small_sample_caveat"]
    assert "regression guarding" in coverage["small_sample_caveat"]
    assert "not statistically representative product performance" in coverage["small_sample_caveat"]
    assert coverage["valid_for"] == ["metric_pipeline_validation", "regression_guarding"]
    assert coverage["not_valid_for"] == [
        "statistically_representative_product_performance",
        "readme_headline_performance_claim",
    ]
    assert coverage["readme_headline_performance_claim_blocked"] is True
    assert coverage["statistically_representative_product_performance"] is False
    assert coverage["future_metric_names"]["ndcg_at_k"] == "binary exact-evidence nDCG@K"
    assert coverage["full_graded_ndcg_allowed"] is False
    assert coverage["label_application_policy"] == {
        "accepted_query_user_decision": "accept_recommendation",
        "human_judged_topical_negatives_created": False,
        "non_positive_label_provenance": "derived_from_user_exact_evidence_policy",
        "non_positive_scope": "not_official_positive_for_exact_evidence_metric",
        "positive_label_provenance": "user_bulk_accept_recommendation",
    }
    assert run_id not in readme
    assert "official exact-evidence Hit@K" not in readme
    assert "official exact-evidence MRR@K" not in readme
    assert "binary exact-evidence nDCG@K" not in readme

    assert len(qrels_rows) == 140
    assert len({row["qrels_unit_id"] for row in qrels_rows}) == 140
    assert "gq_auto_010" not in {row["query_id"] for row in qrels_rows}
    positive_rows = [row for row in qrels_rows if row["qrels_positive"] is True]
    non_positive_rows = [row for row in qrels_rows if row["qrels_positive"] is False]
    assert len(positive_rows) == 28
    assert len(non_positive_rows) == 112
    for row in positive_rows:
        assert row["relevance_label"] == 3
        assert row["relevance_label_text"] == "EXACT_ANSWER_EVIDENCE"
        assert row["answerability_label"] == 3
        assert row["answerability_label_text"] == "FULLY_ANSWERABLE"
        assert row["binary_exact_evidence_label"] == 1
        assert row["label_provenance"] == "user_bulk_accept_recommendation"
        assert row["not_official_positive_for_exact_evidence_metric"] is False
        assert row["metric_family"] == "official exact-evidence retrieval metrics"
        assert row["metric_scope"] == "source_bound_search_unit_exact_answer_evidence_smoke"
        assert row["benchmark_scope"] == "small official exact-evidence retrieval smoke benchmark"
        assert row["readme_headline_performance_claim_blocked"] is True
        assert row["statistically_representative_product_performance"] is False
        assert row["future_ndcg_name"] == "binary exact-evidence nDCG@K"
    for row in non_positive_rows:
        assert row["relevance_label"] is None
        assert row["relevance_label_text"] == "not_judged_for_topical_relevance"
        assert row["answerability_label"] is None
        assert row["answerability_label_text"] == "not_judged_for_answerability"
        assert row["binary_exact_evidence_label"] == 0
        assert row["label_provenance"] == "derived_from_user_exact_evidence_policy"
        assert row["not_official_positive_for_exact_evidence_metric"] is True
        assert row["human_judged_topical_negative"] is False
        assert row["broad_topical_relevance_label_created"] is False
    for row in qrels_rows:
        assert row["official_metric_denominator_query"] is True
        assert row["qrels_excluded"] is False
        assert row["generation_source"] is False
        assert row["promotion_evidence"] is False
        assert row["gold"] is False
        assert row["metric_computation_allowed_in_v3_4_2"] is False
        assert row["metric_scope"] == "source_bound_search_unit_exact_answer_evidence_smoke"
        assert row["benchmark_scope"] == "small official exact-evidence retrieval smoke benchmark"
        assert row["readme_headline_performance_claim_blocked"] is True
        assert row["statistically_representative_product_performance"] is False
        assert row["source_bound_locator"]
        assert row["document_version_id"]
        assert row["search_unit_id"]

    assert len(exclusions) == 1
    exclusion = exclusions[0]
    assert exclusion["query_id"] == "gq_auto_010"
    assert exclusion["question"] == "2월 실업률은 전년 같은 달보다 어떻게 변했나요?"
    assert exclusion["user_decision"] == "exclude_from_qrels"
    assert exclusion["exclusion_reason"] == "standalone_query_missing_year"
    assert exclusion["user_note"] == (
        "2월 실업률은 전년 같은 달보다 어떻게 변했나요? - 기준 연도 정보가 없어 standalone retrieval qrels에서 제외"
    )
    assert exclusion["official_metric_denominator_included"] is False
    assert exclusion["not_counted_as_miss"] is True
    assert exclusion["not_counted_as_failure"] is True
    assert exclusion["not_counted_as_negative"] is True
    assert exclusion["not_counted_as_unanswerable"] is True
    assert exclusion["retrieval_failure"] is False
    assert exclusion["qrels_positive"] is None
    assert exclusion["source_raw_candidate_row_count"] == 6
    assert exclusion["source_candidate_unit_count"] == 5

    guardrails = event["guardrails"]
    assert guardrails["official_exact_evidence_qrels_created"] is True
    assert guardrails["user_review_decisions_applied"] is True
    assert guardrails["readme_headline_performance_claim_blocked"] is True
    for key in (
        "official_retrieval_metrics_computed",
        "official_ndcg_computed",
        "official_mrr_computed",
        "official_hit_at_k_computed",
        "broad_graded_ndcg_computed",
        "binary_exact_evidence_ndcg_computed",
        "lane_score_collapsed",
        "excluded_query_counted_as_miss",
        "excluded_query_counted_as_failure",
        "excluded_query_counted_as_negative",
        "excluded_query_counted_as_unanswerable",
        "denominator_mutation",
        "answer_citation_denominator_mutation",
        "official_denominator_query_id_set_mutation",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "candidate_artifacts_as_generation_source",
        "generation_used_expected_answer",
        "generation_used_supporting_evidence",
        "generation_used_gold_fields",
        "prompt_context_behavior_change",
        "retrieval_mutation",
        "renderer_mutation",
        "scorer_behavior_mutation",
        "index_or_export_rebuild_performed",
        "export_mutation",
        "silver_mutation",
        "silver_rows_created",
        "production_mutation",
        "promotion_evidence",
        "threshold_tuning",
        "winner_selection",
        "readme_metric_claim_added",
        "readme_headline_performance_claim_added",
        "statistically_representative_product_performance_claim_added",
        "per_run_markdown_created",
    ):
        assert guardrails[key] is False, key
    assert event["active_implementation_queue_empty"] is True
    assert event["next_implementation_phase"] == "v3_4_3_official_exact_evidence_metric_computation"
    assert not report_artifact_path(run_id, "results.jsonl").exists()
    assert not report_artifact_path(run_id, "summary.md").exists()
    assert_no_gold_generation_source_fields(event)
    assert_no_gold_generation_source_fields(coverage)
    assert_no_gold_generation_source_fields(qrels_rows)
    assert_no_gold_generation_source_fields(exclusions)


def test_v3_4_3_computes_lane_b_exact_evidence_retrieval_smoke_metrics_only() -> None:
    run_id = AGENTIC_V3_4_3_OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_SMOKE_METRIC_RUN_ID
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "official_exact_evidence_retrieval_smoke_metrics_computed_v3_4_3"
        and item.get("run_id") == run_id
    )
    metrics = read_json(AGENTIC_V3_4_3_RETRIEVAL_SMOKE_METRICS_JSON)
    per_query_rows = read_jsonl(AGENTIC_V3_4_3_RETRIEVAL_SMOKE_PER_QUERY_JSONL)
    readme = README.read_text(encoding="utf-8")

    assert event["status"] == "OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_SMOKE_METRICS_COMPUTED_SMALL_SAMPLE"
    assert event["measurement_classification"] == "official_exact_evidence_retrieval_smoke_metric_v3_4_3"
    assert event["run_class"] == "official_exact_evidence_retrieval_smoke_metric_computation"
    assert event["metric_family"] == "official exact-evidence retrieval smoke metrics"
    assert event["metric_scope"] == "source_bound_search_unit_exact_answer_evidence_smoke"
    assert event["benchmark_scope"] == "small official exact-evidence retrieval smoke benchmark"
    assert event["primary_ranking_surface"] == "Lane B live_llm_retrieval_topk"
    assert event["primary_lane_source"] == "retrieved_topk"
    assert event["reference_only_surfaces"]["lane_c_query_bound_oracle"] == {
        "coverage_rate": 1.0,
        "included_positive_coverage_count": 28,
        "included_query_count": 28,
        "lane_source": "query_bound_oracle",
        "not_primary_ranking_surface": True,
        "not_used_for_micro_or_macro_metrics": True,
        "ranking_surface": "Lane C query_bound_oracle",
        "reference_only": True,
    }
    assert event["qrels_prerequisite"] == {
        "run_id": AGENTIC_V3_4_2_APPLY_USER_OFFICIAL_RETRIEVAL_QRELS_LABELS_RUN_ID,
        "status_event_found": True,
        "status": "OFFICIAL_EXACT_EVIDENCE_RETRIEVAL_QRELS_READY_METRICS_DEFERRED",
        "included_query_count": 28,
        "excluded_query_count": 1,
    }
    assert event["included_query_count"] == 28
    assert event["excluded_query_count"] == 1
    assert event["excluded_query_ids"] == ["gq_auto_010"]
    assert event["source_family_counts"] == {"PDF": 3, "TEXT": 6, "XLSX": 19}
    assert event["small_sample_warning"] is True
    assert event["readme_headline_allowed"] is False
    assert event["regression_guard_allowed"] is True
    assert event["representative_product_performance_claim_allowed"] is False
    assert event["graded_ndcg_computed"] is False
    assert event["binary_exact_evidence_ndcg_computed"] is True
    assert event["lane_score_collapsed"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["confidence_warning"]["one_query_delta_percentage_points"] == pytest.approx(100 / 28)
    assert "about 3.57 percentage points" in event["confidence_warning"]["text"]

    assert metrics["included_query_count"] == 28
    assert metrics["excluded_query_count"] == 1
    assert metrics["excluded_query_ids"] == ["gq_auto_010"]
    assert metrics["source_family_counts"] == {"PDF": 3, "TEXT": 6, "XLSX": 19}
    assert metrics["excluded_source_family_counts"] == {"PDF": 1}
    assert metrics["primary_ranking_surface"] == "Lane B live_llm_retrieval_topk"
    assert metrics["primary_ranking_surface_only"] is True
    assert metrics["metrics"] == [
        "Hit@1",
        "Hit@3",
        "Hit@5",
        "MRR@5",
        "binary exact-evidence nDCG@5",
    ]
    assert metrics["small_sample_warning"] is True
    assert metrics["readme_headline_allowed"] is False
    assert metrics["regression_guard_allowed"] is True
    assert metrics["representative_product_performance_claim_allowed"] is False
    assert metrics["graded_ndcg_computed"] is False
    assert metrics["binary_exact_evidence_ndcg_computed"] is True
    assert metrics["lane_score_collapsed"] is False

    micro = metrics["micro_overall"]
    assert micro["denominator"] == 28
    assert micro["hit_at_1_count"] == 27
    assert micro["hit_at_1"] == pytest.approx(27 / 28)
    assert micro["hit_at_3_count"] == 28
    assert micro["hit_at_3"] == pytest.approx(1.0)
    assert micro["hit_at_5_count"] == 28
    assert micro["hit_at_5"] == pytest.approx(1.0)
    assert micro["mrr_at_5_sum"] == pytest.approx(27.5)
    assert micro["mrr_at_5"] == pytest.approx(27.5 / 28)
    assert micro["binary_exact_evidence_ndcg_at_5"] == pytest.approx(0.9868189197704093)

    assert metrics["by_source_family"]["PDF"]["denominator"] == 3
    assert metrics["by_source_family"]["PDF"]["hit_at_1"] == pytest.approx(1.0)
    assert metrics["by_source_family"]["TEXT"]["denominator"] == 6
    assert metrics["by_source_family"]["TEXT"]["mrr_at_5"] == pytest.approx(1.0)
    assert metrics["by_source_family"]["XLSX"]["denominator"] == 19
    assert metrics["by_source_family"]["XLSX"]["hit_at_1_count"] == 18
    assert metrics["by_source_family"]["XLSX"]["mrr_at_5"] == pytest.approx(18.5 / 19)

    macro = metrics["macro_by_source_family"]
    assert macro["source_families"] == ["PDF", "TEXT", "XLSX"]
    assert macro["source_family_count"] == 3
    assert macro["hit_at_1"] == pytest.approx((1 + 1 + (18 / 19)) / 3)
    assert macro["hit_at_3"] == pytest.approx(1.0)
    assert macro["hit_at_5"] == pytest.approx(1.0)
    assert macro["mrr_at_5"] == pytest.approx((1 + 1 + (18.5 / 19)) / 3)
    assert macro["binary_exact_evidence_ndcg_at_5"] == pytest.approx(0.9935250833959905)

    assert len(per_query_rows) == 28
    assert "gq_auto_010" not in {row["query_id"] for row in per_query_rows}
    assert Counter(row["source_family"] for row in per_query_rows) == {"PDF": 3, "TEXT": 6, "XLSX": 19}
    assert sum(1 for row in per_query_rows if row["hit_at_1"] is False) == 1
    rank_two = [row for row in per_query_rows if row["best_positive_rank"] == 2]
    assert [row["query_id"] for row in rank_two] == ["gq_xlsx_lookup_007"]
    for row in per_query_rows:
        assert row["primary_ranking_surface"] == "Lane B live_llm_retrieval_topk"
        assert row["primary_lane_source"] == "retrieved_topk"
        assert row["reference_only_surface"] == "Lane C query_bound_oracle"
        assert row["graded_relevance_gain_used"] is False
        assert row["readme_headline_allowed"] is False
        assert row["regression_guard_allowed"] is True
        assert row["representative_product_performance_claim_allowed"] is False
        assert row["promotion_evidence"] is False

    guardrails = event["guardrails"]
    assert guardrails["official_exact_evidence_retrieval_smoke_metrics_computed"] is True
    assert guardrails["official_retrieval_metrics_computed"] is True
    assert guardrails["primary_ranking_surface_lane_b_only"] is True
    assert guardrails["lane_c_reference_only"] is True
    assert guardrails["binary_exact_evidence_ndcg_computed"] is True
    assert guardrails["small_sample_warning"] is True
    assert guardrails["readme_headline_allowed"] is False
    assert guardrails["regression_guard_allowed"] is True
    for key in (
        "graded_ndcg_computed",
        "broad_graded_ndcg_computed",
        "lane_score_collapsed",
        "readme_headline_performance_claim_added",
        "statistically_representative_product_performance_claim_added",
        "representative_product_performance_claim",
        "threshold_tuning",
        "winner_selection",
        "denominator_mutation",
        "answer_citation_denominator_mutation",
        "official_denominator_query_id_set_mutation",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "candidate_artifacts_as_generation_source",
        "generation_used_expected_answer",
        "generation_used_supporting_evidence",
        "generation_used_gold_fields",
        "prompt_context_behavior_change",
        "retrieval_mutation",
        "renderer_mutation",
        "scorer_behavior_mutation",
        "index_or_export_rebuild_performed",
        "export_mutation",
        "silver_mutation",
        "production_mutation",
        "promotion_evidence",
    ):
        assert guardrails[key] is False, key
    assert run_id not in readme
    assert "official exact-evidence retrieval smoke metrics" not in readme
    assert_no_gold_generation_source_fields(event)
    assert_no_gold_generation_source_fields(metrics)
    assert_no_gold_generation_source_fields(per_query_rows)


def test_v3_4_4_readme_metric_card_and_silver_readiness_artifacts_are_guarded() -> None:
    run_id = AGENTIC_V3_4_4_README_RETRIEVAL_SMOKE_AND_SILVER_READINESS_ARTIFACTS_RUN_ID
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    event = next(
        item
        for item in reversed(status_events)
        if item.get("event_type") == "readme_retrieval_smoke_and_silver_readiness_artifacts_v3_4_4"
        and item.get("run_id") == run_id
    )
    source_metrics = read_json(AGENTIC_V3_4_3_RETRIEVAL_SMOKE_METRICS_JSON)
    metric_card = read_json(AGENTIC_V3_4_4_README_METRIC_CARD_JSON)
    readme_section = AGENTIC_V3_4_4_README_SECTION_MD.read_text(encoding="utf-8")
    silver_summary = read_json(AGENTIC_V3_4_4_SILVER_READINESS_SUMMARY_JSON)
    readme = README.read_text(encoding="utf-8")
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    runner_summary = runner.run_v3_4_4_readme_retrieval_smoke_and_silver_readiness_artifacts(
        args=SimpleNamespace(status_jsonl=str(REPORT_DIR / "status.jsonl"))
    )

    assert event["status"] == "README_RETRIEVAL_SMOKE_CARD_READY_SILVER_GENERATION_BLOCKED"
    assert event["run_class"] == "readme_ready_artifacts_and_silver_readiness_boundary"
    assert event["readme_directly_updated"] is False
    assert event["pending_manual_integration"] is True
    assert event["triage_doc_updated"] is False
    assert event["artifact_paths"] == {
        "readme_metric_card_json": report_artifact_repo_relative(run_id, "readme_metric_card.json"),
        "readme_section_md": report_artifact_repo_relative(run_id, "readme_section.md"),
        "silver_readiness_summary_json": report_artifact_repo_relative(run_id, "silver_readiness_summary.json"),
        "status_jsonl": "ai/eval/reports/rag-ingestion/status.jsonl",
        "progress_doc": "docs/rag-ingestion-progress.md",
    }
    assert run_id not in readme
    assert "Retrieval smoke regression guard" not in readme
    assert run_id in runner.REPORT_ARTIFACT_SLUGS
    assert runner.DEFAULT_V3_4_4_README_METRIC_CARD_JSON == AGENTIC_V3_4_4_README_METRIC_CARD_JSON
    assert runner_summary["run_id"] == run_id
    assert runner_summary["artifact_paths"] == event["artifact_paths"]
    assert runner_summary["readme_metric_card"]["metric_family"] == (
        "official exact-evidence retrieval smoke metrics"
    )
    assert runner_summary["silver_readiness_summary"]["silver_generation_blocked"] is True

    assert metric_card["metric_family"] == source_metrics["metric_family"]
    assert metric_card["metric_scope"] == source_metrics["metric_scope"]
    assert metric_card["primary_ranking_surface"] == "Lane B live_llm_retrieval_topk"
    assert metric_card["reference_only_surfaces"]["lane_c_query_bound_oracle"] == {
        "coverage_rate": 1.0,
        "included_positive_coverage_count": 28,
        "included_query_count": 28,
        "lane_source": "query_bound_oracle",
        "not_primary_ranking_surface": True,
        "not_used_for_micro_or_macro_metrics": True,
        "ranking_surface": "Lane C query_bound_oracle",
        "reference_only": True,
    }
    assert metric_card["included_queries"] == 28
    assert metric_card["excluded_queries"] == {
        "count": 1,
        "query_ids": ["gq_auto_010"],
        "reason": "standalone_query_missing_year",
    }
    assert metric_card["source_family_counts"] == {"PDF": 3, "TEXT": 6, "XLSX": 19}

    source_micro = source_metrics["micro_overall"]
    assert metric_card["micro"]["hit_at_1"] == {
        "count": source_micro["hit_at_1_count"],
        "denominator": 28,
        "value": source_micro["hit_at_1"],
    }
    assert metric_card["micro"]["hit_at_3"] == {
        "count": source_micro["hit_at_3_count"],
        "denominator": 28,
        "value": source_micro["hit_at_3"],
    }
    assert metric_card["micro"]["hit_at_5"] == {
        "count": source_micro["hit_at_5_count"],
        "denominator": 28,
        "value": source_micro["hit_at_5"],
    }
    assert metric_card["micro"]["mrr_at_5"] == {
        "sum": source_micro["mrr_at_5_sum"],
        "denominator": 28,
        "value": source_micro["mrr_at_5"],
    }
    assert metric_card["micro"]["binary_exact_evidence_ndcg_at_5"] == {
        "value": source_micro["binary_exact_evidence_ndcg_at_5"],
    }
    assert metric_card["macro_by_source_family"] == {
        "hit_at_1": source_metrics["macro_by_source_family"]["hit_at_1"],
        "hit_at_3": source_metrics["macro_by_source_family"]["hit_at_3"],
        "hit_at_5": source_metrics["macro_by_source_family"]["hit_at_5"],
        "mrr_at_5": source_metrics["macro_by_source_family"]["mrr_at_5"],
        "binary_exact_evidence_ndcg_at_5": source_metrics["macro_by_source_family"][
            "binary_exact_evidence_ndcg_at_5"
        ],
    }

    warnings = metric_card["warnings"]
    assert warnings["small_sample_warning"] is True
    assert warnings["readme_headline_allowed"] is False
    assert warnings["regression_guard_allowed"] is True
    assert warnings["representative_product_performance_claim_allowed"] is False
    assert warnings["one_query_delta_percentage_points"] == pytest.approx(100 / 28)
    assert "not statistically representative product performance" in warnings["small_sample_warning_text"]

    guardrails = metric_card["guardrails"]
    for key in (
        "lane_a_b_c_collapsed_score",
        "threshold_tuning",
        "winner_selection",
        "graded_ndcg",
        "readme_headline_product_performance_claim",
        "representative_product_performance_claim",
        "promotion_evidence",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "answer_citation_denominator_mutation",
        "official_denominator_query_id_set_mutation",
        "prompt_mutation",
        "retrieval_mutation",
        "scorer_mutation",
        "renderer_mutation",
        "index_or_export_mutation",
        "production_mutation",
        "silver_mutation",
        "silver_generation_from_official_denominator_rows",
        "candidate_artifacts_as_generation_source",
    ):
        assert guardrails[key] is False, key

    assert readme_section.startswith("## Retrieval smoke regression guard")
    assert "small 28-query official exact-evidence retrieval smoke benchmark" in readme_section
    assert "metric-pipeline validation and regression guarding" in readme_section
    assert "not a statistically representative product-performance benchmark" in readme_section
    assert "Lane B retrieval placed an exact-evidence SearchUnit at rank 1 for 27/28" in readme_section
    assert "within top 3 for 28/28" in readme_section
    assert "readme_headline_allowed=false" in readme_section
    assert "regression_guard_allowed=true" in readme_section
    assert "Lane C is reference-only" in readme_section
    assert "No graded nDCG or collapsed Lane A/B/C score is reported" in readme_section
    for prohibited in (
        "RAG achieves 96.4% Hit@1",
        "production performance",
        "representative benchmark",
        "winner",
        "promotion evidence",
    ):
        assert prohibited not in readme_section

    assert silver_summary["silver_generation_blocked"] is True
    assert silver_summary["silver_mutation"] is False
    assert silver_summary["silver_jsonl_rows_created"] is False
    assert silver_summary["answer_citation_silver_jsonl_files_created"] == {
        "contract": False,
        "dev": False,
        "holdout": False,
    }
    assert silver_summary["official_denominator_overlap_boundary"] == {
        "official_denominator_query_id_count": 29,
        "official_source_bound_search_unit_rows": 29,
        "official_denominator_overlap_true_count": 29,
        "eligible_dev_holdout_source_candidate_count_from_official_manifest": 0,
        "official_denominator_source_bound_search_units_remain_excluded_from_silver": True,
        "official_29_query_ids_copied_or_relabelled_to_silver_dev_holdout": False,
        "official_29_query_ids_excluded_from_dev_holdout_tuning_silver": True,
    }
    assert silver_summary["strict_non_official_source_bound_candidate_inventory"][
        "counts_by_source_family"
    ] == {"TEXT": 0, "PDF": 3, "XLSX": 4, "total": 7}
    assert silver_summary["strict_non_official_source_bound_candidate_inventory"][
        "candidate_artifacts_used_as_generation_source"
    ] is False
    assert silver_summary["thresholds"]["pilot_threshold_rows"] == 100
    assert silver_summary["thresholds"]["pilot_threshold_met"] is False
    assert silver_summary["thresholds"]["target_rows"] == 1000
    assert silver_summary["thresholds"]["preferred_target_by_source_family"] == {
        "TEXT": 350,
        "PDF": 325,
        "XLSX": 325,
    }
    assert silver_summary["thresholds"]["preferred_target_met"] is False
    assert silver_summary["expected_values_used_for_audit_only"] is True
    assert silver_summary["candidate_artifacts_must_not_be_used_as_generation_source"] is True
    assert silver_summary["candidate_artifacts_used_as_generation_source"] is False
    assert silver_summary["source_inventory_differs_from_v3_3_3"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()

    assert event["silver_generation_blocked"] is True
    assert event["silver_mutation"] is False
    assert event["strict_non_official_source_bound_candidate_counts"] == {
        "TEXT": 0,
        "PDF": 3,
        "XLSX": 4,
        "total": 7,
    }
    assert event["official_denominator_source_bound_overlap_excluded_from_silver"] is True
    assert event["candidate_artifacts_used_as_generation_source"] is False
    assert_generation_guardrail_flags_false(event)
    assert_generation_guardrail_flags_false(metric_card)
    assert_generation_guardrail_flags_false(silver_summary)
    assert_no_gold_generation_source_fields(event)
    assert_no_gold_generation_source_fields(metric_card)
    assert_no_gold_generation_source_fields(silver_summary)


def test_v3_1_7_pdf_window_expansion_preflight_fails_closed_without_safe_locator_metadata() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    units, diagnostic = runner.build_safe_pdf_paragraph_window_units_for_row(
        row={
            "track": "pdf_business_ocr_mm",
            "source_family": "PDF",
            "denominator_locator": {
                "source_pdf_path": "",
                "document_version_id": "",
                "page": 1,
                "physical_page_index": 0,
                "bbox": [0, 0, 10, 10],
                "region_type": "paragraph",
            },
        },
        query_id="gq_auto_010",
        generated_at="2026-05-18T00:00:00+00:00",
    )

    assert units == []
    assert diagnostic["expansion_attempted"] is True
    assert diagnostic["expansion_applied"] is False
    assert diagnostic["locator_safe_metadata_available"] is False
    assert diagnostic["fail_closed_blocker"] == "locator_safe_pdf_window_source_missing"
    assert diagnostic["candidate_artifacts_as_generation_source"] is False
    assert diagnostic["generation_used_expected_answer"] is False
    assert diagnostic["generation_used_supporting_evidence"] is False
    assert diagnostic["generation_used_gold_fields"] is False


def test_v3_1_7_pdf_context_expansion_citation_contract_is_diagnostic_only() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    expansion = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_CONTEXT_DIAGNOSTICS_JSONL)[0]
    citation = runner.build_source_bound_pdf_context_expansion_citation(
        expansion["expansion_units"][0],
        track="pdf_business_ocr_mm",
        query_id="gq_auto_010",
        source_family="PDF",
    )
    payload = citation["search_unit_citation_payload"]

    assert citation["context_expansion"] is True
    assert citation["citation_payload_validation"]["ok"] is True
    assert payload["source_bound_official_denominator"] is False
    assert payload["source_bound_diagnostic_context_expansion"] is True
    assert payload["non_production_diagnostic_context_expansion"] is True
    assert payload["locator_schema"] == "pdf_source_bound_context_expansion_v1"
    assert payload["search_unit_id"] == "pdfwin_b1c6527f848018640ad5ed231877c662"
    assert payload["expansion_policy_name"] == "same_page_pdf_paragraph_line_window_v1"
    assert payload["expansion_policy_version"] == "v1"


def test_v3_1_7_pdf_prompt_context_expansion_is_target_bound_and_query_bound() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    v3_1_4_rows = read_jsonl(AGENTIC_V3_1_4_PDF_RESIDUAL_RESULTS)
    source_queue = {
        "items": [
            {"query_id": "gq_auto_010"},
            {"query_id": "text_namu_v2_0012"},
            {"query_id": "gq_xlsx_lookup_008"},
        ]
    }
    units_by_query_id, diagnostics_by_query_id = runner.build_v3_1_6_pdf_window_expansion_units(
        v3_1_4_rows=v3_1_4_rows,
        remaining_queue=source_queue,
        generated_at="2026-05-18T00:00:00+00:00",
    )
    assert set(units_by_query_id) == {"gq_auto_010"}
    assert set(diagnostics_by_query_id) == {"gq_auto_010"}

    target_row = next(row for row in v3_1_4_rows if row["query_id"] == "gq_auto_010")
    context = runner.build_v3_prompt_context_from_row(
        target_row,
        use_query_bound_only=True,
        mode="query_bound_only_source_bound",
        context_expansion_units=units_by_query_id["gq_auto_010"],
    )
    assert context["prompt_context_source_bound_only"] is True
    assert context["prompt_context_policy"]["diagnostic_context_expansion_allowed"] is True
    assert context["prompt_context_policy"]["diagnostic_context_expansion_count"] == 1
    assert context["prompt_context_policy"]["candidate_artifacts_as_generation_source"] is False
    assert context["prompt_context_policy"]["generation_used_expected_answer"] is False
    assert context["prompt_context_policy"]["generation_used_supporting_evidence"] is False
    assert context["prompt_context_policy"]["generation_used_gold_fields"] is False
    expansion_citations = [citation for citation in context["citations"] if citation.get("context_expansion")]
    assert len(expansion_citations) == 1
    assert expansion_citations[0]["search_unit_id"] == "pdfwin_b1c6527f848018640ad5ed231877c662"
    assert expansion_citations[0]["query_bound"] is True


def test_v3_1_artifact_consistency_preflight_fails_closed_on_stale_summary() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    guardrails = runner.v3_1_guardrails()
    summary = {
        **guardrails,
        "guardrails": guardrails,
        "run_id": "stale-run",
        "status": "ALL_TRACK_FOUNDATION_MEASUREMENT_V3_1_COMPLETED",
        "result_count": 29,
        "diagnostic_only": True,
        "lane_names": list(runner.V3_1_LANE_NAMES),
    }
    rows = [{"query_id": query_id} for query_id in AGENTIC_V3_1_PRIORITY_QUERY_IDS]
    rows.extend({"query_id": f"extra_{idx:02d}"} for idx in range(24))
    triage = {
        "run_id": runner.V3_1_RUN_ID,
        "items": [
            {"priority_rank": idx + 1, "query_id": query_id}
            for idx, query_id in enumerate(AGENTIC_V3_1_PRIORITY_QUERY_IDS)
        ],
    }

    result = runner.v3_1_artifact_consistency_preflight(
        summary=summary,
        rows=rows,
        triage=triage,
        expected_priority_query_ids=AGENTIC_V3_1_PRIORITY_QUERY_IDS,
    )

    assert result["ok"] is False
    assert "v3_1_summary_run_id_mismatch" in result["errors"]
    assert "v3_1_row_run_id_mismatch" in result["errors"]
    assert "v3_1_row_lane_results_mismatch" in result["errors"]


def test_agentic_available_pipeline_row_exception_is_specific_not_pipeline_unavailable() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    class BoomRetriever:
        def retrieve(self, _query: str) -> object:
            raise RuntimeError("synthetic retriever failure after index availability")

    args = SimpleNamespace(
        agent_loop_backend="legacy",
        agent_max_iter=1,
        agent_max_total_ms=1000,
        agent_max_llm_tokens=1000,
        agent_min_stop_confidence=0.0,
    )
    rows = [
        {
            "query_id": "q-row-failure",
            "track": "text_namu_v2_1",
            "question": "실패 분기 확인용 질문",
            "expected_answer": "sentinel answer",
            "supporting_evidence": "sentinel evidence",
        }
    ]

    out = runner.execute_agentic_generation_rows(rows, args, {"_retriever": BoomRetriever()})

    assert len(out) == 1
    row = out[0]
    assert row["failure_category"] == runner.AGENTIC_GENERATION_ROW_FAILED
    assert row["failure_category"] != runner.GENERATION_PIPELINE_UNAVAILABLE
    assert row["agentic_loop_enabled"] is True
    assert row["agentic_loop_executed"] is True
    assert row["scoring_attempted"] is False
    assert row["generated_answer"] == ""
    assert row["generated_citations"] == []
    assert row["retrieved_evidence"] == []
    assert row["infrastructure_blocker_category"] is None


def test_faiss_cuda_build_fails_closed_when_gpu_api_unavailable(
    tmp_path, monkeypatch
) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag import faiss_index as faiss_index_module
    from app.capabilities.rag.faiss_index import FaissIndex

    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_ready", lambda: False)
    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_count", lambda: 0)
    index = FaissIndex(tmp_path / "idx", build_device="cuda")

    with pytest.raises(RuntimeError, match="FAISS GPU build requested"):
        index.build(
            np.ones((2, 4), dtype=np.float32),
            index_version="gpu-required",
            embedding_model="hashing",
        )


def test_faiss_cuda_build_records_gpu_metadata(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag import faiss_index as faiss_index_module
    from app.capabilities.rag.faiss_index import FaissIndex

    calls: list[tuple[str, int | None]] = []

    class _FakeGpuIndex:
        def __init__(self, cpu_index):
            self.cpu_index = cpu_index

        def add(self, vectors):
            calls.append(("add", int(vectors.shape[0])))
            self.cpu_index.add(vectors)

    def _to_gpu(_resources, device, cpu_index):
        calls.append(("to_gpu", int(device)))
        return _FakeGpuIndex(cpu_index)

    def _to_cpu(gpu_index):
        calls.append(("to_cpu", None))
        return gpu_index.cpu_index

    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_ready", lambda: True)
    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_count", lambda: 1)
    monkeypatch.setattr(
        faiss_index_module.faiss,
        "StandardGpuResources",
        lambda: object(),
        raising=False,
    )
    monkeypatch.setattr(
        faiss_index_module.faiss,
        "index_cpu_to_gpu",
        _to_gpu,
        raising=False,
    )
    monkeypatch.setattr(
        faiss_index_module.faiss,
        "index_gpu_to_cpu",
        _to_cpu,
        raising=False,
    )

    index = FaissIndex(tmp_path / "idx", build_device="cuda")
    index.build(
        np.ones((2, 4), dtype=np.float32),
        index_version="gpu-used",
        embedding_model="hashing",
    )

    payload = json.loads((tmp_path / "idx" / "build.json").read_text())
    assert payload["faiss_build_device_requested"] == "cuda"
    assert payload["faiss_gpu_used"] is True
    assert payload["faiss_gpu_count"] == 1
    assert payload["faiss_gpu_device"] == 0
    assert calls == [("to_gpu", 0), ("add", 2), ("to_cpu", None)]


def test_sentence_transformer_embedder_exposes_configured_max_seq_length_for_ingest_manifest() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", max_seq_length=1024)

    assert embedder.max_seq_length == 1024


def resolve_report_artifact_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.parent == REPORT_ARCHIVE_DIR:
        for archive_dir in EXTERNAL_REPORT_ARCHIVE_DIRS:
            archived_external = archive_dir / path.name
            if archived_external.exists():
                return archived_external
        return path
    if path.parent == REPORT_DIR:
        for archive_dir in EXTERNAL_REPORT_ARCHIVE_DIRS:
            archived_external = archive_dir / path.name
            if archived_external.exists():
                return archived_external
        archived = REPORT_ARCHIVE_DIR / path.name
        if archived.exists():
            return archived
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(resolve_report_artifact_path(path).read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in resolve_report_artifact_path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_csv(path: Path) -> list[dict[str, str]]:
    with resolve_report_artifact_path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(resolve_report_artifact_path(path).read_bytes()).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def assert_no_unexpected_eval_query_status(stdout: str) -> None:
    allowed_v3_1_9_policy_paths = {
        "ai/eval/eval_queries/official_denominator_registry.json",
        "ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv",
    }
    allowed_current_silver_policy_paths = {
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
    }
    allowed_paths = allowed_v3_1_9_policy_paths | allowed_current_silver_policy_paths
    unexpected = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().replace("\\", "/") if len(line) > 3 else line.strip().replace("\\", "/")
        if path not in allowed_paths:
            unexpected.append(line)
    assert unexpected == []


def assert_no_gold_generation_source_fields(value: Any) -> None:
    forbidden_keys = {"expected_answer", "supporting_evidence", "human_label"}
    if isinstance(value, dict):
        assert not forbidden_keys.intersection(value)
        for item in value.values():
            assert_no_gold_generation_source_fields(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_gold_generation_source_fields(item)


def assert_generation_guardrail_flags_false(value: Any) -> None:
    false_keys = {
        "promotion_evidence",
        "promotion_gate_auto_run",
        "threshold_tuning",
        "winner_selection",
        "candidate_artifacts_as_generation_source",
        "generation_used_expected_answer",
        "generation_used_supporting_evidence",
        "generation_used_gold_fields",
    }
    if isinstance(value, dict):
        for key in false_keys:
            if key in value:
                assert value[key] is False, key
        if "diagnostic_only" in value:
            assert value["diagnostic_only"] is True
        for item in value.values():
            assert_generation_guardrail_flags_false(item)
    elif isinstance(value, list):
        for item in value:
            assert_generation_guardrail_flags_false(item)


def official_file_identity(path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_metric_first_run_v1 as official

    identity = official.file_identity(resolve_report_artifact_path(path))
    if path.is_relative_to(ROOT):
        identity["path"] = path.relative_to(ROOT).as_posix()
    return identity


def numeric_bbox(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        return all(isinstance(float(item), float) for item in value)
    except (TypeError, ValueError):
        return False
