"""Generate Track B B0 TEXT backend identity report.

This script is read-only. It inspects code paths, optionally samples the live
catalog DB and `/api/v1/library/search`, and records why Track B TEXT E2E work
is or is not ready to proceed beyond backend identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_text_backend_identity_report.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_API_URL = "http://localhost:8080/api/v1/library/search"

TEXT_TYPES = {"TEXT", "TXT", "MARKDOWN", "MD"}
PDF_TYPES = {"PDF", "OCR"}
XLSX_TYPES = {"SPREADSHEET", "XLSX", "XLSM"}

EVIDENCE_PATHS = {
    "controller": Path("core-api/src/main/java/com/aipipeline/coreapi/catalog/adapter/in/web/DocumentCatalogController.java"),
    "service": Path("core-api/src/main/java/com/aipipeline/coreapi/catalog/application/service/DocumentCatalogService.java"),
    "repository": Path("core-api/src/main/java/com/aipipeline/coreapi/catalog/adapter/out/persistence/SearchUnitJpaRepository.java"),
    "entity": Path("core-api/src/main/java/com/aipipeline/coreapi/catalog/adapter/out/persistence/SearchUnitJpaEntity.java"),
    "vector_tools": Path("ai/app/capabilities/rag_orchestrator/vector_tools.py"),
    "fixture_tools": Path("ai/app/capabilities/rag_orchestrator/tools.py"),
    "worker_config": Path("ai/app/core/config.py"),
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    warnings: list[str] = []

    static_identity = inspect_static_identity(root)
    db_snapshot: dict[str, Any] = {"status": "SKIPPED"} if args.skip_db else inspect_db(args.db_dsn, warnings)
    payload = build_report(
        static_identity=static_identity,
        db_snapshot=db_snapshot,
        api_probe={"status": "SKIPPED"} if args.skip_api_probe else probe_library_search(
            args.api_url,
            args.api_probe_query,
            args.api_probe_limit,
            source_file_types=sorted(TEXT_TYPES) if static_identity.get("text_only_filter_supported") else [],
        ),
        warnings=warnings,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0


def inspect_static_identity(root: Path) -> dict[str, Any]:
    files = {
        name: inspect_file(root / relative)
        for name, relative in EVIDENCE_PATHS.items()
    }
    controller_text = files["controller"].get("text") or ""
    service_text = files["service"].get("text") or ""
    repository_text = files["repository"].get("text") or ""
    vector_tools_text = files["vector_tools"].get("text") or ""
    fixture_tools_text = files["fixture_tools"].get("text") or ""
    worker_config_text = files["worker_config"].get("text") or ""

    search_method = section_between(
        controller_text,
        '@GetMapping("/search")',
        "public record SourceFileResponse",
    )
    repository_search = section_between(
        repository_text,
        "List<SearchUnitJpaEntity> searchByText",
        "Optional<SearchUnitJpaEntity> findByIdAndEmbeddingClaimToken",
    )
    service_search = section_between(
        service_text,
        "public List<SearchResult> search",
        "private List<SearchUnitJpaEntity>",
    )
    text_import_route = section_between(
        controller_text,
        '@PostMapping("/source-files/{sourceFileId}/text-import")',
        '@GetMapping("/search")',
    )

    implementation_files = {
        name: {
            "path": str(EVIDENCE_PATHS[name]).replace("\\", "/"),
            "sha256": item.get("sha256"),
            "exists": item.get("exists", False),
        }
        for name, item in files.items()
    }
    config_sha256 = combined_sha256(
        {
            key: value["sha256"]
            for key, value in implementation_files.items()
            if key in {"controller", "service", "repository"} and value.get("sha256")
        }
    )

    library_search_present = (
        '@RequestMapping("/api/v1/library")' in controller_text
        and '@GetMapping("/search")' in controller_text
        and "catalog.search(query, limit" in controller_text
        and "searchByText" in service_text
    )
    controller_accepts_source_type = "sourceFileType" in search_method or "source_file_type" in search_method
    service_accepts_source_type = "sourceFileType" in service_search or "source_file_type" in service_search
    repository_filters_source_type = "source_file_type" in repository_search or "sourceFileType" in repository_search
    text_only_filter_supported = (
        library_search_present
        and controller_accepts_source_type
        and service_accepts_source_type
        and repository_filters_source_type
    )
    text_import_path_supported = (
        '@PostMapping("/source-files/{sourceFileId}/text-import")' in controller_text
        and "importTextSourceFile" in service_text
        and "buildTextSearchUnitDrafts" in service_text
        and "TEXT_PIPELINE_VERSION" in service_text
    )
    text_extension_classification_supported = all(
        marker in service_text for marker in ('.txt', '.md', '.markdown')
    )

    return {
        "library_search_present": library_search_present,
        "implementation_files": implementation_files,
        "config_sha256": config_sha256,
        "library_search_identity": {
            "backend": "library_search",
            "api_route": "/api/v1/library/search",
            "http_method": "GET",
            "controller": "DocumentCatalogController.search(query, limit, sourceFileTypes)",
            "service": "DocumentCatalogService.search(query, limit, sourceFileTypes)",
            "repository_method": "SearchUnitJpaRepository.searchByText/searchByTextAndSourceFileTypes",
            "repository": "SearchUnitJpaRepository.searchByText/searchByTextAndSourceFileTypes",
            "query_surface": "JPQL LIKE over SearchUnit text fields",
            "filtering_mode": "source_type_filtered_lexical_search"
            if text_only_filter_supported
            else "unfiltered_lexical_search",
            "query_fields": [
                field
                for field in ("textContent", "bm25Text", "displayText", "citationText", "debugText")
                if field in repository_text
            ],
            "limit_clamp": "1..50" if "Math.max(1, Math.min(limit, 50))" in service_text else None,
            "source_type_request_param_supported": controller_accepts_source_type,
            "source_type_repository_filter_supported": repository_filters_source_type,
            "embedding_status_filter_supported": (
                ":embeddingStatus" in repository_search
                or "unit.embeddingStatus =" in repository_search
            ),
            "index_version_filter_supported": "indexVersion" in repository_search or "index_version" in repository_search,
            "index_version": None,
            "artifact_dir": None,
            "vector_namespace": None,
            "config_sha256": config_sha256,
        },
        "text_corpus_import_path": {
            "status": "present" if text_import_path_supported else "not_found",
            "api_route": "/api/v1/library/source-files/{sourceFileId}/text-import"
            if text_import_path_supported
            else None,
            "http_method": "POST" if text_import_path_supported else None,
            "controller": "DocumentCatalogController.importTextSource"
            if "importTextSource" in text_import_route
            else None,
            "service": "DocumentCatalogService.importTextSourceFile",
            "parser_version": "text-import-v1" if "text-import-v1" in service_text else None,
            "canonical_source_file_type": "TEXT" if text_extension_classification_supported else None,
            "extension_classification_supported": text_extension_classification_supported,
            "creates_search_units": text_import_path_supported,
            "worker_job_required": False if text_import_path_supported else None,
        },
        "text_only_filter_supported": text_only_filter_supported,
        "candidate_backends": {
            "library_search": {
                "status": "present" if library_search_present else "not_found",
                "operational_role": "lexical_diagnostic",
            },
            "legacy_text_index": {
                "status": "not_found_by_static_scan",
                "operational_role": None,
            },
            "vector_text_candidate": {
                "status": "poc_wrapper_present" if "def text_vector_search_tool" in vector_tools_text else "not_found",
                "operational_role": "vector_poc_post_filter" if "TEXT_VECTOR_READINESS_WARNING" in vector_tools_text else None,
            },
            "manual_fixture_backend": {
                "status": "fixture_present" if "fake_text_vector_search_tool" in fixture_tools_text else "not_found",
                "operational_role": "smoke_only" if "fixture-only" in fixture_tools_text else None,
            },
        },
        "vector_adjacent_identity": {
            "backend": "faiss" if "VECTOR_BACKEND_FAISS" in vector_tools_text else None,
            "default_artifact_dir": "eval/indexes/rag-data" if "eval/indexes/rag-data" in worker_config_text else None,
            "production_filter_enforcement": False if "production-grade filter-enforcement" in vector_tools_text else None,
            "text_contract_warning": "text_vector_contract_not_production_ready"
            if "TEXT_VECTOR_READINESS_WARNING" in vector_tools_text
            else None,
            "library_search_used": False if "library_search_used" in vector_tools_text else None,
        },
    }


def build_report(
    *,
    static_identity: Mapping[str, Any],
    db_snapshot: Mapping[str, Any],
    api_probe: Mapping[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    blockers: list[str] = []
    library_identity = dict(static_identity.get("library_search_identity") or {})
    text_only_filter_supported = bool(static_identity.get("text_only_filter_supported"))
    text_corpus_import_path = dict(static_identity.get("text_corpus_import_path") or {})
    path_mixing = path_mixing_from_db(db_snapshot)
    api_result_path_mixing = path_mixing_from_api(api_probe)
    ready_text_count = int(path_mixing.get("text_count") or 0)
    api_text_count = int(api_result_path_mixing.get("text_count") or 0)
    api_non_text_count = int(api_result_path_mixing.get("non_text_count") or 0)

    if not static_identity.get("library_search_present"):
        blockers.append("library search route was not found in static code inspection")
    if not text_only_filter_supported:
        blockers.append("GET /api/v1/library/search does not support TEXT-only request/query filtering")
    if db_snapshot.get("status") == "OK" and ready_text_count == 0:
        blockers.append("live READY search_unit snapshot has no TEXT/TXT/MARKDOWN/MD rows")
    if db_snapshot.get("status") == "OK" and ready_text_count > 0:
        if api_probe.get("status") != "OK":
            blockers.append("live TEXT-filtered library search API probe was not verified")
        elif api_non_text_count > 0:
            blockers.append("live library search probe returned non-TEXT hits")
        elif api_text_count == 0:
            blockers.append("live TEXT-filtered library search API probe returned no TEXT hits")
    if db_snapshot.get("status") == "ERROR":
        warnings.append(f"DB inspection unavailable: {db_snapshot.get('error')}")
    if api_probe.get("status") == "ERROR":
        warnings.append(f"live API probe unavailable: {api_probe.get('error')}")

    b1_entry_allowed = bool(
        text_only_filter_supported
        and db_snapshot.get("status") == "OK"
        and ready_text_count > 0
        and api_probe.get("status") == "OK"
        and api_text_count > 0
        and api_non_text_count == 0
    )
    b1_decision = (
        "B1 entry is allowed for diagnostic gold rows because READY TEXT rows exist and the TEXT-filtered API probe was clean."
        if b1_entry_allowed
        else "Keep B1 blocked until READY TEXT rows exist and a clean TEXT-filtered API probe is recorded."
    )
    next_phase_recommendation = (
        "B0 blocker cleared; proceed to B1 gold v0 as diagnostic-only Track B work."
        if b1_entry_allowed
        else (
            "Keep B1 blocked; import a small real TEXT corpus through the text-import path and rerun B0."
            if text_corpus_import_path.get("status") == "present"
            else "Keep B1 blocked; first add or expose a TEXT-only retrievable corpus/path, or explicitly switch to fixture-only smoke rows."
        )
    )

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_text_backend_identity_v1",
        "status": "DIAGNOSTIC_COMPLETED" if static_identity.get("library_search_present") else "BLOCKED",
        "report_role": "rag_text_backend_identity",
        "scope": "track_b_text_retrieval_e2e",
        "phase": "B0",
        "retrieval_backend": "library_search" if static_identity.get("library_search_present") else None,
        "retrieval_backend_identity": library_identity,
        "backend_identity": library_identity,
        "candidate_backends": static_identity.get("candidate_backends"),
        "vector_adjacent_identity": static_identity.get("vector_adjacent_identity"),
        "text_corpus_import_path": text_corpus_import_path,
        "text_only_filter_supported": text_only_filter_supported,
        "post_retrieval_text_filter_possible": True,
        "library_search_diagnostics": {
            "route_params": ["query", "limit", *([] if not text_only_filter_supported else ["sourceFileTypes"])],
            "limit_default": 20,
            "limit_max": 50 if library_identity.get("limit_clamp") == "1..50" else None,
            "searched_fields": library_identity.get("query_fields") or [],
            "source_file_type_aliases": sorted(TEXT_TYPES) if text_only_filter_supported else [],
            "unsupported_filters": [
                *([] if text_only_filter_supported else ["source_file_type"]),
                "embedding_status",
                "index_version",
                "tenant_id",
                "acl",
            ],
        },
        "path_mixing": path_mixing,
        "api_probe": api_probe,
        "api_result_path_mixing": api_result_path_mixing,
        "operational_claim_allowed": False,
        "b1_entry_allowed": b1_entry_allowed,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "blockers": blockers,
        "warnings": dedupe(warnings + [
            "library_search is lexical diagnostic and must not be used as vector-grade production Evidence",
        ]),
        "important_decisions": [
            "Use library_search as the B0 backend identity for the current Track B diagnostic path.",
            b1_decision,
            "Do not mix this Track B report with XLSX/PDF promotion gate evidence.",
        ],
        "next_phase_recommendation": next_phase_recommendation,
    }


def inspect_db(dsn: str, warnings: list[str]) -> dict[str, Any]:
    try:
        import psycopg2  # type: ignore[import-not-found]
        import psycopg2.extras  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on local env
        return {"status": "ERROR", "error": f"psycopg2 import failed: {type(exc).__name__}: {exc}"}

    try:
        with psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT upper(coalesce(su.source_file_type, 'UNKNOWN')) AS source_file_type,
                           count(*)::int AS count
                      FROM search_unit su
                     GROUP BY 1
                     ORDER BY 1
                    """
                )
                all_breakdown = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT
                      count(*) FILTER (
                        WHERE upper(coalesce(su.source_file_type, '')) in ('TEXT', 'TXT', 'MARKDOWN', 'MD')
                      )::int AS text_count,
                      count(*) FILTER (
                        WHERE upper(coalesce(su.source_file_type, '')) in ('PDF', 'OCR')
                      )::int AS pdf_count,
                      count(*) FILTER (
                        WHERE upper(coalesce(su.source_file_type, '')) in ('SPREADSHEET', 'XLSX', 'XLSM')
                      )::int AS xlsx_count,
                      count(*) FILTER (
                        WHERE coalesce(su.source_file_type, '') = ''
                           OR upper(coalesce(su.source_file_type, '')) not in (
                             'TEXT', 'TXT', 'MARKDOWN', 'MD', 'PDF', 'OCR', 'SPREADSHEET', 'XLSX', 'XLSM'
                           )
                      )::int AS unknown_count,
                      count(*)::int AS total_count
                      FROM search_unit su
                    """
                )
                all_summary = dict(cur.fetchone())
                cur.execute(
                    """
                    SELECT upper(coalesce(su.source_file_type, 'UNKNOWN')) AS source_file_type,
                           count(*)::int AS count
                      FROM search_unit su
                      JOIN source_file sf ON sf.id = su.source_file_id
                     WHERE sf.status = 'READY'
                     GROUP BY 1
                     ORDER BY 1
                    """
                )
                ready_breakdown = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT
                      count(*) FILTER (
                        WHERE upper(coalesce(su.source_file_type, '')) in ('TEXT', 'TXT', 'MARKDOWN', 'MD')
                      )::int AS text_count,
                      count(*) FILTER (
                        WHERE upper(coalesce(su.source_file_type, '')) in ('PDF', 'OCR')
                      )::int AS pdf_count,
                      count(*) FILTER (
                        WHERE upper(coalesce(su.source_file_type, '')) in ('SPREADSHEET', 'XLSX', 'XLSM')
                      )::int AS xlsx_count,
                      count(*) FILTER (
                        WHERE coalesce(su.source_file_type, '') = ''
                           OR upper(coalesce(su.source_file_type, '')) not in (
                             'TEXT', 'TXT', 'MARKDOWN', 'MD', 'PDF', 'OCR', 'SPREADSHEET', 'XLSX', 'XLSM'
                           )
                      )::int AS unknown_count,
                      count(*)::int AS total_count
                      FROM search_unit su
                      JOIN source_file sf ON sf.id = su.source_file_id
                     WHERE sf.status = 'READY'
                    """
                )
                ready_summary = dict(cur.fetchone())
                cur.execute(
                    """
                    SELECT coalesce(index_version, 'NULL') AS index_version,
                           count(*)::int AS count
                      FROM search_unit
                     GROUP BY 1
                     ORDER BY 1
                    """
                )
                index_versions = [dict(row) for row in cur.fetchall()]
    except Exception as exc:  # pragma: no cover - depends on local DB state
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}

    warnings.append("DB inspection was read-only and reflects only the current local catalog state")
    return {
        "status": "OK",
        "source_file_type_breakdown": ready_breakdown,
        "source_type_summary": ready_summary,
        "source_scope": "READY source_file rows only",
        "all_source_file_type_breakdown": all_breakdown,
        "all_source_type_summary": all_summary,
        "index_version_breakdown": index_versions,
    }


def probe_library_search(
    api_url: str,
    query: str,
    limit: int,
    *,
    source_file_types: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    url = library_search_probe_url(api_url, query, limit, source_file_types=source_file_types)
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - local/read-only diagnostic URL
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
    except Exception as exc:  # pragma: no cover - depends on local service
        return {
            "status": "ERROR",
            "url": url,
            "query": query,
            "limit": limit,
            "source_file_types": list(source_file_types),
            "error": f"{type(exc).__name__}: {exc}",
        }

    results = payload.get("results") or []
    return {
        "status": "OK",
        "url": url,
        "query": query,
        "limit": limit,
        "source_file_types": list(source_file_types),
        "result_count": len(results),
        "source_type_summary": summarize_source_types(source_type_from_result(row) for row in results),
    }


def library_search_probe_url(
    api_url: str,
    query: str,
    limit: int,
    *,
    source_file_types: list[str] | tuple[str, ...] = (),
) -> str:
    params: list[tuple[str, str]] = [
        ("query", query),
        ("limit", str(limit)),
    ]
    params.extend(("sourceFileTypes", item) for item in source_file_types)
    return api_url + "?" + urllib.parse.urlencode(params)


def path_mixing_from_db(db_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if db_snapshot.get("status") != "OK":
        return {
            "source": "live_db_ready_search_unit_snapshot",
            "status": db_snapshot.get("status"),
            "counts_observed": False,
            "text_count": None,
            "pdf_count": None,
            "xlsx_count": None,
            "unknown_count": None,
            "other_count": None,
            "total_count": None,
            "mixing_observed": None,
            "exclusion_rule": "TEXT source_file_type in TEXT/TXT/MARKDOWN/MD; exclude PDF/OCR/SPREADSHEET/XLSX/XLSM/UNKNOWN",
        }
    summary = dict(db_snapshot.get("source_type_summary") or {})
    non_text = (
        int(summary.get("pdf_count") or 0)
        + int(summary.get("xlsx_count") or 0)
        + int(summary.get("unknown_count") or 0)
    )
    return {
        "source": "live_db_ready_search_unit_snapshot",
        "status": "OK",
        "counts_observed": True,
        "source_scope": db_snapshot.get("source_scope") or "READY source_file rows only",
        "text_count": int(summary.get("text_count") or 0),
        "pdf_count": int(summary.get("pdf_count") or 0),
        "xlsx_count": int(summary.get("xlsx_count") or 0),
        "unknown_count": int(summary.get("unknown_count") or 0),
        "other_count": int(summary.get("unknown_count") or 0),
        "total_count": int(summary.get("total_count") or 0),
        "mixing_observed": non_text > 0,
        "exclusion_rule": "TEXT source_file_type in TEXT/TXT/MARKDOWN/MD; exclude PDF/OCR/SPREADSHEET/XLSX/XLSM/UNKNOWN",
    }


def path_mixing_from_api(api_probe: Mapping[str, Any]) -> dict[str, Any]:
    summary = dict(api_probe.get("source_type_summary") or {})
    if api_probe.get("status") != "OK":
        return {
            "source": "live_api_probe",
            "status": api_probe.get("status"),
            "counts_observed": False,
            "text_count": None,
            "pdf_count": None,
            "xlsx_count": None,
            "unknown_count": None,
            "other_count": None,
            "non_text_count": None,
            "mixing_observed": None,
            "exclusion_rule": "TEXT source_file_type in TEXT/TXT/MARKDOWN/MD; exclude PDF/OCR/SPREADSHEET/XLSX/XLSM/UNKNOWN",
        }
    non_text = int(summary.get("pdf_count") or 0) + int(summary.get("xlsx_count") or 0) + int(summary.get("unknown_count") or 0)
    return {
        "source": "live_api_probe",
        "status": "OK",
        "counts_observed": True,
        "text_count": int(summary.get("text_count") or 0),
        "pdf_count": int(summary.get("pdf_count") or 0),
        "xlsx_count": int(summary.get("xlsx_count") or 0),
        "unknown_count": int(summary.get("unknown_count") or 0),
        "other_count": int(summary.get("unknown_count") or 0),
        "non_text_count": non_text,
        "mixing_observed": non_text > 0,
        "exclusion_rule": "TEXT source_file_type in TEXT/TXT/MARKDOWN/MD; exclude PDF/OCR/SPREADSHEET/XLSX/XLSM/UNKNOWN",
    }


def summarize_source_types(values: Any) -> dict[str, int]:
    counts = {
        "text_count": 0,
        "pdf_count": 0,
        "xlsx_count": 0,
        "unknown_count": 0,
        "total_count": 0,
    }
    for value in values:
        counts["total_count"] += 1
        normalized = normalize_source_type(value)
        if normalized in TEXT_TYPES:
            counts["text_count"] += 1
        elif normalized in PDF_TYPES:
            counts["pdf_count"] += 1
        elif normalized in XLSX_TYPES:
            counts["xlsx_count"] += 1
        else:
            counts["unknown_count"] += 1
    return counts


def normalize_source_type(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    normalized = str(value).strip().upper()
    return normalized or "UNKNOWN"


def source_type_from_result(result: Mapping[str, Any]) -> Any:
    source = result.get("sourceFile") or {}
    unit = result.get("searchUnit") or {}
    return unit.get("sourceFileType") or source.get("fileType") or result.get("sourceFileType")


def inspect_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    text = path.read_text(encoding="utf-8")
    return {
        "exists": True,
        "path": str(path),
        "sha256": sha256_text(text),
        "text": text,
    }


def section_between(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        return ""
    end_index = text.find(end, start_index)
    if end_index < 0:
        return text[start_index:]
    return text[start_index:end_index]


def combined_sha256(items: Mapping[str, str]) -> str | None:
    if not items:
        return None
    digest = hashlib.sha256()
    for key in sorted(items):
        digest.update(key.encode("utf-8"))
        digest.update(b"\0")
        digest.update(items[key].encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Track B B0 TEXT backend identity report.")
    parser.add_argument("--root", default=".", help="Repository root to inspect.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Report output path.")
    parser.add_argument("--db-dsn", default=os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN)
    parser.add_argument("--skip-db", action="store_true", help="Skip live DB snapshot.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--api-probe-query", default="test")
    parser.add_argument("--api-probe-limit", type=int, default=3)
    parser.add_argument("--skip-api-probe", action="store_true", help="Skip live library-search API probe.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
