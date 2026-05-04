"""CLI entrypoint for SearchUnit indexing."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from app.capabilities.rag.embeddings import (
    SentenceTransformerEmbedder,
    resolve_max_seq_length,
)
from app.capabilities.rag.faiss_index import FaissIndex
from app.capabilities.rag.metadata_store import RagMetadataStore
from app.capabilities.rag.search_unit_indexing import SearchUnitVectorIndexer
from app.clients.core_api_client import CoreApiClient
from app.core.config import WorkerSettings
from app.core.logging import configure_logging
from app.services.search_unit_indexing_loop import SearchUnitIndexingWorker

log = logging.getLogger(__name__)


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging()
    try:
        _validate_cli_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    if not args.once and not args.loop:
        args.once = True
    index_version = _resolved_index_version(args)

    settings = WorkerSettings()
    max_seq_length = resolve_max_seq_length(settings.rag_embedding_max_seq_length)
    core_api = CoreApiClient(
        settings.core_api_base_url,
        settings.core_api_request_timeout_seconds,
        settings.internal_secret,
    )
    try:
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
            index_version=index_version,
            embedding_text_variant=settings.rag_embedding_text_variant,
            max_seq_length=max_seq_length,
        )
        worker = SearchUnitIndexingWorker(
            core_api=core_api,
            indexer=indexer,
            worker_id=settings.worker_id,
            batch_size=args.batch_size,
            stale_after_seconds=args.stale_after_seconds,
            source_file_id=args.source_file_id,
            source_file_ids=args.source_file_ids,
            document_version_id=args.document_version_id,
            document_version_ids=args.document_version_ids,
            parsed_artifact_id=args.parsed_artifact_id,
            search_unit_ids=args.search_unit_id,
            source_file_types=args.source_file_type,
            parser_versions=args.parser_version,
            expected_index_version=args.expected_index_version,
            limit=args.limit,
            allow_unscoped=args.allow_unscoped,
        )

        if args.loop:
            worker.run_loop(
                interval_seconds=args.interval_seconds,
                dry_run=args.dry_run,
            )
        else:
            summary = worker.run_once(dry_run=args.dry_run)
            log.info("SearchUnit indexing once summary: %s", summary)
        return 0
    except KeyboardInterrupt:
        log.info("SearchUnit indexing loop interrupted")
        return 0
    finally:
        core_api.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Claim pending SearchUnits from core-api and index them into ragmeta/FAISS.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one claim/index/complete cycle.")
    mode.add_argument("--loop", action="store_true", help="Run continuously until interrupted.")
    parser.add_argument("--batch-size", type=int, default=50, help="SearchUnit claim batch size.")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=10.0,
        help="Sleep interval between loop iterations.",
    )
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=None,
        help="Ask Spring to reclaim stale EMBEDDING claims older than this many seconds.",
    )
    parser.add_argument(
        "--index-version",
        default=None,
        help="Optional index_version. Omit to use the currently loaded FAISS build version.",
    )
    parser.add_argument(
        "--source-file-id",
        default=None,
        help="Restrict claim to one source_file_id. Use for canary/batch isolation.",
    )
    parser.add_argument(
        "--source-file-ids",
        action="append",
        default=None,
        help="Restrict claim to a source_file_id. Repeat for batch isolation.",
    )
    parser.add_argument(
        "--document-version-id",
        default=None,
        help="Restrict claim to one document_version_id.",
    )
    parser.add_argument(
        "--document-version-ids",
        action="append",
        default=None,
        help="Restrict claim to a document_version_id. Repeat for batch isolation.",
    )
    parser.add_argument(
        "--parsed-artifact-id",
        default=None,
        help="Restrict claim to one parsed_artifact_id.",
    )
    parser.add_argument(
        "--search-unit-id",
        action="append",
        default=None,
        help="Restrict claim to an explicit SearchUnit id. Repeat for canary sets.",
    )
    parser.add_argument(
        "--source-file-type",
        action="append",
        default=None,
        help="Restrict claim to a source_file_type such as SPREADSHEET or PDF. Repeat as needed.",
    )
    parser.add_argument(
        "--parser-version",
        action="append",
        default=None,
        help="Restrict claim to a parser_version. Repeat as needed.",
    )
    parser.add_argument(
        "--expected-index-version",
        default=None,
        help="Fail claim unless Spring is configured for this candidate index version.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Explicit claim limit. Overrides batch-size at the Spring claim boundary.",
    )
    parser.add_argument(
        "--allow-unscoped",
        action="store_true",
        help="Allow an unscoped claim. Intended for local diagnostics only, not canary/batch runs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate CLI/config wiring without claiming SearchUnits or writing indexes.",
    )
    return parser


def _resolved_index_version(args: argparse.Namespace) -> str | None:
    return args.index_version or args.expected_index_version


def _validate_cli_args(args: argparse.Namespace) -> None:
    if args.expected_index_version and args.index_version and args.index_version != args.expected_index_version:
        raise ValueError(
            "--index-version must match --expected-index-version when both are provided "
            f"(index_version={args.index_version!r}, expected_index_version={args.expected_index_version!r})"
        )
    resolved_index_version = _resolved_index_version(args)
    if resolved_index_version == "rag-ingestion-v2-candidate" and not args.expected_index_version:
        args.expected_index_version = resolved_index_version
    if args.dry_run:
        return
    if args.allow_unscoped:
        return
    has_hard_identity_scope = _has_hard_identity_scope(args)
    if resolved_index_version is None:
        if not has_hard_identity_scope:
            raise ValueError(
                "non-dry-run indexing without --index-version/--expected-index-version "
                "requires a hard identity scope, or explicit --allow-unscoped"
            )
        return
    if resolved_index_version != "rag-ingestion-v2-candidate":
        return
    if not has_hard_identity_scope:
        raise ValueError(
            "non-dry-run candidate indexing with rag-ingestion-v2-candidate "
            "requires a hard identity scope (--document-version-id/--document-version-ids, "
            "--source-file-id/--source-file-ids, --parsed-artifact-id, or --search-unit-id), "
            "or explicit --allow-unscoped"
        )


def _has_hard_identity_scope(args: argparse.Namespace) -> bool:
    return any(
        (
            args.document_version_id,
            bool(args.document_version_ids),
            args.source_file_id,
            bool(args.source_file_ids),
            args.parsed_artifact_id,
            bool(args.search_unit_id),
        )
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
