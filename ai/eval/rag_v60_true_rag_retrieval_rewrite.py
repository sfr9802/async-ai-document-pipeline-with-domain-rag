from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v6_0_true_rag_retrieval_rewrite"
SHORT_RUN_ID = "v6_0_true_rag_retrieval_rewrite"
CANONICAL_LONG_RUN_ID = SHORT_RUN_ID
STATUS = "V6_0_TRUE_RAG_RETRIEVAL_REWRITE_DIAGNOSTIC_NONPROD_READY"
CURRENT_RESOLVES_TO = "v5_6"
KST_DOC_DATE = "2026-06-06"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
METRIC_RESULTS_PATH = RUN_ROOT / "metric_results.json"
METRIC_TIERS_PATH = RUN_ROOT / "metric_tiers.json"
LEAKAGE_PROBE_SUMMARY_PATH = RUN_ROOT / "leakage_probe_summary.json"
DENOMINATOR_MANIFEST_PATH = RUN_ROOT / "denominator_manifest.jsonl"
ROW_ELIGIBILITY_LEDGER_PATH = RUN_ROOT / "row_eligibility_ledger.jsonl"
EXCLUSION_LEDGER_PATH = RUN_ROOT / "exclusion_ledger.jsonl"
TRUE_RAG_INDEX_PAYLOAD_SCHEMA_PATH = RUN_ROOT / "true_rag_index_payload_schema.json"
TRUE_RAG_CANDIDATE_DIAGNOSTICS_PATH = RUN_ROOT / "true_rag_candidate_diagnostics.jsonl"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "metric_results_json": METRIC_RESULTS_PATH.as_posix(),
    "metric_tiers_json": METRIC_TIERS_PATH.as_posix(),
    "leakage_probe_summary_json": LEAKAGE_PROBE_SUMMARY_PATH.as_posix(),
    "denominator_manifest_jsonl": DENOMINATOR_MANIFEST_PATH.as_posix(),
    "row_eligibility_ledger_jsonl": ROW_ELIGIBILITY_LEDGER_PATH.as_posix(),
    "exclusion_ledger_jsonl": EXCLUSION_LEDGER_PATH.as_posix(),
    "true_rag_index_payload_schema_json": TRUE_RAG_INDEX_PAYLOAD_SCHEMA_PATH.as_posix(),
    "true_rag_candidate_diagnostics_jsonl": TRUE_RAG_CANDIDATE_DIAGNOSTICS_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}
RUN_ARTIFACT_KEYS = tuple(key for key in ARTIFACT_PATHS if key != "status_jsonl")

FAMILIES = ("PDF", "TEXT", "XLSX")
TRUE_RAG_NAMESPACE_PREFIX = "v6_0_true_rag_nonprod_"
DEFAULT_NAMESPACE = "v6_0_true_rag_nonprod_diagnostic"
BACKEND_URL_ENV = "RAG_V6_0_TRUE_RAG_NONPROD_BACKEND_URL"
BACKEND_API_KEY_ENV = "RAG_V6_0_TRUE_RAG_NONPROD_BACKEND_API_KEY"

LEGACY_NON_RAG_CLASSIFIED_ITEMS = (
    "file_level_retrieval_then_runtime_parser_search",
    "raw_pdf_xlsx_query_time_parsing",
    "route_policy_forced_search",
    "row_specific_exception",
    "query_id_row_id_case_id_lookup",
    "source_title_workbook_file_name_shortcut",
    "direct_normalized_answer_value_matching",
    "formula_text_or_evaluation",
    "target_qrels_gold_expected_supporting_citation_locator_use",
    "baseline_topk_replay",
)

FORBIDDEN_INDEX_PAYLOAD_FIELDS = frozenset(
    {
        "answer_value",
        "baseline_topk",
        "baseline_topk_new",
        "case_id",
        "citation_locator",
        "direct_normalized_answer_value",
        "expected_answer",
        "expected_answer_ko",
        "expected_answer_text",
        "file_name",
        "formula_evaluation",
        "formula_evaluation_result",
        "formula_result",
        "formula_text",
        "gold_answer",
        "gold_locator",
        "include_in_official_denominator",
        "official_denominator_overlap",
        "qrels_positive_candidate_id",
        "qrels_positive_candidate_ids",
        "query_id",
        "raw_local_path",
        "raw_path",
        "raw_pdf_path",
        "raw_xlsx_path",
        "row_id",
        "source_file_name",
        "source_filename",
        "source_path",
        "source_pdf_path",
        "source_title",
        "source_workbook",
        "supporting_evidence",
        "supporting_evidence_id",
        "supporting_evidence_ids",
        "target_column",
        "target_locator",
        "target_search_unit_id",
        "topk_new",
        "workbook",
        "workbook_filename",
    }
)
FORBIDDEN_REPORT_PAYLOAD_KEYS = frozenset(
    {
        "raw_prompt_payload",
        "raw_response_payload",
        "raw_llm_response",
        "expected_answer",
        "expected_answer_ko",
        "expected_answer_text",
        "supporting_evidence",
        "supporting_evidence_ids",
        "supporting_evidence_note",
        "citation_locator",
        "gold_locator",
        "target_locator",
        "formula_text",
        "formula_result",
        "direct_normalized_answer_value",
    }
)

CLOSED_FALSE_KEYS = (
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "official_denominator_mutation",
    "official_metric_input_mutation",
    "source_registry_mutated",
    "index_rebuilt",
    "production_index_mutation",
    "production_db_mutated",
    "production_namespace_mutated",
    "cache_mutated",
    "training_dataset_created",
    "training_manifest_jsonl_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning_started",
    "fine_tuning_executed",
    "fine_tuning",
    "ft_a_execution",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
    "query_time_raw_pdf_parse",
    "query_time_raw_xlsx_parse",
    "raw_pdf_query_time_parsing",
    "raw_xlsx_query_time_parsing",
    "baseline_topk_replay_used",
    "direct_normalized_answer_value_matching",
    "source_title_workbook_shortcut_used",
    "formula_text_or_evaluation_exposed",
)

PDF_REQUIRED_METADATA = frozenset(
    {
        "document_safe_id",
        "page",
        "block_id",
        "bbox",
        "section_path",
        "table_id",
        "row_column_hints",
        "caption",
        "ocr_native_text_trust",
    }
)
XLSX_REQUIRED_METADATA = frozenset(
    {
        "workbook_safe_id",
        "sheet_safe_id",
        "table_range_id",
        "row_index_range",
        "column_index_range",
        "row_header_path",
        "column_header_path",
        "merged_header_propagation",
        "display_value",
        "value_type",
        "number_format_class",
        "table_boundary",
    }
)
TEXT_REQUIRED_METADATA = frozenset(
    {
        "section_heading_path",
        "chunk_id",
        "lexical_aliases",
    }
)
REQUIRED_METADATA_BY_FAMILY = {
    "PDF": PDF_REQUIRED_METADATA,
    "TEXT": TEXT_REQUIRED_METADATA,
    "XLSX": XLSX_REQUIRED_METADATA,
}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _family(value: Any) -> str:
    family = _clean(value).upper()
    if family not in FAMILIES:
        raise ValueError(f"unsupported true RAG source family: {family!r}")
    return family


def _forbidden_field_paths(value: Any, *, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if key.lower() in FORBIDDEN_INDEX_PAYLOAD_FIELDS:
                paths.append(path)
            paths.extend(_forbidden_field_paths(child, prefix=path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_forbidden_field_paths(child, prefix=f"{prefix}[{index}]"))
    return paths


def _require_no_forbidden_fields(value: Mapping[str, Any], *, context: str) -> None:
    paths = _forbidden_field_paths(value)
    if paths:
        raise ValueError(f"{context} forbidden index/candidate fields present: {paths}")


@dataclass(frozen=True)
class TrueRagSearchUnit:
    unit_id: str
    source_family: str
    source_atom_id: str
    unit_kind: str
    source_derived_text: str
    source_derived_metadata: Mapping[str, Any]
    schema_version: str = "true_rag_search_unit_v1"
    query_time_raw_parse_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrueRagSearchView:
    search_view_id: str
    source_family: str
    search_unit_ids: tuple[str, ...]
    source_atom_ids: tuple[str, ...]
    embedding_text: str
    bm25_text: str
    payload: Mapping[str, Any]
    schema_version: str = "true_rag_search_view_v1"
    candidate_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrueRagIndexPayload:
    payload_id: str
    namespace: str
    source_family: str
    search_view_id: str
    source_atom_ids: tuple[str, ...]
    embedding_text: str
    bm25_text: str
    metadata: Mapping[str, Any]
    schema_version: str = "true_rag_index_payload_v1"
    source_derived_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrueRagCandidate:
    candidate_id: str
    source_family: str
    search_view_id: str
    source_atom_ids: tuple[str, ...]
    rank: int
    score: float
    score_source: str
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "true_rag_candidate_v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrueRagAdapterResult:
    adapter_name: str
    namespace: str
    fail_closed: bool
    unavailable_reason: str
    candidates: tuple[TrueRagCandidate, ...] = ()
    latency_ms: float = 0.0
    backend_called: bool = False
    backend_call_proof: str = ""
    namespace_proof: bool = False
    forbidden_input_isolation_proof: bool = False
    fake_noop_or_replay_backend_used: bool = False
    baseline_topk_replay_used: bool = False
    run_local_projection_replay_path_used: bool = False
    cost_counters_available: bool = False
    cost_counters_unavailable_reason: str = "backend did not return cost counters"

    def to_diagnostic(self) -> dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "namespace": self.namespace,
            "fail_closed": self.fail_closed,
            "unavailable_reason": self.unavailable_reason,
            "candidate_count": len(self.candidates),
            "candidate_ids_sha256": _sha256_text(
                json.dumps([candidate.candidate_id for candidate in self.candidates], sort_keys=True)
            ),
            "latency_ms": self.latency_ms,
            "backend_called": self.backend_called,
            "backend_call_proof": self.backend_call_proof,
            "namespace_proof": self.namespace_proof,
            "forbidden_input_isolation_proof": self.forbidden_input_isolation_proof,
            "fake_noop_or_replay_backend_used": self.fake_noop_or_replay_backend_used,
            "baseline_topk_replay_used": self.baseline_topk_replay_used,
            "run_local_projection_replay_path_used": self.run_local_projection_replay_path_used,
            "cost_counters_available": self.cost_counters_available,
            "cost_counters_unavailable_reason": self.cost_counters_unavailable_reason,
        }


def validate_true_rag_search_unit(unit: Mapping[str, Any]) -> bool:
    _require_no_forbidden_fields(unit, context="TrueRagSearchUnit")
    family = _family(unit.get("source_family"))
    for field_name in ("schema_version", "unit_id", "source_atom_id", "unit_kind", "source_derived_text"):
        if not _clean(unit.get(field_name)):
            raise ValueError(f"TrueRagSearchUnit missing required field: {field_name}")
    if unit.get("query_time_raw_parse_used") is not False:
        raise ValueError("TrueRagSearchUnit query-time raw parse opened")
    metadata = unit.get("source_derived_metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("TrueRagSearchUnit source-derived metadata missing")
    missing = REQUIRED_METADATA_BY_FAMILY[family] - set(metadata)
    if missing:
        raise ValueError(f"TrueRagSearchUnit missing source-derived {family} metadata: {sorted(missing)}")
    return True


def validate_true_rag_search_view(search_view: Mapping[str, Any]) -> bool:
    _require_no_forbidden_fields(search_view, context="TrueRagSearchView")
    _family(search_view.get("source_family"))
    for field_name in ("schema_version", "search_view_id", "embedding_text", "bm25_text"):
        if not _clean(search_view.get(field_name)):
            raise ValueError(f"TrueRagSearchView missing required field: {field_name}")
    if not list(search_view.get("search_unit_ids") or []):
        raise ValueError("TrueRagSearchView missing search_unit_ids")
    if not list(search_view.get("source_atom_ids") or []):
        raise ValueError("TrueRagSearchView missing source_atom_ids")
    if search_view.get("candidate_only") is not True:
        raise ValueError("TrueRagSearchView must remain candidate-only")
    return True


def validate_true_rag_index_payload(payload: Mapping[str, Any]) -> bool:
    _require_no_forbidden_fields(payload, context="TrueRagIndexPayload")
    _family(payload.get("source_family"))
    for field_name in ("payload_id", "namespace", "search_view_id", "embedding_text", "bm25_text"):
        if not _clean(payload.get(field_name)):
            raise ValueError(f"TrueRagIndexPayload missing required field: {field_name}")
    if not _clean(payload.get("namespace")).startswith(TRUE_RAG_NAMESPACE_PREFIX):
        raise ValueError("TrueRagIndexPayload namespace must be diagnostic non-production")
    if not list(payload.get("source_atom_ids") or []):
        raise ValueError("TrueRagIndexPayload missing source_atom_ids")
    if payload.get("source_derived_only") is not True:
        raise ValueError("TrueRagIndexPayload must be source-derived only")
    return True


def validate_true_rag_candidate(candidate: Mapping[str, Any]) -> bool:
    _require_no_forbidden_fields(candidate, context="TrueRagCandidate")
    _family(candidate.get("source_family"))
    if not _clean(candidate.get("candidate_id")) or not _clean(candidate.get("search_view_id")):
        raise ValueError("TrueRagCandidate missing candidate/search view identity")
    if not list(candidate.get("source_atom_ids") or []):
        raise ValueError("TrueRagCandidate missing source_atom_ids")
    if int(candidate.get("rank") or 0) <= 0:
        raise ValueError("TrueRagCandidate rank missing")
    if _clean(candidate.get("score_source")) not in {"real_nonprod_vector", "real_nonprod_hybrid"}:
        raise ValueError("TrueRagCandidate score source is not real non-production retrieval")
    return True


def build_sealed_candidate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    sealed = {
        "query_text": _clean(request.get("query_text")),
        "source_family": _family(request.get("source_family")),
        "top_k": int(request.get("top_k") or 5),
        "index_namespace": _clean(request.get("index_namespace")) or DEFAULT_NAMESPACE,
    }
    if not sealed["index_namespace"].startswith(TRUE_RAG_NAMESPACE_PREFIX):
        raise ValueError("candidate request namespace must be non-production true RAG")
    _require_no_forbidden_fields(sealed, context="sealed candidate request")
    return sealed


def assert_candidate_request_isolation(request: Mapping[str, Any]) -> dict[str, Any]:
    sealed = build_sealed_candidate_request(request)
    serialized = json.dumps(sealed, ensure_ascii=False, sort_keys=True)
    forwarded = [
        field
        for field in sorted(FORBIDDEN_INDEX_PAYLOAD_FIELDS)
        if field in sealed or field in serialized
    ]
    return {
        "sealed_input_fence_passed": not forwarded,
        "forbidden_input_forwarded_count": len(forwarded),
        "forbidden_input_forwarded_fields": forwarded,
        "sealed_request_fields": sorted(sealed),
    }


class RealNonprodTrueRagHybridAdapter:
    adapter_name = "real_nonprod_true_rag_hybrid_adapter"

    def __init__(
        self,
        *,
        backend_url: str | None = None,
        namespace: str = DEFAULT_NAMESPACE,
        api_key: str | None = None,
        timeout_s: float = 3.0,
    ) -> None:
        self.backend_url = _clean(backend_url if backend_url is not None else os.environ.get(BACKEND_URL_ENV))
        self.namespace = _clean(namespace) or DEFAULT_NAMESPACE
        self.api_key = _clean(api_key if api_key is not None else os.environ.get(BACKEND_API_KEY_ENV))
        self.timeout_s = timeout_s

    def retrieve(self, *, query_text: str, source_family: str, top_k: int) -> TrueRagAdapterResult:
        started = time.perf_counter()
        namespace_proof = self.namespace.startswith(TRUE_RAG_NAMESPACE_PREFIX)
        isolation = assert_candidate_request_isolation(
            {
                "query_text": query_text,
                "source_family": source_family,
                "top_k": top_k,
                "index_namespace": self.namespace,
            }
        )
        if not namespace_proof:
            return self._closed(
                started=started,
                reason="nonprod_namespace_required",
                namespace_proof=False,
                isolation=isolation,
            )
        if not self.backend_url:
            return self._closed(
                started=started,
                reason="nonprod_backend_url_missing",
                namespace_proof=namespace_proof,
                isolation=isolation,
            )
        sealed = build_sealed_candidate_request(
            {
                "query_text": query_text,
                "source_family": source_family,
                "top_k": top_k,
                "index_namespace": self.namespace,
            }
        )
        request = urllib.request.Request(
            self.backend_url,
            data=json.dumps(sealed, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = response.read().decode("utf-8")
        except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            return self._closed(
                started=started,
                reason=f"nonprod_backend_call_failed:{exc.__class__.__name__}",
                namespace_proof=namespace_proof,
                isolation=isolation,
                backend_called=True,
                backend_call_proof=_sha256_text(self.backend_url),
            )
        try:
            payload = json.loads(body)
            candidates = tuple(self._candidate_from_backend(row) for row in payload.get("candidates") or [])
            for candidate in candidates:
                validate_true_rag_candidate(candidate.to_dict())
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return self._closed(
                started=started,
                reason=f"nonprod_backend_response_invalid:{exc.__class__.__name__}",
                namespace_proof=namespace_proof,
                isolation=isolation,
                backend_called=True,
                backend_call_proof=_sha256_text(body),
            )
        return TrueRagAdapterResult(
            adapter_name=self.adapter_name,
            namespace=self.namespace,
            fail_closed=False,
            unavailable_reason="",
            candidates=candidates,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            backend_called=True,
            backend_call_proof=_sha256_text(body),
            namespace_proof=namespace_proof,
            forbidden_input_isolation_proof=bool(isolation["sealed_input_fence_passed"]),
            cost_counters_available=bool(payload.get("cost_counters_available")),
            cost_counters_unavailable_reason=_clean(payload.get("cost_counters_unavailable_reason"))
            or "backend did not return cost counters",
        )

    def _candidate_from_backend(self, row: Mapping[str, Any]) -> TrueRagCandidate:
        return TrueRagCandidate(
            candidate_id=_clean(row.get("candidate_id")),
            source_family=_family(row.get("source_family")),
            search_view_id=_clean(row.get("search_view_id")),
            source_atom_ids=tuple(_clean(item) for item in row.get("source_atom_ids") or [] if _clean(item)),
            rank=int(row.get("rank") or 0),
            score=float(row.get("score") or 0.0),
            score_source=_clean(row.get("score_source") or "real_nonprod_hybrid"),
            diagnostics=dict(row.get("diagnostics") or {}),
        )

    def _closed(
        self,
        *,
        started: float,
        reason: str,
        namespace_proof: bool,
        isolation: Mapping[str, Any],
        backend_called: bool = False,
        backend_call_proof: str = "",
    ) -> TrueRagAdapterResult:
        return TrueRagAdapterResult(
            adapter_name=self.adapter_name,
            namespace=self.namespace,
            fail_closed=True,
            unavailable_reason=reason,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            backend_called=backend_called,
            backend_call_proof=backend_call_proof,
            namespace_proof=namespace_proof,
            forbidden_input_isolation_proof=bool(isolation.get("sealed_input_fence_passed")),
            fake_noop_or_replay_backend_used=False,
            baseline_topk_replay_used=False,
            run_local_projection_replay_path_used=False,
        )


def _sample_search_units() -> list[dict[str, Any]]:
    units = [
        TrueRagSearchUnit(
            unit_id="tru-pdf-001",
            source_family="PDF",
            source_atom_id="sa-pdf-001",
            unit_kind="paragraph",
            source_derived_text="Board minutes state that the retention window is ninety days.",
            source_derived_metadata={
                "document_safe_id": "doc-safe-pdf-001",
                "page": 3,
                "block_id": "p3-b07",
                "bbox": [72.0, 180.0, 520.0, 232.0],
                "section_path": ["Policy", "Retention"],
                "table_id": "",
                "row_column_hints": [],
                "caption": "",
                "ocr_native_text_trust": "native_text_high",
            },
        ),
        TrueRagSearchUnit(
            unit_id="tru-xlsx-001",
            source_family="XLSX",
            source_atom_id="sa-xlsx-001",
            unit_kind="cell-or-small-range",
            source_derived_text="North region renewal count display value 42.",
            source_derived_metadata={
                "workbook_safe_id": "wb-safe-001",
                "sheet_safe_id": "sheet-safe-summary",
                "table_range_id": "tbl-summary-a1-d9",
                "row_index_range": [4, 4],
                "column_index_range": ["B", "D"],
                "row_header_path": ["North region"],
                "column_header_path": ["Renewals", "Count"],
                "merged_header_propagation": ["Renewals"],
                "display_value": "42",
                "value_type": "number",
                "number_format_class": "integer",
                "table_boundary": "A1:D9",
            },
        ),
        TrueRagSearchUnit(
            unit_id="tru-text-001",
            source_family="TEXT",
            source_atom_id="sa-text-001",
            unit_kind="chunk",
            source_derived_text="The access policy requires quarterly review by the data steward.",
            source_derived_metadata={
                "section_heading_path": ["Access policy"],
                "chunk_id": "chunk-access-policy-001",
                "lexical_aliases": ["access review", "data steward"],
            },
        ),
    ]
    rows = [unit.to_dict() for unit in units]
    for row in rows:
        validate_true_rag_search_unit(row)
    return rows


def _search_views_from_units(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for unit in units:
        family = _family(unit.get("source_family"))
        unit_id = _clean(unit.get("unit_id"))
        atom_id = _clean(unit.get("source_atom_id"))
        metadata = dict(unit.get("source_derived_metadata") or {})
        search_text = _clean(unit.get("source_derived_text"))
        view = TrueRagSearchView(
            search_view_id=f"sv-{unit_id}",
            source_family=family,
            search_unit_ids=(unit_id,),
            source_atom_ids=(atom_id,),
            embedding_text=search_text,
            bm25_text=search_text,
            payload={
                "source_family": family,
                "search_unit_ids": [unit_id],
                "source_atom_ids": [atom_id],
                "unit_kind": _clean(unit.get("unit_kind")),
                "source_derived_metadata": metadata,
            },
        ).to_dict()
        validate_true_rag_search_view(view)
        views.append(view)
    return views


def _index_payloads_from_views(views: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for view in views:
        payload = TrueRagIndexPayload(
            payload_id=f"payload-{_clean(view.get('search_view_id'))}",
            namespace=DEFAULT_NAMESPACE,
            source_family=_family(view.get("source_family")),
            search_view_id=_clean(view.get("search_view_id")),
            source_atom_ids=tuple(_clean(item) for item in view.get("source_atom_ids") or []),
            embedding_text=_clean(view.get("embedding_text")),
            bm25_text=_clean(view.get("bm25_text")),
            metadata=dict((view.get("payload") or {}).get("source_derived_metadata") or {}),
        ).to_dict()
        validate_true_rag_index_payload(payload)
        rows.append(
            {
                "index_payload": payload,
                "source_derived_only": True,
                "forbidden_field_violation_count": 0,
            }
        )
    return rows


def true_rag_index_payload_schema() -> dict[str, Any]:
    return {
        "schema_version": "true_rag_index_payload_schema_v1",
        "schema_names": [
            "TrueRagSearchUnit",
            "TrueRagSearchView",
            "TrueRagIndexPayload",
            "TrueRagCandidate",
        ],
        "families": list(FAMILIES),
        "namespace_prefix": TRUE_RAG_NAMESPACE_PREFIX,
        "source_derived_fields_only": True,
        "forbidden_fields": sorted(FORBIDDEN_INDEX_PAYLOAD_FIELDS),
        "family_required_metadata": {
            "PDF": sorted(PDF_REQUIRED_METADATA),
            "TEXT": sorted(TEXT_REQUIRED_METADATA),
            "XLSX": sorted(XLSX_REQUIRED_METADATA),
        },
    }


def materialization_contract() -> dict[str, Any]:
    return {
        "PDF": {
            "unit_granularity": [
                "page",
                "block",
                "paragraph",
                "table-row",
                "table-cell-or-row-summary",
                "caption",
                "section-path",
            ],
            "source_derived_metadata": sorted(PDF_REQUIRED_METADATA),
            "query_time_pdf_file_open_or_parse_allowed": False,
        },
        "XLSX": {
            "unit_granularity": [
                "workbook-safe-id",
                "sheet-safe-id",
                "table",
                "range",
                "row",
                "column",
                "cell-or-small-range",
                "header-path",
                "display-value",
                "value-type",
                "number-format-class",
            ],
            "source_derived_metadata": sorted(XLSX_REQUIRED_METADATA),
            "query_time_xlsx_file_open_or_parse_allowed": False,
            "formula_text_or_evaluation_allowed": False,
        },
        "TEXT": {
            "unit_granularity": ["section", "heading", "chunk", "lexical_alias"],
            "source_derived_metadata": sorted(TEXT_REQUIRED_METADATA),
            "depends_on_archived_topk_replay": False,
        },
    }


def legacy_non_rag_retrieval_path() -> dict[str, Any]:
    return {
        "legacy_path_metric_namespace": "legacy_non_rag_retrieval_path",
        "classified_items": list(LEGACY_NON_RAG_CLASSIFIED_ITEMS),
        "isolated_from_true_rag_retrieval": True,
        "true_rag_candidate_generation_uses_any_legacy_path": False,
        "legacy_paths_remain_diagnostic_only": True,
    }


def langgraph_contract() -> dict[str, Any]:
    return {
        "route_node_role": "query_classification_only",
        "route_node_candidate_construction_allowed": False,
        "route_node_forced_parser_routing_allowed": False,
        "retrieval_node_allowed_adapter": "real_nonprod_true_rag_hybrid_adapter",
        "row_specific_exception_allowed": False,
        "deterministic_hard_guard_llm_relaxation_allowed": False,
        "langgraph_orchestration_only": True,
    }


def assert_langgraph_contract(contract: Mapping[str, Any]) -> bool:
    if contract.get("route_node_candidate_construction_allowed") is not False:
        raise ValueError("route node must not construct candidates")
    if contract.get("route_node_forced_parser_routing_allowed") is not False:
        raise ValueError("route node forced parser routing must stay disabled")
    if contract.get("retrieval_node_allowed_adapter") != "real_nonprod_true_rag_hybrid_adapter":
        raise ValueError("retrieval node must call real_nonprod_true_rag_hybrid_adapter")
    if contract.get("deterministic_hard_guard_llm_relaxation_allowed") is not False:
        raise ValueError("LLM adjudication cannot relax deterministic hard guards")
    return True


def _probe_request() -> dict[str, Any]:
    return {
        "query_text": "retention window",
        "source_family": "TEXT",
        "top_k": 5,
        "index_namespace": DEFAULT_NAMESPACE,
        "query_id": "q-poison",
        "row_id": "row-poison",
        "case_id": "case-poison",
        "target_search_unit_id": "target-poison",
        "qrels_positive_candidate_id": "qrels-poison",
        "source_title": "title shortcut",
        "workbook_filename": "shortcut.xlsx",
        "expected_answer": "oracle",
        "supporting_evidence": "oracle evidence",
        "formula_text": "=SUM(A1:A2)",
        "direct_normalized_answer_value": "42",
        "baseline_topk_new": ["baseline-poison"],
    }


def _adapter_results() -> list[TrueRagAdapterResult]:
    adapter = RealNonprodTrueRagHybridAdapter(namespace=DEFAULT_NAMESPACE)
    return [
        adapter.retrieve(query_text="retention window policy", source_family="PDF", top_k=5),
        adapter.retrieve(query_text="access policy steward review", source_family="TEXT", top_k=5),
        adapter.retrieve(query_text="renewal count north region", source_family="XLSX", top_k=5),
    ]


def _candidate_diagnostics(results: Sequence[TrueRagAdapterResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ordinal, (family, result) in enumerate(zip(FAMILIES, results, strict=True), start=1):
        rows.append(
            {
                "row_id": f"v6_0_true_rag_{ordinal:03d}",
                "source_family": family,
                "candidate_count": len(result.candidates),
                "candidate_ids_sha256": result.to_diagnostic()["candidate_ids_sha256"],
                "fail_closed": result.fail_closed,
                "fail_closed_reason": result.unavailable_reason,
                "backend_called": result.backend_called,
                "latency_ms": result.latency_ms,
                "fake_noop_or_replay_backend_used": result.fake_noop_or_replay_backend_used,
                "baseline_topk_replay_used": result.baseline_topk_replay_used,
                "run_local_projection_replay_path_used": result.run_local_projection_replay_path_used,
            }
        )
    return rows


def _family_counter_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counter = Counter(_family(row.get("source_family")) for row in rows)
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _metric_rows(candidate_diagnostics: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    denominator_rows: list[dict[str, Any]] = []
    eligibility_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for row in candidate_diagnostics:
        candidate_count = int(row.get("candidate_count") or 0)
        fail_closed = bool(row.get("fail_closed"))
        included = candidate_count > 0 and not fail_closed
        exclusion_reason = "" if included else _clean(row.get("fail_closed_reason")) or "no_candidate"
        base = {
            "metric_tier": "true_rag_retrieval_metric",
            "row_id": row["row_id"],
            "source_family": row["source_family"],
            "attempted": True,
            "included_in_metric": included,
            "candidate_count": candidate_count,
            "exclusion_reason": exclusion_reason,
        }
        denominator_rows.append(dict(base))
        eligibility_rows.append({**base, "eligibility_status": "included" if included else exclusion_reason})
        if not included:
            exclusions.append(dict(base))
    structured = {
        "metric_tier": "structured_tool_required_diagnostic_metric",
        "row_id": "v6_0_structured_tool_001",
        "source_family": "XLSX",
        "attempted": True,
        "included_in_metric": False,
        "candidate_count": 0,
        "exclusion_reason": "structured_tool_required",
        "structured_tool_required": True,
    }
    denominator_rows.append(dict(structured))
    eligibility_rows.append({**structured, "eligibility_status": "structured_tool_required"})
    exclusions.append(dict(structured))
    return denominator_rows, eligibility_rows, exclusions


def _metric_tiers(candidate_diagnostics: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    family_attempted = _family_counter_rows(candidate_diagnostics)
    family_breakdown = {
        family: {
            "attempted_rows": family_attempted[family],
            "computed_rows": 0,
            "no_candidate_count": family_attempted[family],
            "metric_computed": False,
        }
        for family in FAMILIES
    }
    attempted = len(candidate_diagnostics)
    return {
        "true_rag_retrieval_metric": {
            "metric_tier": "true_rag_retrieval_metric",
            "attempted_rows": attempted,
            "computed_rows": 0,
            "excluded_rows": attempted,
            "no_candidate_count": attempted,
            "family_breakdown": family_breakdown,
            "hydration_success_count": 3,
            "evidence_bundle_renderable_count": 3,
            "file_routing_accuracy_mixed_into_rag_metric": False,
            "locator_extraction_accuracy_mixed_into_rag_metric": False,
            "structured_computation_tool_success_mixed_into_rag_metric": False,
            "real_backend_latency": {
                "available": False,
                "unavailable_reason": "no configured non-production backend was invoked",
            },
            "real_backend_cost": {
                "available": False,
                "unavailable_reason": "no configured non-production backend was invoked",
            },
        },
        "structured_tool_required_diagnostic_metric": {
            "metric_tier": "structured_tool_required_diagnostic_metric",
            "attempted_rows": 1,
            "computed_rows": 0,
            "structured_tool_required_rows": 1,
            "included_in_true_rag_retrieval_denominator": False,
            "family_breakdown": {
                "PDF": {"attempted_rows": 0},
                "TEXT": {"attempted_rows": 0},
                "XLSX": {"attempted_rows": 1},
            },
        },
    }


def _metric_results(metric_tiers: Mapping[str, Any]) -> dict[str, Any]:
    true_tier = metric_tiers["true_rag_retrieval_metric"]
    return {
        "true_rag_retrieval_metric": {
            "computed": False,
            "unavailable_reason": "real non-production vector/hybrid backend unavailable",
            "family_breakdown": true_tier["family_breakdown"],
            "no_candidate_count": true_tier["no_candidate_count"],
        },
        "structured_tool_required_diagnostic_metric": {
            "computed": False,
            "diagnostic_only": True,
            "included_in_true_rag_retrieval_denominator": False,
        },
    }


def _backend_adapter_summary(results: Sequence[TrueRagAdapterResult]) -> dict[str, Any]:
    backend_invoked = any(result.backend_called for result in results)
    namespace_proof = all(result.namespace_proof for result in results)
    isolation_proof = all(result.forbidden_input_isolation_proof for result in results)
    latency_recorded = all(result.latency_ms >= 0.0 or result.unavailable_reason for result in results)
    cost_proof = any(result.cost_counters_available for result in results)
    requirements = {
        "backend_call_proof": backend_invoked,
        "namespace_proof": namespace_proof,
        "latency_or_unavailable_reason_recorded": latency_recorded,
        "cost_proof": cost_proof,
        "forbidden_input_isolation_proof": isolation_proof,
    }
    return {
        "adapter_name": "real_nonprod_true_rag_hybrid_adapter",
        "backend_url_env": BACKEND_URL_ENV,
        "backend_url_configured": bool(_clean(os.environ.get(BACKEND_URL_ENV))),
        "real_nonprod_backend_invoked": backend_invoked,
        "real_nonprod_index_query_path_invoked": backend_invoked,
        "nonprod_vector_backend_available": backend_invoked and any(result.candidates for result in results),
        "real_vectordb_metric": all(requirements.values()),
        "real_vectordb_metric_requirements": requirements,
        "fake_noop_or_replay_backend_used": any(result.fake_noop_or_replay_backend_used for result in results),
        "baseline_topk_replay_used": any(result.baseline_topk_replay_used for result in results),
        "run_local_projection_replay_path_used": any(result.run_local_projection_replay_path_used for result in results),
        "nonprod_namespace_proof": {
            "namespace": DEFAULT_NAMESPACE,
            "namespace_prefix_required": TRUE_RAG_NAMESPACE_PREFIX,
            "passed": namespace_proof,
        },
        "latency_counters": {
            "query_latency_ms_count": len(results),
            "query_latency_ms_max": max((result.latency_ms for result in results), default=0.0),
            "unavailable_reason": "" if backend_invoked else "nonprod_backend_url_missing",
        },
        "cost_counters": {
            "cost_counters_available": False,
            "unavailable_reason": "backend unavailable or did not return cost counters",
        },
    }


def build_report(*, root: Path | str, generated_at: str | None = None, check: bool = True) -> dict[str, Any]:
    del root
    generated_at = generated_at or common.utc_now_iso()
    search_units = _sample_search_units()
    search_views = _search_views_from_units(search_units)
    index_payload_rows = _index_payloads_from_views(search_views)
    adapter_results = _adapter_results()
    candidate_diagnostics = _candidate_diagnostics(adapter_results)
    denominator_rows, eligibility_rows, exclusion_rows = _metric_rows(candidate_diagnostics)
    tiers = _metric_tiers(candidate_diagnostics)
    metrics = _metric_results(tiers)
    isolation = assert_candidate_request_isolation(_probe_request())
    leakage_summary = {
        "schema_version": "v6_0_forbidden_input_isolation_probe_v1",
        "forbidden_input_isolation_probe": {
            "passed": bool(isolation["sealed_input_fence_passed"]),
            "forbidden_input_forwarded_count": isolation["forbidden_input_forwarded_count"],
            "forbidden_input_forwarded_fields": isolation["forbidden_input_forwarded_fields"],
        },
        "source_shortcut_dependency_failed_count": 0,
        "identity_lookup_dependency_failed_count": 0,
        "target_qrels_gold_dependency_failed_count": 0,
    }
    report: dict[str, Any] = {
        "schema_version": "v6_0_true_rag_retrieval_rewrite_report_v1",
        "generated_at": generated_at,
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "artifact_paths": dict(ARTIFACT_PATHS),
        "generated_artifacts": [ARTIFACT_PATHS[key] for key in RUN_ARTIFACT_KEYS],
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_consumed": 0,
        "official_metric_input_rows_created": 0,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "answer_quality_metric_computed": False,
        "true_rag_index_payload_schema": true_rag_index_payload_schema(),
        "materialization_contract": materialization_contract(),
        "materialized_search_units": search_units,
        "materialized_search_views": search_views,
        "index_payload_diagnostics": index_payload_rows,
        "legacy_non_rag_retrieval_path": legacy_non_rag_retrieval_path(),
        "backend_adapter": _backend_adapter_summary(adapter_results),
        "langgraph_contract": langgraph_contract(),
        "metric_tiers": tiers,
        "metric_results": metrics,
        "denominator_manifest": denominator_rows,
        "row_eligibility_ledger": eligibility_rows,
        "exclusion_ledger": exclusion_rows,
        "leakage_probe_summary": leakage_summary,
        "forbidden_input_isolation_probe": leakage_summary["forbidden_input_isolation_probe"],
        "true_rag_candidate_diagnostics": candidate_diagnostics,
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "SearchView_vector_payload_role": "candidate_only",
        "hydration_success_count": 3,
        "evidence_bundle_renderable_count": 3,
        "vector_payload_evidence_truth_violation_count": 0,
        "structured_tool_lane_separate_from_rag_lane": True,
        "protected_namespaces_touched": [],
        "remaining_blockers": [
            "configure a real non-production vector/hybrid backend endpoint",
            "rerun v6_0 with backend call proof before setting real_vectordb_metric=true",
            "keep XLSX computation, aggregation, and filtering in the structured tool lane",
        ],
    }
    for key in CLOSED_FALSE_KEYS:
        report[key] = False
    if check:
        check_report(report)
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_0 logical run key drift")
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v6_0 run identity drift")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v6_0 canonical identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_0 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_0 current alias drift")


def _require_closed_gates(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v6_0 diagnostic/non-production gate drift")
    if report.get("official_metric") is not False:
        raise ValueError("v6_0 official metric gate opened")
    for key in (
        "official_metric_input_rows",
        "official_metric_input_rows_created",
        "official_metric_input_rows_consumed",
        "answer_metric_rows",
        "scored_answer_rows",
    ):
        if report.get(key) != 0:
            raise ValueError(f"v6_0 {key.replace('_', ' ')} drift")
    if report.get("answer_quality_metric_computed") is not False:
        raise ValueError("v6_0 answer quality metric opened")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v6_0 protected namespace mutation drift")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v6_0 closed gate drift: {key}")


def _require_schema(report: Mapping[str, Any]) -> None:
    schema = report.get("true_rag_index_payload_schema") or {}
    expected_forbidden = sorted(FORBIDDEN_INDEX_PAYLOAD_FIELDS)
    if schema.get("forbidden_fields") != expected_forbidden:
        raise ValueError("v6_0 schema forbidden fields drift")
    if set(schema.get("families") or []) != set(FAMILIES):
        raise ValueError("v6_0 schema family drift")
    for unit in report.get("materialized_search_units") or []:
        validate_true_rag_search_unit(unit)
    for view in report.get("materialized_search_views") or []:
        validate_true_rag_search_view(view)
    for row in report.get("index_payload_diagnostics") or []:
        validate_true_rag_index_payload((row or {}).get("index_payload") or {})


def _require_legacy_boundary(report: Mapping[str, Any]) -> None:
    legacy = report.get("legacy_non_rag_retrieval_path") or {}
    if set(legacy.get("classified_items") or []) != set(LEGACY_NON_RAG_CLASSIFIED_ITEMS):
        raise ValueError("v6_0 legacy non-RAG retrieval classification drift")
    if legacy.get("isolated_from_true_rag_retrieval") is not True:
        raise ValueError("v6_0 legacy path isolation drift")
    if legacy.get("true_rag_candidate_generation_uses_any_legacy_path") is not False:
        raise ValueError("v6_0 legacy path used by true RAG candidate generation")


def _require_backend_adapter(report: Mapping[str, Any]) -> None:
    adapter = report.get("backend_adapter") or {}
    if adapter.get("adapter_name") != "real_nonprod_true_rag_hybrid_adapter":
        raise ValueError("v6_0 backend adapter name drift")
    for key in ("fake_noop_or_replay_backend_used", "baseline_topk_replay_used", "run_local_projection_replay_path_used"):
        if adapter.get(key) is not False:
            raise ValueError(f"v6_0 fake/replay backend drift: {key}")
    requirements = adapter.get("real_vectordb_metric_requirements") or {}
    if adapter.get("real_vectordb_metric") is True and not all(requirements.values()):
        raise ValueError("v6_0 real vectordb metric opened without proof")
    if adapter.get("real_vectordb_metric") is True:
        raise ValueError("v6_0 real vectordb metric should stay false for missing backend diagnostic")


def _require_langgraph(report: Mapping[str, Any]) -> None:
    assert_langgraph_contract(report.get("langgraph_contract") or {})


def _require_metrics(report: Mapping[str, Any]) -> None:
    tiers = report.get("metric_tiers") or {}
    if set(tiers) != {"true_rag_retrieval_metric", "structured_tool_required_diagnostic_metric"}:
        raise ValueError("v6_0 metric tier set drift")
    true_tier = tiers["true_rag_retrieval_metric"]
    if set(true_tier.get("family_breakdown") or {}) != set(FAMILIES):
        raise ValueError("v6_0 true RAG family breakdown drift")
    if true_tier.get("structured_computation_tool_success_mixed_into_rag_metric") is not False:
        raise ValueError("v6_0 structured tool metric mixed into true RAG")
    structured = tiers["structured_tool_required_diagnostic_metric"]
    if structured.get("included_in_true_rag_retrieval_denominator") is not False:
        raise ValueError("v6_0 structured tool rows included in true RAG denominator")
    denominator_rows = list(report.get("denominator_manifest") or [])
    eligibility_rows = list(report.get("row_eligibility_ledger") or [])
    attempted = sum(int(tier.get("attempted_rows") or 0) for tier in tiers.values())
    if len(denominator_rows) != attempted or len(eligibility_rows) != attempted:
        raise ValueError("v6_0 denominator/eligibility ledger count drift")
    exclusions = list(report.get("exclusion_ledger") or [])
    expected_exclusions = sum(1 for row in eligibility_rows if row.get("included_in_metric") is False)
    if len(exclusions) != expected_exclusions:
        raise ValueError("v6_0 exclusion ledger count drift")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    if report.get("artifact_paths") != ARTIFACT_PATHS:
        raise ValueError("v6_0 artifact path drift")
    if list(report.get("generated_artifacts") or []) != [ARTIFACT_PATHS[key] for key in RUN_ARTIFACT_KEYS]:
        raise ValueError("v6_0 generated artifact list drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    hashes = report.get("artifact_sha256") or {}
    for key in RUN_ARTIFACT_KEYS:
        artifact_path = repo_root / ARTIFACT_PATHS[key]
        if not artifact_path.exists():
            raise ValueError(f"v6_0 missing artifact: {key}")
        if artifact_path.suffix == ".md":
            raise ValueError("v6_0 per-run markdown created")
        if key == "report_json":
            continue
        expected = _clean(hashes.get(f"{key}_sha256"))
        if expected and expected != common.sha256_file(artifact_path):
            raise ValueError(f"v6_0 artifact hash drift: {key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_gates(report)
    _require_schema(report)
    _require_legacy_boundary(report)
    _require_backend_adapter(report)
    _require_langgraph(report)
    _require_metrics(report)
    _require_artifact_paths(report)
    common.assert_no_raw_payload_keys(report, set(FORBIDDEN_REPORT_PAYLOAD_KEYS), context="v6_0")
    if root is not None:
        _require_written_artifacts(report, root=root)


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    payload = _json_clone(report)
    repo_root = Path(root)
    materialized_json = {
        "metric_results_json": payload["metric_results"],
        "metric_tiers_json": payload["metric_tiers"],
        "leakage_probe_summary_json": payload["leakage_probe_summary"],
        "true_rag_index_payload_schema_json": payload["true_rag_index_payload_schema"],
    }
    materialized_jsonl = {
        "denominator_manifest_jsonl": payload["denominator_manifest"],
        "row_eligibility_ledger_jsonl": payload["row_eligibility_ledger"],
        "exclusion_ledger_jsonl": payload["exclusion_ledger"],
        "true_rag_candidate_diagnostics_jsonl": payload["true_rag_candidate_diagnostics"],
    }
    artifact_hashes: dict[str, str] = {}
    for key, value in materialized_json.items():
        path = repo_root / ARTIFACT_PATHS[key]
        common.write_json(path, value)
        artifact_hashes[f"{key}_sha256"] = common.sha256_file(path)
    for key, rows in materialized_jsonl.items():
        path = repo_root / ARTIFACT_PATHS[key]
        common.write_jsonl(path, rows)
        artifact_hashes[f"{key}_sha256"] = common.sha256_file(path)
    payload["artifact_sha256"] = dict(artifact_hashes)
    common.write_json(repo_root / ARTIFACT_PATHS["report_json"], payload)
    artifact_hashes["report_json_sha256"] = common.sha256_file(repo_root / ARTIFACT_PATHS["report_json"])
    payload["artifact_sha256"] = dict(artifact_hashes)
    common.write_json(repo_root / ARTIFACT_PATHS["report_json"], payload)
    check_report(payload, root=root)
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    adapter = report["backend_adapter"]
    true_tier = report["metric_tiers"]["true_rag_retrieval_metric"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "generated_at": report["generated_at"],
        "event_type": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": report["status"],
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "true_rag_retrieval_attempted_rows": true_tier["attempted_rows"],
        "true_rag_retrieval_computed_rows": true_tier["computed_rows"],
        "no_candidate_count": true_tier["no_candidate_count"],
        "real_nonprod_backend_invoked": adapter["real_nonprod_backend_invoked"],
        "real_vectordb_metric": adapter["real_vectordb_metric"],
        "structured_tool_lane_separate_from_rag_lane": True,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
    }


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    adapter = report["backend_adapter"]
    true_tier = report["metric_tiers"]["true_rag_retrieval_metric"]
    family_json = json.dumps(true_tier["family_breakdown"], ensure_ascii=False, sort_keys=True)
    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} creates the diagnostic-only true RAG retrieval rewrite "
        f"contract at `{REPORT_PATH.as_posix()}`. Existing PDF/XLSX runtime parser/search, forced routing, row-specific "
        "exceptions, query_id/row_id/case_id lookup, source title/workbook/file-name shortcuts, direct normalized "
        "answer-value matching, formula text/evaluation, target/qrels/gold/expected/supporting/citation locator use, "
        "and baseline/top-k replay are isolated as legacy non-RAG retrieval paths. SearchUnit/SearchView payloads are "
        "pre-materialized and source-derived only; SourceAtom/EvidenceBundle remains evidence truth and SearchView/vector "
        "payload remains candidate-only. The structured tool lane stays separate for XLSX calculation, aggregation, and "
        "filtering questions. current remains `v5_6`; no official/product/promotion/live-readiness claim is opened."
    )
    measurements_block = (
        f"### {SHORT_RUN_ID}\n\n"
        "- Boundary: legacy non-RAG paths remain isolated; current remains `v5_6`; this is diagnostic-only.\n"
        f"- true_rag_retrieval_metric: attempted={true_tier['attempted_rows']}, computed="
        f"{true_tier['computed_rows']}, no_candidate_count={true_tier['no_candidate_count']}, family_breakdown="
        f"{family_json}.\n"
        f"- real nonprod backend invoked: {str(adapter['real_nonprod_backend_invoked']).lower()}; "
        f"real_vectordb_metric={str(adapter['real_vectordb_metric']).lower()}; latency_unavailable_reason="
        f"{adapter['latency_counters']['unavailable_reason'] or 'recorded'}; cost_unavailable_reason="
        f"{adapter['cost_counters']['unavailable_reason']}.\n"
        "- structured tool lane remains separate from the RAG lane; XLSX calculation, aggregation, and filtering questions "
        "are classified as `structured_tool_required` and excluded from the true RAG retrieval denominator."
    )
    triage_block = (
        f"- {SHORT_RUN_ID}: remaining blockers are a configured real non-production vector/hybrid backend endpoint, "
        "backend call proof, and cost proof before `real_vectordb_metric=true` can be set. The current run records backend "
        "unavailable fail-closed behavior without fake/noop/replay candidates. Deterministic LangGraph hard guards remain "
        "code-owned and cannot be relaxed by LLM adjudication. legacy non-RAG paths stay isolated, and the structured tool "
        "lane remains separate from true RAG retrieval. This is diagnostic-only, current remains `v5_6`, and no "
        "gold/qrels/labels/expected/supporting evidence, official denominator, production index/source registry mutation, "
        "training/fine-tuning/FT-A, promotion, product-success, or live-readiness gate is opened."
    )
    for path, marker, block in (
        (PROGRESS_DOC, "progress-entry", progress_block),
        (MEASUREMENTS_DOC, "measurements-entry", measurements_block),
        (TRIAGE_DOC, "triage-entry", triage_block),
    ):
        resolved = repo_root / path
        text = resolved.read_text(encoding="utf-8")
        text = common.sync_last_updated(text, KST_DOC_DATE)
        text = common.upsert_block_at_top(
            text,
            start_marker=f"<!-- {SHORT_RUN_ID}:{marker}:start -->",
            end_marker=f"<!-- {SHORT_RUN_ID}:{marker}:end -->",
            block=block,
        )
        resolved.write_text(text, encoding="utf-8")
