from __future__ import annotations

import json
import sys
from pathlib import Path

from openpyxl import Workbook


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "scripts"))

from app.capabilities.rag.search_unit_indexing import (
    SearchUnitIndexDocument,
    _is_duplicate_indexed,
    build_search_unit_embedding_text,
    to_chunk_row,
)


def _synthetic_ready_source_bound_report() -> dict:
    locators: dict[str, dict] = {}
    for index in range(6):
        query_id = f"text-{index:02d}"
        locators[query_id] = {
            "query_id": query_id,
            "track": "text_namu_v2_1",
            "document_id": f"text-doc-{index}",
            "document_version_id": f"docv-text-{index}",
            "search_unit_id": f"su-text-{index}",
            "source_text": f"원본 텍스트 코퍼스 문장 {index}",
            "source_content_sha256": f"text-sha-{index}",
            "text_locator": {
                "source_corpus_path": "ai/eval/corpora/rag_chunks.jsonl",
                "line_number": index + 1,
                "chunk_id": f"chunk-{index}",
                "section_path": ["섹션", str(index)],
                "title": f"텍스트 문서 {index}",
            },
        }
    for index in range(19):
        query_id = f"xlsx-{index:02d}"
        locators[query_id] = {
            "query_id": query_id,
            "track": "xlsx_business_structured",
            "workbook": "sample.xlsx",
            "source_file_path": "datasets/sample.xlsx",
            "sheet": "Sheet1",
            "range": f"A{index + 2}:D{index + 2}",
            "cell": f"D{index + 2}",
            "row_label": f"행={index}",
            "target_column": "값",
            "normalized_value": str(1000 + index),
            "search_unit_id": f"su-xlsx-{index}",
            "document_version_id": f"docv-xlsx-{index}",
            "source_content_sha256": f"xlsx-sha-{index}",
        }
    for index in range(4):
        query_id = f"pdf-{index:02d}"
        locators[query_id] = {
            "query_id": query_id,
            "track": "pdf_business_ocr_mm",
            "source_pdf_path": "local-storage/report.pdf",
            "source_pdf_filename": "report.pdf",
            "page": index + 1,
            "physical_page_index": index,
            "bbox": [1.0, 2.0 + index, 30.0, 40.0],
            "region_type": "table_body" if index % 2 else "paragraph",
            "row_label": f"PDF 원본 행 {index}",
            "target_column": "PDF 원본 열",
            "search_unit_id": f"su-pdf-{index}",
            "document_version_id": f"docv-pdf-{index}",
            "source_file_id": f"pdf-source-{index}",
            "source_content_sha256": f"pdf-sha-{index}",
            "pdf_source_text_locator": {
                "method": "pymupdf_source_pdf_text",
                "source_lines": [{"text": f"PDF 원본 행 {index}", "bbox": [1, 2, 3, 4]}],
            },
        }
    return {
        "schema_version": "official_answer_citation_source_bound_index_build_readiness_v1",
        "status": "BUILD_READY",
        "build_ready": True,
        "blocker_category": None,
        "target_index_path": "ai/eval/indexes/rag-data-official-denominator-v1",
        "index_version": "official-answer-citation-agentic-loop-v1-nonprod-official-denominator-source-bound",
        "non_production_only": True,
        "official_denominator_rows": 29,
        "official_rows_by_track": {
            "pdf_business_ocr_mm": 4,
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
        },
        "expected_official_rows_by_track": {
            "pdf_business_ocr_mm": 4,
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
        },
        "required_fields_by_track": {
            "text_namu_v2_1": [
                "document_id",
                "document_version_id",
                "search_unit_id",
                "text_locator",
            ],
            "xlsx_business_structured": [
                "workbook",
                "sheet",
                "range",
                "cell",
                "row_label",
                "target_column",
                "normalized_value",
                "search_unit_id",
                "document_version_id",
            ],
            "pdf_business_ocr_mm": [
                "source_pdf_path",
                "page",
                "physical_page_index",
                "bbox",
                "region_type",
                "row_label",
                "target_column",
                "search_unit_id",
                "document_version_id",
            ],
        },
        "missing_fields_by_query_id": {},
        "missing_source_files_by_query_id": {},
        "blocked_query_ids": [],
        "source_bound_locators_by_query_id": locators,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "production_index_path_used": False,
        "candidate_index_path_used": False,
        "promotion_evidence": False,
        "baseline_overwrite": False,
        "gold_mutation": False,
        "denominator_mutation": False,
        "human_label_mutation": False,
    }


def test_search_unit_duplicate_lookup_preserves_namespace_and_diagnostic_metadata() -> None:
    doc = SearchUnitIndexDocument(
        search_unit_id="su-xlsx-duplicate",
        claim_token="claim-xlsx-duplicate",
        index_id="source_file:source-xlsx:unit:ROW_GROUP:A2:D2",
        source_file_id="source-xlsx",
        source_file_name="sample.xlsx",
        extracted_artifact_id="artifact-xlsx",
        artifact_type="XLSX_WORKBOOK_JSON",
        unit_type="ROW_GROUP",
        unit_key="A2:D2",
        title="Sample row",
        section_path="Sheet1",
        page_start=None,
        page_end=None,
        text_content="대중교통구분: 지하철 | 노선명: 5호선 | 년월: 201902 | 승차총승객수: 15446522",
        content_sha256="content-sha",
        metadata_json={
            "fileType": "xlsx",
            "sheetName": "Sheet1",
            "cellRange": "A2:D2",
            "sourceAtomId": "source-atom-xlsx",
            "sourceRegistryVersion": "source-registry-v1",
        },
        index_metadata={
            "namespace": "diagnostic-nonprod",
            "diagnostic_only": True,
        },
    )
    embedding_text = build_search_unit_embedding_text(doc)
    chunk = to_chunk_row(
        doc,
        faiss_row_id=0,
        index_version="search-unit-live-v1",
        embedding_model="synthetic-embedding-v1",
        embedding_text=embedding_text,
    )

    assert chunk.extra["namespace"] == "diagnostic-nonprod"
    assert chunk.extra["diagnostic_only"] is True
    assert chunk.extra["sourceAtomId"] == "source-atom-xlsx"
    assert _is_duplicate_indexed(
        by_index_id={chunk.chunk_id: chunk},
        doc=doc,
        embedding_text=embedding_text,
        embedding_model="synthetic-embedding-v1",
    ) is True


def test_official_denominator_readiness_fails_closed_on_missing_locator_fields(tmp_path: Path) -> None:
    from scripts.rag_official_denominator_source_bound_index import (
        SOURCE_BOUND_INDEX_VERSION,
        TARGET_INDEX_PATH,
        build_readiness_report,
    )

    metric_config = tmp_path / "official_metric_input_config.json"
    metric_config.write_text(
        json.dumps(
            {
                "candidate_manifest": [
                    {
                        "query_id": "text-row",
                        "track": "text_namu_v2_1",
                        "question": "텍스트 질문",
                        "expected_answer": "must not be used",
                        "supporting_evidence": "must not be used",
                        "citation_locator": {"cited_chunk_ids": ["chunk-1"]},
                    },
                    {
                        "query_id": "xlsx-row",
                        "track": "xlsx_business_structured",
                        "question": "엑셀 질문",
                        "expected_answer": "must not be used",
                        "supporting_evidence": "must not be used",
                        "citation_locator": {
                            "file": "sample.xlsx",
                            "sheet": "Sheet1",
                            "range": "A2:D5",
                            "matched_cells": ["D2"],
                            "search_unit_id": "su-xlsx",
                            "document_version_id": "docv-xlsx",
                        },
                    },
                    {
                        "query_id": "pdf-row",
                        "track": "pdf_business_ocr_mm",
                        "question": "PDF 질문",
                        "expected_answer": "must not be used",
                        "supporting_evidence": "must not be used",
                        "citation_locator": {
                            "file": "source-pdf-id",
                            "page": 3,
                            "physical_page_index": 2,
                            "bbox": [1, 2, 3, 4],
                            "region_type": "table_body",
                            "search_unit_id": "su-pdf",
                        },
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = build_readiness_report(
        metric_input_config_path=metric_config,
        output_index=TARGET_INDEX_PATH,
        index_version=SOURCE_BOUND_INDEX_VERSION,
        source_roots=[tmp_path / "missing-sources"],
    )

    assert report["entrypoint_implemented"] is True
    assert report["status"] == "FAIL_CLOSED"
    assert report["blocker_category"] == "SOURCE_BOUND_OFFICIAL_DENOMINATOR_SOURCE_FIELDS_MISSING"
    assert report["target_index_path"] == "ai/eval/indexes/rag-data-official-denominator-v1"
    assert report["index_version"] == SOURCE_BOUND_INDEX_VERSION
    assert report["official_denominator_rows"] == 3
    assert report["build_ready"] is False
    assert report["target_index_built"] is False
    assert report["load_check_passed"] is False
    assert report["rerun_allowed"] is False
    assert report["generation_used_expected_answer"] is False
    assert report["generation_used_supporting_evidence"] is False
    assert report["candidate_artifacts_as_generation_source"] is False
    assert report["blocked_query_ids"] == ["text-row", "xlsx-row", "pdf-row"]
    assert report["missing_fields_by_query_id"]["text-row"] == [
        "document_id",
        "document_version_id",
        "search_unit_id",
        "text_locator",
    ]
    assert report["missing_fields_by_query_id"]["xlsx-row"] == [
        "row_label",
        "target_column",
        "normalized_value",
    ]
    assert report["missing_fields_by_query_id"]["pdf-row"] == [
        "source_pdf_path",
        "row_label",
        "target_column",
        "document_version_id",
    ]
    assert report["missing_source_files_by_query_id"]["xlsx-row"] == ["sample.xlsx"]


def test_source_bound_readiness_resolves_text_and_xlsx_from_source_roots_only(
    tmp_path: Path,
) -> None:
    from scripts.rag_official_denominator_source_bound_index import (
        SOURCE_BOUND_INDEX_VERSION,
        TARGET_INDEX_PATH,
        build_readiness_report,
    )

    source_root = tmp_path / "source-root"
    source_root.mkdir()
    corpus_root = tmp_path / "corpus-root"
    corpus_root.mkdir()
    (corpus_root / "rag_chunks.jsonl").write_text(
        json.dumps(
            {
                "chunk_id": "chunk-1",
                "doc_id": "doc-1",
                "title": "문서 제목",
                "section_id": "section-1",
                "section_path": ["개요"],
                "chunk_text": "원본 코퍼스에서만 온 문장입니다.",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    workbook_path = source_root / "sample.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["대중교통구분", "노선명", "년월", "승차총승객수"])
    sheet.append(["지하철", "5호선", "201902", 15446522])
    workbook.save(workbook_path)

    metric_config = tmp_path / "official_metric_input_config.json"
    metric_config.write_text(
        json.dumps(
            {
                "candidate_manifest": [
                    {
                        "query_id": "text-row",
                        "track": "text_namu_v2_1",
                        "question": "텍스트 질문",
                        "expected_answer": "must not be used",
                        "supporting_evidence": "must not be used",
                        "citation_locator": {"cited_chunk_ids": ["chunk-1"]},
                    },
                    {
                        "query_id": "xlsx-row",
                        "track": "xlsx_business_structured",
                        "question": "엑셀 질문",
                        "expected_answer": "must not be used",
                        "supporting_evidence": "must not be used",
                        "citation_locator": {
                            "file": "sample.xlsx",
                            "sheet": "Sheet1",
                            "range": "A2:D2",
                            "matched_cells": ["D2"],
                        },
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = build_readiness_report(
        metric_input_config_path=metric_config,
        output_index=TARGET_INDEX_PATH,
        index_version=SOURCE_BOUND_INDEX_VERSION,
        source_roots=[source_root, corpus_root],
    )

    assert report["build_ready"] is False
    assert report["official_denominator_rows"] == 2
    assert "text-row" not in report["missing_fields_by_query_id"]
    assert "xlsx-row" not in report["missing_fields_by_query_id"]
    assert "xlsx-row" not in report["missing_source_files_by_query_id"]
    assert report["generation_used_expected_answer"] is False
    assert report["generation_used_supporting_evidence"] is False
    assert report["candidate_artifacts_as_generation_source"] is False

    text_locator = report["source_bound_locators_by_query_id"]["text-row"]
    assert text_locator["document_id"] == "doc-1"
    assert text_locator["text_locator"]["chunk_id"] == "chunk-1"
    assert text_locator["text_locator"]["section_path"] == ["개요"]
    assert text_locator["document_version_id"].startswith("docv_sha256_")
    assert text_locator["search_unit_id"].startswith("su_")

    xlsx_locator = report["source_bound_locators_by_query_id"]["xlsx-row"]
    assert xlsx_locator["workbook"] == "sample.xlsx"
    assert xlsx_locator["sheet"] == "Sheet1"
    assert xlsx_locator["range"] == "A2:D2"
    assert xlsx_locator["cell"] == "D2"
    assert xlsx_locator["row_label"] == (
        "대중교통구분=지하철 | 노선명=5호선 | 년월=201902"
    )
    assert xlsx_locator["target_column"] == "승차총승객수"
    assert xlsx_locator["normalized_value"] == "15446522"
    assert xlsx_locator["document_version_id"].startswith("docv_sha256_")
    assert xlsx_locator["search_unit_id"].startswith("su_")
    assert report["source_file_inventory_by_query_id"]["xlsx-row"][0]["exists"] is True


def test_pdf_source_bound_readiness_reads_external_source_locator_without_synthesizing_table_fields(
    tmp_path: Path,
) -> None:
    from scripts.rag_official_denominator_source_bound_index import (
        SOURCE_BOUND_INDEX_VERSION,
        TARGET_INDEX_PATH,
        build_readiness_report,
    )

    external_root = tmp_path / "_external_runtime_artifacts"
    report_dir = external_root / "rag-ingestion" / "hard-cleanup-20260517" / "reports"
    report_dir.mkdir(parents=True)
    (report_dir / "pdf_answer_citation_diagnostic_review_input.jsonl").write_text(
        json.dumps(
            {
                "query_id": "pdf-row",
                "track": "pdf_business_ocr_mm",
                "diagnostic_only": True,
                "official_metric_input": False,
                "promotion_evidence": False,
                "source_file_id": "source-file-1",
                "document_version_id": "docv-source-1",
                "search_unit_id": "su-source-1",
                "page": 8,
                "physical_page_index": 7,
                "bbox": [63.65, 121.56, 227.84, 131.77],
                "region_type": "paragraph",
                "matched_text": "원본 PDF parser에서 온 문장",
                "citation_locator": {
                    "file": "source-file-1",
                    "document_version_id": "docv-source-1",
                    "search_unit_id": "su-source-1",
                    "page": 8,
                    "physical_page_index": 7,
                    "bbox": [63.65, 121.56, 227.84, 131.77],
                    "region_type": "paragraph",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    metric_config = tmp_path / "official_metric_input_config.json"
    metric_config.write_text(
        json.dumps(
            {
                "candidate_manifest": [
                    {
                        "query_id": "pdf-row",
                        "track": "pdf_business_ocr_mm",
                        "question": "PDF 질문",
                        "expected_answer": "must not be used",
                        "supporting_evidence": "must not be used",
                        "citation_locator": {
                            "file": "source-file-1",
                            "page": 8,
                            "physical_page_index": 7,
                            "bbox": [63.65, 121.56, 227.84, 131.77],
                            "region_type": "paragraph",
                            "search_unit_id": "su-source-1",
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = build_readiness_report(
        metric_input_config_path=metric_config,
        output_index=TARGET_INDEX_PATH,
        index_version=SOURCE_BOUND_INDEX_VERSION,
        source_roots=[external_root],
    )

    locator = report["source_bound_locators_by_query_id"]["pdf-row"]
    assert locator["document_version_id"] == "docv-source-1"
    assert locator["search_unit_id"] == "su-source-1"
    assert locator["page"] == 8
    assert locator["physical_page_index"] == 7
    assert locator["bbox"] == [63.65, 121.56, 227.84, 131.77]
    assert locator["region_type"] == "paragraph"
    assert "row_label" in report["missing_fields_by_query_id"]["pdf-row"]
    assert "target_column" in report["missing_fields_by_query_id"]["pdf-row"]
    assert "source_pdf_path" in report["missing_fields_by_query_id"]["pdf-row"]
    assert locator.get("row_label") in (None, "")
    assert locator.get("target_column") in (None, "")
    assert report["candidate_artifacts_as_generation_source"] is False
    assert report["generation_used_expected_answer"] is False
    assert report["generation_used_supporting_evidence"] is False
    assert report["source_file_inventory_by_query_id"]["pdf-row"][0]["kind"] == "pdf_locator_manifest"


def test_pdf_source_bound_readiness_derives_row_and_target_axis_from_source_pdf_text(
    tmp_path: Path,
) -> None:
    import fitz

    from scripts.rag_official_denominator_source_bound_index import (
        SOURCE_BOUND_INDEX_VERSION,
        TARGET_INDEX_PATH,
        build_search_unit_manifest_rows,
        build_readiness_report,
    )

    source_root = tmp_path / "source-root"
    source_root.mkdir()
    pdf_path = source_root / "source.pdf"
    doc = fitz.open()
    paragraph_page = doc.new_page(width=595, height=842)
    paragraph_page.insert_text((70, 130), "source paragraph label", fontsize=10)
    table_page = doc.new_page(width=595, height=842)
    table_page.insert_text((76, 88), "source export table", fontsize=10)
    table_page.insert_text((210, 108), "export FOB", fontsize=10)
    table_page.insert_text((310, 108), "import CIF", fontsize=10)
    table_page.insert_text((420, 108), "trade balance", fontsize=10)
    table_page.insert_text((78, 140), "2024", fontsize=10)
    table_page.insert_text((210, 140), "6,836.1", fontsize=10)
    doc.save(pdf_path)
    doc.close()

    report_dir = source_root / "reports"
    report_dir.mkdir()
    (report_dir / "pdf_answer_citation_diagnostic_review_input.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "query_id": "pdf-paragraph",
                        "track": "pdf_business_ocr_mm",
                        "diagnostic_only": True,
                        "official_metric_input": False,
                        "promotion_evidence": False,
                        "source_file_id": "source-file-1",
                        "document_version_id": "docv-source-1",
                        "search_unit_id": "su-paragraph",
                        "page": 1,
                        "physical_page_index": 0,
                        "bbox": [68, 120, 230, 136],
                        "region_type": "paragraph",
                        "citation_locator": {
                            "file": "source.pdf",
                            "document_version_id": "docv-source-1",
                            "search_unit_id": "su-paragraph",
                            "page": 1,
                            "physical_page_index": 0,
                            "bbox": [68, 120, 230, 136],
                            "region_type": "paragraph",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "query_id": "pdf-table",
                        "track": "pdf_business_ocr_mm",
                        "diagnostic_only": True,
                        "official_metric_input": False,
                        "promotion_evidence": False,
                        "source_file_id": "source-file-1",
                        "document_version_id": "docv-source-1",
                        "search_unit_id": "su-table",
                        "page": 2,
                        "physical_page_index": 1,
                        "bbox": [70, 80, 500, 180],
                        "region_type": "table_body",
                        "citation_locator": {
                            "file": "source.pdf",
                            "document_version_id": "docv-source-1",
                            "search_unit_id": "su-table",
                            "page": 2,
                            "physical_page_index": 1,
                            "bbox": [70, 80, 500, 180],
                            "region_type": "table_body",
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    metric_config = tmp_path / "official_metric_input_config.json"
    metric_config.write_text(
        json.dumps(
            {
                "candidate_manifest": [
                    {
                        "query_id": "pdf-paragraph",
                        "track": "pdf_business_ocr_mm",
                        "question": "must not be used",
                        "expected_answer": "must not be used",
                        "supporting_evidence": "must not be used",
                        "citation_locator": {
                            "file": "source-file-1",
                            "page": 1,
                            "physical_page_index": 0,
                            "bbox": [68, 120, 230, 136],
                            "region_type": "paragraph",
                            "search_unit_id": "su-paragraph",
                        },
                    },
                    {
                        "query_id": "pdf-table",
                        "track": "pdf_business_ocr_mm",
                        "question": "must not be used",
                        "expected_answer": "must not be used",
                        "supporting_evidence": "must not be used",
                        "citation_locator": {
                            "file": "source-file-1",
                            "page": 2,
                            "physical_page_index": 1,
                            "bbox": [70, 80, 500, 180],
                            "region_type": "table_body",
                            "search_unit_id": "su-table",
                        },
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = build_readiness_report(
        metric_input_config_path=metric_config,
        output_index=TARGET_INDEX_PATH,
        index_version=SOURCE_BOUND_INDEX_VERSION,
        source_roots=[source_root],
    )

    assert report["missing_fields_by_query_id"] == {}
    paragraph = report["source_bound_locators_by_query_id"]["pdf-paragraph"]
    assert paragraph["row_label"] == "source paragraph label"
    assert paragraph["target_column"] == "paragraph_text"
    assert paragraph["pdf_source_text_locator"]["method"] == "pymupdf_source_pdf_text"
    table = report["source_bound_locators_by_query_id"]["pdf-table"]
    assert table["row_label"] == "source export table"
    assert "export FOB" in table["target_column"]
    assert "import CIF" in table["target_column"]
    assert "trade balance" in table["target_column"]
    table_source_text = " | ".join(
        line["text"] for line in table["pdf_source_text_locator"]["source_lines"]
    )
    assert "2024" in table_source_text
    assert "6,836.1" in table_source_text
    manifest_rows = build_search_unit_manifest_rows(report)
    table_manifest = next(row for row in manifest_rows if row["query_id"] == "pdf-table")
    assert "2024" in table_manifest["display_text"]
    assert "6,836.1" in table_manifest["display_text"]
    assert table["pdf_source_text_locator"]["method"] == "pymupdf_source_pdf_text"
    assert report["generation_used_expected_answer"] is False
    assert report["generation_used_supporting_evidence"] is False
    assert report["candidate_artifacts_as_generation_source"] is False


def test_builds_and_load_checks_source_bound_official_denominator_index(tmp_path: Path) -> None:
    from app.capabilities.rag.embeddings import HashingEmbedder
    from scripts.rag_official_denominator_source_bound_index import (
        SOURCE_BOUND_INDEX_VERSION,
        build_source_bound_index_from_readiness,
        load_check_source_bound_index,
    )

    report = _synthetic_ready_source_bound_report()
    embedder = HashingEmbedder(dim=32)
    index_dir = tmp_path / "rag-data-official-denominator-v1"

    build_result = build_source_bound_index_from_readiness(
        report,
        output_index=index_dir,
        index_version=SOURCE_BOUND_INDEX_VERSION,
        embedder=embedder,
        max_seq_length=1024,
    )
    load_check = load_check_source_bound_index(
        index_dir,
        readiness_report=report,
        runtime_embedding_model=embedder.model_name,
    )

    assert build_result["built"] is True
    assert build_result["official_denominator_rows"] == 29
    assert build_result["track_counts"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert (index_dir / "faiss.index").exists()
    assert (index_dir / "build.json").exists()
    assert (index_dir / "ingest_manifest.json").exists()
    assert (index_dir / "search_unit_manifest.jsonl").exists()

    build_payload = json.loads((index_dir / "build.json").read_text(encoding="utf-8"))
    ingest_manifest = json.loads((index_dir / "ingest_manifest.json").read_text(encoding="utf-8"))
    manifest_rows = [
        json.loads(line)
        for line in (index_dir / "search_unit_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert build_payload["index_version"] == SOURCE_BOUND_INDEX_VERSION
    assert build_payload["official_denominator_source_bound"] is True
    assert build_payload["non_production_only"] is True
    assert build_payload["candidate_artifacts_as_generation_source"] is False
    assert build_payload["production_index_path_used"] is False
    assert ingest_manifest["index_version"] == SOURCE_BOUND_INDEX_VERSION
    assert ingest_manifest["official_denominator_source_bound_provenance"]["non_production_only"] is True
    assert ingest_manifest["official_denominator_source_bound_provenance"]["official_denominator_rows"] == 29
    assert len(manifest_rows) == 29
    assert {row["faiss_row_id"] for row in manifest_rows} == set(range(29))
    assert len({row["search_unit_id"] for row in manifest_rows}) == 29
    assert all(row["canonical_citation_payload"]["searchUnitId"] for row in manifest_rows)
    assert all(row["source_bound_official_denominator"] is True for row in manifest_rows)
    assert all("must not be used" not in row["embedding_text"] for row in manifest_rows)

    assert load_check["passed"] is True
    assert load_check["official_denominator_rows"] == 29
    assert load_check["track_counts"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert load_check["required_locator_schema_coverage_passed"] is True


def test_deterministic_search_unit_id_uses_source_locator_and_normalized_value() -> None:
    from scripts.rag_official_denominator_source_bound_index import deterministic_search_unit_id

    left = deterministic_search_unit_id(
        track="xlsx_business_structured",
        source_identity="docv-source",
        locator={"sheet": "Sheet1", "range": "A2:D2", "cell": "D2"},
        normalized_value="15446522",
    )
    reordered = deterministic_search_unit_id(
        track="xlsx_business_structured",
        source_identity="docv-source",
        locator={"cell": "D2", "range": "A2:D2", "sheet": "Sheet1"},
        normalized_value="15446522",
    )
    changed = deterministic_search_unit_id(
        track="xlsx_business_structured",
        source_identity="docv-source",
        locator={"sheet": "Sheet1", "range": "A2:D2", "cell": "D2"},
        normalized_value="15446523",
    )

    assert left == reordered
    assert left != changed
    assert left.startswith("su_")


def test_canonical_search_unit_citation_payload_preserves_track_locator_fields() -> None:
    from app.capabilities.rag.generation import RetrievedChunk
    from app.capabilities.rag.retrieval_contract import citation_payload

    xlsx = citation_payload(
        RetrievedChunk(
            chunk_id="chunk-xlsx",
            doc_id="source-file-xlsx",
            section="sheet",
            text="row text",
            score=0.9,
            search_unit_id="su-xlsx",
            source_file_id="source-file-xlsx",
            source_file_name="sample.xlsx",
            unit_type="CHUNK",
            unit_key="sheet:0:chunk:1:A2:D5",
            metadata_json={
                "source_identity": "XLSX:docv-xlsx:su-xlsx:fp-xlsx",
                "locator_fingerprint": "fp-xlsx",
                "canonical_payload_status": "canonicalizable",
                "canonical_payload_renderable": True,
                "generation_source_allowed": True,
                "official_denominator_overlap": False,
                "not_official_denominator": True,
                "track_locator_payload": {
                    "workbook": "sample.xlsx",
                    "sheet": "Sheet1",
                    "range": "A2:D5",
                    "cell": "D2",
                },
                "canonical_citation_payload": {
                    "source_family": "XLSX",
                    "source_identity": "XLSX:docv-xlsx:su-xlsx:fp-xlsx",
                    "locator_fingerprint": "fp-xlsx",
                    "search_unit_id": "su-xlsx",
                },
                "document_version_id": "docv-xlsx",
                "workbook": "sample.xlsx",
                "sheet": "Sheet1",
                "range": "A2:D5",
                "cell": "D2",
                "row_label": "2019-02 5호선",
                "target_column": "승차총승객수",
                "normalized_value": "15446522",
            },
        )
    )
    pdf = citation_payload(
        RetrievedChunk(
            chunk_id="chunk-pdf",
            doc_id="source-file-pdf",
            section="page",
            text="row text",
            score=0.8,
            search_unit_id="su-pdf",
            source_file_id="source-file-pdf",
            source_file_name="report.pdf",
            unit_type="TABLE",
            unit_key="page:65:table:1",
            page_start=65,
            page_end=65,
            metadata_json={
                "source_identity": "PDF:docv-pdf:su-pdf:fp-pdf",
                "locator_fingerprint": "fp-pdf",
                "canonical_payload_status": "canonicalizable",
                "canonical_payload_renderable": True,
                "generation_source_allowed": False,
                "official_denominator_overlap": True,
                "not_official_denominator": False,
                "track_locator_payload": {
                    "source_pdf_path": "reports/report.pdf",
                    "document_version_id": "docv-pdf",
                    "page": 65,
                    "physical_page_index": 64,
                    "bbox": [73.6, 76.45, 239.27, 88.44],
                    "region_type": "table_body",
                },
                "document_version_id": "docv-pdf",
                "source_pdf_path": "reports/report.pdf",
                "page": 65,
                "physical_page_index": 64,
                "bbox": [73.6, 76.45, 239.27, 88.44],
                "region_type": "table_body",
                "row_label": "2020",
                "target_column": "한국(원/달러) 기말",
            },
        )
    )

    assert xlsx["searchUnitId"] == "su-xlsx"
    assert xlsx["source_identity"] == "XLSX:docv-xlsx:su-xlsx:fp-xlsx"
    assert xlsx["sourceIdentity"] == "XLSX:docv-xlsx:su-xlsx:fp-xlsx"
    assert xlsx["locator_fingerprint"] == "fp-xlsx"
    assert xlsx["locatorFingerprint"] == "fp-xlsx"
    assert xlsx["canonical_payload_status"] == "canonicalizable"
    assert xlsx["canonicalPayloadStatus"] == "canonicalizable"
    assert xlsx["canonical_payload_renderable"] is True
    assert xlsx["canonicalPayloadRenderable"] is True
    assert xlsx["generation_source_allowed"] is True
    assert xlsx["generationSourceAllowed"] is True
    assert xlsx["official_denominator_overlap"] is False
    assert xlsx["not_official_denominator"] is True
    assert xlsx["track_locator_payload"]["cell"] == "D2"
    assert xlsx["trackLocatorPayload"]["range"] == "A2:D5"
    assert xlsx["canonical_citation_payload"]["search_unit_id"] == "su-xlsx"
    assert xlsx["document_version_id"] == "docv-xlsx"
    assert xlsx["workbook"] == "sample.xlsx"
    assert xlsx["sheet"] == "Sheet1"
    assert xlsx["range"] == "A2:D5"
    assert xlsx["cell"] == "D2"
    assert xlsx["row_label"] == "2019-02 5호선"
    assert xlsx["target_column"] == "승차총승객수"
    assert xlsx["normalized_value"] == "15446522"
    assert pdf["source_identity"] == "PDF:docv-pdf:su-pdf:fp-pdf"
    assert pdf["locator_fingerprint"] == "fp-pdf"
    assert pdf["canonical_payload_status"] == "canonicalizable"
    assert pdf["canonical_payload_renderable"] is True
    assert pdf["generation_source_allowed"] is False
    assert pdf["official_denominator_overlap"] is True
    assert pdf["not_official_denominator"] is False
    assert pdf["track_locator_payload"]["region_type"] == "table_body"
    assert pdf["source_pdf_path"] == "reports/report.pdf"
    assert pdf["page"] == 65
    assert pdf["physical_page_index"] == 64
    assert pdf["bbox"] == [73.6, 76.45, 239.27, 88.44]
    assert pdf["region_type"] == "table_body"
    assert pdf["row_label"] == "2020"
    assert pdf["target_column"] == "한국(원/달러) 기말"
    assert pdf["document_version_id"] == "docv-pdf"


def test_structured_source_bound_adapters_preserve_xlsx_and_pdf_fields() -> None:
    from app.capabilities.rag.citation_contract import (
        pdf_source_bound_adapter_payload,
        xlsx_source_bound_adapter_payload,
    )
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    xlsx_payload = {
        "source_bound_official_denominator": True,
        "workbook": "sample.xlsx",
        "sheet": "Sheet1",
        "range": "A2:D5",
        "cell": "D2",
        "row_label": "2019-02 5호선",
        "target_column": "승차총승객수",
        "normalized_value": "15446522",
        "searchUnitId": "su-xlsx",
        "document_version_id": "docv-xlsx",
    }
    pdf_payload = {
        "source_bound_official_denominator": True,
        "source_pdf_path": "reports/report.pdf",
        "page": 65,
        "physical_page_index": 0,
        "bbox": [73.6, 76.45, 239.27, 88.44],
        "region_type": "table_body",
        "row_label": "2020",
        "target_column": "한국(원/달러) 기말",
        "searchUnitId": "su-pdf",
        "document_version_id": "docv-pdf",
    }

    assert xlsx_source_bound_adapter_payload(xlsx_payload) == runner.xlsx_source_bound_adapter_payload(xlsx_payload)
    assert pdf_source_bound_adapter_payload(pdf_payload) == runner.pdf_source_bound_adapter_payload(pdf_payload)
    assert runner.xlsx_source_bound_adapter_payload(xlsx_payload) == {
        "adapter": "xlsx_source_bound_deterministic_v1",
        "output_from_source_bound_search_unit": True,
        "workbook": "sample.xlsx",
        "sheet": "Sheet1",
        "range": "A2:D5",
        "cell": "D2",
        "row_label": "2019-02 5호선",
        "target_column": "승차총승객수",
        "normalized_value": "15446522",
        "search_unit_id": "su-xlsx",
        "document_version_id": "docv-xlsx",
    }
    assert runner.pdf_source_bound_adapter_payload(pdf_payload) == {
        "adapter": "pdf_source_bound_deterministic_v1",
        "output_from_source_bound_search_unit": True,
        "source_pdf_path": "reports/report.pdf",
        "page": 65,
        "physical_page_index": 0,
        "bbox": [73.6, 76.45, 239.27, 88.44],
        "region_type": "table_body",
        "row_label": "2020",
        "target_column": "한국(원/달러) 기말",
        "search_unit_id": "su-pdf",
        "document_version_id": "docv-pdf",
    }


def test_structured_source_bound_adapters_reject_candidate_artifact_payloads() -> None:
    import pytest
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    candidate_payload = {
        "source_bound_official_denominator": False,
        "candidate_result_jsonl": "ai/eval/reports/rag-ingestion/xlsx_candidate.jsonl",
        "workbook": "sample.xlsx",
        "sheet": "Sheet1",
        "range": "A2:D5",
        "cell": "D2",
        "row_label": "2019-02 5호선",
        "target_column": "승차총승객수",
        "normalized_value": "15446522",
        "searchUnitId": "su-xlsx",
        "document_version_id": "docv-xlsx",
    }

    with pytest.raises(ValueError, match="source-bound SearchUnit payload"):
        runner.xlsx_source_bound_adapter_payload(candidate_payload)


def test_chunk_only_citations_cannot_be_official_compatible_for_structured_tracks() -> None:
    from app.capabilities.rag.generation import RetrievedChunk
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    chunk_only = RetrievedChunk(
        chunk_id="chunk-only",
        doc_id="doc-only",
        section="generic",
        text="generic text",
        score=0.5,
    )

    citation = runner.citations_from_chunks(
        [chunk_only],
        track="xlsx_business_structured",
        require_official_compatible=True,
        structured_adapters_enabled=True,
    )[0]

    assert citation["locator"] == {"chunk_id": "chunk-only", "doc_id": "doc-only"}
    assert citation["official_compatible_locator"] is False
    assert citation["citation_payload_validation"]["category"] == "STRUCTURED_LOCATOR_DROPPED"
    assert citation["structured_source_bound_adapter_enabled"] is True
    assert citation["structured_adapter_output_from_source_bound_search_unit"] is False
    assert "structured_source_bound_adapter" not in citation


def test_document_version_identity_is_accepted_when_source_file_id_is_absent() -> None:
    from app.capabilities.rag.generation import RetrievedChunk
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    chunk = RetrievedChunk(
        chunk_id="chunk-xlsx",
        doc_id="docv-xlsx",
        section="sheet",
        text="source row text",
        score=0.9,
        search_unit_id="su-xlsx",
        metadata_json={
            "source_bound_official_denominator": True,
            "document_version_id": "docv-xlsx",
            "workbook": "sample.xlsx",
            "sheet": "Sheet1",
            "range": "A2:D5",
            "cell": "D2",
            "row_label": "2019-02 5호선",
            "target_column": "승차총승객수",
            "normalized_value": "15446522",
        },
    )

    citation = runner.citations_from_chunks(
        [chunk],
        track="xlsx_business_structured",
        require_official_compatible=True,
        structured_adapters_enabled=True,
        allowed_manifest_search_unit_ids={"su-xlsx"},
    )[0]

    assert citation["official_compatible_locator"] is True
    assert citation["citation_payload_validation"]["ok"] is True
    assert citation["structured_adapter_output_from_source_bound_search_unit"] is True


def test_retrieved_search_unit_not_in_manifest_blocks_official_path() -> None:
    from app.capabilities.rag.generation import RetrievedChunk
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    chunk = RetrievedChunk(
        chunk_id="chunk-xlsx",
        doc_id="docv-xlsx",
        section="sheet",
        text="source row text",
        score=0.9,
        search_unit_id="su-not-in-manifest",
        metadata_json={
            "source_bound_official_denominator": True,
            "document_version_id": "docv-xlsx",
            "workbook": "sample.xlsx",
            "sheet": "Sheet1",
            "range": "A2:D5",
            "cell": "D2",
            "row_label": "2019-02 5호선",
            "target_column": "승차총승객수",
            "normalized_value": "15446522",
        },
    )

    citation = runner.citations_from_chunks(
        [chunk],
        track="xlsx_business_structured",
        require_official_compatible=True,
        structured_adapters_enabled=True,
        allowed_manifest_search_unit_ids={"su-xlsx"},
    )[0]

    assert citation["official_compatible_locator"] is False
    assert citation["citation_payload_validation"]["category"] == runner.SEARCH_UNIT_MANIFEST_MISMATCH
    assert citation["structured_adapter_output_from_source_bound_search_unit"] is False


def test_runner_blocks_rerun_when_source_bound_index_is_not_built(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    monkeypatch.setattr(runner, "AI_WORKER_ROOT", tmp_path / "ai")
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    dependency = runner.inspect_rag_index_dependency(
        Path("eval/indexes/rag-data-official-denominator-v1")
    )

    assert dependency["worker_relative_path"] == "eval/indexes/rag-data-official-denominator-v1"
    assert dependency["official_denominator_source_bound_index"] is True
    assert dependency["source_bound_index_load_checked"] is False
    assert dependency["satisfied"] is False
    assert dependency["rerun_allowed"] is False
    assert dependency["production_index_path_used"] is False
    assert dependency["candidate_index_path_used"] is False
    assert dependency["blocker_category"] == "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING"


def test_runner_rejects_basename_spoof_even_when_load_checked(tmp_path: Path) -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    index_dir = tmp_path / "rag-data-official-denominator-v1"
    index_dir.mkdir()
    (index_dir / "faiss.index").write_bytes(b"fake")
    (index_dir / "ingest_manifest.json").write_text("{}", encoding="utf-8")
    (index_dir / "search_unit_manifest.jsonl").write_text("", encoding="utf-8")
    (index_dir / "build.json").write_text(
        json.dumps({"index_version": runner.OFFICIAL_SOURCE_BOUND_INDEX_VERSION}),
        encoding="utf-8",
    )

    dependency = runner.inspect_rag_index_dependency(
        index_dir,
        source_bound_index_load_checked=True,
    )

    assert dependency["official_denominator_source_bound_index"] is False
    assert dependency["source_bound_index_load_checked"] is False
    assert dependency["rerun_allowed"] is False
    assert dependency["blocker_category"] == "NON_OFFICIAL_DENOMINATOR_INDEX_PATH"


def test_runner_requires_expected_index_version_even_when_load_checked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    monkeypatch.setattr(runner, "AI_WORKER_ROOT", tmp_path / "ai")
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    index_dir = tmp_path / "ai" / "eval" / "indexes" / "rag-data-official-denominator-v1"
    index_dir.mkdir(parents=True)
    (index_dir / "faiss.index").write_bytes(b"fake")
    (index_dir / "ingest_manifest.json").write_text("{}", encoding="utf-8")
    (index_dir / "search_unit_manifest.jsonl").write_text("", encoding="utf-8")
    (index_dir / "build.json").write_text("{}", encoding="utf-8")

    missing_version = runner.inspect_rag_index_dependency(
        index_dir,
        source_bound_index_load_checked=True,
    )

    assert missing_version["missing_files"] == []
    assert missing_version["source_bound_index_load_checked"] is False
    assert missing_version["index_version_matches_expected"] is False
    assert missing_version["rerun_allowed"] is False
    assert missing_version["blocker_category"] == runner.SOURCE_BOUND_INDEX_VERSION_MISMATCH

    (index_dir / "build.json").write_text(
        json.dumps({"index_version": "wrong-version"}),
        encoding="utf-8",
    )
    wrong_version = runner.inspect_rag_index_dependency(
        index_dir,
        source_bound_index_load_checked=True,
    )

    assert wrong_version["source_bound_index_load_checked"] is False
    assert wrong_version["index_version_matches_expected"] is False
    assert wrong_version["rerun_allowed"] is False
    assert wrong_version["blocker_category"] == runner.SOURCE_BOUND_INDEX_VERSION_MISMATCH

def test_runner_accepts_only_real_loaded_source_bound_index(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.capabilities.rag.embeddings import HashingEmbedder
    from scripts.rag_official_denominator_source_bound_index import (
        SOURCE_BOUND_INDEX_VERSION,
        build_source_bound_index_from_readiness,
    )
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    monkeypatch.setattr(runner, "AI_WORKER_ROOT", tmp_path / "ai")
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    index_dir = tmp_path / "ai" / "eval" / "indexes" / "rag-data-official-denominator-v1"
    build_source_bound_index_from_readiness(
        _synthetic_ready_source_bound_report(),
        output_index=index_dir,
        index_version=SOURCE_BOUND_INDEX_VERSION,
        embedder=HashingEmbedder(dim=16),
        max_seq_length=1024,
    )

    dependency = runner.inspect_rag_index_dependency(
        Path("eval/indexes/rag-data-official-denominator-v1"),
        source_bound_index_load_checked=True,
    )

    assert dependency["source_bound_index_load_checked"] is True
    assert dependency["index_version_matches_expected"] is True
    assert dependency["source_bound_artifact_contract_ok"] is True
    assert dependency["source_bound_artifact_load_check"]["passed"] is True
    assert dependency["rerun_allowed"] is True
    assert dependency["blocker_category"] is None


def test_source_bound_v2_preflight_blocks_stale_readiness_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.capabilities.rag.embeddings import HashingEmbedder
    from scripts.rag_official_denominator_source_bound_index import (
        SOURCE_BOUND_INDEX_VERSION,
        build_source_bound_index_from_readiness,
    )
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    monkeypatch.setattr(runner, "AI_WORKER_ROOT", tmp_path / "ai")
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    index_dir = tmp_path / "ai" / "eval" / "indexes" / "rag-data-official-denominator-v1"
    build_source_bound_index_from_readiness(
        _synthetic_ready_source_bound_report(),
        output_index=index_dir,
        index_version=SOURCE_BOUND_INDEX_VERSION,
        embedder=HashingEmbedder(dim=16),
        max_seq_length=1024,
    )
    stale = _synthetic_ready_source_bound_report()
    stale.update(
        {
            "status": "FAIL_CLOSED",
            "build_ready": False,
            "target_index_built": False,
            "load_check_passed": False,
            "rerun_allowed": False,
            "blocked_query_ids": ["text-00"],
            "missing_fields_by_query_id": {"text-00": ["text_locator"]},
        }
    )
    readiness_path = tmp_path / "readiness.json"
    readiness_path.write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")

    preflight = runner.inspect_source_bound_v2_preflight(
        Path("eval/indexes/rag-data-official-denominator-v1"),
        readiness_path=readiness_path,
        source_bound_index_load_checked=True,
    )

    assert preflight["rerun_allowed"] is False
    assert preflight["blocker_category"] == runner.STALE_SOURCE_BOUND_READINESS_ARTIFACT
    assert preflight["readiness_artifact"]["status"] == "FAIL_CLOSED"
    assert preflight["readiness_artifact"]["blocked_query_ids"] == ["text-00"]
    assert preflight["source_bound_artifact_load_check"]["passed"] is True


def test_v2_run_id_uses_separate_artifact_defaults_and_result_rows() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    args = runner.parse_args(["--run-id", runner.V2_RUN_ID])

    assert args.run_id == "official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic"
    assert args.rag_index_dir.endswith("rag-data-official-denominator-v1")
    assert args.results_jsonl.endswith(
        "v2_source_bound_results.jsonl"
    )
    assert args.summary_json.endswith(
        "v2_source_bound_summary.json"
    )
    assert args.enable_structured_source_bound_adapters is True
    assert args.source_bound_index_load_checked is True

    row = runner.result_row(
        {"query_id": "q1", "track": "text_namu_v2_1"},
        args=args,
        generated_answer="",
        generated_citations=[],
        scored_citations=[],
        discarded_off_track_citations=[],
        retrieved_evidence=[],
        answer_score=None,
        citation_support_score=None,
        scoring_attempted=False,
        failure_category="CITATION_UNSUPPORTED",
        failure_detail="diagnostic",
        agentic_loop_executed=False,
        agentic_loop_steps_count=0,
        infrastructure_blocker_category=None,
    )

    assert row["schema_version"] == args.run_id
    assert row["run_id"] == args.run_id


def test_v2_1_run_id_uses_separate_artifact_defaults() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    args = runner.parse_args(["--run-id", runner.V2_1_RUN_ID])

    assert args.run_id == "official_answer_citation_agentic_loop_run_v2_1_citation_contract_repair"
    assert args.results_jsonl.endswith(
        "v2_1_citation_results.jsonl"
    )
    assert args.summary_json.endswith(
        "v2_1_citation_summary.json"
    )
    assert args.enable_structured_source_bound_adapters is True
    assert args.source_bound_index_load_checked is True


def test_pdf_query_discards_off_track_xlsx_search_unit_from_scored_citations() -> None:
    from app.capabilities.rag.generation import RetrievedChunk
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    pdf_chunk = RetrievedChunk(
        chunk_id="chunk-pdf",
        doc_id="docv-pdf",
        section="page",
        text="pdf source text",
        score=0.9,
        search_unit_id="su-pdf",
        source_file_id="source-file-pdf",
        metadata_json={
            "source_bound_official_denominator": True,
            "track": "pdf_business_ocr_mm",
            "locator_schema": "pdf_source_bound_v1",
            "source_family": "pdf",
            "document_version_id": "docv-pdf",
            "source_pdf_path": "reports/report.pdf",
            "page": 65,
            "physical_page_index": 64,
            "bbox": [73.6, 76.45, 239.27, 88.44],
            "region_type": "table_body",
            "row_label": "2020",
            "target_column": "한국(원/달러) 기말",
        },
    )
    xlsx_chunk = RetrievedChunk(
        chunk_id="chunk-xlsx",
        doc_id="docv-xlsx",
        section="sheet",
        text="xlsx source text",
        score=0.8,
        search_unit_id="su-xlsx",
        metadata_json={
            "source_bound_official_denominator": True,
            "track": "xlsx_business_structured",
            "locator_schema": "xlsx_cell_v1",
            "source_family": "xlsx",
            "document_version_id": "docv-xlsx",
            "workbook": "sample.xlsx",
            "sheet": "Sheet1",
            "range": "A2:D5",
            "cell": "D2",
            "row_label": "2019-02 5호선",
            "target_column": "승차총승객수",
            "normalized_value": "15446522",
        },
    )

    generated = runner.citations_from_chunks(
        [pdf_chunk, xlsx_chunk],
        track="pdf_business_ocr_mm",
        require_official_compatible=True,
        structured_adapters_enabled=True,
        allowed_manifest_search_unit_ids={"su-pdf", "su-xlsx"},
    )
    contract = runner.scored_citation_contract(generated, track="pdf_business_ocr_mm")

    assert len(generated) == 2
    assert generated[1]["citation_payload_validation"]["category"] == runner.OFF_TRACK_CITATION_FOR_QUERY_TRACK
    assert contract["same_track_valid_citation_count"] == 1
    assert [item["search_unit_citation_payload"]["searchUnitId"] for item in contract["scored_citations"]] == [
        "su-pdf"
    ]
    assert contract["discarded_off_track_citation_count"] == 1
    assert contract["discarded_off_track_citations"][0]["search_unit_citation_payload"]["track"] == (
        "xlsx_business_structured"
    )
    assert contract["schema_mismatch_residual_count"] == 0


def test_result_row_separates_query_bound_from_same_track_context_citations() -> None:
    from types import SimpleNamespace

    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    query_bound_citation = {
        "citation_text": "query-bound same-track value",
        "search_unit_citation_payload": {
            "source_bound_official_denominator": True,
            "track": "pdf_business_ocr_mm",
        },
        "citation_payload_validation": {
            "ok": True,
            "manifest_track": "pdf_business_ocr_mm",
            "manifest_query_id": "pdf-row",
        },
        "structured_source_bound_adapter_enabled": True,
        "structured_adapter_output_from_source_bound_search_unit": True,
    }
    same_track_context_citation = {
        "citation_text": "same-track context value",
        "search_unit_citation_payload": {
            "source_bound_official_denominator": True,
            "track": "pdf_business_ocr_mm",
        },
        "citation_payload_validation": {
            "ok": True,
            "manifest_track": "pdf_business_ocr_mm",
            "manifest_query_id": "other-pdf-row",
        },
        "structured_source_bound_adapter_enabled": True,
        "structured_adapter_output_from_source_bound_search_unit": True,
    }
    off_track_citation = {
        "citation_text": "off-track xlsx value",
        "search_unit_citation_payload": {
            "source_bound_official_denominator": True,
            "track": "xlsx_business_structured",
        },
        "citation_payload_validation": {
            "ok": False,
            "off_track": True,
            "category": runner.OFF_TRACK_CITATION_FOR_QUERY_TRACK,
            "manifest_track": "xlsx_business_structured",
            "manifest_query_id": "xlsx-row",
        },
    }

    row = runner.result_row(
        {
            "query_id": "pdf-row",
            "track": "pdf_business_ocr_mm",
        },
        args=SimpleNamespace(
            agent_loop_backend="legacy",
            enable_structured_source_bound_adapters=True,
            allow_chunk_only_official_citation_fallback=False,
            run_id=runner.V2_1_RUN_ID,
        ),
        generated_answer="answer",
        generated_citations=[query_bound_citation, same_track_context_citation, off_track_citation],
        scored_citations=[query_bound_citation, same_track_context_citation],
        discarded_off_track_citations=[off_track_citation],
        retrieved_evidence=[{"id": "evidence"}],
        answer_score=1.0,
        citation_support_score=1.0,
        scoring_attempted=True,
        failure_category="PASS",
        failure_detail="",
        agentic_loop_executed=True,
        agentic_loop_steps_count=1,
        infrastructure_blocker_category=None,
    )

    assert row["same_track_valid_citation_count"] == 2
    assert row["query_bound_scored_citation_count"] == 1
    assert row["non_query_bound_same_track_scored_citation_count"] == 1
    assert row["discarded_off_track_citation_count"] == 1
    assert row["schema_mismatch_residual_count"] == 0


def test_v2_2_noop_backend_cannot_be_real_llm_validation() -> None:
    from types import SimpleNamespace

    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    preflight = runner.llm_backend_preflight_for_v2_2(
        SimpleNamespace(
            llm_backend="noop",
            llm_base_url="",
            llm_model="noop",
            llm_timeout_seconds=30,
            llm_max_tokens=256,
            llm_strict_json_retries=1,
        ),
        check_endpoint=False,
    )

    assert preflight["ok"] is False
    assert preflight["failure_bucket"] == "LLM_BACKEND_UNAVAILABLE"
    assert preflight["llm_backend"] == "noop"
    assert preflight["real_llm_backend_used"] is False
    assert preflight["local_llm_used"] is False
    assert "noop backend is not a real LLM validation backend" in preflight["blockers"]


def test_v2_2_unavailable_backend_fail_closes_rows_without_promotion() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    v2_1_row = {
        "run_id": runner.V2_1_RUN_ID,
        "query_id": "text_namu_v2_0017",
        "track": "text_namu_v2_1",
        "failure_category": "PARTIAL_OR_UNSUPPORTED",
        "generated_answer": "old extractive answer",
        "scored_citations": [],
        "discarded_off_track_citations": [],
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "promotion_evidence": False,
    }
    backend = {
        "ok": False,
        "llm_backend": "llamacpp",
        "real_llm_backend_used": False,
        "local_llm_used": False,
        "failure_bucket": "LLM_BACKEND_UNAVAILABLE",
        "blockers": ["local llamacpp unavailable: connection refused"],
        "timeout_seconds": 30,
        "max_tokens": 256,
        "strict_json_retries": 1,
        "model": "local-model",
    }

    rows = runner.v2_2_fail_closed_rows_from_v2_1([v2_1_row], backend)

    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == runner.V2_2_RUN_ID
    assert row["validation_bucket"] == "LLM_BACKEND_UNAVAILABLE"
    assert row["failure_category"] == "LLM_BACKEND_UNAVAILABLE"
    assert row["generated_answer"] == ""
    assert row["generated_citations"] == []
    assert row["scored_citations"] == []
    assert row["source_v2_1_generated_answer"] == "old extractive answer"
    assert row["llm_backend_validation_started"] is False
    assert row["real_llm_backend_used"] is False
    assert row["real_llm_backend_available"] is False
    assert row["real_llm_backend_used_for_row"] is False
    assert row["local_llm_used"] is False
    assert row["diagnostic_only"] is True
    assert row["promotion_evidence"] is False
    assert row["generation_used_expected_answer"] is False
    assert row["generation_used_supporting_evidence"] is False
    assert row["generation_used_gold_fields"] is False
    assert row["candidate_artifacts_as_generation_source"] is False


def test_v2_2_prompt_context_uses_same_track_source_bound_citations_only() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    row = {
        "query_id": "text-row",
        "track": "text_namu_v2_1",
        "scored_citations": [
            {
                "citation_text": "query-bound source-bound text answer",
                "search_unit_citation_payload": {
                    "source_bound_official_denominator": True,
                    "track": "text_namu_v2_1",
                    "searchUnitId": "su-text-query",
                    "search_unit_id": "su-text-query",
                    "manifest_query_id": "text-row",
                },
                "citation_payload_validation": {
                    "ok": True,
                    "manifest_query_id": "text-row",
                    "manifest_track": "text_namu_v2_1",
                    "row_query_id": "text-row",
                },
            },
            {
                "citation_text": "same-track context text",
                "search_unit_citation_payload": {
                    "source_bound_official_denominator": True,
                    "track": "text_namu_v2_1",
                    "searchUnitId": "su-text-other",
                    "search_unit_id": "su-text-other",
                    "manifest_query_id": "other-text-row",
                },
                "citation_payload_validation": {
                    "ok": True,
                    "manifest_query_id": "other-text-row",
                    "manifest_track": "text_namu_v2_1",
                    "row_query_id": "text-row",
                },
            },
        ],
        "discarded_off_track_citations": [
            {
                "citation_text": "off-track xlsx value must not enter prompt",
                "search_unit_citation_payload": {
                    "source_bound_official_denominator": True,
                    "track": "xlsx_business_structured",
                },
                "citation_payload_validation": {
                    "off_track": True,
                    "category": runner.OFF_TRACK_CITATION_FOR_QUERY_TRACK,
                    "manifest_track": "xlsx_business_structured",
                },
            }
        ],
    }

    context = runner.build_v2_2_prompt_context(row, use_query_bound_only=False)
    prompt = runner.build_v2_2_llm_prompt(
        row,
        context,
        question="질문 텍스트",
    )

    assert context["same_track_scored_citation_count"] == 2
    assert context["query_bound_scored_citation_count"] == 1
    assert context["non_query_bound_same_track_context_used"] is True
    assert context["off_track_citation_count_excluded_from_prompt"] == 1
    assert "query-bound source-bound text answer" in prompt
    assert "same-track context text" in prompt
    assert "off-track xlsx value must not enter prompt" not in prompt
    assert "expected_answer" not in prompt
    assert "supporting_evidence" not in prompt
    assert "gold" not in prompt.lower()
    assert "candidate" not in prompt.lower()


def test_v2_2_structured_adapter_output_is_retained_without_llm_overwrite() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    v2_1_row = {
        "run_id": runner.V2_1_RUN_ID,
        "query_id": "gq_pdf_section_question_001",
        "track": "pdf_business_ocr_mm",
        "failure_category": "PASS",
        "generated_answer": "adapter answer 518.4",
        "scored_citations": [
            {
                "citation_text": "2024 | 6,836.1 | 518.4",
                "structured_source_bound_adapter_enabled": True,
                "structured_adapter_output_from_source_bound_search_unit": True,
                "structured_source_bound_adapter": {
                    "output_from_source_bound_search_unit": True,
                    "normalized_value": "518.4",
                },
                "search_unit_citation_payload": {
                    "source_bound_official_denominator": True,
                    "track": "pdf_business_ocr_mm",
                    "searchUnitId": "su-pdf",
                    "search_unit_id": "su-pdf",
                    "manifest_query_id": "gq_pdf_section_question_001",
                },
                "citation_payload_validation": {
                    "ok": True,
                    "manifest_query_id": "gq_pdf_section_question_001",
                    "manifest_track": "pdf_business_ocr_mm",
                },
            }
        ],
        "discarded_off_track_citations": [],
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "promotion_evidence": False,
    }
    backend = {
        "ok": True,
        "llm_backend": "llamacpp",
        "real_llm_backend_used": True,
        "local_llm_used": True,
        "timeout_seconds": 30,
        "max_tokens": 256,
        "strict_json_retries": 1,
        "model": "local-model",
    }

    row = runner.v2_2_retained_structured_adapter_row(v2_1_row, backend)

    assert row["run_id"] == runner.V2_2_RUN_ID
    assert row["validation_bucket"] == "PASS_RETAINED"
    assert row["generated_answer"] == "adapter answer 518.4"
    assert row["llm_answer"] == ""
    assert row["llm_invoked_for_row"] is False
    assert row["real_llm_backend_available"] is True
    assert row["real_llm_backend_used"] is False
    assert row["real_llm_backend_used_for_row"] is False
    assert row["structured_adapter_output_retained"] is True
    assert row["structured_adapter_overwritten_by_llm"] is False
    assert row["prompt_context_source_bound_only"] is True
    assert row["promotion_evidence"] is False


def test_v3_run_id_is_separate_and_source_bound_defaults_are_locked() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    args = runner.parse_args(["--run-id", runner.V3_RUN_ID])

    assert args.run_id == "official_answer_citation_agentic_loop_run_v3_comparable_live_measurement"
    assert args.run_id not in {
        runner.RUN_ID,
        runner.V2_RUN_ID,
        runner.V2_1_RUN_ID,
        runner.V2_2_RUN_ID,
    }
    assert runner.is_source_bound_manifest_run(args.run_id) is True
    assert args.source_bound_index_load_checked is True
    assert args.enable_structured_source_bound_adapters is True
    assert args.results_jsonl.endswith("v3_comparable_results.jsonl")
    assert args.summary_json.endswith("v3_comparable_summary.json")
    assert runner.V3_RUN_ID in runner.RUN_IDS_WITH_DISABLED_SUMMARY_MARKDOWN
    assert args.summary_md == ""
    assert "v2_2_llm_backend_validation" not in args.results_jsonl


def test_v3_requires_completed_v2_2_preflight_before_generation() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    rows = [
        {
            "run_id": runner.V2_2_RUN_ID,
            "query_id": f"row-{index:02d}",
            "track": "text_namu_v2_1" if index < 6 else "xlsx_business_structured",
            "failure_category": "PASS",
            "validation_bucket": "PASS_RETAINED",
            "promotion_evidence": False,
            "generation_used_expected_answer": False,
            "generation_used_supporting_evidence": False,
            "generation_used_gold_fields": False,
            "candidate_artifacts_as_generation_source": False,
            "prompt_context_source_bound_only": True,
        }
        for index in range(29)
    ]
    rows[17]["query_id"] = "text_namu_v2_0017"
    rows[17]["track"] = "text_namu_v2_1"
    rows[17]["failure_category"] = "PARTIAL_OR_UNSUPPORTED"
    rows[17]["validation_bucket"] = "LLM_SYNTHESIS_REGRESSED"
    summary = {
        "run_id": runner.V2_2_RUN_ID,
        "status": "LLM_BACKEND_VALIDATION_COMPLETED",
        "llm_backend_validation_status": "LLM_BACKEND_VALIDATION_COMPLETED",
        "result_count": 29,
        "scored_count": 29,
        "pass_count": 28,
        "promotion_evidence": False,
        "real_llm_backend_used": True,
        "source_bound_index_used": True,
        "canonical_search_unit_payload_used": True,
        "prompt_context_source_bound_only": True,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "schema_mismatch_residual_count": 0,
        "query_bound_evidence_gap_count": 0,
        "validation_bucket_counts": {"PASS_RETAINED": 28, "LLM_SYNTHESIS_REGRESSED": 1},
    }
    attribution = {"run_id": runner.V2_2_RUN_ID, "promotion_evidence": False}

    preflight = runner.v2_2_artifact_consistency_preflight(
        summary=summary,
        attribution=attribution,
        rows=rows,
    )
    blocked = runner.v2_2_artifact_consistency_preflight(
        summary={**summary, "llm_backend_validation_status": "LLM_BACKEND_UNAVAILABLE_FAIL_CLOSED"},
        attribution=attribution,
        rows=rows,
    )

    assert preflight["ok"] is True
    assert preflight["ready_for_v3_comparable_live_measurement"] is True
    assert preflight["completed_run_id"] == runner.V2_2_RUN_ID
    assert preflight["pass_count"] == 28
    assert preflight["remaining_failure_query_ids"] == ["text_namu_v2_0017"]
    assert blocked["ok"] is False
    assert "v2_2_llm_backend_validation_not_completed" in blocked["errors"]


def test_v3_1_preflight_requires_exact_current_denominator_query_ids() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    rows = []
    for index in range(4):
        rows.append(
            {
                "run_id": runner.V3_RUN_ID,
                "query_id": f"pdf-{index}",
                "track": "pdf_business_ocr_mm",
                "failure_category": "PASS",
                "structured_adapter_output_retained": True,
            }
        )
    for index in range(6):
        rows.append(
            {
                "run_id": runner.V3_RUN_ID,
                "query_id": f"text-{index}",
                "track": "text_namu_v2_1",
                "failure_category": "PASS" if index == 0 else "PARTIAL_OR_UNSUPPORTED",
                "structured_adapter_output_retained": False,
            }
        )
    for index in range(19):
        rows.append(
            {
                "run_id": runner.V3_RUN_ID,
                "query_id": f"xlsx-{index}",
                "track": "xlsx_business_structured",
                "failure_category": "PASS",
                "structured_adapter_output_retained": True,
            }
        )
    summary = {
        "run_id": runner.V3_RUN_ID,
        "status": "COMPARABLE_LIVE_MEASUREMENT_V3_COMPLETED",
        "result_count": 29,
        "pass_count": 24,
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
    }
    attribution = {"run_id": runner.V3_RUN_ID, "promotion_evidence": False}
    expected_query_ids = {row["query_id"] for row in rows}

    ok = runner.v3_artifact_consistency_preflight(
        summary=summary,
        attribution=attribution,
        rows=rows,
        expected_query_ids=expected_query_ids,
    )
    mismatched = runner.v3_artifact_consistency_preflight(
        summary=summary,
        attribution=attribution,
        rows=[{**rows[0], "query_id": "stale-pdf-0"}, *rows[1:]],
        expected_query_ids=expected_query_ids,
    )

    assert ok["ok"] is True
    assert mismatched["ok"] is False
    assert "v3_query_ids_do_not_match_current_official_denominator" in mismatched["errors"]


def test_v3_structured_rows_are_retained_and_text_rows_use_llm(monkeypatch) -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    structured_citation = {
        "citation_text": "source-bound table body value 518.4",
        "structured_adapter_output_from_source_bound_search_unit": True,
        "structured_source_bound_adapter": {
            "output_from_source_bound_search_unit": True,
            "normalized_value": "518.4",
        },
        "search_unit_citation_payload": {
            "source_bound_official_denominator": True,
            "track": "pdf_business_ocr_mm",
            "searchUnitId": "su-pdf",
            "search_unit_id": "su-pdf",
            "manifest_query_id": "pdf-row",
        },
        "citation_payload_validation": {
            "ok": True,
            "manifest_query_id": "pdf-row",
            "manifest_track": "pdf_business_ocr_mm",
        },
    }
    text_citation = {
        "citation_text": "정답 문장",
        "search_unit_citation_payload": {
            "source_bound_official_denominator": True,
            "track": "text_namu_v2_1",
            "searchUnitId": "su-text",
            "search_unit_id": "su-text",
            "manifest_query_id": "text-row",
        },
        "citation_payload_validation": {
            "ok": True,
            "manifest_query_id": "text-row",
            "manifest_track": "text_namu_v2_1",
            "row_query_id": "text-row",
        },
    }
    v2_2_rows = [
        {
            "run_id": runner.V2_2_RUN_ID,
            "query_id": "pdf-row",
            "track": "pdf_business_ocr_mm",
            "failure_category": "PASS",
            "generated_answer": "adapter answer 518.4",
            "generated_citations": [structured_citation],
            "scored_citations": [structured_citation],
            "discarded_off_track_citations": [],
            "promotion_evidence": False,
        },
        {
            "run_id": runner.V2_2_RUN_ID,
            "query_id": "text-row",
            "track": "text_namu_v2_1",
            "failure_category": "PASS",
            "generated_answer": "old retained answer",
            "generated_citations": [text_citation],
            "scored_citations": [text_citation],
            "discarded_off_track_citations": [],
            "promotion_evidence": False,
        },
    ]
    source_rows = {
        "text-row": {
            "query_id": "text-row",
            "track": "text_namu_v2_1",
            "question": "질문",
            "expected_answer": "정답 문장",
            "supporting_evidence": "정답 문장",
        }
    }
    backend = {
        "ok": True,
        "llm_backend": "llamacpp",
        "real_llm_backend_used": True,
        "local_llm_used": True,
        "timeout_seconds": 30,
        "max_tokens": 256,
        "strict_json_retries": 1,
        "retry_policy": "strict_json_retries_then_fail_closed",
        "model": "local-model",
    }

    monkeypatch.setattr(
        runner,
        "call_v3_llm_synthesis",
        lambda *, prompt, backend_preflight: ("정답 문장", {"attempt_count": 1, "prompt_seen": prompt}),
    )

    rows = runner.build_v3_rows_from_v2_2(
        v2_2_rows=v2_2_rows,
        source_rows_by_id=source_rows,
        backend_preflight=backend,
        prompt_context_mode="same-track-scored-context",
    )

    structured_row = next(row for row in rows if row["query_id"] == "pdf-row")
    text_row = next(row for row in rows if row["query_id"] == "text-row")
    assert structured_row["run_id"] == runner.V3_RUN_ID
    assert structured_row["result_bucket"] == "PASS_RETAINED_BY_STRUCTURED_ADAPTER"
    assert structured_row["generated_answer"] == "adapter answer 518.4"
    assert structured_row["llm_invoked_for_row"] is False
    assert structured_row["structured_adapter_output_retained"] is True
    assert structured_row["structured_adapter_overwritten_by_llm"] is False
    assert text_row["run_id"] == runner.V3_RUN_ID
    assert text_row["result_bucket"] == "LLM_SYNTHESIS_PASS"
    assert text_row["generated_answer"] == "정답 문장"
    assert text_row["llm_invoked_for_row"] is True
    assert text_row["real_llm_backend_used_for_row"] is True
    assert text_row["structured_adapter_output_retained"] is False
    assert all(row["candidate_artifacts_as_generation_source"] is False for row in rows)
    assert all(row["generation_used_expected_answer"] is False for row in rows)
    assert all(row["generation_used_supporting_evidence"] is False for row in rows)
    assert all(row["generation_used_gold_fields"] is False for row in rows)
    assert all("expected_answer" not in row for row in rows)
    assert all("supporting_evidence" not in row for row in rows)


def test_v3_prompt_context_modes_exclude_off_track_and_gold_candidate_text() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    query_bound = {
        "citation_text": "query-bound text",
        "search_unit_citation_payload": {
            "source_bound_official_denominator": True,
            "track": "text_namu_v2_1",
            "searchUnitId": "su-query",
            "search_unit_id": "su-query",
            "manifest_query_id": "text-row",
        },
        "citation_payload_validation": {
            "ok": True,
            "manifest_query_id": "text-row",
            "manifest_track": "text_namu_v2_1",
            "row_query_id": "text-row",
        },
    }
    same_track = {
        "citation_text": "same-track context text",
        "search_unit_citation_payload": {
            "source_bound_official_denominator": True,
            "track": "text_namu_v2_1",
            "searchUnitId": "su-other",
            "search_unit_id": "su-other",
            "manifest_query_id": "other-text-row",
        },
        "citation_payload_validation": {
            "ok": True,
            "manifest_query_id": "other-text-row",
            "manifest_track": "text_namu_v2_1",
            "row_query_id": "text-row",
        },
    }
    off_track = {
        "citation_text": "off-track xlsx value",
        "search_unit_citation_payload": {
            "source_bound_official_denominator": True,
            "track": "xlsx_business_structured",
        },
        "citation_payload_validation": {
            "off_track": True,
            "category": runner.OFF_TRACK_CITATION_FOR_QUERY_TRACK,
            "manifest_track": "xlsx_business_structured",
        },
    }
    row = {
        "query_id": "text-row",
        "track": "text_namu_v2_1",
        "scored_citations": [query_bound, same_track],
        "discarded_off_track_citations": [off_track],
    }

    query_bound_context = runner.build_v3_prompt_context(row, prompt_context_mode="query-bound-only")
    same_track_context = runner.build_v3_prompt_context(
        row,
        prompt_context_mode="same-track-scored-context",
    )
    prompt = runner.build_v3_llm_prompt(row, same_track_context, question="질문")

    assert query_bound_context["query_bound_evidence_only"] is True
    assert query_bound_context["same_track_scored_citation_count"] == 1
    assert query_bound_context["non_query_bound_same_track_context_used"] is False
    assert same_track_context["query_bound_evidence_only"] is False
    assert same_track_context["same_track_scored_citation_count"] == 2
    assert same_track_context["non_query_bound_same_track_context_used"] is True
    assert same_track_context["off_track_citation_count_excluded_from_prompt"] == 1
    assert "query-bound text" in prompt
    assert "same-track context text" in prompt
    assert "off-track xlsx value" not in prompt
    assert "expected_answer" not in prompt
    assert "supporting_evidence" not in prompt
    assert "gold" not in prompt.lower()
    assert "candidate" not in prompt.lower()


def test_v3_locator_validation_reports_pdf_source_path_byte_equality() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    expected_citation = {
        "search_unit_citation_payload": {
            "source_pdf_path": "reports/report.pdf",
            "page": 3,
            "physical_page_index": 2,
            "bbox": [1.0, 2.0, 3.0, 4.0],
            "region_type": "paragraph",
            "search_unit_id": "su-pdf",
            "document_version_id": "docv-pdf",
            "source_bound_official_denominator": True,
        }
    }
    generated_locator = {
        "source_pdf_path": "reports/repert.pdf",
        "page": 3,
        "physical_page_index": 2,
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "region_type": "paragraph",
        "search_unit_id": "su-pdf",
        "document_version_id": "docv-pdf",
    }

    validation = runner.llm_generated_locator_validation(
        generated_locators=[generated_locator],
        expected_citations=[expected_citation],
        cited_search_unit_ids=["su-pdf"],
        source_family="PDF",
    )

    source_path = validation["field_comparisons_by_search_unit_id"]["su-pdf"]["source_pdf_path"]
    assert validation["ok"] is False
    assert validation["mismatched_fields_by_search_unit_id"] == {"su-pdf": ["source_pdf_path"]}
    assert source_path["byte_equal"] is False
    assert source_path["normalized_equal"] is False


def test_v3_locator_validation_reports_xlsx_row_label_byte_and_normalized_equality() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    expected_citation = {
        "search_unit_citation_payload": {
            "workbook": "book.xlsx",
            "sheet": "일반현황",
            "range": "A1:J2",
            "cell": "J2",
            "row_label": "장기요양기관코드=1 | 우편번호=2",
            "target_column": "기관별 상세주소",
            "normalized_value": "서울",
            "search_unit_id": "su-xlsx",
            "document_version_id": "docv-xlsx",
            "source_bound_official_denominator": True,
        }
    }
    spacing_only_locator = {
        "workbook": "book.xlsx",
        "sheet": "일반현황",
        "range": "A1:J2",
        "cell": "J2",
        "row_label": "장기요양기관코드=1|우편번호=2",
        "target_column": "기관별 상세주소",
        "normalized_value": "서울",
        "search_unit_id": "su-xlsx",
        "document_version_id": "docv-xlsx",
    }
    semantic_mismatch_locator = {
        **spacing_only_locator,
        "row_label": "장기요양기관코드=1 | 우편번호=2 | 기관별 상세주소=서울",
    }

    spacing_validation = runner.llm_generated_locator_validation(
        generated_locators=[spacing_only_locator],
        expected_citations=[expected_citation],
        cited_search_unit_ids=["su-xlsx"],
        source_family="XLSX",
    )
    mismatch_validation = runner.llm_generated_locator_validation(
        generated_locators=[semantic_mismatch_locator],
        expected_citations=[expected_citation],
        cited_search_unit_ids=["su-xlsx"],
        source_family="XLSX",
    )

    spacing_row_label = spacing_validation["field_comparisons_by_search_unit_id"]["su-xlsx"]["row_label"]
    mismatch_row_label = mismatch_validation["field_comparisons_by_search_unit_id"]["su-xlsx"]["row_label"]
    assert spacing_validation["ok"] is False
    assert spacing_row_label["byte_equal"] is False
    assert spacing_row_label["normalized_equal"] is True
    assert mismatch_validation["ok"] is False
    assert mismatch_row_label["byte_equal"] is False
    assert mismatch_row_label["normalized_equal"] is False


def test_v3_text_namu_0017_diagnostic_fields_are_emitted() -> None:
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    row = runner.v3_text_diagnostics(
        query_id="text_namu_v2_0017",
        source_row={
            "expected_answer": "정답 문장",
            "supporting_evidence": "근거 문장",
        },
        llm_answer="정답 문장",
        citation_text="근거 문장",
        score={"failure_category": "PASS", "answer_score": 1.0, "citation_support_score": 1.0},
        prompt_context={
            "non_query_bound_same_track_context_used": True,
            "query_bound_evidence_only": False,
            "policy_errors": [],
            "prompt_context_source_bound_only": True,
        },
    )

    assert set(row) == {
        "llm_output_contains_expected_answer_span_for_scoring",
        "citation_support_present",
        "answer_citation_support_jointly_satisfied",
        "non_query_bound_same_track_context_used",
        "non_query_bound_same_track_context_distracted",
        "scorer_normalization_issue_possible",
        "prompt_context_policy",
    }
    assert row["llm_output_contains_expected_answer_span_for_scoring"] is True
    assert row["citation_support_present"] is True
    assert row["answer_citation_support_jointly_satisfied"] is True
    assert row["non_query_bound_same_track_context_used"] is True
    assert row["non_query_bound_same_track_context_distracted"] is False
    assert row["scorer_normalization_issue_possible"] is False
    assert row["prompt_context_policy"]["mode"] == "same-track-scored-context"


def test_text_query_discards_off_track_xlsx_search_unit_from_scored_citations() -> None:
    from app.capabilities.rag.generation import RetrievedChunk
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    text_chunk = RetrievedChunk(
        chunk_id="chunk-text",
        doc_id="docv-text",
        section="text",
        text="text source",
        score=0.9,
        search_unit_id="su-text",
        metadata_json={
            "source_bound_official_denominator": True,
            "track": "text_namu_v2_1",
            "locator_schema": "text_locator_v1",
            "source_family": "text",
            "document_id": "doc-text",
            "document_version_id": "docv-text",
            "text_locator": {
                "chunk_id": "chunk-text",
                "line_number": 42,
                "source_corpus_path": "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl",
            },
        },
    )
    xlsx_chunk = RetrievedChunk(
        chunk_id="chunk-xlsx",
        doc_id="docv-xlsx",
        section="sheet",
        text="xlsx source text",
        score=0.8,
        search_unit_id="su-xlsx",
        metadata_json={
            "source_bound_official_denominator": True,
            "track": "xlsx_business_structured",
            "locator_schema": "xlsx_cell_v1",
            "source_family": "xlsx",
            "document_version_id": "docv-xlsx",
            "workbook": "sample.xlsx",
            "sheet": "Sheet1",
            "range": "A2:D5",
            "cell": "D2",
            "row_label": "2019-02 5호선",
            "target_column": "승차총승객수",
            "normalized_value": "15446522",
        },
    )

    generated = runner.citations_from_chunks(
        [text_chunk, xlsx_chunk],
        track="text_namu_v2_1",
        require_official_compatible=True,
        structured_adapters_enabled=True,
        allowed_manifest_search_unit_ids={"su-text", "su-xlsx"},
    )
    contract = runner.scored_citation_contract(generated, track="text_namu_v2_1")

    assert generated[1]["citation_payload_validation"]["category"] == runner.OFF_TRACK_CITATION_FOR_QUERY_TRACK
    assert contract["same_track_valid_citation_count"] == 1
    assert [item["search_unit_citation_payload"]["searchUnitId"] for item in contract["scored_citations"]] == [
        "su-text"
    ]
    assert contract["discarded_off_track_citation_count"] == 1
    assert contract["schema_mismatch_residual_count"] == 0


def test_same_track_locator_requirements_remain_fail_closed() -> None:
    from app.capabilities.rag.generation import RetrievedChunk
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    pdf_missing_bbox = RetrievedChunk(
        chunk_id="chunk-pdf",
        doc_id="docv-pdf",
        section="page",
        text="pdf source text",
        score=0.9,
        search_unit_id="su-pdf",
        metadata_json={
            "source_bound_official_denominator": True,
            "track": "pdf_business_ocr_mm",
            "locator_schema": "pdf_source_bound_v1",
            "document_version_id": "docv-pdf",
            "source_pdf_path": "reports/report.pdf",
            "page": 65,
            "physical_page_index": 64,
            "region_type": "table_body",
            "row_label": "2020",
            "target_column": "한국(원/달러) 기말",
        },
    )

    generated = runner.citations_from_chunks(
        [pdf_missing_bbox],
        track="pdf_business_ocr_mm",
        require_official_compatible=True,
        structured_adapters_enabled=True,
        allowed_manifest_search_unit_ids={"su-pdf"},
    )
    contract = runner.scored_citation_contract(generated, track="pdf_business_ocr_mm")

    assert generated[0]["citation_payload_validation"]["category"] == runner.STRUCTURED_LOCATOR_DROPPED
    assert generated[0]["citation_payload_validation"]["validation_category"] == runner.SAME_TRACK_LOCATOR_INCOMPLETE
    assert generated[0]["citation_payload_validation"]["missing_fields"] == ["bbox"]
    assert contract["same_track_valid_citation_count"] == 0
    assert contract["schema_mismatch_residual_count"] == 1


def test_runner_fail_closes_when_only_off_track_citations_are_retrieved() -> None:
    from types import SimpleNamespace

    from app.capabilities.rag.generation import RetrievedChunk
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    class XlsxOnlyRetriever:
        def retrieve(self, _query: str) -> object:
            return SimpleNamespace(
                results=[
                    RetrievedChunk(
                        chunk_id="chunk-xlsx",
                        doc_id="docv-xlsx",
                        section="xlsx_business_structured",
                        text="off-track xlsx value 15446522",
                        score=0.9,
                        search_unit_id="su-xlsx",
                        metadata_json={
                            "source_bound_official_denominator": True,
                            "track": "xlsx_business_structured",
                            "locator_schema": "xlsx_cell_v1",
                            "source_family": "xlsx",
                            "manifest_query_id": "xlsx-row",
                            "document_version_id": "docv-xlsx",
                            "workbook": "sample.xlsx",
                            "sheet": "Sheet1",
                            "range": "A2:D5",
                            "cell": "D2",
                            "row_label": "2019-02 5호선",
                            "target_column": "승차총승객수",
                            "normalized_value": "15446522",
                        },
                    )
                ]
            )

    args = SimpleNamespace(
        agent_loop_backend="legacy",
        agent_max_iter=1,
        agent_max_total_ms=1000,
        agent_max_llm_tokens=1000,
        agent_min_stop_confidence=0.0,
        enable_structured_source_bound_adapters=True,
        allow_chunk_only_official_citation_fallback=False,
        run_id=runner.V2_1_RUN_ID,
    )
    rows = [
        {
            "query_id": "pdf-row",
            "track": "pdf_business_ocr_mm",
            "question": "PDF row-bound answer should fail closed",
            "expected_answer": "15446522",
            "supporting_evidence": "15446522",
        }
    ]

    out = runner.execute_agentic_generation_rows(
        rows,
        args,
        {
            "_retriever": XlsxOnlyRetriever(),
            "source_bound_manifest_search_unit_ids": ["su-xlsx"],
            "index_dependency": {"build_metadata": {}},
        },
    )

    assert len(out) == 1
    row = out[0]
    assert row["failure_category"] == runner.OFF_TRACK_CITATION_FOR_QUERY_TRACK
    assert row["score_status"] == "FAIL_CLOSED"
    assert row["scoring_attempted"] is False
    assert row["answer_score"] is None
    assert row["citation_support_score"] is None
    assert row["same_track_valid_citation_count"] == 0
    assert row["discarded_off_track_citation_count"] == 1
    assert row["scored_citations"] == []
    assert row["discarded_off_track_citations"][0]["citation_payload_validation"]["manifest_query_id"] == "xlsx-row"
    assert "#xlsx_business_structured" not in row["generated_answer"]


def test_claude_user_message_carries_pdf_xlsx_locators_without_gold_metadata() -> None:
    from app.capabilities.rag.claude_generation import _build_user_message
    from app.capabilities.rag.generation import RetrievedChunk

    pdf_chunk = RetrievedChunk(
        chunk_id="chunk-pdf",
        doc_id="docv-pdf",
        section="page-8",
        text="실업률은 모든 연령계층에서 상승했다.",
        score=0.91,
        search_unit_id="su-pdf",
        metadata_json={
            "source_atom_hydrated_from_registry": True,
            "source_family": "PDF",
            "track": "pdf_business_ocr_mm",
            "source_pdf_path": "local-storage/report.pdf",
            "page": 8,
            "physical_page_index": 7,
            "bbox": [63.65, 121.56, 227.84, 131.77],
            "region_type": "paragraph",
            "expected_answer": "DO_NOT_LEAK_EXPECTED",
            "supporting_evidence": "DO_NOT_LEAK_EVIDENCE",
            "gold_label": "DO_NOT_LEAK_GOLD",
        },
    )
    xlsx_chunk = RetrievedChunk(
        chunk_id="chunk-xlsx",
        doc_id="docv-xlsx",
        section="철도",
        text="5호선 201902 승차총승객수는 15446522이다.",
        score=0.88,
        search_unit_id="su-xlsx",
        metadata_json={
            "source_atom_hydrated_from_registry": True,
            "source_family": "XLSX",
            "track": "xlsx_business_structured",
            "workbook": "서울시 대중교통 수단별 이용 현황.xlsx",
            "sheet": "철도",
            "range": "A352:D401",
            "cell": "D352",
            "row_label": "대중교통구분=지하철 | 노선명=5호선 | 년월=201902",
            "target_column": "승차총승객수",
            "normalized_value": "15446522",
            "answerability_label": "DO_NOT_LEAK_LABEL",
        },
    )

    message = _build_user_message("5호선 201902 승차총승객수?", [pdf_chunk, xlsx_chunk])

    assert "Citation ID: [S1]" in message
    assert "Citation ID: [S2]" in message
    assert "PDF locator:" in message
    assert "source_pdf_path=local-storage/report.pdf" in message
    assert "page=8" in message
    assert "bbox=[63.65, 121.56, 227.84, 131.77]" in message
    assert "XLSX locator:" in message
    assert "workbook=서울시 대중교통 수단별 이용 현황.xlsx" in message
    assert "sheet=철도" in message
    assert "range=A352:D401" in message
    assert "cell=D352" in message
    assert "target_column=승차총승객수" in message
    assert "normalized_value=15446522" in message
    assert "DO_NOT_LEAK" not in message


def test_claude_user_message_omits_candidate_locator_when_source_registry_hydration_required() -> None:
    from app.capabilities.rag.claude_generation import _build_user_message
    from app.capabilities.rag.generation import RetrievedChunk

    chunk = RetrievedChunk(
        chunk_id="candidate-xlsx",
        doc_id="docv-xlsx",
        section="Sheet1",
        text="검증 전 후보 표 조각입니다.",
        score=0.74,
        search_unit_id="su-candidate",
        page_start=9,
        page_end=9,
        metadata_json={
            "source_atom_hydrated_from_registry": False,
            "source_family": "XLSX",
            "source_atom_id": "srcatom-candidate",
            "canonical_citation_payload": {
                "sheet": "HiddenCandidate",
                "cell": "Z99",
                "range": "Z99:Z100",
                "normalized_value": "DO_NOT_PROMOTE",
            },
            "workbook": "candidate.xlsx",
            "sheet": "HiddenCandidate",
            "cell": "Z99",
            "range": "Z99:Z100",
            "source_pdf_path": "local-storage/candidate.pdf",
            "bbox": [1, 2, 3, 4],
        },
    )

    message = _build_user_message("후보 locator는 쓰지 말 것", [chunk])

    assert "Citation ID: [S1]" in message
    assert "source_registry_hydration_required" not in message
    assert "XLSX locator:" not in message
    assert "PDF locator:" not in message
    assert "HiddenCandidate" not in message
    assert "Z99" not in message
    assert "candidate.xlsx" not in message
    assert "candidate.pdf" not in message
    assert "DO_NOT_PROMOTE" not in message


def test_pdf_xlsx_llm_quality_benchmark_dry_run_records_silver_seed_and_policy(tmp_path: Path) -> None:
    import rag_pdf_xlsx_llm_quality_benchmark as benchmark

    manifest = tmp_path / "manifest.jsonl"
    silver = tmp_path / "silver.jsonl"
    source_identity = "PDF:docv-pdf:su-pdf:lf-pdf"
    manifest.write_text(
        json.dumps(
            {
                "search_view_id": "searchview-pdf",
                "source_family": "PDF",
                "source_atom_id": "srcatom-pdf",
                "source_identity": source_identity,
                "locator_fingerprint": "lf-pdf",
                "parent_search_unit_id": "su-pdf",
                "generation_source_allowed": True,
                "runtime_evidence_allowed": True,
                "official_denominator_overlap": False,
                "display_text": "산림청 정책연구용역 관리규정 별지 제1호서식",
                "embedding_text": "Locator: page=1 | region_type=text_block",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    silver.write_text(
        json.dumps(
            {
                "source_family": "PDF",
                "source_identity": source_identity,
                "locator_fingerprint": "lf-pdf",
                "generated_question_draft": "산림청 별지 서식?",
                "query_quality_profile": "short_keyword_or_fragment",
                "manifest_partition": "core",
                "row_ordinal": 1,
                "diagnostic_only": True,
                "not_gold": True,
                "not_official_denominator": True,
                "not_official_qrels": True,
                "official_metric_denominator_usage_allowed": False,
                "promotion_evidence": False,
                "threshold_tuning": False,
                "winner_selection": False,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = benchmark.run_benchmark(
        manifest_path=manifest,
        silver_manifest_path=silver,
        output_dir=tmp_path,
        run_label="unit",
        model="fake",
        base_url="http://127.0.0.1:9/v1",
        cases_per_family=1,
        max_tokens=32,
        query_max_tokens=32,
        timeout_seconds=1,
        dry_run=True,
    )

    assert summary["status"] == "PASS_DRY_RUN"
    assert summary["case_count"] == 1
    assert summary["silver_seed_match_count"] == 1
    assert summary["silver_join_summary"]["locator_only_fallback_enabled"] is False
    assert summary["query_rewrite_summary"]["query_source_counts"] == {"dry_run_challenge_fallback": 1}
    response_rows = [
        json.loads(line)
        for line in (tmp_path / "pdf_xlsx_llm_quality_unit_responses.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {row["seed_query_source"] for row in response_rows} == {"silver_seed"}
    assert {row["query_source"] for row in response_rows} == {"dry_run_challenge_fallback"}


def test_pdf_xlsx_llm_quality_benchmark_joins_silver_without_locator_only_cross_join(tmp_path: Path) -> None:
    import rag_pdf_xlsx_llm_quality_benchmark as benchmark

    source_identity = "XLSX:docv-xlsx:su-xlsx:lf-shared"
    silver = tmp_path / "silver.jsonl"
    silver.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False)
            for row in [
            {
                "source_family": "XLSX",
                "source_identity": "XLSX:other-doc:su-other:lf-shared",
                "locator_fingerprint": "lf-shared",
                "generated_question_draft": "잘못된 locator-only seed",
                "diagnostic_only": True,
                "not_gold": True,
                "not_official_denominator": True,
                "not_official_qrels": True,
                "official_metric_denominator_usage_allowed": False,
                "promotion_evidence": False,
                "threshold_tuning": False,
                "winner_selection": False,
            },
            {
                "source_family": "XLSX",
                "source_identity": source_identity,
                "locator_fingerprint": "lf-shared",
                "generated_question_draft": "정확한 source identity seed",
                "query_quality_profile": "messy_user_like",
                "row_ordinal": 7,
                "diagnostic_only": True,
                "not_gold": True,
                "not_official_denominator": True,
                "not_official_qrels": True,
                "official_metric_denominator_usage_allowed": False,
                "promotion_evidence": False,
                "threshold_tuning": False,
                "winner_selection": False,
            },
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    index = benchmark.load_silver_seed_index(silver)
    matched = benchmark.find_silver_seed(
        {"source_family": "XLSX", "source_identity": source_identity, "locator_fingerprint": "lf-shared"},
        index,
    )
    mismatched = benchmark.find_silver_seed(
        {"source_family": "XLSX", "source_identity": "XLSX:nope:su-nope:lf-shared", "locator_fingerprint": "lf-shared"},
        index,
    )

    assert matched["generated_question_draft"] == "정확한 source identity seed"
    assert matched["_join_key_used"] == "source_family+source_identity+locator_fingerprint"
    assert mismatched == {}


def test_pdf_xlsx_llm_quality_benchmark_builds_diverse_non_friendly_queries() -> None:
    import rag_pdf_xlsx_llm_quality_benchmark as benchmark

    cases = [
        benchmark.EvidenceCase(
            case_id="pdf-1",
            family="PDF",
            source_atom_id="srcatom-pdf-1",
            doc_id="docv-pdf",
            section="page-1",
            evidence_text="산림청 정책연구용역 관리규정 별지 제1호서식",
            locator={"source_pdf_path": "report.pdf", "page": 1, "bbox": [1, 2, 3, 4], "region_type": "text_block"},
        ),
        benchmark.EvidenceCase(
            case_id="pdf-2",
            family="PDF",
            source_atom_id="srcatom-pdf-2",
            doc_id="docv-pdf",
            section="page-2",
            evidence_text="경쟁입찰 협상에 의한 계약 추진",
            locator={"source_pdf_path": "report.pdf", "page": 2, "bbox": [2, 3, 4, 5], "region_type": "paragraph"},
        ),
        benchmark.EvidenceCase(
            case_id="xlsx-1",
            family="XLSX",
            source_atom_id="srcatom-xlsx-1",
            doc_id="docv-xlsx",
            section="철도",
            evidence_text="5호선 201902 승차총승객수 15446522",
            locator={
                "workbook": "transport.xlsx",
                "sheet": "철도",
                "range": "A352:D401",
                "cell": "D352",
                "row_label": "노선명=5호선 | 년월=201902",
                "target_column": "승차총승객수",
                "normalized_value": "15446522",
            },
        ),
        benchmark.EvidenceCase(
            case_id="xlsx-2",
            family="XLSX",
            source_atom_id="srcatom-xlsx-2",
            doc_id="docv-xlsx",
            section="일반현황",
            evidence_text="해오름요양원 우편번호 41786",
            locator={
                "workbook": "care.xlsx",
                "sheet": "일반현황",
                "range": "A702:J751",
                "cell": "C702",
                "row_label": "장기요양기관이름=해오름요양원",
                "target_column": "우편번호",
                "normalized_value": "41786",
            },
        ),
    ]

    friendly = [benchmark.build_friendly_query(case) for case in cases]
    challenge = [benchmark.build_challenge_query(case, ordinal=index) for index, case in enumerate(cases, start=1)]
    metrics = benchmark.query_quality_metrics(challenge)

    assert len(set(challenge)) == len(challenge)
    assert metrics["query_style_count"] >= 4
    assert metrics["friendly_suffix_ratio"] < 0.5
    assert metrics["max_same_six_char_prefix_count"] <= 1
    assert any(len(query.split()) <= 3 for query in challenge)
    assert all(query not in friendly for query in challenge)
    joined = " ".join(challenge)
    assert "report.pdf" not in joined
    assert "transport" not in joined
    assert "care.xlsx" not in joined
    value_fallback = benchmark.build_challenge_query(cases[2], ordinal=6)
    assert "15446522" not in value_fallback
    assert "D352" not in value_fallback

    silver_case = benchmark.EvidenceCase(
        case_id="silver-xlsx",
        family="XLSX",
        source_atom_id="srcatom-xlsx-silver",
        doc_id="docv-xlsx",
        section="철도",
        evidence_text="5호선 201902 승차총승객수 15446522",
        locator={"sheet": "철도", "cell": "D352", "normalized_value": "15446522"},
        silver_query="5호선 201902 승차총승객수?",
        silver_query_profile="short_keyword_or_fragment",
    )
    friendly_silver_case = benchmark.EvidenceCase(
        case_id="friendly-pdf",
        family="PDF",
        source_atom_id="srcatom-pdf-friendly",
        doc_id="docv-pdf",
        section="page-1",
        evidence_text="경쟁입찰 협상에 의한 계약 추진",
        locator={"page": 1, "bbox": [1, 2, 3, 4]},
        silver_query="경쟁입찰 협상에 의한 계약 추진 현황을 확인해 주세요.",
        silver_query_profile="clean_source_grounded",
    )

    rewrite = benchmark.rewrite_query_with_client(
        silver_case,
        ordinal=1,
        seed_query=silver_case.silver_query,
        llm_client=lambda _system, _user: (
            '{"query":"5호선 201902 승객수?","style":"terse_lookup",'
            '"rationale":"silver seed shortened without internal locators"}'
        ),
    )
    assert rewrite["query_source"] == "llm_rewrite"
    assert rewrite["seed_query_source"] == "silver_seed"
    assert rewrite["query"] == "5호선 201902 승객수?"

    fallback = benchmark.rewrite_query_with_client(
        friendly_silver_case,
        ordinal=2,
        seed_query=friendly_silver_case.silver_query,
        llm_client=lambda _system, _user: (
            '{"query":"report.pdf 경쟁입찰 확인해 주세요.","style":"friendly",'
            '"rationale":"intentionally invalid for fallback coverage"}'
        ),
    )
    assert fallback["query_source"] == "challenge_fallback_after_llm_rewrite"
    assert fallback["query"] != friendly_silver_case.silver_query


def test_pdf_xlsx_llm_quality_benchmark_scores_locator_and_value_grounding() -> None:
    import rag_pdf_xlsx_llm_quality_benchmark as benchmark

    case = benchmark.EvidenceCase(
        case_id="xlsx-1",
        family="XLSX",
        source_atom_id="srcatom-xlsx-1",
        doc_id="docv-xlsx",
        section="철도",
        evidence_text="5호선 201902 승차총승객수 15446522",
        locator={
            "workbook": "transport.xlsx",
            "sheet": "철도",
            "range": "A352:D401",
            "cell": "D352",
            "target_column": "승차총승객수",
            "normalized_value": "15446522",
        },
    )

    supported = benchmark.score_response(
        case,
        '{"answer":"5호선 201902 승차총승객수는 15446522입니다.",'
        '"citations":[{"citation_id":"S1","locator":"철도 D352"}]}',
    )
    locator_only = benchmark.score_response(
        case,
        '{"answer":"철도 D352입니다.","citations":[{"citation_id":"S1","locator":"철도 D352"}]}',
    )
    comma_numeric = benchmark.score_response(
        case,
        '{"answer":"5호선 201902 승차총승객수는 15,446,522입니다.",'
        '"citations":[{"citation_id":"S1","locator":"철도 D352"}]}',
    )

    assert supported["quality_pass"] is True
    assert supported["value_supported"] is True
    assert supported["citation_valid"] is True
    assert comma_numeric["quality_pass"] is True
    assert locator_only["quality_pass"] is False
    assert locator_only["failure_types"] == ["locator_only_answer", "missing_expected_value"]

    pdf_case = benchmark.EvidenceCase(
        case_id="pdf-1",
        family="PDF",
        source_atom_id="srcatom-pdf-1",
        doc_id="docv-pdf",
        section="page-1",
        evidence_text="산림청 정책연구용역 관리규정 별지 제1호서식",
        locator={"page": 1, "bbox": [59.37, 60.71, 327.24, 68.74]},
    )
    pdf_page_only = benchmark.score_response(
        pdf_case,
        '{"answer":"산림청 정책연구용역 관리규정 별지 제1호서식입니다.",'
        '"citations":[{"citation_id":"S1","locator":"page=1"}]}',
    )
    pdf_bbox = benchmark.score_response(
        pdf_case,
        '{"answer":"산림청 정책연구용역 관리규정 별지 제1호서식입니다.",'
        '"citations":[{"citation_id":"S1","locator":"page=1; bbox=[59.37, 60.71, 327.24, 68.74]"}]}',
    )
    assert "pdf_locator_missing" in pdf_page_only["failure_types"]
    assert "pdf_locator_missing" not in pdf_bbox["failure_types"]

    summary = benchmark.answer_quality_summary(
        [
            {"prompt_mode": "baseline_legacy_context", "family": "PDF", "score": supported},
            {"prompt_mode": "final_locator_context", "family": "PDF", "score": supported},
            {"prompt_mode": "baseline_legacy_context", "family": "XLSX", "score": locator_only},
            {"prompt_mode": "final_locator_context", "family": "XLSX", "score": supported},
        ]
    )
    assert summary["delta_by_family_final_minus_baseline"]["PDF"]["quality_pass"] == 0
    assert summary["delta_by_family_final_minus_baseline"]["XLSX"]["quality_pass"] == 1
    assert summary["delta_final_minus_baseline"]["diagnostic_aggregate_only"] is True
