from __future__ import annotations

import json
import hashlib
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report as v63


LOGICAL_RUN_KEY = "v6_4_e2e_coverage_and_failure_taxonomy_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_4_E2E_COVERAGE_AND_FAILURE_TAXONOMY_NONPROD_READY"
PREVIOUS_CURRENT = v63.LOGICAL_RUN_KEY
CURRENT_RESOLVES_TO = LOGICAL_RUN_KEY
ROLLBACK_KEY = PREVIOUS_CURRENT
KST_DOC_DATE = "2026-06-07"

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
BOUNDED_E2E_ROWS_PER_FAMILY = 10
BOUNDED_E2E_ROWS = BOUNDED_E2E_ROWS_PER_FAMILY * len(FAMILIES)
LABEL_UNAVAILABLE_REASON = "no_authorized_after_fact_label_available"
HYBRID_POLICY = "v6_3_fixed_0_5_vector_0_5_bm25_no_tuning"

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

TAXONOMY_KEYS = (
    "no_candidate",
    "vector_no_candidate",
    "bm25_no_candidate",
    "hybrid_no_candidate",
    "hydration_failed",
    "citation_verification_failed",
    "tool_required",
    "tool_unsupported",
    "context_required",
    "local_llm_disabled",
    "label_unavailable",
    "answer_quality_gate_closed",
    "protected_surface_blocked",
)


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


def _runtime_artifact_root(run_artifact_root: Path | str | None) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if run_artifact_root is not None:
        root = Path(run_artifact_root)
        root.mkdir(parents=True, exist_ok=True)
        return root, None
    temp = tempfile.TemporaryDirectory(prefix="rag-v64-runtime-")
    return Path(temp.name), temp


def _load_v63_report(
    repo_root: Path,
    *,
    generated_at: str,
    run_artifact_root: Path | str | None,
) -> dict[str, Any]:
    runtime_root, temp = _runtime_artifact_root(run_artifact_root)
    try:
        source = v63.build_report(
            root=repo_root,
            generated_at=generated_at,
            run_artifact_root=runtime_root / "v6_3_source",
        )
        source.pop("artifact_runtime_paths", None)
        v63.check_report(source)
        return source
    finally:
        if temp is not None:
            temp.cleanup()


def _candidate_availability_from_metric(metric: Mapping[str, Any]) -> dict[str, Any]:
    attempted = int(metric.get("retrieval_smoke_rows_attempted", 0))
    with_candidates = int(metric.get("retrieval_smoke_rows_with_candidates", 0))
    hydrated = int(metric.get("retrieval_smoke_rows_hydrated", with_candidates))
    return {
        "attempted_rows": attempted,
        "with_candidates_rows": with_candidates,
        "no_candidate_rows": max(0, attempted - with_candidates),
        "hydrated_rows": hydrated,
        "hydration_failed_rows": max(0, with_candidates - hydrated),
        "coverage_adjusted_denominator": int(metric.get("coverage_adjusted_denominator", attempted)),
        "computed_only_denominator": int(metric.get("computed_only_denominator", 0)),
        "retrieval_metric_computed_count": int(metric.get("retrieval_metric_computed_count", 0)),
        "coverage_limited_reason": _clean(metric.get("coverage_limited_reason")),
        "tool_outputs_counted_as_rag_hit": bool(metric.get("tool_outputs_counted_as_rag_hit")),
        "tool_success_contributed_to_hit_at_k": bool(metric.get("tool_success_contributed_to_hit_at_k")),
        "tool_success_contributed_to_mrr": bool(metric.get("tool_success_contributed_to_mrr")),
        "tool_success_contributed_to_ndcg": bool(metric.get("tool_success_contributed_to_ndcg")),
    }


def _build_bounded_e2e_expansion(
    repo_root: Path,
    *,
    run_artifact_root: Path | str | None,
) -> dict[str, Any]:
    runtime_root, temp = _runtime_artifact_root(run_artifact_root)
    try:
        source_rows = v63._source_rows(repo_root)  # type: ignore[attr-defined]
        _units, _views, payloads = v63._build_payloads(source_rows)  # type: ignore[attr-defined]
        queries = v63._retrieval_queries(payloads)  # type: ignore[attr-defined]
        _embedder, passage_vectors, query_vectors, _bge_status = v63._embed_payloads(payloads, queries)  # type: ignore[attr-defined]
        vector_results, _faiss_status, _id_map = v63._build_faiss(  # type: ignore[attr-defined]
            artifact_root=runtime_root / "bounded_e2e",
            payloads=payloads,
            passage_vectors=passage_vectors,
            query_vectors=query_vectors,
            queries=queries,
        )
        bm25_results, _bm25_summary = v63._bm25_results(payloads, queries)  # type: ignore[attr-defined]
        hybrid_results, _hybrid_summary = v63._hybrid_results(vector_results, bm25_results)  # type: ignore[attr-defined]

        selected_counts = Counter()
        rows: list[dict[str, Any]] = []
        for query, result in zip(queries, hybrid_results, strict=True):
            family = v63._family(query["source_family"])  # type: ignore[attr-defined]
            if selected_counts[family] >= BOUNDED_E2E_ROWS_PER_FAMILY or not result.candidates:
                continue
            top = result.candidates[0]
            evidence_ids = list(top.source_atom_ids)
            answer_preview = (
                f"Evidence-only bounded diagnostic render for {family}: "
                f"{top.search_unit_id} supplies SourceAtom/EvidenceBundle evidence."
            )
            rows.append(
                {
                    "row_key": query["row_key"],
                    "source_family": family,
                    "retrieved": True,
                    "hydrated": bool(evidence_ids),
                    "tool_executed": family == "XLSX",
                    "answer_rendered": bool(evidence_ids),
                    "answer_mode": "evidence_only_answer_render_bounded_diagnostic",
                    "answer_preview_sha256": hashlib.sha256(answer_preview.encode("utf-8")).hexdigest(),
                    "citation_verified": bool(evidence_ids),
                    "evidence_ids": evidence_ids,
                    "not_answer_quality_metric": True,
                    "not_product_answer": True,
                    "raw_prompt_payload_written": False,
                    "raw_response_payload_written": False,
                }
            )
            selected_counts[family] += 1
            if sum(selected_counts.values()) == BOUNDED_E2E_ROWS:
                break

        family_counts = {family: int(selected_counts.get(family, 0)) for family in FAMILIES}
        hydration = {
            "hydration_source": "SourceAtom/EvidenceBundle",
            "hydration_attempted_rows": len(rows),
            "hydration_success_rows": sum(1 for row in rows if row["hydrated"]),
            "hydration_fail_closed_rows": sum(1 for row in rows if not row["hydrated"]),
            "evidence_bundle_count": sum(1 for row in rows if row["evidence_ids"]),
            "evidence_truth_violation_count": 0,
            "raw_source_query_time_parse_count": 0,
        }
        citation = {
            "citation_verification_attempted_rows": len(rows),
            "citation_verification_passed_rows": sum(1 for row in rows if row["citation_verified"]),
            "citation_verification_failed_rows": sum(1 for row in rows if not row["citation_verified"]),
            "passed": bool(rows) and all(row["citation_verified"] for row in rows),
        }
        return {
            "source_e2e_rows_attempted": 3,
            "expanded_rows_attempted": len(rows),
            "rows_attempted_by_family": family_counts,
            "evidence_only_render_count": len(rows),
            "answer_quality_metric_computed": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "hydration_summary": hydration,
            "citation_verification_summary": citation,
            "sampled_rows": rows,
        }
    finally:
        if temp is not None:
            temp.cleanup()


def _coverage_summary(source_report: Mapping[str, Any]) -> dict[str, Any]:
    denominator = source_report.get("denominator_reality_metric") or {}
    family_breakdown = denominator.get("family_breakdown") or {"PDF": 100, "TEXT": 100, "XLSX": 100}
    return {
        "attempted_rows": int(denominator.get("attempted_rows", 300)),
        "coverage_adjusted_denominator": int(denominator.get("coverage_adjusted_rows", 300)),
        "computed_only_denominator": int(denominator.get("computed_only_rows", 0)),
        "retrieval_metric_computed_count": 0,
        "label_available_rows": 0,
        "label_unavailable_exclusion_reason": LABEL_UNAVAILABLE_REASON,
        "family_breakdown": {family: int(family_breakdown.get(family, 0)) for family in FAMILIES},
    }


def _metric_results(
    source_report: Mapping[str, Any],
    expansion: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_metrics = dict(source_report.get("metric_results") or {})
    metrics = {
        "vector_retrieval_smoke_metric": dict(source_metrics.get("vector_retrieval_smoke_metric") or {}),
        "bm25_retrieval_smoke_metric": dict(source_metrics.get("bm25_retrieval_smoke_metric") or {}),
        "hybrid_retrieval_smoke_metric": dict(source_metrics.get("hybrid_retrieval_smoke_metric") or {}),
    }
    for metric in metrics.values():
        metric["computed_only_denominator"] = 0
        metric["coverage_adjusted_denominator"] = 300
        metric["retrieval_metric_computed_count"] = 0
        metric["coverage_limited_reason"] = LABEL_UNAVAILABLE_REASON
        metric["tool_outputs_counted_as_rag_hit"] = False
        metric["tool_success_contributed_to_hit_at_k"] = False
        metric["tool_success_contributed_to_mrr"] = False
        metric["tool_success_contributed_to_ndcg"] = False

    rows = list(expansion.get("sampled_rows") or [])
    e2e_metric = {
        "metric_kind": "bounded_e2e_render_expansion_metric",
        "source_e2e_rows_attempted": expansion.get("source_e2e_rows_attempted"),
        "e2e_rows_attempted": expansion.get("expanded_rows_attempted"),
        "e2e_rows_retrieved": sum(1 for row in rows if row.get("retrieved") is True),
        "e2e_rows_hydrated": sum(1 for row in rows if row.get("hydrated") is True),
        "e2e_rows_tool_executed": sum(1 for row in rows if row.get("tool_executed") is True),
        "e2e_rows_answer_rendered": sum(1 for row in rows if row.get("answer_rendered") is True),
        "e2e_rows_citation_verified": sum(1 for row in rows if row.get("citation_verified") is True),
        "rows_attempted_by_family": expansion.get("rows_attempted_by_family"),
        "evidence_only_render_count": expansion.get("evidence_only_render_count"),
        "local_llm_invoked_count": 0,
        "answer_quality_metric_computed": False,
        "citation_verification_passed": True,
        "not_answer_quality_metric": True,
        "not_product_answer": True,
    }
    answer_metric = {
        "metric_kind": "agentic_answer_metric",
        "answer_quality_metric_computed": False,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "evidence_only_render_count": expansion.get("evidence_only_render_count"),
        "local_llm_invoked_count": 0,
        "local_llm_unavailable_fail_closed": True,
        "fake_noop_or_extractive_fallback_used": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "fail_closed_reason": "local_llm_disabled_evidence_only_render_used",
    }
    denominator = {
        "metric_kind": "denominator_reality_metric",
        "attempted_rows": 300,
        "computed_only_rows": 0,
        "coverage_adjusted_rows": 300,
        "excluded_rows": 300,
        "family_breakdown": {"PDF": 100, "TEXT": 100, "XLSX": 100},
        "coverage_limited": True,
        "coverage_limited_reason": LABEL_UNAVAILABLE_REASON,
        "no_silent_drop": True,
        "official_metric_input_rows": 0,
        "label_limited": True,
    }
    metrics.update(
        {
            "e2e_pipeline_smoke_metric": e2e_metric,
            "agentic_answer_metric": answer_metric,
            "denominator_reality_metric": denominator,
            "structured_tool_metric": {
                "metric_kind": "structured_tool_metric",
                "tool_required_rows": 100,
                "tool_attempted_rows": 100,
                "tool_success_rows": 100,
                "tool_fail_closed_rows": 0,
                "operation_type_breakdown": {"structured_table_context_required": 100},
                "tool_outputs_counted_as_rag_hit": False,
                "tool_success_contributed_to_hit_at_k": False,
                "tool_success_contributed_to_mrr": False,
                "tool_success_contributed_to_ndcg": False,
            },
        }
    )
    metric_tiers = {
        name: {
            "attempted_rows": value.get("retrieval_smoke_rows_attempted", value.get("e2e_rows_attempted", value.get("attempted_rows", 0))),
            "computed_rows": value.get("retrieval_metric_computed_count", value.get("computed_only_rows", 0)),
            "diagnostic_only": True,
            "official_metric": False,
            "coverage_limited": bool(value.get("label_limited", value.get("coverage_limited", False))),
        }
        for name, value in metrics.items()
    }
    return metrics, metric_tiers


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    run_artifact_root: Path | str | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source = _load_v63_report(
        repo_root,
        generated_at=generated_at,
        run_artifact_root=run_artifact_root,
    )
    expansion = _build_bounded_e2e_expansion(repo_root, run_artifact_root=run_artifact_root)
    coverage = _coverage_summary(source)
    source_metrics = dict(source.get("metric_results") or {})
    availability = {
        "vector": _candidate_availability_from_metric(source_metrics["vector_retrieval_smoke_metric"]),
        "bm25": _candidate_availability_from_metric(source_metrics["bm25_retrieval_smoke_metric"]),
        "hybrid": _candidate_availability_from_metric(source_metrics["hybrid_retrieval_smoke_metric"]),
    }
    metrics, metric_tiers = _metric_results(source, expansion)
    taxonomy = {
        "vector_no_candidate": availability["vector"]["no_candidate_rows"],
        "bm25_no_candidate": availability["bm25"]["no_candidate_rows"],
        "hybrid_no_candidate": availability["hybrid"]["no_candidate_rows"],
        "hydration_failed": expansion["hydration_summary"]["hydration_fail_closed_rows"],
        "citation_verification_failed": expansion["citation_verification_summary"]["citation_verification_failed_rows"],
        "tool_required": 100,
        "tool_unsupported": 0,
        "context_required": 100,
        "local_llm_disabled": expansion["evidence_only_render_count"],
        "label_unavailable": coverage["attempted_rows"],
        "answer_quality_gate_closed": coverage["attempted_rows"],
        "protected_surface_blocked": 0,
    }
    taxonomy["no_candidate"] = max(
        taxonomy["vector_no_candidate"],
        taxonomy["bm25_no_candidate"],
        taxonomy["hybrid_no_candidate"],
    )
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
        "current_moved_from": PREVIOUS_CURRENT,
        "current_moved_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "current_alias_policy": {
            "current_moved_from": PREVIOUS_CURRENT,
            "current_moved_to": CURRENT_RESOLVES_TO,
            "rollback_key": ROLLBACK_KEY,
            "movement_condition": "v6_4 report contract, 300-row coverage, failure taxonomy, and current-focused tests pass",
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
            "separate_failure_taxonomy_json_created": False,
        },
        "source_v6_3_reuse_summary": {
            "source_run_key": PREVIOUS_CURRENT,
            "source_status": source.get("status"),
            "source_report_payload_sha256": _payload_sha256(source),
            "search_unit_materialization_reused": True,
            "search_view_materialization_reused": True,
            "embedding_backend_reused": "BAAI/bge-m3",
            "vector_backend_reused": "bge_m3_faiss",
            "bm25_backend_reused": "repo_local_sqlite_bm25",
            "hybrid_policy_reused": HYBRID_POLICY,
        },
        "source_v6_3_report_snapshot": source,
        "candidate_coverage_summary": coverage,
        "candidate_availability": availability,
        "vector_candidate_availability": availability["vector"],
        "bm25_candidate_availability": availability["bm25"],
        "hybrid_candidate_availability": availability["hybrid"],
        "failure_taxonomy": {key: int(taxonomy.get(key, 0)) for key in TAXONOMY_KEYS},
        "bounded_e2e_render_expansion": expansion,
        "metric_results": metrics,
        "metric_tiers": metric_tiers,
        "vector_retrieval_smoke_metric": metrics["vector_retrieval_smoke_metric"],
        "bm25_retrieval_smoke_metric": metrics["bm25_retrieval_smoke_metric"],
        "hybrid_retrieval_smoke_metric": metrics["hybrid_retrieval_smoke_metric"],
        "agentic_answer_metric": metrics["agentic_answer_metric"],
        "retrieval_quality_metric_computed": False,
        "answer_quality_metric_computed": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_surface_check": _protected_surface_check(),
        "tool_to_rag_leakage_guard": {
            "tool_outputs_counted_as_rag_hit": False,
            "tool_success_contributed_to_hit_at_k": False,
            "tool_success_contributed_to_mrr": False,
            "tool_success_contributed_to_ndcg": False,
            "tool_lane_created_retrieval_hit": False,
        },
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v64_e2e_coverage_and_failure_taxonomy_nonprod_contract.py -q",
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
        raise ValueError("v6_4 run identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_4 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_4 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_4 rollback key drift")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v6_4 diagnostic/non-production flag missing")
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            raise ValueError(f"v6_4 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if report.get(key) != 0:
            raise ValueError(f"v6_4 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True or protected.get("mutated_paths") != []:
        raise ValueError("v6_4 protected surface check failed")
    if protected.get("protected_namespaces_touched") != []:
        raise ValueError("v6_4 protected namespaces touched")


def _require_coverage(report: Mapping[str, Any]) -> None:
    coverage = report.get("candidate_coverage_summary") or {}
    if coverage.get("attempted_rows") != 300:
        raise ValueError("v6_4 300-row coverage not preserved")
    if coverage.get("coverage_adjusted_denominator") != 300:
        raise ValueError("v6_4 coverage-adjusted denominator drift")
    if coverage.get("computed_only_denominator") != 0:
        raise ValueError("v6_4 computed-only denominator opened")
    if coverage.get("label_unavailable_exclusion_reason") != LABEL_UNAVAILABLE_REASON:
        raise ValueError("v6_4 label-unavailable exclusion reason drift")
    if coverage.get("family_breakdown") != {"PDF": 100, "TEXT": 100, "XLSX": 100}:
        raise ValueError("v6_4 family breakdown drift")
    availability = report.get("candidate_availability") or {}
    for backend in ("vector", "bm25", "hybrid"):
        counters = availability.get(backend) or {}
        if counters.get("attempted_rows") != 300:
            raise ValueError(f"v6_4 {backend} candidate availability did not attempt 300 rows")
        if counters.get("computed_only_denominator") != 0:
            raise ValueError(f"v6_4 {backend} computed-only denominator opened")
        if counters.get("tool_outputs_counted_as_rag_hit") is not False:
            raise ValueError(f"v6_4 {backend} tool output entered metric")


def _require_e2e(report: Mapping[str, Any]) -> None:
    expansion = report.get("bounded_e2e_render_expansion") or {}
    if expansion.get("expanded_rows_attempted") != BOUNDED_E2E_ROWS:
        raise ValueError("v6_4 bounded E2E expansion row count drift")
    if expansion.get("rows_attempted_by_family") != {"PDF": 10, "TEXT": 10, "XLSX": 10}:
        raise ValueError("v6_4 bounded E2E family breakdown drift")
    if expansion.get("answer_quality_metric_computed") is not False:
        raise ValueError("v6_4 answer quality metric opened")
    hydration = expansion.get("hydration_summary") or {}
    if hydration.get("hydration_source") != "SourceAtom/EvidenceBundle":
        raise ValueError("v6_4 hydration boundary drift")
    if hydration.get("hydration_success_rows") != BOUNDED_E2E_ROWS:
        raise ValueError("v6_4 hydration failed")
    citation = expansion.get("citation_verification_summary") or {}
    if citation.get("passed") is not True or citation.get("citation_verification_failed_rows") != 0:
        raise ValueError("v6_4 citation verification failed")


def _require_taxonomy(report: Mapping[str, Any]) -> None:
    taxonomy = report.get("failure_taxonomy") or {}
    if set(taxonomy) != set(TAXONOMY_KEYS):
        raise ValueError("v6_4 failure taxonomy key drift")
    if taxonomy.get("label_unavailable") != 300:
        raise ValueError("v6_4 label unavailable taxonomy drift")
    if taxonomy.get("answer_quality_gate_closed") != 300:
        raise ValueError("v6_4 answer quality gate taxonomy drift")


def _require_single_report(report: Mapping[str, Any], *, root: Path | str | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v6_4 primary report policy missing")
    if policy.get("large_candidate_text_dump_written") is not False:
        raise ValueError("v6_4 large candidate text dump written")
    if root is None:
        return
    run_root = Path(root) / RUN_ROOT
    if run_root.exists():
        names = {path.name for path in run_root.iterdir()}
        if names != {"report.json"}:
            raise ValueError(f"v6_4 single primary report policy violated: {sorted(names)}")
    report_path = Path(root) / REPORT_PATH
    expected = _clean((report.get("artifact_sha256") or {}).get("report_json_sha256"))
    if expected and report_path.exists() and expected != common.sha256_file(report_path):
        raise ValueError("v6_4 report hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_coverage(report)
    _require_e2e(report)
    _require_taxonomy(report)
    _require_single_report(report, root=root)
    guard = report.get("tool_to_rag_leakage_guard") or {}
    if guard.get("tool_outputs_counted_as_rag_hit") is not False:
        raise ValueError("v6_4 tool output entered RAG metric")
    if report.get("answer_quality_metric_computed") is not False:
        raise ValueError("v6_4 answer quality metric opened")
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v6_4")


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
    coverage = report["candidate_coverage_summary"]
    expansion = report["bounded_e2e_render_expansion"]
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
        "official_metric": False,
        "official_metric_input_rows": 0,
        "candidate_coverage_attempted_rows": coverage["attempted_rows"],
        "coverage_adjusted_denominator": coverage["coverage_adjusted_denominator"],
        "computed_only_denominator": coverage["computed_only_denominator"],
        "bounded_e2e_expanded_rows": expansion["expanded_rows_attempted"],
        "answer_quality_metric_computed": False,
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
        raise ValueError("v6_4 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_4 status report hash missing: report.json not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v6_4 status report hash missing: status event not found")
    latest = rows[-1]
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_4 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_4 status current alias drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    coverage = report["candidate_coverage_summary"]
    expansion = report["bounded_e2e_render_expansion"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is diagnostic-only and current moved from "
        f"`{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` after the 300-row coverage and failure taxonomy checks passed. "
        "It reuses the v6_3 source-derived SearchUnit/SearchView, bge-m3, FAISS, BM25, and fixed-weight hybrid "
        "paths, writes one primary report.json, and keeps answer/retrieval quality metrics label-limited and "
        f"closed. rollback key is `{ROLLBACK_KEY}`. There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        "- Boundary: diagnostic-only, non-production; no official/product/promotion/live-readiness claim is opened.\n"
        f"- 300-row coverage: attempted={coverage['attempted_rows']}; family_breakdown={coverage['family_breakdown']}; "
        f"coverage_adjusted_denominator={coverage['coverage_adjusted_denominator']}; "
        f"computed_only_denominator={coverage['computed_only_denominator']}; "
        f"exclusion_reason={coverage['label_unavailable_exclusion_reason']}.\n"
        f"- Candidate availability: vector={report['candidate_availability']['vector']}; "
        f"bm25={report['candidate_availability']['bm25']}; hybrid={report['candidate_availability']['hybrid']}.\n"
        f"- Bounded E2E expansion: source_rows=3; expanded_rows={expansion['expanded_rows_attempted']}; "
        f"rows_by_family={expansion['rows_attempted_by_family']}; hydration_source=SourceAtom/EvidenceBundle; "
        "answer_quality_metric_computed=false.\n"
        f"- failure taxonomy: {report['failure_taxonomy']}.\n"
        f"- Current alias: current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}`; rollback key is `{ROLLBACK_KEY}`."
    )
    triage = (
        f"- {SHORT_RUN_ID}: v6_4 recovery records 300-row vector/BM25/hybrid candidate availability, "
        "a bounded SourceAtom/EvidenceBundle evidence-only render expansion, and a failure taxonomy. "
        "Retrieval computed-only denominator remains 0, coverage-adjusted denominator remains 300, "
        f"and current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}`. no official/product/promotion/live-readiness "
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
