from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_5_1_holdout_candidate_intake_gate_nonprod as v451
import rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod as v452
import rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod as v453
import rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod as v466


ROOT = v466.ROOT
REPORT_DIR = v466.REPORT_DIR
STATUS_JSONL = v466.STATUS_JSONL
PROGRESS_DOC = v466.PROGRESS_DOC
MEASUREMENTS_DOC = v466.MEASUREMENTS_DOC
TRIAGE_DOC = v466.TRIAGE_DOC
README = v466.README
EVAL_README = v466.EVAL_README

AI_ROOT = ROOT / "ai"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.capabilities.rag import holdout_manifest_contract  # noqa: E402
from app.capabilities.rag.holdout_candidate_validation import (  # noqa: E402
    SOURCE_IDENTITY_HASH_ALGORITHM,
    validate_holdout_candidate_rows_for_fastapi,
)


V4_NAME = v466.V4_NAME
V4_RUN_FAMILY = v466.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod"
EVENT_TYPE = "diagnostic_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod"
STATUS = "DIAGNOSTIC_V4_6_7_HOLDOUT_CANDIDATE_RUNTIME_GATE_PARITY_BRIDGE_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_report_v1"

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v466.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
            "candidate_manifest.jsonl",
            "candidate_validation.jsonl",
            "dry_run_execution_plan.json",
            "dry_run_input_manifest.jsonl",
            "metrics.json",
            "official_metric_results.jsonl",
            "prompt_manifest.json",
            "raw_llm_response.json",
            "review_packet.csv",
            "runtime_gate_parity.json",
            "source_identity_audit.jsonl",
            "summary.json",
            "training_manifest.jsonl",
        }
    )
)


def clean(value: Any) -> str:
    return v466.clean(value)


def repo_relative(path: Path) -> str:
    return v466.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v466.artifact_path_text(path)


def utc_now() -> str:
    return v466.utc_now()


def sha256_file(path: Path) -> str:
    return v466.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v466.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v466.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v466.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v466.write_jsonl(path, rows)


def _source_identity_hash(family: str, identity_key: str) -> str:
    return hashlib.sha256(f"{family}:{identity_key}".encode("utf-8")).hexdigest()


def _target_sufficient_probe_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(100):
        rows.append(
            {
                "candidate_id": f"parity-pdf-candidate-{index:03d}",
                "query_id": f"parity-pdf-query-{index:03d}",
                "source_family": "PDF",
                "source_document_id": f"parity-pdf-doc-{index % 20:02d}",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            }
        )
    for index in range(100):
        rows.append(
            {
                "candidate_id": f"parity-xlsx-candidate-{index:03d}",
                "query_id": f"parity-xlsx-query-{index:03d}",
                "source_family": "XLSX",
                "workbook_id": f"parity-workbook-{index % 8:02d}",
                "disjoint_from_prior": True,
                "query_fidelity_included": True,
                "real_unseen": True,
            }
        )
    return rows


def _prior_collision_probe_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "collision-pdf-candidate",
            "query_id": "collision-pdf-query",
            "source_family": "PDF",
            "source_document_id": "collision-doc",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
        }
    ]


def _hash_record(family: str, identity_key: str) -> dict[str, Any]:
    family = family.upper()
    return {
        "schema_version": f"{RUN_ID}_prior_identity_hash_record_probe_v1",
        "source_family": family,
        "source_identity_hash": _source_identity_hash(family, identity_key),
        "identity_scope": "PDF_source_document" if family == "PDF" else "XLSX_workbook",
        "source_atom_count": 1,
        "raw_source_identity_value_embedded": False,
        "raw_local_path_value_embedded": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def _prior_identity_summary_report(hash_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, list[dict[str, Any]]] = {"PDF": [], "XLSX": [], "TEXT": []}
    normalized_records: list[dict[str, Any]] = []
    for record in hash_records:
        family = clean(record.get("source_family")).upper()
        source_identity_hash = clean(record.get("source_identity_hash"))
        if family not in by_family or not source_identity_hash:
            continue
        normalized = {
            "source_family": family,
            "source_identity_hash": source_identity_hash,
            "identity_scope": clean(record.get("identity_scope")),
            "source_atom_count": int(record.get("source_atom_count") or 0),
            "raw_source_identity_value_embedded": False,
            "raw_local_path_value_embedded": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
        }
        by_family[family].append(normalized)
        normalized_records.append(normalized)
    normalized_records.sort(key=lambda item: (item["source_family"], item["source_identity_hash"]))
    summary = {
        "schema_version": f"{RUN_ID}_prior_identity_ledger_summary_probe_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "prior_source_identity_ledger_summary_only": True,
        "prior_identity_collision_baseline_available": True,
        "identity_key_hash_algorithm": SOURCE_IDENTITY_HASH_ALGORITHM,
        "holdout_candidate_manifest_contract_version": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
        ),
        "holdout_candidate_manifest_contract_hash": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
        ),
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
        "prior_identity_key_counts_by_family": {
            family: len(rows) for family, rows in by_family.items()
        },
        "prior_identity_source_atom_counts_by_family": {
            family: sum(int(row["source_atom_count"]) for row in rows)
            for family, rows in by_family.items()
        },
        "source_registry_family_row_counts": {"PDF": 0, "XLSX": 0, "TEXT": 0},
        "prior_identity_hash_record_count": len(normalized_records),
        "prior_identity_hash_set_sha256": v453.prior_identity_hash_set_sha256(normalized_records),
        "prior_identity_hash_records_by_family": by_family,
    }
    return {"prior_identity_ledger_summary": summary}


def _candidate_gate_snapshot(gate: Mapping[str, Any]) -> dict[str, Any]:
    counts = dict(gate.get("accepted_holdout_candidate_counts") or {})
    query_counts = dict(gate.get("real_query_fidelity_included_counts") or {})
    targets = dict(gate.get("minimum_targets") or {})
    deficits = dict(gate.get("deficits") or _deficits_from_gate(counts, query_counts, targets))
    return {
        "passed": bool(gate.get("passed")),
        "candidate_manifest_present": bool(gate.get("candidate_manifest_present")),
        "candidate_manifest_rows": int(gate.get("candidate_manifest_rows") or 0),
        "accepted_holdout_candidate_counts": counts,
        "real_query_fidelity_included_counts": query_counts,
        "minimum_targets": targets,
        "deficits": deficits,
        "excluded_candidate_count": int(gate.get("excluded_candidate_count") or 0),
        "blocked_reasons": list(gate.get("blocked_reasons") or []),
        "official_metric_input_rows": int(gate.get("official_metric_input_rows") or 0),
    }


def _source_identity_gate_snapshot(gate: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = _candidate_gate_snapshot(gate)
    snapshot.update(
        {
            "prior_identity_baseline_present": bool(gate.get("prior_identity_baseline_present")),
            "prior_identity_hash_summary_present": bool(gate.get("prior_identity_hash_summary_present")),
            "prior_identity_hash_summary_rows": int(gate.get("prior_identity_hash_summary_rows") or 0),
            "source_identity_collision_count": int(gate.get("source_identity_collision_count") or 0),
            "source_identity_audit_excluded_count": int(gate.get("source_identity_audit_excluded_count") or 0),
        }
    )
    return snapshot


def _runtime_audit_gate_snapshot(gate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "executed": bool(gate.get("executed")),
        "prior_identity_hash_record_count": int(gate.get("prior_identity_hash_record_count") or 0),
        "collision_count": int(gate.get("collision_count") or 0),
        "passed": bool(gate.get("passed")),
    }


def _deficits_from_gate(
    counts: Mapping[str, Any],
    query_counts: Mapping[str, Any],
    targets: Mapping[str, Any],
) -> dict[str, int]:
    return {
        "pdf_source_document_disjoint_needed": max(
            0,
            int(targets.get("pdf_unseen_source_documents") or 0)
            - int(counts.get("PDF_source_document_disjoint") or 0),
        ),
        "xlsx_workbook_disjoint_needed": max(
            0,
            int(targets.get("xlsx_unseen_workbooks") or 0)
            - int(counts.get("XLSX_workbook_disjoint") or 0),
        ),
        "pdf_query_fidelity_rows_needed": max(
            0,
            int(targets.get("query_fidelity_included_rows_per_family") or 0)
            - int(query_counts.get("PDF") or 0),
        ),
        "xlsx_query_fidelity_rows_needed": max(
            0,
            int(targets.get("query_fidelity_included_rows_per_family") or 0)
            - int(query_counts.get("XLSX") or 0),
        ),
    }


def _runtime_hash_sample(validation: Mapping[str, Any]) -> dict[str, list[str]]:
    accepted = validation.get("accepted_candidates")
    excluded = validation.get("excluded_candidates")
    accepted_rows = accepted if isinstance(accepted, Sequence) and not isinstance(accepted, (str, bytes)) else []
    excluded_rows = excluded if isinstance(excluded, Sequence) and not isinstance(excluded, (str, bytes)) else []
    return {
        "accepted_source_identity_hashes": [
            clean(row.get("source_identity_hash"))
            for row in accepted_rows
            if isinstance(row, Mapping) and clean(row.get("source_identity_hash"))
        ][:3],
        "excluded_source_identity_hashes": [
            clean(row.get("source_identity_hash"))
            for row in excluded_rows
            if isinstance(row, Mapping) and clean(row.get("source_identity_hash"))
        ][:3],
    }


def build_parity_probe(
    *,
    probe_id: str,
    candidate_rows: Sequence[Mapping[str, Any]],
    prior_identity_hash_records: Sequence[Mapping[str, Any]],
    compare_v4_5_1: bool,
) -> dict[str, Any]:
    prior_summary = _prior_identity_summary_report(prior_identity_hash_records)
    runtime_validation = validate_holdout_candidate_rows_for_fastapi(
        candidate_rows,
        prior_identity_hash_records=prior_identity_hash_records,
    )
    v451_report = v451.build_artifacts(candidate_rows=candidate_rows)["report"]
    v452_report = v452.build_artifacts(
        candidate_rows=candidate_rows,
        prior_identity_summary_report=prior_summary,
    )["report"]

    runtime_candidate_gate = _candidate_gate_snapshot(runtime_validation["candidate_intake_gate"])
    runtime_candidate_gate["candidate_manifest_present"] = bool(candidate_rows)
    runtime_candidate_gate["candidate_manifest_rows"] = len(candidate_rows)
    runtime_audit_gate = _runtime_audit_gate_snapshot(runtime_validation["source_identity_audit_gate"])
    v451_candidate_gate = _candidate_gate_snapshot(v451_report["candidate_intake_gate"])
    v452_audit_gate = _source_identity_gate_snapshot(v452_report["source_identity_audit_gate"])
    v452_candidate_like_gate = {
        key: v452_audit_gate[key]
        for key in (
            "passed",
            "candidate_manifest_present",
            "candidate_manifest_rows",
            "accepted_holdout_candidate_counts",
            "real_query_fidelity_included_counts",
            "minimum_targets",
            "deficits",
            "excluded_candidate_count",
        )
    }
    runtime_candidate_like_gate = {
        key: runtime_candidate_gate[key]
        for key in (
            "passed",
            "candidate_manifest_present",
            "candidate_manifest_rows",
            "accepted_holdout_candidate_counts",
            "real_query_fidelity_included_counts",
            "minimum_targets",
            "deficits",
            "excluded_candidate_count",
        )
    }
    v451_candidate_like_gate = {
        key: v451_candidate_gate[key]
        for key in runtime_candidate_like_gate
    }
    parity_checks = {
        "candidate_manifest_shape_matches": (
            runtime_candidate_gate["candidate_manifest_present"] == v451_candidate_gate["candidate_manifest_present"]
            and runtime_candidate_gate["candidate_manifest_rows"] == v451_candidate_gate["candidate_manifest_rows"]
        ),
        "candidate_counts_match_v4_5_1": (
            runtime_candidate_gate["accepted_holdout_candidate_counts"]
            == v451_candidate_gate["accepted_holdout_candidate_counts"]
        ),
        "query_counts_match_v4_5_1": (
            runtime_candidate_gate["real_query_fidelity_included_counts"]
            == v451_candidate_gate["real_query_fidelity_included_counts"]
        ),
        "deficits_match_v4_5_1": runtime_candidate_gate["deficits"] == v451_candidate_gate["deficits"],
        "candidate_intake_passed_matches_v4_5_1": (
            runtime_candidate_gate["passed"] == v451_candidate_gate["passed"]
        ),
        "source_identity_audit_passed_matches_v4_5_2": (
            runtime_audit_gate["passed"] == v452_audit_gate["passed"]
        ),
        "source_identity_collision_count_matches": (
            runtime_audit_gate["collision_count"] == v452_audit_gate["source_identity_collision_count"]
        ),
        "runtime_candidate_gate_matches_v4_5_2_source_gate": (
            runtime_candidate_like_gate == v452_candidate_like_gate
        ),
        "v4_5_1_comparison_applicable": compare_v4_5_1,
    }
    if not compare_v4_5_1:
        parity_checks.update(
            {
                "candidate_counts_match_v4_5_1": True,
                "query_counts_match_v4_5_1": True,
                "deficits_match_v4_5_1": True,
                "candidate_intake_passed_matches_v4_5_1": True,
            }
        )
    parity_checks["all_passed"] = all(
        bool(value)
        for key, value in parity_checks.items()
        if key != "v4_5_1_comparison_applicable"
    )
    return {
        "schema_version": f"{RUN_ID}_parity_probe_v1",
        "probe_id": probe_id,
        "candidate_row_count": len(candidate_rows),
        "prior_identity_hash_record_count": len(prior_identity_hash_records),
        "raw_candidate_rows_embedded": False,
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
        "source_identity_hash_algorithm": SOURCE_IDENTITY_HASH_ALGORITHM,
        "runtime_candidate_intake_gate": runtime_candidate_gate,
        "runtime_source_identity_audit_gate": runtime_audit_gate,
        "v4_5_1_candidate_intake_gate": v451_candidate_gate,
        "v4_5_2_source_identity_audit_gate": v452_audit_gate,
        "runtime_hash_samples": _runtime_hash_sample(runtime_validation),
        "parity_checks": parity_checks,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_runtime_gate_parity() -> dict[str, Any]:
    sufficient_probe = build_parity_probe(
        probe_id="target_sufficient_no_collision",
        candidate_rows=_target_sufficient_probe_rows(),
        prior_identity_hash_records=[_hash_record("PDF", "unrelated-prior-baseline-doc")],
        compare_v4_5_1=True,
    )
    collision_probe = build_parity_probe(
        probe_id="prior_hash_collision_fail_closed",
        candidate_rows=_prior_collision_probe_rows(),
        prior_identity_hash_records=[_hash_record("PDF", "collision-doc")],
        compare_v4_5_1=False,
    )
    probes = {
        "target_sufficient_no_collision": sufficient_probe,
        "prior_hash_collision_fail_closed": collision_probe,
    }
    all_passed = all(probe["parity_checks"]["all_passed"] for probe in probes.values())
    return {
        "schema_version": f"{RUN_ID}_runtime_gate_parity_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "holdout_candidate_runtime_gate_parity_bridge_only": True,
        "probe_case_count": len(probes),
        "probe_cases": probes,
        "all_parity_checks_passed": all_passed,
        "runtime_candidate_intake_gate_matches_v4_5_1": bool(
            sufficient_probe["parity_checks"]["candidate_intake_passed_matches_v4_5_1"]
            and sufficient_probe["parity_checks"]["candidate_counts_match_v4_5_1"]
            and sufficient_probe["parity_checks"]["query_counts_match_v4_5_1"]
            and sufficient_probe["parity_checks"]["deficits_match_v4_5_1"]
        ),
        "runtime_source_identity_audit_gate_matches_v4_5_2": all(
            probe["parity_checks"]["source_identity_audit_passed_matches_v4_5_2"]
            for probe in probes.values()
        ),
        "runtime_prior_hash_collision_matches_v4_5_2": all(
            probe["parity_checks"]["source_identity_collision_count_matches"]
            for probe in probes.values()
        ),
        "source_identity_hash_algorithm": SOURCE_IDENTITY_HASH_ALGORITHM,
        "raw_candidate_rows_embedded": False,
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
        "candidate_manifest_exported": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def _source_report_input(name: str, report_path: Path, report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_report_name": name,
        "source_report_json": repo_relative(report_path),
        "source_report_exists": report_path.exists(),
        "source_report_sha256": sha256_file(report_path) if report_path.exists() else "",
        "source_run_id": clean(report.get("run_id")),
        "source_report_diagnostic_only": bool(report.get("diagnostic_only", True)),
        "source_report_boundary_flags_clean": (
            int(report.get("official_metric_input_rows") or 0) == 0
            and report.get("promotion_evidence") is False
            and report.get("product_success_evidence_allowed") is False
        ),
        "official_metric_input_rows": int(report.get("official_metric_input_rows") or 0),
        "promotion_evidence": bool(report.get("promotion_evidence")),
        "product_success_evidence_allowed": bool(report.get("product_success_evidence_allowed")),
    }


def build_source_report_inputs() -> dict[str, dict[str, Any]]:
    inputs = {
        "v4_5_1": _source_report_input("v4_5_1", v451.REPORT_JSON, v451.load_v4_5_report()),
        "v4_5_2": _source_report_input("v4_5_2", v452.REPORT_JSON, v452.build_artifacts()["report"]),
        "v4_5_3": _source_report_input("v4_5_3", v453.REPORT_JSON, v453.build_artifacts()["report"]),
        "v4_6_6": _source_report_input("v4_6_6", v466.REPORT_JSON, v466.build_artifacts()["report"]),
    }
    if v451.REPORT_JSON.exists():
        inputs["v4_5_1"] = _source_report_input("v4_5_1", v451.REPORT_JSON, read_json(v451.REPORT_JSON))
    if v452.REPORT_JSON.exists():
        inputs["v4_5_2"] = _source_report_input("v4_5_2", v452.REPORT_JSON, read_json(v452.REPORT_JSON))
    if v453.REPORT_JSON.exists():
        inputs["v4_5_3"] = _source_report_input("v4_5_3", v453.REPORT_JSON, read_json(v453.REPORT_JSON))
    if v466.REPORT_JSON.exists():
        inputs["v4_6_6"] = _source_report_input("v4_6_6", v466.REPORT_JSON, read_json(v466.REPORT_JSON))
    return inputs


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
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
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
        "source_atom_registry_mutated": False,
        "db_or_production_namespace_written": False,
        "protected_namespaces_touched": [],
        "source_atom_evidence_bundle_evidence_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_query_matching_used": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "review_csv_created": False,
        "single_report_artifact_contract": True,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_metrics(parity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "holdout_candidate_runtime_gate_parity_bridge_only": True,
        "runtime_parity_probe_only": True,
        "probe_case_count": int(parity["probe_case_count"]),
        "all_parity_checks_passed": bool(parity["all_parity_checks_passed"]),
        "runtime_candidate_intake_gate_matches_v4_5_1": bool(
            parity["runtime_candidate_intake_gate_matches_v4_5_1"]
        ),
        "runtime_source_identity_audit_gate_matches_v4_5_2": bool(
            parity["runtime_source_identity_audit_gate_matches_v4_5_2"]
        ),
        "runtime_prior_hash_collision_matches_v4_5_2": bool(
            parity["runtime_prior_hash_collision_matches_v4_5_2"]
        ),
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
        "fine_tuning_dataset_exports_created": 0,
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
    parity: Mapping[str, Any],
    metrics: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    source_report_inputs: Mapping[str, Mapping[str, Any]],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    blocked_reasons = [
        "real_external_holdout_candidates_not_registered",
        "candidate_manifest_export_remains_closed",
        "dry_run_input_manifest_not_exported",
        "ft_route_policy_dry_run_not_opened",
        "v4_7_official_metric_gate_not_opened",
        "user_owned_gold_qrels_denominator_policy_pending",
    ]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "diagnostic_only": True,
        "production_routing": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "holdout_candidate_runtime_gate_parity_bridge_only": True,
        "runtime_parity_probe_only": True,
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
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_llm_response_payload_created": False,
        "user_owned_policy_gate_ready": False,
        "readiness_decision": "blocked_pending_real_external_holdout_candidates_and_user_policy",
        "blocked_reasons": blocked_reasons,
        "runtime_gate_parity": dict(parity),
        "metrics": dict(metrics),
        "guardrails": dict(guardrails),
        "guardrail_audit": dict(guardrails),
        "source_report_inputs": {key: dict(value) for key, value in source_report_inputs.items()},
        "artifact_paths": dict(artifact_paths),
        "summary": {
            **dict(metrics),
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "event_type": EVENT_TYPE,
            "status": STATUS,
            "v4_name": V4_NAME,
            "run_family": V4_RUN_FAMILY,
            "readiness_decision": "blocked_pending_real_external_holdout_candidates_and_user_policy",
            "blocked_reasons": blocked_reasons,
            "artifact_paths": dict(artifact_paths),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
        },
        "single_report_artifact_contract": True,
        "review_csv_created": False,
        "human_review_required": False,
        "verification": {
            "schema_version": f"{RUN_ID}_verification_v1",
            "run_id": RUN_ID,
            "commands_required_by_goal": [
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py --check",
                "targeted v4_6_7 runtime gate parity bridge tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_6_7 because this slice validates deterministic in-memory "
                "runtime/script gate parity only; future FT-A training, embedding, index, or LLM workloads should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "The parity probes are synthetic in-memory contract checks and are not real external holdout candidates.",
            "No external source-document-disjoint PDF candidate manifest is registered.",
            "No external workbook-disjoint XLSX candidate manifest is registered.",
            "User-owned gold/qrels/denominator and promotion policy remains closed.",
            "v4_6 FT-A dry run, dry-run input manifest export, dataset export, job creation, and v4_7 remain unopened.",
        ],
        "next_recommendation": (
            "Acquire or register real source-disjoint PDF/XLSX external candidate rows, run v4_5_1 and v4_5_2, "
            "then rerun v4_6/v4_6_6 before any FT-A dry-run manifest or training lane opens."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    parity = build_runtime_gate_parity()
    metrics = build_metrics(parity)
    guardrails = build_guardrails()
    source_report_inputs = build_source_report_inputs()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        parity=parity,
        metrics=metrics,
        guardrails=guardrails,
        source_report_inputs=source_report_inputs,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "runtime_gate_parity": parity,
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
        raise RuntimeError(f"unexpected v4_6_7 primary artifacts: {unexpected}")


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
    report["metrics"] = dict(report["metrics"])
    report["metrics"]["single_report_artifact_contract"] = True
    report["metrics"]["sidecar_primary_artifacts_suppressed"] = True
    report["metrics"]["review_csv_created"] = False
    report["review_csv_created"] = False
    report["human_review_required"] = False
    report["candidate_manifest_exported"] = False
    report["candidate_manifest_jsonl_created"] = False
    report["candidate_validation_jsonl_created"] = False
    report["source_identity_audit_jsonl_created"] = False
    report["dry_run_execution_plan_exported"] = False
    report["dry_run_input_manifest_exported"] = False
    report["fine_tuning_dataset_export_created"] = False
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
        "summary_json_created": False,
        "per_run_markdown_created": False,
        "review_csv_created": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
        "runtime_gate_parity": dict(report["runtime_gate_parity"]),
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
    tag_by_path = {
        PROGRESS_DOC: "progress-entry",
        MEASUREMENTS_DOC: "measurements-entry",
        TRIAGE_DOC: "triage-entry",
    }
    tag = tag_by_path.get(path, "entry")
    block = (
        f"<!-- {marker}:{tag}:start -->\n"
        f"{entry.rstrip()}\n"
        f"<!-- {marker}:{tag}:end -->\n"
    )
    text = path.read_text(encoding="utf-8")
    pattern = rf"<!-- {re.escape(marker)}:{re.escape(tag)}:start -->.*?<!-- {re.escape(marker)}:{re.escape(tag)}:end -->\n?"
    if re.search(pattern, text, flags=re.DOTALL):
        text = re.sub(pattern, block, text, count=1, flags=re.DOTALL)
    else:
        if path == PROGRESS_DOC:
            progress_anchor = (
                "failure attribution, response audit, or per-run Markdown outputs are reserved\n"
                "for behavior-changing runs or explicit forensic evidence requirements.\n"
            )
            anchor_index = text.find(progress_anchor)
            if anchor_index != -1:
                insertion_index = anchor_index + len(progress_anchor)
                text = text[:insertion_index] + "\n" + block + text[insertion_index:].lstrip("\n")
            else:
                text = block + text
        else:
            text = block + text
    path.write_text(text, encoding="utf-8")


def _refresh_docs() -> None:
    return None


def update_readme() -> None:
    text = README.read_text(encoding="utf-8")
    current_status = f"{EVENT_TYPE}_ready"
    text = re.sub(
        r"Current RAG status: `[^`]+`\.",
        f"Current RAG status: `{current_status}`.",
        text,
        count=1,
    )
    verify_block = (
        "```powershell\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py\n"
        "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py\n"
        "python -X utf8 -m py_compile "
        "ai\\scripts\\rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_5_finetune_readiness_packet_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_ft_route_policy_dry_run_preflight_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py --check\n"
        "python -X utf8 -m pytest ai/tests --rag-current -q\n"
        "```"
    )
    verify_start = text.index("## How To Verify Locally")
    verify_end = text.index("## Repo Map")
    verify_section = text[verify_start:verify_end]
    verify_section = re.sub(
        r"```powershell\n.*?```",
        lambda _match: verify_block,
        verify_section,
        count=1,
        flags=re.DOTALL,
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
        r"v4_6_6 is `diagnostic_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod_ready`"
        r"(?:; v4_6_7 is `[^`]+`)?\.",
        f"v4_6_6 is `{v466.EVENT_TYPE}_ready`; v4_6_7 is `{current_status}`.",
        text,
        count=1,
    )
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod.py` | "
        "Compares the default-disabled FastAPI holdout-candidate validator against v4_5_1/v4_5_2 script gates with in-memory hash-only probes; no manifest, sidecar, dataset, job, checkpoint, dry-run, prompt, raw LLM response, official metric, promotion, or product-success evidence is emitted. |"
    )
    pattern = r"\| `rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod\.py` \| .*?\|"
    if re.search(pattern, text):
        text = re.sub(pattern, row, text, count=1)
    elif "| `rag_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod.py` |" in text:
        text = text.replace(
            "\n<!-- v4_diagnostic_runtime_locator_and_finetune_readiness_inventory:end -->",
            f"\n{row}\n<!-- v4_diagnostic_runtime_locator_and_finetune_readiness_inventory:end -->",
            1,
        )
    else:
        text = text.rstrip() + "\n" + row + "\n"
    scripts_readme.write_text(text, encoding="utf-8")


def update_progress_doc() -> None:
    _refresh_docs()
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    current_status = f"{EVENT_TYPE}_ready"
    marker = RUN_ID
    entry = (
        f"- v4_6_7 holdout candidate runtime gate parity bridge (`{RUN_ID}`) is {current_status}. "
        "It compares the default-disabled FastAPI holdout-candidate validation path against the v4_5_1 intake gate "
        "and v4_5_2 source-identity audit gate using in-memory, hash-only parity probes. It proves gate-shape parity "
        "for target-sufficient no-collision rows and fail-closed parity for prior-hash collisions, while treating those "
        "probe rows as synthetic contract checks rather than real external holdout. It does not create or persist a "
        "candidate manifest, validation sidecar, source-identity audit sidecar, dry-run input manifest, dry-run execution "
        "plan, prompt payload, prompt manifest, raw LLM response, dataset, training manifest, job, checkpoint, official "
        "metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim."
    )
    replace_marked_entry(PROGRESS_DOC, marker, entry)
    text = PROGRESS_DOC.read_text(encoding="utf-8")
    text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{current_status}`;",
        text,
        count=1,
    )
    text = re.sub(
        r"(?:current diagnostic v4_6_7 holdout candidate runtime gate parity bridge loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_6 holdout gap and dry-run blocker ledger loop:\n`[^`]+`;",
        "current diagnostic v4_6_7 holdout candidate runtime gate parity bridge loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_6_6 holdout gap and dry-run blocker ledger loop:\n`{v466.RUN_ID}`;",
        text,
        count=1,
    )
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    _refresh_docs()
    metrics = report["metrics"]
    path_text = report["artifact_paths"]["report_json"]
    entry = f"""### v4_6_7 Holdout Candidate Runtime Gate Parity Bridge

- Run: `{RUN_ID}`
- v4 name: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Primary artifact: `{path_text}`
- Source evidence: in-memory parity probes against FastAPI holdout candidate validation, v4_5_1 intake, v4_5_2 source-identity audit, and v4_5_3-compatible prior hash records.
- Interpretation: this is a deterministic contract-parity check only. It is not real external holdout acquisition, not manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| holdout_candidate_runtime_gate_parity_bridge_only | true |
| runtime_parity_probe_only | true |
| probe_case_count | {metrics['probe_case_count']} |
| all_parity_checks_passed | {str(metrics['all_parity_checks_passed']).lower()} |
| runtime_candidate_intake_gate_matches_v4_5_1 | {str(metrics['runtime_candidate_intake_gate_matches_v4_5_1']).lower()} |
| runtime_source_identity_audit_gate_matches_v4_5_2 | {str(metrics['runtime_source_identity_audit_gate_matches_v4_5_2']).lower()} |
| runtime_prior_hash_collision_matches_v4_5_2 | {str(metrics['runtime_prior_hash_collision_matches_v4_5_2']).lower()} |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_execution_plan_exported | false |
| dry_run_input_manifest_exported | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |

Artifact policy: single ignored `report.json`; no runtime parity sidecar, candidate manifest sidecar, validation JSONL, source-identity audit JSONL, dry-run plan/input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, or per-run Markdown is created.
"""
    replace_marked_entry(MEASUREMENTS_DOC, RUN_ID, entry)


def update_triage_doc() -> None:
    _refresh_docs()
    entry = f"""### v4_6_7 Holdout Candidate Runtime Gate Parity Bridge Triage

- Run: `{RUN_ID}`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/{RUN_ID}/report.json`; single-report contract remains active.
- v4_6_7 is diagnostic-only and parity-bridge-only. It compares runtime-adjacent FastAPI holdout validation with v4_5_1/v4_5_2 script gates using in-memory hash-only probes.
- The bridge proves contract consistency only; it is not real holdout availability, not external holdout acquisition, not candidate manifest export, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `real_holdout_sufficient=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.
"""
    replace_marked_entry(TRIAGE_DOC, RUN_ID, entry)


def update_v4_plan() -> None:
    plan_path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    text = plan_path.read_text(encoding="utf-8")
    if "### v4_6_7 — Holdout Candidate Runtime Gate Parity Bridge" not in text:
        insert = """### v4_6_7 — Holdout Candidate Runtime Gate Parity Bridge

This is a diagnostic parity bridge after v4_6_6, not holdout acquisition and not a dry run.

Purpose:

- Compare the default-disabled FastAPI holdout-candidate validator with the v4_5_1 intake gate and v4_5_2 source-identity audit gate.
- Use only in-memory, hash-only parity probes for target-sufficient no-collision rows and prior-hash collision fail-closed rows.
- Keep real external holdout acquisition, manifest export, dry-run input/export, FT-A dry-run execution, dataset export, v4_7, official metric, promotion, product-success, and live-readiness gates closed.

Locked boundary:

```text
holdout_candidate_runtime_gate_parity_bridge_only = true
runtime_parity_probe_only = true
all_parity_checks_passed = true
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
        text = text.replace("### v4_7 — Official Metric Opening Gate", insert + "### v4_7 — Official Metric Opening Gate", 1)
    text = text.replace(
        "v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        "v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod\n↓\nv4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
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


def check_report(report: Mapping[str, Any]) -> None:
    if report["schema_version"] != REPORT_SCHEMA_VERSION:
        raise AssertionError("unexpected report schema")
    if not report["runtime_gate_parity"]["all_parity_checks_passed"]:
        raise AssertionError("runtime gate parity checks must pass")
    if report["official_metric_input_rows"] != 0:
        raise AssertionError("official metric rows must remain zero")
    for field in (
        "promotion_evidence",
        "product_success_evidence_allowed",
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
        "training_job_created",
        "model_or_adapter_checkpoint_written",
        "live_db_index_cache_readiness",
    ):
        if report.get(field):
            raise AssertionError(f"{field} must remain closed")
    if report.get("real_holdout_sufficient"):
        raise AssertionError("parity probes must not be promoted to real holdout sufficiency")


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
                    "holdout_candidate_runtime_gate_parity_bridge_only": True,
                    "all_parity_checks_passed": report["runtime_gate_parity"]["all_parity_checks_passed"],
                    "real_holdout_sufficient": False,
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
