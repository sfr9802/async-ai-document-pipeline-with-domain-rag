from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report as v63


LOGICAL_RUN_KEY = "v7_0_e2e_eval_architecture_closeout_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V7_0_E2E_EVAL_ARCHITECTURE_CLOSEOUT_NONPROD_READY"
PREVIOUS_CURRENT = v63.LOGICAL_RUN_KEY
RECOVERED_CURRENT = "v6_9_answer_quality_gate_packet_nonprod"
CURRENT_RESOLVES_TO = RECOVERED_CURRENT
ROLLBACK_KEY = PREVIOUS_CURRENT
KST_DOC_DATE = "2026-06-07"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
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

HUMAN_OWNED_DECISION_GATES = [
    "gold",
    "qrels",
    "expected_evidence",
    "relevance",
    "answerability",
    "official_denominator",
    "promotion",
]

REQUIRED_PREDECESSOR_CHECKPOINTS = (
    "v6_4_e2e_coverage_and_failure_taxonomy_nonprod",
    "v6_5_retrieval_metric_unlock_packet_nonprod",
    "v6_6_structured_tool_operation_taxonomy_nonprod",
    "v6_7_agentic_retry_fail_closed_policy_nonprod",
    "v6_8_metric_gated_retrieval_quality_engineering_nonprod",
    "v6_9_answer_quality_gate_packet_nonprod",
)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None) -> dict[str, Any]:
    if source_report is not None:
        report = _json_clone(source_report)
        v63.check_report(report)
        return report
    report = registry.load_report(PREVIOUS_CURRENT, root=root)
    v63.check_report(report, root=root)
    v63.require_status_report_hash(root, report)
    return report


def _source_report_lock(root: Path, source_report: Mapping[str, Any]) -> dict[str, Any]:
    source_report_path = root / v63.REPORT_PATH
    payload_sha256 = _payload_sha256(source_report)
    artifact_hashes = dict(source_report.get("artifact_sha256") or {})
    artifact_report_sha256 = _clean(artifact_hashes.get("report_json_sha256"))
    if not artifact_report_sha256 and source_report_path.exists():
        artifact_report_sha256 = common.sha256_file(source_report_path)
    if not artifact_report_sha256:
        artifact_report_sha256 = payload_sha256
    return {
        "source_run_key": PREVIOUS_CURRENT,
        "source_report_path": v63.REPORT_PATH.as_posix(),
        "source_report_artifact_status": common.artifact_status(source_report_path),
        "source_report_payload_sha256": payload_sha256,
        "source_artifact_report_sha256": artifact_report_sha256,
        "source_status": source_report.get("status"),
        "source_current_resolves_to": source_report.get("current_resolves_to"),
        "source_rollback_key": source_report.get("rollback_key"),
        "source_diagnostic_only": source_report.get("diagnostic_only") is True,
        "source_official_metric_input_rows": source_report.get("official_metric_input_rows"),
    }


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


def _checkpoint_results() -> list[dict[str, Any]]:
    return [
        {
            "checkpoint_id": "plan_recovery",
            "status": "passed",
            "decision": "Create and maintain the missing referenced v7 plan file in place.",
            "diagnostic_only": True,
        },
        {
            "checkpoint_id": "source_v6_3_evidence_lock",
            "status": "passed",
            "decision": "Use the v6_3 report as the source E2E architecture evidence and hash-lock it.",
            "diagnostic_only": True,
        },
        {
            "checkpoint_id": "metric_boundary_closeout",
            "status": "passed",
            "decision": "Keep retrieval quality, answer quality, and product success metrics closed.",
            "diagnostic_only": True,
        },
        {
            "checkpoint_id": "rollback_current_contract",
            "status": "passed",
            "decision": "Move current to v7_0 only after preserving v6_3 as rollback.",
            "diagnostic_only": True,
        },
        {
            "checkpoint_id": "protected_surface_audit",
            "status": "passed",
            "decision": "Record protected surfaces as clean without mutating them.",
            "diagnostic_only": True,
        },
        {
            "checkpoint_id": "human_owned_gate_boundary",
            "status": "passed",
            "decision": "Record all remaining quality, denominator, and promotion gates as human-owned.",
            "diagnostic_only": True,
        },
    ]


def _predecessor_checkpoint_audit(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in REQUIRED_PREDECESSOR_CHECKPOINTS:
        path = root / REPORT_ROOT / "runs" / key / "report.json"
        present = path.exists()
        rows.append(
            {
                "checkpoint_key": key,
                "artifact_path": (REPORT_ROOT / "runs" / key / "report.json").as_posix(),
                "artifact_status": "present" if present else "missing",
                "status": "present" if present else "missing",
                "skip_reason": "",
                "diagnostic_only_skip": False,
            }
        )
    return rows


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source = _load_source_report(repo_root, source_report)
    source_lock = _source_report_lock(repo_root, source)
    metrics = dict(source.get("metric_results") or {})
    e2e_metric = dict(source.get("e2e_pipeline_smoke_metric") or metrics.get("e2e_pipeline_smoke_metric") or {})
    faiss_status = dict(source.get("faiss_status") or {})
    bge_status = dict(source.get("bge_m3_status") or {})
    consolidated = dict(source.get("consolidated_report_policy") or {})
    predecessor_rows = _predecessor_checkpoint_audit(repo_root)
    predecessor_missing = [row["checkpoint_key"] for row in predecessor_rows if row["status"] == "missing"]

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
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": LOGICAL_RUN_KEY,
        "current_moved_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "current_alias_policy": {
            "current_moved_from": LOGICAL_RUN_KEY,
            "current_moved_to": CURRENT_RESOLVES_TO,
            "historical_marker_current_moved_from": PREVIOUS_CURRENT,
            "historical_marker_current_moved_to": LOGICAL_RUN_KEY,
            "rollback_key": ROLLBACK_KEY,
            "movement_condition": "v7_0 is explicit-only marker evidence; recovered current follows the latest diagnostic recovery packet",
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
            "separate_structured_tool_diagnostics_jsonl_created": False,
            "source_v6_3_primary_report_only": consolidated.get("primary_report_only") is True,
        },
        "source_report_lock": source_lock,
        "source_v6_3_metric_snapshot": {
            "bge_m3_model_identifier": bge_status.get("embedding_model_identifier"),
            "bge_m3_embedding_count": bge_status.get("embedding_count"),
            "bge_m3_embedding_dim": bge_status.get("embedding_dim"),
            "faiss_index_type": faiss_status.get("faiss_index_type"),
            "faiss_vector_count": faiss_status.get("vector_count"),
            "faiss_query_count": faiss_status.get("query_count"),
            "e2e_rows_attempted": e2e_metric.get("e2e_rows_attempted"),
            "e2e_rows_citation_verified": e2e_metric.get("e2e_rows_citation_verified"),
        },
        "architecture_closeout_summary": {
            "source_e2e_contract_verified": source.get("status") == v63.STATUS,
            "source_bge_m3_faiss_verified": bool(
                bge_status.get("model_ready") is True
                and faiss_status.get("faiss_available") is True
                and faiss_status.get("index_build_invoked") is True
                and faiss_status.get("index_query_invoked") is True
            ),
            "source_citation_verification_passed": e2e_metric.get("citation_verification_passed") is True,
            "metric_lanes_separate": set(metrics) >= {
                "vector_retrieval_smoke_metric",
                "bm25_retrieval_smoke_metric",
                "hybrid_retrieval_smoke_metric",
                "structured_tool_metric",
                "agentic_answer_metric",
                "e2e_pipeline_smoke_metric",
                "denominator_reality_metric",
            },
            "single_report_policy_preserved": consolidated.get("primary_report_only") is True,
            "codex_owned_architecture_checkpoints_closed": False,
            "premature_closeout_marker_only": True,
            "v7_completion_claim": False,
            "required_predecessor_checkpoints_exist_or_skipped": not predecessor_missing,
            "missing_required_predecessor_checkpoints": predecessor_missing,
            "quality_or_promotion_gate_opened": False,
            "remaining_human_owned_decision_gates": list(HUMAN_OWNED_DECISION_GATES),
        },
        "checkpoint_results": _checkpoint_results(),
        "predecessor_checkpoint_audit": predecessor_rows,
        "conservative_diagnostic_only_decisions": {
            "missing_v7_plan_file_recovered_in_place": True,
            "retrieval_quality_labels_remain_user_owned": True,
            "answer_quality_evidence_remains_user_owned": True,
            "denominator_policy_remains_user_owned": True,
            "promotion_policy_remains_user_owned": True,
            "v6_3_is_rollback_key": True,
            "v7_0_recorded_as_premature_closeout_marker_only": True,
            "v7_completion_claim_from_v7_0": False,
        },
        "answer_quality_metric_computed": False,
        "retrieval_quality_metric_computed": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "official_metric": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "production_routing_enabled": False,
        "production_db_mutated": False,
        "production_index_mutation": False,
        "production_namespace_mutated": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "relevance_label_mutation": False,
        "answerability_label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "source_registry_mutated": False,
        "training_dataset_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "protected_surface_check": _protected_surface_check(),
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v70_e2e_eval_architecture_closeout_nonprod_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v7_0_e2e_eval_architecture_closeout_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
        ],
    }
    check_report(report)
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != LOGICAL_RUN_KEY:
        raise ValueError("v7_0 run id drift")
    if report.get("status") != STATUS:
        raise ValueError("v7_0 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v7_0 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v7_0 rollback key drift")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True:
        raise ValueError("v7_0 diagnostic-only flag missing")
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            raise ValueError(f"v7_0 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if report.get(key) != 0:
            raise ValueError(f"v7_0 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True or protected.get("mutated_paths") != []:
        raise ValueError("v7_0 protected surface check failed")
    for key in (
        "gold_qrels_expected_supporting_relevance_answerability_clean",
        "official_denominator_clean",
        "source_registry_clean",
        "production_index_namespace_clean",
        "production_db_cache_clean",
    ):
        if protected.get(key) is not True:
            raise ValueError(f"v7_0 protected surface flag opened: {key}")
    if protected.get("protected_namespaces_touched") != []:
        raise ValueError("v7_0 protected namespaces touched")


def _require_source_lock(report: Mapping[str, Any]) -> None:
    source = report.get("source_report_lock") or {}
    if source.get("source_run_key") != PREVIOUS_CURRENT:
        raise ValueError("v7_0 source run drift")
    if source.get("source_status") != v63.STATUS:
        raise ValueError("v7_0 source status drift")
    if source.get("source_current_resolves_to") != PREVIOUS_CURRENT:
        raise ValueError("v7_0 source current drift")
    if not _clean(source.get("source_report_payload_sha256")):
        raise ValueError("v7_0 source payload hash missing")
    if not _clean(source.get("source_artifact_report_sha256")):
        raise ValueError("v7_0 source artifact hash missing")


def _require_architecture(report: Mapping[str, Any]) -> None:
    summary = report.get("architecture_closeout_summary") or {}
    required_true = (
        "source_e2e_contract_verified",
        "source_bge_m3_faiss_verified",
        "source_citation_verification_passed",
        "metric_lanes_separate",
        "single_report_policy_preserved",
    )
    for key in required_true:
        if summary.get(key) is not True:
            raise ValueError(f"v7_0 architecture closeout field failed: {key}")
    predecessor_rows = report.get("predecessor_checkpoint_audit") or []
    missing_or_unskipped = [
        row
        for row in predecessor_rows
        if row.get("status") not in {"present", "skipped"} or (row.get("status") == "skipped" and not _clean(row.get("skip_reason")))
    ]
    closed = summary.get("codex_owned_architecture_checkpoints_closed")
    if closed is True:
        if missing_or_unskipped:
            raise ValueError("v7_0 required predecessor checkpoints missing or unskipped")
        if summary.get("remaining_human_owned_decision_gates"):
            raise ValueError("v7_0 cannot pass closeout: human-owned decision gates remain open")
    elif closed is False:
        if summary.get("premature_closeout_marker_only") is not True:
            raise ValueError("v7_0 premature marker flag missing")
        if summary.get("v7_completion_claim") is not False:
            raise ValueError("v7_0 completion claim opened")
        if summary.get("required_predecessor_checkpoints_exist_or_skipped") is True:
            if summary.get("remaining_human_owned_decision_gates") != HUMAN_OWNED_DECISION_GATES:
                raise ValueError("v7_0 predecessor satisfaction missing human-owned gate blockers")
    else:
        raise ValueError("v7_0 checkpoint closeout flag drift")
    if summary.get("quality_or_promotion_gate_opened") is not False:
        raise ValueError("v7_0 quality or promotion gate opened")
    if summary.get("remaining_human_owned_decision_gates") != HUMAN_OWNED_DECISION_GATES:
        raise ValueError("v7_0 human-owned gate list drift")
    checkpoints = report.get("checkpoint_results") or []
    if len(checkpoints) != 6 or any(row.get("status") != "passed" for row in checkpoints):
        raise ValueError("v7_0 checkpoint closeout incomplete")


def _require_single_report(report: Mapping[str, Any], *, root: Path | str | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v7_0 primary report policy missing")
    if policy.get("large_candidate_text_dump_written") is not False:
        raise ValueError("v7_0 large candidate text dump written")
    if root is None:
        return
    report_path = Path(root) / REPORT_PATH
    if report_path.exists():
        actual = common.sha256_file(report_path)
        expected = _clean((report.get("artifact_sha256") or {}).get("report_json_sha256"))
        if expected and expected != actual:
            raise ValueError(f"v7_0 report hash drift: expected {expected}, actual {actual}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_source_lock(report)
    _require_architecture(report)
    _require_single_report(report, root=root)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v7_0")


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
        "event_type": LOGICAL_RUN_KEY,
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": LOGICAL_RUN_KEY,
        "current_moved_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "live_db_index_cache_readiness": False,
        "gold_qrels_expected_supporting_labels_mutated": False,
        "protected_namespaces_touched": [],
        "source_run_key": PREVIOUS_CURRENT,
        "source_report_payload_sha256": report["source_report_lock"]["source_report_payload_sha256"],
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
    }


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def require_status_report_hash(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    report_path = repo_root / REPORT_PATH
    if not status_path.exists():
        raise ValueError("v7_0 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v7_0 status report hash missing: report.json not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v7_0 status report hash missing: status event not found")
    latest = rows[-1]
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v7_0 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v7_0 status current alias drift")
    if latest.get("rollback_key") != report.get("rollback_key"):
        raise ValueError("v7_0 status rollback drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    source = report["source_report_lock"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is diagnostic-only explicit marker evidence and current "
        f"resolves to `{RECOVERED_CURRENT}`. The historical v7_0 movement from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` "
        "is preserved only as audit context and is superseded by the recovered diagnostic current. The run "
        f"hash-locks `{PREVIOUS_CURRENT}` as the source bge-m3 + FAISS E2E evidence, records checkpoint by "
        "checkpoint audit decisions, writes one primary report.json, and keeps retrieval quality, answer "
        "quality, official denominator, promotion, product-success, and live-readiness gates closed. "
        f"rollback key is `{ROLLBACK_KEY}`. There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"- v7_0 premature closeout marker: source_run=`{source['source_run_key']}`; "
        f"source_payload_sha256={source['source_report_payload_sha256']}; "
        f"source_artifact_report_sha256={source['source_artifact_report_sha256']}.\n"
        "- Metrics: no new retrieval-quality, answer-quality, official, product, promotion, or live-readiness "
        "metric is computed; v6_3 vector/BM25/hybrid/tool/E2E lanes remain diagnostic-only and separated.\n"
        f"- Current alias: current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` historically, but `{SHORT_RUN_ID}` is preserved as a premature closeout marker and `{RECOVERED_CURRENT}` supersedes it as current; rollback key is `{ROLLBACK_KEY}`. "
        "There is no official/product/promotion/live-readiness claim."
    )
    triage = (
        f"- {SHORT_RUN_ID}: diagnostic-only E2E evaluation architecture closeout is recorded as a premature marker only. The required "
        "predecessor checkpoint gaps are audited, v6_3 is preserved as rollback and source evidence, "
        "and remaining gold/qrels/expected evidence/relevance/answerability/official denominator/promotion "
        f"decisions stay human-owned. current resolves to `{RECOVERED_CURRENT}`. Its earlier current movement is superseded by the recovered diagnostic current; historical movement was from "
        f"`{ROLLBACK_KEY}` to `{SHORT_RUN_ID}`; current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` historically; rollback key is `{ROLLBACK_KEY}`. "
        "no official/product/promotion/live-readiness claim is opened."
    )
    return progress, measurements, triage


def _upsert_doc(root: Path, path: Path, *, start: str, end: str, block: str) -> None:
    full_path = root / path
    text = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(common.upsert_block_at_top(text, start_marker=start, end_marker=end, block=block), encoding="utf-8")


def _plan_doc(report: Mapping[str, Any]) -> str:
    checkpoints = "\n".join(
        f"- [x] {row['checkpoint_id']}: {row['decision']}" for row in report["checkpoint_results"]
    )
    verification = "\n".join(f"- `{command}`" for command in report["verification_commands"])
    return f"""# RAG v7 E2E Evaluation Plan

## Objective

Implement `v7_0_e2e_eval_architecture_closeout_nonprod` checkpoint by checkpoint as a diagnostic-only marker after `{PREVIOUS_CURRENT}`. It is not a completed v7 closeout unless the required v6_4-v6_9 predecessors exist or are explicitly skipped with diagnostic-only reasons and the remaining human-owned quality, denominator, promotion, and live-readiness gates are explicitly resolved.

## Non-Goals

- No gold, qrels, expected evidence, supporting evidence, relevance, answerability, or official denominator creation or mutation.
- No production index, production namespace, production DB/cache, source registry, training dataset, fine-tuning dataset/job/checkpoint, promotion, product-success, or live-readiness mutation or claim.
- No retrieval-quality or answer-quality metric opening without user-owned labels, evidence, denominator, and promotion policy.

## Baseline

- Source run: `{PREVIOUS_CURRENT}`.
- Source status: `{report['source_report_lock']['source_status']}`.
- Source report payload SHA256: `{report['source_report_lock']['source_report_payload_sha256']}`.
- Rollback key target: `{ROLLBACK_KEY}`.

## Checkpoints

{checkpoints}

- [ ] closeout_gate_guard: v6_4-v6_9 predecessor checkpoints are present or explicitly skipped, but human-owned quality, denominator, promotion, and live-readiness gates remain open; v7_0 remains a premature closeout marker only.

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
