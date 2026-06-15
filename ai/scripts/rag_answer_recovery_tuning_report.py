"""Aggregate answer-recovery diagnostics into compact phase-level reports."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rag_answer_recovery_embedding_readiness as readiness  # noqa: E402
import rag_answer_recovery_existing_embedding_retrieval_probe as retrieval_probe  # noqa: E402
import rag_answer_recovery_narrow_calibration as narrow  # noqa: E402
import rag_answer_recovery_report_artifacts as report_artifacts  # noqa: E402
import rag_answer_recovery_safe_recall_missed_row_triage as missed_triage  # noqa: E402
import rag_answer_recovery_safe_recall_tuning as safe_recall  # noqa: E402

DEFAULT_CONFIG = readiness.DEFAULT_CONFIG
DEFAULT_SAFE_RECALL_CONFIG = AI_WORKER_ROOT / "eval" / "configs" / "answer_recovery_safe_recall_tuning.yaml"
DEFAULT_MISSED_ROW_TRIAGE_CONFIG = (
    AI_WORKER_ROOT / "eval" / "configs" / "answer_recovery_safe_recall_missed_row_triage.yaml"
)
DEFAULT_REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    overrides = report_artifacts.reporting_overrides_from_args(args)
    backend_contract_kwargs = {}
    if args.skip_backend_probe:
        backend_contract_kwargs["probe_embedding_allowed_override"] = False

    result = run_tuning_report(
        config_path=readiness.resolve_path(args.config),
        safe_recall_config_path=readiness.resolve_path(args.safe_recall_config),
        missed_row_triage_config_path=readiness.resolve_path(args.missed_row_triage_config),
        report_dir=readiness.resolve_path(args.reports_dir),
        top_k=int(args.top_k),
        reporting_overrides=overrides,
        backend_contract_kwargs=backend_contract_kwargs,
    )
    print(
        json.dumps(
            {
                "overall_status": result["report"]["overall_status"],
                "artifact_profile": result["report"]["artifact_profile"],
                "compact_reports": result["compact_reports"],
                "debug_artifacts_emitted": result["report"]["debug_artifacts_emitted"],
                "legacy_cleanup_status": result["report"]["artifact_compaction"]["cleanup_status"],
                "production_index_mutation": result["report"]["guardrails"]["production_index_mutation"],
                "official_answer_denominator_opened": result["report"]["guardrails"][
                    "official_answer_denominator_opened"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--safe-recall-config", default=str(DEFAULT_SAFE_RECALL_CONFIG))
    parser.add_argument("--missed-row-triage-config", default=str(DEFAULT_MISSED_ROW_TRIAGE_CONFIG))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--top-k", type=int, default=retrieval_probe.DEFAULT_TOP_K)
    parser.add_argument(
        "--skip-backend-probe",
        action="store_true",
        help="Skip the live diagnostic embedding probe; retrieval probe will remain deferred unless backend is available.",
    )
    report_artifacts.add_reporting_args(parser)
    return parser.parse_args(argv)


def run_tuning_report(
    *,
    config_path: Path,
    safe_recall_config_path: Path,
    missed_row_triage_config_path: Path,
    report_dir: Path,
    top_k: int,
    reporting_overrides: Mapping[str, Any] | None = None,
    backend_contract_kwargs: Mapping[str, Any] | None = None,
    force_failure_after_stage_run: bool = False,
) -> dict[str, Any]:
    reporting_overrides = dict(reporting_overrides or {})
    embedding_config = report_artifacts.with_reporting_overrides(
        readiness.load_config(config_path),
        reporting_overrides,
    )
    options = report_artifacts.reporting_options(embedding_config)
    safe_config = report_artifacts.with_reporting_overrides(
        safe_recall.load_config(safe_recall_config_path),
        options,
    )
    narrow_config_path = safe_recall.resolve_path(safe_config["baseline_policy"]["source_config"])
    narrow_config = report_artifacts.with_reporting_overrides(
        narrow.load_config(narrow_config_path),
        options,
    )
    triage_config = report_artifacts.with_reporting_overrides(
        missed_triage.load_config(missed_row_triage_config_path),
        options,
    )

    stage_payloads: dict[str, Any] = {}
    configs = {
        "narrow": narrow_config,
        "safe_recall": safe_config,
        "missed_row_triage": triage_config,
        "embedding_readiness": embedding_config,
    }
    debug_artifacts_emitted = False
    cleanup_result = {
        "cleanup_status": "NOT_RUN",
        "removed": [],
        "missing": [],
        "tracked_legacy_artifacts_detected": [],
    }

    try:
        narrow_report = narrow.run_calibration(
            config=narrow_config,
            config_path=narrow_config_path,
            report_dir=report_dir,
        )
        stage_payloads["narrow_calibration"] = narrow_report

        safe_payload = safe_recall.run_safe_recall_tuning(
            config=safe_config,
            config_path=safe_recall_config_path,
            report_dir=report_dir,
        )
        stage_payloads["safe_recall_tuning"] = safe_payload

        triage_payload = missed_triage.run_triage_with_artifacts(
            config=triage_config,
            config_path=missed_row_triage_config_path,
            artifact_overrides=triage_artifact_overrides(safe_payload),
        )
        stage_payloads["missed_row_triage"] = triage_payload

        readiness_payload = readiness.run_readiness(
            config=embedding_config,
            config_path=config_path,
            backend_contract_kwargs=dict(backend_contract_kwargs or {}),
            artifact_overrides=readiness_artifact_overrides(safe_payload, triage_payload),
        )
        stage_payloads["embedding_readiness"] = readiness_payload

        backend_report = readiness.build_backend_contract_report(
            config=embedding_config,
            config_path=config_path,
            namespace_payload=readiness_payload["namespace_inventory"],
            embedding_backend=readiness_payload["embedding_backend"],
            readiness_payload=readiness_payload,
        )
        stage_payloads["embedding_backend_contract"] = backend_report

        probe_report = run_retrieval_probe_safely(
            config=embedding_config,
            readiness_report=readiness_payload,
            top_k=top_k,
        )
        stage_payloads["existing_embedding_retrieval_probe"] = probe_report

        if force_failure_after_stage_run:
            raise RuntimeError("forced compact-report failure after stage execution")

        if should_emit_debug_bundle(options):
            emit_debug_artifacts(stage_payloads=stage_payloads, configs=configs)
            debug_artifacts_emitted = True

        compact_paths = report_artifacts.compact_report_paths(
            embedding_config,
            resolve_path=readiness.resolve_path,
            report_dir=report_dir,
        )
        if (
            options["artifact_profile"] == "compact"
            and options["clean_legacy_stage_artifacts_on_compact_run"]
        ):
            cleanup_result = report_artifacts.cleanup_legacy_stage_artifacts(
                reports_dir=compact_paths["json"].parent,
                repo_root=REPO_ROOT,
            )

        verification = build_verification()
        compact_report = build_compact_json_report(
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            options=options,
            stage_payloads=stage_payloads,
            cleanup_result=cleanup_result,
            verification=verification,
            debug_artifacts_emitted=debug_artifacts_emitted,
        )
        write_compact_outputs(embedding_config, compact_paths, compact_report)
        return {
            "report": compact_report,
            "compact_reports": {
                "md": readiness.repo_relative(compact_paths["md"]),
                "json": readiness.repo_relative(compact_paths["json"]),
            },
            "stage_payloads": stage_payloads,
        }
    except Exception:
        if report_artifacts.reporting_options(embedding_config)["emit_debug_artifacts_on_failure"] and stage_payloads:
            emit_debug_artifacts(stage_payloads=stage_payloads, configs=configs, force_debug=True)
        raise


def triage_artifact_overrides(safe_payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    tuning_report = safe_payload["tuning_report"]
    return {
        "safe_recall_tuning_report": {"payload": tuning_report},
        "safe_recall_variants_csv": {"rows": tuning_report["variants"]},
        "safe_recall_selected_policy": {"payload": safe_payload["selected_policy"]},
        "safe_recall_rejected_variants_md": {
            "line_count": len(safe_recall.render_rejected_variants_md(tuning_report).splitlines())
        },
        "missed_safe_recovery_analysis": {"payload": safe_payload["missed_analysis"]},
    }


def readiness_artifact_overrides(
    safe_payload: Mapping[str, Any],
    triage_payload: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    tuning_report = safe_payload["tuning_report"]
    return {
        "safe_recall_tuning_report": {"payload": tuning_report},
        "safe_recall_selected_policy": {"payload": safe_payload["selected_policy"]},
        "safe_recall_variants_csv": {"rows": tuning_report["variants"]},
        "missed_safe_recovery_analysis": {"payload": safe_payload["missed_analysis"]},
        "missed_row_triage": {"payload": triage_payload},
    }


def run_retrieval_probe_safely(
    *,
    config: Mapping[str, Any],
    readiness_report: Mapping[str, Any],
    top_k: int,
) -> dict[str, Any]:
    try:
        return retrieval_probe.run_probe(
            config=config,
            readiness_report=readiness_report,
            top_k=top_k,
        )
    except Exception as exc:  # noqa: BLE001 - compact report should capture probe deferral reason
        return {
            "schema_version": "answer_recovery_existing_embedding_retrieval_probe_report_v1",
            "stage": retrieval_probe.STAGE,
            "status": "DEFERRED",
            "defer_reason": readiness.safe_error(exc),
            "summary": {
                "probe_row_count": 0,
                "target_found_top_k_count": 0,
                "all_targets_found_top_k": False,
                "top_k": top_k,
                "query_embedding_count": 0,
                "expected_answer_or_label_embedding_count": 0,
            },
            "namespace": "",
            "guardrails": retrieval_probe.guardrail_summary(config),
            "rows": [],
        }


def should_emit_debug_bundle(options: Mapping[str, Any]) -> bool:
    return any(
        bool(options.get(key))
        for key in (
            "emit_debug_artifacts",
            "emit_stage_reports",
            "emit_csv",
            "emit_row_manifest",
            "emit_namespace_inventory",
        )
    )


def emit_debug_artifacts(
    *,
    stage_payloads: Mapping[str, Any],
    configs: Mapping[str, Mapping[str, Any]],
    force_debug: bool = False,
) -> None:
    if force_debug:
        configs = {
            name: report_artifacts.with_reporting_overrides(config, {"artifact_profile": "debug"})
            for name, config in configs.items()
        }
    if "narrow_calibration" in stage_payloads:
        narrow.write_outputs(configs["narrow"], stage_payloads["narrow_calibration"])
    if "safe_recall_tuning" in stage_payloads:
        safe_recall.write_outputs(configs["safe_recall"], stage_payloads["safe_recall_tuning"])
    if "missed_row_triage" in stage_payloads:
        missed_triage.write_outputs(configs["missed_row_triage"], stage_payloads["missed_row_triage"])
    if "embedding_readiness" in stage_payloads:
        readiness.write_outputs(configs["embedding_readiness"], stage_payloads["embedding_readiness"])
    elif "embedding_backend_contract" in stage_payloads:
        readiness.write_backend_contract_outputs(
            configs["embedding_readiness"],
            stage_payloads["embedding_backend_contract"],
        )
    if "existing_embedding_retrieval_probe" in stage_payloads:
        retrieval_probe.write_outputs(
            configs["embedding_readiness"],
            stage_payloads["existing_embedding_retrieval_probe"],
        )


def build_compact_json_report(
    *,
    generated_at: str,
    options: Mapping[str, Any],
    stage_payloads: Mapping[str, Any],
    cleanup_result: Mapping[str, Any],
    verification: Mapping[str, Any],
    debug_artifacts_emitted: bool,
) -> dict[str, Any]:
    calibration = calibration_summary(stage_payloads["narrow_calibration"], stage_payloads["safe_recall_tuning"])
    missed = missed_recovery_summary(stage_payloads["safe_recall_tuning"]["missed_analysis"])
    triage = triage_consolidation_summary(stage_payloads["missed_row_triage"])
    backend = embedding_backend_summary(stage_payloads["embedding_backend_contract"])
    readiness_summary = embedding_readiness_summary(stage_payloads["embedding_readiness"])
    retrieval_summary = retrieval_probe_summary(stage_payloads["existing_embedding_retrieval_probe"])
    guardrails = guardrail_summary(
        stage_payloads=stage_payloads,
        embedding_backend=backend,
        embedding_readiness=readiness_summary,
        retrieval_summary=retrieval_summary,
    )
    overall_status = overall_status_from_sections(
        stage_payloads=stage_payloads,
        guardrails=guardrails,
        cleanup_result=cleanup_result,
    )
    return {
        "schema_version": "answer_recovery_tuning_report_v1",
        "artifact_compaction": {
            "schema_version": "answer_recovery_report_artifact_compaction_v1",
            "cleanup_status": cleanup_result["cleanup_status"],
            "cleaned_legacy_artifacts": cleanup_result.get("removed", []),
            "tracked_legacy_artifacts_detected": cleanup_result.get("tracked_legacy_artifacts_detected", []),
        },
        "artifact_profile": options["artifact_profile"],
        "overall_status": overall_status,
        "generated_at": generated_at,
        "production_promotion_ready": guardrails["production_promotion_ready"],
        "official_answer_denominator_ready": guardrails["official_answer_denominator_ready"],
        "official_denominator_registry_changed": guardrails["official_denominator_registry_changed"],
        "production_index_mutation": guardrails["production_index_mutation"],
        "broad_indexing": guardrails["broad_indexing"],
        "calibration": calibration,
        "missed_recovery": missed,
        "triage": triage,
        "embedding_backend": backend,
        "embedding_readiness": readiness_summary,
        "existing_embedding_retrieval_probe": retrieval_summary,
        "retrieval_probe": retrieval_summary,
        "guardrails": guardrails,
        "verification": verification,
        "debug_artifacts_emitted": debug_artifacts_emitted,
    }


def calibration_summary(
    narrow_report: Mapping[str, Any],
    safe_payload: Mapping[str, Any],
) -> dict[str, Any]:
    selected = narrow_report["selected_policy"]
    counts = selected["counts"]
    before_after = narrow_report["before_after_counts"]
    rejected = narrow_report.get("rejected_variants", [])
    safe_selected = safe_payload["selected_policy"]
    return {
        "selected_policy": selected["variant_name"],
        "safe_recall_selected_policy": safe_selected["variant_name"],
        "total_evaluated": counts["total_evaluated"],
        "before_calibration_wrongly_supported_count": before_after[
            "before_calibration_wrongly_supported_count"
        ],
        "after_calibration_wrongly_supported_count": before_after[
            "after_calibration_wrongly_supported_count"
        ],
        "recovered_after_loop": counts["recovered_after_loop"],
        "citation_coverage_before": counts["citation_coverage_before"],
        "citation_coverage_after": counts["citation_coverage_after"],
        "rejected_variant_count": len(rejected),
        "key_rejected_variants": [
            {
                "variant_name": row["variant_name"],
                "rejection_reasons": list(row.get("rejection_reasons", []))[:3],
            }
            for row in rejected[:5]
        ],
    }


def missed_recovery_summary(missed_analysis: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "total_missed_or_blocked": missed_analysis["total_missed_or_blocked"],
        "safe_recovery_candidates": missed_analysis["safe_recovery_candidate_count"],
        "blocked_by_lane": dict(missed_analysis["counts_by_lane"]),
        "blocked_by_reason": dict(missed_analysis["counts_by_reason"]),
    }


def triage_consolidation_summary(triage_payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = list(triage_payload.get("rows", []))
    counts = triage_payload["counts"]
    selection = triage_payload["selection_policy"]

    def ids_for(category: str) -> list[str]:
        return [str(row["row_id"]) for row in rows if row.get("category") == category]

    gold_review_rows = [
        {
            "row_id": str(row["row_id"]),
            "lane": str(row.get("lane", "")),
            "case_type": str(row.get("case_type", "")),
            "reason": str(row.get("recovery_or_block_reason", "")),
            "judgment_needed": (
                "User gold-policy judgment only: expected answer/evidence semantics, "
                "answerability/relevance label, and whether a future official denominator may include the row."
            ),
            "codex_decision": "not_decided",
        }
        for row in rows
        if row.get("category") == "GOLD_POLICY_REQUIRED"
    ]
    excluded_frozen = list(selection.get("excluded_frozen_gold_rows", []))
    return {
        "category_counts": dict(counts["category_counts"]),
        "row_groups": {
            "promotion_candidate": [],
            "safe_recoverable_report_only": ids_for("SAFE_RECOVERABLE_WITH_EXISTING_EVIDENCE"),
            "diagnostic_only": ids_for("DIAGNOSTIC_ONLY_DO_NOT_PROMOTE"),
            "policy_blocked_correctly": ids_for("POLICY_BLOCKED_CORRECTLY"),
            "index_scope_missing": ids_for("INDEX_SCOPE_MISSING"),
            "gold_policy_required": ids_for("GOLD_POLICY_REQUIRED"),
            "unknown_needs_manual_review": ids_for("UNKNOWN_NEEDS_MANUAL_REVIEW"),
            "excluded_frozen_gold_sourced": [str(row.get("case_id", "")) for row in excluded_frozen],
        },
        "frozen_gold_sourced_excluded_count": int(selection.get("excluded_frozen_gold_row_count") or 0),
        "frozen_gold_used_for_selection": bool(selection.get("frozen_gold_used_for_selection")),
        "frozen_gold_used_for_training": bool(selection.get("frozen_gold_used_for_training")),
        "gold_policy_required_user_review": gold_review_rows,
        "interpretation": {
            "promotion_candidate": "No current row is a production-promotion candidate.",
            "safe_recoverable_report_only": (
                "Recovered rows remain report-only evidence until human-reviewed answer/evidence labels "
                "and an explicit promotion policy exist."
            ),
            "index_scope_missing": (
                "Do not count as retrieval/ranking failures unless source evidence is proven in-scope and indexed."
            ),
            "policy_blocked_correctly": "Preserve current fail-closed blocks; do not count as recovery failures.",
            "diagnostic_only": "Do not promote OCR/IDP/multimodal or other diagnostic-only evidence.",
        },
    }


def embedding_backend_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    settings = report.get("settings_summary", {})
    return {
        "embedding_backend_available": report.get("embedding_backend_available"),
        "backend_contract_status": report.get("backend_contract_status"),
        "backend_provider_constructible": report.get("backend_provider_constructible"),
        "backend_probe_embedding_succeeded": report.get("backend_probe_embedding_succeeded"),
        "backend_embedding_model": settings.get("rag_embedding_model", ""),
        "backend_embedding_dimension_detected": report.get("backend_embedding_dimension_detected"),
        "staging_backfill_enabled_by_config": report.get("staging_backfill_enabled_by_config"),
        "staging_backfill_status": report.get("staging_backfill_status"),
        "vector_write_attempted": bool(report.get("vector_write_attempted")),
        "namespace_created": bool(report.get("namespace_created")),
        "staging_namespace_safe": bool(report.get("staging_namespace_safe")),
        "existing_vector_indexes_detected": bool(report.get("existing_vector_indexes_detected")),
    }


def embedding_readiness_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    counts = payload["counts"]
    cause_counts = dict(counts["index_scope_missing_cause_counts"])
    safe_rows = list(payload.get("safe_existing_rows", []))
    namespace_names = sorted(
        {
            namespace
            for row in safe_rows
            for namespace in row.get("existing_embedding_namespaces", [])
            if namespace
        }
    )
    return {
        "manifest_rows": counts["manifest_row_count"],
        "production_eligible_source_count": counts["classification_counts"][
            "EMBED_STAGING_PRODUCTION_ELIGIBLE_SOURCE"
        ],
        "already_embedded_safe_source_count": counts["safe_existing_already_embedded_count"],
        "existing_vector_indexes_detected": payload["embedding_backend"]["existing_vector_indexes_detected"],
        "staging_namespace_safe": payload["embedding_backend"]["staging_namespace_safe"],
        "index_scope_missing_cause_counts": cause_counts,
        "safe_evidence_row_ids": [row["row_id"] for row in safe_rows[:20]],
        "safe_evidence_chunk_ids": [row["chunk_id"] for row in safe_rows[:20] if row.get("chunk_id")],
        "namespace_names": namespace_names,
    }


def retrieval_probe_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    rows = list(report.get("rows", []))
    found_at_rank_1 = sum(1 for row in rows if row.get("target_rank") == 1)
    found_top_10 = sum(
        1
        for row in rows
        if row.get("target_rank") is not None and int(row.get("target_rank")) <= 10
    )
    rank_counts = Counter(str(row.get("target_rank") or "not_found") for row in rows)
    summary = report.get("summary", {})
    return {
        "probe_status": report.get("status"),
        "defer_reason": report.get("defer_reason", ""),
        "target_count": summary.get("probe_row_count", len(rows)),
        "found_at_rank_1_count": found_at_rank_1,
        "found_in_top_10_count": found_top_10,
        "target_found_top_k_count": summary.get("target_found_top_k_count", 0),
        "read_only": True,
        "namespace": report.get("namespace", ""),
        "rank_summary": dict(sorted(rank_counts.items())),
    }


def guardrail_summary(
    *,
    stage_payloads: Mapping[str, Any],
    embedding_backend: Mapping[str, Any],
    embedding_readiness: Mapping[str, Any],
    retrieval_summary: Mapping[str, Any],
) -> dict[str, Any]:
    del retrieval_summary
    readiness_guardrails = stage_payloads["embedding_readiness"]["guardrail_status"]
    safe_guardrails = stage_payloads["safe_recall_tuning"]["tuning_report"]["guardrail_status"]
    registry_changed = bool(
        readiness_guardrails.get("official_denominator_registry_changed")
        or safe_guardrails.get("official_denominator_registry_changed")
        or stage_payloads["narrow_calibration"].get("official_denominator_registry_changed")
    )
    return {
        "official_denominator_registry_changed": registry_changed,
        "official_answer_denominator_opened": bool(
            readiness_guardrails.get("official_answer_denominator_opened")
            or safe_guardrails.get("official_answer_denominator_opened")
        ),
        "production_index_mutation": bool(
            readiness_guardrails.get("production_index_mutation")
            or safe_guardrails.get("production_index_mutation")
        ),
        "broad_indexing": bool(readiness_guardrails.get("broad_indexing") or safe_guardrails.get("broad_indexing")),
        "frozen_gold_training_rows": int(readiness_guardrails.get("frozen_gold_training_rows") or 0),
        "frozen_gold_profile_selection": bool(readiness_guardrails.get("frozen_gold_profile_selection")),
        "expected_answer_or_label_embedding_count": int(
            readiness_guardrails.get("expected_answer_or_label_embedding_count") or 0
        ),
        "hidden_xlsx_support_eligible_count": int(
            readiness_guardrails.get("hidden_xlsx_support_eligible_count") or 0
        ),
        "pdf_file_content_mixing_support_eligible_count": int(
            readiness_guardrails.get("pdf_file_content_mixing_support_eligible_count") or 0
        ),
        "diagnostic_only_support_eligible_count": int(
            readiness_guardrails.get("diagnostic_only_support_eligible_count") or 0
        ),
        "production_promotion_ready": False,
        "official_answer_denominator_ready": False,
        "vector_write_attempted": bool(embedding_backend["vector_write_attempted"]),
        "namespace_created": bool(embedding_backend["namespace_created"]),
        "production_eligible_source_count": embedding_readiness["production_eligible_source_count"],
    }


def overall_status_from_sections(
    *,
    stage_payloads: Mapping[str, Any],
    guardrails: Mapping[str, Any],
    cleanup_result: Mapping[str, Any],
) -> str:
    blocking_guardrails = (
        guardrails["official_denominator_registry_changed"]
        or guardrails["official_answer_denominator_opened"]
        or guardrails["production_index_mutation"]
        or guardrails["broad_indexing"]
        or guardrails["frozen_gold_training_rows"] != 0
        or guardrails["frozen_gold_profile_selection"]
        or guardrails["expected_answer_or_label_embedding_count"] != 0
        or guardrails["hidden_xlsx_support_eligible_count"] != 0
        or guardrails["pdf_file_content_mixing_support_eligible_count"] != 0
        or guardrails["diagnostic_only_support_eligible_count"] != 0
        or guardrails["production_promotion_ready"]
        or guardrails["official_answer_denominator_ready"]
        or guardrails["vector_write_attempted"]
        or guardrails["namespace_created"]
    )
    if blocking_guardrails:
        return "BLOCKED"
    if cleanup_result.get("tracked_legacy_artifacts_detected"):
        return "BLOCKED"
    stage_statuses = [
        stage_payloads["narrow_calibration"].get("status"),
        stage_payloads["safe_recall_tuning"]["tuning_report"].get("status"),
        stage_payloads["missed_row_triage"].get("status"),
        stage_payloads["embedding_readiness"].get("status"),
        stage_payloads["embedding_backend_contract"].get("status"),
        stage_payloads["existing_embedding_retrieval_probe"].get("status"),
    ]
    if any(status in {"FAIL", "BLOCKED"} for status in stage_statuses):
        return "WARN"
    return "PASS"


def build_verification() -> dict[str, Any]:
    official_diff = readiness.official_registry_diff_proof()
    cached = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--quiet",
            "--",
            "ai/eval/eval_queries/official_denominator_registry.json",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "runners_executed": [
            "answer_recovery_narrow_calibration",
            "answer_recovery_missed_safe_recovery_analysis",
            "answer_recovery_embedding_backend_contract_recheck",
            "answer_recovery_embedding_readiness",
            "answer_recovery_existing_embedding_retrieval_probe",
        ],
        "pytest_results": "not_run_by_report_runner",
        "git_diff_check_result": "not_run_by_report_runner",
        "official_denominator_registry_json_diff_status": "unchanged"
        if official_diff["diff_empty"]
        else "changed",
        "official_denominator_registry_json_cached_diff_status": "unchanged"
        if cached.returncode == 0
        else "changed",
        "official_denominator_registry_diff_proof": official_diff,
        "known_warnings": [],
    }


def write_compact_outputs(
    config: Mapping[str, Any],
    paths: Mapping[str, Path],
    report: Mapping[str, Any],
) -> None:
    options = report_artifacts.reporting_options(config)
    if options["emit_machine_report"]:
        readiness.write_json(paths["json"], report)
    if options["emit_human_report"]:
        readiness.write_text(paths["md"], render_compact_md(report))


def render_compact_md(report: Mapping[str, Any]) -> str:
    lines = [
        "# Answer Recovery Tuning Report",
        "",
        "## Status",
        "",
    ]
    for key in (
        "overall_status",
        "generated_at",
        "artifact_profile",
        "production_promotion_ready",
        "official_answer_denominator_ready",
        "official_denominator_registry_changed",
        "production_index_mutation",
        "broad_indexing",
    ):
        lines.append(f"- {key}: `{report.get(key)}`")

    sections = [
        ("Calibration Summary", report["calibration"]),
        ("Missed / Blocked Recovery Summary", report["missed_recovery"]),
        ("Triage Consolidation", report["triage"]),
        ("Embedding Backend Summary", report["embedding_backend"]),
        ("Embedding Readiness Summary", report["embedding_readiness"]),
        ("Existing Embedding Retrieval Probe Summary", report["existing_embedding_retrieval_probe"]),
        ("Guardrails", report["guardrails"]),
        ("Verification", report["verification"]),
    ]
    for title, payload in sections:
        lines.extend(["", f"## {title}", ""])
        lines.extend(render_mapping(payload))
    lines.append("")
    return "\n".join(lines)


def render_mapping(payload: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, Mapping):
            compact = ", ".join(f"{subkey}={subvalue}" for subkey, subvalue in value.items())
            lines.append(f"- {key}: `{compact}`")
        elif isinstance(value, list):
            if not value:
                lines.append(f"- {key}: `[]`")
            else:
                rendered = json.dumps(value[:10], ensure_ascii=False, sort_keys=True)
                lines.append(f"- {key}: `{rendered}`")
        else:
            lines.append(f"- {key}: `{value}`")
    return lines


if __name__ == "__main__":
    sys.exit(main())
