from __future__ import annotations

import subprocess
import json
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
