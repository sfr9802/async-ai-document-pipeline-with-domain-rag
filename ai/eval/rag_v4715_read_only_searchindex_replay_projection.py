from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v4712_layered_retrieval_generalization_and_overfit_audit as v4712
from ai.eval import rag_v4713_live_retrieval_answerability_and_full_pdf_replay as v4713
from ai.eval import rag_v4714_diagnostic_precondition_hardening as v4714
from ai.eval import rag_v476_archive_purge as v476


LOGICAL_RUN_KEY = "v4_7_15"
SHORT_RUN_ID = "v4_7_15_read_only_searchindex_replay_projection"
CANONICAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_15_"
    "read_only_searchindex_replay_projection_nonprod"
)
STATUS = "V4_7_15_READ_ONLY_SEARCHINDEX_REPLAY_PROJECTION_NONPROD_READY"

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
ARCHIVE_MANIFEST_PATH = REPORT_ROOT / "archive_manifest.jsonl"
SOURCE_RUN_ID = v4714.SHORT_RUN_ID
SOURCE_REPORT_JSON = v4714.SHORT_REPORT_PATH
SOURCE_OVERLAY_JSON = v4713.SILVER_ANSWERABILITY_OVERLAY_JSON
SOURCE_TOPK_ROWS = v4712.V3_7_2_TOPK_ROWS

FAMILIES = ("TEXT", "PDF", "XLSX")
EXPECTED_REPLAY_FAMILY_COUNTS = {"TEXT": 350, "PDF": 325, "XLSX": 325}
EXPECTED_OVERLAY_FAMILY_COUNTS = {"TEXT": 30, "PDF": 30, "XLSX": 30}
KST_DOC_DATE = "2026-05-31"
FORBIDDEN_FALSE_KEYS = (
    "official_metric",
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
)


def utc_now_iso() -> str:
    return v476.utc_now_iso()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v476.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v476.write_json(path, payload)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    v476.write_jsonl(path, list(rows))


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _counter_dict(counter: Counter[str] | None = None) -> dict[str, int]:
    counter = counter or Counter()
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report = dict(source_report or registry.load_report("v4_7_14", root=root))
    v4714.check_report(report)
    return report


def _load_overlay(root: Path) -> dict[str, Any]:
    overlay_path = root / SOURCE_OVERLAY_JSON
    if not overlay_path.exists():
        raise FileNotFoundError(f"missing v4_7_13 silver answerability overlay: {SOURCE_OVERLAY_JSON}")
    overlay = read_json(overlay_path)
    if _as_int(overlay.get("row_count")) != 90:
        raise ValueError("v4_7_15 expected the 90-row v4_7_13 silver answerability overlay")
    return overlay


def _load_silver_topk_rows(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolution = v4712.resolve_v3_7_2_artifact(root, SOURCE_TOPK_ROWS)
    if not resolution.get("found"):
        return [], resolution
    rows = [
        dict(row)
        for row in read_jsonl(Path(resolution["path"]))
        if _clean(row.get("query_scope")) == "silver_1000_diagnostic_overlay"
    ]
    return rows, resolution


def _compact_resolution(resolution: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "logical_path": _clean(resolution.get("logical_path")),
        "sha256": _clean(resolution.get("sha256")),
        "expected_sha256": _clean(resolution.get("expected_sha256")),
        "sha256_verified": bool(resolution.get("sha256_verified")),
        "resolved_via_archive": bool(resolution.get("resolved_via_archive")),
        "physical_path_redacted": True,
    }


def _archive_manifest_summary(root: Path, token: str) -> dict[str, Any]:
    path = root / ARCHIVE_MANIFEST_PATH
    rows = [row for row in read_jsonl(path) if token in _clean(row.get("artifact_path"))] if path.exists() else []
    statuses = sorted({_clean(row.get("report_status")) for row in rows if _clean(row.get("report_status"))})
    materialization_rows = [
        _as_int(row.get("row_count"))
        for row in rows
        if "materialization_diagnostics" in _clean(row.get("artifact_path"))
    ]
    return {
        "manifest_token": token,
        "record_count": len(rows),
        "sha256_record_count": sum(1 for row in rows if _clean(row.get("sha256"))),
        "report_statuses": statuses,
        "materialization_diagnostics_row_count": max(materialization_rows) if materialization_rows else 0,
    }


def build_read_only_searchindexcontract_replay(
    *,
    root: Path,
    silver_topk_rows: Sequence[Mapping[str, Any]],
    topk_resolution: Mapping[str, Any],
) -> dict[str, Any]:
    v370 = _archive_manifest_summary(root, "v3_7_0")
    v371 = _archive_manifest_summary(root, "v3_7_1")
    families = Counter(_clean(row.get("source_family")).upper() for row in silver_topk_rows)
    bucket_counts = Counter(_clean(row.get("primary_retrieval_diagnostic_bucket")) for row in silver_topk_rows)
    target_miss_by_family = Counter()
    target_hit_by_family = Counter()
    envelope_count = 0
    hydration_count = 0
    evidence_count = 0
    citation_count = 0
    vector_truth_violations = 0
    canonical_source_registry_count = 0

    for row in silver_topk_rows:
        family = _clean(row.get("source_family")).upper()
        if row.get("target_hit_in_topk") is True or row.get("target_hit_at_k") is True:
            target_hit_by_family[family] += 1
        else:
            target_miss_by_family[family] += 1
        envelopes = list(row.get("top_result_envelopes") or [])
        envelope_count += len(envelopes)
        hydration_count += _as_int(row.get("topk_hydrateable_row_count"))
        evidence_count += _as_int(row.get("topk_evidence_bundle_renderable_row_count"))
        citation_count += _as_int(row.get("topk_citation_renderable_row_count"))
        for envelope in envelopes:
            if envelope.get("vector_payload_used_as_evidence_truth") is True:
                vector_truth_violations += 1
            if envelope.get("vector_metadata_used_as_canonical_citation_source") is True:
                vector_truth_violations += 1
            if envelope.get("canonical_payload_source") == "source_registry":
                canonical_source_registry_count += 1

    unblocked = (
        bool(topk_resolution.get("sha256_verified"))
        and bool(topk_resolution.get("resolved_via_archive"))
        and len(silver_topk_rows) == 1000
    )
    return {
        "schema_version": f"{SHORT_RUN_ID}_read_only_searchindexcontract_replay_v1",
        "status": "READ_ONLY_SEARCHINDEXCONTRACT_REPLAY_UNBLOCKED_ARCHIVED_TOPK_DIAGNOSTIC_ONLY"
        if unblocked
        else "READ_ONLY_SEARCHINDEXCONTRACT_REPLAY_BLOCKED_ARCHIVED_TOPK_UNAVAILABLE_FAIL_CLOSED",
        "source_topk_logical_path": _clean(topk_resolution.get("logical_path")),
        "source_topk_sha256": _clean(topk_resolution.get("sha256")),
        "source_topk_expected_sha256": _clean(topk_resolution.get("expected_sha256")),
        "source_topk_sha256_verified": bool(topk_resolution.get("sha256_verified")),
        "source_topk_resolved_via_archive": bool(topk_resolution.get("resolved_via_archive")),
        "source_topk_physical_path_redacted": True,
        "source_topk_resolution": _compact_resolution(topk_resolution),
        "v3_7_0_source_registry_manifest_record_count": v370["record_count"],
        "v3_7_0_source_registry_manifest_sha256_record_count": v370["sha256_record_count"],
        "v3_7_0_source_registry_manifest_statuses": v370["report_statuses"],
        "v3_7_0_materialization_diagnostics_row_count": v370["materialization_diagnostics_row_count"],
        "v3_7_1_index_manifest_record_count": v371["record_count"],
        "v3_7_1_index_manifest_sha256_record_count": v371["sha256_record_count"],
        "v3_7_1_index_manifest_statuses": v371["report_statuses"],
        "replay_input_row_count": len(silver_topk_rows),
        "replay_counts_by_family": _counter_dict(families),
        "topk_envelope_count": envelope_count,
        "sourceatom_hydration_success_envelope_count": hydration_count,
        "evidencebundle_renderable_envelope_count": evidence_count,
        "citation_renderable_envelope_count": citation_count,
        "canonical_payload_source_registry_envelope_count": canonical_source_registry_count,
        "vector_payload_evidence_truth_violation_count": vector_truth_violations,
        "target_hit_in_topk_count": sum(target_hit_by_family.values()),
        "target_hit_in_topk_count_by_family": _counter_dict(target_hit_by_family),
        "target_not_in_topk_diagnostic_count": sum(target_miss_by_family.values()),
        "target_not_in_topk_diagnostic_count_by_family": _counter_dict(target_miss_by_family),
        "primary_retrieval_diagnostic_bucket_counts": dict(sorted(bucket_counts.items())),
        "read_only": True,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "live_runtime_adapter_invoked": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "source_registry_mutated": False,
        "silver_mutated": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "production_db_mutated": False,
        "live_db_index_cache_readiness": False,
        "retrieval_quality_policy": (
            "archived_read_only_replay_is_diagnostic_projection_not_live_retrieval_quality_metric"
        ),
    }


def _bool(row: Mapping[str, Any], key: str) -> bool:
    return row.get(key) is True


def _primary_bucket(row: Mapping[str, Any]) -> str:
    if _bool(row, "target_not_in_topk") or _bool(row, "retrieval_target_miss"):
        return "retrieval_target_not_in_topk"
    if (
        _bool(row, "evidence_window_insufficient")
        or _bool(row, "source_family_route_ok_but_evidence_mismatch")
        or _bool(row, "repeated_prefix_cluster_member")
    ):
        return "target_hit_evidence_context_repair"
    if _bool(row, "query_too_broad"):
        return "query_specificity_fixture_review"
    return "no_repair_projection"


def _projection_counter(rows: Sequence[Mapping[str, Any]], bucket: str) -> dict[str, Any]:
    selected = [row for row in rows if _primary_bucket(row) == bucket]
    return {
        "row_count": len(selected),
        "counts_by_family": _counter_dict(Counter(_clean(row.get("source_family")).upper() for row in selected)),
    }


def _overlap_matrix(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for family in FAMILIES:
        scoped = [row for row in rows if _clean(row.get("source_family")).upper() == family]
        target = [row for row in scoped if _bool(row, "target_not_in_topk") or _bool(row, "retrieval_target_miss")]
        target_hit = [row for row in scoped if row not in target]
        evidence = [row for row in scoped if _bool(row, "evidence_window_insufficient")]
        route = [row for row in scoped if _bool(row, "source_family_route_ok_but_evidence_mismatch")]
        prefix = [row for row in scoped if _bool(row, "repeated_prefix_cluster_member")]
        broad = [row for row in scoped if _bool(row, "query_too_broad")]
        matrix[family] = {
            "row_count": len(scoped),
            "target_not_in_topk_total": len(target),
            "evidence_window_insufficient_total": len(evidence),
            "source_family_route_ok_but_evidence_mismatch_total": len(route),
            "repeated_prefix_cluster_total": len(prefix),
            "query_too_broad_total": len(broad),
            "target_not_in_topk_and_evidence_window_insufficient": sum(
                1 for row in scoped if row in target and row in evidence
            ),
            "target_not_in_topk_and_source_family_route_ok_but_evidence_mismatch": sum(
                1 for row in scoped if row in target and row in route
            ),
            "repeated_prefix_cluster_overlap_with_target_miss": sum(
                1 for row in scoped if row in prefix and row in target
            ),
            "repeated_prefix_cluster_target_hit": sum(1 for row in scoped if row in prefix and row in target_hit),
            "evidence_window_insufficient_target_hit": sum(1 for row in scoped if row in evidence and row in target_hit),
            "source_family_route_ok_but_evidence_mismatch_target_hit": sum(
                1 for row in scoped if row in route and row in target_hit
            ),
            "query_too_broad_overlap_with_target_miss": sum(1 for row in scoped if row in broad and row in target),
            "query_too_broad_overlap_with_evidence_window": sum(
                1 for row in scoped if row in broad and row in evidence
            ),
            "query_too_broad_primary_review": sum(
                1 for row in scoped if row in broad and _primary_bucket(row) == "query_specificity_fixture_review"
            ),
        }
    return matrix


def build_diagnostic_retrieval_evidence_repair_projection(
    *,
    overlay: Mapping[str, Any],
    silver_topk_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    overlay_rows = [dict(row) for row in overlay.get("rows") or []]
    topk_query_ids = {_clean(row.get("query_id")) for row in silver_topk_rows if _clean(row.get("query_id"))}
    overlay_query_ids = [_clean(row.get("query_id")) for row in overlay_rows]
    missing_ids = [query_id for query_id in overlay_query_ids if query_id not in topk_query_ids]
    source_audit_counts = Counter(_clean(row.get("source_family")).upper() for row in silver_topk_rows)
    overlay_counts = Counter(_clean(row.get("source_family")).upper() for row in overlay_rows)
    primary_counts = {
        "retrieval_target_not_in_topk": _projection_counter(overlay_rows, "retrieval_target_not_in_topk"),
        "target_hit_evidence_context_repair": _projection_counter(overlay_rows, "target_hit_evidence_context_repair"),
        "query_specificity_fixture_review": _projection_counter(overlay_rows, "query_specificity_fixture_review"),
        "no_repair_projection": _projection_counter(overlay_rows, "no_repair_projection"),
    }
    target_miss_by_family = Counter(
        _clean(row.get("source_family")).upper()
        for row in overlay_rows
        if _bool(row, "target_not_in_topk") or _bool(row, "retrieval_target_miss")
    )
    return {
        "schema_version": f"{SHORT_RUN_ID}_retrieval_evidence_repair_projection_v1",
        "status": "SILVER_RETRIEVAL_EVIDENCE_REPAIR_PROJECTION_READY_DIAGNOSTIC_ONLY",
        "source_overlay_run_id": v4713.SHORT_RUN_ID,
        "source_overlay_path": SOURCE_OVERLAY_JSON.as_posix(),
        "source_overlay_status": overlay.get("status"),
        "projection_input_row_count": len(overlay_rows),
        "projection_counts_by_family": _counter_dict(overlay_counts),
        "projection_source_audit_row_count": len(silver_topk_rows),
        "projection_source_audit_counts_by_family": _counter_dict(source_audit_counts),
        "overlay_rows_missing_from_audit_count": len(missing_ids),
        "overlay_missing_query_id_count": len(set(missing_ids)),
        "overlay_query_id_join_policy": "exact_query_id_join_against_v3_7_2_silver_1000_topk_rows",
        "primary_projection_policy": "target_first_disjoint_diagnostic_only",
        "primary_projection_counts": primary_counts,
        "target_not_in_topk_count_by_family": _counter_dict(target_miss_by_family),
        "root_cause_overlap_matrix_by_family": _overlap_matrix(overlay_rows),
        "diagnostic_silver_only": True,
        "silver_mutation": False,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "silver_promoted_to_gold_count": 0,
        "official_metric_input_rows": 0,
        "mutation_policy": [
            "diagnostic_projection_only",
            "do_not_modify_silver_gold_qrels_labels_expected_or_supporting_evidence",
            "do_not_modify_denominator_rows",
        ],
    }


def _build_counters(
    *,
    source_report: Mapping[str, Any],
    replay: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    source_counters = source_report.get("counters") or {}
    primary = projection.get("primary_projection_counts") or {}
    target_projection = primary.get("retrieval_target_not_in_topk") or {}
    context_projection = primary.get("target_hit_evidence_context_repair") or {}
    query_projection = primary.get("query_specificity_fixture_review") or {}
    no_projection = primary.get("no_repair_projection") or {}
    return {
        "diagnostic_only": True,
        "non_production": True,
        "current_resolves_to": LOGICAL_RUN_KEY,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
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
        "live_retrieval_precondition_unavailable_count": _as_int(
            source_counters.get("live_retrieval_precondition_unavailable_count")
        ),
        "live_retrieval_quality_failure_count": 0,
        "llm_unavailable_skip_count": _as_int(source_counters.get("llm_unavailable_skip_count")),
        "generated_response_count": 0,
        "claim_support_fail_count": 0,
        "parser_failure_count": 0,
        "citation_failure_count": 0,
        "unsupported_answer_count": 0,
        "noop_or_extractive_fallback_answer_count": 0,
        "read_only_replay_row_count": _as_int(replay.get("replay_input_row_count")),
        "read_only_replay_topk_envelope_count": _as_int(replay.get("topk_envelope_count")),
        "read_only_replay_sourceatom_hydration_success_envelope_count": _as_int(
            replay.get("sourceatom_hydration_success_envelope_count")
        ),
        "read_only_replay_evidencebundle_renderable_envelope_count": _as_int(
            replay.get("evidencebundle_renderable_envelope_count")
        ),
        "read_only_replay_citation_renderable_envelope_count": _as_int(
            replay.get("citation_renderable_envelope_count")
        ),
        "read_only_replay_vector_payload_evidence_truth_violation_count": _as_int(
            replay.get("vector_payload_evidence_truth_violation_count")
        ),
        "diagnostic_target_not_in_topk_replay_count": _as_int(replay.get("target_not_in_topk_diagnostic_count")),
        "projection_input_row_count": _as_int(projection.get("projection_input_row_count")),
        "retrieval_target_not_in_topk_projection_count": _as_int(target_projection.get("row_count")),
        "target_hit_evidence_context_repair_projection_count": _as_int(context_projection.get("row_count")),
        "query_specificity_fixture_review_projection_count": _as_int(query_projection.get("row_count")),
        "no_repair_projection_count": _as_int(no_projection.get("row_count")),
        "overlay_rows_missing_from_audit_count": _as_int(projection.get("overlay_rows_missing_from_audit_count")),
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    v4714_report = _load_source_report(root, source_report=source_report)
    overlay = _load_overlay(root)
    silver_topk_rows, topk_resolution = _load_silver_topk_rows(root)
    replay = build_read_only_searchindexcontract_replay(
        root=root,
        silver_topk_rows=silver_topk_rows,
        topk_resolution=topk_resolution,
    )
    projection = build_diagnostic_retrieval_evidence_repair_projection(
        overlay=overlay,
        silver_topk_rows=silver_topk_rows,
    )
    counters = _build_counters(source_report=v4714_report, replay=replay, projection=projection)
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
            "source_silver_answerability_overlay_json": SOURCE_OVERLAY_JSON.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        "source_overlay_json": SOURCE_OVERLAY_JSON.as_posix(),
        "source_topk_rows_jsonl": SOURCE_TOPK_ROWS.as_posix(),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
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
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "answer_generation_attempted": False,
        "full_pdf_generation_rows": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "read_only_searchindexcontract_replay": replay,
        "diagnostic_retrieval_evidence_repair_projection": projection,
        "source_precondition_summary": {
            "v4_7_13_live_retrieval_precondition_status": (
                (v4714_report.get("live_retrieval_preflight") or {}).get("status")
            ),
            "v4_7_13_local_llm_precondition_status": (v4714_report.get("local_llm_preflight") or {}).get("status"),
            "live_retrieval_quality_failure_count": _as_int(
                (v4714_report.get("counters") or {}).get("live_retrieval_quality_failure_count")
            ),
            "llm_unavailable_skip_count": _as_int(
                (v4714_report.get("counters") or {}).get("llm_unavailable_skip_count")
            ),
            "claim_support_fail_count": _as_int((v4714_report.get("counters") or {}).get("claim_support_fail_count")),
            "parser_failure_count": _as_int((v4714_report.get("counters") or {}).get("parser_failure_count")),
        },
        "counters": counters,
        "completion_branch": "artifact_ready_read_only_replay_projection_diagnostic_ready",
        "residual_risks": [
            "archived replay validates the v3_7_2 read-only top-k contract but does not prove live DB/index/cache readiness",
            "repair projections are diagnostic queues and do not mutate silver, gold, qrels, labels, or denominators",
        ],
    }
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    report = json.loads(json.dumps(report, ensure_ascii=False))
    write_json(root / SHORT_REPORT_PATH, report)
    hashes = {"report_json_sha256": sha256_file(root / SHORT_REPORT_PATH)}
    return report, hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    counters = report["counters"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v4_7_15_read_only_searchindex_replay_projection_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
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
        "read_only_replay_row_count": counters["read_only_replay_row_count"],
        "read_only_replay_topk_envelope_count": counters["read_only_replay_topk_envelope_count"],
        "projection_input_row_count": counters["projection_input_row_count"],
        "retrieval_target_not_in_topk_projection_count": counters[
            "retrieval_target_not_in_topk_projection_count"
        ],
        "target_hit_evidence_context_repair_projection_count": counters[
            "target_hit_evidence_context_repair_projection_count"
        ],
        "query_specificity_fixture_review_projection_count": counters[
            "query_specificity_fixture_review_projection_count"
        ],
        "no_repair_projection_count": counters["no_repair_projection_count"],
        "live_retrieval_quality_failure_count": counters["live_retrieval_quality_failure_count"],
        "llm_unavailable_skip_count": counters["llm_unavailable_skip_count"],
        "generated_response_count": counters["generated_response_count"],
        "claim_support_fail_count": counters["claim_support_fail_count"],
        "parser_failure_count": counters["parser_failure_count"],
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
        and row.get("event_type") != "diagnostic_v4_7_15_read_only_searchindex_replay_projection_nonprod"
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


def _sync_last_updated(text: str) -> str:
    return re.sub(r"Last updated: .*? KST\.", f"Last updated: {KST_DOC_DATE} KST.", text, count=1)


def _replace_summary_block(text: str, *, block: str) -> str:
    start = "<!-- v4_7_15_summary_start -->"
    end = "<!-- v4_7_15_summary_end -->"
    wrapped = f"{start}\n{block.rstrip()}\n{end}"
    prior_current_summary = re.compile(r"<!-- v4_7[^>]*_summary_start -->.*?<!-- v4_7[^>]*_summary_end -->", re.S)
    if prior_current_summary.search(text):
        return prior_current_summary.sub(wrapped, text, count=1)
    return _upsert_block(text, start_marker=start, end_marker=end, block=block)


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    counters = report["counters"]
    replay = report["read_only_searchindexcontract_replay"]
    projection = report["diagnostic_retrieval_evidence_repair_projection"]
    primary = projection["primary_projection_counts"]
    progress = root / "docs/rag-ingestion-progress.md"
    measurements = root / "docs/rag-ingestion-measurements.md"
    triage = root / "docs/rag-ingestion-triage.md"
    readme = root / "README.md"
    eval_readme = root / "ai/eval/README.md"
    scripts_readme = root / "ai/scripts/README.md"

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is artifact-ready / read-only replay diagnostic-ready. "
        f"Artifact: `{SHORT_REPORT_PATH.as_posix()}`. Archived read-only SearchIndexContract top-k replay is "
        f"{replay['status']} with {counters['read_only_replay_row_count']} silver rows and "
        f"{counters['read_only_replay_topk_envelope_count']} top-k envelopes; live runtime adapter invoked=false "
        "and live_db_index_cache_readiness=false. The 90-row v4_7_13 silver overlay is projected into "
        f"diagnostic queues: retrieval target not in top-k "
        f"{primary['retrieval_target_not_in_topk']['row_count']}, target-hit evidence/context repair "
        f"{primary['target_hit_evidence_context_repair']['row_count']}, query-specificity fixture review "
        f"{primary['query_specificity_fixture_review']['row_count']}, no repair projection "
        f"{primary['no_repair_projection']['row_count']}. official_metric_input_rows=0, "
        "silver_promoted_to_gold_count=0, promotion_evidence=false, product_success_evidence_allowed=false; "
        "silver, gold, qrels, labels, expected/supporting evidence, denominator rows, source registry, indexes, "
        "cache, and production DB are not mutated."
    )
    progress.write_text(
        _sync_last_updated(
            _upsert_block(
                progress.read_text(encoding="utf-8"),
                start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
                end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
                block=progress_block,
                after_anchor="# RAG Ingestion Progress",
            )
        ),
        encoding="utf-8",
    )

    measurements_block = f"""## v4_7_15 read-only SearchIndexContract replay projection

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`

| counter | value |
| --- | --- |
| status | {STATUS} |
| read_only_searchindexcontract_replay_status | {replay['status']} |
| source_topk_sha256_verified | {str(replay['source_topk_sha256_verified']).lower()} |
| source_topk_resolved_via_archive | {str(replay['source_topk_resolved_via_archive']).lower()} |
| v3_7_0_source_registry_manifest_record_count | {replay['v3_7_0_source_registry_manifest_record_count']} |
| v3_7_1_index_manifest_record_count | {replay['v3_7_1_index_manifest_record_count']} |
| replay_input_row_count | {replay['replay_input_row_count']} |
| replay_counts_by_family | {json.dumps(replay['replay_counts_by_family'], sort_keys=True)} |
| topk_envelope_count | {replay['topk_envelope_count']} |
| sourceatom_hydration_success_envelope_count | {replay['sourceatom_hydration_success_envelope_count']} |
| evidencebundle_renderable_envelope_count | {replay['evidencebundle_renderable_envelope_count']} |
| citation_renderable_envelope_count | {replay['citation_renderable_envelope_count']} |
| vector_payload_evidence_truth_violation_count | {replay['vector_payload_evidence_truth_violation_count']} |
| projection_input_row_count | {projection['projection_input_row_count']} |
| retrieval_target_not_in_topk_projection_count | {primary['retrieval_target_not_in_topk']['row_count']} |
| target_hit_evidence_context_repair_projection_count | {primary['target_hit_evidence_context_repair']['row_count']} |
| query_specificity_fixture_review_projection_count | {primary['query_specificity_fixture_review']['row_count']} |
| no_repair_projection_count | {primary['no_repair_projection']['row_count']} |
| overlay_rows_missing_from_audit_count | {projection['overlay_rows_missing_from_audit_count']} |
| live_retrieval_quality_failure_count | {counters['live_retrieval_quality_failure_count']} |
| claim_support_fail_count | {counters['claim_support_fail_count']} |
| parser_failure_count | {counters['parser_failure_count']} |
| official_metric_input_rows | 0 |
"""
    measurements.write_text(
        _sync_last_updated(
            _upsert_block(
                measurements.read_text(encoding="utf-8"),
                start_marker="<!-- v4_7_15_measurements_start -->",
                end_marker="<!-- v4_7_15_measurements_end -->",
                block=measurements_block,
                after_anchor="# RAG Ingestion Measurements",
            )
        ),
        encoding="utf-8",
    )

    overlap = projection["root_cause_overlap_matrix_by_family"]
    triage_block = (
        f"- {SHORT_RUN_ID} diagnostic-only repair projection: retrieval target not in top-k "
        f"{primary['retrieval_target_not_in_topk']['row_count']} "
        f"{primary['retrieval_target_not_in_topk']['counts_by_family']}; target-hit evidence/context repair "
        f"{primary['target_hit_evidence_context_repair']['row_count']} "
        f"{primary['target_hit_evidence_context_repair']['counts_by_family']}; query-specificity fixture review "
        f"{primary['query_specificity_fixture_review']['row_count']} "
        f"{primary['query_specificity_fixture_review']['counts_by_family']}; no repair projection "
        f"{primary['no_repair_projection']['row_count']}. Secondary overlap: TEXT evidence-window overlap with target miss "
        f"{overlap['TEXT']['target_not_in_topk_and_evidence_window_insufficient']}; XLSX repeated-prefix total "
        f"{overlap['XLSX']['repeated_prefix_cluster_total']} with "
        f"{overlap['XLSX']['repeated_prefix_cluster_overlap_with_target_miss']} target misses and "
        f"{overlap['XLSX']['repeated_prefix_cluster_target_hit']} target-hit rows; PDF evidence-window total "
        f"{overlap['PDF']['evidence_window_insufficient_total']} with "
        f"{overlap['PDF']['evidence_window_insufficient_target_hit']} target-hit rows, and query-too-broad primary review "
        f"{overlap['PDF']['query_too_broad_primary_review']}. Diagnostic-only projection; no silver/gold/qrels, label, "
        "expected/supporting evidence, denominator, source registry, cache, production DB, or index mutation."
    )
    triage.write_text(
        _sync_last_updated(
            _upsert_block(
                triage.read_text(encoding="utf-8"),
                start_marker="<!-- v4_7_15_triage_start -->",
                end_marker="<!-- v4_7_15_triage_end -->",
                block=triage_block,
                after_anchor="# RAG Ingestion Triage",
            )
        ),
        encoding="utf-8",
    )

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        "`current` resolves to `v4_7_15`: non-production read-only SearchIndexContract replay projection. "
        f"Archived silver top-k replay covers {replay['replay_input_row_count']} rows and "
        f"{replay['topk_envelope_count']} envelopes with vector evidence-truth violations "
        f"{replay['vector_payload_evidence_truth_violation_count']}; live retrieval quality failures remain "
        f"{counters['live_retrieval_quality_failure_count']} because unavailable live SearchIndexContract states are "
        "fail-closed preconditions, not quality failures. Local LLM unavailable states remain generation-not-attempted "
        f"with generated responses {counters['generated_response_count']}, parser failures "
        f"{counters['parser_failure_count']}, and claim-support failures {counters['claim_support_fail_count']}. "
        f"v4_7_14_diagnostic_precondition_hardening remains explicit for historical checks. Canonical details: "
        "`docs/rag-ingestion-progress.md`, `docs/rag-ingestion-measurements.md`, and "
        "`docs/rag-ingestion-triage.md`; prior v4_7 cleanup keys remain checkable through explicit aliases.\n"
        "Lineage breadcrumbs: v4_7 remains pre-official; it supersedes the abstract v4_7_1 Korean review packet; "
        "the hydrated packet has hydrated rows 204, PDF 100, XLSX 104 and non-empty `질의문` 204; "
        "v4_7_3 applies the user-reviewed Korean query candidate CSV and v4_7_3 applies the user-reviewed CSV "
        "decisions with 미검수=통과; PDF survivor 58 and v4_7_4 replays only the 58 user-passed PDF survivor "
        "candidates. official_metric_input_rows=0. "
        "## Korean human review packet. The previous v4_7_1 Korean review packet was abstract; "
        "review_packet_ko_hydrated.xlsx carries actual Korean query candidates. "
        "User-owned fields remain blank/default; not official metric. fine_tuning_executed=false.\n"
        "Hard boundary: diagnostic-only, non-production, not official metric, not gold/qrels/labels, "
        "not denominator/training/fine-tuning/FT-A, not promotion evidence, not product-success evidence, "
        "and not live readiness."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v4_7_15`, `v4_7_14_diagnostic_precondition_hardening` remains explicit, "
        "`v4_7_13_live_retrieval_answerability_and_full_pdf_replay` remains explicit, "
        "`v4_7_12_layered_retrieval_generalization_and_overfit_audit` records layered retrieval audit rows 1057, "
        "`v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness`, "
        "`v4_7_9_pdf_evidence_residual_answer_quality_replay`, and prior v4_7 cleanup keys remain checkable "
        "without opening official metrics. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        forbidden = {"prompt", "raw_prompt", "raw_response", "response", "raw_llm_response", "final_answer"}
        overlap = forbidden & set(value)
        if overlap:
            raise ValueError(f"v4_7_15 raw prompt/response leakage keys present: {sorted(overlap)}")
        for child in value.values():
            _assert_no_raw_payload_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_raw_payload_keys(child)


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v4_7_15 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v4_7_15 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v4_7_15 status mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v4_7_15 must remain diagnostic-only and non-production")
    for key in FORBIDDEN_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v4_7_15 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0 or report.get("silver_official_metric_input_rows") != 0:
        raise ValueError("v4_7_15 opened official metric rows")
    if report.get("silver_promoted_to_gold_count") != 0:
        raise ValueError("v4_7_15 promoted silver")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v4_7_15 touched protected namespaces")
    if report.get("SearchView_vector_payload_role") != "candidate_only":
        raise ValueError("v4_7_15 SearchView/vector payload role changed")
    if report.get("SourceAtom_EvidenceBundle_role") != "evidence_truth":
        raise ValueError("v4_7_15 SourceAtom/EvidenceBundle role changed")
    if report.get("answer_generation_attempted") is not False or report.get("full_pdf_generation_rows") != []:
        raise ValueError("v4_7_15 must not generate substitute answers")
    if report.get("raw_prompt_payload_written") is not False or report.get("raw_response_payload_written") is not False:
        raise ValueError("v4_7_15 raw prompt/response payload must not be written")
    _assert_no_raw_payload_keys(report)

    replay = report.get("read_only_searchindexcontract_replay") or {}
    if replay.get("status") != "READ_ONLY_SEARCHINDEXCONTRACT_REPLAY_UNBLOCKED_ARCHIVED_TOPK_DIAGNOSTIC_ONLY":
        raise ValueError("v4_7_15 read-only SearchIndexContract replay did not unblock")
    if replay.get("read_only") is not True:
        raise ValueError("v4_7_15 replay must remain read-only")
    if replay.get("diagnostic_only") is not True:
        raise ValueError("v4_7_15 replay must remain diagnostic-only")
    if replay.get("source_topk_sha256_verified") is not True or replay.get("source_topk_resolved_via_archive") is not True:
        raise ValueError("v4_7_15 archived top-k source was not sha-verified via archive")
    if replay.get("v3_7_0_source_registry_manifest_record_count") != 5:
        raise ValueError("v4_7_15 v3_7_0 source registry manifest record count drift")
    if replay.get("v3_7_1_index_manifest_record_count") != 5:
        raise ValueError("v4_7_15 v3_7_1 index manifest record count drift")
    if replay.get("replay_input_row_count") != 1000:
        raise ValueError("v4_7_15 replay input row count drift")
    if replay.get("replay_counts_by_family") != EXPECTED_REPLAY_FAMILY_COUNTS:
        raise ValueError("v4_7_15 replay family counts drift")
    for key in (
        "topk_envelope_count",
        "sourceatom_hydration_success_envelope_count",
        "evidencebundle_renderable_envelope_count",
        "citation_renderable_envelope_count",
    ):
        if _as_int(replay.get(key)) != 5000:
            raise ValueError(f"v4_7_15 replay envelope counter drift: {key}")
    if _as_int(replay.get("canonical_payload_source_registry_envelope_count")) != 5000:
        raise ValueError("v4_7_15 replay source registry canonical payload count drift")
    if _as_int(replay.get("vector_payload_evidence_truth_violation_count")) != 0:
        raise ValueError("v4_7_15 vector payload evidence-truth violation")
    for key in (
        "live_runtime_adapter_invoked",
        "index_rebuilt",
        "cache_mutated",
        "source_registry_mutated",
        "silver_mutated",
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
        "production_db_mutated",
        "live_db_index_cache_readiness",
    ):
        if replay.get(key) is not False:
            raise ValueError(f"v4_7_15 replay opened forbidden surface: {key}")

    projection = report.get("diagnostic_retrieval_evidence_repair_projection") or {}
    if projection.get("status") != "SILVER_RETRIEVAL_EVIDENCE_REPAIR_PROJECTION_READY_DIAGNOSTIC_ONLY":
        raise ValueError("v4_7_15 projection status mismatch")
    if projection.get("diagnostic_silver_only") is not True:
        raise ValueError("v4_7_15 projection must remain diagnostic silver only")
    if projection.get("projection_input_row_count") != 90:
        raise ValueError("v4_7_15 projection input row count drift")
    if projection.get("projection_counts_by_family") != EXPECTED_OVERLAY_FAMILY_COUNTS:
        raise ValueError("v4_7_15 projection family counts drift")
    if projection.get("projection_source_audit_row_count") != 1000:
        raise ValueError("v4_7_15 projection source audit row count drift")
    if projection.get("projection_source_audit_counts_by_family") != EXPECTED_REPLAY_FAMILY_COUNTS:
        raise ValueError("v4_7_15 projection source audit family counts drift")
    if _as_int(projection.get("overlay_rows_missing_from_audit_count")) != 0:
        raise ValueError("v4_7_15 overlay/audit join drift")
    primary = projection.get("primary_projection_counts") or {}
    expected_primary = {
        "retrieval_target_not_in_topk": (68, {"TEXT": 28, "PDF": 12, "XLSX": 28}),
        "target_hit_evidence_context_repair": (14, {"TEXT": 2, "PDF": 10, "XLSX": 2}),
        "query_specificity_fixture_review": (3, {"TEXT": 0, "PDF": 3, "XLSX": 0}),
        "no_repair_projection": (5, {"TEXT": 0, "PDF": 5, "XLSX": 0}),
    }
    for key, (row_count, family_counts) in expected_primary.items():
        actual = primary.get(key) or {}
        if actual.get("row_count") != row_count or actual.get("counts_by_family") != family_counts:
            raise ValueError(f"v4_7_15 projection primary count drift: {key}")
    for key in (
        "silver_mutation",
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
    ):
        if projection.get(key) is not False:
            raise ValueError(f"v4_7_15 projection opened forbidden surface: {key}")
    if projection.get("official_metric_input_rows") != 0 or projection.get("silver_promoted_to_gold_count") != 0:
        raise ValueError("v4_7_15 projection opened official or promotion surface")

    counters = report.get("counters") or {}
    required = (
        "current_resolves_to",
        "official_metric_input_rows",
        "read_only_replay_row_count",
        "read_only_replay_topk_envelope_count",
        "projection_input_row_count",
        "retrieval_target_not_in_topk_projection_count",
        "target_hit_evidence_context_repair_projection_count",
        "live_retrieval_quality_failure_count",
        "llm_unavailable_skip_count",
        "generated_response_count",
        "claim_support_fail_count",
        "parser_failure_count",
    )
    missing = [key for key in required if key not in counters]
    if missing:
        raise ValueError(f"v4_7_15 missing counters: {missing}")
    if counters["current_resolves_to"] != LOGICAL_RUN_KEY:
        raise ValueError("current must resolve to v4_7_15")
    if counters["official_metric_input_rows"] != 0:
        raise ValueError("v4_7_15 opened official metric rows")
    if counters["read_only_replay_row_count"] != 1000 or counters["read_only_replay_topk_envelope_count"] != 5000:
        raise ValueError("v4_7_15 replay counters drift")
    if counters["projection_input_row_count"] != 90:
        raise ValueError("v4_7_15 projection counter drift")
    if counters["retrieval_target_not_in_topk_projection_count"] != 68:
        raise ValueError("v4_7_15 retrieval target projection count drift")
    if counters["target_hit_evidence_context_repair_projection_count"] != 14:
        raise ValueError("v4_7_15 evidence/context projection count drift")
    for key in (
        "live_retrieval_quality_failure_count",
        "generated_response_count",
        "claim_support_fail_count",
        "parser_failure_count",
        "citation_failure_count",
        "unsupported_answer_count",
        "noop_or_extractive_fallback_answer_count",
        "read_only_replay_vector_payload_evidence_truth_violation_count",
        "overlay_rows_missing_from_audit_count",
    ):
        if _as_int(counters.get(key)) != 0:
            raise ValueError("v4_7_15 fail-closed or guardrail counter drift")
    if counters.get("raw_prompt_payload_written") is not False or counters.get("raw_response_payload_written") is not False:
        raise ValueError("v4_7_15 raw prompt/response payload must not be written")
