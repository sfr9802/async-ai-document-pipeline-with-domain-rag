"""Classify full72 gold document-version scope for candidate indexing.

This report is read-only. It uses the unique expected_document_version_id
values from the gold CSV and classifies each value against the required
PDF/XLSX candidate parser/indexing contract.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_v0.csv")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/full72_docv_scope_classification_report.json")
DEFAULT_PLAN_OUTPUT = Path("eval/reports/rag-ingestion/missing_scope_docv_resolution_plan.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_INDEX_VERSION = "rag-ingestion-v2-candidate"
DEFAULT_SOURCE_FILE_TYPES = ("SPREADSHEET", "PDF")
DEFAULT_PARSER_VERSIONS = ("xlsx-extract-v2-hidden-safe", "pdf-extract-v1", "pdf-extract-v2")
EXPECTED_XLSX_HIDDEN_POLICY = "exclude_hidden"
EXPECTED_XLSX_HIDDEN_POLICY_VERSION = "exclude-hidden-v1"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gold_rows = read_gold(Path(args.gold))
    expected_docvs = sorted({
        row.get("expected_document_version_id", "").strip()
        for row in gold_rows
        if row.get("expected_document_version_id", "").strip()
    })
    by_docv = rows_by_docv(gold_rows)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    blockers: list[str] = []
    warnings: list[str] = []
    classifications: list[dict[str, Any]] = []
    candidates_by_file: dict[str, list[dict[str, Any]]] = {}

    try:
        with connect(db_dsn) as conn:
            classifications = [
                classify_docv(
                    conn,
                    docv,
                    gold_rows=by_docv.get(docv, []),
                    required_source_file_types=[item.upper() for item in args.source_file_type],
                    required_parser_versions=list(args.parser_version),
                    expected_index_version=args.expected_index_version,
                )
                for docv in expected_docvs
            ]
            file_names = sorted({
                row.get("expected_file_name", "").strip()
                for row in gold_rows
                if row.get("expected_file_name", "").strip()
            })
            candidates_by_file = {
                name: find_candidate_docvs(
                    conn,
                    name,
                    required_source_file_types=[item.upper() for item in args.source_file_type],
                    required_parser_versions=list(args.parser_version),
                    expected_index_version=args.expected_index_version,
                )
                for name in file_names
            }
    except Exception as exc:
        blockers.append(f"DB inspection failed: {type(exc).__name__}: {exc}")

    class_counts = Counter(item.get("class") for item in classifications)
    missing_scope = [
        item["document_version_id"]
        for item in classifications
        if item.get("class") in {"B", "C"}
    ]
    payload = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "FAIL" if blockers else "PASS",
        "scope": "full72_gold_document_version_id",
        "gold": {
            "path": str(args.gold),
            "row_count": len(gold_rows),
            "unique_expected_document_version_id_count": len(expected_docvs),
            "bucket_counts": dict(Counter(row.get("bucket", "") for row in gold_rows)),
            "document_version_row_counts": {
                docv: len(by_docv.get(docv, []))
                for docv in expected_docvs
            },
        },
        "required_contract": {
            "sourceFileTypes": list(args.source_file_type),
            "parserVersions": list(args.parser_version),
            "expectedIndexVersion": args.expected_index_version,
            "xlsxHiddenPolicy": EXPECTED_XLSX_HIDDEN_POLICY,
            "xlsxHiddenPolicyVersion": EXPECTED_XLSX_HIDDEN_POLICY_VERSION,
        },
        "class_definition": {
            "A": "required parser/source scope has candidate rows and all required-scope rows are PENDING",
            "B": "rows exist for the gold docv, but parser/source/index contract differs from required scope or rows are already mixed",
            "C": "document_version/search_unit row is absent from required scope or the gold binding is stale",
        },
        "class_counts": dict(class_counts),
        "missing_scope_document_version_ids": missing_scope,
        "document_versions": classifications,
        "candidate_docvs_by_file": candidates_by_file,
        "blockers": blockers,
        "warnings": warnings,
    }
    write_json(Path(args.output), payload)

    plan = build_resolution_plan(payload)
    write_json(Path(args.plan_output), plan)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if blockers else 0


def classify_docv(
    conn: Any,
    docv: str,
    *,
    gold_rows: list[dict[str, str]],
    required_source_file_types: list[str],
    required_parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, Any]:
    docv_row = fetch_one(conn, """
        SELECT dv.id,
               dv.source_file_name,
               dv.source_file_type,
               dv.parse_status,
               sf.id AS source_file_id,
               sf.file_type AS source_file_type_from_source_file,
               sf.status AS source_file_status,
               sf.status_detail AS source_file_status_detail
          FROM document_version dv
          LEFT JOIN source_file sf ON sf.id = dv.source_file_id
         WHERE dv.id = %s
    """, (docv,))
    groups = fetch_all(conn, """
        SELECT upper(coalesce(source_file_type, 'UNKNOWN')) AS source_file_type,
               coalesce(parser_version, 'UNKNOWN') AS parser_version,
               coalesce(embedding_status, 'UNKNOWN') AS embedding_status,
               coalesce(index_version, 'NULL') AS index_version,
               count(*)::int AS count
          FROM search_unit
         WHERE document_version_id = %s
         GROUP BY 1, 2, 3, 4
         ORDER BY 1, 2, 3, 4
    """, (docv,))
    required = fetch_one(conn, """
        SELECT count(*)::int AS scoped_count,
               count(*) FILTER (WHERE embedding_status = 'PENDING')::int AS pending_count,
               count(*) FILTER (WHERE embedding_status = 'EMBEDDED')::int AS embedded_count,
               count(*) FILTER (WHERE embedding_status IS DISTINCT FROM 'PENDING')::int AS non_pending_count,
               count(*) FILTER (WHERE index_version = %s)::int AS candidate_index_count,
               count(*) FILTER (
                 WHERE upper(coalesce(source_file_type, '')) = 'SPREADSHEET'
                   AND location_json->>'hidden_policy' IS DISTINCT FROM %s
               )::int AS xlsx_hidden_policy_mismatch_count,
               count(*) FILTER (
                 WHERE upper(coalesce(source_file_type, '')) = 'SPREADSHEET'
                   AND location_json->>'hidden_policy_version' IS DISTINCT FROM %s
               )::int AS xlsx_hidden_policy_version_mismatch_count
          FROM search_unit
         WHERE document_version_id = %s
           AND upper(coalesce(source_file_type, '')) = ANY(%s)
           AND parser_version = ANY(%s)
    """, (
        expected_index_version,
        EXPECTED_XLSX_HIDDEN_POLICY,
        EXPECTED_XLSX_HIDDEN_POLICY_VERSION,
        docv,
        required_source_file_types,
        required_parser_versions,
    ))
    scoped_count = int(required.get("scoped_count") or 0)
    pending_count = int(required.get("pending_count") or 0)
    embedded_count = int(required.get("embedded_count") or 0)
    all_rows = sum(int(row.get("count") or 0) for row in groups)
    reasons: list[str] = []
    classification = "C"
    action = "gold_rebind"

    if scoped_count > 0 and pending_count == scoped_count:
        classification = "A"
        action = "scoped_indexing"
        reasons.append("required parser/source scope has PENDING candidate rows")
    elif scoped_count > 0:
        classification = "B"
        action = "cleanup_or_verify_then_index"
        reasons.append("required parser/source scope exists but status/index mix is not all PENDING")
    elif all_rows > 0:
        classification = "B"
        action = "parser_scope_fix_or_reimport"
        reasons.append("gold docv has rows, but none match required parser/source scope")
    else:
        classification = "C"
        action = "gold_rebind_or_reimport"
        reasons.append("gold docv has no search_unit rows in this DB")

    if not docv_row:
        classification = "C"
        action = "gold_rebind_or_reimport"
        reasons.append("document_version row is absent; binding is stale")
    source_type = str(docv_row.get("source_file_type") or "").upper() if docv_row else ""
    if source_type == "SPREADSHEET" and scoped_count == 0 and all_rows > 0:
        action = "reimport_xlsx_hidden_safe_and_rebind"
    if source_type == "PDF" and scoped_count == 0 and all_rows > 0:
        action = "verify_pdf_parser_scope_or_rebind"
    if source_type == "PDF" and scoped_count > 0 and pending_count == scoped_count:
        action = "scoped_indexing"
    if embedded_count == scoped_count and scoped_count > 0:
        action = "already_embedded_verify_namespace"
        reasons.append("required parser/source rows are already EMBEDDED")

    return {
        "document_version_id": docv,
        "gold_row_count": len(gold_rows),
        "gold_bucket_counts": dict(Counter(row.get("bucket", "") for row in gold_rows)),
        "expected_file_name": first_nonblank(row.get("expected_file_name") for row in gold_rows),
        "source_sample_ids": sorted({
            row.get("source_sample_id", "").strip()
            for row in gold_rows
            if row.get("source_sample_id", "").strip()
        }),
        "document_version": row_to_plain(docv_row),
        "search_unit_groups": rows_to_plain(groups),
        "required_scope_summary": row_to_plain(required),
        "class": classification,
        "recommended_action": action,
        "reasons": reasons,
    }


def find_candidate_docvs(
    conn: Any,
    file_name: str,
    *,
    required_source_file_types: list[str],
    required_parser_versions: list[str],
    expected_index_version: str,
) -> list[dict[str, Any]]:
    rows = fetch_all(conn, """
        WITH grouped AS (
          SELECT document_version_id,
                 count(*)::int AS scoped_count,
                 count(*) FILTER (WHERE embedding_status = 'PENDING')::int AS pending_count,
                 count(*) FILTER (WHERE embedding_status = 'EMBEDDED')::int AS embedded_count,
                 count(*) FILTER (WHERE index_version = %s)::int AS candidate_index_count,
                 min(created_at) AS first_unit_at,
                 max(created_at) AS last_unit_at
            FROM search_unit
           WHERE source_file_name = %s
             AND upper(coalesce(source_file_type, '')) = ANY(%s)
             AND parser_version = ANY(%s)
           GROUP BY document_version_id
        )
        SELECT g.document_version_id,
               dv.source_file_type,
               dv.parse_status,
               dv.source_file_id,
               sf.status AS source_file_status,
               g.scoped_count,
               g.pending_count,
               g.embedded_count,
               g.candidate_index_count,
               g.first_unit_at,
               g.last_unit_at
          FROM grouped g
          LEFT JOIN document_version dv ON dv.id = g.document_version_id
          LEFT JOIN source_file sf ON sf.id = dv.source_file_id
         ORDER BY g.embedded_count DESC, g.last_unit_at DESC, g.document_version_id
         LIMIT 20
    """, (expected_index_version, file_name, required_source_file_types, required_parser_versions))
    return rows_to_plain(rows)


def build_resolution_plan(payload: dict[str, Any]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for item in payload.get("document_versions", []):
        docv = item.get("document_version_id")
        action = item.get("recommended_action")
        file_name = item.get("expected_file_name")
        candidate_docvs = (payload.get("candidate_docvs_by_file") or {}).get(file_name, [])
        selected = candidate_docvs[0]["document_version_id"] if candidate_docvs else None
        actions.append({
            "document_version_id": docv,
            "class": item.get("class"),
            "expected_file_name": file_name,
            "recommended_action": action,
            "candidate_rebind_document_version_id": selected,
            "candidate_options": candidate_docvs[:5],
            "notes": item.get("reasons", []),
        })
    return {
        "run_id": payload.get("run_id"),
        "generated_at": payload.get("generated_at"),
        "scope": payload.get("scope"),
        "status": payload.get("status"),
        "actions": actions,
        "missing_scope_document_version_ids": payload.get("missing_scope_document_version_ids", []),
        "policy": [
            "Use reimport/rebind for legacy XLSX parser scope.",
            "Use scoped indexing for required-scope PENDING PDF/XLSX rows.",
            "Do not use candidate snapshots or library_search as baseline/promotion evidence.",
        ],
    }


def rows_by_docv(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        docv = row.get("expected_document_version_id", "").strip()
        if docv:
            grouped[docv].append(row)
    return grouped


def read_gold(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def first_nonblank(values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


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
    parser.add_argument("--plan-output", default=str(DEFAULT_PLAN_OUTPUT))
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--expected-index-version", default=DEFAULT_INDEX_VERSION)
    parser.add_argument("--source-file-type", action="append", default=list(DEFAULT_SOURCE_FILE_TYPES))
    parser.add_argument("--parser-version", action="append", default=list(DEFAULT_PARSER_VERSIONS))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
