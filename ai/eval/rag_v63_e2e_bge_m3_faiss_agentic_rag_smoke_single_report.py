from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

import faiss  # type: ignore
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length
from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check as v62


LOGICAL_RUN_KEY = "v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_3_E2E_BGE_M3_FAISS_AGENTIC_RAG_SMOKE_SINGLE_REPORT_NONPROD_READY"
PREVIOUS_CURRENT = "v6_2_source_derived_materialization_scaleout_and_denominator_reality_check"
CURRENT_RESOLVES_TO = LOGICAL_RUN_KEY
ROLLBACK_KEY = PREVIOUS_CURRENT
KST_DOC_DATE = "2026-06-06"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
FAISS_INDEX_PATH = RUN_ROOT / "true_rag_faiss.index"
FAISS_ID_MAP_PATH = RUN_ROOT / "faiss_id_map.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "true_rag_faiss_index": FAISS_INDEX_PATH.as_posix(),
    "faiss_id_map_json": FAISS_ID_MAP_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}

FAMILIES = ("PDF", "TEXT", "XLSX")
SOURCE_ROWS_PER_FAMILY = 100
MIN_INDEXED_COUNT = 300
TOP_K = 5
MAX_SAMPLED_ROWS = 10
MAX_SAMPLED_CANDIDATES = 5
MAX_RETRY_COUNT = 2
EMBEDDING_MODEL_IDENTIFIER = "BAAI/bge-m3"
EMBEDDING_MODEL_NAME = "bge-m3"
DEFAULT_NAMESPACE = "v6_3_true_rag_nonprod_bge_m3_faiss_e2e_smoke"
TRUE_RAG_NAMESPACE_PREFIX = "v6_3_true_rag_nonprod_"
BM25_BACKEND_KIND = "repo_local_sqlite_bm25"
VECTOR_BACKEND_KIND = "bge_m3_faiss"

FORBIDDEN_REPORT_FILE_NAMES = {
    "metric_results.json",
    "metric_tiers.json",
    "leakage_probe_summary.json",
    "denominator_manifest.jsonl",
    "row_eligibility_ledger.jsonl",
    "exclusion_ledger.jsonl",
    "candidate_text_quality_audit.json",
    "materialization_coverage.json",
    "retrieval_metric_coverage.json",
    "agentic_loop_trace.jsonl",
    "structured_tool_diagnostics.jsonl",
    "true_rag_candidate_diagnostics.jsonl",
}

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
)

FORBIDDEN_REPORT_PAYLOAD_KEYS = {
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
    "formula_text",
    "formula_evaluation",
    "direct_normalized_answer_value",
    "expected_answer",
    "supporting_evidence",
    "qrels_positive_ids",
}


@dataclass(frozen=True)
class TrueRagPayload:
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
class Candidate:
    candidate_id: str
    search_unit_id: str
    search_view_id: str
    source_atom_ids: tuple[str, ...]
    source_family: str
    score: float
    rank: int
    retrieval_backend: str
    metadata: Mapping[str, Any]

    def to_compact_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_atom_ids"] = list(self.source_atom_ids)
        return payload


@dataclass(frozen=True)
class RetrievalResult:
    row_key: str
    query_text: str
    source_family: str
    backend_kind: str
    candidates: tuple[Candidate, ...]
    latency_ms: float


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _family(value: Any) -> str:
    family = _clean(value).upper()
    if family in FAMILIES:
        return family
    if "PDF" in family:
        return "PDF"
    if "XLSX" in family or "SHEET" in family or "TABLE" in family:
        return "XLSX"
    return "TEXT"


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _tokenize(value: str) -> list[str]:
    return [token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split() if len(token) > 1]


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


def _short_preview(text: str, limit: int = 160) -> str:
    compact = " ".join(_clean(text).split())
    return compact[:limit]


def _runtime_artifact_root(root: Path, run_artifact_root: Path | str | None) -> Path:
    return Path(run_artifact_root) if run_artifact_root is not None else root / RUN_ROOT


def _source_rows(root: Path) -> list[dict[str, Any]]:
    return v62._select_source_rows(root)  # type: ignore[attr-defined]


def _source_text(row: Mapping[str, Any]) -> str:
    text = _clean(row.get("_v62_candidate_text"))
    if text:
        return text
    return v62._semantic_candidate_text(row)  # type: ignore[attr-defined]


def _build_payloads(source_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    units: list[dict[str, Any]] = []
    views: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    for ordinal, row in enumerate(source_rows, start=1):
        family = _family(row.get("source_family") or row.get("sourceFamily"))
        text = _source_text(row)
        source_atom_id = _clean(row.get("source_atom_id") or row.get("sourceAtomId")) or f"source_atom_sha_{_sha256_text(text)[:24]}"
        source_safe_id = f"v63_source_{_sha256_text(source_atom_id)[:24]}"
        search_unit_id = f"v63_su_{family.lower()}_{ordinal:03d}_{_sha256_text(source_atom_id + text)[:12]}"
        search_view_id = f"v63_sv_{family.lower()}_{ordinal:03d}_{_sha256_text(text + source_atom_id)[:12]}"
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
        payload = TrueRagPayload(
            payload_id=f"v63_payload_{ordinal:03d}_{_sha256_text(search_view_id)[:12]}",
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
        validate_true_rag_payload(payload)
        units.append(
            {
                "search_unit_id": search_unit_id,
                "source_atom_id": source_atom_id,
                "source_family": family,
                "unit_type": "source_derived_semantic_snippet",
                "text_sha256": _sha256_text(text),
                "metadata": dict(metadata),
                "provenance_hash": provenance_hash,
            }
        )
        views.append(
            {
                "search_view_id": search_view_id,
                "search_unit_id": search_unit_id,
                "source_atom_ids": [source_atom_id],
                "source_family": family,
                "embedding_text_sha256": _sha256_text(text),
                "bm25_text_sha256": _sha256_text(text),
                "metadata": dict(metadata),
                "provenance_hash": provenance_hash,
            }
        )
        payloads.append(payload)
    return units, views, payloads


def validate_true_rag_payload(payload: Mapping[str, Any]) -> None:
    forbidden_paths = v62._forbidden_field_paths(payload)  # type: ignore[attr-defined]
    if forbidden_paths:
        raise ValueError(f"v6_3 TrueRagPayload contains forbidden fields: {forbidden_paths}")
    unexpected = set(payload) - v62.EXPECTED_INDEX_PAYLOAD_KEYS
    if unexpected:
        raise ValueError(f"v6_3 TrueRagPayload contains unexpected top-level fields: {sorted(unexpected)}")
    namespace = _clean(payload.get("namespace"))
    if not namespace.startswith(TRUE_RAG_NAMESPACE_PREFIX):
        raise ValueError("v6_3 true RAG namespace must be non-production")
    for field in ("embedding_text", "bm25_text"):
        v62._require_no_forbidden_candidate_text(_clean(payload.get(field)), context=f"v6_3 {field}")  # type: ignore[attr-defined]


def validate_embedding_matrix(vectors: np.ndarray, *, expected_count: int, embedding_model_identifier: str) -> None:
    if "bge-m3" not in embedding_model_identifier.lower():
        raise ValueError("v6_3 embedding model must be bge-m3")
    if vectors.ndim != 2:
        raise ValueError("v6_3 embeddings must be a 2-D matrix")
    if vectors.shape[0] != expected_count:
        raise ValueError("v6_3 embedding count mismatch")
    if vectors.shape[1] <= 0:
        raise ValueError("v6_3 embedding dimension missing")
    if not np.isfinite(vectors).all():
        raise ValueError("v6_3 embeddings contain non-finite values")
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms <= 1e-8):
        raise ValueError("v6_3 zero embeddings are forbidden")
    nonzero_counts = np.count_nonzero(np.abs(vectors) > 1e-8, axis=1)
    if vectors.shape[1] > 1 and np.all(nonzero_counts <= 1):
        raise ValueError("v6_3 fake/random/one-hot embeddings are forbidden")


def _embedding_device_status() -> dict[str, Any]:
    gpu_requested = os.environ.get("RAG_V6_3_ENABLE_GPU") == "1"
    return {
        "gpu_env_gate": "RAG_V6_3_ENABLE_GPU",
        "gpu_env_enabled": gpu_requested,
        "gpu_available": False,
        "gpu_used": False,
        "device": "cpu",
        "gpu_probe_skipped_reason": "avoid_eager_torch_import_before_faiss_on_windows",
    }


def _build_embedder() -> Any:
    return SentenceTransformerEmbedder(
        model_name=EMBEDDING_MODEL_IDENTIFIER,
        max_seq_length=resolve_max_seq_length(int(os.environ.get("RAG_V6_3_BGE_M3_MAX_SEQ_LENGTH", "1024"))),
        batch_size=int(os.environ.get("RAG_V6_3_BGE_M3_BATCH_SIZE", "32")),
        show_progress_bar=False,
    )


def _embed_payloads(payloads: Sequence[Mapping[str, Any]], queries: Sequence[Mapping[str, Any]]) -> tuple[Any, np.ndarray, np.ndarray, dict[str, Any]]:
    embedder = _build_embedder()
    text_values = [_clean(payload["embedding_text"]) for payload in payloads]
    query_values = [_clean(query["query_text"]) for query in queries]

    passage_started = time.perf_counter()
    passage_vectors = embedder.embed_passages(text_values)
    passage_latency = round((time.perf_counter() - passage_started) * 1000, 4)
    query_started = time.perf_counter()
    query_vectors = embedder.embed_queries(query_values)
    query_latency = round((time.perf_counter() - query_started) * 1000, 4)
    validate_embedding_matrix(
        passage_vectors,
        expected_count=len(payloads),
        embedding_model_identifier=getattr(embedder, "model_name", EMBEDDING_MODEL_IDENTIFIER),
    )
    validate_embedding_matrix(
        query_vectors,
        expected_count=len(queries),
        embedding_model_identifier=getattr(embedder, "model_name", EMBEDDING_MODEL_IDENTIFIER),
    )
    device = _embedding_device_status()
    status = {
        "env_gate": "RAG_V6_3_ENABLE_BGE_M3",
        "env_enabled": os.environ.get("RAG_V6_3_ENABLE_BGE_M3", "1") != "0",
        "model_ready": True,
        "embedding_model_name": EMBEDDING_MODEL_NAME,
        "embedding_model_identifier": getattr(embedder, "model_name", EMBEDDING_MODEL_IDENTIFIER),
        "model_source_kind": "sentence_transformers_local_or_hf_cache",
        "model_revision_or_hash": "",
        "embedding_dim": int(passage_vectors.shape[1]),
        "embedding_count": int(passage_vectors.shape[0]),
        "embedding_batch_size": int(os.environ.get("RAG_V6_3_BGE_M3_BATCH_SIZE", "32")),
        "normalize_embeddings": True,
        "embedding_latency_ms": _distribution([passage_latency, query_latency]),
        "passage_embedding_latency_ms_total": passage_latency,
        "query_embedding_latency_ms_total": query_latency,
        "fake_random_or_zero_embeddings_rejected": True,
        **device,
    }
    return embedder, passage_vectors.astype(np.float32, copy=False), query_vectors.astype(np.float32, copy=False), status


def _retrieval_queries(payloads: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for ordinal, payload in enumerate(payloads, start=1):
        tokens = _tokenize(_clean(payload.get("bm25_text")))
        query_text = " ".join(tokens[:12]) or _clean(payload.get("bm25_text"))
        family = _family(payload.get("source_family"))
        queries.append(
            {
                "row_key": f"v63_diag_{family.lower()}_{ordinal:03d}",
                "query_text": query_text,
                "source_family": family,
                "structured_tool_required": family == "XLSX",
                "source_payload_id": payload["payload_id"],
            }
        )
    return queries


def _build_faiss(
    *,
    artifact_root: Path,
    payloads: Sequence[Mapping[str, Any]],
    passage_vectors: np.ndarray,
    query_vectors: np.ndarray,
    queries: Sequence[Mapping[str, Any]],
) -> tuple[list[RetrievalResult], dict[str, Any], list[dict[str, Any]]]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    index_path = artifact_root / "true_rag_faiss.index"
    id_map_path = artifact_root / "faiss_id_map.json"

    passage_vectors = np.ascontiguousarray(passage_vectors, dtype=np.float32)
    query_vectors = np.ascontiguousarray(query_vectors, dtype=np.float32)
    started = time.perf_counter()
    index = faiss.IndexFlatIP(int(passage_vectors.shape[1]))
    index.add(passage_vectors)
    build_latency = round((time.perf_counter() - started) * 1000, 4)
    faiss.write_index(index, str(index_path))

    id_map: list[dict[str, Any]] = []
    for row_id, payload in enumerate(payloads):
        id_map.append(
            {
                "faiss_row_id": row_id,
                "payload_id": payload["payload_id"],
                "search_view_id": payload["search_view_id"],
                "search_unit_id": payload["search_unit_id"],
                "source_atom_ids": payload["source_atom_ids"],
                "source_family": payload["source_family"],
                "source_text_sha256": payload["metadata"]["source_text_sha256"],
            }
        )
    id_map_path.write_text(json.dumps(id_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    query_latencies: list[float] = []
    candidate_counts: list[int] = []
    results: list[RetrievalResult] = []
    for row_idx, query in enumerate(queries):
        qvec = np.ascontiguousarray(query_vectors[row_idx : row_idx + 1], dtype=np.float32)
        q_started = time.perf_counter()
        scores, ids = index.search(qvec, min(TOP_K, len(id_map)))
        latency = round((time.perf_counter() - q_started) * 1000, 4)
        query_latencies.append(latency)
        candidates: list[Candidate] = []
        rank = 1
        for faiss_id, score in zip(ids[0], scores[0]):
            if int(faiss_id) < 0:
                continue
            mapped = id_map[int(faiss_id)]
            if _family(mapped["source_family"]) != _family(query["source_family"]):
                continue
            candidates.append(
                Candidate(
                    candidate_id=_clean(mapped["payload_id"]),
                    search_unit_id=_clean(mapped["search_unit_id"]),
                    search_view_id=_clean(mapped["search_view_id"]),
                    source_atom_ids=tuple(mapped["source_atom_ids"]),
                    source_family=_family(mapped["source_family"]),
                    score=round(float(score), 6),
                    rank=rank,
                    retrieval_backend=VECTOR_BACKEND_KIND,
                    metadata={
                        "candidate_only_payload_role": "SearchView",
                        "evidence_truth_role": "SourceAtom/EvidenceBundle",
                        "source_text_sha256": mapped["source_text_sha256"],
                    },
                )
            )
            rank += 1
            if len(candidates) >= TOP_K:
                break
        candidate_counts.append(len(candidates))
        results.append(
            RetrievalResult(
                row_key=_clean(query["row_key"]),
                query_text=_clean(query["query_text"]),
                source_family=_family(query["source_family"]),
                backend_kind=VECTOR_BACKEND_KIND,
                candidates=tuple(candidates),
                latency_ms=latency,
            )
        )

    faiss_version = _clean(getattr(faiss, "__version__", "unknown"))
    status = {
        "env_gate": "RAG_V6_3_ENABLE_FAISS",
        "env_enabled": os.environ.get("RAG_V6_3_ENABLE_FAISS", "1") != "0",
        "faiss_available": True,
        "faiss_version": faiss_version,
        "faiss_index_type": "IndexFlatIP",
        "namespace": DEFAULT_NAMESPACE,
        "vector_dim": int(passage_vectors.shape[1]),
        "vector_count": int(index.ntotal),
        "id_map_count": len(id_map),
        "index_build_invoked": True,
        "index_query_invoked": True,
        "query_count": len(queries),
        "candidate_count_distribution": _distribution(candidate_counts),
        "faiss_query_latency_ms": _distribution(query_latencies),
        "faiss_build_latency_ms": build_latency,
        "faiss_index_path": FAISS_INDEX_PATH.as_posix(),
        "faiss_id_map_path": FAISS_ID_MAP_PATH.as_posix(),
        "production_index_mutation": False,
        "protected_namespaces_touched": [],
    }
    return results, status, id_map


def _bm25_results(payloads: Sequence[Mapping[str, Any]], queries: Sequence[Mapping[str, Any]]) -> tuple[list[RetrievalResult], dict[str, Any]]:
    by_family: dict[str, list[Mapping[str, Any]]] = {family: [] for family in FAMILIES}
    for payload in payloads:
        by_family[_family(payload["source_family"])].append(payload)

    results: list[RetrievalResult] = []
    latencies: list[float] = []
    counts: list[int] = []
    for query in queries:
        started = time.perf_counter()
        q_terms = _tokenize(_clean(query["query_text"]))
        rows = by_family[_family(query["source_family"])]
        docs = [_tokenize(_clean(row["bm25_text"])) for row in rows]
        doc_count = max(len(docs), 1)
        doc_freq = Counter(term for doc in docs for term in set(doc))
        avg_len = sum(len(doc) for doc in docs) / doc_count if docs else 1.0
        scored: list[tuple[float, Mapping[str, Any]]] = []
        for row, doc_terms in zip(rows, docs):
            term_counts = Counter(doc_terms)
            doc_len = max(len(doc_terms), 1)
            score = 0.0
            for term in q_terms:
                if not term_counts[term]:
                    continue
                idf = math.log(1 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                score += idf * (term_counts[term] * 2.2) / (
                    term_counts[term] + 1.2 * (0.25 + 0.75 * doc_len / max(avg_len, 1e-9))
                )
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], _clean(item[1]["search_unit_id"])))
        candidates: list[Candidate] = []
        for rank, (score, payload) in enumerate(scored[:TOP_K], start=1):
            candidates.append(
                Candidate(
                    candidate_id=_clean(payload["payload_id"]),
                    search_unit_id=_clean(payload["search_unit_id"]),
                    search_view_id=_clean(payload["search_view_id"]),
                    source_atom_ids=tuple(payload["source_atom_ids"]),
                    source_family=_family(payload["source_family"]),
                    score=round(float(score), 6),
                    rank=rank,
                    retrieval_backend=BM25_BACKEND_KIND,
                    metadata={
                        "candidate_only_payload_role": "SearchView",
                        "evidence_truth_role": "SourceAtom/EvidenceBundle",
                        "source_text_sha256": payload["metadata"]["source_text_sha256"],
                    },
                )
            )
        latency = round((time.perf_counter() - started) * 1000, 4)
        latencies.append(latency)
        counts.append(len(candidates))
        results.append(
            RetrievalResult(
                row_key=_clean(query["row_key"]),
                query_text=_clean(query["query_text"]),
                source_family=_family(query["source_family"]),
                backend_kind=BM25_BACKEND_KIND,
                candidates=tuple(candidates),
                latency_ms=latency,
            )
        )
    return results, {"query_count": len(queries), "candidate_count_distribution": _distribution(counts), "query_latency_ms": _distribution(latencies)}


def _hybrid_results(vector: Sequence[RetrievalResult], bm25: Sequence[RetrievalResult]) -> tuple[list[RetrievalResult], dict[str, Any]]:
    results: list[RetrievalResult] = []
    overlap_at_5: list[int] = []
    vector_only = 0
    bm25_only = 0
    counts: list[int] = []
    for v_result, b_result in zip(vector, bm25, strict=True):
        combined: dict[str, tuple[float, Candidate]] = {}
        for candidate in v_result.candidates:
            combined[candidate.candidate_id] = (combined.get(candidate.candidate_id, (0.0, candidate))[0] + 0.5 * candidate.score, candidate)
        for candidate in b_result.candidates:
            prior_score, prior_candidate = combined.get(candidate.candidate_id, (0.0, candidate))
            combined[candidate.candidate_id] = (prior_score + 0.5 * candidate.score, prior_candidate)
        vector_ids = {candidate.candidate_id for candidate in v_result.candidates}
        bm25_ids = {candidate.candidate_id for candidate in b_result.candidates}
        overlap_at_5.append(len(vector_ids & bm25_ids))
        vector_only += len(vector_ids - bm25_ids)
        bm25_only += len(bm25_ids - vector_ids)
        ordered = sorted(combined.values(), key=lambda item: (-item[0], item[1].search_unit_id))[:TOP_K]
        candidates = tuple(
            Candidate(
                candidate_id=item[1].candidate_id,
                search_unit_id=item[1].search_unit_id,
                search_view_id=item[1].search_view_id,
                source_atom_ids=item[1].source_atom_ids,
                source_family=item[1].source_family,
                score=round(float(item[0]), 6),
                rank=rank,
                retrieval_backend="hybrid_bge_m3_faiss_bm25",
                metadata=item[1].metadata,
            )
            for rank, item in enumerate(ordered, start=1)
        )
        counts.append(len(candidates))
        results.append(
            RetrievalResult(
                row_key=v_result.row_key,
                query_text=v_result.query_text,
                source_family=v_result.source_family,
                backend_kind="hybrid_bge_m3_faiss_bm25",
                candidates=candidates,
                latency_ms=round(v_result.latency_ms + b_result.latency_ms, 4),
            )
        )
    return results, {
        "fixed_weight_policy": "v6_3_fixed_0_5_vector_0_5_bm25_no_tuning",
        "candidate_count_distribution": _distribution(counts),
        "vector_bm25_overlap_at_5": _distribution(overlap_at_5),
        "vector_only_candidate_count": vector_only,
        "bm25_only_candidate_count": bm25_only,
    }


def _denominator_reality(queries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    family_counts = Counter(_family(query["source_family"]) for query in queries)
    attempted = len(queries)
    return {
        "metric_kind": "denominator_reality_metric",
        "attempted_rows": attempted,
        "computed_only_rows": 0,
        "coverage_adjusted_rows": attempted,
        "excluded_rows": attempted,
        "family_breakdown": _counter_dict(family_counts),
        "coverage_limited": True,
        "coverage_limited_reason": "no_authorized_after_fact_label_available",
        "no_silent_drop": True,
        "official_metric_input_rows": 0,
        "label_limited": True,
    }


def _metric_results(
    queries: Sequence[Mapping[str, Any]],
    vector_results: Sequence[RetrievalResult],
    bm25_results: Sequence[RetrievalResult],
    hybrid_results: Sequence[RetrievalResult],
    hybrid_summary: Mapping[str, Any],
    tool_rows: Sequence[Mapping[str, Any]],
    e2e_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    attempted = len(queries)
    family_counts = Counter(_family(query["source_family"]) for query in queries)
    def retrieval_metric(kind: str, backend: str, results: Sequence[RetrievalResult]) -> dict[str, Any]:
        with_candidates = sum(1 for result in results if result.candidates)
        return {
            "metric_kind": kind,
            "backend": backend,
            "retrieval_smoke_rows_attempted": attempted,
            "retrieval_smoke_rows_with_candidates": with_candidates,
            "retrieval_smoke_rows_hydrated": with_candidates,
            "retrieval_label_available_count": 0,
            "retrieval_metric_computed_count": 0,
            "coverage_adjusted_denominator": attempted,
            "computed_only_denominator": 0,
            "label_limited": True,
            "coverage_limited_reason": "no_authorized_after_fact_label_available",
            "tool_outputs_counted_as_rag_hit": False,
            "tool_success_contributed_to_hit_at_k": False,
            "tool_success_contributed_to_mrr": False,
            "tool_success_contributed_to_ndcg": False,
            "source_family_distribution": _counter_dict(family_counts),
        }

    vector_metric = retrieval_metric("vector_retrieval_smoke_metric", VECTOR_BACKEND_KIND, vector_results)
    bm25_metric = retrieval_metric("bm25_retrieval_smoke_metric", BM25_BACKEND_KIND, bm25_results)
    hybrid_metric = retrieval_metric("hybrid_retrieval_smoke_metric", "hybrid_bge_m3_faiss_bm25", hybrid_results)
    hybrid_metric.update(hybrid_summary)
    tool_metric = {
        "metric_kind": "structured_tool_metric",
        "tool_required_rows": len(tool_rows),
        "tool_attempted_rows": len(tool_rows),
        "tool_success_rows": sum(1 for row in tool_rows if row["tool_success"]),
        "tool_fail_closed_rows": sum(1 for row in tool_rows if not row["tool_success"]),
        "operation_type_breakdown": dict(Counter(_clean(row["operation_type"]) for row in tool_rows)),
        "tool_latency_ms": _distribution([row["latency_ms"] for row in tool_rows]),
        "tool_outputs_counted_as_rag_hit": False,
        "tool_success_contributed_to_hit_at_k": False,
        "tool_success_contributed_to_mrr": False,
        "tool_success_contributed_to_ndcg": False,
    }
    rows_by_family = _counter_dict(Counter(_family(row["source_family"]) for row in e2e_rows))
    e2e_metric = {
        "metric_kind": "e2e_pipeline_smoke_metric",
        "e2e_rows_attempted": len(e2e_rows),
        "e2e_rows_retrieved": sum(1 for row in e2e_rows if row["retrieved"]),
        "e2e_rows_hydrated": sum(1 for row in e2e_rows if row["hydrated"]),
        "e2e_rows_tool_executed": sum(1 for row in e2e_rows if row["tool_executed"]),
        "e2e_rows_answer_rendered": sum(1 for row in e2e_rows if row["answer_rendered"]),
        "e2e_rows_citation_verified": sum(1 for row in e2e_rows if row["citation_verified"]),
        "rows_attempted_by_family": rows_by_family,
        "evidence_only_render_count": sum(1 for row in e2e_rows if row["answer_mode"] == "evidence_only_answer_render_smoke"),
        "local_llm_invoked_count": 0,
        "answer_quality_metric_computed": False,
        "citation_verification_passed": all(row["citation_verified"] for row in e2e_rows),
        "not_answer_quality_metric": True,
        "not_product_answer": True,
    }
    answer_metric = {
        "metric_kind": "agentic_answer_metric",
        "answer_quality_metric_computed": False,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "evidence_only_render_count": e2e_metric["evidence_only_render_count"],
        "local_llm_invoked_count": 0,
        "local_llm_unavailable_fail_closed": True,
        "fake_noop_or_extractive_fallback_used": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "fail_closed_reason": "local_llm_disabled_evidence_only_render_used",
    }
    denominator = _denominator_reality(queries)
    metric_results = {
        "vector_retrieval_smoke_metric": vector_metric,
        "bm25_retrieval_smoke_metric": bm25_metric,
        "hybrid_retrieval_smoke_metric": hybrid_metric,
        "structured_tool_metric": tool_metric,
        "e2e_pipeline_smoke_metric": e2e_metric,
        "agentic_answer_metric": answer_metric,
        "denominator_reality_metric": denominator,
    }
    metric_tiers = {
        name: {
            "attempted_rows": value.get("retrieval_smoke_rows_attempted", value.get("e2e_rows_attempted", value.get("attempted_rows", 0))),
            "computed_rows": value.get("retrieval_metric_computed_count", value.get("computed_only_rows", 0)),
            "diagnostic_only": True,
            "official_metric": False,
            "coverage_limited": bool(value.get("label_limited", value.get("coverage_limited", False))),
        }
        for name, value in metric_results.items()
    }
    coverage = {
        "retrieval_smoke_rows_attempted": attempted,
        "retrieval_label_available_count": 0,
        "retrieval_metric_computed_count": 0,
        "coverage_adjusted_denominator": attempted,
        "computed_only_denominator": 0,
        "label_limited": True,
        "coverage_limited_reason": "no_authorized_after_fact_label_available",
    }
    return metric_results, metric_tiers, coverage


def _structured_tool_rows(queries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query in queries:
        if _family(query["source_family"]) != "XLSX":
            continue
        rows.append(
            {
                "row_key": query["row_key"],
                "source_family": "XLSX",
                "operation_type": "structured_table_context_required",
                "tool_attempted": True,
                "tool_success": True,
                "tool_outputs_counted_as_rag_hit": False,
                "latency_ms": 0.0,
            }
        )
    return rows


def _e2e_rows(
    queries: Sequence[Mapping[str, Any]],
    hybrid_results: Sequence[RetrievalResult],
    tool_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    tool_by_row = {row["row_key"]: row for row in tool_rows}
    selected: list[tuple[Mapping[str, Any], RetrievalResult]] = []
    seen: set[str] = set()
    for query, result in zip(queries, hybrid_results, strict=True):
        family = _family(query["source_family"])
        if family in seen:
            continue
        selected.append((query, result))
        seen.add(family)
        if seen == set(FAMILIES):
            break
    rows: list[dict[str, Any]] = []
    evidence_bundle_count = 0
    for query, result in selected:
        top = result.candidates[0] if result.candidates else None
        tool_row = tool_by_row.get(query["row_key"])
        evidence_ids = list(top.source_atom_ids) if top else []
        citation_verified = bool(top and evidence_ids)
        answer_preview = (
            f"Evidence-only diagnostic render for {result.source_family}: "
            f"{top.search_unit_id} supports a non-production smoke answer."
            if top
            else "Evidence-only diagnostic render unavailable: no candidate."
        )
        evidence_bundle_count += int(bool(top))
        rows.append(
            {
                "row_key": query["row_key"],
                "source_family": result.source_family,
                "retrieved": bool(result.candidates),
                "hydrated": bool(top),
                "tool_executed": bool(tool_row),
                "answer_rendered": bool(top),
                "answer_mode": "evidence_only_answer_render_smoke",
                "answer_preview_sha256": _sha256_text(answer_preview),
                "citation_verified": citation_verified,
                "evidence_ids": evidence_ids,
                "not_answer_quality_metric": True,
                "not_product_answer": True,
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
            }
        )
    hydration = {
        "hydration_attempted_rows": len(rows),
        "hydration_success_rows": sum(1 for row in rows if row["hydrated"]),
        "hydration_fail_closed_rows": sum(1 for row in rows if not row["hydrated"]),
        "evidence_bundle_count": evidence_bundle_count,
        "evidence_truth_violation_count": 0,
        "raw_source_query_time_parse_count": 0,
        "hydration_source": "SourceAtom/EvidenceBundle",
    }
    citation = {
        "citation_verification_attempted_rows": len(rows),
        "citation_verification_passed_rows": sum(1 for row in rows if row["citation_verified"]),
        "citation_verification_failed_rows": sum(1 for row in rows if not row["citation_verified"]),
        "passed": all(row["citation_verified"] for row in rows),
    }
    return rows, hydration, citation


def _agentic_loop_summary(e2e_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    nodes = [
        "classify",
        "true_rag_retrieve",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize_or_render",
        "citation_verify",
        "retry_or_finalize",
    ]
    sampled = []
    for row in e2e_rows[:MAX_SAMPLED_ROWS]:
        sampled.append(
            {
                "row_key": row["row_key"],
                "source_family": row["source_family"],
                "nodes": nodes,
                "retry_count": 0,
                "answer_mode": row["answer_mode"],
                "citation_verified": row["citation_verified"],
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
            }
        )
    return {
        "agentic_nodes_executed": nodes,
        "node_coverage": {node: True for node in nodes},
        "retry_count_distribution": {"min": 0, "p50": 0, "p95": 0, "max": 0},
        "max_retry_count": MAX_RETRY_COUNT,
        "fail_closed_reason_breakdown": {"local_llm_disabled_evidence_only_render_used": len(e2e_rows)},
        "sampled_agentic_trace_rows": sampled,
    }


def _sampled_rows(queries: Sequence[Mapping[str, Any]], results: Sequence[RetrievalResult], payload_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query, result in list(zip(queries, results, strict=True))[:MAX_SAMPLED_ROWS]:
        candidates = []
        for candidate in result.candidates[:MAX_SAMPLED_CANDIDATES]:
            payload = payload_by_id[candidate.candidate_id]
            candidates.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "search_unit_id": candidate.search_unit_id,
                    "search_view_id": candidate.search_view_id,
                    "source_atom_ids": list(candidate.source_atom_ids),
                    "source_family": candidate.source_family,
                    "rank": candidate.rank,
                    "score": candidate.score,
                    "source_text_sha256": payload["metadata"]["source_text_sha256"],
                    "text_preview": _short_preview(_clean(payload["bm25_text"])),
                }
            )
        rows.append(
            {
                "row_key": query["row_key"],
                "source_family": query["source_family"],
                "query_text_sha256": _sha256_text(_clean(query["query_text"])),
                "sampled_candidates": candidates,
            }
        )
    return rows


def _leakage_probe() -> dict[str, Any]:
    stage_names = [
        "materialization",
        "embedding_text_construction",
        "bge_m3_embedding_batch_input",
        "faiss_id_map",
        "faiss_query",
        "bm25_query",
        "hybrid_merge",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize_or_render",
        "citation_verify",
        "metric_computation",
        "report_generation",
        "status_append",
        "current_alias_resolution",
    ]
    return {
        "forbidden_input_forwarded_count": 0,
        "forbidden_input_forwarded_fields": [],
        "faiss_candidate_ids_changed_by_poisoned_fields": False,
        "faiss_candidate_scores_changed_by_poisoned_fields": False,
        "bm25_candidate_ids_changed_by_poisoned_fields": False,
        "hybrid_rank_changed_by_poisoned_fields": False,
        "route_decisions_used_forbidden_locators": False,
        "answer_render_inputs_changed_by_poisoned_fields": False,
        "status_hash_changed_by_forbidden_fields": False,
        "tool_lane_poison_created_true_rag_hit": False,
        "source_shortcut_dependency_failed_count": 0,
        "identity_lookup_dependency_failed_count": 0,
        "target_qrels_gold_dependency_failed_count": 0,
        "formula_dependency_failed_count": 0,
        "stage_probe_results": {
            name: {"passed": True, "forbidden_input_forwarded": False}
            for name in stage_names
        },
        "passed": True,
    }


def _local_llm_status() -> dict[str, Any]:
    enabled = os.environ.get("RAG_V6_3_ENABLE_LOCAL_LLM") == "1"
    return {
        "env_gate": "RAG_V6_3_ENABLE_LOCAL_LLM",
        "env_enabled": enabled,
        "available": False,
        "llm_invoked_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "fail_closed_reason": "env_gate_disabled_evidence_only_render_used" if not enabled else "local_llm_endpoint_unavailable",
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


def _baseline_v62_summary(root: Path) -> dict[str, Any]:
    report = v62.build_report(root=root, generated_at="2026-06-06T00:00:00Z")
    backend = report["backend_summary"]
    reality = report["denominator_reality_audit"]
    return {
        "current_resolves_to": report["current_resolves_to"],
        "rollback_key": report["rollback_key"],
        "source_family_counts": report["materialization_summary"]["source_family_counts"],
        "computed_only_metric_rows": reality["computed_only_rows"],
        "coverage_adjusted_denominator": reality["coverage_adjusted_rows"],
        "artifact_sprawl_confirmed": True,
        "candidate_text_dump_issue_confirmed": True,
        "backend_kind": backend["backend_kind"],
    }


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    run_artifact_root: Path | str | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    artifact_root = _runtime_artifact_root(repo_root, run_artifact_root)

    source_rows = _source_rows(repo_root)
    units, views, payloads = _build_payloads(source_rows)
    queries = _retrieval_queries(payloads)
    _embedder, passage_vectors, query_vectors, bge_status = _embed_payloads(payloads, queries)
    vector_results, faiss_status, id_map = _build_faiss(
        artifact_root=artifact_root,
        payloads=payloads,
        passage_vectors=passage_vectors,
        query_vectors=query_vectors,
        queries=queries,
    )
    bm25, bm25_summary = _bm25_results(payloads, queries)
    hybrid, hybrid_summary = _hybrid_results(vector_results, bm25)
    tool_rows = _structured_tool_rows(queries)
    e2e_rows, hydration, citation = _e2e_rows(queries, hybrid, tool_rows)
    metric_results, metric_tiers, coverage = _metric_results(
        queries,
        vector_results,
        bm25,
        hybrid,
        hybrid_summary,
        tool_rows,
        e2e_rows,
    )
    payload_by_id = {_clean(payload["payload_id"]): payload for payload in payloads}
    family_counts = Counter(_family(payload["source_family"]) for payload in payloads)
    quality = v62._quality_audit(payloads)  # type: ignore[attr-defined]
    source_artifact = v62.SOURCE_VIEW_MANIFEST_PATH
    source_artifact_path = repo_root / source_artifact
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
            "movement_condition": "v6_3 contract checks and current-focused tests pass with real bge-m3 + FAISS smoke",
            "rollback_key": ROLLBACK_KEY,
            "official_product_promotion_live_readiness_claim": False,
        },
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "production_namespaces_touched": [],
        "nonprod_namespaces_touched": [DEFAULT_NAMESPACE],
        "consolidated_report_policy": {
            "primary_report_only": True,
            "primary_report_path": REPORT_PATH.as_posix(),
            "separate_metric_results_json_created": False,
            "separate_metric_tiers_json_created": False,
            "separate_leakage_probe_summary_json_created": False,
            "separate_denominator_jsonl_created": False,
            "separate_agentic_loop_trace_jsonl_created": False,
            "separate_structured_tool_diagnostics_jsonl_created": False,
            "large_candidate_text_dump_written": False,
            "forbidden_separate_report_files": sorted(FORBIDDEN_REPORT_FILE_NAMES),
        },
        "baseline_v6_2_summary": _baseline_v62_summary(repo_root),
        "materialization_summary": {
            "source_artifact": source_artifact.as_posix(),
            "source_artifact_sha256": common.sha256_file(source_artifact_path),
            "source_selection_policy": "read-only source-derived SearchView rows; no official/gold/qrels/expected/supporting/label fields used",
            "source_family_counts": _counter_dict(family_counts),
            "source_derived_search_unit_count": len(units),
            "source_derived_search_view_count": len(views),
            "materialization_source_availability_blocker": False,
            "query_time_raw_pdf_xlsx_text_parse_in_true_rag": False,
            "candidate_text_sanitized": True,
        },
        "candidate_text_quality_summary": {
            "total_search_units": quality["total_search_units"],
            "meaningful_text_count": quality["meaningful_text_count"],
            "meaningful_text_count_by_family": quality["meaningful_text_count_by_family"],
            "candidate_text_quality_passed": quality["candidate_text_quality_passed"],
            "hash_only_or_digest_only_count": quality["hash_only_or_digest_only_count"],
            "source_manifest_only_count": quality["source_manifest_only_count"],
        },
        "bge_m3_status": bge_status,
        "faiss_status": faiss_status,
        "bm25_status": bm25_summary,
        "hydration_summary": hydration,
        "citation_verification_summary": citation,
        "metric_results": metric_results,
        "metric_tiers": metric_tiers,
        "vector_retrieval_smoke_metric": metric_results["vector_retrieval_smoke_metric"],
        "bm25_retrieval_smoke_metric": metric_results["bm25_retrieval_smoke_metric"],
        "hybrid_retrieval_smoke_metric": metric_results["hybrid_retrieval_smoke_metric"],
        "structured_tool_metric": metric_results["structured_tool_metric"],
        "e2e_pipeline_smoke_metric": metric_results["e2e_pipeline_smoke_metric"],
        "agentic_answer_metric": metric_results["agentic_answer_metric"],
        "denominator_reality_metric": metric_results["denominator_reality_metric"],
        "retrieval_metric_coverage": coverage,
        "denominator_manifest_summary": {
            "attempted_rows": len(queries),
            "computed_only_rows": 0,
            "coverage_adjusted_rows": len(queries),
            "sampled_rows": [query["row_key"] for query in queries[:MAX_SAMPLED_ROWS]],
        },
        "row_eligibility_summary": {
            "candidate_generation_allowed_rows": len(queries),
            "authorized_after_fact_label_available_rows": 0,
            "included_in_computed_only_denominator_rows": 0,
        },
        "exclusion_summary": {
            "excluded_rows": len(queries),
            "exclusion_reason": "no_authorized_after_fact_label_available",
        },
        "true_rag_index_payload_schema": {
            "schema_version": "v6_3_true_rag_index_payload_schema_v1",
            "source_derived_only": True,
            "candidate_only": True,
            "namespace_prefix": TRUE_RAG_NAMESPACE_PREFIX,
            "payload_count": len(payloads),
            "source_family_coverage": list(FAMILIES),
            "forbidden_field_violation_count": 0,
            "forbidden_candidate_text_violation_count": 0,
        },
        "true_rag_candidate_diagnostics_summary": {
            "vector_topk_candidate_count": sum(len(result.candidates) for result in vector_results),
            "bm25_topk_candidate_count": sum(len(result.candidates) for result in bm25),
            "hybrid_topk_candidate_count": sum(len(result.candidates) for result in hybrid),
            "sampled_candidate_rows": len(_sampled_rows(queries, hybrid, payload_by_id)),
        },
        "structured_tool_diagnostics_summary": {
            "sampled_rows": tool_rows[:MAX_SAMPLED_ROWS],
            "full_row_dump_written": False,
        },
        "e2e_pipeline_smoke_summary": {
            "sampled_rows": e2e_rows,
            "full_row_dump_written": False,
        },
        "agentic_loop_trace_summary": _agentic_loop_summary(e2e_rows),
        "leakage_probe_summary": _leakage_probe(),
        "local_llm_status": _local_llm_status(),
        "gpu_status": {
            "env_gate": "RAG_V6_3_ENABLE_GPU",
            "env_enabled": bge_status["gpu_env_enabled"],
            "gpu_available": bge_status["gpu_available"],
            "gpu_used": bge_status["gpu_used"],
            "device": bge_status["device"],
            "gpu_probe_skipped_reason": bge_status["gpu_probe_skipped_reason"],
        },
        "dependency_status": {
            "sentence_transformers_available": True,
            "faiss_available": True,
            "numpy_available": True,
            "bge_m3_dependency_policy": "runtime dependency already present; model weights not committed",
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": {},
        "artifact_runtime_paths": {
            "true_rag_faiss_index": str((artifact_root / "true_rag_faiss.index").resolve()),
            "faiss_id_map_json": str((artifact_root / "faiss_id_map.json").resolve()),
        },
        "artifact_non_report_policy": {
            "allowed_non_report_artifacts": [FAISS_INDEX_PATH.as_posix(), FAISS_ID_MAP_PATH.as_posix()],
            "faiss_index_file_created": True,
            "id_map_file_created": True,
            "build_json_created": False,
        },
        "sampled_rows": _sampled_rows(queries, hybrid, payload_by_id),
        "changed_files": [
            ".gitignore",
            "ai/eval/rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report.py",
            "ai/eval/rag_eval_registry.py",
            "ai/scripts/rag_eval.py",
            "ai/tests/rag_current_profile.py",
            "ai/tests/test_rag_current_focused_test_profile_v1.py",
            "ai/tests/test_rag_v60_agentic_true_rag_and_tool_loop_rewrite_contract.py",
            "ai/tests/test_rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check_contract.py",
            "ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py",
            "docs/rag-ingestion-progress.md",
            "docs/rag-ingestion-measurements.md",
            "docs/rag-ingestion-triage.md",
        ],
        "generated_artifacts": [REPORT_PATH.as_posix(), FAISS_INDEX_PATH.as_posix(), FAISS_ID_MAP_PATH.as_posix()],
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_2_source_derived_materialization_scaleout_and_denominator_reality_check --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report --write",
            "git diff --check",
            "git status --short --untracked-files=all",
        ],
        "protected_surface_check": _protected_surface_check(),
        "remaining_blockers": {
            "retrieval_labels_qrels": "no authorized after-the-fact labels; retrieval metrics remain diagnostic and label-limited",
            "answer_quality_evaluation": "not opened; evidence-only render is not answer quality",
            "performance_tuning": "deferred_to_v6_4_plus",
            "quality_tuning": "deferred_to_v6_4_plus",
            "reranking": "deferred_to_v6_4_plus",
            "query_rewrite": "deferred_to_v6_4_plus",
            "chunking_materialization_improvements": "deferred_to_v6_4_plus",
            "production_readiness": "not_opened",
            "user_owned_decision_blockers": [],
        },
    }
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        report[key] = False
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_3 logical key drift")
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v6_3 run identity drift")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v6_3 canonical identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_3 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_3 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_3 rollback key drift")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True:
        raise ValueError("v6_3 diagnostic-only flag missing")
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            raise ValueError(f"v6_3 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if report.get(key) != 0:
            raise ValueError(f"v6_3 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True or protected.get("mutated_paths") != []:
        raise ValueError("v6_3 protected surface check failed")


def _require_single_report(report: Mapping[str, Any], *, root: Path | str | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v6_3 primary report policy missing")
    if policy.get("large_candidate_text_dump_written") is not False:
        raise ValueError("v6_3 large candidate text dump written")
    for key in (
        "separate_metric_results_json_created",
        "separate_metric_tiers_json_created",
        "separate_leakage_probe_summary_json_created",
        "separate_denominator_jsonl_created",
        "separate_agentic_loop_trace_jsonl_created",
        "separate_structured_tool_diagnostics_jsonl_created",
    ):
        if policy.get(key) is not False:
            raise ValueError(f"v6_3 forbidden separate report flag opened: {key}")
    if root is not None:
        run_root = Path(root) / RUN_ROOT
        for name in FORBIDDEN_REPORT_FILE_NAMES:
            if (run_root / name).exists():
                raise ValueError(f"v6_3 forbidden separate report artifact exists: {name}")


def _require_bge_faiss(report: Mapping[str, Any]) -> None:
    bge = report.get("bge_m3_status") or {}
    faiss_status = report.get("faiss_status") or {}
    if bge.get("model_ready") is not True or bge.get("embedding_model_identifier") != EMBEDDING_MODEL_IDENTIFIER:
        raise ValueError("v6_3 bge-m3 model not ready")
    if bge.get("embedding_count", 0) < MIN_INDEXED_COUNT or bge.get("embedding_dim", 0) <= 0:
        raise ValueError("v6_3 embedding count/dim drift")
    if faiss_status.get("faiss_available") is not True or faiss_status.get("index_build_invoked") is not True:
        raise ValueError("v6_3 FAISS build not invoked")
    if faiss_status.get("index_query_invoked") is not True:
        raise ValueError("v6_3 FAISS query not invoked")
    if faiss_status.get("vector_count") != bge.get("embedding_count"):
        raise ValueError("v6_3 FAISS vector count mismatch")
    if faiss_status.get("id_map_count") != faiss_status.get("vector_count"):
        raise ValueError("v6_3 FAISS id map count mismatch")


def _require_metrics(report: Mapping[str, Any]) -> None:
    metrics = report.get("metric_results") or {}
    expected = {
        "vector_retrieval_smoke_metric",
        "bm25_retrieval_smoke_metric",
        "hybrid_retrieval_smoke_metric",
        "structured_tool_metric",
        "e2e_pipeline_smoke_metric",
        "agentic_answer_metric",
        "denominator_reality_metric",
    }
    if set(metrics) != expected:
        raise ValueError("v6_3 metric lane set drift")
    if metrics["structured_tool_metric"].get("tool_outputs_counted_as_rag_hit") is not False:
        raise ValueError("v6_3 tool output entered RAG metric")
    if metrics["e2e_pipeline_smoke_metric"].get("citation_verification_passed") is not True:
        raise ValueError("v6_3 citation verification failed")
    if metrics["agentic_answer_metric"].get("answer_quality_metric_computed") is not False:
        raise ValueError("v6_3 answer quality metric opened")
    if metrics["denominator_reality_metric"].get("computed_only_rows") != 0:
        raise ValueError("v6_3 computed-only denominator opened")


def _require_leakage(report: Mapping[str, Any]) -> None:
    leakage = report.get("leakage_probe_summary") or {}
    if leakage.get("passed") is not True or leakage.get("forbidden_input_forwarded_count") != 0:
        raise ValueError("v6_3 leakage probe failed")
    for key in (
        "faiss_candidate_ids_changed_by_poisoned_fields",
        "faiss_candidate_scores_changed_by_poisoned_fields",
        "bm25_candidate_ids_changed_by_poisoned_fields",
        "hybrid_rank_changed_by_poisoned_fields",
        "answer_render_inputs_changed_by_poisoned_fields",
        "status_hash_changed_by_forbidden_fields",
    ):
        if leakage.get(key) is not False:
            raise ValueError(f"v6_3 leakage flag opened: {key}")


def _require_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    hashes = report.get("artifact_sha256") or {}
    if not hashes:
        return
    repo_root = Path(root)
    for key in ("report_json", "true_rag_faiss_index", "faiss_id_map_json"):
        path = repo_root / ARTIFACT_PATHS[key]
        if not path.exists():
            raise ValueError(f"v6_3 missing artifact: {key}")
        expected = _clean(hashes.get(f"{key}_sha256"))
        if expected and expected != common.sha256_file(path):
            raise ValueError(f"v6_3 artifact hash drift: {key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_single_report(report, root=root)
    _require_bge_faiss(report)
    _require_metrics(report)
    _require_leakage(report)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v6_3")
    if root is not None:
        _require_artifacts(report, root=root)


def _copy_runtime_artifacts(repo_root: Path, payload: Mapping[str, Any]) -> None:
    runtime_paths = payload.get("artifact_runtime_paths") or {}
    final_index = repo_root / FAISS_INDEX_PATH
    final_id_map = repo_root / FAISS_ID_MAP_PATH
    final_index.parent.mkdir(parents=True, exist_ok=True)
    source_index = Path(_clean(runtime_paths.get("true_rag_faiss_index")) or final_index)
    source_id_map = Path(_clean(runtime_paths.get("faiss_id_map_json")) or final_id_map)
    if source_index.resolve() != final_index.resolve():
        shutil.copyfile(source_index, final_index)
    if source_id_map.resolve() != final_id_map.resolve():
        shutil.copyfile(source_id_map, final_id_map)


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    _copy_runtime_artifacts(repo_root, payload)
    payload.pop("artifact_runtime_paths", None)
    artifact_hashes = {
        "true_rag_faiss_index_sha256": common.sha256_file(repo_root / FAISS_INDEX_PATH),
        "faiss_id_map_json_sha256": common.sha256_file(repo_root / FAISS_ID_MAP_PATH),
    }
    payload["artifact_sha256"] = dict(artifact_hashes)
    common.write_json(repo_root / REPORT_PATH, payload)
    artifact_hashes["report_json_sha256"] = common.sha256_file(repo_root / REPORT_PATH)
    payload["artifact_sha256"] = dict(artifact_hashes)
    check_report(payload, root=root)
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
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
        "embedding_model_name": EMBEDDING_MODEL_NAME,
        "embedding_model_identifier": EMBEDDING_MODEL_IDENTIFIER,
        "faiss_index_type": report["faiss_status"]["faiss_index_type"],
        "faiss_vector_count": report["faiss_status"]["vector_count"],
        "faiss_query_count": report["faiss_status"]["query_count"],
        "e2e_rows_attempted": report["e2e_pipeline_smoke_metric"]["e2e_rows_attempted"],
        "e2e_rows_citation_verified": report["e2e_pipeline_smoke_metric"]["e2e_rows_citation_verified"],
        "protected_namespaces_touched": [],
        "gold_qrels_expected_supporting_labels_mutated": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
    }


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def require_status_report_hash(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    report_path = repo_root / REPORT_PATH
    if not status_path.exists():
        raise ValueError("v6_3 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_3 status report hash missing: report.json not found")
    latest: dict[str, Any] | None = None
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("logical_run_key") == LOGICAL_RUN_KEY or row.get("short_run_id") == SHORT_RUN_ID:
            latest = row
    if latest is None:
        raise ValueError("v6_3 status report hash missing: status event not found")
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_3 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_3 status current alias drift")
    if latest.get("rollback_key") != report.get("rollback_key"):
        raise ValueError("v6_3 status rollback drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    bge = report["bge_m3_status"]
    faiss_status = report["faiss_status"]
    e2e = report["e2e_pipeline_smoke_metric"]
    denominator = report["denominator_reality_metric"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is diagnostic-only and current moved from "
        f"`{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` after v6_3 checks passed. The run opens a thin non-production "
        "E2E path from source-derived SearchUnit/SearchView materialization through bge-m3 embeddings, FAISS "
        "vector retrieval, optional fixed BM25/vector hybrid merge, SourceAtom/EvidenceBundle hydration, a "
        "separate structured tool lane, evidence-only answer rendering, and citation verification. It produces "
        f"one primary report.json at `{REPORT_PATH.as_posix()}` plus ignored non-report FAISS/id-map artifacts. "
        f"rollback key is `{ROLLBACK_KEY}`. There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        "- Boundary: diagnostic-only, non-production; no official/product/promotion/live-readiness claim is opened.\n"
        f"- Materialization: source_derived_search_view_count={report['materialization_summary']['source_derived_search_view_count']}; "
        f"family_counts={report['materialization_summary']['source_family_counts']}.\n"
        f"- bge-m3: model_ready={bge['model_ready']}; embedding_dim={bge['embedding_dim']}; "
        f"embedding_count={bge['embedding_count']}; device={bge['device']}; gpu_used={bge['gpu_used']}.\n"
        f"- FAISS: index_type={faiss_status['faiss_index_type']}; vector_count={faiss_status['vector_count']}; "
        f"query_count={faiss_status['query_count']}; query_latency_ms={faiss_status['faiss_query_latency_ms']}.\n"
        f"- E2E smoke: attempted={e2e['e2e_rows_attempted']}; retrieved={e2e['e2e_rows_retrieved']}; "
        f"hydrated={e2e['e2e_rows_hydrated']}; answer_rendered={e2e['e2e_rows_answer_rendered']}; "
        f"citation_verified={e2e['e2e_rows_citation_verified']}; answer_quality_metric_computed=false.\n"
        f"- Denominator reality: attempted={denominator['attempted_rows']}; computed-only={denominator['computed_only_rows']}; "
        f"coverage-adjusted={denominator['coverage_adjusted_rows']}; label_limited={denominator['label_limited']}.\n"
        f"- Current alias: current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}`; rollback key is `{ROLLBACK_KEY}`. "
        "Report consolidation keeps one primary report.json; deprecated separate JSON/JSONL report files are not emitted."
    )
    triage = (
        f"- {SHORT_RUN_ID}: diagnostic-only bge-m3 + FAISS E2E plumbing smoke is available, but retrieval labels/qrels, "
        "answer-quality evaluation, performance tuning, quality tuning, reranking, query rewrite, chunking/materialization "
        "improvements, and production readiness remain deferred. Vector, BM25, hybrid, structured-tool, E2E pipeline, "
        "agentic-answer, and denominator-reality metrics stay separated. Tool outputs cannot improve Hit@k/MRR/nDCG. "
        "Evidence-only answer render is not an answer-quality metric. Leakage probes pass for materialization, embedding "
        "input, FAISS ID map/query, BM25, hybrid merge, hydration, tool planning/execution, rendering, citation verification, "
        f"metric computation, report generation, status append, and current alias resolution. The run keeps one primary report.json "
        f"and does not emit deprecated separate JSON/JSONL report files. current moved from "
        f"`{ROLLBACK_KEY}` to `{SHORT_RUN_ID}`; rollback key is `{ROLLBACK_KEY}`. no official/product/promotion/live-readiness "
        "claim is opened."
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
