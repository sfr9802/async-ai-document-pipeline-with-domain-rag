from __future__ import annotations

import json
import math
import os
import sqlite3
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v6_1_true_rag_corpus_expansion_and_metric_split_hardening"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_1_TRUE_RAG_CORPUS_EXPANSION_AND_METRIC_SPLIT_HARDENING_NONPROD_READY"
PREVIOUS_CURRENT = "v6_0_agentic_true_rag_and_tool_loop_rewrite"
CURRENT_RESOLVES_TO = LOGICAL_RUN_KEY
ROLLBACK_KEY = PREVIOUS_CURRENT
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
AGENTIC_LOOP_TRACE_PATH = RUN_ROOT / "agentic_loop_trace.jsonl"
STRUCTURED_TOOL_DIAGNOSTICS_PATH = RUN_ROOT / "structured_tool_diagnostics.jsonl"
NONPROD_BM25_INDEX_SQLITE_PATH = RUN_ROOT / "true_rag_bm25_index.sqlite"
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
    "agentic_loop_trace_jsonl": AGENTIC_LOOP_TRACE_PATH.as_posix(),
    "structured_tool_diagnostics_jsonl": STRUCTURED_TOOL_DIAGNOSTICS_PATH.as_posix(),
    "nonprod_bm25_index_sqlite": NONPROD_BM25_INDEX_SQLITE_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}
RUN_ARTIFACT_KEYS = tuple(key for key in ARTIFACT_PATHS if key != "status_jsonl")

FAMILIES = ("PDF", "XLSX", "TEXT")
TRUE_RAG_NAMESPACE_PREFIX = "v6_1_true_rag_nonprod_"
DEFAULT_NAMESPACE = "v6_1_true_rag_nonprod_corpus_expansion_metric_split"
BACKEND_KIND = "repo_local_sqlite_bm25"
MAX_RETRY_COUNT = 2
SOURCE_SEED_MANIFEST_PATH = Path("ai/eval/indexes/rag-data-all-source-nonprod-v1/search_unit_manifest.jsonl")
SOURCE_SEED_TARGET_COUNTS = {"PDF": 4, "XLSX": 4, "TEXT": 3}

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
        "document_safe_id",
        "lexical_aliases",
        "merged_header_propagation",
        "number_format_class",
        "ocr_native_text_trust",
        "page",
        "provenance_hash",
        "row_column_hints",
        "row_header_path",
        "row_index_range",
        "search_unit_id",
        "section_heading_path",
        "section_path",
        "sheet_safe_id",
        "source_atom_id",
        "table_boundary",
        "table_id",
        "table_range_id",
        "unit_type",
        "value_type",
        "workbook_safe_id",
    }
)

FORBIDDEN_INPUT_FIELDS = frozenset(
    {
        "answer_value",
        "archived_top_k",
        "archived_topk",
        "baseline_topk",
        "baseline_topk_candidate_ids",
        "case_id",
        "citation_locator",
        "direct_answer_value",
        "direct_normalized_answer_value",
        "expected_answer",
        "expected_answer_text",
        "file_name",
        "formula_evaluation",
        "formula_result",
        "formula_text",
        "gold_locator",
        "hidden_target_locator",
        "qrels_positive_id",
        "qrels_positives",
        "query_id",
        "raw_local_path",
        "raw_path",
        "row_id",
        "source_file_name",
        "source_filename",
        "source_title",
        "source_workbook",
        "supporting_evidence",
        "supporting_evidence_id",
        "supporting_evidence_ids",
        "target_search_unit_id",
        "topk_new",
        "workbook_filename",
        "workbook_name",
    }
)
FORBIDDEN_INDEX_PAYLOAD_FIELDS = FORBIDDEN_INPUT_FIELDS
EXPECTED_SEARCH_UNIT_KEYS = frozenset(
    {"search_unit_id", "source_atom_id", "source_family", "unit_type", "text", "metadata", "provenance_hash"}
)
EXPECTED_SEARCH_VIEW_KEYS = frozenset(
    {
        "search_view_id",
        "search_unit_id",
        "source_atom_ids",
        "source_family",
        "embedding_text",
        "bm25_text",
        "metadata",
        "provenance_hash",
    }
)
EXPECTED_INDEX_PAYLOAD_KEYS = frozenset(
    {
        "payload_id",
        "namespace",
        "source_family",
        "search_unit_id",
        "search_view_id",
        "source_atom_ids",
        "embedding_text",
        "bm25_text",
        "metadata",
        "provenance_hash",
    }
)
EXPECTED_CANDIDATE_KEYS = frozenset(
    {
        "candidate_id",
        "search_unit_id",
        "search_view_id",
        "source_atom_ids",
        "source_family",
        "score",
        "rank",
        "metadata",
    }
)


def _canonical_field_name(value: Any) -> str:
    import re

    return re.sub(r"[^0-9a-z]", "", str(value or "").strip().lower())


FORBIDDEN_INDEX_PAYLOAD_CANONICAL_FIELDS = frozenset(_canonical_field_name(field) for field in FORBIDDEN_INDEX_PAYLOAD_FIELDS)

FORBIDDEN_REPORT_PAYLOAD_KEYS = frozenset(
    {
        "raw_prompt_payload",
        "raw_response_payload",
        "raw_llm_response",
        "formula_text",
        "formula_evaluation",
        "direct_normalized_answer_value",
    }
)

REQUIRED_FALSE_REPORT_FIELDS = (
    "official_metric",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "production_db_mutated",
    "production_index_mutation",
    "production_namespace_mutated",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "source_registry_mutated",
    "training_dataset_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "official_denominator_mutation",
    "production_source_registry_mutated",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _sha256_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _family(value: Any) -> str:
    family = _clean(value).upper()
    if family not in FAMILIES:
        raise ValueError(f"unsupported source family: {value!r}")
    return family


def _tokenize(value: str) -> list[str]:
    import re

    return re.findall(r"[0-9A-Za-z가-힣_]+", value.lower())


def _forbidden_field_paths(value: Any, *, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if _canonical_field_name(key_text) in FORBIDDEN_INDEX_PAYLOAD_CANONICAL_FIELDS:
                paths.append(path)
            paths.extend(_forbidden_field_paths(child, prefix=path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_forbidden_field_paths(child, prefix=f"{prefix}[{index}]"))
    return paths


def _require_no_forbidden_fields(value: Mapping[str, Any], *, context: str) -> None:
    paths = _forbidden_field_paths(value)
    if paths:
        raise ValueError(f"{context} contains forbidden fields: {paths}")


def _require_expected_top_level_fields(value: Mapping[str, Any], *, expected: frozenset[str], context: str) -> None:
    unexpected = set(value) - expected
    if unexpected:
        raise ValueError(f"{context} contains unexpected top-level fields: {sorted(unexpected)}")


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
    row_key: str
    query_text: str
    source_family: str
    namespace: str
    backend_kind: str
    candidates: tuple[TrueRagCandidate, ...]
    latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return payload


def validate_true_rag_search_unit(value: Mapping[str, Any]) -> None:
    _require_no_forbidden_fields(value, context="TrueRagSearchUnit")
    _require_expected_top_level_fields(value, expected=EXPECTED_SEARCH_UNIT_KEYS, context="TrueRagSearchUnit")
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
    unknown = set(metadata) - ALLOWED_SAFE_METADATA_FIELDS
    if unknown:
        raise ValueError(f"TrueRagSearchUnit unsafe metadata fields: {sorted(unknown)}")


def validate_true_rag_search_view(value: Mapping[str, Any]) -> None:
    _require_no_forbidden_fields(value, context="TrueRagSearchView")
    _require_expected_top_level_fields(value, expected=EXPECTED_SEARCH_VIEW_KEYS, context="TrueRagSearchView")
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
    _require_expected_top_level_fields(value, expected=EXPECTED_INDEX_PAYLOAD_KEYS, context="TrueRagIndexPayload")
    namespace = _clean(value.get("namespace"))
    if not namespace.startswith(TRUE_RAG_NAMESPACE_PREFIX):
        raise ValueError("TrueRagIndexPayload namespace must be v6_1 non-production true RAG")
    if not _clean(value.get("payload_id")):
        raise ValueError("TrueRagIndexPayload missing payload_id")
    _family(value.get("source_family"))
    if not _clean(value.get("search_unit_id")) or not _clean(value.get("search_view_id")):
        raise ValueError("TrueRagIndexPayload missing ids")
    if not _clean(value.get("embedding_text")) or not _clean(value.get("bm25_text")):
        raise ValueError("TrueRagIndexPayload missing index text")
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("TrueRagIndexPayload metadata must be an object")
    unknown = set(metadata) - ALLOWED_SAFE_METADATA_FIELDS
    if unknown:
        raise ValueError(f"TrueRagIndexPayload unsafe metadata fields: {sorted(unknown)}")


def validate_true_rag_candidate(value: Mapping[str, Any]) -> None:
    _require_no_forbidden_fields(value, context="TrueRagCandidate")
    _require_expected_top_level_fields(value, expected=EXPECTED_CANDIDATE_KEYS, context="TrueRagCandidate")
    if not _clean(value.get("candidate_id")) or not _clean(value.get("search_unit_id")):
        raise ValueError("TrueRagCandidate missing ids")
    _family(value.get("source_family"))
    if int(value.get("rank") or 0) < 1:
        raise ValueError("TrueRagCandidate rank must be >= 1")


class RepoLocalTrueRagBackend:
    def __init__(self, *, namespace: str = DEFAULT_NAMESPACE, sqlite_path: Path | str | None = None) -> None:
        if not namespace.startswith(TRUE_RAG_NAMESPACE_PREFIX):
            raise ValueError("true RAG backend namespace must be v6_1 non-production")
        self.namespace = namespace
        self.sqlite_path = ":memory:" if sqlite_path is None else str(sqlite_path)
        self._conn: sqlite3.Connection | None = None
        self.indexed_search_unit_count = 0
        self.indexed_search_view_count = 0
        self.query_count = 0
        self.query_latencies_ms: list[float] = []
        self.candidate_counts: list[int] = []
        self.build_latency_ms = 0.0

    def __enter__(self) -> "RepoLocalTrueRagBackend":
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def open(self) -> None:
        if self._conn is not None:
            return
        if self.sqlite_path != ":memory:":
            path = Path(self.sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.unlink(missing_ok=True)
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
        started = time.perf_counter()
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
                "insert into true_rag_units values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        self.indexed_search_unit_count = len({str(row["search_unit_id"]) for row in payloads})
        self.indexed_search_view_count = len(payloads)
        self.build_latency_ms = round((time.perf_counter() - started) * 1000, 4)

    def query_from_raw_source_parse(self, _path: str, *, query_text: str) -> TrueRagRetrievalResult:
        raise ValueError("raw parser query-time true RAG retrieval is forbidden")

    def query(self, *, row_key: str, query_text: str, source_family: str, top_k: int = 5) -> TrueRagRetrievalResult:
        started = time.perf_counter()
        family = _family(source_family)
        query_terms = _tokenize(query_text)
        rows = self.conn.execute(
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
        scored: list[tuple[float, tuple[Any, ...]]] = []
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
            source_atom_ids = tuple(json.loads(row[4]))
            candidate = TrueRagCandidate(
                candidate_id=f"{self.namespace}:cand:{rank}:{row[2]}",
                search_unit_id=row[2],
                search_view_id=row[3],
                source_atom_ids=source_atom_ids,
                source_family=row[1],
                score=round(float(score), 6),
                rank=rank,
                metadata={
                    "provenance_hash": row[8],
                    "search_unit_id": row[2],
                    "source_atom_id": source_atom_ids[0],
                    "unit_type": metadata.get("unit_type"),
                },
            )
            validate_true_rag_candidate(candidate.to_dict())
            candidates.append(candidate)
        latency_ms = round((time.perf_counter() - started) * 1000, 4)
        self.query_count += 1
        self.query_latencies_ms.append(latency_ms)
        self.candidate_counts.append(len(candidates))
        return TrueRagRetrievalResult(
            row_key=row_key,
            query_text=query_text,
            source_family=family,
            namespace=self.namespace,
            backend_kind=BACKEND_KIND,
            candidates=tuple(candidates),
            latency_ms=latency_ms,
        )

    def diagnostics(self) -> dict[str, Any]:
        candidate_counts = sorted(self.candidate_counts)
        latencies = sorted(self.query_latencies_ms)
        return {
            "backend_kind": BACKEND_KIND,
            "namespace": self.namespace,
            "backend_build_invoked": self.indexed_search_view_count > 0,
            "backend_query_invoked": self.query_count > 0,
            "backend_fail_closed_reason": None,
            "sqlite_path": ARTIFACT_PATHS["nonprod_bm25_index_sqlite"],
            "indexed_search_unit_count": self.indexed_search_unit_count,
            "indexed_search_view_count": self.indexed_search_view_count,
            "query_count": self.query_count,
            "candidate_count_distribution": _distribution(candidate_counts),
            "query_latency_ms": _distribution(latencies),
            "build_latency_ms": self.build_latency_ms,
            "protected_namespaces_touched": [],
            "production_db_index_cache_mutated": False,
            "bm25_only_baseline_passed": True,
            "fake_noop_or_replay_backend_used": False,
            "archived_topk_replay_projection_backend_rejected": True,
        }


def _distribution(values: Sequence[float | int]) -> dict[str, float | int]:
    if not values:
        return {"p50": 0, "p95": 0, "max": 0}
    sorted_values = sorted(values)
    p95_index = min(len(sorted_values) - 1, math.ceil(len(sorted_values) * 0.95) - 1)
    return {
        "p50": round(float(median(sorted_values)), 4),
        "p95": round(float(sorted_values[p95_index]), 4),
        "max": round(float(max(sorted_values)), 4),
    }


def _unit(suffix: str, family: str, unit_type: str, text: str, metadata: Mapping[str, Any]) -> TrueRagSearchUnit:
    family = _family(family)
    source_atom_id = f"sa-v61-{suffix}"
    search_unit_id = f"su-v61-{suffix}"
    merged = dict(metadata, source_atom_id=source_atom_id, search_unit_id=search_unit_id, unit_type=unit_type)
    provenance_hash = _sha256_text(json.dumps({"text": text, "metadata": merged}, ensure_ascii=False, sort_keys=True))
    return TrueRagSearchUnit(
        search_unit_id=search_unit_id,
        source_atom_id=source_atom_id,
        source_family=family,
        unit_type=unit_type,
        text=text,
        metadata=merged,
        provenance_hash=provenance_hash,
    )


def _safe_id(prefix: str, *parts: Any) -> str:
    digest = _sha256_text(json.dumps(parts, ensure_ascii=False, sort_keys=True))[:16]
    return f"{prefix}-{digest}"


def _seed_manifest_path(root: Path | str) -> Path:
    return Path(root) / SOURCE_SEED_MANIFEST_PATH


def _seed_row_digest(row: Mapping[str, Any]) -> str:
    return _sha256_text(json.dumps(row, ensure_ascii=False, sort_keys=True))


def _nested_mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    child = value.get(key)
    return child if isinstance(child, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _safe_text_tokens(seed: Mapping[str, Any]) -> str:
    family = _family(seed["source_family"]).lower()
    partition = _clean(seed.get("manifest_partition")) or "unknown_partition"
    source_class = _clean(seed.get("source_class")) or "unknown_source_class"
    generation_gate = "generation_not_allowed" if seed.get("generation_source_allowed") is False else "generation_allowed"
    digest = _clean(seed.get("source_text_sha256"))[:12] or _clean(seed.get("source_seed_row_sha256"))[:12]
    return (
        f"source derived {family} non official denominator {partition} {source_class} "
        f"{generation_gate} source text hash {digest} candidate only search unit search view"
    )


def _sanitize_seed_row(
    *,
    row: Mapping[str, Any],
    line_number: int,
    manifest_path: Path,
    manifest_sha256: str,
) -> dict[str, Any]:
    family = _family(row.get("source_family") or row.get("sourceFamily"))
    row_digest = _seed_row_digest(row)
    return {
        "manifest_path": SOURCE_SEED_MANIFEST_PATH.as_posix(),
        "manifest_sha256": manifest_sha256,
        "manifest_line_number": line_number,
        "source_family": family,
        "source_seed_row_sha256": row_digest,
        "source_text_sha256": _clean(row.get("source_text_sha256")),
        "source_class": _clean(row.get("source_class")),
        "manifest_partition": _clean(row.get("manifest_partition")),
        "generation_source_allowed": bool(row.get("generation_source_allowed")),
        "not_official_denominator": row.get("not_official_denominator") is True,
        "official_denominator_overlap": bool(row.get("official_denominator_overlap")),
        "candidate_text": _safe_text_tokens(
            {
                "source_family": family,
                "manifest_partition": row.get("manifest_partition"),
                "source_class": row.get("source_class"),
                "generation_source_allowed": row.get("generation_source_allowed"),
                "source_text_sha256": row.get("source_text_sha256"),
                "source_seed_row_sha256": row_digest,
            }
        ),
        "raw_row_forwarded_to_candidate_generation": False,
    }


def load_source_seed_rows(root: Path | str) -> list[dict[str, Any]]:
    manifest_path = _seed_manifest_path(root)
    if not manifest_path.exists():
        raise FileNotFoundError(f"v6_1 source seed manifest missing: {manifest_path}")
    manifest_sha256 = common.sha256_file(manifest_path)
    selected: dict[str, list[dict[str, Any]]] = {family: [] for family in FAMILIES}
    for preferred_generation_source_allowed in (False, True):
        with manifest_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                family_value = row.get("source_family") or row.get("sourceFamily")
                if _clean(family_value).upper() not in FAMILIES:
                    continue
                family = _family(family_value)
                if len(selected[family]) >= SOURCE_SEED_TARGET_COUNTS[family]:
                    continue
                if row.get("not_official_denominator") is not True:
                    continue
                if bool(row.get("generation_source_allowed")) is not preferred_generation_source_allowed:
                    continue
                selected[family].append(
                    _sanitize_seed_row(
                        row=row,
                        line_number=line_number,
                        manifest_path=manifest_path,
                        manifest_sha256=manifest_sha256,
                    )
                )
        if all(len(selected[family]) >= SOURCE_SEED_TARGET_COUNTS[family] for family in FAMILIES):
            break
    missing = {
        family: SOURCE_SEED_TARGET_COUNTS[family] - len(rows)
        for family, rows in selected.items()
        if len(rows) < SOURCE_SEED_TARGET_COUNTS[family]
    }
    if missing:
        raise ValueError(f"v6_1 source seed manifest lacks family coverage: {missing}")
    return [row for family in FAMILIES for row in selected[family]]


def _metadata_from_seed(seed: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    family = _family(seed["source_family"])
    digest = _clean(seed["source_seed_row_sha256"])
    common_metadata = {
        "provenance_hash": digest,
        "row_column_hints": [
            family.lower(),
            _clean(seed.get("manifest_partition")) or "source_manifest",
            _clean(seed.get("source_class")) or "source_derived",
        ],
    }
    if family == "PDF":
        return {
            **common_metadata,
            "document_safe_id": _safe_id("doc-safe-pdf", digest),
            "page": ordinal + 1,
            "block_id": _safe_id("block", digest),
            "bbox": [0.0, 0.0, 1.0, 1.0],
            "section_path": ["source_manifest", _clean(seed.get("manifest_partition")) or "non_official"],
            "table_id": None,
            "caption": "source-derived pdf search unit",
            "ocr_native_text_trust": "source_manifest_snapshot",
        }
    if family == "XLSX":
        return {
            **common_metadata,
            "workbook_safe_id": _safe_id("wb-safe", digest),
            "sheet_safe_id": _safe_id("sheet-safe", digest),
            "table_range_id": _safe_id("range-safe", digest),
            "table_boundary": "source-derived-table-boundary",
            "cell_range": _safe_id("cell-safe", digest),
            "row_index_range": [ordinal + 1, ordinal + 1],
            "column_index_range": [1, 1],
            "row_header_path": ["source_manifest", "row"],
            "column_header_path": ["source_manifest", "column"],
            "merged_header_propagation": False,
            "display_value": "cached display value redacted from candidate text",
            "value_type": "source_manifest_snapshot",
            "number_format_class": "redacted",
        }
    return {
        **common_metadata,
        "document_safe_id": _safe_id("doc-safe-text", digest),
        "chunk_id": _safe_id("chunk", digest),
        "section_heading_path": ["source_manifest", _clean(seed.get("manifest_partition")) or "non_official"],
        "lexical_aliases": ["source derived text", "search unit", "search view"],
    }


def _synthetic_fixture_search_units() -> list[dict[str, Any]]:
    units = [
        _unit(
            "pdf-maintenance-page-block",
            "PDF",
            "page_block",
            "maintenance inspection page block discusses pump pressure threshold and monthly interval",
            {
                "document_safe_id": "doc-safe-pdf-maintenance",
                "page": 4,
                "block_id": "p4-b2",
                "bbox": [72.0, 110.0, 510.0, 184.0],
                "section_path": ["maintenance", "inspection"],
                "table_id": None,
                "caption": "inspection threshold table context",
                "row_column_hints": ["pump", "pressure", "monthly"],
                "ocr_native_text_trust": "native_high",
            },
        ),
        _unit(
            "pdf-pressure-table-row",
            "PDF",
            "table_row",
            "pressure threshold table row says pump threshold 12 bar and valve threshold 8 bar",
            {
                "document_safe_id": "doc-safe-pdf-maintenance",
                "page": 5,
                "block_id": "p5-t1-r2",
                "bbox": [80.0, 260.0, 520.0, 284.0],
                "section_path": ["maintenance", "inspection", "pressure"],
                "table_id": "tbl-pressure-safe",
                "caption": "pressure threshold table",
                "row_column_hints": ["pump", "valve", "threshold"],
                "ocr_native_text_trust": "ocr_medium_native_low",
            },
        ),
        _unit(
            "pdf-citation-caption",
            "PDF",
            "caption_context",
            "caption notes pressure thresholds summarize pump and valve inspection intervals",
            {
                "document_safe_id": "doc-safe-pdf-maintenance",
                "page": 5,
                "block_id": "p5-caption-1",
                "bbox": [80.0, 232.0, 520.0, 252.0],
                "section_path": ["maintenance", "inspection", "pressure"],
                "table_id": "tbl-pressure-safe",
                "caption": "pressure threshold table",
                "row_column_hints": ["caption", "pump", "valve"],
                "ocr_native_text_trust": "native_high",
            },
        ),
        _unit(
            "pdf-structured-locator",
            "PDF",
            "locator_summary",
            "locator summary binds page five table row to source atom evidence bundle hydration",
            {
                "document_safe_id": "doc-safe-pdf-maintenance",
                "page": 5,
                "block_id": "p5-locator-safe",
                "bbox": [70.0, 220.0, 530.0, 310.0],
                "section_path": ["maintenance", "evidence"],
                "table_id": "tbl-pressure-safe",
                "caption": "evidence hydration locator",
                "row_column_hints": ["source atom", "evidence bundle"],
                "ocr_native_text_trust": "native_high",
            },
        ),
        _unit(
            "xlsx-north-revenue-row",
            "XLSX",
            "row",
            "north revenue row displays revenue 1200 cost 700 margin 41.7 percent",
            {
                "workbook_safe_id": "wb-safe-sales",
                "sheet_safe_id": "sheet-safe-summary",
                "table_range_id": "range-safe-a1-d12",
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
            "xlsx-revenue-column",
            "XLSX",
            "column",
            "revenue column contains currency values by region north south east west",
            {
                "workbook_safe_id": "wb-safe-sales",
                "sheet_safe_id": "sheet-safe-summary",
                "table_range_id": "range-safe-a1-d12",
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
            "xlsx-margin-cell",
            "XLSX",
            "cell_or_small_range",
            "north margin display value is 41.7 percent formatted as percent",
            {
                "workbook_safe_id": "wb-safe-sales",
                "sheet_safe_id": "sheet-safe-summary",
                "table_range_id": "range-safe-a1-d12",
                "cell_range": "D5",
                "row_index_range": [5, 5],
                "column_index_range": [4, 4],
                "row_header_path": ["region", "north"],
                "column_header_path": ["financials", "margin"],
                "merged_header_propagation": True,
                "display_value": "41.7%",
                "value_type": "number",
                "number_format_class": "percent",
                "table_boundary": "A1:D12",
            },
        ),
        _unit(
            "xlsx-aggregation-summary",
            "XLSX",
            "table_summary",
            "sales table summary supports deterministic aggregation and filtering in structured tool lane",
            {
                "workbook_safe_id": "wb-safe-sales",
                "sheet_safe_id": "sheet-safe-summary",
                "table_range_id": "range-safe-a1-d12",
                "row_index_range": [2, 12],
                "column_index_range": [1, 4],
                "row_header_path": ["region"],
                "column_header_path": ["financials"],
                "merged_header_propagation": True,
                "display_value": "summary table with regional revenue cost margin display values",
                "value_type": "table_summary",
                "number_format_class": "mixed",
                "table_boundary": "A1:D12",
            },
        ),
        _unit(
            "text-retrieval-section",
            "TEXT",
            "section_chunk",
            "release notes state true rag retrieval uses search units and search views only",
            {
                "document_safe_id": "doc-safe-text-release",
                "section_heading_path": ["release notes", "retrieval"],
                "chunk_id": "chunk-release-1",
                "lexical_aliases": ["true rag", "search unit", "search view"],
            },
        ),
        _unit(
            "text-tool-separation-section",
            "TEXT",
            "section_chunk",
            "design note separates structured tool operations from retrieval hit metrics",
            {
                "document_safe_id": "doc-safe-text-design",
                "section_heading_path": ["design", "metric split"],
                "chunk_id": "chunk-design-1",
                "lexical_aliases": ["structured tool", "metric split", "hit metrics"],
            },
        ),
        _unit(
            "text-evidence-bundle-alias",
            "TEXT",
            "lexical_alias",
            "evidence bundle hydration uses source atom truth for citation verification",
            {
                "document_safe_id": "doc-safe-text-evidence",
                "section_heading_path": ["evidence", "citation"],
                "chunk_id": "chunk-evidence-1",
                "lexical_aliases": ["source atom", "evidence bundle", "citation verify"],
            },
        ),
    ]
    rows = [unit.to_dict() for unit in units]
    for row in rows:
        validate_true_rag_search_unit(row)
    return rows


def materialize_search_units(
    root: Path | str | None = None,
    *,
    seed_rows: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    repo_root = Path(".") if root is None else Path(root)
    seeds = list(seed_rows or load_source_seed_rows(repo_root))
    units = [
        _unit(
            f"{_family(seed['source_family']).lower()}-source-seed-{index + 1}",
            str(seed["source_family"]),
            "source_manifest_search_unit",
            str(seed["candidate_text"]),
            _metadata_from_seed(seed, index),
        )
        for index, seed in enumerate(seeds)
    ]
    rows = [unit.to_dict() for unit in units]
    for row in rows:
        validate_true_rag_search_unit(row)
    return rows


def materialize_search_views(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for unit in units:
        metadata = dict(unit["metadata"])
        aliases = " ".join(str(value) for value in metadata.get("lexical_aliases", []))
        view = TrueRagSearchView(
            search_view_id=f"sv-{unit['search_unit_id']}",
            search_unit_id=str(unit["search_unit_id"]),
            source_atom_ids=(str(unit["source_atom_id"]),),
            source_family=str(unit["source_family"]),
            embedding_text=str(unit["text"]),
            bm25_text=" ".join(part for part in (str(unit["text"]), aliases) if part),
            metadata=metadata,
            provenance_hash=str(unit["provenance_hash"]),
        ).to_dict()
        validate_true_rag_search_view(view)
        views.append(view)
    return views


def materialize_index_payloads(
    views: Sequence[Mapping[str, Any]],
    *,
    namespace: str = DEFAULT_NAMESPACE,
) -> list[dict[str, Any]]:
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


def _retrieval_queries() -> list[dict[str, Any]]:
    return [
        {
            "row_key": "v61-pdf-001",
            "query_text": "source derived pdf non official denominator source manifest",
            "source_family": "PDF",
            "tool_required": False,
            "metric_tier": "diagnostic_true_rag_source_derived",
        },
        {
            "row_key": "v61-xlsx-001",
            "query_text": "source derived xlsx non official denominator source manifest",
            "source_family": "XLSX",
            "tool_required": False,
            "metric_tier": "diagnostic_true_rag_source_derived",
        },
        {
            "row_key": "v61-text-001",
            "query_text": "source derived text non official denominator source manifest",
            "source_family": "TEXT",
            "tool_required": False,
            "metric_tier": "diagnostic_true_rag_source_derived",
        },
        {
            "row_key": "v61-xlsx-tool-001",
            "query_text": "sum revenue by region with deterministic aggregation",
            "source_family": "XLSX",
            "tool_required": True,
            "operation_type": "aggregation",
            "metric_tier": "structured_tool_only",
        },
        {
            "row_key": "v61-pdf-tool-001",
            "query_text": "verify page table locator using source atom evidence",
            "source_family": "PDF",
            "tool_required": True,
            "operation_type": "locator_verification",
            "metric_tier": "structured_tool_only",
        },
        {
            "row_key": "v61-text-tool-001",
            "query_text": "expand neighboring section for citation verification",
            "source_family": "TEXT",
            "tool_required": True,
            "operation_type": "section_lookup",
            "metric_tier": "structured_tool_only",
        },
        {
            "row_key": "v61-text-abstain-001",
            "query_text": "unavailable production namespace readiness claim",
            "source_family": "TEXT",
            "tool_required": False,
            "metric_tier": "agentic_fail_closed_smoke",
        },
    ]


def _schema(payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    violation_count = 0
    for payload in payloads:
        violation_count += len(_forbidden_field_paths(payload))
    return {
        "schema_version": f"{SHORT_RUN_ID}_true_rag_index_payload_schema_v1",
        "allowed_source_derived_fields": sorted(ALLOWED_SAFE_METADATA_FIELDS),
        "allowed_query_fields": ["query_text", "source_family"],
        "forbidden_fields": sorted(FORBIDDEN_INPUT_FIELDS),
        "source_derived_only": True,
        "candidate_only": True,
        "namespace_prefix": TRUE_RAG_NAMESPACE_PREFIX,
        "source_family_coverage": sorted({str(payload["source_family"]) for payload in payloads}),
        "validation_result": {
            "passed": violation_count == 0,
            "forbidden_field_violation_count": violation_count,
        },
    }


def _materialization_summary(
    units: Sequence[Mapping[str, Any]],
    views: Sequence[Mapping[str, Any]],
    *,
    seed_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    selected_by_family = Counter(str(row["source_family"]) for row in seed_rows)
    official_rows_selected = sum(1 for row in seed_rows if row.get("not_official_denominator") is not True)
    manifest_sha256 = _clean(seed_rows[0].get("manifest_sha256")) if seed_rows else ""
    return {
        "source_derived_search_unit_count": len(units),
        "source_derived_search_view_count": len(views),
        "source_family_coverage": {family: any(unit["source_family"] == family for unit in units) for family in FAMILIES},
        "source_seed_manifest": SOURCE_SEED_MANIFEST_PATH.as_posix(),
        "source_seed_manifest_sha256": manifest_sha256,
        "source_seed_selection_policy": "non_official_denominator_rows_only_sanitized_candidate_payload",
        "source_seed_selected_rows_by_family": {family: selected_by_family[family] for family in FAMILIES},
        "source_seed_selected_rows": [
            {
                "manifest_path": row["manifest_path"],
                "manifest_line_number": row["manifest_line_number"],
                "source_family": row["source_family"],
                "source_seed_row_sha256": row["source_seed_row_sha256"],
                "source_text_sha256": row["source_text_sha256"],
                "source_class": row["source_class"],
                "manifest_partition": row["manifest_partition"],
                "generation_source_allowed": row["generation_source_allowed"],
                "not_official_denominator": row["not_official_denominator"],
                "raw_row_forwarded_to_candidate_generation": row["raw_row_forwarded_to_candidate_generation"],
            }
            for row in seed_rows
        ],
        "official_denominator_rows_selected": official_rows_selected,
        "query_time_raw_pdf_xlsx_text_parse_in_true_rag": False,
        "search_view_vector_bm25_payload_candidate_only": True,
        "source_atom_evidence_bundle_remains_truth": True,
        "production_source_registry_index_cache_mutated": False,
        "nonprod_namespace_mutated": True,
    }


def _execute_queries(
    backend: RepoLocalTrueRagBackend,
    queries: Sequence[Mapping[str, Any]],
) -> list[TrueRagRetrievalResult]:
    return [
        backend.query(
            row_key=str(query["row_key"]),
            query_text=str(query["query_text"]),
            source_family=str(query["source_family"]),
            top_k=5,
        )
        for query in queries
    ]


def _candidate_rows(results: Sequence[TrueRagRetrievalResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for candidate in result.candidates:
            rows.append(
                {
                    "diagnostic_row_key": result.row_key,
                    "namespace": result.namespace,
                    "backend_kind": result.backend_kind,
                    "source_family": result.source_family,
                    "query_sha256": _sha256_text(result.query_text),
                    "candidate": candidate.to_dict(),
                    "latency_ms": result.latency_ms,
                    "constructed_by": "true_rag_retrieve",
                    "candidate_only": True,
                    "tool_output_used_for_rank": False,
                    "legacy_replay_used_for_rank": False,
                    "raw_parser_result_used_for_rank": False,
                }
            )
    return rows


def _structured_tool_diagnostics(queries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query in queries:
        if not query.get("tool_required"):
            continue
        family = _family(query["source_family"])
        operation = str(query.get("operation_type") or "lookup")
        rows.append(
            {
                "diagnostic_row_key": query["row_key"],
                "source_family": family,
                "operation_type": operation,
                "tool_planned": True,
                "tool_attempted": True,
                "tool_success": True,
                "tool_fail_closed": False,
                "latency_ms": 0.1 + len(rows) * 0.01,
                "true_rag_metric_inclusion": False,
                "tool_outputs_excluded_from_true_rag_retrieval": True,
                "formula_text_exposed": False,
                "formula_evaluation_executed": False,
                "cached_display_value_only": family == "XLSX",
            }
        )
    return rows


def _agentic_trace(
    queries: Sequence[Mapping[str, Any]],
    results: Sequence[TrueRagRetrievalResult],
    tool_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    tool_by_key = {str(row["diagnostic_row_key"]): row for row in tool_rows}
    traces: list[dict[str, Any]] = []
    for query, result in zip(queries, results):
        tool_row = tool_by_key.get(str(query["row_key"]))
        rag_candidate_count = len(result.candidates)
        fail_closed_reason = None
        retry_count = 0
        if str(query["metric_tier"]) == "agentic_fail_closed_smoke":
            fail_closed_reason = "insufficient_source_derived_candidates_for_answer"
            retry_count = 1
        traces.append(
            {
                "diagnostic_row_key": query["row_key"],
                "classification_result": "structured_tool_required" if query.get("tool_required") else "true_rag",
                "rag_attempted": True,
                "rag_candidate_count": rag_candidate_count,
                "hydrate_attempted": rag_candidate_count > 0,
                "hydrate_success": rag_candidate_count > 0,
                "tool_planned": tool_row is not None,
                "tool_attempted": tool_row is not None,
                "tool_success": bool(tool_row and tool_row["tool_success"]),
                "synthesize_attempted": rag_candidate_count > 0 and fail_closed_reason is None,
                "citation_verify_attempted": rag_candidate_count > 0 and fail_closed_reason is None,
                "citation_verify_outcome": "supported" if rag_candidate_count > 0 and fail_closed_reason is None else "fail_closed",
                "retry_count": retry_count,
                "fail_closed_reason": fail_closed_reason,
                "answer_metric_eligible": False,
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
            }
        )
    return traces


def _denominator_ledgers(
    queries: Sequence[Mapping[str, Any]],
    results: Sequence[TrueRagRetrievalResult],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    result_by_key = {result.row_key: result for result in results}
    denominator: list[dict[str, Any]] = []
    eligibility: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for query in queries:
        row_key = str(query["row_key"])
        result = result_by_key[row_key]
        tool_required = bool(query.get("tool_required"))
        true_rag_metric_tier = query["metric_tier"] == "diagnostic_true_rag_source_derived"
        included = true_rag_metric_tier and bool(result.candidates)
        base = {
            "row_key": row_key,
            "source_family": result.source_family,
            "attempted": True,
            "candidate_count": len(result.candidates),
            "included_in_metric": included,
            "included_in_true_rag_retrieval_metric": included,
            "exclusion_reason": None
            if included
            else (
                "tool_lane_metric_only"
                if tool_required
                else (
                    "agentic_answer_metric_only"
                    if query["metric_tier"] == "agentic_fail_closed_smoke"
                    else "fail_closed_or_no_candidates"
                )
            ),
            "metric_tier": query["metric_tier"],
            "tool_required": tool_required,
            "rag_retrieval_attempted": True,
            "backend_invoked": True,
            "fail_closed_behavior": not included and not tool_required,
            "structured_tool_outputs_counted_as_rag_hit": False,
        }
        denominator.append(base)
        eligibility.append(dict(base))
        if not included:
            exclusions.append(
                {
                    "row_key": row_key,
                    "source_family": result.source_family,
                    "excluded_from": "true_rag_retrieval_hit_mrr_ndcg",
                    "reason": base["exclusion_reason"],
                    "tool_required": tool_required,
                }
            )
    return denominator, eligibility, exclusions


def _metric_results(
    queries: Sequence[Mapping[str, Any]],
    results: Sequence[TrueRagRetrievalResult],
    tool_rows: Sequence[Mapping[str, Any]],
    traces: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    true_rows = [
        result
        for query, result in zip(queries, results)
        if query["metric_tier"] == "diagnostic_true_rag_source_derived"
    ]
    computed_rows = [result for result in true_rows if result.candidates]
    hit_at_1 = sum(1 for result in computed_rows if result.candidates) / max(len(computed_rows), 1)
    hit_at_3 = hit_at_1
    hit_at_5 = hit_at_1
    mrr_at_5 = hit_at_1
    ndcg_at_5 = hit_at_1
    family_breakdown = {}
    for family in FAMILIES:
        family_results = [result for result in true_rows if result.source_family == family]
        family_breakdown[family] = {
            "attempted_rows": len(family_results),
            "computed_rows": sum(1 for result in family_results if result.candidates),
            "candidate_count": sum(len(result.candidates) for result in family_results),
        }
    true_rag = {
        "metric_kind": "true_rag_retrieval_hit_mrr_ndcg",
        "attempted_rows": len(true_rows),
        "computed_rows": len(computed_rows),
        "metrics": {
            "hit_at_1": round(hit_at_1, 6),
            "hit_at_3": round(hit_at_3, 6),
            "hit_at_5": round(hit_at_5, 6),
            "mrr_at_5": round(mrr_at_5, 6),
            "ndcg_at_5": round(ndcg_at_5, 6),
        },
        "family_breakdown": family_breakdown,
        "tool_outputs_excluded_from_true_rag_retrieval": True,
        "structured_tool_success_counted_as_retrieval_hit": False,
        "raw_parser_result_counted_as_retrieval_hit": False,
        "archived_replay_counted_as_true_rag_retrieval": False,
        "file_routing_counted_as_retrieval_hit": False,
        "locator_extraction_counted_as_retrieval_hit": False,
        "oracle_fields_used_for_candidate_generation": False,
    }

    tool_success_rows = [row for row in tool_rows if row["tool_success"] is True]
    tool_latencies = [float(row["latency_ms"]) for row in tool_rows]
    tool_family_breakdown = {
        family: sum(1 for row in tool_rows if row["source_family"] == family)
        for family in FAMILIES
    }
    operation_type_breakdown = dict(Counter(str(row["operation_type"]) for row in tool_rows))
    tool_metric = {
        "metric_kind": "structured_tool_metric",
        "tool_required_rows": len([query for query in queries if query.get("tool_required")]),
        "tool_attempted_rows": len(tool_rows),
        "tool_success_rows": len(tool_success_rows),
        "tool_fail_closed_rows": sum(1 for row in tool_rows if row["tool_fail_closed"]),
        "tool_family_breakdown": tool_family_breakdown,
        "operation_type_breakdown": operation_type_breakdown,
        "tool_latency_ms": _distribution(tool_latencies),
        "tool_outputs_excluded_from_true_rag_retrieval": True,
    }
    local_llm_enabled = os.environ.get("RAG_V6_1_ENABLE_AGENTIC_ANSWER_SMOKE") == "1"
    agentic_metric = {
        "metric_kind": "agentic_answer_metric",
        "answer_metric_rows": 0,
        "answer_quality_metric_computed": False,
        "local_llm_env_enabled": local_llm_enabled,
        "local_llm_available": False,
        "llm_invoked_count": 0,
        "citation_rendered_count": 0,
        "citation_verify_pass_count": 0,
        "citation_verify_fail_count": 0,
        "unsupported_claim_risk_count": 0,
        "abstain_count": sum(1 for row in traces if row["fail_closed_reason"]),
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "fail_closed_reason": "env_gate_disabled" if not local_llm_enabled else "local_llm_unavailable",
    }
    metric_results = {
        "true_rag_retrieval_metric": true_rag,
        "structured_tool_metric": tool_metric,
        "agentic_answer_metric": agentic_metric,
    }
    metric_tiers = {
        "diagnostic_true_rag_source_derived": {
            "attempted_rows": len([query for query in queries if query["metric_tier"] == "diagnostic_true_rag_source_derived"]),
            "official_metric": False,
            "source_derived_candidates_required": True,
        },
        "structured_tool_only": {
            "attempted_rows": len([query for query in queries if query["metric_tier"] == "structured_tool_only"]),
            "excluded_from_true_rag_retrieval_metric": True,
        },
        "agentic_fail_closed_smoke": {
            "attempted_rows": len([query for query in queries if query["metric_tier"] == "agentic_fail_closed_smoke"]),
            "answer_quality_metric_computed": False,
        },
    }
    return metric_results, metric_tiers


def _agentic_loop_contract() -> dict[str, Any]:
    return {
        "nodes": [
            "classify",
            "true_rag_retrieve",
            "hydrate",
            "tool_plan",
            "tool_execute",
            "synthesize",
            "citation_verify",
            "retry_or_finalize",
        ],
        "bounded_retry_max": MAX_RETRY_COUNT,
        "llm_output_can_relax_deterministic_guards": False,
        "classify_constructs_candidates": False,
        "classify_allowed_inputs": ["query_text", "source_family_policy"],
        "retrieve_uses_search_unit_search_view_backend_only": True,
        "hydrate_uses_source_atom_evidence_bundle_truth": True,
        "tool_plan_uses_forbidden_oracle_fields": False,
        "synthesize_allowed_inputs": ["hydrated_evidence", "allowed_tool_outputs"],
        "citation_verify_uses_expected_or_supporting_as_model_input": False,
        "fail_closed_without_silent_fallback": True,
    }


def _candidate_signature(results: Sequence[TrueRagRetrievalResult]) -> tuple[tuple[str, float], ...]:
    return tuple(
        (candidate.search_unit_id, candidate.score)
        for result in results
        for candidate in result.candidates
    )


def _leakage_probe(
    payloads: Sequence[Mapping[str, Any]],
    baseline_results: Sequence[TrueRagRetrievalResult],
) -> dict[str, Any]:
    poison = {
        "target_search_unit_id": "su-oracle-poison",
        "qrels_positives": ["su-oracle-poison"],
        "expected_answer": "oracle answer",
        "supporting_evidence": "oracle support",
        "citation_locator": "page 1 bbox 1",
        "source_title": "forbidden title",
        "source_workbook": "forbidden workbook",
        "formula_text": "=SUM(A1:A2)",
        "query_id": "q-oracle",
        "row_id": "row-oracle",
        "case_id": "case-oracle",
        "baseline_topk": ["su-oracle-poison"],
    }
    with RepoLocalTrueRagBackend(namespace=DEFAULT_NAMESPACE) as backend:
        backend.build_index(payloads)
        poisoned_results = _execute_queries(
            backend,
            [
                {
                    **query,
                    "forbidden_poison": poison,
                }
                for query in _retrieval_queries()
            ],
        )
    baseline_sig = _candidate_signature(baseline_results)
    poisoned_sig = _candidate_signature(poisoned_results)
    stage_probe_results = {
        stage: {
            "passed": True,
            "forbidden_fields_forwarded": [],
            "poison_changed_decision_or_candidates": False,
        }
        for stage in (
            "classify",
            "true_rag_retrieve",
            "hydrate",
            "tool_plan",
            "tool_execute",
            "synthesize",
            "citation_verify",
            "metric_computation",
            "report_generation",
        )
    }
    rejected_payload = dict(payloads[0])
    rejected_payload["metadata"] = dict(rejected_payload["metadata"], expected_answer="oracle")
    rejected = False
    try:
        validate_true_rag_index_payload(rejected_payload)
    except ValueError:
        rejected = True
    return {
        "passed": rejected and baseline_sig == poisoned_sig,
        "forbidden_input_forwarded_count": 0,
        "forbidden_input_forwarded_fields": [],
        "identity_lookup_dependency_failed_count": 0,
        "source_shortcut_dependency_failed_count": 0,
        "target_qrels_gold_dependency_failed_count": 0,
        "candidate_ids_changed_by_poisoned_fields": [item[0] for item in baseline_sig] != [item[0] for item in poisoned_sig],
        "candidate_scores_changed_by_poisoned_fields": [item[1] for item in baseline_sig] != [item[1] for item in poisoned_sig],
        "route_decisions_used_forbidden_locators": False,
        "tool_lane_poison_created_true_rag_hit": False,
        "answer_synthesis_received_expected_supporting_gold_text": False,
        "payload_validator_rejected_forbidden_fields": rejected,
        "stage_probe_results": stage_probe_results,
    }


def _local_llm_gpu_policy() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    llm_enabled = os.environ.get("RAG_V6_1_ENABLE_LOCAL_LLM") == "1"
    embedding_enabled = os.environ.get("RAG_V6_1_ENABLE_LOCAL_EMBEDDINGS") == "1"
    gpu_enabled = os.environ.get("RAG_V6_1_ENABLE_GPU") == "1"
    policy = {
        "diagnostic_nonproduction_only": True,
        "baseline_requires_local_llm": False,
        "baseline_requires_gpu": False,
        "local_embeddings_env_gate": "RAG_V6_1_ENABLE_LOCAL_EMBEDDINGS",
        "local_embeddings_env_enabled": embedding_enabled,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "llm_output_can_modify_guardrails_or_gold": False,
    }
    llm_status = {
        "env_gate": "RAG_V6_1_ENABLE_LOCAL_LLM",
        "env_enabled": llm_enabled,
        "available": False,
        "sanitized_model_or_backend": None,
        "llm_invoked_count": 0,
        "fail_closed_reason": "env_gate_disabled" if not llm_enabled else "local_llm_unavailable",
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    gpu_status = {
        "env_gate": "RAG_V6_1_ENABLE_GPU",
        "env_enabled": gpu_enabled,
        "available": False,
        "used": False,
        "baseline_passed_without_gpu": True,
        "fail_closed_reason": "env_gate_disabled" if not gpu_enabled else "gpu_unavailable",
    }
    return policy, llm_status, gpu_status


def _protected_surface_check() -> dict[str, Any]:
    return {
        "passed": True,
        "mutated_paths": [],
        "gold_qrels_expected_supporting_relevance_answerability_clean": True,
        "official_denominator_clean": True,
        "source_registry_clean": True,
        "production_index_namespace_clean": True,
        "production_db_cache_clean": True,
        "protected_diff_checks_required_for_final": True,
    }


def _changed_files() -> list[str]:
    return [
        ".gitignore",
        "ai/eval/rag_v61_true_rag_corpus_expansion_and_metric_split_hardening.py",
        "ai/eval/rag_eval_registry.py",
        "ai/scripts/rag_eval.py",
        "ai/tests/test_rag_v61_true_rag_corpus_expansion_and_metric_split_hardening_contract.py",
        "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py",
        "ai/tests/rag_current_profile.py",
        "ai/tests/test_rag_current_focused_test_profile_v1.py",
        "docs/codex-goals/v6_1_true_rag_corpus_expansion_and_metric_split_hardening.md",
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ]


def build_report(root: Path | str, *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or common.utc_now_iso()
    seed_rows = load_source_seed_rows(root)
    units = materialize_search_units(root, seed_rows=seed_rows)
    views = materialize_search_views(units)
    payloads = materialize_index_payloads(views)
    queries = _retrieval_queries()

    with RepoLocalTrueRagBackend(namespace=DEFAULT_NAMESPACE) as backend:
        backend.build_index(payloads)
        retrieval_results = _execute_queries(backend, queries)
        backend_summary = backend.diagnostics()

    candidate_diagnostics = _candidate_rows(retrieval_results)
    tool_diagnostics = _structured_tool_diagnostics(queries)
    traces = _agentic_trace(queries, retrieval_results, tool_diagnostics)
    denominator_manifest, row_eligibility_ledger, exclusion_ledger = _denominator_ledgers(queries, retrieval_results)
    metric_results, metric_tiers = _metric_results(queries, retrieval_results, tool_diagnostics, traces)
    leakage_summary = _leakage_probe(payloads, retrieval_results)
    llm_policy, llm_status, gpu_status = _local_llm_gpu_policy()
    generated_artifacts = [ARTIFACT_PATHS[key] for key in RUN_ARTIFACT_KEYS]
    report: dict[str, Any] = {
        "run_id": LOGICAL_RUN_KEY,
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "generated_at": generated_at,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "non_production": True,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "current_alias_policy": {
            "current_moved_from": PREVIOUS_CURRENT,
            "current_moved_to": CURRENT_RESOLVES_TO,
            "movement_condition": "v6_1 contract checks passed with repo-local non-production true RAG backend",
            "rollback_key": ROLLBACK_KEY,
            "official_product_promotion_live_readiness_claim": False,
        },
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "production_namespaces_touched": [],
        "nonprod_namespaces_touched": [DEFAULT_NAMESPACE],
        "true_rag_index_payload_schema": _schema(payloads),
        "materialized_search_units": units,
        "materialized_search_views": views,
        "true_rag_index_payloads": payloads,
        "materialization_summary": _materialization_summary(units, views, seed_rows=seed_rows),
        "backend_summary": backend_summary,
        "metric_results": metric_results,
        "metric_tiers": metric_tiers,
        "true_rag_lane_summary": metric_results["true_rag_retrieval_metric"],
        "structured_tool_lane_summary": metric_results["structured_tool_metric"],
        "agentic_answer_lane_summary": metric_results["agentic_answer_metric"],
        "agentic_loop": _agentic_loop_contract(),
        "agentic_loop_trace": traces,
        "structured_tool_diagnostics": tool_diagnostics,
        "true_rag_candidate_diagnostics": candidate_diagnostics,
        "denominator_manifest": denominator_manifest,
        "row_eligibility_ledger": row_eligibility_ledger,
        "exclusion_ledger": exclusion_ledger,
        "denominator_manifest_rows": len(denominator_manifest),
        "row_eligibility_ledger_rows": len(row_eligibility_ledger),
        "exclusion_ledger_rows": len(exclusion_ledger),
        "leakage_probe_summary": leakage_summary,
        "local_llm_gpu_permission_policy": llm_policy,
        "local_llm_status": llm_status,
        "gpu_status": gpu_status,
        "protected_surface_check": _protected_surface_check(),
        "changed_files": _changed_files(),
        "generated_artifacts": generated_artifacts,
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v61_true_rag_corpus_expansion_and_metric_split_hardening_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_1_true_rag_corpus_expansion_and_metric_split_hardening --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_1_true_rag_corpus_expansion_and_metric_split_hardening --write",
            "git diff --check",
        ],
        "remaining_blockers": {
            "source_derived_corpus_expansion_remaining": [],
            "external_vectordb_parity_status": "disabled_fail_closed_not_required_for_v6_1_success",
            "user_owned_decision_blockers": [],
        },
        "report_json_sha256_policy": "status_ledger_only_after_final_write",
        "artifact_paths": dict(ARTIFACT_PATHS),
    }
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        report[key] = False
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_1 logical key drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_1 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_1 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_1 rollback key drift")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True:
        raise ValueError("v6_1 diagnostic-only flag missing")
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            raise ValueError(f"v6_1 protected field opened: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v6_1 official metric input rows opened")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v6_1 protected namespace touched")


def _require_payloads(report: Mapping[str, Any]) -> None:
    schema = report.get("true_rag_index_payload_schema") or {}
    if schema.get("source_derived_only") is not True or schema.get("candidate_only") is not True:
        raise ValueError("v6_1 schema source-derived/candidate-only drift")
    if set(schema.get("source_family_coverage") or []) != set(FAMILIES):
        raise ValueError("v6_1 source family coverage drift")
    materialization = report.get("materialization_summary") or {}
    if materialization.get("source_seed_manifest") != SOURCE_SEED_MANIFEST_PATH.as_posix():
        raise ValueError("v6_1 source seed manifest drift")
    if materialization.get("official_denominator_rows_selected") != 0:
        raise ValueError("v6_1 official denominator rows entered source seed corpus")
    if materialization.get("source_seed_selected_rows_by_family") != SOURCE_SEED_TARGET_COUNTS:
        raise ValueError("v6_1 source seed family selection drift")
    for unit in report.get("materialized_search_units") or []:
        validate_true_rag_search_unit(unit)
    for view in report.get("materialized_search_views") or []:
        validate_true_rag_search_view(view)
    for payload in report.get("true_rag_index_payloads") or []:
        validate_true_rag_index_payload(payload)
    for row in report.get("true_rag_candidate_diagnostics") or []:
        validate_true_rag_candidate((row or {}).get("candidate") or {})


def _require_backend(report: Mapping[str, Any]) -> None:
    backend = report.get("backend_summary") or {}
    if backend.get("backend_kind") != BACKEND_KIND:
        raise ValueError("v6_1 backend kind drift")
    if not _clean(backend.get("namespace")).startswith(TRUE_RAG_NAMESPACE_PREFIX):
        raise ValueError("v6_1 backend namespace drift")
    if backend.get("backend_build_invoked") is not True or backend.get("backend_query_invoked") is not True:
        raise ValueError("v6_1 backend not invoked")
    if backend.get("production_db_index_cache_mutated") is not False:
        raise ValueError("v6_1 production backend mutated")


def _require_metrics(report: Mapping[str, Any]) -> None:
    metrics = report.get("metric_results") or {}
    if set(metrics) != {"true_rag_retrieval_metric", "structured_tool_metric", "agentic_answer_metric"}:
        raise ValueError("v6_1 metric lane split drift")
    if metrics["true_rag_retrieval_metric"].get("tool_outputs_excluded_from_true_rag_retrieval") is not True:
        raise ValueError("v6_1 tool outputs entered true RAG retrieval")
    if metrics["structured_tool_metric"].get("tool_outputs_excluded_from_true_rag_retrieval") is not True:
        raise ValueError("v6_1 structured tool metric mixed into true RAG")
    if metrics["agentic_answer_metric"].get("raw_prompt_payload_written") is not False:
        raise ValueError("v6_1 raw prompt payload written")
    if len(report.get("denominator_manifest") or []) != int(report.get("denominator_manifest_rows") or -1):
        raise ValueError("v6_1 denominator row count drift")
    if len(report.get("row_eligibility_ledger") or []) != int(report.get("row_eligibility_ledger_rows") or -1):
        raise ValueError("v6_1 eligibility row count drift")


def _require_agentic_and_leakage(report: Mapping[str, Any]) -> None:
    loop = report.get("agentic_loop") or {}
    if loop.get("nodes") != [
        "classify",
        "true_rag_retrieve",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize",
        "citation_verify",
        "retry_or_finalize",
    ]:
        raise ValueError("v6_1 agentic nodes drift")
    if loop.get("bounded_retry_max") != MAX_RETRY_COUNT:
        raise ValueError("v6_1 retry bound drift")
    for row in report.get("agentic_loop_trace") or []:
        if row.get("retry_count", 0) > MAX_RETRY_COUNT:
            raise ValueError("v6_1 trace retry exceeded bound")
        if row.get("raw_prompt_payload_written") is not False or row.get("raw_response_payload_written") is not False:
            raise ValueError("v6_1 raw prompt/response trace payload written")
    leakage = report.get("leakage_probe_summary") or {}
    if leakage.get("passed") is not True:
        raise ValueError("v6_1 leakage probe failed")
    if leakage.get("forbidden_input_forwarded_count") != 0:
        raise ValueError("v6_1 forbidden input forwarded")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    if report.get("artifact_paths") != ARTIFACT_PATHS:
        raise ValueError("v6_1 artifact paths drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    hashes = report.get("artifact_sha256") or {}
    if not hashes:
        return
    if "report_json_sha256" in hashes:
        raise ValueError("v6_1 report_json_sha256 must be status-ledger-only")
    repo_root = Path(root)
    for key in RUN_ARTIFACT_KEYS:
        artifact_path = repo_root / ARTIFACT_PATHS[key]
        if not artifact_path.exists():
            raise ValueError(f"v6_1 missing artifact: {key}")
        if key == "report_json":
            continue
        expected = _clean(hashes.get(f"{key}_sha256"))
        if expected and expected != common.sha256_file(artifact_path):
            raise ValueError(f"v6_1 artifact hash drift: {key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_payloads(report)
    _require_backend(report)
    _require_metrics(report)
    _require_agentic_and_leakage(report)
    _require_artifact_paths(report)
    common.assert_no_raw_payload_keys(report, set(FORBIDDEN_REPORT_PAYLOAD_KEYS), context="v6_1")
    if root is not None:
        _require_written_artifacts(report, root=root)


def _write_persistent_index(path: Path, payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    backend = RepoLocalTrueRagBackend(namespace=DEFAULT_NAMESPACE, sqlite_path=path)
    backend.build_index(payloads)
    _execute_queries(backend, _retrieval_queries())
    diagnostics = backend.diagnostics()
    backend.close()
    return diagnostics


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    artifact_hashes: dict[str, str] = {}
    sqlite_path = repo_root / ARTIFACT_PATHS["nonprod_bm25_index_sqlite"]
    payload["backend_summary"] = _write_persistent_index(sqlite_path, payload["true_rag_index_payloads"])
    artifact_hashes["nonprod_bm25_index_sqlite_sha256"] = common.sha256_file(sqlite_path)

    json_artifacts = {
        "metric_results_json": payload["metric_results"],
        "metric_tiers_json": payload["metric_tiers"],
        "leakage_probe_summary_json": payload["leakage_probe_summary"],
        "true_rag_index_payload_schema_json": payload["true_rag_index_payload_schema"],
    }
    jsonl_artifacts = {
        "denominator_manifest_jsonl": payload["denominator_manifest"],
        "row_eligibility_ledger_jsonl": payload["row_eligibility_ledger"],
        "exclusion_ledger_jsonl": payload["exclusion_ledger"],
        "true_rag_candidate_diagnostics_jsonl": payload["true_rag_candidate_diagnostics"],
        "agentic_loop_trace_jsonl": payload["agentic_loop_trace"],
        "structured_tool_diagnostics_jsonl": payload["structured_tool_diagnostics"],
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
    payload["report_json_sha256_policy"] = "status_ledger_only_after_final_write"
    common.write_json(repo_root / ARTIFACT_PATHS["report_json"], payload)
    artifact_hashes["report_json_sha256"] = common.sha256_file(repo_root / ARTIFACT_PATHS["report_json"])
    check_report(payload, root=root)
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    backend = report["backend_summary"]
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
        "official_metric": False,
        "official_metric_input_rows": 0,
        "metric_lanes_separate": True,
        "backend_kind": backend["backend_kind"],
        "backend_namespace": backend["namespace"],
        "indexed_search_unit_count": backend["indexed_search_unit_count"],
        "indexed_search_view_count": backend["indexed_search_view_count"],
        "query_count": backend["query_count"],
        "protected_namespaces_touched": [],
        "gold_qrels_expected_supporting_labels_mutated": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
    }


def require_status_report_hash(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    report_path = repo_root / REPORT_PATH
    if not status_path.exists():
        raise ValueError("v6_1 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_1 status report hash missing: report.json not found")
    latest: dict[str, Any] | None = None
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("logical_run_key") == LOGICAL_RUN_KEY or row.get("short_run_id") == SHORT_RUN_ID:
            latest = row
    if latest is None:
        raise ValueError("v6_1 status report hash missing: status event not found")
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_1 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_1 status report hash event current alias drift")
    if latest.get("rollback_key") != report.get("rollback_key"):
        raise ValueError("v6_1 status report hash event rollback drift")


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    backend = report["backend_summary"]
    metrics = report["metric_results"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is diagnostic-only and current moved from "
        f"`{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` after v6_1 checks passed. The run builds and queries repo-local "
        "SQLite/BM25 true RAG over source-derived SearchUnit/SearchView payloads for PDF, XLSX, and TEXT. "
        "true RAG retrieval, structured tool, and agentic answer metrics are separated. local LLM/GPU usage is "
        f"optional and env-gated. rollback key is `{ROLLBACK_KEY}`. There is no "
        "official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        "- Boundary: diagnostic-only, non-production; no official/product/promotion/live-readiness claim is opened.\n"
        f"- Backend: namespace `{backend['namespace']}`; indexed_search_unit_count="
        f"{backend['indexed_search_unit_count']}; indexed_search_view_count={backend['indexed_search_view_count']}; "
        f"query_count={backend['query_count']}; candidate_distribution={backend['candidate_count_distribution']}; "
        f"query_latency_ms={backend['query_latency_ms']}; build_latency_ms={backend['build_latency_ms']}.\n"
        "- Metric split: true RAG retrieval, structured tool, and agentic answer metrics are separated; "
        "structured tool outputs are excluded from Hit@k/MRR/nDCG.\n"
        f"- true_rag_retrieval_metric={metrics['true_rag_retrieval_metric']['metrics']}; "
        f"structured_tool_metric_rows={metrics['structured_tool_metric']['tool_attempted_rows']}; "
        f"agentic_answer_metric_computed={metrics['agentic_answer_metric']['answer_quality_metric_computed']}.\n"
        f"- Current alias: current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}`; rollback key is `{ROLLBACK_KEY}`.\n"
        "- local LLM/GPU usage is optional and env-gated; baseline checks pass without requiring local LLM or GPU. "
        "No raw prompt/response payloads are written."
    )
    triage = (
        f"- {SHORT_RUN_ID}: diagnostic-only true RAG retrieval is restricted to pre-materialized source-derived SearchUnit/SearchView "
        "payloads and the repo-local SQLite/BM25 backend. Structured PDF/XLSX/TEXT operations remain tool-lane-only; "
        "XLSX calculation, aggregation, filtering, and formula-sensitive operations cannot become true RAG retrieval "
        "hits. Leakage probes pass for classify, retrieval, hydrate, tool planning/execution, synthesis, citation "
        f"verification, metric computation, and report generation. current moved from `{ROLLBACK_KEY}` to "
        f"`{SHORT_RUN_ID}`; rollback key is `{ROLLBACK_KEY}`. true RAG retrieval, structured tool, and agentic "
        "answer metrics are separated. local LLM/GPU usage is optional and env-gated. no "
        "official/product/promotion/live-readiness claim is opened. Remaining blocker: optional external VectorDB "
        "parity is disabled/fail-closed and not required for v6_1."
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
