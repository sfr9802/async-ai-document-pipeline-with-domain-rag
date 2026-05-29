from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPORT_ROOT = Path("ai/eval/reports/rag-ingestion")

V4_7_PREOFFICIAL_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_preofficial_"
    "external_holdout_candidate_manifest_registration_nonprod"
)
V4_7_PREOFFICIAL_STATUS = "V4_7_PREOFFICIAL_EXTERNAL_HOLDOUT_CANDIDATE_MANIFEST_REGISTRATION_READY"

V4_7_2_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_2_"
    "source_grounded_korean_query_review_packet_hydration_nonprod"
)
V4_7_2_STATUS = "DIAGNOSTIC_V4_7_2_SOURCE_GROUNDED_KOREAN_QUERY_REVIEW_PACKET_HYDRATION_NONPROD_READY"

V4_7_3_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_3_"
    "human_reviewed_korean_query_candidate_pass_exclusion_application_nonprod"
)
V4_7_3_STATUS = "V4_7_3_HUMAN_REVIEWED_KOREAN_QUERY_CANDIDATE_PASS_EXCLUSION_APPLICATION_NONPROD_READY"

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

V4_7_6_SHORT_KEY = "v4_7_6"
V4_7_6_SHORT_RUN_ID = "v4_7_6_eval_artifact_archive_purge"
V4_7_6_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_6_"
    "eval_artifact_external_archive_and_purge_nonprod"
)
V4_7_6_STATUS = "V4_7_6_EVAL_ARTIFACT_ARCHIVE_PURGE_NONPROD_READY"

V4_7_7_SHORT_KEY = "v4_7_7"
V4_7_7_SHORT_RUN_ID = "v4_7_7_v3_legacy_archive_and_runner_consolidation"
V4_7_7_LONG_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v4_7_7_"
    "v3_legacy_artifact_archive_and_diagnostic_runner_consolidation_nonprod"
)
V4_7_7_STATUS = "V4_7_7_V3_LEGACY_ARCHIVE_RUNNER_CONSOLIDATION_NONPROD_READY"


class ReportResolutionError(RuntimeError):
    """Raised when a diagnostic report alias cannot be resolved safely."""


@dataclass(frozen=True)
class RunMetadata:
    logical_key: str
    short_run_id: str
    canonical_long_run_id: str
    status: str
    short_report_path: Path
    legacy_report_path: Path | None = None
    accepted_aliases: tuple[str, ...] = ()
    canonical_fields: tuple[str, ...] = ("run_id",)


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


RUNS: dict[str, RunMetadata] = {
    "v4_7_preofficial": RunMetadata(
        logical_key="v4_7_preofficial",
        short_run_id="v4_7_preofficial",
        canonical_long_run_id=V4_7_PREOFFICIAL_LONG_RUN_ID,
        status=V4_7_PREOFFICIAL_STATUS,
        short_report_path=REPORT_ROOT / "runs" / "v4_7_preofficial" / "report.json",
        legacy_report_path=REPORT_ROOT / "quality" / V4_7_PREOFFICIAL_LONG_RUN_ID / "report.json",
        accepted_aliases=(V4_7_PREOFFICIAL_LONG_RUN_ID,),
    ),
    "v4_7_2": RunMetadata(
        logical_key="v4_7_2",
        short_run_id="v4_7_2",
        canonical_long_run_id=V4_7_2_LONG_RUN_ID,
        status=V4_7_2_STATUS,
        short_report_path=REPORT_ROOT / "runs" / "v4_7_2" / "report.json",
        legacy_report_path=REPORT_ROOT / "quality" / V4_7_2_LONG_RUN_ID / "report.json",
        accepted_aliases=(V4_7_2_LONG_RUN_ID,),
    ),
    "v4_7_3": RunMetadata(
        logical_key="v4_7_3",
        short_run_id="v4_7_3",
        canonical_long_run_id=V4_7_3_LONG_RUN_ID,
        status=V4_7_3_STATUS,
        short_report_path=REPORT_ROOT / "runs" / "v4_7_3" / "report.json",
        legacy_report_path=REPORT_ROOT / "quality" / V4_7_3_LONG_RUN_ID / "report.json",
        accepted_aliases=(V4_7_3_LONG_RUN_ID,),
    ),
    "v4_7_4": RunMetadata(
        logical_key="v4_7_4",
        short_run_id="v4_7_4",
        canonical_long_run_id=V4_7_4_LONG_RUN_ID,
        status=V4_7_4_STATUS,
        short_report_path=REPORT_ROOT / "runs" / "v4_7_4" / "report.json",
        legacy_report_path=REPORT_ROOT / "quality" / V4_7_4_LONG_RUN_ID / "report.json",
        accepted_aliases=(V4_7_4_LONG_RUN_ID, "v4_7_4_pdf_survivor_replay"),
    ),
    V4_7_5_SHORT_KEY: RunMetadata(
        logical_key=V4_7_5_SHORT_KEY,
        short_run_id=V4_7_5_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_5_LONG_RUN_ID,
        status=V4_7_5_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_5_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_5_SHORT_RUN_ID, V4_7_5_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_6_SHORT_KEY: RunMetadata(
        logical_key=V4_7_6_SHORT_KEY,
        short_run_id=V4_7_6_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_6_LONG_RUN_ID,
        status=V4_7_6_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_6_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_6_SHORT_RUN_ID, V4_7_6_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
    V4_7_7_SHORT_KEY: RunMetadata(
        logical_key=V4_7_7_SHORT_KEY,
        short_run_id=V4_7_7_SHORT_RUN_ID,
        canonical_long_run_id=V4_7_7_LONG_RUN_ID,
        status=V4_7_7_STATUS,
        short_report_path=REPORT_ROOT / "runs" / V4_7_7_SHORT_KEY / "report.json",
        accepted_aliases=(V4_7_7_SHORT_RUN_ID, V4_7_7_LONG_RUN_ID),
        canonical_fields=("short_run_id", "canonical_long_run_id"),
    ),
}

ALIAS_TO_KEY: dict[str, str] = {
    alias: key
    for key, metadata in RUNS.items()
    for alias in (key, *metadata.accepted_aliases)
}
ALIAS_TO_KEY["current"] = V4_7_7_SHORT_KEY


def _repo_root(root: Path | str | None = None) -> Path:
    return Path.cwd() if root is None else Path(root)


def _normalize_key(key: str) -> str:
    normalized = key.strip()
    try:
        return ALIAS_TO_KEY[normalized]
    except KeyError as exc:
        raise ReportResolutionError(f"unknown RAG eval run key: {key}") from exc


def resolve_run(key: str, *, root: Path | str | None = None) -> ResolvedRun:
    normalized = _normalize_key(key)
    metadata = RUNS[normalized]
    repo_root = _repo_root(root)
    return ResolvedRun(
        logical_key=metadata.logical_key,
        short_run_id=metadata.short_run_id,
        canonical_long_run_id=metadata.canonical_long_run_id,
        status=metadata.status,
        report_path=repo_root / metadata.short_report_path,
        legacy_long_path_supported=metadata.legacy_report_path is not None,
    )


def legacy_report_path(key: str, *, root: Path | str | None = None) -> Path | None:
    metadata = RUNS[_normalize_key(key)]
    if metadata.legacy_report_path is None:
        return None
    return _repo_root(root) / metadata.legacy_report_path


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


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
    metadata = RUNS[resolved.logical_key]
    if "run_id" in metadata.canonical_fields:
        if report.get("run_id") != metadata.canonical_long_run_id:
            raise ReportResolutionError(f"{resolved.logical_key} report run id mismatch")
    if "short_run_id" in metadata.canonical_fields:
        if report.get("short_run_id") != metadata.short_run_id:
            raise ReportResolutionError(f"{resolved.logical_key} report short_run_id mismatch")
    if "canonical_long_run_id" in metadata.canonical_fields:
        if report.get("canonical_long_run_id") != metadata.canonical_long_run_id:
            raise ReportResolutionError(f"{resolved.logical_key} report canonical_long_run_id mismatch")
    if report.get("status") != metadata.status:
        raise ReportResolutionError(f"{resolved.logical_key} report status mismatch")
