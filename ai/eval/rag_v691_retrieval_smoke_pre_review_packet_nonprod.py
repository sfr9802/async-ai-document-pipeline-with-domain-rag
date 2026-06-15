from __future__ import annotations

import csv
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report as v63
from ai.eval import rag_v65_retrieval_metric_unlock_packet_nonprod as v65
from ai.eval import rag_v68_metric_gated_retrieval_quality_engineering_nonprod as v68
from ai.eval import rag_v69_answer_quality_gate_packet_nonprod as v69


LOGICAL_RUN_KEY = "v6_9_1_retrieval_smoke_pre_review_packet_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_9_1_RETRIEVAL_SMOKE_PRE_REVIEW_PACKET_NONPROD_READY"
PREVIOUS_CURRENT = v69.LOGICAL_RUN_KEY
CURRENT_RESOLVES_TO = v69.LOGICAL_RUN_KEY
ROLLBACK_KEY = v69.LOGICAL_RUN_KEY

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
REVIEW_PACKET_JSONL_PATH = RUN_ROOT / "retrieval_smoke_review_packet.jsonl"
REVIEW_PACKET_CSV_PATH = RUN_ROOT / "retrieval_smoke_review_packet.csv"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "retrieval_smoke_review_packet_jsonl": REVIEW_PACKET_JSONL_PATH.as_posix(),
    "retrieval_smoke_review_packet_csv": REVIEW_PACKET_CSV_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}

FAMILIES = ("PDF", "TEXT", "XLSX")
BACKENDS = ("vector", "bm25", "hybrid")
QUERY_ROWS_PER_FAMILY = 3
MAX_CANDIDATES_PER_BACKEND = 5
BLOCKED_REASON = "pending_user_owned_qrels_denominator_review_for_current_searchunit_searchview_surface"
LEGACY_BRIDGE_BLOCKED_REASON = "no_safe_read_only_label_qrels_bridge_available"
SOURCE_ATOM_REGISTRY_PATH = Path("ai/eval/source_registry/source_atom_registry_v1.jsonl")
USER_OWNED_REVIEW_FIELDS = (
    "relevance_label",
    "answerability_label",
    "official_positive_qrels",
    "denominator_inclusion",
    "expected_answer_or_evidence_decision",
    "review_notes",
)

REQUIRED_FALSE_REPORT_FIELDS = (
    "official_metric",
    "retrieval_quality_metric_computed",
    "answer_quality_metric_computed",
    "agentic_answer_metric_computed",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "production_db_mutated",
    "production_index_mutation",
    "production_namespace_mutated",
    "production_cache_mutated",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "official_denominator_mutation",
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
    "generated_final_answer_text",
    "query_text",
    "expected_answer",
    "expected_answer_text",
    "supporting_evidence",
    "supporting_evidence_text",
    "supporting_evidence_ids",
    "qrels_positive_ids",
    "qrels_positive_candidate_ids",
    "target_search_unit_id",
    "source_identity",
    "source_title",
    "source_file_name",
    "source_pdf_path",
    "source_pdf_filename",
    "workbook",
    "workbook_name",
    "row_id",
    "case_id",
}

CSV_FIELDS = (
    "query_id",
    "source_family",
    "backend",
    "rank",
    "candidate_id",
    "search_unit_id",
    "search_view_id",
    "source_atom_id",
    "locator",
    "locator_sha256",
    "excerpt_preview",
    "excerpt_sha256",
    "query_text_preview",
    "query_text_sha256",
    "candidate_score",
    "review_status",
    *USER_OWNED_REVIEW_FIELDS,
)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    return _sha256_json(payload)


def _short_preview(text: str, limit: int = 180) -> str:
    compact = " ".join(_clean(text).split())
    return compact[:limit]


def _family(value: Any) -> str:
    return v63._family(value)  # type: ignore[attr-defined]


def _backend_name(value: str) -> str:
    if value == v63.VECTOR_BACKEND_KIND:
        return "vector"
    if value == v63.BM25_BACKEND_KIND:
        return "bm25"
    if value == "hybrid_bge_m3_faiss_bm25":
        return "hybrid"
    return value


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _protected_surface_check() -> dict[str, Any]:
    return v69._protected_surface_check()  # type: ignore[attr-defined]


def _load_v63(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v63.LOGICAL_RUN_KEY, root=root)
    v63.check_report(source, root=root if report is None else None)
    if report is None:
        v63.require_status_report_hash(root, source)
    return source


def _load_v65(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v65.LOGICAL_RUN_KEY, root=root)
    v65.check_report(source, root=root if report is None else None)
    if report is None:
        v65.require_status_report_hash(root, source)
    return source


def _load_v68(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v68.LOGICAL_RUN_KEY, root=root)
    v68.check_report(source, root=root if report is None else None)
    if report is None:
        v68.require_status_report_hash(root, source)
    return source


def _load_v69(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v69.LOGICAL_RUN_KEY, root=root)
    v69.check_report(source, root=root if report is None else None)
    if report is None:
        v69.require_status_report_hash(root, source)
    return source


def _source_v63_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    materialization = source["materialization_summary"]
    candidate_summary = source["true_rag_candidate_diagnostics_summary"]
    bge = source["bge_m3_status"]
    faiss_status = source["faiss_status"]
    return {
        "run_key": v63.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "source_derived_search_unit_count": materialization["source_derived_search_unit_count"],
        "source_derived_search_view_count": materialization["source_derived_search_view_count"],
        "source_family_counts": materialization["source_family_counts"],
        "source_artifact": materialization["source_artifact"],
        "source_artifact_sha256": materialization["source_artifact_sha256"],
        "vector_topk_candidate_count": candidate_summary["vector_topk_candidate_count"],
        "bm25_topk_candidate_count": candidate_summary["bm25_topk_candidate_count"],
        "hybrid_topk_candidate_count": candidate_summary["hybrid_topk_candidate_count"],
        "embedding_model_identifier": bge["embedding_model_identifier"],
        "embedding_model_revision_or_hash_present": bool(_clean(bge.get("model_revision_or_hash"))),
        "faiss_index_path": faiss_status["faiss_index_path"],
        "faiss_id_map_path": faiss_status["faiss_id_map_path"],
        "faiss_index_sha256": (source.get("artifact_sha256") or {}).get("true_rag_faiss_index_sha256"),
        "faiss_id_map_sha256": (source.get("artifact_sha256") or {}).get("faiss_id_map_json_sha256"),
    }


def _source_v65_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    bridge = source["bridge_audit"]
    packet = source["bridged_retrieval_metric_packet"]
    return {
        "run_key": v65.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "audited_rows": bridge["audited_rows"],
        "bridgeable_rows": bridge["bridgeable_row_count"],
        "non_bridgeable_or_ambiguous_rows": bridge["non_bridgeable_or_ambiguous_row_count"],
        "bridge_state_counts": bridge["state_counts"],
        "bridged_retrieval_metric_computed": packet["computed"],
        "computed_only_denominator": packet["computed_only_denominator"],
        "bridged_metric_denominator": packet["bridged_metric_denominator"],
    }


def _source_v68_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    gate = source["retrieval_quality_gate"]
    diagnostics = source["retrieval_engineering_diagnostics"]
    return {
        "run_key": v68.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "safe_read_only_denominator_available": gate["safe_read_only_denominator_available"],
        "computed_only_denominator": gate["computed_only_denominator"],
        "coverage_adjusted_denominator": gate["coverage_adjusted_denominator"],
        "retrieval_quality_metric_computed": gate["retrieval_quality_metric_computed"],
        "blocked_reason": gate["blocked_reason"],
        "hit_at_k_computed": gate["hit_at_k_computed"],
        "mrr_computed": gate["mrr_computed"],
        "ndcg_computed": gate["ndcg_computed"],
        "by_backend": diagnostics["by_backend"],
        "by_family": diagnostics["by_family"],
    }


def _source_v69_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    summary = source["answer_quality_gate_summary"]
    return {
        "run_key": v69.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "packet_rows": summary["packet_rows"],
        "rows_by_family": summary["rows_by_family"],
        "agentic_verification_state_counts": summary["agentic_verification_state_counts"],
        "human_owned_blank_rows": summary["human_owned_blank_rows"],
        "answer_quality_metric_computed": summary["answer_quality_metric_computed"],
        "retrieval_quality_metric_computed": source.get("retrieval_quality_metric_computed") is True,
    }


def _build_current_payloads(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _, _, payloads = v63._build_payloads(v63._source_rows(root))  # type: ignore[attr-defined]
    queries = v63._retrieval_queries(payloads)  # type: ignore[attr-defined]
    if len(payloads) != 300 or len(queries) != 300:
        raise ValueError("v6_9_1 current v6 candidate surface must have 300 payloads and queries")
    family_counts = Counter(_family(payload.get("source_family")) for payload in payloads)
    if _counter_dict(family_counts) != {"PDF": 100, "TEXT": 100, "XLSX": 100}:
        raise ValueError("v6_9_1 current candidate surface family balance drift")
    return payloads, queries


def _select_review_queries(queries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for query in queries:
        family = _family(query.get("source_family"))
        if counts[family] >= QUERY_ROWS_PER_FAMILY:
            continue
        selected.append(dict(query))
        counts[family] += 1
        if all(counts[family] == QUERY_ROWS_PER_FAMILY for family in FAMILIES):
            break
    if len(selected) != QUERY_ROWS_PER_FAMILY * len(FAMILIES):
        raise ValueError("v6_9_1 review query selection drift")
    return selected


def _vector_results_for_review_queries(
    root: Path,
    selected_queries: Sequence[Mapping[str, Any]],
) -> tuple[list[v63.RetrievalResult], dict[str, Any]]:  # type: ignore[name-defined]
    index_path = root / v63.FAISS_INDEX_PATH
    id_map_path = root / v63.FAISS_ID_MAP_PATH
    if not index_path.exists() or not id_map_path.exists():
        raise ValueError("v6_9_1 requires existing v6_3 FAISS index and id map")
    id_map = json.loads(id_map_path.read_text(encoding="utf-8"))
    index = v63.faiss.read_index(str(index_path))
    embedder = v63._build_embedder()  # type: ignore[attr-defined]
    query_values = [_clean(query.get("query_text")) for query in selected_queries]
    started = time.perf_counter()
    query_vectors = embedder.embed_queries(query_values)
    embedding_latency_ms = round((time.perf_counter() - started) * 1000, 4)
    v63.validate_embedding_matrix(
        query_vectors,
        expected_count=len(selected_queries),
        embedding_model_identifier=getattr(embedder, "model_name", v63.EMBEDDING_MODEL_IDENTIFIER),
    )

    query_latencies: list[float] = []
    candidate_counts: list[int] = []
    results: list[v63.RetrievalResult] = []
    for row_idx, query in enumerate(selected_queries):
        qvec = v63.np.ascontiguousarray(query_vectors[row_idx : row_idx + 1], dtype=v63.np.float32)
        query_started = time.perf_counter()
        scores, ids = index.search(qvec, min(MAX_CANDIDATES_PER_BACKEND, len(id_map)))
        latency_ms = round((time.perf_counter() - query_started) * 1000, 4)
        query_latencies.append(latency_ms)
        candidates: list[v63.Candidate] = []
        rank = 1
        for faiss_id, score in zip(ids[0], scores[0]):
            if int(faiss_id) < 0:
                continue
            mapped = id_map[int(faiss_id)]
            if _family(mapped.get("source_family")) != _family(query.get("source_family")):
                continue
            candidates.append(
                v63.Candidate(
                    candidate_id=_clean(mapped.get("payload_id")),
                    search_unit_id=_clean(mapped.get("search_unit_id")),
                    search_view_id=_clean(mapped.get("search_view_id")),
                    source_atom_ids=tuple(mapped.get("source_atom_ids") or []),
                    source_family=_family(mapped.get("source_family")),
                    score=round(float(score), 6),
                    rank=rank,
                    retrieval_backend=v63.VECTOR_BACKEND_KIND,
                    metadata={
                        "candidate_only_payload_role": "SearchView",
                        "evidence_truth_role": "SourceAtom/EvidenceBundle",
                        "source_text_sha256": _clean(mapped.get("source_text_sha256")),
                    },
                )
            )
            rank += 1
            if len(candidates) >= MAX_CANDIDATES_PER_BACKEND:
                break
        candidate_counts.append(len(candidates))
        results.append(
            v63.RetrievalResult(
                row_key=_clean(query.get("row_key")),
                query_text=_clean(query.get("query_text")),
                source_family=_family(query.get("source_family")),
                backend_kind=v63.VECTOR_BACKEND_KIND,
                candidates=tuple(candidates),
                latency_ms=latency_ms,
            )
        )
    status = {
        "query_count": len(selected_queries),
        "candidate_count_distribution": v63._distribution(candidate_counts),  # type: ignore[attr-defined]
        "query_latency_ms": v63._distribution(query_latencies),  # type: ignore[attr-defined]
        "query_embedding_latency_ms_total": embedding_latency_ms,
        "faiss_index_path": v63.FAISS_INDEX_PATH.as_posix(),
        "faiss_id_map_path": v63.FAISS_ID_MAP_PATH.as_posix(),
        "production_index_mutation": False,
    }
    return results, status


def _safe_locator_from_source_atom(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {"locator_available": False}
    payload = row.get("canonical_citation_payload")
    if not isinstance(payload, Mapping):
        payload = row.get("raw_locator") if isinstance(row.get("raw_locator"), Mapping) else {}
    mapping = {
        "documentVersionId": "document_version_id",
        "locatorFingerprint": "locator_fingerprint",
        "stable_locator_fingerprint": "locator_fingerprint",
        "sourceFamily": "source_family",
        "searchUnitId": "registry_search_unit_id",
        "unitId": "registry_search_unit_id",
    }
    allowed = {
        "bbox",
        "cell",
        "cell_range",
        "column_index",
        "document_id",
        "document_version_id",
        "header_path",
        "locator_fingerprint",
        "page",
        "page_index",
        "physical_page_index",
        "range",
        "region_type",
        "registry_search_unit_id",
        "row_index",
        "row_label",
        "sheet",
        "sheet_name",
        "source_family",
        "target_column",
        "table_id",
        "workbook_version_id",
    }
    safe: dict[str, Any] = {"locator_available": True}
    for raw_key, value in payload.items():
        key = mapping.get(_clean(raw_key), _clean(raw_key))
        if key in allowed and value not in ("", None, []):
            safe[key] = value
    for raw_key in ("source_family", "document_version_id", "document_id", "workbook_version_id"):
        if raw_key not in safe and _clean(row.get(raw_key)):
            safe[raw_key] = _clean(row.get(raw_key))
    if _clean(row.get("content_hash")):
        safe["source_atom_content_hash"] = _clean(row.get("content_hash"))
    return safe


def _source_atom_id_from_row(row: Mapping[str, Any]) -> str:
    return _clean(row.get("source_atom_id") or row.get("sourceAtomId"))


def _load_safe_locators(root: Path, source_atom_ids: set[str]) -> dict[str, dict[str, Any]]:
    path = root / SOURCE_ATOM_REGISTRY_PATH
    if not path.exists():
        return {source_atom_id: {"locator_available": False} for source_atom_id in source_atom_ids}
    locators: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            source_atom_id = _source_atom_id_from_row(row)
            if source_atom_id in source_atom_ids:
                locators[source_atom_id] = _safe_locator_from_source_atom(row)
                if len(locators) == len(source_atom_ids):
                    break
    for source_atom_id in source_atom_ids:
        locators.setdefault(source_atom_id, {"locator_available": False})
    return locators


def _packet_rows_from_results(
    root: Path,
    *,
    payloads: Sequence[Mapping[str, Any]],
    results_by_backend: Mapping[str, Sequence[v63.RetrievalResult]],  # type: ignore[name-defined]
) -> list[dict[str, Any]]:
    payload_by_id = {_clean(payload.get("payload_id")): payload for payload in payloads}
    source_atom_ids = {
        _clean(candidate.source_atom_ids[0])
        for results in results_by_backend.values()
        for result in results
        for candidate in result.candidates
        if candidate.source_atom_ids
    }
    locators = _load_safe_locators(root, source_atom_ids)
    rows: list[dict[str, Any]] = []
    for backend in BACKENDS:
        for result in results_by_backend[backend]:
            for candidate in result.candidates:
                payload = payload_by_id.get(candidate.candidate_id, {})
                source_atom_id = _clean(candidate.source_atom_ids[0] if candidate.source_atom_ids else "")
                locator = locators.get(source_atom_id) or {"locator_available": False}
                excerpt_text = _clean(payload.get("bm25_text"))
                row = {
                    "schema_version": f"{SHORT_RUN_ID}_review_packet_row_v1",
                    "review_packet_id": LOGICAL_RUN_KEY,
                    "query_id": result.row_key,
                    "source_family": candidate.source_family,
                    "backend": backend,
                    "rank": candidate.rank,
                    "candidate_id": candidate.candidate_id,
                    "search_unit_id": candidate.search_unit_id,
                    "search_view_id": candidate.search_view_id,
                    "source_atom_id": source_atom_id,
                    "locator": locator,
                    "locator_sha256": _sha256_json(locator),
                    "excerpt_preview": _short_preview(excerpt_text),
                    "excerpt_sha256": _clean((candidate.metadata or {}).get("source_text_sha256"))
                    or _sha256_text(excerpt_text),
                    "query_text_preview": _short_preview(result.query_text, 120),
                    "query_text_sha256": _sha256_text(result.query_text),
                    "candidate_score": candidate.score,
                    "candidate_surface_role": "SearchView candidate-only",
                    "evidence_truth_role": "SourceAtom/EvidenceBundle",
                    "tool_output": False,
                    "review_status": "pending_user_review",
                    "relevance_label": "",
                    "answerability_label": "",
                    "official_positive_qrels": "",
                    "denominator_inclusion": "",
                    "expected_answer_or_evidence_decision": "",
                    "review_notes": "",
                }
                rows.append(row)
    return rows


def _review_packet_summary(rows: Sequence[Mapping[str, Any]], selected_queries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    query_family_counts = Counter(_family(query.get("source_family")) for query in selected_queries)
    row_family_counts = Counter(_family(row.get("source_family")) for row in rows)
    backend_counts = Counter(_clean(row.get("backend")) for row in rows)
    blank_rows = sum(
        1 for row in rows if all(_clean(row.get(field)) == "" for field in USER_OWNED_REVIEW_FIELDS)
    )
    return {
        "review_packet_created": True,
        "review_packet_location": "jsonl_and_csv_sidecars",
        "review_packet_row_count": len(rows),
        "selected_query_count": len(selected_queries),
        "selected_queries_by_family": _counter_dict(query_family_counts),
        "candidate_rows_by_family": _counter_dict(row_family_counts),
        "candidate_rows_by_backend": {backend: int(backend_counts.get(backend, 0)) for backend in BACKENDS},
        "review_fields_left_blank": True,
        "user_owned_field_filled_count": len(rows) * len(USER_OWNED_REVIEW_FIELDS) - blank_rows * len(USER_OWNED_REVIEW_FIELDS),
        "human_owned_blank_rows": blank_rows,
        "user_owned_review_fields": list(USER_OWNED_REVIEW_FIELDS),
        "candidate_rows_are_metric_hits": False,
        "metric_computed_from_packet": False,
        "packet_includes_tool_outputs": False,
    }


def _metric_gate(
    *,
    v65_summary: Mapping[str, Any],
    v68_summary: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "gate_status": "closed_pending_user_review",
        "safe_read_only_denominator_available": False,
        "safe_read_only_denominator_source": "",
        "legacy_safe_read_only_denominator_source": v65.LOGICAL_RUN_KEY,
        "legacy_bridgeable_rows": v65_summary["bridgeable_rows"],
        "legacy_bridge_blocked_reason": LEGACY_BRIDGE_BLOCKED_REASON,
        "computed_only_denominator": 0,
        "coverage_adjusted_denominator": v68_summary["coverage_adjusted_denominator"],
        "retrieval_quality_metric_computed": False,
        "answer_quality_metric_computed": False,
        "blocked_reason": BLOCKED_REASON,
        "blocked_by_user_owned_decisions": [
            "relevance_label",
            "answerability_label",
            "official_positive_qrels",
            "denominator_inclusion",
            "expected_answer_or_evidence_decision",
        ],
        "hit_at_k_computed": False,
        "mrr_computed": False,
        "ndcg_computed": False,
        "hit_at_k": None,
        "mrr": None,
        "ndcg": None,
        "tool_outputs_excluded_from_true_rag_metrics": True,
        "searchview_vector_payload_candidate_only": True,
        "sourceatom_evidencebundle_evidence_truth": True,
    }


def _index_lineage_gate(v63_summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "index_lineage_recorded_for_review_packet": True,
        "source_artifact": v63_summary["source_artifact"],
        "source_artifact_sha256": v63_summary["source_artifact_sha256"],
        "faiss_index_path": v63_summary["faiss_index_path"],
        "faiss_index_sha256": v63_summary["faiss_index_sha256"],
        "faiss_id_map_path": v63_summary["faiss_id_map_path"],
        "faiss_id_map_sha256": v63_summary["faiss_id_map_sha256"],
        "embedding_model_identifier": v63_summary["embedding_model_identifier"],
        "embedding_model_revision_or_hash_present": v63_summary["embedding_model_revision_or_hash_present"],
        "index_version_present": False,
        "index_lineage_review_required_before_metric": True,
    }


def _build_review_packet(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    payloads, queries = _build_current_payloads(root)
    selected_queries = _select_review_queries(queries)
    vector_results, vector_status = _vector_results_for_review_queries(root, selected_queries)
    bm25_results, bm25_status = v63._bm25_results(payloads, selected_queries)  # type: ignore[attr-defined]
    hybrid_results, hybrid_status = v63._hybrid_results(vector_results, bm25_results)  # type: ignore[attr-defined]
    results_by_backend = {
        "vector": vector_results,
        "bm25": bm25_results,
        "hybrid": hybrid_results,
    }
    rows = _packet_rows_from_results(root, payloads=payloads, results_by_backend=results_by_backend)
    packet_summary = _review_packet_summary(rows, selected_queries)
    retrieval_status = {
        "selected_query_count": len(selected_queries),
        "selected_queries": [
            {
                "query_id": _clean(query.get("row_key")),
                "source_family": _family(query.get("source_family")),
                "query_text_sha256": _sha256_text(_clean(query.get("query_text"))),
            }
            for query in selected_queries
        ],
        "vector_review_query_status": vector_status,
        "bm25_review_query_status": bm25_status,
        "hybrid_review_query_status": hybrid_status,
    }
    return rows, packet_summary, retrieval_status


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    v6_3_report: Mapping[str, Any] | None = None,
    v6_5_report: Mapping[str, Any] | None = None,
    v6_8_report: Mapping[str, Any] | None = None,
    v6_9_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source_v63 = _load_v63(repo_root, v6_3_report)
    source_v65 = _load_v65(repo_root, v6_5_report)
    source_v68 = _load_v68(repo_root, v6_8_report)
    source_v69 = _load_v69(repo_root, v6_9_report)
    v63_summary = _source_v63_summary(source_v63)
    v65_summary = _source_v65_summary(source_v65)
    v68_summary = _source_v68_summary(source_v68)
    review_rows, packet_summary, retrieval_status = _build_review_packet(repo_root)
    gate = _metric_gate(v65_summary=v65_summary, v68_summary=v68_summary)
    report: dict[str, Any] = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "run_id": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at,
        "diagnostic_only": True,
        "non_production": True,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "current_alias_policy": {
            "current_moved": False,
            "current_remains": CURRENT_RESOLVES_TO,
            "current_moved_from": "",
            "current_moved_to": "",
            "rollback_key": ROLLBACK_KEY,
            "movement_condition": "none; v6_9_1 is an additive pre-review packet and does not move current",
            "official_product_promotion_live_readiness_claim": False,
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": {},
        "generated_artifacts": [
            REPORT_PATH.as_posix(),
            REVIEW_PACKET_JSONL_PATH.as_posix(),
            REVIEW_PACKET_CSV_PATH.as_posix(),
        ],
        "consolidated_report_policy": {
            "primary_report_path": REPORT_PATH.as_posix(),
            "review_packet_jsonl_created": True,
            "review_packet_csv_created": True,
            "review_packet_sidecars_reason": "human qrels/denominator review needs sortable candidate rows",
            "separate_metric_results_json_created": False,
            "separate_denominator_manifest_jsonl_created": False,
            "separate_approved_qrels_jsonl_created": False,
        },
        "source_v6_3_current_candidate_surface_check": v63_summary,
        "source_v6_5_bridge_check": v65_summary,
        "source_v6_8_retrieval_gate_check": v68_summary,
        "source_v6_9_answer_quality_gate_check": _source_v69_summary(source_v69),
        "retrieval_smoke_review_packet": {
            "packet_location": "jsonl_and_csv_sidecars",
            "jsonl_path": REVIEW_PACKET_JSONL_PATH.as_posix(),
            "csv_path": REVIEW_PACKET_CSV_PATH.as_posix(),
            "rows": review_rows,
            **packet_summary,
        },
        "retrieval_smoke_review_packet_summary": packet_summary,
        "retrieval_review_query_execution": retrieval_status,
        "metric_unlock_diagnosis": {
            "metric_can_open_now": False,
            "fail_closed": True,
            "blocked_reason": BLOCKED_REASON,
            "legacy_v5_5_v6_5_bridge_forced": False,
            "current_based_qrels_review_packet_needed": True,
            "approved_current_qrels_denominator_found": False,
            "safe_to_compute_hit_mrr_ndcg": False,
            "reasoning_summary": (
                "v6_5 approved qrels do not bridge to the current v6 SearchUnit/SearchView/SourceAtom surface; "
                "a new user-reviewed current-surface packet is required before any retrieval ranking metric."
            ),
        },
        "metric_gate": gate,
        "index_lineage_gate": _index_lineage_gate(v63_summary),
        "candidate_generation_input_policy": {
            "candidate_generation_allowed_input_surface": ["query_text", "allowed_corpus_index_source_surfaces"],
            "expected_supporting_gold_qrels_used_for_candidate_generation": False,
            "target_ids_used_for_candidate_generation": False,
            "row_or_case_ids_used_for_candidate_generation": False,
            "source_title_shortcuts_used_for_candidate_generation": False,
            "workbook_file_name_shortcuts_used_for_candidate_generation": False,
            "tool_outputs_used_for_true_rag_metric": False,
        },
        "protected_surface_check": _protected_surface_check(),
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "user_review_packet_created": True,
        "review_packet_row_count": packet_summary["review_packet_row_count"],
        "human_owned_decisions_filled": False,
        **{field: False for field in REQUIRED_FALSE_REPORT_FIELDS},
        "verification_commands": [
            "python -X utf8 -m py_compile ai/eval/rag_v691_retrieval_smoke_pre_review_packet_nonprod.py ai/scripts/rag_eval.py",
            "python -X utf8 -m pytest ai/tests/test_rag_v691_retrieval_smoke_pre_review_packet_nonprod_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_9_1_retrieval_smoke_pre_review_packet_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_8_metric_gated_retrieval_quality_engineering_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_9_answer_quality_gate_packet_nonprod --check",
            "python -X utf8 docs/portfolio/build_portfolio_pdf.py",
            "python -X utf8 docs/portfolio/build_resume_pdf.py",
        ],
    }
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != LOGICAL_RUN_KEY or report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_9_1 run identity drift")
    if report.get("schema_version") != f"{SHORT_RUN_ID}_report_v1":
        raise ValueError("v6_9_1 schema drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_9_1 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_9_1 current alias drift")
    if (report.get("current_alias_policy") or {}).get("current_moved") is not False:
        raise ValueError("v6_9_1 must not move current")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_9_1 rollback key drift")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v6_9_1 diagnostic/non-production flag missing")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            if key == "retrieval_quality_metric_computed":
                raise ValueError("v6_9_1 retrieval quality metric opened")
            if key == "answer_quality_metric_computed":
                raise ValueError("v6_9_1 answer quality metric opened")
            raise ValueError(f"v6_9_1 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if int(report.get(key) or 0) != 0:
            raise ValueError(f"v6_9_1 official metric row field opened: {key}")
    if report.get("human_owned_decisions_filled") is not False:
        raise ValueError("v6_9_1 human-owned decisions filled")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True:
        raise ValueError("v6_9_1 protected surface check failed")
    if protected.get("mutated_paths") or protected.get("protected_namespaces_touched"):
        raise ValueError("v6_9_1 protected namespaces touched")


def _require_sources(report: Mapping[str, Any]) -> None:
    v63_source = report.get("source_v6_3_current_candidate_surface_check") or {}
    if v63_source.get("source_derived_search_unit_count") != 300:
        raise ValueError("v6_9_1 v6_3 SearchUnit count drift")
    if v63_source.get("source_derived_search_view_count") != 300:
        raise ValueError("v6_9_1 v6_3 SearchView count drift")
    if v63_source.get("source_family_counts") != {"PDF": 100, "TEXT": 100, "XLSX": 100}:
        raise ValueError("v6_9_1 v6_3 family balance drift")
    v65_source = report.get("source_v6_5_bridge_check") or {}
    if v65_source.get("bridgeable_rows") != 0:
        raise ValueError("v6_9_1 legacy bridge unexpectedly opened")
    v68_source = report.get("source_v6_8_retrieval_gate_check") or {}
    if v68_source.get("safe_read_only_denominator_available") is not False:
        raise ValueError("v6_9_1 source v6_8 denominator unexpectedly opened")
    if v68_source.get("computed_only_denominator") != 0:
        raise ValueError("v6_9_1 source v6_8 computed denominator opened")
    if v68_source.get("coverage_adjusted_denominator") != 300:
        raise ValueError("v6_9_1 source v6_8 coverage denominator drift")
    if v68_source.get("retrieval_quality_metric_computed") is not False:
        raise ValueError("v6_9_1 source v6_8 retrieval metric opened")
    by_backend = v68_source.get("by_backend") or {}
    expected_backend = {
        "vector": (299, 299),
        "bm25": (300, 300),
        "hybrid": (300, 300),
    }
    for backend, (with_candidates, hydrated) in expected_backend.items():
        counters = by_backend.get(backend) or {}
        if counters.get("with_candidates_rows") != with_candidates or counters.get("hydrated_rows") != hydrated:
            raise ValueError(f"v6_9_1 source v6_8 {backend} availability drift")
    v69_source = report.get("source_v6_9_answer_quality_gate_check") or {}
    if v69_source.get("packet_rows") != 29:
        raise ValueError("v6_9_1 source v6_9 packet row drift")
    if v69_source.get("rows_by_family") != {"PDF": 4, "TEXT": 6, "XLSX": 19}:
        raise ValueError("v6_9_1 source v6_9 family drift")
    if (v69_source.get("agentic_verification_state_counts") or {}).get("passed") != 10:
        raise ValueError("v6_9_1 source v6_9 passed count drift")
    if (v69_source.get("agentic_verification_state_counts") or {}).get("skipped_no_answer") != 19:
        raise ValueError("v6_9_1 source v6_9 skipped count drift")


def _require_metric_gate(report: Mapping[str, Any]) -> None:
    gate = report.get("metric_gate") or {}
    if gate.get("gate_status") != "closed_pending_user_review":
        raise ValueError("v6_9_1 metric gate status drift")
    if gate.get("safe_read_only_denominator_available") is not False:
        raise ValueError("v6_9_1 safe denominator unexpectedly opened")
    if gate.get("computed_only_denominator") != 0:
        raise ValueError("v6_9_1 computed-only denominator opened")
    if gate.get("coverage_adjusted_denominator") != 300:
        raise ValueError("v6_9_1 coverage denominator drift")
    if gate.get("blocked_reason") != BLOCKED_REASON:
        raise ValueError("v6_9_1 blocked reason drift")
    for key in ("hit_at_k_computed", "mrr_computed", "ndcg_computed"):
        if gate.get(key) is not False:
            raise ValueError(f"v6_9_1 retrieval metric component opened: {key}")
    for key in ("hit_at_k", "mrr", "ndcg"):
        if gate.get(key) is not None:
            raise ValueError(f"v6_9_1 retrieval metric value opened: {key}")
    if gate.get("tool_outputs_excluded_from_true_rag_metrics") is not True:
        raise ValueError("v6_9_1 tool outputs not excluded from true RAG metrics")
    diagnosis = report.get("metric_unlock_diagnosis") or {}
    if diagnosis.get("metric_can_open_now") is not False or diagnosis.get("fail_closed") is not True:
        raise ValueError("v6_9_1 metric unlock diagnosis drift")
    if diagnosis.get("legacy_v5_5_v6_5_bridge_forced") is not False:
        raise ValueError("v6_9_1 forced legacy bridge")
    if diagnosis.get("current_based_qrels_review_packet_needed") is not True:
        raise ValueError("v6_9_1 current qrels review packet requirement missing")


def _require_review_packet(report: Mapping[str, Any]) -> None:
    packet = report.get("retrieval_smoke_review_packet") or {}
    summary = report.get("retrieval_smoke_review_packet_summary") or {}
    rows = list(packet.get("rows") or [])
    if packet.get("review_packet_created") is not True or summary.get("review_packet_created") is not True:
        raise ValueError("v6_9_1 review packet missing")
    if packet.get("review_fields_left_blank") is not True or summary.get("review_fields_left_blank") is not True:
        raise ValueError("v6_9_1 review fields not left blank")
    if packet.get("metric_computed_from_packet") is not False:
        raise ValueError("v6_9_1 metric computed from unreviewed packet")
    if packet.get("packet_includes_tool_outputs") is not False:
        raise ValueError("v6_9_1 review packet includes tool outputs")
    if len(rows) != packet.get("review_packet_row_count") or len(rows) != summary.get("review_packet_row_count"):
        raise ValueError("v6_9_1 review packet row count drift")
    if summary.get("selected_query_count") != QUERY_ROWS_PER_FAMILY * len(FAMILIES):
        raise ValueError("v6_9_1 selected query count drift")
    if summary.get("selected_queries_by_family") != {"PDF": 3, "TEXT": 3, "XLSX": 3}:
        raise ValueError("v6_9_1 selected query family drift")
    backend_counts = summary.get("candidate_rows_by_backend") or {}
    if set(backend_counts) != set(BACKENDS) or any(int(backend_counts.get(backend) or 0) <= 0 for backend in BACKENDS):
        raise ValueError("v6_9_1 backend review rows missing")
    if summary.get("user_owned_field_filled_count") != 0:
        raise ValueError("v6_9_1 user-owned review field filled")
    for row in rows:
        for field in (
            "query_id",
            "source_family",
            "backend",
            "candidate_id",
            "search_unit_id",
            "search_view_id",
            "source_atom_id",
            "locator",
            "locator_sha256",
            "excerpt_sha256",
        ):
            if row.get(field) in ("", None, []):
                raise ValueError(f"v6_9_1 review row missing {field}")
        if row.get("backend") not in BACKENDS:
            raise ValueError("v6_9_1 backend drift")
        if row.get("source_family") not in FAMILIES:
            raise ValueError("v6_9_1 family drift")
        if row.get("tool_output") is not False:
            raise ValueError("v6_9_1 tool output entered review packet")
        if row.get("candidate_surface_role") != "SearchView candidate-only":
            raise ValueError("v6_9_1 candidate/evidence boundary drift")
        if row.get("evidence_truth_role") != "SourceAtom/EvidenceBundle":
            raise ValueError("v6_9_1 evidence truth boundary drift")
        for field in USER_OWNED_REVIEW_FIELDS:
            if row.get(field) != "":
                raise ValueError("v6_9_1 user-owned review field filled")


def _require_candidate_generation_policy(report: Mapping[str, Any]) -> None:
    policy = report.get("candidate_generation_input_policy") or {}
    for key in (
        "expected_supporting_gold_qrels_used_for_candidate_generation",
        "target_ids_used_for_candidate_generation",
        "row_or_case_ids_used_for_candidate_generation",
        "source_title_shortcuts_used_for_candidate_generation",
        "workbook_file_name_shortcuts_used_for_candidate_generation",
        "tool_outputs_used_for_true_rag_metric",
    ):
        if policy.get(key) is not False:
            raise ValueError(f"v6_9_1 candidate generation boundary opened: {key}")


def _require_artifacts(report: Mapping[str, Any], root: Path | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("review_packet_jsonl_created") is not True or policy.get("review_packet_csv_created") is not True:
        raise ValueError("v6_9_1 review packet sidecar policy missing")
    if root is None:
        return
    run_root = root / RUN_ROOT
    if not run_root.exists():
        return
    names = {path.name for path in run_root.iterdir() if path.is_file()}
    expected_names = {"report.json", "retrieval_smoke_review_packet.jsonl", "retrieval_smoke_review_packet.csv"}
    if names != expected_names:
        raise ValueError(f"v6_9_1 artifact set drift: {sorted(names)}")
    hashes = report.get("artifact_sha256") or {}
    if hashes.get("retrieval_smoke_review_packet_jsonl_sha256"):
        actual = common.sha256_file(root / REVIEW_PACKET_JSONL_PATH)
        if actual != hashes["retrieval_smoke_review_packet_jsonl_sha256"]:
            raise ValueError("v6_9_1 review packet jsonl hash drift")
    if hashes.get("retrieval_smoke_review_packet_csv_sha256"):
        actual = common.sha256_file(root / REVIEW_PACKET_CSV_PATH)
        if actual != hashes["retrieval_smoke_review_packet_csv_sha256"]:
            raise ValueError("v6_9_1 review packet csv hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    repo_root = Path(root) if root is not None else None
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_sources(report)
    _require_metric_gate(report)
    _require_review_packet(report)
    _require_candidate_generation_policy(report)
    _require_artifacts(report, repo_root)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v6_9_1")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            csv_row: dict[str, Any] = {}
            for field in CSV_FIELDS:
                value = row.get(field)
                if isinstance(value, (dict, list)):
                    csv_row[field] = json.dumps(value, ensure_ascii=False, sort_keys=True)
                else:
                    csv_row[field] = value
            writer.writerow(csv_row)


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    payload["artifact_sha256"] = {}
    rows = list((payload.get("retrieval_smoke_review_packet") or {}).get("rows") or [])
    common.write_jsonl(repo_root / REVIEW_PACKET_JSONL_PATH, rows)
    _write_csv(repo_root / REVIEW_PACKET_CSV_PATH, rows)
    artifact_hashes = {
        "retrieval_smoke_review_packet_jsonl_sha256": common.sha256_file(repo_root / REVIEW_PACKET_JSONL_PATH),
        "retrieval_smoke_review_packet_csv_sha256": common.sha256_file(repo_root / REVIEW_PACKET_CSV_PATH),
    }
    payload["artifact_sha256"] = dict(artifact_hashes)
    common.write_json(repo_root / REPORT_PATH, payload)
    artifact_hashes["report_json_sha256"] = common.sha256_file(repo_root / REPORT_PATH)
    payload["artifact_sha256"] = dict(artifact_hashes)
    check_report(payload, root=root)
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    gate = report["metric_gate"]
    packet = report["retrieval_smoke_review_packet_summary"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved": False,
        "rollback_key": ROLLBACK_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "retrieval_quality_metric_computed": False,
        "answer_quality_metric_computed": False,
        "safe_read_only_denominator_available": gate["safe_read_only_denominator_available"],
        "computed_only_denominator": gate["computed_only_denominator"],
        "coverage_adjusted_denominator": gate["coverage_adjusted_denominator"],
        "blocked_reason": gate["blocked_reason"],
        "hit_at_k_computed": False,
        "mrr_computed": False,
        "ndcg_computed": False,
        "review_packet_created": True,
        "review_packet_row_count": packet["review_packet_row_count"],
        "human_owned_decisions_filled": False,
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
    rows = [row for row in rows if row.get("logical_run_key") != LOGICAL_RUN_KEY and row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def require_status_report_hash(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    if not status_path.exists():
        raise ValueError("v6_9_1 status report hash missing: status.jsonl not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v6_9_1 status report hash missing: status event not found")
    latest = rows[-1]
    paths = {
        "report_json_sha256": repo_root / REPORT_PATH,
        "retrieval_smoke_review_packet_jsonl_sha256": repo_root / REVIEW_PACKET_JSONL_PATH,
        "retrieval_smoke_review_packet_csv_sha256": repo_root / REVIEW_PACKET_CSV_PATH,
    }
    for hash_key, path in paths.items():
        expected = _clean((latest.get("artifact_sha256") or {}).get(hash_key))
        if not expected:
            raise ValueError(f"v6_9_1 status artifact hash missing: {hash_key}")
        if not path.exists():
            raise ValueError(f"v6_9_1 status artifact missing: {path}")
        actual = common.sha256_file(path)
        if expected != actual:
            raise ValueError(f"v6_9_1 status artifact hash drift for {hash_key}: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_9_1 status current alias drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    packet = report["retrieval_smoke_review_packet_summary"]
    gate = report["metric_gate"]
    backend_counts = packet["candidate_rows_by_backend"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is an additive, diagnostic-only current-surface "
        f"retrieval smoke review packet. current remains `{CURRENT_RESOLVES_TO}`. 300개 SearchUnit/SearchView 기준 "
        "Dense/BM25/Hybrid 후보 가용성 및 hydration을 진단했고, qrels/denominator 승인 전까지 Hit@K/MRR/nDCG를 열지 않았다. "
        f"review_packet_rows={packet['review_packet_row_count']}; blocked_reason={gate['blocked_reason']}; "
        "human-owned relevance/answerability/qrels/denominator/expected-evidence fields remain blank."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        f"- Review packet: selected_queries={packet['selected_query_count']}; selected_queries_by_family="
        f"{packet['selected_queries_by_family']}; candidate_rows_by_backend={backend_counts}; "
        f"candidate_rows_by_family={packet['candidate_rows_by_family']}.\n"
        "- Metric gate: retrieval_quality_metric_computed=false; answer_quality_metric_computed=false; "
        f"computed_only_denominator=0; coverage_adjusted_denominator={gate['coverage_adjusted_denominator']}; "
        f"blocked_reason={gate['blocked_reason']}; Hit@K/MRR/nDCG remain uncomputed until user-approved current qrels/denominator exists.\n"
        "- Boundary: SearchView/vector payload is candidate-only; SourceAtom/EvidenceBundle is evidence truth; tool-output rows are excluded from retrieval ranking metrics. "
        "human-owned relevance, answerability, qrels, denominator, and expected-evidence fields remain blank."
    )
    triage = (
        f"- {SHORT_RUN_ID}: v5_5/v6_5 bridge remains unusable for current metric unlock "
        f"(bridgeable_rows={gate['legacy_bridgeable_rows']}; legacy_blocked_reason={gate['legacy_bridge_blocked_reason']}). "
        "A new current SearchUnit/SearchView review packet was created with blank human-owned relevance, answerability, qrels, "
        "denominator, and expected-evidence fields. Hit@K/MRR/nDCG retrieval ranking metrics remain closed."
    )
    return progress, measurements, triage


def _upsert_doc(root: Path, path: Path, *, start: str, end: str, block: str) -> None:
    full_path = root / path
    text = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(common.upsert_block_at_top(text, start_marker=start, end_marker=end, block=block), encoding="utf-8")


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    progress, measurements, triage = _doc_fragments(report)
    _upsert_doc(
        repo_root,
        PROGRESS_DOC,
        start=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress,
    )
    _upsert_doc(
        repo_root,
        MEASUREMENTS_DOC,
        start=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
        end=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
        block=measurements,
    )
    _upsert_doc(
        repo_root,
        TRIAGE_DOC,
        start=f"<!-- {SHORT_RUN_ID}:triage-entry:start -->",
        end=f"<!-- {SHORT_RUN_ID}:triage-entry:end -->",
        block=triage,
    )
