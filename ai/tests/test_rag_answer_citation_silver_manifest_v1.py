from __future__ import annotations

import json
import os
import sys
import csv
import inspect
from collections import defaultdict
from pathlib import Path
from typing import Any

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
SILVER_DIR = ROOT / "ai" / "eval" / "silver"
MANIFEST = SILVER_DIR / "answer_citation_silver_manifest_v1.json"
READINESS = SILVER_DIR / "answer_citation_silver_readiness_v1.json"
STATUS_JSONL = REPORT_DIR / "status.jsonl"
V3_5_0_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_0_"
    "strict_non_official_source_bound_capacity_expansion"
)
V3_5_0_CAPACITY_SUMMARY = REPORT_DIR / f"{V3_5_0_RUN_ID}_capacity_summary.json"
V3_5_0_MANIFEST_READY = REPORT_DIR / f"{V3_5_0_RUN_ID}_manifest_ready_candidates.jsonl"
V3_5_0_BLOCKED_OR_CONVERTIBLE = (
    REPORT_DIR / f"{V3_5_0_RUN_ID}_blocked_or_convertible_candidates.jsonl"
)
V3_5_0_ACQUISITION_PLAN = REPORT_DIR / f"{V3_5_0_RUN_ID}_acquisition_plan.json"
V3_5_1_RUN_ID = "official_answer_citation_agentic_loop_run_v3_5_1_pilot_silver_source_manifest_freeze"
V3_5_1_PILOT_SOURCE_MANIFEST = REPORT_DIR / f"{V3_5_1_RUN_ID}_pilot_source_manifest.jsonl"
V3_5_1_FREEZE_SUMMARY = REPORT_DIR / f"{V3_5_1_RUN_ID}_freeze_summary.json"
V3_5_1_FREEZE_AUDIT = REPORT_DIR / f"{V3_5_1_RUN_ID}_freeze_audit.jsonl"
V3_5_1_SELECTION_RATIONALE = REPORT_DIR / f"{V3_5_1_RUN_ID}_selection_rationale.json"
V3_5_2_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_2_"
    "xlsx_source_value_manifest_repair_and_acquisition"
)
V3_5_2_XLSX_MANIFEST_READY = REPORT_DIR / f"{V3_5_2_RUN_ID}_xlsx_manifest_ready_candidates.jsonl"
V3_5_2_XLSX_BLOCKED_OR_CONVERTIBLE = (
    REPORT_DIR / f"{V3_5_2_RUN_ID}_xlsx_blocked_or_convertible_candidates.jsonl"
)
V3_5_2_XLSX_SOURCE_COLLECTION_MANIFEST = (
    REPORT_DIR / f"{V3_5_2_RUN_ID}_xlsx_source_collection_manifest.json"
)
V3_5_2_POST_XLSX_CAPACITY_SUMMARY = REPORT_DIR / f"{V3_5_2_RUN_ID}_post_xlsx_capacity_summary.json"
V3_5_3_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_5_3_"
    "pdf_page_bbox_source_text_manifest_repair_and_acquisition"
)
V3_5_3_PDF_MANIFEST_READY = REPORT_DIR / f"{V3_5_3_RUN_ID}_pdf_manifest_ready_candidates.jsonl"
V3_5_3_PDF_BLOCKED_OR_CONVERTIBLE = (
    REPORT_DIR / f"{V3_5_3_RUN_ID}_pdf_blocked_or_convertible_candidates.jsonl"
)
V3_5_3_PDF_SOURCE_COLLECTION_MANIFEST = REPORT_DIR / f"{V3_5_3_RUN_ID}_pdf_source_collection_manifest.json"
V3_5_3_POST_PDF_CAPACITY_SUMMARY = REPORT_DIR / f"{V3_5_3_RUN_ID}_post_pdf_capacity_summary.json"
V3_5_3_BALANCED_CAPACITY_SUMMARY = REPORT_DIR / f"{V3_5_3_RUN_ID}_balanced_capacity_summary.json"
V3_5_4_RUN_ID = "official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze"
V3_5_4_BALANCED_SOURCE_MANIFEST = REPORT_DIR / f"{V3_5_4_RUN_ID}_balanced_source_manifest.jsonl"
V3_5_4_FREEZE_SUMMARY = REPORT_DIR / f"{V3_5_4_RUN_ID}_freeze_summary.json"
V3_5_4_FREEZE_AUDIT = REPORT_DIR / f"{V3_5_4_RUN_ID}_freeze_audit.jsonl"
V3_5_4_AUDIT_SAMPLE_PACKET = REPORT_DIR / f"{V3_5_4_RUN_ID}_audit_sample_packet.jsonl"
V3_5_4_NEXT_PHASE_POLICY_BOUNDARY = (
    REPORT_DIR / f"{V3_5_4_RUN_ID}_next_phase_policy_boundary.json"
)
V3_5_5_RUN_ID = "official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit"
V3_5_5_QUALITY_SUMMARY = REPORT_DIR / f"{V3_5_5_RUN_ID}_quality_summary.json"
V3_5_5_MANIFEST_VALIDATION = REPORT_DIR / f"{V3_5_5_RUN_ID}_manifest_validation.jsonl"
V3_5_5_AUDIT_SAMPLE_REVIEW_PACKET = REPORT_DIR / f"{V3_5_5_RUN_ID}_audit_sample_review_packet.jsonl"
V3_5_5_DUPLICATE_HASH_AUDIT = REPORT_DIR / f"{V3_5_5_RUN_ID}_duplicate_hash_audit.jsonl"
V3_5_5_RECOMMENDED_REPAIR_QUEUE = REPORT_DIR / f"{V3_5_5_RUN_ID}_recommended_repair_queue.jsonl"
V3_5_5_NEXT_PHASE_POLICY_BOUNDARY = REPORT_DIR / f"{V3_5_5_RUN_ID}_next_phase_policy_boundary.json"
V3_6_0_RUN_ID = "official_answer_citation_agentic_loop_run_v3_6_0_low_touch_noisy_silver_policy_application"
V3_6_0_POLICY_APPROVAL_SUMMARY = REPORT_DIR / f"{V3_6_0_RUN_ID}_policy_approval_summary.json"
V3_6_0_GENERATION_CONTRACT = REPORT_DIR / f"{V3_6_0_RUN_ID}_generation_contract.json"
V3_6_0_USER_DECISION_MATRIX = REPORT_DIR / f"{V3_6_0_RUN_ID}_user_decision_matrix.jsonl"
V3_6_0_GUARDRAIL_SUMMARY = REPORT_DIR / f"{V3_6_0_RUN_ID}_guardrail_summary.json"
V3_6_1_RUN_ID = "official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation"
V3_6_1_WEAK_SILVER_CANDIDATES = REPORT_DIR / f"{V3_6_1_RUN_ID}_weak_silver_candidates.jsonl"
V3_6_1_GENERATION_SUMMARY = REPORT_DIR / f"{V3_6_1_RUN_ID}_generation_summary.json"
V3_6_1_SPLIT_MANIFEST = REPORT_DIR / f"{V3_6_1_RUN_ID}_split_manifest.json"
V3_6_1_QUALITY_DISTRIBUTION = REPORT_DIR / f"{V3_6_1_RUN_ID}_generation_quality_distribution.json"
V3_6_1_BLOCKED_ROWS = REPORT_DIR / f"{V3_6_1_RUN_ID}_generation_blocked_rows.jsonl"
V3_6_1_POLICY_COMPLIANCE_AUDIT = REPORT_DIR / f"{V3_6_1_RUN_ID}_policy_compliance_audit.json"
V3_6_1_NEXT_PHASE_RECOMMENDATION = REPORT_DIR / f"{V3_6_1_RUN_ID}_next_phase_recommendation.json"
V3_6_2_RUN_ID = "official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval"
V3_6_2_CANDIDATE_SANITY_SUMMARY = REPORT_DIR / f"{V3_6_2_RUN_ID}_candidate_sanity_summary.json"
V3_6_2_CANDIDATE_SANITY_PER_ROW = REPORT_DIR / f"{V3_6_2_RUN_ID}_candidate_sanity_per_row.jsonl"
V3_6_2_CANDIDATE_QUARANTINE_ROWS = REPORT_DIR / f"{V3_6_2_RUN_ID}_candidate_quarantine_rows.jsonl"
V3_6_2_CANDIDATE_METRIC_FEASIBILITY = REPORT_DIR / f"{V3_6_2_RUN_ID}_candidate_metric_feasibility.json"
V3_6_2_SPLIT_INDEPENDENCE_AUDIT = REPORT_DIR / f"{V3_6_2_RUN_ID}_split_independence_audit.json"
V3_6_2_HASH_CONTRACT_AUDIT = REPORT_DIR / f"{V3_6_2_RUN_ID}_hash_contract_audit.json"
V3_6_2_NEXT_PHASE_RECOMMENDATION = REPORT_DIR / f"{V3_6_2_RUN_ID}_next_phase_recommendation.json"
V3_6_3_RUN_ID = "official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze"
V3_6_3_MANIFEST_SUMMARY = REPORT_DIR / f"{V3_6_3_RUN_ID}_diagnostic_weak_noisy_silver_manifest_summary.json"
V3_6_3_MANIFEST_ALL = REPORT_DIR / f"{V3_6_3_RUN_ID}_diagnostic_weak_noisy_silver_manifest_all.jsonl"
V3_6_3_MANIFEST_CORE = REPORT_DIR / f"{V3_6_3_RUN_ID}_diagnostic_weak_noisy_silver_manifest_core.jsonl"
V3_6_3_MANIFEST_REVIEW_ONLY = REPORT_DIR / f"{V3_6_3_RUN_ID}_diagnostic_weak_noisy_silver_manifest_review_only.jsonl"
V3_6_3_MANIFEST_QUARANTINE = REPORT_DIR / f"{V3_6_3_RUN_ID}_diagnostic_weak_noisy_silver_manifest_quarantine.jsonl"
V3_6_3_MANIFEST_POLICY_AUDIT = REPORT_DIR / f"{V3_6_3_RUN_ID}_diagnostic_weak_noisy_silver_manifest_policy_audit.json"
V3_6_3_NEXT_PHASE_RECOMMENDATION = (
    REPORT_DIR / f"{V3_6_3_RUN_ID}_diagnostic_weak_noisy_silver_manifest_next_phase_recommendation.json"
)
V3_6_4_RUN_ID = "official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric"
V3_6_4_SUMMARY = REPORT_DIR / f"{V3_6_4_RUN_ID}_summary.json"
V3_6_4_PER_ROW = REPORT_DIR / f"{V3_6_4_RUN_ID}_per_row.jsonl"
V3_6_4_AGGREGATE_BY_BUCKET = REPORT_DIR / f"{V3_6_4_RUN_ID}_aggregate_by_bucket.json"
V3_6_4_FAILURE_TAXONOMY = REPORT_DIR / f"{V3_6_4_RUN_ID}_failure_taxonomy.json"
V3_6_4_SAMPLE_REVIEW = REPORT_DIR / f"{V3_6_4_RUN_ID}_sample_review.jsonl"
V3_6_4_POLICY_AUDIT = REPORT_DIR / f"{V3_6_4_RUN_ID}_policy_audit.json"
V3_6_4_NEXT_PHASE_RECOMMENDATION = REPORT_DIR / f"{V3_6_4_RUN_ID}_next_phase_recommendation.json"
V3_6_5_RUN_ID = "official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage"
V3_6_5_SUMMARY = REPORT_DIR / f"{V3_6_5_RUN_ID}_summary.json"
V3_6_5_PER_ROW = REPORT_DIR / f"{V3_6_5_RUN_ID}_per_row.jsonl"
V3_6_5_BLOCKER_MATRIX = REPORT_DIR / f"{V3_6_5_RUN_ID}_blocker_matrix.json"
V3_6_5_RUNTIME_SURFACE_AUDIT = REPORT_DIR / f"{V3_6_5_RUN_ID}_runtime_surface_audit.json"
V3_6_5_REFERENCE_SURFACE_AUDIT = REPORT_DIR / f"{V3_6_5_RUN_ID}_reference_surface_audit.json"
V3_6_5_DB_SURFACE_AUDIT = REPORT_DIR / f"{V3_6_5_RUN_ID}_db_surface_audit.json"
V3_6_5_LOCAL_LLM_SURFACE_AUDIT = REPORT_DIR / f"{V3_6_5_RUN_ID}_local_llm_surface_audit.json"
V3_6_5_POLICY_AUDIT = REPORT_DIR / f"{V3_6_5_RUN_ID}_policy_audit.json"
V3_6_5_NEXT_PHASE_RECOMMENDATION = REPORT_DIR / f"{V3_6_5_RUN_ID}_next_phase_recommendation.json"
V3_6_6_RUN_ID = "official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe"
V3_6_6_SUMMARY = REPORT_DIR / f"{V3_6_6_RUN_ID}_summary.json"
V3_6_6_REFERENCE_SIDECAR = REPORT_DIR / f"{V3_6_6_RUN_ID}_reference_sidecar.jsonl"
V3_6_6_CORE_SMOKE_SAMPLE = REPORT_DIR / f"{V3_6_6_RUN_ID}_core_smoke_sample.jsonl"
V3_6_6_RUNTIME_PROBE_SUMMARY = REPORT_DIR / f"{V3_6_6_RUN_ID}_runtime_probe_summary.json"
V3_6_6_DB_RETRIEVAL_SURFACE_AUDIT = REPORT_DIR / f"{V3_6_6_RUN_ID}_db_retrieval_surface_audit.json"
V3_6_6_POLICY_AUDIT = REPORT_DIR / f"{V3_6_6_RUN_ID}_policy_audit.json"
V3_6_6_NEXT_PHASE_RECOMMENDATION = REPORT_DIR / f"{V3_6_6_RUN_ID}_next_phase_recommendation.json"
V3_6_7_RUN_ID = "official_answer_citation_agentic_loop_run_v3_6_7_runtime_stability_probe_for_core_only"
V3_6_7_SUMMARY = REPORT_DIR / f"{V3_6_7_RUN_ID}_summary.json"
V3_6_7_RUNTIME_ATTEMPTS = REPORT_DIR / f"{V3_6_7_RUN_ID}_runtime_attempts.jsonl"
V3_6_7_RUNTIME_STABILITY_SUMMARY = REPORT_DIR / f"{V3_6_7_RUN_ID}_runtime_stability_summary.json"
V3_6_7_POLICY_AUDIT = REPORT_DIR / f"{V3_6_7_RUN_ID}_policy_audit.json"
V3_6_7_NEXT_PHASE_RECOMMENDATION = REPORT_DIR / f"{V3_6_7_RUN_ID}_next_phase_recommendation.json"
V3_6_7_RECOMMENDATION_CHOICES = {
    "v3_6_7_core_only_live_diagnostic_weak_noisy_silver_metric",
    "v3_6_7_manifest_locator_live_retrieval_probe",
    "v3_6_7_runtime_stability_probe_for_core_only",
    "v3_6_7_reference_sidecar_recovery_or_compaction_fix",
}
V3_6_8_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_8_"
    "nonprod_all_source_index_materialization_and_canonical_payload_wiring"
)
V3_6_8_SUMMARY = REPORT_DIR / f"{V3_6_8_RUN_ID}_summary.json"
V3_6_8_SOURCE_INVENTORY = REPORT_DIR / f"{V3_6_8_RUN_ID}_source_inventory.json"
V3_6_8_INDEX_BUILD_SUMMARY = REPORT_DIR / f"{V3_6_8_RUN_ID}_index_build_summary.json"
V3_6_8_PAYLOAD_CONTRACT_SUMMARY = REPORT_DIR / f"{V3_6_8_RUN_ID}_payload_contract_summary.json"
V3_6_8_RETRIEVAL_SMOKE_DIAGNOSTICS = REPORT_DIR / f"{V3_6_8_RUN_ID}_retrieval_smoke_diagnostics.jsonl"
V3_6_8_FAILURE_BUCKETS = REPORT_DIR / f"{V3_6_8_RUN_ID}_failure_buckets.json"
V3_6_8_INDEX_DIR = ROOT / "ai" / "eval" / "indexes" / "rag-data-all-source-nonprod-v1"
V3_6_8_INDEX_BUILD = V3_6_8_INDEX_DIR / "build.json"
V3_6_8_INDEX_INGEST_MANIFEST = V3_6_8_INDEX_DIR / "ingest_manifest.json"
V3_6_8_INDEX_SEARCH_UNIT_MANIFEST = V3_6_8_INDEX_DIR / "search_unit_manifest.jsonl"
V3_6_8_INDEX_SOURCE_INVENTORY = V3_6_8_INDEX_DIR / "source_inventory.json"
V3_6_8_INDEX_PAYLOAD_CONTRACT = V3_6_8_INDEX_DIR / "payload_contract_summary.json"
V3_6_8_OUTCOMES = {
    "ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED",
    "ALL_SOURCE_INDEX_BUILT_PAYLOAD_PARTIAL",
    "INDEX_MATERIALIZATION_BLOCKED",
    "PAYLOAD_WIRED_BUT_LLM_CITATION_COPY_BLOCKED",
}
V3_6_8_SOURCE_REGISTRY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_8_"
    "source_registry_first_evidence_bundle_architecture_audit"
)
V3_6_8_SOURCE_REGISTRY_SUMMARY = REPORT_DIR / f"{V3_6_8_SOURCE_REGISTRY_RUN_ID}_summary.json"
V3_6_8_SOURCE_REGISTRY_SOURCE_OBJECT_AUDIT = (
    REPORT_DIR / f"{V3_6_8_SOURCE_REGISTRY_RUN_ID}_source_object_audit.json"
)
V3_6_8_SOURCE_REGISTRY_SEARCHUNIT_ROLE_AUDIT = (
    REPORT_DIR / f"{V3_6_8_SOURCE_REGISTRY_RUN_ID}_searchunit_role_audit.json"
)
V3_6_8_SOURCE_REGISTRY_EVIDENCE_BUNDLE_CONTRACT = (
    REPORT_DIR / f"{V3_6_8_SOURCE_REGISTRY_RUN_ID}_evidence_bundle_contract.json"
)
V3_6_8_SOURCE_REGISTRY_TRACK_ROUTING_AUDIT = (
    REPORT_DIR / f"{V3_6_8_SOURCE_REGISTRY_RUN_ID}_track_routing_audit.json"
)
V3_6_8_SOURCE_REGISTRY_FAILURE_BUCKETS = (
    REPORT_DIR / f"{V3_6_8_SOURCE_REGISTRY_RUN_ID}_failure_buckets.json"
)
V3_6_8_SOURCE_REGISTRY_OUTCOMES = {
    "SOURCE_REGISTRY_EVIDENCE_ARCHITECTURE_READY",
    "SEARCHUNIT_OVERLOADED_BLOCKER",
    "SOURCE_REGISTRY_MISSING_BLOCKER",
    "VECTOR_DB_COUPLING_BLOCKER",
    "TRACK_ROUTING_OVERFIT_BLOCKER",
}
V3_6_9_SEARCHUNIT_SOURCEATOM_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_6_9_"
    "searchunit_searchview_sourceatom_refactor"
)
V3_6_9_SEARCHUNIT_SOURCEATOM_SUMMARY = REPORT_DIR / f"{V3_6_9_SEARCHUNIT_SOURCEATOM_RUN_ID}_summary.json"
V3_6_9_SEARCHUNIT_SOURCEATOM_CONTRACT = (
    REPORT_DIR / f"{V3_6_9_SEARCHUNIT_SOURCEATOM_RUN_ID}_contract_refactor.json"
)
V3_6_9_SEARCHUNIT_SOURCEATOM_ADAPTER = (
    REPORT_DIR / f"{V3_6_9_SEARCHUNIT_SOURCEATOM_RUN_ID}_search_view_adapter_diagnostics.json"
)
V3_6_9_SEARCHUNIT_SOURCEATOM_HYDRATION = (
    REPORT_DIR / f"{V3_6_9_SEARCHUNIT_SOURCEATOM_RUN_ID}_source_atom_hydration_smoke.json"
)
V3_6_9_SEARCHUNIT_SOURCEATOM_FAILURE_BUCKETS = (
    REPORT_DIR / f"{V3_6_9_SEARCHUNIT_SOURCEATOM_RUN_ID}_failure_buckets.json"
)
V3_6_9_SEARCHUNIT_SOURCEATOM_OUTCOMES = {
    "SEARCHUNIT_SEARCHVIEW_SOURCEATOM_CONTRACT_READY",
    "SEARCHUNIT_SEARCHVIEW_SOURCEATOM_REFACTOR_BLOCKED",
    "SOURCE_REGISTRY_MATERIALIZATION_REQUIRED",
    "VECTOR_METADATA_DECOUPLING_REQUIRED",
}
V3_7_0_SOURCE_REGISTRY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_0_"
    "source_registry_materialization"
)
V3_7_0_SOURCE_REGISTRY_SUMMARY = REPORT_DIR / f"{V3_7_0_SOURCE_REGISTRY_RUN_ID}_summary.json"
V3_7_0_SOURCE_REGISTRY_SOURCE_INVENTORY = (
    REPORT_DIR / f"{V3_7_0_SOURCE_REGISTRY_RUN_ID}_source_inventory.json"
)
V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_DIAGNOSTICS = (
    REPORT_DIR / f"{V3_7_0_SOURCE_REGISTRY_RUN_ID}_materialization_diagnostics.jsonl"
)
V3_7_0_SOURCE_REGISTRY_HYDRATION_SMOKE = (
    REPORT_DIR / f"{V3_7_0_SOURCE_REGISTRY_RUN_ID}_hydration_smoke.json"
)
V3_7_0_SOURCE_REGISTRY_FAILURE_BUCKETS = (
    REPORT_DIR / f"{V3_7_0_SOURCE_REGISTRY_RUN_ID}_failure_buckets.json"
)
SOURCE_ATOM_REGISTRY_DIR = ROOT / "ai" / "eval" / "source_registry"
SOURCE_ATOM_REGISTRY_JSONL = SOURCE_ATOM_REGISTRY_DIR / "source_atom_registry_v1.jsonl"
SOURCE_ATOM_REGISTRY_BUILD_JSON = SOURCE_ATOM_REGISTRY_DIR / "source_atom_registry_build.json"
SOURCE_ATOM_REGISTRY_INVENTORY_JSON = SOURCE_ATOM_REGISTRY_DIR / "source_atom_registry_inventory.json"
SOURCE_ATOM_REGISTRY_BLOCKED_JSONL = SOURCE_ATOM_REGISTRY_DIR / "source_atom_registry_blocked.jsonl"
V3_7_0_SOURCE_REGISTRY_OUTCOMES = {
    "SOURCE_REGISTRY_MATERIALIZED_READY",
    "SOURCE_REGISTRY_MATERIALIZED_PARTIAL",
    "SOURCE_REGISTRY_MATERIALIZATION_BLOCKED",
    "RAW_SOURCE_LINEAGE_BLOCKED",
    "SNAPSHOT_ONLY_POLICY_BLOCKED",
}
V3_7_1_ALL_SOURCE_CITABLE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_1_"
    "all_source_citable_nonprod_index_build"
)
V3_7_1_ALL_SOURCE_CITABLE_SUMMARY = REPORT_DIR / f"{V3_7_1_ALL_SOURCE_CITABLE_RUN_ID}_summary.json"
V3_7_1_ALL_SOURCE_CITABLE_SOURCE_INVENTORY = (
    REPORT_DIR / f"{V3_7_1_ALL_SOURCE_CITABLE_RUN_ID}_source_inventory.json"
)
V3_7_1_ALL_SOURCE_CITABLE_INDEX_BUILD_SUMMARY = (
    REPORT_DIR / f"{V3_7_1_ALL_SOURCE_CITABLE_RUN_ID}_index_build_summary.json"
)
V3_7_1_ALL_SOURCE_CITABLE_HYDRATION_SMOKE = (
    REPORT_DIR / f"{V3_7_1_ALL_SOURCE_CITABLE_RUN_ID}_hydration_smoke.json"
)
V3_7_1_ALL_SOURCE_CITABLE_FAILURE_BUCKETS = (
    REPORT_DIR / f"{V3_7_1_ALL_SOURCE_CITABLE_RUN_ID}_failure_buckets.json"
)
V3_7_1_ALL_SOURCE_CITABLE_INDEX_DIR = (
    ROOT / "ai" / "eval" / "indexes" / "rag-data-all-source-citable-nonprod-v1"
)
V3_7_1_ALL_SOURCE_CITABLE_OUTCOMES = {
    "ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILT",
    "ALL_SOURCE_CITABLE_INDEX_PARTIAL",
    "ALL_SOURCE_CITABLE_INDEX_BLOCKED",
    "SOURCE_REGISTRY_NOT_READY",
}
V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_2_"
    "source_registry_backed_retrieval_smoke_report"
)
V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY = (
    REPORT_DIR / f"{V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID}_summary.json"
)
V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS = (
    REPORT_DIR / f"{V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID}_topk_rows.jsonl"
)
V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_FAILURE_BUCKETS = (
    REPORT_DIR / f"{V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID}_failure_buckets.json"
)
V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_PER_TRACK = (
    REPORT_DIR / f"{V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID}_per_track_breakdown.json"
)
V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SILVER_OVERLAY = (
    REPORT_DIR / f"{V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID}_silver_1000_diagnostic_overlay.json"
)
V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_BUCKETS = [
    "search_miss",
    "source_atom_missing",
    "source_atom_blocked",
    "locator_incomplete",
    "evidence_bundle_render_failed",
    "citation_render_failed",
    "snapshot_only",
    "adapter_missing",
    "track_mismatch",
]


def require_v3_7_2_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return
    message = "missing v3_7_2 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_7_2_ARTIFACTS_REQUIRED") == "1":
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


SOURCE_BOUND_SEARCH_UNIT_MANIFEST = (
    ROOT / "ai" / "eval" / "indexes" / "rag-data-official-denominator-v1" / "search_unit_manifest.jsonl"
)
SILVER_JSONL_BY_SPLIT = {
    "contract": SILVER_DIR / "answer_citation_silver_contract_v1.jsonl",
    "dev": SILVER_DIR / "answer_citation_silver_dev_v1.jsonl",
    "holdout": SILVER_DIR / "answer_citation_silver_holdout_v1.jsonl",
}
OFFICIAL_INPUT_CONFIG = REPORT_DIR / "metric_input_v1.json"
FIRST_RUN = REPORT_DIR / "baseline_v1.json"
XLSX_CANDIDATE = REPORT_DIR / "xlsx_candidate_v1.jsonl"
PDF_CANDIDATE = REPORT_DIR / "pdf_candidate_v1.jsonl"
AGENTIC_SUMMARY = REPORT_ARCHIVE_DIR / "agentic_v1_summary.json"
AGENTIC_ATTRIBUTION = REPORT_ARCHIVE_DIR / "agentic_v1_failure.json"
README = ROOT / "README.md"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"


def test_answer_citation_silver_manifest_locks_policy_and_taxonomy() -> None:
    manifest = read_json(MANIFEST)

    assert manifest["purpose"] == "anti_overfit_generalization_and_source_bound_contract"
    assert manifest["silver_set_is_gold"] is False
    assert manifest["silver_set_is_official_metric_denominator"] is False
    assert manifest["silver_set_is_promotion_evidence"] is False
    assert manifest["silver_set_used_for_generation"] is False
    assert manifest["expected_values_used_for_audit_only"] is True
    assert manifest["official_denominator_query_ids_excluded_from_tuning_silver"] is True
    assert manifest["candidate_artifacts_used_as_generation_source"] is False
    assert manifest["production_index_path_used"] is False
    assert manifest["minimum_safe_source_candidate_schema"] == {
        "id_field": "query_id_or_candidate_id",
        "required_fields": [
            "source_family",
            "source_bound_locator",
            "document_version_id",
            "search_unit_id",
            "source_text_available",
            "generation_source",
            "promotion_evidence",
            "official_denominator_overlap",
        ],
        "required_boolean_values": {
            "generation_source": False,
            "promotion_evidence": False,
            "official_denominator_overlap": False,
        },
        "forbidden_fields": [
            "expected_answer",
            "supporting_evidence",
            "relevance_label",
            "answerability_label",
            "gold_label",
            "human_label",
        ],
    }
    assert manifest["non_production_index"]["target_index_path"] == (
        "ai/eval/indexes/rag-data-official-denominator-v1"
    )
    assert manifest["non_production_index"]["production_index_path_used"] is False
    overlap_scan = manifest["source_bound_material_audit"]["official_denominator_overlap_scan"]
    assert overlap_scan["source_bound_search_unit_manifest_rows"] == 29
    assert overlap_scan["official_denominator_overlap_true_count"] == 29
    assert overlap_scan["official_denominator_overlap_false_count"] == 0
    assert overlap_scan["eligible_dev_holdout_source_candidate_count"] == 0
    assert manifest["source_bound_material_audit"]["safe_source_manifests_can_be_created"] is False

    assert set(manifest["splits"]) == {"contract", "dev", "holdout", "sealed"}
    assert manifest["splits"]["contract"]["allowed_use"] == "implementation_regression_only"
    assert manifest["splits"]["dev"]["allowed_use"] == "tuning_allowed"
    assert manifest["splits"]["holdout"]["allowed_use"] == "aggregate_monitoring_only_during_tuning"
    assert manifest["splits"]["sealed"]["allowed_use"] == "final_pre_promotion_sanity_only"
    assert manifest["splits"]["contract"]["tuning_allowed"] is False
    assert manifest["splits"]["dev"]["tuning_allowed"] is True
    assert manifest["splits"]["holdout"]["tuning_allowed"] is False
    assert manifest["splits"]["sealed"]["tuning_allowed"] is False

    assert manifest["label_confidence"] == ["high", "medium", "low"]
    leakage_policy = manifest["leakage_policy"]
    assert leakage_policy["same_leakage_group_id_cannot_cross"] == [
        "dev",
        "holdout",
        "sealed",
    ]
    assert leakage_policy["same_query_template_family_and_source_locator_family_should_not_cross_dev_holdout"] is True
    assert leakage_policy["official_query_ids_must_not_appear_in_dev_or_holdout_tuning_silver"] is True

    serialized = json.dumps(manifest, ensure_ascii=False)
    assert "expected_answer_used_for_generation" not in serialized
    assert "supporting_evidence_used_for_generation" not in serialized
    assert "prod-index" not in json.dumps(manifest["non_production_index"], ensure_ascii=False).lower()


def test_answer_citation_silver_rows_or_readiness_are_source_bound_and_non_leaky() -> None:
    official_query_ids = official_denominator_query_ids()
    rows_by_split = {split: read_jsonl_if_exists(path) for split, path in SILVER_JSONL_BY_SPLIT.items()}
    all_rows = [row for rows in rows_by_split.values() for row in rows]

    if not all_rows:
        readiness = read_json(READINESS)
        assert readiness["status"] == "BLOCKED_SOURCE_BOUND_SILVER_SOURCE_DATA_MISSING"
        assert readiness["silver_jsonl_files_created"] == {
            "contract": False,
            "dev": False,
            "holdout": False,
        }
        assert readiness["per_track_counts"] == {
            "text_namu_v2_1": 0,
            "xlsx_business_structured": 0,
            "pdf_business_ocr_mm": 0,
        }
        assert readiness["official_denominator_query_ids_excluded_from_tuning_silver"] is True
        assert readiness["candidate_artifacts_used_as_generation_source"] is False
        assert readiness["expected_values_used_for_audit_only"] is True
        assert readiness["silver_set_used_for_generation"] is False
        assert readiness["minimum_safe_source_candidate_schema"]["required_boolean_values"] == {
            "generation_source": False,
            "promotion_evidence": False,
            "official_denominator_overlap": False,
        }
        blocker = readiness["source_data_decision"]
        assert blocker["safe_source_bound_answer_citation_source_data_available"] is False
        assert blocker["safe_source_manifests_can_be_created"] is False
        assert blocker["precise_blocker"] == (
            "Only official-denominator source-bound SearchUnits are currently available; all 29 overlap "
            "the official denominator and cannot satisfy official_denominator_overlap=false for "
            "dev/holdout tuning silver."
        )
        return

    case_ids = [clean(row.get("silver_case_id")) for row in all_rows]
    assert len(case_ids) == len(set(case_ids))
    assert all(case_ids)
    for split, rows in rows_by_split.items():
        for row in rows:
            assert row["split"] == split
            assert row["used_for_generation"] is False
            assert row["promotion_evidence"] is False
            assert row.get("silver_set_is_gold") is not True
            assert row.get("silver_set_is_official_metric_denominator") is not True
            assert row.get("candidate_artifacts_used_as_generation_source") is not True
            assert row.get("expected_values_used_for_generation") is not True
            assert row.get("supporting_evidence_used_for_generation") is not True
            assert "production" not in json.dumps(row, ensure_ascii=False).lower()
            assert clean(row.get("label_confidence")) in {"high", "medium", "low"}
            assert clean(row.get("query_template_family"))
            assert clean(row.get("leakage_group_id"))
            if split in {"dev", "holdout"}:
                assert clean(row.get("query_id")) not in official_query_ids
            if row["track"] == "text_namu_v2_1":
                assert_text_locator(row)
            elif row["track"] == "xlsx_business_structured":
                assert_xlsx_locator(row)
            elif row["track"] == "pdf_business_ocr_mm":
                assert_pdf_locator(row)
            else:
                raise AssertionError(f"unknown silver track: {row['track']}")

    assert split_group_ids(rows_by_split["dev"]).isdisjoint(split_group_ids(rows_by_split["holdout"]))
    assert split_group_ids(rows_by_split["dev"]).isdisjoint(split_group_ids(read_jsonl_if_exists(SILVER_DIR / "answer_citation_silver_sealed_v1.jsonl")))
    assert template_locator_families(rows_by_split["dev"]).isdisjoint(
        template_locator_families(rows_by_split["holdout"])
    )


def test_answer_citation_silver_readiness_records_exact_current_blockers() -> None:
    readiness = read_json(READINESS)

    assert readiness["purpose"] == "anti_overfit_generalization_and_source_bound_contract"
    assert readiness["not_gold"] is True
    assert readiness["not_official_metric_denominator"] is True
    assert readiness["not_promotion_evidence"] is True
    assert readiness["not_performance_rerun"] is True
    assert readiness["no_tuning_performed"] is True
    assert readiness["gold_csvs_mutated"] is False
    assert readiness["official_denominator_registry_mutated"] is False
    assert readiness["human_labels_mutated"] is False
    assert readiness["production_namespace_or_vector_path_mutated"] is False
    assert readiness["first_run_baseline_overwritten"] is False
    assert readiness["xlsx_pdf_candidates_promoted"] is False
    assert readiness["candidate_result_rows_used_as_silver_generation_source"] is False

    assert readiness["official_denominator_query_ids"]["dev_holdout_tuning_silver_overlap_count"] == 0
    assert readiness["source_bound_nonproduction_index"]["target_index_path"] == (
        "ai/eval/indexes/rag-data-official-denominator-v1"
    )
    assert readiness["source_bound_nonproduction_index"]["production_index_path_used"] is False

    blockers = readiness["blockers_by_track"]
    assert blockers["text_namu_v2_1"]["status"] == "blocked"
    assert blockers["text_namu_v2_1"]["missing_source_bound_fields"] == [
        "document_version_id",
        "search_unit_id",
        "text_locator",
    ]
    assert blockers["xlsx_business_structured"]["status"] == "blocked"
    assert blockers["xlsx_business_structured"]["missing_source_bound_fields"] == [
        "cell",
        "row_label",
        "target_column",
        "normalized_value_for_audit_only",
    ]
    assert blockers["pdf_business_ocr_mm"]["status"] == "blocked"
    assert blockers["pdf_business_ocr_mm"]["missing_source_bound_fields"] == [
        "source_pdf_path",
        "document_version_id",
        "search_unit_id",
        "row_label",
        "target_column",
    ]
    overlap_scan = readiness["official_denominator_overlap_scan"]
    assert overlap_scan["source_bound_search_unit_manifest_rows"] == 29
    assert overlap_scan["official_denominator_overlap_true_count"] == 29
    assert overlap_scan["official_denominator_overlap_false_count"] == 0
    assert overlap_scan["eligible_dev_holdout_source_candidate_count"] == 0
    assert overlap_scan["excluded_official_query_id_count"] == 29


def test_answer_citation_silver_use_policy_matches_current_artifact_boundaries() -> None:
    first_run = read_json(FIRST_RUN)
    xlsx_rows = read_jsonl(XLSX_CANDIDATE)
    pdf_rows = read_jsonl(PDF_CANDIDATE)
    summary = read_json(AGENTIC_SUMMARY)
    attribution = read_json(AGENTIC_ATTRIBUTION)

    assert first_run["scored_count"] == 29
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }
    assert len(xlsx_rows) == 29
    assert len(pdf_rows) == 29
    assert all(row["promotion_evidence"] is False for row in xlsx_rows)
    assert all(row["promotion_evidence"] is False for row in pdf_rows)
    assert all(row["expected_answer_used_for_generation"] is False for row in xlsx_rows)
    assert all(row["supporting_evidence_used_for_generation"] is False for row in xlsx_rows)
    assert all(row["expected_answer_used_for_generation"] is False for row in pdf_rows)
    assert all(row["supporting_evidence_used_for_generation"] is False for row in pdf_rows)

    assert summary["measurement_classification"] == (
        "diagnostic_live_generation_fixture_all_index_not_official_denominator_representative"
    )
    assert summary["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["performance_interpretation"] == (
        "diagnostic_retrieval_agent_loop_not_final_answer_generation_quality"
    )
    assert summary["diagnostic_limitations"]["current_pass_is_promotion_evidence"] is False
    assert attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert attribution["structured_adapter_wiring_verdict"]["xlsx_candidate_adapter_wired_into_live_path"] is False
    assert attribution["structured_adapter_wiring_verdict"]["pdf_candidate_adapter_wired_into_live_path"] is False


def test_docs_record_answer_citation_silver_strategy_without_promotion_claims() -> None:
    readme = README.read_text(encoding="utf-8")
    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_progress = progress.split("## Short History", 1)[0]

    assert "docs/rag-ingestion-progress.md" in readme
    assert "docs/rag-ingestion-measurements.md" in readme
    assert "docs/rag-ingestion-triage.md" in readme
    assert "production promotion" in readme

    normalized = " ".join(current_progress.split())
    assert "answer_citation_silver_manifest_v1.json" in current_progress
    assert "answer_citation_silver_readiness_v1.json" in current_progress
    assert "anti-overfit" in normalized
    assert "silver is not gold" in normalized
    assert "not official denominator" in normalized
    assert "not promotion evidence" in normalized
    assert "expected values are audit-only" in normalized
    assert "official 29 query_ids are excluded from dev/holdout tuning silver" in normalized
    assert "TEXT=0, XLSX=0, PDF=0" in normalized

    current_normalized = " ".join(current_progress.split())
    assert "official-denominator source-bound index, build/load check, and canonical SearchUnit citation payload wiring are already available" in current_normalized
    assert "29/29 source-bound SearchUnits overlap the official denominator" in current_normalized
    assert "safe non-official source-bound source manifests are still missing" in current_normalized
    assert "silver generation stays closed until safe silver-source data coverage is settled" in current_normalized

    assert "silver promotion evidence" not in current_progress.lower()


def test_answer_citation_silver_source_material_is_not_official_denominator_overlap() -> None:
    readiness = read_json(READINESS)
    manifest = read_json(MANIFEST)
    source_bound_rows = read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    official_query_ids = official_denominator_query_ids()

    assert len(source_bound_rows) == 29
    assert {clean(row.get("query_id")) for row in source_bound_rows} == official_query_ids
    assert all(row["source_bound_official_denominator"] is True for row in source_bound_rows)
    assert all(row["promotion_evidence"] is False for row in source_bound_rows)
    assert all(row["candidate_artifact_generation_source"] is False for row in source_bound_rows)
    assert all(has_value(row.get("document_version_id")) for row in source_bound_rows)
    assert all(has_value(row.get("search_unit_id")) for row in source_bound_rows)
    assert all(has_value(row.get("embedding_text") or row.get("bm25_text") or row.get("display_text")) for row in source_bound_rows)

    assert readiness["official_denominator_overlap_scan"]["eligible_dev_holdout_source_candidate_count"] == 0
    assert readiness["per_track_counts"] == {"text_namu_v2_1": 0, "xlsx_business_structured": 0, "pdf_business_ocr_mm": 0}
    assert manifest["source_bound_material_audit"]["per_source_family_safe_candidate_counts"] == {
        "TEXT": 0,
        "XLSX": 0,
        "PDF": 0,
    }
    for split in ("dev", "holdout", "contract"):
        assert SILVER_JSONL_BY_SPLIT[split].exists() is False


def test_v3_3_1_status_event_records_silver_source_manifest_blocker_without_generation() -> None:
    run_id = "official_answer_citation_agentic_loop_run_v3_3_1_answer_citation_silver_source_manifest_readiness"
    event = next(
        item
        for item in reversed(read_jsonl(STATUS_JSONL))
        if item.get("event_type") == "answer_citation_silver_source_manifest_readiness_v3_3_1"
        and item.get("run_id") == run_id
    )

    assert event["run_class"] == "status_ledger_only_silver_source_manifest_readiness"
    assert event["safe_source_manifests_can_be_created"] is False
    assert event["silver_jsonl_files_created"] == {"contract": False, "dev": False, "holdout": False}
    assert event["source_data_blocker"]["official_denominator_overlap_true_count"] == 29
    assert event["source_data_blocker"]["eligible_dev_holdout_source_candidate_count"] == 0
    assert event["guardrails"]["silver_generation_run"] is False
    assert event["guardrails"]["generation_source_mutation"] is False
    assert event["guardrails"]["promotion_evidence"] is False
    assert event["guardrails"]["gold_mutation"] is False
    assert event["guardrails"]["expected_answer_mutation"] is False
    assert event["guardrails"]["supporting_evidence_mutation"] is False
    assert event["guardrails"]["official_denominator_query_id_set_mutation"] is False
    assert event["guardrails"]["official_retrieval_metrics_computed"] is False
    assert event["guardrails"]["production_mutation"] is False


def test_v3_5_0_capacity_summary_locks_schema_and_previous_strict_inventory() -> None:
    summary = read_json(V3_5_0_CAPACITY_SUMMARY)
    manifest_ready_rows = read_jsonl(V3_5_0_MANIFEST_READY)

    assert summary["run_id"] == V3_5_0_RUN_ID
    assert summary["artifact_kind"] == "strict_non_official_source_bound_capacity_summary"
    assert summary["schema_version"] == "v3_5_0_strict_non_official_source_bound_capacity_summary_v1"
    assert summary["previous_strict_inventory"] == {"TEXT": 0, "PDF": 3, "XLSX": 4, "total": 7}
    assert summary["new_manifest_ready_inventory"] == {
        "TEXT": 350,
        "PDF": 3,
        "XLSX": 4,
        "total": 357,
    }
    assert len(manifest_ready_rows) == summary["new_manifest_ready_inventory"]["total"]
    assert summary["pilot_threshold_rows"] == 100
    assert summary["target_rows"] == 1000
    assert summary["preferred_target_by_source_family"] == {"TEXT": 350, "PDF": 325, "XLSX": 325}
    assert summary["pilot_threshold_met"] is True
    assert summary["target_threshold_met"] is False
    assert summary["recommended_next_phase"] == "v3_5_1_pilot_silver_source_manifest_freeze"
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["official_denominator_rows_reused"] is False
    assert summary["official_29_query_ids_copied_or_relabelled"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert summary["source_inventory_differs_from_v3_4_4"] is True
    assert summary["source_inventory_change_reason"] == (
        "v3_5_0 deterministically reconstructs TEXT document/search-unit locator fields from existing "
        "rag_chunks source rows without creating questions, answers, labels, or silver rows."
    )


def test_v3_5_0_manifest_ready_candidates_are_source_bound_and_non_official() -> None:
    rows = read_jsonl(V3_5_0_MANIFEST_READY)
    official_query_ids = official_denominator_query_ids()
    official_search_unit_ids = {
        clean(row.get("search_unit_id")) for row in read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    }
    by_family: dict[str, int] = defaultdict(int)

    assert rows
    assert len({row["candidate_id"] for row in rows}) == len(rows)
    for row in rows:
        by_family[row["source_family"]] += 1
        assert row["classification"] == "strict_manifest_ready"
        assert row["official_denominator_overlap"] is False
        assert row["generation_source"] is False
        assert row["promotion_evidence"] is False
        assert row["not_gold"] is True
        assert row["not_official_denominator"] is True
        assert row["silver_expected_values_policy"] == "audit_only"
        assert row["candidate_artifacts_used_as_generation_source"] is False
        assert row["source_text_available"] is True
        assert has_value(row.get("source_hash") or row.get("excerpt_hash"))
        assert clean(row.get("provenance_query_id")) not in official_query_ids
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert "expected_answer" not in row
        assert "supporting_evidence" not in row
        assert "relevance_label" not in row
        assert "answerability_label" not in row

        locator = row["source_locator"]
        if row["source_family"] == "TEXT":
            assert_required(row, ("candidate_id", "document_version_id", "search_unit_id"))
            assert_required(
                locator,
                (
                    "source_corpus_path",
                    "doc_id",
                    "chunk_id",
                    "section_id",
                    "jsonl_line_number",
                    "char_start",
                    "char_end",
                ),
            )
            assert locator["source_corpus_path"] == "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl"
        elif row["source_family"] == "PDF":
            assert_required(row, ("candidate_id", "document_version_id", "search_unit_id", "source_pdf_path"))
            assert_required(locator, ("source_pdf_path", "page", "physical_page_index", "bbox", "region_type"))
            assert isinstance(locator["bbox"], list)
            assert len(locator["bbox"]) == 4
            assert row["extract_provenance"]["source_manifest_kind"] == "pdf_answer_citation_diagnostic_review_input"
        elif row["source_family"] == "XLSX":
            assert_required(row, ("candidate_id", "document_version_id", "search_unit_id", "source_workbook"))
            assert_required(locator, ("workbook", "sheet", "range"))
            assert has_value(locator.get("matched_cells") or locator.get("cell") or locator.get("range"))
            assert row["extract_provenance"]["source_manifest_kind"] == (
                "xlsx_strict_silver_retrieval_evidence_manifest"
            )
        else:
            raise AssertionError(row["source_family"])

    assert by_family == {"TEXT": 350, "PDF": 3, "XLSX": 4}


def test_v3_5_0_keeps_silver_rows_closed_and_official_ids_excluded() -> None:
    summary = read_json(V3_5_0_CAPACITY_SUMMARY)
    manifest_ready_rows = read_jsonl(V3_5_0_MANIFEST_READY)
    official_query_ids = official_denominator_query_ids()

    for split in ("contract", "dev", "holdout"):
        assert SILVER_JSONL_BY_SPLIT[split].exists() is False

    assert summary["silver_jsonl_rows_created"] is False
    assert summary["silver_generation_allowed"] is False
    assert summary["official_denominator_rows_reused"] is False
    assert summary["official_29_query_ids_copied_or_relabelled"] is False
    assert {
        clean(row.get("provenance_query_id"))
        for row in manifest_ready_rows
        if clean(row.get("provenance_query_id"))
    }.isdisjoint(official_query_ids)
    assert {
        clean(row.get("query_id"))
        for row in manifest_ready_rows
        if clean(row.get("query_id"))
    }.isdisjoint(official_query_ids)


def test_v3_5_0_acquisition_plan_is_track_separated_and_non_generating() -> None:
    summary = read_json(V3_5_0_CAPACITY_SUMMARY)
    plan = read_json(V3_5_0_ACQUISITION_PLAN)
    blocked_or_convertible = read_jsonl(V3_5_0_BLOCKED_OR_CONVERTIBLE)

    assert plan["run_id"] == V3_5_0_RUN_ID
    assert plan["artifact_kind"] == "strict_non_official_source_bound_acquisition_plan"
    assert set(plan["recommendations_by_source_family"]) == {"TEXT", "PDF", "XLSX"}
    for family, section in plan["recommendations_by_source_family"].items():
        assert family in {"TEXT", "PDF", "XLSX"}
        assert "existing_material_convertible" in section
        assert "existing_material_blocked" in section
        assert "new_source_collection_needed" in section

    assert plan["minimum_viable_pilot_plan"]["target_manifest_ready_rows"] >= 100
    assert plan["target_expansion_plan"]["target_rows"] == 1000
    assert plan["target_expansion_plan"]["preferred_mix"] == {"TEXT": 350, "PDF": 325, "XLSX": 325}
    for key in (
        "no_official_denominator_overlap",
        "no_expected_answer_or_supporting_evidence_generation",
        "no_label_mutation",
        "no_promotion_evidence",
        "no_readme_representative_performance_claim",
        "no_candidate_artifact_as_generation_source",
    ):
        assert plan["risk_notes"][key] is True

    assert summary["convertible_inventory"]["TEXT"]["candidate_count"] >= 135000
    assert summary["convertible_inventory"]["XLSX"]["candidate_count"] == 761
    assert summary["convertible_inventory"]["PDF"]["candidate_count"] == 148
    assert any(row["classification"] == "convertible_with_existing_source" for row in blocked_or_convertible)
    assert any(row["classification"].startswith("blocked_") for row in blocked_or_convertible)


def test_v3_5_1_pilot_source_manifest_freeze_is_source_only_and_text_heavy() -> None:
    summary = read_json(V3_5_1_FREEZE_SUMMARY)
    rows = read_jsonl(V3_5_1_PILOT_SOURCE_MANIFEST)
    audit_rows = read_jsonl(V3_5_1_FREEZE_AUDIT)
    rationale = read_json(V3_5_1_SELECTION_RATIONALE)
    official_query_ids = official_denominator_query_ids()
    official_search_unit_ids = {
        clean(row.get("search_unit_id")) for row in read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    }

    assert summary["run_id"] == V3_5_1_RUN_ID
    assert summary["artifact_kind"] == "pilot_source_manifest_freeze"
    assert summary["source_run_id"] == V3_5_0_RUN_ID
    assert summary["previous_manifest_ready_inventory"] == {"TEXT": 350, "PDF": 3, "XLSX": 4, "total": 357}
    assert summary["frozen_manifest_row_count"] == len(rows) == 357
    assert summary["frozen_counts_by_source_family"] == {"TEXT": 350, "PDF": 3, "XLSX": 4, "total": 357}
    assert summary["excluded_during_freeze_counts_by_reason"] == {}
    assert summary["pilot_threshold_met"] is True
    assert summary["balanced_pilot_threshold_met"] is False
    assert summary["target_threshold_met"] is False
    assert summary["source_family_imbalance_warning"] is True
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["questions_created"] is False
    assert summary["expected_answers_created"] is False
    assert summary["supporting_evidence_created"] is False
    assert summary["relevance_labels_created"] is False
    assert summary["answerability_labels_created"] is False
    assert summary["qrels_created"] is False
    assert summary["official_denominator_rows_reused"] is False
    assert summary["official_29_query_ids_copied_or_relabelled"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert summary["recommended_next_phase"] == "v3_5_2_xlsx_source_value_manifest_repair_and_acquisition"
    assert rationale["silver_generation_allowed"] is False
    assert audit_rows

    assert len({row["candidate_id"] for row in rows}) == len(rows)
    for row in rows:
        assert_source_only_manifest_row(row)
        assert row["run_id"] == V3_5_1_RUN_ID
        assert row["classification"] == "pilot_source_manifest_frozen"
        assert row["source_family"] in {"TEXT", "PDF", "XLSX"}
        assert row["official_denominator_overlap"] is False
        assert row["not_official_denominator"] is True
        assert row["not_gold"] is True
        assert has_value(row.get("document_version_id"))
        assert has_value(row.get("search_unit_id"))
        assert has_value(row.get("source_bound_locator"))
        assert has_value(row.get("locator_fingerprint"))
        assert has_value(row.get("source_content_sha256"))
        assert has_value(row.get("canonical_citation_payload"))
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert clean(row.get("query_id")) not in official_query_ids
        assert clean(row.get("provenance_query_id")) not in official_query_ids
        assert row.get("source_text_available") is True or row.get("source_value_available") is True


def test_v3_5_2_xlsx_repair_uses_actual_workbook_values_not_query_or_expected_answer() -> None:
    summary = read_json(V3_5_2_POST_XLSX_CAPACITY_SUMMARY)
    rows = read_jsonl(V3_5_2_XLSX_MANIFEST_READY)
    blocked_or_convertible = read_jsonl(V3_5_2_XLSX_BLOCKED_OR_CONVERTIBLE)
    source_collection = read_json(V3_5_2_XLSX_SOURCE_COLLECTION_MANIFEST)
    official_search_unit_ids = {
        clean(row.get("search_unit_id")) for row in read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    }

    assert summary["run_id"] == V3_5_2_RUN_ID
    assert summary["artifact_kind"] == "xlsx_source_value_manifest_repair_and_acquisition"
    assert summary["source_run_ids"] == [V3_5_0_RUN_ID, V3_5_1_RUN_ID]
    assert summary["starting_xlsx_manifest_ready_count"] == 4
    assert summary["target_xlsx_rows"] == 325
    assert summary["xlsx_gap_before"] == 321
    assert summary["manifest_ready_count"] == len(rows) == 321
    assert summary["xlsx_repaired_count"] == 321
    assert summary["repaired_from_locator_complete_candidates_count"] >= 321
    assert summary["locator_complete_candidate_rows"] == 700
    assert summary["repaired_from_source_collection_workbooks_count"] == 0
    assert summary["newly_collected_workbook_count"] == 0
    assert summary["newly_collected_manifest_ready_count"] == 0
    assert summary["xlsx_newly_collected_source_count"] == 0
    assert summary["xlsx_final_count"] == 325
    assert summary["xlsx_manifest_ready_count_after"] == 325
    assert summary["xlsx_gap_after"] == 0
    assert summary["target_xlsx_met"] is True
    assert summary["remaining_preferred_gap_by_source_family"] == {"TEXT": 0, "PDF": 322, "XLSX": 0}
    assert summary["combined_source_family_counts_after_phase"] == {"TEXT": 350, "PDF": 3, "XLSX": 325, "total": 678}
    assert summary["target_threshold_met"] is False
    assert summary["acquisition_performed"] is False
    assert summary["acquisition_reason"] == "existing_xlsx_candidate_workbooks_sufficient_for_preferred_gap"
    assert set(summary["blocked_counts_by_reason"]) == {
        "blocked_candidate_artifact_only",
        "blocked_source_unavailable",
        "blocked_missing_locator",
        "blocked_missing_source_value",
        "blocked_formula_without_cached_value",
        "blocked_hidden_policy",
        "blocked_duplicate_or_near_duplicate",
        "blocked_official_denominator_overlap",
        "blocked_license_or_provenance_unclear",
        "blocked_other",
    }
    assert summary["blocked_counts_by_reason"]["blocked_source_unavailable"] == 2
    assert summary["blocked_counts_by_reason"]["blocked_hidden_policy"] >= 0
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert summary["no_candidate_artifact_as_generation_source"] is True
    assert summary["query_or_expected_answer_used_as_generation_source"] is False
    assert source_collection["acquisition_performed"] is False
    assert source_collection["newly_collected_workbook_count"] == 0
    assert source_collection["candidate_artifacts_used_as_generation_source"] is False
    assert blocked_or_convertible
    assert len(blocked_or_convertible) == 702

    for row in rows:
        assert_source_only_manifest_row(row)
        assert row["run_id"] == V3_5_2_RUN_ID
        assert row["classification"] == "xlsx_source_value_manifest_ready"
        assert row["source_family"] == "XLSX"
        assert row["official_denominator_overlap"] is False
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert has_value(row.get("source_workbook"))
        assert has_value(row.get("workbook_path"))
        assert has_value(row.get("workbook_id") or row.get("document_version_id"))
        assert has_value(row.get("workbook_sha256"))
        assert has_value(row.get("sheet_name"))
        assert "row_label" in row
        assert "column_label" in row
        assert has_value(row.get("source_value"))
        assert has_value(row.get("source_value_type"))
        assert "display_value" in row
        assert "normalized_value" in row
        assert "number_format" in row
        assert "formula_present" in row
        assert "formula_cached_value_available" in row
        assert "hidden_policy" in row
        assert "hidden_status_detected" in row
        assert "sheet_hidden" in row
        assert "hidden_rows" in row
        assert "hidden_columns" in row
        assert has_value(row.get("source_value_hash"))
        locator = row["source_bound_locator"]
        assert_required(locator, ("workbook", "sheet", "range"))
        assert "cell" in locator
        assert has_value(row.get("locator_fingerprint"))
        assert row["source_value_available"] is True
        assert row["query_or_expected_answer_used_as_generation_source"] is False
        assert "query" not in row
        assert "expected_answer_text" not in row
        assert row["extract_provenance"]["candidate_artifacts_used_as_generation_source"] is False
        assert row["extract_provenance"]["query_or_expected_answer_used_as_generation_source"] is False


def test_v3_5_3_pdf_repair_records_page_bbox_text_hash_and_provenance() -> None:
    summary = read_json(V3_5_3_POST_PDF_CAPACITY_SUMMARY)
    rows = read_jsonl(V3_5_3_PDF_MANIFEST_READY)
    blocked_or_convertible = read_jsonl(V3_5_3_PDF_BLOCKED_OR_CONVERTIBLE)
    source_collection = read_json(V3_5_3_PDF_SOURCE_COLLECTION_MANIFEST)
    balanced = read_json(V3_5_3_BALANCED_CAPACITY_SUMMARY)
    official_search_unit_ids = {
        clean(row.get("search_unit_id")) for row in read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    }

    assert summary["run_id"] == V3_5_3_RUN_ID
    assert summary["artifact_kind"] == "pdf_page_bbox_source_text_manifest_repair_and_acquisition"
    assert summary["source_run_ids"] == [V3_5_0_RUN_ID, V3_5_1_RUN_ID, V3_5_2_RUN_ID]
    assert summary["manifest_ready_count"] == len(rows) == 322
    assert summary["pdf_repaired_count"] == 322
    assert summary["starting_pdf_manifest_ready_count"] == 3
    assert summary["target_pdf_rows"] == 325
    assert summary["pdf_gap_before"] == 322
    assert summary["repaired_from_existing_source_pdfs_count"] == 322
    assert summary["newly_collected_pdf_count"] == 0
    assert summary["newly_collected_manifest_ready_count"] == 0
    assert summary["pdf_newly_collected_source_count"] == 0
    assert summary["pdf_final_count"] == 325
    assert summary["pdf_manifest_ready_count_after"] == 325
    assert summary["pdf_gap_after"] == 0
    assert summary["target_pdf_met"] is True
    assert summary["remaining_preferred_gap_by_source_family"] == {"TEXT": 0, "PDF": 0, "XLSX": 0}
    assert summary["combined_source_family_counts_after_phase"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert summary["balanced_pilot_threshold_met"] is True
    assert summary["target_threshold_met"] is True
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert summary["acquisition_performed"] is False
    assert summary["acquisition_reason"] == "existing_148_pdf_source_collection_sufficient_for_preferred_gap"
    assert summary["extraction_methods_used"] == {"pymupdf_native_text_block_v1": 322}
    assert summary["per_document_cap"] == 4
    assert set(summary["blocked_counts_by_reason"]) == {
        "blocked_missing_locator",
        "blocked_missing_source_text",
        "blocked_unstable_extraction",
        "blocked_candidate_artifact_only",
        "blocked_duplicate_or_near_duplicate",
        "blocked_official_denominator_overlap",
        "blocked_source_unavailable",
        "blocked_license_or_provenance_unclear",
        "blocked_other",
    }
    assert summary["blocked_counts_by_reason"]["blocked_missing_locator"] == 8194
    assert summary["blocked_counts_by_reason"]["blocked_candidate_artifact_only"] == 7
    assert source_collection["acquisition_performed"] is False
    assert source_collection["newly_collected_pdf_count"] == 0
    assert source_collection["newly_collected_manifest_ready_count"] == 0
    assert blocked_or_convertible
    assert balanced["artifact_kind"] == "post_v3_5_3_balanced_source_capacity_summary"
    assert balanced["final_manifest_ready_counts_by_source_family"] == {
        "TEXT": 350,
        "PDF": 325,
        "XLSX": 325,
        "total": 1000,
    }
    assert balanced["preferred_target_by_source_family"] == {
        "TEXT": 350,
        "PDF": 325,
        "XLSX": 325,
        "total": 1000,
    }
    assert balanced["gaps_by_source_family"] == {"TEXT": 0, "PDF": 0, "XLSX": 0, "total": 0}
    assert balanced["pilot_threshold_rows"] == 100
    assert balanced["pilot_threshold_met"] is True
    assert balanced["balanced_pilot_possible"] is True
    assert balanced["target_rows"] == 1000
    assert balanced["target_threshold_met"] is True
    assert balanced["preferred_mix_met"] is True
    assert balanced["source_family_imbalance_warning"] is False
    assert balanced["silver_generation_allowed"] is False
    assert balanced["silver_jsonl_rows_created"] is False
    assert balanced["recommended_next_phase"] == "v3_5_4_balanced_silver_source_manifest_freeze"

    for row in rows:
        assert_source_only_manifest_row(row)
        assert row["run_id"] == V3_5_3_RUN_ID
        assert row["classification"] == "pdf_source_text_manifest_ready"
        assert row["source_family"] == "PDF"
        assert row["official_denominator_overlap"] is False
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert_required(
            row,
            (
                "source_pdf_path",
                "stable_pdf_identity",
                "document_version_id",
                "search_unit_id",
                "page",
                "page_index",
                "physical_page_index",
                "bbox",
                "region_type",
                "locator_fingerprint",
                "source_text",
                "source_text_hash",
                "source_pdf_sha256",
                "extraction_method",
                "extraction_provenance",
            ),
        )
        assert row["extraction_method"] == "pymupdf_native_text_block_v1"
        locator = row["source_bound_locator"]
        assert_required(locator, ("source_pdf_path", "page", "page_index", "physical_page_index", "bbox", "region_type"))
        assert isinstance(locator["bbox"], list)
        assert len(locator["bbox"]) == 4
        provenance = row["extract_provenance"]
        assert provenance["source_manifest_kind"] == "source_collection_20260510_manifest"
        assert provenance["candidate_artifacts_used_as_generation_source"] is False
        assert provenance["extraction_method"] == "pymupdf_native_text_block_v1"
        assert has_value(provenance.get("source_page")) or has_value(provenance.get("download_url"))


def test_v3_5_4_balanced_source_manifest_freeze_locks_counts_and_source_only_policy() -> None:
    summary = read_json(V3_5_4_FREEZE_SUMMARY)
    rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    audit_rows = read_jsonl(V3_5_4_FREEZE_AUDIT)
    policy = read_json(V3_5_4_NEXT_PHASE_POLICY_BOUNDARY)

    assert summary["run_id"] == V3_5_4_RUN_ID
    assert summary["artifact_kind"] == "balanced_silver_source_manifest_freeze_source_only"
    assert summary["source_run_ids"] == [V3_5_1_RUN_ID, V3_5_2_RUN_ID, V3_5_3_RUN_ID]
    assert summary["input_counts_by_component"]["v3_5_1_frozen_text_pdf_xlsx_manifest"][
        "counts_by_source_family"
    ] == {"TEXT": 350, "PDF": 3, "XLSX": 4, "total": 357}
    assert summary["input_counts_by_component"]["v3_5_2_xlsx_overlay"]["counts_by_source_family"] == {
        "TEXT": 0,
        "PDF": 0,
        "XLSX": 321,
        "total": 321,
    }
    assert summary["input_counts_by_component"]["v3_5_3_pdf_overlay"]["counts_by_source_family"] == {
        "TEXT": 0,
        "PDF": 322,
        "XLSX": 0,
        "total": 322,
    }
    assert summary["frozen_manifest_row_count"] == len(rows) == 1000
    assert summary["frozen_counts_by_source_family"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert summary["preferred_target_by_source_family"] == {
        "TEXT": 350,
        "PDF": 325,
        "XLSX": 325,
        "total": 1000,
    }
    assert summary["target_rows"] == 1000
    assert summary["target_threshold_met"] is True
    assert summary["preferred_mix_met"] is True
    assert summary["balanced_pilot_possible"] is True
    assert summary["excluded_during_freeze_counts_by_reason"] == {}
    assert summary["backfill_performed"] is False
    assert summary["backfill_source_artifacts"] == []
    assert summary["recommended_next_phase"] == "v3_5_5_balanced_source_manifest_quality_audit"
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    assert policy["v3_5_4_is_silver_generation"] is False
    assert policy["codex_must_not_decide_gold_expected_evidence_or_label_policy"] is True
    assert "question_generation_policy" in policy["user_owned_decisions_needed_before_silver_generation"]

    for split in ("contract", "dev", "holdout"):
        assert SILVER_JSONL_BY_SPLIT[split].exists() is False

    assert len({row["candidate_id"] for row in rows}) == len(rows)
    assert len({row["source_identity"] for row in rows}) == len(rows)
    assert len({row["locator_fingerprint"] for row in rows}) == len(rows)
    assert len(audit_rows) == len(rows)

    for row in rows:
        assert_source_only_manifest_row(row)
        assert_no_generation_payload_keys(row)
        assert row["run_id"] == V3_5_4_RUN_ID
        assert row["classification"] == "balanced_source_manifest_frozen"
        assert row["official_denominator_overlap"] is False
        assert row["not_official_denominator"] is True
        assert row["not_gold"] is True


def test_v3_5_4_balanced_manifest_rows_are_non_official_with_family_locator_hash_contracts() -> None:
    rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    official_rows = read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    official_query_ids = {clean(row.get("query_id")) for row in official_rows}
    official_search_unit_ids = {clean(row.get("search_unit_id")) for row in official_rows}
    official_locator_fingerprints = {
        source_locator_fingerprint(row.get("locator")) for row in official_rows if has_value(row.get("locator"))
    }

    assert rows
    for row in rows:
        assert row["official_denominator_overlap"] is False
        assert clean(row.get("query_id")) not in official_query_ids
        assert clean(row.get("provenance_query_id")) not in official_query_ids
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert clean(row.get("locator_fingerprint")) not in official_locator_fingerprints

        family = row["source_family"]
        locator = row["source_bound_locator"]
        assert_required(row, ("candidate_id", "document_version_id", "search_unit_id", "locator_fingerprint"))
        assert has_value(row.get("source_content_sha256") or row.get("source_hash"))
        if family == "TEXT":
            assert_required(locator, ("source_corpus_path", "chunk_id", "doc_id", "jsonl_line_number"))
            assert "char_start" in locator
            assert "char_end" in locator
            assert has_value(row.get("source_excerpt") or row.get("source_text_preview"))
            assert has_value(row.get("source_excerpt_hash") or row.get("excerpt_hash"))
        elif family == "PDF":
            assert_required(row, ("source_pdf_path", "page", "page_index", "bbox", "extraction_method"))
            assert has_value(row.get("source_pdf_sha256") or row.get("source_hash"))
            assert has_value(row.get("extraction_provenance") or row.get("extract_provenance"))
            assert has_value(row.get("source_text"))
            assert has_value(row.get("source_text_hash"))
            assert row["source_content_sha256"] == row["source_text_hash"]
            assert isinstance(row["bbox"], list)
            assert len(row["bbox"]) == 4
            assert all(isinstance(value, (int, float)) for value in row["bbox"])
        elif family == "XLSX":
            assert has_value(row.get("workbook_path") or row.get("source_workbook") or row.get("workbook_id"))
            assert has_value(row.get("workbook_sha256") or row.get("source_hash"))
            assert has_value(row.get("sheet_name"))
            assert has_value(row.get("cell") or row.get("range") or row.get("row_label") or row.get("column_label"))
            assert has_value(row.get("source_value"))
            assert has_value(row.get("source_value_hash"))
            assert row["source_content_sha256"] == row["source_value_hash"]
            assert "hidden_policy" in row
            assert "formula_present" in row
            assert "formula_cached_value_available" in row
        else:
            raise AssertionError(f"unexpected family: {family}")


def test_v3_5_4_sample_packet_is_manifest_derived_source_only_and_balanced() -> None:
    summary = read_json(V3_5_4_FREEZE_SUMMARY)
    rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    samples = read_jsonl(V3_5_4_AUDIT_SAMPLE_PACKET)
    manifest_candidate_ids = {row["candidate_id"] for row in rows}

    assert summary["audit_sample_packet_counts_by_source_family"] == {
        "TEXT": 25,
        "PDF": 25,
        "XLSX": 25,
        "total": 75,
    }
    assert len(samples) == 75
    assert {sample["candidate_id"] for sample in samples} <= manifest_candidate_ids
    assert count_by_source_family(samples) == {"TEXT": 25, "PDF": 25, "XLSX": 25, "total": 75}
    for sample in samples:
        assert_source_only_manifest_row(sample)
        assert_no_generation_payload_keys(sample)
        assert has_value(sample.get("source_locator"))
        assert has_value(sample.get("source_excerpt_or_value"))
        assert has_value(sample.get("source_hash"))
        assert has_value(sample.get("locator_fingerprint"))


def test_v3_5_5_quality_audit_summary_artifacts_and_v3_5_4_inputs_are_locked() -> None:
    summary = read_json(V3_5_5_QUALITY_SUMMARY)
    validation_rows = read_jsonl(V3_5_5_MANIFEST_VALIDATION)
    v3_5_4_rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    policy = read_json(V3_5_5_NEXT_PHASE_POLICY_BOUNDARY)

    assert summary["run_id"] == V3_5_5_RUN_ID
    assert summary["artifact_kind"] == "balanced_source_manifest_quality_audit_source_only"
    assert summary["source_run_id"] == V3_5_4_RUN_ID
    assert summary["input_manifest_path"].endswith(f"{V3_5_4_RUN_ID}_balanced_source_manifest.jsonl")
    assert summary["input_manifest_sha256_before"] == sha256_file(V3_5_4_BALANCED_SOURCE_MANIFEST)
    assert summary["input_manifest_sha256_after"] == summary["input_manifest_sha256_before"]
    assert summary["input_manifest_row_count"] == len(v3_5_4_rows) == len(validation_rows) == 1000
    assert summary["input_counts_by_source_family"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert summary["full_manifest_validation_completed"] is True
    assert summary["audit_sample_review_completed"] is True
    assert summary["source_only_boundary_preserved"] is True
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["questions_created"] is False
    assert summary["expected_answers_created"] is False
    assert summary["supporting_evidence_created"] is False
    assert summary["relevance_labels_created"] is False
    assert summary["answerability_labels_created"] is False
    assert summary["qrels_created"] is False
    assert summary["candidate_artifact_source_leak_detected_count"] >= 0
    assert summary["official_denominator_overlap_detected_count"] >= 0
    assert summary["normalized_source_hash_repetition_group_count"] == 17
    assert summary["normalized_source_hash_repetition_row_count"] == 57
    assert summary["recommended_next_phase"] in {
        "v3_6_0_silver_generation_policy_packet",
        "v3_5_6_source_manifest_quality_repair",
    }
    assert policy["v3_5_5_is_source_quality_audit_only"] is True
    assert policy["v3_5_5_authorizes_silver_generation"] is False
    assert "question_generation_policy" in policy["user_owned_decisions_needed_before_silver_generation"]

    for path_key in (
        "quality_summary_json",
        "manifest_validation_jsonl",
        "audit_sample_review_packet_jsonl",
        "duplicate_hash_audit_jsonl",
        "recommended_repair_queue_jsonl",
        "next_phase_policy_boundary_json",
    ):
        assert path_key in summary["artifact_paths"]

    for row in validation_rows:
        assert row["run_id"] == V3_5_5_RUN_ID
        assert row["source_run_id"] == V3_5_4_RUN_ID
        assert row["source_quality_status"] in {
            "pass_source_quality",
            "review_duplicate_or_near_duplicate",
            "review_short_source_text_or_value",
            "review_pdf_extraction_order",
            "review_pdf_header_footer_or_boilerplate",
            "review_pdf_numeric_or_table_context",
            "review_xlsx_hidden_policy_boundary",
            "review_xlsx_formula_or_cached_value",
            "review_xlsx_value_context",
            "repair_required_missing_document_identity",
            "repair_required_locator_unresolvable",
            "repair_required_source_text_or_value_missing",
            "repair_required_source_hash_missing",
            "repair_required_official_denominator_overlap",
            "repair_required_candidate_artifact_source_leak",
            "repair_required_provenance_or_license_unclear",
            "blocked_other",
        }
        assert row["source_only_boundary_preserved"] is True
        assert_no_generation_payload_keys(row)


def test_v3_5_5_duplicate_hash_audit_sample_packet_and_repair_queue_are_source_only() -> None:
    summary = read_json(V3_5_5_QUALITY_SUMMARY)
    rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    samples = read_jsonl(V3_5_5_AUDIT_SAMPLE_REVIEW_PACKET)
    duplicate_rows = read_jsonl(V3_5_5_DUPLICATE_HASH_AUDIT)
    repair_rows = read_jsonl(V3_5_5_RECOMMENDED_REPAIR_QUEUE)
    manifest_candidate_ids = {row["candidate_id"] for row in rows}
    source_hash_counts: dict[str, int] = {}
    for row in rows:
        source_hash = (
            clean(row.get("source_text_hash"))
            or clean(row.get("source_value_hash"))
            or clean(row.get("source_hash"))
            or clean(row.get("excerpt_hash"))
            or clean(row.get("source_content_sha256"))
        )
        source_hash_counts[source_hash] = source_hash_counts.get(source_hash, 0) + 1
    repeated_hashes = {source_hash: count for source_hash, count in source_hash_counts.items() if count > 1}

    assert len(duplicate_rows) == len(repeated_hashes) == 17
    assert sum(row["group_size"] for row in duplicate_rows) == 57
    assert summary["normalized_source_hash_repetition_group_count"] == len(duplicate_rows)
    assert summary["recommended_repair_queue_count"] == len(repair_rows)
    for duplicate in duplicate_rows:
        assert duplicate["source_quality_status"] == "review_duplicate_or_near_duplicate"
        assert duplicate["duplicate_hash_retained_reason"] == "distinct_source_identity_or_locator"
        assert duplicate["silver_generation_allowed"] is False
        assert len(set(duplicate["source_identities"])) == duplicate["group_size"]
        assert len(set(duplicate["locator_fingerprints"])) == duplicate["group_size"]
        assert_no_generation_payload_keys(duplicate)

    assert len(samples) >= 75
    assert {sample["candidate_id"] for sample in samples} <= manifest_candidate_ids
    sample_counts = count_by_source_family(samples)
    assert sample_counts["TEXT"] >= 25
    assert sample_counts["PDF"] >= 25
    assert sample_counts["XLSX"] >= 25
    assert sample_counts == summary["audit_sample_counts_by_source_family"]
    assert any(sample["sample_reason"] == "normalized_source_hash_repetition" for sample in samples)

    for sample in samples:
        assert_source_only_manifest_row(sample)
        assert_no_generation_payload_keys(sample)
        assert has_value(sample.get("source_locator"))
        assert has_value(sample.get("source_excerpt_or_value"))
        assert has_value(sample.get("source_hash"))
        if sample["source_family"] == "PDF":
            assert_required(sample, ("source_pdf_path", "page", "page_index", "extraction_method", "source_text_hash"))
        elif sample["source_family"] == "XLSX":
            assert_required(sample, ("source_workbook", "sheet_name", "source_value_hash"))
            assert has_value(sample.get("cell") or sample.get("range"))
        elif sample["source_family"] == "TEXT":
            assert_required(sample, ("source_corpus_path", "chunk_id", "doc_id", "source_excerpt_hash"))

    for repair in repair_rows:
        assert_required(repair, ("candidate_id", "source_family", "source_quality_status", "recommended_action"))
        assert repair["source_quality_status"].startswith("repair_required_")
        assert repair["silver_generation_allowed"] is False
        assert_no_generation_payload_keys(repair)


def test_v3_5_source_material_phases_create_no_silver_rows_or_label_payloads() -> None:
    summaries = [
        read_json(V3_5_1_FREEZE_SUMMARY),
        read_json(V3_5_2_POST_XLSX_CAPACITY_SUMMARY),
        read_json(V3_5_3_POST_PDF_CAPACITY_SUMMARY),
        read_json(V3_5_4_FREEZE_SUMMARY),
        read_json(V3_5_5_QUALITY_SUMMARY),
    ]
    manifest_rows = (
        read_jsonl(V3_5_1_PILOT_SOURCE_MANIFEST)
        + read_jsonl(V3_5_2_XLSX_MANIFEST_READY)
        + read_jsonl(V3_5_3_PDF_MANIFEST_READY)
        + read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    )
    official_query_ids = official_denominator_query_ids()

    for split in ("contract", "dev", "holdout"):
        assert SILVER_JSONL_BY_SPLIT[split].exists() is False

    for summary in summaries:
        assert summary["silver_generation_allowed"] is False
        assert summary["silver_jsonl_rows_created"] is False
        assert summary["questions_created"] is False
        assert summary["expected_answers_created"] is False
        assert summary["supporting_evidence_created"] is False
        assert summary["relevance_labels_created"] is False
        assert summary["answerability_labels_created"] is False
        assert summary["qrels_created"] is False
        assert summary["official_denominator_rows_reused"] is False
        assert summary["official_29_query_ids_copied_or_relabelled"] is False
        assert summary["candidate_artifacts_used_as_generation_source"] is False

    assert manifest_rows
    for row in manifest_rows:
        assert_source_only_manifest_row(row)
        assert row["official_denominator_overlap"] is False
        assert clean(row.get("query_id")) not in official_query_ids
        assert clean(row.get("provenance_query_id")) not in official_query_ids


def test_v3_6_0_low_touch_noisy_policy_application_records_user_decision_without_rows() -> None:
    summary = read_json(V3_6_0_POLICY_APPROVAL_SUMMARY)
    contract = read_json(V3_6_0_GENERATION_CONTRACT)
    matrix_rows = read_jsonl(V3_6_0_USER_DECISION_MATRIX)
    guardrail = read_json(V3_6_0_GUARDRAIL_SUMMARY)

    assert summary["run_id"] == V3_6_0_RUN_ID
    assert summary["artifact_kind"] == "low_touch_noisy_silver_policy_application"
    assert summary["user_policy_decision_applied"] is True
    assert summary["low_touch_human_review_required"] is False
    assert summary["source_manifest_counts"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert summary["source_quality_counts"] == {
        "pass_source_quality_count": 666,
        "review_only_count": 334,
        "critical_repair_required_count": 0,
    }
    assert summary["allow_generated_question_draft"] is True
    assert summary["allow_expected_answer_draft"] is True
    assert summary["allow_supporting_evidence_locator_draft"] is True
    assert summary["allow_weak_relevance_status_draft"] is True
    assert summary["allow_weak_answerability_status_draft"] is True
    assert summary["weak_silver_candidate_count"] == 0
    assert summary["weak_silver_candidates_created"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["promotion_evidence"] is False
    assert summary["readme_representative_product_performance_claim"] is False
    assert summary["recommended_next_phase"] == "v3_6_1_balanced_weak_noisy_silver_candidate_generation"

    assert contract["contains_generated_rows"] is False
    assert contract["contract_scope"] == "v3_6_1_row_schema_only"
    assert "generated_question_draft" in contract["row_schema"]["draft_only_fields"]
    assert "expected_answer_draft" in contract["row_schema"]["draft_only_fields"]
    assert "supporting_evidence_locator_draft" in contract["row_schema"]["draft_only_fields"]
    assert len(matrix_rows) >= 8
    assert {row["decision_key"] for row in matrix_rows} >= {
        "manual_review_all_1000_rows",
        "generated_question_draft_allowed",
        "expected_answer_draft_allowed",
        "supporting_evidence_locator_draft_allowed",
        "review_only_source_rows_allowed",
        "official_qrels_created",
        "promotion_evidence",
    }
    assert guardrail["policy_only_no_generated_rows"] is True
    assert guardrail["guardrails"]["weak_noisy_silver_candidate_rows_created"] is False
    assert_no_generation_payload_keys(summary)
    assert_no_generation_payload_keys(guardrail)


def test_v3_6_1_weak_noisy_candidate_rows_are_source_bound_non_gold_and_mixed() -> None:
    summary = read_json(V3_6_1_GENERATION_SUMMARY)
    rows = read_jsonl(V3_6_1_WEAK_SILVER_CANDIDATES)
    blocked_rows = read_jsonl(V3_6_1_BLOCKED_ROWS)
    distribution = read_json(V3_6_1_QUALITY_DISTRIBUTION)
    source_manifest_rows = read_jsonl(V3_5_4_BALANCED_SOURCE_MANIFEST)
    official_rows = read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)
    official_search_unit_ids = {clean(row.get("search_unit_id")) for row in official_rows}
    official_locator_fingerprints = {
        source_locator_fingerprint(row.get("locator")) for row in official_rows if has_value(row.get("locator"))
    }
    source_candidate_ids = {row["candidate_id"] for row in source_manifest_rows}

    assert summary["run_id"] == V3_6_1_RUN_ID
    assert summary["artifact_kind"] == "balanced_weak_noisy_silver_candidate_generation"
    assert summary["source_policy_run_id"] == V3_6_0_RUN_ID
    assert summary["source_manifest_run_id"] == V3_5_4_RUN_ID
    assert summary["source_quality_audit_run_id"] == V3_5_5_RUN_ID
    assert summary["user_policy_decision_applied"] is True
    assert summary["low_touch_human_review_required"] is False
    assert summary["weak_silver_candidate_count"] == len(rows) == 1000
    assert summary["source_family_counts"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert count_by_source_family(rows) == summary["source_family_counts"]
    assert summary["query_quality_profile_counts"] == {
        "ambiguous_but_source_answerable": 200,
        "clean_source_grounded": 450,
        "noisy_user_like": 100,
        "numeric_table_or_locator_hard": 100,
        "short_keyword_or_fragment": 150,
    }
    assert distribution["query_quality_profile_counts"] == summary["query_quality_profile_counts"]
    assert summary["pass_source_quality_rows_used"] == 666
    assert summary["review_only_rows_used"] == 334
    assert blocked_rows == []
    assert summary["blocked_generation_row_count"] == 0
    assert summary["official_denominator_overlap_detected_count"] == 0
    assert summary["candidate_artifact_source_leak_detected_count"] == 0
    assert summary["duplicate_generated_question_hash_count"] == 0
    assert summary["official_proximity_review_row_count"] == 3
    assert summary["normalized_source_hash_repetition_rows_used"] == 57

    weak_ids = [row["weak_silver_candidate_id"] for row in rows]
    question_hashes = [row["generated_question_hash"] for row in rows]
    source_locator_keys = [
        (row["source_family"], row["source_document_identity"], row["locator_fingerprint"])
        for row in rows
    ]
    assert len(weak_ids) == len(set(weak_ids))
    assert len(question_hashes) == len(set(question_hashes))
    assert len(source_locator_keys) == len(set(source_locator_keys))
    assert {row["source_candidate_id"] for row in rows} == source_candidate_ids

    seen_profiles = {row["query_quality_profile"] for row in rows}
    assert seen_profiles == {
        "clean_source_grounded",
        "short_keyword_or_fragment",
        "ambiguous_but_source_answerable",
        "noisy_user_like",
        "numeric_table_or_locator_hard",
    }
    for row in rows:
        assert_required(
            row,
            (
                "weak_silver_candidate_id",
                "source_candidate_id",
                "source_family",
                "source_document_identity",
                "source_locator",
                "source_text_or_value_hash",
                "source_quality_status",
                "query_quality_profile",
                "generated_question_draft",
                "expected_answer_draft",
                "supporting_evidence_locator_draft",
                "supporting_evidence_excerpt_hash",
                "weak_relevance_status",
                "weak_answerability_status",
                "human_review_status",
                "split_role",
                "generation_policy_version",
            ),
        )
        assert row["source_candidate_id"] in source_candidate_ids
        assert clean(row.get("search_unit_id")) not in official_search_unit_ids
        assert clean(row.get("locator_fingerprint")) not in official_locator_fingerprints
        assert row["official_denominator_overlap"] is False
        assert row["official_denominator_overlap_detected"] is False
        assert row["candidate_artifacts_used_as_generation_source"] is False
        assert row["not_gold"] is True
        assert row["not_official_denominator"] is True
        assert row["not_official_qrels"] is True
        assert row["promotion_evidence"] is False
        assert row["weak_silver_candidate"] is True
        assert row["weak_noisy_silver"] is True
        assert row["human_review_status"] == "weak_silver_unreviewed"
        assert row["expected_answer_status"] == "weak_silver_unreviewed_draft"
        assert row["supporting_evidence_status"] == "weak_silver_unreviewed_draft"
        assert row["weak_relevance_status"] == "auto_weak_silver_source_grounded"
        assert row["official_relevance_label_created"] is False
        assert row["official_answerability_label_created"] is False
        assert row["official_qrels_created"] is False
        assert row["official_gold_label_created"] is False
        assert_forbid_final_label_or_qrels_payload(row)
        locator_draft = row["supporting_evidence_locator_draft"]
        assert locator_draft["source_family"] == row["source_family"]
        assert locator_draft["locator_fingerprint"] == row["locator_fingerprint"]
        assert has_value(locator_draft.get("source_locator"))


def test_v3_6_1_policy_compliance_audit_locks_inputs_splits_and_canonical_silver() -> None:
    summary = read_json(V3_6_1_GENERATION_SUMMARY)
    audit = read_json(V3_6_1_POLICY_COMPLIANCE_AUDIT)
    split = read_json(V3_6_1_SPLIT_MANIFEST)
    next_phase = read_json(V3_6_1_NEXT_PHASE_RECOMMENDATION)

    assert audit["source_policy_run_id"] == V3_6_0_RUN_ID
    assert audit["candidate_artifacts_used_as_generation_source"] is False
    assert audit["candidate_artifact_source_leak_detected_count"] == 0
    assert audit["official_denominator_overlap_detected_count"] == 0
    assert audit["official_gold_labels_created"] is False
    assert audit["official_qrels_created"] is False
    assert audit["official_relevance_labels_created"] is False
    assert audit["official_answerability_labels_created"] is False
    assert audit["promotion_evidence"] is False
    assert audit["representative_product_performance_claim"] is False
    assert audit["protected_input_sha256_before"] == audit["protected_input_sha256_after"]
    assert audit["protected_input_sha256_unchanged"] is True
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False

    assert split["split_counts"] == {
        "weak_silver_exploration": 700,
        "weak_silver_holdout": 200,
        "weak_silver_stress_smoke_candidate": 100,
    }
    assert split["split_counts_by_source_family"]["weak_silver_exploration"] == {
        "TEXT": 244,
        "PDF": 228,
        "XLSX": 228,
        "total": 700,
    }
    assert split["split_counts_by_source_family"]["weak_silver_holdout"] == {
        "TEXT": 70,
        "PDF": 65,
        "XLSX": 65,
        "total": 200,
    }
    assert split["split_counts_by_source_family"]["weak_silver_stress_smoke_candidate"] == {
        "TEXT": 36,
        "PDF": 32,
        "XLSX": 32,
        "total": 100,
    }
    assert split["official_proximity_rows_in_stress_smoke_count"] == 0
    assert split["not_official_dev_holdout_contract"] is True
    assert next_phase["recommended_next_phase"] == "v3_6_2_weak_noisy_silver_candidate_sanity_eval"
    assert next_phase["promotion_evidence"] is False
    assert next_phase["threshold_tuning"] is False
    assert next_phase["winner_selection"] is False

    for split_name in ("contract", "dev", "holdout"):
        assert SILVER_JSONL_BY_SPLIT[split_name].exists() is False


def test_v3_6_2_candidate_sanity_eval_artifacts_are_compact_guarded_and_feasible() -> None:
    summary = read_json(V3_6_2_CANDIDATE_SANITY_SUMMARY)
    per_row = read_jsonl(V3_6_2_CANDIDATE_SANITY_PER_ROW)
    quarantine_rows = read_jsonl(V3_6_2_CANDIDATE_QUARANTINE_ROWS)
    metric_feasibility = read_json(V3_6_2_CANDIDATE_METRIC_FEASIBILITY)
    split_audit = read_json(V3_6_2_SPLIT_INDEPENDENCE_AUDIT)
    hash_audit = read_json(V3_6_2_HASH_CONTRACT_AUDIT)
    next_phase = read_json(V3_6_2_NEXT_PHASE_RECOMMENDATION)

    assert summary["run_id"] == V3_6_2_RUN_ID
    assert summary["artifact_kind"] == "weak_noisy_silver_candidate_sanity_eval"
    assert summary["source_candidate_generation_run_id"] == V3_6_1_RUN_ID
    assert summary["candidate_row_count"] == 1000
    assert summary["unique_weak_silver_candidate_id_count"] == 1000
    assert summary["duplicate_weak_silver_candidate_id_count"] == 0
    assert summary["duplicate_source_identity_locator_count"] == 0
    assert summary["duplicate_generated_question_hash_count"] == 0
    assert summary["duplicate_source_text_or_value_hash_group_count"] == 17
    assert summary["duplicate_source_text_or_value_hash_row_count"] == 57
    assert summary["official_proximity_review_row_count"] == 3
    assert summary["official_proximity_review_split_role_counts"] == {"weak_silver_exploration": 3}
    assert summary["source_identity_groups_crossing_split_roles_count"] == 74
    assert summary["split_independence_warning"] == "source_identity_groups_cross_split_roles_diagnostic_holdout_warning"
    assert summary["split_independence_official_leakage"] is False
    assert summary["candidate_sanity_passed"] is True
    assert summary["bucket_counts"] == {
        "blocked_candidate": 0,
        "core_pass_quality_candidate": 665,
        "quarantine_candidate": 0,
        "review_only_challenge_candidate": 335,
    }
    assert summary["source_family_counts"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert summary["query_quality_profile_counts"] == {
        "ambiguous_but_source_answerable": 200,
        "clean_source_grounded": 450,
        "noisy_user_like": 100,
        "numeric_table_or_locator_hard": 100,
        "short_keyword_or_fragment": 150,
    }
    assert summary["source_quality_status_counts"] == {
        "pass_source_quality": 666,
        "review_duplicate_or_near_duplicate": 57,
        "review_pdf_extraction_order": 29,
        "review_pdf_header_footer_or_boilerplate": 2,
        "review_pdf_numeric_or_table_context": 39,
        "review_short_source_text_or_value": 203,
        "review_xlsx_hidden_policy_boundary": 4,
    }
    assert summary["weak_answerability_status_counts"] == {
        "auto_weak_silver_likely_answerable": 666,
        "auto_weak_silver_uncertain_answerability": 334,
    }
    assert summary["split_role_counts"] == {
        "weak_silver_exploration": 700,
        "weak_silver_holdout": 200,
        "weak_silver_stress_smoke_candidate": 100,
    }
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["lane_a_b_c_collapsed_scoring"] is False
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert "candidate_sanity_per_row" not in summary
    assert "source_candidate_rows" not in summary

    assert len(per_row) == 1000
    assert quarantine_rows == []
    assert {row["diagnostic_bucket"] for row in per_row} == {
        "core_pass_quality_candidate",
        "review_only_challenge_candidate",
    }
    assert all(row["not_gold"] is True for row in per_row)
    assert all(row["not_official_denominator"] is True for row in per_row)
    assert all(row["not_official_qrels"] is True for row in per_row)
    assert all(row["promotion_evidence"] is False for row in per_row)
    assert all(row["official_metric_denominator_usage_allowed"] is False for row in per_row)
    assert all(row["supporting_evidence_excerpt_hash_matches_source_hash"] is True for row in per_row)
    assert sum(1 for row in per_row if row["official_proximity_review"]) == 3
    assert all(
        row["diagnostic_bucket"] == "review_only_challenge_candidate"
        for row in per_row
        if row["official_proximity_review"]
    )
    assert all(
        row["diagnostic_bucket"] == "review_only_challenge_candidate"
        for row in per_row
        if row["source_quality_status"].startswith("review_")
    )

    assert metric_feasibility["candidate_quality_metrics_allowed_immediately"] is True
    assert metric_feasibility["diagnostic_weak_noisy_silver_metrics_allowed_after_v3_6_2_passes"] is True
    assert metric_feasibility["official_metric_denominator_usage_allowed"] is False
    assert metric_feasibility["promotion_evidence_allowed"] is False
    assert metric_feasibility["readme_representative_product_performance_claim_allowed"] is False
    assert metric_feasibility["threshold_tuning_allowed"] is False
    assert metric_feasibility["winner_selection_allowed"] is False

    assert split_audit["source_identity_groups_crossing_split_roles_count"] == 74
    assert split_audit["split_independence_warning"] == "source_identity_groups_cross_split_roles_diagnostic_holdout_warning"
    assert split_audit["official_leakage_detected"] is False
    assert split_audit["not_official_dev_holdout_contract"] is True

    assert hash_audit["generated_question_hash_contract"] == "normalized_question_sha256_lowercase_whitespace_collapsed"
    assert hash_audit["raw_question_hash_contract"] is False
    assert hash_audit["normalized_question_hash_match_count"] == 1000
    assert hash_audit["salted_hash_detected"] is False
    assert hash_audit["source_identity_bound_hash_detected"] is False

    assert next_phase["v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_allowed"] is True
    assert next_phase["recommended_next_phase"] == "v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze"
    assert next_phase["promotion_evidence"] is False
    assert next_phase["official_metric_denominator_usage_allowed"] is False


def test_v3_6_3_diagnostic_manifest_freeze_counts_policy_and_flags() -> None:
    summary = read_json(V3_6_3_MANIFEST_SUMMARY)
    all_rows = read_jsonl(V3_6_3_MANIFEST_ALL)
    core_rows = read_jsonl(V3_6_3_MANIFEST_CORE)
    review_rows = read_jsonl(V3_6_3_MANIFEST_REVIEW_ONLY)
    quarantine_rows = read_jsonl(V3_6_3_MANIFEST_QUARANTINE)
    policy_audit = read_json(V3_6_3_MANIFEST_POLICY_AUDIT)
    next_phase = read_json(V3_6_3_NEXT_PHASE_RECOMMENDATION)
    sanity_summary = read_json(V3_6_2_CANDIDATE_SANITY_SUMMARY)
    sanity_rows = read_jsonl(V3_6_2_CANDIDATE_SANITY_PER_ROW)

    assert summary["run_id"] == V3_6_3_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_weak_noisy_silver_manifest_freeze"
    assert summary["source_candidate_generation_run_id"] == V3_6_1_RUN_ID
    assert summary["source_sanity_eval_run_id"] == V3_6_2_RUN_ID
    assert summary["manifest_freeze_passed"] is True
    assert summary["manifest_row_count"] == len(all_rows) == 1000
    assert summary["core_manifest_row_count"] == len(core_rows) == 665
    assert summary["review_only_manifest_row_count"] == len(review_rows) == 335
    assert summary["quarantine_manifest_row_count"] == len(quarantine_rows) == 0
    assert summary["bucket_counts"] == sanity_summary["bucket_counts"] == {
        "blocked_candidate": 0,
        "core_pass_quality_candidate": 665,
        "quarantine_candidate": 0,
        "review_only_challenge_candidate": 335,
    }
    assert summary["source_family_counts"] == {"TEXT": 350, "PDF": 325, "XLSX": 325, "total": 1000}
    assert summary["split_role_counts"] == {
        "weak_silver_exploration": 700,
        "weak_silver_holdout": 200,
        "weak_silver_stress_smoke_candidate": 100,
    }
    assert summary["query_quality_profile_counts"] == sanity_summary["query_quality_profile_counts"]
    assert summary["source_quality_status_counts"] == sanity_summary["source_quality_status_counts"]
    assert summary["weak_answerability_status_counts"] == sanity_summary["weak_answerability_status_counts"]
    assert summary["official_proximity_review_row_count"] == 3
    assert summary["official_proximity_review_split_role_counts"] == {"weak_silver_exploration": 3}
    assert summary["duplicate_source_text_or_value_hash_group_count"] == 17
    assert summary["duplicate_source_text_or_value_hash_row_count"] == 57
    assert summary["split_independence_warning"] == "source_identity_groups_cross_split_roles_diagnostic_holdout_warning"
    assert summary["hash_contract"] == "normalized_question_sha256_lowercase_whitespace_collapsed"
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert "manifest_rows_all" not in summary
    assert "source_candidate_rows" not in summary
    assert "sanity_rows" not in summary

    all_ids = {row["weak_silver_candidate_id"] for row in all_rows}
    core_ids = {row["weak_silver_candidate_id"] for row in core_rows}
    review_ids = {row["weak_silver_candidate_id"] for row in review_rows}
    quarantine_ids = {row["weak_silver_candidate_id"] for row in quarantine_rows}
    sanity_ids = {row["weak_silver_candidate_id"] for row in sanity_rows}
    sanity_proximity_ids = {
        row["weak_silver_candidate_id"]
        for row in sanity_rows
        if row["official_proximity_review"]
    }
    assert all_ids == sanity_ids
    assert core_ids | review_ids | quarantine_ids == all_ids
    assert core_ids.isdisjoint(review_ids)
    assert core_ids.isdisjoint(quarantine_ids)
    assert review_ids.isdisjoint(quarantine_ids)
    assert sanity_proximity_ids
    assert sanity_proximity_ids <= review_ids
    assert sanity_proximity_ids.isdisjoint(core_ids)

    core_policy = summary["core_manifest_policy"]
    assert core_policy["pass_source_quality_and_likely_answerable_are_necessary_but_not_sufficient"] is True
    assert core_policy["official_proximity_review_rows_remain_review_only"] is True
    assert set(core_policy["excluded_from_core_reasons"]) >= {
        "review_duplicate_or_near_duplicate",
        "review_short_source_text_or_value",
        "review_pdf_extraction_order",
        "review_pdf_numeric_or_table_context",
        "review_pdf_header_footer_or_boilerplate",
        "review_xlsx_hidden_policy_boundary",
        "auto_weak_silver_uncertain_answerability",
        "official_proximity_review",
    }

    for row in all_rows:
        assert row["manifest_run_id"] == V3_6_3_RUN_ID
        assert row["source_candidate_generation_run_id"] == V3_6_1_RUN_ID
        assert row["source_sanity_eval_run_id"] == V3_6_2_RUN_ID
        assert row["diagnostic_only"] is True
        assert row["not_gold"] is True
        assert row["not_official_denominator"] is True
        assert row["not_official_qrels"] is True
        assert row["promotion_evidence"] is False
        assert row["official_qrels_created"] is False
        assert row["official_relevance_label_created"] is False
        assert row["official_answerability_label_created"] is False
        assert row["official_gold_label_created"] is False
        assert row["official_metric_denominator_usage_allowed"] is False
        assert_forbid_final_label_or_qrels_payload(row)
        assert "source_candidate_rows" not in row
        assert "sanity_rows" not in row

    assert {row["diagnostic_bucket"] for row in core_rows} == {"core_pass_quality_candidate"}
    assert {row["diagnostic_bucket"] for row in review_rows} == {"review_only_challenge_candidate"}
    assert all(row["source_quality_status"] == "pass_source_quality" for row in core_rows)
    assert all(row["weak_answerability_status"] == "auto_weak_silver_likely_answerable" for row in core_rows)
    assert not any(row["official_proximity_review"] for row in core_rows)
    assert all(
        row["diagnostic_bucket"] == "review_only_challenge_candidate"
        for row in review_rows
        if row["official_proximity_review"]
    )
    assert sum(1 for row in review_rows if row["official_proximity_review"]) == 3

    assert policy_audit["official_qrels_created"] is False
    assert policy_audit["official_relevance_labels_created"] is False
    assert policy_audit["official_answerability_labels_created"] is False
    assert policy_audit["official_denominator_mutation"] is False
    assert policy_audit["promotion_evidence"] is False
    assert policy_audit["threshold_tuning"] is False
    assert policy_audit["winner_selection"] is False
    assert policy_audit["readme_representative_product_performance_claim"] is False
    assert policy_audit["protected_input_sha256_before"] == policy_audit["protected_input_sha256_after"]

    assert next_phase["v3_6_4_diagnostic_only_weak_noisy_silver_metric_allowed"] is True
    assert next_phase["recommended_next_phase"] == "v3_6_4_diagnostic_only_weak_noisy_silver_metric"
    assert next_phase["requires_separate_reporting_for"] == [
        "core_only",
        "review_only_challenge",
        "all_diagnostic",
    ]
    assert next_phase["official_metric_denominator_usage_allowed"] is False
    assert next_phase["promotion_evidence"] is False
    assert next_phase["threshold_tuning"] is False
    assert next_phase["winner_selection"] is False


def test_v3_6_4_diagnostic_metric_preserves_manifest_partitions_and_guardrails() -> None:
    summary = read_json(V3_6_4_SUMMARY)
    per_row = read_jsonl(V3_6_4_PER_ROW)
    aggregate = read_json(V3_6_4_AGGREGATE_BY_BUCKET)
    failure_taxonomy = read_json(V3_6_4_FAILURE_TAXONOMY)
    sample_review = read_jsonl(V3_6_4_SAMPLE_REVIEW)
    policy_audit = read_json(V3_6_4_POLICY_AUDIT)
    next_phase = read_json(V3_6_4_NEXT_PHASE_RECOMMENDATION)
    v3_6_3_summary = read_json(V3_6_3_MANIFEST_SUMMARY)

    assert summary["run_id"] == V3_6_4_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_only_weak_noisy_silver_metric"
    assert summary["source_manifest_run_id"] == V3_6_3_RUN_ID
    assert summary["manifest_metric_passed"] is True
    assert summary["fail_closed_reasons"] == []
    assert summary["generated_expected_answers_are_gold"] is False
    assert summary["official_metric"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    assert summary["not_gold"] is True
    assert summary["not_official_qrels"] is True
    assert summary["not_official_denominator"] is True
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_representative_product_performance_claim"] is False
    assert summary["lane_a_b_c_collapsed_scoring"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False

    assert summary["manifest_counts"] == {
        "all_diagnostic": 1000,
        "core_only": 665,
        "review_only_challenge": 335,
        "quarantine": 0,
    }
    assert summary["manifest_row_count"] == len(per_row) == v3_6_3_summary["manifest_row_count"] == 1000
    assert summary["core_manifest_row_count"] == 665
    assert summary["review_only_manifest_row_count"] == 335
    assert summary["quarantine_manifest_row_count"] == 0
    assert summary["source_family_counts"] == {"PDF": 325, "TEXT": 350, "XLSX": 325}
    assert summary["split_role_counts"] == {
        "weak_silver_exploration": 700,
        "weak_silver_holdout": 200,
        "weak_silver_stress_smoke_candidate": 100,
    }
    assert summary["query_quality_profile_counts"] == v3_6_3_summary["query_quality_profile_counts"]
    assert summary["source_quality_status_counts"] == v3_6_3_summary["source_quality_status_counts"]
    assert summary["weak_answerability_status_counts"] == v3_6_3_summary["weak_answerability_status_counts"]
    assert summary["source_identity_groups_crossing_split_roles_count"] == 74
    assert summary["split_independence_warning"] == "source_identity_groups_cross_split_roles_diagnostic_holdout_warning"
    assert summary["split_independence_official_leakage"] is False
    assert summary["official_proximity_review_row_count"] == 3
    assert summary["official_proximity_core_row_count"] == 0
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True

    reporting = aggregate["reporting_partitions"]
    assert set(reporting) == {"core_only", "review_only_challenge", "all_diagnostic"}
    assert reporting["core_only"]["row_count"] == 665
    assert reporting["review_only_challenge"]["row_count"] == 335
    assert reporting["all_diagnostic"]["row_count"] == 1000
    assert reporting["core_only"]["official_proximity_review_row_count"] == 0
    assert reporting["review_only_challenge"]["official_proximity_review_row_count"] == 3
    for partition in reporting.values():
        assert partition["generated_expected_answers_are_gold"] is False
        assert partition["official_metric"] is False
        metrics = partition["metrics"]
        assert metrics["diagnostic_source_identity_hit_at_1"] == 1.0
        assert metrics["diagnostic_source_identity_hit_at_3"] == 1.0
        assert metrics["diagnostic_source_identity_hit_at_5"] == 1.0
        assert metrics["diagnostic_locator_fingerprint_hit_at_1"] == 1.0
        assert metrics["diagnostic_locator_fingerprint_hit_at_3"] == 1.0
        assert metrics["diagnostic_locator_fingerprint_hit_at_5"] == 1.0
        assert metrics["diagnostic_source_family_match_at_5"] == 1.0
        assert metrics["diagnostic_retrieved_context_present_rate"] == 1.0
        assert metrics["diagnostic_citation_locator_parse_success_rate"] == 1.0
        assert metrics["diagnostic_citation_source_identity_match_rate"] == 1.0
        assert metrics["diagnostic_answer_non_empty_rate"] == 0.0
        assert metrics["diagnostic_answer_normalized_exact_match_rate"] == 0.0
        assert metrics["diagnostic_answer_contains_expected_draft_rate"] == 0.0
        assert metrics["diagnostic_answer_token_f1_mean"] == 0.0
        assert metrics["diagnostic_citation_emitted_rate"] == 0.0
        assert metrics["diagnostic_citation_locator_match_rate"] == 0.0
        assert metrics["diagnostic_answer_citation_consistency_proxy_rate"] == 0.0

    assert reporting["all_diagnostic"]["metrics"]["diagnostic_numeric_or_date_value_match_rate"] == 0.0
    assert aggregate["source_family"]["TEXT"]["row_count"] == 350
    assert aggregate["source_family"]["PDF"]["row_count"] == 325
    assert aggregate["source_family"]["XLSX"]["row_count"] == 325
    assert aggregate["split_role"]["exploration"]["row_count"] == 700
    assert aggregate["split_role"]["holdout"]["row_count"] == 200
    assert aggregate["split_role"]["stress_smoke_candidate"]["row_count"] == 100
    assert aggregate["query_quality_profile"]["clean_source_grounded"]["row_count"] == 450
    assert aggregate["source_quality_status"]["pass_source_quality"]["row_count"] == 666
    assert aggregate["weak_answerability_status"]["auto_weak_silver_likely_answerable"]["row_count"] == 666

    assert failure_taxonomy["primary_failure_counts"]["runtime_fail_closed"] == 665
    assert failure_taxonomy["primary_failure_counts"]["weak_silver_expected_answer_ambiguous"] == 334
    assert failure_taxonomy["primary_failure_counts"]["review_only_source_quality_risk"] == 1
    assert failure_taxonomy["primary_failure_counts"]["pass_diagnostic_proxy"] == 0
    assert summary["primary_failure_taxonomy"] == failure_taxonomy["primary_failure_counts"]
    assert {row["primary_failure"] for row in sample_review} >= {
        "runtime_fail_closed",
        "weak_silver_expected_answer_ambiguous",
        "review_only_source_quality_risk",
    }

    assert {row["reporting_partition"] for row in per_row} == {"core_only", "review_only_challenge"}
    assert sum(1 for row in per_row if row["reporting_partition"] == "core_only") == 665
    assert sum(1 for row in per_row if row["reporting_partition"] == "review_only_challenge") == 335
    assert all(row["generated_expected_answers_are_gold"] is False for row in per_row)
    assert all(row["official_metric_denominator_usage_allowed"] is False for row in per_row)
    assert all(row["promotion_evidence"] is False for row in per_row)
    assert all(row["runtime_generation_fail_closed"] is True for row in per_row)
    assert all(row["diagnostic_answer_non_empty"] is False for row in per_row)

    for key in (
        "diagnostic_only",
        "not_gold",
        "not_official_qrels",
        "not_official_denominator",
    ):
        assert policy_audit[key] is True
    for key in (
        "official_metric",
        "official_metric_denominator_usage_allowed",
        "generated_expected_answers_are_gold",
        "promotion_evidence",
        "threshold_tuning",
        "winner_selection",
        "readme_representative_product_performance_claim",
        "lane_a_b_c_collapsed_scoring",
        "prompt_mutation",
        "retrieval_mutation",
        "scorer_mutation",
        "renderer_mutation",
        "index_or_export_mutation",
        "production_mutation",
        "candidate_artifacts_used_as_generation_source",
    ):
        assert policy_audit[key] is False

    assert next_phase["v3_6_5_should_proceed_to"] == "rough_failure_bucket_triage"
    assert next_phase["targeted_diagnostic_repair_planning_now"] is False
    assert next_phase["targeted_diagnostic_repair_planning_after_triage"] is True


def test_v3_6_4_diagnostic_metric_fails_closed_if_review_flags_enter_core() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    manifest_summary = read_json(V3_6_3_MANIFEST_SUMMARY)
    manifest_policy_audit = read_json(V3_6_3_MANIFEST_POLICY_AUDIT)
    manifest_next_phase = read_json(V3_6_3_NEXT_PHASE_RECOMMENDATION)
    all_rows = read_jsonl(V3_6_3_MANIFEST_ALL)
    core_rows = read_jsonl(V3_6_3_MANIFEST_CORE)
    review_rows = read_jsonl(V3_6_3_MANIFEST_REVIEW_ONLY)
    quarantine_rows = read_jsonl(V3_6_3_MANIFEST_QUARANTINE)

    clean_reasons = runner.v3_6_4_manifest_fail_closed_reasons(
        missing_source_files=[],
        manifest_summary=manifest_summary,
        manifest_policy_audit=manifest_policy_audit,
        manifest_next_phase=manifest_next_phase,
        all_rows=all_rows,
        core_rows=core_rows,
        review_rows=review_rows,
        quarantine_rows=quarantine_rows,
    )
    assert clean_reasons == []

    proximity_core_rows = [dict(row) for row in core_rows]
    proximity_core_rows[0]["official_proximity_review"] = True
    proximity_reasons = runner.v3_6_4_manifest_fail_closed_reasons(
        missing_source_files=[],
        manifest_summary=manifest_summary,
        manifest_policy_audit=manifest_policy_audit,
        manifest_next_phase=manifest_next_phase,
        all_rows=all_rows,
        core_rows=proximity_core_rows,
        review_rows=review_rows,
        quarantine_rows=quarantine_rows,
    )
    assert "official_proximity_rows_in_core" in proximity_reasons

    source_quality_core_rows = [dict(row) for row in core_rows]
    source_quality_core_rows[0]["source_quality_status"] = "review_xlsx_hidden_policy_boundary"
    source_quality_reasons = runner.v3_6_4_manifest_fail_closed_reasons(
        missing_source_files=[],
        manifest_summary=manifest_summary,
        manifest_policy_audit=manifest_policy_audit,
        manifest_next_phase=manifest_next_phase,
        all_rows=all_rows,
        core_rows=source_quality_core_rows,
        review_rows=review_rows,
        quarantine_rows=quarantine_rows,
    )
    assert "review_source_quality_rows_in_core" in source_quality_reasons


def test_v3_6_5_rough_failure_bucket_triage_policy_and_surface_audits() -> None:
    summary = read_json(V3_6_5_SUMMARY)
    per_row = read_jsonl(V3_6_5_PER_ROW)
    blocker_matrix = read_json(V3_6_5_BLOCKER_MATRIX)
    runtime_audit = read_json(V3_6_5_RUNTIME_SURFACE_AUDIT)
    reference_audit = read_json(V3_6_5_REFERENCE_SURFACE_AUDIT)
    db_audit = read_json(V3_6_5_DB_SURFACE_AUDIT)
    local_llm_audit = read_json(V3_6_5_LOCAL_LLM_SURFACE_AUDIT)
    policy_audit = read_json(V3_6_5_POLICY_AUDIT)
    next_phase = read_json(V3_6_5_NEXT_PHASE_RECOMMENDATION)

    assert summary["run_id"] == V3_6_5_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_only_rough_failure_bucket_triage"
    assert summary["v3_6_4_source_run_id"] == V3_6_4_RUN_ID
    assert summary["source_manifest_counts"] == {
        "all_diagnostic": 1000,
        "core_only": 665,
        "quarantine": 0,
        "review_only_challenge": 335,
    }
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_representative_product_performance_claim"] is False
    assert summary["generated_expected_answers_are_gold"] is False
    assert summary["local_llm_usage_allowed"] is True
    assert summary["local_llm_usage_scope"] == "capability_probe_and_runtime_surface_audit_only"
    assert summary["local_llm_live_silver_generation_allowed"] is False
    assert summary["local_llm_metric_scoring_allowed"] is False
    assert summary["external_llm_api_allowed"] is False
    assert summary["db_usage_allowed"] is True
    assert summary["db_usage_scope"] == "read_only_reference_and_runtime_surface_audit_only"
    assert summary["db_write_allowed"] is False
    assert summary["db_migration_allowed"] is False
    assert summary["db_index_rebuild_allowed"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["db_results_as_gold_allowed"] is False
    assert summary["db_results_as_official_qrels_allowed"] is False
    assert summary["db_results_as_generation_source_allowed"] is False

    assert summary["local_llm_live_silver_generation_attempted"] is False
    assert summary["local_llm_metric_scoring_attempted"] is False
    assert summary["external_llm_api_attempted"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["production_db_used"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["fail_closed_reasons"] == []
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["protected_input_sha256_matches_v3_6_4_summary"] is True
    assert summary["protected_v3_6_3_input_sha256_before"] == summary["protected_v3_6_3_input_sha256_after"]
    assert summary["protected_v3_6_3_input_sha256_unchanged"] is True

    assert summary["v3_6_4_primary_failure_counts"] == {
        "answer_span_mismatch": 0,
        "citation_missing": 0,
        "citation_parse_failure": 0,
        "citation_source_mismatch": 0,
        "locator_mismatch": 0,
        "numeric_or_date_mismatch": 0,
        "pass_diagnostic_proxy": 0,
        "retrieval_miss": 0,
        "review_only_source_quality_risk": 1,
        "runtime_fail_closed": 665,
        "source_family_mismatch": 0,
        "unsupported_metric_surface": 0,
        "weak_silver_expected_answer_ambiguous": 334,
    }
    bucket_counts = summary["multi_label_blocker_bucket_counts"]
    assert bucket_counts["runtime_generation_surface_unavailable"] == 1000
    assert bucket_counts["answer_proxy_reference_missing_from_v3_6_3_manifest"] == 1000
    assert bucket_counts["live_retrieval_metric_not_computed"] == 1000
    assert bucket_counts["deterministic_manifest_locator_self_match_only"] == 1000
    assert bucket_counts["weak_silver_expected_answer_ambiguous"] == 334
    assert bucket_counts["review_only_source_quality_noise"] == 334
    assert bucket_counts["official_proximity_review_excluded_from_core"] == 3
    assert bucket_counts["core_metric_not_interpretable_until_runtime_available"] == 665
    assert bucket_counts["review_only_metric_stress_only"] == 335
    assert bucket_counts["diagnostic_reference_sidecar_possible"] == 1000
    assert bucket_counts["targeted_repair_not_allowed_until_triage_complete"] == 1000

    assert len(per_row) == 1000
    first_row = per_row[0]
    assert first_row["local_llm_generation_attempted"] is False
    assert first_row["db_write_attempted"] is False
    assert first_row["generated_expected_answers_are_gold"] is False
    assert first_row["not_gold"] is True
    assert first_row["not_official_qrels"] is True
    assert first_row["not_official_denominator"] is True
    assert first_row["promotion_evidence"] is False
    assert {row["blocker_name"] for row in blocker_matrix["blockers"]} >= set(bucket_counts)

    assert runtime_audit["local_llm_surface_classification"] in {
        "reusable_without_behavior_change",
        "reusable_with_diagnostic_adapter_only",
        "unavailable_requires_new_diagnostic_runtime_surface",
        "blocked_by_policy",
    }
    assert runtime_audit["local_llm_health_check_used_silver_rows"] is False
    assert runtime_audit["local_llm_health_check_used_source_text"] is False
    assert runtime_audit["local_llm_health_check_used_expected_answers"] is False
    assert runtime_audit["local_llm_health_check_used_supporting_evidence"] is False
    assert runtime_audit["local_llm_health_check_used_gold_fields"] is False
    assert runtime_audit["local_llm_live_silver_generation_attempted"] is False
    assert runtime_audit["local_llm_live_silver_generation_allowed"] is False
    assert runtime_audit["local_llm_metric_scoring_attempted"] is False
    assert runtime_audit["local_llm_metric_scoring_allowed"] is False
    assert runtime_audit["external_llm_api_allowed"] is False
    assert runtime_audit["external_llm_api_attempted"] is False
    assert runtime_audit["db_write_allowed"] is False
    assert runtime_audit["db_write_attempted"] is False
    assert runtime_audit["db_index_rebuild_allowed"] is False
    assert runtime_audit["db_index_rebuild_attempted"] is False

    assert local_llm_audit["local_llm_usage_allowed"] is True
    assert local_llm_audit["local_llm_live_silver_generation_attempted"] is False
    assert local_llm_audit["external_llm_api_attempted"] is False

    assert reference_audit["candidate_row_count"] == 1000
    assert reference_audit["candidate_expected_answer_draft_available"] is True
    assert reference_audit["candidate_expected_answer_draft_present_count"] == 1000
    assert reference_audit["candidate_supporting_evidence_locator_draft_available"] is True
    assert reference_audit["candidate_supporting_evidence_locator_draft_present_count"] == 1000
    assert reference_audit["reference_sidecar_possible"] is True
    assert reference_audit["reference_sidecar_recommended"] is True
    assert reference_audit["generated_expected_answers_are_gold"] is False
    assert reference_audit["references_used_for_generation"] is False
    assert reference_audit["references_used_for_official_metric"] is False
    assert reference_audit["references_used_for_promotion"] is False

    assert db_audit["db_usage_allowed"] is True
    assert db_audit["db_read_only_probe_attempted"] is True
    assert db_audit["db_surface_detected"] is True
    assert db_audit["db_write_attempted"] is False
    assert db_audit["db_migration_attempted"] is False
    assert db_audit["db_index_rebuild_attempted"] is False
    assert db_audit["production_db_used"] is False
    assert db_audit["db_results_as_gold_allowed"] is False
    assert db_audit["db_results_as_official_qrels_allowed"] is False
    assert db_audit["db_results_as_generation_source_allowed"] is False
    assert db_audit["candidate_expected_answer_draft_available"] is True
    assert db_audit["candidate_supporting_evidence_locator_draft_available"] is True
    assert db_audit["diagnostic_reference_sidecar_recommended"] is True
    assert db_audit["live_retrieval_probe_requires_diagnostic_adapter"] is True

    for key in (
        "local_llm_usage_allowed",
        "db_usage_allowed",
        "diagnostic_only",
        "not_gold",
        "not_official_qrels",
        "not_official_denominator",
    ):
        assert policy_audit[key] is True
    for key in (
        "local_llm_live_silver_generation_allowed",
        "local_llm_metric_scoring_allowed",
        "external_llm_api_allowed",
        "db_write_allowed",
        "db_migration_allowed",
        "db_index_rebuild_allowed",
        "production_db_usage_allowed",
        "db_results_as_gold_allowed",
        "db_results_as_official_qrels_allowed",
        "db_results_as_generation_source_allowed",
        "promotion_evidence",
        "threshold_tuning",
        "winner_selection",
        "local_llm_live_silver_generation_attempted",
        "local_llm_metric_scoring_attempted",
        "external_llm_api_attempted",
        "db_write_attempted",
        "db_migration_attempted",
        "db_index_rebuild_attempted",
        "production_db_used",
    ):
        assert policy_audit[key] is False

    assert policy_audit["official_proximity_rows_enter_core"] is False
    assert policy_audit["official_proximity_rows_remain_review_only"] is True
    assert policy_audit["split_holdout_not_source_isolated"] is True
    assert next_phase["recommended_next_phase"] == "v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe"
    assert next_phase["targeted_diagnostic_repair_planning_now"] is False
    assert next_phase["targeted_diagnostic_repair_planning_after_runtime_reference_probe"] is True
    assert next_phase["db_read_only_reference_sidecar_allowed_next_phase"] is True
    assert next_phase["local_llm_live_core_generation_allowed_next_phase"] is False


def test_v3_6_6_reference_sidecar_runtime_and_retrieval_probe_are_diagnostic_only() -> None:
    summary = read_json(V3_6_6_SUMMARY)
    sidecar = read_jsonl(V3_6_6_REFERENCE_SIDECAR)
    smoke_rows = read_jsonl(V3_6_6_CORE_SMOKE_SAMPLE)
    runtime_summary = read_json(V3_6_6_RUNTIME_PROBE_SUMMARY)
    db_audit = read_json(V3_6_6_DB_RETRIEVAL_SURFACE_AUDIT)
    policy_audit = read_json(V3_6_6_POLICY_AUDIT)
    next_phase = read_json(V3_6_6_NEXT_PHASE_RECOMMENDATION)

    assert summary["run_id"] == V3_6_6_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_reference_sidecar_and_runtime_surface_probe"
    assert summary["source_triage_run_id"] == V3_6_5_RUN_ID
    assert summary["sidecar_row_counts"] == {
        "all_diagnostic": 1000,
        "core_only": 665,
        "quarantine": 0,
        "review_only_challenge": 335,
    }
    assert len(sidecar) == 1000
    assert summary["diagnostic_reference_sidecar_complete"] is True
    assert summary["expected_answer_draft_availability"]["present_count"] == 1000
    assert summary["supporting_evidence_locator_draft_availability"]["present_count"] == 1000
    assert summary["official_proximity_rows_remain_out_of_core"] is True
    assert summary["official_proximity_core_row_count"] == 0
    assert summary["review_only_remains_stress_only"] is True
    assert summary["split_holdout_independence_warning_carried_forward"] is True

    assert {row["reporting_partition"] for row in sidecar} == {
        "core_only",
        "review_only_challenge",
    }
    assert sum(1 for row in sidecar if row["reporting_partition"] == "core_only") == 665
    assert sum(1 for row in sidecar if row["reporting_partition"] == "review_only_challenge") == 335
    assert not [
        row["weak_silver_candidate_id"]
        for row in sidecar
        if row["official_proximity_review"] and row["reporting_partition"] == "core_only"
    ]
    for row in sidecar:
        assert row["generated_question_draft"]
        assert row["expected_answer_draft"]
        assert row["supporting_evidence_locator_draft"]
        assert row["generated_expected_answers_are_gold"] is False
        assert row["not_gold"] is True
        assert row["not_official_qrels"] is True
        assert row["not_official_denominator"] is True
        assert row["promotion_evidence"] is False
        assert row["references_used_for_generation"] is False
        assert row["references_used_for_official_metric"] is False

    assert len(smoke_rows) == 30
    assert summary["core_smoke_sample_target_row_count"] == 30
    assert runtime_summary["core_smoke_sample_target_by_source_family"] == {"PDF": 10, "TEXT": 10, "XLSX": 10}
    assert runtime_summary["core_smoke_generation_attempted_row_count"] <= 30
    assert runtime_summary["core_smoke_generation_succeeded_row_count"] <= runtime_summary[
        "core_smoke_generation_attempted_row_count"
    ]
    assert summary["core_smoke_generation_attempted_row_count"] == runtime_summary[
        "core_smoke_generation_attempted_row_count"
    ]
    assert summary["core_smoke_generation_succeeded_row_count"] == runtime_summary[
        "core_smoke_generation_succeeded_row_count"
    ]
    assert runtime_summary["generation_input_policy"]["uses_generated_question_draft"] is True
    assert runtime_summary["generation_input_policy"]["uses_source_family"] is True
    assert runtime_summary["generation_input_policy"]["uses_source_identity"] is False
    assert runtime_summary["generation_input_policy"]["uses_locator_fingerprint"] is False
    assert runtime_summary["generation_input_policy"]["uses_expected_answer_draft"] is False
    assert runtime_summary["generation_input_policy"]["uses_supporting_evidence_locator_draft"] is False
    assert runtime_summary["generation_input_policy"]["uses_gold_fields"] is False
    assert runtime_summary["generation_input_policy"]["uses_official_fields"] is False
    assert runtime_summary["generation_input_policy"]["uses_db_query_results_as_generation_source"] is False
    assert runtime_summary["generation_input_policy"]["posthoc_validation_uses_source_identity"] is True
    assert runtime_summary["generation_input_policy"]["posthoc_validation_uses_locator_fingerprint"] is True
    for row in smoke_rows:
        assert row["reporting_partition"] == "core_only"
        assert row["generation_input_field_names"] == [
            "generated_question_draft",
            "source_family",
        ]
        assert "source_identity" not in row["generation_input_field_names"]
        assert "locator_fingerprint" not in row["generation_input_field_names"]
        assert "expected_answer_draft" not in row
        assert "supporting_evidence_locator_draft" not in row
        assert row["generation_input_used_expected_answer_draft"] is False
        assert row["generation_input_used_supporting_evidence_locator_draft"] is False
        assert row["generation_input_used_gold_fields"] is False
        assert row["generation_input_used_official_fields"] is False
        assert row["generation_input_used_db_query_results"] is False
        assert row["generated_expected_answers_are_gold"] is False
        assert row["not_gold"] is True
        assert row["not_official_qrels"] is True
        assert row["not_official_denominator"] is True
        assert row["promotion_evidence"] is False

    assert db_audit["db_read_only_probe_attempted"] is True
    assert db_audit["manifest_locator_mapping_available"] is True
    assert db_audit["db_write_attempted"] is False
    assert db_audit["db_migration_attempted"] is False
    assert db_audit["db_index_rebuild_attempted"] is False
    assert db_audit["production_db_used"] is False
    assert db_audit["db_results_as_generation_source_allowed"] is False
    assert "@" not in " ".join(db_audit["db_path_or_dsn_sanitized"])

    for payload in (summary, runtime_summary, db_audit, policy_audit, next_phase):
        assert payload["generated_expected_answers_are_gold"] is False
        assert payload["not_gold"] is True
        assert payload["not_official_qrels"] is True
        assert payload["not_official_denominator"] is True
        assert payload["promotion_evidence"] is False
    for key in (
        "official_metric_denominator_usage_allowed",
        "threshold_tuning",
        "winner_selection",
        "readme_representative_product_performance_claim",
        "lane_a_b_c_collapsed_scoring",
        "prompt_mutation",
        "retrieval_mutation",
        "scorer_mutation",
        "renderer_mutation",
        "index_or_export_mutation",
        "production_mutation",
        "official_qrels_created",
        "official_relevance_labels_created",
        "official_answerability_labels_created",
        "official_gold_labels_created",
    ):
        assert summary[key] is False
        assert policy_audit[key] is False

    expected_recommendations = {
        "v3_6_7_core_only_live_diagnostic_weak_noisy_silver_metric",
        "v3_6_7_runtime_stability_probe_for_core_only",
        "v3_6_7_manifest_locator_live_retrieval_probe",
        "v3_6_7_reference_sidecar_recovery_or_compaction_fix",
    }
    assert next_phase["recommended_next_phase"] in expected_recommendations
    assert next_phase["choose_exactly_one_policy_satisfied"] is True
    assert summary["recommended_next_phase"] == next_phase["recommended_next_phase"]
    assert summary["v3_6_7_core_only_live_diagnostic_metric_allowed"] == next_phase[
        "v3_6_7_core_only_live_diagnostic_metric_allowed"
    ]
    if runtime_summary["local_generation_unstable"]:
        assert next_phase["recommended_next_phase"] == "v3_6_7_runtime_stability_probe_for_core_only"
    elif runtime_summary["local_generation_blocked"]:
        assert next_phase["recommended_next_phase"] == "v3_6_7_manifest_locator_live_retrieval_probe"
    elif runtime_summary["local_generation_succeeded"] and db_audit["live_retrieval_probe_feasible_without_rebuild"]:
        assert next_phase["recommended_next_phase"] == "v3_6_7_core_only_live_diagnostic_weak_noisy_silver_metric"


def test_v3_6_6_source_policy_validation_fails_closed_on_inherited_llm_or_db_mutation_flags() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    local_llm_audit = read_json(V3_6_5_LOCAL_LLM_SURFACE_AUDIT)
    db_audit = read_json(V3_6_5_DB_SURFACE_AUDIT)
    local_llm_audit["external_llm_api_attempted"] = True
    db_audit["db_write_attempted"] = True
    db_audit["db_migration_attempted"] = True
    db_audit["db_index_rebuild_attempted"] = True
    reasons = runner.v3_6_6_source_fail_closed_reasons(
        source_load_errors=[],
        v3_6_5_summary=read_json(V3_6_5_SUMMARY),
        v3_6_5_policy=read_json(V3_6_5_POLICY_AUDIT),
        v3_6_5_local_llm=local_llm_audit,
        v3_6_5_db=db_audit,
        v3_6_5_next_phase=read_json(V3_6_5_NEXT_PHASE_RECOMMENDATION),
        v3_6_4_summary=read_json(V3_6_4_SUMMARY),
        v3_6_3_summary=read_json(V3_6_3_MANIFEST_SUMMARY),
        candidate_rows=read_jsonl(V3_6_1_WEAK_SILVER_CANDIDATES),
        manifest_all_rows=read_jsonl(V3_6_3_MANIFEST_ALL),
        manifest_core_rows=read_jsonl(V3_6_3_MANIFEST_CORE),
        manifest_review_rows=read_jsonl(V3_6_3_MANIFEST_REVIEW_ONLY),
        manifest_quarantine_rows=read_jsonl(V3_6_3_MANIFEST_QUARANTINE),
        v3_6_4_rows=read_jsonl(V3_6_4_PER_ROW),
        v3_6_5_rows=read_jsonl(V3_6_5_PER_ROW),
    )

    assert "v3_6_5_local_llm_guardrail_true:external_llm_api_attempted" in reasons
    assert "v3_6_5_db_guardrail_true:db_write_attempted" in reasons
    assert "v3_6_5_db_guardrail_true:db_migration_attempted" in reasons
    assert "v3_6_5_db_guardrail_true:db_index_rebuild_attempted" in reasons


def test_v3_6_7_runtime_stability_probe_is_core_only_diagnostic_and_non_promoting() -> None:
    summary = read_json(V3_6_7_SUMMARY)
    attempts = read_jsonl(V3_6_7_RUNTIME_ATTEMPTS)
    runtime_summary = read_json(V3_6_7_RUNTIME_STABILITY_SUMMARY)
    policy_audit = read_json(V3_6_7_POLICY_AUDIT)
    next_phase = read_json(V3_6_7_NEXT_PHASE_RECOMMENDATION)

    assert summary["run_id"] == V3_6_7_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_runtime_stability_probe_for_core_only"
    assert summary["source_v3_6_6_run_id"] == V3_6_6_RUN_ID
    assert summary["v3_6_6_recommended_this_phase"] is True
    assert summary["sidecar_row_counts"] == {
        "all_diagnostic": 1000,
        "core_only": 665,
        "quarantine": 0,
        "review_only_challenge": 335,
    }
    assert len(attempts) == 30
    assert summary["runtime_probe_row_count"] == len(attempts)
    assert runtime_summary["runtime_probe_row_count"] == len(attempts)
    assert summary["runtime_probe_core_only"] is True
    assert runtime_summary["runtime_probe_core_only"] is True
    assert summary["review_only_rows_attempted"] == 0
    assert runtime_summary["review_only_rows_attempted"] == 0
    assert summary["official_proximity_rows_attempted"] == 0
    assert runtime_summary["official_proximity_rows_attempted"] == 0

    assert sum(1 for row in attempts if row["local_llm_invoked"]) == summary["runtime_attempted_row_count"]
    assert summary["strict_json_answer_returned_row_count"] <= summary["runtime_attempted_row_count"]
    assert summary["citation_surface_valid_row_count"] <= summary["runtime_attempted_row_count"]
    assert summary["baseline_strict_json_answer_returned_row_count"] <= len(attempts)
    assert summary["baseline_citation_surface_valid_row_count"] <= len(attempts)
    assert runtime_summary["runtime_stability_classification"] == summary["runtime_stability_classification"]
    assert runtime_summary["local_llm_surface_classification"] == summary["local_llm_surface_classification"]
    assert runtime_summary["generation_input_policy"] == {
        "uses_generated_question_draft": True,
        "uses_source_family": True,
        "uses_source_identity": False,
        "uses_locator_fingerprint": False,
        "uses_expected_answer_draft": False,
        "uses_supporting_evidence_locator_draft": False,
        "uses_gold_fields": False,
        "uses_official_fields": False,
        "uses_db_query_results_as_generation_source": False,
        "posthoc_validation_uses_source_identity": True,
        "posthoc_validation_uses_locator_fingerprint": True,
    }
    assert policy_audit["generation_input_policy"] == runtime_summary["generation_input_policy"]
    for row in attempts:
        assert row["reporting_partition"] == "core_only"
        assert row["official_proximity_review"] is False
        assert row["generation_input_field_names"] == [
            "generated_question_draft",
            "source_family",
        ]
        assert "expected_answer_draft" not in row
        assert "supporting_evidence_locator_draft" not in row
        assert row["generation_input_used_expected_answer_draft"] is False
        assert row["generation_input_used_supporting_evidence_locator_draft"] is False
        assert row["generation_input_used_gold_fields"] is False
        assert row["generation_input_used_official_fields"] is False
        assert row["generation_input_used_db_query_results"] is False
        assert row["generated_expected_answers_are_gold"] is False
        assert row["not_gold"] is True
        assert row["not_official_qrels"] is True
        assert row["not_official_denominator"] is True
        assert row["promotion_evidence"] is False
        assert row["references_used_for_generation"] is False
        assert row["references_used_for_official_metric"] is False

    for payload in (summary, runtime_summary, policy_audit, next_phase):
        assert payload["generated_expected_answers_are_gold"] is False
        assert payload["not_gold"] is True
        assert payload["not_official_qrels"] is True
        assert payload["not_official_denominator"] is True
        assert payload["promotion_evidence"] is False

    for payload in (summary, policy_audit):
        assert payload["official_metric"] is False
        assert payload["official_metric_denominator_usage_allowed"] is False
        assert payload["local_llm_live_silver_generation_allowed"] is False
        assert payload["local_llm_live_silver_generation_attempted"] is False
        assert payload["local_llm_metric_scoring_allowed"] is False
        assert payload["local_llm_metric_scoring_attempted"] is False
        assert payload["external_llm_api_allowed"] is False
        assert payload["external_llm_api_attempted"] is False
        assert payload["db_write_allowed"] is False
        assert payload["db_write_attempted"] is False
        assert payload["db_migration_allowed"] is False
        assert payload["db_migration_attempted"] is False
        assert payload["db_index_rebuild_allowed"] is False
        assert payload["db_index_rebuild_attempted"] is False
        assert payload["db_write_migration_reindex_attempted"] is False
        assert payload["production_db_usage_allowed"] is False
        assert payload["production_db_used"] is False
        assert payload["db_results_as_gold_allowed"] is False
        assert payload["db_results_as_official_qrels_allowed"] is False
        assert payload["db_results_as_generation_source_allowed"] is False
        assert payload["official_qrels_created"] is False
        assert payload["official_relevance_labels_created"] is False
        assert payload["official_answerability_labels_created"] is False
        assert payload["official_gold_labels_created"] is False
        assert payload["readme_performance_claim_mutation"] is False
        assert payload["threshold_tuning"] is False
        assert payload["winner_selection"] is False
        assert payload["prompt_mutation"] is False
        assert payload["retrieval_mutation"] is False
        assert payload["scorer_mutation"] is False
        assert payload["renderer_mutation"] is False
        assert payload["index_or_export_mutation"] is False
        assert payload["production_mutation"] is False

    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["protected_v3_6_3_input_sha256_before"] == summary["protected_v3_6_3_input_sha256_after"]
    assert summary["protected_v3_6_3_input_sha256_unchanged"] is True
    assert next_phase["recommended_next_phase"] in V3_6_7_RECOMMENDATION_CHOICES
    assert next_phase["choose_exactly_one_policy_satisfied"] is True
    assert summary["recommended_next_phase"] == next_phase["recommended_next_phase"]
    assert summary["v3_6_7_core_only_live_diagnostic_metric_allowed"] == next_phase[
        "v3_6_7_core_only_live_diagnostic_metric_allowed"
    ]


def test_v3_6_7_source_policy_validation_fails_closed_on_smoke_generation_input_leakage() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    smoke_rows = read_jsonl(V3_6_6_CORE_SMOKE_SAMPLE)
    leaked_field_rows = [dict(row) for row in smoke_rows]
    leaked_field_rows[0]["generation_input_field_names"] = [
        "generated_question_draft",
        "source_family",
        "expected_answer_draft",
    ]
    leaked_field_reasons = runner.v3_6_7_source_fail_closed_reasons(
        source_load_errors=[],
        v3_6_6_summary=read_json(V3_6_6_SUMMARY),
        v3_6_6_runtime_summary=read_json(V3_6_6_RUNTIME_PROBE_SUMMARY),
        v3_6_6_db_audit=read_json(V3_6_6_DB_RETRIEVAL_SURFACE_AUDIT),
        v3_6_6_policy=read_json(V3_6_6_POLICY_AUDIT),
        v3_6_6_next_phase=read_json(V3_6_6_NEXT_PHASE_RECOMMENDATION),
        sidecar_rows=read_jsonl(V3_6_6_REFERENCE_SIDECAR),
        baseline_smoke_rows=leaked_field_rows,
    )
    leaked_flag_rows = [dict(row) for row in smoke_rows]
    leaked_flag_rows[0]["generation_input_used_supporting_evidence_locator_draft"] = True
    leaked_flag_reasons = runner.v3_6_7_source_fail_closed_reasons(
        source_load_errors=[],
        v3_6_6_summary=read_json(V3_6_6_SUMMARY),
        v3_6_6_runtime_summary=read_json(V3_6_6_RUNTIME_PROBE_SUMMARY),
        v3_6_6_db_audit=read_json(V3_6_6_DB_RETRIEVAL_SURFACE_AUDIT),
        v3_6_6_policy=read_json(V3_6_6_POLICY_AUDIT),
        v3_6_6_next_phase=read_json(V3_6_6_NEXT_PHASE_RECOMMENDATION),
        sidecar_rows=read_jsonl(V3_6_6_REFERENCE_SIDECAR),
        baseline_smoke_rows=leaked_flag_rows,
    )

    assert "v3_6_6_core_smoke_generation_input_field_leakage" in leaked_field_reasons
    assert "v3_6_6_core_smoke_generation_input_policy_violation" in leaked_flag_reasons


def test_v3_6_8_nonprod_all_source_summary_locks_outcome_and_guardrails() -> None:
    summary = read_json(V3_6_8_SUMMARY)
    payload_contract = read_json(V3_6_8_PAYLOAD_CONTRACT_SUMMARY)
    failure_buckets = read_json(V3_6_8_FAILURE_BUCKETS)

    assert summary["run_id"] == V3_6_8_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_nonprod_all_source_index_materialization_and_canonical_payload_wiring"
    assert summary["run_class"] == "diagnostic_only_nonprod_all_source_index_materialization"
    assert set(summary["outcome_choices"]) == V3_6_8_OUTCOMES
    assert summary["outcome"] == "ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED"
    assert summary["next_allowed_phase"] == "v3_6_9_core_only_live_diagnostic_metric"
    assert summary["recommended_next_phase"] == summary["next_allowed_phase"]
    assert "manifest_locator" not in summary["recommended_next_phase"]
    assert summary["no_generic_probe_recommended"] is True
    assert summary["decision_output"]["generic_manifest_locator_probe_recommended"] is False
    assert summary["core_only_live_diagnostic_metric_allowed"] is True

    assert summary["diagnostic_only"] is True
    assert summary["implementation_allowed"] is True
    assert summary["implementation_scope"] == [
        "non_production_index_export_build",
        "non_production_searchunit_materialization",
        "canonical_citation_payload_serialization",
        "source_bound_locator_canonicalization",
        "retrieval_context_envelope_wiring",
        "load_check_and_retrieval_smoke",
    ]
    assert summary["index_or_export_mutation"] is True
    assert summary["index_or_export_mutation_scope"] == "non_production_only"
    assert summary["index_namespace"] == "rag-data-all-source-nonprod-v1"
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False

    for key in (
        "official_metric",
        "official_metric_denominator_usage_allowed",
        "answer_metric_computed",
        "citation_metric_computed",
        "answer_correctness_scored",
        "generated_expected_answers_are_gold",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "official_qrels_created",
        "official_relevance_labels_created",
        "official_answerability_labels_created",
        "official_gold_labels_created",
        "prompt_mutation",
        "retrieval_mutation",
        "scorer_mutation",
        "renderer_mutation",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
        "readme_representative_product_performance_claim",
        "lane_a_b_c_collapsed_scoring",
        "expected_answer_draft_used_as_retrieval_source",
        "expected_answer_draft_used_as_generation_input",
        "supporting_evidence_used_as_answer_text_source",
        "generated_silver_answers_used_as_source_material",
        "gold_fields_used_as_generation_input",
        "qrels_or_labels_used_as_generation_input",
    ):
        assert summary[key] is False, key

    assert summary["load_check"]["passed"] is True
    assert summary["load_check"]["canonical_payload_available_by_family"] == {
        "PDF": True,
        "TEXT": True,
        "XLSX": True,
    }
    assert summary["load_check"]["no_llm_citation_render_valid_by_family"] == {
        "PDF": True,
        "TEXT": True,
        "XLSX": True,
    }
    assert summary["payload_contract"]["canonicalizable_count"] == 136280
    assert summary["payload_contract"]["retrieval_only_uncanonicalized_count"] == 0
    assert sorted(summary["payload_contract"]["families_with_canonical_payload"]) == ["PDF", "TEXT", "XLSX"]
    assert sorted(summary["payload_contract"]["families_with_valid_no_llm_render"]) == ["PDF", "TEXT", "XLSX"]
    assert payload_contract["retrieval_only_uncanonicalized_generation_source_allowed_count"] == 0

    assert summary["retrieval_smoke"]["retrieval_result_count"] == 50
    assert summary["retrieval_smoke"]["canonical_payload_available_count"] == 50
    assert summary["retrieval_smoke"]["no_llm_citation_render_valid_count"] == 50
    assert summary["retrieval_smoke"]["payload_missing_bucket_counts"] == {}
    assert failure_buckets["blocking_buckets"] == []
    assert failure_buckets["failure_bucket_counts"]["ALL_SOURCE_NONPROD_INDEX_BUILT_AND_PAYLOAD_WIRED"] == 1


def test_v3_6_8_source_inventory_and_index_files_preserve_scope_and_exclusions() -> None:
    summary = read_json(V3_6_8_SUMMARY)
    source_inventory = read_json(V3_6_8_SOURCE_INVENTORY)
    index_source_inventory = read_json(V3_6_8_INDEX_SOURCE_INVENTORY)
    build_summary = read_json(V3_6_8_INDEX_BUILD_SUMMARY)
    build_json = read_json(V3_6_8_INDEX_BUILD)
    ingest_manifest = read_json(V3_6_8_INDEX_INGEST_MANIFEST)

    for path in (
        V3_6_8_INDEX_DIR / "faiss.index",
        V3_6_8_INDEX_BUILD,
        V3_6_8_INDEX_INGEST_MANIFEST,
        V3_6_8_INDEX_SEARCH_UNIT_MANIFEST,
        V3_6_8_INDEX_SOURCE_INVENTORY,
        V3_6_8_INDEX_PAYLOAD_CONTRACT,
    ):
        assert path.exists(), path

    line_count = sum(1 for line in V3_6_8_INDEX_SEARCH_UNIT_MANIFEST.read_text(encoding="utf-8").splitlines() if line)
    assert line_count == build_summary["search_unit_manifest_row_count"]
    assert line_count == summary["index_build"]["row_count"] == 136280
    assert build_summary["faiss_index_vector_count"] == line_count
    assert build_json["chunk_count"] == line_count
    assert build_json["index_namespace"] == "rag-data-all-source-nonprod-v1"
    assert build_json["dataset_scope"] == "all_eligible_existing_source_datasets_nonprod"
    assert build_json["non_production_only"] is True
    assert ingest_manifest["non_production_only"] is True
    assert ingest_manifest["source_unit_count"] == line_count

    assert source_inventory == index_source_inventory
    counts = source_inventory["counts"]
    assert counts["total_eligible_source_units_by_source_family"] == {
        "PDF": 329,
        "TEXT": 135958,
        "XLSX": 344,
        "total": 136631,
    }
    assert counts["accepted_source_units_by_source_family"] == {
        "PDF": 329,
        "TEXT": 135608,
        "XLSX": 343,
        "total": 136280,
    }
    assert counts["canonicalizable_count"] == line_count
    assert counts["retrieval_only_uncanonicalized_count"] == 0
    assert counts["official_overlap_count"] == 29
    assert counts["silver_source_overlap_count"] == 999
    assert counts["raw_corpus_count"] > 100000
    assert counts["v3_5_4_source_rows_represented"] + counts["v3_5_4_source_rows_blocked"] == 1000
    assert source_inventory["rejected_counts"]["by_reason"] == {"duplicate_search_unit_id": 351}

    exclusion_policy = source_inventory["exclusion_policy"]
    for key, value in exclusion_policy.items():
        assert value is False, key
    assert build_summary["non_production_only"] is True
    assert all(item["exists"] for item in build_summary["required_files"].values())


def test_v3_6_8_search_unit_manifest_has_namespace_split_and_canonical_payloads() -> None:
    required_fields = {
        "index_namespace",
        "dataset_scope",
        "source_family",
        "split_scope",
        "official_denominator_overlap",
        "silver_source_overlap",
        "review_only",
        "quarantine",
        "source_identity",
        "locator_fingerprint",
        "search_unit_id",
        "canonical_payload_status",
        "generation_source_allowed",
        "gold_or_label_source",
        "expected_answer_source",
        "canonical_citation_payload",
        "track_locator_payload",
    }
    family_examples: dict[str, dict[str, Any]] = {}
    family_counts = defaultdict(int)
    official_overlap_count = 0
    official_overlap_search_unit_ids: set[str] = set()
    retrieval_only_count = 0
    dataset_scopes = set()
    split_scopes = set()
    manifest_partitions = set()
    reporting_partitions = set()

    with V3_6_8_INDEX_SEARCH_UNIT_MANIFEST.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            assert required_fields <= set(row), row.get("search_unit_id")
            assert row["index_namespace"] == "rag-data-all-source-nonprod-v1"
            assert row["canonical_payload_status"] in {"canonicalizable", "retrieval_only_uncanonicalized"}
            assert row["gold_or_label_source"] is False
            assert row["expected_answer_source"] is False
            assert row["qrels_source"] is False
            assert row["generated_silver_answer_source"] is False
            assert row["metric_result_source"] is False
            assert row["report_artifact_source"] is False
            assert row["non_production_only"] is True
            assert row["promotion_evidence"] is False
            assert row["not_gold"] is True
            assert row["not_official_qrels"] is True
            assert row["source_identity"]
            assert row["locator_fingerprint"]
            assert row["search_unit_id"]

            family = row["source_family"]
            family_counts[family] += 1
            dataset_scopes.add(row["dataset_scope"])
            split_scopes.add(row["split_scope"])
            manifest_partitions.add(row["manifest_partition"])
            reporting_partitions.add(row["reporting_partition"])
            if row["official_denominator_overlap"]:
                official_overlap_count += 1
                official_overlap_search_unit_ids.add(row["search_unit_id"])
            generation_policy_allowed = (
                row["canonical_payload_status"] == "canonicalizable"
                and row["dataset_scope"] == "v3_5_4_balanced_source_only_manifest"
                and row["review_only"] is False
                and row["quarantine"] is False
                and row["official_denominator_overlap"] is False
                and row["raw_corpus_source"] is False
            )
            if row["canonical_payload_status"] == "retrieval_only_uncanonicalized":
                retrieval_only_count += 1
                assert row["generation_source_allowed"] is False
            else:
                assert row["canonical_payload_renderable"] is True
                assert row["generation_source_allowed"] is generation_policy_allowed
                family_examples.setdefault(family, row)

    assert dict(family_counts) == {"TEXT": 135608, "PDF": 329, "XLSX": 343}
    assert official_overlap_count == 29
    official_search_unit_ids = {row["search_unit_id"] for row in read_jsonl(SOURCE_BOUND_SEARCH_UNIT_MANIFEST)}
    assert official_overlap_search_unit_ids == official_search_unit_ids
    assert retrieval_only_count == 0
    assert set(family_examples) == {"TEXT", "PDF", "XLSX"}
    assert dataset_scopes == {
        "official_denominator_regression_smoke",
        "raw_text_corpus_namu_v4",
        "v3_5_4_balanced_source_only_manifest",
    }
    assert {
        "core_only",
        "review_only",
        "source_only",
        "weak_silver_exploration",
        "weak_silver_holdout",
        "weak_silver_stress_smoke_candidate",
        "official_denominator_regression_smoke",
        "raw_corpus_unlabeled",
    } >= split_scopes
    assert {"core", "review_only", "source_only", "official_denominator", "raw_corpus"} >= manifest_partitions
    assert {
        "core_only",
        "review_only_challenge",
        "official_denominator_regression_smoke",
        "raw_corpus_recall_smoke_only",
    } >= reporting_partitions

    text_locator = family_examples["TEXT"]["track_locator_payload"]
    assert text_locator["document_id"]
    assert text_locator["chunk_id"]
    assert text_locator["text_locator"]
    assert family_examples["TEXT"]["canonical_citation_payload"]["source_identity"]

    pdf_locator = family_examples["PDF"]["track_locator_payload"]
    assert pdf_locator["source_pdf_path"]
    assert pdf_locator["document_version_id"]
    assert pdf_locator["page"] is not None
    assert pdf_locator["physical_page_index"] is not None
    assert pdf_locator["bbox"]
    assert pdf_locator["region_type"]

    xlsx_locator = family_examples["XLSX"]["track_locator_payload"]
    assert xlsx_locator["workbook"]
    assert xlsx_locator["sheet"]
    assert xlsx_locator["range"] or xlsx_locator["cell"]


def test_v3_6_8_retrieval_smoke_exposes_compact_canonical_envelopes_only() -> None:
    summary = read_json(V3_6_8_SUMMARY)
    rows = read_jsonl(V3_6_8_RETRIEVAL_SMOKE_DIAGNOSTICS)

    assert len(rows) == summary["retrieval_smoke"]["row_count"] == 10
    assert {row["source_family"] for row in rows} >= {"TEXT", "PDF", "XLSX"}
    for row in rows:
        assert row["run_id"] == V3_6_8_RUN_ID
        assert row["retrieval_result_count"] == len(row["top_result_envelopes"]) == 5
        assert row["canonical_payload_available_count"] == 5
        assert row["no_llm_citation_render_valid_count"] == 5
        assert row["primary_failure_bucket"] == ""
        assert row["expected_answer_draft_used_as_retrieval_source"] is False
        assert row["expected_answer_draft_used_as_generation_input"] is False
        assert row["answer_metric_computed"] is False
        assert row["citation_metric_computed"] is False
        assert row["promotion_evidence"] is False
        for envelope in row["top_result_envelopes"]:
            assert envelope["search_unit_id"]
            assert envelope["source_identity"]
            assert envelope["locator_fingerprint"]
            assert envelope["canonical_payload_status"] == "canonicalizable"
            assert envelope["canonical_citation_payload_present"] is True
            assert envelope["track_locator_payload_present"] is True
            assert isinstance(envelope["generation_source_allowed"], bool)
            assert "display_text" not in envelope
            assert "embedding_text" not in envelope
            assert "canonical_citation_payload" not in envelope


def test_v3_6_8_no_llm_render_helper_and_retrieval_only_guardrail() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    examples: dict[str, dict[str, Any]] = {}
    with V3_6_8_INDEX_SEARCH_UNIT_MANIFEST.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(examples) == 3:
                break
            row = json.loads(line)
            if row.get("canonical_payload_status") == "canonicalizable":
                examples.setdefault(row["source_family"], row["canonical_citation_payload"])

    assert set(examples) == {"TEXT", "PDF", "XLSX"}
    for family, payload in examples.items():
        rendered = runner.v3_6_8_all_source_render_citation(payload)
        assert rendered["valid"] is True, family
        assert rendered["citation"]["source_family"] == family
        assert rendered["citation"]["source_identity"]
        assert rendered["citation"]["locator_fingerprint"]
        assert rendered["citation"]["search_unit_id"]

    retrieval_only = runner.v3_6_8_all_source_finalize_unit(
        generated_at="2026-05-20T00:00:00+00:00",
        dataset_scope="unit_test",
        source_class="unit_test",
        source_unit_id="unit_test_missing_payload",
        source_family="PDF",
        source_identity="",
        locator_fingerprint="fp",
        search_unit_id="su",
        document_version_id="docv",
        source_locator={},
        track_locator={},
        canonical_payload={"source_family": "PDF", "search_unit_id": "su"},
        source_text="source text",
        split_scope="unit_test",
        manifest_partition="unit_test",
        reporting_partition="unit_test",
        review_only=False,
        quarantine=False,
        official_denominator_overlap=False,
        silver_source_overlap=False,
        raw_corpus_source=False,
        external_archive_source=False,
        upstream_artifact="unit_test",
    )
    assert retrieval_only["canonical_payload_status"] == "retrieval_only_uncanonicalized"
    assert retrieval_only["generation_source_allowed"] is False
    assert "source_identity" in retrieval_only["canonical_payload_missing_fields"]
    assert "track_locator_payload" in retrieval_only["canonical_payload_missing_fields"]
    payload_contract = runner.v3_6_8_all_source_payload_contract_summary(
        generated_at="2026-05-20T00:00:00+00:00",
        manifest_rows=[retrieval_only],
        retrieval_smoke_rows=[],
    )
    failure_buckets = runner.v3_6_8_all_source_failure_buckets(
        generated_at="2026-05-20T00:00:00+00:00",
        source_inventory={
            "rejected_counts": {
                "by_reason": {"forbidden_generation_or_label_field_present": 1},
                "total": 1,
            }
        },
        build_summary={"index_path": "unit_test"},
        load_check={
            "index_can_be_loaded": True,
            "required_files_present": True,
            "missing_required_files": [],
            "no_expected_answer_gold_qrels_report_artifact_indexed": True,
            "official_29_rows_remain_protected_and_identifiable": True,
            "v3_5_4_source_rows_unaccounted": 0,
            "passed": True,
        },
        payload_contract_summary=payload_contract,
        retrieval_smoke_rows=[],
        fail_closed_reasons=[],
    )
    decision = runner.v3_6_8_all_source_exit_decision(
        load_check={
            "index_can_be_loaded": True,
            "required_files_present": True,
            "passed": True,
        },
        payload_contract_summary=payload_contract,
        failure_buckets=failure_buckets,
        fail_closed_reasons=[],
    )
    assert payload_contract["retrieval_only_uncanonicalized_count"] == 1
    assert payload_contract["retrieval_only_uncanonicalized_generation_source_allowed_count"] == 0
    assert failure_buckets["failure_bucket_counts"]["RETRIEVAL_ONLY_UNCANONICALIZED"] == 1
    assert failure_buckets["failure_bucket_counts"]["SOURCE_UNIT_REJECTED_FOR_FORBIDDEN_FIELD"] == 1
    assert decision["outcome"] == "ALL_SOURCE_INDEX_BUILT_PAYLOAD_PARTIAL"
    assert decision["next_allowed_phase"] == "targeted_canonicalization_repair"


def test_v3_6_8_rejects_v3_5_4_rows_with_forbidden_generation_or_label_fields() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    row = {
        "candidate_id": "forbidden-text-row",
        "source_family": "TEXT",
        "source_identity": "TEXT:docv:su:fp",
        "locator_fingerprint": "fp",
        "search_unit_id": "su",
        "document_version_id": "docv",
        "source_bound_locator": {
            "doc_id": "doc",
            "chunk_id": "chunk",
            "source_corpus_path": "corpus.jsonl",
        },
        "canonical_citation_payload": {
            "source_family": "TEXT",
            "document_id": "doc",
            "document_version_id": "docv",
            "search_unit_id": "su",
            "text_locator": {
                "doc_id": "doc",
                "chunk_id": "chunk",
                "source_corpus_path": "corpus.jsonl",
            },
        },
        "source_text": "source text",
        "expected_answers_created": True,
        "promotion_evidence": False,
    }

    assert runner.v3_6_8_all_source_forbidden_source_fields(row) == ["expected_answers_created"]
    unit = runner.v3_6_8_all_source_unit_from_v3_5_4_row(
        row,
        manifest_row={"split_role": "core_only", "manifest_partition": "core"},
        sidecar_row={"reporting_partition": "core_only"},
        generated_at="2026-05-20T00:00:00+00:00",
    )
    assert "forbidden_generation_or_label_field_present" in unit["source_rejection_reasons"]
    assert unit["gold_or_label_source"] is False
    assert unit["expected_answer_source"] is False


def test_v3_6_8_source_registry_audit_summary_locks_source_first_policy_and_exit() -> None:
    summary = read_json(V3_6_8_SOURCE_REGISTRY_SUMMARY)
    source_object_audit = read_json(V3_6_8_SOURCE_REGISTRY_SOURCE_OBJECT_AUDIT)
    searchunit_role_audit = read_json(V3_6_8_SOURCE_REGISTRY_SEARCHUNIT_ROLE_AUDIT)
    evidence_contract = read_json(V3_6_8_SOURCE_REGISTRY_EVIDENCE_BUNDLE_CONTRACT)
    routing_audit = read_json(V3_6_8_SOURCE_REGISTRY_TRACK_ROUTING_AUDIT)
    failure_buckets = read_json(V3_6_8_SOURCE_REGISTRY_FAILURE_BUCKETS)

    assert summary["run_id"] == V3_6_8_SOURCE_REGISTRY_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_source_registry_first_evidence_bundle_architecture_audit"
    assert summary["run_class"] == "diagnostic_only_source_registry_first_architecture_audit"
    assert summary["diagnostic_only"] is True
    assert summary["implementation_allowed"] is True
    assert summary["index_or_export_mutation"] is False
    assert summary["vector_db_source_of_truth_allowed"] is False
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert set(summary["outcome_choices"]) == V3_6_8_SOURCE_REGISTRY_OUTCOMES
    assert summary["outcome"] == "SEARCHUNIT_OVERLOADED_BLOCKER"
    assert summary["next_allowed_phase"] == "SearchUnit/SearchView/SourceAtom refactor"
    assert summary["recommended_next_phase"] == summary["next_allowed_phase"]
    assert summary["no_generic_probe_recommended"] is True
    assert "manifest_locator" not in summary["recommended_next_phase"]

    for key in (
        "official_metric",
        "answer_metric_computed",
        "citation_metric_computed",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "official_qrels_created",
        "official_relevance_labels_created",
        "official_answerability_labels_created",
        "official_gold_labels_created",
        "expected_answer_draft_used_as_generation_input",
        "silver_expected_answer_used_as_generation_input",
        "silver_evidence_locator_used_as_retrieval_shortcut",
        "query_id_specific_evidence_patch",
        "file_name_specific_evidence_patch",
        "prompt_mutation",
        "retrieval_ranking_mutation",
        "scorer_mutation",
        "threshold_tuning",
        "winner_selection",
        "readme_representative_product_performance_claim",
        "lane_a_b_c_collapsed_scoring",
        "production_db_used",
        "db_write_attempted",
        "db_migration_attempted",
        "production_mutation",
    ):
        assert summary[key] is False, key

    assert searchunit_role_audit["searchunit_overloaded"] is True
    assert searchunit_role_audit["roles_observed"] == {
        "retrieval_unit": True,
        "source_atom": True,
        "citation_unit": True,
        "answer_evidence_unit": True,
        "metric_qrels_unit": True,
        "llm_context_unit": True,
    }
    assert searchunit_role_audit["primary_blocker"] == "SEARCHUNIT_OVERLOADED_BLOCKER"
    assert searchunit_role_audit["next_phase"] == summary["next_allowed_phase"]

    assert source_object_audit["classification_counts"]["raw_source_derived"] > 0
    assert source_object_audit["classification_counts"]["extraction_snapshot_derived"] > 0
    assert source_object_audit["classification_counts"]["retrieval_hit_derived"] > 0
    assert source_object_audit["classification_counts"]["query_manifest_derived"] > 0
    assert source_object_audit["classification_counts"]["eval_artifact_derived"] > 0
    assert source_object_audit["classification_counts"]["silver_or_gold_derived"] > 0
    assert source_object_audit["anti_overfit_audit"]["query_id_specific_evidence_patch_count"] == 0
    assert source_object_audit["anti_overfit_audit"]["file_name_specific_evidence_patch_count"] == 0
    assert source_object_audit["anti_overfit_audit"]["silver_expected_answer_used_as_generation_input"] is False
    assert source_object_audit["anti_overfit_audit"]["silver_evidence_locator_used_as_retrieval_shortcut"] is False

    assert evidence_contract["source_atom_schema"]["required_fields"] == [
        "source_atom_id",
        "source_family",
        "source_identity",
        "document_id_or_workbook_id",
        "document_version_id_or_workbook_version_id",
        "content_hash",
        "extraction_version",
        "raw_locator",
        "normalized_text_or_value_snapshot",
        "parent_pointers",
        "canonical_citation_payload",
    ]
    assert evidence_contract["search_view_contract"]["must_point_to_source_atoms"] is True
    assert evidence_contract["vector_db_contract"]["candidate_generator_only"] is True
    assert evidence_contract["policy_modes"] == ["official_evidence", "runtime_evidence", "diagnostic_evidence"]
    assert evidence_contract["no_vector_checks"]["hydrate_canonical_payload_from_source_atom_id"] is True
    assert evidence_contract["no_vector_checks"]["render_citation_from_source_atom_id"] is True
    assert evidence_contract["no_vector_checks"]["assemble_evidence_bundle_from_source_atom_id"] is True
    assert evidence_contract["no_vector_checks"]["check_source"] == "executed_no_vector_source_atom_matrix"
    assert summary["no_vector_check_results"]["executed"] is True
    assert summary["no_vector_check_results"]["families_passed"] == ["PDF", "TEXT", "XLSX"]

    assert routing_audit["track_routing_overfit_blocker"] is False
    assert routing_audit["source_family_generic_evidence_assembly"] is True
    assert routing_audit["final_comparison_by_evidence_completeness_required"] is True
    assert routing_audit["undifferentiated_score_pool_risk"] is True
    assert failure_buckets["blocking_buckets"] == ["SEARCHUNIT_OVERLOADED_BLOCKER"]
    assert failure_buckets["secondary_blocking_buckets"] == ["SOURCE_REGISTRY_MISSING_BLOCKER"]
    assert failure_buckets["blocking_bucket_rationale"] == (
        "SOURCE_REGISTRY_MISSING_BLOCKER is recorded as a secondary blocker because "
        "SEARCHUNIT_OVERLOADED_BLOCKER must be repaired first; materializing SourceAtom rows before "
        "SearchUnit/SearchView separation would preserve the overload."
    )
    assert failure_buckets["failure_bucket_counts"]["SEARCHUNIT_OVERLOADED_BLOCKER"] == 1


def test_v3_6_8_source_atom_no_vector_hydration_render_and_evidence_bundle_helpers() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    atoms = {
        "TEXT": {
            "source_atom_id": "atom-text",
            "source_family": "TEXT",
            "source_identity": "TEXT:doc-text:v1:span-1",
            "document_id": "doc-text",
            "document_version_id": "doc-text-v1",
            "content_hash": "hash-text",
            "extraction_version": "unit-test",
            "raw_locator": {"document_id": "doc-text", "chunk_id": "chunk-1", "text_span": "0:12"},
            "normalized_text_or_value_snapshot": "text snapshot",
            "parent_pointers": {"search_view_ids": ["view-text"]},
            "canonical_citation_payload": {
                "source_family": "TEXT",
                "source_identity": "TEXT:doc-text:v1:span-1",
                "locator_fingerprint": "fp-text",
                "search_unit_id": "su-text",
                "document_id": "doc-text",
                "document_version_id": "doc-text-v1",
                "text_locator": {"document_id": "doc-text", "chunk_id": "chunk-1", "text_span": "0:12"},
            },
        },
        "PDF": {
            "source_atom_id": "atom-pdf",
            "source_family": "PDF",
            "source_identity": "PDF:doc-pdf:v1:p1:b1",
            "document_id": "doc-pdf",
            "document_version_id": "doc-pdf-v1",
            "content_hash": "hash-pdf",
            "extraction_version": "unit-test",
            "raw_locator": {
                "source_pdf_path": "docs/source.pdf",
                "page": 1,
                "physical_page_index": 0,
                "bbox": [1.0, 2.0, 3.0, 4.0],
                "region_type": "paragraph",
            },
            "normalized_text_or_value_snapshot": "pdf snapshot",
            "parent_pointers": {"search_view_ids": ["view-pdf"]},
            "canonical_citation_payload": {
                "source_family": "PDF",
                "source_identity": "PDF:doc-pdf:v1:p1:b1",
                "locator_fingerprint": "fp-pdf",
                "search_unit_id": "su-pdf",
                "document_version_id": "doc-pdf-v1",
                "source_pdf_path": "docs/source.pdf",
                "page": 1,
                "physical_page_index": 0,
                "bbox": [1.0, 2.0, 3.0, 4.0],
                "region_type": "paragraph",
            },
        },
        "XLSX": {
            "source_atom_id": "atom-xlsx",
            "source_family": "XLSX",
            "source_identity": "XLSX:book:v1:Sheet1!A1",
            "workbook_id": "book",
            "workbook_version_id": "book-v1",
            "content_hash": "hash-xlsx",
            "extraction_version": "unit-test",
            "raw_locator": {"workbook": "book.xlsx", "sheet": "Sheet1", "cell": "A1", "row_label": "row"},
            "normalized_text_or_value_snapshot": "xlsx snapshot",
            "parent_pointers": {"search_view_ids": ["view-xlsx"]},
            "canonical_citation_payload": {
                "source_family": "XLSX",
                "source_identity": "XLSX:book:v1:Sheet1!A1",
                "locator_fingerprint": "fp-xlsx",
                "search_unit_id": "su-xlsx",
                "workbook": "book.xlsx",
                "sheet": "Sheet1",
                "cell": "A1",
                "row_label": "row",
                "target_column": "value",
            },
        },
    }

    registry = {}
    for family, atom in atoms.items():
        validation = runner.v3_6_8_source_registry_validate_source_atom(atom)
        assert validation["valid"] is True, family
        registry[atom["source_atom_id"]] = atom
        payload = runner.v3_6_8_source_registry_hydrate_canonical_payload(
            atom["source_atom_id"],
            source_registry=registry,
        )
        rendered = runner.v3_6_8_source_registry_render_citation(
            atom["source_atom_id"],
            source_registry=registry,
        )
        bundle = runner.v3_6_8_source_registry_assemble_evidence_bundle(
            atom["source_atom_id"],
            source_registry=registry,
            mode="runtime_evidence",
        )
        assert payload["valid"] is True
        assert payload["payload"]["source_family"] == family
        assert rendered["valid"] is True
        assert rendered["citation"]["source_family"] == family
        assert bundle["valid"] is True
        assert bundle["evidence_bundle"]["source_atom_id"] == atom["source_atom_id"]
        assert bundle["evidence_bundle"]["source_family"] == family
        assert bundle["evidence_bundle"]["canonical_payload_source"] == "source_registry"
        if family == "TEXT":
            assert {
                "source_document_id_or_path",
                "section_chunk_span_identity",
                "text_span",
                "parent_paragraph_or_section",
                "nearby_context",
            } <= set(bundle["evidence_bundle"]["text_evidence"])
        if family == "PDF":
            assert {
                "source_pdf_path",
                "document_version_id",
                "page",
                "physical_page_index",
                "bbox",
                "region_type",
                "matched_text",
                "nearby_paragraph_or_window",
                "section_heading",
                "ocr_confidence",
            } <= set(bundle["evidence_bundle"]["pdf_evidence"])
        if family == "XLSX":
            assert {
                "workbook_or_source_path",
                "sheet",
                "table_or_range",
                "matched_cells",
                "row_or_column_labels",
                "nearby_row_or_range_context",
                "value_locator",
            } <= set(bundle["evidence_bundle"]["xlsx_evidence"])

    official_missing_raw = runner.v3_6_8_source_registry_assemble_evidence_bundle(
        "atom-text",
        source_registry=registry,
        mode="official_evidence",
    )
    assert official_missing_raw["valid"] is True
    assert official_missing_raw["evidence_bundle"]["official_evidence_allowed"] is False
    assert official_missing_raw["evidence_bundle"]["runtime_answer_allowed"] is True
    assert official_missing_raw["evidence_bundle"]["diagnostic_only_reason"] == (
        "raw_file_missing_extraction_snapshot_present"
    )

    official_ready_atom = dict(atoms["TEXT"])
    official_ready_atom["source_atom_id"] = "atom-text-official"
    official_ready_atom["raw_file_exists"] = True
    official_ready_atom["extraction_snapshot_present"] = True
    official_ready_registry = {"atom-text-official": official_ready_atom}
    official_ready = runner.v3_6_8_source_registry_assemble_evidence_bundle(
        "atom-text-official",
        source_registry=official_ready_registry,
        mode="official_evidence",
    )
    assert official_ready["valid"] is True
    assert official_ready["evidence_bundle"]["official_evidence_allowed"] is True

    snapshot_only = runner.v3_6_8_source_registry_hydration_policy(
        raw_file_exists=False,
        extraction_snapshot_present=True,
    )
    assert snapshot_only["hydration_allowed"] is True
    assert snapshot_only["official_evidence_allowed"] is False
    assert snapshot_only["runtime_answer_allowed"] is True
    assert snapshot_only["diagnostic_only_reason"] == "raw_file_missing_extraction_snapshot_present"

    missing_all = runner.v3_6_8_source_registry_hydration_policy(
        raw_file_exists=False,
        extraction_snapshot_present=False,
    )
    assert missing_all["hydration_allowed"] is False
    assert missing_all["fail_closed"] is True
    assert missing_all["failure_bucket"] == "SOURCE_REGISTRY_MISSING_BLOCKER"

    hit = {
        "search_view_id": "view-text",
        "source_atom_ids": ["atom-text"],
        "canonical_citation_payload": {"source_family": "TEXT", "source_identity": "vector-owned"},
    }
    from_hit = runner.v3_6_8_source_registry_evidence_bundle_from_vector_hit(hit, source_registry=registry)
    assert from_hit["valid"] is True
    assert from_hit["evidence_bundle"]["source_atom_id"] == "atom-text"
    assert from_hit["evidence_bundle"]["canonical_payload_source"] == "source_registry"
    assert from_hit["vector_payload_used_as_evidence_truth"] is False

    chunk_only = runner.v3_6_8_source_registry_evidence_bundle_from_vector_hit(
        {"chunk_id": "chunk-only", "display_text": "not enough"},
        source_registry=registry,
    )
    assert chunk_only["valid"] is False
    assert chunk_only["failure_bucket"] == "RETRIEVAL_RESULT_CHUNK_ONLY_NOT_SEARCHUNIT"


def test_v3_6_9_source_atom_search_view_contract_hydrates_evidence_without_vector_truth() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag.source_registry import (
        assemble_evidence_bundle,
        evidence_bundle_from_search_view,
        hydrate_canonical_citation_payload,
        render_citation,
        validate_search_view,
        validate_source_atom,
    )

    registry = {
        "atom-text": {
            "source_atom_id": "atom-text",
            "source_family": "TEXT",
            "source_identity": "TEXT:doc-text:v1:span-1",
            "document_id": "doc-text",
            "document_version_id": "doc-text-v1",
            "content_hash": "hash-text",
            "extraction_version": "unit-test",
            "raw_file_exists": True,
            "extraction_snapshot_present": True,
            "raw_locator": {"document_id": "doc-text", "chunk_id": "chunk-1", "text_span": "0:12"},
            "normalized_text_or_value_snapshot": "text snapshot",
            "parent_pointers": {"search_view_ids": ["view-text"]},
            "canonical_citation_payload": {
                "source_family": "TEXT",
                "source_identity": "TEXT:doc-text:v1:span-1",
                "locator_fingerprint": "fp-text",
                "search_unit_id": "su-text",
                "document_id": "doc-text",
                "document_version_id": "doc-text-v1",
                "text_locator": {"document_id": "doc-text", "chunk_id": "chunk-1", "text_span": "0:12"},
            },
        }
    }
    vector_owned_payload = {
        "source_family": "TEXT",
        "source_identity": "TEXT:vector-owned",
        "locator_fingerprint": "fp-vector-owned",
        "search_unit_id": "su-vector-owned",
    }
    search_view = {
        "search_view_id": "view-text",
        "search_view_kind": "dense_embedding_chunk",
        "source_atom_ids": ["atom-text"],
        "embedding_text": "retrieval-only candidate text",
        "canonical_citation_payload": vector_owned_payload,
    }

    assert validate_source_atom(registry["atom-text"])["valid"] is True
    assert validate_search_view(search_view)["valid"] is True
    payload = hydrate_canonical_citation_payload("atom-text", source_registry=registry)
    rendered = render_citation("atom-text", source_registry=registry)
    bundle = assemble_evidence_bundle("atom-text", source_registry=registry, mode="runtime_evidence")
    from_view = evidence_bundle_from_search_view(search_view, source_registry=registry)

    assert payload["valid"] is True
    assert payload["payload"]["source_identity"] == "TEXT:doc-text:v1:span-1"
    assert rendered["valid"] is True
    assert bundle["valid"] is True
    assert from_view["valid"] is True
    assert from_view["source_atom_hydrated_from_registry"] is True
    assert from_view["vector_payload_used_as_evidence_truth"] is False
    assert from_view["ignored_vector_canonical_payload"] is True
    assert from_view["evidence_bundle"]["search_view_id"] == "view-text"
    assert from_view["evidence_bundle"]["source_atom_id"] == "atom-text"
    assert from_view["evidence_bundle"]["canonical_payload_source"] == "source_registry"
    assert from_view["evidence_bundle"]["citation"]["source_identity"] == "TEXT:doc-text:v1:span-1"
    assert from_view["evidence_bundle"]["citation"]["source_identity"] != "TEXT:vector-owned"

    chunk_only = evidence_bundle_from_search_view(
        {"search_view_id": "chunk-view", "chunk_id": "chunk-only", "embedding_text": "no source atom"},
        source_registry=registry,
    )
    assert chunk_only["valid"] is False
    assert chunk_only["failure_bucket"] == "RETRIEVAL_RESULT_CHUNK_ONLY_NOT_SEARCHUNIT"

    missing_atom = evidence_bundle_from_search_view(
        {"search_view_id": "view-missing", "source_atom_ids": ["atom-missing"]},
        source_registry=registry,
    )
    assert missing_atom["valid"] is False
    assert missing_atom["failure_bucket"] == "VECTOR_HIT_SOURCE_ATOM_MISSING"


def test_v3_6_9_retrieval_context_payload_exposes_search_view_and_source_atom_refs() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag.generation import RetrievedChunk
    from app.capabilities.rag.retrieval_contract import citation_payload

    citation = citation_payload(
        RetrievedChunk(
            chunk_id="chunk-text",
            doc_id="source-file-text",
            section="section",
            text="text",
            score=0.9,
            search_unit_id="su-text",
            metadata_json={
                "search_view_id": "view-text",
                "search_view_kind": "dense_embedding_chunk",
                "source_atom_id": "atom-text",
                "source_atom_ids": ["atom-text"],
                "source_registry_version": "source-registry-v1",
                "canonical_payload_source": "source_registry",
                "source_identity": "TEXT:doc-text:v1:span-1",
                "locator_fingerprint": "fp-text",
                "canonical_citation_payload": {
                    "source_family": "TEXT",
                    "source_identity": "TEXT:doc-text:v1:span-1",
                    "locator_fingerprint": "fp-text",
                    "search_unit_id": "su-text",
                },
            },
        )
    )

    assert citation["searchViewId"] == "view-text"
    assert citation["search_view_id"] == "view-text"
    assert citation["searchViewKind"] == "dense_embedding_chunk"
    assert citation["sourceAtomId"] == "atom-text"
    assert citation["source_atom_id"] == "atom-text"
    assert citation["sourceAtomIds"] == ["atom-text"]
    assert citation["source_atom_ids"] == ["atom-text"]
    assert citation["sourceRegistryVersion"] == "source-registry-v1"
    assert citation["sourceRegistryHydrationRequired"] is True
    assert citation["sourceAtomHydratedFromRegistry"] is False
    assert citation["vectorPayloadUsedAsEvidenceTruth"] is False
    assert citation["canonicalPayloadSource"] == "source_registry_hydration_required"
    assert citation["source_identity"] is None
    assert citation["locator_fingerprint"] is None
    assert citation["canonical_citation_payload"] is None
    assert citation["candidateSourceIdentity"] == "TEXT:doc-text:v1:span-1"
    assert citation["candidateLocatorFingerprint"] == "fp-text"
    assert citation["candidateCanonicalCitationPayload"]["search_unit_id"] == "su-text"


def test_rag_query_orchestrator_can_use_injected_retriever_vector_tools() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from types import SimpleNamespace

    from app.capabilities.rag.generation import RetrievedChunk
    from app.capabilities.rag_orchestrator.evidence import QueryPolicy
    from app.capabilities.rag_orchestrator.graph import run_query_orchestrator_pure

    class FakeRetriever:
        _top_k = 1
        _candidate_k = 1

        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []
            self.top_k_during_call: int | None = None
            self.candidate_k_during_call: int | None = None

        def retrieve(self, query: str, filters: Any = None) -> Any:
            self.top_k_during_call = self._top_k
            self.candidate_k_during_call = self._candidate_k
            self.calls.append({"query": query, "filters": filters})
            return SimpleNamespace(
                query=query,
                top_k=1,
                index_version="idx-v1",
                embedding_model="fake-embedding",
                results=[
                    RetrievedChunk(
                        chunk_id="chunk-xlsx-1",
                        doc_id="doc-xlsx-1",
                        section="Sheet1",
                        text="Sheet1 A2:B2 매출 합계 42",
                        score=0.91,
                        search_unit_id="su-xlsx-1",
                        source_file_id="source-xlsx-1",
                        source_file_name="book.xlsx",
                        metadata_json={
                            "sourceFileType": "SPREADSHEET",
                            "parserVersion": "xlsx-extract-v2-hidden-safe",
                            "embeddingStatus": "EMBEDDED",
                            "indexVersion": "idx-v1",
                            "citationText": "Sheet1 A2:B2 매출 합계 42",
                            "sheetName": "Sheet1",
                            "cellRange": "A2:B2",
                            "documentVersionId": "docv-xlsx-1",
                        },
                    )
                ],
            )

    retriever = FakeRetriever()
    state = run_query_orchestrator_pure(
        query="xlsx 매출 합계",
        policy=QueryPolicy(
            request_id="req-xlsx",
            required_index_version="idx-v1",
            allowed_source_file_types=["SPREADSHEET"],
            allowed_parser_versions=["xlsx-extract-v2-hidden-safe"],
            top_k=1,
        ),
        retriever=retriever,
    )

    assert retriever.calls == [{"query": "xlsx 매출 합계", "filters": None}]
    assert retriever.top_k_during_call == 5
    assert retriever.candidate_k_during_call == 5
    assert retriever._top_k == 1
    assert retriever._candidate_k == 1
    assert state["tool_results"][0].tool == "xlsx_vector_search_tool"
    backend_identity = state["tool_results"][0].backend_identity
    assert backend_identity["backend"] == "faiss"
    assert backend_identity["poc_wrapper"] is True
    assert backend_identity["post_filter_applied"] is True
    assert backend_identity["library_search_used"] is False
    assert backend_identity["production_filter_enforcement"] is False
    assert state["verified_evidence"][0].search_unit_id == "su-xlsx-1"
    assert state["answer"]["status"] == "stub"
    assert any(item["node"] == "run_selected_vector_tools" for item in state["trace"])
    route_diagnostic = state["route_diagnostics"][0]
    assert route_diagnostic["diagnostic_only"] is True
    assert route_diagnostic["production_vector_written"] is False
    assert route_diagnostic["production_namespace_mutated"] is False
    assert route_diagnostic["official_denominator_registry_changed"] is False


def test_rag_query_orchestrator_capability_marks_injected_retriever_backend() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from types import SimpleNamespace

    from app.capabilities.base import (
        CapabilityError,
        CapabilityInput,
        CapabilityInputArtifact,
    )
    from app.capabilities.rag.generation import RetrievedChunk
    from app.capabilities.rag_orchestrator.capability import (
        RagQueryOrchestratorCapability,
        RagQueryOrchestratorCapabilityConfig,
    )

    class FakeRetriever:
        _top_k = 1
        _candidate_k = 1

        def retrieve(self, query: str, filters: Any = None) -> Any:
            return SimpleNamespace(
                query=query,
                top_k=1,
                index_version="idx-v1",
                embedding_model="fake-embedding",
                results=[
                    RetrievedChunk(
                        chunk_id="chunk-xlsx-1",
                        doc_id="doc-xlsx-1",
                        section="Sheet1",
                        text="Sheet1 A2:B2 매출 합계 42",
                        score=0.91,
                        search_unit_id="su-xlsx-1",
                        source_file_id="source-xlsx-1",
                        source_file_name="book.xlsx",
                        metadata_json={
                            "sourceFileType": "SPREADSHEET",
                            "parserVersion": "xlsx-extract-v2-hidden-safe",
                            "embeddingStatus": "EMBEDDED",
                            "indexVersion": "idx-v1",
                            "citationText": "Sheet1 A2:B2 매출 합계 42",
                            "sheetName": "Sheet1",
                            "cellRange": "A2:B2",
                            "documentVersionId": "docv-xlsx-1",
                        },
                    )
                ],
            )

    capability = RagQueryOrchestratorCapability(
        config=RagQueryOrchestratorCapabilityConfig(enabled=True),
        retriever=FakeRetriever(),
    )
    request = {
        "query": "xlsx 매출 합계",
        "policy": {
            "requiredIndexVersion": "idx-v1",
            "allowedSourceFileTypes": ["SPREADSHEET"],
            "allowedParserVersions": ["xlsx-extract-v2-hidden-safe"],
            "topK": 1,
        },
    }

    output = capability.run(
        CapabilityInput(
            job_id="job-xlsx",
            capability="RAG_QUERY_ORCHESTRATOR",
            attempt_no=1,
            inputs=[
                CapabilityInputArtifact(
                    artifact_id="input-json",
                    type="INPUT_JSON",
                    content=json.dumps(request).encode("utf-8"),
                )
            ],
        )
    )

    payload = json.loads(output.outputs[0].content.decode("utf-8"))
    assert payload["graph_backend"] == "pure_vector_retriever_poc"
    assert payload["runtime_endpoint"] is False
    assert payload["langchain_used"] is False
    assert "vector_retriever" not in payload["state"]
    assert payload["state"]["tool_results"][0]["tool"] == "xlsx_vector_search_tool"
    backend_identity = payload["state"]["tool_results"][0]["backend_identity"]
    assert backend_identity["backend"] == "faiss"
    assert backend_identity["library_search_used"] is False
    assert backend_identity["production_filter_enforcement"] is False

    production_request = dict(request)
    production_request["mode"] = "production"
    with pytest.raises(CapabilityError) as exc:
        capability.run(
            CapabilityInput(
                job_id="job-xlsx-prod",
                capability="RAG_QUERY_ORCHESTRATOR",
                attempt_no=1,
                inputs=[
                    CapabilityInputArtifact(
                        artifact_id="input-json",
                        type="INPUT_JSON",
                        content=json.dumps(production_request).encode("utf-8"),
                    )
                ],
            )
        )
    assert exc.value.code == "RAG_QUERY_ORCHESTRATOR_PRODUCTION_CONTEXT_REQUIRED"


def test_rag_query_orchestrator_retriever_path_rejects_off_track_and_policy_mismatch_chunks() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from types import SimpleNamespace

    from app.capabilities.rag.generation import RetrievedChunk
    from app.capabilities.rag_orchestrator.evidence import QueryPolicy
    from app.capabilities.rag_orchestrator.graph import run_query_orchestrator_pure

    def chunk(
        *,
        chunk_id: str,
        source_file_type: str,
        index_version: str = "idx-v1",
        parser_version: str = "xlsx-extract-v2-hidden-safe",
    ) -> RetrievedChunk:
        metadata: dict[str, Any] = {
            "sourceFileType": source_file_type,
            "parserVersion": parser_version,
            "embeddingStatus": "EMBEDDED",
            "indexVersion": index_version,
            "citationText": f"{chunk_id} citation",
            "documentVersionId": f"docv-{chunk_id}",
        }
        if source_file_type == "SPREADSHEET":
            metadata.update({"sheetName": "Sheet1", "cellRange": "A2:B2"})
        elif source_file_type == "PDF":
            metadata.update({"page": 2, "bbox": [0, 0, 10, 10]})
        return RetrievedChunk(
            chunk_id=chunk_id,
            doc_id=f"doc-{chunk_id}",
            section="section",
            text=f"{chunk_id} text",
            score=0.9,
            search_unit_id=f"su-{chunk_id}",
            source_file_id=f"source-{chunk_id}",
            source_file_name=f"{chunk_id}.dat",
            metadata_json=metadata,
        )

    class FakeRetriever:
        _top_k = 1
        _candidate_k = 1

        def retrieve(self, query: str, filters: Any = None) -> Any:
            return SimpleNamespace(
                query=query,
                top_k=4,
                index_version="idx-v1",
                embedding_model="fake-embedding",
                results=[
                    chunk(chunk_id="valid-xlsx", source_file_type="SPREADSHEET"),
                    chunk(chunk_id="off-track-pdf", source_file_type="PDF"),
                    chunk(
                        chunk_id="wrong-index-xlsx",
                        source_file_type="SPREADSHEET",
                        index_version="idx-v2",
                    ),
                    chunk(
                        chunk_id="wrong-parser-xlsx",
                        source_file_type="SPREADSHEET",
                        parser_version="other-parser",
                    ),
                ],
            )

    state = run_query_orchestrator_pure(
        query="xlsx 매출 합계",
        policy=QueryPolicy(
            request_id="req-xlsx",
            required_index_version="idx-v1",
            allowed_source_file_types=["SPREADSHEET"],
            allowed_parser_versions=["xlsx-extract-v2-hidden-safe"],
            top_k=1,
        ),
        retriever=FakeRetriever(),
    )

    assert [item.chunk_id for item in state["verified_evidence"]] == ["valid-xlsx"]
    rejection_reasons = {
        reason
        for item in state["rejected_evidence"]
        for reason in item["reasons"]
    }
    assert "source_file_type_mismatch" in rejection_reasons
    assert "index_version_mismatch" in rejection_reasons
    assert "parser_version_not_allowed" in rejection_reasons
    used_ids = set(state["answer"]["used_evidence_ids"])
    assert used_ids == {"vector-valid-xlsx"}
    assert "vector-off-track-pdf" not in used_ids
    assert "vector-wrong-index-xlsx" not in used_ids
    assert "score_status" not in state
    assert all("score_status" not in item for item in state["route_diagnostics"])


def test_vector_retriever_overfetch_is_restored_when_retrieve_raises() -> None:
    sys.path.insert(0, str(ROOT / "ai"))

    from app.capabilities.rag_orchestrator.evidence import QueryPolicy
    from app.capabilities.rag_orchestrator.vector_tools import xlsx_vector_search_tool

    class RaisingRetriever:
        _top_k = 1
        _candidate_k = 1

        def retrieve(self, query: str, filters: Any = None) -> Any:
            assert self._top_k == 5
            assert self._candidate_k == 5
            raise RuntimeError("boom")

    retriever = RaisingRetriever()
    with pytest.raises(RuntimeError, match="boom"):
        xlsx_vector_search_tool(
            "xlsx 매출 합계",
            QueryPolicy(
                request_id="req-xlsx",
                required_index_version="idx-v1",
                allowed_source_file_types=["SPREADSHEET"],
                allowed_parser_versions=["xlsx-extract-v2-hidden-safe"],
                top_k=1,
            ),
            retriever=retriever,
        )

    assert retriever._top_k == 1
    assert retriever._candidate_k == 1


def test_rag_query_orchestrator_conflicting_policy_metadata_does_not_call_retriever() -> None:
    sys.path.insert(0, str(ROOT / "ai"))

    from app.capabilities.rag_orchestrator.evidence import QueryPolicy
    from app.capabilities.rag_orchestrator.graph import run_query_orchestrator_pure

    class FakeRetriever:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def retrieve(self, query: str, filters: Any = None) -> Any:
            self.calls.append({"query": query, "filters": filters})
            raise AssertionError("conflicting source guards must not retrieve")

    retriever = FakeRetriever()
    state = run_query_orchestrator_pure(
        query="xlsx 매출 합계",
        policy=QueryPolicy(
            request_id="req-conflict",
            required_index_version="idx-v1",
            allowed_source_file_types=["SPREADSHEET"],
            allowed_parser_versions=["xlsx-extract-v2-hidden-safe"],
            top_k=1,
        ),
        source_metadata={"source_file_type": "PDF"},
        retriever=retriever,
    )

    assert retriever.calls == []
    assert state["route_decision"]["route"] == "policy_blocked"
    assert state["selected_tools"] == []
    assert state["verified_evidence"] == []
    assert state["answer"]["status"] == "blocked"
    assert "policy_source_metadata_conflict" in state["route_decision"]["metadata_guards"]
    assert "policy_source_metadata_conflict" in state["route_decision"]["blocked_flags"]
    assert state["route_diagnostics"][0]["production_vector_written"] is False
    assert state["route_diagnostics"][0]["official_denominator_registry_changed"] is False


def test_registry_wires_query_orchestrator_to_registered_rag_retriever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from types import SimpleNamespace

    from app.capabilities import registry as registry_module
    from app.capabilities.base import (
        Capability,
        CapabilityInput,
        CapabilityInputArtifact,
        CapabilityOutput,
    )
    from app.capabilities.rag.generation import RetrievedChunk
    from app.core.config import WorkerSettings

    class FakeRagCapability(Capability):
        name = "RAG"

        def run(self, input: CapabilityInput) -> CapabilityOutput:
            raise AssertionError("registry smoke should not execute RAG")

    class FakeRetriever:
        _top_k = 1
        _candidate_k = 1

        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def retrieve(self, query: str, filters: Any = None) -> Any:
            self.calls.append({"query": query, "filters": filters})
            return SimpleNamespace(
                query=query,
                top_k=1,
                index_version="idx-v1",
                embedding_model="fake-embedding",
                results=[
                    RetrievedChunk(
                        chunk_id="chunk-xlsx-1",
                        doc_id="doc-xlsx-1",
                        section="Sheet1",
                        text="Sheet1 A2:B2 매출 합계 42",
                        score=0.91,
                        search_unit_id="su-xlsx-1",
                        source_file_id="source-xlsx-1",
                        source_file_name="book.xlsx",
                        metadata_json={
                            "sourceFileType": "SPREADSHEET",
                            "parserVersion": "xlsx-extract-v2-hidden-safe",
                            "embeddingStatus": "EMBEDDED",
                            "indexVersion": "idx-v1",
                            "citationText": "Sheet1 A2:B2 매출 합계 42",
                            "sheetName": "Sheet1",
                            "cellRange": "A2:B2",
                            "documentVersionId": "docv-xlsx-1",
                        },
                    )
                ],
            )

    retriever = FakeRetriever()

    monkeypatch.setattr(
        registry_module,
        "_build_rag_capability",
        lambda settings: FakeRagCapability(),
    )
    monkeypatch.setattr(
        registry_module,
        "_get_shared_retriever_bundle",
        lambda settings: (retriever, object()),
    )

    registry = registry_module.build_default_registry(
        WorkerSettings(
            rag_enabled=True,
            ocr_enabled=False,
            ocr_extract_enabled=False,
            xlsx_extract_enabled=False,
            pdf_extract_enabled=False,
            multimodal_enabled=False,
            rag_query_orchestrator_enabled=True,
        )
    )

    capability = registry.get("RAG_QUERY_ORCHESTRATOR")
    request = {
        "query": "xlsx 매출 합계",
        "policy": {
            "requiredIndexVersion": "idx-v1",
            "allowedSourceFileTypes": ["SPREADSHEET"],
            "allowedParserVersions": ["xlsx-extract-v2-hidden-safe"],
            "topK": 1,
        },
    }
    output = capability.run(
        CapabilityInput(
            job_id="job-xlsx",
            capability="RAG_QUERY_ORCHESTRATOR",
            attempt_no=1,
            inputs=[
                CapabilityInputArtifact(
                    artifact_id="input-json",
                    type="INPUT_JSON",
                    content=json.dumps(request).encode("utf-8"),
                )
            ],
        )
    )

    payload = json.loads(output.outputs[0].content.decode("utf-8"))
    assert payload["graph_backend"] == "pure_vector_retriever_poc"
    assert payload["state"]["tool_results"][0]["tool"] == "xlsx_vector_search_tool"
    assert retriever.calls == [{"query": "xlsx 매출 합계", "filters": None}]


def test_v3_6_9_searchunit_searchview_sourceatom_refactor_summary_locks_exit_and_guardrails() -> None:
    summary = read_json(V3_6_9_SEARCHUNIT_SOURCEATOM_SUMMARY)
    contract = read_json(V3_6_9_SEARCHUNIT_SOURCEATOM_CONTRACT)
    adapter = read_json(V3_6_9_SEARCHUNIT_SOURCEATOM_ADAPTER)
    hydration = read_json(V3_6_9_SEARCHUNIT_SOURCEATOM_HYDRATION)
    failure_buckets = read_json(V3_6_9_SEARCHUNIT_SOURCEATOM_FAILURE_BUCKETS)

    assert summary["run_id"] == V3_6_9_SEARCHUNIT_SOURCEATOM_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_searchunit_searchview_sourceatom_refactor"
    assert summary["run_class"] == "diagnostic_only_source_first_contract_refactor"
    assert summary["diagnostic_only"] is True
    assert summary["implementation_allowed"] is True
    assert set(summary["outcome_choices"]) == V3_6_9_SEARCHUNIT_SOURCEATOM_OUTCOMES
    assert summary["outcome"] == "SEARCHUNIT_SEARCHVIEW_SOURCEATOM_CONTRACT_READY"
    assert summary["next_allowed_phase"] == "source registry materialization"
    assert summary["recommended_next_phase"] == summary["next_allowed_phase"]
    assert summary["no_generic_probe_recommended"] is True
    assert "manifest_locator" not in summary["recommended_next_phase"]
    assert summary["source_atom_search_view_contract_validated"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["db_migration_required_for_minimal_python_refactor"] is False
    assert summary["db_migration_deferred_until_source_registry_materialization"] is True
    assert summary["source_registry_materialization_required"] is True

    for key in (
        "official_metric",
        "answer_metric_computed",
        "citation_metric_computed",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "official_qrels_created",
        "official_relevance_labels_created",
        "official_answerability_labels_created",
        "official_gold_labels_created",
        "expected_answer_draft_used_as_generation_input",
        "silver_expected_answer_used_as_generation_input",
        "silver_evidence_locator_used_as_retrieval_shortcut",
        "query_id_specific_evidence_patch",
        "file_name_specific_evidence_patch",
        "prompt_mutation",
        "retrieval_ranking_mutation",
        "scorer_mutation",
        "threshold_tuning",
        "winner_selection",
        "readme_representative_product_performance_claim",
        "lane_a_b_c_collapsed_scoring",
        "production_db_used",
        "db_write_attempted",
        "db_migration_attempted",
        "production_mutation",
    ):
        assert summary[key] is False, key

    assert contract["search_view_contract"]["must_point_to_source_atoms"] is True
    assert contract["search_view_contract"]["canonical_citation_source_allowed"] == "only_validated_source_atom"
    assert contract["source_atom_contract"]["source_registry_version"] == "source-registry-v1"
    assert contract["vector_metadata_contract"]["candidate_generator_only"] is True
    assert contract["vector_metadata_contract"]["must_not_own_canonical_citation_payload"] is True
    assert adapter["chunk_only_failure_bucket"] == "RETRIEVAL_RESULT_CHUNK_ONLY_NOT_SEARCHUNIT"
    assert adapter["vector_payload_used_as_evidence_truth"] is False
    assert adapter["ignored_vector_canonical_payload"] is True
    assert hydration["families_passed"] == ["PDF", "TEXT", "XLSX"]
    assert hydration["no_vector_citation_render_valid_count"] == 3
    assert failure_buckets["blocking_buckets"] == []
    assert failure_buckets["next_blocking_work"] == ["SOURCE_REGISTRY_MATERIALIZATION_REQUIRED"]


def test_v3_7_0_source_registry_materialization_artifacts_lock_source_first_contract() -> None:
    summary = read_json(V3_7_0_SOURCE_REGISTRY_SUMMARY)
    inventory = read_json(V3_7_0_SOURCE_REGISTRY_SOURCE_INVENTORY)
    registry_inventory = read_json(SOURCE_ATOM_REGISTRY_INVENTORY_JSON)
    build = read_json(SOURCE_ATOM_REGISTRY_BUILD_JSON)
    hydration = read_json(V3_7_0_SOURCE_REGISTRY_HYDRATION_SMOKE)
    failure_buckets = read_json(V3_7_0_SOURCE_REGISTRY_FAILURE_BUCKETS)
    diagnostics = read_jsonl(V3_7_0_SOURCE_REGISTRY_MATERIALIZATION_DIAGNOSTICS)
    blocked_rows = read_jsonl(SOURCE_ATOM_REGISTRY_BLOCKED_JSONL)

    assert summary["run_id"] == V3_7_0_SOURCE_REGISTRY_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_source_registry_materialization"
    assert summary["run_class"] == "diagnostic_only_source_registry_materialization"
    assert summary["diagnostic_only"] is True
    assert set(summary["outcome_choices"]) == V3_7_0_SOURCE_REGISTRY_OUTCOMES
    assert summary["outcome"] == "SOURCE_REGISTRY_MATERIALIZED_READY"
    assert summary["next_allowed_phase"] == "v3_7_1_all_source_citable_nonprod_index_build"
    assert summary["v3_7_1_all_source_citable_nonprod_index_build_allowed"] is True
    assert summary["source_registry_materialized"] is True
    assert summary["source_registry_path"] == "ai/eval/source_registry/source_atom_registry_v1.jsonl"
    assert summary["materialized_source_atom_count"] == build["materialized_source_atom_count"]
    assert summary["materialized_source_atom_count"] == registry_inventory["materialized_source_atom_count"]
    assert summary["total_inspected_source_candidates"] == registry_inventory["total_inspected_source_candidates"]
    assert summary["v3_5_4_source_only_manifest_counts"] == {"TEXT": 350, "PDF": 325, "XLSX": 325}
    assert summary["official_overlap_count"] == 29
    assert summary["official_denominator_source_atoms_protected_regression_scope"] is True
    assert summary["protected_official_denominator_not_dev_or_holdout_tuning_source"] is True

    for key in (
        "official_metric",
        "answer_metric_computed",
        "citation_metric_computed",
        "retrieval_metric_computed",
        "hybrid_retrieval_baseline_computed",
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "official_qrels_created",
        "official_relevance_labels_created",
        "official_answerability_labels_created",
        "official_gold_labels_created",
        "expected_answer_draft_used_as_source_content",
        "supporting_evidence_used_as_answer_text_source",
        "generated_silver_answers_used_as_source_material",
        "generated_silver_questions_used_as_source_material",
        "silver_evidence_locator_used_as_retrieval_shortcut",
        "query_id_specific_evidence_patch",
        "file_name_specific_evidence_patch",
        "threshold_tuning",
        "winner_selection",
        "promotion_gate",
        "readme_representative_product_performance_claim",
        "lane_a_b_c_collapsed_scoring",
        "production_db_used",
        "db_write_attempted",
        "db_migration_attempted",
        "db_index_rebuild_attempted",
        "vector_index_build_performed",
        "vector_metadata_used_as_canonical_citation_source",
    ):
        assert summary[key] is False, key

    assert inventory["source_material_inputs"]["v3_5_4_source_only_manifest"]["row_count"] == 1000
    assert inventory["source_material_inputs"]["official_source_bound_units"]["row_count"] == 29
    assert inventory["source_material_inputs"]["raw_text_chunks"]["row_count"] > 100000
    assert inventory["excluded_source_content_policy"]["expected_answers_indexed"] is False
    assert inventory["excluded_source_content_policy"]["gold_labels_indexed"] is False
    assert inventory["excluded_source_content_policy"]["qrels_indexed"] is False
    assert inventory["excluded_source_content_policy"]["metric_result_files_indexed"] is False
    assert inventory["excluded_source_content_policy"]["generated_silver_answers_indexed"] is False
    assert set(registry_inventory["source_family_counts"]) == {"TEXT", "PDF", "XLSX"}
    assert all(registry_inventory["source_family_counts"][family] > 0 for family in ("TEXT", "PDF", "XLSX"))
    assert registry_inventory["materialization_bucket_counts"]["source_atom_ready"] > 0
    assert registry_inventory["materialization_bucket_counts"]["snapshot_only_ready"] > 0
    assert registry_inventory["materialization_bucket_counts"]["retrieval_only_uncanonicalized"] == 0
    assert registry_inventory["snapshot_only_count"] == registry_inventory["materialization_bucket_counts"]["snapshot_only_ready"]
    assert failure_buckets["failure_bucket_counts"]["blocked_expected_answer_or_label_artifact"] > 0
    assert failure_buckets["failure_bucket_counts"]["blocked_eval_artifact"] > 0
    assert not failure_buckets["blocking_buckets"]
    assert blocked_rows
    assert {row["materialization_bucket"] for row in blocked_rows} >= {
        "blocked_eval_artifact",
        "blocked_expected_answer_or_label_artifact",
    }
    assert all(row.get("materialization_bucket") for row in diagnostics[:25])


def test_v3_7_0_xlsx_raw_locator_resolves_unambiguous_external_archive_workbook(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    workbook_path = tmp_path / "source_collection" / "nested" / "external_book.xlsx"
    workbook_path.parent.mkdir(parents=True)
    workbook_path.write_bytes(b"PK\x03\x04")
    monkeypatch.setattr(runner, "V3_5_XLSX_SOURCE_ROOTS", (tmp_path / "source_collection",))

    unit = {
        "source_family": "XLSX",
        "source_locator": {
            "workbook": workbook_path.name,
            "source_file_path": "",
            "sheet": "Sheet1",
            "range": "A1",
        },
        "track_locator_payload": {
            "workbook": workbook_path.name,
            "source_path": "",
            "sheet": "Sheet1",
            "range": "A1",
        },
    }

    locator = runner.v3_7_0_normalized_raw_locator(unit)

    assert Path(locator["source_path"]).resolve() == workbook_path.resolve()
    assert runner.v3_7_0_raw_file_exists(source_family="XLSX", raw_locator=locator) is True


def test_v3_7_0_xlsx_raw_locator_does_not_guess_ambiguous_external_archive_workbook(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    first = tmp_path / "root-a" / "same_name.xlsx"
    second = tmp_path / "root-b" / "same_name.xlsx"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"PK\x03\x04")
    second.write_bytes(b"PK\x03\x04")
    monkeypatch.setattr(runner, "V3_5_XLSX_SOURCE_ROOTS", (tmp_path,))

    unit = {
        "source_family": "XLSX",
        "source_locator": {
            "workbook": "same_name.xlsx",
            "source_file_path": "",
            "sheet": "Sheet1",
            "cell": "B2",
        },
        "track_locator_payload": {
            "workbook": "same_name.xlsx",
            "source_path": "",
            "sheet": "Sheet1",
            "cell": "B2",
        },
    }

    locator = runner.v3_7_0_normalized_raw_locator(unit)

    assert locator["source_path"] == ""
    assert runner.v3_7_0_raw_file_exists(source_family="XLSX", raw_locator=locator) is False


def test_v3_7_0_xlsx_raw_locator_resolves_single_valid_duplicate_archive_workbook(tmp_path, monkeypatch) -> None:
    import zipfile

    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    invalid = tmp_path / "root-a" / "same_name.xlsx"
    valid = tmp_path / "root-b" / "same_name.xlsx"
    invalid.parent.mkdir(parents=True)
    valid.parent.mkdir(parents=True)
    invalid.write_bytes(b"not an xlsx zip archive")
    with zipfile.ZipFile(valid, "w"):
        pass
    monkeypatch.setattr(runner, "V3_5_XLSX_SOURCE_ROOTS", (tmp_path,))

    unit = {
        "source_family": "XLSX",
        "source_locator": {
            "workbook": "same_name.xlsx",
            "source_file_path": "",
            "sheet": "Sheet1",
            "range": "A1:B2",
        },
        "track_locator_payload": {
            "workbook": "same_name.xlsx",
            "source_path": "",
            "sheet": "Sheet1",
            "range": "A1:B2",
        },
    }

    locator = runner.v3_7_0_normalized_raw_locator(unit)

    assert Path(locator["source_path"]).resolve() == valid.resolve()
    assert runner.v3_7_0_raw_file_exists(source_family="XLSX", raw_locator=locator) is True


def test_v3_7_0_pdf_raw_locator_keeps_basename_only_archive_match_snapshot_only(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    pdf_path = tmp_path / "archive" / "nested" / "report.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(runner, "V3_5_PDF_DIAGNOSTIC_SOURCE_ROOTS", (tmp_path / "archive",))

    unit = {
        "source_family": "PDF",
        "source_locator": {
            "source_pdf_path": "report.pdf",
            "page": 1,
            "bbox": [1, 2, 3, 4],
            "region_type": "text",
        },
        "track_locator_payload": {
            "source_pdf_path": "",
            "page": 1,
            "bbox": [1, 2, 3, 4],
            "region_type": "text",
        },
    }

    locator = runner.v3_7_0_normalized_raw_locator(unit)

    assert locator["source_pdf_path"] == "report.pdf"
    assert runner.v3_7_0_raw_file_exists(source_family="PDF", raw_locator=locator) is False
    resolution = runner.v3_7_0_snapshot_only_resolution_summary(
        [
            {
                "source_atom_id": "srcatom_v1_pdf_test",
                "source_family": "PDF",
                "source_identity": "PDF:report",
                "materialization_bucket": "snapshot_only_ready",
                "raw_locator": locator,
            }
        ]
    )
    assert resolution["counts_by_resolution_bucket"] == {
        "source_identity_insufficient_basename_only_archive_match": 1
    }
    assert resolution["counts_by_source_family"]["PDF"] == 1


def test_v3_7_1_xlsx_search_view_ranking_text_keeps_locator_and_value_fields() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    atom = {
        "source_atom_id": "srcatom_v1_xlsx_test",
        "source_family": "XLSX",
        "source_identity": "XLSX:book.xlsx:Sheet1!B2",
        "raw_locator": {
            "workbook": "book.xlsx",
            "source_path": "D:/archive/book.xlsx",
            "sheet": "Sheet1",
            "range": "A1:B2",
            "cell": "B2",
            "row_label": "매출",
            "column_label": "2026년",
            "target_column": "2026년",
        },
        "normalized_text_or_value_snapshot": "42",
        "parent_pointers": {"search_unit_id": "su-xlsx-1"},
    }

    view = runner.v3_7_1_search_view_from_source_atom(
        atom,
        faiss_row_id=7,
        generated_at="2026-05-21T00:00:00Z",
    )

    for field in ("embedding_text", "bm25_text", "display_text"):
        assert "workbook=book.xlsx" in view[field]
        assert "sheet=Sheet1" in view[field]
        assert "range=A1:B2" in view[field]
        assert "cell=B2" in view[field]
        assert "row_label=매출" in view[field]
        assert "target_column=2026년" in view[field]
        assert "normalized_value=42" in view[field]


def test_v3_7_2_structured_rerank_prefers_xlsx_exact_locator_value_over_broad_range() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    query = "2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까?"
    broad_range = {
        "faiss_row_id": 1,
        "source_family": "XLSX",
        "bm25_text": (
            "workbook=국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx | "
            "sheet=일반현황 | range=A1:J30761 | normalized_value=202011"
        ),
        "display_text": "일반현황 broad sheet range 202011",
    }
    exact_value = {
        "faiss_row_id": 2,
        "source_family": "XLSX",
        "bm25_text": (
            "workbook=국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx | "
            "sheet=일반현황 | range=A702:J751 | cell=C702 | "
            "row_label=장기요양기관이름=하얀민들레노인요양원 | "
            "column_label=우편번호 | target_column=우편번호 | normalized_value=41786"
        ),
        "display_text": "하얀민들레노인요양원 우편번호 41786",
    }

    hits = runner.v3_7_2_rank_family_candidates(
        query_text=query,
        candidate_rows=[broad_range, exact_value],
        base_scores=[0.90, 0.10],
        top_k=2,
    )

    assert hits[0][0] == 2
    assert hits[0][1] > hits[1][1]


def test_v3_7_2_structured_rerank_prefers_pdf_content_terms_over_filename_only_match() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    query = "1월 산업활동에서 생산 지표는 어떻게 움직였나요?"
    filename_only = {
        "faiss_row_id": 10,
        "source_family": "PDF",
        "bm25_text": "source_pdf_path=2025_01_recent_economic_trends.pdf | page=1 | 목 차",
        "display_text": "2025년 1월 최근경제동향 목차",
    }
    content_match = {
        "faiss_row_id": 11,
        "source_family": "PDF",
        "bm25_text": (
            "source_pdf_path=2025_01_recent_economic_trends.pdf | page=8 | "
            "region_type=text | matched_text=1월 산업활동은 생산 지표가 조정되며 광공업 생산이 움직였다"
        ),
        "display_text": "1월 산업활동 생산 지표 광공업 생산",
    }

    hits = runner.v3_7_2_rank_family_candidates(
        query_text=query,
        candidate_rows=[filename_only, content_match],
        base_scores=[0.80, 0.20],
        top_k=2,
    )

    assert hits[0][0] == 11
    assert hits[0][1] > hits[1][1]


def test_v3_8_file_grounded_metrics_keep_xlsx_and_pdf_denominators_separate() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_xlsx_target": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "41786",
            },
            "normalized_text_or_value_snapshot": "41786",
        },
        "atom_pdf_target": {
            "source_family": "PDF",
            "source_identity": "docv_pdf:report.pdf:3:[1, 2, 3, 4]",
            "raw_locator": {
                "source_pdf_path": "D:/repo/report.pdf",
                "page": 3,
                "physical_page_index": 2,
                "bbox": [1, 2, 3, 4],
                "region_type": "paragraph",
            },
            "normalized_text_or_value_snapshot": "matched paragraph text",
        },
    }
    topk_rows = [
        {
            "query_id": "xlsx_q1",
            "source_family": "XLSX",
            "target_source_atom_ids": ["atom_xlsx_target"],
            "target_search_view_ids": ["sv_xlsx_target"],
            "official_manifest_target": {
                "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
            },
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_xlsx_target",
                    "source_atom_id": "atom_xlsx_target",
                    "source_family": "XLSX",
                    "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
        {
            "query_id": "pdf_q1",
            "source_family": "PDF",
            "target_source_atom_ids": ["atom_pdf_target"],
            "target_search_view_ids": ["sv_pdf_target"],
            "question_gold_locator_target": {
                "file": "report.pdf",
                "page": 3,
                "bbox": [1, 2, 3, 4],
            },
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_pdf_target",
                    "source_atom_id": "atom_pdf_target",
                    "source_family": "PDF",
                    "source_identity": "docv_pdf:report.pdf:3:[1, 2, 3, 4]",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
    ]

    metrics = runner.v3_8_file_grounded_retrieval_eval_metrics(
        topk_rows,
        source_registry=source_registry,
    )

    assert metrics["headline_aggregate_score_reported"] is False
    assert metrics["answer_generation_metric_computed"] is False
    assert metrics["gold_or_label_mutation"] is False
    assert set(metrics["per_source_family"]) == {"PDF", "XLSX"}
    assert metrics["per_source_family"]["XLSX"]["query_count"] == 1
    assert metrics["per_source_family"]["PDF"]["query_count"] == 1
    assert metrics["per_source_family"]["XLSX"]["metrics"]["workbook_hit@1"]["rate"] == 1.0
    assert metrics["per_source_family"]["XLSX"]["metrics"]["sheet_hit@5"]["rate"] == 1.0
    assert metrics["per_source_family"]["XLSX"]["metrics"]["table_or_range_hit@5"]["rate"] == 1.0
    assert metrics["per_source_family"]["XLSX"]["metrics"]["cell_or_value_hit@5"]["rate"] == 1.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["file_hit@1"]["rate"] == 1.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["page_hit@5"]["rate"] == 1.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["block_or_bbox_available@5"]["rate"] == 1.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["matched_text_present@5"]["rate"] == 1.0


def test_v3_8_file_grounded_metrics_count_unsupported_without_vector_truth_or_gold_mutation() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_xlsx_target": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "41786",
            },
            "normalized_text_or_value_snapshot": "41786",
        },
        "atom_xlsx_wrong": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:other.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "other.xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "00000",
            },
            "normalized_text_or_value_snapshot": "00000",
        },
    }
    topk_rows = [
        {
            "query_id": "xlsx_q1",
            "source_family": "XLSX",
            "target_source_atom_ids": ["atom_xlsx_target"],
            "target_search_view_ids": ["sv_xlsx_target"],
            "official_manifest_target": {
                "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
            },
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_xlsx_wrong",
                    "source_atom_id": "atom_xlsx_wrong",
                    "source_family": "XLSX",
                    "source_identity": "docv_xlsx:other.xlsx:Summary:A1:D10:C4",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                    "vector_metadata_used_as_canonical_citation_source": True,
                    "vector_payload_used_as_evidence_truth": True,
                }
            ],
        }
    ]

    metrics = runner.v3_8_file_grounded_retrieval_eval_metrics(
        topk_rows,
        source_registry=source_registry,
    )

    xlsx = metrics["per_source_family"]["XLSX"]["metrics"]
    assert xlsx["file_hit@1"]["rate"] == 0.0
    assert xlsx["target_source_atom_recall@5"]["rate"] == 0.0
    assert xlsx["evidence_select_hit@3"]["rate"] == 0.0
    assert xlsx["unsupported_rate"]["rate"] == 1.0
    assert metrics["vector_db_role"] == "candidate_generator_only"
    assert metrics["source_atom_registry_canonical_truth"] is True
    assert metrics["vector_metadata_used_as_canonical_citation_source"] is False
    assert metrics["vector_metadata_used_as_evidence_truth"] is False
    assert metrics["ignored_vector_truth_claim_count"] == 1


def test_v3_8_file_grounded_metrics_require_loaded_source_atom_for_contract_survival() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    topk_rows = [
        {
            "query_id": "pdf_q1",
            "source_family": "PDF",
            "target_source_atom_ids": ["atom_pdf_target"],
            "target_search_view_ids": ["sv_pdf_target"],
            "official_manifest_target": {
                "source_identity": "docv_pdf:report.pdf:3:[1, 2, 3, 4]",
            },
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_pdf_target",
                    "source_atom_id": "atom_pdf_target",
                    "source_family": "PDF",
                    "source_identity": "docv_pdf:report.pdf:3:[1, 2, 3, 4]",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        }
    ]

    metrics = runner.v3_8_file_grounded_retrieval_eval_metrics(
        topk_rows,
        source_registry={},
    )

    pdf = metrics["per_source_family"]["PDF"]["metrics"]
    assert pdf["file_hit@5"]["rate"] == 1.0
    assert pdf["target_source_atom_recall@5"]["rate"] == 1.0
    assert pdf["evidence_select_hit@3"]["rate"] == 0.0
    assert pdf["contract_survival_rate"]["rate"] == 0.0
    assert pdf["unsupported_rate"]["rate"] == 1.0


def test_v3_8_1_evidence_selector_prefers_citation_capable_same_file_evidence() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_xlsx_target": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "41786",
            },
            "normalized_text_or_value_snapshot": "41786",
        },
        "atom_xlsx_wrong": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:other.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "other.xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "00000",
            },
            "normalized_text_or_value_snapshot": "00000",
        },
    }
    row = {
        "query_id": "xlsx_selector_q1",
        "source_family": "XLSX",
        "target_source_atom_ids": ["atom_xlsx_target"],
        "target_search_view_ids": ["sv_xlsx_target"],
        "official_manifest_target": {
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
        },
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_wrong",
                "source_atom_id": "atom_xlsx_wrong",
                "source_family": "XLSX",
                "source_identity": "docv_xlsx:other.xlsx:Summary:A1:D10:C4",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
                "vector_metadata_used_as_canonical_citation_source": True,
            },
            {
                "rank": 2,
                "search_view_id": "sv_same_file_unhydrated",
                "source_atom_id": "missing_atom",
                "source_family": "XLSX",
                "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:B2",
                "source_atom_hydrated_from_registry": False,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
            {
                "rank": 3,
                "search_view_id": "sv_xlsx_target",
                "source_atom_id": "atom_xlsx_target",
                "source_family": "XLSX",
                "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
            {
                "rank": 4,
                "search_view_id": "sv_wrong_late",
                "source_atom_id": "atom_xlsx_wrong",
                "source_family": "XLSX",
                "source_identity": "docv_xlsx:other.xlsx:Summary:A1:D10:C4",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
        ],
    }

    selected = runner.v3_8_1_select_evidence_candidates(
        row,
        source_registry=source_registry,
    )

    assert len(selected) == 3
    assert selected[0]["source_atom_id"] == "atom_xlsx_target"
    assert selected[0]["source_atom_hydrated_from_registry"] is True
    assert selected[0]["source_atom_registry_hydrated"] is True
    assert selected[0]["selector_rank"] == 1
    assert selected[0]["selector_file_hit"] is True
    assert selected[0]["selector_target_hit"] is True
    assert selected[0]["contract_survived"] is True
    assert selected[0]["citation_render_valid"] is True
    assert selected[0]["vector_metadata_used_as_canonical_citation_source"] is False


def test_v3_8_1_pdf_selector_file_hit_uses_registry_target_identity_for_metrics_only() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_pdf_target": {
            "source_family": "PDF",
            "source_identity": "docv_pdf:report.pdf:3:[1, 2, 3, 4]",
            "raw_locator": {
                "source_pdf_path": "D:/repo/report.pdf",
                "page": 3,
                "physical_page_index": 2,
                "bbox": [1, 2, 3, 4],
                "region_type": "paragraph",
                "matched_text": "target paragraph",
            },
        },
    }
    row = {
        "query_id": "pdf_selector_identity_q1",
        "source_family": "PDF",
        "target_source_atom_ids": ["atom_pdf_target"],
        "target_search_view_ids": ["sv_pdf_target"],
        "question_gold_locator_target": {
            "file": "9a5cbe71-1b11-45ef-a4f5-9fb6f2f70c2b",
            "page": 3,
            "bbox": [1, 2, 3, 4],
        },
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_pdf_target",
                "source_atom_id": "atom_pdf_target",
                "source_family": "PDF",
                "source_identity": "docv_pdf:report.pdf:3:[1, 2, 3, 4]",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            }
        ],
    }

    selected = runner.v3_8_1_select_evidence_candidates(
        row,
        source_registry=source_registry,
    )

    assert len(selected) == 1
    assert selected[0]["selector_target_hit"] is True
    assert selected[0]["source_atom_registry_hydrated"] is True
    assert selected[0]["selector_file_hit"] is True


def test_v3_8_1_evidence_selector_uses_target_ids_only_for_metrics_not_ordering() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_xlsx_neighbor": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
            },
        },
        "atom_xlsx_target": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
            },
        },
    }
    row = {
        "query_id": "xlsx_selector_order_q1",
        "source_family": "XLSX",
        "target_source_atom_ids": ["atom_xlsx_target"],
        "target_search_view_ids": ["sv_xlsx_target"],
        "official_manifest_target": {
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:",
        },
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_xlsx_neighbor",
                "source_atom_id": "atom_xlsx_neighbor",
                "source_family": "XLSX",
                "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
            {
                "rank": 2,
                "search_view_id": "sv_xlsx_target",
                "source_atom_id": "atom_xlsx_target",
                "source_family": "XLSX",
                "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
        ],
    }

    selected = runner.v3_8_1_select_evidence_candidates(
        row,
        source_registry=source_registry,
    )

    assert [candidate["source_atom_id"] for candidate in selected[:2]] == [
        "atom_xlsx_neighbor",
        "atom_xlsx_target",
    ]
    assert selected[0]["selector_target_hit"] is False
    assert selected[1]["selector_target_hit"] is True


def test_v3_8_1_evidence_selector_metrics_are_separate_and_diagnostic_only() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_xlsx_target": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "41786",
            },
            "normalized_text_or_value_snapshot": "41786",
        },
        "atom_pdf_target": {
            "source_family": "PDF",
            "source_identity": "docv_pdf:report.pdf:3:[1, 2, 3, 4]",
            "raw_locator": {
                "source_pdf_path": "D:/repo/report.pdf",
                "page": 3,
                "physical_page_index": 2,
                "bbox": [1, 2, 3, 4],
                "region_type": "paragraph",
                "matched_text": "matched paragraph text",
            },
            "normalized_text_or_value_snapshot": "matched paragraph text",
        },
    }
    topk_rows = [
        {
            "query_id": "xlsx_selector_q1",
            "source_family": "XLSX",
            "target_source_atom_ids": ["atom_xlsx_target"],
            "target_search_view_ids": ["sv_xlsx_target"],
            "official_manifest_target": {
                "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
            },
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_xlsx_target",
                    "source_atom_id": "atom_xlsx_target",
                    "source_family": "XLSX",
                    "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                    "vector_payload_used_as_evidence_truth": True,
                }
            ],
        },
        {
            "query_id": "pdf_selector_q1",
            "source_family": "PDF",
            "target_source_atom_ids": ["atom_pdf_target"],
            "target_search_view_ids": ["sv_pdf_target"],
            "question_gold_locator_target": {
                "file": "report.pdf",
                "page": 3,
                "bbox": [1, 2, 3, 4],
            },
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_pdf_wrong",
                    "source_atom_id": "missing_pdf_atom",
                    "source_family": "PDF",
                    "source_identity": "docv_pdf:report.pdf:3:[1, 2, 3, 4]",
                    "source_atom_hydrated_from_registry": False,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
    ]

    metrics = runner.v3_8_1_evidence_selector_metrics(
        topk_rows,
        source_registry=source_registry,
    )

    assert metrics["run_id"] == "official_answer_citation_agentic_loop_run_v3_8_1_evidence_selector_v1"
    assert metrics["headline_aggregate_score_reported"] is False
    assert metrics["answer_generation_metric_computed"] is False
    assert metrics["gold_or_label_mutation"] is False
    assert metrics["vector_db_role"] == "candidate_generator_only"
    assert metrics["source_atom_registry_canonical_truth"] is True
    assert metrics["denominator_policy"]["xlsx_and_pdf_are_not_collapsed"] is True
    assert metrics["selector_policy"]["uses_target_source_atom_ids_for_selection"] is False
    assert metrics["selector_policy"]["target_source_atom_ids_used_for_metrics_only"] is True
    assert metrics["vector_truth_violation_count"] == 1
    assert set(metrics["per_source_family"]) == {"PDF", "XLSX"}
    assert metrics["per_source_family"]["XLSX"]["query_count"] == 1
    assert metrics["per_source_family"]["PDF"]["query_count"] == 1
    assert metrics["per_source_family"]["XLSX"]["selector_candidate_count"] == 1
    assert metrics["per_source_family"]["PDF"]["selector_candidate_count"] == 1
    assert metrics["per_source_family"]["XLSX"]["metrics"]["selector_target_hit@3"]["rate"] == 1.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["selector_target_hit@3"]["rate"] == 0.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["selector_unsupported_rate"]["rate"] == 1.0


def test_v3_8_1_evidence_selector_run_measurement_wires_artifact_freeze_summary_without_answer_generation() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    args = runner.parse_args(["--run-id", runner.V3_8_1_EVIDENCE_SELECTOR_RUN_ID])

    summary, rows = runner.run_measurement(args)

    assert rows == []
    assert summary["run_id"] == runner.V3_8_1_EVIDENCE_SELECTOR_RUN_ID
    assert summary["status"] == "DIAGNOSTIC_EVIDENCE_SELECTOR_V1_COMPUTED"
    assert summary["run_class"] == "diagnostic_only_evidence_selector_v1"
    assert summary["source_run_id"] == runner.V3_7_2_SOURCE_REGISTRY_BACKED_RETRIEVAL_SMOKE_REPORT_RUN_ID
    assert summary["parent_file_grounded_eval_run_id"] == runner.V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID
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
    assert summary["source_atom_registry_canonical_truth_used_for_selection"] is True
    assert summary["selector_uses_target_source_atom_ids_for_selection"] is False
    assert summary["target_source_atom_ids_used_for_metrics_only"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["xlsx_pdf_collapsed_score_reported"] is False
    assert set(summary["per_source_family"]) == {"PDF", "XLSX"}
    assert summary["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert summary["fail_closed_reasons"] == []
    assert summary["artifact_paths"]["summary_json"].endswith("_v3_8_1_evidence_selector_v1_summary.json")
    assert summary["artifact_paths"]["metrics_json"].endswith("_v3_8_1_evidence_selector_v1_metrics.json")
    assert summary["artifact_paths"]["per_query_jsonl"].endswith("_v3_8_1_evidence_selector_v1_per_query.jsonl")
    assert summary["artifact_paths"]["per_family_json"].endswith("_v3_8_1_evidence_selector_v1_per_family.json")


def test_v3_8_2_oracle_free_file_resolver_ignores_gold_target_ids_for_selection() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_allowed_budget": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
        },
        "atom_forbidden_gold": {
            "source_family": "XLSX",
            "source_identity": "docv_secret:secret_target.xlsx:Sheet1:A1:B2:B2",
            "raw_locator": {
                "workbook": "secret_target.xlsx",
                "document_version_id": "docv_secret",
                "sheet": "Sheet1",
                "range": "A1:B2",
                "cell": "B2",
            },
            "workbook_id": "secret_target.xlsx",
            "workbook_version_id": "docv_secret",
        },
    }
    row = {
        "query_id": "oracle_free_ignore_gold",
        "query_text": "budget.xlsx 파일의 Summary 시트 C4 값을 알려줘",
        "source_family": "XLSX",
        "target_source_atom_ids": ["atom_forbidden_gold"],
        "target_search_view_ids": ["sv_forbidden_gold"],
        "question_gold_locator_target": {
            "file": "secret_target.xlsx",
            "sheet": "Sheet1",
            "matched_cells": ["B2"],
        },
        "official_manifest_target": {
            "source_identity": "docv_secret:secret_target.xlsx:Sheet1:A1:B2:B2",
        },
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_allowed_budget",
                "source_atom_id": "atom_allowed_budget",
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
            {
                "rank": 2,
                "search_view_id": "sv_forbidden_gold",
                "source_atom_id": "atom_forbidden_gold",
                "source_family": "XLSX",
                "source_identity": "docv_secret:secret_target.xlsx:Sheet1:A1:B2:B2",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
        ],
    }

    resolved = runner.v3_8_2_oracle_free_file_resolve(row, source_registry=source_registry)

    assert resolved["oracle_free"] is True
    assert resolved["resolve_status"] == "resolved"
    assert resolved["oracle_free_input_violation_count"] == 0
    assert resolved["forbidden_input_fields_used"] == []
    assert resolved["candidates"][0]["source_file_name"] == "budget.xlsx"
    assert resolved["candidates"][0]["document_version_id"] == "docv_budget"
    assert resolved["candidates"][0]["oracle_free"] is True
    assert "query_file_name_mention" in resolved["candidates"][0]["resolve_reasons"]
    assert all(
        "target_source_atom_ids" not in reason
        and "question_gold_locator_target" not in reason
        and "official_manifest_target" not in reason
        for candidate in resolved["candidates"]
        for reason in candidate["resolve_reasons"]
    )
    guarded = runner.V3_8_2OracleFreeInputGuard(row)
    assert guarded.get("target_source_atom_ids") is None
    assert guarded.get("question_gold_locator_target") is None
    with pytest.raises(KeyError):
        _ = guarded["official_manifest_target"]
    assert guarded.forbidden_input_fields_used() == [
        "target_source_atom_ids",
        "question_gold_locator_target",
        "official_manifest_target",
    ]


def test_v3_8_2_file_resolve_metrics_keep_pdf_xlsx_denominators_separate() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_xlsx_target": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_xlsx",
        },
        "atom_pdf_target": {
            "source_family": "PDF",
            "source_identity": "docv_pdf:local-storage/input/report.pdf:3:[1, 2, 3, 4]",
            "document_version_id": "docv_pdf",
            "raw_locator": {
                "source_file_id": "pdf-file-1",
                "source_pdf_filename": "report.pdf",
                "source_pdf_path": "D:/repo/report.pdf",
                "document_version_id": "docv_pdf",
                "page": 3,
            },
        },
    }
    topk_rows = [
        {
            "query_id": "xlsx_resolve_q1",
            "query_text": "budget.xlsx Summary C4 값",
            "source_family": "XLSX",
            "target_source_atom_ids": ["atom_xlsx_target"],
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_xlsx_target",
                    "source_atom_id": "atom_xlsx_target",
                    "source_family": "XLSX",
                    "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
        {
            "query_id": "pdf_resolve_q1",
            "query_text": "report.pdf 3페이지 내용",
            "source_family": "PDF",
            "target_source_atom_ids": ["atom_pdf_target"],
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_pdf_target",
                    "source_atom_id": "atom_pdf_target",
                    "source_family": "PDF",
                    "source_identity": "docv_pdf:local-storage/input/report.pdf:3:[1, 2, 3, 4]",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
    ]

    metrics = runner.v3_8_2_oracle_free_file_resolve_metrics(
        topk_rows,
        source_registry=source_registry,
    )

    assert metrics["run_id"] == runner.V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID
    assert metrics["headline_aggregate_score_reported"] is False
    assert metrics["answer_generation_metric_computed"] is False
    assert metrics["gold_or_label_mutation"] is False
    assert metrics["denominator_policy"]["xlsx_and_pdf_are_not_collapsed"] is True
    assert set(metrics["per_source_family"]) == {"PDF", "XLSX"}
    assert metrics["per_source_family"]["XLSX"]["query_count"] == 1
    assert metrics["per_source_family"]["PDF"]["query_count"] == 1
    assert metrics["per_source_family"]["XLSX"]["metrics"]["file_resolve@1"]["rate"] == 1.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["file_resolve@1"]["rate"] == 1.0
    assert metrics["per_source_family"]["XLSX"]["metrics"]["file_resolve@3"]["rate"] == 1.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["file_resolve@3"]["rate"] == 1.0
    assert metrics["per_source_family"]["XLSX"]["metrics"]["abstain_rate"]["rate"] == 0.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["abstain_rate"]["rate"] == 0.0
    assert metrics["per_source_family"]["XLSX"]["metrics"]["wrong_file_block_rate"]["rate"] == 0.0
    assert metrics["per_source_family"]["PDF"]["metrics"]["wrong_file_block_rate"]["rate"] == 0.0
    assert metrics["oracle_free_input_violation_count"] == 0


def test_v3_8_2_file_resolver_abstains_and_blocks_wrong_file_without_oracle_free_evidence() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_pdf_target": {
            "source_family": "PDF",
            "source_identity": "docv_target:local-storage/input/target.pdf:3:[1, 2, 3, 4]",
            "document_version_id": "docv_target",
            "raw_locator": {
                "source_file_id": "target-file-id",
                "source_pdf_filename": "target.pdf",
                "source_pdf_path": "D:/repo/target.pdf",
                "document_version_id": "docv_target",
                "page": 3,
            },
        },
        "atom_pdf_wrong": {
            "source_family": "PDF",
            "source_identity": "docv_wrong:local-storage/input/wrong.pdf:9:[5, 6, 7, 8]",
            "document_version_id": "docv_wrong",
            "raw_locator": {
                "source_file_id": "wrong-file-id",
                "source_pdf_filename": "wrong.pdf",
                "source_pdf_path": "D:/repo/wrong.pdf",
                "document_version_id": "docv_wrong",
                "page": 9,
            },
        },
    }
    row = {
        "query_id": "pdf_wrong_block_q1",
        "query_text": "2월 실업률은 전년 같은 달보다 어떻게 변했나요?",
        "source_family": "PDF",
        "target_source_atom_ids": ["atom_pdf_target"],
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_pdf_wrong",
                "source_atom_id": "atom_pdf_wrong",
                "source_family": "PDF",
                "source_identity": "docv_wrong:local-storage/input/wrong.pdf:9:[5, 6, 7, 8]",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            }
        ],
    }

    per_query = runner.v3_8_2_file_resolve_per_query_row(
        row,
        source_registry=source_registry,
        top_k=3,
    )

    assert per_query["resolve_status"] == "abstain"
    assert per_query["abstain_rate"] is True
    assert per_query["file_resolve@1"] is False
    assert per_query["file_resolve@3"] is False
    assert per_query["wrong_file_block_rate"] is True
    assert per_query["resolved_file_candidates"][0]["source_file_name"] == "wrong.pdf"
    assert per_query["resolved_file_candidates"][0]["oracle_free"] is True
    assert per_query["metric_overlay_redacted_from_candidate_artifact"] is True
    assert "metric_target_file_identity" not in per_query
    assert "target_source_atom_ids" not in per_query
    assert "official_manifest_target" not in per_query
    assert "low_oracle_free_confidence" in per_query["resolve_block_reasons"]


def test_v3_8_2_run_measurement_wires_oracle_free_summary_without_answer_generation() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    args = runner.parse_args(["--run-id", runner.V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID])

    summary, rows = runner.run_measurement(args)

    assert rows == []
    assert summary["run_id"] == runner.V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID
    assert summary["status"] == "DIAGNOSTIC_ORACLE_FREE_FILE_RESOLVE_COMPUTED"
    assert summary["run_class"] == "diagnostic_only_oracle_free_file_resolve_v1"
    assert summary["source_run_id"] == runner.V3_7_2_SOURCE_REGISTRY_BACKED_RETRIEVAL_SMOKE_REPORT_RUN_ID
    assert summary["parent_file_grounded_eval_run_id"] == runner.V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID
    assert summary["parent_evidence_selector_run_id"] == runner.V3_8_1_EVIDENCE_SELECTOR_RUN_ID
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
    assert summary["resolver_uses_target_source_atom_ids_for_selection"] is False
    assert summary["target_source_atom_ids_used_for_metrics_only"] is True
    assert summary["source_atom_registry_canonical_truth_used_for_resolution"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["xlsx_pdf_collapsed_score_reported"] is False
    assert set(summary["per_source_family"]) == {"PDF", "XLSX"}
    assert summary["source_family_counts"] == {"PDF": 329, "XLSX": 344}
    assert summary["oracle_free_input_violation_count"] == 0
    assert summary["fail_closed_reasons"] == []
    assert summary["artifact_paths"]["summary_json"].endswith("_v3_8_2_oracle_free_file_resolve_summary.json")
    assert summary["artifact_paths"]["metrics_json"].endswith("_v3_8_2_oracle_free_file_resolve_metrics.json")
    assert summary["artifact_paths"]["per_query_jsonl"].endswith("_v3_8_2_oracle_free_file_resolve_per_query.jsonl")
    assert summary["artifact_paths"]["per_family_json"].endswith("_v3_8_2_oracle_free_file_resolve_per_family.json")


def test_v3_8_3_xlsx_scoped_cell_resolver_uses_v3_8_2_gate_not_gold_target_ids() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_allowed_budget": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "41786",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
            "normalized_text_or_value_snapshot": "41786",
        },
        "atom_forbidden_gold": {
            "source_family": "XLSX",
            "source_identity": "docv_secret:secret_target.xlsx:Sheet1:A1:B2:B2",
            "raw_locator": {
                "workbook": "secret_target.xlsx",
                "document_version_id": "docv_secret",
                "sheet": "Sheet1",
                "range": "A1:B2",
                "cell": "B2",
                "normalized_value": "999",
            },
            "workbook_id": "secret_target.xlsx",
            "workbook_version_id": "docv_secret",
            "normalized_text_or_value_snapshot": "999",
        },
    }
    row = {
        "query_id": "xlsx_scope_ignore_gold",
        "query_text": "secret_target.xlsx 파일의 Sheet1 시트 B2 값을 알려줘",
        "source_family": "XLSX",
        "target_source_atom_ids": ["atom_forbidden_gold"],
        "target_search_view_ids": ["sv_forbidden_gold"],
        "question_gold_locator_target": {
            "file": "secret_target.xlsx",
            "sheet": "Sheet1",
            "matched_cells": ["B2"],
        },
        "official_manifest_target": {
            "source_identity": "docv_secret:secret_target.xlsx:Sheet1:A1:B2:B2",
        },
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_forbidden_gold",
                "source_atom_id": "atom_forbidden_gold",
                "source_family": "XLSX",
                "source_identity": "docv_secret:secret_target.xlsx:Sheet1:A1:B2:B2",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
            {
                "rank": 2,
                "search_view_id": "sv_allowed_budget",
                "source_atom_id": "atom_allowed_budget",
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
        ],
    }
    file_gate_row = {
        "query_id": "xlsx_scope_ignore_gold",
        "source_family": "XLSX",
        "resolve_status": "resolved",
        "resolve_block_reasons": [],
        "resolved_file_candidates": [
            {
                "candidate_rank": 1,
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                "source_file_name": "budget.xlsx",
                "document_version_id": "docv_budget",
                "workbook_version_id": "docv_budget",
                "resolve_score": 0.92,
                "resolve_reasons": ["persisted_v3_8_2_gate"],
                "oracle_free": True,
            }
        ],
        "oracle_free_input_violation_count": 0,
        "oracle_free": True,
    }

    resolved = runner.v3_8_3_xlsx_scoped_cell_resolve(
        row,
        source_registry=source_registry,
        file_gate_row=file_gate_row,
    )

    assert resolved["oracle_free"] is True
    assert resolved["resolve_status"] == "resolved"
    assert resolved["oracle_free_input_violation_count"] == 0
    assert resolved["workbook_gate"]["source_file_name"] == "budget.xlsx"
    assert resolved["candidates"][0]["workbook"] == "budget.xlsx"
    assert resolved["candidates"][0]["sheet"] == "Summary"
    assert resolved["candidates"][0]["range"] == "A1:D10"
    assert resolved["candidates"][0]["cell"] == "C4"
    assert resolved["candidates"][0]["matched_text_or_value_present"] is True
    assert resolved["candidates"][0]["matched_text_or_value_sha256"]
    assert resolved["candidates"][0]["oracle_free"] is True
    assert "matched_text_or_value" not in resolved["candidates"][0]
    assert "normalized_value" not in resolved["candidates"][0]
    assert "target_source_atom_ids" not in resolved["candidates"][0]
    assert "official_manifest_target" not in resolved["candidates"][0]


def test_v3_8_3_xlsx_scoped_cell_resolver_promotes_query_locator_signal_inside_gate() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_rank1": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:A1",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "A1",
                "normalized_value": "header",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
            "normalized_text_or_value_snapshot": "header",
        },
        "atom_query_cell": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:B2",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "B2",
                "normalized_value": "41786",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
            "normalized_text_or_value_snapshot": "41786",
        },
    }
    row = {
        "query_id": "xlsx_query_locator_signal",
        "query_text": "budget.xlsx Summary 시트 B2 셀을 확인해줘",
        "source_family": "XLSX",
        "target_source_atom_ids": ["atom_rank1"],
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_rank1",
                "source_atom_id": "atom_rank1",
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:A1",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
            {
                "rank": 2,
                "search_view_id": "sv_query_cell",
                "source_atom_id": "atom_query_cell",
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:B2",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
        ],
    }
    file_gate_row = {
        "query_id": "xlsx_query_locator_signal",
        "source_family": "XLSX",
        "resolve_status": "resolved",
        "resolve_block_reasons": [],
        "resolved_file_candidates": [
            {
                "candidate_rank": 1,
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:A1",
                "source_file_name": "budget.xlsx",
                "document_version_id": "docv_budget",
                "workbook_version_id": "docv_budget",
                "resolve_score": 0.93,
                "resolve_reasons": ["persisted_v3_8_2_gate"],
                "oracle_free": True,
            }
        ],
        "oracle_free_input_violation_count": 0,
        "oracle_free": True,
    }

    resolved = runner.v3_8_3_xlsx_scoped_cell_resolve(
        row,
        source_registry=source_registry,
        file_gate_row=file_gate_row,
    )

    assert resolved["resolve_status"] == "resolved"
    assert resolved["candidates"][0]["source_atom_id"] == "atom_query_cell"
    assert resolved["candidates"][0]["cell"] == "B2"
    assert resolved["candidates"][0]["query_locator_signal_count"] >= 2
    assert set(resolved["candidates"][0]["query_locator_signals"]) >= {
        "query_sheet_literal_match",
        "query_cell_literal_match",
    }
    assert "target_source_atom_ids" not in resolved["candidates"][0]


def test_v3_8_3_xlsx_scoped_cell_resolver_prefers_structural_specificity_over_rank() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_rank1_generic": {
            "source_family": "XLSX",
            "source_identity": "docv_rail:rail.xlsx:철도:A2:D51:D2",
            "raw_locator": {
                "workbook": "rail.xlsx",
                "document_version_id": "docv_rail",
                "sheet": "철도",
                "range": "A2:D51",
                "cell": "D2",
                "row_label": "노선명=1호선",
                "column_label": "승차총승객수",
                "target_column": "승차총승객수",
                "normalized_value": "111",
            },
            "workbook_id": "rail.xlsx",
            "workbook_version_id": "docv_rail",
            "normalized_text_or_value_snapshot": "111",
        },
        "atom_rank2_specific": {
            "source_family": "XLSX",
            "source_identity": "docv_rail:rail.xlsx:철도:A552:D601:D552",
            "raw_locator": {
                "workbook": "rail.xlsx",
                "document_version_id": "docv_rail",
                "sheet": "철도",
                "range": "A552:D601",
                "cell": "D552",
                "row_label": "노선명=1호선 | 기준월=2019년 5월",
                "column_label": "승차총승객수",
                "target_column": "승차총승객수",
                "normalized_value": "222",
            },
            "workbook_id": "rail.xlsx",
            "workbook_version_id": "docv_rail",
            "normalized_text_or_value_snapshot": "222",
        },
    }
    row = {
        "query_id": "xlsx_structural_specificity",
        "query_text": "철도 기준월 2019년 5월 1호선 승차총승객수",
        "source_family": "XLSX",
        "target_source_atom_ids": ["atom_rank1_generic"],
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_generic",
                "source_atom_id": "atom_rank1_generic",
                "source_family": "XLSX",
                "source_identity": "docv_rail:rail.xlsx:철도:A2:D51:D2",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
            {
                "rank": 2,
                "search_view_id": "sv_specific",
                "source_atom_id": "atom_rank2_specific",
                "source_family": "XLSX",
                "source_identity": "docv_rail:rail.xlsx:철도:A552:D601:D552",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
        ],
    }
    file_gate_row = {
        "query_id": "xlsx_structural_specificity",
        "source_family": "XLSX",
        "resolve_status": "resolved",
        "resolved_file_candidates": [
            {
                "candidate_rank": 1,
                "source_family": "XLSX",
                "source_identity": "docv_rail:rail.xlsx:철도:A2:D51:D2",
                "source_file_name": "rail.xlsx",
                "document_version_id": "docv_rail",
                "workbook_version_id": "docv_rail",
                "resolve_score": 0.91,
                "oracle_free": True,
            }
        ],
        "oracle_free_input_violation_count": 0,
        "oracle_free": True,
    }

    resolved = runner.v3_8_3_xlsx_scoped_cell_resolve(
        row,
        source_registry=source_registry,
        file_gate_row=file_gate_row,
    )

    assert resolved["resolve_status"] == "resolved"
    assert resolved["candidates"][0]["source_atom_id"] == "atom_rank2_specific"
    assert "query_row_label_key_value_pair_match" in resolved["candidates"][0]["query_locator_signals"]
    assert resolved["candidates"][0]["structural_specificity_rank"] > resolved["candidates"][1]["structural_specificity_rank"]
    assert "normalized_value" not in resolved["candidates"][0]
    assert "target_source_atom_ids" not in resolved["candidates"][0]


def test_v3_8_3_xlsx_scoped_cell_metrics_keep_xlsx_denominator_and_v3_8_2_gate() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_xlsx_target": {
            "source_family": "XLSX",
            "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_xlsx",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "41786",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_xlsx",
            "normalized_text_or_value_snapshot": "41786",
        },
        "atom_pdf_target": {
            "source_family": "PDF",
            "source_identity": "docv_pdf:local-storage/input/report.pdf:3:[1, 2, 3, 4]",
            "document_version_id": "docv_pdf",
            "raw_locator": {"source_pdf_filename": "report.pdf", "page": 3},
        },
    }
    topk_rows = [
        {
            "query_id": "xlsx_scope_q1",
            "query_text": "budget.xlsx Summary C4 값",
            "source_family": "XLSX",
            "target_source_atom_ids": ["atom_xlsx_target"],
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_xlsx_target",
                    "source_atom_id": "atom_xlsx_target",
                    "source_family": "XLSX",
                    "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
        {
            "query_id": "pdf_ignored_q1",
            "query_text": "report.pdf 3페이지 내용",
            "source_family": "PDF",
            "target_source_atom_ids": ["atom_pdf_target"],
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_pdf_target",
                    "source_atom_id": "atom_pdf_target",
                    "source_family": "PDF",
                    "source_identity": "docv_pdf:local-storage/input/report.pdf:3:[1, 2, 3, 4]",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
    ]
    file_gate_rows = [
        {
            "query_id": "xlsx_scope_q1",
            "source_family": "XLSX",
            "resolve_status": "resolved",
            "resolve_block_reasons": [],
            "resolved_file_candidates": [
                {
                    "candidate_rank": 1,
                    "source_family": "XLSX",
                    "source_identity": "docv_xlsx:budget.xlsx:Summary:A1:D10:C4",
                    "source_file_name": "budget.xlsx",
                    "document_version_id": "docv_xlsx",
                    "workbook_version_id": "docv_xlsx",
                    "resolve_score": 0.91,
                    "resolve_reasons": ["persisted_v3_8_2_gate"],
                    "oracle_free": True,
                }
            ],
            "oracle_free_input_violation_count": 0,
            "oracle_free": True,
        },
        {
            "query_id": "pdf_ignored_q1",
            "source_family": "PDF",
            "resolve_status": "resolved",
            "resolved_file_candidates": [
                {
                    "candidate_rank": 1,
                    "source_family": "PDF",
                    "source_file_name": "report.pdf",
                    "document_version_id": "docv_pdf",
                    "oracle_free": True,
                }
            ],
            "oracle_free_input_violation_count": 0,
            "oracle_free": True,
        },
    ]

    metrics = runner.v3_8_3_xlsx_scoped_cell_resolve_metrics(
        topk_rows,
        source_registry=source_registry,
        file_gate_rows=file_gate_rows,
    )

    assert metrics["run_id"] == runner.V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID
    assert metrics["parent_file_resolve_run_id"] == runner.V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID
    assert metrics["source_families_reported_separately"] == ["XLSX"]
    assert metrics["headline_aggregate_score_reported"] is False
    assert metrics["answer_generation_metric_computed"] is False
    assert metrics["gold_or_label_mutation"] is False
    assert metrics["denominator_policy"]["xlsx_only_denominator"] is True
    assert metrics["denominator_policy"]["pdf_rows_excluded"] is True
    assert metrics["all_xlsx_query_count"] == 1
    assert metrics["v3_8_2_gate_row_found_count"] == 1
    assert metrics["v3_8_2_gate_resolved_count"] == 1
    assert metrics["v3_8_2_gate_missing_count"] == 0
    assert metrics["per_source_family"]["XLSX"]["query_count"] == 1
    xlsx = metrics["per_source_family"]["XLSX"]["metrics"]
    assert xlsx["sheet_resolve@1"]["rate"] == 1.0
    assert xlsx["sheet_resolve@3"]["rate"] == 1.0
    assert xlsx["table_or_range_resolve@1"]["rate"] == 1.0
    assert xlsx["table_or_range_resolve@3"]["rate"] == 1.0
    assert xlsx["cell_or_value_resolve@1"]["rate"] == 1.0
    assert xlsx["cell_or_value_resolve@3"]["rate"] == 1.0
    assert xlsx["abstain_rate"]["rate"] == 0.0
    assert metrics["oracle_free_input_violation_count"] == 0


def test_v3_8_3_xlsx_miss_taxonomy_partitions_query_and_family_diagnostics() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_target": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "41786",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
            "normalized_text_or_value_snapshot": "41786",
        },
        "atom_wrong_sheet": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Other:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Other",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "41786",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
            "normalized_text_or_value_snapshot": "41786",
        },
        "atom_wrong_range": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Summary:E1:H10:G4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Summary",
                "range": "E1:H10",
                "cell": "G4",
                "normalized_value": "90000",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
            "normalized_text_or_value_snapshot": "90000",
        },
    }
    topk_rows = [
        {
            "query_id": "cell_hit",
            "query_text": "Summary C4 값",
            "source_family": "XLSX",
            "target_source_atom_ids": ["atom_target"],
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_target",
                    "source_atom_id": "atom_target",
                    "source_family": "XLSX",
                    "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
        {
            "query_id": "sheet_miss",
            "query_text": "Summary C4 값",
            "source_family": "XLSX",
            "target_source_atom_ids": ["atom_target"],
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_wrong_sheet",
                    "source_atom_id": "atom_wrong_sheet",
                    "source_family": "XLSX",
                    "source_identity": "docv_budget:budget.xlsx:Other:A1:D10:C4",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
        {
            "query_id": "range_miss",
            "query_text": "Summary C4 값",
            "source_family": "XLSX",
            "target_source_atom_ids": ["atom_target"],
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_wrong_range",
                    "source_atom_id": "atom_wrong_range",
                    "source_family": "XLSX",
                    "source_identity": "docv_budget:budget.xlsx:Summary:E1:H10:G4",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
        {
            "query_id": "gate_disambiguation",
            "query_text": "workbook 후보가 애매해",
            "source_family": "XLSX",
            "target_source_atom_ids": ["atom_target"],
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": "sv_target_again",
                    "source_atom_id": "atom_target",
                    "source_family": "XLSX",
                    "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        },
    ]
    resolved_gate = {
        "source_family": "XLSX",
        "resolve_status": "resolved",
        "resolve_block_reasons": [],
        "resolved_file_candidates": [
            {
                "candidate_rank": 1,
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                "source_file_name": "budget.xlsx",
                "document_version_id": "docv_budget",
                "workbook_version_id": "docv_budget",
                "oracle_free": True,
            }
        ],
        "oracle_free_input_violation_count": 0,
        "oracle_free": True,
    }
    file_gate_rows = [
        {"query_id": "cell_hit", **resolved_gate},
        {"query_id": "sheet_miss", **resolved_gate},
        {"query_id": "range_miss", **resolved_gate},
        {
            "query_id": "gate_disambiguation",
            "source_family": "XLSX",
            "resolve_status": "disambiguation",
            "resolve_block_reasons": ["ambiguous_oracle_free_candidates"],
            "resolved_file_candidates": [],
            "oracle_free_input_violation_count": 0,
            "oracle_free": True,
        },
    ]

    metrics = runner.v3_8_3_xlsx_scoped_cell_resolve_metrics(
        topk_rows,
        source_registry=source_registry,
        file_gate_rows=file_gate_rows,
    )

    rows_by_query = {row["query_id"]: row for row in metrics["per_query_rows"]}
    assert rows_by_query["cell_hit"]["xlsx_miss_taxonomy"]["primary_category"] == "cell_or_value_resolved_at_rank_1"
    assert rows_by_query["sheet_miss"]["xlsx_miss_taxonomy"]["primary_category"] == "sheet_miss_after_workbook_gate"
    assert rows_by_query["range_miss"]["xlsx_miss_taxonomy"]["primary_category"] == "table_or_range_miss_after_sheet_hit"
    assert rows_by_query["gate_disambiguation"]["xlsx_miss_taxonomy"]["primary_category"] == "workbook_gate_disambiguation"

    family_taxonomy = metrics["per_source_family"]["XLSX"]["miss_taxonomy"]
    assert family_taxonomy["primary_category_counts"] == {
        "cell_or_value_resolved_at_rank_1": 1,
        "sheet_miss_after_workbook_gate": 1,
        "table_or_range_miss_after_sheet_hit": 1,
        "workbook_gate_disambiguation": 1,
    }
    assert metrics["per_family_rows"][0]["source_family"] == "XLSX"
    assert metrics["per_family_rows"][0]["miss_taxonomy"] == family_taxonomy


def test_v3_8_3_xlsx_scoped_cell_resolver_abstains_after_wrong_workbook_gate() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_xlsx_target": {
            "source_family": "XLSX",
            "source_identity": "docv_target:target.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "target.xlsx",
                "document_version_id": "docv_target",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
            },
            "workbook_version_id": "docv_target",
        },
        "atom_xlsx_wrong": {
            "source_family": "XLSX",
            "source_identity": "docv_wrong:wrong.xlsx:Sheet1:A1:B2:B2",
            "raw_locator": {
                "workbook": "wrong.xlsx",
                "document_version_id": "docv_wrong",
                "sheet": "Sheet1",
                "range": "A1:B2",
                "cell": "B2",
            },
            "workbook_version_id": "docv_wrong",
        },
    }
    row = {
        "query_id": "xlsx_scope_wrong_gate",
        "query_text": "시트에서 C4 값을 알려줘",
        "source_family": "XLSX",
        "target_source_atom_ids": ["atom_xlsx_target"],
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_target",
                "source_atom_id": "atom_xlsx_target",
                "source_family": "XLSX",
                "source_identity": "docv_target:target.xlsx:Summary:A1:D10:C4",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            }
        ],
    }
    file_gate_row = {
        "query_id": "xlsx_scope_wrong_gate",
        "source_family": "XLSX",
        "resolve_status": "abstain",
        "resolve_block_reasons": ["low_oracle_free_confidence"],
        "resolved_file_candidates": [
            {
                "candidate_rank": 1,
                "source_family": "XLSX",
                "source_identity": "docv_wrong:wrong.xlsx:Sheet1:A1:B2:B2",
                "source_file_name": "wrong.xlsx",
                "document_version_id": "docv_wrong",
                "workbook_version_id": "docv_wrong",
                "resolve_score": 0.12,
                "resolve_reasons": ["persisted_v3_8_2_gate"],
                "oracle_free": True,
            }
        ],
        "oracle_free_input_violation_count": 0,
        "oracle_free": True,
    }

    per_query = runner.v3_8_3_xlsx_scoped_cell_resolve_per_query_row(
        row,
        source_registry=source_registry,
        top_k=3,
        file_gate_row=file_gate_row,
    )

    assert per_query["resolve_status"] == "abstain"
    assert per_query["abstain_rate"] is True
    assert per_query["sheet_resolve@1"] is False
    assert per_query["table_or_range_resolve@1"] is False
    assert per_query["cell_or_value_resolve@1"] is False
    assert per_query["wrong_workbook_block_rate"] is True
    assert per_query["scoped_cell_candidates"] == []
    assert "low_oracle_free_confidence" in per_query["resolve_block_reasons"]
    assert per_query["metric_overlay_redacted_from_candidate_artifact"] is True


def test_v3_8_3_xlsx_scoped_cell_resolver_fails_closed_on_parent_gate_forbidden_inputs() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_budget": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "normalized_value": "41786",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
            "normalized_text_or_value_snapshot": "41786",
        }
    }
    row = {
        "query_id": "xlsx_scope_parent_gate_leak",
        "query_text": "budget.xlsx Summary C4 값",
        "source_family": "XLSX",
        "target_source_atom_ids": ["atom_budget"],
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_budget",
                "source_atom_id": "atom_budget",
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            }
        ],
    }
    file_gate_row = {
        "query_id": "xlsx_scope_parent_gate_leak",
        "source_family": "XLSX",
        "resolve_status": "resolved",
        "resolve_block_reasons": [],
        "resolved_file_candidates": [
            {
                "candidate_rank": 1,
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                "source_file_name": "budget.xlsx",
                "document_version_id": "docv_budget",
                "workbook_version_id": "docv_budget",
                "resolve_score": 0.92,
                "resolve_reasons": ["persisted_v3_8_2_gate"],
                "oracle_free": True,
            }
        ],
        "forbidden_input_fields_used": ["expected_answer"],
        "oracle_free_input_violation_count": 1,
        "oracle_free": True,
    }

    resolved = runner.v3_8_3_xlsx_scoped_cell_resolve(
        row,
        source_registry=source_registry,
        file_gate_row=file_gate_row,
    )

    assert resolved["resolve_status"] == "abstain"
    assert resolved["oracle_free_input_violation_count"] == 1
    assert resolved["candidates"] == []
    assert resolved["forbidden_input_fields_used"] == ["expected_answer"]
    assert "oracle_free_input_violation_count" in resolved["resolve_block_reasons"]


def test_v3_8_3_xlsx_scoped_cell_resolver_abstains_without_usable_sheet_range_candidates() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    row = {
        "query_id": "xlsx_scope_no_usable_locator",
        "query_text": "budget workbook 안의 Summary 값을 확인해줘",
        "source_family": "XLSX",
        "target_source_atom_ids": [],
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_budget_no_range",
                "source_atom_id": "atom_budget_no_range",
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            }
        ],
    }
    file_gate_row = {
        "query_id": "xlsx_scope_no_usable_locator",
        "source_family": "XLSX",
        "resolve_status": "resolved",
        "resolve_block_reasons": [],
        "resolved_file_candidates": [
            {
                "candidate_rank": 1,
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx",
                "source_file_name": "budget.xlsx",
                "document_version_id": "docv_budget",
                "workbook_version_id": "docv_budget",
                "resolve_score": 0.88,
                "resolve_reasons": ["persisted_v3_8_2_gate"],
                "oracle_free": True,
            }
        ],
        "oracle_free_input_violation_count": 0,
        "oracle_free": True,
    }

    resolved = runner.v3_8_3_xlsx_scoped_cell_resolve(
        row,
        source_registry={},
        file_gate_row=file_gate_row,
    )

    assert resolved["resolve_status"] == "abstain"
    assert resolved["candidates"] == []
    assert "no_xlsx_scoped_cell_candidates_after_workbook_gate" in resolved["resolve_block_reasons"]


def test_v3_8_3_xlsx_structural_row_column_signals_rank_generic_candidates() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    source_registry = {
        "atom_wrong_rank1": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Summary",
                "range": "A1:D10",
                "cell": "C4",
                "row_label": "부서=영업1팀 | 월=202601",
                "target_column": "예산",
                "normalized_value": "1100",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
            "normalized_text_or_value_snapshot": "영업1팀 예산 1100",
        },
        "atom_query_row": {
            "source_family": "XLSX",
            "source_identity": "docv_budget:budget.xlsx:Summary:A11:D20:D14",
            "raw_locator": {
                "workbook": "budget.xlsx",
                "document_version_id": "docv_budget",
                "sheet": "Summary",
                "range": "A11:D20",
                "cell": "D14",
                "row_label": "부서=전략기획팀 | 월=202602",
                "target_column": "집행액",
                "normalized_value": "41786",
            },
            "workbook_id": "budget.xlsx",
            "workbook_version_id": "docv_budget",
            "normalized_text_or_value_snapshot": "전략기획팀 집행액 41786",
        },
    }
    row = {
        "query_id": "xlsx_scope_generic_row_column",
        "query_text": "budget.xlsx Summary에서 2026년 2월 전략기획팀 집행액을 확인해줘",
        "source_family": "XLSX",
        "target_source_atom_ids": ["atom_query_row"],
        "top_result_envelopes": [
            {
                "rank": 1,
                "search_view_id": "sv_wrong_rank1",
                "source_atom_id": "atom_wrong_rank1",
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
            {
                "rank": 2,
                "search_view_id": "sv_query_row",
                "source_atom_id": "atom_query_row",
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A11:D20:D14",
                "source_atom_hydrated_from_registry": True,
                "evidence_bundle_render_valid": True,
                "citation_render_valid": True,
            },
        ],
    }
    file_gate_row = {
        "query_id": "xlsx_scope_generic_row_column",
        "source_family": "XLSX",
        "resolve_status": "resolved",
        "resolve_block_reasons": [],
        "resolved_file_candidates": [
            {
                "candidate_rank": 1,
                "source_family": "XLSX",
                "source_identity": "docv_budget:budget.xlsx:Summary:A1:D10:C4",
                "source_file_name": "budget.xlsx",
                "document_version_id": "docv_budget",
                "workbook_version_id": "docv_budget",
                "resolve_score": 0.92,
                "resolve_reasons": ["persisted_v3_8_2_gate"],
                "oracle_free": True,
            }
        ],
        "oracle_free_input_violation_count": 0,
        "oracle_free": True,
    }

    resolved = runner.v3_8_3_xlsx_scoped_cell_resolve(
        row,
        source_registry=source_registry,
        file_gate_row=file_gate_row,
    )

    assert resolved["resolve_status"] == "resolved"
    assert resolved["candidates"][0]["source_atom_id"] == "atom_query_row"
    assert resolved["candidates"][0]["range"] == "A11:D20"
    assert set(resolved["candidates"][0]["query_locator_signals"]) >= {
        "query_row_label_value_match",
        "query_column_label_match",
        "query_date_number_normalized_match",
    }
    assert "row_label" not in resolved["candidates"][0]
    assert "target_column" not in resolved["candidates"][0]
    assert "normalized_value" not in resolved["candidates"][0]


def test_v3_8_3_xlsx_query_locator_signals_normalize_page_sheet_names() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    signals = runner.v3_8_3_query_locator_signals(
        query_text="26페이지의 연령별 성별 수술 현황 수치를 찾아주세요.",
        workbook="generic.xlsx",
        sheet="26p",
        cell_range="A1:BE71",
        cell="A1",
    )

    assert "query_sheet_normalized_page_match" in signals


def test_v3_8_3_xlsx_scoped_metrics_split_validation_and_exclude_drift_headlines() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    def atom(atom_id: str, workbook: str, sheet: str, cell_range: str, cell: str, value: str) -> dict[str, Any]:
        return {
            "source_family": "XLSX",
            "source_identity": f"docv_{workbook}:{workbook}:{sheet}:{cell_range}:{cell}",
            "raw_locator": {
                "workbook": workbook,
                "document_version_id": f"docv_{workbook}",
                "sheet": sheet,
                "range": cell_range,
                "cell": cell,
                "normalized_value": value,
            },
            "workbook_id": workbook,
            "workbook_version_id": f"docv_{workbook}",
            "normalized_text_or_value_snapshot": value,
        }

    source_registry = {
        "atom_sealed": atom("atom_sealed", "sealed.xlsx", "Sheet1", "A1:B2", "B2", "10"),
        "atom_dev": atom("atom_dev", "dev.xlsx", "Sheet1", "A1:B2", "B2", "20"),
        "atom_val": atom("atom_val", "validation.xlsx", "Sheet1", "A1:B2", "B2", "30"),
        "atom_drift": atom("atom_drift", "validation.xlsx", "Sheet1", "A3:B4", "B4", "40"),
    }

    def topk_row(query_id: str, scope: str, atom_id: str, workbook: str, *, drift: bool = False) -> dict[str, Any]:
        query_text = "major topic drift" if drift else f"{workbook} Sheet1 B2 값"
        return {
            "query_id": query_id,
            "query_scope": scope,
            "query_text": query_text,
            "source_family": "XLSX",
            "target_source_atom_ids": [atom_id],
            "query_drift": drift,
            "silver_query_quality_profile": "major_topic_drift" if drift else "clean_source_grounded",
            "top_result_envelopes": [
                {
                    "rank": 1,
                    "search_view_id": f"sv_{atom_id}",
                    "source_atom_id": atom_id,
                    "source_family": "XLSX",
                    "source_identity": source_registry[atom_id]["source_identity"],
                    "source_atom_hydrated_from_registry": True,
                    "evidence_bundle_render_valid": True,
                    "citation_render_valid": True,
                }
            ],
        }

    def gate(query_id: str, atom_id: str, workbook: str) -> dict[str, Any]:
        return {
            "query_id": query_id,
            "source_family": "XLSX",
            "resolve_status": "resolved",
            "resolve_block_reasons": [],
            "resolved_file_candidates": [
                {
                    "candidate_rank": 1,
                    "source_family": "XLSX",
                    "source_identity": source_registry[atom_id]["source_identity"],
                    "source_file_name": workbook,
                    "document_version_id": f"docv_{workbook}",
                    "workbook_version_id": f"docv_{workbook}",
                    "resolve_score": 0.92,
                    "resolve_reasons": ["persisted_v3_8_2_gate"],
                    "oracle_free": True,
                }
            ],
            "oracle_free_input_violation_count": 0,
            "oracle_free": True,
        }

    metrics = runner.v3_8_3_xlsx_scoped_cell_resolve_metrics(
        [
            topk_row("sealed_q", "sealed_gold_no_regression_check", "atom_sealed", "sealed.xlsx"),
            topk_row("dev_q", "silver_1000_diagnostic_overlay", "atom_dev", "dev.xlsx"),
            topk_row("val_q", "silver_1000_diagnostic_overlay", "atom_val", "validation.xlsx"),
            topk_row("drift_q", "silver_1000_diagnostic_overlay", "atom_drift", "validation.xlsx", drift=True),
        ],
        source_registry=source_registry,
        file_gate_rows=[
            gate("sealed_q", "atom_sealed", "sealed.xlsx"),
            gate("dev_q", "atom_dev", "dev.xlsx"),
            gate("val_q", "atom_val", "validation.xlsx"),
            gate("drift_q", "atom_drift", "validation.xlsx"),
        ],
    )

    split = metrics["diagnostic_validation_split"]
    assert split["split_strategy"] == "workbook_disjoint_non_official_overlay"
    assert split["legacy_v3_8_3_rows_role"] == "dev_only_diagnostic_not_validation_success"
    assert split["protected_regression"]["query_count"] == 1
    assert split["dev"]["query_count"] == 1
    assert split["validation"]["query_count"] == 2
    assert split["validation"]["query_drift_excluded_count"] == 1
    assert split["validation"]["anchor_bound_query_count"] == 1
    assert split["validation"]["source_identity_disjoint_from_dev"] is True
    assert split["validation"]["workbook_disjoint_from_dev"] is True
    assert metrics["promotion_evidence"] is False
    assert metrics["official_metric_input_rows"] == 0


def test_v3_8_3_xlsx_scoped_resolver_has_no_query_id_or_file_title_hacks() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    checked_source = "\n".join(
        inspect.getsource(func)
        for func in (
            runner.v3_8_3_xlsx_scoped_cell_resolve,
            runner.v3_8_3_query_locator_signals,
            runner.v3_8_3_query_locator_signal_score,
            runner.v3_8_3_xlsx_diagnostic_validation_split,
        )
    )

    forbidden_fragments = [
        "gq_auto_",
        "v3_6_1_weak_noisy",
        "과학기술정보통신부",
        "국민건강보험공단",
        "서울시 대중교통",
        "제_1장",
        "rag-ingestion-sales.xlsx",
    ]
    assert not any(fragment in checked_source for fragment in forbidden_fragments)


def test_v3_8_3_run_measurement_wires_xlsx_scoped_cell_summary_without_answer_generation() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    args = runner.parse_args(["--run-id", runner.V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID])

    summary, rows = runner.run_measurement(args)

    assert rows == []
    assert summary["run_id"] == runner.V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID
    assert summary["status"] == "DIAGNOSTIC_XLSX_SCOPED_CELL_RESOLVE_COMPUTED"
    assert summary["run_class"] == "diagnostic_only_xlsx_scoped_cell_resolve_v1"
    assert summary["source_run_id"] == runner.V3_7_2_SOURCE_REGISTRY_BACKED_RETRIEVAL_SMOKE_REPORT_RUN_ID
    assert summary["parent_file_resolve_run_id"] == runner.V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID
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
    assert summary["xlsx_only"] is True
    assert summary["source_family_counts"] == {"XLSX": 344}
    assert summary["file_resolve_gate_run_id"] == runner.V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID
    assert summary["oracle_free_input_violation_count"] == 0
    assert summary["resolver_uses_target_source_atom_ids_for_selection"] is False
    assert summary["target_source_atom_ids_used_for_metrics_only"] is True
    assert summary["xlsx_pdf_collapsed_score_reported"] is False
    assert summary["diagnostic_validation_split"]["official_metric_input_rows"] == 0
    assert summary["diagnostic_validation_split"]["promotion_evidence"] is False
    assert summary["diagnostic_validation_split"]["validation"]["query_count"] > 0
    assert summary["diagnostic_validation_split"]["validation"]["source_identity_disjoint_from_dev"] is True
    assert summary["fail_closed_reasons"] == []
    assert summary["artifact_paths"]["summary_json"].endswith("_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_summary.json")
    assert summary["artifact_paths"]["metrics_json"].endswith("_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_metrics.json")
    assert summary["artifact_paths"]["per_query_jsonl"].endswith("_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_per_query.jsonl")
    assert summary["artifact_paths"]["per_family_json"].endswith("_v3_8_3_xlsx_scoped_cell_resolve_diagnostic_per_family.json")


def test_v3_9_1_xlsx_axis_signals_do_not_use_normalized_value_shortcuts() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    scoring_source = "\n".join(
        inspect.getsource(func)
        for func in (
            runner.v3_9_1_xlsx_axis_signals,
            runner.v3_9_1_xlsx_candidate_from_source_atom,
            runner.v3_9_1_xlsx_merge_candidates,
        )
    )

    assert "target_value" not in scoring_source
    assert "expected_answer" not in scoring_source
    assert "supporting_evidence" not in scoring_source
    assert "normalized_value=\"\"" in inspect.getsource(runner.v3_9_1_xlsx_axis_signals)

    signals, score = runner.v3_9_1_xlsx_axis_signals(
        query_text="2019년 2월 철도 승차총승객수와 5호선 행을 찾아주세요",
        workbook="",
        sheet="철도",
        cell_range="A1:D50",
        cell="D3",
        row_label="노선명=5호선 | 년월=201902",
        column_label="승차총승객수",
        target_column="승차총승객수",
    )

    assert "query_row_label_token_match" in signals
    assert "query_column_label_match" in signals
    assert score > 0


def test_v3_9_1_run_measurement_wires_xlsx_table_axis_pdf_file_identity_without_promotion() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    args = runner.parse_args(["--run-id", runner.V3_9_1_XLSX_SOURCEATOM_TABLE_AXIS_PDF_FILE_IDENTITY_RUN_ID])

    summary, rows = runner.run_measurement(args)

    assert rows == []
    assert summary["run_id"] == runner.V3_9_1_XLSX_SOURCEATOM_TABLE_AXIS_PDF_FILE_IDENTITY_RUN_ID
    assert summary["status"] == "DIAGNOSTIC_V3_9_1_XLSX_TABLE_AXIS_PDF_FILE_IDENTITY_COMPUTED"
    assert summary["run_class"] == "diagnostic_only_xlsx_sourceatom_table_axis_pdf_file_identity"
    assert summary["source_run_id"] == runner.V3_7_2_SOURCE_REGISTRY_BACKED_RETRIEVAL_SMOKE_REPORT_RUN_ID
    assert summary["parent_file_resolve_run_id"] == runner.V3_8_2_ORACLE_FREE_FILE_RESOLVE_RUN_ID
    assert summary["parent_xlsx_scoped_cell_run_id"] == runner.V3_8_3_XLSX_SCOPED_CELL_RESOLVE_RUN_ID
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["answer_generation_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["fine_tuning_started"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["gold_mutation"] is False
    assert summary["qrels_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["source_family_counts"] == {"XLSX": 344, "PDF": 329}
    assert set(summary["per_source_family"]) == {"XLSX", "PDF_FILE_IDENTITY", "PDF_CONTENT", "TEXT"}
    assert summary["xlsx_pdf_collapsed_score_reported"] is False
    assert summary["headline_aggregate_score_reported"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["answer_value_in_query_success_evidence_used"] is False
    assert summary["index_to_content_success_evidence_used"] is False
    assert summary["file_or_source_title_leak_success_evidence_used"] is False

    xlsx = summary["per_source_family"]["XLSX"]
    xlsx_metrics = xlsx["metrics"]
    assert xlsx["locator_signal_count_distribution"]["signal_empty_rank1_count"] == 257
    assert xlsx["locator_signal_count_distribution"]["rank1_candidate_count"] == 300
    assert xlsx["baseline_v3_8_3_metrics"]["table_or_range_resolve@1"]["numerator"] == 22
    assert xlsx_metrics["table_or_range_resolve@1"]["numerator"] == 23
    assert xlsx_metrics["cell_or_value_resolve@1"]["numerator"] == 20
    assert xlsx_metrics["cell_or_value_resolve@3"]["numerator"] == 26
    assert xlsx["source_atom_table_axis_ranked_into_top3_count"] == 60

    split = summary["split_manifest"]
    assert split["official_metric_input_rows"] == 0
    assert split["source_atom_disjoint_guard"]["workbook_disjoint_from_dev"] is True
    assert split["source_atom_disjoint_guard"]["source_identity_disjoint_from_dev"] is True
    assert split["query_fidelity_validation_minimum_met"] is True
    assert split["query_fidelity_validation"]["headline_included"] >= 30
    assert split["query_fidelity_validation"]["headline_included"] == 118
    assert split["validation"]["metrics"]["table_or_range_resolve@1"]["numerator"] == 3
    assert split["validation"]["metrics"]["table_or_range_resolve@3"]["numerator"] == 9
    assert split["validation"]["metrics"]["cell_or_value_resolve@1"]["numerator"] == 3
    assert split["validation"]["metrics"]["cell_or_value_resolve@3"]["numerator"] == 9
    assert split["validation"]["miss_taxonomy"]["primary_category_counts"]["table_or_range_miss_after_sheet_hit"] == 105

    pdf = summary["per_source_family"]["PDF_FILE_IDENTITY"]
    pdf_metrics = pdf["metrics"]
    assert pdf_metrics["file_resolve@1"]["numerator"] == 66
    assert pdf_metrics["file_resolve@3"]["numerator"] == 129
    assert pdf_metrics["abstain_rate"]["numerator"] == 182
    assert pdf_metrics["wrong_file_block_rate"]["numerator"] == 60
    assert summary["per_source_family"]["PDF_CONTENT"]["computed_in_this_run"] is False
    assert summary["per_source_family"]["PDF_CONTENT"]["preselected_sourceatom_evidence_quality_gain_mixed_with_file_identity"] is False
    assert summary["per_source_family"]["TEXT"]["comparison_only"] is True
    assert summary["failure_taxonomy"]["pdf_answer_ready_evidence_window"]["computed_in_this_run"] is False
    assert summary["failure_taxonomy"]["pdf_answer_ready_evidence_window"]["file_identity_gain_not_mixed_with_answer_ready_gain"] is True

    assert len(summary["per_query_rows"]) == 673
    assert len(summary["query_fidelity_audit_rows"]) == 344
    assert all(row["official_metric_input_rows"] == 0 for row in summary["query_fidelity_audit_rows"])
    assert all(
        row[column] == ""
        for row in summary["query_fidelity_audit_rows"]
        for column in ("query_approval", "relevance", "answerability", "expected_answer", "supporting_evidence", "pass_fail")
    )
    assert summary["fail_closed_reasons"] == []
    assert summary["artifact_paths"]["summary_json"].endswith("_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic_summary.json")
    assert summary["artifact_paths"]["metrics_json"].endswith("_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic_metrics.json")
    assert summary["artifact_paths"]["per_query_jsonl"].endswith("_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic_per_query.jsonl")
    assert summary["artifact_paths"]["query_fidelity_audit_jsonl"].endswith("_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic_query_fidelity_audit.jsonl")


def test_v3_9_2_overfit_risk_audit_builds_seen_blind_holdout_reset_without_success_evidence() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_v3_9_2_overfit_risk_audit_and_blind_holdout_reset as audit

    artifacts = audit.build_artifacts()
    summary = artifacts["summary"]
    metrics = artifacts["metrics"]
    seen = artifacts["seen_manifest"]
    split = artifacts["split_manifest"]
    architecture = artifacts["architecture"]
    overfit_rows = artifacts["overfit_rows"]

    assert summary["run_id"] == audit.RUN_ID
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["fine_tuning_executed"] is False
    assert summary["gold_mutation"] is False
    assert summary["qrels_mutation"] is False
    assert summary["label_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["staging_or_commit_performed"] is False
    assert summary["seen_validation_is_strong_blind_validation"] is False
    assert summary["seen_validation_downgraded_to_seen_validation_only"] is True
    assert summary["fresh_holdout_sufficient"] is False
    assert "No v3_9_1 metric improvement is preserved as future success evidence" in summary[
        "generalizable_signal_conclusion"
    ]

    assert seen["real_unseen_counts"] == {
        "PDF_source_document_disjoint": 0,
        "XLSX_workbook_disjoint": 0,
    }
    assert seen["real_unseen_holdout_sufficient"] is False
    assert metrics["overfit_risk_label_counts"]["likely_general"] == 0
    assert metrics["overfit_risk_label_counts"]["insufficient_blind_evidence"] >= 1
    assert metrics["fresh_holdout"]["product_success_evidence_allowed"] is False
    assert split["product_success_evidence_allowed"] is False
    assert split["synthetic_ood_guard_used"] is True
    assert split["workbook_disjoint_guard"]["passed_for_synthetic_ood"] is True
    assert split["source_document_disjoint_guard"]["passed_for_synthetic_ood"] is True

    assert architecture["xlsx_sourceatom_searchunit_table_axis_materialization"]["scope"] == "overlay_rerank_only"
    assert architecture["xlsx_sourceatom_searchunit_table_axis_materialization"][
        "nonprod_rematerialization_needed_for_next_performance_phase"
    ] is True
    assert architecture["pdf_file_identity_scope"]["file_identity_gain_mixed_with_answer_ready_gain"] is False

    delta_types = {row["delta_type"] for row in overfit_rows}
    assert {
        "dev_delta",
        "old_validation_delta",
        "leave_one_workbook_out_delta",
        "query_fidelity_included_delta",
        "query_fidelity_excluded_delta",
        "leakage_bucket_delta",
        "locator_signal_count_delta",
        "rank1_signal_empty_delta",
        "pdf_file1_gain_vs_wrong_file_disambiguation_abstain_movement",
        "pdf_file_at1_gain_case_review",
    } <= delta_types
    pdf_gain = next(row for row in overfit_rows if row["delta_type"] == "pdf_file_at1_gain_case_review")
    assert pdf_gain["gain_case_count"] == 1
    assert pdf_gain["gain_cases"][0]["query_id"] == "v3_6_1_weak_noisy_silver_v3_5_3_pdf_a99e56be96dcc462"
    assert "query_source_date_alias_match" in pdf_gain["gain_cases"][0]["source_identity_normalization_signals"]
    assert pdf_gain["future_success_evidence"] is False
    assert any("metric_tradeoff" in row["overfit_risk_labels"] for row in overfit_rows)


def test_v3_9_2_fresh_holdout_query_fidelity_keeps_user_fields_blank_and_shortcuts_blocked() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_v3_9_2_overfit_risk_audit_and_blind_holdout_reset as audit

    artifacts = audit.build_artifacts()
    candidates = artifacts["candidate_manifest"]["candidates"]
    fidelity_rows = artifacts["query_fidelity_rows"]
    leakage_rows = artifacts["leakage_audit_rows"]

    assert len(candidates) == 14
    assert {row["source_family"] for row in candidates} == {"PDF", "XLSX"}
    assert {row["query_style"] for row in candidates} >= {
        "terse_question",
        "messy_user_like",
        "short_fragment",
        "implicit_context",
        "no_source_title",
        "colloquial_korean",
    }
    assert all(row["synthetic"] is True for row in candidates)
    assert all(row["product_success_evidence_allowed"] is False for row in candidates)
    assert all(row["official_metric_input_rows"] == 0 for row in candidates)
    assert all(
        row[field] == ""
        for row in candidates
        for field in (
            "query_approval",
            "relevance",
            "answerability",
            "expected_answer",
            "supporting_evidence",
            "pass_fail",
            "denominator_eligibility",
        )
    )

    assert len(fidelity_rows) == len(candidates)
    assert all(row["query_fidelity_headline_included"] is True for row in fidelity_rows)
    assert all(row["official_metric_input_rows"] == 0 for row in fidelity_rows)
    assert all(row["answer_value_in_query"] is False for row in fidelity_rows)
    assert all(row["index_to_content"] is False for row in fidelity_rows)
    assert all(row["source_title_leak"] is False for row in fidelity_rows)
    assert all(row["file_title_leak"] is False for row in fidelity_rows)
    assert all(row["exact_query_hack"] is False for row in fidelity_rows)
    assert all(row["unnatural_sheet_or_cell_reference"] is False for row in fidelity_rows)
    assert all(
        row[field] == ""
        for row in fidelity_rows
        for field in (
            "query_approval",
            "relevance",
            "answerability",
            "expected_answer",
            "supporting_evidence",
            "pass_fail",
            "denominator_eligibility",
        )
    )
    assert any(row["bucket"] == "answer_value_in_query" for row in leakage_rows)
    assert all(
        row["success_evidence_allowed"] is False
        for row in leakage_rows
        if row["bucket"] in {"answer_value_in_query", "index_to_content", "source_title_leak", "file_title_leak"}
    )


def test_v3_10_fresh_holdout_and_xlsx_nonprod_materialization_stays_diagnostic_only() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization as run

    artifacts = run.build_artifacts()
    summary = artifacts["summary"]
    metrics = artifacts["metrics"]
    holdout = artifacts["fresh_holdout_manifest"]
    seen = artifacts["seen_surface_manifest"]
    sourceatoms = artifacts["xlsx_sourceatom_rows"]
    searchunits = artifacts["xlsx_searchunit_rows"]
    index_summary = artifacts["xlsx_index_build_summary"]

    assert summary["run_id"] == run.RUN_ID
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["fine_tuning_executed"] is False
    assert summary["fresh_real_holdout_sufficient"] is False
    assert summary["product_success_evidence_allowed"] is False
    assert summary["seen_validation_locked_to_seen_validation_only"] is True
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["answer_value_in_query_success_evidence_used"] is False
    assert summary["index_to_content_success_evidence_used"] is False
    assert summary["file_or_source_title_leak_success_evidence_used"] is False

    assert seen["seen_policy"].startswith("v3_8_3/v3_9/v3_9_1")
    assert seen["real_unseen_registry_counts"] == {
        "PDF_source_document_disjoint": 0,
        "XLSX_workbook_disjoint": 0,
    }
    assert holdout["real_holdout_sufficient"] is False
    assert holdout["minimum_targets"] == {
        "xlsx_unseen_workbooks": 8,
        "pdf_unseen_source_documents": 20,
        "query_fidelity_included_rows_per_family": 100,
    }
    assert holdout["real_query_fidelity_included_counts"]["XLSX"] == 0
    assert holdout["real_query_fidelity_included_counts"]["PDF"] == 0
    assert holdout["synthetic_ood_guard"]["product_success_evidence_allowed"] is False
    assert holdout["synthetic_ood_guard"]["candidate_count"] > 14

    assert sourceatoms
    assert len(sourceatoms) == len(searchunits)
    assert index_summary["index_namespace"] == run.ALLOWED_NAMESPACE
    assert index_summary["materialization_scope"] == "nonprod_manifest_materialized"
    assert index_summary["overlay_only"] is False
    assert index_summary["protected_namespaces_touched"] == []
    assert index_summary["sourceatom_manifest_rows"] == len(sourceatoms)
    assert index_summary["searchunit_manifest_rows"] == len(searchunits)
    for row in sourceatoms[:10]:
        assert row["index_namespace"] == run.ALLOWED_NAMESPACE
        assert row["materialized_in_nonprod_sourceatom"] is True
        assert row["overlay_only"] is False
        for field in run.REQUIRED_SOURCEATOM_TABLE_AXIS_FIELDS:
            assert field in row
        for field in run.FORBIDDEN_TABLE_AXIS_FIELDS:
            assert field not in row
        assert row["raw_answer_value_for_query_scoring_used"] is False
    for row in searchunits[:10]:
        assert row["index_namespace"] == run.ALLOWED_NAMESPACE
        assert row["materialized_in_nonprod_searchunit"] is True
        for field in run.REQUIRED_SEARCHUNIT_TABLE_AXIS_FIELDS:
            assert field in row
        for field in run.FORBIDDEN_TABLE_AXIS_FIELDS:
            assert field not in row

    xlsx_eval = metrics["xlsx_table_axis_eval"]
    assert xlsx_eval["fresh_real_holdout"]["success_claim_allowed"] is False
    assert xlsx_eval["old_seen_reference"]["success_claim_allowed"] is False
    assert (
        xlsx_eval["nonprod_seen_materialization_smoke"]["signal_empty_rank1_rate"]["numerator"]
        < xlsx_eval["old_seen_reference"]["signal_empty_rank1_rate"]["numerator"]
    )
    assert xlsx_eval["nonprod_seen_materialization_smoke"]["table_or_range@3"] == xlsx_eval[
        "old_seen_reference"
    ]["table_or_range@3"]


def test_v3_10_query_fidelity_and_leakage_guards_keep_holdout_rows_user_owned_blank() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization as run

    artifacts = run.build_artifacts()
    candidates = artifacts["fresh_holdout_manifest"]["query_candidates"]
    fidelity_rows = artifacts["query_fidelity_rows"]
    leakage_rows = artifacts["leakage_audit_rows"]

    assert candidates
    assert {row["query_style"] for row in candidates} >= {
        "terse_question",
        "messy_user_like",
        "short_fragment",
        "implicit_context",
        "no_source_title",
        "colloquial_korean",
    }
    assert all(row["official_metric_input_rows"] == 0 for row in candidates)
    assert all(row["product_success_evidence_allowed"] is False for row in candidates)
    assert all(row["direct_normalized_value_query_matching_used"] is False for row in candidates)
    assert all(
        row[field] == ""
        for row in candidates
        for field in (
            "query_approval",
            "relevance",
            "answerability",
            "expected_answer",
            "supporting_evidence",
            "pass_fail",
            "denominator_eligibility",
        )
    )

    assert len(fidelity_rows) == len(candidates)
    assert all(row["official_metric_input_rows"] == 0 for row in fidelity_rows)
    assert all(row["query_fidelity_headline_included"] is True for row in fidelity_rows)
    for shortcut in (
        "answer_value_in_query",
        "index_to_content",
        "source_title_leak",
        "file_title_leak",
        "exact_query_hack",
        "major_topic_drift",
        "unnatural_sheet_or_cell_reference",
    ):
        assert all(row[shortcut] is False for row in fidelity_rows)
        assert any(row["bucket"] == shortcut for row in leakage_rows)
    assert all(row["success_evidence_allowed"] is False for row in leakage_rows)


def test_pdf_xlsx_answer_quality_review_packet_pairs_final_run_rows_and_keeps_user_fields_blank(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    summary_path = (
        REPORT_DIR
        / "quality"
        / "pdf_xlsx_llm_quality_final_llm_rewrite_all_llm_15pf_v3_summary.json"
    )
    require_pdf_xlsx_answer_quality_local_artifacts(summary_path)
    report = packet.run_packet(summary_path=summary_path, output_dir=tmp_path)

    assert report["status"] == "PASS"
    assert report["schema_version"] == "rag_pdf_xlsx_answer_quality_review_packet_v1"
    assert report["source_run_label"] == "final_llm_rewrite_all_llm_15pf_v3"
    assert report["diagnostic_only"] is True
    assert report["official_metric"] is False
    assert report["promotion_evidence"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["review_packet_row_count"] == 30
    assert report["case_counts_by_source_type"] == {"PDF": 15, "XLSX": 15}
    assert report["baseline_quality_pass_counts"] == {"PDF": 0, "XLSX": 0}
    assert report["final_quality_pass_counts"] == {"PDF": 6, "XLSX": 15}
    assert report["aggregate_diagnostic_only_scope"] == "legacy_raw_final_alias"
    assert report["aggregate_raw_final_diagnostic_only"] == "21/30"
    assert report["aggregate_answer_ready_diagnostic_only"] == "21/30"
    assert report["generated_artifacts"]["review_csv"]["path"].endswith("review_packet.csv")
    assert report["generated_artifacts"]["pdf_delta_audit_jsonl"]["path"].endswith("pdf_delta_audit.jsonl")
    assert report["generated_artifacts"]["query_fidelity_audit_jsonl"]["path"].endswith("query_fidelity_audit.jsonl")
    assert report["generated_artifacts"]["pdf_residual_review_md"]["path"].endswith("pdf_residual_review.md")
    assert report["generated_artifacts"]["summary_md"]["path"].endswith("summary.md")
    assert report["query_fidelity_summary"]["rows"] == 30
    assert report["headline_quality_counts"]["all_rows_query_fidelity_unverified"]["rows"] == 30
    assert report["future_scored_adapter"]["official_metric_input_rows"] == 0

    with (tmp_path / "review_packet.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 30
    assert packet.USER_DECISION_COLUMNS == [
        "user_answerable",
        "user_relevance",
        "user_expected_answer",
        "user_supporting_evidence",
        "user_pass_fail",
        "user_denominator_eligibility",
        "user_policy_note",
        "user_review_approved",
        "user_query_intent_preserved",
        "user_query_approval",
        "user_query_policy_note",
    ]
    for row in rows:
        assert row["diagnostic_only"] == "TRUE"
        assert row["not_gold"] == "TRUE"
        assert row["not_official_denominator"] == "TRUE"
        assert row["official_metric_candidate"] == "FALSE"
        assert row["promotion_evidence"] == "FALSE"
        assert all(row[column] == "" for column in packet.USER_DECISION_COLUMNS)
        assert row["baseline_result"].startswith("FAIL")
        assert row["final_result"]
        assert row["retrieved_evidence_text"]
        assert row["locator_json"]

    pdf_residuals = report["pdf_residuals"]
    assert pdf_residuals["total_residuals"] == 9
    assert pdf_residuals["final_failure_type_counts"] == {
        "locator_only_answer": 1,
        "low_evidence_overlap": 9,
        "pdf_locator_missing": 1,
    }
    assert set(pdf_residuals["likely_cause_counts"]) == {
        "retrieval_miss",
        "weak_snippet",
        "ocr_ish_text",
        "locator_only_evidence",
        "table_form_formatting",
        "semantic_answer_mismatch",
        "evaluator_overlap_limitation",
    }
    assert pdf_residuals["likely_cause_counts"]["retrieval_miss"] == 0
    assert pdf_residuals["likely_cause_counts"]["weak_snippet"] > 0
    assert pdf_residuals["likely_cause_counts"]["evaluator_overlap_limitation"] > 0


def test_pdf_xlsx_answer_quality_review_packet_future_adapter_stays_disabled_until_user_approval(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    summary_path = (
        REPORT_DIR
        / "quality"
        / "pdf_xlsx_llm_quality_final_llm_rewrite_all_llm_15pf_v3_summary.json"
    )
    require_pdf_xlsx_answer_quality_local_artifacts(summary_path)
    report = packet.run_packet(summary_path=summary_path, output_dir=tmp_path)
    review_rows = packet.read_csv_rows(tmp_path / "review_packet.csv")

    assert report["validation"]["ok"] is True
    assert report["validation"]["user_decision_columns_blank"] is True
    assert report["future_scored_adapter"]["status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert report["future_scored_adapter"]["official_metric_input_rows"] == 0
    assert "user_decision_fields_blank" in report["future_scored_adapter"]["blocked_reasons"]
    assert "user_query_decision_fields_blank" in report["future_scored_adapter"]["blocked_reasons"]
    assert "user_review_approved_not_true" in report["future_scored_adapter"]["blocked_reasons"]
    assert "user_query_approval_not_true" in report["future_scored_adapter"]["blocked_reasons"]
    assert "diagnostic_only_packet_not_scored_eval_input" in report["future_scored_adapter"]["blocked_reasons"]

    adapter_preview = packet.build_future_scored_adapter_preview(review_rows)
    assert adapter_preview == report["future_scored_adapter"]
    assert packet.validate_review_rows(review_rows)["official_metric_input_rows"] == 0

    approved_included = dict(next(row for row in review_rows if row["query_fidelity_headline_included"] == "TRUE"))
    for column in packet.ANSWER_USER_DECISION_COLUMNS:
        approved_included[column] = "approved"
    approved_included["user_query_intent_preserved"] = "true"
    approved_included["user_query_approval"] = "approved"
    approved_included["user_query_policy_note"] = "user-approved query intent"
    approved_preview = packet.build_future_scored_adapter_preview([approved_included])
    assert approved_preview["adapter_enabled"] is False
    assert approved_preview["official_metric_input_rows"] == 0
    assert approved_preview["approved_only_official_adjacent_rows_seen"] == 1
    assert approved_preview["blocked_reasons"] == ["diagnostic_only_packet_not_scored_eval_input"]

    excluded = dict(next(row for row in review_rows if row["query_fidelity_headline_included"] == "FALSE"))
    for column in packet.ANSWER_USER_DECISION_COLUMNS:
        excluded[column] = "approved"
    excluded["user_query_intent_preserved"] = "true"
    excluded["user_query_approval"] = "approved"
    excluded_preview = packet.build_future_scored_adapter_preview([excluded])
    assert excluded_preview["official_metric_input_rows"] == 0
    assert excluded_preview["approved_only_official_adjacent_rows_seen"] == 0
    assert "query_fidelity_exclusions_present" in excluded_preview["blocked_reasons"]
    assert "user_review_approved_not_true" not in excluded_preview["blocked_reasons"]


def test_pdf_xlsx_answer_quality_review_packet_pdf_residual_classifiers_match_structural_signals() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    assert packet.ocr_ish_text("정 책 연 구 과 제 명")
    assert packet.locator_like_evidence("Page 12")
    assert packet.locator_like_evidence("p.65")
    assert packet.table_or_form_formatting("A12 value")
    assert packet.table_or_form_formatting("항목 | 금액 | 비고")


def test_pdf_xlsx_answer_quality_review_packet_answer_ready_delta_and_query_fidelity_artifacts(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    summary_path = REPORT_DIR / "quality" / "pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_summary.json"
    require_pdf_xlsx_answer_quality_local_artifacts(summary_path)
    report = packet.run_packet(summary_path=summary_path, output_dir=tmp_path)

    assert report["status"] == "PASS"
    assert report["aggregate_raw_final_diagnostic_only"] == "17/30"
    assert report["aggregate_answer_ready_diagnostic_only"] == "20/30"
    assert report["official_metric_input_rows"] == 0
    assert report["evaluation_split"]["role"] == "dev_current_pdf_headline"
    assert report["evaluation_split"]["success_evidence_allowed"] is False
    assert report["evaluation_split"]["official_metric_input_rows"] == 0
    assert report["headline_quality_counts"]["query_fidelity_subset"]["dev_only"] is True
    assert report["headline_quality_counts"]["query_fidelity_subset"]["success_evidence_allowed"] is False
    assert report["headline_quality_counts"]["query_fidelity_subset"]["by_family"]["PDF"] == {
        "rows": 13,
        "raw_final_pass": 5,
        "answer_ready_pass": 8,
        "fresh_answer_ready_pass": 7,
        "raw_final_reused_rows": 4,
        "raw_final_reused_pass": 1,
        "delta_answer_ready_minus_raw": 3,
        "answer_ready_reuse_reason_counts": {
            "no_structural_answer_ready_evidence_gain_preserve_raw_final": 3,
            "raw_pass_regression_guard_preserve_existing_pass": 1,
        },
    }
    assert report["pdf_delta_audit_summary"]["pdf_case_count"] == 15
    assert report["pdf_delta_audit_summary"]["delta_bucket_counts"]["raw_fail_to_ready_pass"] == 3
    assert report["pdf_delta_audit_summary"]["delta_bucket_counts"].get("raw_pass_to_ready_fail_regression", 0) == 0
    assert report["pdf_residuals"]["residual_scope"] == "answer_ready_context"
    assert report["pdf_residuals"]["total_residuals"] == 7
    assert report["pdf_residual_review_summary"]["answer_ready_failed_review_rows"] == 7
    assert report["pdf_residual_review_summary"]["query_excluded_review_rows"] == 0
    assert report["query_fidelity_summary"]["excluded"] > 0
    assert report["anti_overfit_guardrails"]["candidate_rules_frozen_before_validation"] is True
    assert report["anti_overfit_guardrails"]["forbidden_rule_status"] == {
        "case_id_branches": False,
        "exact_query_hacks": False,
        "file_or_source_title_hacks": False,
        "pass_fail_threshold_tuning": False,
        "expected_supporting_or_gold_text_input": False,
        "drift_contaminated_headline_gain": False,
    }
    assert report["headline_quality_counts"]["query_fidelity_subset"]["rows"] < report[
        "headline_quality_counts"
    ]["all_rows_query_fidelity_unverified"]["rows"]
    assert report["ocr_rationale"]["decision"] == "skipped"

    pdf_delta_rows = read_jsonl(tmp_path / "pdf_delta_audit.jsonl")
    query_rows = read_jsonl(tmp_path / "query_fidelity_audit.jsonl")
    residual_rows = list(csv.DictReader((tmp_path / "pdf_residual_review.csv").open(encoding="utf-8-sig", newline="")))

    assert len(pdf_delta_rows) == 15
    assert len(query_rows) == 30
    assert all(row["diagnostic_only"] is True for row in pdf_delta_rows)
    assert all(row["official_metric_candidate"] is False for row in query_rows)
    assert any(row["delta_bucket"] == "raw_fail_to_ready_pass" for row in pdf_delta_rows)
    assert any(row["query_fidelity_headline_included"] is False for row in query_rows)
    assert residual_rows
    assert (tmp_path / "pdf_residual_review.md").read_text(encoding="utf-8").startswith("# PDF Residual Review")


def test_pdf_xlsx_answer_quality_review_packet_validation_holdout_artifacts(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    summary_path = REPORT_DIR / "quality" / "pdf_xlsx_llm_quality_answer_ready_pdf_v1_llm_15pf_validation_summary.json"
    require_pdf_xlsx_answer_quality_local_artifacts(summary_path)
    report = packet.run_packet(summary_path=summary_path, output_dir=tmp_path)

    split = report["evaluation_split"]
    assert report["status"] == "PASS"
    assert report["aggregate_raw_final_diagnostic_only"] == "18/30"
    assert report["aggregate_answer_ready_diagnostic_only"] == "20/30"
    assert report["official_metric_input_rows"] == 0
    assert split["role"] == "validation_holdout"
    assert split["dev_only"] is False
    assert split["source_document_disjoint_from_dev"] is True
    assert split["dev_overlap_document_count"] == 0
    assert split["success_evidence_allowed"] is True
    assert split["official_metric_input_rows"] == 0

    assert report["headline_quality_counts"]["all_rows_query_fidelity_unverified"]["by_family"]["PDF"] == {
        "rows": 15,
        "raw_final_pass": 8,
        "answer_ready_pass": 9,
        "fresh_answer_ready_pass": 6,
        "raw_final_reused_rows": 3,
        "raw_final_reused_pass": 3,
        "delta_answer_ready_minus_raw": 1,
        "answer_ready_reuse_reason_counts": {
            "raw_pass_regression_guard_preserve_existing_pass": 3,
        },
    }
    assert report["headline_quality_counts"]["query_fidelity_subset"]["by_family"]["PDF"] == {
        "rows": 14,
        "raw_final_pass": 8,
        "answer_ready_pass": 8,
        "fresh_answer_ready_pass": 5,
        "raw_final_reused_rows": 3,
        "raw_final_reused_pass": 3,
        "delta_answer_ready_minus_raw": 0,
        "answer_ready_reuse_reason_counts": {
            "raw_pass_regression_guard_preserve_existing_pass": 3,
        },
    }
    assert report["pdf_delta_audit_summary"]["delta_bucket_counts"]["raw_fail_to_ready_pass"] == 1
    assert report["pdf_delta_audit_summary"]["delta_bucket_counts"].get("raw_pass_to_ready_fail_regression", 0) == 0
    assert report["pdf_residuals"]["total_residuals"] == 6
    assert report["pdf_residual_review_summary"]["answer_ready_failed_review_rows"] == 6
    assert report["pdf_residual_review_summary"]["query_excluded_review_rows"] == 1
    assert report["pdf_residual_review_summary"]["bucket_counts"]["true_answer_failure"] == 0
    assert report["anti_overfit_guardrails"]["dev_only_gain_counts_as_success"] is False
    assert report["anti_overfit_guardrails"]["forbidden_rule_status"]["drift_contaminated_headline_gain"] is False
    assert report["future_scored_adapter"]["adapter_enabled"] is False
    assert report["validation"]["scored_eval_entry_allowed"] is False


def test_pdf_answer_ready_reuses_raw_final_when_structural_evidence_does_not_improve() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    no_gain_profile = {
        "family": "PDF",
        "bounded_expansion_applied": False,
        "raw_answer_ready_score": 0.0,
        "answer_ready_score": 0.0,
        "answer_ready_score_delta": 0.0,
        "raw_snippet": "내부감시장치에 대한 감사의 의견서................................................................1",
        "answer_ready_snippet": "내부감시장치에 대한 감사의 의견서 ... 1",
    }
    structural_gain_profile = {
        "family": "PDF",
        "bounded_expansion_applied": True,
        "raw_answer_ready_score": 0.1,
        "answer_ready_score": 0.45,
        "answer_ready_score_delta": 0.35,
        "raw_snippet": "감 사 보 고 서................................................................1",
        "answer_ready_snippet": "감 사 보 고 서 ... 1 독립된 감사인의 감사보고서 ... 2",
    }

    assert quality.should_reuse_raw_final_for_answer_ready(no_gain_profile) is True
    assert quality.should_reuse_raw_final_for_answer_ready(structural_gain_profile) is False


def test_pdf_validation_split_prefers_document_disjoint_cases_and_records_metadata() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    rows = [
        pdf_manifest_row(
            source_atom_id="src-dev-a",
            search_view_id="search-dev-a",
            document_version_id="doc-dev-a",
            search_unit_id="su-dev-a",
            page=1,
            bbox=[1.0, 2.0, 3.0, 4.0],
            text="개발 문서 A의 PDF 본문이며 충분한 길이의 문장입니다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-dev-b",
            search_view_id="search-dev-b",
            document_version_id="doc-dev-b",
            search_unit_id="su-dev-b",
            page=1,
            bbox=[1.0, 2.0, 3.0, 4.0],
            text="개발 문서 B의 PDF 본문이며 충분한 길이의 문장입니다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-overlap",
            search_view_id="search-overlap",
            document_version_id="doc-dev-a",
            search_unit_id="su-overlap",
            page=2,
            bbox=[1.0, 2.0, 3.0, 4.0],
            text="개발 문서 A와 겹치는 검증 후보입니다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-val-c",
            search_view_id="search-val-c",
            document_version_id="doc-val-c",
            search_unit_id="su-val-c",
            page=1,
            bbox=[1.0, 2.0, 3.0, 4.0],
            text="검증 문서 C의 독립 PDF 본문이며 충분한 길이의 문장입니다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-val-d",
            search_view_id="search-val-d",
            document_version_id="doc-val-d",
            search_unit_id="su-val-d",
            page=1,
            bbox=[1.0, 2.0, 3.0, 4.0],
            text="검증 문서 D의 독립 PDF 본문입니다.",
        ),
    ]

    dev_cases = quality.load_evidence_cases_from_rows(
        rows,
        cases_per_family=2,
        split_role="dev_current_pdf_headline",
    )
    validation_cases = quality.load_evidence_cases_from_rows(
        rows,
        cases_per_family=2,
        split_role="validation_holdout",
        dev_cases=dev_cases,
    )
    split = quality.case_selection_summary(
        validation_cases,
        split_role="validation_holdout",
        dev_cases=dev_cases,
    )

    assert [case.source_atom_id for case in validation_cases] == ["src-val-c", "src-val-d"]
    assert split["role"] == "validation_holdout"
    assert split["source_document_disjoint_from_dev"] is True
    assert split["fallback_strategy_used"] == ""
    assert split["dev_overlap_document_count"] == 0
    assert split["official_metric_input_rows"] == 0


def test_pdf_answer_ready_silver_seed_index_excludes_holdout_and_kfold_rows(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    manifest_row = pdf_manifest_row(
        source_atom_id="src-pdf",
        search_view_id="search-pdf",
        document_version_id="docv-pdf",
        search_unit_id="su-page",
        page=1,
        bbox=[1.0, 2.0, 3.0, 4.0],
        text="정책 연구 보고서의 PDF 본문이며 검증에 충분한 문장입니다.",
    )
    base_silver = {
        "source_family": "PDF",
        "source_identity": quality.canonical_source_identity(manifest_row),
        "locator_fingerprint": manifest_row["locator_fingerprint"],
        "diagnostic_only": True,
        "not_gold": True,
        "not_official_denominator": True,
        "not_official_qrels": True,
        "official_metric_denominator_usage_allowed": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "query_quality_profile": "diagnostic",
    }
    holdout = {
        **base_silver,
        "generated_question_draft": "홀드아웃 질문은 개발 시드로 쓰면 안 됩니다.",
        "manifest_partition": "holdout",
        "split_role": "validation_holdout",
        "row_ordinal": 1,
    }
    kfold = {
        **base_silver,
        "generated_question_draft": "kfold 홀드아웃 질문도 개발 시드로 쓰면 안 됩니다.",
        "manifest_partition": "kfold_holdout",
        "row_ordinal": 2,
    }
    dev = {
        **base_silver,
        "generated_question_draft": "개발 전용 진단 질문만 선택합니다.",
        "manifest_partition": "core",
        "split_role": "dev",
        "row_ordinal": 3,
    }
    silver_path = tmp_path / "silver.jsonl"
    silver_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in [holdout, kfold, dev]) + "\n",
        encoding="utf-8",
    )

    silver_index = quality.load_silver_seed_index(silver_path)
    seed = quality.find_silver_seed(manifest_row, silver_index)

    assert seed["generated_question_draft"] == "개발 전용 진단 질문만 선택합니다."
    assert seed["manifest_partition"] == "core"


def test_pdf_xlsx_answer_quality_packet_loads_selected_cases_for_holdout_roundtrip(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    selected_case = {
        "case_id": "pdf-016",
        "family": "PDF",
        "source_atom_id": "src-val",
        "doc_id": "doc-val",
        "section": "page=7",
        "evidence_text": "검증 전용 PDF 근거 본문입니다.",
        "locator": {"page": 7, "bbox": [10.0, 20.0, 30.0, 40.0], "source_pdf_path": "D:/diagnostic/source/validation.pdf"},
        "locator_fingerprint": "fp-val",
        "search_view_id": "search-val",
        "raw_evidence_text": "검증 전용 PDF 근거 본문입니다.",
        "normalized_evidence_text": "검증 전용 PDF 근거 본문입니다.",
        "answer_ready_evidence_text": "검증 전용 PDF 근거 본문입니다.",
    }
    summary = {
        "run_label": "answer_ready_pdf_v1_llm_15pf_validation",
        "cases_by_family": {"PDF": 1},
        "selected_cases": [selected_case],
        "case_selection": {"role": "validation_holdout"},
        "manifest": str(tmp_path / "missing_manifest.jsonl"),
        "silver_manifest": str(tmp_path / "missing_silver.jsonl"),
    }

    cases = packet.load_cases_for_summary(summary)

    assert list(cases) == ["pdf-016"]
    assert cases["pdf-016"].evidence_text == "검증 전용 PDF 근거 본문입니다."
    assert cases["pdf-016"].locator["page"] == 7


def test_pdf_xlsx_answer_quality_packet_fails_closed_if_official_metric_candidate_is_set() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    row = {column: "" for column in packet.REVIEW_COLUMNS}
    row.update(
        {
            "case_id": "pdf-unit",
            "source_type": "PDF",
            "diagnostic_only": "TRUE",
            "not_gold": "TRUE",
            "not_official_denominator": "TRUE",
            "not_official_qrels": "TRUE",
            "official_metric_candidate": "TRUE",
            "promotion_evidence": "FALSE",
        }
    )

    validation = packet.validate_review_rows([row])

    assert validation["ok"] is False
    assert validation["official_metric_input_rows"] == 1
    assert "pdf-unit has official_metric_candidate='TRUE', expected FALSE" in validation["errors"]


def test_pdf_xlsx_answer_ready_anti_overfit_audit_scans_benchmark_and_packet_files(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_anti_overfit_audit as audit

    default_scan_names = {path.name for path in audit.DEFAULT_SCAN_FILES}
    assert "rag_pdf_xlsx_llm_quality_benchmark.py" in default_scan_names
    assert "rag_pdf_xlsx_answer_quality_review_packet.py" in default_scan_names

    review_csv = tmp_path / "review.csv"
    review_csv.write_text(
        "\n".join(
            [
                "query_id,query,expected_answer,expected_evidence_location",
                "pdf_case_001,동성제약 감사보고서 핵심,감사의견 적정,page=7; bbox=[1,2,3,4]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    bad_source = tmp_path / "bad_answer_ready_rule.py"
    bad_source.write_text(
        "\n".join(
            [
                'if case_id == "pdf_case_001":',
                '    selected_answer = "감사의견 적정"',
                'EXPECTED_LOCATOR = "page=7; bbox=[1,2,3,4]"',
                'DOMAIN_ALIAS = {"동성제약": "감사의견"}',
                'if expected_evidence_locator and answer_allowed:',
                '    content_source = expected_evidence_locator',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = audit.run_audit(
        scan_files=[bad_source],
        review_paths=[review_csv],
        output_json=tmp_path / "audit.json",
        output_csv=tmp_path / "audit.csv",
    )

    assert report["status"] == "FAIL"
    assert report["hardcoded_query_id_count"] == 1
    assert report["hardcoded_gold_answer_literal_count"] == 1
    assert report["hardcoded_expected_locator_usage_count"] >= 1
    assert report["hardcoded_domain_alias_count"] >= 1


def test_pdf_xlsx_answer_quality_review_packet_query_fidelity_classifies_exclusions() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    case = quality.EvidenceCase(
        case_id="pdf-unit",
        family="PDF",
        source_atom_id="src",
        doc_id="doc",
        section="section",
        evidence_text="서울의 역사적 스케치와 도시 변천 과정을 설명한다.",
        locator={"page": 1},
    )

    major = packet.query_fidelity_audit(
        case=case,
        seed_query="영업보고서의 주요 내용은 무엇입니까?",
        query="서울의 역사적 스케치에 대해 알려줘",
        evidence_text=case.evidence_text,
    )
    assert major["query_drift_severity"] == "major_topic_drift"
    assert major["query_generation_mode"] == "invalid_drift"
    assert major["headline_included"] is False

    index_to_content = packet.query_fidelity_audit(
        case=case,
        seed_query="다른 경로 데이터 검색",
        query="서울의 역사적 스케치와 도시 변천 과정",
        evidence_text=case.evidence_text,
    )
    assert index_to_content["query_drift_severity"] == "index_to_content_query"
    assert index_to_content["query_generation_mode"] == "source_grounded_synthetic_query"
    assert index_to_content["headline_included"] is False

    preserving = packet.query_fidelity_audit(
        case=case,
        seed_query="서울의 역사적 스케치에 대해 알려주세요.",
        query="서울의 역사적 스케치는 무엇을 다루나요?",
        evidence_text=case.evidence_text,
    )
    assert preserving["query_generation_mode"] == "seed_preserving_rewrite"
    assert preserving["headline_included"] is True


def test_pdf_xlsx_answer_quality_review_packet_duplicate_rows_fail_closed() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import pytest
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    duplicate = {"case_id": "pdf-001", "prompt_mode": "final_locator_context"}
    with pytest.raises(ValueError, match="duplicate response row"):
        packet.build_review_rows(
            summary={},
            response_rows=[duplicate, duplicate],
            previous_response_rows=[],
            cases={},
            max_evidence_chars=100,
        )


def test_pdf_xlsx_answer_ready_packet_requires_answer_ready_rows_for_answer_ready_runs() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import pytest
    import rag_pdf_xlsx_answer_quality_review_packet as packet
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    case = quality.EvidenceCase(
        case_id="pdf-unit",
        family="PDF",
        source_atom_id="src",
        doc_id="doc",
        section="page=1",
        evidence_text="서울의 역사적 스케치와 도시 변천 과정을 설명한다.",
        locator={"page": 1, "bbox": [1.0, 2.0, 3.0, 4.0]},
    )
    rows = [
        packet_unit_response_row("pdf-unit", "baseline_legacy_context", query="서울의 역사적 스케치", quality_pass=False),
        packet_unit_response_row("pdf-unit", "final_locator_context", query="서울의 역사적 스케치", quality_pass=True),
    ]

    with pytest.raises(ValueError, match="missing required answer_ready_context rows"):
        packet.build_review_rows(
            summary={"run_label": "answer_ready_pdf_v1_llm_15pf"},
            response_rows=rows,
            previous_response_rows=[],
            cases={"pdf-unit": case},
            max_evidence_chars=100,
        )


def test_pdf_xlsx_answer_quality_review_packet_splits_residual_review_scope() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    failed = {
        "source_type": "PDF",
        "case_id": "pdf-failed",
        "query": "서울의 역사적 스케치",
        "query_drift_severity": "style_only",
        "query_generation_mode": "seed_preserving_rewrite",
        "query_fidelity_headline_included": "TRUE",
        "query_fidelity_exclusion_reason": "",
        "answer_ready_result": "FAIL: low_evidence_overlap",
        "answer_ready_failure_types": "low_evidence_overlap",
        "delta_bucket": "raw_fail_to_ready_fail_same_failure",
        "weak_snippet_flag": "TRUE",
        "dot_heavy_flag": "FALSE",
        "ocr_ish_flag": "FALSE",
        "locator_only_flag": "FALSE",
        "table_form_like_flag": "FALSE",
        "bounded_expansion_applied": "TRUE",
        "locator_page": "1",
        "locator_bbox": "[1,2,3,4]",
        "answer_ready_evidence_text": "서울의 역사적 스케치",
    }
    query_excluded_pass = {
        **failed,
        "case_id": "pdf-query-excluded",
        "query_fidelity_headline_included": "FALSE",
        "answer_ready_result": "PASS",
        "answer_ready_failure_types": "",
        "weak_snippet_flag": "FALSE",
        "bounded_expansion_applied": "FALSE",
    }

    review_rows = packet.build_pdf_residual_review_rows([failed, query_excluded_pass])
    summary = packet.summarize_pdf_residual_review_rows(review_rows)

    assert summary["rows"] == 2
    assert summary["answer_ready_failed_review_rows"] == 1
    assert summary["query_excluded_review_rows"] == 1
    assert summary["answer_ready_failed_bucket_counts"]["weak_evidence"] == 1
    assert summary["query_excluded_bucket_counts"]["query_drift"] == 1
    assert {row["review_scope"] for row in review_rows} == {
        "answer_ready_failure",
        "query_fidelity_excluded_only",
    }


def test_pdf_xlsx_answer_quality_counts_separate_fresh_answer_ready_from_raw_reuse() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    rows = [
        {
            "source_type": "PDF",
            "final_result": "PASS",
            "answer_ready_result": "PASS",
            "answer_ready_reused_raw_final": "TRUE",
            "answer_ready_reuse_reason": "raw_pass_regression_guard_preserve_existing_pass",
        },
        {
            "source_type": "PDF",
            "final_result": "FAIL: low_evidence_overlap",
            "answer_ready_result": "PASS",
            "answer_ready_reused_raw_final": "FALSE",
            "answer_ready_reuse_reason": "",
        },
        {
            "source_type": "XLSX",
            "final_result": "PASS",
            "answer_ready_result": "PASS",
            "answer_ready_reused_raw_final": "FALSE",
            "answer_ready_reuse_reason": "",
        },
    ]

    block = packet.quality_count_block(rows, evaluation_split={"dev_only": False, "success_evidence_allowed": True})

    assert block["answer_ready_pass"] == 3
    assert block["fresh_answer_ready_pass"] == 2
    assert block["raw_final_reused_pass"] == 1
    assert block["raw_final_reused_rows"] == 1
    assert block["answer_ready_reuse_reason_counts"] == {"raw_pass_regression_guard_preserve_existing_pass": 1}
    assert block["by_family"]["PDF"]["fresh_answer_ready_pass"] == 1
    assert block["by_family"]["PDF"]["raw_final_reused_pass"] == 1


def test_pdf_xlsx_answer_quality_summary_keeps_two_mode_compatibility() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    rows = [
        {
            "prompt_mode": "baseline_legacy_context",
            "family": "PDF",
            "score": {"quality_pass": False, "parse_ok": True, "citation_valid": True},
        },
        {
            "prompt_mode": "final_locator_context",
            "family": "PDF",
            "score": {"quality_pass": True, "parse_ok": True, "citation_valid": True},
        },
    ]

    summary = quality.answer_quality_summary(rows)

    assert summary["delta_final_minus_baseline"]["quality_pass"] == 1
    assert summary["delta_answer_ready_minus_raw_final"]["quality_pass"] == 0
    assert summary["delta_by_family_answer_ready_minus_raw_final"]["PDF"]["quality_pass"] == 0


def test_pdf_answer_ready_normalization_collapses_dot_leaders_without_touching_numbers() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    text = (
        "제1.2조 적용 2020년 1,088.0 Page 12 "
        "사 업 보 고 서............................................................................1 "
        "총액;;;;; 3.14 p.65"
    )

    normalized = quality.normalize_pdf_evidence_snippet(text)

    assert "................................................................" not in normalized
    assert ";;;;;" not in normalized
    assert "사 업 보 고 서 ... 1" in normalized
    assert "제1.2조" in normalized
    assert "1,088.0" in normalized
    assert "3.14" in normalized
    assert "Page 12" in normalized
    assert "p.65" in normalized


def test_pdf_answer_ready_expansion_uses_bounded_same_page_neighbors_and_preserves_locator() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    target_row = pdf_manifest_row(
        source_atom_id="src-target",
        search_view_id="search-target",
        document_version_id="docv-pdf",
        search_unit_id="su-page",
        page=3,
        bbox=[50.0, 100.0, 540.0, 112.0],
        text="사 업 보 고 서............................................................................1",
    )
    same_page_rows = [
        pdf_manifest_row(
            source_atom_id="src-heading",
            search_view_id="search-heading",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=3,
            bbox=[50.0, 72.0, 300.0, 86.0],
            text="제68기 사업보고서",
        ),
        target_row,
        pdf_manifest_row(
            source_atom_id="src-content",
            search_view_id="search-content",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=3,
            bbox=[50.0, 122.0, 540.0, 138.0],
            text="동성제약 주식회사의 사업의 내용과 재무에 관한 사항을 다음과 같이 보고합니다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-next",
            search_view_id="search-next",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=3,
            bbox=[50.0, 146.0, 540.0, 160.0],
            text="회사의 개요 및 주요 영업 현황을 포함합니다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-other-page",
            search_view_id="search-other-page",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=4,
            bbox=[50.0, 80.0, 540.0, 96.0],
            text="다른 페이지 문장은 섞이면 안 됩니다.",
        ),
    ]
    context_index = quality.build_pdf_context_index(same_page_rows)
    locator = quality.extract_locator({**target_row, **quality.parse_locator_text(target_row["embedding_text"])})

    audit = quality.pdf_evidence_readiness_audit(
        raw_snippet=target_row["display_text"],
        normalized_snippet=quality.normalize_pdf_evidence_snippet(target_row["display_text"]),
        query="사업보고서 주요 내용",
        locator=locator,
        bounded_expansion_applied=False,
    )
    ready = quality.answer_ready_pdf_evidence(
        row=target_row,
        locator=locator,
        query="사업보고서 주요 내용",
        context_index=context_index,
        audit=audit,
        max_chars=180,
    )

    assert ready["bounded_expansion_applied"] is True
    assert ready["locator"]["page"] == 3
    assert ready["locator"]["bbox"] == [50.0, 100.0, 540.0, 112.0]
    assert "제68기 사업보고서" in ready["answer_ready_snippet"]
    assert "사업의 내용과 재무" in ready["answer_ready_snippet"]
    assert "회사의 개요" in ready["answer_ready_snippet"]
    assert "다른 페이지" not in ready["answer_ready_snippet"]
    assert len(ready["answer_ready_snippet"]) <= 180
    assert ready["raw_snippet"] == target_row["display_text"]
    assert ready["normalized_snippet"].startswith("사 업 보 고 서 ... 1")
    assert ready["answer_ready_score"] > audit["answer_ready_score"]


def test_pdf_answer_ready_pairs_toc_anchor_with_same_column_body_window() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    target_row = pdf_manifest_row(
        source_atom_id="src-toc",
        search_view_id="search-toc",
        document_version_id="docv-pdf",
        search_unit_id="su-page",
        page=7,
        bbox=[58.0, 88.0, 272.0, 101.0],
        text="제1장 과업개요 ........................................ 01",
    )
    same_page_rows = [
        target_row,
        pdf_manifest_row(
            source_atom_id="src-other-column",
            search_view_id="search-other-column",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=7,
            bbox=[330.0, 104.0, 540.0, 122.0],
            text="제2장 환경분석의 세부 표제는 이 창에 섞이면 안 됩니다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-body",
            search_view_id="search-body",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=7,
            bbox=[60.0, 112.0, 276.0, 138.0],
            text="본 과업은 항공기 소음 피해 현황을 조사하고 주민 지원 방안을 검토하는 데 목적이 있다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-body-next",
            search_view_id="search-body-next",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=7,
            bbox=[60.0, 141.0, 276.0, 165.0],
            text="과업의 범위에는 관련 문헌 연구와 사례 분석, 개선 방안 도출이 포함된다.",
        ),
    ]
    context_index = quality.build_pdf_context_index(same_page_rows)
    locator = quality.extract_locator({**target_row, **quality.parse_locator_text(target_row["embedding_text"])})
    audit = quality.pdf_evidence_readiness_audit(
        raw_snippet=target_row["display_text"],
        normalized_snippet=quality.normalize_pdf_evidence_snippet(target_row["display_text"]),
        query="과업개요 목적 범위",
        locator=locator,
        bounded_expansion_applied=False,
    )

    ready = quality.answer_ready_pdf_evidence(
        row=target_row,
        locator=locator,
        query="과업개요 목적 범위",
        context_index=context_index,
        audit=audit,
        max_chars=260,
    )

    assert ready["bounded_expansion_applied"] is True
    assert "항공기 소음 피해 현황" in ready["answer_ready_snippet"]
    assert "개선 방안 도출" in ready["answer_ready_snippet"]
    assert "제2장 환경분석" not in ready["answer_ready_snippet"]
    assert ready["locator"]["bbox"] == [58.0, 88.0, 272.0, 101.0]


def test_pdf_answer_ready_same_page_expansion_suppresses_far_broad_context() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    target_row = pdf_manifest_row(
        source_atom_id="src-anchor",
        search_view_id="search-anchor",
        document_version_id="docv-pdf",
        search_unit_id="su-page",
        page=5,
        bbox=[60.0, 100.0, 520.0, 114.0],
        text="제2절 주요 결과 ........................................ 15",
    )
    same_page_rows = [
        target_row,
        pdf_manifest_row(
            source_atom_id="src-body",
            search_view_id="search-body",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=5,
            bbox=[60.0, 122.0, 520.0, 140.0],
            text="주요 결과는 이용자 만족도가 상승했고 응답률도 개선되었다는 점이다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-body-next",
            search_view_id="search-body-next",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=5,
            bbox=[60.0, 145.0, 520.0, 162.0],
            text="다만 표본 규모가 작아 다음 조사에서 추가 검증이 필요하다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-far-footer",
            search_view_id="search-far-footer",
            document_version_id="docv-pdf",
            search_unit_id="su-page",
            page=5,
            bbox=[60.0, 620.0, 520.0, 640.0],
            text="부록 안내 문구와 연락처는 본문 근거 창에 섞이면 안 됩니다.",
        ),
    ]
    context_index = quality.build_pdf_context_index(same_page_rows)
    locator = quality.extract_locator({**target_row, **quality.parse_locator_text(target_row["embedding_text"])})
    audit = quality.pdf_evidence_readiness_audit(
        raw_snippet=target_row["display_text"],
        normalized_snippet=quality.normalize_pdf_evidence_snippet(target_row["display_text"]),
        query="주요 결과 만족도 응답률",
        locator=locator,
        bounded_expansion_applied=False,
    )

    ready = quality.answer_ready_pdf_evidence(
        row=target_row,
        locator=locator,
        query="주요 결과 만족도 응답률",
        context_index=context_index,
        audit=audit,
        max_chars=360,
    )

    assert ready["bounded_expansion_applied"] is True
    assert "이용자 만족도" in ready["answer_ready_snippet"]
    assert "추가 검증" in ready["answer_ready_snippet"]
    assert "부록 안내" not in ready["answer_ready_snippet"]
    assert ready["bounded_expansion_scope"] == "same_page_native_bounded_window"


def test_pdf_answer_ready_score_demotes_locator_only_dot_heavy_evidence() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    locator = {"source_pdf_path": "report.pdf", "page": 2, "bbox": [1, 2, 3, 4], "region_type": "text_block"}
    weak = quality.pdf_evidence_readiness_audit(
        raw_snippet="전자공시시스템 dart.fss.or.kr Page 2 ........................................ 3",
        normalized_snippet=quality.normalize_pdf_evidence_snippet(
            "전자공시시스템 dart.fss.or.kr Page 2 ........................................ 3"
        ),
        query="감사보고서 핵심 사항",
        locator=locator,
        bounded_expansion_applied=False,
    )
    dense = quality.pdf_evidence_readiness_audit(
        raw_snippet="감사의견 우리는 동성제약 주식회사의 재무제표를 감사하였으며 핵심 감사사항을 검토하였습니다.",
        normalized_snippet=quality.normalize_pdf_evidence_snippet(
            "감사의견 우리는 동성제약 주식회사의 재무제표를 감사하였으며 핵심 감사사항을 검토하였습니다."
        ),
        query="감사보고서 핵심 사항",
        locator=locator,
        bounded_expansion_applied=False,
    )

    assert weak["dot_leader_or_repeated_punctuation_ratio"] > 0
    assert weak["locator_only_flag"] is True
    assert dense["locator_only_flag"] is False
    assert dense["answer_ready_score"] > weak["answer_ready_score"]


def test_pdf_answer_ready_dry_run_audit_is_diagnostic_only_and_keeps_xlsx_unchanged(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    manifest = tmp_path / "manifest.jsonl"
    silver = tmp_path / "silver.jsonl"
    pdf_row = pdf_manifest_row(
        source_atom_id="src-pdf",
        search_view_id="search-pdf",
        document_version_id="docv-pdf",
        search_unit_id="su-page",
        page=1,
        bbox=[60.0, 90.0, 540.0, 105.0],
        text="목 차............................................................................1",
    )
    pdf_neighbor = pdf_manifest_row(
        source_atom_id="src-pdf-neighbor",
        search_view_id="search-pdf-neighbor",
        document_version_id="docv-pdf",
        search_unit_id="su-page",
        page=1,
        bbox=[60.0, 114.0, 540.0, 130.0],
        text="보고서의 주요 내용은 재무상태와 영업 현황을 포함합니다.",
    )
    xlsx_row = xlsx_manifest_row()
    manifest.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in [pdf_row, pdf_neighbor, xlsx_row]) + "\n",
        encoding="utf-8",
    )
    silver.write_text("", encoding="utf-8")

    summary = quality.run_benchmark(
        manifest_path=manifest,
        silver_manifest_path=silver,
        output_dir=tmp_path / "quality",
        run_label="pdf_answer_ready_unit",
        model="unused",
        base_url="http://localhost:9/v1",
        cases_per_family=1,
        max_tokens=10,
        query_max_tokens=10,
        timeout_seconds=1,
        dry_run=True,
    )
    rows = read_jsonl(tmp_path / "quality" / "pdf_xlsx_llm_quality_pdf_answer_ready_unit_responses.jsonl")
    pdf_rows = [row for row in rows if row["family"] == "PDF"]
    xlsx_rows = [row for row in rows if row["family"] == "XLSX"]
    audit_rows = read_jsonl(ROOT / summary["pdf_evidence_readiness_audit_path"])

    assert summary["status"] == "PASS_DRY_RUN"
    assert summary["policy"]["official_metric_input_rows"] == 0
    assert summary["policy"]["expected_answer_or_supporting_evidence_used"] is False
    assert summary["pdf_evidence_readiness_summary"]["pdf_case_count"] == 1
    assert summary["pdf_evidence_readiness_summary"]["bounded_expansion_applied_count"] == 1
    assert summary["pdf_evidence_readiness_summary"]["avg_raw_answer_ready_score"] < summary[
        "pdf_evidence_readiness_summary"
    ]["avg_expanded_answer_ready_score"]
    assert summary["pdf_evidence_readiness_summary"]["avg_answer_ready_score_delta"] > 0
    assert len(audit_rows) == 1
    assert audit_rows[0]["raw_snippet"] == "목 차............................................................................1"
    assert audit_rows[0]["normalized_snippet"] == "목 차 ... 1"
    assert "재무상태와 영업 현황" in audit_rows[0]["answer_ready_snippet"]
    assert audit_rows[0]["raw_answer_ready_score"] < audit_rows[0]["answer_ready_score"]
    assert audit_rows[0]["locator"]["page"] == 1
    assert audit_rows[0]["locator"]["bbox"] == [60.0, 90.0, 540.0, 105.0]

    assert {row["prompt_mode"] for row in pdf_rows} == {
        "baseline_legacy_context",
        "final_locator_context",
        "answer_ready_context",
    }
    assert {row["evidence_variant"] for row in pdf_rows} == {"raw", "answer_ready"}
    raw_final = next(row for row in pdf_rows if row["prompt_mode"] == "final_locator_context")
    ready_final = next(row for row in pdf_rows if row["prompt_mode"] == "answer_ready_context")
    assert raw_final["effective_evidence_text"] == "목 차............................................................................1"
    assert ready_final["effective_evidence_text"] == audit_rows[0]["answer_ready_snippet"]
    assert ready_final["citation_locator"] == raw_final["citation_locator"]
    assert ready_final["policy"]["diagnostic_only"] is True
    assert ready_final["policy"]["official_metric_input_rows"] == 0

    assert {row["prompt_mode"] for row in xlsx_rows} == {
        "baseline_legacy_context",
        "final_locator_context",
        "answer_ready_context",
    }
    xlsx_final = next(row for row in xlsx_rows if row["prompt_mode"] == "final_locator_context")
    xlsx_ready = next(row for row in xlsx_rows if row["prompt_mode"] == "answer_ready_context")
    assert xlsx_ready["effective_evidence_text"] == xlsx_final["effective_evidence_text"]
    assert xlsx_ready["evidence_variant"] == "raw"


def test_natural_answer_quality_benchmark_can_opt_in_text_without_changing_pdf_xlsx_default(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    manifest = tmp_path / "manifest.jsonl"
    silver = tmp_path / "silver.jsonl"
    pdf_row = pdf_manifest_row(
        source_atom_id="src-pdf",
        search_view_id="search-pdf",
        document_version_id="docv-pdf",
        search_unit_id="su-page",
        page=1,
        bbox=[60.0, 90.0, 540.0, 105.0],
        text="본문에는 재난방송 수신환경 개선 노력이 포함된다.",
    )
    rows = [pdf_row, xlsx_manifest_row(), text_manifest_row()]
    manifest.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    silver.write_text("", encoding="utf-8")

    default_summary = quality.run_benchmark(
        manifest_path=manifest,
        silver_manifest_path=silver,
        output_dir=tmp_path / "default",
        run_label="default_pdf_xlsx",
        model="unused",
        base_url="http://localhost:9/v1",
        cases_per_family=1,
        max_tokens=10,
        query_max_tokens=10,
        timeout_seconds=1,
        dry_run=True,
    )
    text_summary = quality.run_benchmark(
        manifest_path=manifest,
        silver_manifest_path=silver,
        output_dir=tmp_path / "with_text",
        run_label="with_text",
        model="unused",
        base_url="http://localhost:9/v1",
        cases_per_family=1,
        max_tokens=10,
        query_max_tokens=10,
        timeout_seconds=1,
        dry_run=True,
        source_families=("PDF", "XLSX", "TEXT"),
    )

    rows_with_text = read_jsonl(tmp_path / "with_text" / "pdf_xlsx_llm_quality_with_text_responses.jsonl")
    text_rows = [row for row in rows_with_text if row["family"] == "TEXT"]

    assert default_summary["case_selection"]["cases_by_family"] == {"PDF": 1, "XLSX": 1}
    assert text_summary["case_selection"]["cases_by_family"] == {"PDF": 1, "TEXT": 1, "XLSX": 1}
    assert text_summary["source_families_requested"] == ["PDF", "XLSX", "TEXT"]
    assert {row["prompt_mode"] for row in text_rows} == {
        "baseline_legacy_context",
        "final_locator_context",
        "answer_ready_context",
    }
    assert {row["evidence_variant"] for row in text_rows} == {"raw"}
    assert text_rows[0]["policy"]["official_metric_input_rows"] == 0
    assert text_summary["query_quality"]["query_style_target_counts"]

    artifact_paths = {key: Path(value) for key, value in text_summary["artifact_paths"].items()}
    for key in (
        "metrics_json",
        "per_family_json",
        "per_query_jsonl",
        "failure_taxonomy_json",
        "failure_taxonomy_jsonl",
    ):
        assert artifact_paths[key].exists()
        assert text_summary["artifact_hashes"][f"{key}_sha256"] == sha256_file(artifact_paths[key])

    metrics = read_json(artifact_paths["metrics_json"])
    per_family = read_json(artifact_paths["per_family_json"])
    per_query = read_jsonl(artifact_paths["per_query_jsonl"])
    failure_taxonomy = read_json(artifact_paths["failure_taxonomy_json"])
    failure_taxonomy_rows = read_jsonl(artifact_paths["failure_taxonomy_jsonl"])

    assert metrics["official_metric_input_rows"] == 0
    assert metrics["adapter_enabled"] is False
    assert metrics["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert metrics["promotion_evidence"] is False
    assert metrics["threshold_tuning"] is False
    assert metrics["winner_selection"] is False
    assert metrics["no_collapsed_cross_family_score"] is True
    assert metrics["source_families_reported_separately"] == ["PDF", "XLSX", "TEXT"]
    assert metrics["answer_quality"]["answer_ready_context"]["diagnostic_aggregate_only"] is True
    assert metrics["answer_quality"]["answer_ready_context"]["headline_allowed"] is False
    assert metrics["answer_quality"]["answer_ready_context"]["no_collapsed_cross_family_score"] is True
    assert per_family["official_metric_input_rows"] == 0
    assert per_family["no_collapsed_cross_family_score"] is True
    assert set(per_family["families"]) == {"PDF", "XLSX", "TEXT"}
    assert failure_taxonomy["official_metric_input_rows"] == 0
    assert len(per_query) == len(failure_taxonomy_rows) == 3
    for row in per_query:
        assert row["official_metric_input_rows"] == 0
        assert row["official_metric_candidate"] is False
        assert row["promotion_evidence"] is False
        assert "source_identity" not in row
        assert "evidence_text" not in row
        assert "expected_answer" not in row
        assert "supporting_evidence" not in row


def test_non_pdf_answer_ready_reuses_final_locator_response_to_neutralize_llm_regression(
    tmp_path,
    monkeypatch,
) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    manifest = tmp_path / "manifest.jsonl"
    silver = tmp_path / "silver.jsonl"
    manifest.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True)
            for row in [xlsx_manifest_row(), text_manifest_row()]
        )
        + "\n",
        encoding="utf-8",
    )
    silver.write_text("", encoding="utf-8")
    calls: list[str] = []

    def fake_llm(**kwargs: Any) -> str:
        system_prompt = kwargs["system_prompt"]
        user_prompt = kwargs["user_prompt"]
        calls.append(system_prompt)
        if system_prompt.startswith("You rewrite Korean diagnostic RAG benchmark queries"):
            query = (
                "5호선 2019년 2월 승차총승객수 수치"
                if "승차총승객수" in user_prompt
                else "실크캣 소년 성격 행동"
            )
            return json.dumps({"query": query, "style": "terse_question", "rationale": "unit"}, ensure_ascii=False)
        if "15,446,522" in user_prompt:
            return json.dumps(
                {
                    "answer": "2019년 2월 5호선 승차총승객수 15,446,522명",
                    "citations": [{"citation_id": "S1", "locator": "sheet=Sheet1; cell=B2"}],
                    "abstain_reason": "",
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "answer": "실크캣 소년은 조용한 성격과 특정 장면의 행동으로 소개된다.",
                "citations": [{"citation_id": "S1", "locator": "text_locator=paragraph-3"}],
                "abstain_reason": "",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(quality, "call_local_llm", fake_llm)
    summary = quality.run_benchmark(
        manifest_path=manifest,
        silver_manifest_path=silver,
        output_dir=tmp_path / "reuse",
        run_label="non_pdf_reuse",
        model="unused",
        base_url="http://localhost:9/v1",
        cases_per_family=1,
        max_tokens=80,
        query_max_tokens=80,
        timeout_seconds=1,
        source_families=("XLSX", "TEXT"),
    )
    rows = read_jsonl(tmp_path / "reuse" / "pdf_xlsx_llm_quality_non_pdf_reuse_responses.jsonl")
    by_mode = {(row["family"], row["prompt_mode"]): row for row in rows}

    for family in ("XLSX", "TEXT"):
        final_row = by_mode[(family, "final_locator_context")]
        ready_row = by_mode[(family, "answer_ready_context")]
        assert ready_row["raw_response"] == final_row["raw_response"]
        assert ready_row["score"] == final_row["score"] | {"answer_ready_reused_raw_final": True}
        assert ready_row["answer_ready_reused_raw_final"] is True
        assert ready_row["answer_ready_reuse_reason"] == "non_pdf_answer_ready_context_reuses_final_locator_response"

    assert summary["answer_quality"]["delta_by_family_answer_ready_minus_raw_final"]["XLSX"]["quality_pass"] == 0
    assert summary["answer_quality"]["delta_by_family_answer_ready_minus_raw_final"]["TEXT"]["quality_pass"] == 0
    assert summary["per_family_metrics"]["families"]["XLSX"]["raw_pass_to_ready_fail_regression"] == 0
    assert summary["per_family_metrics"]["families"]["TEXT"]["raw_pass_to_ready_fail_regression"] == 0
    assert len([call for call in calls if call.startswith("You rewrite Korean diagnostic")]) == 2


def test_v3_9_per_query_rows_exclude_shortcut_buckets_and_keep_rows() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    evidence = "지역순환경제 정책은 지역 자원 순환과 산업 연계를 통해 실행 전략을 마련한다."
    cases = [
        quality.EvidenceCase(
            case_id=case_id,
            family="PDF",
            source_atom_id=f"src-{case_id}",
            doc_id="docv",
            section="page-1",
            evidence_text=evidence,
            locator={"source_pdf_path": "D:/safe/region-report.pdf", "page": 1, "bbox": [1, 2, 3, 4]},
            source_identity=f"PDF:docv:{case_id}",
        )
        for case_id in ("exact", "title", "drift", "index")
    ]
    query_specs = {
        "exact": ("지역순환경제 정책", "지역순환경제 정책", "exact_query_hack"),
        "title": ("region-report.pdf 지역순환경제 정책", "지역순환경제 정책", "source_title_leak"),
        "drift": ("반도체 공급망 수출 규제", "지역순환경제 정책", "major_topic_drift"),
        "index": ("지역 자원 순환 산업 연계 실행 전략", "page 1", "index_to_content"),
    }
    query_rows = []
    output_rows = []
    for case in cases:
        query, seed_query, _bucket = query_specs[case.case_id]
        query_rows.append({"query": query, "seed_query": seed_query})
        for mode in ("baseline_legacy_context", "final_locator_context", "answer_ready_context"):
            row = packet_unit_response_row(case.case_id, mode, query=query, quality_pass=True)
            row["seed_query"] = seed_query
            output_rows.append(row)

    rows = quality.v3_9_per_query_rows(
        cases=cases,
        query_rows=query_rows,
        output_rows=output_rows,
        split_role=quality.VALIDATION_SPLIT_ROLE,
    )

    assert len(rows) == 4
    assert {row["case_id"]: row["query_fidelity_bucket"] for row in rows} == {
        case_id: bucket for case_id, (_query, _seed, bucket) in query_specs.items()
    }
    assert all(row["query_fidelity_headline_included"] is False for row in rows)
    assert all(row["official_metric_input_rows"] == 0 for row in rows)
    assert all(row["official_metric_candidate"] is False for row in rows)


def test_v3_9_validation_holdout_fallback_blocks_success_when_disjoint_pool_is_insufficient() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_llm_quality_benchmark as quality

    rows = [
        pdf_manifest_row(
            source_atom_id="src-dev",
            search_view_id="search-dev",
            document_version_id="docv-shared",
            search_unit_id="su-dev",
            page=1,
            bbox=[60.0, 90.0, 540.0, 105.0],
            text="지역순환경제 정책은 지역 자원 순환과 산업 연계를 통해 실행 전략을 마련한다.",
        ),
        pdf_manifest_row(
            source_atom_id="src-validation",
            search_view_id="search-validation",
            document_version_id="docv-shared",
            search_unit_id="su-validation",
            page=2,
            bbox=[60.0, 120.0, 540.0, 145.0],
            text="지역순환경제 실행 계획은 산업 연계와 순환 자원 활용을 중점으로 둔다.",
        ),
    ]
    dev_cases = quality.load_evidence_cases_from_rows(
        rows,
        cases_per_family=1,
        source_families=("PDF",),
    )
    dev_selection = quality.case_selection_summary(
        dev_cases,
        split_role=quality.DEFAULT_SPLIT_ROLE,
    )
    validation_cases = quality.load_evidence_cases_from_rows(
        rows,
        cases_per_family=1,
        split_role=quality.VALIDATION_SPLIT_ROLE,
        dev_cases=dev_cases,
        source_families=("PDF",),
    )
    selection = quality.case_selection_summary(
        validation_cases,
        split_role=quality.VALIDATION_SPLIT_ROLE,
        dev_cases=dev_cases,
    )

    assert [case.case_id for case in dev_cases] == ["pdf-001"]
    assert dev_selection["dev_only"] is True
    assert dev_selection["source_document_disjoint_from_dev"] == "not_applicable_dev_split"
    assert dev_selection["success_evidence_allowed"] is False
    assert [case.case_id for case in validation_cases] == ["pdf-002"]
    assert selection["fallback_strategy_used"] == "non_disjoint_fill"
    assert selection["source_document_disjoint_from_dev"] is False
    assert selection["success_evidence_allowed"] is False
    assert selection["official_metric_input_rows"] == 0


def test_v3_9_review_packet_query_fidelity_matches_compact_metrics(tmp_path) -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    label = "v3_9_natural_answer_quality_validation_6pf"
    summary_path = REPORT_DIR / "quality" / f"pdf_xlsx_llm_quality_{label}_summary.json"
    metrics_path = REPORT_DIR / "quality" / f"pdf_xlsx_llm_quality_{label}_metrics.json"
    per_query_path = REPORT_DIR / "quality" / f"pdf_xlsx_llm_quality_{label}_per_query.jsonl"
    require_pdf_xlsx_answer_quality_local_artifacts(summary_path, metrics_path, per_query_path)

    report = packet.run_packet(summary_path=summary_path, output_dir=tmp_path)
    metric_rows = {row["case_id"]: row for row in read_jsonl(per_query_path)}
    packet_rows = {row["case_id"]: row for row in read_jsonl(tmp_path / "query_fidelity_audit.jsonl")}
    review_rows = read_jsonl(tmp_path / "review_packet.jsonl")

    assert set(packet_rows) == set(metric_rows)
    for case_id, metric_row in metric_rows.items():
        packet_row = packet_rows[case_id]
        assert packet_row["query_fidelity_bucket"] == metric_row["query_fidelity_bucket"]
        assert packet_row["query_fidelity_headline_included"] == metric_row["query_fidelity_headline_included"]
        assert packet_row["query_fidelity_exclusion_reason"] == metric_row["query_fidelity_exclusion_reason"]
        assert packet_row["official_metric_input_rows"] == 0
    expected_policy = sorted(
        {
            row["query_fidelity_exclusion_reason"]
            for row in packet_rows.values()
            if not row["query_fidelity_headline_included"]
        }
    )
    assert report["query_fidelity_summary"]["excluded_from_headline_policy"] == expected_policy
    assert report["query_fidelity_summary"]["headline_included"] == read_json(metrics_path)["query_fidelity_included_count"]
    assert report["query_fidelity_summary"]["excluded"] == read_json(metrics_path)["query_fidelity_excluded_count"]
    assert all(row["official_metric_input_rows"] == "0" for row in review_rows)


def test_v3_9_query_fidelity_classifier_separates_shortcut_and_drift_buckets() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    case = packet.quality_benchmark.EvidenceCase(
        case_id="pdf-001",
        family="PDF",
        source_atom_id="src",
        doc_id="docv",
        section="page-1",
        evidence_text="지역순환경제 정책은 지역 자원 순환과 산업 연계를 통해 실행 전략을 마련한다.",
        locator={"source_pdf_path": "D:/safe/region-report.pdf", "page": 1, "bbox": [1, 2, 3, 4]},
    )

    exact = packet.query_fidelity_audit_v3_9(
        case=case,
        query="지역순환경제 정책",
        seed_query="지역순환경제 정책",
        evidence_text=case.evidence_text,
    )
    source_title = packet.query_fidelity_audit_v3_9(
        case=case,
        query="region-report.pdf 지역순환경제 정책",
        seed_query="지역순환경제 정책",
        evidence_text=case.evidence_text,
    )
    drift = packet.query_fidelity_audit_v3_9(
        case=case,
        query="반도체 공급망 수출 규제",
        seed_query="지역순환경제 정책",
        evidence_text=case.evidence_text,
    )
    index_to_content = packet.query_fidelity_audit_v3_9(
        case=case,
        query="지역 자원 순환과 산업 연계 실행 전략",
        seed_query="page 1",
        evidence_text=case.evidence_text,
    )

    assert exact["v3_9_bucket"] == "exact_query_hack"
    assert source_title["v3_9_bucket"] == "source_title_leak"
    assert drift["v3_9_bucket"] == "major_topic_drift"
    assert index_to_content["v3_9_bucket"] == "index_to_content"
    assert not exact["headline_included"]
    assert not source_title["headline_included"]
    assert not drift["headline_included"]
    assert not index_to_content["headline_included"]
    assert exact["official_metric_candidate"] is False


def test_v3_9_query_fidelity_classifier_separates_answer_value_in_query_bucket() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_pdf_xlsx_answer_quality_review_packet as packet

    case = packet.quality_benchmark.EvidenceCase(
        case_id="xlsx-001",
        family="XLSX",
        source_atom_id="src",
        doc_id="docv",
        section="Sheet1",
        evidence_text="숨기려 해도 숨길 수 없는 마음 : 배명훈 장편소설",
        locator={
            "workbook": "books.xlsx",
            "sheet": "Sheet1",
            "range": "A10:J10",
            "normalized_value": "숨기려 해도 숨길 수 없는 마음 : 배명훈 장편소설",
        },
    )

    answer_value = packet.query_fidelity_audit_v3_9(
        case=case,
        query="숨기려 해도 숨길 수 없는 마음 배명훈 장편소설 뭐야?",
        seed_query="도서정보 자료에서 특정 항목을 찾아줘",
        evidence_text=case.evidence_text,
    )

    assert answer_value["v3_9_bucket"] == "answer_value_in_query"
    assert answer_value["query_fidelity_exclusion_reason"] == "answer_value_in_query_unapproved"
    assert answer_value["headline_included"] is False
    assert answer_value["official_metric_candidate"] is False


def test_v3_9_pdf_xlsx_bottleneck_quality_artifacts_are_validation_separated_and_hash_locked() -> None:
    run_id = "official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    per_family_path = REPORT_DIR / f"{run_id}_per_family.json"
    per_query_path = REPORT_DIR / f"{run_id}_per_query.jsonl"
    failure_taxonomy_path = REPORT_DIR / f"{run_id}_failure_taxonomy.json"
    query_fidelity_path = REPORT_DIR / f"{run_id}_query_fidelity_audit.jsonl"
    pdf_residual_path = REPORT_DIR / f"{run_id}_pdf_residual_review.jsonl"
    xlsx_residual_path = REPORT_DIR / f"{run_id}_xlsx_locator_residual_review.jsonl"
    split_manifest_path = REPORT_DIR / f"{run_id}_split_manifest.json"

    for path in (
        summary_path,
        metrics_path,
        per_family_path,
        per_query_path,
        failure_taxonomy_path,
        query_fidelity_path,
        pdf_residual_path,
        xlsx_residual_path,
        split_manifest_path,
    ):
        assert resolve_report_artifact_path(path).exists(), path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    per_family = read_json(per_family_path)
    per_query = read_jsonl(per_query_path)
    failure_taxonomy = read_json(failure_taxonomy_path)
    query_fidelity = read_jsonl(query_fidelity_path)
    pdf_residuals = read_jsonl(pdf_residual_path)
    xlsx_residuals = read_jsonl(xlsx_residual_path)
    split_manifest = read_json(split_manifest_path)

    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric_input_rows"] == 0
    assert summary["fine_tuning_executed"] is False
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["dev_only_gain_is_success_evidence"] is False
    assert summary["no_collapsed_pdf_xlsx_headline"] is True
    assert summary["query_fidelity_excluded_rows_retained"] is True
    assert summary["candidate_rule_freeze"]["direct_normalized_value_query_matching"] is False
    assert summary["candidate_rule_freeze"]["case_id_branches"] is False
    assert summary["candidate_rule_freeze"]["exact_query_hacks"] is False
    assert summary["candidate_rule_freeze"]["file_or_source_title_hacks"] is False
    assert summary["candidate_rule_freeze"]["expected_supporting_gold_text_input"] is False
    assert summary["candidate_rule_freeze"]["pass_fail_threshold_tuning"] is False

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
        assert metrics[flag] is False

    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["adapter_enabled"] is False
    assert metrics["validation_improvement_only_generalized_signal"] is True
    assert metrics["generalized_validation_signal"]["PDF"] == {
        "delta": 1,
        "generalized": True,
        "query_fidelity_included_answer_ready": "3/4",
        "query_fidelity_included_raw_final": "2/4",
    }
    assert metrics["generalized_validation_signal"]["XLSX"]["delta"] == 0
    assert metrics["generalized_validation_signal"]["XLSX"]["generalized"] is False
    assert metrics["XLSX"]["table_or_range_resolve"]["@1"]["numerator"] == 22
    assert metrics["XLSX"]["cell_or_value_resolve"]["@1"]["numerator"] == 19
    assert metrics["XLSX"]["miss_taxonomy"]["primary_category_counts"][
        "table_or_range_miss_after_sheet_hit"
    ] == 219
    assert metrics["XLSX"]["direct_normalized_value_query_matching_used"] is False
    assert metrics["PDF"]["ocr_rationale"]["decision"] == "skipped"
    assert metrics["PDF"]["ocr_rationale"]["ocr_touched"] is False

    assert per_family["source_families_reported_separately"] == ["PDF", "XLSX"]
    assert per_family["text_comparison_only"] is True
    assert per_family["validation"]["answer_quality"]["PDF"]["query_fidelity_included"][
        "answer_pass_like"
    ] == {"denominator": 4, "numerator": 3, "rate": 0.75}
    assert per_family["validation"]["answer_quality"]["XLSX"]["query_fidelity_included"][
        "answer_pass_like"
    ] == {"denominator": 1, "numerator": 1, "rate": 1.0}
    assert per_family["xlsx_locator_diagnostic"]["metric_movement_after_structural_specificity_rule"] == (
        "unchanged_on_current_344_row_v3_8_3_surface"
    )

    assert len(per_query) == 24
    assert {row["source_family"] for row in per_query} == {"PDF", "XLSX"}
    assert {row["split"] for row in per_query} == {"dev", "validation"}
    assert all(row["official_metric_input_rows"] == 0 for row in per_query)
    assert all("expected_answer" not in row and "supporting_evidence" not in row for row in per_query)
    validation_rows = [row for row in per_query if row["split"] == "validation"]
    assert sum(1 for row in validation_rows if row["query_fidelity_headline_included"]) == 5
    assert sum(1 for row in validation_rows if not row["query_fidelity_headline_included"]) == 7
    assert sum(1 for row in validation_rows if row["raw_pass_to_ready_fail_regression"]) == 0
    assert any(row["query_fidelity_bucket"] == "answer_value_in_query" for row in query_fidelity)

    assert failure_taxonomy["official_metric_input_rows"] == 0
    assert failure_taxonomy["xlsx_locator_miss_taxonomy"]["primary_category_counts"][
        "table_or_range_miss_after_sheet_hit"
    ] == 219
    assert len(pdf_residuals) == 12
    assert len(xlsx_residuals) == 325
    assert all(row["direct_normalized_value_query_matching_used"] is False for row in xlsx_residuals)
    assert split_manifest["validation_split"]["source_document_disjoint_from_dev"] is True
    assert split_manifest["validation_split"]["dev_overlap_document_count"] == 0
    assert split_manifest["protected_rows_role"] == "sealed_no_regression_reference_only_not_tuning_input"

    hash_contract = {
        "metrics_sha256": metrics_path,
        "per_family_sha256": per_family_path,
        "per_query_sha256": per_query_path,
        "failure_taxonomy_sha256": failure_taxonomy_path,
        "query_fidelity_audit_sha256": query_fidelity_path,
        "pdf_residual_review_sha256": pdf_residual_path,
        "xlsx_locator_residual_review_sha256": xlsx_residual_path,
        "split_manifest_sha256": split_manifest_path,
    }
    for hash_key, path in hash_contract.items():
        assert summary["artifact_sha256"][hash_key] == sha256_file(path)


def test_pdf_content_window_sufficiency_gate_blocks_tiny_locator_fragments() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from eval.harness import pdf_xlsx_answer_evidence_serializer as serializer
    from eval.harness import pdf_xlsx_deterministic_answer_compiler as compiler

    for raw_fragment in (
        "XI.",
        "1.",
        "Ⅰ.",
        "Page 2",
        "내부회계관리제도운영보고서....................................................................1",
    ):
        evidence_row = serializer.serialize_input_row(
            {
                "run_id": "unit_source",
                "row_index": 57,
                "track": "PDF",
                "query_id": "pdf_raw_locator_57",
                "query": "투자자 보호를 위하여 필요한 사항은 무엇인지 자세히 알려주세요.",
                "expected_answer_shape": "PDF_SECTION_WITH_SUMMARY",
                "context": {
                    "file_name": "dart_dongsung_business_report_2025_20250321.pdf",
                    "page_no": "2",
                    "bbox": [10, 20, 30, 40],
                    "locator": {
                        "file": "dart_dongsung_business_report_2025_20250321.pdf",
                        "page": "2",
                        "bbox": [10, 20, 30, 40],
                    },
                    "paragraph_context": [raw_fragment],
                    "sentence_context": [raw_fragment],
                },
            },
            run_id="unit_evidence",
        )

        assert evidence_row["answer_generation_allowed"] is False
        assert evidence_row["content_window_available"] is False
        assert evidence_row["fail_closed_reason"] == "PDF_CONTENT_WINDOW_TOO_THIN"
        assert evidence_row["evidence_quality"]["pdf_content_window_usable"] is False

        compiled = compiler.compile_evidence_row(evidence_row, run_id="unit_compiled")

        assert compiled["compiled_answer"]["answer"] == ""
        assert compiled["compiled_answer"]["abstain_reason"] == "PDF_CONTENT_WINDOW_TOO_THIN"
        assert compiled["compiled_answer"]["citations"] == []

    legacy_compiled = compiler.compile_evidence_row(
        {
            "run_id": "legacy_unit_source",
            "track": "PDF",
            "query_id": "legacy_pdf_raw_locator",
            "query": "사업보고서 내용을 확인하고 싶은데 어떤 정보가 포함되어 있나요?",
            "expected_answer_shape": "PDF_SECTION_WITH_SUMMARY",
            "answer_allowed": True,
            "answer_generation_allowed": True,
            "evidence_object": {
                "evidence_type": "pdf",
                "content_summary": "1.",
                "paragraph_block_text": "1.",
                "page": "3",
                "locator": {"file": "dart_dongsung_business_report_2026_20260407_correction.pdf", "page": "3"},
            },
        },
        run_id="unit_compiled",
    )

    assert legacy_compiled["compiled_answer"]["answer"] == ""
    assert legacy_compiled["compiled_answer"]["abstain_reason"] == "PDF_CONTENT_WINDOW_TOO_THIN"


def test_pdf_adjacent_block_window_can_replace_tiny_bbox_fragment_as_diagnostic_input() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    from eval.harness import pdf_xlsx_answer_evidence_serializer as serializer
    from eval.harness import pdf_xlsx_deterministic_answer_compiler as compiler
    import rag_pdf_xlsx_answer_generation_input_builder as builder

    paragraph_window = builder.pdf_adjacent_block_window_from_blocks(
        [
            (10.0, 10.0, 40.0, 20.0, "XI.", 0, 0),
            (
                10.0,
                24.0,
                300.0,
                70.0,
                "투자자 보호를 위하여 필요한 사항은 투자위험, 감사의견, 내부통제 "
                "관련 정보를 함께 확인해야 한다는 내용입니다.",
                1,
                0,
            ),
        ],
        bbox=[10.0, 10.0, 40.0, 20.0],
        max_chars=240,
    )

    evidence_row = serializer.serialize_input_row(
        {
            "run_id": "unit_source",
            "row_index": 57,
            "track": "PDF",
            "query_id": "pdf_raw_locator_57",
            "query": "투자자 보호를 위하여 필요한 사항은 무엇인지 자세히 알려주세요.",
            "expected_answer_shape": "PDF_SECTION_WITH_SUMMARY",
            "context": {
                "file_name": "dart_dongsung_business_report_2025_20250321.pdf",
                "page_no": "2",
                "bbox": [10, 20, 30, 40],
                "locator": {
                    "file": "dart_dongsung_business_report_2025_20250321.pdf",
                    "page": "2",
                    "bbox": [10, 20, 30, 40],
                },
                "paragraph_context": ["XI."],
                "paragraph_window": paragraph_window,
                "sentence_context": ["XI."],
            },
        },
        run_id="unit_evidence",
    )

    assert paragraph_window.startswith("XI. 투자자 보호를 위하여")
    assert evidence_row["answer_generation_allowed"] is True
    assert evidence_row["content_window_available"] is True
    assert evidence_row["content_window_basis"] == ["content_summary", "paragraph_window"]
    assert evidence_row["evidence_object"]["content_source"] == "paragraph_window"
    assert evidence_row["evidence_object"]["content_summary"].startswith("투자자 보호를 위하여")

    compiled = compiler.compile_evidence_row(evidence_row, run_id="unit_compiled")

    assert compiled["compiled_answer"]["answer"].startswith("투자자 보호를 위하여")
    assert compiled["compiled_answer"]["citations"][0]["locator"]["page"] == "2"


def test_v3_8_file_grounded_run_measurement_wires_read_only_summary_without_answer_generation() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    args = runner.parse_args(["--run-id", runner.V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID])

    summary, rows = runner.run_measurement(args)

    assert rows == []
    assert summary["run_id"] == runner.V3_8_FILE_GROUNDED_RETRIEVAL_EVAL_RUN_ID
    assert summary["status"] == "DIAGNOSTIC_FILE_GROUNDED_RETRIEVAL_EVAL_COMPUTED"
    assert summary["source_run_id"] == runner.V3_7_2_SOURCE_REGISTRY_BACKED_RETRIEVAL_SMOKE_REPORT_RUN_ID
    assert summary["source_family_counts"]["PDF"] == 329
    assert summary["source_family_counts"]["XLSX"] == 344
    assert set(summary["per_source_family"]) == {"PDF", "XLSX"}
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
    assert summary["answer_generation_metric_computed"] is False
    assert summary["gold_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["source_atom_registry_canonical_truth_used_for_metrics"] is True
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["artifact_paths"]["metrics_json"].endswith(
        "official_answer_citation_agentic_loop_run_v3_8_file_grounded_retrieval_eval_metrics.json"
    )
    assert summary["fail_closed_reasons"] == []


def test_v3_7_0_source_registry_no_vector_hydration_and_citation_smoke() -> None:
    hydration = read_json(V3_7_0_SOURCE_REGISTRY_HYDRATION_SMOKE)
    registry_rows = read_jsonl(SOURCE_ATOM_REGISTRY_JSONL)
    examples = {row["source_family"]: row for row in registry_rows if row["source_family"] not in {}}

    assert hydration["families_passed"] == ["PDF", "TEXT", "XLSX"]
    assert hydration["no_vector_evidence_bundle_hydration_passed"] is True
    assert hydration["no_vector_citation_rendering_passed"] is True
    assert hydration["vector_db_used"] is False
    assert hydration["llm_used"] is False
    assert hydration["vector_metadata_used_as_canonical_citation_source"] is False
    assert hydration["runtime_evidence_allowed_count"] == 3
    assert hydration["official_evidence_allowed_only_with_strict_locator_fields"] is True

    for family in ("TEXT", "PDF", "XLSX"):
        atom = examples[family]
        assert atom["source_atom_id"]
        assert atom["content_hash"]
        assert atom["extraction_version"]
        assert atom["raw_locator"]
        assert atom["normalized_text_or_value_snapshot"]
        assert atom["canonical_citation_payload"]["source_identity"] == atom["source_identity"]
        assert atom["canonical_citation_payload"]["canonical_payload_source"] == "source_registry"
        assert atom["gold_or_label_source"] is False
        assert atom["expected_answer_source"] is False
        assert atom["generation_source_allowed"] is False or atom["source_family"] != "TEXT"

    assert examples["TEXT"]["raw_locator"]["chunk_id"]
    assert examples["TEXT"]["raw_locator"]["stable_locator_fingerprint"]
    assert examples["PDF"]["raw_locator"]["source_pdf_path"]
    assert examples["PDF"]["raw_locator"]["page"] is not None
    assert examples["PDF"]["raw_locator"]["physical_page_index"] is not None
    assert examples["PDF"]["raw_locator"]["bbox"]
    assert examples["PDF"]["raw_locator"]["region_type"]
    assert examples["XLSX"]["raw_locator"]["workbook"]
    assert examples["XLSX"]["raw_locator"]["sheet"]
    assert examples["XLSX"]["raw_locator"]["value_locator"]


def test_v3_7_1_all_source_citable_nonprod_index_is_source_atom_backed_without_vector_truth() -> None:
    summary = read_json(V3_7_1_ALL_SOURCE_CITABLE_SUMMARY)
    inventory = read_json(V3_7_1_ALL_SOURCE_CITABLE_SOURCE_INVENTORY)
    build_summary = read_json(V3_7_1_ALL_SOURCE_CITABLE_INDEX_BUILD_SUMMARY)
    hydration = read_json(V3_7_1_ALL_SOURCE_CITABLE_HYDRATION_SMOKE)
    failure_buckets = read_json(V3_7_1_ALL_SOURCE_CITABLE_FAILURE_BUCKETS)
    build = read_json(V3_7_1_ALL_SOURCE_CITABLE_INDEX_DIR / "build.json")
    ingest = read_json(V3_7_1_ALL_SOURCE_CITABLE_INDEX_DIR / "ingest_manifest.json")
    index_inventory = read_json(V3_7_1_ALL_SOURCE_CITABLE_INDEX_DIR / "source_inventory.json")

    assert summary["run_id"] == V3_7_1_ALL_SOURCE_CITABLE_RUN_ID
    assert summary["artifact_kind"] == "diagnostic_all_source_citable_nonprod_index_build"
    assert summary["run_class"] == "diagnostic_only_all_source_citable_nonprod_index_build"
    assert set(summary["outcome_choices"]) == V3_7_1_ALL_SOURCE_CITABLE_OUTCOMES
    assert summary["outcome"] == "ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILT"
    assert summary["next_allowed_phase"] == "v3_7_2_source_registry_backed_retrieval_smoke"
    assert summary["source_registry_outcome"] == "SOURCE_REGISTRY_MATERIALIZED_READY"
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["search_view_source_atom_contract"] is True
    assert summary["vector_db_role"] == "candidate_generator_only"
    assert summary["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["retrieval_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["hybrid_retrieval_baseline_computed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["production_db_used"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False

    assert summary["index_path"] == "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1"
    assert summary["search_view_count"] == build_summary["search_view_manifest_row_count"]
    assert summary["search_view_count"] == inventory["counts"]["search_views_indexed"]
    assert summary["search_view_count"] == index_inventory["counts"]["search_views_indexed"]
    assert summary["source_family_counts"] == {"TEXT": 135608, "PDF": 329, "XLSX": 343}
    assert summary["official_overlap_count"] == 29
    assert summary["snapshot_only_count"] == 3
    assert summary["blocking_buckets"] == []
    assert summary["fail_closed_reasons"] == []
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["load_check"]["passed"] is True
    assert summary["load_check"]["canonical_payload_absent_from_vector_metadata"] is True
    assert summary["load_check"]["search_view_source_atom_pointer_valid"] is True
    assert summary["load_check"]["official_29_rows_remain_protected_and_identifiable"] is True

    assert hydration["families_passed"] == ["PDF", "TEXT", "XLSX"]
    assert hydration["no_vector_evidence_bundle_hydration_passed"] is True
    assert hydration["no_vector_citation_rendering_passed"] is True
    assert hydration["search_view_hit_hydrates_from_source_registry"] is True
    assert hydration["vector_metadata_used_as_canonical_citation_source"] is False
    assert hydration["vector_payload_used_as_evidence_truth"] is False
    assert hydration["poisoned_vector_metadata_ignored_count"] == 3
    assert hydration["snapshot_only_policy_explicit"] is True
    assert failure_buckets["blocking_buckets"] == []
    assert failure_buckets["failure_bucket_counts"]["ALL_SOURCE_CITABLE_NONPROD_INDEX_BUILT"] == 1

    assert build["index_namespace"] == "rag-data-all-source-citable-nonprod-v1"
    assert build["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert ingest["search_view_source_atom_pointer_required"] is True
    assert ingest["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert (V3_7_1_ALL_SOURCE_CITABLE_INDEX_DIR / "faiss.index").exists()
    assert (V3_7_1_ALL_SOURCE_CITABLE_INDEX_DIR / "search_view_manifest.jsonl").exists()

    samples: list[dict[str, Any]] = []
    with (V3_7_1_ALL_SOURCE_CITABLE_INDEX_DIR / "search_view_manifest.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                samples.append(json.loads(line))
            if len(samples) >= 20:
                break
    assert samples
    assert all(row["source_atom_id"] and row["source_atom_ids"] == [row["source_atom_id"]] for row in samples)
    assert all("canonical_citation_payload" not in row for row in samples)
    assert all(row["canonical_citation_payload_present"] is False for row in samples)
    assert all(row["canonical_payload_stored_in_vector_metadata"] is False for row in samples)


def test_v3_7_2_source_registry_backed_retrieval_smoke_report_tracks_contract_survival_by_track() -> None:
    require_v3_7_2_local_artifacts(
        V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY,
        V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS,
        V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_FAILURE_BUCKETS,
        V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_PER_TRACK,
        V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SILVER_OVERLAY,
    )
    summary = read_json(V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SUMMARY)
    topk_rows = read_jsonl(V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_TOPK_ROWS)
    failure_buckets = read_json(V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_FAILURE_BUCKETS)
    per_track = read_json(V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_PER_TRACK)
    silver_overlay = read_json(V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_SILVER_OVERLAY)

    assert summary["run_id"] == V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_RUN_ID
    assert summary["artifact_kind"] == "v3_7_2_source_registry_backed_retrieval_smoke_report"
    assert summary["run_class"] == "diagnostic_only_source_registry_backed_retrieval_smoke_report"
    assert summary["contract_path"] == ["SearchView", "SourceAtom", "EvidenceBundle", "Citation render"]
    assert summary["input_artifacts"]["index_namespace"] == "rag-data-all-source-citable-nonprod-v1"
    assert summary["input_artifacts"]["source_atom_registry_jsonl"] == (
        "ai/eval/source_registry/source_atom_registry_v1.jsonl"
    )
    assert summary["top_k"] == 5
    assert summary["diagnostic_only"] is True
    assert summary["official_gold_usage"] == "sealed_no_regression_check_only"
    assert summary["silver_usage"] == "diagnostic_failure_distribution_only"
    assert summary["headline_aggregate_success_rate_reported"] is False
    assert summary["retrieval_score_primary_metric"] is False
    assert summary["answer_quality_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["promotion_readiness_opened"] is False
    assert summary["promotion_evidence"] is False
    assert summary["prompt_mutation"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["canonical_citation_payload_stored_in_vector_metadata"] is False

    assert failure_buckets["failure_bucket_definitions"] == V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_BUCKETS
    assert set(summary["failure_bucket_counts"]) == set(V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_BUCKETS)
    assert summary["row_level_retrieval_bottleneck"]["tracks"]["XLSX"]["target_not_in_topk_count"] == summary[
        "per_track_breakdown"
    ]["XLSX"]["retrieval_diagnostic_bucket_counts"]["target_not_in_topk"]
    assert summary["row_level_retrieval_bottleneck"]["tracks"]["XLSX"]["target_mapping_bucket_counts"][
        "locator_mapping_gap"
    ] == 1
    assert summary["row_level_retrieval_bottleneck"]["scope_tracks"]["silver_1000_diagnostic_overlay"]["XLSX"][
        "target_not_in_topk_count"
    ] <= summary["row_level_retrieval_bottleneck"]["tracks"]["XLSX"]["target_not_in_topk_count"]
    assert set(per_track["tracks"]) == {"TEXT", "PDF", "XLSX"}
    assert set(summary["per_track_breakdown"]) == {"TEXT", "PDF", "XLSX"}
    for track, breakdown in summary["per_track_breakdown"].items():
        assert track in {"TEXT", "PDF", "XLSX"}
        assert breakdown["query_count"] > 0
        assert "topk_hit_count" not in breakdown
        assert breakdown["topk_returned_count"] >= breakdown["query_count"]
        assert breakdown["same_track_hit_at_k_count"] <= breakdown["query_count"]
        assert breakdown["target_hit_at_k_count"] <= breakdown["query_count"]
        assert breakdown["contract_survival_at_k_count"] <= breakdown["topk_returned_count"]
        assert breakdown["target_contract_survival_at_k_count"] <= breakdown["target_hit_at_k_count"]
        assert breakdown["source_atom_hydrated_row_count"] <= breakdown["topk_returned_count"]
        assert breakdown["evidence_bundle_rendered_row_count"] <= breakdown["topk_returned_count"]
        assert breakdown["citation_rendered_row_count"] <= breakdown["topk_returned_count"]
        assert breakdown["top_failure_bucket"] in ["none", *V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_BUCKETS]
        assert breakdown["next_fix"]

    assert summary["retrieval_metric_interpretation"]["topk_returned_count"] == (
        "number of SearchView candidates returned; not target correctness"
    )
    assert summary["retrieval_routing_mode"] == "query_source_family_routed_for_structured_tracks"
    assert summary["routed_source_families"] == ["PDF", "XLSX"]
    assert summary["family_routed_missing_query_key_count"] == 0
    assert summary["family_routed_missing_query_keys"] == []
    assert summary["mixed_retrieval_baseline"]["candidate_pool_mode"] == "mixed_all_source_faiss_topk_before_family_routing"
    assert summary["per_track_breakdown"]["TEXT"]["target_hit_at_k_count"] == 20
    assert summary["per_track_breakdown"]["PDF"]["target_hit_at_k_count"] == 266
    assert summary["per_track_breakdown"]["XLSX"]["target_hit_at_k_count"] == 34
    assert summary["per_track_breakdown"]["PDF"]["retrieval_diagnostic_bucket_counts"]["target_not_in_topk"] == 63
    assert summary["per_track_breakdown"]["XLSX"]["retrieval_diagnostic_bucket_counts"]["target_not_in_topk"] == 310
    assert summary["sealed_gold_no_regression_check"]["target_hit_at_k_count"] == summary[
        "sealed_gold_no_regression_check"
    ]["target_hit_in_topk_count"]
    assert summary["sealed_gold_no_regression_check"]["target_hit_at_k_count"] == 20
    assert summary["row_level_retrieval_bottleneck"]["scope_tracks"]["sealed_gold_no_regression_check"]["XLSX"][
        "target_hit_at_k_count"
    ] == 19
    assert summary["sealed_gold_no_regression_check"]["target_contract_survival_at_k_count"] <= summary[
        "sealed_gold_no_regression_check"
    ]["target_hit_at_k_count"]
    assert summary["sealed_gold_no_regression_check"]["target_mapping_audit"]["row_count"] == 29
    assert summary["sealed_gold_no_regression_check"]["target_mapping_audit"]["target_present_in_index_count"] <= 29
    assert set(summary["family_routed_retrieval_smoke"]["tracks"]) >= {"PDF", "XLSX"}
    for track in ("PDF", "XLSX"):
        routed = summary["family_routed_retrieval_smoke"]["tracks"][track]
        assert routed["candidate_pool_source_family"] == track
        assert routed["query_count"] == summary["per_track_breakdown"][track]["query_count"]
        assert routed["topk_returned_count"] >= routed["query_count"]
        assert routed["same_track_hit_at_k_count"] == routed["query_count"]
        assert summary["per_track_breakdown"][track]["same_track_hit_at_k_count"] == routed["query_count"]
        assert summary["per_track_breakdown"][track]["off_track_returned_count"] == 0
        assert summary["per_track_breakdown"][track]["target_hit_at_k_count"] == routed["target_hit_at_k_count"]
        assert summary["per_track_breakdown"][track]["failure_bucket_counts"]["track_mismatch"] == 0
        assert summary["per_track_breakdown"][track]["retrieval_diagnostic_bucket_counts"]["family_route_missing"] == 0
        assert summary["mixed_retrieval_baseline"]["tracks"][track]["query_count"] == routed["query_count"]
        assert summary["mixed_retrieval_baseline"]["tracks"][track]["off_track_returned_count"] > 0
        assert summary["mixed_retrieval_baseline"]["tracks"][track]["retrieval_diagnostic_bucket_counts"][
            "cross_family_text_dominance"
        ] > 0

    assert topk_rows
    assert {row["query_scope"] for row in topk_rows} >= {
        "sealed_gold_no_regression_check",
        "silver_1000_diagnostic_overlay",
    }
    assert all(row["top_k"] == 5 for row in topk_rows)
    assert all("topk_hit_count" not in row for row in topk_rows)
    assert all(row["topk_returned_count"] == len(row.get("top_result_envelopes", [])) for row in topk_rows)
    assert all(isinstance(row["same_track_hit_at_k"], bool) for row in topk_rows)
    assert all(row["contract_survival_at_k_count"] <= row["topk_returned_count"] for row in topk_rows)
    assert all(row["target_contract_survival_at_k"] <= row["target_hit_at_k"] for row in topk_rows)
    assert all(
        row["off_track_returned_count"] == 0
        for row in topk_rows
        if row["source_family"] in {"PDF", "XLSX"}
    )
    assert all(row["target_mapping_audit"]["target_mapping_bucket"] for row in topk_rows)
    assert all("expected_answer" not in row for row in topk_rows)
    assert all("supporting_evidence" not in row for row in topk_rows)
    assert all(row["retrieval_score_primary_metric"] is False for row in topk_rows)
    assert all(row["answer_quality_metric_computed"] is False for row in topk_rows)
    assert all(row["promotion_evidence"] is False for row in topk_rows)

    hit_envelopes = [
        envelope
        for row in topk_rows
        for envelope in row.get("top_result_envelopes", [])
    ]
    assert hit_envelopes
    assert all(envelope["canonical_payload_source"] == "source_registry" for envelope in hit_envelopes)
    assert all(envelope["canonical_citation_payload_present_in_vector_metadata"] is False for envelope in hit_envelopes)
    assert all(envelope["vector_payload_used_as_evidence_truth"] is False for envelope in hit_envelopes)
    assert all(envelope["primary_failure_bucket"] in ["", *V3_7_2_SOURCE_REGISTRY_RETRIEVAL_SMOKE_BUCKETS] for envelope in hit_envelopes)

    assert silver_overlay["source"] == "silver_1000_diagnostic_overlay"
    assert silver_overlay["row_count"] == 1000
    assert silver_overlay["interpretation"] == "coverage_and_failure_discovery_only"
    assert "silver_precision" not in json.dumps(summary, ensure_ascii=False).lower()
    assert "silver precision" not in json.dumps(summary, ensure_ascii=False).lower()
    assert summary["sealed_gold_no_regression_check"]["tuning_allowed"] is False
    assert summary["sealed_gold_no_regression_check"]["metric_promotion_allowed"] is False


def test_v3_7_2_structured_family_routing_does_not_fall_back_to_mixed_rows() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    text_row = {
        "source_family": "TEXT",
        "query_scope": "scope",
        "query_id": "same-id",
        "top_result_envelopes": [{"source_family": "TEXT"}],
        "topk_returned_count": 1,
    }
    pdf_mixed_row = {
        "source_family": "PDF",
        "query_scope": "scope",
        "query_id": "same-id",
        "top_result_envelopes": [{"source_family": "TEXT"}],
        "topk_returned_count": 1,
        "target_mapping_audit": {"target_mapping_bucket": "target_present"},
    }
    xlsx_mixed_row = {
        "source_family": "XLSX",
        "query_scope": "scope",
        "query_id": "missing-id",
        "top_result_envelopes": [{"source_family": "TEXT"}],
        "topk_returned_count": 1,
        "target_mapping_audit": {"target_mapping_bucket": "target_present"},
    }
    pdf_routed_row = {
        "source_family": "PDF",
        "query_scope": "scope",
        "query_id": "same-id",
        "top_result_envelopes": [{"source_family": "PDF"}],
        "topk_returned_count": 1,
        "same_track_hit_at_k": True,
    }

    result = runner.v3_7_2_apply_structured_family_routing(
        mixed_topk_rows=[text_row, pdf_mixed_row, xlsx_mixed_row],
        routed_rows_by_query_key={
            runner.v3_7_2_query_routing_key(pdf_routed_row): pdf_routed_row,
        },
    )

    routed_rows = result["topk_rows"]
    assert runner.v3_7_2_query_routing_key(text_row) != runner.v3_7_2_query_routing_key(pdf_mixed_row)
    assert routed_rows[0]["top_result_envelopes"] == [{"source_family": "TEXT"}]
    assert routed_rows[1]["top_result_envelopes"] == [{"source_family": "PDF"}]
    assert routed_rows[2]["family_routed_primary_row_missing"] is True
    assert routed_rows[2]["top_result_envelopes"] == []
    assert routed_rows[2]["topk_returned_count"] == 0
    assert routed_rows[2]["primary_retrieval_diagnostic_bucket"] == "family_route_missing"
    assert result["missing_query_keys"] == [runner.v3_7_2_query_routing_key(xlsx_mixed_row)]


def assert_text_locator(row: dict[str, Any]) -> None:
    required = ("document_id", "document_version_id", "search_unit_id", "text_locator")
    assert_required(row, required)


def assert_xlsx_locator(row: dict[str, Any]) -> None:
    required = (
        "workbook",
        "sheet",
        "range",
        "cell",
        "row_label",
        "target_column",
        "document_version_id",
        "search_unit_id",
        "source_basis",
    )
    assert_required(row, required)
    assert clean(row.get("normalized_value_for_audit_only"))


def assert_pdf_locator(row: dict[str, Any]) -> None:
    required = (
        "source_pdf_path",
        "page",
        "physical_page_index",
        "bbox",
        "region_type",
        "document_version_id",
        "search_unit_id",
        "source_basis",
    )
    assert_required(row, required)
    assert isinstance(row["bbox"], list)
    assert len(row["bbox"]) == 4
    assert all(isinstance(value, (int, float)) for value in row["bbox"])
    if row["label_confidence"] == "high":
        assert clean(row.get("row_label"))
        assert clean(row.get("target_column"))


def assert_required(row: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if not has_value(row.get(field))]
    assert missing == []


def assert_source_only_manifest_row(row: dict[str, Any]) -> None:
    forbidden_fields = (
        "query",
        "question",
        "expected_answer",
        "expected_answer_text",
        "supporting_evidence",
        "relevance_label",
        "answerability_label",
        "qrel",
        "qrels",
        "gold_label",
        "human_label",
        "generated_answer",
        "answer_claims",
    )
    for field in forbidden_fields:
        assert field not in row
    assert row["generation_source"] is False
    assert row["promotion_evidence"] is False
    assert row["official_denominator_overlap"] is False
    assert row["silver_generation_allowed"] is False
    assert row["silver_jsonl_row"] is False
    assert row["questions_created"] is False
    assert row["expected_answers_created"] is False
    assert row["supporting_evidence_created"] is False
    assert row["relevance_labels_created"] is False
    assert row["answerability_labels_created"] is False
    assert row["qrels_created"] is False
    assert row["candidate_artifacts_used_as_generation_source"] is False


def assert_no_generation_payload_keys(value: Any) -> None:
    forbidden_keys = {
        "query",
        "question",
        "question_text",
        "expected_answer",
        "expected_answer_text",
        "expected_answer_final",
        "answer_text",
        "supporting_evidence",
        "supporting_evidence_final",
        "relevance_label",
        "answerability_label",
        "label_status",
        "qrel",
        "qrels",
        "qrels_candidate_id",
        "gold_label",
        "human_label",
        "generated_answer",
        "answer_claims",
    }
    if isinstance(value, dict):
        overlap = forbidden_keys & set(value)
        assert overlap == set()
        for nested in value.values():
            assert_no_generation_payload_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_generation_payload_keys(nested)


def assert_forbid_final_label_or_qrels_payload(value: Any) -> None:
    forbidden_keys = {
        "expected_answer",
        "expected_answer_text",
        "expected_answer_final",
        "supporting_evidence",
        "supporting_evidence_final",
        "relevance_label",
        "answerability_label",
        "label_status",
        "qrel",
        "qrels",
        "qrels_candidate_id",
        "gold_label",
        "human_label",
        "generated_answer",
        "answer_claims",
    }
    if isinstance(value, dict):
        overlap = forbidden_keys & set(value)
        assert overlap == set()
        for nested in value.values():
            assert_forbid_final_label_or_qrels_payload(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_forbid_final_label_or_qrels_payload(nested)


def count_by_source_family(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"TEXT": 0, "PDF": 0, "XLSX": 0}
    for row in rows:
        family = clean(row.get("source_family")).upper()
        if family in counts:
            counts[family] += 1
    counts["total"] = sum(counts.values())
    return counts


def source_locator_fingerprint(locator: Any) -> str:
    return json_hash(locator)


def json_hash(value: Any) -> str:
    import hashlib

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def pdf_manifest_row(
    *,
    source_atom_id: str,
    search_view_id: str,
    document_version_id: str,
    search_unit_id: str,
    page: int,
    bbox: list[float],
    text: str,
) -> dict[str, Any]:
    locator_fingerprint = json_hash(
        {
            "document_version_id": document_version_id,
            "search_unit_id": search_unit_id,
            "page": page,
            "bbox": bbox,
            "text": text,
        }
    )
    source_pdf_path = "D:/diagnostic/source/report.pdf"
    embedding_text = "\n".join(
        [
            f"SourceAtom: {source_atom_id}",
            "Family: PDF",
            f"Identity: PDF:{document_version_id}:{search_unit_id}:{locator_fingerprint}",
            (
                "Locator: "
                f"source_pdf_path={source_pdf_path} | page={page} | physical_page_index={page - 1} | "
                f"bbox={json.dumps(bbox, ensure_ascii=False)} | region_type=text_block"
            ),
            f"Snapshot: {text}",
        ]
    )
    return {
        "source_family": "PDF",
        "source_atom_id": source_atom_id,
        "search_view_id": search_view_id,
        "document_version_id": document_version_id,
        "parent_search_unit_id": search_unit_id,
        "source_identity": f"PDF:{document_version_id}:{search_unit_id}:{locator_fingerprint}",
        "locator_fingerprint": locator_fingerprint,
        "display_text": text,
        "bm25_text": text,
        "embedding_text": embedding_text,
        "generation_source_allowed": True,
        "runtime_evidence_allowed": True,
        "official_denominator_overlap": False,
    }


def packet_unit_response_row(
    case_id: str,
    prompt_mode: str,
    *,
    query: str,
    quality_pass: bool,
    family: str = "PDF",
    answer_ready_reused_raw_final: bool = False,
    answer_ready_reuse_reason: str = "",
) -> dict[str, Any]:
    failure_types = [] if quality_pass else ["low_evidence_overlap"]
    return {
        "case_id": case_id,
        "family": family,
        "prompt_mode": prompt_mode,
        "query": query,
        "seed_query": query,
        "query_style": "terse_question",
        "raw_response": json.dumps(
            {
                "answer": f"{query} 답변",
                "citations": [{"citation_id": "S1", "locator": "page=1; bbox=[1,2,3,4]"}],
                "abstain_reason": "",
            },
            ensure_ascii=False,
        ),
        "score": {
            "quality_pass": quality_pass,
            "parse_ok": True,
            "citation_valid": True,
            "text_supported": quality_pass,
            "value_supported": False,
            "failure_types": failure_types,
            "answer_ready_reused_raw_final": answer_ready_reused_raw_final,
        },
        "answer_ready_reused_raw_final": answer_ready_reused_raw_final,
        "answer_ready_reuse_reason": answer_ready_reuse_reason,
        "source_atom_id": "src",
        "search_view_id": "search",
        "locator_fingerprint": "fp",
        "join_key_used": "source_family+source_identity+locator_fingerprint",
        "weak_silver_candidate_id": "silver",
        "source_candidate_id": "candidate",
    }


def xlsx_manifest_row() -> dict[str, Any]:
    locator_fingerprint = json_hash(
        {
            "workbook": "book.xlsx",
            "sheet": "Sheet1",
            "cell": "B2",
            "value": "2019년 2월 5호선 승차총승객수 15,446,522명",
        }
    )
    return {
        "source_family": "XLSX",
        "source_atom_id": "src-xlsx",
        "search_view_id": "search-xlsx",
        "document_version_id": "docv-xlsx",
        "parent_search_unit_id": "su-xlsx",
        "source_identity": f"XLSX:docv-xlsx:su-xlsx:{locator_fingerprint}",
        "locator_fingerprint": locator_fingerprint,
        "display_text": "row_label=2019년 2월 5호선 | target_column=승차총승객수 | normalized_value=2019년 2월 5호선 승차총승객수 15,446,522명",
        "bm25_text": "row_label=2019년 2월 5호선 | target_column=승차총승객수 | normalized_value=2019년 2월 5호선 승차총승객수 15,446,522명",
        "embedding_text": (
            "Locator: workbook=book.xlsx | sheet=Sheet1 | range=A2:D2 | cell=B2 | "
            "row_label=2019년 2월 5호선 | target_column=승차총승객수 | normalized_value=2019년 2월 5호선 승차총승객수 15,446,522명"
        ),
        "generation_source_allowed": True,
        "runtime_evidence_allowed": True,
        "official_denominator_overlap": False,
    }


def text_manifest_row() -> dict[str, Any]:
    locator_fingerprint = json_hash(
        {
            "document_version_id": "docv-text",
            "search_unit_id": "su-text",
            "text_locator": "paragraph-3",
            "text": "실크캣 소년은 작품 설명에서 조용한 성격과 특정 장면의 행동으로 소개된다.",
        }
    )
    text = "실크캣 소년은 작품 설명에서 조용한 성격과 특정 장면의 행동으로 소개된다."
    return {
        "source_family": "TEXT",
        "source_atom_id": "src-text",
        "search_view_id": "search-text",
        "document_version_id": "docv-text",
        "parent_search_unit_id": "su-text",
        "source_identity": f"TEXT:docv-text:su-text:{locator_fingerprint}",
        "locator_fingerprint": locator_fingerprint,
        "display_text": text,
        "bm25_text": text,
        "embedding_text": "Locator: text_locator=paragraph-3 | Snapshot: " + text,
        "generation_source_allowed": True,
        "runtime_evidence_allowed": True,
        "official_denominator_overlap": False,
    }


def sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(resolve_report_artifact_path(path).read_bytes()).hexdigest()


def split_group_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {clean(row.get("leakage_group_id")) for row in rows if clean(row.get("leakage_group_id"))}


def template_locator_families(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {
        (clean(row.get("query_template_family")), clean(row.get("source_locator_family")))
        for row in rows
        if clean(row.get("query_template_family")) and clean(row.get("source_locator_family"))
    }


def official_denominator_query_ids() -> set[str]:
    config = read_json(OFFICIAL_INPUT_CONFIG)
    return {row["query_id"] for row in config["candidate_manifest"]}


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
    rows = []
    with resolve_report_artifact_path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    resolved = resolve_report_artifact_path(path)
    if not resolved.exists():
        return []
    return read_jsonl(resolved)


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
