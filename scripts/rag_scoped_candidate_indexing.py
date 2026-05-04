"""Run scoped SearchUnit candidate indexing until the scope is empty.

This is a reporting wrapper around the existing worker components. It refuses
unscoped candidate indexing unless --allow-unscoped is explicitly supplied,
and its default scope is the unique expected_document_version_id values from
the full72 gold CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AI_WORKER = ROOT / "ai-worker"
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))

from ai_worker.search_unit_indexing import _validate_cli_args  # noqa: E402
from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length  # noqa: E402
from app.capabilities.rag.faiss_index import FaissIndex  # noqa: E402
from app.capabilities.rag.metadata_store import RagMetadataStore  # noqa: E402
from app.capabilities.rag.search_unit_indexing import SearchUnitVectorIndexer  # noqa: E402
from app.clients.core_api_client import CoreApiClient  # noqa: E402
from app.core.config import WorkerSettings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.services.search_unit_indexing_loop import SearchUnitIndexingWorker  # noqa: E402


DEFAULT_GOLD = Path("eval/gold_queries_v0.csv")
DEFAULT_OUTPUT = Path("reports/scoped_candidate_indexing_report.json")
DEFAULT_INDEX_VERSION = "rag-ingestion-v2-candidate"
DEFAULT_SOURCE_FILE_TYPES = ("SPREADSHEET", "PDF")
DEFAULT_PARSER_VERSIONS = ("xlsx-extract-v2-hidden-safe", "pdf-extract-v1", "pdf-extract-v2")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging()
    document_version_ids = load_scope_ids(args)
    validate_scope(args, document_version_ids)
    run_started_at = utc_timestamp()
    cycles: list[dict[str, Any]] = []
    status = "PASS"
    blockers: list[str] = []

    settings = WorkerSettings()
    core_api = CoreApiClient(
        settings.core_api_base_url,
        settings.core_api_request_timeout_seconds,
        settings.internal_secret,
    )
    try:
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
        index = FaissIndex(Path(settings.rag_index_dir))
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
            source_file_ids=[],
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
        "scope": "full72_document_version_scoped_candidate_indexing",
        "documentVersionIds": document_version_ids,
        "sourceFileTypes": list(args.source_file_type),
        "parserVersions": list(args.parser_version),
        "expectedIndexVersion": args.expected_index_version,
        "allowUnscoped": bool(args.allow_unscoped),
        "dryRun": bool(args.dry_run),
        "batchSize": args.batch_size,
        "limit": args.limit,
        "maxCycles": args.max_cycles,
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


def validate_scope(args: argparse.Namespace, document_version_ids: list[str]) -> None:
    synthetic = argparse.Namespace(
        expected_index_version=args.expected_index_version,
        index_version=args.expected_index_version,
        dry_run=args.dry_run,
        allow_unscoped=args.allow_unscoped,
        document_version_id=None,
        document_version_ids=document_version_ids,
        source_file_id=None,
        source_file_ids=None,
        parsed_artifact_id=None,
        search_unit_id=None,
    )
    _validate_cli_args(synthetic)
    if not args.allow_unscoped and not document_version_ids:
        raise ValueError("documentVersionIds scope is required when allowUnscoped=false")


def load_scope_ids(args: argparse.Namespace) -> list[str]:
    ids: set[str] = set(args.document_version_id or [])
    gold = Path(args.gold)
    if gold.exists():
        with gold.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                docv = (row.get("expected_document_version_id") or "").strip()
                if docv:
                    ids.add(docv)
    return sorted(ids)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--document-version-id", action="append", default=None)
    parser.add_argument("--source-file-type", action="append", default=list(DEFAULT_SOURCE_FILE_TYPES))
    parser.add_argument("--parser-version", action="append", default=list(DEFAULT_PARSER_VERSIONS))
    parser.add_argument("--expected-index-version", default=DEFAULT_INDEX_VERSION)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--max-cycles", type=int, default=200)
    parser.add_argument("--stale-after-seconds", type=int, default=None)
    parser.add_argument("--allow-unscoped", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
