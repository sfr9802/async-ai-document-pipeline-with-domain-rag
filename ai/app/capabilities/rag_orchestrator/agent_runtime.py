"""Non-production ToolRegistry-only agent runtime for bounded RAG tools."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.capabilities.rag.source_registry import assemble_evidence_bundle
from app.capabilities.rag_orchestrator.runtime_adapters import (
    DEFAULT_TIMEOUT_MS,
    RuntimeAdapterAuditContext,
    RuntimeCacheContract,
    SearchIndexContract,
    SourceAtomStoreContract,
    cache_key_for_query,
)
from app.capabilities.rag_orchestrator.tool_registry import (
    LAYER_NAMES,
    ROUTE_HYBRID,
    ROUTE_ROUGH_QUERY,
    ROUTE_UNSUPPORTED,
    ROUTE_USER_LOCATOR,
    ToolRegistry,
    ToolSpec,
    build_default_tool_registry,
)

TRACE_SCHEMA_VERSION = "rag_agent_tool_call_trace_v1"
INPUT_SCHEMA_VERSION = "rag_tool_spec_v1.input.v1"
OUTPUT_SCHEMA_VERSION = "rag_tool_spec_v1.output.v1"
EVIDENCE_TRUTH_SOURCE = "source_atom_evidence_bundle"
NO_EVIDENCE_TRUTH_SOURCE = "none"

RUNTIME_CONTRACT_GUARDS = (
    "raw_pdf_xlsx_query_time_parse",
    "full_workbook_sheet_scan",
    "full_pdf_page_block_scan",
    "broad_source_atom_scan",
    "vector_payload_used_as_evidence_truth",
    "target_locator_used",
    "gold_locator_used",
    "supporting_evidence_used",
    "expected_answer_used",
    "direct_normalized_answer_value_query_matching",
    "unbounded_fallback",
)

USER_LOCATOR_BUCKETS = (
    "LOCATION_FOUND",
    "BOUNDED_BROAD_RANGE",
    "AMBIGUOUS_FILE_IDENTITY",
    "AMBIGUOUS_WORKBOOK_IDENTITY",
    "AMBIGUOUS_PAGE_ONLY_LOCATOR",
    "AMBIGUOUS_SHEET_ONLY_LOCATOR",
    "LOCATION_NOT_FOUND",
    "OUT_OF_BOUNDS_LOCATOR",
    "UNSUPPORTED_LOCATOR_FORMAT",
    "CONTEXT_REQUIRED",
    "CONTRACT_VIOLATION",
    "NO_USER_LOCATOR",
)

AMBIGUOUS_LOCATOR_BUCKETS = (
    "AMBIGUOUS_FILE_IDENTITY",
    "AMBIGUOUS_WORKBOOK_IDENTITY",
    "AMBIGUOUS_PAGE_ONLY_LOCATOR",
    "AMBIGUOUS_SHEET_ONLY_LOCATOR",
)

DEICTIC_PATTERNS = (
    "이 표",
    "이거",
    "그 페이지",
    "이 페이지",
    "이 파일",
    "방금 것",
    "여기",
    "선택한 범위",
    "선택 범위",
    "선택된 범위",
    "선택 영역",
    "이 문서",
    "그 문서",
    "해당 문서",
    "현재 문서",
    "해당 표",
    "현재 표",
    "위 표",
    "해당 파일",
    "현재 파일",
    "이 셀",
    "해당 셀",
)


@dataclass(frozen=True)
class AgentRuntimeRequest:
    query_id: str
    query_text: str
    source_family: str
    source_registry: Mapping[str, Mapping[str, Any]]
    candidate_source_atom_ids: Sequence[str] = ()
    diagnostic_case_id: str = ""
    run_id: str = "agent_runtime_nonprod"
    rough_query_hint: bool = False
    artifact_context: Mapping[str, Any] = field(default_factory=dict)
    request_context: Mapping[str, Any] = field(default_factory=dict)
    runtime_flags: Mapping[str, Any] = field(default_factory=dict)
    internal_replay_adapter: bool = False


@dataclass(frozen=True)
class AgentRuntimeResult:
    run_id: str
    query_id: str
    diagnostic_case_id: str
    route_lane: str
    agent_route: str
    final_answer: str
    selected_source_atom_ids: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...]
    trace_rows: tuple[dict[str, Any], ...]
    tool_call_sequence: list[str]
    runtime_contract_violation: bool
    fail_closed_reason: str
    blocked_reason: str
    locator_resolution_bucket: str
    locator_bounds_answerability: str
    response_policy_bucket: str
    answer_allowed_by_policy: bool
    user_clarification_required: bool
    ambiguity_requires_clarification: bool
    active_context_required: bool
    active_context_present: bool
    deictic_query: bool
    page_only_locator: bool
    sheet_only_locator: bool
    final_answer_policy: str
    evidence_truth_source: str
    abstained: bool
    runtime_adapter_trace_rows: tuple[dict[str, Any], ...] = ()
    db_contract_status: str = "not_configured"
    index_contract_status: str = "not_configured"
    cache_contract_status: str = "not_configured"
    cache_hit: bool = False
    cache_key_namespace: str = ""
    adapter_fail_closed_reason: str = ""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", _clean(value).casefold())


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _locator(atom: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(_as_mapping(atom.get("canonical_citation_payload")))
    merged.update({key: value for key, value in _as_mapping(atom.get("raw_locator")).items() if _clean(value)})
    return merged


def _range_contains_cell(range_text: str, cell: str) -> bool:
    match = re.match(r"^([A-Z]{1,3})([1-9][0-9]*):([A-Z]{1,3})([1-9][0-9]*)$", _clean(range_text).upper())
    cell_match = re.match(r"^([A-Z]{1,3})([1-9][0-9]*)$", _clean(cell).upper())
    if not match or not cell_match:
        return False

    def col_num(col: str) -> int:
        value = 0
        for char in col:
            value = value * 26 + (ord(char) - ord("A") + 1)
        return value

    left_col, top_row, right_col, bottom_row = match.groups()
    cell_col, cell_row = cell_match.groups()
    col = col_num(cell_col)
    row = int(cell_row)
    return col_num(left_col) <= col <= col_num(right_col) and int(top_row) <= row <= int(bottom_row)


def is_deictic_query(query_text: str) -> bool:
    normalized = _norm(query_text)
    return any(_norm(pattern) in normalized for pattern in DEICTIC_PATTERNS)


def parse_query_locator(query_text: str) -> dict[str, Any]:
    query = _clean(query_text)
    ranges = _unique(re.findall(r"\b[A-Z]{1,3}[1-9][0-9]{0,6}:[A-Z]{1,3}[1-9][0-9]{0,6}\b", query.upper()))
    query_without_ranges = query
    for range_text in ranges:
        query_without_ranges = re.sub(re.escape(range_text), " ", query_without_ranges, flags=re.IGNORECASE)
    cells = _unique(re.findall(r"\b[A-Z]{1,3}[1-9][0-9]{0,6}\b", query_without_ranges.upper()))
    files = _unique(re.findall(r"([A-Za-z0-9가-힣_(). \-]+?\.(?:xlsx|pdf))", query, flags=re.IGNORECASE))
    sheets = _unique(
        [
            *re.findall(
                r"(?:시트|sheet)\s*[:=]?\s*['\"]?([^'\"!,;]+?)(?=\s*(?:셀|cell|범위|range|값|의|에서|$))",
                query,
                flags=re.IGNORECASE,
            ),
            *re.findall(r"([A-Za-z0-9가-힣_ \-]{1,40})\s*(?:시트|sheet)", query, flags=re.IGNORECASE),
        ]
    )
    pages = _unique(
        item
        for pair in re.findall(r"(?:page|p\.?|쪽|페이지)\s*([0-9]{1,4})|([0-9]{1,4})\s*(?:쪽|페이지)", query, flags=re.IGNORECASE)
        for item in pair
        if item
    )
    sections = _unique(
        re.findall(r"(?:절|섹션|section)\s*[:=]?\s*([A-Za-z0-9가-힣_ \-]{1,50})", query, flags=re.IGNORECASE)
    )
    unsupported = bool(re.search(r"(?:셀|cell|범위|range|페이지|page|section|시트|sheet)", query, flags=re.IGNORECASE)) and not any(
        (files, sheets, cells, ranges, pages, sections)
    )
    locator_types = []
    for name, values in (
        ("file", files),
        ("sheet", sheets),
        ("cell", cells),
        ("range", ranges),
        ("page", pages),
        ("section", sections),
    ):
        if values:
            locator_types.append(name)
    return {
        "query_user_provided_locator": bool(locator_types) or unsupported,
        "unsupported_locator_format": unsupported,
        "deictic_query": is_deictic_query(query),
        "page_only_locator": bool(pages) and not files and not sheets and not cells and not ranges and not sections,
        "sheet_only_locator": bool(sheets) and not files and not pages and not cells and not ranges and not sections,
        "locator_terms": {
            "file": files,
            "sheet": sheets,
            "cell": cells,
            "range": ranges,
            "page": pages,
            "section": sections,
        },
        "locator_text": " | ".join(_unique([*files, *sheets, *cells, *ranges, *pages, *sections])),
    }


def _unique(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = _clean(value)
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


class AgentRuntime:
    def __init__(
        self,
        *,
        registry: ToolRegistry | None = None,
        search_index: SearchIndexContract | None = None,
        source_atom_store: SourceAtomStoreContract | None = None,
        runtime_cache: RuntimeCacheContract | None = None,
    ) -> None:
        self.registry = registry or build_default_tool_registry()
        self._spec_by_layer = {spec.layer_name: spec for spec in self.registry.tool_specs()}
        self.search_index = search_index
        self.source_atom_store = source_atom_store
        self.runtime_cache = runtime_cache

    def invoke(self, request: AgentRuntimeRequest) -> AgentRuntimeResult:
        violation = self._contract_violation(request)
        parsed_locator = parse_query_locator(request.query_text)
        active_context_ids = self._active_source_atom_ids(request)
        initial_candidate_ids = tuple(active_context_ids or request.candidate_source_atom_ids)
        supported_family = _clean(request.source_family).upper() in {"PDF", "XLSX", "TEXT"}
        rough_query_present = bool(request.rough_query_hint) or (
            bool(_clean(request.query_text)) and not parsed_locator["query_user_provided_locator"]
        )
        route = self.registry.route_policy(
            user_locator_present=bool(parsed_locator["query_user_provided_locator"]),
            rough_query_present=rough_query_present,
            supported_source_family=supported_family and not violation,
        )
        if violation:
            route_lane = ROUTE_UNSUPPORTED
            fail_closed_reason = f"CONTRACT_VIOLATION:{violation}"
        else:
            route_lane = route.route_lane
            fail_closed_reason = "" if route.route_lane != ROUTE_UNSUPPORTED else route.reason

        state: dict[str, Any] = {
            "request": request,
            "route_lane": route_lane,
            "route_policy_reason": route.reason,
            "selected_tool_ids": set(route.selected_tool_ids),
            "parsed_locator": parsed_locator,
            "candidate_ids": initial_candidate_ids,
            "active_context_ids": active_context_ids,
            "active_context_present": bool(active_context_ids),
            "active_context_required": bool(parsed_locator["deictic_query"]),
            "deictic_query": bool(parsed_locator["deictic_query"]),
            "page_only_locator": bool(parsed_locator["page_only_locator"]),
            "sheet_only_locator": bool(parsed_locator["sheet_only_locator"]),
            "selected_source_atom_ids": (),
            "evidence_bundle_ids": (),
            "evidence_text": "",
            "confidence": 0.0,
            "drop_reason": "",
            "blocked_reason": "",
            "locator_resolution_bucket": "NO_USER_LOCATOR",
            "locator_bounds_answerability": "NOT_USER_LOCATOR",
            "response_policy_bucket": "PENDING",
            "answer_allowed_by_policy": False,
            "user_clarification_required": False,
            "ambiguity_requires_clarification": False,
            "final_answer_policy": "",
            "evidence_truth_source": NO_EVIDENCE_TRUTH_SOURCE,
            "runtime_contract_violation": bool(violation),
            "fail_closed_reason": fail_closed_reason,
            "final_answer": "",
            "abstained": False,
            "runtime_source_registry": dict(request.source_registry),
            "runtime_adapter_trace_rows": [],
            "search_view_ids": (),
            "db_contract_status": "not_configured",
            "index_contract_status": "not_configured",
            "cache_contract_status": "not_configured",
            "cache_hit": False,
            "cache_key_namespace": _clean(_as_mapping(request.request_context).get("cache_namespace")),
            "cache_key": "",
            "adapter_fail_closed_reason": "",
        }
        trace_rows: list[dict[str, Any]] = []
        layers = ("L0_QUERY_ROUTING",) if route_lane == ROUTE_UNSUPPORTED else LAYER_NAMES
        parent_id = ""
        for index, layer_name in enumerate(layers, start=1):
            spec = self._spec_by_layer[layer_name]
            if layer_name != "L0_QUERY_ROUTING" and spec.tool_id not in state["selected_tool_ids"]:
                continue
            started = time.perf_counter()
            self._execute_spec(spec, state)
            latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            tool_call_id = f"{request.query_id or request.diagnostic_case_id}:{index:02d}:{layer_name}"
            row = self._trace_row(
                request=request,
                spec=spec,
                tool_call_id=tool_call_id,
                parent_tool_call_id=parent_id,
                latency_ms=latency_ms,
                state=state,
            )
            trace_rows.append(row)
            parent_id = tool_call_id

        if not state["final_answer"]:
            self._finalize_answer(state)
            if trace_rows:
                trace_rows[-1]["source_atom_ids"] = list(state["selected_source_atom_ids"])
                trace_rows[-1]["evidence_bundle_ids"] = list(state["evidence_bundle_ids"])
                trace_rows[-1]["drop_reason"] = state["drop_reason"]
                trace_rows[-1]["fail_closed_reason"] = state["fail_closed_reason"]

        return AgentRuntimeResult(
            run_id=request.run_id,
            query_id=request.query_id,
            diagnostic_case_id=request.diagnostic_case_id,
            route_lane=route_lane,
            agent_route=route_lane,
            final_answer=state["final_answer"],
            selected_source_atom_ids=tuple(state["selected_source_atom_ids"]),
            evidence_bundle_ids=tuple(state["evidence_bundle_ids"]),
            trace_rows=tuple(trace_rows),
            tool_call_sequence=[row["tool_name"] for row in trace_rows],
            runtime_contract_violation=bool(state["runtime_contract_violation"]),
            fail_closed_reason=_clean(state["fail_closed_reason"]),
            blocked_reason=_clean(state["blocked_reason"]),
            locator_resolution_bucket=_clean(state["locator_resolution_bucket"]),
            locator_bounds_answerability=_clean(state["locator_bounds_answerability"]),
            response_policy_bucket=_clean(state["response_policy_bucket"]),
            answer_allowed_by_policy=bool(state["answer_allowed_by_policy"]),
            user_clarification_required=bool(state["user_clarification_required"]),
            ambiguity_requires_clarification=bool(state["ambiguity_requires_clarification"]),
            active_context_required=bool(state["active_context_required"]),
            active_context_present=bool(state["active_context_present"]),
            deictic_query=bool(state["deictic_query"]),
            page_only_locator=bool(state["page_only_locator"]),
            sheet_only_locator=bool(state["sheet_only_locator"]),
            final_answer_policy=_clean(state["final_answer_policy"]),
            evidence_truth_source=_clean(state["evidence_truth_source"]),
            abstained=bool(state["abstained"]),
            runtime_adapter_trace_rows=tuple(state["runtime_adapter_trace_rows"]),
            db_contract_status=_clean(state["db_contract_status"]),
            index_contract_status=_clean(state["index_contract_status"]),
            cache_contract_status=_clean(state["cache_contract_status"]),
            cache_hit=bool(state["cache_hit"]),
            cache_key_namespace=_clean(state["cache_key_namespace"]),
            adapter_fail_closed_reason=_clean(state["adapter_fail_closed_reason"]),
        )

    def _active_source_atom_ids(self, request: AgentRuntimeRequest) -> tuple[str, ...]:
        context = _as_mapping(request.request_context)
        candidate_scope = set(request.candidate_source_atom_ids)
        if not candidate_scope:
            return ()
        explicit_ids = []
        raw_ids = context.get("active_source_atom_ids")
        if isinstance(raw_ids, str):
            explicit_ids.append(raw_ids)
        elif isinstance(raw_ids, Sequence):
            explicit_ids.extend(str(item) for item in raw_ids)
        if _clean(context.get("active_source_atom_id")):
            explicit_ids.append(_clean(context.get("active_source_atom_id")))
        bounded = []
        for source_atom_id in _unique(explicit_ids):
            if source_atom_id not in request.source_registry and self.source_atom_store is None:
                continue
            if source_atom_id not in candidate_scope:
                continue
            bounded.append(source_atom_id)
        return tuple(bounded)

    def _adapter_namespace(self, request: AgentRuntimeRequest) -> str:
        context = _as_mapping(request.request_context)
        return _clean(context.get("namespace")) or "rag-data-live-runtime-smoke-nonprod"

    def _diagnostic_tenant_id(self, request: AgentRuntimeRequest) -> str:
        context = _as_mapping(request.request_context)
        return _clean(context.get("diagnostic_tenant_id") or context.get("tenant_id")) or "diagnostic-tenant"

    def _adapter_timeout_ms(self, request: AgentRuntimeRequest) -> int:
        context = _as_mapping(request.request_context)
        try:
            value = int(context.get("timeout_ms") or DEFAULT_TIMEOUT_MS)
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT_MS
        return max(value, 1)

    def _adapter_context(self, state: Mapping[str, Any]) -> RuntimeAdapterAuditContext:
        request: AgentRuntimeRequest = state["request"]
        return RuntimeAdapterAuditContext(
            run_id=request.run_id,
            query_id=request.query_id,
            route_lane=_clean(state.get("route_lane")),
            diagnostic_tenant_id=self._diagnostic_tenant_id(request),
            namespace=self._adapter_namespace(request),
            cache_key=_clean(state.get("cache_key")),
            timeout_ms=self._adapter_timeout_ms(request),
        )

    def _record_adapter_result(self, state: dict[str, Any], result: Any) -> None:
        state["runtime_adapter_trace_rows"].append(result.audit_row(self._adapter_context(state)))

    def _source_registry_for_state(self, state: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
        registry = state.get("runtime_source_registry")
        return registry if isinstance(registry, Mapping) else {}

    def _block_adapter_fail_closed(self, state: dict[str, Any], reason: str) -> None:
        state["candidate_ids"] = ()
        state["selected_source_atom_ids"] = ()
        state["evidence_bundle_ids"] = ()
        state["evidence_text"] = ""
        state["evidence_truth_source"] = NO_EVIDENCE_TRUTH_SOURCE
        state["locator_resolution_bucket"] = "CONTRACT_VIOLATION"
        state["locator_bounds_answerability"] = "UNANSWERABLE_FROM_LOCATOR_BOUNDS"
        state["response_policy_bucket"] = "CONTRACT_VIOLATION"
        state["blocked_reason"] = "CONTRACT_VIOLATION"
        state["drop_reason"] = reason.casefold()
        state["fail_closed_reason"] = reason
        state["adapter_fail_closed_reason"] = reason
        state["confidence"] = 0.0

    def _contract_violation(self, request: AgentRuntimeRequest) -> str:
        for guard in RUNTIME_CONTRACT_GUARDS:
            if bool(request.runtime_flags.get(guard)):
                return guard
        return ""

    def _execute_spec(self, spec: ToolSpec, state: dict[str, Any]) -> None:
        layer = spec.layer_name
        if state["runtime_contract_violation"]:
            state["drop_reason"] = "runtime_contract_violation"
            state["blocked_reason"] = "CONTRACT_VIOLATION"
            state["locator_resolution_bucket"] = "CONTRACT_VIOLATION"
            state["locator_bounds_answerability"] = "UNANSWERABLE_FROM_LOCATOR_BOUNDS"
            state["response_policy_bucket"] = "CONTRACT_VIOLATION"
            state["user_clarification_required"] = False
            state["confidence"] = 0.0
            self._finalize_answer(state)
            return
        if layer == "L0_QUERY_ROUTING":
            state["confidence"] = 0.95 if state["route_lane"] != ROUTE_UNSUPPORTED else 0.0
            state["drop_reason"] = "" if state["route_lane"] != ROUTE_UNSUPPORTED else state["fail_closed_reason"]
            self._execute_cache_lookup(state)
            if state["fail_closed_reason"] == "CACHE_NAMESPACE_MISMATCH":
                self._block_adapter_fail_closed(state, "CACHE_NAMESPACE_MISMATCH")
            if state["deictic_query"] and not state["active_context_present"] and state["route_lane"] != ROUTE_UNSUPPORTED:
                self._block_response_policy(
                    state,
                    locator_bucket="CONTEXT_REQUIRED",
                    response_bucket="CONTEXT_REQUIRED",
                    blocked_reason="CONTEXT_REQUIRED",
                    active_context_required=True,
                )
        elif state["blocked_reason"]:
            state["confidence"] = 0.0
            state["drop_reason"] = _clean(state["blocked_reason"]).casefold()
        elif layer == "L1_COARSE_CANDIDATE_GENERATION":
            self._execute_l1(state)
        elif layer == "L2_FILE_WORKBOOK_IDENTITY":
            self._execute_l2(state)
        elif layer == "L3_STRUCTURAL_LOCATOR":
            self._execute_l3(state)
        elif layer == "L4_SOURCEATOM_HYDRATION":
            self._execute_l4(state)
        elif layer == "L5_EVIDENCE_BUNDLE_ASSEMBLY":
            self._execute_l5(state)
        elif layer == "L6_EVIDENCE_SELECTOR":
            self._execute_l6(state)
        elif layer == "L7_ANSWER_READY_CONTEXT":
            self._execute_l7(state)
        elif layer == "L8_FINAL_LLM_ANSWER_GENERATION":
            self._finalize_answer(state)

    def _execute_cache_lookup(self, state: dict[str, Any]) -> None:
        if self.runtime_cache is None:
            return
        request: AgentRuntimeRequest = state["request"]
        context = _as_mapping(request.request_context)
        namespace = _clean(context.get("cache_namespace")) or _clean(state["cache_key_namespace"])
        expected_namespace = _clean(context.get("expected_cache_namespace")) or namespace
        state["cache_key_namespace"] = namespace
        state["cache_key"] = cache_key_for_query(
            run_id=request.run_id,
            query_id=request.query_id,
            namespace=namespace,
        )
        result = self.runtime_cache.get_bundle(
            cache_key=state["cache_key"],
            namespace=namespace,
            expected_namespace=expected_namespace,
            diagnostic_tenant_id=self._diagnostic_tenant_id(request),
            timeout_ms=self._adapter_timeout_ms(request),
        )
        state["cache_contract_status"] = result.status
        state["cache_hit"] = result.cache_hit
        self._record_adapter_result(state, result)
        if result.fail_closed:
            state["fail_closed_reason"] = result.fail_closed_reason
            state["adapter_fail_closed_reason"] = result.fail_closed_reason

    def _execute_l1(self, state: dict[str, Any]) -> None:
        request: AgentRuntimeRequest = state["request"]
        family = _clean(request.source_family).upper()
        if self.search_index is not None:
            index_result = self.search_index.search_candidates(
                query_text=request.query_text,
                source_family=family,
                diagnostic_tenant_id=self._diagnostic_tenant_id(request),
                namespace=self._adapter_namespace(request),
                bounded_source_atom_ids=tuple(state["candidate_ids"]),
                timeout_ms=self._adapter_timeout_ms(request),
            )
            state["index_contract_status"] = index_result.status
            state["search_view_ids"] = tuple(index_result.search_view_ids)
            self._record_adapter_result(state, index_result)
            if index_result.fail_closed:
                self._block_adapter_fail_closed(state, index_result.fail_closed_reason)
                return
            state["candidate_ids"] = tuple(index_result.source_atom_ids)
            if self.source_atom_store is not None and state["candidate_ids"]:
                hydrate_result = self.source_atom_store.hydrate_source_atoms(
                    source_atom_ids=tuple(state["candidate_ids"]),
                    diagnostic_tenant_id=self._diagnostic_tenant_id(request),
                    namespace=self._adapter_namespace(request),
                    timeout_ms=self._adapter_timeout_ms(request),
                )
                state["db_contract_status"] = hydrate_result.status
                self._record_adapter_result(state, hydrate_result)
                if hydrate_result.fail_closed:
                    self._block_adapter_fail_closed(state, hydrate_result.fail_closed_reason)
                    return
                state["runtime_source_registry"].update(dict(hydrate_result.source_atoms))
        candidates = []
        for source_atom_id in state["candidate_ids"]:
            atom = _as_mapping(self._source_registry_for_state(state).get(source_atom_id))
            if atom and _clean(atom.get("source_family")).upper() == family and _context_authorizes_atom(
                source_atom_id,
                atom,
                request_context=request.request_context,
            ):
                candidates.append(source_atom_id)
        state["candidate_ids"] = tuple(candidates)
        state["confidence"] = 0.8 if candidates else 0.0
        state["drop_reason"] = "" if candidates else "no_bounded_candidates"

    def _execute_l2(self, state: dict[str, Any]) -> None:
        terms = state["parsed_locator"]["locator_terms"]
        file_terms = terms.get("file", [])
        if not file_terms:
            state["confidence"] = 0.75 if state["candidate_ids"] else 0.0
            state["drop_reason"] = "" if state["candidate_ids"] else "missing_source_identity"
            return
        request: AgentRuntimeRequest = state["request"]
        kept = [
            source_atom_id
            for source_atom_id in state["candidate_ids"]
            if any(
                _text_matches(
                    term,
                    _locator_values(
                        _as_mapping(self._source_registry_for_state(state).get(source_atom_id)),
                        "workbook",
                        "file_name",
                        "source_path",
                        "source_identity",
                    ),
                )
                for term in file_terms
            )
        ]
        state["candidate_ids"] = tuple(kept)
        state["confidence"] = 0.8 if kept else 0.0
        state["drop_reason"] = "" if kept else "wrong_file_or_workbook"

    def _execute_l3(self, state: dict[str, Any]) -> None:
        parsed = state["parsed_locator"]
        if not parsed["query_user_provided_locator"]:
            selected = tuple(state["candidate_ids"][:3])
            state["selected_source_atom_ids"] = selected
            state["locator_resolution_bucket"] = "NO_USER_LOCATOR"
            state["locator_bounds_answerability"] = "NOT_USER_LOCATOR"
            state["confidence"] = 0.65 if selected else 0.0
            state["drop_reason"] = "" if selected else "no_bounded_candidates"
            return
        if parsed["unsupported_locator_format"]:
            self._block_locator(state, "UNSUPPORTED_LOCATOR_FORMAT")
            return
        selected, bucket = self._resolve_locator(state)
        state["selected_source_atom_ids"] = selected
        state["locator_resolution_bucket"] = bucket
        if bucket == "LOCATION_FOUND":
            state["locator_bounds_answerability"] = "ANSWERABLE_FROM_LOCATOR_BOUNDS"
            state["confidence"] = 0.9
            state["drop_reason"] = ""
        elif bucket == "BOUNDED_BROAD_RANGE":
            state["locator_bounds_answerability"] = "ANSWERABLE_FROM_LOCATOR_BOUNDS"
            state["confidence"] = 0.75
            state["drop_reason"] = ""
        else:
            self._block_locator(state, bucket)

    def _execute_l4(self, state: dict[str, Any]) -> None:
        request: AgentRuntimeRequest = state["request"]
        if self.source_atom_store is not None and state["selected_source_atom_ids"]:
            hydrate_result = self.source_atom_store.hydrate_source_atoms(
                source_atom_ids=tuple(state["selected_source_atom_ids"]),
                diagnostic_tenant_id=self._diagnostic_tenant_id(request),
                namespace=self._adapter_namespace(request),
                timeout_ms=self._adapter_timeout_ms(request),
            )
            state["db_contract_status"] = hydrate_result.status
            self._record_adapter_result(state, hydrate_result)
            if hydrate_result.fail_closed:
                self._block_adapter_fail_closed(state, hydrate_result.fail_closed_reason)
                return
            state["runtime_source_registry"].update(dict(hydrate_result.source_atoms))
        hydrated = tuple(
            source_atom_id
            for source_atom_id in state["selected_source_atom_ids"]
            if source_atom_id in self._source_registry_for_state(state)
        )
        state["selected_source_atom_ids"] = hydrated
        state["confidence"] = 0.85 if hydrated else 0.0
        if not hydrated and not state["blocked_reason"]:
            state["drop_reason"] = "source_atom_missing"

    def _execute_l5(self, state: dict[str, Any]) -> None:
        request: AgentRuntimeRequest = state["request"]
        evidence_texts = []
        bundle_ids = []
        for source_atom_id in state["selected_source_atom_ids"]:
            atom = _as_mapping(self._source_registry_for_state(state).get(source_atom_id))
            bundle_result = assemble_evidence_bundle(
                source_atom_id,
                source_registry={
                    source_atom_id: _evidence_atom_for_runtime(
                        atom,
                        allow_replay=bool(request.internal_replay_adapter),
                    )
                },
                mode="runtime_evidence",
            )
            if not bundle_result.get("valid"):
                self._block_runtime_contract(
                    state,
                    _clean(bundle_result.get("failure_bucket")) or "SOURCE_ATOM_SCHEMA_INCOMPLETE",
                )
                return
            bundle = _as_mapping(bundle_result.get("evidence_bundle"))
            if _low_trust_ocr_evidence(bundle):
                self._block_runtime_contract(state, "LOW_TRUST_OCR_EVIDENCE")
                return
            text = _clean(bundle.get("matched_text_or_value"))
            if text:
                evidence_texts.append(text)
                bundle_ids.append(f"bundle:{source_atom_id}")
        state["evidence_bundle_ids"] = tuple(bundle_ids)
        state["evidence_text"] = "\n".join(evidence_texts)
        state["evidence_truth_source"] = EVIDENCE_TRUTH_SOURCE if bundle_ids else NO_EVIDENCE_TRUTH_SOURCE
        state["confidence"] = 0.85 if bundle_ids else 0.0
        if not bundle_ids and not state["blocked_reason"]:
            state["drop_reason"] = "evidence_text_missing"

    def _execute_l6(self, state: dict[str, Any]) -> None:
        state["confidence"] = 0.8 if state["evidence_bundle_ids"] else 0.0
        if not state["evidence_bundle_ids"] and not state["blocked_reason"]:
            state["drop_reason"] = "no_selected_evidence"

    def _execute_l7(self, state: dict[str, Any]) -> None:
        state["confidence"] = 0.8 if state["evidence_text"] else 0.0
        if not state["evidence_text"] and not state["blocked_reason"]:
            state["drop_reason"] = "locator_bounds_unanswerable"

    def _resolve_locator(self, state: dict[str, Any]) -> tuple[tuple[str, ...], str]:
        request: AgentRuntimeRequest = state["request"]
        terms = state["parsed_locator"]["locator_terms"]
        scored: list[tuple[int, str]] = []
        identity_seen = False
        location_terms_present = bool(terms.get("cell") or terms.get("range") or terms.get("page") or terms.get("section"))
        for source_atom_id in state["candidate_ids"]:
            atom = _as_mapping(self._source_registry_for_state(state).get(source_atom_id))
            score = 0
            location_match = not location_terms_present
            for term in terms.get("file", []):
                if _text_matches(term, _locator_values(atom, "workbook", "file_name", "source_path", "source_identity")):
                    score += 4
            for term in terms.get("sheet", []):
                if _text_matches(term, _locator_values(atom, "sheet", "sheet_name")):
                    score += 3
            if score:
                identity_seen = True
            locator = _locator(atom)
            for term in terms.get("cell", []):
                cell = _clean(locator.get("cell")).upper()
                range_text = _clean(locator.get("range") or locator.get("table_range")).upper()
                if cell and term.upper() == cell:
                    score += 5
                    location_match = True
                elif range_text and _range_contains_cell(range_text, term.upper()):
                    score += 2
                    location_match = True
            for term in terms.get("range", []):
                if _text_matches(term, _locator_values(atom, "range", "table_range")):
                    score += 5
                    location_match = True
            for term in terms.get("page", []):
                if _clean(locator.get("page")) == _clean(term):
                    score += 4
                    location_match = True
            for term in terms.get("section", []):
                if _text_matches(term, _locator_values(atom, "section", "section_title", "row_label")):
                    score += 2
                    location_match = True
            if score > 0 and location_match:
                scored.append((score, source_atom_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        if not scored:
            return (), "OUT_OF_BOUNDS_LOCATOR" if identity_seen and location_terms_present else "LOCATION_NOT_FOUND"
        top = scored[0][0]
        tied = [source_atom_id for score, source_atom_id in scored if score == top]
        if state["page_only_locator"] and not state["active_context_present"]:
            return (), "AMBIGUOUS_PAGE_ONLY_LOCATOR"
        if state["sheet_only_locator"] and not state["active_context_present"]:
            return (), "AMBIGUOUS_SHEET_ONLY_LOCATOR"
        if len(tied) > 1:
            return self._resolve_broad_or_ambiguous_identity(
                request=request,
                source_registry=self._source_registry_for_state(state),
                source_atom_ids=tied,
                broad_bucket="BOUNDED_BROAD_RANGE",
                ambiguous_bucket="AMBIGUOUS_FILE_IDENTITY" if _clean(request.source_family).upper() == "PDF" else "AMBIGUOUS_WORKBOOK_IDENTITY",
            )
        return (tied[0],), "LOCATION_FOUND"

    def _resolve_broad_or_ambiguous_identity(
        self,
        *,
        request: AgentRuntimeRequest,
        source_registry: Mapping[str, Mapping[str, Any]],
        source_atom_ids: Sequence[str],
        broad_bucket: str,
        ambiguous_bucket: str,
    ) -> tuple[tuple[str, ...], str]:
        unique_ids = tuple(_unique(source_atom_ids))
        if not unique_ids:
            return (), ambiguous_bucket
        identities = {
            _source_identity_key(_as_mapping(source_registry.get(source_atom_id)), request.source_family)
            for source_atom_id in unique_ids
        }
        identities.discard("")
        if len(identities) == 1:
            return unique_ids, broad_bucket if len(unique_ids) > 1 else "LOCATION_FOUND"
        return (), ambiguous_bucket

    def _block_locator(self, state: dict[str, Any], bucket: str) -> None:
        state["selected_source_atom_ids"] = ()
        state["evidence_bundle_ids"] = ()
        state["locator_resolution_bucket"] = bucket
        state["locator_bounds_answerability"] = "UNANSWERABLE_FROM_LOCATOR_BOUNDS"
        if bucket == "AMBIGUOUS_PAGE_ONLY_LOCATOR":
            state["blocked_reason"] = "AMBIGUOUS_FILE_IDENTITY"
            state["response_policy_bucket"] = "AMBIGUOUS_FILE_IDENTITY"
            state["active_context_required"] = True
        elif bucket == "AMBIGUOUS_SHEET_ONLY_LOCATOR":
            state["blocked_reason"] = "AMBIGUOUS_WORKBOOK_IDENTITY"
            state["response_policy_bucket"] = "AMBIGUOUS_WORKBOOK_IDENTITY"
            state["active_context_required"] = True
        elif bucket in AMBIGUOUS_LOCATOR_BUCKETS:
            state["blocked_reason"] = bucket
            state["response_policy_bucket"] = bucket
            state["active_context_required"] = True
        else:
            state["blocked_reason"] = bucket
            state["response_policy_bucket"] = bucket
        state["user_clarification_required"] = bucket in AMBIGUOUS_LOCATOR_BUCKETS or bucket in {
            "AMBIGUOUS_PAGE_ONLY_LOCATOR",
            "AMBIGUOUS_SHEET_ONLY_LOCATOR",
            "CONTEXT_REQUIRED",
        }
        state["ambiguity_requires_clarification"] = bucket in AMBIGUOUS_LOCATOR_BUCKETS or bucket in {
            "AMBIGUOUS_PAGE_ONLY_LOCATOR",
            "AMBIGUOUS_SHEET_ONLY_LOCATOR",
        }
        state["drop_reason"] = bucket.casefold()
        state["confidence"] = 0.0

    def _block_response_policy(
        self,
        state: dict[str, Any],
        *,
        locator_bucket: str,
        response_bucket: str,
        blocked_reason: str,
        active_context_required: bool = False,
    ) -> None:
        state["selected_source_atom_ids"] = ()
        state["evidence_bundle_ids"] = ()
        state["evidence_text"] = ""
        state["evidence_truth_source"] = NO_EVIDENCE_TRUTH_SOURCE
        state["locator_resolution_bucket"] = locator_bucket
        state["locator_bounds_answerability"] = "UNANSWERABLE_FROM_LOCATOR_BOUNDS"
        state["response_policy_bucket"] = response_bucket
        state["blocked_reason"] = blocked_reason
        state["drop_reason"] = blocked_reason.casefold()
        state["user_clarification_required"] = True
        state["active_context_required"] = bool(active_context_required)
        state["confidence"] = 0.0

    def _block_runtime_contract(self, state: dict[str, Any], reason: str) -> None:
        state["selected_source_atom_ids"] = ()
        state["evidence_bundle_ids"] = ()
        state["evidence_text"] = ""
        state["evidence_truth_source"] = NO_EVIDENCE_TRUTH_SOURCE
        state["locator_resolution_bucket"] = "CONTRACT_VIOLATION"
        state["locator_bounds_answerability"] = "UNANSWERABLE_FROM_LOCATOR_BOUNDS"
        state["response_policy_bucket"] = "CONTRACT_VIOLATION"
        state["blocked_reason"] = "CONTRACT_VIOLATION"
        state["drop_reason"] = reason.casefold()
        state["fail_closed_reason"] = f"CONTRACT_VIOLATION:{reason}"
        state["runtime_contract_violation"] = True
        state["confidence"] = 0.0

    def _finalize_answer(self, state: dict[str, Any]) -> None:
        if state["runtime_contract_violation"]:
            state["final_answer"] = "런타임 계약 위반으로 비프로덕션 경로가 중단되었습니다."
            state["final_answer_policy"] = "fail_closed_contract"
            state["abstained"] = True
            return
        if state["route_lane"] == ROUTE_UNSUPPORTED:
            state["final_answer"] = "지원되지 않는 요청이라 비프로덕션 경로가 중단되었습니다."
            state["response_policy_bucket"] = "UNSUPPORTED"
            state["final_answer_policy"] = "fail_closed_unsupported"
            state["abstained"] = True
            return
        if state["blocked_reason"]:
            if state["blocked_reason"] in {"CONTEXT_REQUIRED", "AMBIGUOUS_FILE_IDENTITY", "AMBIGUOUS_WORKBOOK_IDENTITY"}:
                state["final_answer"] = "답변하려면 파일/문서, 시트, 범위, 페이지 또는 셀을 더 구체적으로 지정해 주세요."
                state["final_answer_policy"] = "clarification_required"
                state["user_clarification_required"] = True
            else:
                state["final_answer"] = "요청한 위치를 찾지 못했습니다. 제공된 위치 범위 안에서 답변하지 않습니다."
                state["final_answer_policy"] = "locator_fail_closed"
            state["fail_closed_reason"] = _clean(state["adapter_fail_closed_reason"]) or state["blocked_reason"]
            state["abstained"] = True
            return
        if not state["evidence_text"]:
            state["final_answer"] = "제공된 근거만으로는 답변하기 어렵습니다."
            state["response_policy_bucket"] = "INSUFFICIENT_EVIDENCE"
            state["final_answer_policy"] = "abstain_insufficient_evidence"
            state["abstained"] = True
            return
        state["response_policy_bucket"] = "ANSWER_ALLOWED"
        state["answer_allowed_by_policy"] = True
        state["final_answer_policy"] = "answer_allowed"
        state["final_answer"] = state["evidence_text"][:240]
        state["abstained"] = False

    def _trace_row(
        self,
        *,
        request: AgentRuntimeRequest,
        spec: ToolSpec,
        tool_call_id: str,
        parent_tool_call_id: str,
        latency_ms: float,
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "run_id": request.run_id,
            "query_id": request.query_id,
            "diagnostic_case_id": request.diagnostic_case_id,
            "tool_call_id": tool_call_id,
            "parent_tool_call_id": parent_tool_call_id,
            "layer_id": spec.layer_name,
            "tool_name": spec.tool_id,
            "route_lane": state["route_lane"],
            "input_schema_version": INPUT_SCHEMA_VERSION,
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "allowed_input_passed": True,
            "forbidden_input_blocked": True,
            "confidence": round(float(state["confidence"]), 3),
            "drop_reason": _clean(state["drop_reason"]),
            "response_policy_bucket": _clean(state["response_policy_bucket"]),
            "answer_allowed_by_policy": bool(state["answer_allowed_by_policy"]),
            "user_clarification_required": bool(state["user_clarification_required"]),
            "provenance": {
                "tool_registry_version": self.registry.registry_version,
                "tool_spec_version": spec.tool_spec_version,
                "query_text_sha256": _sha256(request.query_text),
                "source_atom_registry_canonical_truth": True,
                "vector_payload_used_as_evidence_truth": False,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
            },
            "source_atom_ids": list(state["selected_source_atom_ids"]),
            "evidence_bundle_ids": list(state["evidence_bundle_ids"]),
            "latency_ms": latency_ms,
            "runtime_contract_violation": bool(state["runtime_contract_violation"]),
            "fail_closed_reason": _clean(state["fail_closed_reason"]),
        }


def _locator_values(atom: Mapping[str, Any], *fields: str) -> list[str]:
    locator = _locator(atom)
    values = [_clean(atom.get("source_identity"))]
    values.extend(_clean(locator.get(field)) for field in fields)
    return [value for value in values if value]


def _text_matches(term: str, values: Sequence[str]) -> bool:
    needle = _norm(term)
    return bool(needle) and any(needle in _norm(value) or _norm(value) in needle for value in values)


def _source_identity_key(atom: Mapping[str, Any], source_family: str) -> str:
    locator = _locator(atom)
    family = _clean(source_family).upper()
    if family == "PDF":
        for key in ("document_id", "file_name", "source_path", "workbook"):
            value = _clean(locator.get(key))
            if value:
                return f"PDF:{value.casefold()}"
        identity = _clean(atom.get("source_identity"))
        return ":".join(identity.split(":")[:2]).casefold() if identity else ""
    if family == "XLSX":
        for key in ("workbook_id", "workbook", "file_name", "source_path"):
            value = _clean(locator.get(key))
            if value:
                return f"XLSX:{value.casefold()}"
        identity = _clean(atom.get("source_identity"))
        return ":".join(identity.split(":")[:2]).casefold() if identity else ""
    return _clean(atom.get("source_identity")).casefold()


def _context_authorizes_atom(
    source_atom_id: str,
    atom: Mapping[str, Any],
    *,
    request_context: Mapping[str, Any],
) -> bool:
    context = _as_mapping(request_context)
    auth_keys_present = any(key in context for key in ("authorized_source_atom_ids", "allowed_source_atom_ids"))
    authorized_ids = _context_id_set(context, "authorized_source_atom_ids", "allowed_source_atom_ids")
    if auth_keys_present and not authorized_ids:
        return False
    if authorized_ids and source_atom_id not in authorized_ids:
        return False
    context_tenant = _clean(context.get("tenant_id"))
    atom_tenant = _clean(atom.get("tenant_id") or _locator(atom).get("tenant_id"))
    if context_tenant and not atom_tenant:
        return False
    if context_tenant and atom_tenant and context_tenant != atom_tenant:
        return False
    return True


def _context_id_set(context: Mapping[str, Any], *keys: str) -> set[str]:
    values: list[str] = []
    for key in keys:
        raw = context.get(key)
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, Sequence):
            values.extend(str(item) for item in raw)
    return set(_unique(values))


def _evidence_atom_for_runtime(atom: Mapping[str, Any], *, allow_replay: bool = False) -> dict[str, Any]:
    if not any(bool(atom.get(flag)) for flag in ("mock_source_atom", "diagnostic_replay_atom", "runtime_replay_atom")):
        return dict(atom)
    if not allow_replay:
        return dict(atom)

    raw = dict(_as_mapping(atom.get("raw_locator")))
    payload = dict(_as_mapping(atom.get("canonical_citation_payload")))
    family = _clean(atom.get("source_family")).upper()
    source_atom_id = _clean(atom.get("source_atom_id")) or "runtime-replay-source-atom"
    text = _clean(atom.get("normalized_text_or_value_snapshot")) or "bounded runtime replay evidence"
    source_identity = _clean(atom.get("source_identity")) or f"{family}:{source_atom_id}"
    if family == "PDF":
        page_value = raw.get("page") if raw.get("page") is not None else payload.get("page")
        page = int(page_value) if str(page_value or "").isdigit() else 1
        raw.setdefault("source_pdf_path", raw.get("file_name") or payload.get("source_pdf_path") or "runtime-replay.pdf")
        raw.setdefault("file_name", PathName(raw["source_pdf_path"]).name)
        raw.setdefault("page", page)
        raw.setdefault("physical_page_index", max(page - 1, 0))
        raw.setdefault("bbox", [0, 0, 1, 1])
        raw.setdefault("region_type", "text")
        document_id = _clean(atom.get("document_id")) or f"doc:{raw['source_pdf_path']}"
        document_version_id = _clean(atom.get("document_version_id")) or f"{document_id}:v1"
        payload.update(
            {
                "source_family": "PDF",
                "source_identity": source_identity,
                "locator_fingerprint": payload.get("locator_fingerprint") or f"fp:{source_atom_id}",
                "search_unit_id": payload.get("search_unit_id") or f"su:{source_atom_id}",
                "source_pdf_path": raw["source_pdf_path"],
                "document_id": document_id,
                "document_version_id": document_version_id,
                "page": raw["page"],
                "physical_page_index": raw["physical_page_index"],
                "bbox": raw["bbox"],
                "region_type": raw["region_type"],
            }
        )
        atom_ids = {"document_id": document_id, "document_version_id": document_version_id}
    else:
        family = "XLSX"
        raw.setdefault("workbook", raw.get("file_name") or payload.get("workbook") or "runtime-replay.xlsx")
        raw.setdefault("sheet", payload.get("sheet") or "Sheet1")
        if not raw.get("range") and not raw.get("cell"):
            raw["cell"] = "A1"
        workbook_id = _clean(atom.get("workbook_id")) or f"wb:{raw['workbook']}"
        workbook_version_id = _clean(atom.get("workbook_version_id")) or f"{workbook_id}:v1"
        payload.update(
            {
                "source_family": "XLSX",
                "source_identity": source_identity,
                "locator_fingerprint": payload.get("locator_fingerprint") or f"fp:{source_atom_id}",
                "search_unit_id": payload.get("search_unit_id") or f"su:{source_atom_id}",
                "workbook": raw["workbook"],
                "sheet": raw["sheet"],
                "range": raw.get("range") or raw.get("cell"),
                "cell": raw.get("cell"),
            }
        )
        atom_ids = {"workbook_id": workbook_id, "workbook_version_id": workbook_version_id}

    enriched = {
        **dict(atom),
        **atom_ids,
        "source_atom_id": source_atom_id,
        "source_family": family,
        "source_identity": source_identity,
        "content_hash": _clean(atom.get("content_hash")) or _sha256(text),
        "extraction_version": _clean(atom.get("extraction_version")) or "runtime-replay-v1",
        "raw_locator": raw,
        "normalized_text_or_value_snapshot": text,
        "parent_pointers": atom.get("parent_pointers") or {"runtime_replay": True},
        "canonical_citation_payload": payload,
        "extraction_snapshot_present": True,
    }
    return enriched


def _low_trust_ocr_evidence(bundle: Mapping[str, Any]) -> bool:
    pdf_evidence = _as_mapping(bundle.get("pdf_evidence"))
    confidence = pdf_evidence.get("ocr_confidence")
    if confidence in (None, ""):
        return False
    try:
        return float(confidence) < 0.5
    except (TypeError, ValueError):
        return True


def PathName(value: Any) -> Path:
    from pathlib import Path

    return Path(_clean(value))
