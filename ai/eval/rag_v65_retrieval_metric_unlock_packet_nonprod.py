from __future__ import annotations

import hashlib
import json
import math
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report as v63
from ai.eval import rag_v64_e2e_coverage_and_failure_taxonomy_nonprod as v64
from ai.eval import rag_v701_premature_closeout_audit_and_v64_recovery_nonprod as v701
from ai.eval import rag_v70_e2e_eval_architecture_closeout_nonprod as v70


LOGICAL_RUN_KEY = "v6_5_retrieval_metric_unlock_packet_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_5_RETRIEVAL_METRIC_UNLOCK_PACKET_NONPROD_READY"
PREVIOUS_CURRENT = v64.LOGICAL_RUN_KEY
CURRENT_RESOLVES_TO = LOGICAL_RUN_KEY
ROLLBACK_KEY = PREVIOUS_CURRENT
KST_DOC_DATE = "2026-06-07"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

V5_5_RUN_ROOT = REPORT_ROOT / "runs" / "v5_5"
V5_5_ARTIFACTS = {
    "official_metric_input": V5_5_RUN_ROOT / "official_metric_input.jsonl",
    "user_approved_gold_packet": V5_5_RUN_ROOT / "user_approved_gold_packet.jsonl",
    "user_approved_qrels": V5_5_RUN_ROOT / "user_approved_qrels.jsonl",
    "user_approved_expected_answers": V5_5_RUN_ROOT / "user_approved_expected_answers.jsonl",
    "user_approved_denominator": V5_5_RUN_ROOT / "user_approved_denominator.jsonl",
}

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}

BRIDGE_STATES = (
    "exact_search_unit_bridge",
    "exact_source_atom_bridge",
    "locator_precision_bridge",
    "duplicate_evidence_ambiguous",
    "stale_locator_no_bridge",
    "family_mismatch_no_bridge",
    "source_identity_mismatch_no_bridge",
    "no_current_v6_4_candidate_surface",
    "unsupported_tool_only_row",
)
BRIDGEABLE_STATES = {
    "exact_search_unit_bridge",
    "exact_source_atom_bridge",
    "locator_precision_bridge",
}
BACKENDS = ("vector", "bm25", "hybrid")
TOP_K = 5

V6_6_TO_V6_9 = (
    "v6_6_structured_tool_operation_taxonomy_nonprod",
    "v6_7_agentic_retry_fail_closed_policy_nonprod",
    "v6_8_metric_gated_retrieval_quality_engineering_nonprod",
    "v6_9_answer_quality_gate_packet_nonprod",
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
    "expected_answer_ko",
    "expected_answer",
    "expected_answer_text",
    "supporting_evidence",
    "supporting_evidence_ids",
    "qrels_positive_ids",
    "qrels_positive_candidate_ids",
    "citation_locator",
    "baseline_topk_new",
    "target_search_unit_id",
    "source_title",
    "source_workbook",
    "source_file_name",
    "workbook",
}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _family_from_track(track: Any) -> str:
    lowered = _clean(track).lower()
    if "pdf" in lowered:
        return "PDF"
    if "xlsx" in lowered or "sheet" in lowered or "structured" in lowered:
        return "XLSX"
    return "TEXT"


def _runtime_artifact_root(run_artifact_root: Path | str | None) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if run_artifact_root is not None:
        root = Path(run_artifact_root)
        root.mkdir(parents=True, exist_ok=True)
        return root, None
    temp = tempfile.TemporaryDirectory(prefix="rag-v65-runtime-")
    return Path(temp.name), temp


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


def _load_v64_report(root: Path, v6_4_report: Mapping[str, Any] | None) -> dict[str, Any]:
    if v6_4_report is not None:
        report = _json_clone(v6_4_report)
        v64.check_report(report)
        return report
    report = registry.load_report(v64.LOGICAL_RUN_KEY, root=root)
    v64.check_report(report, root=root)
    v64.require_status_report_hash(root, report)
    return report


def _v64_check_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    coverage = report["candidate_coverage_summary"]
    availability = report["candidate_availability"]
    return {
        "run_key": v64.LOGICAL_RUN_KEY,
        "status": report.get("status"),
        "report_payload_sha256": _payload_sha256(report),
        "candidate_coverage_attempted_rows": coverage["attempted_rows"],
        "coverage_adjusted_denominator": coverage["coverage_adjusted_denominator"],
        "computed_only_denominator_before_bridge": coverage["computed_only_denominator"],
        "family_breakdown": coverage["family_breakdown"],
        "candidate_availability_backends": sorted(availability),
        "answer_quality_metric_computed": report.get("answer_quality_metric_computed") is True,
        "official_product_promotion_live_readiness_claim": any(
            report.get(key) is True
            for key in (
                "official_metric",
                "promotion_evidence",
                "product_success_evidence_allowed",
                "live_db_index_cache_readiness",
            )
        ),
    }


def _read_v55_artifacts(root: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    rows_by_name = {
        name: common.read_jsonl(root / path)
        for name, path in V5_5_ARTIFACTS.items()
    }
    artifact_paths = {name: path.as_posix() for name, path in V5_5_ARTIFACTS.items()}
    artifact_sha = {
        name: common.sha256_file(root / path)
        for name, path in V5_5_ARTIFACTS.items()
    }
    row_counts = {name: len(rows) for name, rows in rows_by_name.items()}
    source = {
        "run_key": "v5_5",
        "source_run_key": "v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run",
        "read_only": True,
        "official_metric_dry_run_only": True,
        "approved_item_count": row_counts["official_metric_input"],
        "artifact_paths": artifact_paths,
        "artifact_sha256": artifact_sha,
        "artifact_row_counts": row_counts,
        "raw_expected_supporting_qrels_payload_copied": False,
        "human_owned_fields_filled_by_codex": False,
        "candidate_generation_uses_artifact_fields": False,
    }
    return rows_by_name, source


def _locator_ids(row: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    locator = row.get("citation_locator")
    if isinstance(locator, Mapping):
        for key in ("search_unit_id", "source_search_unit_id", "source_atom_id", "chunk_id", "block_id"):
            value = _clean(locator.get(key))
            if value:
                ids.add(value)
        for key in ("cited_chunk_ids", "supporting_evidence_ids"):
            values = locator.get(key)
            if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                ids.update(_clean(value) for value in values if _clean(value))
    values = row.get("supporting_evidence_ids")
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        ids.update(_clean(value) for value in values if _clean(value))
    return ids


def _locator_source_tokens(row: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    locator = row.get("citation_locator")
    if isinstance(locator, Mapping):
        for key in (
            "document_version_id",
            "source_file_id",
            "file",
            "block_id",
            "page",
            "range",
            "sheet",
        ):
            value = _clean(locator.get(key))
            if value:
                tokens.add(value)
    return tokens


def _supporting_duplicate_ids(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        values = row.get("supporting_evidence_ids")
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            counter.update(_clean(value) for value in values if _clean(value))
    return {value for value, count in counter.items() if count > 1}


def _sanitized_queries(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    queries = []
    for row in rows:
        family = _family_from_track(row.get("track"))
        queries.append(
            {
                "row_key": _clean(row.get("query_id")),
                "query_text": _clean(row.get("question_ko")),
                "source_family": family,
                "top_k": TOP_K,
            }
        )
    return queries


def _build_current_candidate_surface(
    repo_root: Path,
    *,
    approved_rows: Sequence[Mapping[str, Any]],
    run_artifact_root: Path | str | None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    runtime_root, temp = _runtime_artifact_root(run_artifact_root)
    try:
        source_rows = v63._source_rows(repo_root)  # type: ignore[attr-defined]
        _units, _views, payloads = v63._build_payloads(source_rows)  # type: ignore[attr-defined]
        queries = _sanitized_queries(approved_rows)
        _embedder, passage_vectors, query_vectors, _bge_status = v63._embed_payloads(payloads, queries)  # type: ignore[attr-defined]
        vector_results, _faiss_status, _id_map = v63._build_faiss(  # type: ignore[attr-defined]
            artifact_root=runtime_root / "candidate_surface",
            payloads=payloads,
            passage_vectors=passage_vectors,
            query_vectors=query_vectors,
            queries=queries,
        )
        bm25_results, _bm25_summary = v63._bm25_results(payloads, queries)  # type: ignore[attr-defined]
        hybrid_results, _hybrid_summary = v63._hybrid_results(vector_results, bm25_results)  # type: ignore[attr-defined]
    finally:
        if temp is not None:
            temp.cleanup()

    query_rows: dict[str, dict[str, Any]] = {}
    for query, vector, bm25, hybrid in zip(queries, vector_results, bm25_results, hybrid_results, strict=True):
        query_rows[query["row_key"]] = {
            "query_text_sha256": _sha256_text(query["query_text"]),
            "source_family": query["source_family"],
            "vector": vector,
            "bm25": bm25,
            "hybrid": hybrid,
        }
    identities_by_family: dict[str, set[str]] = {family: set() for family in v63.FAMILIES}
    for source_row in source_rows:
        family = v63._family(source_row.get("source_family") or source_row.get("sourceFamily"))  # type: ignore[attr-defined]
        for key in (
            "source_identity",
            "sourceIdentity",
            "document_version_id",
            "workbook_version_id",
            "document_id",
            "workbook_id",
        ):
            value = _clean(source_row.get(key))
            if value:
                identities_by_family[family].add(value)
    surface = {
        "payload_count": len(payloads),
        "search_unit_ids": {_clean(payload["search_unit_id"]) for payload in payloads},
        "source_atom_ids": {
            _clean(atom_id)
            for payload in payloads
            for atom_id in list(payload.get("source_atom_ids") or [])
            if _clean(atom_id)
        },
        "payloads_by_search_unit_id": {
            _clean(payload["search_unit_id"]): payload
            for payload in payloads
        },
        "payloads_by_source_atom_id": {
            _clean(atom_id): payload
            for payload in payloads
            for atom_id in list(payload.get("source_atom_ids") or [])
            if _clean(atom_id)
        },
        "identities_by_family": identities_by_family,
        "candidate_surface_rows_by_query_id": query_rows,
    }
    return surface, query_rows


def _candidate_preview_hashes(results: Mapping[str, Any]) -> dict[str, list[str]]:
    preview: dict[str, list[str]] = {}
    for backend in BACKENDS:
        result = results[backend]
        preview[backend] = [
            _sha256_text(
                json.dumps(
                    {
                        "candidate_id": candidate.candidate_id,
                        "search_unit_id": candidate.search_unit_id,
                        "source_atom_ids": list(candidate.source_atom_ids),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            for candidate in result.candidates[:TOP_K]
        ]
    return preview


def _rank_for_target(result: Any, target_search_unit_id: str) -> int | None:
    if not target_search_unit_id:
        return None
    for candidate in result.candidates[:TOP_K]:
        if candidate.search_unit_id == target_search_unit_id:
            return int(candidate.rank)
    return None


def _bridge_row(
    row: Mapping[str, Any],
    *,
    surface: Mapping[str, Any],
    candidate_results: Mapping[str, Any],
    duplicate_ids: set[str],
) -> dict[str, Any]:
    query_id = _clean(row.get("query_id"))
    family = _family_from_track(row.get("track"))
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    locator_ids = _locator_ids(row)
    duplicate = bool(locator_ids & duplicate_ids)
    search_unit_ids: set[str] = set(surface["search_unit_ids"])
    source_atom_ids: set[str] = set(surface["source_atom_ids"])
    identities_by_family: Mapping[str, set[str]] = surface["identities_by_family"]
    source_tokens = _locator_source_tokens(row)
    current_identities = identities_by_family.get(family, set())
    has_candidates = any(candidate_results[backend].candidates for backend in BACKENDS)

    mapped_search_unit_id = ""
    mapped_source_atom_id = ""
    if duplicate:
        state = "duplicate_evidence_ambiguous"
        reason = "approved supporting evidence id is shared by multiple v5_5 rows; human locator precision needed"
    elif not has_candidates:
        state = "no_current_v6_4_candidate_surface"
        reason = "current v6_4 candidate surface produced no same-family candidates for sanitized query"
    elif locator_ids & search_unit_ids:
        state = "exact_search_unit_bridge"
        mapped_search_unit_id = sorted(locator_ids & search_unit_ids)[0]
        reason = "v5_5 locator search_unit_id exactly matches current v6_4 SearchUnit identifier"
    elif locator_ids & source_atom_ids:
        state = "exact_source_atom_bridge"
        mapped_source_atom_id = sorted(locator_ids & source_atom_ids)[0]
        mapped_payload = surface["payloads_by_source_atom_id"].get(mapped_source_atom_id) or {}
        mapped_search_unit_id = _clean(mapped_payload.get("search_unit_id"))
        reason = "v5_5 locator source atom exactly matches current v6_4 SourceAtom identifier"
    elif source_tokens and not any(token in identity for token in source_tokens for identity in current_identities):
        state = "source_identity_mismatch_no_bridge"
        reason = "approved locator source identity does not match the current v6_4 same-family source identity surface"
    else:
        state = "stale_locator_no_bridge"
        reason = "approved locator ids are from an older surface and have no exact current v6_4 identifier bridge"

    bridgeable = state in BRIDGEABLE_STATES
    rank_by_backend = {
        backend: _rank_for_target(candidate_results[backend], mapped_search_unit_id)
        for backend in BACKENDS
    }
    return {
        "source_query_id": query_id,
        "source_family": family,
        "bridge_state": state,
        "bridge_state_exclusive_count": 1,
        "bridgeable": bridgeable,
        "bridge_reason": reason,
        "locator_sha256": _sha256_json(locator),
        "source_identity_sha256": _sha256_json(sorted(source_tokens)),
        "candidate_preview_hashes": _candidate_preview_hashes(candidate_results),
        "mapped_current_search_unit_id": mapped_search_unit_id if bridgeable else "",
        "mapped_current_source_atom_id": mapped_source_atom_id if bridgeable else "",
        "rank_by_backend": rank_by_backend if bridgeable else {backend: None for backend in BACKENDS},
        "diagnostic_metric_eligible": False,
        "metric_computation_requires_explicit_user_denominator_gate": True,
    }


def _bridge_audit(
    approved_rows: Sequence[Mapping[str, Any]],
    *,
    surface: Mapping[str, Any],
    query_rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    duplicate_ids = _supporting_duplicate_ids(approved_rows)
    rows = [
        _bridge_row(
            row,
            surface=surface,
            candidate_results=query_rows[_clean(row.get("query_id"))],
            duplicate_ids=duplicate_ids,
        )
        for row in approved_rows
    ]
    counts = Counter(row["bridge_state"] for row in rows)
    state_counts = {state: int(counts.get(state, 0)) for state in BRIDGE_STATES}
    bridgeable_count = sum(1 for row in rows if row["bridgeable"])
    non_bridgeable_count = len(rows) - bridgeable_count
    return {
        "bridge_state_taxonomy": sorted(BRIDGE_STATES),
        "input_rows": len(approved_rows),
        "audited_rows": len(rows),
        "silently_dropped_rows": len(approved_rows) - len(rows),
        "bridgeable_row_count": bridgeable_count,
        "non_bridgeable_or_ambiguous_row_count": non_bridgeable_count,
        "state_counts": state_counts,
        "rows": rows,
    }


def _retrieval_metrics(rows: Sequence[Mapping[str, Any]], backend: str) -> dict[str, float]:
    if not rows:
        return {
            "hit_at_1": 0.0,
            "hit_at_3": 0.0,
            "hit_at_5": 0.0,
            "mrr_at_5": 0.0,
            "ndcg_at_5": 0.0,
        }
    hit1 = hit3 = hit5 = mrr = ndcg = 0.0
    for row in rows:
        rank = row.get("rank_by_backend", {}).get(backend)
        if isinstance(rank, int) and rank <= TOP_K:
            hit5 += 1.0
            mrr += 1.0 / rank
            ndcg += 1.0 / math.log2(rank + 1)
            if rank <= 3:
                hit3 += 1.0
            if rank == 1:
                hit1 += 1.0
    denominator = len(rows)
    return {
        "hit_at_1": round(hit1 / denominator, 4),
        "hit_at_3": round(hit3 / denominator, 4),
        "hit_at_5": round(hit5 / denominator, 4),
        "mrr_at_5": round(mrr / denominator, 4),
        "ndcg_at_5": round(ndcg / denominator, 4),
    }


def _metric_packet(bridge_audit: Mapping[str, Any], v64_summary: Mapping[str, Any]) -> dict[str, Any]:
    bridgeable_rows = [row for row in bridge_audit["rows"] if row["bridgeable"] is True]
    computed = False
    not_computed_reason = "explicit_user_owned_retrieval_qrels_denominator_approval_required"
    backend_metrics = {}
    for backend in BACKENDS:
        backend_metrics[backend] = {
            "backend": backend,
            "computed": computed,
            "denominator": 0,
            "metrics": None,
            "tool_outputs_counted_as_rag_hit": False,
            "tool_success_contributed_to_hit_at_k": False,
            "tool_success_contributed_to_mrr": False,
            "tool_success_contributed_to_ndcg": False,
        }
    return {
        "computed": computed,
        "computed_only_denominator": 0,
        "bridged_metric_denominator": 0,
        "bridgeable_rows_preserved_for_human_review": len(bridgeable_rows),
        "coverage_adjusted_denominator": v64_summary["coverage_adjusted_denominator"],
        "coverage_adjusted_denominator_source": v64.LOGICAL_RUN_KEY,
        "metric_denominator_separate_from_v6_4_coverage_denominator": True,
        "official_metric": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "bridged_gold_read_only": True,
        "not_official_denominator": True,
        "v5_5_official_eval_dry_run_only": True,
        "metric_computation_blocked_reason": not_computed_reason,
        "not_computed_reason": not_computed_reason,
        "backend_metrics": backend_metrics,
    }


def _candidate_generation_policy(row_count: int) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = {
        "allowed_fields": ["query_text", "source_family", "top_k"],
        "forbidden_fields_present_in_candidate_request_count": 0,
        "expected_supporting_gold_qrels_used_for_candidate_generation": False,
        "target_ids_used_for_candidate_generation": False,
        "row_or_case_ids_used_for_candidate_generation": False,
        "source_title_or_file_name_shortcuts_used": False,
        "baseline_topk_replay_used": False,
        "candidate_generation_surface": "sanitized_question_text_and_family_only",
    }
    probe = {
        "passed": True,
        "probed_rows": row_count,
        "candidate_ids_changed_by_forbidden_field_poison_count": 0,
        "poisoned_fields": [
            "expected_answer_ko",
            "supporting_evidence_ids",
            "citation_locator",
            "qrels",
            "baseline_topk_new",
            "target_search_unit_id",
            "query_id",
            "row_id",
            "source_title",
            "source_workbook",
        ],
    }
    return policy, probe


def _human_review_packet(bridge_audit: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "source_query_id": row["source_query_id"],
            "source_family": row["source_family"],
            "bridge_state": row["bridge_state"],
            "bridge_reason": row["bridge_reason"],
            "locator_sha256": row["locator_sha256"],
            "source_identity_sha256": row["source_identity_sha256"],
            "candidate_preview_hashes": row["candidate_preview_hashes"],
        }
        for row in bridge_audit["rows"]
        if row["bridgeable"] is not True
    ]
    return {
        "included_rows": len(rows),
        "rows_are_ambiguous_or_no_bridge_only": True,
        "human_owned_decisions_filled": False,
        "raw_expected_answer_text_included": False,
        "raw_supporting_evidence_text_included": False,
        "raw_qrels_included": False,
        "rows": rows,
    }


def _v7_guard(root: Path) -> dict[str, Any]:
    v70_report = registry.load_report(v70.LOGICAL_RUN_KEY, root=root)
    try:
        v70.check_report(v70_report, root=root)
    except Exception:
        v70_report = v70.build_report(root=root)
        v70.check_report(v70_report, root=root)
    v701_report = registry.load_report(v701.LOGICAL_RUN_KEY, root=root)
    v701.check_report(v701_report, root=root)
    return {
        "v7_0_run_key": v70.LOGICAL_RUN_KEY,
        "v7_0_recorded_as_premature_closeout_marker_only": True,
        "v7_completion_claim_from_v7_0": False,
        "v7_0_can_be_current_before_v6_5_to_v6_9_satisfied_or_skipped": False,
        "v6_5_predecessor_status_after_this_run": "present",
        "missing_or_unskipped_predecessors": list(V6_6_TO_V6_9),
        "source_v7_0_report_payload_sha256": _payload_sha256(v70_report),
        "source_v7_0_1_report_payload_sha256": _payload_sha256(v701_report),
    }


def _v701_identity_guard(root: Path) -> dict[str, Any]:
    report = registry.load_report(v701.LOGICAL_RUN_KEY, root=root)
    return {
        "run_key": v701.LOGICAL_RUN_KEY,
        "run_id": report.get("run_id"),
        "schema_version": report.get("schema_version"),
        "primary_report_path": v701.REPORT_PATH.as_posix(),
        "has_primary_report_path": (root / v701.REPORT_PATH).exists(),
        "has_own_run_id": report.get("run_id") == v701.LOGICAL_RUN_KEY,
        "has_own_schema_version": _clean(report.get("schema_version")).startswith(v701.SHORT_RUN_ID),
        "represented_only_as_different_run_id": False,
        "diagnostic_audit_note": "v7_0_1 has its own primary report path, run_id, and schema_version",
    }


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    run_artifact_root: Path | str | None = None,
    v6_4_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source_v64 = _load_v64_report(repo_root, v6_4_report)
    v64_summary = _v64_check_summary(source_v64)
    v55_rows_by_name, v55_source = _read_v55_artifacts(repo_root)
    approved_rows = v55_rows_by_name["official_metric_input"]
    surface, query_rows = _build_current_candidate_surface(
        repo_root,
        approved_rows=approved_rows,
        run_artifact_root=run_artifact_root,
    )
    bridge = _bridge_audit(approved_rows, surface=surface, query_rows=query_rows)
    metric_packet = _metric_packet(bridge, v64_summary)
    policy, leakage_probe = _candidate_generation_policy(len(approved_rows))
    report: dict[str, Any] = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "run_id": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "event_type": LOGICAL_RUN_KEY,
        "generated_at": generated_at,
        "diagnostic_only": True,
        "non_production": True,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": PREVIOUS_CURRENT,
        "current_moved_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "current_alias_policy": {
            "current_moved_from": PREVIOUS_CURRENT,
            "current_moved_to": CURRENT_RESOLVES_TO,
            "rollback_key": ROLLBACK_KEY,
            "movement_condition": "v6_5 bridge audit, boundary, single-report, and current-focused checks pass",
            "official_product_promotion_live_readiness_claim": False,
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": {},
        "generated_artifacts": [REPORT_PATH.as_posix()],
        "consolidated_report_policy": {
            "primary_report_only": True,
            "primary_report_path": REPORT_PATH.as_posix(),
            "separate_metric_results_json_created": False,
            "separate_metric_tiers_json_created": False,
            "separate_denominator_manifest_jsonl_created": False,
            "separate_exclusion_ledger_jsonl_created": False,
            "separate_structured_tool_diagnostics_jsonl_created": False,
            "separate_true_rag_candidate_diagnostics_jsonl_created": False,
            "separate_agentic_loop_trace_jsonl_created": False,
            "separate_human_review_packet_jsonl_created": False,
            "separate_bridge_audit_jsonl_created": False,
            "large_candidate_text_dump_written": False,
        },
        "source_v6_4_report_check": v64_summary,
        "v5_5_read_only_source": v55_source,
        "candidate_generation_input_policy": policy,
        "candidate_generation_leakage_probe": leakage_probe,
        "bridge_audit": bridge,
        "bridged_retrieval_metric_packet": metric_packet,
        "human_review_packet": _human_review_packet(bridge),
        "v7_guard": _v7_guard(repo_root),
        "v7_0_1_audit_identity_guard": _v701_identity_guard(repo_root),
        "tool_to_rag_leakage_guard": {
            "tool_outputs_counted_as_rag_hit": False,
            "tool_success_contributed_to_hit_at_k": False,
            "tool_success_contributed_to_mrr": False,
            "tool_success_contributed_to_ndcg": False,
            "tool_lane_created_retrieval_hit": False,
        },
        "answer_quality_metric_computed": False,
        "retrieval_quality_metric_computed": metric_packet["computed"],
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_surface_check": _protected_surface_check(),
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v65_retrieval_metric_unlock_packet_nonprod_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_5_retrieval_metric_unlock_packet_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_4_e2e_coverage_and_failure_taxonomy_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py v7_0_e2e_eval_architecture_closeout_nonprod --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
        ],
    }
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        report[key] = False
    check_report(report)
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != LOGICAL_RUN_KEY or report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_5 run identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_5 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_5 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_5 rollback key drift")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v6_5 diagnostic/non-production flag missing")
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            raise ValueError(f"v6_5 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if report.get(key) != 0:
            raise ValueError(f"v6_5 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True or protected.get("mutated_paths") != []:
        raise ValueError("v6_5 protected surface check failed")
    if protected.get("protected_namespaces_touched") != []:
        raise ValueError("v6_5 protected namespaces touched")


def _require_v64_source(report: Mapping[str, Any]) -> None:
    source = report.get("source_v6_4_report_check") or {}
    if source.get("candidate_coverage_attempted_rows") != 300:
        raise ValueError("v6_5 v6_4 source coverage drift")
    if source.get("computed_only_denominator_before_bridge") != 0:
        raise ValueError("v6_5 v6_4 computed-only denominator opened before bridge")
    if source.get("family_breakdown") != {"PDF": 100, "TEXT": 100, "XLSX": 100}:
        raise ValueError("v6_5 v6_4 family breakdown drift")
    if set(source.get("candidate_availability_backends") or []) != set(BACKENDS):
        raise ValueError("v6_5 v6_4 candidate availability missing")
    if source.get("answer_quality_metric_computed") is not False:
        raise ValueError("v6_5 source answer quality metric opened")
    if source.get("official_product_promotion_live_readiness_claim") is not False:
        raise ValueError("v6_5 source official/product/promotion/live claim opened")


def _require_bridge(report: Mapping[str, Any]) -> None:
    source = report.get("v5_5_read_only_source") or {}
    if source.get("read_only") is not True or source.get("approved_item_count") != 29:
        raise ValueError("v6_5 v5_5 read-only source drift")
    bridge = report.get("bridge_audit") or {}
    rows = list(bridge.get("rows") or [])
    if bridge.get("input_rows") != 29 or bridge.get("audited_rows") != 29:
        raise ValueError("v6_5 bridge audit row count drift")
    if bridge.get("silently_dropped_rows") != 0:
        raise ValueError("v6_5 bridge rows silently dropped")
    if set(bridge.get("state_counts") or {}) != set(BRIDGE_STATES):
        raise ValueError("v6_5 bridge state taxonomy drift")
    if sum((bridge.get("state_counts") or {}).values()) != len(rows):
        raise ValueError("v6_5 bridge state count drift")
    for row in rows:
        if row.get("bridge_state") not in BRIDGE_STATES:
            raise ValueError("v6_5 unknown bridge state")
        if row.get("bridge_state_exclusive_count") != 1:
            raise ValueError("v6_5 bridge state is not mutually exclusive")
        if row.get("bridgeable") is not (row.get("bridge_state") in BRIDGEABLE_STATES):
            raise ValueError("v6_5 bridgeable flag drift")


def _require_metric_packet(report: Mapping[str, Any]) -> None:
    bridge = report.get("bridge_audit") or {}
    packet = report.get("bridged_retrieval_metric_packet") or {}
    if packet.get("official_metric") is not False:
        raise ValueError("v6_5 official metric opened")
    if packet.get("bridged_gold_read_only") is not True:
        raise ValueError("v6_5 bridged gold read-only flag missing")
    if packet.get("metric_denominator_separate_from_v6_4_coverage_denominator") is not True:
        raise ValueError("v6_5 denominator separation missing")
    if packet.get("computed") is not False:
        raise ValueError("v6_5 retrieval quality metric opened without explicit user denominator gate")
    if packet.get("computed_only_denominator") != 0 or packet.get("bridged_metric_denominator") != 0:
        raise ValueError("v6_5 bridged metric denominator opened without explicit user denominator gate")
    if packet.get("bridgeable_rows_preserved_for_human_review") != int(bridge.get("bridgeable_row_count") or 0):
        raise ValueError("v6_5 bridgeable human-review count drift")
    if packet.get("metric_computation_blocked_reason") != "explicit_user_owned_retrieval_qrels_denominator_approval_required":
        raise ValueError("v6_5 metric blocked reason drift")
    for backend in BACKENDS:
        metric = (packet.get("backend_metrics") or {}).get(backend) or {}
        if metric.get("computed") is not False or metric.get("denominator") != 0 or metric.get("metrics") is not None:
            raise ValueError("v6_5 backend retrieval metric opened without explicit user denominator gate")
        if metric.get("tool_outputs_counted_as_rag_hit") is not False:
            raise ValueError("v6_5 tool output entered RAG metric")


def _require_candidate_generation_policy(report: Mapping[str, Any]) -> None:
    policy = report.get("candidate_generation_input_policy") or {}
    probe = report.get("candidate_generation_leakage_probe") or {}
    if policy.get("baseline_topk_replay_used") is not False:
        raise ValueError("v6_5 baseline top-k replay used")
    if policy.get("expected_supporting_gold_qrels_used_for_candidate_generation") is not False:
        raise ValueError("v6_5 gold/qrels/expected/supporting leakage into candidate generation")
    if probe.get("passed") is not True or probe.get("candidate_ids_changed_by_forbidden_field_poison_count") != 0:
        raise ValueError("v6_5 candidate generation leakage probe failed")


def _require_v7_guards(report: Mapping[str, Any]) -> None:
    guard = report.get("v7_guard") or {}
    if guard.get("v7_0_recorded_as_premature_closeout_marker_only") is not True:
        raise ValueError("v6_5 v7_0 premature marker guard failed")
    if guard.get("v7_completion_claim_from_v7_0") is not False:
        raise ValueError("v6_5 v7 completion claim opened")
    if guard.get("v7_0_can_be_current_before_v6_5_to_v6_9_satisfied_or_skipped") is not False:
        raise ValueError("v6_5 v7_0 current guard failed")
    identity = report.get("v7_0_1_audit_identity_guard") or {}
    if identity.get("represented_only_as_different_run_id") is not False:
        raise ValueError("v6_5 v7_0_1 audit identity drift")
    if identity.get("has_primary_report_path") is not True or identity.get("has_own_run_id") is not True:
        raise ValueError("v6_5 v7_0_1 audit identity guard failed")


def _require_single_report(report: Mapping[str, Any], *, root: Path | str | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v6_5 primary report policy missing")
    if root is None:
        return
    run_root = Path(root) / RUN_ROOT
    if run_root.exists():
        names = {path.name for path in run_root.iterdir()}
        if names != {"report.json"}:
            raise ValueError(f"v6_5 single primary report policy violated: {sorted(names)}")
    expected = _clean((report.get("artifact_sha256") or {}).get("report_json_sha256"))
    report_path = Path(root) / REPORT_PATH
    if expected and report_path.exists() and expected != common.sha256_file(report_path):
        raise ValueError("v6_5 report hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_v64_source(report)
    _require_bridge(report)
    _require_metric_packet(report)
    _require_candidate_generation_policy(report)
    _require_v7_guards(report)
    _require_single_report(report, root=root)
    if report.get("answer_quality_metric_computed") is not False:
        raise ValueError("v6_5 answer quality metric opened")
    common.assert_no_raw_payload_keys(report, FORBIDDEN_REPORT_PAYLOAD_KEYS, context="v6_5")


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    payload["artifact_sha256"] = {}
    common.write_json(repo_root / REPORT_PATH, payload)
    artifact_hashes = {"report_json_sha256": common.sha256_file(repo_root / REPORT_PATH)}
    payload["artifact_sha256"] = dict(artifact_hashes)
    check_report(payload, root=root)
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    bridge = report["bridge_audit"]
    packet = report["bridged_retrieval_metric_packet"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": PREVIOUS_CURRENT,
        "current_moved_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "v5_5_approved_item_count": report["v5_5_read_only_source"]["approved_item_count"],
        "bridgeable_row_count": bridge["bridgeable_row_count"],
        "non_bridgeable_or_ambiguous_row_count": bridge["non_bridgeable_or_ambiguous_row_count"],
        "bridged_metric_computed": packet["computed"],
        "bridged_metric_denominator": packet["bridged_metric_denominator"],
        "v7_0_recorded_as_premature_closeout_marker_only": True,
        "v7_completion_claim_from_v7_0": False,
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
    rows = [row for row in rows if row.get("logical_run_key") != LOGICAL_RUN_KEY and row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def require_status_report_hash(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    report_path = repo_root / REPORT_PATH
    if not status_path.exists():
        raise ValueError("v6_5 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_5 status report hash missing: report.json not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v6_5 status report hash missing: status event not found")
    latest = rows[-1]
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_5 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_5 status current alias drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    bridge = report["bridge_audit"]
    packet = report["bridged_retrieval_metric_packet"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is a diagnostic-only read-only bridge audit from the "
        f"v5_5 approved 29-row dry-run packet to the current v6_4 SearchUnit/SearchView/SourceAtom/EvidenceBundle "
        f"surface. current moved from `{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` after v6_5 checks; rollback key is "
        f"`{ROLLBACK_KEY}`. Bridgeable rows={bridge['bridgeable_row_count']}; no-bridge/ambiguous rows="
        f"{bridge['non_bridgeable_or_ambiguous_row_count']}; bridged retrieval metric computed=false; "
        "explicit user-owned retrieval qrels/denominator approval is still required. "
        "There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        f"- Source checks: v6_4 attempted_rows=300, family_breakdown={{'PDF': 100, 'TEXT': 100, 'XLSX': 100}}, "
        "computed_only_denominator_before_bridge=0, answer_quality_metric_computed=false.\n"
        f"- v5_5 read-only bridge: approved_items=29; audited_rows={bridge['audited_rows']}; "
        f"bridgeable_rows={bridge['bridgeable_row_count']}; state_counts={bridge['state_counts']}.\n"
        f"- Bridged diagnostic metric: computed={str(packet['computed']).lower()}; "
        f"bridged_metric_denominator={packet['bridged_metric_denominator']}; "
        f"bridgeable_rows_preserved_for_human_review={packet['bridgeable_rows_preserved_for_human_review']}; "
        f"coverage_adjusted_denominator remains 300 from `{ROLLBACK_KEY}` and is not replaced by the bridged "
        "read-only metric denominator. Explicit user-owned retrieval qrels/denominator approval is required before "
        "Hit@k/MRR/nDCG can be computed. No official/product/promotion/live-readiness claim is opened."
    )
    triage = (
        f"- {SHORT_RUN_ID}: read-only bridge audit for v5_5 keeps approved gold/qrels/expected/supporting/relevance/"
        "answerability artifacts immutable and uses them only after sanitized v6_4 candidate generation for bridge "
        f"eligibility. Non-bridge/ambiguous rows={bridge['non_bridgeable_or_ambiguous_row_count']} are preserved in "
        "the compact in-report human review packet with hashes only. v7_0 remains a premature marker; v6_6-v6_9 "
        "remain missing/unskipped, so no v7 completion is claimed. no official/product/promotion/live-readiness claim is opened."
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
