from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Mapping, Sequence


LAYERED_RETRIEVAL_SCHEMA_VERSION = "layered_retrieval_trace_v1"
LAYER_NAMES = (
    "L0_QUERY_ROUTING",
    "L1_COARSE_CANDIDATE_GENERATION",
    "L2_FILE_WORKBOOK_IDENTITY",
    "L3_STRUCTURAL_LOCATOR",
    "L4_SOURCEATOM_HYDRATION",
    "L5_EVIDENCE_BUNDLE_ASSEMBLY",
    "L6_EVIDENCE_SELECTOR",
    "L7_ANSWER_READY_CONTEXT",
    "L9_METRICS_FAILURE_TAXONOMY",
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _unique_sorted(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


@dataclass(frozen=True)
class LayerCandidate:
    candidate_id: str
    source_family: str
    layer_name: str
    source_atom_id: str = ""
    search_view_id: str = ""
    source_identity: str = ""
    document_version_id: str = ""
    workbook_id: str = ""
    source_file_name: str = ""
    sheet_name: str = ""
    table_range: str = ""
    cell: str = ""
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    score_components: Mapping[str, Any] = field(default_factory=dict)
    guardrail_flags: tuple[str, ...] = ()
    failure_bucket: str = ""
    diagnostic_only: bool = True
    source_atom_hydrated_from_registry: bool = False
    evidence_bundle_assembled: bool = False
    vector_payload_used_as_evidence_truth: bool = False
    canonical_payload_source: str = "source_registry"

    def to_json(self) -> dict[str, Any]:
        return _jsonable(self)


@dataclass(frozen=True)
class LayerDecision:
    query_id: str
    source_family: str
    layer_name: str
    selected_candidate_ids: tuple[str, ...] = ()
    candidates: tuple[LayerCandidate, ...] = ()
    signals: Mapping[str, Any] = field(default_factory=dict)
    guardrail_flags: tuple[str, ...] = ()
    failure_bucket: str = ""
    abstain_or_disambiguate: bool = False
    diagnostic_only: bool = True
    used_gold_or_expected_text: bool = False
    used_answer_value_shortcut: bool = False
    direct_normalized_value_query_matching_used: bool = False
    source_atom_hydrated_from_registry: bool = False
    evidence_bundle_assembled: bool = False
    vector_payload_used_as_evidence_truth: bool = False
    headline_eligible: bool = True

    def to_json(self) -> dict[str, Any]:
        payload = _jsonable(self)
        payload["candidates"] = [candidate.to_json() for candidate in self.candidates]
        return payload


@dataclass(frozen=True)
class QueryRouteDecision(LayerDecision):
    query_text_sha256: str = ""
    intent_type: str = "unknown"
    routed_by: str = "requested_family_or_surface_hint"


@dataclass(frozen=True)
class LayeredRetrievalTrace:
    query_id: str
    query_text_sha256: str
    source_family: str
    decisions: tuple[LayerDecision, ...]
    diagnostic_only: bool = True
    used_gold_or_expected_text: bool = False
    used_answer_value_shortcut: bool = False
    direct_normalized_value_query_matching_used: bool = False
    product_success_evidence_allowed: bool = False

    def to_json(self) -> dict[str, Any]:
        return serialize_layered_trace(self)


def route_query_for_layered_retrieval(
    *,
    query_id: str,
    query_text: str,
    requested_family: str | None = None,
) -> QueryRouteDecision:
    text = query_text or ""
    lowered = text.lower()
    family = (requested_family or "").upper()
    if family not in {"PDF", "XLSX"}:
        if ".xlsx" in lowered or "sheet" in lowered or "cell" in lowered or re.search(r"\b[A-Z]{1,3}\d+\b", text):
            family = "XLSX"
        elif ".pdf" in lowered or "page" in lowered or "section" in lowered:
            family = "PDF"
        else:
            family = "UNKNOWN"

    if family == "XLSX" and (re.search(r"\b[A-Z]{1,3}\d+\b", text) or "cell" in lowered):
        intent = "cell_or_value_lookup"
    elif family == "XLSX" and ("table" in lowered or "range" in lowered):
        intent = "table_or_range_lookup"
    elif family == "XLSX" and "sheet" in lowered:
        intent = "sheet_lookup"
    elif family == "PDF" and ("page" in lowered or "bbox" in lowered or "section" in lowered):
        intent = "page_or_block_lookup"
    elif family == "PDF":
        intent = "pdf_document_lookup"
    else:
        intent = "unknown"

    flags: list[str] = []
    if ".pdf" in lowered or ".xlsx" in lowered:
        flags.append("file_title_leak")
    if re.search(r"\b[A-Z]{1,3}\d+\b", text) or " sheet " in f" {lowered} " or " cell " in f" {lowered} ":
        flags.append("unnatural_sheet_or_cell_reference")
    if re.search(r"\banswer\s*(is|:)", lowered):
        flags.append("answer_value_in_query")
    if family == "UNKNOWN":
        flags.append("source_family_ambiguous")

    guardrail_flags = _unique_sorted(flags)
    return QueryRouteDecision(
        query_id=query_id,
        source_family=family,
        layer_name="L0_QUERY_ROUTING",
        selected_candidate_ids=(),
        candidates=(),
        signals={"requested_family": requested_family or "", "query_text_sha256": _sha256_text(text)},
        guardrail_flags=guardrail_flags,
        query_text_sha256=_sha256_text(text),
        intent_type=intent,
        direct_normalized_value_query_matching_used=False,
        used_gold_or_expected_text=False,
        used_answer_value_shortcut=False,
        headline_eligible=not bool(guardrail_flags),
    )


def serialize_layered_trace(trace: LayeredRetrievalTrace) -> dict[str, Any]:
    return {
        "schema_version": LAYERED_RETRIEVAL_SCHEMA_VERSION,
        "query_id": trace.query_id,
        "query_text_sha256": trace.query_text_sha256,
        "source_family": trace.source_family,
        "diagnostic_only": trace.diagnostic_only,
        "used_gold_or_expected_text": trace.used_gold_or_expected_text,
        "used_answer_value_shortcut": trace.used_answer_value_shortcut,
        "direct_normalized_value_query_matching_used": trace.direct_normalized_value_query_matching_used,
        "product_success_evidence_allowed": trace.product_success_evidence_allowed,
        "decisions": [decision.to_json() for decision in trace.decisions],
    }

