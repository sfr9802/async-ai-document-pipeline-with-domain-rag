from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_5_finetune_readiness_packet_nonprod as v45
import rag_v4_5_1_holdout_candidate_intake_gate_nonprod as v451
import rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod as v452
import rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod as v453
from app.capabilities.rag import holdout_manifest_contract


ROOT = v45.ROOT
REPORT_DIR = v45.REPORT_DIR
STATUS_JSONL = v45.STATUS_JSONL
PROGRESS_DOC = v45.PROGRESS_DOC
MEASUREMENTS_DOC = v45.MEASUREMENTS_DOC
TRIAGE_DOC = v45.TRIAGE_DOC
README = v45.README
EVAL_README = v45.EVAL_README

V4_NAME = v45.V4_NAME
V4_RUN_FAMILY = v45.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod"
EVENT_TYPE = "diagnostic_v4_6_ft_route_policy_dry_run_preflight_nonprod"
STATUS = "DIAGNOSTIC_V4_6_FT_ROUTE_POLICY_DRY_RUN_PREFLIGHT_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_6_ft_route_policy_dry_run_preflight_report_v1"
TARGET_POLICY_BUCKETS = [
    "ANSWER_ALLOWED",
    "CONTEXT_REQUIRED",
    "AMBIGUOUS_WORKBOOK_IDENTITY",
    "AMBIGUOUS_FILE_IDENTITY",
    "UNSUPPORTED_RANGE_TOO_LARGE",
]
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "dpo_dataset.jsonl",
            "ft_route_policy_dry_run.json",
            "metrics.json",
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


def clean(value: Any) -> str:
    return v45.clean(value)


def repo_relative(path: Path) -> str:
    return v45.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v45.artifact_path_text(path)


def utc_now() -> str:
    return v45.utc_now()


def sha256_file(path: Path) -> str:
    return v45.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v45.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v45.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v45.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v45.write_jsonl(path, rows)


def load_v4_5_report() -> dict[str, Any]:
    if v45.REPORT_JSON.exists():
        return read_json(v45.REPORT_JSON)
    return {}


def load_v4_5_1_report() -> dict[str, Any]:
    if v451.REPORT_JSON.exists():
        return read_json(v451.REPORT_JSON)
    return {}


def load_v4_5_2_report() -> dict[str, Any]:
    if v452.REPORT_JSON.exists():
        return read_json(v452.REPORT_JSON)
    return {}


def load_v4_5_3_report() -> dict[str, Any]:
    if v453.REPORT_JSON.exists():
        return read_json(v453.REPORT_JSON)
    return {}


def source_report_input(
    *,
    input_key: str,
    run_id: str,
    report_json: Path,
    report: Mapping[str, Any],
) -> dict[str, Any]:
    exists = report_json.exists()
    return {
        "schema_version": f"{RUN_ID}_source_report_input_v1",
        "run_id": RUN_ID,
        "input_key": input_key,
        "source_run_id": run_id,
        "source_report_json": repo_relative(report_json),
        "source_report_exists": exists,
        "source_report_sha256": sha256_file(report_json) if exists else "",
        "source_report_schema_version": clean(report.get("schema_version")),
        "source_report_status": clean(report.get("status")),
        "source_report_diagnostic_only": bool(report.get("diagnostic_only")),
        "source_report_official_metric": bool(report.get("official_metric")),
        "source_report_official_metric_input_rows": int(report.get("official_metric_input_rows") or 0),
        "source_report_promotion_evidence": bool(report.get("promotion_evidence")),
        "source_report_product_success_evidence_allowed": bool(
            report.get("product_success_evidence_allowed")
        ),
        "source_report_holdout_candidate_manifest_contract_version": clean(
            report.get("holdout_candidate_manifest_contract_version")
            or _mapping(report.get("holdout_candidate_manifest_contract")).get("schema_version")
        ),
        "source_report_holdout_candidate_manifest_contract_hash": clean(
            report.get("holdout_candidate_manifest_contract_hash")
            or _mapping(report.get("holdout_candidate_manifest_contract")).get("contract_hash")
        ),
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_source_report_inputs(
    *,
    v4_5_report: Mapping[str, Any],
    v4_5_1_report: Mapping[str, Any],
    v4_5_2_report: Mapping[str, Any],
    v4_5_3_report: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "v4_5": source_report_input(
            input_key="v4_5",
            run_id=v45.RUN_ID,
            report_json=v45.REPORT_JSON,
            report=v4_5_report,
        ),
        "v4_5_1": source_report_input(
            input_key="v4_5_1",
            run_id=v451.RUN_ID,
            report_json=v451.REPORT_JSON,
            report=v4_5_1_report,
        ),
        "v4_5_2": source_report_input(
            input_key="v4_5_2",
            run_id=v452.RUN_ID,
            report_json=v452.REPORT_JSON,
            report=v4_5_2_report,
        ),
        "v4_5_3": source_report_input(
            input_key="v4_5_3",
            run_id=v453.RUN_ID,
            report_json=v453.REPORT_JSON,
            report=v4_5_3_report,
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)


def _first_present_bool(report: Mapping[str, Any], key: str) -> bool:
    metrics = _mapping(report.get("metrics"))
    guardrails = _mapping(report.get("guardrails"))
    summary = _mapping(report.get("summary"))
    for scope in (report, metrics, guardrails, summary):
        if key in scope:
            return _bool_value(scope.get(key))
    return False


def _first_present_int(report: Mapping[str, Any], key: str) -> int:
    metrics = _mapping(report.get("metrics"))
    guardrails = _mapping(report.get("guardrails"))
    summary = _mapping(report.get("summary"))
    for scope in (report, metrics, guardrails, summary):
        if key in scope:
            return _int_value(scope.get(key))
    return 0


def source_report_contract(
    *,
    report: Mapping[str, Any],
    expected_run_id: str,
    expected_schema_version: str,
    required_true: Mapping[str, bool] | None = None,
    required_false: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    checks = {
        "report_loaded": bool(report),
        "run_id_matches": clean(report.get("run_id")) == expected_run_id,
        "schema_version_matches": clean(report.get("schema_version")) == expected_schema_version,
        "diagnostic_only": report.get("diagnostic_only") is True,
        "official_metric_false": report.get("official_metric") is False,
        "official_metric_input_rows_zero": _first_present_int(report, "official_metric_input_rows") == 0,
        "promotion_evidence_false": report.get("promotion_evidence") is False,
        "product_success_evidence_allowed_false": report.get("product_success_evidence_allowed") is False,
        "fine_tuning_dataset_export_not_created": not _first_present_bool(
            report, "fine_tuning_dataset_export_created"
        ),
        "training_job_not_created": not _first_present_bool(report, "training_job_created"),
        "model_or_adapter_checkpoint_not_written": not _first_present_bool(
            report, "model_or_adapter_checkpoint_written"
        ),
        "single_report_artifact_contract": _first_present_bool(report, "single_report_artifact_contract"),
        "sidecar_primary_artifacts_suppressed": _first_present_bool(
            report, "sidecar_primary_artifacts_suppressed"
        ),
        "review_csv_not_created": not _first_present_bool(report, "review_csv_created"),
    }
    for key, value in (required_true or {}).items():
        checks[key] = value is True
    for key, value in (required_false or {}).items():
        checks[key] = value is False
    failed_checks = [key for key, value in checks.items() if value is not True]
    return {
        "passed": not failed_checks,
        "failed_checks": failed_checks,
    }


def v4_5_2_prior_hash_matches_v4_5_3(
    *,
    v4_5_2_report: Mapping[str, Any],
    v4_5_3_prior_identity_hash_set_sha256: str,
) -> bool:
    v452_summary = _mapping(v4_5_2_report.get("prior_identity_summary_report"))
    v452_hash = clean(v452_summary.get("prior_identity_hash_set_sha256"))
    return bool(v452_hash and v4_5_3_prior_identity_hash_set_sha256 and v452_hash == v4_5_3_prior_identity_hash_set_sha256)


def holdout_candidate_manifest_contract_hash_matches(report: Mapping[str, Any]) -> bool:
    contract = _mapping(report.get("holdout_candidate_manifest_contract"))
    report_hash = clean(report.get("holdout_candidate_manifest_contract_hash") or contract.get("contract_hash"))
    report_version = clean(
        report.get("holdout_candidate_manifest_contract_version") or contract.get("schema_version")
    )
    return (
        report_version == holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
        and report_hash == holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
    )


def _gate(
    *,
    name: str,
    passed: bool,
    source_run_id: str,
    source_report_json: Path,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_{name}_v1",
        "run_id": RUN_ID,
        "gate": name,
        "passed": passed,
        "source_run_id": source_run_id,
        "source_report_json": repo_relative(source_report_json),
        "evidence": dict(evidence or {}),
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_preflight_gates(
    *,
    v4_5_report: Mapping[str, Any],
    v4_5_1_report: Mapping[str, Any],
    v4_5_2_report: Mapping[str, Any],
    v4_5_3_report: Mapping[str, Any],
    user_owned_policy_opened: bool = False,
    official_denominator_policy_opened: bool = False,
    promotion_policy_opened: bool = False,
) -> dict[str, dict[str, Any]]:
    v45_metrics = _mapping(v4_5_report.get("metrics"))
    v451_gate = _mapping(v4_5_1_report.get("candidate_intake_gate"))
    v452_gate = _mapping(v4_5_2_report.get("source_identity_audit_gate"))
    v453_summary = _mapping(v4_5_3_report.get("prior_identity_ledger_summary"))
    v453_metrics = _mapping(v4_5_3_report.get("metrics"))
    v453_source_inputs = _mapping(v4_5_3_report.get("source_registry_inputs"))
    v453_hash_count = _int_value(
        v4_5_3_report.get("prior_identity_hash_record_count")
        or v453_metrics.get("prior_identity_hash_record_count")
        or v453_summary.get("prior_identity_hash_record_count")
    )
    v453_source_rows_scanned = _int_value(
        v453_source_inputs.get("rows_scanned")
        or v453_metrics.get("source_registry_pdf_xlsx_rows_scanned")
    )
    v453_source_registry_sha256 = clean(v453_source_inputs.get("source_atom_registry_jsonl_sha256"))
    v453_prior_identity_hash_set_sha256 = clean(
        v453_summary.get("prior_identity_hash_set_sha256")
        or v4_5_3_report.get("prior_identity_hash_set_sha256")
    )
    v453_hash_algorithm = clean(
        v453_summary.get("identity_key_hash_algorithm")
        or v4_5_3_report.get("identity_key_hash_algorithm")
    )
    v45_contract = source_report_contract(
        report=v4_5_report,
        expected_run_id=v45.RUN_ID,
        expected_schema_version=v45.REPORT_SCHEMA_VERSION,
        required_true={
            "route_policy_projection_recorded": _first_present_bool(
                v4_5_report, "route_policy_projection_recorded"
            ),
        },
        required_false={
            "ft_route_policy_dry_run_executed_false": _first_present_bool(
                v4_5_report, "ft_route_policy_dry_run_executed"
            ),
        },
    )
    v451_contract = source_report_contract(
        report=v4_5_1_report,
        expected_run_id=v451.RUN_ID,
        expected_schema_version=v451.REPORT_SCHEMA_VERSION,
        required_true={
            "holdout_candidate_manifest_contract_hash_matches": (
                holdout_candidate_manifest_contract_hash_matches(v4_5_1_report)
            ),
        },
        required_false={
            "candidate_manifest_jsonl_created_false": _first_present_bool(
                v4_5_1_report, "candidate_manifest_jsonl_created"
            ),
            "candidate_validation_jsonl_created_false": _first_present_bool(
                v4_5_1_report, "candidate_validation_jsonl_created"
            ),
        },
    )
    v452_contract = source_report_contract(
        report=v4_5_2_report,
        expected_run_id=v452.RUN_ID,
        expected_schema_version=v452.REPORT_SCHEMA_VERSION,
        required_true={
            "holdout_candidate_manifest_contract_hash_matches": (
                holdout_candidate_manifest_contract_hash_matches(v4_5_2_report)
            ),
            "prior_identity_summary_report_present": bool(
                v4_5_2_report.get("prior_identity_summary_report_present")
                and _mapping(v4_5_2_report.get("prior_identity_summary_report"))
            ),
        },
        required_false={
            "candidate_manifest_jsonl_created_false": _first_present_bool(
                v4_5_2_report, "candidate_manifest_jsonl_created"
            ),
            "source_identity_audit_jsonl_created_false": _first_present_bool(
                v4_5_2_report, "source_identity_audit_jsonl_created"
            ),
        },
    )
    v453_contract = source_report_contract(
        report=v4_5_3_report,
        expected_run_id=v453.RUN_ID,
        expected_schema_version=v453.REPORT_SCHEMA_VERSION,
        required_true={
            "holdout_candidate_manifest_contract_hash_matches": (
                holdout_candidate_manifest_contract_hash_matches(v4_5_3_report)
            ),
        },
        required_false={
            "prior_identity_ledger_jsonl_created_false": _first_present_bool(
                v4_5_3_report, "prior_identity_ledger_jsonl_created"
            ),
        },
    )
    v452_prior_hash_matches_v453 = v4_5_2_prior_hash_matches_v4_5_3(
        v4_5_2_report=v4_5_2_report,
        v4_5_3_prior_identity_hash_set_sha256=v453_prior_identity_hash_set_sha256,
    )
    v453_passed = (
        v453_contract["passed"] is True
        and v4_5_3_report.get("prior_identity_collision_baseline_available") is True
        and v4_5_3_report.get("raw_source_identity_values_embedded") is False
        and v4_5_3_report.get("raw_local_path_values_exposed") is False
        and v4_5_3_report.get("prior_identity_ledger_jsonl_created") is False
        and v453_hash_count > 0
        and v453_source_rows_scanned > 0
        and bool(v453_source_registry_sha256)
        and bool(v453_prior_identity_hash_set_sha256)
        and v453_hash_algorithm == "sha256(family:identity_key)"
    )
    return {
        "v4_5_readiness_gate": _gate(
            name="v4_5_readiness_gate",
            passed=bool(v45_metrics.get("readiness_gate_passed")) and v45_contract["passed"] is True,
            source_run_id=v45.RUN_ID,
            source_report_json=v45.REPORT_JSON,
            evidence={
                "source_report_contract": dict(v45_contract),
                "readiness_decision": clean(v4_5_report.get("readiness_decision")),
                "split_quality_gate_passed": bool(v45_metrics.get("split_quality_gate_passed")),
                "leakage_audit_gate_passed": bool(v45_metrics.get("leakage_audit_gate_passed")),
                "fine_tuning_dataset_exports_created": int(
                    v45_metrics.get("fine_tuning_dataset_exports_created") or 0
                ),
            },
        ),
        "v4_5_1_candidate_intake_gate": _gate(
            name="v4_5_1_candidate_intake_gate",
            passed=bool(v451_gate.get("passed")) and v451_contract["passed"] is True,
            source_run_id=v451.RUN_ID,
            source_report_json=v451.REPORT_JSON,
            evidence={
                "source_report_contract": dict(v451_contract),
                "candidate_manifest_present": bool(v4_5_1_report.get("candidate_manifest_present")),
                "candidate_manifest_rows": int(v4_5_1_report.get("candidate_manifest_rows") or 0),
            },
        ),
        "v4_5_2_source_identity_audit_gate": _gate(
            name="v4_5_2_source_identity_audit_gate",
            passed=(
                bool(v452_gate.get("passed"))
                and v452_contract["passed"] is True
                and v452_prior_hash_matches_v453
            ),
            source_run_id=v452.RUN_ID,
            source_report_json=v452.REPORT_JSON,
            evidence={
                "source_report_contract": dict(v452_contract),
                "prior_identity_baseline_present": bool(v4_5_2_report.get("prior_identity_baseline_present")),
                "prior_identity_summary_report_present": bool(
                    v4_5_2_report.get("prior_identity_summary_report_present")
                ),
                "prior_identity_hash_set_matches_v4_5_3": v452_prior_hash_matches_v453,
                "source_identity_collision_count": int(v452_gate.get("source_identity_collision_count") or 0),
            },
        ),
        "v4_5_3_prior_identity_baseline_gate": _gate(
            name="v4_5_3_prior_identity_baseline_gate",
            passed=v453_passed,
            source_run_id=v453.RUN_ID,
            source_report_json=v453.REPORT_JSON,
            evidence={
                "source_report_contract": dict(v453_contract),
                "prior_identity_hash_record_count": v453_hash_count,
                "source_registry_rows_scanned": v453_source_rows_scanned,
                "source_atom_registry_jsonl_sha256_present": bool(v453_source_registry_sha256),
                "source_atom_registry_jsonl_sha256": v453_source_registry_sha256,
                "prior_identity_hash_set_sha256": v453_prior_identity_hash_set_sha256,
                "identity_key_hash_algorithm": v453_hash_algorithm,
                "raw_source_identity_values_embedded": bool(
                    v4_5_3_report.get("raw_source_identity_values_embedded")
                ),
                "raw_local_path_values_exposed": bool(v4_5_3_report.get("raw_local_path_values_exposed")),
            },
        ),
        "user_owned_gold_policy_gate": _gate(
            name="user_owned_gold_policy_gate",
            passed=user_owned_policy_opened,
            source_run_id="user_owned_policy",
            source_report_json=REPORT_JSON,
            evidence={"status": "pending_user_owned_gold_qrels_label_policy"},
        ),
        "official_denominator_gate": _gate(
            name="official_denominator_gate",
            passed=official_denominator_policy_opened,
            source_run_id="user_owned_policy",
            source_report_json=REPORT_JSON,
            evidence={"official_metric_input_rows": 0},
        ),
        "promotion_policy_gate": _gate(
            name="promotion_policy_gate",
            passed=promotion_policy_opened,
            source_run_id="user_owned_policy",
            source_report_json=REPORT_JSON,
            evidence={"promotion_evidence": False, "product_success_evidence_allowed": False},
        ),
    }


def all_preflight_gates_passed(gates: Mapping[str, Mapping[str, Any]]) -> bool:
    return all(bool(gate.get("passed")) for gate in gates.values())


def blocked_reasons_for_preflight(gates: Mapping[str, Mapping[str, Any]]) -> list[str]:
    reasons: list[str] = []
    if not gates["v4_5_readiness_gate"]["passed"]:
        reasons.append("v4_5_readiness_gate_failed")
    if not gates["v4_5_1_candidate_intake_gate"]["passed"]:
        reasons.append("v4_5_1_candidate_intake_gate_failed")
    if not gates["v4_5_2_source_identity_audit_gate"]["passed"]:
        reasons.append("v4_5_2_source_identity_audit_gate_failed")
    if not gates["v4_5_3_prior_identity_baseline_gate"]["passed"]:
        reasons.append("v4_5_3_prior_identity_baseline_gate_failed")
    if not gates["user_owned_gold_policy_gate"]["passed"]:
        reasons.append("user_owned_gold_qrels_denominator_policy_pending")
    if not gates["official_denominator_gate"]["passed"]:
        reasons.append("official_denominator_policy_closed")
    if not gates["promotion_policy_gate"]["passed"]:
        reasons.append("promotion_policy_closed")
    return reasons


def build_ft_a_route_policy_preflight(gates: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    opened = all_preflight_gates_passed(gates)
    return {
        "schema_version": f"{RUN_ID}_ft_a_route_policy_preflight_v1",
        "run_id": RUN_ID,
        "lane": "FT-A",
        "purpose": "route/policy/clarification classifier dry-run preflight",
        "target_policy_buckets": list(TARGET_POLICY_BUCKETS),
        "preflight_passed": opened,
        "dry_run_opened": opened,
        "dry_run_executed": False,
        "prompt_payload_created": False,
        "raw_llm_response_payload_created": False,
        "training_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "requires_gpu_when_opened": True,
        "blocked_reasons": blocked_reasons_for_preflight(gates),
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_guardrails() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "source_atom_evidence_bundle_evidence_truth": True,
        "source_atom_registry_canonical_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "full_document_or_workbook_scan_forbidden": True,
        "direct_normalized_answer_value_query_matching_used": False,
        "direct_normalized_value_query_matching_used": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "source_title_or_file_name_shortcut_success_evidence_used": False,
        "prompt_payload_created": False,
        "raw_llm_response_payload_created": False,
        "fine_tuning_dataset_export_created": False,
        "training_job_created": False,
        "training_manifest_jsonl_created": False,
        "model_or_adapter_checkpoint_written": False,
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
        "production_routing": False,
        "official_metric": False,
        "official_metric_lift": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "representative_product_performance": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "v4_6_ft_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "live_db_index_cache_readiness": False,
        "single_report_artifact_contract": True,
        "review_csv_created": False,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_metrics(
    gates: Mapping[str, Mapping[str, Any]],
    ft_a: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "ft_route_policy_dry_run_preflight_only": True,
        "all_preflight_gates_passed": all_preflight_gates_passed(gates),
        "v4_5_readiness_gate_passed": bool(gates["v4_5_readiness_gate"]["passed"]),
        "v4_5_1_candidate_intake_gate_passed": bool(gates["v4_5_1_candidate_intake_gate"]["passed"]),
        "v4_5_2_source_identity_audit_gate_passed": bool(gates["v4_5_2_source_identity_audit_gate"]["passed"]),
        "v4_5_3_prior_identity_baseline_gate_passed": bool(gates["v4_5_3_prior_identity_baseline_gate"]["passed"]),
        "user_owned_gold_policy_gate_passed": bool(gates["user_owned_gold_policy_gate"]["passed"]),
        "official_denominator_gate_passed": bool(gates["official_denominator_gate"]["passed"]),
        "promotion_policy_gate_passed": bool(gates["promotion_policy_gate"]["passed"]),
        "ft_route_policy_dry_run_opened": bool(ft_a["dry_run_opened"]),
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_exports_created": 0,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_report(
    *,
    gates: Mapping[str, Mapping[str, Any]],
    ft_a: Mapping[str, Any],
    metrics: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
    source_report_inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    blocked_reasons = blocked_reasons_for_preflight(gates)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "ft_route_policy_dry_run_preflight_only": True,
        "v4_6_ft_dry_run_opened": bool(ft_a["dry_run_opened"]),
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "fine_tuning_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "production_routing": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "single_report_artifact_contract": True,
        "review_csv_created": False,
        "human_review_required": False,
        "readiness_decision": (
            "ready_to_open_nonprod_ft_a_dry_run"
            if all_preflight_gates_passed(gates)
            else "blocked_pending_v4_5_holdout_identity_and_user_policy_gates"
        ),
        "blocked_reasons": blocked_reasons,
        "artifact_paths": dict(artifact_paths),
        "source_run_references": {
            "v4_5_report_json": repo_relative(v45.REPORT_JSON),
            "v4_5_report_sha256": source_report_inputs["v4_5"]["source_report_sha256"],
            "v4_5_1_report_json": repo_relative(v451.REPORT_JSON),
            "v4_5_1_report_sha256": source_report_inputs["v4_5_1"]["source_report_sha256"],
            "v4_5_2_report_json": repo_relative(v452.REPORT_JSON),
            "v4_5_2_report_sha256": source_report_inputs["v4_5_2"]["source_report_sha256"],
            "v4_5_3_report_json": repo_relative(v453.REPORT_JSON),
            "v4_5_3_report_sha256": source_report_inputs["v4_5_3"]["source_report_sha256"],
        },
        "source_report_inputs": {key: dict(value) for key, value in source_report_inputs.items()},
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
        "preflight_gates": {key: dict(value) for key, value in gates.items()},
        "ft_a_route_policy_preflight": dict(ft_a),
        "metrics": dict(metrics),
        "guardrails": dict(guardrails),
        "guardrail_audit": dict(guardrails),
        "verification": {
            "schema_version": f"{RUN_ID}_verification_v1",
            "run_id": RUN_ID,
            "commands_required_by_goal": [
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py --check",
                "targeted v4_6 preflight tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_6 preflight because no dry run, dataset export, or training job is opened. "
                "Future FT-A training or large LLM workloads should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "v4_5 readiness remains blocked by real holdout and user-owned policy gates.",
            "v4_5_1 has no accepted external candidate manifest by default.",
            "v4_5_2 source-identity audit remains closed without accepted external candidates.",
            "User-owned gold/qrels/denominator and promotion policy remain closed.",
        ],
        "next_recommendation": (
            "Only open the non-production FT-A dry run after v4_5, v4_5_1, v4_5_2, v4_5_3, "
            "and user-owned policy gates pass."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    v4_5_report = load_v4_5_report()
    v4_5_1_report = load_v4_5_1_report()
    v4_5_2_report = load_v4_5_2_report()
    v4_5_3_report = load_v4_5_3_report()
    gates = build_preflight_gates(
        v4_5_report=v4_5_report,
        v4_5_1_report=v4_5_1_report,
        v4_5_2_report=v4_5_2_report,
        v4_5_3_report=v4_5_3_report,
    )
    ft_a = build_ft_a_route_policy_preflight(gates)
    metrics = build_metrics(gates, ft_a)
    guardrails = build_guardrails()
    source_report_inputs = build_source_report_inputs(
        v4_5_report=v4_5_report,
        v4_5_1_report=v4_5_1_report,
        v4_5_2_report=v4_5_2_report,
        v4_5_3_report=v4_5_3_report,
    )
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        gates=gates,
        ft_a=ft_a,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
        source_report_inputs=source_report_inputs,
    )
    return {
        "report": report,
        "preflight_gates": gates,
        "ft_a_route_policy_preflight": ft_a,
        "metrics": metrics,
        "guardrails": guardrails,
        "source_report_inputs": source_report_inputs,
    }


def remove_stale_sidecar_artifacts(target_dir: Path) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()


def assert_single_report_directory(target_dir: Path) -> None:
    unexpected = sorted(path.name for path in target_dir.iterdir() if path.name != "report.json")
    if unexpected:
        raise RuntimeError(f"unexpected v4_6 primary artifacts: {unexpected}")


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
    report["fine_tuning_dataset_export_created"] = False
    report["training_job_created"] = False
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
        "training_manifest_jsonl_created": False,
        "fine_tuning_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
        "preflight_gates": dict(report["preflight_gates"]),
        "source_report_inputs": dict(report["source_report_inputs"]),
        "readiness_decision": report["readiness_decision"],
        "blocked_reasons": list(report["blocked_reasons"]),
        "schema_version": f"{RUN_ID}_status_event_v1",
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v453.replace_marked_entry(path, marker, entry)


def _refresh_docs() -> None:
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v453.v452.v451.v45.v44.v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_6 FT route policy dry-run preflight loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_5_3 external holdout prior source identity ledger summary loop:\n`[^`]+`;",
        "current diagnostic v4_6 FT route policy dry-run preflight loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_5_3 external holdout prior source identity ledger summary loop:\n`{v453.RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")

    readme_text = README.read_text(encoding="utf-8")
    readme_text = re.sub(
        r"Current RAG status: `[^`]+`\.",
        f"Current RAG status: `{EVENT_TYPE}_ready`.",
        readme_text,
        count=1,
    )
    verify_block = (
        "```powershell\n"
        "python -X utf8 -m py_compile "
        "ai\\scripts\\rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py --check\n"
        "python -X utf8 -m pytest ai/tests --rag-current -q\n"
        "```"
    )
    verify_start = readme_text.index("## How To Verify Locally")
    verify_end = readme_text.index("## Repo Map")
    verify_section = readme_text[verify_start:verify_end]
    verify_section = re.sub(
        r"```powershell\n.*?```",
        lambda _match: verify_block,
        verify_section,
        count=1,
        flags=re.DOTALL,
    )
    README.write_text(readme_text[:verify_start] + verify_section + readme_text[verify_end:], encoding="utf-8")

    eval_text = EVAL_README.read_text(encoding="utf-8")
    eval_text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{EVENT_TYPE}_ready`",
        eval_text,
        count=1,
    )
    eval_text = re.sub(
        r"v4_5_3 is `diagnostic_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod_ready`"
        r"(?:; v4_6 is `[^`]+`)?\.",
        f"v4_5_3 is `{v453.EVENT_TYPE}_ready`; v4_6 is `{EVENT_TYPE}_ready`.",
        eval_text,
        count=1,
    )
    EVAL_README.write_text(eval_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py` | "
        "Checks whether the non-production FT-A route/policy dry-run lane may open; it remains preflight-only while v4_5/v4_5_1/v4_5_2/v4_5_3 and user-owned policy gates are closed and emits no dataset, job, checkpoint, raw prompt, raw LLM response, official metric, promotion, or product-success evidence. |"
    )
    pattern = r"\| `rag_v4_6_ft_route_policy_dry_run_preflight_nonprod\.py` \| .*?\|"
    if re.search(pattern, text):
        text = re.sub(pattern, row, text, count=1)
    elif "<!-- v4_diagnostic_runtime_locator_and_finetune_readiness_inventory:end -->" in text:
        text = text.replace(
            "\n<!-- v4_diagnostic_runtime_locator_and_finetune_readiness_inventory:end -->",
            f"\n{row}\n<!-- v4_diagnostic_runtime_locator_and_finetune_readiness_inventory:end -->",
            1,
        )
    else:
        text = text.rstrip() + "\n" + row + "\n"
    scripts_readme.write_text(text, encoding="utf-8")


def update_v4_plan_note() -> None:
    plan_path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    text = plan_path.read_text(encoding="utf-8")
    text = text.replace(
        "official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_nonprod/",
        "official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod/",
    )
    text = text.replace(
        "v4_6_optional_ft_route_policy_dry_run_nonprod",
        "v4_6_ft_route_policy_dry_run_preflight_nonprod",
    )
    text = text.replace(
        "- v4_6 actual FT dry-run should wait for v4_5 readiness gates.",
        "- v4_6 preflight should remain closed until v4_5, v4_5_1, v4_5_2, v4_5_3, and user-owned policy gates pass; any actual FT-A dry run comes later.",
    )
    text = text.replace(
        "- optional nonprod FT-A dry run preserves fail-closed policy and shows diagnostic route-policy movement.",
        "- preflight confirms whether a later optional nonprod FT-A dry run may open; no diagnostic route-policy movement is claimed until the dry run actually runs.",
    )
    plan_path.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    report_path = report["artifact_paths"]["report_json"]
    metrics = report["metrics"]
    _refresh_docs()
    progress_entry = (
        f"- v4_6 FT route policy dry-run preflight (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It persists a preflight-only gate check for the later non-production FT-A route/policy dry run; "
        "no dry run, prompt payload, raw LLM response, dataset, job, checkpoint, official metric, promotion, product evidence, or live readiness is created. "
        "v4_5_3 baseline gate passes, while v4_5, v4_5_1, v4_5_2, and user-owned policy gates remain closed."
    )
    measurements_entry = f"""### v4_6 FT Route Policy Dry-Run Preflight

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, preflight-only, single `report.json`.
- Primary artifact: `{report_path}`
- Source evidence: v4_5/v4_5_1/v4_5_2/v4_5_3 report inputs are hash-locked in `source_report_inputs`; v4_5_3 supplies the hash-only prior identity baseline.

| Diagnostic count | Value |
| --- | ---: |
| ft_route_policy_dry_run_preflight_only | true |
| all_preflight_gates_passed | {str(metrics["all_preflight_gates_passed"]).lower()} |
| v4_5_readiness_gate_passed | {str(metrics["v4_5_readiness_gate_passed"]).lower()} |
| v4_5_1_candidate_intake_gate_passed | {str(metrics["v4_5_1_candidate_intake_gate_passed"]).lower()} |
| v4_5_2_source_identity_audit_gate_passed | {str(metrics["v4_5_2_source_identity_audit_gate_passed"]).lower()} |
| v4_5_3_prior_identity_baseline_gate_passed | {str(metrics["v4_5_3_prior_identity_baseline_gate_passed"]).lower()} |
| user_owned_gold_policy_gate_passed | {str(metrics["user_owned_gold_policy_gate_passed"]).lower()} |
| official_denominator_gate_passed | {str(metrics["official_denominator_gate_passed"]).lower()} |
| promotion_policy_gate_passed | {str(metrics["promotion_policy_gate_passed"]).lower()} |
| ft_route_policy_dry_run_opened | {str(metrics["ft_route_policy_dry_run_opened"]).lower()} |
| ft_route_policy_dry_run_executed | {str(metrics["ft_route_policy_dry_run_executed"]).lower()} |
| fine_tuning_dataset_exports_created | {metrics["fine_tuning_dataset_exports_created"]} |
| official_metric | false |
| official_metric_input_rows | {metrics["official_metric_input_rows"]} |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the preflight gates, source report input hashes, v4_5_3 prior identity hash-set provenance, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no prompt payload, raw LLM response, dataset sidecar, training job, checkpoint, review CSV, or per-run Markdown.
"""
    triage_entry = (
        "### v4_6 FT Route Policy Dry-Run Preflight Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_6 is preflight only and is not the FT-A dry run itself.\n"
        "- The current default run keeps the dry run closed because v4_5, v4_5_1, v4_5_2, and user-owned gold/qrels/denominator policy gates are not open.\n"
        "- v4_5_3 prior identity baseline provenance is accepted only as hash-only SourceAtom-registry-derived evidence; raw source identities and local paths remain unexposed.\n"
        "- SearchView/vector payload remains candidate-only; SourceAtom/EvidenceBundle and the source registry remain evidence truth.\n"
        "- No official metric rows, promotion evidence, product-success evidence, dataset export, training job, checkpoint, production route, or live DB/index/cache readiness claim is created.\n"
        "- GPU is not required for this deterministic preflight; future FT-A training, embedding, or local LLM workloads should use GPU when the gates actually open.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    update_scripts_readme()
    update_v4_plan_note()
    _refresh_docs()


def run_write() -> dict[str, Any]:
    artifacts = build_artifacts()
    report = write_artifacts(artifacts)
    update_docs(report)
    append_status_event(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    report = artifacts["report"]
    if args.check:
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": report["status"],
                    "all_preflight_gates_passed": report["metrics"]["all_preflight_gates_passed"],
                    "ft_route_policy_dry_run_opened": report["metrics"]["ft_route_policy_dry_run_opened"],
                    "ft_route_policy_dry_run_executed": report["metrics"]["ft_route_policy_dry_run_executed"],
                    "fine_tuning_dataset_exports_created": report["metrics"]["fine_tuning_dataset_exports_created"],
                    "training_job_created": report["metrics"]["training_job_created"],
                    "official_metric_input_rows": report["metrics"]["official_metric_input_rows"],
                    "blocked_reasons": report["blocked_reasons"],
                    "gpu_required_for_this_slice": report["metrics"]["gpu_required_for_this_slice"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    written = run_write()
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "report": written["artifact_paths"]["report_json"],
                "status": written["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
