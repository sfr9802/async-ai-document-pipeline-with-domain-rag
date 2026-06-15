from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_5_1_holdout_candidate_intake_gate_nonprod as v451
import rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod as v452
import rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod as v453
import rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod as v466
import rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod as v467


ROOT = v467.ROOT
REPORT_DIR = v467.REPORT_DIR
STATUS_JSONL = v467.STATUS_JSONL
PROGRESS_DOC = v467.PROGRESS_DOC
MEASUREMENTS_DOC = v467.MEASUREMENTS_DOC
TRIAGE_DOC = v467.TRIAGE_DOC
README = v467.README
EVAL_README = v467.EVAL_README

AI_ROOT = ROOT / "ai"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.capabilities.rag.holdout_manifest_contract import (  # noqa: E402
    build_holdout_acquisition_requirements,
    build_holdout_candidate_manifest_contract,
)
from app.capabilities.rag_orchestrator.phase1_diagnostic_runtime import (  # noqa: E402
    HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH,
    RagHoldoutCandidateValidationRequest,
    SourceFirstRagService,
)

V4_NAME = v467.V4_NAME
V4_RUN_FAMILY = v467.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod"
EVENT_TYPE = "diagnostic_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod"
STATUS = "DIAGNOSTIC_V4_6_8_RUNTIME_READINESS_DEPENDENCY_FRESHNESS_GATE_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_6_8_runtime_readiness_dependency_freshness_gate_report_v1"

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "candidate_manifest.jsonl",
            "candidate_validation.jsonl",
            "dependency_freshness_gate.json",
            "dry_run_execution_plan.json",
            "dry_run_input_manifest.jsonl",
            "holdout_acquisition_requirements.json",
            "metrics.json",
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


def clean(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return "__external_path_redacted__"


def utc_now() -> str:
    return v467.utc_now()


def sha256_file(path: Path) -> str:
    return v467.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return dict(model.model_dump())
    return dict(model.dict())


def _load_report(path: Path, fallback: Mapping[str, Any]) -> dict[str, Any]:
    return read_json(path) if path.exists() else dict(fallback)


def _source_report_input(name: str, path: Path, report: Mapping[str, Any]) -> dict[str, Any]:
    exists = path.exists()
    actual_sha = sha256_file(path) if exists else ""
    return {
        "source_report_name": name,
        "source_report_json": repo_relative(path),
        "source_report_exists": exists,
        "source_report_sha256": actual_sha,
        "source_report_hash_current": bool(exists and actual_sha),
        "source_run_id": clean(report.get("run_id")),
        "source_report_schema_version": clean(report.get("schema_version")),
        "source_report_diagnostic_only": bool(report.get("diagnostic_only", True)),
        "official_metric_input_rows": int(report.get("official_metric_input_rows") or 0),
        "promotion_evidence": bool(report.get("promotion_evidence")),
        "product_success_evidence_allowed": bool(report.get("product_success_evidence_allowed")),
    }


def build_source_reports() -> dict[str, dict[str, Any]]:
    return {
        "v4_5_1": _load_report(v451.REPORT_JSON, v451.build_artifacts()["report"]),
        "v4_5_2": _load_report(v452.REPORT_JSON, v452.build_artifacts()["report"]),
        "v4_5_3": _load_report(v453.REPORT_JSON, v453.build_artifacts()["report"]),
        "v4_6_6": _load_report(v466.REPORT_JSON, v466.build_artifacts()["report"]),
        "v4_6_7": _load_report(v467.REPORT_JSON, v467.build_artifacts()["report"]),
    }


def build_source_report_inputs(source_reports: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    paths = {
        "v4_5_1": v451.REPORT_JSON,
        "v4_5_2": v452.REPORT_JSON,
        "v4_5_3": v453.REPORT_JSON,
        "v4_6_6": v466.REPORT_JSON,
        "v4_6_7": v467.REPORT_JSON,
    }
    return {
        name: _source_report_input(name, paths[name], report)
        for name, report in sorted(source_reports.items())
    }


def forbidden_surface_violation_count(payload: Mapping[str, Any]) -> int:
    forbidden_keys = {
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
        "source_identity_audit_jsonl_created",
        "training_job_created",
        "training_manifest_jsonl_created",
        "v4_7_official_metric_gate_opened",
    }
    count = 0

    def visit(value: Any, key: str = "") -> None:
        nonlocal count
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
            return
        if key in forbidden_keys and value is True:
            count += 1
        if key in {"fine_tuning_dataset_exports_created", "official_metric_input_rows"} and int(value or 0) != 0:
            count += 1

    visit(payload)
    return count


def raw_source_identity_or_path_leak_count(payload: Mapping[str, Any]) -> int:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    patterns = (r"[A-Za-z]:/", r"\\\\", "parity-pdf-doc", "parity-workbook", "collision-doc")
    return sum(1 for pattern in patterns if re.search(pattern, serialized))


def build_dependency_freshness_gate(
    *,
    source_inputs: Mapping[str, Mapping[str, Any]],
    readiness_projection: Mapping[str, Any],
    holdout_validation_projection: Mapping[str, Any],
    report_shell: Mapping[str, Any],
) -> dict[str, Any]:
    source_hashes = {
        name: bool(input_report.get("source_report_hash_current"))
        for name, input_report in sorted(source_inputs.items())
    }
    runtime_matches = (
        readiness_projection.get("holdout_gap_ledger", {}).get("deficits")
        == report_shell.get("holdout_acquisition_requirements", {}).get("deficits")
        and readiness_projection.get("dry_run_input_manifest_exported") is False
        and readiness_projection.get("ft_route_policy_dry_run_opened") is False
    )
    contract_matches = (
        holdout_validation_projection.get("contract_hash")
        == report_shell.get("holdout_candidate_manifest_contract", {}).get("contract_hash")
    )
    forbidden_count = forbidden_surface_violation_count(report_shell)
    raw_leak_count = raw_source_identity_or_path_leak_count(report_shell)
    flag_open_count = sum(
        1
        for key in ("official_metric", "promotion_evidence", "product_success_evidence_allowed")
        if report_shell.get(key) is True
    ) + int(report_shell.get("official_metric_input_rows") or 0)
    return {
        "schema_version": f"{RUN_ID}_dependency_freshness_gate_v1",
        "run_id": RUN_ID,
        "all_source_report_hashes_current": all(source_hashes.values()),
        "source_report_hash_current_by_input": source_hashes,
        "runtime_readiness_dto_projection_matches_v4_6_6": runtime_matches,
        "holdout_validation_contract_hash_matches": contract_matches,
        "forbidden_surface_violation_count": forbidden_count,
        "raw_source_identity_or_path_leak_count": raw_leak_count,
        "official_or_promotion_flag_open_count": flag_open_count,
        "gate_passed": all(source_hashes.values())
        and runtime_matches
        and contract_matches
        and forbidden_count == 0
        and raw_leak_count == 0
        and flag_open_count == 0,
        "candidate_manifest_exported": False,
        "candidate_manifest_jsonl_created": False,
        "dry_run_input_manifest_exported": False,
        "ft_route_policy_dry_run_opened": False,
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
        "source_atom_evidence_bundle_evidence_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "source_atom_registry_mutated": False,
        "db_or_production_namespace_written": False,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_query_matching_used": False,
        "protected_namespaces_touched": [],
        "review_csv_created": False,
        "single_report_artifact_contract": True,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_artifacts() -> dict[str, Any]:
    source_reports = build_source_reports()
    source_inputs = build_source_report_inputs(source_reports)
    v466_report = source_reports["v4_6_6"]
    raw_holdout_gap = dict(v466_report.get("holdout_gap_ledger") or {})
    raw_dry_run_blockers = dict(v466_report.get("dry_run_blocker_ledger") or {})
    requirements = build_holdout_acquisition_requirements(
        deficits=raw_holdout_gap.get("deficits") or {},
        accepted_source_counts=raw_holdout_gap.get("source_counts") or {},
        query_fidelity_included_counts=raw_holdout_gap.get("query_fidelity_included_counts") or {},
        non_gold_next_actions=raw_holdout_gap.get("acquisition_requirements") or [],
        user_owned_next_actions=raw_dry_run_blockers.get("user_owned_next_actions") or [],
        blocked_reasons=v466_report.get("blocked_reasons") or [],
        readiness_decision="blocked_pending_real_external_holdout_candidates_and_user_policy",
        validation_route_path=HOLDOUT_CANDIDATE_VALIDATION_ROUTE_PATH,
    )
    contract = build_holdout_candidate_manifest_contract()
    service = SourceFirstRagService(readiness_report=v466_report)
    readiness_projection = model_to_dict(service.readiness())
    validation_projection = model_to_dict(
        service.validate_holdout_candidates(RagHoldoutCandidateValidationRequest(candidate_rows=[]))
    )
    guardrails = build_guardrails()
    report_shell = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "runtime_readiness_dependency_freshness_gate_only": True,
        "external_holdout_acquisition_requirements_packet_only": True,
        "holdout_candidate_manifest_contract": contract,
        "holdout_acquisition_requirements": requirements,
        "source_report_inputs": source_inputs,
        "runtime_readiness_projection": {
            "readiness_report_available": readiness_projection.get("readiness_report_available"),
            "run_id": readiness_projection.get("run_id"),
            "status": readiness_projection.get("status"),
            "holdout_gap_ledger": readiness_projection.get("holdout_gap_ledger"),
            "dry_run_blocker_count": readiness_projection.get("dry_run_blocker_count"),
            "candidate_manifest_exported": readiness_projection.get("candidate_manifest_exported"),
            "dry_run_input_manifest_exported": readiness_projection.get("dry_run_input_manifest_exported"),
            "ft_route_policy_dry_run_opened": readiness_projection.get("ft_route_policy_dry_run_opened"),
            "v4_7_official_metric_gate_opened": readiness_projection.get("v4_7_official_metric_gate_opened"),
            "official_metric_input_rows": readiness_projection.get("official_metric_input_rows"),
        },
        "holdout_validation_projection": {
            "schema_version": validation_projection.get("schema_version"),
            "contract_hash": validation_projection.get("contract_hash"),
            "candidate_manifest_present": validation_projection.get("candidate_manifest_present"),
            "candidate_manifest_rows": validation_projection.get("candidate_manifest_rows"),
            "official_metric_input_rows": validation_projection.get("official_metric_input_rows"),
            "promotion_evidence": validation_projection.get("promotion_evidence"),
            "product_success_evidence_allowed": validation_projection.get("product_success_evidence_allowed"),
        },
        "guardrails": guardrails,
        "guardrail_audit": dict(guardrails),
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
        "candidate_manifest_present": False,
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
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "review_csv_created": False,
        "single_report_artifact_contract": True,
        "blocked_reasons": [
            "real_external_holdout_candidates_not_registered",
            "candidate_manifest_export_remains_closed",
            "dry_run_input_manifest_not_exported",
            "ft_route_policy_dry_run_not_opened",
            "v4_7_official_metric_gate_not_opened",
            "user_owned_gold_qrels_denominator_policy_pending",
        ],
        "readiness_decision": "blocked_pending_real_external_holdout_candidates_and_user_policy",
    }
    freshness = build_dependency_freshness_gate(
        source_inputs=source_inputs,
        readiness_projection=readiness_projection,
        holdout_validation_projection=validation_projection,
        report_shell=report_shell,
    )
    report = {
        **report_shell,
        "dependency_freshness_gate": freshness,
        "metrics": {
            "schema_version": f"{RUN_ID}_metrics_v1",
            "run_id": RUN_ID,
            "status": STATUS,
            "diagnostic_only": True,
            "runtime_readiness_dependency_freshness_gate_only": True,
            "external_holdout_acquisition_requirements_packet_only": True,
            "all_source_report_hashes_current": freshness["all_source_report_hashes_current"],
            "runtime_readiness_dto_projection_matches_v4_6_6": freshness[
                "runtime_readiness_dto_projection_matches_v4_6_6"
            ],
            "holdout_validation_contract_hash_matches": freshness["holdout_validation_contract_hash_matches"],
            "forbidden_surface_violation_count": freshness["forbidden_surface_violation_count"],
            "raw_source_identity_or_path_leak_count": freshness["raw_source_identity_or_path_leak_count"],
            "official_or_promotion_flag_open_count": freshness["official_or_promotion_flag_open_count"],
            "real_holdout_sufficient": False,
            "candidate_manifest_exported": False,
            "dry_run_input_manifest_exported": False,
            "ft_route_policy_dry_run_opened": False,
            "v4_7_official_metric_gate_opened": False,
            "fine_tuning_dataset_exports_created": 0,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_db_index_cache_readiness": False,
            "review_csv_created": False,
            "gpu_required_for_this_slice": False,
            "gpu_required_for_future_training_when_opened": True,
        },
        "summary": {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "status": STATUS,
            "diagnostic_only": True,
            "runtime_readiness_dependency_freshness_gate_only": True,
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "readiness_decision": "blocked_pending_real_external_holdout_candidates_and_user_policy",
        },
        "artifact_paths": {"report_json": repo_relative(REPORT_JSON)},
        "residual_risks": [
            "No real external source-document-disjoint PDF candidate manifest is registered.",
            "No real external workbook-disjoint XLSX candidate manifest is registered.",
            "This run checks dependency freshness and acquisition requirements only; it does not acquire holdout rows.",
            "FT-A dry run, dataset export, job creation, and v4_7 remain unopened.",
        ],
        "next_recommendation": (
            "Register real source-disjoint PDF/XLSX candidate rows that satisfy the exposed acquisition requirements, "
            "then rerun v4_5_1, v4_5_2, v4_6_6, v4_6_7, and this freshness gate before any FT-A dry run."
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
        raise RuntimeError(f"unexpected v4_6_8 primary artifacts: {unexpected}")


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
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": sha256_file(REPORT_JSON)},
        "diagnostic_only": True,
        "runtime_readiness_dependency_freshness_gate_only": True,
        "external_holdout_acquisition_requirements_packet_only": True,
        "all_source_report_hashes_current": report["dependency_freshness_gate"]["all_source_report_hashes_current"],
        "runtime_readiness_dto_projection_matches_v4_6_6": report["dependency_freshness_gate"][
            "runtime_readiness_dto_projection_matches_v4_6_6"
        ],
        "holdout_validation_contract_hash_matches": report["dependency_freshness_gate"][
            "holdout_validation_contract_hash_matches"
        ],
        "forbidden_surface_violation_count": report["dependency_freshness_gate"]["forbidden_surface_violation_count"],
        "raw_source_identity_or_path_leak_count": report["dependency_freshness_gate"][
            "raw_source_identity_or_path_leak_count"
        ],
        "official_or_promotion_flag_open_count": report["dependency_freshness_gate"][
            "official_or_promotion_flag_open_count"
        ],
        "real_holdout_sufficient": False,
        "candidate_manifest_exported": False,
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
        raise AssertionError("unexpected v4_6_8 schema")
    freshness = report["dependency_freshness_gate"]
    if not freshness["gate_passed"]:
        raise AssertionError("v4_6_8 dependency freshness gate failed")
    if not freshness.get("all_source_report_hashes_current"):
        raise AssertionError("source report hashes must be current")
    if not all(freshness.get("source_report_hash_current_by_input", {}).values()):
        raise AssertionError("all source report hash inputs must be current")
    if not freshness.get("runtime_readiness_dto_projection_matches_v4_6_6"):
        raise AssertionError("runtime readiness projection must match v4_6_6")
    if not freshness.get("holdout_validation_contract_hash_matches"):
        raise AssertionError("holdout validation contract hash must match")
    if int(freshness.get("forbidden_surface_violation_count") or 0) != 0:
        raise AssertionError("dependency freshness gate recorded forbidden surface violations")
    if int(freshness.get("raw_source_identity_or_path_leak_count") or 0) != 0:
        raise AssertionError("dependency freshness gate recorded raw source identity or path leaks")
    if int(freshness.get("official_or_promotion_flag_open_count") or 0) != 0:
        raise AssertionError("dependency freshness gate recorded official or promotion openings")
    for name, source_input in dict(report.get("source_report_inputs") or {}).items():
        if not source_input.get("source_report_hash_current"):
            raise AssertionError(f"{name} source report hash must be current")
        if int(source_input.get("official_metric_input_rows") or 0) != 0:
            raise AssertionError(f"{name} official metric rows must remain zero")
        if source_input.get("promotion_evidence") is True:
            raise AssertionError(f"{name} promotion evidence must remain false")
        if source_input.get("product_success_evidence_allowed") is True:
            raise AssertionError(f"{name} product success evidence must remain false")
    if forbidden_surface_violation_count(report) != 0:
        raise AssertionError("nested forbidden surface opened")
    if raw_source_identity_or_path_leak_count(report) != 0:
        raise AssertionError("raw source identity or local path leaked")
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
        raise AssertionError("requirements packets must not satisfy real holdout")


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
    script = "ai\\scripts\\rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod.py"
    compile_cmd = f"python -X utf8 -m py_compile {script}"
    check_cmd = f"python -X utf8 {script} --check"
    if compile_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py\n",
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py\n"
            f"{compile_cmd}\n",
            1,
        )
    if check_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 ai\\scripts\\rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py --check\n",
            "python -X utf8 ai\\scripts\\rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py --check\n"
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
        r"v4_6_7 is `diagnostic_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod_ready`"
        r"(?:; v4_6_8 is `[^`]+`)?\.",
        f"v4_6_7 is `{v467.EVENT_TYPE}_ready`; v4_6_8 is `{current_status}`.",
        text,
        count=1,
    )
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    rows = [
        (
            "| `rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py` | "
            "Compares the default-disabled FastAPI holdout-candidate validator against v4_5_1/v4_5_2 script gates with in-memory hash-only probes; no manifest, sidecar, dataset, job, checkpoint, dry-run, prompt, raw LLM response, official metric, promotion, or product-success evidence is emitted. |"
        ),
        (
            "| `rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod.py` | "
            "Rechecks v4_5_1/v4_5_2/v4_5_3/v4_6_6/v4_6_7 report-hash freshness and projects FastAPI readiness/holdout-acquisition requirements without acquiring candidates, exporting manifests, opening dry runs, or emitting official/promotion/product/live readiness evidence. |"
        ),
    ]
    for script_name in (
        "rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py",
        "rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod.py",
    ):
        text = re.sub(rf"\n?\| `{re.escape(script_name)}` \| .*?\|", "", text)
    insertion = "\n".join(rows)
    text = text.replace(
        "\n\nv4 scripts remain diagnostic/non-production",
        f"\n{insertion}\n\nv4 scripts remain diagnostic/non-production",
        1,
    )
    scripts_readme.write_text(text, encoding="utf-8")


def update_progress_doc() -> None:
    current_status = f"{EVENT_TYPE}_ready"
    entry = (
        f"- v4_6_8 runtime readiness dependency freshness gate (`{RUN_ID}`) is {current_status}. "
        "It recomputes the current v4_5_1/v4_5_2/v4_5_3/v4_6_6/v4_6_7 report hashes, projects the "
        "default-disabled FastAPI readiness DTO and holdout-acquisition requirements packet, and confirms the "
        "runtime-side DTOs still match the closed v4_6_6 holdout-gap and blocker ledgers. This is a dependency "
        "freshness and acquisition-requirements packet only: it does not acquire real external holdout rows, does "
        "not export a candidate manifest, dry-run input manifest, dry-run plan, prompt payload, prompt manifest, "
        "raw LLM response, dataset, training manifest, job, checkpoint, official metric, promotion evidence, "
        "product-success evidence, production route, or live DB/index/cache readiness claim."
    )
    v467.replace_marked_entry(PROGRESS_DOC, RUN_ID, entry)
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{current_status}`;",
        text,
        count=1,
    )
    text = re.sub(
        r"(?:current diagnostic v4_6_8 runtime readiness dependency freshness gate loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_7 holdout candidate runtime gate parity bridge loop:\n`[^`]+`;",
        "current diagnostic v4_6_8 runtime readiness dependency freshness gate loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_6_7 holdout candidate runtime gate parity bridge loop:\n`{v467.RUN_ID}`;",
        text,
        count=1,
    )
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    path_text = report["artifact_paths"]["report_json"]
    entry = f"""### v4_6_8 Runtime Readiness Dependency Freshness Gate

- Run: `{RUN_ID}`
- v4 name: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Primary artifact: `{path_text}`
- Source evidence: current report hashes for v4_5_1, v4_5_2, v4_5_3, v4_6_6, and v4_6_7 plus FastAPI readiness/holdout-candidate validation DTO projections.
- Interpretation: this is a deterministic dependency-freshness and acquisition-requirements packet only. It is not real external holdout acquisition, not candidate manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| runtime_readiness_dependency_freshness_gate_only | true |
| external_holdout_acquisition_requirements_packet_only | true |
| all_source_report_hashes_current | {str(metrics['all_source_report_hashes_current']).lower()} |
| runtime_readiness_dto_projection_matches_v4_6_6 | {str(metrics['runtime_readiness_dto_projection_matches_v4_6_6']).lower()} |
| holdout_validation_contract_hash_matches | {str(metrics['holdout_validation_contract_hash_matches']).lower()} |
| forbidden_surface_violation_count | {metrics['forbidden_surface_violation_count']} |
| raw_source_identity_or_path_leak_count | {metrics['raw_source_identity_or_path_leak_count']} |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |

Artifact policy: single ignored `report.json`; no acquisition sidecar, candidate manifest sidecar, validation JSONL, source-identity audit JSONL, dry-run plan/input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, or per-run Markdown is created.
"""
    v467.replace_marked_entry(MEASUREMENTS_DOC, RUN_ID, entry)


def update_triage_doc() -> None:
    entry = f"""### v4_6_8 Runtime Readiness Dependency Freshness Gate Triage

- Run: `{RUN_ID}`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/{RUN_ID}/report.json`; single-report contract remains active.
- v4_6_8 is diagnostic-only, dependency-freshness-gate-only, and external-holdout-acquisition-requirements-packet-only.
- It proves current dependency freshness and FastAPI DTO projection consistency only; it is not real holdout availability, not external holdout acquisition, not candidate manifest export, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `real_holdout_sufficient=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.
"""
    v467.replace_marked_entry(TRIAGE_DOC, RUN_ID, entry)


def update_v4_plan() -> None:
    plan_path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    text = plan_path.read_text(encoding="utf-8")
    if "### v4_6_8 — Runtime Readiness Dependency Freshness Gate" not in text:
        insert = """### v4_6_8 — Runtime Readiness Dependency Freshness Gate

This is a diagnostic dependency-freshness and acquisition-requirements packet after v4_6_7, not holdout acquisition and not a dry run.

Purpose:

- Recompute the current v4_5_1, v4_5_2, v4_5_3, v4_6_6, and v4_6_7 report hashes.
- Project default-disabled FastAPI readiness and holdout-candidate validation DTOs against the closed v4_6_6/v4_6_7 contract.
- Keep real external holdout acquisition, manifest export, dry-run input/export, FT-A dry-run execution, dataset export, v4_7, official metric, promotion, product-success, and live-readiness gates closed.

Locked boundary:

```text
runtime_readiness_dependency_freshness_gate_only = true
external_holdout_acquisition_requirements_packet_only = true
all_source_report_hashes_current = true
runtime_readiness_dto_projection_matches_v4_6_6 = true
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

"""
        text = text.replace("### v4_7 — Official Metric Opening Gate", insert + "### v4_7 — Official Metric Opening Gate", 1)
    text = text.replace(
        "v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        "v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod\n↓\nv4_6_8_runtime_readiness_dependency_freshness_gate_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
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
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    check_report(artifacts["report"])
    if args.check:
        metrics = artifacts["report"]["metrics"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": STATUS,
                    "runtime_readiness_dependency_freshness_gate_only": True,
                    "external_holdout_acquisition_requirements_packet_only": True,
                    "all_source_report_hashes_current": metrics["all_source_report_hashes_current"],
                    "real_holdout_sufficient": False,
                    "candidate_manifest_exported": False,
                    "ft_route_policy_dry_run_opened": False,
                    "v4_7_official_metric_gate_opened": False,
                    "fine_tuning_dataset_exports_created": 0,
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
