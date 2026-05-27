"""Feature-flagged Phase 1 source-first diagnostic RAG service.

This module is intentionally runtime-adjacent rather than production routing:
SearchView payloads are candidate metadata only, while SourceAtom/EvidenceBundle
contracts remain the evidence truth boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from pydantic import BaseModel, Field

from app.capabilities.rag.ft_dry_run_manifest_validation import (
    FT_A_DRY_RUN_INPUT_VALIDATION_REQUEST_VERSION,
    validate_ft_a_dry_run_input_manifest_rows_for_fastapi,
)
from app.capabilities.rag.holdout_candidate_validation import validate_holdout_candidate_rows_for_fastapi
from app.capabilities.rag.holdout_manifest_contract import (
    HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION,
    V4_READINESS_NAME,
    V4_READINESS_RUN_FAMILY,
    build_holdout_acquisition_requirements,
    build_holdout_candidate_manifest_contract,
)
from app.capabilities.rag.source_registry import SOURCE_REGISTRY_CONTRACT_VERSION, assemble_evidence_bundle
from app.capabilities.rag_orchestrator.agent_runtime import (
    AgentRuntime,
    AgentRuntimeRequest,
    EVIDENCE_TRUTH_SOURCE,
)
from app.capabilities.rag_orchestrator.runtime_adapters import (
    InMemorySearchIndexAdapter,
    InMemorySourceAtomStoreAdapter,
)

PHASE1_V3_22_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_22_"
    "xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
)
PHASE1_FASTAPI_STATUS_MARKER = "PHASE1_DIAGNOSTIC_CONTRACT_CLOSURE_FASTAPI_DIAGNOSTIC_INTEGRATION_READY"
DIAGNOSTIC_ROUTE_PATH = "/internal/rag/diagnostic/query"
FEATURE_FLAG_NAME = "RAG_FASTAPI_DIAGNOSTIC_ROUTE_ENABLED"
SETTINGS_FEATURE_FIELD = "rag_fastapi_diagnostic_route_enabled"
DIAGNOSTIC_NAMESPACE = "rag-phase1-fastapi-diagnostic-nonprod"
READINESS_ROUTE_PATH = "/internal/rag/diagnostic/readiness"
HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH = "/internal/rag/diagnostic/holdout-candidates/validate"
FT_A_DRY_RUN_INPUT_VALIDATION_ROUTE_PATH = "/internal/rag/diagnostic/ft-a/dry-run-input/validate"
V4_6_PREFLIGHT_RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod"
V4_6_6_HOLDOUT_GAP_BLOCKER_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod"
)
V4_6_10_MANIFEST_GATE_REPLAY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod"
)
V4_6_12_RUNTIME_REPLAY_ROUTE_PARITY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
)
DEFAULT_V4_6_READINESS_REPORT = (
    Path(__file__).resolve().parents[4]
    / "ai"
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "quality"
    / V4_6_PREFLIGHT_RUN_ID
    / "report.json"
)
DEFAULT_V4_READINESS_REPORT = (
    Path(__file__).resolve().parents[4]
    / "ai"
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "quality"
    / V4_6_12_RUNTIME_REPLAY_ROUTE_PARITY_RUN_ID
    / "report.json"
)
SMALL_RANGE_MAX_CELLS = 8
BOUNDED_SUMMARY_MAX_CELLS = 100
RANGE_MODES = {
    "SINGLE_CELL_VALUE",
    "SMALL_RANGE_TABLE",
    "BOUNDED_RANGE_SUMMARY",
    "UNSUPPORTED_RANGE_TOO_LARGE",
    "FORMAT_METADATA_UNAVAILABLE",
    "AMBIGUOUS_RANGE_CONTEXT_REQUIRED",
}
FORBIDDEN_READINESS_DEBUG_KEYS = {
    "full_prompt",
    "llm_response",
    "prompt",
    "prompt_manifest",
    "prompt_payload",
    "prompt_text",
    "raw_llm_payload",
    "raw_llm_request",
    "raw_llm_response",
    "raw_prompt",
}
HAZARDOUS_READINESS_BOOL_FIELDS = {
    "candidate_manifest_exported",
    "candidate_manifest_created",
    "candidate_manifest_jsonl_created",
    "candidate_validation_jsonl_created",
    "db_or_production_namespace_written",
    "dry_run_execution_plan_exported",
    "dry_run_input_manifest_exported",
    "fine_tuning_dataset_export_created",
    "fine_tuning_executed",
    "fine_tuning_started",
    "ft_route_policy_dry_run_executed",
    "ft_route_policy_dry_run_opened",
    "live_db_index_cache_readiness",
    "model_or_adapter_checkpoint_written",
    "official_metric",
    "official_metric_lift",
    "production_mutation",
    "production_routing",
    "product_success_evidence_allowed",
    "promotion_evidence",
    "prompt_manifest_created",
    "prompt_payload_created",
    "raw_candidate_rows_embedded",
    "raw_llm_response_payload_created",
    "raw_local_path_values_exposed",
    "raw_runtime_request_body_embedded",
    "raw_runtime_response_body_embedded",
    "raw_source_identity_values_embedded",
    "raw_prompt_text_embedded",
    "review_csv_created",
    "review_packet_created",
    "source_identity_audit_jsonl_created",
    "threshold_tuning",
    "training_job_created",
    "training_manifest_jsonl_created",
    "v4_7_official_metric_gate_opened",
    "winner_selection",
}
HAZARDOUS_READINESS_NONZERO_FIELDS = {
    "fine_tuning_dataset_exports_created",
    "official_metric_input_rows",
    "official_metric_rows_created",
}
LEGACY_READINESS_WARNING_STATUS_PREFIX = "V4_6_READINESS_REPORT"
LEGACY_READINESS_WARNING_REASON_PREFIX = "v4_6_readiness_report"
LOCAL_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|//|/(?:data|home|mnt|opt|private|repo|tmp|Users|var|workspace)(?:/|$))",
    re.IGNORECASE,
)
DIAGNOSTIC_HTTP_HASH_FIELD_NAMES = {
    "document_id",
    "document_version_id",
    "file_id",
    "file_name",
    "source_corpus_path",
    "source_document_id",
    "source_identity",
    "source_path",
    "source_pdf_path",
    "workbook",
    "workbook_id",
    "workbook_or_source_path",
}
DIAGNOSTIC_HTTP_DROP_FIELD_NAMES = {
    "raw_locator",
    "source_identity_key",
    "track_locator_payload",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (_clean(value),) if _clean(value) else ()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(_clean(item) for item in value if _clean(item))
    return ()


def _public_hash(value: Any) -> str:
    cleaned = _clean(value)
    return _sha256(cleaned) if cleaned else ""


def _sanitize_diagnostic_http_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        payload: dict[str, Any] = {}
        for raw_key, raw_child in value.items():
            key = str(raw_key)
            if key in DIAGNOSTIC_HTTP_DROP_FIELD_NAMES:
                continue
            if key in DIAGNOSTIC_HTTP_HASH_FIELD_NAMES:
                child_hash = _public_hash(raw_child)
                if child_hash:
                    payload[f"{key}_hash"] = child_hash
                continue
            payload[key] = _sanitize_diagnostic_http_payload(raw_child)
        return payload
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_diagnostic_http_payload(item) for item in value]
    if isinstance(value, str) and LOCAL_PATH_RE.search(value.replace("\\", "/")):
        return "__local_path_redacted__"
    return value


def _readiness_report_contract_violations(report: Mapping[str, Any]) -> list[str]:
    metrics = _as_mapping(report.get("metrics"))
    guardrails = _as_mapping(report.get("guardrails") or report.get("guardrail_audit"))
    violations: list[str] = []
    for field in HAZARDOUS_READINESS_BOOL_FIELDS:
        if bool(report.get(field) or metrics.get(field) or guardrails.get(field)):
            violations.append(f"{field}_not_allowed")
    for field in HAZARDOUS_READINESS_NONZERO_FIELDS:
        if _first_nonzero_numeric_value(report.get(field), metrics.get(field), guardrails.get(field)):
            violations.append(f"{field}_nonzero")
    for field in _nested_hazardous_true_fields(report):
        violations.append(f"{field}_not_allowed")
    for field in _nested_hazardous_nonzero_fields(report):
        violations.append(f"{field}_nonzero")
    violations.extend(_v4_6_10_replay_contract_violations(report))
    violations.extend(_v4_6_12_route_parity_contract_violations(report))
    if _contains_forbidden_readiness_surface(report):
        violations.append("readiness_report_contains_forbidden_debug_or_path_surface")
    return sorted(set(violations))


def _first_nonzero_numeric_value(*values: Any) -> bool:
    for value in values:
        try:
            if int(value or 0) != 0:
                return True
        except (TypeError, ValueError):
            return True
    return False


def _nested_hazardous_true_fields(value: Any) -> set[str]:
    fields: set[str] = set()
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            key = str(child_key)
            if key in HAZARDOUS_READINESS_BOOL_FIELDS and bool(child_value):
                fields.add(key)
            fields.update(_nested_hazardous_true_fields(child_value))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            fields.update(_nested_hazardous_true_fields(item))
    return fields


def _nested_hazardous_nonzero_fields(value: Any) -> set[str]:
    fields: set[str] = set()
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            key = str(child_key)
            if key in HAZARDOUS_READINESS_NONZERO_FIELDS and _first_nonzero_numeric_value(child_value):
                fields.add(key)
            fields.update(_nested_hazardous_nonzero_fields(child_value))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            fields.update(_nested_hazardous_nonzero_fields(item))
    return fields


def _v4_6_10_replay_contract_violations(report: Mapping[str, Any]) -> list[str]:
    replay = _as_mapping(report.get("external_holdout_candidate_manifest_gate_replay"))
    if not replay:
        return []
    metrics = _as_mapping(report.get("metrics"))
    manifest_input = _as_mapping(replay.get("candidate_manifest_input"))
    violations: list[str] = []
    replay_present = bool(replay.get("candidate_manifest_present"))
    try:
        rows_replayed = int(replay.get("candidate_rows_replayed") or 0)
    except (TypeError, ValueError):
        rows_replayed = -1
    if replay_present and rows_replayed <= 0:
        violations.append("v4_6_10_candidate_rows_replayed_inconsistent")
    if not replay_present and rows_replayed != 0:
        violations.append("v4_6_10_candidate_rows_replayed_inconsistent")
    for source_name, source in (("top_level", report), ("metrics", metrics)):
        if "candidate_manifest_present" in source and bool(source.get("candidate_manifest_present")) != replay_present:
            violations.append(f"v4_6_10_{source_name}_candidate_manifest_present_mismatch")
    if "candidate_rows_replayed" in metrics:
        try:
            metric_rows = int(metrics.get("candidate_rows_replayed") or 0)
        except (TypeError, ValueError):
            metric_rows = -1
        if metric_rows != rows_replayed:
            violations.append("v4_6_10_metrics_candidate_rows_replayed_mismatch")
    if manifest_input.get("raw_local_path_exposed") is True:
        violations.append("v4_6_10_candidate_manifest_input_raw_local_path_exposed")
    if manifest_input.get("provided") is True and manifest_input.get("path_kind") not in {
        "external_redacted",
        "repo_relative",
    }:
        violations.append("v4_6_10_candidate_manifest_input_path_kind_invalid")
    return violations


def _v4_6_12_route_parity_contract_violations(report: Mapping[str, Any]) -> list[str]:
    parity = _as_mapping(report.get("external_holdout_runtime_replay_route_parity"))
    if not parity:
        return []
    metrics = _as_mapping(report.get("metrics"))
    violations: list[str] = []
    if report.get("external_holdout_runtime_replay_route_parity_only") is not True:
        violations.append("v4_6_12_route_parity_only_missing")
    if not bool(report.get("runtime_parity_probe_only") or metrics.get("runtime_parity_probe_only")):
        violations.append("v4_6_12_runtime_parity_probe_only_missing")
    if bool(parity.get("feature_flag_default_enabled")):
        violations.append("v4_6_12_feature_flag_default_enabled")
    if bool(parity.get("production_orchestrator_mode_enabled")):
        violations.append("v4_6_12_production_orchestrator_mode_enabled")
    if parity.get("route_path") not in {None, "", HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH}:
        violations.append("v4_6_12_route_path_unexpected")
    for field in (
        "route_candidate_counts_match_v4_6_10_replay",
        "route_source_identity_audit_matches_v4_6_10_replay",
        "route_response_sanitized",
        "enabled_validation_error_raw_input_redacted",
        "route_rejects_prompt_path_metric_and_readiness_fields",
        "transient_external_manifest_deleted",
    ):
        if parity.get(field) is not True or (field in metrics and metrics.get(field) is not True):
            violations.append(f"v4_6_12_{field}_false")
    if "route_response_sanitized" in parity and parity.get("route_response_sanitized") is not True:
        violations.append("v4_6_12_route_response_not_sanitized")
    if "route_response_sanitized" in metrics and metrics.get("route_response_sanitized") is not True:
        violations.append("v4_6_12_route_response_not_sanitized")
    if parity.get("transient_external_manifest_persisted_in_repo") is True:
        violations.append("v4_6_12_transient_external_manifest_persisted_in_repo")
    if _clean(parity.get("feature_flag_name")) not in {"", FEATURE_FLAG_NAME}:
        violations.append("v4_6_12_feature_flag_name_unexpected")
    for field, expected in (
        ("disabled_route_status_code", 404),
        ("production_disabled_route_status_code", 404),
        ("enabled_target_sufficient_status_code", 200),
        ("enabled_validation_error_status_code", 422),
    ):
        if field in parity:
            try:
                if int(parity.get(field) or 0) != expected:
                    violations.append(f"v4_6_12_{field}_unexpected")
            except (TypeError, ValueError):
                violations.append(f"v4_6_12_{field}_unexpected")
    return violations


def _contains_forbidden_readiness_surface(value: Any, *, key: str = "") -> bool:
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            if str(child_key) in FORBIDDEN_READINESS_DEBUG_KEYS:
                return True
            if _contains_forbidden_readiness_surface(child_value, key=str(child_key)):
                return True
        return False
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_forbidden_readiness_surface(item, key=key) for item in value)
    if isinstance(value, str):
        return bool(LOCAL_PATH_RE.search(value.replace("\\", "/")))
    return False


def _project_holdout_gap_ledger(ledger: Mapping[str, Any]) -> dict[str, Any]:
    safe_keys = (
        "accepted_pdf_holdout_candidates",
        "accepted_xlsx_holdout_candidates",
        "candidate_manifest_exported",
        "candidate_manifest_present",
        "real_holdout_available",
        "real_holdout_sufficient",
        "source_counts",
        "query_fidelity_included_counts",
        "deficits",
        "minimum_targets",
        "acquisition_requirements",
    )
    return {key: ledger[key] for key in safe_keys if key in ledger}


def _project_dry_run_blocker_ledger(ledger: Mapping[str, Any]) -> dict[str, Any]:
    safe_keys = (
        "all_non_gold_source_gates_passed",
        "dry_run_blocker_count",
        "dry_run_execution_plan_exported",
        "dry_run_input_manifest_exported",
        "ft_route_policy_dry_run_opened",
        "ft_route_policy_dry_run_executed",
        "source_gate_state",
        "non_gold_next_actions",
        "user_owned_next_actions",
        "user_owned_policy_gate_ready",
        "v4_7_official_metric_gate_opened",
    )
    return {key: ledger[key] for key in safe_keys if key in ledger}


def _project_candidate_manifest_input(metadata: Mapping[str, Any]) -> dict[str, Any]:
    safe_keys = (
        "provided",
        "exists",
        "format",
        "path_label",
        "path_kind",
        "sha256",
        "rows_loaded",
        "load_error",
        "raw_local_path_exposed",
        "input_only_replay",
    )
    payload = {key: metadata[key] for key in safe_keys if key in metadata}
    if payload.get("provided") is True:
        payload["path_label"] = "__external_candidate_manifest_path_redacted__"
        payload["path_kind"] = "external_redacted"
    payload["raw_local_path_exposed"] = False
    return payload


def _project_external_holdout_manifest_gate_replay(replay: Mapping[str, Any]) -> dict[str, Any]:
    if not replay:
        return {}
    safe_keys = (
        "external_holdout_candidate_manifest_gate_replay_only",
        "candidate_manifest_input_only",
        "candidate_manifest_present",
        "candidate_rows_replayed",
        "candidate_gate_target_sufficient",
        "source_reports_closed",
        "codex_owned_dependency_checks_passed",
        "v4_5_1_intake_gate_passed",
        "v4_5_2_source_identity_audit_gate_passed",
        "v4_6_9_duplicate_hygiene_gate_passed",
        "source_identity_collision_count",
        "source_identity_audit_excluded_count",
        "candidate_intake_exclusion_reasons",
        "source_identity_audit_exclusion_reasons",
        "real_holdout_sufficient",
        "candidate_manifest_exported",
        "dry_run_input_manifest_exported",
        "ft_route_policy_dry_run_opened",
        "ft_route_policy_dry_run_executed",
        "v4_7_official_metric_gate_opened",
        "official_metric_input_rows",
        "promotion_evidence",
        "product_success_evidence_allowed",
    )
    payload = {key: replay[key] for key in safe_keys if key in replay}
    payload["candidate_manifest_input"] = _project_candidate_manifest_input(
        _as_mapping(replay.get("candidate_manifest_input"))
    )
    return payload


def _project_external_holdout_runtime_replay_route_parity(parity: Mapping[str, Any]) -> dict[str, Any]:
    if not parity:
        return {}
    safe_keys = (
        "schema_version",
        "run_id",
        "feature_flag_default_enabled",
        "feature_flag_name",
        "disabled_route_status_code",
        "production_disabled_route_status_code",
        "production_orchestrator_mode_enabled",
        "enabled_target_sufficient_status_code",
        "enabled_validation_error_status_code",
        "enabled_validation_error_raw_input_redacted",
        "probe_candidate_row_count",
        "route_path",
        "route_candidate_counts_match_v4_6_10_replay",
        "route_source_identity_audit_matches_v4_6_10_replay",
        "route_response_sanitized",
        "route_rejects_prompt_path_metric_and_readiness_fields",
        "route_candidate_intake_gate_passed",
        "route_source_identity_audit_gate_passed",
        "route_candidate_intake_snapshot",
        "route_source_identity_audit_snapshot",
        "transient_external_manifest_deleted",
        "transient_external_manifest_persisted_in_repo",
        "v4_6_10_replay_candidate_manifest_present",
        "v4_6_10_replay_candidate_rows_replayed",
        "v4_6_10_replay_candidate_gate_target_sufficient",
        "v4_6_10_replay_real_holdout_sufficient",
        "official_metric_input_rows",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
    )
    return {key: parity[key] for key in safe_keys if key in parity}


@dataclass(frozen=True)
class XlsxDisplayContract:
    raw_value: str = ""
    normalized_value: str = ""
    display_value: str | None = ""
    number_format: str = ""
    value_type: str = ""
    formula_cached_value: str = ""
    formula_text_visible_to_user: bool = False
    formula_evaluation_at_query_time: bool = False
    format_confidence: str = "high"
    format_provenance: str = "source_atom_materialized_xlsx_display_metadata_v1"
    format_drop_reason: str = ""
    merged_cell: bool = False
    merged_range: str = ""
    merged_owner_cell: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["display_value"] is None:
            payload["display_value"] = ""
            payload["format_confidence"] = "low"
            payload["format_drop_reason"] = "FORMAT_METADATA_UNAVAILABLE"
            payload["format_provenance"] = ""
        return payload


class RagDiagnosticQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    source_family: Literal["PDF", "XLSX", "TEXT"] | None = None
    file_id: str | None = None
    source_identity: str | None = None
    workbook_id: str | None = None
    sheet_name: str | None = None
    cell: str | None = None
    range: str | None = None
    page: int | None = None
    active_context: dict[str, Any] | None = None
    tenant_id: str | None = None
    debug: bool = False

    model_config = {"extra": "forbid"}


class RagDiagnosticQueryResponse(BaseModel):
    diagnostic_only: bool = True
    answer_allowed_by_policy: bool
    response_policy_bucket: str
    final_answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_bundles: list[dict[str, Any]] = Field(default_factory=list)
    selected_source_atom_ids: list[str] = Field(default_factory=list)
    selected_search_view_ids: list[str] = Field(default_factory=list)
    search_view_candidate_metadata_only: bool = True
    evidence_truth_source: str
    xlsx_range_rendering_mode: str
    fail_closed_reason: str
    warnings: list[str] = Field(default_factory=list)
    request_id: str
    run_id: str = PHASE1_V3_22_RUN_ID
    official_metric_input_rows: int = 0
    promotion_evidence: bool = False
    product_success_evidence_allowed: bool = False
    live_db_index_cache_readiness: bool = False
    llm_invoked: bool = False
    vector_payload_used_as_evidence_truth: bool = False
    formula_text_visible_to_user: bool = False
    formula_evaluation_at_query_time: bool = False


class RagDiagnosticReadinessResponse(BaseModel):
    diagnostic_only: bool = True
    readiness_report_available: bool
    readiness_source: str
    run_id: str
    status: str
    v4_name: str = V4_READINESS_NAME
    run_family: str = V4_READINESS_RUN_FAMILY
    ft_route_policy_dry_run_preflight_only: bool = True
    all_preflight_gates_passed: bool = False
    ft_route_policy_dry_run_opened: bool = False
    ft_route_policy_dry_run_executed: bool = False
    fine_tuning_dataset_exports_created: int = 0
    training_job_created: bool = False
    model_or_adapter_checkpoint_written: bool = False
    preflight_gates: dict[str, Any] = Field(default_factory=dict)
    source_report_inputs: dict[str, Any] = Field(default_factory=dict)
    holdout_gap_and_dry_run_blocker_ledger_only: bool = False
    holdout_gap_ledger: dict[str, Any] = Field(default_factory=dict)
    dry_run_blocker_ledger: dict[str, Any] = Field(default_factory=dict)
    external_holdout_candidate_manifest_gate_replay_only: bool = False
    candidate_manifest_input_only: bool = False
    candidate_manifest_input: dict[str, Any] = Field(default_factory=dict)
    candidate_rows_replayed: int = 0
    external_holdout_runtime_replay_route_parity_only: bool = False
    runtime_parity_probe_only: bool = False
    external_holdout_runtime_replay_route_parity: dict[str, Any] = Field(default_factory=dict)
    candidate_rows_replayed_in_probe: int = 0
    route_path: str = ""
    route_candidate_counts_match_v4_6_10_replay: bool = False
    route_source_identity_audit_matches_v4_6_10_replay: bool = False
    route_response_sanitized: bool = False
    enabled_validation_error_raw_input_redacted: bool = False
    route_rejects_prompt_path_metric_and_readiness_fields: bool = False
    transient_external_manifest_deleted: bool = False
    transient_external_manifest_persisted_in_repo: bool = False
    candidate_gate_target_sufficient: bool = False
    source_reports_closed: bool = False
    codex_owned_dependency_checks_passed: bool = False
    v4_5_1_intake_gate_passed: bool = False
    v4_5_2_source_identity_audit_gate_passed: bool = False
    v4_6_9_duplicate_hygiene_gate_passed: bool = False
    official_metric_opening_preflight_gate_passed: bool = False
    official_metric_opening_preflight_gate_opened: bool = False
    official_metric_rows_authorized: bool = False
    missing_user_owned_input_count: int = 0
    single_report_artifact_contract: bool = False
    source_identity_collision_count: int = 0
    source_identity_audit_excluded_count: int = 0
    candidate_intake_exclusion_reasons: dict[str, int] = Field(default_factory=dict)
    source_identity_audit_exclusion_reasons: dict[str, int] = Field(default_factory=dict)
    candidate_manifest_exported: bool = False
    candidate_manifest_jsonl_created: bool = False
    candidate_validation_jsonl_created: bool = False
    source_identity_audit_jsonl_created: bool = False
    candidate_manifest_present: bool = False
    real_holdout_available: bool = False
    real_holdout_sufficient: bool = False
    dry_run_execution_plan_exported: bool = False
    dry_run_input_manifest_exported: bool = False
    user_owned_policy_gate_ready: bool = False
    v4_7_official_metric_gate_opened: bool = False
    dry_run_blocker_count: int = 0
    accepted_pdf_holdout_candidates: int = 0
    accepted_xlsx_holdout_candidates: int = 0
    pdf_source_document_disjoint_needed: int = 0
    xlsx_workbook_disjoint_needed: int = 0
    pdf_query_fidelity_rows_needed: int = 0
    xlsx_query_fidelity_rows_needed: int = 0
    gpu_required_for_future_training_when_opened: bool = False
    gpu_required_for_this_slice: bool = False
    readiness_decision: str = ""
    blocked_reasons: list[str] = Field(default_factory=list)
    official_metric_input_rows: int = 0
    official_metric: bool = False
    promotion_evidence: bool = False
    product_success_evidence_allowed: bool = False
    live_db_index_cache_readiness: bool = False
    source_atom_evidence_bundle_evidence_truth: bool = True
    searchview_vector_payload_candidate_only: bool = True
    vector_payload_used_as_evidence_truth: bool = False
    holdout_candidate_manifest_contract: dict[str, Any] = Field(
        default_factory=build_holdout_candidate_manifest_contract
    )
    holdout_acquisition_requirements: dict[str, Any] = Field(default_factory=dict)
    protected_namespaces_touched: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    model_config = {"protected_namespaces": ()}


class RagHoldoutCandidateValidationRequest(BaseModel):
    schema_version: Literal["v4_holdout_candidate_manifest_contract_v1"] = "v4_holdout_candidate_manifest_contract_v1"
    request_id: str | None = None
    candidate_rows: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    prior_identity_hash_records: list[dict[str, Any] | str] = Field(default_factory=list, max_length=5000)

    model_config = {"extra": "forbid"}


class RagHoldoutCandidateValidationResponse(BaseModel):
    diagnostic_only: bool = True
    holdout_candidate_manifest_validation_only: bool = True
    v4_name: str
    run_family: str
    schema_version: str
    contract_hash_algorithm: str
    contract_hash: str
    holdout_candidate_manifest_contract: dict[str, Any] = Field(default_factory=dict)
    candidate_manifest_present: bool
    candidate_manifest_rows: int
    candidate_intake_gate: dict[str, Any]
    source_identity_audit_gate: dict[str, Any]
    accepted_candidate_count: int
    excluded_candidate_count: int
    accepted_candidates: list[dict[str, Any]] = Field(default_factory=list)
    excluded_candidates: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str
    candidate_manifest_jsonl_created: bool = False
    candidate_validation_jsonl_created: bool = False
    source_identity_audit_jsonl_created: bool = False
    fine_tuning_dataset_export_created: bool = False
    fine_tuning_dataset_exports_created: int = 0
    training_job_created: bool = False
    model_or_adapter_checkpoint_written: bool = False
    official_metric: bool = False
    official_metric_input_rows: int = 0
    promotion_evidence: bool = False
    product_success_evidence_allowed: bool = False
    live_db_index_cache_readiness: bool = False
    db_or_production_namespace_written: bool = False
    protected_namespaces_touched: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    model_config = {"protected_namespaces": ()}


class RagFtADryRunInputValidationRequest(BaseModel):
    schema_version: Literal[
        "v4_6_4_ft_a_dry_run_input_manifest_validation_request_v1"
    ] = FT_A_DRY_RUN_INPUT_VALIDATION_REQUEST_VERSION
    request_id: str | None = None
    manifest_rows: list[dict[str, Any]] = Field(default_factory=list, max_length=500)

    model_config = {"extra": "forbid"}


class RagFtADryRunInputValidationResponse(BaseModel):
    diagnostic_only: bool = True
    ft_a_dry_run_input_manifest_validator_only: bool = True
    v4_name: str
    run_family: str
    schema_version: str
    run_id: str
    dry_run_input_manifest_contract: dict[str, Any] = Field(default_factory=dict)
    dry_run_input_manifest_validation: dict[str, Any] = Field(default_factory=dict)
    manifest_row_count: int
    accepted_manifest_row_count: int
    excluded_manifest_row_count: int
    gold_or_prompt_or_output_rejection_count: int
    dry_run_input_manifest_gate_passed: bool = False
    request_id: str
    manifest_rows_exported: bool = False
    prompt_payload_created: bool = False
    prompt_manifest_created: bool = False
    raw_prompt_text_embedded: bool = False
    raw_llm_response_payload_created: bool = False
    fine_tuning_dataset_export_created: bool = False
    fine_tuning_dataset_exports_created: int = 0
    training_job_created: bool = False
    model_or_adapter_checkpoint_written: bool = False
    official_metric: bool = False
    official_metric_input_rows: int = 0
    promotion_evidence: bool = False
    product_success_evidence_allowed: bool = False
    live_db_index_cache_readiness: bool = False
    db_or_production_namespace_written: bool = False
    protected_namespaces_touched: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    model_config = {"protected_namespaces": ()}


def cell_ref_to_row_col(cell: str) -> tuple[int, int] | None:
    match = re.match(r"^([A-Z]{1,3})([1-9][0-9]*)$", _clean(cell).upper())
    if not match:
        return None
    col_text, row_text = match.groups()
    col = 0
    for char in col_text:
        col = col * 26 + (ord(char) - ord("A") + 1)
    return int(row_text), col


def range_shape(range_text: str) -> tuple[int, int, int]:
    match = re.match(r"^([A-Z]{1,3})([1-9][0-9]*):([A-Z]{1,3})([1-9][0-9]*)$", _clean(range_text).upper())
    if not match:
        return (1, 1, 1)

    def col_num(col: str) -> int:
        value = 0
        for char in col:
            value = value * 26 + (ord(char) - ord("A") + 1)
        return value

    left_col, top_row, right_col, bottom_row = match.groups()
    rows = int(bottom_row) - int(top_row) + 1
    cols = col_num(right_col) - col_num(left_col) + 1
    return rows, cols, max(rows, 0) * max(cols, 0)


def explicit_query_range_area(query: str) -> int | None:
    match = re.search(r"\b([A-Z]{1,3}[1-9][0-9]*:[A-Z]{1,3}[1-9][0-9]*)\b", _clean(query).upper())
    if not match:
        return None
    _rows, _cols, area = range_shape(match.group(1))
    return area


def determine_xlsx_range_mode_from_request(
    *,
    requested_range: str | None,
    selected_source_atoms: Sequence[Mapping[str, Any]],
) -> str:
    range_text = _clean(requested_range)
    if range_text:
        _rows, _cols, area = range_shape(range_text)
        if area > BOUNDED_SUMMARY_MAX_CELLS:
            return "UNSUPPORTED_RANGE_TOO_LARGE"
        if area <= SMALL_RANGE_MAX_CELLS:
            return "SINGLE_CELL_VALUE" if len(selected_source_atoms) == 1 and area == 1 else "SMALL_RANGE_TABLE"
        return "BOUNDED_RANGE_SUMMARY"
    if not selected_source_atoms:
        return "FORMAT_METADATA_UNAVAILABLE"
    if len(selected_source_atoms) == 1:
        locator = _as_mapping(selected_source_atoms[0].get("raw_locator"))
        atom_range = _clean(locator.get("range") or locator.get("cell"))
        _rows, _cols, area = range_shape(atom_range)
        return "UNSUPPORTED_RANGE_TOO_LARGE" if area > BOUNDED_SUMMARY_MAX_CELLS else "SINGLE_CELL_VALUE"

    cells = [cell_ref_to_row_col(_clean(_as_mapping(atom.get("raw_locator")).get("cell"))) for atom in selected_source_atoms]
    points = [point for point in cells if point is not None]
    if not points:
        return "FORMAT_METADATA_UNAVAILABLE"
    rows = [row for row, _col in points]
    cols = [col for _row, col in points]
    span_area = (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1)
    if span_area <= SMALL_RANGE_MAX_CELLS and len(selected_source_atoms) <= SMALL_RANGE_MAX_CELLS:
        return "SMALL_RANGE_TABLE"
    if span_area <= BOUNDED_SUMMARY_MAX_CELLS:
        return "BOUNDED_RANGE_SUMMARY"
    return "UNSUPPORTED_RANGE_TOO_LARGE"


def render_xlsx_display_value(
    selected_source_atoms: Sequence[Mapping[str, Any]],
    *,
    requested_range: str | None = None,
) -> dict[str, Any]:
    mode = determine_xlsx_range_mode_from_request(
        requested_range=requested_range,
        selected_source_atoms=selected_source_atoms,
    )
    if mode == "UNSUPPORTED_RANGE_TOO_LARGE":
        return {
            **empty_display_contract(),
            "rendered_value": "",
            "xlsx_range_rendering_mode": mode,
            "fail_closed_reason": "UNSUPPORTED_RANGE_TOO_LARGE",
        }
    contracts = [_display_contract_from_atom(atom) for atom in selected_source_atoms]
    if not contracts:
        return {
            **empty_display_contract(),
            "rendered_value": "",
            "xlsx_range_rendering_mode": mode,
        }
    first = dict(contracts[0])
    if mode == "SMALL_RANGE_TABLE":
        lines = ["| Cell | Display value |", "| --- | --- |"]
        for atom in sorted(selected_source_atoms, key=_sort_atom_cell_key):
            locator = _as_mapping(atom.get("raw_locator"))
            contract = _display_contract_from_atom(atom)
            value = _contract_rendered_value(contract)
            lines.append(f"| {_clean(locator.get('cell'))} | {value} |")
        rendered = "\n".join(lines)
        return {
            **first,
            "rendered_value": rendered,
            "display_value": rendered,
            "value_type": "small_range_table",
            "xlsx_range_rendering_mode": mode,
            "formula_cached_value_used": False,
            "formula_text_visible_to_user": False,
            "formula_evaluation_at_query_time": False,
        }
    if mode == "BOUNDED_RANGE_SUMMARY":
        examples: list[str] = []
        for atom in sorted(selected_source_atoms, key=_sort_atom_cell_key):
            locator = _as_mapping(atom.get("raw_locator"))
            examples.append(f"{_clean(locator.get('cell'))}={_contract_rendered_value(_display_contract_from_atom(atom))}")
        range_text = _clean(requested_range) or _clean(_as_mapping(selected_source_atoms[0].get("raw_locator")).get("range"))
        rendered = (
            f"bounded_range={range_text}; materialized_cell_count={len(selected_source_atoms)}; "
            f"shown_examples={', '.join(examples)}"
        )
        return {
            **first,
            "rendered_value": rendered,
            "display_value": rendered,
            "value_type": "bounded_range_summary",
            "xlsx_range_rendering_mode": mode,
            "formula_cached_value_used": False,
            "formula_text_visible_to_user": False,
            "formula_evaluation_at_query_time": False,
        }
    formula_cached_value_used = bool(_clean(first.get("formula_cached_value"))) or _clean(first.get("value_type")).casefold() == "formula"
    rendered = _contract_rendered_value(first)
    return {
        **first,
        "rendered_value": rendered,
        "display_value": rendered,
        "xlsx_range_rendering_mode": mode,
        "formula_cached_value_used": formula_cached_value_used,
        "formula_text_visible_to_user": False,
        "formula_evaluation_at_query_time": False,
    }


def empty_display_contract() -> dict[str, Any]:
    return {
        "raw_value": "",
        "normalized_value": "",
        "display_value": "",
        "number_format": "",
        "value_type": "",
        "formula_cached_value": "",
        "formula_text_visible_to_user": False,
        "formula_evaluation_at_query_time": False,
        "format_confidence": "low",
        "format_provenance": "",
        "format_drop_reason": "NO_SELECTED_XLSX_SOURCEATOM",
        "merged_cell": False,
        "merged_range": "",
        "merged_owner_cell": "",
    }


def build_diagnostic_xlsx_source_atom(
    source_atom_id: str,
    *,
    workbook: str,
    sheet: str,
    cell: str,
    cell_range: str,
    display_contract: XlsxDisplayContract,
    tenant_id: str = "diagnostic-local",
) -> dict[str, Any]:
    contract = display_contract.to_payload()
    rendered = _contract_rendered_value(contract)
    source_identity = f"XLSX:{workbook}:{sheet}:{cell_range or cell}"
    raw_locator = {
        "workbook": workbook,
        "file_name": workbook,
        "sheet": sheet,
        "cell": cell,
        "range": cell_range or cell,
        "tenant_id": tenant_id,
        "value_locator": cell,
    }
    payload = {
        "source_family": "XLSX",
        "source_identity": source_identity,
        "locator_fingerprint": f"fp:{source_atom_id}",
        "search_unit_id": f"su:{source_atom_id}",
        "workbook": workbook,
        "sheet": sheet,
        "range": cell_range or cell,
        "cell": cell,
        "normalized_value": _clean(contract.get("normalized_value")) or rendered,
    }
    return {
        "source_atom_id": source_atom_id,
        "source_family": "XLSX",
        "source_identity": source_identity,
        "workbook_id": f"wb:{workbook}",
        "workbook_version_id": f"wb:{workbook}:v1",
        "tenant_id": tenant_id,
        "content_hash": _sha256(f"{source_atom_id}|{rendered}"),
        "extraction_version": "phase1-fastapi-diagnostic-v1",
        "raw_locator": raw_locator,
        "normalized_text_or_value_snapshot": rendered,
        "parent_pointers": {"diagnostic_runtime": True},
        "canonical_citation_payload": payload,
        "source_registry_version": SOURCE_REGISTRY_CONTRACT_VERSION,
        "raw_file_exists": False,
        "extraction_snapshot_present": True,
        "runtime_replay_atom": True,
        "xlsx_display_contract": contract,
    }


class SourceFirstRagService:
    """Diagnostic-only service wrapper around the existing AgentRuntime."""

    def __init__(
        self,
        *,
        source_atoms: Sequence[Mapping[str, Any]] = (),
        llm_invoker: Callable[[dict[str, object]], str] | None = None,
        index_available: bool = False,
        source_atom_store_available: bool = True,
        namespace: str = DIAGNOSTIC_NAMESPACE,
        readiness_report: Mapping[str, Any] | None = None,
        readiness_report_path: Path | None = None,
    ) -> None:
        self.source_atoms = {_clean(atom.get("source_atom_id")): dict(atom) for atom in source_atoms if _clean(atom.get("source_atom_id"))}
        self.search_views = {
            f"sv:{atom_id}": _search_view_for_atom(atom_id, atom)
            for atom_id, atom in self.source_atoms.items()
        }
        self.llm_invoker = llm_invoker
        self.namespace = namespace
        self.readiness_report = dict(readiness_report) if readiness_report is not None else None
        self.readiness_report_path = readiness_report_path or DEFAULT_V4_READINESS_REPORT
        self.runtime = AgentRuntime(
            search_index=InMemorySearchIndexAdapter(
                search_views=self.search_views,
                namespace=namespace,
                available=index_available,
            ),
            source_atom_store=InMemorySourceAtomStoreAdapter(
                source_atoms=self.source_atoms,
                namespace=namespace,
                available=source_atom_store_available,
            ),
        )

    def validate_holdout_candidates(
        self,
        request: RagHoldoutCandidateValidationRequest,
    ) -> RagHoldoutCandidateValidationResponse:
        validation = validate_holdout_candidate_rows_for_fastapi(
            request.candidate_rows,
            prior_identity_hash_records=request.prior_identity_hash_records,
        )
        request_id = request.request_id or _sha256(
            json.dumps(
                {
                    "candidate_rows": request.candidate_rows,
                    "prior_identity_hash_records": request.prior_identity_hash_records,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )[:16]
        return RagHoldoutCandidateValidationResponse(**validation, request_id=request_id)

    def validate_ft_a_dry_run_input_manifest(
        self,
        request: RagFtADryRunInputValidationRequest,
    ) -> RagFtADryRunInputValidationResponse:
        validation = validate_ft_a_dry_run_input_manifest_rows_for_fastapi(request.manifest_rows)
        request_id = request.request_id or _sha256(
            json.dumps(
                {"manifest_rows": request.manifest_rows},
                ensure_ascii=False,
                sort_keys=True,
            )
        )[:16]
        return RagFtADryRunInputValidationResponse(**validation, request_id=request_id)

    def readiness(self) -> RagDiagnosticReadinessResponse:
        report = self._load_readiness_report()
        if not report:
            return RagDiagnosticReadinessResponse(
                readiness_report_available=False,
                readiness_source=repo_relative_or_name(self.readiness_report_path),
                run_id=V4_6_PREFLIGHT_RUN_ID,
                status="V4_6_READINESS_REPORT_UNAVAILABLE",
                blocked_reasons=["v4_6_readiness_report_missing"],
                official_metric_input_rows=0,
                promotion_evidence=False,
                product_success_evidence_allowed=False,
                live_db_index_cache_readiness=False,
                warnings=[
                    "diagnostic_readiness_failed_closed",
                    "not_production_routing",
                    "no_live_db_index_cache_readiness_claim",
                ],
            )

        contract_violations = _readiness_report_contract_violations(report)
        if contract_violations:
            return RagDiagnosticReadinessResponse(
                readiness_report_available=False,
                readiness_source=repo_relative_or_name(self.readiness_report_path),
                run_id=V4_6_PREFLIGHT_RUN_ID,
                status="V4_6_READINESS_REPORT_CONTRACT_VIOLATION",
                blocked_reasons=[
                    "v4_6_readiness_report_contract_violation",
                    *contract_violations,
                ],
                official_metric_input_rows=0,
                official_metric=False,
                promotion_evidence=False,
                product_success_evidence_allowed=False,
                live_db_index_cache_readiness=False,
                ft_route_policy_dry_run_opened=False,
                ft_route_policy_dry_run_executed=False,
                fine_tuning_dataset_exports_created=0,
                training_job_created=False,
                model_or_adapter_checkpoint_written=False,
                preflight_gates={},
                source_report_inputs={},
                warnings=[
                    "diagnostic_readiness_failed_closed",
                    "readiness_report_contract_violation",
                    "not_production_routing",
                    "no_live_db_index_cache_readiness_claim",
                ],
        )

        metrics = _as_mapping(report.get("metrics"))
        guardrails = _as_mapping(report.get("guardrails") or report.get("guardrail_audit"))
        raw_holdout_gap_ledger = dict(_as_mapping(report.get("holdout_gap_ledger")))
        raw_dry_run_blocker_ledger = dict(_as_mapping(report.get("dry_run_blocker_ledger")))
        manifest_gate_replay = _project_external_holdout_manifest_gate_replay(
            _as_mapping(report.get("external_holdout_candidate_manifest_gate_replay"))
        )
        route_parity = _project_external_holdout_runtime_replay_route_parity(
            _as_mapping(report.get("external_holdout_runtime_replay_route_parity"))
        )
        official_metric_preflight = _as_mapping(report.get("official_metric_opening_preflight"))
        holdout_gap_ledger = _project_holdout_gap_ledger(raw_holdout_gap_ledger)
        dry_run_blocker_ledger = _project_dry_run_blocker_ledger(raw_dry_run_blocker_ledger)
        holdout_deficits = _as_mapping(raw_holdout_gap_ledger.get("deficits"))
        holdout_acquisition_requirements = build_holdout_acquisition_requirements(
            deficits=holdout_deficits,
            accepted_source_counts=_as_mapping(raw_holdout_gap_ledger.get("source_counts")),
            query_fidelity_included_counts=_as_mapping(raw_holdout_gap_ledger.get("query_fidelity_included_counts")),
            non_gold_next_actions=_as_sequence(raw_holdout_gap_ledger.get("acquisition_requirements")),
            user_owned_next_actions=_as_sequence(raw_dry_run_blocker_ledger.get("user_owned_next_actions")),
            blocked_reasons=_as_sequence(report.get("blocked_reasons")),
            readiness_decision=_clean(report.get("readiness_decision"))
            or "blocked_pending_real_external_holdout_candidates_and_user_policy",
            validation_route_path=HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH,
        )
        return RagDiagnosticReadinessResponse(
            readiness_report_available=True,
            readiness_source=repo_relative_or_name(self.readiness_report_path),
            run_id=_clean(report.get("run_id")) or V4_6_PREFLIGHT_RUN_ID,
            status=_clean(report.get("status")) or _clean(metrics.get("status")),
            v4_name=_clean(report.get("v4_name")) or V4_READINESS_NAME,
            run_family=_clean(report.get("run_family")) or V4_READINESS_RUN_FAMILY,
            ft_route_policy_dry_run_preflight_only=bool(
                report.get("ft_route_policy_dry_run_preflight_only")
                or metrics.get("ft_route_policy_dry_run_preflight_only")
            ),
            all_preflight_gates_passed=bool(metrics.get("all_preflight_gates_passed")),
            ft_route_policy_dry_run_opened=bool(
                metrics.get("ft_route_policy_dry_run_opened")
                or report.get("v4_6_ft_dry_run_opened")
            ),
            ft_route_policy_dry_run_executed=bool(
                metrics.get("ft_route_policy_dry_run_executed")
                or report.get("ft_route_policy_dry_run_executed")
            ),
            fine_tuning_dataset_exports_created=int(metrics.get("fine_tuning_dataset_exports_created") or 0),
            training_job_created=bool(metrics.get("training_job_created") or report.get("training_job_created")),
            model_or_adapter_checkpoint_written=bool(
                metrics.get("model_or_adapter_checkpoint_written")
                or report.get("model_or_adapter_checkpoint_written")
            ),
            preflight_gates=dict(_as_mapping(report.get("preflight_gates"))),
            source_report_inputs=dict(_as_mapping(report.get("source_report_inputs"))),
            holdout_gap_and_dry_run_blocker_ledger_only=bool(
                report.get("holdout_gap_and_dry_run_blocker_ledger_only")
                or metrics.get("holdout_gap_and_dry_run_blocker_ledger_only")
            ),
            holdout_gap_ledger=holdout_gap_ledger,
            dry_run_blocker_ledger=dry_run_blocker_ledger,
            external_holdout_candidate_manifest_gate_replay_only=bool(
                report.get("external_holdout_candidate_manifest_gate_replay_only")
                or metrics.get("external_holdout_candidate_manifest_gate_replay_only")
                or manifest_gate_replay.get("external_holdout_candidate_manifest_gate_replay_only")
            ),
            candidate_manifest_input_only=bool(manifest_gate_replay.get("candidate_manifest_input_only")),
            candidate_manifest_input=dict(_as_mapping(manifest_gate_replay.get("candidate_manifest_input"))),
            candidate_rows_replayed=int(
                manifest_gate_replay.get("candidate_rows_replayed")
                or metrics.get("candidate_rows_replayed")
                or 0
            ),
            external_holdout_runtime_replay_route_parity_only=bool(
                report.get("external_holdout_runtime_replay_route_parity_only")
                or metrics.get("external_holdout_runtime_replay_route_parity_only")
            ),
            runtime_parity_probe_only=bool(report.get("runtime_parity_probe_only") or metrics.get("runtime_parity_probe_only")),
            external_holdout_runtime_replay_route_parity=route_parity,
            candidate_rows_replayed_in_probe=int(
                route_parity.get("probe_candidate_row_count")
                or metrics.get("candidate_rows_replayed_in_probe")
                or 0
            ),
            route_path=_clean(route_parity.get("route_path")),
            route_candidate_counts_match_v4_6_10_replay=bool(
                route_parity.get("route_candidate_counts_match_v4_6_10_replay")
                or metrics.get("route_candidate_counts_match_v4_6_10_replay")
            ),
            route_source_identity_audit_matches_v4_6_10_replay=bool(
                route_parity.get("route_source_identity_audit_matches_v4_6_10_replay")
                or metrics.get("route_source_identity_audit_matches_v4_6_10_replay")
            ),
            route_response_sanitized=bool(route_parity.get("route_response_sanitized") or metrics.get("route_response_sanitized")),
            enabled_validation_error_raw_input_redacted=bool(
                route_parity.get("enabled_validation_error_raw_input_redacted")
                or metrics.get("enabled_validation_error_raw_input_redacted")
            ),
            route_rejects_prompt_path_metric_and_readiness_fields=bool(
                route_parity.get("route_rejects_prompt_path_metric_and_readiness_fields")
                or metrics.get("route_rejects_prompt_path_metric_and_readiness_fields")
            ),
            transient_external_manifest_deleted=bool(
                route_parity.get("transient_external_manifest_deleted")
                or metrics.get("transient_external_manifest_deleted")
            ),
            transient_external_manifest_persisted_in_repo=bool(
                route_parity.get("transient_external_manifest_persisted_in_repo")
            ),
            candidate_gate_target_sufficient=bool(manifest_gate_replay.get("candidate_gate_target_sufficient")),
            source_reports_closed=bool(
                manifest_gate_replay.get("source_reports_closed") or report.get("source_reports_closed")
            ),
            codex_owned_dependency_checks_passed=bool(
                manifest_gate_replay.get("codex_owned_dependency_checks_passed")
                or metrics.get("codex_owned_dependency_checks_passed")
            ),
            v4_5_1_intake_gate_passed=bool(manifest_gate_replay.get("v4_5_1_intake_gate_passed")),
            v4_5_2_source_identity_audit_gate_passed=bool(
                manifest_gate_replay.get("v4_5_2_source_identity_audit_gate_passed")
            ),
            v4_6_9_duplicate_hygiene_gate_passed=bool(
                manifest_gate_replay.get("v4_6_9_duplicate_hygiene_gate_passed")
            ),
            official_metric_opening_preflight_gate_passed=bool(official_metric_preflight.get("gate_passed")),
            official_metric_opening_preflight_gate_opened=bool(official_metric_preflight.get("gate_opened")),
            official_metric_rows_authorized=bool(official_metric_preflight.get("official_metric_rows_authorized")),
            missing_user_owned_input_count=int(official_metric_preflight.get("missing_user_owned_input_count") or 0),
            single_report_artifact_contract=bool(
                report.get("single_report_artifact_contract")
                or _as_mapping(report.get("summary")).get("single_report_artifact_contract")
            ),
            source_identity_collision_count=int(manifest_gate_replay.get("source_identity_collision_count") or 0),
            source_identity_audit_excluded_count=int(
                manifest_gate_replay.get("source_identity_audit_excluded_count") or 0
            ),
            candidate_intake_exclusion_reasons=dict(
                _as_mapping(manifest_gate_replay.get("candidate_intake_exclusion_reasons"))
            ),
            source_identity_audit_exclusion_reasons=dict(
                _as_mapping(manifest_gate_replay.get("source_identity_audit_exclusion_reasons"))
            ),
            candidate_manifest_exported=bool(
                report.get("candidate_manifest_exported")
                or metrics.get("candidate_manifest_exported")
                or holdout_gap_ledger.get("candidate_manifest_exported")
                or manifest_gate_replay.get("candidate_manifest_exported")
            ),
            candidate_manifest_jsonl_created=bool(
                report.get("candidate_manifest_jsonl_created") or metrics.get("candidate_manifest_jsonl_created")
            ),
            candidate_validation_jsonl_created=bool(
                report.get("candidate_validation_jsonl_created") or metrics.get("candidate_validation_jsonl_created")
            ),
            source_identity_audit_jsonl_created=bool(
                report.get("source_identity_audit_jsonl_created") or metrics.get("source_identity_audit_jsonl_created")
            ),
            candidate_manifest_present=bool(
                metrics.get("candidate_manifest_present")
                or holdout_gap_ledger.get("candidate_manifest_present")
                or manifest_gate_replay.get("candidate_manifest_present")
            ),
            real_holdout_available=bool(metrics.get("real_holdout_available") or holdout_gap_ledger.get("real_holdout_available")),
            real_holdout_sufficient=bool(
                metrics.get("real_holdout_sufficient")
                or holdout_gap_ledger.get("real_holdout_sufficient")
                or manifest_gate_replay.get("real_holdout_sufficient")
            ),
            dry_run_execution_plan_exported=bool(
                report.get("dry_run_execution_plan_exported")
                or metrics.get("dry_run_execution_plan_exported")
                or raw_dry_run_blocker_ledger.get("dry_run_execution_plan_exported")
            ),
            dry_run_input_manifest_exported=bool(
                report.get("dry_run_input_manifest_exported")
                or metrics.get("dry_run_input_manifest_exported")
                or raw_dry_run_blocker_ledger.get("dry_run_input_manifest_exported")
                or manifest_gate_replay.get("dry_run_input_manifest_exported")
            ),
            user_owned_policy_gate_ready=bool(
                metrics.get("user_owned_policy_gate_ready")
                or raw_dry_run_blocker_ledger.get("user_owned_policy_gate_ready")
            ),
            v4_7_official_metric_gate_opened=bool(
                report.get("v4_7_official_metric_gate_opened")
                or metrics.get("v4_7_official_metric_gate_opened")
                or raw_dry_run_blocker_ledger.get("v4_7_official_metric_gate_opened")
                or manifest_gate_replay.get("v4_7_official_metric_gate_opened")
            ),
            dry_run_blocker_count=int(
                metrics.get("dry_run_blocker_count")
                or raw_dry_run_blocker_ledger.get("dry_run_blocker_count")
                or 0
            ),
            accepted_pdf_holdout_candidates=int(
                metrics.get("accepted_pdf_holdout_candidates")
                or holdout_gap_ledger.get("accepted_pdf_holdout_candidates")
                or 0
            ),
            accepted_xlsx_holdout_candidates=int(
                metrics.get("accepted_xlsx_holdout_candidates")
                or holdout_gap_ledger.get("accepted_xlsx_holdout_candidates")
                or 0
            ),
            pdf_source_document_disjoint_needed=int(
                metrics.get("pdf_source_document_disjoint_needed")
                or holdout_deficits.get("pdf_source_document_disjoint_needed")
                or 0
            ),
            xlsx_workbook_disjoint_needed=int(
                metrics.get("xlsx_workbook_disjoint_needed")
                or holdout_deficits.get("xlsx_workbook_disjoint_needed")
                or 0
            ),
            pdf_query_fidelity_rows_needed=int(holdout_deficits.get("pdf_query_fidelity_rows_needed") or 0),
            xlsx_query_fidelity_rows_needed=int(holdout_deficits.get("xlsx_query_fidelity_rows_needed") or 0),
            gpu_required_for_future_training_when_opened=bool(metrics.get("gpu_required_for_future_training_when_opened")),
            gpu_required_for_this_slice=bool(metrics.get("gpu_required_for_this_slice")),
            readiness_decision=_clean(report.get("readiness_decision")),
            blocked_reasons=list(_as_sequence(report.get("blocked_reasons"))),
            official_metric=bool(report.get("official_metric") or metrics.get("official_metric")),
            official_metric_input_rows=int(report.get("official_metric_input_rows") or metrics.get("official_metric_input_rows") or 0),
            promotion_evidence=bool(report.get("promotion_evidence") or metrics.get("promotion_evidence")),
            product_success_evidence_allowed=bool(
                report.get("product_success_evidence_allowed")
                or metrics.get("product_success_evidence_allowed")
            ),
            live_db_index_cache_readiness=bool(report.get("live_db_index_cache_readiness")),
            source_atom_evidence_bundle_evidence_truth=bool(
                guardrails.get("source_atom_evidence_bundle_evidence_truth", True)
            ),
            searchview_vector_payload_candidate_only=bool(
                guardrails.get("searchview_vector_payload_candidate_only", True)
            ),
            vector_payload_used_as_evidence_truth=bool(guardrails.get("vector_payload_used_as_evidence_truth")),
            holdout_acquisition_requirements=holdout_acquisition_requirements,
            protected_namespaces_touched=list(_as_sequence(guardrails.get("protected_namespaces_touched"))),
            warnings=[
                "diagnostic_only",
                "not_production_routing",
                "not_official_metric",
                "not_promotion_evidence",
                "not_live_db_index_cache_readiness",
            ],
        )

    def _load_readiness_report(self) -> dict[str, Any]:
        if self.readiness_report is not None:
            return dict(self.readiness_report)
        if not self.readiness_report_path.exists():
            return {}
        try:
            payload = json.loads(self.readiness_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def query(self, request: RagDiagnosticQueryRequest) -> RagDiagnosticQueryResponse:
        request_id = _sha256(f"{request.query}|{request.source_family}|{request.cell}|{request.range}")[:16]
        requested_range = _clean(request.range) or _first_query_range(request.query)
        preflight_mode = determine_xlsx_range_mode_from_request(
            requested_range=requested_range,
            selected_source_atoms=[],
        ) if requested_range else "FORMAT_METADATA_UNAVAILABLE"
        if preflight_mode == "UNSUPPORTED_RANGE_TOO_LARGE":
            return self._fail_closed_response(
                request_id=request_id,
                response_policy_bucket="UNSUPPORTED_RANGE_TOO_LARGE",
                fail_closed_reason="UNSUPPORTED_RANGE_TOO_LARGE",
                xlsx_range_rendering_mode="UNSUPPORTED_RANGE_TOO_LARGE",
            )

        runtime_request = AgentRuntimeRequest(
            run_id=PHASE1_V3_22_RUN_ID,
            query_id=request_id,
            query_text=_query_text_with_request_locators(request),
            source_family=_clean(request.source_family) or _infer_source_family(self.source_atoms.values()),
            source_registry=self.source_atoms,
            candidate_source_atom_ids=tuple(self.source_atoms),
            request_context=self._request_context(request),
            internal_replay_adapter=True,
        )
        result = self.runtime.invoke(runtime_request)
        selected_atoms = [self.source_atoms[source_atom_id] for source_atom_id in result.selected_source_atom_ids if source_atom_id in self.source_atoms]
        rendered = render_xlsx_display_value(selected_atoms, requested_range=requested_range) if selected_atoms else empty_display_contract()
        xlsx_mode = _clean(rendered.get("xlsx_range_rendering_mode")) or "FORMAT_METADATA_UNAVAILABLE"
        final_answer = result.final_answer
        llm_invoked = False
        if result.answer_allowed_by_policy:
            if self.llm_invoker is not None:
                final_answer = str(
                    self.llm_invoker(
                        {
                            "query": request.query,
                            "rendered_value": _clean(rendered.get("rendered_value")),
                            "evidence_truth_source": result.evidence_truth_source,
                            "selected_source_atom_ids": list(result.selected_source_atom_ids),
                            "diagnostic_only": True,
                        }
                    )
                )
                llm_invoked = True
            else:
                final_answer = _clean(rendered.get("rendered_value")) or result.final_answer
        return RagDiagnosticQueryResponse(
            answer_allowed_by_policy=result.answer_allowed_by_policy,
            response_policy_bucket=result.response_policy_bucket,
            final_answer=final_answer,
            citations=[_citation_payload(atom) for atom in selected_atoms],
            evidence_bundles=[_evidence_bundle_for_atom(atom) for atom in selected_atoms],
            selected_source_atom_ids=list(result.selected_source_atom_ids),
            selected_search_view_ids=_search_view_ids_from_runtime_trace(result.runtime_adapter_trace_rows),
            evidence_truth_source=result.evidence_truth_source,
            xlsx_range_rendering_mode=xlsx_mode,
            fail_closed_reason=result.fail_closed_reason,
            warnings=_response_warnings(result),
            request_id=request_id,
            llm_invoked=llm_invoked,
            vector_payload_used_as_evidence_truth=False,
            formula_text_visible_to_user=False,
            formula_evaluation_at_query_time=False,
        )

    def _request_context(self, request: RagDiagnosticQueryRequest) -> dict[str, Any]:
        active_context = _as_mapping(request.active_context)
        active_ids = list(_as_sequence(active_context.get("active_source_atom_ids") or active_context.get("source_atom_ids")))
        if _clean(active_context.get("active_source_atom_id") or active_context.get("source_atom_id")):
            active_ids.append(_clean(active_context.get("active_source_atom_id") or active_context.get("source_atom_id")))
        return {
            "diagnostic_tenant_id": _clean(request.tenant_id) or "diagnostic-local",
            "tenant_id": _clean(request.tenant_id) or "diagnostic-local",
            "namespace": self.namespace,
            "cache_namespace": self.namespace,
            "expected_cache_namespace": self.namespace,
            "authorized_source_atom_ids": tuple(self.source_atoms),
            "active_source_atom_ids": tuple(dict.fromkeys(active_ids)),
        }

    def _fail_closed_response(
        self,
        *,
        request_id: str,
        response_policy_bucket: str,
        fail_closed_reason: str,
        xlsx_range_rendering_mode: str,
    ) -> RagDiagnosticQueryResponse:
        return RagDiagnosticQueryResponse(
            answer_allowed_by_policy=False,
            response_policy_bucket=response_policy_bucket,
            final_answer="요청한 범위는 비프로덕션 진단 경로의 안전 범위를 초과했습니다.",
            evidence_truth_source="none",
            xlsx_range_rendering_mode=xlsx_range_rendering_mode,
            fail_closed_reason=fail_closed_reason,
            warnings=["diagnostic route failed closed before LLM invocation"],
            request_id=request_id,
            llm_invoked=False,
        )


def _display_contract_from_atom(atom: Mapping[str, Any]) -> dict[str, Any]:
    contract = dict(_as_mapping(atom.get("xlsx_display_contract")))
    if not contract:
        contract = {
            "raw_value": _clean(atom.get("normalized_text_or_value_snapshot")),
            "display_value": _clean(atom.get("normalized_text_or_value_snapshot")),
            "normalized_value": _clean(atom.get("normalized_text_or_value_snapshot")),
            "format_confidence": "low",
            "format_drop_reason": "FORMAT_METADATA_UNAVAILABLE",
        }
    if not _clean(contract.get("display_value")):
        contract["display_value"] = _clean(contract.get("raw_value"))
        contract["format_confidence"] = "low"
        contract["format_drop_reason"] = "FORMAT_METADATA_UNAVAILABLE"
    contract.setdefault("formula_text_visible_to_user", False)
    contract.setdefault("formula_evaluation_at_query_time", False)
    return contract


def _contract_rendered_value(contract: Mapping[str, Any]) -> str:
    return _clean(contract.get("display_value")) or _clean(contract.get("raw_value")) or _clean(contract.get("normalized_value"))


def _sort_atom_cell_key(atom: Mapping[str, Any]) -> tuple[int, int, str]:
    locator = _as_mapping(atom.get("raw_locator"))
    parsed = cell_ref_to_row_col(_clean(locator.get("cell")))
    if parsed is None:
        return (999999, 999999, _clean(atom.get("source_atom_id")))
    row, col = parsed
    return row, col, _clean(atom.get("source_atom_id"))


def _search_view_for_atom(atom_id: str, atom: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "search_view_id": f"sv:{atom_id}",
        "source_family": _clean(atom.get("source_family")).upper(),
        "source_atom_ids": [atom_id],
        "bm25_text": _clean(atom.get("normalized_text_or_value_snapshot")),
        "vector_payload": {
            "candidate_only": True,
            "source_atom_ids": [atom_id],
            "canonical_payload_ignored_for_evidence_truth": True,
        },
    }


def _query_text_with_request_locators(request: RagDiagnosticQueryRequest) -> str:
    parts = [request.query]
    if request.file_id:
        parts.append(f"file {request.file_id}")
    if request.source_identity:
        parts.append(f"file {request.source_identity}")
    if request.workbook_id:
        parts.append(f"file {request.workbook_id}")
    if request.sheet_name:
        parts.append(f"sheet {request.sheet_name}")
    if request.cell:
        parts.append(f"cell {request.cell}")
    if request.range:
        parts.append(f"range {request.range}")
    if request.page is not None:
        parts.append(f"page {request.page}")
    return " ".join(_clean(part) for part in parts if _clean(part))


def _first_query_range(query: str) -> str:
    match = re.search(r"\b([A-Z]{1,3}[1-9][0-9]*:[A-Z]{1,3}[1-9][0-9]*)\b", _clean(query).upper())
    return match.group(1) if match else ""


def _infer_source_family(source_atoms: Sequence[Mapping[str, Any]]) -> str:
    for atom in source_atoms:
        family = _clean(atom.get("source_family")).upper()
        if family:
            return family
    return "XLSX"


def _citation_payload(atom: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(_as_mapping(atom.get("canonical_citation_payload")))
    source_identity = _clean(atom.get("source_identity") or payload.get("source_identity"))
    if source_identity and "source_identity" not in payload:
        payload["source_identity"] = source_identity
    return _sanitize_diagnostic_http_payload(payload)


def _evidence_bundle_for_atom(atom: Mapping[str, Any]) -> dict[str, Any]:
    atom_id = _clean(atom.get("source_atom_id"))
    result = assemble_evidence_bundle(atom_id, source_registry={atom_id: atom}, mode="runtime_evidence")
    if result.get("valid"):
        bundle = dict(_as_mapping(result.get("evidence_bundle")))
        bundle["evidence_truth_source"] = EVIDENCE_TRUTH_SOURCE
        return _sanitize_diagnostic_http_payload(bundle)
    return {
        "source_atom_id": atom_id,
        "evidence_truth_source": "none",
        "failure_bucket": _clean(result.get("failure_bucket")) or "EVIDENCE_BUNDLE_CONTRACT_INCOMPLETE",
    }


def _search_view_ids_from_runtime_trace(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    ids: list[str] = []
    for row in rows:
        for search_view_id in _as_sequence(row.get("search_view_ids")):
            if search_view_id not in ids:
                ids.append(search_view_id)
    return ids


def _response_warnings(result: Any) -> list[str]:
    warnings = [
        "diagnostic_only",
        "not_production_routing",
        "search_view_candidate_metadata_only",
        "source_atom_evidence_bundle_is_evidence_truth",
    ]
    if getattr(result, "cache_contract_status", "not_configured") in {"unavailable", "namespace_mismatch"}:
        warnings.append("cache_unavailable_or_namespace_mismatch_fail_closed")
    return warnings


def repo_relative_or_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path(__file__).resolve().parents[4]).as_posix()
    except ValueError:
        return "__external_readiness_report_path_redacted__"
