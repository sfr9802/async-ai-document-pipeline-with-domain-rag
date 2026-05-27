from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_5_1_holdout_candidate_intake_gate_nonprod as v451
from app.capabilities.rag import holdout_manifest_contract


ROOT = v451.ROOT
REPORT_DIR = v451.REPORT_DIR
STATUS_JSONL = v451.STATUS_JSONL
PROGRESS_DOC = v451.PROGRESS_DOC
MEASUREMENTS_DOC = v451.MEASUREMENTS_DOC
TRIAGE_DOC = v451.TRIAGE_DOC
README = v451.README
EVAL_README = v451.EVAL_README

V4_NAME = v451.V4_NAME
V4_RUN_FAMILY = v451.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod"
EVENT_TYPE = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod"
STATUS = "DIAGNOSTIC_V4_5_2_EXTERNAL_HOLDOUT_CANDIDATE_SOURCE_IDENTITY_AUDIT_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
V4_5_3_RUN_ID = "official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod"
V4_5_3_REPORT_JSON = REPORT_DIR / "quality" / V4_5_3_RUN_ID / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_5_2_external_holdout_candidate_source_identity_audit_report_v1"
EXTRA_RAW_LOCAL_PATH_FIELDS = (
    "source_uri",
    "uri",
    "url",
)
IDENTITY_RAW_LOCAL_PATH_FIELDS = (
    "candidate_id",
    "document_id",
    "document_version_id",
    "ledger_row_id",
    "query_id",
    "source_document_id",
    "source_identity",
    "source_run_id",
    "source_workbook_id",
    "workbook_id",
    "workbook_version_id",
)
RAW_LOCATOR_RAW_LOCAL_PATH_FIELDS = (
    "document_id",
    "document_version_id",
    "source_pdf_path",
    "source_xlsx_path",
    "workbook",
)
RAW_LOCAL_PATH_REDACTION = "__raw_local_path_redacted__"
EXTRA_FORBIDDEN_READINESS_FLAG_FIELDS = (
    "official_denominator",
    "official_denominator_mutation",
    "official_metric_input",
    "official_metric_input_rows",
    "promotion_ready",
)
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v451.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
            "candidate_validation.jsonl",
            "holdout_candidate_manifest.jsonl",
            "metrics.json",
            "prior_identity_ledger.jsonl",
            "review_packet.csv",
            "source_identity_audit.jsonl",
            "summary.json",
            "training_manifest.jsonl",
        }
    )
)


def clean(value: Any) -> str:
    return v451.clean(value)


def repo_relative(path: Path) -> str:
    return v451.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v451.artifact_path_text(path)


def utc_now() -> str:
    return v451.utc_now()


def sha256_file(path: Path) -> str:
    return v451.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v451.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v451.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v451.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v451.write_jsonl(path, rows)


def input_path_label(path: Path | None, *, external_label: str) -> tuple[str, str]:
    if path is None:
        return "", "not_provided"
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError:
        return external_label, "external_redacted"
    return relative.as_posix(), "repo_relative"


def load_jsonl_input_rows(
    path: Path | None,
    *,
    schema_suffix: str,
    external_label: str,
    missing_error: str,
    not_file_error: str,
    invalid_error: str,
    unsupported_error: str,
    row_not_object_error: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path_label, path_kind = input_path_label(path, external_label=external_label)
    metadata: dict[str, Any] = {
        "schema_version": f"{RUN_ID}_{schema_suffix}_input_v1",
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
        metadata["load_error"] = missing_error
        return [], metadata
    metadata["exists"] = True
    if not path.is_file():
        metadata["load_error"] = not_file_error
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
                metadata["load_error"] = invalid_error
                metadata["invalid_line_number"] = line_no
                return [], metadata
            if isinstance(row, list):
                metadata["load_error"] = unsupported_error
                metadata["invalid_line_number"] = line_no
                return [], metadata
            if not isinstance(row, Mapping):
                metadata["load_error"] = row_not_object_error
                metadata["invalid_line_number"] = line_no
                return [], metadata
            if ("rows" in row or "candidates" in row) and "source_family" not in row:
                metadata["load_error"] = unsupported_error
                metadata["invalid_line_number"] = line_no
                return [], metadata
            rows.append(dict(row))

    metadata["sha256"] = sha256_file(path)
    metadata["rows_loaded"] = len(rows)
    return rows, metadata


def load_candidate_manifest_rows(path: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return load_jsonl_input_rows(
        path,
        schema_suffix="candidate_manifest",
        external_label="__external_candidate_manifest_path_redacted__",
        missing_error="candidate_manifest_file_missing",
        not_file_error="candidate_manifest_path_not_file",
        invalid_error="candidate_manifest_invalid_jsonl",
        unsupported_error="candidate_manifest_unsupported_format",
        row_not_object_error="candidate_manifest_row_not_object",
    )


def load_prior_identity_rows(path: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return load_jsonl_input_rows(
        path,
        schema_suffix="prior_identity_ledger",
        external_label="__external_prior_identity_ledger_path_redacted__",
        missing_error="prior_identity_ledger_file_missing",
        not_file_error="prior_identity_ledger_path_not_file",
        invalid_error="prior_identity_ledger_invalid_jsonl",
        unsupported_error="prior_identity_ledger_unsupported_format",
        row_not_object_error="prior_identity_ledger_row_not_object",
    )


def load_prior_identity_summary_report(path: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    path_label, path_kind = input_path_label(
        path,
        external_label="__external_prior_identity_summary_report_path_redacted__",
    )
    metadata: dict[str, Any] = {
        "schema_version": f"{RUN_ID}_prior_identity_summary_report_input_v1",
        "provided": path is not None,
        "exists": False,
        "format": "json",
        "path_label": path_label,
        "path_kind": path_kind,
        "sha256": "",
        "load_error": "",
        "raw_local_path_exposed": False,
    }
    if path is None:
        return {}, metadata
    if not path.exists():
        metadata["load_error"] = "prior_identity_summary_report_file_missing"
        return {}, metadata
    metadata["exists"] = True
    if not path.is_file():
        metadata["load_error"] = "prior_identity_summary_report_path_not_file"
        return {}, metadata
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        metadata["load_error"] = "prior_identity_summary_report_invalid_json"
        return {}, metadata
    if not isinstance(payload, Mapping):
        metadata["load_error"] = "prior_identity_summary_report_not_object"
        return {}, metadata
    metadata["sha256"] = sha256_file(path)
    return dict(payload), metadata


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def source_identity_key(row: Mapping[str, Any], family: str) -> str:
    return holdout_manifest_contract.source_identity_key(row, family)


def source_identity_field_conflicts(row: Mapping[str, Any], family: str) -> list[str]:
    return holdout_manifest_contract.source_identity_field_conflicts(row, family)


def is_raw_local_path_value(value: Any) -> bool:
    text = clean(value).replace("\\", "/")
    return bool(text and v451.LOCAL_PATH_RE.search(text))


def redact_raw_local_path_value(value: Any) -> Any:
    if isinstance(value, str):
        return RAW_LOCAL_PATH_REDACTION if is_raw_local_path_value(value) else value
    if isinstance(value, list):
        return [redact_raw_local_path_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_raw_local_path_value(item) for key, item in value.items()}
    return value


def raw_local_path_field_names(row: Mapping[str, Any]) -> list[str]:
    fields = set(v451.raw_local_path_field_names(row))
    for field in (*EXTRA_RAW_LOCAL_PATH_FIELDS, *IDENTITY_RAW_LOCAL_PATH_FIELDS):
        if is_raw_local_path_value(row.get(field)):
            fields.add(field)
    raw_locator = _as_mapping(row.get("raw_locator"))
    for field in RAW_LOCATOR_RAW_LOCAL_PATH_FIELDS:
        if is_raw_local_path_value(raw_locator.get(field)):
            fields.add(f"raw_locator.{field}")
    return sorted(fields)


def forbidden_readiness_flag_names(row: Mapping[str, Any]) -> list[str]:
    fields = set(v451.forbidden_readiness_flag_names(row))
    for field in EXTRA_FORBIDDEN_READINESS_FLAG_FIELDS:
        if v451.bool_value(row.get(field)):
            fields.add(field)
    return sorted(fields)


def build_prior_identity_index(prior_identity_rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in prior_identity_rows:
        family = clean(row.get("source_family")).upper()
        identity = source_identity_key(row, family)
        if family in {"PDF", "XLSX", "TEXT"} and identity:
            index[(family, identity)] = {
                "source_family": family,
                "source_identity_hash": source_identity_hash(family, identity),
                "source_identity_hash_algorithm": "sha256(family:identity_key)",
                "identity_scope": source_identity_scope_for_row(row, family),
                "match_source": "prior_identity_ledger",
            }
    return index


def source_identity_hash(family: str, identity_key: str) -> str:
    return hashlib.sha256(f"{family}:{identity_key}".encode("utf-8")).hexdigest()


def source_identity_scope(family: str) -> str:
    if family == "PDF":
        return "PDF_document_or_document_version"
    if family == "XLSX":
        return "XLSX_workbook"
    return "TEXT_control"


def source_identity_scope_for_row(row: Mapping[str, Any], family: str) -> str:
    return holdout_manifest_contract.source_identity_scope(row, family) or source_identity_scope(family)


def _prior_summary_mapping(prior_identity_summary_report: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not prior_identity_summary_report:
        return {}
    nested = prior_identity_summary_report.get("prior_identity_ledger_summary")
    if isinstance(nested, Mapping):
        return nested
    return prior_identity_summary_report


def prior_identity_hash_records_from_summary_report(
    prior_identity_summary_report: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    summary = _prior_summary_mapping(prior_identity_summary_report)
    if not summary:
        return []
    if clean(summary.get("identity_key_hash_algorithm")) != "sha256(family:identity_key)":
        return []
    if summary.get("raw_source_identity_values_embedded") is not False:
        return []
    if summary.get("raw_local_path_values_exposed") is not False:
        return []
    by_family = summary.get("prior_identity_hash_records_by_family")
    if not isinstance(by_family, Mapping):
        return []

    rows: list[dict[str, Any]] = []
    for family in ("PDF", "XLSX", "TEXT"):
        records = by_family.get(family)
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            source_family = clean(record.get("source_family")).upper()
            source_identity_hash = clean(record.get("source_identity_hash"))
            if source_family != family or not source_identity_hash:
                continue
            try:
                source_atom_count = int(record.get("source_atom_count") or 0)
            except (TypeError, ValueError):
                source_atom_count = 0
            rows.append(
                {
                    "source_family": family,
                    "source_identity_hash": source_identity_hash,
                    "identity_scope": clean(record.get("identity_scope")),
                    "source_atom_count": source_atom_count,
                }
            )
    rows.sort(key=lambda item: (item["source_family"], item["source_identity_hash"]))
    return rows


def build_prior_identity_hash_index(
    prior_identity_summary_report: Mapping[str, Any] | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in prior_identity_hash_records_from_summary_report(prior_identity_summary_report):
        index[(row["source_family"], row["source_identity_hash"])] = {
            "source_family": row["source_family"],
            "source_identity_hash": row["source_identity_hash"],
            "identity_scope": row["identity_scope"],
            "source_atom_count": row["source_atom_count"],
            "match_source": "hash_summary_report",
        }
    return index


def compact_prior_identity_summary_report(
    prior_identity_summary_report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    summary = _prior_summary_mapping(prior_identity_summary_report)
    rows = prior_identity_hash_records_from_summary_report(prior_identity_summary_report)
    by_family = {"PDF": 0, "XLSX": 0, "TEXT": 0}
    for row in rows:
        by_family[row["source_family"]] += 1
    return {
        "schema_version": f"{RUN_ID}_prior_identity_hash_summary_bridge_v1",
        "source_run_id": clean(summary.get("run_id")),
        "identity_key_hash_algorithm": clean(summary.get("identity_key_hash_algorithm")),
        "prior_identity_hash_record_count": len(rows),
        "prior_identity_key_counts_by_family": by_family,
        "prior_identity_hash_set_sha256": clean(summary.get("prior_identity_hash_set_sha256")),
        "holdout_candidate_manifest_contract_version": clean(
            summary.get("holdout_candidate_manifest_contract_version")
        )
        or holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION,
        "holdout_candidate_manifest_contract_hash": clean(
            summary.get("holdout_candidate_manifest_contract_hash")
        )
        or holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH,
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
    }


def _candidate_with_audit_fields(
    row: Mapping[str, Any],
    *,
    accepted: bool,
    reason: str,
    prior_match: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    family = clean(row.get("source_family")).upper()
    identity = source_identity_key(row, family)
    payload = v451.sanitized_candidate_row(row, accepted=accepted, reason=reason)
    for raw_identity_field in (
        "source_identity_key",
        "source_identity",
        "source_document_id",
        "workbook_id",
    ):
        payload.pop(raw_identity_field, None)
    if identity and not is_raw_local_path_value(identity):
        payload["source_identity_hash"] = source_identity_hash(family, identity)
        payload["source_identity_hash_algorithm"] = "sha256(family:identity_key)"
        payload["source_identity_scope"] = source_identity_scope_for_row(row, family)
    payload["source_identity_audit_checked"] = True
    payload["source_identity_field_conflicts"] = source_identity_field_conflicts(row, family)
    payload["raw_local_path_fields_present"] = raw_local_path_field_names(row)
    payload["forbidden_readiness_flags_present"] = forbidden_readiness_flag_names(row)
    payload["prior_identity_collision"] = bool(prior_match)
    if prior_match:
        payload["prior_identity_match"] = {
            key: value for key, value in dict(prior_match).items() if value not in ("", [])
        }
    payload = redact_raw_local_path_value(payload)
    return {key: value for key, value in payload.items() if value not in ("", [])}


def audit_candidate_rows_against_prior_identities(
    candidate_rows: Sequence[Mapping[str, Any]],
    prior_identity_rows: Sequence[Mapping[str, Any]],
    *,
    prior_identity_summary_report: Mapping[str, Any] | None = None,
    minimum_targets: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    prior_index = build_prior_identity_index(prior_identity_rows)
    prior_hash_index = build_prior_identity_hash_index(prior_identity_summary_report)
    collision_excluded: list[dict[str, Any]] = []
    rows_for_intake: list[Mapping[str, Any]] = []

    for row in candidate_rows:
        family = clean(row.get("source_family")).upper()
        identity = source_identity_key(row, family)
        prior_match = prior_index.get((family, identity))
        if not prior_match and identity:
            prior_match = prior_hash_index.get((family, source_identity_hash(family, identity)))
        reason = ""
        if v451.protected_field_names(row):
            reason = "protected_oracle_field_present"
        elif raw_local_path_field_names(row):
            reason = "raw_local_path_present"
        elif forbidden_readiness_flag_names(row):
            reason = "forbidden_readiness_flag_present"
        elif clean(row.get("leakage_bucket")):
            reason = "leakage_bucket_present"
        elif source_identity_field_conflicts(row, family):
            reason = "source_identity_field_conflict"
        elif family == "PDF" and not identity:
            reason = "source_document_identity_missing"
        elif family == "XLSX" and not identity:
            reason = "workbook_identity_missing"
        elif prior_match:
            reason = "prior_source_identity_collision"

        if reason:
            collision_excluded.append(
                _candidate_with_audit_fields(row, accepted=False, reason=reason, prior_match=prior_match)
            )
            continue
        rows_for_intake.append(row)

    validation = v451.validate_holdout_candidate_rows(rows_for_intake, minimum_targets=minimum_targets)
    accepted = [
        _candidate_with_audit_fields(row, accepted=True, reason="")
        for row in validation["accepted_candidates"]
    ]
    base_excluded = [
        _candidate_with_audit_fields(row, accepted=False, reason=clean(row.get("exclusion_reason")))
        for row in validation["excluded_candidates"]
    ]
    source_identity_collision_count = sum(
        1 for row in collision_excluded if row.get("exclusion_reason") == "prior_source_identity_collision"
    )
    source_identity_audit_excluded_count = len(collision_excluded)
    prior_identity_hash_summary_rows = len(prior_hash_index)
    prior_identity_baseline_present = bool(prior_identity_rows) or bool(prior_hash_index)
    gate = dict(validation["candidate_intake_gate"])
    blocked_reasons = list(gate["blocked_reasons"])
    if candidate_rows and "candidate_manifest_missing" in blocked_reasons:
        blocked_reasons.remove("candidate_manifest_missing")
    if not prior_identity_baseline_present and "prior_identity_ledger_missing" not in blocked_reasons:
        insert_at = 1 if blocked_reasons[:1] == ["candidate_manifest_missing"] else 0
        blocked_reasons.insert(insert_at, "prior_identity_ledger_missing")
    if not rows_for_intake and candidate_rows and "real_disjoint_holdout_candidates_below_target" not in blocked_reasons:
        blocked_reasons.append("real_disjoint_holdout_candidates_below_target")
    source_identity_gate_passed = bool(gate["passed"]) and prior_identity_baseline_present
    gate.update(
        {
            "schema_version": f"{RUN_ID}_source_identity_audit_gate_v1",
            "run_id": RUN_ID,
            "passed": source_identity_gate_passed,
            "candidate_manifest_present": bool(candidate_rows),
            "candidate_manifest_rows": len(candidate_rows),
            "excluded_candidate_count": int(gate["excluded_candidate_count"]) + source_identity_audit_excluded_count,
            "prior_identity_ledger_present": bool(prior_identity_rows),
            "prior_identity_rows": len(prior_identity_rows),
            "prior_identity_hash_summary_present": bool(prior_hash_index),
            "prior_identity_hash_summary_rows": prior_identity_hash_summary_rows,
            "prior_identity_baseline_present": prior_identity_baseline_present,
            "source_identity_collision_count": source_identity_collision_count,
            "source_identity_audit_excluded_count": source_identity_audit_excluded_count,
            "holdout_candidate_manifest_contract_version": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
            ),
            "holdout_candidate_manifest_contract_hash": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
            ),
            "blocked_reasons": blocked_reasons,
        }
    )
    return {
        "schema_version": f"{RUN_ID}_source_identity_audit_v1",
        "run_id": RUN_ID,
        "source_identity_audit_ready": True,
        "candidate_manifest_present": bool(candidate_rows),
        "candidate_manifest_rows": len(candidate_rows),
        "prior_identity_ledger_present": bool(prior_identity_rows),
        "prior_identity_rows": len(prior_identity_rows),
        "prior_identity_index_count": len(prior_index),
        "prior_identity_hash_summary_present": bool(prior_hash_index),
        "prior_identity_hash_summary_rows": prior_identity_hash_summary_rows,
        "prior_identity_baseline_present": prior_identity_baseline_present,
        "accepted_candidates": accepted,
        "excluded_candidates": [*collision_excluded, *base_excluded],
        "source_identity_audit_gate": gate,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def default_minimum_targets(source_report: Mapping[str, Any]) -> dict[str, int]:
    return v451.default_minimum_targets(source_report)


def load_v4_5_1_report() -> dict[str, Any]:
    if v451.REPORT_JSON.exists():
        return read_json(v451.REPORT_JSON)
    return v451.build_artifacts()["report"]


def source_run_references(source_report: Mapping[str, Any]) -> dict[str, Any]:
    refs = dict(v451.source_run_references(source_report))
    refs.update(
        {
            "previous_gate_run_id": v451.RUN_ID,
            "previous_gate_report_json": repo_relative(v451.REPORT_JSON),
            "previous_gate_report_sha256": sha256_file(v451.REPORT_JSON)
            if v451.REPORT_JSON.exists()
            else "",
            "v4_5_1_report_json": repo_relative(v451.REPORT_JSON),
            "v4_5_report_json": repo_relative(v451.v45.REPORT_JSON),
            "v4_5_report_sha256": sha256_file(v451.v45.REPORT_JSON)
            if v451.v45.REPORT_JSON.exists()
            else "",
        }
    )
    return refs


def build_guardrails(source_report: Mapping[str, Any]) -> dict[str, Any]:
    guardrails = dict(v451.build_guardrails(source_report))
    guardrails.update(
        {
            "schema_version": f"{RUN_ID}_guardrail_audit_v1",
            "run_id": RUN_ID,
            "status": STATUS,
            "external_holdout_candidate_source_identity_audit_only": True,
            "source_identity_audit_ready": True,
            "prior_identity_ledger_created": False,
            "source_identity_audit_jsonl_created": False,
            "v4_6_ft_dry_run_opened": False,
            "fine_tuning_dataset_export_created": False,
            "training_job_created": False,
            "model_or_adapter_checkpoint_written": False,
        }
    )
    return guardrails


def build_metrics(audit: Mapping[str, Any], source_report: Mapping[str, Any]) -> dict[str, Any]:
    gate = audit["source_identity_audit_gate"]
    counts = gate["accepted_holdout_candidate_counts"]
    query_counts = gate["real_query_fidelity_included_counts"]
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "external_holdout_candidate_source_identity_audit_only": True,
        "source_identity_audit_ready": True,
        "candidate_manifest_present": bool(audit["candidate_manifest_present"]),
        "candidate_manifest_rows": int(audit["candidate_manifest_rows"]),
        "prior_identity_ledger_present": bool(audit["prior_identity_ledger_present"]),
        "prior_identity_rows": int(audit["prior_identity_rows"]),
        "prior_identity_index_count": int(audit["prior_identity_index_count"]),
        "prior_identity_summary_report_present": bool(audit["prior_identity_hash_summary_present"]),
        "prior_identity_summary_hash_records": int(audit["prior_identity_hash_summary_rows"]),
        "prior_identity_hash_summary_present": bool(audit["prior_identity_hash_summary_present"]),
        "prior_identity_hash_summary_rows": int(audit["prior_identity_hash_summary_rows"]),
        "prior_identity_baseline_present": bool(audit["prior_identity_baseline_present"]),
        "source_identity_collision_count": int(gate["source_identity_collision_count"]),
        "source_identity_audit_excluded_count": int(gate["source_identity_audit_excluded_count"]),
        "accepted_pdf_holdout_candidates": int(counts["PDF_source_document_disjoint"]),
        "accepted_xlsx_holdout_candidates": int(counts["XLSX_workbook_disjoint"]),
        "accepted_text_control_candidates": int(counts["TEXT_control_only"]),
        "excluded_holdout_candidate_count": int(gate["excluded_candidate_count"]),
        "source_identity_audit_gate_passed": bool(gate["passed"]),
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
        "readiness_gate_passed": False,
        "v4_6_ft_dry_run_opened": False,
        "fine_tuning_dataset_exports_created": 0,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "minimum_targets": dict(gate["minimum_targets"]),
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
        "previous_gate_run_id": v451.RUN_ID,
        "previous_gate_readiness_gate_passed": bool((source_report.get("metrics") or {}).get("readiness_gate_passed")),
    }


def build_report(
    *,
    source_report: Mapping[str, Any] | None = None,
    candidate_rows: Sequence[Mapping[str, Any]] | None = None,
    prior_identity_rows: Sequence[Mapping[str, Any]] | None = None,
    prior_identity_summary_report: Mapping[str, Any] | None = None,
    candidate_manifest_path: Path | None = None,
    prior_identity_ledger_path: Path | None = None,
    prior_identity_summary_report_path: Path | None = None,
    minimum_targets: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    source = dict(source_report or load_v4_5_1_report())
    targets = dict(minimum_targets or default_minimum_targets(source))
    manifest_rows, candidate_manifest_input = load_candidate_manifest_rows(candidate_manifest_path)
    ledger_rows, prior_identity_ledger_input = load_prior_identity_rows(prior_identity_ledger_path)
    default_summary_path = (
        V4_5_3_REPORT_JSON
        if (
            prior_identity_summary_report is None
            and prior_identity_summary_report_path is None
            and prior_identity_rows is None
            and prior_identity_ledger_path is None
            and V4_5_3_REPORT_JSON.exists()
        )
        else None
    )
    summary_report_input_rows, prior_identity_summary_report_input = load_prior_identity_summary_report(
        prior_identity_summary_report_path or default_summary_path
    )
    prior_identity_summary_report_input["defaulted_from_v4_5_3_report"] = bool(default_summary_path)
    if default_summary_path:
        prior_identity_summary_report_input["provided"] = False
        prior_identity_summary_report_input["default_source_run_id"] = V4_5_3_RUN_ID
    rows_for_validation = candidate_rows if candidate_rows is not None else manifest_rows
    rows_for_prior = prior_identity_rows if prior_identity_rows is not None else ledger_rows
    summary_for_prior = (
        prior_identity_summary_report
        if prior_identity_summary_report is not None
        else summary_report_input_rows
    )
    audit = audit_candidate_rows_against_prior_identities(
        rows_for_validation or (),
        rows_for_prior or (),
        prior_identity_summary_report=summary_for_prior,
        minimum_targets=targets,
    )
    metrics = build_metrics(audit, source)
    guardrails = build_guardrails(source)
    gate = dict(audit["source_identity_audit_gate"])
    gate_blocked_reasons = list(gate["blocked_reasons"])
    for load_error in (
        clean(candidate_manifest_input.get("load_error")),
        clean(prior_identity_ledger_input.get("load_error")),
        clean(prior_identity_summary_report_input.get("load_error")),
    ):
        if load_error and load_error not in gate_blocked_reasons:
            gate_blocked_reasons.insert(0, load_error)
    gate["blocked_reasons"] = gate_blocked_reasons
    blocked_reasons = list(gate_blocked_reasons)
    if "user_owned_gold_qrels_denominator_policy_pending" not in blocked_reasons:
        blocked_reasons.append("user_owned_gold_qrels_denominator_policy_pending")
    readiness_decision = (
        "blocked_pending_user_owned_gold_qrels_denominator_policy"
        if gate["passed"]
        else "blocked_pending_external_manifest_identity_audit_and_user_policy"
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
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
        "external_holdout_candidate_source_identity_audit_only": True,
        "source_identity_audit_ready": True,
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
        "candidate_manifest_present": bool(audit["candidate_manifest_present"]),
        "candidate_manifest_rows": int(audit["candidate_manifest_rows"]),
        "candidate_manifest_input": candidate_manifest_input,
        "prior_identity_ledger_present": bool(audit["prior_identity_ledger_present"]),
        "prior_identity_rows": int(audit["prior_identity_rows"]),
        "prior_identity_ledger_input": prior_identity_ledger_input,
        "prior_identity_summary_report_present": bool(audit["prior_identity_hash_summary_present"]),
        "prior_identity_summary_hash_records": int(audit["prior_identity_hash_summary_rows"]),
        "prior_identity_baseline_present": bool(audit["prior_identity_baseline_present"]),
        "prior_identity_summary_report_input": prior_identity_summary_report_input,
        "prior_identity_summary_report": compact_prior_identity_summary_report(summary_for_prior),
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "prior_identity_ledger_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
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
        "source_identity_audit_gate": gate,
        "accepted_candidates": list(audit["accepted_candidates"]),
        "excluded_candidates": list(audit["excluded_candidates"]),
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
            "external_holdout_candidate_source_identity_audit_only": True,
            "source_identity_audit_ready": True,
            "holdout_candidate_manifest_contract_version": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
            ),
            "holdout_candidate_manifest_contract_hash": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
            ),
            "candidate_manifest_present": bool(audit["candidate_manifest_present"]),
            "candidate_manifest_rows": int(audit["candidate_manifest_rows"]),
            "prior_identity_ledger_present": bool(audit["prior_identity_ledger_present"]),
            "prior_identity_rows": int(audit["prior_identity_rows"]),
            "prior_identity_summary_report_present": bool(audit["prior_identity_hash_summary_present"]),
            "prior_identity_summary_hash_records": int(audit["prior_identity_hash_summary_rows"]),
            "prior_identity_baseline_present": bool(audit["prior_identity_baseline_present"]),
            "source_identity_audit_gate_passed": bool(gate["passed"]),
            "real_holdout_available": False,
            "real_holdout_sufficient": False,
            "candidate_manifest_input": candidate_manifest_input,
            "prior_identity_ledger_input": prior_identity_ledger_input,
            "prior_identity_summary_report_input": prior_identity_summary_report_input,
            "readiness_decision": readiness_decision,
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
            "candidate_manifest_jsonl_created": False,
            "candidate_validation_jsonl_created": False,
            "prior_identity_ledger_jsonl_created": False,
            "source_identity_audit_jsonl_created": False,
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
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py --check",
                "targeted v4_5_2 external manifest source-identity audit tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_5_2 because this slice validates external candidate "
                "source-identity contracts only; future training or large embedding/LLM/index work should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "No default repo-local external holdout candidate manifest is present.",
            "No default raw prior identity ledger input is supplied to v4_5_2; the v4_5_3 hash-only summary can provide the prior baseline, but default run still fails closed without external candidates.",
            "Real source-document-disjoint PDF and workbook-disjoint XLSX holdout counts remain below target.",
            "User-owned gold/qrels/denominator/promotion policy remains closed.",
            "v4_6 FT-A dry run remains unopened.",
        ],
        "next_recommendation": (
            "Supply an external candidate manifest plus either a raw prior identity ledger or the v4_5_3 hash-only summary baseline, pass this source-identity audit, "
            "and keep all fine-tuning dataset exports closed until candidate and user-owned policy gates pass."
        ),
    }
    return report


def build_artifacts(
    *,
    source_report: Mapping[str, Any] | None = None,
    candidate_rows: Sequence[Mapping[str, Any]] | None = None,
    prior_identity_rows: Sequence[Mapping[str, Any]] | None = None,
    prior_identity_summary_report: Mapping[str, Any] | None = None,
    candidate_manifest_path: Path | None = None,
    prior_identity_ledger_path: Path | None = None,
    prior_identity_summary_report_path: Path | None = None,
    minimum_targets: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    report = build_report(
        source_report=source_report,
        candidate_rows=candidate_rows,
        prior_identity_rows=prior_identity_rows,
        prior_identity_summary_report=prior_identity_summary_report,
        candidate_manifest_path=candidate_manifest_path,
        prior_identity_ledger_path=prior_identity_ledger_path,
        prior_identity_summary_report_path=prior_identity_summary_report_path,
        minimum_targets=minimum_targets,
    )
    return {
        "report": report,
        "metrics": report["metrics"],
        "guardrails": report["guardrails"],
        "source_identity_audit_gate": report["source_identity_audit_gate"],
    }


def remove_stale_sidecar_artifacts(target_dir: Path) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()


def assert_single_report_directory(target_dir: Path) -> None:
    unexpected = sorted(path.name for path in target_dir.iterdir() if path.name != "report.json")
    if unexpected:
        raise RuntimeError(f"unexpected v4_5_2 primary artifacts: {unexpected}")


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
    report["candidate_manifest_jsonl_created"] = False
    report["candidate_validation_jsonl_created"] = False
    report["prior_identity_ledger_jsonl_created"] = False
    report["source_identity_audit_jsonl_created"] = False
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
        "candidate_manifest_input": dict(report["candidate_manifest_input"]),
        "prior_identity_ledger_input": dict(report["prior_identity_ledger_input"]),
        "prior_identity_summary_report_input": dict(report["prior_identity_summary_report_input"]),
        "report_json_created": True,
        "review_csv_created": False,
        "summary_json_created": False,
        "per_run_markdown_created": False,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "prior_identity_ledger_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "raw_llm_response_payload_created": False,
        "prompt_payload_created": False,
        "training_manifest_jsonl_created": False,
        "fine_tuning_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
        "source_identity_audit_gate": dict(report["source_identity_audit_gate"]),
        "readiness_decision": report["readiness_decision"],
        "blocked_reasons": list(report["blocked_reasons"]),
        "schema_version": f"{RUN_ID}_status_event_v1",
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v451.replace_marked_entry(path, marker, entry)


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_5_2 external holdout candidate source identity audit loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_5_1 holdout candidate intake gate loop:\n`[^`]+`;",
        "current diagnostic v4_5_2 external holdout candidate source identity audit loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_5_1 holdout candidate intake gate loop:\n`{v451.RUN_ID}`;",
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
        "ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py --check\n"
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
        f"v4_5_1 is `{v451.EVENT_TYPE}_ready`.",
        f"v4_5_1 is `{v451.EVENT_TYPE}_ready`; v4_5_2 is `{EVENT_TYPE}_ready`.",
    )
    EVAL_README.write_text(eval_readme_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    marker = "v4_diagnostic_runtime_locator_and_finetune_readiness_inventory"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py` | "
        "Validates optional external holdout candidate manifests against either a raw prior identity ledger input or the v4_5_3 hash-only prior summary report so PDF document and XLSX workbook collisions are excluded before any v4_6 FT dry run; no sidecar, training dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |"
    )
    if row not in text:
        text = text.replace(
            "| `rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py` | Validates optional external real holdout candidate manifest input before any v4_6 FT dry run; the manifest is read as input only, raw external paths are redacted, and no candidate sidecar, training dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |",
            "| `rag_v4_5_1_holdout_candidate_intake_gate_nonprod.py` | Validates optional external real holdout candidate manifest input before any v4_6 FT dry run; the manifest is read as input only, raw external paths are redacted, and no candidate sidecar, training dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |\n"
            + row,
        )
    scripts_readme.write_text(text, encoding="utf-8")


def update_v4_plan_note() -> None:
    plan_path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    if not plan_path.exists():
        return
    text = plan_path.read_text(encoding="utf-8")
    marker = "### v4_5_2 — External Holdout Candidate Source Identity Audit"
    entry = """### v4_5_2 — External Holdout Candidate Source Identity Audit

Purpose:

- Add source-identity audit infrastructure for external holdout candidate manifests.
- Require PDF document-level identity and XLSX workbook-level identity to be disjoint from a prior identity ledger before candidates can satisfy split-quality gates.
- Keep v4_6 FT-A dry run closed while candidate and user-owned policy gates remain blocked.

Success criteria:

```text
external_holdout_candidate_source_identity_audit_only = true
source_identity_audit_ready = true
candidate_manifest_input_path_kind = repo_relative or external_redacted
prior_identity_ledger_input_path_kind = repo_relative or external_redacted
prior_source_identity_collisions are excluded
official_metric_input_rows = 0
v4_6_ft_dry_run_opened = false unless v4_5, v4_5_1, v4_5_2, and user-owned policy gates pass
```

"""
    if marker not in text:
        text = text.replace(
            "### v4_6 — FT Route Policy Dry-Run Preflight",
            entry + "### v4_6 — FT Route Policy Dry-Run Preflight",
            1,
        )
    text = text.replace(
        "v4_5_1_holdout_candidate_intake_gate_nonprod\n↓\nv4_6_optional_ft_route_policy_dry_run_nonprod",
        "v4_5_1_holdout_candidate_intake_gate_nonprod\n↓\nv4_5_2_external_holdout_candidate_source_identity_audit_nonprod\n↓\nv4_6_optional_ft_route_policy_dry_run_nonprod",
    )
    plan_path.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    report_path = report["artifact_paths"]["report_json"]
    metrics = report["metrics"]
    gate = report["source_identity_audit_gate"]
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v451.v45.v44.v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)
    progress_entry = (
        f"- v4_5_2 external holdout candidate source-identity audit (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It adds a source-identity audit layer over v4_5_1 so external candidate rows must be checked against a prior identity ledger; "
        "PDF candidates need document-level identity and XLSX candidates need workbook-level identity before they can count as source-disjoint. "
        "When no raw prior ledger is supplied, the default checked run uses the v4_5_3 hash-only prior summary report as its collision baseline if present. "
        f"The default checked run still has no external manifest, so the gate fails closed and writes one `report.json` at `{report_path}`. "
        "Boundary: diagnostic-only, non-production, not product success evidence, not promotion evidence, not official metric lift, not live DB/index/cache readiness, "
        "no candidate sidecar, no prior-ledger sidecar, no source-identity audit sidecar, no fine-tuning dataset export, no training job, and no checkpoint."
    )
    measurements_entry = f"""### v4_5_2 External Holdout Candidate Source Identity Audit

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, external holdout candidate source-identity audit only, single `report.json`.
- Primary artifact: `{report_path}`
- Source evidence: v4_5_1 candidate intake gate plus optional external candidate manifest, optional raw prior identity ledger input, and the v4_5_3 hash-only prior summary report when available.

| Diagnostic count | Value |
| --- | ---: |
| source_identity_audit_ready | true |
| candidate_manifest_input_provided | {str(report["candidate_manifest_input"]["provided"]).lower()} |
| candidate_manifest_input_path_kind | {report["candidate_manifest_input"]["path_kind"]} |
| prior_identity_ledger_input_provided | {str(report["prior_identity_ledger_input"]["provided"]).lower()} |
| prior_identity_ledger_input_path_kind | {report["prior_identity_ledger_input"]["path_kind"]} |
| prior_identity_summary_report_defaulted_from_v4_5_3 | {str(report["prior_identity_summary_report_input"].get("defaulted_from_v4_5_3_report")).lower()} |
| prior_identity_summary_report_path_kind | {report["prior_identity_summary_report_input"]["path_kind"]} |
| candidate_manifest_present | {str(metrics["candidate_manifest_present"]).lower()} |
| candidate_manifest_rows | {metrics["candidate_manifest_rows"]} |
| prior_identity_ledger_present | {str(metrics["prior_identity_ledger_present"]).lower()} |
| prior_identity_rows | {metrics["prior_identity_rows"]} |
| prior_identity_summary_report_present | {str(metrics["prior_identity_summary_report_present"]).lower()} |
| prior_identity_summary_hash_records | {metrics["prior_identity_summary_hash_records"]} |
| prior_identity_baseline_present | {str(metrics["prior_identity_baseline_present"]).lower()} |
| source_identity_audit_gate_passed | {str(metrics["source_identity_audit_gate_passed"]).lower()} |
| source_identity_collision_count | {metrics["source_identity_collision_count"]} |
| accepted_pdf_holdout_candidates | {metrics["accepted_pdf_holdout_candidates"]}/{metrics["minimum_targets"]["pdf_unseen_source_documents"]} |
| accepted_xlsx_holdout_candidates | {metrics["accepted_xlsx_holdout_candidates"]}/{metrics["minimum_targets"]["xlsx_unseen_workbooks"]} |
| real_query_fidelity_included_rows_per_family | {gate["real_query_fidelity_included_counts"]["PDF"]}/{metrics["minimum_targets"]["query_fidelity_included_rows_per_family"]} PDF, {gate["real_query_fidelity_included_counts"]["XLSX"]}/{metrics["minimum_targets"]["query_fidelity_included_rows_per_family"]} XLSX |
| real_holdout_available | false |
| real_holdout_sufficient | false |
| v4_6_ft_dry_run_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds candidate_manifest_input, prior_identity_ledger_input, prior_identity_summary_report_input, the compact hash-only prior summary bridge, source_identity_audit_gate, accepted/excluded sanitized candidate rows, metrics, guardrails, source lineage, verification, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no candidate manifest sidecar, prior identity ledger sidecar, validation JSONL, review CSV, training manifest, dataset sidecar, checkpoint, or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_5_2 External Holdout Candidate Source Identity Audit Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_5_2 is diagnostic source-identity audit infrastructure over external holdout candidate manifests, not a v4_6 fine-tuning dry run.\n"
        "- Candidate manifests, raw prior identity ledgers, and v4_5_3 hash-only prior summary reports are read as input only; external paths are redacted and inputs are not copied into the run directory.\n"
        "- PDF candidates require document-level identity; XLSX candidates require workbook-level identity. XLSX row/cell-level `source_identity` alone is not accepted as workbook-disjoint proof.\n"
        "- Prior source identity collisions are excluded before candidate counts or query-fidelity rows can satisfy gates.\n"
        "- Current default run has no manifest; it can consume the v4_5_3 hash-only prior summary baseline, but the source-identity audit gate still fails closed until accepted external candidates exist.\n"
        "- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy; user-owned label/qrels/denominator policy stays closed.\n"
        "- GPU is not required for this deterministic source-identity audit; future training, embedding, or LLM/index workloads should use GPU when opened.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    update_scripts_readme()
    update_v4_plan_note()
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v451.v45.v44.v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)


def run_write(
    *,
    candidate_manifest_path: Path | None = None,
    prior_identity_ledger_path: Path | None = None,
    prior_identity_summary_report_path: Path | None = None,
) -> dict[str, Any]:
    artifacts = build_artifacts(
        candidate_manifest_path=candidate_manifest_path,
        prior_identity_ledger_path=prior_identity_ledger_path,
        prior_identity_summary_report_path=prior_identity_summary_report_path,
    )
    report = write_artifacts(artifacts)
    update_docs(report)
    append_status_event(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--candidate-manifest", "--manifest-file", dest="candidate_manifest", type=Path, default=None)
    parser.add_argument("--prior-identity-ledger", dest="prior_identity_ledger", type=Path, default=None)
    parser.add_argument(
        "--prior-identity-summary-report",
        dest="prior_identity_summary_report",
        type=Path,
        default=None,
    )
    args = parser.parse_args(argv)
    if args.check:
        artifacts = build_artifacts(
            candidate_manifest_path=args.candidate_manifest,
            prior_identity_ledger_path=args.prior_identity_ledger,
            prior_identity_summary_report_path=args.prior_identity_summary_report,
        )
        metrics = artifacts["metrics"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["report"]["summary"]["status"],
                    "source_identity_audit_gate_passed": metrics["source_identity_audit_gate_passed"],
                    "candidate_manifest_present": metrics["candidate_manifest_present"],
                    "candidate_manifest_rows": metrics["candidate_manifest_rows"],
                    "candidate_manifest_input_provided": artifacts["report"]["candidate_manifest_input"]["provided"],
                    "candidate_manifest_load_error": artifacts["report"]["candidate_manifest_input"]["load_error"],
                    "prior_identity_ledger_present": metrics["prior_identity_ledger_present"],
                    "prior_identity_rows": metrics["prior_identity_rows"],
                    "prior_identity_ledger_input_provided": artifacts["report"]["prior_identity_ledger_input"]["provided"],
                    "prior_identity_ledger_load_error": artifacts["report"]["prior_identity_ledger_input"]["load_error"],
                    "prior_identity_summary_report_present": metrics["prior_identity_summary_report_present"],
                    "prior_identity_summary_hash_records": metrics["prior_identity_summary_hash_records"],
                    "prior_identity_baseline_present": metrics["prior_identity_baseline_present"],
                    "prior_identity_summary_report_input_provided": artifacts["report"]["prior_identity_summary_report_input"]["provided"],
                    "prior_identity_summary_report_load_error": artifacts["report"]["prior_identity_summary_report_input"]["load_error"],
                    "source_identity_collision_count": metrics["source_identity_collision_count"],
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
    report = run_write(
        candidate_manifest_path=args.candidate_manifest,
        prior_identity_ledger_path=args.prior_identity_ledger,
        prior_identity_summary_report_path=args.prior_identity_summary_report,
    )
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
