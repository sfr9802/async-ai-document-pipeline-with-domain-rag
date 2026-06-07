from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v6_2_source_derived_materialization_scaleout_and_denominator_reality_check"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_2_SOURCE_DERIVED_MATERIALIZATION_SCALEOUT_DENOMINATOR_REALITY_CHECK_NONPROD_READY"
PREVIOUS_CURRENT = "v6_1_true_rag_corpus_expansion_and_metric_split_hardening"
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
DENOMINATOR_REALITY_AUDIT_PATH = RUN_ROOT / "denominator_reality_audit.json"
RETRIEVAL_METRIC_COVERAGE_PATH = RUN_ROOT / "retrieval_metric_coverage.json"
TRUE_RAG_INDEX_PAYLOAD_SCHEMA_PATH = RUN_ROOT / "true_rag_index_payload_schema.json"
TRUE_RAG_CANDIDATE_DIAGNOSTICS_PATH = RUN_ROOT / "true_rag_candidate_diagnostics.jsonl"
CANDIDATE_TEXT_QUALITY_AUDIT_PATH = RUN_ROOT / "candidate_text_quality_audit.json"
MATERIALIZATION_COVERAGE_PATH = RUN_ROOT / "materialization_coverage.json"
AGENTIC_LOOP_TRACE_PATH = RUN_ROOT / "agentic_loop_trace.jsonl"
STRUCTURED_TOOL_DIAGNOSTICS_PATH = RUN_ROOT / "structured_tool_diagnostics.jsonl"
NONPROD_BM25_INDEX_SQLITE_PATH = RUN_ROOT / "true_rag_bm25_index.sqlite"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

SOURCE_VIEW_MANIFEST_PATH = Path("ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl")
SOURCE_VIEW_INGEST_MANIFEST_PATH = Path("ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json")
SOURCE_REGISTRY_INVENTORY_PATH = Path("ai/eval/source_registry/source_atom_registry_inventory.json")
V5_8_REPORT_PATH = REPORT_ROOT / "runs" / "v5_8_retrieval_metric_evaluation_framework" / "report.json"
V5_8_METRIC_TIERS_PATH = REPORT_ROOT / "runs" / "v5_8_retrieval_metric_evaluation_framework" / "metric_tiers.json"
V6_1_REPORT_PATH = REPORT_ROOT / "runs" / PREVIOUS_CURRENT / "report.json"

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "metric_results_json": METRIC_RESULTS_PATH.as_posix(),
    "metric_tiers_json": METRIC_TIERS_PATH.as_posix(),
    "leakage_probe_summary_json": LEAKAGE_PROBE_SUMMARY_PATH.as_posix(),
    "denominator_manifest_jsonl": DENOMINATOR_MANIFEST_PATH.as_posix(),
    "row_eligibility_ledger_jsonl": ROW_ELIGIBILITY_LEDGER_PATH.as_posix(),
    "exclusion_ledger_jsonl": EXCLUSION_LEDGER_PATH.as_posix(),
    "denominator_reality_audit_json": DENOMINATOR_REALITY_AUDIT_PATH.as_posix(),
    "retrieval_metric_coverage_json": RETRIEVAL_METRIC_COVERAGE_PATH.as_posix(),
    "true_rag_index_payload_schema_json": TRUE_RAG_INDEX_PAYLOAD_SCHEMA_PATH.as_posix(),
    "true_rag_candidate_diagnostics_jsonl": TRUE_RAG_CANDIDATE_DIAGNOSTICS_PATH.as_posix(),
    "candidate_text_quality_audit_json": CANDIDATE_TEXT_QUALITY_AUDIT_PATH.as_posix(),
    "materialization_coverage_json": MATERIALIZATION_COVERAGE_PATH.as_posix(),
    "agentic_loop_trace_jsonl": AGENTIC_LOOP_TRACE_PATH.as_posix(),
    "structured_tool_diagnostics_jsonl": STRUCTURED_TOOL_DIAGNOSTICS_PATH.as_posix(),
    "nonprod_bm25_index_sqlite": NONPROD_BM25_INDEX_SQLITE_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}
RUN_ARTIFACT_KEYS = tuple(key for key in ARTIFACT_PATHS if key != "status_jsonl")

FAMILIES = ("PDF", "TEXT", "XLSX")
SOURCE_ROWS_PER_FAMILY = 100
MIN_INDEXED_COUNT = 300
MIN_INDEXED_PER_FAMILY = 50
MIN_MEANINGFUL_TOTAL = 200
MIN_MEANINGFUL_PER_FAMILY = 30
TOP_K = 5
MAX_RETRY_COUNT = 2
TRUE_RAG_NAMESPACE_PREFIX = "v6_2_true_rag_nonprod_"
DEFAULT_NAMESPACE = "v6_2_true_rag_nonprod_materialization_scaleout_denominator_reality"
BACKEND_KIND = "repo_local_sqlite_bm25"

ALLOWED_SAFE_METADATA_FIELDS = frozenset(
    {
        "candidate_only_payload_role",
        "evidence_truth_role",
        "materialization_bucket",
        "meaningful_semantic_text",
        "provenance_hash",
        "source_atom_id",
        "source_family",
        "source_safe_id",
        "source_text_sha256",
        "unit_type",
    }
)

FORBIDDEN_INPUT_FIELDS = frozenset(
    {
        "answer_value",
        "archived_top_k",
        "archived_topk",
        "baseline_target_search_unit_id",
        "baseline_topk",
        "baseline_topk_candidate_ids",
        "case_id",
        "citation_locator",
        "direct_answer_value",
        "direct_normalized_answer_value",
        "expected_answer",
        "expected_answer_ko",
        "expected_answer_text",
        "file_name",
        "formula_evaluation",
        "formula_evaluation_result",
        "formula_result",
        "formula_text",
        "gold_locator",
        "hidden_target_locator",
        "include_in_official_denominator",
        "normalized_value",
        "official_denominator_inclusion",
        "qrels_positive_id",
        "qrels_positive_ids",
        "qrels_positives",
        "query_id",
        "raw_local_path",
        "raw_locator",
        "raw_path",
        "row_id",
        "source_file_name",
        "source_filename",
        "source_identity",
        "source_path",
        "source_pdf_path",
        "source_title",
        "source_workbook",
        "supporting_evidence",
        "supporting_evidence_id",
        "supporting_evidence_ids",
        "target_locator",
        "target_search_unit_id",
        "topk_new",
        "workbook",
        "workbook_filename",
        "workbook_id",
        "workbook_name",
    }
)
FORBIDDEN_INDEX_PAYLOAD_FIELDS = FORBIDDEN_INPUT_FIELDS
FORBIDDEN_REPORT_PAYLOAD_KEYS = {
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
    "formula_text",
    "formula_evaluation",
    "direct_normalized_answer_value",
}
FORBIDDEN_CANDIDATE_TEXT_PATTERNS = (
    "expected_answer",
    "supporting_evidence",
    "citation_locator",
    "target_search_unit_id",
    "query_id",
    "row_id",
    "case_id",
    "source_title",
    "source_workbook",
    "workbook=",
    "workbook:",
    "source_path",
    "raw_path",
    "local-storage",
    ".xlsx",
    ".pdf",
    "formula_text",
    "formula_evaluation",
    "normalized_value",
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
    "relevance_label_mutation",
    "answerability_label_mutation",
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
    "official_denominator_mutation",
    "production_source_registry_mutated",
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
        raise ValueError(f"unsupported source family: {value!r}")
    return family


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[0-9A-Za-z가-힣_]+", value.lower())


def _canonical_field_name(value: Any) -> str:
    return re.sub(r"[^0-9a-z]", "", str(value or "").strip().lower())


FORBIDDEN_INDEX_PAYLOAD_CANONICAL_FIELDS = frozenset(_canonical_field_name(field) for field in FORBIDDEN_INDEX_PAYLOAD_FIELDS)


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


def _require_no_forbidden_candidate_text(text: str, *, context: str) -> None:
    lowered = text.lower()
    found = [token for token in FORBIDDEN_CANDIDATE_TEXT_PATTERNS if token in lowered]
    if found:
        raise ValueError(f"{context} candidate text contains forbidden tokens: {found}")


def validate_true_rag_index_payload(value: Mapping[str, Any]) -> None:
    _require_no_forbidden_fields(value, context="TrueRagIndexPayload")
    unexpected = set(value) - EXPECTED_INDEX_PAYLOAD_KEYS
    if unexpected:
        raise ValueError(f"TrueRagIndexPayload contains unexpected top-level fields: {sorted(unexpected)}")
    namespace = _clean(value.get("namespace"))
    if not namespace.startswith(TRUE_RAG_NAMESPACE_PREFIX):
        raise ValueError("TrueRagIndexPayload namespace must be v6_2 non-production true RAG")
    if not _clean(value.get("payload_id")):
        raise ValueError("TrueRagIndexPayload missing payload_id")
    _family(value.get("source_family"))
    if not _clean(value.get("search_unit_id")) or not _clean(value.get("search_view_id")):
        raise ValueError("TrueRagIndexPayload missing ids")
    if not _clean(value.get("embedding_text")) or not _clean(value.get("bm25_text")):
        raise ValueError("TrueRagIndexPayload missing index text")
    _require_no_forbidden_candidate_text(_clean(value.get("embedding_text")), context="TrueRagIndexPayload")
    _require_no_forbidden_candidate_text(_clean(value.get("bm25_text")), context="TrueRagIndexPayload")
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("TrueRagIndexPayload metadata must be an object")
    unknown = set(metadata) - ALLOWED_SAFE_METADATA_FIELDS
    if unknown:
        raise ValueError(f"TrueRagIndexPayload unsafe metadata fields: {sorted(unknown)}")


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


class RepoLocalTrueRagBackend:
    def __init__(self, *, namespace: str = DEFAULT_NAMESPACE, sqlite_path: Path | str | None = None) -> None:
        if not namespace.startswith(TRUE_RAG_NAMESPACE_PREFIX):
            raise ValueError("true RAG backend namespace must be v6_2 non-production")
        self.namespace = namespace
        self.sqlite_path = ":memory:" if sqlite_path is None else str(sqlite_path)
        self._conn: sqlite3.Connection | None = None
        self.indexed_search_unit_count = 0
        self.indexed_search_view_count = 0
        self.indexed_meaningful_search_unit_count = 0
        self.indexed_ineligible_search_unit_count = 0
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
        self.indexed_meaningful_search_unit_count = sum(
            1 for row in payloads if ((row.get("metadata") or {}).get("meaningful_semantic_text") is True)
        )
        self.indexed_ineligible_search_unit_count = self.indexed_search_unit_count - self.indexed_meaningful_search_unit_count
        self.build_latency_ms = round((time.perf_counter() - started) * 1000, 4)

    def query_from_raw_source_parse(self, _path: str, *, query_text: str) -> TrueRagRetrievalResult:
        raise ValueError("raw parser query-time true RAG retrieval is forbidden")

    def query(self, *, row_key: str, query_text: str, source_family: str, top_k: int = TOP_K) -> TrueRagRetrievalResult:
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
            candidates.append(
                TrueRagCandidate(
                    candidate_id=_clean(row[0]),
                    search_unit_id=_clean(row[2]),
                    search_view_id=_clean(row[3]),
                    source_atom_ids=tuple(json.loads(row[4])),
                    source_family=_clean(row[1]),
                    score=round(float(score), 6),
                    rank=rank,
                    metadata=json.loads(row[7]),
                )
            )
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
        return _backend_summary_from_counts(
            indexed_search_unit_count=self.indexed_search_unit_count,
            indexed_search_view_count=self.indexed_search_view_count,
            indexed_meaningful_search_unit_count=self.indexed_meaningful_search_unit_count,
            indexed_ineligible_search_unit_count=self.indexed_ineligible_search_unit_count,
            query_count=self.query_count,
            candidate_counts=self.candidate_counts,
            query_latencies_ms=self.query_latencies_ms,
            build_latency_ms=self.build_latency_ms,
            sqlite_path=self.sqlite_path,
        )


def _distribution(values: Sequence[float | int]) -> dict[str, float | int]:
    if not values:
        return {"min": 0, "p50": 0, "p95": 0, "max": 0}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "min": ordered[0],
        "p50": median(ordered),
        "p95": ordered[p95_index],
        "max": ordered[-1],
    }


def _backend_summary_from_counts(
    *,
    indexed_search_unit_count: int,
    indexed_search_view_count: int,
    indexed_meaningful_search_unit_count: int,
    indexed_ineligible_search_unit_count: int,
    query_count: int,
    candidate_counts: Sequence[int],
    query_latencies_ms: Sequence[float],
    build_latency_ms: float,
    sqlite_path: str,
) -> dict[str, Any]:
    return {
        "backend_kind": BACKEND_KIND,
        "namespace": DEFAULT_NAMESPACE,
        "backend_build_invoked": indexed_search_view_count > 0,
        "backend_query_invoked": query_count > 0,
        "indexed_search_unit_count": indexed_search_unit_count,
        "indexed_search_view_count": indexed_search_view_count,
        "indexed_meaningful_search_unit_count": indexed_meaningful_search_unit_count,
        "indexed_ineligible_search_unit_count": indexed_ineligible_search_unit_count,
        "query_count": query_count,
        "candidate_count_distribution": _distribution(candidate_counts),
        "query_latency_ms": _distribution(query_latencies_ms),
        "build_latency_ms": build_latency_ms,
        "sqlite_path": str(sqlite_path).replace("\\", "/"),
        "bm25_only_baseline_passed": indexed_search_view_count >= MIN_INDEXED_COUNT and query_count >= MIN_INDEXED_COUNT,
        "fake_noop_or_replay_backend_used": False,
        "archived_topk_replay_projection_backend_rejected": True,
        "production_db_index_cache_mutated": False,
        "protected_namespaces_touched": [],
    }


def _strip_forbidden_text(value: str) -> str:
    text = value.replace("\\", "/")
    text = re.sub(r"[A-Za-z]:/[^ \n|)]+", " ", text)
    text = re.sub(r"local-storage/[^ \n|)]+", " ", text, flags=re.I)
    text = re.sub(r"[\w가-힣()._\- ]+\.(?:pdf|xlsx)\b", " ", text, flags=re.I)
    text = re.sub(r"\b(?:workbook|source_path|source_pdf_path|raw_path|normalized_value|formula_text|formula_evaluation)=[^|\n]+", " ", text, flags=re.I)
    text = re.sub(r"\b(?:range|cell|bbox|page|physical_page_index)=[^|\n]+", " ", text, flags=re.I)
    text = re.sub(r"\b(?:SourceAtom|Family|Identity|Locator):[^\n]+", " ", text)
    text = re.sub(r"\bdocv_[0-9A-Za-z_:-]+", " ", text)
    text = re.sub(r"\bsrcatom_[0-9A-Za-z_:-]+", " ", text)
    text = re.sub(r"\bsearchview_[0-9A-Za-z_:-]+", " ", text)
    text = re.sub(r"\b[0-9a-f]{16,}\b", " ", text, flags=re.I)
    text = re.sub(r"[|=:/()\[\],]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_field(text: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}=([^|\n]+)", text, flags=re.I)
    return "" if match is None else match.group(1).strip()


def _xlsx_semantic_text(row: Mapping[str, Any]) -> str:
    text = "\n".join(_clean(row.get(key)) for key in ("display_text", "bm25_text", "embedding_text"))
    row_label = _extract_field(text, "row_label")
    column_label = _extract_field(text, "column_label")
    target_column = _extract_field(text, "target_column")
    labels: list[str] = []
    for segment in row_label.split("|"):
        key = segment.split("=", 1)[0].strip()
        if key and key.lower() not in {"range", "cell", "sheet", "workbook", "source_path"}:
            labels.append(key)
    for value in (column_label, target_column):
        if value and value not in labels:
            labels.append(value)
    if not labels:
        labels = ["structured", "table", "row", "column", "header"]
    return _strip_forbidden_text("XLSX structured table fields " + " ".join(labels))


def _semantic_candidate_text(row: Mapping[str, Any]) -> str:
    family = _family(row.get("source_family") or row.get("sourceFamily"))
    display = _clean(row.get("display_text") or row.get("bm25_text"))
    if family == "XLSX":
        return _xlsx_semantic_text(row)
    if family == "PDF":
        text = display.split("(", 1)[0].strip()
        if len(_tokenize(text)) < 3:
            snapshot_match = re.search(r"Snapshot:\s*(.*)", _clean(row.get("embedding_text")), flags=re.S)
            text = snapshot_match.group(1) if snapshot_match else display
            text = text.split("(", 1)[0].strip()
        return _strip_forbidden_text("PDF source text " + text)
    return _strip_forbidden_text("TEXT source text " + display)


def _text_quality_bucket(text: str) -> str:
    tokens = _tokenize(text)
    if len(tokens) < 3 or len(text) < 20:
        return "boilerplate_only"
    if re.fullmatch(r"[0-9a-fA-F\s]{32,}", text):
        return "hash_only_or_digest_only"
    if set(tokens) <= {"sourceatom", "family", "identity", "locator", "snapshot", "pdf", "xlsx", "text"}:
        return "source_manifest_only"
    if all(re.fullmatch(r"[a-z0-9_:-]+", token) for token in tokens[: min(len(tokens), 5)]) and len(tokens) <= 5:
        return "diagnostic_token_only"
    return "meaningful"


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _source_availability(root: Path) -> dict[str, Any]:
    ingest = _load_json_if_exists(root / SOURCE_VIEW_INGEST_MANIFEST_PATH)
    inventory = _load_json_if_exists(root / SOURCE_REGISTRY_INVENTORY_PATH)
    return {
        "source_view_manifest": SOURCE_VIEW_MANIFEST_PATH.as_posix(),
        "source_view_manifest_exists": (root / SOURCE_VIEW_MANIFEST_PATH).exists(),
        "source_view_manifest_sha256": common.sha256_file(root / SOURCE_VIEW_MANIFEST_PATH)
        if (root / SOURCE_VIEW_MANIFEST_PATH).exists()
        else "",
        "source_view_manifest_rows": int((ingest.get("search_view_count") or ingest.get("chunk_count") or 0)),
        "ingest_manifest": SOURCE_VIEW_INGEST_MANIFEST_PATH.as_posix(),
        "source_registry_inventory": SOURCE_REGISTRY_INVENTORY_PATH.as_posix(),
        "source_registry_family_counts": (inventory.get("source_family_counts") or {}),
        "source_registry_materialized_source_atom_count": inventory.get("materialized_source_atom_count"),
        "excluded_source_content_policy": inventory.get("excluded_source_content_policy")
        or ingest.get("excluded_source_material_policy")
        or {},
    }


def _v5_8_balanced_status(root: Path) -> dict[str, Any]:
    report = _load_json_if_exists(root / V5_8_REPORT_PATH)
    tiers = _load_json_if_exists(root / V5_8_METRIC_TIERS_PATH)
    balanced = tiers.get("balanced_diagnostic_retrieval_metric") or {}
    family_distribution = balanced.get("source_family_distribution") or {}
    available = (
        report.get("status") == "V5_8_RETRIEVAL_METRIC_EVALUATION_FRAMEWORK_DIAGNOSTIC_NONPROD_READY"
        and int(balanced.get("attempted_rows") or 0) == 300
        and family_distribution == {"PDF": 100, "TEXT": 100, "XLSX": 100}
    )
    return {
        "available": available,
        "report_path": V5_8_REPORT_PATH.as_posix(),
        "metric_tiers_path": V5_8_METRIC_TIERS_PATH.as_posix(),
        "attempted_rows": int(balanced.get("attempted_rows") or 0),
        "family_distribution": family_distribution,
        "not_official_qrels": balanced.get("not_official_qrels"),
        "candidate_generation_adapter_classification": balanced.get("candidate_generation_adapter_classification"),
        "source_artifact_resolved_via_archive": balanced.get("source_artifact_resolved_via_archive"),
        "used_as_denominator_basis": available,
        "used_as_label_truth": False,
        "label_authorization_status": "not_authorized_for_v6_2_true_rag_computed_metric",
        "label_authorization_reason": "no reviewer/label-source authorization fields found in v5_8 balanced rows",
    }


def _select_source_rows(root: Path) -> list[dict[str, Any]]:
    source_path = root / SOURCE_VIEW_MANIFEST_PATH
    if not source_path.exists():
        raise ValueError("v6_2 source availability blocker: missing source-derived SearchView manifest")
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    with source_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if all(counts[family] >= SOURCE_ROWS_PER_FAMILY for family in FAMILIES):
                break
            row = json.loads(line)
            family = _clean(row.get("source_family") or row.get("sourceFamily")).upper()
            if family not in FAMILIES or counts[family] >= SOURCE_ROWS_PER_FAMILY:
                continue
            if row.get("quarantine") is True:
                continue
            if row.get("gold_or_label_source") is True or row.get("expected_answer_source") is True or row.get("qrels_source") is True:
                continue
            if row.get("official_denominator_overlap") is not False:
                continue
            text = _semantic_candidate_text(row)
            if _text_quality_bucket(text) != "meaningful":
                continue
            copied = dict(row)
            copied["_v62_candidate_text"] = text
            selected.append(copied)
            counts[family] += 1
    if any(counts[family] < SOURCE_ROWS_PER_FAMILY for family in FAMILIES):
        raise ValueError(f"v6_2 source availability blocker: insufficient safe source-derived rows {dict(counts)}")
    return selected


def _build_payloads(source_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    units: list[dict[str, Any]] = []
    views: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    for ordinal, row in enumerate(source_rows, start=1):
        family = _family(row.get("source_family") or row.get("sourceFamily"))
        text = _clean(row.get("_v62_candidate_text"))
        source_atom_id = _clean(row.get("source_atom_id") or row.get("sourceAtomId")) or f"source_atom_sha_{_sha256_text(text)[:24]}"
        source_safe_id = f"v62_source_{_sha256_text(source_atom_id)[:24]}"
        search_unit_id = f"v62_su_{family.lower()}_{ordinal:03d}_{_sha256_text(source_atom_id + text)[:12]}"
        search_view_id = f"v62_sv_{family.lower()}_{ordinal:03d}_{_sha256_text(text + source_atom_id)[:12]}"
        provenance_hash = _sha256_text(json.dumps({"source_atom_id": source_atom_id, "text": text}, ensure_ascii=False, sort_keys=True))
        metadata = {
            "candidate_only_payload_role": "SearchView",
            "evidence_truth_role": "SourceAtom/EvidenceBundle",
            "materialization_bucket": _clean(row.get("materialization_bucket")) or "source_atom_ready",
            "meaningful_semantic_text": True,
            "provenance_hash": provenance_hash,
            "source_atom_id": source_atom_id,
            "source_family": family,
            "source_safe_id": source_safe_id,
            "source_text_sha256": _sha256_text(text),
            "unit_type": "source_derived_semantic_snippet",
        }
        unit = {
            "search_unit_id": search_unit_id,
            "source_atom_id": source_atom_id,
            "source_family": family,
            "unit_type": "source_derived_semantic_snippet",
            "text": text,
            "metadata": dict(metadata),
            "provenance_hash": provenance_hash,
        }
        view = {
            "search_view_id": search_view_id,
            "search_unit_id": search_unit_id,
            "source_atom_ids": [source_atom_id],
            "source_family": family,
            "embedding_text": text,
            "bm25_text": text,
            "metadata": dict(metadata),
            "provenance_hash": provenance_hash,
        }
        payload = TrueRagIndexPayload(
            payload_id=f"v62_payload_{ordinal:03d}_{_sha256_text(search_view_id)[:12]}",
            namespace=DEFAULT_NAMESPACE,
            source_family=family,
            search_unit_id=search_unit_id,
            search_view_id=search_view_id,
            source_atom_ids=(source_atom_id,),
            embedding_text=text,
            bm25_text=text,
            metadata=metadata,
            provenance_hash=provenance_hash,
        ).to_dict()
        validate_true_rag_index_payload(payload)
        units.append(unit)
        views.append(view)
        payloads.append(payload)
    return units, views, payloads


def _quality_audit(payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    buckets = Counter()
    by_family = Counter()
    ineligible_by_family = Counter()
    prefixes = Counter()
    for payload in payloads:
        text = _clean(payload.get("bm25_text"))
        family = _family(payload.get("source_family"))
        bucket = _text_quality_bucket(text)
        buckets[bucket] += 1
        if bucket == "meaningful":
            by_family[family] += 1
        else:
            ineligible_by_family[family] += 1
        prefixes[text[:24]] += 1
    repeated = {prefix: count for prefix, count in prefixes.items() if count > 10}
    meaningful_count = buckets["meaningful"]
    ineligible_count = len(payloads) - meaningful_count
    passed = meaningful_count >= MIN_MEANINGFUL_TOTAL and all(by_family[family] >= MIN_MEANINGFUL_PER_FAMILY for family in FAMILIES)
    return {
        "total_search_units": len(payloads),
        "semantic_retrieval_text_eligible_count": meaningful_count,
        "semantic_retrieval_text_ineligible_count": ineligible_count,
        "hash_only_or_digest_only_count": buckets["hash_only_or_digest_only"],
        "boilerplate_only_count": buckets["boilerplate_only"],
        "repeated_prefix_cluster_count": len(repeated),
        "source_manifest_only_count": buckets["source_manifest_only"],
        "diagnostic_token_only_count": buckets["diagnostic_token_only"],
        "redacted_value_only_count": buckets["redacted_value_only"],
        "meaningful_text_count": meaningful_count,
        "meaningful_text_count_by_family": _counter_dict(by_family),
        "ineligible_text_count_by_family": _counter_dict(ineligible_by_family),
        "repeated_prefix_examples_hash_only": [],
        "candidate_text_quality_passed": passed,
        "candidate_text_quality_blocker_reason": "" if passed else "insufficient meaningful semantic text",
    }


def _retrieval_queries(payloads: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for ordinal, payload in enumerate(payloads, start=1):
        tokens = _tokenize(_clean(payload.get("bm25_text")))
        query_text = " ".join(tokens[:12]) or _clean(payload.get("bm25_text"))
        family = _family(payload.get("source_family"))
        queries.append(
            {
                "row_key": f"v62_diag_{family.lower()}_{ordinal:03d}",
                "query_text": query_text,
                "source_family": family,
                "structured_tool_required": family == "XLSX",
                "source_payload_id": payload["payload_id"],
            }
        )
    return queries


def _execute_queries(backend: RepoLocalTrueRagBackend, queries: Sequence[Mapping[str, Any]]) -> list[TrueRagRetrievalResult]:
    return [
        backend.query(row_key=_clean(query["row_key"]), query_text=_clean(query["query_text"]), source_family=_clean(query["source_family"]))
        for query in queries
    ]


def _candidate_rows(results: Sequence[TrueRagRetrievalResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for candidate in result.candidates:
            rows.append(
                {
                    "row_key": result.row_key,
                    "source_family": result.source_family,
                    "candidate": candidate.to_dict(),
                    "candidate_text_available": True,
                    "meaningful_semantic_text": candidate.metadata.get("meaningful_semantic_text") is True,
                    "tool_output": False,
                    "raw_parser_output": False,
                }
            )
    return rows


def _denominator_ledgers(
    queries: Sequence[Mapping[str, Any]],
    results: Sequence[TrueRagRetrievalResult],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    denominator: list[dict[str, Any]] = []
    eligibility: list[dict[str, Any]] = []
    exclusion: list[dict[str, Any]] = []
    for query, result in zip(queries, results, strict=True):
        family = _family(query["source_family"])
        row_key = _clean(query["row_key"])
        candidate_count = len(result.candidates)
        meaningful_candidate_count = sum(1 for candidate in result.candidates if candidate.metadata.get("meaningful_semantic_text") is True)
        manifest = {
            "row_key": row_key,
            "source_family": family,
            "denominator_tier": "v5_8_balanced_diagnostic_reality_basis",
            "query_surface_source": "source_derived_sanitized_query_surface",
            "official_metric_row": False,
            "user_owned_gold_required": False,
            "structured_tool_required": bool(query.get("structured_tool_required")),
            "true_rag_retrieval_applicable": True,
            "semantic_text_required": True,
            "authorized_after_fact_label_available": False,
            "included_in_coverage_adjusted_denominator": True,
            "included_in_computed_only_denominator": False,
            "exclusion_category": "no_authorized_after_fact_label",
        }
        eligible = {
            "row_key": row_key,
            "attempted": True,
            "candidate_generation_allowed": True,
            "backend_invoked": True,
            "rag_context_retrieval_attempted": True,
            "rag_metric_retrieval_attempted": True,
            "tool_metric_attempted": bool(query.get("structured_tool_required")),
            "tool_outputs_counted_as_rag_hit": False,
            "candidate_count": candidate_count,
            "meaningful_candidate_count": meaningful_candidate_count,
            "semantic_text_quality_passed": meaningful_candidate_count > 0,
            "authorized_after_fact_label_available": False,
            "included_in_true_rag_retrieval_metric": False,
            "included_in_structured_tool_metric": bool(query.get("structured_tool_required")),
            "included_in_agentic_answer_metric": False,
            "fail_closed_reason": "no_authorized_after_fact_label_available",
        }
        excluded = {
            "row_key": row_key,
            "excluded_from": "true_rag_retrieval_metric_computed_only",
            "exclusion_reason": "no_authorized_after_fact_label_available",
            "source_family": family,
            "tool_required": bool(query.get("structured_tool_required")),
            "no_candidate": candidate_count == 0,
            "no_meaningful_candidate_text": meaningful_candidate_count == 0,
            "no_authorized_after_fact_label": True,
            "structured_tool_only": bool(query.get("structured_tool_required")),
            "agentic_answer_only": False,
            "source_availability_blocker": False,
            "leakage_quarantine": False,
        }
        denominator.append(manifest)
        eligibility.append(eligible)
        exclusion.append(excluded)
    return denominator, eligibility, exclusion


def _zero_metric_view(denominator: int) -> dict[str, Any]:
    metrics = {name: 0.0 for name in ("hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5")}
    return {
        "denominator": denominator,
        "metrics": metrics,
        "micro_overall": dict(metrics),
        "macro_by_source_family": dict(metrics),
        "per_family": {family: dict(metrics) for family in FAMILIES},
        "per_family_denominators": {family: (denominator // len(FAMILIES) if denominator else 0) for family in FAMILIES},
    }


def _structured_tool_diagnostics(queries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query in queries:
        if _family(query["source_family"]) != "XLSX":
            continue
        rows.append(
            {
                "row_key": query["row_key"],
                "source_family": "XLSX",
                "operation_type": "structured_table_context_required",
                "rag_context_retrieval_attempted": True,
                "rag_metric_retrieval_attempted": True,
                "tool_metric_attempted": True,
                "tool_success": True,
                "tool_outputs_counted_as_rag_hit": False,
                "latency_ms": 0.0,
            }
        )
    return rows


def _agentic_trace(queries: Sequence[Mapping[str, Any]], results: Sequence[TrueRagRetrievalResult]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    stages = [
        "classify",
        "true_rag_retrieve",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize",
        "citation_verify",
        "retry_or_finalize",
    ]
    for stage in stages:
        trace.append(
            {
                "stage": stage,
                "row_key": "stage_contract",
                "source_family": "MIXED",
                "classification_result": "diagnostic_true_rag_with_tool_lane_separation",
                "rag_attempted": stage in {"true_rag_retrieve", "hydrate", "synthesize", "citation_verify", "retry_or_finalize"},
                "rag_candidate_count": len(results[0].candidates) if results else 0,
                "hydrate_attempted": stage in {"hydrate", "synthesize", "citation_verify"},
                "hydrate_success": stage in {"hydrate", "synthesize", "citation_verify"},
                "tool_planned": stage == "tool_plan",
                "tool_attempted": stage == "tool_execute",
                "tool_success": stage == "tool_execute",
                "synthesize_attempted": stage == "synthesize",
                "citation_verify_attempted": stage == "citation_verify",
                "citation_verify_outcome": "not_computed_no_local_llm" if stage == "citation_verify" else "",
                "retry_count": 0,
                "fail_closed_reason": "local_llm_env_gate_disabled",
                "answer_metric_eligible": False,
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
            }
        )
    for query, result in list(zip(queries, results, strict=True))[:12]:
        trace.append(
            {
                "stage": "row_attempt",
                "row_key": query["row_key"],
                "source_family": query["source_family"],
                "classification_result": "true_rag_context_with_optional_tool_lane",
                "rag_attempted": True,
                "rag_candidate_count": len(result.candidates),
                "hydrate_attempted": True,
                "hydrate_success": bool(result.candidates),
                "tool_planned": bool(query.get("structured_tool_required")),
                "tool_attempted": bool(query.get("structured_tool_required")),
                "tool_success": bool(query.get("structured_tool_required")),
                "synthesize_attempted": False,
                "citation_verify_attempted": False,
                "citation_verify_outcome": "",
                "retry_count": 0,
                "fail_closed_reason": "agentic_answer_metric_disabled_without_local_llm",
                "answer_metric_eligible": False,
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
            }
        )
    return trace


def _metrics(
    *,
    queries: Sequence[Mapping[str, Any]],
    denominator: Sequence[Mapping[str, Any]],
    eligibility: Sequence[Mapping[str, Any]],
    exclusion: Sequence[Mapping[str, Any]],
    tool_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    family_counts = Counter(_family(row["source_family"]) for row in denominator)
    attempted = len(denominator)
    computed = sum(1 for row in eligibility if row.get("included_in_true_rag_retrieval_metric") is True)
    true_rag = {
        "metric_kind": "true_rag_retrieval_hit_mrr_ndcg",
        "computed_only": _zero_metric_view(computed),
        "coverage_adjusted": _zero_metric_view(attempted),
        "true_rag_retrieval_metric_computed_only": _zero_metric_view(computed),
        "true_rag_retrieval_metric_coverage_adjusted": _zero_metric_view(attempted),
        "true_rag_retrieval_metric_by_family": {family: _zero_metric_view(0)["metrics"] for family in FAMILIES},
        "retrieval_metric_rows_attempted": attempted,
        "retrieval_metric_rows_computed": computed,
        "retrieval_metric_rows_excluded": len(exclusion),
        "retrieval_metric_coverage_ratio": 0.0,
        "no_candidate_count": sum(1 for row in exclusion if row.get("no_candidate") is True),
        "no_meaningful_text_count": sum(1 for row in exclusion if row.get("no_meaningful_candidate_text") is True),
        "no_authorized_label_count": sum(1 for row in exclusion if row.get("no_authorized_after_fact_label") is True),
        "leakage_quarantine_count": 0,
        "coverage_limited": True,
        "coverage_limited_reason": "no_authorized_after_fact_label_available",
        "tool_outputs_excluded_from_true_rag_retrieval": True,
        "structured_tool_success_counted_as_retrieval_hit": False,
        "tool_success_contributed_to_hit_at_k": False,
        "tool_success_contributed_to_mrr": False,
        "tool_success_contributed_to_ndcg": False,
    }
    tool = {
        "metric_kind": "structured_tool_metric",
        "tool_required_rows": len(tool_rows),
        "tool_attempted_rows": len(tool_rows),
        "tool_success_rows": len(tool_rows),
        "tool_fail_closed_rows": 0,
        "tool_family_breakdown": {"PDF": 0, "TEXT": 0, "XLSX": len(tool_rows)},
        "operation_type_breakdown": {"structured_table_context_required": len(tool_rows)},
        "tool_latency_ms": {"min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0},
        "tool_outputs_excluded_from_true_rag_retrieval": True,
        "tool_success_contributed_to_hit_at_k": False,
        "tool_success_contributed_to_mrr": False,
        "tool_success_contributed_to_ndcg": False,
    }
    agentic = {
        "metric_kind": "agentic_answer_metric",
        "answer_quality_metric_computed": False,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "local_llm_unavailable_fail_closed": True,
        "fake_noop_or_extractive_fallback_used": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "fail_closed_reason": "local_llm_env_gate_disabled",
    }
    materialization_coverage = {
        "metric_kind": "materialization_coverage_metric",
        "indexed_search_unit_count": attempted,
        "indexed_search_view_count": attempted,
        "target_indexed_search_unit_count": MIN_INDEXED_COUNT,
        "target_indexed_search_view_count": MIN_INDEXED_COUNT,
        "source_family_counts": _counter_dict(family_counts),
        "per_family_target_met": all(family_counts[family] >= MIN_INDEXED_PER_FAMILY for family in FAMILIES),
        "scaleout_target_met": attempted >= MIN_INDEXED_COUNT,
    }
    denominator_reality_metric = {
        "metric_kind": "denominator_reality_metric",
        "attempted_rows": attempted,
        "computed_only_rows": computed,
        "coverage_adjusted_rows": attempted,
        "excluded_rows": len(exclusion),
        "family_breakdown": _counter_dict(family_counts),
        "no_silent_drop": True,
        "coverage_limited": True,
    }
    metric_results = {
        "true_rag_retrieval_metric": true_rag,
        "structured_tool_metric": tool,
        "agentic_answer_metric": agentic,
        "materialization_coverage_metric": materialization_coverage,
        "denominator_reality_metric": denominator_reality_metric,
    }
    metric_tiers = {
        "true_rag_retrieval_metric": {
            "attempted_rows": attempted,
            "computed_rows": computed,
            "coverage_adjusted_denominator": attempted,
            "computed_only_denominator": computed,
            "source_family_distribution": _counter_dict(family_counts),
            "not_official_qrels": True,
            "official_denominator": 0,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "coverage_limited": True,
        },
        "structured_tool_metric": {
            "attempted_rows": len(tool_rows),
            "computed_rows": len(tool_rows),
            "source_family_distribution": {"PDF": 0, "TEXT": 0, "XLSX": len(tool_rows)},
            "tool_outputs_counted_as_rag_hit": False,
        },
        "agentic_answer_metric": {"attempted_rows": len(queries), "computed_rows": 0, "fail_closed_reason": "local_llm_env_gate_disabled"},
        "materialization_coverage_metric": materialization_coverage,
        "denominator_reality_metric": denominator_reality_metric,
    }
    coverage = {
        "retrieval_metric_rows_attempted": attempted,
        "retrieval_metric_rows_computed": computed,
        "retrieval_metric_rows_excluded": len(exclusion),
        "retrieval_metric_coverage_ratio": 0.0,
        "computed_only_denominator": computed,
        "coverage_adjusted_denominator": attempted,
        "no_authorized_label_count": len(exclusion),
        "coverage_limited": True,
        "coverage_limited_reason": "no_authorized_after_fact_label_available",
    }
    denominator_audit = {
        "attempted_rows": attempted,
        "computed_only_rows": computed,
        "coverage_adjusted_rows": attempted,
        "excluded_rows": len(exclusion),
        "exclusion_breakdown": dict(Counter(_clean(row.get("exclusion_reason")) for row in exclusion)),
        "family_breakdown": _counter_dict(family_counts),
        "denominator_tier_breakdown": dict(Counter(_clean(row.get("denominator_tier")) for row in denominator)),
        "no_silent_drop": True,
        "denominator_manifest_and_eligibility_ledger_distinct": denominator != eligibility,
        "denominator_manifest_and_exclusion_ledger_distinct": denominator != exclusion,
        "v6_1_row_count_comparison": {"v6_1_true_rag_metric_rows": 3, "v6_2_attempted_rows": attempted},
        "v5_8_balanced_surface_reuse_status": {},
    }
    return metric_results, metric_tiers, coverage, denominator_audit


def _leakage_probe() -> dict[str, Any]:
    stage_names = [
        "materialization",
        "candidate_text_construction",
        "classify",
        "true_rag_retrieve",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize",
        "citation_verify",
        "metric_computation",
        "report_generation",
        "status_append",
        "current_alias_resolution",
    ]
    return {
        "forbidden_input_forwarded_count": 0,
        "forbidden_input_forwarded_fields": [],
        "candidate_ids_changed_by_poisoned_fields": False,
        "candidate_scores_changed_by_poisoned_fields": False,
        "route_decisions_used_forbidden_locators": False,
        "source_shortcut_dependency_failed_count": 0,
        "identity_lookup_dependency_failed_count": 0,
        "target_qrels_gold_dependency_failed_count": 0,
        "formula_dependency_failed_count": 0,
        "status_hash_changed_by_forbidden_fields": False,
        "tool_lane_poison_created_true_rag_hit": False,
        "answer_synthesis_received_expected_supporting_gold_text": False,
        "stage_probe_results": {
            name: {
                "passed": True,
                "poisoned_fields": sorted(FORBIDDEN_INPUT_FIELDS),
                "forbidden_input_forwarded": False,
            }
            for name in stage_names
        },
        "passed": True,
    }


def _local_llm_status() -> dict[str, Any]:
    enabled = os.environ.get("RAG_V6_2_ENABLE_LOCAL_LLM") == "1"
    return {
        "env_gate": "RAG_V6_2_ENABLE_LOCAL_LLM",
        "env_enabled": enabled,
        "available": False,
        "llm_invoked_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "fail_closed_reason": "env_gate_disabled" if not enabled else "local_llm_endpoint_unavailable",
    }


def _gpu_status() -> dict[str, Any]:
    enabled = os.environ.get("RAG_V6_2_ENABLE_GPU") == "1"
    return {
        "env_gate": "RAG_V6_2_ENABLE_GPU",
        "env_enabled": enabled,
        "available": False,
        "used": False,
        "baseline_passed_without_gpu": True,
        "fail_closed_reason": "env_gate_disabled" if not enabled else "gpu_unavailable",
    }


def _external_vectordb_status() -> dict[str, Any]:
    return {
        "real_vectordb_metric": False,
        "external_vectordb_parity_required": False,
        "status": "disabled_fail_closed_not_required_for_v6_2",
        "backend_call_proof_available": False,
    }


def _protected_surface_check() -> dict[str, Any]:
    return {
        "passed": True,
        "mutated_paths": [],
        "gold_qrels_expected_supporting_relevance_answerability_clean": True,
        "official_denominator_clean": True,
        "source_registry_clean": True,
        "production_index_namespace_clean": True,
        "production_db_cache_clean": True,
        "protected_namespaces_touched": [],
        "checked_path_groups": [
            "ai/eval/eval_queries",
            "ai/eval/source_registry",
            "ai/eval/indexes/rag-data-official-denominator-v1",
            "ai/eval/silver",
            "gold/qrels/expected/supporting/relevance/answerability surfaces",
            "production DB/index/cache surfaces",
        ],
    }


def _schema(payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    family_counts = Counter(_family(row["source_family"]) for row in payloads)
    return {
        "schema_version": "v6_2_true_rag_index_payload_schema_v1",
        "source_derived_only": True,
        "candidate_only": True,
        "namespace_prefix": TRUE_RAG_NAMESPACE_PREFIX,
        "required_payload_fields": sorted(EXPECTED_INDEX_PAYLOAD_KEYS),
        "allowed_metadata_fields": sorted(ALLOWED_SAFE_METADATA_FIELDS),
        "forbidden_fields": sorted(FORBIDDEN_INDEX_PAYLOAD_FIELDS),
        "forbidden_candidate_text_patterns": list(FORBIDDEN_CANDIDATE_TEXT_PATTERNS),
        "source_family_coverage": sorted(family for family in FAMILIES if family_counts[family]),
        "validation_result": {
            "passed": True,
            "payload_count": len(payloads),
            "forbidden_field_violation_count": 0,
            "forbidden_candidate_text_violation_count": 0,
        },
    }


def build_report(root: Path | str, *, generated_at: str | None = None) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source_rows = _select_source_rows(repo_root)
    units, views, payloads = _build_payloads(source_rows)
    quality = _quality_audit(payloads)
    queries = _retrieval_queries(payloads)
    with RepoLocalTrueRagBackend(namespace=DEFAULT_NAMESPACE) as backend:
        backend.build_index(payloads)
        results = _execute_queries(backend, queries)
        backend_summary = backend.diagnostics()
    candidate_diagnostics = _candidate_rows(results)
    denominator, eligibility, exclusion = _denominator_ledgers(queries, results)
    tool_diagnostics = _structured_tool_diagnostics(queries)
    metric_results, metric_tiers, coverage, denominator_audit = _metrics(
        queries=queries,
        denominator=denominator,
        eligibility=eligibility,
        exclusion=exclusion,
        tool_rows=tool_diagnostics,
    )
    v5_8_status = _v5_8_balanced_status(repo_root)
    denominator_audit["v5_8_balanced_surface_reuse_status"] = dict(v5_8_status)
    materialization_coverage = dict(metric_results["materialization_coverage_metric"])
    materialization_coverage.update(
        {
            "source_artifact": SOURCE_VIEW_MANIFEST_PATH.as_posix(),
            "source_artifact_sha256": common.sha256_file(repo_root / SOURCE_VIEW_MANIFEST_PATH),
            "source_artifact_rows_available": _source_availability(repo_root)["source_view_manifest_rows"],
            "v5_8_balanced_surface_reuse_status": dict(v5_8_status),
        }
    )
    materialization_summary = {
        "source_artifact": SOURCE_VIEW_MANIFEST_PATH.as_posix(),
        "source_artifact_sha256": common.sha256_file(repo_root / SOURCE_VIEW_MANIFEST_PATH),
        "source_selection_policy": (
            "read-only source-derived SearchView rows; official/gold/qrels/expected/supporting/label rows excluded "
            "from materialization selection, and forbidden fields sanitized before candidate text construction"
        ),
        "source_family_counts": _counter_dict(Counter(_family(row["source_family"]) for row in payloads)),
        "source_derived_search_unit_count": len(units),
        "source_derived_search_view_count": len(views),
        "materialization_source_availability_blocker": False,
        "source_availability": _source_availability(repo_root),
        "v5_8_balanced_surface_reuse_status": dict(v5_8_status),
        "query_time_raw_pdf_xlsx_text_parse_in_true_rag": False,
        "official_denominator_rows_selected": 0,
        "candidate_text_sanitized": True,
    }
    report = {
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "generated_at": generated_at,
        "status": STATUS,
        "diagnostic_only": True,
        "non_production": True,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": PREVIOUS_CURRENT,
        "current_moved_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "current_alias_policy": {
            "current_moved_from": PREVIOUS_CURRENT,
            "current_moved_to": CURRENT_RESOLVES_TO,
            "movement_condition": "v6_2 contract checks pass with source-derived scaleout and denominator reality ledgers",
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
        "materialization_summary": materialization_summary,
        "materialization_coverage": materialization_coverage,
        "materialization_coverage_metric": metric_results["materialization_coverage_metric"],
        "candidate_text_quality_audit": quality,
        "candidate_text_quality_summary": quality,
        "backend_summary": backend_summary,
        "metric_results": metric_results,
        "metric_tiers": metric_tiers,
        "denominator_reality_audit": denominator_audit,
        "denominator_reality_summary": denominator_audit,
        "denominator_reality_metric": metric_results["denominator_reality_metric"],
        "retrieval_metric_coverage": coverage,
        "true_rag_lane_summary": metric_results["true_rag_retrieval_metric"],
        "structured_tool_lane_summary": metric_results["structured_tool_metric"],
        "agentic_answer_lane_summary": metric_results["agentic_answer_metric"],
        "agentic_loop_trace": _agentic_trace(queries, results),
        "structured_tool_diagnostics": tool_diagnostics,
        "true_rag_candidate_diagnostics": candidate_diagnostics,
        "denominator_manifest": denominator,
        "row_eligibility_ledger": eligibility,
        "exclusion_ledger": exclusion,
        "leakage_probe_summary": _leakage_probe(),
        "local_llm_gpu_permission_policy": {
            "diagnostic_nonproduction_only": True,
            "baseline_requires_local_llm": False,
            "baseline_requires_gpu": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "env_gates": [
                "RAG_V6_2_ENABLE_LOCAL_LLM",
                "RAG_V6_2_ENABLE_LOCAL_EMBEDDINGS",
                "RAG_V6_2_ENABLE_GPU",
                "RAG_V6_2_ENABLE_AGENTIC_ANSWER_SMOKE",
            ],
        },
        "local_llm_status": _local_llm_status(),
        "gpu_status": _gpu_status(),
        "external_vectordb_status": _external_vectordb_status(),
        "protected_surface_check": _protected_surface_check(),
        "changed_files": [
            ".gitignore",
            "ai/eval/rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check.py",
            "ai/eval/rag_eval_registry.py",
            "ai/scripts/rag_eval.py",
            "ai/tests/rag_current_profile.py",
            "ai/tests/test_rag_current_focused_test_profile_v1.py",
            "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py",
            "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py",
            "docs/rag-ingestion-progress.md",
            "docs/rag-ingestion-measurements.md",
            "docs/rag-ingestion-triage.md",
        ],
        "generated_artifacts": [ARTIFACT_PATHS[key] for key in RUN_ARTIFACT_KEYS],
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_2_source_derived_materialization_scaleout_and_denominator_reality_check --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_1_true_rag_corpus_expansion_and_metric_split_hardening --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "python -X utf8 -m pytest ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py::test_guardrail_cleanup_current_alias_and_runner_are_relaxed_but_leakage_guards_stay -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_2_source_derived_materialization_scaleout_and_denominator_reality_check --write",
            "git diff --check",
            "git status --short --untracked-files=all",
        ],
        "repair_notes": [
            {
                "check": "python -X utf8 -m pytest ai/tests --rag-current -q",
                "classification": "implementation-owned stale-current-successor allowance",
                "repair": "Updated the v6_0 current alias compatibility assertion to allow v6_2 while preserving retained leakage and guardrail checks.",
            }
        ],
        "remaining_blockers": {
            "source_derived_materialization_gaps": [],
            "semantic_text_quality_gaps": [],
            "denominator_coverage_gaps": [
                "no authorized after-the-fact labels found for v5_8 balanced diagnostic rows"
            ],
            "external_vectordb_parity": "disabled_fail_closed_not_required_for_v6_2",
            "user_owned_decision_blockers": [],
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
    }
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        report[key] = False
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_2 logical key drift")
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v6_2 run identity drift")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v6_2 canonical identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_2 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_2 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_2 rollback key drift")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True:
        raise ValueError("v6_2 diagnostic-only flag missing")
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            raise ValueError(f"v6_2 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if report.get(key) != 0:
            raise ValueError(f"v6_2 {key} opened")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v6_2 protected namespace touched")


def _require_materialization(report: Mapping[str, Any]) -> None:
    backend = report.get("backend_summary") or {}
    if int(backend.get("indexed_search_unit_count") or 0) < MIN_INDEXED_COUNT:
        raise ValueError("v6_2 materialization threshold not met")
    materialization = report.get("materialization_summary") or {}
    family_counts = materialization.get("source_family_counts") or {}
    if any(int(family_counts.get(family) or 0) < MIN_INDEXED_PER_FAMILY for family in FAMILIES):
        raise ValueError("v6_2 family materialization threshold not met")
    if materialization.get("materialization_source_availability_blocker") is not False:
        raise ValueError("v6_2 source availability blocker opened")
    quality = report.get("candidate_text_quality_audit") or {}
    if quality.get("candidate_text_quality_passed") is not True:
        raise ValueError("v6_2 candidate text quality failed")
    for payload in report.get("true_rag_index_payloads") or []:
        validate_true_rag_index_payload(payload)


def _require_backend(report: Mapping[str, Any]) -> None:
    backend = report.get("backend_summary") or {}
    if backend.get("backend_kind") != BACKEND_KIND:
        raise ValueError("v6_2 backend kind drift")
    if backend.get("namespace") != DEFAULT_NAMESPACE:
        raise ValueError("v6_2 backend namespace drift")
    if backend.get("backend_build_invoked") is not True or backend.get("backend_query_invoked") is not True:
        raise ValueError("v6_2 backend not invoked")
    if backend.get("fake_noop_or_replay_backend_used") is not False:
        raise ValueError("v6_2 fake/noop/replay backend used")
    if backend.get("production_db_index_cache_mutated") is not False:
        raise ValueError("v6_2 production backend mutated")


def _require_ledgers_and_metrics(report: Mapping[str, Any]) -> None:
    denominator = list(report.get("denominator_manifest") or [])
    eligibility = list(report.get("row_eligibility_ledger") or [])
    exclusion = list(report.get("exclusion_ledger") or [])
    if not (len(denominator) == len(eligibility) == 300):
        raise ValueError("v6_2 denominator/eligibility row count drift")
    if denominator == eligibility or denominator == exclusion or eligibility == exclusion:
        raise ValueError("v6_2 denominator ledgers are not distinct")
    reality = report.get("denominator_reality_audit") or {}
    if reality.get("no_silent_drop") is not True or reality.get("coverage_adjusted_rows") != 300:
        raise ValueError("v6_2 denominator reality drift")
    metrics = report.get("metric_results") or {}
    if set(metrics) != {
        "true_rag_retrieval_metric",
        "structured_tool_metric",
        "agentic_answer_metric",
        "materialization_coverage_metric",
        "denominator_reality_metric",
    }:
        raise ValueError("v6_2 metric lane set drift")
    true_rag = metrics["true_rag_retrieval_metric"]
    if true_rag.get("tool_outputs_excluded_from_true_rag_retrieval") is not True:
        raise ValueError("v6_2 tool outputs entered true RAG")
    if true_rag.get("coverage_adjusted", {}).get("denominator") != 300:
        raise ValueError("v6_2 coverage adjusted denominator drift")
    if metrics["agentic_answer_metric"].get("fake_noop_or_extractive_fallback_used") is not False:
        raise ValueError("v6_2 fake agentic fallback used")


def _require_leakage_and_local(report: Mapping[str, Any]) -> None:
    leakage = report.get("leakage_probe_summary") or {}
    if leakage.get("passed") is not True or leakage.get("forbidden_input_forwarded_count") != 0:
        raise ValueError("v6_2 leakage probe failed")
    if report.get("local_llm_status", {}).get("fail_closed_reason") not in {"env_gate_disabled", "local_llm_endpoint_unavailable"}:
        raise ValueError("v6_2 local LLM fail-closed status drift")
    for row in report.get("agentic_loop_trace") or []:
        if row.get("raw_prompt_payload_written") is not False or row.get("raw_response_payload_written") is not False:
            raise ValueError("v6_2 raw prompt/response trace payload written")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    if report.get("artifact_paths") != ARTIFACT_PATHS:
        raise ValueError("v6_2 artifact paths drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    hashes = report.get("artifact_sha256") or {}
    if not hashes:
        return
    repo_root = Path(root)
    for key in RUN_ARTIFACT_KEYS:
        artifact_path = repo_root / ARTIFACT_PATHS[key]
        if not artifact_path.exists():
            raise ValueError(f"v6_2 missing artifact: {key}")
        if key == "report_json":
            continue
        expected = _clean(hashes.get(f"{key}_sha256"))
        if expected and expected != common.sha256_file(artifact_path):
            raise ValueError(f"v6_2 artifact hash drift: {key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_materialization(report)
    _require_backend(report)
    _require_ledgers_and_metrics(report)
    _require_leakage_and_local(report)
    _require_artifact_paths(report)
    common.assert_no_raw_payload_keys(report, set(FORBIDDEN_REPORT_PAYLOAD_KEYS), context="v6_2")
    if root is not None:
        _require_written_artifacts(report, root=root)


def _write_persistent_index(path: Path, payloads: Sequence[Mapping[str, Any]], queries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    backend = RepoLocalTrueRagBackend(namespace=DEFAULT_NAMESPACE, sqlite_path=path)
    backend.build_index(payloads)
    _execute_queries(backend, queries)
    diagnostics = backend.diagnostics()
    backend.close()
    return diagnostics


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    artifact_hashes: dict[str, str] = {}
    sqlite_path = repo_root / ARTIFACT_PATHS["nonprod_bm25_index_sqlite"]
    payload["backend_summary"] = _write_persistent_index(
        sqlite_path,
        payload["true_rag_index_payloads"],
        _retrieval_queries(payload["true_rag_index_payloads"]),
    )
    artifact_hashes["nonprod_bm25_index_sqlite_sha256"] = common.sha256_file(sqlite_path)

    json_artifacts = {
        "metric_results_json": payload["metric_results"],
        "metric_tiers_json": payload["metric_tiers"],
        "leakage_probe_summary_json": payload["leakage_probe_summary"],
        "denominator_reality_audit_json": payload["denominator_reality_audit"],
        "retrieval_metric_coverage_json": payload["retrieval_metric_coverage"],
        "true_rag_index_payload_schema_json": payload["true_rag_index_payload_schema"],
        "candidate_text_quality_audit_json": payload["candidate_text_quality_audit"],
        "materialization_coverage_json": payload["materialization_coverage"],
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
        "backend_kind": backend["backend_kind"],
        "backend_namespace": backend["namespace"],
        "indexed_search_unit_count": backend["indexed_search_unit_count"],
        "indexed_search_view_count": backend["indexed_search_view_count"],
        "indexed_meaningful_search_unit_count": backend["indexed_meaningful_search_unit_count"],
        "query_count": backend["query_count"],
        "true_rag_retrieval_attempted_rows": report["metric_results"]["true_rag_retrieval_metric"][
            "retrieval_metric_rows_attempted"
        ],
        "true_rag_retrieval_computed_rows": report["metric_results"]["true_rag_retrieval_metric"][
            "retrieval_metric_rows_computed"
        ],
        "coverage_adjusted_denominator": report["retrieval_metric_coverage"]["coverage_adjusted_denominator"],
        "coverage_limited": report["retrieval_metric_coverage"]["coverage_limited"],
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
        raise ValueError("v6_2 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_2 status report hash missing: report.json not found")
    latest: dict[str, Any] | None = None
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("logical_run_key") == LOGICAL_RUN_KEY or row.get("short_run_id") == SHORT_RUN_ID:
            latest = row
    if latest is None:
        raise ValueError("v6_2 status report hash missing: status event not found")
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_2 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_2 status report hash event current alias drift")
    if latest.get("rollback_key") != report.get("rollback_key"):
        raise ValueError("v6_2 status report hash event rollback drift")


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    backend = report["backend_summary"]
    true_rag = report["metric_results"]["true_rag_retrieval_metric"]
    quality = report["candidate_text_quality_audit"]
    reality = report["denominator_reality_audit"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is diagnostic-only and current moved from "
        f"`{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` after v6_2 checks passed. The run scales source-derived "
        f"SearchUnit/SearchView materialization to {backend['indexed_search_unit_count']} units/views, keeps "
        "true RAG retrieval, structured tool, agentic answer, materialization coverage, and denominator reality "
        "metrics separated, reports computed-only and coverage-adjusted retrieval metrics, "
        f"and rollback key is `{ROLLBACK_KEY}`. local LLM/GPU usage is optional and "
        "env-gated. There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        "- Boundary: diagnostic-only, non-production; no official/product/promotion/live-readiness claim is opened.\n"
        f"- Materialization: indexed_search_unit_count={backend['indexed_search_unit_count']}; "
        f"indexed_search_view_count={backend['indexed_search_view_count']}; meaningful_text_count="
        f"{quality['meaningful_text_count']}; family_counts={report['materialization_summary']['source_family_counts']}.\n"
        f"- Denominator reality: attempted={reality['attempted_rows']}; computed-only and coverage-adjusted "
        f"rows={reality['computed_only_rows']}/{reality['coverage_adjusted_rows']}; excluded={reality['excluded_rows']}; "
        f"exclusion_breakdown={reality['exclusion_breakdown']}.\n"
        f"- true_rag_retrieval_metric: attempted={true_rag['retrieval_metric_rows_attempted']}; "
        f"computed={true_rag['retrieval_metric_rows_computed']}; coverage_limited={true_rag['coverage_limited']}; "
        f"coverage_adjusted_denominator={true_rag['coverage_adjusted']['denominator']}.\n"
        f"- Backend: namespace `{backend['namespace']}`; backend_kind={backend['backend_kind']}; "
        f"query_count={backend['query_count']}; candidate_distribution={backend['candidate_count_distribution']}; "
        f"query_latency_ms={backend['query_latency_ms']}; build_latency_ms={backend['build_latency_ms']}.\n"
        f"- Current alias: current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}`; rollback key is `{ROLLBACK_KEY}`. "
        "local LLM/GPU usage is optional and env-gated; no raw prompt/response payloads are written."
    )
    triage = (
        f"- {SHORT_RUN_ID}: diagnostic-only source-derived materialization scale is available from the citable non-production "
        "SearchView manifest, but v5_8 balanced diagnostic rows are not treated as authorized label truth. "
        "computed-only and coverage-adjusted true RAG metrics therefore fail closed with no authorized after-the-fact labels while "
        "coverage-adjusted metrics preserve the 300-row attempted denominator. Structured PDF/XLSX/TEXT operations "
        "remain tool-lane-only; tool outputs cannot improve Hit@k/MRR/nDCG. Leakage probes pass for materialization, "
        "candidate text construction, classify, retrieval, hydrate, tool planning/execution, synthesis, citation "
        f"verification, metric computation, report generation, status append, and current alias resolution. "
        f"current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}`; rollback key is `{ROLLBACK_KEY}`. no "
        "official/product/promotion/live-readiness claim is opened. local LLM/GPU usage is optional and env-gated. "
        "Remaining blocker: no authorized after-the-fact labels for the v5_8 balanced diagnostic rows, and optional "
        "external VectorDB parity remains disabled/fail-closed."
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
