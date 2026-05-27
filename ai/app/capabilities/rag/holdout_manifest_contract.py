"""Shared non-production holdout candidate manifest contract.

The contract is input-only and diagnostic: it describes the shape that future
external holdout candidate manifests must satisfy before any fine-tuning lane
can open. It does not create manifests, labels, qrels, datasets, jobs, or
promotion evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


V4_READINESS_NAME = "v4_source_grounded_runtime_locator_and_finetune_readiness"
V4_READINESS_RUN_FAMILY = (
    "official_answer_citation_agentic_loop_run_v4_source_grounded_runtime_locator_and_finetune_readiness_nonprod"
)
HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION = "v4_holdout_candidate_manifest_contract_v1"
HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH_ALGORITHM = "sha256(canonical_json_without_contract_hash)"

SOURCE_FAMILIES = ("PDF", "XLSX", "TEXT")
MINIMUM_TARGETS = {
    "pdf_unseen_source_documents": 20,
    "xlsx_unseen_workbooks": 8,
    "query_fidelity_included_rows_per_family": 100,
}

PDF_IDENTITY_PRIORITY = (
    {
        "tier": "document_version",
        "fields": ("document_version_id", "raw_locator.document_version_id"),
    },
    {
        "tier": "source_document",
        "fields": (
            "source_document_id",
            "document_id",
            "raw_locator.source_document_id",
            "raw_locator.document_id",
        ),
    },
    {
        "tier": "source_identity_fallback",
        "fields": ("source_identity",),
    },
)
XLSX_IDENTITY_PRIORITY = (
    {
        "tier": "workbook",
        "fields": ("workbook_id", "source_workbook_id", "raw_locator.workbook"),
    },
    {
        "tier": "workbook_version",
        "fields": ("workbook_version_id",),
    },
)
TEXT_IDENTITY_PRIORITY = (
    {
        "tier": "text_source_identity",
        "fields": ("source_identity",),
    },
    {
        "tier": "text_candidate_fallback",
        "fields": ("candidate_id",),
    },
)

IDENTITY_PRIORITY_BY_FAMILY = {
    "PDF": PDF_IDENTITY_PRIORITY,
    "XLSX": XLSX_IDENTITY_PRIORITY,
    "TEXT": TEXT_IDENTITY_PRIORITY,
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def field_value(row: Mapping[str, Any], field: str) -> str:
    if field.startswith("raw_locator."):
        return clean(as_mapping(row.get("raw_locator")).get(field.split(".", 1)[1]))
    return clean(row.get(field))


def identity_priority_for_family(family: str) -> tuple[Mapping[str, Any], ...]:
    return tuple(IDENTITY_PRIORITY_BY_FAMILY.get(family.upper(), ()))


def flatten_identity_aliases(family: str) -> list[str]:
    fields: list[str] = []
    for tier in identity_priority_for_family(family):
        fields.extend(str(field) for field in tier["fields"])
    return fields


def source_identity_key(row: Mapping[str, Any], family: str) -> str:
    for tier in identity_priority_for_family(family):
        for field in tier["fields"]:
            value = field_value(row, str(field))
            if value:
                return value
    return ""


def source_identity_scope(row: Mapping[str, Any], family: str) -> str:
    family = family.upper()
    if family == "PDF":
        for tier in PDF_IDENTITY_PRIORITY:
            if any(field_value(row, str(field)) for field in tier["fields"]):
                return "PDF_document_version" if tier["tier"] == "document_version" else "PDF_source_document"
    if family == "XLSX":
        return "XLSX_workbook" if source_identity_key(row, family) else ""
    if family == "TEXT":
        return "TEXT_control" if source_identity_key(row, family) else ""
    return ""


def source_identity_field_conflicts(row: Mapping[str, Any], family: str) -> list[str]:
    conflicting_fields: list[str] = []
    for tier in identity_priority_for_family(family):
        values_by_field = {
            str(field): field_value(row, str(field))
            for field in tier["fields"]
            if field_value(row, str(field))
        }
        distinct_values = set(values_by_field.values())
        if len(distinct_values) > 1:
            conflicting_fields.extend(values_by_field)
    return sorted(conflicting_fields)


def _jsonable_priority(priority: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "tier": str(tier["tier"]),
            "fields": [str(field) for field in tier["fields"]],
        }
        for tier in priority
    ]


def _contract_payload_without_hash() -> dict[str, Any]:
    return {
        "schema_version": HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION,
        "v4_name": V4_READINESS_NAME,
        "run_family": V4_READINESS_RUN_FAMILY,
        "diagnostic_only": True,
        "input_only": True,
        "input_format": "jsonl",
        "accepted_source_families": list(SOURCE_FAMILIES),
        "minimum_targets": dict(MINIMUM_TARGETS),
        "required_common_fields": [
            "candidate_id",
            "query_id",
            "source_family",
            "disjoint_from_prior",
            "query_fidelity_included",
            "real_unseen",
        ],
        "identity_aliases_by_family": {
            family: flatten_identity_aliases(family)
            for family in SOURCE_FAMILIES
        },
        "identity_priority_by_family": {
            family: _jsonable_priority(identity_priority_for_family(family))
            for family in SOURCE_FAMILIES
        },
        "identity_conflict_policy": {
            "same_tier_distinct_identity_values_fail_closed": True,
            "exclusion_reason": "source_identity_field_conflict",
            "higher_priority_identity_wins_over_lower_priority_fallback": True,
            "xlsx_source_identity_only_is_not_workbook_proof": True,
        },
        "source_identity_accepted_as_xlsx_workbook_proof": False,
        "optional_fields": [
            "active_context_bucket",
            "leakage_bucket",
            "source_identity",
            "tenant_id",
        ],
        "forbidden_fields": [
            "expected_answer",
            "supporting_evidence",
            "target_locator",
            "gold_locator",
            "gold_answer",
            "gold_supporting_text",
            "official_metric",
            "official_metric_input_rows",
            "promotion_evidence",
            "product_success_evidence_allowed",
        ],
        "source_identity_collision_audit_required": True,
        "prior_identity_hash_set_required": True,
        "raw_external_path_redaction_required": True,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "fine_tuning_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
    }


def holdout_candidate_manifest_contract_hash(payload: Mapping[str, Any] | None = None) -> str:
    body = dict(payload or _contract_payload_without_hash())
    body.pop("contract_hash", None)
    body.pop("contract_hash_algorithm", None)
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH = holdout_candidate_manifest_contract_hash()


def build_holdout_candidate_manifest_contract() -> dict[str, Any]:
    contract = _contract_payload_without_hash()
    contract["contract_hash_algorithm"] = HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH_ALGORITHM
    contract["contract_hash"] = HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
    return contract


def build_holdout_acquisition_requirements(
    *,
    deficits: Mapping[str, Any] | None = None,
    accepted_source_counts: Mapping[str, Any] | None = None,
    query_fidelity_included_counts: Mapping[str, Any] | None = None,
    non_gold_next_actions: Sequence[Any] | None = None,
    user_owned_next_actions: Sequence[Any] | None = None,
    blocked_reasons: Sequence[Any] | None = None,
    readiness_decision: str = "blocked_pending_real_external_holdout_candidates_and_user_policy",
    validation_route_path: str = "/internal/rag/diagnostic/holdout-candidates/validate",
) -> dict[str, Any]:
    """Return the non-writing acquisition packet external candidate providers need."""

    contract = build_holdout_candidate_manifest_contract()
    raw_deficits = as_mapping(deficits)
    source_counts = as_mapping(accepted_source_counts)
    query_counts = as_mapping(query_fidelity_included_counts)
    canonical_deficits = {
        "pdf_source_document_disjoint_needed": int(raw_deficits.get("pdf_source_document_disjoint_needed") or 20),
        "xlsx_workbook_disjoint_needed": int(raw_deficits.get("xlsx_workbook_disjoint_needed") or 8),
        "pdf_query_fidelity_rows_needed": int(raw_deficits.get("pdf_query_fidelity_rows_needed") or 100),
        "xlsx_query_fidelity_rows_needed": int(raw_deficits.get("xlsx_query_fidelity_rows_needed") or 100),
    }
    canonical_source_counts = {
        "PDF_source_document_disjoint": int(source_counts.get("PDF_source_document_disjoint") or 0),
        "XLSX_workbook_disjoint": int(source_counts.get("XLSX_workbook_disjoint") or 0),
    }
    canonical_query_counts = {
        "PDF": int(query_counts.get("PDF") or 0),
        "XLSX": int(query_counts.get("XLSX") or 0),
    }
    return {
        "schema_version": "v4_holdout_acquisition_requirements_v1",
        "v4_name": V4_READINESS_NAME,
        "run_family": V4_READINESS_RUN_FAMILY,
        "diagnostic_only": True,
        "external_holdout_acquisition_requirements_only": True,
        "input_only": True,
        "validation_route_path": validation_route_path,
        "candidate_manifest_contract_version": contract["schema_version"],
        "candidate_manifest_contract_hash_algorithm": contract["contract_hash_algorithm"],
        "candidate_manifest_contract_hash": contract["contract_hash"],
        "minimum_targets": dict(MINIMUM_TARGETS),
        "deficits": canonical_deficits,
        "accepted_source_counts": canonical_source_counts,
        "query_fidelity_included_counts": canonical_query_counts,
        "accepted_source_families": list(SOURCE_FAMILIES),
        "required_candidate_row_fields": list(contract["required_common_fields"]),
        "identity_fields_by_family": {
            family: flatten_identity_aliases(family)
            for family in SOURCE_FAMILIES
        },
        "identity_priority_by_family": dict(contract["identity_priority_by_family"]),
        "identity_conflict_policy": dict(contract["identity_conflict_policy"]),
        "source_identity_accepted_as_xlsx_workbook_proof": False,
        "forbidden_fields": list(contract["forbidden_fields"]),
        "source_identity_collision_audit_required": True,
        "prior_identity_hash_set_required": True,
        "raw_external_path_redaction_required": True,
        "non_gold_next_actions": [clean(action) for action in (non_gold_next_actions or []) if clean(action)],
        "user_owned_next_actions": [clean(action) for action in (user_owned_next_actions or []) if clean(action)],
        "blocked_reasons": [clean(reason) for reason in (blocked_reasons or []) if clean(reason)],
        "readiness_decision": readiness_decision,
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
        "candidate_manifest_exported": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "dry_run_input_manifest_exported": False,
        "dry_run_execution_plan_exported": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "v4_7_official_metric_gate_opened": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_dataset_exports_created": 0,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
    }
