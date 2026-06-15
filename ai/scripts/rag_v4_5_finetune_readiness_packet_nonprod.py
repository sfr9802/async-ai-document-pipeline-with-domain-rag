from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod as v44


ROOT = v44.ROOT
REPORT_DIR = v44.REPORT_DIR
STATUS_JSONL = v44.STATUS_JSONL
PROGRESS_DOC = v44.PROGRESS_DOC
MEASUREMENTS_DOC = v44.MEASUREMENTS_DOC
TRIAGE_DOC = v44.TRIAGE_DOC
README = v44.README
EVAL_README = v44.EVAL_README

V4_NAME = v44.V4_NAME
V4_RUN_FAMILY = v44.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod"
EVENT_TYPE = "diagnostic_v4_5_finetune_readiness_packet_nonprod"
STATUS = "DIAGNOSTIC_V4_5_FINETUNE_READINESS_PACKET_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_5_finetune_readiness_packet_report_v1"
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v44.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
            "dpo_dataset.jsonl",
            "fine_tuning_lanes.json",
            "finetune_readiness_packet.json",
            "metrics.json",
            "reward_model_dataset.jsonl",
            "review_packet.csv",
            "sft_dataset.jsonl",
            "summary.json",
            "training_manifest.jsonl",
        }
    )
)


def clean(value: Any) -> str:
    return v44.clean(value)


def repo_relative(path: Path) -> str:
    return v44.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v44.artifact_path_text(path)


def utc_now() -> str:
    return v44.utc_now()


def sha256_file(path: Path) -> str:
    return v44.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v44.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v44.read_jsonl(path)


def artifact_exists(path: Path) -> bool:
    return v44.artifact_exists(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v44.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v44.write_jsonl(path, rows)


def load_v4_4_report() -> dict[str, Any]:
    if artifact_exists(v44.REPORT_JSON):
        return read_json(v44.REPORT_JSON)
    return v44.build_artifacts()["report"]


def source_run_references() -> dict[str, Any]:
    return {
        "previous_gate_run_id": v44.RUN_ID,
        "previous_gate_report_json": repo_relative(v44.REPORT_JSON),
        "v4_4_report_json": repo_relative(v44.REPORT_JSON),
        "v4_3_report_json": repo_relative(v44.v43.REPORT_JSON),
        "v4_2_report_json": repo_relative(v44.v43.v42.REPORT_JSON),
        "v4_1_report_json": repo_relative(v44.v43.v42.v41.REPORT_JSON),
        "phase1_v3_22_report_json": repo_relative(v44.v43.v42.v41.v322.REPORT_JSON),
    }


def previous_gate_report_sha256(source_report: Mapping[str, Any]) -> str:
    artifact_paths = source_report.get("artifact_paths") or {}
    report_text = clean(artifact_paths.get("report_json")) if isinstance(artifact_paths, Mapping) else ""
    report_path = ROOT / report_text if report_text else v44.REPORT_JSON
    if artifact_exists(report_path):
        return sha256_file(report_path)
    return ""


def build_evidence_path_quality_gate(source_report: Mapping[str, Any]) -> dict[str, Any]:
    guardrails = source_report.get("guardrails") or {}
    return {
        "schema_version": f"{RUN_ID}_evidence_path_quality_gate_v1",
        "run_id": RUN_ID,
        "passed": (
            guardrails.get("source_atom_evidence_bundle_evidence_truth") is True
            and guardrails.get("searchview_vector_payload_candidate_only") is True
            and guardrails.get("vector_payload_used_as_evidence_truth") is False
        ),
        "source_atom_evidence_bundle_evidence_truth": bool(
            guardrails.get("source_atom_evidence_bundle_evidence_truth")
        ),
        "searchview_vector_payload_candidate_only": bool(guardrails.get("searchview_vector_payload_candidate_only")),
        "vector_payload_used_as_evidence_truth": bool(guardrails.get("vector_payload_used_as_evidence_truth")),
        "raw_pdf_query_time_parsing": bool(guardrails.get("raw_pdf_query_time_parsing")),
        "raw_xlsx_query_time_parsing": bool(guardrails.get("raw_xlsx_query_time_parsing")),
        "direct_normalized_answer_value_query_matching_used": bool(
            guardrails.get("direct_normalized_answer_value_query_matching_used")
        ),
        "input_role": "readiness_gate_from_v4_4_guardrails",
    }


def build_split_quality_gate(source_report: Mapping[str, Any]) -> dict[str, Any]:
    holdout = source_report.get("holdout_manifest") or {}
    metrics = source_report.get("metrics") or {}
    counts = dict(holdout.get("real_unseen_registry_counts") or metrics.get("real_unseen_registry_counts") or {})
    minimum_targets = dict(holdout.get("minimum_targets") or metrics.get("minimum_targets") or {})
    query_counts = dict(metrics.get("real_query_fidelity_included_counts") or {})
    pdf_count = int(counts.get("PDF_source_document_disjoint") or 0)
    xlsx_count = int(counts.get("XLSX_workbook_disjoint") or 0)
    pdf_target = int(minimum_targets.get("pdf_unseen_source_documents") or 20)
    xlsx_target = int(minimum_targets.get("xlsx_unseen_workbooks") or 8)
    query_target = int(minimum_targets.get("query_fidelity_included_rows_per_family") or 100)
    pdf_query_count = int(query_counts.get("PDF") or 0)
    xlsx_query_count = int(query_counts.get("XLSX") or 0)
    identity_sufficient = pdf_count >= pdf_target and xlsx_count >= xlsx_target
    query_fidelity_sufficient = pdf_query_count >= query_target and xlsx_query_count >= query_target
    blocked_reasons: list[str] = []
    if not identity_sufficient:
        blocked_reasons.append("real_disjoint_holdout_unavailable")
    if not query_fidelity_sufficient:
        blocked_reasons.append("real_query_fidelity_rows_below_target")
    return {
        "schema_version": f"{RUN_ID}_split_quality_gate_v1",
        "run_id": RUN_ID,
        "passed": identity_sufficient and query_fidelity_sufficient,
        "real_holdout_available": bool(holdout.get("real_holdout_available") or metrics.get("real_holdout_available")),
        "real_holdout_sufficient": bool(
            holdout.get("real_holdout_sufficient") or metrics.get("real_holdout_sufficient")
        ),
        "real_unseen_registry_counts": {
            "PDF_source_document_disjoint": pdf_count,
            "XLSX_workbook_disjoint": xlsx_count,
        },
        "minimum_targets": {
            "pdf_unseen_source_documents": pdf_target,
            "xlsx_unseen_workbooks": xlsx_target,
            "query_fidelity_included_rows_per_family": query_target,
        },
        "real_query_fidelity_included_counts": {
            "PDF": pdf_query_count,
            "XLSX": xlsx_query_count,
            "TEXT": int(query_counts.get("TEXT") or 0),
        },
        "source_family_split_requirements": {
            "PDF": "source_document_disjoint",
            "XLSX": "workbook_disjoint",
            "TEXT": "comparison_control_only",
        },
        "blocked_reasons": blocked_reasons,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
    }


def build_leakage_audit_gate(source_report: Mapping[str, Any]) -> dict[str, Any]:
    metrics = source_report.get("metrics") or {}
    leakage_rows = list(source_report.get("leakage_audit") or [])
    bucket_count = int(metrics.get("leakage_bucket_count") or len({row.get("bucket") for row in leakage_rows}))
    excluded_count = int(
        metrics.get("leakage_excluded_count")
        or sum(1 for row in leakage_rows if row.get("excluded_from_holdout") is True)
    )
    required_buckets = set(v44.LEAKAGE_BUCKETS)
    observed_buckets = {clean(row.get("bucket")) for row in leakage_rows}
    passed = bucket_count == len(required_buckets) and excluded_count == len(required_buckets)
    return {
        "schema_version": f"{RUN_ID}_leakage_audit_gate_v1",
        "run_id": RUN_ID,
        "passed": passed,
        "leakage_audit_infrastructure_ready": bool(source_report.get("leakage_audit_infrastructure_ready")),
        "leakage_bucket_count": bucket_count,
        "leakage_excluded_count": excluded_count,
        "required_buckets": sorted(required_buckets),
        "observed_buckets": sorted(observed_buckets),
        "excluded_from_holdout": passed,
        "interpreted_as_leakage_free_status": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
    }


def build_readiness_gates(source_report: Mapping[str, Any]) -> dict[str, Any]:
    evidence_gate = build_evidence_path_quality_gate(source_report)
    split_gate = build_split_quality_gate(source_report)
    leakage_gate = build_leakage_audit_gate(source_report)
    return {
        "schema_version": f"{RUN_ID}_readiness_gates_v1",
        "run_id": RUN_ID,
        "evidence_path_quality_gate": evidence_gate,
        "split_quality_gate": split_gate,
        "leakage_audit_gate": leakage_gate,
        "user_owned_gold_policy_gate": {
            "passed": False,
            "status": "pending_user_owned_gold_qrels_label_policy",
            "user_owned_decision_required": True,
        },
        "official_denominator_gate": {
            "passed": False,
            "status": "closed_pending_user_owned_denominator_policy",
            "official_metric_input_rows": 0,
        },
        "promotion_policy_gate": {
            "passed": False,
            "status": "closed_pending_user_owned_promotion_policy",
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
        },
    }


def _gate_passed(gates: Mapping[str, Any], key: str) -> bool:
    gate = gates.get(key) or {}
    return bool(gate.get("passed")) if isinstance(gate, Mapping) else False


def readiness_gate_passed(gates: Mapping[str, Any]) -> bool:
    return all(
        _gate_passed(gates, key)
        for key in (
            "evidence_path_quality_gate",
            "split_quality_gate",
            "leakage_audit_gate",
            "user_owned_gold_policy_gate",
            "official_denominator_gate",
            "promotion_policy_gate",
        )
    )


def blocked_reasons_for_lane(gates: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not _gate_passed(gates, "evidence_path_quality_gate"):
        reasons.append("evidence_path_quality_gate_failed")
    if not _gate_passed(gates, "split_quality_gate"):
        reasons.append("split_quality_gate_failed")
    if not _gate_passed(gates, "leakage_audit_gate"):
        reasons.append("leakage_audit_gate_failed")
    if not _gate_passed(gates, "user_owned_gold_policy_gate"):
        reasons.append("user_owned_gold_qrels_denominator_policy_pending")
    if not _gate_passed(gates, "official_denominator_gate"):
        reasons.append("official_denominator_policy_closed")
    if not _gate_passed(gates, "promotion_policy_gate"):
        reasons.append("promotion_policy_closed")
    return reasons


def build_fine_tuning_lanes(gates: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    reasons = blocked_reasons_for_lane(gates)
    lane_ready = not reasons
    lanes: dict[str, dict[str, Any]] = {}
    for lane_name, purpose in (
        ("SFT", "supervised source-grounded answer style adaptation"),
        ("DPO", "preference optimization after user-owned pair labels"),
        ("reward_model", "reward modeling after user-owned answer/evidence labels"),
    ):
        lanes[lane_name] = {
            "schema_version": f"{RUN_ID}_fine_tuning_lane_v1",
            "run_id": RUN_ID,
            "lane": lane_name,
            "purpose": purpose,
            "lane_ready": lane_ready,
            "readiness_only": True,
            "dataset_export_created": False,
            "training_job_created": False,
            "training_started": False,
            "training_executed": False,
            "model_or_adapter_checkpoint_written": False,
            "requires_gpu_when_opened": True,
            "blocked_reasons": reasons,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
        }
    return lanes


def build_family_separated_readiness(gates: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    split_gate = gates["split_quality_gate"]
    counts = split_gate["real_unseen_registry_counts"]
    targets = split_gate["minimum_targets"]
    return {
        "PDF": {
            "source_document_disjoint_required": True,
            "real_holdout_rows": counts["PDF_source_document_disjoint"],
            "minimum_target": targets["pdf_unseen_source_documents"],
            "query_fidelity_target": targets["query_fidelity_included_rows_per_family"],
            "readiness_success_evidence_allowed": False,
        },
        "XLSX": {
            "workbook_disjoint_required": True,
            "real_holdout_rows": counts["XLSX_workbook_disjoint"],
            "minimum_target": targets["xlsx_unseen_workbooks"],
            "query_fidelity_target": targets["query_fidelity_included_rows_per_family"],
            "readiness_success_evidence_allowed": False,
        },
        "TEXT": {
            "comparison_control_only": True,
            "real_holdout_rows": 0,
            "readiness_success_evidence_allowed": False,
        },
    }


def build_guardrails() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
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
        "db_or_production_namespace_written": False,
        "protected_namespaces_touched": [],
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
        "pdf_xlsx_text_collapsed_headline_product_score": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_route_policy_dry_run_executed": False,
        "route_policy_projection_recorded": True,
        "threshold_tuning": False,
        "winner_selection": False,
        "live_db_index_cache_readiness": False,
        "single_report_artifact_contract": True,
        "review_csv_created": False,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
        "local_llm_or_gpu_inference_required": False,
    }


def build_metrics(
    *,
    source_report: Mapping[str, Any],
    gates: Mapping[str, Any],
    lanes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    split_gate = gates["split_quality_gate"]
    leakage_gate = gates["leakage_audit_gate"]
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "fine_tuning_dataset_exports_created": sum(
            1 for lane in lanes.values() if lane.get("dataset_export_created") is True
        ),
        "ft_route_policy_dry_run_executed": False,
        "route_policy_projection_recorded": True,
        "readiness_gate_passed": readiness_gate_passed(gates),
        "evidence_path_quality_gate_passed": _gate_passed(gates, "evidence_path_quality_gate"),
        "split_quality_gate_passed": _gate_passed(gates, "split_quality_gate"),
        "leakage_audit_gate_passed": _gate_passed(gates, "leakage_audit_gate"),
        "user_owned_gold_policy_gate_passed": _gate_passed(gates, "user_owned_gold_policy_gate"),
        "official_denominator_gate_passed": _gate_passed(gates, "official_denominator_gate"),
        "promotion_policy_gate_passed": _gate_passed(gates, "promotion_policy_gate"),
        "readiness_decision": "ready_for_training" if readiness_gate_passed(gates) else (
            "blocked_pending_real_holdout_and_user_owned_policy"
        ),
        "real_holdout_available": bool(split_gate["real_holdout_available"]),
        "real_holdout_sufficient": bool(split_gate["real_holdout_sufficient"]),
        "real_unseen_registry_counts": dict(split_gate["real_unseen_registry_counts"]),
        "minimum_targets": dict(split_gate["minimum_targets"]),
        "real_query_fidelity_included_counts": dict(split_gate["real_query_fidelity_included_counts"]),
        "leakage_bucket_count": int(leakage_gate["leakage_bucket_count"]),
        "leakage_excluded_count": int(leakage_gate["leakage_excluded_count"]),
        "sft_ready": bool(lanes["SFT"]["lane_ready"]),
        "dpo_ready": bool(lanes["DPO"]["lane_ready"]),
        "reward_model_ready": bool(lanes["reward_model"]["lane_ready"]),
        "training_job_created": False,
        "training_dataset_exported_for_training": False,
        "model_or_adapter_checkpoint_written": False,
        "review_csv_created": False,
        "single_report_artifact_contract": True,
        "sidecar_primary_artifacts_suppressed": True,
        "source_gate_status": clean(source_report.get("status")),
        "source_gate_run_id": clean(source_report.get("run_id")),
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
    source_report: Mapping[str, Any],
) -> dict[str, Any]:
    summary = dict(metrics)
    summary.update(
        {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "event_type": EVENT_TYPE,
            "status": STATUS,
            "v4_name": V4_NAME,
            "run_family": V4_RUN_FAMILY,
            "run_class": "diagnostic_only_finetune_readiness_packet_nonprod",
            "generated_at": utc_now(),
            "artifact_paths": dict(artifact_paths),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
            "human_review_required": False,
            "production_routing": False,
            "official_metric_lift": False,
            "fine_tuning_readiness_only": True,
            "fine_tuning_started": False,
            "fine_tuning_executed": False,
            "fine_tuning_dataset_export_created": False,
            "training_manifest_jsonl_created": False,
            "fine_tuning_lanes_json_created": False,
            "prompt_payload_created": False,
            "raw_llm_response_payload_created": False,
            "live_db_index_cache_readiness": False,
            "previous_gate_run_id": clean(source_report.get("run_id")),
            "previous_gate_report_sha256": previous_gate_report_sha256(source_report),
        }
    )
    return summary


def build_verification_section() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_verification_v1",
        "run_id": RUN_ID,
        "commands_required_by_goal": [
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py",
            "python -X utf8 ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py --check",
            "targeted v4_5 fine-tuning readiness tests",
            "targeted artifact/status/guardrail tests",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
            "git diff --cached --check",
            "git check-ignore -v for v4_5 report.json and status.jsonl",
        ],
        "results_recorded_in_final_response": True,
        "gpu_note": (
            "No GPU workload is executed in v4_5 because this slice performs deterministic readiness "
            "gate materialization. Future training/inference workloads should use GPU when opened."
        ),
    }


def build_report(
    *,
    source_report: Mapping[str, Any],
    gates: Mapping[str, Any],
    lanes: Mapping[str, Mapping[str, Any]],
    metrics: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    summary = build_summary(metrics=metrics, artifact_paths=artifact_paths, source_report=source_report)
    family_readiness = build_family_separated_readiness(gates)
    blocked_reasons = blocked_reasons_for_lane(gates)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "production_routing": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "fine_tuning_dataset_export_created": False,
        "training_job_created": False,
        "training_dataset_exported_for_training": False,
        "model_or_adapter_checkpoint_written": False,
        "ft_route_policy_dry_run_executed": False,
        "route_policy_projection_recorded": True,
        "live_db_index_cache_readiness": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "single_report_artifact_contract": True,
        "human_review_required": False,
        "review_csv_created": False,
        "readiness_decision": metrics["readiness_decision"],
        "blocked_reasons": blocked_reasons,
        "artifact_paths": dict(artifact_paths),
        "source_run_references": source_run_references(),
        "input_lineage": {
            **source_run_references(),
            "previous_gate_report_sha256": previous_gate_report_sha256(source_report),
        },
        "summary": summary,
        "metrics": dict(metrics),
        "family_separated_readiness": family_readiness,
        "readiness_gates": dict(gates),
        "fine_tuning_lanes": {key: dict(value) for key, value in lanes.items()},
        "ft_route_policy_dry_run": {
            "schema_version": f"{RUN_ID}_ft_route_policy_dry_run_v1",
            "run_id": RUN_ID,
            "executed": False,
            "route_policy_projection_recorded": True,
            "created_prompt_payload": False,
            "created_raw_llm_response_payload": False,
            "created_training_dataset_export": False,
            "created_training_job": False,
            "decision": metrics["readiness_decision"],
            "blocked_reasons": blocked_reasons,
        },
        "guardrails": dict(guardrails),
        "guardrail_audit": dict(guardrails),
        "verification": build_verification_section(),
        "changed_files": [
            "ai/scripts/rag_v4_5_finetune_readiness_packet_nonprod.py",
            "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
            "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py",
            "ai/tests/test_rag_diagnostic_guardrail_git_diff.py",
            "ai/tests/test_rag_diagnostic_status_sync.py",
            "ai/tests/test_rag_current_focused_test_profile_v1.py",
            "docs/rag-ingestion-progress.md",
            "docs/rag-ingestion-measurements.md",
            "docs/rag-ingestion-triage.md",
            "README.md",
            "ai/eval/README.md",
            "ai/scripts/README.md",
            "reports/rag_eval/rag-ingestion/status.jsonl",
        ],
        "residual_risks": [
            "Real PDF source-document-disjoint and XLSX workbook-disjoint holdout rows remain unavailable in this checkout.",
            "Real query-fidelity included rows remain below the per-family target, so split quality is not open.",
            "User-owned gold/qrels/denominator and promotion policy remain pending, so no training lane is ready.",
            "No official metric rows, production routing, threshold tuning, winner selection, dataset export, or training execution are emitted.",
        ],
        "next_recommendation": (
            "Carry v4 forward by acquiring real source-disjoint PDF/XLSX holdout identities and user-owned label/qrels/"
            "denominator policy before any fine-tuning dataset export or GPU training job is opened."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    source_report = load_v4_4_report()
    gates = build_readiness_gates(source_report)
    lanes = build_fine_tuning_lanes(gates)
    guardrails = build_guardrails()
    metrics = build_metrics(source_report=source_report, gates=gates, lanes=lanes)
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        source_report=source_report,
        gates=gates,
        lanes=lanes,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "source_report": source_report,
        "readiness_gates": gates,
        "fine_tuning_lanes": lanes,
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
        raise RuntimeError(f"unexpected v4_5 primary artifacts: {unexpected}")


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
    report["summary"]["review_csv_created"] = False
    report["summary"]["training_manifest_jsonl_created"] = False
    report["summary"]["fine_tuning_lanes_json_created"] = False
    report["metrics"] = dict(report["metrics"])
    report["metrics"]["single_report_artifact_contract"] = True
    report["metrics"]["sidecar_primary_artifacts_suppressed"] = True
    report["metrics"]["review_csv_created"] = False
    report["review_csv_created"] = False
    report["human_review_required"] = False
    report["fine_tuning_dataset_export_created"] = False
    remove_stale_sidecar_artifacts(target_dir)
    assert_single_report_directory(target_dir)
    write_json(report_path, report)
    assert_single_report_directory(target_dir)
    return report


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v44.replace_marked_entry(path, marker, entry)


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_5 fine-tuning readiness packet loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_4 real blind/OOD holdout and leakage audit loop:\n`[^`]+`;",
        "current diagnostic v4_5 fine-tuning readiness packet loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_4 real blind/OOD holdout and leakage audit loop:\n`{v44.RUN_ID}`;",
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
    readme_verify_block = (
        "```powershell\n"
        "python -X utf8 -m py_compile "
        "ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py --check\n"
        "python -X utf8 -m pytest ai/tests --rag-current -q\n"
        "```"
    )
    verify_start = readme_text.index("## How To Verify Locally")
    verify_end = readme_text.index("## Repo Map")
    verify_section = readme_text[verify_start:verify_end]
    verify_section = re.sub(
        r"```powershell\n.*?```",
        lambda _match: readme_verify_block,
        verify_section,
        count=1,
        flags=re.DOTALL,
    )
    readme_text = readme_text[:verify_start] + verify_section + readme_text[verify_end:]
    README.write_text(readme_text, encoding="utf-8")

    eval_readme_text = EVAL_README.read_text(encoding="utf-8")
    eval_readme_text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{EVENT_TYPE}_ready`",
        eval_readme_text,
        count=1,
    )
    eval_readme_text = eval_readme_text.replace(
        f"v4_4 is `{v44.EVENT_TYPE}_ready`.",
        f"v4_4 is `{v44.EVENT_TYPE}_ready`; v4_5 is `{EVENT_TYPE}_ready`.",
    )
    EVAL_README.write_text(eval_readme_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    marker = "v4_diagnostic_runtime_locator_and_finetune_readiness_inventory"
    entry = f"""## v4 RAG Diagnostic Runtime/Locator/Fine-Tuning Readiness Inventory

| Script | Role |
|---|---|
| `rag_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod.py` | Persists the v3_22 XLSX display metadata contract into SourceAtom-owned runtime-adjacent fields. |
| `rag_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod.py` | Packages family-separated XLSX table/range/cell locator diagnostics from seen-reference v3 surfaces. |
| `rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py` | Keeps PDF file identity confidence separate from answer-ready evidence-window diagnostics. |
| `rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py` | Materializes real blind/OOD holdout and leakage-audit infrastructure while fail-closing on unavailable source-disjoint holdout. |
| `rag_v4_5_finetune_readiness_packet_nonprod.py` | Builds the fine-tuning-readiness-only packet after v4_4 gates; no dataset export, training job, checkpoint, official metric, promotion, or product-success evidence is emitted. |

v4 scripts remain diagnostic/non-production and write one ignored `report.json`
per run. Actual fine-tuning remains closed until real disjoint splits and
user-owned gold/qrels/denominator policy exist.
"""
    replace_marked_entry(scripts_readme, marker, entry)
    text = scripts_readme.read_text(encoding="utf-8")
    text = text.replace(
        "Do not convert diagnostic scripts into production code. Keep v3_19-v3_21 as\n"
        "runtime/observability predecessors, keep v3_22 as the single-report closure\n"
        "entrypoint, and carry v4 work into persisted locator/holdout/fine-tuning\n"
        "readiness only after the diagnostic boundaries remain green.\n",
        "Do not convert diagnostic scripts into production code. Keep v3_19-v3_21 as\n"
        "runtime/observability predecessors, keep v3_22 as the single-report closure\n"
        "entrypoint, and keep v4 work in persisted locator/holdout/fine-tuning\n"
        "readiness lanes only while the diagnostic boundaries remain green.\n",
    )
    scripts_readme.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    gates = report["readiness_gates"]
    report_path = report["artifact_paths"]["report_json"]
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v44.v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)
    progress_entry = (
        f"- v4_5 fine-tuning readiness packet (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        f"It packages v4_4 holdout, split, query-fidelity, leakage-audit, and excluded-row gate evidence into one "
        f"`report.json` at `{report_path}` and records a route-policy projection only: no dry run, prompt payload, raw LLM response, "
        "training dataset export, training job, model/adaptor checkpoint, official metric row, promotion evidence, "
        "or product-success evidence is created. The packet is blocked for actual fine-tuning because real disjoint "
        "PDF/XLSX holdout and real query-fidelity rows remain below target, and user-owned gold/qrels/denominator "
        "policy remains closed. Boundary: diagnostic-only, non-production, not official metric lift, not live "
        "DB/index/cache readiness, not threshold tuning, not winner selection, and not representative product performance."
    )
    measurements_entry = f"""### v4_5 Fine-Tuning Readiness Packet

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, fine-tuning-readiness only, single `report.json`.
- Primary artifact: `{report_path}`
- Source evidence: v4_4 real blind/OOD holdout and leakage-audit report.

| Diagnostic count | Value |
| --- | ---: |
| readiness_gate_passed | false |
| evidence_path_quality_gate_passed | {str(metrics["evidence_path_quality_gate_passed"]).lower()} |
| split_quality_gate_passed | {str(metrics["split_quality_gate_passed"]).lower()} |
| leakage_audit_gate_passed | {str(metrics["leakage_audit_gate_passed"]).lower()} |
| PDF_source_document_disjoint | {metrics["real_unseen_registry_counts"]["PDF_source_document_disjoint"]}/{metrics["minimum_targets"]["pdf_unseen_source_documents"]} |
| XLSX_workbook_disjoint | {metrics["real_unseen_registry_counts"]["XLSX_workbook_disjoint"]}/{metrics["minimum_targets"]["xlsx_unseen_workbooks"]} |
| real_query_fidelity_included_rows_per_family | {metrics["real_query_fidelity_included_counts"]["PDF"]}/{metrics["minimum_targets"]["query_fidelity_included_rows_per_family"]} PDF, {metrics["real_query_fidelity_included_counts"]["XLSX"]}/{metrics["minimum_targets"]["query_fidelity_included_rows_per_family"]} XLSX |
| leakage_bucket_count | {metrics["leakage_bucket_count"]} |
| leakage_excluded_count | {metrics["leakage_excluded_count"]} |
| fine_tuning_dataset_exports_created | 0 |
| sft_ready | false |
| dpo_ready | false |
| reward_model_ready | false |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| fine_tuning_started | false |
| fine_tuning_executed | false |
| ft_route_policy_dry_run_executed | false |
| route_policy_projection_recorded | true |
| gpu_required_for_this_slice | false |
| gpu_required_for_future_training_when_opened | true |

Counter source-of-truth: `report.json` embeds readiness_gates, fine_tuning_lanes, ft_route_policy_dry_run, metrics, family_separated_readiness, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV, training manifest, dataset sidecar, checkpoint, or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_5 Fine-Tuning Readiness Packet Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_5 is a diagnostic fine-tuning-readiness packet, not actual fine-tuning/training.\n"
        "- Evidence path quality is read from v4_4 guardrails: SourceAtom/EvidenceBundle remains evidence truth and SearchView/vector remains candidate-only.\n"
        "- Split quality remains blocked: PDF source-document-disjoint and XLSX workbook-disjoint holdout counts are below target, and real query-fidelity rows remain below the per-family target.\n"
        "- Leakage audit infrastructure is carried forward as exclusion coverage, not as leakage-free or product-success evidence.\n"
        "- SFT, DPO, and reward-model lanes are all blocked; no dataset export, training job, prompt payload, raw LLM response, or checkpoint is created.\n"
        "- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy.\n"
        "- GPU is not required for this deterministic readiness packet; future training or LLM/index workloads should use GPU when opened.\n"
        "- Next lane: acquire real source-disjoint PDF/XLSX holdout identities and user-owned label/qrels/denominator policy before opening any fine-tuning dataset export.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    update_scripts_readme()
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v44.v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)


def artifact_sha256_from_report_paths(artifact_paths: Mapping[str, str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path_text in artifact_paths.items():
        path = Path(path_text)
        if not path.is_absolute():
            path = ROOT / path_text
        if artifact_exists(path):
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
        "raw_llm_response_payload_created": False,
        "prompt_payload_created": False,
        "training_manifest_jsonl_created": False,
        "fine_tuning_lanes_json_created": False,
        "fine_tuning_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
        "readiness_gates": dict(report["readiness_gates"]),
        "readiness_decision": report["readiness_decision"],
        "blocked_reasons": list(report["blocked_reasons"]),
        "schema_version": f"{RUN_ID}_status_event_v1",
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


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
    if args.check:
        artifacts = build_artifacts()
        metrics = artifacts["metrics"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["report"]["summary"]["status"],
                    "readiness_gate_passed": metrics["readiness_gate_passed"],
                    "split_quality_gate_passed": metrics["split_quality_gate_passed"],
                    "leakage_audit_gate_passed": metrics["leakage_audit_gate_passed"],
                    "fine_tuning_dataset_exports_created": metrics["fine_tuning_dataset_exports_created"],
                    "official_metric_input_rows": metrics["official_metric_input_rows"],
                    "gpu_required_for_this_slice": metrics["gpu_required_for_this_slice"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    report = run_write()
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "report": report["artifact_paths"]["report_json"],
                "status": report["summary"]["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
