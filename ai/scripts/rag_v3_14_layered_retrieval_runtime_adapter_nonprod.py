from __future__ import annotations

import argparse
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
import rag_v3_13_pdf_file_identity_structural_locator_nonprod_alignment as v313


ROOT = v392.ROOT
if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))
if str(ROOT / "ai" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))

from eval.harness import rag_diagnostic_common as diagnostic_common  # noqa: E402
from eval.harness import rag_layered_runtime_trace as layered_trace  # noqa: E402

from app.capabilities.rag.source_registry import assemble_evidence_bundle


RUN_ID = "official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod"
REPORT_DIR = v392.REPORT_DIR
STATUS_JSONL = v392.STATUS_JSONL
PROGRESS_DOC = v392.PROGRESS_DOC
MEASUREMENTS_DOC = v392.MEASUREMENTS_DOC
TRIAGE_DOC = v392.TRIAGE_DOC

STATUS = "DIAGNOSTIC_V3_14_LAYERED_RETRIEVAL_RUNTIME_ADAPTER_NONPROD_READY"
EVENT_TYPE = "diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod"
RUNTIME_LAYER_NAMES = (
    "L0_QUERY_ROUTING",
    "L1_COARSE_CANDIDATE_GENERATION",
    "L2_FILE_WORKBOOK_IDENTITY",
    "L3_STRUCTURAL_LOCATOR",
    "L4_SOURCEATOM_HYDRATION",
    "L5_EVIDENCE_BUNDLE_ASSEMBLY",
    "L6_EVIDENCE_SELECTOR",
    "L7_ANSWER_READY_CONTEXT",
)
METRICS_TAXONOMY_LAYER = "L9_METRICS_FAILURE_TAXONOMY"
SKIPPED_LAYERS = ("L8_GENERATION_OR_DETERMINISTIC_EXECUTION",)
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


LayeredRetrievalRequest = layered_trace.LayeredRetrievalRequest
SourceFamilyRoute = layered_trace.SourceFamilyRoute
SourceIdentityResolution = layered_trace.SourceIdentityResolution
StructuralLocatorResult = layered_trace.StructuralLocatorResult
HydratedEvidence = layered_trace.HydratedEvidence
EvidenceBundle = layered_trace.EvidenceBundle
AnswerReadyContext = layered_trace.AnswerReadyContext
LayerDropReason = layered_trace.LayerDropReason
Candidate = layered_trace.Candidate
CandidateSet = layered_trace.CandidateSet
LayerTiming = layered_trace.LayerTiming
LayeredRetrievalTrace = layered_trace.LayeredRetrievalTrace

as_mapping = layered_trace.as_mapping
jsonable = layered_trace.jsonable
top = layered_trace.top
layer_drop = layered_trace.layer_drop
timed_layer = layered_trace.timed_layer
compact_layer_timing = layered_trace.compact_layer_timing
clean = diagnostic_common.clean
utc_now = diagnostic_common.utc_now
sha256_file = diagnostic_common.sha256_file
sha256_text = diagnostic_common.sha256_text
read_json = diagnostic_common.read_json
read_jsonl = diagnostic_common.read_jsonl
write_json = diagnostic_common.write_json
write_jsonl = diagnostic_common.write_jsonl
artifact_exists = diagnostic_common.artifact_exists
artifact_is_file = diagnostic_common.artifact_is_file


def repo_relative(path: Path) -> str:
    return diagnostic_common.repo_relative(path, root=ROOT)


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator if denominator else None}


def percentile(values: Sequence[float | int], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return round(ordered[0], 6)
    rank = (len(ordered) - 1) * (percentile_value / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1.0 - weight) + ordered[upper] * weight, 6)


def source_atom_id_from_row(row: Mapping[str, Any]) -> str:
    return clean(row.get("source_atom_id") or row.get("source_atom_id_original"))


def infer_signal_types(source_family: str, score_components: Mapping[str, Any]) -> tuple[str, ...]:
    signals = {"diagnostic_replay"}
    if source_family == "PDF":
        signals.update({"metadata", "structural"})
        if score_components.get("retrieval_best_rank") is not None:
            signals.add("diagnostic_replay_vector_like")
        if score_components.get("query_file_mention_match") is not None:
            signals.add("diagnostic_replay_keyword_like")
        if score_components.get("source_registry_metadata"):
            signals.add("id_lookup")
    elif source_family == "XLSX":
        signals.update({"metadata", "structural", "diagnostic_replay_keyword_like"})
        if score_components.get("source_atom_table_axis_same_workbook") is not None:
            signals.add("id_lookup")
        if score_components.get("table_boundary_candidate_present"):
            signals.add("structural_table_boundary")
    return tuple(sorted(signals))


def source_identity_resolution(
    *,
    query_id: str,
    source_family: str,
    row: Mapping[str, Any],
    score_row: Mapping[str, Any],
    rank: int,
) -> SourceIdentityResolution:
    candidate_id = f"{query_id}:{source_family}:candidate:{rank}"
    if source_family == "PDF":
        components = as_mapping(score_row.get("score_components"))
        return SourceIdentityResolution(
            candidate_id=candidate_id,
            source_family=source_family,
            resolved=bool(row.get("file_resolve@3") or row.get("file_resolve@1") or source_atom_id_from_row(score_row)),
            rank=rank,
            document_version_id_sha256=clean(score_row.get("document_version_id_sha256")),
            source_identity_sha256=clean(score_row.get("source_identity_sha256")),
            confidence_bucket=clean(row.get("rank1_confidence_bucket") or components.get("confidence_bucket")),
            resolve_status=clean(row.get("resolve_status")),
        )
    return SourceIdentityResolution(
        candidate_id=candidate_id,
        source_family=source_family,
        resolved=bool(row.get("new_sheet@3") or row.get("new_table_or_range@3") or source_atom_id_from_row(score_row)),
        rank=rank,
        workbook_id="workbook_identity_from_v3_12_metadata",
        sheet_name="sheet_identity_from_v3_12_metadata" if row.get("new_sheet@3") else "",
        resolve_status="resolved" if row.get("new_sheet@3") else "candidate_only",
    )


def structural_locator_result(
    *,
    query_id: str,
    source_family: str,
    row: Mapping[str, Any],
    score_row: Mapping[str, Any],
    rank: int,
) -> StructuralLocatorResult:
    candidate_id = f"{query_id}:{source_family}:candidate:{rank}"
    if source_family == "PDF":
        return StructuralLocatorResult(
            candidate_id=candidate_id,
            source_family=source_family,
            located=bool(score_row.get("bbox_present") or row.get("bbox_candidate_count")),
            page=int(score_row["page"]) if score_row.get("page") is not None else None,
            bbox_present=bool(score_row.get("bbox_present")),
            same_page_bounded_window=bool(score_row.get("same_page_bounded_evidence_window_candidate")),
        )
    return StructuralLocatorResult(
        candidate_id=candidate_id,
        source_family=source_family,
        located=bool(row.get("new_table_or_range@3") or row.get("new_cell_or_value@3")),
        sheet_name="sheet_locator_from_v3_12",
        table_or_range="table_or_range_locator_from_v3_12" if row.get("new_table_or_range@3") else "",
        cell="cell_locator_from_v3_12" if row.get("new_cell_or_value@3") else "",
        structural_score=float(score_row["structural_score"]) if score_row.get("structural_score") is not None else None,
    )


def candidate_from_score_row(
    *,
    query_id: str,
    source_family: str,
    row: Mapping[str, Any],
    score_row: Mapping[str, Any],
    rank: int,
    source_registry: Mapping[str, Mapping[str, Any]],
) -> Candidate:
    source_atom_id = source_atom_id_from_row(score_row)
    hydrated = bool(source_atom_id and source_atom_id in source_registry)
    candidate_id = f"{query_id}:{source_family}:candidate:{rank}"
    components = dict(as_mapping(score_row.get("score_components")))
    identity = source_identity_resolution(
        query_id=query_id,
        source_family=source_family,
        row=row,
        score_row=score_row,
        rank=rank,
    )
    structural = structural_locator_result(
        query_id=query_id,
        source_family=source_family,
        row=row,
        score_row=score_row,
        rank=rank,
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
        source_family=source_family,
        rank=rank,
        source_atom_id=source_atom_id,
        source_identity_sha256=clean(score_row.get("source_identity_sha256")),
        score_components=components,
        signal_types=infer_signal_types(source_family, components),
        identity_resolution=identity,
        structural_locator=structural,
        hydrated_evidence=hydration,
    )


def registry_evidence_bundle_is_valid(
    candidate: Candidate, source_registry: Mapping[str, Mapping[str, Any]]
) -> bool:
    if not candidate.source_atom_id:
        return False
    result = assemble_evidence_bundle(
        candidate.source_atom_id,
        source_registry=source_registry,
        mode="runtime_evidence",
        search_view_id=candidate.search_view_id or None,
    )
    return bool(result.get("valid"))


def score_rows_by_query(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[clean(row.get("query_id"))].append(row)
    for query_rows in grouped.values():
        query_rows.sort(
            key=lambda item: int(item.get("candidate_rank") or item.get("candidate_rank_old") or len(query_rows) + 1)
        )
    return grouped


def trace_rows_by_query(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {clean(row.get("query_id")): row for row in rows}


def collect_source_atom_ids(*row_groups: Sequence[Mapping[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for rows in row_groups:
        for row in rows:
            source_atom_id = source_atom_id_from_row(row)
            if source_atom_id:
                ids.add(source_atom_id)
    return ids


def load_source_registry_subset(source_atom_ids: set[str]) -> dict[str, Mapping[str, Any]]:
    if not source_atom_ids:
        return {}
    registry: dict[str, Mapping[str, Any]] = {}
    with v392.SOURCE_REGISTRY_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            source_atom_id = clean(row.get("source_atom_id"))
            if source_atom_id in source_atom_ids:
                registry[source_atom_id] = row
                if len(registry) == len(source_atom_ids):
                    break
    return registry


def elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 6)


def query_intent(source_family: str, row: Mapping[str, Any]) -> str:
    if source_family == "PDF":
        if row.get("answer_ready_window_sufficiency_measurable"):
            return "pdf_file_identity_structural_window_lookup"
        return "pdf_document_lookup"
    if row.get("new_cell_or_value@3"):
        return "cell_or_value_lookup"
    if row.get("new_table_or_range@3"):
        return "table_or_range_lookup"
    return "workbook_sheet_lookup"


def answer_ready_available(source_family: str, row: Mapping[str, Any], evidence_bundle: EvidenceBundle) -> bool:
    if not evidence_bundle.assembled:
        return False
    if source_family == "PDF":
        return bool(row.get("answer_ready_window_sufficient"))
    return True


def build_runtime_trace(
    *,
    source_family: str,
    row: Mapping[str, Any],
    source_trace: Mapping[str, Any],
    score_rows: Sequence[Mapping[str, Any]],
    source_registry: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    query_id = clean(row.get("query_id"))
    query_hash = clean(row.get("query_text_sha256")) or sha256_text(query_id)

    l0_start = time.perf_counter()
    intent = query_intent(source_family, row)
    request = LayeredRetrievalRequest(
        query_id=query_id,
        source_family=source_family,
        query_text_sha256=query_hash,
        source_artifact_run_id=clean(row.get("run_id")),
        query_intent=intent,
    )
    route = SourceFamilyRoute(
        source_family=source_family,
        query_intent=intent,
        route_reason="source_family_and_safe_query_metadata",
        signal_types=("metadata", "safe_query_features"),
    )
    l0_duration = elapsed_ms(l0_start)

    l1_start = time.perf_counter()
    candidates = tuple(
        candidate_from_score_row(
            query_id=query_id,
            source_family=source_family,
            row=row,
            score_row=score_row,
            rank=index,
            source_registry=source_registry,
        )
        for index, score_row in enumerate(score_rows, 1)
    )
    l1_duration = elapsed_ms(l1_start)

    l2_start = time.perf_counter()
    identity_resolved_candidates = tuple(
        candidate
        for candidate in candidates
        if candidate.identity_resolution and candidate.identity_resolution.resolved
    )
    l2_duration = elapsed_ms(l2_start)

    l3_start = time.perf_counter()
    structurally_located_candidates = tuple(
        candidate
        for candidate in identity_resolved_candidates
        if candidate.structural_locator and candidate.structural_locator.located
    )
    l3_duration = elapsed_ms(l3_start)

    l4_start = time.perf_counter()
    candidate_ids = [candidate.candidate_id for candidate in candidates]
    source_atom_ids = [candidate.source_atom_id for candidate in candidates if candidate.source_atom_id]
    hydrated_candidates = tuple(
        candidate
        for candidate in structurally_located_candidates
        if candidate.hydrated_evidence and candidate.hydrated_evidence.hydrated
    )
    l4_duration = elapsed_ms(l4_start)

    l5_start = time.perf_counter()
    evidence_candidates = tuple(
        candidate for candidate in hydrated_candidates if registry_evidence_bundle_is_valid(candidate, source_registry)
    )
    evidence_candidate_ids = tuple(candidate.candidate_id for candidate in evidence_candidates)
    evidence_source_atom_ids = tuple(candidate.source_atom_id for candidate in evidence_candidates if candidate.source_atom_id)
    evidence_assembled = bool(evidence_candidates)
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
    answer_available = answer_ready_available(source_family, row, evidence_bundle)
    answer_context = AnswerReadyContext(
        available=answer_available,
        status="AVAILABLE" if answer_available else "UNAVAILABLE",
        selected_candidate_ids=selected_candidate_ids,
        source_atom_ids=selected_source_atom_ids,
    )
    l7_duration = elapsed_ms(l7_start)
    candidate_count = len(candidates)
    l1_signals = ("diagnostic_replay_vector_like", "diagnostic_replay_keyword_like", "metadata")
    layer_timings = (
        layered_trace.timed_layer(
            layer_name="L0_QUERY_ROUTING",
            input_count=0,
            output_count=0,
            family=source_family,
            route=intent,
            signal_types=route.signal_types,
            duration_ms=l0_duration,
        ),
        layered_trace.timed_layer(
            layer_name="L1_COARSE_CANDIDATE_GENERATION",
            input_count=0,
            output_count=candidate_count,
            family=source_family,
            route=intent,
            signal_types=l1_signals,
            top_candidate_ids=candidate_ids,
            top_source_atom_ids=source_atom_ids,
            duration_ms=l1_duration,
        ),
        layered_trace.timed_layer(
            layer_name="L2_FILE_WORKBOOK_IDENTITY",
            input_count=candidate_count,
            output_count=len(identity_resolved_candidates),
            family=source_family,
            route=intent,
            signal_types=("metadata", "id_lookup", "prior_candidate_score"),
            top_candidate_ids=[candidate.candidate_id for candidate in identity_resolved_candidates],
            top_source_atom_ids=[candidate.source_atom_id for candidate in identity_resolved_candidates],
            drop_reason="file_or_workbook_identity_unresolved",
            duration_ms=l2_duration,
        ),
        layered_trace.timed_layer(
            layer_name="L3_STRUCTURAL_LOCATOR",
            input_count=len(identity_resolved_candidates),
            output_count=len(structurally_located_candidates),
            family=source_family,
            route=intent,
            signal_types=("structural", "source_family_specific_locator"),
            top_candidate_ids=[candidate.candidate_id for candidate in structurally_located_candidates],
            top_source_atom_ids=[candidate.source_atom_id for candidate in structurally_located_candidates],
            drop_reason="structural_locator_unresolved",
            duration_ms=l3_duration,
        ),
        layered_trace.timed_layer(
            layer_name="L4_SOURCEATOM_HYDRATION",
            input_count=len(structurally_located_candidates),
            output_count=len(hydrated_candidates),
            family=source_family,
            route=intent,
            signal_types=("id_lookup", "source_atom_registry"),
            top_candidate_ids=[candidate.candidate_id for candidate in hydrated_candidates],
            top_source_atom_ids=[candidate.source_atom_id for candidate in hydrated_candidates],
            source_atom_hydration_status="HYDRATED" if hydrated_candidates else "NO_SOURCEATOM_CANDIDATE",
            drop_reason="source_atom_registry_join_missing",
            duration_ms=l4_duration,
        ),
        layered_trace.timed_layer(
            layer_name="L5_EVIDENCE_BUNDLE_ASSEMBLY",
            input_count=len(hydrated_candidates),
            output_count=len(evidence_candidates),
            family=source_family,
            route=intent,
            signal_types=("source_atom_registry", "evidence_bundle"),
            top_candidate_ids=evidence_candidate_ids,
            top_source_atom_ids=evidence_source_atom_ids,
            evidence_bundle_assembly_status=evidence_bundle.status,
            drop_reason="source_atom_registry_bundle_invalid",
            duration_ms=l5_duration,
        ),
        layered_trace.timed_layer(
            layer_name="L6_EVIDENCE_SELECTOR",
            input_count=len(evidence_candidates),
            output_count=len(selected_candidates),
            family=source_family,
            route=intent,
            signal_types=("selector_score_components", "diagnostic_replay_no_production_winner"),
            top_candidate_ids=selected_candidate_ids,
            top_source_atom_ids=selected_source_atom_ids,
            drop_reason="not_selected_by_diagnostic_selector",
            duration_ms=l6_duration,
        ),
        layered_trace.timed_layer(
            layer_name="L7_ANSWER_READY_CONTEXT",
            input_count=len(selected_candidates),
            output_count=len(selected_candidates) if answer_context.available else 0,
            family=source_family,
            route=intent,
            signal_types=("answer_ready_context_diagnostic",),
            top_candidate_ids=selected_candidate_ids,
            top_source_atom_ids=selected_source_atom_ids,
            answer_ready_context_status=answer_context.status,
            drop_reason="answer_ready_context_unavailable",
            duration_ms=l7_duration,
        ),
    )
    candidate_sets = (
        CandidateSet("L1_COARSE_CANDIDATE_GENERATION", source_family, candidates),
        CandidateSet("L4_SOURCEATOM_HYDRATION", source_family, hydrated_candidates),
        CandidateSet("L6_EVIDENCE_SELECTOR", source_family, selected_candidates),
    )
    trace = LayeredRetrievalTrace(
        request=request,
        route=route,
        layer_timings=layer_timings,
        candidate_sets=candidate_sets,
        evidence_bundle=evidence_bundle,
        answer_ready_context=answer_context,
    )
    total_latency = round(sum(layer.duration_ms for layer in layer_timings), 6)
    failure_bucket = clean(row.get("failure_bucket")) or "not_classified"
    per_query = {
        "schema_version": f"{RUN_ID}_per_query_v1",
        "run_id": RUN_ID,
        "query_id": query_id,
        "source_family": source_family,
        "query_text_sha256": query_hash,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "source_artifact_run_id": clean(row.get("run_id")),
        "source_trace_run_id": clean(source_trace.get("run_id")),
        "route": route.route_reason,
        "query_intent": intent,
        "candidate_count": candidate_count,
        "selected_candidate_ids": list(selected_candidate_ids),
        "selected_source_atom_ids": list(selected_source_atom_ids),
        "source_atom_hydration_status": "HYDRATED" if hydrated_candidates else "NO_SOURCEATOM_CANDIDATE",
        "hydrated_source_atom_count": len(hydrated_candidates),
        "evidence_bundle_assembly_status": evidence_bundle.status,
        "answer_ready_context_available": answer_context.available,
        "answer_ready_context_status": answer_context.status,
        "total_retrieval_latency_ms": total_latency,
        "failure_bucket": failure_bucket,
        "raw_file_query_time_accessed": False,
        "L8_executed": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "used_gold_or_expected_text": False,
        "used_answer_value_shortcut": False,
        "direct_normalized_value_query_matching_used": False,
        "vector_payload_used_as_evidence_truth": False,
        "product_success_evidence_allowed": False,
    }
    trace_row = {
        "schema_version": f"{RUN_ID}_layer_trace_per_query_v1",
        "run_id": RUN_ID,
        "query_id": query_id,
        "source_family": source_family,
        "query_text_sha256": query_hash,
        "diagnostic_only": True,
        "layers_recorded": list(RUNTIME_LAYER_NAMES),
        "metrics_taxonomy_layer": METRICS_TAXONOMY_LAYER,
        "layers_skipped_by_design": list(SKIPPED_LAYERS),
        "layer_timings": [layered_trace.compact_layer_timing(layer) for layer in layer_timings],
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
        "vector_payload_used_as_evidence_truth": False,
        "runtime_adapter_contract": "v3_14_dataclass_contract_diagnostic_only",
    }
    return per_query, trace_row


def lineage_entry(path: Path) -> dict[str, str]:
    return {"path": repo_relative(path), "sha256": sha256_file(path)}


def build_input_lineage(input_paths: Mapping[str, Path]) -> dict[str, Any]:
    return {key: lineage_entry(path) for key, path in input_paths.items()}


def build_latency_summary(per_query_rows: Sequence[Mapping[str, Any]], trace_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total_values = [float(row["total_retrieval_latency_ms"]) for row in per_query_rows]
    per_layer_values: dict[str, list[float]] = {layer: [] for layer in RUNTIME_LAYER_NAMES}
    per_family_total: dict[str, list[float]] = defaultdict(list)
    per_family_layer: dict[str, dict[str, list[float]]] = defaultdict(lambda: {layer: [] for layer in RUNTIME_LAYER_NAMES})
    for row, trace in zip(per_query_rows, trace_rows):
        family = clean(row.get("source_family"))
        per_family_total[family].append(float(row["total_retrieval_latency_ms"]))
        for layer in trace["layer_timings"]:
            name = layer["layer_name"]
            duration = float(layer["duration_ms"])
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
            name = layer["layer_name"]
            per_layer_input[name].append(int(layer["input_candidate_count"]))
            per_layer_output[name].append(int(layer["output_candidate_count"]))
            per_layer_drop[name] += int(layer["dropped_candidate_count"])
            per_family_output[family][name].append(int(layer["output_candidate_count"]))
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
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    total = Counter()
    zero_output_by_layer = Counter()
    for row, trace in zip(per_query_rows, trace_rows):
        family = clean(row.get("source_family"))
        bucket = clean(row.get("failure_bucket")) or "not_classified"
        by_family[family][bucket] += 1
        total[bucket] += 1
        for layer in trace["layer_timings"]:
            if layer["layer_name"] != "L0_QUERY_ROUTING" and int(layer["output_candidate_count"]) == 0:
                zero_output_by_layer[layer["layer_name"]] += 1
    return {
        "schema_version": f"{RUN_ID}_failure_taxonomy_v1",
        "run_id": RUN_ID,
        "taxonomy_scope": "layered_retrieval_runtime_adapter_nonprod",
        "diagnostic_only": True,
        "metrics_taxonomy_layer": METRICS_TAXONOMY_LAYER,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "failure_bucket_counts": dict(sorted(total.items())),
        "per_source_family_failure_bucket_counts": {
            family: dict(sorted(counter.items())) for family, counter in sorted(by_family.items())
        },
        "zero_output_layer_counts": dict(sorted(zero_output_by_layer.items())),
        "raw_file_fallback_blocked_count": 0,
        "L8_executed": False,
    }


def guardrail_flags() -> dict[str, Any]:
    return {
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_evidence": False,
        "fine_tuning_executed": False,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "file_or_source_title_leak_success_evidence_used": False,
        "source_atom_registry_mutated": False,
        "source_registry_baseline_mutated": False,
        "official_denominator_mutated": False,
        "db_or_production_namespace_written": False,
        "protected_namespaces_touched": [],
        "source_atom_registry_canonical_truth": True,
        "vector_payload_used_as_evidence_truth": False,
        "raw_file_query_time_accessed": False,
        "raw_file_fallback_attempted": False,
        "raw_file_fallback_blocked_count": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "L8_executed": False,
        "answer_generation_executed": False,
        "deterministic_answer_execution_executed": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
    }


def build_guardrail_audit() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "raw_file_query_time_accessed": False,
        "allowed_runtime_inputs": [
            "existing_v3_12_xlsx_diagnostic_artifacts",
            "existing_v3_13_pdf_diagnostic_artifacts",
            "source_atom_registry",
            "searchunit_or_searchview_manifests_as_candidate_surfaces",
        ],
        "blocked_runtime_inputs": ["raw_pdf_files", "raw_xlsx_files", "gold_expected_supporting_text"],
        **guardrail_flags(),
    }


def build_leakage_audit() -> list[dict[str, Any]]:
    buckets = (
        "gold_expected_supporting_text",
        "direct_normalized_answer_value_query_matching",
        "file_or_source_title_success_evidence",
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


def source_family_metrics(
    *,
    family: str,
    rows: Sequence[Mapping[str, Any]],
    latency_summary: Mapping[str, Any],
    candidate_flow: Mapping[str, Any],
) -> dict[str, Any]:
    answer_ready = sum(1 for row in rows if row.get("answer_ready_context_available") is True)
    hydrated = sum(1 for row in rows if row.get("source_atom_hydration_status") == "HYDRATED")
    bundles = sum(1 for row in rows if row.get("evidence_bundle_assembly_status") == "ASSEMBLED")
    return {
        "source_family": family,
        "row_count": len(rows),
        "source_atom_hydrated": ratio(hydrated, len(rows)),
        "evidence_bundle_assembled": ratio(bundles, len(rows)),
        "answer_ready_context_available": ratio(answer_ready, len(rows)),
        "latency_summary": latency_summary["per_source_family"].get(family, {}),
        "candidate_flow_summary": candidate_flow["per_source_family"].get(family, {}),
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
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
    rows_by_family: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in per_query_rows:
        rows_by_family[clean(row.get("source_family"))].append(row)
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "total_runtime_adapter_rows": len(per_query_rows),
        "total_pdf_rows": len(rows_by_family.get("PDF", [])),
        "total_xlsx_rows": len(rows_by_family.get("XLSX", [])),
        "latency_summary": latency_summary,
        "candidate_flow_summary": candidate_flow,
        "source_family_separated_metrics": {
            family: source_family_metrics(
                family=family,
                rows=rows,
                latency_summary=latency_summary,
                candidate_flow=candidate_flow,
            )
            for family, rows in sorted(rows_by_family.items())
        },
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
        "families_reported_separately": ["PDF", "XLSX"],
        "pdf_xlsx_collapsed_headline_score_reported": False,
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
        "run_class": "diagnostic_only_layered_retrieval_runtime_adapter_nonprod",
        "runtime_adapter_surface": "diagnostic_replay_query_time_adapter",
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "product_success_evidence_allowed": False,
        "fresh_real_holdout_sufficient": False,
        "total_runtime_adapter_rows": metrics["total_runtime_adapter_rows"],
        "total_pdf_rows": metrics["total_pdf_rows"],
        "total_xlsx_rows": metrics["total_xlsx_rows"],
        "families_reported_separately": ["PDF", "XLSX"],
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
        },
        "v3_12_xlsx_control_reference": {
            "run_id": v312.RUN_ID,
            "row_count": metrics["total_xlsx_rows"],
            "optimized_in_v3_14": False,
        },
        "v3_13_pdf_diagnostic_reference": {
            "run_id": v313.RUN_ID,
            "row_count": metrics["total_pdf_rows"],
            "optimized_in_v3_14": False,
        },
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
        **guardrail_flags(),
    }


@lru_cache(maxsize=1)
def build_artifacts() -> dict[str, Any]:
    input_paths = {
        "v3_11_summary_json": REPORT_DIR / "official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic_summary.json",
        "v3_12_xlsx_summary_json": v312.OUTPUTS["summary_json"],
        "v3_12_xlsx_metrics_json": v312.OUTPUTS["metrics_json"],
        "v3_12_xlsx_eval_jsonl": v312.OUTPUTS["xlsx_structural_locator_eval_per_query_jsonl"],
        "v3_12_xlsx_trace_jsonl": v312.OUTPUTS["xlsx_layer_trace_per_query_jsonl"],
        "v3_12_xlsx_score_jsonl": v312.OUTPUTS["xlsx_score_components_jsonl"],
        "v3_13_pdf_summary_json": v313.OUTPUTS["summary_json"],
        "v3_13_pdf_metrics_json": v313.OUTPUTS["metrics_json"],
        "v3_13_pdf_eval_jsonl": v313.OUTPUTS["pdf_structural_locator_eval_per_query_jsonl"],
        "v3_13_pdf_trace_jsonl": v313.OUTPUTS["pdf_layer_trace_per_query_jsonl"],
        "v3_13_pdf_score_jsonl": v313.OUTPUTS["pdf_score_components_jsonl"],
        "v3_10_holdout_manifest_json": v310.OUTPUTS["fresh_real_holdout_manifest_json"],
        "source_registry_jsonl": v392.SOURCE_REGISTRY_JSONL,
    }
    missing = [repo_relative(path) for path in input_paths.values() if not artifact_exists(path)]
    if missing:
        raise FileNotFoundError("missing required v3_14 input artifacts: " + ", ".join(missing))
    input_lineage = build_input_lineage(input_paths)
    xlsx_eval_rows = read_jsonl(v312.OUTPUTS["xlsx_structural_locator_eval_per_query_jsonl"])
    xlsx_trace_source = trace_rows_by_query(read_jsonl(v312.OUTPUTS["xlsx_layer_trace_per_query_jsonl"]))
    xlsx_score_rows = read_jsonl(v312.OUTPUTS["xlsx_score_components_jsonl"])
    pdf_eval_rows = read_jsonl(v313.OUTPUTS["pdf_structural_locator_eval_per_query_jsonl"])
    pdf_trace_source = trace_rows_by_query(read_jsonl(v313.OUTPUTS["pdf_layer_trace_per_query_jsonl"]))
    pdf_score_rows = read_jsonl(v313.OUTPUTS["pdf_score_components_jsonl"])
    source_registry = load_source_registry_subset(collect_source_atom_ids(xlsx_score_rows, pdf_score_rows))
    xlsx_scores_by_query = score_rows_by_query(xlsx_score_rows)
    pdf_scores_by_query = score_rows_by_query(pdf_score_rows)
    per_query_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    for row in xlsx_eval_rows:
        per_query, trace = build_runtime_trace(
            source_family="XLSX",
            row=row,
            source_trace=xlsx_trace_source.get(clean(row.get("query_id")), {}),
            score_rows=xlsx_scores_by_query.get(clean(row.get("query_id")), []),
            source_registry=source_registry,
        )
        per_query_rows.append(per_query)
        trace_rows.append(trace)
    for row in pdf_eval_rows:
        per_query, trace = build_runtime_trace(
            source_family="PDF",
            row=row,
            source_trace=pdf_trace_source.get(clean(row.get("query_id")), {}),
            score_rows=pdf_scores_by_query.get(clean(row.get("query_id")), []),
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
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Last updated: [^.]+\.", "Last updated: 2026-05-25 KST.", text, count=1)
    start = f"<!-- {marker}:start -->"
    end = f"<!-- {marker}:end -->"
    marked = f"{start}\n{entry.rstrip()}\n{end}\n"
    text = re.sub(rf"\n?{re.escape(start)}.*?{re.escape(end)}\n?", "\n", text, flags=re.DOTALL)
    insertion_candidates = [index for index in (text.find("\n<!-- "), text.find("\n## ")) if index != -1]
    insert_at = min(insertion_candidates) if insertion_candidates else -1
    if insert_at == -1:
        text = text.rstrip() + "\n\n" + marked
    else:
        text = text[:insert_at].rstrip() + "\n\n" + marked + "\n" + text[insert_at:].lstrip("\n")
    path.write_text(text, encoding="utf-8")


def refresh_current_artifact_wording(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r"only `rag-ingestion/`, and that directory keeps `status\.jsonl` plus compact\s+current v3_6_9.*?quality artifacts\.",
        "only `rag-ingestion/`, and that directory keeps `status.jsonl` plus compact current v3_6_9 and later diagnostic artifacts required by the current RAG profile.",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"`status\.jsonl` plus compact v3_6_9,.*?quality artifacts;",
        "`status.jsonl` plus compact current v3_6_9 and later diagnostic artifacts required by the current RAG profile;",
        text,
        flags=re.DOTALL,
    )
    text = text.replace(
        "`status.jsonl` plus v3_8, v3_8_1, v3_8_2, v3_8_3 summary/metrics/per-query/per-family JSON/JSONL, and v3_9 quality artifacts where required by tests",
        "`status.jsonl` plus compact current v3_6_9 and later diagnostic artifacts required by the current RAG profile",
    )
    path.write_text(text, encoding="utf-8")


def update_docs(metrics: Mapping[str, Any]) -> None:
    latency = metrics["latency_summary"]
    candidate_flow = metrics["candidate_flow_summary"]
    l4_max = candidate_flow["per_layer"]["L4_SOURCEATOM_HYDRATION"]["max_output_candidate_count"]
    progress_entry = (
        f"- v3_14 layered retrieval runtime adapter non-prod (`{RUN_ID}`) runs L0 through L7 over the "
        "common PDF/XLSX runtime adapter surface using existing v3_12 XLSX and v3_13 PDF diagnostic "
        "artifacts. It records per-layer candidate counts, latency, drop reasons, signal types, SourceAtom "
        "hydration, EvidenceBundle assembly, selected candidates, and answer-ready context availability. "
        "SourceAtom registry remains canonical truth; SearchView/vector payload remains candidate-only; "
        "raw_file_query_time_accessed=false; L8 generation and deterministic answer execution stay closed. "
        "PDF and XLSX are reported separately, current seen rows are diagnostic/no-regression only, and "
        "fresh real source-document/workbook-disjoint holdout remains unavailable. official_metric_input_rows=0; "
        "future scored adapter remains DISABLED_PENDING_USER_APPROVAL; product_success_evidence_allowed=false; "
        "protected_namespaces_touched=[]."
    )
    measurements_entry = f"""## 2026-05-25 - v3_14 Layered Retrieval Runtime Adapter Non-Prod

- Run: `{RUN_ID}`
- Policy: diagnostic-only runtime adapter; official_metric_input_rows=0; product_success_evidence_allowed=false; future scored adapter remains DISABLED_PENDING_USER_APPROVAL; no L8 generation, deterministic answer execution, promotion, threshold tuning, or winner selection.
- Scope: query-time L0-L7 adapter replay over existing v3_12 XLSX and v3_13 PDF diagnostic artifacts. This measures trace completeness, candidate flow, latency instrumentation, and guardrails, not score lift.
- Holdout: fresh real source-document/workbook-disjoint holdout remains unavailable; current seen rows are diagnostic/no-regression only.

| Runtime adapter metric | value |
| --- | ---: |
| total runtime adapter rows | {metrics['total_runtime_adapter_rows']} |
| PDF rows | {metrics['total_pdf_rows']} |
| XLSX rows | {metrics['total_xlsx_rows']} |
| median total retrieval latency ms | {latency['median_total_retrieval_latency_ms']} |
| p95 total retrieval latency ms | {latency['p95_total_retrieval_latency_ms']} |
| max L4 hydrated candidate count | {l4_max} |
| raw_file_query_time_accessed | false |
| L8_executed | false |

Per-family latency and candidate-count summaries are reported separately in the compact metrics, latency, candidate-flow, and per-family artifacts. No PDF/XLSX headline score, official metric, product success evidence, or promotion evidence is produced.
"""
    triage_entry = f"""## v3_14 Layered Retrieval Runtime Adapter Triage

- runtime adapter success is trace completeness, not score lift: each diagnostic query records L0-L7 candidate counts, latency, drop reasons, signal types, SourceAtom hydration, EvidenceBundle assembly, selected candidates, and answer-ready context availability.
- PDF and XLSX remain separated. v3_13 PDF rows and v3_12 XLSX rows enter the same orchestration interface, but their metrics are source-family separated and are not collapsed into a headline score.
- Raw PDF/XLSX query-time access is rejected by design. The adapter uses existing artifacts, manifests, candidate surfaces, and SourceAtom registry joins only.
- SourceAtom registry remains canonical evidence truth; SearchView/vector payload remains candidate-only.
- The future scored adapter remains disabled, and fresh real source-document/workbook-disjoint holdout remains unavailable, so product success and promotion remain blocked.
"""
    refresh_current_artifact_wording(PROGRESS_DOC)
    refresh_current_artifact_wording(MEASUREMENTS_DOC)
    refresh_current_artifact_wording(TRIAGE_DOC)
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_14_layered_retrieval_runtime_adapter_nonprod_ready`;",
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
        "run_class": summary["run_class"],
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
        "total_runtime_adapter_rows": summary["total_runtime_adapter_rows"],
        "total_pdf_rows": summary["total_pdf_rows"],
        "total_xlsx_rows": summary["total_xlsx_rows"],
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
        key.replace("_jsonl_sha256", "_sha256").replace("_json_sha256", "_sha256"): value
        for key, value in diagnostic_common.artifact_sha256_without_summary(OUTPUTS).items()
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
    parser = argparse.ArgumentParser(description="Build v3_14 diagnostic-only layered retrieval runtime adapter artifacts.")
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
                    "raw_file_query_time_accessed": False,
                    "L8_executed": False,
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
