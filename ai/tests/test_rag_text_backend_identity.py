from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_text_backend_identity.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_text_backend_identity_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


identity = load_module()


def test_summarize_source_types_groups_text_pdf_xlsx_and_unknown():
    summary = identity.summarize_source_types([
        "TEXT",
        "markdown",
        "PDF",
        "ocr",
        "SPREADSHEET",
        "xlsm",
        "",
        None,
        "custom",
    ])

    assert summary == {
        "text_count": 2,
        "pdf_count": 2,
        "xlsx_count": 2,
        "unknown_count": 3,
        "total_count": 9,
    }


def test_build_report_blocks_b1_when_text_filter_is_missing_and_text_rows_are_empty():
    report = identity.build_report(
        static_identity={
            "library_search_present": True,
            "text_only_filter_supported": False,
            "library_search_identity": {
                "api_route": "/api/v1/library/search",
            },
            "candidate_backends": {},
            "vector_adjacent_identity": {},
        },
        db_snapshot={
            "status": "OK",
            "source_type_summary": {
                "text_count": 0,
                "pdf_count": 4,
                "xlsx_count": 2,
                "unknown_count": 0,
                "total_count": 6,
            },
        },
        api_probe={"status": "SKIPPED"},
        warnings=[],
    )

    assert report["status"] == "DIAGNOSTIC_COMPLETED"
    assert report["schema_version"] == "rag_text_backend_identity_v1"
    assert report["scope"] == "track_b_text_retrieval_e2e"
    assert report["retrieval_backend"] == "library_search"
    assert report["backend_identity"] == report["retrieval_backend_identity"]
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["operational_claim_allowed"] is False
    assert report["b1_entry_allowed"] is False
    assert report["path_mixing"]["counts_observed"] is True
    assert report["path_mixing"]["mixing_observed"] is True
    assert "GET /api/v1/library/search does not support TEXT-only request/query filtering" in report["blockers"]
    assert "live READY search_unit snapshot has no TEXT/TXT/MARKDOWN/MD rows" in report["blockers"]


def test_build_report_allows_b1_when_filter_supported_text_rows_exist_and_api_probe_is_clean():
    report = identity.build_report(
        static_identity={
            "library_search_present": True,
            "text_only_filter_supported": True,
            "library_search_identity": {
                "api_route": "/api/v1/library/search",
                "limit_clamp": "1..50",
                "query_fields": ["textContent"],
            },
            "candidate_backends": {},
            "vector_adjacent_identity": {},
        },
        db_snapshot={
            "status": "OK",
            "source_type_summary": {
                "text_count": 3,
                "pdf_count": 4,
                "xlsx_count": 2,
                "unknown_count": 0,
                "total_count": 9,
            },
        },
        api_probe={
            "status": "OK",
            "source_type_summary": {
                "text_count": 1,
                "pdf_count": 0,
                "xlsx_count": 0,
                "unknown_count": 0,
                "total_count": 1,
            },
        },
        warnings=[],
    )

    assert report["text_only_filter_supported"] is True
    assert report["b1_entry_allowed"] is True
    assert "sourceFileTypes" in report["library_search_diagnostics"]["route_params"]
    assert report["library_search_diagnostics"]["source_file_type_aliases"] == ["MARKDOWN", "MD", "TEXT", "TXT"]
    assert "source_file_type" not in report["library_search_diagnostics"]["unsupported_filters"]
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["next_phase_recommendation"].startswith("B0 blocker cleared")
    assert any(decision.startswith("B1 entry is allowed") for decision in report["important_decisions"])


def test_build_report_blocks_b1_when_api_probe_is_not_verified_even_with_text_rows():
    report = identity.build_report(
        static_identity={
            "library_search_present": True,
            "text_only_filter_supported": True,
            "library_search_identity": {
                "api_route": "/api/v1/library/search",
                "limit_clamp": "1..50",
                "query_fields": ["textContent"],
            },
            "candidate_backends": {},
            "vector_adjacent_identity": {},
        },
        db_snapshot={
            "status": "OK",
            "source_type_summary": {
                "text_count": 3,
                "pdf_count": 4,
                "xlsx_count": 2,
                "unknown_count": 0,
                "total_count": 9,
            },
        },
        api_probe={"status": "SKIPPED"},
        warnings=[],
    )

    assert report["b1_entry_allowed"] is False
    assert "live TEXT-filtered library search API probe was not verified" in report["blockers"]
    assert report["path_mixing"]["mixing_observed"] is True


def test_inspect_static_identity_detects_source_type_filter_supported():
    static_identity = identity.inspect_static_identity(ROOT)

    assert static_identity["library_search_present"] is True
    assert static_identity["text_only_filter_supported"] is True
    assert static_identity["library_search_identity"]["source_type_request_param_supported"] is True
    assert static_identity["library_search_identity"]["source_type_repository_filter_supported"] is True
    assert static_identity["text_corpus_import_path"]["status"] == "present"
    assert static_identity["text_corpus_import_path"]["canonical_source_file_type"] == "TEXT"
    assert static_identity["text_corpus_import_path"]["extension_classification_supported"] is True


def test_library_search_probe_url_includes_text_source_type_filters():
    url = identity.library_search_probe_url(
        "http://localhost:8080/api/v1/library/search",
        "test query",
        3,
        source_file_types=["MARKDOWN", "MD", "TEXT", "TXT"],
    )

    assert url == (
        "http://localhost:8080/api/v1/library/search?"
        "query=test+query&limit=3&sourceFileTypes=MARKDOWN&sourceFileTypes=MD"
        "&sourceFileTypes=TEXT&sourceFileTypes=TXT"
    )


def test_source_type_from_result_prefers_search_unit_type():
    result = {
        "sourceFile": {"fileType": "PDF"},
        "searchUnit": {"sourceFileType": "TEXT"},
    }

    assert identity.source_type_from_result(result) == "TEXT"
