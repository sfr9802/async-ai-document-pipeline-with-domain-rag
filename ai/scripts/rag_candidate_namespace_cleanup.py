"""Scoped cleanup/retire policy for candidate SearchUnit namespace drift.

The script is scope-only: it never deletes the whole candidate namespace. In
apply mode it resets scoped SearchUnits with stale/mismatched candidate state
back to PENDING and removes their candidate embedding_record rows so the
SearchUnit indexer can upsert a fresh vector/chunk/callback result.

It intentionally does not pre-delete ragmeta.chunks. The FAISS writer rebuilds
from existing ragmeta rows and updates chunks by stable chunk_id/index_id; a
pre-delete can create non-contiguous faiss_row_id gaps.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_pdf_v0.csv")
DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/candidate_namespace_cleanup_upsert_report.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_INDEX_VERSION = "rag-ingestion-v2-pdf-candidate-v1"
DEFAULT_SOURCE_FILE_TYPES = ("PDF",)
DEFAULT_PARSER_VERSIONS = ("pdf-extract-v1", "pdf-extract-v2")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    warnings: list[str] = []
    blockers: list[str] = []
    docvs = load_scope_ids(args, warnings)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    mutations: dict[str, Any] = {
        "apply": bool(args.apply),
        "reset_search_unit_count": 0,
        "deleted_embedding_record_count": 0,
        "deleted_ragmeta_chunk_count": 0,
        "ragmeta_chunks_predelete_policy": "not_deleted_to_preserve_faiss_row_contiguity_before_upsert",
    }
    try:
        with connect(db_dsn) as conn:
            before = inspect_scope(
                conn,
                document_version_ids=docvs,
                source_file_types=[item.upper() for item in args.source_file_type],
                parser_versions=list(args.parser_version),
                expected_index_version=args.expected_index_version,
            )
            if args.apply:
                mutations.update(apply_cleanup(
                    conn,
                    document_version_ids=docvs,
                    source_file_types=[item.upper() for item in args.source_file_type],
                    parser_versions=list(args.parser_version),
                    expected_index_version=args.expected_index_version,
                ))
            after = inspect_scope(
                conn,
                document_version_ids=docvs,
                source_file_types=[item.upper() for item in args.source_file_type],
                parser_versions=list(args.parser_version),
                expected_index_version=args.expected_index_version,
            )
    except Exception as exc:
        blockers.append(f"DB inspection/cleanup failed: {type(exc).__name__}: {exc}")

    payload = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "FAIL" if blockers else "PASS",
        "scope": "full72_candidate_namespace_cleanup_upsert",
        "document_version_ids": docvs,
        "sourceFileTypes": list(args.source_file_type),
        "parserVersions": list(args.parser_version),
        "expectedIndexVersion": args.expected_index_version,
        "policy": {
            "allow_global_delete": False,
            "cleanup_scope": "documentVersionIds + sourceFileTypes + parserVersions",
            "vector_id_contract": "index_version:search_unit.index_id",
            "upsert_contract": "ragmeta.chunks ON CONFLICT (index_version, chunk_id)",
            "retire_policy": "reset scoped stale/mismatched SearchUnits to PENDING and delete scoped embedding_record rows only",
            "ragmeta_chunk_policy": "leave chunks in place for the staged FAISS rewrite/upsert to replace by stable chunk_id",
        },
        "before": before,
        "mutations": mutations,
        "after": after,
        "blockers": blockers,
        "warnings": warnings,
    }
    write_json(Path(args.output), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "PASS" else 2


def inspect_scope(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, Any]:
    summary = fetch_one(conn, """
        WITH scoped AS (
          SELECT su.*
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = ANY(%s)
             AND su.parser_version = ANY(%s)
        )
        SELECT count(*)::int AS scoped_count,
               count(*) FILTER (WHERE su.index_version = %s)::int AS search_unit_candidate_index_count,
               count(*) FILTER (WHERE er.id IS NOT NULL)::int AS embedding_record_count,
               count(*) FILTER (WHERE c.chunk_id IS NOT NULL)::int AS ragmeta_chunk_count,
               count(*) FILTER (
                 WHERE er.id IS NOT NULL
                   AND er.vector_id IS DISTINCT FROM (%s || ':' || su.index_id)
               )::int AS embedding_record_vector_id_mismatch_count,
               count(*) FILTER (
                 WHERE c.chunk_id IS NOT NULL
                   AND c.extra_json->>'vectorId' IS DISTINCT FROM (%s || ':' || su.index_id)
               )::int AS ragmeta_chunk_vector_id_mismatch_count,
               count(*) FILTER (
                 WHERE c.chunk_id IS NOT NULL
                   AND er.id IS NOT NULL
                   AND c.extra_json->>'embeddingTextSha256' IS DISTINCT FROM er.embedding_text_sha256
               )::int AS chunk_embedding_text_sha_mismatch_count,
               count(*) FILTER (
                 WHERE su.embedding_status = 'EMBEDDED'
                   AND (
                        su.index_version IS DISTINCT FROM %s
                     OR er.id IS NULL
                     OR c.chunk_id IS NULL
                     OR er.vector_id IS DISTINCT FROM (%s || ':' || su.index_id)
                     OR c.extra_json->>'vectorId' IS DISTINCT FROM (%s || ':' || su.index_id)
                   )
               )::int AS stale_embedded_candidate_state_count
          FROM scoped su
          LEFT JOIN embedding_record er
            ON er.search_unit_id = su.id
           AND er.index_version = %s
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
    """, (
        document_version_ids,
        source_file_types,
        parser_versions,
        expected_index_version,
        expected_index_version,
        expected_index_version,
        expected_index_version,
        expected_index_version,
        expected_index_version,
        expected_index_version,
        expected_index_version,
    ))
    samples = fetch_all(conn, """
        SELECT su.id,
               su.document_version_id,
               su.source_file_name,
               su.source_file_type,
               su.parser_version,
               su.embedding_status,
               su.index_version,
               su.index_id,
               er.vector_id AS embedding_record_vector_id,
               c.extra_json->>'vectorId' AS chunk_vector_id
          FROM search_unit su
          LEFT JOIN embedding_record er
            ON er.search_unit_id = su.id
           AND er.index_version = %s
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
         WHERE su.document_version_id = ANY(%s)
           AND upper(coalesce(su.source_file_type, '')) = ANY(%s)
           AND su.parser_version = ANY(%s)
           AND (
                su.index_version = %s
             OR er.id IS NOT NULL
             OR c.chunk_id IS NOT NULL
           )
         ORDER BY su.document_version_id, su.id
         LIMIT 25
    """, (
        expected_index_version,
        expected_index_version,
        document_version_ids,
        source_file_types,
        parser_versions,
        expected_index_version,
    ))
    return {
        "summary": row_to_plain(summary),
        "sample_existing_candidate_entries": rows_to_plain(samples),
    }


def apply_cleanup(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("""
            WITH scoped AS (
              SELECT su.id
                FROM search_unit su
                LEFT JOIN embedding_record er
                  ON er.search_unit_id = su.id
                 AND er.index_version = %s
                LEFT JOIN ragmeta.chunks c
                  ON c.chunk_id = su.index_id
                 AND c.index_version = %s
               WHERE su.document_version_id = ANY(%s)
                 AND upper(coalesce(su.source_file_type, '')) = ANY(%s)
                 AND su.parser_version = ANY(%s)
                 AND (
                      su.index_version IS NOT NULL
                   OR er.id IS NOT NULL
                   OR c.chunk_id IS NOT NULL
                 )
                 AND (
                      su.embedding_status IS DISTINCT FROM 'PENDING'
                   OR su.index_version IS NOT NULL
                   OR su.embedding_claim_token IS NOT NULL
                   OR su.embedding_claimed_at IS NOT NULL
                   OR er.id IS NOT NULL
                 )
            ),
            deleted AS (
              DELETE FROM embedding_record er
               USING scoped s
               WHERE er.search_unit_id = s.id
                 AND er.index_version = %s
               RETURNING er.id
            ),
            updated AS (
              UPDATE search_unit su
                 SET embedding_status = 'PENDING',
                     index_version = NULL,
                     indexed_content_sha256 = NULL,
                     embedding_claim_token = NULL,
                     embedding_claimed_at = NULL,
                     embedding_status_detail = NULL,
                     embedded_at = NULL,
                     updated_at = now()
                FROM scoped s
               WHERE su.id = s.id
               RETURNING su.id
            )
            SELECT (SELECT count(*)::int FROM updated) AS reset_search_unit_count,
                   (SELECT count(*)::int FROM deleted) AS deleted_embedding_record_count
        """, (
            expected_index_version,
            expected_index_version,
            document_version_ids,
            source_file_types,
            parser_versions,
            expected_index_version,
        ))
        row = cur.fetchone()
    return {
        "apply": True,
        "reset_search_unit_count": int(row[0] if row else 0),
        "deleted_embedding_record_count": int(row[1] if row else 0),
        "deleted_ragmeta_chunk_count": 0,
        "ragmeta_chunks_predelete_policy": "not_deleted_to_preserve_faiss_row_contiguity_before_upsert",
    }


def load_scope_ids(args: argparse.Namespace, warnings: list[str]) -> list[str]:
    ids: set[str] = set(args.document_version_id or [])
    gold = Path(args.gold)
    if gold.exists():
        with gold.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                docv = (row.get("expected_document_version_id") or "").strip()
                if docv:
                    ids.add(docv)
    else:
        warnings.append(f"Gold query file not found: {gold}")
    return sorted(ids)


def connect(dsn: str) -> Any:
    try:
        import psycopg2  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg2 is required for live DB inspection") from exc
    return psycopg2.connect(dsn)


def fetch_one(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return {}
        names = [desc[0] for desc in cur.description]
        return dict(zip(names, row))


def fetch_all(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        names = [desc[0] for desc in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


def rows_to_plain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row_to_plain(row) for row in rows]


def row_to_plain(row: dict[str, Any]) -> dict[str, Any]:
    return {key: plain_value(value) for key, value in row.items()}


def plain_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


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
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--expected-index-version", default=DEFAULT_INDEX_VERSION)
    parser.add_argument("--document-version-id", action="append", default=None)
    parser.add_argument("--source-file-type", action="append", default=list(DEFAULT_SOURCE_FILE_TYPES))
    parser.add_argument("--parser-version", action="append", default=list(DEFAULT_PARSER_VERSIONS))
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
