"""Portfolio-facing AgentOps adapter over the bounded RAG orchestrator.

This module does not add autonomy, production routing, or official scoring. It
maps the existing deterministic RAG runtime into a small AgentOps vocabulary:
tool registry, policy decision, and run-level trace.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.capabilities.rag_orchestrator.agent_runtime import (
    AgentRuntime,
    AgentRuntimeRequest,
    AgentRuntimeResult,
)

AGENTOPS_TRACE_SCHEMA_VERSION = "agentops_run_trace_v1"
AGENTOPS_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_TRACE_EVIDENCE_REFS = 99
DEFAULT_INDEXING_SCOPE = "nonprod_source_derived_read_only"
DEFAULT_REPORT_ARTIFACT_PATH = "reports/portfolio_agentops_report.md"
ALLOWED_REPORT_ARTIFACT_PATHS = (DEFAULT_REPORT_ARTIFACT_PATH,)
TRACE_FAILURE_CATEGORIES = (
    "",
    "ambiguous_file_identity",
    "ambiguous_page_only_locator",
    "ambiguous_sheet_only_locator",
    "ambiguous_workbook_identity",
    "answer_format_blocked",
    "cache_namespace_mismatch",
    "candidate_scope_missing",
    "candidate_scope_source_family_mismatch",
    "context_required",
    "index_namespace_mismatch",
    "index_unavailable",
    "indexing_scope_blocked",
    "insufficient_evidence",
    "location_not_found",
    "missing_evidence",
    "namespace_mismatch",
    "no_candidate_evidence_scope",
    "no_evidence",
    "official_policy_not_opened",
    "out_of_bounds_locator",
    "report_artifact_path_blocked",
    "request_context_malformed",
    "reserved_request_context_key",
    "runtime_contract_violation",
    "runtime_fail_closed",
    "runtime_tool_call_drift",
    "source_atom_hydration_unbounded",
    "source_atom_id_missing_or_unauthorized",
    "source_atom_store_namespace_mismatch",
    "source_atom_store_unavailable",
    "source_family_mismatch",
    "unsupported",
    "unsupported_evidence_only_tool_path",
    "unsupported_locator_format",
    "unsupported_source_family",
    "unsupported_tool",
)
TRACE_RUNTIME_TOOL_CALLS = (
    "rag.l0.query_routing",
    "rag.l1.coarse_candidate_generation",
    "rag.l2.file_workbook_identity",
    "rag.l3.structural_locator",
    "rag.l4.sourceatom_hydration",
    "rag.l5.evidence_bundle_assembly",
    "rag.l6.evidence_selector",
    "rag.l7.answer_ready_context",
    "rag.l8.final_llm_answer_generation",
)

ALLOWED_INDEXING_SCOPES = (DEFAULT_INDEXING_SCOPE,)
ALLOWED_ANSWER_FORMAT_REQUIREMENTS = ("answer_with_citations_or_abstain",)
NONPROD_RETRIEVAL_NAMESPACES = (
    "rag-data-all-source-citable-nonprod-v1",
    "rag-data-all-source-nonprod-v1",
    "rag-data-live-runtime-smoke-nonprod",
)
REPORT_NAMESPACES = ("ai/eval/reports/rag-ingestion/runs",)
SUPPORTED_SOURCE_FAMILIES = ("PDF", "TEXT", "XLSX")
UNSUPPORTED_SOURCE_FAMILY_TRACE_VALUE = "UNSUPPORTED_SOURCE_FAMILY"
UNSUPPORTED_NAMESPACE_TRACE_VALUE = "UNSUPPORTED_NAMESPACE"
UNSUPPORTED_INDEXING_SCOPE_TRACE_VALUE = "UNSUPPORTED_INDEXING_SCOPE"
UNSUPPORTED_ANSWER_FORMAT_TRACE_VALUE = "UNSUPPORTED_ANSWER_FORMAT_REQUIREMENT"
RESERVED_REQUEST_CONTEXT_KEYS = frozenset(
    {
        "namespace",
        "indexing_scope",
        "source_family",
        "official_requested",
        "candidate_source_atom_ids",
        "evidence_ids",
        "requested_tools",
        "query",
        "query_id",
        "run_id",
    }
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _source_family(value: Any) -> str:
    return _clean(value).upper()


def _registry_source_family(record: Any) -> str:
    if not isinstance(record, MappingABC):
        return ""
    return _source_family(record.get("source_family"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_clean(value).encode("utf-8")).hexdigest()


def _query_ref(run_id: str) -> str:
    return f"query_ref:{_sha256('agentops-query-ref:' + _clean(run_id))[:16]}"


def _evidence_refs(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"evidence_ref:{index:02d}" for index, _value in enumerate(values, start=1))


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (_clean(values),) if _clean(values) else ()
    return tuple(_clean(value) for value in values if _clean(value))


def _trace_failure_category(value: Any) -> str:
    category = _clean(value)
    if not category:
        return ""
    if category in TRACE_FAILURE_CATEGORIES:
        return category
    if category.upper().startswith("CONTRACT_VIOLATION"):
        return "runtime_contract_violation"
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", category).strip("_").lower()
    if normalized in TRACE_FAILURE_CATEGORIES:
        return normalized
    return "runtime_fail_closed"


def _trace_tools_called(values: Sequence[str]) -> tuple[tuple[str, ...], bool]:
    allowed = set(TRACE_RUNTIME_TOOL_CALLS)
    safe_calls: list[str] = []
    unknown_seen = False
    for value in values:
        call = _clean(value)
        if call in allowed:
            safe_calls.append(call)
        elif call:
            unknown_seen = True
    return tuple(safe_calls), unknown_seen


def _trace_source_family(value: Any) -> str:
    family = _source_family(value)
    return family if family in SUPPORTED_SOURCE_FAMILIES else UNSUPPORTED_SOURCE_FAMILY_TRACE_VALUE


def _trace_namespace(value: Any) -> str:
    namespace = _clean(value)
    allowed = {*NONPROD_RETRIEVAL_NAMESPACES, *REPORT_NAMESPACES}
    return namespace if namespace in allowed else UNSUPPORTED_NAMESPACE_TRACE_VALUE


def _trace_indexing_scope(value: Any) -> str:
    scope = _clean(value)
    return scope if scope in ALLOWED_INDEXING_SCOPES else UNSUPPORTED_INDEXING_SCOPE_TRACE_VALUE


def _trace_answer_format_requirement(value: Any) -> str:
    requirement = _clean(value)
    return requirement if requirement in ALLOWED_ANSWER_FORMAT_REQUIREMENTS else UNSUPPORTED_ANSWER_FORMAT_TRACE_VALUE


@dataclass(frozen=True)
class AgentOpsToolSpec:
    name: str
    description: str
    input_expectation: str
    output_expectation: str
    allowed_namespaces: tuple[str, ...]
    allowed_source_families: tuple[str, ...]
    evidence_required: bool
    mapped_runtime_layers: tuple[str, ...]
    official: bool = False
    diagnostic_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputExpectation": self.input_expectation,
            "outputExpectation": self.output_expectation,
            "allowedNamespaces": list(self.allowed_namespaces),
            "allowedSourceFamilies": list(self.allowed_source_families),
            "evidenceRequired": self.evidence_required,
            "official": self.official,
            "diagnosticOnly": self.diagnostic_only,
            "mappedRuntimeLayers": list(self.mapped_runtime_layers),
        }


def build_agentops_tool_registry() -> tuple[AgentOpsToolSpec, ...]:
    """Return the thin Agent-style tool registry for portfolio/report use."""

    return (
        AgentOpsToolSpec(
            name="retrieve_txt_corpus",
            description="Select candidate TEXT SearchView rows through the bounded non-production RAG runtime.",
            input_expectation="query text plus non-production namespace and TEXT source-family hint",
            output_expectation="candidate SourceAtom ids and trace rows; vector/SearchView payload remains candidate-only",
            allowed_namespaces=NONPROD_RETRIEVAL_NAMESPACES,
            allowed_source_families=("TEXT",),
            evidence_required=False,
            mapped_runtime_layers=("L0_QUERY_ROUTING", "L1_COARSE_CANDIDATE_GENERATION"),
        ),
        AgentOpsToolSpec(
            name="retrieve_xlsx_table",
            description="Select candidate XLSX table/range/cell evidence through query-owned locator or rough-query signals.",
            input_expectation="query text plus XLSX source-family hint, allowed namespace, optional active context",
            output_expectation="candidate SourceAtom ids with XLSX citation metadata; no query-time workbook scan",
            allowed_namespaces=NONPROD_RETRIEVAL_NAMESPACES,
            allowed_source_families=("XLSX",),
            evidence_required=False,
            mapped_runtime_layers=("L0_QUERY_ROUTING", "L1_COARSE_CANDIDATE_GENERATION", "L3_STRUCTURAL_LOCATOR"),
        ),
        AgentOpsToolSpec(
            name="retrieve_pdf_ocr",
            description="Select candidate PDF page/block/OCR evidence while preserving low-trust OCR fail-closed behavior.",
            input_expectation="query text plus PDF source-family hint, allowed namespace, optional active page context",
            output_expectation="candidate SourceAtom ids with PDF page/citation metadata; low-trust OCR is not answer truth",
            allowed_namespaces=NONPROD_RETRIEVAL_NAMESPACES,
            allowed_source_families=("PDF",),
            evidence_required=False,
            mapped_runtime_layers=("L0_QUERY_ROUTING", "L1_COARSE_CANDIDATE_GENERATION", "L3_STRUCTURAL_LOCATOR"),
        ),
        AgentOpsToolSpec(
            name="validate_evidence",
            description="Hydrate SourceAtom ids into EvidenceBundle truth and reject missing, mismatched, or unsafe evidence.",
            input_expectation="bounded SourceAtom ids already selected by an allowed retrieval tool",
            output_expectation="validated EvidenceBundle ids or fail-closed reason",
            allowed_namespaces=NONPROD_RETRIEVAL_NAMESPACES,
            allowed_source_families=SUPPORTED_SOURCE_FAMILIES,
            evidence_required=True,
            mapped_runtime_layers=("L4_SOURCEATOM_HYDRATION", "L5_EVIDENCE_BUNDLE_ASSEMBLY", "L6_EVIDENCE_SELECTOR"),
        ),
        AgentOpsToolSpec(
            name="classify_answerability",
            description="Classify bounded-context answerability as diagnostic machine policy, not human gold truth.",
            input_expectation="validated evidence bundle state and answer-ready context status",
            output_expectation="diagnostic answerability gate state with relevance left unjudged without user gold",
            allowed_namespaces=NONPROD_RETRIEVAL_NAMESPACES,
            allowed_source_families=SUPPORTED_SOURCE_FAMILIES,
            evidence_required=True,
            mapped_runtime_layers=("L7_ANSWER_READY_CONTEXT", "L8_FINAL_LLM_ANSWER_GENERATION"),
        ),
        AgentOpsToolSpec(
            name="generate_eval_report",
            description="Summarize diagnostic run decisions into report/status artifacts without creating official rows.",
            input_expectation="run trace, policy decision, and existing eval report references",
            output_expectation="portfolio/report entry; official metric inputs remain zero unless user-owned gates open",
            allowed_namespaces=REPORT_NAMESPACES,
            allowed_source_families=SUPPORTED_SOURCE_FAMILIES,
            evidence_required=False,
            mapped_runtime_layers=("report.json", "status.jsonl"),
        ),
    )


def _tool_specs_by_name() -> dict[str, AgentOpsToolSpec]:
    return {spec.name: spec for spec in build_agentops_tool_registry()}


def _trace_selected_tools(values: Sequence[str], *, failure_category: str = "") -> tuple[str, ...]:
    if failure_category == "unsupported_tool":
        return ()
    allowed = _tool_specs_by_name()
    return tuple(name for name in values if name in allowed)


def _default_tools_for_family(source_family: str) -> tuple[str, ...]:
    family = _source_family(source_family)
    if family == "TEXT":
        retrieval = "retrieve_txt_corpus"
    elif family == "XLSX":
        retrieval = "retrieve_xlsx_table"
    elif family == "PDF":
        retrieval = "retrieve_pdf_ocr"
    else:
        return ()
    return (retrieval, "validate_evidence", "classify_answerability")


def _normalize_selected_tools_for_runtime(selected_tools: Sequence[str]) -> tuple[str, ...]:
    selected = tuple(selected_tools)
    retrieval_tools = tuple(name for name in selected if name.startswith("retrieve_"))
    if len(retrieval_tools) != 1:
        return selected
    runtime_chain = (retrieval_tools[0], "validate_evidence", "classify_answerability")
    extras = tuple(name for name in selected if name not in runtime_chain)
    return runtime_chain + extras


@dataclass(frozen=True)
class AgentOpsRequestContext:
    run_id: str
    query: str
    source_family: str
    namespace: str
    indexing_scope: str = DEFAULT_INDEXING_SCOPE
    query_id: str = ""
    requested_tools: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    candidate_source_atom_ids: tuple[str, ...] = ()
    request_context: Mapping[str, Any] = field(default_factory=dict)
    official_requested: bool = False
    answer_format_requirement: str = "answer_with_citations_or_abstain"

    def __post_init__(self) -> None:
        run_id = _clean(self.run_id)
        if not AGENTOPS_RUN_ID_RE.fullmatch(run_id):
            raise ValueError("run_id must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
        query_id = _clean(self.query_id)
        if query_id and not AGENTOPS_RUN_ID_RE.fullmatch(query_id):
            raise ValueError("query_id must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "query_id", query_id)
        object.__setattr__(self, "requested_tools", _as_tuple(self.requested_tools))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "candidate_source_atom_ids", _as_tuple(self.candidate_source_atom_ids))


@dataclass(frozen=True)
class AgentOpsPolicyDecision:
    allowed: bool
    selected_tools: tuple[str, ...]
    policy_decision: str
    diagnostic_only: bool
    fail_closed: bool
    failure_category: str = ""
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "selected_tools": list(self.selected_tools),
            "policy_decision": self.policy_decision,
            "diagnostic_only": self.diagnostic_only,
            "fail_closed": self.fail_closed,
            "failure_category": self.failure_category,
            "reasons": list(self.reasons),
        }


class AgentOpsPolicy:
    """Fail-closed policy for the AgentOps adapter.

    Ambiguous official/gold decisions are downgraded to diagnostic-only. Unsafe
    namespace, unsupported family, or missing preselected evidence for pure
    evidence tools fail closed.
    """

    def __init__(self, registry: Sequence[AgentOpsToolSpec] | None = None) -> None:
        self._specs = {spec.name: spec for spec in (registry or build_agentops_tool_registry())}

    def decide(self, context: AgentOpsRequestContext) -> AgentOpsPolicyDecision:
        family = _source_family(context.source_family)
        selected = _normalize_selected_tools_for_runtime(context.requested_tools or _default_tools_for_family(family))
        if family not in SUPPORTED_SOURCE_FAMILIES:
            return self._fail("unsupported_source_family", selected, f"unsupported source family: {family or '<blank>'}")
        unknown = tuple(name for name in selected if name not in self._specs)
        if unknown:
            return self._fail("unsupported_tool", selected, "unsupported tool(s): " + ", ".join(unknown))
        if not isinstance(context.request_context, MappingABC):
            return self._fail("request_context_malformed", selected, "request_context must be a bounded mapping")
        reserved = tuple(sorted(set(context.request_context) & RESERVED_REQUEST_CONTEXT_KEYS))
        if reserved:
            return self._fail(
                "reserved_request_context_key",
                selected,
                "request_context cannot override policy-owned key(s): " + ", ".join(reserved),
            )
        for name in selected:
            spec = self._specs[name]
            if family not in spec.allowed_source_families:
                return self._fail("source_family_mismatch", selected, f"{name} does not allow {family}")
            if context.namespace not in spec.allowed_namespaces:
                return self._fail("namespace_mismatch", selected, f"{context.namespace} is not allowed for {name}")
        if context.indexing_scope not in ALLOWED_INDEXING_SCOPES:
            return self._fail("indexing_scope_blocked", selected, f"{context.indexing_scope} is not an allowed read-only indexing scope")
        if context.answer_format_requirement not in ALLOWED_ANSWER_FORMAT_REQUIREMENTS:
            return self._fail(
                "answer_format_blocked",
                selected,
                f"{context.answer_format_requirement} is not an allowed answer format requirement",
            )

        retrieval_selected = any(name.startswith("retrieve_") for name in selected)
        existing_evidence_required = any(self._specs[name].evidence_required for name in selected) and not retrieval_selected
        if existing_evidence_required:
            if not context.evidence_ids:
                return self._fail("missing_evidence", selected, "evidence-required tool requested without evidence ids")
            return self._fail(
                "unsupported_evidence_only_tool_path",
                selected,
                "evidence-only tool requests are blocked until the runtime wrapper supports them",
            )
        if context.official_requested:
            return self._fail(
                "official_policy_not_opened",
                selected,
                "official scoring requires user-owned gold/qrels/denominator approval",
            )
        return AgentOpsPolicyDecision(
            allowed=True,
            selected_tools=tuple(selected),
            policy_decision="allow_diagnostic",
            diagnostic_only=True,
            fail_closed=False,
            reasons=("non-production diagnostic policy satisfied",),
        )

    def _fail(self, category: str, selected_tools: Sequence[str], reason: str) -> AgentOpsPolicyDecision:
        return AgentOpsPolicyDecision(
            allowed=False,
            selected_tools=tuple(selected_tools),
            policy_decision="fail_closed",
            diagnostic_only=True,
            fail_closed=True,
            failure_category=category,
            reasons=(reason,),
        )


@dataclass(frozen=True)
class AgentOpsRunTrace:
    run_id: str
    query: str
    request_context: Mapping[str, Any]
    selected_tools: tuple[str, ...]
    tools_called: tuple[str, ...]
    retrieval_namespace: str
    indexing_scope: str
    evidence_ids: tuple[str, ...]
    answerability_label: str
    answerability_label_source: str
    relevance_label: str
    relevance_label_source: str
    policy_decision: str
    diagnostic_only: bool
    retry_repair_fallback: Mapping[str, Any]
    failure_category: str
    final_decision: str
    report_artifact_path: str = DEFAULT_REPORT_ARTIFACT_PATH
    schema_version: str = AGENTOPS_TRACE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "query": self.query,
            "request_context": dict(self.request_context),
            "selected_tools": list(self.selected_tools),
            "tools_called": list(self.tools_called),
            "retrieval_namespace": self.retrieval_namespace,
            "indexing_scope": self.indexing_scope,
            "evidence_ids": list(self.evidence_ids),
            "answerability_label": self.answerability_label,
            "answerability_label_source": self.answerability_label_source,
            "relevance_label": self.relevance_label,
            "relevance_label_source": self.relevance_label_source,
            "policy_decision": self.policy_decision,
            "diagnostic_only": self.diagnostic_only,
            "retry_repair_fallback": dict(self.retry_repair_fallback),
            "failure_category": self.failure_category,
            "final_decision": self.final_decision,
            "report_artifact_path": self.report_artifact_path,
        }


def retry_repair_fallback_policy(*, final_decision: str, failure_category: str = "") -> dict[str, Any]:
    safe_failure_category = _trace_failure_category(failure_category)
    return {
        "max_retry_count": 1,
        "retry_attempted": False,
        "retry_requires_new_allowed_signal": True,
        "repair_attempted": False,
        "fallback_decision": "fail_closed" if final_decision == "fail_closed" else "not_needed",
        "diagnostic_only_on_ambiguous_answerability": True,
        "unbounded_retry_allowed": False,
        "failure_category": safe_failure_category,
    }


def run_agentops_diagnostic(
    context: AgentOpsRequestContext,
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
    policy: AgentOpsPolicy | None = None,
    runtime: AgentRuntime | None = None,
    report_artifact_path: str = DEFAULT_REPORT_ARTIFACT_PATH,
) -> AgentOpsRunTrace:
    report_artifact_path = _clean(report_artifact_path)
    if report_artifact_path not in ALLOWED_REPORT_ARTIFACT_PATHS:
        blocked = AgentOpsPolicyDecision(
            allowed=False,
            selected_tools=(),
            policy_decision="fail_closed",
            diagnostic_only=True,
            fail_closed=True,
            failure_category="report_artifact_path_blocked",
            reasons=("report artifact path must use the portfolio report artifact",),
        )
        return _trace_from_policy_block(context, blocked, report_artifact_path=DEFAULT_REPORT_ARTIFACT_PATH)

    decision = (policy or AgentOpsPolicy()).decide(context)
    if decision.fail_closed:
        return _trace_from_policy_block(context, decision, report_artifact_path=report_artifact_path)
    if decision.selected_tools == ("generate_eval_report",):
        return _trace_from_report_only(context, decision, report_artifact_path=report_artifact_path)

    candidate_ids = context.candidate_source_atom_ids
    if not candidate_ids:
        blocked = AgentOpsPolicyDecision(
            allowed=False,
            selected_tools=decision.selected_tools,
            policy_decision="fail_closed",
            diagnostic_only=True,
            fail_closed=True,
            failure_category="no_candidate_evidence_scope",
            reasons=("explicit bounded candidate_source_atom_ids are required; broad source registry scan is blocked",),
        )
        return _trace_from_policy_block(context, blocked, report_artifact_path=report_artifact_path)
    candidate_scope_block = _candidate_scope_block_decision(
        context=context,
        source_registry=source_registry,
        selected_tools=decision.selected_tools,
    )
    if candidate_scope_block is not None:
        return _trace_from_policy_block(context, candidate_scope_block, report_artifact_path=report_artifact_path)

    runtime_context = {**dict(context.request_context), "namespace": context.namespace}
    try:
        result = (runtime or AgentRuntime()).invoke(
            AgentRuntimeRequest(
                run_id=context.run_id,
                query_id=context.query_id or context.run_id,
                query_text=context.query,
                source_family=_source_family(context.source_family),
                source_registry=source_registry,
                candidate_source_atom_ids=candidate_ids,
                request_context=runtime_context,
                internal_replay_adapter=True,
            )
        )
    except Exception:
        blocked = AgentOpsPolicyDecision(
            allowed=False,
            selected_tools=decision.selected_tools,
            policy_decision="fail_closed",
            diagnostic_only=True,
            fail_closed=True,
            failure_category="runtime_fail_closed",
            reasons=("runtime invocation failed before a bounded trace result was available",),
        )
        return _trace_from_policy_block(context, blocked, report_artifact_path=report_artifact_path)
    return _trace_from_runtime_result(
        context=context,
        decision=decision,
        result=result,
        report_artifact_path=report_artifact_path,
    )


def _candidate_scope_block_decision(
    *,
    context: AgentOpsRequestContext,
    source_registry: Mapping[str, Mapping[str, Any]],
    selected_tools: Sequence[str],
) -> AgentOpsPolicyDecision | None:
    if not isinstance(source_registry, MappingABC):
        return AgentOpsPolicyDecision(
            allowed=False,
            selected_tools=tuple(selected_tools),
            policy_decision="fail_closed",
            diagnostic_only=True,
            fail_closed=True,
            failure_category="source_atom_store_unavailable",
            reasons=("source_registry must be a bounded source atom mapping",),
        )

    missing_ids = tuple(source_atom_id for source_atom_id in context.candidate_source_atom_ids if source_atom_id not in source_registry)
    if missing_ids:
        return AgentOpsPolicyDecision(
            allowed=False,
            selected_tools=tuple(selected_tools),
            policy_decision="fail_closed",
            diagnostic_only=True,
            fail_closed=True,
            failure_category="candidate_scope_missing",
            reasons=("candidate_source_atom_ids must exist in the bounded source registry",),
        )

    request_family = _source_family(context.source_family)
    mismatched = tuple(
        source_atom_id
        for source_atom_id in context.candidate_source_atom_ids
        if _registry_source_family(source_registry[source_atom_id]) != request_family
    )
    if mismatched:
        return AgentOpsPolicyDecision(
            allowed=False,
            selected_tools=tuple(selected_tools),
            policy_decision="fail_closed",
            diagnostic_only=True,
            fail_closed=True,
            failure_category="candidate_scope_source_family_mismatch",
            reasons=("candidate source family must match the request source family",),
        )
    return None


def _trace_from_policy_block(
    context: AgentOpsRequestContext,
    decision: AgentOpsPolicyDecision,
    *,
    report_artifact_path: str,
) -> AgentOpsRunTrace:
    failure_category = _trace_failure_category(decision.failure_category)
    return AgentOpsRunTrace(
        run_id=context.run_id,
        query=_query_ref(context.run_id),
        request_context=_trace_request_context(context),
        selected_tools=_trace_selected_tools(decision.selected_tools, failure_category=failure_category),
        tools_called=(),
        retrieval_namespace=_trace_namespace(context.namespace),
        indexing_scope=_trace_indexing_scope(context.indexing_scope),
        evidence_ids=(),
        answerability_label="diagnostic_unanswerable_from_bounds",
        answerability_label_source="machine_policy_not_gold",
        relevance_label="",
        relevance_label_source="not_evaluated_without_user_gold",
        policy_decision=decision.policy_decision,
        diagnostic_only=True,
        retry_repair_fallback=retry_repair_fallback_policy(
            final_decision="fail_closed",
            failure_category=failure_category,
        ),
        failure_category=failure_category,
        final_decision="fail_closed",
        report_artifact_path=report_artifact_path,
    )


def _trace_from_report_only(
    context: AgentOpsRequestContext,
    decision: AgentOpsPolicyDecision,
    *,
    report_artifact_path: str,
) -> AgentOpsRunTrace:
    return AgentOpsRunTrace(
        run_id=context.run_id,
        query=_query_ref(context.run_id),
        request_context=_trace_request_context(context),
        selected_tools=_trace_selected_tools(decision.selected_tools),
        tools_called=(),
        retrieval_namespace=_trace_namespace(context.namespace),
        indexing_scope=_trace_indexing_scope(context.indexing_scope),
        evidence_ids=(),
        answerability_label="diagnostic_unanswerable_from_bounds",
        answerability_label_source="machine_policy_not_gold",
        relevance_label="",
        relevance_label_source="not_evaluated_without_user_gold",
        policy_decision=decision.policy_decision,
        diagnostic_only=True,
        retry_repair_fallback=retry_repair_fallback_policy(
            final_decision="diagnostic_only_handoff",
            failure_category="",
        ),
        failure_category="",
        final_decision="diagnostic_only_handoff",
        report_artifact_path=report_artifact_path,
    )


def _trace_from_runtime_result(
    *,
    context: AgentOpsRequestContext,
    decision: AgentOpsPolicyDecision,
    result: AgentRuntimeResult,
    report_artifact_path: str,
) -> AgentOpsRunTrace:
    tools_called, unknown_tool_call_seen = _trace_tools_called(result.tool_call_sequence)
    if unknown_tool_call_seen:
        answerability = "diagnostic_unanswerable_from_bounds"
        final_decision = "fail_closed"
        failure_category = "runtime_tool_call_drift"
        evidence_ids = ()
    elif result.runtime_contract_violation:
        answerability = "diagnostic_unanswerable_from_bounds"
        final_decision = "fail_closed"
        failure_category = _trace_failure_category(result.fail_closed_reason or "runtime_contract_violation")
        evidence_ids = ()
    elif len(result.evidence_bundle_ids) > MAX_TRACE_EVIDENCE_REFS:
        answerability = "diagnostic_unanswerable_from_bounds"
        final_decision = "fail_closed"
        failure_category = "runtime_contract_violation"
        evidence_ids = ()
    elif result.answer_allowed_by_policy and result.evidence_bundle_ids:
        answerability = "diagnostic_answerable_from_bounds"
        final_decision = "diagnostic_only_answer"
        failure_category = _trace_failure_category(decision.failure_category)
        evidence_ids = _evidence_refs(result.evidence_bundle_ids)
    else:
        answerability = "diagnostic_unanswerable_from_bounds"
        final_decision = "fail_closed"
        failure_category = _trace_failure_category(
            _clean(result.fail_closed_reason)
            or _clean(result.blocked_reason)
            or _clean(result.response_policy_bucket)
            or "no_evidence"
        )
        evidence_ids = _evidence_refs(result.evidence_bundle_ids)
    return AgentOpsRunTrace(
        run_id=context.run_id,
        query=_query_ref(context.run_id),
        request_context=_trace_request_context(context),
        selected_tools=_trace_selected_tools(decision.selected_tools),
        tools_called=tools_called,
        retrieval_namespace=_trace_namespace(context.namespace),
        indexing_scope=_trace_indexing_scope(context.indexing_scope),
        evidence_ids=evidence_ids,
        answerability_label=answerability,
        answerability_label_source="machine_policy_not_gold",
        relevance_label="",
        relevance_label_source="not_evaluated_without_user_gold",
        policy_decision=decision.policy_decision,
        diagnostic_only=True,
        retry_repair_fallback=retry_repair_fallback_policy(
            final_decision=final_decision,
            failure_category=failure_category,
        ),
        failure_category=failure_category,
        final_decision=final_decision,
        report_artifact_path=report_artifact_path,
    )


def _trace_request_context(context: AgentOpsRequestContext) -> dict[str, Any]:
    return {
        "source_family": _trace_source_family(context.source_family),
        "namespace": _trace_namespace(context.namespace),
        "indexing_scope": _trace_indexing_scope(context.indexing_scope),
        "answer_format_requirement": _trace_answer_format_requirement(context.answer_format_requirement),
        "official_requested": context.official_requested,
    }
