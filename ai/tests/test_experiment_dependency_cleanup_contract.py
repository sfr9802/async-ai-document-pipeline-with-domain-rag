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
    assert not hasattr(report_paths, "RAG_INGESTION_PROGRESS_DOC")
    assert not hasattr(report_paths, "RAG_INGESTION_MEASUREMENTS_DOC")
    assert not hasattr(report_paths, "RAG_INGESTION_TRIAGE_DOC")

    assert namespaces["public_portfolio_reports"].git_policy == "tracked allowlist only"
    assert namespaces["actual_rag_reports"].git_policy == "ignored generated machine artifacts"
    assert namespaces["legacy_rag_ingestion_reports"].git_policy == "ignored generated machine artifacts"
    assert namespaces["rag_ingestion_ledgers"].git_policy == "ignored local handoff notes"
    assert namespaces["rag_ingestion_ledgers"].root == report_paths.LEGACY_RAG_INGESTION_REPORT_ROOT
    assert "not execution source of truth" in namespaces["rag_ingestion_ledgers"].role
    assert report_paths.dataset_latest_pointer("text-gold") == ROOT / "reports" / "rag_eval" / "latest_text_gold.json"

    assert _git_ignore_decision("reports/portfolio_agentops_report.md") == "trackable"
    assert _git_ignore_decision("reports/agentops_sample_trace.json") == "trackable"
    assert _git_ignore_decision("reports/rag_eval/latest.json") == "ignored"
    assert _git_ignore_decision("reports/rag_eval/example/report.json") == "ignored"
    assert _git_ignore_decision("reports/rag_eval/rag-ingestion/runs/example/report.json") == "ignored"
    assert _git_ignore_decision("docs/rag-ingestion-progress.md") == "ignored"
    assert _git_ignore_decision("docs/rag-ingestion-measurements.md") == "ignored"
    assert _git_ignore_decision("docs/rag-ingestion-triage.md") == "ignored"


def test_active_report_entrypoints_use_central_report_path_contract() -> None:
    for rel_path in (
        "ai/eval/actual_rag_core_base.py",
        "ai/eval/rag_eval_registry.py",
        "ai/scripts/rag_eval.py",
        "ai/scripts/rag_weaviate_source_atom_index.py",
    ):
        text = (ROOT / rel_path).read_text(encoding="utf-8")
        assert "ai.eval.report_paths" in text, rel_path


def test_active_shared_source_does_not_depend_on_ignored_docs_tree() -> None:
    """Public-source code must not depend on ignored local docs artifacts."""
    active_shared_paths = (
        "ai/eval/report_paths.py",
        "ai/scripts/rag_eval.py",
        "ai/app/capabilities/multimodal/__init__.py",
        "ai/app/capabilities/multimodal/capability.py",
        "ai/app/capabilities/trace.py",
        "ai/eval/experiment_runner/__init__.py",
        "ai/eval/experiment_runner/config.py",
        "ai/eval/experiment_runner/metadata.py",
        "ai/eval/experiment_runner/runner.py",
        "ai/eval/experiment_runner/main.py",
        "ai/eval/experiment_runner/actual_rag.py",
        "ai/eval/actual_rag_dataset.py",
        "ai/eval/actual_rag_agentic_xlsx.py",
        "ai/eval/actual_rag_judging.py",
        "ai/eval/actual_rag_core_base.py",
        "ai/eval/actual_rag_core_xlsx.py",
        "ai/eval/actual_rag_core_quality.py",
        "ai/eval/actual_rag_runner.py",
        "ai/eval/actual_rag_cli.py",
        "ai/eval/xlsx_locator_run_store.py",
        "ai/eval/rag_v69_answer_quality_gate_packet_nonprod.py",
        "ai/eval/rag_v70_e2e_eval_architecture_closeout_nonprod.py",
        "ai/eval/rag_v701_premature_closeout_audit_and_v64_recovery_nonprod.py",
    )

    for rel_path in active_shared_paths:
        text = (ROOT / rel_path).read_text(encoding="utf-8")
        assert "docs/" not in text, rel_path
        assert "docs\\" not in text, rel_path
        assert "import docs" not in text, rel_path
        assert "from docs" not in text, rel_path


def test_current_adjacent_write_branches_emit_worker_handoff_before_status() -> None:
    """Runner --write must preserve worker-authored docs without writing docs/ directly."""
    text = (ROOT / "ai" / "scripts" / "rag_eval.py").read_text(encoding="utf-8")
    for run_key, module_alias in (
        ("v6_9_answer_quality_gate_packet_nonprod", "v69"),
        ("v7_0_e2e_eval_architecture_closeout_nonprod", "v70"),
        ("v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod", "v701"),
    ):
        branch_start = text.index(f'elif run_key == "{run_key}":')
        next_branch = text.find("        elif run_key ==", branch_start + 1)
        branch = text[branch_start:] if next_branch == -1 else text[branch_start:next_branch]

        write_idx = branch.index(f"{module_alias}.write_report_bundle")
        check_idx = branch.index(f"{module_alias}.check_report(report, root=ROOT)", write_idx)
        handoff_idx = branch.index(f"{module_alias}.update_docs(ROOT, report)", check_idx)
        status_idx = branch.index(f"{module_alias}.append_status", handoff_idx)
        assert write_idx < check_idx < handoff_idx < status_idx, run_key


def test_new_experiments_are_routed_through_experiment_runner_contract() -> None:
    """Future experiments should start from a small runner instead of growing monoliths."""
    expected_files = (
        "ai/eval/experiment_runner/__init__.py",
        "ai/eval/experiment_runner/config.py",
        "ai/eval/experiment_runner/metadata.py",
        "ai/eval/experiment_runner/runner.py",
        "ai/eval/experiment_runner/main.py",
        "ai/eval/experiment_runner/actual_rag.py",
    )
    for rel_path in expected_files:
        assert (ROOT / rel_path).is_file(), rel_path
        assert _line_count(ROOT / rel_path) < 500, rel_path

    eval_readme = (ROOT / "ai" / "eval" / "README.md").read_text(encoding="utf-8")
    scripts_readme = (ROOT / "ai" / "scripts" / "README.md").read_text(encoding="utf-8")

    assert "python -m ai.eval.experiment_runner.main" in eval_readme
    assert "python -m ai.eval.experiment_runner.main" in scripts_readme
    assert "--dry-run" in scripts_readme
    assert "legacy-compatible backend" in eval_readme
    assert "backend modules" in eval_readme
    assert "using a backend" in scripts_readme
    assert "ai/eval/actual_rag_dataset.py" in scripts_readme
    assert "ai/eval/actual_rag_agentic_xlsx.py" in scripts_readme
    assert "ai/eval/actual_rag_judging.py" in scripts_readme
    assert "ai/eval/xlsx_locator_run_store.py" in scripts_readme
    assert "explicit cleanup targets" in scripts_readme
    assert "ai/eval/actual_rag_eval.py" in scripts_readme
    assert "rag_official_answer_citation_agentic_loop_run_v1.py" not in scripts_readme


def test_legacy_experiment_script_families_are_removed_from_source_tree() -> None:
    """Old one-off experiment versions should not stay as executable source defaults."""
    removed_globs = (
        "ai/scripts/rag_v3_*.py",
        "ai/scripts/rag_v4_*.py",
        "ai/scripts/run_phase7*.py",
        "ai/scripts/build_phase7*.py",
        "ai/scripts/*phase7*.py",
    )
    removed_paths = {
        "ai/scripts/rag_official_answer_citation_agentic_loop_run_v1.py",
        "ai/scripts/rag_pdf_gold_question_candidate_generation_v1.py",
        "ai/scripts/rag_pdf_strict_silver_generation.py",
        "ai/scripts/rag_xlsx_gold_question_candidate_generation_v1.py",
        "ai/scripts/rag_xlsx_silver_generation.py",
        "ai/scripts/rag_xlsx_strict_silver_generation.py",
        "ai/scripts/rag_xlsx_pdf_agentic_route_loop_diagnostic.py",
        "ai/scripts/rag_xlsx_pdf_route_trace_diagnostic.py",
        "ai/scripts/select_gold_seed_50_from_silver.py",
        "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
        "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py",
        "ai/tests/test_rag_source_bound_official_denominator_index.py",
        "ai/tests/test_rag_eval_v477_archive_aware_short_key_contract.py",
    }

    assert (ROOT / "ai" / "scripts" / "rag_eval.py").is_file()
    assert (ROOT / "ai" / "eval" / "experiment_runner" / "main.py").is_file()
    for pattern in removed_globs:
        assert not list(ROOT.glob(pattern)), pattern
    for rel_path in removed_paths:
        assert not (ROOT / rel_path).exists(), rel_path


def test_no_new_giant_experiment_python_modules_are_introduced() -> None:
    """Experiment code should stay backend-sized instead of preserving monoliths."""
    allowed_existing_monoliths: set[str] = set()
    candidate_roots = (ROOT / "ai" / "eval", ROOT / "ai" / "scripts", ROOT / "ai" / "tests")
    for root in candidate_roots:
        for path in root.rglob("*.py"):
            rel_path = path.relative_to(ROOT).as_posix()
            line_count = _line_count(path)
            if line_count >= 10_000:
                assert rel_path in allowed_existing_monoliths, f"{rel_path} has {line_count} lines"


def test_actual_rag_experiment_backend_is_split_into_focused_modules() -> None:
    """The direct actual-RAG CLI remains compatible while implementation code is split."""
    from ai.eval import actual_rag_cli
    from ai.eval import actual_rag_eval

    assert actual_rag_eval.build_parser() is not None
    assert actual_rag_eval.main is not actual_rag_cli.main
    assert actual_rag_eval.build_parser is not actual_rag_cli.build_parser
    assert _line_count(ROOT / "ai" / "eval" / "actual_rag_cli.py") < 800
    assert _line_count(ROOT / "ai" / "eval" / "actual_rag_eval.py") < 10_000


def test_xlsx_locator_run_store_is_extracted_from_actual_rag_monolith() -> None:
    """RunStore records should live in a focused module while old imports keep working."""
    from ai.eval import actual_rag_eval
    from ai.eval import xlsx_locator_run_store

    exported_names = (
        "XlsxLocatorToolUseRecord",
        "XlsxLocatorEvidenceCandidateRecord",
        "XlsxLocatorGateDeltaRecord",
        "XlsxLocatorGuardrailRecord",
        "XlsxLocatorRunRecord",
    )
    for name in exported_names:
        assert getattr(actual_rag_eval, name) is getattr(xlsx_locator_run_store, name)

    assert issubclass(actual_rag_eval.XlsxLocatorRunStore, xlsx_locator_run_store.XlsxLocatorRunStore)
    assert _line_count(ROOT / "ai" / "eval" / "xlsx_locator_run_store.py") < 1_000
    assert _line_count(ROOT / "ai" / "eval" / "actual_rag_eval.py") < 25_900


def test_actual_rag_dataset_loader_is_extracted_from_actual_rag_monolith() -> None:
    """Dataset schema and loading belong to a focused backend module."""
    from ai.eval import actual_rag_dataset
    from ai.eval import actual_rag_eval

    exported_names = (
        "DatasetSchemaError",
        "ExpectedEvidence",
        "EvalItem",
        "load_eval_dataset",
    )
    for name in exported_names:
        assert getattr(actual_rag_eval, name) is getattr(actual_rag_dataset, name)

    assert _line_count(ROOT / "ai" / "eval" / "actual_rag_dataset.py") < 500
    assert _line_count(ROOT / "ai" / "eval" / "actual_rag_eval.py") < 25_500


def test_actual_rag_judging_is_extracted_from_actual_rag_monolith() -> None:
    """Answer normalization, abstention, and heuristic judging live in a backend module."""
    from ai.eval import actual_rag_eval
    from ai.eval import actual_rag_judging

    exported_names = (
        "DEFAULT_ABSTENTION_PHRASES",
        "GENERIC_ANCHOR_STOPWORDS",
        "KOREAN_GENERIC_SUFFIXES",
        "normalize_answer_text",
        "answer_correct",
        "abstains",
        "_candidate_anchors",
        "_anchor_in_text",
        "_numeric_or_date_anchors",
        "heuristic_judge_answer",
        "HeuristicJudgeAdapter",
    )
    for name in exported_names:
        assert getattr(actual_rag_eval, name) is getattr(actual_rag_judging, name)

    assert _line_count(ROOT / "ai" / "eval" / "actual_rag_judging.py") < 350
    assert _line_count(ROOT / "ai" / "eval" / "actual_rag_eval.py") < 25_300


def test_actual_rag_agentic_xlsx_taxonomy_is_extracted_from_actual_rag_monolith() -> None:
    """Agentic XLSX taxonomy/verifier records belong to a focused backend module."""
    from ai.eval import actual_rag_agentic_xlsx
    from ai.eval import actual_rag_eval

    exported_names = (
        "AGENTIC_XLSX_QUERY_ANCHOR_TAXONOMY_SCHEMA_VERSION",
        "AGENTIC_XLSX_PROTECTED_ANCHOR_VERIFIER_SCHEMA_VERSION",
        "AGENTIC_XLSX_ANCHOR_TAXONOMY_CATEGORIES",
        "AgenticXlsxQueryAnchorTaxonomyRecord",
        "AgenticXlsxProtectedAnchorVerifierRecord",
        "agentic_xlsx_query_anchor_taxonomy_tool",
        "agentic_xlsx_protected_anchor_verifier_tool",
        "validate_agentic_xlsx_query_anchor_taxonomy_output",
        "validate_agentic_xlsx_protected_anchor_verifier_output",
    )
    for name in exported_names:
        assert getattr(actual_rag_eval, name) is getattr(actual_rag_agentic_xlsx, name)

    assert _line_count(ROOT / "ai" / "eval" / "actual_rag_agentic_xlsx.py") < 500
    assert _line_count(ROOT / "ai" / "eval" / "actual_rag_eval.py") < 25_100


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


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
