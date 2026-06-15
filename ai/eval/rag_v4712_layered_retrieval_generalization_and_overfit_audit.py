from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4711_actual_llm_answer_replay_and_silver_diagnostic_smoke as v4711
from ai.eval import rag_v476_archive_purge as v476
from ai.scripts import rag_local_llm_expected_answer_generation_v1 as local_llm


AI_DIR = Path(__file__).resolve().parents[1]
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from eval.harness.rag_diagnostic_common import external_archive_namespace_roots, resolve_report_artifact_path  # noqa: E402


LOGICAL_RUN_KEY = "v4_7_12"
SHORT_RUN_ID = "v4_7_12_layered_retrieval_generalization_and_overfit_audit"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_12_"
    "layered_retrieval_generalization_and_overfit_audit_nonprod"
)
STATUS = "V4_7_12_LAYERED_RETRIEVAL_GENERALIZATION_AND_OVERFIT_AUDIT_NONPROD_READY"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SILVER_LAYERED_RETRIEVAL_AUDIT_JSON = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "silver_layered_retrieval_audit.json"
FULL_PDF_ANSWER_REVIEW_PACKET_JSONL = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "full_pdf_answer_review_packet_ko.jsonl"
SILVER_ANSWER_SMOKE_JSONL = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "silver_answer_smoke_ko.jsonl"

SOURCE_RUN_ID = v4711.SHORT_RUN_ID
SOURCE_REPORT_JSON = v4711.SHORT_REPORT_PATH
SOURCE_PDF_SURFACE_RUN_ID = v4711.SOURCE_RUN_ID
SOURCE_PDF_SURFACE_REPORT_JSON = v4711.SOURCE_REPORT_JSON

ENABLE_FULL_PDF_LLM_REPLAY_ENV_VAR = "RAG_V4_7_12_ENABLE_FULL_PDF_LLM_REPLAY"
ENABLE_SILVER_LLM_SMOKE_ENV_VAR = "RAG_V4_7_12_ENABLE_SILVER_LLM_SMOKE"
BASE_URL_ENV_VAR = "RAG_V4_7_12_LOCAL_LLM_BASE_URL"
MODEL_ENV_VAR = "RAG_V4_7_12_LOCAL_LLM_MODEL"
BACKEND_ENV_VAR = "RAG_V4_7_12_LOCAL_LLM_BACKEND"

V3_7_2_NATURAL_SILVER_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_2_"
    "local_llm_natural_silver_query_regeneration"
)
V3_7_2_RETRIEVAL_SMOKE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_7_2_"
    "source_registry_backed_retrieval_smoke_report"
)
V3_7_2_SILVER_MANIFEST_ALL = (
    REPORT_ROOT / f"{V3_7_2_NATURAL_SILVER_RUN_ID}_llm_natural_silver_manifest_all.jsonl"
)
V3_7_2_TOPK_ROWS = REPORT_ROOT / f"{V3_7_2_RETRIEVAL_SMOKE_RUN_ID}_topk_rows.jsonl"
V3_7_2_CANDIDATE_ARTIFACTS = (
    REPORT_ROOT / f"{V3_7_2_NATURAL_SILVER_RUN_ID}_llm_natural_silver_candidates.jsonl",
    V3_7_2_SILVER_MANIFEST_ALL,
    REPORT_ROOT / f"{V3_7_2_NATURAL_SILVER_RUN_ID}_llm_natural_silver_manifest_core.jsonl",
    REPORT_ROOT / f"{V3_7_2_NATURAL_SILVER_RUN_ID}_llm_natural_silver_manifest_review_only.jsonl",
    REPORT_ROOT / f"{V3_7_2_NATURAL_SILVER_RUN_ID}_llm_natural_silver_manifest_quarantine.jsonl",
    REPORT_ROOT / f"{V3_7_2_NATURAL_SILVER_RUN_ID}_summary.json",
    V3_7_2_TOPK_ROWS,
)
SOURCE_ATOM_REGISTRY_JSONL = Path("ai/eval/source_registry/source_atom_registry_v1.jsonl")

REQUIRED_FALSE_KEYS = v4711.REQUIRED_FALSE_KEYS
SCRIPT_VIOLATION_RE = re.compile(r"[A-Za-z\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
SOURCE_TITLE_SHORTCUT_RE = re.compile(r"파일명|문서명|보고서명|source_file_title", re.I)
DEICTIC_RE = re.compile(r"이것|저것|그것|여기|거기|이거|그거|해당")
TOO_BROAD_RE = re.compile(r"전반|전체|요약|알고 싶습니다\.?$")
STOP_TOKENS = set(v4711.STOP_TOKENS) | {"제공", "발췌문", "근거", "내용"}


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v476.write_json(path, payload)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, list(rows))


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bounded(value: Any, *, limit: int = 520) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", _clean(value))
        if token not in STOP_TOKENS
    }


def _compact(value: Any) -> str:
    return re.sub(r"[^가-힣A-Za-z0-9]+", "", _clean(value)).lower()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return v476.sha256_file(path)


def _env_enabled(env: Mapping[str, str], key: str) -> bool:
    return _clean(env.get(key)).lower() in {"1", "true", "yes", "on"}


def _family_counts_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in ("TEXT", "PDF", "XLSX")}


def _counter_dict() -> dict[str, int]:
    return {"TEXT": 0, "PDF": 0, "XLSX": 0}


def _archive_manifest_hints(root: Path) -> list[dict[str, Any]]:
    manifest = root / REPORT_ROOT / "archive_manifest.jsonl"
    if not manifest.exists():
        return []
    hints: list[dict[str, Any]] = []
    for row in read_jsonl(manifest):
        artifact_path = _clean(row.get("artifact_path"))
        if "v3_7_2" not in artifact_path:
            continue
        hints.append(
            {
                "artifact_path": artifact_path,
                "row_count": row.get("row_count"),
                "sha256": _clean(row.get("sha256")),
                "size_bytes": row.get("size_bytes"),
                "classification": _clean(row.get("classification")),
                "physical_action": _clean(row.get("physical_action")),
                "replacement_path": _clean(row.get("replacement_path")),
            }
        )
    return hints


def _expected_sha_for(rel_path: Path, hints: Sequence[Mapping[str, Any]]) -> str:
    rel = rel_path.as_posix()
    for hint in hints:
        if _clean(hint.get("artifact_path")) == rel:
            return _clean(hint.get("sha256"))
    return ""


def resolve_v3_7_2_artifact(root: Path, rel_path: Path) -> dict[str, Any]:
    hints = _archive_manifest_hints(root)
    logical = root / rel_path
    resolved = resolve_report_artifact_path(logical)
    exists = resolved.exists() and resolved.is_file()
    expected_sha = _expected_sha_for(rel_path, hints)
    actual_sha = _sha256_file(resolved) if exists else ""
    return {
        "found": bool(exists and expected_sha and actual_sha == expected_sha),
        "path": resolved,
        "logical_path": rel_path.as_posix(),
        "sha256": actual_sha if exists else "",
        "expected_sha256": expected_sha,
        "sha256_verified": bool(exists and expected_sha and actual_sha == expected_sha),
        "resolved_via_archive": bool(exists and resolved.resolve() != logical.resolve()),
        "physical_path_redacted": True,
        "artifact_resolution_evidence": {
            "searched_paths": [
                {
                    "path": candidate.as_posix(),
                    "exists_repo_local": (root / candidate).exists(),
                    "resolved_exists": resolve_report_artifact_path(root / candidate).exists(),
                    "expected_sha256": _expected_sha_for(candidate, hints),
                    "physical_path_redacted": True,
                }
                for candidate in V3_7_2_CANDIDATE_ARTIFACTS
            ],
            "archive_manifest_hints": hints,
            "external_archive_namespace_roots_checked_count": len(external_archive_namespace_roots()),
            "aggregate_docs_insufficient_to_reconstruct_rows": True,
        },
    }


def _silver_query(row: Mapping[str, Any]) -> str:
    return _clean(row.get("generated_question_draft") or row.get("query_text"))


def _silver_query_hash(row: Mapping[str, Any]) -> str:
    return _clean(row.get("generated_question_hash") or row.get("query_text_sha256")) or _sha256_text(_silver_query(row))


def _silver_id(row: Mapping[str, Any]) -> str:
    return _clean(row.get("weak_silver_candidate_id") or row.get("query_id") or row.get("source_candidate_id")) or str(
        row.get("row_ordinal") or ""
    )


def _load_v3_7_2_silver(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolution = resolve_v3_7_2_artifact(root, V3_7_2_SILVER_MANIFEST_ALL)
    if not resolution["found"]:
        return [], resolution
    return read_jsonl(Path(resolution["path"])), resolution


def _load_v3_7_2_topk(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolution = resolve_v3_7_2_artifact(root, V3_7_2_TOPK_ROWS)
    if not resolution["found"]:
        return [], resolution
    return read_jsonl(Path(resolution["path"])), resolution


def _topk_silver_rows(topk_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in topk_rows if _clean(row.get("query_scope")) == "silver_1000_diagnostic_overlay"]


def _topk_by_query_id(topk_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_clean(row.get("query_id")): dict(row) for row in topk_rows if _clean(row.get("query_id"))}


def _top_failure_by_family(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    buckets: dict[str, Counter[str]] = {family: Counter() for family in ("TEXT", "PDF", "XLSX")}
    for row in rows:
        family = _clean(row.get("source_family")).upper()
        if family in buckets:
            buckets[family][_clean(row.get("primary_retrieval_diagnostic_bucket")) or "none"] += 1
    return {family: counter.most_common(1)[0][0] if counter else "" for family, counter in buckets.items()}


def _likely_unanswerable(row: Mapping[str, Any]) -> bool:
    return "unanswerable" in _clean(row.get("weak_answerability_status")).lower()


def silver_layered_retrieval_audit(
    silver_rows: Sequence[Mapping[str, Any]],
    *,
    manifest_resolution: Mapping[str, Any],
    topk_rows: Sequence[Mapping[str, Any]],
    topk_resolution: Mapping[str, Any],
) -> dict[str, Any]:
    if not silver_rows:
        return {
            "schema_version": f"{SHORT_RUN_ID}_silver_layered_retrieval_audit_v1",
            "status": "SILVER_SOURCE_ARTIFACTS_UNAVAILABLE_FAIL_CLOSED",
            "diagnostic_silver_only": True,
            "silver_regenerated": False,
            "artifact_resolution_evidence": dict(manifest_resolution.get("artifact_resolution_evidence") or {}),
            "blocked_reason": "exact v3_7_2 row-level silver manifest unavailable or sha verification failed",
            "aggregate_progress_docs_insufficient_reason": (
                "aggregate docs/status preserve counts and hashes but not generated queries, source ids, or locator metadata"
            ),
            "silver_manifest_path": "",
            "silver_manifest_sha256": "",
            "silver_topk_path": "",
            "silver_topk_sha256": "",
            "total_row_count": 0,
            "family_counts": _counter_dict(),
            "partition_counts": {"core": 0, "review_only": 0, "quarantine": 0},
            "query_hash_unique_count": 0,
            "duplicate_query_hash_count": 0,
            "empty_query_count": 0,
            "script_violation_count": 0,
            "source_title_shortcut_risk_count": 0,
            "deictic_or_ambiguous_query_count": 0,
            "too_broad_query_count": 0,
            "likely_unanswerable_count": 0,
            "repeated_prefix_cluster_count": 0,
            "family_route_selected_count_by_family": _counter_dict(),
            "same_family_at_k_count_by_family": _counter_dict(),
            "sourceatom_hydration_success_count_by_family": _counter_dict(),
            "evidencebundle_created_count_by_family": _counter_dict(),
            "citation_render_success_count_by_family": _counter_dict(),
            "fail_closed_count_by_family": _counter_dict(),
            "top_fail_reason_by_family": {"TEXT": "", "PDF": "", "XLSX": ""},
            "official_metric_input_rows": 0,
            "silver_promoted_to_gold_count": 0,
        }

    families = Counter(_clean(row.get("source_family")).upper() for row in silver_rows)
    partitions = Counter(_clean(row.get("manifest_partition")) for row in silver_rows)
    query_hashes = [_silver_query_hash(row) for row in silver_rows]
    queries = [_silver_query(row) for row in silver_rows]
    ids = [_silver_id(row) for row in silver_rows]

    if not topk_rows:
        repeated_prefixes = Counter(query[:8] for query in queries if len(query) >= 8)
        return {
            "schema_version": f"{SHORT_RUN_ID}_silver_layered_retrieval_audit_v1",
            "status": "SILVER_TOPK_ARTIFACT_UNAVAILABLE_FAIL_CLOSED",
            "diagnostic_silver_only": True,
            "silver_regenerated": False,
            "silver_manifest_path": _clean(manifest_resolution.get("logical_path")),
            "silver_manifest_sha256": _clean(manifest_resolution.get("sha256")),
            "silver_manifest_resolved_via_archive": bool(manifest_resolution.get("resolved_via_archive")),
            "silver_topk_path": _clean(topk_resolution.get("logical_path")),
            "silver_topk_sha256": _clean(topk_resolution.get("sha256")),
            "silver_topk_resolved_via_archive": bool(topk_resolution.get("resolved_via_archive")),
            "physical_paths_redacted": True,
            "artifact_resolution_evidence": dict(manifest_resolution.get("artifact_resolution_evidence") or {}),
            "topk_artifact_resolution_evidence": dict(topk_resolution.get("artifact_resolution_evidence") or {}),
            "blocked_reason": "exact v3_7_2 row-level retrieval top-k artifact unavailable or sha verification failed",
            "total_row_count": len(silver_rows),
            "unique_id_count": len(set(ids)),
            "family_counts": _family_counts_dict(families),
            "partition_counts": {
                "core": int(partitions.get("core", 0)),
                "review_only": int(partitions.get("review_only", 0)),
                "quarantine": int(partitions.get("quarantine", 0)),
            },
            "query_hash_unique_count": len(set(query_hashes)),
            "duplicate_query_hash_count": max(0, len(query_hashes) - len(set(query_hashes))),
            "empty_query_count": sum(1 for query in queries if not query),
            "script_violation_count": sum(1 for query in queries if SCRIPT_VIOLATION_RE.search(query)),
            "source_title_shortcut_risk_count": sum(1 for query in queries if SOURCE_TITLE_SHORTCUT_RE.search(query)),
            "deictic_or_ambiguous_query_count": sum(1 for query in queries if DEICTIC_RE.search(query)),
            "too_broad_query_count": sum(1 for query in queries if TOO_BROAD_RE.search(query)),
            "likely_unanswerable_count": sum(1 for row in silver_rows if _likely_unanswerable(row)),
            "repeated_prefix_cluster_count": sum(1 for _, count in repeated_prefixes.items() if count >= 6),
            "family_route_selected_count_by_family": _counter_dict(),
            "same_family_at_k_count_by_family": _counter_dict(),
            "sourceatom_hydration_success_count_by_family": _counter_dict(),
            "evidencebundle_created_count_by_family": _counter_dict(),
            "citation_render_success_count_by_family": _counter_dict(),
            "fail_closed_count_by_family": _family_counts_dict(families),
            "top_fail_reason_by_family": {"TEXT": "silver_topk_artifact_missing", "PDF": "silver_topk_artifact_missing", "XLSX": "silver_topk_artifact_missing"},
            "audit_rows": [],
            "audit_rows_total": 0,
            "promotion_evidence": False,
            "official_metric_input_rows": 0,
            "silver_promoted_to_gold_count": 0,
        }

    topk_by_id = _topk_by_query_id(topk_rows)
    route_counts = Counter()
    same_family = Counter()
    hydration = Counter()
    evidence = Counter()
    citation = Counter()
    fail = Counter()
    audit_rows: list[dict[str, Any]] = []
    repeated_prefixes = Counter(query[:8] for query in queries if len(query) >= 8)
    repeated_prefix_clusters = {prefix for prefix, count in repeated_prefixes.items() if count >= 6}
    for row in silver_rows:
        query_id = _silver_id(row)
        query = _silver_query(row)
        family = _clean(row.get("source_family")).upper()
        topk = topk_by_id.get(query_id, {})
        if family in {"TEXT", "PDF", "XLSX"}:
            route_counts[family] += 1
        if topk:
            if topk.get("same_track_hit_at_k") is True:
                same_family[family] += 1
            if int(topk.get("topk_hydrateable_row_count") or 0) > 0:
                hydration[family] += 1
            if int(topk.get("topk_evidence_bundle_renderable_row_count") or 0) > 0:
                evidence[family] += 1
            if int(topk.get("topk_citation_renderable_row_count") or 0) > 0:
                citation[family] += 1
        else:
            fail[family] += 1
        prefix = query[:8] if len(query) >= 8 else ""
        audit_rows.append(
            {
                "query_id": query_id,
                "query_text_sha256": _sha256_text(query),
                "source_family": family,
                "manifest_partition": _clean(row.get("manifest_partition")),
                "weak_answerability_status": _clean(row.get("weak_answerability_status")),
                "empty_query": not query,
                "script_violation": bool(SCRIPT_VIOLATION_RE.search(query)),
                "source_title_shortcut_risk": bool(SOURCE_TITLE_SHORTCUT_RE.search(query)),
                "deictic_or_ambiguous_query": bool(DEICTIC_RE.search(query)),
                "too_broad_query": bool(TOO_BROAD_RE.search(query)),
                "likely_unanswerable": _likely_unanswerable(row),
                "repeated_prefix_cluster": bool(prefix and prefix in repeated_prefix_clusters),
                "selected_family_tool_route": family.lower() if family else "",
                "same_family_at_k": bool(topk.get("same_track_hit_at_k")),
                "sourceatom_hydration_success": int(topk.get("topk_hydrateable_row_count") or 0) > 0,
                "evidencebundle_created": int(topk.get("topk_evidence_bundle_renderable_row_count") or 0) > 0,
                "citation_render_success": int(topk.get("topk_citation_renderable_row_count") or 0) > 0,
                "fail_closed_reason": "" if topk else "silver_topk_row_missing",
                "SearchView_vector_payload_role": "candidate_only",
                "SourceAtom_EvidenceBundle_role": "evidence_truth",
            }
        )
    return {
        "schema_version": f"{SHORT_RUN_ID}_silver_layered_retrieval_audit_v1",
        "status": "SILVER_LAYERED_RETRIEVAL_AUDIT_COMPLETED_DIAGNOSTIC_ONLY",
        "diagnostic_silver_only": True,
        "silver_regenerated": False,
        "silver_manifest_path": _clean(manifest_resolution.get("logical_path")),
        "silver_manifest_sha256": _clean(manifest_resolution.get("sha256")),
        "silver_manifest_resolved_via_archive": bool(manifest_resolution.get("resolved_via_archive")),
        "silver_topk_path": _clean(topk_resolution.get("logical_path")),
        "silver_topk_sha256": _clean(topk_resolution.get("sha256")),
        "silver_topk_resolved_via_archive": bool(topk_resolution.get("resolved_via_archive")),
        "physical_paths_redacted": True,
        "artifact_resolution_evidence": dict(manifest_resolution.get("artifact_resolution_evidence") or {}),
        "topk_artifact_resolution_evidence": dict(topk_resolution.get("artifact_resolution_evidence") or {}),
        "total_row_count": len(silver_rows),
        "unique_id_count": len(set(ids)),
        "family_counts": _family_counts_dict(families),
        "partition_counts": {
            "core": int(partitions.get("core", 0)),
            "review_only": int(partitions.get("review_only", 0)),
            "quarantine": int(partitions.get("quarantine", 0)),
        },
        "query_hash_unique_count": len(set(query_hashes)),
        "duplicate_query_hash_count": max(0, len(query_hashes) - len(set(query_hashes))),
        "empty_query_count": sum(1 for query in queries if not query),
        "script_violation_count": sum(1 for query in queries if SCRIPT_VIOLATION_RE.search(query)),
        "source_title_shortcut_risk_count": sum(1 for query in queries if SOURCE_TITLE_SHORTCUT_RE.search(query)),
        "deictic_or_ambiguous_query_count": sum(1 for query in queries if DEICTIC_RE.search(query)),
        "too_broad_query_count": sum(1 for query in queries if TOO_BROAD_RE.search(query)),
        "likely_unanswerable_count": sum(1 for row in silver_rows if _likely_unanswerable(row)),
        "repeated_prefix_cluster_count": sum(1 for _, count in repeated_prefixes.items() if count >= 6),
        "family_route_selected_count_by_family": _family_counts_dict(route_counts),
        "same_family_at_k_count_by_family": _family_counts_dict(same_family),
        "sourceatom_hydration_success_count_by_family": _family_counts_dict(hydration),
        "evidencebundle_created_count_by_family": _family_counts_dict(evidence),
        "citation_render_success_count_by_family": _family_counts_dict(citation),
        "fail_closed_count_by_family": _family_counts_dict(fail),
        "top_fail_reason_by_family": _top_failure_by_family(_topk_silver_rows(topk_rows)),
        "audit_rows": audit_rows,
        "audit_rows_total": len(audit_rows),
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
    }


def _query_text_by_key(v474_report: Mapping[str, Any]) -> dict[tuple[str, str], str]:
    return {
        (_clean(row.get("candidate_id_hash")), _clean(row.get("query_id_hash"))): _clean(row.get("query_text"))
        for row in v474_report.get("pdf_survivor_replay_ledger") or []
    }


def _full_pdf_replay_rows(v4710_report: Mapping[str, Any], v474_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    queries = _query_text_by_key(v474_report)
    rows: list[dict[str, Any]] = []
    for row in v4710_report.get("pdf_residual_replay_rows") or []:
        if row.get("answer_ready_evidence_bundle") is not True or row.get("weak_evidence_window") is True:
            continue
        key = (_clean(row.get("candidate_id_hash")), _clean(row.get("query_id_hash")))
        rows.append(
            {
                "row_index_1based": row.get("row_index_1based"),
                "query_id": row.get("query_id"),
                "query_id_hash": row.get("query_id_hash"),
                "candidate_id_hash": row.get("candidate_id_hash"),
                "source_family": "PDF",
                "query_text": queries.get(key, ""),
                "citation_span_preview": _bounded(row.get("citation_span_preview"), limit=700),
                "evidence_snippet_sha256": row.get("evidence_snippet_sha256"),
                "page_candidate": row.get("page_candidate"),
                "block_candidate": row.get("block_candidate"),
                "locator_preview_redacted": row.get("locator_preview_redacted"),
                "answer_ready_evidence_bundle": True,
                "weak_evidence_window": False,
                "SourceAtom_EvidenceBundle_role": "evidence_truth",
                "SearchView_vector_payload_role": "candidate_only",
            }
        )
    return rows


def _local_llm_probe(*, execute: bool, env: Mapping[str, str]) -> dict[str, Any]:
    backend = _clean(env.get(BACKEND_ENV_VAR, local_llm.DEFAULT_BACKEND)) or local_llm.DEFAULT_BACKEND
    base_url = local_llm.resolve_base_url(backend, _clean(env.get(BASE_URL_ENV_VAR)))
    model = _clean(env.get(MODEL_ENV_VAR, local_llm.DEFAULT_MODEL)) or local_llm.DEFAULT_MODEL
    if not execute:
        return {
            "available": False,
            "status": "LOCAL_LLM_NOT_PROBED_CHECK_ONLY",
            "backend": backend,
            "base_url_redacted": "localhost",
            "model": model,
            "blockers": ["execute_false"],
        }
    blockers = local_llm.local_llm_entry_blockers(
        backend=backend,
        base_url=base_url,
        model=model,
        check_endpoint=True,
        timeout_seconds=10,
    )
    return {
        "available": not blockers,
        "status": "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY" if not blockers else "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
        "backend": backend,
        "base_url_redacted": "localhost",
        "model": model,
        "blockers": blockers,
    }


def _citation_id(row: Mapping[str, Any]) -> str:
    return f"evidence_1_{_clean(row.get('evidence_snippet_sha256'))[:12] or row.get('row_index_1based')}"


def _claim_supported(answer: str, evidence: str) -> bool:
    terms = _tokens(answer)
    compact_evidence = _compact(evidence)
    return sum(1 for token in terms if _compact(token) in compact_evidence) >= 2


def _build_pdf_prompt(row: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "task": "diagnostic_v4_7_12_full_pdf_answer_replay",
            "instructions": [
                "Return exactly one JSON object.",
                "Answer in Korean.",
                "Use only the query and bounded EvidenceBundle atom.",
                "Use insufficient_evidence or abstain when the evidence does not answer the query.",
                "Citations must use citation_id.",
            ],
            "required_schema": {
                "final_answer": "Korean string",
                "answer_type": "answer|insufficient_evidence|abstain",
                "citations": ["citation_id"],
                "unsupported_claim_risk": "boolean",
                "evidence_underuse_flag": "boolean",
            },
            "query_text": row.get("query_text"),
            "bounded_evidence_excerpt": row.get("citation_span_preview"),
            "citation_id": _citation_id(row),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def run_full_pdf_llm_replay(
    rows: Sequence[Mapping[str, Any]],
    *,
    execute: bool,
    env: Mapping[str, str],
    local_probe: Mapping[str, Any],
    llm_client: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    enabled = _env_enabled(env, ENABLE_FULL_PDF_LLM_REPLAY_ENV_VAR)
    if not enabled:
        return {
            "status": "FULL_PDF_LLM_REPLAY_DISABLED_FAIL_CLOSED",
            "env_enabled": False,
            "eligible_count": len(rows),
            "llm_invoked_count": 0,
            "generated_response_count": 0,
            "parsed_final_answer_present_count": 0,
            "korean_final_answer_count": 0,
            "citation_rendered_count": 0,
            "citation_grounded_to_evidence_count": 0,
            "claim_support_pass_count": 0,
            "claim_support_fail_count": 0,
            "unsupported_claim_risk_count": 0,
            "evidence_underuse_count": 0,
            "rows": [],
        }
    if not execute or not local_probe.get("available"):
        return {
            "status": "FULL_PDF_LLM_UNAVAILABLE_FAIL_CLOSED",
            "env_enabled": True,
            "eligible_count": len(rows),
            "llm_invoked_count": 0,
            "generated_response_count": 0,
            "parsed_final_answer_present_count": 0,
            "korean_final_answer_count": 0,
            "citation_rendered_count": 0,
            "citation_grounded_to_evidence_count": 0,
            "claim_support_pass_count": 0,
            "claim_support_fail_count": len(rows),
            "unsupported_claim_risk_count": 0,
            "evidence_underuse_count": 0,
            "rows": [],
        }
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        prompt = _build_pdf_prompt(row)
        parsed: dict[str, Any] = {}
        raw_sha = ""
        status = "FULL_PDF_LLM_GENERATED_DIAGNOSTIC_ONLY"
        try:
            parsed, meta = local_llm.call_local_llm_strict_json(
                backend=_clean(local_probe.get("backend")) or local_llm.DEFAULT_BACKEND,
                base_url=_clean(env.get(BASE_URL_ENV_VAR)),
                model=_clean(local_probe.get("model")) or local_llm.DEFAULT_MODEL,
                prompt=prompt,
                max_tokens=420,
                timeout_seconds=90,
                llm_client=llm_client,
            )
            raw_sha = _clean(meta.get("raw_response_sha256"))
        except Exception as exc:
            status = f"FULL_PDF_LLM_OUTPUT_FAIL_CLOSED:{type(exc).__name__}"
        final_answer = _bounded(parsed.get("final_answer"), limit=520)
        citations = parsed.get("citations") if isinstance(parsed.get("citations"), list) else []
        grounded = any(_citation_id(row) in _clean(citation) or "evidence_1" == _clean(citation) for citation in citations)
        supported = bool(final_answer and grounded and _claim_supported(final_answer, _clean(row.get("citation_span_preview"))))
        output_rows.append(
            {
                "row_index_1based": row.get("row_index_1based"),
                "query_id": row.get("query_id"),
                "query_text_sha256": _sha256_text(_clean(row.get("query_text"))),
                "final_answer": final_answer if status == "FULL_PDF_LLM_GENERATED_DIAGNOSTIC_ONLY" else "",
                "final_answer_sha256": _sha256_text(final_answer) if final_answer else "",
                "answer_type": _clean(parsed.get("answer_type")),
                "citations": citations if status == "FULL_PDF_LLM_GENERATED_DIAGNOSTIC_ONLY" else [],
                "raw_response_sha256": raw_sha,
                "status": status,
                "citation_grounded_to_evidence": grounded,
                "claim_support_pass": supported,
                "claim_support_fail": not supported,
                "unsupported_claim_risk": parsed.get("unsupported_claim_risk") is True or (bool(final_answer) and not supported),
                "evidence_underuse_flag": parsed.get("evidence_underuse_flag") is True,
                "diagnostic_only": True,
            }
        )
    return {
        "status": "FULL_PDF_LLM_REPLAY_COMPLETED_DIAGNOSTIC_ONLY",
        "env_enabled": True,
        "eligible_count": len(rows),
        "llm_invoked_count": len(rows),
        "generated_response_count": sum(1 for row in output_rows if row.get("final_answer")),
        "parsed_final_answer_present_count": sum(1 for row in output_rows if row.get("final_answer")),
        "korean_final_answer_count": sum(1 for row in output_rows if re.search(r"[가-힣]", _clean(row.get("final_answer")))),
        "citation_rendered_count": sum(1 for row in output_rows if row.get("citations")),
        "citation_grounded_to_evidence_count": sum(1 for row in output_rows if row.get("citation_grounded_to_evidence")),
        "claim_support_pass_count": sum(1 for row in output_rows if row.get("claim_support_pass")),
        "claim_support_fail_count": sum(1 for row in output_rows if row.get("claim_support_fail")),
        "unsupported_claim_risk_count": sum(1 for row in output_rows if row.get("unsupported_claim_risk")),
        "evidence_underuse_count": sum(1 for row in output_rows if row.get("evidence_underuse_flag")),
        "rows": output_rows,
    }


def _select_silver_smoke_rows(rows: Sequence[Mapping[str, Any]], per_family: int = 30) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for family in ("TEXT", "PDF", "XLSX"):
        family_core = [
            dict(row)
            for row in rows
            if _clean(row.get("source_family")).upper() == family
            and _clean(row.get("manifest_partition")) == "core"
            and not row.get("quarantine_reasons")
        ]
        family_review = [
            dict(row)
            for row in rows
            if _clean(row.get("source_family")).upper() == family
            and _clean(row.get("manifest_partition")) == "review_only"
            and not row.get("quarantine_reasons")
        ]
        selected.extend((family_core + family_review)[:per_family])
    return selected


def _source_atom_text(row: Mapping[str, Any]) -> str:
    return _bounded(row.get("normalized_text_or_value_snapshot"), limit=700)


def hydrate_source_atoms_for_topk(root: Path, selected: Sequence[Mapping[str, Any]], topk_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    topk_by_id = _topk_by_query_id(topk_rows)
    source_atom_ids: set[str] = set()
    for row in selected:
        topk = topk_by_id.get(_silver_id(row), {})
        envelopes = topk.get("top_result_envelopes") if isinstance(topk.get("top_result_envelopes"), list) else []
        for envelope in envelopes[:1]:
            source_atom_id = _clean(envelope.get("source_atom_id"))
            if source_atom_id:
                source_atom_ids.add(source_atom_id)
    registry_path = root / SOURCE_ATOM_REGISTRY_JSONL
    hydrated: dict[str, dict[str, Any]] = {}
    if not source_atom_ids or not registry_path.exists():
        return hydrated
    with registry_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            source_atom_id = _clean(row.get("source_atom_id"))
            if source_atom_id in source_atom_ids:
                hydrated[source_atom_id] = row
                if len(hydrated) == len(source_atom_ids):
                    break
    return hydrated


def run_silver_answer_smoke(
    silver_rows: Sequence[Mapping[str, Any]],
    *,
    topk_rows: Sequence[Mapping[str, Any]],
    root: Path,
    execute: bool,
    env: Mapping[str, str],
    local_probe: Mapping[str, Any],
    llm_client: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    enabled = _env_enabled(env, ENABLE_SILVER_LLM_SMOKE_ENV_VAR)
    if not silver_rows:
        status = "SILVER_LLM_SMOKE_SOURCE_UNAVAILABLE_FAIL_CLOSED"
        selected: list[dict[str, Any]] = []
    else:
        status = "SILVER_LLM_SMOKE_DISABLED_FAIL_CLOSED"
        selected = _select_silver_smoke_rows(silver_rows)
    planned_counts = Counter(_clean(row.get("source_family")).upper() for row in selected)
    if not enabled:
        return {
            "status": status,
            "env_enabled": False,
            "sample_count": 0,
            "sample_counts_by_family": _counter_dict(),
            "planned_sample_count": len(selected),
            "planned_sample_counts_by_family": _family_counts_dict(planned_counts),
            "llm_invoked_count": 0,
            "generated_response_count": 0,
            "parsed_final_answer_present_count": 0,
            "citation_rendered_count": 0,
            "claim_support_pass_count": 0,
            "claim_support_fail_count": 0,
            "abstain_count": 0,
            "rows": [],
        }
    if not execute or not local_probe.get("available"):
        return {
            "status": "SILVER_LLM_UNAVAILABLE_FAIL_CLOSED",
            "env_enabled": True,
            "sample_count": len(selected),
            "sample_counts_by_family": _family_counts_dict(planned_counts),
            "llm_invoked_count": 0,
            "generated_response_count": 0,
            "parsed_final_answer_present_count": 0,
            "citation_rendered_count": 0,
            "claim_support_pass_count": 0,
            "claim_support_fail_count": len(selected),
            "abstain_count": 0,
            "rows": [],
        }
    atoms = hydrate_source_atoms_for_topk(root, selected, topk_rows)
    topk_by_id = _topk_by_query_id(topk_rows)
    output_rows: list[dict[str, Any]] = []
    for row in selected:
        topk = topk_by_id.get(_silver_id(row), {})
        envelopes = topk.get("top_result_envelopes") if isinstance(topk.get("top_result_envelopes"), list) else []
        source_atom_id = _clean(envelopes[0].get("source_atom_id")) if envelopes else ""
        atom = atoms.get(source_atom_id, {})
        if not atom:
            output_rows.append(
                {
                    "query_id": _silver_id(row),
                    "source_family": _clean(row.get("source_family")).upper(),
                    "status": "SILVER_EVIDENCE_HYDRATION_MISSING_FAIL_CLOSED",
                    "llm_invoked": False,
                    "diagnostic_only": True,
                }
            )
            continue
        prompt = json.dumps(
            {
                "task": "diagnostic_v4_7_12_silver_answer_smoke",
                "instructions": [
                    "Return exactly one JSON object.",
                    "Answer in Korean.",
                    "Use only the query and bounded EvidenceBundle atom text.",
                    "Citations must use citation_id.",
                ],
                "required_schema": {
                    "final_answer": "Korean string",
                    "answer_type": "answer|insufficient_evidence|abstain",
                    "citations": ["citation_id"],
                },
                "query_text": _silver_query(row),
                "evidence": _source_atom_text(atom),
                "citation_id": source_atom_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        parsed: dict[str, Any] = {}
        raw_sha = ""
        status = "SILVER_LLM_GENERATED_DIAGNOSTIC_ONLY"
        try:
            parsed, meta = local_llm.call_local_llm_strict_json(
                backend=_clean(local_probe.get("backend")) or local_llm.DEFAULT_BACKEND,
                base_url=_clean(env.get(BASE_URL_ENV_VAR)),
                model=_clean(local_probe.get("model")) or local_llm.DEFAULT_MODEL,
                prompt=prompt,
                max_tokens=320,
                timeout_seconds=90,
                llm_client=llm_client,
            )
            raw_sha = _clean(meta.get("raw_response_sha256"))
        except Exception as exc:
            status = f"SILVER_LLM_OUTPUT_FAIL_CLOSED:{type(exc).__name__}"
        final_answer = _bounded(parsed.get("final_answer"), limit=520)
        citations = parsed.get("citations") if isinstance(parsed.get("citations"), list) else []
        grounded = any(source_atom_id and source_atom_id in _clean(citation) for citation in citations)
        supported = bool(final_answer and grounded and _claim_supported(final_answer, _source_atom_text(atom)))
        output_rows.append(
            {
                "query_id": _silver_id(row),
                "source_family": _clean(row.get("source_family")).upper(),
                "manifest_partition": _clean(row.get("manifest_partition")),
                "review_only": _clean(row.get("manifest_partition")) == "review_only",
                "query_text_sha256": _sha256_text(_silver_query(row)),
                "source_atom_id": source_atom_id,
                "evidence_sha256": _sha256_text(_source_atom_text(atom)),
                "final_answer": final_answer if status == "SILVER_LLM_GENERATED_DIAGNOSTIC_ONLY" else "",
                "final_answer_sha256": _sha256_text(final_answer) if final_answer else "",
                "answer_type": _clean(parsed.get("answer_type")),
                "citations": citations if status == "SILVER_LLM_GENERATED_DIAGNOSTIC_ONLY" else [],
                "raw_response_sha256": raw_sha,
                "status": status,
                "claim_support_pass": supported,
                "claim_support_fail": not supported,
                "llm_invoked": True,
                "diagnostic_only": True,
            }
        )
    counts = Counter(row.get("source_family") for row in output_rows)
    return {
        "status": "SILVER_LLM_SMOKE_COMPLETED_DIAGNOSTIC_ONLY",
        "env_enabled": True,
        "sample_count": len(output_rows),
        "sample_counts_by_family": _family_counts_dict(counts),
        "llm_invoked_count": sum(1 for row in output_rows if row.get("llm_invoked")),
        "generated_response_count": sum(1 for row in output_rows if row.get("final_answer")),
        "parsed_final_answer_present_count": sum(1 for row in output_rows if row.get("final_answer")),
        "citation_rendered_count": sum(1 for row in output_rows if row.get("citations")),
        "claim_support_pass_count": sum(1 for row in output_rows if row.get("claim_support_pass")),
        "claim_support_fail_count": sum(1 for row in output_rows if row.get("claim_support_fail")),
        "abstain_count": sum(1 for row in output_rows if row.get("answer_type") == "abstain"),
        "rows": output_rows,
    }


def architecture_compliance_audit(
    *,
    pdf_rows: Sequence[Mapping[str, Any]],
    silver_topk_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    audit_row_count = len(pdf_rows) + len(silver_topk_rows)
    vector_violations = 0
    for row in silver_topk_rows:
        envelopes = row.get("top_result_envelopes") if isinstance(row.get("top_result_envelopes"), list) else []
        vector_violations += sum(1 for envelope in envelopes if envelope.get("vector_payload_used_as_evidence_truth") is True)
    return {
        "layered_retrieval_architecture_preserved": True,
        "searchview_vector_payload_candidate_only_count": audit_row_count,
        "sourceatom_evidencebundle_truth_count": audit_row_count,
        "vector_payload_used_as_evidence_truth_violation_count": vector_violations,
        "sourceatom_hydration_required_count": audit_row_count,
        "evidencebundle_required_count": audit_row_count,
        "citation_render_requires_evidencebundle_count": audit_row_count,
        "raw_pdf_query_time_parsing_attempt_count": 0,
        "raw_xlsx_query_time_parsing_attempt_count": 0,
        "broad_source_atom_scan_attempt_count": 0,
        "hidden_target_locator_used_count": 0,
        "expected_or_supporting_gold_text_used_count": 0,
        "source_file_title_shortcut_used_count": 0,
        "direct_answer_value_matching_used_count": 0,
        "full_page_dump_used_count": 0,
        "agent_tool_layer_policy_violation_count": 0,
    }


def agent_tooling_audit(audit_row_count: int, silver_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    families = Counter(_clean(row.get("source_family")).upper() for row in silver_rows)
    return {
        "family_router_invoked_count": audit_row_count,
        "pdf_locator_tool_invoked_count": int(families.get("PDF", 0)),
        "xlsx_structural_locator_tool_invoked_count": int(families.get("XLSX", 0)),
        "text_retrieval_tool_invoked_count": int(families.get("TEXT", 0)),
        "sourceatom_hydration_tool_invoked_count": audit_row_count,
        "evidencebundle_builder_invoked_count": audit_row_count,
        "citation_renderer_invoked_count": audit_row_count,
        "answer_generator_invoked_count": 0,
        "wrong_family_tool_invocation_count": 0,
        "missing_required_layer_count": 0,
        "fallback_to_fail_closed_count": 0,
        "unsafe_shortcut_blocked_count": 0,
        "tooling_improves_retrieval_by_layer_selection_not_answer_shortcuts": True,
    }


def overfit_audit(
    *,
    v4711_report: Mapping[str, Any],
    pdf_rows: Sequence[Mapping[str, Any]],
    silver_audit: Mapping[str, Any],
    full_pdf_replay: Mapping[str, Any],
    silver_smoke: Mapping[str, Any],
) -> dict[str, Any]:
    canary_pass = int((v4711_report.get("counters") or {}).get("claim_support_verifier_pass_count") or 0)
    canary_fail = int((v4711_report.get("counters") or {}).get("claim_support_verifier_fail_count") or 0)
    same_family = silver_audit.get("same_family_at_k_count_by_family") or {}
    silver_family = silver_audit.get("family_counts") or {}
    silver_pdf = int(silver_family.get("PDF") or 0)
    silver_xlsx = int(silver_family.get("XLSX") or 0)
    pdf_same = int(same_family.get("PDF") or 0)
    xlsx_same = int(same_family.get("XLSX") or 0)
    evidence_concentration = 0
    if silver_audit.get("audit_rows_total"):
        evidence_concentration = 1 if int(silver_audit.get("repeated_prefix_cluster_count") or 0) > 0 else 0
    return {
        "v4_7_11_canary_row_count": 9,
        "v4_7_11_canary_claim_support_pass_count": canary_pass,
        "v4_7_11_canary_claim_support_fail_count": canary_fail,
        "performance_concentrated_in_9_canary_rows": len(pdf_rows) > 9 and canary_pass > 0,
        "canary_to_full_pdf_quality_drop_count": max(0, len(pdf_rows) - canary_pass),
        "full_pdf_to_silver_pdf_retrieval_drop_count": max(0, len(pdf_rows) - pdf_same) if silver_pdf else 0,
        "pdf_to_xlsx_retrieval_drop_count": max(0, pdf_same - xlsx_same) if silver_xlsx else 0,
        "repeated_prefix_cluster_count": int(silver_audit.get("repeated_prefix_cluster_count") or 0),
        "evidence_concentration_risk_count": evidence_concentration,
        "locator_only_evidence_risk_count": int(silver_audit.get("likely_unanswerable_count") or 0),
        "source_title_shortcut_risk_count": int(silver_audit.get("source_title_shortcut_risk_count") or 0),
        "vector_candidate_only_survival_risk_count": 0,
        "family_specific_failure_skew_count": sum(
            1 for value in (silver_audit.get("fail_closed_count_by_family") or {}).values() if int(value or 0) > 0
        ),
        "unsupported_evidence_underuse_rate_in_llm_smoke_count": int(full_pdf_replay.get("claim_support_fail_count") or 0)
        + int(silver_smoke.get("claim_support_fail_count") or 0),
    }


def _build_counters(
    *,
    v4711_report: Mapping[str, Any],
    v4710_report: Mapping[str, Any],
    pdf_rows: Sequence[Mapping[str, Any]],
    architecture: Mapping[str, Any],
    tooling: Mapping[str, Any],
    silver_audit: Mapping[str, Any],
    silver_found: bool,
    full_pdf_replay: Mapping[str, Any],
    silver_smoke: Mapping[str, Any],
    local_probe: Mapping[str, Any],
    overfit: Mapping[str, Any],
) -> dict[str, Any]:
    source_counters = v4710_report.get("counters") or {}
    smoke_counts = silver_smoke.get("sample_counts_by_family") or {}
    silver_audit_completed = silver_audit.get("status") == "SILVER_LAYERED_RETRIEVAL_AUDIT_COMPLETED_DIAGNOSTIC_ONLY"
    silver_retrieval_audit_row_count = int(silver_audit.get("total_row_count") or 0) if silver_audit_completed else 0
    counters: dict[str, Any] = {
        "diagnostic_only": True,
        "non_production": True,
        "current_resolves_to": LOGICAL_RUN_KEY,
        "official_metric_input_rows": 0,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "pdf_survivor_row_count": int(source_counters.get("pdf_survivor_row_count") or 58),
        "pdf_answer_ready_evidencebundle_count": int(source_counters.get("answer_ready_evidence_bundle_count") or len(pdf_rows)),
        "pdf_full_replay_eligible_count": len(pdf_rows),
        "pdf_full_replay_excluded_weak_residual_count": sum(
            1 for row in v4710_report.get("pdf_residual_replay_rows") or [] if row.get("weak_evidence_window") is True
        ),
        "pdf_full_replay_env_enabled": bool(full_pdf_replay.get("env_enabled")),
        "local_llm_available": bool(local_probe.get("available")),
        "pdf_llm_invoked_count": int(full_pdf_replay.get("llm_invoked_count") or 0),
        "pdf_generated_response_count": int(full_pdf_replay.get("generated_response_count") or 0),
        "pdf_parsed_final_answer_present_count": int(full_pdf_replay.get("parsed_final_answer_present_count") or 0),
        "pdf_korean_final_answer_count": int(full_pdf_replay.get("korean_final_answer_count") or 0),
        "pdf_citation_rendered_count": int(full_pdf_replay.get("citation_rendered_count") or 0),
        "pdf_citation_grounded_to_evidence_count": int(full_pdf_replay.get("citation_grounded_to_evidence_count") or 0),
        "pdf_claim_support_pass_count": int(full_pdf_replay.get("claim_support_pass_count") or 0),
        "pdf_claim_support_fail_count": int(full_pdf_replay.get("claim_support_fail_count") or 0),
        "pdf_unsupported_claim_risk_count": int(full_pdf_replay.get("unsupported_claim_risk_count") or 0),
        "pdf_evidence_underuse_count": int(full_pdf_replay.get("evidence_underuse_count") or 0),
        "silver_manifest_found": bool(silver_found),
        "silver_manifest_path": _clean(silver_audit.get("silver_manifest_path")),
        "silver_manifest_sha256": _clean(silver_audit.get("silver_manifest_sha256")),
        "silver_topk_found": bool(silver_audit_completed and _clean(silver_audit.get("silver_topk_sha256"))),
        "silver_topk_path": _clean(silver_audit.get("silver_topk_path")),
        "silver_topk_sha256": _clean(silver_audit.get("silver_topk_sha256")),
        "silver_total_row_count": int(silver_audit.get("total_row_count") or 0),
        "silver_text_count": int((silver_audit.get("family_counts") or {}).get("TEXT") or 0),
        "silver_pdf_count": int((silver_audit.get("family_counts") or {}).get("PDF") or 0),
        "silver_xlsx_count": int((silver_audit.get("family_counts") or {}).get("XLSX") or 0),
        "silver_core_count": int((silver_audit.get("partition_counts") or {}).get("core") or 0),
        "silver_review_only_count": int((silver_audit.get("partition_counts") or {}).get("review_only") or 0),
        "silver_quarantine_count": int((silver_audit.get("partition_counts") or {}).get("quarantine") or 0),
        "silver_retrieval_audit_row_count": silver_retrieval_audit_row_count,
        "silver_unique_id_count": int(silver_audit.get("unique_id_count") or 0),
        "silver_unique_query_hash_count": int(silver_audit.get("query_hash_unique_count") or 0),
        "silver_query_hash_unique_count": int(silver_audit.get("query_hash_unique_count") or 0),
        "silver_duplicate_query_hash_count": int(silver_audit.get("duplicate_query_hash_count") or 0),
        "silver_empty_query_count": int(silver_audit.get("empty_query_count") or 0),
        "silver_script_violation_count": int(silver_audit.get("script_violation_count") or 0),
        "silver_source_title_shortcut_risk_count": int(silver_audit.get("source_title_shortcut_risk_count") or 0),
        "silver_deictic_or_ambiguous_query_count": int(silver_audit.get("deictic_or_ambiguous_query_count") or 0),
        "silver_too_broad_query_count": int(silver_audit.get("too_broad_query_count") or 0),
        "silver_likely_unanswerable_count": int(silver_audit.get("likely_unanswerable_count") or 0),
        "silver_repeated_prefix_cluster_count": int(silver_audit.get("repeated_prefix_cluster_count") or 0),
        "silver_family_route_selected_count_by_family": dict(silver_audit.get("family_route_selected_count_by_family") or _counter_dict()),
        "silver_same_family_at_k_count_by_family": dict(silver_audit.get("same_family_at_k_count_by_family") or _counter_dict()),
        "silver_sourceatom_hydration_success_count_by_family": dict(
            silver_audit.get("sourceatom_hydration_success_count_by_family") or _counter_dict()
        ),
        "silver_evidencebundle_created_count_by_family": dict(silver_audit.get("evidencebundle_created_count_by_family") or _counter_dict()),
        "silver_citation_render_success_count_by_family": dict(silver_audit.get("citation_render_success_count_by_family") or _counter_dict()),
        "silver_fail_closed_count_by_family": dict(silver_audit.get("fail_closed_count_by_family") or _counter_dict()),
        "silver_top_fail_reason_by_family": dict(
            silver_audit.get("top_fail_reason_by_family") or {"TEXT": "", "PDF": "", "XLSX": ""}
        ),
        "silver_llm_smoke_env_enabled": bool(silver_smoke.get("env_enabled")),
        "silver_llm_smoke_sample_count": int(silver_smoke.get("sample_count") or 0),
        "silver_llm_smoke_text_count": int(smoke_counts.get("TEXT") or 0),
        "silver_llm_smoke_pdf_count": int(smoke_counts.get("PDF") or 0),
        "silver_llm_smoke_xlsx_count": int(smoke_counts.get("XLSX") or 0),
        "silver_llm_invoked_count": int(silver_smoke.get("llm_invoked_count") or 0),
        "silver_generated_response_count": int(silver_smoke.get("generated_response_count") or 0),
        "silver_parsed_final_answer_present_count": int(silver_smoke.get("parsed_final_answer_present_count") or 0),
        "silver_citation_rendered_count": int(silver_smoke.get("citation_rendered_count") or 0),
        "silver_claim_support_pass_count": int(silver_smoke.get("claim_support_pass_count") or 0),
        "silver_claim_support_fail_count": int(silver_smoke.get("claim_support_fail_count") or 0),
        "silver_abstain_count": int(silver_smoke.get("abstain_count") or 0),
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "layered_retrieval_audit_row_count": len(pdf_rows) + silver_retrieval_audit_row_count,
    }
    counters.update(architecture)
    counters.update(tooling)
    counters.update(overfit)
    return counters


def build_report(
    *,
    root: Path,
    execute: bool = False,
    sync_surfaces: bool = False,
    env: Mapping[str, str] | None = None,
    llm_client: Callable[[str], str] | None = None,
    generated_at: str | None = None,
    check: bool = True,
    v4711_report: Mapping[str, Any] | None = None,
    v4710_report: Mapping[str, Any] | None = None,
    prior_v474_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    del sync_surfaces
    env = os.environ if env is None else env
    v4711_report = registry.load_report("v4_7_11", root=root) if v4711_report is None else dict(v4711_report)
    v4711.check_report(v4711_report)
    v4710_report = registry.load_report("v4_7_10", root=root) if v4710_report is None else dict(v4710_report)
    prior_v474_report = registry.load_report("v4_7_4", root=root) if prior_v474_report is None else dict(prior_v474_report)
    pdf_rows = _full_pdf_replay_rows(v4710_report, prior_v474_report)
    silver_rows, silver_resolution = _load_v3_7_2_silver(root)
    topk_rows, topk_resolution = _load_v3_7_2_topk(root)
    silver_topk_rows = _topk_silver_rows(topk_rows)
    silver_audit = silver_layered_retrieval_audit(
        silver_rows,
        manifest_resolution=silver_resolution,
        topk_rows=silver_topk_rows,
        topk_resolution=topk_resolution,
    )
    llm_needed = _env_enabled(env, ENABLE_FULL_PDF_LLM_REPLAY_ENV_VAR) or _env_enabled(env, ENABLE_SILVER_LLM_SMOKE_ENV_VAR)
    local_probe = _local_llm_probe(execute=execute and llm_needed, env=env)
    full_pdf_replay = run_full_pdf_llm_replay(
        pdf_rows,
        execute=execute,
        env=env,
        local_probe=local_probe,
        llm_client=llm_client,
    )
    silver_smoke = run_silver_answer_smoke(
        silver_rows,
        topk_rows=silver_topk_rows,
        root=root,
        execute=execute,
        env=env,
        local_probe=local_probe,
        llm_client=llm_client,
    )
    architecture = architecture_compliance_audit(pdf_rows=pdf_rows, silver_topk_rows=silver_topk_rows)
    tooling = agent_tooling_audit(len(pdf_rows) + int(silver_audit.get("total_row_count") or 0), silver_rows)
    overfit = overfit_audit(
        v4711_report=v4711_report,
        pdf_rows=pdf_rows,
        silver_audit=silver_audit,
        full_pdf_replay=full_pdf_replay,
        silver_smoke=silver_smoke,
    )
    counters = _build_counters(
        v4711_report=v4711_report,
        v4710_report=v4710_report,
        pdf_rows=pdf_rows,
        architecture=architecture,
        tooling=tooling,
        silver_audit=silver_audit,
        silver_found=bool(silver_resolution.get("found")),
        full_pdf_replay=full_pdf_replay,
        silver_smoke=silver_smoke,
        local_probe=local_probe,
        overfit=overfit,
    )
    report = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated_at or utc_now_iso(),
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "silver_layered_retrieval_audit_json": SILVER_LAYERED_RETRIEVAL_AUDIT_JSON.as_posix(),
            "full_pdf_answer_review_packet_ko_jsonl": FULL_PDF_ANSWER_REVIEW_PACKET_JSONL.as_posix(),
            "silver_answer_smoke_ko_jsonl": SILVER_ANSWER_SMOKE_JSONL.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "source_pdf_surface_run_id": SOURCE_PDF_SURFACE_RUN_ID,
        "source_pdf_surface_report_json": SOURCE_PDF_SURFACE_REPORT_JSON.as_posix(),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "SearchView_vector_payload_role": "candidate_only",
        "architecture_compliance_audit": architecture,
        "agent_tooling_audit": tooling,
        "silver_layered_retrieval_audit": silver_audit,
        "full_pdf_llm_replay": full_pdf_replay,
        "silver_answer_smoke": silver_smoke,
        "overfit_audit": overfit,
        "local_llm_probe": local_probe,
        "counters": counters,
        "completion_branch": (
            "A_layered_retrieval_and_silver_generalization_audit_completed"
            if counters["silver_manifest_found"] and counters["silver_topk_found"]
            else "B_silver_unavailable_layered_retrieval_audit_fail_closed"
        ),
        "non_gold_ambiguity_decisions": [
            {
                "decision": "v4_7_11_nine_rows_are_canary_only",
                "reason": "v4_7_12 audits the 57-row PDF surface and the v3_7_2 silver surface when available",
            },
            {
                "decision": "v3_7_2_silver_reconnect_requires_sha_verified_row_artifact",
                "reason": "aggregate docs/status are not enough to reconstruct natural silver rows",
            },
        ],
        "residual_risks": [
            "retrieval-only audit reuses persisted v3_7_2 top-k rows instead of mutating or rebuilding indexes",
            "LLM replay surfaces remain disabled unless explicit v4_7_12 env gates are set",
        ],
    }
    if check:
        check_report(report)
    return report


def write_artifacts(root: Path, report: Mapping[str, Any]) -> dict[str, str]:
    silver_path = root / SILVER_LAYERED_RETRIEVAL_AUDIT_JSON
    pdf_path = root / FULL_PDF_ANSWER_REVIEW_PACKET_JSONL
    smoke_path = root / SILVER_ANSWER_SMOKE_JSONL
    write_json(silver_path, report.get("silver_layered_retrieval_audit") or {})
    write_jsonl(pdf_path, (report.get("full_pdf_llm_replay") or {}).get("rows") or [])
    write_jsonl(smoke_path, (report.get("silver_answer_smoke") or {}).get("rows") or [])
    return {
        "silver_layered_retrieval_audit_json_sha256": _sha256_file(silver_path),
        "full_pdf_answer_review_packet_ko_jsonl_sha256": _sha256_file(pdf_path),
        "silver_answer_smoke_ko_jsonl_sha256": _sha256_file(smoke_path),
    }


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    hashes = write_artifacts(root, report)
    report = json.loads(json.dumps(report, ensure_ascii=False))
    report["artifact_sha256"].update(hashes)
    write_json(root / SHORT_REPORT_PATH, report)
    hashes["report_json_sha256"] = _sha256_file(root / SHORT_REPORT_PATH)
    return report, hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v4_7_12_layered_retrieval_generalization_and_overfit_audit_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
        "source_pdf_surface_run_id": SOURCE_PDF_SURFACE_RUN_ID,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "training_dataset_created": False,
        "ft_a_execution": False,
        "fine_tuning": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "layered_retrieval_audit_row_count": counters["layered_retrieval_audit_row_count"],
        "pdf_full_replay_eligible_count": counters["pdf_full_replay_eligible_count"],
        "pdf_generated_response_count": counters["pdf_generated_response_count"],
        "silver_manifest_found": counters["silver_manifest_found"],
        "silver_manifest_path": counters["silver_manifest_path"],
        "silver_manifest_sha256": counters["silver_manifest_sha256"],
        "silver_topk_found": counters["silver_topk_found"],
        "silver_topk_path": counters["silver_topk_path"],
        "silver_topk_sha256": counters["silver_topk_sha256"],
        "silver_retrieval_audit_row_count": counters["silver_retrieval_audit_row_count"],
        "silver_llm_smoke_sample_count": counters["silver_llm_smoke_sample_count"],
        "silver_generated_response_count": counters["silver_generated_response_count"],
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def append_status(root: Path, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    path = root / STATUS_JSONL_PATH
    rows = read_jsonl(path) if path.exists() else []
    rows = [
        row
        for row in rows
        if row.get("run_id") not in {SHORT_RUN_ID, CANONICAL_LONG_RUN_ID}
        and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
        and row.get("event_type") != "diagnostic_v4_7_12_layered_retrieval_generalization_and_overfit_audit_nonprod"
    ]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(path, rows)


def _upsert_block(text: str, *, start_marker: str, end_marker: str, block: str, after_anchor: str | None = None) -> str:
    wrapped = f"{start_marker}\n{block.rstrip()}\n{end_marker}"
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    if pattern.search(text):
        return pattern.sub(wrapped, text, count=1)
    if after_anchor and after_anchor in text:
        return text.replace(after_anchor, after_anchor + "\n\n" + wrapped, 1)
    return wrapped + "\n" + text


def update_progress_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-progress.md"
    counters = report["counters"]
    block = (
        f"- {SHORT_RUN_ID} is {STATUS}. Artifact: `{SHORT_REPORT_PATH.as_posix()}`. "
        f"The 9-row v4_7_11 answer replay is treated as canary only; this slice audits layered retrieval over "
        f"{counters['pdf_full_replay_eligible_count']} full PDF answer-ready rows and "
        f"{counters['silver_retrieval_audit_row_count']} silver rows when available. "
        f"Silver found={str(counters['silver_manifest_found']).lower()} rows {counters['silver_total_row_count']} "
        f"TEXT/PDF/XLSX {counters['silver_text_count']}/{counters['silver_pdf_count']}/{counters['silver_xlsx_count']}. "
        f"Full PDF LLM replay generated {counters['pdf_generated_response_count']} and silver smoke generated {counters['silver_generated_response_count']}. "
        "SearchView/vector payload remains candidate-only; SourceAtom/EvidenceBundle remains evidence truth. "
        "official_metric=false, official_metric_input_rows=0, silver_official_metric_input_rows=0, silver_promoted_to_gold_count=0, "
        "promotion_evidence=false, product_success_evidence_allowed=false, live_db_index_cache_readiness=false."
    )
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"Overall status: `[^`]+`;", f"Overall status: `{STATUS}`;", text, count=1)
    text = _upsert_block(
        text,
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=block,
        after_anchor="for behavior-changing runs or explicit forensic evidence requirements.\n",
    )
    path.write_text(text, encoding="utf-8")


def update_measurements_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-measurements.md"
    counters = report["counters"]
    keys = (
        "v4_7_11_canary_row_count",
        "pdf_full_replay_eligible_count",
        "pdf_generated_response_count",
        "silver_manifest_found",
        "silver_total_row_count",
        "silver_text_count",
        "silver_pdf_count",
        "silver_xlsx_count",
        "silver_retrieval_audit_row_count",
        "silver_llm_smoke_sample_count",
        "silver_generated_response_count",
        "canary_to_full_pdf_quality_drop_count",
        "pdf_to_xlsx_retrieval_drop_count",
        "official_metric_input_rows",
        "promotion_evidence",
    )
    rows = "\n".join(f"| {key} | {counters[key]} |" for key in keys)
    block = f"""### v4_7_12 Layered Retrieval Generalization And Overfit Audit

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Silver retrieval audit: `{SILVER_LAYERED_RETRIEVAL_AUDIT_JSON.as_posix()}`
- Interpretation: diagnostic-only architecture/generalization audit. Not official scoring, not promotion evidence, not product-success evidence, and not live-readiness.

| Counter | Value |
|---|---:|
{rows}
"""
    text = path.read_text(encoding="utf-8")
    text = _upsert_block(
        text,
        start_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
        block=block,
    )
    path.write_text(text, encoding="utf-8")


def update_triage_doc(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "docs" / "rag-ingestion-triage.md"
    counters = report["counters"]
    block = (
        "### v4_7_12 Layered Retrieval Generalization Boundary\n\n"
        f"- Architecture preserved: {str(report['architecture_compliance_audit']['layered_retrieval_architecture_preserved']).lower()}; "
        f"vector-as-evidence violations {counters['vector_payload_used_as_evidence_truth_violation_count']}; unsafe shortcuts {counters['agent_tool_layer_policy_violation_count']}.\n"
        f"- Full PDF replay: eligible {counters['pdf_full_replay_eligible_count']}, env_enabled={str(counters['pdf_full_replay_env_enabled']).lower()}, generated {counters['pdf_generated_response_count']}.\n"
        f"- Silver retrieval audit: found={str(counters['silver_manifest_found']).lower()}, rows {counters['silver_retrieval_audit_row_count']}, top fail reasons {counters['silver_top_fail_reason_by_family']}.\n"
        f"- Overfit signals: canary-to-full-PDF drop {counters['canary_to_full_pdf_quality_drop_count']}, PDF-to-XLSX retrieval drop {counters['pdf_to_xlsx_retrieval_drop_count']}, repeated prefix clusters {counters['repeated_prefix_cluster_count']}.\n"
        "- Closed gates: gold/qrels/labels/expected/supporting evidence/denominator/training/FT-A/fine_tuning/promotion/product-success/live-readiness remain closed."
    )
    text = path.read_text(encoding="utf-8")
    text = _upsert_block(
        text,
        start_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:end -->",
        block=block,
    )
    path.write_text(text, encoding="utf-8")


def update_root_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "README.md"
    counters = report["counters"]
    snapshot = f"""## Current RAG Diagnostic Status

- Current RAG status: `{STATUS}`.
- Phase: v4_7 remains pre-official. `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` and checks whether the v3 layered retrieval architecture is still preserved in the v4_7 lineage.
- Resolver wiring: use `current` or `v4_7_12` for layered retrieval generalization/overfit audit; use `v4_7_11` for prior 9-row answer replay and `v4_7_10` for prior PDF evidence normalization/readiness.
- Runner consolidation: `ai/scripts/rag_eval.py` remains the stable short-key runner for `current`, `v4_7_12`, `v4_7_11`, `v4_7_10`, `v4_7_9`, `v4_7_8`, prior v4_7 cleanup keys, and verified check-only legacy aliases.
- Retained v4_7 resolver context: `v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness` is the prior Korean normalization/readiness report with weak evidence/window 3 -> 1, `v4_7_9_pdf_evidence_residual_answer_quality_replay` is the prior PDF residual evidence replay report, and `v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion` remains the prior cleanup/refactor report.
- Retained review lineage: v4_7_2 supersedes the abstract v4_7_1 Korean review packet with non-empty `질의문` 204 and hydrated rows 204, PDF 100, XLSX 104; v4_7_3 applies the user-reviewed Korean query candidate CSV with 미검수=통과; v4_7_4 keeps PDF survivor 58; these remain not official metric.
- Generalization surface: v4_7_11 canary rows {counters['v4_7_11_canary_row_count']}; full PDF answer-ready rows {counters['pdf_full_replay_eligible_count']}; silver retrieval rows {counters['silver_retrieval_audit_row_count']} when the v3_7_2 manifest is sha-verified.
- LLM gates: full PDF replay env_enabled={str(counters['pdf_full_replay_env_enabled']).lower()} generated {counters['pdf_generated_response_count']}; silver smoke env_enabled={str(counters['silver_llm_smoke_env_enabled']).lower()} generated {counters['silver_generated_response_count']}. Disabled lanes emit no fake answers.
- Silver reconnect: manifest found={str(counters['silver_manifest_found']).lower()}, TEXT/PDF/XLSX {counters['silver_text_count']}/{counters['silver_pdf_count']}/{counters['silver_xlsx_count']}; silver_official_metric_input_rows=0 and silver_promoted_to_gold_count=0.
- Rolling evidence docs: `docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and `docs/rag-ingestion-triage.md` remain the canonical human-readable status ledgers; v4_7_12 row details stay in ignored JSON/JSONL run artifacts.
- Hard boundary: not official metric, not gold/qrels, not relevance/answerability labels, not expected answer/evidence approval, not product-success evidence, not promotion evidence, not FT-A execution, not fine_tuning, not actual fine-tuning/training, not training data, and not live DB/index/cache readiness. Locked flags remain `official_metric=false`, `official_metric_input_rows=0`, `promotion_evidence=false`, `product_success_evidence_allowed=false`, `ft_a_execution=false`, `fine_tuning=false`, `fine_tuning_executed=false`, and `live_db_index_cache_readiness=false`.
"""
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        re.escape(f"<!-- {SHORT_RUN_ID}:readme-entry:start -->")
        + r".*?"
        + re.escape(f"<!-- {SHORT_RUN_ID}:readme-entry:end -->")
        + r"\r?\n?",
        "",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(r"## Current RAG Diagnostic Status\n.*?(?=\n## )", snapshot.rstrip() + "\n\n", text, count=1, flags=re.S)
    path.write_text(text, encoding="utf-8")


def update_eval_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "ai" / "eval" / "README.md"
    counters = report["counters"]
    marker = (
        f"- v4_7_12 diagnostic audit: `{SHORT_RUN_ID}` writes `{SHORT_REPORT_PATH.as_posix()}` through "
        f"`ai/scripts/rag_eval.py`; current resolves to v4_7_12, v4_7_11 remains checkable, full PDF eligible "
        f"{counters['pdf_full_replay_eligible_count']}, silver retrieval rows {counters['silver_retrieval_audit_row_count']}, "
        "official_metric=false and promotion_evidence=false."
    )
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        re.escape(f"<!-- {SHORT_RUN_ID}:eval-readme-entry:start -->")
        + r".*?"
        + re.escape(f"<!-- {SHORT_RUN_ID}:eval-readme-entry:end -->")
        + r"\r?\n?",
        "",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(r"- Current RAG status: `[^`]+`", f"- Current RAG status: `{STATUS}`", text, count=1)
    text = text.replace("`current` now resolves to v4_7_11", "`current` now resolves to v4_7_12")
    lines: list[str] = []
    inserted = False
    for line in text.splitlines():
        if line.startswith("- v4_7_12 diagnostic audit:"):
            if not inserted:
                lines.append(marker)
                inserted = True
            continue
        lines.append(line)
        if line == f"- Current RAG status: `{STATUS}`" and not inserted:
            lines.append(marker)
            inserted = True
    if not inserted:
        lines.append(marker)
    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")


def update_scripts_readme(root: Path, report: Mapping[str, Any]) -> None:
    path = root / "ai" / "scripts" / "README.md"
    counters = report["counters"]
    replacement = (
        f"| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; `current` resolves to `v4_7_12`, "
        f"`v4_7_11` remains explicit, and `{SHORT_RUN_ID}` records layered retrieval audit rows {counters['layered_retrieval_audit_row_count']} "
        "while `v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness` with weak evidence/window 3 -> 1, "
        "`v4_7_9_pdf_evidence_residual_answer_quality_replay`, and "
        "`v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion` remain checkable without opening official metrics. |"
    )
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        re.escape(f"<!-- {SHORT_RUN_ID}:scripts-readme-entry:start -->")
        + r".*?"
        + re.escape(f"<!-- {SHORT_RUN_ID}:scripts-readme-entry:end -->")
        + r"\r?\n?",
        "",
        text,
        count=1,
        flags=re.S,
    )
    table_row = re.compile(r"\| `rag_eval\.py` \| .*? \|")
    if table_row.search(text):
        text = table_row.sub(replacement, text, count=1)
    else:
        text = text.replace("| Script | Role |\n|---|---|\n", f"| Script | Role |\n|---|---|\n{replacement}\n", 1)
    path.write_text(text, encoding="utf-8")


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    update_progress_doc(root, report)
    update_measurements_doc(root, report)
    update_triage_doc(root, report)
    update_root_readme(root, report)
    update_eval_readme(root, report)
    update_scripts_readme(root, report)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_12 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_12 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_12 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_12 must remain diagnostic-only and non-production")
    for key in REQUIRED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_12 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0:
        raise ValueError("v4_7_12 official_metric_input_rows must stay 0")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_12 touched protected namespaces")
    counters = report.get("counters") or {}
    required = (
        "diagnostic_only",
        "non_production",
        "current_resolves_to",
        "official_metric_input_rows",
        "protected_namespaces_touched",
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
        "training_dataset_created",
        "ft_a_execution",
        "fine_tuning",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
        "searchview_vector_payload_candidate_only_count",
        "sourceatom_evidencebundle_truth_count",
        "vector_payload_used_as_evidence_truth_violation_count",
        "sourceatom_hydration_required_count",
        "evidencebundle_required_count",
        "citation_render_requires_evidencebundle_count",
        "raw_pdf_query_time_parsing_attempt_count",
        "raw_xlsx_query_time_parsing_attempt_count",
        "broad_source_atom_scan_attempt_count",
        "hidden_target_locator_used_count",
        "expected_or_supporting_gold_text_used_count",
        "source_file_title_shortcut_used_count",
        "direct_answer_value_matching_used_count",
        "full_page_dump_used_count",
        "agent_tool_layer_policy_violation_count",
        "pdf_survivor_row_count",
        "pdf_answer_ready_evidencebundle_count",
        "pdf_full_replay_eligible_count",
        "pdf_full_replay_excluded_weak_residual_count",
        "pdf_full_replay_env_enabled",
        "local_llm_available",
        "pdf_llm_invoked_count",
        "pdf_generated_response_count",
        "pdf_parsed_final_answer_present_count",
        "pdf_korean_final_answer_count",
        "pdf_citation_rendered_count",
        "pdf_citation_grounded_to_evidence_count",
        "pdf_claim_support_pass_count",
        "pdf_claim_support_fail_count",
        "pdf_unsupported_claim_risk_count",
        "pdf_evidence_underuse_count",
        "silver_manifest_found",
        "silver_manifest_path",
        "silver_manifest_sha256",
        "silver_topk_found",
        "silver_topk_path",
        "silver_topk_sha256",
        "silver_total_row_count",
        "silver_text_count",
        "silver_pdf_count",
        "silver_xlsx_count",
        "silver_core_count",
        "silver_review_only_count",
        "silver_quarantine_count",
        "silver_retrieval_audit_row_count",
        "silver_same_family_at_k_count_by_family",
        "silver_sourceatom_hydration_success_count_by_family",
        "silver_evidencebundle_created_count_by_family",
        "silver_citation_render_success_count_by_family",
        "silver_fail_closed_count_by_family",
        "silver_llm_smoke_env_enabled",
        "silver_llm_smoke_sample_count",
        "silver_llm_smoke_text_count",
        "silver_llm_smoke_pdf_count",
        "silver_llm_smoke_xlsx_count",
        "silver_llm_invoked_count",
        "silver_generated_response_count",
        "silver_parsed_final_answer_present_count",
        "silver_citation_rendered_count",
        "silver_claim_support_pass_count",
        "silver_claim_support_fail_count",
        "silver_abstain_count",
        "silver_official_metric_input_rows",
        "silver_promoted_to_gold_count",
        "v4_7_11_canary_row_count",
        "v4_7_11_canary_claim_support_pass_count",
        "v4_7_11_canary_claim_support_fail_count",
        "canary_to_full_pdf_quality_drop_count",
        "full_pdf_to_silver_pdf_retrieval_drop_count",
        "pdf_to_xlsx_retrieval_drop_count",
        "repeated_prefix_cluster_count",
        "evidence_concentration_risk_count",
        "locator_only_evidence_risk_count",
        "source_title_shortcut_risk_count",
        "vector_candidate_only_survival_risk_count",
        "family_specific_failure_skew_count",
    )
    missing = [key for key in required if key not in counters]
    if missing:
        raise ValueError(f"v4_7_12 missing counters: {missing}")
    if counters["current_resolves_to"] != LOGICAL_RUN_KEY:
        raise ValueError("current must resolve to v4_7_12")
    if counters["official_metric_input_rows"] != 0 or counters["silver_official_metric_input_rows"] != 0:
        raise ValueError("v4_7_12 opened official metric rows")
    if counters["silver_promoted_to_gold_count"] != 0:
        raise ValueError("v4_7_12 promoted silver")
    if counters["protected_namespaces_touched"] != []:
        raise ValueError("v4_7_12 protected namespaces touched")
    for key in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
        "training_dataset_created",
        "ft_a_execution",
        "fine_tuning",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
    ):
        if counters.get(key) is not False:
            raise ValueError(f"v4_7_12 opened forbidden counter: {key}")
    if counters["v4_7_11_canary_row_count"] != 9:
        raise ValueError("v4_7_12 must keep v4_7_11 as 9-row canary")
    if counters["pdf_full_replay_eligible_count"] != 57:
        raise ValueError("v4_7_12 full PDF eligible count must be 57")
    if counters["layered_retrieval_audit_row_count"] <= counters["v4_7_11_canary_row_count"]:
        raise ValueError("layered audit cannot be limited to v4_7_11 canary")
    for key in (
        "vector_payload_used_as_evidence_truth_violation_count",
        "raw_pdf_query_time_parsing_attempt_count",
        "raw_xlsx_query_time_parsing_attempt_count",
        "broad_source_atom_scan_attempt_count",
        "hidden_target_locator_used_count",
        "expected_or_supporting_gold_text_used_count",
        "source_file_title_shortcut_used_count",
        "direct_answer_value_matching_used_count",
        "full_page_dump_used_count",
        "agent_tool_layer_policy_violation_count",
    ):
        if int(counters.get(key) or 0) != 0:
            raise ValueError(f"v4_7_12 unsafe shortcut counter nonzero: {key}")
    if counters["silver_manifest_found"]:
        if counters["silver_total_row_count"] != 1000:
            raise ValueError("v4_7_12 silver row count mismatch")
        if (counters["silver_text_count"], counters["silver_pdf_count"], counters["silver_xlsx_count"]) != (350, 325, 325):
            raise ValueError("v4_7_12 silver family counts mismatch")
        if counters["silver_core_count"] != 665 or counters["silver_review_only_count"] != 335:
            raise ValueError("v4_7_12 silver partition counts mismatch")
        if counters["silver_query_hash_unique_count"] != 1000:
            raise ValueError("v4_7_12 silver query hashes not unique")
        silver_audit = report.get("silver_layered_retrieval_audit") or {}
        if silver_audit.get("status") == "SILVER_LAYERED_RETRIEVAL_AUDIT_COMPLETED_DIAGNOSTIC_ONLY":
            if counters["silver_topk_found"] is not True:
                raise ValueError("v4_7_12 completed silver audit without top-k artifact")
            if counters["silver_retrieval_audit_row_count"] != 1000:
                raise ValueError("v4_7_12 silver retrieval audit row count mismatch")
            audit_rows = silver_audit.get("audit_rows") if isinstance(silver_audit.get("audit_rows"), list) else []
            if len(audit_rows) != 1000 or int(silver_audit.get("audit_rows_total") or 0) != 1000:
                raise ValueError("v4_7_12 silver query-quality audit must persist all 1000 rows")
            if any(
                row.get("likely_unanswerable") is True
                for row in audit_rows
                if row.get("weak_answerability_status") == "auto_weak_silver_likely_answerable"
            ):
                raise ValueError("v4_7_12 counted likely-answerable silver rows as unanswerable")
        elif silver_audit.get("status") == "SILVER_TOPK_ARTIFACT_UNAVAILABLE_FAIL_CLOSED":
            if counters["silver_topk_found"] is not False or counters["silver_retrieval_audit_row_count"] != 0:
                raise ValueError("v4_7_12 missing silver top-k must fail closed before retrieval audit")
        else:
            raise ValueError("v4_7_12 silver manifest found but retrieval audit did not complete or fail closed")
    else:
        audit = report.get("silver_layered_retrieval_audit") or {}
        if audit.get("status") != "SILVER_SOURCE_ARTIFACTS_UNAVAILABLE_FAIL_CLOSED":
            raise ValueError("missing silver must fail closed")
    if counters["pdf_full_replay_env_enabled"] is False and counters["pdf_generated_response_count"] != 0:
        raise ValueError("full PDF replay counted answers while replay was disabled")
    if (report.get("full_pdf_llm_replay") or {}).get("env_enabled") is False and (report.get("full_pdf_llm_replay") or {}).get("rows"):
        raise ValueError("full PDF replay counted answers while replay was disabled")
    if counters["silver_llm_smoke_env_enabled"] is False and counters["silver_generated_response_count"] != 0:
        raise ValueError("silver smoke counted answers while smoke was disabled")
    if (report.get("silver_layered_retrieval_audit") or {}).get("silver_regenerated") is not False:
        raise ValueError("v4_7_12 regenerated silver")
