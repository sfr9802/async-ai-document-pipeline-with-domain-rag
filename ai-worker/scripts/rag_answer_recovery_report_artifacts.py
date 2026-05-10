"""Reporting profile helpers for answer-recovery diagnostic artifacts."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any, Mapping

ALLOWED_ARTIFACT_PROFILES = {"compact", "standard", "debug"}

DEFAULT_REPORTING = {
    "artifact_profile": "compact",
    "compact_report_basename": "answer_recovery_tuning_report",
    "emit_human_report": True,
    "emit_machine_report": True,
    "emit_stage_reports": False,
    "emit_csv": False,
    "emit_row_manifest": False,
    "emit_namespace_inventory": False,
    "emit_debug_artifacts": False,
    "emit_debug_artifacts_on_failure": True,
    "clean_legacy_stage_artifacts_on_compact_run": True,
}

COMPACT_CLEANUP_FILENAMES = [
    "answer_recovery_embedding_backend_contract_recheck.md",
    "answer_recovery_embedding_backend_contract_recheck.json",
    "answer_recovery_embedding_backend_contract_recheck.csv",
    "answer_recovery_embedding_readiness.md",
    "answer_recovery_embedding_readiness.json",
    "answer_recovery_embedding_readiness.csv",
    "answer_recovery_existing_embedding_retrieval_probe.md",
    "answer_recovery_existing_embedding_retrieval_probe.json",
    "answer_recovery_existing_embedding_retrieval_probe.csv",
    "answer_recovery_embedding_backfill_manifest.jsonl",
    "answer_recovery_embedding_namespace_inventory.json",
]


def add_reporting_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--artifact-profile",
        choices=sorted(ALLOWED_ARTIFACT_PROFILES),
        default=None,
        help="Report artifact profile. Defaults to config reporting.artifact_profile or compact.",
    )
    parser.add_argument("--emit-csv", action="store_true", help="Emit CSV artifacts for this explicit run.")
    parser.add_argument(
        "--emit-stage-reports",
        action="store_true",
        help="Emit legacy per-stage md/json reports for this explicit run.",
    )
    parser.add_argument(
        "--emit-row-manifest",
        action="store_true",
        help="Emit row-level JSONL manifest artifacts for this explicit run.",
    )
    parser.add_argument(
        "--emit-namespace-inventory",
        action="store_true",
        help="Emit namespace inventory JSON artifacts for this explicit run.",
    )
    parser.add_argument(
        "--emit-debug-artifacts",
        action="store_true",
        help="Emit all debug-only legacy artifacts for this explicit run.",
    )
    parser.add_argument(
        "--no-clean-legacy-stage-artifacts",
        action="store_true",
        help="Disable compact-run cleanup of stale generated legacy stage artifacts.",
    )


def reporting_overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if getattr(args, "artifact_profile", None):
        overrides["artifact_profile"] = args.artifact_profile
    for attr in (
        "emit_csv",
        "emit_stage_reports",
        "emit_row_manifest",
        "emit_namespace_inventory",
        "emit_debug_artifacts",
    ):
        if bool(getattr(args, attr, False)):
            overrides[attr] = True
    if bool(getattr(args, "no_clean_legacy_stage_artifacts", False)):
        overrides["clean_legacy_stage_artifacts_on_compact_run"] = False
    return overrides


def with_reporting_overrides(
    config: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(config)
    reporting = dict(merged.get("reporting") or {})
    reporting.update(dict(overrides or {}))
    merged["reporting"] = reporting
    return merged


def reporting_options(
    config: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw = dict(DEFAULT_REPORTING)
    if config:
        raw.update(dict(config.get("reporting") or {}))
    raw.update(dict(overrides or {}))
    profile = str(raw.get("artifact_profile") or "compact")
    if profile not in ALLOWED_ARTIFACT_PROFILES:
        raise ValueError(f"Unsupported answer-recovery artifact_profile: {profile}")

    if profile == "compact":
        raw["emit_human_report"] = bool(raw.get("emit_human_report", True))
        raw["emit_machine_report"] = bool(raw.get("emit_machine_report", True))
        raw["emit_stage_reports"] = bool(raw.get("emit_stage_reports", False))
        raw["emit_csv"] = bool(raw.get("emit_csv", False))
        raw["emit_row_manifest"] = bool(raw.get("emit_row_manifest", False))
        raw["emit_namespace_inventory"] = bool(raw.get("emit_namespace_inventory", False))
        raw["emit_debug_artifacts"] = bool(raw.get("emit_debug_artifacts", False))
    elif profile == "standard":
        raw["emit_human_report"] = bool(raw.get("emit_human_report", True))
        raw["emit_machine_report"] = bool(raw.get("emit_machine_report", True))
        raw["emit_stage_reports"] = bool(raw.get("emit_stage_reports", False))
        raw["emit_csv"] = bool(raw.get("emit_csv", False))
        raw["emit_row_manifest"] = bool(raw.get("emit_row_manifest", False))
        raw["emit_namespace_inventory"] = bool(raw.get("emit_namespace_inventory", False))
        raw["emit_debug_artifacts"] = bool(raw.get("emit_debug_artifacts", False))
    else:
        raw["emit_human_report"] = True
        raw["emit_machine_report"] = True
        raw["emit_stage_reports"] = True
        raw["emit_csv"] = True
        raw["emit_row_manifest"] = True
        raw["emit_namespace_inventory"] = True
        raw["emit_debug_artifacts"] = True

    raw["artifact_profile"] = profile
    return raw


def validate_reporting_config(config: Mapping[str, Any]) -> list[str]:
    reporting = dict(config.get("reporting") or {})
    profile = str(reporting.get("artifact_profile") or "compact")
    if profile not in ALLOWED_ARTIFACT_PROFILES:
        return [f"artifact_profile must be one of {sorted(ALLOWED_ARTIFACT_PROFILES)}"]
    return []


def compact_report_paths(
    config: Mapping[str, Any],
    *,
    resolve_path: Any,
    report_dir: Path | None = None,
) -> dict[str, Path]:
    options = reporting_options(config)
    basename = str(options["compact_report_basename"])
    if report_dir is None:
        paths = config.get("report_paths", {})
        readiness_json = paths.get("readiness_json")
        if readiness_json:
            report_dir = resolve_path(readiness_json).parent
        else:
            report_dir = resolve_path("ai-worker/eval/reports/rag-ingestion")
    return {
        "md": report_dir / f"{basename}.md",
        "json": report_dir / f"{basename}.json",
    }


def cleanup_legacy_stage_artifacts(
    *,
    reports_dir: Path,
    repo_root: Path,
    filenames: list[str] | None = None,
) -> dict[str, Any]:
    names = filenames or COMPACT_CLEANUP_FILENAMES
    reports_dir = reports_dir.resolve()
    repo_root = repo_root.resolve()
    candidates = [reports_dir / name for name in names]
    outside = [
        str(path)
        for path in candidates
        if reports_dir not in (path.resolve(), *path.resolve().parents)
    ]
    if outside:
        return {
            "cleanup_status": "FAILED_OUTSIDE_REPORTS_DIR",
            "removed": [],
            "missing": [],
            "tracked_legacy_artifacts_detected": outside,
        }

    tracked = tracked_paths(repo_root=repo_root, paths=candidates)
    if tracked:
        return {
            "cleanup_status": "FAILED_TRACKED_LEGACY_ARTIFACTS_DETECTED",
            "removed": [],
            "missing": [],
            "tracked_legacy_artifacts_detected": tracked,
        }

    removed: list[str] = []
    missing: list[str] = []
    for path in candidates:
        if path.exists():
            path.unlink()
            removed.append(repo_relative(repo_root, path))
        else:
            missing.append(repo_relative(repo_root, path))
    return {
        "cleanup_status": "CLEANED" if removed else "NO_STALE_ARTIFACTS_FOUND",
        "removed": removed,
        "missing": missing,
        "tracked_legacy_artifacts_detected": [],
    }


def tracked_paths(*, repo_root: Path, paths: list[Path]) -> list[str]:
    relative_paths = [repo_relative(repo_root, path) for path in paths if path.exists()]
    if not relative_paths:
        return []
    result = subprocess.run(
        ["git", "ls-files", "--", *relative_paths],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
