from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")

V4_7_PREOFFICIAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_preofficial_"
    "external_holdout_candidate_manifest_registration_nonprod"
)
V4_7_PREOFFICIAL_STATUS = "V4_7_PREOFFICIAL_EXTERNAL_HOLDOUT_CANDIDATE_MANIFEST_REGISTRATION_READY"

V4_7_2_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_2_"
    "source_grounded_korean_query_review_packet_hydration_nonprod"
)
V4_7_2_STATUS = "DIAGNOSTIC_V4_7_2_SOURCE_GROUNDED_KOREAN_QUERY_REVIEW_PACKET_HYDRATION_NONPROD_READY"

V4_7_3_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_3_"
    "human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
)
V4_7_3_STATUS = "V4_7_3_HUMAN_REVIEWED_KOREAN_QUERY_CANDIDATE_PASS_EXCLUSION_APPLICATION_NONPROD_READY"

V4_7_4_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_4_"
    "pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
)
V4_7_4_STATUS = "V4_7_4_PDF_SURVIVOR_RETRIEVAL_EVIDENCE_ANSWER_QUALITY_REPLAY_NONPROD_READY"

V4_7_5_SHORT_KEY = "v4_7_5"
V4_7_5_SHORT_RUN_ID = "v4_7_5_pdf_evidence_repair_eval_compaction"
V4_7_5_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_5_pdf_survivor_"
    "evidence_window_repair_and_eval_surface_compaction_nonprod"
)
V4_7_5_STATUS = "V4_7_5_PDF_EVIDENCE_REPAIR_EVAL_COMPACTION_NONPROD_READY"

V4_7_6_SHORT_KEY = "v4_7_6"
V4_7_6_SHORT_RUN_ID = "v4_7_6_eval_artifact_archive_purge"
V4_7_6_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_6_"
    "eval_artifact_external_archive_and_purge_nonprod"
)
V4_7_6_STATUS = "V4_7_6_EVAL_ARTIFACT_ARCHIVE_PURGE_NONPROD_READY"

V4_7_7_SHORT_KEY = "v4_7_7"
V4_7_7_SHORT_RUN_ID = "v4_7_7_v3_legacy_archive_and_runner_consolidation"
V4_7_7_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_7_"
    "v3_legacy_artifact_archive_and_diagnostic_runner_consolidation_nonprod"
)
V4_7_7_STATUS = "V4_7_7_V3_LEGACY_ARCHIVE_RUNNER_CONSOLIDATION_NONPROD_READY"

V4_7_8_SHORT_KEY = "v4_7_8"
V4_7_8_SHORT_RUN_ID = "v4_7_8_test_doc_dependency_decoupling_runner_alias_expansion"
V4_7_8_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_8_"
    "test_doc_dependency_decoupling_and_legacy_runner_alias_expansion_nonprod"
)
V4_7_8_STATUS = "V4_7_8_TEST_DOC_DEPENDENCY_DECOUPLING_RUNNER_ALIAS_EXPANSION_NONPROD_READY"

V4_7_9_SHORT_KEY = "v4_7_9"
V4_7_9_SHORT_RUN_ID = "v4_7_9_pdf_evidence_residual_answer_quality_replay"
V4_7_9_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_9_"
    "pdf_evidence_residual_answer_quality_replay_nonprod"
)
V4_7_9_STATUS = "V4_7_9_PDF_EVIDENCE_RESIDUAL_ANSWER_QUALITY_REPLAY_NONPROD_READY"

V4_7_10_SHORT_KEY = "v4_7_10"
V4_7_10_SHORT_RUN_ID = "v4_7_10_pdf_korean_evidence_normalization_and_answer_replay_readiness"
V4_7_10_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_10_"
    "pdf_korean_evidence_normalization_and_answer_replay_readiness_nonprod"
)
V4_7_10_STATUS = "V4_7_10_PDF_KOREAN_EVIDENCE_NORMALIZATION_AND_ANSWER_REPLAY_READINESS_NONPROD_READY"

V4_7_11_SHORT_KEY = "v4_7_11"
V4_7_11_SHORT_RUN_ID = "v4_7_11_actual_llm_answer_replay_and_silver_diagnostic_smoke"
V4_7_11_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_11_"
    "actual_llm_answer_replay_and_silver_diagnostic_smoke_nonprod"
)
V4_7_11_STATUS = "V4_7_11_ACTUAL_LLM_ANSWER_REPLAY_AND_SILVER_DIAGNOSTIC_SMOKE_NONPROD_READY"

V4_7_12_SHORT_KEY = "v4_7_12"
V4_7_12_SHORT_RUN_ID = "v4_7_12_layered_retrieval_generalization_and_overfit_audit"
V4_7_12_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_12_"
    "layered_retrieval_generalization_and_overfit_audit_nonprod"
)
V4_7_12_STATUS = "V4_7_12_LAYERED_RETRIEVAL_GENERALIZATION_AND_OVERFIT_AUDIT_NONPROD_READY"

V4_7_13_SHORT_KEY = "v4_7_13"
V4_7_13_SHORT_RUN_ID = "v4_7_13_live_retrieval_answerability_and_full_pdf_replay"
V4_7_13_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_13_"
    "live_retrieval_answerability_and_full_pdf_replay_nonprod"
)
V4_7_13_STATUS = "V4_7_13_LIVE_RETRIEVAL_ANSWERABILITY_AND_FULL_PDF_REPLAY_NONPROD_READY"

V4_7_14_SHORT_KEY = "v4_7_14"
V4_7_14_SHORT_RUN_ID = "v4_7_14_diagnostic_precondition_hardening"
V4_7_14_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_14_"
    "diagnostic_precondition_hardening_nonprod"
)
V4_7_14_STATUS = "V4_7_14_DIAGNOSTIC_PRECONDITION_HARDENING_NONPROD_READY"

V4_7_15_SHORT_KEY = "v4_7_15"
V4_7_15_SHORT_RUN_ID = "v4_7_15_read_only_searchindex_replay_projection"
V4_7_15_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_15_"
    "read_only_searchindex_replay_projection_nonprod"
)
V4_7_15_STATUS = "V4_7_15_READ_ONLY_SEARCHINDEX_REPLAY_PROJECTION_NONPROD_READY"

V4_7_16_SHORT_KEY = "v4_7_16"
V4_7_16_SHORT_RUN_ID = "v4_7_16_target_recall_repair_prototype"
V4_7_16_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_16_"
    "target_recall_repair_prototype_nonprod"
)
V4_7_16_STATUS = "V4_7_16_TARGET_RECALL_REPAIR_PROTOTYPE_NONPROD_READY"

V4_7_17_SHORT_KEY = "v4_7_17"
V4_7_17_SHORT_RUN_ID = "v4_7_17_candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit"
V4_7_17_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_17_"
    "candidate_only_generalization_validation_and_xlsx_table_axis_repair_audit_nonprod"
)
V4_7_17_STATUS = "V4_7_17_CANDIDATE_ONLY_GENERALIZATION_VALIDATION_AND_XLSX_TABLE_AXIS_REPAIR_AUDIT_NONPROD_READY"
V4_7_18_SHORT_KEY = "v4_7_18"
V4_7_18_SHORT_RUN_ID = "v4_7_18_xlsx_candidate_only_materialization_repair_and_lineage_reproducibility"
V4_7_18_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_18_"
    "xlsx_candidate_only_materialization_repair_and_lineage_reproducibility_nonprod"
)
V4_7_18_STATUS = "V4_7_18_XLSX_CANDIDATE_ONLY_MATERIALIZATION_REPAIR_AND_LINEAGE_REPRODUCIBILITY_NONPROD_READY"
V5_0_SHORT_KEY = "v5_0"
V5_0_SHORT_RUN_ID = "v5_0_v4_closeout_and_v5_gate_plan"
V5_0_LONG_RUN_ID = "official_answer_citation_agentic_loop_run_v5_0_v4_closeout_and_v5_gate_plan_nonprod"
V5_0_STATUS = "V5_0_V4_CLOSEOUT_AND_V5_GATE_PLAN_DIAGNOSTIC_NONPROD_READY"
V5_1_SHORT_KEY = "v5_1"
V5_1_SHORT_RUN_ID = "v5_1_official_eval_gate_scaffolding"
V5_1_LONG_RUN_ID = "official_answer_citation_agentic_loop_run_v5_1_official_eval_gate_scaffolding_nonprod"
V5_1_STATUS = "V5_1_OFFICIAL_EVAL_GATE_SCAFFOLDING_DIAGNOSTIC_NONPROD_READY"
V5_2_SHORT_KEY = "v5_2"
V5_2_SHORT_RUN_ID = "v5_2_xlsx_residual_candidate_only_retrieval_engineering"
V5_2_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_2_"
    "xlsx_residual_candidate_only_retrieval_engineering_nonprod"
)
V5_2_STATUS = "V5_2_XLSX_RESIDUAL_CANDIDATE_ONLY_RETRIEVAL_ENGINEERING_DIAGNOSTIC_NONPROD_READY"
V5_3_SHORT_KEY = "v5_3"
V5_3_SHORT_RUN_ID = "v5_3_pdf_text_residual_retrieval_evidence_hardening"
V5_3_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_3_"
    "pdf_text_residual_retrieval_evidence_hardening_nonprod"
)
V5_3_STATUS = "V5_3_PDF_TEXT_RESIDUAL_RETRIEVAL_EVIDENCE_HARDENING_DIAGNOSTIC_NONPROD_READY"
V5_4_SHORT_KEY = "v5_4"
V5_4_SHORT_RUN_ID = "v5_4_user_owned_official_eval_approval_packet"
V5_4_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_4_"
    "user_owned_official_eval_approval_packet_nonprod"
)
V5_4_STATUS = "V5_4_USER_OWNED_OFFICIAL_EVAL_APPROVAL_PACKET_NONPROD_READY"
V5_5_SHORT_KEY = "v5_5"
V5_5_SHORT_RUN_ID = "v5_5_user_approved_gold_packet_ingestion_and_official_metric_dry_run"
V5_5_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_5_"
    "user_approved_gold_packet_ingestion_and_official_metric_dry_run_nonprod"
)
V5_5_STATUS = "V5_5_USER_APPROVED_GOLD_PACKET_INGESTION_AND_OFFICIAL_METRIC_DRY_RUN_NONPROD_READY"
V5_6_SHORT_KEY = "v5_6"
V5_6_SHORT_RUN_ID = "v5_6_official_metric_scored_execution_and_failure_attribution_nonprod"
V5_6_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_6_"
    "official_metric_scored_execution_and_failure_attribution_nonprod"
)
V5_6_STATUS = "V5_6_OFFICIAL_METRIC_SCORED_EXECUTION_BACKEND_UNAVAILABLE_FAIL_CLOSED_NONPROD_READY"
V5_6_2_SHORT_KEY = "v5_6_2"
V5_6_2_SHORT_RUN_ID = "v5_6_2_official_metric_backend_enabled_preflight_scored_rerun_nonprod"
V5_6_2_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v5_6_2_"
    "official_metric_backend_enabled_preflight_scored_rerun_nonprod"
)
V5_6_2_STATUS = "V5_6_2_OFFICIAL_METRIC_BACKEND_ENABLED_PREFLIGHT_FAIL_CLOSED_NONPROD_READY"
V5_6_2_SCORED_STATUS = "V5_6_2_OFFICIAL_METRIC_BACKEND_ENABLED_PREFLIGHT_SCORED_RERUN_NONPROD_READY"


class ReportResolutionError(RuntimeError):
    """Raised when a diagnostic report alias cannot be resolved safely."""


@dataclass(frozen=True)
class RunMetadata:
    logical_key: str
    short_run_id: str
    canonical_long_run_id: str
    status: str
    short_report_path: Path
    legacy_report_path: Path | None = None
    accepted_aliases: tuple[str, ...] = ()
    canonical_fields: tuple[str, ...] = ("run_id",)
    accepted_statuses: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedRun:
    logical_key: str
    short_run_id: str
    canonical_long_run_id: str
    status: str
    report_path: Path
    legacy_long_path_supported: bool

    @property
    def compatibility_alias(self) -> bool:
        return self.legacy_long_path_supported


RUNS: dict[str, RunMetadata] = {
    "v4_7_preofficial": RunMetadata(
        logical_key="v4_7_preofficial",
        short_run_id="v4_7_preofficial",
        canonical_long_run_id=V4_7_PREOFFICIAL_LONG_RUN_ID,
        status=V4_7_PREOFFICIAL_STATUS,
        short_report_path=REPORT_ROOT / "runs" / "v4_7_preofficial" / "report.json",
        legacy_report_path=REPORT_ROOT / "quality" / V4_7_PREOFFICIAL_LONG_RUN_ID / "report.json",
        accepted_aliases=(V4_7_PREOFFICIAL_LONG_RUN_ID,),
    ),
    "v4_7_2": RunMetadata(
        logical_key="v4_7_2",
        short_run_id="v4_7_2",
        canonical_long_run_id=V4_7_2_LONG_RUN_ID,
        status=V4_7_2_STATUS,
        short_report_path=REPORT_ROOT / "runs" / "v4_7_2" / "report.json",
        legacy_report_path=REPORT_ROOT / "quality" / V4_7_2_LONG_RUN_ID / "report.json",
        accepted_aliases=(V4_7_2_LONG_RUN_ID,),
    ),
    "v4_7_3": RunMetadata(
        logical_key="v4_7_3",
        short_run_id="v4_7_3",
        canonical_long_run_id=V4_7_3_LONG_RUN_ID,
        status=V4_7_3_STATUS,
        short_report_path=REPORT_ROOT / "runs" / "v4_7_3" / "report.json",
        legacy_report_path=REPORT_ROOT / "quality" / V4_7_3_LONG_RUN_ID / "report.json",
        accepted_aliases=(V4_7_3_LONG_RUN_ID,),
    ),
    "v4_7_4": RunMetadata(
        logical_key="v4_7_4",
        short_run_id="v4_7_4",
        canonical_long_run_id=V4_7_4_LONG_RUN_ID,
        status=V4_7_4_STATUS,
        short_report_path=REPORT_ROOT / "runs" / "v4_7_4" / "report.json",
        legacy_report_path=REPORT_ROOT / "quality" / V4_7_4_LONG_RUN_ID / "report.json",
        accepted_aliases=(V4_7_4_LONG_RUN_ID, "v4_7_4_pdf_survivor_replay"),
    ),
    V4_7_5_SHORT_KEY: RunMetadata(
        logical_key=V4_7_5_SHORT_KEY,
        short_run_id=V4_7_5_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_5_LONG_RUN_ID,
        status=V4_7_5_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_5_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_5_SHORT_RUN_ID, V4_7_5_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_6_SHORT_KEY: RunMetadata(
        logical_key=V4_7_6_SHORT_KEY,
        short_run_id=V4_7_6_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_6_LONG_RUN_ID,
        status=V4_7_6_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_6_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_6_SHORT_RUN_ID, V4_7_6_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_7_SHORT_KEY: RunMetadata(
        logical_key=V4_7_7_SHORT_KEY,
        short_run_id=V4_7_7_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_7_LONG_RUN_ID,
        status=V4_7_7_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_7_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_7_SHORT_RUN_ID, V4_7_7_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_8_SHORT_KEY: RunMetadata(
        logical_key=V4_7_8_SHORT_KEY,
        short_run_id=V4_7_8_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_8_LONG_RUN_ID,
        status=V4_7_8_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_8_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_8_SHORT_RUN_ID, V4_7_8_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_9_SHORT_KEY: RunMetadata(
        logical_key=V4_7_9_SHORT_KEY,
        short_run_id=V4_7_9_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_9_LONG_RUN_ID,
        status=V4_7_9_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_9_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_9_SHORT_RUN_ID, V4_7_9_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_10_SHORT_KEY: RunMetadata(
        logical_key=V4_7_10_SHORT_KEY,
        short_run_id=V4_7_10_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_10_LONG_RUN_ID,
        status=V4_7_10_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_10_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_10_SHORT_RUN_ID, V4_7_10_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_11_SHORT_KEY: RunMetadata(
        logical_key=V4_7_11_SHORT_KEY,
        short_run_id=V4_7_11_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_11_LONG_RUN_ID,
        status=V4_7_11_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_11_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_11_SHORT_RUN_ID, V4_7_11_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_12_SHORT_KEY: RunMetadata(
        logical_key=V4_7_12_SHORT_KEY,
        short_run_id=V4_7_12_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_12_LONG_RUN_ID,
        status=V4_7_12_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_12_SHORT_KEY / "report.json",
        accepted_aliases=(
            V4_7_12_SHORT_RUN_ID,
            V4_7_12_LONG_RUN_ID,
            "v4_7_12_answer_policy_calibration_and_silver_manifest_reconnect",
        ),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_13_SHORT_KEY: RunMetadata(
        logical_key=V4_7_13_SHORT_KEY,
        short_run_id=V4_7_13_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_13_LONG_RUN_ID,
        status=V4_7_13_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_13_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_13_SHORT_RUN_ID, V4_7_13_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_14_SHORT_KEY: RunMetadata(
        logical_key=V4_7_14_SHORT_KEY,
        short_run_id=V4_7_14_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_14_LONG_RUN_ID,
        status=V4_7_14_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_14_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_14_SHORT_RUN_ID, V4_7_14_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_15_SHORT_KEY: RunMetadata(
        logical_key=V4_7_15_SHORT_KEY,
        short_run_id=V4_7_15_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_15_LONG_RUN_ID,
        status=V4_7_15_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_15_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_15_SHORT_RUN_ID, V4_7_15_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_16_SHORT_KEY: RunMetadata(
        logical_key=V4_7_16_SHORT_KEY,
        short_run_id=V4_7_16_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_16_LONG_RUN_ID,
        status=V4_7_16_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_16_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_16_SHORT_RUN_ID, V4_7_16_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_17_SHORT_KEY: RunMetadata(
        logical_key=V4_7_17_SHORT_KEY,
        short_run_id=V4_7_17_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_17_LONG_RUN_ID,
        status=V4_7_17_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_17_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_17_SHORT_RUN_ID, V4_7_17_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_18_SHORT_KEY: RunMetadata(
        logical_key=V4_7_18_SHORT_KEY,
        short_run_id=V4_7_18_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_18_LONG_RUN_ID,
        status=V4_7_18_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_18_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_18_SHORT_RUN_ID, V4_7_18_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V5_0_SHORT_KEY: RunMetadata(
        logical_key=V5_0_SHORT_KEY,
        short_run_id=V5_0_SHORT_RUN_ID,
        canonical_long_run_id=V5_0_LONG_RUN_ID,
        status=V5_0_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V5_0_SHORT_KEY / "report.json",
        accepted_aliases=(V5_0_SHORT_RUN_ID, V5_0_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V5_1_SHORT_KEY: RunMetadata(
        logical_key=V5_1_SHORT_KEY,
        short_run_id=V5_1_SHORT_RUN_ID,
        canonical_long_run_id=V5_1_LONG_RUN_ID,
        status=V5_1_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V5_1_SHORT_KEY / "report.json",
        accepted_aliases=(V5_1_SHORT_RUN_ID, V5_1_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V5_2_SHORT_KEY: RunMetadata(
        logical_key=V5_2_SHORT_KEY,
        short_run_id=V5_2_SHORT_RUN_ID,
        canonical_long_run_id=V5_2_LONG_RUN_ID,
        status=V5_2_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V5_2_SHORT_KEY / "report.json",
        accepted_aliases=(V5_2_SHORT_RUN_ID, V5_2_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V5_3_SHORT_KEY: RunMetadata(
        logical_key=V5_3_SHORT_KEY,
        short_run_id=V5_3_SHORT_RUN_ID,
        canonical_long_run_id=V5_3_LONG_RUN_ID,
        status=V5_3_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V5_3_SHORT_KEY / "report.json",
        accepted_aliases=(V5_3_SHORT_RUN_ID, V5_3_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V5_4_SHORT_KEY: RunMetadata(
        logical_key=V5_4_SHORT_KEY,
        short_run_id=V5_4_SHORT_RUN_ID,
        canonical_long_run_id=V5_4_LONG_RUN_ID,
        status=V5_4_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V5_4_SHORT_KEY / "report.json",
        accepted_aliases=(V5_4_SHORT_RUN_ID, V5_4_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V5_5_SHORT_KEY: RunMetadata(
        logical_key=V5_5_SHORT_KEY,
        short_run_id=V5_5_SHORT_RUN_ID,
        canonical_long_run_id=V5_5_LONG_RUN_ID,
        status=V5_5_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V5_5_SHORT_KEY / "report.json",
        accepted_aliases=(V5_5_SHORT_RUN_ID, V5_5_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V5_6_SHORT_KEY: RunMetadata(
        logical_key=V5_6_SHORT_KEY,
        short_run_id=V5_6_SHORT_RUN_ID,
        canonical_long_run_id=V5_6_LONG_RUN_ID,
        status=V5_6_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V5_6_SHORT_KEY / "report.json",
        accepted_aliases=(V5_6_SHORT_RUN_ID, V5_6_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V5_6_2_SHORT_KEY: RunMetadata(
        logical_key=V5_6_2_SHORT_KEY,
        short_run_id=V5_6_2_SHORT_RUN_ID,
        canonical_long_run_id=V5_6_2_LONG_RUN_ID,
        status=V5_6_2_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V5_6_2_SHORT_KEY / "report.json",
        accepted_aliases=(V5_6_2_SHORT_RUN_ID, V5_6_2_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
        accepted_statuses=(V5_6_2_SCORED_STATUS,),
    ),
}

ALIAS_TO_KEY: dict[str, str] = {
    alias: key
    for key, metadata in RUNS.items()
    for alias in (key, *metadata.accepted_aliases)
}
ALIAS_TO_KEY["current"] = V5_6_SHORT_KEY


def _repo_root(root: Path | str | None = None) -> Path:
    return Path.cwd() if root is None else Path(root)


def _normalize_key(key: str) -> str:
    normalized = key.strip()
    try:
        return ALIAS_TO_KEY[normalized]
    except KeyError as exc:
        raise ReportResolutionError(f"unknown RAG eval run key: {key}") from exc


def resolve_run(key: str, *, root: Path | str | None = None) -> ResolvedRun:
    normalized = _normalize_key(key)
    metadata = RUNS[normalized]
    repo_root = _repo_root(root)
    return ResolvedRun(
        logical_key=metadata.logical_key,
        short_run_id=metadata.short_run_id,
        canonical_long_run_id=metadata.canonical_long_run_id,
        status=metadata.status,
        report_path=repo_root / metadata.short_report_path,
        legacy_long_path_supported=metadata.legacy_report_path is not None,
    )


def legacy_report_path(key: str, *, root: Path | str | None = None) -> Path | None:
    metadata = RUNS[_normalize_key(key)]
    if metadata.legacy_report_path is None:
        return None
    return _repo_root(root) / metadata.legacy_report_path


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_report(
    key: str,
    *,
    root: Path | str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    resolved = resolve_run(key, root=root)
    if not resolved.report_path.exists():
        raise ReportResolutionError(f"missing report for {resolved.logical_key}: {resolved.report_path}")
    actual_sha256 = sha256_file(resolved.report_path)
    if expected_sha256 and expected_sha256 != actual_sha256:
        raise ReportResolutionError(
            f"report sha256 mismatch for {resolved.logical_key}: expected {expected_sha256}, got {actual_sha256}"
        )
    try:
        report = json.loads(resolved.report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReportResolutionError(f"invalid JSON report for {resolved.logical_key}") from exc
    _validate_identity(resolved, report)
    return report


def _validate_identity(resolved: ResolvedRun, report: dict[str, Any]) -> None:
    metadata = RUNS[resolved.logical_key]
    if "run_id" in metadata.canonical_fields:
        if report.get("run_id") != metadata.canonical_long_run_id:
            raise ReportResolutionError(f"{resolved.logical_key} report run id mismatch")
    if "short_run_id" in metadata.canonical_fields:
        if report.get("short_run_id") != metadata.short_run_id:
            raise ReportResolutionError(f"{resolved.logical_key} report short_run_id mismatch")
    if "canonical_long_run_id" in metadata.canonical_fields:
        if report.get("canonical_long_run_id") != metadata.canonical_long_run_id:
            raise ReportResolutionError(f"{resolved.logical_key} report canonical_long_run_id mismatch")
    if report.get("status") != metadata.status and report.get("status") not in metadata.accepted_statuses:
        raise ReportResolutionError(f"{resolved.logical_key} report status mismatch")
