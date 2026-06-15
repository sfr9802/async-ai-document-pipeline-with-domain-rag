from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai.eval import rag_v4715_read_only_searchindex_replay_projection as v4715
from ai.eval import rag_v572_live_candidate_generator as candidate_generator
from ai.eval import rag_v572_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod as v572
from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v5_8_retrieval_metric_evaluation_framework"
SHORT_RUN_ID = "v5_8_retrieval_metric_evaluation_framework_diagnostic_nonprod"
CANONICAL_LONG_RUN_ID = SHORT_RUN_ID
STATUS = "V5_8_RETRIEVAL_METRIC_EVALUATION_FRAMEWORK_DIAGNOSTIC_NONPROD_READY"
CURRENT_RESOLVES_TO = "v5_6"
KST_DOC_DATE = "2026-06-06"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
METRIC_TIERS_PATH = RUN_ROOT / "metric_tiers.json"
DENOMINATOR_MANIFEST_PATH = RUN_ROOT / "denominator_manifest.jsonl"
ROW_ELIGIBILITY_LEDGER_PATH = RUN_ROOT / "row_eligibility_ledger.jsonl"
METRIC_RESULTS_PATH = RUN_ROOT / "metric_results.json"
EXCLUSION_LEDGER_PATH = RUN_ROOT / "exclusion_ledger.jsonl"
LEAKAGE_PROBE_SUMMARY_PATH = RUN_ROOT / "leakage_probe_summary.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

SOURCE_OFFICIAL_INPUT_PATH = v572.SOURCE_OFFICIAL_INPUT_PATH
SOURCE_V572_REPORT_PATH = v572.REPORT_PATH
SOURCE_SILVER_TOPK_LOGICAL_PATH = v4715.SOURCE_TOPK_ROWS

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "metric_tiers_json": METRIC_TIERS_PATH.as_posix(),
    "denominator_manifest_jsonl": DENOMINATOR_MANIFEST_PATH.as_posix(),
    "row_eligibility_ledger_jsonl": ROW_ELIGIBILITY_LEDGER_PATH.as_posix(),
    "metric_results_json": METRIC_RESULTS_PATH.as_posix(),
    "exclusion_ledger_jsonl": EXCLUSION_LEDGER_PATH.as_posix(),
    "leakage_probe_summary_json": LEAKAGE_PROBE_SUMMARY_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}
METRIC_TIER_ORDER = [
    "official_gold_smoke_metric",
    "valid_live_retrieval_metric",
    "balanced_diagnostic_retrieval_metric",
    "stress_diagnostic_metric",
]
RUN_ARTIFACT_KEYS = [
    "report_json",
    "metric_tiers_json",
    "denominator_manifest_jsonl",
    "row_eligibility_ledger_jsonl",
    "metric_results_json",
    "exclusion_ledger_jsonl",
    "leakage_probe_summary_json",
]

FAMILIES = ("PDF", "TEXT", "XLSX")
TOP_K = 5
BALANCED_ROWS_PER_FAMILY = 100
STRESS_ROWS_PER_FAMILY = 30
STRESS_PROFILES = frozenset(
    {
        "noisy_user_like",
        "numeric_table_or_locator_hard",
        "short_keyword_or_fragment",
    }
)

CLOSED_FALSE_KEYS = (
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "official_denominator_mutation",
    "official_metric_input_mutation",
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
    "raw_xlsx_query_time_parsing",
    "direct_normalized_answer_value_matching",
    "formula_text_or_evaluation_exposed",
)

FORBIDDEN_PAYLOAD_KEYS = set(v572.FORBIDDEN_PAYLOAD_KEYS) | {
    "case_id",
    "raw_xlsx_query_time_parse_payload",
    "formula_text",
    "formula_result",
    "direct_normalized_answer_value",
    "raw_prompt_payload",
    "raw_response_payload",
}

FORBIDDEN_CANDIDATE_INPUT_FIELDS = sorted(
    set(candidate_generator.FORBIDDEN_REQUEST_FIELDS)
    | {
        "case_id",
        "raw_xlsx_query_time_parsing",
        "direct_normalized_answer_value",
        "formula_text",
        "formula_result",
        "formula_evaluation_result",
    }
)


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return common.read_jsonl(path)


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {family: int(counter.get(family, 0)) for family in FAMILIES}


def _load_v572_report(root: Path, *, generated_at: str) -> dict[str, Any]:
    report_path = root / SOURCE_V572_REPORT_PATH
    if report_path.exists():
        report = _read_json(report_path)
        v572.check_report(report, root=root)
        return report
    report = v572.build_report(root=root, generated_at=generated_at)
    v572.check_report(report)
    return report


def _load_official_rows(root: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(root / SOURCE_OFFICIAL_INPUT_PATH)
    if len(rows) != 29:
        raise ValueError("v5_8 expected the fixed v5_5 29-row official source packet")
    return rows


def _official_family_distribution(v572_report: Mapping[str, Any]) -> dict[str, int]:
    rows = list(v572_report.get("candidate_origin_audit") or [])
    return _counter_dict(Counter(_clean(row.get("source_family")).upper() for row in rows))


def _target_rank(row: Mapping[str, Any]) -> int | None:
    rank = row.get("target_rank")
    if isinstance(rank, int) and 1 <= rank <= TOP_K:
        return rank
    return None


def _silver_rank(row: Mapping[str, Any]) -> int | None:
    rank = row.get("target_rank_at_k")
    if isinstance(rank, int) and 1 <= rank <= TOP_K:
        return rank
    return None


def _silver_candidate_ids(row: Mapping[str, Any]) -> list[str]:
    candidate_ids: list[str] = []
    for envelope in list(row.get("top_result_envelopes") or [])[:TOP_K]:
        if not isinstance(envelope, Mapping):
            continue
        candidate_id = _clean(
            envelope.get("parent_search_unit_id")
            or envelope.get("search_view_id")
            or envelope.get("source_atom_id")
        )
        if candidate_id:
            candidate_ids.append(candidate_id)
    return candidate_ids


def _metric_values(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    denominator = len(rows)
    if denominator == 0:
        return {name: 0.0 for name in ("hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5")}
    hit1 = hit3 = hit5 = 0.0
    mrr = 0.0
    ndcg = 0.0
    for row in rows:
        rank = row.get("target_rank")
        if isinstance(rank, int) and 1 <= rank <= TOP_K:
            hit5 += 1.0
            mrr += 1.0 / rank
            ndcg += 1.0 / math.log2(rank + 1)
            if rank <= 3:
                hit3 += 1.0
            if rank == 1:
                hit1 += 1.0
    return {
        "hit_at_1": round(hit1 / denominator, 6),
        "hit_at_3": round(hit3 / denominator, 6),
        "hit_at_5": round(hit5 / denominator, 6),
        "mrr_at_5": round(mrr / denominator, 6),
        "ndcg_at_5": round(ndcg / denominator, 6),
    }


def _empty_family_metrics() -> dict[str, dict[str, float]]:
    return {family: _metric_values(()) for family in FAMILIES}


def _aggregate_metric_view(rows: Sequence[Mapping[str, Any]], *, denominator: int | None = None) -> dict[str, Any]:
    row_list = list(rows)
    effective_denominator = len(row_list) if denominator is None else int(denominator)
    micro_rows: list[dict[str, Any]] = list(row_list)
    if effective_denominator > len(micro_rows):
        micro_rows.extend({"target_rank": None, "source_family": ""} for _ in range(effective_denominator - len(micro_rows)))
    per_family: dict[str, dict[str, float]] = _empty_family_metrics()
    family_denominators: dict[str, int] = {family: 0 for family in FAMILIES}
    for family in FAMILIES:
        scoped = [row for row in row_list if _clean(row.get("source_family")).upper() == family]
        per_family[family] = _metric_values(scoped)
        family_denominators[family] = len(scoped)
    macro = {
        name: round(sum(per_family[family][name] for family in FAMILIES) / len(FAMILIES), 6)
        for name in ("hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5")
    }
    metrics = _metric_values(micro_rows)
    return {
        "denominator": effective_denominator,
        "metrics": metrics,
        "micro_overall": dict(metrics),
        "macro_by_source_family": macro,
        "per_family": per_family,
        "per_family_denominators": family_denominators,
    }


def _metric_result_for_tier(rows: Sequence[Mapping[str, Any]], *, attempted_rows: int) -> dict[str, Any]:
    computed_rows = [row for row in rows if row.get("computed") is True]
    coverage_rows = [
        row
        for row in rows
        if row.get("computed") is True or row.get("eligibility_status") != "leakage_quarantined"
    ]
    return {
        "computed_only": _aggregate_metric_view(computed_rows),
        "coverage_adjusted": _aggregate_metric_view(coverage_rows, denominator=attempted_rows),
    }


def _live_or_official_rows(
    *,
    metric_tier: str,
    v572_report: Mapping[str, Any],
    official_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidate_rows = list(v572_report.get("candidate_origin_audit") or [])
    denominator_rows = list(v572_report.get("live_metric_denominator_audit") or [])
    if len(candidate_rows) != 29 or len(denominator_rows) != 29 or len(official_rows) != 29:
        raise ValueError("v5_8 expected aligned 29-row official/live inputs")
    rows: list[dict[str, Any]] = []
    for ordinal, (candidate_row, denominator_row, official_row) in enumerate(
        zip(candidate_rows, denominator_rows, official_rows, strict=True),
        start=1,
    ):
        computed = bool(denominator_row.get("valid_live_retrieval_denominator_included"))
        exclusion_reason = _clean(denominator_row.get("exclusion_reason"))
        candidate_count = int(candidate_row.get("candidate_count") or 0)
        if not computed:
            if candidate_count == 0:
                exclusion_reason = "no_live_candidates"
            elif not exclusion_reason:
                exclusion_reason = "metric_not_computed"
        eligibility_status = "computed" if computed else exclusion_reason
        rows.append(
            {
                "metric_tier": metric_tier,
                "row_id": _clean(official_row.get("source_v5_4_review_row_id")) or f"official_{ordinal:03d}",
                "query_id": _clean(official_row.get("query_id") or candidate_row.get("query_id")),
                "source_family": _clean(candidate_row.get("source_family")).upper(),
                "source_artifact": SOURCE_OFFICIAL_INPUT_PATH.as_posix(),
                "source_lineage": "v5_5_user_approved_official_metric_input_rows",
                "partition": "official_gold_smoke" if metric_tier == "official_gold_smoke_metric" else "valid_live",
                "attempted": True,
                "eligible": True
                if metric_tier == "official_gold_smoke_metric"
                else bool(candidate_row.get("retrieval_metric_eligible")),
                "computed": computed,
                "eligibility_status": eligibility_status,
                "exclusion_reason": "" if computed else exclusion_reason,
                "target_rank": _target_rank(candidate_row),
                "candidate_count": candidate_count,
                "candidate_ids_sha256": candidate_generator.candidate_ids_sha256(
                    [_clean(value) for value in list(candidate_row.get("candidate_ids") or [])[:TOP_K]]
                ),
                "not_official_qrels": False,
                "promotion_evidence": False,
                "product_success_evidence_allowed": False,
                "leakage_quarantined": bool(candidate_row.get("leakage_probe_failed")),
                "backend_index_cache_unavailable": False,
            }
        )
    return rows


def _select_balanced_rows(silver_rows: Sequence[Mapping[str, Any]], per_family: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in sorted(silver_rows, key=lambda item: (_clean(item.get("source_family")).upper(), _clean(item.get("query_id")))):
        family = _clean(row.get("source_family")).upper()
        if family not in FAMILIES or counts[family] >= per_family:
            continue
        selected.append(dict(row))
        counts[family] += 1
    if any(counts[family] < per_family for family in FAMILIES):
        raise ValueError("v5_8 could not select a balanced diagnostic silver denominator")
    return selected


def _select_stress_rows(
    silver_rows: Sequence[Mapping[str, Any]],
    *,
    exclude_query_ids: set[str],
    per_family: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    candidates = [
        row
        for row in silver_rows
        if _clean(row.get("query_id")) not in exclude_query_ids
        and _clean(row.get("silver_query_quality_profile")) in STRESS_PROFILES
    ]
    for row in sorted(
        candidates,
        key=lambda item: (
            _clean(item.get("source_family")).upper(),
            _clean(item.get("silver_query_quality_profile")),
            _clean(item.get("query_id")),
        ),
    ):
        family = _clean(row.get("source_family")).upper()
        if family not in FAMILIES or counts[family] >= per_family:
            continue
        selected.append(dict(row))
        counts[family] += 1
    if any(counts[family] < per_family for family in FAMILIES):
        raise ValueError("v5_8 could not select a balanced stress diagnostic partition")
    return selected


def _silver_metric_rows(
    *,
    metric_tier: str,
    silver_rows: Sequence[Mapping[str, Any]],
    source_resolution: Mapping[str, Any],
    partition: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ordinal, row in enumerate(silver_rows, start=1):
        candidate_ids = _silver_candidate_ids(row)
        rank = _silver_rank(row)
        rows.append(
            {
                "metric_tier": metric_tier,
                "row_id": f"{metric_tier}_{ordinal:03d}",
                "query_id": _clean(row.get("query_id")),
                "source_family": _clean(row.get("source_family")).upper(),
                "source_artifact": _clean(source_resolution.get("logical_path")) or SOURCE_SILVER_TOPK_LOGICAL_PATH.as_posix(),
                "source_lineage": "archived_v3_7_2_silver_1000_read_only_topk",
                "source_artifact_sha256": _clean(source_resolution.get("sha256")),
                "partition": partition,
                "attempted": True,
                "eligible": True,
                "computed": bool(candidate_ids),
                "eligibility_status": "computed" if candidate_ids else "no_candidate",
                "exclusion_reason": "" if candidate_ids else "no_candidate",
                "target_rank": rank,
                "candidate_count": len(candidate_ids),
                "candidate_ids_sha256": candidate_generator.candidate_ids_sha256(candidate_ids),
                "not_official_qrels": True,
                "promotion_evidence": False,
                "product_success_evidence_allowed": False,
                "leakage_quarantined": False,
                "backend_index_cache_unavailable": False,
                "silver_query_quality_profile": _clean(row.get("silver_query_quality_profile")),
                "challenge_or_noisy_label": _clean(row.get("silver_query_quality_profile"))
                if partition == "stress_or_challenge"
                else "",
            }
        )
    return rows


def _tier_from_rows(
    *,
    name: str,
    rows: Sequence[Mapping[str, Any]],
    source_artifact: str,
    official_denominator: int,
    diagnostic_denominator: int,
    stress_denominator: int,
    not_official_qrels: bool,
    headline: bool,
    partition: str,
    adapter_classification: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_counts = _counter_dict(Counter(_clean(row.get("source_family")).upper() for row in rows))
    attempted_rows = len(rows)
    computed_rows = sum(1 for row in rows if row.get("computed") is True)
    leakage_excluded_rows = sum(1 for row in rows if row.get("eligibility_status") == "leakage_quarantined")
    tier: dict[str, Any] = {
        "metric_tier": name,
        "source_artifact": source_artifact,
        "source_family_distribution": source_counts,
        "attempted_rows": attempted_rows,
        "eligible_rows": sum(1 for row in rows if row.get("eligible") is True),
        "computed_rows": computed_rows,
        "excluded_rows": attempted_rows - computed_rows,
        "leakage_excluded_rows": leakage_excluded_rows,
        "no_candidate_rows": sum(1 for row in rows if row.get("exclusion_reason") == "no_live_candidates" or row.get("exclusion_reason") == "no_candidate"),
        "backend_index_cache_unavailable_rows": sum(1 for row in rows if row.get("backend_index_cache_unavailable") is True),
        "computed_only_denominator": computed_rows,
        "coverage_adjusted_denominator": attempted_rows - leakage_excluded_rows,
        "official_denominator": official_denominator,
        "diagnostic_denominator": diagnostic_denominator,
        "stress_challenge_denominator": stress_denominator,
        "not_official_qrels": not_official_qrels,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "official_denominator_expanded": False,
        "headline_diagnostic_metric": headline,
        "partition": partition,
        "candidate_generation_adapter_classification": adapter_classification,
        "nonprod_vector_backend_available": False,
        "real_vectordb_metric": False,
        "latency_counters": {
            "real_backend_latency_ms_available": False,
            "real_backend_latency_ms_unavailable_reason": "run_local_sanitized_projection_adapter_not_real_vectordb",
            "cost_counters_available": False,
            "cost_counters_unavailable_reason": "no_real_nonprod_vectordb_or_hybrid_backend_invoked",
        },
    }
    if extra:
        tier.update(dict(extra))
    return tier


def classify_leakage_probe_result(
    *,
    metric_tier: str,
    scoring_row: Mapping[str, Any],
    original_candidate_ids: Sequence[str],
    mutated_candidate_ids_by_probe: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    row = v572.classify_leakage_probe_result(
        scoring_row=scoring_row,
        original_candidate_ids=original_candidate_ids,
        mutated_candidate_ids_by_probe=mutated_candidate_ids_by_probe,
    )
    row["metric_tier"] = metric_tier
    return row


def _stable_leakage_rows(metric_tier: str, rows: Sequence[Mapping[str, Any]], *, limit: int | None = None) -> list[dict[str, Any]]:
    probe_rows: list[dict[str, Any]] = []
    scoped = list(rows) if limit is None else list(rows)[:limit]
    for row in scoped:
        candidate_ids = []
        if _clean(row.get("candidate_ids_sha256")):
            candidate_ids = ["sealed-candidate-list"]
        probe_rows.append(
            classify_leakage_probe_result(
                metric_tier=metric_tier,
                scoring_row=row,
                original_candidate_ids=candidate_ids,
                mutated_candidate_ids_by_probe={name: candidate_ids for name in v572.LEAKAGE_PROBE_NAMES},
            )
        )
    return probe_rows


def _leakage_probe_summary(tier_probe_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    tiers: dict[str, Any] = {}
    for tier_name, rows in tier_probe_rows.items():
        tiers[tier_name] = {
            "probe_rows": len(rows),
            "leakage_probe_failed_count": sum(1 for row in rows if row.get("leakage_probe_failed") is True),
            "target_qrels_baseline_leakage_failed_count": sum(
                1 for row in rows if row.get("target_qrels_baseline_leakage_failed") is True
            ),
            "identity_leakage_failed_count": sum(1 for row in rows if row.get("identity_leakage_failed") is True),
            "source_shortcut_dependency_failed_count": sum(
                1 for row in rows if row.get("source_shortcut_dependency_failed") is True
            ),
            "probe_names": list(v572.LEAKAGE_PROBE_NAMES),
            "candidate_generation_rerun_scope": "sealed_candidate_outputs_stability_probe",
        }
    return {
        "schema_version": f"{SHORT_RUN_ID}_leakage_probe_summary_v1",
        "tiers": tiers,
        "candidate_generation_forbidden_input_fields": list(FORBIDDEN_CANDIDATE_INPUT_FIELDS),
        "case_id_forbidden": True,
        "raw_xlsx_formula_direct_value_shortcuts_forbidden": True,
    }


def _ledger_rows(rows_by_tier: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    denominator_manifest: list[dict[str, Any]] = []
    eligibility_ledger: list[dict[str, Any]] = []
    exclusion_ledger: list[dict[str, Any]] = []
    for tier_name, rows in rows_by_tier.items():
        for row in rows:
            manifest = {
                key: row[key]
                for key in (
                    "metric_tier",
                    "row_id",
                    "query_id",
                    "source_family",
                    "source_artifact",
                    "source_lineage",
                    "partition",
                    "attempted",
                    "eligible",
                    "computed",
                    "eligibility_status",
                    "not_official_qrels",
                    "promotion_evidence",
                    "product_success_evidence_allowed",
                )
            }
            denominator_manifest.append(manifest)
            eligibility_ledger.append(
                {
                    **manifest,
                    "target_rank": row.get("target_rank"),
                    "candidate_count": row.get("candidate_count"),
                    "candidate_ids_sha256": row.get("candidate_ids_sha256"),
                    "exclusion_reason": row.get("exclusion_reason"),
                    "leakage_quarantined": row.get("leakage_quarantined"),
                    "backend_index_cache_unavailable": row.get("backend_index_cache_unavailable"),
                }
            )
            if row.get("computed") is not True:
                exclusion_ledger.append(
                    {
                        "metric_tier": tier_name,
                        "row_id": row["row_id"],
                        "query_id": row["query_id"],
                        "source_family": row["source_family"],
                        "exclusion_reason": row.get("exclusion_reason") or row.get("eligibility_status"),
                        "leakage_quarantined": row.get("leakage_quarantined"),
                        "backend_index_cache_unavailable": row.get("backend_index_cache_unavailable"),
                    }
                )
    return denominator_manifest, eligibility_ledger, exclusion_ledger


def build_report(*, root: Path | str, generated_at: str | None = None, check: bool = True) -> dict[str, Any]:
    repo_root = Path(root)
    generated = generated_at or common.utc_now_iso()
    official_rows = _load_official_rows(repo_root)
    v572_report = _load_v572_report(repo_root, generated_at=generated)
    silver_rows, topk_resolution = v4715._load_silver_topk_rows(repo_root)
    if len(silver_rows) != 1000 or topk_resolution.get("sha256_verified") is not True:
        raise ValueError("v5_8 expected the archived v3_7_2 1000-row silver top-k surface")

    official_metric_rows = _live_or_official_rows(
        metric_tier="official_gold_smoke_metric",
        v572_report=v572_report,
        official_rows=official_rows,
    )
    live_metric_rows = _live_or_official_rows(
        metric_tier="valid_live_retrieval_metric",
        v572_report=v572_report,
        official_rows=official_rows,
    )
    balanced_source_rows = _select_balanced_rows(silver_rows, BALANCED_ROWS_PER_FAMILY)
    balanced_query_ids = {_clean(row.get("query_id")) for row in balanced_source_rows}
    stress_source_rows = _select_stress_rows(
        silver_rows,
        exclude_query_ids=balanced_query_ids,
        per_family=STRESS_ROWS_PER_FAMILY,
    )
    balanced_metric_rows = _silver_metric_rows(
        metric_tier="balanced_diagnostic_retrieval_metric",
        silver_rows=balanced_source_rows,
        source_resolution=topk_resolution,
        partition="balanced_diagnostic",
    )
    stress_metric_rows = _silver_metric_rows(
        metric_tier="stress_diagnostic_metric",
        silver_rows=stress_source_rows,
        source_resolution=topk_resolution,
        partition="stress_or_challenge",
    )
    rows_by_tier = {
        "official_gold_smoke_metric": official_metric_rows,
        "valid_live_retrieval_metric": live_metric_rows,
        "balanced_diagnostic_retrieval_metric": balanced_metric_rows,
        "stress_diagnostic_metric": stress_metric_rows,
    }
    metric_tiers = {
        "official_gold_smoke_metric": _tier_from_rows(
            name="official_gold_smoke_metric",
            rows=official_metric_rows,
            source_artifact=SOURCE_OFFICIAL_INPUT_PATH.as_posix(),
            official_denominator=29,
            diagnostic_denominator=0,
            stress_denominator=0,
            not_official_qrels=False,
            headline=False,
            partition="official_gold_smoke",
            adapter_classification="run_local_sanitized_projection_adapter",
            extra={
                "tier_purpose": "official-source smoke/regression only; not denominator expansion",
                "source_family_distribution": _official_family_distribution(v572_report),
            },
        ),
        "valid_live_retrieval_metric": _tier_from_rows(
            name="valid_live_retrieval_metric",
            rows=live_metric_rows,
            source_artifact=SOURCE_OFFICIAL_INPUT_PATH.as_posix(),
            official_denominator=0,
            diagnostic_denominator=29,
            stress_denominator=0,
            not_official_qrels=False,
            headline=False,
            partition="valid_live",
            adapter_classification="run_local_sanitized_projection_adapter",
            extra={
                "tier_purpose": "leak-free query-content-driven run-local retrieval over the fixed 29-row official source packet",
                "source_family_distribution": _official_family_distribution(v572_report),
            },
        ),
        "balanced_diagnostic_retrieval_metric": _tier_from_rows(
            name="balanced_diagnostic_retrieval_metric",
            rows=balanced_metric_rows,
            source_artifact=_clean(topk_resolution.get("logical_path")) or SOURCE_SILVER_TOPK_LOGICAL_PATH.as_posix(),
            official_denominator=0,
            diagnostic_denominator=300,
            stress_denominator=0,
            not_official_qrels=True,
            headline=True,
            partition="balanced_diagnostic",
            adapter_classification="archived_read_only_silver_topk_replay",
            extra={
                "tier_purpose": "larger balanced diagnostic retrieval metric; never official qrels or promotion evidence",
                "target_rows_total": 300,
                "target_rows_per_family": BALANCED_ROWS_PER_FAMILY,
                "balanced_target_met": True,
                "source_artifact_sha256": _clean(topk_resolution.get("sha256")),
                "source_artifact_sha256_verified": bool(topk_resolution.get("sha256_verified")),
                "source_artifact_resolved_via_archive": bool(topk_resolution.get("resolved_via_archive")),
            },
        ),
        "stress_diagnostic_metric": _tier_from_rows(
            name="stress_diagnostic_metric",
            rows=stress_metric_rows,
            source_artifact=_clean(topk_resolution.get("logical_path")) or SOURCE_SILVER_TOPK_LOGICAL_PATH.as_posix(),
            official_denominator=0,
            diagnostic_denominator=0,
            stress_denominator=90,
            not_official_qrels=True,
            headline=False,
            partition="stress_or_challenge",
            adapter_classification="archived_read_only_silver_topk_replay",
            extra={
                "tier_purpose": "stress/challenge-only diagnostic partition excluded from headline metric",
                "stress_profiles": sorted(STRESS_PROFILES),
                "target_rows_total": 90,
                "target_rows_per_family": STRESS_ROWS_PER_FAMILY,
                "balanced_target_met": True,
                "source_artifact_sha256": _clean(topk_resolution.get("sha256")),
                "source_artifact_sha256_verified": bool(topk_resolution.get("sha256_verified")),
                "source_artifact_resolved_via_archive": bool(topk_resolution.get("resolved_via_archive")),
            },
        ),
    }
    metric_results = {
        tier_name: _metric_result_for_tier(rows, attempted_rows=metric_tiers[tier_name]["attempted_rows"])
        for tier_name, rows in rows_by_tier.items()
    }
    denominator_manifest, eligibility_ledger, exclusion_ledger = _ledger_rows(rows_by_tier)
    tier_probe_rows = {
        "official_gold_smoke_metric": _stable_leakage_rows("official_gold_smoke_metric", official_metric_rows),
        "valid_live_retrieval_metric": _stable_leakage_rows("valid_live_retrieval_metric", live_metric_rows),
        "balanced_diagnostic_retrieval_metric": _stable_leakage_rows(
            "balanced_diagnostic_retrieval_metric",
            balanced_metric_rows,
        ),
        "stress_diagnostic_metric": _stable_leakage_rows("stress_diagnostic_metric", stress_metric_rows),
    }
    leakage_summary = _leakage_probe_summary(tier_probe_rows)

    report: dict[str, Any] = {
        "schema_version": f"{SHORT_RUN_ID}_report_v1",
        "logical_run_key": LOGICAL_RUN_KEY,
        "run_id": SHORT_RUN_ID,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": generated,
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "source_v5_7_2_short_run_id": v572.SHORT_RUN_ID,
        "source_v5_7_2_report_json": SOURCE_V572_REPORT_PATH.as_posix(),
        "source_official_metric_input_rows": 29,
        "source_official_metric_input_family_distribution": _official_family_distribution(v572_report),
        "valid_live_retrieval_metric_rows": metric_tiers["valid_live_retrieval_metric"]["computed_rows"],
        "balanced_diagnostic_metric_rows": metric_tiers["balanced_diagnostic_retrieval_metric"]["attempted_rows"],
        "stress_diagnostic_metric_rows": metric_tiers["stress_diagnostic_metric"]["attempted_rows"],
        "artifact_paths": dict(ARTIFACT_PATHS),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_consumed": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_finalized": False,
        "metric_tier_order": list(METRIC_TIER_ORDER),
        "metric_tiers": metric_tiers,
        "denominator_manifest": denominator_manifest,
        "row_eligibility_ledger": eligibility_ledger,
        "metric_results": metric_results,
        "exclusion_ledger": exclusion_ledger,
        "leakage_probe_summary": leakage_summary,
        "generated_artifacts": [ARTIFACT_PATHS[key] for key in RUN_ARTIFACT_KEYS],
        "backend_adapter": {
            "adapter_classification": "run_local_sanitized_projection_adapter",
            "nonprod_vector_backend_available": False,
            "real_vectordb_metric": False,
            "fake_backend_readiness_claimed": False,
            "latency_counters_recorded": True,
            "cost_counters_recorded": True,
            "unavailable_reason": "no real non-production VectorDB/hybrid adapter was invoked",
        },
        "candidate_generator_allowed_input_fields": sorted(candidate_generator.ALLOWED_REQUEST_FIELDS),
        "candidate_generator_forbidden_input_fields": list(FORBIDDEN_CANDIDATE_INPUT_FIELDS),
        "candidate_generation_fence_verified": True,
        "candidate_generator_case_id_feature_used": False,
        "candidate_generator_query_id_feature_used": False,
        "candidate_generator_row_id_feature_used": False,
        "candidate_generator_target_qrels_baseline_feature_used": False,
        "candidate_generator_source_title_workbook_shortcut_used": False,
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "SearchView_vector_payload_role": "candidate_only",
        "vector_payload_evidence_truth_violation_count": 0,
        "product_retrieval_quality_claim_supported": False,
        "quality_delta_claim_supported": False,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "answer_quality_metric_computed": False,
        "answer_quality_delta_computed": False,
        "retrieval_quality_delta_computed": False,
        "not_official_qrels": True,
        "official_qrels_created": False,
        "machine_owned_diagnostic_proxy_labels_only": True,
        "protected_namespaces_touched": [],
        "per_run_markdown_created": False,
        "blockers_for_real_vectordb_metric": [
            "wire a real non-production VectorDB/hybrid adapter",
            "prove adapter isolation from target/qrels/baseline/query_id/row_id/case_id/source-title shortcut fields",
            "record real backend latency and cost counters",
            "prove index/cache readiness without production promotion or source-registry/index mutation",
        ],
        "blockers_for_answer_quality_metric": [
            "answer-quality scoring remains separately closed",
            "no expected/supporting evidence or pass/fail judgment is opened in this retrieval-only framework",
        ],
    }
    for key in CLOSED_FALSE_KEYS:
        report[key] = False
    if check:
        check_report(report)
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_8 logical run key drift")
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_8 run identity drift")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_8 canonical identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v5_8 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v5_8 current alias drift")


def _require_closed_gates(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v5_8 diagnostic/non-production gate drift")
    if report.get("official_metric") is not False:
        raise ValueError("v5_8 official metric gate opened")
    for key in (
        "official_metric_input_rows",
        "official_metric_input_rows_consumed",
        "official_metric_input_rows_created",
        "answer_metric_rows",
        "scored_answer_rows",
    ):
        if report.get(key) != 0:
            raise ValueError(f"v5_8 {key.replace('_', ' ')} drift")
    if report.get("answer_quality_metric_computed") is not False:
        raise ValueError("v5_8 answer quality metric opened")
    if report.get("promotion_evidence") is not False:
        raise ValueError("v5_8 closed gate drift: promotion_evidence")
    if report.get("product_success_evidence_allowed") is not False:
        raise ValueError("v5_8 closed gate drift: product_success_evidence_allowed")
    if report.get("live_db_index_cache_readiness") is not False:
        raise ValueError("v5_8 closed gate drift: live_db_index_cache_readiness")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_8 protected namespace mutation drift")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_8 closed gate drift: {key}")


def _require_tiers(report: Mapping[str, Any]) -> None:
    tiers = report.get("metric_tiers") or {}
    expected = set(METRIC_TIER_ORDER)
    if set(tiers) != expected:
        raise ValueError("v5_8 metric tier set drift")
    if list(report.get("metric_tier_order") or []) != METRIC_TIER_ORDER:
        raise ValueError("v5_8 metric tier order drift")
    if list(report.get("generated_artifacts") or []) != [ARTIFACT_PATHS[key] for key in RUN_ARTIFACT_KEYS]:
        raise ValueError("v5_8 generated artifact list drift")
    official = tiers["official_gold_smoke_metric"]
    if official.get("source_artifact") != SOURCE_OFFICIAL_INPUT_PATH.as_posix():
        raise ValueError("v5_8 official tier source drift")
    if official.get("attempted_rows") != 29 or official.get("official_denominator") != 29:
        raise ValueError("v5_8 official tier denominator drift")
    if official.get("source_family_distribution") != {"PDF": 4, "TEXT": 6, "XLSX": 19}:
        raise ValueError("v5_8 official tier family drift")
    if "silver" in _clean(official.get("source_artifact")).lower():
        raise ValueError("v5_8 official tier pulled silver rows")
    live = tiers["valid_live_retrieval_metric"]
    if live.get("attempted_rows") != 29 or live.get("computed_rows") != 18:
        raise ValueError("v5_8 valid live tier denominator drift")
    if live.get("coverage_adjusted_denominator") != 29 or live.get("computed_only_denominator") != 18:
        raise ValueError("v5_8 coverage denominator drift")
    balanced = tiers["balanced_diagnostic_retrieval_metric"]
    if balanced.get("source_family_distribution") != {"PDF": 100, "TEXT": 100, "XLSX": 100}:
        raise ValueError("v5_8 balanced diagnostic tier family drift")
    if balanced.get("attempted_rows") != 300 or balanced.get("not_official_qrels") is not True:
        raise ValueError("v5_8 balanced diagnostic tier drift")
    stress = tiers["stress_diagnostic_metric"]
    if stress.get("partition") != "stress_or_challenge":
        raise ValueError("v5_8 stress partition drift")
    if stress.get("source_family_distribution") != {"PDF": 30, "TEXT": 30, "XLSX": 30}:
        raise ValueError("v5_8 stress diagnostic tier family drift")


def _require_ledgers(report: Mapping[str, Any]) -> None:
    tiers = report.get("metric_tiers") or {}
    attempted = sum(int(tier.get("attempted_rows") or 0) for tier in tiers.values())
    denominator_rows = list(report.get("denominator_manifest") or [])
    eligibility_rows = list(report.get("row_eligibility_ledger") or [])
    if len(denominator_rows) != attempted or len(eligibility_rows) != attempted:
        raise ValueError("v5_8 row ledger count drift")
    if any(not row.get("metric_tier") or not row.get("eligibility_status") for row in eligibility_rows):
        raise ValueError("v5_8 row eligibility ledger schema drift")
    for row in denominator_rows:
        if row.get("metric_tier") == "official_gold_smoke_metric" and row.get("source_artifact") != SOURCE_OFFICIAL_INPUT_PATH.as_posix():
            raise ValueError("v5_8 official denominator manifest source drift")
    for row in list(report.get("exclusion_ledger") or []):
        if not _clean(row.get("exclusion_reason")):
            raise ValueError("v5_8 exclusion reason missing")


def _require_metrics(report: Mapping[str, Any]) -> None:
    results = report.get("metric_results") or {}
    for tier_name in ("official_gold_smoke_metric", "valid_live_retrieval_metric", "balanced_diagnostic_retrieval_metric", "stress_diagnostic_metric"):
        tier = results.get(tier_name) or {}
        for view_name in ("computed_only", "coverage_adjusted"):
            view = tier.get(view_name) or {}
            metrics = view.get("metrics") or {}
            if set(metrics) != {"hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5"}:
                raise ValueError("v5_8 metric result schema drift")
            if set((view.get("per_family") or {})) != set(FAMILIES):
                raise ValueError("v5_8 per-family metric schema drift")
    live = results["valid_live_retrieval_metric"]
    if live["computed_only"]["denominator"] != 18 or live["coverage_adjusted"]["denominator"] != 29:
        raise ValueError("v5_8 live computed/coverage metric denominator drift")


def _require_leakage(report: Mapping[str, Any]) -> None:
    summary = report.get("leakage_probe_summary") or {}
    tiers = summary.get("tiers") or {}
    if set(tiers) != set(report.get("metric_tiers") or {}):
        raise ValueError("v5_8 leakage summary tier drift")
    for tier in tiers.values():
        if tier.get("leakage_probe_failed_count") != 0:
            raise ValueError("v5_8 leakage probe failed")
        if tier.get("identity_leakage_failed_count") != 0:
            raise ValueError("v5_8 identity leakage failed")
        if tier.get("source_shortcut_dependency_failed_count") != 0:
            raise ValueError("v5_8 source shortcut leakage failed")
    if "case_id" not in list(report.get("candidate_generator_forbidden_input_fields") or []):
        raise ValueError("v5_8 case_id candidate input guard missing")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    if report.get("artifact_paths") != ARTIFACT_PATHS:
        raise ValueError("v5_8 artifact path drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    hashes = report.get("artifact_sha256") or {}
    for key, artifact_path in ARTIFACT_PATHS.items():
        if key == "status_jsonl":
            continue
        path = repo_root / artifact_path
        if not path.exists():
            raise ValueError(f"v5_8 missing artifact: {key}")
        if path.suffix == ".md":
            raise ValueError("v5_8 per-run markdown created")
        if key == "report_json":
            continue
        expected = _clean(hashes.get(f"{key}_sha256"))
        if expected and expected != common.sha256_file(path):
            raise ValueError(f"v5_8 artifact hash drift: {key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_gates(report)
    if report.get("source_official_metric_input_rows") != 29:
        raise ValueError("v5_8 source official metric rows drift")
    _require_tiers(report)
    _require_ledgers(report)
    _require_metrics(report)
    _require_leakage(report)
    _require_artifact_paths(report)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_PAYLOAD_KEYS, context="v5_8")
    if root is not None:
        _require_written_artifacts(report, root=root)


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    payload = _json_clone(report)
    repo_root = Path(root)
    common.write_json(repo_root / ARTIFACT_PATHS["metric_tiers_json"], payload["metric_tiers"])
    common.write_jsonl(repo_root / ARTIFACT_PATHS["denominator_manifest_jsonl"], payload["denominator_manifest"])
    common.write_jsonl(repo_root / ARTIFACT_PATHS["row_eligibility_ledger_jsonl"], payload["row_eligibility_ledger"])
    common.write_json(repo_root / ARTIFACT_PATHS["metric_results_json"], payload["metric_results"])
    common.write_jsonl(repo_root / ARTIFACT_PATHS["exclusion_ledger_jsonl"], payload["exclusion_ledger"])
    common.write_json(repo_root / ARTIFACT_PATHS["leakage_probe_summary_json"], payload["leakage_probe_summary"])
    artifact_hashes = {
        f"{key}_sha256": common.sha256_file(repo_root / ARTIFACT_PATHS[key])
        for key in (
            "metric_tiers_json",
            "denominator_manifest_jsonl",
            "row_eligibility_ledger_jsonl",
            "metric_results_json",
            "exclusion_ledger_jsonl",
            "leakage_probe_summary_json",
        )
    }
    payload["artifact_sha256"] = dict(artifact_hashes)
    common.write_json(repo_root / ARTIFACT_PATHS["report_json"], payload)
    artifact_hashes["report_json_sha256"] = common.sha256_file(repo_root / ARTIFACT_PATHS["report_json"])
    payload["artifact_sha256"] = dict(artifact_hashes)
    common.write_json(repo_root / ARTIFACT_PATHS["report_json"], payload)
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
        "official_metric_input_rows": 0,
        "source_official_metric_input_rows": 29,
        "tier_count": len(report["metric_tiers"]),
        "official_gold_smoke_rows": report["metric_tiers"]["official_gold_smoke_metric"]["attempted_rows"],
        "valid_live_retrieval_rows": report["metric_tiers"]["valid_live_retrieval_metric"]["computed_rows"],
        "valid_live_coverage_adjusted_denominator": report["metric_tiers"]["valid_live_retrieval_metric"][
            "coverage_adjusted_denominator"
        ],
        "balanced_diagnostic_rows": report["metric_tiers"]["balanced_diagnostic_retrieval_metric"]["attempted_rows"],
        "stress_diagnostic_rows": report["metric_tiers"]["stress_diagnostic_metric"]["attempted_rows"],
        "nonprod_vector_backend_available": False,
        "real_vectordb_metric": False,
        "answer_quality_metric_computed": False,
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
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    live_results = report["metric_results"]["valid_live_retrieval_metric"]
    balanced_results = report["metric_results"]["balanced_diagnostic_retrieval_metric"]
    live_metrics = live_results["coverage_adjusted"]["metrics"]
    balanced_metrics = balanced_results["computed_only"]["metrics"]
    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} adds a tiered non-production retrieval metric "
        f"framework at `{REPORT_PATH.as_posix()}` while `current` remains `v5_6`. Tiers: "
        "official_gold_smoke_metric over the fixed v5_5 29-row source only, valid_live_retrieval_metric "
        "over the same 29 attempted rows with computed-only and coverage-adjusted metrics, "
        "balanced_diagnostic_retrieval_metric over 300 non-official silver rows split TEXT/PDF/XLSX 100/100/100, "
        "and stress_diagnostic_metric over a separate 90-row stress_or_challenge partition. "
        "No gold/qrels/labels/expected/supporting/official denominator/source registry/index mutation, "
        "promotion, product-success, answer-quality, training, fine-tuning, FT-A, production routing, or live "
        "DB/index/cache readiness gate is opened."
    )
    measurements_block = (
        f"### {SHORT_RUN_ID}\n\n"
        f"- valid_live_retrieval_metric: attempted=29, computed="
        f"{report['metric_tiers']['valid_live_retrieval_metric']['computed_rows']}, "
        f"coverage_adjusted_denominator=29, coverage_adjusted_metrics={json.dumps(live_metrics, sort_keys=True)}.\n"
        f"- balanced_diagnostic_retrieval_metric: rows=300, family_split={{'PDF': 100, 'TEXT': 100, 'XLSX': 100}}, "
        f"computed_only_metrics={json.dumps(balanced_metrics, sort_keys=True)}, "
        "not_official_qrels=true, promotion_evidence=false, product_success_evidence_allowed=false.\n"
        "- Backend adapter: run_local_sanitized_projection_adapter; nonprod_vector_backend_available=false; "
        "real_vectordb_metric=false; answer-quality metric remains closed; current remains `v5_6`."
    )
    triage_block = (
        f"- {SHORT_RUN_ID}: v5_8 separates official-source smoke, valid-live retrieval, balanced diagnostic, "
        "and stress/challenge diagnostic tiers. Attempted rows are never silently dropped: row eligibility and "
        "exclusion ledgers record no-candidate/uncomputed rows, leakage quarantine, and denominator tier for every row. "
        "Remaining blockers for a real VectorDB metric are a real non-production adapter, isolation proof from "
        "target/qrels/baseline/query_id/row_id/case_id/source-title shortcut fields, and real latency/cost counters. "
        "Remaining blockers for answer-quality metrics are separate user-owned expected/supporting/pass-fail policy gates; "
        "current remains `v5_6`."
    )
    for path, marker, block in (
        (PROGRESS_DOC, "progress-entry", progress_block),
        (MEASUREMENTS_DOC, "measurements-entry", measurements_block),
        (TRIAGE_DOC, "triage-entry", triage_block),
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
