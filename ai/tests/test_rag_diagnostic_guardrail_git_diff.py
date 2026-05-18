from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTECTED_PATHS = (
    "ai/eval/eval_queries/official_denominator_registry.json",
    "ai/eval/eval_queries/gold_queries_pdf_question_gold_v2.csv",
    "ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv",
    "ai/eval/eval_queries/gold_queries_xlsx_question_gold_v2.csv",
    "ai/eval/reports/rag-ingestion/baseline_v1.json",
    "ai/eval/reports/rag-ingestion/scorer_v1.jsonl",
    "ai/eval/reports/rag-ingestion/metric_input_v1.json",
    "ai/eval/reports/rag-ingestion/smoke_v1.json",
    "ai/eval/reports/rag-ingestion/xlsx_candidate_v1.jsonl",
    "ai/eval/reports/rag-ingestion/pdf_candidate_v1.jsonl",
)


def test_residual_audit_does_not_mutate_protected_artifacts():
    for protected_path in PROTECTED_PATHS:
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
