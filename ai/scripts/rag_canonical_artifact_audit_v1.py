"""Audit the current report-only canonical artifact pack.

This is a read-only/report-only generator. It records freshness, guardrail
status, and slim-pack grouping without opening official metrics, mutating
registries, running tuning, or writing production indexes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_CANONICAL_PATHS = {
    "three_track_metric_preflight_board": REPORT_DIR / "three_track_metric_preflight_board.json",
    "hyperparameter_tuning_readiness_plan": REPORT_DIR / "hyperparameter_tuning_readiness_plan.json",
    "report_only_tuning_dry_run_plan": REPORT_DIR / "report_only_tuning_dry_run_plan_v1.json",
    "official_metric_transition_readiness_checklist": REPORT_DIR
    / "official_metric_transition_readiness_checklist_v1.json",
    "human_audit_packet": REVIEW_DIR / "rag_human_audit_packet_v2_question_quality_local_llm.json",
    "human_audit_v2_applied_decisions": REVIEW_DIR / "rag_human_audit_v2_applied_decisions.json",
    "official_denominator_candidate_diff_preview": REPORT_DIR / "official_denominator_candidate_diff_preview_v1.json",
    "official_question_gold_v2_registry_application": REPORT_DIR / "official_question_gold_v2_registry_application_report.json",
    "official_metric_input_config": REPORT_DIR / "metric_input_v1.json",
    "xlsx_answer_citation_policy_packet": REPORT_DIR / "rag_xlsx_answer_citation_policy_review_packet_v1.json",
    "pdf_answer_citation_policy_packet": REPORT_DIR / "rag_pdf_answer_citation_policy_review_packet_v1.json",
    "pdf_evidence_metadata_enrichment": REPORT_DIR / "pdf_evidence_metadata_enrichment_report.json",
    "pdf_layout_gap_closure": REPORT_DIR / "pdf_layout_gap_closure_report.json",
    "pdf_evidence_readiness_repair": REPORT_DIR / "pdf_evidence_readiness_repair_report.json",
    "text_namu_policy_packet": REVIEW_DIR / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json",
    "progress_doc": REPO_ROOT / "docs" / "rag-ingestion-progress.md",
}

DEFAULT_OUTPUT_JSON = REPORT_DIR / "canonical_artifact_audit_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "canonical_artifact_audit_v1.md"
DEFAULT_SLIM_MANIFEST_JSON = REPORT_DIR / "slim_canonical_pack_manifest_v1.json"
DEFAULT_SLIM_MANIFEST_MD = REPORT_DIR / "slim_canonical_pack_manifest_v1.md"
DEFAULT_SCRIPT_PLAN_JSON = REPORT_DIR / "script_simplification_plan_v1.json"
DEFAULT_SCRIPT_PLAN_MD = REPORT_DIR / "script_simplification_plan_v1.md"

CANONICAL_CURRENT_REPORTS = [
    "ai/eval/reports/rag-ingestion/three_track_metric_preflight_board.json",
    "ai/eval/reports/rag-ingestion/three_track_metric_preflight_board.md",
    "ai/eval/reports/rag-ingestion/hyperparameter_tuning_readiness_plan.json",
    "ai/eval/reports/rag-ingestion/hyperparameter_tuning_readiness_plan.md",
    "ai/eval/reports/rag-ingestion/report_only_tuning_dry_run_plan_v1.json",
    "ai/eval/reports/rag-ingestion/report_only_tuning_dry_run_plan_v1.md",
    "ai/eval/reports/rag-ingestion/official_metric_transition_readiness_checklist_v1.json",
    "ai/eval/reports/rag-ingestion/official_metric_transition_readiness_checklist_v1.md",
    "ai/eval/review/rag_human_audit_packet_v2_question_quality_local_llm.json",
    "ai/eval/review/rag_human_audit_packet_v2_question_quality_local_llm.md",
    "ai/eval/review/rag_human_audit_v2_applied_decisions.json",
    "ai/eval/review/rag_human_audit_v2_applied_decisions.md",
    "ai/eval/reports/rag-ingestion/official_denominator_candidate_diff_preview_v1.json",
    "ai/eval/reports/rag-ingestion/official_denominator_candidate_diff_preview_v1.md",
    "ai/eval/reports/rag-ingestion/official_question_gold_v2_registry_application_report.json",
    "ai/eval/reports/rag-ingestion/official_question_gold_v2_registry_application_report.md",
    "ai/eval/reports/rag-ingestion/metric_input_v1.json",
    "ai/eval/reports/rag-ingestion/metric_input_v1.md",
    "docs/rag-ingestion-progress.md",
]

SOURCE_PROOF_REPORTS = [
    "ai/eval/reports/rag-ingestion/rag_xlsx_answer_citation_policy_review_packet_v1.json",
    "ai/eval/reports/rag-ingestion/rag_pdf_answer_citation_policy_review_packet_v1.json",
    "ai/eval/reports/rag-ingestion/pdf_evidence_metadata_enrichment_report.json",
    "ai/eval/reports/rag-ingestion/pdf_layout_gap_closure_report.json",
    "ai/eval/reports/rag-ingestion/pdf_evidence_readiness_repair_report.json",
    "ai/eval/review/rag_text_namu_answer_citation_policy_review_packet_v2_1.json",
]

ARCHIVE_OR_CLEANUP_PATTERNS = [
    "historical/superseded stale board/plan versions showing XLSX leakage FAIL",
    "historical/superseded stale board/plan versions showing PDF strict_ready_rows=0",
    "historical/superseded stale PDF repair reports with SearchUnit id 0",
    "historical/superseded stale XLSX packet reports with leakage FAIL",
    "historical/superseded intermediate one-off preview reports no longer referenced by canonical pack",
    "historical/superseded duplicate JSONL rows except the latest review input needed by packet generation",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_audit(
        canonical_paths=DEFAULT_CANONICAL_PATHS,
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        slim_manifest_report=Path(args.slim_manifest_report),
        slim_manifest_md=Path(args.slim_manifest_md),
        script_plan_report=Path(args.script_plan_report),
        script_plan_md=Path(args.script_plan_md),
    )
    print(
        json.dumps(
            {
                "status": result["audit"]["status"],
                "report": result["audit"]["artifact_paths"]["report_json"],
                "slim_manifest": result["slim_manifest"]["artifact_paths"]["report_json"],
                "script_plan": result["script_plan"]["artifact_paths"]["report_json"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["audit"]["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--slim-manifest-report", default=str(DEFAULT_SLIM_MANIFEST_JSON))
    parser.add_argument("--slim-manifest-md", default=str(DEFAULT_SLIM_MANIFEST_MD))
    parser.add_argument("--script-plan-report", default=str(DEFAULT_SCRIPT_PLAN_JSON))
    parser.add_argument("--script-plan-md", default=str(DEFAULT_SCRIPT_PLAN_MD))
    return parser.parse_args(argv)


def run_audit(
    *,
    canonical_paths: Mapping[str, Path],
    output_report: Path,
    output_md: Path,
    slim_manifest_report: Path,
    slim_manifest_md: Path,
    script_plan_report: Path,
    script_plan_md: Path,
) -> dict[str, dict[str, Any]]:
    payloads = {name: read_json(path) for name, path in canonical_paths.items() if path.suffix == ".json"}
    artifacts = [artifact_record(name, path, payloads.get(name, {})) for name, path in canonical_paths.items()]
    artifact_index = {row["name"]: row for row in artifacts}
    errors = validation_errors(canonical_paths=canonical_paths, payloads=payloads)
    summary = audit_summary(artifacts, payloads)
    audit = {
        "schema_version": "canonical_artifact_audit_v1",
        "generated_at": utc_timestamp(),
        "status": "CANONICAL_ARTIFACT_AUDIT_PASS" if not errors else "CANONICAL_ARTIFACT_AUDIT_FAIL_CLOSED",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_scope": summary["official_metric_input_rows_scope"],
        "registry_backed_official_metric_input_rows": summary["registry_backed_official_metric_input_rows"],
        "registry_backed_official_metric_input_rows_by_track": summary[
            "registry_backed_official_metric_input_rows_by_track"
        ],
        "summary": summary,
        "artifacts": artifacts,
        "artifact_index": artifact_index,
        "stale_conflicts_found": errors,
        "validation": {"ok": not errors, "errors": errors},
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
    }
    slim_manifest = build_slim_manifest(audit)
    slim_manifest["artifact_paths"] = {
        "report_json": repo_relative(slim_manifest_report),
        "report_md": repo_relative(slim_manifest_md),
    }
    script_plan = build_script_plan()
    script_plan["artifact_paths"] = {"report_json": repo_relative(script_plan_report), "report_md": repo_relative(script_plan_md)}
    write_json(output_report, audit)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_audit_markdown(audit), encoding="utf-8")
    write_json(slim_manifest_report, slim_manifest)
    slim_manifest_md.parent.mkdir(parents=True, exist_ok=True)
    slim_manifest_md.write_text(render_manifest_markdown(slim_manifest), encoding="utf-8")
    write_json(script_plan_report, script_plan)
    script_plan_md.parent.mkdir(parents=True, exist_ok=True)
    script_plan_md.write_text(render_script_plan_markdown(script_plan), encoding="utf-8")
    return {"audit": audit, "slim_manifest": slim_manifest, "script_plan": script_plan}


def artifact_record(name: str, path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    exists = path.exists()
    return {
        "name": name,
        "path": repo_relative(path),
        "exists": exists,
        "generated_at": clean(payload.get("generated_at")),
        "sha256": sha256_file(path) if exists else None,
        "schema_version": clean(payload.get("schema_version")),
        "status": clean(payload.get("status")),
        "source_artifacts": payload.get("source_artifacts") if isinstance(payload.get("source_artifacts"), Mapping) else {},
        "official_metric_input_rows": official_rows(payload),
        "promotion_evidence": payload.get("promotion_evidence") is True,
        "tuning_run_started": payload.get("tuning_run_started") is True,
        "official_metrics_closed": payload.get("official_metrics_closed") if "official_metrics_closed" in payload else None,
        "stale_conflict_detected": payload_stale_conflict(name, payload),
        "selected_as_canonical": True,
    }


def validation_errors(*, canonical_paths: Mapping[str, Path], payloads: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    for name, path in canonical_paths.items():
        if not path.exists():
            errors.append(f"missing required canonical file: {name}")
    board = payloads.get("three_track_metric_preflight_board", {})
    readiness = payloads.get("hyperparameter_tuning_readiness_plan", {})
    dry_plan = payloads.get("report_only_tuning_dry_run_plan", {})
    checklist = payloads.get("official_metric_transition_readiness_checklist", {})
    human = payloads.get("human_audit_packet", {})
    applied = payloads.get("human_audit_v2_applied_decisions", {})
    denominator_preview = payloads.get("official_denominator_candidate_diff_preview", {})
    registry_application = payloads.get("official_question_gold_v2_registry_application", {})
    metric_config = payloads.get("official_metric_input_config", {})
    pdf_answer = payloads.get("pdf_answer_citation_policy_packet", {})
    xlsx = payloads.get("xlsx_answer_citation_policy_packet", {})
    pdf_repair = payloads.get("pdf_evidence_readiness_repair", {})
    progress_doc = canonical_paths.get("progress_doc")

    if board and clean(board.get("status")) != "DIAGNOSTIC_PREFLIGHT_READY":
        errors.append("board status must be DIAGNOSTIC_PREFLIGHT_READY")
    if clean(nested_mapping(board, "tracks", "xlsx_business_structured").get("leakage_status")) == "FAIL":
        errors.append("selected board contains stale XLSX leakage FAIL state")
    if nested_int(board, "tracks", "pdf_business_ocr_mm", "strict_gate_readiness_count") == 0:
        errors.append("selected board contains stale PDF strict_ready_rows=0 state")
    if clean(xlsx.get("leakage_raw_status")) == "FAIL":
        errors.append("selected XLSX packet contains stale leakage FAIL state")
    if int_value(pdf_repair.get("strict_ready_rows")) == 0 and pdf_repair:
        errors.append("selected PDF repair report contains stale strict_ready_rows=0 state")
    if clean(board.get("status")) == "DIAGNOSTIC_PREFLIGHT_READY" and not canonical_paths["pdf_answer_citation_policy_packet"].exists():
        errors.append("latest board says ready but PDF answer/citation packet is missing")
    if clean(readiness.get("status")) == "REPORT_ONLY_READY" and not canonical_paths["human_audit_packet"].exists():
        errors.append("latest plan says ready but human audit packet is missing")
    if pdf_plan_answer_ready(dry_plan) and not canonical_paths["pdf_answer_citation_policy_packet"].exists():
        errors.append("dry-run plan treats PDF as answer-ready but PDF answer/citation packet is missing")
    if canonical_paths["pdf_answer_citation_policy_packet"].exists():
        errors.extend(pdf_answer_packet_readiness_errors(pdf_answer))
    for name, payload in payloads.items():
        if official_rows(payload) > 0 and not official_rows_allowed(name, payload):
            errors.append(f"{name} official_metric_input_rows must remain 0")
        if payload.get("promotion_evidence") is True:
            errors.append(f"{name} promotion_evidence must remain false")
        if payload.get("tuning_run_started") is True:
            errors.append(f"{name} tuning_run_started must remain false")
        if cross_track_average_open(payload):
            errors.append(f"{name} cross-track average flags must remain false")
    if clean(dry_plan.get("status")) == "REPORT_ONLY_DRY_RUN_PLAN_READY" and not pdf_answer:
        errors.append("dry-run plan is ready but PDF answer/citation packet payload is unavailable")
    if checklist and checklist.get("official_denominator_registry_opened") is True:
        errors.append("official transition checklist must keep official_denominator_registry_opened=false")
    if human:
        errors.extend(human_audit_v2_errors(human))
        if human.get("human_audit_completed") is True:
            for name in (
                "human_audit_v2_applied_decisions",
                "official_denominator_candidate_diff_preview",
                "official_metric_input_config",
            ):
                if not canonical_paths.get(name) or not canonical_paths[name].exists():
                    errors.append(f"completed human audit requires current artifact: {name}")
    errors.extend(candidate_transition_artifact_errors(applied, denominator_preview, registry_application, metric_config))
    if progress_doc and progress_doc.exists():
        errors.extend(progress_doc_conflicts(progress_doc))
    return sorted(dict.fromkeys(errors))


def progress_doc_conflicts(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []
    for idx, line in enumerate(text.splitlines()):
        context = "\n".join(text.splitlines()[max(0, idx - 3) : idx + 1]).lower()
        historical = (
            ("historical" in context and "without historical" not in context)
            or "superseded" in context
            or "->" in line
        )
        if re.search(r"XLSX\s+leakage\s+FAIL|leakage_raw_status\s*=\s*FAIL", line, flags=re.IGNORECASE) and not historical:
            errors.append("progress doc contradicts current XLSX PASS state")
        if re.search(r"PDF\s+strict_ready_rows\s*=\s*0|strict_ready_rows\s*=\s*0|strict ready rows\s*`0`", line, flags=re.IGNORECASE) and not historical:
            errors.append("progress doc contradicts current PDF strict_ready_rows=7 state")
    return sorted(dict.fromkeys(errors))


def audit_summary(artifacts: list[Mapping[str, Any]], payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    registry_rows_by_track = registry_backed_rows_by_track(payloads)
    registry_rows = sum(registry_rows_by_track.values())
    artifact_duplicate_sum = sum(int_value(row.get("official_metric_input_rows")) for row in artifacts)
    return {
        "artifact_count": len(artifacts),
        "missing_count": sum(1 for row in artifacts if not row["exists"]),
        "official_metric_input_rows_total": registry_rows or artifact_duplicate_sum,
        "official_metric_input_rows_scope": (
            "unique_registry_backed_question_gold_input_rows_not_artifact_duplicate_sum"
            if registry_rows
            else "artifact_field_sum_no_registry_backed_input_detected"
        ),
        "official_metric_input_rows_artifact_duplicate_sum": artifact_duplicate_sum,
        "registry_backed_official_metric_input_rows": registry_rows,
        "registry_backed_official_metric_input_rows_by_track": registry_rows_by_track,
        "promotion_evidence_true_count": sum(1 for row in artifacts if row.get("promotion_evidence") is True),
        "tuning_run_started": any(row.get("tuning_run_started") is True for row in artifacts),
        "stale_conflict_count": sum(1 for row in artifacts if row.get("stale_conflict_detected") is True),
    }


def build_slim_manifest(audit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "slim_canonical_pack_manifest_v1",
        "generated_at": utc_timestamp(),
        "status": "SLIM_CANONICAL_PACK_MANIFEST_READY",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "keep_as_canonical_current_reports": [{"path": path, "selected_as_canonical": True} for path in CANONICAL_CURRENT_REPORTS],
        "keep_as_source_proof_generated_ignored": [{"path": path, "selected_as_source_proof": True} for path in SOURCE_PROOF_REPORTS],
        "archive_or_remove_if_ignored_and_superseded": [
            {"description": item, "action": "external_archive_or_ignored_cleanup_candidate"} for item in ARCHIVE_OR_CLEANUP_PATTERNS
        ],
        "known_noncanonical_stale_docs": [
            {
                "path": "README.md",
                "reason": "README may still mention older blocked states; exclude from freshness-sensitive slim pack until refreshed.",
            }
        ],
        "validation": {
            "ok": True,
            "errors": [],
            "canonical_paths_exclude_stale_blocked_reports": True,
            "audit_status": audit.get("status"),
        },
        "artifact_paths": {"report_json": "", "report_md": ""},
    }


def build_script_plan() -> dict[str, Any]:
    return {
        "schema_version": "script_simplification_plan_v1",
        "generated_at": utc_timestamp(),
        "status": "SCRIPT_SIMPLIFICATION_PLAN_READY",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "groups": {
            "keep_active_generator": [
                "rag_report_only_tuning_dry_run_plan_v1.py",
                "rag_human_audit_packet_v2_question_quality_local_llm.py",
                "rag_human_audit_v2_applied_decisions.py",
                "rag_official_denominator_candidate_diff_preview_v1.py",
                "rag_official_question_gold_v2_registry_apply.py",
                "rag_official_metric_input_config_v1.py",
                "rag_three_track_metric_preflight_board.py",
                "rag_hyperparameter_tuning_readiness_plan.py",
            ],
            "keep_historical_input_generator": [
                "rag_human_audit_packet_v1.py",
            ],
            "keep_guardrail_audit": [
                "rag_canonical_artifact_audit_v1.py",
                "rag_anti_shortcut_guardrail_audit_v1.py",
            ],
            "keep_test_fixture_support": [
                "rag_pdf_answer_citation_diagnostic.py",
                "rag_pdf_answer_citation_policy_review_packet_v1.py",
                "rag_xlsx_answer_citation_policy_review_packet_v1.py",
                "rag_pdf_evidence_readiness_repair.py",
                "rag_pdf_layout_gap_closure.py",
            ],
            "deprecate_wrapper": [],
            "archive_generated_only": ARCHIVE_OR_CLEANUP_PATTERNS,
            "remove_if_ignored_and_unreferenced": [],
        },
        "physical_removal_performed": False,
        "notes": [
            "Do not physically remove implementation scripts in this pass.",
            "Prefer deprecated headers or thin wrappers only after import, CLI, source_artifact, and docs reference scans pass.",
        ],
        "validation": {"ok": True, "errors": []},
        "artifact_paths": {"report_json": "", "report_md": ""},
    }


def render_audit_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# Canonical Artifact Audit v1",
        "",
        f"- Status: `{audit['status']}`",
        f"- Official metric input rows total: `{audit['summary']['official_metric_input_rows_total']}`",
        f"- Official metric input rows scope: `{audit['summary']['official_metric_input_rows_scope']}`",
        f"- Artifact duplicate row-field sum: `{audit['summary']['official_metric_input_rows_artifact_duplicate_sum']}`",
        f"- Tuning run started: `{json.dumps(audit['summary']['tuning_run_started'])}`",
        "",
        "## Validation",
        "",
    ]
    if audit["validation"]["errors"]:
        lines.extend(f"- `{error}`" for error in audit["validation"]["errors"])
    else:
        lines.append("- `PASS`")
    return "\n".join(lines) + "\n"


def render_manifest_markdown(manifest: Mapping[str, Any]) -> str:
    lines = ["# Slim Canonical Pack Manifest v1", "", f"- Status: `{manifest['status']}`", "", "## Canonical Current", ""]
    lines.extend(f"- `{row['path']}`" for row in manifest["keep_as_canonical_current_reports"])
    lines.extend(["", "## Source Proof", ""])
    lines.extend(f"- `{row['path']}`" for row in manifest["keep_as_source_proof_generated_ignored"])
    return "\n".join(lines) + "\n"


def render_script_plan_markdown(plan: Mapping[str, Any]) -> str:
    lines = ["# Script Simplification Plan v1", "", f"- Status: `{plan['status']}`"]
    for group, values in plan["groups"].items():
        lines.extend(["", f"## {group}", ""])
        lines.extend(f"- `{value}`" for value in values)
    return "\n".join(lines).rstrip() + "\n"


def payload_stale_conflict(name: str, payload: Mapping[str, Any]) -> bool:
    if not payload:
        return False
    if name == "three_track_metric_preflight_board":
        return (
            clean(nested_mapping(payload, "tracks", "xlsx_business_structured").get("leakage_status")) == "FAIL"
            or nested_int(payload, "tracks", "pdf_business_ocr_mm", "strict_gate_readiness_count") == 0
        )
    if name == "xlsx_answer_citation_policy_packet":
        return clean(payload.get("leakage_raw_status")) == "FAIL"
    if name == "pdf_evidence_readiness_repair":
        return int_value(payload.get("strict_ready_rows")) == 0
    if name == "pdf_answer_citation_policy_packet":
        return bool(pdf_answer_packet_readiness_errors(payload))
    return False


def pdf_answer_packet_readiness_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not payload:
        return ["PDF answer/citation packet payload is unavailable"]
    if clean(payload.get("status")) != "DIAGNOSTIC_POLICY_PACKET_READY":
        errors.append("PDF answer/citation packet must be DIAGNOSTIC_POLICY_PACKET_READY")
    counts_ready = (
        int_value(payload.get("input_rows")) == 7
        and int_value(payload.get("strict_ready_rows")) == 7
        and int_value(payload.get("generated_answer_rows")) == 7
        and int_value(payload.get("clean_pass_rows")) == 7
        and int_value(payload.get("answer_support_pass_count")) == 7
        and int_value(payload.get("citation_locator_valid_count")) == 7
        and int_value(payload.get("cleanup_rows")) == 0
        and int_value(payload.get("unresolved_rows")) == 0
        and int_value(payload.get("lane_policy_blocked_rows")) == 0
    )
    if not counts_ready:
        errors.append("PDF answer/citation packet must have 7 clean/support/citation rows and 0 lane blockers")
    if nested_mapping(payload, "validation").get("ok") is not True:
        errors.append("PDF answer/citation packet validation.ok must be true")
    return errors


def human_audit_v2_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if clean(payload.get("status")) != "HUMAN_AUDIT_PACKET_V2_READY":
        errors.append("human audit packet must be HUMAN_AUDIT_PACKET_V2_READY")
    if payload.get("official_metric") is True or official_rows(payload) != 0:
        errors.append("human audit packet official rows must remain 0")
    if payload.get("promotion_evidence") is True:
        errors.append("human audit packet must not be promotion evidence")
    validation = human_label_validation(payload)
    errors.extend(validation["errors"])
    if not validation["completed"]:
        errors.append("human audit packet v2 row-level labels must be complete")
    return errors


def candidate_transition_artifact_errors(
    applied: Mapping[str, Any],
    denominator_preview: Mapping[str, Any],
    registry_application: Mapping[str, Any],
    metric_config: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if applied:
        if clean(applied.get("status")) != "HUMAN_AUDIT_V2_APPLIED_DECISIONS_READY":
            errors.append("human audit v2 applied decisions must be ready")
        if nested_mapping(applied, "validation").get("ok") is not True:
            errors.append("human audit v2 applied decisions validation.ok must be true")
    if denominator_preview:
        if clean(denominator_preview.get("status")) != "OFFICIAL_DENOMINATOR_CANDIDATE_DIFF_PREVIEW_READY":
            errors.append("official denominator candidate diff preview must be ready")
        if clean(denominator_preview.get("registry_diff_status")) != "PREVIEW_ONLY_NO_MUTATION":
            errors.append("official denominator candidate diff preview must be preview-only")
        if nested_mapping(denominator_preview, "guardrails").get("official_denominator_registry_changed") is True:
            errors.append("official denominator candidate diff preview must not mutate registry")
        if nested_mapping(denominator_preview, "validation").get("ok") is not True:
            errors.append("official denominator candidate diff preview validation.ok must be true")
    if metric_config:
        if clean(metric_config.get("status")) not in {
            "OFFICIAL_METRIC_INPUT_CONFIG_READY_PENDING_REGISTRY_APPLICATION",
            "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED",
        }:
            errors.append("official metric input config must be ready pending registry application")
        if metric_config.get("official_metric_execution_started") is not False:
            errors.append("official metric input config must not start metric execution")
        if (
            clean(metric_config.get("status")) == "OFFICIAL_METRIC_INPUT_CONFIG_READY_PENDING_REGISTRY_APPLICATION"
            and metric_config.get("metric_execution_allowed") is not False
        ):
            errors.append("official metric input config must not allow execution before registry application")
        if nested_mapping(metric_config, "validation").get("ok") is not True:
            errors.append("official metric input config validation.ok must be true")
    if registry_application:
        if clean(registry_application.get("status")) != "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLIED":
            errors.append("official question gold v2 registry application must be applied")
        if registry_application.get("registry_updated") is not True:
            errors.append("official question gold v2 registry application must update registry")
        if registry_application.get("official_metric_execution_started") is not False:
            errors.append("official question gold v2 registry application must not start metric execution")
        if nested_mapping(registry_application, "validation").get("ok") is not True:
            errors.append("official question gold v2 registry application validation.ok must be true")
    for name, payload in (
        ("human audit v2 applied decisions", applied),
        ("official denominator candidate diff preview", denominator_preview),
        ("official question gold v2 registry application", registry_application),
        ("official metric input config", metric_config),
    ):
        if not payload:
            continue
        if official_rows(payload) != 0 and not (
            name in {"official question gold v2 registry application", "official metric input config"}
            and official_rows_allowed(name, payload)
        ):
            errors.append(f"{name} official_metric_input_rows must remain 0")
        if payload.get("promotion_evidence") is True:
            errors.append(f"{name} promotion_evidence must remain false")
        if payload.get("tuning_run_started") is True:
            errors.append(f"{name} tuning_run_started must remain false")
        guardrails = nested_mapping(payload, "guardrails")
        for key in (
            "official_denominator_registry_mutation",
            "official_denominator_registry_opened",
            "official_metric_executed",
            "gold_registry_mutation",
            "candidate_artifact_mutation",
            "immutable_baseline_mutation",
            "production_namespace_vector_index_mutation",
            "production_vector_written",
        ):
            if payload.get(key) is True or guardrails.get(key) is True:
                if name == "official metric input config" and official_rows_allowed(name, payload) and key in {
                    "official_denominator_registry_mutation",
                    "official_denominator_registry_opened",
                }:
                    continue
                errors.append(f"{name} guardrail {key} must remain false")
    return errors


def official_rows_allowed(name: str, payload: Mapping[str, Any]) -> bool:
    if name == "official_question_gold_v2_registry_application" or name == "official question gold v2 registry application":
        return (
            clean(payload.get("status")) == "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLIED"
            and payload.get("registry_updated") is True
            and payload.get("official_metric_execution_started") is False
            and payload.get("promotion_evidence") is not True
        )
    if name in {
        "official_metric_input_config",
        "official metric input config",
        "report_only_tuning_dry_run_plan",
        "official_metric_transition_readiness_checklist",
        "three_track_metric_preflight_board",
    }:
        return (
            clean(payload.get("status"))
            in {
                "OFFICIAL_METRIC_INPUT_CONFIG_READY_REGISTRY_BACKED_NOT_EXECUTED",
                "REPORT_ONLY_DRY_RUN_PLAN_READY",
                "OFFICIAL_METRIC_INPUT_READY_NOT_EXECUTED",
                "DIAGNOSTIC_PREFLIGHT_READY",
            }
            and (
                payload.get("metric_input_config_registry_backed") is True
                or nested_mapping(payload, "guardrails").get("official_metric_input_rows_registry_backed") is True
                or payload.get("registry_application_status") == "APPLIED"
            )
            and payload.get("official_metric_execution_started") is not True
            and payload.get("promotion_evidence") is not True
        )
    return False


def human_label_validation(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("actionable_rows") or [] if isinstance(row, Mapping)]
    if not rows:
        return {"completed": False, "errors": [], "counts": {}}
    errors: list[str] = []
    counts: Counter[str] = Counter()
    missing: list[str] = []
    invalid: list[str] = []
    for row in rows:
        qid = clean(row.get("query_id") or row.get("row_id"))
        label = clean(row.get("human_label"))
        allowed = row.get("allowed_decision_values") if isinstance(row.get("allowed_decision_values"), list) else []
        allowed_values = {clean(value) for value in allowed}
        if not label:
            missing.append(qid)
            continue
        counts[label] += 1
        if label not in allowed_values:
            invalid.append(qid)
    if missing:
        errors.append(f"human audit packet rows missing human_label: {', '.join(missing)}")
    if invalid:
        errors.append(f"human audit packet rows have invalid human_label: {', '.join(invalid)}")
    summary = nested_mapping(payload, "summary")
    if "human_labeled_rows" in summary and int_value(summary.get("human_labeled_rows")) != sum(counts.values()):
        errors.append("human audit packet human_labeled_rows summary mismatch")
    if "human_unlabeled_rows" in summary and int_value(summary.get("human_unlabeled_rows")) != len(missing):
        errors.append("human audit packet human_unlabeled_rows summary mismatch")
    expected_counts = payload.get("human_audit_label_counts")
    if isinstance(expected_counts, Mapping):
        normalized_expected = {clean(key): int_value(value) for key, value in expected_counts.items()}
        if normalized_expected != dict(sorted(counts.items())):
            errors.append("human audit packet human_audit_label_counts mismatch")
    return {"completed": bool(rows) and not missing and not invalid, "errors": errors, "counts": dict(sorted(counts.items()))}


def pdf_plan_answer_ready(plan: Mapping[str, Any]) -> bool:
    return (
        clean(plan.get("status")) == "REPORT_ONLY_DRY_RUN_PLAN_READY"
        and clean(nested_mapping(plan, "track_dev_set_policy", "pdf_business_ocr_mm").get("answer_citation_dry_run_eligibility"))
        == "eligible"
    )


def official_rows(payload: Mapping[str, Any]) -> int:
    values = [
        int_value(payload.get("official_metric_input_rows")),
        int_value(nested_mapping(payload, "diagnostic_metric_preview").get("official_metric_input_rows")),
        int_value(nested_mapping(payload, "guardrails").get("official_metric_input_rows")),
    ]
    by_track = payload.get("official_metric_input_rows_by_track")
    if isinstance(by_track, Mapping):
        values.append(sum(int_value(value) for value in by_track.values()))
    return max(values) if values else 0


def registry_backed_rows_by_track(payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    for name in (
        "official_metric_input_config",
        "official_question_gold_v2_registry_application",
        "report_only_tuning_dry_run_plan",
        "official_metric_transition_readiness_checklist",
        "three_track_metric_preflight_board",
    ):
        payload = payloads.get(name, {})
        if not payload or not official_rows_allowed(name, payload):
            continue
        by_track = payload.get("official_metric_input_rows_by_track")
        if isinstance(by_track, Mapping):
            normalized = {clean(key): int_value(value) for key, value in by_track.items() if int_value(value)}
            if normalized:
                return dict(sorted(normalized.items()))
        nested_by_track = nested_mapping(payload, "registry_backed_official_metric_input_rows_by_track")
        if nested_by_track:
            normalized = {clean(key): int_value(value) for key, value in nested_by_track.items() if int_value(value)}
            if normalized:
                return dict(sorted(normalized.items()))
    return {}


def cross_track_average_open(payload: Mapping[str, Any]) -> bool:
    return any(
        value is True
        for value in (
            payload.get("cross_track_average_optimization_allowed"),
            payload.get("cross_track_averages_computed"),
            nested_mapping(payload, "split_policy").get("cross_track_average_computed"),
        )
    )


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def nested_int(payload: Mapping[str, Any], *keys: str) -> int:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return 0
        current = current.get(key)
    return int_value(current)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.suffix != ".json":
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def int_value(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def clean(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
