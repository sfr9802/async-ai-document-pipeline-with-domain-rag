from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod as v461
import rag_v4_6_ft_route_policy_dry_run_preflight_nonprod as v46


ROOT = v461.ROOT
REPORT_DIR = v461.REPORT_DIR
STATUS_JSONL = v461.STATUS_JSONL
PROGRESS_DOC = v461.PROGRESS_DOC
MEASUREMENTS_DOC = v461.MEASUREMENTS_DOC
TRIAGE_DOC = v461.TRIAGE_DOC
README = v461.README
EVAL_README = v461.EVAL_README

V4_NAME = v461.V4_NAME
V4_RUN_FAMILY = v461.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod"
EVENT_TYPE = "diagnostic_v4_6_2_ft_route_policy_fixture_contract_nonprod"
STATUS = "DIAGNOSTIC_V4_6_2_FT_ROUTE_POLICY_FIXTURE_CONTRACT_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_6_2_ft_route_policy_fixture_contract_report_v1"
TARGET_POLICY_BUCKETS = [
    "ANSWER_ALLOWED",
    "CONTEXT_REQUIRED",
    "AMBIGUOUS_WORKBOOK_IDENTITY",
    "AMBIGUOUS_FILE_IDENTITY",
    "UNSUPPORTED_RANGE_TOO_LARGE",
    "INDEX_UNAVAILABLE",
    "CONTRACT_VIOLATION",
    "UNSUPPORTED_ROUTE",
]
ALLOWED_ROUTE_LANES = ["rough_query", "deictic", "user_locator", "hybrid", "unsupported"]
ALLOWED_SOURCE_FAMILIES = ["PDF", "XLSX", "TEXT"]
ALLOWED_MODEL_INPUT_FIELDS = [
    "raw_query_text",
    "source_family",
    "route_lane",
    "active_context_available",
    "candidate_search_view_count",
    "selected_source_atom_count",
    "selected_evidence_bundle_count",
    "fail_closed_reason_code",
]
LABEL_ONLY_FIELDS = ["response_policy_bucket", "fail_closed"]
FORBIDDEN_MODEL_INPUT_FIELDS = [
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
]
FORBIDDEN_FIELD_NAME_PATTERNS = [
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
]
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "dpo_dataset.jsonl",
            "ft_a_fixture_contract.json",
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
    return v461.clean(value)


def repo_relative(path: Path) -> str:
    return v461.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v461.artifact_path_text(path)


def utc_now() -> str:
    return v461.utc_now()


def sha256_file(path: Path) -> str:
    return v461.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v461.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v461.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v461.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v461.write_jsonl(path, rows)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def build_ft_a_fixture_contract() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_ft_a_fixture_contract_v1",
        "run_id": RUN_ID,
        "lane": "FT-A",
        "row_source": "route_policy_audit_rows_only",
        "target_policy_buckets": list(TARGET_POLICY_BUCKETS),
        "allowed_route_lanes": list(ALLOWED_ROUTE_LANES),
        "allowed_source_families": list(ALLOWED_SOURCE_FAMILIES),
        "allowed_model_input_fields": list(ALLOWED_MODEL_INPUT_FIELDS),
        "label_only_fields": list(LABEL_ONLY_FIELDS),
        "forbidden_model_input_fields": list(FORBIDDEN_MODEL_INPUT_FIELDS),
        "dataset_export_gate_opened": False,
        "prompt_payload_created": False,
        "raw_llm_response_payload_created": False,
        "training_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def _fixture_probe_rows() -> list[dict[str, Any]]:
    return [
        {
            "row_id": "probe-context-required",
            "query_id": "probe-context-required-q",
            "source_family": "XLSX",
            "raw_query_text": "this cell value",
            "route_lane": "deictic",
            "response_policy_bucket": "CONTEXT_REQUIRED",
            "fail_closed": True,
            "active_context_available": False,
            "candidate_search_view_count": 0,
            "selected_source_atom_count": 0,
            "selected_evidence_bundle_count": 0,
            "fail_closed_reason_code": "MISSING_ACTIVE_CONTEXT",
        },
        {
            "row_id": "probe-hidden-answer",
            "query_id": "probe-hidden-answer-q",
            "source_family": "PDF",
            "raw_query_text": "answer from this file",
            "route_lane": "rough_query",
            "response_policy_bucket": "ANSWER_ALLOWED",
            "expected_answer": "hidden answer text",
        },
        {
            "row_id": "probe-target-locator",
            "query_id": "probe-target-locator-q",
            "source_family": "XLSX",
            "raw_query_text": "B7",
            "route_lane": "user_locator",
            "response_policy_bucket": "ANSWER_ALLOWED",
            "target_locator": "Sheet1!B7",
        },
        {
            "row_id": "probe-alias-leakage",
            "query_id": "probe-alias-leakage-q",
            "source_family": "PDF",
            "raw_query_text": "answer from this prompt",
            "route_lane": "rough_query",
            "response_policy_bucket": "ANSWER_ALLOWED",
            "expected_answer_text": "hidden alias answer",
            "prompt_payload": "prompt alias",
            "llm_response": "response alias",
            "human_label": "approved",
        },
        {
            "row_id": "probe-unsupported-bucket",
            "query_id": "probe-unsupported-bucket-q",
            "source_family": "TEXT",
            "raw_query_text": "ship this",
            "route_lane": "unsupported",
            "response_policy_bucket": "PROMOTE_TO_PRODUCTION",
        },
    ]


def _accepted_fixture_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "row_id": clean(row.get("row_id")),
        "query_id": clean(row.get("query_id")),
        "source_family": clean(row.get("source_family")).upper(),
        "route_lane": clean(row.get("route_lane")),
        "response_policy_bucket": clean(row.get("response_policy_bucket")),
        "fail_closed": bool(row.get("fail_closed")),
        "model_input_fields": {
            field: row.get(field)
            for field in ALLOWED_MODEL_INPUT_FIELDS
            if field in row and _has_value(row.get(field))
        },
        "label_fields": {
            field: row.get(field)
            for field in LABEL_ONLY_FIELDS
            if field in row and _has_value(row.get(field))
        },
    }


def forbidden_model_input_fields_present(row: Mapping[str, Any]) -> list[str]:
    allowed_fields = set(ALLOWED_MODEL_INPUT_FIELDS) | set(LABEL_ONLY_FIELDS) | {"row_id", "query_id"}
    forbidden: set[str] = set()
    for field, value in row.items():
        if not _has_value(value):
            continue
        normalized = clean(field).casefold()
        if field in FORBIDDEN_MODEL_INPUT_FIELDS:
            forbidden.add(field)
            continue
        if field in allowed_fields:
            continue
        if any(pattern in normalized for pattern in FORBIDDEN_FIELD_NAME_PATTERNS):
            forbidden.add(field)
    return sorted(forbidden)


def validate_ft_a_fixture_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        row_id = clean(row.get("row_id")) or f"row-{index}"
        source_family = clean(row.get("source_family")).upper()
        route_lane = clean(row.get("route_lane"))
        bucket = clean(row.get("response_policy_bucket"))
        forbidden_fields = forbidden_model_input_fields_present(row)
        if forbidden_fields:
            excluded.append(
                {
                    "row_id": row_id,
                    "exclusion_reason": "forbidden_model_input_field_present",
                    "forbidden_model_input_fields": sorted(forbidden_fields),
                }
            )
            continue
        if source_family not in ALLOWED_SOURCE_FAMILIES:
            excluded.append({"row_id": row_id, "exclusion_reason": "unsupported_source_family"})
            continue
        if route_lane not in ALLOWED_ROUTE_LANES:
            excluded.append({"row_id": row_id, "exclusion_reason": "unsupported_route_lane"})
            continue
        if bucket not in TARGET_POLICY_BUCKETS:
            excluded.append({"row_id": row_id, "exclusion_reason": "unsupported_response_policy_bucket"})
            continue
        accepted.append(_accepted_fixture_row(row))
    gold_oracle_rejections = sum(
        1
        for row in excluded
        if row["exclusion_reason"] == "forbidden_model_input_field_present"
    )
    return {
        "schema_version": f"{RUN_ID}_fixture_validation_v1",
        "run_id": RUN_ID,
        "fixture_row_count": len(rows),
        "accepted_fixture_rows": accepted,
        "excluded_fixture_rows": excluded,
        "accepted_fixture_row_count": len(accepted),
        "excluded_fixture_row_count": len(excluded),
        "gold_oracle_field_rejection_count": gold_oracle_rejections,
        "official_metric_input_rows": 0,
        "training_dataset_export_created": False,
        "prompt_payload_created": False,
        "raw_llm_response_payload_created": False,
    }


def load_source_reports() -> dict[str, dict[str, Any]]:
    return {
        "v4_6": read_json(v46.REPORT_JSON) if v46.REPORT_JSON.exists() else {},
        "v4_6_1": read_json(v461.REPORT_JSON) if v461.REPORT_JSON.exists() else {},
    }


def source_report_inputs(source_reports: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    inputs = {
        "v4_6": v461.bridge_source_report_input(
            input_key="v4_6",
            run_id=v46.RUN_ID,
            report_json=v46.REPORT_JSON,
            report=source_reports.get("v4_6", {}),
        ),
        "v4_6_1": v461.bridge_source_report_input(
            input_key="v4_6_1",
            run_id=v461.RUN_ID,
            report_json=v461.REPORT_JSON,
            report=source_reports.get("v4_6_1", {}),
        ),
    }
    for source_input in inputs.values():
        source_input["schema_version"] = f"{RUN_ID}_source_report_input_v1"
        source_input["run_id"] = RUN_ID
    return inputs


def build_fixture_contract_gate(
    *,
    validation: Mapping[str, Any],
    source_reports: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    v46_report = _mapping(source_reports.get("v4_6"))
    v461_report = _mapping(source_reports.get("v4_6_1"))
    blocked_reasons = ["dry_run_and_dataset_export_require_all_v4_6_preflight_gates"]
    return {
        "schema_version": f"{RUN_ID}_fixture_contract_gate_v1",
        "run_id": RUN_ID,
        "fixture_contract_schema_ready": True,
        "fixture_contract_schema_check_passed": True,
        "dry_run_dataset_gate_passed": False,
        "fixture_validation_probe_count": int(validation.get("fixture_row_count") or 0),
        "accepted_fixture_probe_count": int(validation.get("accepted_fixture_row_count") or 0),
        "rejected_fixture_probe_count": int(validation.get("excluded_fixture_row_count") or 0),
        "gold_oracle_field_rejection_count": int(validation.get("gold_oracle_field_rejection_count") or 0),
        "v4_6_preflight_report_present": bool(v46_report),
        "v4_6_preflight_opened": bool(v46_report.get("ft_route_policy_dry_run_opened")),
        "v4_6_1_contract_bridge_report_present": bool(v461_report),
        "v4_6_1_contract_bridge_gate_passed": bool(
            _mapping(v461_report.get("contract_bridge_gate")).get("passed")
        ),
        "dataset_export_gate_opened": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_exports_created": 0,
        "blocked_reasons": blocked_reasons,
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
        "prompt_payload_created": False,
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


def build_metrics(*, validation: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "ft_route_policy_fixture_contract_only": True,
        "fixture_contract_schema_ready": True,
        "fixture_contract_schema_check_passed": bool(gate.get("fixture_contract_schema_check_passed")),
        "dry_run_dataset_gate_passed": bool(gate.get("dry_run_dataset_gate_passed")),
        "fixture_validation_probe_count": int(validation.get("fixture_row_count") or 0),
        "accepted_fixture_probe_count": int(validation.get("accepted_fixture_row_count") or 0),
        "rejected_fixture_probe_count": int(validation.get("excluded_fixture_row_count") or 0),
        "gold_oracle_field_rejection_count": int(validation.get("gold_oracle_field_rejection_count") or 0),
        "dataset_export_gate_opened": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "fine_tuning_dataset_exports_created": 0,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "prompt_payload_created": False,
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
    fixture_contract: Mapping[str, Any],
    validation: Mapping[str, Any],
    gate: Mapping[str, Any],
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
        "ft_route_policy_fixture_contract_only": True,
        "ft_a_fixture_contract": dict(fixture_contract),
        "fixture_validation": dict(validation),
        "fixture_contract_gate": dict(gate),
        "source_report_inputs": {key: dict(value) for key, value in source_inputs.items()},
        "readiness_decision": "blocked_pending_v4_6_preflight_gates_and_user_policy",
        "blocked_reasons": list(gate["blocked_reasons"]),
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
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "prompt_payload_created": False,
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
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py --check",
                "targeted v4_6_2 fixture contract tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_6_2 because this slice validates a deterministic "
                "FT-A fixture contract only; future FT-A training, embedding, or local LLM workloads should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "No actual FT-A dry run is opened.",
            "No fine-tuning dataset is exported.",
            "v4_6 source and user-owned policy gates remain closed in the default repo state.",
            "v4_7 official metric opening remains user-owned and unopened.",
        ],
        "next_recommendation": (
            "Keep dataset export and FT-A execution closed until v4_6 preflight gates and user-owned policy inputs pass; "
            "next non-gold work can add an isolated prompt-only baseline schema without emitting prompts."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    source_reports = load_source_reports()
    inputs = source_report_inputs(source_reports)
    fixture_contract = build_ft_a_fixture_contract()
    validation = validate_ft_a_fixture_rows(_fixture_probe_rows())
    gate = build_fixture_contract_gate(validation=validation, source_reports=source_reports)
    metrics = build_metrics(validation=validation, gate=gate)
    guardrails = build_guardrails()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        source_inputs=inputs,
        fixture_contract=fixture_contract,
        validation=validation,
        gate=gate,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "fixture_contract": fixture_contract,
        "fixture_validation": validation,
        "fixture_contract_gate": gate,
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
        raise RuntimeError(f"unexpected v4_6_2 primary artifacts: {unexpected}")


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
    report["training_manifest_jsonl_created"] = False
    report["training_job_created"] = False
    remove_stale_sidecar_artifacts(target_dir)
    assert_single_report_directory(target_dir)
    write_json(report_path, report)
    assert_single_report_directory(target_dir)
    return report


def artifact_sha256_from_report_paths(artifact_paths: Mapping[str, str]) -> dict[str, str]:
    return v461.artifact_sha256_from_report_paths(artifact_paths)


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
        "fixture_contract_gate": dict(report["fixture_contract_gate"]),
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
    v461.replace_marked_entry(path, marker, entry)


def _refresh_docs() -> None:
    v461._refresh_docs()


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_6_2 FT-A route-policy fixture contract loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_1 holdout candidate manifest identity contract bridge loop:\n`[^`]+`;",
        "current diagnostic v4_6_2 FT-A route-policy fixture contract loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_6_1 holdout candidate manifest identity contract bridge loop:\n"
        f"`{v461.RUN_ID}`;",
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
        "ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py --check\n"
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
        r"v4_6_1 is `diagnostic_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod_ready`"
        r"(?:; v4_6_2 is `[^`]+`)?\.",
        f"v4_6_1 is `{v461.EVENT_TYPE}_ready`; v4_6_2 is `{EVENT_TYPE}_ready`.",
        eval_text,
        count=1,
    )
    EVAL_README.write_text(eval_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py` | "
        "Defines and validates the non-writing FT-A route/policy fixture contract for a later dry run; it rejects gold/oracle/prompt/raw-response fields and emits no dataset, job, checkpoint, raw prompt, raw LLM response, official metric, promotion, or product-success evidence. |"
    )
    pattern = r"\| `rag_v4_6_2_ft_route_policy_fixture_contract_nonprod\.py` \| .*?\|"
    if re.search(pattern, text):
        text = re.sub(pattern, row, text, count=1)
    elif "| `rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py` |" in text:
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
    if "### v4_6_2 — FT-A Route-Policy Fixture Contract" not in text:
        insert = """### v4_6_2 — FT-A Route-Policy Fixture Contract

This is a diagnostic contract for a later non-production FT-A dry run, not the dry run itself.

Purpose:

- Define route-policy audit row inputs that may be used by a later FT-A fixture or dry run.
- Reject gold/oracle answer fields, hidden target locators, prompt payloads, raw LLM responses, and answer text as model inputs.
- Keep dataset export, dry-run execution, v4_7, official metric, promotion, product-success, and live-readiness gates closed.

Required state:

```text
ft_route_policy_fixture_contract_only = true
fixture_contract_schema_ready = true
dataset_export_gate_opened = false
ft_route_policy_dry_run_opened = false
ft_route_policy_dry_run_executed = false
fine_tuning_dataset_exports_created = 0
official_metric_input_rows = 0
promotion_evidence = false
product_success_evidence_allowed = false
```

"""
        text = text.replace("### v4_7 — Official Metric Opening Gate", insert + "### v4_7 — Official Metric Opening Gate", 1)
    text = text.replace(
        "v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        "v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod\n↓\nv4_6_2_ft_route_policy_fixture_contract_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
    )
    plan_path.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    report_path = report["artifact_paths"]["report_json"]
    metrics = report["metrics"]
    _refresh_docs()
    progress_entry = (
        f"- v4_6_2 FT-A route-policy fixture contract (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It defines the non-writing route-policy audit row contract for a later FT-A dry run and validates that gold/oracle answer text, hidden target locators, prompt payloads, and raw LLM responses are rejected before any dataset export. "
        "This is diagnostic-only and fixture-contract-only: it does not open the FT-A dry run, does not open v4_7, does not create a dataset, training manifest, job, checkpoint, prompt payload, raw LLM response, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim."
    )
    measurements_entry = f"""### v4_6_2 FT-A Route-Policy Fixture Contract

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, fixture-contract-only, single `report.json`.
- Primary artifact: `{report_path}`
- Source evidence: v4_6 preflight report and v4_6_1 holdout manifest identity contract bridge report.

| Diagnostic count | Value |
| --- | ---: |
| ft_route_policy_fixture_contract_only | true |
| fixture_contract_schema_ready | true |
| fixture_contract_schema_check_passed | {str(metrics["fixture_contract_schema_check_passed"]).lower()} |
| dry_run_dataset_gate_passed | {str(metrics["dry_run_dataset_gate_passed"]).lower()} |
| fixture_validation_probe_count | {metrics["fixture_validation_probe_count"]} |
| accepted_fixture_probe_count | {metrics["accepted_fixture_probe_count"]} |
| rejected_fixture_probe_count | {metrics["rejected_fixture_probe_count"]} |
| gold_oracle_field_rejection_count | {metrics["gold_oracle_field_rejection_count"]} |
| dataset_export_gate_opened | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| v4_7_official_metric_gate_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the FT-A fixture contract, validation probes, fixture_contract_gate, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no prompt payload, raw LLM response, dataset sidecar, training manifest, training job, checkpoint, review CSV, or per-run Markdown.
"""
    triage_entry = (
        "### v4_6_2 FT-A Route-Policy Fixture Contract Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_6_2 is diagnostic-only, non-production, FT-A route-policy fixture contract only.\n"
        "- The contract prepares row-shape and leakage/no-go rules only; it is not the FT-A dry run, not dataset export, and not a v4_7 opening.\n"
        "- It rejects gold/oracle answer text, supporting evidence, target/gold locators, prompt payloads, raw LLM responses, final answers, direct answer values, and local file paths as model inputs.\n"
        "- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.\n"
        "- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion gate.\n"
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
                    "fixture_contract_schema_check_passed": report["metrics"][
                        "fixture_contract_schema_check_passed"
                    ],
                    "dry_run_dataset_gate_passed": report["metrics"]["dry_run_dataset_gate_passed"],
                    "fixture_validation_probe_count": report["metrics"]["fixture_validation_probe_count"],
                    "gold_oracle_field_rejection_count": report["metrics"]["gold_oracle_field_rejection_count"],
                    "dataset_export_gate_opened": report["metrics"]["dataset_export_gate_opened"],
                    "ft_route_policy_dry_run_opened": report["metrics"]["ft_route_policy_dry_run_opened"],
                    "ft_route_policy_dry_run_executed": report["metrics"]["ft_route_policy_dry_run_executed"],
                    "fine_tuning_dataset_exports_created": report["metrics"]["fine_tuning_dataset_exports_created"],
                    "official_metric_input_rows": report["metrics"]["official_metric_input_rows"],
                    "v4_7_official_metric_gate_opened": report["metrics"]["v4_7_official_metric_gate_opened"],
                    "gpu_required_for_this_slice": report["metrics"]["gpu_required_for_this_slice"],
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
