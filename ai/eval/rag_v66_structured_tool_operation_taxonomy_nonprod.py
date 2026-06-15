from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v651_gold29_actual_response_smoke_nonprod as v651


LOGICAL_RUN_KEY = "v6_6_structured_tool_operation_taxonomy_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_6_STRUCTURED_TOOL_OPERATION_TAXONOMY_NONPROD_READY"
PREVIOUS_CURRENT = v651.LOGICAL_RUN_KEY
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
STRUCTURED_TOOL_OPERATION_TAXONOMY = (
    "pdf_page_span_extract",
    "pdf_locator_lookup",
    "text_span_lookup",
    "xlsx_table_slice",
    "xlsx_cell_lookup",
    "xlsx_filter",
    "xlsx_aggregate",
    "no_tool_required",
    "unsupported_tool_request",
    "tool_surface_unavailable",
    "tool_execution_failed",
    "tool_result_empty",
    "tool_result_hydration_failed",
)
V7_REMAINING_PREDECESSORS = (
    "v6_7_agentic_retry_fail_closed_policy_nonprod",
    "v6_8_metric_gated_retrieval_quality_engineering_nonprod",
    "v6_9_answer_quality_gate_packet_nonprod",
)
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
    "raw_tool_payload_written",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
)
FORBIDDEN_REPORT_PAYLOAD_KEYS = {
    "raw_tool_payload",
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


def _source_v651_summary(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v651.LOGICAL_RUN_KEY, root=root)
    v651.check_report(source, root=root if report is None else None)
    if report is None:
        v651.require_status_report_hash(root, source)
    smoke = source["actual_response_smoke_summary"]
    return {
        "run_key": v651.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "actual_response_rows_attempted": smoke["actual_response_rows_attempted"],
        "actual_response_rows_rendered": smoke["actual_response_rows_rendered"],
        "citation_verified_rows": smoke["citation_verified_rows"],
        "fail_closed_rows": smoke["fail_closed_rows"],
        "retrieval_quality_metric_computed": source.get("retrieval_quality_metric_computed") is True,
        "answer_quality_metric_computed": source.get("answer_quality_metric_computed") is True,
        "tool_outputs_excluded_from_true_rag_metrics": True,
    }


def _operation_state_for_row(row: Mapping[str, Any]) -> str:
    family = _clean(row.get("source_family"))
    if family == "PDF":
        return "pdf_locator_lookup" if row.get("citation_verified") is True else "pdf_page_span_extract"
    if family == "TEXT":
        return "text_span_lookup"
    if family == "XLSX":
        return "xlsx_table_slice" if int(row.get("candidate_count") or 0) else "xlsx_cell_lookup"
    return "unsupported_tool_request"


def _build_tool_rows(v651_report: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    family_counter: Counter[str] = Counter()
    operation_counter: Counter[str] = Counter()
    for source_row in v651_report["response_diagnostics"]:
        family = _clean(source_row.get("source_family"))
        state = _operation_state_for_row(source_row)
        family_counter[family] += 1
        operation_counter[state] += 1
        rows.append(
            {
                "gold_row_hash": source_row["gold_row_hash"],
                "source_family": family,
                "query_hash": source_row["query_hash"],
                "operation_state": state,
                "requested_operation_state": state,
                "tool_required": family == "XLSX",
                "tool_supported": False,
                "tool_executed": False,
                "tool_result_available": False,
                "tool_result_hydrated_to_evidence_bundle": False,
                "rag_candidate_count": int(source_row.get("candidate_count") or 0),
                "rag_hydrated_evidence_count": int(source_row.get("hydrated_evidence_count") or 0),
                "tool_output_used_for_rag_metric": False,
                "fail_closed_reason": "tool_surface_unavailable",
                "source_response_route_hash": hashlib.sha256(
                    _clean(source_row.get("route_decision")).encode("utf-8")
                ).hexdigest(),
                "raw_tool_payload_written": False,
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
            }
        )
    summary = {
        "tool_operation_rows": len(rows),
        "silently_dropped_rows": 29 - len(rows),
        "rows_by_family": _counter_dict(family_counter),
        "operation_state_counts": {key: int(operation_counter.get(key, 0)) for key in STRUCTURED_TOOL_OPERATION_TAXONOMY},
        "tool_supported_rows": 0,
        "tool_executed_rows": 0,
        "tool_result_available_rows": 0,
        "tool_result_hydrated_rows": 0,
        "tool_metric_rows": len(rows),
        "tool_metric_official": False,
        "tool_surface_unavailable_rows": len(rows),
    }
    return rows, summary


def _candidate_generation_policy() -> dict[str, Any]:
    return {
        "allowed_fields": ["query_text", "source_family", "top_k"],
        "expected_supporting_qrels_used_for_candidate_generation": False,
        "target_ids_used_for_candidate_generation": False,
        "row_or_case_ids_used_for_candidate_generation": False,
        "source_title_or_file_name_shortcuts_used": False,
        "workbook_or_file_name_shortcuts_used": False,
        "baseline_topk_or_prior_route_diagnostics_used": False,
        "prior_route_diagnostics_used_for_candidate_generation": False,
        "tool_outputs_used_for_candidate_generation": False,
        "tool_success_used_for_candidate_generation": False,
        "forbidden_fields_present_in_candidate_request_count": 0,
    }


def _tool_to_rag_guard() -> dict[str, Any]:
    return {
        "tool_outputs_counted_as_rag_hit": False,
        "tool_success_contributed_to_hit_at_k": False,
        "tool_success_contributed_to_mrr": False,
        "tool_success_contributed_to_ndcg": False,
        "tool_result_hydration_counted_as_retrieval_hit": False,
    }


def _evidence_truth_boundary() -> dict[str, Any]:
    return {
        "source_atom_evidence_bundle_role": "evidence_truth",
        "search_view_vector_payload_role": "candidate_only",
        "tool_output_role": "diagnostic_tool_result_only",
        "tool_output_used_as_evidence_truth": False,
        "tool_result_hydrated_to_evidence_bundle_count": 0,
        "evidence_truth_violation_count": 0,
    }


def _v7_guard() -> dict[str, Any]:
    return {
        "v7_0_recorded_as_premature_closeout_marker_only": True,
        "v7_completion_claim_from_v7_0": False,
        "v7_0_can_be_current_before_v6_7_to_v6_9_satisfied_or_skipped": False,
        "missing_or_unskipped_predecessors": list(V7_REMAINING_PREDECESSORS),
    }


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    v6_5_1_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source_report = _json_clone(v6_5_1_report) if v6_5_1_report is not None else registry.load_report(v651.LOGICAL_RUN_KEY, root=repo_root)
    v651.check_report(source_report, root=repo_root if v6_5_1_report is None else None)
    if v6_5_1_report is None:
        v651.require_status_report_hash(repo_root, source_report)
    source_summary = _source_v651_summary(repo_root, source_report)
    tool_rows, tool_summary = _build_tool_rows(source_report)
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
            "movement_condition": "v6_6 structured-tool taxonomy, tool/RAG separation, single-report, and current-focused checks pass",
            "official_product_promotion_live_readiness_claim": False,
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": {},
        "generated_artifacts": [REPORT_PATH.as_posix()],
        "consolidated_report_policy": {
            "primary_report_only": True,
            "primary_report_path": REPORT_PATH.as_posix(),
            "separate_structured_tool_diagnostics_jsonl_created": False,
            "separate_tool_metrics_json_created": False,
            "separate_review_csv_created": False,
            "separate_review_xlsx_created": False,
            "separate_review_jsonl_created": False,
            "separate_metric_results_json_created": False,
            "separate_agentic_loop_trace_jsonl_created": False,
            "separate_true_rag_candidate_diagnostics_jsonl_created": False,
        },
        "source_v6_5_1_report_check": source_summary,
        "structured_tool_operation_taxonomy": list(STRUCTURED_TOOL_OPERATION_TAXONOMY),
        "tool_operation_summary": tool_summary,
        "tool_operation_rows": tool_rows,
        "tool_metric_official": False,
        "tool_outputs_excluded_from_true_rag_metrics": True,
        "candidate_generation_input_policy": _candidate_generation_policy(),
        "tool_to_rag_leakage_guard": _tool_to_rag_guard(),
        "evidence_truth_boundary": _evidence_truth_boundary(),
        "protected_surface_check": _protected_surface_check(),
        "v7_guard": _v7_guard(),
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        **{field: False for field in REQUIRED_FALSE_REPORT_FIELDS},
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v66_structured_tool_operation_taxonomy_nonprod_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_6_structured_tool_operation_taxonomy_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_5_1_gold29_actual_response_smoke_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py v7_0_e2e_eval_architecture_closeout_nonprod --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
        ],
    }
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != LOGICAL_RUN_KEY or report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_6 run identity drift")
    if report.get("schema_version") != f"{SHORT_RUN_ID}_report_v1":
        raise ValueError("v6_6 schema drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_6 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_6 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_6 rollback key drift")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v6_6 diagnostic/non-production flag missing")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            if key == "retrieval_quality_metric_computed":
                raise ValueError("v6_6 retrieval quality metric opened")
            if key == "answer_quality_metric_computed":
                raise ValueError("v6_6 answer quality metric opened")
            raise ValueError(f"v6_6 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if int(report.get(key) or 0) != 0:
            raise ValueError(f"v6_6 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True:
        raise ValueError("v6_6 protected surface check failed")
    if protected.get("mutated_paths") or protected.get("protected_namespaces_touched"):
        raise ValueError("v6_6 protected namespaces touched")


def _require_source(report: Mapping[str, Any]) -> None:
    source = report.get("source_v6_5_1_report_check") or {}
    if source.get("run_key") != ROLLBACK_KEY:
        raise ValueError("v6_6 source v6_5_1 drift")
    if source.get("actual_response_rows_attempted") != 29:
        raise ValueError("v6_6 source attempted row drift")
    if source.get("retrieval_quality_metric_computed") is not False:
        raise ValueError("v6_6 source retrieval quality metric opened")
    if source.get("answer_quality_metric_computed") is not False:
        raise ValueError("v6_6 source answer quality metric opened")


def _require_tool_rows(report: Mapping[str, Any]) -> None:
    rows = report.get("tool_operation_rows") or []
    summary = report.get("tool_operation_summary") or {}
    taxonomy = set(report.get("structured_tool_operation_taxonomy") or [])
    if not set(STRUCTURED_TOOL_OPERATION_TAXONOMY).issubset(taxonomy):
        raise ValueError("v6_6 structured tool taxonomy incomplete")
    if len(rows) != 29 or summary.get("tool_operation_rows") != 29:
        raise ValueError("v6_6 tool operation row count drift")
    if summary.get("silently_dropped_rows") != 0:
        raise ValueError("v6_6 tool operation rows dropped")
    for row in rows:
        if row.get("operation_state") not in taxonomy:
            raise ValueError("v6_6 unknown operation state")
        if row.get("raw_tool_payload_written") is not False:
            raise ValueError("v6_6 raw tool payload written")
        if row.get("raw_prompt_payload_written") is not False or row.get("raw_response_payload_written") is not False:
            raise ValueError("v6_6 raw prompt/response payload written")
        if row.get("tool_output_used_for_rag_metric") is not False:
            raise ValueError("v6_6 tool output entered RAG metric row")
    for key in ("tool_supported_rows", "tool_executed_rows", "tool_result_available_rows", "tool_result_hydrated_rows"):
        if int(summary.get(key) or 0) != 0:
            raise ValueError(f"v6_6 tool summary unexpectedly opened: {key}")
    if summary.get("tool_metric_official") is not False:
        raise ValueError("v6_6 tool metric became official")


def _require_metric_boundaries(report: Mapping[str, Any]) -> None:
    if report.get("retrieval_quality_metric_computed") is not False:
        raise ValueError("v6_6 retrieval quality metric opened")
    if report.get("answer_quality_metric_computed") is not False:
        raise ValueError("v6_6 answer quality metric opened")
    if report.get("tool_metric_official") is not False:
        raise ValueError("v6_6 official tool metric opened")
    if report.get("tool_outputs_excluded_from_true_rag_metrics") is not True:
        raise ValueError("v6_6 tool output exclusion missing")
    guard = report.get("tool_to_rag_leakage_guard") or {}
    for key in ("tool_outputs_counted_as_rag_hit", "tool_success_contributed_to_hit_at_k", "tool_success_contributed_to_mrr", "tool_success_contributed_to_ndcg"):
        if guard.get(key) is not False:
            raise ValueError("v6_6 tool output entered true RAG metric")
    policy = report.get("candidate_generation_input_policy") or {}
    for key in (
        "expected_supporting_qrels_used_for_candidate_generation",
        "tool_outputs_used_for_candidate_generation",
        "prior_route_diagnostics_used_for_candidate_generation",
    ):
        if policy.get(key) is not False:
            raise ValueError("v6_6 candidate-generation boundary opened")
    evidence = report.get("evidence_truth_boundary") or {}
    if evidence.get("source_atom_evidence_bundle_role") != "evidence_truth":
        raise ValueError("v6_6 SourceAtom/EvidenceBundle truth boundary missing")
    if evidence.get("search_view_vector_payload_role") != "candidate_only":
        raise ValueError("v6_6 SearchView candidate-only boundary missing")
    if evidence.get("tool_output_used_as_evidence_truth") is not False:
        raise ValueError("v6_6 tool output used as evidence truth")


def _require_v7_guard(report: Mapping[str, Any]) -> None:
    guard = report.get("v7_guard") or {}
    if guard.get("v7_0_recorded_as_premature_closeout_marker_only") is not True:
        raise ValueError("v6_6 v7_0 premature marker guard failed")
    if guard.get("v7_completion_claim_from_v7_0") is not False:
        raise ValueError("v6_6 v7 completion claim opened")
    if guard.get("missing_or_unskipped_predecessors") != list(V7_REMAINING_PREDECESSORS):
        raise ValueError("v6_6 v7 predecessor guard drift")


def _require_single_report(report: Mapping[str, Any], root: Path | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v6_6 primary report policy missing")
    if root is not None:
        run_root = root / RUN_ROOT
        if run_root.exists():
            names = {path.name for path in run_root.iterdir()}
            if names != {"report.json"}:
                raise ValueError(f"v6_6 single primary report policy violated: {sorted(names)}")
            expected = _clean((report.get("artifact_sha256") or {}).get("report_json_sha256"))
            if expected and common.sha256_file(run_root / "report.json") != expected:
                raise ValueError("v6_6 report hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    repo_root = Path(root) if root is not None else None
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_source(report)
    _require_tool_rows(report)
    _require_metric_boundaries(report)
    _require_v7_guard(report)
    _require_single_report(report, repo_root)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v6_6")


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
    summary = report["tool_operation_summary"]
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
        "tool_operation_rows": summary["tool_operation_rows"],
        "tool_supported_rows": summary["tool_supported_rows"],
        "tool_executed_rows": summary["tool_executed_rows"],
        "tool_metric_official": False,
        "tool_outputs_excluded_from_true_rag_metrics": True,
        "official_metric": False,
        "retrieval_quality_metric_computed": False,
        "answer_quality_metric_computed": False,
        "official_metric_input_rows": 0,
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
        raise ValueError("v6_6 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_6 status report hash missing: report.json not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v6_6 status report hash missing: status event not found")
    latest = rows[-1]
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_6 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_6 status current alias drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    summary = report["tool_operation_summary"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is a diagnostic-only structured tool operation taxonomy "
        f"over the v6_5_1 gold29 actual-response smoke rows. current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` "
        f"after v6_6 checks; rollback key is `{ROLLBACK_KEY}`. tool rows={summary['tool_operation_rows']}; "
        "tool_supported_rows=0; tool_executed_rows=0; tool outputs are excluded from Hit@k/MRR/nDCG. "
        "There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        f"- Source check: v6_5_1 attempted_rows=29; rendered=10; citation_verified=10; fail_closed=19.\n"
        f"- Structured tool taxonomy: rows={summary['tool_operation_rows']}; rows_by_family={summary['rows_by_family']}; "
        f"operation_state_counts={summary['operation_state_counts']}.\n"
        "- Metric policy: tool_metric_official=false; retrieval_quality_metric_computed=false; "
        "answer_quality_metric_computed=false; tool outputs are excluded from Hit@k/MRR/nDCG. "
        "No official/product/promotion/live-readiness claim is opened."
    )
    triage = (
        f"- {SHORT_RUN_ID}: PDF/TEXT/XLSX structured operation states are recorded in primary report.json only. "
        "Tool surfaces are unavailable in this diagnostic packet, so tool execution and hydration fail closed without "
        "raw tool/prompt/response payloads. SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload "
        "remains candidate-only; tool outputs are excluded from Hit@k/MRR/nDCG. no official/product/promotion/live-readiness "
        "claim is opened."
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
