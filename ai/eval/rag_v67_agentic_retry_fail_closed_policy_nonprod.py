from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v651_gold29_actual_response_smoke_nonprod as v651
from ai.eval import rag_v66_structured_tool_operation_taxonomy_nonprod as v66


LOGICAL_RUN_KEY = "v6_7_agentic_retry_fail_closed_policy_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_7_AGENTIC_RETRY_FAIL_CLOSED_POLICY_NONPROD_READY"
PREVIOUS_CURRENT = v66.LOGICAL_RUN_KEY
CURRENT_RESOLVES_TO = LOGICAL_RUN_KEY
ROLLBACK_KEY = PREVIOUS_CURRENT

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}
FAMILIES = ("PDF", "TEXT", "XLSX")
V7_REMAINING_PREDECESSORS = (
    "v6_8_metric_gated_retrieval_quality_engineering_nonprod",
    "v6_9_answer_quality_gate_packet_nonprod",
)
REQUIRED_FALSE_REPORT_FIELDS = (
    "official_metric",
    "agentic_loop_metric_computed",
    "answer_quality_metric_computed",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "production_db_mutated",
    "production_index_mutation",
    "production_namespace_mutated",
    "production_cache_mutated",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "official_denominator_mutation",
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
    "expected_answer",
    "expected_answer_text",
    "supporting_evidence",
    "supporting_evidence_ids",
    "qrels_positive_ids",
    "qrels_positive_candidate_ids",
    "target_search_unit_id",
    "source_title",
    "source_file_name",
    "workbook",
    "row_id",
    "case_id",
}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _protected_surface_check() -> dict[str, Any]:
    return v651._protected_surface_check()  # type: ignore[attr-defined]


def _load_v66(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v66.LOGICAL_RUN_KEY, root=root)
    v66.check_report(source, root=root if report is None else None)
    if report is None:
        v66.require_status_report_hash(root, source)
    return source


def _load_v651(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v651.LOGICAL_RUN_KEY, root=root)
    v651.check_report(source, root=root if report is None else None)
    if report is None:
        v651.require_status_report_hash(root, source)
    return source


def _source_v66_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    summary = source["tool_operation_summary"]
    return {
        "run_key": v66.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "tool_operation_rows": summary["tool_operation_rows"],
        "tool_supported_rows": summary["tool_supported_rows"],
        "tool_executed_rows": summary["tool_executed_rows"],
        "tool_metric_official": summary["tool_metric_official"],
        "tool_outputs_excluded_from_true_rag_metrics": source.get("tool_outputs_excluded_from_true_rag_metrics") is True,
    }


def _selected_path(response_row: Mapping[str, Any], tool_row: Mapping[str, Any]) -> str:
    if response_row.get("answer_rendered") is not True:
        return "none_fail_closed"
    if tool_row.get("tool_required") is True:
        return "rag_then_tool"
    return "rag_only"


def _verification_state(response_row: Mapping[str, Any]) -> str:
    if response_row.get("citation_verified") is True:
        return "passed"
    if response_row.get("answer_rendered") is True:
        return "failed"
    return "skipped_no_answer"


def _build_agentic_rows(v651_report: Mapping[str, Any], v66_report: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tool_by_hash = {row["gold_row_hash"]: row for row in v66_report["tool_operation_rows"]}
    rows: list[dict[str, Any]] = []
    family_counter: Counter[str] = Counter()
    path_counter: Counter[str] = Counter()
    verification_counter: Counter[str] = Counter()
    for response_row in v651_report["response_diagnostics"]:
        gold_hash = response_row["gold_row_hash"]
        tool_row = tool_by_hash[gold_hash]
        family = _clean(response_row.get("source_family"))
        selected_path = _selected_path(response_row, tool_row)
        verification = _verification_state(response_row)
        family_counter[family] += 1
        path_counter[selected_path] += 1
        verification_counter[verification] += 1
        fail_reason = _clean(response_row.get("fail_closed_reason"))
        if not fail_reason and verification == "failed":
            fail_reason = "verification_failed"
        rows.append(
            {
                "gold_row_hash": gold_hash,
                "source_family": family,
                "query_hash": response_row["query_hash"],
                "selected_path": selected_path,
                "rag_attempted": int(response_row.get("candidate_count") or 0) > 0,
                "tool_attempted": False,
                "verification_state": verification,
                "retry_count": 0,
                "retry_reason": "",
                "final_answer_rendered": response_row.get("answer_rendered") is True,
                "final_citation_verified": response_row.get("citation_verified") is True,
                "fail_closed_reason": fail_reason,
                "expected_supporting_qrels_used_in_loop": False,
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
                "source_tool_operation_state": tool_row["operation_state"],
                "source_route_hash": hashlib.sha256(_clean(response_row.get("route_decision")).encode("utf-8")).hexdigest(),
            }
        )
    summary = {
        "agentic_loop_rows": len(rows),
        "silently_dropped_rows": 29 - len(rows),
        "rows_by_family": _counter_dict(family_counter),
        "selected_path_counts": {key: int(path_counter.get(key, 0)) for key in ("rag_only", "tool_only", "rag_then_tool", "tool_then_rag", "none_fail_closed")},
        "verification_state_counts": {key: int(verification_counter.get(key, 0)) for key in ("passed", "failed", "skipped_no_answer", "not_applicable")},
        "retry_attempted_rows": sum(1 for row in rows if row["retry_count"]),
        "expected_supporting_qrels_used_in_loop_count": 0,
        "final_answer_rendered_rows": sum(1 for row in rows if row["final_answer_rendered"]),
        "final_citation_verified_rows": sum(1 for row in rows if row["final_citation_verified"]),
        "fail_closed_rows": sum(1 for row in rows if row["fail_closed_reason"]),
    }
    return rows, summary


def _agentic_retry_policy() -> dict[str, Any]:
    return {
        "max_retry_count": 0,
        "retry_requires_new_allowed_signal": True,
        "retry_may_use_expected_or_qrels": False,
        "selection_may_use_expected_or_qrels": False,
        "fail_closed_on_verification_failure": True,
        "retry_signal_sources": ["new_candidate_availability", "new_tool_surface_availability"],
        "human_owned_quality_decisions_required_before_answer_metric": True,
    }


def _candidate_generation_policy() -> dict[str, Any]:
    return {
        "allowed_fields": ["query_text", "source_family", "top_k", "tool_availability_state"],
        "expected_supporting_qrels_used_for_selection_or_retry": False,
        "target_ids_used_for_selection_or_retry": False,
        "row_or_case_ids_used_for_selection_or_retry": False,
        "prior_route_diagnostics_used_for_selection_or_retry": False,
        "tool_outputs_used_for_true_rag_metric": False,
        "forbidden_fields_present_in_agentic_loop_count": 0,
    }


def _tool_to_rag_guard() -> dict[str, Any]:
    return {
        "tool_outputs_counted_as_rag_hit": False,
        "tool_success_contributed_to_hit_at_k": False,
        "tool_success_contributed_to_mrr": False,
        "tool_success_contributed_to_ndcg": False,
        "agentic_path_choice_counted_as_answer_quality": False,
    }


def _v7_guard() -> dict[str, Any]:
    return {
        "v7_0_recorded_as_premature_closeout_marker_only": True,
        "v7_completion_claim_from_v7_0": False,
        "missing_or_unskipped_predecessors": list(V7_REMAINING_PREDECESSORS),
    }


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    v6_6_report: Mapping[str, Any] | None = None,
    v6_5_1_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source_v66 = _load_v66(repo_root, v6_6_report)
    source_v651 = _load_v651(repo_root, v6_5_1_report)
    rows, summary = _build_agentic_rows(source_v651, source_v66)
    report: dict[str, Any] = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "run_id": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at,
        "diagnostic_only": True,
        "non_production": True,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "current_alias_policy": {
            "current_moved_from": ROLLBACK_KEY,
            "current_moved_to": CURRENT_RESOLVES_TO,
            "rollback_key": ROLLBACK_KEY,
            "movement_condition": "v6_7 agentic selection/retry fail-closed policy, boundary, single-report, and current-focused checks pass",
            "official_product_promotion_live_readiness_claim": False,
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": {},
        "generated_artifacts": [REPORT_PATH.as_posix()],
        "consolidated_report_policy": {
            "primary_report_only": True,
            "primary_report_path": REPORT_PATH.as_posix(),
            "separate_agentic_loop_trace_jsonl_created": False,
            "separate_structured_tool_diagnostics_jsonl_created": False,
            "separate_metric_results_json_created": False,
            "separate_review_jsonl_created": False,
        },
        "source_v6_6_report_check": _source_v66_summary(source_v66),
        "agentic_retry_policy": _agentic_retry_policy(),
        "agentic_loop_summary": summary,
        "agentic_loop_rows": rows,
        "candidate_generation_input_policy": _candidate_generation_policy(),
        "tool_to_rag_leakage_guard": _tool_to_rag_guard(),
        "protected_surface_check": _protected_surface_check(),
        "v7_guard": _v7_guard(),
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        **{field: False for field in REQUIRED_FALSE_REPORT_FIELDS},
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v67_agentic_retry_fail_closed_policy_nonprod_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_7_agentic_retry_fail_closed_policy_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_6_structured_tool_operation_taxonomy_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py v7_0_e2e_eval_architecture_closeout_nonprod --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
        ],
    }
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != LOGICAL_RUN_KEY or report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_7 run identity drift")
    if report.get("schema_version") != f"{SHORT_RUN_ID}_report_v1":
        raise ValueError("v6_7 schema drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_7 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_7 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_7 rollback key drift")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v6_7 diagnostic/non-production flag missing")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            if key == "agentic_loop_metric_computed":
                raise ValueError("v6_7 agentic loop metric opened")
            if key == "answer_quality_metric_computed":
                raise ValueError("v6_7 answer quality metric opened")
            raise ValueError(f"v6_7 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if int(report.get(key) or 0) != 0:
            raise ValueError(f"v6_7 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True:
        raise ValueError("v6_7 protected surface check failed")
    if protected.get("mutated_paths") or protected.get("protected_namespaces_touched"):
        raise ValueError("v6_7 protected namespaces touched")


def _require_source(report: Mapping[str, Any]) -> None:
    source = report.get("source_v6_6_report_check") or {}
    if source.get("run_key") != ROLLBACK_KEY:
        raise ValueError("v6_7 source v6_6 drift")
    if source.get("tool_operation_rows") != 29:
        raise ValueError("v6_7 source tool row drift")
    if source.get("tool_metric_official") is not False:
        raise ValueError("v6_7 source tool metric official")


def _require_policy(report: Mapping[str, Any]) -> None:
    policy = report.get("agentic_retry_policy") or {}
    if policy.get("retry_requires_new_allowed_signal") is not True:
        raise ValueError("v6_7 retry policy missing new-signal requirement")
    if policy.get("retry_may_use_expected_or_qrels") is not False:
        raise ValueError("v6_7 retry may use expected or qrels")
    if policy.get("selection_may_use_expected_or_qrels") is not False:
        raise ValueError("v6_7 selection may use expected or qrels")
    if policy.get("fail_closed_on_verification_failure") is not True:
        raise ValueError("v6_7 verification failure does not fail closed")


def _require_rows(report: Mapping[str, Any]) -> None:
    rows = report.get("agentic_loop_rows") or []
    summary = report.get("agentic_loop_summary") or {}
    if len(rows) != 29 or summary.get("agentic_loop_rows") != 29:
        raise ValueError("v6_7 agentic loop row count drift")
    if summary.get("silently_dropped_rows") != 0:
        raise ValueError("v6_7 agentic loop rows dropped")
    if summary.get("retry_attempted_rows") != 0:
        raise ValueError("v6_7 retry unexpectedly attempted")
    if summary.get("expected_supporting_qrels_used_in_loop_count") != 0:
        raise ValueError("v6_7 expected/qrels entered loop")
    for row in rows:
        if row.get("selected_path") not in {"rag_only", "tool_only", "rag_then_tool", "tool_then_rag", "none_fail_closed"}:
            raise ValueError("v6_7 selected path drift")
        if row.get("verification_state") not in {"passed", "failed", "skipped_no_answer", "not_applicable"}:
            raise ValueError("v6_7 verification state drift")
        if row.get("expected_supporting_qrels_used_in_loop") is not False:
            raise ValueError("v6_7 expected/qrels entered row loop")
        if row.get("raw_prompt_payload_written") is not False or row.get("raw_response_payload_written") is not False:
            raise ValueError("v6_7 raw prompt/response payload written")


def _require_metric_boundaries(report: Mapping[str, Any]) -> None:
    policy = report.get("candidate_generation_input_policy") or {}
    if policy.get("expected_supporting_qrels_used_for_selection_or_retry") is not False:
        raise ValueError("v6_7 selection used expected/supporting/qrels")
    if policy.get("tool_outputs_used_for_true_rag_metric") is not False:
        raise ValueError("v6_7 tool output entered true RAG metric")
    guard = report.get("tool_to_rag_leakage_guard") or {}
    for key in ("tool_success_contributed_to_hit_at_k", "tool_success_contributed_to_mrr", "tool_success_contributed_to_ndcg"):
        if guard.get(key) is not False:
            raise ValueError("v6_7 tool output entered true RAG metric")


def _require_single_report(report: Mapping[str, Any], root: Path | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v6_7 primary report policy missing")
    if root is not None:
        run_root = root / RUN_ROOT
        if run_root.exists():
            names = {path.name for path in run_root.iterdir()}
            if names != {"report.json"}:
                raise ValueError(f"v6_7 single primary report policy violated: {sorted(names)}")
            expected = _clean((report.get("artifact_sha256") or {}).get("report_json_sha256"))
            if expected and common.sha256_file(run_root / "report.json") != expected:
                raise ValueError("v6_7 report hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    repo_root = Path(root) if root is not None else None
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_source(report)
    _require_policy(report)
    _require_rows(report)
    _require_metric_boundaries(report)
    _require_single_report(report, repo_root)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v6_7")


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
    summary = report["agentic_loop_summary"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": PREVIOUS_CURRENT,
        "current_moved_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "agentic_loop_rows": summary["agentic_loop_rows"],
        "retry_attempted_rows": summary["retry_attempted_rows"],
        "agentic_loop_metric_computed": False,
        "answer_quality_metric_computed": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
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
        raise ValueError("v6_7 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_7 status report hash missing: report.json not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v6_7 status report hash missing: status event not found")
    latest = rows[-1]
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_7 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_7 status current alias drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    summary = report["agentic_loop_summary"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is a diagnostic-only agentic selection/retry fail-closed "
        f"policy packet over v6_6. current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` after v6_7 checks; "
        f"rollback key is `{ROLLBACK_KEY}`. agentic_rows={summary['agentic_loop_rows']}; retry_attempted_rows=0; "
        "answer_quality_metric_computed=false. There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        f"- Agentic loop diagnostics: rows={summary['agentic_loop_rows']}; selected_path_counts={summary['selected_path_counts']}; "
        f"verification_state_counts={summary['verification_state_counts']}; retry_attempted_rows=0.\n"
        "- Metrics policy: agentic_loop_metric_computed=false; answer_quality_metric_computed=false; "
        "expected/qrels/supporting evidence are not used for selection or retry. No official/product/promotion/live-readiness claim is opened."
    )
    triage = (
        f"- {SHORT_RUN_ID}: RAG/tool path selection, verification, retry count, and fail-closed reasons are embedded in "
        "primary report.json only. Retries require a new allowed signal and may not use expected answers, supporting evidence, "
        "or qrels. no official/product/promotion/live-readiness claim is opened."
    )
    return progress, measurements, triage


def _upsert_doc(root: Path, path: Path, *, start: str, end: str, block: str) -> None:
    full_path = root / path
    text = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(common.upsert_block_at_top(text, start_marker=start, end_marker=end, block=block), encoding="utf-8")


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
