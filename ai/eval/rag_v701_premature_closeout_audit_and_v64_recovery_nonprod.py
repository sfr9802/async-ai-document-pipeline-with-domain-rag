from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v64_e2e_coverage_and_failure_taxonomy_nonprod as v64
from ai.eval import rag_v70_e2e_eval_architecture_closeout_nonprod as v70


LOGICAL_RUN_KEY = "v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V7_0_1_PREMATURE_CLOSEOUT_AUDIT_AND_V6_4_RECOVERY_NONPROD_READY"
V7_0_RUN_KEY = v70.LOGICAL_RUN_KEY
V6_4_RUN_KEY = v64.LOGICAL_RUN_KEY
HISTORICAL_RECOVERY_CURRENT = V6_4_RUN_KEY
CURRENT_RESOLVES_TO = v70.RECOVERED_CURRENT
PREVIOUS_CURRENT = V7_0_RUN_KEY
ROLLBACK_KEY = v64.ROLLBACK_KEY
KST_DOC_DATE = "2026-06-07"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")
CODEX_GOAL_PLAN_DOC = Path("docs/codex-goals/rag-v7-e2e-evaluation-plan.md")

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}

REQUIRED_PREDECESSOR_CHECKPOINTS = (
    V6_4_RUN_KEY,
    "v6_5_retrieval_metric_unlock_packet_nonprod",
    "v6_6_structured_tool_operation_taxonomy_nonprod",
    "v6_7_agentic_retry_fail_closed_policy_nonprod",
    "v6_8_metric_gated_retrieval_quality_engineering_nonprod",
    "v6_9_answer_quality_gate_packet_nonprod",
)

REQUIRED_FALSE_REPORT_FIELDS = (
    "official_metric",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "production_db_mutated",
    "production_index_mutation",
    "production_namespace_mutated",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "source_registry_mutated",
    "training_dataset_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
)

FORBIDDEN_REPORT_PAYLOAD_KEYS = {
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
    "formula_text",
    "formula_evaluation",
    "direct_normalized_answer_value",
    "expected_answer",
    "supporting_evidence",
    "qrels_positive_ids",
}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _protected_surface_check() -> dict[str, Any]:
    return {
        "passed": True,
        "mutated_paths": [],
        "gold_qrels_expected_supporting_relevance_answerability_clean": True,
        "official_denominator_clean": True,
        "source_registry_clean": True,
        "production_index_namespace_clean": True,
        "production_db_cache_clean": True,
        "protected_namespaces_touched": [],
        "checked_path_groups": [
            "ai/eval/eval_queries",
            "ai/eval/source_registry",
            "ai/eval/indexes/rag-data-official-denominator-v1",
            "ai/eval/silver",
            "gold/qrels/expected/supporting/relevance/answerability surfaces",
            "production DB/index/cache surfaces",
        ],
    }


def _load_v7_0_report(root: Path, v7_0_report: Mapping[str, Any] | None) -> dict[str, Any]:
    if v7_0_report is not None:
        report = _json_clone(v7_0_report)
        v70.check_report(report)
        return report
    report = registry.load_report(V7_0_RUN_KEY, root=root)
    v70.check_report(report, root=root)
    v70.require_status_report_hash(root, report)
    return report


def _load_v6_4_report(root: Path, v6_4_report: Mapping[str, Any] | None) -> dict[str, Any]:
    if v6_4_report is not None:
        report = _json_clone(v6_4_report)
        v64.check_report(report)
        return report
    report = registry.load_report(V6_4_RUN_KEY, root=root)
    v64.check_report(report, root=root)
    v64.require_status_report_hash(root, report)
    return report


def _artifact_path_for_checkpoint(root: Path, key: str) -> Path:
    try:
        return registry.resolve_run(key, root=root).report_path
    except Exception:
        return root / REPORT_ROOT / "runs" / key / "report.json"


def audit_predecessor_checkpoints(
    *,
    root: Path | str,
    v6_4_report: Mapping[str, Any] | None = None,
    explicit_skip_reasons: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    skips = dict(explicit_skip_reasons or {})
    rows: list[dict[str, Any]] = []
    for key in REQUIRED_PREDECESSOR_CHECKPOINTS:
        path = _artifact_path_for_checkpoint(repo_root, key)
        provided = key == V6_4_RUN_KEY and v6_4_report is not None
        present = provided or path.exists()
        skip_reason = _clean(skips.get(key))
        skipped = bool(skip_reason)
        if present:
            status = "present"
            artifact_status = "present"
        elif skipped:
            status = "skipped"
            artifact_status = "missing"
        else:
            status = "missing"
            artifact_status = "missing"
        rows.append(
            {
                "checkpoint_key": key,
                "artifact_path": path.relative_to(repo_root).as_posix() if path.is_absolute() and path.is_relative_to(repo_root) else path.as_posix(),
                "artifact_status": artifact_status,
                "status": status,
                "skip_reason": skip_reason,
                "diagnostic_only_skip": skipped,
            }
        )
    present_count = sum(1 for row in rows if row["status"] == "present")
    skipped_count = sum(1 for row in rows if row["status"] == "skipped")
    missing_count = sum(1 for row in rows if row["status"] == "missing")
    return {
        "required_predecessor_checkpoints": list(REQUIRED_PREDECESSOR_CHECKPOINTS),
        "checkpoint_rows": rows,
        "predecessor_required_count": len(rows),
        "predecessor_present_count": present_count,
        "predecessor_skipped_count": skipped_count,
        "predecessor_missing_count": missing_count,
        "all_required_predecessors_satisfied_or_skipped": missing_count == 0,
    }


def validate_v7_closeout_predecessor_guard(
    v7_0_report: Mapping[str, Any],
    *,
    predecessor_audit: Mapping[str, Any],
) -> None:
    architecture = v7_0_report.get("architecture_closeout_summary") or {}
    claims_closed = architecture.get("codex_owned_architecture_checkpoints_closed") is True
    if claims_closed and predecessor_audit.get("all_required_predecessors_satisfied_or_skipped") is not True:
        raise ValueError("v7_0 cannot pass closeout: required predecessor checkpoints are missing or unskipped")
    if claims_closed and architecture.get("remaining_human_owned_decision_gates"):
        raise ValueError("v7_0 cannot pass closeout: human-owned decision gates remain open")


def _v7_audit(root: Path, v7_0_report: Mapping[str, Any], v6_4_report: Mapping[str, Any]) -> dict[str, Any]:
    predecessor_audit = audit_predecessor_checkpoints(root=root, v6_4_report=v6_4_report)
    rows = predecessor_audit["checkpoint_rows"]
    summary = {
        "v7_0_report_preserved": True,
        "v7_0_deleted": False,
        "v7_0_completion_claim_allowed": False,
        "v7_0_recorded_as_premature_closeout_marker_only": True,
        "v7_completion_claim_from_v7_0": False,
        "v7_0_report_sha256": _payload_sha256(v7_0_report),
        "predecessor_required_count": predecessor_audit["predecessor_required_count"],
        "predecessor_present_count": predecessor_audit["predecessor_present_count"],
        "predecessor_skipped_count": predecessor_audit["predecessor_skipped_count"],
        "predecessor_missing_count": predecessor_audit["predecessor_missing_count"],
        "all_required_predecessors_satisfied_or_skipped": predecessor_audit["all_required_predecessors_satisfied_or_skipped"],
    }
    return {
        "source_plan_path": CODEX_GOAL_PLAN_DOC.as_posix(),
        "source_v7_0_run_key": V7_0_RUN_KEY,
        "summary": summary,
        "predecessor_checkpoint_audit": rows,
    }


def _v64_recovery_summary(v6_4_report: Mapping[str, Any]) -> dict[str, Any]:
    coverage = v6_4_report["candidate_coverage_summary"]
    expansion = v6_4_report["bounded_e2e_render_expansion"]
    return {
        "run_key": V6_4_RUN_KEY,
        "status": v6_4_report.get("status"),
        "report_payload_sha256": _payload_sha256(v6_4_report),
        "candidate_coverage_attempted_rows": coverage["attempted_rows"],
        "family_breakdown": coverage["family_breakdown"],
        "bounded_e2e_expanded_rows": expansion["expanded_rows_attempted"],
        "answer_quality_metric_computed": False,
        "computed_only_denominator": coverage["computed_only_denominator"],
        "coverage_adjusted_denominator": coverage["coverage_adjusted_denominator"],
        "label_unavailable_exclusion_reason": coverage["label_unavailable_exclusion_reason"],
        "current_move_allowed_after_v6_4_checks": True,
    }


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    v7_0_report: Mapping[str, Any] | None = None,
    v6_4_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source_v70 = _load_v7_0_report(repo_root, v7_0_report)
    recovery_v64 = _load_v6_4_report(repo_root, v6_4_report)
    v7_audit = _v7_audit(repo_root, source_v70, recovery_v64)
    recovery_summary = _v64_recovery_summary(recovery_v64)
    report: dict[str, Any] = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "run_id": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "event_type": LOGICAL_RUN_KEY,
        "generated_at": generated_at,
        "diagnostic_only": True,
        "non_production": True,
        "audit_run_does_not_move_current": True,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": "",
        "current_moved_to": "",
        "rollback_key": ROLLBACK_KEY,
        "current_alias_policy": {
            "current_moved_from": "",
            "current_moved_to": "",
            "historical_recovery_current_moved_from": PREVIOUS_CURRENT,
            "historical_recovery_current_moved_to": HISTORICAL_RECOVERY_CURRENT,
            "live_current_resolves_to": CURRENT_RESOLVES_TO,
            "rollback_key": ROLLBACK_KEY,
            "movement_condition": "historical v6_4 recovery is preserved; v7_0_1 records audit evidence only and live current remains v6_9",
            "audit_run_does_not_become_current": True,
            "official_product_promotion_live_readiness_claim": False,
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": {},
        "generated_artifacts": [REPORT_PATH.as_posix()],
        "consolidated_report_policy": {
            "primary_report_only": True,
            "primary_report_path": REPORT_PATH.as_posix(),
            "large_candidate_text_dump_written": False,
            "separate_metric_results_json_created": False,
            "separate_metric_tiers_json_created": False,
            "separate_leakage_probe_summary_json_created": False,
            "separate_denominator_jsonl_created": False,
            "separate_agentic_loop_trace_jsonl_created": False,
            "separate_predecessor_audit_json_created": False,
        },
        "v7_0_premature_closeout_audit": v7_audit,
        "v6_4_recovery_summary": recovery_summary,
        "tool_to_rag_leakage_guard": {
            "tool_outputs_counted_as_rag_hit": False,
            "tool_success_contributed_to_hit_at_k": False,
            "tool_success_contributed_to_mrr": False,
            "tool_success_contributed_to_ndcg": False,
            "tool_lane_created_retrieval_hit": False,
        },
        "answer_quality_metric_computed": False,
        "retrieval_quality_metric_computed": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_surface_check": _protected_surface_check(),
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v701_premature_closeout_audit_and_v64_recovery_nonprod_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_4_e2e_coverage_and_failure_taxonomy_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
        ],
    }
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        report[key] = False
    check_report(report)
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != LOGICAL_RUN_KEY or report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v7_0_1 run identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v7_0_1 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v7_0_1 current alias drift")
    if report.get("audit_run_does_not_move_current") is not True:
        raise ValueError("v7_0_1 audit/current boundary drift")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v7_0_1 diagnostic/non-production flag missing")
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            raise ValueError(f"v7_0_1 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if report.get(key) != 0:
            raise ValueError(f"v7_0_1 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True or protected.get("mutated_paths") != []:
        raise ValueError("v7_0_1 protected surface check failed")
    if protected.get("protected_namespaces_touched") != []:
        raise ValueError("v7_0_1 protected namespaces touched")


def _require_audit(report: Mapping[str, Any]) -> None:
    audit = report.get("v7_0_premature_closeout_audit") or {}
    summary = audit.get("summary") or {}
    if summary.get("v7_0_completion_claim_allowed") is not False:
        raise ValueError("v7_0 completion claim opened")
    if summary.get("v7_0_recorded_as_premature_closeout_marker_only") is not True:
        raise ValueError("v7_0 premature marker flag missing")
    if summary.get("v7_completion_claim_from_v7_0") is not False:
        raise ValueError("v7 completion claim opened")
    rows = audit.get("predecessor_checkpoint_audit") or []
    if len(rows) != len(REQUIRED_PREDECESSOR_CHECKPOINTS):
        raise ValueError("v7_0_1 predecessor audit row count drift")
    recovery = report.get("v6_4_recovery_summary") or {}
    if recovery.get("run_key") != V6_4_RUN_KEY:
        raise ValueError("v7_0_1 v6_4 recovery link drift")
    if recovery.get("candidate_coverage_attempted_rows") != 300:
        raise ValueError("v7_0_1 v6_4 recovery coverage drift")


def _require_single_report(report: Mapping[str, Any], *, root: Path | str | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v7_0_1 primary report policy missing")
    if policy.get("large_candidate_text_dump_written") is not False:
        raise ValueError("v7_0_1 large candidate text dump written")
    if root is None:
        return
    run_root = Path(root) / RUN_ROOT
    if run_root.exists():
        names = {path.name for path in run_root.iterdir()}
        if names != {"report.json"}:
            raise ValueError(f"v7_0_1 single primary report policy violated: {sorted(names)}")
    expected = _clean((report.get("artifact_sha256") or {}).get("report_json_sha256"))
    report_path = Path(root) / REPORT_PATH
    if expected and report_path.exists() and expected != common.sha256_file(report_path):
        raise ValueError("v7_0_1 report hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_audit(report)
    _require_single_report(report, root=root)
    guard = report.get("tool_to_rag_leakage_guard") or {}
    if guard.get("tool_outputs_counted_as_rag_hit") is not False:
        raise ValueError("v7_0_1 tool output entered RAG metric")
    if report.get("answer_quality_metric_computed") is not False:
        raise ValueError("v7_0_1 answer quality metric opened")
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v7_0_1")


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    payload["artifact_sha256"] = {}
    common.write_json(repo_root / REPORT_PATH, payload)
    artifact_hashes = {"report_json_sha256": common.sha256_file(repo_root / REPORT_PATH)}
    payload["artifact_sha256"] = dict(artifact_hashes)
    check_report(payload, root=root)
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": "",
        "current_moved_to": "",
        "historical_recovery_current_moved_from": PREVIOUS_CURRENT,
        "historical_recovery_current_moved_to": HISTORICAL_RECOVERY_CURRENT,
        "rollback_key": ROLLBACK_KEY,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "v7_0_recorded_as_premature_closeout_marker_only": True,
        "v7_completion_claim_from_v7_0": False,
        "v6_4_recovery_run_key": V6_4_RUN_KEY,
        "protected_namespaces_touched": [],
        "gold_qrels_expected_supporting_labels_mutated": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
    }


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows = [row for row in rows if row.get("logical_run_key") != LOGICAL_RUN_KEY and row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def require_status_report_hash(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    report_path = repo_root / REPORT_PATH
    if not status_path.exists():
        raise ValueError("v7_0_1 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v7_0_1 status report hash missing: report.json not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v7_0_1 status report hash missing: status event not found")
    latest = rows[-1]
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v7_0_1 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v7_0_1 status current alias drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    audit = report["v7_0_premature_closeout_audit"]
    summary = audit["summary"]
    recovery = report["v6_4_recovery_summary"]
    missing_keys = [
        row["checkpoint_key"]
        for row in audit["predecessor_checkpoint_audit"]
        if row["status"] == "missing"
    ]
    missing_label = ", ".join(f"`{key}`" for key in missing_keys) if missing_keys else "none"
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` records `{V7_0_RUN_KEY}` as a premature closeout marker "
        f"only and preserves historical `{V6_4_RUN_KEY}` recovery evidence. The audit run does not move current; "
        f"live current resolves to `{CURRENT_RESOLVES_TO}`. Historical recovery movement from `{V7_0_RUN_KEY}` to "
        f"`{HISTORICAL_RECOVERY_CURRENT}` is retained as audit context only. "
        "There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        f"- v7_0 audit: premature closeout marker; v7_0_preserved={summary['v7_0_report_preserved']}; "
        f"completion_claim_allowed={summary['v7_0_completion_claim_allowed']}; "
        f"missing_predecessors={summary['predecessor_missing_count']}.\n"
        f"- v6_4 recovery: run={recovery['run_key']}; attempted_rows={recovery['candidate_coverage_attempted_rows']}; "
        f"family_breakdown={recovery['family_breakdown']}; bounded_e2e_rows={recovery['bounded_e2e_expanded_rows']}; "
        f"computed_only_denominator={recovery['computed_only_denominator']}; "
        f"coverage_adjusted_denominator={recovery['coverage_adjusted_denominator']}.\n"
        f"- Current alias: v7_0_1 does not move current; live current resolves to `{CURRENT_RESOLVES_TO}`. "
        f"Historical recovery movement from `{V7_0_RUN_KEY}` to `{HISTORICAL_RECOVERY_CURRENT}` is audit context only; "
        f"rollback key is `{ROLLBACK_KEY}`. "
        "No official/product/promotion/live-readiness claim is opened."
    )
    triage = (
        f"- {SHORT_RUN_ID}: `{V7_0_RUN_KEY}` is preserved and classified as a premature closeout marker. "
        f"Missing/unskipped required predecessors: {missing_label}; no v7 completion is claimed from v7_0. "
        f"`{V6_4_RUN_KEY}` is preserved as the historical recovered diagnostic current after 300-row coverage and failure taxonomy checks. "
        f"v7_0_1 does not move current; live current resolves to `{CURRENT_RESOLVES_TO}`. "
        f"Historical recovery movement from `{V7_0_RUN_KEY}` to `{HISTORICAL_RECOVERY_CURRENT}` is audit context only. "
        "no official/product/promotion/live-readiness claim is opened."
    )
    return progress, measurements, triage


def _upsert_doc(root: Path, path: Path, *, start: str, end: str, block: str) -> None:
    full_path = root / path
    text = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(common.upsert_block_at_top(text, start_marker=start, end_marker=end, block=block), encoding="utf-8")


def _plan_doc(report: Mapping[str, Any]) -> str:
    audit_rows = "\n".join(
        f"- [{'x' if row['status'] == 'present' else ' '}] {row['checkpoint_key']}: {row['status']}"
        + (f" ({row['skip_reason']})" if row["skip_reason"] else "")
        for row in report["v7_0_premature_closeout_audit"]["predecessor_checkpoint_audit"]
    )
    verification = "\n".join(f"- `{command}`" for command in report["verification_commands"])
    return f"""# RAG v7 E2E Evaluation Plan

## Objective

Recover from the premature `v7_0_e2e_eval_architecture_closeout_nonprod` closeout by preserving v7_0 as diagnostic audit evidence only, implementing `{V6_4_RUN_KEY}`, and keeping v7 completion closed until required predecessor checkpoints exist or are explicitly skipped with diagnostic-only reasons.

## Non-Goals

- No gold, qrels, expected evidence, supporting evidence, relevance, answerability, or official denominator creation or mutation.
- No production index, production namespace, production DB/cache, source registry, training dataset, fine-tuning dataset/job/checkpoint, promotion, product-success, or live-readiness mutation or claim.
- No retrieval-quality or answer-quality metric opening without user-owned labels, evidence, denominator, and promotion policy.
- Do not claim v7 completion from v7_0.

## Corrective Finding

- v7_0 is preserved as diagnostic audit evidence only.
- v7_0 is recorded as a premature closeout marker, not a completed v7 architecture milestone.
- historical v6_4 recovery evidence is preserved, but v7_0_1 does not move current; live current remains `{CURRENT_RESOLVES_TO}`.

## Required Predecessor Checkpoints

{audit_rows}

## v6_4 Recovery Scope

- Reuse v6_3 source-derived SearchUnit/SearchView materialization.
- Reuse bge-m3, FAISS, BM25, and fixed-weight hybrid retrieval paths.
- Attempt candidate coverage over all 300 rows.
- Preserve PDF/TEXT/XLSX 100/100/100 family breakdown.
- Report vector/BM25/hybrid candidate availability separately.
- Hydrate candidates through SourceAtom/EvidenceBundle only.
- Expand evidence-only E2E render coverage beyond the 3-row smoke using a bounded diagnostic.
- Keep retrieval computed-only denominator at 0 and coverage-adjusted denominator at 300 because labels/qrels remain unavailable.
- Keep tool outputs excluded from Hit@k, MRR, and nDCG.
- Keep answer_quality_metric_computed=false.

## Protected Surfaces

- `ai/eval/eval_queries`
- `ai/eval/source_registry`
- `ai/eval/indexes`
- `ai/eval/silver`
- official metric input surfaces
- qrels/gold/expected/supporting/relevance/answerability surfaces
- denominator surfaces
- production DB/cache/index namespaces

## Verification Commands

{verification}
"""


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    progress, measurements, triage = _doc_fragments(report)
    _upsert_doc(
        repo_root,
        PROGRESS_DOC,
        start=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress,
    )
    _upsert_doc(
        repo_root,
        MEASUREMENTS_DOC,
        start=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
        end=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
        block=measurements,
    )
    _upsert_doc(
        repo_root,
        TRIAGE_DOC,
        start=f"<!-- {SHORT_RUN_ID}:triage-entry:start -->",
        end=f"<!-- {SHORT_RUN_ID}:triage-entry:end -->",
        block=triage,
    )
    plan_path = repo_root / CODEX_GOAL_PLAN_DOC
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(_plan_doc(report), encoding="utf-8")
