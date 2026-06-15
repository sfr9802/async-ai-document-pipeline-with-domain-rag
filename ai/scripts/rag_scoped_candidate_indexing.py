"""Run scoped SearchUnit candidate indexing until the scope is empty.

This is a reporting wrapper around the existing worker components. It refuses
unscoped candidate indexing unless --allow-unscoped is explicitly supplied,
and its default scope is the Track C PDF candidate scope report. XLSX or mixed
candidate runs must pass explicit scope/index arguments.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_WORKER = Path(__file__).resolve().parents[1]
ROOT = AI_WORKER.parent
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))

from app.cli.search_unit_indexing import _validate_cli_args  # noqa: E402
from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length  # noqa: E402
from app.capabilities.rag.faiss_index import FaissIndex  # noqa: E402
from app.capabilities.rag.metadata_store import RagMetadataStore  # noqa: E402
from app.capabilities.rag.search_unit_indexing import SearchUnitVectorIndexer  # noqa: E402
from app.clients.core_api_client import CoreApiClient  # noqa: E402
from app.core.config import WorkerSettings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.services.search_unit_indexing_loop import SearchUnitIndexingWorker  # noqa: E402


DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_pdf_v0.csv")
DEFAULT_SCOPE_REPORT = Path("reports/rag_eval/rag-ingestion/pdf_candidate_scope_report.json")
DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/scoped_candidate_indexing_report.json")
DEFAULT_INDEX_VERSION = "rag-ingestion-v2-pdf-candidate-v1"
DEFAULT_SOURCE_FILE_TYPES = ("PDF",)
DEFAULT_PARSER_VERSIONS = ("pdf-extract-v1", "pdf-extract-v2")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging()
    document_version_ids, source_file_ids, scope_report = load_scope(args)
    validate_scope(args, document_version_ids, source_file_ids, scope_report)
    run_started_at = utc_timestamp()
    cycles: list[dict[str, Any]] = []
    status = "PASS"
    blockers: list[str] = []

    settings = WorkerSettings()
    artifact_dir = Path(args.artifact_dir or settings.rag_index_dir)
    artifact_dir_exists_before_run = artifact_dir.exists()
    if not args.dry_run and artifact_dir_exists_before_run and not args.allow_existing_artifact:
        consistency_report = Path(args.consistency_report)
        if not consistency_report.exists():
            status = "FAIL"
            blockers.append(
                "artifact_dir already exists without a consistency report; refusing silent reuse "
                f"artifact_dir={artifact_dir} consistency_report={consistency_report}"
            )
    core_api = CoreApiClient(
        settings.core_api_base_url,
        settings.core_api_request_timeout_seconds,
        settings.internal_secret,
    )
    try:
        if blockers:
            raise RuntimeError("; ".join(blockers))
        max_seq_length = resolve_max_seq_length(settings.rag_embedding_max_seq_length)
        embedder = SentenceTransformerEmbedder(
            model_name=settings.rag_embedding_model,
            query_prefix=settings.rag_embedding_prefix_query,
            passage_prefix=settings.rag_embedding_prefix_passage,
            max_seq_length=max_seq_length,
            batch_size=int(settings.rag_embedding_batch_size),
            cuda_alloc_conf=settings.rag_embedding_cuda_alloc_conf or None,
        )
        metadata = RagMetadataStore(settings.rag_db_dsn)
        index = FaissIndex(artifact_dir)
        indexer = SearchUnitVectorIndexer(
            embedder=embedder,
            metadata_store=metadata,
            index=index,
            index_version=args.expected_index_version,
            embedding_text_variant=settings.rag_embedding_text_variant,
            max_seq_length=max_seq_length,
        )
        worker = SearchUnitIndexingWorker(
            core_api=core_api,
            indexer=indexer,
            worker_id=settings.worker_id,
            batch_size=args.batch_size,
            stale_after_seconds=args.stale_after_seconds,
            source_file_id=None,
            source_file_ids=source_file_ids,
            document_version_id=None,
            document_version_ids=document_version_ids,
            parsed_artifact_id=None,
            search_unit_ids=[],
            source_file_types=list(args.source_file_type),
            parser_versions=list(args.parser_version),
            expected_index_version=args.expected_index_version,
            limit=args.limit,
            allow_unscoped=args.allow_unscoped,
        )
        for cycle in range(1, args.max_cycles + 1):
            summary = worker.run_once(dry_run=args.dry_run)
            item = {
                "cycle": cycle,
                "claimed": summary.claimed,
                "indexed": summary.indexed,
                "failed": summary.failed,
                "stale": summary.stale,
                "skipped_local": summary.skipped_local,
                "dry_run": summary.dry_run,
            }
            cycles.append(item)
            if summary.dry_run or summary.claimed == 0:
                break
            if summary.failed:
                status = "FAIL"
                blockers.append(f"cycle {cycle} reported failed={summary.failed}")
                break
        else:
            status = "FAIL"
            blockers.append(f"max_cycles reached before scope emptied: {args.max_cycles}")
    except Exception as exc:
        status = "FAIL"
        blockers.append(f"scoped indexing failed: {type(exc).__name__}: {exc}")
    finally:
        core_api.close()

    payload = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "run_started_at": run_started_at,
        "status": status,
        "scope": "explicit_scoped_candidate_indexing",
        "documentVersionIds": document_version_ids,
        "sourceFileIds": source_file_ids,
        "sourceFileTypes": list(args.source_file_type),
        "parserVersions": list(args.parser_version),
        "expectedIndexVersion": args.expected_index_version,
        "artifactDir": str(artifact_dir),
        "allowUnscoped": bool(args.allow_unscoped),
        "dryRun": bool(args.dry_run),
        "batchSize": args.batch_size,
        "limit": args.limit,
        "maxCycles": args.max_cycles,
        "scopeReport": artifact_identity(Path(args.scope_report)) if args.scope_report else None,
        "consistencyReport": str(Path(args.consistency_report)),
        "existingArtifactPolicy": {
            "allowExistingArtifact": bool(args.allow_existing_artifact),
            "artifactDirExistsBeforeRun": artifact_dir_exists_before_run,
        },
        "cycles": cycles,
        "totals": {
            "claimed": sum(item["claimed"] for item in cycles),
            "indexed": sum(item["indexed"] for item in cycles),
            "failed": sum(item["failed"] for item in cycles),
            "stale": sum(item["stale"] for item in cycles),
            "skipped_local": sum(item["skipped_local"] for item in cycles),
        },
        "blockers": blockers,
    }
    write_json(Path(args.output), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 2

def load_scope(args: argparse.Namespace) -> tuple[list[str], list[str], dict[str, Any]]:
    ids: set[str] = set(args.document_version_id or [])
    source_ids: set[str] = set(args.source_file_id or [])
    report: dict[str, Any] = {}
    if args.scope_report:
        path = Path(args.scope_report)
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                report = loaded
                cli_scope = loaded.get("indexing_cli_scope") if isinstance(loaded.get("indexing_cli_scope"), dict) else {}
                scope = loaded.get("scope") if isinstance(loaded.get("scope"), dict) else {}
                ids.update(str(item) for item in (cli_scope.get("documentVersionIds") or scope.get("document_version_ids") or []) if str(item))
                source_ids.update(str(item) for item in (cli_scope.get("sourceFileIds") or scope.get("source_file_ids") or []) if str(item))
    gold = Path(args.gold)
    if not args.scope_report and gold.exists():
        with gold.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                docv = (row.get("expected_document_version_id") or "").strip()
                if docv:
                    ids.add(docv)
    return sorted(ids), sorted(source_ids), report


def validate_scope(
    args: argparse.Namespace,
    document_version_ids: list[str],
    source_file_ids: list[str],
    scope_report: dict[str, Any],
) -> None:
    synthetic = argparse.Namespace(
        expected_index_version=args.expected_index_version,
        index_version=args.expected_index_version,
        dry_run=args.dry_run,
        allow_unscoped=args.allow_unscoped,
        document_version_id=None,
        document_version_ids=document_version_ids,
        source_file_id=None,
        source_file_ids=source_file_ids or None,
        parsed_artifact_id=None,
        search_unit_id=None,
    )
    _validate_cli_args(synthetic)
    if not args.allow_unscoped and not document_version_ids and not source_file_ids:
        raise ValueError("documentVersionIds or sourceFileIds scope is required when allowUnscoped=false")
    if scope_report:
        cli_scope = scope_report.get("indexing_cli_scope") if isinstance(scope_report.get("indexing_cli_scope"), dict) else {}
        if scope_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
            raise ValueError(f"scope report must be PASS/PASS_WITH_WARNINGS: {scope_report.get('status')}")
        if scope_report.get("allowUnscoped") is not False or cli_scope.get("allowUnscoped") is not False:
            raise ValueError("scope report must keep allowUnscoped=false")
        expected = cli_scope.get("expectedIndexVersion") or scope_report.get("index_version")
        if expected and expected != args.expected_index_version:
            raise ValueError(
                "scope report expectedIndexVersion must match CLI expected index version "
                f"(scope={expected!r}, cli={args.expected_index_version!r})"
            )
        report_source_types = set(str(item).upper() for item in (cli_scope.get("sourceFileTypes") or []))
        cli_source_types = set(str(item).upper() for item in args.source_file_type)
        if report_source_types and report_source_types != cli_source_types:
            raise ValueError(
                f"sourceFileTypes must match scope report (scope={sorted(report_source_types)}, cli={sorted(cli_source_types)})"
            )
        report_parsers = set(str(item) for item in (cli_scope.get("parserVersions") or []))
        cli_parsers = set(str(item) for item in args.parser_version)
        if report_parsers and report_parsers != cli_parsers:
            raise ValueError(
                f"parserVersions must match scope report (scope={sorted(report_parsers)}, cli={sorted(cli_parsers)})"
            )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--scope-report", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--document-version-id", action="append", default=None)
    parser.add_argument("--source-file-id", action="append", default=None)
    parser.add_argument("--source-file-type", action="append", default=None)
    parser.add_argument("--parser-version", action="append", default=None)
    parser.add_argument("--expected-index-version", default=DEFAULT_INDEX_VERSION)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument(
        "--consistency-report",
        default="reports/rag_eval/rag-ingestion/pdf_candidate_embedding_consistency_report.json",
    )
    parser.add_argument("--allow-existing-artifact", action="store_true")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--max-cycles", type=int, default=200)
    parser.add_argument("--stale-after-seconds", type=int, default=None)
    parser.add_argument("--allow-unscoped", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.source_file_type is None:
        args.source_file_type = list(DEFAULT_SOURCE_FILE_TYPES)
    if args.parser_version is None:
        args.parser_version = list(DEFAULT_PARSER_VERSIONS)
    return args


if __name__ == "__main__":
    sys.exit(main())
