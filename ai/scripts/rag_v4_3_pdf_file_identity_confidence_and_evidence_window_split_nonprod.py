from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_13_pdf_file_identity_structural_locator_nonprod_alignment as v313
import rag_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod as v42


ROOT = v42.ROOT
REPORT_DIR = v42.REPORT_DIR
STATUS_JSONL = v42.STATUS_JSONL
PROGRESS_DOC = v42.PROGRESS_DOC
MEASUREMENTS_DOC = v42.MEASUREMENTS_DOC
TRIAGE_DOC = v42.TRIAGE_DOC
README = v42.README
EVAL_README = v42.EVAL_README

V4_NAME = v42.V4_NAME
V4_RUN_FAMILY = v42.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod"
EVENT_TYPE = "diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod"
STATUS = "DIAGNOSTIC_V4_3_PDF_FILE_IDENTITY_CONFIDENCE_AND_EVIDENCE_WINDOW_SPLIT_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_report_v1"
ROW_SCHEMA_VERSION = "rag_v4_3_pdf_file_identity_split_manifest_row_v1"
PDF_FILE_IDENTITY_METRIC_KEY = (
    "pdf_file_identity_structural_locator_eval.v3_13_pdf_file_identity_confidence_diagnostic"
)
PDF_FILE_IDENTITY_METRIC_SCOPE = "diagnostic_only_seen_reference_file_identity_confidence_no_rerank"
PDF_EVIDENCE_WINDOW_METRIC_KEY = (
    "pdf_file_identity_structural_locator_eval.v3_13_pdf_evidence_window_diagnostic"
)
PDF_EVIDENCE_WINDOW_METRIC_SCOPE = "diagnostic_only_same_page_bbox_window_availability_not_answer_generation"
ANSWER_READY_WINDOW_SCOPE = "selector_target_hit_same_page_bbox_window_only"
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v42.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
            "metrics.json",
            "pdf_candidate_components.jsonl",
            "pdf_file_identity_split_manifest.jsonl",
            "per_query.jsonl",
            "review_packet.csv",
            "summary.json",
        }
    )
)


def clean(value: Any) -> str:
    return v42.clean(value)


def repo_relative(path: Path) -> str:
    return v42.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v42.artifact_path_text(path)


def utc_now() -> str:
    return v42.utc_now()


def sha256_file(path: Path) -> str:
    return v42.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v42.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v42.read_jsonl(path)


def artifact_exists(path: Path) -> bool:
    return v42.artifact_exists(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v42.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v42.write_jsonl(path, rows)


def with_reference_provenance(metric: Mapping[str, Any]) -> dict[str, Any]:
    numerator = int(metric.get("numerator") or 0)
    denominator = int(metric.get("denominator") or 0)
    rate = metric.get("rate")
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": rate,
        "ratio": rate,
        "computed_by_v4_3": False,
        "metric_role": "reference_only_seen_diagnostic",
        "optimization_target": False,
        "source_run_id": v313.RUN_ID,
    }


def source_run_references() -> dict[str, Any]:
    return {
        "v3_13_run_id": v313.RUN_ID,
        "v3_13_metrics_json": repo_relative(v313.OUTPUTS["metrics_json"]),
        "v3_13_pdf_eval_jsonl": repo_relative(v313.OUTPUTS["pdf_structural_locator_eval_per_query_jsonl"]),
        "v3_13_pdf_score_components_jsonl": repo_relative(v313.OUTPUTS["pdf_score_components_jsonl"]),
        "v4_2_run_id": v42.RUN_ID,
        "v4_2_report_json": repo_relative(v42.REPORT_JSON),
    }


def build_pdf_file_identity_split_manifest(eval_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_row in sorted(eval_rows, key=lambda row: clean(row.get("query_id"))):
        rows.append(
            {
                "schema_version": ROW_SCHEMA_VERSION,
                "run_id": RUN_ID,
                "source_run_id": v313.RUN_ID,
                "query_id": clean(source_row.get("query_id")),
                "source_family": "PDF",
                "source_family_separated": True,
                "file_identity_answer_window_kept_separate": True,
                "candidate_count": int(source_row.get("candidate_count") or 0),
                "file_identity_metric_computed": bool(source_row.get("file_identity_metric_computed")),
                "evidence_window_metric_computed": bool(source_row.get("answer_ready_window_sufficiency_metric_computed")),
                "file_resolve_at1": bool(source_row.get("file_resolve@1")),
                "file_resolve_at3": bool(source_row.get("file_resolve@3")),
                "resolve_status": clean(source_row.get("resolve_status")),
                "failure_bucket": clean(source_row.get("failure_bucket")),
                "rank1_confidence_bucket": clean(source_row.get("rank1_confidence_bucket")),
                "abstain_or_disambiguate": bool(source_row.get("abstain_or_disambiguate")),
                "wrong_file_block_rate": bool(source_row.get("wrong_file_block_rate")),
                "wrong_file_forcing_accepted": bool(source_row.get("wrong_file_forcing_accepted")),
                "accepted_wrong_rank1_with_target_in_top3_rerank_candidates": bool(
                    source_row.get("accepted_wrong_rank1_with_target_in_top3_rerank_candidates")
                ),
                "page_candidate_count": int(source_row.get("page_candidate_count") or 0),
                "block_candidate_count": int(source_row.get("block_candidate_count") or 0),
                "bbox_candidate_count": int(source_row.get("bbox_candidate_count") or 0),
                "same_page_bounded_evidence_window_candidate_count": int(
                    source_row.get("same_page_bounded_evidence_window_candidate_count") or 0
                ),
                "answer_ready_window_sufficiency_measurable": bool(
                    source_row.get("answer_ready_window_sufficiency_measurable")
                ),
                "answer_ready_window_sufficient": bool(source_row.get("answer_ready_window_sufficient")),
                "answer_ready_window_sufficiency_metric_scope": clean(
                    source_row.get("answer_ready_window_sufficiency_metric_scope")
                ),
                "bbox_correctness_metric_computed": False,
                "bbox_correctness_blocked_reason": clean(source_row.get("bbox_correctness_blocked_reason")),
                "source_atom_hydrated_from_registry": bool(source_row.get("source_atom_hydrated_from_registry")),
                "evidence_bundle_assembled": bool(source_row.get("evidence_bundle_assembled")),
                "canonical_payload_source": clean(source_row.get("canonical_payload_source")),
                "computed_by_v4_3": False,
                "metric_role": "reference_only_seen_diagnostic",
                "optimization_target": False,
                "source_metric_key": PDF_FILE_IDENTITY_METRIC_KEY,
                "source_metric_scope": PDF_FILE_IDENTITY_METRIC_SCOPE,
                "metric_provenance": {
                    "file_identity": {
                        "computed_by_v4_3": False,
                        "metric_role": "reference_only_seen_diagnostic",
                        "optimization_target": False,
                        "source_run_id": v313.RUN_ID,
                        "source_metric_key": PDF_FILE_IDENTITY_METRIC_KEY,
                        "source_metric_scope": PDF_FILE_IDENTITY_METRIC_SCOPE,
                        "seen_reference_only": True,
                    },
                    "evidence_window": {
                        "computed_by_v4_3": False,
                        "metric_role": "reference_only_seen_diagnostic",
                        "optimization_target": False,
                        "source_run_id": v313.RUN_ID,
                        "source_metric_key": PDF_EVIDENCE_WINDOW_METRIC_KEY,
                        "source_metric_scope": PDF_EVIDENCE_WINDOW_METRIC_SCOPE,
                        "answer_ready_window_sufficiency_metric_scope": ANSWER_READY_WINDOW_SCOPE,
                        "bbox_correctness_metric_computed": False,
                        "seen_reference_only": True,
                    },
                },
                "seen_reference_only": True,
                "fresh_real_holdout": False,
                "source_document_disjoint_validation": False,
                "direct_normalized_value_query_matching_used": False,
                "raw_answer_value_for_query_scoring_used": False,
                "used_gold_or_expected_text": False,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
                "vector_payload_used_as_evidence_truth": False,
                "success_claim_allowed": False,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
            }
        )
    return rows


def build_metrics(
    rows: Sequence[Mapping[str, Any]],
    score_rows: Sequence[Mapping[str, Any]],
    v3_13_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    pdf_eval = v3_13_metrics["pdf_file_identity_structural_locator_eval"]
    identity = pdf_eval["v3_13_pdf_file_identity_confidence_diagnostic"]
    window = pdf_eval["v3_13_pdf_evidence_window_diagnostic"]
    failure_counts = Counter(clean(row.get("failure_bucket")) for row in rows)
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "pdf_file_identity_rows": len(rows),
        "pdf_candidate_component_rows": len(score_rows),
        "xlsx_rows_included": 0,
        "text_rows_included": 0,
        "source_family_separated_metrics": {
            "PDF": {
                "row_count": len(rows),
                "candidate_component_rows": len(score_rows),
                "computed_by_v4_3": False,
                "metric_role": "reference_only_seen_diagnostic",
            },
            "XLSX": {"row_count": 0, "excluded": True},
            "TEXT": {"row_count": 0, "excluded": True},
        },
        "seen_reference_only_rows": len(rows),
        "source_document_disjoint_validation_rows": 0,
        "fresh_real_holdout_available": False,
        "fresh_real_holdout_sufficient": False,
        "real_blind_ood_holdout_available": False,
        "real_unseen_registry_counts": {"PDF_source_document_disjoint": 0},
        "minimum_targets": {
            "pdf_unseen_source_documents": 20,
            "query_fidelity_included_rows_per_family": 100,
        },
        "query_fidelity_included_rows_per_family_target": 100,
        "file_resolve_at1": with_reference_provenance(identity["file_resolve@1"]),
        "file_resolve_at3": with_reference_provenance(identity["file_resolve@3"]),
        "abstain_rate": with_reference_provenance(identity["abstain_rate"]),
        "wrong_file_block_rate": with_reference_provenance(identity["wrong_file_block_rate"]),
        "abstain_count": identity["abstain_count"],
        "disambiguation_count": identity["disambiguation_count"],
        "abstain_or_disambiguation_count": identity["abstain_or_disambiguation_count"],
        "accepted_wrong_rank1_with_target_in_top3_count": identity[
            "accepted_wrong_rank1_with_target_in_top3_rerank_candidates"
        ]["numerator"],
        "accepted_wrong_rank1_with_target_in_top3_rate": with_reference_provenance(
            identity["accepted_wrong_rank1_with_target_in_top3_rerank_candidates"]
        ),
        "wrong_file_forcing_accepted_count": identity["wrong_file_forcing_accepted_rate"]["numerator"],
        "wrong_file_forcing_accepted_rate": with_reference_provenance(identity["wrong_file_forcing_accepted_rate"]),
        "wrong_file_forcing_delta_from_v3_11": with_reference_provenance(
            identity["wrong_file_forcing_delta_from_v3_11"]
        ),
        "rank1_confidence_bucket_counts": dict(identity["rank1_confidence_bucket_counts"]),
        "same_page_bounded_evidence_window_candidate_at3": with_reference_provenance(
            window["same_page_bounded_evidence_window_candidate@3"]
        ),
        "answer_ready_window_measurable_at_query": with_reference_provenance(
            window["answer_ready_window_measurable@query"]
        ),
        "answer_ready_window_sufficient_at_query": with_reference_provenance(
            window["answer_ready_window_sufficient@query"]
        ),
        "page_candidate_at3": with_reference_provenance(window["page_candidate@3"]),
        "block_candidate_at3": with_reference_provenance(window["block_candidate@3"]),
        "bbox_present_at3": with_reference_provenance(window["bbox_present@3"]),
        "bbox_correctness_metric_computed": False,
        "bbox_correctness_metric_blocked_reason": clean(window["bbox_correctness_metric_blocked_reason"]),
        "pdf_file_identity_answer_window_kept_separate": True,
        "pdf_file_identity_failure_taxonomy": dict(sorted(failure_counts.items())),
        "pdf_file_identity_metrics": {
            "computed_by_v4_3": False,
            "metric_role": "reference_only_seen_diagnostic",
            "optimization_target": False,
            "source_run_id": v313.RUN_ID,
            "source_metric_key": PDF_FILE_IDENTITY_METRIC_KEY,
            "source_metric_scope": PDF_FILE_IDENTITY_METRIC_SCOPE,
            "file_resolve_at1": with_reference_provenance(identity["file_resolve@1"]),
            "file_resolve_at3": with_reference_provenance(identity["file_resolve@3"]),
            "abstain_or_disambiguation_count": identity["abstain_or_disambiguation_count"],
        },
        "pdf_evidence_window_metrics": {
            "computed_by_v4_3": False,
            "metric_role": "reference_only_seen_diagnostic",
            "optimization_target": False,
            "source_run_id": v313.RUN_ID,
            "source_metric_key": PDF_EVIDENCE_WINDOW_METRIC_KEY,
            "source_metric_scope": PDF_EVIDENCE_WINDOW_METRIC_SCOPE,
            "answer_ready_window_sufficiency_metric_scope": ANSWER_READY_WINDOW_SCOPE,
            "bbox_correctness_metric_computed": False,
            "same_page_bounded_evidence_window_candidate_at3": with_reference_provenance(
                window["same_page_bounded_evidence_window_candidate@3"]
            ),
            "answer_ready_window_sufficient_at_query": with_reference_provenance(
                window["answer_ready_window_sufficient@query"]
            ),
        },
        "validation_holdout_metrics": {
            "row_count": 0,
            "computed_by_v4_3": False,
            "fresh_real_holdout_available": False,
            "blocked_reason": "fresh real PDF source-document-disjoint holdout unavailable",
        },
        "synthetic_ood_guard_metrics": {
            "row_count": 0,
            "counted_as_validation_success": False,
            "shortcut_leakage_guard_only": True,
        },
        "per_query_rows": len(rows),
        "input_lineage": source_run_references(),
        "denominator_policy": (
            "v4_3 keeps PDF file-identity and evidence-window metrics on the v3_13 329-row seen diagnostic "
            "surface; PDF file identity is not collapsed with answer-ready evidence-window quality."
        ),
        "not_official_denominator": True,
        "official_metric_denominator_usage_allowed": False,
        "direct_normalized_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "live_db_index_cache_readiness": False,
        "gpu_required_for_this_slice": False,
        "local_llm_or_gpu_inference_required": False,
        "single_report_artifact_contract": True,
        "sidecar_primary_artifacts_suppressed": True,
        "review_csv_created": False,
        "human_review_required": False,
    }


def build_holdout_policy(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_holdout_policy_v1",
        "run_id": RUN_ID,
        "seen_reference_only_rows": metrics["seen_reference_only_rows"],
        "source_document_disjoint_validation_rows": 0,
        "fresh_real_holdout_available": False,
        "fresh_real_holdout_sufficient": False,
        "real_blind_ood_holdout_available": False,
        "real_unseen_registry_counts": {"PDF_source_document_disjoint": 0},
        "seen_reference_success_claim_allowed": False,
        "product_success_evidence_allowed": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "blocked_reason": "fresh real PDF source-document-disjoint holdout unavailable",
        "interpretation": (
            "The current 329 PDF rows are seen-reference/no-regression diagnostics only. They do not establish "
            "source-document-disjoint validation, blind/OOD quality, production readiness, promotion evidence, or "
            "fine-tuning readiness beyond infrastructure preparation."
        ),
        "minimum_targets": {
            "pdf_unseen_source_documents": 20,
            "query_fidelity_included_rows_per_family": 100,
        },
    }


def build_guardrails() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "family_separated_pdf_only": True,
        "xlsx_lane_excluded": True,
        "text_lane_excluded": True,
        "pdf_file_identity_answer_window_kept_separate": True,
        "bbox_correctness_metric_computed": False,
        "source_atom_evidence_bundle_evidence_truth": True,
        "source_atom_registry_canonical_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "direct_normalized_value_query_matching_used": False,
        "direct_normalized_answer_value_query_matching_used": False,
        "raw_answer_value_for_query_scoring_used": False,
        "raw_pdf_query_time_parsing": False,
        "raw_pdf_query_time_parsing_forbidden": True,
        "full_document_scan_forbidden": True,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "source_title_or_file_name_shortcut_used": False,
        "exact_query_hack_used": False,
        "source_atom_registry_mutated": False,
        "db_or_production_namespace_written": False,
        "protected_namespaces_touched": [],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "official_denominator_mutation": False,
        "production_mutation": False,
        "production_routing": False,
        "official_metric": False,
        "official_metric_lift": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "representative_product_performance": False,
        "pdf_xlsx_text_collapsed_headline_product_score": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_route_policy_dry_run_executed": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "live_db_index_cache_readiness": False,
        "single_report_artifact_contract": True,
        "review_csv_created": False,
        "gpu_required_for_this_slice": False,
        "local_llm_or_gpu_inference_required": False,
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
    holdout_policy: Mapping[str, Any],
) -> dict[str, Any]:
    summary = dict(metrics)
    summary.update(
        {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "event_type": EVENT_TYPE,
            "status": STATUS,
            "v4_name": V4_NAME,
            "run_family": V4_RUN_FAMILY,
            "run_class": "diagnostic_only_pdf_file_identity_confidence_and_evidence_window_split_nonprod",
            "generated_at": utc_now(),
            "artifact_paths": dict(artifact_paths),
            "review_packet_dir": repo_relative(OUTPUT_DIR),
            "holdout_policy": dict(holdout_policy),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
            "human_review_required": False,
            "diagnostic_only": True,
            "production_routing": False,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "official_metric_lift": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "fine_tuning_readiness_only": True,
            "fine_tuning_started": False,
            "fine_tuning_executed": False,
            "live_db_index_cache_readiness": False,
            "agent_runtime_product_ready": False,
        }
    )
    return summary


def build_verification_section() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_verification_v1",
        "run_id": RUN_ID,
        "commands_required_by_goal": [
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py",
            "python -X utf8 ai\\scripts\\rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py --check",
            "targeted v4_3 PDF file identity split tests",
            "targeted artifact/status/guardrail tests",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
            "git diff --cached --check",
            "git check-ignore -v for v4_3 report.json and status.jsonl",
        ],
        "results_recorded_in_final_response": True,
        "gpu_note": "No GPU workload is executed in v4_3 because this slice performs deterministic artifact materialization.",
    }


def build_report(
    *,
    rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    holdout_policy: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    summary = build_summary(metrics=metrics, artifact_paths=artifact_paths, holdout_policy=holdout_policy)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "production_routing": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "official_metric_lift": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "fine_tuning_readiness_only": True,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "live_db_index_cache_readiness": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "single_report_artifact_contract": True,
        "human_review_required": False,
        "review_csv_created": False,
        "pdf_file_identity_answer_window_kept_separate": True,
        "artifact_paths": dict(artifact_paths),
        "source_run_references": source_run_references(),
        "input_lineage": source_run_references(),
        "denominator_policy": metrics["denominator_policy"],
        "not_official_denominator": True,
        "official_metric_denominator_usage_allowed": False,
        "summary": summary,
        "metrics": dict(metrics),
        "pdf_file_identity_metrics": metrics["pdf_file_identity_metrics"],
        "pdf_evidence_window_metrics": metrics["pdf_evidence_window_metrics"],
        "validation_holdout_metrics": metrics["validation_holdout_metrics"],
        "synthetic_ood_guard_metrics": metrics["synthetic_ood_guard_metrics"],
        "pdf_file_identity_failure_taxonomy": metrics["pdf_file_identity_failure_taxonomy"],
        "pdf_file_identity_split_manifest": list(rows),
        "per_query_rows": {
            "row_count": len(rows),
            "embedded_manifest_field": "pdf_file_identity_split_manifest",
            "sidecar_created": False,
        },
        "holdout_policy": dict(holdout_policy),
        "guardrails": dict(guardrails),
        "guardrail_audit": dict(guardrails),
        "verification": build_verification_section(),
        "changed_files": [
            "ai/scripts/rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py",
            "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
            "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py",
            "ai/tests/test_rag_diagnostic_guardrail_git_diff.py",
            "ai/tests/test_rag_diagnostic_status_sync.py",
            "ai/tests/test_rag_current_focused_test_profile_v1.py",
            "docs/rag-ingestion-progress.md",
            "docs/rag-ingestion-measurements.md",
            "docs/rag-ingestion-triage.md",
            "README.md",
            "ai/eval/README.md",
            "ai/eval/reports/rag-ingestion/status.jsonl",
        ],
        "residual_risks": [
            "v4_3 packages v3_13 PDF diagnostics as reference-only seen rows; it does not prove source-document-disjoint validation.",
            "PDF file identity remains separated from answer-ready evidence-window quality and bbox correctness is not computed.",
            "No official metric input rows, promotion evidence, product-success evidence, threshold tuning, winner selection, or fine-tuning execution are emitted.",
            "GPU inference is not required for this slice because no model, embedding, or index rebuild workload is run.",
        ],
        "next_recommendation": (
            "Proceed to real blind/OOD holdout and leakage-audit infrastructure only after preserving the PDF identity/window split "
            "and acquiring source-document-disjoint PDF evidence."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    eval_rows = read_jsonl(v313.OUTPUTS["pdf_structural_locator_eval_per_query_jsonl"])
    score_rows = read_jsonl(v313.OUTPUTS["pdf_score_components_jsonl"])
    v3_13_metrics = read_json(v313.OUTPUTS["metrics_json"])
    rows = build_pdf_file_identity_split_manifest(eval_rows)
    metrics = build_metrics(rows, score_rows, v3_13_metrics)
    holdout_policy = build_holdout_policy(metrics)
    guardrails = build_guardrails()
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        rows=rows,
        metrics=metrics,
        guardrails=guardrails,
        holdout_policy=holdout_policy,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "metrics": metrics,
        "pdf_file_identity_split_manifest": rows,
        "guardrails": guardrails,
        "holdout_policy": holdout_policy,
    }


def remove_stale_sidecar_artifacts(target_dir: Path) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()


def assert_single_report_directory(target_dir: Path) -> None:
    unexpected = sorted(path.name for path in target_dir.iterdir() if path.name != "report.json")
    if unexpected:
        raise RuntimeError(f"unexpected v4_3 primary artifacts: {unexpected}")


def write_artifacts(artifacts: Mapping[str, Any], *, output_dir: Path | None = None) -> dict[str, Any]:
    target_dir = output_dir or OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    report_path = target_dir / "report.json"
    report = dict(artifacts["report"])
    report["artifact_paths"] = {"report_json": artifact_path_text(report_path)}
    report["summary"] = dict(report["summary"])
    report["summary"]["artifact_paths"] = dict(report["artifact_paths"])
    report["summary"]["single_report_artifact_contract"] = True
    report["summary"]["sidecar_primary_artifacts_suppressed"] = True
    report["summary"]["review_csv_created"] = False
    report["metrics"] = dict(report["metrics"])
    report["metrics"]["single_report_artifact_contract"] = True
    report["metrics"]["sidecar_primary_artifacts_suppressed"] = True
    report["metrics"]["review_csv_created"] = False
    report["review_csv_created"] = False
    report["human_review_required"] = False
    remove_stale_sidecar_artifacts(target_dir)
    assert_single_report_directory(target_dir)
    write_json(report_path, report)
    assert_single_report_directory(target_dir)
    return report


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v42.replace_marked_entry(path, marker, entry)


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_3 PDF file identity confidence and evidence-window split loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_2 XLSX locator v2 structural materialization loop:\n`[^`]+`;",
        "current diagnostic v4_3 PDF file identity confidence and evidence-window split loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_2 XLSX locator v2 structural materialization loop:\n`{v42.RUN_ID}`;",
        progress_text,
        count=1,
    )
    progress_text = progress_text.replace(
        "keeps `official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod` "
        "plus its single `report.json` as the counter source of truth.",
        "keeps `official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod` "
        "as the Phase 1 closure baseline; each v4_n diagnostic slice uses its own single `report.json` "
        "as the current counter source of truth.",
    )
    progress_text = progress_text.replace(
        "`official_metric_input_rows=0`, `product_success_evidence_allowed=false`",
        "`official_metric=false`, `official_metric_input_rows=0`, `product_success_evidence_allowed=false`",
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")

    readme_text = README.read_text(encoding="utf-8")
    readme_text = re.sub(
        r"Current RAG status: `[^`]+`\.",
        f"Current RAG status: `{EVENT_TYPE}_ready`.",
        readme_text,
        count=1,
    )
    readme_text = readme_text.replace(
        "`production_routing=false`, `official_metric_input_rows=0`",
        "`production_routing=false`, `official_metric=false`, `official_metric_input_rows=0`",
    )
    readme_verify_block = (
        "```powershell\n"
        "python -X utf8 -m py_compile "
        "ai\\scripts\\rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod.py --check\n"
        "python -X utf8 -m pytest ai/tests --rag-current -q\n"
        "```"
    )
    verify_start = readme_text.index("## How To Verify Locally")
    verify_end = readme_text.index("## Repo Map")
    verify_section = readme_text[verify_start:verify_end]
    verify_section = re.sub(
        r"```powershell\n.*?```",
        lambda _match: readme_verify_block,
        verify_section,
        count=1,
        flags=re.DOTALL,
    )
    readme_text = readme_text[:verify_start] + verify_section + readme_text[verify_end:]
    README.write_text(readme_text, encoding="utf-8")

    eval_readme_text = EVAL_README.read_text(encoding="utf-8")
    eval_readme_text = re.sub(
        r"- Current RAG status: `[^`]+`",
        f"- Current RAG status: `{EVENT_TYPE}_ready`",
        eval_readme_text,
        count=1,
    )
    eval_readme_text = eval_readme_text.replace(
        f"v4_2 is `{v42.EVENT_TYPE}_ready`.",
        f"v4_2 is `{v42.EVENT_TYPE}_ready`; v4_3 is `{EVENT_TYPE}_ready`.",
    )
    eval_readme_text = eval_readme_text.replace(
        "`production_routing=false`, `official_metric_input_rows=0`",
        "`production_routing=false`, `official_metric=false`, `official_metric_input_rows=0`",
    )
    EVAL_README.write_text(eval_readme_text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    report_path = report["artifact_paths"]["report_json"]
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)
    progress_entry = (
        f"- v4_3 PDF file identity confidence and evidence-window split (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        f"It packages the v3_13 PDF file identity/evidence-window diagnostic surface into one `report.json` at "
        f"`{report_path}` with 329 seen-reference PDF rows and 942 candidate-component rows. File identity "
        "metrics remain separate from answer-ready evidence-window metrics; bbox correctness is not computed; "
        "all carried metrics are reference-only seen diagnostics with computed_by_v4_3=false. Fresh real PDF "
        "source-document-disjoint holdout remains unavailable, so promotion, threshold tuning, winner selection, "
        "production routing, official_metric=false, official metric lift, and fine-tuning execution remain closed."
    )
    measurements_entry = f"""### v4_3 PDF File Identity Confidence And Evidence-Window Split

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, family-separated PDF-only, single `report.json`, `official_metric=false`.
- Primary artifact: `{report_path}`
- Metric provenance: PDF file-identity and evidence-window counts are v3_13 reference-only seen diagnostics with `computed_by_v4_3=false`.

| Diagnostic count | Value |
| --- | ---: |
| pdf_file_identity_rows | {metrics["pdf_file_identity_rows"]} |
| pdf_candidate_component_rows | {metrics["pdf_candidate_component_rows"]} |
| file_resolve_at1 | {metrics["file_resolve_at1"]["numerator"]}/{metrics["file_resolve_at1"]["denominator"]} |
| file_resolve_at3 | {metrics["file_resolve_at3"]["numerator"]}/{metrics["file_resolve_at3"]["denominator"]} |
| abstain_or_disambiguation_count | {metrics["abstain_or_disambiguation_count"]} |
| accepted_wrong_rank1_with_target_in_top3_count | {metrics["accepted_wrong_rank1_with_target_in_top3_count"]} |
| wrong_file_forcing_accepted_count | {metrics["wrong_file_forcing_accepted_count"]} |
| same_page_bounded_evidence_window_candidate_at3 | {metrics["same_page_bounded_evidence_window_candidate_at3"]["numerator"]}/{metrics["same_page_bounded_evidence_window_candidate_at3"]["denominator"]} |
| answer_ready_window_sufficient_at_query | {metrics["answer_ready_window_sufficient_at_query"]["numerator"]}/{metrics["answer_ready_window_sufficient_at_query"]["denominator"]} |
| bbox_correctness_metric_computed | false |
| source_document_disjoint_validation_rows | 0 |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| fine_tuning_executed | false |
| gpu_required_for_this_slice | false |

Counter source-of-truth: `report.json` embeds summary, metrics, per-query PDF file-identity split manifest, failure taxonomy, source run references, holdout policy, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV, sidecar manifest, metrics sidecar, or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_3 PDF File Identity Confidence And Evidence-Window Split Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_3 keeps XLSX/TEXT lanes excluded and reports PDF diagnostics separately.\n"
        "- The 329-row denominator remains the v3_13 PDF file-identity/evidence-window seen diagnostic surface.\n"
        "- File identity metrics are kept separate from answer-ready evidence-window metrics; bbox correctness remains uncomputed without independent gold-free evidence.\n"
        "- PDF file-identity and evidence-window metrics are `reference_only_seen_diagnostic` with `computed_by_v4_3=false`.\n"
        "- Fresh real source-document-disjoint holdout remains unavailable, so seen-reference/no-regression rows cannot be interpreted as product success.\n"
        "- Direct normalized-value matching, raw answer value scoring, target/gold locator use, expected/supporting gold text use, source/file title shortcuts, official_metric=false, threshold tuning, winner selection, promotion evidence, production routing, and fine-tuning execution remain forbidden.\n"
        "- GPU is not required for this slice because the runner performs deterministic JSON materialization only; future embedding/LLM/index workloads should prefer GPU when available.\n"
        "- Next lane: real blind/OOD holdout and leakage-audit infrastructure.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    triage_text = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_text = triage_text.replace(
        "Next technical lane: v4_1 persisted XLSX SourceAtom display metadata materialization, followed by v4_2 "
        "XLSX locator v2, v4_3 PDF file identity split, v4_4 real blind/OOD holdout and leakage audit, and v4_5 "
        "fine-tuning readiness packet.",
        "Completed v4_1-v4_3: persisted XLSX SourceAtom display metadata materialization, XLSX locator v2, and "
        "PDF file identity split. Next technical lane: v4_4 real blind/OOD holdout and leakage audit, followed by "
        "v4_5 fine-tuning readiness packet.",
    )
    triage_text = triage_text.replace(
        "Completed v4_1-v4_3: persisted XLSX SourceAtom display metadata materialization, XLSX locator v2, and "
        "PDF file identity split. Next technical lane: v4_4 real blind/OOD holdout and leakage audit, followed by "
        "v4_5 fine-tuning readiness packet.",
        "Completed v4_1-v4_3: v4_1 persisted XLSX SourceAtom display metadata materialization, v4_2 XLSX locator "
        "v2, and v4_3 PDF file identity split. Next technical lane: v4_4 real blind/OOD holdout and leakage audit, "
        "followed by v4_5 fine-tuning readiness packet.",
    )
    TRIAGE_DOC.write_text(triage_text, encoding="utf-8")
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)


def artifact_sha256_from_report_paths(artifact_paths: Mapping[str, str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path_text in artifact_paths.items():
        path = Path(path_text)
        if not path.is_absolute():
            path = ROOT / path_text
        if artifact_exists(path):
            hashes[f"{key}_sha256"] = sha256_file(path)
    return hashes


def append_status_event(report: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": artifact_sha256_from_report_paths(report["artifact_paths"]),
        "report_json_created": True,
        "review_csv_created": False,
        "summary_json_created": False,
        "per_run_markdown_created": False,
        "raw_llm_response_payload_created": False,
        "prompt_payload_created": False,
        "pdf_file_identity_split_manifest_jsonl_created": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
        "holdout_policy": dict(report["holdout_policy"]),
    }
    event.pop("per_query_rows", None)
    event.pop("pdf_file_identity_metrics", None)
    event.pop("pdf_evidence_window_metrics", None)
    event.pop("source_family_separated_metrics", None)
    event.pop("pdf_file_identity_failure_taxonomy", None)
    event.pop("input_lineage", None)
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def run_write() -> dict[str, Any]:
    artifacts = build_artifacts()
    report = write_artifacts(artifacts)
    update_docs(report)
    append_status_event(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        artifacts = build_artifacts()
        metrics = artifacts["metrics"]
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": artifacts["report"]["summary"]["status"],
                    "pdf_file_identity_rows": metrics["pdf_file_identity_rows"],
                    "pdf_candidate_component_rows": metrics["pdf_candidate_component_rows"],
                    "file_resolve_at1": metrics["file_resolve_at1"],
                    "answer_ready_window_sufficient_at_query": metrics[
                        "answer_ready_window_sufficient_at_query"
                    ],
                    "official_metric_input_rows": metrics["official_metric_input_rows"],
                    "gpu_required_for_this_slice": metrics["gpu_required_for_this_slice"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    report = run_write()
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "report": report["artifact_paths"]["report_json"],
                "status": report["summary"]["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
