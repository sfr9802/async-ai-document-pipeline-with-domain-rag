from __future__ import annotations

import sys
import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai"


def _require_ai_on_path() -> None:
    ai_path = str(AI_ROOT)
    if ai_path not in sys.path:
        sys.path.insert(0, ai_path)


def test_experiment_dependency_extra_mirrors_requirements_dev() -> None:
    pyproject = tomllib.loads((AI_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    experiment_extra = set(pyproject["project"]["optional-dependencies"]["experiments"])
    requirements_dev = set()
    for raw_line in (AI_ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            requirements_dev.add(line)

    assert requirements_dev <= experiment_extra


def test_active_experiment_template_is_diagnostic_only_for_legacy_tune_runner() -> None:
    _require_ai_on_path()
    from scripts.tune import (
        active_config_fail_closed_reason,
        load_active_config,
        tuning_sweep_disabled_reason,
    )

    config = load_active_config(AI_ROOT / "eval" / "experiments" / "active.yaml")

    assert active_config_fail_closed_reason(config) is None
    assert tuning_sweep_disabled_reason(config) == (
        "_meta.execution_policy.allow_tuning_sweep=false"
    )


def test_experiment_gitignore_keeps_reproducibility_receipts_trackable() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        "!ai/eval/experiments/rounds/*.json",
        "!ai/eval/experiments/rounds/*.md",
        "!ai/eval/experiments/studies/**/FINAL_BEST.json",
        "!ai/eval/experiments/studies/**/STUDY_SUMMARY.md",
        "!ai/eval/experiments/studies/**/summary.md",
        "ai/eval/experiments/run_output/*",
        "!ai/eval/experiments/run_output/.gitkeep",
    ):
        assert pattern in gitignore

    assert _git_ignore_decision("ai/eval/experiments/run_output/.gitkeep") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/run_output/study_bundle.json") == "ignored"
    assert _git_ignore_decision("ai/eval/experiments/run_output/llm_input.md") == "ignored"
    assert _git_ignore_decision("ai/eval/experiments/rounds/round_01_config.json") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/rounds/round_01_analysis.md") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/FINAL_BEST.json") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/STUDY_SUMMARY.md") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/summary.md") == "trackable"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/study.db") == "ignored"
    assert _git_ignore_decision("ai/eval/experiments/studies/demo/plots/plot.png") == "ignored"


def test_report_namespace_policy_centralizes_scattered_artifact_roots() -> None:
    from ai.eval import report_paths

    namespaces = {namespace.name: namespace for namespace in report_paths.REPORT_NAMESPACES}

    assert report_paths.PUBLIC_REPORT_ROOT == ROOT / "reports"
    assert report_paths.ACTUAL_RAG_REPORT_ROOT == ROOT / "reports" / "rag_eval"
    assert report_paths.LEGACY_RAG_INGESTION_REPORT_ROOT == ROOT / "reports" / "rag_eval" / "rag-ingestion"
    assert report_paths.LEGACY_RAG_INGESTION_STATUS_JSONL == (
        ROOT / "reports" / "rag_eval" / "rag-ingestion" / "status.jsonl"
    )
    assert not (ROOT / "ai" / "eval" / "reports" / "rag-ingestion").exists()
    assert report_paths.RAG_INGESTION_PROGRESS_DOC == ROOT / "docs" / "rag-ingestion-progress.md"
    assert report_paths.RAG_INGESTION_MEASUREMENTS_DOC == ROOT / "docs" / "rag-ingestion-measurements.md"
    assert report_paths.RAG_INGESTION_TRIAGE_DOC == ROOT / "docs" / "rag-ingestion-triage.md"

    assert namespaces["public_portfolio_reports"].git_policy == "tracked allowlist only"
    assert namespaces["actual_rag_reports"].git_policy == "ignored generated machine artifacts"
    assert namespaces["legacy_rag_ingestion_reports"].git_policy == "ignored generated machine artifacts"
    assert namespaces["rag_ingestion_ledgers"].git_policy == "tracked human-facing ledgers"
    assert report_paths.dataset_latest_pointer("text-gold") == ROOT / "reports" / "rag_eval" / "latest_text_gold.json"

    assert _git_ignore_decision("reports/portfolio_agentops_report.md") == "trackable"
    assert _git_ignore_decision("reports/agentops_sample_trace.json") == "trackable"
    assert _git_ignore_decision("reports/rag_eval/latest.json") == "ignored"
    assert _git_ignore_decision("reports/rag_eval/example/report.json") == "ignored"
    assert _git_ignore_decision("reports/rag_eval/rag-ingestion/runs/example/report.json") == "ignored"
    assert _git_ignore_decision("docs/rag-ingestion-progress.md") == "trackable"
    assert _git_ignore_decision("docs/rag-ingestion-measurements.md") == "trackable"
    assert _git_ignore_decision("docs/rag-ingestion-triage.md") == "trackable"


def test_active_report_entrypoints_use_central_report_path_contract() -> None:
    for rel_path in (
        "ai/eval/actual_rag_eval.py",
        "ai/eval/rag_eval_registry.py",
        "ai/scripts/rag_eval.py",
        "ai/scripts/rag_weaviate_source_atom_index.py",
    ):
        text = (ROOT / rel_path).read_text(encoding="utf-8")
        assert "ai.eval.report_paths" in text, rel_path


def _git_ignore_decision(repo_relative_path: str) -> str:
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--", repo_relative_path],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 1:
        return "trackable"
    assert result.returncode == 0, result.stderr

    pattern_source = result.stdout.split("\t", 1)[0]
    pattern = pattern_source.split(":", 2)[2]
    if pattern.startswith("!"):
        return "trackable"
    return "ignored"
