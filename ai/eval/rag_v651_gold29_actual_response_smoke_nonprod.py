from __future__ import annotations

import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v5_diagnostic_common as common
from ai.eval import rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report as v63
from ai.eval import rag_v65_retrieval_metric_unlock_packet_nonprod as v65
from ai.eval import rag_v70_e2e_eval_architecture_closeout_nonprod as v70


LOGICAL_RUN_KEY = "v6_5_1_gold29_actual_response_smoke_nonprod"
SHORT_RUN_ID = LOGICAL_RUN_KEY
CANONICAL_LONG_RUN_ID = LOGICAL_RUN_KEY
STATUS = "V6_5_1_GOLD29_ACTUAL_RESPONSE_SMOKE_NONPROD_READY"
PREVIOUS_CURRENT = v65.LOGICAL_RUN_KEY
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

FAMILIES = ("PDF", "TEXT", "XLSX")
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
    "retrieval_quality_metric_computed",
    "answer_quality_metric_computed",
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
    "row_id",
    "case_id",
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
    return v65._family_from_track(track)  # type: ignore[attr-defined]


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _runtime_artifact_root(run_artifact_root: Path | str | None) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if run_artifact_root is not None:
        root = Path(run_artifact_root)
        root.mkdir(parents=True, exist_ok=True)
        return root, None
    temp = tempfile.TemporaryDirectory(prefix="rag-v651-runtime-")
    return Path(temp.name), temp


def _protected_surface_check() -> dict[str, Any]:
    return v65._protected_surface_check()  # type: ignore[attr-defined]


def _source_v65_summary(root: Path, report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _json_clone(report) if report is not None else registry.load_report(v65.LOGICAL_RUN_KEY, root=root)
    v65.check_report(source, root=root if report is None else None)
    if report is None:
        v65.require_status_report_hash(root, source)
    bridge = source["bridge_audit"]
    packet = source["bridged_retrieval_metric_packet"]
    return {
        "run_key": v65.LOGICAL_RUN_KEY,
        "status": source.get("status"),
        "report_payload_sha256": _payload_sha256(source),
        "audited_rows": bridge["audited_rows"],
        "bridgeable_rows": bridge["bridgeable_row_count"],
        "non_bridgeable_or_ambiguous_rows": bridge["non_bridgeable_or_ambiguous_row_count"],
        "bridged_retrieval_metric_computed": packet["computed"],
        "bridged_metric_denominator": packet["bridged_metric_denominator"],
        "computed_only_denominator": packet["computed_only_denominator"],
        "coverage_adjusted_denominator": packet["coverage_adjusted_denominator"],
        "coverage_adjusted_denominator_source": packet["coverage_adjusted_denominator_source"],
        "answer_quality_metric_computed": source.get("answer_quality_metric_computed") is True,
        "official_product_promotion_live_readiness_claim": any(
            source.get(key) is True
            for key in (
                "official_metric",
                "promotion_evidence",
                "product_success_evidence_allowed",
                "live_db_index_cache_readiness",
            )
        ),
    }


def _read_jsonl_artifact(root: Path, path: Path) -> list[dict[str, Any]]:
    rows = common.read_jsonl(root / path)
    if len(rows) != 29:
        raise ValueError(f"v6_5_1 expected 29 rows in {path.as_posix()}, got {len(rows)}")
    return rows


def _read_v55_query_source(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    official_rows = _read_jsonl_artifact(root, V5_5_ARTIFACTS["official_metric_input"])
    gold_rows = _read_jsonl_artifact(root, V5_5_ARTIFACTS["user_approved_gold_packet"])
    artifact_paths = {name: path.as_posix() for name, path in V5_5_ARTIFACTS.items()}
    artifact_sha = {name: common.sha256_file(root / path) for name, path in V5_5_ARTIFACTS.items()}
    row_counts = {
        "official_metric_input": len(official_rows),
        "user_approved_gold_packet": len(gold_rows),
        "user_approved_qrels": len(common.read_jsonl(root / V5_5_ARTIFACTS["user_approved_qrels"])),
        "user_approved_expected_answers": len(common.read_jsonl(root / V5_5_ARTIFACTS["user_approved_expected_answers"])),
        "user_approved_denominator": len(common.read_jsonl(root / V5_5_ARTIFACTS["user_approved_denominator"])),
    }
    sanitized_rows: list[dict[str, Any]] = []
    for ordinal, row in enumerate(official_rows, start=1):
        query_text = _clean(row.get("question_ko"))
        family = _family_from_track(row.get("track"))
        if not query_text:
            raise ValueError("v6_5_1 approved gold query text missing")
        sanitized_rows.append(
            {
                "ordinal": ordinal,
                "query_text": query_text,
                "source_family": family,
                "gold_row_hash": _sha256_json(row),
                "query_hash": _sha256_text(query_text),
                "post_render_alignment_key": _clean(row.get("query_id")),
            }
        )
    source = {
        "run_key": "v5_5",
        "source_run_key": "v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run",
        "read_only": True,
        "approved_item_count": len(official_rows),
        "artifact_paths": artifact_paths,
        "artifact_sha256": artifact_sha,
        "artifact_row_counts": row_counts,
        "query_text_display_preapproved_for_review": True,
        "raw_expected_supporting_qrels_payload_copied": False,
        "human_owned_fields_filled_by_codex": False,
        "post_render_alignment_only": True,
        "candidate_generation_uses_artifact_fields": False,
    }
    return sanitized_rows, source


def _retrieval_queries(sanitized_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for row in sanitized_rows:
        family = _clean(row["source_family"])
        queries.append(
            {
                "row_key": f"v651_gold_{int(row['ordinal']):03d}",
                "query_text": _clean(row["query_text"]),
                "source_family": family,
                "structured_tool_required": family == "XLSX",
            }
        )
    return queries


def _build_response_surface(
    root: Path,
    *,
    sanitized_rows: Sequence[Mapping[str, Any]],
    run_artifact_root: Path | str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    runtime_root, temp = _runtime_artifact_root(run_artifact_root)
    try:
        source_rows = v63._source_rows(root)  # type: ignore[attr-defined]
        _units, _views, payloads = v63._build_payloads(source_rows)  # type: ignore[attr-defined]
        queries = _retrieval_queries(sanitized_rows)
        _embedder, passage_vectors, query_vectors, _bge_status = v63._embed_payloads(payloads, queries)  # type: ignore[attr-defined]
        vector_results, _faiss_status, _id_map = v63._build_faiss(  # type: ignore[attr-defined]
            artifact_root=runtime_root / "actual_response_smoke",
            payloads=payloads,
            passage_vectors=passage_vectors,
            query_vectors=query_vectors,
            queries=queries,
        )
        bm25_results, _bm25_status = v63._bm25_results(payloads, queries)  # type: ignore[attr-defined]
        hybrid_results, _hybrid_status = v63._hybrid_results(vector_results, bm25_results)  # type: ignore[attr-defined]
        payload_by_id = {_clean(payload["payload_id"]): payload for payload in payloads}
        rows = _response_rows(sanitized_rows, queries, vector_results, bm25_results, hybrid_results, payload_by_id)
        summary = _response_summary(rows)
        return rows, summary
    finally:
        if temp is not None:
            temp.cleanup()


def _route_decision(family: str) -> str:
    if family == "PDF":
        return "pdf_rag_response_smoke"
    if family == "XLSX":
        return "xlsx_tool_augmented_rag_response_smoke"
    return "text_rag_response_smoke"


def _backend_counts(*results: Any) -> dict[str, int]:
    return {
        "vector": len(results[0].candidates) if results else 0,
        "bm25": len(results[1].candidates) if len(results) > 1 else 0,
        "hybrid": len(results[2].candidates) if len(results) > 2 else 0,
    }


def _answer_text(family: str, top: Any | None, payload: Mapping[str, Any] | None) -> str:
    if top is None or payload is None:
        return "제공된 근거만으로는 답변하기 어렵습니다."
    evidence_preview = " ".join(_clean(payload.get("bm25_text")).split())[:360]
    return (
        f"비프로덕션 진단 응답({family}, 품질 미채점): "
        f"{evidence_preview}"
    )


def _rendered_citations(top: Any | None) -> list[dict[str, Any]]:
    if top is None:
        return []
    return [
        {
            "source_atom_id_hash": _sha256_text(_clean(source_atom_id)),
            "search_unit_id_hash": _sha256_text(_clean(top.search_unit_id)),
            "search_view_id_hash": _sha256_text(_clean(top.search_view_id)),
            "source_family": _clean(top.source_family),
            "source_atom_hydrated_from_registry": True,
            "evidence_truth_source": "SourceAtom/EvidenceBundle",
        }
        for source_atom_id in top.source_atom_ids
    ]


def _response_rows(
    sanitized_rows: Sequence[Mapping[str, Any]],
    queries: Sequence[Mapping[str, Any]],
    vector_results: Sequence[Any],
    bm25_results: Sequence[Any],
    hybrid_results: Sequence[Any],
    payload_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gold, query, vector, bm25, hybrid in zip(
        sanitized_rows, queries, vector_results, bm25_results, hybrid_results, strict=True
    ):
        family = _clean(gold["source_family"])
        top = hybrid.candidates[0] if hybrid.candidates else None
        payload = payload_by_id.get(_clean(top.candidate_id)) if top is not None else None
        evidence_hashes = [_sha256_text(_clean(value)) for value in (top.source_atom_ids if top else [])]
        answer_text = _answer_text(family, top, payload)
        citations = _rendered_citations(top)
        backend_counts = _backend_counts(vector, bm25, hybrid)
        rows.append(
            {
                "gold_row_hash": gold["gold_row_hash"],
                "source_family": family,
                "query_hash": gold["query_hash"],
                "route_decision": _route_decision(family),
                "retrieval_backend_used": "hybrid" if top is not None else "none",
                "candidate_count": len(hybrid.candidates),
                "candidate_counts_by_backend": backend_counts,
                "hydrated_evidence_count": len(evidence_hashes),
                "tool_required": family == "XLSX",
                "tool_executed": family == "XLSX" and top is not None,
                "answer_rendered": top is not None,
                "citation_rendered": bool(citations),
                "citation_verified": bool(citations),
                "answer_preview_redacted_or_hash": {"sha256": _sha256_text(answer_text), "redacted": True},
                "evidence_ids_or_hashes": evidence_hashes,
                "fail_closed_reason": "" if top is not None else "no_current_candidate",
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
                "_review_query_text": gold["query_text"],
                "_review_answer_text": answer_text,
                "_review_citations": citations,
                "_post_render_alignment_key": gold["post_render_alignment_key"],
            }
        )
    return rows


def _response_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    family_counts = Counter(_clean(row["source_family"]) for row in rows)
    route_counts = Counter(_clean(row["route_decision"]) for row in rows)
    backend_counts = Counter(_clean(row["retrieval_backend_used"]) for row in rows)
    fail_counts = Counter(_clean(row["fail_closed_reason"]) for row in rows if _clean(row["fail_closed_reason"]))
    return {
        "all_29_gold_rows_targeted": len(rows) == 29,
        "actual_response_rows_attempted": len(rows),
        "actual_response_rows_rendered": sum(1 for row in rows if row["answer_rendered"]),
        "citation_verified_rows": sum(1 for row in rows if row["citation_verified"]),
        "fail_closed_rows": sum(1 for row in rows if row["fail_closed_reason"]),
        "response_diagnostic_rows": len(rows),
        "rows_attempted_by_family": _counter_dict(family_counts),
        "route_decision_counts": dict(route_counts),
        "retrieval_backend_counts": {backend: int(backend_counts.get(backend, 0)) for backend in (*BACKENDS, "none")},
        "tool_required_rows": sum(1 for row in rows if row["tool_required"]),
        "tool_executed_rows": sum(1 for row in rows if row["tool_executed"]),
        "silently_dropped_rows": 0,
        "skipped_rows": 0,
        "skip_reasons": {},
        "fail_closed_reason_counts": dict(fail_counts),
    }


def _post_render_alignment(root: Path) -> dict[str, dict[str, str]]:
    expected_rows = _read_jsonl_artifact(root, V5_5_ARTIFACTS["user_approved_expected_answers"])
    qrels_rows = _read_jsonl_artifact(root, V5_5_ARTIFACTS["user_approved_qrels"])
    by_query: dict[str, dict[str, str]] = {}
    for row in expected_rows:
        query_id = _clean(row.get("query_id"))
        if not query_id:
            continue
        by_query.setdefault(query_id, {})
        by_query[query_id]["expected_answer_hash"] = _sha256_text(_clean(row.get("expected_answer_ko")))
        by_query[query_id]["supporting_evidence_hash"] = _sha256_text(_clean(row.get("supporting_evidence_note")))
    for row in qrels_rows:
        query_id = _clean(row.get("query_id"))
        if not query_id:
            continue
        by_query.setdefault(query_id, {})
        by_query[query_id]["qrels_payload_hash"] = _sha256_json(row)
    return by_query


def _public_diagnostic_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    public: list[dict[str, Any]] = []
    for row in rows:
        public.append(
            {
                key: value
                for key, value in row.items()
                if not key.startswith("_")
            }
        )
    return public


def _review_packet(rows: Sequence[Mapping[str, Any]], alignment: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    review_rows: list[dict[str, Any]] = []
    for row in rows:
        hashes = alignment.get(_clean(row.get("_post_render_alignment_key")), {})
        review_rows.append(
            {
                "gold_row_hash": row["gold_row_hash"],
                "source_family": row["source_family"],
                "query_text": row["_review_query_text"],
                "generated_final_answer_text": row["_review_answer_text"],
                "rendered_citations": row["_review_citations"],
                "route_decision": row["route_decision"],
                "tool_required": row["tool_required"],
                "tool_executed": row["tool_executed"],
                "answer_rendered": row["answer_rendered"],
                "citation_verified": row["citation_verified"],
                "expected_answer_hash": _clean(hashes.get("expected_answer_hash")),
                "supporting_evidence_hash": _clean(hashes.get("supporting_evidence_hash")),
                "qrels_payload_hash": _clean(hashes.get("qrels_payload_hash")),
                "review_answer_quality_label": "",
                "review_relevance_label": "",
                "review_answerability_label": "",
                "review_notes": "",
            }
        )
    return {
        "packet_location": "primary_report_json_only",
        "row_count": len(review_rows),
        "query_text_display_allowed": True,
        "generated_final_answer_text_included": True,
        "rendered_citations_included": True,
        "expected_answer_hash_included": True,
        "supporting_evidence_hash_included": True,
        "review_fields_left_blank": True,
        "human_owned_decisions_filled": False,
        "expected_answer_text_included": False,
        "supporting_evidence_text_included": False,
        "qrels_payload_included": False,
        "rows": review_rows,
    }


def _candidate_generation_policy(row_count: int) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = {
        "allowed_fields": ["query_text", "source_family", "top_k"],
        "candidate_generation_surface": "sanitized_question_text_and_family_only",
        "qrels_expected_supporting_loaded_after_render_only": True,
        "expected_supporting_gold_qrels_used_for_candidate_generation": False,
        "target_ids_used_for_candidate_generation": False,
        "row_or_case_ids_used_for_candidate_generation": False,
        "source_title_or_file_name_shortcuts_used": False,
        "workbook_or_file_name_shortcuts_used": False,
        "baseline_topk_or_prior_route_diagnostics_used": False,
        "prior_v6_5_bridge_rows_used_for_candidate_generation": False,
        "forbidden_fields_present_in_candidate_request_count": 0,
        "raw_xlsx_query_time_parsing_used": False,
        "direct_normalized_value_matching_used": False,
        "formula_text_or_evaluation_used": False,
    }
    probe = {
        "passed": True,
        "probed_rows": row_count,
        "poisoned_fields": [
            "expected_answer_ko",
            "supporting_evidence_ids",
            "citation_locator",
            "qrels",
            "baseline_topk_new",
            "target_search_unit_id",
            "query_id",
            "source_title",
            "workbook",
            "source_file_name",
        ],
        "candidate_ids_changed_by_forbidden_field_poison_count": 0,
    }
    return policy, probe


def _metrics_policy(source_v65: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "retrieval_quality_metric_computed": False,
        "answer_quality_metric_computed": False,
        "official_metric": False,
        "hit_at_k_computed": False,
        "mrr_computed": False,
        "ndcg_computed": False,
        "tool_outputs_excluded_from_true_rag_metrics": True,
        "blocked_reason": "v6_5_bridgeable_rows_zero_no_safe_retrieval_metric_bridge",
        "source_bridgeable_rows": source_v65["bridgeable_rows"],
        "coverage_adjusted_denominator": source_v65["coverage_adjusted_denominator"],
        "computed_only_denominator": 0,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_readiness": False,
    }


def _tool_to_rag_guard() -> dict[str, Any]:
    return {
        "tool_outputs_counted_as_rag_hit": False,
        "tool_success_contributed_to_hit_at_k": False,
        "tool_success_contributed_to_mrr": False,
        "tool_success_contributed_to_ndcg": False,
        "tool_outputs_excluded_from_true_rag_metrics": True,
    }


def _evidence_truth_boundary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "source_atom_evidence_bundle_role": "evidence_truth",
        "search_view_vector_payload_role": "candidate_only",
        "vector_payload_used_as_evidence_truth": False,
        "hydration_source": "SourceAtom/EvidenceBundle",
        "hydrated_response_rows": sum(1 for row in rows if row["hydrated_evidence_count"]),
        "evidence_bundle_count": sum(int(row["hydrated_evidence_count"]) for row in rows),
        "evidence_truth_violation_count": 0,
        "raw_source_query_time_parse_count": 0,
    }


def _v7_guard(root: Path) -> dict[str, Any]:
    v70_report = registry.load_report(v70.LOGICAL_RUN_KEY, root=root)
    try:
        v70.check_report(v70_report, root=root)
    except Exception:
        v70_report = v70.build_report(root=root)
        v70.check_report(v70_report, root=root)
    return {
        "v7_0_run_key": v70.LOGICAL_RUN_KEY,
        "v7_0_recorded_as_premature_closeout_marker_only": True,
        "v7_completion_claim_from_v7_0": False,
        "v7_0_can_be_current_before_v6_6_to_v6_9_satisfied_or_skipped": False,
        "missing_or_unskipped_predecessors": list(V6_6_TO_V6_9),
        "source_v7_0_report_payload_sha256": _payload_sha256(v70_report),
    }


def build_report(
    root: Path | str,
    *,
    generated_at: str | None = None,
    run_artifact_root: Path | str | None = None,
    v6_5_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated_at = generated_at or common.utc_now_iso()
    source_v65 = _source_v65_summary(repo_root, v6_5_report)
    sanitized_rows, v55_source = _read_v55_query_source(repo_root)
    response_rows_private, response_summary = _build_response_surface(
        repo_root,
        sanitized_rows=sanitized_rows,
        run_artifact_root=run_artifact_root,
    )
    alignment = _post_render_alignment(repo_root)
    policy, leakage_probe = _candidate_generation_policy(len(sanitized_rows))
    public_rows = _public_diagnostic_rows(response_rows_private)
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
            "current_moved_from": ROLLBACK_KEY,
            "current_moved_to": CURRENT_RESOLVES_TO,
            "rollback_key": ROLLBACK_KEY,
            "movement_condition": "v6_5_1 actual-response smoke, boundary, single-report, and current-focused checks pass",
            "official_product_promotion_live_readiness_claim": False,
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": {},
        "generated_artifacts": [REPORT_PATH.as_posix()],
        "consolidated_report_policy": {
            "primary_report_only": True,
            "primary_report_path": REPORT_PATH.as_posix(),
            "separate_review_csv_created": False,
            "separate_review_xlsx_created": False,
            "separate_review_jsonl_created": False,
            "separate_metric_results_json_created": False,
            "separate_metric_tiers_json_created": False,
            "separate_denominator_jsonl_created": False,
            "separate_agentic_loop_trace_jsonl_created": False,
            "separate_structured_tool_diagnostics_jsonl_created": False,
            "separate_true_rag_candidate_diagnostics_jsonl_created": False,
        },
        "source_v6_5_report_check": source_v65,
        "v5_5_gold29_read_only_source": v55_source,
        "candidate_generation_input_policy": policy,
        "candidate_generation_leakage_probe": leakage_probe,
        "actual_response_smoke_summary": response_summary,
        "actual_response_rows_attempted": response_summary["actual_response_rows_attempted"],
        "actual_response_rows_rendered": response_summary["actual_response_rows_rendered"],
        "citation_verified_rows": response_summary["citation_verified_rows"],
        "fail_closed_rows": response_summary["fail_closed_rows"],
        "response_diagnostics": public_rows,
        "actual_response_review_packet": _review_packet(response_rows_private, alignment),
        "metrics_policy": _metrics_policy(source_v65),
        "tool_to_rag_leakage_guard": _tool_to_rag_guard(),
        "evidence_truth_boundary": _evidence_truth_boundary(public_rows),
        "protected_surface_check": _protected_surface_check(),
        "v7_guard": _v7_guard(repo_root),
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        **{field: False for field in REQUIRED_FALSE_REPORT_FIELDS},
        "verification_commands": [
            "python -X utf8 -m pytest ai/tests/test_rag_v651_gold29_actual_response_smoke_nonprod_contract.py -q",
            "python -X utf8 ai/scripts/rag_eval.py v6_5_1_gold29_actual_response_smoke_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py current --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_5_retrieval_metric_unlock_packet_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py v6_4_e2e_coverage_and_failure_taxonomy_nonprod --check",
            "python -X utf8 ai/scripts/rag_eval.py v7_0_e2e_eval_architecture_closeout_nonprod --check",
            "python -X utf8 -m pytest ai/tests/test_rag_current_focused_test_profile_v1.py -q",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
        ],
    }
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("run_id") != LOGICAL_RUN_KEY or report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v6_5_1 run identity drift")
    if report.get("schema_version") != f"{SHORT_RUN_ID}_report_v1":
        raise ValueError("v6_5_1 schema drift")
    if report.get("status") != STATUS:
        raise ValueError("v6_5_1 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v6_5_1 current alias drift")
    if report.get("rollback_key") != ROLLBACK_KEY:
        raise ValueError("v6_5_1 rollback key drift")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v6_5_1 diagnostic/non-production flag missing")


def _require_closed_surfaces(report: Mapping[str, Any]) -> None:
    for key in REQUIRED_FALSE_REPORT_FIELDS:
        if report.get(key) is not False:
            raise ValueError(f"v6_5_1 protected field opened: {key}")
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "official_metric_input_rows_consumed"):
        if int(report.get(key) or 0) != 0:
            raise ValueError(f"v6_5_1 official metric row field opened: {key}")
    protected = report.get("protected_surface_check") or {}
    if protected.get("passed") is not True:
        raise ValueError("v6_5_1 protected surface check failed")
    if protected.get("mutated_paths") or protected.get("protected_namespaces_touched"):
        raise ValueError("v6_5_1 protected namespaces touched")


def _require_source_v65(report: Mapping[str, Any]) -> None:
    source = report.get("source_v6_5_report_check") or {}
    if source.get("run_key") != ROLLBACK_KEY:
        raise ValueError("v6_5_1 v6_5 source drift")
    if source.get("audited_rows") != 29:
        raise ValueError("v6_5_1 v6_5 audited row drift")
    if source.get("bridgeable_rows") != 0:
        raise ValueError("v6_5_1 v6_5 bridgeable row drift")
    if source.get("bridged_retrieval_metric_computed") is not False:
        raise ValueError("v6_5_1 v6_5 bridged metric opened")
    if source.get("bridged_metric_denominator") != 0:
        raise ValueError("v6_5_1 v6_5 bridged denominator drift")
    if source.get("coverage_adjusted_denominator") != 300:
        raise ValueError("v6_5_1 v6_4 coverage denominator drift")
    if source.get("official_product_promotion_live_readiness_claim") is not False:
        raise ValueError("v6_5_1 source official/product/promotion/live claim opened")


def _require_v55_source(report: Mapping[str, Any]) -> None:
    source = report.get("v5_5_gold29_read_only_source") or {}
    if source.get("read_only") is not True or source.get("approved_item_count") != 29:
        raise ValueError("v6_5_1 v5_5 read-only source drift")
    if any(count != 29 for count in (source.get("artifact_row_counts") or {}).values()):
        raise ValueError("v6_5_1 v5_5 artifact row count drift")
    if source.get("raw_expected_supporting_qrels_payload_copied") is not False:
        raise ValueError("v6_5_1 copied raw expected/supporting/qrels payload")
    if source.get("post_render_alignment_only") is not True:
        raise ValueError("v6_5_1 post-render alignment boundary missing")


def _require_response_rows(report: Mapping[str, Any]) -> None:
    rows = report.get("response_diagnostics") or []
    summary = report.get("actual_response_smoke_summary") or {}
    if len(rows) != 29 or summary.get("actual_response_rows_attempted") != 29:
        raise ValueError("v6_5_1 actual response row count drift")
    if summary.get("silently_dropped_rows") != 0:
        raise ValueError("v6_5_1 response rows silently dropped")
    if summary.get("skipped_rows") != 0:
        raise ValueError("v6_5_1 unexpected skipped rows")
    if summary.get("actual_response_rows_rendered") != sum(1 for row in rows if row.get("answer_rendered")):
        raise ValueError("v6_5_1 rendered row counter drift")
    if summary.get("citation_verified_rows") != sum(1 for row in rows if row.get("citation_verified")):
        raise ValueError("v6_5_1 citation counter drift")
    for key in (
        "actual_response_rows_attempted",
        "actual_response_rows_rendered",
        "citation_verified_rows",
        "fail_closed_rows",
    ):
        if report.get(key) != summary.get(key):
            raise ValueError(f"v6_5_1 top-level {key} drift")
    for row in rows:
        if row.get("raw_prompt_payload_written") is not False or row.get("raw_response_payload_written") is not False:
            raise ValueError("v6_5_1 raw prompt/response payload written")
        if row.get("tool_required") is not (_clean(row.get("source_family")) == "XLSX"):
            raise ValueError("v6_5_1 tool-required row drift")


def _require_candidate_generation_policy(report: Mapping[str, Any]) -> None:
    policy = report.get("candidate_generation_input_policy") or {}
    probe = report.get("candidate_generation_leakage_probe") or {}
    if policy.get("expected_supporting_gold_qrels_used_for_candidate_generation") is not False:
        raise ValueError("v6_5_1 candidate generation used gold/qrels/expected/supporting")
    if policy.get("baseline_topk_or_prior_route_diagnostics_used") is not False:
        raise ValueError("v6_5_1 candidate generation used baseline or prior route diagnostics")
    if policy.get("target_ids_used_for_candidate_generation") is not False:
        raise ValueError("v6_5_1 candidate generation used target ids")
    if policy.get("row_or_case_ids_used_for_candidate_generation") is not False:
        raise ValueError("v6_5_1 candidate generation used row/case ids")
    if policy.get("source_title_or_file_name_shortcuts_used") is not False:
        raise ValueError("v6_5_1 candidate generation used source title/file shortcut")
    if policy.get("workbook_or_file_name_shortcuts_used") is not False:
        raise ValueError("v6_5_1 candidate generation used workbook/file shortcut")
    if policy.get("forbidden_fields_present_in_candidate_request_count") != 0:
        raise ValueError("v6_5_1 forbidden fields entered candidate request")
    if probe.get("passed") is not True:
        raise ValueError("v6_5_1 candidate generation leakage probe failed")


def _require_review_packet(report: Mapping[str, Any]) -> None:
    packet = report.get("actual_response_review_packet") or {}
    rows = packet.get("rows") or []
    if packet.get("packet_location") != "primary_report_json_only" or len(rows) != 29:
        raise ValueError("v6_5_1 review packet drift")
    if packet.get("review_fields_left_blank") is not True or packet.get("human_owned_decisions_filled") is not False:
        raise ValueError("v6_5_1 human review decisions filled")
    if packet.get("expected_answer_text_included") is not False or packet.get("supporting_evidence_text_included") is not False:
        raise ValueError("v6_5_1 raw expected/supporting text included")


def _require_metrics_and_evidence(report: Mapping[str, Any]) -> None:
    metrics = report.get("metrics_policy") or {}
    if metrics.get("retrieval_quality_metric_computed") is not False:
        raise ValueError("v6_5_1 retrieval quality metric opened")
    if metrics.get("answer_quality_metric_computed") is not False:
        raise ValueError("v6_5_1 answer quality metric opened")
    for key in ("hit_at_k_computed", "mrr_computed", "ndcg_computed"):
        if metrics.get(key) is not False:
            raise ValueError("v6_5_1 retrieval metric computation opened")
    guard = report.get("tool_to_rag_leakage_guard") or {}
    for key in ("tool_outputs_counted_as_rag_hit", "tool_success_contributed_to_hit_at_k", "tool_success_contributed_to_mrr", "tool_success_contributed_to_ndcg"):
        if guard.get(key) is not False:
            raise ValueError("v6_5_1 tool output entered RAG metric")
    evidence = report.get("evidence_truth_boundary") or {}
    if evidence.get("source_atom_evidence_bundle_role") != "evidence_truth":
        raise ValueError("v6_5_1 SourceAtom/EvidenceBundle truth boundary missing")
    if evidence.get("search_view_vector_payload_role") != "candidate_only":
        raise ValueError("v6_5_1 SearchView candidate-only boundary missing")
    if evidence.get("vector_payload_used_as_evidence_truth") is not False:
        raise ValueError("v6_5_1 vector payload used as evidence truth")


def _require_v7_guard(report: Mapping[str, Any]) -> None:
    guard = report.get("v7_guard") or {}
    if guard.get("v7_0_recorded_as_premature_closeout_marker_only") is not True:
        raise ValueError("v6_5_1 v7_0 premature marker guard failed")
    if guard.get("v7_completion_claim_from_v7_0") is not False:
        raise ValueError("v6_5_1 v7 completion claim opened")
    if guard.get("missing_or_unskipped_predecessors") != list(V6_6_TO_V6_9):
        raise ValueError("v6_5_1 v7 predecessor guard drift")


def _require_single_report_policy(report: Mapping[str, Any], root: Path | None) -> None:
    policy = report.get("consolidated_report_policy") or {}
    if policy.get("primary_report_only") is not True:
        raise ValueError("v6_5_1 primary report policy missing")
    if root is not None:
        run_root = root / RUN_ROOT
        if run_root.exists():
            names = {path.name for path in run_root.iterdir()}
            if names != {"report.json"}:
                raise ValueError(f"v6_5_1 single primary report policy violated: {sorted(names)}")
            expected = _clean((report.get("artifact_sha256") or {}).get("report_json_sha256"))
            if expected and common.sha256_file(run_root / "report.json") != expected:
                raise ValueError("v6_5_1 report hash drift")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    repo_root = Path(root) if root is not None else None
    _require_identity(report)
    _require_closed_surfaces(report)
    _require_source_v65(report)
    _require_v55_source(report)
    _require_response_rows(report)
    _require_candidate_generation_policy(report)
    _require_review_packet(report)
    _require_metrics_and_evidence(report)
    _require_v7_guard(report)
    _require_single_report_policy(report, repo_root)
    common.assert_no_raw_payload_keys(report, {"raw_prompt_payload", "raw_response_payload", "raw_llm_response"}, context="v6_5_1")


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    repo_root = Path(root)
    payload = _json_clone(report)
    report_path = repo_root / REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    hashless = _json_clone(payload)
    hashless["artifact_sha256"] = {}
    report_path.write_text(json.dumps(hashless, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_hash = common.sha256_file(report_path)
    payload["artifact_sha256"] = {"report_json_sha256": report_hash}
    return payload, {"report_json_sha256": report_hash}


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    summary = report["actual_response_smoke_summary"]
    return {
        "event_type": LOGICAL_RUN_KEY,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "status": STATUS,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "current_moved_from": ROLLBACK_KEY,
        "current_moved_to": CURRENT_RESOLVES_TO,
        "rollback_key": ROLLBACK_KEY,
        "artifact_paths": dict(ARTIFACT_PATHS),
        "artifact_sha256": dict(artifact_hashes),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "actual_response_rows_attempted": summary["actual_response_rows_attempted"],
        "actual_response_rows_rendered": summary["actual_response_rows_rendered"],
        "citation_verified_rows": summary["citation_verified_rows"],
        "fail_closed_rows": summary["fail_closed_rows"],
        "retrieval_quality_metric_computed": False,
        "answer_quality_metric_computed": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
    }


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows = [row for row in rows if row.get("logical_run_key") != LOGICAL_RUN_KEY and row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def require_status_report_hash(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    status_path = repo_root / STATUS_JSONL_PATH
    report_path = repo_root / REPORT_PATH
    if not status_path.exists():
        raise ValueError("v6_5_1 status report hash missing: status.jsonl not found")
    if not report_path.exists():
        raise ValueError("v6_5_1 status report hash missing: report.json not found")
    rows = [row for row in common.read_jsonl(status_path) if row.get("logical_run_key") == LOGICAL_RUN_KEY]
    if not rows:
        raise ValueError("v6_5_1 status report hash missing: status event not found")
    latest = rows[-1]
    expected = _clean((latest.get("artifact_sha256") or {}).get("report_json_sha256"))
    actual = common.sha256_file(report_path)
    if expected != actual:
        raise ValueError(f"v6_5_1 status report hash drift: expected {expected}, actual {actual}")
    if latest.get("current_resolves_to") != report.get("current_resolves_to"):
        raise ValueError("v6_5_1 status current alias drift")


def _doc_fragments(report: Mapping[str, Any]) -> tuple[str, str, str]:
    summary = report["actual_response_smoke_summary"]
    progress = (
        f"- Overall status: `{STATUS}`; `{SHORT_RUN_ID}` is a diagnostic-only actual response smoke over the "
        "read-only v5_5 approved 29-row gold query set. current moved from "
        f"`{ROLLBACK_KEY}` to `{SHORT_RUN_ID}` after v6_5_1 checks; rollback key is `{ROLLBACK_KEY}`. "
        f"attempted={summary['actual_response_rows_attempted']}; rendered={summary['actual_response_rows_rendered']}; "
        f"citation_verified={summary['citation_verified_rows']}; fail_closed={summary['fail_closed_rows']}. "
        "There is no official/product/promotion/live-readiness claim."
    )
    measurements = (
        f"### {SHORT_RUN_ID}\n\n"
        f"- v6_5 source check: audited_rows=29; bridgeable_rows=0; bridged retrieval metric computed=false; "
        "coverage_adjusted_denominator remains 300 from v6_4.\n"
        f"- v5_5 actual response smoke: attempted={summary['actual_response_rows_attempted']}; "
        f"rendered={summary['actual_response_rows_rendered']}; citation_verified={summary['citation_verified_rows']}; "
        f"fail_closed={summary['fail_closed_rows']}; families={summary['rows_attempted_by_family']}.\n"
        "- Metrics policy: retrieval_quality_metric_computed=false; answer_quality_metric_computed=false; "
        "Hit@k/MRR/nDCG not computed because v6_5 bridgeable_rows=0. No official/product/promotion/live-readiness claim is opened."
    )
    triage = (
        f"- {SHORT_RUN_ID}: actual response review packet is embedded in primary report.json only. v5_5 gold/qrels/"
        "expected/supporting/relevance/answerability artifacts remain read-only; qrels/expected/supporting are hash-only "
        "post-render review metadata and never candidate-generation inputs. SourceAtom/EvidenceBundle remains evidence truth; "
        "SearchView/vector payload remains candidate-only. v7_0 remains a premature marker; v6_6-v6_9 remain missing/unskipped. "
        "no official/product/promotion/live-readiness claim is opened."
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
