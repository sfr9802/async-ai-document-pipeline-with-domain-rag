"""Non-production live-runtime-like DB/index/cache adapter contracts."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from app.capabilities.rag.source_registry import validate_search_view

ADAPTER_INPUT_SCHEMA_VERSION = "rag_live_runtime_adapter_input_v1"
ADAPTER_OUTPUT_SCHEMA_VERSION = "rag_live_runtime_adapter_output_v1"
DEFAULT_TIMEOUT_MS = 250
MAX_BOUNDED_SOURCE_ATOM_IDS = 16


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (_clean(value),) if _clean(value) else ()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(_clean(item) for item in value if _clean(item))
    return ()


def _source_atom_ids_from_search_view(search_view: Mapping[str, Any]) -> tuple[str, ...]:
    validation = validate_search_view(search_view)
    return tuple(validation.get("source_atom_ids") or ())


def cache_key_for_query(*, run_id: str, query_id: str, namespace: str) -> str:
    raw = f"{run_id}|{query_id}|{namespace}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RuntimeAdapterAuditContext:
    run_id: str
    query_id: str
    route_lane: str
    diagnostic_tenant_id: str
    namespace: str
    cache_key: str = ""
    timeout_ms: int = DEFAULT_TIMEOUT_MS


@dataclass(frozen=True)
class RuntimeAdapterResult:
    adapter_name: str
    operation: str
    status: str
    allowed_by_contract: bool
    fail_closed: bool = False
    fail_closed_reason: str = ""
    source_atom_ids: tuple[str, ...] = ()
    search_view_ids: tuple[str, ...] = ()
    evidence_bundle_ids: tuple[str, ...] = ()
    source_atoms: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    search_views: tuple[Mapping[str, Any], ...] = ()
    cache_key: str = ""
    cache_hit: bool = False
    latency_ms: float = 0.0
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    production_write_attempted: bool = False
    broad_scan_attempted: bool = False
    vector_payload_used_as_evidence_truth: bool = False
    runtime_contract_violation: bool = False

    def audit_row(self, context: RuntimeAdapterAuditContext) -> dict[str, Any]:
        return {
            "run_id": context.run_id,
            "query_id": context.query_id,
            "route_lane": context.route_lane,
            "adapter_name": self.adapter_name,
            "operation": self.operation,
            "input_schema_version": ADAPTER_INPUT_SCHEMA_VERSION,
            "output_schema_version": ADAPTER_OUTPUT_SCHEMA_VERSION,
            "tenant_id": context.diagnostic_tenant_id,
            "diagnostic_tenant_id": context.diagnostic_tenant_id,
            "namespace": context.namespace,
            "cache_key": self.cache_key or context.cache_key,
            "source_atom_ids": list(self.source_atom_ids),
            "search_view_ids": list(self.search_view_ids),
            "evidence_bundle_ids": list(self.evidence_bundle_ids),
            "allowed_by_contract": self.allowed_by_contract,
            "fail_closed": self.fail_closed,
            "fail_closed_reason": self.fail_closed_reason,
            "latency_ms": self.latency_ms,
            "timeout_ms": self.timeout_ms or context.timeout_ms,
            "production_write_attempted": self.production_write_attempted,
            "broad_scan_attempted": self.broad_scan_attempted,
            "vector_payload_used_as_evidence_truth": self.vector_payload_used_as_evidence_truth,
            "runtime_contract_violation": self.runtime_contract_violation,
            "status": self.status,
            "cache_hit": self.cache_hit,
        }


class SearchIndexContract(Protocol):
    """Candidate-only search index contract."""

    adapter_name: str

    def search_candidates(
        self,
        *,
        query_text: str,
        source_family: str,
        diagnostic_tenant_id: str,
        namespace: str,
        bounded_source_atom_ids: Sequence[str] = (),
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> RuntimeAdapterResult:
        ...


class SourceAtomStoreContract(Protocol):
    """Bounded canonical SourceAtom hydration contract."""

    adapter_name: str

    def hydrate_source_atoms(
        self,
        *,
        source_atom_ids: Sequence[str],
        diagnostic_tenant_id: str,
        namespace: str,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> RuntimeAdapterResult:
        ...


class RuntimeCacheContract(Protocol):
    """Optional runtime cache contract that never owns evidence truth."""

    adapter_name: str

    def get_bundle(
        self,
        *,
        cache_key: str,
        namespace: str,
        expected_namespace: str,
        diagnostic_tenant_id: str,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> RuntimeAdapterResult:
        ...


class InMemorySearchIndexAdapter:
    adapter_name = "InMemorySearchIndexAdapter"

    def __init__(
        self,
        *,
        search_views: Mapping[str, Mapping[str, Any]],
        namespace: str = "rag-data-live-runtime-smoke-nonprod",
        available: bool = True,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        max_candidates: int = 8,
    ) -> None:
        self.search_views = dict(search_views)
        self.namespace = namespace
        self.available = available
        self.timeout_ms = timeout_ms
        self.max_candidates = max_candidates

    def search_candidates(
        self,
        *,
        query_text: str,
        source_family: str,
        diagnostic_tenant_id: str,
        namespace: str,
        bounded_source_atom_ids: Sequence[str] = (),
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> RuntimeAdapterResult:
        started = time.perf_counter()
        resolved_timeout = timeout_ms or self.timeout_ms
        if not self.available:
            return self._result(
                status="unavailable",
                allowed=False,
                fail_closed=True,
                reason="INDEX_UNAVAILABLE",
                started=started,
                timeout_ms=resolved_timeout,
            )
        if namespace != self.namespace:
            return self._result(
                status="namespace_mismatch",
                allowed=False,
                fail_closed=True,
                reason="INDEX_NAMESPACE_MISMATCH",
                started=started,
                timeout_ms=resolved_timeout,
            )
        bounded = set(_as_sequence(bounded_source_atom_ids))
        views: list[Mapping[str, Any]] = []
        source_atom_ids: list[str] = []
        family = _clean(source_family).upper()
        for view_id, view in sorted(self.search_views.items()):
            if family and _clean(view.get("source_family")).upper() not in {"", family}:
                continue
            view_source_atom_ids = _source_atom_ids_from_search_view(view)
            if bounded and not any(source_atom_id in bounded for source_atom_id in view_source_atom_ids):
                continue
            if not view_source_atom_ids:
                continue
            views.append({"search_view_id": _clean(view.get("search_view_id")) or view_id, **dict(view)})
            source_atom_ids.extend(view_source_atom_ids)
            if len(views) >= self.max_candidates:
                break
        unique_atom_ids = tuple(dict.fromkeys(source_atom_ids))
        return self._result(
            status="available",
            allowed=True,
            source_atom_ids=unique_atom_ids,
            search_view_ids=tuple(_clean(view.get("search_view_id")) for view in views),
            search_views=tuple(views),
            started=started,
            timeout_ms=resolved_timeout,
        )

    def _result(
        self,
        *,
        status: str,
        allowed: bool,
        started: float,
        timeout_ms: int,
        fail_closed: bool = False,
        reason: str = "",
        source_atom_ids: Sequence[str] = (),
        search_view_ids: Sequence[str] = (),
        search_views: Sequence[Mapping[str, Any]] = (),
    ) -> RuntimeAdapterResult:
        return RuntimeAdapterResult(
            adapter_name=self.adapter_name,
            operation="search",
            status=status,
            allowed_by_contract=allowed,
            fail_closed=fail_closed,
            fail_closed_reason=reason,
            source_atom_ids=tuple(source_atom_ids),
            search_view_ids=tuple(search_view_ids),
            search_views=tuple(search_views),
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            timeout_ms=timeout_ms,
        )


class InMemorySourceAtomStoreAdapter:
    adapter_name = "InMemorySourceAtomStoreAdapter"

    def __init__(
        self,
        *,
        source_atoms: Mapping[str, Mapping[str, Any]],
        namespace: str = "rag-data-live-runtime-smoke-nonprod",
        available: bool = True,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        max_hydration_ids: int = MAX_BOUNDED_SOURCE_ATOM_IDS,
    ) -> None:
        self.source_atoms = dict(source_atoms)
        self.namespace = namespace
        self.available = available
        self.timeout_ms = timeout_ms
        self.max_hydration_ids = max_hydration_ids

    def hydrate_source_atoms(
        self,
        *,
        source_atom_ids: Sequence[str],
        diagnostic_tenant_id: str,
        namespace: str,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> RuntimeAdapterResult:
        started = time.perf_counter()
        resolved_timeout = timeout_ms or self.timeout_ms
        requested = tuple(dict.fromkeys(_as_sequence(source_atom_ids)))
        if not self.available:
            return self._result(
                status="unavailable",
                allowed=False,
                fail_closed=True,
                reason="SOURCE_ATOM_STORE_UNAVAILABLE",
                requested=requested,
                hydrated={},
                started=started,
                timeout_ms=resolved_timeout,
            )
        if namespace != self.namespace:
            return self._result(
                status="namespace_mismatch",
                allowed=False,
                fail_closed=True,
                reason="SOURCE_ATOM_STORE_NAMESPACE_MISMATCH",
                requested=requested,
                hydrated={},
                started=started,
                timeout_ms=resolved_timeout,
            )
        if len(requested) > self.max_hydration_ids:
            return self._result(
                status="bounded_id_limit_exceeded",
                allowed=False,
                fail_closed=True,
                reason="SOURCE_ATOM_HYDRATION_UNBOUNDED",
                requested=requested,
                hydrated={},
                started=started,
                timeout_ms=resolved_timeout,
                broad_scan_attempted=True,
            )
        hydrated = {
            source_atom_id: dict(atom)
            for source_atom_id in requested
            if (atom := _as_mapping(self.source_atoms.get(source_atom_id)))
            and _clean(atom.get("tenant_id") or diagnostic_tenant_id) == diagnostic_tenant_id
        }
        missing = [source_atom_id for source_atom_id in requested if source_atom_id not in hydrated]
        return self._result(
            status="available" if not missing else "partial",
            allowed=not missing,
            fail_closed=bool(missing),
            reason="SOURCE_ATOM_ID_MISSING_OR_UNAUTHORIZED" if missing else "",
            requested=requested,
            hydrated=hydrated,
            started=started,
            timeout_ms=resolved_timeout,
        )

    def _result(
        self,
        *,
        status: str,
        allowed: bool,
        requested: Sequence[str],
        hydrated: Mapping[str, Mapping[str, Any]],
        started: float,
        timeout_ms: int,
        fail_closed: bool = False,
        reason: str = "",
        broad_scan_attempted: bool = False,
    ) -> RuntimeAdapterResult:
        return RuntimeAdapterResult(
            adapter_name=self.adapter_name,
            operation="hydrate_source_atoms",
            status=status,
            allowed_by_contract=allowed,
            fail_closed=fail_closed,
            fail_closed_reason=reason,
            source_atom_ids=tuple(requested),
            source_atoms=dict(hydrated),
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            timeout_ms=timeout_ms,
            broad_scan_attempted=broad_scan_attempted,
        )


class InMemoryRuntimeCacheAdapter:
    adapter_name = "InMemoryRuntimeCacheAdapter"

    def __init__(
        self,
        *,
        namespace: str,
        cache_items: Mapping[str, Mapping[str, Any]] | None = None,
        available: bool = True,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self.namespace = namespace
        self.cache_items = dict(cache_items or {})
        self.available = available
        self.timeout_ms = timeout_ms

    def get_bundle(
        self,
        *,
        cache_key: str,
        namespace: str,
        expected_namespace: str,
        diagnostic_tenant_id: str,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> RuntimeAdapterResult:
        started = time.perf_counter()
        resolved_timeout = timeout_ms or self.timeout_ms
        if not self.available:
            return self._result(
                status="unavailable",
                allowed=True,
                fail_closed=False,
                reason="",
                cache_key=cache_key,
                started=started,
                timeout_ms=resolved_timeout,
            )
        if namespace != expected_namespace or self.namespace != expected_namespace:
            return self._result(
                status="namespace_mismatch",
                allowed=False,
                fail_closed=True,
                reason="CACHE_NAMESPACE_MISMATCH",
                cache_key=cache_key,
                started=started,
                timeout_ms=resolved_timeout,
            )
        cached = _as_mapping(self.cache_items.get(cache_key))
        if not cached:
            return self._result(
                status="miss",
                allowed=True,
                fail_closed=False,
                reason="",
                cache_key=cache_key,
                started=started,
                timeout_ms=resolved_timeout,
            )
        return self._result(
            status="hit",
            allowed=True,
            fail_closed=False,
            reason="",
            cache_key=cache_key,
            source_atom_ids=_as_sequence(cached.get("source_atom_ids")),
            evidence_bundle_ids=_as_sequence(cached.get("evidence_bundle_ids")),
            started=started,
            timeout_ms=resolved_timeout,
            cache_hit=True,
        )

    def _result(
        self,
        *,
        status: str,
        allowed: bool,
        fail_closed: bool,
        reason: str,
        cache_key: str,
        started: float,
        timeout_ms: int,
        source_atom_ids: Sequence[str] = (),
        evidence_bundle_ids: Sequence[str] = (),
        cache_hit: bool = False,
    ) -> RuntimeAdapterResult:
        return RuntimeAdapterResult(
            adapter_name=self.adapter_name,
            operation="get_bundle",
            status=status,
            allowed_by_contract=allowed,
            fail_closed=fail_closed,
            fail_closed_reason=reason,
            source_atom_ids=tuple(source_atom_ids),
            evidence_bundle_ids=tuple(evidence_bundle_ids),
            cache_key=cache_key,
            cache_hit=cache_hit,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            timeout_ms=timeout_ms,
        )
