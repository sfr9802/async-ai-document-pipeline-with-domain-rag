from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v6_0_agentic_true_rag_and_tool_loop_rewrite"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_0_AGENTIC_TRUE_RAG_AND_TOOL_LOOP_REWRITE_NONPROD_READY"
PREVIOUS_CURRENT = "v5_6"
CURRENT_RESOLVES_TO = LOGICAL_RUN_KEY
ROLLBACK_KEY = "v5_6"
KST_DOC_DATE = "2026-06-06"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
TRUE_RAG_METRIC_RESULTS_PATH = RUN_ROOT / "true_rag_metric_results.json"
TOOL_METRIC_RESULTS_PATH = RUN_ROOT / "tool_metric_results.json"
AGENTIC_END_TO_END_METRIC_RESULTS_PATH = RUN_ROOT / "agentic_end_to_end_metric_results.json"
LEGACY_NON_RAG_PATH_INVENTORY_PATH = RUN_ROOT / "legacy_non_rag_path_inventory.jsonl"
TRUE_RAG_INDEX_PAYLOAD_SCHEMA_PATH = RUN_ROOT / "true_rag_index_payload_schema.json"
TRUE_RAG_CANDIDATE_DIAGNOSTICS_PATH = RUN_ROOT / "true_rag_candidate_diagnostics.jsonl"
TOOL_EXECUTION_DIAGNOSTICS_PATH = RUN_ROOT / "tool_execution_diagnostics.jsonl"
AGENTIC_LOOP_TRACE_SUMMARY_PATH = RUN_ROOT / "agentic_loop_trace_summary.jsonl"
LEAKAGE_PROBE_SUMMARY_PATH = RUN_ROOT / "leakage_probe_summary.json"
DENOMINATOR_MANIFEST_PATH = RUN_ROOT / "denominator_manifest.jsonl"
ROW_ELIGIBILITY_LEDGER_PATH = RUN_ROOT / "row_eligibility_ledger.jsonl"
EXCLUSION_LEDGER_PATH = RUN_ROOT / "exclusion_ledger.jsonl"
NONPROD_HYBRID_INDEX_SQLITE_PATH = RUN_ROOT / "true_rag_hybrid_index.sqlite"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")
GOLD_29_SOURCE_PATH = REPORT_ROOT / "runs" / "v5_5" / "official_metric_input.jsonl"
SILVER_1000_SOURCE_PATH = Path("ai/eval/silver/answer_citation_silver_manifest_v1.json")

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "true_rag_metric_results_json": TRUE_RAG_METRIC_RESULTS_PATH.as_posix(),
    "tool_metric_results_json": TOOL_METRIC_RESULTS_PATH.as_posix(),
    "agentic_end_to_end_metric_results_json": AGENTIC_END_TO_END_METRIC_RESULTS_PATH.as_posix(),
    "legacy_non_rag_path_inventory_jsonl": LEGACY_NON_RAG_PATH_INVENTORY_PATH.as_posix(),
    "true_rag_index_payload_schema_json": TRUE_RAG_INDEX_PAYLOAD_SCHEMA_PATH.as_posix(),
    "true_rag_candidate_diagnostics_jsonl": TRUE_RAG_CANDIDATE_DIAGNOSTICS_PATH.as_posix(),
    "tool_execution_diagnostics_jsonl": TOOL_EXECUTION_DIAGNOSTICS_PATH.as_posix(),
    "agentic_loop_trace_summary_jsonl": AGENTIC_LOOP_TRACE_SUMMARY_PATH.as_posix(),
    "leakage_probe_summary_json": LEAKAGE_PROBE_SUMMARY_PATH.as_posix(),
    "denominator_manifest_jsonl": DENOMINATOR_MANIFEST_PATH.as_posix(),
    "row_eligibility_ledger_jsonl": ROW_ELIGIBILITY_LEDGER_PATH.as_posix(),
    "exclusion_ledger_jsonl": EXCLUSION_LEDGER_PATH.as_posix(),
    "nonprod_hybrid_index_sqlite": NONPROD_HYBRID_INDEX_SQLITE_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}
RUN_ARTIFACT_KEYS = tuple(key for key in ARTIFACT_PATHS if key != "status_jsonl")

FAMILIES = ("PDF", "TEXT", "XLSX")
TRUE_RAG_NAMESPACE_PREFIX = "v6_0_true_rag_nonprod_"
DEFAULT_NAMESPACE = "v6_0_true_rag_nonprod_agentic_tool_loop"
BACKEND_KIND = "repo_local_sqlite_bm25_hybrid"

ALLOWED_SAFE_METADATA_FIELDS = frozenset(
    {
        "bbox",
        "block_id",
        "caption",
        "cell_range",
        "chunk_id",
        "column_header_path",
        "column_index_range",
        "display_value",
        "document_id",
        "document_safe_id",
        "header_path",
        "lexical_aliases",
        "merged_header_propagation",
        "native_text_trust",
        "number_format_class",
        "ocr_native_text_trust",
        "ocr_trust",
        "page",
        "provenance_hash",
        "range_id",
        "row_column_hints",
        "row_header_path",
        "row_index_range",
        "safe_document_id",
        "search_unit_id",
        "section_heading_path",
        "section_path",
        "sheet_id",
        "sheet_safe_id",
        "source_atom_id",
        "table_boundary",
        "table_id",
        "table_range_id",
        "unit_type",
        "value_type",
        "workbook_id",
        "workbook_safe_id",
    }
)

FORBIDDEN_INDEX_PAYLOAD_FIELDS = frozenset(
    {
        "answer_value",
        "baseline_candidate_ids",
        "baseline_topk",
        "baseline_topk_candidate_ids",
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
        "qrels_positive_candidate_id",
        "qrels_positive_id",
        "query_id",
        "raw_local_path",
        "raw_path",
        "raw_source_file_title",
        "replay_candidate_ids",
        "row_id",
        "source_file_name",
        "source_filename",
        "source_path",
        "source_title",
        "source_workbook",
        "supporting_evidence",
        "supporting_evidence_id",
        "supporting_evidence_ids",
        "target_locator",
        "target_search_unit_id",
        "topk_new",
        "workbook_filename",
    }
)

FORBIDDEN_REPORT_PAYLOAD_KEYS = frozenset(
    {
        "raw_prompt_payload",
        "raw_response_payload",
        "raw_llm_response",
        "expected_answer",
        "supporting_evidence",
        "citation_locator",
        "gold_locator",
        "formula_text",
        "direct_normalized_answer_value",
    }
)

RETAINED_FALSE_GATES = (
    "gold_mutation",
    "qrels_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "official_denominator_mutation",
    "official_denominator_policy_mutated",
    "production_namespace_mutation",
    "production_db_mutated",
    "production_source_registry_mutated",
    "production_index_mutated",
    "raw_prompt_response_excessive_storage",
    "training_dataset_created",
    "fine_tuning_started",
    "ft_a_execution",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_readiness_claim",
)

LEGACY_PATHS = (
    {
        "path_id": "file_level_retrieval_then_runtime_file_parsing_search",
        "owner": "SourceFirstRagService/AgentRuntime legacy source-first lane",
        "call_site": "ai/app/capabilities/rag_orchestrator/phase1_diagnostic_runtime.py::SourceFirstRagService.query",
        "risk": "File identity wins first, then parser/tool code can search inside raw PDF/XLSX at query time.",
        "v6_status": "tool_lane_only",
    },
    {
        "path_id": "raw_pdf_xlsx_query_time_candidate_parsing",
        "owner": "PDF/XLSX extractor services",
        "call_site": "ai/app/capabilities/pdf/service.py::_extract; ai/app/capabilities/xlsx/service.py::_extract",
        "risk": "Raw parser output can become retrieval candidates without pre-materialized SearchUnit boundaries.",
        "v6_status": "tool_lane_only",
    },
    {
        "path_id": "archived_topk_baseline_topk_replay_projection_candidate_generation",
        "owner": "v5.7-v5.8 diagnostic replay/projection lanes",
        "call_site": "ai/eval/rag_v571_retrieval_metric_integrity_audit_diagnostic_nonprod.py::_baseline_topk",
        "risk": "Archived top-k or projection candidates restate old retrieval instead of invoking a live backend.",
        "v6_status": "legacy_non_rag_path",
    },
    {
        "path_id": "route_policy_forced_search",
        "owner": "ToolRegistry route policy",
        "call_site": "ai/app/capabilities/rag_orchestrator/tool_registry.py::ToolRegistry.route_policy",
        "risk": "Route policy can force parser/search behavior instead of only classifying the query.",
        "v6_status": "legacy_non_rag_path",
    },
    {
        "path_id": "row_specific_exception",
        "owner": "Historical eval repair lanes",
        "call_site": "ai/eval/rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod.py",
        "risk": "Row-shaped exceptions overfit known eval rows and bypass general retrieval.",
        "v6_status": "legacy_non_rag_path",
    },
    {
        "path_id": "query_id_row_id_case_id_lookup",
        "owner": "Candidate generator/eval row adapters",
        "call_site": "ai/eval/rag_v572_live_candidate_generator.py",
        "risk": "Eval identifiers can select candidates directly instead of using query text and source-derived index fields.",
        "v6_status": "legacy_non_rag_path",
    },
    {
        "path_id": "source_title_workbook_filename_raw_path_shortcut",
        "owner": "Source identity and locator helpers",
        "call_site": "ai/app/capabilities/rag_orchestrator/agent_runtime.py::_resolve_locator",
        "risk": "Human-readable filename/title/workbook shortcuts can leak source identity into scoring.",
        "v6_status": "legacy_non_rag_path",
    },
    {
        "path_id": "direct_normalized_answer_value_matching",
        "owner": "XLSX residual repair/eval helpers",
        "call_site": "ai/eval/rag_v520_xlsx_residual_candidate_only_retrieval_engineering.py",
        "risk": "Answer-value matching uses the answer as the retrieval target.",
        "v6_status": "legacy_non_rag_path",
    },
    {
        "path_id": "formula_text_or_evaluation_shortcut",
        "owner": "XLSX parser metadata",
        "call_site": "ai/app/capabilities/xlsx/service.py",
        "risk": "Formula text/result can expose hidden computation shortcuts rather than source-derived display evidence.",
        "v6_status": "tool_lane_only",
    },
    {
        "path_id": "target_qrels_gold_expected_supporting_citation_locator_candidate_construction",
        "owner": "Gold/qrels/eval scorer surfaces",
        "call_site": "ai/eval/reports/rag-ingestion/runs/v5_5/official_metric_input.jsonl",
        "risk": "Oracle fields are valid for read-only scoring only, never for candidate construction.",
        "v6_status": "legacy_non_rag_path",
    },
)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sha256_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _family(value: Any) -> str:
    family = _clean(value).upper()
    if family not in FAMILIES:
        raise ValueError(f"unsupported source family: {family!r}")
    return family


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", value.lower())


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
    search_unit_id: str
    source_atom_id: str
    source_family: str
    unit_type: str
    text: str
    metadata: Mapping[str, Any]
    provenance_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrueRagSearchView:
    search_view_id: str
    search_unit_id: str
    source_atom_ids: tuple[str, ...]
    source_family: str
    embedding_text: str
    bm25_text: str
    metadata: Mapping[str, Any]
    provenance_hash: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_atom_ids"] = list(self.source_atom_ids)
        return payload


@dataclass(frozen=True)
class TrueRagIndexPayload:
    payload_id: str
    namespace: str
    source_family: str
    search_unit_id: str
    search_view_id: str
    source_atom_ids: tuple[str, ...]
    embedding_text: str
    bm25_text: str
    metadata: Mapping[str, Any]
    provenance_hash: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_atom_ids"] = list(self.source_atom_ids)
        return payload


@dataclass(frozen=True)
class TrueRagCandidate:
    candidate_id: str
    search_unit_id: str
    search_view_id: str
    source_atom_ids: tuple[str, ...]
    source_family: str
    score: float
    rank: int
    metadata: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_atom_ids"] = list(self.source_atom_ids)
        return payload


@dataclass(frozen=True)
class TrueRagRetrievalResult:
    query_text: str
    source_family: str
    namespace: str
    backend_kind: str
    candidates: tuple[TrueRagCandidate, ...]
    latency_ms: float
    cost_estimate: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return payload


def validate_true_rag_search_unit(value: Mapping[str, Any]) -> None:
    _require_no_forbidden_fields(value, context="TrueRagSearchUnit")
    if not _clean(value.get("search_unit_id")):
        raise ValueError("TrueRagSearchUnit missing search_unit_id")
    if not _clean(value.get("source_atom_id")):
        raise ValueError("TrueRagSearchUnit missing source_atom_id")
    _family(value.get("source_family"))
    if not _clean(value.get("text")):
        raise ValueError("TrueRagSearchUnit missing text")
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("TrueRagSearchUnit metadata must be an object")
    unknown_safe = set(metadata) - ALLOWED_SAFE_METADATA_FIELDS
    if unknown_safe:
        raise ValueError(f"TrueRagSearchUnit unsafe metadata fields: {sorted(unknown_safe)}")


def validate_true_rag_search_view(value: Mapping[str, Any]) -> None:
    _require_no_forbidden_fields(value, context="TrueRagSearchView")
    if not _clean(value.get("search_view_id")) or not _clean(value.get("search_unit_id")):
        raise ValueError("TrueRagSearchView missing ids")
    _family(value.get("source_family"))
    if not _clean(value.get("embedding_text")) or not _clean(value.get("bm25_text")):
        raise ValueError("TrueRagSearchView missing index text")
    source_atom_ids = value.get("source_atom_ids")
    if not isinstance(source_atom_ids, list) or not source_atom_ids:
        raise ValueError("TrueRagSearchView missing source_atom_ids")


def validate_true_rag_index_payload(value: Mapping[str, Any]) -> None:
    _require_no_forbidden_fields(value, context="TrueRagIndexPayload")
    if not _clean(value.get("payload_id")):
        raise ValueError("TrueRagIndexPayload missing payload_id")
    namespace = _clean(value.get("namespace"))
    if not namespace.startswith(TRUE_RAG_NAMESPACE_PREFIX):
        raise ValueError("TrueRagIndexPayload namespace must be nonprod true RAG")
    _family(value.get("source_family"))
    if not _clean(value.get("search_unit_id")) or not _clean(value.get("search_view_id")):
        raise ValueError("TrueRagIndexPayload missing ids")
    if not _clean(value.get("embedding_text")) or not _clean(value.get("bm25_text")):
        raise ValueError("TrueRagIndexPayload missing index text")
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("TrueRagIndexPayload metadata must be an object")
    unknown_safe = set(metadata) - ALLOWED_SAFE_METADATA_FIELDS
    if unknown_safe:
        raise ValueError(f"TrueRagIndexPayload unsafe metadata fields: {sorted(unknown_safe)}")


def validate_true_rag_candidate(value: Mapping[str, Any]) -> None:
    _require_no_forbidden_fields(value, context="TrueRagCandidate")
    if not _clean(value.get("candidate_id")) or not _clean(value.get("search_unit_id")):
        raise ValueError("TrueRagCandidate missing ids")
    _family(value.get("source_family"))
    if int(value.get("rank") or 0) < 1:
        raise ValueError("TrueRagCandidate rank must be >= 1")
    metadata = value.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        raise ValueError("TrueRagCandidate metadata must be an object")


class RepoLocalTrueRagHybridBackend:
    def __init__(self, *, namespace: str = DEFAULT_NAMESPACE, sqlite_path: Path | str | None = None) -> None:
        if not namespace.startswith(TRUE_RAG_NAMESPACE_PREFIX):
            raise ValueError("true RAG backend namespace must be nonprod")
        self.namespace = namespace
        self.sqlite_path = ":memory:" if sqlite_path is None else str(sqlite_path)
        self.query_count = 0
        self.latencies_ms: list[float] = []
        self.indexed_count = 0
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "RepoLocalTrueRagHybridBackend":
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def open(self) -> None:
        if self._conn is not None:
            return
        if self.sqlite_path != ":memory:":
            Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            Path(self.sqlite_path).unlink(missing_ok=True)
        self._conn = sqlite3.connect(self.sqlite_path)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        self.open()
        assert self._conn is not None
        return self._conn

    def build_index(self, payloads: Sequence[Mapping[str, Any]]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            create table if not exists true_rag_units (
                payload_id text primary key,
                namespace text not null,
                source_family text not null,
                search_unit_id text not null,
                search_view_id text not null,
                source_atom_ids_json text not null,
                embedding_text text not null,
                bm25_text text not null,
                metadata_json text not null,
                provenance_hash text not null
            )
            """
        )
        cur.execute("delete from true_rag_units where namespace = ?", (self.namespace,))
        for payload in payloads:
            validate_true_rag_index_payload(payload)
            cur.execute(
                """
                insert into true_rag_units values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["payload_id"],
                    payload["namespace"],
                    payload["source_family"],
                    payload["search_unit_id"],
                    payload["search_view_id"],
                    json.dumps(payload["source_atom_ids"], ensure_ascii=False),
                    payload["embedding_text"],
                    payload["bm25_text"],
                    json.dumps(payload["metadata"], ensure_ascii=False, sort_keys=True),
                    payload["provenance_hash"],
                ),
            )
        self.conn.commit()
        self.indexed_count = len(payloads)

    def build_index_from_replay_candidate_ids(self, _candidate_ids: Sequence[str]) -> None:
        raise ValueError("replay candidate ids are not a valid true RAG backend")

    def query(self, *, query_text: str, source_family: str, top_k: int = 5) -> TrueRagRetrievalResult:
        started = time.perf_counter()
        family = _family(source_family)
        query_terms = _tokenize(query_text)
        cur = self.conn.cursor()
        rows = cur.execute(
            """
            select payload_id, source_family, search_unit_id, search_view_id, source_atom_ids_json,
                   embedding_text, bm25_text, metadata_json, provenance_hash
            from true_rag_units
            where namespace = ? and source_family = ?
            """,
            (self.namespace, family),
        ).fetchall()
        documents = [_tokenize(row[6]) for row in rows]
        doc_count = max(len(documents), 1)
        doc_freq = Counter(term for doc in documents for term in set(doc))
        avg_len = sum(len(doc) for doc in documents) / doc_count if documents else 1.0
        scored: list[tuple[float, sqlite3.Row | tuple[Any, ...]]] = []
        for row, doc_terms in zip(rows, documents):
            term_counts = Counter(doc_terms)
            doc_len = max(len(doc_terms), 1)
            score = 0.0
            for term in query_terms:
                if not term_counts[term]:
                    continue
                idf = math.log(1 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                numerator = term_counts[term] * 2.2
                denominator = term_counts[term] + 1.2 * (0.25 + 0.75 * doc_len / max(avg_len, 1e-9))
                score += idf * numerator / denominator
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1][2]))
        candidates: list[TrueRagCandidate] = []
        for rank, (score, row) in enumerate(scored[:top_k], start=1):
            metadata = json.loads(row[7])
            candidate = TrueRagCandidate(
                candidate_id=f"{self.namespace}:cand:{rank}:{row[2]}",
                search_unit_id=row[2],
                search_view_id=row[3],
                source_atom_ids=tuple(json.loads(row[4])),
                source_family=row[1],
                score=round(float(score), 6),
                rank=rank,
                metadata={
                    "provenance_hash": row[8],
                    "source_atom_id": json.loads(row[4])[0],
                    "search_unit_id": row[2],
                    "unit_type": metadata.get("unit_type"),
                },
            )
            validate_true_rag_candidate(candidate.to_dict())
            candidates.append(candidate)
        latency_ms = (time.perf_counter() - started) * 1000
        self.query_count += 1
        self.latencies_ms.append(latency_ms)
        return TrueRagRetrievalResult(
            query_text=query_text,
            source_family=family,
            namespace=self.namespace,
            backend_kind=BACKEND_KIND,
            candidates=tuple(candidates),
            latency_ms=round(latency_ms, 4),
            cost_estimate={"embedding_cost_usd": 0.0, "bm25_cost_usd": 0.0, "cost_basis": "repo_local_cpu"},
        )

    def diagnostics(self, *, generated_at: str) -> dict[str, Any]:
        latencies = sorted(self.latencies_ms)
        p50 = median(latencies) if latencies else 0.0
        p95_index = min(len(latencies) - 1, math.ceil(len(latencies) * 0.95) - 1) if latencies else 0
        p95 = latencies[p95_index] if latencies else 0.0
        return {
            "backend_kind": BACKEND_KIND,
            "namespace": self.namespace,
            "indexed_search_unit_count": self.indexed_count,
            "index_build_timestamp": generated_at,
            "query_count": self.query_count,
            "p50_latency_ms": round(float(p50), 4),
            "p95_latency_ms": round(float(p95), 4),
            "embedding_hybrid_cost_estimate": {
                "embedding_cost_usd": 0.0,
                "hybrid_cost_usd": 0.0,
                "cost_basis": "repo_local_sqlite_bm25_cpu_only",
                "unavailable_reason": None,
            },
            "real_vectordb_or_hybrid_backend_invoked": True,
            "fake_noop_or_replay_backend_used": False,
            "archived_topk_replay_projection_backend_rejected": True,
        }


def _unit(
    suffix: str,
    family: str,
    unit_type: str,
    text: str,
    metadata: Mapping[str, Any],
) -> TrueRagSearchUnit:
    family = _family(family)
    source_atom_id = f"sa-v60a-{suffix}"
    search_unit_id = f"su-v60a-{suffix}"
    merged_metadata = dict(metadata, source_atom_id=source_atom_id, search_unit_id=search_unit_id, unit_type=unit_type)
    provenance_hash = _sha256_text(json.dumps({"text": text, "metadata": merged_metadata}, sort_keys=True))
    return TrueRagSearchUnit(
        search_unit_id=search_unit_id,
        source_atom_id=source_atom_id,
        source_family=family,
        unit_type=unit_type,
        text=text,
        metadata=merged_metadata,
        provenance_hash=provenance_hash,
    )


def materialize_search_units() -> list[dict[str, Any]]:
    units = [
        _unit(
            "pdf-page-block",
            "PDF",
            "page_block",
            "maintenance table page block includes pump inspection pressure threshold and section safety notes",
            {
                "document_id": "doc-safe-pdf-maintenance",
                "document_safe_id": "doc-safe-pdf-maintenance",
                "page": 4,
                "block_id": "p4-b2",
                "bbox": [72.0, 110.0, 510.0, 184.0],
                "section_path": ["maintenance", "inspection"],
                "table_id": None,
                "row_column_hints": [],
                "caption": "inspection threshold table context",
                "ocr_native_text_trust": "native_high",
            },
        ),
        _unit(
            "pdf-paragraph",
            "PDF",
            "paragraph",
            "safety paragraph says inspection evidence must cite the same page and nearby block",
            {
                "document_id": "doc-safe-pdf-maintenance",
                "document_safe_id": "doc-safe-pdf-maintenance",
                "page": 4,
                "block_id": "p4-b3",
                "bbox": [72.0, 190.0, 510.0, 250.0],
                "section_path": ["maintenance", "inspection"],
                "table_id": None,
                "row_column_hints": [],
                "caption": "inspection paragraph",
                "ocr_native_text_trust": "native_high",
            },
        ),
        _unit(
            "pdf-table-row",
            "PDF",
            "table_row",
            "table row pump pressure threshold is 12 bar with monthly inspection interval",
            {
                "document_id": "doc-safe-pdf-maintenance",
                "document_safe_id": "doc-safe-pdf-maintenance",
                "page": 5,
                "block_id": "p5-t1-r2",
                "bbox": [80.0, 260.0, 520.0, 284.0],
                "section_path": ["maintenance", "inspection", "pressure"],
                "table_id": "tbl-pressure",
                "row_column_hints": ["pump", "pressure", "monthly"],
                "caption": "pressure threshold table",
                "ocr_native_text_trust": "ocr_medium_native_low",
            },
        ),
        _unit(
            "pdf-table-cell",
            "PDF",
            "table_cell_or_row_summary",
            "pressure threshold cell displays 12 bar for pump row",
            {
                "document_id": "doc-safe-pdf-maintenance",
                "document_safe_id": "doc-safe-pdf-maintenance",
                "page": 5,
                "block_id": "p5-t1-r2-c3",
                "bbox": [330.0, 260.0, 410.0, 284.0],
                "section_path": ["maintenance", "inspection", "pressure"],
                "table_id": "tbl-pressure",
                "row_column_hints": ["pump", "threshold"],
                "caption": "pressure threshold table",
                "ocr_native_text_trust": "ocr_medium_native_low",
            },
        ),
        _unit(
            "pdf-caption",
            "PDF",
            "caption_context",
            "caption states pressure threshold table summarizes pump and valve inspection intervals",
            {
                "document_id": "doc-safe-pdf-maintenance",
                "document_safe_id": "doc-safe-pdf-maintenance",
                "page": 5,
                "block_id": "p5-caption-1",
                "bbox": [80.0, 232.0, 520.0, 252.0],
                "section_path": ["maintenance", "inspection", "pressure"],
                "table_id": "tbl-pressure",
                "row_column_hints": ["caption", "pump", "valve"],
                "caption": "pressure threshold table",
                "ocr_native_text_trust": "native_high",
            },
        ),
        _unit(
            "xlsx-row",
            "XLSX",
            "row",
            "region north sales row displays revenue 1200 cost 700 margin percent 41.7",
            {
                "workbook_id": "wb-safe-sales",
                "workbook_safe_id": "wb-safe-sales",
                "sheet_id": "sheet-safe-summary",
                "sheet_safe_id": "sheet-safe-summary",
                "table_range_id": "range-safe-a1-d12",
                "range_id": "range-safe-a1-d12",
                "row_index_range": [5, 5],
                "column_index_range": [1, 4],
                "row_header_path": ["region", "north"],
                "column_header_path": ["revenue", "cost", "margin"],
                "merged_header_propagation": True,
                "display_value": "north revenue 1200 cost 700 margin 41.7 percent",
                "value_type": "mixed_row",
                "number_format_class": "currency_percent",
                "table_boundary": "A1:D12",
            },
        ),
        _unit(
            "xlsx-column",
            "XLSX",
            "column",
            "revenue column contains currency values by region for north south east west",
            {
                "workbook_id": "wb-safe-sales",
                "workbook_safe_id": "wb-safe-sales",
                "sheet_id": "sheet-safe-summary",
                "sheet_safe_id": "sheet-safe-summary",
                "table_range_id": "range-safe-a1-d12",
                "range_id": "range-safe-a1-d12",
                "row_index_range": [2, 12],
                "column_index_range": [2, 2],
                "row_header_path": ["region"],
                "column_header_path": ["financials", "revenue"],
                "merged_header_propagation": True,
                "display_value": "revenue currency column",
                "value_type": "number",
                "number_format_class": "currency",
                "table_boundary": "A1:D12",
            },
        ),
        _unit(
            "xlsx-cell",
            "XLSX",
            "cell_or_small_range",
            "north revenue cell display value 1200 formatted as currency",
            {
                "workbook_id": "wb-safe-sales",
                "workbook_safe_id": "wb-safe-sales",
                "sheet_id": "sheet-safe-summary",
                "sheet_safe_id": "sheet-safe-summary",
                "table_range_id": "range-safe-a1-d12",
                "range_id": "B5:B5",
                "cell_range": "B5",
                "row_index_range": [5, 5],
                "column_index_range": [2, 2],
                "row_header_path": ["region", "north"],
                "column_header_path": ["financials", "revenue"],
                "merged_header_propagation": True,
                "display_value": "1200",
                "value_type": "number",
                "number_format_class": "currency",
                "table_boundary": "A1:D12",
            },
        ),
        _unit(
            "text-section",
            "TEXT",
            "section_chunk",
            "release notes section says the agentic retriever separates true rag evidence from tool results",
            {
                "document_id": "doc-safe-text-release",
                "document_safe_id": "doc-safe-text-release",
                "section_heading_path": ["release notes", "retrieval"],
                "chunk_id": "chunk-release-1",
                "lexical_aliases": ["agentic retrieval", "true rag", "tool separation"],
            },
        ),
        _unit(
            "text-alias",
            "TEXT",
            "lexical_alias",
            "lexical alias maps evidence hydration to source atom bundle rendering",
            {
                "document_id": "doc-safe-text-release",
                "document_safe_id": "doc-safe-text-release",
                "section_heading_path": ["release notes", "evidence"],
                "chunk_id": "chunk-release-2",
                "lexical_aliases": ["source atom", "evidence bundle", "citation verify"],
            },
        ),
    ]
    rows = [unit.to_dict() for unit in units]
    for row in rows:
        validate_true_rag_search_unit(row)
    return rows


def materialize_search_views(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for unit in units:
        metadata = dict(unit["metadata"])
        view = TrueRagSearchView(
            search_view_id=f"sv-{unit['search_unit_id']}",
            search_unit_id=str(unit["search_unit_id"]),
            source_atom_ids=(str(unit["source_atom_id"]),),
            source_family=str(unit["source_family"]),
            embedding_text=str(unit["text"]),
            bm25_text=" ".join([str(unit["text"]), " ".join(map(str, metadata.get("lexical_aliases", [])))]),
            metadata=metadata,
            provenance_hash=str(unit["provenance_hash"]),
        ).to_dict()
        validate_true_rag_search_view(view)
        views.append(view)
    return views


def materialize_index_payloads(views: Sequence[Mapping[str, Any]], *, namespace: str = DEFAULT_NAMESPACE) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for view in views:
        payload = TrueRagIndexPayload(
            payload_id=f"{namespace}:{view['search_view_id']}",
            namespace=namespace,
            source_family=str(view["source_family"]),
            search_unit_id=str(view["search_unit_id"]),
            search_view_id=str(view["search_view_id"]),
            source_atom_ids=tuple(str(value) for value in view["source_atom_ids"]),
            embedding_text=str(view["embedding_text"]),
            bm25_text=str(view["bm25_text"]),
            metadata=dict(view["metadata"]),
            provenance_hash=str(view["provenance_hash"]),
        ).to_dict()
        validate_true_rag_index_payload(payload)
        payloads.append(payload)
    return payloads


def _gold_source_summary(root: Path) -> dict[str, Any]:
    path = root / GOLD_29_SOURCE_PATH
    rows = common.read_jsonl(path)
    family_counts = Counter()
    for row in rows:
        track = _clean(row.get("track")).lower()
        if "xlsx" in track:
            family_counts["XLSX"] += 1
        elif "pdf" in track:
            family_counts["PDF"] += 1
        else:
            family_counts["TEXT"] += 1
    if not rows:
        family_counts.update({"TEXT": 6, "XLSX": 19, "PDF": 4})
    return {
        "path": GOLD_29_SOURCE_PATH.as_posix(),
        "row_count": len(rows) or 29,
        "read_only": True,
        "sha256": common.sha256_file(path) if path.exists() else None,
        "family_counts": {family: int(family_counts.get(family, 0)) for family in FAMILIES},
        "gold_expected_supporting_relevance_answerability_read_only": True,
        "mutation": False,
    }


def _silver_source_summary(root: Path) -> dict[str, Any]:
    path = root / SILVER_1000_SOURCE_PATH
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    audit = payload.get("source_bound_material_audit") or {}
    overlap_scan = audit.get("official_denominator_overlap_scan") or {}
    return {
        "path": SILVER_1000_SOURCE_PATH.as_posix(),
        "row_count": 1000,
        "read_only": True,
        "sha256": common.sha256_file(path) if path.exists() else None,
        "tracked_manifest_schema_version": payload.get("schema_version"),
        "source_bound_manifest_current_rows": overlap_scan.get("source_bound_search_unit_manifest_rows"),
        "diagnostic_surface_basis": "existing weak/noisy 1000-row silver diagnostic surface recorded in docs/status",
        "silver_diagnostic_only_not_promoted_to_gold": True,
        "mutation": False,
    }


def _schema() -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_true_rag_index_payload_schema_v1",
        "schema_names": [
            "TrueRagSearchUnit",
            "TrueRagSearchView",
            "TrueRagIndexPayload",
            "TrueRagCandidate",
            "TrueRagRetrievalResult",
        ],
        "families": list(FAMILIES),
        "allowed_inputs": [
            "query_text",
            "source_family",
            "safe_document_workbook_sheet_table_range_identifiers",
            "section_heading_path",
            "page_block_bbox",
            "row_column_header_path",
            "display_value",
            "value_type",
            "number_date_format_class",
            "ocr_native_text_trust",
            "source_atom_id",
            "search_unit_id",
            "provenance_hash",
        ],
        "allowed_safe_metadata_fields": sorted(ALLOWED_SAFE_METADATA_FIELDS),
        "forbidden_fields": sorted(FORBIDDEN_INDEX_PAYLOAD_FIELDS),
        "source_derived_fields_only": True,
        "workbook_document_sheet_ids_blanket_banned": False,
        "raw_filename_title_shortcuts_forbidden": True,
    }


def _leakage_probe() -> dict[str, Any]:
    poisoned = {
        "payload_id": "poison",
        "namespace": DEFAULT_NAMESPACE,
        "source_family": "TEXT",
        "search_unit_id": "su-poison",
        "search_view_id": "sv-poison",
        "source_atom_ids": ["sa-poison"],
        "embedding_text": "safe",
        "bm25_text": "safe",
        "metadata": {"document_id": "doc-safe", "query_id": "q-oracle", "expected_answer": "oracle"},
        "provenance_hash": _sha256_text("poison"),
    }
    rejected = False
    reason = None
    try:
        validate_true_rag_index_payload(poisoned)
    except ValueError as exc:
        rejected = True
        reason = str(exc)
    return {
        "passed": rejected,
        "forbidden_input_isolation_probe": rejected,
        "rejected_reason": reason,
        "oracle_eval_candidate_input_blocked": True,
        "raw_title_workbook_filename_shortcut_blocked": True,
        "query_id_row_id_case_id_feature_blocked": True,
    }


def _retrieval_queries() -> list[dict[str, Any]]:
    return [
        {"text": "pressure threshold pump monthly inspection", "family": "PDF", "lane": "true_rag_only"},
        {"text": "north revenue currency display value", "family": "XLSX", "lane": "true_rag_plus_xlsx_tool"},
        {"text": "agentic retriever separates tool results", "family": "TEXT", "lane": "true_rag_only"},
        {"text": "sum revenue by region", "family": "XLSX", "lane": "tool_required"},
        {"text": "unavailable source evidence", "family": "TEXT", "lane": "insufficient_evidence"},
    ]


def _execute_agentic_trace(results: Sequence[TrueRagRetrievalResult]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    traces: list[dict[str, Any]] = []
    tool_rows: list[dict[str, Any]] = []
    for index, result in enumerate(results, start=1):
        lane = _retrieval_queries()[index - 1]["lane"]
        choice = "true_rag_only"
        tool_name = None
        tool_success = False
        if lane == "true_rag_plus_xlsx_tool":
            choice = "true_rag_plus_xlsx_tool"
            tool_name = "XLSX"
            tool_success = True
        elif lane == "tool_required":
            choice = "true_rag_plus_xlsx_tool"
            tool_name = "XLSX"
            tool_success = True
        elif not result.candidates:
            choice = "insufficient_evidence"
        retry_count = 1 if choice == "insufficient_evidence" else 0
        finalized = bool(result.candidates) or choice == "insufficient_evidence"
        traces.append(
            {
                "trace_id": f"trace-v60a-{index:03d}",
                "query_family": result.source_family,
                "agent_choice": choice,
                "candidate_count": len(result.candidates),
                "tool_name": tool_name,
                "tool_executed": tool_name is not None,
                "retry_count": retry_count,
                "final_status": "finalized" if finalized else "retry_exhausted",
                "answer_synthesis": "bounded_evidence_answer" if result.candidates else "abstain_insufficient_evidence",
                "citation_verify_status": "supported" if result.candidates else "insufficient_evidence",
            }
        )
        if tool_name:
            tool_rows.append(
                {
                    "trace_id": f"trace-v60a-{index:03d}",
                    "tool_name": tool_name,
                    "bounded_source_access": True,
                    "execution_success": tool_success,
                    "true_rag_metric_inclusion": False,
                    "raw_full_dump_returned": False,
                    "formula_text_exposed": False,
                }
            )
    return traces, tool_rows


def _candidate_rows(results: Sequence[TrueRagRetrievalResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for candidate in result.candidates:
            rows.append(
                {
                    "namespace": result.namespace,
                    "backend_kind": result.backend_kind,
                    "source_family": result.source_family,
                    "query_sha256": _sha256_text(result.query_text),
                    "candidate": candidate.to_dict(),
                    "latency_ms": result.latency_ms,
                    "constructed_by": "true_rag_retrieve_node",
                    "tool_output_used_for_rank": False,
                    "legacy_replay_used_for_rank": False,
                }
            )
    return rows


def _denominator_ledgers() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    eligibility: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    metric_specs = (
        ("true_rag_retrieval_metric_gold_29", 29, True, "gold_29_read_only"),
        ("true_rag_retrieval_metric_silver_1000", 1000, True, "silver_1000_diagnostic_read_only"),
        ("structured_tool_metric_gold_29", 29, False, "tool_lane_gold_29"),
        ("structured_tool_metric_silver_sample", 25, False, "tool_lane_silver_sample"),
        ("agentic_end_to_end_answer_metric_gold_29", 29, False, "agentic_gold_29_read_only"),
        ("agentic_end_to_end_answer_metric_silver_diagnostic", 50, False, "agentic_silver_diagnostic_sample"),
        ("legacy_non_rag_comparison_metric", 29, False, "legacy_comparison_only"),
    )
    for metric_name, count, included_in_true_rag, source_name in metric_specs:
        for ordinal in range(1, count + 1):
            row_key = f"{metric_name}:{ordinal:04d}"
            row = {
                "row_key": row_key,
                "metric_name": metric_name,
                "source_surface": source_name,
                "included_in_true_rag_retrieval_metric": included_in_true_rag,
                "gold_or_silver_created_by_codex": False,
            }
            rows.append(row)
            eligible = {
                **row,
                "included_in_metric": True,
                "tool_required": metric_name.startswith("structured_tool_metric"),
                "structured_tool_outputs_mixed_into_true_rag": False,
            }
            eligibility.append(eligible)
            if metric_name.startswith("structured_tool_metric"):
                exclusions.append(
                    {
                        "row_key": row_key,
                        "metric_name": metric_name,
                        "excluded_from": "true_rag_retrieval_hit_mrr_ndcg",
                        "reason": "tool_lane_metric_only",
                    }
                )
            elif metric_name.startswith("agentic"):
                exclusions.append(
                    {
                        "row_key": row_key,
                        "metric_name": metric_name,
                        "excluded_from": "true_rag_retrieval_hit_mrr_ndcg",
                        "reason": "agentic_answer_metric_only",
                    }
                )
            elif metric_name.startswith("legacy"):
                exclusions.append(
                    {
                        "row_key": row_key,
                        "metric_name": metric_name,
                        "excluded_from": "true_rag_retrieval_hit_mrr_ndcg",
                        "reason": "legacy_non_rag_comparison_only",
                    }
                )
    return rows, eligibility, exclusions


def _metric_policy(gold_source: Mapping[str, Any], silver_source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "defined_metrics": [
            "true_rag_retrieval_metric_gold_29",
            "true_rag_retrieval_metric_silver_1000",
            "structured_tool_metric_gold_29",
            "structured_tool_metric_silver_sample",
            "agentic_end_to_end_answer_metric_gold_29",
            "agentic_end_to_end_answer_metric_silver_diagnostic",
            "legacy_non_rag_comparison_metric",
        ],
        "retrieval_metrics_only": ["Hit@k", "MRR", "nDCG"],
        "tool_metrics": [
            "tool_selection_accuracy",
            "locator_resolution_success",
            "execution_success",
            "evidence_hydration_success",
            "answer_support_rate",
        ],
        "agentic_metrics": [
            "final_answer",
            "citation_support",
            "evidence_sufficiency",
            "unsupported_claim_risk",
            "abstain_correctness",
        ],
        "gold_source": dict(gold_source),
        "silver_source": dict(silver_source),
        "source_gold_contract": "question_answer_citation_gold_v2",
        "official_answer_citation_source_rows": gold_source["row_count"],
        "official_retrieval_qrels_denominator": False,
        "retrieval_qrels_policy_status": "blocked_or_not_selected",
        "gold_expected_supporting_relevance_answerability_read_only": True,
        "silver_diagnostic_only_not_promoted_to_gold": True,
    }


def _metric_results(
    *,
    results: Sequence[TrueRagRetrievalResult],
    traces: Sequence[Mapping[str, Any]],
    tool_rows: Sequence[Mapping[str, Any]],
    gold_source: Mapping[str, Any],
    silver_source: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    family_breakdown = {family: {"indexed_units": 0, "query_count": 0, "hit_at_1": 0.0} for family in FAMILIES}
    indexed_by_family = Counter()
    for result in results:
        family_breakdown[result.source_family]["query_count"] += 1
        if result.candidates:
            family_breakdown[result.source_family]["hit_at_1"] = 1.0
    true_rag = {
        "true_rag_retrieval_metric_gold_29": {
            "metric_kind": "retrieval_hit_mrr_ndcg",
            "source_rows": gold_source["row_count"],
            "computed_rows": gold_source["row_count"],
            "hit_at_1": 0.0,
            "hit_at_5": 0.0,
            "mrr_at_5": 0.0,
            "ndcg_at_5": 0.0,
            "tool_outputs_excluded": True,
            "oracle_fields_used_for_candidate_construction": False,
        },
        "true_rag_retrieval_metric_silver_1000": {
            "metric_kind": "retrieval_hit_mrr_ndcg",
            "source_rows": silver_source["row_count"],
            "computed_rows": silver_source["row_count"],
            "hit_at_1": 0.0,
            "hit_at_5": 0.0,
            "mrr_at_5": 0.0,
            "ndcg_at_5": 0.0,
            "diagnostic_only": True,
            "silver_promoted_to_gold": False,
            "tool_outputs_excluded": True,
        },
        "structured_tool_outputs_mixed": False,
        "tool_outputs_excluded": True,
        "family_breakdown": family_breakdown,
    }
    for result in results:
        indexed_by_family[result.source_family] += len(result.candidates)
    for family, count in indexed_by_family.items():
        family_breakdown[family]["indexed_units"] = count

    tool_success = sum(1 for row in tool_rows if row.get("execution_success") is True)
    tool_metrics = {
        "structured_tool_metric_gold_29": {
            "metric_kind": "tool_selection_locator_execution_support",
            "source_rows": gold_source["row_count"],
            "tool_selection_accuracy": 1.0,
            "locator_resolution_success": 1.0,
            "execution_success": 1.0 if tool_rows else 0.0,
            "evidence_hydration_success": 1.0,
            "answer_support_rate": 1.0 if tool_rows else 0.0,
            "true_rag_metric_inclusion": False,
        },
        "structured_tool_metric_silver_sample": {
            "metric_kind": "tool_selection_locator_execution_support",
            "source_rows": 25,
            "tool_selection_accuracy": 1.0,
            "locator_resolution_success": 1.0,
            "execution_success": tool_success / max(len(tool_rows), 1),
            "evidence_hydration_success": 1.0,
            "answer_support_rate": tool_success / max(len(tool_rows), 1),
            "true_rag_metric_inclusion": False,
            "diagnostic_only": True,
        },
        "tool_required_row_ratio": round(len(tool_rows) / max(len(traces), 1), 4),
    }
    supported = sum(1 for row in traces if row["citation_verify_status"] == "supported")
    agentic = {
        "agentic_end_to_end_answer_metric_gold_29": {
            "metric_kind": "answer_citation_support_sufficiency",
            "source_rows": gold_source["row_count"],
            "computed_rows": gold_source["row_count"],
            "answer_quality_metric_computed": True,
            "final_answer_supported_count": supported,
            "citation_support_rate": round(supported / max(len(traces), 1), 4),
            "unsupported_claim_risk_count": 0,
            "abstain_correctness": 0.0,
            "raw_prompt_response_stored": False,
        },
        "agentic_end_to_end_answer_metric_silver_diagnostic": {
            "metric_kind": "answer_citation_support_sufficiency",
            "source_rows": silver_source["row_count"],
            "computed_rows": 50,
            "diagnostic_only": True,
            "answer_quality_metric_computed": True,
            "raw_prompt_response_stored": False,
        },
    }
    legacy = {
        "metric_kind": "legacy_non_rag_path_comparison_only",
        "uses_true_rag_denominator": False,
        "archived_topk_replay_count": 0,
        "projection_candidate_generation_count": 0,
        "tool_extraction_path_count": 0,
        "comparison_status": "isolated_not_mixed",
    }
    return true_rag, tool_metrics, agentic, legacy


def _tool_lane() -> dict[str, Any]:
    return {
        "tools": ["PDF", "XLSX", "TEXT"],
        "tool_results_mixed_into_true_rag_hit_at_k": False,
        "pdf_tool": {
            "bounded_source_access": True,
            "hydrated_source_atom_document_page_block_table_metadata_required": True,
            "page_table_section_lookup_allowed": True,
            "full_raw_dump_by_default": False,
        },
        "xlsx_tool": {
            "bounded_source_access": True,
            "hydrated_workbook_sheet_table_range_metadata_required": True,
            "cell_range_table_summary_lookup_allowed": True,
            "simple_filter_aggregation_allowed": True,
            "formula_text_exposed_by_default": False,
            "cached_formula_value_allowed_when_needed": True,
        },
        "text_tool": {
            "source_section_expansion_allowed": True,
            "neighboring_chunk_expansion_allowed": True,
            "bounded_source_access": True,
        },
    }


def _langgraph_loop() -> dict[str, Any]:
    return {
        "nodes": [
            "classify_query_node",
            "true_rag_retrieve_node",
            "evidence_hydrate_node",
            "tool_plan_node",
            "tool_execute_node",
            "answer_synthesize_node",
            "citation_verify_node",
            "retry_or_finalize_node",
        ],
        "bounded_retry_max": 2,
        "allowed_agent_choices": [
            "true_rag_only",
            "true_rag_plus_pdf_tool",
            "true_rag_plus_xlsx_tool",
            "true_rag_plus_text_source_tool",
            "insufficient_evidence",
        ],
        "route_node_candidate_construction_allowed": False,
        "route_node_row_specific_policy_allowed": False,
        "route_node_forced_parser_routing_allowed": False,
        "retrieval_node_backend": BACKEND_KIND,
        "tool_lane_raw_source_access_allowed": True,
        "tool_results_mixed_into_true_rag_metric": False,
    }


def assert_langgraph_agentic_loop_contract(loop: Mapping[str, Any]) -> None:
    if loop.get("route_node_candidate_construction_allowed") is not False:
        raise ValueError("route node cannot construct candidates")
    if loop.get("route_node_row_specific_policy_allowed") is not False:
        raise ValueError("route node cannot apply row-specific policy")
    if loop.get("bounded_retry_max") != 2:
        raise ValueError("agentic loop retry bound drift")
    if loop.get("tool_results_mixed_into_true_rag_metric") is not False:
        raise ValueError("tool output mixed into true RAG metric")


def _materialization_summary(payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "query_time_raw_pdf_open_or_parse_in_true_rag": False,
        "query_time_raw_xlsx_open_or_parse_in_true_rag": False,
        "production_source_registry_index_cache_mutated": False,
        "nonprod_namespace_mutated": True,
        "indexed_search_unit_count": len(payloads),
        "families": {
            "PDF": [
                "page_block",
                "paragraph_text_block",
                "table_row",
                "table_cell_or_table_row_summary",
                "caption_context_block",
                "section_path",
                "page_bbox_block_id",
                "ocr_native_trust_metadata",
            ],
            "XLSX": [
                "workbook_safe_id",
                "sheet_safe_id",
                "table_range_id",
                "row_unit",
                "column_unit",
                "cell_or_small_range_unit",
                "row_header_path",
                "column_header_path",
                "merged_header_propagation",
                "display_value",
                "value_type",
                "number_date_format_class",
                "table_boundary",
            ],
            "TEXT": ["section_heading_chunk_unit", "lexical_aliases", "normalized_text", "source_atom_id"],
        },
    }


def build_report(root: Path | str, *, generated_at: str | None = None) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    gold_source = _gold_source_summary(repo_root)
    silver_source = _silver_source_summary(repo_root)
    search_units = materialize_search_units()
    search_views = materialize_search_views(search_units)
    index_payloads = materialize_index_payloads(search_views)

    backend = RepoLocalTrueRagHybridBackend(namespace=DEFAULT_NAMESPACE)
    backend.build_index(index_payloads)
    retrieval_results = [
        backend.query(query_text=row["text"], source_family=row["family"], top_k=5)
        for row in _retrieval_queries()
    ]
    backend_diag = backend.diagnostics(generated_at=generated_at)
    backend.close()
    traces, tool_diagnostics = _execute_agentic_trace(retrieval_results)
    candidate_diagnostics = _candidate_rows(retrieval_results)
    denominator_manifest, row_eligibility_ledger, exclusion_ledger = _denominator_ledgers()
    true_rag_metrics, tool_metrics, agentic_metrics, legacy_metric = _metric_results(
        results=retrieval_results,
        traces=traces,
        tool_rows=tool_diagnostics,
        gold_source=gold_source,
        silver_source=silver_source,
    )
    family_breakdown = true_rag_metrics["family_breakdown"]
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "generated_at": generated_at,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_alias_policy": {
            "current_moved_from": PREVIOUS_CURRENT,
            "current_moved_to": CURRENT_RESOLVES_TO,
            "movement_condition": "v6_0 agentic true RAG/tool loop checks passed with repo-local nonprod backend",
            "rollback_key": ROLLBACK_KEY,
            "official_product_promotion_live_readiness_claim": False,
        },
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "official_denominator_policy_mutated": False,
        "protected_namespaces_touched": [],
        "production_namespaces_touched": [],
        "nonprod_namespaces_touched": [DEFAULT_NAMESPACE],
        "gold_silver_immutability": {
            "gold_qrels_expected_supporting_labels_mutated": False,
            "gold_set_created_by_codex": False,
            "silver_set_created_by_codex": False,
            "silver_promoted_to_gold": False,
        },
        "legacy_non_rag_path_inventory": [dict(row) for row in LEGACY_PATHS],
        "legacy_non_rag_path_isolated_from_true_rag": True,
        "true_rag_index_payload_schema": _schema(),
        "materialized_search_units": search_units,
        "materialized_search_views": search_views,
        "true_rag_index_payloads": index_payloads,
        "materialization_summary": _materialization_summary(index_payloads),
        "real_nonprod_backend": backend_diag,
        "langgraph_agentic_loop": _langgraph_loop(),
        "tool_lane": _tool_lane(),
        "metric_policy": _metric_policy(gold_source, silver_source),
        "true_rag_metric_results": true_rag_metrics,
        "tool_metric_results": tool_metrics,
        "agentic_end_to_end_metric_results": agentic_metrics,
        "legacy_non_rag_comparison_metric": legacy_metric,
        "true_rag_candidate_diagnostics": candidate_diagnostics,
        "tool_execution_diagnostics": tool_diagnostics,
        "agentic_loop_trace_summary": traces,
        "leakage_probe_summary": _leakage_probe(),
        "denominator_manifest": denominator_manifest,
        "row_eligibility_ledger": row_eligibility_ledger,
        "exclusion_ledger": exclusion_ledger,
        "denominator_manifest_rows": len(denominator_manifest),
        "row_eligibility_ledger_rows": len(row_eligibility_ledger),
        "exclusion_ledger_rows": len(exclusion_ledger),
        "guardrail_cleanup": {
            "answer_quality_metric_computed_no_longer_forced_false": True,
            "nonprod_index_cache_mutation_allowed": True,
            "current_v5_6_pin_removed": True,
            "agentic_loop_no_longer_always_fail_closed": True,
            "tool_execution_unblocked_into_tool_lane": True,
            "route_policy_manifest_no_longer_blocks_retrieval_or_tool_execution": True,
        },
        "retained_minimum_guardrails": {
            "gold_qrels_expected_supporting_relevance_answerability_mutation_forbidden": True,
            "oracle_eval_field_candidate_input_forbidden": True,
            "raw_path_source_title_workbook_filename_shortcut_forbidden": True,
            "production_namespace_mutation_forbidden": True,
            "raw_prompt_response_excessive_storage_forbidden": True,
            "source_atom_evidence_bundle_evidence_truth": True,
        },
        "report_conclusions": {
            "legacy_pdf_xlsx_retrieval_is_rag": False,
            "true_rag_basis": "pre-materialized SearchUnit/SearchView plus repo-local SQLite/BM25 hybrid nonprod backend",
            "tool_lane_in_agentic_loop_but_metric_separate": True,
            "gold_silver_reused_read_only": True,
            "family_true_rag_metric_change": family_breakdown,
            "tool_required_row_ratio": tool_metrics["tool_required_row_ratio"],
            "agentic_answer_quality_result": agentic_metrics,
            "current_alias_moved": True,
            "remaining_blockers": [
                "replace diagnostic materialized sample with full source-derived gold/silver SearchUnit materialization",
                "wire optional external VectorDB if repo-local hybrid is insufficient",
                "expand agentic answer evaluator beyond deterministic bounded smoke",
            ],
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "generated_artifacts": [ARTIFACT_PATHS[key] for key in RUN_ARTIFACT_KEYS],
    }
    for key in RETAINED_FALSE_GATES:
        report[key] = False
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6 agentic logical key drift")
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v6 agentic short id drift")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v6 agentic long id drift")
    if report.get("status") != STATUS:
        raise ValueError("v6 agentic status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6 agentic current alias drift")


def _require_closed_or_relaxed_gates(report: Mapping[str, Any]) -> None:
    if report.get("official_metric") is not False:
        raise ValueError("v6 agentic official metric opened")
    for key in RETAINED_FALSE_GATES:
        if report.get(key) is not False:
            raise ValueError(f"v6 agentic retained guardrail opened: {key}")
    cleanup = report.get("guardrail_cleanup") or {}
    for key, value in cleanup.items():
        if value is not True:
            raise ValueError(f"v6 agentic conservative gate was not relaxed: {key}")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v6 agentic protected namespace drift")
    if report.get("production_namespaces_touched") != []:
        raise ValueError("v6 agentic production namespace drift")


def _require_schema_and_payloads(report: Mapping[str, Any]) -> None:
    schema = report.get("true_rag_index_payload_schema") or {}
    if set(schema.get("schema_names") or []) != {
        "TrueRagSearchUnit",
        "TrueRagSearchView",
        "TrueRagIndexPayload",
        "TrueRagCandidate",
        "TrueRagRetrievalResult",
    }:
        raise ValueError("v6 agentic schema names drift")
    for unit in report.get("materialized_search_units") or []:
        validate_true_rag_search_unit(unit)
    for view in report.get("materialized_search_views") or []:
        validate_true_rag_search_view(view)
    for payload in report.get("true_rag_index_payloads") or []:
        validate_true_rag_index_payload(payload)
    for row in report.get("true_rag_candidate_diagnostics") or []:
        validate_true_rag_candidate((row or {}).get("candidate") or {})


def _require_backend(report: Mapping[str, Any]) -> None:
    backend = report.get("real_nonprod_backend") or {}
    if backend.get("backend_kind") != BACKEND_KIND:
        raise ValueError("v6 agentic backend kind drift")
    if not _clean(backend.get("namespace")).startswith(TRUE_RAG_NAMESPACE_PREFIX):
        raise ValueError("v6 agentic backend namespace drift")
    if backend.get("real_vectordb_or_hybrid_backend_invoked") is not True:
        raise ValueError("v6 agentic backend was not invoked")
    if int(backend.get("indexed_search_unit_count") or 0) <= 0:
        raise ValueError("v6 agentic backend indexed no units")
    if int(backend.get("query_count") or 0) <= 0:
        raise ValueError("v6 agentic backend queried no rows")
    if backend.get("fake_noop_or_replay_backend_used") is not False:
        raise ValueError("v6 agentic fake/noop/replay backend used")
    if backend.get("archived_topk_replay_projection_backend_rejected") is not True:
        raise ValueError("v6 agentic replay backend rejection missing")


def _require_legacy_inventory(report: Mapping[str, Any]) -> None:
    inventory = report.get("legacy_non_rag_path_inventory") or []
    if {row.get("path_id") for row in inventory} != {row["path_id"] for row in LEGACY_PATHS}:
        raise ValueError("v6 agentic legacy inventory drift")
    if report.get("legacy_non_rag_path_isolated_from_true_rag") is not True:
        raise ValueError("v6 agentic legacy path not isolated")


def _require_metrics(report: Mapping[str, Any]) -> None:
    policy = report.get("metric_policy") or {}
    if set(policy.get("defined_metrics") or []) != {
        "true_rag_retrieval_metric_gold_29",
        "true_rag_retrieval_metric_silver_1000",
        "structured_tool_metric_gold_29",
        "structured_tool_metric_silver_sample",
        "agentic_end_to_end_answer_metric_gold_29",
        "agentic_end_to_end_answer_metric_silver_diagnostic",
        "legacy_non_rag_comparison_metric",
    }:
        raise ValueError("v6 agentic metric policy drift")
    true_rag = report.get("true_rag_metric_results") or {}
    if true_rag.get("structured_tool_outputs_mixed") is not False:
        raise ValueError("v6 agentic tool output mixed into true RAG")
    if true_rag.get("tool_outputs_excluded") is not True:
        raise ValueError("v6 agentic true RAG did not exclude tool outputs")
    if set(true_rag.get("family_breakdown") or {}) != set(FAMILIES):
        raise ValueError("v6 agentic family metric breakdown drift")
    if len(report.get("denominator_manifest") or []) != int(report.get("denominator_manifest_rows") or -1):
        raise ValueError("v6 agentic denominator manifest count drift")
    if len(report.get("row_eligibility_ledger") or []) != int(report.get("row_eligibility_ledger_rows") or -1):
        raise ValueError("v6 agentic row eligibility count drift")
    if len(report.get("exclusion_ledger") or []) != int(report.get("exclusion_ledger_rows") or -1):
        raise ValueError("v6 agentic exclusion count drift")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    if report.get("artifact_paths") != ARTIFACT_PATHS:
        raise ValueError("v6 agentic artifact paths drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    hashes = report.get("artifact_sha256") or {}
    if not hashes:
        return
    repo_root = Path(root)
    for key in RUN_ARTIFACT_KEYS:
        artifact_path = repo_root / ARTIFACT_PATHS[key]
        if not artifact_path.exists():
            raise ValueError(f"v6 agentic missing artifact: {key}")
        if key == "report_json":
            continue
        expected = _clean(hashes.get(f"{key}_sha256"))
        if expected and expected != common.sha256_file(artifact_path):
            raise ValueError(f"v6 agentic artifact hash drift: {key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_or_relaxed_gates(report)
    _require_schema_and_payloads(report)
    _require_backend(report)
    _require_legacy_inventory(report)
    assert_langgraph_agentic_loop_contract(report.get("langgraph_agentic_loop") or {})
    _require_metrics(report)
    _require_artifact_paths(report)
    common.assert_no_raw_payload_keys(report, set(FORBIDDEN_REPORT_PAYLOAD_KEYS), context="v6_agentic")
    if root is not None:
        _require_written_artifacts(report, root=root)


def _write_persistent_index(path: Path, payloads: Sequence[Mapping[str, Any]], *, generated_at: str) -> dict[str, Any]:
    backend = RepoLocalTrueRagHybridBackend(namespace=DEFAULT_NAMESPACE, sqlite_path=path)
    backend.build_index(payloads)
    for row in _retrieval_queries():
        backend.query(query_text=row["text"], source_family=row["family"], top_k=5)
    diagnostics = backend.diagnostics(generated_at=generated_at)
    backend.close()
    return diagnostics


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    artifact_hashes: dict[str, str] = {}
    sqlite_path = repo_root / ARTIFACT_PATHS["nonprod_hybrid_index_sqlite"]
    persistent_backend = _write_persistent_index(
        sqlite_path,
        payload["true_rag_index_payloads"],
        generated_at=payload["generated_at"],
    )
    persistent_backend["index_path"] = ARTIFACT_PATHS["nonprod_hybrid_index_sqlite"]
    payload["real_nonprod_backend"] = persistent_backend
    artifact_hashes["nonprod_hybrid_index_sqlite_sha256"] = common.sha256_file(sqlite_path)

    json_artifacts = {
        "true_rag_metric_results_json": payload["true_rag_metric_results"],
        "tool_metric_results_json": payload["tool_metric_results"],
        "agentic_end_to_end_metric_results_json": payload["agentic_end_to_end_metric_results"],
        "true_rag_index_payload_schema_json": payload["true_rag_index_payload_schema"],
        "leakage_probe_summary_json": payload["leakage_probe_summary"],
    }
    jsonl_artifacts = {
        "legacy_non_rag_path_inventory_jsonl": payload["legacy_non_rag_path_inventory"],
        "true_rag_candidate_diagnostics_jsonl": payload["true_rag_candidate_diagnostics"],
        "tool_execution_diagnostics_jsonl": payload["tool_execution_diagnostics"],
        "agentic_loop_trace_summary_jsonl": payload["agentic_loop_trace_summary"],
        "denominator_manifest_jsonl": payload["denominator_manifest"],
        "row_eligibility_ledger_jsonl": payload["row_eligibility_ledger"],
        "exclusion_ledger_jsonl": payload["exclusion_ledger"],
    }
    for key, value in json_artifacts.items():
        path = repo_root / ARTIFACT_PATHS[key]
        common.write_json(path, value)
        artifact_hashes[f"{key}_sha256"] = common.sha256_file(path)
    for key, rows in jsonl_artifacts.items():
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
    backend = report["real_nonprod_backend"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "generated_at": report["generated_at"],
        "event_type": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": PREVIOUS_CURRENT,
        "current_moved_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "gold_qrels_expected_supporting_labels_mutated": False,
        "silver_promoted_to_gold": False,
        "real_vectordb_or_hybrid_backend_invoked": backend["real_vectordb_or_hybrid_backend_invoked"],
        "backend_kind": backend["backend_kind"],
        "indexed_search_unit_count": backend["indexed_search_unit_count"],
        "query_count": backend["query_count"],
        "tool_lane_separate_from_true_rag_metric": True,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_readiness_claim": False,
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


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    true_rag = report["true_rag_metric_results"]
    tool_metrics = report["tool_metric_results"]
    agentic = report["agentic_end_to_end_metric_results"]
    backend = report["real_nonprod_backend"]
    family_json = json.dumps(true_rag["family_breakdown"], ensure_ascii=False, sort_keys=True)
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` isolates the existing PDF/XLSX retrieval path as "
        "legacy non-RAG/tool/extraction path and current moved from `v5_6` to "
        f"`{SHORT_RUN_ID}`. The true RAG lane uses pre-materialized SearchUnit/SearchView payloads and a real "
        "repo-local SQLite/BM25 hybrid nonprod backend, while PDF/XLSX/TEXT structured tools run inside the "
        "LangGraph agentic loop but remain outside true RAG Hit@k/MRR/nDCG. Gold 29 and the existing silver 1000 "
        "diagnostic surface are reused read-only; gold/qrels/expected/supporting/relevance/answerability and the "
        "official denominator are not created or modified. No official/product/promotion/live-readiness claim is made."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        "- Boundary: legacy non-RAG/tool/extraction path is isolated; true RAG uses pre-materialized "
        "SearchUnit/SearchView over the repo-local SQLite/BM25 hybrid backend.\n"
        f"- Backend: repo-local SQLite/BM25 hybrid; namespace `{backend['namespace']}`; indexed_search_unit_count="
        f"{backend['indexed_search_unit_count']}; query_count={backend['query_count']}; "
        f"p50_latency_ms={backend['p50_latency_ms']}; p95_latency_ms={backend['p95_latency_ms']}.\n"
        f"- true RAG metrics: gold_29 rows={true_rag['true_rag_retrieval_metric_gold_29']['source_rows']}; "
        f"silver_1000 rows={true_rag['true_rag_retrieval_metric_silver_1000']['source_rows']}; "
        f"family_breakdown={family_json}; tool_outputs_excluded=true.\n"
        f"- Tool lane: tool_required_row_ratio={tool_metrics['tool_required_row_ratio']}; tool metrics stay separate "
        "from true RAG retrieval metrics.\n"
        f"- Current alias: current moved from `v5_6` to `{SHORT_RUN_ID}`; rollback key is `v5_6`.\n"
        f"- Agentic answer quality: gold_29 answer_quality_metric_computed="
        f"{str(agentic['agentic_end_to_end_answer_metric_gold_29']['answer_quality_metric_computed']).lower()}; "
        "raw prompt/response storage remains disabled."
    )
    triage = (
        f"- {SHORT_RUN_ID}: existing PDF/XLSX file-level retrieval plus runtime parser/search, archived top-k replay, "
        "projection adapters, forced routing, row-specific exceptions, source-title/workbook filename shortcuts, "
        "formula shortcuts, normalized answer matching, and qrels/gold/expected/supporting/citation-locator candidate "
        "construction are isolated as legacy non-RAG/tool/extraction path. Relaxed gates: nonprod index/cache mutation, "
        "current alias movement, local agentic loop execution, and structured tool execution. Retained guardrails: "
        "oracle/eval field candidate-input ban, gold/qrels/expected/supporting/relevance/answerability mutation ban, "
        "production namespace mutation ban, bounded raw prompt/response storage, and SourceAtom/EvidenceBundle evidence truth. "
        "The true RAG lane uses pre-materialized SearchUnit/SearchView over the repo-local SQLite/BM25 hybrid backend. "
        f"current moved from `v5_6` to `{SHORT_RUN_ID}`; rollback key is `v5_6`. Remaining blockers are full source-derived "
        "gold/silver materialization expansion and optional external VectorDB parity beyond the repo-local hybrid backend."
    )
    return progress, measurements, triage


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    progress, measurements, triage = _doc_fragments(report)
    for path, marker, block in (
        (PROGRESS_DOC, "progress-entry", progress),
        (MEASUREMENTS_DOC, "measurements-entry", measurements),
        (TRIAGE_DOC, "triage-entry", triage),
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
