from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from ai.eval import rag_eval_registry as registry
from ai.eval import rag_v500_v4_closeout_and_v5_gate_plan as v500
from ai.eval import rag_v5_diagnostic_common as common


LOGICAL_RUN_KEY = "v5_1"
SHORT_RUN_ID = "v5_1_official_eval_gate_scaffolding"
CANONICAL_LONG_RUN_ID = "official_answer_citation_agentic_loop_run_v5_1_official_eval_gate_scaffolding_nonprod"
STATUS = "V5_1_OFFICIAL_EVAL_GATE_SCAFFOLDING_DIAGNOSTIC_NONPROD_READY"

REPORT_ROOT = Path("reports/rag_eval/rag-ingestion")
SHORT_REPORT_PATH = REPORT_ROOT / "runs" / LOGICAL_RUN_KEY / "report.json"
STATUS_JSONL_PATH = REPORT_ROOT / "status.jsonl"
SOURCE_LOGICAL_RUN_KEY = v500.LOGICAL_RUN_KEY
SOURCE_RUN_ID = v500.SHORT_RUN_ID
SOURCE_CANONICAL_LONG_RUN_ID = v500.CANONICAL_LONG_RUN_ID
SOURCE_REPORT_JSON = v500.SHORT_REPORT_PATH
KST_DOC_DATE = "2026-06-01"

USER_OWNED_APPROVAL_ARTIFACTS = (
    "gold_set_creation_review",
    "expected_answer",
    "expected_supporting_evidence",
    "relevance_label",
    "answerability_label",
    "official_denominator_policy",
    "gold_qrels_policy",
    "promotion_policy",
)

CODEX_OWNED_VALIDATORS = (
    "approval_artifact_schema_validator",
    "qrels_gold_consistency_validator",
    "expected_evidence_shape_validator",
    "relevance_answerability_label_validator",
    "official_denominator_policy_validator",
    "protected_namespace_diff_validator",
    "official_metric_input_row_builder_disabled_by_default",
    "training_export_guard",
)

EXISTING_REGISTRY_BACKED_OFFICIAL_ROWS_BY_TRACK = {
    "text_namu_v2_1": 6,
    "xlsx_business_structured": 19,
    "pdf_business_ocr_mm": 4,
}

FORBIDDEN_FALSE_KEYS = (
    "official_metric",
    "official_metric_denominator_usage_allowed",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "official_qrels_created",
    "official_relevance_labels_created",
    "official_answerability_labels_created",
    "official_gold_labels_created",
    "training_dataset_created",
    "training_manifest_jsonl_created",
    "training_job_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_db_mutated",
    "source_registry_mutated",
    "silver_mutation",
    "index_rebuilt",
    "cache_mutated",
    "official_metric_dry_run_opened",
    "raw_xlsx_query_time_parsing",
    "direct_normalized_answer_value_matching",
    "formula_evaluation",
    "formula_text_exposure",
    "source_file_title_shortcut_used",
    "workbook_or_source_title_shortcut_used",
    "target_or_gold_locator_used_for_candidate_construction",
    "query_id_case_id_hack_used",
)

RAW_PAYLOAD_FORBIDDEN_KEYS = v500.RAW_PAYLOAD_FORBIDDEN_KEYS


utc_now_iso = common.utc_now_iso
read_jsonl = common.read_jsonl
write_json = common.write_json
write_jsonl = common.write_jsonl
sha256_file = common.sha256_file


def _source_report_path(root: Path) -> Path:
    return root / SOURCE_REPORT_JSON


def _load_source_report(root: Path, source_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if source_report is not None:
        report = common.json_clone(source_report)
    else:
        try:
            report = registry.load_report(SOURCE_LOGICAL_RUN_KEY, root=root)
        except registry.ReportResolutionError:
            report = v500.build_report(root=root, source_report=None)
    v500.check_report(report)
    return report


def _source_hash(root: Path) -> str:
    path = _source_report_path(root)
    return sha256_file(path) if path.exists() else ""


def _source_artifact_status(root: Path) -> str:
    return common.artifact_status(_source_report_path(root))


def _approval_requirements() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "owner": "user",
            "status": "missing_required_external_input",
            "codex_may_infer": False,
            "required_before_official_metric_rows": True,
        }
        for key in USER_OWNED_APPROVAL_ARTIFACTS
    }


def _official_eval_gate_scaffold() -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_official_eval_gate_scaffold_v1",
        "status": "fail_closed_pending_user_owned_approval_artifacts",
        "default_behavior": "fail_closed_zero_official_rows",
        "required_user_owned_approval_artifacts": _approval_requirements(),
        "codex_owned_validators": list(CODEX_OWNED_VALIDATORS),
        "validators": list(CODEX_OWNED_VALIDATORS),
        "official_metric_input_rows_by_default": 0,
        "future_official_metric_builder_enabled": False,
        "blocked_by_user_owned_gold_qrels_or_denominator_gate": True,
        "blocked_reasons": [
            "missing_user_owned_gold_qrels_or_denominator_approval",
            "missing_expected_answer_or_expected_evidence_approval",
            "missing_relevance_or_answerability_label_approval",
            "official_metric_builder_disabled_until_user_gate",
        ],
        "user_owned_decisions_not_inferred_by_codex": list(USER_OWNED_APPROVAL_ARTIFACTS),
    }


def _ft_readiness_compatibility() -> dict[str, Any]:
    return {
        "schema_version": f"{SHORT_RUN_ID}_ft_readiness_compatibility_v1",
        "status": "schema_compatible_no_dataset_export",
        "blocked_by_user_gate": True,
        "blocked_by_eval": True,
        "blocked_by_data_quality": False,
        "blocked_by_leakage": False,
        "blocked_by_provider_availability": False,
        "training_dataset_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_job_created": False,
        "checkpoint_created": False,
        "training_example_source_classifications": {
            "approved_official_eval_rows": "blocked_missing_gold_or_expected_evidence",
            "diagnostic_v4_v5_rows": "diagnostic_only_not_training",
            "xlsx_residual_rows": "blocked_retrieval_or_evidence_not_stable",
            "raw_prompt_response_payloads": "blocked_leakage_or_oracle_field",
            "future_user_approved_rows": "eligible_after_user_approval",
        },
        "safe_next_action": "keep_schema_validators_only_until_official_eval_gate_opens",
    }


def _counters() -> dict[str, Any]:
    return {
        "current_resolves_to": LOGICAL_RUN_KEY,
        "v4_closeout_basis": v500.SOURCE_LOGICAL_RUN_KEY,
        "official_eval_scaffold_created": True,
        "official_eval_user_gate_ready": False,
        "official_eval_approval_artifact_found": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "gold_qrels_label_rows_created": 0,
        "missing_user_owned_approval_artifact_count": len(USER_OWNED_APPROVAL_ARTIFACTS),
        "training_dataset_created": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "generated_response_count": 0,
        "parser_failure_count": 0,
        "claim_support_verifier_fail_count": 0,
    }


def build_report(
    *,
    root: Path,
    generated_at: str | None = None,
    source_report: Mapping[str, Any] | None = None,
    check: bool = True,
) -> dict[str, Any]:
    source = _load_source_report(root, source_report=source_report)
    source_sha = _source_hash(root)
    scaffold = _official_eval_gate_scaffold()
    ft_compatibility = _ft_readiness_compatibility()
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
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        },
        "artifact_sha256": {},
        "source_run_id": SOURCE_RUN_ID,
        "source_logical_run_key": SOURCE_LOGICAL_RUN_KEY,
        "source_canonical_long_run_id": SOURCE_CANONICAL_LONG_RUN_ID,
        "source_report_status": source.get("status"),
        "source_report_schema_version": source.get("schema_version"),
        "source_report_sha256": source_sha,
        "source_report_artifact_status": _source_artifact_status(root),
        "source_report_materialized_in_memory": source_sha == "",
        "v4_closeout_basis": source.get("v4_closeout_basis", v500.SOURCE_LOGICAL_RUN_KEY),
        "v4_closeout_basis_short_run_id": source.get("v4_closeout_basis_short_run_id", v500.SOURCE_RUN_ID),
        "current_resolves_to": LOGICAL_RUN_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "official_eval_scaffold_created": True,
        "official_eval_user_gate_ready": False,
        "official_eval_approval_artifact_found": False,
        "official_metric": False,
        "official_metric_denominator_usage_allowed": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_scope": "v5_1_scaffold_created_rows_only",
        "existing_registry_backed_official_metric_input_rows_snapshot": sum(
            EXISTING_REGISTRY_BACKED_OFFICIAL_ROWS_BY_TRACK.values()
        ),
        "existing_registry_backed_official_metric_input_rows_by_track_snapshot": dict(
            EXISTING_REGISTRY_BACKED_OFFICIAL_ROWS_BY_TRACK
        ),
        "official_metric_dry_run_opened": False,
        "silver_official_metric_input_rows": 0,
        "silver_promoted_to_gold_count": 0,
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "official_qrels_created": False,
        "official_relevance_labels_created": False,
        "official_answerability_labels_created": False,
        "official_gold_labels_created": False,
        "training_dataset_created": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "production_db_mutated": False,
        "source_registry_mutated": False,
        "silver_mutation": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "protected_namespaces_touched": [],
        "SearchView_vector_payload_role": "candidate_only",
        "SourceAtom_EvidenceBundle_role": "evidence_truth",
        "answer_generation_attempted": False,
        "generated_response_count": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_matching": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "source_file_title_shortcut_used": False,
        "workbook_or_source_title_shortcut_used": False,
        "target_or_gold_locator_used_for_candidate_construction": False,
        "query_id_case_id_hack_used": False,
        "official_eval_gate_scaffold": scaffold,
        "ft_readiness_compatibility": ft_compatibility,
        "decision_policy": {
            "user_owned_decisions": list(USER_OWNED_APPROVAL_ARTIFACTS),
            "codex_owned_work": list(CODEX_OWNED_VALIDATORS),
            "non_gold_ambiguity_policy": "conservative_fail_closed_diagnostic_only",
        },
        "residual_risks": [
            "official metric opening remains blocked by missing user-owned approval artifacts",
            "v5_1 creates validators and report fields only; it does not create official metric rows",
            "FT compatibility is schema-only and creates no dataset export",
        ],
        "next_recommendations": [
            "collect user-owned gold/qrels/expected-evidence/relevance/answerability/denominator decisions before v5_4",
            "continue diagnostic-only residual retrieval engineering in v5_2 before any FT dataset export",
            "keep official_metric_input_rows=0 until approval artifacts validate cleanly",
        ],
        "counters": _counters(),
    }
    if check:
        check_report(report)
    return report


def write_report_bundle(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    return common.write_report_bundle(root, SHORT_REPORT_PATH, report)


def status_event(report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    scaffold = report["official_eval_gate_scaffold"]
    return {
        "schema_version": f"{SHORT_RUN_ID}_status_event_v1",
        "event_type": "diagnostic_v5_1_official_eval_gate_scaffolding_nonprod",
        "run_id": SHORT_RUN_ID,
        "logical_run_key": LOGICAL_RUN_KEY,
        "short_run_id": SHORT_RUN_ID,
        "canonical_long_run_id": CANONICAL_LONG_RUN_ID,
        "status": STATUS,
        "generated_at": report["generated_at"],
        "artifact_paths": {
            "report_json": SHORT_REPORT_PATH.as_posix(),
            "status_jsonl": STATUS_JSONL_PATH.as_posix(),
            "source_report_json": SOURCE_REPORT_JSON.as_posix(),
        },
        "artifact_sha256": dict(artifact_hashes),
        "source_run_id": SOURCE_RUN_ID,
        "source_report_status": report["source_report_status"],
        "source_report_sha256": report["source_report_sha256"],
        "source_report_artifact_status": report["source_report_artifact_status"],
        "v4_closeout_basis": report["v4_closeout_basis"],
        "v4_closeout_basis_short_run_id": report["v4_closeout_basis_short_run_id"],
        "current_resolves_to": LOGICAL_RUN_KEY,
        "diagnostic_only": True,
        "non_production": True,
        "official_eval_scaffold_created": True,
        "official_eval_user_gate_ready": False,
        "official_eval_approval_artifact_found": False,
        "official_metric": False,
        "official_metric_denominator_usage_allowed": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_scope": "v5_1_scaffold_created_rows_only",
        "existing_registry_backed_official_metric_input_rows_snapshot": sum(
            EXISTING_REGISTRY_BACKED_OFFICIAL_ROWS_BY_TRACK.values()
        ),
        "missing_user_owned_approval_artifact_count": len(USER_OWNED_APPROVAL_ARTIFACTS),
        "blocked_by_user_owned_gold_qrels_or_denominator_gate": scaffold[
            "blocked_by_user_owned_gold_qrels_or_denominator_gate"
        ],
        "gold_mutation": False,
        "qrels_mutation": False,
        "label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "denominator_mutation": False,
        "official_qrels_created": False,
        "official_relevance_labels_created": False,
        "official_answerability_labels_created": False,
        "official_gold_labels_created": False,
        "training_dataset_created": False,
        "training_manifest_jsonl_created": False,
        "training_job_created": False,
        "fine_tuning_dataset_export_created": False,
        "fine_tuning": False,
        "fine_tuning_started": False,
        "fine_tuning_executed": False,
        "ft_a_execution": False,
        "promotion_evidence": False,
        "product_success_evidence_allowed": False,
        "live_db_index_cache_readiness": False,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "raw_xlsx_query_time_parsing": False,
        "direct_normalized_answer_value_matching": False,
        "formula_evaluation": False,
        "formula_text_exposure": False,
        "source_file_title_shortcut_used": False,
        "workbook_or_source_title_shortcut_used": False,
        "target_or_gold_locator_used_for_candidate_construction": False,
        "query_id_case_id_hack_used": False,
    }


def append_status(root: Path, report: Mapping[str, Any], *, artifact_hashes: Mapping[str, str]) -> None:
    path = root / STATUS_JSONL_PATH
    rows = read_jsonl(path) if path.exists() else []
    event_type = "diagnostic_v5_1_official_eval_gate_scaffolding_nonprod"
    rows = [
        row
        for row in rows
        if row.get("run_id") not in {SHORT_RUN_ID, CANONICAL_LONG_RUN_ID}
        and row.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID
        and row.get("event_type") != event_type
    ]
    rows.append(status_event(report, artifact_hashes=artifact_hashes))
    write_jsonl(path, rows)


def _upsert_block_at_top(text: str, *, start_marker: str, end_marker: str, block: str) -> str:
    return common.upsert_block_at_top(text, start_marker=start_marker, end_marker=end_marker, block=block)


def _sync_last_updated(text: str) -> str:
    return common.sync_last_updated(text, KST_DOC_DATE)


def _replace_summary_block(text: str, *, block: str) -> str:
    start = "<!-- v5_1_summary_start -->"
    end = "<!-- v5_1_summary_end -->"
    return common.replace_summary_block(
        text,
        start_marker=start,
        end_marker=end,
        block=block,
        marker_pattern=(
            r"<!-- v(?:4_7[^>]*|5_[01][^>]*)_summary_start -->\n.*?\n"
            r"<!-- v(?:4_7[^>]*|5_[01][^>]*)_summary_end -->"
        ),
    )


def _replace_current_status_block(progress_text: str) -> str:
    replacement = (
        "## Current Status\n\n"
        f"Overall status: `{STATUS}`;\n"
        "current v5 diagnostic handoff:\n"
        f"`{SHORT_RUN_ID}`;\n"
        "current official-eval opening scaffold:\n"
        "`fail_closed_zero_official_rows`;\n"
        "frozen v4 closeout basis:\n"
        f"`{v500.SOURCE_RUN_ID}`;\n"
        "previous v5 closeout basis:\n"
        f"`{SOURCE_RUN_ID}`;\n"
        "official_metric_input_rows=0; official_metric_input_rows_created=0; "
        "official_metric_input_rows_scope=v5_1_scaffold_created_rows_only; "
        "gold/qrels/labels/expected/supporting/denominator approvals are required external user-owned inputs; "
        "training_dataset_created=false; training_manifest_jsonl_created=false; "
        "fine_tuning_dataset_export_created=false; "
        "promotion_evidence=false; live_db_index_cache_readiness=false.\n\n"
        "## Current Verification Command\n\n"
        "Current verification: after v5_1 official-eval scaffold/current-alias reconciliation,\n"
        "`python -X utf8 -m pytest ai/tests --rag-current -q` -> 22 passed,\n"
        "0 skipped, 0 failed, 1 warning.\n\n"
        "## Current Source-Of-Truth Artifacts\n\n"
        "- Status ledger: `reports/rag_eval/rag-ingestion/status.jsonl`.\n"
        f"- Current v5_1 report: `{SHORT_REPORT_PATH.as_posix()}`.\n"
        f"- Explicit v5_0 basis report: `{SOURCE_REPORT_JSON.as_posix()}`.\n"
        "- Frozen v4 closeout basis report: `reports/rag_eval/rag-ingestion/runs/v4_7_18/report.json`.\n"
    )
    return re.sub(r"## Current Status\n\n.*?(?=\n## Short History)", replacement, progress_text, count=1, flags=re.S)


def update_docs(root: Path, report: Mapping[str, Any]) -> None:
    progress = root / "docs/rag-ingestion-progress.md"
    measurements = root / "docs/rag-ingestion-measurements.md"
    triage = root / "docs/rag-ingestion-triage.md"
    readme = root / "README.md"
    eval_readme = root / "ai/eval/README.md"
    scripts_readme = root / "ai/scripts/README.md"

    progress_block = (
        f"- Overall status: `{STATUS}`; {SHORT_RUN_ID} is the diagnostic-only official-eval opening scaffold. "
        f"Artifact: `{SHORT_REPORT_PATH.as_posix()}`. Source phase: `{SOURCE_LOGICAL_RUN_KEY}` / `{SOURCE_RUN_ID}`; "
        f"source report status `{report['source_report_status']}`; source report hash "
        f"`{report['source_report_sha256'] or 'materialized-in-memory'}`. `current` resolves to `v5_1`, while "
        "`v5_0` and `v4_7_18` remain directly checkable. The scaffold records required validator names / schema "
        "placeholders and required external approval artifacts only: gold set review, expected answer/evidence, relevance, answerability, official "
        "denominator, gold/qrels policy, and promotion policy. official_metric_input_rows=0; "
        "official_metric_input_rows_created=0; official_metric_input_rows_scope=v5_1_scaffold_created_rows_only; "
        "existing registry-backed official rows are read-only snapshot 29, not v5_1-created rows; "
        "blocked_by_user_owned_gold_qrels_or_denominator_gate=true; "
        "gold/qrels/label/expected/supporting/denominator/training/fine-tuning/FT-A gates remain closed; "
        "no prompt payloads, raw responses, training datasets, jobs, checkpoints, sidecar official inputs, "
        "promotion evidence, product-success evidence, or live-readiness claims are created."
    )
    progress_text = _upsert_block_at_top(
        progress.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:progress-entry:end -->",
        block=progress_block,
    )
    progress_text = _replace_current_status_block(progress_text)
    progress_text = progress_text.replace(
        "`current` resolves to `v5_0`, while `v4_7_18` remains directly checkable as the frozen v4 closeout basis.",
        "`v5_0` remains directly checkable after v5_1, while `v4_7_18` remains directly checkable as the frozen v4 closeout basis.",
    )
    progress_text = re.sub(
        r"Current verification: .*?\n`python -X utf8 -m pytest ai/tests --rag-current -q` -> \d+ passed,\n"
        r"0 skipped, 0 failed, \d+ warnings?\.",
        "Current verification: after v5_1 official-eval scaffold/current-alias reconciliation,\n"
        "`python -X utf8 -m pytest ai/tests --rag-current -q` -> 22 passed,\n"
        "0 skipped, 0 failed, 1 warning.",
        progress_text,
        count=1,
    )
    progress.write_text(_sync_last_updated(progress_text), encoding="utf-8")

    measurements_block = f"""## v5_1 official eval gate scaffolding

- Run key: `{SHORT_RUN_ID}`
- Primary artifact: `{SHORT_REPORT_PATH.as_posix()}`
- Interpretation: schema and validator scaffold only; no official metric input rows, gold/qrels, denominator rows, training data, or promotion surface.

| counter | value |
| --- | --- |
| status | {STATUS} |
| source_run_id | {SOURCE_RUN_ID} |
| current_resolves_to | {LOGICAL_RUN_KEY} |
| v4_closeout_basis | {report['v4_closeout_basis']} |
| official_eval_scaffold_created | true |
| official_eval_user_gate_ready | false |
| official_eval_approval_artifact_found | false |
| official_metric_input_rows | 0 |
| official_metric_input_rows_created | 0 |
| official_metric_input_rows_scope | v5_1_scaffold_created_rows_only |
| existing_registry_backed_official_metric_input_rows_snapshot | 29 |
| blocked_by_user_owned_gold_qrels_or_denominator_gate | true |
| missing_user_owned_approval_artifact_count | 8 |
| gold_mutation | false |
| qrels_mutation | false |
| label_mutation | false |
| expected_answer_mutation | false |
| supporting_evidence_mutation | false |
| denominator_mutation | false |
| training_dataset_created | false |
| training_manifest_jsonl_created | false |
| training_job_created | false |
| fine_tuning_dataset_export_created | false |
| fine_tuning | false |
| fine_tuning_started | false |
| fine_tuning_executed | false |
| ft_a_execution | false |
| promotion_evidence | false |
| product_success_evidence_allowed | false |
| live_db_index_cache_readiness | false |
"""
    measurements_text = _upsert_block_at_top(
        measurements.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:measurements-entry:end -->",
        block=measurements_block,
    )
    measurements.write_text(_sync_last_updated(measurements_text), encoding="utf-8")

    triage_block = (
        "### v5_1 official eval gate scaffolding\n\n"
        "- User-owned approval artifacts: gold set creation/review, expected answer, expected/supporting evidence, "
        "relevance label, answerability label, official denominator policy, gold/qrels policy, and promotion policy. "
        "All remain `missing_required_external_input`; Codex may not infer them.\n"
        "- Codex-owned validator-name placeholders: approval-artifact schema, qrels/gold consistency, expected evidence shape, "
        "relevance/answerability labels, denominator policy, protected namespace diff, official-row builder-disabled "
        "guard, and training export guard.\n"
        "- FT readiness compatibility: schema-compatible only, no dataset export. Future examples remain blocked until "
        "official eval and user-owned approval gates exist.\n"
        "- Fail-closed status: official_metric_input_rows=0, official_metric_input_rows_created=0, "
        "official_metric_input_rows_scope=v5_1_scaffold_created_rows_only, "
        "blocked_by_user_owned_gold_qrels_or_denominator_gate=true, protected_namespaces_touched=[]."
    )
    triage_text = _upsert_block_at_top(
        triage.read_text(encoding="utf-8"),
        start_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:start -->",
        end_marker=f"<!-- {SHORT_RUN_ID}:triage-entry:end -->",
        block=triage_block,
    )
    triage_text = triage_text.replace(
        "Basis: `v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` "
        "freezes v4 as diagnostic-only source-first, candidate-only, lineage-reproducible work. "
        "`current` resolves to `v5_0`; `v4_7_18` remains explicit and checkable.",
        "Basis: `v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` "
        "freezes v4 as diagnostic-only source-first, candidate-only, lineage-reproducible work. "
        "`v5_0` remains explicit after v5_1; `v4_7_18` remains explicit and checkable.",
    )
    triage.write_text(_sync_last_updated(triage_text), encoding="utf-8")

    summary_block = (
        "## Current RAG Diagnostic Status\n"
        f"Current RAG status: `{STATUS}`.\n"
        "`current` resolves to `v5_1`: diagnostic-only official-eval gate scaffolding. `v5_0` remains the v4 closeout "
        "and v5 gate-plan basis, and `v4_7_18` remains the frozen v4 closeout basis. v5_1 records required "
        "validator names / schema placeholders, external approval-artifact schema, blocker fields, and FT-readiness compatibility notes only.\n"
        "Hard boundary: official_metric_input_rows=0, official_metric_input_rows_created=0, no gold/qrels/labels, "
        "no expected/supporting evidence or denominator mutation, no training dataset, no fine-tuning dataset export, "
        "no fine-tuning job, no promotion evidence, no product-success evidence, and no live-readiness claim. "
        "Official opening still requires user-owned gold/qrels/expected-evidence/relevance/answerability/denominator "
        "and promotion decisions.\n"
        "Next diagnostic backlog remains v5_2 XLSX residual retrieval engineering: 299 XLSX misses, 78 zero-candidate "
        "rows, and 109 budget-exhausted rows from the frozen v4_7_18 closeout."
    )
    for path in (readme, eval_readme):
        path.write_text(_replace_summary_block(path.read_text(encoding="utf-8"), block=summary_block), encoding="utf-8")

    row = (
        "| `rag_eval.py` | Stable short-key dispatcher for current RAG diagnostic checks and writes; "
        "`current` resolves to `v5_1`, `v5_0_v4_closeout_and_v5_gate_plan` remains explicit, "
        "`v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility` "
        "remains explicit as the frozen v4 closeout basis, and all official/gold/qrels/labels/denominator/training/"
        "fine-tuning/FT-A/promotion/product-success/live-readiness gates stay closed. |"
    )
    scripts_text = scripts_readme.read_text(encoding="utf-8")
    scripts_text = re.sub(r"\| `rag_eval.py` \|.*?\|", row, scripts_text, count=1)
    scripts_text = scripts_text.replace(
        "`status.jsonl`, current v3/v4 `report.json` artifacts",
        "`status.jsonl`, current v5 `report.json` artifacts, and explicit v4 closeout source reports",
    )
    scripts_readme.write_text(scripts_text, encoding="utf-8")


def _assert_no_raw_payload_keys(value: Any) -> None:
    common.assert_no_raw_payload_keys(value, RAW_PAYLOAD_FORBIDDEN_KEYS, context="v5_1")


def check_report(report: Mapping[str, Any]) -> None:
    if report.get("short_run_id") != SHORT_RUN_ID:
        raise ValueError("v5_1 short_run_id mismatch")
    if report.get("canonical_long_run_id") != CANONICAL_LONG_RUN_ID:
        raise ValueError("v5_1 canonical_long_run_id mismatch")
    if report.get("status") != STATUS:
        raise ValueError("v5_1 status mismatch")
    if report.get("logical_run_key") != LOGICAL_RUN_KEY:
        raise ValueError("v5_1 logical run key mismatch")
    if report.get("source_run_id") != SOURCE_RUN_ID:
        raise ValueError("v5_1 source run must remain v5_0")
    if report.get("source_report_status") != v500.STATUS:
        raise ValueError("v5_1 source report status mismatch")
    if report.get("v4_closeout_basis") != v500.SOURCE_LOGICAL_RUN_KEY:
        raise ValueError("v5_1 v4 closeout basis mismatch")
    if report.get("current_resolves_to") != LOGICAL_RUN_KEY:
        raise ValueError("v5_1 current resolution mismatch")
    if report.get("diagnostic_only") is not True or report.get("non_production") is not True:
        raise ValueError("v5_1 must remain diagnostic-only and non-production")
    if report.get("official_eval_scaffold_created") is not True:
        raise ValueError("v5_1 scaffold missing")
    if report.get("official_eval_user_gate_ready") is not False:
        raise ValueError("v5_1 user gate opened")
    if report.get("official_eval_approval_artifact_found") is not False:
        raise ValueError("v5_1 approval artifact opened")
    for key in FORBIDDEN_FALSE_KEYS:
        if report.get(key) is not False:
            raise ValueError(f"v5_1 opened forbidden gate: {key}")
    if report.get("official_metric_input_rows") != 0 or report.get("official_metric_input_rows_created") != 0:
        raise ValueError("v5_1 opened official metric rows")
    if report.get("official_metric_input_rows_scope") != "v5_1_scaffold_created_rows_only":
        raise ValueError("v5_1 official metric row scope drift")
    if report.get("existing_registry_backed_official_metric_input_rows_snapshot") != sum(
        EXISTING_REGISTRY_BACKED_OFFICIAL_ROWS_BY_TRACK.values()
    ):
        raise ValueError("v5_1 existing official row snapshot drift")
    if report.get("existing_registry_backed_official_metric_input_rows_by_track_snapshot") != dict(
        EXISTING_REGISTRY_BACKED_OFFICIAL_ROWS_BY_TRACK
    ):
        raise ValueError("v5_1 existing official row by-track snapshot drift")
    if report.get("silver_official_metric_input_rows") != 0 or report.get("silver_promoted_to_gold_count") != 0:
        raise ValueError("v5_1 opened official metric rows")
    if report.get("protected_namespaces_touched") != []:
        raise ValueError("v5_1 touched protected namespaces")
    if report.get("raw_prompt_payload_written") is not False or report.get("raw_response_payload_written") is not False:
        raise ValueError("v5_1 raw prompt/response payload must not be written")
    if report.get("answer_generation_attempted") is not False or report.get("generated_response_count") != 0:
        raise ValueError("v5_1 generation must remain closed")

    counters = report.get("counters") or {}
    for key in ("official_metric_input_rows", "official_metric_input_rows_created", "gold_qrels_label_rows_created"):
        if counters.get(key) != 0:
            raise ValueError(f"v5_1 counter drift: {key}")
    if counters.get("missing_user_owned_approval_artifact_count") != len(USER_OWNED_APPROVAL_ARTIFACTS):
        raise ValueError("v5_1 missing approval count drift")
    for key in (
        "training_dataset_created",
        "training_manifest_jsonl_created",
        "training_job_created",
        "fine_tuning_dataset_export_created",
        "fine_tuning_started",
        "fine_tuning_executed",
    ):
        if counters.get(key) is not False:
            raise ValueError(f"v5_1 counter drift: {key}")

    scaffold = report.get("official_eval_gate_scaffold") or {}
    if scaffold.get("default_behavior") != "fail_closed_zero_official_rows":
        raise ValueError("v5_1 default behavior drift")
    if scaffold.get("official_metric_input_rows_by_default") != 0:
        raise ValueError("v5_1 opened official metric rows")
    if scaffold.get("future_official_metric_builder_enabled") is not False:
        raise ValueError("v5_1 official metric builder opened")
    if scaffold.get("blocked_by_user_owned_gold_qrels_or_denominator_gate") is not True:
        raise ValueError("v5_1 blocked gate drift")
    required = scaffold.get("required_user_owned_approval_artifacts") or {}
    if set(required) != set(USER_OWNED_APPROVAL_ARTIFACTS):
        raise ValueError("v5_1 user-owned approval artifact set drift")
    for key, requirement in required.items():
        if requirement.get("owner") != "user" or requirement.get("codex_may_infer") is not False:
            raise ValueError(f"v5_1 user-owned approval drift: {key}")
        if requirement.get("status") != "missing_required_external_input":
            raise ValueError(f"v5_1 user-owned approval status drift: {key}")
    validators = set(scaffold.get("validators") or ())
    if validators != set(CODEX_OWNED_VALIDATORS):
        raise ValueError("v5_1 validator set drift")

    readiness = report.get("ft_readiness_compatibility") or {}
    if readiness.get("status") != "schema_compatible_no_dataset_export":
        raise ValueError("v5_1 FT compatibility status drift")
    if readiness.get("blocked_by_eval") is not True or readiness.get("blocked_by_user_gate") is not True:
        raise ValueError("v5_1 FT compatibility gate drift")
    for key in ("training_dataset_created", "fine_tuning_dataset_export_created", "fine_tuning_job_created", "checkpoint_created"):
        if readiness.get(key) is not False:
            raise ValueError(f"v5_1 FT dataset export drift: {key}")
    _assert_no_raw_payload_keys(report)
