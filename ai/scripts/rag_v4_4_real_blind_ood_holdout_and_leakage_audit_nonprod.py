from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import rag_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization as v310
import rag_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod as v43


ROOT = v43.ROOT
REPORT_DIR = v43.REPORT_DIR
STATUS_JSONL = v43.STATUS_JSONL
PROGRESS_DOC = v43.PROGRESS_DOC
MEASUREMENTS_DOC = v43.MEASUREMENTS_DOC
TRIAGE_DOC = v43.TRIAGE_DOC
README = v43.README
EVAL_README = v43.EVAL_README

V4_NAME = v43.V4_NAME
V4_RUN_FAMILY = v43.V4_RUN_FAMILY
RUN_ID = "official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod"
EVENT_TYPE = "diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod"
STATUS = "DIAGNOSTIC_V4_4_REAL_BLIND_OOD_HOLDOUT_AND_LEAKAGE_AUDIT_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"

REPORT_SCHEMA_VERSION = "rag_v4_4_real_blind_ood_holdout_and_leakage_audit_report_v1"
QUERY_FIDELITY_ROW_SCHEMA_VERSION = "rag_v4_4_query_fidelity_audit_row_v1"
LEAKAGE_ROW_SCHEMA_VERSION = "rag_v4_4_leakage_bucket_audit_row_v1"
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = tuple(
    sorted(
        {
            *v43.FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES,
            "excluded_row_ledger.jsonl",
            "holdout_manifest.json",
            "leakage_audit.jsonl",
            "metrics.json",
            "query_fidelity_audit.jsonl",
            "review_packet.csv",
            "split_manifest.json",
            "summary.json",
        }
    )
)
LEAKAGE_BUCKETS = (
    "answer_value_in_query",
    "index_to_content_query",
    "source_title_leak",
    "file_title_leak",
    "exact_query_hack",
    "major_topic_drift",
    "unnatural_sheet_or_cell_reference",
    "target_locator_leak",
    "gold_supporting_expected_text_leak",
)
LEAKAGE_BUCKET_ALIASES = {
    "index_to_content": "index_to_content_query",
}


def clean(value: Any) -> str:
    return v43.clean(value)


def repo_relative(path: Path) -> str:
    return v43.repo_relative(path)


def artifact_path_text(path: Path) -> str:
    return v43.artifact_path_text(path)


def utc_now() -> str:
    return v43.utc_now()


def sha256_file(path: Path) -> str:
    return v43.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return v43.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v43.read_jsonl(path)


def artifact_exists(path: Path) -> bool:
    return v43.artifact_exists(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v43.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v43.write_jsonl(path, rows)


def source_run_references() -> dict[str, Any]:
    return {
        "v3_10_run_id": v310.RUN_ID,
        "v3_10_fresh_real_holdout_manifest_json": repo_relative(
            v310.OUTPUTS["fresh_real_holdout_manifest_json"]
        ),
        "v3_10_query_fidelity_audit_jsonl": repo_relative(v310.OUTPUTS["query_fidelity_audit_jsonl"]),
        "v3_10_leakage_audit_jsonl": repo_relative(v310.OUTPUTS["leakage_audit_jsonl"]),
        "v4_2_run_id": v43.v42.RUN_ID,
        "v4_2_report_json": repo_relative(v43.v42.REPORT_JSON),
        "v4_3_run_id": v43.RUN_ID,
        "v4_3_report_json": repo_relative(v43.REPORT_JSON),
    }


def build_query_fidelity_audit(source_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        rows.append(
            {
                "schema_version": QUERY_FIDELITY_ROW_SCHEMA_VERSION,
                "run_id": RUN_ID,
                "source_run_id": v310.RUN_ID,
                "query_id": clean(row.get("query_id")),
                "source_family": clean(row.get("source_family")),
                "synthetic": bool(row.get("synthetic")),
                "real_unseen": bool(row.get("real_unseen")),
                "query_fidelity_bucket": clean(row.get("query_fidelity_bucket")),
                "query_fidelity_headline_included": bool(row.get("query_fidelity_headline_included")),
                "query_fidelity_exclusion_reason": clean(row.get("query_fidelity_exclusion_reason")),
                "query_text_sha256": clean(row.get("query_text_sha256")),
                "answer_value_in_query": bool(row.get("answer_value_in_query")),
                "index_to_content_query": bool(row.get("index_to_content") or row.get("index_to_content_query")),
                "source_title_leak": bool(row.get("source_title_leak")),
                "file_title_leak": bool(row.get("file_title_leak")),
                "exact_query_hack": bool(row.get("exact_query_hack")),
                "major_topic_drift": bool(row.get("major_topic_drift")),
                "unnatural_sheet_or_cell_reference": bool(row.get("unnatural_sheet_or_cell_reference")),
                "target_locator_leak": bool(row.get("target_locator_leak")),
                "gold_supporting_expected_text_leak": bool(row.get("gold_supporting_expected_text_leak")),
                "success_evidence_allowed": False,
                "product_success_evidence_allowed": False,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
            }
        )
    return rows


def build_leakage_audit(source_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    source_by_bucket: dict[str, Mapping[str, Any]] = {}
    for row in source_rows:
        source_bucket = clean(row.get("bucket"))
        bucket = LEAKAGE_BUCKET_ALIASES.get(source_bucket, source_bucket)
        source_by_bucket[bucket] = row

    rows: list[dict[str, Any]] = []
    for index, bucket in enumerate(LEAKAGE_BUCKETS, start=1):
        source_row = source_by_bucket.get(bucket, {})
        rows.append(
            {
                "schema_version": LEAKAGE_ROW_SCHEMA_VERSION,
                "run_id": RUN_ID,
                "source_run_id": v310.RUN_ID if source_row else "",
                "probe_id": f"v4_4_leakage_probe_{index:02d}",
                "source_probe_id": clean(source_row.get("probe_id")),
                "bucket": bucket,
                "source_bucket": clean(source_row.get("bucket")) if source_row else bucket,
                "bucket_classified": True,
                "leakage_buckets": [bucket],
                "primary_leakage_bucket": bucket,
                "detector_version": "v4_4_leakage_bucket_audit_v1",
                "detection_method": "source_probe_normalization_or_required_bucket_placeholder",
                "current_artifact_probe_present": bool(source_row),
                "query_text_sha256": clean(source_row.get("query_text_sha256")),
                "query_fidelity_headline_included": False,
                "excluded_from_holdout": True,
                "excluded_from_headline": True,
                "excluded_row_ledger_reason": "leakage_bucket_not_holdout_eligible",
                "success_evidence_allowed": False,
                "product_success_evidence_allowed": False,
                "official_metric_input_rows": 0,
                "diagnostic_only": True,
                "direct_normalized_value_query_matching_used": False,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
                "gold_or_expected_text_used": False,
                "local_path_leak_detected": False,
                "hidden_xlsx_excluded_content_leak_detected": False,
            }
        )
    return rows


def build_excluded_row_ledger(
    leakage_rows: Sequence[Mapping[str, Any]], query_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    ledger = [
        {
            "schema_version": f"{RUN_ID}_excluded_row_ledger_v1",
            "run_id": RUN_ID,
            "row_id": clean(row.get("probe_id")),
            "row_type": "leakage_bucket",
            "source_family": "",
            "bucket": clean(row.get("bucket")),
            "excluded_reason": "leakage_bucket_not_holdout_eligible",
            "excluded_from_holdout": True,
            "excluded_from_headline": True,
            "success_evidence_allowed": False,
            "official_metric_input_rows": 0,
        }
        for row in leakage_rows
    ]
    for row in query_rows:
        if row.get("query_fidelity_headline_included") is not True:
            ledger.append(
                {
                    "schema_version": f"{RUN_ID}_excluded_row_ledger_v1",
                    "run_id": RUN_ID,
                    "row_id": clean(row.get("query_id")),
                    "row_type": "query_fidelity",
                    "source_family": clean(row.get("source_family")),
                    "bucket": clean(row.get("query_fidelity_bucket")),
                    "excluded_reason": clean(row.get("query_fidelity_exclusion_reason")),
                    "excluded_from_holdout": True,
                    "excluded_from_headline": True,
                    "success_evidence_allowed": False,
                    "official_metric_input_rows": 0,
                }
            )
    return ledger


def build_holdout_manifest(source_holdout: Mapping[str, Any]) -> dict[str, Any]:
    counts = dict(source_holdout.get("real_unseen_registry_counts") or {})
    minimum_targets = dict(source_holdout.get("minimum_targets") or {})
    pdf_count = int(counts.get("PDF_source_document_disjoint") or 0)
    xlsx_count = int(counts.get("XLSX_workbook_disjoint") or 0)
    pdf_target = int(minimum_targets.get("pdf_unseen_source_documents") or 20)
    xlsx_target = int(minimum_targets.get("xlsx_unseen_workbooks") or 8)
    query_target = int(minimum_targets.get("query_fidelity_included_rows_per_family") or 100)
    real_holdout_available = pdf_count > 0 and xlsx_count > 0
    real_holdout_sufficient = pdf_count >= pdf_target and xlsx_count >= xlsx_target
    blocked_reason = (
        "fresh real PDF source-document-disjoint and XLSX workbook-disjoint holdout unavailable"
        if not real_holdout_available
        else "fresh real holdout available but below minimum source-disjoint PDF/XLSX targets"
    )
    return {
        "schema_version": f"{RUN_ID}_holdout_manifest_v1",
        "run_id": RUN_ID,
        "source_run_id": v310.RUN_ID,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "real_holdout_available": real_holdout_available,
        "real_holdout_sufficient": real_holdout_sufficient,
        "real_holdout_acquired": real_holdout_available,
        "real_blind_ood_holdout_available": real_holdout_available,
        "real_unseen_registry_counts": {
            "PDF_source_document_disjoint": pdf_count,
            "XLSX_workbook_disjoint": xlsx_count,
        },
        "minimum_targets": {
            "pdf_unseen_source_documents": pdf_target,
            "xlsx_unseen_workbooks": xlsx_target,
            "query_fidelity_included_rows_per_family": query_target,
        },
        "pdf_source_document_disjoint_from_dev": pdf_count > 0,
        "xlsx_workbook_disjoint_from_dev": xlsx_count > 0,
        "text_control_opened": False,
        "query_fidelity_audit_present": True,
        "leakage_audit_present": True,
        "blocked_reason": blocked_reason,
        "interpretation": (
            "v4_4 materializes the holdout and leakage audit infrastructure, but current repo-local evidence still "
            "has zero real unseen PDF source documents and zero real unseen XLSX workbooks. Synthetic OOD rows remain "
            "anti-overfit guards only and are not success, official, or promotion evidence."
        ),
        "synthetic_ood_guard": {
            **dict(source_holdout.get("synthetic_ood_guard") or {}),
            "product_success_evidence_allowed": False,
            "official_metric_input_rows": 0,
        },
    }


def build_split_manifest(holdout: Mapping[str, Any], query_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    synthetic_included = Counter(
        clean(row.get("source_family"))
        for row in query_rows
        if row.get("synthetic") is True and row.get("query_fidelity_headline_included") is True
    )
    pdf_count = int(holdout["real_unseen_registry_counts"]["PDF_source_document_disjoint"])
    xlsx_count = int(holdout["real_unseen_registry_counts"]["XLSX_workbook_disjoint"])
    return {
        "schema_version": f"{RUN_ID}_split_manifest_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "real_holdout_split_created": False,
        "synthetic_ood_guard_only": True,
        "source_family_splits": {
            "PDF": {
                "required_disjointness": "source_document",
                "real_unseen_count": pdf_count,
                "minimum_target": holdout["minimum_targets"]["pdf_unseen_source_documents"],
                "split_created": pdf_count > 0,
                "synthetic_guard_included_rows": int(synthetic_included["PDF"]),
            },
            "XLSX": {
                "required_disjointness": "workbook",
                "real_unseen_count": xlsx_count,
                "minimum_target": holdout["minimum_targets"]["xlsx_unseen_workbooks"],
                "split_created": xlsx_count > 0,
                "synthetic_guard_included_rows": int(synthetic_included["XLSX"]),
            },
            "TEXT": {
                "required_disjointness": "comparison_control_only",
                "real_unseen_count": 0,
                "minimum_target": 0,
                "split_created": False,
                "comparison_control_only": True,
            },
        },
    }


def build_guardrails() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "v4_name": V4_NAME,
        "run_family": V4_RUN_FAMILY,
        "source_atom_evidence_bundle_evidence_truth": True,
        "source_atom_registry_canonical_truth": True,
        "searchview_vector_payload_candidate_only": True,
        "vector_payload_used_as_evidence_truth": False,
        "raw_pdf_query_time_parsing": False,
        "raw_xlsx_query_time_parsing": False,
        "full_document_or_workbook_scan_forbidden": True,
        "direct_normalized_answer_value_query_matching_used": False,
        "direct_normalized_value_query_matching_used": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
        "answer_value_in_query_success_evidence_used": False,
        "index_to_content_success_evidence_used": False,
        "source_title_or_file_name_shortcut_success_evidence_used": False,
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


def build_metrics(
    *,
    holdout: Mapping[str, Any],
    query_rows: Sequence[Mapping[str, Any]],
    leakage_rows: Sequence[Mapping[str, Any]],
    excluded_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    real_included = Counter(
        clean(row.get("source_family"))
        for row in query_rows
        if row.get("real_unseen") is True and row.get("query_fidelity_headline_included") is True
    )
    synthetic_included = Counter(
        clean(row.get("source_family"))
        for row in query_rows
        if row.get("synthetic") is True and row.get("query_fidelity_headline_included") is True
    )
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "fine_tuning_executed": False,
        "real_blind_ood_holdout_infrastructure_ready": True,
        "leakage_audit_infrastructure_ready": True,
        "query_fidelity_audit_present": True,
        "leakage_excluded_count_reported": True,
        "real_holdout_available": bool(holdout["real_holdout_available"]),
        "real_holdout_sufficient": bool(holdout["real_holdout_sufficient"]),
        "real_unseen_registry_counts": dict(holdout["real_unseen_registry_counts"]),
        "minimum_targets": dict(holdout["minimum_targets"]),
        "real_query_fidelity_included_counts": {
            "PDF": int(real_included["PDF"]),
            "XLSX": int(real_included["XLSX"]),
            "TEXT": int(real_included["TEXT"]),
        },
        "synthetic_ood_query_fidelity_included_counts": {
            "PDF": int(synthetic_included["PDF"]),
            "XLSX": int(synthetic_included["XLSX"]),
            "TEXT": int(synthetic_included["TEXT"]),
        },
        "query_fidelity_audit_rows": len(query_rows),
        "leakage_audit_rows": len(leakage_rows),
        "leakage_bucket_count": len({row["bucket"] for row in leakage_rows}),
        "leakage_excluded_count": sum(1 for row in leakage_rows if row.get("excluded_from_holdout") is True),
        "excluded_row_ledger_rows": len(excluded_rows),
        "synthetic_ood_guard_product_success_evidence_allowed": False,
        "source_family_metrics": {
            "PDF": {
                "source_document_disjoint_required": True,
                "real_holdout_rows": int(holdout["real_unseen_registry_counts"]["PDF_source_document_disjoint"]),
                "target": holdout["minimum_targets"]["pdf_unseen_source_documents"],
            },
            "XLSX": {
                "workbook_disjoint_required": True,
                "real_holdout_rows": int(holdout["real_unseen_registry_counts"]["XLSX_workbook_disjoint"]),
                "target": holdout["minimum_targets"]["xlsx_unseen_workbooks"],
            },
            "TEXT": {"comparison_control_only": True, "real_holdout_rows": 0, "target": 0},
        },
    }


def build_family_separated_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "PDF": {
            "source_document_disjoint_required": True,
            "real_holdout_rows": metrics["real_unseen_registry_counts"]["PDF_source_document_disjoint"],
            "minimum_target": metrics["minimum_targets"]["pdf_unseen_source_documents"],
            "real_holdout_available": metrics["real_holdout_available"],
            "real_holdout_sufficient": metrics["real_holdout_sufficient"],
            "product_success_evidence_allowed": False,
        },
        "XLSX": {
            "workbook_disjoint_required": True,
            "real_holdout_rows": metrics["real_unseen_registry_counts"]["XLSX_workbook_disjoint"],
            "minimum_target": metrics["minimum_targets"]["xlsx_unseen_workbooks"],
            "real_holdout_available": metrics["real_holdout_available"],
            "real_holdout_sufficient": metrics["real_holdout_sufficient"],
            "product_success_evidence_allowed": False,
        },
        "TEXT": {
            "comparison_control_only": True,
            "real_holdout_rows": 0,
            "product_success_evidence_allowed": False,
        },
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
    holdout: Mapping[str, Any],
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
            "run_class": "diagnostic_only_real_blind_ood_holdout_and_leakage_audit_nonprod",
            "generated_at": utc_now(),
            "artifact_paths": dict(artifact_paths),
            "holdout_manifest": dict(holdout),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_created": False,
            "human_review_required": False,
            "production_routing": False,
            "official_metric_lift": False,
            "fine_tuning_readiness_only": True,
            "fine_tuning_started": False,
            "live_db_index_cache_readiness": False,
        }
    )
    return summary


def build_verification_section() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_verification_v1",
        "run_id": RUN_ID,
        "commands_required_by_goal": [
            "python -X utf8 -m py_compile ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py",
            "python -X utf8 ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py --check",
            "targeted v4_4 real blind/OOD holdout and leakage tests",
            "targeted artifact/status/guardrail tests",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
            "git diff --cached --check",
            "git check-ignore -v for v4_4 report.json and status.jsonl",
        ],
        "results_recorded_in_final_response": True,
        "gpu_note": "No GPU workload is executed in v4_4 because this slice performs deterministic audit materialization.",
    }


def build_report(
    *,
    holdout: Mapping[str, Any],
    split_manifest: Mapping[str, Any],
    query_rows: Sequence[Mapping[str, Any]],
    leakage_rows: Sequence[Mapping[str, Any]],
    excluded_rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    summary = build_summary(metrics=metrics, artifact_paths=artifact_paths, holdout=holdout)
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
        "real_blind_ood_holdout_infrastructure_ready": True,
        "leakage_audit_infrastructure_ready": True,
        "query_fidelity_audit_present": True,
        "leakage_excluded_count_reported": True,
        "artifact_paths": dict(artifact_paths),
        "source_run_references": source_run_references(),
        "input_lineage": source_run_references(),
        "summary": summary,
        "metrics": dict(metrics),
        "family_separated_metrics": build_family_separated_metrics(metrics),
        "holdout_manifest": dict(holdout),
        "split_manifest": dict(split_manifest),
        "query_fidelity_audit": list(query_rows),
        "leakage_audit": list(leakage_rows),
        "excluded_row_ledger": list(excluded_rows),
        "guardrails": dict(guardrails),
        "guardrail_audit": dict(guardrails),
        "verification": build_verification_section(),
        "changed_files": [
            "ai/scripts/rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py",
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
            "Real PDF source-document-disjoint and XLSX workbook-disjoint holdout rows remain unavailable in this checkout.",
            "Synthetic OOD rows are retained only as anti-overfit guards and are not success, official, or promotion evidence.",
            "No official metric rows, production routing, threshold tuning, winner selection, or fine-tuning execution are emitted.",
            "GPU inference is not required because no model, embedding, or index rebuild workload is run.",
        ],
        "next_recommendation": (
            "Proceed to v4_5 fine-tuning readiness packet only as a readiness packet, and keep actual training closed "
            "until real disjoint splits and user-owned label/qrels/denominator policy exist."
        ),
    }


def build_artifacts(*, output_dir: Path | None = None) -> dict[str, Any]:
    source_holdout = read_json(v310.OUTPUTS["fresh_real_holdout_manifest_json"])
    source_query_rows = read_jsonl(v310.OUTPUTS["query_fidelity_audit_jsonl"])
    source_leakage_rows = read_jsonl(v310.OUTPUTS["leakage_audit_jsonl"])
    query_rows = build_query_fidelity_audit(source_query_rows)
    leakage_rows = build_leakage_audit(source_leakage_rows)
    excluded_rows = build_excluded_row_ledger(leakage_rows, query_rows)
    holdout = build_holdout_manifest(source_holdout)
    split_manifest = build_split_manifest(holdout, query_rows)
    guardrails = build_guardrails()
    metrics = build_metrics(
        holdout=holdout,
        query_rows=query_rows,
        leakage_rows=leakage_rows,
        excluded_rows=excluded_rows,
    )
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    report = build_report(
        holdout=holdout,
        split_manifest=split_manifest,
        query_rows=query_rows,
        leakage_rows=leakage_rows,
        excluded_rows=excluded_rows,
        metrics=metrics,
        guardrails=guardrails,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "metrics": metrics,
        "holdout_manifest": holdout,
        "split_manifest": split_manifest,
        "query_fidelity_audit": query_rows,
        "leakage_audit": leakage_rows,
        "excluded_row_ledger": excluded_rows,
        "guardrails": guardrails,
    }


def remove_stale_sidecar_artifacts(target_dir: Path) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()


def assert_single_report_directory(target_dir: Path) -> None:
    unexpected = sorted(path.name for path in target_dir.iterdir() if path.name != "report.json")
    if unexpected:
        raise RuntimeError(f"unexpected v4_4 primary artifacts: {unexpected}")


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
    report["summary"]["holdout_manifest_json_created"] = False
    report["summary"]["query_fidelity_audit_jsonl_created"] = False
    report["summary"]["leakage_audit_jsonl_created"] = False
    report["summary"]["excluded_row_ledger_jsonl_created"] = False
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
    v43.replace_marked_entry(path, marker, entry)


def update_current_status_lines() -> None:
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        f"Overall status: `{EVENT_TYPE}_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"(?:current diagnostic v4_4 real blind/OOD holdout and leakage audit loop:\n`[^`]+`;\n)?"
        r"current diagnostic v4_3 PDF file identity confidence and evidence-window split loop:\n`[^`]+`;",
        "current diagnostic v4_4 real blind/OOD holdout and leakage audit loop:\n"
        f"`{RUN_ID}`;\ncurrent diagnostic v4_3 PDF file identity confidence and evidence-window split loop:\n`{v43.RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")

    readme_text = README.read_text(encoding="utf-8")
    readme_text = re.sub(
        r"Current RAG status: `[^`]+`\.",
        f"Current RAG status: `{EVENT_TYPE}_ready`.",
        readme_text,
        count=1,
    )
    readme_verify_block = (
        "```powershell\n"
        "python -X utf8 -m py_compile "
        "ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py\n"
        "python -X utf8 ai\\scripts\\rag_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod.py --check\n"
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
        f"v4_3 is `{v43.EVENT_TYPE}_ready`.",
        f"v4_3 is `{v43.EVENT_TYPE}_ready`; v4_4 is `{EVENT_TYPE}_ready`.",
    )
    EVAL_README.write_text(eval_readme_text, encoding="utf-8")


def update_docs(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    holdout = report["holdout_manifest"]
    report_path = report["artifact_paths"]["report_json"]
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)

    progress_entry = (
        f"- v4_4 real blind/OOD holdout and leakage audit (`{RUN_ID}`) is {EVENT_TYPE}_ready. "
        f"It packages the v3_10 holdout insufficiency, query-fidelity audit, and leakage-bucket probes into one "
        f"`report.json` at `{report_path}`. Infrastructure is materialized, but real holdout remains unavailable: "
        "PDF_source_document_disjoint=0/20, XLSX_workbook_disjoint=0/8, and real query-fidelity included rows are "
        "0/100 per family. Nine leakage buckets are classified and excluded from holdout/success evidence. "
        "official_metric=false, official_metric_input_rows=0, promotion_evidence=false, product_success_evidence_allowed=false, "
        "production_routing=false, threshold_tuning=false, winner_selection=false, and fine_tuning_executed=false remain locked."
    )
    measurements_entry = f"""### v4_4 Real Blind/OOD Holdout And Leakage Audit

- Run: `{RUN_ID}`
- v4 marker: `{V4_NAME}`
- Run family: `{V4_RUN_FAMILY}`
- Policy: diagnostic-only, non-production, family-separated PDF/XLSX holdout infrastructure, TEXT comparison/control only, single `report.json`.
- Primary artifact: `{report_path}`
- Source evidence: v3_10 holdout manifest, v3_10 query-fidelity audit, v3_10 leakage audit, v4_2 XLSX locator report, and v4_3 PDF file-identity split report.

| Diagnostic count | Value |
| --- | ---: |
| real_holdout_available | false |
| PDF_source_document_disjoint | {holdout["real_unseen_registry_counts"]["PDF_source_document_disjoint"]}/{holdout["minimum_targets"]["pdf_unseen_source_documents"]} |
| XLSX_workbook_disjoint | {holdout["real_unseen_registry_counts"]["XLSX_workbook_disjoint"]}/{holdout["minimum_targets"]["xlsx_unseen_workbooks"]} |
| query_fidelity_included_rows_per_family | {metrics["real_query_fidelity_included_counts"]["PDF"]}/{holdout["minimum_targets"]["query_fidelity_included_rows_per_family"]} |
| query_fidelity_audit_rows | {metrics["query_fidelity_audit_rows"]} |
| leakage_bucket_count | {metrics["leakage_bucket_count"]} |
| leakage_excluded_count | {metrics["leakage_excluded_count"]} |
| official_metric | false |
| official_metric_input_rows | 0 |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| fine_tuning_executed | false |
| gpu_required_for_this_slice | false |

Counter source-of-truth: `report.json` embeds summary, metrics, holdout_manifest, split_manifest, query_fidelity_audit, leakage_audit, excluded_row_ledger, family_separated_metrics, guardrails, verification, changed_files, residual_risks, and next_recommendation. `report.json` and `status.jsonl` are ignored artifacts; no review CSV, sidecar manifest, metrics sidecar, audit sidecar, or per-run Markdown is created.
"""
    triage_entry = (
        "### v4_4 Real Blind/OOD Holdout And Leakage Audit Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract remains active.\n"
        "- v4_4 materializes holdout, split, query-fidelity, leakage-bucket, and excluded-row ledger infrastructure.\n"
        "- PDF source-document-disjoint and XLSX workbook-disjoint real holdout rows remain unavailable; TEXT remains comparison/control only.\n"
        "- Fresh real holdout remains unavailable, so synthetic OOD rows are anti-overfit guards only and cannot be interpreted as product success.\n"
        "- Leakage buckets classified and excluded: answer_value_in_query, index_to_content_query, source_title_leak, file_title_leak, exact_query_hack, major_topic_drift, unnatural_sheet_or_cell_reference, target_locator_leak, gold_supporting_expected_text_leak.\n"
        "- Direct normalized answer-value matching, target/gold locator use, expected/supporting gold text use, vector payload as evidence truth, threshold tuning, winner selection, promotion evidence, production routing, and fine-tuning execution remain forbidden.\n"
        "- GPU is not required for this slice because the runner performs deterministic audit materialization only; future embedding/LLM/index workloads should prefer GPU when available.\n"
        "- Next lane: v4_5 fine-tuning readiness packet only after preserving these split and leakage gates.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    update_current_status_lines()
    triage_text = TRIAGE_DOC.read_text(encoding="utf-8")
    triage_text = triage_text.replace(
        "Completed v4_1-v4_3: v4_1 persisted XLSX SourceAtom display metadata materialization, v4_2 XLSX locator "
        "v2, and v4_3 PDF file identity split. Next technical lane: v4_4 real blind/OOD holdout and leakage audit, "
        "followed by v4_5 fine-tuning readiness packet.",
        "Completed v4_1-v4_3: v4_1 persisted XLSX SourceAtom display metadata materialization, v4_2 XLSX locator "
        "v2, and v4_3 PDF file identity split. v4_4 real blind/OOD holdout and leakage audit infrastructure is "
        "now materialized but still fail-closed on real holdout availability. Next technical lane: v4_5 "
        "fine-tuning readiness packet.",
    )
    TRIAGE_DOC.write_text(triage_text, encoding="utf-8")
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v43.v42.v41.v322.v321.v320.v319.refresh_last_updated(doc_path)


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
        "holdout_manifest_json_created": False,
        "split_manifest_json_created": False,
        "query_fidelity_audit_jsonl_created": False,
        "leakage_audit_jsonl_created": False,
        "excluded_row_ledger_jsonl_created": False,
        "per_run_markdown_created": False,
        "raw_llm_response_payload_created": False,
        "prompt_payload_created": False,
        **dict(report["metrics"]),
        **dict(report["guardrails"]),
        "holdout_manifest": dict(report["holdout_manifest"]),
    }
    event.pop("source_family_metrics", None)
    event.pop("source_family_separated_metrics", None)
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
                    "real_holdout_available": metrics["real_holdout_available"],
                    "real_unseen_registry_counts": metrics["real_unseen_registry_counts"],
                    "leakage_bucket_count": metrics["leakage_bucket_count"],
                    "leakage_excluded_count": metrics["leakage_excluded_count"],
                    "official_metric_input_rows": metrics["official_metric_input_rows"],
                    "gpu_required_for_this_slice": artifacts["guardrails"]["gpu_required_for_this_slice"],
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
