from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))

from app.api import create_app  # noqa: E402
from app.core.config import WorkerSettings  # noqa: E402
from app.capabilities.rag_orchestrator.phase1_diagnostic_runtime import (  # noqa: E402
    DEFAULT_V4_READINESS_REPORT,
    SourceFirstRagService,
    XlsxDisplayContract,
    build_diagnostic_xlsx_source_atom,
    determine_xlsx_range_mode_from_request,
    render_xlsx_display_value,
)
from app.capabilities.rag.source_registry import assemble_evidence_bundle, validate_source_atom  # noqa: E402


ROUTE = "/internal/rag/diagnostic/query"
READINESS_ROUTE = "/internal/rag/diagnostic/readiness"
HOLDOUT_CANDIDATE_VALIDATION_ROUTE = "/internal/rag/diagnostic/holdout-candidates/validate"
FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE = "/internal/rag/diagnostic/ft-a/dry-run-input/validate"


class LlmRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, payload: dict[str, object]) -> str:
        self.calls.append(payload)
        return f"LLM:{payload['rendered_value']}"


def enabled_settings() -> WorkerSettings:
    return WorkerSettings(rag_fastapi_diagnostic_route_enabled=True)


def atom(
    atom_id: str,
    *,
    workbook: str = "Book.xlsx",
    sheet: str = "Sheet1",
    cell: str = "A1",
    cell_range: str = "A1",
    display_value: str | None = "75%",
    raw_value: str = "0.75",
    normalized_value: str = "0.75",
    value_type: str = "percentage",
    number_format: str = "0%",
    formula_cached_value: str = "",
) -> dict[str, object]:
    contract = XlsxDisplayContract(
        raw_value=raw_value,
        normalized_value=normalized_value,
        display_value=display_value,
        number_format=number_format,
        value_type=value_type,
        format_provenance="source_atom_materialized_xlsx_display_metadata_v1",
        formula_cached_value=formula_cached_value,
    )
    return build_diagnostic_xlsx_source_atom(
        atom_id,
        workbook=workbook,
        sheet=sheet,
        cell=cell,
        cell_range=cell_range,
        display_contract=contract,
    )


def v4_6_readiness_report() -> dict[str, object]:
    return {
        "run_id": "official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod",
        "status": "DIAGNOSTIC_V4_6_FT_ROUTE_POLICY_DRY_RUN_PREFLIGHT_NONPROD_READY",
        "v4_name": "v4_source_grounded_runtime_locator_and_finetune_readiness",
        "run_family": "official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod",
        "diagnostic_only": True,
        "ft_route_policy_dry_run_preflight_only": True,
        "v4_6_ft_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "blocked_reasons": [
            "v4_5_readiness_gate_failed",
            "user_owned_gold_qrels_denominator_policy_pending",
            "official_denominator_policy_closed",
            "promotion_policy_closed",
        ],
        "metrics": {
            "all_preflight_gates_passed": False,
            "v4_5_3_prior_identity_baseline_gate_passed": True,
            "ft_route_policy_dry_run_opened": False,
            "ft_route_policy_dry_run_executed": False,
            "fine_tuning_dataset_exports_created": 0,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
        },
        "preflight_gates": {
            "v4_5_3_prior_identity_baseline_gate": {
                "passed": True,
                "evidence": {
                    "prior_identity_hash_record_count": 102,
                    "source_atom_registry_jsonl_sha256": "source-registry-sha",
                    "prior_identity_hash_set_sha256": "hash-set-sha",
                },
            },
            "user_owned_gold_policy_gate": {
                "passed": False,
                "evidence": {"status": "pending_user_owned_gold_qrels_label_policy"},
            },
        },
        "source_report_inputs": {
            "v4_5": {
                "source_report_json": "ai/eval/reports/rag-ingestion/quality/v4_5/report.json",
                "source_report_sha256": "v45-sha",
                "source_report_exists": True,
            },
            "v4_5_3": {
                "source_report_json": "ai/eval/reports/rag-ingestion/quality/v4_5_3/report.json",
                "source_report_sha256": "v453-sha",
                "source_report_exists": True,
            },
        },
        "guardrails": {
            "source_atom_evidence_bundle_evidence_truth": True,
            "searchview_vector_payload_candidate_only": True,
            "vector_payload_used_as_evidence_truth": False,
            "protected_namespaces_touched": [],
        },
    }


def v4_6_6_holdout_gap_blocker_report() -> dict[str, object]:
    return {
        "run_id": "official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod",
        "status": "DIAGNOSTIC_V4_6_6_HOLDOUT_GAP_AND_DRY_RUN_BLOCKER_LEDGER_NONPROD_READY",
        "v4_name": "v4_source_grounded_runtime_locator_and_finetune_readiness",
        "run_family": "official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod",
        "schema_version": "rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_report_v1",
        "diagnostic_only": True,
        "holdout_gap_and_dry_run_blocker_ledger_only": True,
        "candidate_manifest_exported": False,
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "v4_7_official_metric_gate_opened": False,
        "blocked_reasons": [
            "v4_5_readiness_gate_failed",
            "v4_5_1_candidate_intake_gate_failed",
            "v4_5_2_source_identity_audit_gate_failed",
            "v4_6_preflight_all_gates_failed",
            "v4_6_5_execution_plan_gate_failed",
            "dry_run_input_manifest_not_exported",
            "user_owned_gold_qrels_denominator_policy_pending",
        ],
        "metrics": {
            "status": "DIAGNOSTIC_V4_6_6_HOLDOUT_GAP_AND_DRY_RUN_BLOCKER_LEDGER_NONPROD_READY",
            "diagnostic_only": True,
            "holdout_gap_and_dry_run_blocker_ledger_only": True,
            "accepted_pdf_holdout_candidates": 0,
            "accepted_xlsx_holdout_candidates": 0,
            "candidate_manifest_exported": False,
            "candidate_manifest_present": False,
            "dry_run_blocker_count": 7,
            "dry_run_execution_plan_exported": False,
            "dry_run_input_manifest_exported": False,
            "fine_tuning_dataset_exports_created": 0,
            "ft_route_policy_dry_run_opened": False,
            "ft_route_policy_dry_run_executed": False,
            "gpu_required_for_future_training_when_opened": True,
            "gpu_required_for_this_slice": False,
            "live_db_index_cache_readiness": False,
            "model_or_adapter_checkpoint_written": False,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "pdf_source_document_disjoint_needed": 20,
            "product_success_evidence_allowed": False,
            "promotion_evidence": False,
            "real_holdout_available": False,
            "real_holdout_sufficient": False,
            "training_job_created": False,
            "user_owned_policy_gate_ready": False,
            "v4_7_official_metric_gate_opened": False,
            "xlsx_workbook_disjoint_needed": 8,
        },
        "holdout_gap_ledger": {
            "schema_version": (
                "official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod"
                "_holdout_gap_ledger_v1"
            ),
            "run_id": "official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod",
            "accepted_pdf_holdout_candidates": 0,
            "accepted_xlsx_holdout_candidates": 0,
            "candidate_manifest_exported": False,
            "candidate_manifest_present": False,
            "real_holdout_available": False,
            "real_holdout_sufficient": False,
            "source_counts": {
                "PDF_source_document_disjoint": 0,
                "XLSX_workbook_disjoint": 0,
            },
            "query_fidelity_included_counts": {
                "PDF": 0,
                "XLSX": 0,
            },
            "deficits": {
                "pdf_source_document_disjoint_needed": 20,
                "xlsx_workbook_disjoint_needed": 8,
                "pdf_query_fidelity_rows_needed": 100,
                "xlsx_query_fidelity_rows_needed": 100,
            },
            "minimum_targets": {
                "pdf_unseen_source_documents": 20,
                "xlsx_unseen_workbooks": 8,
                "query_fidelity_included_rows_per_family": 100,
            },
            "acquisition_requirements": [
                "add_20_pdf_source_document_disjoint_candidates",
                "add_8_xlsx_workbook_disjoint_candidates",
                "add_100_pdf_query_fidelity_included_rows",
                "add_100_xlsx_query_fidelity_included_rows",
                "rerun_v4_5_1_candidate_intake_gate",
                "rerun_v4_5_2_source_identity_audit_gate",
                "rerun_v4_6_preflight_before_any_ft_a_dry_run",
            ],
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
        },
        "dry_run_blocker_ledger": {
            "schema_version": (
                "official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod"
                "_dry_run_blocker_ledger_v1"
            ),
            "run_id": "official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod",
            "all_non_gold_source_gates_passed": False,
            "dry_run_blocker_count": 7,
            "dry_run_execution_plan_exported": False,
            "dry_run_input_manifest_exported": False,
            "ft_route_policy_dry_run_opened": False,
            "ft_route_policy_dry_run_executed": False,
            "source_gate_state": {
                "v4_5_readiness_gate_passed": False,
                "v4_5_1_candidate_intake_gate_passed": False,
                "v4_5_2_source_identity_audit_gate_passed": False,
                "v4_5_3_prior_identity_baseline_gate_passed": True,
                "v4_6_preflight_all_gates_passed": False,
                "v4_6_5_execution_plan_gate_passed": False,
                "dry_run_input_manifest_exported": False,
            },
            "non_gold_next_actions": [
                "add_20_pdf_source_document_disjoint_candidates",
                "add_8_xlsx_workbook_disjoint_candidates",
                "add_100_pdf_query_fidelity_included_rows",
                "add_100_xlsx_query_fidelity_included_rows",
                "rerun_v4_5_1_candidate_intake_gate",
                "rerun_v4_5_2_source_identity_audit_gate",
                "rerun_v4_6_preflight_before_any_ft_a_dry_run",
            ],
            "user_owned_next_actions": [
                "approve_gold_qrels_denominator_policy_before_any_official_metric_or_promotion_gate",
            ],
            "user_owned_policy_gate_ready": False,
            "v4_7_official_metric_gate_opened": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "blocked_reasons": [
                "v4_5_readiness_gate_failed",
                "v4_5_1_candidate_intake_gate_failed",
                "v4_5_2_source_identity_audit_gate_failed",
                "v4_6_preflight_all_gates_failed",
                "v4_6_5_execution_plan_gate_failed",
                "dry_run_input_manifest_not_exported",
                "user_owned_gold_qrels_denominator_policy_pending",
            ],
        },
        "guardrails": {
            "source_atom_evidence_bundle_evidence_truth": True,
            "searchview_vector_payload_candidate_only": True,
            "vector_payload_used_as_evidence_truth": False,
            "protected_namespaces_touched": [],
            "production_routing": False,
            "db_or_production_namespace_written": False,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_db_index_cache_readiness": False,
            "raw_prompt_text_embedded": False,
            "raw_llm_response_payload_created": False,
            "prompt_payload_created": False,
            "fine_tuning_dataset_export_created": False,
            "training_job_created": False,
            "model_or_adapter_checkpoint_written": False,
            "v4_7_official_metric_gate_opened": False,
        },
        "source_report_inputs": {
            "v4_6": {
                "source_report_json": "ai/eval/reports/rag-ingestion/quality/v4_6/report.json",
                "source_report_sha256": "v46-sha",
                "source_report_exists": True,
                "source_report_boundary_flags_clean": True,
            },
            "v4_6_5": {
                "source_report_json": "ai/eval/reports/rag-ingestion/quality/v4_6_5/report.json",
                "source_report_sha256": "v465-sha",
                "source_report_exists": True,
                "source_report_boundary_flags_clean": True,
            },
        },
    }


def v4_6_10_manifest_gate_replay_report() -> dict[str, object]:
    return {
        "run_id": "official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod",
        "status": "DIAGNOSTIC_V4_6_10_EXTERNAL_HOLDOUT_CANDIDATE_MANIFEST_GATE_REPLAY_NONPROD_READY",
        "v4_name": "v4_source_grounded_runtime_locator_and_finetune_readiness",
        "run_family": "official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod",
        "schema_version": "rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_report_v1",
        "diagnostic_only": True,
        "external_holdout_candidate_manifest_gate_replay_only": True,
        "candidate_manifest_present": False,
        "candidate_manifest_exported": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "single_report_artifact_contract": True,
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "v4_7_official_metric_gate_opened": False,
        "blocked_reasons": [
            "external_holdout_candidate_manifest_missing",
            "candidate_gate_target_sufficient_false",
            "real_holdout_sufficient_false",
            "user_owned_official_denominator_policy_missing",
        ],
        "external_holdout_candidate_manifest_gate_replay": {
            "external_holdout_candidate_manifest_gate_replay_only": True,
            "candidate_manifest_input_only": True,
            "candidate_manifest_input": {
                "provided": False,
                "exists": False,
                "format": "jsonl",
                "path_label": "",
                "path_kind": "not_provided",
                "sha256": "",
                "rows_loaded": 0,
                "load_error": "",
                "raw_local_path_exposed": False,
                "input_only_replay": True,
            },
            "candidate_manifest_present": False,
            "candidate_rows_replayed": 0,
            "candidate_gate_target_sufficient": False,
            "accepted_pdf_holdout_candidates": 0,
            "accepted_xlsx_holdout_candidates": 0,
            "source_reports_closed": True,
            "codex_owned_dependency_checks_passed": True,
            "v4_5_1_intake_gate_passed": False,
            "v4_5_2_source_identity_audit_gate_passed": False,
            "v4_6_9_duplicate_hygiene_gate_passed": True,
            "source_identity_collision_count": 0,
            "source_identity_audit_excluded_count": 0,
            "candidate_intake_exclusion_reasons": {},
            "source_identity_audit_exclusion_reasons": {},
            "real_holdout_sufficient": False,
            "candidate_manifest_exported": False,
            "dry_run_input_manifest_exported": False,
            "ft_route_policy_dry_run_opened": False,
            "ft_route_policy_dry_run_executed": False,
            "v4_7_official_metric_gate_opened": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
        },
        "official_metric_opening_preflight": {
            "gate_passed": False,
            "gate_opened": False,
            "official_metric_rows_authorized": False,
            "missing_user_owned_input_count": 6,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
        },
        "metrics": {
            "external_holdout_candidate_manifest_gate_replay_only": True,
            "candidate_manifest_present": False,
            "candidate_rows_replayed": 0,
            "accepted_pdf_holdout_candidates": 0,
            "accepted_xlsx_holdout_candidates": 0,
            "candidate_manifest_exported": False,
            "real_holdout_sufficient": False,
            "ft_route_policy_dry_run_opened": False,
            "ft_route_policy_dry_run_executed": False,
            "v4_7_official_metric_gate_opened": False,
            "fine_tuning_dataset_exports_created": 0,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_db_index_cache_readiness": False,
            "codex_owned_dependency_checks_passed": True,
        },
        "guardrails": {
            "source_atom_evidence_bundle_evidence_truth": True,
            "searchview_vector_payload_candidate_only": True,
            "vector_payload_used_as_evidence_truth": False,
            "protected_namespaces_touched": [],
            "raw_candidate_rows_embedded": False,
            "raw_source_identity_values_embedded": False,
            "raw_local_path_values_exposed": False,
        },
    }


def v4_6_12_runtime_replay_route_parity_report() -> dict[str, object]:
    return {
        "run_id": "official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod",
        "status": "DIAGNOSTIC_V4_6_12_EXTERNAL_HOLDOUT_RUNTIME_REPLAY_ROUTE_PARITY_NONPROD_READY",
        "v4_name": "v4_source_grounded_runtime_locator_and_finetune_readiness",
        "run_family": "official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod",
        "schema_version": "rag_v4_6_12_external_holdout_runtime_replay_route_parity_report_v1",
        "diagnostic_only": True,
        "external_holdout_runtime_replay_route_parity_only": True,
        "runtime_parity_probe_only": True,
        "candidate_manifest_present": False,
        "candidate_manifest_exported": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "single_report_artifact_contract": True,
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "v4_7_official_metric_gate_opened": False,
        "real_holdout_sufficient": False,
        "blocked_reasons": [
            "real_external_holdout_candidates_not_user_registered",
            "user_owned_gold_qrels_denominator_policy_pending",
            "v4_7_official_metric_gate_closed",
        ],
        "external_holdout_runtime_replay_route_parity": {
            "schema_version": (
                "official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
                "_route_parity_v1"
            ),
            "run_id": "official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod",
            "feature_flag_default_enabled": False,
            "feature_flag_name": "RAG_FASTAPI_DIAGNOSTIC_ROUTE_ENABLED",
            "disabled_route_status_code": 404,
            "production_disabled_route_status_code": 404,
            "production_orchestrator_mode_enabled": False,
            "enabled_target_sufficient_status_code": 200,
            "enabled_validation_error_status_code": 422,
            "enabled_validation_error_raw_input_redacted": True,
            "probe_candidate_row_count": 200,
            "route_path": HOLDOUT_CANDIDATE_VALIDATION_ROUTE,
            "route_candidate_counts_match_v4_6_10_replay": True,
            "route_source_identity_audit_matches_v4_6_10_replay": True,
            "route_response_sanitized": True,
            "route_rejects_prompt_path_metric_and_readiness_fields": True,
            "route_candidate_intake_gate_passed": True,
            "route_source_identity_audit_gate_passed": True,
            "route_candidate_intake_snapshot": {
                "accepted_candidate_count": 200,
                "excluded_candidate_count": 0,
                "accepted_holdout_candidate_counts": {
                    "PDF_source_document_disjoint": 20,
                    "TEXT_control_only": 0,
                    "XLSX_workbook_disjoint": 8,
                },
                "real_query_fidelity_included_counts": {"PDF": 100, "TEXT": 0, "XLSX": 100},
                "deficits": {
                    "pdf_source_document_disjoint_needed": 0,
                    "xlsx_workbook_disjoint_needed": 0,
                    "pdf_query_fidelity_rows_needed": 0,
                    "xlsx_query_fidelity_rows_needed": 0,
                },
                "passed": True,
            },
            "route_source_identity_audit_snapshot": {
                "collision_count": 0,
                "executed": True,
                "invalid_prior_identity_hash_record_count": 0,
                "passed": True,
                "prior_identity_hash_record_count": 2,
            },
            "transient_external_manifest_deleted": True,
            "transient_external_manifest_persisted_in_repo": False,
            "v4_6_10_replay_candidate_manifest_present": True,
            "v4_6_10_replay_candidate_rows_replayed": 200,
            "v4_6_10_replay_candidate_gate_target_sufficient": True,
            "v4_6_10_replay_real_holdout_sufficient": False,
            "raw_runtime_request_body_embedded": False,
            "raw_runtime_response_body_embedded": False,
            "raw_candidate_rows_embedded": False,
            "raw_source_identity_values_embedded": False,
            "raw_local_path_values_exposed": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_db_index_cache_readiness": False,
        },
        "metrics": {
            "external_holdout_runtime_replay_route_parity_only": True,
            "runtime_parity_probe_only": True,
            "candidate_manifest_present": False,
            "candidate_rows_replayed_in_probe": 200,
            "candidate_manifest_exported": False,
            "dry_run_input_manifest_exported": False,
            "ft_route_policy_dry_run_opened": False,
            "ft_route_policy_dry_run_executed": False,
            "fine_tuning_dataset_exports_created": 0,
            "route_candidate_counts_match_v4_6_10_replay": True,
            "route_source_identity_audit_matches_v4_6_10_replay": True,
            "route_response_sanitized": True,
            "enabled_validation_error_raw_input_redacted": True,
            "transient_external_manifest_deleted": True,
            "real_holdout_sufficient": False,
            "v4_7_official_metric_gate_opened": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_db_index_cache_readiness": False,
        },
        "guardrails": {
            "source_atom_evidence_bundle_evidence_truth": True,
            "searchview_vector_payload_candidate_only": True,
            "vector_payload_used_as_evidence_truth": False,
            "protected_namespaces_touched": [],
            "raw_runtime_request_body_embedded": False,
            "raw_runtime_response_body_embedded": False,
            "raw_candidate_rows_embedded": False,
            "raw_source_identity_values_embedded": False,
            "raw_local_path_values_exposed": False,
        },
        "source_report_inputs": {
            "v4_6_10": {
                "source_report_json": (
                    "ai/eval/reports/rag-ingestion/quality/"
                    "official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod/"
                    "report.json"
                ),
                "source_report_sha256": "v4610-sha",
                "source_report_exists": True,
                "source_report_boundary_flags_clean": True,
            }
        },
    }


def test_diagnostic_rag_route_is_disabled_by_default_and_in_production_mode() -> None:
    default_client = TestClient(create_app(settings=WorkerSettings()))
    default_response = default_client.post(ROUTE, json={"query": "Book.xlsx Sheet1 A1 값", "source_family": "XLSX"})

    production_client = TestClient(
        create_app(
            settings=WorkerSettings(
                rag_query_orchestrator_mode="production",
                rag_fastapi_diagnostic_route_enabled=True,
            )
        )
    )
    production_response = production_client.post(
        ROUTE,
        json={"query": "Book.xlsx Sheet1 A1 값", "source_family": "XLSX"},
    )

    assert default_response.status_code == 404
    assert default_response.json()["detail"] == "diagnostic RAG route disabled"
    assert production_response.status_code == 404
    assert production_response.json()["detail"] == "diagnostic RAG route disabled"


def test_diagnostic_readiness_route_is_disabled_by_default_and_in_production_mode() -> None:
    default_client = TestClient(create_app(settings=WorkerSettings()))
    default_response = default_client.get(READINESS_ROUTE)

    production_client = TestClient(
        create_app(
            settings=WorkerSettings(
                rag_query_orchestrator_mode="production",
                rag_fastapi_diagnostic_route_enabled=True,
            )
        )
    )
    production_response = production_client.get(READINESS_ROUTE)

    assert default_response.status_code == 404
    assert default_response.json()["detail"] == "diagnostic RAG route disabled"
    assert production_response.status_code == 404
    assert production_response.json()["detail"] == "diagnostic RAG route disabled"


def test_enabled_diagnostic_readiness_route_fails_closed_when_report_missing_or_invalid(tmp_path) -> None:
    missing_service = SourceFirstRagService(readiness_report_path=tmp_path / "missing_report.json")
    missing_client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=missing_service))

    missing_body = missing_client.get(READINESS_ROUTE).json()

    assert missing_body["readiness_report_available"] is False
    assert missing_body["status"] == "V4_6_READINESS_REPORT_UNAVAILABLE"
    assert "v4_6_readiness_report_missing" in missing_body["blocked_reasons"]
    assert missing_body["official_metric_input_rows"] == 0
    assert missing_body["promotion_evidence"] is False
    assert missing_body["product_success_evidence_allowed"] is False
    assert missing_body["live_db_index_cache_readiness"] is False
    assert "__external_readiness_report_path_redacted__" in missing_body["readiness_source"]

    invalid_path = tmp_path / "invalid_report.json"
    invalid_path.write_text("{not valid json", encoding="utf-8")
    invalid_service = SourceFirstRagService(readiness_report_path=invalid_path)
    invalid_client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=invalid_service))

    invalid_body = invalid_client.get(READINESS_ROUTE).json()

    assert invalid_body["readiness_report_available"] is False
    assert invalid_body["status"] == "V4_6_READINESS_REPORT_UNAVAILABLE"
    assert invalid_body["official_metric_input_rows"] == 0
    assert invalid_body["promotion_evidence"] is False
    assert invalid_body["product_success_evidence_allowed"] is False
    assert invalid_body["live_db_index_cache_readiness"] is False


def test_enabled_diagnostic_readiness_route_rejects_promotional_or_path_leaking_report() -> None:
    corrupt_report = {
        **v4_6_readiness_report(),
        "official_metric": True,
        "official_metric_input_rows": 5,
        "promotion_evidence": True,
        "product_success_evidence_allowed": True,
        "live_db_index_cache_readiness": True,
        "ft_route_policy_dry_run_executed": True,
        "source_report_inputs": {
            "v4_5": {
                "source_report_json": "D:/private/source/report.json",
                "source_report_sha256": "bad-sha",
            }
        },
        "preflight_gates": {
            "bad_gate": {
                "passed": True,
                "evidence": {"raw_prompt": "hidden prompt"},
            }
        },
    }
    service = SourceFirstRagService(readiness_report=corrupt_report)
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    assert body["readiness_report_available"] is False
    assert body["status"] == "V4_6_READINESS_REPORT_CONTRACT_VIOLATION"
    assert "v4_6_readiness_report_contract_violation" in body["blocked_reasons"]
    assert "official_metric_not_allowed" in body["blocked_reasons"]
    assert "official_metric_input_rows_nonzero" in body["blocked_reasons"]
    assert "readiness_report_contains_forbidden_debug_or_path_surface" in body["blocked_reasons"]
    assert body["preflight_gates"] == {}
    assert body["source_report_inputs"] == {}
    assert body["official_metric_input_rows"] == 0
    assert body["official_metric"] is False
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["ft_route_policy_dry_run_executed"] is False
    assert body["training_job_created"] is False
    assert "D:/" not in response.text
    assert "raw_prompt" not in response.text
    assert "raw_llm_response" not in response.text


def test_enabled_diagnostic_readiness_route_rejects_promotional_v4_6_6_nested_ledger_flags() -> None:
    corrupt_report = v4_6_6_holdout_gap_blocker_report()
    corrupt_report["holdout_gap_ledger"]["candidate_manifest_exported"] = True
    corrupt_report["dry_run_blocker_ledger"]["ft_route_policy_dry_run_executed"] = True
    corrupt_report["dry_run_blocker_ledger"]["official_metric_input_rows"] = 1
    corrupt_report["guardrails"]["prompt_payload_created"] = True
    corrupt_report["metrics"]["fine_tuning_dataset_exports_created"] = 1
    service = SourceFirstRagService(readiness_report=corrupt_report)
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    assert body["readiness_report_available"] is False
    assert body["status"] == "V4_6_READINESS_REPORT_CONTRACT_VIOLATION"
    assert "v4_6_readiness_report_contract_violation" in body["blocked_reasons"]
    assert "candidate_manifest_exported_not_allowed" in body["blocked_reasons"]
    assert "fine_tuning_dataset_exports_created_nonzero" in body["blocked_reasons"]
    assert "ft_route_policy_dry_run_executed_not_allowed" in body["blocked_reasons"]
    assert "official_metric_input_rows_nonzero" in body["blocked_reasons"]
    assert "prompt_payload_created_not_allowed" in body["blocked_reasons"]
    assert body["holdout_gap_ledger"] == {}
    assert body["dry_run_blocker_ledger"] == {}
    assert body["official_metric_input_rows"] == 0
    assert body["official_metric"] is False
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["ft_route_policy_dry_run_executed"] is False
    assert body["dry_run_execution_plan_exported"] is False
    assert body["dry_run_input_manifest_exported"] is False
    assert body["v4_7_official_metric_gate_opened"] is False
    assert "raw_prompt" not in response.text
    assert "raw_llm_response" not in response.text
    assert "D:/" not in response.text


def test_enabled_diagnostic_readiness_route_rejects_adjacent_prompt_payload_surfaces() -> None:
    corrupt_report = v4_6_readiness_report()
    corrupt_report["preflight_gates"]["bad_prompt_gate"] = {
        "passed": True,
        "evidence": {
            "prompt_payload": "hidden prompt payload",
            "prompt_text": "hidden prompt text",
            "raw_llm_request": "hidden request",
        },
    }
    service = SourceFirstRagService(readiness_report=corrupt_report)
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    assert body["readiness_report_available"] is False
    assert body["status"] == "V4_6_READINESS_REPORT_CONTRACT_VIOLATION"
    assert "readiness_report_contains_forbidden_debug_or_path_surface" in body["blocked_reasons"]
    assert "prompt_payload" not in response.text
    assert "prompt_text" not in response.text
    assert "raw_llm_request" not in response.text


def test_enabled_diagnostic_readiness_route_exposes_v4_held_closed_gate_state_without_promotional_claims() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_readiness_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["diagnostic_only"] is True
    assert body["readiness_report_available"] is True
    assert body["run_id"].endswith("_v4_6_ft_route_policy_dry_run_preflight_nonprod")
    assert body["v4_name"] == "v4_source_grounded_runtime_locator_and_finetune_readiness"
    assert body["ft_route_policy_dry_run_preflight_only"] is True
    assert body["ft_route_policy_dry_run_opened"] is False
    assert body["ft_route_policy_dry_run_executed"] is False
    assert body["all_preflight_gates_passed"] is False
    assert body["preflight_gates"]["v4_5_3_prior_identity_baseline_gate"]["passed"] is True
    assert body["preflight_gates"]["user_owned_gold_policy_gate"]["passed"] is False
    assert "user_owned_gold_qrels_denominator_policy_pending" in body["blocked_reasons"]
    assert body["source_report_inputs"]["v4_5"]["source_report_sha256"] == "v45-sha"
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["searchview_vector_payload_candidate_only"] is True
    assert body["source_atom_evidence_bundle_evidence_truth"] is True
    assert body["vector_payload_used_as_evidence_truth"] is False
    assert "raw_prompt" not in serialized
    assert "raw_llm_response" not in serialized
    assert "D:/" not in serialized


def test_enabled_diagnostic_readiness_route_projects_v4_6_6_holdout_gap_and_blocker_ledgers() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["diagnostic_only"] is True
    assert body["readiness_report_available"] is True
    assert body["run_id"].endswith("_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod")
    assert body["status"] == "DIAGNOSTIC_V4_6_6_HOLDOUT_GAP_AND_DRY_RUN_BLOCKER_LEDGER_NONPROD_READY"
    assert body["holdout_gap_and_dry_run_blocker_ledger_only"] is True
    assert body["candidate_manifest_exported"] is False
    assert body["candidate_manifest_present"] is False
    assert body["real_holdout_available"] is False
    assert body["real_holdout_sufficient"] is False
    assert body["dry_run_execution_plan_exported"] is False
    assert body["dry_run_input_manifest_exported"] is False
    assert body["ft_route_policy_dry_run_opened"] is False
    assert body["ft_route_policy_dry_run_executed"] is False
    assert body["fine_tuning_dataset_exports_created"] == 0
    assert body["training_job_created"] is False
    assert body["model_or_adapter_checkpoint_written"] is False
    assert body["v4_7_official_metric_gate_opened"] is False
    assert body["user_owned_policy_gate_ready"] is False
    assert body["pdf_source_document_disjoint_needed"] == 20
    assert body["xlsx_workbook_disjoint_needed"] == 8
    assert body["pdf_query_fidelity_rows_needed"] == 100
    assert body["xlsx_query_fidelity_rows_needed"] == 100
    assert body["dry_run_blocker_count"] == 7
    assert "user_owned_gold_qrels_denominator_policy_pending" in body["blocked_reasons"]
    assert body["holdout_gap_ledger"]["deficits"] == {
        "pdf_source_document_disjoint_needed": 20,
        "xlsx_workbook_disjoint_needed": 8,
        "pdf_query_fidelity_rows_needed": 100,
        "xlsx_query_fidelity_rows_needed": 100,
    }
    assert body["holdout_gap_ledger"]["source_counts"] == {
        "PDF_source_document_disjoint": 0,
        "XLSX_workbook_disjoint": 0,
    }
    assert body["dry_run_blocker_ledger"]["source_gate_state"]["v4_5_3_prior_identity_baseline_gate_passed"] is True
    assert body["dry_run_blocker_ledger"]["source_gate_state"]["v4_6_preflight_all_gates_passed"] is False
    assert body["dry_run_blocker_ledger"]["user_owned_next_actions"] == [
        "approve_gold_qrels_denominator_policy_before_any_official_metric_or_promotion_gate",
    ]
    assert body["official_metric"] is False
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["source_atom_evidence_bundle_evidence_truth"] is True
    assert body["searchview_vector_payload_candidate_only"] is True
    assert body["vector_payload_used_as_evidence_truth"] is False
    assert "raw_prompt" not in serialized
    assert "raw_llm_response" not in serialized
    assert "D:/" not in serialized


def test_enabled_diagnostic_readiness_route_projects_holdout_acquisition_requirements_without_opening_gates() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    requirements = body["holdout_acquisition_requirements"]
    contract = body["holdout_candidate_manifest_contract"]
    assert requirements["schema_version"] == "v4_holdout_acquisition_requirements_v1"
    assert requirements["diagnostic_only"] is True
    assert requirements["external_holdout_acquisition_requirements_only"] is True
    assert requirements["validation_route_path"] == HOLDOUT_CANDIDATE_VALIDATION_ROUTE
    assert requirements["candidate_manifest_contract_hash"] == contract["contract_hash"]
    assert requirements["candidate_manifest_contract_version"] == contract["schema_version"]
    assert requirements["minimum_targets"] == {
        "pdf_unseen_source_documents": 20,
        "xlsx_unseen_workbooks": 8,
        "query_fidelity_included_rows_per_family": 100,
    }
    assert requirements["deficits"] == {
        "pdf_source_document_disjoint_needed": 20,
        "xlsx_workbook_disjoint_needed": 8,
        "pdf_query_fidelity_rows_needed": 100,
        "xlsx_query_fidelity_rows_needed": 100,
    }
    assert requirements["accepted_source_counts"] == {
        "PDF_source_document_disjoint": 0,
        "XLSX_workbook_disjoint": 0,
    }
    assert requirements["query_fidelity_included_counts"] == {"PDF": 0, "XLSX": 0}
    assert requirements["identity_fields_by_family"]["PDF"][0] == "document_version_id"
    assert "source_identity" not in requirements["identity_fields_by_family"]["XLSX"]
    assert "raw_locator.workbook" in requirements["identity_fields_by_family"]["XLSX"]
    assert "expected_answer" in requirements["forbidden_fields"]
    assert "target_locator" in requirements["forbidden_fields"]
    assert requirements["candidate_manifest_exported"] is False
    assert requirements["candidate_manifest_jsonl_created"] is False
    assert requirements["dry_run_input_manifest_exported"] is False
    assert requirements["ft_route_policy_dry_run_opened"] is False
    assert requirements["v4_7_official_metric_gate_opened"] is False
    assert requirements["official_metric_input_rows"] == 0
    assert requirements["promotion_evidence"] is False
    assert requirements["product_success_evidence_allowed"] is False
    assert requirements["live_db_index_cache_readiness"] is False
    assert requirements["readiness_decision"] == "blocked_pending_real_external_holdout_candidates_and_user_policy"
    assert "add_20_pdf_source_document_disjoint_candidates" in requirements["non_gold_next_actions"]
    assert "approve_gold_qrels_denominator_policy_before_any_official_metric_or_promotion_gate" in requirements[
        "user_owned_next_actions"
    ]
    assert "raw_prompt" not in serialized
    assert "raw_llm_response" not in serialized
    assert "D:/" not in serialized


def test_enabled_diagnostic_readiness_route_projects_v4_6_10_manifest_replay_without_opening_gates() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_10_manifest_gate_replay_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["diagnostic_only"] is True
    assert body["readiness_report_available"] is True
    assert body["run_id"].endswith("_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod")
    assert body["external_holdout_candidate_manifest_gate_replay_only"] is True
    assert body["candidate_manifest_input_only"] is True
    assert body["candidate_manifest_input"] == {
        "provided": False,
        "exists": False,
        "format": "jsonl",
        "path_label": "",
        "path_kind": "not_provided",
        "sha256": "",
        "rows_loaded": 0,
        "load_error": "",
        "raw_local_path_exposed": False,
        "input_only_replay": True,
    }
    assert body["candidate_manifest_present"] is False
    assert body["candidate_rows_replayed"] == 0
    assert body["candidate_gate_target_sufficient"] is False
    assert body["source_reports_closed"] is True
    assert body["codex_owned_dependency_checks_passed"] is True
    assert body["v4_5_1_intake_gate_passed"] is False
    assert body["v4_5_2_source_identity_audit_gate_passed"] is False
    assert body["v4_6_9_duplicate_hygiene_gate_passed"] is True
    assert body["official_metric_opening_preflight_gate_passed"] is False
    assert body["official_metric_opening_preflight_gate_opened"] is False
    assert body["official_metric_rows_authorized"] is False
    assert body["missing_user_owned_input_count"] == 6
    assert body["single_report_artifact_contract"] is True
    assert body["source_identity_collision_count"] == 0
    assert body["source_identity_audit_excluded_count"] == 0
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["candidate_manifest_exported"] is False
    assert body["dry_run_input_manifest_exported"] is False
    assert body["ft_route_policy_dry_run_opened"] is False
    assert body["ft_route_policy_dry_run_executed"] is False
    assert body["v4_7_official_metric_gate_opened"] is False
    assert body["real_holdout_sufficient"] is False
    assert "external_holdout_candidate_manifest_missing" in body["blocked_reasons"]
    assert "raw_prompt" not in serialized
    assert "raw_llm_response" not in serialized
    assert "D:/" not in serialized


def test_enabled_diagnostic_readiness_route_rejects_v4_6_10_sidecar_or_raw_surface_opening() -> None:
    report = v4_6_10_manifest_gate_replay_report()
    report["candidate_validation_jsonl_created"] = True
    report["guardrails"]["raw_candidate_rows_embedded"] = True
    service = SourceFirstRagService(readiness_report=report)
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    assert body["readiness_report_available"] is False
    assert "v4_6_readiness_report_contract_violation" in body["blocked_reasons"]
    assert "candidate_validation_jsonl_created_not_allowed" in body["blocked_reasons"]
    assert "raw_candidate_rows_embedded_not_allowed" in body["blocked_reasons"]
    assert body["candidate_manifest_input"] == {}
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["live_db_index_cache_readiness"] is False


def test_enabled_diagnostic_readiness_route_rejects_inconsistent_v4_6_10_manifest_replay_counters() -> None:
    report = v4_6_10_manifest_gate_replay_report()
    report["candidate_manifest_present"] = True
    report["metrics"]["candidate_manifest_present"] = True
    report["external_holdout_candidate_manifest_gate_replay"]["candidate_manifest_present"] = True
    report["external_holdout_candidate_manifest_gate_replay"]["candidate_rows_replayed"] = 0
    service = SourceFirstRagService(readiness_report=report)
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    assert body["readiness_report_available"] is False
    assert "v4_6_readiness_report_contract_violation" in body["blocked_reasons"]
    assert "v4_6_10_candidate_rows_replayed_inconsistent" in body["blocked_reasons"]
    assert body["candidate_manifest_present"] is False
    assert body["candidate_rows_replayed"] == 0
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False


def test_enabled_diagnostic_readiness_route_redacts_v4_6_10_manifest_input_metadata() -> None:
    report = v4_6_10_manifest_gate_replay_report()
    replay = report["external_holdout_candidate_manifest_gate_replay"]
    replay["candidate_manifest_present"] = True
    replay["candidate_rows_replayed"] = 2
    replay["candidate_gate_target_sufficient"] = True
    replay["candidate_manifest_input"] = {
        "provided": True,
        "exists": True,
        "format": "jsonl",
        "path_label": "ai/eval/external_candidates.jsonl",
        "path_kind": "repo_relative",
        "sha256": "manifest-sha",
        "rows_loaded": 2,
        "load_error": "",
        "raw_local_path_exposed": False,
        "input_only_replay": True,
    }
    report["candidate_manifest_present"] = True
    report["metrics"]["candidate_manifest_present"] = True
    report["metrics"]["candidate_rows_replayed"] = 2
    service = SourceFirstRagService(readiness_report=report)
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["candidate_manifest_present"] is True
    assert body["candidate_rows_replayed"] == 2
    assert body["candidate_gate_target_sufficient"] is True
    assert body["real_holdout_sufficient"] is False
    assert body["candidate_manifest_input"]["provided"] is True
    assert body["candidate_manifest_input"]["exists"] is True
    assert body["candidate_manifest_input"]["path_label"] == "__external_candidate_manifest_path_redacted__"
    assert body["candidate_manifest_input"]["path_kind"] == "external_redacted"
    assert body["candidate_manifest_input"]["sha256"] == "manifest-sha"
    assert body["candidate_manifest_input"]["rows_loaded"] == 2
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["v4_7_official_metric_gate_opened"] is False
    assert "ai/eval/external_candidates.jsonl" not in serialized
    assert "raw_prompt" not in serialized
    assert "raw_llm_response" not in serialized
    assert "D:/" not in serialized


def test_enabled_diagnostic_readiness_route_projects_v4_6_12_runtime_replay_route_parity_without_opening_gates() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_12_runtime_replay_route_parity_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["diagnostic_only"] is True
    assert body["readiness_report_available"] is True
    assert body["run_id"].endswith("_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod")
    assert body["external_holdout_runtime_replay_route_parity_only"] is True
    assert body["runtime_parity_probe_only"] is True
    assert body["route_path"] == HOLDOUT_CANDIDATE_VALIDATION_ROUTE
    assert body["route_candidate_counts_match_v4_6_10_replay"] is True
    assert body["route_source_identity_audit_matches_v4_6_10_replay"] is True
    assert body["route_response_sanitized"] is True
    assert body["enabled_validation_error_raw_input_redacted"] is True
    assert body["transient_external_manifest_deleted"] is True
    assert body["transient_external_manifest_persisted_in_repo"] is False
    assert body["candidate_rows_replayed_in_probe"] == 200
    assert body["external_holdout_runtime_replay_route_parity"]["route_candidate_intake_snapshot"] == {
        "accepted_candidate_count": 200,
        "excluded_candidate_count": 0,
        "accepted_holdout_candidate_counts": {
            "PDF_source_document_disjoint": 20,
            "TEXT_control_only": 0,
            "XLSX_workbook_disjoint": 8,
        },
        "real_query_fidelity_included_counts": {"PDF": 100, "TEXT": 0, "XLSX": 100},
        "deficits": {
            "pdf_source_document_disjoint_needed": 0,
            "xlsx_workbook_disjoint_needed": 0,
            "pdf_query_fidelity_rows_needed": 0,
            "xlsx_query_fidelity_rows_needed": 0,
        },
        "passed": True,
    }
    assert body["candidate_manifest_present"] is False
    assert body["candidate_manifest_exported"] is False
    assert body["candidate_manifest_jsonl_created"] is False
    assert body["candidate_validation_jsonl_created"] is False
    assert body["source_identity_audit_jsonl_created"] is False
    assert body["dry_run_input_manifest_exported"] is False
    assert body["ft_route_policy_dry_run_opened"] is False
    assert body["ft_route_policy_dry_run_executed"] is False
    assert body["v4_7_official_metric_gate_opened"] is False
    assert body["real_holdout_sufficient"] is False
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["protected_namespaces_touched"] == []
    assert "real_external_holdout_candidates_not_user_registered" in body["blocked_reasons"]
    assert "candidate_manifest_path" not in serialized
    assert "hidden holdout prompt" not in serialized
    assert "D:/private" not in serialized
    assert "raw_prompt" not in serialized
    assert "raw_llm_response" not in serialized


def test_enabled_diagnostic_readiness_route_rejects_corrupt_v4_6_12_runtime_replay_route_parity() -> None:
    report = v4_6_12_runtime_replay_route_parity_report()
    report["candidate_manifest_jsonl_created"] = True
    report["external_holdout_runtime_replay_route_parity"]["route_response_sanitized"] = False
    report["external_holdout_runtime_replay_route_parity"]["raw_runtime_request_body_embedded"] = True
    report["external_holdout_runtime_replay_route_parity"]["debug_path"] = "D:/private/holdout.jsonl"
    report["external_holdout_runtime_replay_route_parity"]["raw_prompt"] = "hidden holdout prompt"
    report["metrics"]["route_response_sanitized"] = False
    report["official_metric_input_rows"] = 3
    service = SourceFirstRagService(readiness_report=report)
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["readiness_report_available"] is False
    assert body["status"] == "V4_6_READINESS_REPORT_CONTRACT_VIOLATION"
    assert "v4_6_readiness_report_contract_violation" in body["blocked_reasons"]
    assert "candidate_manifest_jsonl_created_not_allowed" in body["blocked_reasons"]
    assert "official_metric_input_rows_nonzero" in body["blocked_reasons"]
    assert "v4_6_12_route_response_not_sanitized" in body["blocked_reasons"]
    assert "raw_runtime_request_body_embedded_not_allowed" in body["blocked_reasons"]
    assert "readiness_report_contains_forbidden_debug_or_path_surface" in body["blocked_reasons"]
    assert body["external_holdout_runtime_replay_route_parity"] == {}
    assert body["route_response_sanitized"] is False
    assert body["candidate_manifest_jsonl_created"] is False
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert "D:/private" not in serialized
    assert "hidden holdout prompt" not in serialized
    assert "raw_prompt" not in serialized
    assert "raw_llm_response" not in serialized


def test_diagnostic_readiness_default_report_tracks_latest_v4_6_12_route_parity_gate() -> None:
    assert DEFAULT_V4_READINESS_REPORT.parts[-2].endswith(
        "_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
    )


def test_enabled_diagnostic_readiness_route_exposes_holdout_candidate_manifest_contract_without_opening_intake() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_readiness_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.get(READINESS_ROUTE)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    contract = body["holdout_candidate_manifest_contract"]
    assert contract["diagnostic_only"] is True
    assert contract["input_only"] is True
    assert contract["input_format"] == "jsonl"
    assert contract["schema_version"] == "v4_holdout_candidate_manifest_contract_v1"
    assert contract["contract_hash"]
    assert contract["contract_hash_algorithm"] == "sha256(canonical_json_without_contract_hash)"
    assert contract["candidate_manifest_jsonl_created"] is False
    assert contract["candidate_validation_jsonl_created"] is False
    assert contract["source_identity_audit_jsonl_created"] is False
    assert contract["fine_tuning_dataset_export_created"] is False
    assert contract["training_job_created"] is False
    assert contract["model_or_adapter_checkpoint_written"] is False
    assert contract["official_metric_input_rows"] == 0
    assert contract["promotion_evidence"] is False
    assert contract["product_success_evidence_allowed"] is False
    assert contract["live_db_index_cache_readiness"] is False
    assert contract["minimum_targets"] == {
        "pdf_unseen_source_documents": 20,
        "xlsx_unseen_workbooks": 8,
        "query_fidelity_included_rows_per_family": 100,
    }
    assert contract["accepted_source_families"] == ["PDF", "XLSX", "TEXT"]
    assert contract["identity_aliases_by_family"]["PDF"][0] == "document_version_id"
    assert "document_version_id" in contract["identity_aliases_by_family"]["PDF"]
    assert "raw_locator.document_version_id" in contract["identity_aliases_by_family"]["PDF"]
    assert "workbook_version_id" in contract["identity_aliases_by_family"]["XLSX"]
    assert "raw_locator.workbook" in contract["identity_aliases_by_family"]["XLSX"]
    assert "source_identity" not in contract["identity_aliases_by_family"]["XLSX"]
    assert contract["identity_priority_by_family"]["PDF"][0] == {
        "tier": "document_version",
        "fields": ["document_version_id", "raw_locator.document_version_id"],
    }
    assert contract["identity_conflict_policy"]["same_tier_distinct_identity_values_fail_closed"] is True
    assert contract["identity_conflict_policy"]["exclusion_reason"] == "source_identity_field_conflict"
    assert contract["source_identity_accepted_as_xlsx_workbook_proof"] is False
    assert contract["source_identity_collision_audit_required"] is True
    assert contract["prior_identity_hash_set_required"] is True
    assert "expected_answer" in contract["forbidden_fields"]
    assert "supporting_evidence" in contract["forbidden_fields"]
    assert "target_locator" in contract["forbidden_fields"]
    assert "gold_locator" in contract["forbidden_fields"]
    assert "raw_prompt" not in serialized
    assert "raw_llm_response" not in serialized
    assert "D:/" not in serialized


def test_diagnostic_holdout_candidate_validation_route_is_disabled_by_default_and_in_production_mode() -> None:
    payload = {"schema_version": "v4_holdout_candidate_manifest_contract_v1", "candidate_rows": []}
    default_client = TestClient(create_app(settings=WorkerSettings()))
    default_response = default_client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    production_client = TestClient(
        create_app(
            settings=WorkerSettings(
                rag_query_orchestrator_mode="production",
                rag_fastapi_diagnostic_route_enabled=True,
            )
        )
    )
    production_response = production_client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    assert default_response.status_code == 404
    assert default_response.json()["detail"] == "diagnostic RAG route disabled"
    assert production_response.status_code == 404
    assert production_response.json()["detail"] == "diagnostic RAG route disabled"


def test_diagnostic_ft_a_dry_run_input_validation_route_is_disabled_by_default_and_in_production_mode() -> None:
    payload = {
        "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
        "manifest_rows": [],
        "dry_run_input_manifest_path": "D:/private/manifest.jsonl",
        "raw_prompt": "hidden prompt",
    }
    default_client = TestClient(create_app(settings=WorkerSettings()))
    default_response = default_client.post(FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE, json=payload)

    production_client = TestClient(
        create_app(
            settings=WorkerSettings(
                rag_query_orchestrator_mode="production",
                rag_fastapi_diagnostic_route_enabled=True,
            )
        )
    )
    production_response = production_client.post(FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE, json=payload)

    assert default_response.status_code == 404
    assert default_response.json()["detail"] == "diagnostic RAG route disabled"
    assert "D:/private" not in default_response.text
    assert "hidden prompt" not in default_response.text
    assert production_response.status_code == 404
    assert production_response.json()["detail"] == "diagnostic RAG route disabled"
    assert "D:/private" not in production_response.text
    assert "hidden prompt" not in production_response.text


def test_enabled_diagnostic_holdout_candidate_validation_handles_empty_candidate_rows_closed() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.post(
        HOLDOUT_CANDIDATE_VALIDATION_ROUTE,
        json={
            "schema_version": "v4_holdout_candidate_manifest_contract_v1",
            "candidate_rows": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["diagnostic_only"] is True
    assert body["candidate_manifest_present"] is False
    assert body["candidate_manifest_rows"] == 0
    assert body["accepted_candidate_count"] == 0
    assert body["excluded_candidate_count"] == 0
    assert body["candidate_intake_gate"]["accepted_candidate_count"] == 0
    assert body["candidate_intake_gate"]["excluded_candidate_count"] == 0
    assert body["candidate_intake_gate"]["passed"] is False
    assert "candidate_manifest_missing" in body["candidate_intake_gate"]["blocked_reasons"]
    assert body["candidate_intake_gate"]["deficits"] == {
        "pdf_source_document_disjoint_needed": 20,
        "xlsx_workbook_disjoint_needed": 8,
        "pdf_query_fidelity_rows_needed": 100,
        "xlsx_query_fidelity_rows_needed": 100,
    }
    assert body["candidate_manifest_jsonl_created"] is False
    assert body["candidate_validation_jsonl_created"] is False
    assert body["source_identity_audit_jsonl_created"] is False
    assert body["fine_tuning_dataset_export_created"] is False
    assert body["training_job_created"] is False
    assert body["model_or_adapter_checkpoint_written"] is False
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["protected_namespaces_touched"] == []


def test_enabled_diagnostic_holdout_candidate_validation_rejects_candidate_rows_over_500_without_input_echo() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    rows = [
        {
            "candidate_id": f"pdf-over-limit-{index}",
            "query_id": f"pdf-over-limit-query-{index}",
            "source_family": "PDF",
            "source_document_id": f"pdf-over-limit-doc-{index}",
            "local_path": "D:/private/holdout.pdf",
            "raw_prompt": "hidden holdout prompt",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
        }
        for index in range(501)
    ]

    response = client.post(
        HOLDOUT_CANDIDATE_VALIDATION_ROUTE,
        json={
            "schema_version": "v4_holdout_candidate_manifest_contract_v1",
            "candidate_rows": rows,
        },
    )

    assert response.status_code == 422
    assert "D:/private" not in response.text
    assert "hidden holdout prompt" not in response.text
    assert "pdf-over-limit-" not in response.text
    assert "pdf-over-limit-query-" not in response.text
    assert "pdf-over-limit-doc-" not in response.text
    assert all("input" not in detail for detail in response.json()["detail"])


def test_enabled_diagnostic_ft_a_dry_run_input_validation_accepts_manifest_rows_without_writes() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payload = {
        "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
        "request_id": "ft-a-dry-run-input-smoke",
        "manifest_rows": [
            {
                "row_id": "row-ok",
                "query_id": "query-ok",
                "source_family": "XLSX",
                "route_lane": "deictic",
                "response_policy_bucket": "CONTEXT_REQUIRED",
                "prompt_policy_id": "prompt_only_policy_bucket_classifier_schema_v1",
                "raw_query_text": "이전 셀의 값을 설명해줘",
                "active_context_available": False,
                "candidate_search_view_count": 0,
            },
            {
                "row_id": "row-unsupported-policy",
                "query_id": "query-unsupported-policy",
                "source_family": "PDF",
                "route_lane": "rough_query",
                "response_policy_bucket": "ANSWER_ALLOWED",
                "prompt_policy_id": "production_prompt_policy",
            },
        ],
    }

    response = client.post(FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["diagnostic_only"] is True
    assert body["ft_a_dry_run_input_manifest_validator_only"] is True
    assert body["request_id"] == "ft-a-dry-run-input-smoke"
    assert body["manifest_row_count"] == 2
    assert body["accepted_manifest_row_count"] == 1
    assert body["excluded_manifest_row_count"] == 1
    assert body["dry_run_input_manifest_validation"]["accepted_manifest_row_count"] == 1
    assert body["dry_run_input_manifest_validation"]["excluded_manifest_rows"][0]["exclusion_reason"] == "unsupported_prompt_policy_id"
    accepted = body["dry_run_input_manifest_validation"]["accepted_manifest_rows"][0]
    assert accepted["row_id_hash"]
    assert accepted["query_id_hash"]
    assert accepted["model_input_field_names"] == [
        "active_context_available",
        "candidate_search_view_count",
        "raw_query_text",
        "route_lane",
        "source_family",
    ]
    assert body["dry_run_input_manifest_gate_passed"] is False
    assert body["manifest_rows_exported"] is False
    assert body["prompt_payload_created"] is False
    assert body["prompt_manifest_created"] is False
    assert body["raw_prompt_text_embedded"] is False
    assert body["raw_llm_response_payload_created"] is False
    assert body["fine_tuning_dataset_export_created"] is False
    assert body["fine_tuning_dataset_exports_created"] == 0
    assert body["training_job_created"] is False
    assert body["model_or_adapter_checkpoint_written"] is False
    assert body["official_metric"] is False
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["protected_namespaces_touched"] == []
    assert "이전 셀의 값을 설명해줘" not in response.text
    assert "row-ok" not in response.text
    assert "query-ok" not in response.text


def test_enabled_diagnostic_ft_a_dry_run_input_validation_rejects_prompt_gold_path_and_extra_fields() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payload = {
        "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
        "manifest_rows": [
            {
                "row_id": "row-leaky",
                "query_id": "query-leaky",
                "source_family": "PDF",
                "route_lane": "rough_query",
                "response_policy_bucket": "ANSWER_ALLOWED",
                "prompt_policy_id": "prompt_only_policy_bucket_classifier_schema_v1",
                "expected_answer": "secret answer",
                "supporting_evidence": "secret support",
                "raw_prompt": "hidden prompt",
                "raw_llm_response": "hidden response",
                "local_file_path": "D:/private/source.pdf",
                "official_metric_input_rows": 1,
                "promotion_evidence": True,
            }
        ],
    }

    response = client.post(FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE, json=payload)
    extra_response = client.post(
        FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE,
        json={**payload, "dry_run_input_manifest_path": "D:/private/manifest.jsonl"},
    )

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["accepted_manifest_row_count"] == 0
    assert body["excluded_manifest_row_count"] == 1
    excluded = body["dry_run_input_manifest_validation"]["excluded_manifest_rows"][0]
    assert excluded["exclusion_reason"] == "forbidden_prompt_gold_or_output_field_present"
    assert "expected_answer" in excluded["forbidden_manifest_fields"]
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["manifest_rows_exported"] is False
    assert "secret answer" not in serialized
    assert "secret support" not in serialized
    assert "hidden prompt" not in serialized
    assert "hidden response" not in serialized
    assert "D:/private" not in serialized
    assert extra_response.status_code == 422
    assert "D:/private" not in extra_response.text


def test_enabled_diagnostic_ft_a_dry_run_input_validation_rejects_operational_metric_identity_fields() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payload = {
        "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
        "manifest_rows": [
            {
                "row_id": "row-operational-only",
                "query_id": "query-operational-only",
                "source_family": "PDF",
                "route_lane": "rough_query",
                "response_policy_bucket": "ANSWER_ALLOWED",
                "prompt_policy_id": "prompt_only_policy_bucket_classifier_schema_v1",
                "source_identity": "pdf-source-identity",
                "official_metric_input_rows": 1,
                "training_job_created": True,
                "model_or_adapter_checkpoint_written": True,
                "dry_run_input_manifest_exported": True,
            }
        ],
    }

    response = client.post(FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["accepted_manifest_row_count"] == 0
    assert body["excluded_manifest_row_count"] == 1
    excluded = body["dry_run_input_manifest_validation"]["excluded_manifest_rows"][0]
    assert excluded["exclusion_reason"] == "forbidden_prompt_gold_or_output_field_present"
    assert {
        "source_identity",
        "official_metric_input_rows",
        "training_job_created",
        "model_or_adapter_checkpoint_written",
        "dry_run_input_manifest_exported",
    }.issubset(set(excluded["forbidden_manifest_fields"]))
    assert body["manifest_rows_exported"] is False
    assert body["fine_tuning_dataset_export_created"] is False
    assert body["training_job_created"] is False
    assert body["model_or_adapter_checkpoint_written"] is False
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert "row-operational-only" not in serialized
    assert "query-operational-only" not in serialized
    assert "pdf-source-identity" not in serialized


def test_enabled_diagnostic_ft_a_dry_run_input_validation_rejects_manifest_row_count_over_500_without_leakage() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    base_row = {
        "row_id": "row-ok",
        "query_id": "query-ok",
        "source_family": "XLSX",
        "route_lane": "deictic",
        "response_policy_bucket": "CONTEXT_REQUIRED",
        "prompt_policy_id": "prompt_only_policy_bucket_classifier_schema_v1",
        "raw_query_text": "이전 셀의 값을 설명해줘",
    }
    allowed_rows = [{**base_row, "row_id": f"row-ok-{index}", "query_id": f"query-ok-{index}"} for index in range(500)]
    too_many_rows = [
        {
            **base_row,
            "row_id": f"row-too-many-{index}",
            "query_id": f"query-too-many-{index}",
            "local_file_path": "D:/private/source.pdf",
        }
        for index in range(501)
    ]

    allowed_response = client.post(
        FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE,
        json={
            "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
            "manifest_rows": allowed_rows,
        },
    )
    rejected_response = client.post(
        FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE,
        json={
            "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
            "manifest_rows": too_many_rows,
        },
    )

    assert allowed_response.status_code == 200
    assert allowed_response.json()["accepted_manifest_row_count"] == 500
    assert "이전 셀의 값을 설명해줘" not in allowed_response.text
    assert "row-ok-1" not in allowed_response.text
    assert "query-ok-1" not in allowed_response.text
    assert rejected_response.status_code == 422
    assert "D:/private" not in rejected_response.text
    assert "row-too-many-500" not in rejected_response.text
    assert "query-too-many-500" not in rejected_response.text
    assert "input" not in rejected_response.text


def test_enabled_diagnostic_ft_a_dry_run_input_validation_handles_empty_manifest_rows_closed() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.post(
        FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE,
        json={
            "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
            "manifest_rows": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["diagnostic_only"] is True
    assert body["manifest_row_count"] == 0
    assert body["accepted_manifest_row_count"] == 0
    assert body["excluded_manifest_row_count"] == 0
    assert body["dry_run_input_manifest_gate_passed"] is False
    assert body["manifest_rows_exported"] is False
    assert body["prompt_payload_created"] is False
    assert body["raw_llm_response_payload_created"] is False
    assert body["training_job_created"] is False
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False


def test_enabled_diagnostic_ft_a_dry_run_input_validation_rejects_bad_schema_and_non_object_rows_without_input_echo() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payloads = [
        {
            "schema_version": "wrong_schema",
            "manifest_rows": [],
            "raw_prompt": "hidden prompt",
            "local_file_path": "D:/private/manifest.jsonl",
        },
        {
            "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
            "manifest_rows": None,
            "raw_prompt": "hidden prompt",
        },
        {
            "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
            "manifest_rows": ["row-ok", {"query_id": "query-ok"}],
            "dry_run_input_manifest_path": "D:/private/manifest.jsonl",
        },
    ]

    for payload in payloads:
        response = client.post(FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE, json=payload)
        assert response.status_code == 422
        assert "hidden prompt" not in response.text
        assert "D:/private" not in response.text
        assert "row-ok" not in response.text
        assert "query-ok" not in response.text
        assert all("input" not in detail for detail in response.json()["detail"])


def test_enabled_diagnostic_ft_a_dry_run_input_validation_reports_all_row_rejection_reasons_without_raw_ids() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    rows = [
        {
            "row_id": "row-missing",
            "source_family": "XLSX",
            "route_lane": "deictic",
            "response_policy_bucket": "CONTEXT_REQUIRED",
            "prompt_policy_id": "prompt_only_policy_bucket_classifier_schema_v1",
        },
        {
            "row_id": "row-family",
            "query_id": "query-family",
            "source_family": "DOCX",
            "route_lane": "rough_query",
            "response_policy_bucket": "ANSWER_ALLOWED",
            "prompt_policy_id": "prompt_only_policy_bucket_classifier_schema_v1",
        },
        {
            "row_id": "row-route",
            "query_id": "query-route",
            "source_family": "PDF",
            "route_lane": "production_chat",
            "response_policy_bucket": "ANSWER_ALLOWED",
            "prompt_policy_id": "prompt_only_policy_bucket_classifier_schema_v1",
        },
        {
            "row_id": "row-bucket",
            "query_id": "query-bucket",
            "source_family": "TEXT",
            "route_lane": "rough_query",
            "response_policy_bucket": "ANSWERABLE",
            "prompt_policy_id": "prompt_only_policy_bucket_classifier_schema_v1",
        },
        {
            "row_id": "row-policy",
            "query_id": "query-policy",
            "source_family": "PDF",
            "route_lane": "rough_query",
            "response_policy_bucket": "ANSWER_ALLOWED",
            "prompt_policy_id": "production_prompt_policy",
        },
    ]

    response = client.post(
        FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE,
        json={
            "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
            "manifest_rows": rows,
        },
    )

    assert response.status_code == 200
    body = response.json()
    excluded_rows = body["dry_run_input_manifest_validation"]["excluded_manifest_rows"]
    reasons = {row["exclusion_reason"] for row in excluded_rows}
    assert body["accepted_manifest_row_count"] == 0
    assert body["excluded_manifest_row_count"] == 5
    assert reasons == {
        "missing_required_manifest_field",
        "unsupported_source_family",
        "unsupported_route_lane",
        "unsupported_response_policy_bucket",
        "unsupported_prompt_policy_id",
    }
    assert all("row_id_hash" in row for row in excluded_rows)
    assert "row-missing" not in response.text
    assert "row-family" not in response.text
    assert "query-policy" not in response.text


def test_enabled_diagnostic_holdout_candidate_validation_accepts_family_rows_without_writes_or_identity_leakage() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "request_id": "holdout-validation-smoke",
        "candidate_rows": [
            {
                "candidate_id": "pdf-c1",
                "query_id": "pdf-q1",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-001",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "XLSX:workbook-001:Sheet1:A1",
                "query_id": "query-for-workbook-001",
                "source_family": "XLSX",
                "workbook_id": "workbook-001",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "text-c1",
                "query_id": "text-q1",
                "source_family": "TEXT",
                "source_identity": "text-control-001",
                "active_context_bucket": "control",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
        ],
    }

    response = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["diagnostic_only"] is True
    assert body["holdout_candidate_manifest_validation_only"] is True
    assert body["candidate_manifest_present"] is True
    assert body["candidate_manifest_rows"] == 3
    assert body["accepted_candidate_count"] == 3
    assert body["excluded_candidate_count"] == 0
    assert body["candidate_intake_gate"]["accepted_holdout_candidate_counts"] == {
        "PDF_source_document_disjoint": 1,
        "XLSX_workbook_disjoint": 1,
        "TEXT_control_only": 1,
    }
    assert body["candidate_intake_gate"]["real_query_fidelity_included_counts"] == {
        "PDF": 1,
        "XLSX": 1,
        "TEXT": 1,
    }
    assert body["candidate_intake_gate"]["passed"] is False
    assert "real_disjoint_holdout_candidates_below_target" in body["candidate_intake_gate"]["blocked_reasons"]
    assert "real_query_fidelity_candidates_below_target" in body["candidate_intake_gate"]["blocked_reasons"]
    assert body["candidate_manifest_jsonl_created"] is False
    assert body["candidate_validation_jsonl_created"] is False
    assert body["source_identity_audit_jsonl_created"] is False
    assert body["fine_tuning_dataset_export_created"] is False
    assert body["training_job_created"] is False
    assert body["model_or_adapter_checkpoint_written"] is False
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["accepted_candidates"][0]["source_identity_hash"]
    assert body["accepted_candidates"][0]["source_identity_scope"] == "PDF_source_document"
    assert body["accepted_candidates"][1]["candidate_id_hash"]
    assert body["accepted_candidates"][1]["query_id_hash"]
    assert "candidate_id" not in body["accepted_candidates"][1]
    assert "query_id" not in body["accepted_candidates"][1]
    assert "pdf-doc-001" not in serialized
    assert "workbook-001" not in serialized
    assert "text-control-001" not in serialized
    assert "source_identity_key" not in serialized


def test_enabled_diagnostic_holdout_candidate_validation_marks_target_sufficient_manifest_without_writes() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    pdf_rows = [
        {
            "candidate_id": f"pdf-c{i}",
            "query_id": f"pdf-q{i}",
            "source_family": "PDF",
            "source_document_id": f"pdf-doc-{i % 20:02d}",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
        }
        for i in range(100)
    ]
    xlsx_rows = [
        {
            "candidate_id": f"xlsx-c{i}",
            "query_id": f"xlsx-q{i}",
            "source_family": "XLSX",
            "workbook_id": f"workbook-{i % 8:02d}",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
        }
        for i in range(100)
    ]
    payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "prior_identity_hash_records": [
            {"source_identity_hash": hashlib.sha256(b"not-a-collision").hexdigest()}
        ],
        "candidate_rows": [*pdf_rows, *xlsx_rows],
    }

    response = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_intake_gate"]["passed"] is True
    assert body["source_identity_audit_gate"]["executed"] is True
    assert body["source_identity_audit_gate"]["passed"] is True
    assert body["accepted_candidate_count"] == 200
    assert body["excluded_candidate_count"] == 0
    assert body["candidate_intake_gate"]["deficits"] == {
        "pdf_source_document_disjoint_needed": 0,
        "xlsx_workbook_disjoint_needed": 0,
        "pdf_query_fidelity_rows_needed": 0,
        "xlsx_query_fidelity_rows_needed": 0,
    }
    assert body["candidate_manifest_jsonl_created"] is False
    assert body["candidate_validation_jsonl_created"] is False
    assert body["source_identity_audit_jsonl_created"] is False
    assert body["fine_tuning_dataset_export_created"] is False
    assert body["training_job_created"] is False
    assert body["official_metric_input_rows"] == 0
    assert "candidate_id" not in body["accepted_candidates"][0]
    assert "query_id" not in body["accepted_candidates"][0]
    assert "pdf-doc-" not in response.text
    assert "workbook-" not in response.text


def test_enabled_diagnostic_holdout_candidate_validation_rejects_invalid_prior_hash_baseline() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    pdf_rows = [
        {
            "candidate_id": f"pdf-c{i}",
            "query_id": f"pdf-q{i}",
            "source_family": "PDF",
            "source_document_id": f"pdf-doc-{i % 20:02d}",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
        }
        for i in range(100)
    ]
    xlsx_rows = [
        {
            "candidate_id": f"xlsx-c{i}",
            "query_id": f"xlsx-q{i}",
            "source_family": "XLSX",
            "workbook_id": f"workbook-{i % 8:02d}",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
        }
        for i in range(100)
    ]
    payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "prior_identity_hash_records": [
            {"source_identity_hash": "not-a-collision"},
            {
                "source_identity_hash": hashlib.sha256(b"wrong-algorithm").hexdigest(),
                "source_identity_hash_algorithm": "sha256(scope|identity)",
            },
        ],
        "candidate_rows": [*pdf_rows, *xlsx_rows],
    }

    response = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_intake_gate"]["passed"] is True
    assert body["source_identity_audit_gate"]["executed"] is True
    assert body["source_identity_audit_gate"]["passed"] is False
    assert body["source_identity_audit_gate"]["prior_identity_hash_record_count"] == 0
    assert body["source_identity_audit_gate"]["invalid_prior_identity_hash_record_count"] == 2
    assert "invalid_prior_identity_hash_records" in body["source_identity_audit_gate"]["blocked_reasons"]
    assert "prior_identity_hash_baseline_missing" in body["source_identity_audit_gate"]["blocked_reasons"]
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False


def test_enabled_diagnostic_holdout_candidate_validation_accepts_text_control_only_alias_without_writes() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "candidate_rows": [
            {
                "candidate_id": "text-control-candidate",
                "query_id": "text-control-query",
                "source_family": "TEXT",
                "source_identity": "text-control-source",
                "control_only": True,
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            }
        ],
    }

    response = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_candidate_count"] == 1
    assert body["excluded_candidate_count"] == 0
    assert body["candidate_intake_gate"]["accepted_holdout_candidate_counts"]["TEXT_control_only"] == 1
    assert body["accepted_candidates"][0]["source_identity_scope"] == "TEXT_control"
    assert body["candidate_manifest_jsonl_created"] is False
    assert body["official_metric_input_rows"] == 0
    assert "text-control-source" not in response.text


def test_enabled_diagnostic_holdout_candidate_validation_rejects_duplicates_false_flags_and_text_non_control() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "candidate_rows": [
            {
                "candidate_id": "dupe",
                "query_id": "dupe-query",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-good",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "dupe",
                "query_id": "dupe-query",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-other",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "not-disjoint",
                "query_id": "not-disjoint-query",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-not-disjoint",
                "disjoint_from_prior": False,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "synthetic",
                "query_id": "synthetic-query",
                "source_family": "XLSX",
                "workbook_id": "synthetic-workbook",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": False,
            },
            {
                "candidate_id": "no-fidelity",
                "query_id": "no-fidelity-query",
                "source_family": "XLSX",
                "workbook_id": "no-fidelity-workbook",
                "disjoint_from_prior": True,
                "query_fidelity_included": False,
                "real_unseen": True,
            },
            {
                "candidate_id": "text-case",
                "query_id": "text-query",
                "source_family": "TEXT",
                "source_identity": "text-not-control",
                "active_context_bucket": "seen_reference",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "bad-family",
                "query_id": "bad-family-query",
                "source_family": "IMAGE",
                "source_identity": "image-identity",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
        ],
    }

    response = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_candidate_count"] == 1
    assert body["excluded_candidate_count"] == 6
    reasons = {reason for row in body["excluded_candidates"] for reason in row["exclusion_reasons"]}
    assert {
        "duplicate_candidate_id",
        "duplicate_query_id",
        "not_disjoint_from_prior",
        "synthetic_or_not_real_unseen",
        "query_fidelity_not_included",
        "text_family_control_only",
        "unsupported_source_family",
    }.issubset(reasons)
    assert body["candidate_intake_gate"]["passed"] is False
    assert "candidate_rows_excluded" in body["candidate_intake_gate"]["blocked_reasons"]
    assert "pdf-doc-" not in response.text
    assert "synthetic-workbook" not in response.text
    assert "no-fidelity-workbook" not in response.text
    assert "text-not-control" not in response.text


def test_enabled_diagnostic_holdout_candidate_validation_rejects_duplicates_even_when_first_row_is_invalid() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "candidate_rows": [
            {
                "candidate_id": "shadowed",
                "query_id": "shadow-query",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-invalid-first",
                "disjoint_from_prior": False,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "shadowed",
                "query_id": "shadow-query",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-valid-looking-duplicate",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
        ],
    }

    response = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_candidate_count"] == 0
    assert body["excluded_candidate_count"] == 2
    assert body["candidate_intake_gate"]["accepted_candidate_count"] == 0
    assert body["candidate_intake_gate"]["passed"] is False
    excluded_by_hash = {row["candidate_id_hash"]: row for row in body["excluded_candidates"]}
    assert len(excluded_by_hash) == 1
    duplicate_reasons = {reason for row in body["excluded_candidates"] for reason in row["exclusion_reasons"]}
    assert "not_disjoint_from_prior" in duplicate_reasons
    assert "duplicate_candidate_id" in duplicate_reasons
    assert "duplicate_query_id" in duplicate_reasons
    assert "pdf-doc-invalid-first" not in response.text
    assert "pdf-doc-valid-looking-duplicate" not in response.text


def test_holdout_candidate_validation_request_id_changes_with_prior_identity_hash_records() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    base_payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "candidate_rows": [
            {
                "candidate_id": "pdf-c1",
                "query_id": "pdf-q1",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-001",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            }
        ],
    }

    without_prior = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=base_payload).json()
    with_prior = client.post(
        HOLDOUT_CANDIDATE_VALIDATION_ROUTE,
        json={**base_payload, "prior_identity_hash_records": [{"source_identity_hash": "abc"}]},
    ).json()

    assert without_prior["request_id"] != with_prior["request_id"]


def test_enabled_diagnostic_holdout_candidate_validation_rejects_gold_prompt_path_and_readiness_fields() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "candidate_rows": [
            {
                "candidate_id": "bad-oracle",
                "query_id": "bad-q1",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-secret",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
                "expected_answer": "secret answer",
                "supporting_evidence": "secret evidence",
                "target_locator": "page 1",
                "gold_locator": "page 2",
                "raw_prompt": "hidden prompt",
                "prompt": "hidden prompt",
                "raw_llm_response": "hidden response",
                "local_path": "D:/private/source.pdf",
                "candidate_manifest_jsonl_created": True,
                "official_metric_input_rows": 1,
                "promotion_evidence": True,
                "product_success_evidence_allowed": True,
                "live_db_index_cache_readiness": True,
            },
            {
                "candidate_id": "bad-xlsx",
                "query_id": "bad-q2",
                "source_family": "XLSX",
                "source_identity": "xlsx-source-identity-alone",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "missing-required",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-missing-query",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "operational",
                "query_id": "operational-q",
                "source_family": "XLSX",
                "workbook_id": "workbook-operational",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
                "output_dir": "out/holdout",
                "job_name": "train-ft-a",
                "namespace": "production-index",
            },
        ],
    }

    response = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    serialized = response.text
    assert body["accepted_candidate_count"] == 0
    assert body["excluded_candidate_count"] == 4
    reasons = {reason for row in body["excluded_candidates"] for reason in row["exclusion_reasons"]}
    assert "protected_oracle_fields_present" in reasons
    assert "forbidden_prompt_or_llm_fields_present" in reasons
    assert "raw_local_path_present" in reasons
    assert "forbidden_contract_fields_present" in reasons
    assert "forbidden_operational_fields_present" in reasons
    assert "source_identity_missing" in reasons
    assert "required_fields_missing" in reasons
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert "secret answer" not in serialized
    assert "secret evidence" not in serialized
    assert "hidden prompt" not in serialized
    assert "hidden response" not in serialized
    assert "D:/private" not in serialized
    assert "pdf-doc-secret" not in serialized
    assert "xlsx-source-identity-alone" not in serialized
    assert "workbook-operational" not in serialized
    assert "production-index" not in serialized
    assert "__raw_local_path_redacted__" in serialized


def test_enabled_diagnostic_holdout_candidate_validation_reports_family_deficits_and_extra_forbid() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "candidate_rows": [
            {
                "candidate_id": "pdf-c1",
                "query_id": "pdf-q1",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-001",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            }
        ],
    }

    response = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)
    extra_response = client.post(
        HOLDOUT_CANDIDATE_VALIDATION_ROUTE,
        json={
            **payload,
            "candidate_manifest_path": "D:/private/holdout.jsonl",
            "raw_prompt": "hidden holdout prompt",
        },
    )
    wrong_schema_response = client.post(
        HOLDOUT_CANDIDATE_VALIDATION_ROUTE,
        json={
            **payload,
            "schema_version": "wrong_contract",
            "candidate_manifest_path": "D:/private/holdout.jsonl",
            "raw_prompt": "hidden holdout prompt",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_intake_gate"]["deficits"] == {
        "pdf_source_document_disjoint_needed": 19,
        "xlsx_workbook_disjoint_needed": 8,
        "pdf_query_fidelity_rows_needed": 99,
        "xlsx_query_fidelity_rows_needed": 100,
    }
    assert body["candidate_intake_gate"]["accepted_holdout_candidate_counts"]["TEXT_control_only"] == 0
    assert body["candidate_intake_gate"]["real_query_fidelity_included_counts"]["TEXT"] == 0
    assert extra_response.status_code == 422
    assert wrong_schema_response.status_code == 422
    for rejected_response in (extra_response, wrong_schema_response):
        assert "D:/private" not in rejected_response.text
        assert "hidden holdout prompt" not in rejected_response.text
        assert "pdf-doc-001" not in rejected_response.text
        assert all("input" not in detail for detail in rejected_response.json()["detail"])


def test_enabled_diagnostic_holdout_candidate_validation_rejects_identity_conflicts_and_prior_hash_collisions() -> None:
    service = SourceFirstRagService(readiness_report=v4_6_6_holdout_gap_blocker_report())
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))
    prior_hash = hashlib.sha256("PDF:pdf-doc-001".encode("utf-8")).hexdigest()
    payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "prior_identity_hash_records": [
            {
                "source_family": "PDF",
                "source_identity_hash": prior_hash,
                "identity_scope": "PDF_source_document",
                "source_identity_hash_algorithm": "sha256(family:identity_key)",
            }
        ],
        "candidate_rows": [
            {
                "candidate_id": "conflict",
                "query_id": "conflict-q",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-a",
                "document_id": "pdf-doc-b",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            {
                "candidate_id": "prior-hit",
                "query_id": "prior-q",
                "source_family": "PDF",
                "source_document_id": "pdf-doc-001",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
        ],
    }

    response = client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE, json=payload)

    assert response.status_code == 200
    body = response.json()
    reasons = {reason for row in body["excluded_candidates"] for reason in row["exclusion_reasons"]}
    assert "source_identity_field_conflict" in reasons
    assert "prior_identity_hash_collision" in reasons
    assert body["excluded_candidates"][1]["source_identity_hash"] == prior_hash
    assert (
        body["excluded_candidates"][1]["source_identity_hash_algorithm"]
        == "sha256(family:identity_key)"
    )
    assert body["source_identity_audit_gate"]["executed"] is True
    assert body["source_identity_audit_gate"]["collision_count"] == 1
    assert body["source_identity_audit_gate"]["passed"] is False
    assert "pdf-doc-a" not in response.text
    assert "pdf-doc-b" not in response.text
    assert "pdf-doc-001" not in response.text


def test_enabled_diagnostic_rag_route_preserves_source_first_boundary_and_evidence_truth() -> None:
    recorder = LlmRecorder()
    service = SourceFirstRagService(
        source_atoms=[atom("xlsx-a1", workbook="SecretBook.xlsx")],
        llm_invoker=recorder,
        index_available=True,
        source_atom_store_available=True,
    )
    client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=service))

    response = client.post(
        ROUTE,
        json={
            "query": "Book.xlsx Sheet1 A1 값을 알려줘",
            "source_family": "XLSX",
            "workbook_id": "SecretBook.xlsx",
            "sheet_name": "Sheet1",
            "cell": "A1",
            "tenant_id": "diagnostic-local",
            "debug": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["diagnostic_only"] is True
    assert body["answer_allowed_by_policy"] is True
    assert body["final_answer"] == "LLM:75%"
    assert body["llm_invoked"] is True
    assert len(recorder.calls) == 1
    assert body["official_metric_input_rows"] == 0
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["evidence_truth_source"] == "source_atom_evidence_bundle"
    assert body["search_view_candidate_metadata_only"] is True
    assert body["vector_payload_used_as_evidence_truth"] is False
    assert body["selected_source_atom_ids"] == ["xlsx-a1"]
    assert body["selected_search_view_ids"] == ["sv:xlsx-a1"]
    assert "raw_prompt" not in body
    assert "raw_llm_response" not in body
    assert "SecretBook.xlsx" not in response.text
    assert "XLSX:SecretBook.xlsx" not in response.text
    assert '"source_identity":' not in response.text
    assert '"raw_locator":' not in response.text
    assert '"workbook":' not in response.text
    assert body["citations"][0]["source_identity_hash"]
    assert body["evidence_bundles"][0]["xlsx_evidence"]["xlsx_display_metadata"]["display_value"] == "75%"
    assert body["evidence_bundles"][0]["xlsx_evidence"]["xlsx_display_metadata"]["formula_text_visible_to_user"] is False


def test_fail_closed_diagnostic_route_cases_do_not_invoke_llm() -> None:
    ambiguous_recorder = LlmRecorder()
    ambiguous_service = SourceFirstRagService(
        source_atoms=[
            atom("book-a1", workbook="Book.xlsx", display_value="75%"),
            atom("other-a1", workbook="Other.xlsx", display_value="88%"),
        ],
        llm_invoker=ambiguous_recorder,
        index_available=True,
    )
    ambiguous_client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=ambiguous_service))
    ambiguous = ambiguous_client.post(
        ROUTE,
        json={"query": "A1 값", "source_family": "XLSX", "cell": "A1"},
    ).json()
    assert ambiguous["answer_allowed_by_policy"] is False
    assert ambiguous["llm_invoked"] is False
    assert ambiguous["response_policy_bucket"] == "AMBIGUOUS_WORKBOOK_IDENTITY"
    assert ambiguous_recorder.calls == []

    deictic_recorder = LlmRecorder()
    deictic_service = SourceFirstRagService(source_atoms=[atom("xlsx-a1")], llm_invoker=deictic_recorder)
    deictic_client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=deictic_service))
    deictic = deictic_client.post(ROUTE, json={"query": "이 표 값은?", "source_family": "XLSX"}).json()
    assert deictic["answer_allowed_by_policy"] is False
    assert deictic["llm_invoked"] is False
    assert deictic["response_policy_bucket"] == "CONTEXT_REQUIRED"
    assert deictic_recorder.calls == []

    large_range_recorder = LlmRecorder()
    large_range_service = SourceFirstRagService(source_atoms=[atom("xlsx-a1")], llm_invoker=large_range_recorder)
    large_range_client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=large_range_service))
    large_range = large_range_client.post(
        ROUTE,
        json={"query": "Book.xlsx Sheet1 A1:Z99 요약", "source_family": "XLSX", "range": "A1:Z99"},
    ).json()
    assert large_range["answer_allowed_by_policy"] is False
    assert large_range["llm_invoked"] is False
    assert large_range["xlsx_range_rendering_mode"] == "UNSUPPORTED_RANGE_TOO_LARGE"
    assert large_range["fail_closed_reason"] == "UNSUPPORTED_RANGE_TOO_LARGE"
    assert large_range_recorder.calls == []

    unavailable_recorder = LlmRecorder()
    unavailable_service = SourceFirstRagService(
        source_atoms=[atom("xlsx-a1")],
        llm_invoker=unavailable_recorder,
        index_available=False,
    )
    unavailable_client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=unavailable_service))
    unavailable = unavailable_client.post(
        ROUTE,
        json={"query": "Book.xlsx Sheet1 A1 값", "source_family": "XLSX", "cell": "A1"},
    ).json()
    assert unavailable["answer_allowed_by_policy"] is False
    assert unavailable["llm_invoked"] is False
    assert unavailable["fail_closed_reason"] == "INDEX_UNAVAILABLE"
    assert unavailable_recorder.calls == []

    source_store_recorder = LlmRecorder()
    source_store_service = SourceFirstRagService(
        source_atoms=[atom("xlsx-a1")],
        llm_invoker=source_store_recorder,
        index_available=True,
        source_atom_store_available=False,
    )
    source_store_client = TestClient(create_app(settings=enabled_settings(), rag_diagnostic_service=source_store_service))
    source_store = source_store_client.post(
        ROUTE,
        json={"query": "Book.xlsx Sheet1 A1 값", "source_family": "XLSX", "cell": "A1"},
    ).json()
    assert source_store["answer_allowed_by_policy"] is False
    assert source_store["llm_invoked"] is False
    assert source_store["fail_closed_reason"] == "SOURCE_ATOM_STORE_UNAVAILABLE"
    assert source_store_recorder.calls == []


def test_xlsx_display_rendering_preserves_v3_22_value_formatting_contract() -> None:
    assert render_xlsx_display_value([atom("pct", display_value="75%", raw_value="0.75")])["rendered_value"] == "75%"
    assert (
        render_xlsx_display_value(
            [
                atom(
                    "date",
                    display_value="2026-05-27",
                    raw_value="45439",
                    normalized_value="2026-05-27",
                    value_type="date",
                    number_format="yyyy-mm-dd",
                )
            ]
        )["rendered_value"]
        == "2026-05-27"
    )
    assert (
        render_xlsx_display_value(
            [
                atom(
                    "currency",
                    display_value="$1,234.00",
                    raw_value="1234",
                    value_type="currency",
                    number_format="$#,##0.00",
                )
            ]
        )["rendered_value"]
        == "$1,234.00"
    )
    formula_result = render_xlsx_display_value(
        [
            atom(
                "formula",
                display_value="42",
                raw_value="42",
                value_type="formula",
                formula_cached_value="42",
            )
        ]
    )
    assert formula_result["rendered_value"] == "42"
    assert formula_result["formula_cached_value_used"] is True
    assert formula_result["formula_text_visible_to_user"] is False
    assert formula_result["formula_evaluation_at_query_time"] is False

    fallback = render_xlsx_display_value([atom("fallback", display_value=None, raw_value="raw-only")])
    assert fallback["rendered_value"] == "raw-only"
    assert fallback["format_confidence"] == "low"
    assert fallback["format_drop_reason"] == "FORMAT_METADATA_UNAVAILABLE"

    small_range = render_xlsx_display_value(
        [
            atom("a1", cell="A1", cell_range="A1:B2", display_value="A"),
            atom("b1", cell="B1", cell_range="A1:B2", display_value="B"),
            atom("a2", cell="A2", cell_range="A1:B2", display_value="C"),
            atom("b2", cell="B2", cell_range="A1:B2", display_value="D"),
        ],
        requested_range="A1:B2",
    )
    assert small_range["xlsx_range_rendering_mode"] == "SMALL_RANGE_TABLE"
    assert "| A1 | A |" in small_range["rendered_value"]

    bounded = render_xlsx_display_value(
        [atom(f"a{idx}", cell=f"A{idx}", cell_range="A1:A20", display_value=str(idx)) for idx in range(1, 13)],
        requested_range="A1:A20",
    )
    assert bounded["xlsx_range_rendering_mode"] == "BOUNDED_RANGE_SUMMARY"
    assert "materialized_cell_count=12" in bounded["rendered_value"]

    assert determine_xlsx_range_mode_from_request(requested_range="A1:Z99", selected_source_atoms=[]) == (
        "UNSUPPORTED_RANGE_TOO_LARGE"
    )


def test_diagnostic_xlsx_source_atom_validates_and_evidence_bundle_carries_display_metadata() -> None:
    source_atom = atom(
        "valid-formula",
        display_value="42",
        raw_value="42",
        value_type="formula",
        formula_cached_value="42",
    )

    validation = validate_source_atom(source_atom)
    bundle = assemble_evidence_bundle(
        "valid-formula",
        source_registry={"valid-formula": source_atom},
        mode="runtime_evidence",
    )

    assert validation["valid"] is True
    assert bundle["valid"] is True
    metadata = bundle["evidence_bundle"]["xlsx_evidence"]["xlsx_display_metadata"]
    assert metadata["display_value"] == "42"
    assert metadata["formula_cached_value_present"] is True
    assert metadata["formula_text_visible_to_user"] is False
    assert metadata["formula_evaluation_at_query_time"] is False
    assert "formula_text" not in metadata


def test_v3_22_script_reuses_importable_phase1_runtime_contract() -> None:
    script = ROOT / "ai" / "scripts" / "rag_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod.py"
    text = script.read_text(encoding="utf-8")

    assert "app.capabilities.rag_orchestrator.phase1_diagnostic_runtime" in text
    assert "PHASE1_V3_22_RUN_ID" in text
    assert "shared_range_shape" in text
