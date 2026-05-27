from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

AI_DIR = Path(__file__).resolve().parents[1]
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from fastapi.testclient import TestClient

from app.api import create_app
from app.capabilities.rag_orchestrator.phase1_diagnostic_runtime import (
    HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH,
    SourceFirstRagService,
)
from app.core.config import WorkerSettings

import rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod as v467
import rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod as v4610
import rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod as v4611


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
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
EVENT_TYPE = "diagnostic_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
STATUS = "DIAGNOSTIC_V4_6_12_EXTERNAL_HOLDOUT_RUNTIME_REPLAY_ROUTE_PARITY_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_6_12_external_holdout_runtime_replay_route_parity_report_v1"

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "candidate_manifest.jsonl",
            "candidate_validation.jsonl",
            "dry_run_input_manifest.jsonl",
            "external_holdout_runtime_replay_route_parity.json",
            "metrics.json",
            "official_metric_results.jsonl",
            "prompt_manifest.json",
            "raw_llm_response.json",
            "review_packet.csv",
            "sft_dataset.jsonl",
            "source_identity_audit.jsonl",
            "summary.json",
            "training_manifest.jsonl",
        }
    )
)

FORBIDDEN_RAW_VALUE_FRAGMENTS = (
    "pdf-v4612",
    "xlsx-v4612",
    "pdf-doc-v4612",
    "workbook-v4612",
    "hidden holdout prompt",
    "secret holdout answer",
    "secret holdout support",
    "D:/private",
)


def clean(value: Any) -> str:
    return v4610.clean(value)


def repo_relative(path: Path) -> str:
    return v4610.repo_relative(path)


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


def artifact_path_text(path: Path) -> str:
    try:
        return repo_relative(path) if path.resolve() == REPORT_JSON.resolve() else path.as_posix()
    except OSError:
        return path.as_posix()


def _enabled_settings() -> WorkerSettings:
    return WorkerSettings(rag_fastapi_diagnostic_route_enabled=True)


def _response_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _probe_candidate_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(100):
        rows.append(
            {
                "candidate_id": f"pdf-v4612-candidate-{index:03d}",
                "query_id": f"pdf-v4612-query-{index:03d}",
                "source_family": "PDF",
                "source_document_id": f"pdf-doc-v4612-{index % 20:02d}",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            }
        )
    for index in range(100):
        rows.append(
            {
                "candidate_id": f"xlsx-v4612-candidate-{index:03d}",
                "query_id": f"xlsx-v4612-query-{index:03d}",
                "source_family": "XLSX",
                "workbook_id": f"workbook-v4612-{index % 8:02d}",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            }
        )
    return rows


def _leaky_candidate_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "pdf-v4612-leaky",
            "query_id": "pdf-v4612-leaky-query",
            "source_family": "PDF",
            "source_document_id": "pdf-doc-v4612-leaky",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
            "expected_answer": "secret holdout answer",
            "supporting_evidence": "secret holdout support",
            "raw_prompt": "hidden holdout prompt",
            "local_path": "D:/private/holdout.pdf",
            "official_metric_input_rows": 1,
            "promotion_evidence": True,
            "candidate_manifest_jsonl_created": True,
            "live_db_index_cache_readiness": True,
        }
    ]


def _prior_identity_hash_records() -> list[dict[str, Any]]:
    return [
        {
            "source_family": "PDF",
            "source_identity_hash": v4610.v452.source_identity_hash("PDF", "unrelated-prior-pdf-v4612"),
            "identity_scope": "PDF_source_document",
            "source_identity_hash_algorithm": "sha256(family:identity_key)",
            "source_atom_count": 1,
        },
        {
            "source_family": "XLSX",
            "source_identity_hash": v4610.v452.source_identity_hash("XLSX", "unrelated-prior-xlsx-v4612"),
            "identity_scope": "XLSX_workbook",
            "source_identity_hash_algorithm": "sha256(family:identity_key)",
            "source_atom_count": 1,
        },
    ]


def _prior_identity_summary_report(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, list[dict[str, Any]]] = {"PDF": [], "XLSX": [], "TEXT": []}
    for record in records:
        family = clean(record.get("source_family")).upper()
        source_identity_hash = clean(record.get("source_identity_hash"))
        if family not in by_family or not source_identity_hash:
            continue
        by_family[family].append(
            {
                "source_family": family,
                "source_identity_hash": source_identity_hash,
                "identity_scope": clean(record.get("identity_scope")),
                "source_atom_count": int(record.get("source_atom_count") or 0),
            }
        )
    return {
        "identity_key_hash_algorithm": "sha256(family:identity_key)",
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
        "prior_identity_hash_records_by_family": by_family,
    }


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _build_v4_6_10_transient_manifest_replay(
    rows: Sequence[Mapping[str, Any]],
    prior_hash_records: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    temp_dir_path: Path | None = None
    manifest_path: Path | None = None
    with tempfile.TemporaryDirectory(prefix="codex-v4612-holdout-") as temp_dir:
        temp_dir_path = Path(temp_dir)
        manifest_path = temp_dir_path / "external_candidates.jsonl"
        _write_jsonl(manifest_path, rows)
        report = v4610.build_artifacts(
            candidate_manifest_path=manifest_path,
            prior_identity_summary_report=_prior_identity_summary_report(prior_hash_records),
        )["report"]
    deleted = bool(
        temp_dir_path is not None
        and manifest_path is not None
        and not temp_dir_path.exists()
        and not manifest_path.exists()
    )
    return report, deleted


def _source_report_input(name: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    report = read_json(path) if exists else {}
    metrics = report.get("metrics") if isinstance(report.get("metrics"), Mapping) else {}
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), Mapping) else {}
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
        "source_report_boundary_flags_clean": boundary_flags_clean,
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
    }


def build_source_report_inputs() -> dict[str, dict[str, Any]]:
    return {
        "v4_6_7": _source_report_input("v4_6_7", v467.REPORT_JSON),
        "v4_6_10": _source_report_input("v4_6_10", v4610.REPORT_JSON),
        "v4_6_11": _source_report_input("v4_6_11", v4611.REPORT_JSON),
    }


def build_external_holdout_runtime_replay_route_parity() -> dict[str, Any]:
    rows = _probe_candidate_rows()
    prior_hash_records = _prior_identity_hash_records()
    service = SourceFirstRagService()
    enabled_client = TestClient(create_app(settings=_enabled_settings(), rag_diagnostic_service=service))
    target_payload = {
        "schema_version": "v4_holdout_candidate_manifest_contract_v1",
        "request_id": "v4-6-12-route-parity-target",
        "candidate_rows": rows,
        "prior_identity_hash_records": prior_hash_records,
    }
    enabled_response = enabled_client.post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH, json=target_payload)
    enabled_payload = _response_json(enabled_response)
    replay_report, transient_manifest_deleted = _build_v4_6_10_transient_manifest_replay(
        rows,
        prior_hash_records,
    )
    replay = replay_report["external_holdout_candidate_manifest_gate_replay"]

    validation_error_payload = {
        **target_payload,
        "candidate_manifest_path": "D:/private/holdout.jsonl",
        "raw_prompt": "hidden holdout prompt",
    }
    validation_error_response = enabled_client.post(
        HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH,
        json=validation_error_payload,
    )
    leaky_response = enabled_client.post(
        HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH,
        json={
            "schema_version": "v4_holdout_candidate_manifest_contract_v1",
            "request_id": "v4-6-12-route-parity-leak-probe",
            "candidate_rows": _leaky_candidate_rows(),
        },
    )
    leaky_payload = _response_json(leaky_response)
    disabled_response = TestClient(create_app(settings=WorkerSettings())).post(
        HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH,
        json=validation_error_payload,
    )
    production_disabled_response = TestClient(
        create_app(
            settings=WorkerSettings(
                rag_query_orchestrator_mode="production",
                rag_fastapi_diagnostic_route_enabled=True,
            )
        )
    ).post(HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH, json=validation_error_payload)

    route_gate = enabled_payload.get("candidate_intake_gate") if isinstance(enabled_payload, Mapping) else {}
    route_audit = enabled_payload.get("source_identity_audit_gate") if isinstance(enabled_payload, Mapping) else {}
    route_counts = route_gate.get("accepted_holdout_candidate_counts") if isinstance(route_gate, Mapping) else {}
    route_query_counts = route_gate.get("real_query_fidelity_included_counts") if isinstance(route_gate, Mapping) else {}
    route_deficits = route_gate.get("deficits") if isinstance(route_gate, Mapping) else {}
    route_replay_count_match = (
        enabled_response.status_code == 200
        and int(enabled_payload.get("candidate_manifest_rows") or 0) == int(replay.get("candidate_rows_replayed") or 0)
        and int(enabled_payload.get("accepted_candidate_count") or 0) == len(rows)
        and int(replay.get("candidate_rows_replayed") or 0) == len(rows)
    )
    route_count_match = (
        route_replay_count_match
        and int(route_counts.get("PDF_source_document_disjoint") or 0)
        == int(replay.get("accepted_pdf_holdout_candidates") or 0)
        and int(route_counts.get("XLSX_workbook_disjoint") or 0)
        == int(replay.get("accepted_xlsx_holdout_candidates") or 0)
        and int(route_query_counts.get("PDF") or 0) == 100
        and int(route_query_counts.get("XLSX") or 0) == 100
        and route_deficits
        == {
            "pdf_source_document_disjoint_needed": 0,
            "xlsx_workbook_disjoint_needed": 0,
            "pdf_query_fidelity_rows_needed": 0,
            "xlsx_query_fidelity_rows_needed": 0,
        }
    )
    route_audit_match = (
        bool(route_audit.get("passed")) == bool(replay.get("v4_5_2_source_identity_audit_gate_passed"))
        and int(route_audit.get("collision_count") or 0) == int(replay.get("source_identity_collision_count") or 0)
    )
    leaky_exclusion_reasons = {
        reason
        for row in leaky_payload.get("excluded_candidates") or []
        if isinstance(row, Mapping)
        for reason in row.get("exclusion_reasons") or []
    }
    route_rejects_leaks = (
        leaky_response.status_code == 200
        and int(leaky_payload.get("accepted_candidate_count") or 0) == 0
        and {
            "protected_oracle_fields_present",
            "forbidden_prompt_or_llm_fields_present",
            "raw_local_path_present",
            "forbidden_contract_fields_present",
            "forbidden_readiness_flags_present",
        }.issubset(leaky_exclusion_reasons)
        and int(leaky_payload.get("official_metric_input_rows") or 0) == 0
        and leaky_payload.get("promotion_evidence") is False
        and leaky_payload.get("live_db_index_cache_readiness") is False
    )
    sanitized_projection = not _contains_forbidden_raw_fragment(
        {
            "enabled_text": enabled_response.text,
            "validation_error_text": validation_error_response.text,
            "leaky_text": leaky_response.text,
            "disabled_text": disabled_response.text,
            "production_disabled_text": production_disabled_response.text,
        }
    )
    return {
        "schema_version": f"{RUN_ID}_route_parity_v1",
        "run_id": RUN_ID,
        "route_path": HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH,
        "feature_flag_name": "RAG_FASTAPI_DIAGNOSTIC_ROUTE_ENABLED",
        "feature_flag_default_enabled": WorkerSettings().rag_fastapi_diagnostic_route_enabled,
        "production_orchestrator_mode_enabled": False,
        "disabled_route_status_code": disabled_response.status_code,
        "production_disabled_route_status_code": production_disabled_response.status_code,
        "disabled_route_raw_body_leakage_detected": _contains_forbidden_raw_fragment(
            disabled_response.text + production_disabled_response.text
        ),
        "enabled_target_sufficient_status_code": enabled_response.status_code,
        "enabled_validation_error_status_code": validation_error_response.status_code,
        "enabled_validation_error_raw_input_redacted": _validation_error_raw_input_redacted(
            validation_error_response
        ),
        "route_response_sanitized": sanitized_projection,
        "transient_external_manifest_deleted": transient_manifest_deleted,
        "transient_external_manifest_persisted_in_repo": False,
        "probe_candidate_row_count": len(rows),
        "raw_candidate_rows_embedded": False,
        "raw_runtime_request_body_embedded": False,
        "raw_runtime_response_body_embedded": False,
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
        "v4_6_10_replay_candidate_manifest_present": bool(replay.get("candidate_manifest_present")),
        "v4_6_10_replay_candidate_rows_replayed": int(replay.get("candidate_rows_replayed") or 0),
        "v4_6_10_replay_candidate_gate_target_sufficient": bool(
            replay.get("candidate_gate_target_sufficient")
        ),
        "v4_6_10_replay_real_holdout_sufficient": bool(replay.get("real_holdout_sufficient")),
        "route_candidate_intake_gate_passed": bool(route_gate.get("passed")),
        "route_source_identity_audit_gate_passed": bool(route_audit.get("passed")),
        "route_candidate_counts_match_v4_6_10_replay": route_count_match,
        "route_source_identity_audit_matches_v4_6_10_replay": route_audit_match,
        "route_rejects_prompt_path_metric_and_readiness_fields": route_rejects_leaks,
        "route_candidate_intake_snapshot": {
            "passed": bool(route_gate.get("passed")),
            "accepted_holdout_candidate_counts": dict(route_counts or {}),
            "real_query_fidelity_included_counts": dict(route_query_counts or {}),
            "deficits": dict(route_deficits or {}),
            "accepted_candidate_count": int(route_gate.get("accepted_candidate_count") or 0),
            "excluded_candidate_count": int(route_gate.get("excluded_candidate_count") or 0),
        },
        "route_source_identity_audit_snapshot": {
            "executed": bool(route_audit.get("executed")),
            "passed": bool(route_audit.get("passed")),
            "prior_identity_hash_record_count": int(route_audit.get("prior_identity_hash_record_count") or 0),
            "invalid_prior_identity_hash_record_count": int(
                route_audit.get("invalid_prior_identity_hash_record_count") or 0
            ),
            "collision_count": int(route_audit.get("collision_count") or 0),
        },
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
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
        "candidate_manifest_exported": False,
        "real_holdout_sufficient": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "dry_run_execution_plan_exported": False,
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
        "raw_llm_response_payload_created": False,
        "raw_candidate_rows_embedded": False,
        "raw_runtime_request_body_embedded": False,
        "raw_runtime_response_body_embedded": False,
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
        "source_atom_evidence_bundle_evidence_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "source_atom_registry_mutated": False,
        "db_or_production_namespace_written": False,
        "protected_namespaces_touched": [],
        "review_csv_created": False,
        "review_packet_created": False,
        "single_report_artifact_contract": True,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_metrics(parity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "external_holdout_runtime_replay_route_parity_only": True,
        "runtime_parity_probe_only": True,
        "gate_opened": False,
        "gate_passed": False,
        "candidate_manifest_present": False,
        "candidate_manifest_exported": False,
        "candidate_rows_replayed_in_probe": int(parity.get("probe_candidate_row_count") or 0),
        "route_candidate_counts_match_v4_6_10_replay": bool(
            parity.get("route_candidate_counts_match_v4_6_10_replay")
        ),
        "route_source_identity_audit_matches_v4_6_10_replay": bool(
            parity.get("route_source_identity_audit_matches_v4_6_10_replay")
        ),
        "enabled_validation_error_raw_input_redacted": bool(
            parity.get("enabled_validation_error_raw_input_redacted")
        ),
        "route_response_sanitized": bool(parity.get("route_response_sanitized")),
        "transient_external_manifest_deleted": bool(parity.get("transient_external_manifest_deleted")),
        "route_rejects_prompt_path_metric_and_readiness_fields": bool(
            parity.get("route_rejects_prompt_path_metric_and_readiness_fields")
        ),
        "real_holdout_sufficient": False,
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "fine_tuning_dataset_exports_created": 0,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "single_report_artifact_contract": True,
        "review_csv_created": False,
    }


def build_report(
    *,
    source_inputs: Mapping[str, Mapping[str, Any]],
    parity: Mapping[str, Any],
    metrics: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    source_reports_current = all(bool(item.get("source_report_hash_current")) for item in source_inputs.values())
    source_reports_closed = all(bool(item.get("source_report_boundary_flags_clean")) for item in source_inputs.values())
    blocked_reasons = [
        "real_external_holdout_candidates_not_user_registered",
        "user_owned_gold_qrels_denominator_policy_pending",
        "v4_7_official_metric_gate_closed",
    ]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "status": STATUS,
        "generated_at": utc_now(),
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "diagnostic_only": True,
        "external_holdout_runtime_replay_route_parity_only": True,
        "runtime_parity_probe_only": True,
        "external_holdout_runtime_replay_route_parity": dict(parity),
        "source_report_inputs": {key: dict(value) for key, value in source_inputs.items()},
        "source_reports_current": source_reports_current,
        "source_reports_closed": source_reports_closed,
        "metrics": dict(metrics),
        "guardrails": dict(guardrails),
        "artifact_paths": dict(artifact_paths),
        "summary": {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "status": STATUS,
            "diagnostic_only": True,
            "external_holdout_runtime_replay_route_parity_only": True,
            "runtime_parity_probe_only": True,
            "single_report_artifact_contract": True,
            "report_json_created": bool(artifact_paths),
            "review_csv_created": False,
            "candidate_manifest_exported": False,
            "real_holdout_sufficient": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
        },
        "readiness_decision": "blocked_pending_user_registered_external_holdout_and_policy",
        "blocked_reasons": blocked_reasons,
        "candidate_manifest_present": False,
        "candidate_manifest_exported": False,
        "single_report_artifact_contract": True,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "dry_run_execution_plan_exported": False,
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
        "raw_llm_response_payload_created": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "real_holdout_sufficient": False,
        "protected_namespaces_touched": [],
        "review_csv_created": False,
        "per_run_markdown_created": False,
        "warnings": [
            "diagnostic_only",
            "runtime_route_parity_probe_only",
            "not_real_external_holdout_registration",
            "no_candidate_manifest_or_sidecar_export",
            "not_official_metric_or_promotion_evidence",
        ],
    }


def build_artifacts() -> dict[str, Any]:
    source_inputs = build_source_report_inputs()
    parity = build_external_holdout_runtime_replay_route_parity()
    guardrails = build_guardrails()
    metrics = build_metrics(parity)
    artifact_paths = {"report_json": repo_relative(REPORT_JSON)}
    report = build_report(
        source_inputs=source_inputs,
        parity=parity,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "external_holdout_runtime_replay_route_parity": parity,
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
        raise RuntimeError(f"unexpected v4_6_12 primary artifacts: {unexpected}")


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
    hashes: dict[str, str] = {}
    for key, path_text in artifact_paths.items():
        path = Path(path_text)
        if not path.is_absolute():
            path = ROOT / path_text
        if path.exists():
            hashes[f"{key}_sha256"] = sha256_file(path)
    return hashes


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
        "external_holdout_runtime_replay_route_parity": dict(
            report["external_holdout_runtime_replay_route_parity"]
        ),
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
    v467.replace_marked_entry(path, marker, entry)


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
        r"(?:current diagnostic v4_6_12 external holdout runtime replay route parity loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_11 FT-A runtime input validation route parity loop:\n`[^`]+`;",
        "current diagnostic v4_6_12 external holdout runtime replay route parity loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_6_11 FT-A runtime input validation route parity loop:\n"
        f"`{v4611.RUN_ID}`;",
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
    script = "ai\\scripts\\rag_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod.py"
    compile_cmd = f"python -X utf8 -m py_compile {script}"
    check_cmd = f"python -X utf8 {script} --check"
    if compile_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py\n",
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py\n"
            f"{compile_cmd}\n",
            1,
        )
    if check_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 ai\\scripts\\rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py --check\n",
            "python -X utf8 ai\\scripts\\rag_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod.py --check\n"
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
        r"v4_6_11 is `diagnostic_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod_ready`"
        r"(?:; v4_6_12 is `[^`]+`)?\.",
        f"v4_6_11 is `{v4611.EVENT_TYPE}_ready`; v4_6_12 is `{current_status}`.",
        eval_text,
        count=1,
    )
    EVAL_README.write_text(eval_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod.py` | "
        "Checks the default-disabled FastAPI holdout-candidate validation route against a transient "
        "v4_6_10 external manifest replay using hash-only probes. It verifies route count/source-identity "
        "parity, validation-error redaction, leak rejection, temp-manifest deletion, and no candidate "
        "manifest, validation/source-audit sidecar, dry-run input, dataset, job, checkpoint, official metric, "
        "promotion, product-success, or live-readiness opening. |"
    )
    pattern = r"\n?\| `rag_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod\.py` \| .*?\|"
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
    if "### v4_6_12 — External Holdout Runtime Replay Route Parity" not in text:
        insert = """### v4_6_12 — External Holdout Runtime Replay Route Parity

This is a diagnostic route-parity check, not external holdout registration and not a dry run.

Purpose:

- Compare the default-disabled FastAPI holdout-candidate validation route with a transient v4_6_10 external manifest replay.
- Verify target-sufficient probe rows produce matching route/replay counts and source-identity audit state without persisting candidate manifests or sidecars.
- Verify route validation errors redact raw body/path/prompt content and leak probes are rejected as hash-only diagnostics.
- Keep real external holdout registration, candidate export, dry-run input/export, FT-A execution, dataset export, v4_7, official metric, promotion, product-success, and live-readiness gates closed.

Locked boundary:

```text
external_holdout_runtime_replay_route_parity_only = true
runtime_parity_probe_only = true
candidate_manifest_present = false
candidate_manifest_exported = false
candidate_manifest_jsonl_created = false
candidate_validation_jsonl_created = false
source_identity_audit_jsonl_created = false
dry_run_input_manifest_exported = false
ft_route_policy_dry_run_opened = false
ft_route_policy_dry_run_executed = false
v4_7_official_metric_gate_opened = false
official_metric_input_rows = 0
promotion_evidence = false
product_success_evidence_allowed = false
live_db_index_cache_readiness = false
```

"""
        text = text.replace("### v4_7 — Official Metric Opening Gate", insert + "### v4_7 — Official Metric Opening Gate", 1)
    text = text.replace(
        "v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        "v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod\n↓\nv4_6_12_external_holdout_runtime_replay_route_parity_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
    )
    plan_path.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    report_path = report["artifact_paths"]["report_json"]
    metrics = report["metrics"]
    progress_entry = (
        f"- v4_6_12 external holdout runtime replay route parity (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It compares the default-disabled FastAPI holdout-candidate validation route with a transient v4_6_10 "
        "external manifest replay, verifying route/replay candidate counts, source-identity audit parity, "
        "default-disabled and production-disabled routing, validation-error redaction, leak-field rejection, "
        "and temp-manifest cleanup. This remains route-parity-probe-only: it does not register real external "
        "holdout, export a candidate manifest, create candidate validation or source-identity audit sidecars, "
        "open dry-run inputs, run FT-A, create datasets/jobs/checkpoints, create official metric rows, or claim "
        "promotion, product success, production routing, or live DB/index/cache readiness."
    )
    measurements_entry = f"""### v4_6_12 External Holdout Runtime Replay Route Parity

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Primary artifact: `{report_path}`
- Source evidence: v4_6_7/v4_6_10/v4_6_11 report hashes, FastAPI holdout-candidate validation route, and transient external-manifest replay against v4_6_10.
- Interpretation: route/replay parity and redaction are deterministic contract checks only. This is not real external holdout registration, not candidate manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| external_holdout_runtime_replay_route_parity_only | true |
| runtime_parity_probe_only | true |
| route_candidate_counts_match_v4_6_10_replay | {str(metrics['route_candidate_counts_match_v4_6_10_replay']).lower()} |
| route_source_identity_audit_matches_v4_6_10_replay | {str(metrics['route_source_identity_audit_matches_v4_6_10_replay']).lower()} |
| enabled_validation_error_raw_input_redacted | {str(metrics['enabled_validation_error_raw_input_redacted']).lower()} |
| route_response_sanitized | {str(metrics['route_response_sanitized']).lower()} |
| transient_external_manifest_deleted | {str(metrics['transient_external_manifest_deleted']).lower()} |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Artifact policy: single ignored `report.json`; no route-parity sidecar, candidate manifest, validation JSONL, source-identity audit JSONL, dry-run input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, official metric result, or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_6_12 External Holdout Runtime Replay Route Parity Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_6_12 is diagnostic-only, non-production, and route-parity-probe-only.\n"
        "- It verifies the FastAPI holdout-candidate validation route matches v4_6_10 transient manifest replay counts/audit state and redacts route validation errors.\n"
        "- It is not real holdout registration, not candidate manifest export, not validation/source-audit sidecar creation, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.\n"
        "- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `live_db_index_cache_readiness=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.\n"
        "- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion gate.\n"
    )
    _replace_marked_entry(PROGRESS_DOC, RUN_ID, progress_entry)
    _replace_marked_entry(MEASUREMENTS_DOC, RUN_ID, measurements_entry)
    _replace_marked_entry(TRIAGE_DOC, RUN_ID, triage_entry)
    update_current_status_lines()
    update_scripts_readme()
    update_v4_plan_note()


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise AssertionError("unexpected v4_6_12 schema")
    if report.get("run_id") != RUN_ID:
        raise AssertionError("unexpected v4_6_12 run_id")
    if report.get("diagnostic_only") is not True:
        raise AssertionError("v4_6_12 must remain diagnostic-only")
    if report.get("external_holdout_runtime_replay_route_parity_only") is not True:
        raise AssertionError("route parity flag must remain true")
    parity = report.get("external_holdout_runtime_replay_route_parity")
    if not isinstance(parity, Mapping):
        raise AssertionError("missing route parity block")
    if parity.get("route_path") != HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH:
        raise AssertionError("unexpected holdout route path")
    required_parity_true = (
        "enabled_validation_error_raw_input_redacted",
        "route_response_sanitized",
        "transient_external_manifest_deleted",
        "route_candidate_counts_match_v4_6_10_replay",
        "route_source_identity_audit_matches_v4_6_10_replay",
        "route_rejects_prompt_path_metric_and_readiness_fields",
        "v4_6_10_replay_candidate_gate_target_sufficient",
        "route_candidate_intake_gate_passed",
        "route_source_identity_audit_gate_passed",
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
    if int(parity.get("enabled_target_sufficient_status_code") or 0) != 200:
        raise AssertionError("enabled target-sufficient route probe must return 200")
    if int(parity.get("enabled_validation_error_status_code") or 0) != 422:
        raise AssertionError("enabled validation-error route probe must return 422")
    if parity.get("v4_6_10_replay_real_holdout_sufficient") is not False:
        raise AssertionError("v4_6_10 replay probe must not claim real holdout sufficiency")
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), Mapping) else {}
    for field in (
        "candidate_manifest_exported",
        "candidate_manifest_jsonl_created",
        "candidate_validation_jsonl_created",
        "source_identity_audit_jsonl_created",
        "dry_run_execution_plan_exported",
        "dry_run_input_manifest_exported",
        "ft_route_policy_dry_run_opened",
        "ft_route_policy_dry_run_executed",
        "fine_tuning_dataset_export_created",
        "training_manifest_jsonl_created",
        "training_job_created",
        "model_or_adapter_checkpoint_written",
        "prompt_payload_created",
        "prompt_manifest_created",
        "raw_llm_response_payload_created",
        "v4_7_official_metric_gate_opened",
        "official_metric",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
        "real_holdout_sufficient",
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
    if report.get("candidate_manifest_present") is not False:
        raise AssertionError("top-level candidate_manifest_present must remain false")
    if _contains_forbidden_raw_fragment(report):
        raise AssertionError("raw candidate, prompt, path, or manifest path leaked")
    if "candidate_manifest_path" in json.dumps(report, ensure_ascii=False, sort_keys=True):
        raise AssertionError("candidate manifest path field leaked")


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
                    "external_holdout_runtime_replay_route_parity_only": True,
                    "runtime_parity_probe_only": True,
                    "route_candidate_counts_match_v4_6_10_replay": metrics[
                        "route_candidate_counts_match_v4_6_10_replay"
                    ],
                    "route_source_identity_audit_matches_v4_6_10_replay": metrics[
                        "route_source_identity_audit_matches_v4_6_10_replay"
                    ],
                    "route_response_sanitized": metrics["route_response_sanitized"],
                    "transient_external_manifest_deleted": metrics["transient_external_manifest_deleted"],
                    "candidate_manifest_exported": False,
                    "real_holdout_sufficient": False,
                    "ft_route_policy_dry_run_opened": False,
                    "v4_7_official_metric_gate_opened": False,
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
