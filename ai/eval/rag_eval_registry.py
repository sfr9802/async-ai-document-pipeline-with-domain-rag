from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")

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


class ReportResolutionError(RuntimeError):
    """Raised when a diagnostic report alias cannot be resolved safely."""


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


def _repo_root(root: Path | str | None = None) -> Path:
    return Path.cwd() if root is None else Path(root)


def _relative_report_path(key: str) -> Path:
    normalized = _normalize_key(key)
    if normalized == "v4_7_4":
        return REPORT_ROOT / "quality" / V4_7_4_LONG_RUN_ID / "report.json"
    if normalized == V4_7_5_SHORT_KEY:
        return REPORT_ROOT / "runs" / V4_7_5_SHORT_KEY / "report.json"
    raise ReportResolutionError(f"unknown RAG eval run key: {key}")


def _normalize_key(key: str) -> str:
    normalized = key.strip()
    if normalized in {"current", V4_7_5_SHORT_RUN_ID, V4_7_5_LONG_RUN_ID}:
        return V4_7_5_SHORT_KEY
    if normalized in {V4_7_4_LONG_RUN_ID, "v4_7_4_pdf_survivor_replay"}:
        return "v4_7_4"
    return normalized


def resolve_run(key: str, *, root: Path | str | None = None) -> ResolvedRun:
    normalized = _normalize_key(key)
    repo_root = _repo_root(root)
    report_path = repo_root / _relative_report_path(normalized)
    if normalized == "v4_7_4":
        return ResolvedRun(
            logical_key="v4_7_4",
            short_run_id="v4_7_4",
            canonical_long_run_id=V4_7_4_LONG_RUN_ID,
            status=V4_7_4_STATUS,
            report_path=report_path,
            legacy_long_path_supported=True,
        )
    if normalized == V4_7_5_SHORT_KEY:
        return ResolvedRun(
            logical_key=V4_7_5_SHORT_KEY,
            short_run_id=V4_7_5_SHORT_RUN_ID,
            canonical_long_run_id=V4_7_5_LONG_RUN_ID,
            status=V4_7_5_STATUS,
            report_path=report_path,
            legacy_long_path_supported=True,
        )
    raise ReportResolutionError(f"unknown RAG eval run key: {key}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    if resolved.logical_key == "v4_7_4":
        if report.get("run_id") != resolved.canonical_long_run_id:
            raise ReportResolutionError("v4_7_4 report run id mismatch")
        if report.get("status") != resolved.status:
            raise ReportResolutionError("v4_7_4 report status mismatch")
        return
    if report.get("short_run_id") != resolved.short_run_id:
        raise ReportResolutionError("v4_7_5 report short_run_id mismatch")
    if report.get("canonical_long_run_id") != resolved.canonical_long_run_id:
        raise ReportResolutionError("v4_7_5 report canonical_long_run_id mismatch")
    if report.get("status") != resolved.status:
        raise ReportResolutionError("v4_7_5 report status mismatch")
