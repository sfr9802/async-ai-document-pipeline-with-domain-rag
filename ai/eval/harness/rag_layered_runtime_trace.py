"""Shared dataclasses and pure helpers for RAG layered runtime traces."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Mapping, Sequence

from . import rag_diagnostic_common as diagnostic_common


@dataclass(frozen=True)
class LayeredRetrievalRequest:
    query_id: str
    source_family: str
    query_text_sha256: str
    source_artifact_run_id: str
    query_intent: str
    diagnostic_replay: bool = True


@dataclass(frozen=True)
class SourceFamilyRoute:
    source_family: str
    query_intent: str
    route_reason: str
    signal_types: tuple[str, ...]


@dataclass(frozen=True)
class SourceIdentityResolution:
    candidate_id: str
    source_family: str
    resolved: bool
    rank: int
    document_version_id_sha256: str = ""
    source_identity_sha256: str = ""
    workbook_id: str = ""
    sheet_name: str = ""
    confidence_bucket: str = ""
    resolve_status: str = ""


@dataclass(frozen=True)
class StructuralLocatorResult:
    candidate_id: str
    source_family: str
    located: bool
    page: int | None = None
    bbox_present: bool = False
    same_page_bounded_window: bool = False
    sheet_name: str = ""
    table_or_range: str = ""
    cell: str = ""
    structural_score: float | None = None


@dataclass(frozen=True)
class HydratedEvidence:
    candidate_id: str
    source_atom_id: str
    hydrated: bool
    canonical_payload_source: str
    hydration_status: str


@dataclass(frozen=True)
class EvidenceBundle:
    assembled: bool
    status: str
    candidate_ids: tuple[str, ...]
    source_atom_ids: tuple[str, ...]
    vector_payload_used_as_evidence_truth: bool = False


@dataclass(frozen=True)
class AnswerReadyContext:
    available: bool
    status: str
    selected_candidate_ids: tuple[str, ...]
    source_atom_ids: tuple[str, ...]
    generation_executed: bool = False
    deterministic_answer_execution_executed: bool = False


@dataclass(frozen=True)
class LayerDropReason:
    layer_name: str
    reason: str
    count: int


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    source_family: str
    rank: int
    source_atom_id: str = ""
    search_view_id: str = ""
    source_identity_sha256: str = ""
    score_components: Mapping[str, Any] = field(default_factory=dict)
    signal_types: tuple[str, ...] = ()
    identity_resolution: SourceIdentityResolution | None = None
    structural_locator: StructuralLocatorResult | None = None
    hydrated_evidence: HydratedEvidence | None = None
    diagnostic_replay_channel: str = "diagnostic_replay"


@dataclass(frozen=True)
class CandidateSet:
    layer_name: str
    source_family: str
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class LayerTiming:
    layer_name: str
    duration_ms: float
    input_candidate_count: int
    output_candidate_count: int
    dropped_candidate_count: int
    top_candidate_ids: tuple[str, ...] = ()
    top_source_atom_ids: tuple[str, ...] = ()
    route: str = ""
    family: str = ""
    drop_reasons: tuple[Mapping[str, Any], ...] = ()
    signal_types: tuple[str, ...] = ()
    raw_file_query_time_accessed: bool = False
    source_atom_hydration_status: str = ""
    evidence_bundle_assembly_status: str = ""
    answer_ready_context_status: str = ""


@dataclass(frozen=True)
class LayeredRetrievalTrace:
    request: LayeredRetrievalRequest
    route: SourceFamilyRoute
    layer_timings: tuple[LayerTiming, ...]
    candidate_sets: tuple[CandidateSet, ...]
    evidence_bundle: EvidenceBundle
    answer_ready_context: AnswerReadyContext
    diagnostic_only: bool = True
    raw_file_query_time_accessed: bool = False
    L8_executed: bool = False


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def top(values: Sequence[str], limit: int = 3) -> tuple[str, ...]:
    return tuple(value for value in values if value)[:limit]


def layer_drop(layer_name: str, reason: str, count: int) -> tuple[Mapping[str, Any], ...]:
    if count <= 0:
        return ()
    return (jsonable(LayerDropReason(layer_name=layer_name, reason=reason, count=count)),)


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
    dropped = max(0, input_count - output_count)
    if duration_ms is None:
        start = time.perf_counter()
        duration_ms = round((time.perf_counter() - start) * 1000.0, 6)
    return LayerTiming(
        layer_name=layer_name,
        duration_ms=duration_ms,
        input_candidate_count=input_count,
        output_candidate_count=output_count,
        dropped_candidate_count=dropped,
        top_candidate_ids=top(top_candidate_ids),
        top_source_atom_ids=top(top_source_atom_ids),
        route=route,
        family=family,
        drop_reasons=layer_drop(layer_name, drop_reason, dropped),
        signal_types=tuple(sorted({diagnostic_common.clean(signal) for signal in signal_types if diagnostic_common.clean(signal)})),
        raw_file_query_time_accessed=False,
        source_atom_hydration_status=source_atom_hydration_status,
        evidence_bundle_assembly_status=evidence_bundle_assembly_status,
        answer_ready_context_status=answer_ready_context_status,
    )


def compact_layer_timing(layer: LayerTiming) -> dict[str, Any]:
    row = {
        "layer_name": layer.layer_name,
        "duration_ms": layer.duration_ms,
        "input_candidate_count": layer.input_candidate_count,
        "output_candidate_count": layer.output_candidate_count,
        "dropped_candidate_count": layer.dropped_candidate_count,
        "top_candidate_ids": list(layer.top_candidate_ids[:1]),
        "top_source_atom_ids": list(layer.top_source_atom_ids[:1]),
        "route": layer.route,
        "family": layer.family,
        "drop_reasons": [jsonable(drop) for drop in layer.drop_reasons],
        "signal_types": list(layer.signal_types),
        "raw_file_query_time_accessed": layer.raw_file_query_time_accessed,
    }
    if layer.source_atom_hydration_status:
        row["source_atom_hydration_status"] = layer.source_atom_hydration_status
    if layer.evidence_bundle_assembly_status:
        row["evidence_bundle_assembly_status"] = layer.evidence_bundle_assembly_status
    if layer.answer_ready_context_status:
        row["answer_ready_context_status"] = layer.answer_ready_context_status
    return row
