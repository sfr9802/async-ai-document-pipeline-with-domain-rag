"""Environment preflight for answer-recovery diagnostic work."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER_ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
DEFAULT_JSON = REPORT_DIR / "answer_recovery_environment_preflight.json"
DEFAULT_MD = REPORT_DIR / "answer_recovery_environment_preflight.md"

ANSWER_RECOVERY_SCRIPTS = [
    "rag_answer_recovery_diagnostic.py",
    "rag_answer_recovery_narrow_calibration.py",
    "rag_answer_recovery_safe_recall_tuning.py",
    "rag_answer_recovery_safe_recall_missed_row_triage.py",
    "rag_answer_recovery_embedding_readiness.py",
    "rag_answer_recovery_embedding_backend_contract_recheck.py",
    "rag_answer_recovery_existing_embedding_retrieval_probe.py",
    "rag_answer_recovery_tuning_report.py",
]

REQUIRED_PATHS = [
    "docs/rag-ingestion-progress.md",
    "ai-worker/eval/reports/rag-ingestion/answer_recovery_tuning_report.md",
    "ai-worker/eval/reports/rag-ingestion/answer_recovery_tuning_report.json",
    "ai-worker/eval/reports/rag-ingestion/answer_recovery_safe_recall_missed_row_triage.json",
    "ai-worker/eval/reports/rag-ingestion/answer_sufficiency_expanded_diagnostic_report.json",
    "ai-worker/eval/reports/rag-ingestion/answer_recovery_expanded_trace.jsonl",
    "ai-worker/eval/eval_queries/official_denominator_registry.json",
    "ai-worker/eval/configs/answer_recovery_narrow_silver_calibration.yaml",
    "ai-worker/eval/configs/answer_recovery_safe_recall_tuning.yaml",
    "ai-worker/eval/configs/answer_recovery_safe_recall_missed_row_triage.yaml",
    "ai-worker/eval/configs/answer_recovery_embedding_readiness.yaml",
    "ai-worker/eval/configs/answer_recovery_fresh_diagnostic_candidate_discovery.yaml",
    "ai-worker/eval/configs/answer_recovery_optuna_round_01_config.yaml",
]

COMPACTED_STAGE_PATHS = [
    "ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_readiness.json",
    "ai-worker/eval/reports/rag-ingestion/answer_recovery_embedding_backend_contract_recheck.json",
    "ai-worker/eval/reports/rag-ingestion/answer_recovery_existing_embedding_retrieval_probe.json",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_preflight()
    write_json(Path(args.json_out), payload)
    write_text(Path(args.md_out), render_md(payload))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "script_help_failures": payload["counts"]["script_help_failures"],
                "missing_required_paths": payload["counts"]["missing_required_paths"],
                "known_environment_warnings": len(payload["known_environment_warnings"]),
                "official_denominator_registry_changed": payload["guardrail_status"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    return parser.parse_args(argv)


def run_preflight() -> dict[str, Any]:
    required_path_checks = path_checks(REQUIRED_PATHS)
    compacted_stage_checks = path_checks(COMPACTED_STAGE_PATHS)
    script_checks = script_help_checks()
    official_diff = official_registry_diff_proof()
    import_roots = [
        root_status("repo_root", REPO_ROOT),
        root_status("ai_worker_root", AI_WORKER_ROOT),
        root_status("scripts_root", SCRIPT_DIR),
        root_status("app_root", AI_WORKER_ROOT / "app"),
        root_status("eval_root", AI_WORKER_ROOT / "eval"),
    ]

    missing_required = [row for row in required_path_checks if not row["exists"]]
    script_failures = [row for row in script_checks if row["help_returncode"] != 0]
    warnings = []
    for row in compacted_stage_checks:
        if not row["exists"]:
            warnings.append(
                {
                    "code": "COMPACT_STAGE_ARTIFACT_ABSENT",
                    "path": row["path"],
                    "classification": "warning",
                    "detail": "Expected after compact artifact cleanup; compact tuning report remains canonical.",
                }
            )
    for row in script_checks:
        if row["stderr_preview"] and row["help_returncode"] == 0:
            warnings.append(
                {
                    "code": "SCRIPT_HELP_STDERR",
                    "path": row["path"],
                    "classification": "warning",
                    "detail": row["stderr_preview"],
                }
            )

    guardrails = base_guardrails()
    guardrails["official_denominator_registry_changed"] = bool(official_diff["changed"])
    guardrails["all_guardrails_preserved"] = guardrail_count(guardrails) == 0
    status = "PASS"
    if missing_required or script_failures or official_diff["changed"] or not guardrails["all_guardrails_preserved"]:
        status = "BLOCKED"

    return {
        "schema_version": "answer_recovery_environment_preflight_report_v1",
        "status": status,
        "repo_root": str(REPO_ROOT),
        "git": {
            "commit": run_git(["rev-parse", "HEAD"]),
            "branch": run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "version_info": list(sys.version_info[:3]),
            "platform": platform.platform(),
        },
        "command_context": {
            "working_directory": str(REPO_ROOT),
            "script_directory": str(SCRIPT_DIR),
        },
        "import_roots": import_roots,
        "answer_recovery_script_help_checks": script_checks,
        "required_path_checks": required_path_checks,
        "compacted_stage_path_checks": compacted_stage_checks,
        "official_denominator_registry_diff_proof": official_diff,
        "guardrail_status": guardrails,
        "known_environment_warnings": warnings,
        "failures": [
            *[
                {"code": "MISSING_REQUIRED_PATH", "path": row["path"], "classification": "failure"}
                for row in missing_required
            ],
            *[
                {
                    "code": "SCRIPT_HELP_FAILED",
                    "path": row["path"],
                    "classification": "failure",
                    "returncode": row["help_returncode"],
                    "stderr_preview": row["stderr_preview"],
                }
                for row in script_failures
            ],
        ],
        "counts": {
            "required_paths": len(required_path_checks),
            "missing_required_paths": len(missing_required),
            "scripts_checked": len(script_checks),
            "script_help_failures": len(script_failures),
        },
    }


def script_help_checks() -> list[dict[str, Any]]:
    rows = []
    for name in ANSWER_RECOVERY_SCRIPTS:
        path = SCRIPT_DIR / name
        if not path.exists():
            rows.append(
                {
                    "path": repo_relative(path),
                    "exists": False,
                    "command": "",
                    "help_returncode": 1,
                    "stdout_preview": "",
                    "stderr_preview": "script missing",
                }
            )
            continue
        command = [sys.executable, str(path), "--help"]
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        rows.append(
            {
                "path": repo_relative(path),
                "exists": True,
                "command": " ".join(command),
                "help_returncode": result.returncode,
                "stdout_preview": first_line(result.stdout),
                "stderr_preview": first_line(result.stderr),
            }
        )
    return rows


def path_checks(paths: list[str]) -> list[dict[str, Any]]:
    rows = []
    for raw in paths:
        path = resolve_path(raw)
        rows.append(
            {
                "path": raw,
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return rows


def root_status(name: str, path: Path) -> dict[str, Any]:
    return {
        "name": name,
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
    }


def base_guardrails() -> dict[str, Any]:
    return {
        "official_denominator_registry_changed": False,
        "official_answer_denominator_opened": False,
        "production_index_mutation": False,
        "broad_indexing": False,
        "vector_write_attempted": False,
        "namespace_created": False,
        "frozen_gold_training_rows": 0,
        "frozen_gold_profile_selection": False,
        "expected_answer_or_label_embedding_count": 0,
        "hidden_xlsx_support_eligible_count": 0,
        "pdf_file_content_mixing_support_eligible_count": 0,
        "diagnostic_only_support_eligible_count": 0,
        "production_promotion_ready": False,
        "official_answer_denominator_ready": False,
        "promotion_evidence": False,
        "per_trial_llm_steering": False,
        "llm_as_objective": False,
        "mid_round_search_space_mutation": False,
        "raw_data_exposed_to_llm_analyst": False,
    }


def guardrail_count(payload: Mapping[str, Any]) -> int:
    count = 0
    for key, value in payload.items():
        if key == "all_guardrails_preserved":
            continue
        if isinstance(value, bool) and value:
            count += 1
        elif isinstance(value, int) and not isinstance(value, bool) and value != 0:
            count += 1
    return count


def official_registry_diff_proof() -> dict[str, Any]:
    rel = "ai-worker/eval/eval_queries/official_denominator_registry.json"
    unstaged = subprocess.run(["git", "diff", "--quiet", "--", rel], cwd=REPO_ROOT, text=True, capture_output=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", rel],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    changed = unstaged.returncode != 0 or staged.returncode != 0
    return {
        "path": rel,
        "command": f"git diff --quiet -- {rel}; git diff --cached --quiet -- {rel}",
        "changed": changed,
        "unstaged_diff_empty": unstaged.returncode == 0,
        "staged_diff_empty": staged.returncode == 0,
        "diff_empty": not changed,
        "diff_stdout_bytes": len(unstaged.stdout or "") + len(staged.stdout or ""),
    }


def render_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Answer Recovery Environment Preflight",
        "",
        f"- Status: `{payload['status']}`.",
        f"- Repo root: `{payload['repo_root']}`.",
        f"- Git branch: `{payload['git']['branch']}`.",
        f"- Git commit: `{payload['git']['commit']}`.",
        f"- Python executable: `{payload['python']['executable']}`.",
        f"- Python version: `{payload['python']['version_info']}`.",
        f"- Working directory: `{payload['command_context']['working_directory']}`.",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
        ]
    )
    for key, value in payload["guardrail_status"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Warnings",
            "",
        ]
    )
    if payload["known_environment_warnings"]:
        for warning in payload["known_environment_warnings"]:
            lines.append(f"- `{warning['code']}`: {warning.get('path', '')} {warning['detail']}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        for failure in payload["failures"]:
            lines.append(f"- `{failure['code']}`: {failure.get('path', '')}")
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def resolve_path(value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def first_line(value: str) -> str:
    return next((line.strip() for line in value.splitlines() if line.strip()), "")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
