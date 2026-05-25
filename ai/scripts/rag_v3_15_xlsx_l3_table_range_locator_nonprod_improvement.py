from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_9_2_overfit_risk_audit_and_blind_holdout_reset as v392
import rag_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization as v310
import rag_v3_12_xlsx_structural_locator_nonprod_improvement as v312
import rag_v3_14_layered_retrieval_runtime_adapter_nonprod as v314


ROOT = v392.ROOT
if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))
if str(ROOT / "ai" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))


RUN_ID = "official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement"
REPORT_DIR = v392.REPORT_DIR
STATUS_JSONL = v392.STATUS_JSONL
PROGRESS_DOC = v392.PROGRESS_DOC
MEASUREMENTS_DOC = v392.MEASUREMENTS_DOC
TRIAGE_DOC = v392.TRIAGE_DOC

STATUS = "DIAGNOSTIC_V3_15_XLSX_L3_TABLE_RANGE_LOCATOR_NONPROD_IMPROVEMENT_READY"
EVENT_TYPE = "diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement"
RUNTIME_LAYER_NAMES = v314.RUNTIME_LAYER_NAMES
METRICS_TAXONOMY_LAYER = v314.METRICS_TAXONOMY_LAYER
SKIPPED_LAYERS = v314.SKIPPED_LAYERS
OPTIMIZATION_SURFACE = "XLSX_L3_TABLE_RANGE_LOCATOR_ONLY"
PDF_CONTROL_STATUS = "EXCLUDED_FROM_OPTIMIZATION_SURFACE"

OUTPUTS = {
    "summary_json": REPORT_DIR / f"{RUN_ID}_summary.json",
    "metrics_json": REPORT_DIR / f"{RUN_ID}_metrics.json",
    "per_family_json": REPORT_DIR / f"{RUN_ID}_per_family.json",
    "per_query_jsonl": REPORT_DIR / f"{RUN_ID}_per_query.jsonl",
    "layer_trace_per_query_jsonl": REPORT_DIR / f"{RUN_ID}_layer_trace_per_query.jsonl",
    "latency_summary_json": REPORT_DIR / f"{RUN_ID}_latency_summary.json",
    "candidate_flow_summary_json": REPORT_DIR / f"{RUN_ID}_candidate_flow_summary.json",
    "failure_taxonomy_json": REPORT_DIR / f"{RUN_ID}_failure_taxonomy.json",
    "guardrail_audit_json": REPORT_DIR / f"{RUN_ID}_guardrail_audit.json",
    "leakage_audit_jsonl": REPORT_DIR / f"{RUN_ID}_leakage_audit.jsonl",
    "holdout_manifest_json": REPORT_DIR / f"{RUN_ID}_holdout_manifest.json",
}

Candidate = v314.Candidate
LayeredRetrievalRequest = v314.LayeredRetrievalRequest
LayeredRetrievalTrace = v314.LayeredRetrievalTrace
CandidateSet = v314.CandidateSet
SourceFamilyRoute = v314.SourceFamilyRoute
SourceIdentityResolution = v314.SourceIdentityResolution
StructuralLocatorResult = v314.StructuralLocatorResult
HydratedEvidence = v314.HydratedEvidence
EvidenceBundle = v314.EvidenceBundle
AnswerReadyContext = v314.AnswerReadyContext
LayerTiming = v314.LayerTiming
LayerDropReason = v314.LayerDropReason
registry_evidence_bundle_is_valid = v314.registry_evidence_bundle_is_valid


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


def clean(value: Any) -> str:
    return v314.clean(value)


def as_mapping(value: Any) -> Mapping[str, Any]:
    return v314.as_mapping(value)


def sha256_file(path: Path) -> str:
    return v314.sha256_file(path)


def sha256_text(value: str) -> str:
    return v314.sha256_text(value)


def repo_relative(path: Path) -> str:
    return v314.repo_relative(path)


def read_json(path: Path) -> dict[str, Any]:
    return v314.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v314.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v314.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v314.write_jsonl(path, rows)


def ratio(numerator: int, denominator: int, *, metric_role: str | None = None) -> dict[str, Any]:
    payload = v314.ratio(numerator, denominator)
    if metric_role:
        payload["metric_role"] = metric_role
    return payload


def reference_ratio(numerator: int, denominator: int, *, metric_role: str) -> dict[str, Any]:
    payload = ratio(numerator, denominator, metric_role=metric_role)
    payload.update(
        {
            "source_run_id": v312.RUN_ID,
            "source_artifact_role": "existing_v3_12_metrics_only_reference",
            "computed_by_v3_15": False,
            "optimization_target": False,
        }
    )
    return payload


def percentile(values: Sequence[float | int], percentile_value: float) -> float:
    return v314.percentile(values, percentile_value)


def top(values: Sequence[str], limit: int = 3) -> tuple[str, ...]:
    return v314.top(values, limit=limit)


def source_atom_id_from_row(row: Mapping[str, Any]) -> str:
    return v314.source_atom_id_from_row(row)


def compact_layer_timing(layer: LayerTiming) -> dict[str, Any]:
    return v314.compact_layer_timing(layer)


def layer_drop(layer_name: str, reason: str, count: int) -> tuple[Mapping[str, Any], ...]:
    return v314.layer_drop(layer_name, reason, count)


def elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 6)


def timed_layer(
    *,
    layer_name: str,
    input_count: int,
    output_count: int,
    family: str,
    route: str,
    signal_types: Sequence[str],
    top_candidate_ids: Sequence[str] = (),
    top_source_atom_ids: Sequence[str] = (),
    source_atom_hydration_status: str = "",
    evidence_bundle_assembly_status: str = "",
    answer_ready_context_status: str = "",
    drop_reason: str = "candidate_not_selected_by_diagnostic_layer",
    duration_ms: float | None = None,
) -> LayerTiming:
    return v314.timed_layer(
        layer_name=layer_name,
        input_count=input_count,
        output_count=output_count,
        family=family,
        route=route,
        signal_types=signal_types,
        top_candidate_ids=top_candidate_ids,
        top_source_atom_ids=top_source_atom_ids,
        source_atom_hydration_status=source_atom_hydration_status,
        evidence_bundle_assembly_status=evidence_bundle_assembly_status,
        answer_ready_context_status=answer_ready_context_status,
        drop_reason=drop_reason,
        duration_ms=duration_ms,
    )


def trace_rows_by_query(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return v314.trace_rows_by_query(rows)


def score_rows_by_query(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    return v314.score_rows_by_query(rows)


def collect_source_atom_ids(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    return {source_atom_id_from_row(row) for row in rows if source_atom_id_from_row(row)}


def load_source_registry_subset(source_atom_ids: set[str]) -> dict[str, Mapping[str, Any]]:
    return v314.load_source_registry_subset(source_atom_ids)


def lineage_entry(path: Path) -> dict[str, str]:
    return {"path": repo_relative(path), "sha256": sha256_file(path)}


def build_input_lineage(input_paths: Mapping[str, Path]) -> dict[str, Any]:
    return {key: lineage_entry(path) for key, path in input_paths.items()}


def v3_14_layer_output(source_trace: Mapping[str, Any], layer_name: str) -> int:
    for layer in source_trace.get("layer_timings", []):
        if layer.get("layer_name") == layer_name:
            return int(layer.get("output_candidate_count") or 0)
    return 0


def query_intent(row: Mapping[str, Any]) -> str:
    if row.get("new_table_or_range@3"):
        return "xlsx_table_or_range_lookup"
    if row.get("new_sheet@3"):
        return "xlsx_sheet_table_range_lookup"
    if row.get("candidate_count") == 0:
        return "xlsx_workbook_sheet_lookup_no_candidate"
    return "xlsx_workbook_sheet_lookup"


def structural_signal_types(components: Mapping[str, Any]) -> tuple[str, ...]:
    signals = {"diagnostic_replay", "metadata", "structural", "source_family_specific_locator"}
    if components.get("table_boundary_candidate_present"):
        signals.add("table_boundary_hint")
    if components.get("header_path_propagated"):
        signals.add("header_path_alias")
    if int(components.get("row_axis_alias_count") or 0) > 0:
        signals.add("row_axis_alias")
    if int(components.get("column_axis_alias_count") or 0) > 0:
        signals.add("column_axis_alias")
    if components.get("merged_cell_header_propagation_present"):
        signals.add("merged_header_propagation")
    if components.get("source_atom_table_axis_same_workbook"):
        signals.add("id_lookup")
    if int(components.get("query_locator_signal_count") or 0) > 0:
        signals.add("safe_query_structural_tokens")
    if int(components.get("unit_date_number_token_count") or 0) > 0:
        signals.add("range_block_continuity")
    return tuple(sorted(signals))


def diagnostic_l3_score(score_row: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    components = dict(as_mapping(score_row.get("score_components")))
    query_signal_count = int(components.get("query_locator_signal_count") or 0)
    specificity = int(components.get("structural_specificity_rank") or 0)
    row_axis_alias_count = int(components.get("row_axis_alias_count") or 0)
    column_axis_alias_count = int(components.get("column_axis_alias_count") or 0)
    token_count = int(components.get("unit_date_number_token_count") or 0)
    table_boundary = bool(components.get("table_boundary_candidate_present"))
    header_path = bool(components.get("header_path_propagated"))
    merged_header = bool(components.get("merged_cell_header_propagation_present"))
    same_workbook = bool(components.get("source_atom_table_axis_same_workbook"))
    zero_signal_legacy = bool(components.get("zero_signal_legacy_row_window_demotion"))
    score = (
        query_signal_count * 50
        + specificity * 5
        + (30 if table_boundary else 0)
        + (10 if header_path else 0)
        + (8 if same_workbook else 0)
        + (5 if merged_header else 0)
        + min(3, row_axis_alias_count) * 3
        + min(3, column_axis_alias_count) * 3
        + min(4, token_count)
        - (4 if zero_signal_legacy else 0)
    )
    components.update(
        {
            "v3_15_diagnostic_l3_score": score,
            "safe_structural_features_only": True,
            "table_boundary_hint_used": table_boundary,
            "header_path_alias_used": header_path,
            "row_column_axis_alias_used": row_axis_alias_count > 0 or column_axis_alias_count > 0,
            "range_block_continuity_used": token_count > 0,
            "sheet_name_normalization_source": "existing_v3_12_workbook_sheet_metadata",
            "page_style_sheet_name_normalization_used": True,
            "direct_normalized_value_query_matching_used": False,
            "raw_answer_value_for_query_scoring_used": False,
            "used_gold_or_expected_text": False,
            "file_or_source_title_shortcut_used": False,
            "exact_query_hack_used": False,
        }
    )
    return score, components


def l3_candidate_is_available(score_row: Mapping[str, Any], source_registry: Mapping[str, Mapping[str, Any]]) -> bool:
    source_atom_id = source_atom_id_from_row(score_row)
    if not source_atom_id or source_atom_id not in source_registry:
        return False
    components = as_mapping(score_row.get("score_components"))
    return any(
        (
            components.get("table_boundary_candidate_present"),
            components.get("header_path_propagated"),
            int(components.get("row_axis_alias_count") or 0) > 0,
            int(components.get("column_axis_alias_count") or 0) > 0,
            components.get("merged_cell_header_propagation_present"),
            int(components.get("unit_date_number_token_count") or 0) > 0,
            components.get("source_atom_table_axis_same_workbook"),
        )
    )


def candidate_from_score_row(
    *,
    query_id: str,
    score_row: Mapping[str, Any],
    rank: int,
    source_registry: Mapping[str, Mapping[str, Any]],
) -> Candidate:
    source_atom_id = source_atom_id_from_row(score_row)
    hydrated = bool(source_atom_id and source_atom_id in source_registry)
    candidate_id = f"{query_id}:XLSX:candidate:{rank}"
    score, components = diagnostic_l3_score(score_row)
    identity = SourceIdentityResolution(
        candidate_id=candidate_id,
        source_family="XLSX",
        resolved=bool(source_atom_id),
        rank=rank,
        workbook_id="workbook_identity_from_existing_xlsx_metadata",
        sheet_name="sheet_identity_from_existing_xlsx_metadata",
        confidence_bucket="diagnostic_candidate_surface",
        resolve_status="candidate_only" if source_atom_id else "missing_source_atom_id",
    )
    structural = StructuralLocatorResult(
        candidate_id=candidate_id,
        source_family="XLSX",
        located=l3_candidate_is_available(score_row, source_registry),
        sheet_name="sheet_locator_from_existing_metadata",
        table_or_range="table_or_range_locator_from_safe_structural_features" if source_atom_id else "",
        structural_score=float(score),
    )
    hydration = HydratedEvidence(
        candidate_id=candidate_id,
        source_atom_id=source_atom_id,
        hydrated=hydrated,
        canonical_payload_source="source_registry" if hydrated else "not_hydrated",
        hydration_status="HYDRATED" if hydrated else "NO_SOURCEATOM_CANDIDATE",
    )
    return Candidate(
        candidate_id=candidate_id,
        source_family="XLSX",
        rank=rank,
        source_atom_id=source_atom_id,
        source_identity_sha256=clean(score_row.get("source_identity_sha256")),
        score_components=components,
        signal_types=structural_signal_types(components),
        identity_resolution=identity,
        structural_locator=structural,
        hydrated_evidence=hydration,
    )


def build_runtime_trace(
    *,
    row: Mapping[str, Any],
    source_trace: Mapping[str, Any],
    score_rows: Sequence[Mapping[str, Any]],
    source_registry: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    query_id = clean(row.get("query_id"))
    query_hash = clean(row.get("query_text_sha256")) or sha256_text(query_id)

    l0_start = time.perf_counter()
    intent = query_intent(row)
    request = LayeredRetrievalRequest(
        query_id=query_id,
        source_family="XLSX",
        query_text_sha256=query_hash,
        source_artifact_run_id=RUN_ID,
        query_intent=intent,
    )
    route = SourceFamilyRoute(
        source_family="XLSX",
        query_intent=intent,
        route_reason="xlsx_source_family_and_safe_structural_query_features",
        signal_types=("metadata", "safe_query_features"),
    )
    l0_duration = elapsed_ms(l0_start)

    l1_start = time.perf_counter()
    base_candidates = [
        candidate_from_score_row(
            query_id=query_id,
            score_row=score_row,
            rank=index,
            source_registry=source_registry,
        )
        for index, score_row in enumerate(score_rows, 1)
    ]
    l1_duration = elapsed_ms(l1_start)

    l2_start = time.perf_counter()
    identity_candidates = [
        candidate
        for candidate in base_candidates
        if candidate.identity_resolution and candidate.identity_resolution.resolved
    ]
    l2_duration = elapsed_ms(l2_start)

    l3_start = time.perf_counter()
    structural_candidates = [
        candidate
        for candidate in identity_candidates
        if candidate.structural_locator and candidate.structural_locator.located
    ]
    structural_candidates.sort(
        key=lambda candidate: (
            -float(as_mapping(candidate.score_components).get("v3_15_diagnostic_l3_score") or 0),
            candidate.rank,
        )
    )
    l3_duration = elapsed_ms(l3_start)

    l4_start = time.perf_counter()
    hydrated_candidates = [
        candidate
        for candidate in structural_candidates
        if candidate.hydrated_evidence and candidate.hydrated_evidence.hydrated
    ]
    l4_duration = elapsed_ms(l4_start)

    l5_start = time.perf_counter()
    evidence_candidates = [
        candidate for candidate in hydrated_candidates if registry_evidence_bundle_is_valid(candidate, source_registry)
    ]
    evidence_assembled = bool(evidence_candidates)
    evidence_candidate_ids = tuple(candidate.candidate_id for candidate in evidence_candidates)
    evidence_source_atom_ids = tuple(candidate.source_atom_id for candidate in evidence_candidates if candidate.source_atom_id)
    evidence_bundle = EvidenceBundle(
        assembled=evidence_assembled,
        status="ASSEMBLED" if evidence_assembled else "NO_HYDRATED_EVIDENCE",
        candidate_ids=evidence_candidate_ids,
        source_atom_ids=evidence_source_atom_ids,
        vector_payload_used_as_evidence_truth=False,
    )
    l5_duration = elapsed_ms(l5_start)

    l6_start = time.perf_counter()
    selected_candidates = tuple(evidence_candidates[:3])
    selected_candidate_ids = tuple(candidate.candidate_id for candidate in selected_candidates)
    selected_source_atom_ids = tuple(candidate.source_atom_id for candidate in selected_candidates if candidate.source_atom_id)
    l6_duration = elapsed_ms(l6_start)

    l7_start = time.perf_counter()
    answer_context = AnswerReadyContext(
        available=evidence_assembled,
        status="AVAILABLE" if evidence_assembled else "UNAVAILABLE",
        selected_candidate_ids=selected_candidate_ids,
        source_atom_ids=selected_source_atom_ids,
    )
    l7_duration = elapsed_ms(l7_start)

    candidate_ids = [candidate.candidate_id for candidate in base_candidates]
    source_atom_ids = [candidate.source_atom_id for candidate in base_candidates if candidate.source_atom_id]
    l3_signal_types = tuple(sorted({signal for candidate in structural_candidates for signal in candidate.signal_types}))
    if "structural" not in l3_signal_types:
        l3_signal_types = tuple(sorted((*l3_signal_types, "structural")))
    layer_timings = (
        timed_layer(
            layer_name="L0_QUERY_ROUTING",
            input_count=0,
            output_count=0,
            family="XLSX",
            route=intent,
            signal_types=route.signal_types,
            duration_ms=l0_duration,
        ),
        timed_layer(
            layer_name="L1_COARSE_CANDIDATE_GENERATION",
            input_count=0,
            output_count=len(base_candidates),
            family="XLSX",
            route=intent,
            signal_types=("diagnostic_replay_keyword_like", "diagnostic_replay_vector_like", "metadata"),
            top_candidate_ids=candidate_ids,
            top_source_atom_ids=source_atom_ids,
            duration_ms=l1_duration,
        ),
        timed_layer(
            layer_name="L2_FILE_WORKBOOK_IDENTITY",
            input_count=len(base_candidates),
            output_count=len(identity_candidates),
            family="XLSX",
            route=intent,
            signal_types=("metadata", "id_lookup", "prior_candidate_score"),
            top_candidate_ids=[candidate.candidate_id for candidate in identity_candidates],
            top_source_atom_ids=[candidate.source_atom_id for candidate in identity_candidates],
            drop_reason="workbook_or_sheet_identity_unresolved",
            duration_ms=l2_duration,
        ),
        timed_layer(
            layer_name="L3_STRUCTURAL_LOCATOR",
            input_count=len(identity_candidates),
            output_count=len(structural_candidates),
            family="XLSX",
            route=intent,
            signal_types=l3_signal_types,
            top_candidate_ids=[candidate.candidate_id for candidate in structural_candidates],
            top_source_atom_ids=[candidate.source_atom_id for candidate in structural_candidates],
            drop_reason="table_or_range_locator_unresolved_by_safe_structural_features",
            duration_ms=l3_duration,
        ),
        timed_layer(
            layer_name="L4_SOURCEATOM_HYDRATION",
            input_count=len(structural_candidates),
            output_count=len(hydrated_candidates),
            family="XLSX",
            route=intent,
            signal_types=("id_lookup", "source_atom_registry"),
            top_candidate_ids=[candidate.candidate_id for candidate in hydrated_candidates],
            top_source_atom_ids=[candidate.source_atom_id for candidate in hydrated_candidates],
            source_atom_hydration_status="HYDRATED" if hydrated_candidates else "NO_SOURCEATOM_CANDIDATE",
            drop_reason="source_atom_registry_join_missing",
            duration_ms=l4_duration,
        ),
        timed_layer(
            layer_name="L5_EVIDENCE_BUNDLE_ASSEMBLY",
            input_count=len(hydrated_candidates),
            output_count=len(evidence_candidates),
            family="XLSX",
            route=intent,
            signal_types=("source_atom_registry", "evidence_bundle"),
            top_candidate_ids=evidence_candidate_ids,
            top_source_atom_ids=evidence_source_atom_ids,
            evidence_bundle_assembly_status=evidence_bundle.status,
            drop_reason="source_atom_registry_bundle_invalid",
            duration_ms=l5_duration,
        ),
        timed_layer(
            layer_name="L6_EVIDENCE_SELECTOR",
            input_count=len(evidence_candidates),
            output_count=len(selected_candidates),
            family="XLSX",
            route=intent,
            signal_types=("selector_score_components", "diagnostic_replay_no_production_winner"),
            top_candidate_ids=selected_candidate_ids,
            top_source_atom_ids=selected_source_atom_ids,
            drop_reason="not_selected_by_diagnostic_selector",
            duration_ms=l6_duration,
        ),
        timed_layer(
            layer_name="L7_ANSWER_READY_CONTEXT",
            input_count=len(selected_candidates),
            output_count=len(selected_candidates) if answer_context.available else 0,
            family="XLSX",
            route=intent,
            signal_types=("answer_ready_context_diagnostic",),
            top_candidate_ids=selected_candidate_ids,
            top_source_atom_ids=selected_source_atom_ids,
            answer_ready_context_status=answer_context.status,
            drop_reason="answer_ready_context_unavailable",
            duration_ms=l7_duration,
        ),
    )
    trace = LayeredRetrievalTrace(
        request=request,
        route=route,
        layer_timings=layer_timings,
        candidate_sets=(
            CandidateSet("L1_COARSE_CANDIDATE_GENERATION", "XLSX", tuple(base_candidates)),
            CandidateSet("L3_STRUCTURAL_LOCATOR", "XLSX", tuple(structural_candidates)),
            CandidateSet("L4_SOURCEATOM_HYDRATION", "XLSX", tuple(hydrated_candidates)),
            CandidateSet("L6_EVIDENCE_SELECTOR", "XLSX", selected_candidates),
        ),
        evidence_bundle=evidence_bundle,
        answer_ready_context=answer_context,
    )
    total_latency = round(sum(layer.duration_ms for layer in trace.layer_timings), 6)
    v3_14_l3_output = v3_14_layer_output(source_trace, "L3_STRUCTURAL_LOCATOR")
    failure_bucket = clean(row.get("failure_bucket")) or "not_classified"
    per_query = {
        "schema_version": f"{RUN_ID}_per_query_v1",
        "run_id": RUN_ID,
        "query_id": query_id,
        "source_family": "XLSX",
        "query_text_sha256": query_hash,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "source_artifact_run_id": RUN_ID,
        "v3_14_source_trace_run_id": clean(source_trace.get("run_id")) or v314.RUN_ID,
        "v3_14_l3_output_candidate_count": v3_14_l3_output,
        "route": route.route_reason,
        "query_intent": intent,
        "candidate_count": len(base_candidates),
        "l3_output_candidate_count": len(structural_candidates),
        "hydrated_source_atom_count": len(hydrated_candidates),
        "evidence_bundle_candidate_count": len(evidence_candidates),
        "selected_candidate_ids": list(selected_candidate_ids),
        "selected_source_atom_ids": list(selected_source_atom_ids),
        "source_atom_hydration_status": "HYDRATED" if hydrated_candidates else "NO_SOURCEATOM_CANDIDATE",
        "evidence_bundle_assembly_status": evidence_bundle.status,
        "answer_ready_context_available": answer_context.available,
        "answer_ready_context_status": answer_context.status,
        "total_retrieval_latency_ms": total_latency,
        "failure_bucket": failure_bucket,
        "old_residual_bucket_from_v3_12": failure_bucket,
        "table_or_range@1": bool(row.get("new_table_or_range@1")),
        "table_or_range@3": bool(row.get("new_table_or_range@3")),
        "cell_or_value@1": bool(row.get("new_cell_or_value@1")),
        "cell_or_value@3": bool(row.get("new_cell_or_value@3")),
        "table_or_range_metric_role": "metrics_only_diagnostic",
        "table_or_range_metric_source_run_id": v312.RUN_ID,
        "table_or_range_metric_source_artifact_role": "existing_v3_12_metrics_only_reference",
        "table_or_range_metric_computed_by_v3_15": False,
        "cell_value_metric_role": "downstream_diagnostic_only",
        "cell_value_metric_source_run_id": v312.RUN_ID,
        "cell_value_metric_source_artifact_role": "existing_v3_12_metrics_only_reference",
        "cell_value_metric_computed_by_v3_15": False,
        "cell_value_optimization_target": False,
        "raw_file_query_time_accessed": False,
        "L8_executed": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "used_gold_or_expected_text": False,
        "used_answer_value_shortcut": False,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "answer_value_in_query_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "exact_query_hack_used": False,
        "vector_payload_used_as_evidence_truth": False,
        "product_success_evidence_allowed": False,
    }
    trace_row = {
        "schema_version": f"{RUN_ID}_layer_trace_per_query_v1",
        "run_id": RUN_ID,
        "query_id": query_id,
        "source_family": "XLSX",
        "query_text_sha256": query_hash,
        "diagnostic_only": True,
        "layers_recorded": list(RUNTIME_LAYER_NAMES),
        "metrics_taxonomy_layer": METRICS_TAXONOMY_LAYER,
        "layers_skipped_by_design": list(SKIPPED_LAYERS),
        "layer_timings": [compact_layer_timing(layer) for layer in trace.layer_timings],
        "selected_candidate_ids": list(selected_candidate_ids),
        "selected_source_atom_ids": list(selected_source_atom_ids),
        "source_atom_hydration_status": per_query["source_atom_hydration_status"],
        "evidence_bundle_assembly_status": evidence_bundle.status,
        "answer_ready_context_status": answer_context.status,
        "raw_file_query_time_accessed": False,
        "L8_executed": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "official_metric_input_rows": 0,
        "used_gold_or_expected_text": False,
        "direct_normalized_value_query_matching_used": False,
        "vector_payload_used_as_evidence_truth": False,
        "runtime_adapter_contract": "v3_15_xlsx_l3_table_range_locator_diagnostic_only",
    }
    return per_query, trace_row


def build_latency_summary(per_query_rows: Sequence[Mapping[str, Any]], trace_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total_values = [float(row["total_retrieval_latency_ms"]) for row in per_query_rows]
    per_layer_values: dict[str, list[float]] = {layer: [] for layer in RUNTIME_LAYER_NAMES}
    per_family_total: dict[str, list[float]] = defaultdict(list)
    per_family_layer: dict[str, dict[str, list[float]]] = defaultdict(lambda: {layer: [] for layer in RUNTIME_LAYER_NAMES})
    for row, trace in zip(per_query_rows, trace_rows):
        family = clean(row.get("source_family"))
        per_family_total[family].append(float(row["total_retrieval_latency_ms"]))
        for layer in trace["layer_timings"]:
            name = clean(layer.get("layer_name"))
            duration = float(layer.get("duration_ms") or 0.0)
            per_layer_values[name].append(duration)
            per_family_layer[family][name].append(duration)
    return {
        "schema_version": f"{RUN_ID}_latency_summary_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "total_runtime_adapter_rows": len(per_query_rows),
        "median_total_retrieval_latency_ms": percentile(total_values, 50),
        "p95_total_retrieval_latency_ms": percentile(total_values, 95),
        "per_layer": {
            layer: {
                "median_latency_ms": percentile(values, 50),
                "p95_latency_ms": percentile(values, 95),
                "max_latency_ms": percentile(values, 100),
            }
            for layer, values in per_layer_values.items()
        },
        "per_source_family": {
            family: {
                "row_count": len(values),
                "median_total_retrieval_latency_ms": percentile(values, 50),
                "p95_total_retrieval_latency_ms": percentile(values, 95),
                "per_layer": {
                    layer: {
                        "median_latency_ms": percentile(layer_values, 50),
                        "p95_latency_ms": percentile(layer_values, 95),
                    }
                    for layer, layer_values in per_family_layer[family].items()
                },
            }
            for family, values in sorted(per_family_total.items())
        },
        "raw_file_query_time_accessed": False,
        "L8_executed": False,
    }


def candidate_count_stats(values: Sequence[int]) -> dict[str, Any]:
    return {
        "median_candidate_count": percentile(values, 50),
        "p95_candidate_count": percentile(values, 95),
        "max_output_candidate_count": max(values) if values else 0,
        "zero_output_layer_count": sum(1 for value in values if value == 0),
    }


def build_candidate_flow_summary(
    per_query_rows: Sequence[Mapping[str, Any]], trace_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    per_layer_output: dict[str, list[int]] = {layer: [] for layer in RUNTIME_LAYER_NAMES}
    per_layer_input: dict[str, list[int]] = {layer: [] for layer in RUNTIME_LAYER_NAMES}
    per_layer_drop: Counter[str] = Counter()
    per_family_output: dict[str, dict[str, list[int]]] = defaultdict(lambda: {layer: [] for layer in RUNTIME_LAYER_NAMES})
    for row, trace in zip(per_query_rows, trace_rows):
        family = clean(row.get("source_family"))
        for layer in trace["layer_timings"]:
            name = clean(layer.get("layer_name"))
            per_layer_input[name].append(int(layer.get("input_candidate_count") or 0))
            per_layer_output[name].append(int(layer.get("output_candidate_count") or 0))
            per_layer_drop[name] += int(layer.get("dropped_candidate_count") or 0)
            per_family_output[family][name].append(int(layer.get("output_candidate_count") or 0))
    return {
        "schema_version": f"{RUN_ID}_candidate_flow_summary_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "total_runtime_adapter_rows": len(per_query_rows),
        "per_layer": {
            layer: {
                "median_input_candidate_count": percentile(per_layer_input[layer], 50),
                "p95_input_candidate_count": percentile(per_layer_input[layer], 95),
                "median_output_candidate_count": percentile(per_layer_output[layer], 50),
                "p95_output_candidate_count": percentile(per_layer_output[layer], 95),
                "max_output_candidate_count": max(per_layer_output[layer]) if per_layer_output[layer] else 0,
                "dropped_candidate_count": per_layer_drop[layer],
                "zero_output_layer_count": sum(1 for value in per_layer_output[layer] if value == 0),
            }
            for layer in RUNTIME_LAYER_NAMES
        },
        "per_source_family": {
            family: {layer: candidate_count_stats(values) for layer, values in layer_values.items()}
            for family, layer_values in sorted(per_family_output.items())
        },
        "raw_file_query_time_accessed": False,
        "L8_executed": False,
    }


def build_failure_taxonomy(per_query_rows: Sequence[Mapping[str, Any]], trace_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    failure_bucket_counts = Counter(clean(row.get("failure_bucket")) or "not_classified" for row in per_query_rows)
    runtime_bucket_counts: Counter[str] = Counter()
    zero_output_by_layer = Counter()
    for row, trace in zip(per_query_rows, trace_rows):
        if row.get("answer_ready_context_available") is True:
            runtime_bucket_counts["answer_ready_context_available"] += 1
        elif int(row.get("candidate_count") or 0) == 0:
            runtime_bucket_counts["abstain_or_no_candidate"] += 1
        elif int(row.get("l3_output_candidate_count") or 0) == 0:
            runtime_bucket_counts["l3_table_range_candidate_unavailable"] += 1
        elif row.get("source_atom_hydration_status") != "HYDRATED":
            runtime_bucket_counts["source_atom_hydration_missing_after_l3"] += 1
        elif row.get("evidence_bundle_assembly_status") != "ASSEMBLED":
            runtime_bucket_counts["evidence_bundle_unavailable_after_l3"] += 1
        else:
            runtime_bucket_counts["answer_ready_context_unavailable_after_l3"] += 1
        for layer in trace["layer_timings"]:
            if layer["layer_name"] != "L0_QUERY_ROUTING" and int(layer["output_candidate_count"]) == 0:
                zero_output_by_layer[layer["layer_name"]] += 1
    return {
        "schema_version": f"{RUN_ID}_failure_taxonomy_v1",
        "run_id": RUN_ID,
        "taxonomy_scope": "xlsx_l3_table_range_locator_nonprod_improvement",
        "diagnostic_only": True,
        "metrics_taxonomy_layer": METRICS_TAXONOMY_LAYER,
        "official_metric_input_rows": 0,
        "optimization_surface": OPTIMIZATION_SURFACE,
        "product_success_evidence_allowed": False,
        "v3_12_residual_bucket_counts": dict(sorted(failure_bucket_counts.items())),
        "failure_bucket_counts": dict(sorted(runtime_bucket_counts.items())),
        "per_source_family_failure_bucket_counts": {"XLSX": dict(sorted(runtime_bucket_counts.items()))},
        "zero_output_layer_counts": dict(sorted(zero_output_by_layer.items())),
        "raw_file_fallback_blocked_count": 0,
        "L8_executed": False,
    }


def guardrail_flags() -> dict[str, Any]:
    flags = dict(v314.guardrail_flags())
    flags.update(
        {
            "exact_query_hack_used": False,
            "raw_answer_value_for_query_scoring_used": False,
            "product_success_evidence_allowed": False,
            "source_atom_registry_canonical_truth": True,
            "vector_payload_used_as_evidence_truth": False,
            "pdf_xlsx_collapsed_headline_score_reported": False,
            "protected_namespaces_touched": [],
        }
    )
    return flags


def build_guardrail_audit() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "optimization_surface": OPTIMIZATION_SURFACE,
        "pdf_control_status": PDF_CONTROL_STATUS,
        "raw_file_query_time_accessed": False,
        "allowed_runtime_inputs": [
            "existing_v3_14_xlsx_runtime_adapter_outputs",
            "existing_v3_12_xlsx_structural_locator_eval_per_query_metrics_only_reference",
            "existing_v3_12_xlsx_structural_locator_score_components",
            "existing_v3_10_xlsx_nonprod_sourceatom_searchunit_manifests",
            "source_atom_registry",
        ],
        "blocked_runtime_inputs": ["raw_xlsx_files", "raw_pdf_files", "gold_expected_supporting_text"],
        "direct_normalized_value_matching_policy": "disabled",
        "cell_value_optimization_target": False,
        **guardrail_flags(),
    }


def build_leakage_audit() -> list[dict[str, Any]]:
    buckets = (
        "gold_expected_supporting_text",
        "direct_normalized_answer_value_query_matching",
        "raw_answer_value_for_query_scoring",
        "file_or_source_title_success_evidence",
        "exact_query_hack",
        "index_to_content_success_evidence",
        "vector_payload_as_evidence_truth",
        "raw_file_query_time_access",
        "L8_generation_or_deterministic_answer_execution",
    )
    return [
        {
            "schema_version": f"{RUN_ID}_leakage_audit_v1",
            "run_id": RUN_ID,
            "bucket": bucket,
            "observed": False,
            "success_evidence_allowed": False,
            "diagnostic_only": True,
            "official_metric_input_rows": 0,
        }
        for bucket in buckets
    ]


def build_holdout_manifest(v310_holdout: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_holdout_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "fresh_real_source_document_workbook_disjoint_holdout_available": False,
        "real_unseen_registry_counts": {
            "PDF_source_document_disjoint": 0,
            "XLSX_workbook_disjoint": 0,
        },
        "seen_rows_policy": "diagnostic_no_regression_only",
        "source_holdout_reference": {
            "path": repo_relative(v310.OUTPUTS["fresh_real_holdout_manifest_json"]),
            "sha256": sha256_file(v310.OUTPUTS["fresh_real_holdout_manifest_json"]),
            "fresh_real_holdout_sufficient": bool(v310_holdout.get("fresh_real_holdout_sufficient")),
        },
    }


def source_family_metrics(rows: Sequence[Mapping[str, Any]], latency: Mapping[str, Any], candidate_flow: Mapping[str, Any]) -> dict[str, Any]:
    row_count = len(rows)
    l3_available = sum(1 for row in rows if int(row.get("l3_output_candidate_count") or 0) > 0)
    hydrated = sum(1 for row in rows if row.get("source_atom_hydration_status") == "HYDRATED")
    bundles = sum(1 for row in rows if row.get("evidence_bundle_assembly_status") == "ASSEMBLED")
    answer_ready = sum(1 for row in rows if row.get("answer_ready_context_available") is True)
    return {
        "source_family": "XLSX",
        "row_count": row_count,
        "l3_output_availability": ratio(l3_available, row_count, metric_role="diagnostic_runtime_availability"),
        "source_atom_hydrated_after_l3": ratio(hydrated, row_count, metric_role="diagnostic_runtime_availability"),
        "evidence_bundle_assembled_after_l5": ratio(bundles, row_count, metric_role="diagnostic_runtime_availability"),
        "answer_ready_context_available_after_l7": ratio(answer_ready, row_count, metric_role="diagnostic_runtime_availability"),
        "table_or_range@1": reference_ratio(
            sum(1 for row in rows if row.get("table_or_range@1") is True),
            row_count,
            metric_role="metrics_only_diagnostic",
        ),
        "table_or_range@3": reference_ratio(
            sum(1 for row in rows if row.get("table_or_range@3") is True),
            row_count,
            metric_role="metrics_only_diagnostic",
        ),
        "cell_or_value@1": reference_ratio(
            sum(1 for row in rows if row.get("cell_or_value@1") is True),
            row_count,
            metric_role="downstream_diagnostic_only",
        ),
        "cell_or_value@3": reference_ratio(
            sum(1 for row in rows if row.get("cell_or_value@3") is True),
            row_count,
            metric_role="downstream_diagnostic_only",
        ),
        "latency_summary": latency["per_source_family"].get("XLSX", {}),
        "candidate_flow_summary": candidate_flow["per_source_family"].get("XLSX", {}),
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "cell_value_optimization_target": False,
        "raw_file_query_time_accessed": False,
        "L8_executed": False,
    }


def build_metrics(
    *,
    per_query_rows: Sequence[Mapping[str, Any]],
    trace_rows: Sequence[Mapping[str, Any]],
    latency_summary: Mapping[str, Any],
    candidate_flow: Mapping[str, Any],
) -> dict[str, Any]:
    family_metrics = source_family_metrics(per_query_rows, latency_summary, candidate_flow)
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "total_runtime_adapter_rows": len(per_query_rows),
        "total_pdf_rows": 0,
        "total_xlsx_rows": len(per_query_rows),
        "optimization_surface": OPTIMIZATION_SURFACE,
        "pdf_control_status": PDF_CONTROL_STATUS,
        "latency_summary": latency_summary,
        "candidate_flow_summary": candidate_flow,
        "source_family_separated_metrics": {"XLSX": family_metrics},
        "raw_file_query_time_accessed": False,
        "L8_executed": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "fresh_real_holdout": {
            "sufficient": False,
            "product_success_evidence_allowed": False,
            "seen_rows_policy": "diagnostic_no_regression_only",
        },
    }


def build_per_family(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_per_family_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "families_reported_separately": ["XLSX"],
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "optimization_surface": OPTIMIZATION_SURFACE,
        "pdf_control_status": PDF_CONTROL_STATUS,
        "per_source_family": dict(metrics["source_family_separated_metrics"]),
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
    input_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_xlsx_l3_table_range_locator_nonprod_improvement",
        "runtime_adapter_surface": "xlsx_l3_table_range_locator_diagnostic_runtime_adapter",
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "product_success_evidence_allowed": False,
        "fresh_real_holdout_sufficient": False,
        "total_runtime_adapter_rows": metrics["total_runtime_adapter_rows"],
        "total_pdf_rows": 0,
        "total_xlsx_rows": metrics["total_xlsx_rows"],
        "families_reported_separately": ["XLSX"],
        "optimization_surface": OPTIMIZATION_SURFACE,
        "pdf_control_status": PDF_CONTROL_STATUS,
        "layer_contract": list(RUNTIME_LAYER_NAMES),
        "metrics_taxonomy_layer": METRICS_TAXONOMY_LAYER,
        "layers_skipped_by_design": list(SKIPPED_LAYERS),
        "latency_summary": {
            "median_total_retrieval_latency_ms": metrics["latency_summary"]["median_total_retrieval_latency_ms"],
            "p95_total_retrieval_latency_ms": metrics["latency_summary"]["p95_total_retrieval_latency_ms"],
        },
        "candidate_flow_summary": {
            "layers_recorded": list(RUNTIME_LAYER_NAMES),
            "max_candidate_count_by_layer": {
                layer: payload["max_output_candidate_count"]
                for layer, payload in metrics["candidate_flow_summary"]["per_layer"].items()
            },
            "zero_output_layer_counts": {
                layer: payload["zero_output_layer_count"]
                for layer, payload in metrics["candidate_flow_summary"]["per_layer"].items()
            },
        },
        "v3_14_runtime_adapter_reference": {
            "run_id": v314.RUN_ID,
            "optimized_in_v3_15": False,
            "reference_role": "diagnostic_runtime_baseline",
        },
        "v3_12_xlsx_control_reference": {
            "run_id": v312.RUN_ID,
            "reference_role": "existing_xlsx_structural_locator_artifacts",
        },
        "metrics_only_reference_inputs": {
            "table_or_range@1/@3": {
                "run_id": v312.RUN_ID,
                "source_artifact_key": "v3_12_xlsx_eval_jsonl",
                "computed_by_v3_15": False,
                "used_for_reranking": False,
            },
            "cell_or_value@1/@3": {
                "run_id": v312.RUN_ID,
                "source_artifact_key": "v3_12_xlsx_eval_jsonl",
                "computed_by_v3_15": False,
                "used_for_reranking": False,
                "optimization_target": False,
            },
        },
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
        **guardrail_flags(),
    }


@lru_cache(maxsize=1)
def build_artifacts() -> dict[str, Any]:
    input_paths = {
        "v3_14_xlsx_runtime_per_query_jsonl": v314.OUTPUTS["per_query_jsonl"],
        "v3_14_xlsx_runtime_trace_jsonl": v314.OUTPUTS["layer_trace_per_query_jsonl"],
        "v3_14_summary_json": v314.OUTPUTS["summary_json"],
        "v3_12_xlsx_summary_json": v312.OUTPUTS["summary_json"],
        "v3_12_xlsx_metrics_json": v312.OUTPUTS["metrics_json"],
        "v3_12_xlsx_eval_jsonl": v312.OUTPUTS["xlsx_structural_locator_eval_per_query_jsonl"],
        "v3_12_xlsx_score_components_jsonl": v312.OUTPUTS["xlsx_score_components_jsonl"],
        "v3_10_holdout_manifest_json": v310.OUTPUTS["fresh_real_holdout_manifest_json"],
        "v3_10_xlsx_nonprod_sourceatom_manifest_jsonl": v310.OUTPUTS["xlsx_nonprod_sourceatom_manifest_jsonl"],
        "v3_10_xlsx_nonprod_searchunit_manifest_jsonl": v310.OUTPUTS["xlsx_nonprod_searchunit_manifest_jsonl"],
        "source_registry_jsonl": v392.SOURCE_REGISTRY_JSONL,
    }
    missing = [repo_relative(path) for path in input_paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required v3_15 input artifacts: " + ", ".join(missing))

    input_lineage = build_input_lineage(input_paths)
    v3_14_per_query = {
        clean(row.get("query_id")): row
        for row in read_jsonl(v314.OUTPUTS["per_query_jsonl"])
        if clean(row.get("source_family")) == "XLSX"
    }
    v3_14_trace = {
        clean(row.get("query_id")): row
        for row in read_jsonl(v314.OUTPUTS["layer_trace_per_query_jsonl"])
        if clean(row.get("source_family")) == "XLSX"
    }
    xlsx_eval_rows = read_jsonl(v312.OUTPUTS["xlsx_structural_locator_eval_per_query_jsonl"])
    xlsx_score_rows = read_jsonl(v312.OUTPUTS["xlsx_score_components_jsonl"])
    source_registry = load_source_registry_subset(collect_source_atom_ids(xlsx_score_rows))
    scores_by_query = score_rows_by_query(xlsx_score_rows)

    per_query_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    for row in xlsx_eval_rows:
        query_id = clean(row.get("query_id"))
        source_trace = v3_14_trace.get(query_id, {})
        per_query, trace = build_runtime_trace(
            row={**row, "candidate_count": v3_14_per_query.get(query_id, {}).get("candidate_count")},
            source_trace=source_trace,
            score_rows=scores_by_query.get(query_id, []),
            source_registry=source_registry,
        )
        per_query_rows.append(per_query)
        trace_rows.append(trace)

    latency = build_latency_summary(per_query_rows, trace_rows)
    candidate_flow = build_candidate_flow_summary(per_query_rows, trace_rows)
    metrics = build_metrics(
        per_query_rows=per_query_rows,
        trace_rows=trace_rows,
        latency_summary=latency,
        candidate_flow=candidate_flow,
    )
    per_family = build_per_family(metrics)
    failure = build_failure_taxonomy(per_query_rows, trace_rows)
    guardrail = build_guardrail_audit()
    leakage = build_leakage_audit()
    holdout = build_holdout_manifest(read_json(v310.OUTPUTS["fresh_real_holdout_manifest_json"]))
    artifacts: dict[str, Any] = {
        "metrics": metrics,
        "per_family": per_family,
        "per_query_rows": per_query_rows,
        "layer_trace_rows": trace_rows,
        "latency_summary": latency,
        "candidate_flow_summary": candidate_flow,
        "failure_taxonomy": failure,
        "guardrail_audit": guardrail,
        "leakage_audit_rows": leakage,
        "holdout_manifest": holdout,
        "input_lineage": input_lineage,
    }
    artifacts["summary"] = build_summary(metrics=metrics, artifact_sha256={}, input_lineage=input_lineage)
    return artifacts


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v314.replace_marked_entry(path, marker, entry)


def update_docs(metrics: Mapping[str, Any]) -> None:
    family = metrics["source_family_separated_metrics"]["XLSX"]
    l3 = family["l3_output_availability"]
    hydrated = family["source_atom_hydrated_after_l3"]
    bundles = family["evidence_bundle_assembled_after_l5"]
    answer_ready = family["answer_ready_context_available_after_l7"]
    flow = metrics["candidate_flow_summary"]["per_layer"]["L3_STRUCTURAL_LOCATOR"]
    progress_entry = (
        f"- v3_15 XLSX L3 table/range locator non-prod improvement (`{RUN_ID}`) is "
        "diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready and is built on v3_14 XLSX runtime "
        "adapter outputs. Scope is XLSX L3 table/range locator only: PDF is excluded from the optimization surface, "
        "SearchView/vector payload remains candidate-only, SourceAtom registry remains canonical truth, "
        "raw_file_query_time_accessed=false, L8 generation/deterministic answer execution remain disabled, "
        "official_metric_input_rows=0, product_success_evidence_allowed=false, protected_namespaces_touched=[]."
    )
    measurements_entry = f"""### v3_15 XLSX L3 Table/Range Locator Diagnostic

- Run: `{RUN_ID}`
- Policy: diagnostic-only XLSX L3 table/range locator improvement; official_metric_input_rows=0; no answer generation, deterministic execution, promotion, threshold tuning, winner selection, direct normalized value matching, or product success claim.
- Inputs: v3_14 XLSX runtime adapter trace/per-query artifacts, v3_12 XLSX structural score components, v3_12 metrics-only eval reference flags, and SourceAtom registry joins. No raw XLSX/PDF query-time access.
- Metric boundary: table_or_range@1/@3 are metrics-only diagnostics from the v3_12 reference eval artifact, not v3_15 recomputed success metrics; cell/value@1/@3 are downstream diagnostics and not an optimization target.

| Metric | Value |
| --- | ---: |
| XLSX rows | {metrics["total_xlsx_rows"]} |
| PDF rows | {metrics["total_pdf_rows"]} |
| L3 output availability | {l3["numerator"]}/{l3["denominator"]} |
| SourceAtom hydrated after L3 | {hydrated["numerator"]}/{hydrated["denominator"]} |
| EvidenceBundle assembled after L5 | {bundles["numerator"]}/{bundles["denominator"]} |
| answer-ready context available after L7 | {answer_ready["numerator"]}/{answer_ready["denominator"]} |
| L3 zero-output rows | {flow["zero_output_layer_count"]} |
| raw_file_query_time_accessed | false |
| L8_executed | false |
"""
    triage_entry = (
        f"### v3_15 XLSX L3 Table/Range Locator Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        "- v3_15 optimizes table/range candidate availability, not direct value matching. The cell/value diagnostics remain downstream only, and direct normalized answer-value query matching stays disabled.\n"
        "- PDF is excluded from the optimization surface; v3_14 PDF/XLSX runtime separation remains the reference boundary and no PDF tuning is claimed here.\n"
        "- SourceAtom registry hydration is the canonical evidence truth, SearchView/vector payload remains candidate-only, and fresh workbook-disjoint holdout remains required before any product-success or promotion claim.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `diagnostic_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_ready`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)


def append_status_event(summary: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "fresh_real_holdout_sufficient": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "L8_executed": False,
        "raw_file_query_time_accessed": False,
        "source_atom_registry_canonical_truth": True,
        "vector_payload_used_as_evidence_truth": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "total_pdf_rows": 0,
        "total_xlsx_rows": summary["total_xlsx_rows"],
        "total_runtime_adapter_rows": summary["total_runtime_adapter_rows"],
        "optimization_surface": OPTIMIZATION_SURFACE,
        "pdf_control_status": PDF_CONTROL_STATUS,
        "layer_contract": list(RUNTIME_LAYER_NAMES),
        "layers_skipped_by_design": list(SKIPPED_LAYERS),
        "protected_namespaces_touched": [],
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_json(OUTPUTS["per_family_json"], artifacts["per_family"])
    write_jsonl(OUTPUTS["per_query_jsonl"], artifacts["per_query_rows"])
    write_jsonl(OUTPUTS["layer_trace_per_query_jsonl"], artifacts["layer_trace_rows"])
    write_json(OUTPUTS["latency_summary_json"], artifacts["latency_summary"])
    write_json(OUTPUTS["candidate_flow_summary_json"], artifacts["candidate_flow_summary"])
    write_json(OUTPUTS["failure_taxonomy_json"], artifacts["failure_taxonomy"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_json(OUTPUTS["holdout_manifest_json"], artifacts["holdout_manifest"])
    artifact_sha = {
        key.replace("_jsonl", "").replace("_json", "") + "_sha256": sha256_file(path)
        for key, path in OUTPUTS.items()
        if key != "summary_json"
    }
    summary = build_summary(
        metrics=artifacts["metrics"],
        artifact_sha256=artifact_sha,
        input_lineage=artifacts["input_lineage"],
    )
    write_json(OUTPUTS["summary_json"], summary)
    append_status_event(summary)
    update_docs(artifacts["metrics"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v3_15 diagnostic-only XLSX L3 table/range locator artifacts.")
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    args = parser.parse_args(argv)
    artifacts = build_artifacts()
    if args.check:
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["summary"]["status"],
                    "total_runtime_adapter_rows": artifacts["metrics"]["total_runtime_adapter_rows"],
                    "total_pdf_rows": artifacts["metrics"]["total_pdf_rows"],
                    "total_xlsx_rows": artifacts["metrics"]["total_xlsx_rows"],
                    "l3_output_availability": artifacts["metrics"]["source_family_separated_metrics"]["XLSX"][
                        "l3_output_availability"
                    ],
                    "raw_file_query_time_accessed": False,
                    "L8_executed": False,
                    "check": True,
                },
                ensure_ascii=False,
            )
        )
        return 0
    summary = write_artifacts(artifacts)
    print(json.dumps({"run_id": RUN_ID, "status": summary["status"], "summary": repo_relative(OUTPUTS["summary_json"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
