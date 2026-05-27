from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod as v452
from app.capabilities.rag import holdout_manifest_contract


ROOT = v452.ROOT
REPORT_DIR = v452.REPORT_DIR
STATUS_JSONL = v452.STATUS_JSONL
PROGRESS_DOC = v452.PROGRESS_DOC
MEASUREMENTS_DOC = v452.MEASUREMENTS_DOC
TRIAGE_DOC = v452.TRIAGE_DOC
README = v452.README
EVAL_README = v452.EVAL_README
SOURCE_REGISTRY_JSONL = ROOT / "ai" / "eval" / "source_registry" / "source_atom_registry_v1.jsonl"

V4_NAME = v452.V4_NAME
V4_RUN_FAMILY = v452.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod"
EVENT_TYPE = "diagnostic_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod"
STATUS = "DIAGNOSTIC_V4_5_3_EXTERNAL_HOLDOUT_PRIOR_SOURCE_IDENTITY_LEDGER_SUMMARY_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_report_v1"
LEGACY_RUN_IDS = {
    "official_answer_citation_agentic_loop_run_v4_5_3_prior_source_identity_ledger_materialization_nonprod",
}
LEGACY_EVENT_TYPES = {
    "diagnostic_v4_5_3_prior_source_identity_ledger_materialization_nonprod",
}

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v452.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
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
    return v452.clean(value)


def repo_relative(path: Path) -> str:
    return v452.repo_relative(path)


def utc_now() -> str:
    return v452.utc_now()


def sha256_file(path: Path) -> str:
    return v452.sha256_file(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v452.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v452.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v452.write_jsonl(path, rows)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _identity_hash(family: str, identity_key: str) -> str:
    return hashlib.sha256(f"{family}:{identity_key}".encode("utf-8")).hexdigest()


def _pdf_identity_key_and_scope(row: Mapping[str, Any]) -> tuple[str, str]:
    identity_key = holdout_manifest_contract.source_identity_key(row, "PDF")
    identity_scope = holdout_manifest_contract.source_identity_scope(row, "PDF")
    return identity_key, identity_scope


def _xlsx_identity_key(row: Mapping[str, Any]) -> str:
    return holdout_manifest_contract.source_identity_key(row, "XLSX")


def _ledger_group(row: Mapping[str, Any]) -> tuple[str, str, str]:
    family = clean(row.get("source_family")).upper()
    if family == "PDF":
        identity_key, identity_scope = _pdf_identity_key_and_scope(row)
        return family, identity_key, identity_scope
    if family == "XLSX":
        return family, _xlsx_identity_key(row), "XLSX_workbook"
    return "", "", ""


def load_source_registry_rows(path: Path = SOURCE_REGISTRY_JSONL) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, Mapping) and clean(row.get("source_family")).upper() in {"PDF", "XLSX"}:
                rows.append(dict(row))
    return rows


def _source_family_counts(source_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"PDF": 0, "XLSX": 0, "TEXT": 0}
    for row in source_rows:
        family = clean(row.get("source_family")).upper()
        if family in counts:
            counts[family] += 1
    return counts


def path_like_source_identity_count(source_rows: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for row in source_rows if v452.is_raw_local_path_value(row.get("source_identity")))


def path_like_identity_key_candidate_count(source_rows: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in source_rows:
        _family, identity_key, _identity_scope = _ledger_group(row)
        if identity_key and v452.is_raw_local_path_value(identity_key):
            count += 1
    return count


def path_like_raw_locator_row_count(source_rows: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in source_rows:
        raw_locator = _as_mapping(row.get("raw_locator"))
        if any(v452.is_raw_local_path_value(value) for value in raw_locator.values()):
            count += 1
    return count


def build_prior_identity_hash_records(source_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in source_rows:
        family, identity_key, identity_scope = _ledger_group(row)
        if not family or not identity_key or v452.is_raw_local_path_value(identity_key):
            continue
        key = (family, identity_key)
        group = groups.setdefault(
            key,
            {
                "schema_version": f"{RUN_ID}_prior_identity_hash_record_v1",
                "source_family": family,
                "source_identity_hash": _identity_hash(family, identity_key),
                "identity_scope": identity_scope,
                "source_atom_count": 0,
                "sample_source_atom_ids": [],
                "raw_source_identity_value_embedded": False,
                "raw_local_path_value_embedded": False,
                "official_metric_input_rows": 0,
                "promotion_evidence": False,
                "product_success_evidence_allowed": False,
            },
        )
        group["source_atom_count"] += 1
        source_atom_id = clean(row.get("source_atom_id"))
        if source_atom_id and len(group["sample_source_atom_ids"]) < 3:
            group["sample_source_atom_ids"].append(source_atom_id)
    rows = list(groups.values())
    rows.sort(key=lambda item: (item["source_family"], item["source_identity_hash"]))
    return rows


def prior_identity_hash_set_sha256(hash_records: Sequence[Mapping[str, Any]]) -> str:
    payload = "\n".join(
        f"{row['source_family']}:{row['source_identity_hash']}" for row in hash_records
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_prior_identity_ledger_summary(source_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    hash_records = build_prior_identity_hash_records(source_rows)
    by_family = {
        family: [row for row in hash_records if row["source_family"] == family]
        for family in ("PDF", "XLSX", "TEXT")
    }
    source_family_counts = _source_family_counts(source_rows)
    return {
        "schema_version": f"{RUN_ID}_prior_identity_ledger_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "prior_source_identity_ledger_summary_only": True,
        "prior_identity_collision_baseline_available": True,
        "identity_key_policy": {
            "PDF": "document_version_id, then source_document_id fallback",
            "XLSX": "workbook_id/source_workbook_id/raw_locator.workbook, then workbook_version_id fallback",
            "TEXT": "control_only",
        },
        "identity_key_hash_algorithm": "sha256(family:identity_key)",
        "holdout_candidate_manifest_contract_version": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
        ),
        "holdout_candidate_manifest_contract_hash": (
            holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
        ),
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
        "path_like_source_identity_count": path_like_source_identity_count(source_rows),
        "path_like_identity_key_candidate_count": path_like_identity_key_candidate_count(source_rows),
        "path_like_raw_locator_row_count": path_like_raw_locator_row_count(source_rows),
        "prior_identity_key_counts_by_family": {
            family: len(rows) for family, rows in by_family.items()
        },
        "prior_identity_source_atom_counts_by_family": {
            family: sum(int(row["source_atom_count"]) for row in rows)
            for family, rows in by_family.items()
        },
        "source_registry_family_row_counts": source_family_counts,
        "prior_identity_hash_record_count": len(hash_records),
        "prior_identity_hash_set_sha256": prior_identity_hash_set_sha256(hash_records),
        "prior_identity_hash_records_by_family": by_family,
    }


def build_metrics(
    ledger_summary: Mapping[str, Any],
    source_row_count: int,
) -> dict[str, Any]:
    key_counts = ledger_summary["prior_identity_key_counts_by_family"]
    atom_counts = ledger_summary["prior_identity_source_atom_counts_by_family"]
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "external_holdout_prior_source_identity_ledger_summary_only": True,
        "prior_source_identity_ledger_summary_only": True,
        "prior_identity_collision_baseline_available": True,
        "prior_identity_hash_record_count": int(ledger_summary["prior_identity_hash_record_count"]),
        "prior_pdf_identity_count": int(key_counts["PDF"]),
        "prior_xlsx_identity_count": int(key_counts["XLSX"]),
        "prior_text_control_identity_count": int(key_counts["TEXT"]),
        "prior_pdf_source_atom_count": int(atom_counts["PDF"]),
        "prior_xlsx_source_atom_count": int(atom_counts["XLSX"]),
        "prior_text_source_atom_count": int(atom_counts["TEXT"]),
        "source_registry_pdf_xlsx_rows_scanned": source_row_count,
        "path_like_source_identity_count": int(ledger_summary["path_like_source_identity_count"]),
        "path_like_identity_key_candidate_count": int(ledger_summary["path_like_identity_key_candidate_count"]),
        "path_like_raw_locator_row_count": int(ledger_summary["path_like_raw_locator_row_count"]),
        "candidate_manifest_present": False,
        "candidate_manifest_rows": 0,
        "source_identity_audit_gate_passed": False,
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
        "readiness_gate_passed": False,
        "v4_6_ft_dry_run_opened": False,
        "fine_tuning_dataset_exports_created": 0,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
        "previous_gate_run_id": v452.RUN_ID,
    }


def build_guardrails() -> dict[str, Any]:
    guardrails = dict(v452.build_guardrails(v452.load_v4_5_1_report()))
    guardrails.update(
        {
            "schema_version": f"{RUN_ID}_guardrail_audit_v1",
            "run_id": RUN_ID,
            "status": STATUS,
            "external_holdout_candidate_source_identity_audit_only": False,
            "source_identity_audit_ready": False,
            "external_holdout_prior_source_identity_ledger_summary_only": True,
            "prior_source_identity_ledger_summary_only": True,
            "prior_identity_collision_baseline_available": True,
            "prior_identity_ledger_jsonl_created": False,
            "candidate_manifest_jsonl_created": False,
            "source_identity_audit_jsonl_created": False,
            "v4_6_ft_dry_run_opened": False,
            "fine_tuning_dataset_export_created": False,
            "training_job_created": False,
            "model_or_adapter_checkpoint_written": False,
            "raw_source_identity_values_embedded": False,
            "raw_local_path_values_exposed": False,
        }
    )
    return guardrails


def source_run_references() -> dict[str, Any]:
    return {
        "previous_gate_run_id": v452.RUN_ID,
        "previous_gate_report_json": repo_relative(v452.REPORT_JSON),
        "source_registry_jsonl": repo_relative(SOURCE_REGISTRY_JSONL),
        "source_registry_jsonl_sha256": sha256_file(SOURCE_REGISTRY_JSONL) if SOURCE_REGISTRY_JSONL.exists() else "",
        "v4_5_2_report_json": repo_relative(v452.REPORT_JSON),
        "v4_5_1_report_json": repo_relative(v452.v451.REPORT_JSON),
    }


def source_registry_inputs(source_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_source_registry_inputs_v1",
        "source_atom_registry_jsonl": repo_relative(SOURCE_REGISTRY_JSONL),
        "source_atom_registry_jsonl_sha256": sha256_file(SOURCE_REGISTRY_JSONL)
        if SOURCE_REGISTRY_JSONL.exists()
        else "",
        "rows_scanned": len(source_rows),
        "family_row_counts": _source_family_counts(source_rows),
        "source_family_scope": ["PDF", "XLSX"],
        "text_family_control_only": True,
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
    }


def build_report(*, source_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    rows = list(source_rows) if source_rows is not None else load_source_registry_rows()
    ledger_summary = build_prior_identity_ledger_summary(rows)
    metrics = build_metrics(ledger_summary, len(rows))
    guardrails = build_guardrails()
    blocked_reasons = [
        "candidate_manifest_missing",
        "external_holdout_candidate_source_identity_audit_not_rerun_with_prior_identity_summary",
        "real_disjoint_holdout_candidates_below_target",
        "real_query_fidelity_candidates_below_target",
        "user_owned_gold_qrels_denominator_policy_pending",
    ]
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
        "external_holdout_prior_source_identity_ledger_summary_only": True,
        "prior_source_identity_ledger_summary_only": True,
        "prior_identity_collision_baseline_available": True,
        "prior_identity_ledger_rows_embedded_in_report": False,
        "prior_identity_ledger_jsonl_created": False,
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
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
        "candidate_manifest_present": False,
        "candidate_manifest_rows": 0,
        "candidate_manifest_jsonl_created": False,
        "candidate_validation_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        "single_report_artifact_contract": True,
        "review_csv_created": False,
        "human_review_required": False,
        "real_holdout_available": False,
        "real_holdout_sufficient": False,
        "v4_6_ft_dry_run_opened": False,
        "fine_tuning_dataset_export_created": False,
        "training_dataset_exported_for_training": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "readiness_decision": "blocked_pending_external_candidate_manifest_and_user_policy",
        "blocked_reasons": blocked_reasons,
        "prior_identity_ledger_summary": ledger_summary,
        "metrics": metrics,
        "guardrails": guardrails,
        "source_run_references": source_run_references(),
        "source_registry_inputs": source_registry_inputs(rows),
        "artifact_paths": {"report_json": repo_relative(REPORT_JSON)},
        "summary": {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "event_type": EVENT_TYPE,
            "status": STATUS,
            "v4_name": V4_NAME,
            "run_family": V4_RUN_FAMILY,
            "diagnostic_only": True,
            "external_holdout_prior_source_identity_ledger_summary_only": True,
            "prior_source_identity_ledger_summary_only": True,
            "prior_identity_collision_baseline_available": True,
            "holdout_candidate_manifest_contract_version": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_VERSION
            ),
            "holdout_candidate_manifest_contract_hash": (
                holdout_manifest_contract.HOLDOUT_CANDIDATE_MANIFEST_CONTRACT_HASH
            ),
            "prior_identity_hash_record_count": metrics["prior_identity_hash_record_count"],
            "prior_identity_key_counts_by_family": dict(
                ledger_summary["prior_identity_key_counts_by_family"]
            ),
            "candidate_manifest_present": False,
            "candidate_manifest_rows": 0,
            "readiness_decision": "blocked_pending_external_candidate_manifest_and_user_policy",
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
            "prior_identity_ledger_jsonl_created": False,
            "source_identity_audit_jsonl_created": False,
            "raw_source_identity_values_embedded": False,
            "raw_local_path_values_exposed": False,
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
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py --check",
                "targeted v4_5_3 external holdout prior source identity ledger summary tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_5_3 because this slice summarizes a deterministic "
                "hash-only prior source-identity baseline; future training, embedding, or LLM/index workloads should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "No default external holdout candidate manifest is present.",
            "The hash-only prior identity summary proves seen-source identity coverage only; it does not create real disjoint holdout rows.",
            "v4_6 fine-tuning remains closed until v4_5 gates, candidate source-identity audit, and user-owned policy gates pass.",
        ],
        "next_recommendation": (
            "Use this hash-only prior identity summary as the collision baseline for user/repo-owned external PDF/XLSX candidate manifests, "
            "then rerun the v4_5_2 audit before considering any v4_6 dry-run work."
        ),
    }
    serialized = json.dumps(report, ensure_ascii=False)
    if re.search(r"[A-Za-z]:[/\\\\]|file://|/(?:private|tmp|Users|workspace)(?:/|$)", serialized):
        raise RuntimeError("raw local path leaked into v4_5_3 report")
    return report


def build_artifacts(*, source_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    report = build_report(source_rows=source_rows)
    return {
        "schema_version": f"{RUN_ID}_artifact_bundle_v1",
        "run_id": RUN_ID,
        "report": report,
        "metrics": report["metrics"],
        "summary": report["summary"],
    }


def write_artifacts(artifacts: Mapping[str, Any], *, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = dict(artifacts["report"])
    report_json = output_dir / "report.json"
    for stale_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale = output_dir / stale_name
        if stale.exists():
            stale.unlink()
    unexpected = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.name != "report.json"
    )
    if unexpected:
        raise RuntimeError(f"unexpected v4_5_3 primary artifacts: {unexpected}")
    report["artifact_paths"] = {"report_json": report_json.as_posix() if output_dir != OUTPUT_DIR else repo_relative(REPORT_JSON)}
    write_json(report_json, report)
    return report


def artifact_sha256_from_report_paths(paths: Mapping[str, str]) -> dict[str, str]:
    return {
        "report_json_sha256": sha256_file(ROOT / paths["report_json"]) if not Path(paths["report_json"]).is_absolute() else sha256_file(Path(paths["report_json"]))
    }


def append_status_event(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    event = {
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": artifact_sha256_from_report_paths(report["artifact_paths"]),
        "report_json_created": True,
        "summary_json_created": False,
        "per_run_markdown_created": False,
        "review_csv_created": False,
        "prior_identity_ledger_jsonl_created": False,
        "candidate_manifest_jsonl_created": False,
        "source_identity_audit_jsonl_created": False,
        **dict(metrics),
        **dict(report["guardrails"]),
        "blocked_reasons": list(report["blocked_reasons"]),
        "readiness_decision": report["readiness_decision"],
        "schema_version": f"{RUN_ID}_status_event_v1",
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [
        row
        for row in existing
        if not (
            (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)
            or row.get("run_id") in LEGACY_RUN_IDS
            or row.get("event_type") in LEGACY_EVENT_TYPES
        )
    ]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v452.replace_marked_entry(path, marker, entry)


def remove_marked_entry(path: Path, marker: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = (
        rf"\n?<!-- {re.escape(marker)}:start -->\n"
        rf".*?"
        rf"<!-- {re.escape(marker)}:end -->\n?"
    )
    text = re.sub(pattern, "", text, count=1, flags=re.DOTALL)
    path.write_text(text, encoding="utf-8")


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_5_3 (?:prior source identity ledger materialization|external holdout prior source identity ledger summary) loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_5_2 external holdout candidate source identity audit loop:\n`[^`]+`;",
        "current diagnostic v4_5_3 external holdout prior source identity ledger summary loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_5_2 external holdout candidate source identity audit loop:\n`{v452.RUN_ID}`;",
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
        "ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py --check\n"
        "python -X utf8 -m pytest ai/tests --rag-current -q\n"
        "```"
    )
    verify_start = readme_text.index("## How To Verify Locally")
    verify_end = readme_text.index("## Repo Map")
    verify_section = readme_text[verify_start:verify_end]
    verify_section = re.sub(r"```powershell\n.*?```", lambda _match: verify_block, verify_section, count=1, flags=re.DOTALL)
    README.write_text(readme_text[:verify_start] + verify_section + readme_text[verify_end:], encoding="utf-8")

    eval_text = EVAL_README.read_text(encoding="utf-8")
    eval_text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{EVENT_TYPE}_ready`",
        eval_text,
        count=1,
    )
    eval_text = re.sub(
        r"v4_5_2 is `diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod_ready`"
        r"(?:; v4_5_3 is `[^`]+`)?\.",
        f"v4_5_2 is `{v452.EVENT_TYPE}_ready`; v4_5_3 is `{EVENT_TYPE}_ready`.",
        eval_text,
        count=1,
    )
    EVAL_README.write_text(eval_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod.py` | "
        "Summarizes a hash-only prior PDF document/XLSX workbook identity collision baseline from SourceAtom registry evidence inside the single diagnostic report so future external candidate audits can reject seen-source collisions without exposing raw identity values, writing ledger sidecars, or opening training. |"
    )
    text = re.sub(
        r"\| `rag_v4_5_3_prior_source_identity_ledger_materialization_nonprod\.py` \| .*?\|\n?",
        "",
        text,
    )
    if row not in text:
        text = text.replace(
            "| `rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py` | Validates optional external holdout candidate manifests against either a raw prior identity ledger input or the v4_5_3 hash-only prior summary report so PDF document and XLSX workbook collisions are excluded before any v4_6 FT dry run; no sidecar, training dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |",
            "| `rag_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod.py` | Validates optional external holdout candidate manifests against either a raw prior identity ledger input or the v4_5_3 hash-only prior summary report so PDF document and XLSX workbook collisions are excluded before any v4_6 FT dry run; no sidecar, training dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |\n"
            + row,
        )
    scripts_readme.write_text(text, encoding="utf-8")


def update_v4_plan_note() -> None:
    plan_path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    text = plan_path.read_text(encoding="utf-8")
    text = re.sub(
        r"### v4_5_3 — Prior Source Identity Ledger Materialization\n\n.*?(?=### v4_6 — (?:Optional Non-Production Fine-Tuning Dry Run|FT Route Policy Dry-Run Preflight))",
        "",
        text,
        count=1,
        flags=re.DOTALL,
    )
    marker = "### v4_5_3 — External Holdout Prior Source Identity Ledger Summary"
    entry = """### v4_5_3 — External Holdout Prior Source Identity Ledger Summary

Purpose:

- Summarize a sanitized/hash-only prior PDF document and XLSX workbook identity collision baseline from SourceAtom registry evidence.
- Keep the baseline inside the single diagnostic `report.json` so future external candidate audits can use it without exposing raw source identities or creating sidecar candidate/training artifacts.
- Keep v4_6 FT-A dry run closed while external candidate and user-owned policy gates remain blocked.

Success criteria:

```text
prior_source_identity_ledger_summary_only = true
prior_identity_collision_baseline_available = true
raw_source_identity_values_embedded = false
raw_local_path_values_exposed = false
prior_identity_ledger_jsonl_created = false
official_metric_input_rows = 0
v4_6_ft_dry_run_opened = false unless v4_5, v4_5_1, v4_5_2, v4_5_3, and user-owned policy gates pass
```

"""
    if marker not in text:
        text = text.replace(
            "### v4_6 — FT Route Policy Dry-Run Preflight",
            entry + "### v4_6 — FT Route Policy Dry-Run Preflight",
            1,
        )
    text = text.replace(
        "v4_5_2_external_holdout_candidate_source_identity_audit_nonprod\n↓\nv4_6_optional_ft_route_policy_dry_run_nonprod",
        "v4_5_2_external_holdout_candidate_source_identity_audit_nonprod\n↓\nv4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod\n↓\nv4_6_optional_ft_route_policy_dry_run_nonprod",
    )
    text = text.replace(
        "v4_5_3_prior_source_identity_ledger_materialization_nonprod",
        "v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod",
    )
    plan_path.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    report_path = report["artifact_paths"]["report_json"]
    metrics = report["metrics"]
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v452.v451.v45.v44.v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)
    progress_entry = (
        f"- v4_5_3 external holdout prior source identity ledger summary (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It summarizes sanitized/hash-only prior PDF document and XLSX workbook identity collision keys from the SourceAtom registry into the single `report.json`; "
        "the baseline is for future external candidate collision checks and does not expose raw source identities, create candidate rows, review CSV, training datasets, jobs, checkpoints, or a ledger sidecar. "
        f"Current counts are PDF identities={metrics['prior_pdf_identity_count']}, XLSX identities={metrics['prior_xlsx_identity_count']}; "
        "real holdout availability remains false and v4_6 remains closed."
    )
    measurements_entry = f"""### v4_5_3 External Holdout Prior Source Identity Ledger Summary

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, hash-only prior source-identity ledger summary only, single `report.json`.
- Primary artifact: `{report_path}`
- Source evidence: `ai/eval/source_registry/source_atom_registry_v1.jsonl` PDF/XLSX SourceAtom rows.

| Diagnostic count | Value |
| --- | ---: |
| prior_source_identity_ledger_summary_only | true |
| prior_identity_collision_baseline_available | true |
| prior_identity_hash_record_count | {metrics["prior_identity_hash_record_count"]} |
| prior_pdf_identity_count | {metrics["prior_pdf_identity_count"]} |
| prior_xlsx_identity_count | {metrics["prior_xlsx_identity_count"]} |
| prior_pdf_source_atom_count | {metrics["prior_pdf_source_atom_count"]} |
| prior_xlsx_source_atom_count | {metrics["prior_xlsx_source_atom_count"]} |
| path_like_source_identity_count | {metrics["path_like_source_identity_count"]} |
| path_like_identity_key_candidate_count | {metrics["path_like_identity_key_candidate_count"]} |
| path_like_raw_locator_row_count | {metrics["path_like_raw_locator_row_count"]} |
| candidate_manifest_present | false |
| candidate_manifest_rows | 0 |
| real_holdout_available | false |
| real_holdout_sufficient | false |
| v4_6_ft_dry_run_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the hash-only `prior_identity_ledger_summary`, metrics, guardrails, source registry input hashes, verification, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no raw prior identity values, prior identity ledger sidecar, candidate manifest sidecar, validation JSONL, review CSV, training manifest, dataset sidecar, checkpoint, or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_5_3 External Holdout Prior Source Identity Ledger Summary Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_5_3 is diagnostic hash-only prior identity baseline infrastructure, not a v4_6 fine-tuning dry run.\n"
        "- Hash records are derived from existing SourceAtom registry PDF document and XLSX workbook identities only; raw local paths and raw source identities are not exposed.\n"
        "- The summary does not create external holdout candidates, labels, qrels, denominator rows, review packets, training data, jobs, or checkpoints.\n"
        "- Current default run still has no external candidate manifest, so real holdout availability and source-identity audit gate readiness remain closed.\n"
        "- User-owned decisions remain gold set creation/review, expected answer/evidence judgment, relevance/answerability labels, gold policy, official denominator policy, and promotion policy.\n"
        "- GPU is not required for this deterministic hash summary; future training, embedding, or LLM/index workloads should use GPU when opened.\n"
    )
    for legacy_run_id in LEGACY_RUN_IDS:
        remove_marked_entry(PROGRESS_DOC, f"{legacy_run_id}:progress-entry")
        remove_marked_entry(MEASUREMENTS_DOC, f"{legacy_run_id}:measurements-entry")
        remove_marked_entry(TRIAGE_DOC, f"{legacy_run_id}:triage-entry")
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    update_scripts_readme()
    update_v4_plan_note()
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v452.v451.v45.v44.v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)


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
    metrics = artifacts["metrics"]
    if args.check:
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["report"]["status"],
                    "prior_source_identity_ledger_summary_only": metrics[
                        "prior_source_identity_ledger_summary_only"
                    ],
                    "prior_identity_collision_baseline_available": metrics[
                        "prior_identity_collision_baseline_available"
                    ],
                    "prior_identity_hash_record_count": metrics["prior_identity_hash_record_count"],
                    "prior_pdf_identity_count": metrics["prior_pdf_identity_count"],
                    "prior_xlsx_identity_count": metrics["prior_xlsx_identity_count"],
                    "path_like_source_identity_count": metrics["path_like_source_identity_count"],
                    "candidate_manifest_present": metrics["candidate_manifest_present"],
                    "real_holdout_available": metrics["real_holdout_available"],
                    "official_metric_input_rows": metrics["official_metric_input_rows"],
                    "v4_6_ft_dry_run_opened": metrics["v4_6_ft_dry_run_opened"],
                    "gpu_required_for_this_slice": metrics["gpu_required_for_this_slice"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    report = run_write()
    print(json.dumps({"run_id": RUN_ID, "report": report["artifact_paths"]["report_json"], "status": report["status"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
