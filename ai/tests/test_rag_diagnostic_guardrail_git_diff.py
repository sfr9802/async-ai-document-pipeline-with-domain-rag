from __future__ import annotations

import subprocess
import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
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
STATUS_JSONL = ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "status.jsonl"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    summary = json.loads(V3_1_9_SUMMARY.read_text(encoding="utf-8"))
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
    summary = json.loads(V3_2_3_SUMMARY.read_text(encoding="utf-8"))
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
    summary = json.loads(V3_2_4_SUMMARY.read_text(encoding="utf-8"))
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
    summary = json.loads(V3_2_5_SUMMARY.read_text(encoding="utf-8"))
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
    summary = json.loads(V3_2_6_SUMMARY.read_text(encoding="utf-8"))
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
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    protected_paths = (
        *STRICT_PROTECTED_PATHS,
        *V3_1_9_ALLOWED_POLICY_APPLICATION_PATHS,
        "README.md",
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
        "README.md",
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
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
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
        "README.md",
        "docs/rag-ingestion-triage.md",
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
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
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
        "README.md",
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
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["recommended_repair_queue_count"] == 0:
        protected_paths = (*protected_paths, "docs/rag-ingestion-triage.md")

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
