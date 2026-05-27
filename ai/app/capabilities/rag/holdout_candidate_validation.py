"""In-memory v4 holdout candidate manifest validation.

The validator is intentionally input-only: it accepts caller-provided candidate
rows, returns sanitized/hash-only diagnostics, and never writes manifests,
datasets, prompts, jobs, checkpoints, or metric rows.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from app.capabilities.rag.holdout_manifest_contract import (
    HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH,
    HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH_ALGORITHM,
    HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION,
    MINIMUM_TARGETS,
    SOURCE_FAMILIES,
    V4_READINESS_NAME,
    V4_READINESS_RUN_FAMILY,
    build_holdout_candidate_manifest_contract,
    source_identity_field_conflicts,
    source_identity_key,
    source_identity_scope,
)

RAW_LOCAL_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|//|/(?:data|home|mnt|opt|private|repo|tmp|Users|var|workspace)(?:/|$))",
    re.IGNORECASE,
)
RAW_LOCAL_PATH_REDACTION = "__raw_local_path_redacted__"
SOURCE_IDENTITY_HASH_ALGORITHM = "sha256(family:identity_key)"
CANDIDATE_ID_HASH_ALGORITHM = "sha256(candidate_id)"
QUERY_ID_HASH_ALGORITHM = "sha256(query_id)"
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_COMMON_FIELDS = (
    "candidate_id",
    "query_id",
    "source_family",
    "disjoint_from_prior",
    "query_fidelity_included",
    "real_unseen",
)
PROTECTED_ORACLE_FIELDS = (
    "expected_answer",
    "expected_answer_text",
    "expected_evidence",
    "gold_answer",
    "gold_locator",
    "gold_supporting_text",
    "supporting_evidence",
    "supporting_evidence_text",
    "target_locator",
)
FORBIDDEN_CONTRACT_FIELDS = (
    "official_metric",
    "official_metric_input_rows",
    "promotion_evidence",
    "product_success_evidence_allowed",
)
FORBIDDEN_PROMPT_OR_LLM_FIELDS = (
    "full_prompt",
    "llm_response",
    "prompt",
    "prompt_payload",
    "prompt_text",
    "raw_llm_request",
    "raw_llm_response",
    "raw_prompt",
)
FORBIDDEN_READINESS_FLAG_FIELDS = (
    "candidate_manifest_exported",
    "candidate_manifest_jsonl_created",
    "candidate_validation_jsonl_created",
    "db_or_production_namespace_written",
    "dry_run_execution_plan_exported",
    "dry_run_input_manifest_exported",
    "fine_tuning_dataset_export_created",
    "fine_tuning_dataset_exports_created",
    "fine_tuning_executed",
    "fine_tuning_started",
    "ft_route_policy_dry_run_executed",
    "ft_route_policy_dry_run_opened",
    "live_db_index_cache_readiness",
    "model_or_adapter_checkpoint_written",
    "production_mutation",
    "production_routing",
    "source_identity_audit_jsonl_created",
    "training_job_created",
    "training_manifest_jsonl_created",
    "v4_7_official_metric_gate_opened",
)
FORBIDDEN_OPERATIONAL_FIELD_NAMES = (
    "adapter_path",
    "artifact_path",
    "cache_namespace",
    "candidate_manifest_path",
    "candidate_validation_path",
    "checkpoint_dir",
    "checkpoint_path",
    "dataset_output_path",
    "db_namespace",
    "dry_run_execution_plan_path",
    "dry_run_input_manifest_path",
    "fine_tuning_dataset_path",
    "index_namespace",
    "job_id",
    "job_name",
    "manifest_path",
    "model_output_path",
    "model_path",
    "namespace",
    "output_dir",
    "output_file",
    "output_path",
    "prior_identity_ledger_path",
    "production_namespace",
    "raw_prior_ledger_path",
    "report_path",
    "review_packet_path",
    "search_index_namespace",
    "source_identity_audit_path",
    "training_manifest_path",
)


def validate_holdout_candidate_rows_for_fastapi(
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    prior_identity_hash_records: Sequence[Mapping[str, Any] | str] = (),
) -> dict[str, Any]:
    """Validate candidate rows for the internal diagnostic FastAPI route."""

    prior_hash_audit = _prior_identity_hash_audit(prior_identity_hash_records)
    prior_hashes = prior_hash_audit["hashes"]
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    seen_query_ids: set[tuple[str, str]] = set()
    collision_count = 0

    for raw_row in candidate_rows:
        row = raw_row if isinstance(raw_row, Mapping) else {}
        family = _clean(row.get("source_family")).upper()
        candidate_id = _clean(row.get("candidate_id"))
        query_id = _clean(row.get("query_id"))
        missing_fields = _missing_required_fields(row)
        identity = source_identity_key(row, family) if family in SOURCE_FAMILIES else ""
        scope = source_identity_scope(row, family) if family in SOURCE_FAMILIES else ""
        identity_hash = _source_identity_hash(family, scope, identity) if identity and scope else ""
        reasons: list[str] = []
        duplicate_candidate_id = bool(candidate_id and candidate_id in seen_candidate_ids)
        duplicate_query_id = bool(family and query_id and (family, query_id) in seen_query_ids)

        if family not in SOURCE_FAMILIES:
            reasons.append("unsupported_source_family")
        if missing_fields:
            reasons.append("required_fields_missing")
        if duplicate_candidate_id:
            reasons.append("duplicate_candidate_id")
        if duplicate_query_id:
            reasons.append("duplicate_query_id")
        if candidate_id:
            seen_candidate_ids.add(candidate_id)
        if family and query_id:
            seen_query_ids.add((family, query_id))

        protected_fields = _present_fields(row, PROTECTED_ORACLE_FIELDS)
        forbidden_contract_fields = _present_keys(row, FORBIDDEN_CONTRACT_FIELDS)
        forbidden_prompt_fields = _present_fields(row, FORBIDDEN_PROMPT_OR_LLM_FIELDS)
        forbidden_readiness_flags = _truthy_or_nonzero_fields(row, FORBIDDEN_READINESS_FLAG_FIELDS)
        forbidden_operational_fields = _present_keys(row, FORBIDDEN_OPERATIONAL_FIELD_NAMES)
        raw_local_path_fields = _raw_local_path_fields(row)
        conflicts = source_identity_field_conflicts(row, family) if family in SOURCE_FAMILIES else []

        if protected_fields:
            reasons.append("protected_oracle_fields_present")
        if forbidden_contract_fields:
            reasons.append("forbidden_contract_fields_present")
        if forbidden_prompt_fields:
            reasons.append("forbidden_prompt_or_llm_fields_present")
        if raw_local_path_fields:
            reasons.append("raw_local_path_present")
        if conflicts:
            reasons.append("source_identity_field_conflict")
        if forbidden_readiness_flags:
            reasons.append("forbidden_readiness_flags_present")
        if forbidden_operational_fields:
            reasons.append("forbidden_operational_fields_present")
        if _clean(row.get("leakage_bucket")):
            reasons.append("leakage_bucket_present")
        if "real_unseen" in row and not _bool_value(row.get("real_unseen")):
            reasons.append("synthetic_or_not_real_unseen")
        if not identity:
            reasons.append("source_identity_missing")
        if (
            family == "TEXT"
            and _clean(row.get("active_context_bucket")).lower() != "control"
            and not _bool_value(row.get("control_only"))
        ):
            reasons.append("text_family_control_only")
        if family in {"PDF", "XLSX"} and "disjoint_from_prior" in row and not _bool_value(row.get("disjoint_from_prior")):
            reasons.append("not_disjoint_from_prior")
        if "query_fidelity_included" in row and not _bool_value(row.get("query_fidelity_included")):
            reasons.append("query_fidelity_not_included")
        if identity_hash and identity_hash in prior_hashes:
            reasons.append("prior_identity_hash_collision")
            collision_count += 1

        sanitized = _sanitize_row(
            row,
            accepted=not reasons,
            reasons=sorted(dict.fromkeys(reasons)),
            identity_hash=identity_hash,
            scope=scope,
            protected_fields=protected_fields,
            forbidden_contract_fields=forbidden_contract_fields,
            forbidden_prompt_fields=forbidden_prompt_fields,
            raw_local_path_fields=raw_local_path_fields,
            conflicts=conflicts,
            forbidden_readiness_flags=forbidden_readiness_flags,
            forbidden_operational_fields=forbidden_operational_fields,
            missing_fields=missing_fields,
        )
        if reasons:
            excluded.append(sanitized)
            continue

        accepted.append(sanitized)

    gate = _candidate_intake_gate(candidate_rows, accepted, excluded)
    source_identity_audit_blocked_reasons: list[str] = []
    if prior_identity_hash_records and not prior_hashes:
        source_identity_audit_blocked_reasons.append("prior_identity_hash_baseline_missing")
    if prior_hash_audit["invalid_count"]:
        source_identity_audit_blocked_reasons.append("invalid_prior_identity_hash_records")
    if collision_count:
        source_identity_audit_blocked_reasons.append("prior_identity_hash_collision")
    source_identity_audit_gate = {
        "executed": bool(prior_identity_hash_records),
        "prior_identity_hash_record_count": len(prior_hashes),
        "submitted_prior_identity_hash_record_count": len(prior_identity_hash_records),
        "invalid_prior_identity_hash_record_count": prior_hash_audit["invalid_count"],
        "collision_count": collision_count,
        "blocked_reasons": source_identity_audit_blocked_reasons,
        "passed": (
            bool(prior_identity_hash_records)
            and bool(prior_hashes)
            and prior_hash_audit["invalid_count"] == 0
            and collision_count == 0
        ),
    }
    return {
        "diagnostic_only": True,
        "holdout_candidate_manifest_validation_only": True,
        "v4_name": V4_READINESS_NAME,
        "run_family": V4_READINESS_RUN_FAMILY,
        "schema_version": HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION,
        "contract_hash_algorithm": HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH_ALGORITHM,
        "contract_hash": HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH,
        "holdout_candidate_manifest_contract": build_holdout_candidate_manifest_contract(),
        "candidate_manifest_present": bool(candidate_rows),
        "candidate_manifest_rows": len(candidate_rows),
        "candidate_intake_gate": gate,
        "source_identity_audit_gate": source_identity_audit_gate,
        "accepted_candidate_count": len(accepted),
        "excluded_candidate_count": len(excluded),
        "accepted_candidates": accepted,
        "excluded_candidates": excluded,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "db_or_production_namespace_written": False,
        "protected_namespaces_touched": [],
        "warnings": [
            "diagnostic_only",
            "input_only",
            "not_production_routing",
            "no_artifact_writes",
            "no_official_metric_rows",
            "source_identity_values_hash_only",
        ],
    }


def _candidate_intake_gate(
    candidate_rows: Sequence[Mapping[str, Any]],
    accepted: Sequence[Mapping[str, Any]],
    excluded: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    targets = dict(MINIMUM_TARGETS)
    pdf_hashes = {
        _clean(row.get("source_identity_hash"))
        for row in accepted
        if row.get("source_family") == "PDF" and _clean(row.get("source_identity_hash"))
    }
    xlsx_hashes = {
        _clean(row.get("source_identity_hash"))
        for row in accepted
        if row.get("source_family") == "XLSX" and _clean(row.get("source_identity_hash"))
    }
    text_hashes = {
        _clean(row.get("source_identity_hash"))
        for row in accepted
        if row.get("source_family") == "TEXT" and _clean(row.get("source_identity_hash"))
    }
    query_counts = {
        family: len(
            {
                _clean(row.get("query_id_hash")) or _clean(row.get("candidate_id_hash"))
                for row in accepted
                if row.get("source_family") == family and bool(row.get("query_fidelity_included"))
            }
        )
        for family in SOURCE_FAMILIES
    }
    counts = {
        "PDF_source_document_disjoint": len(pdf_hashes),
        "XLSX_workbook_disjoint": len(xlsx_hashes),
        "TEXT_control_only": len(text_hashes),
    }
    deficits = {
        "pdf_source_document_disjoint_needed": max(0, targets["pdf_unseen_source_documents"] - counts["PDF_source_document_disjoint"]),
        "xlsx_workbook_disjoint_needed": max(0, targets["xlsx_unseen_workbooks"] - counts["XLSX_workbook_disjoint"]),
        "pdf_query_fidelity_rows_needed": max(0, targets["query_fidelity_included_rows_per_family"] - query_counts["PDF"]),
        "xlsx_query_fidelity_rows_needed": max(0, targets["query_fidelity_included_rows_per_family"] - query_counts["XLSX"]),
    }
    identity_sufficient = deficits["pdf_source_document_disjoint_needed"] == 0 and deficits["xlsx_workbook_disjoint_needed"] == 0
    query_sufficient = deficits["pdf_query_fidelity_rows_needed"] == 0 and deficits["xlsx_query_fidelity_rows_needed"] == 0
    blocked_reasons: list[str] = []
    if not candidate_rows:
        blocked_reasons.append("candidate_manifest_missing")
    if not identity_sufficient:
        blocked_reasons.append("real_disjoint_holdout_candidates_below_target")
    if not query_sufficient:
        blocked_reasons.append("real_query_fidelity_candidates_below_target")
    if excluded:
        blocked_reasons.append("candidate_rows_excluded")
    return {
        "passed": bool(candidate_rows) and identity_sufficient and query_sufficient and not excluded,
        "accepted_candidate_count": len(accepted),
        "excluded_candidate_count": len(excluded),
        "accepted_holdout_candidate_counts": counts,
        "real_query_fidelity_included_counts": query_counts,
        "minimum_targets": targets,
        "deficits": deficits,
        "blocked_reasons": blocked_reasons,
    }


def _sanitize_row(
    row: Mapping[str, Any],
    *,
    accepted: bool,
    reasons: Sequence[str],
    identity_hash: str,
    scope: str,
    protected_fields: Sequence[str],
    forbidden_contract_fields: Sequence[str],
    forbidden_prompt_fields: Sequence[str],
    raw_local_path_fields: Sequence[str],
    conflicts: Sequence[str],
    forbidden_readiness_flags: Sequence[str],
    forbidden_operational_fields: Sequence[str],
    missing_fields: Sequence[str],
) -> dict[str, Any]:
    candidate_id = _clean(row.get("candidate_id"))
    query_id = _clean(row.get("query_id"))
    payload = {
        "candidate_id_hash": _simple_hash(candidate_id),
        "candidate_id_hash_algorithm": CANDIDATE_ID_HASH_ALGORITHM if candidate_id else "",
        "candidate_id_present": bool(candidate_id),
        "query_id_hash": _simple_hash(query_id),
        "query_id_hash_algorithm": QUERY_ID_HASH_ALGORITHM if query_id else "",
        "query_id_present": bool(query_id),
        "source_family": _clean(row.get("source_family")).upper(),
        "accepted_for_holdout": accepted,
        "exclusion_reason": reasons[0] if reasons else "",
        "exclusion_reasons": list(reasons),
        "source_identity_hash": identity_hash,
        "source_identity_hash_algorithm": SOURCE_IDENTITY_HASH_ALGORITHM if identity_hash else "",
        "source_identity_scope": scope,
        "query_fidelity_included": _bool_value(row.get("query_fidelity_included")),
        "disjoint_from_prior": _bool_value(row.get("disjoint_from_prior")),
        "real_unseen": _bool_value(row.get("real_unseen")),
        "missing_required_fields": list(missing_fields),
        "protected_oracle_fields_present": list(protected_fields),
        "forbidden_contract_fields_present": list(forbidden_contract_fields),
        "forbidden_prompt_or_llm_fields_present": list(forbidden_prompt_fields),
        "raw_local_path_fields_present": list(raw_local_path_fields),
        "raw_local_path_redaction": RAW_LOCAL_PATH_REDACTION if raw_local_path_fields else "",
        "source_identity_field_conflicts": list(conflicts),
        "forbidden_readiness_flags_present": list(forbidden_readiness_flags),
        "forbidden_operational_fields_present": list(forbidden_operational_fields),
    }
    return {key: value for key, value in payload.items() if value not in ("", [])}


def _source_identity_hash(family: str, scope: str, identity: str) -> str:
    del scope
    return hashlib.sha256(f"{family}:{identity}".encode("utf-8")).hexdigest()


def _simple_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def _prior_identity_hash_audit(records: Sequence[Mapping[str, Any] | str]) -> dict[str, Any]:
    hashes: set[str] = set()
    invalid_count = 0
    for record in records:
        if isinstance(record, str):
            value = _clean(record)
            algorithm = ""
        elif isinstance(record, Mapping):
            value = _clean(record.get("source_identity_hash") or record.get("identity_hash"))
            algorithm = _clean(record.get("source_identity_hash_algorithm") or record.get("identity_hash_algorithm"))
        else:
            value = ""
            algorithm = ""
        if not value:
            invalid_count += 1
            continue
        if algorithm and algorithm != SOURCE_IDENTITY_HASH_ALGORITHM:
            invalid_count += 1
            continue
        if not SHA256_HEX_RE.fullmatch(value):
            invalid_count += 1
            continue
        if value:
            hashes.add(value)
    return {"hashes": hashes, "invalid_count": invalid_count}


def _missing_required_fields(row: Mapping[str, Any]) -> list[str]:
    return [field for field in REQUIRED_COMMON_FIELDS if not _field_present(row, field)]


def _field_present(row: Mapping[str, Any], field: str) -> bool:
    if field not in row:
        return False
    value = row.get(field)
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _present_fields(row: Mapping[str, Any], fields: Sequence[str]) -> list[str]:
    return sorted(field for field in fields if _field_present(row, field))


def _present_keys(row: Mapping[str, Any], fields: Sequence[str]) -> list[str]:
    return sorted(field for field in fields if field in row)


def _truthy_or_nonzero_fields(row: Mapping[str, Any], fields: Sequence[str]) -> list[str]:
    return sorted(field for field in fields if _field_present(row, field) and _truthy_or_nonzero(row.get(field)))


def _truthy_or_nonzero(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    return _bool_value(value)


def _raw_local_path_fields(value: Any, *, prefix: str = "") -> list[str]:
    fields: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            fields.extend(_raw_local_path_fields(child, prefix=child_prefix))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            fields.extend(_raw_local_path_fields(child, prefix=f"{prefix}[{index}]"))
    elif isinstance(value, str) and RAW_LOCAL_PATH_RE.search(value.replace("\\", "/")):
        fields.append(prefix or "value")
    return sorted(set(fields))


def _redact_local_path(value: str) -> str:
    return RAW_LOCAL_PATH_REDACTION if value and RAW_LOCAL_PATH_RE.search(value.replace("\\", "/")) else value


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    return _clean(value).lower() in {"1", "true", "yes", "y"}


def _clean(value: Any) -> str:
    return str(value or "").strip()
