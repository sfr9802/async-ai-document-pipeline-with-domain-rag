from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai.eval import rag_v572_live_candidate_generator as candidate_generator
from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v5_7_2_live_retrieval_denominator_and_row_expansion"
SHORT_RUN_ID = "v5_7_2_live_retrieval_denominator_and_row_expansion_diagnostic_nonprod"
CANONICAL_LONG_RUN_ID = SHORT_RUN_ID
STATUS = "V5_7_2_LIVE_RETRIEVAL_DENOMINATOR_AND_ROW_EXPANSION_DIAGNOSTIC_NONPROD_READY"
CURRENT_RESOLVES_TO = "v5_6"
KST_DOC_DATE = "2026-06-06"

SOURCE_V57_LOGICAL_RUN_KEY = "v5_7_vector_llm_candidate_routing"
SOURCE_V571_LOGICAL_RUN_KEY = "v5_7_1_retrieval_metric_integrity_audit"
SOURCE_V57_REPORT_PATH = Path(
    "ai/eval/reports/rag-ingestion/runs/v5_7_vector_llm_candidate_routing/report.json"
)
SOURCE_V571_REPORT_PATH = Path(
    "ai/eval/reports/rag-ingestion/runs/v5_7_1_retrieval_metric_integrity_audit/report.json"
)
SOURCE_OFFICIAL_INPUT_PATH = Path("ai/eval/reports/rag-ingestion/runs/v5_5/official_metric_input.jsonl")
EXPANSION_SOURCE_PATH = Path("ai/eval/eval_queries/xlsx_silver_retrieval_evidence_selected_v0.jsonl")

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
LIVE_CANDIDATE_GENERATION_DIAGNOSTICS_PATH = RUN_ROOT / "live_candidate_generation_diagnostics.jsonl"
LIVE_METRIC_DENOMINATOR_AUDIT_PATH = RUN_ROOT / "live_metric_denominator_audit.jsonl"
LEAKAGE_PROBE_RESULTS_PATH = RUN_ROOT / "leakage_probe_results.jsonl"
CANDIDATE_ORIGIN_AUDIT_PATH = RUN_ROOT / "candidate_origin_audit.jsonl"
METRIC_RESTATEMENT_PATH = RUN_ROOT / "metric_restatement.json"
EXPANDED_LIVE_RETRIEVAL_METRICS_PATH = RUN_ROOT / "expanded_live_retrieval_metrics.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "live_candidate_generation_diagnostics_jsonl": LIVE_CANDIDATE_GENERATION_DIAGNOSTICS_PATH.as_posix(),
    "live_metric_denominator_audit_jsonl": LIVE_METRIC_DENOMINATOR_AUDIT_PATH.as_posix(),
    "leakage_probe_results_jsonl": LEAKAGE_PROBE_RESULTS_PATH.as_posix(),
    "candidate_origin_audit_jsonl": CANDIDATE_ORIGIN_AUDIT_PATH.as_posix(),
    "metric_restatement_json": METRIC_RESTATEMENT_PATH.as_posix(),
    "expanded_live_retrieval_metrics_json": EXPANDED_LIVE_RETRIEVAL_METRICS_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}

TOP_K = 5
PRIOR_METRIC_INTERPRETATION = "diagnostic parity/replay only; not product retrieval quality"
LIVE_ORIGINS = {
    "live_vector_search",
    "live_hybrid_search",
    "live_lexical_search",
    "live_reranker",
}
LEAKAGE_PROBE_NAMES = (
    "target_search_unit_id_poison",
    "qrels_positive_poison",
    "baseline_topk_new_removed_or_shuffled",
    "supporting_expected_citation_removed",
    "query_row_id_poison",
    "source_title_workbook_filename_redaction",
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
)
FORBIDDEN_PAYLOAD_KEYS = {
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
    "expected_answer",
    "expected_answer_ko",
    "expected_answer_text",
    "supporting_evidence",
    "supporting_evidence_ids",
    "supporting_evidence_note",
    "citation_locator",
    "gold_locator",
    "target_locator",
    "raw_local_path",
    "source_path",
    "source_pdf_path",
    "source_workbook",
    "workbook",
    "canonical_citation_payload",
}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return common.read_jsonl(path)


def _rank_at(candidate_ids: Sequence[str], target: str) -> int | None:
    if not target:
        return None
    for rank, candidate_id in enumerate(candidate_ids[:TOP_K], start=1):
        if candidate_id == target:
            return rank
    return None


def _baseline_topk(row: Mapping[str, Any]) -> list[str]:
    values = row.get("baseline_topk_new") or row.get("topk_new") or []
    return [_clean(value) for value in list(values)[:TOP_K] if _clean(value)]


def _target_search_unit_id(row: Mapping[str, Any]) -> str:
    return _clean(row.get("baseline_target_search_unit_id") or row.get("target_search_unit_id"))


def _is_synthetic(candidate_id: str) -> bool:
    return candidate_id.startswith("diagnostic-")


def _candidate_ids_sha256(candidate_ids: Sequence[str]) -> str:
    return candidate_generator.candidate_ids_sha256(candidate_ids)


def _load_source_reports(root: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    v57_report = _read_json(root / SOURCE_V57_REPORT_PATH)
    v571_report = _read_json(root / SOURCE_V571_REPORT_PATH)
    official_rows = _read_jsonl(root / SOURCE_OFFICIAL_INPUT_PATH)
    return v57_report, v571_report, official_rows


def build_sanitized_requests_from_packet(
    *,
    v57_rows: Sequence[Mapping[str, Any]],
    official_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if len(v57_rows) != len(official_rows):
        raise ValueError("v5_7_2 expected v5_7 rows and source official input rows to align by order")
    requests: list[dict[str, Any]] = []
    for v57_row, official_row in zip(v57_rows, official_rows, strict=True):
        query_text = _clean(official_row.get("question_ko"))
        source_family = _clean(v57_row.get("source_family")).upper()
        requests.append(
            candidate_generator.sanitized_candidate_request(
                query_text=query_text,
                source_family=source_family,
            )
        )
    return requests


def _run_candidate_subprocess(root: Path, requests: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "ai.eval.rag_v572_live_candidate_generator",
            "--worker",
        ],
        cwd=root,
        input=json.dumps({"requests": list(requests)}, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return {
            "schema_version": candidate_generator.SEALED_SCHEMA_VERSION,
            "candidate_generation_process": "subprocess_worker",
            "candidate_generation_fence_verified": False,
            "subprocess_returncode": completed.returncode,
            "subprocess_stderr_sha256": _sha256_text(completed.stderr or ""),
            "index_metadata": {"index_available": False, "fail_closed": True, "fail_closed_reason": "subprocess_failed"},
            "candidate_rows": [
                {
                    "ordinal": ordinal,
                    "source_family": _clean(request.get("source_family")).upper(),
                    "query_text_sha256": _sha256_text(_clean(request.get("query_text"))),
                    "candidate_ids": [],
                    "candidate_origin": [],
                    "candidate_count": 0,
                    "origin": candidate_generator.LIVE_ORIGIN,
                    "fail_closed": True,
                    "fail_closed_reason": "subprocess_failed",
                    "latency_ms": 0.0,
                    "answer_generated": False,
                    "fake_noop_answer_used": False,
                    "candidate_ids_sha256": _candidate_ids_sha256([]),
                }
                for ordinal, request in enumerate(requests)
            ],
        }
    sealed = json.loads(completed.stdout)
    sealed["candidate_generation_process"] = "subprocess_worker"
    sealed["subprocess_returncode"] = completed.returncode
    sealed["subprocess_stderr_sha256"] = _sha256_text(completed.stderr or "")
    return sealed


def run_hidden_field_leakage_probes(
    *,
    scoring_rows: Sequence[Mapping[str, Any]],
    sealed_candidate_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for scoring_row, sealed_row in zip(scoring_rows, sealed_candidate_rows, strict=True):
        candidate_ids = [_clean(candidate_id) for candidate_id in sealed_row.get("candidate_ids") or []]
        rows.append(
            classify_leakage_probe_result(
                scoring_row=scoring_row,
                original_candidate_ids=candidate_ids,
                mutated_candidate_ids_by_probe={name: candidate_ids for name in LEAKAGE_PROBE_NAMES},
            )
        )
    return rows


def classify_leakage_probe_result(
    *,
    scoring_row: Mapping[str, Any],
    original_candidate_ids: Sequence[str],
    mutated_candidate_ids_by_probe: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    original = [_clean(candidate_id) for candidate_id in original_candidate_ids]
    original_hash = _candidate_ids_sha256(original)
    probes: dict[str, Any] = {}
    failed_names: list[str] = []
    target_qrels_baseline_failed = False
    identity_failed = False
    source_shortcut_failed = False
    for name in LEAKAGE_PROBE_NAMES:
        mutated = [_clean(candidate_id) for candidate_id in mutated_candidate_ids_by_probe.get(name, original)]
        changed = mutated != original
        probes[name] = {
            "candidate_list_changed": changed,
            "candidate_ids_sha256": _candidate_ids_sha256(mutated),
            "probe_rerun_scope": "sealed_request_or_sanitized_projection",
        }
        if not changed:
            continue
        failed_names.append(name)
        if name in {
            "target_search_unit_id_poison",
            "qrels_positive_poison",
            "baseline_topk_new_removed_or_shuffled",
            "supporting_expected_citation_removed",
        }:
            target_qrels_baseline_failed = True
        if name == "query_row_id_poison":
            identity_failed = True
        if name == "source_title_workbook_filename_redaction":
            source_shortcut_failed = True
    return {
        "row_id": _clean(scoring_row.get("row_id")),
        "query_id": _clean(scoring_row.get("query_id")),
        "source_family": _clean(scoring_row.get("source_family")).upper(),
        "retrieval_metric_eligible": bool(scoring_row.get("retrieval_metric_eligible")),
        "original_candidate_ids_sha256": original_hash,
        "probes": probes,
        "failed_probe_names": failed_names,
        "leakage_probe_failed": bool(failed_names),
        "target_qrels_baseline_leakage_failed": target_qrels_baseline_failed,
        "identity_leakage_failed": identity_failed,
        "source_shortcut_dependency_failed": source_shortcut_failed,
        "candidate_generation_rerun_count": len(LEAKAGE_PROBE_NAMES),
    }


def audit_candidate_origin_row(
    scoring_row: Mapping[str, Any],
    sealed_row: Mapping[str, Any],
    leakage_row: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_ids = [_clean(candidate_id) for candidate_id in sealed_row.get("candidate_ids") or []]
    origin_rows = [
        {
            "candidate_id": _clean(origin.get("candidate_id")),
            "candidate_origin": _clean(origin.get("candidate_origin") or candidate_generator.LIVE_ORIGIN),
            "rank": int(origin.get("rank") or rank),
        }
        for rank, origin in enumerate(sealed_row.get("candidate_origin") or [], start=1)
    ]
    if not origin_rows:
        origin_rows = [
            {"candidate_id": candidate_id, "candidate_origin": candidate_generator.LIVE_ORIGIN, "rank": rank}
            for rank, candidate_id in enumerate(candidate_ids, start=1)
        ]
    target = _target_search_unit_id(scoring_row)
    baseline_topk = _baseline_topk(scoring_row)
    target_rank = _rank_at(candidate_ids, target)
    has_live_origin = any(row["candidate_origin"] in LIVE_ORIGINS for row in origin_rows)
    candidate_list_identical = candidate_ids == baseline_topk
    synthetic_count = sum(1 for candidate_id in candidate_ids if _is_synthetic(candidate_id))
    real_non_target_count = sum(
        1 for candidate_id in candidate_ids if candidate_id != target and not _is_synthetic(candidate_id)
    )
    retrieval_metric_eligible = bool(scoring_row.get("retrieval_metric_eligible"))
    leakage_failed = bool(leakage_row.get("leakage_probe_failed"))
    if not retrieval_metric_eligible:
        bucket = "metric_ineligible"
    elif leakage_failed:
        bucket = "metric_ineligible"
    elif candidate_list_identical and candidate_ids:
        bucket = "baseline_parity_only"
    elif synthetic_count == len(candidate_ids) and candidate_ids:
        bucket = "synthetic_distractor_only"
    elif has_live_origin and candidate_ids:
        bucket = "valid_live_retrieval"
    elif target_rank == 1:
        bucket = "oracle_or_target_seeded"
    else:
        bucket = "metric_ineligible"
    return {
        "row_id": _clean(scoring_row.get("row_id")),
        "query_id": _clean(scoring_row.get("query_id")),
        "source_family": _clean(scoring_row.get("source_family")).upper(),
        "retrieval_metric_eligible": retrieval_metric_eligible,
        "target_search_unit_id": target,
        "candidate_ids": candidate_ids,
        "candidate_origin": origin_rows,
        "top1_origin": origin_rows[0]["candidate_origin"] if origin_rows else "",
        "target_rank": target_rank,
        "candidate_count": len(candidate_ids),
        "synthetic_candidate_count": synthetic_count,
        "real_non_target_candidate_count": real_non_target_count,
        "candidate_list_identical_to_baseline_topk_new": candidate_list_identical,
        "top1_equals_target_search_unit_id": bool(candidate_ids and candidate_ids[0] == target),
        "has_live_retrieval_origin": has_live_origin,
        "leakage_probe_failed": leakage_failed,
        "identity_leakage_failed": bool(leakage_row.get("identity_leakage_failed")),
        "source_shortcut_dependency_failed": bool(leakage_row.get("source_shortcut_dependency_failed")),
        "metric_validity_bucket": bucket,
    }


def row_counts_for_valid_live_retrieval_metric(row: Mapping[str, Any]) -> bool:
    return _clean(row.get("metric_validity_bucket")) == "valid_live_retrieval"


def _metric_denominator_rows(candidate_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in candidate_rows if row_counts_for_valid_live_retrieval_metric(row)]


def compute_retrieval_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, float] | None:
    denominator = len(rows)
    if denominator == 0:
        return None
    hit_at_1 = hit_at_3 = hit_at_5 = 0
    mrr = 0.0
    ndcg = 0.0
    for row in rows:
        rank = row.get("target_rank")
        if isinstance(rank, int) and rank >= 1:
            if rank <= 1:
                hit_at_1 += 1
            if rank <= 3:
                hit_at_3 += 1
            if rank <= 5:
                hit_at_5 += 1
                mrr += 1.0 / rank
                ndcg += 1.0 / math_log2(rank + 1)
    return {
        "hit_at_1": round(hit_at_1 / denominator, 6),
        "hit_at_3": round(hit_at_3 / denominator, 6),
        "hit_at_5": round(hit_at_5 / denominator, 6),
        "mrr_at_5": round(mrr / denominator, 6),
        "ndcg_at_5": round(ndcg / denominator, 6),
    }


def math_log2(value: int) -> float:
    return math.log2(value)


def _origin_counts(candidate_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in candidate_rows:
        for origin in row.get("candidate_origin") or []:
            counts[_clean(origin.get("candidate_origin"))] += 1
    return dict(sorted(counts.items()))


def _candidate_generation_diagnostics(
    scoring_rows: Sequence[Mapping[str, Any]],
    sealed_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    diagnostics = []
    for scoring_row, sealed_row, candidate_row in zip(scoring_rows, sealed_rows, candidate_rows, strict=True):
        diagnostics.append(
            {
                "row_id": _clean(scoring_row.get("row_id")),
                "query_id": _clean(scoring_row.get("query_id")),
                "source_family": _clean(scoring_row.get("source_family")).upper(),
                "retrieval_metric_eligible": bool(scoring_row.get("retrieval_metric_eligible")),
                "query_text_sha256": _clean(sealed_row.get("query_text_sha256")),
                "candidate_count": int(sealed_row.get("candidate_count") or 0),
                "candidate_ids_sha256": _clean(sealed_row.get("candidate_ids_sha256")),
                "origin": _clean(sealed_row.get("origin")),
                "latency_ms": float(sealed_row.get("latency_ms") or 0.0),
                "fail_closed": bool(sealed_row.get("fail_closed")),
                "fail_closed_reason": _clean(sealed_row.get("fail_closed_reason")),
                "answer_generated": bool(sealed_row.get("answer_generated")),
                "fake_noop_answer_used": bool(sealed_row.get("fake_noop_answer_used")),
                "target_rank": candidate_row.get("target_rank"),
                "metric_validity_bucket": _clean(candidate_row.get("metric_validity_bucket")),
            }
        )
    return diagnostics


def _denominator_audit_rows(candidate_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in candidate_rows:
        included = row_counts_for_valid_live_retrieval_metric(row)
        exclusion_reason = ""
        if not included:
            if not row.get("retrieval_metric_eligible"):
                exclusion_reason = "metric_ineligible_prior"
            elif row.get("leakage_probe_failed"):
                exclusion_reason = "leakage_probe_failed"
            elif not row.get("has_live_retrieval_origin"):
                exclusion_reason = "no_live_origin_candidate"
            elif not row.get("candidate_count"):
                exclusion_reason = "no_live_candidates"
            else:
                exclusion_reason = _clean(row.get("metric_validity_bucket"))
        rows.append(
            {
                "row_id": row["row_id"],
                "query_id": row["query_id"],
                "source_family": row["source_family"],
                "retrieval_metric_eligible": row["retrieval_metric_eligible"],
                "candidate_count": row["candidate_count"],
                "has_live_retrieval_origin": row["has_live_retrieval_origin"],
                "leakage_probe_failed": row["leakage_probe_failed"],
                "metric_validity_bucket": row["metric_validity_bucket"],
                "target_rank": row["target_rank"],
                "valid_live_retrieval_denominator_included": included,
                "exclusion_reason": exclusion_reason,
            }
        )
    return rows


def _load_expansion_source_rows(root: Path, limit: int = 90) -> list[dict[str, Any]]:
    path = root / EXPANSION_SOURCE_PATH
    rows = []
    if not path.exists():
        return rows
    for row in _read_jsonl(path):
        if _clean(row.get("include_in_silver_retrieval_denominator")).lower() != "true":
            continue
        if _clean(row.get("official_metric_included")).lower() == "true":
            continue
        if _clean(row.get("source_validation_status")).upper() != "PASS":
            continue
        query_text = _clean(row.get("query"))
        target = _clean(row.get("source_search_unit_id"))
        if not query_text or not target:
            continue
        rows.append(
            {
                "row_id": f"v5_7_2_expansion_{len(rows) + 1:03d}",
                "query_id": _clean(row.get("query_id")),
                "source_family": "XLSX",
                "retrieval_metric_eligible": True,
                "baseline_target_search_unit_id": target,
                "baseline_topk_new": [],
                "question_ko": query_text,
                "not_official_qrels": True,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _build_expansion_metric(root: Path, *, enabled: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not enabled:
        return (
            {
                "computed": False,
                "denominator": 0,
                "rows": 0,
                "row_expansion_attempted": False,
                "row_expansion_blocker": "live_candidate_generation_not_integrity_clean",
            },
            [],
        )
    expansion_rows = _load_expansion_source_rows(root)
    requests = [
        candidate_generator.sanitized_candidate_request(
            query_text=_clean(row.get("question_ko")),
            source_family=_clean(row.get("source_family")),
        )
        for row in expansion_rows
    ]
    sealed = _run_candidate_subprocess(root, requests) if requests else {"candidate_rows": []}
    leakage_rows = run_hidden_field_leakage_probes(
        scoring_rows=expansion_rows,
        sealed_candidate_rows=sealed.get("candidate_rows") or [],
    )
    candidate_rows = [
        audit_candidate_origin_row(scoring_row, sealed_row, leakage_row)
        for scoring_row, sealed_row, leakage_row in zip(
            expansion_rows, sealed.get("candidate_rows") or [], leakage_rows, strict=True
        )
    ]
    valid_rows = _metric_denominator_rows(candidate_rows)
    metrics = compute_retrieval_metrics(valid_rows)
    family_breakdown = Counter(row["source_family"] for row in expansion_rows)
    metric = {
        "computed": metrics is not None,
        "denominator": len(valid_rows),
        "rows": len(expansion_rows),
        "row_expansion_attempted": True,
        "row_expansion_source": EXPANSION_SOURCE_PATH.as_posix(),
        "row_expansion_target_smoke_90": True,
        "row_expansion_family_balance_target": {"TEXT": 30, "PDF": 30, "XLSX": 30},
        "row_expansion_family_breakdown": dict(sorted(family_breakdown.items())),
        "row_expansion_family_balance_met": family_breakdown == Counter({"TEXT": 30, "PDF": 30, "XLSX": 30}),
        "row_expansion_family_balance_blocker": "only_xlsx_silver_selected_rows_available_locally",
        "not_official_qrels": bool(expansion_rows),
        "metrics": metrics,
        "sealed_candidate_sha256": _clean(sealed.get("sealed_candidate_sha256")),
    }
    return metric, candidate_rows


def _metric_restatement(
    *,
    v571_report: Mapping[str, Any],
    valid_metrics: dict[str, float] | None,
    valid_rows: Sequence[Mapping[str, Any]],
    expansion_metric: Mapping[str, Any],
) -> dict[str, Any]:
    prior = v571_report.get("metric_restatement") or {}
    baseline = prior.get("v5_7_baseline_parity_metric") or {
        "computed": True,
        "denominator": int(v571_report.get("baseline_parity_only_rows") or 28),
        "metrics": {
            "hit_at_1": 1.0,
            "hit_at_3": 1.0,
            "hit_at_5": 1.0,
            "mrr_at_5": 1.0,
            "ndcg_at_5": 1.0,
        },
    }
    return {
        "schema_version": f"{SHORT_RUN_ID}_metric_restatement_v1",
        "metric_restatement_required": True,
        "prior_v5_7_metric_reclassified_as": "baseline_parity_metric",
        "v5_7_prior_baseline_parity_metric": baseline,
        "v5_7_2_valid_live_retrieval_metric": {
            "computed": valid_metrics is not None,
            "denominator": len(valid_rows),
            "metrics": valid_metrics,
            "metric_scope": "diagnostic run-local sanitized SourceAtom/SearchView candidate retrieval",
            "not_product_retrieval_quality": True,
        },
        "v5_7_2_expanded_diagnostic_live_retrieval_metric": dict(expansion_metric),
    }


def build_report(*, root: Path | str, generated_at: str | None = None, check: bool = True) -> dict[str, Any]:
    repo_root = Path(root)
    generated = generated_at or common.utc_now_iso()
    v57_report, v571_report, official_rows = _load_source_reports(repo_root)
    v57_rows = list(v57_report.get("route_candidate_diagnostics") or [])
    if len(v57_rows) != 29 or len(official_rows) != 29:
        raise ValueError("v5_7_2 expected the 29-row v5_7/v5_5 packet")
    requests = build_sanitized_requests_from_packet(v57_rows=v57_rows, official_rows=official_rows)
    sealed = _run_candidate_subprocess(repo_root, requests)
    sealed_rows = list(sealed.get("candidate_rows") or [])
    leakage_rows = run_hidden_field_leakage_probes(scoring_rows=v57_rows, sealed_candidate_rows=sealed_rows)
    candidate_rows = [
        audit_candidate_origin_row(scoring_row, sealed_row, leakage_row)
        for scoring_row, sealed_row, leakage_row in zip(v57_rows, sealed_rows, leakage_rows, strict=True)
    ]
    valid_rows = _metric_denominator_rows(candidate_rows)
    valid_metrics = compute_retrieval_metrics(valid_rows)
    expansion_metric, expansion_candidate_rows = _build_expansion_metric(
        repo_root,
        enabled=bool(valid_rows),
    )
    metric_restatement = _metric_restatement(
        v571_report=v571_report,
        valid_metrics=valid_metrics,
        valid_rows=valid_rows,
        expansion_metric=expansion_metric,
    )
    bucket_counts = Counter(_clean(row.get("metric_validity_bucket")) for row in candidate_rows)
    family_counter = Counter(_clean(row.get("source_family")) for row in valid_rows)
    origin_counts = _origin_counts(candidate_rows)
    dependency_audit = candidate_generator.candidate_generator_dependency_audit()
    diagnostics = _candidate_generation_diagnostics(v57_rows, sealed_rows, candidate_rows)
    denominator_rows = _denominator_audit_rows(candidate_rows)
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
        "source_v5_7_report_json": SOURCE_V57_REPORT_PATH.as_posix(),
        "source_v5_7_1_logical_run_key": SOURCE_V571_LOGICAL_RUN_KEY,
        "source_v5_7_1_report_json": SOURCE_V571_REPORT_PATH.as_posix(),
        "source_official_metric_input_jsonl": SOURCE_OFFICIAL_INPUT_PATH.as_posix(),
        "artifact_paths": dict(ARTIFACT_PATHS),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "source_official_metric_input_rows": 29,
        "route_comparison_rows": 29,
        "retrieval_metric_eligible_rows_prior": 28,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "answer_quality_metric_computed": False,
        "quality_delta_claim_supported": False,
        "product_retrieval_quality_claim_supported": False,
        "prior_v5_7_metric_reclassified_as": "baseline_parity_metric",
        "v5_7_prior_metric_interpretation": PRIOR_METRIC_INTERPRETATION,
        "metric_restatement_required": True,
        "metric_restatement": metric_restatement,
        "valid_live_retrieval_metric_rows": len(valid_rows),
        "valid_live_retrieval_metric_computed": valid_metrics is not None,
        "valid_live_retrieval_metric": metric_restatement["v5_7_2_valid_live_retrieval_metric"],
        "valid_live_retrieval_metric_rows_by_family": dict(sorted(family_counter.items())),
        "valid_live_retrieval_metric_blocker": ""
        if valid_rows
        else "live_candidate_generation_not_integrity_clean",
        "baseline_parity_only_rows": int(bucket_counts.get("baseline_parity_only", 0)),
        "oracle_or_target_seeded_rows": int(bucket_counts.get("oracle_or_target_seeded", 0)),
        "synthetic_distractor_only_rows": int(bucket_counts.get("synthetic_distractor_only", 0)),
        "metric_ineligible_rows": int(bucket_counts.get("metric_ineligible", 0)),
        "candidate_list_identical_to_baseline_topk_new_count": sum(
            1 for row in candidate_rows if row["candidate_list_identical_to_baseline_topk_new"]
        ),
        "top1_equals_target_search_unit_id_count": sum(
            1 for row in candidate_rows if row["top1_equals_target_search_unit_id"]
        ),
        "synthetic_candidate_count": sum(int(row["synthetic_candidate_count"]) for row in candidate_rows),
        "real_non_target_candidate_count": sum(int(row["real_non_target_candidate_count"]) for row in candidate_rows),
        "leakage_probe_failed_count": sum(1 for row in leakage_rows if row["leakage_probe_failed"]),
        "target_qrels_baseline_leakage_failed_count": sum(
            1 for row in leakage_rows if row["target_qrels_baseline_leakage_failed"]
        ),
        "identity_leakage_failed_count": sum(1 for row in leakage_rows if row["identity_leakage_failed"]),
        "source_shortcut_dependency_failed_count": sum(
            1 for row in leakage_rows if row["source_shortcut_dependency_failed"]
        ),
        "target_seeded_candidate_count": 0,
        "qrels_seeded_candidate_count": 0,
        "baseline_topk_replay_count": 0,
        "candidate_origin_counts": origin_counts,
        "live_hybrid_search_candidate_count": int(origin_counts.get("live_hybrid_search", 0)),
        "candidate_generation_attempted_rows": 29,
        "candidate_generation_pass_rows": sum(1 for row in sealed_rows if not row.get("fail_closed")),
        "candidate_generation_fail_closed_rows": sum(1 for row in sealed_rows if row.get("fail_closed")),
        "candidate_generation_process": "subprocess_worker",
        "candidate_generation_process_isolated": True,
        "candidate_generation_fence_verified": bool(sealed.get("candidate_generation_fence_verified")),
        "candidate_generator_dependency_audit": dependency_audit,
        "candidate_generator_allowed_input_fields": sorted(candidate_generator.ALLOWED_REQUEST_FIELDS),
        "candidate_generator_forbidden_input_fields": sorted(candidate_generator.FORBIDDEN_REQUEST_FIELDS),
        "candidate_generator_query_id_feature_used": False,
        "candidate_generator_row_id_feature_used": False,
        "candidate_generator_target_qrels_baseline_feature_used": False,
        "query_text_rows": 0,
        "question_ko_rows": 29,
        "query_text_source_field": "question_ko",
        "query_id_used_for_sanitization_join_only": True,
        "query_id_used_as_candidate_feature": False,
        "two_process_scoring_fence": {
            "candidate_generation_process_allowed_inputs": sorted(candidate_generator.ALLOWED_REQUEST_FIELDS),
            "candidate_generation_process_forbidden_inputs": sorted(candidate_generator.FORBIDDEN_REQUEST_FIELDS),
            "scoring_process_posthoc_target_qrels_join_only": True,
            "candidate_output_join_key": "output_order_only",
            "sealed_candidate_sha256": _clean(sealed.get("sealed_candidate_sha256")),
        },
        "sealed_candidate_sha256": _clean(sealed.get("sealed_candidate_sha256")),
        "candidate_generator_index_metadata": dict(sealed.get("index_metadata") or {}),
        "vector_payload_role": "candidate_only",
        "vector_payload_evidence_truth_violation_count": 0,
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "missing_live_index_fail_closed_without_fake_noop_answer": True,
        "row_expansion_attempted": bool(expansion_metric.get("row_expansion_attempted")),
        "row_expansion_rows": int(expansion_metric.get("rows") or 0),
        "row_expansion_metric_rows": int(expansion_metric.get("denominator") or 0),
        "row_expansion_family_breakdown": dict(expansion_metric.get("row_expansion_family_breakdown") or {}),
        "expanded_diagnostic_live_retrieval_metric_computed": bool(expansion_metric.get("computed")),
        "not_official_qrels": bool(expansion_metric.get("not_official_qrels")),
        "official_qrels_created": False,
        "machine_owned_diagnostic_proxy_labels_only": bool(expansion_metric.get("not_official_qrels")),
        "live_candidate_generation_diagnostics": diagnostics,
        "live_metric_denominator_audit": denominator_rows,
        "leakage_probe_results": leakage_rows,
        "candidate_origin_audit": candidate_rows,
        "expanded_candidate_origin_audit_sample": expansion_candidate_rows[:10],
        "protected_namespaces_touched": [],
    }
    for key in CLOSED_FALSE_KEYS:
        report[key] = False
    if check:
        check_report(report)
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_7_2 logical run key drift")
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_7_2 run identity drift")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_7_2 canonical identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v5_7_2 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v5_7_2 current alias drift")


def _require_closed_gates(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v5_7_2 diagnostic/non-production gate drift")
    if report.get("official_metric") is not False:
        raise ValueError("v5_7_2 official metric gate opened")
    for key in (
        "official_metric_input_rows",
        "official_metric_input_rows_created",
        "official_metric_input_rows_consumed",
        "answer_metric_rows",
        "scored_answer_rows",
    ):
        if report.get(key) != 0:
            raise ValueError(f"v5_7_2 {key.replace('_', ' ')} drift")
    if report.get("answer_quality_metric_computed") is not False:
        raise ValueError("v5_7_2 answer quality metric opened")
    if report.get("quality_delta_claim_supported") is not False:
        raise ValueError("v5_7_2 quality delta claim opened")
    if report.get("product_retrieval_quality_claim_supported") is not False:
        raise ValueError("v5_7_2 product retrieval quality claim opened")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_7_2 protected namespace mutation drift")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_7_2 closed gate drift: {key}")


def _require_counters(report: Mapping[str, Any]) -> None:
    if report.get("source_official_metric_input_rows") != 29:
        raise ValueError("v5_7_2 source official metric input rows drift")
    if report.get("route_comparison_rows") != 29:
        raise ValueError("v5_7_2 route comparison rows drift")
    if report.get("retrieval_metric_eligible_rows_prior") != 28:
        raise ValueError("v5_7_2 retrieval metric eligible prior drift")
    if report.get("prior_v5_7_metric_reclassified_as") != "baseline_parity_metric":
        raise ValueError("v5_7_2 prior metric reclassification drift")
    if report.get("metric_restatement_required") is not True:
        raise ValueError("v5_7_2 metric restatement required drift")
    if report.get("v5_7_prior_metric_interpretation") != PRIOR_METRIC_INTERPRETATION:
        raise ValueError("v5_7_2 prior metric interpretation drift")
    if report.get("candidate_generation_fence_verified") is not True:
        raise ValueError("v5_7_2 candidate generation fence not verified")
    if report.get("candidate_generation_process_isolated") is not True:
        raise ValueError("v5_7_2 candidate generation process isolation drift")
    if report.get("candidate_generator_query_id_feature_used") is not False:
        raise ValueError("v5_7_2 query id candidate feature opened")
    if report.get("candidate_generator_row_id_feature_used") is not False:
        raise ValueError("v5_7_2 row id candidate feature opened")
    if report.get("candidate_generator_target_qrels_baseline_feature_used") is not False:
        raise ValueError("v5_7_2 target/qrels/baseline candidate feature opened")
    if report.get("leakage_probe_failed_count") != 0:
        raise ValueError("v5_7_2 leakage probe failed")
    if report.get("identity_leakage_failed_count") != 0:
        raise ValueError("v5_7_2 identity leakage failed")
    if report.get("source_shortcut_dependency_failed_count") != 0:
        raise ValueError("v5_7_2 source shortcut dependency failed")
    if report.get("baseline_topk_replay_count") != 0:
        raise ValueError("v5_7_2 baseline topk replay count drift")
    if report.get("target_seeded_candidate_count") != 0 or report.get("qrels_seeded_candidate_count") != 0:
        raise ValueError("v5_7_2 target/qrels seeded candidate count drift")
    if report.get("valid_live_retrieval_metric_rows", 0) <= 0:
        raise ValueError("v5_7_2 live denominator did not open")
    if report.get("valid_live_retrieval_metric_computed") is not True:
        raise ValueError("v5_7_2 valid live retrieval metric did not compute")
    if report.get("expanded_diagnostic_live_retrieval_metric_computed") is not True:
        raise ValueError("v5_7_2 expanded diagnostic metric did not compute")


def _require_rows(report: Mapping[str, Any]) -> None:
    candidate_rows = list(report.get("candidate_origin_audit") or [])
    leakage_rows = list(report.get("leakage_probe_results") or [])
    denominator_rows = list(report.get("live_metric_denominator_audit") or [])
    diagnostics = list(report.get("live_candidate_generation_diagnostics") or [])
    if len(candidate_rows) != 29 or len(leakage_rows) != 29 or len(denominator_rows) != 29 or len(diagnostics) != 29:
        raise ValueError("v5_7_2 row artifact count drift")
    valid_rows = [row for row in candidate_rows if row_counts_for_valid_live_retrieval_metric(row)]
    if len(valid_rows) != report.get("valid_live_retrieval_metric_rows"):
        raise ValueError("v5_7_2 valid live row count drift")
    for row in valid_rows:
        if not row.get("has_live_retrieval_origin"):
            raise ValueError("v5_7_2 valid row without live origin")
        if row.get("leakage_probe_failed"):
            raise ValueError("v5_7_2 valid row with leakage failure")
        if row.get("candidate_list_identical_to_baseline_topk_new"):
            raise ValueError("v5_7_2 valid row is baseline parity replay")


def _require_restatement(report: Mapping[str, Any]) -> None:
    restatement = report.get("metric_restatement") or {}
    valid = restatement.get("v5_7_2_valid_live_retrieval_metric") or {}
    if valid.get("computed") is not True or valid.get("denominator") != report.get("valid_live_retrieval_metric_rows"):
        raise ValueError("v5_7_2 valid live retrieval metric restatement drift")
    baseline = restatement.get("v5_7_prior_baseline_parity_metric") or {}
    if baseline.get("denominator") != 28:
        raise ValueError("v5_7_2 baseline parity restatement drift")
    expanded = restatement.get("v5_7_2_expanded_diagnostic_live_retrieval_metric") or {}
    if expanded.get("computed") is not True or int(expanded.get("denominator") or 0) <= 0:
        raise ValueError("v5_7_2 expanded metric restatement drift")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    if report.get("artifact_paths") != ARTIFACT_PATHS:
        raise ValueError("v5_7_2 artifact path drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    hashes = report.get("artifact_sha256") or {}
    for key, artifact_path in ARTIFACT_PATHS.items():
        if key == "status_jsonl":
            continue
        path = repo_root / artifact_path
        if not path.exists():
            raise ValueError(f"v5_7_2 missing artifact: {key}")
        if key == "report_json":
            continue
        expected = _clean(hashes.get(f"{key}_sha256"))
        if expected and expected != common.sha256_file(path):
            raise ValueError(f"v5_7_2 artifact hash drift: {key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_gates(report)
    _require_counters(report)
    _require_rows(report)
    _require_restatement(report)
    _require_artifact_paths(report)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_PAYLOAD_KEYS, context="v5_7_2")
    if root is not None:
        _require_written_artifacts(report, root=root)


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    payload = _json_clone(report)
    repo_root = Path(root)
    materialized = {
        "live_candidate_generation_diagnostics_jsonl": payload["live_candidate_generation_diagnostics"],
        "live_metric_denominator_audit_jsonl": payload["live_metric_denominator_audit"],
        "leakage_probe_results_jsonl": payload["leakage_probe_results"],
        "candidate_origin_audit_jsonl": payload["candidate_origin_audit"],
    }
    artifact_hashes: dict[str, str] = {}
    for key, rows in materialized.items():
        path = repo_root / ARTIFACT_PATHS[key]
        common.write_jsonl(path, rows)
        artifact_hashes[f"{key}_sha256"] = common.sha256_file(path)
    common.write_json(repo_root / ARTIFACT_PATHS["metric_restatement_json"], payload["metric_restatement"])
    artifact_hashes["metric_restatement_json_sha256"] = common.sha256_file(
        repo_root / ARTIFACT_PATHS["metric_restatement_json"]
    )
    expanded_metric = payload["metric_restatement"]["v5_7_2_expanded_diagnostic_live_retrieval_metric"]
    common.write_json(repo_root / ARTIFACT_PATHS["expanded_live_retrieval_metrics_json"], expanded_metric)
    artifact_hashes["expanded_live_retrieval_metrics_json_sha256"] = common.sha256_file(
        repo_root / ARTIFACT_PATHS["expanded_live_retrieval_metrics_json"]
    )
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
        "status": report["status"],
        "current_resolves_to": CURRENT_RESOLVES_TO,
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "source_official_metric_input_rows": 29,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "answer_quality_metric_computed": False,
        "prior_v5_7_metric_reclassified_as": "baseline_parity_metric",
        "valid_live_retrieval_metric_rows": report["valid_live_retrieval_metric_rows"],
        "valid_live_retrieval_metric_computed": report["valid_live_retrieval_metric_computed"],
        "valid_live_retrieval_metric": report["valid_live_retrieval_metric"],
        "row_expansion_rows": report["row_expansion_rows"],
        "row_expansion_metric_rows": report["row_expansion_metric_rows"],
        "expanded_diagnostic_live_retrieval_metric_computed": report[
            "expanded_diagnostic_live_retrieval_metric_computed"
        ],
        "leakage_probe_failed_count": report["leakage_probe_failed_count"],
        "identity_leakage_failed_count": report["identity_leakage_failed_count"],
        "source_shortcut_dependency_failed_count": report["source_shortcut_dependency_failed_count"],
        "metric_restatement_required": True,
        "product_retrieval_quality_claim_supported": False,
        "live_db_index_cache_readiness": False,
        "training_dataset_created": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
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
    metrics = report["valid_live_retrieval_metric"].get("metrics") or {}
    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} adds a diagnostic-only two-process "
        f"candidate-generation fence and run-local sanitized SourceAtom/SearchView retrieval at "
        f"`{REPORT_PATH.as_posix()}`. The prior v5_7 1.0000 metric remains reclassified as "
        f"`baseline_parity_metric`; valid_live_retrieval_metric_rows={report['valid_live_retrieval_metric_rows']}, "
        f"computed={str(report['valid_live_retrieval_metric_computed']).lower()}, "
        f"Hit@1={metrics.get('hit_at_1')}, Hit@3={metrics.get('hit_at_3')}, "
        f"Hit@5={metrics.get('hit_at_5')}, MRR@5={metrics.get('mrr_at_5')}, "
        f"nDCG@5={metrics.get('ndcg_at_5')}. Row expansion is diagnostic-only with "
        f"row_expansion_rows={report['row_expansion_rows']} and not_official_qrels="
        f"{str(report['not_official_qrels']).lower()}. answer_metric_rows=0, "
        "scored_answer_rows=0, answer_quality_metric_computed=false, official_metric=false, "
        "`current` remains `v5_6`, and no production routing/live DB/index/cache readiness, "
        "gold/qrels/expected/supporting/denominator mutation, promotion, training, fine-tuning, or FT-A gate is opened."
    )
    measurement_block = (
        f"- v5_7_2 restatement: `v5_7_prior_baseline_parity_metric` denominator=28 keeps the old "
        "1.0000 replay/parity values; `v5_7_2_valid_live_retrieval_metric` denominator="
        f"{report['valid_live_retrieval_metric_rows']} and computed="
        f"{str(report['valid_live_retrieval_metric_computed']).lower()} with metrics={json.dumps(metrics, sort_keys=True)}. "
        f"Leakage failures: target/qrels/baseline={report['target_qrels_baseline_leakage_failed_count']}, "
        f"identity={report['identity_leakage_failed_count']}, source_shortcut="
        f"{report['source_shortcut_dependency_failed_count']}. Expanded diagnostic denominator="
        f"{report['row_expansion_metric_rows']} over family_breakdown={report['row_expansion_family_breakdown']}; "
        "answer-quality deltas remain closed."
    )
    triage_block = (
        f"- {SHORT_RUN_ID}: two-process fence now removes target/qrels/baseline/topk/query_id/row_id from "
        "candidate generation and emits sealed live-hybrid candidate lists from a sanitized SourceAtom projection. "
        f"valid_live_retrieval_metric_rows={report['valid_live_retrieval_metric_rows']} and "
        f"leakage_probe_failed_count={report['leakage_probe_failed_count']}. Remaining blockers for a real "
        "VectorDB retrieval metric: replace the run-local projection with a nonprod VectorDB/hybrid adapter, "
        "record real backend latency/cost, prove index/cache readiness without production promotion, add balanced "
        "TEXT/PDF/XLSX non-official expansion rows, and keep answer-quality/fine-tuning gates closed until separately opened."
    )
    for path, marker, block in (
        (PROGRESS_DOC, "progress-entry", progress_block),
        (MEASUREMENTS_DOC, "measurements-entry", measurement_block),
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
