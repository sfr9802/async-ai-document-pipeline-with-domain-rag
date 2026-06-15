from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_5_1_holdout_candidate_intake_gate_nonprod as v451
import rag_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod as v467
import rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod as v468


ROOT = v468.ROOT
REPORT_DIR = v468.REPORT_DIR
STATUS_JSONL = v468.STATUS_JSONL
PROGRESS_DOC = v468.PROGRESS_DOC
MEASUREMENTS_DOC = v468.MEASUREMENTS_DOC
TRIAGE_DOC = v468.TRIAGE_DOC
README = v468.README
EVAL_README = v468.EVAL_README

AI_ROOT = ROOT / "ai"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.capabilities.rag.holdout_candidate_validation import (  # noqa: E402
    validate_holdout_candidate_rows_for_fastapi,
)


V4_NAME = v468.V4_NAME
V4_RUN_FAMILY = v468.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod"
EVENT_TYPE = "diagnostic_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod"
STATUS = "DIAGNOSTIC_V4_6_9_HOLDOUT_CANDIDATE_DUPLICATE_HYGIENE_GATE_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REPORT_SCHEMA_VERSION = "rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_report_v1"

FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "candidate_manifest.jsonl",
            "candidate_validation.jsonl",
            "duplicate_hygiene_gate.json",
            "dry_run_execution_plan.json",
            "dry_run_input_manifest.jsonl",
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
    return v468.repo_relative(path)


def utc_now() -> str:
    return v468.utc_now()


def sha256_file(path: Path) -> str:
    return v468.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v468.read_json(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v468.write_json(path, payload)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v468.read_jsonl(path)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v468.write_jsonl(path, rows)


def _duplicate_probe_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "shadowed",
            "query_id": "shadow-query",
            "source_family": "PDF",
            "source_document_id": "pdf-invalid-first",
            "source_identity": "pdf-invalid-first",
            "disjoint_from_prior": False,
            "query_fidelity_included": True,
            "real_unseen": True,
        },
        {
            "candidate_id": "shadowed",
            "query_id": "shadow-query",
            "source_family": "PDF",
            "source_document_id": "pdf-valid-looking-duplicate",
            "source_identity": "pdf-valid-looking-duplicate",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
        },
    ]


def _distinct_query_control_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "pdf-doc-1-q1",
            "query_id": "pdf-q1",
            "source_family": "PDF",
            "source_document_id": "pdf-doc-1",
            "source_identity": "pdf-doc-1",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
        },
        {
            "candidate_id": "pdf-doc-1-q2",
            "query_id": "pdf-q2",
            "source_family": "PDF",
            "source_document_id": "pdf-doc-1",
            "source_identity": "pdf-doc-1",
            "disjoint_from_prior": True,
            "query_fidelity_included": True,
            "real_unseen": True,
        },
    ]


def _source_report_input(name: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    report = read_json(path) if exists else {}
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


def build_source_report_inputs() -> dict[str, dict[str, Any]]:
    return {
        "v4_5_1": _source_report_input("v4_5_1", v451.REPORT_JSON),
        "v4_6_7": _source_report_input("v4_6_7", v467.REPORT_JSON),
        "v4_6_8": _source_report_input("v4_6_8", v468.REPORT_JSON),
    }


def _runtime_reason_set(payload: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            clean(reason)
            for row in payload.get("excluded_candidates") or []
            for reason in row.get("exclusion_reasons") or []
            if clean(reason)
        }
    )


def build_duplicate_hygiene_gate() -> dict[str, Any]:
    duplicate_rows = _duplicate_probe_rows()
    runtime_validation = validate_holdout_candidate_rows_for_fastapi(duplicate_rows)
    script_validation = v451.validate_holdout_candidate_rows(
        duplicate_rows,
        minimum_targets={
            "pdf_unseen_source_documents": 1,
            "xlsx_unseen_workbooks": 0,
            "query_fidelity_included_rows_per_family": 1,
        },
    )
    control_rows = _distinct_query_control_rows()
    runtime_control = validate_holdout_candidate_rows_for_fastapi(control_rows)
    script_control = v451.validate_holdout_candidate_rows(
        control_rows,
        minimum_targets={
            "pdf_unseen_source_documents": 1,
            "xlsx_unseen_workbooks": 0,
            "query_fidelity_included_rows_per_family": 2,
        },
    )
    runtime_reasons = _runtime_reason_set(runtime_validation)
    script_excluded = list(script_validation.get("excluded_candidates") or [])
    runtime_invalid_first_duplicate_rejected = (
        int(runtime_validation.get("accepted_candidate_count") or 0) == 0
        and int(runtime_validation.get("excluded_candidate_count") or 0) == 2
        and {"not_disjoint_from_prior", "duplicate_candidate_id", "duplicate_query_id"}.issubset(runtime_reasons)
    )
    script_invalid_first_duplicate_rejected = (
        len(script_validation.get("accepted_candidates") or []) == 0
        and len(script_excluded) == 2
        and clean(script_excluded[0].get("exclusion_reason")) == "not_disjoint_from_prior"
        and clean(script_excluded[1].get("exclusion_reason")) == "duplicate_candidate_id"
    )
    runtime_control_counts = runtime_control["candidate_intake_gate"]["accepted_holdout_candidate_counts"]
    runtime_control_query_counts = runtime_control["candidate_intake_gate"]["real_query_fidelity_included_counts"]
    script_control_counts = script_control["candidate_intake_gate"]["accepted_holdout_candidate_counts"]
    script_control_query_counts = script_control["candidate_intake_gate"]["real_query_fidelity_included_counts"]
    distinct_query_rows_preserved = (
        int(runtime_control.get("accepted_candidate_count") or 0) == 2
        and len(script_control.get("accepted_candidates") or []) == 2
        and runtime_control_counts["PDF_source_document_disjoint"] == 1
        and script_control_counts["PDF_source_document_disjoint"] == 1
        and runtime_control_query_counts["PDF"] == 2
        and script_control_query_counts["PDF"] == 2
    )
    gate_passed = (
        runtime_invalid_first_duplicate_rejected
        and script_invalid_first_duplicate_rejected
        and distinct_query_rows_preserved
    )
    return {
        "schema_version": f"{RUN_ID}_duplicate_hygiene_gate_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "holdout_candidate_duplicate_hygiene_gate_only": True,
        "gate_passed": gate_passed,
        "runtime_invalid_first_duplicate_rejected": runtime_invalid_first_duplicate_rejected,
        "script_invalid_first_duplicate_rejected": script_invalid_first_duplicate_rejected,
        "runtime_script_duplicate_hygiene_consistent": (
            runtime_invalid_first_duplicate_rejected and script_invalid_first_duplicate_rejected
        ),
        "distinct_query_rows_preserved_without_identity_count_inflation": distinct_query_rows_preserved,
        "runtime_accepted_candidate_count": int(runtime_validation.get("accepted_candidate_count") or 0),
        "runtime_excluded_candidate_count": int(runtime_validation.get("excluded_candidate_count") or 0),
        "script_accepted_candidate_count": len(script_validation.get("accepted_candidates") or []),
        "script_excluded_candidate_count": len(script_excluded),
        "runtime_exclusion_reasons": runtime_reasons,
        "script_first_exclusion_reason": clean(script_excluded[0].get("exclusion_reason")) if script_excluded else "",
        "script_second_exclusion_reason": clean(script_excluded[1].get("exclusion_reason")) if len(script_excluded) > 1 else "",
        "accepted_duplicate_row_count": 0,
        "raw_candidate_rows_embedded": False,
        "raw_source_identity_values_embedded": False,
        "raw_local_path_values_exposed": False,
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
        "source_atom_evidence_bundle_evidence_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
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
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_query_matching_used": False,
        "protected_namespaces_touched": [],
        "review_csv_created": False,
        "single_report_artifact_contract": True,
        "gpu_required_for_this_slice": False,
        "gpu_required_for_future_training_when_opened": True,
    }


def raw_source_identity_or_path_leak_count(payload: Mapping[str, Any]) -> int:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    patterns = (
        r"[A-Za-z]:/",
        r"\\\\",
        "shadowed",
        "shadow-query",
        "pdf-invalid-first",
        "pdf-valid-looking-duplicate",
        "pdf-doc-1",
    )
    return sum(1 for pattern in patterns if re.search(pattern, serialized))


def build_artifacts() -> dict[str, Any]:
    source_inputs = build_source_report_inputs()
    hygiene = build_duplicate_hygiene_gate()
    guardrails = build_guardrails()
    metrics = {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "holdout_candidate_duplicate_hygiene_gate_only": True,
        "duplicate_hygiene_gate_passed": hygiene["gate_passed"],
        "runtime_invalid_first_duplicate_rejected": hygiene["runtime_invalid_first_duplicate_rejected"],
        "script_invalid_first_duplicate_rejected": hygiene["script_invalid_first_duplicate_rejected"],
        "runtime_script_duplicate_hygiene_consistent": hygiene["runtime_script_duplicate_hygiene_consistent"],
        "distinct_query_rows_preserved_without_identity_count_inflation": hygiene[
            "distinct_query_rows_preserved_without_identity_count_inflation"
        ],
        "accepted_duplicate_row_count": 0,
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
        "review_csv_created": False,
    }
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "holdout_candidate_duplicate_hygiene_gate_only": True,
        "duplicate_hygiene_gate": hygiene,
        "source_report_inputs": source_inputs,
        "metrics": metrics,
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
        "artifact_paths": {"report_json": repo_relative(REPORT_JSON)},
        "summary": {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "status": STATUS,
            "diagnostic_only": True,
            "holdout_candidate_duplicate_hygiene_gate_only": True,
            "duplicate_hygiene_gate_passed": hygiene["gate_passed"],
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
        },
        "blocked_reasons": [
            "real_external_holdout_candidates_not_registered",
            "candidate_manifest_export_remains_closed",
            "dry_run_input_manifest_not_exported",
            "ft_route_policy_dry_run_not_opened",
            "v4_7_official_metric_gate_not_opened",
            "user_owned_gold_qrels_denominator_policy_pending",
        ],
        "readiness_decision": "blocked_pending_real_external_holdout_candidates_and_user_policy",
        "residual_risks": [
            "This run proves strict duplicate hygiene for diagnostic validators only; it does not acquire holdout rows.",
            "No real external source-document-disjoint PDF candidate manifest is registered.",
            "No real external workbook-disjoint XLSX candidate manifest is registered.",
            "FT-A dry run, dataset export, job creation, and v4_7 remain unopened.",
        ],
        "next_recommendation": (
            "Keep the stricter duplicate hygiene in the runtime/script intake boundary, then register real "
            "source-disjoint PDF/XLSX candidate rows before any FT-A dry-run manifest or v4_7 opening."
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
        raise RuntimeError(f"unexpected v4_6_9 primary artifacts: {unexpected}")


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
        **dict(report["metrics"]),
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": {"report_json_sha256": sha256_file(REPORT_JSON)},
        "diagnostic_only": True,
        "holdout_candidate_duplicate_hygiene_gate_only": True,
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
        raise AssertionError("unexpected v4_6_9 schema")
    hygiene = report["duplicate_hygiene_gate"]
    if not hygiene.get("gate_passed"):
        raise AssertionError("duplicate hygiene gate failed")
    for field in (
        "runtime_invalid_first_duplicate_rejected",
        "script_invalid_first_duplicate_rejected",
        "runtime_script_duplicate_hygiene_consistent",
        "distinct_query_rows_preserved_without_identity_count_inflation",
    ):
        if hygiene.get(field) is not True:
            raise AssertionError(f"{field} must remain true")
    if raw_source_identity_or_path_leak_count(report) != 0:
        raise AssertionError("raw candidate id, source identity, or local path leaked")
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
        raise AssertionError("duplicate hygiene must not satisfy real holdout")


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
    script = "ai\\scripts\\rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod.py"
    compile_cmd = f"python -X utf8 -m py_compile {script}"
    check_cmd = f"python -X utf8 {script} --check"
    if compile_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod.py\n",
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod.py\n"
            f"{compile_cmd}\n",
            1,
        )
    if check_cmd not in verify_section:
        verify_section = verify_section.replace(
            "python -X utf8 ai\\scripts\\rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod.py --check\n",
            "python -X utf8 ai\\scripts\\rag_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod.py --check\n"
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
        r"v4_6_8 is `diagnostic_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod_ready`"
        r"(?:; v4_6_9 is `[^`]+`)?\.",
        f"v4_6_8 is `{v468.EVENT_TYPE}_ready`; v4_6_9 is `{current_status}`.",
        text,
        count=1,
    )
    EVAL_README.write_text(text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod.py` | "
        "Checks strict holdout candidate duplicate hygiene across the default-disabled FastAPI validator and v4_5_1 intake gate; invalid-first duplicate IDs fail closed without writing manifests, sidecars, dry-run inputs, datasets, jobs, checkpoints, official metrics, promotion, or product-success evidence. |"
    )
    pattern = r"\n?\| `rag_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod\.py` \| .*?\|"
    text = re.sub(pattern, "", text)
    text = text.replace(
        "\n\nv4 scripts remain diagnostic/non-production",
        f"\n{row}\n\nv4 scripts remain diagnostic/non-production",
        1,
    )
    scripts_readme.write_text(text, encoding="utf-8")


def update_progress_doc() -> None:
    current_status = f"{EVENT_TYPE}_ready"
    entry = (
        f"- v4_6_9 holdout candidate duplicate hygiene gate (`{RUN_ID}`) is {current_status}. "
        "It hardens the runtime-adjacent holdout candidate validation boundary so invalid rows still reserve "
        "non-empty candidate/query IDs and a later valid-looking duplicate fails closed. It checks the "
        "default-disabled FastAPI validator and v4_5_1 intake gate with sanitized in-memory probes only. It does "
        "not acquire real external holdout rows, export a candidate manifest, create a validation sidecar, dry-run "
        "input manifest, dry-run plan, prompt payload, prompt manifest, raw LLM response, dataset, training "
        "manifest, job, checkpoint, official metric, promotion evidence, product-success evidence, production "
        "route, or live DB/index/cache readiness claim."
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
        r"(?:current diagnostic v4_6_9 holdout candidate duplicate hygiene gate loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_8 runtime readiness dependency freshness gate loop:\n`[^`]+`;",
        "current diagnostic v4_6_9 holdout candidate duplicate hygiene gate loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_6_8 runtime readiness dependency freshness gate loop:\n`{v468.RUN_ID}`;",
        text,
        count=1,
    )
    PROGRESS_DOC.write_text(text, encoding="utf-8")


def update_measurements_doc(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    path_text = report["artifact_paths"]["report_json"]
    entry = f"""### v4_6_9 Holdout Candidate Duplicate Hygiene Gate

- Run: `{RUN_ID}`
- v4 name: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Primary artifact: `{path_text}`
- Source evidence: sanitized in-memory duplicate probes against the default-disabled FastAPI holdout validator and v4_5_1 intake gate.
- Interpretation: this is a deterministic duplicate-hygiene check only. It is not real external holdout acquisition, not candidate manifest export, not FT-A dry-run execution, not official metric, not promotion evidence, and not product/live readiness.

| Counter | Value |
|---|---:|
| holdout_candidate_duplicate_hygiene_gate_only | true |
| duplicate_hygiene_gate_passed | {str(metrics['duplicate_hygiene_gate_passed']).lower()} |
| runtime_invalid_first_duplicate_rejected | {str(metrics['runtime_invalid_first_duplicate_rejected']).lower()} |
| script_invalid_first_duplicate_rejected | {str(metrics['script_invalid_first_duplicate_rejected']).lower()} |
| runtime_script_duplicate_hygiene_consistent | {str(metrics['runtime_script_duplicate_hygiene_consistent']).lower()} |
| distinct_query_rows_preserved_without_identity_count_inflation | {str(metrics['distinct_query_rows_preserved_without_identity_count_inflation']).lower()} |
| accepted_duplicate_row_count | 0 |
| real_holdout_sufficient | false |
| candidate_manifest_exported | false |
| dry_run_input_manifest_exported | false |
| ft_route_policy_dry_run_opened | false |
| v4_7_official_metric_gate_opened | false |
| official_metric_input_rows | 0 |

Artifact policy: single ignored `report.json`; no duplicate-hygiene sidecar, candidate manifest sidecar, validation JSONL, source-identity audit JSONL, dry-run plan/input manifest, prompt manifest, raw LLM response payload, training manifest, dataset export, checkpoint, review CSV, or per-run Markdown is created.
"""
    v467.replace_marked_entry(MEASUREMENTS_DOC, RUN_ID, entry)


def update_triage_doc() -> None:
    entry = f"""### v4_6_9 Holdout Candidate Duplicate Hygiene Gate Triage

- Run: `{RUN_ID}`
- Primary artifact: `reports/rag_eval/rag-ingestion/quality/{RUN_ID}/report.json`; single-report contract remains active.
- v4_6_9 is diagnostic-only and duplicate-hygiene-gate-only. It checks that invalid-first duplicate candidate/query IDs fail closed across runtime and v4_5_1 script validation.
- It proves duplicate boundary hardening only; it is not real holdout availability, not external holdout acquisition, not candidate manifest export, not dry-run execution, not prompt payload creation, not dataset export, and not a v4_7 opening.
- It keeps `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `real_holdout_sufficient=false`, `ft_route_policy_dry_run_opened=false`, and `v4_7_official_metric_gate_opened=false`.
- User-owned gold/qrels/denominator/promotion decisions remain closed before v4_7.
"""
    v467.replace_marked_entry(TRIAGE_DOC, RUN_ID, entry)


def update_v4_plan() -> None:
    plan_path = ROOT / "docs" / "rag_v4_source_grounded_runtime_and_finetune_readiness_plan.md"
    text = plan_path.read_text(encoding="utf-8")
    if "### v4_6_9 — Holdout Candidate Duplicate Hygiene Gate" not in text:
        insert = """### v4_6_9 — Holdout Candidate Duplicate Hygiene Gate

This is a diagnostic duplicate-hygiene gate after v4_6_8, not holdout acquisition and not a dry run.

Purpose:

- Ensure invalid holdout candidate rows still reserve non-empty candidate/query IDs, so a later valid-looking duplicate fails closed.
- Compare the default-disabled FastAPI holdout-candidate validator with the v4_5_1 intake gate using sanitized in-memory probes.
- Keep real external holdout acquisition, manifest export, dry-run input/export, FT-A dry-run execution, dataset export, v4_7, official metric, promotion, product-success, and live-readiness gates closed.

Locked boundary:

```text
holdout_candidate_duplicate_hygiene_gate_only = true
duplicate_hygiene_gate_passed = true
runtime_invalid_first_duplicate_rejected = true
script_invalid_first_duplicate_rejected = true
accepted_duplicate_row_count = 0
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
        "v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        "v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod\n↓\nv4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
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
                    "holdout_candidate_duplicate_hygiene_gate_only": True,
                    "duplicate_hygiene_gate_passed": metrics["duplicate_hygiene_gate_passed"],
                    "runtime_invalid_first_duplicate_rejected": metrics["runtime_invalid_first_duplicate_rejected"],
                    "script_invalid_first_duplicate_rejected": metrics["script_invalid_first_duplicate_rejected"],
                    "real_holdout_sufficient": False,
                    "candidate_manifest_exported": False,
                    "ft_route_policy_dry_run_opened": False,
                    "v4_7_official_metric_gate_opened": False,
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
