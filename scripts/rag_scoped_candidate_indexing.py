"""Run scoped SearchUnit candidate indexing until the scope is empty.

This is a reporting wrapper around the existing worker components. It refuses
unscoped candidate indexing unless --allow-unscoped is explicitly supplied,
and its default scope is the unique expected_document_version_id values from
the full72 gold CSV.
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
    scope = load_scope(args)
    args.expected_index_version = resolve_expected_index_version(args, scope)
    document_version_ids = scope["document_version_ids"]
    source_file_ids = scope["source_file_ids"]
    source_file_types = args.source_file_type or scope["source_file_types"] or list(DEFAULT_SOURCE_FILE_TYPES)
    parser_versions = args.parser_version or scope["parser_versions"] or list(DEFAULT_PARSER_VERSIONS)
    validate_scope(args, document_version_ids, source_file_ids)
    run_started_at = utc_timestamp()
    cycles: list[dict[str, Any]] = []
    status = "PASS"
    blockers: list[str] = []

    settings = WorkerSettings()
    resolved_index_dir = Path(args.artifact_dir or settings.rag_index_dir)
    if args.enrich_existing_report:
        payload = enrich_existing_report(
            Path(args.output),
            args=args,
            scope=scope,
            document_version_ids=document_version_ids,
            source_file_ids=source_file_ids,
            source_file_types=list(source_file_types),
            parser_versions=list(parser_versions),
            resolved_index_dir=resolved_index_dir,
        )
        write_json(Path(args.output), payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload.get("status") == "PASS" else 2

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
        index = FaissIndex(resolved_index_dir)
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
            source_file_types=list(source_file_types),
            parser_versions=list(parser_versions),
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
        "track": "C",
        "phase": "C4",
        "report_role": "scoped_candidate_indexing",
        "source_file_type": "PDF" if list(source_file_types) == ["PDF"] else None,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "index_version": args.expected_index_version,
        "artifact_dir": str(resolved_index_dir),
        "resolvedIndexDir": str(resolved_index_dir),
        "retrieval_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "scope": scope["scope_name"],
        "scopeReport": str(args.scope_report) if args.scope_report else None,
        "scopeExpectedIndexVersion": scope.get("expected_index_version"),
        "documentVersionIds": document_version_ids,
        "sourceFileIds": source_file_ids,
        "sourceFileTypes": list(source_file_types),
        "parserVersions": list(parser_versions),
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
        "artifact_contract": artifact_contract(resolved_index_dir, args.expected_index_version),
        "blockers": blockers,
    }
    write_json(Path(args.output), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 2


def validate_scope(args: argparse.Namespace, document_version_ids: list[str], source_file_ids: list[str]) -> None:
    synthetic = argparse.Namespace(
        expected_index_version=args.expected_index_version,
        index_version=args.expected_index_version,
        dry_run=args.dry_run,
        allow_unscoped=args.allow_unscoped,
        document_version_id=None,
        document_version_ids=document_version_ids,
        source_file_id=None,
        source_file_ids=source_file_ids,
        parsed_artifact_id=None,
        search_unit_id=None,
    )
    _validate_cli_args(synthetic)
    if not args.allow_unscoped and not (document_version_ids or source_file_ids):
        raise ValueError("documentVersionIds or sourceFileIds scope is required when allowUnscoped=false")


def load_scope_ids(args: argparse.Namespace) -> list[str]:
    return load_scope(args)["document_version_ids"]


def resolve_expected_index_version(args: argparse.Namespace, scope: dict[str, Any]) -> str:
    scope_expected = clean(scope.get("expected_index_version"))
    cli_expected = clean(args.expected_index_version)
    if scope_expected and cli_expected and scope_expected != cli_expected:
        raise ValueError(
            "scope report expectedIndexVersion must match --expected-index-version "
            f"(scope={scope_expected!r}, cli={cli_expected!r})"
        )
    return cli_expected or scope_expected or DEFAULT_INDEX_VERSION


def load_scope(args: argparse.Namespace) -> dict[str, Any]:
    ids: set[str] = set(args.document_version_id or [])
    source_file_ids: set[str] = set(args.source_file_id or [])
    source_file_types: set[str] = set()
    parser_versions: set[str] = set()
    expected_index_version = ""
    scope_name = "full72_document_version_scoped_candidate_indexing"

    if args.scope_report:
        scope_name = "scope_report_scoped_candidate_indexing"
        report = read_json(Path(args.scope_report))
        ids.update(extract_list(report, ("scope", "document_version_ids")))
        ids.update(extract_list(report, ("indexing_cli_scope", "documentVersionIds")))
        source_file_ids.update(extract_list(report, ("scope", "source_file_ids")))
        source_file_ids.update(extract_list(report, ("indexing_cli_scope", "sourceFileIds")))
        source_file_types.update(extract_list(report, ("indexing_cli_scope", "sourceFileTypes")))
        if report.get("source_file_type"):
            source_file_types.add(str(report["source_file_type"]))
        parser_versions.update(extract_list(report, ("scope", "parser_versions")))
        parser_versions.update(extract_list(report, ("indexing_cli_scope", "parserVersions")))
        expected_index_version = clean(
            first_value(
                report.get("indexing_cli_scope") or {},
                "expectedIndexVersion",
                "indexVersion",
            )
            or report.get("index_version")
        )

    gold = Path(args.gold)
    if gold.exists() and (not args.scope_report or args.include_gold_scope):
        with gold.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                docv = (row.get("expected_document_version_id") or "").strip()
                if docv:
                    ids.add(docv)
    return {
        "scope_name": scope_name,
        "document_version_ids": sorted(ids),
        "source_file_ids": sorted(source_file_ids),
        "source_file_types": sorted(source_file_types),
        "parser_versions": sorted(parser_versions),
        "expected_index_version": expected_index_version,
    }


def extract_list(payload: dict[str, Any], path: tuple[str, ...]) -> list[str]:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return []
        value = value.get(key)
    if not isinstance(value, list):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def enrich_existing_report(
    output_path: Path,
    *,
    args: argparse.Namespace,
    scope: dict[str, Any],
    document_version_ids: list[str],
    source_file_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    resolved_index_dir: Path,
) -> dict[str, Any]:
    payload = read_json(output_path) if output_path.exists() else {}
    payload.update({
        "metadata_refreshed_at": utc_timestamp(),
        "track": "C",
        "phase": "C4",
        "report_role": payload.get("report_role") or "scoped_candidate_indexing",
        "source_file_type": "PDF" if source_file_types == ["PDF"] else payload.get("source_file_type"),
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "index_version": args.expected_index_version,
        "expectedIndexVersion": args.expected_index_version,
        "artifact_dir": str(resolved_index_dir),
        "resolvedIndexDir": str(resolved_index_dir),
        "retrieval_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "scope": payload.get("scope") or scope["scope_name"],
        "scopeReport": str(args.scope_report) if args.scope_report else payload.get("scopeReport"),
        "scopeExpectedIndexVersion": scope.get("expected_index_version"),
        "documentVersionIds": document_version_ids,
        "sourceFileIds": source_file_ids,
        "sourceFileTypes": source_file_types,
        "parserVersions": parser_versions,
        "allowUnscoped": bool(payload.get("allowUnscoped", args.allow_unscoped)),
        "dryRun": bool(payload.get("dryRun", args.dry_run)),
        "artifact_contract": artifact_contract(resolved_index_dir, args.expected_index_version),
        "metadata_refresh_note": (
            "Existing C4 indexing report was enriched without running indexing, retrieval, "
            "promotion, baseline updates, or cleanup."
        ),
    })
    return payload


def artifact_contract(path: Path, expected_index_version: str) -> dict[str, Any]:
    build_path = path / "build.json"
    manifest_path = path / "ingest_manifest.json"
    faiss_path = path / "faiss.index"
    build = read_json(build_path) if build_path.exists() else {}
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    return {
        "artifact_dir": str(path),
        "exists": path.exists(),
        "expected_index_version": expected_index_version,
        "build_json": artifact_file_identity(build_path),
        "ingest_manifest_json": artifact_file_identity(manifest_path),
        "faiss_index": artifact_file_identity(faiss_path),
        "build_index_version": build.get("index_version"),
        "manifest_index_version": manifest.get("index_version"),
        "build_matches_expected_index_version": build.get("index_version") == expected_index_version,
        "manifest_matches_expected_index_version": manifest.get("index_version") == expected_index_version,
    }


def artifact_file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else None,
        "sha256": file_sha256(path) if path.exists() else None,
    }


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def first_value(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--scope-report", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--document-version-id", action="append", default=None)
    parser.add_argument("--source-file-id", action="append", default=None)
    parser.add_argument("--source-file-type", action="append", default=None)
    parser.add_argument("--parser-version", action="append", default=None)
    parser.add_argument("--expected-index-version", default=None)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--enrich-existing-report", action="store_true")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--max-cycles", type=int, default=200)
    parser.add_argument("--stale-after-seconds", type=int, default=None)
    parser.add_argument("--allow-unscoped", action="store_true")
    parser.add_argument("--include-gold-scope", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return args


if __name__ == "__main__":
    sys.exit(main())
