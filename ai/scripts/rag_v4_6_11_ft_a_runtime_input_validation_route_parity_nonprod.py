from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

AI_DIR = Path(__file__).resolve().parents[1]
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from fastapi.testclient import TestClient

from app.api import create_app
from app.capabilities.rag_orchestrator.phase1_diagnostic_runtime import (
    FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE_PATH,
    RagFtADryRunInputValidationRequest,
    SourceFirstRagService,
)
from app.core.config import WorkerSettings

import rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod as v464
import rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod as v465
import rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod as v466
import rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod as v4610


ROOT = v4610.ROOT
REPORT_DIR = v4610.REPORT_DIR
STATUS_JSONL = v4610.STATUS_JSONL
PROGRESS_DOC = v4610.PROGRESS_DOC
MEASUREMENTS_DOC = v4610.MEASUREMENTS_DOC
TRIAGE_DOC = v4610.TRIAGE_DOC
README = v4610.README
EVAL_README = v4610.EVAL_README

V4_NAME = v4610.V4_NAME
V4_RUN_FAMILY = v4610.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod"
EVENT_TYPE = "diagnostic_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod"
STATUS = "DIAGNOSTIC_V4_6_11_FT_A_RUNTIME_INPUT_VALIDATION_ROUTE_PARITY_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_6_11_ft_a_runtime_input_validation_route_parity_report_v1"

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "dry_run_input_manifest.jsonl",
            "dpo_dataset.jsonl",
            "ft_a_runtime_input_validation_route_parity.json",
            "metrics.json",
            "official_metric_results.jsonl",
            "prompt_manifest.json",
            "raw_llm_response.json",
            "review_packet.csv",
            "reward_model_dataset.jsonl",
            "sft_dataset.jsonl",
            "summary.json",
            "training_manifest.jsonl",
        }
    )
)

FORBIDDEN_RAW_VALUE_FRAGMENTS = (
    "이전 셀의 값을 설명해줘",
    "hidden prompt",
    "hidden response",
    "secret answer",
    "secret support",
    "pdf-source-identity",
    "D:/private",
    "row-ok",
    "query-ok",
)


def clean(value: Any) -> str:
    return v4610.clean(value)


def repo_relative(path: Path) -> str:
    return v4610.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return path.as_posix() if not _is_default_output_path(path) else repo_relative(path)


def utc_now() -> str:
    return v4610.utc_now()


def sha256_file(path: Path) -> str:
    return v4610.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v4610.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v4610.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v4610.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v4610.write_jsonl(path, rows)


def _is_default_output_path(path: Path) -> bool:
    try:
        return path.resolve() == REPORT_JSON.resolve()
    except OSError:
        return False


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _source_report_input(name: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    report = read_json(path) if exists else {}
    metrics = _mapping(report.get("metrics"))
    guardrails = _mapping(report.get("guardrails") or report.get("guardrail_audit"))
    boundary_flags_clean = (
        bool(report.get("diagnostic_only", True))
        and not bool(report.get("official_metric") or metrics.get("official_metric") or guardrails.get("official_metric"))
        and int(report.get("official_metric_input_rows") or metrics.get("official_metric_input_rows") or 0) == 0
        and not bool(report.get("promotion_evidence") or metrics.get("promotion_evidence") or guardrails.get("promotion_evidence"))
        and not bool(
            report.get("product_success_evidence_allowed")
            or metrics.get("product_success_evidence_allowed")
            or guardrails.get("product_success_evidence_allowed")
        )
        and not bool(
            report.get("live_db_index_cache_readiness")
            or metrics.get("live_db_index_cache_readiness")
            or guardrails.get("live_db_index_cache_readiness")
        )
    )
    return {
        "source_report_name": name,
        "source_report_json": repo_relative(path),
        "source_report_exists": exists,
        "source_report_sha256": sha256_file(path) if exists else "",
        "source_report_hash_current": bool(exists and path.is_file()),
        "source_run_id": clean(report.get("run_id")),
        "source_report_schema_version": clean(report.get("schema_version")),
        "source_report_status": clean(report.get("status")),
        "source_report_diagnostic_only": bool(report.get("diagnostic_only", True)),
        "official_metric": bool(report.get("official_metric") or metrics.get("official_metric")),
        "official_metric_input_rows": int(
            report.get("official_metric_input_rows") or metrics.get("official_metric_input_rows") or 0
        ),
        "promotion_evidence": bool(report.get("promotion_evidence") or metrics.get("promotion_evidence")),
        "product_success_evidence_allowed": bool(
            report.get("product_success_evidence_allowed") or metrics.get("product_success_evidence_allowed")
        ),
        "live_db_index_cache_readiness": bool(
            report.get("live_db_index_cache_readiness") or metrics.get("live_db_index_cache_readiness")
        ),
        "source_report_boundary_flags_clean": boundary_flags_clean,
    }


def build_source_report_inputs() -> dict[str, dict[str, Any]]:
    return {
        "v4_6_4": _source_report_input("v4_6_4", v464.REPORT_JSON),
        "v4_6_5": _source_report_input("v4_6_5", v465.REPORT_JSON),
        "v4_6_6": _source_report_input("v4_6_6", v466.REPORT_JSON),
        "v4_6_10": _source_report_input("v4_6_10", v4610.REPORT_JSON),
    }


def _valid_probe_rows() -> list[dict[str, Any]]:
    return [
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
    ]


def _leaky_probe_rows() -> list[dict[str, Any]]:
    return [
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
        },
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
        },
    ]


def _request_payload(rows: Sequence[Mapping[str, Any]], *, request_id: str = "ft-a-route-parity") -> dict[str, Any]:
    return {
        "schema_version": "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1",
        "request_id": request_id,
        "manifest_rows": [dict(row) for row in rows],
    }


def _enabled_settings() -> WorkerSettings:
    return WorkerSettings(rag_fastapi_diagnostic_route_enabled=True)


def _response_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _exclusion_reason_counts(validation: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in validation.get("excluded_manifest_rows") or []:
        reason = clean(_mapping(row).get("exclusion_reason"))
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _contract_metadata_bridge_present(contract: Mapping[str, Any]) -> bool:
    return (
        bool(contract.get("source_fixture_run_id"))
        and bool(contract.get("source_prompt_policy_baseline_run_id"))
        and bool(contract.get("required_future_dry_run_outputs"))
        and bool(contract.get("stop_condition_audit_buckets"))
    )


def _contains_forbidden_raw_fragment(value: Any) -> bool:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return any(fragment in serialized for fragment in FORBIDDEN_RAW_VALUE_FRAGMENTS)


def _validation_error_raw_input_redacted(response: Any) -> bool:
    if response.status_code != 422:
        return False
    body = _response_json(response)
    detail = body.get("detail")
    detail_rows = detail if isinstance(detail, list) else []
    if not detail_rows:
        return False
    if any(isinstance(row, Mapping) and "input" in row for row in detail_rows):
        return False
    return not _contains_forbidden_raw_fragment(response.text)


def build_ft_a_runtime_input_validation_route_parity() -> dict[str, Any]:
    service = SourceFirstRagService()
    script_validation = v464.validate_dry_run_input_manifest_rows(_valid_probe_rows())
    service_response = service.validate_ft_a_dry_run_input_manifest(
        RagFtADryRunInputValidationRequest(**_request_payload(_valid_probe_rows()))
    )
    service_payload = service_response.model_dump() if hasattr(service_response, "model_dump") else service_response.dict()
    enabled_client = TestClient(create_app(settings=_enabled_settings(), rag_diagnostic_service=service))
    enabled_response = enabled_client.post(
        FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE_PATH,
        json=_request_payload(_valid_probe_rows()),
    )
    enabled_payload = _response_json(enabled_response)
    leaky_response = enabled_client.post(
        FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE_PATH,
        json=_request_payload(_leaky_probe_rows(), request_id="ft-a-leak-probe"),
    )
    leaky_payload = _response_json(leaky_response)
    operational_fields = set()
    for row in _mapping(leaky_payload.get("dry_run_input_manifest_validation")).get("excluded_manifest_rows") or []:
        operational_fields.update(_mapping(row).get("forbidden_manifest_fields") or [])
    validation_error_response = enabled_client.post(
        FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE_PATH,
        json={
            **_request_payload(_leaky_probe_rows(), request_id="ft-a-extra-field-probe"),
            "dry_run_input_manifest_path": "D:/private/manifest.jsonl",
            "raw_prompt": "hidden prompt",
        },
    )

    disabled_payload = {
        **_request_payload(_leaky_probe_rows(), request_id="ft-a-disabled-probe"),
        "dry_run_input_manifest_path": "D:/private/manifest.jsonl",
        "raw_prompt": "hidden prompt",
    }
    disabled_response = TestClient(create_app(settings=WorkerSettings())).post(
        FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE_PATH,
        json=disabled_payload,
    )
    production_disabled_response = TestClient(
        create_app(
            settings=WorkerSettings(
                rag_query_orchestrator_mode="production",
                rag_fastapi_diagnostic_route_enabled=True,
            )
        )
    ).post(FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE_PATH, json=disabled_payload)

    enabled_validation = _mapping(enabled_payload.get("dry_run_input_manifest_validation"))
    script_reasons = _exclusion_reason_counts(script_validation)
    route_reasons = _exclusion_reason_counts(enabled_validation)
    contract = _mapping(enabled_payload.get("dry_run_input_manifest_contract"))
    count_fields = (
        "manifest_row_count",
        "accepted_manifest_row_count",
        "excluded_manifest_row_count",
        "gold_or_prompt_or_output_rejection_count",
        "official_metric_input_rows",
        "fine_tuning_dataset_exports_created",
    )
    script_runtime_counts_match = (
        enabled_response.status_code == 200
        and service_payload.get("accepted_manifest_row_count") == script_validation.get("accepted_manifest_row_count")
        and service_payload.get("excluded_manifest_row_count") == script_validation.get("excluded_manifest_row_count")
        and enabled_payload.get("accepted_manifest_row_count") == script_validation.get("accepted_manifest_row_count")
        and enabled_payload.get("excluded_manifest_row_count") == script_validation.get("excluded_manifest_row_count")
        and route_reasons == script_reasons
    )
    runtime_response_sanitized = not _contains_forbidden_raw_fragment(
        {
            "service_payload": service_payload,
            "enabled_payload": enabled_payload,
            "leaky_payload": leaky_payload,
            "enabled_text": enabled_response.text,
            "leaky_text": leaky_response.text,
        }
    )
    return {
        "schema_version": f"{RUN_ID}_runtime_input_validation_route_parity_v1",
        "run_id": RUN_ID,
        "route_path": FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE_PATH,
        "feature_flag_name": "RAG_FASTAPI_DIAGNOSTIC_ROUTE_ENABLED",
        "feature_flag_default_enabled": WorkerSettings().rag_fastapi_diagnostic_route_enabled,
        "production_orchestrator_mode_enabled": False,
        "disabled_route_status_code": disabled_response.status_code,
        "production_disabled_route_status_code": production_disabled_response.status_code,
        "disabled_route_raw_body_leakage_detected": _contains_forbidden_raw_fragment(
            disabled_response.text + production_disabled_response.text
        ),
        "enabled_valid_probe_status_code": enabled_response.status_code,
        "enabled_validation_error_status_code": validation_error_response.status_code,
        "enabled_validation_error_raw_input_redacted": _validation_error_raw_input_redacted(
            validation_error_response
        ),
        "script_runtime_counts_match": script_runtime_counts_match,
        "contract_metadata_bridge_present": _contract_metadata_bridge_present(contract),
        "runtime_response_sanitized": runtime_response_sanitized,
        "runtime_rejects_operational_metric_identity_fields": {
            "source_identity",
            "official_metric_input_rows",
            "training_job_created",
            "model_or_adapter_checkpoint_written",
            "dry_run_input_manifest_exported",
        }.issubset(operational_fields),
        "service_route_count_parity": {
            field: {
                "service": service_payload.get(field),
                "route": enabled_payload.get(field),
                "script": (
                    len(_valid_probe_rows())
                    if field == "manifest_row_count"
                    else script_validation.get(field)
                    if field in script_validation
                    else 0
                ),
            }
            for field in count_fields
        },
        "script_exclusion_reason_counts": script_reasons,
        "route_exclusion_reason_counts": route_reasons,
        "leaky_probe_exclusion_reason_counts": _exclusion_reason_counts(
            _mapping(leaky_payload.get("dry_run_input_manifest_validation"))
        ),
        "contract_metadata_bridge_keys": {
            "source_fixture_run_id": clean(contract.get("source_fixture_run_id")),
            "source_prompt_policy_baseline_run_id": clean(contract.get("source_prompt_policy_baseline_run_id")),
            "required_future_dry_run_output_count": len(contract.get("required_future_dry_run_outputs") or []),
            "stop_condition_audit_bucket_count": len(contract.get("stop_condition_audit_buckets") or []),
        },
        "response_boundary": {
            "diagnostic_only": bool(enabled_payload.get("diagnostic_only")),
            "manifest_rows_exported": bool(enabled_payload.get("manifest_rows_exported")),
            "prompt_payload_created": bool(enabled_payload.get("prompt_payload_created")),
            "prompt_manifest_created": bool(enabled_payload.get("prompt_manifest_created")),
            "raw_prompt_text_embedded": bool(enabled_payload.get("raw_prompt_text_embedded")),
            "raw_llm_response_payload_created": bool(enabled_payload.get("raw_llm_response_payload_created")),
            "fine_tuning_dataset_export_created": bool(enabled_payload.get("fine_tuning_dataset_export_created")),
            "training_job_created": bool(enabled_payload.get("training_job_created")),
            "model_or_adapter_checkpoint_written": bool(enabled_payload.get("model_or_adapter_checkpoint_written")),
            "official_metric": bool(enabled_payload.get("official_metric")),
            "official_metric_input_rows": int(enabled_payload.get("official_metric_input_rows") or 0),
            "promotion_evidence": bool(enabled_payload.get("promotion_evidence")),
            "product_success_evidence_allowed": bool(enabled_payload.get("product_success_evidence_allowed")),
            "live_db_index_cache_readiness": bool(enabled_payload.get("live_db_index_cache_readiness")),
            "protected_namespaces_touched": list(enabled_payload.get("protected_namespaces_touched") or []),
        },
    }


def build_guardrails() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "production_routing": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "official_metric_rows_created": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_prompt_text_embedded": False,
        "raw_llm_response_payload_created": False,
        "raw_runtime_request_body_embedded": False,
        "raw_runtime_response_body_embedded": False,
        "raw_local_path_values_exposed": False,
        "raw_source_identity_values_embedded": False,
        "source_atom_evidence_bundle_evidence_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "source_atom_registry_mutated": False,
        "protected_namespaces_touched": [],
        "db_or_production_namespace_written": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "review_csv_created": False,
        "review_packet_created": False,
        "single_report_artifact_contract": True,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_metrics(parity: Mapping[str, Any]) -> dict[str, Any]:
    response_boundary = _mapping(parity.get("response_boundary"))
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "ft_a_runtime_input_validation_route_parity_only": True,
        "runtime_parity_probe_only": True,
        "route_path": clean(parity.get("route_path")),
        "feature_flag_default_enabled": bool(parity.get("feature_flag_default_enabled")),
        "production_orchestrator_mode_enabled": bool(parity.get("production_orchestrator_mode_enabled")),
        "disabled_route_status_code": int(parity.get("disabled_route_status_code") or 0),
        "production_disabled_route_status_code": int(parity.get("production_disabled_route_status_code") or 0),
        "enabled_valid_probe_status_code": int(parity.get("enabled_valid_probe_status_code") or 0),
        "enabled_validation_error_status_code": int(parity.get("enabled_validation_error_status_code") or 0),
        "script_runtime_counts_match": bool(parity.get("script_runtime_counts_match")),
        "contract_metadata_bridge_present": bool(parity.get("contract_metadata_bridge_present")),
        "runtime_response_sanitized": bool(parity.get("runtime_response_sanitized")),
        "runtime_rejects_operational_metric_identity_fields": bool(
            parity.get("runtime_rejects_operational_metric_identity_fields")
        ),
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_dataset_exports_created": int(response_boundary.get("fine_tuning_dataset_exports_created") or 0),
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_prompt_text_embedded": False,
        "raw_llm_response_payload_created": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_report(
    *,
    source_inputs: Mapping[str, Mapping[str, Any]],
    parity: Mapping[str, Any],
    metrics: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "ft_a_runtime_input_validation_route_parity_only": True,
        "runtime_parity_probe_only": True,
        "source_report_inputs": {key: dict(value) for key, value in source_inputs.items()},
        "ft_a_runtime_input_validation_route_parity": dict(parity),
        "readiness_decision": "route_parity_ready_but_ft_a_dry_run_and_v4_7_remain_closed",
        "blocked_reasons": [
            "dry_run_input_manifest_export_not_authorized",
            "ft_route_policy_dry_run_not_opened",
            "real_external_holdout_and_user_policy_inputs_still_required",
        ],
        "artifact_paths": dict(artifact_paths),
        "summary": {
            **dict(metrics),
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "event_type": EVENT_TYPE,
            "status": STATUS,
            "v4_name": V4_NAME,
            "run_family": V4_RUN_FAMILY,
            "artifact_paths": dict(artifact_paths),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
        },
        "metrics": dict(metrics),
        "guardrails": dict(guardrails),
        "guardrail_audit": dict(guardrails),
        "review_csv_created": False,
        "single_report_artifact_contract": True,
        "sidecar_primary_artifacts_suppressed": True,
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_prompt_text_embedded": False,
        "raw_llm_response_payload_created": False,
        "v4_7_official_metric_gate_opened": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "verification": {
            "schema_version": f"{RUN_ID}_verification_v1",
            "run_id": RUN_ID,
            "commands_required_by_goal": [
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py --check",
                "targeted v4_6_11 source/route/status/guardrail tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_6_11 because this slice validates deterministic FastAPI "
                "route parity and redaction. Future FT-A training, embedding, or local LLM workloads should "
                "use GPU when gates open."
            ),
        },
        "residual_risks": [
            "No dry-run input manifest sidecar is exported.",
            "No prompt payload, prompt manifest, dataset, training manifest, job, checkpoint, or raw LLM response is emitted.",
            "No FT-A dry run is opened or executed.",
            "v4_7 official metric opening remains user-owned and unopened.",
        ],
        "next_recommendation": (
            "Register real source-disjoint external holdout candidate rows as an input-only manifest and rerun "
            "the v4_5/v4_6 gates before considering any dry-run manifest export or official metric opening."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    source_inputs = build_source_report_inputs()
    parity = build_ft_a_runtime_input_validation_route_parity()
    metrics = build_metrics(parity)
    guardrails = build_guardrails()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        source_inputs=source_inputs,
        parity=parity,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "ft_a_runtime_input_validation_route_parity": parity,
        "metrics": metrics,
        "guardrails": guardrails,
    }


def remove_stale_sidecar_artifacts(target_dir: Path) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()


def assert_single_report_directory(target_dir: Path) -> None:
    unexpected = sorted(path.name for path in target_dir.iterdir() if path.name != "report.json")
    if unexpected:
        raise RuntimeError(f"unexpected v4_6_11 primary artifacts: {unexpected}")


def write_artifacts(artifacts: Mapping[str, Any], *, output_dir: Path | None = None) -> dict[str, Any]:
    target_dir = output_dir or OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    report_path = target_dir / "report.json"
    report = dict(artifacts["report"])
    report["artifact_paths"] = {"report_json": artifact_path_text(report_path)}
    report["summary"] = dict(report["summary"])
    report["summary"]["artifact_paths"] = dict(report["artifact_paths"])
    report["summary"]["single_report_artifact_contract"] = True
    report["summary"]["sidecar_primary_artifacts_suppressed"] = True
    report["metrics"] = dict(report["metrics"])
    report["metrics"]["single_report_artifact_contract"] = True
    report["metrics"]["sidecar_primary_artifacts_suppressed"] = True
    report["review_csv_created"] = False
    remove_stale_sidecar_artifacts(target_dir)
    assert_single_report_directory(target_dir)
    write_json(report_path, report)
    assert_single_report_directory(target_dir)
    return report


def artifact_sha256_from_report_paths(artifact_paths: Mapping[str, str]) -> dict[str, str]:
    return v466.artifact_sha256_from_report_paths(artifact_paths)


def append_status_event(report: Mapping[str, Any]) -> None:
    event = {
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": artifact_sha256_from_report_paths(report["artifact_paths"]),
        "report_json_created": True,
        "review_csv_created": False,
        "summary_json_created": False,
        "per_run_markdown_created": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
        "ft_a_runtime_input_validation_route_parity": dict(report["ft_a_runtime_input_validation_route_parity"]),
        "source_report_inputs": dict(report["source_report_inputs"]),
        "readiness_decision": report["readiness_decision"],
        "blocked_reasons": list(report["blocked_reasons"]),
        "schema_version": f"{RUN_ID}_status_event_v1",
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def _replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v4610.v469.v467.replace_marked_entry(path, marker, entry)


def _refresh_docs() -> None:
    return None


def update_current_status_lines() -> None:
    current_status = f"{EVENT_TYPE}_ready"
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{current_status}`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_6_11 FT-A runtime input validation route parity loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_10 external holdout candidate manifest gate replay loop:\n`[^`]+`;",
        "current diagnostic v4_6_11 FT-A runtime input validation route parity loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_6_10 external holdout candidate manifest gate replay loop:\n"
        f"`{v4610.RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")

    readme_text = README.read_text(encoding="utf-8")
    readme_text = re.sub(
        r"Current RAG status: `[^`]+`\.",
        f"Current RAG status: `{current_status}`.",
        readme_text,
        count=1,
    )
    verify_start = readme_text.index("## How To Verify Locally")
    verify_end = readme_text.index("## Repo Map")
    verify_section = readme_text[verify_start:verify_end]
    script = "ai\\scripts\\rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py"
    compile_cmd = f"python -X utf8 -m py_compile {script}"
    check_cmd = f"python -X utf8 {script} --check"
    if compile_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod.py\n",
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod.py\n"
            f"{compile_cmd}\n",
            1,
        )
    if check_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 ai\\scripts\\rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod.py --check\n",
            "python -X utf8 ai\\scripts\\rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod.py --check\n"
            f"{check_cmd}\n",
            1,
        )
    README.write_text(readme_text[:verify_start] + verify_section + readme_text[verify_end:], encoding="utf-8")

    eval_text = EVAL_README.read_text(encoding="utf-8")
    eval_text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{current_status}`",
        eval_text,
        count=1,
    )
    eval_text = re.sub(
        r"v4_6_10 is `diagnostic_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod_ready`"
        r"(?:; v4_6_11 is `[^`]+`)?\.",
        f"v4_6_10 is `{v4610.EVENT_TYPE}_ready`; v4_6_11 is `{current_status}`.",
        eval_text,
        count=1,
    )
    EVAL_README.write_text(eval_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py` | "
        "Hash-locks the FastAPI FT-A dry-run input validation route against the v4_6_4 validator. "
        "It exercises default-disabled, production-disabled, enabled, validation-error, redaction, and "
        "operational-field rejection paths without exporting dry-run inputs, prompt manifests, raw LLM "
        "responses, datasets, jobs, checkpoints, official metric rows, promotion evidence, product-success "
        "evidence, or live-readiness claims. |"
    )
    pattern = r"\n?\| `rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod\.py` \| .*?\|"
    text = re.sub(pattern, "", text)
    text = text.replace(
        "\n\nv4 scripts remain diagnostic/non-production",
        f"\n{row}\n\nv4 scripts remain diagnostic/non-production",
        1,
    )
    scripts_readme.write_text(text, encoding="utf-8")


def update_v4_plan_note() -> None:
    plan_path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    text = plan_path.read_text(encoding="utf-8")
    if "### v4_6_11 — FT-A Runtime Input Validation Route Parity" not in text:
        insert = """### v4_6_11 — FT-A Runtime Input Validation Route Parity

This is a diagnostic runtime-route parity check, not dry-run input manifest export and not FT-A execution.

Purpose:

- Lock the FastAPI FT-A dry-run input validation route to the v4_6_4 validator behavior.
- Verify default-disabled and production-disabled routing before body parsing leaks raw prompt/path content.
- Verify enabled responses stay sanitized/hash-only and reject prompt/gold/output, operational metric, training, checkpoint, and source-identity fields.
- Keep dry-run input manifest export, FT-A execution, dataset export, v4_7, official metric, promotion, product-success, and live-readiness gates closed.

Locked boundary:

```text
ft_a_runtime_input_validation_route_parity_only = true
runtime_parity_probe_only = true
dry_run_input_manifest_exported = false
ft_route_policy_dry_run_opened = false
ft_route_policy_dry_run_executed = false
fine_tuning_dataset_exports_created = 0
training_job_created = false
model_or_adapter_checkpoint_written = false
official_metric_input_rows = 0
promotion_evidence = false
product_success_evidence_allowed = false
live_db_index_cache_readiness = false
```

"""
        text = text.replace("### v4_7 — Official Metric Opening Gate", insert + "### v4_7 — Official Metric Opening Gate", 1)
    text = text.replace(
        "v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        "v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod\n↓\nv4_6_11_ft_a_runtime_input_validation_route_parity_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
    )
    plan_path.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    report_path = report["artifact_paths"]["report_json"]
    metrics = report["metrics"]
    _refresh_docs()
    progress_entry = (
        f"- v4_6_11 FT-A runtime input validation route parity (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It hash-locks the FastAPI diagnostic/internal FT-A dry-run input validation route against the "
        "v4_6_4 validator, covering default-disabled and production-disabled 404 behavior, enabled route "
        "count parity, sanitized/hash-only response projection, validation-error input redaction, and "
        "operational metric/source-identity/training/checkpoint field rejection. This remains runtime-parity "
        "probe-only: it does not export a dry-run input manifest, does not create prompt payloads or prompt "
        "manifests, does not create raw LLM responses, datasets, jobs, checkpoints, official metric rows, "
        "promotion evidence, product-success evidence, production routing, or live DB/index/cache readiness."
    )
    measurements_entry = f"""### v4_6_11 FT-A Runtime Input Validation Route Parity

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Primary artifact: `{report_path}`
- Source evidence: v4_6_4/v4_6_5/v4_6_6/v4_6_10 report hashes and the FastAPI diagnostic/internal FT-A dry-run input validation route.
- Interpretation: route parity and redaction are measured as deterministic contract checks only. This is not dry-run input manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, not product-success evidence, and not live readiness.

| Counter | Value |
|---|---:|
| ft_a_runtime_input_validation_route_parity_only | true |
| runtime_parity_probe_only | true |
| disabled_route_status_code | {metrics['disabled_route_status_code']} |
| production_disabled_route_status_code | {metrics['production_disabled_route_status_code']} |
| enabled_valid_probe_status_code | {metrics['enabled_valid_probe_status_code']} |
| enabled_validation_error_status_code | {metrics['enabled_validation_error_status_code']} |
| script_runtime_counts_match | {str(metrics['script_runtime_counts_match']).lower()} |
| contract_metadata_bridge_present | {str(metrics['contract_metadata_bridge_present']).lower()} |
| runtime_response_sanitized | {str(metrics['runtime_response_sanitized']).lower()} |
| runtime_rejects_operational_metric_identity_fields | {str(metrics['runtime_rejects_operational_metric_identity_fields']).lower()} |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Artifact policy: single ignored `report.json`; no route-parity sidecar, dry-run input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, official metric result, or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_6_11 FT-A Runtime Input Validation Route Parity Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_6_11 is diagnostic-only, non-production, and runtime-parity-probe-only.\n"
        "- It verifies the FastAPI FT-A dry-run input validation route preserves v4_6_4 validator counts, rejects forbidden prompt/gold/output and operational fields, redacts validation error input, and stays default-disabled and production-disabled.\n"
        "- It is not dry-run input manifest export, not FT-A dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.\n"
        "- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `live_db_index_cache_readiness=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.\n"
        "- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion gate.\n"
    )
    _replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    _replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    _replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    update_scripts_readme()
    update_v4_plan_note()
    _refresh_docs()


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise AssertionError("unexpected v4_6_11 schema")
    if report.get("run_id") != RUN_ID:
        raise AssertionError("unexpected v4_6_11 run_id")
    if report.get("diagnostic_only") is not True:
        raise AssertionError("v4_6_11 must remain diagnostic-only")
    if report.get("ft_a_runtime_input_validation_route_parity_only") is not True:
        raise AssertionError("route parity flag must remain true")
    parity = _mapping(report.get("ft_a_runtime_input_validation_route_parity"))
    guardrails = _mapping(report.get("guardrails"))
    if parity.get("route_path") != FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE_PATH:
        raise AssertionError("unexpected FT-A route path")
    required_parity_true = (
        "script_runtime_counts_match",
        "contract_metadata_bridge_present",
        "runtime_response_sanitized",
        "runtime_rejects_operational_metric_identity_fields",
        "enabled_validation_error_raw_input_redacted",
    )
    for field in required_parity_true:
        if parity.get(field) is not True:
            raise AssertionError(f"{field} must remain true")
    if parity.get("feature_flag_default_enabled") is not False:
        raise AssertionError("diagnostic route must remain disabled by default")
    if parity.get("production_orchestrator_mode_enabled") is not False:
        raise AssertionError("diagnostic route must remain disabled in production mode")
    if int(parity.get("disabled_route_status_code") or 0) != 404:
        raise AssertionError("disabled route must 404")
    if int(parity.get("production_disabled_route_status_code") or 0) != 404:
        raise AssertionError("production-disabled route must 404")
    if parity.get("disabled_route_raw_body_leakage_detected") is not False:
        raise AssertionError("disabled route must not leak raw body")
    if int(parity.get("enabled_valid_probe_status_code") or 0) != 200:
        raise AssertionError("enabled valid probe must return 200")
    if int(parity.get("enabled_validation_error_status_code") or 0) != 422:
        raise AssertionError("enabled extra-field probe must return 422")
    for field in (
        "dry_run_input_manifest_exported",
        "ft_route_policy_dry_run_opened",
        "ft_route_policy_dry_run_executed",
        "fine_tuning_dataset_export_created",
        "training_manifest_jsonl_created",
        "training_job_created",
        "model_or_adapter_checkpoint_written",
        "prompt_payload_created",
        "prompt_manifest_created",
        "raw_prompt_text_embedded",
        "raw_llm_response_payload_created",
        "v4_7_official_metric_gate_opened",
        "official_metric",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
    ):
        if report.get(field) is not False:
            raise AssertionError(f"{field} must remain false")
        if guardrails.get(field) is not False:
            raise AssertionError(f"guardrail {field} must remain false")
    for field in ("official_metric_input_rows", "fine_tuning_dataset_exports_created"):
        if int(report.get(field) or 0) != 0:
            raise AssertionError(f"{field} must remain 0")
        if int(guardrails.get(field) or 0) != 0:
            raise AssertionError(f"guardrail {field} must remain 0")
    if guardrails.get("protected_namespaces_touched") != []:
        raise AssertionError("protected namespaces must remain untouched")
    if _contains_forbidden_raw_fragment(report):
        raise AssertionError("raw query, prompt, answer, identity, row id, query id, or path leaked")


def run_write() -> dict[str, Any]:
    artifacts = build_artifacts()
    report = write_artifacts(artifacts)
    check_report(report)
    update_docs(report)
    append_status_event(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    report = artifacts["report"]
    check_report(report)
    if args.check:
        metrics = report["metrics"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": STATUS,
                    "ft_a_runtime_input_validation_route_parity_only": True,
                    "runtime_parity_probe_only": True,
                    "script_runtime_counts_match": metrics["script_runtime_counts_match"],
                    "runtime_response_sanitized": metrics["runtime_response_sanitized"],
                    "contract_metadata_bridge_present": metrics["contract_metadata_bridge_present"],
                    "runtime_rejects_operational_metric_identity_fields": metrics[
                        "runtime_rejects_operational_metric_identity_fields"
                    ],
                    "dry_run_input_manifest_exported": False,
                    "ft_route_policy_dry_run_opened": False,
                    "official_metric_input_rows": 0,
                    "promotion_evidence": False,
                    "gpu_required_for_this_slice": False,
                    "gpu_required_for_future_training_when_opened": True,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    written = run_write()
    print(json.dumps({"report": written["artifact_paths"]["report_json"], "run_id": RUN_ID, "status": STATUS}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
