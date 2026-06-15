from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57
from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v5_7_1_retrieval_metric_integrity_audit"
SHORT_RUN_ID = "v5_7_1_retrieval_metric_integrity_audit_diagnostic_nonprod"
CANONICAL_LONG_RUN_ID = SHORT_RUN_ID
STATUS = "V5_7_1_RETRIEVAL_METRIC_INTEGRITY_AUDIT_DIAGNOSTIC_NONPROD_READY"
CURRENT_RESOLVES_TO = "v5_6"
KST_DOC_DATE = "2026-06-06"

SOURCE_V57_LOGICAL_RUN_KEY = v57.LOGICAL_RUN_KEY
SOURCE_V57_SHORT_RUN_ID = v57.SHORT_RUN_ID
BASELINE_LOGICAL_RUN_KEY = v57.BASELINE_LOGICAL_RUN_KEY
BASELINE_SHORT_RUN_ID = v57.BASELINE_SHORT_RUN_ID

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
METRIC_INTEGRITY_AUDIT_PATH = RUN_ROOT / "metric_integrity_audit.jsonl"
CANDIDATE_ORIGIN_AUDIT_PATH = RUN_ROOT / "candidate_origin_audit.jsonl"
LEAKAGE_PROBE_RESULTS_PATH = RUN_ROOT / "leakage_probe_results.jsonl"
METRIC_RESTATEMENT_PATH = RUN_ROOT / "metric_restatement.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "metric_integrity_audit_jsonl": METRIC_INTEGRITY_AUDIT_PATH.as_posix(),
    "candidate_origin_audit_jsonl": CANDIDATE_ORIGIN_AUDIT_PATH.as_posix(),
    "leakage_probe_results_jsonl": LEAKAGE_PROBE_RESULTS_PATH.as_posix(),
    "metric_restatement_json": METRIC_RESTATEMENT_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}

TOP_K = 5
PERFECT_RETRIEVAL_METRICS = dict(v57.PERFECT_RETRIEVAL_METRICS)
PRIOR_METRIC_INTERPRETATION = "diagnostic parity/replay only; not product retrieval quality"

LIVE_ORIGINS = {"live_vector_search", "live_hybrid_search"}
NON_LIVE_ORIGINS = {
    "baseline_topk_replay",
    "qrels_positive_seed",
    "target_search_unit_seed",
    "diagnostic_synthetic_distractor",
    "unknown",
}
ALLOWED_ORIGINS = LIVE_ORIGINS | NON_LIVE_ORIGINS
ALLOWED_BUCKETS = {
    "valid_live_retrieval",
    "baseline_parity_only",
    "oracle_or_target_seeded",
    "synthetic_distractor_only",
    "metric_ineligible",
}

CLOSED_FALSE_KEYS = (
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "official_denominator_mutation",
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
    "production_db_mutated",
    "source_registry_mutated",
    "index_rebuilt",
    "cache_mutated",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
)

FORBIDDEN_PAYLOAD_KEYS = set(v57.FORBIDDEN_PAYLOAD_KEYS) | {
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
    "expected_answer",
    "supporting_evidence",
    "supporting_evidence_ids",
    "gold_locator",
    "target_locator",
    "raw_local_path",
    "direct_answer_value",
    "official_denominator_mutation",
}
FORBIDDEN_PAYLOAD_KEYS.discard("official_denominator_mutation")

CandidateGenerator = Callable[[Mapping[str, Any]], Sequence[str]]


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _candidate_ids(row: Mapping[str, Any]) -> list[str]:
    for key in ("candidate_ids", "v5_7_candidate_ids", "topk_new"):
        values = row.get(key)
        if values:
            return [_clean(value) for value in list(values)[:TOP_K]]
    return []


def _baseline_topk(row: Mapping[str, Any]) -> list[str]:
    for key in ("baseline_topk_new", "topk_new"):
        values = row.get(key)
        if values:
            return [_clean(value) for value in list(values)[:TOP_K]]
    return []


def _target_search_unit_id(row: Mapping[str, Any]) -> str:
    return _clean(row.get("target_search_unit_id") or row.get("baseline_target_search_unit_id"))


def _qrels_positive_ids(row: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("qrels_positive_candidate_ids", "qrels_positive_ids"):
        values = row.get(key)
        if isinstance(values, Iterable) and not isinstance(values, (str, bytes)):
            ids.update(_clean(value) for value in values if _clean(value))
    for key in ("qrels_positive_candidate_id", "qrels_positive_id"):
        value = _clean(row.get(key))
        if value:
            ids.add(value)
    return ids


def _rank_at(candidate_ids: Sequence[str], target: str) -> int | None:
    if not target:
        return None
    for rank, candidate_id in enumerate(candidate_ids[:TOP_K], start=1):
        if candidate_id == target:
            return rank
    return None


def _is_synthetic(candidate_id: str) -> bool:
    return candidate_id.startswith("diagnostic-")


def _safe_candidate_list(candidate_generator: CandidateGenerator, row: Mapping[str, Any]) -> list[str]:
    return [_clean(candidate_id) for candidate_id in list(candidate_generator(row))[:TOP_K]]


def _sha256_candidate_ids(candidate_ids: Sequence[str]) -> str:
    return hashlib.sha256(json.dumps(list(candidate_ids), ensure_ascii=False).encode("utf-8")).hexdigest()


def _poison_non_existing_id(row: Mapping[str, Any], field: str) -> str:
    row_id = _clean(row.get("row_id"))
    query_id = _clean(row.get("query_id"))
    return f"poison-{field}-{row_id or query_id or 'row'}-non-existing"


def _mutate_target(row: Mapping[str, Any]) -> dict[str, Any]:
    mutated = _json_clone(row)
    poison = _poison_non_existing_id(row, "target_search_unit_id")
    mutated["target_search_unit_id"] = poison
    mutated["baseline_target_search_unit_id"] = poison
    return mutated


def _mutate_qrels_positive(row: Mapping[str, Any]) -> dict[str, Any]:
    mutated = _json_clone(row)
    replacement = _poison_non_existing_id(row, "qrels_positive")
    mutated["qrels_positive_candidate_ids"] = [replacement]
    mutated["qrels_positive_candidate_id"] = replacement
    mutated["qrels_positive_id"] = replacement
    return mutated


def _mutate_baseline_topk(row: Mapping[str, Any]) -> dict[str, Any]:
    mutated = _json_clone(row)
    topk = _baseline_topk(row)
    if len(topk) >= 2:
        poisoned = list(reversed(topk))
    else:
        poisoned = []
    mutated["baseline_topk_new"] = poisoned
    mutated["topk_new"] = poisoned
    return mutated


def _remove_evidence_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    mutated = _json_clone(row)
    for key in (
        "supporting_evidence_id",
        "supporting_evidence_ids",
        "supporting_evidence",
        "citation_locator",
        "expected_answer",
        "gold_locator",
        "target_locator",
    ):
        mutated.pop(key, None)
    return mutated


def _poison_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    mutated = _json_clone(row)
    mutated["query_id"] = _poison_non_existing_id(row, "query_id")
    mutated["row_id"] = _poison_non_existing_id(row, "row_id")
    return mutated


def run_leakage_probes_for_row(
    row: Mapping[str, Any],
    *,
    candidate_generator: CandidateGenerator | None = None,
) -> dict[str, Any]:
    generator = candidate_generator or _candidate_ids
    original = _safe_candidate_list(generator, row)
    probe_specs = (
        ("target_search_unit_id_poison", _mutate_target(row), "target_qrels_baseline"),
        ("qrels_positive_poison", _mutate_qrels_positive(row), "target_qrels_baseline"),
        ("baseline_topk_new_shuffle", _mutate_baseline_topk(row), "target_qrels_baseline"),
        ("evidence_fields_removed", _remove_evidence_fields(row), "protected_evidence_fields"),
        ("query_row_id_poison", _poison_identity(row), "identity_fields"),
    )
    probes: dict[str, Any] = {}
    failed_probe_names: list[str] = []
    protected_failed = False
    identity_failed = False
    for name, mutated_row, category in probe_specs:
        mutated = _safe_candidate_list(generator, mutated_row)
        changed = mutated != original
        probes[name] = {
            "candidate_list_changed": changed,
            "candidate_count": len(mutated),
            "candidate_ids_sha256": _sha256_candidate_ids(mutated),
            "probe_category": category,
        }
        if changed:
            failed_probe_names.append(name)
            if category in {"target_qrels_baseline", "protected_evidence_fields"}:
                protected_failed = True
            if category == "identity_fields":
                identity_failed = True
    return {
        "row_id": _clean(row.get("row_id")),
        "query_id": _clean(row.get("query_id")),
        "source_family": _clean(row.get("source_family")),
        "retrieval_metric_eligible": row.get("retrieval_metric_eligible") is True,
        "original_candidate_ids": original,
        "probes": probes,
        "failed_probe_names": failed_probe_names,
        "protected_field_leakage_failed": protected_failed,
        "identity_poison_failed": identity_failed,
        "leakage_probe_failed": bool(failed_probe_names),
    }


def _origin_for_candidate(
    candidate_id: str,
    *,
    baseline_topk: Sequence[str],
    target: str,
    qrels_positive_ids: set[str],
    override: Mapping[str, str],
) -> str:
    override_origin = _clean(override.get(candidate_id))
    if override_origin in ALLOWED_ORIGINS:
        return override_origin
    if _is_synthetic(candidate_id):
        return "diagnostic_synthetic_distractor"
    if candidate_id in baseline_topk:
        return "baseline_topk_replay"
    if target and candidate_id == target:
        return "target_search_unit_seed"
    if candidate_id in qrels_positive_ids:
        return "qrels_positive_seed"
    return "unknown"


def audit_candidate_origin_row(
    row: Mapping[str, Any],
    *,
    leakage_probe_failed: bool | None = None,
) -> dict[str, Any]:
    candidate_ids = _candidate_ids(row)
    baseline_topk = _baseline_topk(row)
    target = _target_search_unit_id(row)
    qrels_positive_ids = _qrels_positive_ids(row)
    override = row.get("candidate_origin_override") or {}
    if not isinstance(override, Mapping):
        override = {}
    origins: list[dict[str, Any]] = []
    for rank, candidate_id in enumerate(candidate_ids, start=1):
        origin = _origin_for_candidate(
            candidate_id,
            baseline_topk=baseline_topk,
            target=target,
            qrels_positive_ids=qrels_positive_ids,
            override=override,
        )
        origins.append(
            {
                "candidate_id": candidate_id,
                "rank": rank,
                "candidate_origin": origin,
                "matches_baseline_topk_new": candidate_id in baseline_topk,
                "matches_target_search_unit_id": bool(target and candidate_id == target),
                "matches_qrels_positive": candidate_id in qrels_positive_ids,
            }
        )
    origin_values = {entry["candidate_origin"] for entry in origins}
    candidate_list_identical = candidate_ids == baseline_topk
    target_rank = _rank_at(candidate_ids, target)
    top1_equals_target = bool(candidate_ids and target and candidate_ids[0] == target)
    synthetic_count = sum(1 for candidate_id in candidate_ids if _is_synthetic(candidate_id))
    real_non_target_count = sum(
        1 for candidate_id in candidate_ids if not _is_synthetic(candidate_id) and candidate_id != target
    )
    has_live_origin = bool(origin_values & LIVE_ORIGINS)
    retrieval_metric_eligible = row.get("retrieval_metric_eligible") is True
    if not retrieval_metric_eligible:
        bucket = "metric_ineligible"
    elif candidate_ids and synthetic_count == len(candidate_ids):
        bucket = "synthetic_distractor_only"
    elif candidate_list_identical:
        bucket = "baseline_parity_only"
    elif has_live_origin and leakage_probe_failed is False:
        bucket = "valid_live_retrieval"
    elif {"target_search_unit_seed", "qrels_positive_seed"} & origin_values or top1_equals_target:
        bucket = "oracle_or_target_seeded"
    else:
        bucket = "oracle_or_target_seeded"
    return {
        "row_id": _clean(row.get("row_id") or row.get("source_v5_4_review_row_id")),
        "query_id": _clean(row.get("query_id")),
        "source_family": _clean(row.get("source_family")),
        "retrieval_metric_eligible": retrieval_metric_eligible,
        "target_search_unit_id": target,
        "candidate_ids": candidate_ids,
        "candidate_origin": origins,
        "top1_origin": "" if not origins else origins[0]["candidate_origin"],
        "target_rank": target_rank,
        "candidate_count": len(candidate_ids),
        "synthetic_candidate_count": synthetic_count,
        "real_non_target_candidate_count": real_non_target_count,
        "candidate_list_identical_to_baseline_topk_new": candidate_list_identical,
        "top1_equals_target_search_unit_id": top1_equals_target,
        "metric_validity_bucket": bucket,
        "has_live_retrieval_origin": has_live_origin,
        "leakage_probe_failed": bool(leakage_probe_failed),
    }


def row_counts_for_valid_live_retrieval_metric(audit_row: Mapping[str, Any]) -> bool:
    if audit_row.get("retrieval_metric_eligible") is not True:
        return False
    if audit_row.get("metric_validity_bucket") != "valid_live_retrieval":
        return False
    if audit_row.get("leakage_probe_failed") is True:
        return False
    origins = {
        _clean(entry.get("candidate_origin"))
        for entry in list(audit_row.get("candidate_origin") or [])
        if isinstance(entry, Mapping)
    }
    return bool(origins & LIVE_ORIGINS)


def _v57_audit_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "row_id": _clean(row.get("row_id")),
        "query_id": _clean(row.get("query_id")),
        "source_family": _clean(row.get("source_family")),
        "retrieval_metric_eligible": row.get("retrieval_metric_eligible") is True,
        "target_search_unit_id": _clean(row.get("baseline_target_search_unit_id")),
        "candidate_ids": [_clean(candidate_id) for candidate_id in list(row.get("v5_7_candidate_ids") or [])[:TOP_K]],
        "baseline_topk_new": [_clean(candidate_id) for candidate_id in list(row.get("baseline_topk_new") or [])[:TOP_K]],
    }


def _v57_replay_probe_candidate_generator(row: Mapping[str, Any]) -> list[str]:
    query_id = _clean(row.get("query_id"))
    if query_id.startswith("poison-query_id-"):
        return []
    return _baseline_topk(row)


def _retrieval_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    eligible = [row for row in rows if row.get("retrieval_metric_eligible") is True]
    if not eligible:
        return {key: 0.0 for key in PERFECT_RETRIEVAL_METRICS}
    hit1 = hit3 = hit5 = mrr = ndcg = 0.0
    for row in eligible:
        rank = row.get("target_rank")
        if isinstance(rank, int) and rank <= TOP_K:
            hit5 += 1.0
            mrr += 1.0 / rank
            ndcg += 1.0 / math.log2(rank + 1)
            if rank <= 3:
                hit3 += 1.0
            if rank == 1:
                hit1 += 1.0
    denominator = len(eligible)
    return {
        "hit_at_1": round(hit1 / denominator, 4),
        "hit_at_3": round(hit3 / denominator, 4),
        "hit_at_5": round(hit5 / denominator, 4),
        "mrr_at_5": round(mrr / denominator, 4),
        "ndcg_at_5": round(ndcg / denominator, 4),
    }


def _load_or_build_v57_report(repo_root: Path, generated_at: str) -> dict[str, Any]:
    report_path = repo_root / v57.REPORT_PATH
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        v57.check_report(report, root=repo_root)
        return report
    report = v57.build_report(root=repo_root, generated_at=generated_at)
    v57.check_report(report)
    return report


def _count_origin(candidate_rows: Sequence[Mapping[str, Any]], origin: str) -> int:
    return sum(
        1
        for row in candidate_rows
        for entry in list(row.get("candidate_origin") or [])
        if isinstance(entry, Mapping) and entry.get("candidate_origin") == origin
    )


def _count_baseline_replay_membership(candidate_rows: Sequence[Mapping[str, Any]]) -> int:
    return sum(
        1
        for row in candidate_rows
        for entry in list(row.get("candidate_origin") or [])
        if isinstance(entry, Mapping) and entry.get("matches_baseline_topk_new") is True
    )


def _metric_integrity_rows(
    *,
    candidate_rows: Sequence[Mapping[str, Any]],
    leakage_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    leakage_by_query = {_clean(row.get("query_id")): row for row in leakage_rows}
    rows: list[dict[str, Any]] = []
    for row in candidate_rows:
        leakage = leakage_by_query.get(_clean(row.get("query_id"))) or {}
        rows.append(
            {
                "row_id": row["row_id"],
                "query_id": row["query_id"],
                "source_family": row["source_family"],
                "retrieval_metric_eligible": row["retrieval_metric_eligible"],
                "metric_validity_bucket": row["metric_validity_bucket"],
                "target_rank": row["target_rank"],
                "candidate_list_identical_to_baseline_topk_new": row[
                    "candidate_list_identical_to_baseline_topk_new"
                ],
                "top1_equals_target_search_unit_id": row["top1_equals_target_search_unit_id"],
                "leakage_probe_failed": leakage.get("leakage_probe_failed") is True,
                "failed_probe_names": list(leakage.get("failed_probe_names") or []),
                "valid_live_retrieval_denominator_included": row_counts_for_valid_live_retrieval_metric(row),
                "metric_restatement": "v5_7_baseline_parity_metric"
                if row["metric_validity_bucket"] == "baseline_parity_only"
                else "v5_7_valid_live_retrieval_metric"
                if row["metric_validity_bucket"] == "valid_live_retrieval"
                else "v5_7_oracle_seeded_or_synthetic_candidate_metric",
            }
        )
    return rows


def _metric_restatement(
    *,
    v57_report: Mapping[str, Any],
    candidate_rows: Sequence[Mapping[str, Any]],
    valid_live_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    baseline_rows = [
        row
        for row in candidate_rows
        if row.get("retrieval_metric_eligible") is True
        and row.get("metric_validity_bucket") == "baseline_parity_only"
    ]
    oracle_rows = [
        row
        for row in candidate_rows
        if row.get("retrieval_metric_eligible") is True
        and row.get("metric_validity_bucket") in {"oracle_or_target_seeded", "synthetic_distractor_only"}
    ]
    prior_metrics = (
        ((v57_report.get("diagnostic_retrieval_delta_table") or {}).get("metrics") or {}).get("v5_7")
        or PERFECT_RETRIEVAL_METRICS
    )
    return {
        "metric_restatement_required": True,
        "v5_7_prior_metric_interpretation": PRIOR_METRIC_INTERPRETATION,
        "v5_7_prior_metric": dict(prior_metrics),
        "v5_7_baseline_parity_metric": {
            "computed": bool(baseline_rows),
            "denominator": len(baseline_rows),
            "metrics": _retrieval_metrics(baseline_rows) if baseline_rows else None,
            "interpretation": "diagnostic baseline replay/parity only; not live retrieval quality",
        },
        "v5_7_oracle_seeded_or_synthetic_candidate_metric": {
            "computed": bool(oracle_rows),
            "denominator": len(oracle_rows),
            "metrics": _retrieval_metrics(oracle_rows) if oracle_rows else None,
            "interpretation": "oracle, target-seeded, qrels-seeded, or synthetic-only candidates are diagnostic only",
        },
        "v5_7_valid_live_retrieval_metric": {
            "computed": bool(valid_live_rows),
            "denominator": len(valid_live_rows),
            "metrics": _retrieval_metrics(valid_live_rows) if valid_live_rows else None,
            "blocked_reason": ""
            if valid_live_rows
            else "no row has live_vector_search/live_hybrid_search origin with leak-stable candidate generation",
        },
    }


def build_report(
    *,
    root: Path | str,
    generated_at: str | None = None,
    check: bool = True,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated = generated_at or common.utc_now_iso()
    v57_report = _load_or_build_v57_report(repo_root, generated)
    v57_rows = list(v57_report.get("route_candidate_diagnostics") or [])
    audit_input_rows = [_v57_audit_row(row) for row in v57_rows]
    leakage_rows = [
        run_leakage_probes_for_row(row, candidate_generator=_v57_replay_probe_candidate_generator)
        for row in audit_input_rows
    ]
    leakage_by_query = {_clean(row.get("query_id")): row for row in leakage_rows}
    candidate_rows = [
        audit_candidate_origin_row(
            row,
            leakage_probe_failed=(leakage_by_query.get(_clean(row.get("query_id"))) or {}).get(
                "leakage_probe_failed"
            )
            is True,
        )
        for row in audit_input_rows
    ]
    metric_rows = _metric_integrity_rows(candidate_rows=candidate_rows, leakage_rows=leakage_rows)
    valid_live_rows = [row for row in candidate_rows if row_counts_for_valid_live_retrieval_metric(row)]
    restatement = _metric_restatement(
        v57_report=v57_report,
        candidate_rows=candidate_rows,
        valid_live_rows=valid_live_rows,
    )
    bucket_counts = {
        bucket: sum(1 for row in candidate_rows if row.get("metric_validity_bucket") == bucket)
        for bucket in ALLOWED_BUCKETS
    }
    report: dict[str, Any] = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "source_v5_7_logical_run_key": SOURCE_V57_LOGICAL_RUN_KEY,
        "source_v5_7_short_run_id": SOURCE_V57_SHORT_RUN_ID,
        "source_v5_7_report_json": v57.REPORT_PATH.as_posix(),
        "baseline_logical_run_key": BASELINE_LOGICAL_RUN_KEY,
        "baseline_short_run_id": BASELINE_SHORT_RUN_ID,
        "baseline_report_json": v57.v56compare.FULL_PACKET_REPORT_PATH.as_posix(),
        "artifact_paths": dict(ARTIFACT_PATHS),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_consumed": 0,
        "official_metric_input_rows_created": 0,
        "source_official_metric_input_rows": 29,
        "route_comparison_rows": 29,
        "retrieval_metric_eligible_rows_prior": 28,
        "valid_live_retrieval_metric_rows": len(valid_live_rows),
        "baseline_parity_only_rows": bucket_counts["baseline_parity_only"],
        "oracle_or_target_seeded_rows": bucket_counts["oracle_or_target_seeded"],
        "synthetic_distractor_only_rows": bucket_counts["synthetic_distractor_only"],
        "metric_ineligible_rows": bucket_counts["metric_ineligible"],
        "candidate_list_identical_to_baseline_topk_new_count": sum(
            1 for row in candidate_rows if row.get("candidate_list_identical_to_baseline_topk_new") is True
        ),
        "top1_equals_target_search_unit_id_count": sum(
            1 for row in candidate_rows if row.get("top1_equals_target_search_unit_id") is True
        ),
        "synthetic_candidate_count": sum(int(row["synthetic_candidate_count"]) for row in candidate_rows),
        "real_non_target_candidate_count": sum(int(row["real_non_target_candidate_count"]) for row in candidate_rows),
        "leakage_probe_failed_count": sum(1 for row in leakage_rows if row.get("leakage_probe_failed") is True),
        "target_seeded_candidate_count": _count_origin(candidate_rows, "target_search_unit_seed"),
        "qrels_seeded_candidate_count": _count_origin(candidate_rows, "qrels_positive_seed"),
        "baseline_topk_replay_count": _count_baseline_replay_membership(candidate_rows),
        "valid_live_retrieval_metric_computed": bool(valid_live_rows),
        "metric_restatement_required": True,
        "v5_7_prior_metric_interpretation": PRIOR_METRIC_INTERPRETATION,
        "product_retrieval_quality_claim_supported": False,
        "quality_delta_claim_supported": False,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "answer_quality_metric_computed": False,
        "answer_quality_delta_computed": False,
        "retrieval_quality_delta_computed": False,
        "metric_integrity_audit": metric_rows,
        "candidate_origin_audit": candidate_rows,
        "leakage_probe_results": leakage_rows,
        "metric_restatement": restatement,
        "protected_namespaces_touched": [],
        "blockers_for_real_vectordb_retrieval_metric": [
            "replace baseline_topk_new replay with query-content-driven live_vector_search or live_hybrid_search",
            "remove query_id/row_id keyed candidate lookup from scoring and use stable query/search payload inputs only",
            "prove target_search_unit_id, qrels positive ids, baseline_topk_new, expected answers, supporting evidence, and citation locators are unavailable to candidate generation",
            "record nonzero live retrieval latency/cost counters from a real non-production VectorDB/index path",
            "keep denominator fixed and exclude any leakage-probe-failed row before computing live retrieval metrics",
        ],
    }
    for key in CLOSED_FALSE_KEYS:
        report[key] = False
    if check:
        check_report(report)
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_7_1 logical run key drift")
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_7_1 run identity drift")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_7_1 canonical identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v5_7_1 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v5_7_1 current alias drift")
    if report.get("source_v5_7_logical_run_key") != SOURCE_V57_LOGICAL_RUN_KEY:
        raise ValueError("v5_7_1 source v5_7 drift")


def _require_closed_gates(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v5_7_1 diagnostic/non-production gate drift")
    if report.get("official_metric") is not False:
        raise ValueError("v5_7_1 official metric gate opened")
    for key in (
        "official_metric_input_rows",
        "official_metric_input_rows_consumed",
        "official_metric_input_rows_created",
        "answer_metric_rows",
        "scored_answer_rows",
    ):
        if report.get(key) != 0:
            raise ValueError(f"v5_7_1 {key.replace('_', ' ')} drift")
    if report.get("answer_quality_metric_computed") is not False:
        raise ValueError("v5_7_1 answer quality metric opened")
    if report.get("quality_delta_claim_supported") is not False:
        raise ValueError("v5_7_1 quality delta claim opened")
    if report.get("product_retrieval_quality_claim_supported") is not False:
        raise ValueError("v5_7_1 product retrieval quality claim opened")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_7_1 protected namespace mutation drift")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_7_1 closed gate drift: {key}")


def _require_counters(report: Mapping[str, Any]) -> None:
    if report.get("source_official_metric_input_rows") != 29:
        raise ValueError("v5_7_1 source official metric input rows drift")
    if report.get("route_comparison_rows") != 29:
        raise ValueError("v5_7_1 route comparison denominator drift")
    if report.get("retrieval_metric_eligible_rows_prior") != 28:
        raise ValueError("v5_7_1 retrieval metric eligible prior drift")
    if report.get("metric_restatement_required") is not True:
        raise ValueError("v5_7_1 metric restatement required drift")
    if report.get("v5_7_prior_metric_interpretation") != PRIOR_METRIC_INTERPRETATION:
        raise ValueError("v5_7_1 prior metric interpretation drift")
    if report.get("valid_live_retrieval_metric_rows") != 0:
        raise ValueError("v5_7_1 valid live retrieval denominator drift")
    if report.get("valid_live_retrieval_metric_computed") is not False:
        raise ValueError("v5_7_1 valid live retrieval metric opened")
    if report.get("baseline_parity_only_rows") != 28:
        raise ValueError("v5_7_1 baseline parity row count drift")
    if report.get("oracle_or_target_seeded_rows") != 0:
        raise ValueError("v5_7_1 oracle/target-seeded row count drift")
    if report.get("synthetic_distractor_only_rows") != 0:
        raise ValueError("v5_7_1 synthetic-only row count drift")
    if report.get("candidate_list_identical_to_baseline_topk_new_count") != 29:
        raise ValueError("v5_7_1 baseline topk parity count drift")
    if report.get("top1_equals_target_search_unit_id_count") != 29:
        raise ValueError("v5_7_1 top1 target count drift")
    if report.get("leakage_probe_failed_count") != 29:
        raise ValueError("v5_7_1 leakage probe failed count drift")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    if report.get("artifact_paths") != ARTIFACT_PATHS:
        raise ValueError("v5_7_1 artifact path drift")


def _require_rows(report: Mapping[str, Any]) -> None:
    metric_rows = list(report.get("metric_integrity_audit") or [])
    candidate_rows = list(report.get("candidate_origin_audit") or [])
    leakage_rows = list(report.get("leakage_probe_results") or [])
    if len(metric_rows) != 29 or len(candidate_rows) != 29 or len(leakage_rows) != 29:
        raise ValueError("v5_7_1 audit row count drift")
    for row in candidate_rows:
        bucket = _clean(row.get("metric_validity_bucket"))
        if bucket not in ALLOWED_BUCKETS:
            raise ValueError("v5_7_1 bucket drift")
        if row.get("retrieval_metric_eligible") is True and bucket == "valid_live_retrieval":
            raise ValueError("v5_7_1 bucket drift: v5_7 has no valid live retrieval rows")
        for entry in list(row.get("candidate_origin") or []):
            if not isinstance(entry, Mapping):
                raise ValueError("v5_7_1 candidate origin schema drift")
            if _clean(entry.get("candidate_origin")) not in ALLOWED_ORIGINS:
                raise ValueError("v5_7_1 candidate origin value drift")
    if sum(1 for row in candidate_rows if row.get("retrieval_metric_eligible") is True) != 28:
        raise ValueError("v5_7_1 retrieval metric eligible audit row count drift")


def _require_restatement(report: Mapping[str, Any]) -> None:
    restatement = report.get("metric_restatement") or {}
    valid = restatement.get("v5_7_valid_live_retrieval_metric") or {}
    if valid.get("computed") is not False or valid.get("denominator") != 0:
        raise ValueError("v5_7_1 valid live retrieval metric restatement drift")
    baseline = restatement.get("v5_7_baseline_parity_metric") or {}
    if baseline.get("denominator") != 28:
        raise ValueError("v5_7_1 baseline parity metric restatement drift")
    oracle = restatement.get("v5_7_oracle_seeded_or_synthetic_candidate_metric") or {}
    if oracle.get("denominator") != 0:
        raise ValueError("v5_7_1 oracle/synthetic metric restatement drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    hashes = report.get("artifact_sha256") or {}
    for key, artifact_path in ARTIFACT_PATHS.items():
        if key == "status_jsonl":
            continue
        path = repo_root / artifact_path
        if not path.exists():
            raise ValueError(f"v5_7_1 artifact missing: {key}")
        if key == "report_json":
            continue
        expected = _clean(hashes.get(f"{key}_sha256"))
        if expected and expected != common.sha256_file(path):
            raise ValueError(f"v5_7_1 artifact hash drift: {key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_gates(report)
    _require_counters(report)
    _require_artifact_paths(report)
    _require_rows(report)
    _require_restatement(report)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_PAYLOAD_KEYS, context="v5_7_1_metric_integrity_audit")
    if root is not None:
        _require_written_artifacts(report, root=root)


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    payload = _json_clone(report)
    repo_root = Path(root)
    materialized = {
        "metric_integrity_audit_jsonl": payload["metric_integrity_audit"],
        "candidate_origin_audit_jsonl": payload["candidate_origin_audit"],
        "leakage_probe_results_jsonl": payload["leakage_probe_results"],
        "metric_restatement_json": payload["metric_restatement"],
    }
    for key, value in materialized.items():
        path = repo_root / ARTIFACT_PATHS[key]
        if path.suffix == ".jsonl":
            common.write_jsonl(path, value)
        else:
            common.write_json(path, value)
    artifact_hashes = {
        f"{key}_sha256": common.sha256_file(repo_root / ARTIFACT_PATHS[key])
        for key in materialized
    }
    payload["artifact_sha256"] = dict(artifact_hashes)
    common.write_json(repo_root / ARTIFACT_PATHS["report_json"], payload)
    artifact_hashes["report_json_sha256"] = common.sha256_file(repo_root / ARTIFACT_PATHS["report_json"])
    check_report(payload, root=root)
    return payload, artifact_hashes


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
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
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "answer_quality_metric_computed": False,
        "source_official_metric_input_rows": 29,
        "route_comparison_rows": 29,
        "retrieval_metric_eligible_rows_prior": 28,
        "valid_live_retrieval_metric_rows": report["valid_live_retrieval_metric_rows"],
        "baseline_parity_only_rows": report["baseline_parity_only_rows"],
        "oracle_or_target_seeded_rows": report["oracle_or_target_seeded_rows"],
        "synthetic_distractor_only_rows": report["synthetic_distractor_only_rows"],
        "candidate_list_identical_to_baseline_topk_new_count": report[
            "candidate_list_identical_to_baseline_topk_new_count"
        ],
        "top1_equals_target_search_unit_id_count": report["top1_equals_target_search_unit_id_count"],
        "synthetic_candidate_count": report["synthetic_candidate_count"],
        "real_non_target_candidate_count": report["real_non_target_candidate_count"],
        "leakage_probe_failed_count": report["leakage_probe_failed_count"],
        "target_seeded_candidate_count": report["target_seeded_candidate_count"],
        "qrels_seeded_candidate_count": report["qrels_seeded_candidate_count"],
        "baseline_topk_replay_count": report["baseline_topk_replay_count"],
        "valid_live_retrieval_metric_computed": report["valid_live_retrieval_metric_computed"],
        "metric_restatement_required": True,
        "v5_7_prior_metric_interpretation": PRIOR_METRIC_INTERPRETATION,
        "product_retrieval_quality_claim_supported": False,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
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


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} adds a diagnostic-only metric integrity audit at "
        f"`{REPORT_PATH.as_posix()}` for the prior v5_7 vector/LLM candidate-routing run. "
        "The audit restates the v5_7 1.0000 retrieval metric as baseline parity/replay only: "
        f"baseline_parity_only_rows={report['baseline_parity_only_rows']}, "
        f"valid_live_retrieval_metric_rows={report['valid_live_retrieval_metric_rows']}, "
        f"valid_live_retrieval_metric_computed={str(report['valid_live_retrieval_metric_computed']).lower()}, "
        f"leakage_probe_failed_count={report['leakage_probe_failed_count']}. "
        "answer_metric_rows=0, scored_answer_rows=0, answer_quality_metric_computed=false, official_metric=false. "
        "No production routing, live DB/index/cache readiness, gold/qrels/expected/supporting/denominator mutation, "
        "promotion, product-success, training, fine-tuning, or FT-A gate is opened; `current` remains `v5_6`."
    )
    measurements_block = (
        f"### {SHORT_RUN_ID}\n\n"
        "- Scope: diagnostic-only metric integrity audit over `v5_7_vector_llm_candidate_routing` using the "
        "v5_6 full-packet new retrieval metric as prior baseline; no answer-quality metric is computed.\n"
        f"- Restatement: `v5_7_baseline_parity_metric` denominator={report['baseline_parity_only_rows']} "
        "with the prior 1.0000 values; `v5_7_valid_live_retrieval_metric` denominator="
        f"{report['valid_live_retrieval_metric_rows']} and computed="
        f"{str(report['valid_live_retrieval_metric_computed']).lower()}; "
        f"`v5_7_oracle_seeded_or_synthetic_candidate_metric` denominator={report['oracle_or_target_seeded_rows'] + report['synthetic_distractor_only_rows']}.\n"
        f"- Origin/probe counters: candidate_list_identical_to_baseline_topk_new_count="
        f"{report['candidate_list_identical_to_baseline_topk_new_count']}; "
        f"top1_equals_target_search_unit_id_count={report['top1_equals_target_search_unit_id_count']}; "
        f"baseline_topk_replay_count={report['baseline_topk_replay_count']}; "
        f"synthetic_candidate_count={report['synthetic_candidate_count']}; "
        f"real_non_target_candidate_count={report['real_non_target_candidate_count']}; "
        f"leakage_probe_failed_count={report['leakage_probe_failed_count']}."
    )
    triage_block = (
        f"- {SHORT_RUN_ID}: v5_7 prior retrieval metric is reclassified as "
        "`diagnostic parity/replay only; not product retrieval quality`. All 29 candidate lists are identical to "
        "baseline_topk_new and top-1 equals the target search unit; the 28 eligible rows are "
        "`baseline_parity_only`, while the valid live retrieval denominator is 0. "
        "Blockers before opening a real VectorDB retrieval metric: replace baseline_topk replay with a "
        "query-content-driven live vector/hybrid path, remove query_id/row_id keyed lookup from scoring, prove "
        "target/qrels/baseline/expected/supporting/citation fields are unavailable to candidate generation, record "
        "nonzero live retrieval latency/cost, and exclude leakage-probe-failed rows from the metric denominator."
    )
    for path, block, suffix in (
        (PROGRESS_DOC, progress_block, "progress-entry"),
        (MEASUREMENTS_DOC, measurements_block, "measurements-entry"),
        (TRIAGE_DOC, triage_block, "triage-entry"),
    ):
        full_path = repo_root / path
        text = full_path.read_text(encoding="utf-8")
        text = common.upsert_block_at_top(
            text,
            start_marker=f"<!-- {SHORT_RUN_ID}:{suffix}:start -->",
            end_marker=f"<!-- {SHORT_RUN_ID}:{suffix}:end -->",
            block=block,
        )
        full_path.write_text(text, encoding="utf-8")
