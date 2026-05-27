from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod as v4610
from app.capabilities.rag import holdout_manifest_contract


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
RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod"
EVENT_TYPE = "diagnostic_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod"
STATUS_READY = "V4_7_PREOFFICIAL_EXTERNAL_HOLDOUT_CANDIDATE_MANIFEST_REGISTRATION_READY"
STATUS_INPUT_REQUIRED = "v4_7_preofficial_external_holdout_candidate_manifest_registration_input_required"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_report_v1"

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v4610.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
            "candidate_manifest.jsonl",
            "candidate_validation.jsonl",
            "manifest_registration.json",
            "metrics.json",
            "source_identity_audit.jsonl",
            "summary.json",
            "v4_7_official_metric_input_rows.jsonl",
        }
    )
)

FORBIDDEN_PACKET_FIELDS = tuple(
    sorted(
        {
            "answerability_label",
            "cache_namespace",
            "candidate_manifest_path",
            "dataset_output_path",
            "db_namespace",
            "dry_run_input_manifest_path",
            "expected_answer",
            "expected_answer_text",
            "expected_evidence",
            "fine_tuning_dataset_path",
            "full_prompt",
            "gold_answer",
            "gold_locator",
            "gold_supporting_text",
            "index_namespace",
            "job_id",
            "job_name",
            "llm_response",
            "manifest_path",
            "namespace",
            "official_metric",
            "official_metric_input_rows",
            "output_path",
            "product_success_evidence_allowed",
            "production_namespace",
            "promotion_evidence",
            "prompt",
            "prompt_payload",
            "prompt_text",
            "qrels_label",
            "raw_file_path",
            "raw_llm_request",
            "raw_llm_response",
            "raw_prompt",
            "source_identity_audit_path",
            "supporting_evidence",
            "supporting_evidence_text",
            "target_locator",
            "training_manifest_path",
            "v4_7_official_metric_gate_opened",
        }
    )
)


def clean(value: Any) -> str:
    return v4610.clean(value)


def repo_relative(path: Path) -> str:
    return v4610.repo_relative(path)


def utc_now() -> str:
    return v4610.utc_now()


def sha256_file(path: Path) -> str:
    return v4610.sha256_file(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v4610.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v4610.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v4610.write_jsonl(path, rows)


def _reason_counts(*reason_maps: Mapping[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for reason_map in reason_maps:
        for reason, value in reason_map.items():
            if clean(reason):
                counts[clean(reason)] += int(value or 0)
    return dict(sorted(counts.items()))


def _count_manifest_rows_by_family(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"PDF": 0, "XLSX": 0, "TEXT": 0}
    for row in rows:
        family = clean(row.get("source_family")).upper()
        if family in counts:
            counts[family] += 1
    return counts


def _minimum_targets() -> dict[str, int]:
    return dict(holdout_manifest_contract.MINIMUM_TARGETS)


def _query_counts(replay: Mapping[str, Any]) -> dict[str, int]:
    raw_counts = replay.get("real_query_fidelity_included_counts")
    raw_counts = raw_counts if isinstance(raw_counts, Mapping) else {}
    return {
        "PDF": int(raw_counts.get("PDF") or 0),
        "XLSX": int(raw_counts.get("XLSX") or 0),
        "TEXT": int(raw_counts.get("TEXT") or 0),
    }


def _accepted_counts(replay: Mapping[str, Any]) -> dict[str, int]:
    return {
        "PDF": int(replay.get("accepted_pdf_holdout_candidates") or 0),
        "XLSX": int(replay.get("accepted_xlsx_holdout_candidates") or 0),
        "TEXT": int(replay.get("accepted_text_control_candidates") or 0),
    }


def _thresholds_met(replay: Mapping[str, Any]) -> bool:
    targets = _minimum_targets()
    accepted = _accepted_counts(replay)
    query_counts = _query_counts(replay)
    return bool(
        accepted["PDF"] >= targets["pdf_unseen_source_documents"]
        and accepted["XLSX"] >= targets["xlsx_unseen_workbooks"]
        and query_counts["PDF"] >= targets["query_fidelity_included_rows_per_family"]
        and query_counts["XLSX"] >= targets["query_fidelity_included_rows_per_family"]
    )


def build_user_input_requirements_packet(
    *,
    replay: Mapping[str, Any] | None = None,
    candidate_manifest_available: bool = False,
) -> dict[str, Any]:
    replay = replay or {}
    accepted = _accepted_counts(replay)
    query_counts = _query_counts(replay)
    targets = _minimum_targets()
    deficits = {
        "pdf_source_document_disjoint_needed": max(0, targets["pdf_unseen_source_documents"] - accepted["PDF"]),
        "xlsx_workbook_disjoint_needed": max(0, targets["xlsx_unseen_workbooks"] - accepted["XLSX"]),
        "pdf_query_fidelity_rows_needed": max(0, targets["query_fidelity_included_rows_per_family"] - query_counts["PDF"]),
        "xlsx_query_fidelity_rows_needed": max(0, targets["query_fidelity_included_rows_per_family"] - query_counts["XLSX"]),
    }
    base_packet = holdout_manifest_contract.build_holdout_acquisition_requirements(
        deficits=deficits,
        accepted_source_counts={
            "PDF_source_document_disjoint": accepted["PDF"],
            "XLSX_workbook_disjoint": accepted["XLSX"],
        },
        query_fidelity_included_counts=query_counts,
        blocked_reasons=(
            [] if candidate_manifest_available else ["external_holdout_candidate_manifest_missing"]
        ),
        readiness_decision=(
            "preofficial_candidate_manifest_registration_ready"
            if candidate_manifest_available and _thresholds_met(replay)
            else "blocked_pending_real_external_holdout_candidates_and_user_policy"
        ),
    )
    return {
        **base_packet,
        "preofficial_registration_lane": True,
        "required_file_source_counts": {
            "pdf_source_document_disjoint": targets["pdf_unseen_source_documents"],
            "xlsx_workbook_disjoint": targets["xlsx_unseen_workbooks"],
            "pdf_query_fidelity_rows": targets["query_fidelity_included_rows_per_family"],
            "xlsx_query_fidelity_rows": targets["query_fidelity_included_rows_per_family"],
        },
        "required_row_fields": list(base_packet["required_candidate_row_fields"]),
        "forbidden_fields": list(FORBIDDEN_PACKET_FIELDS),
        "accepted_examples": {
            "PDF": {
                "candidate_id": "pdf_candidate_001_query_001",
                "query_id": "pdf_query_001",
                "source_family": "PDF",
                "source_document_id": "external_pdf_document_sha256_001",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
            "XLSX": {
                "candidate_id": "xlsx_candidate_001_query_001",
                "query_id": "xlsx_query_001",
                "source_family": "XLSX",
                "workbook_id": "external_xlsx_workbook_sha256_001",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            },
        },
        "rejected_examples": {
            "oracle_field": {
                "field": "expected_answer",
                "rejection_reason": "protected_oracle_field_present",
            },
            "raw_local_path": {
                "field": "source_document_id",
                "value": "__raw_local_path_redacted__",
                "rejection_reason": "raw_local_path_present",
            },
            "XLSX_source_identity_only": {
                "source_family": "XLSX",
                "source_identity": "cell_or_sheet_level_identity_only",
                "rejection_reason": "workbook_identity_missing",
            },
            "prior_identity_collision": {
                "source_family": "PDF",
                "rejection_reason": "prior_source_identity_collision",
            },
            "leakage_bucket": {
                "field": "leakage_bucket",
                "rejection_reason": "leakage_bucket_present",
            },
        },
        "pdf_document_identity_proof": {
            "accepted_identity_fields": [
                "document_version_id",
                "source_document_id",
                "document_id",
                "source_identity",
            ],
            "document_or_document_version_identity_required": True,
            "same_tier_distinct_identity_values_fail_closed": True,
        },
        "xlsx_workbook_identity_proof": {
            "accepted_identity_fields": ["workbook_id", "source_workbook_id", "workbook_version_id"],
            "workbook_level_identity_required": True,
            "source_identity_only_rejected": True,
            "source_identity_only_rejection_reason": "workbook_identity_missing",
        },
        "prior_identity_collision_exclusion": {
            "uses_v4_5_3_prior_identity_hash_ledger": True,
            "collision_rejection_reason": "prior_source_identity_collision",
            "raw_prior_identities_embedded": False,
        },
        "leakage_bucket_exclusion": {
            "non_empty_leakage_bucket_rejected": True,
            "rejection_reason": "leakage_bucket_present",
        },
        "query_fidelity_counting": {
            "minimum_included_rows_per_family": {
                "PDF": targets["query_fidelity_included_rows_per_family"],
                "XLSX": targets["query_fidelity_included_rows_per_family"],
            },
            "counting_unit": "accepted unique query_id per source_family",
            "excluded_rows_do_not_count": True,
            "query_fidelity_included_must_be_true": True,
        },
    }


def build_preofficial_registration(
    *,
    candidate_manifest_path: Path | None = None,
    prior_identity_rows: Sequence[Mapping[str, Any]] | None = None,
    prior_identity_summary_report: Mapping[str, Any] | None = None,
    prior_identity_summary_report_path: Path | None = None,
) -> dict[str, Any]:
    source_inputs = v4610.build_source_report_inputs()
    replay = v4610.build_external_holdout_candidate_manifest_gate_replay(
        source_inputs,
        candidate_manifest_path=candidate_manifest_path,
        prior_identity_rows=prior_identity_rows,
        prior_identity_summary_report=prior_identity_summary_report,
        prior_identity_summary_report_path=prior_identity_summary_report_path,
    )
    manifest_rows, manifest_input = v4610.v452.load_candidate_manifest_rows(candidate_manifest_path)
    candidate_manifest_available = bool(replay.get("candidate_manifest_present"))
    accepted = _accepted_counts(replay)
    query_counts = _query_counts(replay)
    rejection_buckets = _reason_counts(
        replay.get("source_identity_audit_exclusion_reasons") or {},
        {}
        if replay.get("source_identity_audit_exclusion_reasons")
        else replay.get("candidate_intake_exclusion_reasons") or {},
    )
    rejected_count = sum(rejection_buckets.values())
    thresholds_met = _thresholds_met(replay)
    source_identity_collision_count = int(replay.get("source_identity_collision_count") or 0)
    registration_gate_passed = bool(
        candidate_manifest_available
        and thresholds_met
        and replay.get("v4_5_1_intake_gate_passed") is True
        and replay.get("v4_5_2_source_identity_audit_gate_passed") is True
        and source_identity_collision_count == 0
        and rejected_count == 0
    )
    blocked_reasons: list[str] = []
    if clean(manifest_input.get("load_error")):
        blocked_reasons.append(clean(manifest_input.get("load_error")))
    if not candidate_manifest_available:
        blocked_reasons.append("external_holdout_candidate_manifest_missing")
    if candidate_manifest_available and replay.get("v4_5_1_intake_gate_passed") is not True:
        blocked_reasons.append("candidate_intake_gate_failed")
    if candidate_manifest_available and replay.get("v4_5_2_source_identity_audit_gate_passed") is not True:
        blocked_reasons.append("source_identity_audit_failed")
    if candidate_manifest_available and not thresholds_met:
        blocked_reasons.append("candidate_registration_thresholds_not_met")
    if rejected_count:
        blocked_reasons.append("candidate_rows_excluded")
    if not registration_gate_passed:
        blocked_reasons.append("preofficial_registration_gate_not_passed")
    blocked_reasons.extend(
        [
            "official_metric_gate_closed",
            "user_owned_gold_qrels_policy_gate_closed",
            "official_denominator_gate_closed",
            "promotion_policy_gate_closed",
        ]
    )
    return {
        "schema_version": f"{RUN_ID}_registration_v1",
        "run_id": RUN_ID,
        "status": STATUS_READY if registration_gate_passed else STATUS_INPUT_REQUIRED,
        "diagnostic_only": True,
        "preofficial_external_holdout_candidate_manifest_registration_only": True,
        "candidate_manifest_available": candidate_manifest_available,
        "candidate_manifest_input_only": True,
        "candidate_manifest_input": v4610._manifest_input_for_v4_6_10(manifest_input),
        "candidate_manifest_exported": False,
        "candidate_rows_registered": int(replay.get("candidate_rows_replayed") or 0),
        "candidate_counts_by_family": _count_manifest_rows_by_family(manifest_rows),
        "accepted_candidate_counts_by_family": accepted,
        "accepted_pdf_holdout_candidates": accepted["PDF"],
        "accepted_xlsx_holdout_candidates": accepted["XLSX"],
        "accepted_text_control_candidates": accepted["TEXT"],
        "real_query_fidelity_included_counts": query_counts,
        "rejected_candidate_count": rejected_count,
        "rejection_buckets": rejection_buckets,
        "v4_5_1_intake_gate_passed": bool(replay.get("v4_5_1_intake_gate_passed")),
        "v4_5_2_source_identity_audit_gate_passed": bool(replay.get("v4_5_2_source_identity_audit_gate_passed")),
        "v4_6_10_manifest_replay_executed": True,
        "v4_6_10_manifest_replay_candidate_gate_target_sufficient": bool(
            replay.get("candidate_gate_target_sufficient")
        ),
        "source_identity_collision_count": source_identity_collision_count,
        "source_identity_audit_excluded_count": int(replay.get("source_identity_audit_excluded_count") or 0),
        "prior_identity_collisions_excluded": source_identity_collision_count == 0,
        "leakage_buckets_excluded": "leakage_bucket_present" not in rejection_buckets,
        "protected_oracle_fields_absent": "protected_oracle_field_present" not in rejection_buckets,
        "raw_local_paths_absent": "raw_local_path_present" not in rejection_buckets,
        "xlsx_source_identity_only_rows_rejected": "workbook_identity_missing" in rejection_buckets or rejected_count == 0,
        "preofficial_candidate_thresholds_met": thresholds_met,
        "registration_gate_passed": registration_gate_passed,
        "user_input_required": not registration_gate_passed,
        "user_owned_policy_input_still_required": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "v4_7_official_metric_gate_opened": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "live_db_index_cache_readiness": False,
        "real_holdout_sufficient": False,
        "blocked_reasons": list(dict.fromkeys(blocked_reasons)),
    }


def build_guardrails(status: str) -> dict[str, Any]:
    guardrails = v4610.build_guardrails()
    guardrails.update(
        {
            "schema_version": f"{RUN_ID}_guardrail_audit_v1",
            "run_id": RUN_ID,
            "status": status,
            "preofficial_external_holdout_candidate_manifest_registration_only": True,
            "candidate_manifest_registration_lane_opened": True,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "v4_7_official_metric_gate_opened": False,
            "product_success_evidence_allowed": False,
            "promotion_evidence": False,
            "live_db_index_cache_readiness": False,
        }
    )
    return guardrails


def _compact_v4_6_10_replay(replay: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_version",
        "holdout_candidate_manifest_contract_version",
        "holdout_candidate_manifest_contract_hash_algorithm",
        "holdout_candidate_manifest_contract_hash",
        "candidate_manifest_present",
        "candidate_manifest_input_only",
        "candidate_manifest_input",
        "candidate_manifest_exported",
        "candidate_rows_replayed",
        "accepted_pdf_holdout_candidates",
        "accepted_xlsx_holdout_candidates",
        "accepted_text_control_candidates",
        "real_query_fidelity_included_counts",
        "excluded_candidate_count",
        "candidate_intake_exclusion_reasons",
        "source_identity_audit_exclusion_reasons",
        "source_identity_collision_count",
        "source_identity_audit_excluded_count",
        "prior_identity_baseline_present",
        "prior_identity_hash_summary_rows",
        "v4_5_1_intake_gate_passed",
        "v4_5_2_source_identity_audit_gate_passed",
        "candidate_gate_target_sufficient",
        "real_holdout_sufficient",
        "official_metric_input_rows",
        "v4_7_official_metric_gate_opened",
        "promotion_evidence",
        "product_success_evidence_allowed",
    )
    return {key: replay.get(key) for key in keys if key in replay}


def build_artifacts(
    *,
    candidate_manifest_path: Path | None = None,
    prior_identity_rows: Sequence[Mapping[str, Any]] | None = None,
    prior_identity_summary_report: Mapping[str, Any] | None = None,
    prior_identity_summary_report_path: Path | None = None,
) -> dict[str, Any]:
    contract = holdout_manifest_contract.build_holdout_candidate_manifest_contract()
    source_inputs = v4610.build_source_report_inputs()
    replay = v4610.build_external_holdout_candidate_manifest_gate_replay(
        source_inputs,
        candidate_manifest_path=candidate_manifest_path,
        prior_identity_rows=prior_identity_rows,
        prior_identity_summary_report=prior_identity_summary_report,
        prior_identity_summary_report_path=prior_identity_summary_report_path,
    )
    registration = build_preofficial_registration(
        candidate_manifest_path=candidate_manifest_path,
        prior_identity_rows=prior_identity_rows,
        prior_identity_summary_report=prior_identity_summary_report,
        prior_identity_summary_report_path=prior_identity_summary_report_path,
    )
    status = clean(registration.get("status")) or STATUS_INPUT_REQUIRED
    guardrails = build_guardrails(status)
    packet = build_user_input_requirements_packet(
        replay=replay,
        candidate_manifest_available=bool(registration["candidate_manifest_available"]),
    )
    metrics = {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": status,
        "diagnostic_only": True,
        "preofficial_external_holdout_candidate_manifest_registration_only": True,
        "registration_gate_passed": bool(registration["registration_gate_passed"]),
        "candidate_manifest_available": bool(registration["candidate_manifest_available"]),
        "candidate_rows_registered": int(registration["candidate_rows_registered"]),
        "accepted_pdf_holdout_candidates": int(registration["accepted_pdf_holdout_candidates"]),
        "accepted_xlsx_holdout_candidates": int(registration["accepted_xlsx_holdout_candidates"]),
        "rejected_candidate_count": int(registration["rejected_candidate_count"]),
        "source_identity_collision_count": int(registration["source_identity_collision_count"]),
        "real_query_fidelity_included_counts": dict(registration["real_query_fidelity_included_counts"]),
        "preofficial_candidate_thresholds_met": bool(registration["preofficial_candidate_thresholds_met"]),
        "real_holdout_sufficient": False,
        "user_owned_policy_input_still_required": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "v4_7_official_metric_gate_opened": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "live_db_index_cache_readiness": False,
    }
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": status,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "preofficial_external_holdout_candidate_manifest_registration_only": True,
        "holdout_candidate_manifest_contract": contract,
        "holdout_candidate_manifest_contract_version": contract["schema_version"],
        "holdout_candidate_manifest_contract_hash_algorithm": contract["contract_hash_algorithm"],
        "holdout_candidate_manifest_contract_hash": contract["contract_hash"],
        "preofficial_external_holdout_candidate_manifest_registration": registration,
        "v4_6_10_manifest_gate_replay": _compact_v4_6_10_replay(replay),
        "user_input_requirements_packet": packet,
        "source_report_inputs": source_inputs,
        "metrics": metrics,
        "guardrails": guardrails,
        "guardrail_audit": dict(guardrails),
        "candidate_manifest_available": bool(registration["candidate_manifest_available"]),
        "candidate_manifest_present": bool(registration["candidate_manifest_available"]),
        "candidate_manifest_exported": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "candidate_rows_registered": int(registration["candidate_rows_registered"]),
        "candidate_counts_by_family": dict(registration["candidate_counts_by_family"]),
        "accepted_candidate_counts_by_family": dict(registration["accepted_candidate_counts_by_family"]),
        "accepted_pdf_holdout_candidates": int(registration["accepted_pdf_holdout_candidates"]),
        "accepted_xlsx_holdout_candidates": int(registration["accepted_xlsx_holdout_candidates"]),
        "real_query_fidelity_included_counts": dict(registration["real_query_fidelity_included_counts"]),
        "rejected_candidate_count": int(registration["rejected_candidate_count"]),
        "rejection_buckets": dict(registration["rejection_buckets"]),
        "registration_gate_passed": bool(registration["registration_gate_passed"]),
        "preofficial_candidate_thresholds_met": bool(registration["preofficial_candidate_thresholds_met"]),
        "user_input_required": bool(registration["user_input_required"]),
        "user_owned_policy_input_still_required": True,
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
            "status": status,
            "diagnostic_only": True,
            "preofficial_external_holdout_candidate_manifest_registration_only": True,
            "registration_gate_passed": bool(registration["registration_gate_passed"]),
            "candidate_manifest_available": bool(registration["candidate_manifest_available"]),
            "candidate_rows_registered": int(registration["candidate_rows_registered"]),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
        },
        "blocked_reasons": list(registration["blocked_reasons"]),
        "readiness_decision": (
            "preofficial_candidate_manifest_registration_ready_official_metric_closed"
            if registration["registration_gate_passed"]
            else "v4_7_preofficial_external_holdout_candidate_manifest_registration_input_required"
        ),
        "residual_risks": [
            "Registered candidate rows are pre-official holdout candidates only, not gold/qrels/expected-answer rows.",
            "Official denominator, gold/qrels policy, promotion policy, FT-A execution, and live readiness remain closed.",
        ],
        "next_recommendation": (
            "Use the registered manifest only as pre-official source-disjoint candidate evidence; do not promote it "
            "to official metric input until user-owned gold/qrels, denominator, and promotion policies are supplied."
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
        raise RuntimeError(f"unexpected v4_7 primary artifacts: {unexpected}")


def write_artifacts(artifacts: Mapping[str, Any], *, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    remove_stale_sidecar_artifacts(output_dir)
    assert_single_report_directory(output_dir)
    report = dict(artifacts["report"])
    report_json = output_dir / "report.json"
    report["artifact_paths"] = {
        "report_json": "__external_report_json_path_redacted__"
        if output_dir != OUTPUT_DIR
        else repo_relative(REPORT_JSON)
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
        "status": clean(report["status"]),
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": sha256_file(REPORT_JSON)},
        "diagnostic_only": True,
        "preofficial_external_holdout_candidate_manifest_registration_only": True,
        "candidate_manifest_exported": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_exports_created": 0,
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


def forbidden_surface_violation_count(payload: Mapping[str, Any]) -> int:
    return v4610.forbidden_surface_violation_count(payload)


def raw_source_identity_or_path_leak_count(payload: Mapping[str, Any]) -> int:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    patterns = (r"[A-Za-z]:/", r"\\\\", "source_identity_key", "v47_pdf_doc_sha_", "v47_xlsx_workbook_sha_")
    return sum(1 for pattern in patterns if re.search(pattern, serialized))


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise AssertionError("unexpected v4_7 preofficial registration schema")
    registration = report["preofficial_external_holdout_candidate_manifest_registration"]
    contract_hash = holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
    if report.get("preofficial_external_holdout_candidate_manifest_registration_only") is not True:
        raise AssertionError("preofficial_external_holdout_candidate_manifest_registration_only must remain true")
    if report.get("holdout_candidate_manifest_contract_hash") != contract_hash:
        raise AssertionError("holdout_candidate_manifest_contract_hash must match current contract")
    if registration.get("official_metric_input_rows") != 0:
        raise AssertionError("official_metric_input_rows must remain 0")
    if report.get("registration_gate_passed") is not bool(registration.get("registration_gate_passed")):
        raise AssertionError("registration_gate_passed must match nested registration state")
    if report.get("candidate_manifest_available") is not bool(registration.get("candidate_manifest_available")):
        raise AssertionError("candidate_manifest_available must match nested registration state")
    if report.get("candidate_manifest_available") and int(report.get("candidate_rows_registered") or 0) <= 0:
        raise AssertionError("candidate_rows_registered must be positive when manifest is available")
    if not report.get("candidate_manifest_available") and int(report.get("candidate_rows_registered") or 0) != 0:
        raise AssertionError("candidate_rows_registered must remain 0 when manifest is absent")
    if registration.get("candidate_manifest_input", {}).get("raw_local_path_exposed") is not False:
        raise AssertionError("candidate_manifest_input must not expose raw local paths")
    if registration.get("candidate_manifest_input", {}).get("path_kind") not in {"not_provided", "external_redacted", "repo_relative"}:
        raise AssertionError("candidate_manifest_input path_kind must be bounded")
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
        raise AssertionError("real_holdout_sufficient must remain false in pre-official registration")
    if forbidden_surface_violation_count(report) != 0:
        raise AssertionError("forbidden official, promotion, training, dry-run, or artifact surface opened")
    if raw_source_identity_or_path_leak_count(report) != 0:
        raise AssertionError("raw candidate id, source identity, or local path leaked")


def update_progress_doc(report: Mapping[str, Any]) -> None:
    current_status = clean(report["status"])
    entry = (
        f"- v4_7 pre-official external holdout candidate manifest registration (`{RUN_ID}`) is "
        f"{current_status}. It is a registration/acquisition lane only: optional external `--candidate-manifest` "
        "input is replayed through v4_5_1 intake, v4_5_2 source-identity audit, and v4_6_10 no-write manifest "
        "replay. The lane records aggregate accepted/rejected counts, query-fidelity counts, and a compact "
        "requirements packet while keeping `official_metric=false`, `official_metric_input_rows=0`, "
        "`v4_7_official_metric_gate_opened=false`, `promotion_evidence=false`, "
        "`product_success_evidence_allowed=false`, and `live_db_index_cache_readiness=false`. It does not run "
        "FT-A, export datasets, write checkpoints, mutate gold/qrels/denominators, or claim product/live readiness."
    )
    v4610.v469.v467.replace_marked_entry(PROGRESS_DOC, RUN_ID, entry)
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{current_status}`;",
        text,
        count=1,
    )
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    query_counts = report["real_query_fidelity_included_counts"]
    entry = f"""### v4_7 Preofficial External Holdout Candidate Manifest Registration

- Run: `{RUN_ID}`
- v4 name: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Primary artifact: `{report["artifact_paths"]["report_json"]}`
- Source evidence: v4_5_1/v4_5_2/v4_6_10-compatible candidate manifest contract, v4_5_3 prior identity hash baseline, and optional external candidate manifest input. This is pre-official registration evidence only.
- Interpretation: accepted counts here are candidate registration counters, not official metric rows, not promotion evidence, not product success evidence, and not FT-A execution.

| Counter | Value |
|---|---:|
| preofficial_external_holdout_candidate_manifest_registration_only | true |
| registration_gate_passed | {str(metrics["registration_gate_passed"]).lower()} |
| candidate_manifest_available | {str(metrics["candidate_manifest_available"]).lower()} |
| candidate_rows_registered | {metrics["candidate_rows_registered"]} |
| accepted_pdf_holdout_candidates | {metrics["accepted_pdf_holdout_candidates"]}/20 |
| accepted_xlsx_holdout_candidates | {metrics["accepted_xlsx_holdout_candidates"]}/8 |
| real_query_fidelity_included_rows_per_family | {query_counts["PDF"]}/100 PDF, {query_counts["XLSX"]}/100 XLSX |
| rejected_candidate_count | {metrics["rejected_candidate_count"]} |
| source_identity_collision_count | {metrics["source_identity_collision_count"]} |
| preofficial_candidate_thresholds_met | {str(metrics["preofficial_candidate_thresholds_met"]).lower()} |
| real_holdout_sufficient | false |
| official_metric_input_rows | 0 |
| v4_7_official_metric_gate_opened | false |
| product_success_evidence_allowed | false |
| promotion_evidence | false |
| live_db_index_cache_readiness | false |

Artifact policy: single ignored `report.json`; no candidate manifest sidecar, validation JSONL, source-identity audit JSONL, dry-run input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, official metric results, or per-run Markdown is created. Raw candidate rows, raw source identities, and raw local paths are not embedded.
"""
    v4610.v469.v467.replace_marked_entry(MEASUREMENTS_DOC, RUN_ID, entry)


def update_triage_doc(report: Mapping[str, Any]) -> None:
    entry = f"""### v4_7 Preofficial External Holdout Candidate Manifest Registration Triage

- Run: `{RUN_ID}`
- Primary artifact: `{report["artifact_paths"]["report_json"]}`; single-report contract remains active.
- This opens only the v4_7 pre-official external holdout candidate manifest acquisition/registration lane.
- Candidate rows are accepted only if v4_5_1/v4_5_2-compatible validation accepts them, PDF identity is document-level, XLSX identity is workbook-level, prior SourceAtom identity collisions are excluded, leakage buckets are empty, protected oracle fields are absent, and query-fidelity included rows meet the registration target.
- It is not official metric, not FT-A dry-run execution, not fine-tuning, not dataset export, not promotion evidence, not product-success evidence, not production routing, and not live DB/index/cache readiness.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `v4_7_official_metric_gate_opened=false`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, and `live_db_index_cache_readiness=false`.
- User-owned gold/qrels, official denominator, expected-answer evidence, and promotion policy gates remain closed before any official metric or promotion lane.
"""
    v4610.v469.v467.replace_marked_entry(TRIAGE_DOC, RUN_ID, entry)


def update_readme(report: Mapping[str, Any]) -> None:
    current_status = clean(report["status"])
    text = README.read_text(encoding="utf-8")
    text = re.sub(
        r"Current RAG status: `[^`]+`\.",
        f"Current RAG status: `{current_status}`.",
        text,
        count=1,
    )
    text = text.replace(
        "v4_7 remains closed because no external candidate manifest is registered, real source-disjoint holdout is insufficient, and user-owned gold/qrels/official denominator/promotion gates remain closed.",
        "v4_7 is open only as a pre-official external holdout candidate manifest registration lane; official metric, FT-A execution, fine-tuning, product success, promotion, production routing, and live DB/index/cache readiness remain closed.",
    )
    verify_start = text.index("## How To Verify Locally")
    verify_end = text.index("## Repo Map")
    verify_section = text[verify_start:verify_end]
    script = "ai\\scripts\\rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py"
    compile_cmd = f"python -X utf8 -m py_compile {script}"
    check_cmd = f"python -X utf8 {script} --check"
    if compile_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod.py\n",
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod.py\n"
            f"{compile_cmd}\n",
            1,
        )
    if check_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 ai\\scripts\\rag_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod.py --check\n",
            "python -X utf8 ai\\scripts\\rag_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod.py --check\n"
            f"{check_cmd}\n",
            1,
        )
    README.write_text(text[:verify_start] + verify_section + text[verify_end:], encoding="utf-8")


def update_eval_readme(report: Mapping[str, Any]) -> None:
    current_status = clean(report["status"])
    text = EVAL_README.read_text(encoding="utf-8")
    text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{current_status}`",
        text,
        count=1,
    )
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod.py` | "
        "Registers or validates optional external PDF/XLSX holdout candidate manifests as pre-official input only. "
        "It reuses v4_5_1 intake, v4_5_2 source-identity audit, and v4_6_10 no-write replay, records only aggregate "
        "counts plus a compact requirements packet, and keeps official metrics, FT-A execution, fine-tuning, "
        "promotion, product-success evidence, and live readiness closed. |"
    )
    pattern = r"\n?\| `rag_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod\.py` \| .*?\|"
    text = re.sub(pattern, "", text)
    text = text.replace(
        "\n\nv4 scripts remain diagnostic/non-production",
        f"\n{row}\n\nv4 scripts remain diagnostic/non-production",
        1,
    )
    scripts_readme.write_text(text, encoding="utf-8")


def update_human_docs(report: Mapping[str, Any]) -> None:
    update_readme(report)
    update_eval_readme(report)
    update_scripts_readme()
    update_progress_doc(report)
    update_measurements_doc(report)
    update_triage_doc(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--candidate-manifest",
        type=Path,
        default=None,
        help="Optional external holdout candidate manifest JSONL for pre-official input-only registration.",
    )
    parser.add_argument(
        "--prior-identity-summary-report",
        type=Path,
        default=None,
        help="Optional external prior identity summary report; defaults to the v4_5_3 hash-only report.",
    )
    args = parser.parse_args(argv)
    artifacts = build_artifacts(
        candidate_manifest_path=args.candidate_manifest,
        prior_identity_summary_report_path=args.prior_identity_summary_report,
    )
    check_report(artifacts["report"])
    if args.check:
        report = artifacts["report"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": report["status"],
                    "preofficial_external_holdout_candidate_manifest_registration_only": True,
                    "registration_gate_passed": report["registration_gate_passed"],
                    "candidate_manifest_available": report["candidate_manifest_available"],
                    "candidate_rows_registered": report["candidate_rows_registered"],
                    "accepted_pdf_holdout_candidates": report["accepted_pdf_holdout_candidates"],
                    "accepted_xlsx_holdout_candidates": report["accepted_xlsx_holdout_candidates"],
                    "rejected_candidate_count": report["rejected_candidate_count"],
                    "official_metric_input_rows": 0,
                    "v4_7_official_metric_gate_opened": False,
                    "promotion_evidence": False,
                    "product_success_evidence_allowed": False,
                    "live_db_index_cache_readiness": False,
                },
                sort_keys=True,
            )
        )
        return 0
    report = write_artifacts(artifacts)
    update_status(report)
    update_human_docs(report)
    print(json.dumps({"run_id": RUN_ID, "status": report["status"], "report": repo_relative(REPORT_JSON)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
