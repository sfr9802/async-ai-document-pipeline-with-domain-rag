"""Input-only FT-A dry-run manifest validation for diagnostic runtime routes.

The helpers here mirror the v4_6_4 script contract without exporting a
manifest, prompt payload, dataset, job, checkpoint, official metric row, or
promotion evidence.
"""

from __future__ import annotations

import re
import hashlib
from typing import Any, Mapping, Sequence

from app.capabilities.rag.holdout_manifest_contract import (
    V4_READINESS_NAME,
    V4_READINESS_RUN_FAMILY,
)


FT_A_DRY_RUN_INPUT_VALIDATION_REQUEST_VERSION = (
    "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1"
)
FT_A_DRY_RUN_INPUT_MANIFEST_VALIDATOR_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod"
)
FT_A_DRY_RUN_INPUT_MANIFEST_VALIDATION_SCHEMA_VERSION = (
    f"{FT_A_DRY_RUN_INPUT_MANIFEST_VALIDATOR_RUN_ID}_dry_run_input_manifest_validation_v1"
)
SOURCE_FIXTURE_RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod"
SOURCE_PROMPT_POLICY_BASELINE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod"
)

REQUIRED_MANIFEST_FIELDS = (
    "row_id",
    "query_id",
    "source_family",
    "route_lane",
    "response_policy_bucket",
    "prompt_policy_id",
)
TARGET_POLICY_BUCKETS = (
    "ANSWER_ALLOWED",
    "CONTEXT_REQUIRED",
    "AMBIGUOUS_WORKBOOK_IDENTITY",
    "AMBIGUOUS_FILE_IDENTITY",
    "UNSUPPORTED_RANGE_TOO_LARGE",
    "INDEX_UNAVAILABLE",
    "CONTRACT_VIOLATION",
    "UNSUPPORTED_ROUTE",
)
ALLOWED_ROUTE_LANES = ("rough_query", "deictic", "user_locator", "hybrid", "unsupported")
ALLOWED_SOURCE_FAMILIES = ("PDF", "XLSX", "TEXT")
ALLOWED_MODEL_INPUT_FIELDS = (
    "raw_query_text",
    "source_family",
    "route_lane",
    "active_context_available",
    "candidate_search_view_count",
    "selected_source_atom_count",
    "selected_evidence_bundle_count",
    "fail_closed_reason_code",
)
LABEL_ONLY_FIELDS = ("response_policy_bucket", "fail_closed")
FORBIDDEN_MODEL_INPUT_FIELDS = (
    "expected_answer",
    "supporting_evidence",
    "target_locator",
    "gold_locator",
    "hidden_target_locator",
    "hidden_supporting_evidence",
    "raw_prompt",
    "raw_llm_response",
    "final_answer",
    "normalized_answer_value",
    "direct_answer_value",
    "source_file_path",
    "local_file_path",
)
FORBIDDEN_FIELD_NAME_PATTERNS = (
    "answer",
    "expected",
    "support",
    "gold",
    "qrel",
    "label",
    "prompt",
    "llm",
    "response",
    "generated",
    "target",
    "locator",
    "path",
)
PROMPT_POLICY_IDS = (
    "deterministic_rule_baseline_v1",
    "prompt_only_policy_bucket_classifier_schema_v1",
    "conservative_fallback_policy_v1",
)
REQUIRED_FUTURE_DRY_RUN_OUTPUTS = (
    "deterministic_rule_baseline_policy_bucket",
    "prompt_only_baseline_policy_bucket",
    "ft_model_policy_bucket",
    "conservative_fallback_policy_bucket",
)
STOP_CONDITION_AUDIT_BUCKETS = (
    "fail_closed_preservation_regression",
    "answer_allowed_overreach",
    "context_required_false_negative",
    "ambiguous_identity_false_negative",
    "unsupported_route_false_negative",
)
RAW_LOCAL_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|//|/(?:data|home|mnt|opt|private|repo|tmp|Users|var|workspace)(?:/|$))",
    re.IGNORECASE,
)


def clean(value: Any) -> str:
    return str(value or "").strip()


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def forbidden_prompt_gold_or_output_fields_present(row: Mapping[str, Any]) -> list[str]:
    allowed_fields = set(REQUIRED_MANIFEST_FIELDS) | set(ALLOWED_MODEL_INPUT_FIELDS) | set(LABEL_ONLY_FIELDS)
    allowed_field_names = {field.casefold() for field in allowed_fields}
    forbidden: set[str] = set()
    for field in row:
        normalized = clean(field).casefold()
        if normalized in allowed_field_names:
            continue
        forbidden.add(field)
    return sorted(forbidden)


def accepted_manifest_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "row_id": clean(row.get("row_id")),
        "query_id": clean(row.get("query_id")),
        "source_family": clean(row.get("source_family")).upper(),
        "route_lane": clean(row.get("route_lane")),
        "response_policy_bucket": clean(row.get("response_policy_bucket")),
        "prompt_policy_id": clean(row.get("prompt_policy_id")),
        "model_input_fields": {
            field: row.get(field)
            for field in ALLOWED_MODEL_INPUT_FIELDS
            if field in row and has_value(row.get(field))
        },
    }


def validate_dry_run_input_manifest_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    allowed_prompt_policy_ids = set(PROMPT_POLICY_IDS)
    for index, raw_row in enumerate(rows):
        row = raw_row if isinstance(raw_row, Mapping) else {}
        row_id = clean(row.get("row_id")) or f"row-{index}"
        missing_required = [field for field in REQUIRED_MANIFEST_FIELDS if not has_value(row.get(field))]
        if missing_required:
            excluded.append(
                {
                    "row_id": _sanitize_fastapi_value(row_id),
                    "exclusion_reason": "missing_required_manifest_field",
                    "missing_required_manifest_fields": missing_required,
                }
            )
            continue
        forbidden_fields = forbidden_prompt_gold_or_output_fields_present(row)
        if forbidden_fields:
            excluded.append(
                {
                    "row_id": _sanitize_fastapi_value(row_id),
                    "exclusion_reason": "forbidden_prompt_gold_or_output_field_present",
                    "forbidden_manifest_fields": forbidden_fields,
                }
            )
            continue
        source_family = clean(row.get("source_family")).upper()
        route_lane = clean(row.get("route_lane"))
        bucket = clean(row.get("response_policy_bucket"))
        prompt_policy_id = clean(row.get("prompt_policy_id"))
        if source_family not in ALLOWED_SOURCE_FAMILIES:
            excluded.append({"row_id": _sanitize_fastapi_value(row_id), "exclusion_reason": "unsupported_source_family"})
            continue
        if route_lane not in ALLOWED_ROUTE_LANES:
            excluded.append({"row_id": _sanitize_fastapi_value(row_id), "exclusion_reason": "unsupported_route_lane"})
            continue
        if bucket not in TARGET_POLICY_BUCKETS:
            excluded.append(
                {"row_id": _sanitize_fastapi_value(row_id), "exclusion_reason": "unsupported_response_policy_bucket"}
            )
            continue
        if prompt_policy_id not in allowed_prompt_policy_ids:
            excluded.append({"row_id": _sanitize_fastapi_value(row_id), "exclusion_reason": "unsupported_prompt_policy_id"})
            continue
        accepted.append(accepted_manifest_row(row))
    leakage_rejections = sum(
        1
        for row in excluded
        if row["exclusion_reason"] == "forbidden_prompt_gold_or_output_field_present"
    )
    return {
        "schema_version": FT_A_DRY_RUN_INPUT_MANIFEST_VALIDATION_SCHEMA_VERSION,
        "run_id": FT_A_DRY_RUN_INPUT_MANIFEST_VALIDATOR_RUN_ID,
        "fixture_row_count": len(rows),
        "accepted_manifest_rows": accepted,
        "excluded_manifest_rows": excluded,
        "accepted_manifest_row_count": len(accepted),
        "excluded_manifest_row_count": len(excluded),
        "gold_or_prompt_or_output_rejection_count": leakage_rejections,
        "manifest_rows_exported": False,
        "official_metric_input_rows": 0,
        "training_dataset_export_created": False,
        "prompt_payload_created": False,
        "raw_llm_response_payload_created": False,
    }


def build_dry_run_input_manifest_contract() -> dict[str, Any]:
    return {
        "schema_version": f"{FT_A_DRY_RUN_INPUT_MANIFEST_VALIDATOR_RUN_ID}_dry_run_input_manifest_contract_v1",
        "run_id": FT_A_DRY_RUN_INPUT_MANIFEST_VALIDATOR_RUN_ID,
        "v4_name": V4_READINESS_NAME,
        "run_family": V4_READINESS_RUN_FAMILY,
        "lane": "FT-A",
        "source_fixture_run_id": SOURCE_FIXTURE_RUN_ID,
        "source_prompt_policy_baseline_run_id": SOURCE_PROMPT_POLICY_BASELINE_RUN_ID,
        "manifest_validator_schema_ready": True,
        "manifest_rows_exported": False,
        "required_manifest_fields": list(REQUIRED_MANIFEST_FIELDS),
        "optional_manifest_input_fields": list(ALLOWED_MODEL_INPUT_FIELDS),
        "label_only_fields": list(LABEL_ONLY_FIELDS),
        "target_policy_buckets": list(TARGET_POLICY_BUCKETS),
        "allowed_route_lanes": list(ALLOWED_ROUTE_LANES),
        "allowed_source_families": list(ALLOWED_SOURCE_FAMILIES),
        "allowed_prompt_policy_ids": list(PROMPT_POLICY_IDS),
        "required_future_dry_run_outputs": list(REQUIRED_FUTURE_DRY_RUN_OUTPUTS),
        "stop_condition_audit_buckets": list(STOP_CONDITION_AUDIT_BUCKETS),
        "forbidden_model_input_fields": list(FORBIDDEN_MODEL_INPUT_FIELDS),
        "forbidden_field_name_patterns": list(FORBIDDEN_FIELD_NAME_PATTERNS),
        "raw_prompt_text_allowed": False,
        "prompt_payload_allowed": False,
        "prompt_manifest_allowed": False,
        "raw_llm_response_allowed": False,
        "training_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
    }


def validate_ft_a_dry_run_input_manifest_rows_for_fastapi(
    manifest_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validation = _sanitize_validation_for_fastapi(validate_dry_run_input_manifest_rows(manifest_rows))
    return {
        "diagnostic_only": True,
        "ft_a_dry_run_input_manifest_validator_only": True,
        "v4_name": V4_READINESS_NAME,
        "run_family": V4_READINESS_RUN_FAMILY,
        "schema_version": validation["schema_version"],
        "run_id": FT_A_DRY_RUN_INPUT_MANIFEST_VALIDATOR_RUN_ID,
        "dry_run_input_manifest_contract": build_dry_run_input_manifest_contract(),
        "dry_run_input_manifest_validation": validation,
        "manifest_row_count": len(manifest_rows),
        "accepted_manifest_row_count": int(validation["accepted_manifest_row_count"]),
        "excluded_manifest_row_count": int(validation["excluded_manifest_row_count"]),
        "gold_or_prompt_or_output_rejection_count": int(
            validation["gold_or_prompt_or_output_rejection_count"]
        ),
        "dry_run_input_manifest_gate_passed": False,
        "manifest_rows_exported": False,
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_prompt_text_embedded": False,
        "raw_llm_response_payload_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "db_or_production_namespace_written": False,
        "protected_namespaces_touched": [],
        "warnings": [
            "diagnostic_only",
            "validator_only",
            "input_only",
            "not_production_routing",
            "no_artifact_writes",
            "no_prompt_payload_created",
            "no_training_dataset_export",
            "no_official_metric_rows",
        ],
    }


def _sanitize_fastapi_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _sanitize_fastapi_value(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_fastapi_value(item) for item in value]
    if isinstance(value, str) and RAW_LOCAL_PATH_RE.search(value.replace("\\", "/")):
        return "__local_path_redacted__"
    return value


def _sha256(value: Any) -> str:
    cleaned = clean(value)
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest() if cleaned else ""


def _sanitize_validation_for_fastapi(validation: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(validation)
    payload["accepted_manifest_rows"] = [
        _sanitize_accepted_manifest_row(row)
        for row in validation.get("accepted_manifest_rows", [])
        if isinstance(row, Mapping)
    ]
    payload["excluded_manifest_rows"] = [
        _sanitize_excluded_manifest_row(row)
        for row in validation.get("excluded_manifest_rows", [])
        if isinstance(row, Mapping)
    ]
    return payload


def _sanitize_accepted_manifest_row(row: Mapping[str, Any]) -> dict[str, Any]:
    model_inputs = row.get("model_input_fields")
    model_input_fields = model_inputs if isinstance(model_inputs, Mapping) else {}
    return {
        "row_id_hash": _sha256(row.get("row_id")),
        "query_id_hash": _sha256(row.get("query_id")),
        "source_family": clean(row.get("source_family")).upper(),
        "route_lane": clean(row.get("route_lane")),
        "response_policy_bucket": clean(row.get("response_policy_bucket")),
        "prompt_policy_id": clean(row.get("prompt_policy_id")),
        "model_input_field_names": sorted(str(field) for field in model_input_fields),
    }


def _sanitize_excluded_manifest_row(row: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = {
        str(key): _sanitize_fastapi_value(value)
        for key, value in row.items()
        if key not in {"row_id", "query_id"}
    }
    row_id_hash = _sha256(row.get("row_id"))
    query_id_hash = _sha256(row.get("query_id"))
    if row_id_hash:
        sanitized["row_id_hash"] = row_id_hash
    if query_id_hash:
        sanitized["query_id_hash"] = query_id_hash
    return sanitized
