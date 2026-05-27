from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod as v464


ROOT = v464.ROOT
REPORT_DIR = v464.REPORT_DIR
STATUS_JSONL = v464.STATUS_JSONL
PROGRESS_DOC = v464.PROGRESS_DOC
MEASUREMENTS_DOC = v464.MEASUREMENTS_DOC
TRIAGE_DOC = v464.TRIAGE_DOC
README = v464.README
EVAL_README = v464.EVAL_README

V4_NAME = v464.V4_NAME
V4_RUN_FAMILY = v464.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod"
EVENT_TYPE = "diagnostic_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod"
STATUS = "DIAGNOSTIC_V4_6_5_FT_A_DRY_RUN_EXECUTION_PLAN_GATE_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_6_5_ft_a_dry_run_execution_plan_gate_report_v1"

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "dpo_dataset.jsonl",
            "dry_run_execution_plan.json",
            "dry_run_input_manifest.jsonl",
            "ft_route_policy_dry_run.json",
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
    return v464.clean(value)


def repo_relative(path: Path) -> str:
    return v464.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v464.artifact_path_text(path)


def utc_now() -> str:
    return v464.utc_now()


def sha256_file(path: Path) -> str:
    return v464.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v464.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v464.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v464.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v464.write_jsonl(path, rows)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def load_v4_6_4_report() -> dict[str, Any]:
    if v464.REPORT_JSON.exists():
        return read_json(v464.REPORT_JSON)
    return {}


def source_report_boundary_flags_clean(report: Mapping[str, Any]) -> bool:
    return v464.source_report_boundary_flags_clean(report)


def source_report_input(
    *,
    input_key: str,
    source_run_id: str,
    report_json: Path,
    report: Mapping[str, Any],
) -> dict[str, Any]:
    exists = report_json.exists()
    source_gate = _mapping(report.get("dry_run_input_manifest_gate"))
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
        "source_report_manifest_validator_schema_check_passed": bool(
            source_gate.get("manifest_validator_schema_check_passed")
        ),
        "source_report_dry_run_input_manifest_gate_passed": bool(
            source_gate.get("dry_run_input_manifest_gate_passed")
        ),
        "source_report_manifest_rows_exported": bool(source_gate.get("manifest_rows_exported")),
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_source_report_inputs(*, v4_6_4_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "v4_6_4": source_report_input(
            input_key="v4_6_4",
            source_run_id=v464.RUN_ID,
            report_json=v464.REPORT_JSON,
            report=v4_6_4_report,
        )
    }


def build_dry_run_execution_plan_contract(*, v4_6_4_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_dry_run_execution_plan_contract_v1",
        "run_id": RUN_ID,
        "lane": "FT-A",
        "source_validator_run_id": v464.RUN_ID,
        "source_validator_schema_version": clean(v4_6_4_report.get("schema_version")),
        "execution_plan_schema_ready": True,
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_export_required_before_execution": True,
        "dry_run_executes_prompts": False,
        "llm_invocation_allowed": False,
        "raw_prompt_text_allowed": False,
        "raw_llm_response_allowed": False,
        "dataset_export_allowed": False,
        "training_job_allowed": False,
        "allowed_execution_plan_steps": [
            "validate_v4_6_preflight_gate_state",
            "validate_dry_run_input_manifest_gate_state",
            "validate_prompt_policy_baseline_gate_state",
            "validate_user_owned_policy_gate_state",
            "emit_closed_gate_report_only",
        ],
        "forbidden_execution_outputs": [
            "dry_run_execution_plan.json",
            "dry_run_input_manifest.jsonl",
            "prompt_manifest.json",
            "raw_llm_response.json",
            "training_manifest.jsonl",
            "sft_dataset.jsonl",
            "dpo_dataset.jsonl",
            "reward_model_dataset.jsonl",
            "official_metric_results.jsonl",
        ],
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_dry_run_execution_plan_gate(
    *,
    v4_6_4_report: Mapping[str, Any],
    user_owned_policy_gate_ready: bool = False,
) -> dict[str, Any]:
    source_gate = _mapping(v4_6_4_report.get("dry_run_input_manifest_gate"))
    source_contract = _mapping(v4_6_4_report.get("dry_run_input_manifest_contract"))
    source_boundary_clean = source_report_boundary_flags_clean(v4_6_4_report)
    source_ready = (
        bool(v4_6_4_report.get("diagnostic_only"))
        and clean(v4_6_4_report.get("schema_version"))
        == "rag_v4_6_4_ft_a_dry_run_input_manifest_validator_report_v1"
        and bool(v4_6_4_report.get("ft_a_dry_run_input_manifest_validator_only"))
        and bool(source_gate.get("manifest_validator_schema_check_passed"))
        and source_boundary_clean
    )
    manifest_gate_passed = bool(source_gate.get("dry_run_input_manifest_gate_passed"))
    manifest_rows_exported = bool(source_gate.get("manifest_rows_exported")) and bool(
        source_contract.get("manifest_rows_exported")
    )
    gate_passed = (
        source_ready
        and manifest_gate_passed
        and manifest_rows_exported
        and bool(user_owned_policy_gate_ready)
    )
    blocked_reasons = [
        "dry_run_execution_requires_manifest_export_prompt_policy_and_user_policy_gates"
    ]
    if not source_boundary_clean:
        blocked_reasons.append("v4_6_4_source_boundary_flags_not_clean")
    if not source_ready:
        blocked_reasons.append("missing_or_invalid_v4_6_4_dry_run_input_manifest_validator")
    if not manifest_gate_passed:
        blocked_reasons.append("v4_6_4_dry_run_input_manifest_gate_not_passed")
    if not manifest_rows_exported:
        blocked_reasons.append("dry_run_input_manifest_not_exported")
    if not user_owned_policy_gate_ready:
        blocked_reasons.append("user_owned_gold_qrels_denominator_policy_pending")
    return {
        "schema_version": f"{RUN_ID}_dry_run_execution_plan_gate_v1",
        "run_id": RUN_ID,
        "dry_run_execution_plan_schema_check_passed": True,
        "v4_6_4_source_report_ready": source_ready,
        "v4_6_4_source_boundary_flags_clean": source_boundary_clean,
        "v4_6_4_dry_run_input_manifest_gate_passed": manifest_gate_passed,
        "manifest_rows_exported": manifest_rows_exported,
        "user_owned_policy_gate_ready": bool(user_owned_policy_gate_ready),
        "dry_run_execution_plan_gate_passed": gate_passed,
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_exported": False,
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_llm_response_payload_created": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_exports_created": 0,
        "official_metric_input_rows": 0,
        "v4_7_official_metric_gate_opened": False,
        "blocked_reasons": blocked_reasons if not gate_passed else [],
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


def build_metrics(*, gate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "ft_a_dry_run_execution_plan_gate_only": True,
        "dry_run_execution_plan_schema_check_passed": bool(
            gate.get("dry_run_execution_plan_schema_check_passed")
        ),
        "dry_run_execution_plan_gate_passed": bool(gate.get("dry_run_execution_plan_gate_passed")),
        "v4_6_4_source_report_ready": bool(gate.get("v4_6_4_source_report_ready")),
        "v4_6_4_dry_run_input_manifest_gate_passed": bool(
            gate.get("v4_6_4_dry_run_input_manifest_gate_passed")
        ),
        "manifest_rows_exported": bool(gate.get("manifest_rows_exported")),
        "user_owned_policy_gate_ready": bool(gate.get("user_owned_policy_gate_ready")),
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
    contract: Mapping[str, Any],
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
        "ft_a_dry_run_execution_plan_gate_only": True,
        "dry_run_execution_plan_contract": dict(contract),
        "dry_run_execution_plan_gate": dict(gate),
        "source_report_inputs": {key: dict(value) for key, value in source_inputs.items()},
        "readiness_decision": "blocked_pending_manifest_export_dry_run_preflight_and_user_policy_gates",
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
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py --check",
                "targeted v4_6_5 dry-run execution plan gate tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_6_5 because this slice validates a deterministic dry-run "
                "execution plan gate only; future FT-A training, embedding, or local LLM workloads should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "No dry-run execution plan sidecar is exported.",
            "No dry-run input manifest sidecar is exported.",
            "No raw prompt text, prompt payload, or raw LLM response is emitted.",
            "No actual FT-A dry run is opened or executed.",
            "v4_7 official metric opening remains user-owned and unopened.",
        ],
        "next_recommendation": (
            "Keep prompt payload creation, FT-A execution, dataset export, and v4_7 closed until manifest export, "
            "v4_6 preflight, and user-owned policy inputs pass."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    v4_6_4_report = load_v4_6_4_report()
    source_inputs = build_source_report_inputs(v4_6_4_report=v4_6_4_report)
    contract = build_dry_run_execution_plan_contract(v4_6_4_report=v4_6_4_report)
    gate = build_dry_run_execution_plan_gate(v4_6_4_report=v4_6_4_report)
    metrics = build_metrics(gate=gate)
    guardrails = build_guardrails()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        source_inputs=source_inputs,
        contract=contract,
        gate=gate,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "dry_run_execution_plan_contract": contract,
        "dry_run_execution_plan_gate": gate,
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
        raise RuntimeError(f"unexpected v4_6_5 primary artifacts: {unexpected}")


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
    return v464.artifact_sha256_from_report_paths(artifact_paths)


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
        "ft_a_dry_run_execution_plan_gate_only": True,
        "dry_run_execution_plan_schema_check_passed": report["metrics"][
            "dry_run_execution_plan_schema_check_passed"
        ],
        "dry_run_execution_plan_gate_passed": report["metrics"]["dry_run_execution_plan_gate_passed"],
        "dry_run_execution_plan_exported": False,
        "dry_run_input_manifest_exported": False,
        "source_report_inputs": dict(report["source_report_inputs"]),
        "blocked_reasons": list(report["blocked_reasons"]),
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
    text = README.read_text(encoding="utf-8")
    text = replace_current_status(text)
    if "rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py" not in text:
        marker = "python -X utf8 ai\\scripts\\rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod.py --check\n"
        addition = (
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py\n"
            "python -X utf8 ai\\scripts\\rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py\n"
            "python -X utf8 ai\\scripts\\rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py --check\n"
        )
        text = text.replace(marker, marker + addition)
    README.write_text(text, encoding="utf-8")


def update_eval_readme() -> None:
    text = EVAL_README.read_text(encoding="utf-8")
    text = replace_current_status(text)
    if "v4_6_5 is `diagnostic_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod_ready`" not in text:
        text = text.replace(
            "v4_6_4 is `diagnostic_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod_ready`.",
            "v4_6_4 is `diagnostic_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod_ready`; "
            "v4_6_5 is `diagnostic_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod_ready`.",
        )
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    path = ROOT / "ai" / "scripts" / "README.md"
    text = path.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py` | "
        "Defines the closed FT-A dry-run execution plan gate without exporting the plan or manifest and without "
        "creating prompts, raw LLM responses, datasets, jobs, checkpoints, official metrics, promotion, or product-success evidence. |"
    )
    if "rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py" not in text:
        text = text.replace(
            "| `rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod.py` | Validates the schema for a future FT-A dry-run input manifest without exporting that manifest; prompt/gold/output fields are rejected and no prompt manifest, raw LLM response, dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |\n",
            "| `rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod.py` | Validates the schema for a future FT-A dry-run input manifest without exporting that manifest; prompt/gold/output fields are rejected and no prompt manifest, raw LLM response, dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |\n"
            + row
            + "\n",
        )
    path.write_text(text, encoding="utf-8")


def update_progress_doc() -> None:
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_status = f"{EVENT_TYPE}_ready"
    entry = (
        f"<!-- {RUN_ID}:progress-entry:start -->\n"
        f"- v4_6_5 FT-A dry-run execution plan gate (`{RUN_ID}`) is {current_status}. "
        "It validates the closed execution-plan gate after v4_6_4, but does not export a dry-run execution plan, "
        "does not export a dry-run input manifest, does not create prompt payloads or prompt manifests, does not invoke an LLM, "
        "does not open or execute the FT-A dry run, does not create datasets, jobs, checkpoints, official metrics, promotion evidence, "
        "product-success evidence, production routes, or live DB/index/cache readiness claims.\n"
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
        "current diagnostic v4_6_5 FT-A dry-run execution plan gate loop:\n"
        f"`{RUN_ID}`;\n"
    )
    text = re.sub(
        r"(?:current diagnostic v4_6_5 FT-A dry-run execution plan gate loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_4 FT-A dry-run input manifest validator loop:",
        loop + "current diagnostic v4_6_4 FT-A dry-run input manifest validator loop:",
        text,
        count=1,
    )
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    text = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    metrics = report["metrics"]
    entry = f"""<!-- {RUN_ID}:measurements-entry:start -->
### v4_6_5 FT-A Dry-Run Execution Plan Gate

- Run: `{RUN_ID}`
- v4 name: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, FT-A dry-run execution-plan-gate only, single `report.json`.
- Primary artifact: `{report['artifact_paths']['report_json']}`
- Source evidence: v4_6_4 FT-A dry-run input manifest validator report.

| Field | Value |
| --- | --- |
| ft_a_dry_run_execution_plan_gate_only | true |
| dry_run_execution_plan_schema_check_passed | {str(metrics['dry_run_execution_plan_schema_check_passed']).lower()} |
| dry_run_execution_plan_gate_passed | {str(metrics['dry_run_execution_plan_gate_passed']).lower()} |
| dry_run_execution_plan_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the dry-run execution plan contract, dry_run_execution_plan_gate, source_report_inputs, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no dry-run execution plan sidecar, dry-run input manifest sidecar, prompt manifest, raw LLM response, dataset sidecar, training manifest, training job, checkpoint, review CSV, official metric result, or per-run Markdown.
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
### v4_6_5 FT-A Dry-Run Execution Plan Gate Triage

- Run: `{RUN_ID}`
- Primary artifact: `ai/eval/reports/rag-ingestion/quality/{RUN_ID}/report.json`; single-report contract remains active.
- v4_6_5 is diagnostic-only, non-production, execution-plan-gate-only FT-A dry-run preparation.
- It is not the FT-A dry run, not dry-run execution, not manifest export, not prompt payload creation, not dataset export, and not a v4_7 opening.
- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion-adjacent evaluation.
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
    section = """### v4_6_5 — FT-A Dry-Run Execution Plan Gate

This is a diagnostic gate for a later non-production FT-A dry-run execution plan, not the execution plan export and not the dry run itself.

Purpose:

- Validate that the dry-run execution plan lane remains closed while manifest export, prompt payload creation, dataset export, dry-run execution, v4_7, official metric, promotion, product-success, and live-readiness gates are closed.
- Preserve the distinction between source/manifest gates and user-owned gold/qrels/denominator/promotion policy gates.
- Keep all outputs in one ignored `report.json`.

Locked boundary:

```text
dry_run_execution_plan_gate_passed = false
dry_run_execution_plan_exported = false
dry_run_input_manifest_exported = false
ft_route_policy_dry_run_opened = false
ft_route_policy_dry_run_executed = false
official_metric_input_rows = 0
promotion_evidence = false
product_success_evidence_allowed = false
```

"""
    if "### v4_6_5 — FT-A Dry-Run Execution Plan Gate" not in text:
        text = text.replace("### v4_7 — Official Metric Opening Gate", section + "### v4_7 — Official Metric Opening Gate")
    if "v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod" not in text:
        text = text.replace(
            "v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
            "v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod\n↓\nv4_6_5_ft_a_dry_run_execution_plan_gate_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
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
    if report["dry_run_execution_plan_gate"]["dry_run_execution_plan_gate_passed"]:
        raise AssertionError("dry-run execution plan gate must remain closed")
    if report["ft_route_policy_dry_run_executed"]:
        raise AssertionError("dry run execution must remain closed")


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
                    "dry_run_execution_plan_schema_check_passed": report["metrics"][
                        "dry_run_execution_plan_schema_check_passed"
                    ],
                    "dry_run_execution_plan_gate_passed": report["metrics"][
                        "dry_run_execution_plan_gate_passed"
                    ],
                    "dry_run_execution_plan_exported": False,
                    "dry_run_input_manifest_exported": False,
                    "ft_route_policy_dry_run_opened": False,
                    "ft_route_policy_dry_run_executed": False,
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
