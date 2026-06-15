from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = REPO_ROOT / "ai"

# Active actual-RAG eval runs and latest pointers. This tree is generated and
# ignored; public-facing claims should point to docs, not to committing these.
ACTUAL_RAG_REPORT_ROOT = REPO_ROOT / "reports" / "rag_eval"
ACTUAL_RAG_RUN_REGISTRY = ACTUAL_RAG_REPORT_ROOT / "runs.jsonl"
ACTUAL_RAG_LATEST_POINTER = ACTUAL_RAG_REPORT_ROOT / "latest.json"

# Legacy/current diagnostic ladder artifacts. These are physically consolidated
# under the same generated machine-report root as actual-RAG reports.
LEGACY_RAG_INGESTION_REPORT_ROOT = ACTUAL_RAG_REPORT_ROOT / "rag-ingestion"
LEGACY_RAG_INGESTION_RUNS_ROOT = LEGACY_RAG_INGESTION_REPORT_ROOT / "runs"
LEGACY_RAG_INGESTION_STATUS_JSONL = LEGACY_RAG_INGESTION_REPORT_ROOT / "status.jsonl"
LEGACY_RAG_INGESTION_ARCHIVE_MANIFEST = LEGACY_RAG_INGESTION_REPORT_ROOT / "archive_manifest.jsonl"

# Human-facing ledgers. These are the canonical tracked summaries for portfolio
# and repo hygiene state.
RAG_INGESTION_PROGRESS_DOC = REPO_ROOT / "docs" / "rag-ingestion-progress.md"
RAG_INGESTION_MEASUREMENTS_DOC = REPO_ROOT / "docs" / "rag-ingestion-measurements.md"
RAG_INGESTION_TRIAGE_DOC = REPO_ROOT / "docs" / "rag-ingestion-triage.md"

# Tracked root reports are intentionally limited to small public portfolio
# artifacts. Machine RAG reports live under ACTUAL_RAG_REPORT_ROOT instead.
PUBLIC_REPORT_ROOT = REPO_ROOT / "reports"
PUBLIC_PORTFOLIO_REPORT = PUBLIC_REPORT_ROOT / "portfolio_agentops_report.md"
PUBLIC_AGENTOPS_SAMPLE_TRACE = PUBLIC_REPORT_ROOT / "agentops_sample_trace.json"


@dataclass(frozen=True)
class ReportNamespace:
    name: str
    root: Path
    git_policy: str
    role: str

    def repo_relative_root(self, repo_root: Path = REPO_ROOT) -> str:
        return self.root.relative_to(repo_root).as_posix()


REPORT_NAMESPACES = (
    ReportNamespace(
        name="public_portfolio_reports",
        root=PUBLIC_REPORT_ROOT,
        git_policy="tracked allowlist only",
        role="small public portfolio report and sanitized sample trace",
    ),
    ReportNamespace(
        name="actual_rag_reports",
        root=ACTUAL_RAG_REPORT_ROOT,
        git_policy="ignored generated machine artifacts",
        role=(
            "consolidated generated machine-report root for actual-RAG report.json "
            "runs, latest pointers, run registry, Weaviate manifests, and rag-ingestion/"
        ),
    ),
    ReportNamespace(
        name="legacy_rag_ingestion_reports",
        root=LEGACY_RAG_INGESTION_REPORT_ROOT,
        git_policy="ignored generated machine artifacts",
        role="legacy/current diagnostic ladder reports, status.jsonl, and short-key report evidence",
    ),
    ReportNamespace(
        name="rag_ingestion_ledgers",
        root=RAG_INGESTION_PROGRESS_DOC.parent,
        git_policy="tracked human-facing ledgers",
        role="append-only progress, measurements, and triage summaries",
    ),
)


def dataset_latest_pointer(dataset_slug: str, *, report_root: Path = ACTUAL_RAG_REPORT_ROOT) -> Path:
    slug = dataset_slug.strip().replace("-", "_")
    if not slug:
        raise ValueError("dataset_slug must not be blank")
    return report_root / f"latest_{slug}.json"
