from __future__ import annotations

from ai.eval.actual_rag_core_base import *
from ai.eval.actual_rag_core_xlsx import *
from ai.eval.actual_rag_core_quality import *

def write_weaviate_route_ab_artifacts(
    *,
    output_dir: Path,
    suite_run_id: str,
    generated_at: str,
    dataset_path: Path,
    baseline_summary: Mapping[str, Any],
    baseline_rows: Sequence[Mapping[str, Any]],
    items: Sequence[EvalItem],
    modes: Sequence[str],
    top_k: int,
    judge_adapter: Any,
    provisional_require_citations: bool,
    evidence_gate_mode: str,
    lane_factory: Callable[[str], Any],
) -> dict[str, str]:
    lane_specs = [
        ("lane_a_full_index", "full_index"),
        *[
            (
                "lane_b_text_only" if mode == "text_only" else "lane_c_mixed_pool" if mode == "mixed_pool" else "lane_d_route_selected",
                mode,
            )
            for mode in modes
        ],
    ]
    lanes: dict[str, dict[str, Any]] = {}
    lane_public_rows: dict[str, list[dict[str, Any]]] = {}
    item_rows: list[dict[str, Any]] = []
    baseline_filter_policy = (
        baseline_summary.get("weaviate_filter_policy")
        if isinstance(baseline_summary.get("weaviate_filter_policy"), Mapping)
        else {}
    )
    if _clean(baseline_filter_policy.get("route_mode")) == "full_index":
        lane_a_summary = dict(baseline_summary)
        public_baseline_rows = [_public_report_row(row) for row in baseline_rows]
    else:
        lane_a_summary, public_baseline_rows = _run_weaviate_route_ab_lane(
            lane_run_id=f"{suite_run_id}_full_index",
            route_mode="full_index",
            items=items,
            top_k=top_k,
            judge_adapter=judge_adapter,
            provisional_require_citations=provisional_require_citations,
            evidence_gate_mode=evidence_gate_mode,
            lane_factory=lane_factory,
        )
    lane_public_rows["lane_a_full_index"] = public_baseline_rows
    lanes["lane_a_full_index"] = _weaviate_ab_lane_summary(
        lane_id="lane_a_full_index",
        route_mode="full_index",
        dataset_source=dataset_path.as_posix(),
        summary=lane_a_summary,
        rows=public_baseline_rows,
    )
    item_rows.extend(_ab_item_rows(lane_id="lane_a_full_index", rows=public_baseline_rows))
    for lane_id, route_mode in lane_specs[1:]:
        lane_summary, lane_rows = _run_weaviate_route_ab_lane(
            lane_run_id=f"{suite_run_id}_{route_mode}",
            route_mode=route_mode,
            items=items,
            top_k=top_k,
            judge_adapter=judge_adapter,
            provisional_require_citations=provisional_require_citations,
            evidence_gate_mode=evidence_gate_mode,
            lane_factory=lane_factory,
        )
        lanes[lane_id] = _weaviate_ab_lane_summary(
            lane_id=lane_id,
            route_mode=route_mode,
            dataset_source=dataset_path.as_posix(),
            summary=lane_summary,
            rows=lane_rows,
        )
        lane_public_rows[lane_id] = list(lane_rows)
        item_rows.extend(_ab_item_rows(lane_id=lane_id, rows=lane_rows))

    mixed_route_path = ROOT / "reports/rag_eval/rag-ingestion/runs/v5_5/official_metric_input.jsonl"
    mixed_route_available = mixed_route_path.exists()
    mixed_route_unavailable_reason = "" if mixed_route_available else "mixed_route_packet_missing"
    mixed_route_diagnostic: dict[str, Any] = {
        "available": mixed_route_available,
        "executed": False,
        "dataset_path": mixed_route_path.as_posix(),
        "item_count": 0,
        "lanes": {},
        "unavailable_reason": mixed_route_unavailable_reason,
        "candidate_generation_uses_gold_fields": False,
        "candidate_generation_uses_expected_fields": False,
        "candidate_generation_uses_qrels": False,
        "candidate_generation_uses_labels": False,
        "candidate_generation_uses_query_ids": False,
    }
    if mixed_route_available and _should_run_mixed_route_diagnostic(dataset_path):
        try:
            mixed_items = _load_weaviate_mixed_route_diagnostic_items(mixed_route_path)
            mixed_route_diagnostic["item_count"] = len(mixed_items)
            for route_mode, lane_id in (
                ("mixed_pool", "lane_c_mixed_pool"),
                ("route_selected", "lane_d_route_selected"),
            ):
                if route_mode not in modes:
                    continue
                mixed_summary, mixed_rows = _run_weaviate_route_ab_lane(
                    lane_run_id=f"{suite_run_id}_mixed_route_diagnostic_{route_mode}",
                    route_mode=route_mode,
                    items=mixed_items,
                    top_k=top_k,
                    judge_adapter=judge_adapter,
                    provisional_require_citations=provisional_require_citations,
                    evidence_gate_mode=evidence_gate_mode,
                    lane_factory=lane_factory,
                )
                mixed_route_diagnostic["lanes"][lane_id] = _weaviate_ab_lane_summary(
                    lane_id=lane_id,
                    route_mode=route_mode,
                    dataset_source=mixed_route_path.as_posix(),
                    summary=mixed_summary,
                    rows=mixed_rows,
                )
                item_rows.extend(
                    _ab_item_rows(
                        lane_id=lane_id,
                        rows=mixed_rows,
                        dataset_role="mixed_route_diagnostic",
                    )
                )
            mixed_route_diagnostic["executed"] = bool(mixed_route_diagnostic["lanes"])
            mixed_route_diagnostic["unavailable_reason"] = (
                "" if mixed_route_diagnostic["executed"] else "requested_modes_exclude_mixed_or_routed"
            )
        except Exception as exc:
            mixed_route_diagnostic["executed"] = False
            mixed_route_diagnostic["unavailable_reason"] = (
                f"mixed_route_diagnostic_failed:{type(exc).__name__}:{exc}"
            )

    guardrail_violations: list[str] = []
    for lane_id, lane in lanes.items():
        lane_guard = lane.get("guardrail_status") if isinstance(lane.get("guardrail_status"), Mapping) else {}
        for violation in lane_guard.get("violations") or []:
            guardrail_violations.append(f"{lane_id}:{violation}")

    lane_b = lanes.get("lane_b_text_only", {})
    lane_c = lanes.get("lane_c_mixed_pool", {})
    lane_d = lanes.get("lane_d_route_selected", {})
    text_route_degradation_count = (
        _text_route_degradation_count(
            [
                lane_public_rows.get("lane_a_full_index", []),
                lane_public_rows.get("lane_b_text_only", []),
            ],
            lane_public_rows.get("lane_d_route_selected", []),
        )
        if lane_d
        else 0
    )
    if lane_d:
        lane_d["text_route_degradation_count"] = text_route_degradation_count
    baseline_p95 = float(lanes["lane_a_full_index"].get("weaviate_query_latency_ms_p95") or 0.0)
    route_p95 = float(lane_d.get("weaviate_query_latency_ms_p95") or 0.0) if lane_d else 0.0
    route_duplicate_ok = float(lane_d.get("duplicate_result_rate") or 0.0) <= float(lane_c.get("duplicate_result_rate") or 0.0) + 0.2 if lane_d and lane_c else False
    route_pollution_ok = int(lane_d.get("wrong_source_family_count") or 0) <= int(lane_c.get("wrong_source_family_count") or 0) if lane_d and lane_c else False
    latency_ok = not baseline_p95 or route_p95 <= max(1.0, baseline_p95 * 2)
    route_metadata_policy_ok = (
        bool(lane_d)
        and _clean(lane_d.get("schema_version_source_atom") or lane_d.get("weaviate_schema_version")) == "weaviate_source_atom_v2"
        and not bool(lane_d.get("schema_index_v2_rebuild_required_for_metadata_only_policy"))
        and int(lane_d.get("metadata_only_object_count") or 0) > 0
        and int(lane_d.get("vectorized_object_count") or 0) < int(lane_d.get("index_object_count") or 0)
        and bool(lane_d.get("index_time_metadata_only_supported"))
        and not bool(lane_d.get("current_index_vectorizes_all_source_atoms"))
    )
    route_selected_filter_ok = (
        bool(lane_d)
        and bool(lane_d.get("route_filter_sent"))
        and bool(lane_d.get("source_family_filter_sent"))
        and bool(lane_d.get("granularity_filter_sent"))
        and bool(lane_d.get("retrieval_route_filter_sent"))
    )
    mixed_lanes = mixed_route_diagnostic.get("lanes") if isinstance(mixed_route_diagnostic.get("lanes"), Mapping) else {}
    mixed_lane_c = mixed_lanes.get("lane_c_mixed_pool") if isinstance(mixed_lanes.get("lane_c_mixed_pool"), Mapping) else {}
    mixed_lane_d = mixed_lanes.get("lane_d_route_selected") if isinstance(mixed_lanes.get("lane_d_route_selected"), Mapping) else {}
    mixed_route_executed = bool(mixed_route_diagnostic.get("executed") and mixed_lane_c and mixed_lane_d)
    mixed_c_weak = mixed_lane_c.get("weak_evidence_match_recall@10") if mixed_route_executed else None
    mixed_d_weak = mixed_lane_d.get("weak_evidence_match_recall@10") if mixed_route_executed else None
    mixed_d_denominator = int(mixed_lane_d.get("weak_evidence_match_recall@10_denominator") or 0) if mixed_route_executed else 0
    mixed_weak_allowed_drop = round(1.0 / float(mixed_d_denominator), 6) if mixed_d_denominator else 0.0
    mixed_weak_delta = (
        round(float(mixed_d_weak) - float(mixed_c_weak), 6)
        if isinstance(mixed_c_weak, (int, float)) and isinstance(mixed_d_weak, (int, float))
        else None
    )
    mixed_same_doc_delta = (
        round(float(mixed_lane_d.get("same_doc_duplicate_rate") or 0.0) - float(mixed_lane_c.get("same_doc_duplicate_rate") or 0.0), 6)
        if mixed_route_executed
        else None
    )
    mixed_duplicate_delta = (
        round(float(mixed_lane_d.get("duplicate_result_rate") or 0.0) - float(mixed_lane_c.get("duplicate_result_rate") or 0.0), 6)
        if mixed_route_executed
        else None
    )
    mixed_diagnostic_weak_ok = (
        not mixed_route_executed
        or mixed_weak_delta is None
        or mixed_weak_delta >= -mixed_weak_allowed_drop
    )
    mixed_diagnostic_duplicate_ok = (
        not mixed_route_executed
        or (
            (mixed_duplicate_delta is None or mixed_duplicate_delta <= 0.1)
            and (mixed_same_doc_delta is None or mixed_same_doc_delta <= 0.1)
        )
    )
    mixed_diagnostic_quality_ok = bool(mixed_diagnostic_weak_ok and mixed_diagnostic_duplicate_ok)
    text_degradation_ok = (
        text_route_degradation_count == 0
        and _metric_score_not_lower(
            lane_d.get("weak_evidence_match_recall@10") if lane_d else None,
            [
                lane_a.get("weak_evidence_match_recall@10")
                for lane_a in (lanes.get("lane_a_full_index", {}), lane_b)
            ],
        )
    )
    promotion_blockers: list[str] = []
    if lane_d and not route_metadata_policy_ok:
        promotion_blockers.append("route_selected_metadata_only_policy_not_proven")
    if lane_d and not route_selected_filter_ok:
        promotion_blockers.append("route_selected_weaviate_route_filters_not_all_sent")
    if lane_d and not text_degradation_ok:
        promotion_blockers.append("text_route_degradation")
    if lane_d and not route_pollution_ok:
        promotion_blockers.append("wrong_source_family_not_reduced_vs_mixed_pool")
    if lane_d and not route_duplicate_ok:
        promotion_blockers.append("primary_text_duplicate_pressure_increased")
    if lane_d and not latency_ok:
        promotion_blockers.append("route_selected_latency_exceeds_gate")
    if mixed_route_executed and not mixed_diagnostic_weak_ok:
        promotion_blockers.append("mixed_route_weak_evidence_match_recall_regression")
    if mixed_route_executed and not mixed_diagnostic_duplicate_ok:
        promotion_blockers.append("mixed_route_duplicate_pressure_regression")
    if mixed_route_available and _should_run_mixed_route_diagnostic(dataset_path) and any(
        mode in {"mixed_pool", "route_selected"} for mode in modes
    ):
        unavailable_reason = _clean(mixed_route_diagnostic.get("unavailable_reason"))
        if not mixed_route_diagnostic.get("executed") or unavailable_reason.startswith("mixed_route_diagnostic_failed"):
            guardrail_violations.append(
                f"mixed_route_dataset_diagnostic:{unavailable_reason or 'not_executed'}"
            )
    if guardrail_violations:
        recommendation = "invalid_due_to_guardrail_violation"
    elif lane_d and lane_d.get("weaviate_filter_policy", {}).get("schema_index_v2_rebuild_required"):
        recommendation = "rebuild_schema_v2_required"
    elif lane_d and not route_metadata_policy_ok:
        recommendation = "rebuild_schema_v2_required"
    elif lane_d and not route_selected_filter_ok:
        recommendation = "rebuild_schema_v2_required"
    elif lane_d and not mixed_diagnostic_quality_ok:
        recommendation = "keep_current_weaviate_full_index"
    elif lane_d and route_metadata_policy_ok and route_selected_filter_ok and route_pollution_ok and route_duplicate_ok and latency_ok and text_degradation_ok and mixed_diagnostic_quality_ok:
        recommendation = "promote_route_selected_nonprod_default"
    elif lane_d and not latency_ok:
        recommendation = "defer_due_to_latency"
    elif lane_d and not route_pollution_ok:
        recommendation = "defer_due_to_pollution"
    else:
        recommendation = "keep_current_weaviate_full_index"

    report = {
        "schema_version": "actual_rag_eval.weaviate_route_selected_hybrid_evidence_store_ab.v1",
        "run_id": suite_run_id,
        "generated_at": generated_at,
        "non_production": True,
        "candidate_generation_input_policy": WEAVIATE_CANDIDATE_INPUT_POLICY,
        "datasets": {
            "text_regression_dataset_path": dataset_path.as_posix(),
            "mixed_route_dataset_path": mixed_route_path.as_posix(),
            "mixed_route_dataset_available": mixed_route_available,
            "mixed_route_dataset_unavailable_reason": mixed_route_unavailable_reason,
            "gold_mutation": False,
        },
        "vectorization_policy": {
            "vectorized_by_default": ["paragraph", "heading_context_block", "table_summary", "table_row", "caption"],
            "metadata_only_by_default": ["cell", "page_marker", "empty_fragment", "repeated_header_footer", "metadata_only", "local_path_source_trace_fields"],
            "title_query_property_policy": "source_owned_metadata_searchable_not_evidence_truth",
            "route_selected_metadata_only_policy_proven": route_metadata_policy_ok if lane_d else None,
            "route_selected_schema_version": lane_d.get("weaviate_schema_version") if lane_d else "",
            "route_selected_metadata_only_object_count": lane_d.get("metadata_only_object_count") if lane_d else None,
            "route_selected_vectorized_object_count": lane_d.get("vectorized_object_count") if lane_d else None,
            "route_selected_index_object_count": lane_d.get("index_object_count") if lane_d else None,
            "route_selected_all_route_filters_sent": route_selected_filter_ok if lane_d else None,
        },
        "lanes": lanes,
        "mixed_route_dataset_diagnostic": mixed_route_diagnostic,
        "text_degradation_result": {
            "lane_a_weak_evidence_match_recall@10": lanes["lane_a_full_index"].get("weak_evidence_match_recall@10"),
            "lane_b_weak_evidence_match_recall@10": lane_b.get("weak_evidence_match_recall@10"),
            "lane_d_weak_evidence_match_recall@10": lane_d.get("weak_evidence_match_recall@10"),
            "text_route_degradation_count": text_route_degradation_count,
            "text_route_degradation_ok": text_degradation_ok if lane_d else None,
        },
        "mixed_pool_pollution_result": {
            "lane_c_mixed_pool_pollution_count": lane_c.get("mixed_pool_pollution_count"),
            "lane_d_wrong_source_family_count": lane_d.get("wrong_source_family_count") if lane_d else None,
            "mixed_route_dataset_executed": mixed_route_diagnostic.get("executed"),
            "mixed_route_lane_c_mixed_pool_pollution_count": (
                (mixed_route_diagnostic.get("lanes") or {}).get("lane_c_mixed_pool", {}).get("mixed_pool_pollution_count")
                if isinstance(mixed_route_diagnostic.get("lanes"), Mapping)
                else None
            ),
            "mixed_route_lane_d_wrong_source_family_count": (
                (mixed_route_diagnostic.get("lanes") or {}).get("lane_d_route_selected", {}).get("wrong_source_family_count")
                if isinstance(mixed_route_diagnostic.get("lanes"), Mapping)
                else None
            ),
            "mixed_route_weak_evidence_match_recall_delta": mixed_weak_delta,
            "mixed_route_weak_evidence_allowed_drop": mixed_weak_allowed_drop if mixed_route_executed else None,
            "mixed_route_same_doc_duplicate_rate_delta": mixed_same_doc_delta,
            "mixed_route_duplicate_result_rate_delta": mixed_duplicate_delta,
            "mixed_route_diagnostic_weak_ok": mixed_diagnostic_weak_ok if mixed_route_executed else None,
            "mixed_route_diagnostic_duplicate_ok": mixed_diagnostic_duplicate_ok if mixed_route_executed else None,
            "mixed_route_diagnostic_quality_ok": mixed_diagnostic_quality_ok if mixed_route_executed else None,
        },
        "route_selected_recovery_result": {
            "wrong_source_family_count_decreased_vs_mixed": route_pollution_ok,
            "duplicate_pressure_materially_increased": not route_duplicate_ok if lane_d and lane_c else None,
            "metadata_only_policy_proven": route_metadata_policy_ok if lane_d else None,
            "all_route_filters_sent": route_selected_filter_ok if lane_d else None,
            "mixed_route_diagnostic_quality_ok": mixed_diagnostic_quality_ok if mixed_route_executed else None,
        },
        "latency_comparison": {
            "lane_a_p95": baseline_p95,
            "lane_d_p95": route_p95 if lane_d else None,
            "route_selected_within_2x_lane_a": latency_ok if lane_d else None,
        },
        "guardrail_status": {
            "valid": not guardrail_violations,
            "violations": guardrail_violations,
            "weaviate_invoked": all(
                (lane.get("external_vector_db") or {}).get("invoked") is True for lane in lanes.values()
            ),
            "gold_mutation": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
        },
        "recommendation": recommendation,
        "promotion_blockers": promotion_blockers,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / WEAVIATE_ROUTE_AB_REPORT_FILENAME
    items_path = output_dir / WEAVIATE_ROUTE_AB_ITEMS_FILENAME
    write_json(report_path, report)
    write_jsonl(items_path, item_rows)
    return {
        "route_selected_hybrid_evidence_store_ab_report_json": report_path.as_posix(),
        "route_selected_hybrid_evidence_store_ab_items_jsonl": items_path.as_posix(),
    }


def refresh_weaviate_route_ab_quality_gate_counts(summary: MutableMapping[str, Any]) -> None:
    artifact_paths = summary.get("artifact_paths") if isinstance(summary.get("artifact_paths"), Mapping) else {}
    report_path_text = _clean(artifact_paths.get("route_selected_hybrid_evidence_store_ab_report_json"))
    if not report_path_text:
        return
    gate = summary.get("legacy_real_rag_quality_gate") if isinstance(summary.get("legacy_real_rag_quality_gate"), Mapping) else {}
    counts = gate.get("evidence_package_status_counts") if isinstance(gate.get("evidence_package_status_counts"), Mapping) else {}
    if not counts:
        return
    report_path = Path(report_path_text)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return
    if not isinstance(report, MutableMapping):
        return
    lanes = report.get("lanes") if isinstance(report.get("lanes"), MutableMapping) else {}
    lane_a = lanes.get("lane_a_full_index") if isinstance(lanes.get("lane_a_full_index"), MutableMapping) else {}
    lane_a["evidence_package_sufficient_count"] = counts.get("sufficient")
    lane_a["evidence_package_insufficient_count"] = counts.get("insufficient")
    report["quality_gate"] = {
        "available": True,
        "applied_to_primary_lane": "lane_a_full_index",
        "evidence_package_status_counts": dict(counts),
        "legacy_baseline_replayed_not_executed": bool(gate.get("legacy_baseline_replayed_not_executed")),
    }
    write_json(report_path, report)


def run_eval_from_paths(
    *,
    dataset_path: Path | str,
    output_dir: Path | str,
    context_jsonl_path: Path | str | None = None,
    index: str = "current",
    top_k: int = 10,
    run_id: str | None = None,
    command: str = "",
    judge_mode: str = "heuristic",
    judge_backend: str = "",
    judge_base_url: str = "",
    judge_model: str = "",
    judge_threshold: float = 0.5,
    judge_timeout_seconds: int = 60,
    judge_max_tokens: int = 360,
    skip_judge_endpoint_check: bool = False,
    provisional_require_citations: bool = False,
    generated_at: str | None = None,
    comparison_summary: Mapping[str, Any] | None = None,
    comparison_target: str = "",
    portfolio_comparison_reports: Sequence[str] | None = None,
    write_portfolio_experiment_summary: bool = False,
    report_root: Path | str = REPORT_ROOT,
    registry_path: Path | str | None = None,
    status_jsonl_path: Path | str = STATUS_JSONL_PATH,
    append_registry: bool = False,
    write_latest: bool = False,
    resolve_expected_evidence: bool = True,
    evidence_resolution_scope: str = "full-corpus",
    max_evidence_candidates: int = 5,
    min_evidence_resolution_score: float = 0.35,
    count_medium_evidence_resolution: bool = False,
    write_evidence_mapping_packet: bool = False,
    write_human_review_packet: bool = False,
    reviewed_evidence_mapping_csv: Path | str | None = None,
    output_mode: str = "single",
    retrieval_surface: str = "auto",
    retrieval_backend: str = "auto",
    legacy_surface_comparison: bool = False,
    retrieval_adapter: Any | None = None,
    source_native_units: Sequence[Mapping[str, Any]] | None = None,
    searchunit_units: Sequence[Mapping[str, Any]] | None = None,
    source_native_embedding_provider: Any | None = None,
    source_native_index_dir: Path | str | None = None,
    source_native_index_build: Mapping[str, Any] | None = None,
    quality_gate_baseline_path: Path | str | None = None,
    evidence_gate_mode: str = "off",
    answer_composer: str = "extractive-v1",
    selected_evidence_citation_format: str = "compact",
    selected_evidence_composer_retry_mode: str = "off",
    local_llm_composer_backend: str = "",
    local_llm_composer_base_url: str = "",
    local_llm_composer_model: str = "",
    local_llm_composer_timeout_seconds: int = 60,
    local_llm_composer_max_tokens: int = 360,
    skip_local_llm_composer_endpoint_check: bool = False,
    weaviate_route_ab_mode: str | Sequence[str] | None = None,
    weaviate_route_ab_lane_factory: Callable[[str], Any] | None = None,
    corpus_coverage_audit_query_ids: str | Sequence[str] | None = None,
    corpus_coverage_audit_target_anchors: Sequence[str] | None = None,
    corpus_coverage_audit_lane_factory: Callable[[str], Any] | None = None,
    corpus_coverage_audit_source_registry_path: Path | str | None = SOURCE_NATIVE_SOURCE_REGISTRY_PATH,
    corpus_coverage_audit_index_checkpoint_path: Path | str | None = None,
    corpus_coverage_audit_index_manifest_path: Path | str | None = None,
    agentic_planner_mode: str = "off",
    xlsx_locator_tool_execute_once: bool = False,
    llm_query_anchor_classifier: bool = False,
) -> RagEvalBundle:
    dataset = Path(dataset_path)
    output = Path(output_dir)
    normalized_output_mode = _clean(output_mode).lower() or "single"
    if normalized_output_mode not in {"single", "legacy", "both", "runstore"}:
        raise DatasetSchemaError(f"unsupported output mode: {output_mode}")
    normalized_retrieval_backend = _clean(retrieval_backend).lower() or "auto"
    if normalized_retrieval_backend not in set(RAG_RETRIEVAL_BACKEND_CHOICES):
        raise DatasetSchemaError(f"unsupported retrieval backend: {retrieval_backend}")
    weaviate_backend_requested = normalized_retrieval_backend in WEAVIATE_BACKEND_ALIASES
    normalized_retrieval_surface = _clean(retrieval_surface).replace("_", "-").lower() or "auto"
    if normalized_retrieval_surface not in {"auto", "searchunit-searchview", "source-native", "source-atom", "evidence-bundle"}:
        raise DatasetSchemaError(f"unsupported retrieval surface: {retrieval_surface}")
    normalized_evidence_gate_mode = _clean(evidence_gate_mode).lower() or "off"
    if normalized_evidence_gate_mode not in {"off", "diagnostic", "enforce"}:
        raise DatasetSchemaError(f"unsupported evidence gate mode: {evidence_gate_mode}")
    normalized_agentic_planner_mode = _clean(agentic_planner_mode).lower() or "off"
    if normalized_agentic_planner_mode not in AGENTIC_PLANNER_MODE_CHOICES:
        raise DatasetSchemaError(f"unsupported agentic planner mode: {agentic_planner_mode}")
    normalized_answer_composer = _clean(answer_composer).replace("_", "-").lower() or "extractive-v1"
    if normalized_answer_composer not in ANSWER_COMPOSER_PROVIDERS:
        raise DatasetSchemaError(f"unsupported answer composer: {answer_composer}")
    normalized_selected_evidence_composer_retry_mode = _normalize_selected_evidence_composer_retry_mode(
        selected_evidence_composer_retry_mode
    )
    if normalized_agentic_planner_mode in {"dry-run", "execute-once"}:
        if normalized_evidence_gate_mode == "off":
            raise DatasetSchemaError("agentic planner requires evidence_gate_mode diagnostic or enforce")
        if normalized_answer_composer not in {
            SELECTED_EVIDENCE_COMPOSER_PROVIDER,
            SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROVIDER,
        }:
            raise DatasetSchemaError("agentic planner requires a selected-evidence answer composer")
    if normalized_agentic_planner_mode == "execute-once" and normalized_selected_evidence_composer_retry_mode != "off":
        raise DatasetSchemaError("agentic planner execute-once does not allow selected-evidence LLM retry")
    if xlsx_locator_tool_execute_once:
        if normalized_agentic_planner_mode != "off":
            raise DatasetSchemaError("xlsx locator tool execute-once must not be combined with agentic planner modes")
        if normalized_evidence_gate_mode == "off":
            raise DatasetSchemaError("xlsx locator tool execute-once requires evidence_gate_mode diagnostic or enforce")
        if normalized_answer_composer not in {
            SELECTED_EVIDENCE_COMPOSER_PROVIDER,
            SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROVIDER,
        }:
            raise DatasetSchemaError(
                "xlsx locator tool execute-once requires a selected-evidence answer composer"
            )
        if normalized_selected_evidence_composer_retry_mode != "off":
            raise DatasetSchemaError("xlsx locator tool execute-once does not allow selected-evidence LLM retry")
    if normalized_output_mode == "runstore":
        if not xlsx_locator_tool_execute_once:
            raise DatasetSchemaError("output_mode=runstore requires xlsx locator tool execute-once")
        if append_registry or write_latest:
            raise DatasetSchemaError("output_mode=runstore cannot append registry or write latest pointers")
        if write_evidence_mapping_packet or write_human_review_packet:
            raise DatasetSchemaError("output_mode=runstore cannot write review packet sidecars")
        if reviewed_evidence_mapping_csv is not None:
            raise DatasetSchemaError("output_mode=runstore cannot write reviewed mapping patch artifacts")
        if _clean(quality_gate_baseline_path):
            raise DatasetSchemaError("output_mode=runstore cannot write quality gate sidecars")
        if _parse_weaviate_route_ab_modes(weaviate_route_ab_mode):
            raise DatasetSchemaError("output_mode=runstore cannot write Weaviate route A/B sidecars")
        if portfolio_comparison_reports or write_portfolio_experiment_summary:
            raise DatasetSchemaError("output_mode=runstore cannot write portfolio comparison artifacts")
    normalized_selected_evidence_citation_format = _normalize_selected_evidence_citation_format(
        selected_evidence_citation_format
    )
    if normalized_retrieval_surface == "searchunit-searchview" and not legacy_surface_comparison:
        raise DatasetSchemaError(
            "retrieval_surface=searchunit-searchview is legacy/debug only; pass --legacy-surface-comparison"
        )
    if _output_dir_has_artifacts(output):
        raise DatasetSchemaError(f"{output}: already contains actual RAG eval artifacts")
    items = load_eval_dataset(dataset)
    response_quality_input_summary = build_response_quality_input_summary(dataset_path=dataset, items=items)
    denominator_before_reviewed_mapping = _strict_denominator_snapshot(items)
    gpu_preflight = build_gpu_preflight()
    external_vector_db = discover_external_vector_db()
    source_native_loader = (
        SourceNativeCorpusLoader(
            search_view_manifest_path=Path(source_native_index_dir) / "search_view_manifest.jsonl",
            source_atom_registry_path=SOURCE_NATIVE_SOURCE_REGISTRY_PATH,
        )
        if source_native_index_dir is not None
        else None
    )
    if retrieval_adapter is not None:
        adapter = retrieval_adapter
        if hasattr(adapter, "requested_backend"):
            try:
                adapter.requested_backend = normalized_retrieval_backend
            except Exception:
                pass
    elif context_jsonl_path:
        adapter = JsonlContextAdapter(context_jsonl_path, requested_backend=normalized_retrieval_backend)
    elif weaviate_backend_requested:
        adapter = build_default_weaviate_adapter(requested_backend=normalized_retrieval_backend)
    else:
        source_adapter = SourceNativeHybridAdapter(
            ROOT,
            requested_backend=normalized_retrieval_backend,
            loader=source_native_loader,
            units=source_native_units,
            embedding_provider=source_native_embedding_provider,
            gpu_preflight=gpu_preflight,
            external_vector_db=external_vector_db,
        )
        searchunit_backend = (
            normalized_retrieval_backend
            if normalized_retrieval_surface == "searchunit-searchview"
            else "bm25"
        )
        searchunit_adapter = RepoCurrentHybridAdapter(
            ROOT,
            requested_backend=searchunit_backend,
            payloads=searchunit_units,
            gpu_preflight=gpu_preflight,
            external_vector_db=external_vector_db,
        )
        adapter = SurfaceComparingRagAdapter(
            requested_surface=normalized_retrieval_surface,
            requested_backend=normalized_retrieval_backend,
            source_adapter=source_adapter,
            searchunit_adapter=searchunit_adapter,
            legacy_surface_comparison=legacy_surface_comparison,
        )
    adapter_is_weaviate_lane = weaviate_backend_requested or isinstance(adapter, WeaviateSourceAtomAdapter)
    validate_ready = getattr(adapter, "validate_ready_for_run", None)
    if callable(validate_ready):
        try:
            validate_ready()
        except Exception:
            close_adapter = getattr(adapter, "close", None)
            if callable(close_adapter):
                close_adapter()
            raise
    adapter_external_vector_db = getattr(adapter, "external_vector_db_report", None)
    if isinstance(adapter_external_vector_db, Mapping):
        external_vector_db = dict(adapter_external_vector_db)
    generated_at = generated_at or utc_now_iso()
    run_id = run_id or make_actual_rag_run_id(dataset, generated_at=generated_at, report_root=report_root)
    judge_adapter = build_judge_adapter(
        judge_mode=judge_mode,
        judge_backend=judge_backend,
        judge_base_url=judge_base_url,
        judge_model=judge_model,
        judge_threshold=judge_threshold,
        judge_timeout_seconds=judge_timeout_seconds,
        judge_max_tokens=judge_max_tokens,
        skip_judge_endpoint_check=skip_judge_endpoint_check,
    )
    started = time.perf_counter()

    query_evidence_planners_by_item_id: dict[str, Mapping[str, Any]] = {}
    retrieval_items: list[EvalItem] = list(items)
    if llm_query_anchor_classifier:
        retrieval_items = []
        for item in items:
            planner = plan_query_evidence_with_local_llm(
                item.query,
                backend=local_llm_composer_backend,
                base_url=local_llm_composer_base_url,
                model=local_llm_composer_model,
                timeout_seconds=local_llm_composer_timeout_seconds,
                skip_endpoint_check=skip_local_llm_composer_endpoint_check,
            )
            query_evidence_planners_by_item_id[item.id] = planner
            source_row = dict(item.source_row) if isinstance(item.source_row, Mapping) else {}
            source_row["query_evidence_planner"] = planner
            retrieval_items.append(replace(item, source_row=source_row))

    raw_outputs: list[dict[str, Any]] = []
    for item in retrieval_items:
        try:
            raw_outputs.append(adapter.run_item(item, top_k=top_k))
        except Exception as exc:  # keep row-level pipeline failures inspectable
            if adapter_is_weaviate_lane:
                close_adapter = getattr(adapter, "close", None)
                if callable(close_adapter):
                    close_adapter()
                raise
            raw_outputs.append(_pipeline_error_output(item, f"{type(exc).__name__}: {exc}"))
    if llm_query_anchor_classifier:
        raw_outputs = apply_llm_query_anchor_classifier_to_outputs(
            raw_outputs,
            backend=local_llm_composer_backend,
            base_url=local_llm_composer_base_url,
            model=local_llm_composer_model,
            timeout_seconds=local_llm_composer_timeout_seconds,
            skip_endpoint_check=skip_local_llm_composer_endpoint_check,
            precomputed_query_evidence_planners=query_evidence_planners_by_item_id,
        )
    if xlsx_locator_tool_execute_once:
        raw_outputs = preserve_xlsx_locator_source_contexts(raw_outputs)
    composer_applied = normalized_answer_composer in {
        SELECTED_EVIDENCE_COMPOSER_PROVIDER,
        SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROVIDER,
    }
    if composer_applied:
        raw_outputs = apply_selected_evidence_composer_to_outputs(
            raw_outputs,
            citation_format=normalized_selected_evidence_citation_format,
            composer_provider=normalized_answer_composer,
            local_llm_backend=local_llm_composer_backend,
            local_llm_base_url=local_llm_composer_base_url,
            local_llm_model=local_llm_composer_model,
            local_llm_timeout_seconds=local_llm_composer_timeout_seconds,
            local_llm_max_tokens=local_llm_composer_max_tokens,
            skip_local_llm_endpoint_check=skip_local_llm_composer_endpoint_check,
            retry_mode=normalized_selected_evidence_composer_retry_mode,
        )
    raw_outputs, evidence_gate_summary = apply_evidence_gate_to_outputs(
        raw_outputs,
        mode=normalized_evidence_gate_mode,
    )
    xlsx_locator_run_record: XlsxLocatorRunRecord | None = None
    xlsx_locator_before_rows: list[dict[str, Any]] | None = None
    xlsx_locator_after_rows: list[dict[str, Any]] | None = None
    if xlsx_locator_tool_execute_once:
        xlsx_locator_before_rows = [dict(row) for row in raw_outputs]
        raw_outputs, xlsx_locator_run_record = apply_xlsx_locator_tool_execute_once_to_outputs(
            raw_outputs,
            evidence_gate_mode=normalized_evidence_gate_mode,
            citation_format=normalized_selected_evidence_citation_format,
            composer_provider=normalized_answer_composer,
            local_llm_backend=local_llm_composer_backend,
            local_llm_base_url=local_llm_composer_base_url,
            local_llm_model=local_llm_composer_model,
            local_llm_timeout_seconds=local_llm_composer_timeout_seconds,
            local_llm_max_tokens=local_llm_composer_max_tokens,
            skip_local_llm_endpoint_check=skip_local_llm_composer_endpoint_check,
        )
        xlsx_locator_after_rows = [dict(row) for row in raw_outputs]
        evidence_gate_summary = build_evidence_gate_summary(raw_outputs, mode=normalized_evidence_gate_mode)
    agentic_planner_execute_once_report: dict[str, Any] | None = None
    if normalized_agentic_planner_mode == "execute-once":
        raw_outputs, agentic_planner_execute_once_report = apply_agentic_planner_execute_once_to_outputs(
            raw_outputs,
            adapter=adapter,
            top_k=top_k,
            evidence_gate_mode=normalized_evidence_gate_mode,
            citation_format=normalized_selected_evidence_citation_format,
            composer_provider=normalized_answer_composer,
            local_llm_backend=local_llm_composer_backend,
            local_llm_base_url=local_llm_composer_base_url,
            local_llm_model=local_llm_composer_model,
            local_llm_timeout_seconds=local_llm_composer_timeout_seconds,
            local_llm_max_tokens=local_llm_composer_max_tokens,
            skip_local_llm_endpoint_check=skip_local_llm_composer_endpoint_check,
        )
        evidence_gate_summary = build_evidence_gate_summary(raw_outputs, mode=normalized_evidence_gate_mode)
    reviewed_mapping_path = Path(reviewed_evidence_mapping_csv) if reviewed_evidence_mapping_csv is not None else None
    items, reviewed_mapping = apply_reviewed_evidence_mapping(
        items,
        reviewed_mapping_csv=reviewed_mapping_path,
    )
    denominator_after_reviewed_mapping = _strict_denominator_snapshot(items)
    denominator_changes = _denominator_change_report(
        denominator_before_reviewed_mapping,
        denominator_after_reviewed_mapping,
    )
    evidence_config = _evidence_resolution_config(
        enabled=resolve_expected_evidence,
        scope=evidence_resolution_scope,
        max_candidates=max_evidence_candidates,
        min_score=min_evidence_resolution_score,
        count_medium=count_medium_evidence_resolution,
    )
    if evidence_config.enabled:
        raw_outputs = apply_expected_evidence_resolution(
            items=items,
            raw_outputs=raw_outputs,
            adapter=adapter,
            config=evidence_config,
        )

    top_k_values = top_k_values_for(top_k)
    summary, scored_rows = score_rag_eval_items(
        items,
        raw_outputs,
        top_k_values=top_k_values,
        judge_adapter=judge_adapter,
        provisional_require_citations=provisional_require_citations,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    adapter_external_vector_db = getattr(adapter, "external_vector_db_report", None)
    if isinstance(adapter_external_vector_db, Mapping):
        external_vector_db = dict(adapter_external_vector_db)
    backend_comparison = build_backend_comparison_metrics(raw_outputs, adapter)
    summary["diagnostic_metrics"].update(backend_comparison)
    surface_comparison = build_surface_comparison_metrics(raw_outputs, top_k)
    add_surface_metrics(summary, surface_comparison, top_k=top_k)
    surface_next_repair_targets: list[str] = []
    if int(surface_comparison.get("source_native_target_span_present_but_not_retrieved_count") or 0) > 0:
        surface_next_repair_targets.append("repair source-native retrieval ranking/query formulation")
    if int(surface_comparison.get("source_native_target_span_absent_count") or 0) > 0:
        surface_next_repair_targets.append("repair source-native corpus/source coverage")
    if bool(surface_comparison.get("surface_comparison_available")):
        surface_next_repair_targets.append("keep SearchUnit/SearchView as legacy comparison baseline only")
    retrieval_backend_report = (
        dict(adapter.retrieval_backend_report)
        if isinstance(getattr(adapter, "retrieval_backend_report", None), Mapping)
        else {
            "requested": normalized_retrieval_backend,
            "selected": "unknown",
            "bm25_enabled": False,
            "vector_enabled": False,
            "hybrid_enabled": False,
            "embedding_model": "",
            "embedding_device": "unavailable",
            "gpu_used_for_embedding": False,
            "vector_index_kind": "unavailable",
            "vector_index_type": "unavailable",
            "vector_dim": 0,
            "indexed_unit_count": 0,
            "query_count": len(items),
            "fallback_reason": "adapter_did_not_report_backend",
        }
    )
    retrieval_surface_report = (
        dict(adapter.retrieval_surface_report)
        if isinstance(getattr(adapter, "retrieval_surface_report", None), Mapping)
        else {
            "requested": normalized_retrieval_surface.replace("-", "_"),
            "selected": "precomputed_context" if context_jsonl_path else "unknown",
            "source_native_available": False,
            "source_native_selected": False,
            "source_native_unit_count": 0,
            "searchunit_searchview_role": "legacy_comparison_debug_only",
            "searchunit_searchview_candidate_surface_enabled": False,
            "legacy_surface_comparison_enabled": False,
            "auto_fallback_to_searchunit_searchview": False,
            "fallback_reason": "adapter_did_not_report_surface",
        }
    )
    retrieval_surface_decision = (
        dict(adapter.retrieval_surface_decision)
        if isinstance(getattr(adapter, "retrieval_surface_decision", None), Mapping)
        else {
            "selected_default_surface": retrieval_surface_report.get("selected"),
            "searchunit_searchview_demoted": False,
            "demotion_reason": "",
            "source_native_available": bool(retrieval_surface_report.get("source_native_available")),
            "source_native_selected": bool(retrieval_surface_report.get("source_native_selected")),
            "fallback_reason": retrieval_surface_report.get("fallback_reason"),
            "recommendation": "surface_comparison_unavailable",
        }
    )
    surface_migration = build_surface_migration_report(
        retrieval_surface_report=retrieval_surface_report,
        retrieval_backend_report=retrieval_backend_report,
        surface_comparison=surface_comparison,
        legacy_surface_comparison=legacy_surface_comparison,
    )
    source_native_layered_retrieval = build_source_native_layered_retrieval_report(
        raw_outputs=raw_outputs,
        retrieval_surface_report=retrieval_surface_report,
        retrieval_backend_report=retrieval_backend_report,
        legacy_surface_comparison=legacy_surface_comparison,
    )
    vector_index_audit = build_vector_index_audit_report(
        raw_outputs=raw_outputs,
        adapter=adapter,
        retrieval_surface_report=retrieval_surface_report,
        retrieval_backend_report=retrieval_backend_report,
        backend_comparison=backend_comparison,
        external_vector_db=external_vector_db,
    )
    summary["diagnostic_metrics"].update(vector_index_audit.get("target_presence_diagnostics") or {})
    diagnostic_retrieval_metrics = build_diagnostic_retrieval_metrics_report(scored_rows, top_k=top_k)
    semantic_quality_samples = build_semantic_quality_samples_report(scored_rows)
    for ranking_name, ranking_metrics in (diagnostic_retrieval_metrics.get("rankings") or {}).items():
        if not isinstance(ranking_metrics, Mapping):
            continue
        for metric_name, metric_value in ranking_metrics.items():
            if metric_name.startswith(("hit@", "ndcg@")):
                summary["diagnostic_metrics"][f"{ranking_name}_{metric_name}_diagnostic"] = metric_value
    normalized_corpus_audit_query_ids = _normalize_audit_query_ids(corpus_coverage_audit_query_ids)
    corpus_coverage_lane_factory: Callable[[str], Any] | None = None
    if normalized_corpus_audit_query_ids:
        if corpus_coverage_audit_lane_factory is not None:
            corpus_coverage_lane_factory = corpus_coverage_audit_lane_factory
        elif adapter_is_weaviate_lane:
            def default_corpus_coverage_lane_factory(route_mode: str) -> WeaviateSourceAtomAdapter:
                return build_default_weaviate_adapter(
                    requested_backend=normalized_retrieval_backend,
                    retrieval_route_mode=route_mode,
                )

            corpus_coverage_lane_factory = default_corpus_coverage_lane_factory
    active_index_manifest_path = _clean(corpus_coverage_audit_index_manifest_path)
    if not active_index_manifest_path:
        active_config = getattr(adapter, "config_obj", None)
        active_index_manifest_path = _clean(getattr(active_config, "index_manifest_path", ""))
    corpus_coverage_audit = build_corpus_coverage_audit_report(
        items=items,
        rows=raw_outputs,
        query_ids=normalized_corpus_audit_query_ids,
        target_anchors=corpus_coverage_audit_target_anchors,
        top_k=top_k,
        lane_factory=corpus_coverage_lane_factory,
        source_registry_path=corpus_coverage_audit_source_registry_path,
        active_index_checkpoint_path=corpus_coverage_audit_index_checkpoint_path,
        active_index_manifest_path=active_index_manifest_path,
    )
    summary["diagnostic_metrics"].update(
        {
            "corpus_coverage_audit_enabled": bool(corpus_coverage_audit.get("enabled")),
            "corpus_coverage_audit_row_count": int(corpus_coverage_audit.get("row_count") or 0),
            "corpus_coverage_audit_route_filter_failure_count": int(
                (corpus_coverage_audit.get("classification_counts") or {}).get("route_filter_failure", 0)
            )
            if isinstance(corpus_coverage_audit.get("classification_counts"), Mapping)
            else 0,
        }
    )
    composer_rows = [
        row.get("answer_composer") if isinstance(row.get("answer_composer"), Mapping) else {}
        for row in raw_outputs
    ]
    composer_selected_counts = [int(row.get("selected_evidence_count") or 0) for row in composer_rows]
    local_llm_requested = normalized_answer_composer == SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROVIDER
    local_llm_rows = [
        row.get("local_llm") if isinstance(row.get("local_llm"), Mapping) else {}
        for row in composer_rows
        if isinstance(row.get("local_llm"), Mapping)
    ]
    retry_rows = [
        row.get("retry") if isinstance(row.get("retry"), Mapping) else {}
        for row in composer_rows
        if isinstance(row.get("retry"), Mapping)
    ]
    final_answer_discipline_rows = [
        row.get("answer_discipline") if isinstance(row.get("answer_discipline"), Mapping) else {}
        for row in composer_rows
        if isinstance(row.get("answer_discipline"), Mapping)
    ]
    primary_answer_discipline_rows: list[Mapping[str, Any]] = []
    for row in composer_rows:
        initial = row.get("initial_answer_discipline") if isinstance(row.get("initial_answer_discipline"), Mapping) else {}
        final = row.get("answer_discipline") if isinstance(row.get("answer_discipline"), Mapping) else {}
        if initial:
            primary_answer_discipline_rows.append(initial)
        elif final:
            primary_answer_discipline_rows.append(final)
    local_llm_status_counts = Counter(_clean(row.get("status")) or "unknown" for row in local_llm_rows)
    retry_status_counts = Counter(_clean(row.get("status")) or "unknown" for row in retry_rows)
    answer_discipline_status_counts = Counter(
        _clean(row.get("status")) or "unknown" for row in primary_answer_discipline_rows
    )
    final_answer_discipline_status_counts = Counter(
        _clean(row.get("status")) or "unknown" for row in final_answer_discipline_rows
    )
    local_llm_fallback_reason_counts = Counter(
        _clean(row.get("trigger"))
        for row in retry_rows
        if _clean(row.get("trigger")).startswith("answer_discipline_")
    )
    local_llm_fallback_reason_counts.update(
        _clean(row.get("fallback_reason"))
        for row in local_llm_rows
        if _clean(row.get("fallback_reason")).startswith("answer_discipline_")
    )
    local_llm_blockers = sorted(
        {
            _clean(blocker)
            for row in local_llm_rows
            for blocker in _as_list(row.get("blockers"))
            if _clean(blocker)
        }
    )
    local_llm_generated_count = local_llm_status_counts.get("generated", 0)
    local_llm_answer_discipline_denominator = len(primary_answer_discipline_rows)
    local_llm_accepted_clean_count = sum(
        1
        for composer in composer_rows
        if _clean(
            (composer.get("answer_discipline") if isinstance(composer.get("answer_discipline"), Mapping) else {}).get(
                "status"
            )
        )
        == "clean_supported"
        and not bool(composer.get("local_llm_fallback_used"))
        and _clean(
            (composer.get("local_llm") if isinstance(composer.get("local_llm"), Mapping) else {}).get("status")
        )
        == "generated"
    )
    def _discipline_maps_for_composer(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        maps: list[Mapping[str, Any]] = []
        for key in ("initial_answer_discipline", "answer_discipline"):
            value = row.get(key)
            if isinstance(value, Mapping):
                maps.append(value)
        return maps

    unsupported_extra_detail_count = sum(
        1
        for row in composer_rows
        if any(
            bool(discipline.get("unsupported_extra_detail"))
            or _clean(discipline.get("status")) == "supported_core_with_unsupported_extra"
            for discipline in _discipline_maps_for_composer(row)
        )
    )
    query_irrelevant_supported_detail_count = sum(
        1
        for row in composer_rows
        if any(
            bool(discipline.get("query_irrelevant_supported_detail"))
            or _clean(discipline.get("status")) == "query_irrelevant_supported_detail"
            for discipline in _discipline_maps_for_composer(row)
        )
    )
    local_llm_rejected_then_deterministic_overexpanded_count = max(
        answer_discipline_status_counts.get("local_llm_rejected_then_deterministic_overexpanded", 0),
        final_answer_discipline_status_counts.get("local_llm_rejected_then_deterministic_overexpanded", 0),
    )
    answer_overexpansion_count_diagnostic = sum(
        1
        for row in composer_rows
        if any(
            bool(discipline.get("unsupported_extra_detail"))
            or bool(discipline.get("query_irrelevant_supported_detail"))
            or _clean(discipline.get("status"))
            in {
                "supported_core_with_unsupported_extra",
                "query_irrelevant_supported_detail",
                "local_llm_rejected_then_deterministic_overexpanded",
            }
            for discipline in _discipline_maps_for_composer(row)
        )
    )
    local_llm_clean_answer_output_rejected_count = sum(
        1
        for row in composer_rows
        if _clean(
            (row.get("initial_answer_discipline") if isinstance(row.get("initial_answer_discipline"), Mapping) else {}).get(
                "status"
            )
        )
        == "clean_supported"
        and _clean((row.get("local_llm") if isinstance(row.get("local_llm"), Mapping) else {}).get("status"))
        == "unsupported_or_empty_deterministic_fallback"
        and bool(row.get("local_llm_fallback_used"))
    )
    local_llm_gate_aligned_fallback_count = sum(
        1
        for row in composer_rows
        if _clean((row.get("local_llm") if isinstance(row.get("local_llm"), Mapping) else {}).get("status"))
        == "gate_aligned_deterministic_fallback"
        and bool(row.get("local_llm_gate_aligned_fallback_used"))
    )
    local_llm_clean_answer_gate_blocked_count = sum(
        1
        for output, row in zip(raw_outputs, composer_rows)
        if _clean((row.get("local_llm") if isinstance(row.get("local_llm"), Mapping) else {}).get("status"))
        == "generated"
        and _clean((row.get("answer_discipline") if isinstance(row.get("answer_discipline"), Mapping) else {}).get("status"))
        == "clean_supported"
        and _clean((output.get("evidence_gate") if isinstance(output.get("evidence_gate"), Mapping) else {}).get("answer_gate_decision"))
        == "block_unsupported_answer"
    )
    local_llm_fallback_used = local_llm_requested and (
        any(bool(row.get("local_llm_fallback_used")) for row in composer_rows)
        or any(_clean(row.get("status")) != "generated" for row in local_llm_rows)
    )
    if not local_llm_requested:
        local_llm_not_used_reason = "local_llm_generator_not_wired_for_this_pass"
    elif local_llm_generated_count:
        local_llm_not_used_reason = ""
    elif local_llm_status_counts.get("unavailable_deterministic_fallback"):
        local_llm_not_used_reason = "local_llm_unavailable_deterministic_fallback"
    elif local_llm_status_counts.get("skipped_insufficient_selected_evidence"):
        local_llm_not_used_reason = "selected_evidence_insufficient_before_local_llm"
    else:
        local_llm_not_used_reason = "local_llm_not_generated_deterministic_fallback"
    generator_config = {
        "provider": normalized_answer_composer,
        "generator_provider": normalized_answer_composer,
        "extractive_only": not composer_applied,
        "answer_composer_provider": normalized_answer_composer,
        "selected_evidence_composer_invoked": composer_applied,
        "selected_evidence_composer_item_count": len(composer_rows) if composer_applied else 0,
        "selected_evidence_composer_abstained_count": sum(1 for row in composer_rows if row.get("abstained")) if composer_applied else 0,
        "selected_evidence_composer_selected_evidence_count": sum(composer_selected_counts) if composer_applied else 0,
        "selected_evidence_composer_input_policy": SELECTED_EVIDENCE_COMPOSER_INPUT_POLICY if composer_applied else "",
        "selected_evidence_citation_formatter_invoked": composer_applied,
        "selected_evidence_citation_format": normalized_selected_evidence_citation_format if composer_applied else "",
        "selected_evidence_citation_formatter_variants_available": sorted(SELECTED_EVIDENCE_CITATION_FORMATS),
        "selected_evidence_composer_retry_mode": normalized_selected_evidence_composer_retry_mode if composer_applied else "off",
        "selected_evidence_composer_retry_enabled": bool(composer_applied and normalized_selected_evidence_composer_retry_mode != "off"),
        "selected_evidence_composer_retry_max_count_per_item": 1,
        "selected_evidence_composer_retry_attempt_count": sum(int(row.get("attempt_count") or 0) for row in retry_rows),
        "selected_evidence_composer_retry_accepted_count": retry_status_counts.get("accepted", 0),
        "selected_evidence_composer_retry_rejected_count": retry_status_counts.get("rejected_gate_insufficient", 0),
        "selected_evidence_composer_retry_error_count": retry_status_counts.get("error", 0),
        "selected_evidence_composer_retry_status_counts": dict(retry_status_counts),
        "selected_evidence_composer_retry_input_policy": (
            SELECTED_EVIDENCE_COMPOSER_RETRY_INPUT_POLICY
            if composer_applied and normalized_selected_evidence_composer_retry_mode != "off"
            else ""
        ),
        "selected_evidence_composer_retry_raw_prompt_payload_written": False,
        "selected_evidence_composer_retry_raw_response_payload_written": False,
        "retrieved_context_only_citations_diagnostic_only": True,
        "extractive_v1_baseline_preserved_for_comparison": composer_applied,
        "actual_generation_model_used": bool(local_llm_generated_count),
        "local_llm_generation_available": bool(local_llm_generated_count),
        "local_llm_not_used_reason": local_llm_not_used_reason,
        "local_llm_composer_requested": local_llm_requested,
        "local_llm_composer_fallback_used": bool(local_llm_fallback_used),
        "local_llm_composer_generated_count": int(local_llm_generated_count),
        "local_llm_status_counts": dict(local_llm_status_counts),
        "local_llm_blockers": local_llm_blockers,
        "local_llm_acceptance_rate": (
            None
            if not local_llm_requested or local_llm_answer_discipline_denominator == 0
            else round(local_llm_accepted_clean_count / local_llm_answer_discipline_denominator, 6)
        ),
        "local_llm_accepted_clean_count": int(local_llm_accepted_clean_count),
        "local_llm_answer_discipline_status_counts": dict(answer_discipline_status_counts),
        "local_llm_final_answer_discipline_status_counts": dict(final_answer_discipline_status_counts),
        "local_llm_fallback_reason_counts": dict(local_llm_fallback_reason_counts),
        "answer_overexpansion_count_diagnostic": int(answer_overexpansion_count_diagnostic),
        "unsupported_extra_detail_count": int(unsupported_extra_detail_count),
        "query_irrelevant_supported_detail_count": int(query_irrelevant_supported_detail_count),
        "local_llm_rejected_then_deterministic_overexpanded_count": int(
            local_llm_rejected_then_deterministic_overexpanded_count
        ),
        "local_llm_clean_answer_output_rejected_count": int(local_llm_clean_answer_output_rejected_count),
        "local_llm_gate_aligned_fallback_count": int(local_llm_gate_aligned_fallback_count),
        "local_llm_clean_answer_gate_blocked_count": int(local_llm_clean_answer_gate_blocked_count),
        "citation_id_mismatch_or_missing_count": int(
            answer_discipline_status_counts.get("citation_id_mismatch_or_missing", 0)
        ),
        "anchor_morphology_false_negative_count": int(
            answer_discipline_status_counts.get("anchor_morphology_false_negative", 0)
        ),
        "answer_discipline_input_policy": (
            SELECTED_EVIDENCE_ANSWER_DISCIPLINE_INPUT_POLICY if local_llm_requested else ""
        ),
        "local_llm_prompt_payload_written": False,
        "local_llm_raw_response_payload_written": False,
        "external_api_calls": False,
        "expected_answer_used_for_generation": False,
        "expected_evidence_used_for_generation": False,
    }
    if composer_applied:
        report_limitations = [
            "selected-evidence composer supplies answers from selected SourceAtom/EvidenceBundle evidence for this pass",
            "backend comparison metrics are diagnostic and not official retrieval metrics",
            "external VectorDB is optional and blocked unless explicitly non-production",
        ]
        report_next_repair_targets = [
            *surface_next_repair_targets,
            "repair retrieval/query formulation and selected-evidence anchor coverage before any broader agent loop",
            "use human-owned review before any gold/qrels/answerability updates",
            "add external VectorDB parity only against an explicitly non-production namespace",
        ]
        report_residual_risks = [
            "route-selected default remains non-production diagnostic until fresh text and mixed diagnostic runs are reviewed",
            "full-index Weaviate rollback must remain available through rollback_config",
            "selected-evidence composer is active, but residual repair still requires retrieval/query formulation or selected-evidence anchor coverage",
        ]
    else:
        report_limitations = [
            "extractive-v1 remains the generator for this pass",
            "backend comparison metrics are diagnostic and not official retrieval metrics",
            "external VectorDB is optional and blocked unless explicitly non-production",
        ]
        report_next_repair_targets = [
            *surface_next_repair_targets,
            "replace extractive-v1 only after a richer repo generator is ready",
            "use human-owned review before any gold/qrels/answerability updates",
            "add external VectorDB parity only against an explicitly non-production namespace",
        ]
        report_residual_risks = [
            "route-selected default remains non-production diagnostic until fresh text and mixed diagnostic runs are reviewed",
            "full-index Weaviate rollback must remain available through rollback_config",
            "answer composition remains extractive-v1 unless a selected-evidence composer is explicitly enabled",
        ]
    active_path_report = (
        dict(adapter.active_path_report)
        if isinstance(getattr(adapter, "active_path_report", None), Mapping)
        else {
            "active_retrieval_backend": _clean(retrieval_backend_report.get("selected")),
            "active_retrieval_service_boundary": "python_source_native"
            if retrieval_surface_report.get("selected") == "source_native"
            else _clean(retrieval_surface_report.get("selected")) or "unknown",
            "python_local_corpus_scan_used_for_candidate_generation": retrieval_surface_report.get("selected") == "source_native",
            "source_native_layered_retrieval_used_for_candidate_generation": bool(source_native_layered_retrieval.get("enabled")),
            "diagnostic_hash_vector_used": "diagnostic" in _clean(retrieval_backend_report.get("embedding_model")).casefold(),
            "faiss_used_for_active_retrieval": _clean(retrieval_backend_report.get("vector_index_kind")) == "faiss",
            "searchunit_searchview_used_as_candidate_surface": bool(
                retrieval_surface_report.get("searchunit_searchview_candidate_surface_enabled")
            ),
            "candidate_generation_input_policy": "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk",
        }
    )
    summary.update(
        {
            **active_path_report,
            "run_id": run_id,
            "generated_at": generated_at,
            "command": _redact_absolute_local_paths(command),
            "dataset_path": _report_path_value(dataset),
            "dataset_slug": dataset_slug_for_path(dataset),
            "output_dir": _report_path_value(output),
            "index": index,
            "index_retrieval_config": adapter.config,
            "retrieval_backend": retrieval_backend_report,
            "retrieval_surface": retrieval_surface_report,
            "retrieval_surface_decision": retrieval_surface_decision,
            "surface_migration": surface_migration,
            "surface_deprecation": surface_migration,
            "source_native_layered_retrieval": source_native_layered_retrieval,
            "vector_index_audit": vector_index_audit,
            "final_rag_target": build_final_rag_target_report(),
            "gpu_preflight": gpu_preflight,
            "external_vector_db": external_vector_db,
            "backend_comparison": backend_comparison,
            "surface_comparison": surface_comparison,
            "diagnostic_retrieval_metrics": diagnostic_retrieval_metrics,
            "semantic_quality_samples": semantic_quality_samples,
            "response_quality_input_summary": response_quality_input_summary,
            "selected_evidence_failure_decomposition": build_selected_evidence_failure_decomposition(
                items=items,
                rows=raw_outputs,
            ),
            "dataset_sufficiency_diagnostic": build_dataset_sufficiency_diagnostic(
                items=items,
                rows=raw_outputs,
                dataset_path=dataset,
            ),
            "overfit_and_heuristic_audit": build_overfit_and_heuristic_audit(
                rows=raw_outputs,
                generator_config=generator_config,
            ),
            "residual_anchor_matrix": build_residual_anchor_matrix(items=items, rows=raw_outputs),
            "source_native_axis_provenance": build_source_native_axis_provenance(items=items, rows=raw_outputs),
            "pdf_source_native_decomposition": build_pdf_source_native_decomposition(items=items, rows=raw_outputs),
            "xlsx_pdf_residual_breakdown": build_xlsx_pdf_residual_breakdown(items=items, rows=raw_outputs),
            "corpus_coverage_audit": corpus_coverage_audit,
            "source_native_index_build": dict(source_native_index_build or {}),
            "generator_config": generator_config,
            "generator_model_config": generator_config,
            "evidence_gate": evidence_gate_summary,
            "evidence_gate_mode": evidence_gate_summary["evidence_gate_mode"],
            "validator_version": evidence_gate_summary["validator_version"],
            "top_k": top_k,
            "top_k_values": list(top_k_values),
            "judge_mode": judge_mode,
            "provisional_require_citations": bool(provisional_require_citations),
            "expected_evidence_resolution_config": {
                "enabled": bool(evidence_config.enabled),
                "scope": evidence_config.scope,
                "max_candidates": evidence_config.max_candidates,
                "min_score": evidence_config.min_score,
                "count_medium": evidence_config.count_medium,
                "diagnostic_candidate_lookup_only": True,
                "retriever_ranking_change": False,
                "gold_or_qrels_mutation": False,
                "candidate_generation_input_policy": "query_text_only_for_index_lookup; expected fields scoring_only",
            },
            "evidence_mapping_packet_config": {
                "enabled": bool(write_human_review_packet or write_evidence_mapping_packet),
                "diagnostic_review_packet_only": True,
                "machine_recommendation_not_gold": True,
                "human_decision_fields_filled_by_codex": False,
                "retriever_ranking_change": False,
                "gold_or_qrels_mutation": False,
                "single_review_artifact_format": "csv",
            },
            "reviewed_mapping": dict(reviewed_mapping),
            "reviewed_mapping_input_path": reviewed_mapping.get("input_path", ""),
            "reviewed_mapping_applied": bool(reviewed_mapping.get("applied")),
            "reviewed_mapping_row_count": int(reviewed_mapping.get("row_count") or 0),
            "denominator_changes": denominator_changes,
            "elapsed_ms": elapsed_ms,
            "non_production": True,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "official_metric_input_rows_created": 0,
            "official_metric_input_rows_consumed": 0,
            "protected_namespaces_touched": [],
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "gold_or_qrels_mutation": False,
            "human_decision_fields_filled_by_codex": False,
            "gold_fields_used_for_candidate_generation": False,
            "query_id_used_for_candidate_generation": False,
            "row_id_used_for_candidate_generation": False,
            "target_id_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
            "expected_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "ids_used_for_candidate_generation": False,
            "retriever_oracle_shortcut_used": False,
            "gate_uses_expected_fields": False,
            "gate_uses_gold_fields": False,
            "gate_uses_legacy_fields": False,
            "evidence_gate_retrieval_loop_triggered": False,
            "guardrails": {
                "non_production": True,
                "gold_mutation": False,
                "qrels_mutation": False,
                "label_mutation": False,
                "answerability_label_mutation": False,
                "expected_answer_mutation": False,
                "expected_evidence_mutation": False,
                "denominator_mutation": False,
                "retriever_ranking_improvement": False,
                "official_metric": False,
                "official_metric_input_rows": 0,
                "official_metric_input_rows_created": 0,
                "official_metric_input_rows_consumed": 0,
                "promotion_evidence": False,
                "product_success_evidence_allowed": False,
                "live_readiness_claim": False,
                "protected_namespaces_touched": [],
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
                "gold_fields_used_for_candidate_generation": False,
                "query_id_used_for_candidate_generation": False,
                "row_id_used_for_candidate_generation": False,
                "target_id_used_for_candidate_generation": False,
                "baseline_topk_used_for_candidate_generation": False,
                "expected_fields_used_for_candidate_generation": False,
                "qrels_used_for_candidate_generation": False,
                "answerability_labels_used_for_candidate_generation": False,
                "ids_used_for_candidate_generation": False,
                "retriever_oracle_shortcut_used": False,
                "gate_uses_expected_fields": False,
                "gate_uses_gold_fields": False,
                "gate_uses_legacy_fields": False,
                "evidence_gate_retrieval_loop_triggered": False,
            },
            "assumptions": [
                "actual RAG eval remains non-production diagnostic infrastructure",
                "SearchUnit/SearchView remains explicit legacy comparison/debug only for actual-RAG source-native runs",
                "SourceAtom/EvidenceBundle remains the evidence truth surface",
                "missing GPU/vector dependencies are recorded as fallback reasons rather than silently ignored",
            ],
            "limitations": report_limitations,
            "next_repair_targets": report_next_repair_targets,
            "residual_risks": report_residual_risks,
        }
    )

    report_path = output / "report.json"
    xlsx_locator_run_store_path = output / XLSX_LOCATOR_RUN_STORE_FILENAME
    reviewed_mapping_patch_path = (
        output / "reviewed_evidence_mapping_patch.json"
        if reviewed_mapping.get("enabled")
        else None
    )
    legacy_items_path = output / "rag_eval_items.jsonl"
    legacy_summary_path = output / "rag_eval_summary.json"
    legacy_markdown_path = output / "rag_eval_report.md"
    single_mode = normalized_output_mode in {"single", "both"}
    legacy_mode = normalized_output_mode in {"legacy", "both"}
    runstore_mode = normalized_output_mode == "runstore"
    legacy_mapping_packet_requested = bool(write_evidence_mapping_packet and legacy_mode and not write_human_review_packet)
    human_packet_requested = bool(write_human_review_packet or (write_evidence_mapping_packet and not legacy_mapping_packet_requested))
    summary["artifact_paths"] = {
        "report_json": report_path.as_posix() if single_mode else "",
        "items_jsonl": legacy_items_path.as_posix() if legacy_mode else "",
        "summary_json": (
            report_path.as_posix()
            if single_mode
            else legacy_summary_path.as_posix()
            if legacy_mode
            else ""
        ),
        "markdown_report": legacy_markdown_path.as_posix() if legacy_mode else "",
        "legacy_real_rag_quality_gate_report_json": "",
        "legacy_real_rag_quality_gate_items_jsonl": "",
        "xlsx_locator_run_sqlite": xlsx_locator_run_store_path.as_posix() if xlsx_locator_run_record is not None else "",
        "evidence_resolution_candidates_jsonl": (output / "evidence_resolution_candidates.jsonl").as_posix() if legacy_mode else "",
        "evidence_resolution_review_md": (output / "evidence_resolution_review.md").as_posix() if legacy_mode else "",
        "evidence_mapping_review_packet_csv": (output / "evidence_mapping_review_packet.csv").as_posix()
        if legacy_mapping_packet_requested
        else "",
        "evidence_mapping_review_packet_jsonl": (output / "evidence_mapping_review_packet.jsonl").as_posix()
        if legacy_mapping_packet_requested
        else "",
        "evidence_mapping_review_packet_md": (output / "evidence_mapping_review_packet.md").as_posix()
        if legacy_mapping_packet_requested
        else "",
        "evidence_mapping_packet_summary_json": (output / "evidence_mapping_packet_summary.json").as_posix()
        if legacy_mapping_packet_requested
        else "",
        "human_review_packet_csv": (output / "human_review_packet.csv").as_posix() if human_packet_requested else "",
        "reviewed_evidence_mapping_patch_json": reviewed_mapping_patch_path.as_posix() if reviewed_mapping_patch_path else "",
        "corpus_coverage_audit_jsonl": "",
    }
    packet_rows, packet_summary = build_evidence_mapping_packet(
        summary=summary,
        rows=scored_rows,
        adapter=adapter,
        enabled=bool(human_packet_requested or legacy_mapping_packet_requested),
    )
    _apply_mapping_packet_summary(summary, packet_summary)
    summary["diagnostic_metrics"].update(
        {
            "reviewed_mapping_input_path": reviewed_mapping.get("input_path", ""),
            "reviewed_mapping_applied": bool(reviewed_mapping.get("applied")),
            "reviewed_mapping_row_count": int(reviewed_mapping.get("row_count") or 0),
            "reviewed_mapping_accepted_mapping_count": int(reviewed_mapping.get("accepted_mapping_count") or 0),
            "reviewed_mapping_answerability_label_applied_count": int(
                reviewed_mapping.get("answerability_label_applied_count") or 0
            ),
            "reviewed_mapping_machine_recommendation_treated_as_gold": False,
        }
    )
    evidence_candidates = evidence_resolution_candidate_rows(scored_rows)
    human_review_packet_path: Path | None = None
    if human_packet_requested:
        human_review_packet_path, packet_row_count = write_human_review_packet_csv(output, packet_rows)
    else:
        packet_row_count = 0
    summary["human_review_packet"] = {
        "enabled": human_packet_requested,
        "path": human_review_packet_path.as_posix() if human_review_packet_path else "",
        "row_count": packet_row_count,
        "review_reason": "explicit_human_review_packet_flag" if human_packet_requested else "",
        "format": "csv" if human_packet_requested else "",
        "format_decision": "csv is the single review artifact because it is directly spreadsheet-reviewable and avoids JSONL/Markdown/summary sidecars",
        "human_decision_fields_blank": True,
        "gold_qrels_labels_mutated": False,
    }
    summary["evidence_resolution"] = _evidence_resolution_summary(summary)
    summary["expected_evidence_resolution"] = dict(summary["evidence_resolution"])
    summary["evidence_mapping_packet"] = _evidence_mapping_packet_summary(summary)
    summary["artifact_contract"] = _artifact_contract(
        output_mode=normalized_output_mode,
        report_path=report_path,
        legacy_written=legacy_mode,
        human_review_packet_path=human_review_packet_path,
        reviewed_mapping_patch_path=reviewed_mapping_patch_path,
    )
    summary["artifact_contract"]["portfolio_experiment_sidecar_written"] = False
    summary["artifact_contract"]["portfolio_experiment_sidecars_allowed_only_by_explicit_flag"] = True
    route_ab_modes = _parse_weaviate_route_ab_modes(weaviate_route_ab_mode)
    if route_ab_modes:
        if not adapter_is_weaviate_lane:
            raise DatasetSchemaError("weaviate route A/B mode requires a Weaviate retrieval backend")
        def default_route_ab_lane_factory(route_mode: str) -> WeaviateSourceAtomAdapter:
            return build_default_weaviate_adapter(
                requested_backend=normalized_retrieval_backend,
                retrieval_route_mode=route_mode,
            )

        route_ab_paths = write_weaviate_route_ab_artifacts(
            output_dir=output,
            suite_run_id=run_id,
            generated_at=generated_at,
            dataset_path=dataset,
            baseline_summary=summary,
            baseline_rows=scored_rows,
            items=items,
            modes=route_ab_modes,
            top_k=top_k,
            judge_adapter=judge_adapter,
            provisional_require_citations=provisional_require_citations,
            evidence_gate_mode=normalized_evidence_gate_mode,
            lane_factory=weaviate_route_ab_lane_factory or default_route_ab_lane_factory,
        )
        summary["artifact_paths"].update(route_ab_paths)
        summary["artifact_contract"]["route_ab_sidecar_exception"] = True
        summary["artifact_contract"]["route_ab_artifacts_allowed_only_by_weaviate_route_ab_mode"] = True
        route_ab_report_path = Path(_clean(route_ab_paths.get("route_selected_hybrid_evidence_store_ab_report_json")))
        try:
            route_ab_report = json.loads(route_ab_report_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            route_ab_report = {}
        if isinstance(route_ab_report, Mapping):
            summary["promotion_decision"] = _clean(route_ab_report.get("recommendation")) or summary.get(
                "promotion_decision",
                "blocked_keep_full_index_rollback",
            )
            summary["promotion_blockers"] = list(route_ab_report.get("promotion_blockers") or [])
            summary["weaviate_route_ab_report_path"] = route_ab_report_path.as_posix()
            summary["weaviate_route_ab_guardrail_status"] = dict(route_ab_report.get("guardrail_status") or {})
            summary["residual_risks"] = [
                "promotion decision is non-production diagnostic and not an official metric or readiness gate",
                "full-index Weaviate rollback remains the configured fallback path",
                "answer composer/citation formatter must cite selected EvidenceBundle only in the next lane",
            ]
            summary["next_recommended_goal"] = "selected_evidence_answer_composer_citation_formatter_nonprod"
    else:
        summary["artifact_paths"].update(
            {
                "route_selected_hybrid_evidence_store_ab_report_json": "",
                "route_selected_hybrid_evidence_store_ab_items_jsonl": "",
            }
        )
        summary["artifact_contract"]["route_ab_sidecar_exception"] = False
        summary["artifact_contract"]["route_ab_artifacts_allowed_only_by_weaviate_route_ab_mode"] = True
    summary.update(build_source_native_legacy_cleanup_sections(summary))
    if comparison_summary is not None:
        validate_actual_rag_guardrails(comparison_summary)
        summary["comparison"] = build_run_comparison(
            comparison_summary,
            summary,
            target_label=comparison_target,
        )
    summary["items"] = scored_rows
    summary["evidence_resolution_candidates"] = evidence_candidates
    if quality_gate_baseline_path is not None and _clean(quality_gate_baseline_path):
        legacy_baseline_report, resolved_baseline_path = resolve_quality_gate_baseline_report(
            quality_gate_baseline_path,
            dataset_path=dataset,
            gold_items=items,
            report_root=report_root,
        )
        quality_gate_report, quality_gate_rows, quality_gate_paths = write_legacy_real_rag_quality_gate_artifacts(
            output_dir=output,
            gold_items=items,
            existing_gold_set_path=dataset,
            legacy_baseline_report=legacy_baseline_report,
            legacy_baseline_path=resolved_baseline_path,
            real_rag_report=summary,
            real_rag_report_path=report_path,
            generated_at=generated_at,
        )
        summary["artifact_paths"].update(quality_gate_paths)
        summary["artifact_contract"]["quality_gate_sidecars_written"] = True
        summary["artifact_contract"]["quality_gate_sidecar_exception"] = True
        summary["artifact_contract"]["quality_gate_artifacts_allowed_only_by_quality_gate_baseline"] = True
        summary["legacy_real_rag_quality_gate"] = {
            "enabled": True,
            "schema_version": quality_gate_report["schema_version"],
            "report_json": quality_gate_paths["legacy_real_rag_quality_gate_report_json"],
            "items_jsonl": quality_gate_paths["legacy_real_rag_quality_gate_items_jsonl"],
            "legacy_baseline_path": quality_gate_report["legacy_baseline_path"],
            "legacy_baseline_run_id": quality_gate_report["legacy_baseline_run_id"],
            "legacy_baseline_replayed_not_executed": True,
            "item_count": quality_gate_report["item_count"],
            "comparable_item_count": quality_gate_report["comparable_item_count"],
            "answer_delta_category_counts": dict(quality_gate_report["answer_delta_category_counts"]),
            "evidence_package_status_counts": dict(quality_gate_report["evidence_package_status_counts"]),
            "guardrail_status": dict(quality_gate_report["guardrail_status"]),
            "diagnostic_critic_summary": dict(quality_gate_report["diagnostic_critic_summary"]),
            "row_count": len(quality_gate_rows),
        }
    else:
        summary["legacy_real_rag_quality_gate"] = {
            "enabled": False,
            "reason": "quality_gate_baseline_path_not_supplied",
        }
    refresh_weaviate_route_ab_quality_gate_counts(summary)
    public_scored_rows = [_public_report_row(row) for row in scored_rows]
    summary["items"] = public_scored_rows
    refresh_metric_tiers(summary)
    if normalized_agentic_planner_mode == "dry-run":
        summary["agentic_planner_dry_run"] = build_agentic_planner_dry_run_report(
            summary,
            mode=normalized_agentic_planner_mode,
        )
    if agentic_planner_execute_once_report is not None:
        summary["agentic_planner_execute_once"] = agentic_planner_execute_once_report
    if xlsx_locator_run_record is not None:
        summary["xlsx_locator_tool_execute_once"] = project_xlsx_locator_run_record(
            xlsx_locator_run_record,
            run_store_path=xlsx_locator_run_store_path,
        )
    summary["heuristic_risk_ledger"] = build_heuristic_risk_ledger(summary)
    summary["metric_continuity_checkpoint"] = build_metric_continuity_checkpoint(summary)
    summary["agentic_loop_review"] = build_agentic_loop_review(summary)
    portfolio_comparison_inputs = _load_portfolio_comparison_reports(portfolio_comparison_reports)
    if portfolio_comparison_inputs:
        summary["portfolio_experiment_comparison"] = build_portfolio_experiment_comparison(
            comparison_reports=portfolio_comparison_inputs,
            current_summary=summary,
        )
    elif write_portfolio_experiment_summary:
        raise DatasetSchemaError("--write-portfolio-experiment-summary requires at least one --portfolio-comparison-report")
    portfolio_experiment_summary_path: Path | None = None
    if write_portfolio_experiment_summary:
        comparison = summary.get("portfolio_experiment_comparison")
        if not isinstance(comparison, Mapping) or not comparison.get("enabled"):
            raise DatasetSchemaError("--write-portfolio-experiment-summary requires an enabled portfolio comparison")
        portfolio_experiment_summary_path = output / "portfolio_experiment_summary.md"
        summary.setdefault("artifact_paths", {})
        if isinstance(summary["artifact_paths"], MutableMapping):
            summary["artifact_paths"]["portfolio_experiment_summary_md"] = portfolio_experiment_summary_path.as_posix()
        artifact_contract = summary.get("artifact_contract")
        if isinstance(artifact_contract, MutableMapping):
            artifact_contract["portfolio_experiment_sidecar_written"] = True
            artifact_contract["portfolio_experiment_sidecar_path"] = portfolio_experiment_summary_path.as_posix()
    validate_actual_rag_guardrails(summary)
    output.mkdir(parents=True, exist_ok=True)
    if xlsx_locator_run_record is not None:
        if xlsx_locator_before_rows is None or xlsx_locator_after_rows is None:
            raise DatasetSchemaError("xlsx locator run record missing before/after rows")
        index_config = summary.get("index_retrieval_config") if isinstance(summary.get("index_retrieval_config"), Mapping) else {}
        run_store_collection = _clean(
            summary.get("collection")
            or summary.get("weaviate_collection_name")
            or index_config.get("collection")
            or index_config.get("retrieval_source")
            or "unavailable"
        )
        XlsxLocatorRunStore(xlsx_locator_run_store_path).write_run_record(
            run_id=run_id,
            dataset_slug=dataset_slug_for_path(dataset),
            collection=run_store_collection,
            record=xlsx_locator_run_record,
            before_rows=xlsx_locator_before_rows,
            after_rows=xlsx_locator_after_rows,
        )
        locator_projection = summary.get("xlsx_locator_tool_execute_once")
        if not isinstance(locator_projection, Mapping):
            raise DatasetSchemaError("xlsx locator projection missing after RunStore write")
        validate_xlsx_locator_run_store(run_id, locator_projection, run_store_path=xlsx_locator_run_store_path)
    if portfolio_experiment_summary_path is not None:
        comparison = summary.get("portfolio_experiment_comparison")
        if isinstance(comparison, Mapping):
            portfolio_experiment_summary_path.write_text(
                render_portfolio_experiment_summary(comparison),
                encoding="utf-8",
            )
    if reviewed_mapping_patch_path is not None:
        reviewed_mapping_patch_path = write_reviewed_mapping_patch_artifact(output, reviewed_mapping)
        summary["reviewed_mapping"]["patch_path"] = reviewed_mapping_patch_path.as_posix()
        summary["artifact_paths"]["reviewed_evidence_mapping_patch_json"] = reviewed_mapping_patch_path.as_posix()
        summary["artifact_contract"]["reviewed_mapping_patch_path"] = reviewed_mapping_patch_path.as_posix()
    if single_mode:
        write_json(report_path, summary)
    if legacy_mode:
        legacy_summary = dict(summary)
        legacy_summary.pop("items", None)
        legacy_summary.pop("evidence_resolution_candidates", None)
        write_jsonl(legacy_items_path, public_scored_rows)
        write_evidence_resolution_artifacts(output_dir=output, summary=legacy_summary, rows=public_scored_rows)
        write_json(legacy_summary_path, legacy_summary)
        legacy_markdown_path.write_text(render_markdown_report(legacy_summary, public_scored_rows), encoding="utf-8")
    if legacy_mapping_packet_requested:
        write_evidence_mapping_packet_artifacts(
            output_dir=output,
            summary=summary,
            packet_rows=packet_rows,
            packet_summary=packet_summary,
        )
    registry = Path(registry_path) if registry_path is not None else Path(report_root) / REGISTRY_FILENAME
    if append_registry:
        append_run_registry(summary, registry_path=registry)
        append_actual_rag_status_event(summary, status_jsonl_path=status_jsonl_path)
    if write_latest:
        write_latest_pointers(summary, report_root=report_root)
        write_report_index(report_root=report_root)
    close_adapter = getattr(adapter, "close", None)
    if callable(close_adapter):
        close_adapter()
    summary_path = report_path if single_mode else legacy_summary_path if legacy_mode else xlsx_locator_run_store_path
    items_path = report_path if single_mode else legacy_items_path if legacy_mode else xlsx_locator_run_store_path
    markdown_path = report_path if single_mode else legacy_markdown_path if legacy_mode else xlsx_locator_run_store_path
    return RagEvalBundle(
        output_dir=output,
        items_path=items_path,
        summary_path=summary_path,
        markdown_path=markdown_path,
        summary=summary,
        report_path=report_path if single_mode else None,
    )


def render_markdown_report(summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    strict = summary["strict_metrics"]
    provisional = summary["provisional_metrics"]
    inferred_answerable = summary.get("inferred_answerable_metrics") or {}
    diagnostic_details = summary.get("diagnostic_metric_details") or {}
    diagnostics = summary["diagnostic_metrics"]

    def append_metric_table(lines: list[str], metrics: Mapping[str, Any]) -> None:
        lines.extend(
            [
                "| Metric | Tier | Numerator | Denominator | Score | Skipped | N/A | Diagnostic-only |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for name, metric in metrics.items():
            score = "" if metric["score"] is None else f"{metric['score']:.6f}"
            lines.append(
                f"| {name} | {metric['tier']} | {metric['numerator']} | {metric['denominator']} | {score} | "
                f"{metric['skipped_count']} | {metric['not_applicable_count']} | {metric['diagnostic_only_count']} |"
            )

    def preview(value: Any, limit: int = 160) -> str:
        text = re.sub(r"\s+", " ", _clean(value))
        if len(text) <= limit:
            return text
        return text[: max(limit - 3, 0)].rstrip() + "..."

    def top_context_preview(row: Mapping[str, Any]) -> str:
        contexts = [context for context in _as_list(row.get("retrieved_contexts")) if isinstance(context, Mapping)]
        return preview(contexts[0].get("text") if contexts else "")

    def metric_failure_notes(row: Mapping[str, Any]) -> list[str]:
        labels = set(row.get("failure_labels") or [])
        results = row.get("metric_results") if isinstance(row.get("metric_results"), Mapping) else {}
        judge_result = results.get("judged_answer_correctness_provisional") if isinstance(results, Mapping) else None
        notes: list[str] = []
        if "retrieval_empty" in labels:
            notes.append("retrieval_empty")
        if isinstance(judge_result, Mapping) and judge_result.get("passed") is False:
            notes.append("answer_judge_failed")
        if any(
            str(name).startswith("evidence_recall@") and value is False
            for name, value in results.items()
        ) or any(
            str(name).startswith("weak_evidence_match_recall@") and value is False
            for name, value in results.items()
        ):
            notes.append("evidence_match_failed")
        if "citation_missing" in labels:
            notes.append("citation_missing")
        if "citation_wrong" in labels:
            notes.append("citation_wrong")
        if "answer_exact_mismatch" in labels:
            notes.append("answer_exact_mismatch")
        if results.get("e2e_rag_success_provisional") is False:
            notes.append("e2e_provisional_failed")
        return notes

    lines = [
        "# Actual RAG Eval Report",
        "",
        f"- Run id: `{summary.get('run_id')}`",
        f"- Generated at: `{summary.get('generated_at')}`",
        f"- Command used: `{summary.get('command') or 'not recorded'}`",
        f"- Dataset path: `{summary.get('dataset_path')}`",
        f"- Index/retrieval config: `{json.dumps(summary.get('index_retrieval_config'), ensure_ascii=False, sort_keys=True)}`",
        f"- Generator/model config: `{json.dumps(summary.get('generator_model_config'), ensure_ascii=False, sort_keys=True)}`",
        f"- Total item count: `{summary.get('total_item_count')}`",
        f"- Answerability distribution: `{json.dumps(summary.get('answerability_distribution'), ensure_ascii=False, sort_keys=True)}`",
        "",
    ]
    comparison = summary.get("comparison")
    if isinstance(comparison, Mapping) and comparison.get("rows"):
        lines.extend(
            [
                "## Previous Run Comparison",
                "",
                "| Metric | Tier | Previous | Current | Delta | Interpretation |",
                "|---|---|---:|---:|---:|---|",
            ]
        )
        for row in comparison.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            delta = row.get("delta")
            rendered_delta = "" if delta is None else f"{float(delta):.6f}"
            lines.append(
                f"| {row.get('metric')} | {row.get('tier')} | {row.get('previous')} | "
                f"{row.get('current')} | {rendered_delta} | {row.get('interpretation')} |"
            )
        lines.extend(
            [
                "",
                "Comparison rows are non-production diagnostics only. Denominator changes are not interpreted as quality improvement.",
                "",
            ]
        )
    lines.extend(["## Strict Headline Metrics", ""])
    append_metric_table(lines, strict)
    lines.extend(
        [
            "",
            "## Provisional RAG Metrics",
            "",
            f"- Judge config: `{json.dumps(summary.get('judge_config'), ensure_ascii=False, sort_keys=True)}`",
            f"- Provisional metric policy: `{json.dumps(summary.get('provisional_metric_policy'), ensure_ascii=False, sort_keys=True)}`",
            "- `e2e_rag_success_provisional` requires the provisional answer judge to pass; weak evidence overlap alone is insufficient.",
            "- The answer/context consistency diagnostic is used as a conservative E2E guard when context is available, but its standalone rate is not answer correctness.",
            "",
        ]
    )
    append_metric_table(lines, provisional)
    if inferred_answerable:
        lines.extend(
            [
                "",
                "## Inferred-Answerable Metrics",
                "",
                "These metrics infer answerability only for metric computation when answerability is unknown but expected answer and expected evidence exist. No gold label mutation occurred, and these are not official strict metrics.",
                "",
            ]
        )
        append_metric_table(lines, inferred_answerable)
    if diagnostic_details:
        lines.extend(
            [
                "",
                "## Diagnostic Consistency Metrics",
                "",
                "`answer_extracted_from_retrieved_context_rate` and `citation_points_to_retrieved_context_rate` are diagnostic consistency checks, not answer correctness and not citation correctness. The answer/context diagnostic can gate provisional E2E as a conservative support check, but it is not a standalone quality claim.",
                "",
            ]
        )
        append_metric_table(lines, diagnostic_details)
    lines.extend(
        [
            "",
            "## Diagnostic Metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
    )
    for key in sorted(diagnostics):
        value = diagnostics[key]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        lines.append(f"| {key} | `{rendered}` |")

    planner = summary.get("agentic_planner_dry_run")
    if isinstance(planner, Mapping) and planner.get("planner_enabled"):
        readiness = planner.get("execute_once_readiness") if isinstance(planner.get("execute_once_readiness"), Mapping) else {}
        lines.extend(
            [
                "",
                "## Agentic Planner Dry-Run",
                "",
                f"- Mode: `{planner.get('planner_mode')}`",
                f"- Decisions: `{planner.get('planner_decision_count')}`",
                f"- Failure classes: `{json.dumps(planner.get('planner_failure_class_counts'), ensure_ascii=False, sort_keys=True)}`",
                f"- Proposed actions: `{json.dumps(planner.get('planner_action_counts'), ensure_ascii=False, sort_keys=True)}`",
                f"- Expected extra queries/tools/LLM retries/memory lookups: `{planner.get('planner_expected_extra_query_count')}` / `{planner.get('planner_expected_tool_call_count')}` / `{planner.get('planner_expected_llm_retry_count')}` / `{planner.get('planner_expected_memory_lookup_count')}`",
                f"- Execute-once ready: `{readiness.get('ready')}`",
                f"- Execute-once assessment: `{readiness.get('assessment')}`",
                "",
                "Dry-run planner diagnostics run after the selected-evidence composer and evidence gate. They do not execute retrieval, tools, or LLM retry, and they do not change final citations.",
            ]
        )
    execute_once = summary.get("agentic_planner_execute_once")
    if isinstance(execute_once, Mapping) and execute_once.get("planner_enabled"):
        execution = (
            execute_once.get("planner_execution")
            if isinstance(execute_once.get("planner_execution"), Mapping)
            else {}
        )
        lines.extend(
            [
                "",
                "## Agentic Planner Execute-Once",
                "",
                f"- Decisions/executed: `{execute_once.get('planner_decision_count')}` / `{execute_once.get('planner_executed_decision_count')}`",
                f"- Failure classes: `{json.dumps(execute_once.get('planner_failure_class_counts'), ensure_ascii=False, sort_keys=True)}`",
                f"- Proposed actions: `{json.dumps(execute_once.get('planner_action_counts'), ensure_ascii=False, sort_keys=True)}`",
                f"- Executed extra queries/tools/LLM retries: `{execution.get('extra_query_count_executed')}` / `{execution.get('tool_call_count_executed')}` / `{execution.get('llm_retry_count_executed')}`",
                f"- Executed run-local memory lookups: `{execute_once.get('planner_memory_lookup_count_executed')}`",
                f"- Gate delta: `{json.dumps(execute_once.get('gate_delta'), ensure_ascii=False, sort_keys=True)}`",
                "",
                "Execute-once keeps production routing, official metrics, gate loosening, raw payloads, and retrieved-context-only citation promotion closed. Bounded source tools, LLM retry, and run-local memory are reported only when explicitly executed by one planner action.",
            ]
        )
    loop_review = summary.get("agentic_loop_review")
    if isinstance(loop_review, Mapping) and loop_review.get("enabled"):
        bounded = (
            loop_review.get("bounded_action_evidence")
            if isinstance(loop_review.get("bounded_action_evidence"), Mapping)
            else {}
        )
        loop_status = (
            loop_review.get("planner_memory_tool_llm_retry_loop_status")
            if isinstance(loop_review.get("planner_memory_tool_llm_retry_loop_status"), Mapping)
            else {}
        )
        lines.extend(
            [
                "",
                "## Agentic Loop Review",
                "",
                f"- Review only: `{loop_review.get('review_only')}`",
                f"- Broader agent loop ready/opened: `{loop_review.get('broader_agent_loop_ready')}` / `{loop_review.get('broader_agent_loop_opened')}`",
                f"- Recommendation: `{loop_review.get('recommendation')}`",
                f"- Planner mode: `{bounded.get('planner_mode')}`",
                f"- Bounded quality improvement measured: `{bounded.get('quality_improvement_measured')}`",
                f"- Live text-gold metric measured: `{bounded.get('live_text_gold_metric_measured')}`",
                f"- Executed query/tool/LLM/memory counts: `{loop_status.get('query_probe_executed_count')}` / `{loop_status.get('tool_use_executed_count')}` / `{loop_status.get('llm_retry_executed_count')}` / `{loop_status.get('run_local_memory_lookup_executed_count')}`",
                f"- Gate delta: `{json.dumps(bounded.get('gate_delta'), ensure_ascii=False, sort_keys=True)}`",
                "",
                "The broader agent loop remains closed. Bounded planner actions may be measured one checkpoint at a time, but broader loops require fresh live text-gold evidence, unchanged gate validation, and a human-approved official metric/denominator policy.",
            ]
        )

    resolution_rows = evidence_resolution_candidate_rows(rows)
    if diagnostics.get("expected_evidence_resolution_enabled"):
        lines.extend(
            [
                "",
                "## Expected Evidence Resolution Diagnostics",
                "",
                f"- Enabled/scope: `{diagnostics.get('expected_evidence_resolution_enabled')}` / `{diagnostics.get('expected_evidence_resolution_scope')}`",
                f"- Expected evidence rows: `{diagnostics.get('expected_evidence_row_count')}`",
                f"- Missing ID count: `{diagnostics.get('expected_evidence_id_missing_count')}`",
                f"- Exact resolved count: `{diagnostics.get('expected_evidence_id_resolved_exact_count')}`",
                f"- Candidate resolved count: `{diagnostics.get('expected_evidence_id_resolved_candidate_count')}`",
                f"- Unresolved count: `{diagnostics.get('expected_evidence_id_unresolved_count')}`",
                f"- Confidence counts: high=`{diagnostics.get('expected_evidence_resolution_high_confidence_count')}`, medium=`{diagnostics.get('expected_evidence_resolution_medium_confidence_count')}`, low=`{diagnostics.get('expected_evidence_resolution_low_confidence_count')}`",
                f"- Candidates JSONL: `{_artifact_path(summary, 'evidence_resolution_candidates_jsonl')}`",
                f"- Review Markdown: `{_artifact_path(summary, 'evidence_resolution_review_md')}`",
                "",
                "These mappings are diagnostic and do not mutate gold/qrels.",
                "",
                "### Top Unresolved Evidence Rows",
                "",
                "| Item | Query | Expected answer | Evidence preview | Reason unresolved | Top candidate preview |",
                "|---|---|---|---|---|---|",
            ]
        )
        unresolved = [row for row in resolution_rows if not row.get("resolved")]
        if unresolved:
            for row in unresolved[:10]:
                top = (row.get("candidates") or [{}])[0] if row.get("candidates") else {}
                lines.append(
                    f"| `{row.get('id')}` | {preview(row.get('query'), 90)} | {preview(row.get('expected_answer'), 80)} | "
                    f"{preview((row.get('expected_evidence') or {}).get('text'), 100)} | "
                    f"{', '.join(row.get('resolution_warnings') or [])} | {preview(top.get('text_preview'), 100)} |"
                )
        else:
            lines.append("| none |  |  |  |  |  |")
        lines.extend(
            [
                "",
                "### High/Medium Confidence Candidate Mappings",
                "",
                "| Item | Evidence preview | Selected doc_id | Selected chunk_id | Confidence | Score | Match reasons |",
                "|---|---|---|---|---|---:|---|",
            ]
        )
        mapped = False
        for row in resolution_rows:
            selected = row.get("selected_candidate") if isinstance(row.get("selected_candidate"), Mapping) else {}
            if selected.get("confidence") not in {"high", "medium"}:
                continue
            mapped = True
            lines.append(
                f"| `{row.get('id')}` | {preview((row.get('expected_evidence') or {}).get('text'), 100)} | "
                f"`{selected.get('doc_id')}` | `{selected.get('chunk_id')}` | `{selected.get('confidence')}` | "
                f"{selected.get('score')} | {', '.join(selected.get('match_reasons') or [])} |"
            )
        if not mapped:
            lines.append("| none |  |  |  |  |  |  |")

    if diagnostics.get("evidence_mapping_packet_enabled"):
        lines.extend(
            [
                "",
                "## Evidence Mapping Review Packet",
                "",
                f"- Enabled: `{diagnostics.get('evidence_mapping_packet_enabled')}`",
                f"- CSV: `{_artifact_path(summary, 'evidence_mapping_review_packet_csv')}`",
                f"- JSONL: `{_artifact_path(summary, 'evidence_mapping_review_packet_jsonl')}`",
                f"- Markdown: `{_artifact_path(summary, 'evidence_mapping_review_packet_md')}`",
                f"- Summary JSON: `{_artifact_path(summary, 'evidence_mapping_packet_summary_json')}`",
                f"- Packet rows: `{diagnostics.get('evidence_mapping_packet_row_count')}`",
                f"- Item count: `{diagnostics.get('evidence_mapping_packet_item_count')}`",
                f"- Recommendation counts: likely_accept=`{diagnostics.get('evidence_mapping_packet_likely_accept_count')}`, possible_match=`{diagnostics.get('evidence_mapping_packet_possible_match_count')}`, review_needed=`{diagnostics.get('evidence_mapping_packet_review_needed_count')}`, likely_reject=`{diagnostics.get('evidence_mapping_packet_likely_reject_count')}`",
                f"- Review priority counts: P0=`{diagnostics.get('evidence_mapping_packet_p0_count')}`, P1=`{diagnostics.get('evidence_mapping_packet_p1_count')}`, P2=`{diagnostics.get('evidence_mapping_packet_p2_count')}`, P3=`{diagnostics.get('evidence_mapping_packet_p3_count')}`, P4=`{diagnostics.get('evidence_mapping_packet_p4_count')}`",
                f"- Source metadata counts: resolved=`{diagnostics.get('source_metadata_resolved_candidate_count')}`, unresolved=`{diagnostics.get('source_metadata_unresolved_candidate_count')}`, redacted_paths=`{diagnostics.get('source_metadata_redacted_path_count')}`",
                f"- Human decision fields filled by Codex: `{diagnostics.get('human_decision_fields_filled_by_codex')}`",
                "",
                "Human decision fields remain blank. Machine recommendations are diagnostic review hints, not gold mappings. No gold/qrels mutation occurred.",
            ]
        )

    lines.extend(
        [
            "",
            "## Denominator Policy",
            "",
            str(summary.get("denominator_policy")),
            "",
            "## Failure Breakdown",
            "",
            "| Failure label | Count |",
            "|---|---:|",
        ]
    )
    failure_counts = diagnostics.get("failure_category_counts") or {}
    if failure_counts:
        for label, count in failure_counts.items():
            lines.append(f"| {label} | {count} |")
    else:
        lines.append("| none | 0 |")

    failed_rows = [
        row
        for row in rows
        if any(label not in INFORMATIONAL_LABELS for label in row.get("failure_labels") or [])
    ]
    lines.extend(["", "## Top Failed Examples", ""])
    if failed_rows:
        for row in failed_rows[:10]:
            labels = ", ".join(row.get("failure_labels") or [])
            notes = ", ".join(metric_failure_notes(row)) or "none"
            lines.extend(
                [
                    f"- `{row.get('id')}`",
                    f"  - Query: {preview(row.get('query'))}",
                    f"  - Expected answer: {preview(row.get('expected_answer'))}",
                    f"  - Generated answer: {preview(row.get('generated_answer'))}",
                    f"  - Top retrieved context: {top_context_preview(row)}",
                    f"  - Key metric failures: {notes}",
                    f"  - Retrieval empty: `{bool('retrieval_empty' in (row.get('failure_labels') or []))}`",
                    f"  - Answer judge failed: `{bool('answer_judge_failed' in notes or 'answer_judge_fail' in (row.get('failure_labels') or []))}`",
                    f"  - Evidence match failed: `{bool('evidence_match_failed' in notes or 'evidence_not_retrieved' in (row.get('failure_labels') or []))}`",
                    f"  - Citation missing/wrong: `{bool('citation_missing' in (row.get('failure_labels') or []) or 'citation_wrong' in (row.get('failure_labels') or []))}`",
                    f"  - Failure labels: {labels}",
                ]
            )
    else:
        lines.append("- No failed examples in this run.")

    lines.extend(
        [
            "",
            "## Gold/Data Quality Warnings",
            "",
            f"- Missing expected answer count: `{diagnostics.get('missing_expected_answer_count')}`",
            f"- Missing expected evidence count: `{diagnostics.get('missing_expected_evidence_count')}`",
            f"- Missing answerability label count: `{diagnostics.get('missing_answerability_label_count')}`",
            f"- Expected evidence ID missing count: `{diagnostics.get('expected_evidence_id_missing_count')}`",
            f"- Expected evidence ID unresolved count: `{diagnostics.get('expected_evidence_id_unresolved_count')}`",
            f"- Expected evidence text match candidate count: `{diagnostics.get('expected_evidence_text_match_candidate_count')}`",
            f"- Schema warning count: `{diagnostics.get('schema_warning_count')}`",
            f"- Gold missing count: `{diagnostics.get('gold_missing_count')}`",
            "",
            "## Assumptions Made By Codex",
            "",
        ]
    )
    for decision in summary.get("diagnostic_only_decisions") or []:
        lines.append(f"- {decision['decision']} Rationale: {decision['rationale']}")

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Strict exact/alias answer scoring is deterministic and does not claim semantic equivalence.",
            "- Provisional judged answer correctness is computed with weak assumptions unless a future configured LLM judge is enabled and recorded.",
            "- Weak evidence matching now requires either an ID match or text overlap plus at least one non-generic anchor from expected answer/evidence, but it remains provisional.",
            "- Answer/context and citation/retrieved-context consistency metrics are diagnostic; they do not prove answer correctness or citation correctness.",
            "- Incomplete gold rows still run; they are marked with warning labels and excluded only from strict denominators that require the missing field.",
            "- This runner does not tune retriever ranking.",
            "",
            "## Follow-Up Items Reserved For Human Gold-Policy Decisions",
            "",
            "- Review or supply missing expected answers, expected evidence, answerability labels, relevance labels, and aliases where stricter coverage is desired.",
            "- Decide final citation policy and final semantic/LLM judge policy before any official metric lane is opened.",
            "- Decide which provisional metrics can be promoted, retired, or replaced after reviewing failure examples.",
            "",
            "## Next Repair Targets",
            "",
            "- Connect a real generator adapter if the repo exposes a richer answer-generation path than extractive-v1.",
            "- Add a configurable LLM judge adapter only when model invocation infrastructure and reproducible judge configuration are ready.",
            "- Improve per-item failure examples after larger golden sets expose common failure clusters.",
        ]
    )
    return "\n".join(lines) + "\n"
