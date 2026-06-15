"""Report TEXT/PDF/XLSX RAG path-separation readiness.

The report is intentionally read-only. It inspects the live catalog/ragmeta
database plus any local eval/report artifacts that are present, then fails
closed when candidate PDF/XLSX rows do not satisfy the indexing contract.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/rag_path_separation_readiness.json")
DEFAULT_RETRIEVAL_REPORTS = (
    Path("reports/rag_eval/rag-ingestion/rag_retrieval_eval_report.json"),
    Path("reports/rag_eval/rag-ingestion/strict_D_hardened_xlsx_canary_vector_eval_report.json"),
    Path("reports/rag_eval/rag-ingestion/a5_d_vector_backend_readiness.json"),
)
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
EXPECTED_INDEX_VERSION = "rag-ingestion-v2-candidate"
EXPECTED_XLSX_HIDDEN_POLICY = "exclude_hidden"
EXPECTED_XLSX_HIDDEN_POLICY_VERSION = "exclude-hidden-v1"
XLSX_TYPES = {"SPREADSHEET", "XLSX", "XLSM"}
PDF_TYPES = {"PDF", "OCR"}
TEXT_TYPES = {"TEXT", "TXT", "MARKDOWN", "MD"}
PDF_XLSX_TYPES = sorted(XLSX_TYPES | PDF_TYPES)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    blockers: list[str] = []
    warnings: list[str] = []
    snapshot: dict[str, Any] = {}
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN

    try:
        with connect(db_dsn) as conn:
            snapshot = query_db_snapshot(conn, expected_index_version=args.expected_index_version)
    except Exception as exc:
        blockers.append(f"DB inspection failed: {type(exc).__name__}: {exc}")

    retrieval_summary = inspect_retrieval_reports([Path(path) for path in args.eval_report], blockers, warnings)
    payload = build_readiness_payload(
        snapshot=snapshot,
        retrieval_backend_separation_summary=retrieval_summary,
        blockers=blockers,
        warnings=warnings,
        expected_index_version=args.expected_index_version,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload["status"] == "PASS" else 2


def build_readiness_payload(
    *,
    snapshot: dict[str, Any],
    retrieval_backend_separation_summary: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
    expected_index_version: str,
) -> dict[str, Any]:
    blocker_list = list(blockers)
    warning_list = list(warnings)

    text_path_summary = dict(snapshot.get("text_path_summary") or {})
    xlsx_path_summary = dict(snapshot.get("xlsx_path_summary") or {})
    pdf_path_summary = dict(snapshot.get("pdf_path_summary") or {})
    contract = dict(snapshot.get("search_unit_contract_completeness") or {})
    normalized = dict(snapshot.get("normalized_metadata_coverage") or {})
    embedding = dict(snapshot.get("embedding_index_contract_summary") or {})
    mixing = list(snapshot.get("path_mixing_findings") or [])

    if int(contract.get("pdf_xlsx_candidate_count") or 0) == 0:
        blocker_list.append("No PDF/XLSX candidate SearchUnits found in the live DB")
    for key in (
        "missing_parser_version_count",
        "missing_location_json_count",
        "missing_citation_text_count",
        "missing_embedding_text_count",
    ):
        if int(contract.get(key) or 0) != 0:
            blocker_list.append(f"{key} must be 0 for PDF/XLSX candidate SearchUnits")

    if int(xlsx_path_summary.get("hidden_content_leakage_count") or 0) != 0:
        blocker_list.append("hidden XLSX leakage count must be 0")
    if int(xlsx_path_summary.get("xlsx_hidden_policy_mismatch_count") or 0) != 0:
        blocker_list.append("xlsx_hidden_policy_mismatch_count must be 0")
    if int(xlsx_path_summary.get("xlsx_hidden_policy_version_mismatch_count") or 0) != 0:
        blocker_list.append("xlsx_hidden_policy_version_mismatch_count must be 0")

    for key in (
        "not_embedded_count",
        "index_version_mismatch_count",
        "embedding_record_missing_count",
        "candidate_chunk_missing_count",
        "vector_namespace_mismatch_count",
        "chunk_sha_mismatch_count",
    ):
        if int(embedding.get(key) or 0) != 0:
            blocker_list.append(f"{key} must be 0 for candidate PDF/XLSX rows")

    if int(xlsx_path_summary.get("candidate_count") or 0) > 0:
        if int(normalized.get("xlsx_table_like_search_unit_count") or 0) > 0:
            if int(normalized.get("xlsx_table_metadata_count") or 0) <= 0:
                blocker_list.append("table_metadata coverage is missing for XLSX candidate SearchUnits")
            if int(normalized.get("xlsx_missing_table_metadata_count") or 0) != 0:
                blocker_list.append("xlsx_missing_table_metadata_count must be 0")
        if int(normalized.get("xlsx_cell_metadata_count") or 0) <= 0:
            blocker_list.append("cell_metadata coverage is missing for XLSX candidate SearchUnits")
        if int(normalized.get("xlsx_search_unit_metadata_unmatched_count") or 0) != 0:
            blocker_list.append("xlsx_search_unit_metadata_unmatched_count must be 0")

    if int(pdf_path_summary.get("candidate_count") or 0) > 0:
        if int(normalized.get("pdf_page_metadata_count") or 0) <= 0:
            blocker_list.append("pdf_page_metadata coverage is missing for PDF candidate SearchUnits")
        if int(normalized.get("pdf_missing_page_metadata_count") or 0) != 0:
            blocker_list.append("pdf_missing_page_metadata_count must be 0")

    if mixing:
        blocker_list.append("unexpected source_file_type/parser/document_version path mixing found")

    status = "FAIL" if blocker_list else "PASS"
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "expected_index_version": expected_index_version,
        "text_path_summary": text_path_summary,
        "xlsx_path_summary": xlsx_path_summary,
        "pdf_path_summary": pdf_path_summary,
        "parser_version_breakdown": list(snapshot.get("parser_version_breakdown") or []),
        "artifact_type_breakdown": list(snapshot.get("artifact_type_breakdown") or []),
        "search_unit_contract_completeness": contract,
        "normalized_metadata_coverage": normalized,
        "embedding_index_contract_summary": embedding,
        "retrieval_backend_separation_summary": retrieval_backend_separation_summary,
        "path_mixing_findings": mixing,
        "blockers": blocker_list,
        "warnings": warning_list,
    }


def query_db_snapshot(conn: Any, *, expected_index_version: str) -> dict[str, Any]:
    parser_breakdown = fetch_all(conn, """
        SELECT upper(coalesce(source_file_type, 'UNKNOWN')) AS source_file_type,
               coalesce(parser_version, 'UNKNOWN') AS parser_version,
               count(*)::int AS count
          FROM search_unit
         GROUP BY 1, 2
         ORDER BY 1, 2
    """)
    artifact_breakdown = fetch_all(conn, """
        SELECT 'parsed_artifact' AS table_name,
               artifact_type,
               file_type,
               parser_version,
               count(*)::int AS count
          FROM parsed_artifact
         GROUP BY artifact_type, file_type, parser_version
        UNION ALL
        SELECT 'extracted_artifact' AS table_name,
               artifact_type,
               NULL AS file_type,
               pipeline_version AS parser_version,
               count(*)::int AS count
          FROM extracted_artifact
         GROUP BY artifact_type, pipeline_version
         ORDER BY table_name, artifact_type, file_type, parser_version
    """)
    path_summary = fetch_one(conn, """
        SELECT
          count(*) FILTER (WHERE upper(coalesce(source_file_type, '')) = ANY(%s))::int AS text_count,
          count(*) FILTER (WHERE upper(coalesce(source_file_type, '')) = ANY(%s))::int AS xlsx_count,
          count(*) FILTER (WHERE upper(coalesce(source_file_type, '')) = ANY(%s))::int AS pdf_count,
          count(*) FILTER (
            WHERE upper(coalesce(source_file_type, '')) = ANY(%s)
              AND (
                location_json->>'hidden' = 'true'
                OR location_json->>'hidden_sheet' = 'true'
                OR coalesce(citation_text, '') LIKE '%%숨김%%'
              )
          )::int AS hidden_content_leakage_count,
          count(*) FILTER (
            WHERE upper(coalesce(source_file_type, '')) = ANY(%s)
              AND location_json->>'hidden_policy' IS DISTINCT FROM %s
          )::int AS xlsx_hidden_policy_mismatch_count,
          count(*) FILTER (
            WHERE upper(coalesce(source_file_type, '')) = ANY(%s)
              AND location_json->>'hidden_policy_version' IS DISTINCT FROM %s
          )::int AS xlsx_hidden_policy_version_mismatch_count
          FROM search_unit
    """, (
        sorted(TEXT_TYPES),
        sorted(XLSX_TYPES),
        sorted(PDF_TYPES),
        sorted(XLSX_TYPES),
        sorted(XLSX_TYPES),
        EXPECTED_XLSX_HIDDEN_POLICY,
        sorted(XLSX_TYPES),
        EXPECTED_XLSX_HIDDEN_POLICY_VERSION,
    ))
    contract = fetch_one(conn, """
        SELECT
          count(*)::int AS pdf_xlsx_candidate_count,
          count(*) FILTER (WHERE parser_version IS NULL OR btrim(parser_version) = '')::int AS missing_parser_version_count,
          count(*) FILTER (WHERE location_json IS NULL)::int AS missing_location_json_count,
          count(*) FILTER (WHERE citation_text IS NULL OR btrim(citation_text) = '')::int AS missing_citation_text_count,
          count(*) FILTER (WHERE embedding_text IS NULL OR btrim(embedding_text) = '')::int AS missing_embedding_text_count
          FROM search_unit
         WHERE upper(coalesce(source_file_type, '')) = ANY(%s)
    """, (PDF_XLSX_TYPES,))
    normalized = fetch_one(conn, """
        WITH xlsx_units AS (
          SELECT id,
                 document_version_id,
                 unit_type,
                 chunk_type,
                 nullif(btrim(location_json->>'table_id'), '') AS table_id,
                 nullif(btrim(location_json->>'sheet_name'), '') AS sheet_name,
                 nullif(btrim(coalesce(
                     location_json->>'cell_range',
                     location_json->>'range',
                     location_json->>'used_range',
                     location_json->>'location_range'
                 )), '') AS location_range
           FROM search_unit
           WHERE upper(coalesce(source_file_type, '')) = ANY(%s)
        ),
        xlsx_table_units AS (
          SELECT *
            FROM xlsx_units
           WHERE unit_type = 'TABLE' OR chunk_type = 'row_group'
        ),
        pdf_units AS (
          SELECT * FROM search_unit
           WHERE upper(coalesce(source_file_type, '')) = ANY(%s)
        ),
        pdf_pages AS (
          SELECT DISTINCT document_version_id,
                 (location_json->>'physical_page_index')::int AS physical_page_index
            FROM pdf_units
           WHERE document_version_id IS NOT NULL
             AND location_json ? 'physical_page_index'
             AND (location_json->>'physical_page_index') ~ '^[0-9]+$'
        ),
        xlsx_table_metadata_match AS (
          SELECT xu.id,
                 EXISTS (
                   SELECT 1
                     FROM table_metadata tm
                    WHERE tm.document_version_id = xu.document_version_id
                      AND (
                        (xu.table_id IS NOT NULL AND tm.table_id = xu.table_id)
                        OR (
                          xu.table_id IS NULL
                          AND xu.sheet_name IS NOT NULL
                          AND xu.location_range IS NOT NULL
                          AND tm.sheet_name = xu.sheet_name
                          AND (
                            tm.cell_range = xu.location_range
                            OR tm.data_range = xu.location_range
                            OR tm.header_range = xu.location_range
                            OR tm.location_json->>'cell_range' = xu.location_range
                            OR tm.location_json->>'range' = xu.location_range
                          )
                        )
                      )
                 ) AS has_search_unit_metadata
            FROM xlsx_table_units xu
        )
        SELECT
          (SELECT count(*)::int FROM xlsx_table_units) AS xlsx_table_like_search_unit_count,
          (SELECT count(*)::int FROM table_metadata tm
            WHERE tm.document_version_id IN (SELECT DISTINCT document_version_id FROM xlsx_units WHERE document_version_id IS NOT NULL)) AS xlsx_table_metadata_count,
          greatest(
            (SELECT count(*)::int FROM xlsx_table_units)
            - (SELECT count(*)::int FROM table_metadata tm
                WHERE tm.document_version_id IN (SELECT DISTINCT document_version_id FROM xlsx_units WHERE document_version_id IS NOT NULL)),
            0
          ) AS xlsx_missing_table_metadata_count,
          (SELECT count(*)::int FROM cell_metadata cm
            WHERE cm.document_version_id IN (SELECT DISTINCT document_version_id FROM xlsx_units WHERE document_version_id IS NOT NULL)) AS xlsx_cell_metadata_count,
          (SELECT count(*)::int FROM xlsx_table_metadata_match WHERE has_search_unit_metadata) AS xlsx_search_unit_metadata_matched_count,
          (SELECT count(*)::int FROM xlsx_table_metadata_match WHERE NOT has_search_unit_metadata) AS xlsx_search_unit_metadata_unmatched_count,
          (SELECT count(*)::int FROM pdf_page_metadata ppm
            WHERE ppm.document_version_id IN (SELECT DISTINCT document_version_id FROM pdf_units WHERE document_version_id IS NOT NULL)) AS pdf_page_metadata_count,
          (SELECT count(*)::int FROM pdf_pages p
            LEFT JOIN pdf_page_metadata ppm
              ON ppm.document_version_id = p.document_version_id
             AND ppm.physical_page_index = p.physical_page_index
            WHERE ppm.id IS NULL) AS pdf_missing_page_metadata_count
    """, (sorted(XLSX_TYPES), sorted(PDF_TYPES)))
    embedding = fetch_one(conn, """
        WITH indexed_candidate_units AS (
          SELECT su.*
            FROM search_unit su
            LEFT JOIN embedding_record er_candidate
              ON er_candidate.search_unit_id = su.id
             AND er_candidate.index_version = %s
            LEFT JOIN ragmeta.chunks c_candidate
              ON c_candidate.chunk_id = su.index_id
             AND c_candidate.index_version = %s
           WHERE upper(coalesce(su.source_file_type, '')) = ANY(%s)
             AND (
                  su.index_version = %s
               OR er_candidate.id IS NOT NULL
               OR c_candidate.chunk_id IS NOT NULL
             )
        )
        SELECT
          count(*)::int AS scoped_count,
          count(*) FILTER (WHERE su.embedding_status IS DISTINCT FROM 'EMBEDDED')::int AS not_embedded_count,
          count(*) FILTER (WHERE su.index_version IS DISTINCT FROM %s)::int AS index_version_mismatch_count,
          count(*) FILTER (WHERE er.id IS NULL)::int AS embedding_record_missing_count,
          count(*) FILTER (WHERE c.chunk_id IS NULL)::int AS candidate_chunk_missing_count,
          count(*) FILTER (
            WHERE er.id IS NOT NULL
              AND (er.vector_id IS NULL OR er.vector_id NOT LIKE %s)
          )::int AS vector_namespace_mismatch_count,
          count(*) FILTER (
            WHERE c.chunk_id IS NOT NULL
              AND er.id IS NOT NULL
              AND (
                c.extra_json->>'embeddingTextSha256' IS NULL
                OR c.extra_json->>'embeddingTextSha256' IS DISTINCT FROM er.embedding_text_sha256
              )
          )::int AS chunk_sha_mismatch_count
          FROM indexed_candidate_units su
          LEFT JOIN embedding_record er
            ON er.search_unit_id = su.id
           AND er.index_version = %s
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
    """, (
        expected_index_version,
        expected_index_version,
        PDF_XLSX_TYPES,
        expected_index_version,
        expected_index_version,
        f"{expected_index_version}:%",
        expected_index_version,
        expected_index_version,
    ))
    mixing_rows = fetch_all(conn, """
        WITH typed AS (
          SELECT su.id,
                 su.source_file_type,
                 su.parser_version,
                 su.document_version_id,
                 dv.source_file_type AS document_version_source_file_type,
                 CASE
                   WHEN upper(coalesce(su.source_file_type, '')) = ANY(%s) THEN 'XLSX'
                   WHEN upper(coalesce(su.source_file_type, '')) = ANY(%s) THEN 'PDF'
                   WHEN upper(coalesce(su.source_file_type, '')) = ANY(%s) THEN 'TEXT'
                   ELSE upper(coalesce(su.source_file_type, 'UNKNOWN'))
                 END AS search_unit_path,
                 CASE
                   WHEN upper(coalesce(dv.source_file_type, '')) = ANY(%s) THEN 'XLSX'
                   WHEN upper(coalesce(dv.source_file_type, '')) = ANY(%s) THEN 'PDF'
                   WHEN upper(coalesce(dv.source_file_type, '')) = ANY(%s) THEN 'TEXT'
                   ELSE NULLIF(upper(coalesce(dv.source_file_type, '')), '')
                 END AS document_version_path
            FROM search_unit su
            LEFT JOIN document_version dv ON dv.id = su.document_version_id
        )
        SELECT id,
               source_file_type,
               parser_version,
               document_version_id,
               document_version_source_file_type
          FROM typed
         WHERE (parser_version LIKE 'xlsx-%%' AND search_unit_path <> 'XLSX')
            OR (parser_version LIKE 'pdf-%%' AND search_unit_path <> 'PDF')
            OR (
                 document_version_path IS NOT NULL
             AND search_unit_path <> document_version_path
            )
         ORDER BY id
         LIMIT 25
    """, (
        sorted(XLSX_TYPES),
        sorted(PDF_TYPES),
        sorted(TEXT_TYPES),
        sorted(XLSX_TYPES),
        sorted(PDF_TYPES),
        sorted(TEXT_TYPES),
    ))
    path_mixing = path_mixing_findings(mixing_rows)
    return {
        "text_path_summary": {"candidate_count": int(path_summary.get("text_count") or 0)},
        "xlsx_path_summary": {
            "candidate_count": int(path_summary.get("xlsx_count") or 0),
            "hidden_content_leakage_count": int(path_summary.get("hidden_content_leakage_count") or 0),
            "xlsx_hidden_policy_mismatch_count": int(path_summary.get("xlsx_hidden_policy_mismatch_count") or 0),
            "xlsx_hidden_policy_version_mismatch_count": int(
                path_summary.get("xlsx_hidden_policy_version_mismatch_count") or 0
            ),
        },
        "pdf_path_summary": {"candidate_count": int(path_summary.get("pdf_count") or 0)},
        "parser_version_breakdown": rows_to_plain(parser_breakdown),
        "artifact_type_breakdown": rows_to_plain(artifact_breakdown),
        "search_unit_contract_completeness": row_to_plain(contract),
        "normalized_metadata_coverage": row_to_plain(normalized),
        "embedding_index_contract_summary": row_to_plain(embedding),
        "path_mixing_findings": path_mixing,
    }


def path_mixing_findings(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        source_type = normalize_source_type(row.get("source_file_type"))
        docv_type = normalize_source_type(row.get("document_version_source_file_type"))
        parser_version = str(row.get("parser_version") or "")
        reasons: list[str] = []
        if parser_version.startswith("xlsx-") and source_type != "XLSX":
            reasons.append("xlsx parser on non-XLSX SearchUnit source_file_type")
        if parser_version.startswith("pdf-") and source_type != "PDF":
            reasons.append("pdf parser on non-PDF SearchUnit source_file_type")
        if docv_type and source_type and source_type != docv_type:
            reasons.append("SearchUnit source_file_type differs from document_version source_file_type")
        if reasons:
            findings.append({
                "search_unit_id": row.get("id"),
                "source_file_type": row.get("source_file_type"),
                "document_version_source_file_type": row.get("document_version_source_file_type"),
                "parser_version": row.get("parser_version"),
                "reasons": reasons,
            })
    return findings[:25]


def inspect_retrieval_reports(paths: list[Path], blockers: list[str], warnings: list[str]) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            warnings.append(f"Retrieval/eval artifact not found: {path}")
            continue
        try:
            payload = read_json(path)
        except Exception as exc:
            warnings.append(f"Could not read retrieval/eval artifact {path}: {exc}")
            continue
        metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
        backend = payload.get("retrieval_backend") or metrics.get("retrieval_backend")
        scope = str(payload.get("scope") or path.name)
        vector_claim = "vector" in scope.lower() or "vector" in path.name.lower()
        promotion_evidence = bool(payload.get("promotion_evidence") or metrics.get("promotion_evidence"))
        report = {
            "path": str(path),
            "retrieval_backend": backend,
            "backend_identity": payload.get("backend_identity") or metrics.get("retrieval_backend_identity") or {},
            "vector_claim": vector_claim,
            "promotion_evidence": promotion_evidence,
        }
        if vector_claim and backend != "vector":
            blockers.append(f"Vector eval artifact {path} must use retrieval_backend=vector, got {backend or 'missing'}")
        if promotion_evidence and backend == "library_search":
            blockers.append(f"library_search artifact {path} cannot be promotion evidence")
        if backend == "library_search":
            warnings.append(f"{path} is library_search diagnostic evidence only")
        if backend is None:
            warnings.append(f"{path} does not declare retrieval_backend")
        reports.append(report)
    return {
        "reports": reports,
        "vector_report_count": sum(1 for item in reports if item.get("retrieval_backend") == "vector"),
        "library_search_report_count": sum(1 for item in reports if item.get("retrieval_backend") == "library_search"),
    }


def normalize_source_type(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if text in XLSX_TYPES:
        return "XLSX"
    if text in PDF_TYPES:
        return "PDF"
    if text in TEXT_TYPES:
        return "TEXT"
    return text


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--expected-index-version", default=EXPECTED_INDEX_VERSION)
    parser.add_argument(
        "--eval-report",
        action="append",
        default=None,
        help="Eval/readiness artifact to inspect. Repeat as needed.",
    )
    args = parser.parse_args(argv)
    if args.eval_report is None:
        args.eval_report = [str(path) for path in DEFAULT_RETRIEVAL_REPORTS]
    return args


if __name__ == "__main__":
    sys.exit(main())
