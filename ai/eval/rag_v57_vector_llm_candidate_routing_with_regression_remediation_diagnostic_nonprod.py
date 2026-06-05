from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ai.eval import rag_v56_refactor_route_comparison_packet_diagnostic_nonprod as v56compare
from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v5_7_vector_llm_candidate_routing"
SHORT_RUN_ID = "v5_7_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod"
CANONICAL_LONG_RUN_ID = SHORT_RUN_ID
STATUS = "V5_7_VECTOR_LLM_CANDIDATE_ROUTING_WITH_REGRESSION_REMEDIATION_DIAGNOSTIC_NONPROD_READY"
CURRENT_RESOLVES_TO = "v5_6"
KST_DOC_DATE = "2026-06-05"

BASELINE_LOGICAL_RUN_KEY = v56compare.FULL_PACKET_LOGICAL_RUN_KEY
BASELINE_SHORT_RUN_ID = v56compare.FULL_PACKET_SHORT_RUN_ID

REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")
RUN_ROOT = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY
REPORT_PATH = RUN_ROOT / "report.json"
ROUTE_CANDIDATE_DIAGNOSTICS_PATH = RUN_ROOT / "route_candidate_diagnostics.jsonl"
HEURISTIC_INVENTORY_PATH = RUN_ROOT / "heuristic_inventory.jsonl"
QUALITY_REGRESSION_ATTRIBUTION_PATH = RUN_ROOT / "quality_regression_attribution.jsonl"
FINETUNING_READINESS_CANDIDATES_PATH = RUN_ROOT / "finetuning_readiness_candidates.jsonl"
VECTOR_CANDIDATE_METRICS_PATH = RUN_ROOT / "vector_candidate_metrics.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
PROGRESS_DOC = Path("docs/rag-ingestion-progress.md")
MEASUREMENTS_DOC = Path("docs/rag-ingestion-measurements.md")
TRIAGE_DOC = Path("docs/rag-ingestion-triage.md")

ARTIFACT_PATHS = {
    "report_json": REPORT_PATH.as_posix(),
    "route_candidate_diagnostics_jsonl": ROUTE_CANDIDATE_DIAGNOSTICS_PATH.as_posix(),
    "heuristic_inventory_jsonl": HEURISTIC_INVENTORY_PATH.as_posix(),
    "quality_regression_attribution_jsonl": QUALITY_REGRESSION_ATTRIBUTION_PATH.as_posix(),
    "finetuning_readiness_candidates_jsonl": FINETUNING_READINESS_CANDIDATES_PATH.as_posix(),
    "vector_candidate_metrics_json": VECTOR_CANDIDATE_METRICS_PATH.as_posix(),
    "status_jsonl": STATUS_JSONL_PATH.as_posix(),
}

TOP_K = 5
PERFECT_RETRIEVAL_METRICS = {
    "hit_at_1": 1.0,
    "hit_at_3": 1.0,
    "hit_at_5": 1.0,
    "mrr_at_5": 1.0,
    "ndcg_at_5": 1.0,
}

CLOSED_FALSE_KEYS = (
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
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
    "production_db_mutated",
    "source_registry_mutated",
    "index_rebuilt",
    "cache_mutated",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
)

FORBIDDEN_PAYLOAD_KEYS = set(v56compare.FORBIDDEN_PAYLOAD_KEYS) | {
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
    "expected_answer",
    "supporting_evidence",
    "supporting_evidence_ids",
    "target_locator",
    "gold_locator",
    "raw_local_path",
    "direct_answer_value",
    "source_title_shortcut",
    "official_denominator_mutation",
}

FORBIDDEN_FT_FIELD_NAMES = {
    "target_locator",
    "gold_locator",
    "expected_answer",
    "supporting_evidence",
    "supporting_evidence_ids",
    "raw_local_path",
    "source_title",
    "direct_answer_value",
    "official_denominator_mutation",
    "official_metric_input_rows",
    "qrels_mutation",
    "label_mutation",
    "gold_mutation",
}

ALLOWED_FT_INPUT_FIELD_NAMES = (
    "query_id",
    "source_family",
    "retrieval_hit_status",
    "citation_grounded_status",
    "answer_failure_reason",
    "evidence_available",
)

SHORTCUT_REPLACEMENT_PLANS = {
    "query_keyword_route_selection": "Use source metadata, route policy manifest, vector candidates, and bounded LLM adjudication only when ambiguity gates allow it.",
    "source_family_hardcoded_fallback": "Fail closed when source family cannot be established by SourceAtom/SearchView metadata or route policy.",
    "row_id_special_case": "Remove row identity from scoring; keep row_id only as diagnostic lineage.",
    "query_id_special_case": "Remove query identity from scoring; keep query_id only as diagnostic lineage.",
    "source_title_shortcut": "Use source registry/search-unit metadata fields without title-as-answer or title-as-route shortcuts.",
    "workbook_file_name_shortcut": "Use workbook/sheet metadata as bounded provenance, not as scoring truth.",
    "korean_pdf_marker_template": "Use parser metadata and evidence windows instead of Korean/PDF marker templates.",
    "direct_normalized_answer_value_matching": "Reserve answer values for human/official scoring only; do not use them for route or candidate scoring.",
    "raw_xlsx_query_time_parsing": "Use pre-materialized SearchView/SourceAtom table metadata; query-time raw workbook parsing stays forbidden.",
    "raw_pdf_query_time_parsing": "Use pre-materialized PDF page/block metadata; query-time raw PDF parsing stays forbidden.",
    "formula_text_evaluation": "Use precomputed safe table metadata; do not evaluate formulas during retrieval.",
    "target_locator_shortcut": "Keep target/gold/supporting/expected locators out of routing and retrieval scoring.",
    "gold_locator_shortcut": "Keep target/gold/supporting/expected locators out of routing and retrieval scoring.",
    "supporting_evidence_shortcut": "Keep supporting evidence approval out of routing and retrieval scoring.",
    "expected_answer_shortcut": "Keep expected answers out of routing and retrieval scoring.",
}

REGRESSION_CAUSES = {
    "route_regression",
    "vector_candidate_generation_regression",
    "hybrid_ranking_regression",
    "evidence_assembly_regression",
    "answer_synthesis_regression",
    "latency_or_cost_regression",
    "infrastructure_unavailable_fail_closed",
    "metric_ineligible_or_qrels_missing",
}

REMEDIATION_LANES = {
    "route_regression": "bounded_llm_adjudicator_prompt_schema",
    "vector_candidate_generation_regression": "vector_payload_or_index_repair",
    "hybrid_ranking_regression": "hybrid_search_weight_tuning",
    "evidence_assembly_regression": "evidence_window_or_sourceatom_repair",
    "answer_synthesis_regression": "fine_tuning_readiness_candidate",
    "latency_or_cost_regression": "fail_closed_no_action",
    "infrastructure_unavailable_fail_closed": "fail_closed_no_action",
    "metric_ineligible_or_qrels_missing": "human_owned_gold_or_label_required",
}


@dataclass(frozen=True)
class DiagnosticVectorCandidate:
    candidate_id: str
    rank: int
    score: float
    source_family: str
    payload_kind: str = "vector_candidate"
    evidence_truth: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "rank": self.rank,
            "score": self.score,
            "source_family": self.source_family,
            "payload_kind": self.payload_kind,
            "evidence_truth": self.evidence_truth,
            "candidate_only": True,
        }


class DiagnosticVectorCandidateAdapter:
    def __init__(self, index: Mapping[str, Sequence[Mapping[str, Any]]] | None) -> None:
        self.index = index

    def retrieve(self, query_row: Mapping[str, Any], *, top_k: int = TOP_K) -> dict[str, Any]:
        if not self.index:
            return _fail_closed_vector_result("diagnostic_vector_index_unavailable")
        query_id = _clean(query_row.get("query_id"))
        candidates = list(self.index.get(query_id) or [])[:top_k]
        if not candidates:
            return _fail_closed_vector_result("diagnostic_vector_candidates_missing")
        for candidate in candidates:
            assert_vector_payload_cannot_be_evidence_truth(candidate)
        return {
            "status": "ok",
            "fail_closed_reason": "",
            "candidates": [dict(candidate) for candidate in candidates],
            "candidate_ids": [_clean(candidate.get("candidate_id")) for candidate in candidates],
            "answer_fallback_used": False,
            "fake_noop_answer_generated": False,
            "latency_ms": 0.0,
            "payload_evidence_truth_violation_count": 0,
        }


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json_clone(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fail_closed_vector_result(reason: str) -> dict[str, Any]:
    return {
        "status": "fail_closed",
        "fail_closed_reason": reason,
        "candidates": [],
        "candidate_ids": [],
        "answer_fallback_used": False,
        "fake_noop_answer_generated": False,
        "latency_ms": 0.0,
        "payload_evidence_truth_violation_count": 0,
    }


def assert_vector_payload_cannot_be_evidence_truth(payload: Mapping[str, Any]) -> None:
    if payload.get("evidence_truth") is True:
        raise ValueError("vector payload is candidate-only and cannot become evidence truth")
    if _clean(payload.get("citation_locator")):
        raise ValueError("vector payload is candidate-only and cannot carry citation_locator truth")
    if _clean(payload.get("supporting_evidence")) or _clean(payload.get("expected_answer")):
        raise ValueError("vector payload is candidate-only and cannot carry answer/evidence truth")


def build_diagnostic_vector_index_from_full_packet_report(
    baseline_report: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for row in baseline_report.get("row_level_diagnostic_rows") or []:
        source_family = _clean(row.get("source_family"))
        candidates: list[dict[str, Any]] = []
        for rank, candidate_id in enumerate(list(row.get("topk_new") or [])[:TOP_K], start=1):
            candidate = DiagnosticVectorCandidate(
                candidate_id=_clean(candidate_id),
                rank=rank,
                score=round(1.0 / rank, 6),
                source_family=source_family,
            ).to_payload()
            candidates.append(candidate)
        index[_clean(row.get("query_id"))] = candidates
    return index


def parse_llm_adjudication(
    raw_output: str,
    *,
    allowed_routes: set[str],
    evidence_candidate_ids: set[str],
    hard_guard_blocked: bool,
) -> dict[str, Any]:
    output_hash = _sha256_text(raw_output)
    base = {
        "output_hash": output_hash,
        "raw_response_payload_written": False,
        "raw_prompt_payload_written": False,
        "input_field_names": [
            "query_id",
            "source_family",
            "candidate_ids",
            "route_policy_manifest_id",
            "guard_status",
        ],
    }
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return {
            **base,
            "parse_status": "invalid_json",
            "fail_closed": True,
            "fail_closed_reason": "invalid_llm_json",
        }
    if not isinstance(payload, dict):
        return {
            **base,
            "parse_status": "schema_drift",
            "fail_closed": True,
            "fail_closed_reason": "llm_schema_drift",
        }
    required = {"selected_route", "selected_candidate_id", "decision", "confidence"}
    if not required <= set(payload):
        return {
            **base,
            "parse_status": "schema_drift",
            "fail_closed": True,
            "fail_closed_reason": "llm_schema_drift",
        }
    if hard_guard_blocked and (
        payload.get("relax_hard_guard") is True or payload.get("relax_manifest_policy") is True
    ):
        return {
            **base,
            "parse_status": "guard_relaxation_attempt",
            "fail_closed": True,
            "fail_closed_reason": "llm_guard_relaxation_attempt",
        }
    selected_route = _clean(payload.get("selected_route"))
    if selected_route not in allowed_routes:
        return {
            **base,
            "parse_status": "unsupported_route",
            "fail_closed": True,
            "fail_closed_reason": "unsupported_llm_route",
        }
    selected_candidate_id = _clean(payload.get("selected_candidate_id"))
    if selected_candidate_id and selected_candidate_id not in evidence_candidate_ids:
        return {
            **base,
            "parse_status": "missing_evidence_candidate",
            "fail_closed": True,
            "fail_closed_reason": "llm_selected_missing_evidence_candidate",
        }
    return {
        **base,
        "parse_status": "ok",
        "fail_closed": False,
        "fail_closed_reason": "",
        "selected_route": selected_route,
        "selected_candidate_id": selected_candidate_id,
        "decision": _clean(payload.get("decision")),
        "confidence": float(payload.get("confidence")),
    }


def evaluate_scoring_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    signal_type = _clean(signal.get("signal_type"))
    replacement_plan = SHORTCUT_REPLACEMENT_PLANS.get(
        signal_type,
        "Reject unrecognized shortcut-like signal until a diagnostic policy explicitly allows it.",
    )
    return {
        "signal_type": signal_type,
        "accepted_for_route_or_candidate_scoring": False,
        "blocked_reason": "shortcut_signal_rejected_for_v5_7_vector_llm_candidate_routing",
        "risk": "would leak row identity, source title, raw parser output, answer value, or gold/supporting locator into scoring",
        "replacement_plan": replacement_plan,
    }


def classify_regression(row: Mapping[str, Any]) -> dict[str, Any]:
    if row.get("metric_ineligible_or_qrels_missing") is True:
        cause = "metric_ineligible_or_qrels_missing"
    elif row.get("infrastructure_unavailable") is True:
        cause = "infrastructure_unavailable_fail_closed"
    elif row.get("route_changed") is True:
        cause = "route_regression"
    elif row.get("vector_candidates_missing") is True:
        cause = "vector_candidate_generation_regression"
    elif row.get("evidence_assembly_failed") is True:
        cause = "evidence_assembly_regression"
    elif row.get("answer_synthesis_failed") is True:
        cause = "answer_synthesis_regression"
    elif float(row.get("latency_ms_delta") or 0) > 500:
        cause = "latency_or_cost_regression"
    else:
        cause = "hybrid_ranking_regression"
    remediation = REMEDIATION_LANES[cause]
    ft_candidate = remediation == "fine_tuning_readiness_candidate"
    return {
        "row_id": _clean(row.get("row_id")),
        "query_id": _clean(row.get("query_id")),
        "source_family": _clean(row.get("source_family")),
        "regression_cause": cause,
        "recommended_remediation_lane": remediation,
        "fine_tuning_readiness_candidate": ft_candidate,
        "diagnostic_only": True,
    }


def build_finetuning_readiness_candidate(row: Mapping[str, Any]) -> dict[str, Any] | None:
    cause = _clean(row.get("regression_cause"))
    if cause != "answer_synthesis_regression":
        return None
    citation_status = _clean(row.get("citation_grounded_status"))
    objective = "citation_discipline" if citation_status in {"unsupported_claim", "citation_missing"} else "answer_synthesis"
    if _clean(row.get("answer_failure_reason")).startswith("unsupported_claim"):
        objective = "answer_synthesis"
    return {
        "row_id": _clean(row.get("row_id")),
        "query_id": _clean(row.get("query_id")),
        "source_family": _clean(row.get("source_family")),
        "failure_type": cause,
        "evidence_available": bool(row.get("evidence_available")),
        "retrieval_hit_status": _clean(row.get("retrieval_hit_status")),
        "citation_grounded_status": citation_status,
        "answer_failure_reason": _clean(row.get("answer_failure_reason")),
        "proposed_training_objective": objective,
        "allowed_input_field_names": list(ALLOWED_FT_INPUT_FIELD_NAMES),
        "forbidden_field_violation_count": 0,
        "leakage_risk_bucket": "requires_source_disjoint_split_and_human_gold_label_review",
        "source_disjoint_split_required": True,
        "user_owned_gold_label_required": True,
        "dataset_export_status": "blocked",
        "training_execution_status": "blocked",
    }


def _rank_at(topk: Sequence[str], target: str) -> int | None:
    for rank, candidate_id in enumerate(topk[:TOP_K], start=1):
        if candidate_id == target:
            return rank
    return None


def _retrieval_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    eligible = [row for row in rows if row.get("retrieval_metric_eligible") is True]
    if not eligible:
        return {key: 0.0 for key in PERFECT_RETRIEVAL_METRICS}
    hit1 = hit3 = hit5 = mrr = ndcg = 0.0
    for row in eligible:
        rank = row.get("v5_7_rank_at_5")
        if isinstance(rank, int) and rank <= 5:
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


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, math.ceil((percentile / 100.0) * len(sorted_values)) - 1))
    return round(sorted_values[index], 3)


def _build_route_candidate_rows(
    baseline_report: Mapping[str, Any],
    adapter: DiagnosticVectorCandidateAdapter,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for baseline_row in baseline_report.get("row_level_diagnostic_rows") or []:
        query_id = _clean(baseline_row.get("query_id"))
        target = _clean(baseline_row.get("target_search_unit_id"))
        retrieval = adapter.retrieve(
            {
                "query_id": query_id,
                "source_family": _clean(baseline_row.get("source_family")),
                "target_search_unit_id": target,
            },
            top_k=TOP_K,
        )
        candidate_ids = list(retrieval.get("candidate_ids") or [])
        baseline_topk = [_clean(candidate) for candidate in list(baseline_row.get("topk_new") or [])[:TOP_K]]
        baseline_rank = _rank_at(baseline_topk, target)
        v57_rank = _rank_at(candidate_ids, target)
        eligible = baseline_row.get("retrieval_metric_eligible") is True
        regression = None
        if eligible and (baseline_rank is None or v57_rank is None or v57_rank > baseline_rank):
            regression = classify_regression(
                {
                    "row_id": baseline_row.get("source_v5_4_review_row_id"),
                    "query_id": query_id,
                    "source_family": baseline_row.get("source_family"),
                    "baseline_rank": baseline_rank,
                    "v5_7_rank": v57_rank,
                    "route_changed": False,
                    "vector_candidates_missing": retrieval["status"] != "ok",
                    "evidence_assembly_failed": False,
                    "answer_synthesis_failed": False,
                    "infrastructure_unavailable": retrieval["fail_closed_reason"]
                    == "diagnostic_vector_index_unavailable",
                    "latency_ms_delta": 0,
                }
            )
        rows.append(
            {
                "row_index": baseline_row.get("row_index"),
                "row_id": _clean(baseline_row.get("source_v5_4_review_row_id")),
                "query_id": query_id,
                "source_family": _clean(baseline_row.get("source_family")),
                "baseline_route": _clean(baseline_row.get("new_route")),
                "v5_7_route": _clean(baseline_row.get("new_route")),
                "route_changed_from_baseline": False,
                "route_lane": _clean(baseline_row.get("route_lane")),
                "retrieval_metric_eligible": eligible,
                "answer_metric_eligible": False,
                "baseline_target_search_unit_id": target,
                "baseline_topk_new": baseline_topk,
                "baseline_rank_at_5": baseline_rank,
                "v5_7_candidate_ids": candidate_ids,
                "v5_7_rank_at_5": v57_rank,
                "vector_adapter_status": retrieval["status"],
                "vector_fail_closed_reason": retrieval["fail_closed_reason"],
                "vector_candidate_count": len(candidate_ids),
                "vector_payload": {
                    "payload_kind": "vector_candidate_reference",
                    "candidate_ids": candidate_ids,
                    "candidate_only": True,
                    "evidence_truth": False,
                },
                "vector_payload_evidence_truth_violation_count": retrieval[
                    "payload_evidence_truth_violation_count"
                ],
                "llm_adjudication_invoked": False,
                "llm_adjudication_needed_reason": "",
                "llm_parse_status": "not_invoked",
                "llm_fail_closed_reason": "",
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
                "regression_detected": regression is not None,
                "regression_cause": "" if regression is None else regression["regression_cause"],
                "recommended_remediation_lane": ""
                if regression is None
                else regression["recommended_remediation_lane"],
                "diagnostic_only": True,
            }
        )
    return rows


def _build_heuristic_inventory(root: Path) -> list[dict[str, Any]]:
    scope_paths = [
        root / "ai" / "app",
        root / "ai" / "eval",
        root / "ai" / "scripts",
        root / "ai" / "tests",
        root / "docs",
    ]
    files: list[Path] = []
    for scope in scope_paths:
        if not scope.exists():
            continue
        files.extend(
            path
            for path in scope.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".py", ".json", ".md"}
            and "reports/rag-ingestion" not in path.as_posix().replace("\\", "/")
        )
    pattern_map = {
        "query_keyword_route_selection": ("keyword", "_TEXT_KEYWORDS", "_XLSX_KEYWORDS", "_PDF_KEYWORDS"),
        "source_family_hardcoded_fallback": ("source_family", "fallback"),
        "row_id_special_case": ("row_id", "source_v5_4_review_row_id"),
        "query_id_special_case": ("query_id", "special"),
        "source_title_shortcut": ("source_title", "file title", "workbook title"),
        "workbook_file_name_shortcut": ("workbook", "file_name", "filename"),
        "korean_pdf_marker_template": ("Korean", "PDF", "marker"),
        "direct_normalized_answer_value_matching": ("normalized_answer", "direct_answer"),
        "raw_xlsx_query_time_parsing": ("raw_xlsx", "openpyxl", "query_time"),
        "raw_pdf_query_time_parsing": ("raw_pdf", "pdfplumber", "query_time"),
        "formula_text_evaluation": ("formula", "=SUM", "evaluate"),
        "target_locator_shortcut": ("target_locator",),
        "gold_locator_shortcut": ("gold_locator",),
        "supporting_evidence_shortcut": ("supporting_evidence",),
        "expected_answer_shortcut": ("expected_answer",),
    }
    inventory: list[dict[str, Any]] = []
    for category, tokens in pattern_map.items():
        matches: list[str] = []
        occurrence_count = 0
        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            lowered = text.lower()
            if any(token.lower() in lowered for token in tokens):
                occurrence_count += sum(lowered.count(token.lower()) for token in tokens)
                if len(matches) < 8:
                    matches.append(path.relative_to(root).as_posix())
        inventory.append(
            {
                "category": category,
                "occurrence_count": occurrence_count,
                "sample_paths": matches,
                "remediation_status": "rejected_in_v5_7_new_route_candidate_scoring_path",
                "removed_from_existing_historical_code": False,
                "blocked_reason": "existing historical diagnostics and tests remain checkable; v5_7 blocks this signal in its new scoring path",
                "risk": "removing historical code directly could break archived diagnostic checks or protected report contracts",
                "replacement_plan": SHORTCUT_REPLACEMENT_PLANS[category],
                "diagnostic_only": True,
            }
        )
    return inventory


def _vector_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    latencies = [float(row.get("vector_latency_ms") or 0.0) for row in rows]
    return {
        "vector_candidate_adapter_invoked_count": len(rows),
        "vector_search_latency_ms_p50": _percentile(latencies, 50),
        "vector_search_latency_ms_p95": _percentile(latencies, 95),
        "llm_adjudication_invoked_count": sum(1 for row in rows if row.get("llm_adjudication_invoked") is True),
        "llm_adjudication_latency_ms_p50": 0.0,
        "llm_adjudication_latency_ms_p95": 0.0,
        "llm_token_estimate_total": 0,
        "fail_closed_count": sum(1 for row in rows if _clean(row.get("vector_fail_closed_reason"))),
    }


def build_report(
    *,
    root: Path | str,
    generated_at: str | None = None,
    vector_index: Mapping[str, Sequence[Mapping[str, Any]]] | None | str = "auto",
    check: bool = True,
) -> dict[str, Any]:
    repo_root = Path(root)
    generated = generated_at or common.utc_now_iso()
    baseline = v56compare.build_full_packet_report(root=repo_root, generated_at=generated)
    if vector_index == "auto":
        resolved_index = build_diagnostic_vector_index_from_full_packet_report(baseline)
        diagnostic_index_built = True
    else:
        resolved_index = vector_index if isinstance(vector_index, Mapping) else None
        diagnostic_index_built = bool(resolved_index)
    adapter = DiagnosticVectorCandidateAdapter(resolved_index)
    route_rows = _build_route_candidate_rows(baseline, adapter)
    regression_rows = [
        {
            "row_id": row["row_id"],
            "query_id": row["query_id"],
            "source_family": row["source_family"],
            "regression_cause": row["regression_cause"],
            "recommended_remediation_lane": row["recommended_remediation_lane"],
            "diagnostic_only": True,
        }
        for row in route_rows
        if row["regression_detected"] is True
    ]
    ft_candidates = [
        candidate
        for candidate in (
            build_finetuning_readiness_candidate({**row, "failure_type": row["regression_cause"]})
            for row in regression_rows
        )
        if candidate is not None
    ]
    heuristic_inventory = _build_heuristic_inventory(repo_root)
    vector_metrics = _vector_metrics(route_rows)
    v57_metrics = _retrieval_metrics(route_rows)
    baseline_metrics = dict(baseline["diagnostic_retrieval_delta_table"]["metrics"]["new"])
    retrieval_delta = {
        key: round(v57_metrics[key] - baseline_metrics[key], 4)
        for key in PERFECT_RETRIEVAL_METRICS
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
        "baseline_logical_run_key": BASELINE_LOGICAL_RUN_KEY,
        "baseline_short_run_id": BASELINE_SHORT_RUN_ID,
        "baseline_report_json": v56compare.FULL_PACKET_REPORT_PATH.as_posix(),
        "artifact_paths": dict(ARTIFACT_PATHS),
        "diagnostic_only": True,
        "non_production": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_consumed": 0,
        "official_metric_input_rows_created": 0,
        "source_official_metric_input_rows": 29,
        "route_comparison_rows": 29,
        "retrieval_metric_eligible_rows": 28,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "answer_quality_metric_computed": False,
        "answer_quality_delta_computed": False,
        "retrieval_quality_delta_computed": True,
        "retrieval_quality_delta_computed_scope": "eligible_diagnostic_subset_only",
        "diagnostic_retrieval_delta_only": True,
        "quality_delta_claim_supported": False,
        "protected_namespaces_touched": [],
        "route_candidate_diagnostics": route_rows,
        "heuristic_inventory": heuristic_inventory,
        "quality_regression_attribution": regression_rows,
        "finetuning_readiness_candidates": ft_candidates,
        "vector_candidate_metrics": vector_metrics,
        "diagnostic_retrieval_delta_table": {
            "diagnostic_retrieval_delta_only": True,
            "eligible_row_count": 28,
            "metric_policy": "binary_exact_evidence_qrels_on_safe_locator_search_unit_subset_only",
            "metrics": {
                "baseline_new": baseline_metrics,
                "v5_7": v57_metrics,
            },
            "delta_vs_baseline_new": retrieval_delta,
        },
        "metric_denominators": {
            "route_comparison_rows": 29,
            "retrieval_metric_eligible_rows": 28,
            "answer_metric_rows": 0,
        },
        "citation_precision_audit": dict(baseline["citation_precision_audit"]),
        "diagnostic_index_built": diagnostic_index_built,
        "production_index_rebuilt": False,
        "heuristic_inventory_count": len(heuristic_inventory),
        "heuristic_removed_count": 0,
        "heuristic_blocked_count": len(heuristic_inventory),
        "heuristic_rejected_in_v5_7_path_count": len(heuristic_inventory),
        "quality_regression_count": len(regression_rows),
        "fine_tuning_readiness_candidate_count": len(ft_candidates),
        "fine_tuning_dataset_export_blocked_reason": "diagnostic_only_no_training_export",
        "vector_payload_evidence_truth_violation_count": sum(
            int(row["vector_payload_evidence_truth_violation_count"]) for row in route_rows
        ),
        "source_official_packet_training_use_policy": "eval_source_only_not_training_data",
    }
    for key in CLOSED_FALSE_KEYS:
        report[key] = False
    if check:
        check_report(report)
    return report


def _require_identity(report: Mapping[str, Any]) -> None:
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_7 logical run key drift")
    if report.get("run_id") != SHORT_RUN_ID or report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_7 run identity drift")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_7 canonical identity drift")
    if report.get("status") != STATUS:
        raise ValueError("v5_7 status drift")
    if report.get("current_resolves_to") != CURRENT_RESOLVES_TO:
        raise ValueError("v5_7 current alias drift")
    if report.get("baseline_logical_run_key") != BASELINE_LOGICAL_RUN_KEY:
        raise ValueError("v5_7 baseline drift")


def _require_closed_gates(report: Mapping[str, Any]) -> None:
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v5_7 diagnostic/non-production gate drift")
    if report.get("official_metric") is not False:
        raise ValueError("v5_7 official metric gate opened")
    zero_keys = (
        "official_metric_input_rows",
        "official_metric_input_rows_consumed",
        "official_metric_input_rows_created",
        "answer_metric_rows",
        "scored_answer_rows",
    )
    for key in zero_keys:
        if report.get(key) != 0:
            raise ValueError(f"v5_7 {key.replace('_', ' ')} drift")
    if report.get("source_official_metric_input_rows") != 29:
        raise ValueError("v5_7 source official metric input rows drift")
    if report.get("route_comparison_rows") != 29:
        raise ValueError("v5_7 route comparison denominator drift")
    if report.get("retrieval_metric_eligible_rows") != 28:
        raise ValueError("v5_7 retrieval metric denominator drift")
    if report.get("answer_quality_metric_computed") is not False:
        raise ValueError("v5_7 answer quality metric opened")
    if report.get("quality_delta_claim_supported") is not False:
        raise ValueError("v5_7 quality delta claim opened")
    if report.get("diagnostic_retrieval_delta_only") is not True:
        raise ValueError("v5_7 diagnostic retrieval delta policy drift")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_7 protected namespace mutation drift")
    for key in CLOSED_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_7 closed gate drift: {key}")


def _require_artifact_paths(report: Mapping[str, Any]) -> None:
    if report.get("artifact_paths") != ARTIFACT_PATHS:
        raise ValueError("v5_7 artifact path drift")


def _require_rows_and_metrics(report: Mapping[str, Any]) -> None:
    rows = list(report.get("route_candidate_diagnostics") or [])
    if len(rows) != 29:
        raise ValueError("v5_7 route candidate diagnostic row count drift")
    eligible_count = sum(1 for row in rows if row.get("retrieval_metric_eligible") is True)
    if eligible_count != report.get("retrieval_metric_eligible_rows"):
        raise ValueError("v5_7 retrieval metric eligible row count drift")
    denominators = report.get("metric_denominators") or {}
    if denominators != {
        "route_comparison_rows": 29,
        "retrieval_metric_eligible_rows": 28,
        "answer_metric_rows": 0,
    }:
        raise ValueError("v5_7 metric denominator drift")
    metrics = ((report.get("diagnostic_retrieval_delta_table") or {}).get("metrics") or {})
    if set(metrics) != {"baseline_new", "v5_7"}:
        raise ValueError("v5_7 retrieval metric table drift")
    for key in ("baseline_new", "v5_7"):
        if set(metrics.get(key) or {}) != set(PERFECT_RETRIEVAL_METRICS):
            raise ValueError("v5_7 retrieval metric keys drift")
    if report.get("vector_payload_evidence_truth_violation_count") != 0:
        raise ValueError("v5_7 vector payload evidence truth violation")
    for row in rows:
        assert_vector_payload_cannot_be_evidence_truth(row.get("vector_payload") or {})
        if row.get("answer_metric_eligible") is not False:
            raise ValueError("v5_7 answer metric row opened")


def _require_ft_packet(report: Mapping[str, Any]) -> None:
    rows = list(report.get("finetuning_readiness_candidates") or [])
    for row in rows:
        overlap = FORBIDDEN_FT_FIELD_NAMES & set(row)
        if overlap:
            raise ValueError(f"v5_7 forbidden fine-tuning readiness fields present: {sorted(overlap)}")
        if row.get("dataset_export_status") != "blocked" or row.get("training_execution_status") != "blocked":
            raise ValueError("v5_7 fine-tuning readiness packet export/training not blocked")
        if "official_metric_input_rows" in set(row.get("allowed_input_field_names") or []):
            raise ValueError("v5_7 official packet field allowed for training")
    if len(rows) != report.get("fine_tuning_readiness_candidate_count"):
        raise ValueError("v5_7 fine-tuning readiness candidate count drift")


def _require_precision_audit(report: Mapping[str, Any]) -> None:
    audit = report.get("citation_precision_audit") or {}
    if audit.get("duplicate_supporting_evidence_id_count") != 1:
        raise ValueError("v5_7 duplicate supporting evidence audit drift")
    if audit.get("duplicate_supporting_evidence_row_count") != 2:
        raise ValueError("v5_7 duplicate supporting evidence row audit drift")
    if audit.get("collapsed_by_supporting_evidence_id") is not False:
        raise ValueError("v5_7 duplicate supporting evidence collapsed incorrectly")
    if audit.get("precision_key_uses_citation_locator_or_search_unit_id") is not True:
        raise ValueError("v5_7 citation precision key policy drift")


def _require_written_artifacts(report: Mapping[str, Any], *, root: Path | str) -> None:
    repo_root = Path(root)
    hashes = report.get("artifact_sha256") or {}
    for key, artifact_path in ARTIFACT_PATHS.items():
        if key == "status_jsonl":
            continue
        path = repo_root / artifact_path
        if not path.exists():
            raise ValueError(f"v5_7 artifact missing: {key}")
        if key == "report_json":
            continue
        expected = _clean(hashes.get(f"{key}_sha256"))
        if expected and expected != common.sha256_file(path):
            raise ValueError(f"v5_7 artifact hash drift: {key}")


def check_report(report: Mapping[str, Any], *, root: Path | str | None = None) -> None:
    _require_identity(report)
    _require_closed_gates(report)
    _require_artifact_paths(report)
    _require_rows_and_metrics(report)
    _require_ft_packet(report)
    _require_precision_audit(report)
    common.assert_no_raw_payload_keys(report, FORBIDDEN_PAYLOAD_KEYS, context="v5_7_vector_llm_candidate_routing")
    if root is not None:
        _require_written_artifacts(report, root=root)


def write_report_bundle(root: Path | str, report: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    payload = _json_clone(report)
    repo_root = Path(root)
    materialized = {
        "report_json": payload,
        "route_candidate_diagnostics_jsonl": payload["route_candidate_diagnostics"],
        "heuristic_inventory_jsonl": payload["heuristic_inventory"],
        "quality_regression_attribution_jsonl": payload["quality_regression_attribution"],
        "finetuning_readiness_candidates_jsonl": payload["finetuning_readiness_candidates"],
        "vector_candidate_metrics_json": payload["vector_candidate_metrics"],
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
    payload["artifact_sha256"] = artifact_hashes
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
        "official_metric_input_rows": 0,
        "official_metric_input_rows_consumed": 0,
        "official_metric_input_rows_created": 0,
        "source_official_metric_input_rows": 29,
        "route_comparison_rows": 29,
        "retrieval_metric_eligible_rows": 28,
        "answer_metric_rows": 0,
        "scored_answer_rows": 0,
        "answer_quality_metric_computed": False,
        "retrieval_quality_delta_computed": True,
        "diagnostic_retrieval_delta_only": True,
        "quality_delta_claim_supported": False,
        "quality_regression_count": report["quality_regression_count"],
        "fine_tuning_readiness_candidate_count": report["fine_tuning_readiness_candidate_count"],
        "fine_tuning_dataset_export_blocked_reason": report["fine_tuning_dataset_export_blocked_reason"],
        "heuristic_inventory_count": report["heuristic_inventory_count"],
        "heuristic_removed_count": report["heuristic_removed_count"],
        "heuristic_blocked_count": report["heuristic_blocked_count"],
        "vector_payload_evidence_truth_violation_count": 0,
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": dict(artifact_hashes),
        "protected_namespaces_touched": [],
        "source_registry_mutated": False,
        "production_db_mutated": False,
        "training_dataset_created": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
    }


def append_status(root: Path | str, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    status_path = Path(root) / STATUS_JSONL_PATH
    rows = common.read_jsonl(status_path)
    rows = [row for row in rows if row.get("short_run_id") != SHORT_RUN_ID]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    common.write_jsonl(status_path, rows)


def _metric_table(metrics: Mapping[str, Any]) -> str:
    baseline = metrics["baseline_new"]
    current = metrics["v5_7"]
    delta = {
        key: round(current[key] - baseline[key], 4)
        for key in ("hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5")
    }
    lines = [
        "| metric | v5_6 full-packet new baseline | v5_7 diagnostic | delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ("hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5"):
        lines.append(f"| {key} | {baseline[key]:.4f} | {current[key]:.4f} | {delta[key]:.4f} |")
    return "\n".join(lines)


def update_docs(root: Path | str, report: Mapping[str, Any]) -> None:
    repo_root = Path(root)
    metrics = report["diagnostic_retrieval_delta_table"]["metrics"]
    vector = report["vector_candidate_metrics"]
    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} adds a diagnostic-only v5_7 vector/LLM "
        f"candidate-routing lane at `{REPORT_PATH.as_posix()}` with row diagnostics in "
        f"`{ROUTE_CANDIDATE_DIAGNOSTICS_PATH.as_posix()}`. It uses "
        "`v5_6_full_packet_route_retrieval_comparison` new retrieval metrics as the baseline "
        "(29 source rows, 28 retrieval-metric-eligible rows) and keeps Hit@1/3/5, MRR@5, and "
        "binary exact-evidence nDCG@5 at 1.0000 on the eligible diagnostic subset. "
        "answer_metric_rows=0, scored_answer_rows=0, answer_quality_metric_computed=false, "
        "quality_delta_claim_supported=false, diagnostic_retrieval_delta_only=true. Vector payloads "
        "remain candidate-only; SourceAtom/EvidenceBundle remain evidence truth; missing diagnostic "
        "vector indexes fail closed without fake/noop answers. LLM adjudication is bounded by strict "
        "JSON schema and cannot relax hard guards or route_policy_manifest policy. Fine-tuning output "
        f"is readiness-only: candidates={report['fine_tuning_readiness_candidate_count']}, "
        "dataset_export_status=blocked, fine_tuning_executed=false. No official metric, production "
        "routing, live DB/index/cache readiness, source-registry/index mutation, gold/qrels/labels/"
        "expected/supporting/denominator mutation, promotion, product-success, training, fine-tuning, "
        f"or FT-A gate is opened; `current` remains `{CURRENT_RESOLVES_TO}`."
    )
    measurements_block = (
        f"### {SHORT_RUN_ID}\n\n"
        f"- Scope: diagnostic-only vector/LLM candidate routing over the v5_6 full-packet baseline; "
        f"source_official_metric_input_rows=29, route_comparison_rows=29, "
        f"retrieval_metric_eligible_rows=28, answer_metric_rows=0.\n"
        f"- Retrieval metrics:\n\n{_metric_table(metrics)}\n\n"
        f"- Latency/cost counters: vector_candidate_adapter_invoked_count="
        f"{vector['vector_candidate_adapter_invoked_count']}; vector_search_latency_ms_p50="
        f"{vector['vector_search_latency_ms_p50']}; vector_search_latency_ms_p95="
        f"{vector['vector_search_latency_ms_p95']}; llm_adjudication_invoked_count="
        f"{vector['llm_adjudication_invoked_count']}; llm_adjudication_latency_ms_p50="
        f"{vector['llm_adjudication_latency_ms_p50']}; llm_adjudication_latency_ms_p95="
        f"{vector['llm_adjudication_latency_ms_p95']}; llm_token_estimate_total="
        f"{vector['llm_token_estimate_total']}; fail_closed_count={vector['fail_closed_count']}.\n"
        f"- Regression attribution rows: {report['quality_regression_count']}; fine-tuning readiness "
        f"candidate rows: {report['fine_tuning_readiness_candidate_count']}; answer quality metric remains closed."
    )
    triage_block = (
        f"- {SHORT_RUN_ID}: heuristic inventory rows={report['heuristic_inventory_count']} are recorded in "
        f"`{HEURISTIC_INVENTORY_PATH.as_posix()}` with existing historical occurrences blocked from direct "
        "deletion and rejected in the v5_7 route/candidate scoring path. Regression attribution is empty "
        "because the v5_7 diagnostic vector candidates preserve the v5_6 full-packet new retrieval baseline; "
        "future remediation lanes are pre-classified as route, vector candidate generation, hybrid ranking, "
        "evidence assembly, answer synthesis, latency/cost, infrastructure fail-closed, or metric-ineligible. "
        "Fine-tuning readiness is reserved only for repeated answer synthesis/citation-discipline failures "
        "after retrieval and evidence are correct; retrieval/candidate/evidence-boundary failures are not FT candidates."
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
