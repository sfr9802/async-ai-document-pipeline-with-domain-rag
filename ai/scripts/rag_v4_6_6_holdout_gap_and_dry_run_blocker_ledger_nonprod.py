from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod as v44
import rag_v4_5_1_holdout_candidate_intake_gate_nonprod as v451
import rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod as v452
import rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod as v453
import rag_v4_5_finetune_readiness_packet_nonprod as v45
import rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod as v461
import rag_v4_6_2_ft_route_policy_fixture_contract_nonprod as v462
import rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod as v463
import rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod as v464
import rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod as v465
import rag_v4_6_ft_route_policy_dry_run_preflight_nonprod as v46


ROOT = v465.ROOT
REPORT_DIR = v465.REPORT_DIR
STATUS_JSONL = v465.STATUS_JSONL
PROGRESS_DOC = v465.PROGRESS_DOC
MEASUREMENTS_DOC = v465.MEASUREMENTS_DOC
TRIAGE_DOC = v465.TRIAGE_DOC
README = v465.README
EVAL_README = v465.EVAL_README

V4_NAME = v465.V4_NAME
V4_RUN_FAMILY = v465.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod"
EVENT_TYPE = "diagnostic_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod"
STATUS = "DIAGNOSTIC_V4_6_6_HOLDOUT_GAP_AND_DRY_RUN_BLOCKER_LEDGER_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_report_v1"

SOURCE_REPORTS = {
    "v4_4": (v44.RUN_ID, v44.REPORT_JSON),
    "v4_5": (v45.RUN_ID, v45.REPORT_JSON),
    "v4_5_1": (v451.RUN_ID, v451.REPORT_JSON),
    "v4_5_2": (v452.RUN_ID, v452.REPORT_JSON),
    "v4_5_3": (v453.RUN_ID, v453.REPORT_JSON),
    "v4_6": (v46.RUN_ID, v46.REPORT_JSON),
    "v4_6_1": (v461.RUN_ID, v461.REPORT_JSON),
    "v4_6_2": (v462.RUN_ID, v462.REPORT_JSON),
    "v4_6_3": (v463.RUN_ID, v463.REPORT_JSON),
    "v4_6_4": (v464.RUN_ID, v464.REPORT_JSON),
    "v4_6_5": (v465.RUN_ID, v465.REPORT_JSON),
}

DEFAULT_MINIMUM_TARGETS = {
    "pdf_unseen_source_documents": 20,
    "query_fidelity_included_rows_per_family": 100,
    "xlsx_unseen_workbooks": 8,
}

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "candidate_manifest.jsonl",
            "dpo_dataset.jsonl",
            "dry_run_blocker_ledger.json",
            "dry_run_execution_plan.json",
            "dry_run_input_manifest.jsonl",
            "holdout_gap_ledger.json",
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


def clean(value: Any) -> str:
    return v465.clean(value)


def repo_relative(path: Path) -> str:
    return v465.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v465.artifact_path_text(path)


def utc_now() -> str:
    return v465.utc_now()


def sha256_file(path: Path) -> str:
    return v465.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v465.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v465.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v465.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v465.write_jsonl(path, rows)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def load_source_reports() -> dict[str, dict[str, Any]]:
    return {
        key: read_json(report_path) if report_path.exists() else {}
        for key, (_run_id, report_path) in SOURCE_REPORTS.items()
    }


def source_report_boundary_flags_clean(report: Mapping[str, Any]) -> bool:
    return (
        not bool(report.get("official_metric"))
        and _int(report.get("official_metric_input_rows")) == 0
        and not bool(report.get("official_metric_lift"))
        and not bool(report.get("promotion_evidence"))
        and not bool(report.get("product_success_evidence_allowed"))
        and not bool(report.get("live_db_index_cache_readiness"))
    )


def source_report_input(*, input_key: str, source_run_id: str, report_json: Path, report: Mapping[str, Any]) -> dict[str, Any]:
    exists = report_json.exists()
    metrics = _mapping(report.get("metrics"))
    return {
        "schema_version": f"{RUN_ID}_source_report_input_v1",
        "run_id": RUN_ID,
        "input_key": input_key,
        "source_run_id": source_run_id,
        "source_report_json": repo_relative(report_json),
        "source_report_exists": exists,
        "source_report_sha256": sha256_file(report_json) if exists else "",
        "source_report_schema_version": clean(report.get("schema_version")),
        "source_report_status": clean(report.get("status")),
        "source_report_diagnostic_only": bool(report.get("diagnostic_only")),
        "source_report_boundary_flags_clean": source_report_boundary_flags_clean(report),
        "source_report_official_metric_input_rows": _int(report.get("official_metric_input_rows")),
        "source_report_promotion_evidence": bool(report.get("promotion_evidence")),
        "source_report_product_success_evidence_allowed": bool(
            report.get("product_success_evidence_allowed")
        ),
        "source_report_live_db_index_cache_readiness": bool(
            report.get("live_db_index_cache_readiness")
        ),
        "source_report_real_holdout_sufficient": bool(metrics.get("real_holdout_sufficient")),
        "source_report_readiness_gate_passed": bool(metrics.get("readiness_gate_passed")),
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_source_report_inputs(
    *,
    source_reports: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        key: source_report_input(
            input_key=key,
            source_run_id=source_run_id,
            report_json=report_json,
            report=source_reports.get(key, {}),
        )
        for key, (source_run_id, report_json) in SOURCE_REPORTS.items()
    }


def _minimum_targets(source_reports: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    merged = dict(DEFAULT_MINIMUM_TARGETS)
    for key in ("v4_4", "v4_5", "v4_5_1", "v4_5_2"):
        targets = _mapping(_mapping(source_reports.get(key, {})).get("metrics")).get("minimum_targets")
        if isinstance(targets, Mapping):
            for target_key in merged:
                value = _int(targets.get(target_key))
                if value > 0:
                    merged[target_key] = value
            return merged
    return merged


def _metric_dict(
    source_reports: Mapping[str, Mapping[str, Any]],
    keys: Sequence[str],
    field: str,
) -> Mapping[str, Any]:
    for key in keys:
        metrics = _mapping(_mapping(source_reports.get(key, {})).get("metrics"))
        value = metrics.get(field)
        if isinstance(value, Mapping) and value:
            return value
    return {}


def build_holdout_gap_ledger(*, source_reports: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    targets = _minimum_targets(source_reports)
    unseen_counts = _metric_dict(
        source_reports,
        ("v4_4", "v4_5", "v4_5_1", "v4_5_2"),
        "real_unseen_registry_counts",
    )
    query_counts = _metric_dict(
        source_reports,
        ("v4_4", "v4_5", "v4_5_1", "v4_5_2"),
        "real_query_fidelity_included_counts",
    )
    v451_metrics = _mapping(_mapping(source_reports.get("v4_5_1", {})).get("metrics"))
    v452_metrics = _mapping(_mapping(source_reports.get("v4_5_2", {})).get("metrics"))

    pdf_disjoint = _int(unseen_counts.get("PDF_source_document_disjoint"))
    xlsx_disjoint = _int(unseen_counts.get("XLSX_workbook_disjoint"))
    pdf_query_rows = _int(query_counts.get("PDF"))
    xlsx_query_rows = _int(query_counts.get("XLSX"))

    deficits = {
        "pdf_source_document_disjoint_needed": max(
            targets["pdf_unseen_source_documents"] - pdf_disjoint, 0
        ),
        "pdf_query_fidelity_rows_needed": max(
            targets["query_fidelity_included_rows_per_family"] - pdf_query_rows, 0
        ),
        "xlsx_workbook_disjoint_needed": max(targets["xlsx_unseen_workbooks"] - xlsx_disjoint, 0),
        "xlsx_query_fidelity_rows_needed": max(
            targets["query_fidelity_included_rows_per_family"] - xlsx_query_rows, 0
        ),
    }
    requirements = [
        f"add_{deficits['pdf_source_document_disjoint_needed']}_pdf_source_document_disjoint_candidates",
        f"add_{deficits['xlsx_workbook_disjoint_needed']}_xlsx_workbook_disjoint_candidates",
        f"add_{deficits['pdf_query_fidelity_rows_needed']}_pdf_query_fidelity_included_rows",
        f"add_{deficits['xlsx_query_fidelity_rows_needed']}_xlsx_query_fidelity_included_rows",
        "rerun_v4_5_1_candidate_intake_gate",
        "rerun_v4_5_2_source_identity_audit_gate",
        "rerun_v4_6_preflight_before_any_ft_a_dry_run",
    ]
    return {
        "schema_version": f"{RUN_ID}_holdout_gap_ledger_v1",
        "run_id": RUN_ID,
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
        "candidate_manifest_present": bool(v451_metrics.get("candidate_manifest_present"))
        or bool(v452_metrics.get("candidate_manifest_present")),
        "candidate_manifest_exported": False,
        "accepted_pdf_holdout_candidates": _int(v452_metrics.get("accepted_pdf_holdout_candidates"))
        or _int(v451_metrics.get("accepted_pdf_holdout_candidates")),
        "accepted_xlsx_holdout_candidates": _int(v452_metrics.get("accepted_xlsx_holdout_candidates"))
        or _int(v451_metrics.get("accepted_xlsx_holdout_candidates")),
        "minimum_targets": dict(targets),
        "source_counts": {
            "PDF_source_document_disjoint": pdf_disjoint,
            "XLSX_workbook_disjoint": xlsx_disjoint,
        },
        "query_fidelity_included_counts": {
            "PDF": pdf_query_rows,
            "XLSX": xlsx_query_rows,
        },
        "deficits": deficits,
        "acquisition_requirements": requirements,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_dry_run_blocker_ledger(
    *,
    source_reports: Mapping[str, Mapping[str, Any]],
    user_owned_policy_gate_ready: bool = False,
) -> dict[str, Any]:
    v45_metrics = _mapping(_mapping(source_reports.get("v4_5", {})).get("metrics"))
    v451_metrics = _mapping(_mapping(source_reports.get("v4_5_1", {})).get("metrics"))
    v452_metrics = _mapping(_mapping(source_reports.get("v4_5_2", {})).get("metrics"))
    v453_metrics = _mapping(_mapping(source_reports.get("v4_5_3", {})).get("metrics"))
    v46_metrics = _mapping(_mapping(source_reports.get("v4_6", {})).get("metrics"))
    v465_gate = _mapping(_mapping(source_reports.get("v4_6_5", {})).get("dry_run_execution_plan_gate"))

    gate_state = {
        "v4_5_readiness_gate_passed": bool(v45_metrics.get("readiness_gate_passed")),
        "v4_5_1_candidate_intake_gate_passed": bool(
            v451_metrics.get("candidate_intake_gate_passed")
        ),
        "v4_5_2_source_identity_audit_gate_passed": bool(
            v452_metrics.get("source_identity_audit_gate_passed")
        ),
        "v4_5_3_prior_identity_baseline_gate_passed": bool(
            v453_metrics.get("prior_identity_collision_baseline_available")
        ),
        "v4_6_preflight_all_gates_passed": bool(v46_metrics.get("all_preflight_gates_passed")),
        "v4_6_5_execution_plan_gate_passed": bool(
            v465_gate.get("dry_run_execution_plan_gate_passed")
        ),
        "dry_run_input_manifest_exported": bool(
            _mapping(source_reports.get("v4_6_5", {})).get("dry_run_input_manifest_exported")
        ),
    }
    blocked_reasons: list[str] = []
    if not gate_state["v4_5_readiness_gate_passed"]:
        blocked_reasons.append("v4_5_readiness_gate_failed")
    if not gate_state["v4_5_1_candidate_intake_gate_passed"]:
        blocked_reasons.append("v4_5_1_candidate_intake_gate_failed")
    if not gate_state["v4_5_2_source_identity_audit_gate_passed"]:
        blocked_reasons.append("v4_5_2_source_identity_audit_gate_failed")
    if not gate_state["v4_5_3_prior_identity_baseline_gate_passed"]:
        blocked_reasons.append("v4_5_3_prior_identity_baseline_gate_failed")
    if not gate_state["v4_6_preflight_all_gates_passed"]:
        blocked_reasons.append("v4_6_preflight_all_gates_failed")
    if not gate_state["v4_6_5_execution_plan_gate_passed"]:
        blocked_reasons.append("v4_6_5_execution_plan_gate_failed")
    if not gate_state["dry_run_input_manifest_exported"]:
        blocked_reasons.append("dry_run_input_manifest_not_exported")
    if not user_owned_policy_gate_ready:
        blocked_reasons.append("user_owned_gold_qrels_denominator_policy_pending")

    all_non_gold_source_gates_passed = all(gate_state.values())
    return {
        "schema_version": f"{RUN_ID}_dry_run_blocker_ledger_v1",
        "run_id": RUN_ID,
        "source_gate_state": gate_state,
        "all_non_gold_source_gates_passed": all_non_gold_source_gates_passed,
        "user_owned_policy_gate_ready": bool(user_owned_policy_gate_ready),
        "dry_run_blocker_count": len(blocked_reasons),
        "blocked_reasons": blocked_reasons,
        "non_gold_next_actions": build_holdout_gap_ledger(source_reports=source_reports)[
            "acquisition_requirements"
        ],
        "user_owned_next_actions": [
            "approve_gold_qrels_denominator_policy_before_any_official_metric_or_promotion_gate",
        ],
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_exported": False,
        "v4_7_official_metric_gate_opened": False,
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
        "direct_normalized_answer_value_query_matching_used": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "candidate_manifest_exported": False,
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_exported": False,
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_prompt_text_embedded": False,
        "raw_llm_response_payload_created": False,
        "fine_tuning_dataset_export_created": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
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
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "live_db_index_cache_readiness": False,
        "single_report_artifact_contract": True,
        "review_csv_created": False,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_metrics(
    *,
    holdout_gap: Mapping[str, Any],
    dry_run_blockers: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "holdout_gap_and_dry_run_blocker_ledger_only": True,
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
        "candidate_manifest_present": bool(holdout_gap.get("candidate_manifest_present")),
        "candidate_manifest_exported": False,
        "accepted_pdf_holdout_candidates": _int(holdout_gap.get("accepted_pdf_holdout_candidates")),
        "accepted_xlsx_holdout_candidates": _int(holdout_gap.get("accepted_xlsx_holdout_candidates")),
        "pdf_source_document_disjoint_needed": _int(
            _mapping(holdout_gap.get("deficits")).get("pdf_source_document_disjoint_needed")
        ),
        "xlsx_workbook_disjoint_needed": _int(
            _mapping(holdout_gap.get("deficits")).get("xlsx_workbook_disjoint_needed")
        ),
        "all_non_gold_source_gates_passed": bool(
            dry_run_blockers.get("all_non_gold_source_gates_passed")
        ),
        "dry_run_blocker_count": _int(dry_run_blockers.get("dry_run_blocker_count")),
        "user_owned_policy_gate_ready": bool(dry_run_blockers.get("user_owned_policy_gate_ready")),
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_exported": False,
        "raw_prompt_text_embedded": False,
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_llm_response_payload_created": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "fine_tuning_dataset_exports_created": 0,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
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
    holdout_gap: Mapping[str, Any],
    dry_run_blockers: Mapping[str, Any],
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
        "holdout_gap_and_dry_run_blocker_ledger_only": True,
        "holdout_gap_ledger": dict(holdout_gap),
        "dry_run_blocker_ledger": dict(dry_run_blockers),
        "source_report_inputs": {key: dict(value) for key, value in source_inputs.items()},
        "readiness_decision": "blocked_pending_real_holdout_manifest_source_identity_audit_manifest_export_and_user_policy",
        "blocked_reasons": list(dry_run_blockers["blocked_reasons"]),
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
        "candidate_manifest_exported": False,
        "dry_run_execution_plan_exported": False,
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
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py --check",
                "targeted v4_6_6 holdout gap and dry-run blocker ledger tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_6_6 because this slice compacts deterministic "
                "holdout and dry-run blocker evidence only; future FT-A training, embedding, or local "
                "LLM workloads should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "Real PDF source-document-disjoint holdout candidates are still absent.",
            "Real XLSX workbook-disjoint holdout candidates are still absent.",
            "External holdout candidate manifest export remains closed.",
            "FT-A dry-run input manifest export remains closed.",
            "No actual FT-A dry run is opened or executed.",
            "v4_7 official metric opening remains user-owned and unopened.",
        ],
        "next_recommendation": (
            "Acquire source-document-disjoint PDF and workbook-disjoint XLSX holdout candidates, rerun "
            "v4_5_1 and v4_5_2, then rerun v4_6 preflight before any dry-run, dataset export, GPU "
            "training, official metric, promotion, or v4_7 gate is considered."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    source_reports = load_source_reports()
    source_inputs = build_source_report_inputs(source_reports=source_reports)
    holdout_gap = build_holdout_gap_ledger(source_reports=source_reports)
    dry_run_blockers = build_dry_run_blocker_ledger(source_reports=source_reports)
    metrics = build_metrics(holdout_gap=holdout_gap, dry_run_blockers=dry_run_blockers)
    guardrails = build_guardrails()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        source_inputs=source_inputs,
        holdout_gap=holdout_gap,
        dry_run_blockers=dry_run_blockers,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "holdout_gap_ledger": holdout_gap,
        "dry_run_blocker_ledger": dry_run_blockers,
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
        raise RuntimeError(f"unexpected v4_6_6 primary artifacts: {unexpected}")


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
    report["candidate_manifest_exported"] = False
    report["dry_run_execution_plan_exported"] = False
    report["fine_tuning_dataset_export_created"] = False
    report["training_manifest_jsonl_created"] = False
    report["training_job_created"] = False
    remove_stale_sidecar_artifacts(target_dir)
    assert_single_report_directory(target_dir)
    write_json(report_path, report)
    assert_single_report_directory(target_dir)
    return report


def artifact_sha256_from_report_paths(artifact_paths: Mapping[str, str]) -> dict[str, str]:
    return v465.artifact_sha256_from_report_paths(artifact_paths)


def append_status_event(report: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
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
        "diagnostic_only": True,
        "holdout_gap_and_dry_run_blocker_ledger_only": True,
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
        "candidate_manifest_present": report["metrics"]["candidate_manifest_present"],
        "candidate_manifest_exported": False,
        "accepted_pdf_holdout_candidates": report["metrics"]["accepted_pdf_holdout_candidates"],
        "accepted_xlsx_holdout_candidates": report["metrics"]["accepted_xlsx_holdout_candidates"],
        "all_non_gold_source_gates_passed": report["metrics"]["all_non_gold_source_gates_passed"],
        "dry_run_blocker_count": report["metrics"]["dry_run_blocker_count"],
        "blocked_reasons": list(report["blocked_reasons"]),
        "source_report_inputs": dict(report["source_report_inputs"]),
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_exported": False,
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_llm_response_payload_created": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "review_csv_created": False,
        "per_run_markdown_created": False,
    }
    rows = [
        row
        for row in read_jsonl(STATUS_JSONL)
        if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)
    ]
    rows.append(event)
    write_jsonl(STATUS_JSONL, rows)


def replace_current_status(text: str) -> str:
    current_status = f"{EVENT_TYPE}_ready"
    text = re.sub(
        r"^Current RAG status: `[^`]+`",
        f"Current RAG status: `{current_status}`",
        text,
        flags=re.M,
    )
    text = re.sub(
        r"^Overall status: `[^`]+`;",
        f"Overall status: `{current_status}`;",
        text,
        flags=re.M,
    )
    return text


def update_readme() -> None:
    text = replace_current_status(README.read_text(encoding="utf-8"))
    if "rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py" not in text:
        marker = "python -X utf8 ai\\scripts\\rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py --check\n"
        addition = (
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py\n"
            "python -X utf8 ai\\scripts\\rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py\n"
            "python -X utf8 ai\\scripts\\rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py --check\n"
        )
        text = text.replace(marker, marker + addition)
    README.write_text(text, encoding="utf-8")


def update_eval_readme() -> None:
    text = replace_current_status(EVAL_README.read_text(encoding="utf-8"))
    text = re.sub(
        r"^- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{EVENT_TYPE}_ready`",
        text,
        flags=re.M,
    )
    if "v4_6_6 is `diagnostic_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod_ready`" not in text:
        text = text.replace(
            "v4_6_5 is `diagnostic_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod_ready`.",
            "v4_6_5 is `diagnostic_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod_ready`; "
            "v4_6_6 is `diagnostic_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod_ready`.",
        )
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    path = ROOT / "ai" / "scripts" / "README.md"
    text = path.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py` | "
        "Compacts real-holdout deficits and FT-A dry-run blockers into one closed diagnostic ledger without exporting "
        "candidate manifests, dry-run plans, prompts, raw LLM responses, datasets, jobs, checkpoints, official metrics, promotion, or product-success evidence. |"
    )
    if "rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py" not in text:
        text = text.replace(
            "| `rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py` | Defines the closed FT-A dry-run execution plan gate without exporting the plan or manifest and without creating prompts, raw LLM responses, datasets, jobs, checkpoints, official metrics, promotion, or product-success evidence. |\n",
            "| `rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py` | Defines the closed FT-A dry-run execution plan gate without exporting the plan or manifest and without creating prompts, raw LLM responses, datasets, jobs, checkpoints, official metrics, promotion, or product-success evidence. |\n"
            + row
            + "\n",
        )
    path.write_text(text, encoding="utf-8")


def update_progress_doc() -> None:
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_status = f"{EVENT_TYPE}_ready"
    entry = (
        f"<!-- {RUN_ID}:progress-entry:start -->\n"
        f"- v4_6_6 holdout gap and dry-run blocker ledger (`{RUN_ID}`) is {current_status}. "
        "It compacts current real-holdout deficits and FT-A dry-run blockers after v4_6_5, but does not export a "
        "candidate manifest, dry-run execution plan, dry-run input manifest, prompt payload, prompt manifest, raw LLM response, "
        "dataset, training manifest, job, checkpoint, official metric, promotion evidence, product-success evidence, production route, "
        "or live DB/index/cache readiness claim.\n"
        f"<!-- {RUN_ID}:progress-entry:end -->\n"
    )
    pattern = rf"<!-- {re.escape(RUN_ID)}:progress-entry:start -->.*?<!-- {re.escape(RUN_ID)}:progress-entry:end -->\n"
    if re.search(pattern, text, flags=re.S):
        text = re.sub(pattern, entry, text, flags=re.S)
    else:
        text = entry + text
    current_text, separator, history_text = text.partition("## Short History")
    current_text = replace_current_status(current_text)
    text = current_text + separator + history_text
    loop = (
        "current diagnostic v4_6_6 holdout gap and dry-run blocker ledger loop:\n"
        f"`{RUN_ID}`;\n"
    )
    text = re.sub(
        r"(?:current diagnostic v4_6_6 holdout gap and dry-run blocker ledger loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_5 FT-A dry-run execution plan gate loop:",
        loop + "current diagnostic v4_6_5 FT-A dry-run execution plan gate loop:",
        text,
        count=1,
    )
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    text = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    metrics = report["metrics"]
    entry = f"""<!-- {RUN_ID}:measurements-entry:start -->
### v4_6_6 Holdout Gap And Dry-Run Blocker Ledger

- Run: `{RUN_ID}`
- v4 name: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, holdout-gap and dry-run-blocker ledger only, single `report.json`.
- Primary artifact: `{report['artifact_paths']['report_json']}`
- Source evidence: v4_4 through v4_6_5 diagnostic reports.

| Field | Value |
| --- | --- |
| holdout_gap_and_dry_run_blocker_ledger_only | true |
| real_holdout_sufficient | false |
| candidate_manifest_present | {str(metrics['candidate_manifest_present']).lower()} |
| candidate_manifest_exported | false |
| accepted_pdf_holdout_candidates | {metrics['accepted_pdf_holdout_candidates']} |
| accepted_xlsx_holdout_candidates | {metrics['accepted_xlsx_holdout_candidates']} |
| pdf_source_document_disjoint_needed | {metrics['pdf_source_document_disjoint_needed']} |
| xlsx_workbook_disjoint_needed | {metrics['xlsx_workbook_disjoint_needed']} |
| all_non_gold_source_gates_passed | {str(metrics['all_non_gold_source_gates_passed']).lower()} |
| dry_run_blocker_count | {metrics['dry_run_blocker_count']} |
| dry_run_execution_plan_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| v4_7_official_metric_gate_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds holdout_gap_ledger, dry_run_blocker_ledger, source_report_inputs, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no holdout-gap sidecar, dry-run-blocker sidecar, candidate manifest sidecar, dry-run execution plan sidecar, dry-run input manifest sidecar, prompt manifest, raw LLM response, dataset sidecar, training manifest, training job, checkpoint, review CSV, official metric result, or per-run Markdown.
<!-- {RUN_ID}:measurements-entry:end -->
"""
    pattern = rf"<!-- {re.escape(RUN_ID)}:measurements-entry:start -->.*?<!-- {re.escape(RUN_ID)}:measurements-entry:end -->\n?"
    if re.search(pattern, text, flags=re.S):
        text = re.sub(pattern, entry, text, flags=re.S)
    else:
        text = entry + "\n" + text
    MEASUREMENTS_DOC.write_text(text, encoding="utf-8")


def update_triage_doc() -> None:
    text = TRIAGE_DOC.read_text(encoding="utf-8")
    entry = f"""<!-- {RUN_ID}:triage-entry:start -->
### v4_6_6 Holdout Gap And Dry-Run Blocker Ledger Triage

- Run: `{RUN_ID}`
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/{RUN_ID}/report.json`; single-report contract remains active.
- v4_6_6 is diagnostic-only, non-production, ledger-only infrastructure over existing v4_4 through v4_6_5 reports.
- It is not external holdout acquisition, not candidate manifest export, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- Codex-owned next work remains acquiring or registering source-disjoint candidates and rerunning non-gold gates; user-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion-adjacent evaluation.
<!-- {RUN_ID}:triage-entry:end -->
"""
    pattern = rf"<!-- {re.escape(RUN_ID)}:triage-entry:start -->.*?<!-- {re.escape(RUN_ID)}:triage-entry:end -->\n?"
    if re.search(pattern, text, flags=re.S):
        text = re.sub(pattern, entry, text, flags=re.S)
    else:
        text = entry + "\n" + text
    TRIAGE_DOC.write_text(text, encoding="utf-8")


def update_v4_plan() -> None:
    path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    text = path.read_text(encoding="utf-8")
    section = """### v4_6_6 — Holdout Gap And Dry-Run Blocker Ledger

This is a diagnostic ledger over existing v4_4 through v4_6_5 evidence, not holdout acquisition and not a dry run.

Purpose:

- Compact real PDF/XLSX holdout deficits and FT-A dry-run blockers into one report after v4_6_5.
- Keep non-gold next actions separate from user-owned gold/qrels/denominator/promotion policy.
- Keep all outputs in one ignored `report.json`.

Locked boundary:

```text
real_holdout_sufficient = false
candidate_manifest_exported = false
dry_run_execution_plan_exported = false
dry_run_input_manifest_exported = false
ft_route_policy_dry_run_opened = false
ft_route_policy_dry_run_executed = false
v4_7_official_metric_gate_opened = false
official_metric_input_rows = 0
promotion_evidence = false
product_success_evidence_allowed = false
```

"""
    if "### v4_6_6 — Holdout Gap And Dry-Run Blocker Ledger" not in text:
        text = text.replace("### v4_7 — Official Metric Opening Gate", section + "### v4_7 — Official Metric Opening Gate")
    if "v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod" not in text:
        text = text.replace(
            "v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
            "v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod\n↓\nv4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        )
    path.write_text(text, encoding="utf-8")


def update_human_docs(report: Mapping[str, Any]) -> None:
    update_readme()
    update_eval_readme()
    update_scripts_readme()
    update_progress_doc()
    update_measurements_doc(report)
    update_triage_doc()
    update_v4_plan()


def check_report(report: Mapping[str, Any]) -> None:
    if report["schema_version"] != REPORT_SCHEMA_VERSION:
        raise AssertionError("unexpected report schema")
    if report["official_metric_input_rows"] != 0:
        raise AssertionError("official metric rows must remain zero")
    if report.get("promotion_evidence"):
        raise AssertionError("promotion evidence must remain false")
    if report.get("product_success_evidence_allowed"):
        raise AssertionError("product success evidence must remain false")
    if report.get("candidate_manifest_exported"):
        raise AssertionError("candidate manifest export must remain closed")
    if report.get("dry_run_execution_plan_exported"):
        raise AssertionError("dry-run execution plan export must remain closed")
    if report.get("dry_run_input_manifest_exported"):
        raise AssertionError("dry-run input manifest export must remain closed")
    if report.get("v4_7_official_metric_gate_opened"):
        raise AssertionError("v4_7 official metric gate must remain closed")
    if report["holdout_gap_ledger"]["real_holdout_sufficient"]:
        raise AssertionError("real holdout must remain insufficient in v4_6_6")
    if report["ft_route_policy_dry_run_opened"]:
        raise AssertionError("FT-A dry run must remain closed")
    nested_containers = (
        "holdout_gap_ledger",
        "dry_run_blocker_ledger",
        "metrics",
        "guardrails",
        "guardrail_audit",
    )
    nested_closed_fields = (
        "candidate_manifest_exported",
        "candidate_manifest_jsonl_created",
        "candidate_validation_jsonl_created",
        "source_identity_audit_jsonl_created",
        "dry_run_execution_plan_exported",
        "dry_run_input_manifest_exported",
        "ft_route_policy_dry_run_opened",
        "ft_route_policy_dry_run_executed",
        "v4_7_official_metric_gate_opened",
        "fine_tuning_dataset_export_created",
        "fine_tuning_dataset_exports_created",
        "training_manifest_jsonl_created",
        "training_job_created",
        "model_or_adapter_checkpoint_written",
        "prompt_payload_created",
        "prompt_manifest_created",
        "raw_llm_response_payload_created",
        "official_metric",
        "official_metric_input_rows",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
    )
    for container_name in nested_containers:
        container = _mapping(report.get(container_name))
        for field in nested_closed_fields:
            value = container.get(field)
            if isinstance(value, int | float):
                opened = value != 0
            else:
                opened = bool(value)
            if opened:
                raise AssertionError(f"{container_name}.{field} must remain closed")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    artifacts = build_artifacts()
    report = artifacts["report"]
    check_report(report)
    if args.check:
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": STATUS,
                    "holdout_gap_and_dry_run_blocker_ledger_only": True,
                    "real_holdout_sufficient": False,
                    "all_non_gold_source_gates_passed": report["metrics"][
                        "all_non_gold_source_gates_passed"
                    ],
                    "candidate_manifest_exported": False,
                    "dry_run_execution_plan_exported": False,
                    "dry_run_input_manifest_exported": False,
                    "ft_route_policy_dry_run_opened": False,
                    "ft_route_policy_dry_run_executed": False,
                    "v4_7_official_metric_gate_opened": False,
                    "fine_tuning_dataset_exports_created": 0,
                    "official_metric_input_rows": 0,
                    "promotion_evidence": False,
                    "gpu_required_for_this_slice": False,
                },
                sort_keys=True,
            )
        )
        return 0

    written = write_artifacts(artifacts)
    append_status_event(written)
    update_human_docs(written)
    print(json.dumps({"run_id": RUN_ID, "status": STATUS, "report": repo_relative(REPORT_JSON)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
