from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai.eval.harness import rag_diagnostic_common as diagnostic_common


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
REPORT_ARCHIVE_DIR = REPORT_DIR / "_archive" / "legacy"


def require_v3_7_2_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not artifact_exists(path)]
    if not missing:
        return
    message = "missing v3_7_2 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_7_2_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v3_8_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not artifact_exists(path)]
    if not missing:
        return
    message = "missing v3_8 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_8_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v3_8_1_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not artifact_exists(path)]
    if not missing:
        return
    message = "missing v3_8_1 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_8_1_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v3_8_2_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not artifact_exists(path)]
    if not missing:
        return
    message = "missing v3_8_2 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_8_2_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v3_8_3_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not artifact_exists(path)]
    if not missing:
        return
    message = "missing v3_8_3 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_8_3_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v3_9_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not artifact_exists(path)]
    if not missing:
        return
    message = "missing v3_9 local report artifacts: " + ", ".join(str(path) for path in missing)
    if os.environ.get("RAG_V3_9_ARTIFACTS_REQUIRED") == "1":
        pytest.fail(message)
    pytest.skip(message)


def require_v4_3_local_artifacts(*paths: Path) -> None:
    missing = [path for path in paths if not artifact_exists(path)]
    if not missing:
        return
    pytest.fail("missing v4_3 local report artifacts: " + ", ".join(str(path) for path in missing))


def windows_long_path(path: Path) -> Path:
    if sys.platform != "win32":
        return path
    path_text = str(path)
    if path_text.startswith("\\\\?\\"):
        return path
    if path.is_absolute():
        return Path("\\\\?\\" + path_text)
    return path


EXTERNAL_REPORT_ARCHIVE_DIR = windows_long_path(Path(
    "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
    "rag-ingestion/repo-wide-cleanup-20260519/reports/rag-ingestion-legacy"
))
PRIMARY_EXTERNAL_REPORT_ARCHIVE_DIR = windows_long_path(Path(
    "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
    "rag-ingestion/repo-wide-cleanup-20260521/reports/rag-ingestion-legacy"
))
EXTERNAL_REPORT_ARCHIVE_DIRS = (
    PRIMARY_EXTERNAL_REPORT_ARCHIVE_DIR,
    EXTERNAL_REPORT_ARCHIVE_DIR,
)
STRICT_PROTECTED_PATHS = (
    "ai/eval/eval_queries/gold_queries_pdf_question_gold_v2.csv",
    "ai/eval/eval_queries/gold_queries_xlsx_question_gold_v2.csv",
    "ai/eval/reports/rag-ingestion/baseline_v1.json",
    "ai/eval/reports/rag-ingestion/scorer_v1.jsonl",
    "ai/eval/reports/rag-ingestion/metric_input_v1.json",
    "ai/eval/reports/rag-ingestion/smoke_v1.json",
    "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
    "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
)
V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS = (
    "ai/eval/eval_queries/official_denominator_registry.json",
    "ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv",
)
V3_1_9_SUMMARY = (
    ROOT
    / "ai"
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement_summary.json"
)
V3_2_3_SUMMARY = (
    ROOT
    / "ai"
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "official_answer_citation_agentic_loop_run_v3_2_3_queue_lane_actionability_reconciliation_summary.json"
)
V3_2_4_SUMMARY = (
    ROOT
    / "ai"
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "official_answer_citation_agentic_loop_run_v3_2_4_gq_auto_010_pdf_context_provenance_diagnostic_summary.json"
)
V3_2_5_SUMMARY = (
    ROOT
    / "ai"
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "official_answer_citation_agentic_loop_run_v3_2_5_gq_auto_010_pdf_context_reconciliation_fix_summary.json"
)
V3_2_6_SUMMARY = (
    ROOT
    / "ai"
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "official_answer_citation_agentic_loop_run_v3_2_6_text_prompt_span_rule_remeasurement_summary.json"
)
STATUS_JSONL = REPORT_DIR / "status.jsonl"


def resolve_report_artifact_path(path: Path) -> Path:
    return diagnostic_common.resolve_report_artifact_path(path)


def artifact_exists(path: Path) -> bool:
    return diagnostic_common.artifact_exists(path)


def read_json(path: Path) -> dict[str, object]:
    return json.loads(resolve_report_artifact_path(path).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(resolve_report_artifact_path(path).read_bytes()).hexdigest()


def test_residual_audit_does_not_mutate_protected_artifacts():
    for protected_path in STRICT_PROTECTED_PATHS:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )

        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path


def test_v3_1_9_policy_application_allows_only_gold_policy_surfaces():
    summary = read_json(V3_1_9_SUMMARY)
    changed_paths = set()
    for flag in ([], ["--cached"]):
        result = subprocess.run(
            ["git", "diff", *flag, "--name-only", "--", *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        changed_paths.update(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())

    assert changed_paths <= set(V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS)
    assert summary["run_class"] == "user_approved_gold_policy_override_application"
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["expected_answer_mutation"] is True
    assert summary["supporting_evidence_mutation"] is True
    assert summary["gold_policy_mutation"] is True
    assert summary["behavior_change_made"] is False
    assert summary["renderer_mutation"] is False
    assert summary["scorer_behavior_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["production_mutation"] is False


def test_v3_2_3_no_behavior_diagnostic_does_not_mutate_gold_denominator_or_runtime_artifacts():
    summary = read_json(V3_2_3_SUMMARY)
    protected_paths = (*STRICT_PROTECTED_PATHS, *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS)

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )

        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    assert summary["run_class"] == "classification_only_queue_lane_actionability_reconciliation"
    assert summary["behavior_change_made"] is False
    assert summary["implementation_change_made"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["relevance_label_mutation"] is False
    assert summary["answerability_label_mutation"] is False
    assert summary["denominator_mutation"] is False
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["scorer_behavior_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["production_mutation"] is False


def test_v3_2_4_pdf_context_provenance_diagnostic_does_not_mutate_gold_denominator_or_runtime_artifacts():
    summary = read_json(V3_2_4_SUMMARY)
    protected_paths = (*STRICT_PROTECTED_PATHS, *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS)

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )

        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    assert summary["run_class"] == "classification_only_pdf_context_provenance_diagnostic"
    assert summary["classification"] == "open_because_v3_1_6_expansion_not_wired_into_v3_2_measurement"
    assert summary["v3_2_5_implementation_needed"] is True
    assert summary["v3_2_5_implementation_surface"] == "measurement_source_selection_and_context_assembly_overlay"
    assert summary["index_or_export_rebuild_required"] is False
    assert summary["behavior_change_made"] is False
    assert summary["implementation_change_made"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["relevance_label_mutation"] is False
    assert summary["answerability_label_mutation"] is False
    assert summary["denominator_mutation"] is False
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["scorer_behavior_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["index_or_export_rebuild_performed"] is False


def test_v3_2_5_pdf_context_reconciliation_does_not_mutate_gold_denominator_or_runtime_artifacts():
    summary = read_json(V3_2_5_SUMMARY)
    protected_paths = (*STRICT_PROTECTED_PATHS, *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS)

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )

        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    assert summary["run_class"] == "implementation_safe_pdf_context_reconciliation_full_remeasurement"
    assert summary["behavior_change_made"] is True
    assert summary["implementation_change_made"] is True
    assert summary["prompt_context_behavior_change"] is True
    assert summary["implementation_change_scope"] == (
        "gq_auto_010_pdf_context_reconciliation_existing_v3_1_6_expansion_overlay"
    )
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["relevance_label_mutation"] is False
    assert summary["answerability_label_mutation"] is False
    assert summary["denominator_mutation"] is False
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["scorer_behavior_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["index_or_export_rebuild_required"] is False
    assert summary["index_or_export_rebuild_performed"] is False
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["lane_score_collapsed"] is False


def test_v3_2_6_text_prompt_span_rule_does_not_mutate_gold_denominator_or_runtime_artifacts():
    summary = read_json(V3_2_6_SUMMARY)
    protected_paths = (*STRICT_PROTECTED_PATHS, *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS)

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )

        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    assert summary["run_class"] == "implementation_safe_text_prompt_span_rule_full_remeasurement"
    assert summary["behavior_change_made"] is True
    assert summary["implementation_change_made"] is True
    assert summary["prompt_context_behavior_change"] is True
    assert summary["implementation_change_scope"] == (
        "target_scoped_text_prompt_span_rule_for_narrow_factual_answer_selection"
    )
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["relevance_label_mutation"] is False
    assert summary["answerability_label_mutation"] is False
    assert summary["denominator_mutation"] is False
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["scorer_behavior_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["index_or_export_rebuild_required"] is False
    assert summary["index_or_export_rebuild_performed"] is False
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["lane_score_collapsed"] is False


def test_v3_2_7_closure_does_not_mutate_gold_denominator_or_runtime_artifacts():
    run_id = "official_answer_citation_agentic_loop_run_v3_2_7_post_fix_closure_and_rolling_report_cleanup"
    event = next(
        item
        for item in reversed([json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines()])
        if item.get("event_type") == "official_answer_citation_agentic_loop_v3_2_7_post_fix_closure"
        and item.get("run_id") == run_id
    )
    protected_paths = (*STRICT_PROTECTED_PATHS, *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS)

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )

        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    assert event["run_class"] == "status_ledger_only_closure_and_rolling_report_cleanup"
    assert event["guardrails"]["behavior_change_made_in_v3_2_7"] is False
    assert event["guardrails"]["implementation_change_made_in_v3_2_7"] is False
    assert event["guardrails"]["prompt_context_behavior_change"] is False
    assert event["guardrails"]["gold_mutation"] is False
    assert event["guardrails"]["expected_answer_mutation"] is False
    assert event["guardrails"]["supporting_evidence_mutation"] is False
    assert event["guardrails"]["relevance_label_mutation"] is False
    assert event["guardrails"]["answerability_label_mutation"] is False
    assert event["guardrails"]["denominator_mutation"] is False
    assert event["guardrails"]["official_denominator_query_id_set_mutation"] is False
    assert event["guardrails"]["renderer_mutation"] is False
    assert event["guardrails"]["scorer_behavior_mutation"] is False
    assert event["guardrails"]["retrieval_mutation"] is False
    assert event["guardrails"]["production_mutation"] is False
    assert event["guardrails"]["index_or_export_rebuild_performed"] is False
    assert event["guardrails"]["promotion_evidence"] is False
    assert event["guardrails"]["official_retrieval_metrics_computed"] is False
    assert event["guardrails"]["lane_score_collapsed"] is False


def test_v3_3_0_source_of_truth_audit_does_not_mutate_gold_denominator_or_runtime_artifacts():
    run_id = "official_answer_citation_agentic_loop_run_v3_3_0_post_closure_hardening_source_of_truth_audit"
    event = next(
        item
        for item in reversed([json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines()])
        if item.get("event_type") == "official_answer_citation_agentic_loop_v3_3_0_source_of_truth_audit"
        and item.get("run_id") == run_id
    )
    protected_paths = (*STRICT_PROTECTED_PATHS, *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS)

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )

        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    assert event["run_class"] == "status_ledger_only_source_of_truth_audit"
    assert event["diagnostic_only"] is True
    assert event["promotion_evidence"] is False
    assert event["guardrails"]["behavior_change_made_in_v3_3_0"] is False
    assert event["guardrails"]["implementation_change_made_in_v3_3_0"] is False
    assert event["guardrails"]["gold_mutation"] is False
    assert event["guardrails"]["expected_answer_mutation"] is False
    assert event["guardrails"]["supporting_evidence_mutation"] is False
    assert event["guardrails"]["relevance_label_mutation"] is False
    assert event["guardrails"]["answerability_label_mutation"] is False
    assert event["guardrails"]["denominator_mutation"] is False
    assert event["guardrails"]["official_denominator_query_id_set_mutation"] is False
    assert event["guardrails"]["prompt_context_behavior_change"] is False
    assert event["guardrails"]["renderer_mutation"] is False
    assert event["guardrails"]["scorer_behavior_mutation"] is False
    assert event["guardrails"]["retrieval_mutation"] is False
    assert event["guardrails"]["production_mutation"] is False
    assert event["guardrails"]["silver_mutation"] is False
    assert event["guardrails"]["index_or_export_rebuild_performed"] is False
    assert event["guardrails"]["promotion_evidence"] is False
    assert event["guardrails"]["official_retrieval_metrics_computed"] is False
    assert event["guardrails"]["official_ndcg_computed"] is False
    assert event["guardrails"]["official_mrr_computed"] is False
    assert event["guardrails"]["official_hit_at_k_computed"] is False
    assert event["guardrails"]["lane_score_collapsed"] is False


def test_v3_4_4_readme_artifacts_do_not_mutate_protected_surfaces_or_silver_rows():
    run_id = "official_answer_citation_agentic_loop_run_v3_4_4_readme_retrieval_smoke_and_silver_readiness_artifacts"
    event = next(
        item
        for item in reversed([json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines()])
        if item.get("event_type") == "readme_retrieval_smoke_and_silver_readiness_artifacts_v3_4_4"
        and item.get("run_id") == run_id
    )
    protected_paths = (*STRICT_PROTECTED_PATHS, *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS)

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )

        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()

    assert event["run_class"] == "readme_ready_artifacts_and_silver_readiness_boundary"
    assert event["readme_directly_updated"] is False
    assert event["pending_manual_integration"] is True
    assert event["silver_generation_blocked"] is True
    assert event["silver_mutation"] is False
    assert event["official_denominator_source_bound_overlap_excluded_from_silver"] is True
    assert event["candidate_artifacts_used_as_generation_source"] is False
    assert event["guardrails"]["gold_mutation"] is False
    assert event["guardrails"]["expected_answer_mutation"] is False
    assert event["guardrails"]["supporting_evidence_mutation"] is False
    assert event["guardrails"]["answer_citation_denominator_mutation"] is False
    assert event["guardrails"]["official_denominator_query_id_set_mutation"] is False
    assert event["guardrails"]["prompt_mutation"] is False
    assert event["guardrails"]["retrieval_mutation"] is False
    assert event["guardrails"]["scorer_mutation"] is False
    assert event["guardrails"]["renderer_mutation"] is False
    assert event["guardrails"]["index_or_export_mutation"] is False
    assert event["guardrails"]["production_mutation"] is False
    assert event["guardrails"]["silver_mutation"] is False
    assert event["guardrails"]["silver_generation_from_official_denominator_rows"] is False
    assert event["guardrails"]["lane_a_b_c_collapsed_score"] is False
    assert event["guardrails"]["graded_ndcg"] is False
    assert event["guardrails"]["threshold_tuning"] is False
    assert event["guardrails"]["winner_selection"] is False


def test_v3_5_0_capacity_expansion_does_not_mutate_protected_surfaces_or_silver_rows():
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_5_0_"
        "strict_non_official_source_bound_capacity_expansion"
    )
    summary_path = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / f"{run_id}_capacity_summary.json"
    event = next(
        item
        for item in reversed([json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines()])
        if item.get("event_type") == "strict_non_official_source_bound_capacity_expansion_v3_5_0"
        and item.get("run_id") == run_id
    )
    summary = read_json(summary_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )

        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()

    assert event["run_class"] == "source_capacity_inventory_only_no_silver_generation"
    assert event["triage_doc_updated"] is False
    assert event["pilot_threshold_met"] is True
    assert event["target_threshold_met"] is False
    assert event["silver_generation_allowed"] is False
    assert event["silver_jsonl_rows_created"] is False
    assert event["candidate_artifacts_used_as_generation_source"] is False
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["official_denominator_rows_reused"] is False
    assert summary["official_29_query_ids_copied_or_relabelled"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    for key in (
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "relevance_label_mutation",
        "answerability_label_mutation",
        "answer_citation_denominator_mutation",
        "official_denominator_query_id_set_mutation",
        "prompt_mutation",
        "retrieval_mutation",
        "scorer_mutation",
        "renderer_mutation",
        "index_or_export_mutation",
        "production_mutation",
        "silver_mutation",
        "silver_generation_from_official_denominator_rows",
        "candidate_artifacts_as_generation_source",
        "lane_a_b_c_collapsed_score",
        "graded_ndcg",
        "threshold_tuning",
        "winner_selection",
        "promotion_evidence",
        "readme_headline_product_performance_claim",
        "representative_product_performance_claim",
    ):
        assert event["guardrails"][key] is False, key


def test_v3_5_1_to_v3_5_3_source_material_phases_do_not_mutate_protected_surfaces_or_silver_rows():
    run_ids = {
        "official_answer_citation_agentic_loop_run_v3_5_1_pilot_silver_source_manifest_freeze": (
            "pilot_silver_source_manifest_freeze_v3_5_1",
            ROOT
            / "ai"
            / "eval"
            / "reports"
            / "rag-ingestion"
            / "official_answer_citation_agentic_loop_run_v3_5_1_pilot_silver_source_manifest_freeze_freeze_summary.json",
        ),
        (
            "official_answer_citation_agentic_loop_run_v3_5_2_"
            "xlsx_source_value_manifest_repair_and_acquisition"
        ): (
            "xlsx_source_value_manifest_repair_and_acquisition_v3_5_2",
            ROOT
            / "ai"
            / "eval"
            / "reports"
            / "rag-ingestion"
            / (
                "official_answer_citation_agentic_loop_run_v3_5_2_"
                "xlsx_source_value_manifest_repair_and_acquisition_post_xlsx_capacity_summary.json"
            ),
        ),
        (
            "official_answer_citation_agentic_loop_run_v3_5_3_"
            "pdf_page_bbox_source_text_manifest_repair_and_acquisition"
        ): (
            "pdf_page_bbox_source_text_manifest_repair_and_acquisition_v3_5_3",
            ROOT
            / "ai"
            / "eval"
            / "reports"
            / "rag-ingestion"
            / (
                "official_answer_citation_agentic_loop_run_v3_5_3_"
                "pdf_page_bbox_source_text_manifest_repair_and_acquisition_post_pdf_capacity_summary.json"
            ),
        ),
    }
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()

    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    for run_id, (event_type, summary_path) in run_ids.items():
        event = next(
            item
            for item in reversed(events)
            if item.get("event_type") == event_type and item.get("run_id") == run_id
        )
        summary = read_json(summary_path)
        assert event["triage_doc_updated"] is False
        assert event["silver_generation_allowed"] is False
        assert event["silver_jsonl_rows_created"] is False
        assert event["candidate_artifacts_used_as_generation_source"] is False
        assert summary["silver_generation_allowed"] is False
        assert summary["silver_jsonl_rows_created"] is False
        assert summary["official_denominator_rows_reused"] is False
        assert summary["official_29_query_ids_copied_or_relabelled"] is False
        assert summary["candidate_artifacts_used_as_generation_source"] is False
        for key in (
            "gold_mutation",
            "expected_answer_mutation",
            "supporting_evidence_mutation",
            "relevance_label_mutation",
            "answerability_label_mutation",
            "answer_citation_denominator_mutation",
            "official_denominator_query_id_set_mutation",
            "prompt_mutation",
            "retrieval_mutation",
            "scorer_mutation",
            "renderer_mutation",
            "index_or_export_mutation",
            "production_mutation",
            "silver_mutation",
            "silver_generation_from_official_denominator_rows",
            "candidate_artifacts_as_generation_source",
            "lane_a_b_c_collapsed_score",
            "graded_ndcg",
            "threshold_tuning",
            "winner_selection",
            "promotion_evidence",
            "readme_headline_product_performance_claim",
            "representative_product_performance_claim",
        ):
            assert event["guardrails"][key] is False, key


def test_v3_5_4_balanced_freeze_does_not_mutate_protected_surfaces_or_silver_rows():
    run_id = "official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze"
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_freeze_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()

    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    event = next(
        item
        for item in reversed(events)
        if item.get("event_type") == "balanced_silver_source_manifest_freeze_v3_5_4"
        and item.get("run_id") == run_id
    )
    summary = read_json(summary_path)
    assert event["triage_doc_updated"] is False
    assert event["silver_generation_allowed"] is False
    assert event["silver_jsonl_rows_created"] is False
    assert event["candidate_artifacts_used_as_generation_source"] is False
    assert summary["silver_generation_allowed"] is False
    assert summary["silver_jsonl_rows_created"] is False
    assert summary["official_denominator_rows_reused"] is False
    assert summary["official_29_query_ids_copied_or_relabelled"] is False
    assert summary["candidate_artifacts_used_as_generation_source"] is False
    for key in (
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "relevance_label_mutation",
        "answerability_label_mutation",
        "answer_citation_denominator_mutation",
        "official_denominator_query_id_set_mutation",
        "prompt_mutation",
        "retrieval_mutation",
        "scorer_mutation",
        "renderer_mutation",
        "index_or_export_mutation",
        "production_mutation",
        "silver_mutation",
        "silver_generation_from_official_denominator_rows",
        "candidate_artifacts_as_generation_source",
        "lane_a_b_c_collapsed_score",
        "graded_ndcg",
        "threshold_tuning",
        "winner_selection",
        "promotion_evidence",
        "readme_headline_product_performance_claim",
        "representative_product_performance_claim",
    ):
        assert event["guardrails"][key] is False, key


def test_v3_5_5_quality_audit_does_not_mutate_v3_5_4_protected_surfaces_or_silver_rows():
    run_id = "official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit"
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_quality_summary.json"
    )
    v3_5_4_manifest = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / "official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_balanced_source_manifest.jsonl"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_balanced_source_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_freeze_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_freeze_audit.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_audit_sample_packet.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_next_phase_policy_boundary.json",
    )
    summary = read_json(summary_path)

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    assert summary["input_manifest_sha256_before"] == sha256_file(v3_5_4_manifest)
    assert summary["input_manifest_sha256_after"] == summary["input_manifest_sha256_before"]
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()

    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    event = next(
        item
        for item in reversed(events)
        if item.get("event_type") == "balanced_source_manifest_quality_audit_v3_5_5"
        and item.get("run_id") == run_id
    )
    for payload in (summary, event):
        assert payload["silver_generation_allowed"] is False
        assert payload["silver_jsonl_rows_created"] is False
        assert payload["questions_created"] is False
        assert payload["expected_answers_created"] is False
        assert payload["supporting_evidence_created"] is False
        assert payload["relevance_labels_created"] is False
        assert payload["answerability_labels_created"] is False
        assert payload["qrels_created"] is False
        assert payload["candidate_artifacts_used_as_generation_source"] is False
    for key in (
        "gold_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "answerability_label_mutation",
        "official_denominator_query_id_set_mutation",
        "prompt_mutation",
        "retrieval_mutation",
        "renderer_mutation",
        "index_or_export_mutation",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
        "promotion_evidence",
        "readme_headline_product_performance_claim",
    ):
        assert event["guardrails"][key] is False, key


def test_v3_6_1_weak_noisy_candidate_generation_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = "official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation"
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_generation_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_balanced_source_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_freeze_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_freeze_audit.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_audit_sample_packet.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_next_phase_policy_boundary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_quality_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_manifest_validation.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_audit_sample_review_packet.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_duplicate_hash_audit.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_next_phase_policy_boundary.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["weak_silver_candidate_count"] == 1000
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_6_2_sanity_eval_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = "official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval"
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_candidate_sanity_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_balanced_source_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_freeze_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_quality_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_manifest_validation.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_audit_sample_review_packet.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_duplicate_hash_audit.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_5_balanced_source_manifest_quality_audit_next_phase_policy_boundary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_weak_silver_candidates.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_generation_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_generation_quality_distribution.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_split_manifest.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_policy_compliance_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_next_phase_recommendation.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["candidate_row_count"] == 1000
    assert summary["candidate_sanity_passed"] is True
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_6_3_manifest_freeze_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = "official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze"
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_diagnostic_weak_noisy_silver_manifest_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_weak_silver_candidates.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_generation_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_generation_quality_distribution.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_split_manifest.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_policy_compliance_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval_candidate_sanity_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval_candidate_sanity_per_row.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval_candidate_quarantine_rows.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval_candidate_metric_feasibility.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval_split_independence_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval_hash_contract_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_2_weak_noisy_silver_candidate_sanity_eval_next_phase_recommendation.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["manifest_freeze_passed"] is True
    assert summary["manifest_row_count"] == 1000
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_6_4_metric_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = "official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric"
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_all.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_core.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_review_only.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_quarantine.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_policy_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_next_phase_recommendation.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["diagnostic_row_count"] == 1000
    assert summary["core_manifest_row_count"] == 665
    assert summary["review_only_manifest_row_count"] == 335
    assert summary["quarantine_manifest_row_count"] == 0
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["generated_expected_answers_are_gold"] is False
    assert summary["official_metric"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_6_5_triage_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = "official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage"
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_all.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_core.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_review_only.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_quarantine.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_policy_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_next_phase_recommendation.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_per_row.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_aggregate_by_bucket.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_failure_taxonomy.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_sample_review.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_policy_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_next_phase_recommendation.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["protected_input_sha256_matches_v3_6_4_summary"] is True
    assert summary["protected_v3_6_3_input_sha256_before"] == summary["protected_v3_6_3_input_sha256_after"]
    assert summary["protected_v3_6_3_input_sha256_unchanged"] is True
    assert summary["local_llm_live_silver_generation_allowed"] is False
    assert summary["local_llm_live_silver_generation_attempted"] is False
    assert summary["local_llm_metric_scoring_allowed"] is False
    assert summary["local_llm_metric_scoring_attempted"] is False
    assert summary["external_llm_api_allowed"] is False
    assert summary["external_llm_api_attempted"] is False
    assert summary["db_write_allowed"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_allowed"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["db_index_rebuild_allowed"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["db_results_as_gold_allowed"] is False
    assert summary["db_results_as_official_qrels_allowed"] is False
    assert summary["db_results_as_generation_source_allowed"] is False
    assert summary["official_metric"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_6_6_sidecar_probe_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = "official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe"
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_weak_silver_candidates.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_all.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_core.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_review_only.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_quarantine.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_per_row.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage_per_row.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage_policy_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage_next_phase_recommendation.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["protected_v3_6_3_input_sha256_before"] == summary["protected_v3_6_3_input_sha256_after"]
    assert summary["protected_v3_6_3_input_sha256_unchanged"] is True
    assert summary["diagnostic_reference_sidecar_complete"] is True
    if "sidecar_mutates_v3_6_3_compact_manifest" in summary:
        assert summary["sidecar_mutates_v3_6_3_compact_manifest"] is False
    assert summary["generated_expected_answers_are_gold"] is False
    assert summary["local_llm_live_silver_generation_allowed"] is False
    assert summary["local_llm_live_silver_generation_attempted"] is False
    assert summary["local_llm_metric_scoring_allowed"] is False
    assert summary["local_llm_metric_scoring_attempted"] is False
    assert summary["external_llm_api_allowed"] is False
    assert summary["external_llm_api_attempted"] is False
    assert summary["db_write_allowed"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_allowed"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["db_index_rebuild_allowed"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["db_results_as_gold_allowed"] is False
    assert summary["db_results_as_official_qrels_allowed"] is False
    assert summary["db_results_as_generation_source_allowed"] is False
    assert summary["official_metric"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_6_7_runtime_stability_probe_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = "official_answer_citation_agentic_loop_run_v3_6_7_runtime_stability_probe_for_core_only"
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_weak_silver_candidates.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_all.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_core.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_review_only.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_quarantine.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_4_diagnostic_only_weak_noisy_silver_metric_per_row.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage_per_row.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage_policy_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_5_rough_failure_bucket_triage_next_phase_recommendation.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_reference_sidecar.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_core_smoke_sample.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_runtime_probe_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_db_retrieval_surface_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_policy_audit.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_next_phase_recommendation.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["protected_v3_6_3_input_sha256_before"] == summary["protected_v3_6_3_input_sha256_after"]
    assert summary["protected_v3_6_3_input_sha256_unchanged"] is True
    assert summary["runtime_probe_core_only"] is True
    assert summary["review_only_rows_attempted"] == 0
    assert summary["official_proximity_rows_attempted"] == 0
    assert summary["generated_expected_answers_are_gold"] is False
    assert summary["local_llm_live_silver_generation_allowed"] is False
    assert summary["local_llm_live_silver_generation_attempted"] is False
    assert summary["local_llm_metric_scoring_allowed"] is False
    assert summary["local_llm_metric_scoring_attempted"] is False
    assert summary["external_llm_api_allowed"] is False
    assert summary["external_llm_api_attempted"] is False
    assert summary["db_write_allowed"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_allowed"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["db_index_rebuild_allowed"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["db_results_as_gold_allowed"] is False
    assert summary["db_results_as_official_qrels_allowed"] is False
    assert summary["db_results_as_generation_source_allowed"] is False
    assert summary["official_metric"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["prompt_mutation"] is False
    assert summary["retrieval_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["renderer_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    measurements = (ROOT / "docs" / "rag-ingestion-measurements.md").read_text(encoding="utf-8")
    assert run_id not in measurements
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_6_8_nonprod_materialization_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_6_8_"
        "nonprod_all_source_index_materialization_and_canonical_payload_wiring"
    )
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_balanced_source_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_freeze_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_weak_silver_candidates.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_all.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_core.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_review_only.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_quarantine.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_reference_sidecar.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_7_runtime_stability_probe_for_core_only_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_7_runtime_stability_probe_for_core_only_runtime_attempts.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["protected_v3_6_3_input_sha256_before"] == summary["protected_v3_6_3_input_sha256_after"]
    assert summary["protected_v3_6_3_input_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["implementation_allowed"] is True
    assert summary["index_or_export_mutation"] is True
    assert summary["index_or_export_mutation_scope"] == "non_production_only"
    assert summary["index_path"] == "ai/eval/indexes/rag-data-all-source-nonprod-v1"
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_6_8_source_registry_architecture_audit_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_6_8_"
        "source_registry_first_evidence_bundle_architecture_audit"
    )
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/payload_contract_summary.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_balanced_source_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_freeze_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_weak_silver_candidates.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_all.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_reference_sidecar.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_8_nonprod_all_source_index_materialization_and_canonical_payload_wiring_summary.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["protected_v3_6_3_input_sha256_before"] == summary["protected_v3_6_3_input_sha256_after"]
    assert summary["protected_v3_6_3_input_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["all_source_nonprod_index_sha256_before"] == summary["all_source_nonprod_index_sha256_after"]
    assert summary["all_source_nonprod_index_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["implementation_allowed"] is True
    assert summary["implementation_scope"] == [
        "source_atom_schema_validation",
        "searchview_searchunit_role_audit",
        "evidence_bundle_schema_introduction",
        "track_specific_evidence_assembly_contract",
        "no_vector_citation_render_checks",
        "no_vector_evidence_hydration_checks",
        "soft_track_router_audit",
        "compact_diagnostics_and_tests",
    ]
    assert summary["index_or_export_mutation"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    assert summary["query_id_specific_evidence_patch"] is False
    assert summary["file_name_specific_evidence_patch"] is False
    assert summary["silver_expected_answer_used_as_generation_input"] is False
    assert summary["silver_evidence_locator_used_as_retrieval_shortcut"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_6_9_searchunit_searchview_sourceatom_refactor_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_6_9_"
        "searchunit_searchview_sourceatom_refactor"
    )
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/payload_contract_summary.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/faiss.index",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_balanced_source_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_5_4_balanced_silver_source_manifest_freeze_freeze_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_1_balanced_weak_noisy_silver_candidate_generation_weak_silver_candidates.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_3_diagnostic_weak_noisy_silver_manifest_freeze_diagnostic_weak_noisy_silver_manifest_all.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_6_diagnostic_reference_sidecar_and_runtime_surface_probe_reference_sidecar.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_6_8_source_registry_first_evidence_bundle_architecture_audit_summary.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["protected_v3_6_3_input_sha256_before"] == summary["protected_v3_6_3_input_sha256_after"]
    assert summary["protected_v3_6_3_input_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["all_source_nonprod_index_sha256_before"] == summary["all_source_nonprod_index_sha256_after"]
    assert summary["all_source_nonprod_index_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["implementation_allowed"] is True
    assert summary["index_or_export_mutation"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    assert summary["query_id_specific_evidence_patch"] is False
    assert summary["file_name_specific_evidence_patch"] is False
    assert summary["silver_expected_answer_used_as_generation_input"] is False
    assert summary["silver_evidence_locator_used_as_retrieval_shortcut"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_7_0_source_registry_materialization_does_not_mutate_protected_surfaces_or_promote_silver():
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_7_0_"
        "source_registry_materialization"
    )
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/payload_contract_summary.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/faiss.index",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["all_source_nonprod_index_sha256_before"] == summary["all_source_nonprod_index_sha256_after"]
    assert summary["all_source_nonprod_index_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["implementation_allowed"] is True
    assert summary["index_or_export_mutation"] is True
    assert summary["index_or_export_mutation_scope"] == "source_registry_artifacts_only"
    assert summary["vector_index_build_performed"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["retrieval_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["official_metric_denominator_usage_allowed"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    assert summary["query_id_specific_evidence_patch"] is False
    assert summary["file_name_specific_evidence_patch"] is False
    assert summary["silver_expected_answer_used_as_generation_input"] is False
    assert summary["silver_evidence_locator_used_as_retrieval_shortcut"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_7_1_all_source_citable_nonprod_index_does_not_mutate_source_registry_or_protected_surfaces():
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_7_1_"
        "all_source_citable_nonprod_index_build"
    )
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/payload_contract_summary.json",
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["implementation_allowed"] is True
    assert summary["index_or_export_mutation"] is True
    assert summary["index_or_export_mutation_scope"] == "non_production_only"
    assert summary["vector_index_build_performed"] is True
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["retrieval_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["hybrid_retrieval_baseline_computed"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["official_denominator_query_id_set_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_7_2_source_registry_backed_retrieval_smoke_does_not_mutate_source_registry_or_protected_surfaces():
    run_id = (
        "official_answer_citation_agentic_loop_run_v3_7_2_"
        "source_registry_backed_retrieval_smoke_report"
    )
    summary_path = (
        ROOT
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / f"{run_id}_summary.json"
    )
    require_v3_7_2_local_artifacts(summary_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization_xlsx_nonprod_sourceatom_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization_xlsx_nonprod_searchunit_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization_xlsx_nonprod_index_build_summary.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["index_or_export_mutation"] is False
    assert summary["retrieval_index_mutation"] is False
    assert summary["vector_index_build_performed"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["production_db_usage_allowed"] is False
    assert summary["production_db_used"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["db_index_rebuild_attempted"] is False
    assert summary["db_write_migration_reindex_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["citation_metric_computed"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["official_gold_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False


def test_v3_8_file_grounded_retrieval_eval_does_not_mutate_source_registry_or_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_8_file_grounded_retrieval_eval"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    require_v3_8_local_artifacts(summary_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["index_or_export_mutation"] is False
    assert summary["retrieval_index_mutation"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_canonical_truth_used_for_metrics"] is True
    assert summary["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["answer_generation_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_8_1_evidence_selector_does_not_mutate_source_registry_or_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_8_1_evidence_selector_v1"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    require_v3_8_1_local_artifacts(summary_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["index_or_export_mutation"] is False
    assert summary["retrieval_index_mutation"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_canonical_truth_used_for_selection"] is True
    assert summary["selector_uses_target_source_atom_ids_for_selection"] is False
    assert summary["target_source_atom_ids_used_for_metrics_only"] is True
    assert summary["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["answer_generation_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["gold_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_8_2_oracle_free_file_resolve_does_not_mutate_source_registry_or_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_8_2_oracle_free_file_resolve"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    require_v3_8_2_local_artifacts(summary_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["v3_8_summary_sha256_before"] == summary["v3_8_summary_sha256_after"]
    assert summary["v3_8_summary_sha256_unchanged"] is True
    assert summary["v3_8_1_summary_sha256_before"] == summary["v3_8_1_summary_sha256_after"]
    assert summary["v3_8_1_summary_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["index_or_export_mutation"] is False
    assert summary["retrieval_index_mutation"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_canonical_truth_used_for_resolution"] is True
    assert summary["file_resolve_oracle_free"] is True
    assert summary["oracle_assisted_file_resolve"] is False
    assert summary["oracle_free_input_violation_count"] == 0
    assert summary["resolver_uses_target_source_atom_ids_for_selection"] is False
    assert summary["target_source_atom_ids_used_for_metrics_only"] is True
    assert summary["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["answer_generation_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["gold_mutation"] is False
    assert summary["qrels_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_8_3_xlsx_scoped_cell_resolve_does_not_mutate_source_registry_or_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_8_3_xlsx_scoped_cell_resolve_diagnostic"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    require_v3_8_3_local_artifacts(summary_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["v3_8_2_summary_sha256_before"] == summary["v3_8_2_summary_sha256_after"]
    assert summary["v3_8_2_summary_sha256_unchanged"] is True
    assert summary["v3_8_2_per_query_sha256_before"] == summary["v3_8_2_per_query_sha256_after"]
    assert summary["v3_8_2_per_query_sha256_unchanged"] is True
    assert summary["diagnostic_only"] is True
    assert summary["xlsx_only"] is True
    assert summary["index_or_export_mutation"] is False
    assert summary["retrieval_index_mutation"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_canonical_truth_used_for_resolution"] is True
    assert summary["file_resolve_oracle_free"] is True
    assert summary["oracle_assisted_file_resolve"] is False
    assert summary["oracle_free_input_violation_count"] == 0
    assert summary["resolver_uses_target_source_atom_ids_for_selection"] is False
    assert summary["target_source_atom_ids_used_for_metrics_only"] is True
    assert summary["canonical_citation_payload_stored_in_vector_metadata"] is False
    assert summary["vector_metadata_used_as_canonical_citation_source"] is False
    assert summary["vector_metadata_used_as_evidence_truth"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["official_metric"] is False
    assert summary["answer_generation_metric_computed"] is False
    assert summary["answer_metric_computed"] is False
    assert summary["gold_mutation"] is False
    assert summary["qrels_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["silver_mutation"] is False
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["readme_performance_claim_mutation"] is False
    assert summary["measurements_doc_updated"] is False
    assert summary["triage_doc_updated"] is False
    assert summary["v3_8_2_gate_missing_count"] == 0
    assert summary["v3_8_2_gate_duplicate_query_id_count"] == 0
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_9_natural_answer_quality_does_not_mutate_protected_surfaces():
    label = "v3_9_natural_answer_quality_validation_6pf"
    summary_path = REPORT_DIR / "quality" / f"pdf_xlsx_llm_quality_{label}_summary.json"
    metrics_path = REPORT_DIR / "quality" / f"pdf_xlsx_llm_quality_{label}_metrics.json"
    require_v3_9_local_artifacts(summary_path, metrics_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    assert summary["run_id"] == "official_answer_citation_agentic_loop_run_v3_9_natural_answer_quality_diagnostic"
    assert summary["policy"]["diagnostic_only"] is True
    assert summary["policy"]["official_metric_input_rows"] == 0
    assert summary["policy"]["gold_or_label_mutation"] is False
    assert summary["policy"]["expected_answer_or_supporting_evidence_used"] is False
    assert summary["policy"]["denominator_mutation"] is False
    assert summary["policy"]["production_mutation"] is False
    assert summary["policy"]["promotion_evidence"] is False
    assert summary["policy"]["threshold_tuning"] is False
    assert summary["policy"]["winner_selection"] is False
    assert summary["future_scored_adapter"]["adapter_enabled"] is False
    assert summary["future_scored_adapter"]["status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["future_scored_adapter"]["official_metric_input_rows"] == 0
    assert summary["case_selection"]["source_document_disjoint_from_dev"] is True
    assert summary["case_selection"]["official_metric_input_rows"] == 0
    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["adapter_enabled"] is False
    assert metrics["promotion_evidence"] is False
    assert metrics["threshold_tuning"] is False
    assert metrics["winner_selection"] is False
    assert metrics["protected_official_rows_role"] == "sealed_no_regression_reference_only"


def test_v3_9_pdf_xlsx_bottleneck_quality_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_9_pdf_xlsx_bottleneck_quality_improvement"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    require_v3_9_local_artifacts(summary_path, metrics_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["fine_tuning_executed"] is False
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["policy"]["gold_or_label_mutation"] is False
    assert summary["policy"]["qrels_mutation"] is False
    assert summary["policy"]["expected_answer_or_supporting_evidence_used"] is False
    assert summary["policy"]["official_denominator_mutation"] is False
    assert summary["policy"]["namespace_mutation"] is False
    assert summary["policy"]["production_mutation"] is False
    assert summary["policy"]["promotion_evidence"] is False
    assert summary["policy"]["threshold_tuning"] is False
    assert summary["policy"]["winner_selection"] is False
    assert summary["policy"]["target_locator_used_for_selection"] is False
    assert summary["policy"]["target_locator_metrics_only"] is True
    assert summary["candidate_rule_freeze"]["direct_normalized_value_query_matching"] is False
    assert summary["candidate_rule_freeze"]["exact_query_hacks"] is False
    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["adapter_enabled"] is False
    assert metrics["promotion_evidence"] is False
    assert metrics["threshold_tuning"] is False
    assert metrics["winner_selection"] is False
    assert metrics["gold_mutation"] is False
    assert metrics["label_mutation"] is False
    assert metrics["qrels_mutation"] is False
    assert metrics["expected_answer_mutation"] is False
    assert metrics["supporting_evidence_mutation"] is False
    assert metrics["official_denominator_mutation"] is False
    assert metrics["namespace_mutation"] is False
    assert metrics["production_mutation"] is False


def test_v3_9_1_xlsx_table_axis_pdf_file_identity_does_not_mutate_source_registry_or_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_9_1_xlsx_sourceatom_table_axis_pdf_file_identity_diagnostic"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    require_v3_9_local_artifacts(summary_path, metrics_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["fine_tuning_started"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["answer_value_in_query_success_evidence_used"] is False
    assert summary["index_to_content_success_evidence_used"] is False
    assert summary["file_or_source_title_leak_success_evidence_used"] is False
    assert summary["protected_input_sha256_before"] == summary["protected_input_sha256_after"]
    assert summary["protected_input_sha256_unchanged"] is True
    assert summary["source_registry_sha256_before"] == summary["source_registry_sha256_after"]
    assert summary["source_registry_sha256_unchanged"] is True
    assert summary["index_artifact_sha256_before"] == summary["index_artifact_sha256_after"]
    assert summary["index_artifact_sha256_unchanged"] is True
    assert summary["official_denominator_index_sha256_before"] == summary["official_denominator_index_sha256_after"]
    assert summary["official_denominator_index_sha256_unchanged"] is True
    assert summary["source_registry_mutation"] is False
    assert summary["index_or_export_mutation"] is False
    assert summary["retrieval_index_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["db_write_attempted"] is False
    assert summary["db_migration_attempted"] is False
    assert summary["prompt_mutation"] is False
    assert summary["scorer_mutation"] is False
    assert summary["gold_mutation"] is False
    assert summary["qrels_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["official_qrels_created"] is False
    assert summary["official_relevance_labels_created"] is False
    assert summary["official_answerability_labels_created"] is False
    assert summary["promotion_evidence"] is False
    assert summary["promotion_gate"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["promotion_evidence"] is False
    assert metrics["threshold_tuning"] is False
    assert metrics["winner_selection"] is False
    assert metrics["direct_normalized_value_query_matching_used"] is False
    assert metrics["answer_value_in_query_success_evidence_used"] is False
    assert metrics["index_to_content_success_evidence_used"] is False
    assert metrics["file_or_source_title_leak_success_evidence_used"] is False
    assert metrics["per_source_family"]["PDF_CONTENT"]["computed_in_this_run"] is False
    assert metrics["per_source_family"]["TEXT"]["comparison_only"] is True
    for split in ("contract", "dev", "holdout"):
        assert not (ROOT / "ai" / "eval" / "silver" / f"answer_citation_silver_{split}_v1.jsonl").exists()


def test_v3_9_2_overfit_risk_audit_and_holdout_reset_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_9_2_overfit_risk_audit_and_blind_holdout_reset"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    architecture_path = REPORT_DIR / f"{run_id}_architecture_scope_assessment.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, architecture_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    architecture = read_json(architecture_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["fine_tuning_executed"] is False
    assert summary["gold_mutation"] is False
    assert summary["qrels_mutation"] is False
    assert summary["label_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["staging_or_commit_performed"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["answer_value_in_query_success_evidence_used"] is False
    assert summary["index_to_content_success_evidence_used"] is False
    assert summary["file_or_source_title_leak_success_evidence_used"] is False
    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["fine_tuning_executed"] is False
    assert metrics["direct_normalized_value_query_matching_used"] is False
    assert metrics["answer_value_in_query_success_evidence_used"] is False
    assert metrics["index_to_content_success_evidence_used"] is False
    assert metrics["file_or_source_title_leak_success_evidence_used"] is False
    assert architecture["protected_surface_check"]["gold_qrels_labels_expected_supporting_denominator_changed"] is False
    assert architecture["protected_surface_check"]["db_or_production_namespace_changed"] is False
    assert architecture["xlsx_sourceatom_searchunit_table_axis_materialization"]["materialized_in_v3_9_1"] is False
    assert architecture["xlsx_sourceatom_searchunit_table_axis_materialization"]["scope"] == "overlay_rerank_only"
    assert architecture["pdf_file_identity_scope"]["file_identity_gain_mixed_with_answer_ready_gain"] is False


def test_v3_10_fresh_holdout_xlsx_table_axis_nonprod_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    index_summary_path = REPORT_DIR / f"{run_id}_xlsx_nonprod_index_build_summary.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, index_summary_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    index_summary = read_json(index_summary_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["fine_tuning_executed"] is False
    assert summary["gold_mutation"] is False
    assert summary["qrels_mutation"] is False
    assert summary["label_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["official_denominator_mutation"] is False
    assert summary["production_mutation"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["staging_or_commit_performed"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["answer_value_in_query_success_evidence_used"] is False
    assert summary["index_to_content_success_evidence_used"] is False
    assert summary["file_or_source_title_leak_success_evidence_used"] is False
    assert summary["xlsx_nonprod_namespace"] == "rag-data-xlsx-table-axis-ood-nonprod-v1"
    assert summary["protected_namespaces_touched"] == []
    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["fresh_real_holdout"]["sufficient"] is False
    assert metrics["fresh_real_holdout"]["product_success_evidence_allowed"] is False
    assert index_summary["index_namespace"] == "rag-data-xlsx-table-axis-ood-nonprod-v1"
    assert index_summary["protected_namespaces_touched"] == []
    assert index_summary["source_registry_baseline_mutated"] is False
    assert index_summary["official_denominator_mutated"] is False
    assert index_summary["db_or_production_namespace_written"] is False
    assert index_summary["overlay_only"] is False


def test_v3_11_layered_retrieval_diagnostic_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_11_layered_retrieval_diagnostic"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    guardrail_path = REPORT_DIR / f"{run_id}_guardrail_audit.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["answer_generation_executed"] is False
    assert summary["fresh_real_holdout_sufficient"] is False
    assert summary["product_success_evidence_allowed"] is False
    assert summary["pdf_file_identity_answer_window_kept_separate"] is True
    assert summary["pdf_bbox_correctness_metric_computed"] is False
    assert summary["ocr_touched"] is False
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
        "direct_normalized_value_query_matching_used",
        "answer_value_in_query_success_evidence_used",
        "index_to_content_success_evidence_used",
        "file_or_source_title_leak_success_evidence_used",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag

    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["product_success_evidence_allowed"] is False
    assert metrics["answer_generation_executed"] is False
    assert metrics["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert metrics["per_source_family"]["PDF_EVIDENCE_WINDOW"]["metrics"]["bbox_correctness_metric_computed"] is False
    assert guardrail["protected_namespaces_touched"] == []
    assert guardrail["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert guardrail["vector_payload_used_as_evidence_truth"] is False
    assert guardrail["source_atom_registry_mutated"] is False
    assert guardrail["official_denominator_mutated"] is False
    assert guardrail["db_or_production_namespace_written"] is False


def test_v3_12_xlsx_structural_locator_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    guardrail_path = REPORT_DIR / f"{run_id}_guardrail_audit.json"
    index_path = REPORT_DIR / f"{run_id}_xlsx_nonprod_index_build_summary.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path, index_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    index_summary = read_json(index_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["answer_generation_executed"] is False
    assert summary["fresh_real_holdout_sufficient"] is False
    assert summary["product_success_evidence_allowed"] is False
    assert summary["promotion_evidence"] is False
    assert summary["index_namespace"] == "rag-data-xlsx-structural-locator-nonprod-v1"
    assert summary["source_index_namespace"] == "rag-data-xlsx-table-axis-ood-nonprod-v1"
    assert summary["protected_namespaces_touched"] == []
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
        "direct_normalized_value_query_matching_used",
        "answer_value_in_query_success_evidence_used",
        "index_to_content_success_evidence_used",
        "file_or_source_title_leak_success_evidence_used",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag

    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["fresh_real_holdout"]["sufficient"] is False
    assert metrics["fresh_real_holdout"]["product_success_evidence_allowed"] is False
    assert metrics["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert guardrail["protected_namespaces_touched"] == []
    assert guardrail["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert guardrail["vector_payload_used_as_evidence_truth"] is False
    assert guardrail["source_atom_registry_mutated"] is False
    assert guardrail["official_denominator_mutated"] is False
    assert guardrail["db_or_production_namespace_written"] is False
    assert index_summary["index_namespace"] == "rag-data-xlsx-structural-locator-nonprod-v1"
    assert index_summary["source_namespace"] == "rag-data-xlsx-table-axis-ood-nonprod-v1"
    assert index_summary["manifest_only"] is True
    assert index_summary["protected_namespaces_touched"] == []
    assert index_summary["db_or_production_namespace_written"] is False


def test_v3_13_pdf_file_identity_structural_locator_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    guardrail_path = REPORT_DIR / f"{run_id}_guardrail_audit.json"
    manifest_path = REPORT_DIR / f"{run_id}_pdf_nonprod_manifest_summary.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path, manifest_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_10_"
        "fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization_xlsx_nonprod_index_build_summary.json",
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement_"
        "xlsx_nonprod_index_build_summary.json",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    manifest_summary = read_json(manifest_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["answer_generation_executed"] is False
    assert summary["deterministic_answer_execution_executed"] is False
    assert summary["fresh_real_holdout_sufficient"] is False
    assert summary["product_success_evidence_allowed"] is False
    assert summary["pdf_file_identity_answer_window_kept_separate"] is True
    assert summary["pdf_bbox_correctness_metric_computed"] is False
    assert summary["xlsx_v3_12_control_lane_only"] is True
    assert summary["index_namespace"] == "rag-data-pdf-structural-locator-nonprod-v1"
    assert summary["source_index_namespace"] == "rag-data-all-source-citable-nonprod-v1"
    assert summary["protected_namespaces_touched"] == []
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
        "answer_value_in_query_success_evidence_used",
        "index_to_content_success_evidence_used",
        "file_or_source_title_leak_success_evidence_used",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag

    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["product_success_evidence_allowed"] is False
    assert metrics["answer_generation_executed"] is False
    assert metrics["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert metrics["pdf_file_identity_structural_locator_eval"]["v3_13_pdf_evidence_window_diagnostic"][
        "bbox_correctness_metric_computed"
    ] is False
    assert guardrail["protected_namespaces_touched"] == []
    assert guardrail["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert guardrail["source_atom_registry_mutated"] is False
    assert guardrail["official_denominator_mutated"] is False
    assert guardrail["db_or_production_namespace_written"] is False
    assert guardrail["vector_payload_used_as_evidence_truth"] is False
    assert manifest_summary["index_namespace"] == "rag-data-pdf-structural-locator-nonprod-v1"
    assert manifest_summary["manifest_only"] is True
    assert manifest_summary["index_build_executed"] is False
    assert manifest_summary["protected_namespaces_touched"] == []
    assert manifest_summary["db_or_production_namespace_written"] is False


def test_v3_14_layered_retrieval_runtime_adapter_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    guardrail_path = REPORT_DIR / f"{run_id}_guardrail_audit.json"
    candidate_flow_path = REPORT_DIR / f"{run_id}_candidate_flow_summary.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path, candidate_flow_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement_xlsx_structural_locator_eval_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement_xlsx_layer_trace_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement_xlsx_score_components.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_pdf_structural_locator_eval_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_pdf_layer_trace_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_pdf_score_components.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    candidate_flow = read_json(candidate_flow_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["answer_generation_executed"] is False
    assert summary["deterministic_answer_execution_executed"] is False
    assert summary["L8_executed"] is False
    assert summary["raw_file_query_time_accessed"] is False
    assert summary["fresh_real_holdout_sufficient"] is False
    assert summary["product_success_evidence_allowed"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_mutated"] is False
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert summary["protected_namespaces_touched"] == []
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
        "promotion_evidence",
        "direct_normalized_value_query_matching_used",
        "answer_value_in_query_success_evidence_used",
        "index_to_content_success_evidence_used",
        "file_or_source_title_leak_success_evidence_used",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag

    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["product_success_evidence_allowed"] is False
    assert metrics["raw_file_query_time_accessed"] is False
    assert metrics["L8_executed"] is False
    assert guardrail["protected_namespaces_touched"] == []
    assert guardrail["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert guardrail["source_atom_registry_mutated"] is False
    assert guardrail["official_denominator_mutated"] is False
    assert guardrail["db_or_production_namespace_written"] is False
    assert guardrail["raw_file_query_time_accessed"] is False
    assert guardrail["raw_file_fallback_blocked_count"] == 0
    assert guardrail["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert guardrail["vector_payload_used_as_evidence_truth"] is False
    assert candidate_flow["raw_file_query_time_accessed"] is False
    assert candidate_flow["L8_executed"] is False


def test_v3_15_xlsx_l3_table_range_locator_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement"
    summary_path = REPORT_DIR / f"{run_id}_summary.json"
    metrics_path = REPORT_DIR / f"{run_id}_metrics.json"
    guardrail_path = REPORT_DIR / f"{run_id}_guardrail_audit.json"
    candidate_flow_path = REPORT_DIR / f"{run_id}_candidate_flow_summary.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path, candidate_flow_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod_layer_trace_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement_xlsx_structural_locator_eval_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement_xlsx_layer_trace_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_12_xlsx_structural_locator_nonprod_improvement_xlsx_score_components.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization_xlsx_nonprod_sourceatom_manifest.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_10_fresh_real_holdout_and_xlsx_table_axis_nonprod_rematerialization_xlsx_nonprod_searchunit_manifest.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    candidate_flow = read_json(candidate_flow_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert summary["answer_generation_executed"] is False
    assert summary["deterministic_answer_execution_executed"] is False
    assert summary["L8_executed"] is False
    assert summary["raw_file_query_time_accessed"] is False
    assert summary["fresh_real_holdout_sufficient"] is False
    assert summary["product_success_evidence_allowed"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_mutated"] is False
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert summary["protected_namespaces_touched"] == []
    assert summary["optimization_surface"] == "XLSX_L3_TABLE_RANGE_LOCATOR_ONLY"
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
        "promotion_evidence",
        "direct_normalized_value_query_matching_used",
        "raw_answer_value_for_query_scoring_used",
        "answer_value_in_query_success_evidence_used",
        "index_to_content_success_evidence_used",
        "file_or_source_title_leak_success_evidence_used",
        "exact_query_hack_used",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag

    assert metrics["official_metric"] is False
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["product_success_evidence_allowed"] is False
    assert metrics["raw_file_query_time_accessed"] is False
    assert metrics["L8_executed"] is False
    assert guardrail["protected_namespaces_touched"] == []
    assert guardrail["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert guardrail["source_atom_registry_mutated"] is False
    assert guardrail["official_denominator_mutated"] is False
    assert guardrail["db_or_production_namespace_written"] is False
    assert guardrail["raw_file_query_time_accessed"] is False
    assert guardrail["raw_file_fallback_blocked_count"] == 0
    assert guardrail["future_scored_adapter_status"] == "DISABLED_PENDING_USER_APPROVAL"
    assert guardrail["vector_payload_used_as_evidence_truth"] is False
    assert candidate_flow["raw_file_query_time_accessed"] is False
    assert candidate_flow["L8_executed"] is False


def test_v3_16_final_llm_answer_quality_review_packet_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod"
    output_dir = REPORT_DIR / "quality" / run_id
    summary_path = output_dir / "summary.json"
    metrics_path = output_dir / "metrics.json"
    guardrail_path = output_dir / "guardrail_audit.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_layer_trace_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod_layer_trace_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_pdf_structural_locator_eval_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_pdf_layer_trace_per_query.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["L8_generation_executed"] is True
    assert summary["deterministic_official_execution"] is False
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["promotion_evidence"] is False
    assert summary["raw_file_query_time_accessed"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["protected_namespaces_touched"] == []
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert guardrail["db_or_production_namespace_written"] is False


def test_v3_17_user_locator_rough_query_packet_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod"
    output_dir = REPORT_DIR / "quality" / run_id
    summary_path = output_dir / "summary.json"
    metrics_path = output_dir / "metrics.json"
    guardrail_path = output_dir / "guardrail_audit.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod_summary.json",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_15_xlsx_l3_table_range_locator_nonprod_improvement_layer_trace_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_14_layered_retrieval_runtime_adapter_nonprod_layer_trace_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_pdf_structural_locator_eval_per_query.jsonl",
        "ai/eval/reports/rag-ingestion/official_answer_citation_agentic_loop_run_v3_13_pdf_file_identity_structural_locator_nonprod_alignment_pdf_layer_trace_per_query.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["promotion_evidence"] is False
    assert summary["raw_file_query_time_accessed"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["target_locator_used"] is False
    assert summary["gold_locator_used"] is False
    assert summary["expected_supporting_text_used"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["protected_namespaces_touched"] == []
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert guardrail["db_or_production_namespace_written"] is False


def test_v3_18_agent_runtime_tool_invocation_contract_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod"
    output_dir = REPORT_DIR / "quality" / run_id
    summary_path = output_dir / "summary.json"
    metrics_path = output_dir / "metrics.json"
    guardrail_path = output_dir / "guardrail_audit.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path)
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/quality/"
        "official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod/"
        "summary.json",
        "ai/eval/reports/rag-ingestion/quality/"
        "official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod/"
        "review_packet.jsonl",
        "ai/eval/reports/rag-ingestion/quality/"
        "official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod/"
        "tool_registry.json",
        "ai/eval/reports/rag-ingestion/quality/"
        "official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod/"
        "route_policy_audit.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["agent_runtime_nonprod"] is True
    assert summary["agent_runtime_product_ready"] is False
    assert summary["tool_registry_only_invocation"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["promotion_evidence"] is False
    assert summary["raw_file_query_time_accessed"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_mutated"] is False
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["target_locator_used"] is False
    assert summary["gold_locator_used"] is False
    assert summary["expected_supporting_text_used"] is False
    assert summary["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["protected_namespaces_touched"] == []
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "official_denominator_mutated",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["runtime_contract_violation_count"] == 0
    assert metrics["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert guardrail["db_or_production_namespace_written"] is False


def test_v3_19_locator_ambiguity_deictic_response_policy_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod"
    output_dir = REPORT_DIR / "quality" / run_id
    summary_path = output_dir / "summary.json"
    metrics_path = output_dir / "metrics.json"
    guardrail_path = output_dir / "guardrail_audit.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path)
    v3_18_dir = (
        "ai/eval/reports/rag-ingestion/quality/"
        "official_answer_citation_agentic_loop_run_v3_18_agent_runtime_tool_invocation_contract_nonprod/"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        f"{v3_18_dir}summary.json",
        f"{v3_18_dir}metrics.json",
        f"{v3_18_dir}per_query.jsonl",
        f"{v3_18_dir}agent_tool_call_trace.jsonl",
        f"{v3_18_dir}route_policy_audit.jsonl",
        f"{v3_18_dir}runtime_contract_audit.jsonl",
        f"{v3_18_dir}guardrail_audit.json",
        f"{v3_18_dir}leakage_audit.jsonl",
        f"{v3_18_dir}review_packet.jsonl",
        f"{v3_18_dir}review_packet.csv",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["agent_runtime_nonprod"] is True
    assert summary["agent_runtime_product_ready"] is False
    assert summary["tool_registry_only_invocation"] is True
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["promotion_evidence"] is False
    assert summary["ambiguous_locator_fail_closed"] is True
    assert summary["page_only_locator_without_context_fail_closed"] is True
    assert summary["deictic_context_missing_fail_closed"] is True
    assert summary["raw_file_query_time_accessed"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_registry_mutated"] is False
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["target_locator_used"] is False
    assert summary["gold_locator_used"] is False
    assert summary["expected_supporting_text_used"] is False
    assert summary["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["protected_namespaces_touched"] == []
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "official_denominator_mutated",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["ambiguous_locator_nonabstained_count"] == 0
    assert metrics["page_only_locator_nonabstained_count"] == 0
    assert metrics["sheet_only_locator_nonabstained_count"] == 0
    assert metrics["deictic_context_missing_nonabstained_count"] == 0
    assert metrics["runtime_contract_violation_count"] == 0
    assert metrics["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert guardrail["db_or_production_namespace_written"] is False


def test_v3_20_live_runtime_like_db_index_cache_smoke_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod"
    output_dir = REPORT_DIR / "quality" / run_id
    summary_path = output_dir / "summary.json"
    metrics_path = output_dir / "metrics.json"
    guardrail_path = output_dir / "guardrail_audit.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path)
    v3_19_dir = (
        "ai/eval/reports/rag-ingestion/quality/"
        "official_answer_citation_agentic_loop_run_v3_19_locator_ambiguity_and_deictic_query_fail_closed_response_policy_nonprod/"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        f"{v3_19_dir}summary.json",
        f"{v3_19_dir}metrics.json",
        f"{v3_19_dir}per_query.jsonl",
        f"{v3_19_dir}agent_tool_call_trace.jsonl",
        f"{v3_19_dir}route_policy_audit.jsonl",
        f"{v3_19_dir}runtime_contract_audit.jsonl",
        f"{v3_19_dir}user_response_policy_audit.jsonl",
        f"{v3_19_dir}guardrail_audit.json",
        f"{v3_19_dir}leakage_audit.jsonl",
        f"{v3_19_dir}review_packet.jsonl",
        f"{v3_19_dir}review_packet.csv",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["agent_runtime_nonprod"] is True
    assert summary["agent_runtime_product_ready"] is False
    assert summary["tool_registry_only_invocation"] is True
    assert summary["live_db_index_cache_readiness"] is False
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["promotion_evidence"] is False
    assert summary["raw_file_query_time_accessed"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_store_canonical_truth"] is True
    assert summary["source_atom_registry_mutated"] is False
    assert summary["search_index_candidate_only"] is True
    assert summary["runtime_cache_evidence_truth"] is False
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["target_locator_used"] is False
    assert summary["gold_locator_used"] is False
    assert summary["expected_supporting_text_used"] is False
    assert summary["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["protected_namespaces_touched"] == []
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "official_denominator_mutated",
        "production_mutation",
        "threshold_tuning",
        "winner_selection",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["runtime_contract_violation_count"] == 0
    assert metrics["production_write_attempt_count"] == 0
    assert metrics["broad_source_atom_scan_attempt_count"] == 0
    assert metrics["vector_payload_evidence_truth_violation_count"] == 0
    assert metrics["pdf_xlsx_collapsed_headline_score_reported"] is False
    assert guardrail["db_or_production_namespace_written"] is False


def test_v3_21_agent_runtime_llm_io_observability_packet_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod"
    output_dir = REPORT_DIR / "quality" / run_id
    summary_path = output_dir / "summary.json"
    metrics_path = output_dir / "metrics.json"
    guardrail_path = output_dir / "guardrail_audit.json"
    require_v3_9_local_artifacts(summary_path, metrics_path, guardrail_path)
    v3_20_dir = (
        "ai/eval/reports/rag-ingestion/quality/"
        "official_answer_citation_agentic_loop_run_v3_20_live_runtime_like_db_index_cache_smoke_nonprod/"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        f"{v3_20_dir}summary.json",
        f"{v3_20_dir}metrics.json",
        f"{v3_20_dir}per_query.jsonl",
        f"{v3_20_dir}agent_tool_call_trace.jsonl",
        f"{v3_20_dir}route_policy_audit.jsonl",
        f"{v3_20_dir}runtime_contract_audit.jsonl",
        f"{v3_20_dir}user_response_policy_audit.jsonl",
        f"{v3_20_dir}db_contract_audit.jsonl",
        f"{v3_20_dir}index_contract_audit.jsonl",
        f"{v3_20_dir}cache_contract_audit.jsonl",
        f"{v3_20_dir}live_runtime_smoke_audit.jsonl",
        f"{v3_20_dir}guardrail_audit.json",
        f"{v3_20_dir}leakage_audit.jsonl",
        f"{v3_20_dir}review_packet.jsonl",
        f"{v3_20_dir}review_packet.csv",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    summary = read_json(summary_path)
    metrics = read_json(metrics_path)
    guardrail = read_json(guardrail_path)
    assert summary["run_id"] == run_id
    assert summary["diagnostic_only"] is True
    assert summary["agent_runtime_nonprod"] is True
    assert summary["agent_runtime_product_ready"] is False
    assert summary["tool_registry_only_invocation"] is True
    assert summary["live_db_index_cache_readiness"] is False
    assert summary["official_metric"] is False
    assert summary["official_metric_input_rows"] == 0
    assert summary["promotion_evidence"] is False
    assert summary["raw_file_query_time_accessed"] is False
    assert summary["source_atom_registry_canonical_truth"] is True
    assert summary["source_atom_store_canonical_truth"] is True
    assert summary["source_atom_registry_mutated"] is False
    assert summary["search_index_candidate_only"] is True
    assert summary["runtime_cache_evidence_truth"] is False
    assert summary["vector_payload_used_as_evidence_truth"] is False
    assert summary["target_locator_used"] is False
    assert summary["gold_locator_used"] is False
    assert summary["expected_supporting_text_used"] is False
    assert summary["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert summary["direct_normalized_value_query_matching_used"] is False
    assert summary["actual_llm_responses_are_required_when_llm_invoked"] is True
    assert summary["noop_or_extractive_generator_used"] is False
    assert summary["protected_namespaces_touched"] == []
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "official_denominator_mutated",
        "production_mutation",
        "db_or_production_namespace_written",
        "threshold_tuning",
        "winner_selection",
        "pdf_xlsx_collapsed_headline_score_reported",
    ):
        assert summary[flag] is False, flag
        assert guardrail[flag] is False, flag
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["runtime_contract_violation_count"] == 0
    assert metrics["prompt_leakage_flag_count"] == 0
    assert metrics["response_leakage_flag_count"] == 0
    assert metrics["path_leakage_flag_count"] == 0
    assert metrics["evidence_truth_violation_count"] == 0
    assert metrics["production_write_attempt_count"] == 0
    assert metrics["broad_source_atom_scan_attempt_count"] == 0
    assert guardrail["db_or_production_namespace_written"] is False


def test_v3_22_xlsx_display_value_and_range_rendering_does_not_mutate_protected_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
    output_dir = REPORT_DIR / "quality" / run_id
    report_path = output_dir / "report.json"
    require_v3_9_local_artifacts(report_path)
    v3_21_dir = (
        "ai/eval/reports/rag-ingestion/quality/"
        "official_answer_citation_agentic_loop_run_v3_21_agent_runtime_llm_io_observability_packet_nonprod/"
    )
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        f"{v3_21_dir}summary.json",
        f"{v3_21_dir}metrics.json",
        f"{v3_21_dir}per_query.jsonl",
        f"{v3_21_dir}agent_tool_call_trace.jsonl",
        f"{v3_21_dir}route_policy_audit.jsonl",
        f"{v3_21_dir}runtime_contract_audit.jsonl",
        f"{v3_21_dir}user_response_policy_audit.jsonl",
        f"{v3_21_dir}db_contract_audit.jsonl",
        f"{v3_21_dir}index_contract_audit.jsonl",
        f"{v3_21_dir}cache_contract_audit.jsonl",
        f"{v3_21_dir}live_runtime_smoke_audit.jsonl",
        f"{v3_21_dir}llm_io_packet.jsonl",
        f"{v3_21_dir}llm_io_packet.csv",
        f"{v3_21_dir}llm_invocation_audit.jsonl",
        f"{v3_21_dir}local_llm_readiness.json",
        f"{v3_21_dir}prompt_manifest.json",
        f"{v3_21_dir}guardrail_audit.json",
        f"{v3_21_dir}leakage_audit.jsonl",
        f"{v3_21_dir}review_packet.jsonl",
        f"{v3_21_dir}review_packet.csv",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    metrics = report["metrics"]
    guardrail = report["guardrails"]
    assert report["run_id"] == run_id
    assert report["diagnostic_only"] is True
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["human_review_required"] is False
    assert report["review_csv_created"] is False
    assert guardrail["single_report_artifact_contract"] is True
    assert guardrail["agent_runtime_nonprod"] is True
    assert guardrail["agent_runtime_product_ready"] is False
    assert guardrail["tool_registry_only_invocation"] is True
    assert guardrail["live_db_index_cache_readiness"] is False
    assert guardrail["raw_file_query_time_accessed"] is False
    assert guardrail["source_atom_registry_canonical_truth"] is True
    assert guardrail["source_atom_store_canonical_truth"] is True
    assert guardrail["source_atom_registry_mutated"] is False
    assert guardrail["search_index_candidate_only"] is True
    assert guardrail["runtime_cache_evidence_truth"] is False
    assert guardrail["vector_payload_used_as_evidence_truth"] is False
    assert guardrail["target_locator_used"] is False
    assert guardrail["gold_locator_used"] is False
    assert guardrail["expected_supporting_text_used"] is False
    assert guardrail["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert guardrail["direct_normalized_value_query_matching_used"] is False
    assert guardrail["raw_xlsx_query_time_parsing_forbidden"] is True
    assert guardrail["formula_evaluation_at_query_time"] is False
    for flag in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "official_denominator_mutation",
        "official_denominator_mutated",
        "production_mutation",
        "db_or_production_namespace_written",
        "threshold_tuning",
        "winner_selection",
        "pdf_xlsx_collapsed_headline_score_reported",
    ):
        assert guardrail[flag] is False, flag
    assert metrics["official_metric_input_rows"] == 0
    assert metrics["runtime_contract_violation_count"] == 0
    assert metrics["vector_payload_evidence_truth_violation_count"] == 0
    assert metrics["raw_file_query_time_accessed"] is False
    assert metrics["production_write_attempt_count"] == 0
    assert metrics["broad_source_atom_scan_attempt_count"] == 0


def test_phase1_diagnostic_contract_closure_after_v3_22_does_not_mutate_or_promote_surfaces():
    closure_id = "phase1_diagnostic_contract_closure_after_v3_22"
    closure_event_type = "phase1_diagnostic_contract_closure_after_v3_22_ready"
    v3_22_run_id = "official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
    v3_22_report_path = REPORT_DIR / "quality" / v3_22_run_id / "report.json"
    require_v3_9_local_artifacts(STATUS_JSONL, v3_22_report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(v3_22_report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    event = next(
        item
        for item in reversed(events)
        if item.get("run_id") == closure_id and item.get("event_type") == closure_event_type
    )
    assert event["phase1_closed"] is True
    assert event["closure_basis_run_id"] == v3_22_run_id
    assert event["counter_source_of_truth"] == v3_22_report_path.relative_to(ROOT).as_posix()
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["xlsx_locator_performance_completion"] is False
    assert event["representative_product_performance"] is False
    assert event["source_atom_registry_mutated"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["raw_xlsx_query_time_parsing_forbidden"] is True
    assert event["formula_evaluation_at_query_time"] is False
    assert event["formula_text_visible_to_user_default"] is False
    assert event["review_csv_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["label_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["production_mutation"] is False
    assert event["db_or_production_namespace_written"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["pdf_xlsx_text_collapsed_headline_product_score"] is False
    assert event["artifact_paths"]["v3_22_report_json"] == v3_22_report_path.relative_to(ROOT).as_posix()
    assert event["artifact_sha256"]["v3_22_report_json_sha256"] == sha256_file(v3_22_report_path)
    assert report["summary"]["official_metric_input_rows"] == 0
    assert report["summary"]["product_success_evidence_allowed"] is False
    assert report["summary"]["promotion_evidence"] is False
    assert report["summary"]["live_db_index_cache_readiness"] is False
    assert report["summary"]["review_csv_created"] is False
    assert report["artifact_paths"] == {"report_json": v3_22_report_path.relative_to(ROOT).as_posix()}


def test_phase1_fastapi_diagnostic_integration_does_not_mutate_or_promote_surfaces():
    marker = "phase1_diagnostic_contract_closure_fastapi_diagnostic_integration"
    event_type = "phase1_diagnostic_contract_closure_fastapi_diagnostic_integration_ready"
    v3_22_run_id = "official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
    v3_22_report_path = REPORT_DIR / "quality" / v3_22_run_id / "report.json"
    require_v3_9_local_artifacts(STATUS_JSONL, v3_22_report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )
    for protected_path in protected_paths:
        unstaged = subprocess.run(["git", "diff", "--quiet", "--", protected_path], cwd=ROOT, check=False)
        staged = subprocess.run(["git", "diff", "--cached", "--quiet", "--", protected_path], cwd=ROOT, check=False)
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    event = next(
        item
        for item in reversed(events)
        if item.get("run_id") == marker and item.get("event_type") == event_type
    )
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["production_mutation"] is False
    assert event["db_or_production_namespace_written"] is False
    assert event["no_production_db_index_cache_writes"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["xlsx_locator_completion_claimed"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["label_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["pdf_xlsx_text_collapsed_headline_product_score"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["raw_xlsx_query_time_parsing_forbidden"] is True
    assert event["raw_pdf_query_time_parsing_forbidden"] is True

    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    forbidden_name_fragments = ("scratch", "tmp", "temp", "adhoc", "ad_hoc")
    assert not [
        line
        for line in status
        if any(fragment in Path(line[3:].strip()).name.lower() for fragment in forbidden_name_fragments)
    ]


def test_v4_0_charter_status_opening_does_not_mutate_or_promote_surfaces():
    v4_id = "v4_source_grounded_runtime_locator_and_finetune_readiness"
    v4_event_type = "v4_source_grounded_runtime_locator_and_finetune_readiness_opened"
    v3_22_run_id = "official_answer_citation_agentic_loop_run_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
    v3_22_report_path = REPORT_DIR / "quality" / v3_22_run_id / "report.json"
    require_v3_9_local_artifacts(STATUS_JSONL, v3_22_report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == v4_id and event.get("event_type") == v4_event_type
    ]
    assert len(matches) == 1
    event = matches[0]
    assert event["v4_opened"] is True
    assert event["closure_basis_run_id"] == v3_22_run_id
    assert event["counter_source_of_truth"] == v3_22_report_path.relative_to(ROOT).as_posix()
    assert event["diagnostic_only"] is True
    assert event["production_routing"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["representative_product_performance"] is False
    assert event["pdf_xlsx_text_collapsed_headline_product_score"] is False
    assert event["real_blind_ood_holdout_available"] is False
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["threshold_tuning"] is False
    assert event["winner_selection"] is False
    assert event["source_atom_registry_mutated"] is False
    assert event["source_atom_registry_canonical_truth"] is True
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["raw_xlsx_query_time_parsing_forbidden"] is True
    assert event["raw_pdf_query_time_parsing_forbidden"] is True
    assert event["direct_normalized_answer_value_query_matching_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["formula_evaluation_at_query_time"] is False
    assert event["formula_text_visible_to_user_default"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is False
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["prompt_payload_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["label_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["production_mutation"] is False
    assert event["db_or_production_namespace_written"] is False
    assert event["artifact_paths"] == {
        "v3_22_report_json": v3_22_report_path.relative_to(ROOT).as_posix(),
        "status_jsonl": "ai/eval/reports/rag-ingestion/status.jsonl",
        "progress_doc": "docs/rag-ingestion-progress.md",
        "measurements_doc": "docs/rag-ingestion-measurements.md",
        "triage_doc": "docs/rag-ingestion-triage.md",
    }
    assert event["artifact_sha256"]["v3_22_report_json_sha256"] == sha256_file(v3_22_report_path)
    assert "report_json" not in event["artifact_paths"]
    assert "review_packet.csv" not in event["artifact_paths"].values()
    assert "prompt_template" not in event
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_1_persisted_xlsx_sourceatom_display_metadata_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod"
    event_type = "diagnostic_v4_1_persisted_xlsx_sourceatom_display_metadata_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v3_9_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert report["metrics"]["official_metric_input_rows"] == 0
    assert report["metrics"]["product_success_evidence_allowed"] is False
    assert report["metrics"]["promotion_evidence"] is False
    assert report["metrics"]["fine_tuning_executed"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["raw_xlsx_query_time_parsing_forbidden"] is True
    assert report["guardrails"]["direct_normalized_value_query_matching_used"] is False
    assert report["guardrails"]["target_locator_used"] is False
    assert report["guardrails"]["gold_locator_used"] is False
    assert report["guardrails"]["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["source_atom_registry_mutated"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["raw_file_query_time_accessed"] is False
    assert event["raw_xlsx_query_time_parsing_forbidden"] is True
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["formula_evaluation_at_query_time"] is False
    assert event["formula_text_visible_to_user_default"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is True
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["prompt_payload_created"] is False
    assert event["persisted_sourceatom_manifest_jsonl_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["label_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["production_mutation"] is False
    assert event["db_or_production_namespace_written"] is False
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_7_3_human_reviewed_korean_query_candidate_decision_does_not_mutate_protected_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
    event_type = "diagnostic_v4_7_3_human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["human_review_applied"] is True
    assert report["csv_migeomsu_interpreted_as_pass"] is True
    assert report["query_candidate_pass_mutation"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["promotion_evidence"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["ft_a_execution"] is False
    assert report["fine_tuning"] is False
    assert report["qrels_mutation"] is False
    assert report["gold_mutation"] is False
    assert report["label_mutation"] is False
    assert report["expected_answer_mutation"] is False
    assert report["supporting_evidence_mutation"] is False
    assert report["denominator_mutation"] is False
    assert report["training_dataset_created"] is False
    assert report["gold_jsonl_created"] is False
    assert report["qrels_jsonl_created"] is False
    assert report["labels_jsonl_created"] is False
    assert report["expected_answer_artifact_created"] is False
    assert report["supporting_evidence_artifact_created"] is False
    assert report["training_manifest_jsonl_created"] is False
    assert report["prompt_manifest_jsonl_created"] is False
    assert report["raw_response_payload_jsonl_created"] is False
    assert report["checkpoint_artifact_created"] is False
    assert report["production_db_index_cache_artifact_created"] is False
    assert report["protected_namespaces_touched"] == []
    assert report["reviewed_csv_row_count"] == 204
    assert report["user_passed_query_candidate_row_count"] == 58
    assert report["user_excluded_row_count"] == 146
    assert report["passed_counts_by_family"] == {"PDF": 58, "XLSX": 0, "TEXT": 0}
    assert report["excluded_counts_by_family"] == {"PDF": 42, "XLSX": 104, "TEXT": 0}
    assert "prompt_payload" not in report
    assert "raw_llm_response" not in report
    assert "target_locator" not in report
    assert "gold_locator" not in report

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["human_review_applied"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["ft_a_execution"] is False
    assert event["fine_tuning"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["qrels_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["label_mutation"] is False
    assert event["training_dataset_created"] is False
    assert event["user_passed_query_candidate_row_count"] == 58
    assert event["user_excluded_row_count"] == 146
    assert event["artifact_paths"]["report_json"] == report_path.relative_to(ROOT).as_posix()
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_7_4_pdf_survivor_replay_does_not_mutate_protected_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
    event_type = "diagnostic_v4_7_4_pdf_survivor_retrieval_evidence_answer_quality_replay_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["pdf_survivor_row_count"] == 58
    assert report["xlsx_rows_in_scope"] == 0
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["gold_mutation"] is False
    assert report["qrels_mutation"] is False
    assert report["label_mutation"] is False
    assert report["expected_answer_mutation"] is False
    assert report["supporting_evidence_mutation"] is False
    assert report["denominator_mutation"] is False
    assert report["training_dataset_created"] is False
    assert report["ft_a_execution"] is False
    assert report["fine_tuning"] is False
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["protected_namespaces_touched"] == []
    assert report["raw_pdf_query_time_parsing"] is False
    assert report["broad_source_atom_scan_attempt_count"] == 0
    assert report["vector_payload_evidence_truth_violation_count"] == 0
    assert report["hidden_target_locator_used"] is False
    assert report["expected_or_supporting_gold_text_used"] is False
    assert report["source_file_title_shortcut_used"] is False
    assert report["SearchView_vector_payload_role"] == "candidate_only"
    assert report["SourceAtom_EvidenceBundle_role"] == "evidence_truth"
    assert report["metrics"]["evidence_bundle"]["evidence_bundle_created_count"] == 58
    assert report["metrics"]["evidence_bundle"]["vector_payload_evidence_truth_violation_count"] == 0
    assert "prompt_payload" not in report
    assert "raw_llm_response" not in report
    assert "raw_response_payload" not in report

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["non_production"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["ft_a_execution"] is False
    assert event["fine_tuning"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["qrels_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["label_mutation"] is False
    assert event["training_dataset_created"] is False
    assert event["pdf_survivor_row_count"] == 58
    assert event["xlsx_rows_in_scope"] == 0
    assert event["raw_pdf_query_time_parsing"] is False
    assert event["broad_source_atom_scan_attempt_count"] == 0
    assert event["vector_payload_evidence_truth_violation_count"] == 0
    assert event["hidden_target_locator_used"] is False
    assert event["artifact_paths"]["report_json"] == report_path.relative_to(ROOT).as_posix()
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_1_holdout_manifest_identity_contract_bridge_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod"
    event_type = "diagnostic_v4_6_1_holdout_candidate_manifest_identity_contract_bridge_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["holdout_candidate_manifest_identity_contract_bridge_only"] is True
    assert report["contract_bridge_gate"]["passed"] is True
    assert report["contract_bridge_gate"]["contract_hashes_match"] is True
    assert report["contract_bridge_gate"]["identity_probe_passed"] is True
    assert report["v4_6_ft_dry_run_opened"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["training_manifest_jsonl_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["holdout_candidate_manifest_identity_contract_bridge_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_2_ft_route_policy_fixture_contract_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_2_ft_route_policy_fixture_contract_nonprod"
    event_type = "diagnostic_v4_6_2_ft_route_policy_fixture_contract_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["ft_route_policy_fixture_contract_only"] is True
    assert report["fixture_contract_gate"]["fixture_contract_schema_check_passed"] is True
    assert report["fixture_contract_gate"]["dry_run_dataset_gate_passed"] is False
    assert report["fixture_contract_gate"]["dataset_export_gate_opened"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["prompt_payload_created"] is False
    assert report["raw_llm_response_payload_created"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["training_manifest_jsonl_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["ft_route_policy_fixture_contract_only"] is True
    assert event["fixture_contract_schema_check_passed"] is True
    assert event["dry_run_dataset_gate_passed"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["dataset_export_gate_opened"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_3_ft_a_prompt_policy_baseline_schema_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod"
    event_type = "diagnostic_v4_6_3_ft_a_prompt_policy_baseline_schema_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["ft_a_prompt_policy_baseline_schema_only"] is True
    assert report["prompt_policy_baseline_gate"]["prompt_policy_baseline_schema_check_passed"] is True
    assert report["prompt_policy_baseline_gate"]["dry_run_prompt_baseline_gate_passed"] is False
    assert report["prompt_policy_baseline_schema"]["raw_prompt_text_embedded"] is False
    assert report["prompt_policy_baseline_schema"]["prompt_payload_created"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["prompt_payload_created"] is False
    assert report["raw_llm_response_payload_created"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["training_manifest_jsonl_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["ft_a_prompt_policy_baseline_schema_only"] is True
    assert event["prompt_policy_baseline_schema_check_passed"] is True
    assert event["dry_run_prompt_baseline_gate_passed"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_4_ft_a_dry_run_input_manifest_validator_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod"
    event_type = "diagnostic_v4_6_4_ft_a_dry_run_input_manifest_validator_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["ft_a_dry_run_input_manifest_validator_only"] is True
    assert report["dry_run_input_manifest_gate"]["manifest_validator_schema_check_passed"] is True
    assert report["dry_run_input_manifest_gate"]["dry_run_input_manifest_gate_passed"] is False
    assert report["dry_run_input_manifest_contract"]["manifest_rows_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["prompt_payload_created"] is False
    assert report["prompt_manifest_created"] is False
    assert report["raw_llm_response_payload_created"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["prompt_manifest_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["training_manifest_jsonl_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["ft_a_dry_run_input_manifest_validator_only"] is True
    assert event["manifest_validator_schema_check_passed"] is True
    assert event["dry_run_input_manifest_gate_passed"] is False
    assert event["manifest_rows_exported"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_5_ft_a_dry_run_execution_plan_gate_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod"
    event_type = "diagnostic_v4_6_5_ft_a_dry_run_execution_plan_gate_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["ft_a_dry_run_execution_plan_gate_only"] is True
    assert report["dry_run_execution_plan_gate"]["dry_run_execution_plan_schema_check_passed"] is True
    assert report["dry_run_execution_plan_gate"]["dry_run_execution_plan_gate_passed"] is False
    assert report["dry_run_execution_plan_contract"]["dry_run_execution_plan_exported"] is False
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["prompt_payload_created"] is False
    assert report["prompt_manifest_created"] is False
    assert report["raw_llm_response_payload_created"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["dry_run_execution_plan_exported"] is False
    assert report["guardrails"]["dry_run_input_manifest_exported"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["prompt_manifest_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["training_manifest_jsonl_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["ft_a_dry_run_execution_plan_gate_only"] is True
    assert event["dry_run_execution_plan_schema_check_passed"] is True
    assert event["dry_run_execution_plan_gate_passed"] is False
    assert event["dry_run_execution_plan_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_2_xlsx_locator_v2_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod"
    event_type = "diagnostic_v4_2_xlsx_locator_v2_table_range_cell_structural_materialization_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v3_9_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert report["metrics"]["official_metric_input_rows"] == 0
    assert report["metrics"]["product_success_evidence_allowed"] is False
    assert report["metrics"]["promotion_evidence"] is False
    assert report["metrics"]["fine_tuning_executed"] is False
    assert report["metrics"]["workbook_disjoint_validation_rows"] == 0
    assert report["metrics"]["fresh_real_holdout_available"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["family_separated_xlsx_only"] is True
    assert report["guardrails"]["pdf_lane_excluded"] is True
    assert report["guardrails"]["text_lane_excluded"] is True
    assert report["guardrails"]["direct_normalized_value_query_matching_used"] is False
    assert report["guardrails"]["raw_answer_value_for_query_scoring_used"] is False
    assert report["guardrails"]["target_locator_used"] is False
    assert report["guardrails"]["gold_locator_used"] is False
    assert report["guardrails"]["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert report["guardrails"]["threshold_tuning"] is False
    assert report["guardrails"]["winner_selection"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["source_atom_registry_mutated"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["raw_answer_value_for_query_scoring_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is True
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["prompt_payload_created"] is False
    assert event["xlsx_locator_v2_manifest_jsonl_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["label_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["production_mutation"] is False
    assert event["db_or_production_namespace_written"] is False
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_3_pdf_file_identity_split_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod"
    event_type = "diagnostic_v4_3_pdf_file_identity_confidence_and_evidence_window_split_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert report["official_metric"] is False
    assert report["metrics"]["official_metric_input_rows"] == 0
    assert report["metrics"]["product_success_evidence_allowed"] is False
    assert report["metrics"]["promotion_evidence"] is False
    assert report["metrics"]["fine_tuning_executed"] is False
    assert report["metrics"]["source_document_disjoint_validation_rows"] == 0
    assert report["metrics"]["fresh_real_holdout_available"] is False
    assert report["metrics"]["pdf_file_identity_answer_window_kept_separate"] is True
    assert report["metrics"]["bbox_correctness_metric_computed"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["family_separated_pdf_only"] is True
    assert report["guardrails"]["xlsx_lane_excluded"] is True
    assert report["guardrails"]["text_lane_excluded"] is True
    assert report["guardrails"]["pdf_file_identity_answer_window_kept_separate"] is True
    assert report["guardrails"]["direct_normalized_value_query_matching_used"] is False
    assert report["guardrails"]["raw_answer_value_for_query_scoring_used"] is False
    assert report["guardrails"]["target_locator_used"] is False
    assert report["guardrails"]["gold_locator_used"] is False
    assert report["guardrails"]["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert report["guardrails"]["threshold_tuning"] is False
    assert report["guardrails"]["winner_selection"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["official_metric_lift"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["fine_tuning_readiness_only"] is True
    assert event["fine_tuning_started"] is False
    assert event["fine_tuning_executed"] is False
    assert event["source_atom_registry_mutated"] is False
    assert event["searchview_vector_payload_candidate_only"] is True
    assert event["source_atom_evidence_bundle_evidence_truth"] is True
    assert event["vector_payload_used_as_evidence_truth"] is False
    assert event["direct_normalized_value_query_matching_used"] is False
    assert event["raw_answer_value_for_query_scoring_used"] is False
    assert event["target_locator_used"] is False
    assert event["gold_locator_used"] is False
    assert event["expected_supporting_gold_text_used_for_retrieval_or_generation"] is False
    assert event["review_csv_created"] is False
    assert event["report_json_created"] is True
    assert event["summary_json_created"] is False
    assert event["per_run_markdown_created"] is False
    assert event["raw_llm_response_payload_created"] is False
    assert event["prompt_payload_created"] is False
    assert event["pdf_file_identity_split_manifest_jsonl_created"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["gold_mutation"] is False
    assert event["qrels_mutation"] is False
    assert event["label_mutation"] is False
    assert event["expected_answer_mutation"] is False
    assert event["supporting_evidence_mutation"] is False
    assert event["official_denominator_mutation"] is False
    assert event["production_mutation"] is False
    assert event["db_or_production_namespace_written"] is False
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_6_holdout_gap_blocker_ledger_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod"
    event_type = "diagnostic_v4_6_6_holdout_gap_and_dry_run_blocker_ledger_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["holdout_gap_and_dry_run_blocker_ledger_only"] is True
    assert report["holdout_gap_ledger"]["real_holdout_sufficient"] is False
    assert report["dry_run_blocker_ledger"]["all_non_gold_source_gates_passed"] is False
    assert report["candidate_manifest_exported"] is False
    assert report["dry_run_execution_plan_exported"] is False
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["prompt_payload_created"] is False
    assert report["prompt_manifest_created"] is False
    assert report["raw_llm_response_payload_created"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["candidate_manifest_exported"] is False
    assert report["guardrails"]["dry_run_execution_plan_exported"] is False
    assert report["guardrails"]["dry_run_input_manifest_exported"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["prompt_manifest_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False


def test_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod"
    event_type = "diagnostic_v4_6_7_holdout_candidate_runtime_gate_parity_bridge_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["holdout_candidate_runtime_gate_parity_bridge_only"] is True
    assert report["runtime_parity_probe_only"] is True
    assert report["runtime_gate_parity"]["all_parity_checks_passed"] is True
    assert report["real_holdout_sufficient"] is False
    assert report["candidate_manifest_exported"] is False
    assert report["candidate_manifest_jsonl_created"] is False
    assert report["candidate_validation_jsonl_created"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert report["dry_run_execution_plan_exported"] is False
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["prompt_payload_created"] is False
    assert report["prompt_manifest_created"] is False
    assert report["raw_llm_response_payload_created"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["candidate_manifest_exported"] is False
    assert report["guardrails"]["dry_run_execution_plan_exported"] is False
    assert report["guardrails"]["dry_run_input_manifest_exported"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["prompt_manifest_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["source_atom_evidence_bundle_evidence_truth"] is True
    assert report["guardrails"]["searchview_vector_payload_candidate_only"] is True
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert len(matches) == 1
    assert matches[0]["diagnostic_only"] is True
    assert matches[0]["all_parity_checks_passed"] is True
    assert matches[0]["official_metric_input_rows"] == 0
    assert matches[0]["promotion_evidence"] is False
    assert "prompt_manifest" not in report
    assert "per_query" not in report
    assert "raw_llm_response" not in report
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["holdout_candidate_runtime_gate_parity_bridge_only"] is True
    assert event["real_holdout_sufficient"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["all_parity_checks_passed"] is True
    assert event["dry_run_execution_plan_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_manifest_jsonl_created"] is False
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_8_runtime_readiness_dependency_freshness_gate_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod"
    event_type = "diagnostic_v4_6_8_runtime_readiness_dependency_freshness_gate_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["runtime_readiness_dependency_freshness_gate_only"] is True
    assert report["external_holdout_acquisition_requirements_packet_only"] is True
    assert report["dependency_freshness_gate"]["gate_passed"] is True
    assert report["dependency_freshness_gate"]["forbidden_surface_violation_count"] == 0
    assert report["dependency_freshness_gate"]["raw_source_identity_or_path_leak_count"] == 0
    assert report["real_holdout_sufficient"] is False
    assert report["candidate_manifest_exported"] is False
    assert report["candidate_manifest_jsonl_created"] is False
    assert report["candidate_validation_jsonl_created"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert report["dry_run_execution_plan_exported"] is False
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["runtime_readiness_dependency_freshness_gate_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_9_holdout_candidate_duplicate_hygiene_gate_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod"
    event_type = "diagnostic_v4_6_9_holdout_candidate_duplicate_hygiene_gate_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["holdout_candidate_duplicate_hygiene_gate_only"] is True
    assert report["duplicate_hygiene_gate"]["gate_passed"] is True
    assert report["duplicate_hygiene_gate"]["runtime_invalid_first_duplicate_rejected"] is True
    assert report["duplicate_hygiene_gate"]["script_invalid_first_duplicate_rejected"] is True
    assert report["real_holdout_sufficient"] is False
    assert report["candidate_manifest_exported"] is False
    assert report["candidate_manifest_jsonl_created"] is False
    assert report["candidate_validation_jsonl_created"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert report["dry_run_execution_plan_exported"] is False
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["holdout_candidate_duplicate_hygiene_gate_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_10_external_holdout_manifest_gate_replay_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod"
    event_type = "diagnostic_v4_6_10_external_holdout_candidate_manifest_gate_replay_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["external_holdout_candidate_manifest_gate_replay_only"] is True
    assert report["external_holdout_candidate_manifest_gate_replay"]["gate_passed"] is False
    assert report["external_holdout_candidate_manifest_gate_replay"]["candidate_manifest_present"] is False
    assert report["external_holdout_candidate_manifest_gate_replay"]["candidate_rows_replayed"] == 0
    assert report["official_metric_opening_preflight"]["gate_passed"] is False
    assert report["official_metric_opening_preflight"]["gate_opened"] is False
    assert report["official_metric_opening_preflight"]["missing_user_owned_input_count"] == 6
    assert report["official_metric_opening_preflight"]["official_metric_rows_authorized"] is False
    assert report["candidate_manifest_exported"] is False
    assert report["candidate_manifest_jsonl_created"] is False
    assert report["candidate_validation_jsonl_created"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert report["dry_run_execution_plan_exported"] is False
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["external_holdout_candidate_manifest_gate_replay_only"] is True
    assert event["gate_passed"] is False
    assert event["gate_opened"] is False
    assert event["candidate_manifest_present"] is False
    assert event["candidate_rows_replayed"] == 0
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_7_preofficial_external_holdout_registration_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod"
    event_type = "diagnostic_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["preofficial_external_holdout_candidate_manifest_registration_only"] is True
    assert report["registration_gate_passed"] is True
    assert report["candidate_manifest_available"] is True
    assert report["real_holdout_sufficient"] is False
    assert report["candidate_manifest_exported"] is False
    assert report["candidate_manifest_jsonl_created"] is False
    assert report["candidate_validation_jsonl_created"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert report["dry_run_execution_plan_exported"] is False
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["preofficial_external_holdout_candidate_manifest_registration_only"] is True
    assert event["registration_gate_passed"] is True
    assert event["candidate_manifest_available"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_11_ft_a_runtime_input_validation_route_parity_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod"
    event_type = "diagnostic_v4_6_11_ft_a_runtime_input_validation_route_parity_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["ft_a_runtime_input_validation_route_parity_only"] is True
    assert report["runtime_parity_probe_only"] is True
    assert report["ft_a_runtime_input_validation_route_parity"]["feature_flag_default_enabled"] is False
    assert report["ft_a_runtime_input_validation_route_parity"]["production_disabled_route_status_code"] == 404
    assert report["ft_a_runtime_input_validation_route_parity"]["script_runtime_counts_match"] is True
    assert report["ft_a_runtime_input_validation_route_parity"]["runtime_response_sanitized"] is True
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_runtime_request_body_embedded"] is False
    assert report["guardrails"]["raw_runtime_response_body_embedded"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["ft_a_runtime_input_validation_route_parity_only"] is True
    assert event["runtime_parity_probe_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    serialized = json.dumps({"report": report, "event": event}, ensure_ascii=False)
    for forbidden in (
        "이전 셀의 값을 설명해줘",
        "hidden prompt",
        "hidden response",
        "secret answer",
        "secret support",
        "pdf-source-identity",
        "D:/private",
        "row-ok",
        "query-ok",
        "per_query",
    ):
        assert forbidden not in serialized


def test_v4_6_12_external_holdout_runtime_replay_route_parity_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
    event_type = "diagnostic_v4_6_12_external_holdout_runtime_replay_route_parity_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["external_holdout_runtime_replay_route_parity_only"] is True
    assert report["runtime_parity_probe_only"] is True
    assert report["external_holdout_runtime_replay_route_parity"]["feature_flag_default_enabled"] is False
    assert report["external_holdout_runtime_replay_route_parity"]["production_disabled_route_status_code"] == 404
    assert report["external_holdout_runtime_replay_route_parity"]["route_response_sanitized"] is True
    assert report["external_holdout_runtime_replay_route_parity"]["route_candidate_counts_match_v4_6_10_replay"] is True
    assert report["candidate_manifest_exported"] is False
    assert report["candidate_manifest_jsonl_created"] is False
    assert report["candidate_validation_jsonl_created"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert report["dry_run_input_manifest_exported"] is False
    assert report["ft_route_policy_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["real_holdout_sufficient"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_dataset_exports_created"] == 0
    assert report["training_manifest_jsonl_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["single_report_artifact_contract"] is True
    assert report["review_csv_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_runtime_request_body_embedded"] is False
    assert report["guardrails"]["raw_runtime_response_body_embedded"] is False
    assert report["guardrails"]["raw_candidate_rows_embedded"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["external_holdout_runtime_replay_route_parity_only"] is True
    assert event["runtime_parity_probe_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["candidate_manifest_exported"] is False
    assert event["dry_run_input_manifest_exported"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    serialized = json.dumps({"report": report, "event": event}, ensure_ascii=False)
    for forbidden in (
        "pdf-v4612",
        "xlsx-v4612",
        "pdf-doc-v4612",
        "workbook-v4612",
        "hidden holdout prompt",
        "secret holdout answer",
        "D:/private",
        "candidate_manifest_path",
        "per_query",
    ):
        assert forbidden not in serialized


def test_v4_4_real_blind_ood_holdout_leakage_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod"
    event_type = "diagnostic_v4_4_real_blind_ood_holdout_and_leakage_audit_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["production_routing"] is False
    assert report["threshold_tuning"] is False
    assert report["winner_selection"] is False
    assert report["fine_tuning_started"] is False
    assert report["fine_tuning_executed"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["direct_normalized_answer_value_query_matching_used"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["real_holdout_available"] is False
    assert event["real_holdout_sufficient"] is False
    assert event["real_unseen_registry_counts"] == {
        "PDF_source_document_disjoint": 0,
        "XLSX_workbook_disjoint": 0,
    }
    assert event["leakage_excluded_count"] == 9
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_5_finetune_readiness_packet_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_5_finetune_readiness_packet_nonprod"
    event_type = "diagnostic_v4_5_finetune_readiness_packet_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["production_routing"] is False
    assert report["threshold_tuning"] is False
    assert report["winner_selection"] is False
    assert report["fine_tuning_readiness_only"] is True
    assert report["fine_tuning_started"] is False
    assert report["fine_tuning_executed"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["readiness_gates"]["split_quality_gate"]["passed"] is False
    assert report["readiness_gates"]["leakage_audit_gate"]["passed"] is True
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["direct_normalized_answer_value_query_matching_used"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["readiness_gate_passed"] is False
    assert event["split_quality_gate_passed"] is False
    assert event["leakage_audit_gate_passed"] is True
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_5_1_holdout_candidate_intake_gate_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_5_1_holdout_candidate_intake_gate_nonprod"
    event_type = "diagnostic_v4_5_1_holdout_candidate_intake_gate_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["holdout_candidate_intake_only"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["production_routing"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["v4_6_ft_dry_run_opened"] is False
    assert report["candidate_intake_gate"]["passed"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["direct_normalized_answer_value_query_matching_used"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["candidate_intake_gate_passed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["v4_6_ft_dry_run_opened"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_5_2_external_source_identity_audit_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod"
    event_type = "diagnostic_v4_5_2_external_holdout_candidate_source_identity_audit_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["external_holdout_candidate_source_identity_audit_only"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["production_routing"] is False
    assert report["real_holdout_available"] is False
    assert report["real_holdout_sufficient"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["v4_6_ft_dry_run_opened"] is False
    assert report["source_identity_audit_gate"]["passed"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert report["prior_identity_ledger_jsonl_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["direct_normalized_answer_value_query_matching_used"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["real_holdout_available"] is False
    assert event["real_holdout_sufficient"] is False
    assert event["source_identity_audit_gate_passed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["v4_6_ft_dry_run_opened"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_5_3_external_holdout_prior_identity_summary_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod"
    event_type = "diagnostic_v4_5_3_external_holdout_prior_source_identity_ledger_summary_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["prior_source_identity_ledger_summary_only"] is True
    assert report["prior_identity_collision_baseline_available"] is True
    assert report["raw_source_identity_values_embedded"] is False
    assert report["raw_local_path_values_exposed"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["production_routing"] is False
    assert report["real_holdout_available"] is False
    assert report["real_holdout_sufficient"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["v4_6_ft_dry_run_opened"] is False
    assert report["prior_identity_ledger_jsonl_created"] is False
    assert report["source_identity_audit_jsonl_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["source_atom_registry_mutated"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["direct_normalized_answer_value_query_matching_used"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["real_holdout_available"] is False
    assert event["real_holdout_sufficient"] is False
    assert event["source_identity_audit_gate_passed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["v4_6_ft_dry_run_opened"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_6_ft_route_policy_preflight_does_not_mutate_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_6_ft_route_policy_dry_run_preflight_nonprod"
    event_type = "diagnostic_v4_6_ft_route_policy_dry_run_preflight_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["ft_route_policy_dry_run_preflight_only"] is True
    assert report["v4_6_ft_dry_run_opened"] is False
    assert report["ft_route_policy_dry_run_executed"] is False
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["production_routing"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["training_job_created"] is False
    assert report["model_or_adapter_checkpoint_written"] is False
    assert report["guardrails"]["prompt_payload_created"] is False
    assert report["guardrails"]["raw_llm_response_payload_created"] is False
    assert report["guardrails"]["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["supporting_evidence_mutation"] is False
    assert report["guardrails"]["official_denominator_mutation"] is False
    assert report["guardrails"]["production_mutation"] is False
    assert report["guardrails"]["db_or_production_namespace_written"] is False
    assert report["guardrails"]["vector_payload_used_as_evidence_truth"] is False
    assert report["guardrails"]["raw_pdf_query_time_parsing"] is False
    assert report["guardrails"]["raw_xlsx_query_time_parsing"] is False
    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["ft_route_policy_dry_run_opened"] is False
    assert event["ft_route_policy_dry_run_executed"] is False
    assert event["fine_tuning_dataset_exports_created"] == 0
    assert event["training_job_created"] is False
    assert event["model_or_adapter_checkpoint_written"] is False
    assert event["protected_namespaces_touched"] == []
    assert event["artifact_paths"] == {"report_json": report_path.relative_to(ROOT).as_posix()}
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event


def test_v4_7_2_korean_review_packet_hydration_does_not_mutate_protected_or_promote_surfaces():
    run_id = "official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod"
    event_type = "diagnostic_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod"
    report_path = REPORT_DIR / "quality" / run_id / "report.json"
    require_v4_3_local_artifacts(STATUS_JSONL, report_path)

    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "ai/eval/eval_queries",
        "ai/eval/silver/answer_citation_silver_manifest_v1.json",
        "ai/eval/silver/answer_citation_silver_readiness_v1.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/build.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-official-denominator-v1/search_unit_manifest.jsonl",
        "ai/eval/indexes/rag-data-official-denominator-v1/faiss.index",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/build.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/ingest_manifest.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/source_inventory.json",
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/faiss.index",
        "ai/eval/source_registry/source_atom_registry_v1.jsonl",
        "ai/eval/source_registry/source_atom_registry_build.json",
        "ai/eval/source_registry/source_atom_registry_inventory.json",
        "ai/eval/source_registry/source_atom_registry_blocked.jsonl",
        "ai/eval/reports/rag-ingestion/baseline_v1.json",
        "ai/eval/reports/rag-ingestion/metric_input_v1.json",
        "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
        "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
    )

    for protected_path in protected_paths:
        unstaged = subprocess.run(
            ["git", "diff", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", protected_path],
            cwd=ROOT,
            check=False,
        )
        assert unstaged.returncode == 0, protected_path
        assert staged.returncode == 0, protected_path

    report = read_json(report_path)
    events = [json.loads(line) for line in STATUS_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("event_type") == event_type
    ]

    assert report["diagnostic_only"] is True
    assert report["human_review_only"] is True
    assert report["source_grounded_query_review_packet_hydration_only"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["promotion_evidence"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["ft_a_execution"] is False
    assert report["fine_tuning"] is False
    assert report["qrels_mutation"] is False
    assert report["gold_mutation"] is False
    assert report["label_mutation"] is False
    assert report["training_dataset_created"] is False
    assert report["candidate_manifest_jsonl_created"] is False
    assert report["qrels_jsonl_created"] is False
    assert report["gold_jsonl_created"] is False
    assert report["labels_jsonl_created"] is False
    assert report["answer_key_jsonl_created"] is False
    assert report["evidence_key_jsonl_created"] is False
    assert report["training_manifest_jsonl_created"] is False
    assert report["prompt_manifest_jsonl_created"] is False
    assert report["raw_response_payload_jsonl_created"] is False
    assert report["hydrated_packet_row_count"] == 204
    assert report["hydrated_packet_non_empty_query_count"] == 204
    assert report["extraction_failed_row_count"] == 0
    assert "prompt_payload" not in report
    assert "raw_llm_response" not in report
    assert "target_locator" not in report
    assert "gold_locator" not in report

    assert len(matches) == 1
    event = matches[0]
    assert event["schema_version"] == f"{run_id}_status_event_v1"
    assert event["diagnostic_only"] is True
    assert event["human_review_only"] is True
    assert event["official_metric"] is False
    assert event["official_metric_input_rows"] == 0
    assert event["v4_7_official_metric_gate_opened"] is False
    assert event["promotion_evidence"] is False
    assert event["product_success_evidence_allowed"] is False
    assert event["ft_a_execution"] is False
    assert event["fine_tuning"] is False
    assert event["live_db_index_cache_readiness"] is False
    assert event["qrels_mutation"] is False
    assert event["gold_mutation"] is False
    assert event["label_mutation"] is False
    assert event["training_dataset_created"] is False
    assert event["hydrated_packet_row_count"] == 204
    assert event["hydrated_packet_non_empty_query_count"] == 204
    assert event["extraction_failed_row_count"] == 0
    assert event["artifact_paths"]["report_json"] == report_path.relative_to(ROOT).as_posix()
    assert event["artifact_sha256"]["report_json_sha256"] == sha256_file(report_path)
    assert "prompt_manifest" not in event
    assert "per_query" not in event
    assert "raw_llm_response" not in event
