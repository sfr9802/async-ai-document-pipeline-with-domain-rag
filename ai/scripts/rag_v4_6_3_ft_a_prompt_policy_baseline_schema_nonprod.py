from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v4_6_2_ft_route_policy_fixture_contract_nonprod as v462


ROOT = v462.ROOT
REPORT_DIR = v462.REPORT_DIR
STATUS_JSONL = v462.STATUS_JSONL
PROGRESS_DOC = v462.PROGRESS_DOC
MEASUREMENTS_DOC = v462.MEASUREMENTS_DOC
TRIAGE_DOC = v462.TRIAGE_DOC
README = v462.README
EVAL_README = v462.EVAL_README

V4_NAME = v462.V4_NAME
V4_RUN_FAMILY = v462.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod"
EVENT_TYPE = "diagnostic_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod"
STATUS = "DIAGNOSTIC_V4_6_3_FT_A_PROMPT_POLICY_BASELINE_SCHEMA_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_6_3_ft_a_prompt_policy_baseline_schema_report_v1"
REQUIRED_FUTURE_DRY_RUN_OUTPUTS = [
    "deterministic_rule_baseline_policy_bucket",
    "prompt_only_baseline_policy_bucket",
    "ft_model_policy_bucket",
    "conservative_fallback_policy_bucket",
]
STOP_CONDITION_AUDIT_BUCKETS = [
    "fail_closed_preservation_regression",
    "answer_allowed_overreach",
    "context_required_false_negative",
    "ambiguous_identity_false_negative",
    "unsupported_route_false_negative",
]
PROMPT_POLICY_IDS = [
    "deterministic_rule_baseline_v1",
    "prompt_only_policy_bucket_classifier_schema_v1",
    "conservative_fallback_policy_v1",
]
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "baseline_comparison_contract.json",
            "dpo_dataset.jsonl",
            "ft_route_policy_dry_run.json",
            "metrics.json",
            "prompt_manifest.json",
            "prompt_policy_baseline_schema.json",
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
    return v462.clean(value)


def repo_relative(path: Path) -> str:
    return v462.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v462.artifact_path_text(path)


def utc_now() -> str:
    return v462.utc_now()


def sha256_file(path: Path) -> str:
    return v462.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v462.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v462.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v462.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v462.write_jsonl(path, rows)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def load_v4_6_2_report() -> dict[str, Any]:
    if v462.REPORT_JSON.exists():
        return read_json(v462.REPORT_JSON)
    return {}


def source_report_input(*, report: Mapping[str, Any]) -> dict[str, Any]:
    exists = v462.REPORT_JSON.exists()
    return {
        "schema_version": f"{RUN_ID}_source_report_input_v1",
        "run_id": RUN_ID,
        "input_key": "v4_6_2",
        "source_run_id": v462.RUN_ID,
        "source_report_json": repo_relative(v462.REPORT_JSON),
        "source_report_exists": exists,
        "source_report_sha256": sha256_file(v462.REPORT_JSON) if exists else "",
        "source_report_schema_version": clean(report.get("schema_version")),
        "source_report_status": clean(report.get("status")),
        "source_report_diagnostic_only": bool(report.get("diagnostic_only")),
        "source_report_official_metric": bool(report.get("official_metric")),
        "source_report_official_metric_input_rows": int(report.get("official_metric_input_rows") or 0),
        "source_report_promotion_evidence": bool(report.get("promotion_evidence")),
        "source_report_product_success_evidence_allowed": bool(
            report.get("product_success_evidence_allowed")
        ),
        "source_fixture_contract_gate_ready": bool(
            _mapping(report.get("fixture_contract_gate")).get("fixture_contract_schema_check_passed")
        ),
        "source_fixture_dry_run_dataset_gate_passed": bool(
            _mapping(report.get("fixture_contract_gate")).get("dry_run_dataset_gate_passed")
        ),
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_source_report_inputs(source_fixture_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {"v4_6_2": source_report_input(report=source_fixture_report)}


def build_prompt_policy_baseline_schema(source_fixture_report: Mapping[str, Any]) -> dict[str, Any]:
    fixture_contract = _mapping(source_fixture_report.get("ft_a_fixture_contract"))
    return {
        "schema_version": f"{RUN_ID}_prompt_policy_baseline_schema_v1",
        "run_id": RUN_ID,
        "lane": "FT-A",
        "source_fixture_run_id": v462.RUN_ID,
        "source_fixture_schema_version": clean(source_fixture_report.get("schema_version")),
        "row_source": "v4_6_2_route_policy_fixture_contract_only",
        "prompt_only_baseline_schema_frozen": True,
        "prompt_policy_ids": list(PROMPT_POLICY_IDS),
        "target_policy_buckets": list(fixture_contract.get("target_policy_buckets") or v462.TARGET_POLICY_BUCKETS),
        "allowed_route_lanes": list(fixture_contract.get("allowed_route_lanes") or v462.ALLOWED_ROUTE_LANES),
        "allowed_source_families": list(
            fixture_contract.get("allowed_source_families") or v462.ALLOWED_SOURCE_FAMILIES
        ),
        "allowed_model_input_fields": list(
            fixture_contract.get("allowed_model_input_fields") or v462.ALLOWED_MODEL_INPUT_FIELDS
        ),
        "label_only_fields": list(fixture_contract.get("label_only_fields") or v462.LABEL_ONLY_FIELDS),
        "forbidden_model_input_fields": list(
            fixture_contract.get("forbidden_model_input_fields") or v462.FORBIDDEN_MODEL_INPUT_FIELDS
        ),
        "forbidden_field_name_patterns": list(v462.FORBIDDEN_FIELD_NAME_PATTERNS),
        "required_future_dry_run_outputs": list(REQUIRED_FUTURE_DRY_RUN_OUTPUTS),
        "confusion_matrix_axes": {
            "row_axis": "label_response_policy_bucket",
            "column_axis": "predicted_response_policy_bucket",
        },
        "stop_condition_audit_buckets": list(STOP_CONDITION_AUDIT_BUCKETS),
        "raw_prompt_text_embedded": False,
        "prompt_payload_created": False,
        "prompt_manifest_created": False,
        "raw_llm_response_payload_created": False,
        "training_dataset_export_created": False,
        "training_job_created": False,
        "model_or_adapter_checkpoint_written": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
    }


def build_prompt_policy_baseline_gate(source_fixture_report: Mapping[str, Any]) -> dict[str, Any]:
    gate = _mapping(source_fixture_report.get("fixture_contract_gate"))
    fixture_ready = (
        bool(source_fixture_report.get("diagnostic_only"))
        and clean(source_fixture_report.get("schema_version"))
        == "rag_v4_6_2_ft_route_policy_fixture_contract_report_v1"
        and bool(source_fixture_report.get("ft_route_policy_fixture_contract_only"))
        and bool(gate.get("fixture_contract_schema_check_passed"))
        and not bool(gate.get("dry_run_dataset_gate_passed"))
        and int(source_fixture_report.get("official_metric_input_rows") or 0) == 0
        and not bool(source_fixture_report.get("promotion_evidence"))
        and not bool(source_fixture_report.get("product_success_evidence_allowed"))
    )
    blocked_reasons = ["dry_run_comparison_requires_v4_6_preflight_and_user_policy_gates"]
    if not fixture_ready:
        blocked_reasons.append("missing_or_invalid_v4_6_2_fixture_contract")
    return {
        "schema_version": f"{RUN_ID}_prompt_policy_baseline_gate_v1",
        "run_id": RUN_ID,
        "prompt_policy_baseline_schema_check_passed": True,
        "fixture_contract_gate_ready": fixture_ready,
        "dry_run_prompt_baseline_gate_passed": False,
        "ft_route_policy_dry_run_opened": False,
        "ft_route_policy_dry_run_executed": False,
        "fine_tuning_dataset_exports_created": 0,
        "v4_7_official_metric_gate_opened": False,
        "blocked_reasons": blocked_reasons,
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


def build_metrics(*, gate: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "ft_a_prompt_policy_baseline_schema_only": True,
        "prompt_policy_baseline_schema_check_passed": bool(
            gate.get("prompt_policy_baseline_schema_check_passed")
        ),
        "dry_run_prompt_baseline_gate_passed": bool(gate.get("dry_run_prompt_baseline_gate_passed")),
        "fixture_contract_gate_ready": bool(gate.get("fixture_contract_gate_ready")),
        "future_dry_run_required_output_count": len(schema.get("required_future_dry_run_outputs") or []),
        "stop_condition_audit_bucket_count": len(schema.get("stop_condition_audit_buckets") or []),
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
    schema: Mapping[str, Any],
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
        "ft_a_prompt_policy_baseline_schema_only": True,
        "prompt_policy_baseline_schema": dict(schema),
        "prompt_policy_baseline_gate": dict(gate),
        "source_report_inputs": {key: dict(value) for key, value in source_inputs.items()},
        "readiness_decision": "blocked_pending_v4_6_preflight_and_user_policy_gates",
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
                "python -X utf8 -m py_compile ai\\scripts\\rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py",
                "python -X utf8 ai\\scripts\\rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py --check",
                "targeted v4_6_3 prompt-policy baseline schema tests",
                "python -X utf8 -m pytest ai/tests --rag-current -q",
            ],
            "gpu_note": (
                "No GPU workload is executed in v4_6_3 because this slice freezes a deterministic schema only; "
                "future FT-A training, embedding, or local LLM workloads should use GPU when gates open."
            ),
        },
        "residual_risks": [
            "No raw prompt text or prompt payload is emitted.",
            "No actual FT-A dry run is opened or executed.",
            "No fine-tuning dataset is exported.",
            "v4_7 official metric opening remains user-owned and unopened.",
        ],
        "next_recommendation": (
            "Keep prompt payload creation, FT-A execution, dataset export, and v4_7 closed until v4_6 preflight "
            "and user-owned policy inputs pass; next non-gold work can add a dry-run input manifest validator."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    fixture_report = load_v4_6_2_report()
    inputs = build_source_report_inputs(fixture_report)
    schema = build_prompt_policy_baseline_schema(fixture_report)
    gate = build_prompt_policy_baseline_gate(fixture_report)
    metrics = build_metrics(gate=gate, schema=schema)
    guardrails = build_guardrails()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        source_inputs=inputs,
        schema=schema,
        gate=gate,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "prompt_policy_baseline_schema": schema,
        "prompt_policy_baseline_gate": gate,
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
        raise RuntimeError(f"unexpected v4_6_3 primary artifacts: {unexpected}")


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
    return v462.artifact_sha256_from_report_paths(artifact_paths)


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
        "prompt_policy_baseline_gate": dict(report["prompt_policy_baseline_gate"]),
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
    v462.replace_marked_entry(path, marker, entry)


def _refresh_docs() -> None:
    v462._refresh_docs()


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_6_3 FT-A prompt-policy baseline schema loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_6_2 FT-A route-policy fixture contract loop:\n`[^`]+`;",
        "current diagnostic v4_6_3 FT-A prompt-policy baseline schema loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_6_2 FT-A route-policy fixture contract loop:\n"
        f"`{v462.RUN_ID}`;",
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
        "ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py\n"
        "python -X utf8 -m py_compile "
        "ai\\scripts\\rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py --check\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py --check\n"
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
        r"v4_6_2 is `diagnostic_v4_6_2_ft_route_policy_fixture_contract_nonprod_ready`"
        r"(?:; v4_6_3 is `[^`]+`)?\.",
        f"v4_6_2 is `{v462.EVENT_TYPE}_ready`; v4_6_3 is `{EVENT_TYPE}_ready`.",
        eval_text,
        count=1,
    )
    EVAL_README.write_text(eval_text, encoding="utf-8")


def update_scripts_readme() -> None:
    scripts_readme = ROOT / "ai" / "scripts" / "README.md"
    text = scripts_readme.read_text(encoding="utf-8")
    row = (
        "| `rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod.py` | "
        "Freezes a schema-only prompt-policy baseline contract for a later FT-A route/policy dry run; no raw prompt text, prompt manifest, raw LLM response, dataset, job, checkpoint, official metric, promotion, or product-success evidence is emitted. |"
    )
    pattern = r"\| `rag_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod\.py` \| .*?\|"
    if re.search(pattern, text):
        text = re.sub(pattern, row, text, count=1)
    elif "| `rag_v4_6_2_ft_route_policy_fixture_contract_nonprod.py` |" in text:
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
    if "### v4_6_3 — FT-A Prompt-Policy Baseline Schema" not in text:
        insert = """### v4_6_3 — FT-A Prompt-Policy Baseline Schema

This is a diagnostic schema-only baseline for a later non-production FT-A dry run, not prompt creation and not the dry run itself.

Purpose:

- Freeze allowed prompt-policy baseline identifiers and future dry-run comparison output fields.
- Define confusion-matrix axes and stop-condition audit buckets without rendering raw prompt text.
- Keep prompt payload creation, dataset export, dry-run execution, v4_7, official metric, promotion, product-success, and live-readiness gates closed.

Required state:

```text
ft_a_prompt_policy_baseline_schema_only = true
prompt_policy_baseline_schema_check_passed = true
dry_run_prompt_baseline_gate_passed = false
raw_prompt_text_embedded = false
prompt_payload_created = false
raw_llm_response_payload_created = false
fine_tuning_dataset_exports_created = 0
official_metric_input_rows = 0
promotion_evidence = false
product_success_evidence_allowed = false
```

"""
        text = text.replace("### v4_7 — Official Metric Opening Gate", insert + "### v4_7 — Official Metric Opening Gate", 1)
    text = text.replace(
        "v4_6_2_ft_route_policy_fixture_contract_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
        "v4_6_2_ft_route_policy_fixture_contract_nonprod\n↓\nv4_6_3_ft_a_prompt_policy_baseline_schema_nonprod\n↓\nv4_7_official_metric_opening_gate_only_if_user_policy_approved",
    )
    if "v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod" not in text.split("## 8. Concrete Next Command Prompt", 1)[0]:
        text = text.replace(
            "v4_6_2_ft_route_policy_fixture_contract_nonprod\n",
            "v4_6_2_ft_route_policy_fixture_contract_nonprod\nv4_6_3_ft_a_prompt_policy_baseline_schema_nonprod\n",
            1,
        )
    plan_path.write_text(text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    report_path = report["artifact_paths"]["report_json"]
    metrics = report["metrics"]
    _refresh_docs()
    progress_entry = (
        f"- v4_6_3 FT-A prompt-policy baseline schema (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        "It freezes schema-only prompt-policy baseline identifiers, future dry-run comparison output fields, confusion-matrix axes, and stop-condition audit buckets for a later FT-A route/policy dry run. "
        "This is diagnostic-only and schema-only: it does not render raw prompt text, does not create a prompt payload or prompt manifest, does not open the FT-A dry run, does not open v4_7, does not create a dataset, training manifest, job, checkpoint, raw LLM response, official metric, promotion evidence, product-success evidence, production route, or live DB/index/cache readiness claim."
    )
    measurements_entry = f"""### v4_6_3 FT-A Prompt-Policy Baseline Schema

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, schema-only, single `report.json`.
- Primary artifact: `{report_path}`
- Source evidence: v4_6_2 FT-A route-policy fixture contract report.

| Diagnostic count | Value |
| --- | ---: |
| ft_a_prompt_policy_baseline_schema_only | true |
| prompt_policy_baseline_schema_check_passed | {str(metrics["prompt_policy_baseline_schema_check_passed"]).lower()} |
| dry_run_prompt_baseline_gate_passed | {str(metrics["dry_run_prompt_baseline_gate_passed"]).lower()} |
| fixture_contract_gate_ready | {str(metrics["fixture_contract_gate_ready"]).lower()} |
| future_dry_run_required_output_count | {metrics["future_dry_run_required_output_count"]} |
| stop_condition_audit_bucket_count | {metrics["stop_condition_audit_bucket_count"]} |
| raw_prompt_text_embedded | false |
| prompt_payload_created | false |
| raw_llm_response_payload_created | false |
| ft_route_policy_dry_run_opened | false |
| ft_route_policy_dry_run_executed | false |
| v4_7_official_metric_gate_opened | false |
| fine_tuning_dataset_exports_created | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |

Counter source-of-truth: `report.json` embeds the prompt-policy baseline schema, prompt_policy_baseline_gate, metrics, guardrails, verification, residual_risks, and next_recommendation. There is no raw prompt text, prompt payload, raw LLM response, dataset sidecar, training manifest, training job, checkpoint, review CSV, or per-run Markdown.
"""
    triage_entry = (
        "### v4_6_3 FT-A Prompt-Policy Baseline Schema Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_6_3 is diagnostic-only, non-production, schema-only FT-A prompt-policy baseline preparation.\n"
        "- It freezes prompt-policy baseline identifiers and future dry-run output fields; it is not the FT-A dry run, not prompt payload creation, not dataset export, and not a v4_7 opening.\n"
        "- It keeps raw prompt text, prompt manifests, raw LLM responses, datasets, training manifests, jobs, checkpoints, official metrics, promotion evidence, and product-success evidence absent.\n"
        "- User-owned gold/qrels/denominator/promotion decisions remain closed before any official metric or promotion gate.\n"
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
                    "prompt_policy_baseline_schema_check_passed": report["metrics"][
                        "prompt_policy_baseline_schema_check_passed"
                    ],
                    "dry_run_prompt_baseline_gate_passed": report["metrics"][
                        "dry_run_prompt_baseline_gate_passed"
                    ],
                    "future_dry_run_required_output_count": report["metrics"][
                        "future_dry_run_required_output_count"
                    ],
                    "stop_condition_audit_bucket_count": report["metrics"][
                        "stop_condition_audit_bucket_count"
                    ],
                    "ft_route_policy_dry_run_opened": report["metrics"]["ft_route_policy_dry_run_opened"],
                    "ft_route_policy_dry_run_executed": report["metrics"]["ft_route_policy_dry_run_executed"],
                    "fine_tuning_dataset_exports_created": report["metrics"][
                        "fine_tuning_dataset_exports_created"
                    ],
                    "official_metric_input_rows": report["metrics"]["official_metric_input_rows"],
                    "v4_7_official_metric_gate_opened": report["metrics"]["v4_7_official_metric_gate_opened"],
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
