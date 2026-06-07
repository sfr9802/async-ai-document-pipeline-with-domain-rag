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
from ai.eval import rag_v67_agentic_retry_fail_closed_policy_nonprod as v67
from ai.eval import rag_v68_metric_gated_retrieval_quality_engineering_nonprod as v68


LOGICAL_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_9_ANSWER_QUALITY_GATE_PACKET_NONPROD_READY"
PREVIOUS_CURRENT = v68.LOGICAL_RUN_KEY
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
REQUIRED_FALSE_REPORT_FIELDS = (
    "official_metric",
    "retrieval_quality_metric_computed",
    "answer_quality_metric_computed",
    "agentic_answer_metric_computed",
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
    "generated_final_answer_text",
    "query_text",
    "expected_answer",
    "expected_answer_text",
    "supporting_evidence",
    "supporting_evidence_text",
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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _protected_surface_check() -> dict[str, Any]:
    return v651._protected_surface_check()  # type: ignore[attr-defined]


def _load_v651(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v651.LOGICAL_RUN_KEY, root=root)
    v651.check_report(source, root=root if report is None else None)
    if report is None:
        v651.require_status_report_hash(root, source)
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


def _load_v68(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v68.LOGICAL_RUN_KEY, root=root)
    v68.check_report(source, root=root if report is None else None)
    if report is None:
        v68.require_status_report_hash(root, source)
    return source


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _source_v651_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    summary = source["actual_response_smoke_summary"]
    packet = source["actual_response_review_packet"]
    return {
        "run_key": v651.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "actual_response_rows_attempted": summary["actual_response_rows_attempted"],
        "actual_response_rows_rendered": summary["actual_response_rows_rendered"],
        "citation_verified_rows": summary["citation_verified_rows"],
        "fail_closed_rows": summary["fail_closed_rows"],
        "review_packet_rows": packet["row_count"],
        "expected_answer_text_included": packet["expected_answer_text_included"],
        "supporting_evidence_text_included": packet["supporting_evidence_text_included"],
        "human_owned_decisions_filled": packet["human_owned_decisions_filled"],
    }


def _source_v66_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    summary = source["tool_operation_summary"]
    return {
        "run_key": v66.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "tool_operation_rows": summary["tool_operation_rows"],
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
        "retry_attempted_rows": summary["retry_attempted_rows"],
        "final_answer_rendered_rows": summary["final_answer_rendered_rows"],
        "final_citation_verified_rows": summary["final_citation_verified_rows"],
        "answer_quality_metric_computed": source.get("answer_quality_metric_computed") is True,
    }


def _source_v68_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    gate = source["retrieval_quality_gate"]
    return {
        "run_key": v68.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "safe_read_only_denominator_available": gate["safe_read_only_denominator_available"],
        "retrieval_quality_metric_computed": gate["retrieval_quality_metric_computed"],
        "computed_only_denominator": gate["computed_only_denominator"],
        "coverage_adjusted_denominator": gate["coverage_adjusted_denominator"],
        "blocked_reason": gate["blocked_reason"],
    }


def _answer_quality_gate_policy() -> dict[str, Any]:
    return {
        "human_review_required_before_metric": True,
        "codex_filled_human_review_fields": False,
        "expected_supporting_text_excluded": True,
        "promotion_decision_left_blank": True,
        "official_denominator_decision_left_blank": True,
        "answer_quality_pass_fail_left_blank": True,
        "relevance_answerability_left_blank": True,
        "metric_open_condition": (
            "human-owned pass/fail, relevance, answerability, official denominator, "
            "supporting evidence, and promotion policy decisions supplied later"
        ),
    }


def _build_gate_packet(
    v651_report: Mapping[str, Any],
    v66_report: Mapping[str, Any],
    v67_report: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    tool_by_hash = {row["gold_row_hash"]: row for row in v66_report["tool_operation_rows"]}
    agentic_by_hash = {row["gold_row_hash"]: row for row in v67_report["agentic_loop_rows"]}
    public_by_hash = {row["gold_row_hash"]: row for row in v651_report["response_diagnostics"]}
    rows: list[dict[str, Any]] = []
    family_counter: Counter[str] = Counter()
    route_counter: Counter[str] = Counter()
    verification_counter: Counter[str] = Counter()
    for review_row in v651_report["actual_response_review_packet"]["rows"]:
        gold_hash = review_row["gold_row_hash"]
        public = public_by_hash[gold_hash]
        tool = tool_by_hash[gold_hash]
        agentic = agentic_by_hash[gold_hash]
        family = _clean(review_row.get("source_family"))
        route = _clean(review_row.get("route_decision"))
        verification = _clean(agentic.get("verification_state"))
        family_counter[family] += 1
        route_counter[route] += 1
        verification_counter[verification] += 1
        rows.append(
            {
                "gold_row_hash": gold_hash,
                "source_family": family,
                "query_hash": public["query_hash"],
                "generated_answer_preview_or_hash": {
                    "redacted": True,
                    "sha256": _sha256_text(_clean(review_row.get("generated_final_answer_text"))),
                },
                "citation_hashes": [
                    _sha256_json(citation)
                    for citation in list(review_row.get("rendered_citations") or [])
                ],
                "route_status": route,
                "tool_status": tool["operation_state"],
                "agentic_verification_state": verification,
                "expected_answer_hash": _clean(review_row.get("expected_answer_hash")),
                "supporting_evidence_hash": _clean(review_row.get("supporting_evidence_hash")),
                "qrels_payload_hash": _clean(review_row.get("qrels_payload_hash")),
                "answer_rendered": review_row.get("answer_rendered") is True,
                "citation_verified": review_row.get("citation_verified") is True,
                "human_pass_fail": "",
                "human_relevance": "",
                "human_answerability": "",
                "official_denominator_decision": "",
                "promotion_decision": "",
            }
        )
    packet = {
        "packet_location": "primary_report_json_only",
        "row_count": len(rows),
        "review_fields_left_blank": True,
        "human_owned_decisions_filled": False,
        "expected_answer_hash_included": True,
        "supporting_evidence_hash_included": True,
        "qrels_payload_hash_included": True,
        "expected_answer_text_included": False,
        "supporting_evidence_text_included": False,
        "raw_generated_answer_text_included": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "rows": rows,
    }
    summary = {
        "packet_rows": len(rows),
        "silently_dropped_rows": 29 - len(rows),
        "rows_by_family": _counter_dict(family_counter),
        "route_status_counts": dict(route_counter),
        "agentic_verification_state_counts": {
            key: int(verification_counter.get(key, 0))
            for key in ("passed", "failed", "skipped_no_answer", "not_applicable")
        },
        "human_owned_blank_rows": sum(
            1
            for row in rows
            if row["human_pass_fail"] == ""
            and row["human_relevance"] == ""
            and row["human_answerability"] == ""
            and row["official_denominator_decision"] == ""
            and row["promotion_decision"] == ""
        ),
        "answer_quality_metric_computed": False,
        "agentic_answer_metric_computed": False,
    }
    return packet, summary


def _v7_guard() -> dict[str, Any]:
    return {
        "v7_0_recorded_as_premature_closeout_marker_only": True,
        "v7_completion_claim_from_v7_0": False,
        "all_v6_4_to_v6_9_predecessors_present": True,
        "missing_or_unskipped_predecessors": [],
        "predecessor_satisfaction_is_not_v7_completion": True,
        "remaining_human_owned_decision_gates_block_v7_completion": True,
    }


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    v6_5_1_report: Mapping[str, Any] | None = None,
    v6_6_report: Mapping[str, Any] | None = None,
    v6_7_report: Mapping[str, Any] | None = None,
    v6_8_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source_v651 = _load_v651(repo_root, v6_5_1_report)
    source_v66 = _load_v66(repo_root, v6_6_report)
    source_v67 = _load_v67(repo_root, v6_7_report)
    source_v68 = _load_v68(repo_root, v6_8_report)
    packet, summary = _build_gate_packet(source_v651, source_v66, source_v67)
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
            "movement_condition": "v6_9 answer-quality gate packet, human-owned blank-field, single-report, and current-focused checks pass",
            "official_product_promotion_live_readiness_claim": False,
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": {},
        "generated_artifacts": [REPORT_PATH.as_posix()],
        "consolidated_report_policy": {
            "primary_report_only": True,
            "primary_report_path": REPORT_PATH.as_posix(),
            "separate_answer_quality_packet_jsonl_created": False,
            "separate_human_review_packet_csv_created": False,
            "separate_metric_results_json_created": False,
            "separate_promotion_decision_file_created": False,
            "separate_denominator_decision_file_created": False,
        },
        "source_v6_5_1_response_check": _source_v651_summary(source_v651),
        "source_v6_6_tool_check": _source_v66_summary(source_v66),
        "source_v6_7_agentic_check": _source_v67_summary(source_v67),
        "source_v6_8_retrieval_gate_check": _source_v68_summary(source_v68),
        "answer_quality_gate_policy": _answer_quality_gate_policy(),
        "answer_quality_gate_packet": packet,
        "answer_quality_gate_summary": summary,
        "human_owned_decisions_filled": False,
        "protected_surface_check": _protected_surface_check(),
        "v7_guard": _v7_guard(),
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        **{field: False for field in REQUIRED_FALSE_REPORT_FIELDS},
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v69_answer_quality_gate_packet_nonprod_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_9_answer_quality_gate_packet_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_8_metric_gated_retrieval_quality_engineering_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py v7_0_e2e_eval_architecture_closeout_nonprod --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
        ],
    }
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != LOGICAL_RUN_KEY or report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_9 run identity drift")
    if report.get("schema_version") != f"{SHORT_RUN_ID}_report_v1":
        raise ValueError("v6_9 schema drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_9 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_9 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_9 rollback key drift")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v6_9 diagnostic/non-production flag missing")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            if key == "answer_quality_metric_computed":
                raise ValueError("v6_9 answer quality metric opened")
            if key == "agentic_answer_metric_computed":
                raise ValueError("v6_9 agentic answer metric opened")
            raise ValueError(f"v6_9 protected field opened: {key}")
    if report.get("human_owned_decisions_filled") is not False:
        raise ValueError("v6_9 human-owned decisions filled")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if int(report.get(key) or 0) != 0:
            raise ValueError(f"v6_9 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True:
        raise ValueError("v6_9 protected surface check failed")
    if protected.get("mutated_paths") or protected.get("protected_namespaces_touched"):
        raise ValueError("v6_9 protected namespaces touched")


def _require_sources(report: Mapping[str, Any]) -> None:
    if (report.get("source_v6_5_1_response_check") or {}).get("actual_response_rows_attempted") != 29:
        raise ValueError("v6_9 source v6_5_1 response row drift")
    if (report.get("source_v6_6_tool_check") or {}).get("tool_operation_rows") != 29:
        raise ValueError("v6_9 source v6_6 tool row drift")
    if (report.get("source_v6_7_agentic_check") or {}).get("agentic_loop_rows") != 29:
        raise ValueError("v6_9 source v6_7 agentic row drift")
    v68_source = report.get("source_v6_8_retrieval_gate_check") or {}
    if v68_source.get("retrieval_quality_metric_computed") is not False:
        raise ValueError("v6_9 source v6_8 retrieval metric opened")
    if v68_source.get("computed_only_denominator") != 0:
        raise ValueError("v6_9 source v6_8 computed-only denominator opened")


def _require_policy(report: Mapping[str, Any]) -> None:
    policy = report.get("answer_quality_gate_policy") or {}
    if policy.get("human_review_required_before_metric") is not True:
        raise ValueError("v6_9 human review gate missing")
    if policy.get("codex_filled_human_review_fields") is not False:
        raise ValueError("v6_9 Codex filled human-owned fields")
    if policy.get("expected_supporting_text_excluded") is not True:
        raise ValueError("v6_9 expected/supporting text included")
    if policy.get("promotion_decision_left_blank") is not True:
        raise ValueError("v6_9 promotion decision not left blank")


def _require_packet(report: Mapping[str, Any]) -> None:
    packet = report.get("answer_quality_gate_packet") or {}
    summary = report.get("answer_quality_gate_summary") or {}
    if packet.get("packet_location") != "primary_report_json_only":
        raise ValueError("v6_9 packet location drift")
    if packet.get("review_fields_left_blank") is not True:
        raise ValueError("v6_9 review fields not left blank")
    if packet.get("human_owned_decisions_filled") is not False:
        raise ValueError("v6_9 human-owned decisions filled in packet")
    for key in ("expected_answer_text_included", "supporting_evidence_text_included", "raw_generated_answer_text_included"):
        if packet.get(key) is not False:
            raise ValueError(f"v6_9 raw review text included: {key}")
    rows = list(packet.get("rows") or [])
    if len(rows) != 29 or packet.get("row_count") != 29 or summary.get("packet_rows") != 29:
        raise ValueError("v6_9 answer-quality gate packet row drift")
    if summary.get("silently_dropped_rows") != 0:
        raise ValueError("v6_9 answer-quality gate rows dropped")
    if summary.get("rows_by_family") != {"PDF": 4, "TEXT": 6, "XLSX": 19}:
        raise ValueError("v6_9 answer-quality gate family drift")
    if summary.get("human_owned_blank_rows") != 29:
        raise ValueError("v6_9 human-owned blank-row count drift")
    for row in rows:
        for field in (
            "human_pass_fail",
            "human_relevance",
            "human_answerability",
            "official_denominator_decision",
            "promotion_decision",
        ):
            if row.get(field) != "":
                raise ValueError("v6_9 human-owned review field filled")
        preview = row.get("generated_answer_preview_or_hash") or {}
        if preview.get("redacted") is not True or not _clean(preview.get("sha256")):
            raise ValueError("v6_9 generated answer hash missing")
        if not _clean(row.get("expected_answer_hash")) or not _clean(row.get("supporting_evidence_hash")):
            raise ValueError("v6_9 expected/supporting hashes missing")
        if row.get("agentic_verification_state") not in {"passed", "failed", "skipped_no_answer", "not_applicable"}:
            raise ValueError("v6_9 agentic verification state drift")


def _require_v7_guard(report: Mapping[str, Any]) -> None:
    guard = report.get("v7_guard") or {}
    if guard.get("v7_0_recorded_as_premature_closeout_marker_only") is not True:
        raise ValueError("v6_9 v7 premature marker guard failed")
    if guard.get("v7_completion_claim_from_v7_0") is not False:
        raise ValueError("v6_9 v7 completion claim opened")
    if guard.get("all_v6_4_to_v6_9_predecessors_present") is not True:
        raise ValueError("v6_9 predecessor presence not recorded")
    if guard.get("missing_or_unskipped_predecessors") != []:
        raise ValueError("v6_9 predecessor list should be empty")
    if guard.get("predecessor_satisfaction_is_not_v7_completion") is not True:
        raise ValueError("v6_9 predecessor satisfaction promoted to v7 completion")


def _require_single_report(report: Mapping[str, Any], root: Path | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v6_9 primary report policy missing")
    if root is not None:
        run_root = root / RUN_ROOT
        if run_root.exists():
            names = {path.name for path in run_root.iterdir()}
            if names != {"report.json"}:
                raise ValueError(f"v6_9 single primary report policy violated: {sorted(names)}")
            expected = _clean((report.get("artifact_sha256") or {}).get("report_json_sha256"))
            if expected and common.sha256_file(run_root / "report.json") != expected:
                raise ValueError("v6_9 report hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    repo_root = Path(root) if root is not None else None
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_sources(report)
    _require_policy(report)
    _require_packet(report)
    _require_v7_guard(report)
    _require_single_report(report, repo_root)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v6_9")


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
    summary = report["answer_quality_gate_summary"]
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
        "answer_quality_metric_computed": False,
        "agentic_answer_metric_computed": False,
        "human_owned_decisions_filled": False,
        "answer_quality_gate_packet_rows": summary["packet_rows"],
        "human_owned_blank_rows": summary["human_owned_blank_rows"],
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
        raise ValueError("v6_9 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_9 status report hash missing: report.json not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v6_9 status report hash missing: status event not found")
    latest = rows[-1]
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_9 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_9 status current alias drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    summary = report["answer_quality_gate_summary"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is a diagnostic-only answer-quality gate packet over "
        f"v6_5_1/v6_6/v6_7/v6_8. current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` after v6_9 checks; "
        f"rollback key is `{ROLLBACK_KEY}`. packet_rows={summary['packet_rows']}; human-owned review fields remain blank; "
        "answer_quality_metric_computed=false. There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        f"- Answer-quality gate packet: rows={summary['packet_rows']}; rows_by_family={summary['rows_by_family']}; "
        f"human_owned_blank_rows={summary['human_owned_blank_rows']}; agentic_verification_state_counts="
        f"{summary['agentic_verification_state_counts']}.\n"
        "- Metrics policy: answer_quality_metric_computed=false; agentic_answer_metric_computed=false; "
        "expected/supporting text is excluded, generated answers are redacted to hashes, and human-owned decisions are blank. "
        "No official/product/promotion/live-readiness claim is opened."
    )
    triage = (
        f"- {SHORT_RUN_ID}: answer-quality review preparation is embedded in primary report.json only with hashes for "
        "generated answers, citations, expected answers, supporting evidence, and qrels payloads. human-owned pass/fail, "
        "relevance, answerability, official denominator, and promotion fields are blank. no official/product/promotion/live-readiness claim is opened."
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
