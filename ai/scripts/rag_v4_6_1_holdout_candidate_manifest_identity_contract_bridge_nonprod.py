from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_5_1_holdout_candidate_intake_gate_nonprod as v451
import rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod as v452
import rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod as v453
import rag_v4_6_ft_route_policy_dry_run_preflight_nonprod as v46
from app.capabilities.rag import holdout_manifest_contract


ROOT = v46.ROOT
REPORT_DIR = v46.REPORT_DIR
STATUS_JSONL = v46.STATUS_JSONL
PROGRESS_DOC = v46.PROGRESS_DOC
MEASUREMENTS_DOC = v46.MEASUREMENTS_DOC
TRIAGE_DOC = v46.TRIAGE_DOC
README = v46.README
EVAL_README = v46.EVAL_README

V4_NAME = v46.V4_NAME
V4_RUN_FAMILY = v46.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod"
EVENT_TYPE = "diagnostic_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod"
STATUS = "DIAGNOSTIC_V4_6_1_HOLDOUT_CANDIDATE_MANIFEST_IDENTITY_CONTRACT_BRIDGE_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_report_v1"
REQUIRED_CONTRACT_HASH_INPUTS = (
    "v4_5_1",
    "v4_5_2",
    "v4_5_3",
    "v4_6.source_report_inputs.v4_5_1",
    "v4_6.source_report_inputs.v4_5_2",
    "v4_6.source_report_inputs.v4_5_3",
)
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "candidate_validation.jsonl",
            "contract_probe_results.jsonl",
            "dpo_dataset.jsonl",
            "ft_route_policy_dry_run.json",
            "holdout_candidate_manifest.jsonl",
            "metrics.json",
            "prompt_manifest.json",
            "raw_llm_response.json",
            "review_packet.csv",
            "reward_model_dataset.jsonl",
            "sft_dataset.jsonl",
            "source_identity_audit.jsonl",
            "summary.json",
            "training_manifest.jsonl",
        }
    )
)


def clean(value: Any) -> str:
    return v46.clean(value)


def repo_relative(path: Path) -> str:
    return v46.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v46.artifact_path_text(path)


def utc_now() -> str:
    return v46.utc_now()


def sha256_file(path: Path) -> str:
    return v46.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v46.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v46.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v46.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v46.write_jsonl(path, rows)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def load_report(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def load_source_reports() -> dict[str, dict[str, Any]]:
    return {
        "v4_5_1": load_report(v451.REPORT_JSON),
        "v4_5_2": load_report(v452.REPORT_JSON),
        "v4_5_3": load_report(v453.REPORT_JSON),
        "v4_6": load_report(v46.REPORT_JSON),
    }


def bridge_source_report_input(
    *,
    input_key: str,
    run_id: str,
    report_json: Path,
    report: Mapping[str, Any],
) -> dict[str, Any]:
    source_input = v46.source_report_input(
        input_key=input_key,
        run_id=run_id,
        report_json=report_json,
        report=report,
    )
    source_input["schema_version"] = f"{RUN_ID}_source_report_input_v1"
    source_input["run_id"] = RUN_ID
    return source_input


def source_report_inputs(source_reports: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    inputs = {
        "v4_5_1": bridge_source_report_input(
            input_key="v4_5_1",
            run_id=v451.RUN_ID,
            report_json=v451.REPORT_JSON,
            report=source_reports.get("v4_5_1", {}),
        ),
        "v4_5_2": bridge_source_report_input(
            input_key="v4_5_2",
            run_id=v452.RUN_ID,
            report_json=v452.REPORT_JSON,
            report=source_reports.get("v4_5_2", {}),
        ),
        "v4_5_3": bridge_source_report_input(
            input_key="v4_5_3",
            run_id=v453.RUN_ID,
            report_json=v453.REPORT_JSON,
            report=source_reports.get("v4_5_3", {}),
        ),
        "v4_6": bridge_source_report_input(
            input_key="v4_6",
            run_id=v46.RUN_ID,
            report_json=v46.REPORT_JSON,
            report=source_reports.get("v4_6", {}),
        ),
    }
    v4_6_hashes = v4_6_embedded_contract_hashes(source_reports.get("v4_6", {}))
    observed = [clean(v4_6_hashes.get(key)) for key in ("v4_5_1", "v4_5_2", "v4_5_3")]
    unique_observed = {value for value in observed if value}
    if not inputs["v4_6"]["source_report_holdout_candidate_manifest_contract_hash"] and len(unique_observed) == 1:
        inputs["v4_6"]["source_report_holdout_candidate_manifest_contract_hash"] = unique_observed.pop()
        inputs["v4_6"]["source_report_holdout_candidate_manifest_contract_version"] = (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
        )
        inputs["v4_6"]["source_report_holdout_candidate_manifest_contract_hash_source"] = (
            "v4_6.source_report_inputs"
        )
    return inputs


def _report_contract_hash(report: Mapping[str, Any]) -> str:
    contract = _mapping(report.get("holdout_candidate_manifest_contract"))
    return clean(report.get("holdout_candidate_manifest_contract_hash") or contract.get("contract_hash"))


def v4_6_embedded_contract_hashes(v4_6_report: Mapping[str, Any]) -> dict[str, str]:
    embedded = _mapping(v4_6_report.get("source_report_inputs"))
    return {
        key: clean(_mapping(embedded.get(key)).get("source_report_holdout_candidate_manifest_contract_hash"))
        for key in ("v4_5_1", "v4_5_2", "v4_5_3")
    }


def source_contract_hashes(source_reports: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    hashes = {
        key: _report_contract_hash(source_reports.get(key, {}))
        for key in ("v4_5_1", "v4_5_2", "v4_5_3")
    }
    for key, value in v4_6_embedded_contract_hashes(source_reports.get("v4_6", {})).items():
        hashes[f"v4_6.source_report_inputs.{key}"] = value
    return hashes


def build_identity_contract_probe_results() -> list[dict[str, Any]]:
    contract_hash = holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
    pdf_priority_row = {
        "candidate_id": "pdf-priority",
        "query_id": "pdf-priority-q",
        "source_family": "PDF",
        "document_version_id": "pdf-doc-version",
        "source_document_id": "pdf-source-document",
        "disjoint_from_prior": True,
        "query_fidelity_included": True,
        "real_unseen": True,
    }
    pdf_conflict_row = {
        "candidate_id": "pdf-conflict",
        "query_id": "pdf-conflict-q",
        "source_family": "PDF",
        "document_version_id": "pdf-doc-version-a",
        "raw_locator": {"document_version_id": "pdf-doc-version-b"},
        "disjoint_from_prior": True,
        "query_fidelity_included": True,
        "real_unseen": True,
    }
    xlsx_source_identity_only_row = {
        "candidate_id": "xlsx-source-identity-only",
        "query_id": "xlsx-source-identity-q",
        "source_family": "XLSX",
        "source_identity": "xlsx-source-identity-is-not-workbook-proof",
        "disjoint_from_prior": True,
        "query_fidelity_included": True,
        "real_unseen": True,
    }
    xlsx_conflict_row = {
        "candidate_id": "xlsx-conflict",
        "query_id": "xlsx-conflict-q",
        "source_family": "XLSX",
        "workbook_id": "xlsx-workbook-a",
        "raw_locator": {"workbook": "xlsx-workbook-b"},
        "disjoint_from_prior": True,
        "query_fidelity_included": True,
        "real_unseen": True,
    }
    validation = v451.validate_holdout_candidate_rows(
        [pdf_priority_row, pdf_conflict_row, xlsx_source_identity_only_row, xlsx_conflict_row],
        minimum_targets={
            "pdf_unseen_source_documents": 1,
            "xlsx_unseen_workbooks": 1,
            "query_fidelity_included_rows_per_family": 1,
        },
    )
    accepted = {row["candidate_id"]: row for row in validation["accepted_candidates"]}
    excluded = {row["candidate_id"]: row for row in validation["excluded_candidates"]}
    reports = {
        "v4_5_report": v46.load_v4_5_report(),
        "v4_5_1_report": dict(v46.load_v4_5_1_report()),
        "v4_5_2_report": v46.load_v4_5_2_report(),
        "v4_5_3_report": v46.load_v4_5_3_report(),
    }
    stale_v451_report = dict(reports["v4_5_1_report"])
    stale_v451_report["holdout_candidate_manifest_contract_hash"] = "stale-contract-hash"
    mismatch_gates = v46.build_preflight_gates(
        v4_5_report=reports["v4_5_report"],
        v4_5_1_report=stale_v451_report,
        v4_5_2_report=reports["v4_5_2_report"],
        v4_5_3_report=reports["v4_5_3_report"],
    )
    mismatch_failed_checks = list(
        _mapping(
            _mapping(mismatch_gates["v4_5_1_candidate_intake_gate"].get("evidence")).get(
                "source_report_contract"
            )
        ).get("failed_checks")
        or []
    )
    return [
        {
            "probe_id": "PDF_DOCUMENT_VERSION_PRIORITY",
            "passed": accepted.get("pdf-priority", {}).get("source_identity_key") == "pdf-doc-version",
            "expected_policy": "PDF document_version identity wins over source_document fallback",
            "contract_hash": contract_hash,
        },
        {
            "probe_id": "PDF_SAME_TIER_CONFLICT_FAILS_CLOSED",
            "passed": excluded.get("pdf-conflict", {}).get("exclusion_reason") == "source_identity_field_conflict",
            "expected_policy": "same-tier PDF document_version aliases with different values fail closed",
            "contract_hash": contract_hash,
        },
        {
            "probe_id": "XLSX_SOURCE_IDENTITY_ONLY_REJECTED",
            "passed": excluded.get("xlsx-source-identity-only", {}).get("exclusion_reason") == "source_identity_missing",
            "expected_policy": "XLSX source_identity alone is metadata, not workbook proof",
            "contract_hash": contract_hash,
        },
        {
            "probe_id": "XLSX_SAME_TIER_CONFLICT_FAILS_CLOSED",
            "passed": excluded.get("xlsx-conflict", {}).get("exclusion_reason") == "source_identity_field_conflict",
            "expected_policy": "same-tier XLSX workbook aliases with different values fail closed",
            "contract_hash": contract_hash,
        },
        {
            "probe_id": "V4_6_HASH_MISMATCH_REJECTED",
            "passed": "holdout_candidate_manifest_contract_hash_matches" in mismatch_failed_checks,
            "expected_policy": "v4_6 preflight rejects stale holdout manifest contract hashes",
            "contract_hash": contract_hash,
        },
    ]


def build_contract_bridge_gate(
    *,
    source_reports: Mapping[str, Mapping[str, Any]],
    probe_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected_hash = holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
    hashes = source_contract_hashes(source_reports)
    required_hashes = {key: clean(hashes.get(key)) for key in REQUIRED_CONTRACT_HASH_INPUTS}
    missing = sorted(key for key, value in required_hashes.items() if not value)
    mismatched = sorted(key for key, value in required_hashes.items() if value and value != expected_hash)
    probe_failed = sorted(clean(row.get("probe_id")) for row in probe_results if row.get("passed") is not True)
    blocked_reasons: list[str] = []
    if missing:
        blocked_reasons.append("holdout_candidate_manifest_contract_hash_missing")
    if mismatched:
        blocked_reasons.append("holdout_candidate_manifest_contract_hash_mismatch")
    if probe_failed:
        blocked_reasons.append("identity_contract_probe_failed")
    passed = not blocked_reasons
    return {
        "schema_version": f"{RUN_ID}_contract_bridge_gate_v1",
        "run_id": RUN_ID,
        "passed": passed,
        "contract_hashes_match": not missing and not mismatched,
        "identity_probe_passed": not probe_failed,
        "v4_6_hash_mismatch_rejection_passed": not probe_failed
        and any(row.get("probe_id") == "V4_6_HASH_MISMATCH_REJECTED" for row in probe_results),
        "expected_contract_hash": expected_hash,
        "observed_contract_hashes": required_hashes,
        "missing_contract_hash_inputs": missing,
        "mismatched_contract_hash_inputs": mismatched,
        "failed_identity_probe_ids": probe_failed,
        "blocked_reasons": blocked_reasons,
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
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
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
    gate: Mapping[str, Any],
    probe_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "holdout_candidate_manifest_identity_contract_bridge_only": True,
        "contract_bridge_gate_passed": bool(gate.get("passed")),
        "contract_hashes_match": bool(gate.get("contract_hashes_match")),
        "identity_probe_passed": bool(gate.get("identity_probe_passed")),
        "v4_6_hash_mismatch_rejection_passed": bool(gate.get("v4_6_hash_mismatch_rejection_passed")),
        "identity_contract_probe_count": len(probe_results),
        "identity_contract_probe_passed_count": sum(1 for row in probe_results if row.get("passed") is True),
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "fine_tuning_dataset_exports_created": 0,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
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
    source_reports: Mapping[str, Mapping[str, Any]],
    source_inputs: Mapping[str, Mapping[str, Any]],
    probe_results: Sequence[Mapping[str, Any]],
    gate: Mapping[str, Any],
    metrics: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    blocked_reasons = list(gate.get("blocked_reasons") or [])
    if "user_owned_gold_qrels_denominator_policy_pending" not in blocked_reasons:
        blocked_reasons.append("user_owned_gold_qrels_denominator_policy_pending")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "holdout_candidate_manifest_identity_contract_bridge_only": True,
        "holdout_candidate_manifest_contract": holdout_manifest_contract.build_holdout_candidate_manifest_contract(),
        "holdout_candidate_manifest_contract_version": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
        ),
        "holdout_candidate_manifest_contract_hash_algorithm": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH_ALGORITHM
        ),
        "holdout_candidate_manifest_contract_hash": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
        ),
        "contract_bridge_gate": dict(gate),
        "identity_contract_probe_results": [dict(row) for row in probe_results],
        "source_report_inputs": {key: dict(value) for key, value in source_inputs.items()},
        "source_report_contract_hashes": source_contract_hashes(source_reports),
        "readiness_decision": "blocked_pending_external_candidate_manifest_and_user_policy",
        "blocked_reasons": blocked_reasons,
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
        "fine_tuning_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "v4_6_ft_dry_run_opened": False,
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
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py --check",
                "targeted v4_6_1 contract bridge tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_6_1 because this slice validates deterministic "
                "contract hashes and identity policy probes; future FT-A training, embedding, or LLM workloads should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "No default external real holdout candidate manifest is present.",
            "v4_5_1 and v4_5_2 gates remain closed without accepted external candidates.",
            "User-owned gold/qrels/denominator and promotion policy remain closed.",
            "v4_6 FT-A dry run and v4_7 official metric opening remain unopened.",
        ],
        "next_recommendation": (
            "Keep v4_7 closed until user-owned policy inputs exist; next non-gold work should either "
            "harden external candidate manifest validation or prepare a non-writing FT-A dry-run fixture contract."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    source_reports = load_source_reports()
    inputs = source_report_inputs(source_reports)
    probe_results = build_identity_contract_probe_results()
    gate = build_contract_bridge_gate(source_reports=source_reports, probe_results=probe_results)
    metrics = build_metrics(gate=gate, probe_results=probe_results)
    guardrails = build_guardrails()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        source_reports=source_reports,
        source_inputs=inputs,
        probe_results=probe_results,
        gate=gate,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "contract_bridge_gate": gate,
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
        raise RuntimeError(f"unexpected v4_6_1 primary artifacts: {unexpected}")


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
        "contract_bridge_gate": dict(report["contract_bridge_gate"]),
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
    v46.replace_marked_entry(path, marker, entry)


def _refresh_docs() -> None:
    v46._refresh_docs()


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_6_1 holdout candidate manifest identity contract bridge loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6 FT route policy dry-run preflight loop:\n`[^`]+`;",
        "current diagnostic v4_6_1 holdout candidate manifest identity contract bridge loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_6 FT route policy dry-run preflight loop:\n`{v46.RUN_ID}`;",
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
        "ai\\scripts\\rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py --check\n"
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
        r"(?:; v4_6 is `[^`]+`)?(?:; v4_6_1 is `[^`]+`)?\.",
        f"v4_5_3 is `{v453.EVENT_TYPE}_ready`; v4_6 is `{v46.EVENT_TYPE}_ready`; "
        f"v4_6_1 is `{EVENT_TYPE}_ready`.",
        eval_text,
        count=1,
    )
    EVAL_README.write_text(eval_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py` | "
        "Hash-locks the v4_5_1/v4_5_2/v4_5_3/v4_6 holdout-candidate manifest identity contract and probes PDF/XLSX identity priority, conflict fail-closed behavior, XLSX source_identity-only rejection, and v4_6 stale-contract rejection; no manifest, dataset, job, checkpoint, prompt, raw LLM response, official metric, promotion, or product-success evidence is emitted. |"
    )
    pattern = r"\| `rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod\.py` \| .*?\|"
    if re.search(pattern, text):
        text = re.sub(pattern, row, text, count=1)
    elif "| `rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py` |" in text:
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
    if "### v4_6_1 — Holdout Candidate Manifest Identity Contract Bridge" not in text:
        insert = """### v4_6_1 — Holdout Candidate Manifest Identity Contract Bridge

This is a diagnostic bridge after v4_6 preflight, not a dry run and not an official metric opening gate.

Purpose:

- Hash-lock the shared holdout candidate manifest identity contract across v4_5_1, v4_5_2, v4_5_3, and v4_6.
- Probe PDF/XLSX identity priority, same-tier conflict fail-closed behavior, XLSX source_identity-only rejection, and v4_6 stale-contract rejection.
- Keep v4_6 FT-A dry run and v4_7 official metric opening closed.

Required state:

```text
holdout_candidate_manifest_identity_contract_bridge_only = true
contract_hashes_match = true
identity_probe_passed = true
v4_6_ft_dry_run_opened = false
v4_7_official_metric_gate_opened = false
official_metric_input_rows = 0
promotion_evidence = false
product_success_evidence_allowed = false
```

"""
        text = text.replace("### v4_7 — Official Metric Opening Gate", insert + "### v4_7 — Official Metric Opening Gate", 1)
    text = text.replace(
        "v4_6_ft_route_policy_dry_run_preflight_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        "v4_6_ft_route_policy_dry_run_preflight_nonprod\n↓\nv4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
    )
    EVAL_README.write_text(EVAL_README.read_text(encoding="utf-8"), encoding="utf-8")
    plan_path.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    report_path = report["artifact_paths"]["report_json"]
    metrics = report["metrics"]
    _refresh_docs()
    progress_entry = (
        f"- v4_6_1 holdout candidate manifest identity contract bridge (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It hash-locks the v4_5_1/v4_5_2/v4_5_3/v4_6 holdout-candidate manifest identity contract and probes PDF/XLSX identity priority, same-tier conflict fail-closed behavior, XLSX `source_identity`-only rejection, and v4_6 stale-contract rejection. "
        "This is diagnostic-only and bridge-only: it does not open the FT-A dry run, does not open v4_7, does not create a candidate manifest, validation sidecar, dataset, training job, checkpoint, prompt payload, raw LLM response, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim."
    )
    measurements_entry = f"""### v4_6_1 Holdout Candidate Manifest Identity Contract Bridge

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, identity-contract bridge only, single `report.json`.
- Primary artifact: `{report_path}`
- Source evidence: v4_5_1/v4_5_2/v4_5_3 reports expose the shared holdout manifest contract hash, and v4_6 source report inputs re-lock those same hashes.

| Diagnostic count | Value |
| --- | ---: |
| holdout_candidate_manifest_identity_contract_bridge_only | true |
| contract_bridge_gate_passed | {str(metrics["contract_bridge_gate_passed"]).lower()} |
| contract_hashes_match | {str(metrics["contract_hashes_match"]).lower()} |
| identity_probe_passed | {str(metrics["identity_probe_passed"]).lower()} |
| v4_6_hash_mismatch_rejection_passed | {str(metrics["v4_6_hash_mismatch_rejection_passed"]).lower()} |
| identity_contract_probe_count | {metrics["identity_contract_probe_count"]} |
| identity_contract_probe_passed_count | {metrics["identity_contract_probe_passed_count"]} |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| v4_7_official_metric_gate_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the shared contract hash, source report input hashes, identity probe results, contract_bridge_gate, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no candidate manifest, validation sidecar, source-identity audit sidecar, prompt payload, raw LLM response, dataset sidecar, training job, checkpoint, review CSV, or per-run Markdown.
"""
    triage_entry = (
        "### v4_6_1 Holdout Candidate Manifest Identity Contract Bridge Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_6_1 is diagnostic-only, non-production, holdout-candidate manifest identity contract bridge only.\n"
        "- The bridge proves contract consistency only; it is not split sufficiency, not holdout availability, not the FT-A dry run, and not a v4_7 opening.\n"
        "- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `v4_6_ft_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.\n"
        "- No candidate manifest, validation sidecar, training dataset, job, checkpoint, prompt payload, raw LLM response, production route, or live DB/index/cache readiness claim is created.\n"
        "- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.\n"
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
                    "contract_bridge_gate_passed": report["metrics"]["contract_bridge_gate_passed"],
                    "contract_hashes_match": report["metrics"]["contract_hashes_match"],
                    "identity_probe_passed": report["metrics"]["identity_probe_passed"],
                    "v4_6_hash_mismatch_rejection_passed": report["metrics"][
                        "v4_6_hash_mismatch_rejection_passed"
                    ],
                    "fine_tuning_dataset_exports_created": report["metrics"][
                        "fine_tuning_dataset_exports_created"
                    ],
                    "official_metric_input_rows": report["metrics"]["official_metric_input_rows"],
                    "v4_6_ft_dry_run_opened": report["metrics"]["ft_route_policy_dry_run_opened"],
                    "v4_7_official_metric_gate_opened": report["metrics"][
                        "v4_7_official_metric_gate_opened"
                    ],
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
