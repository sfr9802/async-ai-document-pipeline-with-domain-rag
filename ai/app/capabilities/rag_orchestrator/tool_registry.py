"""Bounded L0-L8 tool specifications for query-time RAG orchestration.

The registry is declarative: it describes the permitted tool surface and route
lanes without executing retrieval, parsing files, or mutating indexes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

TOOL_SPEC_VERSION = "rag_tool_spec_v1"
DEFAULT_TOOL_REGISTRY_VERSION = "rag_tool_registry_l0_l8_v1"

ROUTE_USER_LOCATOR = "user_locator"
ROUTE_ROUGH_QUERY = "rough_query"
ROUTE_HYBRID = "hybrid"
ROUTE_UNSUPPORTED = "unsupported"
ROUTE_LANES = (
    ROUTE_USER_LOCATOR,
    ROUTE_ROUGH_QUERY,
    ROUTE_HYBRID,
    ROUTE_UNSUPPORTED,
)
EXECUTABLE_ROUTE_LANES = (
    ROUTE_USER_LOCATOR,
    ROUTE_ROUGH_QUERY,
    ROUTE_HYBRID,
)

LAYER_NAMES = (
    "L0_QUERY_ROUTING",
    "L1_COARSE_CANDIDATE_GENERATION",
    "L2_FILE_WORKBOOK_IDENTITY",
    "L3_STRUCTURAL_LOCATOR",
    "L4_SOURCEATOM_HYDRATION",
    "L5_EVIDENCE_BUNDLE_ASSEMBLY",
    "L6_EVIDENCE_SELECTOR",
    "L7_ANSWER_READY_CONTEXT",
    "L8_FINAL_LLM_ANSWER_GENERATION",
)

PROVENANCE_POLICY = "source_atom_registry_canonical_truth"


def _tuple_str(values: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(str(value).strip() for value in (values or ()) if str(value).strip())


def _dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


@dataclass(frozen=True)
class ToolSpec:
    """Versioned contract for one bounded L0-L8 query-time tool."""

    tool_id: str
    layer_name: str
    allowed_input: tuple[str, ...] | list[str]
    forbidden_input: tuple[str, ...] | list[str]
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    confidence_policy: Mapping[str, Any]
    drop_reasons: tuple[str, ...] | list[str]
    provenance_requirements: tuple[str, ...] | list[str]
    runtime_contract: Mapping[str, Any] = field(default_factory=dict)
    version: str = "v1"
    tool_spec_version: str = TOOL_SPEC_VERSION
    allowed_route_lanes: tuple[str, ...] | list[str] = EXECUTABLE_ROUTE_LANES
    bounded: bool = True
    unbounded_fallback_allowed: bool = False
    diagnostic_only: bool = True

    def __post_init__(self) -> None:
        if self.tool_spec_version != TOOL_SPEC_VERSION:
            raise ValueError(f"unsupported tool_spec_version: {self.tool_spec_version}")
        if self.layer_name not in LAYER_NAMES:
            raise ValueError(f"unsupported layer_name: {self.layer_name}")
        if not self.tool_id.startswith("rag."):
            raise ValueError("tool_id must use rag. namespace")
        if not self.allowed_input:
            raise ValueError("allowed_input is required")
        if not self.forbidden_input:
            raise ValueError("forbidden_input is required")
        if not self.drop_reasons:
            raise ValueError("drop_reasons is required")
        if not self.provenance_requirements:
            raise ValueError("provenance_requirements is required")
        object.__setattr__(self, "allowed_input", _tuple_str(self.allowed_input))
        object.__setattr__(self, "forbidden_input", _tuple_str(self.forbidden_input))
        object.__setattr__(self, "drop_reasons", _tuple_str(self.drop_reasons))
        object.__setattr__(
            self,
            "provenance_requirements",
            _tuple_str(self.provenance_requirements),
        )
        lanes = _tuple_str(self.allowed_route_lanes)
        if not lanes or any(lane not in ROUTE_LANES for lane in lanes):
            raise ValueError("allowed_route_lanes must be a subset of ROUTE_LANES")
        object.__setattr__(self, "allowed_route_lanes", lanes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "toolSpecVersion": self.tool_spec_version,
            "toolId": self.tool_id,
            "version": self.version,
            "layerName": self.layer_name,
            "allowedRouteLanes": list(self.allowed_route_lanes),
            "allowedInput": list(self.allowed_input),
            "forbiddenInput": list(self.forbidden_input),
            "inputSchema": _dict(self.input_schema),
            "outputSchema": _dict(self.output_schema),
            "confidencePolicy": _dict(self.confidence_policy),
            "dropReasons": list(self.drop_reasons),
            "provenanceRequirements": list(self.provenance_requirements),
            "runtimeContract": _dict(self.runtime_contract),
            "bounded": self.bounded,
            "unboundedFallbackAllowed": self.unbounded_fallback_allowed,
            "diagnosticOnly": self.diagnostic_only,
        }


@dataclass(frozen=True)
class RoutePolicyDecision:
    """Bounded route-lane decision over the registered tool surface."""

    route_lane: str
    selected_tool_ids: tuple[str, ...]
    reason: str
    allow_unbounded_fallback: bool = False
    diagnostic_only: bool = True
    official_metric_input_rows: int = 0
    provenance_policy: str = PROVENANCE_POLICY

    def __post_init__(self) -> None:
        if self.route_lane not in ROUTE_LANES:
            raise ValueError(f"unsupported route_lane: {self.route_lane}")
        object.__setattr__(self, "selected_tool_ids", _tuple_str(self.selected_tool_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_lane": self.route_lane,
            "selected_tool_ids": list(self.selected_tool_ids),
            "route_policy_reason": self.reason,
            "allow_unbounded_fallback": self.allow_unbounded_fallback,
            "diagnostic_only": self.diagnostic_only,
            "official_metric_input_rows": self.official_metric_input_rows,
            "provenance_policy": self.provenance_policy,
        }


@dataclass(frozen=True)
class ToolRegistry:
    """Immutable registry of bounded L0-L8 tool specs."""

    registry_version: str
    specs: tuple[ToolSpec, ...]
    unbounded_fallback_allowed: bool = False
    diagnostic_only: bool = True
    official_metric_input_rows: int = 0
    provenance_policy: str = PROVENANCE_POLICY

    def __post_init__(self) -> None:
        layers = [spec.layer_name for spec in self.specs]
        if tuple(layers) != LAYER_NAMES:
            raise ValueError("ToolRegistry must register exactly L0-L8 in order")
        if len({spec.tool_id for spec in self.specs}) != len(self.specs):
            raise ValueError("ToolRegistry tool ids must be unique")

    def layer_names(self) -> tuple[str, ...]:
        return tuple(spec.layer_name for spec in self.specs)

    def tool_specs(self) -> tuple[ToolSpec, ...]:
        return self.specs

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "rag_tool_registry_v1",
            "registryVersion": self.registry_version,
            "toolSpecVersion": TOOL_SPEC_VERSION,
            "routeLanes": list(ROUTE_LANES),
            "executableRouteLanes": list(EXECUTABLE_ROUTE_LANES),
            "toolSpecs": [spec.to_dict() for spec in self.specs],
            "unboundedFallbackAllowed": self.unbounded_fallback_allowed,
            "diagnosticOnly": self.diagnostic_only,
            "officialMetricInputRows": self.official_metric_input_rows,
            "provenancePolicy": self.provenance_policy,
        }

    def route_policy(
        self,
        *,
        user_locator_present: bool,
        rough_query_present: bool,
        supported_source_family: bool = True,
    ) -> RoutePolicyDecision:
        if not supported_source_family:
            return RoutePolicyDecision(
                route_lane=ROUTE_UNSUPPORTED,
                selected_tool_ids=(),
                reason="unsupported_source_family_or_policy",
                provenance_policy=self.provenance_policy,
            )
        if user_locator_present and rough_query_present:
            lane = ROUTE_HYBRID
            reason = "query_has_user_locator_and_rough_natural_language_request"
        elif user_locator_present:
            lane = ROUTE_USER_LOCATOR
            reason = "query_has_user_provided_locator"
        elif rough_query_present:
            lane = ROUTE_ROUGH_QUERY
            reason = "query_has_rough_natural_language_request"
        else:
            return RoutePolicyDecision(
                route_lane=ROUTE_UNSUPPORTED,
                selected_tool_ids=(),
                reason="no_supported_locator_or_rough_query_signal",
                provenance_policy=self.provenance_policy,
            )
        return RoutePolicyDecision(
            route_lane=lane,
            selected_tool_ids=tuple(
                spec.tool_id for spec in self.specs if lane in spec.allowed_route_lanes
            ),
            reason=reason,
            provenance_policy=self.provenance_policy,
        )


def build_default_tool_registry() -> ToolRegistry:
    """Build the repo's bounded diagnostic L0-L8 tool registry."""

    return ToolRegistry(
        registry_version=DEFAULT_TOOL_REGISTRY_VERSION,
        specs=tuple(_build_specs()),
    )


def _object_schema(required: Iterable[str], properties: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": list(required),
        "properties": dict(properties),
        "additionalProperties": False,
    }


def _runtime_contract(
    *,
    materialization: str,
    adapter: str,
    max_candidates: int | None = None,
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "materialization": materialization,
        "adapterClassification": adapter,
        "rawFileQueryTimeAccessed": False,
        "productionWriteAllowed": False,
        "unboundedScanAllowed": False,
        "sourceAtomRegistryCanonicalTruth": True,
        "vectorPayloadUsedAsEvidenceTruth": False,
    }
    if max_candidates is not None:
        contract["maxCandidateCount"] = max_candidates
    return contract


def _build_specs() -> list[ToolSpec]:
    common_forbidden = (
        "expected_answer",
        "supporting_evidence",
        "gold_locator",
        "target_locator",
        "human_relevance_label",
        "human_answerability_label",
        "raw_pdf_xlsx_query_time_parse",
        "unbounded_source_registry_scan",
        "production_namespace_write",
    )
    return [
        ToolSpec(
            tool_id="rag.l0.query_routing",
            layer_name="L0_QUERY_ROUTING",
            allowed_input=("query_text", "request_policy", "query_owned_locator_text", "source_family_hint"),
            forbidden_input=common_forbidden,
            input_schema=_object_schema(
                ("query_text", "request_policy"),
                {
                    "query_text": {"type": "string"},
                    "request_policy": {"type": "object"},
                    "query_owned_locator_text": {"type": "string"},
                    "source_family_hint": {"type": "string"},
                },
            ),
            output_schema=_object_schema(
                ("route_lane", "route_confidence", "selected_tool_ids"),
                {
                    "route_lane": {"enum": list(ROUTE_LANES)},
                    "route_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "selected_tool_ids": {"type": "array", "items": {"type": "string"}},
                },
            ),
            confidence_policy={
                "policy": "deterministic_query_signal_with_fail_closed_unsupported",
                "minimumConfidence": 0.55,
            },
            drop_reasons=("unsupported_route_lane", "policy_blocked", "no_supported_query_signal"),
            provenance_requirements=("query_text_sha256", "request_policy_id", "route_policy_reason"),
            runtime_contract=_runtime_contract(materialization="query_time_lightweight", adapter="route_policy"),
        ),
        ToolSpec(
            tool_id="rag.l1.coarse_candidate_generation",
            layer_name="L1_COARSE_CANDIDATE_GENERATION",
            allowed_input=("query_text", "route_lane", "index_namespace", "source_file_type_filter"),
            forbidden_input=common_forbidden,
            input_schema=_object_schema(
                ("query_text", "route_lane", "index_namespace"),
                {
                    "query_text": {"type": "string"},
                    "route_lane": {"enum": list(ROUTE_LANES)},
                    "index_namespace": {"type": "string"},
                    "source_file_type_filter": {"type": "array", "items": {"type": "string"}},
                },
            ),
            output_schema=_object_schema(
                ("candidate_ids", "drop_reasons"),
                {
                    "candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "drop_reasons": {"type": "array", "items": {"type": "string"}},
                },
            ),
            confidence_policy={"policy": "retrieval_score_candidate_only_not_answer_confidence"},
            drop_reasons=("index_namespace_mismatch", "source_family_mismatch", "embedding_status_mismatch"),
            provenance_requirements=("index_namespace", "search_view_id", "search_unit_id"),
            runtime_contract=_runtime_contract(
                materialization="index_time_materialized",
                adapter="replay_or_mock_live_runtime_like",
                max_candidates=30,
            ),
        ),
        ToolSpec(
            tool_id="rag.l2.file_workbook_identity",
            layer_name="L2_FILE_WORKBOOK_IDENTITY",
            allowed_input=("candidate_ids", "query_owned_file_or_workbook_signal", "source_identity_metadata"),
            forbidden_input=common_forbidden,
            input_schema=_object_schema(
                ("candidate_ids",),
                {
                    "candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "query_owned_file_or_workbook_signal": {"type": "string"},
                    "source_identity_metadata": {"type": "object"},
                },
            ),
            output_schema=_object_schema(
                ("candidate_ids", "identity_confidence"),
                {
                    "candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "identity_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            ),
            confidence_policy={"policy": "source_identity_match_not_answer_correctness"},
            drop_reasons=("wrong_file_or_workbook", "ambiguous_file_identity", "missing_source_identity"),
            provenance_requirements=("source_file_id", "document_version_id", "workbook_version_id"),
            runtime_contract=_runtime_contract(
                materialization="query_time_lightweight",
                adapter="replay_or_mock_live_runtime_like",
                max_candidates=10,
            ),
        ),
        ToolSpec(
            tool_id="rag.l3.structural_locator",
            layer_name="L3_STRUCTURAL_LOCATOR",
            allowed_input=("bounded_candidate_ids", "query_owned_locator_terms", "precomputed_structural_features"),
            forbidden_input=common_forbidden,
            input_schema=_object_schema(
                ("bounded_candidate_ids", "precomputed_structural_features"),
                {
                    "bounded_candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "query_owned_locator_terms": {"type": "object"},
                    "precomputed_structural_features": {"type": "object"},
                },
            ),
            output_schema=_object_schema(
                ("candidate_ids", "locator_confidence"),
                {
                    "candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "locator_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            ),
            confidence_policy={"policy": "locator_resolution_confidence_not_gold_answerability"},
            drop_reasons=("locator_not_found", "locator_ambiguous", "structural_feature_missing"),
            provenance_requirements=("query_owned_locator_text", "locator_fingerprint", "source_atom_id"),
            runtime_contract=_runtime_contract(
                materialization="query_time_lightweight",
                adapter="replay_or_mock_live_runtime_like",
                max_candidates=3,
            ),
        ),
        ToolSpec(
            tool_id="rag.l4.sourceatom_hydration",
            layer_name="L4_SOURCEATOM_HYDRATION",
            allowed_input=("source_atom_ids", "source_registry_snapshot"),
            forbidden_input=common_forbidden,
            input_schema=_object_schema(
                ("source_atom_ids", "source_registry_snapshot"),
                {
                    "source_atom_ids": {"type": "array", "items": {"type": "string"}},
                    "source_registry_snapshot": {"type": "string"},
                },
            ),
            output_schema=_object_schema(
                ("source_atoms", "hydration_status"),
                {
                    "source_atoms": {"type": "array", "items": {"type": "object"}},
                    "hydration_status": {"type": "string"},
                },
            ),
            confidence_policy={"policy": "binary_registry_hydration_status"},
            drop_reasons=("source_atom_missing", "source_registry_version_mismatch", "canonical_payload_invalid"),
            provenance_requirements=("source_atom_id", "source_registry_version", "canonical_citation_payload"),
            runtime_contract=_runtime_contract(
                materialization="query_time_cacheable",
                adapter="replay_or_mock_live_runtime_like",
                max_candidates=3,
            ),
        ),
        ToolSpec(
            tool_id="rag.l5.evidence_bundle_assembly",
            layer_name="L5_EVIDENCE_BUNDLE_ASSEMBLY",
            allowed_input=("source_atoms", "max_evidence_bundles"),
            forbidden_input=common_forbidden,
            input_schema=_object_schema(
                ("source_atoms", "max_evidence_bundles"),
                {
                    "source_atoms": {"type": "array", "items": {"type": "object"}},
                    "max_evidence_bundles": {"type": "integer", "minimum": 1, "maximum": 3},
                },
            ),
            output_schema=_object_schema(
                ("evidence_bundles", "drop_reasons"),
                {
                    "evidence_bundles": {"type": "array", "items": {"type": "object"}},
                    "drop_reasons": {"type": "array", "items": {"type": "string"}},
                },
            ),
            confidence_policy={"policy": "traceable_evidence_bundle_not_answer_correctness"},
            drop_reasons=("evidence_text_missing", "citation_unrenderable", "max_bundle_limit_exceeded"),
            provenance_requirements=("source_atom_id", "rendered_citation", "source_text_snapshot_hash"),
            runtime_contract=_runtime_contract(
                materialization="query_time_lightweight",
                adapter="replay_or_mock_live_runtime_like",
                max_candidates=3,
            ),
        ),
        ToolSpec(
            tool_id="rag.l6.evidence_selector",
            layer_name="L6_EVIDENCE_SELECTOR",
            allowed_input=("evidence_bundles", "route_lane", "max_selected_evidence"),
            forbidden_input=common_forbidden,
            input_schema=_object_schema(
                ("evidence_bundles", "route_lane"),
                {
                    "evidence_bundles": {"type": "array", "items": {"type": "object"}},
                    "route_lane": {"enum": list(ROUTE_LANES)},
                    "max_selected_evidence": {"type": "integer", "minimum": 1, "maximum": 3},
                },
            ),
            output_schema=_object_schema(
                ("selected_evidence_ids", "selector_confidence"),
                {
                    "selected_evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "selector_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            ),
            confidence_policy={"policy": "ranking_order_diagnostic_only_no_official_metric"},
            drop_reasons=("duplicate_source_atom", "weak_locator_match", "selector_max_limit_exceeded"),
            provenance_requirements=("evidence_bundle_id", "source_atom_id", "selector_reason"),
            runtime_contract=_runtime_contract(
                materialization="query_time_lightweight",
                adapter="replay_or_mock_live_runtime_like",
                max_candidates=3,
            ),
        ),
        ToolSpec(
            tool_id="rag.l7.answer_ready_context",
            layer_name="L7_ANSWER_READY_CONTEXT",
            allowed_input=("selected_evidence", "rendered_citations", "query_text"),
            forbidden_input=common_forbidden,
            input_schema=_object_schema(
                ("selected_evidence", "rendered_citations", "query_text"),
                {
                    "selected_evidence": {"type": "array", "items": {"type": "object"}},
                    "rendered_citations": {"type": "array", "items": {"type": "string"}},
                    "query_text": {"type": "string"},
                },
            ),
            output_schema=_object_schema(
                ("answer_ready_context", "answerability_from_bounds"),
                {
                    "answer_ready_context": {"type": "string"},
                    "answerability_from_bounds": {"type": "string"},
                },
            ),
            confidence_policy={"policy": "context_readiness_not_user_gold_answerability_label"},
            drop_reasons=("no_selected_evidence", "locator_bounds_unanswerable", "context_cache_key_missing"),
            provenance_requirements=("selected_source_atom_ids", "context_cache_key", "rendered_citations"),
            runtime_contract=_runtime_contract(
                materialization="query_time_cacheable",
                adapter="replay_or_mock_live_runtime_like",
                max_candidates=3,
            ),
        ),
        ToolSpec(
            tool_id="rag.l8.final_llm_answer_generation",
            layer_name="L8_FINAL_LLM_ANSWER_GENERATION",
            allowed_input=("answer_ready_context", "query_text", "rendered_citations"),
            forbidden_input=common_forbidden,
            input_schema=_object_schema(
                ("answer_ready_context", "query_text", "rendered_citations"),
                {
                    "answer_ready_context": {"type": "string"},
                    "query_text": {"type": "string"},
                    "rendered_citations": {"type": "array", "items": {"type": "string"}},
                },
            ),
            output_schema=_object_schema(
                ("answer", "citations", "abstain_reason"),
                {
                    "answer": {"type": "string"},
                    "citations": {"type": "array", "items": {"type": "object"}},
                    "abstain_reason": {"type": "string"},
                },
            ),
            confidence_policy={"policy": "generation_parse_status_only_not_official_quality_score"},
            drop_reasons=("llm_unavailable", "malformed_json", "insufficient_evidence_abstain"),
            provenance_requirements=("prompt_sha256", "selected_source_atom_ids", "rendered_citations"),
            runtime_contract=_runtime_contract(
                materialization="query_time_cacheable",
                adapter="replay_or_mock_live_runtime_like",
                max_candidates=3,
            ),
        ),
    ]
