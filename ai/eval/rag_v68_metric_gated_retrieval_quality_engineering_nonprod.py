from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v64_e2e_coverage_and_failure_taxonomy_nonprod as v64
from ai.eval import rag_v65_retrieval_metric_unlock_packet_nonprod as v65
from ai.eval import rag_v651_gold29_actual_response_smoke_nonprod as v651
from ai.eval import rag_v66_structured_tool_operation_taxonomy_nonprod as v66
from ai.eval import rag_v67_agentic_retry_fail_closed_policy_nonprod as v67


LOGICAL_RUN_KEY = "v6_8_metric_gated_retrieval_quality_engineering_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_8_METRIC_GATED_RETRIEVAL_QUALITY_ENGINEERING_NONPROD_READY"
PREVIOUS_CURRENT = v67.LOGICAL_RUN_KEY
CURRENT_RESOLVES_TO = LOGICAL_RUN_KEY
ROLLBACK_KEY = PREVIOUS_CURRENT

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
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
BACKENDS = ("vector", "bm25", "hybrid")
BLOCKED_REASON = "no_safe_read_only_label_qrels_bridge_available"
V7_REMAINING_PREDECESSORS = ("v6_9_answer_quality_gate_packet_nonprod",)

REQUIRED_FALSE_REPORT_FIELDS = (
    "official_metric",
    "retrieval_quality_metric_computed",
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


def _protected_surface_check() -> dict[str, Any]:
    return v651._protected_surface_check()  # type: ignore[attr-defined]


def _load_v64(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v64.LOGICAL_RUN_KEY, root=root)
    v64.check_report(source, root=root if report is None else None)
    if report is None:
        v64.require_status_report_hash(root, source)
    return source


def _load_v65(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v65.LOGICAL_RUN_KEY, root=root)
    v65.check_report(source, root=root if report is None else None)
    if report is None:
        v65.require_status_report_hash(root, source)
    return source


def _load_v66(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v66.LOGICAL_RUN_KEY, root=root)
    v66.check_report(source, root=root if report is None else None)
    if report is None:
        v66.require_status_report_hash(root, source)
    return source


def _load_v67(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v67.LOGICAL_RUN_KEY, root=root)
    v67.check_report(source, root=root if report is None else None)
    if report is None:
        v67.require_status_report_hash(root, source)
    return source


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _source_v64_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    coverage = source["candidate_coverage_summary"]
    return {
        "run_key": v64.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "attempted_rows": coverage["attempted_rows"],
        "coverage_adjusted_denominator": coverage["coverage_adjusted_denominator"],
        "computed_only_denominator": coverage["computed_only_denominator"],
        "family_breakdown": coverage["family_breakdown"],
        "candidate_availability_backends": sorted(source["candidate_availability"]),
        "retrieval_quality_metric_computed": source.get("retrieval_quality_metric_computed") is True,
        "answer_quality_metric_computed": source.get("answer_quality_metric_computed") is True,
    }


def _source_v65_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    bridge = source["bridge_audit"]
    packet = source["bridged_retrieval_metric_packet"]
    return {
        "run_key": v65.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "audited_rows": bridge["audited_rows"],
        "bridgeable_rows": bridge["bridgeable_row_count"],
        "non_bridgeable_or_ambiguous_rows": bridge["non_bridgeable_or_ambiguous_row_count"],
        "bridge_state_counts": bridge["state_counts"],
        "bridged_retrieval_metric_computed": packet["computed"],
        "bridged_metric_denominator": packet["bridged_metric_denominator"],
        "computed_only_denominator": packet["computed_only_denominator"],
        "metric_denominator_separate_from_v6_4_coverage_denominator": packet[
            "metric_denominator_separate_from_v6_4_coverage_denominator"
        ],
    }


def _source_v66_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    summary = source["tool_operation_summary"]
    return {
        "run_key": v66.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "tool_operation_rows": summary["tool_operation_rows"],
        "tool_executed_rows": summary["tool_executed_rows"],
        "tool_result_available_rows": summary["tool_result_available_rows"],
        "tool_metric_official": summary["tool_metric_official"],
        "tool_outputs_excluded_from_true_rag_metrics": source.get("tool_outputs_excluded_from_true_rag_metrics") is True,
    }


def _source_v67_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    summary = source["agentic_loop_summary"]
    return {
        "run_key": v67.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "agentic_loop_rows": summary["agentic_loop_rows"],
        "selected_path_counts": summary["selected_path_counts"],
        "verification_state_counts": summary["verification_state_counts"],
        "retry_attempted_rows": summary["retry_attempted_rows"],
        "final_answer_rendered_rows": summary["final_answer_rendered_rows"],
        "final_citation_verified_rows": summary["final_citation_verified_rows"],
    }


def _candidate_generation_policy() -> dict[str, Any]:
    return {
        "candidate_generation_allowed_input_surface": ["query_text", "allowed_corpus_index_source_surfaces"],
        "expected_supporting_gold_qrels_used_for_candidate_generation": False,
        "target_ids_used_for_candidate_generation": False,
        "row_or_case_ids_used_for_candidate_generation": False,
        "source_title_shortcuts_used_for_candidate_generation": False,
        "workbook_file_name_shortcuts_used_for_candidate_generation": False,
        "baseline_topk_replay_used": False,
        "prior_route_diagnostics_used_for_candidate_generation": False,
        "tool_outputs_used_for_true_rag_metric": False,
    }


def _retrieval_quality_gate(
    *,
    v64_summary: Mapping[str, Any],
    v65_summary: Mapping[str, Any],
) -> dict[str, Any]:
    bridgeable_rows = int(v65_summary["bridgeable_rows"])
    safe_available = bridgeable_rows > 0 and v65_summary["bridged_retrieval_metric_computed"] is True
    return {
        "safe_read_only_denominator_available": safe_available,
        "safe_read_only_denominator_source": v65.LOGICAL_RUN_KEY,
        "bridgeable_rows": bridgeable_rows,
        "bridge_audited_rows": v65_summary["audited_rows"],
        "retrieval_quality_metric_computed": False,
        "computed_only_denominator": 0,
        "coverage_adjusted_denominator": v64_summary["coverage_adjusted_denominator"],
        "blocked_reason": "" if safe_available else BLOCKED_REASON,
        "hit_at_k_computed": False,
        "mrr_computed": False,
        "ndcg_computed": False,
        "hit_at_k": None,
        "mrr": None,
        "ndcg": None,
        "metric_denominator_separate_from_v6_4_coverage_denominator": True,
        "tool_outputs_excluded_from_true_rag_metrics": True,
        "expected_supporting_qrels_used_for_candidate_generation": False,
        "official_metric": False,
    }


def _backend_diagnostics(v64_report: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    availability = v64_report["candidate_availability"]
    for backend in BACKENDS:
        counters = availability[backend]
        diagnostics[backend] = {
            "attempted_rows": counters["attempted_rows"],
            "with_candidates_rows": counters["with_candidates_rows"],
            "no_candidate_rows": counters["no_candidate_rows"],
            "hydrated_rows": counters["hydrated_rows"],
            "hydration_failed_rows": counters["hydration_failed_rows"],
            "computed_only_denominator": counters["computed_only_denominator"],
            "retrieval_quality_metric_computed": False,
            "backend_latency_ms_available": False,
            "backend_latency_ms_p50": None,
            "backend_latency_ms_p95": None,
            "tool_outputs_counted_as_rag_hit": counters["tool_outputs_counted_as_rag_hit"],
        }
    return diagnostics


def _family_diagnostics(v66_report: Mapping[str, Any], v67_report: Mapping[str, Any]) -> dict[str, Any]:
    agentic_rows = list(v67_report["agentic_loop_rows"])
    tool_rows = list(v66_report["tool_operation_rows"])
    agentic_by_family = Counter(_clean(row.get("source_family")) for row in agentic_rows)
    rendered_by_family = Counter(_clean(row.get("source_family")) for row in agentic_rows if row.get("final_answer_rendered") is True)
    verified_by_family = Counter(_clean(row.get("source_family")) for row in agentic_rows if row.get("final_citation_verified") is True)
    fail_closed_by_family = Counter(_clean(row.get("source_family")) for row in agentic_rows if _clean(row.get("fail_closed_reason")))
    tool_by_family = Counter(_clean(row.get("source_family")) for row in tool_rows)
    tool_available_by_family = Counter(
        _clean(row.get("source_family")) for row in tool_rows if row.get("tool_result_available") is True
    )
    return {
        family: {
            "gold29_rows": int(agentic_by_family.get(family, 0)),
            "v6_4_coverage_rows": 100,
            "tool_operation_rows": int(tool_by_family.get(family, 0)),
            "tool_result_available_rows": int(tool_available_by_family.get(family, 0)),
            "final_answer_rendered_rows": int(rendered_by_family.get(family, 0)),
            "final_citation_verified_rows": int(verified_by_family.get(family, 0)),
            "fail_closed_rows": int(fail_closed_by_family.get(family, 0)),
            "retrieval_quality_metric_computed": False,
        }
        for family in FAMILIES
    }


def _engineering_diagnostics(
    *,
    v64_report: Mapping[str, Any],
    v66_report: Mapping[str, Any],
    v67_report: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "diagnostic_only": True,
        "availability_counters_are_quality_metrics": False,
        "backend_latency_counters_are_quality_metrics": False,
        "fail_closed_reason_counters_are_quality_metrics": False,
        "by_backend": _backend_diagnostics(v64_report),
        "by_family": _family_diagnostics(v66_report, v67_report),
        "fail_closed_reason_counts": {
            "metric_gate": {BLOCKED_REASON: 1},
            "agentic_loop": dict(Counter(_clean(row.get("fail_closed_reason")) for row in v67_report["agentic_loop_rows"] if _clean(row.get("fail_closed_reason")))),
        },
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
    v6_4_report: Mapping[str, Any] | None = None,
    v6_5_report: Mapping[str, Any] | None = None,
    v6_6_report: Mapping[str, Any] | None = None,
    v6_7_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source_v64 = _load_v64(repo_root, v6_4_report)
    source_v65 = _load_v65(repo_root, v6_5_report)
    source_v66 = _load_v66(repo_root, v6_6_report)
    source_v67 = _load_v67(repo_root, v6_7_report)
    v64_summary = _source_v64_summary(source_v64)
    v65_summary = _source_v65_summary(source_v65)
    gate = _retrieval_quality_gate(v64_summary=v64_summary, v65_summary=v65_summary)
    diagnostics = _engineering_diagnostics(v64_report=source_v64, v66_report=source_v66, v67_report=source_v67)
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
            "movement_condition": "v6_8 metric-gated retrieval-quality engineering, denominator-separation, single-report, and current-focused checks pass",
            "official_product_promotion_live_readiness_claim": False,
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": {},
        "generated_artifacts": [REPORT_PATH.as_posix()],
        "consolidated_report_policy": {
            "primary_report_only": True,
            "primary_report_path": REPORT_PATH.as_posix(),
            "separate_metric_results_json_created": False,
            "separate_metric_tiers_json_created": False,
            "separate_denominator_manifest_jsonl_created": False,
            "separate_retrieval_quality_packet_json_created": False,
            "separate_engineering_diagnostics_jsonl_created": False,
            "separate_human_review_packet_jsonl_created": False,
        },
        "source_v6_4_report_check": v64_summary,
        "source_v6_5_bridge_check": v65_summary,
        "source_v6_6_tool_check": _source_v66_summary(source_v66),
        "source_v6_7_agentic_check": _source_v67_summary(source_v67),
        "v6_4_coverage_adjusted_denominator": v64_summary["coverage_adjusted_denominator"],
        "retrieval_quality_gate": gate,
        "retrieval_engineering_diagnostics": diagnostics,
        "candidate_generation_input_policy": _candidate_generation_policy(),
        "protected_surface_check": _protected_surface_check(),
        "v7_guard": _v7_guard(),
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        **{field: False for field in REQUIRED_FALSE_REPORT_FIELDS},
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v68_metric_gated_retrieval_quality_engineering_nonprod_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_8_metric_gated_retrieval_quality_engineering_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_7_agentic_retry_fail_closed_policy_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py v7_0_e2e_eval_architecture_closeout_nonprod --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
        ],
    }
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != LOGICAL_RUN_KEY or report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_8 run identity drift")
    if report.get("schema_version") != f"{SHORT_RUN_ID}_report_v1":
        raise ValueError("v6_8 schema drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_8 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_8 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_8 rollback key drift")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v6_8 diagnostic/non-production flag missing")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            if key == "retrieval_quality_metric_computed":
                raise ValueError("v6_8 retrieval quality metric opened")
            if key == "official_denominator_mutation":
                raise ValueError("v6_8 official denominator mutation opened")
            raise ValueError(f"v6_8 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if int(report.get(key) or 0) != 0:
            raise ValueError(f"v6_8 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True:
        raise ValueError("v6_8 protected surface check failed")
    if protected.get("mutated_paths") or protected.get("protected_namespaces_touched"):
        raise ValueError("v6_8 protected namespaces touched")


def _require_sources(report: Mapping[str, Any]) -> None:
    v64_source = report.get("source_v6_4_report_check") or {}
    if v64_source.get("attempted_rows") != 300 or v64_source.get("coverage_adjusted_denominator") != 300:
        raise ValueError("v6_8 v6_4 coverage source drift")
    if v64_source.get("computed_only_denominator") != 0:
        raise ValueError("v6_8 source v6_4 computed-only denominator opened")
    if v64_source.get("family_breakdown") != {"PDF": 100, "TEXT": 100, "XLSX": 100}:
        raise ValueError("v6_8 v6_4 family coverage drift")
    v65_source = report.get("source_v6_5_bridge_check") or {}
    if v65_source.get("audited_rows") != 29:
        raise ValueError("v6_8 v6_5 bridge row drift")
    if v65_source.get("bridgeable_rows") != 0:
        raise ValueError("v6_8 v6_5 bridge unexpectedly opened")
    if v65_source.get("bridged_retrieval_metric_computed") is not False:
        raise ValueError("v6_8 v6_5 bridged retrieval metric opened")
    if v65_source.get("metric_denominator_separate_from_v6_4_coverage_denominator") is not True:
        raise ValueError("v6_8 v6_5 denominator separation missing")
    if (report.get("source_v6_6_tool_check") or {}).get("tool_operation_rows") != 29:
        raise ValueError("v6_8 v6_6 tool source row drift")
    if (report.get("source_v6_7_agentic_check") or {}).get("agentic_loop_rows") != 29:
        raise ValueError("v6_8 v6_7 agentic source row drift")


def _require_retrieval_gate(report: Mapping[str, Any]) -> None:
    gate = report.get("retrieval_quality_gate") or {}
    if gate.get("safe_read_only_denominator_available") is not False:
        raise ValueError("v6_8 safe denominator unexpectedly opened")
    if gate.get("blocked_reason") != BLOCKED_REASON:
        raise ValueError("v6_8 retrieval metric gate blocked reason drift")
    if gate.get("computed_only_denominator") != 0:
        raise ValueError("v6_8 computed-only denominator opened")
    if gate.get("coverage_adjusted_denominator") != 300 or report.get("v6_4_coverage_adjusted_denominator") != 300:
        raise ValueError("v6_8 coverage-adjusted denominator drift")
    if gate.get("metric_denominator_separate_from_v6_4_coverage_denominator") is not True:
        raise ValueError("v6_8 metric denominator separation missing")
    for key in ("hit_at_k_computed", "mrr_computed", "ndcg_computed"):
        if gate.get(key) is not False:
            raise ValueError(f"v6_8 retrieval quality metric component opened: {key}")
    if gate.get("tool_outputs_excluded_from_true_rag_metrics") is not True:
        raise ValueError("v6_8 tool outputs not excluded from true RAG metrics")
    if gate.get("expected_supporting_qrels_used_for_candidate_generation") is not False:
        raise ValueError("v6_8 candidate generation used expected/supporting/qrels")


def _require_engineering_diagnostics(report: Mapping[str, Any]) -> None:
    diagnostics = report.get("retrieval_engineering_diagnostics") or {}
    if diagnostics.get("diagnostic_only") is not True:
        raise ValueError("v6_8 engineering diagnostics not diagnostic-only")
    for key in (
        "availability_counters_are_quality_metrics",
        "backend_latency_counters_are_quality_metrics",
        "fail_closed_reason_counters_are_quality_metrics",
    ):
        if diagnostics.get(key) is not False:
            raise ValueError("v6_8 engineering counters promoted to quality metrics")
    by_backend = diagnostics.get("by_backend") or {}
    if set(by_backend) != set(BACKENDS):
        raise ValueError("v6_8 backend diagnostics drift")
    for backend, counters in by_backend.items():
        if counters.get("attempted_rows") != 300:
            raise ValueError(f"v6_8 {backend} attempted row drift")
        if counters.get("computed_only_denominator") != 0:
            raise ValueError(f"v6_8 {backend} computed-only denominator opened")
        if counters.get("retrieval_quality_metric_computed") is not False:
            raise ValueError(f"v6_8 {backend} retrieval quality metric opened")
        if counters.get("tool_outputs_counted_as_rag_hit") is not False:
            raise ValueError(f"v6_8 {backend} tool output entered RAG metric")
    by_family = diagnostics.get("by_family") or {}
    if {family: (by_family.get(family) or {}).get("gold29_rows") for family in FAMILIES} != {
        "PDF": 4,
        "TEXT": 6,
        "XLSX": 19,
    }:
        raise ValueError("v6_8 gold29 family diagnostics drift")


def _require_candidate_generation_policy(report: Mapping[str, Any]) -> None:
    policy = report.get("candidate_generation_input_policy") or {}
    if policy.get("candidate_generation_allowed_input_surface") != ["query_text", "allowed_corpus_index_source_surfaces"]:
        raise ValueError("v6_8 candidate generation allowed surface drift")
    for key in (
        "expected_supporting_gold_qrels_used_for_candidate_generation",
        "target_ids_used_for_candidate_generation",
        "row_or_case_ids_used_for_candidate_generation",
        "source_title_shortcuts_used_for_candidate_generation",
        "workbook_file_name_shortcuts_used_for_candidate_generation",
        "baseline_topk_replay_used",
        "prior_route_diagnostics_used_for_candidate_generation",
        "tool_outputs_used_for_true_rag_metric",
    ):
        if policy.get(key) is not False:
            raise ValueError(f"v6_8 candidate generation boundary opened: {key}")


def _require_single_report(report: Mapping[str, Any], root: Path | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v6_8 primary report policy missing")
    if root is not None:
        run_root = root / RUN_ROOT
        if run_root.exists():
            names = {path.name for path in run_root.iterdir()}
            if names != {"report.json"}:
                raise ValueError(f"v6_8 single primary report policy violated: {sorted(names)}")
            expected = _clean((report.get("artifact_sha256") or {}).get("report_json_sha256"))
            if expected and common.sha256_file(run_root / "report.json") != expected:
                raise ValueError("v6_8 report hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    repo_root = Path(root) if root is not None else None
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_sources(report)
    _require_retrieval_gate(report)
    _require_engineering_diagnostics(report)
    _require_candidate_generation_policy(report)
    _require_single_report(report, repo_root)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v6_8")


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
    gate = report["retrieval_quality_gate"]
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
        "retrieval_quality_metric_computed": False,
        "safe_read_only_denominator_available": gate["safe_read_only_denominator_available"],
        "computed_only_denominator": gate["computed_only_denominator"],
        "coverage_adjusted_denominator": gate["coverage_adjusted_denominator"],
        "blocked_reason": gate["blocked_reason"],
        "hit_at_k_computed": False,
        "mrr_computed": False,
        "ndcg_computed": False,
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
        raise ValueError("v6_8 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_8 status report hash missing: report.json not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v6_8 status report hash missing: status event not found")
    latest = rows[-1]
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_8 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_8 status current alias drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    gate = report["retrieval_quality_gate"]
    diagnostics = report["retrieval_engineering_diagnostics"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is a diagnostic-only retrieval-quality engineering gate "
        f"over v6_4/v6_5/v6_6/v6_7. current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` after v6_8 checks; "
        f"rollback key is `{ROLLBACK_KEY}`. safe_read_only_denominator_available=false; "
        f"computed_only_denominator=0; blocked_reason={gate['blocked_reason']}. There is no official/product/"
        "promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        "- Retrieval-quality gate: safe_read_only_denominator_available=false; retrieval_quality_metric_computed=false; "
        f"computed_only_denominator=0; coverage_adjusted_denominator={gate['coverage_adjusted_denominator']}; "
        f"blocked_reason={gate['blocked_reason']}; Hit@k/MRR/nDCG remain uncomputed.\n"
        f"- Denominator separation: v6_4 coverage_adjusted_denominator={report['v6_4_coverage_adjusted_denominator']}; "
        "metric_denominator_separate_from_v6_4_coverage_denominator=true; official_denominator_mutation=false.\n"
        f"- Engineering diagnostics only: backend counters={diagnostics['by_backend']}; family counters={diagnostics['by_family']}. "
        "Availability, latency, and fail-closed counters are not quality metrics. No official/product/promotion/live-readiness claim is opened."
    )
    triage = (
        f"- {SHORT_RUN_ID}: v6_5 bridgeable_rows=0 keeps true RAG retrieval metrics closed; "
        f"computed_only_denominator=0 with blocked_reason={gate['blocked_reason']}. Engineering diagnostics summarize "
        "candidate availability, hydration, and fail-closed counters without scoring Hit@k, MRR, nDCG, tool quality, or answer quality. "
        "no official/product/promotion/live-readiness claim is opened."
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
