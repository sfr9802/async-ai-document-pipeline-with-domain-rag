from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_5_finetune_readiness_packet_nonprod as v45


ROOT = v45.ROOT
REPORT_DIR = v45.REPORT_DIR
STATUS_JSONL = v45.STATUS_JSONL
PROGRESS_DOC = v45.PROGRESS_DOC
MEASUREMENTS_DOC = v45.MEASUREMENTS_DOC
TRIAGE_DOC = v45.TRIAGE_DOC
README = v45.README
EVAL_README = v45.EVAL_README

AI_ROOT = ROOT / "ai"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.capabilities.rag import holdout_manifest_contract  # noqa: E402

V4_NAME = v45.V4_NAME
V4_RUN_FAMILY = v45.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod"
EVENT_TYPE = "diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod"
STATUS = "DIAGNOSTIC_V4_5_1_HOLDOUT_CANDIDATE_INTAKE_GATE_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_5_1_holdout_candidate_intake_gate_report_v1"
PROTECTED_ORACLE_FIELDS = (
    "expected_answer",
    "expected_answer_text",
    "expected_evidence",
    "gold_locator",
    "gold_supporting_text",
    "supporting_evidence",
    "supporting_evidence_text",
    "target_locator",
)
RAW_LOCAL_PATH_FIELDS = (
    "absolute_path",
    "file_path",
    "local_path",
    "path",
    "raw_file_path",
    "source_path",
)
IDENTITY_RAW_LOCAL_PATH_FIELDS = (
    "candidate_id",
    "document_id",
    "document_version_id",
    "query_id",
    "source_document_id",
    "source_identity",
    "source_workbook_id",
    "workbook_id",
    "workbook_version_id",
)
RAW_LOCATOR_RAW_LOCAL_PATH_FIELDS = (
    "document_id",
    "document_version_id",
    "source_document_id",
    "source_pdf_path",
    "source_xlsx_path",
    "workbook",
)
REQUIRED_COMMON_FIELDS = (
    "candidate_id",
    "query_id",
    "source_family",
    "disjoint_from_prior",
    "query_fidelity_included",
    "real_unseen",
)
FORBIDDEN_READINESS_FLAG_FIELDS = (
    "fine_tuning_dataset_export_created",
    "fine_tuning_executed",
    "fine_tuning_started",
    "model_or_adapter_checkpoint_written",
    "official_metric",
    "product_success_evidence_allowed",
    "production_routing",
    "promotion_evidence",
    "training_job_created",
    "v4_6_ft_dry_run_opened",
)
LOCAL_PATH_RE = re.compile(
    r"^(?:[A-Za-z]:/|//|/(?:data|home|mnt|opt|private|repo|tmp|Users|var|workspace)(?:/|$))",
    re.IGNORECASE,
)
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v45.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
            "candidate_validation.jsonl",
            "holdout_candidate_manifest.jsonl",
            "metrics.json",
            "review_packet.csv",
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


def candidate_manifest_path_label(path: Path | None) -> tuple[str, str]:
    if path is None:
        return "", "not_provided"
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError:
        return "__external_candidate_manifest_path_redacted__", "external_redacted"
    return relative.as_posix(), "repo_relative"


def load_candidate_manifest_rows(path: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path_label, path_kind = candidate_manifest_path_label(path)
    metadata: dict[str, Any] = {
        "schema_version": f"{RUN_ID}_candidate_manifest_input_v1",
        "provided": path is not None,
        "exists": False,
        "format": "jsonl",
        "path_label": path_label,
        "path_kind": path_kind,
        "sha256": "",
        "rows_loaded": 0,
        "load_error": "",
        "raw_local_path_exposed": False,
    }
    if path is None:
        return [], metadata
    if not path.exists():
        metadata["load_error"] = "candidate_manifest_file_missing"
        return [], metadata
    metadata["exists"] = True
    if not path.is_file():
        metadata["load_error"] = "candidate_manifest_path_not_file"
        return [], metadata

    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                metadata["load_error"] = "candidate_manifest_invalid_jsonl"
                metadata["invalid_line_number"] = line_no
                return [], metadata
            if isinstance(row, list):
                metadata["load_error"] = "candidate_manifest_unsupported_format"
                metadata["invalid_line_number"] = line_no
                return [], metadata
            if not isinstance(row, Mapping):
                metadata["load_error"] = "candidate_manifest_row_not_object"
                metadata["invalid_line_number"] = line_no
                return [], metadata
            if ("candidates" in row or "rows" in row) and "source_family" not in row:
                metadata["load_error"] = "candidate_manifest_unsupported_format"
                metadata["invalid_line_number"] = line_no
                return [], metadata
            rows.append(dict(row))

    metadata["sha256"] = sha256_file(path)
    metadata["rows_loaded"] = len(rows)
    return rows, metadata


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v45.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v45.write_jsonl(path, rows)


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def load_v4_5_report() -> dict[str, Any]:
    if v45.REPORT_JSON.exists():
        return read_json(v45.REPORT_JSON)
    return v45.build_artifacts()["report"]


def source_run_references(source_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "previous_gate_run_id": v45.RUN_ID,
        "previous_gate_report_json": repo_relative(v45.REPORT_JSON),
        "previous_gate_report_sha256": sha256_file(v45.REPORT_JSON) if v45.REPORT_JSON.exists() else "",
        "v4_5_report_json": repo_relative(v45.REPORT_JSON),
        "v4_4_report_json": repo_relative(v45.v44.REPORT_JSON),
        "v4_3_report_json": repo_relative(v45.v44.v43.REPORT_JSON),
        "v4_2_report_json": repo_relative(v45.v44.v43.v42.REPORT_JSON),
        "v4_1_report_json": repo_relative(v45.v44.v43.v42.v41.REPORT_JSON),
        "phase1_v3_22_report_json": repo_relative(v45.v44.v43.v42.v41.v322.REPORT_JSON),
        "source_gate_status": clean(source_report.get("status")),
    }


def default_minimum_targets(source_report: Mapping[str, Any]) -> dict[str, int]:
    gates = source_report.get("readiness_gates") or {}
    split = gates.get("split_quality_gate") if isinstance(gates, Mapping) else {}
    metrics = source_report.get("metrics") or {}
    targets = {}
    if isinstance(split, Mapping):
        targets.update(split.get("minimum_targets") or {})
    targets.update(metrics.get("minimum_targets") or {})
    return {
        "pdf_unseen_source_documents": int(targets.get("pdf_unseen_source_documents") or 20),
        "xlsx_unseen_workbooks": int(targets.get("xlsx_unseen_workbooks") or 8),
        "query_fidelity_included_rows_per_family": int(targets.get("query_fidelity_included_rows_per_family") or 100),
    }


def protected_field_names(row: Mapping[str, Any]) -> list[str]:
    return sorted(field for field in PROTECTED_ORACLE_FIELDS if clean(row.get(field)))


def raw_local_path_field_names(row: Mapping[str, Any]) -> list[str]:
    fields: list[str] = []
    for field in RAW_LOCAL_PATH_FIELDS:
        value = clean(row.get(field)).replace("\\", "/")
        if value and LOCAL_PATH_RE.search(value):
            fields.append(field)
    for field in IDENTITY_RAW_LOCAL_PATH_FIELDS:
        value = clean(row.get(field)).replace("\\", "/")
        if value and LOCAL_PATH_RE.search(value):
            fields.append(field)
    raw_locator = _as_mapping(row.get("raw_locator"))
    for field in RAW_LOCATOR_RAW_LOCAL_PATH_FIELDS:
        value = clean(raw_locator.get(field)).replace("\\", "/")
        if value and LOCAL_PATH_RE.search(value):
            fields.append(f"raw_locator.{field}")
    return sorted(fields)


def forbidden_readiness_flag_names(row: Mapping[str, Any]) -> list[str]:
    return sorted(field for field in FORBIDDEN_READINESS_FLAG_FIELDS if bool_value(row.get(field)))


def missing_required_fields(row: Mapping[str, Any]) -> list[str]:
    return [field for field in REQUIRED_COMMON_FIELDS if not field_present(row, field)]


def field_present(row: Mapping[str, Any], field: str) -> bool:
    if field not in row:
        return False
    value = row.get(field)
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def candidate_identity(row: Mapping[str, Any], family: str) -> str:
    return holdout_manifest_contract.source_identity_key(row, family)


def source_identity_field_conflicts(row: Mapping[str, Any], family: str) -> list[str]:
    return holdout_manifest_contract.source_identity_field_conflicts(row, family)


def redact_raw_local_path_value(value: Any) -> Any:
    if isinstance(value, str):
        text = value.replace("\\", "/")
        return "__raw_local_path_redacted__" if text and LOCAL_PATH_RE.search(text) else value
    if isinstance(value, list):
        return [redact_raw_local_path_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_raw_local_path_value(item) for key, item in value.items()}
    return value


def sanitized_candidate_row(row: Mapping[str, Any], *, accepted: bool, reason: str) -> dict[str, Any]:
    family = clean(row.get("source_family")).upper()
    payload = {
        "candidate_id": clean(row.get("candidate_id")) or clean(row.get("source_identity")),
        "query_id": clean(row.get("query_id")),
        "source_family": clean(row.get("source_family")).upper(),
        "source_identity_key": candidate_identity(row, family),
        "source_identity": clean(row.get("source_identity")),
        "source_document_id": clean(row.get("source_document_id")),
        "workbook_id": clean(row.get("workbook_id")),
        "accepted_for_holdout": accepted,
        "exclusion_reason": reason,
        "query_fidelity_included": bool_value(row.get("query_fidelity_included")),
        "disjoint_from_prior": bool_value(row.get("disjoint_from_prior")),
        "leakage_bucket": clean(row.get("leakage_bucket")),
        "protected_oracle_fields_present": protected_field_names(row),
        "raw_local_path_fields_present": raw_local_path_field_names(row),
        "source_identity_field_conflicts": source_identity_field_conflicts(row, family),
        "forbidden_readiness_flags_present": forbidden_readiness_flag_names(row),
        "missing_required_fields": missing_required_fields(row),
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
    }
    payload = redact_raw_local_path_value(payload)
    return {key: value for key, value in payload.items() if value not in ("", [])}


def validate_holdout_candidate_rows(
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    minimum_targets: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    targets = {
        "pdf_unseen_source_documents": int((minimum_targets or {}).get("pdf_unseen_source_documents") or 20),
        "xlsx_unseen_workbooks": int((minimum_targets or {}).get("xlsx_unseen_workbooks") or 8),
        "query_fidelity_included_rows_per_family": int(
            (minimum_targets or {}).get("query_fidelity_included_rows_per_family") or 100
        ),
    }
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    seen_identities: set[tuple[str, str]] = set()
    seen_query_ids: set[tuple[str, str]] = set()

    for raw_row in candidate_rows:
        family = clean(raw_row.get("source_family")).upper()
        identity = candidate_identity(raw_row, family)
        candidate_id = clean(raw_row.get("candidate_id"))
        query_id = clean(raw_row.get("query_id"))
        missing_fields = missing_required_fields(raw_row)
        reason = ""
        duplicate_candidate_id = bool(candidate_id and candidate_id in seen_candidate_ids)
        duplicate_query_id = bool(query_id and (family, query_id) in seen_query_ids)
        if family not in {"PDF", "XLSX", "TEXT"}:
            reason = "unsupported_source_family"
        elif missing_fields:
            reason = "required_fields_missing"
        elif duplicate_candidate_id:
            reason = "duplicate_candidate_id"
        elif duplicate_query_id:
            reason = "duplicate_query_id"
        elif protected_field_names(raw_row):
            reason = "protected_oracle_field_present"
        elif raw_local_path_field_names(raw_row):
            reason = "raw_local_path_present"
        elif source_identity_field_conflicts(raw_row, family):
            reason = "source_identity_field_conflict"
        elif forbidden_readiness_flag_names(raw_row):
            reason = "forbidden_readiness_flag_present"
        elif clean(raw_row.get("leakage_bucket")):
            reason = "leakage_bucket_present"
        elif "real_unseen" in raw_row and not bool_value(raw_row.get("real_unseen")):
            reason = "synthetic_or_not_real_unseen"
        elif not identity:
            reason = "source_identity_missing"
        elif family == "TEXT" and not bool_value(raw_row.get("control_only")):
            reason = "text_family_control_only"
        elif family in {"PDF", "XLSX"} and not bool_value(raw_row.get("disjoint_from_prior")):
            reason = "not_disjoint_from_prior"
        elif not bool_value(raw_row.get("query_fidelity_included")):
            reason = "query_fidelity_not_included"
        elif (family, identity) in seen_identities and not query_id:
            reason = "duplicate_source_identity"

        if candidate_id:
            seen_candidate_ids.add(candidate_id)
        if query_id:
            seen_query_ids.add((family, query_id))

        if reason:
            excluded.append(sanitized_candidate_row(raw_row, accepted=False, reason=reason))
            continue

        seen_identities.add((family, identity))
        accepted.append(sanitized_candidate_row(raw_row, accepted=True, reason=""))

    pdf_count = len({row["source_identity_key"] for row in accepted if row["source_family"] == "PDF"})
    xlsx_count = len({row["source_identity_key"] for row in accepted if row["source_family"] == "XLSX"})
    text_count = len({row["source_identity_key"] for row in accepted if row["source_family"] == "TEXT"})
    pdf_query_count = len(
        {row.get("query_id") or row["candidate_id"] for row in accepted if row["source_family"] == "PDF"}
    )
    xlsx_query_count = len(
        {row.get("query_id") or row["candidate_id"] for row in accepted if row["source_family"] == "XLSX"}
    )
    text_query_count = len(
        {row.get("query_id") or row["candidate_id"] for row in accepted if row["source_family"] == "TEXT"}
    )
    identity_sufficient = pdf_count >= targets["pdf_unseen_source_documents"] and xlsx_count >= targets["xlsx_unseen_workbooks"]
    query_sufficient = (
        pdf_query_count >= targets["query_fidelity_included_rows_per_family"]
        and xlsx_query_count >= targets["query_fidelity_included_rows_per_family"]
    )
    blocked_reasons: list[str] = []
    if not candidate_rows:
        blocked_reasons.append("candidate_manifest_missing")
    if not identity_sufficient:
        blocked_reasons.append("real_disjoint_holdout_candidates_below_target")
    if not query_sufficient:
        blocked_reasons.append("real_query_fidelity_candidates_below_target")
    if excluded:
        blocked_reasons.append("candidate_rows_excluded")
    gate_passed = bool(candidate_rows) and identity_sufficient and query_sufficient and not excluded
    return {
        "schema_version": f"{RUN_ID}_candidate_validation_v1",
        "run_id": RUN_ID,
        "candidate_intake_schema_ready": True,
        "candidate_manifest_present": bool(candidate_rows),
        "candidate_manifest_rows": len(candidate_rows),
        "accepted_candidates": accepted,
        "excluded_candidates": excluded,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "candidate_intake_gate": {
            "schema_version": f"{RUN_ID}_candidate_intake_gate_v1",
            "run_id": RUN_ID,
            "passed": gate_passed,
            "candidate_manifest_present": bool(candidate_rows),
            "candidate_manifest_rows": len(candidate_rows),
            "accepted_holdout_candidate_counts": {
                "PDF_source_document_disjoint": pdf_count,
                "XLSX_workbook_disjoint": xlsx_count,
                "TEXT_control_only": text_count,
            },
            "real_query_fidelity_included_counts": {
                "PDF": pdf_query_count,
                "XLSX": xlsx_query_count,
                "TEXT": text_query_count,
            },
            "minimum_targets": targets,
            "excluded_candidate_count": len(excluded),
            "blocked_reasons": blocked_reasons,
            "holdout_candidate_manifest_contract_version": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
            ),
            "holdout_candidate_manifest_contract_hash": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
            ),
            "official_metric_input_rows": 0,
            "product_success_evidence_allowed": False,
        },
    }


def build_guardrails(source_report: Mapping[str, Any]) -> dict[str, Any]:
    source_guardrails = dict(source_report.get("guardrails") or {})
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "production_routing": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "candidate_manifest_created": False,
        "candidate_validation_jsonl_created": False,
        "candidate_manifest_jsonl_created": False,
        "holdout_candidate_manifest_written": False,
        "fine_tuning_dataset_export_created": False,
        "training_dataset_exported_for_training": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "v4_6_ft_dry_run_opened": False,
        "prompt_payload_created": False,
        "raw_llm_response_payload_created": False,
        "source_atom_evidence_bundle_evidence_truth": bool(
            source_guardrails.get("source_atom_evidence_bundle_evidence_truth", True)
        ),
        "searchview_vector_payload_candidate_only": bool(
            source_guardrails.get("searchview_vector_payload_candidate_only", True)
        ),
        "vector_payload_used_as_evidence_truth": False,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_query_matching_used": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
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
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def build_metrics(validation: Mapping[str, Any], source_report: Mapping[str, Any]) -> dict[str, Any]:
    gate = validation["candidate_intake_gate"]
    counts = gate["accepted_holdout_candidate_counts"]
    query_counts = gate["real_query_fidelity_included_counts"]
    targets = gate["minimum_targets"]
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "holdout_candidate_intake_only": True,
        "candidate_intake_schema_ready": True,
        "candidate_manifest_present": bool(validation["candidate_manifest_present"]),
        "candidate_manifest_rows": int(validation["candidate_manifest_rows"]),
        "accepted_pdf_holdout_candidates": int(counts["PDF_source_document_disjoint"]),
        "accepted_xlsx_holdout_candidates": int(counts["XLSX_workbook_disjoint"]),
        "accepted_text_control_candidates": int(counts["TEXT_control_only"]),
        "excluded_holdout_candidate_count": int(gate["excluded_candidate_count"]),
        "candidate_intake_gate_passed": bool(gate["passed"]),
        "split_quality_gate_passed": bool(gate["passed"]),
        "readiness_gate_passed": False,
        "v4_6_ft_dry_run_opened": False,
        "fine_tuning_dataset_exports_created": 0,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "minimum_targets": dict(targets),
        "real_unseen_registry_counts": {
            "PDF_source_document_disjoint": int(counts["PDF_source_document_disjoint"]),
            "XLSX_workbook_disjoint": int(counts["XLSX_workbook_disjoint"]),
        },
        "real_query_fidelity_included_counts": dict(query_counts),
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
        "previous_gate_run_id": v45.RUN_ID,
        "previous_gate_readiness_gate_passed": bool((source_report.get("metrics") or {}).get("readiness_gate_passed")),
    }


def build_report(
    *,
    source_report: Mapping[str, Any] | None = None,
    candidate_rows: Sequence[Mapping[str, Any]] | None = None,
    candidate_manifest_path: Path | None = None,
    minimum_targets: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    source = dict(source_report or load_v4_5_report())
    targets = dict(minimum_targets or default_minimum_targets(source))
    manifest_rows, candidate_manifest_input = load_candidate_manifest_rows(candidate_manifest_path)
    rows_for_validation = candidate_rows if candidate_rows is not None else manifest_rows
    validation = validate_holdout_candidate_rows(rows_for_validation or (), minimum_targets=targets)
    metrics = build_metrics(validation, source)
    guardrails = build_guardrails(source)
    gate = dict(validation["candidate_intake_gate"])
    gate_blocked_reasons = list(gate["blocked_reasons"])
    if candidate_manifest_input["load_error"] and candidate_manifest_input["load_error"] not in gate_blocked_reasons:
        gate_blocked_reasons.insert(0, str(candidate_manifest_input["load_error"]))
    gate["blocked_reasons"] = gate_blocked_reasons
    blocked_reasons = list(gate_blocked_reasons)
    if "user_owned_gold_qrels_denominator_policy_pending" not in blocked_reasons:
        blocked_reasons.append("user_owned_gold_qrels_denominator_policy_pending")
    readiness_decision = (
        "blocked_pending_user_owned_gold_qrels_denominator_policy"
        if gate["passed"]
        else "blocked_pending_holdout_candidate_manifest_and_user_policy"
    )
    report = {
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
        "holdout_candidate_intake_only": True,
        "candidate_intake_schema_ready": True,
        "holdout_candidate_manifest_contract_version": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
        ),
        "holdout_candidate_manifest_contract_hash_algorithm": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH_ALGORITHM
        ),
        "holdout_candidate_manifest_contract_hash": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
        ),
        "holdout_candidate_manifest_contract": holdout_manifest_contract.build_holdout_candidate_manifest_contract(),
        "candidate_manifest_present": bool(validation["candidate_manifest_present"]),
        "candidate_manifest_rows": int(validation["candidate_manifest_rows"]),
        "candidate_manifest_input": candidate_manifest_input,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "single_report_artifact_contract": True,
        "review_csv_created": False,
        "human_review_required": False,
        "v4_6_ft_dry_run_opened": False,
        "fine_tuning_dataset_export_created": False,
        "training_dataset_exported_for_training": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "readiness_decision": readiness_decision,
        "blocked_reasons": blocked_reasons,
        "candidate_intake_gate": gate,
        "accepted_candidates": list(validation["accepted_candidates"]),
        "excluded_candidates": list(validation["excluded_candidates"]),
        "metrics": metrics,
        "guardrails": guardrails,
        "source_run_references": source_run_references(source),
        "artifact_paths": {"report_json": repo_relative(REPORT_JSON)},
        "summary": {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "event_type": EVENT_TYPE,
            "status": STATUS,
            "v4_name": V4_NAME,
            "run_family": V4_RUN_FAMILY,
            "diagnostic_only": True,
            "holdout_candidate_intake_only": True,
            "candidate_intake_schema_ready": True,
            "holdout_candidate_manifest_contract_version": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
            ),
            "holdout_candidate_manifest_contract_hash": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
            ),
            "candidate_manifest_present": bool(validation["candidate_manifest_present"]),
            "candidate_manifest_rows": int(validation["candidate_manifest_rows"]),
            "candidate_intake_gate_passed": bool(gate["passed"]),
            "candidate_manifest_input": candidate_manifest_input,
            "readiness_decision": readiness_decision,
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
            "candidate_manifest_jsonl_created": False,
            "candidate_validation_jsonl_created": False,
            "fine_tuning_dataset_export_created": False,
            "training_job_created": False,
            "model_or_adapter_checkpoint_written": False,
            "v4_6_ft_dry_run_opened": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_db_index_cache_readiness": False,
        },
        "verification": {
            "schema_version": f"{RUN_ID}_verification_v1",
            "run_id": RUN_ID,
            "commands": [
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py --check",
                "targeted v4_5_1 holdout candidate intake tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_5_1 because this slice validates candidate intake contracts only; "
                "future training or large embedding/LLM/index work should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "No repo-local real holdout candidate manifest is present.",
            "Real source-document-disjoint PDF and workbook-disjoint XLSX holdout counts remain below target.",
            "User-owned gold/qrels/denominator/promotion policy remains closed.",
            "v4_6 FT-A dry run remains unopened.",
        ],
        "next_recommendation": (
            "Acquire or register real source-disjoint PDF/XLSX candidate identities, run this intake gate, "
            "and keep all fine-tuning dataset exports closed until candidate and user-owned policy gates pass."
        ),
    }
    return report


def build_artifacts(
    *,
    source_report: Mapping[str, Any] | None = None,
    candidate_rows: Sequence[Mapping[str, Any]] | None = None,
    candidate_manifest_path: Path | None = None,
    minimum_targets: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    report = build_report(
        source_report=source_report,
        candidate_rows=candidate_rows,
        candidate_manifest_path=candidate_manifest_path,
        minimum_targets=minimum_targets,
    )
    return {
        "report": report,
        "metrics": report["metrics"],
        "guardrails": report["guardrails"],
        "candidate_intake_gate": report["candidate_intake_gate"],
    }


def remove_stale_sidecar_artifacts(target_dir: Path) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()


def assert_single_report_directory(target_dir: Path) -> None:
    unexpected = sorted(path.name for path in target_dir.iterdir() if path.name != "report.json")
    if unexpected:
        raise RuntimeError(f"unexpected v4_5_1 primary artifacts: {unexpected}")


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
    report["summary"]["candidate_manifest_jsonl_created"] = False
    report["summary"]["candidate_validation_jsonl_created"] = False
    report["metrics"] = dict(report["metrics"])
    report["metrics"]["single_report_artifact_contract"] = True
    report["metrics"]["sidecar_primary_artifacts_suppressed"] = True
    report["metrics"]["review_csv_created"] = False
    report["review_csv_created"] = False
    report["human_review_required"] = False
    report["candidate_manifest_jsonl_created"] = False
    report["candidate_validation_jsonl_created"] = False
    report["fine_tuning_dataset_export_created"] = False
    remove_stale_sidecar_artifacts(target_dir)
    assert_single_report_directory(target_dir)
    write_json(report_path, report)
    assert_single_report_directory(target_dir)
    return report


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v45.replace_marked_entry(path, marker, entry)


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_5_1 holdout candidate intake gate loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_5 fine-tuning readiness packet loop:\n`[^`]+`;",
        "current diagnostic v4_5_1 holdout candidate intake gate loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_5 fine-tuning readiness packet loop:\n`{v45.RUN_ID}`;",
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
        "ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py --check\n"
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
    README.write_text(readme_text[:verify_start] + verify_section + readme_text[verify_end:], encoding="utf-8")

    eval_readme_text = EVAL_README.read_text(encoding="utf-8")
    eval_readme_text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{EVENT_TYPE}_ready`",
        eval_readme_text,
        count=1,
    )
    eval_readme_text = eval_readme_text.replace(
        f"v4_5 is `{v45.EVENT_TYPE}_ready`.",
        f"v4_5 is `{v45.EVENT_TYPE}_ready`; v4_5_1 is `{EVENT_TYPE}_ready`.",
    )
    EVAL_README.write_text(eval_readme_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    marker = "v4_diagnostic_runtime_locator_and_finetune_readiness_inventory"
    entry = f"""## v4 RAG Diagnostic Runtime/Locator/Fine-Tuning Readiness Inventory

| Script | Role |
|---|---|
| `rag_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod.py` | Persists the v3_22 XLSX display metadata contract into SourceAtom-owned runtime-adjacent fields. |
| `rag_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod.py` | Packages family-separated XLSX table/range/cell locator diagnostics from seen-reference v3 surfaces. |
| `rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py` | Keeps PDF file identity confidence separate from answer-ready evidence-window diagnostics. |
| `rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py` | Materializes real blind/OOD holdout and leakage-audit infrastructure while fail-closing on unavailable source-disjoint holdout. |
| `rag_v4_5_finetune_readiness_packet_nonprod.py` | Builds the fine-tuning-readiness-only packet after v4_4 gates; no dataset export, training job, checkpoint, official metric, promotion, or product-success evidence is emitted. |
| `rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py` | Validates optional external real holdout candidate manifest input before any v4_6 FT dry run; the manifest is read as input only, raw external paths are redacted, and no candidate sidecar, training dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |

v4 scripts remain diagnostic/non-production and write one ignored `report.json`
per run. Actual fine-tuning remains closed until real disjoint splits and
user-owned gold/qrels/denominator policy exist.
"""
    replace_marked_entry(scripts_readme, marker, entry)


def update_v4_plan_note() -> None:
    plan_path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    if not plan_path.exists():
        return
    text = plan_path.read_text(encoding="utf-8")
    marker = "### v4_5_1 — Holdout Candidate Intake Gate"
    entry = """### v4_5_1 — Holdout Candidate Intake Gate

Purpose:

- Add a non-production intake validator for future real PDF/XLSX holdout candidates.
- Accept an optional external candidate manifest path as input only; do not copy it into the run directory or expose raw external paths in `report.json`.
- Keep v4_6 FT-A dry run closed while v4_5 gates remain blocked.
- Validate source-family identity, source/workbook disjointness, query-fidelity inclusion, leakage-bucket exclusion, protected oracle-field absence, and raw local path absence before any training export.

Success criteria:

```text
candidate_intake_schema_ready = true
candidate_manifest_present = true only when user/repo-owned candidate rows exist
candidate_manifest_input_path_kind = repo_relative or external_redacted
accepted PDF/XLSX disjoint candidates meet v4_4 targets
leakage buckets are excluded
official_metric_input_rows = 0
v4_6_ft_dry_run_opened = false unless v4_5 and candidate gates pass
```

"""
    if marker not in text:
        text = text.replace("### v4_6 — FT Route Policy Dry-Run Preflight", entry + "### v4_6 — FT Route Policy Dry-Run Preflight", 1)
    text = text.replace(
        "v4_5_finetune_readiness_packet\n↓\nv4_6_optional_ft_route_policy_dry_run_nonprod",
        "v4_5_finetune_readiness_packet\n↓\nv4_5_1_holdout_candidate_intake_gate_nonprod\n↓\nv4_6_optional_ft_route_policy_dry_run_nonprod",
    )
    plan_path.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    report_path = report["artifact_paths"]["report_json"]
    metrics = report["metrics"]
    gate = report["candidate_intake_gate"]
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v45.v44.v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)
    progress_entry = (
        f"- v4_5_1 holdout candidate intake gate (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It adds a runtime-adjacent, source-family-separated intake validator for future real PDF/XLSX holdout candidates, "
        "including optional external manifest input with raw external path redaction, "
        f"and writes one `report.json` at `{report_path}`. The current repo has no holdout candidate manifest, so accepted "
        "PDF/XLSX candidates remain 0 and v4_6 FT-A dry run stays closed. Boundary: diagnostic-only, non-production, "
        "not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, "
        "no candidate sidecar, no fine-tuning dataset export, no training job, and no checkpoint."
    )
    measurements_entry = f"""### v4_5_1 Holdout Candidate Intake Gate

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, holdout-candidate-intake only, single `report.json`.
- Candidate manifest input: optional external manifest path is input-only; raw external paths are redacted in reports/status.
- Primary artifact: `{report_path}`
- Source evidence: v4_5 fine-tuning-readiness packet plus v4_4 holdout/leakage gates.

| Diagnostic count | Value |
| --- | ---: |
| candidate_intake_schema_ready | true |
| candidate_manifest_input_provided | {str(report["candidate_manifest_input"]["provided"]).lower()} |
| candidate_manifest_input_path_kind | {report["candidate_manifest_input"]["path_kind"]} |
| candidate_manifest_present | {str(metrics["candidate_manifest_present"]).lower()} |
| candidate_manifest_rows | {metrics["candidate_manifest_rows"]} |
| candidate_intake_gate_passed | {str(metrics["candidate_intake_gate_passed"]).lower()} |
| accepted_pdf_holdout_candidates | {metrics["accepted_pdf_holdout_candidates"]}/{metrics["minimum_targets"]["pdf_unseen_source_documents"]} |
| accepted_xlsx_holdout_candidates | {metrics["accepted_xlsx_holdout_candidates"]}/{metrics["minimum_targets"]["xlsx_unseen_workbooks"]} |
| real_query_fidelity_included_rows_per_family | {gate["real_query_fidelity_included_counts"]["PDF"]}/{metrics["minimum_targets"]["query_fidelity_included_rows_per_family"]} PDF, {gate["real_query_fidelity_included_counts"]["XLSX"]}/{metrics["minimum_targets"]["query_fidelity_included_rows_per_family"]} XLSX |
| excluded_holdout_candidate_count | {metrics["excluded_holdout_candidate_count"]} |
| v4_6_ft_dry_run_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds candidate_manifest_input, candidate_intake_gate, accepted/excluded sanitized candidate rows, metrics, guardrails, source lineage, verification, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no candidate manifest sidecar, validation JSONL, review CSV, training manifest, dataset sidecar, checkpoint, or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_5_1 Holdout Candidate Intake Gate Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_5_1 is a diagnostic holdout-candidate intake gate, not a v4_6 fine-tuning dry run.\n"
        "- Optional candidate manifest paths are read as input only; external paths are redacted and the manifest is not copied into the run directory.\n"
        "- Current candidate manifest is absent, so accepted PDF source-document-disjoint and XLSX workbook-disjoint candidates remain below target.\n"
        "- Candidate rows are allowed only when source family, source/workbook identity, disjointness, query-fidelity inclusion, leakage exclusion, protected oracle-field absence, and raw local path absence are satisfied.\n"
        "- Protected target/gold/expected/supporting fields are rejected as candidate input, not silently used.\n"
        "- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy; user-owned label/qrels/denominator policy stays closed.\n"
        "- GPU is not required for this deterministic intake validator; future training, embedding, or LLM/index workloads should use GPU when opened.\n"
        "- Next lane: provide real source-disjoint PDF/XLSX candidate rows, then rerun the intake gate before opening any v4_6 FT-A dry run.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    update_scripts_readme()
    update_v4_plan_note()
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v45.v44.v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)


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
        "candidate_manifest_input": dict(report["candidate_manifest_input"]),
        "report_json_created": True,
        "review_csv_created": False,
        "summary_json_created": False,
        "per_run_markdown_created": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "raw_llm_response_payload_created": False,
        "prompt_payload_created": False,
        "training_manifest_jsonl_created": False,
        "fine_tuning_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
        "candidate_intake_gate": dict(report["candidate_intake_gate"]),
        "readiness_decision": report["readiness_decision"],
        "blocked_reasons": list(report["blocked_reasons"]),
        "schema_version": f"{RUN_ID}_status_event_v1",
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def run_write(*, candidate_manifest_path: Path | None = None) -> dict[str, Any]:
    artifacts = build_artifacts(candidate_manifest_path=candidate_manifest_path)
    report = write_artifacts(artifacts)
    update_docs(report)
    append_status_event(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--candidate-manifest", "--manifest-file", dest="candidate_manifest", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.check:
        artifacts = build_artifacts(candidate_manifest_path=args.candidate_manifest)
        metrics = artifacts["metrics"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["report"]["summary"]["status"],
                    "candidate_intake_gate_passed": metrics["candidate_intake_gate_passed"],
                    "candidate_manifest_present": metrics["candidate_manifest_present"],
                    "candidate_manifest_rows": metrics["candidate_manifest_rows"],
                    "candidate_manifest_input_provided": artifacts["report"]["candidate_manifest_input"]["provided"],
                    "candidate_manifest_load_error": artifacts["report"]["candidate_manifest_input"]["load_error"],
                    "accepted_pdf_holdout_candidates": metrics["accepted_pdf_holdout_candidates"],
                    "accepted_xlsx_holdout_candidates": metrics["accepted_xlsx_holdout_candidates"],
                    "v4_6_ft_dry_run_opened": metrics["v4_6_ft_dry_run_opened"],
                    "fine_tuning_dataset_exports_created": metrics["fine_tuning_dataset_exports_created"],
                    "official_metric_input_rows": metrics["official_metric_input_rows"],
                    "gpu_required_for_this_slice": metrics["gpu_required_for_this_slice"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    report = run_write(candidate_manifest_path=args.candidate_manifest)
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
