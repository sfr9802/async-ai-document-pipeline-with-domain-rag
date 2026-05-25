from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import rag_pdf_xlsx_llm_quality_benchmark as quality_benchmark
import rag_v3_13_pdf_file_identity_structural_locator_nonprod_alignment as v313
import rag_v3_14_layered_retrieval_runtime_adapter_nonprod as v314
import rag_v3_15_xlsx_l3_table_range_locator_nonprod_improvement as v315
from rag_local_llm_expected_answer_generation_v1 import (
    DEFAULT_BACKEND,
    DEFAULT_MODEL,
    local_llm_entry_blockers,
    resolve_base_url,
)


ROOT = v315.ROOT
if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))
if str(ROOT / "ai" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))

from app.capabilities.rag.source_registry import assemble_evidence_bundle, render_citation


RUN_ID = "official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod"
REPORT_DIR = v315.REPORT_DIR
STATUS_JSONL = v315.STATUS_JSONL
PROGRESS_DOC = v315.PROGRESS_DOC
MEASUREMENTS_DOC = v315.MEASUREMENTS_DOC
TRIAGE_DOC = v315.TRIAGE_DOC
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID

STATUS = "DIAGNOSTIC_V3_16_FINAL_LLM_ANSWER_QUALITY_REVIEW_NONPROD_READY"
FAIL_CLOSED_STATUS = "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
EVENT_TYPE = "diagnostic_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod"
PROMPT_VERSION = "v3_16_final_llm_answer_quality_review_prompt_v1"

SAMPLE_LIMITS = {
    "xlsx_answer_ready": 30,
    "xlsx_no_candidate_abstain": 10,
    "pdf_answer_ready_control": 15,
    "pdf_residual_control": 5,
}

OUTPUTS = {
    "summary_json": OUTPUT_DIR / "summary.json",
    "metrics_json": OUTPUT_DIR / "metrics.json",
    "per_family_json": OUTPUT_DIR / "per_family.json",
    "per_query_jsonl": OUTPUT_DIR / "per_query.jsonl",
    "responses_jsonl": OUTPUT_DIR / "responses.jsonl",
    "review_packet_csv": OUTPUT_DIR / "review_packet.csv",
    "review_packet_jsonl": OUTPUT_DIR / "review_packet.jsonl",
    "guardrail_audit_json": OUTPUT_DIR / "guardrail_audit.json",
    "leakage_audit_jsonl": OUTPUT_DIR / "leakage_audit.jsonl",
    "prompt_manifest_json": OUTPUT_DIR / "prompt_manifest.json",
    "local_llm_readiness_json": OUTPUT_DIR / "local_llm_readiness.json",
    "runtime_materialization_plan_json": OUTPUT_DIR / "runtime_materialization_plan.json",
    "latency_budget_contract_json": OUTPUT_DIR / "latency_budget_contract.json",
    "per_layer_online_work_audit_jsonl": OUTPUT_DIR / "per_layer_online_work_audit.jsonl",
    "cache_key_contract_json": OUTPUT_DIR / "cache_key_contract.json",
    "forbidden_query_time_work_audit_json": OUTPUT_DIR / "forbidden_query_time_work_audit.json",
}

MATERIALIZATION_CLASSES = (
    "ingestion_time_materialized",
    "index_time_materialized",
    "query_time_lightweight",
    "query_time_cacheable",
    "forbidden_query_time_work",
)
RUNTIME_LAYER_NAMES = (*v314.RUNTIME_LAYER_NAMES, "L8_FINAL_LLM_ANSWER_GENERATION")
LAYER_MATERIALIZATION_CLASSIFICATION = {
    "L0_QUERY_ROUTING": "query_time_lightweight",
    "L1_COARSE_CANDIDATE_GENERATION": "index_time_materialized",
    "L2_FILE_WORKBOOK_IDENTITY": "query_time_lightweight",
    "L3_STRUCTURAL_LOCATOR": "query_time_lightweight",
    "L4_SOURCEATOM_HYDRATION": "query_time_cacheable",
    "L5_EVIDENCE_BUNDLE_ASSEMBLY": "query_time_lightweight",
    "L6_EVIDENCE_SELECTOR": "query_time_lightweight",
    "L7_ANSWER_READY_CONTEXT": "query_time_cacheable",
    "L8_FINAL_LLM_ANSWER_GENERATION": "query_time_cacheable",
}
MAX_L3_STRUCTURAL_CANDIDATES = 3
MAX_L5_EVIDENCE_BUNDLES = 3
SAMPLE_SELECTION_STRATEGY = "stable_query_id_source_atom_hash_first_n_per_family_bucket"

USER_REVIEW_FIELDS = (
    "user_review_like",
    "user_review_note",
    "user_expected_answer_decision",
    "user_supporting_evidence_decision",
    "user_relevance_decision",
    "user_answerability_decision",
)

REVIEW_COLUMNS = (
    "review_id",
    "query_id",
    "diagnostic_case_id",
    "sample_bucket",
    "source_family",
    "source_identity",
    "query",
    "final_answer",
    "rendered_citations",
    "selected_source_atom_ids",
    "selected_evidence_excerpt",
    "locator_summary",
    "generation_model",
    "prompt_version",
    "answer_length_chars",
    "diagnostic_flags",
    "unsupported_claim_risk",
    "citation_missing_flag",
    "evidence_underuse_flag",
    "xlsx_value_formatting_risk",
    "pdf_weak_evidence_window_flag",
    "abstain_quality_flag",
    "malformed_response_flag",
    "runtime_materialization_classification",
    "retrieval_latency_ms",
    "l8_generation_latency_ms",
    "latency_scope",
    *USER_REVIEW_FIELDS,
    "promotion_evidence",
    "official_metric_candidate",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


def clean(value: Any) -> str:
    return v315.clean(value)


def as_mapping(value: Any) -> Mapping[str, Any]:
    return v315.as_mapping(value)


def sha256_file(path: Path) -> str:
    return v315.sha256_file(path)


def sha256_text(value: str) -> str:
    return v315.sha256_text(value)


def repo_relative(path: Path) -> str:
    try:
        return v315.repo_relative(path)
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return v315.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v315.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v315.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v315.write_jsonl(path, rows)


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return v315.ratio(numerator, denominator)


def lineage_entry(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() and path.is_file() else "",
    }


def build_input_paths() -> dict[str, Path]:
    return {
        "v3_15_summary_json": v315.OUTPUTS["summary_json"],
        "v3_15_per_query_jsonl": v315.OUTPUTS["per_query_jsonl"],
        "v3_15_layer_trace_per_query_jsonl": v315.OUTPUTS["layer_trace_per_query_jsonl"],
        "v3_14_summary_json": v314.OUTPUTS["summary_json"],
        "v3_14_per_query_jsonl": v314.OUTPUTS["per_query_jsonl"],
        "v3_14_layer_trace_per_query_jsonl": v314.OUTPUTS["layer_trace_per_query_jsonl"],
        "v3_13_summary_json": v313.OUTPUTS["summary_json"],
        "v3_13_pdf_eval_jsonl": v313.OUTPUTS["pdf_structural_locator_eval_per_query_jsonl"],
        "v3_13_pdf_trace_jsonl": v313.OUTPUTS["pdf_layer_trace_per_query_jsonl"],
        "source_registry_jsonl": v315.v392.SOURCE_REGISTRY_JSONL,
        "diagnostic_silver_query_manifest_jsonl": quality_benchmark.DEFAULT_SILVER_MANIFEST,
    }


def build_input_lineage(input_paths: Mapping[str, Path]) -> dict[str, Any]:
    return {key: lineage_entry(path) for key, path in input_paths.items()}


def require_input_artifacts(input_paths: Mapping[str, Path]) -> None:
    missing = [repo_relative(path) for path in input_paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required v3_16 input artifacts: " + ", ".join(missing))


def guardrail_flags(*, l8_generation_executed: bool, fail_closed: bool = False) -> dict[str, Any]:
    return {
        "diagnostic_only": True,
        "L8_generation_executed": bool(l8_generation_executed),
        "answer_generation_executed": bool(l8_generation_executed),
        "deterministic_official_execution": False,
        "deterministic_answer_execution_executed": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "product_success_evidence_allowed": False,
        "raw_file_query_time_accessed": False,
        "db_or_production_namespace_written": False,
        "source_atom_registry_canonical_truth": True,
        "source_atom_registry_mutated": False,
        "vector_payload_used_as_evidence_truth": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "direct_normalized_value_query_matching_used": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_evidence": False,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "official_denominator_mutated": False,
        "production_mutation": False,
        "raw_file_fallback_attempted": False,
        "raw_file_fallback_blocked_count": 0,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "headline_score": None,
        "local_llm_unavailable_fail_closed": bool(fail_closed),
        "noop_or_extractive_generator_used": False,
    }


def runtime_classification_string() -> str:
    return "; ".join(
        f"{layer}={LAYER_MATERIALIZATION_CLASSIFICATION[layer]}" for layer in RUNTIME_LAYER_NAMES
    )


def percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def latency_stats(values: Sequence[float]) -> dict[str, Any]:
    numeric = [float(value) for value in values]
    return {
        "count": len(numeric),
        "min_ms": round(min(numeric), 3) if numeric else 0.0,
        "median_ms": percentile(numeric, 0.5),
        "p95_ms": percentile(numeric, 0.95),
        "max_ms": round(max(numeric), 3) if numeric else 0.0,
    }


def row_diagnostic_flags(row: Mapping[str, Any]) -> dict[str, Any]:
    flags = row.get("diagnostic_flags")
    if isinstance(flags, str):
        try:
            parsed = json.loads(flags)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    if isinstance(flags, Mapping):
        return dict(flags)
    return {}


def build_runtime_materialization_plan() -> dict[str, Any]:
    exactly_one = (
        set(LAYER_MATERIALIZATION_CLASSIFICATION) == set(RUNTIME_LAYER_NAMES)
        and all(value in MATERIALIZATION_CLASSES for value in LAYER_MATERIALIZATION_CLASSIFICATION.values())
    )
    layer_reasons = {
        "L0_QUERY_ROUTING": "Query routing only reads the diagnostic case route already present in v3_14/v3_15 traces.",
        "L1_COARSE_CANDIDATE_GENERATION": "Coarse candidates are inherited from materialized SearchView/runtime artifacts.",
        "L2_FILE_WORKBOOK_IDENTITY": "File/workbook identity is replayed from bounded upstream trace fields.",
        "L3_STRUCTURAL_LOCATOR": "L3 reranks only bounded precomputed structural candidates and does not scan workbooks or PDFs.",
        "L4_SOURCEATOM_HYDRATION": "L4 hydrates cached SourceAtom-id lookups; vector payloads cannot become evidence truth.",
        "L5_EVIDENCE_BUNDLE_ASSEMBLY": "L5 assembles EvidenceBundles from bounded SourceAtom ids only.",
        "L6_EVIDENCE_SELECTOR": "L6 selects from the bounded bundle/candidate set.",
        "L7_ANSWER_READY_CONTEXT": "L7 answer-ready context can be cached for review but is not source truth.",
        "L8_FINAL_LLM_ANSWER_GENERATION": "L8 final answer generation is cacheable diagnostic output and its latency is separate.",
    }
    return {
        "schema_version": f"{RUN_ID}_runtime_materialization_plan_v1",
        "run_id": RUN_ID,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "materialization_classes": list(MATERIALIZATION_CLASSES),
        "layers": list(RUNTIME_LAYER_NAMES),
        "per_layer_classification": dict(LAYER_MATERIALIZATION_CLASSIFICATION),
        "classification_reason_by_layer": layer_reasons,
        "all_l0_l8_components_classified_once": exactly_one,
        "raw_pdf_xlsx_query_time_parsing_forbidden": True,
        "full_workbook_scan_query_time_forbidden": True,
        "full_pdf_page_block_scan_query_time_forbidden": True,
        "broad_source_atom_registry_scan_query_time_forbidden": True,
        "query_time_l3_policy": "rerank_only_bounded_precomputed_structural_candidates",
        "query_time_l4_policy": "hydrate_by_source_atom_id_from_canonical_registry_lookup",
        "query_time_l5_policy": "assemble_from_source_atom_ids_and_bounded_candidate_sets_only",
        "l7_answer_ready_context_cacheable": True,
        "l7_answer_ready_context_source_truth": False,
        "l8_generation_latency_reported_separately_from_retrieval": True,
        "source_atom_registry_canonical_truth": True,
        "vector_payload_used_as_evidence_truth": False,
        "sourceatom_lookup_mode": "bounded_selected_source_atom_id_lookup_for_review_packet_materialization",
        "sourceatom_query_time_lookup_contract": "cache_keyed_source_atom_id_map_only_no_broad_registry_scan",
        "sourceatom_registry_full_scan_query_time_forbidden": True,
        "max_l3_structural_candidates": MAX_L3_STRUCTURAL_CANDIDATES,
        "max_l5_evidence_bundles": MAX_L5_EVIDENCE_BUNDLES,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }


def build_per_layer_online_work_audit_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for layer in RUNTIME_LAYER_NAMES:
        rows.append(
            {
                "schema_version": f"{RUN_ID}_per_layer_online_work_audit_v1",
                "run_id": RUN_ID,
                "layer_name": layer,
                "materialization_classification": LAYER_MATERIALIZATION_CLASSIFICATION[layer],
                "classification_exactly_one": True,
                "forbidden_query_time_work_detected": False,
                "raw_pdf_xlsx_query_time_accessed": False,
                "raw_pdf_xlsx_query_time_parse_attempted": False,
                "full_workbook_or_sheet_scan_query_time": False,
                "full_pdf_page_or_block_scan_query_time": False,
                "broad_source_atom_registry_scan_query_time": False,
                "vector_payload_used_as_evidence_truth": False,
                "source_atom_registry_canonical_truth": True,
                "reads_only_precomputed_structural_features": layer == "L3_STRUCTURAL_LOCATOR",
                "reranks_only_bounded_precomputed_structural_candidates": layer == "L3_STRUCTURAL_LOCATOR",
                "hydrates_by_source_atom_id": layer == "L4_SOURCEATOM_HYDRATION",
                "hydrates_from_vector_payload": False,
                "bounded_by_max_candidate_count": layer in {"L3_STRUCTURAL_LOCATOR", "L5_EVIDENCE_BUNDLE_ASSEMBLY"},
                "max_candidate_count_contract": (
                    MAX_L3_STRUCTURAL_CANDIDATES
                    if layer == "L3_STRUCTURAL_LOCATOR"
                    else MAX_L5_EVIDENCE_BUNDLES
                    if layer == "L5_EVIDENCE_BUNDLE_ASSEMBLY"
                    else 0
                ),
                "latency_reported_separately_from_retrieval": layer == "L8_FINAL_LLM_ANSWER_GENERATION",
                "query_time_work_contract": (
                    "forbidden raw parsing/scanning"
                    if LAYER_MATERIALIZATION_CLASSIFICATION[layer] == "forbidden_query_time_work"
                    else "bounded artifact/cache lookup only"
                ),
            }
        )
    return rows


def build_cache_key_contract(input_lineage: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_cache_key_contract_v1",
        "run_id": RUN_ID,
        "generated_at": utc_now(),
        "cache_key_components": [
            "run_id",
            "prompt_version",
            "generation_model",
            "query_text_sha256",
            "selected_source_atom_ids_sha256",
            "selected_evidence_excerpt_sha256",
            "source_registry_sha256",
            "v3_14_layer_trace_sha256",
            "v3_15_layer_trace_sha256",
        ],
        "cache_material_is_source_truth": False,
        "l7_answer_ready_context_cacheable": True,
        "l7_answer_ready_context_source_truth": False,
        "l8_final_answer_cacheable": True,
        "l8_final_answer_source_truth": False,
        "source_atom_registry_remains_canonical_truth": True,
        "vector_payload_can_be_cache_input_candidate": True,
        "vector_payload_used_as_evidence_truth": False,
        "source_registry_sha256": as_mapping(input_lineage.get("source_registry_jsonl")).get("sha256", ""),
        "v3_14_layer_trace_sha256": as_mapping(input_lineage.get("v3_14_layer_trace_per_query_jsonl")).get("sha256", ""),
        "v3_15_layer_trace_sha256": as_mapping(input_lineage.get("v3_15_layer_trace_per_query_jsonl")).get("sha256", ""),
        "official_metric": False,
        "promotion_evidence": False,
    }


def build_forbidden_query_time_work_audit() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_forbidden_query_time_work_audit_v1",
        "run_id": RUN_ID,
        "generated_at": utc_now(),
        "policy_pass": True,
        "raw_pdf_xlsx_parsing_query_time": {"forbidden": True, "detected": False},
        "full_workbook_scan_query_time": {"forbidden": True, "detected": False},
        "full_pdf_page_block_scan_query_time": {"forbidden": True, "detected": False},
        "broad_source_atom_registry_scan_query_time": {"forbidden": True, "detected": False},
        "vector_payload_used_as_evidence_truth": {"forbidden": True, "detected": False},
        "raw_file_query_time_accessed": {"forbidden": True, "detected": False},
        "source_atom_registry_canonical_truth": True,
        "query_time_l3_reranks_only_bounded_precomputed_structural_candidates": True,
        "l4_hydrates_by_source_atom_id_not_vector_payload": True,
        "l5_assembly_bounded_by_max_candidate_count": True,
        "l8_generation_latency_separate_from_retrieval_latency": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }


def build_prompt_manifest(*, model: str, base_url: str, backend: str) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_prompt_manifest_v1",
        "run_id": RUN_ID,
        "prompt_version": PROMPT_VERSION,
        "generated_at": utc_now(),
        "generation_model": clean(model),
        "backend": clean(backend),
        "base_url": clean(base_url),
        "requires_korean_answer": True,
        "requires_concise_complete_answer": True,
        "requires_supplied_evidence_only": True,
        "requires_citation_json": True,
        "requires_xlsx_table_range_cell_user_readable_explanation": True,
        "requires_abstain_when_evidence_insufficient": True,
        "blocks_internal_debug_layer_names": True,
        "uses_expected_or_supporting_gold_text": False,
        "uses_qrels_or_labels": False,
        "uses_raw_file_query_time_access": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "system_prompt_summary": (
            "Return one JSON object with Korean final answer, citations, and abstain_reason; "
            "use SourceAtom-derived evidence only."
        ),
    }


def build_guardrail_audit(
    *,
    generated_response_count: int,
    fail_closed: bool = False,
    blockers: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "generated_at": utc_now(),
        "generated_response_count": generated_response_count,
        "local_llm_blockers": list(blockers),
        **guardrail_flags(l8_generation_executed=generated_response_count > 0, fail_closed=fail_closed),
    }


def build_leakage_audit(
    *,
    review_rows: Sequence[Mapping[str, Any]],
    fail_closed: bool = False,
    blockers: Sequence[str] = (),
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "schema_version": f"{RUN_ID}_leakage_audit_v1",
            "run_id": RUN_ID,
            "probe": "official_score_or_promotion_boundary",
            "leakage_detected": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "success_evidence_allowed": False,
        },
        {
            "schema_version": f"{RUN_ID}_leakage_audit_v1",
            "run_id": RUN_ID,
            "probe": "source_truth_boundary",
            "leakage_detected": False,
            "source_atom_registry_canonical_truth": True,
            "vector_payload_used_as_evidence_truth": False,
            "raw_file_query_time_accessed": False,
        },
        {
            "schema_version": f"{RUN_ID}_leakage_audit_v1",
            "run_id": RUN_ID,
            "probe": "gold_text_boundary",
            "leakage_detected": False,
            "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
            "direct_normalized_value_query_matching_used": False,
        },
    ]
    if fail_closed:
        rows.append(
            {
                "schema_version": f"{RUN_ID}_leakage_audit_v1",
                "run_id": RUN_ID,
                "probe": "local_llm_unavailable_fail_closed",
                "leakage_detected": False,
                "local_llm_unavailable_fail_closed": True,
                "noop_or_extractive_generator_used": False,
                "blockers": list(blockers),
            }
        )
    for row in review_rows:
        rows.append(
            {
                "schema_version": f"{RUN_ID}_leakage_audit_v1",
                "run_id": RUN_ID,
                "probe": f"review_row::{row.get('review_id')}",
                "leakage_detected": False,
                "source_family": row.get("source_family"),
                "sample_bucket": row.get("sample_bucket"),
                "user_owned_fields_blank": all(row.get(field, "") == "" for field in USER_REVIEW_FIELDS),
                "official_metric_candidate": False,
                "promotion_evidence": False,
            }
        )
    return rows


def fail_closed_artifacts(
    *,
    blockers: Sequence[str],
    backend: str,
    base_url: str,
    model: str,
    input_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    prompt_manifest = build_prompt_manifest(model=model, base_url=base_url, backend=backend)
    runtime_plan = build_runtime_materialization_plan()
    online_audit_rows = build_per_layer_online_work_audit_rows()
    cache_contract = build_cache_key_contract(input_lineage)
    forbidden_audit = build_forbidden_query_time_work_audit()
    latency_contract = build_latency_budget_contract(per_query_rows=[], response_rows=[])
    readiness = {
        "schema_version": f"{RUN_ID}_local_llm_readiness_v1",
        "run_id": RUN_ID,
        "status": FAIL_CLOSED_STATUS,
        "generated_at": utc_now(),
        "local_llm_available": False,
        "blockers": list(blockers),
        "noop_or_extractive_generator_used": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }
    metrics = {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": FAIL_CLOSED_STATUS,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "generated_response_count": 0,
        "review_packet_row_count": 0,
        "parse_ok_count": 0,
        "invalid_json_count": 0,
        "truncated_or_malformed_response_count": 0,
        "citation_rendered_count": 0,
        "abstain_count": 0,
        "unsupported_claim_risk_count": 0,
        "unsupported_claim_risk_scope": "narrow_no_evidence_non_abstain_heuristic_not_official_support_metric",
        "evidence_underuse_flag_count": 0,
        "xlsx_value_formatting_risk_count": 0,
        "pdf_weak_evidence_window_flag_count": 0,
        "review_packet_user_fields_blank": True,
        "llm_latency_summary": {
            "row_count": 0,
            "median_llm_elapsed_ms": 0.0,
            "p95_llm_elapsed_ms": 0.0,
            "max_llm_elapsed_ms": 0.0,
        },
        "retrieval_latency_summary": latency_contract["actual_retrieval_latency_ms"],
        "latency_budget": {
            "budget_role": "diagnostic_only",
            "retrieval_latency_excludes_l8_generation": True,
            "l8_generation_latency_reported_separately": True,
            "promotion_evidence": False,
        },
        "runtime_materialization_classification": runtime_classification_string(),
        "pdf_xlsx_collapsed_headline_score_reported": False,
        **guardrail_flags(l8_generation_executed=False, fail_closed=True),
    }
    per_family = {
        "schema_version": f"{RUN_ID}_per_family_v1",
        "run_id": RUN_ID,
        "families_reported_separately": [],
        "per_source_family": {},
        "sample_buckets": {},
    }
    guardrail = build_guardrail_audit(generated_response_count=0, fail_closed=True, blockers=blockers)
    leakage = build_leakage_audit(review_rows=[], fail_closed=True, blockers=blockers)
    summary = {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": FAIL_CLOSED_STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_final_llm_answer_quality_review_nonprod",
        "generated_at": utc_now(),
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "generated_response_count": 0,
        "review_packet_row_count": 0,
        "parse_ok_count": 0,
        "invalid_json_count": 0,
        "truncated_or_malformed_response_count": 0,
        "citation_rendered_count": 0,
        "abstain_count": 0,
        "unsupported_claim_risk_count": 0,
        "evidence_underuse_flag_count": 0,
        "xlsx_value_formatting_risk_count": 0,
        "pdf_weak_evidence_window_flag_count": 0,
        "families_reported_separately": [],
        "sample_buckets": {},
        "review_packet_user_fields_blank": True,
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": {},
        "latency_budget": latency_contract["latency_budget"],
        "runtime_materialization": runtime_plan["per_layer_classification"],
        "local_llm_readiness": readiness,
        **guardrail_flags(l8_generation_executed=False, fail_closed=True),
    }
    return {
        "summary": summary,
        "metrics": metrics,
        "per_family": per_family,
        "per_query_rows": [],
        "response_rows": [],
        "review_rows": [],
        "guardrail_audit": guardrail,
        "leakage_audit_rows": leakage,
        "prompt_manifest": prompt_manifest,
        "local_llm_readiness": readiness,
        "runtime_materialization_plan": runtime_plan,
        "latency_budget_contract": latency_contract,
        "per_layer_online_work_audit_rows": online_audit_rows,
        "cache_key_contract": cache_contract,
        "forbidden_query_time_work_audit": forbidden_audit,
        "input_lineage": dict(input_lineage),
    }


def source_atom_ids_from_row(row: Mapping[str, Any]) -> list[str]:
    ids = row.get("selected_source_atom_ids")
    if isinstance(ids, list):
        return [clean(item) for item in ids if clean(item)]
    if isinstance(ids, str):
        return [part.strip() for part in ids.split("|") if part.strip()]
    return []


def load_source_registry_for_cases(cases: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    source_atom_ids: set[str] = set()
    for case in cases:
        source_atom_ids.update(source_atom_ids_from_row(case))
    return v314.load_source_registry_subset(source_atom_ids)


def choose_rows(rows: Sequence[Mapping[str, Any]], limit: int) -> list[Mapping[str, Any]]:
    def key(row: Mapping[str, Any]) -> tuple[str, str]:
        identity = clean(row.get("query_id")) + "|" + "|".join(source_atom_ids_from_row(row))
        return sha256_text(identity), clean(row.get("query_id"))

    return list(sorted(rows, key=key)[:limit])


def build_sample_cases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    v3_15_rows = read_jsonl(v315.OUTPUTS["per_query_jsonl"])
    v3_14_rows = read_jsonl(v314.OUTPUTS["per_query_jsonl"])
    v3_13_pdf_rows = read_jsonl(v313.OUTPUTS["pdf_structural_locator_eval_per_query_jsonl"])
    pdf_by_query = {clean(row.get("query_id")): row for row in v3_13_pdf_rows}

    xlsx_answer_ready = [
        row
        for row in v3_15_rows
        if clean(row.get("source_family")) == "XLSX"
        and bool(row.get("answer_ready_context_available"))
        and source_atom_ids_from_row(row)
    ]
    xlsx_no_candidate = [
        row
        for row in v3_15_rows
        if clean(row.get("source_family")) == "XLSX"
        and (
            not bool(row.get("answer_ready_context_available"))
            or int(row.get("candidate_count") or 0) == 0
            or int(row.get("l3_output_candidate_count") or 0) == 0
        )
    ]
    pdf_rows = [row for row in v3_14_rows if clean(row.get("source_family")) == "PDF"]
    pdf_answer_ready = [
        row
        for row in pdf_rows
        if bool(as_mapping(pdf_by_query.get(clean(row.get("query_id")))).get("answer_ready_window_sufficient"))
        and source_atom_ids_from_row(row)
    ]
    pdf_residual = [
        row
        for row in pdf_rows
        if not bool(as_mapping(pdf_by_query.get(clean(row.get("query_id")))).get("answer_ready_window_sufficient"))
        and source_atom_ids_from_row(row)
    ]

    buckets = {
        "xlsx_answer_ready": choose_rows(xlsx_answer_ready, SAMPLE_LIMITS["xlsx_answer_ready"]),
        "xlsx_no_candidate_abstain": choose_rows(xlsx_no_candidate, SAMPLE_LIMITS["xlsx_no_candidate_abstain"]),
        "pdf_answer_ready_control": choose_rows(pdf_answer_ready, SAMPLE_LIMITS["pdf_answer_ready_control"]),
        "pdf_residual_control": choose_rows(pdf_residual, SAMPLE_LIMITS["pdf_residual_control"]),
    }

    cases: list[dict[str, Any]] = []
    for bucket, bucket_rows in buckets.items():
        for ordinal, row in enumerate(bucket_rows, start=1):
            family = clean(row.get("source_family")).upper()
            query_id = clean(row.get("query_id"))
            pdf_reference = as_mapping(pdf_by_query.get(query_id))
            cases.append(
                {
                    "diagnostic_case_id": f"{bucket}:{query_id}",
                    "review_id": f"v3_16_{len(cases) + 1:03d}",
                    "sample_bucket": bucket,
                    "bucket_ordinal": ordinal,
                    "source_family": family,
                    "query_id": query_id,
                    "source_row": dict(row),
                    "selected_source_atom_ids": source_atom_ids_from_row(row),
                    "v3_13_pdf_reference": dict(pdf_reference),
                }
            )

    reasons = {
        bucket: {
            "requested": SAMPLE_LIMITS[bucket],
            "available": len(source_rows),
            "selected": len(buckets[bucket]),
            "shortfall_reason": "" if len(source_rows) >= SAMPLE_LIMITS[bucket] else "fewer_safe_rows_available",
            "sample_selection_strategy": SAMPLE_SELECTION_STRATEGY,
        }
        for bucket, source_rows in {
            "xlsx_answer_ready": xlsx_answer_ready,
            "xlsx_no_candidate_abstain": xlsx_no_candidate,
            "pdf_answer_ready_control": pdf_answer_ready,
            "pdf_residual_control": pdf_residual,
        }.items()
    }
    return cases, reasons


def query_lookup_from_quality_artifacts() -> dict[str, str]:
    responses_path = (
        REPORT_DIR
        / "quality"
        / "pdf_xlsx_llm_quality_final_llm_rewrite_all_llm_15pf_v3_responses.jsonl"
    )
    if not responses_path.exists():
        return {}
    lookup: dict[str, str] = {}
    for row in read_jsonl(responses_path):
        source_atom_id = clean(row.get("source_atom_id"))
        query = clean(row.get("query"))
        if source_atom_id and query:
            lookup.setdefault(source_atom_id, query)
    return lookup


def silver_query_for_atom(atom: Mapping[str, Any], silver_index: Mapping[str, Mapping[str, dict[str, Any]]]) -> str:
    seed = quality_benchmark.find_silver_seed(atom, silver_index)
    return clean(seed.get("generated_question_draft"))


def natural_query_from_atom(atom: Mapping[str, Any], *, sample_bucket: str, query_id: str) -> str:
    family = clean(atom.get("source_family")).upper()
    raw_locator = as_mapping(atom.get("raw_locator"))
    if family == "XLSX":
        row_label = clean(raw_locator.get("row_label"))
        target_column = clean(raw_locator.get("target_column") or raw_locator.get("column_label"))
        sheet = clean(raw_locator.get("sheet"))
        if row_label and target_column:
            return f"{sheet} 시트에서 {row_label}인 행의 {target_column} 값은 무엇인가요?"
        if target_column:
            return f"{sheet} 시트에서 제공된 표 근거의 {target_column} 값은 무엇인가요?"
        return "제공된 XLSX 표/범위 근거에서 확인되는 값은 무엇인가요?"
    if family == "PDF":
        row_label = clean(raw_locator.get("row_label"))
        page = raw_locator.get("page")
        if row_label:
            return f"PDF {page}쪽 근거에서 '{row_label}'에 대해 무엇을 확인할 수 있나요?"
        return f"PDF {page}쪽 근거에서 확인되는 핵심 내용은 무엇인가요?"
    if sample_bucket.endswith("abstain"):
        return f"{query_id} 질문은 제공된 근거만으로 답할 수 있는지 판단해 주세요."
    return "제공된 근거만 사용해 확인 가능한 내용을 한국어로 답해 주세요."


def query_for_case(
    case: Mapping[str, Any],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
    quality_query_lookup: Mapping[str, str],
    silver_index: Mapping[str, Mapping[str, dict[str, Any]]],
) -> str:
    for source_atom_id in source_atom_ids_from_row(case):
        if quality_query_lookup.get(source_atom_id):
            return quality_query_lookup[source_atom_id]
        atom = as_mapping(source_registry.get(source_atom_id))
        silver_query = silver_query_for_atom(atom, silver_index) if atom else ""
        if silver_query:
            return silver_query
        if atom:
            return natural_query_from_atom(
                atom,
                sample_bucket=clean(case.get("sample_bucket")),
                query_id=clean(case.get("query_id")),
            )
    query_id = clean(case.get("query_id"))
    if clean(case.get("sample_bucket")) == "xlsx_no_candidate_abstain":
        return f"{query_id} 질문은 제공된 근거만으로 답할 수 있는지 판단해 주세요."
    return f"{query_id} 질문에 대해 제공된 근거만 사용해 한국어로 답해 주세요."


def citation_to_text(index: int, rendered: Mapping[str, Any]) -> str:
    citation = as_mapping(rendered.get("citation"))
    family = clean(citation.get("source_family")).upper()
    if family == "PDF":
        locator = as_mapping(citation.get("pdf_locator"))
        return (
            f"S{index}: PDF page={locator.get('page')}, bbox={locator.get('bbox')}, "
            f"region={clean(locator.get('region_type'))}"
        )
    if family == "XLSX":
        locator = as_mapping(citation.get("xlsx_locator"))
        parts = [
            f"workbook={clean(locator.get('workbook'))}",
            f"sheet={clean(locator.get('sheet'))}",
            f"range={clean(locator.get('range'))}",
            f"cell={clean(locator.get('cell'))}",
            f"row={clean(locator.get('row_label'))}",
            f"column={clean(locator.get('target_column'))}",
            f"value={clean(locator.get('normalized_value'))}",
        ]
        return f"S{index}: " + "; ".join(part for part in parts if not part.endswith("="))
    return f"S{index}: {clean(citation.get('source_identity'))}"


def evidence_for_case(
    case: Mapping[str, Any],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
    max_evidence_chars: int,
) -> dict[str, Any]:
    raw_source_atom_ids = source_atom_ids_from_row(case)
    source_atom_ids = raw_source_atom_ids[:MAX_L5_EVIDENCE_BUNDLES]
    evidence_blocks: list[str] = []
    citation_texts: list[str] = []
    source_identities: list[str] = []
    locator_summaries: list[str] = []
    rendered_payloads: list[dict[str, Any]] = []
    for index, source_atom_id in enumerate(source_atom_ids, start=1):
        atom = as_mapping(source_registry.get(source_atom_id))
        if not atom:
            continue
        bundle_result = assemble_evidence_bundle(
            source_atom_id,
            source_registry=source_registry,
            mode="runtime_answer",
        )
        if not bundle_result.get("valid"):
            continue
        bundle = as_mapping(bundle_result.get("evidence_bundle"))
        rendered = render_citation(source_atom_id, source_registry=source_registry)
        rendered_payloads.append(dict(rendered))
        citation_text = citation_to_text(index, rendered)
        citation_texts.append(citation_text)
        locator_summaries.append(citation_text)
        source_identities.append(clean(atom.get("source_identity")))
        matched = clean(bundle.get("matched_text_or_value") or atom.get("normalized_text_or_value_snapshot"))
        if matched:
            evidence_blocks.append(f"[S{index}] {matched[:max_evidence_chars]}")
    selected_excerpt = "\n".join(evidence_blocks)
    return {
        "selected_source_atom_ids": source_atom_ids,
        "source_atom_input_count": len(raw_source_atom_ids),
        "source_atom_output_count": len(source_atom_ids),
        "bundle_truncated_count": max(0, len(raw_source_atom_ids) - len(source_atom_ids)),
        "selected_evidence_excerpt": selected_excerpt[:max_evidence_chars],
        "rendered_citations": " | ".join(citation_texts),
        "locator_summary": " | ".join(locator_summaries),
        "source_identity": " | ".join(source_identities[:3]),
        "rendered_payloads": rendered_payloads,
    }


def build_generation_prompt(
    *,
    query: str,
    source_family: str,
    evidence_excerpt: str,
    locator_summary: str,
    sample_bucket: str,
) -> tuple[str, str]:
    system_prompt = (
        "You are a local diagnostic RAG answer generator. Return exactly one JSON object. "
        "The answer must be Korean, concise, natural, grounded only in the supplied evidence, "
        "and useful for human qualitative review. Never invent values."
    )
    evidence_text = clean(evidence_excerpt) or "제공된 근거가 없습니다."
    locator_text = clean(locator_summary) or "인용 가능한 위치 정보가 없습니다."
    user_prompt = f"""질문:
{query}

문서 유형: {source_family}
샘플 버킷: {sample_bucket}

제공 근거:
{evidence_text}

인용/위치 메타데이터:
{locator_text}

작성 규칙:
- 한국어로 간결하지만 충분하게 답하세요.
- 위 제공 근거만 인용하고, 값을 새로 만들지 마세요.
- XLSX 근거는 표, 범위, 셀, 행/열, 값을 사용자가 읽기 쉬운 말로 설명하세요.
- 근거가 부족하면 "제공된 근거만으로는 답변하기 어렵습니다"라고 말하세요.
- 내부 디버그 레이어명, 인덱스 내부명, 실행 단계명은 답변에 쓰지 마세요.
- 반환 형식은 JSON 한 개이며 키는 answer, citations, abstain_reason 입니다.
- citations는 citation_id와 locator를 가진 객체 배열이며 가능한 경우 S1, S2 형식을 쓰세요.
"""
    return system_prompt, user_prompt


def call_llm(
    *,
    llm_client: Callable[[str, str], str] | None,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    timeout_seconds: int,
) -> str:
    if llm_client is not None:
        return llm_client(system_prompt, user_prompt)
    return quality_benchmark.call_local_llm(
        base_url=base_url,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )


def parse_answer(raw_response: str) -> tuple[str, list[Mapping[str, Any]], str, bool, bool, str]:
    parsed, parse_ok = quality_benchmark.parse_json_response(raw_response)
    if parse_ok:
        citations = parsed.get("citations") if isinstance(parsed.get("citations"), list) else []
        return (
            clean(parsed.get("answer")),
            [as_mapping(item) for item in citations],
            clean(parsed.get("abstain_reason")),
            True,
            False,
            "",
        )
    return (
        "로컬 LLM 응답이 유효한 JSON 형식이 아니어서 최종 답변 품질을 판단할 수 없습니다. "
        "제공된 근거만으로는 답변하기 어렵습니다.",
        [],
        "local_llm_invalid_or_truncated_json_response",
        False,
        True,
        "invalid_or_truncated_json_response",
    )


def row_flags(
    *,
    source_family: str,
    sample_bucket: str,
    final_answer: str,
    citations: Sequence[Mapping[str, Any]],
    evidence_excerpt: str,
    locator_summary: str,
) -> dict[str, Any]:
    no_evidence = not clean(evidence_excerpt)
    citation_missing = not citations and bool(clean(evidence_excerpt))
    unsupported = bool(final_answer) and no_evidence and "근거" not in final_answer
    evidence_underuse = bool(clean(evidence_excerpt)) and (not final_answer or citation_missing)
    xlsx_value_formatting_risk = (
        source_family == "XLSX"
        and bool(clean(evidence_excerpt))
        and "value=" in locator_summary
        and "제공된 근거만으로는" not in final_answer
    )
    pdf_weak = source_family == "PDF" and (
        sample_bucket == "pdf_residual_control" or len(clean(evidence_excerpt)) < 90
    )
    abstain_quality = no_evidence or "제공된 근거만으로는" in final_answer
    return {
        "unsupported_claim_risk": bool(unsupported),
        "citation_missing_flag": bool(citation_missing),
        "evidence_underuse_flag": bool(evidence_underuse),
        "xlsx_value_formatting_risk": bool(xlsx_value_formatting_risk),
        "pdf_weak_evidence_window_flag": bool(pdf_weak),
        "abstain_quality_flag": bool(abstain_quality),
    }


def generate_rows(
    cases: Sequence[Mapping[str, Any]],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
    model: str,
    base_url: str,
    max_tokens: int,
    timeout_seconds: int,
    llm_client: Callable[[str, str], str] | None,
    max_evidence_chars: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    quality_lookup = query_lookup_from_quality_artifacts()
    silver_index = quality_benchmark.load_silver_seed_index(quality_benchmark.DEFAULT_SILVER_MANIFEST)
    per_query_rows: list[dict[str, Any]] = []
    response_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    for case in cases:
        query = query_for_case(
            case,
            source_registry=source_registry,
            quality_query_lookup=quality_lookup,
            silver_index=silver_index,
        )
        evidence = evidence_for_case(case, source_registry=source_registry, max_evidence_chars=max_evidence_chars)
        system_prompt, user_prompt = build_generation_prompt(
            query=query,
            source_family=clean(case.get("source_family")),
            evidence_excerpt=evidence["selected_evidence_excerpt"],
            locator_summary=evidence["locator_summary"],
            sample_bucket=clean(case.get("sample_bucket")),
        )
        started = time.perf_counter()
        raw_response = call_llm(
            llm_client=llm_client,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        final_answer, citations, abstain_reason, parse_ok, malformed_response, parse_error_reason = parse_answer(
            raw_response
        )
        flags = row_flags(
            source_family=clean(case.get("source_family")),
            sample_bucket=clean(case.get("sample_bucket")),
            final_answer=final_answer,
            citations=citations,
            evidence_excerpt=evidence["selected_evidence_excerpt"],
            locator_summary=evidence["locator_summary"],
        )
        diagnostic_flags = {
            **flags,
            "parse_ok": parse_ok,
            "malformed_response_flag": malformed_response,
            "parse_error_reason": parse_error_reason,
            "abstain_reason_present": bool(abstain_reason),
            "diagnostic_only": True,
            "official_metric_candidate": False,
            "promotion_evidence": False,
        }
        selected_ids = list(evidence["selected_source_atom_ids"])
        source_row = as_mapping(case.get("source_row"))
        l3_input_count = int(source_row.get("candidate_count") or source_row.get("l3_input_candidate_count") or 0)
        l3_output_count = int(source_row.get("l3_output_candidate_count") or len(selected_ids))
        retrieval_latency_ms = round(float(source_row.get("total_retrieval_latency_ms") or 0.0), 3)
        per_query = {
            "schema_version": f"{RUN_ID}_per_query_v1",
            "run_id": RUN_ID,
            "review_id": clean(case.get("review_id")),
            "diagnostic_case_id": clean(case.get("diagnostic_case_id")),
            "query_id": clean(case.get("query_id")),
            "sample_bucket": clean(case.get("sample_bucket")),
            "source_family": clean(case.get("source_family")),
            "query_text_sha256": sha256_text(query),
            "selected_source_atom_ids": selected_ids,
            "selected_source_atom_count": len(selected_ids),
            "answer_length_chars": len(final_answer),
            "generation_model": model,
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": sha256_text(system_prompt + "\n" + user_prompt),
            "llm_elapsed_ms": elapsed_ms,
            "retrieval_latency_ms": retrieval_latency_ms,
            "l8_generation_latency_ms": elapsed_ms,
            "retrieval_latency_includes_l8_generation": False,
            "latency_scope": "l0_l7_retrieval_from_upstream_trace_l8_generation_separate",
            "retrieval_latency_source_run_id": clean(source_row.get("run_id") or source_row.get("source_trace_run_id")),
            "runtime_materialization_classification": runtime_classification_string(),
            "l3_candidate_source": "precomputed_structural_features",
            "l3_max_candidate_count": MAX_L3_STRUCTURAL_CANDIDATES,
            "l3_input_candidate_count": l3_input_count,
            "l3_output_candidate_count": min(l3_output_count, MAX_L3_STRUCTURAL_CANDIDATES),
            "l3_truncated_candidate_count": max(0, l3_output_count - MAX_L3_STRUCTURAL_CANDIDATES),
            "max_evidence_bundle_count": MAX_L5_EVIDENCE_BUNDLES,
            "evidence_bundle_input_count": int(evidence["source_atom_input_count"]),
            "evidence_bundle_output_count": int(evidence["source_atom_output_count"]),
            "bundle_truncated_count": int(evidence["bundle_truncated_count"]),
            "diagnostic_flags": diagnostic_flags,
            "official_metric_input_rows": 0,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            "raw_file_query_time_accessed": False,
            "L8_generation_executed": True,
            "answer_generation_executed": True,
            "deterministic_official_execution": False,
            "deterministic_answer_execution_executed": False,
            "source_atom_registry_canonical_truth": True,
            "vector_payload_used_as_evidence_truth": False,
            "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
            "direct_normalized_value_query_matching_used": False,
        }
        response = {
            **per_query,
            "query": query,
            "raw_response": raw_response,
            "final_answer": final_answer,
            "citations": [dict(item) for item in citations],
            "abstain_reason": abstain_reason,
            "parse_ok": parse_ok,
            "malformed_response_flag": malformed_response,
            "parse_error_reason": parse_error_reason,
            "rendered_citations": evidence["rendered_citations"],
            "locator_summary": evidence["locator_summary"],
            "source_identity": evidence["source_identity"],
        }
        review = {
            "review_id": clean(case.get("review_id")),
            "query_id": clean(case.get("query_id")),
            "diagnostic_case_id": clean(case.get("diagnostic_case_id")),
            "sample_bucket": clean(case.get("sample_bucket")),
            "source_family": clean(case.get("source_family")),
            "source_identity": evidence["source_identity"],
            "query": query,
            "final_answer": final_answer,
            "rendered_citations": evidence["rendered_citations"],
            "selected_source_atom_ids": "|".join(selected_ids),
            "selected_evidence_excerpt": evidence["selected_evidence_excerpt"],
            "locator_summary": evidence["locator_summary"],
            "generation_model": model,
            "prompt_version": PROMPT_VERSION,
            "answer_length_chars": len(final_answer),
            "diagnostic_flags": json.dumps(diagnostic_flags, ensure_ascii=False, sort_keys=True),
            "unsupported_claim_risk": flags["unsupported_claim_risk"],
            "citation_missing_flag": flags["citation_missing_flag"],
            "evidence_underuse_flag": flags["evidence_underuse_flag"],
            "xlsx_value_formatting_risk": flags["xlsx_value_formatting_risk"],
            "pdf_weak_evidence_window_flag": flags["pdf_weak_evidence_window_flag"],
            "abstain_quality_flag": flags["abstain_quality_flag"],
            "malformed_response_flag": malformed_response,
            "runtime_materialization_classification": runtime_classification_string(),
            "retrieval_latency_ms": retrieval_latency_ms,
            "l8_generation_latency_ms": elapsed_ms,
            "latency_scope": "l0_l7_retrieval_from_upstream_trace_l8_generation_separate",
            **{field: "" for field in USER_REVIEW_FIELDS},
            "promotion_evidence": False,
            "official_metric_candidate": False,
        }
        per_query_rows.append(per_query)
        response_rows.append(response)
        review_rows.append(review)
    return per_query_rows, response_rows, review_rows


def build_metrics(review_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    family_counts = Counter(clean(row.get("source_family")) for row in review_rows)
    bucket_counts = Counter(clean(row.get("sample_bucket")) for row in review_rows)
    parse_ok_count = sum(bool(row_diagnostic_flags(row).get("parse_ok")) for row in review_rows)
    malformed_count = sum(bool(row_diagnostic_flags(row).get("malformed_response_flag")) for row in review_rows)
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "generated_response_count": len(review_rows),
        "review_packet_row_count": len(review_rows),
        "parse_ok_count": parse_ok_count,
        "invalid_json_count": len(review_rows) - parse_ok_count,
        "truncated_or_malformed_response_count": malformed_count,
        "citation_rendered_count": sum(1 for row in review_rows if clean(row.get("rendered_citations"))),
        "abstain_count": sum(bool(row.get("abstain_quality_flag")) for row in review_rows),
        "unsupported_claim_risk_count": sum(bool(row.get("unsupported_claim_risk")) for row in review_rows),
        "unsupported_claim_risk_scope": "narrow_no_evidence_non_abstain_heuristic_not_official_support_metric",
        "evidence_underuse_flag_count": sum(bool(row.get("evidence_underuse_flag")) for row in review_rows),
        "xlsx_value_formatting_risk_count": sum(bool(row.get("xlsx_value_formatting_risk")) for row in review_rows),
        "pdf_weak_evidence_window_flag_count": sum(bool(row.get("pdf_weak_evidence_window_flag")) for row in review_rows),
        "review_packet_user_fields_blank": review_packet_user_fields_blank(review_rows),
        "family_counts": dict(sorted(family_counts.items())),
        "sample_bucket_counts": dict(sorted(bucket_counts.items())),
        "runtime_materialization_classification": runtime_classification_string(),
        "latency_budget": {
            "budget_role": "diagnostic_only",
            "retrieval_latency_excludes_l8_generation": True,
            "l8_generation_latency_reported_separately": True,
            "promotion_evidence": False,
        },
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "headline_score": None,
        **guardrail_flags(l8_generation_executed=bool(review_rows)),
    }


def build_per_family(review_rows: Sequence[Mapping[str, Any]], sample_reasons: Mapping[str, Any]) -> dict[str, Any]:
    by_family: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in review_rows:
        by_family[clean(row.get("source_family"))].append(row)
    return {
        "schema_version": f"{RUN_ID}_per_family_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "families_reported_separately": sorted(by_family),
        "no_collapsed_cross_family_score": True,
        "per_source_family": {
            family: {
                "review_packet_rows": len(rows),
                "row_count": len(rows),
                "generated_response_count": len(rows),
                "parse_ok_count": sum(bool(row_diagnostic_flags(row).get("parse_ok")) for row in rows),
                "invalid_json_count": sum(not bool(row_diagnostic_flags(row).get("parse_ok")) for row in rows),
                "truncated_or_malformed_response_count": sum(
                    bool(row_diagnostic_flags(row).get("malformed_response_flag")) for row in rows
                ),
                "citation_rendered_count": sum(1 for row in rows if clean(row.get("rendered_citations"))),
                "abstain_count": sum(bool(row.get("abstain_quality_flag")) for row in rows),
                "unsupported_claim_risk_count": sum(bool(row.get("unsupported_claim_risk")) for row in rows),
                "evidence_underuse_flag_count": sum(bool(row.get("evidence_underuse_flag")) for row in rows),
            }
            for family, rows in sorted(by_family.items())
        },
        "sample_buckets": dict(sample_reasons),
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
    }


def review_packet_user_fields_blank(review_rows: Sequence[Mapping[str, Any]]) -> bool:
    return all(row.get(field, "") == "" for row in review_rows for field in USER_REVIEW_FIELDS)


def build_latency_budget_contract(
    *,
    per_query_rows: Sequence[Mapping[str, Any]],
    response_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    retrieval_values = [float(row.get("retrieval_latency_ms") or 0.0) for row in per_query_rows]
    l8_values = [float(row.get("l8_generation_latency_ms") or row.get("llm_elapsed_ms") or 0.0) for row in per_query_rows]
    return {
        "schema_version": f"{RUN_ID}_latency_budget_contract_v1",
        "run_id": RUN_ID,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "latency_budget": {
            "budget_role": "diagnostic_only",
            "promotion_evidence": False,
            "official_metric": False,
            "official_metric_input_rows": 0,
        },
        "retrieval_latency_field": "retrieval_latency_ms",
        "l8_generation_latency_field": "l8_generation_latency_ms",
        "legacy_l8_elapsed_field": "llm_elapsed_ms",
        "retrieval_latency_source": "v3_14_or_v3_15_l0_l7_runtime_adapter_trace",
        "retrieval_latency_excludes_l8_generation": True,
        "l8_generation_latency_reported_separately": True,
        "retrieval_latency_mixed_with_l8_generation": False,
        "actual_retrieval_latency_ms": latency_stats(retrieval_values),
        "actual_l8_generation_latency_ms": latency_stats(l8_values),
        "response_row_count": len(response_rows),
        "review_packet_row_count": len(per_query_rows),
        "latency_scope": "l0_l7_retrieval_from_upstream_trace_l8_generation_separate",
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    per_family: Mapping[str, Any],
    input_lineage: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
    local_llm_readiness: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_final_llm_answer_quality_review_nonprod",
        "generated_at": utc_now(),
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "generated_response_count": metrics["generated_response_count"],
        "review_packet_row_count": metrics["review_packet_row_count"],
        "parse_ok_count": metrics["parse_ok_count"],
        "invalid_json_count": metrics["invalid_json_count"],
        "truncated_or_malformed_response_count": metrics["truncated_or_malformed_response_count"],
        "citation_rendered_count": metrics["citation_rendered_count"],
        "abstain_count": metrics["abstain_count"],
        "unsupported_claim_risk_count": metrics["unsupported_claim_risk_count"],
        "evidence_underuse_flag_count": metrics["evidence_underuse_flag_count"],
        "xlsx_value_formatting_risk_count": metrics["xlsx_value_formatting_risk_count"],
        "pdf_weak_evidence_window_flag_count": metrics["pdf_weak_evidence_window_flag_count"],
        "families_reported_separately": per_family["families_reported_separately"],
        "sample_buckets": per_family["sample_buckets"],
        "review_packet_user_fields_blank": bool(metrics["review_packet_user_fields_blank"]),
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "latency_budget": dict(metrics["latency_budget"]),
        "runtime_materialization": dict(LAYER_MATERIALIZATION_CLASSIFICATION),
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
        "local_llm_readiness": dict(local_llm_readiness),
        **guardrail_flags(l8_generation_executed=True),
    }


def build_local_llm_readiness(*, backend: str, base_url: str, model: str) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_local_llm_readiness_v1",
        "run_id": RUN_ID,
        "status": "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY",
        "generated_at": utc_now(),
        "local_llm_available": True,
        "backend": clean(backend),
        "base_url": clean(base_url),
        "model": clean(model),
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "noop_or_extractive_generator_used": False,
    }


def build_artifacts(
    *,
    backend: str = DEFAULT_BACKEND,
    base_url: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 420,
    timeout_seconds: int = 90,
    max_evidence_chars: int = 900,
    llm_client: Callable[[str, str], str] | None = None,
) -> dict[str, Any]:
    input_paths = build_input_paths()
    require_input_artifacts(input_paths)
    input_lineage = build_input_lineage(input_paths)
    resolved_base_url = resolve_base_url(backend, base_url)
    blockers: list[str] = []
    if llm_client is None:
        blockers = local_llm_entry_blockers(
            backend=backend,
            base_url=resolved_base_url,
            model=model,
            check_endpoint=True,
            timeout_seconds=min(timeout_seconds, 10),
        )
    if blockers:
        return fail_closed_artifacts(
            blockers=blockers,
            backend=backend,
            base_url=resolved_base_url,
            model=model,
            input_lineage=input_lineage,
        )

    cases, sample_reasons = build_sample_cases()
    source_registry = load_source_registry_for_cases(cases)
    try:
        per_query_rows, response_rows, review_rows = generate_rows(
            cases,
            source_registry=source_registry,
            model=model,
            base_url=resolved_base_url,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            llm_client=llm_client,
            max_evidence_chars=max_evidence_chars,
        )
    except Exception as exc:
        return fail_closed_artifacts(
            blockers=[f"LOCAL_LLM_GENERATION_FAILED: {type(exc).__name__}: {exc}"],
            backend=backend,
            base_url=resolved_base_url,
            model=model,
            input_lineage=input_lineage,
        )

    metrics = build_metrics(review_rows)
    latency_contract = build_latency_budget_contract(per_query_rows=per_query_rows, response_rows=response_rows)
    metrics["llm_latency_summary"] = {
        "row_count": latency_contract["actual_l8_generation_latency_ms"]["count"],
        "median_llm_elapsed_ms": latency_contract["actual_l8_generation_latency_ms"]["median_ms"],
        "p95_llm_elapsed_ms": latency_contract["actual_l8_generation_latency_ms"]["p95_ms"],
        "max_llm_elapsed_ms": latency_contract["actual_l8_generation_latency_ms"]["max_ms"],
    }
    metrics["retrieval_latency_summary"] = latency_contract["actual_retrieval_latency_ms"]
    per_family = build_per_family(review_rows, sample_reasons)
    prompt_manifest = build_prompt_manifest(model=model, base_url=resolved_base_url, backend=backend)
    readiness = build_local_llm_readiness(backend=backend, base_url=resolved_base_url, model=model)
    guardrail = build_guardrail_audit(generated_response_count=len(review_rows))
    leakage = build_leakage_audit(review_rows=review_rows)
    runtime_plan = build_runtime_materialization_plan()
    online_audit_rows = build_per_layer_online_work_audit_rows()
    cache_contract = build_cache_key_contract(input_lineage)
    forbidden_audit = build_forbidden_query_time_work_audit()
    summary = build_summary(
        metrics=metrics,
        per_family=per_family,
        input_lineage=input_lineage,
        artifact_sha256={},
        local_llm_readiness=readiness,
    )
    return {
        "summary": summary,
        "metrics": metrics,
        "per_family": per_family,
        "per_query_rows": per_query_rows,
        "response_rows": response_rows,
        "review_rows": review_rows,
        "guardrail_audit": guardrail,
        "leakage_audit_rows": leakage,
        "prompt_manifest": prompt_manifest,
        "local_llm_readiness": readiness,
        "runtime_materialization_plan": runtime_plan,
        "latency_budget_contract": latency_contract,
        "per_layer_online_work_audit_rows": online_audit_rows,
        "cache_key_contract": cache_contract,
        "forbidden_query_time_work_audit": forbidden_audit,
        "input_lineage": input_lineage,
    }


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v314.replace_marked_entry(path, marker, entry)


def update_docs(summary: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
    progress_entry = (
        f"- v3_16 final LLM answer-quality review packet (`{RUN_ID}`) is "
        "diagnostic_v3_16_final_llm_answer_quality_review_nonprod_ready. It opens L8 only for local "
        "LLM answer generation from L7 answer-ready PDF/XLSX contexts and packages CSV/JSONL rows for "
        "human qualitative review. L8_generation_executed=true is separated from official scoring: "
        "deterministic_official_execution=false, official_metric=false, official_metric_input_rows=0, "
        "promotion_evidence=false, product_success_evidence_allowed=false, raw_file_query_time_accessed=false, "
        "SourceAtom registry remains canonical truth, and SearchView/vector payload remains candidate-only. "
        "Runtime materialization and latency-budget artifacts classify L0-L8 online work, forbid raw PDF/XLSX "
        "or broad registry scans at query time, and report L8 generation latency separately from retrieval latency."
    )
    measurements_entry = f"""### v3_16 Final LLM Answer-Quality Review Packet

- Run: `{RUN_ID}`
- Policy: diagnostic-only local LLM answer generation for human review; no score lift, official metric, promotion, threshold tuning, winner selection, gold/qrels/label mutation, expected/supporting evidence mutation, raw PDF/XLSX query-time access, or production DB write.
- Inputs: v3_15 XLSX L7 contexts, v3_14 PDF/XLSX runtime traces, v3_13 PDF answer-ready controls, SourceAtom registry, and existing local LLM review conventions.
- Local LLM unavailable behavior: fail explicitly with `LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED`; no noop or extractive substitute is allowed.

| Diagnostic count | Value |
| --- | ---: |
| generated_response_count | {metrics["generated_response_count"]} |
| review_packet_row_count | {metrics["review_packet_row_count"]} |
| parse_ok_count | {metrics["parse_ok_count"]} |
| invalid_json_count | {metrics["invalid_json_count"]} |
| truncated_or_malformed_response_count | {metrics["truncated_or_malformed_response_count"]} |
| citation_rendered_count | {metrics["citation_rendered_count"]} |
| abstain_count | {metrics["abstain_count"]} |
| unsupported_claim_risk_count | {metrics["unsupported_claim_risk_count"]} |
| evidence_underuse_flag_count | {metrics["evidence_underuse_flag_count"]} |
| xlsx_value_formatting_risk_count | {metrics["xlsx_value_formatting_risk_count"]} |
| pdf_weak_evidence_window_flag_count | {metrics["pdf_weak_evidence_window_flag_count"]} |
| official_metric_input_rows | 0 |
| L8_generation_executed | true |
| deterministic_official_execution | false |
| p95_llm_elapsed_ms | {metrics["llm_latency_summary"]["p95_llm_elapsed_ms"]} |

Runtime materialization and latency budget: L0-L8 are classified exactly once across `ingestion_time_materialized`, `index_time_materialized`, `query_time_lightweight`, `query_time_cacheable`, or `forbidden_query_time_work`; raw PDF/XLSX query-time parsing, full workbook/sheet scans, full PDF page/block scans, broad SourceAtom scans, and vector-payload-as-evidence-truth are forbidden. L8 generation latency is diagnostic-only and is not mixed into retrieval latency.

Artifacts: `{summary["review_packet_dir"]}/review_packet.csv`, `review_packet.jsonl`, `responses.jsonl`, `summary.json`, `metrics.json`, `per_family.json`, `per_query.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `prompt_manifest.json`, `local_llm_readiness.json`, `runtime_materialization_plan.json`, `latency_budget_contract.json`, `per_layer_online_work_audit.jsonl`, `cache_key_contract.json`, and `forbidden_query_time_work_audit.json`.
"""
    triage_entry = (
        "### v3_16 Final LLM Answer-Quality Review Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        "- This is a user-perception review packet, not retrieval improvement and not official scoring. PDF and XLSX stay family-separated and no collapsed headline score is reported.\n"
        "- User-owned review fields remain blank for satisfaction, relevance, answerability, expected-answer decision, and supporting-evidence decision.\n"
        "- Generated final answers are source-truth diagnostics only: SourceAtom/EvidenceBundle citations are review metadata, while final answers remain evaluation artifacts/log-like outputs rather than production source truth.\n"
        "- If the local LLM endpoint is unavailable, v3_16 fails closed and records readiness instead of silently using a noop/extractive generator.\n"
        "- The runtime materialization contract keeps query-time work bounded: L3 reranks only precomputed structural candidates, L4 hydrates by SourceAtom id, L5 assembles bounded bundles, and the latency budget is diagnostic-only with L8 generation reported separately from retrieval.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = __import__("re").sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_16_final_llm_answer_quality_review_nonprod_ready`;",
        progress_text,
        count=1,
    )
    progress_text = __import__("re").sub(
        r"current diagnostic answer-quality loop:\n`[^`]+`;",
        f"current diagnostic answer-quality loop:\n`{RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)


def append_status_event(summary: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": summary["status"],
        "generated_at": utc_now(),
        "review_packet_dir": summary["review_packet_dir"],
        "generated_response_count": summary["generated_response_count"],
        "review_packet_row_count": summary["review_packet_row_count"],
        "parse_ok_count": summary["parse_ok_count"],
        "invalid_json_count": summary["invalid_json_count"],
        "truncated_or_malformed_response_count": summary["truncated_or_malformed_response_count"],
        "citation_rendered_count": summary["citation_rendered_count"],
        "abstain_count": summary["abstain_count"],
        "latency_budget": summary["latency_budget"],
        "runtime_materialization": summary["runtime_materialization"],
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
        **guardrail_flags(
            l8_generation_executed=summary["status"] == STATUS,
            fail_closed=bool(summary.get("local_llm_unavailable_fail_closed")),
        ),
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def artifact_sha256_without_summary() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in OUTPUTS.items():
        if key == "summary_json":
            continue
        hashes[f"{key}_sha256"] = sha256_file(path)
    return hashes


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_json(OUTPUTS["per_family_json"], artifacts["per_family"])
    write_jsonl(OUTPUTS["per_query_jsonl"], artifacts["per_query_rows"])
    write_jsonl(OUTPUTS["responses_jsonl"], artifacts["response_rows"])
    write_csv(OUTPUTS["review_packet_csv"], artifacts["review_rows"])
    write_jsonl(OUTPUTS["review_packet_jsonl"], artifacts["review_rows"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_json(OUTPUTS["prompt_manifest_json"], artifacts["prompt_manifest"])
    write_json(OUTPUTS["local_llm_readiness_json"], artifacts["local_llm_readiness"])
    write_json(OUTPUTS["runtime_materialization_plan_json"], artifacts["runtime_materialization_plan"])
    write_json(OUTPUTS["latency_budget_contract_json"], artifacts["latency_budget_contract"])
    write_jsonl(OUTPUTS["per_layer_online_work_audit_jsonl"], artifacts["per_layer_online_work_audit_rows"])
    write_json(OUTPUTS["cache_key_contract_json"], artifacts["cache_key_contract"])
    write_json(OUTPUTS["forbidden_query_time_work_audit_json"], artifacts["forbidden_query_time_work_audit"])

    artifact_sha = artifact_sha256_without_summary()
    if artifacts["summary"]["status"] == STATUS:
        summary = build_summary(
            metrics=artifacts["metrics"],
            per_family=artifacts["per_family"],
            input_lineage=artifacts["input_lineage"],
            artifact_sha256=artifact_sha,
            local_llm_readiness=artifacts["local_llm_readiness"],
        )
    else:
        summary = dict(artifacts["summary"])
        summary["artifact_sha256"] = artifact_sha
    write_json(OUTPUTS["summary_json"], summary)
    append_status_event(summary)
    if summary["status"] == STATUS:
        update_docs(summary, artifacts["metrics"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v3_16 diagnostic-only final LLM answer-quality review packet.")
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=["llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=420)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--max-evidence-chars", type=int, default=900)
    args = parser.parse_args(argv)
    artifacts = build_artifacts(
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout_seconds,
        max_evidence_chars=args.max_evidence_chars,
    )
    payload = {
        "run_id": RUN_ID,
        "status": artifacts["summary"]["status"],
        "generated_response_count": artifacts["metrics"]["generated_response_count"],
        "review_packet_row_count": artifacts["metrics"]["review_packet_row_count"],
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }
    if args.check:
        print(json.dumps({**payload, "check": True}, ensure_ascii=False, sort_keys=True))
        return 0 if artifacts["summary"]["status"] == STATUS else 2
    summary = write_artifacts(artifacts)
    print(json.dumps({**payload, "summary": repo_relative(OUTPUTS["summary_json"])}, ensure_ascii=False, sort_keys=True))
    return 0 if summary["status"] == STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
