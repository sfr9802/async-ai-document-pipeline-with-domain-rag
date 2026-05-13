from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_retrieval_corpus_diversity_profile.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_retrieval_corpus_diversity_profile_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hidden_xlsx_redaction_counts_metadata_without_content_preview(tmp_path: Path):
    module = load_module()
    query_csv = tmp_path / "xlsx_queries.csv"
    chunk_jsonl = tmp_path / "xlsx_chunks.jsonl"
    write_csv(
        query_csv,
        [
            "query_id",
            "query",
            "expected_file_name",
            "expected_document_version_id",
            "hidden_policy",
        ],
        [
            ["xlsx_1", "monthly sales total", "hidden_safe.xlsx", "docv-xlsx-1", "exclude_hidden"],
            ["xlsx_2", "monthly sales by region", "hidden_safe.xlsx", "docv-xlsx-1", "exclude_hidden"],
        ],
    )
    write_jsonl(
        chunk_jsonl,
        [
            {
                "chunk_id": "c1",
                "source_file_id": "docv-xlsx-1",
                "source_file_name": "hidden_safe.xlsx",
                "parser_version": "xlsx-extract-v2-hidden-safe",
                "embedding_text": "redacted visible workbook metadata",
                "bm25_text": "visible workbook metadata",
                "citation_text": "Sheet1!A1:B2",
                "location_json": {"sheet": "Sheet1", "range": "A1:B2"},
                "tableId": "table-1",
                "headers": ["month", "total"],
                "text": "VISIBLE ONLY",
            }
        ],
    )
    config = base_config(
        tmp_path,
        lanes=[
            {
                "name": "XLSX",
                "hidden_xlsx_redaction": True,
                "query_sources": [{"role": "xlsx", "path": str(query_csv)}],
                "chunk_sources": [
                    {
                        "type": "jsonl",
                        "path": str(chunk_jsonl),
                        "text_fields": ["text"],
                        "source_document_fields": ["source_file_id"],
                        "document_family_fields": ["source_file_name"],
                        "source_artifact_fields": ["source_file_id"],
                        "parser_version_fields": ["parser_version"],
                    }
                ],
            }
        ],
    )

    report = module.build_report(config)
    lane = report["lanes"]["XLSX"]

    assert report["hidden_xlsx_exposed"] is False
    assert lane["hidden_xlsx_redaction"]["enabled"] is True
    assert lane["hidden_xlsx_redaction"]["content_preview_emitted"] is False
    assert lane["content_previews_emitted"] is False
    assert lane["location_json_availability"]["available_count"] == 1
    assert lane["citation_text_availability"]["available_count"] == 1
    assert lane["table_header_metadata_availability"]["table_metadata"]["available_count"] == 1
    assert lane["table_header_metadata_availability"]["header_metadata"]["available_count"] == 1
    assert "hidden" not in json.dumps(lane["source_artifact_concentration"]["top_artifacts_redacted"], ensure_ascii=False)


def test_lane_separation_keeps_text_xlsx_pdf_and_file_identity_distinct(tmp_path: Path):
    module = load_module()
    config = fixture_config(tmp_path)
    config["diagnostic_source_contract"] = diagnostic_source_contract()

    report = module.build_report(config)

    assert set(report["lanes"]) == {"TEXT_NAMU", "XLSX", "PDF_CONTENT", "PDF_FILE_IDENTITY"}
    assert report["lanes"]["PDF_FILE_IDENTITY"]["pdf_file_identity_policy"] == module.PDF_FILE_IDENTITY_ONLY_POLICY
    assert report["lanes"]["XLSX"]["pdf_file_identity_policy"] == "not_pdf_file_identity_lane"
    assert report["lanes"]["TEXT_NAMU"]["row_count"] == 2
    assert report["lanes"]["PDF_CONTENT"]["row_count"] == 1
    assert report["production_index_mutation"] is False
    assert report["vector_write_attempted"] is False
    assert report["official_denominator_registry_changed"] is False
    assert report["diagnostic_source_contract"]["PDF_CONTENT"]["target_sources"] == [
        "DART_PDF",
        "PUBLIC_INSTITUTION_PDF",
        "LOCAL_GOVERNMENT_PDF",
        "INTERNAL_REPORT_PDF",
    ]
    assert (
        report["lanes"]["TEXT_NAMU"]["diagnostic_source_contract"]["hard_negative_policy"]
        == "near_duplicate_metadata_hard_negative_without_query_echo"
    )


def test_pdf_file_identity_only_handling_blocks_content_claims(tmp_path: Path):
    module = load_module()
    identity_csv = tmp_path / "pdf_file.csv"
    write_csv(
        identity_csv,
        [
            "query_id",
            "query",
            "retrieval_lane",
            "expected_file_name",
            "source_file_name",
            "expected_document_version_id",
        ],
        [
            ["f1", "2024 04 electricity pdf", "pdf_file_lookup", "2024_04_electricity.pdf", "2024_04_electricity.pdf", "docv-1"],
            ["f2", "2024 05 electricity pdf", "pdf_file_lookup", "2024_05_electricity.pdf", "2024_05_electricity.pdf", "docv-2"],
            ["f3", "2024 05 electricity pdf", "pdf_file_lookup", "2024_05_electricity.pdf", "2024_05_electricity.pdf", "docv-2"],
        ],
    )
    config = base_config(
        tmp_path,
        lanes=[
            {
                "name": "PDF_FILE_IDENTITY",
                "identity_only": True,
                "query_sources": [{"role": "pdf-file", "path": str(identity_csv)}],
            }
        ],
    )

    report = module.build_report(config)
    lane = report["lanes"]["PDF_FILE_IDENTITY"]

    assert lane["chunk_count_profiled"] == 0
    assert lane["location_json_availability"]["not_applicable"] is True
    assert lane["citation_text_availability"]["not_applicable"] is True
    assert lane["file_identity_token_distribution"]["identity_only"] is True
    assert lane["file_identity_token_distribution"]["content_page_bbox_table_row_column_value_claimed"] is False
    assert lane["pdf_file_identity_policy"] == module.PDF_FILE_IDENTITY_ONLY_POLICY


def test_report_schema_has_required_lane_fields(tmp_path: Path):
    module = load_module()
    report = module.build_report(fixture_config(tmp_path))

    assert report["schema_version"] == "retrieval_corpus_diversity_profile_v1"
    assert report["local_llm_used_for_labels_or_judgments"] is False
    assert report["optuna_run"] is False
    assert isinstance(report["phase2_can_proceed"], bool)
    required = {
        "row_count",
        "source_document_count",
        "document_family_count",
        "parser_version_distribution",
        "source_artifact_concentration",
        "query_duplicate_rate",
        "query_near_duplicate_rate",
        "chunk_duplicate_rate",
        "chunk_near_duplicate_rate",
        "embedding_text_length_distribution",
        "bm25_text_length_distribution",
        "citation_text_length_distribution",
        "location_json_availability",
        "citation_text_availability",
        "table_header_metadata_availability",
        "file_identity_token_distribution",
        "effective_diversity_estimate",
        "classification",
        "metadata_gaps",
    }
    for lane in report["lanes"].values():
        assert required.issubset(lane.keys())
        assert lane["classification"] in {
            module.RISK_LOW,
            module.RISK_MODERATE,
            module.RISK_SUFFICIENT,
            module.RISK_UNKNOWN,
        }


def fixture_config(tmp_path: Path) -> dict:
    text_q = tmp_path / "text_queries.csv"
    text_chunks = tmp_path / "text_chunks.jsonl"
    xlsx_q = tmp_path / "xlsx_queries.csv"
    xlsx_chunks = tmp_path / "xlsx_chunks.jsonl"
    pdf_q = tmp_path / "pdf_queries.csv"
    pdf_chunks = tmp_path / "pdf_chunks.jsonl"
    pdf_file_q = tmp_path / "pdf_file_queries.csv"

    write_csv(text_q, ["query_id", "query", "expected_page_ids"], [["t1", "alpha overview", "doc-a"], ["t2", "beta overview", "doc-b"]])
    write_jsonl(
        text_chunks,
        [
            {"chunk_id": "tc1", "doc_id": "doc-a", "title": "Alpha", "chunk_text": "alpha visible text", "embedding_text": "Alpha\nalpha visible text"},
            {"chunk_id": "tc2", "doc_id": "doc-b", "title": "Beta", "chunk_text": "beta visible text", "embedding_text": "Beta\nbeta visible text"},
        ],
    )
    write_csv(xlsx_q, ["query_id", "query", "expected_document_version_id", "expected_file_name"], [["x1", "sheet total", "xlsx-doc", "book.xlsx"]])
    write_jsonl(
        xlsx_chunks,
        [
            {
                "chunk_id": "xc1",
                "source_file_id": "xlsx-doc",
                "source_file_name": "book.xlsx",
                "parser_version": "xlsx-extract-v2-hidden-safe",
                "text": "visible sheet text",
                "embedding_text": "book sheet visible",
                "bm25_text": "book sheet visible",
                "citation_text": "Sheet!A1:B2",
                "location_json": {"range": "A1:B2"},
                "tableId": "table-1",
                "headers": ["name", "value"],
            }
        ],
    )
    write_csv(pdf_q, ["query_id", "query", "expected_document_version_id", "expected_file_name"], [["p1", "pdf content", "pdf-doc", "doc.pdf"]])
    write_jsonl(
        pdf_chunks,
        [
            {
                "chunk_id": "pc1",
                "source_file_id": "pdf-doc",
                "source_file_name": "doc.pdf",
                "parser_version": "pdf-native-v1",
                "text": "pdf content paragraph",
                "embedding_text": "pdf content paragraph",
                "citation_text": "p.1",
                "location_json": {"page_no": 1},
            }
        ],
    )
    write_csv(
        pdf_file_q,
        ["query_id", "query", "expected_file_name", "source_file_name", "expected_document_version_id"],
        [["pf1", "2024 04 bill file", "2024_04_bill.pdf", "2024_04_bill.pdf", "pf-doc"]],
    )

    return base_config(
        tmp_path,
        lanes=[
            {
                "name": "TEXT_NAMU",
                "query_sources": [{"role": "text", "path": str(text_q)}],
                "chunk_sources": [
                    {
                        "type": "jsonl",
                        "path": str(text_chunks),
                        "text_fields": ["chunk_text"],
                        "source_document_fields": ["doc_id"],
                        "document_family_fields": ["title"],
                        "source_artifact_fields": ["doc_id"],
                    }
                ],
            },
            {
                "name": "XLSX",
                "hidden_xlsx_redaction": True,
                "query_sources": [{"role": "xlsx", "path": str(xlsx_q)}],
                "chunk_sources": [
                    {
                        "type": "jsonl",
                        "path": str(xlsx_chunks),
                        "text_fields": ["text"],
                        "source_document_fields": ["source_file_id"],
                        "document_family_fields": ["source_file_name"],
                        "source_artifact_fields": ["source_file_id"],
                        "parser_version_fields": ["parser_version"],
                    }
                ],
            },
            {
                "name": "PDF_CONTENT",
                "query_sources": [{"role": "pdf", "path": str(pdf_q)}],
                "chunk_sources": [
                    {
                        "type": "jsonl",
                        "path": str(pdf_chunks),
                        "text_fields": ["text"],
                        "source_document_fields": ["source_file_id"],
                        "document_family_fields": ["source_file_name"],
                        "source_artifact_fields": ["source_file_id"],
                        "parser_version_fields": ["parser_version"],
                    }
                ],
            },
            {
                "name": "PDF_FILE_IDENTITY",
                "identity_only": True,
                "query_sources": [{"role": "pdf-file", "path": str(pdf_file_q)}],
            },
        ],
    )


def base_config(tmp_path: Path, *, lanes: list[dict]) -> dict:
    return {
        "schema_version": "retrieval_corpus_diversity_profile_config_v1",
        "postgres": {},
        "near_duplicate": {"simhash_hamming_threshold": 6, "max_bucket_candidates": 50},
        "lanes": lanes,
        "outputs": {
            "json": str(tmp_path / "report.json"),
            "markdown": str(tmp_path / "report.md"),
        },
    }


def diagnostic_source_contract() -> dict:
    return {
        "PDF_CONTENT": {
            "target_sources": [
                "DART_PDF",
                "PUBLIC_INSTITUTION_PDF",
                "LOCAL_GOVERNMENT_PDF",
                "INTERNAL_REPORT_PDF",
            ],
            "hard_negative_policy": "keep_file_identity_confusions_out_of_pdf_content_success",
        },
        "XLSX": {
            "target_sources": [
                "PUBLIC_DATA_PORTAL_XLSX",
                "KOSIS_EXCEL",
                "LOCAL_GOVERNMENT_STATISTICAL_YEARBOOK_EXCEL",
                "INTERNAL_WORK_EXCEL",
            ],
            "hard_negative_policy": "preserve_hidden_redaction_and_table_shape_confusions",
        },
        "PDF_FILE_IDENTITY": {
            "target_sources": ["DART_PDF", "PUBLIC_INSTITUTION_PDF", "STATISTICAL_YEARBOOK_PDF"],
            "hard_negative_policy": "year_version_and_similar_filename_confusions",
        },
        "TEXT_NAMU": {
            "target_sources": ["NAMU_NEAR_DUPLICATE_METADATA"],
            "hard_negative_policy": "near_duplicate_metadata_hard_negative_without_query_echo",
        },
    }


def write_csv(path: Path, fields: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
