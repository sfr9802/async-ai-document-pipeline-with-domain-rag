from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_5_1_holdout_candidate_intake_gate_nonprod as v451
import rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod as v452
import rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod as v453
import rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod as v466
import rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod as v468
import rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod as v469
from app.capabilities.rag import holdout_manifest_contract


ROOT = v469.ROOT
REPORT_DIR = v469.REPORT_DIR
STATUS_JSONL = v469.STATUS_JSONL
PROGRESS_DOC = v469.PROGRESS_DOC
MEASUREMENTS_DOC = v469.MEASUREMENTS_DOC
TRIAGE_DOC = v469.TRIAGE_DOC
README = v469.README
EVAL_README = v469.EVAL_README

V4_NAME = v469.V4_NAME
V4_RUN_FAMILY = v469.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod"
EVENT_TYPE = "diagnostic_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod"
STATUS = "DIAGNOSTIC_V4_6_10_EXTERNAL_HOLDOUT_CANDIDATE_MANIFEST_GATE_REPLAY_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_report_v1"

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "candidate_manifest.jsonl",
            "candidate_validation.jsonl",
            "dry_run_execution_plan.json",
            "dry_run_input_manifest.jsonl",
            "external_holdout_candidate_manifest_gate_replay.json",
            "metrics.json",
            "official_metric_input_rows.jsonl",
            "official_metric_opening_preflight.json",
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

USER_OWNED_REQUIRED_INPUTS = (
    "official_denominator_policy",
    "relevance_labels",
    "answerability_labels",
    "qrels_policy",
    "expected_answer_evidence_policy",
    "promotion_threshold_policy",
)


def clean(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    return v469.repo_relative(path)


def utc_now() -> str:
    return v469.utc_now()


def sha256_file(path: Path) -> str:
    return v469.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v469.read_json(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v469.write_json(path, payload)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v469.read_jsonl(path)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v469.write_jsonl(path, rows)


def _mapping_value(source: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = source.get(key)
    return value if isinstance(value, Mapping) else {}


def _source_report_input(name: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    report = read_json(path) if exists else {}
    actual_sha = sha256_file(path) if exists else ""
    embedded_contract = _mapping_value(report, "holdout_candidate_manifest_contract")
    candidate_intake_gate = _mapping_value(report, "candidate_intake_gate")
    source_identity_audit_gate = _mapping_value(report, "source_identity_audit_gate")
    contract_version = clean(
        report.get("holdout_candidate_manifest_contract_version")
        or embedded_contract.get("schema_version")
        or candidate_intake_gate.get("holdout_candidate_manifest_contract_version")
        or source_identity_audit_gate.get("holdout_candidate_manifest_contract_version")
    )
    contract_hash = clean(
        report.get("holdout_candidate_manifest_contract_hash")
        or embedded_contract.get("contract_hash")
        or candidate_intake_gate.get("holdout_candidate_manifest_contract_hash")
        or source_identity_audit_gate.get("holdout_candidate_manifest_contract_hash")
    )
    return {
        "source_report_name": name,
        "source_report_json": repo_relative(path),
        "source_report_exists": exists,
        "source_report_sha256": actual_sha,
        "source_report_hash_current": bool(exists and actual_sha),
        "source_run_id": clean(report.get("run_id")),
        "source_report_schema_version": clean(report.get("schema_version")),
        "source_report_diagnostic_only": bool(report.get("diagnostic_only", True)),
        "official_metric": bool(report.get("official_metric")),
        "official_metric_input_rows": int(report.get("official_metric_input_rows") or 0),
        "official_metric_lift": bool(report.get("official_metric_lift")),
        "promotion_evidence": bool(report.get("promotion_evidence")),
        "product_success_evidence_allowed": bool(report.get("product_success_evidence_allowed")),
        "candidate_manifest_present": bool(report.get("candidate_manifest_present")),
        "candidate_manifest_exported": bool(report.get("candidate_manifest_exported")),
        "real_holdout_sufficient": bool(report.get("real_holdout_sufficient")),
        "v4_7_official_metric_gate_opened": bool(report.get("v4_7_official_metric_gate_opened")),
        "live_db_index_cache_readiness": bool(report.get("live_db_index_cache_readiness")),
        "source_report_holdout_candidate_manifest_contract_version": contract_version,
        "source_report_holdout_candidate_manifest_contract_hash": contract_hash,
        "source_report_holdout_candidate_manifest_contract_hash_matches": bool(
            contract_hash
            and contract_hash == holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
        ),
    }


def build_source_report_inputs() -> dict[str, dict[str, Any]]:
    return {
        "v4_5_1": _source_report_input("v4_5_1", v451.REPORT_JSON),
        "v4_5_2": _source_report_input("v4_5_2", v452.REPORT_JSON),
        "v4_5_3": _source_report_input("v4_5_3", v453.REPORT_JSON),
        "v4_6_6": _source_report_input("v4_6_6", v466.REPORT_JSON),
        "v4_6_8": _source_report_input("v4_6_8", v468.REPORT_JSON),
        "v4_6_9": _source_report_input("v4_6_9", v469.REPORT_JSON),
    }


def _load_report(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def _reason_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    reasons = Counter(clean(row.get("exclusion_reason")) for row in rows if clean(row.get("exclusion_reason")))
    return dict(sorted(reasons.items()))


def _manifest_input_for_v4_6_10(metadata: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["input_only_replay"] = True
    payload["raw_local_path_exposed"] = False
    if payload.get("provided") is True:
        payload["path_label"] = "__external_candidate_manifest_path_redacted__"
        payload["path_kind"] = "external_redacted"
    return payload


def _default_prior_identity_summary_report() -> dict[str, Any]:
    return _load_report(v453.REPORT_JSON)


def build_external_holdout_candidate_manifest_gate_replay(
    source_inputs: Mapping[str, Mapping[str, Any]],
    *,
    candidate_manifest_path: Path | None = None,
    prior_identity_rows: Sequence[Mapping[str, Any]] | None = None,
    prior_identity_summary_report: Mapping[str, Any] | None = None,
    prior_identity_summary_report_path: Path | None = None,
    minimum_targets: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    v451_report = _load_report(v451.REPORT_JSON)
    v452_report = _load_report(v452.REPORT_JSON)
    v468_report = _load_report(v468.REPORT_JSON)
    v469_report = _load_report(v469.REPORT_JSON)
    acquisition = dict(v468_report.get("holdout_acquisition_requirements") or {})
    intake_gate = dict(v451_report.get("candidate_intake_gate") or {})
    source_audit_gate = dict(v452_report.get("source_identity_audit_gate") or {})
    duplicate_gate = dict(v469_report.get("duplicate_hygiene_gate") or {})
    targets = dict(minimum_targets or acquisition.get("minimum_targets") or intake_gate.get("minimum_targets") or {})
    contract = holdout_manifest_contract.build_holdout_candidate_manifest_contract()
    manifest_rows, candidate_manifest_input_raw = v452.load_candidate_manifest_rows(candidate_manifest_path)
    candidate_manifest_input = _manifest_input_for_v4_6_10(candidate_manifest_input_raw)
    prior_summary_input: dict[str, Any] = {
        "provided": prior_identity_summary_report is not None or prior_identity_summary_report_path is not None,
        "defaulted_from_v4_5_3_report": False,
        "load_error": "",
        "raw_local_path_exposed": False,
    }
    if prior_identity_summary_report is not None:
        prior_summary = dict(prior_identity_summary_report)
    elif prior_identity_summary_report_path is not None:
        prior_summary, prior_summary_input = v452.load_prior_identity_summary_report(prior_identity_summary_report_path)
    else:
        prior_summary = _default_prior_identity_summary_report()
        prior_summary_input["defaulted_from_v4_5_3_report"] = bool(prior_summary)
        prior_summary_input["default_source_run_id"] = v453.RUN_ID if prior_summary else ""

    if candidate_manifest_path is not None:
        intake_validation = v451.validate_holdout_candidate_rows(manifest_rows, minimum_targets=targets)
        intake_gate = dict(intake_validation["candidate_intake_gate"])
        source_audit = v452.audit_candidate_rows_against_prior_identities(
            manifest_rows,
            prior_identity_rows or (),
            prior_identity_summary_report=prior_summary,
            minimum_targets=targets,
        )
        source_audit_gate = dict(source_audit["source_identity_audit_gate"])
        source_audit_exclusion_reasons = _reason_counts(source_audit.get("excluded_candidates") or ())
    else:
        source_audit = {}
        source_audit_exclusion_reasons = {}

    all_source_reports_current = all(bool(item.get("source_report_hash_current")) for item in source_inputs.values())
    source_reports_closed = all(
        int(item.get("official_metric_input_rows") or 0) == 0
        and item.get("official_metric") is False
        and item.get("official_metric_lift") is False
        and item.get("promotion_evidence") is False
        and item.get("product_success_evidence_allowed") is False
        and item.get("candidate_manifest_exported") is False
        and item.get("v4_7_official_metric_gate_opened") is False
        and item.get("live_db_index_cache_readiness") is False
        for item in source_inputs.values()
    )
    codex_owned_dependencies_passed = (
        all_source_reports_current
        and source_reports_closed
        and duplicate_gate.get("gate_passed") is True
        and duplicate_gate.get("runtime_invalid_first_duplicate_rejected") is True
        and duplicate_gate.get("script_invalid_first_duplicate_rejected") is True
    )
    candidate_manifest_present = bool(manifest_rows)
    intake_gate_passed = bool(intake_gate.get("passed"))
    source_identity_audit_gate_passed = bool(source_audit_gate.get("passed"))
    candidate_gate_target_sufficient = bool(
        candidate_manifest_present and intake_gate_passed and source_identity_audit_gate_passed
    )
    blocked_reasons: list[str] = []
    for load_error in (
        clean(candidate_manifest_input.get("load_error")),
        clean(prior_summary_input.get("load_error")),
    ):
        if load_error and load_error not in blocked_reasons:
            blocked_reasons.append(load_error)
    if not candidate_manifest_present:
        blocked_reasons.append("external_holdout_candidate_manifest_missing")
    if candidate_manifest_present and not intake_gate_passed:
        blocked_reasons.append("candidate_intake_gate_failed")
    if candidate_manifest_present and not source_identity_audit_gate_passed:
        blocked_reasons.append("source_identity_audit_failed")
    if not candidate_gate_target_sufficient:
        blocked_reasons.append("candidate_gate_target_sufficient_false")
    blocked_reasons.append("real_holdout_sufficient_false")
    return {
        "schema_version": f"{RUN_ID}_manifest_gate_replay_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "external_holdout_candidate_manifest_gate_replay_only": True,
        "holdout_candidate_manifest_contract_version": contract["schema_version"],
        "holdout_candidate_manifest_contract_hash_algorithm": contract["contract_hash_algorithm"],
        "holdout_candidate_manifest_contract_hash": contract["contract_hash"],
        "gate_passed": False,
        "gate_opened": False,
        "candidate_manifest_present": candidate_manifest_present,
        "candidate_manifest_input_only": True,
        "candidate_manifest_input": candidate_manifest_input,
        "candidate_manifest_exported": False,
        "candidate_rows_replayed": len(manifest_rows),
        "accepted_pdf_holdout_candidates": int(
            intake_gate.get("accepted_holdout_candidate_counts", {}).get("PDF_source_document_disjoint") or 0
        ),
        "accepted_xlsx_holdout_candidates": int(
            intake_gate.get("accepted_holdout_candidate_counts", {}).get("XLSX_workbook_disjoint") or 0
        ),
        "accepted_text_control_candidates": int(
            intake_gate.get("accepted_holdout_candidate_counts", {}).get("TEXT_control_only") or 0
        ),
        "accepted_holdout_candidate_counts": dict(intake_gate.get("accepted_holdout_candidate_counts") or {}),
        "real_query_fidelity_included_counts": dict(
            intake_gate.get("real_query_fidelity_included_counts")
            or source_audit_gate.get("real_query_fidelity_included_counts")
            or {}
        ),
        "excluded_candidate_count": int(intake_gate.get("excluded_candidate_count") or 0),
        "minimum_targets": dict(targets or intake_gate.get("minimum_targets") or {}),
        "family_deficits": dict(acquisition.get("deficits") or {}),
        "candidate_intake_exclusion_reasons": _reason_counts(
            (intake_validation.get("excluded_candidates") if candidate_manifest_path is not None else ()) or ()
        ),
        "source_identity_audit_exclusion_reasons": source_audit_exclusion_reasons,
        "source_identity_collision_count": int(source_audit_gate.get("source_identity_collision_count") or 0),
        "source_identity_audit_excluded_count": int(source_audit_gate.get("source_identity_audit_excluded_count") or 0),
        "prior_identity_baseline_present": bool(source_audit_gate.get("prior_identity_baseline_present")),
        "prior_identity_hash_summary_rows": int(source_audit_gate.get("prior_identity_hash_summary_rows") or 0),
        "prior_identity_summary_report_input": {
            key: value
            for key, value in prior_summary_input.items()
            if key
            in {
                "provided",
                "exists",
                "format",
                "path_label",
                "path_kind",
                "sha256",
                "load_error",
                "raw_local_path_exposed",
                "defaulted_from_v4_5_3_report",
                "default_source_run_id",
            }
        },
        "v4_5_1_intake_gate_replay_source": repo_relative(v451.REPORT_JSON),
        "v4_5_2_source_identity_audit_replay_source": repo_relative(v452.REPORT_JSON),
        "v4_6_9_duplicate_hygiene_source": repo_relative(v469.REPORT_JSON),
        "v4_5_1_intake_gate_passed": intake_gate_passed,
        "v4_5_2_source_identity_audit_gate_passed": source_identity_audit_gate_passed,
        "v4_6_9_duplicate_hygiene_gate_passed": bool(duplicate_gate.get("gate_passed")),
        "candidate_gate_target_sufficient": candidate_gate_target_sufficient,
        "all_source_report_hashes_current": all_source_reports_current,
        "source_reports_closed": source_reports_closed,
        "codex_owned_dependency_checks_passed": codex_owned_dependencies_passed,
        "real_holdout_sufficient": False,
        "real_holdout_sufficiency_not_claimed_reason": (
            "candidate_manifest_replay_input_remains_non_official_until_user_policy_and_external_review"
        ),
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "blocked_reasons": blocked_reasons,
    }


def build_official_metric_opening_preflight(
    replay: Mapping[str, Any],
) -> dict[str, Any]:
    required_inputs = [
        {
            "input_name": input_name,
            "present": False,
            "user_owned": True,
        }
        for input_name in USER_OWNED_REQUIRED_INPUTS
    ]
    missing = [row["input_name"] for row in required_inputs if row["present"] is False]
    return {
        "schema_version": f"{RUN_ID}_official_metric_opening_preflight_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "gate_passed": False,
        "gate_opened": False,
        "mechanical_policy_application_allowed": False,
        "official_metric_rows_authorized": False,
        "required_user_owned_inputs": required_inputs,
        "user_owned_required_input_count": len(required_inputs),
        "user_owned_required_inputs_present_count": len(required_inputs) - len(missing),
        "missing_user_owned_input_count": len(missing),
        "missing_user_owned_inputs": missing,
        "codex_owned_dependency_checks_passed": bool(replay.get("codex_owned_dependency_checks_passed")),
        "candidate_manifest_present": bool(replay.get("candidate_manifest_present")),
        "candidate_manifest_exported": bool(replay.get("candidate_manifest_exported")),
        "real_holdout_sufficient": bool(replay.get("real_holdout_sufficient")),
        "dry_run_input_manifest_exported": bool(replay.get("dry_run_input_manifest_exported")),
        "ft_route_policy_dry_run_opened": bool(replay.get("ft_route_policy_dry_run_opened")),
        "ft_route_policy_dry_run_executed": bool(replay.get("ft_route_policy_dry_run_executed")),
        "v4_7_official_metric_gate_opened": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
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
        "source_atom_evidence_bundle_evidence_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "raw_candidate_rows_embedded": False,
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "source_atom_registry_mutated": False,
        "db_or_production_namespace_written": False,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_query_matching_used": False,
        "protected_namespaces_touched": [],
        "review_csv_created": False,
        "review_packet_created": False,
        "single_report_artifact_contract": True,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def forbidden_surface_violation_count(payload: Mapping[str, Any]) -> int:
    forbidden_true_keys = {
        "candidate_manifest_exported",
        "candidate_manifest_jsonl_created",
        "candidate_validation_jsonl_created",
        "dry_run_execution_plan_exported",
        "dry_run_input_manifest_exported",
        "fine_tuning_dataset_export_created",
        "ft_route_policy_dry_run_executed",
        "ft_route_policy_dry_run_opened",
        "live_db_index_cache_readiness",
        "model_or_adapter_checkpoint_written",
        "official_metric",
        "product_success_evidence_allowed",
        "promotion_evidence",
        "prompt_manifest_created",
        "prompt_payload_created",
        "raw_llm_response_payload_created",
        "review_csv_created",
        "source_identity_audit_jsonl_created",
        "training_job_created",
        "training_manifest_jsonl_created",
        "v4_7_official_metric_gate_opened",
    }
    forbidden_nonzero_keys = {
        "fine_tuning_dataset_exports_created",
        "official_metric_input_rows",
        "official_metric_rows_created",
    }
    count = 0

    def visit(value: Any, key: str = "") -> None:
        nonlocal count
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
            return
        if key in forbidden_true_keys and value is True:
            count += 1
        if key in forbidden_nonzero_keys and int(value or 0) != 0:
            count += 1

    visit(payload)
    return count


def raw_source_identity_or_path_leak_count(payload: Mapping[str, Any]) -> int:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    patterns = (r"[A-Za-z]:/", r"\\\\", "shadowed", "pdf-invalid-first", "source_identity_key")
    return sum(1 for pattern in patterns if re.search(pattern, serialized))


def build_artifacts(
    *,
    candidate_manifest_path: Path | None = None,
    prior_identity_rows: Sequence[Mapping[str, Any]] | None = None,
    prior_identity_summary_report: Mapping[str, Any] | None = None,
    prior_identity_summary_report_path: Path | None = None,
    minimum_targets: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    source_inputs = build_source_report_inputs()
    contract = holdout_manifest_contract.build_holdout_candidate_manifest_contract()
    replay = build_external_holdout_candidate_manifest_gate_replay(
        source_inputs,
        candidate_manifest_path=candidate_manifest_path,
        prior_identity_rows=prior_identity_rows,
        prior_identity_summary_report=prior_identity_summary_report,
        prior_identity_summary_report_path=prior_identity_summary_report_path,
        minimum_targets=minimum_targets,
    )
    preflight = build_official_metric_opening_preflight(replay)
    guardrails = build_guardrails()
    metrics = {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "external_holdout_candidate_manifest_gate_replay_only": True,
        "gate_passed": False,
        "gate_opened": False,
        "candidate_manifest_present": bool(replay["candidate_manifest_present"]),
        "candidate_manifest_exported": False,
        "candidate_rows_replayed": int(replay["candidate_rows_replayed"]),
        "accepted_pdf_holdout_candidates": replay["accepted_pdf_holdout_candidates"],
        "accepted_xlsx_holdout_candidates": replay["accepted_xlsx_holdout_candidates"],
        "real_holdout_sufficient": False,
        "codex_owned_dependency_checks_passed": replay["codex_owned_dependency_checks_passed"],
        "missing_user_owned_input_count": preflight["missing_user_owned_input_count"],
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "fine_tuning_dataset_exports_created": 0,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "review_csv_created": False,
    }
    blocked_reasons = [
        *list(replay.get("blocked_reasons") or []),
        "candidate_manifest_export_remains_closed",
        "dry_run_input_manifest_not_exported",
        "ft_route_policy_dry_run_not_opened",
        "v4_7_official_metric_gate_not_opened",
        "user_owned_official_denominator_policy_missing",
        "user_owned_relevance_labels_missing",
        "user_owned_answerability_labels_missing",
        "user_owned_qrels_policy_missing",
        "user_owned_expected_answer_evidence_policy_missing",
        "user_owned_promotion_threshold_policy_missing",
    ]
    blocked_reasons = list(dict.fromkeys(blocked_reasons))
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "holdout_candidate_manifest_contract": contract,
        "holdout_candidate_manifest_contract_version": contract["schema_version"],
        "holdout_candidate_manifest_contract_hash_algorithm": contract["contract_hash_algorithm"],
        "holdout_candidate_manifest_contract_hash": contract["contract_hash"],
        "external_holdout_candidate_manifest_gate_replay_only": True,
        "external_holdout_candidate_manifest_gate_replay": replay,
        "official_metric_opening_preflight": preflight,
        "source_report_inputs": source_inputs,
        "metrics": metrics,
        "guardrails": guardrails,
        "guardrail_audit": dict(guardrails),
        "candidate_manifest_present": bool(replay["candidate_manifest_present"]),
        "candidate_manifest_exported": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
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
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "review_csv_created": False,
        "single_report_artifact_contract": True,
        "artifact_paths": {"report_json": repo_relative(REPORT_JSON)},
        "summary": {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "status": STATUS,
            "diagnostic_only": True,
            "external_holdout_candidate_manifest_gate_replay_only": True,
            "gate_passed": False,
            "candidate_manifest_present": bool(replay["candidate_manifest_present"]),
            "candidate_rows_replayed": int(replay["candidate_rows_replayed"]),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
        },
        "blocked_reasons": blocked_reasons,
        "readiness_decision": (
            "blocked_pending_user_policy_and_external_holdout_sufficiency_review"
            if replay["candidate_manifest_present"]
            else "blocked_pending_external_holdout_candidate_manifest_and_user_policy"
        ),
        "residual_risks": [
            "This run replays the empty external holdout candidate manifest gate only; it does not acquire candidates.",
            "No real external source-document-disjoint PDF candidate manifest is registered.",
            "No real external workbook-disjoint XLSX candidate manifest is registered.",
            "FT-A dry run, dataset export, job creation, and v4_7 remain unopened.",
        ],
        "next_recommendation": (
            "Register real source-disjoint PDF/XLSX candidate rows as an input-only external manifest, then rerun "
            "v4_5_1, v4_5_2, v4_6_9, and this replay gate before any dry-run manifest or v4_7 opening."
        ),
    }
    return {"report": report}


def remove_stale_sidecar_artifacts(target_dir: Path) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()


def assert_single_report_directory(target_dir: Path) -> None:
    unexpected = sorted(path.name for path in target_dir.iterdir() if path.name != "report.json")
    if unexpected:
        raise RuntimeError(f"unexpected v4_6_10 primary artifacts: {unexpected}")


def write_artifacts(artifacts: Mapping[str, Any], *, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    remove_stale_sidecar_artifacts(output_dir)
    assert_single_report_directory(output_dir)
    report = dict(artifacts["report"])
    report_json = output_dir / "report.json"
    report["artifact_paths"] = {
        "report_json": report_json.as_posix() if output_dir != OUTPUT_DIR else repo_relative(REPORT_JSON)
    }
    report["summary"] = {**dict(report["summary"]), "report_json_created": True}
    write_json(report_json, report)
    assert_single_report_directory(output_dir)
    return report


def update_status(report: Mapping[str, Any]) -> None:
    event = {
        **dict(report["metrics"]),
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": sha256_file(REPORT_JSON)},
        "diagnostic_only": True,
        "external_holdout_candidate_manifest_gate_replay_only": True,
        "protected_namespaces_touched": [],
        "review_csv_created": False,
        "per_run_markdown_created": False,
        "source_report_inputs": dict(report["source_report_inputs"]),
        "blocked_reasons": list(report["blocked_reasons"]),
    }
    rows = [
        row
        for row in read_jsonl(STATUS_JSONL)
        if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)
    ]
    rows.append(event)
    write_jsonl(STATUS_JSONL, rows)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise AssertionError("unexpected v4_6_10 schema")
    replay = report["external_holdout_candidate_manifest_gate_replay"]
    preflight = report["official_metric_opening_preflight"]
    manifest_input = replay.get("candidate_manifest_input") or {}
    expected_contract_hash = holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
    expected_contract_version = holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
    manifest_present = bool(replay.get("candidate_manifest_present"))
    rows_replayed = int(replay.get("candidate_rows_replayed") or 0)
    if report.get("holdout_candidate_manifest_contract_version") != expected_contract_version:
        raise AssertionError("holdout_candidate_manifest_contract_version must match current contract")
    if report.get("holdout_candidate_manifest_contract_hash") != expected_contract_hash:
        raise AssertionError("holdout_candidate_manifest_contract_hash must match current contract")
    if replay.get("holdout_candidate_manifest_contract_version") != expected_contract_version:
        raise AssertionError("replay holdout_candidate_manifest_contract_version must match current contract")
    if replay.get("holdout_candidate_manifest_contract_hash") != expected_contract_hash:
        raise AssertionError("replay holdout_candidate_manifest_contract_hash must match current contract")
    for source_name in ("v4_5_1", "v4_5_2"):
        source_input = dict(report.get("source_report_inputs", {}).get(source_name) or {})
        if source_input.get("source_report_holdout_candidate_manifest_contract_hash_matches") is not True:
            raise AssertionError(f"{source_name} source report contract hash must match current contract")
    if report.get("external_holdout_candidate_manifest_gate_replay_only") is not True:
        raise AssertionError("external holdout manifest gate replay flag must remain true")
    if report.get("candidate_manifest_present") is not manifest_present:
        raise AssertionError("candidate_manifest_present must match replay state")
    if report.get("metrics", {}).get("candidate_manifest_present") is not manifest_present:
        raise AssertionError("metrics candidate_manifest_present must match replay state")
    if manifest_present and manifest_input.get("provided") is not True:
        raise AssertionError("candidate_manifest_present requires input-only manifest metadata")
    if manifest_present and rows_replayed <= 0:
        raise AssertionError("candidate_rows_replayed must be positive when a manifest is present")
    if not manifest_present and rows_replayed != 0:
        raise AssertionError("candidate_rows_replayed must remain 0 without a valid input manifest")
    if manifest_input.get("raw_local_path_exposed") is not False:
        raise AssertionError("candidate_manifest_input must not expose raw local paths")
    if manifest_input.get("path_kind") not in {"not_provided", "external_redacted", "repo_relative"}:
        raise AssertionError("candidate_manifest_input path_kind must be bounded")
    if replay.get("candidate_manifest_input_only") is not True:
        raise AssertionError("candidate manifest replay must remain input-only")
    if preflight.get("gate_opened") is not False:
        raise AssertionError("official metric opening preflight gate must remain closed")
    if any(row.get("present") is True for row in preflight.get("required_user_owned_inputs") or []):
        raise AssertionError("user-owned policy inputs must remain pending")
    if preflight.get("missing_user_owned_input_count") != len(USER_OWNED_REQUIRED_INPUTS):
        raise AssertionError("all user-owned inputs must remain missing")
    for field in (
        "candidate_manifest_exported",
        "candidate_manifest_jsonl_created",
        "candidate_validation_jsonl_created",
        "source_identity_audit_jsonl_created",
        "dry_run_input_manifest_exported",
        "ft_route_policy_dry_run_opened",
        "ft_route_policy_dry_run_executed",
        "v4_7_official_metric_gate_opened",
        "fine_tuning_dataset_export_created",
        "training_manifest_jsonl_created",
        "training_job_created",
        "model_or_adapter_checkpoint_written",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
    ):
        if report.get(field) is not False:
            raise AssertionError(f"{field} must remain false")
    if int(report.get("official_metric_input_rows") or 0) != 0:
        raise AssertionError("official_metric_input_rows must remain 0")
    if report.get("real_holdout_sufficient") is not False:
        raise AssertionError("manifest gate replay must not satisfy real holdout")
    if forbidden_surface_violation_count(report) != 0:
        raise AssertionError("forbidden official, promotion, training, dry-run, or artifact surface opened")
    if raw_source_identity_or_path_leak_count(report) != 0:
        raise AssertionError("raw candidate id, source identity, or local path leaked")


def update_readme() -> None:
    text = README.read_text(encoding="utf-8")
    current_status = f"{EVENT_TYPE}_ready"
    text = re.sub(
        r"Current RAG status: `[^`]+`\.",
        f"Current RAG status: `{current_status}`.",
        text,
        count=1,
    )
    verify_start = text.index("## How To Verify Locally")
    verify_end = text.index("## Repo Map")
    verify_section = text[verify_start:verify_end]
    script = "ai\\scripts\\rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod.py"
    compile_cmd = f"python -X utf8 -m py_compile {script}"
    check_cmd = f"python -X utf8 {script} --check"
    if compile_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod.py\n",
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod.py\n"
            f"{compile_cmd}\n",
            1,
        )
    if check_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 ai\\scripts\\rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod.py --check\n",
            "python -X utf8 ai\\scripts\\rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod.py --check\n"
            f"{check_cmd}\n",
            1,
        )
    README.write_text(text[:verify_start] + verify_section + text[verify_end:], encoding="utf-8")


def update_eval_readme() -> None:
    text = EVAL_README.read_text(encoding="utf-8")
    current_status = f"{EVENT_TYPE}_ready"
    text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{current_status}`",
        text,
        count=1,
    )
    text = re.sub(
        r"v4_6_9 is `diagnostic_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod_ready`"
        r"(?:; v4_6_10 is `[^`]+`)?\.",
        f"v4_6_9 is `{v469.EVENT_TYPE}_ready`; v4_6_10 is `{current_status}`.",
        text,
        count=1,
    )
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod.py` | "
        "Replays the external holdout candidate manifest gate after v4_6_9. The default run remains "
        "input-waiting with no manifest; optional `--candidate-manifest` is input-only, "
        "path-redacted/hash-recorded, emits no raw candidate rows or sidecars, and keeps candidate export, "
        "dry-run inputs, datasets, jobs, checkpoints, v4_7, official metrics, promotion, product-success "
        "evidence, and live readiness closed. |"
    )
    pattern = r"\n?\| `rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod\.py` \| .*?\|"
    text = re.sub(pattern, "", text)
    text = text.replace(
        "\n\nv4 scripts remain diagnostic/non-production",
        f"\n{row}\n\nv4 scripts remain diagnostic/non-production",
        1,
    )
    scripts_readme.write_text(text, encoding="utf-8")


def update_progress_doc() -> None:
    current_status = f"{EVENT_TYPE}_ready"
    entry = (
        f"- v4_6_10 external holdout candidate manifest gate replay (`{RUN_ID}`) is {current_status}. "
        "The default run remains input-waiting after v4_6_9, confirms no candidate manifest is registered, "
        "and keeps all v4_7 user-owned policy inputs pending. The script also accepts optional "
        "`--candidate-manifest` input for no-write replay through the v4_5_1 intake and v4_5_2 "
        "source-identity gates, recording only redacted/hash metadata and aggregate counts while leaving "
        "`real_holdout_sufficient=false`. It does not acquire external holdout rows, export candidate "
        "manifests, create validation/source-audit sidecars, open dry-run inputs, run FT-A, create "
        "datasets/jobs/checkpoints, create official metric rows, or claim promotion, product success, "
        "production routing, or live DB/index/cache readiness."
    )
    v467 = v469.v467
    v467.replace_marked_entry(PROGRESS_DOC, RUN_ID, entry)
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{current_status}`;",
        text,
        count=1,
    )
    text = re.sub(
        r"(?:current diagnostic v4_6_10 external holdout candidate manifest gate replay loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_9 holdout candidate duplicate hygiene gate loop:\n`[^`]+`;",
        "current diagnostic v4_6_10 external holdout candidate manifest gate replay loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_6_9 holdout candidate duplicate hygiene gate loop:\n`{v469.RUN_ID}`;",
        text,
        count=1,
    )
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    path_text = report["artifact_paths"]["report_json"]
    entry = f"""### v4_6_10 External Holdout Candidate Manifest Gate Replay

- Run: `{RUN_ID}`
- v4 name: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Primary artifact: `{path_text}`
- Source evidence: v4_5_1/v4_5_2/v4_5_3/v4_6_6/v4_6_8/v4_6_9 report hashes and the empty external holdout candidate manifest boundary. Optional `--candidate-manifest` replay is input-only and records redacted/hash metadata plus aggregate v4_5_1/v4_5_2 gate outcomes without writing sidecars.
- Interpretation: the default artifact is an input-waiting manifest replay and v4_7-closed preflight only. Optional manifest replay is a no-write gate check, not external holdout acquisition, not candidate manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| external_holdout_candidate_manifest_gate_replay_only | true |
| gate_passed | false |
| candidate_manifest_present | false |
| candidate_manifest_input_provided | false |
| candidate_rows_replayed | 0 |
| missing_user_owned_input_count | {metrics['missing_user_owned_input_count']} |
| codex_owned_dependency_checks_passed | {str(metrics['codex_owned_dependency_checks_passed']).lower()} |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |

Artifact policy: single ignored `report.json`; no manifest replay sidecar, official metric preflight sidecar, candidate manifest, validation JSONL, source-identity audit JSONL, dry-run plan/input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, official metric results, or per-run Markdown is created. Optional manifest input is not copied into the run directory and raw candidate rows/source identities are not embedded in v4_6_10. This is not a v4_7 opening.
"""
    v469.v467.replace_marked_entry(MEASUREMENTS_DOC, RUN_ID, entry)


def update_triage_doc() -> None:
    entry = f"""### v4_6_10 External Holdout Candidate Manifest Gate Replay Triage

- Run: `{RUN_ID}`
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/{RUN_ID}/report.json`; single-report contract remains active.
- v4_6_10 is diagnostic-only and external-holdout-candidate-manifest-gate-replay-only. The default artifact confirms the external candidate manifest is still missing and keeps the v4_7 opening preflight closed.
- Optional `--candidate-manifest` input is a no-write replay through v4_5_1/v4_5_2 only; it records redacted/hash input metadata and aggregate gate outcomes, not raw candidate rows or raw source identities.
- It is not external holdout acquisition, not real holdout availability, not candidate manifest export, not validation/source-audit sidecar creation, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `real_holdout_sufficient=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.
"""
    v469.v467.replace_marked_entry(TRIAGE_DOC, RUN_ID, entry)


def update_v4_plan() -> None:
    plan_path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    text = plan_path.read_text(encoding="utf-8")
    if "### v4_6_10 — External Holdout Candidate Manifest Gate Replay" not in text:
        insert = """### v4_6_10 — External Holdout Candidate Manifest Gate Replay

This is a diagnostic input-waiting replay gate after v4_6_9, not holdout acquisition and not a dry run.

Purpose:

- Reproject the external holdout candidate manifest gate after duplicate hygiene is strict.
- Confirm no real external candidate manifest is registered yet in the default artifact.
- Permit optional no-write `--candidate-manifest` replay through v4_5_1/v4_5_2 while recording only redacted/hash input metadata and aggregate gate outcomes.
- Keep v4_7 official metric opening closed until user-owned gold/qrels/denominator and promotion policy inputs exist.
- Keep candidate export, dry-run input/export, FT-A dry-run execution, dataset export, official metric, promotion, product-success, and live-readiness gates closed.

Locked boundary:

```text
external_holdout_candidate_manifest_gate_replay_only = true
gate_passed = false
candidate_manifest_present = false
candidate_manifest_input_only = true
candidate_rows_replayed = 0
real_holdout_sufficient = false
candidate_manifest_exported = false
dry_run_input_manifest_exported = false
ft_route_policy_dry_run_opened = false
ft_route_policy_dry_run_executed = false
v4_7_official_metric_gate_opened = false
official_metric_input_rows = 0
promotion_evidence = false
product_success_evidence_allowed = false
```

If a candidate manifest is supplied explicitly, v4_6_10 may set `candidate_manifest_present=true`
and `candidate_rows_replayed>0` for that in-memory replay only. It must still keep
`real_holdout_sufficient=false`, must not serialize raw candidate rows or raw source identities,
must not copy the manifest into the run directory, and must not open dry-run, official metric,
promotion, product-success, or live-readiness gates.

"""
        text = text.replace("### v4_7 — Official Metric Opening Gate", insert + "### v4_7 — Official Metric Opening Gate", 1)
    text = text.replace(
        "v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        "v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod\n↓\nv4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
    )
    plan_path.write_text(text, encoding="utf-8")


def update_human_docs(report: Mapping[str, Any]) -> None:
    update_readme()
    update_eval_readme()
    update_scripts_readme()
    update_progress_doc()
    update_measurements_doc(report)
    update_triage_doc()
    update_v4_plan()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--candidate-manifest",
        type=Path,
        default=None,
        help="Optional external holdout candidate manifest JSONL for input-only replay; no sidecars are written.",
    )
    args = parser.parse_args(argv)
    artifacts = build_artifacts(candidate_manifest_path=args.candidate_manifest)
    check_report(artifacts["report"])
    if args.check:
        metrics = artifacts["report"]["metrics"]
        replay = artifacts["report"]["external_holdout_candidate_manifest_gate_replay"]
        manifest_input = replay["candidate_manifest_input"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": STATUS,
                    "external_holdout_candidate_manifest_gate_replay_only": True,
                    "gate_passed": metrics["gate_passed"],
                    "gate_opened": metrics["gate_opened"],
                    "candidate_manifest_input_provided": bool(manifest_input.get("provided")),
                    "candidate_manifest_load_error": clean(manifest_input.get("load_error")),
                    "candidate_manifest_present": metrics["candidate_manifest_present"],
                    "candidate_rows_replayed": metrics["candidate_rows_replayed"],
                    "missing_user_owned_input_count": metrics["missing_user_owned_input_count"],
                    "real_holdout_sufficient": False,
                    "candidate_manifest_exported": False,
                    "ft_route_policy_dry_run_opened": False,
                    "v4_7_official_metric_gate_opened": False,
                    "official_metric_input_rows": 0,
                    "promotion_evidence": False,
                },
                sort_keys=True,
            )
        )
        return 0
    report = write_artifacts(artifacts)
    update_status(report)
    update_human_docs(report)
    print(json.dumps({"run_id": RUN_ID, "status": STATUS, "report": repo_relative(REPORT_JSON)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
