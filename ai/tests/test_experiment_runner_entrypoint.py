from __future__ import annotations

from dataclasses import dataclass, replace
import json
from io import StringIO
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_experiment_config_merges_cli_env_and_redacts_unlisted_env() -> None:
    from ai.eval.experiment_runner.config import build_experiment_config

    config = build_experiment_config(
        [
            "--experiment",
            "actual-rag",
            "--run-id",
            "cli-run",
            "--output-mode",
            "report-json",
        ],
        environ={
            "RAG_EXPERIMENT_RUN_ID": "env-run",
            "RAG_EXPERIMENT_PROFILE": "weaviate",
            "RAG_EXPERIMENT_REPORT_ROOT": "reports/rag_eval/custom",
            "OPENAI_API_KEY": "must-not-leak",
        },
        repo_root=ROOT,
    )

    assert config.experiment == "actual-rag"
    assert config.run_id == "cli-run"
    assert config.output_mode == "report-json"
    assert config.profile == "weaviate"
    assert config.report_root == ROOT / "reports" / "rag_eval" / "custom"
    assert config.observed_env == {
        "RAG_EXPERIMENT_PROFILE": "weaviate",
        "RAG_EXPERIMENT_REPORT_ROOT": "reports/rag_eval/custom",
        "RAG_EXPERIMENT_RUN_ID": "env-run",
    }


def test_experiment_config_rejects_invalid_env_output_mode() -> None:
    from ai.eval.experiment_runner.config import build_experiment_config

    with pytest.raises(ValueError, match="RAG_EXPERIMENT_OUTPUT_MODE"):
        build_experiment_config(
            ["--experiment", "actual-rag", "--run-id", "bad-env-run"],
            environ={"RAG_EXPERIMENT_OUTPUT_MODE": "latest"},
            repo_root=ROOT,
        )


@pytest.mark.parametrize(
    "bad_run_id",
    [
        "..",
        "../escape",
        "nested/run",
        r"nested\run",
        "safe..bad",
        "C:escape",
        str(ROOT / "reports" / "rag_eval" / "escape"),
    ],
)
def test_experiment_config_rejects_path_like_run_id(bad_run_id: str) -> None:
    from ai.eval.experiment_runner.config import build_experiment_config

    with pytest.raises(ValueError, match="RAG_EXPERIMENT_RUN_ID"):
        build_experiment_config(
            ["--experiment", "actual-rag", "--run-id", bad_run_id, "--dry-run"],
            environ={},
            repo_root=ROOT,
        )


@pytest.mark.parametrize(
    ("argv", "environ"),
    [
        (
            ["--experiment", "actual-rag", "--run-id", "bad-sqlite", "--output-mode", "run-sqlite"],
            {},
        ),
        (
            ["--experiment", "actual-rag", "--run-id", "bad-sqlite"],
            {"RAG_EXPERIMENT_OUTPUT_MODE": "run-sqlite"},
        ),
    ],
)
def test_experiment_config_rejects_unwired_run_sqlite_output_mode(
    argv: list[str], environ: dict[str, str]
) -> None:
    from ai.eval.experiment_runner.config import build_experiment_config

    with pytest.raises(ValueError, match="RAG_EXPERIMENT_OUTPUT_MODE"):
        build_experiment_config(argv, environ=environ, repo_root=ROOT)


def test_dry_run_metadata_does_not_invoke_backend_or_leak_secret_env() -> None:
    from ai.eval.experiment_runner.config import build_experiment_config
    from ai.eval.experiment_runner.runner import run_experiment

    config = build_experiment_config(
        ["--experiment", "actual-rag", "--run-id", "dry-run-01", "--dry-run"],
        environ={
            "RAG_EXPERIMENT_PROFILE": "local",
            "OPENAI_API_KEY": "must-not-leak",
        },
        repo_root=ROOT,
    )
    calls: list[object] = []

    result = run_experiment(
        config,
        argv=["--experiment", "actual-rag", "--run-id", "dry-run-01", "--dry-run"],
        environ={"RAG_EXPERIMENT_PROFILE": "local", "OPENAI_API_KEY": "must-not-leak"},
        backend=lambda received: calls.append(received),
    )

    assert calls == []
    assert result["schema_version"] == "experiment_runner.run_metadata.v1"
    assert result["experiment"] == "actual-rag"
    assert result["run_id"] == "dry-run-01"
    assert result["output_mode"] == "dry-run"
    assert result["backend_invoked"] is False
    assert result["observed_env"] == {"RAG_EXPERIMENT_PROFILE": "local"}
    assert "must-not-leak" not in json.dumps(result, ensure_ascii=False)


def test_dry_run_metadata_redacts_path_like_argv_and_env_values() -> None:
    from ai.eval.experiment_runner.config import build_experiment_config
    from ai.eval.experiment_runner.runner import run_experiment

    dataset_path = ROOT / "ai" / "tests" / "fixtures" / "demo_eval.jsonl"
    context_path = ROOT / "ai" / "tests" / "fixtures" / "context.jsonl"
    outside_report_root = ROOT.parent / "private-reports"
    outside_output_dir = ROOT.parent / "private-output"
    argv = [
        "--experiment",
        "actual-rag",
        "--run-id",
        "path-redaction-run",
        "--dry-run",
        "--dataset",
        str(dataset_path),
        f"--context-jsonl={context_path}",
        "--report-root",
        str(outside_report_root),
    ]
    environ = {
        "RAG_EXPERIMENT_DATASET": str(dataset_path),
        "RAG_EXPERIMENT_CONTEXT_JSONL": str(context_path),
        "RAG_EXPERIMENT_OUTPUT_DIR": str(outside_output_dir),
        "RAG_EXPERIMENT_REPORT_ROOT": str(outside_report_root),
    }
    config = build_experiment_config(argv, environ=environ, repo_root=ROOT)

    result = run_experiment(
        config,
        argv=argv,
        environ=environ,
        backend=lambda received: {"unexpected": received.run_id},
    )

    assert result["argv"] == [
        "--experiment",
        "actual-rag",
        "--run-id",
        "path-redaction-run",
        "--dry-run",
        "--dataset",
        "ai/tests/fixtures/demo_eval.jsonl",
        "--context-jsonl=ai/tests/fixtures/context.jsonl",
        "--report-root",
        "<redacted:path>",
    ]
    assert result["report_root"] == "<redacted:path>"
    assert result["observed_env"]["RAG_EXPERIMENT_DATASET"] == "ai/tests/fixtures/demo_eval.jsonl"
    assert result["observed_env"]["RAG_EXPERIMENT_CONTEXT_JSONL"] == "ai/tests/fixtures/context.jsonl"
    assert result["observed_env"]["RAG_EXPERIMENT_OUTPUT_DIR"] == "<redacted:path>"
    assert result["observed_env"]["RAG_EXPERIMENT_REPORT_ROOT"] == "<redacted:path>"
    serialized = json.dumps(result, ensure_ascii=False)
    assert ROOT.name not in serialized
    assert "private-reports" not in serialized
    assert "private-output" not in serialized


def test_report_json_mode_dispatches_backend_and_preserves_metadata() -> None:
    from ai.eval.experiment_runner.config import build_experiment_config
    from ai.eval.experiment_runner.runner import run_experiment

    config = build_experiment_config(
        ["--experiment", "actual-rag", "--run-id", "report-run", "--output-mode", "report-json"],
        environ={},
        repo_root=ROOT,
    )
    calls: list[str] = []

    result = run_experiment(
        config,
        argv=["--experiment", "actual-rag", "--run-id", "report-run", "--output-mode", "report-json"],
        environ={},
        backend=lambda received: calls.append(received.run_id) or {"report_json": "reports/rag_eval/example/report.json"},
    )

    assert calls == ["report-run"]
    assert result["backend_invoked"] is True
    assert result["backend_result"] == {"report_json": "reports/rag_eval/example/report.json"}
    assert result["metadata"]["run_id"] == "report-run"


def test_experiment_runner_main_prints_dry_run_metadata_json() -> None:
    from ai.eval.experiment_runner.main import main

    stdout = StringIO()

    exit_code = main(
        ["--experiment", "actual-rag", "--run-id", "cli-dry-run", "--dry-run"],
        environ={"RAG_EXPERIMENT_PROFILE": "smoke"},
        stdout=stdout,
        repo_root=ROOT,
    )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["run_id"] == "cli-dry-run"
    assert payload["output_mode"] == "dry-run"
    assert payload["backend_invoked"] is False


def test_actual_rag_adapter_maps_runner_config_to_monolith_boundary(monkeypatch) -> None:
    from ai.eval import actual_rag_eval
    from ai.eval.experiment_runner.actual_rag import run_actual_rag_experiment
    from ai.eval.experiment_runner.config import build_experiment_config

    config = build_experiment_config(
        [
            "--experiment",
            "actual-rag",
            "--run-id",
            "adapter-run",
            "--output-mode",
            "report-json",
            "--dataset",
            "ai/tests/fixtures/demo_eval.jsonl",
            "--index",
            "source-native",
            "--top-k",
            "3",
        ],
        environ={},
        repo_root=ROOT,
    )
    seen: dict[str, object] = {}

    def fake_run_eval_from_paths(**kwargs):
        seen.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(actual_rag_eval, "run_eval_from_paths", fake_run_eval_from_paths)

    assert run_actual_rag_experiment(config) == {"ok": True}
    assert seen["dataset_path"] == ROOT / "ai" / "tests" / "fixtures" / "demo_eval.jsonl"
    assert seen["output_dir"] == ROOT / "reports" / "rag_eval" / "adapter-run"
    assert seen["report_root"] == ROOT / "reports" / "rag_eval"
    assert seen["run_id"] == "adapter-run"
    assert seen["index"] == "source-native"
    assert seen["top_k"] == 3
    assert seen["output_mode"] == "single"


def test_actual_rag_adapter_requires_dataset_before_backend_invocation(monkeypatch) -> None:
    from ai.eval import actual_rag_eval
    from ai.eval.experiment_runner.actual_rag import run_actual_rag_experiment
    from ai.eval.experiment_runner.config import build_experiment_config

    config = build_experiment_config(
        ["--experiment", "actual-rag", "--run-id", "missing-dataset", "--output-mode", "report-json"],
        environ={},
        repo_root=ROOT,
    )
    calls: list[dict[str, object]] = []

    def fake_run_eval_from_paths(**kwargs):
        calls.append(kwargs)
        return {"unexpected": True}

    monkeypatch.setattr(actual_rag_eval, "run_eval_from_paths", fake_run_eval_from_paths)

    with pytest.raises(ValueError, match="--dataset"):
        run_actual_rag_experiment(config)
    assert calls == []


def test_actual_rag_adapter_rejects_unwired_run_sqlite_mode(monkeypatch) -> None:
    from ai.eval import actual_rag_eval
    from ai.eval.experiment_runner.actual_rag import run_actual_rag_experiment
    from ai.eval.experiment_runner.config import build_experiment_config

    config = build_experiment_config(
        [
            "--experiment",
            "actual-rag",
            "--run-id",
            "adapter-sqlite-run",
            "--output-mode",
            "report-json",
            "--dataset",
            "ai/tests/fixtures/demo_eval.jsonl",
        ],
        environ={},
        repo_root=ROOT,
    )
    monkeypatch.setattr(actual_rag_eval, "run_eval_from_paths", lambda **_kwargs: {"ok": True})

    with pytest.raises(ValueError, match="run-sqlite"):
        run_actual_rag_experiment(replace(config, output_mode="run-sqlite"))


def test_actual_rag_adapter_returns_json_safe_bundle_summary(monkeypatch) -> None:
    from ai.eval import actual_rag_eval
    from ai.eval.experiment_runner.actual_rag import run_actual_rag_experiment
    from ai.eval.experiment_runner.config import build_experiment_config

    @dataclass(frozen=True)
    class FakeBundle:
        output_dir: Path
        items_path: Path
        summary_path: Path
        markdown_path: Path
        summary: dict[str, object]
        report_path: Path | None = None

    config = build_experiment_config(
        [
            "--experiment",
            "actual-rag",
            "--run-id",
            "json-safe-run",
            "--output-mode",
            "report-json",
            "--dataset",
            "ai/tests/fixtures/demo_eval.jsonl",
        ],
        environ={},
        repo_root=ROOT,
    )
    bundle = FakeBundle(
        output_dir=ROOT / "reports" / "rag_eval" / "json-safe-run",
        items_path=ROOT / "reports" / "rag_eval" / "json-safe-run" / "report.json",
        summary_path=ROOT / "reports" / "rag_eval" / "json-safe-run" / "report.json",
        markdown_path=ROOT / "reports" / "rag_eval" / "json-safe-run" / "report.json",
        report_path=ROOT / "reports" / "rag_eval" / "json-safe-run" / "report.json",
        summary={"status": "ok"},
    )
    monkeypatch.setattr(actual_rag_eval, "run_eval_from_paths", lambda **_kwargs: bundle)

    result = run_actual_rag_experiment(config)

    assert result == {
        "output_dir": "reports/rag_eval/json-safe-run",
        "items_path": "reports/rag_eval/json-safe-run/report.json",
        "summary_path": "reports/rag_eval/json-safe-run/report.json",
        "markdown_path": "reports/rag_eval/json-safe-run/report.json",
        "report_path": "reports/rag_eval/json-safe-run/report.json",
        "summary": {"status": "ok"},
    }
    json.dumps(result)


def test_actual_rag_adapter_redacts_backend_result_paths_outside_repo(monkeypatch) -> None:
    from ai.eval import actual_rag_eval
    from ai.eval.experiment_runner.actual_rag import run_actual_rag_experiment
    from ai.eval.experiment_runner.config import build_experiment_config

    @dataclass(frozen=True)
    class FakeBundle:
        output_dir: Path
        items_path: Path
        summary_path: Path
        markdown_path: Path
        summary: dict[str, object]
        report_path: Path | None = None

    outside_dir = ROOT.parent / "private-output"
    config = build_experiment_config(
        [
            "--experiment",
            "actual-rag",
            "--run-id",
            "outside-result-run",
            "--output-mode",
            "report-json",
            "--dataset",
            "ai/tests/fixtures/demo_eval.jsonl",
            "--output-dir",
            str(outside_dir),
        ],
        environ={},
        repo_root=ROOT,
    )
    bundle = FakeBundle(
        output_dir=outside_dir,
        items_path=outside_dir / "items.jsonl",
        summary_path=outside_dir / "summary.json",
        markdown_path=outside_dir / "report.md",
        report_path=outside_dir / "report.json",
        summary={"outside_path": outside_dir / "nested.json"},
    )
    monkeypatch.setattr(actual_rag_eval, "run_eval_from_paths", lambda **_kwargs: bundle)

    result = run_actual_rag_experiment(config)

    assert result == {
        "output_dir": "<redacted:path>",
        "items_path": "<redacted:path>",
        "summary_path": "<redacted:path>",
        "markdown_path": "<redacted:path>",
        "report_path": "<redacted:path>",
        "summary": {"outside_path": "<redacted:path>"},
    }
    assert "private-output" not in json.dumps(result, ensure_ascii=False)
