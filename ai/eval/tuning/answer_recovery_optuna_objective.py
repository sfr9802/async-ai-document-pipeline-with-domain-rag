"""Guarded answer-recovery objective adapter for future Optuna rounds.

The callable is intentionally fail-closed until fresh, non-frozen reviewed
positive answer-recovery candidates exist. It reads compact diagnostic reports
only; it does not call an LLM, mutate indexes, write vectors, create
namespaces, or update official denominators.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
DEFAULT_TUNING_REPORT = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "answer_recovery_tuning_report.json"
DEFAULT_CANDIDATE_REPORT = (
    AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "answer_recovery_fresh_diagnostic_candidate_discovery.json"
)

FORBIDDEN_PARAMS = {
    "allow_hidden_xlsx",
    "allow_pdf_file_content_support",
    "allow_diagnostic_only_support",
    "allow_unscoped_indexing",
    "mutate_production_index",
    "write_vectors",
    "create_namespace",
    "use_expected_answer_embedding",
    "use_label_embedding",
    "train_on_frozen_gold",
    "open_official_denominator",
    "promote_policy",
}

ALLOWED_SAFE_CONTEXT_VARIANTS = {
    "baseline_selected_policy",
    "text_adjacent_context_v1",
    "text_rewrite_then_adjacent_v1",
    "xlsx_strict_context_v1",
    "pdf_content_native_page_context_v1",
    "mixed_safe_context_v1",
}


def evaluate(params: dict) -> dict:
    """Return a guarded objective payload for optuna-round-refinement."""

    tuning_report = _read_json(DEFAULT_TUNING_REPORT)
    candidate_report = _read_json(DEFAULT_CANDIDATE_REPORT)
    return score_payload(params, tuning_report=tuning_report, candidate_report=candidate_report)


def score_payload(
    params: Mapping[str, Any],
    *,
    tuning_report: Mapping[str, Any] | None,
    candidate_report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    violations = validate_params(params)
    missing_inputs = []
    if tuning_report is None:
        missing_inputs.append(repo_relative(DEFAULT_TUNING_REPORT))
    if candidate_report is None:
        missing_inputs.append(repo_relative(DEFAULT_CANDIDATE_REPORT))

    calibration = dict((tuning_report or {}).get("calibration") or {})
    guardrails = dict((tuning_report or {}).get("guardrails") or {})
    discovery_counts = dict((candidate_report or {}).get("counts") or {})
    discovery_guardrails = dict((candidate_report or {}).get("guardrail_status") or {})

    guardrail_violation_count = guardrail_count(guardrails) + guardrail_count(discovery_guardrails)
    reviewed_positive_count = int(discovery_counts.get("reviewed_positive_candidate_count") or 0)
    fresh_review_ready_count = int(discovery_counts.get("review_ready_count") or 0)
    citation_before = float(calibration.get("citation_coverage_before") or 0.0)
    citation_after = float(calibration.get("citation_coverage_after") or 0.0)
    citation_gain = max(0.0, citation_after - citation_before)
    wrongly_supported = int(calibration.get("after_calibration_wrongly_supported_count") or 0)
    recovered_after_loop = int(calibration.get("recovered_after_loop") or 0)

    hidden_support = int(guardrails.get("hidden_xlsx_support_eligible_count") or 0) + int(
        discovery_guardrails.get("hidden_xlsx_support_eligible_count") or 0
    )
    pdf_file_mixing_support = int(guardrails.get("pdf_file_content_mixing_support_eligible_count") or 0) + int(
        discovery_guardrails.get("pdf_file_content_mixing_support_eligible_count") or 0
    )
    diagnostic_only_support = int(guardrails.get("diagnostic_only_support_eligible_count") or 0) + int(
        discovery_guardrails.get("diagnostic_only_support_eligible_count") or 0
    )
    official_changed = bool(guardrails.get("official_denominator_registry_changed")) or bool(
        discovery_guardrails.get("official_denominator_registry_changed")
    )
    production_mutation = bool(guardrails.get("production_index_mutation")) or bool(
        discovery_guardrails.get("production_index_mutation")
    )
    vector_write = bool(guardrails.get("vector_write_attempted")) or bool(
        discovery_guardrails.get("vector_write_attempted")
    )
    namespace_created = bool(guardrails.get("namespace_created")) or bool(
        discovery_guardrails.get("namespace_created")
    )
    broad_indexing = bool(guardrails.get("broad_indexing")) or bool(discovery_guardrails.get("broad_indexing"))
    prerequisite_failed = reviewed_positive_count <= 0

    primary = (
        recovered_after_loop
        + 0.25 * citation_gain
        - 1000 * wrongly_supported
        - 1000 * guardrail_violation_count
        - 100 * hidden_support
        - 100 * pdf_file_mixing_support
        - 100 * diagnostic_only_support
        - 1000 * int(official_changed)
        - 1000 * int(production_mutation)
        - 1000 * int(vector_write)
        - 1000 * int(namespace_created)
        - 1000 * int(broad_indexing)
        - 1000 * len(violations)
    )
    if missing_inputs:
        primary -= 1000 * len(missing_inputs)
    if prerequisite_failed:
        primary = min(primary, 0.0)

    guardrail_failed = bool(
        violations
        or missing_inputs
        or guardrail_violation_count
        or wrongly_supported
        or hidden_support
        or pdf_file_mixing_support
        or diagnostic_only_support
        or official_changed
        or production_mutation
        or vector_write
        or namespace_created
        or broad_indexing
    )

    return {
        "primary": float(primary),
        "secondary": {
            "guardrail_failed": guardrail_failed,
            "param_violations": violations,
            "missing_inputs": missing_inputs,
            "prerequisite_failed": prerequisite_failed,
            "prerequisite_failure_reason": (
                "fresh_non_frozen_reviewed_positive_candidates_missing" if prerequisite_failed else ""
            ),
            "fresh_review_ready_count": fresh_review_ready_count,
            "reviewed_positive_candidate_count": reviewed_positive_count,
            "recovered_after_loop": recovered_after_loop,
            "wrongly_supported_count": wrongly_supported,
            "citation_coverage": citation_after,
            "citation_coverage_gain": round(citation_gain, 6),
            "unsupported_correctly_blocked": int(
                (tuning_report or {}).get("missed_recovery", {}).get("total_missed_or_blocked") or 0
            ),
            "hidden_xlsx_blocked": int(
                discovery_counts.get("status_counts", {}).get("SKIP_HIDDEN_XLSX", 0)
                if isinstance(discovery_counts.get("status_counts"), Mapping)
                else 0
            ),
            "pdf_file_content_mixing_blocked": int(
                discovery_counts.get("status_counts", {}).get("SKIP_PDF_FILE_CONTENT_MIXING_RISK", 0)
                if isinstance(discovery_counts.get("status_counts"), Mapping)
                else 0
            ),
            "diagnostic_only_blocked": int(
                discovery_counts.get("status_counts", {}).get("SKIP_DIAGNOSTIC_ONLY_SHADOW", 0)
                if isinstance(discovery_counts.get("status_counts"), Mapping)
                else 0
            ),
            "clarification_needed_count": int(calibration.get("clarification_needed_count") or 0),
            "answerability_safe_count": int(discovery_counts.get("review_ready_count") or 0),
            "production_promotion_ready": False,
            "official_answer_denominator_ready": False,
            "official_denominator_registry_changed": official_changed,
            "production_index_mutation": production_mutation,
            "broad_indexing": broad_indexing,
            "vector_write_attempted": vector_write,
            "namespace_created": namespace_created,
            "llm_as_objective": False,
            "per_trial_llm_steering": False,
            "mid_round_search_space_mutation": False,
            "raw_data_exposed_to_llm_analyst": False,
        },
    }


def validate_params(params: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    for key in sorted(set(params) & FORBIDDEN_PARAMS):
        violations.append(f"forbidden_param:{key}")
    if "safe_context_variant" in params and params["safe_context_variant"] not in ALLOWED_SAFE_CONTEXT_VARIANTS:
        violations.append(f"unsupported_safe_context_variant:{params['safe_context_variant']}")
    if int(params.get("max_loop_iterations", 0) or 0) > 2:
        violations.append("max_loop_iterations_exceeds_2")
    if int(params.get("max_query_rewrites", 0) or 0) > 3:
        violations.append("max_query_rewrites_exceeds_3")
    if float(params.get("support_score_threshold", 0.0) or 0.0) < 0.0:
        violations.append("support_score_threshold_below_0")
    return violations


def guardrail_count(payload: Mapping[str, Any]) -> int:
    count = 0
    for key in (
        "official_denominator_registry_changed",
        "official_answer_denominator_opened",
        "production_index_mutation",
        "broad_indexing",
        "vector_write_attempted",
        "namespace_created",
        "frozen_gold_profile_selection",
        "production_promotion_ready",
        "official_answer_denominator_ready",
        "promotion_evidence",
        "per_trial_llm_steering",
        "llm_as_objective",
        "mid_round_search_space_mutation",
        "raw_data_exposed_to_llm_analyst",
    ):
        if bool(payload.get(key)):
            count += 1
    for key in (
        "frozen_gold_training_rows",
        "expected_answer_or_label_embedding_count",
        "hidden_xlsx_support_eligible_count",
        "pdf_file_content_mixing_support_eligible_count",
        "diagnostic_only_support_eligible_count",
    ):
        if int(payload.get(key) or 0) != 0:
            count += 1
    return count


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)
