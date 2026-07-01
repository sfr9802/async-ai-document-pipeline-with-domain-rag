from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from ai.eval.actual_rag_eval import (  # noqa: E402
    SOURCE_NATIVE_BGE_M3_INDEX_DIR,
    SOURCE_NATIVE_SOURCE_REGISTRY_PATH,
    SourceNativeCorpusLoader,
)
from ai.eval.report_paths import ACTUAL_RAG_REPORT_ROOT  # noqa: E402
from ai.eval.weaviate_source_atom import (  # noqa: E402
    BgeM3EmbeddingBuilder,
    WEAVIATE_CANDIDATE_SURFACE_COMPLETE_MANIFEST_SCHEMA_VERSION,
    WEAVIATE_ROUTE_SELECTED_CANDIDATE_SURFACE_V2_COLLECTION,
    WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V1,
    WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2,
    WEAVIATE_STREAMING_BGE_M3_VECTOR_SOURCE,
    WeaviateSourceAtomConfig,
    WeaviateSourceAtomIndexer,
    WeaviateUnavailableError,
)


DEFAULT_MANIFEST_PATH = ACTUAL_RAG_REPORT_ROOT / "weaviate_source_atom_index_manifest_nonprod" / "index_manifest.json"
DEFAULT_CHECKPOINT_PATH = ACTUAL_RAG_REPORT_ROOT / "weaviate_source_atom_index_manifest_nonprod" / "index_checkpoint.json"
DEFAULT_V2_MANIFEST_PATH = ACTUAL_RAG_REPORT_ROOT / "weaviate_source_atom_index_manifest_nonprod_v2" / "index_manifest.json"
DEFAULT_V2_CHECKPOINT_PATH = ACTUAL_RAG_REPORT_ROOT / "weaviate_source_atom_index_manifest_nonprod_v2" / "index_checkpoint.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index SourceAtom records into a non-production Weaviate collection.")
    parser.add_argument(
        "--source-native-index-dir",
        default=str(SOURCE_NATIVE_BGE_M3_INDEX_DIR),
        help=(
            "Directory containing search_view_manifest.jsonl for SourceAtom/EvidenceBundle source-native units. "
            "The Weaviate indexer reads only the manifest text/metadata from this directory; it does not read "
            "faiss.index or build.json."
        ),
    )
    parser.add_argument(
        "--source-atom-registry-path",
        default=str(SOURCE_NATIVE_SOURCE_REGISTRY_PATH),
        help="SourceAtom registry path to hash into the index manifest.",
    )
    parser.add_argument(
        "--manifest-path",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Output JSON manifest path for indexing success or explicit failure.",
    )
    parser.add_argument(
        "--schema-version",
        default="",
        choices=["", WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V1, WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2],
        help=(
            "SourceAtom schema/index version. Defaults to environment/config v1. "
            "When set to weaviate_source_atom_v2 with no explicit collection, the CLI uses SourceAtomNonprodV2."
        ),
    )
    parser.add_argument(
        "--weaviate-collection-name",
        default="",
        help="Optional non-production Weaviate collection override, for example SourceAtomNonprodV2.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional non-production smoke limit; 0 indexes all loaded units.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="Streaming BGE-M3 embedding/upsert batch size. Defaults to 32.",
    )
    parser.add_argument(
        "--vector-source",
        default=WEAVIATE_STREAMING_BGE_M3_VECTOR_SOURCE,
        choices=[WEAVIATE_STREAMING_BGE_M3_VECTOR_SOURCE],
        help=(
            "Vector source for Weaviate upsert. The active ingestion path streams local sentence-transformers "
            "BAAI/bge-m3 embeddings directly into Weaviate; FAISS vector transfer is rejected."
        ),
    )
    parser.add_argument(
        "--checkpoint-path",
        default=str(DEFAULT_CHECKPOINT_PATH),
        help="Checkpoint JSON path used to resume successful streaming BGE-M3 upsert batches.",
    )
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="Delete the non-production checkpoint before indexing, then write a fresh streaming checkpoint.",
    )
    parser.add_argument(
        "--synthesize-xlsx-row-value-bundles",
        action="store_true",
        help=(
            "Candidate-surface-only materialization: synthesize source-owned XLSX row/value table_row "
            "records from manifest snapshots so axes and answer values can be retrieved together. "
            "Does not read raw XLSX files, mutate source registry, or change default indexing."
        ),
    )
    parser.add_argument(
        "--xlsx-workbook-snapshot-path",
        dest="xlsx_workbook_snapshot_paths",
        action="append",
        default=[],
        help=(
            "Optional explicit xlsx-extract-v2-hidden-safe workbook JSON snapshot path used only at index time "
            "to co-materialize same-row date aliases into synthesized XLSX row/value bundles. May be repeated. "
            "Does not parse raw XLSX files or run at query time."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    started = time.perf_counter()
    config = WeaviateSourceAtomConfig.from_env()
    schema_version = args.schema_version or config.schema_version
    collection_name = args.weaviate_collection_name or config.collection_name
    env_collection_set = bool(
        os.environ.get("WEAVIATE_COLLECTION_SOURCE_ATOM")
        or os.environ.get("ACTUAL_RAG_EVAL_WEAVIATE_COLLECTION_SOURCE_ATOM")
    )
    if (
        schema_version == WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2
        and not args.weaviate_collection_name
        and not env_collection_set
        and collection_name == "SourceAtomNonprod"
    ):
        collection_name = "SourceAtomNonprodV2"
    config = replace(config, schema_version=schema_version, collection_name=collection_name)
    manifest_path = Path(args.manifest_path)
    checkpoint_path = Path(args.checkpoint_path) if args.checkpoint_path else None
    if schema_version == WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2:
        if Path(args.manifest_path) == DEFAULT_MANIFEST_PATH:
            manifest_path = DEFAULT_V2_MANIFEST_PATH
        if checkpoint_path == DEFAULT_CHECKPOINT_PATH:
            checkpoint_path = DEFAULT_V2_CHECKPOINT_PATH
    candidate_surface_collection = "CandidateSurface" in config.collection_name
    candidate_surface_recreate_v2 = config.collection_name == WEAVIATE_ROUTE_SELECTED_CANDIDATE_SURFACE_V2_COLLECTION
    collection_recreate_requested = bool(args.reset_checkpoint and candidate_surface_recreate_v2)
    indexer: WeaviateSourceAtomIndexer | None = None
    loader = SourceNativeCorpusLoader(
        search_view_manifest_path=Path(args.source_native_index_dir) / "search_view_manifest.jsonl",
        source_atom_registry_path=Path(args.source_atom_registry_path),
        synthesize_xlsx_row_value_bundles=bool(args.synthesize_xlsx_row_value_bundles),
        xlsx_workbook_snapshot_paths=[Path(path) for path in args.xlsx_workbook_snapshot_paths],
    )
    try:
        def progress(event: dict) -> None:
            print(json.dumps({"status": "indexing", **event}, ensure_ascii=False, sort_keys=True), file=sys.stderr)

        batch_size = int(args.batch_size or 32)
        limit = max(0, int(args.limit or 0))
        full_corpus_index_requested = limit == 0
        indexer = WeaviateSourceAtomIndexer(
            config=config,
            embedding_builder=BgeM3EmbeddingBuilder(
                model_name=config.embedding_model,
                device=config.embedding_device,
                batch_size=batch_size,
            ),
            progress_callback=progress,
        )
        if args.reset_checkpoint and checkpoint_path is not None and checkpoint_path.exists():
            checkpoint_path.unlink()

        def iter_limited_units():
            count = 0
            for unit in loader.iter_units():
                if limit > 0 and count >= limit:
                    break
                count += 1
                yield unit

        manifest = indexer.index_records_streaming(
            iter_limited_units(),
            checkpoint_path=checkpoint_path,
            source_atom_registry_path=Path(args.source_atom_registry_path),
            total_count=limit if limit > 0 else None,
            recreate_collection=collection_recreate_requested,
        )
        manifest["index_vector_source"] = args.vector_source
        manifest["manifest_path"] = manifest_path.as_posix()
        manifest["checkpoint_path"] = checkpoint_path.as_posix() if checkpoint_path is not None else ""
        manifest["checkpoint_resume_enabled"] = checkpoint_path is not None
        manifest["collection_recreate_requested"] = collection_recreate_requested
        manifest["collection_recreated_this_run"] = bool(manifest.get("collection_recreated_this_run"))
        manifest["synthesize_xlsx_row_value_bundles"] = bool(args.synthesize_xlsx_row_value_bundles)
        manifest["index_limit"] = limit
        manifest["candidate_surface_full_corpus_index"] = full_corpus_index_requested
        candidate_surface_schema_v2 = str(manifest.get("schema_version_source_atom") or "").strip() == WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2
        candidate_surface_complete = False
        if (
            candidate_surface_collection
            and candidate_surface_recreate_v2
            and candidate_surface_schema_v2
            and args.synthesize_xlsx_row_value_bundles
        ):
            try:
                indexed_count = int(manifest.get("indexed_count") or 0)
                skipped_count = int(manifest.get("skipped_count") or 0)
                failed_count = int(manifest.get("failed_count") or 0)
                upserted_count_this_run = int(manifest.get("upserted_count_this_run") or 0)
            except (TypeError, ValueError):
                indexed_count = 0
                skipped_count = 0
                failed_count = 1
                upserted_count_this_run = -1
            candidate_surface_complete = bool(
                indexed_count > 0
                and upserted_count_this_run == indexed_count
                and skipped_count == 0
                and failed_count == 0
                and manifest.get("checkpoint_resumed") is False
                and manifest.get("collection_recreated_this_run") is True
                and full_corpus_index_requested
            )
        manifest["candidate_surface_complete_manifest"] = candidate_surface_complete
        manifest["candidate_surface_complete_manifest_schema_version"] = (
            WEAVIATE_CANDIDATE_SURFACE_COMPLETE_MANIFEST_SCHEMA_VERSION if candidate_surface_complete else ""
        )
        manifest["candidate_surface_metric_blocked_until_complete_manifest"] = (
            candidate_surface_collection and not candidate_surface_complete
        )
        manifest["candidate_surface_restart_policy"] = (
            "recreate_collection_with_fresh_manifest_v2"
            if candidate_surface_recreate_v2
            else ("dirty_partial_reindex_required" if candidate_surface_collection else "")
        )
        manifest["source_registry_mutated"] = False
        manifest["latest_current_mutated"] = False
        manifest["official_metric_input_rows"] = 0
        manifest["source_native_loader"] = loader.describe()
        manifest["valid"] = True
        manifest["python_local_corpus_scan_used_for_candidate_generation"] = False
        manifest["source_native_layered_retrieval_used_for_candidate_generation"] = False
        _write_json(manifest_path, manifest)
        print(json.dumps({"status": "completed", "manifest_path": manifest_path.as_posix(), "indexed_count": manifest["indexed_count"]}, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        limit = max(0, int(getattr(args, "limit", 0) or 0))
        failure = {
            "schema_version": "weaviate_source_atom_index_manifest_v1",
            "valid": False,
            "vector_db_backend": "weaviate",
            "collection_name": config.collection_name,
            "weaviate_url_hash": config.url_hash,
            "production_namespace": config.production_namespace,
            "indexed_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "fallback_reason": reason,
            "fallback_action": "fix_weaviate_connection_or_configuration_then_rerun_index_command",
            "index_vector_source": getattr(args, "vector_source", WEAVIATE_STREAMING_BGE_M3_VECTOR_SOURCE),
            "checkpoint_path": checkpoint_path.as_posix() if checkpoint_path is not None else "",
            "checkpoint_resume_enabled": checkpoint_path is not None,
            "collection_recreate_requested": collection_recreate_requested,
            "collection_recreated_this_run": False,
            "synthesize_xlsx_row_value_bundles": bool(getattr(args, "synthesize_xlsx_row_value_bundles", False)),
            "index_limit": limit,
            "candidate_surface_full_corpus_index": limit == 0,
            "candidate_surface_complete_manifest": False,
            "candidate_surface_complete_manifest_schema_version": "",
            "candidate_surface_metric_blocked_until_complete_manifest": "CandidateSurface" in config.collection_name,
            "candidate_surface_restart_policy": (
                "recreate_collection_with_fresh_manifest_v2"
                if config.collection_name.endswith("CandidateSurfaceV2")
                else ("dirty_partial_reindex_required" if "CandidateSurface" in config.collection_name else "")
            ),
            "source_registry_mutated": False,
            "latest_current_mutated": False,
            "official_metric_input_rows": 0,
            "python_local_corpus_scan_used_for_candidate_generation": False,
            "source_native_layered_retrieval_used_for_candidate_generation": False,
            "diagnostic_hash_vector_used": False,
            "faiss_used_for_index_seed": False,
            "faiss_used_for_active_retrieval": False,
            "searchunit_searchview_used_as_candidate_surface": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 6),
            "manifest_path": manifest_path.as_posix(),
        }
        _write_json(manifest_path, failure)
        print(json.dumps({"status": "failed", "manifest_path": manifest_path.as_posix(), "fallback_reason": reason}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2 if isinstance(exc, WeaviateUnavailableError) else 1
    finally:
        if indexer is not None:
            close = getattr(indexer.client, "close", None)
            if callable(close):
                close()


if __name__ == "__main__":
    raise SystemExit(main())
